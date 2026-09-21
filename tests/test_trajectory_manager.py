"""
Pruebas de verificación de TrajectoryManager y UR10eSoftwareGuard.
Ejecutable en entornos locales o CI sin necesidad de hardware robótico conectado.
"""

import os
import sys
import unittest

# Asegurar importación de módulos en src/
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from trajectory_manager import TrajectoryManager, TrajectoryRoute, TrajectoryStep
from robot_guard import UR10eSoftwareGuard


class TestTrajectoryManager(unittest.TestCase):

    def setUp(self):
        self.routes_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "routes"))

    def test_default_tfg_route(self):
        route = TrajectoryManager.get_default_tfg_route()
        self.assertEqual(route.name, "Trayectoria_Referencia_TFG")
        self.assertEqual(len(route.steps), 2)
        self.assertEqual(route.steps[0].move_type, "lineal")
        self.assertEqual(route.steps[0].scan, False)
        self.assertEqual(route.steps[1].move_type, "lineal")
        self.assertEqual(route.steps[1].scan, True)
        self.assertEqual(route.steps[0].target, TrajectoryManager.DEFAULT_ORIGIN_DEG)
        self.assertEqual(route.steps[1].target, TrajectoryManager.DEFAULT_END_DEG)

    def test_parse_default_json(self):
        json_path = os.path.join(self.routes_dir, "default_tfg.json")
        self.assertTrue(os.path.exists(json_path), f"No existe {json_path}")
        route = TrajectoryManager.from_json(json_path)
        self.assertEqual(len(route.steps), 2)
        self.assertTrue(route.force_constant_z)
        self.assertEqual(route.steps[0].coord_type, "articulares_deg")

    def test_parse_mixta_json(self):
        json_path = os.path.join(self.routes_dir, "ejemplo_ruta_mixta.json")
        self.assertTrue(os.path.exists(json_path), f"No existe {json_path}")
        route = TrajectoryManager.from_json(json_path)
        self.assertEqual(len(route.steps), 3)
        self.assertEqual(route.steps[0].move_type, "lineal")
        self.assertEqual(route.steps[1].move_type, "lineal")
        self.assertEqual(route.steps[2].move_type, "circular")
        self.assertIsNotNone(route.steps[2].via)
        self.assertEqual(len(route.steps[2].via), 6)
        self.assertTrue(route.steps[2].scan)

    def test_parse_csv(self):
        csv_path = os.path.join(self.routes_dir, "ejemplo_ruta.csv")
        self.assertTrue(os.path.exists(csv_path), f"No existe {csv_path}")
        route = TrajectoryManager.from_csv(csv_path)
        self.assertEqual(len(route.steps), 3)
        self.assertEqual(route.steps[0].name, "Posicionamiento_Home")
        self.assertEqual(route.steps[0].scan, False)
        self.assertEqual(route.steps[1].name, "Barrido_Lineal")
        self.assertEqual(route.steps[1].scan, True)
        self.assertEqual(route.steps[2].move_type, "circular")
        self.assertEqual(len(route.steps[2].via), 6)

    def test_leadin_calculation(self):
        p_in = [0.0, 0.0, 0.2, 3.14, 0.0, 0.0]
        p_out = [0.1, 0.0, 0.2, 3.14, 0.0, 0.0]
        ext_in, ext_out = TrajectoryManager.calcular_puntos_leadin(p_in, p_out, lead_in_mm=20.0, lead_out_mm=20.0)
        # El vector es en +X. El lead-in debe estar en -20mm (-0.02m)
        self.assertAlmostEqual(ext_in[0], -0.02, places=4)
        self.assertAlmostEqual(ext_out[0], 0.12, places=4)
        self.assertEqual(ext_in[2], 0.2)
        self.assertEqual(ext_out[2], 0.2)

    def test_software_guard_bounds(self):
        guard = UR10eSoftwareGuard(bounds_xyz={'x': (-1.0, 1.0), 'y': (-1.0, 1.0), 'z': (0.0, 1.0)})
        # Pose válida
        valida, _ = guard.validar_pose([0.5, -0.2, 0.3, 3.14, 0.0, 0.0])
        self.assertTrue(valida)

        # Pose que penetra la mesa (Z < 0)
        invalida_z, err_z = guard.validar_pose([0.5, -0.2, -0.05, 3.14, 0.0, 0.0])
        self.assertFalse(invalida_z)
        self.assertIn("Z", err_z)

        # Pose fuera de límites en X
        invalida_x, err_x = guard.validar_pose([1.5, -0.2, 0.3, 3.14, 0.0, 0.0])
        self.assertFalse(invalida_x)
        self.assertIn("X", err_x)


if __name__ == "__main__":
    unittest.main()
