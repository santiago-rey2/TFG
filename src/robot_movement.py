import rtde_control
import math
import time

# IP del robot
robot_ip = "192.168.1.224"

# Coordenadas de ORIGEN (convertidas de grados a radianes)
origin_q = [math.radians(d) for d in [-143.03, -62.89, 81.82, -110.44, -92.18, 0.00]]

# Coordenadas de FIN (convertidas de grados a radianes)
end_q = [math.radians(d) for d in [-57.92, -68.94, 88.45, -113.97, -88.96, 0.03]]

try:
    print(f"Conectando con el robot en {robot_ip}...")
    rtde_ctrl = rtde_control.RTDEControlInterface(robot_ip)

    # Parámetros de movimiento
    speed = 0.25
    acceleration = 0.2

    # Calculamos las poses (TCP) correspondientes a los ángulos articulares
    print("Calculando cinemática directa para las poses...")
    origin_pose = rtde_ctrl.getForwardKinematics(origin_q)
    end_pose = rtde_ctrl.getForwardKinematics(end_q)

    # AJUSTE PARA MOVIMIENTO PLANO: Forzamos la Z del final para que sea igual a la del origen
    print(f"Z original: {origin_pose[2]:.4f}m, Z final detectada: {end_pose[2]:.4f}m")
    end_pose[2] = origin_pose[2] 
    print(f"Ajustando Z final a {end_pose[2]:.4f}m para asegurar trayectoria plana.")

    # 1. Movimiento LINEAL al origen
    print(f"Moviendo linealmente (moveL) a la posición de ORIGEN...")
    rtde_ctrl.moveL(origin_pose, speed, acceleration)
    print("Posición de origen alcanzada.")

    time.sleep(1) # Pausa de seguridad

    # 2. Movimiento LINEAL al fin
    print(f"Moviendo linealmente (moveL) a la posición de FIN...")
    rtde_ctrl.moveL(end_pose, speed, acceleration)
    print("Posición final alcanzada.")

    print("\n¡Trayectoria lineal completada con éxito!")

except Exception as e:
    print(f"Ocurrió un error durante el movimiento: {e}")

finally:
    if 'rtde_ctrl' in locals():
        rtde_ctrl.stopScript()
        print("Conexión cerrada.")
