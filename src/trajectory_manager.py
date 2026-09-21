"""
Módulo de gestión, análisis y parseo de trayectorias para UR10e y Gocator 2600.
Permite definir y cargar rutas de movimiento desde:
  1. Archivos JSON
  2. Archivos CSV
  3. Argumentos por Consola (CLI)
  4. Modo Interactivo
Soporta movimientos lineales ('moveL') y circulares ('moveC'), sincronización
de escaneo y forzado de altura Z constante.
"""

import json
import csv
import math
import os
import sys
import numpy as np
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple


@dataclass
class TrajectoryStep:
    id: int
    name: str
    move_type: str                  # 'lineal' | 'circular'
    coord_type: str                 # 'articulares_deg' | 'articulares_rad' | 'cartesianas'
    target: List[float]             # 6 valores [x,y,z,rx,ry,rz] o [q1..q6]
    origin: Optional[List[float]] = None
    via: Optional[List[float]] = None  # Requerido para move_type == 'circular'
    scan: bool = False
    speed: float = 0.1              # m/s
    acceleration: float = 0.2       # m/s^2
    blend_radius: float = 0.0       # m
    orientation_mode: int = 0       # 0: orientacion fija al TCP, 1: no restringida


@dataclass
class TrajectoryRoute:
    name: str
    description: str
    default_speed: float = 0.1
    default_acceleration: float = 0.2
    force_constant_z: bool = True
    lead_in_mm: float = 0.0
    lead_out_mm: float = 0.0
    steps: List[TrajectoryStep] = field(default_factory=list)


class TrajectoryManager:
    """Motor de carga, validación y normalización de rutas de movimiento."""

    # Coordenadas de referencia estándar del TFG (en grados articulares)
    DEFAULT_ORIGIN_DEG = [60.0, -118.0, -75.0, -75.0, 89.0, 149.0]
    DEFAULT_END_DEG = [132.0, -108.0, -87.0, -72.0, 90.0, 220.0]

    @classmethod
    def get_default_tfg_route(cls) -> TrajectoryRoute:
        """Retorna la trayectoria de referencia estándar utilizada en el proyecto TFG."""
        route = TrajectoryRoute(
            name="Trayectoria_Referencia_TFG",
            description="Trayectoria lineal plana horizontal de referencia del TFG (grados articulares).",
            default_speed=0.1,
            default_acceleration=0.2,
            force_constant_z=True
        )
        # Paso 1: Posicionamiento inicial en origen (sin láser)
        route.steps.append(TrajectoryStep(
            id=1,
            name="Posicionamiento_Origen",
            move_type="lineal",
            coord_type="articulares_deg",
            target=list(cls.DEFAULT_ORIGIN_DEG),
            scan=False,
            speed=0.1,
            acceleration=0.2
        ))
        # Paso 2: Barrido lineal hasta el final (con láser)
        route.steps.append(TrajectoryStep(
            id=2,
            name="Barrido_Lineal_Escaneo",
            move_type="lineal",
            coord_type="articulares_deg",
            origin=list(cls.DEFAULT_ORIGIN_DEG),
            target=list(cls.DEFAULT_END_DEG),
            scan=True,
            speed=0.1,
            acceleration=0.2
        ))
        return route

    @classmethod
    def from_json(cls, file_path_or_str: str) -> TrajectoryRoute:
        """Carga y valida una trayectoria desde un archivo JSON o una cadena JSON."""
        if os.path.isfile(file_path_or_str):
            with open(file_path_or_str, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = json.loads(file_path_or_str)

        params = data.get("parametros_defecto", {})
        route = TrajectoryRoute(
            name=data.get("nombre_trayectoria", "Ruta_JSON"),
            description=data.get("descripcion", ""),
            default_speed=float(params.get("velocidad", 0.1)),
            default_acceleration=float(params.get("aceleracion", 0.2)),
            force_constant_z=bool(params.get("forzar_z_constante", True)),
            lead_in_mm=float(params.get("lead_in_mm", 0.0)),
            lead_out_mm=float(params.get("lead_out_mm", 0.0))
        )

        raw_steps = data.get("rutas", [])
        if not raw_steps:
            raise ValueError("El archivo JSON no contiene ninguna ruta o paso en la clave 'rutas'.")

        for idx, item in enumerate(raw_steps, start=1):
            step_id = item.get("id", idx)
            name = item.get("nombre", f"Paso_{step_id}")
            move_type = item.get("tipo_movimiento", "lineal").strip().lower()
            if move_type not in ("lineal", "circular"):
                raise ValueError(f"Paso {step_id}: tipo_movimiento debe ser 'lineal' o 'circular'. Recibido: '{move_type}'")

            coord_type = item.get("tipo_coordenadas", "articulares_deg").strip().lower()
            if coord_type not in ("articulares_deg", "articulares_rad", "cartesianas"):
                raise ValueError(f"Paso {step_id}: tipo_coordenadas no válido: '{coord_type}'")

            target = item.get("destino")
            if not target or len(target) != 6:
                raise ValueError(f"Paso {step_id}: 'destino' debe ser una lista de 6 números.")
            target = [float(x) for x in target]

            origin = item.get("origen")
            if origin:
                if len(origin) != 6:
                    raise ValueError(f"Paso {step_id}: 'origen' debe tener 6 números.")
                origin = [float(x) for x in origin]

            via = item.get("pose_via")
            if move_type == "circular":
                if not via or len(via) != 6:
                    raise ValueError(f"Paso {step_id}: los movimientos circulares requieren 'pose_via' de 6 números.")
                via = [float(x) for x in via]

            step = TrajectoryStep(
                id=step_id,
                name=name,
                move_type=move_type,
                coord_type=coord_type,
                target=target,
                origin=origin,
                via=via,
                scan=bool(item.get("escanear", False)),
                speed=float(item.get("velocidad", route.default_speed)),
                acceleration=float(item.get("aceleracion", route.default_acceleration)),
                blend_radius=float(item.get("blend_radius", 0.0)),
                orientation_mode=int(item.get("modo_orientacion", 0))
            )
            route.steps.append(step)

        return route

    @classmethod
    def from_csv(cls, file_path: str) -> TrajectoryRoute:
        """Carga y valida una trayectoria desde un archivo tabular CSV."""
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"No se encontró el archivo CSV en: {file_path}")

        route = TrajectoryRoute(
            name=os.path.splitext(os.path.basename(file_path))[0],
            description=f"Ruta cargada desde {file_path}",
            force_constant_z=True
        )

        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            # Normalizar nombres de columnas a minúsculas
            reader.fieldnames = [c.strip().lower() for c in reader.fieldnames if c]

            for row_idx, row in enumerate(reader, start=1):
                # Omitir filas vacías
                if not row or not any(row.values()):
                    continue

                step_id = int(row.get("id", row_idx))
                name = row.get("nombre", f"Paso_{step_id}").strip()
                move_type = row.get("tipo_movimiento", "lineal").strip().lower()
                if move_type not in ("lineal", "circular"):
                    raise ValueError(f"Línea {row_idx}: tipo_movimiento inválido '{move_type}'")

                coord_type = row.get("tipo_coordenadas", "articulares_deg").strip().lower()
                
                # Leer coordenadas de destino (x,y,z,rx,ry,rz o q1..q6)
                try:
                    target = [
                        float(row["x"]), float(row["y"]), float(row["z"]),
                        float(row["rx"]), float(row["ry"]), float(row["rz"])
                    ]
                except (KeyError, ValueError) as e:
                    raise ValueError(f"Línea {row_idx}: error al leer coordenadas de destino (x..rz): {e}")

                # Leer vía en caso circular
                via = None
                if move_type == "circular":
                    try:
                        via = [
                            float(row["via_x"]), float(row["via_y"]), float(row["via_z"]),
                            float(row["via_rx"]), float(row["via_ry"]), float(row["via_rz"])
                        ]
                    except (KeyError, ValueError) as e:
                        raise ValueError(f"Línea {row_idx}: movimiento circular requiere columnas via_x..via_rz válidas: {e}")

                scan_val = row.get("escanear", "false").strip().lower()
                scan = scan_val in ("true", "1", "si", "yes")

                speed = float(row.get("velocidad") or route.default_speed)
                accel = float(row.get("aceleracion") or route.default_acceleration)
                blend = float(row.get("blend_radius") or 0.0)

                step = TrajectoryStep(
                    id=step_id,
                    name=name,
                    move_type=move_type,
                    coord_type=coord_type,
                    target=target,
                    via=via,
                    scan=scan,
                    speed=speed,
                    acceleration=accel,
                    blend_radius=blend
                )
                route.steps.append(step)

        if not route.steps:
            raise ValueError(f"El archivo CSV {file_path} no contiene pasos de trayectoria válidos.")

        return route

    @classmethod
    def from_cli(cls, args) -> TrajectoryRoute:
        """Construye una ruta a partir de argumentos directos de línea de comandos."""
        route = TrajectoryRoute(
            name="Ruta_Consola_CLI",
            description="Trayectoria definida mediante argumentos de consola.",
            default_speed=args.velocidad if hasattr(args, "velocidad") else 0.1,
            default_acceleration=args.aceleracion if hasattr(args, "aceleracion") else 0.2,
            force_constant_z=getattr(args, "forzar_z", True)
        )

        move_type = getattr(args, "tipo_mov", "lineal").strip().lower()
        coord_type = getattr(args, "coord_tipo", "articulares_deg").strip().lower()
        target = getattr(args, "destino", None)
        origin = getattr(args, "origen", None)
        via = getattr(args, "via", None)
        scan = getattr(args, "escanear", False)

        if not target or len(target) != 6:
            raise ValueError("El parámetro --destino requiere exactamente 6 valores numéricos.")

        if move_type == "circular" and (not via or len(via) != 6):
            raise ValueError("Los movimientos circulares (--tipo-mov circular) requieren --via con 6 valores.")

        # Si se especifica origen, creamos paso 1 (ir a origen sin escaneo) y paso 2 (ir a destino con escaneo si aplica)
        if origin and len(origin) == 6:
            route.steps.append(TrajectoryStep(
                id=1,
                name="Aproximacion_Origen",
                move_type="lineal",
                coord_type=coord_type,
                target=list(origin),
                scan=False,
                speed=route.default_speed,
                acceleration=route.default_acceleration
            ))

        route.steps.append(TrajectoryStep(
            id=len(route.steps) + 1,
            name="Movimiento_Principal",
            move_type=move_type,
            coord_type=coord_type,
            target=list(target),
            origin=list(origin) if origin else None,
            via=list(via) if via else None,
            scan=scan,
            speed=route.default_speed,
            acceleration=route.default_acceleration
        ))

        return route

    @classmethod
    def from_interactive(cls) -> TrajectoryRoute:
        """Guía al usuario por consola de forma interactiva para definir o seleccionar una ruta."""
        print("\n" + "=" * 60)
        print(" ASISTENTE INTERACTIVO DE TRAYECTORIAS UR10e & GOCATOR")
        print("=" * 60)
        print("1. Cargar ruta desde archivo JSON")
        print("2. Cargar ruta desde archivo CSV")
        print("3. Usar trayectoria de referencia TFG (Origen -> Fin)")
        print("4. Ingresar coordenadas manualmente por consola")
        
        opcion = input("\nSeleccione una opción [1-4] (por defecto 3): ").strip()
        if opcion == "1":
            ruta_archivo = input("Ruta al archivo JSON [ej: routes/default_tfg.json]: ").strip()
            if not ruta_archivo:
                ruta_archivo = "routes/default_tfg.json"
            return cls.from_json(ruta_archivo)

        elif opcion == "2":
            ruta_archivo = input("Ruta al archivo CSV [ej: routes/ejemplo_ruta.csv]: ").strip()
            if not ruta_archivo:
                ruta_archivo = "routes/ejemplo_ruta.csv"
            return cls.from_csv(ruta_archivo)

        elif opcion == "4":
            print("\n--- Entrada Manual de Movimiento ---")
            tipo_mov = input("Tipo de movimiento (lineal / circular) [por defecto: lineal]: ").strip().lower() or "lineal"
            tipo_coord = input("Tipo de coordenadas (articulares_deg / cartesianas) [por defecto: articulares_deg]: ").strip().lower() or "articulares_deg"
            
            prompt_dest = "Ingrese los 6 valores de DESTINO separados por espacio: "
            valores_dest = [float(x) for x in input(prompt_dest).strip().split()]
            if len(valores_dest) != 6:
                raise ValueError("Se deben ingresar exactamente 6 valores numéricos.")

            valores_via = None
            if tipo_mov == "circular":
                prompt_via = "Ingrese los 6 valores del punto intermedio (VIA) separados por espacio: "
                valores_via = [float(x) for x in input(prompt_via).strip().split()]
                if len(valores_via) != 6:
                    raise ValueError("Se deben ingresar exactamente 6 valores numéricos para VIA.")

            escanear_str = input("¿Activar escaneo Gocator durante el movimiento? (s/n) [n]: ").strip().lower()
            escanear = escanear_str in ("s", "si", "y", "yes")

            vel_str = input("Velocidad de avance en m/s [0.1]: ").strip()
            velocidad = float(vel_str) if vel_str else 0.1

            route = TrajectoryRoute(
                name="Ruta_Manual_Interactiva",
                description="Ruta ingresada interactivamente por consola.",
                default_speed=velocidad,
                default_acceleration=0.2,
                force_constant_z=True
            )
            route.steps.append(TrajectoryStep(
                id=1,
                name="Paso_Manual_1",
                move_type=tipo_mov,
                coord_type=tipo_coord,
                target=valores_dest,
                via=valores_via,
                scan=escanear,
                speed=velocidad,
                acceleration=0.2
            ))
            return route

        else:
            print("[*] Seleccionada trayectoria por defecto del TFG.")
            return cls.get_default_tfg_route()

    # --- Métodos de Normalización y Cinemática ---

    @staticmethod
    def convertir_a_pose_cartesiana(coord: List[float], coord_type: str, rtde_ctrl) -> List[float]:
        """
        Convierte una coordenada (articular o cartesiana) a una pose cartesiana TCP [x, y, z, rx, ry, rz]
        utilizando la cinemática directa del robot si es necesario.
        """
        if coord_type == "cartesianas":
            return list(coord)
        
        # Si son articulares:
        if coord_type == "articulares_deg":
            q_rad = [math.radians(a) for a in coord]
        else: # articulares_rad
            q_rad = list(coord)

        if rtde_ctrl is not None:
            pose = rtde_ctrl.getForwardKinematics(q_rad)
            return list(pose)
        else:
            # Si no hay conexión (ej. pruebas o dry-run sin robot), retornamos representación estimada
            return [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]

    @staticmethod
    def convertir_a_articular_rad(coord: List[float], coord_type: str) -> List[float]:
        """Convierte una coordenada articular a radianes."""
        if coord_type == "articulares_deg":
            return [math.radians(a) for a in coord]
        elif coord_type == "articulares_rad":
            return list(coord)
        else:
            raise ValueError("No se puede convertir directamente coordenadas cartesianas a articulares sin solver.")

    @staticmethod
    def calcular_puntos_leadin(
        pose_inicio: List[float],
        pose_fin: List[float],
        lead_in_mm: float = 20.0,
        lead_out_mm: float = 20.0
    ) -> Tuple[List[float], List[float]]:
        """
        Calcula los puntos extendidos antes del inicio y después del final de una recta,
        para permitir que el robot alcance la velocidad constante antes de activar el sensor.
        Basado en ur10e-trajectory-skill.
        """
        p_in = np.array(pose_inicio[:3])
        p_out = np.array(pose_fin[:3])
        v_dir = p_out - p_in
        dist = np.linalg.norm(v_dir)

        if dist < 1e-6:
            return pose_inicio, pose_fin

        u_dir = v_dir / dist
        start_ext = p_in - u_dir * (lead_in_mm / 1000.0)
        end_ext = p_out + u_dir * (lead_out_mm / 1000.0)

        pose_start_ext = list(start_ext) + pose_inicio[3:]
        pose_end_ext = list(end_ext) + pose_fin[3:]
        return pose_start_ext, pose_end_ext
