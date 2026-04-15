import rtde_receive

robot_ip = "192.168.1.224"

try:
    print(f"Conectando a {robot_ip} para leer el estado...")
    rtde_rec = rtde_receive.RTDEReceiveInterface(robot_ip)
    
    actual_q = rtde_rec.getActualQ()
    actual_tcp = rtde_rec.getActualTCPPose()
    
    print("¡El robot está vivo!")
    print(f"Posiciones articulares (q): {actual_q}")
    print(f"Pose del TCP (x, y, z, rx, ry, rz): {actual_tcp}")

except Exception as e:
    print(f"Error al conectar con el robot: {e}")
