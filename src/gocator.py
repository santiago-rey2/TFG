"""
Módulo de control de comunicación con el perfilómetro Gocator 2600.
Implementa una clase de cliente TCP/IP reutilizable y dos modos de ejecución:
  - Comandos directos por CLI (--cmd start|stop|trigger, --sweep <seg>, --status)
  - Consola interactiva por consola (-i / --interactivo)

Opera de forma 100% independiente del brazo robótico mediante el protocolo
de comandos ASCII en el puerto 8190 de GoPxL.
"""

import socket
import time
import os
import sys
import argparse
from typing import Optional, Dict, Any

# Configuración de red por defecto (TFG: Red 192.168.0.x según Doc-Dia-6)
DEFAULT_GOCATOR_IP = os.getenv("GOCATOR_IP", "192.168.0.10")
DEFAULT_GOCATOR_PORT = int(os.getenv("GOCATOR_PORT", 8190))


class GocatorClient:
    """Cliente de comunicación para el perfilómetro Gocator mediante comandos ASCII."""

    def __init__(self, ip: str = DEFAULT_GOCATOR_IP, port: int = DEFAULT_GOCATOR_PORT, timeout: float = 3.0):
        self.ip = ip
        self.port = port
        self.timeout = timeout
        self.is_running = False

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
                resp_clean = respuesta.strip()
                print(f"[*] Gocator ({self.ip}:{self.port}) [{comando}] -> {resp_clean}")
                ok = "OK" in resp_clean.upper() or len(resp_clean) > 0
                if comando.strip().lower() == "start" and ok:
                    self.is_running = True
                elif comando.strip().lower() == "stop" and ok:
                    self.is_running = False
                return ok
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

    def get_status(self) -> Dict[str, Any]:
        """Comprueba conectividad, mide latencia y retorna resumen de estado."""
        inicio = time.time()
        disponible = False
        latencia_ms = -1.0
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(2.0)
                s.connect((self.ip, self.port))
                latencia_ms = (time.time() - inicio) * 1000.0
                disponible = True
        except Exception:
            disponible = False

        return {
            "ip": self.ip,
            "port": self.port,
            "disponible": disponible,
            "latencia_ms": round(latencia_ms, 2) if disponible else None,
            "emitiendo_laser": self.is_running
        }

    def sweep(self, duration_seconds: float = 30.0):
        """
        Ejecuta una ventana temporal de barrido (START -> Espera con cuenta atrás -> STOP).
        Garantiza que el láser se apague incluso ante interrupción con Ctrl+C.
        """
        print(f"\n[*] Iniciando barrido temporizado de {duration_seconds} segundos...")
        if not self.start():
            print("[!] Advertencia: No se pudo confirmar comando START en el sensor.")

        inicio = time.time()
        try:
            while True:
                transcurrido = time.time() - inicio
                restante = duration_seconds - transcurrido
                if restante <= 0:
                    break
                print(f"\r  [LÁSER ACTIVO] Tiempo restante: {restante:5.1f}s / {duration_seconds:.1f}s (Ctrl+C para detener)", end="", flush=True)
                time.sleep(0.2)
            print("\n[*] Ventana de tiempo completada.")
        except KeyboardInterrupt:
            print("\n[*] Interrupción detectada por el usuario (Ctrl+C).")
        finally:
            print("[*] Apagando láser...")
            self.stop()
            print("[OK] Sensor detenido y láser apagado.")


def enviar_comando_ascii(comando: str, ip: str = DEFAULT_GOCATOR_IP, port: int = DEFAULT_GOCATOR_PORT) -> bool:
    """Función de conveniencia retrocompatible para scripts existentes."""
    client = GocatorClient(ip=ip, port=port)
    return client.send_command(comando)


def consola_interactiva_gocator(client: GocatorClient):
    """Consola interactiva REPL para control directo del perfilómetro Gocator 2600."""
    print("\n" + "=" * 70)
    print(" INICIALIZANDO CONSOLA DE ACTUACIÓN LÁSER GOCATOR 2600 (TFG)")
    print("=" * 70)

    try:
        while True:
            st = client.get_status()
            estado_str = f"ONLINE ({st['latencia_ms']} ms)" if st["disponible"] else "DESCONECTADO / TIMEOUT"
            laser_str = "EMITIENDO" if client.is_running else "APAGADO"

            print("\n" + "=" * 70)
            print(" CONSOLA DE CONTROL - PERFILÓMETRO LÁSER GOCATOR 2600")
            print("=" * 70)
            print(f" [Sensor IP]  : {client.ip}:{client.port} | Conexión: {estado_str}")
            print(f" [Estado]     : Láser {laser_str}")
            print("-" * 70)
            print("  [1] START   - Encender láser y comenzar adquisición continua")
            print("  [2] STOP    - Apagar láser y detener adquisición")
            print("  [3] TRIGGER - Disparo por software (Surface Trigger)")
            print("  [4] SWEEP   - Barrido temporizado (ingresar segundos, ej: 15s)")
            print("  [5] STATUS  - Comprobar conectividad y latencia con el sensor")
            print("  [6] CAMBIAR IP / PUERTO DEL SENSOR")
            print("  [0] Salir   - Asegurar láser apagado y salir")
            print("=" * 70)

            try:
                opcion = input("Gocator> ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\n[*] Saliendo de la consola...")
                break

            if opcion == "1":
                print("[*] Enviando START...")
                client.start()
            elif opcion == "2":
                print("[*] Enviando STOP...")
                client.stop()
            elif opcion == "3":
                print("[*] Enviando TRIGGER...")
                client.trigger()
            elif opcion == "4":
                try:
                    seg_str = input("Duración del barrido en segundos [por defecto 15]: ").strip()
                    duracion = float(seg_str) if seg_str else 15.0
                    client.sweep(duracion)
                except ValueError:
                    print("[!] Valor numérico inválido.")
            elif opcion == "5":
                st = client.get_status()
                print("\n--- DIAGNÓSTICO DE RED GOCATOR ---")
                print(f"  Dirección IP : {st['ip']}")
                print(f"  Puerto ASCII : {st['port']}")
                print(f"  Disponible   : {'SÍ' if st['disponible'] else 'NO (Verificar cable o IP)'}")
                if st['disponible']:
                    print(f"  Latencia     : {st['latencia_ms']} ms")
            elif opcion == "6":
                nueva_ip = input(f"Nueva dirección IP [{client.ip}]: ").strip()
                nuevo_puerto = input(f"Nuevo puerto [{client.port}]: ").strip()
                if nueva_ip:
                    client.ip = nueva_ip
                if nuevo_puerto and nuevo_puerto.isdigit():
                    client.port = int(nuevo_puerto)
                print(f"[OK] Parámetros actualizados a {client.ip}:{client.port}")
            elif opcion == "0":
                print("[*] Finalizando...")
                break
            else:
                print("[!] Opción no reconocida. Seleccione entre 0 y 6.")

    finally:
        if client.is_running:
            print("[*] Apagando láser preventivamente antes de salir...")
            client.stop()
        print("[*] Sesión con Gocator cerrada.")


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Control de actuación independiente para perfilómetro Gocator 2600"
    )
    parser.add_argument("--ip", type=str, default=DEFAULT_GOCATOR_IP, help=f"IP del Gocator (defecto: {DEFAULT_GOCATOR_IP})")
    parser.add_argument("--port", type=int, default=DEFAULT_GOCATOR_PORT, help=f"Puerto ASCII GoPxL (defecto: {DEFAULT_GOCATOR_PORT})")
    parser.add_argument("-i", "--interactivo", action="store_true", help="Iniciar consola interactiva del sensor")
    parser.add_argument("--cmd", choices=["start", "stop", "trigger"], help="Enviar comando único y salir")
    parser.add_argument("--sweep", type=float, nargs="?", const=30.0, help="Realizar barrido por N segundos (defecto: 30s)")
    parser.add_argument("--status", action="store_true", help="Verificar conectividad con el sensor y salir")

    return parser.parse_args()


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


def main():
    cargar_env()
    args = parse_arguments()
    client = GocatorClient(ip=args.ip, port=args.port)

    # 1. Comando directo único
    if args.cmd:
        if args.cmd == "start":
            client.start()
        elif args.cmd == "stop":
            client.stop()
        elif args.cmd == "trigger":
            client.trigger()
        return

    # 2. Comprobación de estado
    if args.status:
        st = client.get_status()
        print(f"Gocator {st['ip']}:{st['port']} -> Disponible: {st['disponible']} | Latencia: {st['latencia_ms']} ms")
        return

    # 3. Barrido temporizado CLI
    if args.sweep is not None:
        client.sweep(args.sweep)
        return

    # 4. Modo interactivo o fallback automático
    iniciar_consola = args.interactivo or (len(sys.argv) == 1 and sys.stdin.isatty())

    if iniciar_consola:
        consola_interactiva_gocator(client)
    else:
        # Fallback para contenedores automáticos o batch sin argumentos
        tiempo_barrido = int(os.getenv("SWEEP_TIME", 30))
        client.sweep(tiempo_barrido)


if __name__ == "__main__":
    main()