"""
Módulo Experimental: Cálculo de punto final mediante offset/distancia de pieza (XYZ).
Permite calcular una nueva pose TCP sumando o restando desplazamientos en los ejes X, Y, Z
a partir de una posición inicial (punto guardado, pose en vivo o entrada manual).
"""

import os
import sys
import math

# Asegurar que el directorio src/ esté en el PATH para importaciones limpias
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from points_manager import (
    leer_puntos,
    listar_puntos,
    guardar_punto,
    get_nombre_archivo_puntos,
    generar_siguiente_nombre_punto,
)
from check_pose import comprobar_punto_actual


def calcular_punto_final(pose_origen, dx=0.0, dy=0.0, dz=0.0):
    """
    Calcula la pose TCP resultante aplicando los desplazamientos dx, dy, dz (en metros)
    a las coordenadas X, Y, Z de la pose_origen.
    Mantiene intacta la orientación angular (Rx, Ry, Rz).

    :param pose_origen: Lista de 6 floats [X, Y, Z, Rx, Ry, Rz]
    :param dx: Desplazamiento en eje X en metros (positivo o negativo)
    :param dy: Desplazamiento en eje Y en metros (positivo o negativo)
    :param dz: Desplazamiento en eje Z en metros (positivo o negativo)
    :return: Lista de 6 floats con la pose final redondeada a 6 decimales.
    """
    if not pose_origen or len(pose_origen) != 6:
        raise ValueError("La pose de origen debe contener exactamente 6 valores [X, Y, Z, Rx, Ry, Rz]")

    x_fin = round(float(pose_origen[0]) + float(dx), 6)
    y_fin = round(float(pose_origen[1]) + float(dy), 6)
    z_fin = round(float(pose_origen[2]) + float(dz), 6)

    rx = round(float(pose_origen[3]), 6)
    ry = round(float(pose_origen[4]), 6)
    rz = round(float(pose_origen[5]), 6)

    return [x_fin, y_fin, z_fin, rx, ry, rz]


def solicitar_offset(eje_nombre):
    """Solicita un desplazamiento numérico por consola (permite positivos y negativos)."""
    while True:
        entrada = input(f"  Desplazamiento en {eje_nombre} (metros, ej. 0.05 o -0.10) [0.0]: ").strip()
        if not entrada:
            return 0.0
        try:
            return float(entrada)
        except ValueError:
            print(f"  [!] Entrada inválida. Introduce un número real para {eje_nombre}.")


def calcular_offset_interactivo(robot_ip=None):
    """
    Asistente interactivo por consola para calcular y opcionalmente guardar
    el punto final a partir de desplazamientos XYZ de pieza.
    """
    print("\n" + "=" * 60)
    print("  CÁLCULO DE PUNTO FINAL POR OFFSET DE PIEZA (XYZ) - EXPERIMENTAL")
    print("=" * 60)
    print("¿Desde qué posición deseas partir?")
    print("  [1] Seleccionar un punto guardado del archivo activo")
    print("  [2] Capturar la pose TCP actual del robot (en tiempo real)")
    print("  [3] Introducir manualmente las coordenadas TCP [X,Y,Z,Rx,Ry,Rz]")
    print("  [c] Cancelar")
    print("-" * 60)

    opcion = input("Elige una opción [1-3] (o 'c' para cancelar): ").strip()
    if opcion.lower() in ("c", "cancelar", "q", "exit"):
        print("[*] Operación cancelada.")
        return None

    pose_origen = None
    nombre_origen = "Manual"

    if opcion == "1":
        claves = listar_puntos()
        if not claves:
            return None
        idx_str = input(f"\nSelecciona el punto origen [1-{len(claves)}]: ").strip()
        try:
            idx = int(idx_str) - 1
            if not (0 <= idx < len(claves)):
                print("[!] Índice fuera de rango.")
                return None
            nombre_origen = claves[idx]
            puntos = leer_puntos()
            pose_origen = puntos[nombre_origen]["pose"]
        except ValueError:
            print("[!] Entrada no válida.")
            return None

    elif opcion == "2":
        if not robot_ip:
            robot_ip = os.getenv("ROBOT_IP", "192.168.1.224")
        print(f"[*] Obteniendo pose TCP actual desde {robot_ip}...")
        pose_origen = comprobar_punto_actual(robot_ip)
        if not pose_origen:
            print("[!] No se pudo obtener la pose del robot.")
            return None
        nombre_origen = "Pose_Actual_Robot"

    elif opcion == "3":
        print("\nIntroduce los 6 valores separados por comas o espacios:")
        print("Ejemplo: -0.46213, -0.103808, 0.169564, 1.8092, 1.901, 0.5625")
        entrada = input("Coordenadas: ").strip().replace(",", " ")
        partes = [p for p in entrada.split() if p]
        if len(partes) != 6:
            print(f"[!] Se esperaban 6 valores, se recibieron {len(partes)}.")
            return None
        try:
            pose_origen = [float(v) for v in partes]
        except ValueError:
            print("[!] Formato numérico incorrecto.")
            return None
    else:
        print("[!] Opción inválida.")
        return None

    print(f"\n--- Posición de Origen: {nombre_origen} ---")
    print(f"  Pose: {pose_origen}")
    print(f"  X: {pose_origen[0]:.6f} m | Y: {pose_origen[1]:.6f} m | Z: {pose_origen[2]:.6f} m")
    print(f"  Rx: {pose_origen[3]:.6f} | Ry: {pose_origen[4]:.6f} | Rz: {pose_origen[5]:.6f}")

    print("\nIntroduce las distancias a sumar o restar respecto a la pieza (en metros):")
    dx = solicitar_offset("X (desplazamiento lateral)")
    dy = solicitar_offset("Y (desplazamiento longitudinal)")
    dz = solicitar_offset("Z (desplazamiento vertical / altura)")

    pose_final = calcular_punto_final(pose_origen, dx, dy, dz)
    distancia_total = math.sqrt(dx**2 + dy**2 + dz**2)

    print("\n" + "=" * 60)
    print("                    RESULTADO DEL CÁLCULO")
    print("=" * 60)
    print(f"  Punto Origen : {pose_origen}")
    print(f"  Offset XYZ   : dX = {dx:+.6f} m, dY = {dy:+.6f} m, dZ = {dz:+.6f} m")
    print(f"  Distancia 3D : {distancia_total:.6f} m ({distancia_total * 1000:.2f} mm)")
    print(f"  PUNTO FINAL  : {pose_final}")
    print("=" * 60)

    if abs(dz) > 1e-6:
        print("\n  [!] AVISO TFG: Has modificado la altura Z (dZ != 0).")
        print("      Si esta trayectoria es para el perfilómetro Gocator,")
        print("      asegúrate de que la distancia de trabajo respecto a la pieza sea adecuada.")

    # Opción para almacenar el nuevo punto en el archivo de puntos activo
    archivo_activo = get_nombre_archivo_puntos()
    guardar = input(f"\n¿Deseas almacenar este punto final en '{archivo_activo}'? (s/N): ").strip().lower()
    if guardar in ("s", "si", "y", "yes"):
        puntos = leer_puntos()
        nombre_por_defecto = generar_siguiente_nombre_punto(puntos)
        entrada_nombre = input(f"Introduce una etiqueta para este punto (Enter para '{nombre_por_defecto}'): ").strip()
        nombre_final = entrada_nombre if entrada_nombre else nombre_por_defecto

        desc_default = f"Offset desde {nombre_origen} (dx={dx:+.4f}, dy={dy:+.4f}, dz={dz:+.4f})"
        desc = input(f"Descripción (Enter para '{desc_default}'): ").strip()
        desc_final = desc if desc else desc_default

        guardar_punto(nombre_final, pose_final, desc_final)

    return pose_final


if __name__ == "__main__":
    from dotenv import load_dotenv
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    load_dotenv(dotenv_path=os.path.join(base_dir, ".env"))
    load_dotenv()
    robot_ip_env = os.getenv("ROBOT_IP", "192.168.1.224")
    calcular_offset_interactivo(robot_ip_env)
