"""
Módulo de control de movimiento para el robot UR10e.
Ejecuta trayectorias parametrizadas (lineales y circulares) a partir de:
  - Archivos JSON (--json)
  - Archivos CSV (--csv)
  - Argumentos de línea de comandos (--modo cli)
  - Consola interactiva en vivo con recarga en caliente (--interactivo)
  - Trayectoria por defecto del TFG (sin argumentos)

Garantiza el forzado de altura Z constante para escaneo plano e integra
guardarraíles de seguridad espacial (UR10eSoftwareGuard).
Desacoplado al 100% de la actuación del perfilómetro láser.
"""

import os
import sys
import time
import glob
import math
import argparse
from typing import Optional, Tuple, List

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
        description="Control de movimiento para UR10e (Soporte JSON, CSV, CLI y Consola Interactiva con Hot-Reload)"
    )
    # Modos de entrada
    parser.add_argument("--json", type=str, help="Ruta a un archivo de definición JSON (ej. routes/default_tfg.json)")
    parser.add_argument("--csv", type=str, help="Ruta a un archivo tabular CSV (ej. routes/ejemplo_ruta.csv)")
    parser.add_argument("-i", "--interactivo", action="store_true", help="Iniciar consola interactiva con recarga en caliente")
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


def conectar_robot(robot_ip: str, dry_run: bool = False) -> Tuple[Optional[object], Optional[object], bool]:
    """
    Inicializa la conexión RTDE con el robot UR10e y verifica el estado de seguridad.
    Si dry_run es True o no está instalado ur_rtde, retorna modo simulación.
    """
    if dry_run or rtde_control is None:
        if rtde_control is None and not dry_run:
            print("[!] 'ur_rtde' no detectado en el entorno local. Activando modo SIMULACIÓN.")
        else:
            print("[*] Modo SIMULACIÓN activado explícitamente.")
        return None, None, True

    print(f"[*] Conectando con UR10e en {robot_ip}...")
    try:
        rtde_ctrl = rtde_control.RTDEControlInterface(robot_ip)
    except Exception as e:
        print(f"[!] Error al conectar RTDE Control con {robot_ip}: {e}")
        print("[!] Cambiando automáticamente a modo SIMULACIÓN para pruebas.")
        return None, None, True

    rtde_rec = None
    try:
        rtde_rec = rtde_receive.RTDEReceiveInterface(robot_ip)
    except Exception as e:
        print(f"[!] Advertencia: No se pudo conectar interfaz de telemetría: {e}")

    if rtde_rec:
        es_seguro, msg_seguridad = UR10eSoftwareGuard.verificar_estado_seguridad(rtde_rec)
        if not es_seguro:
            rtde_ctrl.disconnect()
            if rtde_rec:
                rtde_rec.disconnect()
            raise RuntimeError(f"Fallo de seguridad inicial en UR10e: {msg_seguridad}")
        print("[OK] Conexión RTDE establecida y estado de seguridad verificado.")

    return rtde_ctrl, rtde_rec, False


def desconectar_robot(rtde_ctrl: Optional[object], rtde_rec: Optional[object]):
    """Finaliza y desconecta limpiamente las interfaces RTDE."""
    if rtde_ctrl:
        try:
            rtde_ctrl.stopScript()
            rtde_ctrl.disconnect()
        except Exception:
            pass
        print("[*] Interfaz RTDE Control desconectada.")
    if rtde_rec:
        try:
            rtde_rec.disconnect()
        except Exception:
            pass
        print("[*] Interfaz RTDE Telemetría desconectada.")


def mover_a_origen(
    route: TrajectoryRoute,
    rtde_ctrl: Optional[object],
    rtde_rec: Optional[object],
    dry_run: bool = False
) -> bool:
    """
    Posiciona el robot en el punto de inicio de la trayectoria activa (sin ejecutar el barrido).
    Permite validar y alinear visualmente la posición previa del cabezal en el laboratorio.
    """
    if not route.steps:
        print("[!] La ruta activa no contiene pasos definidos.")
        return False

    guard = UR10eSoftwareGuard()
    first_step = route.steps[0]
    origin_spec = first_step.origin if first_step.origin is not None else first_step.target

    print(f"\n[*] Posicionando en punto de ORIGEN de '{first_step.name}'...")
    try:
        origin_pose = TrajectoryManager.convertir_a_pose_cartesiana(origin_spec, first_step.coord_type, rtde_ctrl)
        ok, err = guard.validar_pose(origin_pose, f"{first_step.name}_Origen")
        if not ok:
            print(f"[ERROR DE SEGURIDAD] {err}")
            return False

        if rtde_ctrl and not dry_run:
            rtde_ctrl.moveL(origin_pose, first_step.speed, first_step.acceleration)
            while not rtde_ctrl.isSteady():
                time.sleep(0.05)
        else:
            print(f"  [SIMULADO] moveL a pose de origen: {[round(v, 4) for v in origin_pose]}")

        print(f"[OK] Robot posicionado en origen: {[round(v, 4) for v in origin_pose]}")
        return True
    except Exception as e:
        print(f"[ERROR] Error al posicionar en origen: {e}")
        return False


def ejecutar_ruta(
    route: TrajectoryRoute,
    robot_ip: str,
    dry_run: bool = False,
    rtde_ctrl: Optional[object] = None,
    rtde_rec: Optional[object] = None,
    desconectar_al_finalizar: bool = True
) -> bool:
    """
    Ejecuta la secuencia de pasos de una trayectoria garantizando altura Z constante
    y validación previa de seguridad con UR10eSoftwareGuard.
    """
    guard = UR10eSoftwareGuard()
    sesion_propia = False

    print(f"\n{'=' * 65}")
    print(f"[*] INICIANDO EJECUCIÓN DE TRAYECTORIA: {route.name}")
    print(f"[*] Descripción: {route.description}")
    print(f"[*] Total de pasos a ejecutar: {len(route.steps)}")
    print(f"[*] Forzar Z constante: {route.force_constant_z}")
    if dry_run or (rtde_ctrl is None and rtde_control is None):
        print(f"[*] MODO: SIMULACIÓN / DRY-RUN (sin enviar comandos a robot físico)")
    print(f"{'=' * 65}")

    try:
        # Si no se pasó una conexión preexistente, conectar ahora
        if rtde_ctrl is None and not dry_run:
            rtde_ctrl, rtde_rec, dry_run = conectar_robot(robot_ip, dry_run)
            sesion_propia = True

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
                    print(f"  > Z de referencia establecida en origen: {z_referencia_global:.4f} m")

                # Validar y mover a origen
                ok, err = guard.validar_pose(origin_pose, f"{step.name}_Origen")
                if not ok:
                    raise ValueError(err)

                print(f"  > Posicionando en origen del tramo...")
                if rtde_ctrl and not dry_run:
                    rtde_ctrl.moveL(origin_pose, step.speed, step.acceleration)
                    while not rtde_ctrl.isSteady():
                        time.sleep(0.05)
                else:
                    print(f"    [SIMULADO] moveL a origen: {[round(v, 4) for v in origin_pose]}")

            # C. Aplicar forzado de Z constante si está activado
            if route.force_constant_z:
                if z_referencia_global is None:
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
                if rtde_ctrl and not dry_run:
                    rtde_ctrl.moveL(target_pose, step.speed, step.acceleration)
                    while not rtde_ctrl.isSteady():
                        time.sleep(0.05)
                else:
                    print(f"    [SIMULADO] moveL a destino: {[round(v, 4) for v in target_pose]}")

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
                if rtde_ctrl and not dry_run:
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
                    print(f"    [SIMULADO] moveC por vía: {[round(v, 4) for v in via_pose]} a destino: {[round(v, 4) for v in target_pose]}")

            print(f"  [OK] Paso '{step.name}' completado con éxito.")

        print(f"\n[SUCCESS] Toda la trayectoria '{route.name}' se completó satisfactoriamente.")
        return True

    except Exception as e:
        print(f"\n[ERROR] Error durante la ejecución del movimiento: {e}")
        return False

    finally:
        if sesion_propia and desconectar_al_finalizar:
            desconectar_robot(rtde_ctrl, rtde_rec)


def listar_archivos_rutas(directorio: str = "routes") -> List[str]:
    """Retorna la lista de archivos de trayectoria (.json y .csv) disponibles."""
    if not os.path.exists(directorio):
        return []
    patrones = [os.path.join(directorio, "*.json"), os.path.join(directorio, "*.csv")]
    encontrados = []
    for p in patrones:
        encontrados.extend(glob.glob(p))
    return sorted(encontrados)


def consola_interactiva(
    ruta_inicial: Optional[TrajectoryRoute],
    archivo_origen: Optional[str],
    tipo_origen: str,
    robot_ip: str,
    dry_run: bool = False
):
    """
    Consola interactiva REPL con conexión persistente RTDE y recarga en caliente de rutas.
    Permite modificar archivos JSON/CSV en caliente y ejecutarlos inmediatamente sin reconectar.
    """
    print("\n" + "=" * 70)
    print(" INICIALIZANDO CONSOLA INTERACTIVA DE MOVIMIENTO UR10e (TFG)")
    print("=" * 70)

    rtde_ctrl, rtde_rec, dry_run = conectar_robot(robot_ip, dry_run)
    active_route = ruta_inicial if ruta_inicial else TrajectoryManager.get_default_tfg_route()
    active_file = archivo_origen
    active_type = tipo_origen

    try:
        while True:
            estado_robot = "SIMULACIÓN / DRY-RUN" if dry_run or rtde_ctrl is None else "ONLINE (RTDE Activo)"
            nombre_archivo = active_file if active_file else "[Memoria / Trayectoria Referencia TFG]"
            z_status = "ACTIVADO (Horizontal)" if active_route.force_constant_z else "DESACTIVADO (XYZ Libre)"

            print("\n" + "=" * 70)
            print(" CONSOLA DE CONTROL CINEMÁTICO UR10e - MODO INTERACTIVO")
            print("=" * 70)
            print(f" [Robot IP]    : {robot_ip} | Estado: {estado_robot}")
            print(f" [Ruta Activa] : {active_route.name} ({nombre_archivo})")
            print(f" [Config]      : Pasos={len(active_route.steps)} | Vel={active_route.default_speed} m/s | Z Cte={z_status}")
            print("-" * 70)
            print("  [1] Ejecutar trayectoria completa en el robot")
            print("  [2] Posicionar en punto de ORIGEN / HOME (sin barrido)")
            print("  [3] Recargar ruta en caliente desde archivo (HOT-RELOAD)")
            print("  [4] Seleccionar otro archivo de ruta (.json / .csv)")
            print("  [5] Consultar estado actual del robot (TCP y Articulaciones)")
            print("  [6] Modificar parámetros al vuelo (velocidad, aceleración, Z cte)")
            print("  [0] Salir y desconectar de forma segura")
            print("=" * 70)

            try:
                opcion = input("UR10e> ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\n[*] Saliendo de la consola interactiva...")
                break

            if opcion == "1":
                print(f"\n[*] Preparando ejecución de '{active_route.name}'...")
                confirmacion = input("¿Confirmar inicio de movimiento en el robot? (s/N): ").strip().lower()
                if confirmacion in ("s", "si", "y", "yes"):
                    ejecutar_ruta(
                        active_route,
                        robot_ip,
                        dry_run=dry_run,
                        rtde_ctrl=rtde_ctrl,
                        rtde_rec=rtde_rec,
                        desconectar_al_finalizar=False
                    )
                else:
                    print("[*] Ejecución cancelada por el usuario.")

            elif opcion == "2":
                mover_a_origen(active_route, rtde_ctrl, rtde_rec, dry_run=dry_run)

            elif opcion == "3":
                if not active_file or not os.path.exists(active_file):
                    print("[!] No hay un archivo físico asociado a la ruta actual para recargar.")
                    continue
                try:
                    if active_type == "json" or active_file.endswith(".json"):
                        active_route = TrajectoryManager.from_json(active_file)
                        active_type = "json"
                    else:
                        active_route = TrajectoryManager.from_csv(active_file)
                        active_type = "csv"
                    print(f"\n[OK] ¡Ruta recargada en caliente con éxito!")
                    print(f"     Archivo  : {active_file}")
                    print(f"     Nombre   : {active_route.name}")
                    print(f"     Nº Pasos : {len(active_route.steps)}")
                    for idx, s in enumerate(active_route.steps, 1):
                        print(f"       -> Paso {idx}: {s.name} ({s.move_type.upper()}) | Target: {s.target}")
                except Exception as e:
                    print(f"[ERROR] Error al recargar el archivo '{active_file}': {e}")

            elif opcion == "4":
                archivos = listar_archivos_rutas("routes")
                print("\n--- Archivos de Trayectoria Disponibles en 'routes/' ---")
                for i, arch in enumerate(archivos, start=1):
                    tam = os.path.getsize(arch)
                    mtime = time.strftime('%H:%M:%S', time.localtime(os.path.getmtime(arch)))
                    print(f"  [{i}] {arch} ({tam} bytes, modificado: {mtime})")
                print("  [M] Introducir otra ruta de archivo manualmente")
                print("  [C] Cancelar")

                sub_op = input("\nSeleccione archivo [1-{}] o M: ".format(len(archivos))).strip()
                if sub_op.lower() == "c" or not sub_op:
                    continue

                archivo_elegido = None
                if sub_op.isdigit() and 1 <= int(sub_op) <= len(archivos):
                    archivo_elegido = archivos[int(sub_op) - 1]
                elif sub_op.lower() == "m":
                    archivo_elegido = input("Introduzca ruta al archivo (.json o .csv): ").strip()

                if archivo_elegido and os.path.exists(archivo_elegido):
                    try:
                        if archivo_elegido.endswith(".json"):
                            active_route = TrajectoryManager.from_json(archivo_elegido)
                            active_type = "json"
                        elif archivo_elegido.endswith(".csv"):
                            active_route = TrajectoryManager.from_csv(archivo_elegido)
                            active_type = "csv"
                        else:
                            print("[!] Formato no reconocido. Solo se admiten archivos .json o .csv")
                            continue
                        active_file = archivo_elegido
                        print(f"[OK] Archivo cargado con éxito: {active_file} ({len(active_route.steps)} pasos)")
                    except Exception as e:
                        print(f"[ERROR] No se pudo parsear el archivo '{archivo_elegido}': {e}")
                else:
                    if archivo_elegido:
                        print(f"[!] El archivo '{archivo_elegido}' no existe.")

            elif opcion == "5":
                print("\n--- TELEMETRÍA Y ESTADO DEL ROBOT ---")
                if rtde_rec and not dry_run:
                    try:
                        tcp = rtde_rec.getActualTCPPose()
                        q_rad = rtde_rec.getActualQ()
                        q_deg = [math.degrees(a) for a in q_rad]
                        prot = rtde_rec.isProtectiveStopped()
                        emerg = rtde_rec.isEmergencyStopped()

                        print(f"  Pose TCP [X, Y, Z] (m) : [{tcp[0]:.4f}, {tcp[1]:.4f}, {tcp[2]:.4f}]")
                        print(f"  Pose TCP [Rx, Ry, Rz]  : [{tcp[3]:.4f}, {tcp[4]:.4f}, {tcp[5]:.4f}]")
                        print("  Articulaciones (deg)   :")
                        nombres_juntas = ["Base", "Shoulder", "Elbow", "Wrist 1", "Wrist 2", "Wrist 3"]
                        for n, deg in zip(nombres_juntas, q_deg):
                            print(f"    - {n:9s}: {deg:8.2f}°")
                        print(f"  Parada de Protección  : {'SÍ (BLOQUEADO)' if prot else 'NO (Normal)'}")
                        print(f"  Parada de Emergencia  : {'SÍ (SETA PULSADA)' if emerg else 'NO (Normal)'}")
                    except Exception as e:
                        print(f"[!] Error al consultar telemetría: {e}")
                else:
                    print("  [Modo Simulación] No hay telemetría en tiempo real disponible.")
                    print("  Pose simulada TCP [X,Y,Z] : [0.0000, 0.0000, 0.0000]")

            elif opcion == "6":
                print("\n--- Modificar Parámetros de Movimiento al Vuelo ---")
                print(f"  1. Velocidad actual     : {active_route.default_speed} m/s")
                print(f"  2. Aceleración actual  : {active_route.default_acceleration} m/s^2")
                print(f"  3. Forzar Z constante   : {'ACTIVADO' if active_route.force_constant_z else 'DESACTIVADO'}")
                sub = input("¿Qué desea modificar? [1-3] o ENTER para volver: ").strip()

                if sub == "1":
                    val = input(f"Nueva velocidad (m/s) [{active_route.default_speed}]: ").strip()
                    if val:
                        active_route.default_speed = float(val)
                        for s in active_route.steps:
                            s.speed = float(val)
                        print(f"[OK] Velocidad actualizada a {active_route.default_speed} m/s.")
                elif sub == "2":
                    val = input(f"Nueva aceleración (m/s^2) [{active_route.default_acceleration}]: ").strip()
                    if val:
                        active_route.default_acceleration = float(val)
                        for s in active_route.steps:
                            s.acceleration = float(val)
                        print(f"[OK] Aceleración actualizada a {active_route.default_acceleration} m/s^2.")
                elif sub == "3":
                    active_route.force_constant_z = not active_route.force_constant_z
                    estado = "ACTIVADO" if active_route.force_constant_z else "DESACTIVADO"
                    print(f"[OK] Forzado de Z constante ahora está {estado}.")

            elif opcion == "0":
                print("\n[*] Saliendo de la consola...")
                break
            else:
                print("[!] Opción no reconocida. Ingrese un número entre 0 y 6.")

    finally:
        desconectar_robot(rtde_ctrl, rtde_rec)
        print("[*] Sesión interactiva finalizada limpiamente.")


def cargar_env():
    """Carga variables desde el archivo .env si existen y no están en el entorno."""
    for ruta in [".env", os.path.join(os.path.dirname(__file__), "..", ".env")]:
        if os.path.exists(ruta):
            with open(ruta, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip('"').strip("'")
                        if k not in os.environ:
                            os.environ[k] = v
            break


def main():
    cargar_env()
    args = parse_arguments()
    robot_ip = os.getenv("ROBOT_IP", "192.168.1.224")

    route: Optional[TrajectoryRoute] = None
    archivo_origen: Optional[str] = None
    tipo_origen: str = "default"

    # 1. Determinar fuente de la trayectoria
    if args.json:
        route = TrajectoryManager.from_json(args.json)
        archivo_origen = args.json
        tipo_origen = "json"
    elif args.csv:
        route = TrajectoryManager.from_csv(args.csv)
        archivo_origen = args.csv
        tipo_origen = "csv"
    elif args.modo == "cli" and args.destino:
        setattr(args, "forzar_z", not args.sin_z_constante)
        route = TrajectoryManager.from_cli(args)
        tipo_origen = "cli"
    else:
        # Trayectoria de referencia por defecto del TFG
        archivo_default = "routes/default_tfg.json"
        if os.path.exists(archivo_default):
            route = TrajectoryManager.from_json(archivo_default)
            archivo_origen = archivo_default
            tipo_origen = "json"
        else:
            route = TrajectoryManager.get_default_tfg_route()
            tipo_origen = "default"

    if args.sin_z_constante and route:
        route.force_constant_z = False

    # 2. Decisión de modo de ejecución: Consola Interactiva o Modo Batch
    # Se entra en consola interactiva si:
    #   - Se pasa explícitamente el flag --interactivo (-i)
    #   - O bien no se especificaron argumentos directos y estamos en una terminal de usuario (TTY)
    iniciar_consola = args.interactivo or (len(sys.argv) == 1 and sys.stdin.isatty())

    if iniciar_consola:
        consola_interactiva(
            ruta_inicial=route,
            archivo_origen=archivo_origen,
            tipo_origen=tipo_origen,
            robot_ip=robot_ip,
            dry_run=args.dry_run
        )
    else:
        # Modo One-Shot (Batch / CI / Automatización)
        if route is None:
            route = TrajectoryManager.get_default_tfg_route()
        ejecutar_ruta(route, robot_ip, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
