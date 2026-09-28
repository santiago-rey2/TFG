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
- **Scripts de Control (`src/`):**
    - `robot_status.py`: Consulta telemetría en tiempo real (articulaciones, pose TCP y temperaturas).
    - `robot_movement.py`: Control cinemático independiente con consola interactiva y recarga en caliente (*hot-reload*) de rutas JSON/CSV.
    - `gocator.py`: Actuación independiente del láser (comandos CLI, barridos temporizados y consola interactiva).
    - `robot_check_connection.py`: Diagnóstico rápido multi-puerto (29999, 30003, 30004, 6080, 8190).
- **Lógica de Trayectoria:**
    - Carga dinámica desde archivos JSON y CSV en `routes/`.
    - **Movimiento Plano:** Forzado automático de altura Z constante para escaneos horizontales.
- **Infraestructura Docker:**
    - Imágenes ultra ligeras optimizadas a **216 MB** (~75 MB comprimidas en tar.gz) para no saturar el almacenamiento del IPC del Robotnik.
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
