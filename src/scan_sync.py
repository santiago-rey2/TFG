"""
Módulo de escaneo sincronizado para UR10e y Gocator 2600.
Este script coordina el movimiento del robot con la activación del perfilómetro.
"""

import rtde_control
import math
import time
import os
import sys
import socket

# --- Configuración Gocator ---
GOCATOR_IP = os.getenv("GOCATOR_IP", "192.168.1.10")
ASCII_PORT = int(os.getenv("GOCATOR_PORT", 8190))

def enviar_comando_gocator(comando):
    """Envía un comando ASCII al Gocator y espera confirmación."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(5.0)
            s.connect((GOCATOR_IP, ASCII_PORT))
            mensaje = f"{comando}\r\n"
            s.sendall(mensaje.encode('ascii'))
            respuesta = s.recv(1024).decode('ascii')
            print(f"[*] Gocator ({comando}): {respuesta.strip()}")
            return True
    except Exception as e:
        print(f"[!] Error Gocator: {e}")
        return False

# --- Configuración Robot ---
def main():
    robot_ip = os.getenv("ROBOT_IP", "192.168.0.210")
    
    # Coordenadas de Referencia (TFG)
    origin_deg = [-143.03, -62.89, 81.82, -110.44, -92.18, 0.00]
    end_deg = [-57.92, -68.94, 88.45, -113.97, -88.96, 0.03]

    origin_q = [math.radians(d) for d in origin_deg]
    end_q = [math.radians(d) for d in end_deg]

    try:
        print(f"[*] Conectando con robot en {robot_ip}...")
        rtde_ctrl = rtde_control.RTDEControlInterface(robot_ip)
        
        velocity = 0.25
        acceleration = 0.2

        print("[*] Calculando trayectoria...")
        origin_pose = rtde_ctrl.getForwardKinematics(origin_q)
        end_pose = rtde_ctrl.getForwardKinematics(end_q)
        end_pose[2] = origin_pose[2]  # Mantener Z constante

        # 1. Posicionamiento Inicial
        print("\n[1/4] Moviendo a posición de origen...")
        rtde_ctrl.moveL(origin_pose, velocity, acceleration)
        
        # Esperar a que el robot se detenga completamente
        while not rtde_ctrl.isSteady():
            time.sleep(0.1)
        print("[*] Robot en posición y estable.")
        time.sleep(1.0)

        # 2. Iniciar Escaneo
        print("\n[2/4] Activando sensor Gocator...")
        if not enviar_comando_gocator("start"):
            raise Exception("No se pudo iniciar el escaneo en el Gocator.")
        
        # En modo Surface con generación 'Software', se requiere el comando trigger
        # para empezar a grabar el volumen 3D.
        print("[*] Enviando señal de disparo (TRIGGER)...")
        enviar_comando_gocator("trigger")

        # 3. Ejecutar Barrido
        print("\n[3/4] Ejecutando barrido de escaneo...")
        # Usamos moveL asíncrono si fuera necesario, pero aquí el bloqueo es útil 
        # para saber cuándo detener el sensor.
        rtde_ctrl.moveL(end_pose, velocity, acceleration)
        
        # 4. Detener Escaneo
        print("\n[4/4] Finalizando captura...")
        enviar_comando_gocator("stop")

        print("\n[SUCCESS] Operación de escaneo sincronizado completada.")

    except Exception as e:
        print(f"\n[ERROR] Fallo en la sincronización: {e}")
        # Intentar detener el sensor por seguridad en caso de error
        enviar_comando_gocator("stop")
        sys.exit(1)

    finally:
        if 'rtde_ctrl' in locals():
            rtde_ctrl.stopScript()
            print("[*] Interfaz de control liberada.")

if __name__ == "__main__":
    main()
