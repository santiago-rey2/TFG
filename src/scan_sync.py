"""
Módulo de escaneo sincronizado para UR10e y Gocator 2600.
Coordina el movimiento lineal ('moveL') o circular ('moveC') del robot con
la activación, disparo ('trigger') y parada ('stop') del perfilómetro láser.
Soporta rutas desde:
  - Archivos JSON (--json)
  - Archivos CSV (--csv)
  - Argumentos directos por consola (--modo cli)
  - Asistente interactivo (--interactivo)
  - Trayectoria de referencia del TFG (por defecto)
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

from gocator import GocatorClient
from trajectory_manager import TrajectoryManager, TrajectoryRoute, TrajectoryStep
from robot_guard import UR10eSoftwareGuard


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Escaneo sincronizado UR10e + Gocator (Soporte JSON, CSV, CLI e Interactivo)"
    )
    # Modos de entrada
    parser.add_argument("--json", type=str, help="Ruta al archivo de trayectoria JSON")
    parser.add_argument("--csv", type=str, help="Ruta al archivo tabular CSV")
    parser.add_argument("--interactivo", action="store_true", help="Iniciar asistente interactivo")
    parser.add_argument("--modo", choices=["default", "cli"], default="default", help="Modo directo")
    parser.add_argument("--dry-run", action="store_true", help="Simular ejecución sin enviar comandos reales a hardware")

    # Parámetros CLI directos
    parser.add_argument("--tipo-mov", choices=["lineal", "circular"], default="lineal", help="Tipo de movimiento")
    parser.add_argument("--coord-tipo", choices=["articulares_deg", "cartesianas", "articulares_rad"],
                        default="articulares_deg", help="Formato de coordenadas")
    parser.add_argument("--origen", nargs=6, type=float, help="Punto de origen (6 valores)")
    parser.add_argument("--via", nargs=6, type=float, help="Punto intermedio para arco circular (6 valores)")
    parser.add_argument("--destino", nargs=6, type=float, help="Punto de destino (6 valores)")
    parser.add_argument("--escanear", action="store_true", default=True, help="Activar sensor Gocator durante el barrido")

    # Parámetros dinámicos
    parser.add_argument("--velocidad", type=float, default=0.1, help="Velocidad del TCP en m/s")
    parser.add_argument("--aceleracion", type=float, default=0.2, help="Aceleración en m/s^2")
    parser.add_argument("--sin-z-constante", action="store_true", help="Desactiva el forzado de altura Z constante")

    return parser.parse_args()


def ejecutar_escaneo_sincronizado(
    route: TrajectoryRoute,
    robot_ip: str,
    gocator_ip: str,
    gocator_port: int,
    dry_run: bool = False
):
    guard = UR10eSoftwareGuard()
    gocator = GocatorClient(ip=gocator_ip, port=gocator_port)

    print(f"\n{'=' * 70}")
    print(f"[*] INICIANDO ESCANEO SINCRONIZADO: {route.name}")
    print(f"[*] Robot IP: {robot_ip} | Gocator: {gocator_ip}:{gocator_port}")
    print(f"[*] Total pasos: {len(route.steps)} | Z constante: {route.force_constant_z}")
    if dry_run or rtde_control is None:
        print(f"[*] MODO: SIMULACIÓN / DRY-RUN (sin enviar comandos a robot físico ni sensor)")
    print(f"{'=' * 70}")

    rtde_ctrl = None
    rtde_rec = None

    try:
        # 1. Conexiones
        if not dry_run and rtde_control is not None:
            print(f"[*] Conectando con UR10e en {robot_ip}...")
            rtde_ctrl = rtde_control.RTDEControlInterface(robot_ip)
            try:
                rtde_rec = rtde_receive.RTDEReceiveInterface(robot_ip)
            except Exception as e:
                print(f"[!] Advertencia: Telemetría no disponible: {e}")

            # Comprobar seguridad previa
            es_seguro, msg_seguridad = UR10eSoftwareGuard.verificar_estado_seguridad(rtde_rec)
            if not es_seguro:
                raise RuntimeError(f"Fallo de seguridad inicial: {msg_seguridad}")
        else:
            if rtde_control is None and not dry_run:
                print("[!] 'ur_rtde' no encontrado en el entorno local. Activando modo SIMULACIÓN.")
                dry_run = True

        z_referencia_global: Optional[float] = None

        # 2. Ejecución secuencial de pasos
        for idx, step in enumerate(route.steps, start=1):
            print(f"\n>> [{idx}/{len(route.steps)}] Paso: '{step.name}' | Movimiento: {step.move_type.upper()} | Escaneo: {'ACTIVO' if step.scan else 'INACTIVO'}")

            target_pose = TrajectoryManager.convertir_a_pose_cartesiana(step.target, step.coord_type, rtde_ctrl)

            # Posicionamiento previo en origen si está indicado
            if step.origin is not None:
                origin_pose = TrajectoryManager.convertir_a_pose_cartesiana(step.origin, step.coord_type, rtde_ctrl)
                if z_referencia_global is None:
                    z_referencia_global = origin_pose[2]
                    print(f"  > Z de referencia establecida: {z_referencia_global:.4f} m")

                ok, err = guard.validar_pose(origin_pose, f"{step.name}_Origen")
                if not ok:
                    raise ValueError(err)

                print(f"  > Moviendo a posición de origen (reposicionamiento sin sensor)...")
                if rtde_ctrl:
                    rtde_ctrl.moveL(origin_pose, step.speed, step.acceleration)
                    while not rtde_ctrl.isSteady():
                        time.sleep(0.05)
                    time.sleep(0.5)
                else:
                    print(f"    [SIMULADO] moveL a origen: {origin_pose}")

            # Forzar Z constante si está activado
            if route.force_constant_z:
                if z_referencia_global is None:
                    current_tcp = rtde_rec.getActualTCPPose() if rtde_rec else target_pose
                    z_referencia_global = current_tcp[2]
                    print(f"  > Z de referencia fijada en: {z_referencia_global:.4f} m")
                target_pose[2] = z_referencia_global

            ok, err = guard.validar_pose(target_pose, step.name)
            if not ok:
                raise ValueError(err)

            # Si este paso requiere escaneo, activar sensor Gocator
            if step.scan:
                print("  [*] Activando láser del sensor Gocator (START)...")
                if not dry_run:
                    if not gocator.start():
                        raise RuntimeError("No se pudo iniciar el escaneo en el sensor Gocator.")
                    print("  [*] Enviando señal de disparo (TRIGGER)...")
                    gocator.trigger()
                    time.sleep(0.1)
                else:
                    print("    [SIMULADO] Sensor Gocator -> START y TRIGGER emitidos.")

            # Ejecución del movimiento
            if step.move_type == "lineal":
                print(f"  > Ejecutando barrido lineal a destino (v={step.speed} m/s)...")
                if rtde_ctrl:
                    rtde_ctrl.moveL(target_pose, step.speed, step.acceleration)
                    while not rtde_ctrl.isSteady():
                        time.sleep(0.05)
                else:
                    print(f"    [SIMULADO] moveL a destino: {target_pose}")

            elif step.move_type == "circular":
                if not step.via:
                    raise ValueError(f"El paso '{step.name}' requiere el punto intermedio 'via'.")

                via_pose = TrajectoryManager.convertir_a_pose_cartesiana(step.via, step.coord_type, rtde_ctrl)
                if route.force_constant_z and z_referencia_global is not None:
                    via_pose[2] = z_referencia_global

                ok, err = guard.validar_pose(via_pose, f"{step.name}_Via")
                if not ok:
                    raise ValueError(err)

                print(f"  > Ejecutando arco circular (moveC) pasando por punto vía...")
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

            # Si el paso tuvo escaneo activo, detener la captura inmediatamente
            if step.scan:
                print("  [*] Finalizando captura del perfilómetro (STOP)...")
                if not dry_run:
                    gocator.stop()
                else:
                    print("    [SIMULADO] Sensor Gocator -> STOP emitido.")

            print(f"  [OK] Paso '{step.name}' finalizado.")

        print(f"\n[SUCCESS] Operación de escaneo sincronizado '{route.name}' finalizada con éxito.")

    except Exception as e:
        print(f"\n[ERROR] Fallo crítico durante el escaneo sincronizado: {e}")
        # Apagar láser preventivamente por seguridad
        try:
            gocator.stop()
            print("[*] Señal de parada de emergencia enviada a Gocator.")
        except Exception:
            pass
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
    gocator_ip = os.getenv("GOCATOR_IP", "192.168.1.10")
    gocator_port = int(os.getenv("GOCATOR_PORT", 8190))

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
        print("[*] Sin argumentos de ruta. Ejecutando trayectoria de referencia por defecto del TFG.")
        route = TrajectoryManager.get_default_tfg_route()

    if args.sin_z_constante:
        route.force_constant_z = False

    ejecutar_escaneo_sincronizado(route, robot_ip, gocator_ip, gocator_port, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
