"""
Módulo de gestión de configuraciones de movimiento.
Carga y valida los perfiles de dinámica (velocidad y aceleración) desde config/movement_config.json.
"""

import os
import json

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(BASE_DIR, "config", "movement_config.json")


def cargar_config_movimiento():
    """Carga los setups de velocidad y aceleración desde config/movement_config.json."""
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[!] Error al leer {CONFIG_PATH}: {e}")

    # Configuración por defecto de respaldo
    return {
        "setups": {
            "movement": {"description": "Standard", "speed": 0.05, "acceleration": 0.2},
            "scan": {"description": "Scan", "speed": 0.008, "acceleration": 0.1}
        },
        "default_setup": "movement"
    }


def seleccionar_setup(config):
    """Permite seleccionar de forma interactiva el perfil de velocidad/aceleración."""
    setups = config.get("setups", {})
    defecto = config.get("default_setup", "movement")

    print("\n--- Setups de Movimiento ---")
    claves = list(setups.keys())
    for i, c in enumerate(claves, start=1):
        s = setups[c]
        marca = " (defecto)" if c == defecto else ""
        print(f"  [{i}] {c}{marca}: speed = {s['speed']} m/s, accel = {s['acceleration']} m/s^2")

    eleccion = input(f"Selecciona setup [1-{len(claves)}] (Enter para '{defecto}'): ").strip()
    sel = defecto
    if eleccion:
        try:
            idx = int(eleccion) - 1
            if 0 <= idx < len(claves):
                sel = claves[idx]
        except ValueError:
            pass

    elegido = setups.get(sel, setups.get(defecto, {}))
    return {
        "name": sel,
        "speed": elegido.get("speed", 0.05),
        "acceleration": elegido.get("acceleration", 0.2)
    }
