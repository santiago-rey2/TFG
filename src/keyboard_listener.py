"""
Módulo de captura de teclado multiplataforma.
Permite detectar pulsaciones de parada de emergencia ([ENTER] o [ESPACIO])
durante la ejecución de movimientos en Windows y Linux/Docker (TTY).
"""

import sys
import time


def escuchar_parada(stop_requested):
    """
    Monitorea de forma no bloqueante si el usuario pulsa [ENTER] o [ESPACIO]
    para solicitar una parada de emergencia inmediata.
    """
    # 1. Plataforma Windows (msvcrt)
    try:
        import msvcrt
        while not stop_requested.is_set():
            if msvcrt.kbhit():
                ch = msvcrt.getch()
                if ch in (b'\r', b'\n', b' '):
                    stop_requested.set()
                    return
            time.sleep(0.02)
        return
    except ImportError:
        pass

    # 2. Linux / Docker con TTY interactivo (termios + select)
    try:
        import select
        import termios
        import tty

        if sys.stdin.isatty():
            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
            try:
                tty.setcbreak(fd)
                while not stop_requested.is_set():
                    rlist, _, _ = select.select([sys.stdin], [], [], 0.05)
                    if rlist:
                        ch = sys.stdin.read(1)
                        if ch in ('\r', '\n', ' '):
                            stop_requested.set()
                            return
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            return
    except Exception:
        pass

    # 3. Fallback genérico para entornos sin terminal directa
    try:
        while not stop_requested.is_set():
            linea = sys.stdin.readline()
            if linea:
                stop_requested.set()
                return
    except Exception:
        pass


def limpiar_buffer_teclado():
    """Descarta cualquier pulsación de tecla residual pendiente en el buffer."""
    try:
        import msvcrt
        while msvcrt.kbhit():
            msvcrt.getch()
    except ImportError:
        try:
            import select
            while select.select([sys.stdin], [], [], 0)[0]:
                sys.stdin.read(1)
        except Exception:
            pass
