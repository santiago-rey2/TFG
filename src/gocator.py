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
    tiempo_barrido = int(os.getenv("SWEEP_TIME", 10))
    print(f"[*] Láser activado. Realizando barrido durante {tiempo_barrido} segundos...")
    time.sleep(tiempo_barrido)

    # 3. Detener la captura
    print("[*] Enviando comando: STOP")
    enviar_comando_ascii("stop")
    print("[*] Captura finalizada.")