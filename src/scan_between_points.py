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
from datetime import datetime

try:
    import gocator
    from gocator import ProfileScan, Settings
except ImportError:
    gocator = None
    ProfileScan = None
    Settings = None

from points_manager import listar_puntos, leer_puntos
from arm_connection import conexion_control, mover_lineal_con_parada

# Directorio de salida de los escaneos (<raíz del proyecto>/scans/, montado como volumen en Docker)
SCANS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scans")


def escanear_a_punto(arm_ip, gocator_ip, config):
    """
    Selecciona un punto objetivo del archivo activo y se mueve hacia él desde
    la posición actual mientras adquiere perfiles con el Gocator 2600 usando el setup 'scan'.

    :param arm_ip: Dirección IP del controlador del brazo UR10e.
    :param gocator_ip: Dirección IP del perfilómetro Gocator 2600.
    :param config: Configuración de movimiento cargada desde movement_config.json.
    """
    if gocator is None or ProfileScan is None or Settings is None:
        print("\n[ERROR] La librería 'gocator-py' no está instalada en este entorno.")
        return

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

    try:
        with conexion_control(arm_ip) as rtde_ctrl:
            print(f"[*] Conectando con perfilómetro Gocator en {gocator_ip}...")
            with gocator.connect(gocator_ip) as sensor:
                # Encender el sensor antes de iniciar el movimiento
                with ProfileScan(sensor, ajustes_escaneo, frame_rate="auto") as scan:
                    print(f"[*] Sensor activo ({scan.frame_rate:.1f} Hz). Iniciando movimiento lineal (moveL)...")

                    def mostrar_progreso():
                        # Mostrar progreso en tiempo real
                        print(f"\r[*] Progreso: {scan.received} perfiles recibidos ({scan.rows} filas)",
                              end="", flush=True)

                    detenido_manualmente = mover_lineal_con_parada(
                        rtde_ctrl, pose_destino, speed, acceleration, al_monitorizar=mostrar_progreso
                    )

                    print()
                    if detenido_manualmente:
                        print(f"[ALERTA] Movimiento hacia '{nombre_punto}' DETENIDO por el usuario.")
                    else:
                        print(f"[OK] Movimiento hacia '{nombre_punto}' completado con éxito.")

                # Al salir del bloque with ProfileScan, el sensor se detiene y construye scan.result
                result = scan.result

            # Guardar en disco si se recibieron datos
            # (el detector de parada ya está detenido, por lo que input() funciona con normalidad)
            if result is not None and scan.received > 0:
                os.makedirs(SCANS_DIR, exist_ok=True)

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

                carpeta = result.save(out_dir=SCANS_DIR, name=nombre_guardado, info=info_meta)
                print(f"[OK] Escaneo guardado en: {carpeta}")
            else:
                print("[!] No se recibieron perfiles durante el escaneo.")

    except Exception as e:
        print(f"\n[ERROR] Fallo durante la ejecución del escaneo: {e}", file=sys.stderr)


# Alias para retrocompatibilidad con main.py
escanear_entre_puntos = escanear_a_punto
