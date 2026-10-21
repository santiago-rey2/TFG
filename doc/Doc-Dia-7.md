# Registro de Trabajo - Día 7
## Desacoplamiento de Procesos y Consola Interactiva con Carga en Caliente

### 1. Objetivos del Día
- Simplificar temporalmente la arquitectura para facilitar pruebas de laboratorio y calibración.
- Separar la ejecución en dos archivos 100% independientes:
  - Movimiento del brazo robótico UR10e ([`src/robot_movement.py`](../src/robot_movement.py)).
  - Actuación del perfilómetro láser Gocator 2600 ([`src/gocator.py`](../src/gocator.py)).
- Mantener la carga dinámica de coordenadas y rutas desde archivos JSON y CSV.
- Implementar **Modo Consola Interactiva (Opción C)** con recarga en caliente (*hot-reload*) de archivos sin necesidad de reconectar la sesión RTDE del robot.

---

### 2. Implementación Realizada

#### 2.1. Movimiento del Brazo (`src/robot_movement.py`)
- **Desacoplamiento total:** Eliminada cualquier dependencia de red o socket con el sensor Gocator.
- **Consola Interactiva:** Al ejecutarse con `-i` / `--interactivo` (o por defecto en terminal interactiva), mantiene la sesión RTDE abierta y ofrece el menú:
  - `[1]` Ejecutar trayectoria completa en el robot.
  - `[2]` Posicionar en punto de ORIGEN / HOME (sin barrido, para comprobar alineación).
  - `[3]` Recargar ruta en caliente desde el archivo actual (Hot-Reload de cambios guardados en el JSON/CSV).
  - `[4]` Seleccionar otro archivo de ruta (explora la carpeta `routes/`).
  - `[5]` Consultar estado actual del robot (pose cartesiana TCP y ángulos de juntas).
  - `[6]` Modificar parámetros al vuelo (velocidad, aceleración, forzado de $Z$ constante).
  - `[0]` Salir y desconectar de forma segura.
- **Modo Batch / CLI:** Si se pasa `--json <archivo>` o `--csv <archivo>` sin `-i`, ejecuta la trayectoria de forma directa (one-shot).

#### 2.2. Actuación del Sensor Láser (`src/gocator.py`)
- **Independiente del robot:** Sin importaciones ni dependencias de `ur_rtde`.
- **Comandos directos por CLI:**
  - `python src/gocator.py --cmd start`: Enciende el láser y comienza adquisición.
  - `python src/gocator.py --cmd stop`: Apaga el láser y detiene adquisición.
  - `python src/gocator.py --cmd trigger`: Disparo por software (Surface Trigger).
  - `python src/gocator.py --sweep 30`: Barrido temporizado con cuenta atrás y parada segura con `Ctrl+C`.
  - `python src/gocator.py --status`: Comprueba disponibilidad de socket y latencia de red.
- **Consola Interactiva (`-i` / `--interactivo`):** Menú rápido para enviar comandos y alternar estado del sensor en vivo.

#### 2.3. Infraestructura Docker
- Se añadieron las directivas `stdin_open: true` y `tty: true` en `docker-compose.yml` para los servicios `movement` y `gocator`, permitiendo operar las consolas interactivas desde contenedores.

---

### 3. Guía Rápida de Uso en el Laboratorio

#### Terminal 1: Control del Robot UR10e
```bash
# Lanzar la consola interactiva con la trayectoria por defecto:
python src/robot_movement.py -i

# O cargar directamente un archivo JSON específico en modo interactivo:
python src/robot_movement.py -i --json routes/default_tfg.json
```
*Si se editan las coordenadas en `routes/default_tfg.json` desde VS Code, basta con pulsar `[3]` en la consola para recargar en caliente y `[1]` para mover el robot sin esperas de reconexión.*

#### Terminal 2: Control del Perfilómetro Gocator
```bash
# Opción A: Consola interactiva del sensor
python src/gocator.py -i

# Opción B: Disparo de barrido de 30 segundos
python src/gocator.py --sweep 30

# Opción C: Encendido y apagado manual
python src/gocator.py --cmd start
# ... realizar pruebas visuales o de escaneo ...
python src/gocator.py --cmd stop
```

---

### 4. Pruebas de Conexión con Emulador URSim (`192.168.1.224`)

Se realizaron pruebas de conexión exhaustivas contra el emulador URSim en la red local (`192.168.1.224`), obteniendo **100% de éxito en todos los canales**:

| Puerto | Protocolo / Servicio | Estado | Resultado Obtenido |
| :--- | :--- | :--- | :--- |
| **29999** | Dashboard Server | **ABIERTO / OK** | Polyscope 5.25.1, Robotmode: RUNNING, Safetystatus: NORMAL, Remote Control: `true`. |
| **30003** | Real-Time Client (500 Hz) | **ABIERTO / OK** | Telemetría real recibida. Articulaciones actuales: `[0°, -90°, 0°, -90°, 0°, 0°]`. Pose TCP: `[0.0, -0.3329, 1.0794] m`. |
| **30004** | RTDE Control / Telemetry | **ABIERTO / OK** | Conexión RTDE nativa operativa desde contenedor Docker (`status` y `movement`). Temperaturas leídas: `[25.5, 25.0, 24.5, 24.0, 23.5, 23.0] °C`. |
| **6080** | Web Pendant (noVNC) | **ABIERTO / OK** | Interfaz Web HTTP 200 OK accesible en `http://192.168.1.224:6080`. |

#### Herramientas de Verificación Disponibles:
1. **Script de Diagnóstico Rápido:**
   ```bash
   python src/robot_check_connection.py --ip 192.168.1.224
   ```
2. **Telemetría Automática con Fallback Socket:**
   ```bash
   python src/robot_status.py
   ```
3. **Ejecución RTDE Nativa en Docker:**
   ```bash
   docker compose run --rm status
   ```

   https://sdurobotics.gitlab.io/ur_rtde/pages/reference/api.html
