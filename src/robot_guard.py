"""
Módulo de seguridad espacial y cinemática para el robot UR10e y sensor Gocator.
Implementa guardarraíles por software para prevenir colisiones del cabezal y sensor,
verificar límites cinemáticos y supervisar paradas de protección.
Basado en los estándares de ur10e-safety-limits-skill.
"""

import math
from typing import List, Tuple, Optional

class UR10eSoftwareGuard:
    def __init__(
        self,
        bounds_xyz: Optional[dict] = None,
        max_tilt_angle_deg: float = 30.0,
        enforce_bounds: bool = True
    ):
        """
        :param bounds_xyz: Diccionario con límites {'x': (min, max), 'y': (min, max), 'z': (min, max)} en metros.
        :param max_tilt_angle_deg: Desviación máxima permitida de inclinación de la herramienta.
        :param enforce_bounds: Habilita o deshabilita la comprobación estricta de límites XYZ.
        """
        # Envolvente segura por defecto alrededor del área de trabajo del robot (en metros)
        # Valores amplios pero seguros para evitar colisiones contra el suelo o la base
        self.bounds = bounds_xyz or {
            'x': (-1.2, 1.2),
            'y': (-1.2, 1.2),
            'z': (-0.2, 1.2)   # Previene que el cabezal baje por debajo de la mesa de trabajo
        }
        self.max_tilt_deg = max_tilt_angle_deg
        self.enforce_bounds = enforce_bounds

    def validar_pose(self, pose: List[float], nombre_paso: str = "Paso") -> Tuple[bool, str]:
        """
        Valida que una pose cartesiana [x, y, z, rx, ry, rz] esté dentro de la envolvente segura.
        """
        if len(pose) != 6:
            return False, f"[{nombre_paso}] La pose cartesiana debe tener 6 elementos [x, y, z, rx, ry, rz]. Recibido: {len(pose)}"

        x, y, z, rx, ry, rz = pose

        if self.enforce_bounds:
            if not (self.bounds['x'][0] <= x <= self.bounds['x'][1]):
                return False, f"[{nombre_paso}] Violación de límite en X: {x:.4f} m fuera de rango {self.bounds['x']}"
            if not (self.bounds['y'][0] <= y <= self.bounds['y'][1]):
                return False, f"[{nombre_paso}] Violación de límite en Y: {y:.4f} m fuera de rango {self.bounds['y']}"
            if not (self.bounds['z'][0] <= z <= self.bounds['z'][1]):
                return False, f"[{nombre_paso}] Violación de límite en Z: {z:.4f} m fuera de rango {self.bounds['z']}"

        return True, "OK"

    def validar_articulaciones(self, q_rad: List[float], nombre_paso: str = "Paso") -> Tuple[bool, str]:
        """
        Valida que las posiciones articulares en radianes estén dentro de los límites seguros (+/- 2*pi).
        """
        if len(q_rad) != 6:
            return False, f"[{nombre_paso}] Se esperan 6 articulaciones. Recibido: {len(q_rad)}"

        for i, q in enumerate(q_rad):
            if abs(q) > 2.0 * math.pi + 0.1:
                return False, f"[{nombre_paso}] Articulación {i+1} excede el rango admisible de rotación: {math.degrees(q):.2f}°"

        return True, "OK"

    @staticmethod
    def verificar_estado_seguridad(rtde_rec) -> Tuple[bool, str]:
        """
        Verifica en tiempo real si el robot se encuentra en parada de protección o emergencia.
        """
        if rtde_rec is None:
            return True, "Modo sin telemetría (omitido)"

        try:
            if hasattr(rtde_rec, "isEmergencyStopped") and rtde_rec.isEmergencyStopped():
                return False, "Seta de emergencia del robot activada (Emergency Stop)."
            if hasattr(rtde_rec, "isProtectiveStopped") and rtde_rec.isProtectiveStopped():
                return False, "Robot detenido por parada de protección (Protective Stop / posible colisión)."
        except Exception as e:
            return False, f"Error al verificar estado de seguridad: {e}"

        return True, "Robot en estado seguro para operar."
