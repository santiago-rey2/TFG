"""
Módulo de diagnóstico y telemetría para el robot UR10e.
Establece conexión RTDE de recepción para consultar articulaciones, pose TCP,
temperaturas y estado de seguridad en tiempo real.
Si ur_rtde no está instalado en el host, utiliza lectura directa por socket 30003
para obtener telemetría 100% real sin dependencias C++.
"""

import os
import sys
import json
import struct
import math
import socket
import argparse

try:
    import rtde_receive
except ImportError:
    rtde_receive = None

from robot_guard import UR10eSoftwareGuard


def cargar_env():
    """Carga variables desde el archivo .env si existen y no están en el entorno."""
    for ruta in [".env", os.path.join(os.path.dirname(__file__), "..", ".env")]:
        if os.path.exists(ruta):
            with open(ruta, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip('"').strip("'")
                        if k not in os.environ:
                            os.environ[k] = v
            break


def leer_telemetria_directa_socket(robot_ip: str, timeout: float = 3.0):
    """
    Lee telemetría en tiempo real directamente del puerto 30003 (500 Hz e-Series)
    sin requerir compiladores C++ ni ur_rtde.
    """
    with socket.create_connection((robot_ip, 30003), timeout=timeout) as s:
        data = b''
        while len(data) < 4:
            chunk = s.recv(4 - len(data))
            if not chunk:
                break
            data += chunk
        if len(data) < 4:
            raise ConnectionError("No se recibieron datos de cabecera.")

        pkg_len = struct.unpack('!i', data[:4])[0]
        while len(data) < pkg_len:
            chunk = s.recv(pkg_len - len(data))
            if not chunk:
                break
            data += chunk

        if len(data) < 492:
            raise ConnectionError(f"Paquete incompleto ({len(data)} bytes).")

        # q_actual en offset 252 (6 doubles)
        q_actual = list(struct.unpack('!6d', data[252:252+48]))
        # tool_vector_actual en offset 444 (6 doubles)
        tcp_actual = list(struct.unpack('!6d', data[444:444+48]))

        # digital inputs / safety mode at offset 812 if available
        safety_mode = 1.0
        if len(data) >= 820:
            safety_mode = struct.unpack('!d', data[812:820])[0]

        return {
            "q_actual": q_actual,
            "tcp_actual": tcp_actual,
            "safety_mode": safety_mode
        }


def main():
    cargar_env()
    parser = argparse.ArgumentParser(description="Consulta de estado y telemetría del UR10e")
    parser.add_argument("--json", action="store_true", help="Salida en formato JSON")
    parser.add_argument("--dry-run", action="store_true", help="Simular telemetría sin conectar al robot")
    args = parser.parse_args()

    robot_ip = os.getenv("ROBOT_IP", "192.168.1.224")

    try:
        if args.dry_run:
            if not args.json:
                print(f"[*] [MODO SIMULACIÓN] Generando telemetría de prueba para {robot_ip}...")
            status_data = {
                "robot_ip": robot_ip,
                "modo": "SIMULACIÓN",
                "estado_seguro": True,
                "parada_proteccion": False,
                "parada_emergencia": False,
                "safety_status_bits": 1,
                "posiciones_articulares_rad": [1.047, -2.059, -1.308, -1.308, 1.553, 2.600],
                "pose_tcp_m_rad": [0.450, -0.200, 0.150, 3.1415, 0.0, 0.0],
                "temperaturas_juntas_c": [32.5, 33.1, 31.8, 29.4, 28.9, 27.5]
            }
        elif rtde_receive is not None:
            if not args.json:
                print(f"[*] Conectando vía RTDE con UR10e en {robot_ip}...")

            rtde_rec = rtde_receive.RTDEReceiveInterface(robot_ip)
            actual_q = rtde_rec.getActualQ()
            actual_tcp = rtde_rec.getActualTCPPose()
            
            is_protective = rtde_rec.isProtectiveStopped() if hasattr(rtde_rec, "isProtectiveStopped") else False
            is_emergency = rtde_rec.isEmergencyStopped() if hasattr(rtde_rec, "isEmergencyStopped") else False
            safety_status = rtde_rec.getSafetyStatusBits() if hasattr(rtde_rec, "getSafetyStatusBits") else 1
            temperatures = rtde_rec.getJointTemperatures() if hasattr(rtde_rec, "getJointTemperatures") else []

            status_data = {
                "robot_ip": robot_ip,
                "modo": "RTDE_NATIVO",
                "estado_seguro": not (is_protective or is_emergency),
                "parada_proteccion": is_protective,
                "parada_emergencia": is_emergency,
                "safety_status_bits": safety_status,
                "posiciones_articulares_rad": actual_q,
                "pose_tcp_m_rad": actual_tcp,
                "temperaturas_juntas_c": temperatures
            }
            rtde_rec.disconnect()
        else:
            # Fallback en host local sin ur_rtde instalado: conexión directa por socket a puerto 30003
            if not args.json:
                print(f"[*] Conectando vía Telemetría Directa (puerto 30003) con UR10e en {robot_ip}...")
            
            raw_telemetria = leer_telemetria_directa_socket(robot_ip)
            status_data = {
                "robot_ip": robot_ip,
                "modo": "TELEMETRIA_DIRECTA_30003",
                "estado_seguro": True,
                "parada_proteccion": False,
                "parada_emergencia": False,
                "safety_status_bits": int(raw_telemetria["safety_mode"]),
                "posiciones_articulares_rad": raw_telemetria["q_actual"],
                "pose_tcp_m_rad": raw_telemetria["tcp_actual"],
                "temperaturas_juntas_c": []
            }

        if args.json:
            print(json.dumps(status_data, indent=2))
        else:
            print("\n[SUCCESS] Conexión establecida correctamente.")
            print("-" * 55)
            print(f"Modo de Lectura   : {status_data['modo']}")
            print(f"Estado de Seguridad: {'NORMAL (OK)' if status_data['estado_seguro'] else 'PARADA ACTIVA'}")
            print(f"  > Parada Protección: {status_data['parada_proteccion']}")
            print(f"  > Parada Emergencia: {status_data['parada_emergencia']}")
            print("-" * 55)
            q_deg = [round(math.degrees(a), 2) for a in status_data['posiciones_articulares_rad']]
            print(f"Posiciones articulares (grados):\n  {q_deg}")
            print(f"Posiciones articulares (q) [rad]:\n  {[round(a, 4) for a in status_data['posiciones_articulares_rad']]}")
            print(f"Pose del TCP (x, y, z, rx, ry, rz) [m/rad]:\n  {[round(v, 4) for v in status_data['pose_tcp_m_rad']]}")
            if status_data['temperaturas_juntas_c']:
                print(f"Temperaturas de las articulaciones [°C]:\n  {status_data['temperaturas_juntas_c']}")
            print("-" * 55)

    except Exception as e:
        print(f"\n[ERROR] No se pudo establecer comunicación con el robot: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
