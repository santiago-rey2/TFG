"""
Script de diagnóstico y verificación de conectividad con el robot Universal Robots UR10e (o URSim).
Verifica los puertos esenciales de comunicación y extrae telemetría directa:
  - Puerto 29999: Dashboard Server (estado Polyscope, modo remoto, seguridad)
  - Puerto 30003: Real-Time Client Interface (lectura directa 500 Hz de articulaciones y pose TCP)
  - Puerto 30004: RTDE (Real-Time Data Exchange)
  - Puerto 6080 : Interfaz Web noVNC / Teach Pendant Virtual
"""

import socket
import struct
import math
import os
import sys
import argparse


def verificar_puerto(ip: str, port: int, timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except Exception:
        return False


def test_dashboard(ip: str) -> dict:
    info = {"disponible": False, "version": None, "robot_mode": None, "safety": None, "remote": None, "program": None}
    try:
        with socket.create_connection((ip, 29999), timeout=3.0) as s:
            info["disponible"] = True
            banner = s.recv(1024).decode('utf-8', errors='ignore').strip()
            
            cmds = {
                "version": "PolyscopeVersion\n",
                "robot_mode": "robotmode\n",
                "safety": "safetystatus\n",
                "remote": "is in remote control\n",
                "program": "programState\n"
            }
            for k, cmd in cmds.items():
                s.sendall(cmd.encode('utf-8'))
                resp = s.recv(1024).decode('utf-8', errors='ignore').strip()
                info[k] = resp
    except Exception as e:
        info["error"] = str(e)
    return info


def test_telemetria_30003(ip: str) -> dict:
    telemetria = {"disponible": False, "joints_deg": None, "tcp_pose": None}
    try:
        with socket.create_connection((ip, 30003), timeout=3.0) as s:
            data = b''
            while len(data) < 4:
                chunk = s.recv(4 - len(data))
                if not chunk:
                    break
                data += chunk
            if len(data) < 4:
                return telemetria

            pkg_len = struct.unpack('!i', data[:4])[0]
            while len(data) < pkg_len:
                chunk = s.recv(pkg_len - len(data))
                if not chunk:
                    break
                data += chunk

            if len(data) >= 492:
                # q_actual en offset 252 (6 doubles)
                q_actual = struct.unpack('!6d', data[252:252+48])
                q_deg = [round(math.degrees(a), 2) for a in q_actual]
                
                # tool_vector_actual en offset 444 (6 doubles)
                tcp_actual = struct.unpack('!6d', data[444:444+48])
                tcp_rounded = [round(v, 4) for v in tcp_actual]
                
                telemetria["disponible"] = True
                telemetria["joints_deg"] = q_deg
                telemetria["tcp_pose"] = tcp_rounded
    except Exception as e:
        telemetria["error"] = str(e)
    return telemetria


def main():
    parser = argparse.ArgumentParser(description="Verificación de conectividad con robot UR10e / URSim")
    parser.add_argument("--ip", type=str, default=os.getenv("ROBOT_IP", "192.168.1.224"), help="IP del robot o simulador")
    args = parser.parse_args()

    ip = args.ip

    print("\n" + "=" * 70)
    print(f" DIAGNÓSTICO DE COMUNICACIÓN CON ROBOT UR10e (@ {ip})")
    print("=" * 70)

    # 1. Dashboard Server
    print("\n[1/4] Dashboard Server (Puerto 29999):")
    dash = test_dashboard(ip)
    if dash["disponible"]:
        print(f"  [OK] Conexión establecida.")
        print(f"       - Versión Polyscope     : {dash['version']}")
        print(f"       - Estado del Robot       : {dash['robot_mode']}")
        print(f"       - Estado de Seguridad    : {dash['safety']}")
        print(f"       - Modo Remoto (Pendant)  : {dash['remote']}")
        print(f"       - Estado de Programa     : {dash['program']}")
    else:
        print(f"  [ERROR] No responde ({dash.get('error', 'Timeout')})")

    # 2. Telemetría Real-time
    print("\n[2/4] Telemetría en Tiempo Real (Puerto 30003 / 500 Hz):")
    tel = test_telemetria_30003(ip)
    if tel["disponible"]:
        names = ["Base", "Shoulder", "Elbow", "Wrist 1", "Wrist 2", "Wrist 3"]
        print(f"  [OK] Paquete de telemetría recibido y procesado.")
        print("  Posiciones articulares actuales:")
        for n, deg in zip(names, tel["joints_deg"]):
            print(f"       - {n:9s}: {deg:8.2f}°")
        print(f"  Pose TCP cartesiana actual:")
        p = tel["tcp_pose"]
        print(f"       - Posición [X, Y, Z]    : [{p[0]:.4f}, {p[1]:.4f}, {p[2]:.4f}] m")
        print(f"       - Orientación [Rx,Ry,Rz]: [{p[3]:.4f}, {p[4]:.4f}, {p[5]:.4f}] rad")
    else:
        print(f"  [ERROR] No responde ({tel.get('error', 'Timeout')})")

    # 3. RTDE Control Interface
    print("\n[3/4] Interfaz RTDE (Puerto 30004):")
    rtde_ok = verificar_puerto(ip, 30004)
    if rtde_ok:
        print("  [OK] Puerto RTDE (30004) ABIERTO y listo para negociación.")
    else:
        print("  [ERROR] Puerto RTDE (30004) CERRADO o no accesible.")

    # 4. Web Interface
    print("\n[4/4] Interfaz Web del Pendant noVNC (Puerto 6080):")
    web_ok = verificar_puerto(ip, 6080)
    if web_ok:
        print("  [OK] Interfaz Web (6080) DISPONIBLE -> http://{}:6080".format(ip))
    else:
        print("  [INFO] Puerto 6080 no responde (normal si no se utiliza noVNC).")

    print("\n" + "=" * 70)
    resumen = "100% OPERATIVO" if dash["disponible"] and tel["disponible"] and rtde_ok else "CONEXIÓN PARCIAL / ERRORES"
    print(f" RESULTADO GLOBAL: {resumen}")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
