"""
Pruebas de verificación de los módulos desacoplados: robot_movement y gocator.
Verifica la funcionalidad sin hardware físico conectado.
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from gocator import GocatorClient
import robot_movement


class TestDecoupledModules(unittest.TestCase):

    def test_gocator_client_initialization(self):
        client = GocatorClient(ip="192.168.0.10", port=8190)
        self.assertEqual(client.ip, "192.168.0.10")
        self.assertEqual(client.port, 8190)
        self.assertFalse(client.is_running)

    @patch("socket.socket")
    def test_gocator_send_command_success(self, mock_socket_class):
        mock_sock = MagicMock()
        mock_socket_class.return_value.__enter__.return_value = mock_sock
        mock_sock.recv.return_value = b"OK\r\n"

        client = GocatorClient(ip="127.0.0.1", port=8190)
        res = client.send_command("start")
        self.assertTrue(res)
        self.assertTrue(client.is_running)

        mock_sock.recv.return_value = b"OK\r\n"
        res_stop = client.send_command("stop")
        self.assertTrue(res_stop)
        self.assertFalse(client.is_running)

    def test_robot_movement_listar_rutas(self):
        rutas = robot_movement.listar_archivos_rutas("routes")
        self.assertTrue(len(rutas) >= 2)
        nombres = [os.path.basename(r) for r in rutas]
        self.assertIn("default_tfg.json", nombres)
        self.assertIn("ejemplo_ruta.csv", nombres)

    def test_robot_movement_dry_run_execution(self):
        route = robot_movement.TrajectoryManager.get_default_tfg_route()
        exito = robot_movement.ejecutar_ruta(route, robot_ip="127.0.0.1", dry_run=True)
        self.assertTrue(exito)

    def test_robot_movement_mover_a_origen_dry_run(self):
        route = robot_movement.TrajectoryManager.get_default_tfg_route()
        exito = robot_movement.mover_a_origen(route, rtde_ctrl=None, rtde_rec=None, dry_run=True)
        self.assertTrue(exito)


if __name__ == "__main__":
    unittest.main()
