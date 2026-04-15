"""
Módulo de control de movimiento para el robot UR10e.
Ejecuta una trayectoria lineal (moveL) entre dos puntos definidos por 
ángulos articulares, garantizando una trayectoria horizontal constante (Z constante).
"""

import rtde_control
import math
import time
import os
import sys

def main():
    # Configuración de red
    robot_ip = os.getenv("ROBOT_IP", "192.168.1.224")

    # Definición de coordenadas objetivo (Grados)
    # Origen: Posición de inicio del escaneo
    origin_deg = [-143.03, -62.89, 81.82, -110.44, -92.18, 0.00]
    # Fin: Posición final del escaneo
    end_deg = [-57.92, -68.94, 88.45, -113.97, -88.96, 0.03]

    # Conversión a radianes para compatibilidad con UR_RTDE
    origin_q = [math.radians(d) for d in origin_deg]
    end_q = [math.radians(d) for d in end_deg]

    try:
        print(f"[*] Inicializando interfaz de control en {robot_ip}...")
        rtde_ctrl = rtde_control.RTDEControlInterface(robot_ip)

        # Configuración de dinámica de movimiento
        velocity = 0.25      # m/s
        acceleration = 0.2   # m/s^2

        # Cálculo de cinemática directa para obtener poses cartesianas (TCP)
        print("[*] Calculando trayectoria plana...")
        origin_pose = rtde_ctrl.getForwardKinematics(origin_q)
        end_pose = rtde_ctrl.getForwardKinematics(end_q)

        # RESTRICCIÓN DE SEGURIDAD: Sincronización de altura (Z)
        # Se fuerza la coordenada Z del destino para que coincida con la del origen.
        # Esto previene desplazamientos en pendiente durante el escaneo del perfilómetro.
        end_pose[2] = origin_pose[2]
        
        print(f"  > Z de referencia: {origin_pose[2]:.4f} m")

        # Ejecución de secuencia de movimiento
        print("\n[1/2] Moviendo a posición de ORIGEN...")
        rtde_ctrl.moveL(origin_pose, velocity, acceleration)
        
        print("[*] Estabilizando posición...")
        time.sleep(1.0)

        print("[2/2] Ejecutando barrido lineal a posición de FIN...")
        rtde_ctrl.moveL(end_pose, velocity, acceleration)

        print("\n[SUCCESS] Trayectoria completada con éxito.")

    except Exception as e:
        print(f"\n[ERROR] Error crítico durante la ejecución: {e}")
        sys.exit(1)

    finally:
        if 'rtde_ctrl' in locals():
            rtde_ctrl.stopScript()
            print("[*] Interfaz de control liberada.")

if __name__ == "__main__":
    main()
