"""
Módulo de control de comunicación con el perfilómetro Gocator 2600.
Implementa una clase de cliente TCP/IP reutilizable y modo de ejecución CLI
mediante el protocolo de comandos ASCII en el puerto 8190 de GoPxL.
"""

import socket
import time
import os
import sys

# Configuración de red por defecto
DEFAULT_GOCATOR_IP = os.getenv("GOCATOR_IP", "192.168.1.10")
DEFAULT_GOCATOR_PORT = int(os.getenv("GOCATOR_PORT", 8190))


class GocatorClient:
    """Cliente de comunicación para el perfilómetro Gocator mediante comandos ASCII."""

    def __init__(self, ip: str = DEFAULT_GOCATOR_IP, port: int = DEFAULT_GOCATOR_PORT, timeout: float = 3.0):
        self.ip = ip
        self.port = port
        self.timeout = timeout

    def send_command(self, comando: str) -> bool:
        """
        Envía un comando ASCII (finalizado en \\r\\n) al sensor y espera confirmación ('OK' / 'ERROR').
        """
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(self.timeout)
                s.connect((self.ip, self.port))

                mensaje = f"{comando.strip()}\r\n"
                s.sendall(mensaje.encode("ascii"))

                respuesta = s.recv(1024).decode("ascii")
                print(f"[*] Gocator ({self.ip}:{self.port}) [{comando}] -> {respuesta.strip()}")
                return "OK" in respuesta.upper() or len(respuesta.strip()) > 0
        except Exception as e:
            print(f"[!] Error de comunicación con Gocator ({self.ip}:{self.port}) al enviar '{comando}': {e}")
            return False

    def start(self) -> bool:
        """Inicia la adquisición y emisión del láser."""
        return self.send_command("start")

    def stop(self) -> bool:
        """Detiene la adquisición y apaga el láser."""
        return self.send_command("stop")

    def trigger(self) -> bool:
        """Envía señal de disparo por software para iniciar grabación de volumen 3D."""
        return self.send_command("trigger")

    def is_available(self) -> bool:
        """Verifica si el sensor responde al puerto TCP configurado."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1.5)
                s.connect((self.ip, self.port))
                return True
        except Exception:
            return False


# Función retrocompatible para scripts existentes
def enviar_comando_ascii(comando: str, ip: str = DEFAULT_GOCATOR_IP, port: int = DEFAULT_GOCATOR_PORT) -> bool:
    client = GocatorClient(ip=ip, port=port)
    return client.send_command(comando)


if __name__ == "__main__":
    gocator_ip = os.getenv("GOCATOR_IP", DEFAULT_GOCATOR_IP)
    gocator_port = int(os.getenv("GOCATOR_PORT", DEFAULT_GOCATOR_PORT))
    tiempo_barrido = int(os.getenv("SWEEP_TIME", 30))

    client = GocatorClient(ip=gocator_ip, port=gocator_port)
    print(f"[*] Iniciando comunicación con Gocator en {client.ip}:{client.port}...")

    # 1. Iniciar adquisición
    print("[*] Enviando comando: START")
    if not client.start():
        print("[!] No se pudo contactar con el sensor Gocator.")

    # 2. Ventana de tiempo para barrido manual
    print(f"[*] Láser activado. Realizando barrido durante {tiempo_barrido} segundos...")
    try:
        time.sleep(tiempo_barrido)
    except KeyboardInterrupt:
        print("\n[*] Interrupción detectada por usuario.")

    # 3. Detener captura
    print("[*] Enviando comando: STOP")
    client.stop()
    print("[*] Captura finalizada.")