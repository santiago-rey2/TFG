"""
Módulo de control de movimiento para el robot UR10e.
Ejecuta trayectorias parametrizadas (lineales y circulares) a partir de:
  - Archivos JSON (--json)
  - Archivos CSV (--csv)
  - Argumentos de línea de comandos (--modo cli)
  - Modo interactivo por consola (--interactivo)
  - Trayectoria por defecto del TFG (sin argumentos)

Garantiza el forzado de altura Z constante para escaneo plano e integra
guardarraíles de seguridad espacial.
"""

import os
import sys
import time
import argparse
from typing import Optional

try:
    import rtde_control
    import rtde_receive
except ImportError:
    rtde_control = None
    rtde_receive = None

from trajectory_manager import TrajectoryManager, TrajectoryRoute, TrajectoryStep
from robot_guard import UR10eSoftwareGuard


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Control de movimiento para UR10e (Soporte JSON, CSV, CLI y modo Interactivo)"
    )
    # Modos de entrada
    parser.add_argument("--json", type=str, help="Ruta a un archivo de definición JSON (ej. routes/default_tfg.json)")
    parser.add_argument("--csv", type=str, help="Ruta a un archivo tabular CSV (ej. routes/ejemplo_ruta.csv)")
    parser.add_argument("--interactivo", action="store_true", help="Iniciar asistente guiado por consola")
    parser.add_argument("--modo", choices=["default", "cli"], default="default", help="Modo de ejecución directo")
    parser.add_argument("--dry-run", action="store_true", help="Simular la ejecución sin enviar comandos al robot real")

    # Parámetros directos CLI
    parser.add_argument("--tipo-mov", choices=["lineal", "circular"], default="lineal", help="Tipo de movimiento para CLI")
    parser.add_argument("--coord-tipo", choices=["articulares_deg", "cartesianas", "articulares_rad"],
                        default="articulares_deg", help="Formato de las coordenadas")
    parser.add_argument("--origen", nargs=6, type=float, help="Punto de origen (6 valores)")
    parser.add_argument("--via", nargs=6, type=float, help="Punto intermedio para movimiento circular (6 valores)")
    parser.add_argument("--destino", nargs=6, type=float, help="Punto de destino (6 valores)")
    
    # Parámetros dinámicos
    parser.add_argument("--velocidad", type=float, default=0.1, help="Velocidad del TCP en m/s")
    parser.add_argument("--aceleracion", type=float, default=0.2, help="Aceleración en m/s^2")
    parser.add_argument("--sin-z-constante", action="store_true", help="Desactiva el forzado de altura Z constante")

    return parser.parse_args()


def ejecutar_ruta(route: TrajectoryRoute, robot_ip: str, dry_run: bool = False):
    guard = UR10eSoftwareGuard()

    print(f"\n{'=' * 65}")
    print(f"[*] INICIANDO EJECUCIÓN DE TRAYECTORIA: {route.name}")
    print(f"[*] Descripción: {route.description}")
    print(f"[*] Total de pasos a ejecutar: {len(route.steps)}")
    print(f"[*] Forzar Z constante: {route.force_constant_z}")
    if dry_run or rtde_control is None:
        print(f"[*] MODO: SIMULACIÓN / DRY-RUN (sin enviar comandos a robot físico)")
    print(f"{'=' * 65}")

    rtde_ctrl = None
    rtde_rec = None

    try:
        if not dry_run and rtde_control is not None:
            print(f"[*] Conectando con UR10e en {robot_ip}...")
            rtde_ctrl = rtde_control.RTDEControlInterface(robot_ip)
            try:
                rtde_rec = rtde_receive.RTDEReceiveInterface(robot_ip)
            except Exception as e:
                print(f"[!] Advertencia: No se pudo conectar interfaz de telemetría: {e}")

            # 1. Comprobación preventiva de seguridad
            es_seguro, msg_seguridad = UR10eSoftwareGuard.verificar_estado_seguridad(rtde_rec)
            if not es_seguro:
                raise RuntimeError(f"Fallo de seguridad inicial: {msg_seguridad}")
        else:
            if rtde_control is None and not dry_run:
                print("[!] 'ur_rtde' no encontrado en el entorno local. Activando modo SIMULACIÓN.")
                dry_run = True

        # Registrar Z de referencia global si aplica
        z_referencia_global: Optional[float] = None

        for idx, step in enumerate(route.steps, start=1):
            print(f"\n>> [{idx}/{len(route.steps)}] Ejecutando paso '{step.name}' (Tipo: {step.move_type.upper()})")

            # A. Resolver pose cartesiana de destino
            target_pose = TrajectoryManager.convertir_a_pose_cartesiana(step.target, step.coord_type, rtde_ctrl)

            # B. Si el paso especifica origen previo, convertirlo y mover primero
            if step.origin is not None:
                origin_pose = TrajectoryManager.convertir_a_pose_cartesiana(step.origin, step.coord_type, rtde_ctrl)
                if z_referencia_global is None:
                    z_referencia_global = origin_pose[2]
                    print(f"  > Z de referencia establecida: {z_referencia_global:.4f} m")

                # Validar y mover a origen
                ok, err = guard.validar_pose(origin_pose, f"{step.name}_Origen")
                if not ok:
                    raise ValueError(err)

                print(f"  > Posicionando en origen del tramo...")
                if rtde_ctrl:
                    rtde_ctrl.moveL(origin_pose, step.speed, step.acceleration)
                    while not rtde_ctrl.isSteady():
                        time.sleep(0.05)
                else:
                    print(f"    [SIMULADO] moveL a origen: {origin_pose}")

            # C. Aplicar forzado de Z constante si está activado
            if route.force_constant_z:
                if z_referencia_global is None:
                    # Usar la Z actual del TCP
                    current_tcp = rtde_rec.getActualTCPPose() if rtde_rec else target_pose
                    z_referencia_global = current_tcp[2]
                    print(f"  > Z de referencia fijada en: {z_referencia_global:.4f} m")
                target_pose[2] = z_referencia_global

            # D. Validar límites de la pose destino
            ok, err = guard.validar_pose(target_pose, step.name)
            if not ok:
                raise ValueError(err)

            # E. Ejecutar movimiento según su tipo
            if step.move_type == "lineal":
                print(f"  > Moviendo linealmente a destino (v={step.speed} m/s)...")
                if rtde_ctrl:
                    rtde_ctrl.moveL(target_pose, step.speed, step.acceleration)
                    while not rtde_ctrl.isSteady():
                        time.sleep(0.05)
                else:
                    print(f"    [SIMULADO] moveL a destino: {target_pose}")

            elif step.move_type == "circular":
                if not step.via:
                    raise ValueError(f"El paso '{step.name}' es circular pero no tiene definido el punto 'via'.")

                via_pose = TrajectoryManager.convertir_a_pose_cartesiana(step.via, step.coord_type, rtde_ctrl)
                if route.force_constant_z and z_referencia_global is not None:
                    via_pose[2] = z_referencia_global

                ok, err = guard.validar_pose(via_pose, f"{step.name}_Via")
                if not ok:
                    raise ValueError(err)

                print(f"  > Ejecutando arco circular (moveC) pasando por vía...")
                if rtde_ctrl:
                    rtde_ctrl.moveC(
                        via_pose,
                        target_pose,
                        step.speed,
                        step.acceleration,
                        step.blend_radius,
                        step.orientation_mode
                    )
                    while not rtde_ctrl.isSteady():
                        time.sleep(0.05)
                else:
                    print(f"    [SIMULADO] moveC pasando por vía: {via_pose} hasta destino: {target_pose}")

            print(f"  [OK] Paso '{step.name}' completado con éxito.")

        print(f"\n[SUCCESS] Toda la trayectoria '{route.name}' se completó satisfactoriamente.")

    except Exception as e:
        print(f"\n[ERROR] Error crítico durante la ejecución del movimiento: {e}")
        sys.exit(1)

    finally:
        if rtde_ctrl:
            try:
                rtde_ctrl.stopScript()
                rtde_ctrl.disconnect()
            except Exception:
                pass
            print("[*] Interfaz de control liberada y desconectada.")
        if rtde_rec:
            try:
                rtde_rec.disconnect()
            except Exception:
                pass


def main():
    args = parse_arguments()
    robot_ip = os.getenv("ROBOT_IP", "192.168.0.210")

    # Selección de la fuente de la trayectoria
    if args.json:
        route = TrajectoryManager.from_json(args.json)
    elif args.csv:
        route = TrajectoryManager.from_csv(args.csv)
    elif args.interactivo:
        route = TrajectoryManager.from_interactive()
    elif args.modo == "cli" and args.destino:
        setattr(args, "forzar_z", not args.sin_z_constante)
        route = TrajectoryManager.from_cli(args)
    else:
        # Modo por defecto (retrocompatibilidad con TFG)
        print("[*] Sin argumentos de ruta. Ejecutando trayectoria de referencia por defecto del TFG.")
        route = TrajectoryManager.get_default_tfg_route()

    if args.sin_z_constante:
        route.force_constant_z = False

    ejecutar_ruta(route, robot_ip, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
