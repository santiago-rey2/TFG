# Proyecto TFG: Análisis de datos de perfilómetro Gocator 2600 y Robot UR10e

## Contexto del Estudiante
Este proyecto está siendo desarrollado por un estudiante de 4º curso de Ingeniería Informática como parte de su Trabajo de Fin de Grado (TFG).

## Descripción del Proyecto
El objetivo principal es el análisis de los datos obtenidos mediante el escaneo de un perfilómetro de masas **Gocator 2600** integrado en un brazo robótico **UR10e**.

## Estado Actual (Abril 2026)
- **Plataforma y Hardware:**
    - El brazo robótico **UR10e** y el perfilómetro **Gocator 2600** están montados sobre una plataforma móvil **Robotnik**.
    - El computador industrial embarcado (**Onboard IPC del Robotnik**) actúa como nodo central y enlace exclusivo, comunicándose instantáneamente con ambos dispositivos a través de su red interna Gigabit Ethernet.
- **Comunicación:**
    - Se utiliza el protocolo **ur_rtde** para interactuar con el UR10e (puerto 30004 y telemetría 30003).
    - Protocolo de comandos ASCII TCP/IP para el perfilómetro Gocator (puerto 8190).
- **Arquitectura Modular de Control (`src/`):**
    - `main.py`: Orquestador principal interactivo que coordina todos los módulos y centraliza de forma exclusiva la carga de configuración y variables de entorno (`ARM_IP`, `GOCATOR_IP`, `POINTS_FILE`).
    - `arm_connection.py`: Centralización de conexión RTDEControl con el brazo UR10e (`conexion_control`) y ejecución de trayectorias lineales `moveL` con parada de emergencia en tiempo real (`mover_lineal_con_parada`).
    - `points_manager.py`: Carga, gestión, selección dinámica y serialización compacta de archivos de puntos (`points/*.json`) con nombrado automático/incremental (`PointN`).
    - `config_manager.py`: Carga y selección dinámica de perfiles de dinámica de movimiento (`config/movement_config.json`).
    - `keyboard_listener.py`: Captura multiplataforma de pulsaciones ([ENTER] / [ESPACIO]) para paradas de emergencia en tiempo real sin bloquear la ejecución.
    - `check_pose.py`: Consulta en tiempo real de la pose TCP actual del UR10e (RTDE y socket 30003).
    - `move_to_point.py`: Selección de punto objetivo y delegación de trayectoria lineal hacia `arm_connection`.
    - `teach_mode.py`: Activación y desactivación del modo guiado manual libre (`teachMode` y `endTeachMode`) con opción de guardado directo.
    - `offset_calculator.py`: Cálculo experimental de puntos finales aplicando desplazamientos relativos (offsets XYZ) a partir de una pose TCP origen.
    - `scan_between_points.py`: Movimiento lineal hacia un punto objetivo desde la pose actual con escaneo sincronizado en segundo plano mediante perfilómetro Gocator 2600 (`gocator-py` / `ProfileScan`) y persistencia directa en volumen `scans/`.
- **Infraestructura Docker:**
    - Imágenes multi-stage optimizadas en **Python 3.12-slim** (~220 MB) para compatibilidad con `gocator-py` y `numpy>=2.0.0` sin saturar el almacenamiento del IPC del Robotnik.
    - Orquestación mediante `docker-compose` con soporte TTY para sesiones interactivas desacopladas.
    - Configuración de red mediante archivo `.env` (ignorado en git).

## Coordenadas de Referencia (TFG)
| Articulación | Origen (°) | Fin (°) |
| :--- | :--- | :--- |
| Base | -143.03 | -57.92 |
| Shoulder | -62.89 | -68.94 |
| Elbow | 81.82 | 88.45 |
| Wrist 1 | -110.44 | -113.97 |
| Wrist 2 | -92.18 | -88.96 |
| Wrist 3 | 0.00 | 0.03 |

## Directrices de Desarrollo
- **Seguridad:** El archivo `.env` no debe subirse al repositorio.
- **Precisión:** Cualquier modificación en la trayectoria debe validar que la altura (Z) se mantenga constante si el escaneo lo requiere.
- **Documentación:** Mantener registros de los escaneos y hallazgos en la carpeta `doc/`.
