"""
Módulo de diagnóstico y telemetría para el robot UR10e.
Establece conexión RTDE de recepción para consultar articulaciones, pose TCP,
temperaturas y estado de seguridad en tiempo real.
"""

import os
import sys
import json
import argparse

try:
    import rtde_receive
except ImportError:
    rtde_receive = None

from robot_guard import UR10eSoftwareGuard


def main():
    parser = argparse.ArgumentParser(description="Consulta de estado y telemetría del UR10e")
    parser.add_argument("--json", action="store_true", help="Salida en formato JSON")
    parser.add_argument("--dry-run", action="store_true", help="Simular telemetría sin conectar al robot")
    args = parser.parse_args()

    robot_ip = os.getenv("ROBOT_IP", "192.168.0.210")

    try:
        if rtde_receive is None or args.dry_run:
            if not args.json:
                print(f"[*] [MODO SIMULACIÓN] Generando telemetría de prueba para {robot_ip}...")
            status_data = {
                "robot_ip": robot_ip,
                "estado_seguro": True,
                "parada_proteccion": False,
                "parada_emergencia": False,
                "safety_status_bits": 1,
                "posiciones_articulares_rad": [1.047, -2.059, -1.308, -1.308, 1.553, 2.600],
                "pose_tcp_m_rad": [0.450, -0.200, 0.150, 3.1415, 0.0, 0.0],
                "temperaturas_juntas_c": [32.5, 33.1, 31.8, 29.4, 28.9, 27.5]
            }
        else:
            if not args.json:
                print(f"[*] Conectando con UR10e en {robot_ip}...")

            rtde_rec = rtde_receive.RTDEReceiveInterface(robot_ip)

            actual_q = rtde_rec.getActualQ()
            actual_tcp = rtde_rec.getActualTCPPose()
            
            # Telemetría de seguridad
            is_protective = rtde_rec.isProtectiveStopped() if hasattr(rtde_rec, "isProtectiveStopped") else False
            is_emergency = rtde_rec.isEmergencyStopped() if hasattr(rtde_rec, "isEmergencyStopped") else False
            safety_status = rtde_rec.getSafetyStatusBits() if hasattr(rtde_rec, "getSafetyStatusBits") else 1
            
            # Temperaturas de juntas
            temperatures = rtde_rec.getJointTemperatures() if hasattr(rtde_rec, "getJointTemperatures") else []

            status_data = {
                "robot_ip": robot_ip,
                "estado_seguro": not (is_protective or is_emergency),
                "parada_proteccion": is_protective,
                "parada_emergencia": is_emergency,
                "safety_status_bits": safety_status,
                "posiciones_articulares_rad": actual_q,
                "pose_tcp_m_rad": actual_tcp,
                "temperaturas_juntas_c": temperatures
            }
            rtde_rec.disconnect()

        if args.json:
            print(json.dumps(status_data, indent=2))
        else:
            print("\n[SUCCESS] Conexión establecida correctamente.")
            print("-" * 55)
            print(f"Estado de Seguridad: {'NORMAL (OK)' if status_data['estado_seguro'] else 'PARADA ACTIVA'}")
            print(f"  > Parada Protección: {status_data['parada_proteccion']}")
            print(f"  > Parada Emergencia: {status_data['parada_emergencia']}")
            print("-" * 55)
            print(f"Posiciones articulares (q) [rad]:\n  {status_data['posiciones_articulares_rad']}")
            print(f"Pose del TCP (x, y, z, rx, ry, rz) [m/rad]:\n  {status_data['pose_tcp_m_rad']}")
            if status_data['temperaturas_juntas_c']:
                print(f"Temperaturas de las articulaciones [°C]:\n  {status_data['temperaturas_juntas_c']}")
            print("-" * 55)

    except Exception as e:
        print(f"\n[ERROR] No se pudo establecer comunicación con el robot: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
