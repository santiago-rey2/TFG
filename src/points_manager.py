"""
Módulo de gestión de puntos y archivos de posiciones.
Lectura, escritura, serialización compacta y selección de archivos de puntos (.json).
"""

import os
import sys
import json
import re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Re-exportación para retrocompatibilidad
from config_manager import cargar_config_movimiento, seleccionar_setup  # noqa: F401

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POINTS_DIR = os.path.join(BASE_DIR, "points")
DEFAULT_POINTS_PATH = os.path.join(POINTS_DIR, "points.json")
POINTS_PATH = DEFAULT_POINTS_PATH


def get_puntos_path():
    """Devuelve la ruta absoluta al archivo de puntos activo."""
    global POINTS_PATH
    return POINTS_PATH


def get_nombre_archivo_puntos():
    """Devuelve el nombre relativo del archivo de puntos activo."""
    try:
        return os.path.relpath(get_puntos_path(), BASE_DIR)
    except Exception:
        return os.path.basename(get_puntos_path())


def serializar_puntos_compacto(puntos):
    """
    Serializa el diccionario de puntos a JSON manteniendo cada vector 'pose'
    en una sola línea. Reduce drásticamente el tamaño del archivo y mejora la legibilidad.
    """
    lineas = ["{", '  "points": {']
    claves = list(puntos.keys())
    for i, clave in enumerate(claves):
        datos = puntos[clave]
        coma = "," if i < len(claves) - 1 else ""
        desc_json = json.dumps(datos.get("description", ""), ensure_ascii=False)
        pose_json = json.dumps(datos.get("pose", []), ensure_ascii=False)
        lineas.append(f'    "{clave}": {{')
        lineas.append(f'      "description": {desc_json},')
        lineas.append(f'      "pose": {pose_json}')
        lineas.append(f'    }}{coma}')
    lineas.append("  }")
    lineas.append("}\n")
    return "\n".join(lineas)


def guardar_puntos_en_disco(puntos, ruta_archivo):
    """Guarda el diccionario de puntos en disco aplicando serialización optimizada."""
    os.makedirs(os.path.dirname(ruta_archivo), exist_ok=True)
    contenido = serializar_puntos_compacto(puntos)
    with open(ruta_archivo, "w", encoding="utf-8") as f:
        f.write(contenido)


def set_puntos_path(ruta):
    """
    Establece un nuevo archivo de puntos activo.
    Resuelve rutas relativas a points/ o al workspace, asegura .json y crea estructura base si no existe.
    """
    global POINTS_PATH
    if not ruta or not str(ruta).strip():
        POINTS_PATH = DEFAULT_POINTS_PATH
        return POINTS_PATH

    ruta_limpia = str(ruta).strip().strip("'\"")
    if not ruta_limpia.lower().endswith(".json"):
        ruta_limpia += ".json"

    if os.path.isabs(ruta_limpia):
        destino = os.path.normpath(ruta_limpia)
    else:
        en_base = os.path.normpath(os.path.join(BASE_DIR, ruta_limpia))
        en_points = os.path.normpath(os.path.join(POINTS_DIR, os.path.basename(ruta_limpia)))

        if os.path.exists(en_base):
            destino = en_base
        elif os.path.exists(en_points):
            destino = en_points
        else:
            destino = en_base if os.path.dirname(ruta_limpia) else en_points

    if not os.path.exists(destino):
        try:
            guardar_puntos_en_disco({}, destino)
            print(f"[*] Creado nuevo archivo de puntos en: {destino}")
        except Exception as e:
            print(f"[!] Error al crear nuevo archivo de puntos en {destino}: {e}")
            return POINTS_PATH

    POINTS_PATH = destino
    rel = get_nombre_archivo_puntos()
    puntos = leer_puntos(POINTS_PATH)
    print(f"[OK] Archivo activo: {rel} ({len(puntos)} puntos disponibles)")
    return POINTS_PATH


def seleccionar_archivo_puntos_interactivo():
    """Menú interactivo para listar y seleccionar archivos de puntos disponibles."""
    os.makedirs(POINTS_DIR, exist_ok=True)
    archivos = sorted([f for f in os.listdir(POINTS_DIR) if f.lower().endswith(".json")])
    actual = get_puntos_path()

    print("\n" + "=" * 55)
    print("      SELECCIÓN DE ARCHIVO DE PUNTOS / POSICIONES")
    print(f"  Activo actualmente: {get_nombre_archivo_puntos()}")
    print("=" * 55)

    if archivos:
        print("\nArchivos disponibles en 'points/':")
        for i, arc in enumerate(archivos, start=1):
            ruta_arc = os.path.normpath(os.path.join(POINTS_DIR, arc))
            marca = "  <-- ACTIVO" if ruta_arc == os.path.normpath(actual) else ""
            print(f"  [{i}] {arc}{marca}")

    idx_otro = len(archivos) + 1
    print(f"  [{idx_otro}] Introducir nuevo nombre o ruta de archivo personalizada")
    print("  [c] Cancelar")
    print("-" * 55)

    eleccion = input(f"Selecciona una opción [1-{idx_otro}] (o 'c' para cancelar): ").strip()
    if eleccion.lower() in ("c", "cancelar", "q", "exit", ""):
        print("[*] Se mantiene el archivo activo actual.")
        return get_puntos_path()

    if eleccion.isdigit():
        idx = int(eleccion) - 1
        if 0 <= idx < len(archivos):
            return set_puntos_path(os.path.join(POINTS_DIR, archivos[idx]))
        elif idx == len(archivos):
            nueva_ruta = input("\nIntroduce nombre o ruta del archivo .json: ").strip()
            if nueva_ruta:
                return set_puntos_path(nueva_ruta)
        print("[!] Opción inválida.")
        return get_puntos_path()

    return set_puntos_path(eleccion)


def leer_puntos(path=None):
    """Lee el diccionario de puntos desde el archivo especificado o el activo."""
    archivo = path if path else get_puntos_path()
    if os.path.exists(archivo):
        try:
            with open(archivo, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("points", {})
        except Exception as e:
            print(f"[!] Error al leer {archivo}: {e}")
    return {}


def listar_puntos(path=None):
    """Muestra por consola la lista de puntos almacenados en el archivo activo y retorna sus nombres."""
    archivo = path if path else get_puntos_path()
    puntos = leer_puntos(archivo)
    rel = get_nombre_archivo_puntos() if not path else os.path.basename(path)
    if not puntos:
        print(f"\n[!] No se encontraron puntos en {rel}.")
        return []

    print(f"\n--- Puntos disponibles en {rel} ---")
    claves = list(puntos.keys())
    for i, nombre in enumerate(claves, start=1):
        info = puntos[nombre]
        desc = f" ({info['description']})" if info.get("description") else ""
        print(f"  [{i}] {nombre}{desc}")
        print(f"      Pose: {info['pose']}")
    return claves


def generar_siguiente_nombre_punto(puntos):
    """Calcula el siguiente identificador incremental 'PointN' evitando colisiones."""
    numeros = []
    for clave in puntos.keys():
        match = re.match(r"^Point(\d+)$", clave, re.IGNORECASE)
        if match:
            numeros.append(int(match.group(1)))

    siguiente_n = max(numeros) + 1 if numeros else 1
    while f"Point{siguiente_n}" in puntos:
        siguiente_n += 1

    return f"Point{siguiente_n}"


def guardar_punto(nombre, pose, descripcion="", path=None):
    """Guarda o actualiza un punto en el archivo activo con formato compacto optimizado."""
    archivo = path if path else get_puntos_path()
    puntos = leer_puntos(archivo)
    if not nombre:
        nombre = generar_siguiente_nombre_punto(puntos)
    puntos[nombre] = {
        "description": descripcion,
        "pose": [round(float(v), 6) for v in pose]
    }
    guardar_puntos_en_disco(puntos, archivo)
    rel = get_nombre_archivo_puntos() if not path else os.path.basename(path)
    print(f"\n[OK] Punto '{nombre}' almacenado exitosamente en {rel}.")
    return nombre


def almacenar_posicion_actual(robot_ip, pose_previa=None, path=None):
    """Obtiene la pose actual del robot y la guarda en el archivo activo."""
    archivo = path if path else get_puntos_path()
    rel = get_nombre_archivo_puntos() if not path else os.path.basename(path)

    if pose_previa is not None:
        pose = pose_previa
    else:
        from check_pose import comprobar_punto_actual
        pose = comprobar_punto_actual(robot_ip)

    if not pose:
        print("[!] No se pudo obtener la pose actual del robot. Operación cancelada.")
        return False

    puntos = leer_puntos(archivo)
    nombre_por_defecto = generar_siguiente_nombre_punto(puntos)

    print(f"\n[*] Archivo de destino activo: {rel}")
    entrada = input(f"Introduce una etiqueta para este punto (Enter para '{nombre_por_defecto}'): ").strip()
    nombre = entrada if entrada else nombre_por_defecto

    if not entrada:
        print(f"[*] Asignada automáticamente la etiqueta incremental: '{nombre}'")

    if nombre in puntos and entrada:
        sobrescribir = input(f"[?] El punto '{nombre}' ya existe en {rel}. ¿Deseas sobrescribirlo? (s/N): ").strip().lower()
        if sobrescribir not in ("s", "si", "y", "yes"):
            print("[*] Operación cancelada sin sobrescribir.")
            return False

    descripcion = input("Introduce una breve descripción (opcional): ").strip()
    guardar_punto(nombre, pose, descripcion, path=archivo)
    return True
