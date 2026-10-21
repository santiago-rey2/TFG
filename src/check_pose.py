"""
Módulo para consultar y comprobar la pose TCP actual del robot UR10e.
Compatible con ur_rtde (puerto 30004) y lectura directa por socket (puerto 30003).
"""

import socket
import struct

try:
    from rtde_receive import RTDEReceiveInterface as RTDEReceive
except ImportError:
    RTDEReceive = None


def comprobar_punto_actual(robot_ip, timeout=2.0):
    """Consulta y muestra por consola la pose actual del TCP del robot."""
    print(f"\n[*] Consultando pose actual del robot en {robot_ip}...")
    tcp = None

    # Intento 1: ur_rtde si está instalado en el entorno
    if RTDEReceive is not None:
        try:
            rtde = RTDEReceive(robot_ip)
            if rtde.isConnected():
                tcp = rtde.getActualTCPPose()
                rtde.disconnect()
        except Exception:
            pass

    # Intento 2: Socket directo puerto 30003 (fallback universal sin librerías C++)
    if tcp is None:
        try:
            with socket.create_connection((robot_ip, 30003), timeout=timeout) as s:
                data = b""
                while len(data) < 492:
                    chunk = s.recv(492 - len(data))
                    if not chunk:
                        break
                    data += chunk
                if len(data) >= 492:
                    tcp = list(struct.unpack("!6d", data[444:492]))
        except Exception as e:
            print(f"[ERROR] No se pudo obtener la pose del robot: {e}")
            return None

    if tcp:
        print("[OK] Pose TCP actual recibida:")
        print(f"  Vector: {[round(v, 6) for v in tcp]}")
        print(f"  X : {tcp[0]:.6f} m")
        print(f"  Y : {tcp[1]:.6f} m")
        print(f"  Z : {tcp[2]:.6f} m")
        print(f"  Rx: {tcp[3]:.4f} rad")
        print(f"  Ry: {tcp[4]:.4f} rad")
        print(f"  Rz: {tcp[5]:.4f} rad")
        return tcp

    print("[ERROR] No se recibió respuesta del robot.")
    return None
