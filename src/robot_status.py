"""
Módulo de diagnóstico para el robot UR10e.
Este script establece una conexión de recepción (RTDE) para consultar 
el estado actual de las articulaciones y la pose del TCP.
"""

import rtde_receive
import os
import sys

def main():
    # Configuración de la dirección IP desde variables de entorno
    robot_ip = os.getenv("ROBOT_IP", "192.168.0.210")

    try:
        print(f"[*] Estableciendo conexión con el robot en {robot_ip}...")
        
        # Inicialización de la interfaz de recepción
        rtde_rec = rtde_receive.RTDEReceiveInterface(robot_ip)
        
        # Extracción de datos de telemetría
        actual_q = rtde_rec.getActualQ()
        actual_tcp = rtde_rec.getActualTCPPose()
        
        print("\n[SUCCESS] Conexión establecida correctamente.")
        print("-" * 40)
        print(f"Posiciones articulares (q) [rad]:\n  {actual_q}")
        print(f"Pose del TCP (x, y, z, rx, ry, rz) [m/rad]:\n  {actual_tcp}")
        print("-" * 40)

    except Exception as e:
        print(f"\n[ERROR] No se pudo establecer comunicación con el robot: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
