# Registro de Trabajo - Día 8
## Arquitectura Modular de Control UR10e, Nombrado Incremental PointN, Cálculo Experimental por Offset XYZ y Optimización

### 1. Objetivos del Día
- Sustituir la arquitectura monolítica experimental anterior por un sistema modular puro en Python, altamente mantenible, desacoplado y orientado a la operación en planta/laboratorio con el brazo robótico **Universal Robots UR10e**.
- Eliminar scripts redundantes, rutas antiguas (`routes/`) y tests obsoletos (`tests/`), manteniendo la documentación histórica intacta en `doc/`.
- Diseñar un **Orquestador Central CLI** ([`src/main.py`](file:///c:/Users/Santi/Documents/GITHUB/TFG/src/main.py)) con menú interactivo no bloqueante.
- Implementar **parada de emergencia en tiempo real** durante movimientos lineales (`moveL`), permitiendo frenar el brazo al pulsar `[ENTER]` o `[ESPACIO]`.
- Desarrollar el modo de guiado manual libre (**Teach Mode / Freedrive**) con fijación de posición y persistencia guiada de poses TCP.
- Implementar gestión dinámica de múltiples archivos de puntos `.json` y asignación automática de etiquetas incrementales con formato **`PointN`** (`Point1`, `Point2`...).
- Incorporar un módulo cinemático experimental para el **cálculo de punto final aplicando offsets XYZ** relativos a las dimensiones de la pieza.
- Optimizar la serialización JSON de puntos reduciendo drásticamente el peso de los archivos generados y proteger la configuración de movimiento en modo solo lectura (`:ro`).
- Desacoplar las dependencias del perfilómetro Gocator en este repositorio, focalizándolo en el control cinemático del UR10e.

---

### 2. Arquitectura Modular Implementada (`src/`)

Se estableció una separación estricta de responsabilidades en 8 módulos independientes:

```text
src/
├── main.py              # Orquestador del menú interactivo por consola (CLI)
├── check_pose.py        # Consulta en tiempo real de la pose TCP (RTDE y socket 30003)
├── config_manager.py    # Carga protegida de perfiles de dinámica (movement/scan)
├── keyboard_listener.py # Detección no bloqueante de teclas de emergencia (ENTER / ESPACIO)
├── move_to_point.py     # Ejecución supervisada de moveL con frenado stopL inmediato
├── teach_mode.py        # Modo guiado manual libre (teachMode y endTeachMode)
├── points_manager.py    # Serialización compacta, gestión de archivos y nombrado PointN
└── offset_calculator.py # Cálculo cinemático por desplazamiento de pieza XYZ (Experimental)
```

#### 2.1. Orquestador Central (`src/main.py`)
Coordina el flujo de trabajo ofreciendo una interfaz interactiva por terminal. Muestra en el banner superior el archivo de posiciones activo en caliente y canaliza las 8 opciones disponibles:
1. `[1]` Listar puntos disponibles en el archivo activo.
2. `[2]` Comprobar pose TCP actual del robot.
3. `[3]` Mover el robot a un punto guardado con selección de dinámica.
4. `[4]` Modo guiado manual libre (Teach Mode).
5. `[5]` Almacenar posición actual en el archivo activo.
6. `[6]` Seleccionar / Cambiar archivo de posiciones activo.
7. `[7]` Calcular punto final por offset XYZ (Experimental).
8. `[8]` Salir de forma limpia liberando conexiones.

Permite opcionalmente especificar el archivo de puntos por argumento de lanzamiento (`python src/main.py ruta.json`) o mediante la variable de entorno `POINTS_FILE`.

#### 2.2. Parada de Emergencia Multiplataforma (`src/keyboard_listener.py` y `src/move_to_point.py`)
- Para garantizar la máxima seguridad en laboratorio, el movimiento `moveL` se ejecuta en modo asíncrono (`rtde_ctrl.moveL(pose, speed, accel, asynchronous=True)`).
- En paralelo, un hilo demonio ejecuta `escuchar_parada()`:
  - En **Windows**: utiliza `msvcrt.kbhit()` y `msvcrt.getch()`.
  - En **Linux / Docker (TTY interactivo)**: conmuta temporalmente la terminal a modo cbreak mediante `termios` y `tty.setcbreak(fd)` con lectura no bloqueante vía `select.select([sys.stdin], [], [], 0.05)`.
- Si el usuario presiona `[ENTER]` o `[ESPACIO]`, se dispara un `threading.Event`, deteniendo el bucle de interpolación e invocando inmediatamente `rtde_ctrl.stopL(10.0)`.

#### 2.3. Guiado Manual Libre (`src/teach_mode.py`)
- Activa `rtde_ctrl.teachMode()`, desengranando los frenos articulares del UR10e para permitir mover el efector con la mano.
- Al pulsar `[ENTER]`, invoca `rtde_ctrl.endTeachMode()`, bloqueando los frenos en la nueva postura.
- Lee de forma inmediata la nueva pose TCP resultante vía telemetría y ofrece al operador guardarla directamente en el archivo activo de puntos.

#### 2.4. Gestión Dinámica y Nombrado Incremental `PointN` (`src/points_manager.py`)
- **Nombrado Automático:** Si el usuario no introduce una etiqueta al guardar una posición, la función `generar_siguiente_nombre_punto()` evalúa las claves existentes con la expresión regular `^Point(\d+)$`, extrae los índices numéricos y genera automáticamente `PointN` con $N = \max(numeros) + 1$.
- **Conmutación en Caliente:** Permite cambiar el archivo activo sobre la marcha entre diferentes configuraciones en la carpeta `points/` o crear nuevos archivos estructurados al vuelo.
- **Edición en Caliente:** Gracias a la lectura directa de disco en cada acción, los archivos `.json` pueden ser editados externamente tanto con el contenedor en marcha como en parado.

#### 2.5. Cálculo Experimental por Offset de Pieza (`src/offset_calculator.py`)
- Permite calcular una nueva posición final aplicando algebraicamente desplazamientos en los tres ejes cartesianos ($\Delta X, \Delta Y, \Delta Z$) respecto a una pieza o referencia:
  $$X_{final} = X_{origen} + \Delta X, \quad Y_{final} = Y_{origen} + \Delta Y, \quad Z_{final} = Z_{origen} + \Delta Z$$
- Mantiene intacta la orientación de la herramienta ($Rx, Ry, Rz$) y redondea a 6 decimales.
- Evalúa la distancia tridimensional euclídea total:
  $$d = \sqrt{\Delta X^2 + \Delta Y^2 + \Delta Z^2}$$
- Incorpora una comprobación de seguridad que avisa al operador si $\Delta Z \neq 0$ para evitar colisiones o descalibraciones en el plano focal de trabajo.

#### 2.6. Gestión Protegida de Configuración (`src/config_manager.py`)
- Centraliza la lectura de perfiles cinemáticos en `config/movement_config.json`:
  - `movement`: $v = 0.05\text{ m/s}, a = 0.2\text{ m/s}^2$ (movimientos generales).
  - `scan`: $v = 0.008\text{ m/s}, a = 0.1\text{ m/s}^2$ (movimientos lentos y estables).
- No expone métodos de escritura, asegurando que las velocidades y aceleraciones máximas permanezcan inalteradas.

---

### 3. Optimizaciones de Rendimiento y Reducción de Tamaño

#### 3.1. Serialización Compacta de Puntos (`points/points.json`)
- Se implementó `serializar_puntos_compacto()` para imprimir los vectores `pose` en una única línea JSON continua:
  ```json
  "origin": {
    "description": "Reference origin point for TFG scans",
    "pose": [-0.46213, -0.103808, 0.169564, 1.8092, 1.901, 0.5625]
  }
  ```
- **Resultados:**
  - Reducción de **70 líneas a 29 líneas** en `points.json` (**-58.6%**).
  - Reducción de peso en disco de **1.261 bytes a 954 bytes** (**-24.3%**).

#### 3.2. Infraestructura Docker e Inmutabilidad de Configuración
- **`.dockerignore`:** Creado para excluir `.git`, documentación `doc/`, cachés `__pycache__` y archivos temporales del contexto de compilación.
- **Protección `:ro`:** El volumen de configuración en `docker-compose.yml` se configuró en modo de solo lectura:
  ```yaml
  volumes:
    - ./src:/app/src
    - ./config:/app/config:ro
    - ./points:/app/points
  ```
- **CMD por defecto:** Actualizado en `Dockerfile` a `python src/main.py`.

---

### 4. Guía de Ejecución en Planta / Laboratorio

Para lanzar el sistema en el computador embarcado (IPC) del Robotnik o en un equipo conectado a la red del robot:

```bash
docker compose run --rm ur10e-control
```

*El parámetro `--rm` garantiza la recolección automática del contenedor al finalizar la sesión interactiva.*

---

### 5. Resumen de Commits Realizados en el Día

| Hash | Mensaje de Commit | Alcance Principal |
| :--- | :--- | :--- |
| `b00ba9e` | `refactor(control): modularize UR10e system with interactive CLI orchestrator` | Nueva arquitectura en `src/`, eliminación de código monolítico y setup Docker. |
| `e40f246` | `feat(kinematics): add experimental piece offset XYZ calculator` | Creación de `offset_calculator.py` e integración en el menú. |
| `675787b` | `docs: update GEMINI.md project architecture and add RTDE documentation reference` | Actualización de directrices y enlaces de referencia API. |
| `d7a1f25` | `docs: rewrite README with full CLI user guide, Docker commands, and option outputs` | Manual de usuario exhaustivo con salidas completas por opción. |
| `e6967d5` | `docs(readme): decouple Gocator profilometer references from documentation and code` | Desacoplamiento del perfilómetro de la documentación principal. |
| `1653f3d` | `docs(readme): simplify execution guide to interactive Docker command` | Reducción de la guía de ejecución a `docker compose run --rm`. |
| `59a6754` | `docs(readme): document hot-reload and offline editing of points.json` | Mención explícita a la edición en caliente y en parado de puntos. |
