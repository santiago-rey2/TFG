"""
Módulo para ejecutar escaneos con el perfilómetro Gocator 2600 mientras
el robot UR10e se desplaza hacia un punto objetivo desde su posición actual.

Sigue la misma estructura y filosofía que move_to_point.py:
  1. Selecciona el punto destino del archivo de puntos activo.
  2. Aplica automáticamente la configuración cinemática 'scan' de movement_config.json.
  3. Enciende el perfilómetro en segundo plano (ProfileScan) antes de iniciar el movimiento.
  4. Ejecuta el movimiento lineal (moveL) con parada de emergencia ([ENTER] / [ESPACIO]).
  5. Apaga el sensor y guarda los resultados en disco (scans/<nombre>/).
"""

import os
import sys
import time
import threading
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from rtde_control import RTDEControlInterface as RTDEControl
except ImportError:
    RTDEControl = None

try:
    import gocator
    from gocator import ProfileScan, Settings
except ImportError:
    gocator = None
    ProfileScan = None
    Settings = None

from points_manager import listar_puntos, leer_puntos
from config_manager import cargar_config_movimiento
from keyboard_listener import escuchar_parada, limpiar_buffer_teclado


def escanear_a_punto(robot_ip=None, gocator_ip=None, config=None):
    """
    Selecciona un punto objetivo del archivo activo y se mueve hacia él desde
    la posición actual mientras adquiere perfiles con el Gocator 2600 usando el setup 'scan'.
    """
    if gocator is None or ProfileScan is None or Settings is None:
        print("\n[ERROR] La librería 'gocator-py' no está instalada en este entorno.")
        return

    if RTDEControl is None:
        print("\n[ERROR] La librería 'ur_rtde' no está disponible.")
        return

    if not robot_ip:
        robot_ip = os.getenv("ROBOT_IP", "192.168.0.210")
    if not gocator_ip:
        gocator_ip = os.getenv("GOCATOR_IP", "192.168.1.10")
    if not config:
        config = cargar_config_movimiento()

    claves = listar_puntos()
    if not claves:
        return

    idx_str = input(f"\nSelecciona el punto objetivo para escanear [1-{len(claves)}] (o 'c' para cancelar): ").strip()
    if idx_str.lower() in ("c", "cancelar", "q", "exit"):
        return

    try:
        idx = int(idx_str) - 1
        if not (0 <= idx < len(claves)):
            print("[!] Índice fuera de rango.")
            return
        nombre_punto = claves[idx]
    except ValueError:
        print("[!] Entrada no válida.")
        return

    puntos = leer_puntos()
    pose_destino = puntos[nombre_punto]["pose"]

    # Usar siempre la configuración 'scan' establecida en movement_config.json
    setups = config.get("setups", {})
    setup_scan = setups.get("scan", {})
    speed = float(setup_scan.get("speed", 0.008))
    acceleration = float(setup_scan.get("acceleration", 0.1))
    travel_speed_mms = speed * 1000.0  # mm/s requerido por Gocator

    print(f"\n[*] Preparando movimiento y escaneo hacia '{nombre_punto}' usando setup 'scan'...")
    print(f"    Destino   : {pose_destino}")
    print(f"    Velocidad : {speed} m/s ({travel_speed_mms:.1f} mm/s) | Aceleración: {acceleration} m/s^2")
    print("\n[!] >> Pulsa [ENTER] o [ESPACIO] para PARAR el robot y el escaneo en cualquier momento <<\n")

    # Ajustes temporales solo para este escaneo
    ajustes_escaneo = Settings(
        scan_mode="profile",
        trigger_source="time",
        travel_speed=round(travel_speed_mms, 3),  # mm/s coincidente con la velocidad real del robot
        exposure=120.0,                           # us
        uniform_spacing=True,                     # True = imagen 2D (alturas e intensidad)
    )

    # Iniciar detector de parada de emergencia en hilo paralelo
    stop_requested = threading.Event()
    listener = threading.Thread(target=escuchar_parada, args=(stop_requested,), daemon=True)
    listener.start()

    rtde_ctrl = None
    try:
        print(f"[*] Conectando con UR10e en {robot_ip}...")
        rtde_ctrl = RTDEControl(robot_ip)

        print(f"[*] Conectando con perfilómetro Gocator en {gocator_ip}...")
        with gocator.connect(gocator_ip) as sensor:
            # Encender el sensor antes de iniciar el movimiento
            with ProfileScan(sensor, ajustes_escaneo, frame_rate="auto") as scan:
                print(f"[*] Sensor activo ({scan.frame_rate:.1f} Hz). Iniciando movimiento lineal (moveL)...")

                # Iniciar movimiento lineal en modo asíncrono
                rtde_ctrl.moveL(pose_destino, speed, acceleration, True)
                time.sleep(0.15)  # Margen para que el controlador inicie la interpolación

                detenido_manualmente = False

                # Monitorear hasta que el robot llegue o se solicite la parada
                while not rtde_ctrl.isSteady():
                    if stop_requested.is_set():
                        detenido_manualmente = True
                        print("\n\n[PARADA DE EMERGENCIA] ¡Pulsación detectada! Frenando el robot...")
                        rtde_ctrl.stopL(10.0)  # Frenado inmediato
                        break

                    # Mostrar progreso en tiempo real
                    print(f"\r[*] Progreso: {scan.received} perfiles recibidos ({scan.rows} filas)", end="", flush=True)
                    time.sleep(0.04)

                print()
                if detenido_manualmente:
                    print(f"[ALERTA] Movimiento hacia '{nombre_punto}' DETENIDO por el usuario.")
                else:
                    print(f"[OK] Movimiento hacia '{nombre_punto}' completado con éxito.")

            # Al salir del bloque with ProfileScan, el sensor se detiene y construye scan.result
            result = scan.result

        # Guardar en disco si se recibieron datos
        if result is not None and scan.received > 0:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            scans_dir = os.path.join(base_dir, "scans")
            os.makedirs(scans_dir, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            nombre_defecto = f"scan_{nombre_punto}_{timestamp}"
            entrada_nombre = input(f"\nNombre para la carpeta del escaneo (Enter para '{nombre_defecto}'): ").strip()
            nombre_guardado = entrada_nombre if entrada_nombre else nombre_defecto

            info_meta = {
                "punto_destino": nombre_punto,
                "pose_destino": pose_destino,
                "robot_speed_ms": speed,
                "travel_speed_mms": travel_speed_mms,
                "acceleration": acceleration,
                "detenido_manualmente": detenido_manualmente,
                "perfiles": scan.received,
                "filas": scan.rows,
            }

            carpeta = result.save(out_dir=scans_dir, name=nombre_guardado, info=info_meta)
            print(f"[OK] Escaneo guardado en: {carpeta}")
        else:
            print("[!] No se recibieron perfiles durante el escaneo.")

    except Exception as e:
        print(f"\n[ERROR] Fallo durante la ejecución del escaneo: {e}", file=sys.stderr)
    finally:
        stop_requested.set()
        limpiar_buffer_teclado()
        if rtde_ctrl is not None:
            try:
                rtde_ctrl.stopScript()
            except Exception:
                pass
            print("[*] Conexión liberada.")


# Alias para retrocompatibilidad con main.py
escanear_entre_puntos = escanear_a_punto


if __name__ == "__main__":
    from dotenv import load_dotenv

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    load_dotenv(dotenv_path=os.path.join(base_dir, ".env"))
    load_dotenv()

    robot_ip_env = os.getenv("ROBOT_IP", "192.168.1.224")
    gocator_ip_env = os.getenv("GOCATOR_IP", "192.168.1.10")
    config_mov = cargar_config_movimiento()

    escanear_a_punto(robot_ip_env, gocator_ip_env, config_mov)
