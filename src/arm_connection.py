"""
Módulo de conexión y movimiento del brazo robótico UR10e mediante ur_rtde (RTDEControl, puerto 30004).
Centraliza:
  - La comprobación de disponibilidad de la librería y la apertura/liberación de la conexión.
  - El movimiento lineal (moveL) con parada de emergencia en tiempo real ([ENTER] / [ESPACIO]).
"""

import time
import threading
from contextlib import contextmanager

try:
    from rtde_control import RTDEControlInterface as RTDEControl
except ImportError:
    RTDEControl = None

from keyboard_listener import escuchar_parada, limpiar_buffer_teclado

# Parámetros del bucle de movimiento
MARGEN_INICIO_MOVIMIENTO_S = 0.15  # Margen para que el controlador inicie la interpolación
PERIODO_MONITORIZACION_S = 0.04    # Periodo de comprobación de llegada / parada
DECELERACION_PARADA = 10.0         # Deceleración de frenado de emergencia (m/s^2)


@contextmanager
def conexion_control(arm_ip):
    """
    Abre una conexión RTDEControl con el brazo UR10e y la libera siempre al salir del bloque 'with'.

    Uso:
        with conexion_control(arm_ip) as rtde_ctrl:
            rtde_ctrl.moveL(...)

    :param arm_ip: Dirección IP del controlador del brazo UR10e.
    :raises RuntimeError: Si la librería ur_rtde no está instalada en el entorno.
    """
    if RTDEControl is None:
        raise RuntimeError("La librería 'ur_rtde' no está disponible en este entorno.")

    print(f"[*] Conectando con UR10e en {arm_ip}...")
    rtde_ctrl = RTDEControl(arm_ip)
    try:
        yield rtde_ctrl
    finally:
        try:
            rtde_ctrl.stopScript()
        except Exception:
            pass
        print("[*] Conexión liberada.")


def mover_lineal_con_parada(rtde_ctrl, pose_destino, speed, acceleration, al_monitorizar=None):
    """
    Ejecuta un moveL asíncrono hacia pose_destino y lo monitoriza hasta que el brazo llega
    o el usuario pulsa [ENTER] / [ESPACIO] (frenado inmediato con stopL).
    El detector de teclado solo está activo durante el movimiento.

    :param rtde_ctrl: Interfaz RTDEControl ya conectada (ver conexion_control).
    :param pose_destino: Pose TCP objetivo [X, Y, Z, Rx, Ry, Rz].
    :param speed: Velocidad lineal en m/s.
    :param acceleration: Aceleración lineal en m/s^2.
    :param al_monitorizar: Función opcional sin argumentos llamada en cada ciclo (p. ej. mostrar progreso).
    :return: True si el movimiento fue detenido manualmente, False si se completó.
    """
    # Iniciar detector de pulsación en hilo paralelo
    stop_requested = threading.Event()
    listener = threading.Thread(target=escuchar_parada, args=(stop_requested,), daemon=True)
    listener.start()

    try:
        # Iniciar movimiento lineal en modo asíncrono
        rtde_ctrl.moveL(pose_destino, speed, acceleration, True)
        time.sleep(MARGEN_INICIO_MOVIMIENTO_S)

        # Monitorear hasta que el robot llegue o se solicite la parada
        while not rtde_ctrl.isSteady():
            if stop_requested.is_set():
                print("\n\n[PARADA DE EMERGENCIA] ¡Pulsación detectada! Frenando el robot...")
                rtde_ctrl.stopL(DECELERACION_PARADA)  # Frenado inmediato
                return True
            if al_monitorizar is not None:
                al_monitorizar()
            time.sleep(PERIODO_MONITORIZACION_S)
        return False
    finally:
        # Detener el detector y restaurar el terminal antes de cualquier input() posterior
        stop_requested.set()
        listener.join(timeout=0.5)
        limpiar_buffer_teclado()
