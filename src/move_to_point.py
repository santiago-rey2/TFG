"""
Módulo para ejecutar movimientos lineales (moveL) a puntos del archivo activo.
Incluye mecanismo de parada de emergencia en tiempo real mediante [ENTER] o [ESPACIO].
"""

import os
import sys
import time
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from rtde_control import RTDEControlInterface as RTDEControl
except ImportError:
    RTDEControl = None

from points_manager import listar_puntos, leer_puntos
from config_manager import seleccionar_setup
from keyboard_listener import escuchar_parada, limpiar_buffer_teclado


def mover_a_punto(robot_ip, config):
    """Selecciona un punto del archivo activo y ejecuta el moveL con parada de emergencia."""
    claves = listar_puntos()
    if not claves:
        return

    idx_str = input(f"\nSelecciona el punto objetivo [1-{len(claves)}] (o 'c' para cancelar): ").strip()
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
    setup = seleccionar_setup(config)

    print(f"\n[*] Preparando movimiento hacia '{nombre_punto}' usando setup '{setup['name']}'...")
    print(f"    Destino   : {pose_destino}")
    print(f"    Velocidad : {setup['speed']} m/s | Aceleración: {setup['acceleration']} m/s^2")
    print("\n[!] >> Pulsa [ENTER] o [ESPACIO] para PARAR el robot en cualquier momento <<\n")

    # Iniciar detector de pulsación en hilo paralelo
    stop_requested = threading.Event()
    listener = threading.Thread(target=escuchar_parada, args=(stop_requested,), daemon=True)
    listener.start()

    rtde_ctrl = None
    try:
        print(f"[*] Conectando con UR10e en {robot_ip}...")
        rtde_ctrl = RTDEControl(robot_ip)

        # Iniciar movimiento lineal en modo asíncrono
        rtde_ctrl.moveL(pose_destino, setup["speed"], setup["acceleration"], True)
        time.sleep(0.15)  # Margen para que el controlador inicie la interpolación

        detenido_manualmente = False

        # Monitorear hasta que el robot llegue o se solicite la parada
        while not rtde_ctrl.isSteady():
            if stop_requested.is_set():
                detenido_manualmente = True
                print("\n\n[PARADA DE EMERGENCIA] ¡Pulsación detectada! Frenando el robot...")
                rtde_ctrl.stopL(10.0)  # Frenado inmediato
                break
            time.sleep(0.04)

        if detenido_manualmente:
            print(f"[ALERTA] Movimiento hacia '{nombre_punto}' DETENIDO por el usuario.")
        else:
            print(f"\n[OK] Movimiento a '{nombre_punto}' completado con éxito.")

    except Exception as e:
        print(f"\n[ERROR] Fallo durante la ejecución de moveL: {e}", file=sys.stderr)
    finally:
        stop_requested.set()
        limpiar_buffer_teclado()
        if rtde_ctrl is not None:
            try:
                rtde_ctrl.stopScript()
            except Exception:
                pass
            print("[*] Conexión liberada.")
