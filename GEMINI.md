# Proyecto TFG: Análisis de datos de perfilómetro Gocator 2600 y Robot UR10e

## Contexto del Estudiante
Este proyecto está siendo desarrollado por un estudiante de 4º curso de Ingeniería Informática como parte de su Trabajo de Fin de Grado (TFG).

## Descripción del Proyecto
El objetivo principal es el análisis de los datos obtenidos mediante el escaneo de un perfilómetro de masas **Gocator 2600** integrado en un brazo robótico **UR10e**.

## Estado Actual (Abril 2026)
- **Comunicación:** Se utiliza el protocolo **ur_rtde** para interactuar con el UR10e.
- **Scripts de Control (`src/`):**
    - `robot_status.py`: Consulta el estado actual del robot (articulaciones y pose TCP).
    - `robot_movement.py`: Ejecuta una trayectoria lineal (`moveL`) entre coordenadas de origen y fin específicas.
- **Lógica de Trayectoria:**
    - Se utilizan coordenadas en grados (convertidas a radianes en el script).
    - **Movimiento Plano:** El script de movimiento sobreescribe automáticamente la coordenada Z del destino con la del origen para garantizar que el desplazamiento sea perfectamente horizontal.
- **Infraestructura:**
    - El proyecto está dockerizado para asegurar la compatibilidad de dependencias (`cmake`, `boost`).
    - Se utiliza `docker-compose` para orquestar los servicios `status` y `movement`.
    - La configuración de la red (IP del robot) se gestiona mediante un archivo `.env` (ignorado en git).

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
