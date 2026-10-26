"""
Módulo para el control de modo manual guiado (Teach Mode / Freedrive) en el robot UR10e.
Permite liberar los frenos para mover el brazo con la mano y fijar la posición al terminar.
"""

import sys

from arm_connection import conexion_control
from check_pose import comprobar_punto_actual


def activar_modo_manual(arm_ip):
    """
    Activa teachMode() para mover el brazo libremente con la mano (Freedrive).
    Al pulsar Enter, llama a endTeachMode() y muestra por consola la nueva pose TCP obtenida.
    """
    print()
    try:
        with conexion_control(arm_ip) as rtde_ctrl:
            try:
                print("[*] Activando teachMode() (Modo Guiado Manual / Freedrive)...")
                if rtde_ctrl.teachMode():
                    print("\n" + "=" * 55)
                    print("  MODO MANUAL (FREEDRIVE) ACTIVADO")
                    print("  Mueve el brazo robótico libremente con la mano.")
                    print("=" * 55)
                    input("\n>> Pulsa [ENTER] cuando hayas terminado de posicionar el robot <<\n")

                    print("[*] Desactivando modo manual con endTeachMode()...")
                    rtde_ctrl.endTeachMode()
                    print("[OK] Modo manual desactivado. Posición del robot fijada.")
                else:
                    print("[ERROR] El controlador no permitió activar teachMode().")
            finally:
                # Seguridad: nunca dejar el brazo en freedrive (se ejecuta antes de stopScript)
                try:
                    rtde_ctrl.endTeachMode()
                except Exception:
                    pass
    except Exception as e:
        print(f"\n[ERROR] Fallo al activar/desactivar el modo manual: {e}", file=sys.stderr)

    # Mostrar la nueva posición obtenida tras el posicionamiento manual
    print("\n--- NUEVA POSICIÓN DEL ROBOT TRAS GUIADO MANUAL ---")
    nueva_pose = comprobar_punto_actual(arm_ip)

    if nueva_pose:
        from points_manager import get_nombre_archivo_puntos, almacenar_posicion_actual
        archivo_activo = get_nombre_archivo_puntos()
        guardar = input(f"\n¿Deseas almacenar esta posición en {archivo_activo}? (s/N): ").strip().lower()
        if guardar in ("s", "si", "y", "yes"):
            almacenar_posicion_actual(arm_ip, pose_previa=nueva_pose)
