"""
Orquestador principal del robot UR10e.
Coordina los módulos funcionales del sistema:
  - points_manager    : Gestión, listado y selección de archivos de puntos y configuraciones.
  - check_pose        : Consulta de la pose TCP actual.
  - move_to_point     : Movimiento a puntos con parada de emergencia.
  - teach_mode        : Modo guiado manual (Freedrive).
  - offset_calculator : Cálculo de punto final según offset/distancia de pieza XYZ (Experimental).
"""

import os
import sys

# Asegurar que el directorio src/ esté en el PATH para importaciones limpias
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
from points_manager import (
    cargar_config_movimiento,
    listar_puntos,
    almacenar_posicion_actual,
    get_nombre_archivo_puntos,
    set_puntos_path,
    seleccionar_archivo_puntos_interactivo,
)
from check_pose import comprobar_punto_actual
from move_to_point import mover_a_punto
from teach_mode import activar_modo_manual
from offset_calculator import calcular_offset_interactivo


def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    load_dotenv(dotenv_path=os.path.join(base_dir, ".env"))
    load_dotenv()
    robot_ip = os.getenv("ROBOT_IP", "192.168.1.224")

    # Permitir especificar el archivo de puntos por argumento de consola o variable de entorno
    if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
        set_puntos_path(sys.argv[1])
    elif os.getenv("POINTS_FILE"):
        set_puntos_path(os.getenv("POINTS_FILE"))

    config = cargar_config_movimiento()

    while True:
        archivo_activo = get_nombre_archivo_puntos()
        print("\n" + "=" * 55)
        print("          ORQUESTADOR DE CONTROL UR10e")
        print(f"  Archivo de posiciones activo: {archivo_activo}")
        print("=" * 55)
        print("  [1] Listar puntos disponibles")
        print("  [2] Comprobar pose TCP actual del robot")
        print("  [3] Mover el robot a un punto")
        print("  [4] Modo guiado manual libre (Teach Mode)")
        print("  [5] Almacenar posición actual")
        print("  [6] Seleccionar / Cambiar archivo de posiciones")
        print("  [7] Calcular punto final por offset XYZ (Experimental)")
        print("  [8] Salir")
        print("-" * 55)

        opcion = input("Elige una opción [1-8]: ").strip()

        if opcion == "1":
            listar_puntos()
        elif opcion == "2":
            comprobar_punto_actual(robot_ip)
        elif opcion == "3":
            mover_a_punto(robot_ip, config)
        elif opcion == "4":
            activar_modo_manual(robot_ip)
        elif opcion == "5":
            almacenar_posicion_actual(robot_ip)
        elif opcion == "6":
            seleccionar_archivo_puntos_interactivo()
        elif opcion == "7":
            calcular_offset_interactivo(robot_ip)
        elif opcion in ("8", "q", "exit"):
            print("\nSaliendo del orquestador.")
            break
        else:
            print("[!] Opción no válida. Introduce un número del 1 al 8.")


if __name__ == "__main__":
    main()
