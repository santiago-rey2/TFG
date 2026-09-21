import socket
import time
import os

# Configuración de red del Gocator (IP por defecto de fábrica o desde .env)
GOCATOR_IP = os.getenv("GOCATOR_IP", "192.168.1.10")
ASCII_PORT = int(os.getenv("GOCATOR_PORT", 8190))

def enviar_comando_ascii(comando):
    try:
        # Crear conexión TCP/IP
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(5.0)
        s.connect((GOCATOR_IP, ASCII_PORT))

        # El protocolo ASCII de GoPxL requiere salto de línea al final (\r\n)
        mensaje = f"{comando}\r\n"
        s.sendall(mensaje.encode('ascii'))

        # Leer la respuesta de confirmación ("OK" o "ERROR")
        respuesta = s.recv(1024).decode('ascii')
        print(f"[*] Comando '{comando}' enviado a {GOCATOR_IP} -> Respuesta: {respuesta.strip()}")

        s.close()
    except Exception as e:
        print(f"[!] Error de comunicación con el sensor ({GOCATOR_IP}:{ASCII_PORT}): {e}")

if __name__ == "__main__":
    print(f"[*] Iniciando comunicación con Gocator en {GOCATOR_IP}:{ASCII_PORT}...")

    # 1. Asegúrate de tener el Gocator configurado en GoPxL en modo "Surface"
    print("[*] Enviando comando: START")
    enviar_comando_ascii("start")

    # 2. Ventana de tiempo para el barrido
    tiempo_barrido = int(os.getenv("SWEEP_TIME", 30))
    print(f"[*] Láser activado. Realizando barrido durante {tiempo_barrido} segundos...")
    time.sleep(tiempo_barrido)

    # 3. Detener la captura
    print("[*] Enviando comando: STOP")
    enviar_comando_ascii("stop")
    print("[*] Captura finalizada.")



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
    robot_ip = os.getenv("ROBOT_IP", "192.168.0.210")

    # Definición de coordenadas objetivo (Grados)
    # Origen: Posición de inicio del escaneo
    origin_deg = [60, -118, -75, -75, 89, 149]
    end_deg = [132, -108, -87, -72, 90, 220]

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
        sudo apt install remmina remmina-plugin-vnc
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
    origin_deg = [60, -118, -75, -75, 89, 149]
    end_deg = [132, -108, -87, -72, 90, 220]

    origin_q = [math.radians(d) for d in origin_deg]
    end_q = [math.radians(d) for d in end_deg]

    try:
        print(f"[*] Conectando con robot en {robot_ip}...")
        rtde_ctrl = rtde_control.RTDEControlInterface(robot_ip)
        
        velocity = 0.1
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

