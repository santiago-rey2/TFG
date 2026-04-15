import rtde_control
import rtde_receive

# La IP de tu simulador UR
robot_ip = "192.168.1.224"

try:
    # 1. Obtener un "I'm alive" leyendo datos del robot
    print(f"Conectando a {robot_ip} para leer el estado...")
    rtde_rec = rtde_receive.RTDEReceiveInterface(robot_ip)
    
    # Leemos la posición actual de las articulaciones (Joints)
    actual_q = rtde_rec.getActualQ()
    print(f"¡El robot está vivo! Posiciones articulares actuales (en radianes): {actual_q}")

    # 2. Intentar mandar una señal de movimiento
    print("Iniciando la interfaz de control...")
    rtde_ctrl = rtde_control.RTDEControlInterface(robot_ip)

    # Copiamos la posición actual y le sumamos un pequeño desplazamiento a la articulación 0 (Base)
    target_q = actual_q[:]
    target_q[0] += 0.1 
    
    # Parámetros de velocidad y aceleración
    speed = 0.5
    acceleration = 0.3

    print("Ejecutando movimiento articular (moveJ)...")
    # moveJ toma la lista de las 6 articulaciones, la velocidad y la aceleración
    rtde_ctrl.moveJ(target_q, speed, acceleration)
    
    print("¡Movimiento de prueba completado con éxito!")

except Exception as e:
    print(f"Ocurrió un error en la conexión o en el movimiento: {e}")

finally:
    # Es una buena práctica detener el script de control al finalizar
    if 'rtde_ctrl' in locals():
        rtde_ctrl.stopScript()