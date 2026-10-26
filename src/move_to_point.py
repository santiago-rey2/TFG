"""
Módulo para ejecutar movimientos lineales (moveL) a puntos del archivo activo.
Incluye mecanismo de parada de emergencia en tiempo real mediante [ENTER] o [ESPACIO].
"""

import sys

from points_manager import listar_puntos, leer_puntos
from config_manager import seleccionar_setup
from arm_connection import conexion_control, mover_lineal_con_parada


def mover_a_punto(arm_ip, config):
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

    try:
        with conexion_control(arm_ip) as rtde_ctrl:
            detenido_manualmente = mover_lineal_con_parada(
                rtde_ctrl, pose_destino, setup["speed"], setup["acceleration"]
            )

        if detenido_manualmente:
            print(f"[ALERTA] Movimiento hacia '{nombre_punto}' DETENIDO por el usuario.")
        else:
            print(f"\n[OK] Movimiento a '{nombre_punto}' completado con éxito.")

    except Exception as e:
        print(f"\n[ERROR] Fallo durante la ejecución de moveL: {e}", file=sys.stderr)
