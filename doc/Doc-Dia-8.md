# Registro de Trabajo - Día 8
## Arquitectura Modular de Control UR10e, Librerías, Métodos `ur_rtde`, Features y Optimización

---

### 1. Contexto, Motivación y Refactorización Arquitectónica

Durante las primeras fases de pruebas en laboratorio (Días 1 a 7), el software creció a través de prototipos experimentales y scripts monolíticos (`robot_movement.py`, `robot_status.py`, `scan_sync.py`, `gocator.py`, `trajectory_manager.py`). Aunque permitieron validar el hardware y la comunicación física con el emulador URSim y el robot físico, acumulaban varios problemas de diseño:

1. **Acoplamiento cruzado de responsabilidades:** La lógica de cinemática, la lectura de telemetría, la gestión de ficheros JSON/CSV y la captura de teclado estaban mezcladas dentro de los mismos bucles de ejecución.
2. **Falta de modularidad y difícil mantenimiento:** Añadir una nueva funcionalidad (como el guiado manual o el cálculo de offsets) requería modificar archivos de cientos de líneas con riesgo de regresión en las pruebas de movimiento.
3. **Bloqueo en llamadas de movimiento:** Las trayectorias se ejecutaban de forma síncrona, imposibilitando la parada de emergencia en tiempo real sin tener que matar el proceso o pulsar la seta física del robot.
4. **Desacoplamiento del sensor:** Se tomó la decisión de separar completamente el control cinemático del UR10e de la actuación del perfilómetro láser Gocator en este repositorio, manteniendo este proyecto centrado al 100% en el posicionamiento y movimiento de precisión del robot.

Por estos motivos, en el **Día 8** se ejecutó una **refactorización integral**:
- **Eliminación limpia de código obsoleto:** Se eliminaron los scripts monolíticos antiguos y las carpetas `routes/` y `tests/`.
- **Estructura Modular (`src/`):** Descomposición funcional en **8 módulos independientes**, cada uno con una responsabilidad única y aislada.
- **Orquestador CLI Interactivo:** Un punto de entrada único ([`src/main.py`](file:///c:/Users/Santi/Documents/GITHUB/TFG/src/main.py)) que canaliza todas las funciones sin reinicios de sesión.

---

### 2. Librerías Implementadas y Justificación Técnica

Cada librería utilizada en la arquitectura ha sido seleccionada con un propósito específico de bajo nivel:

| Librería / Módulo | Origen | Justificación Técnica de Implementación |
| :--- | :--- | :--- |
| **`ur_rtde`** (`RTDEControlInterface`, `RTDEReceiveInterface`) | Externa (`pip install ur_rtde==1.6.3`) | Protocolo oficial de Universal Robots para comunicación a **500 Hz** en el puerto de tiempo real **30004**. Proporciona una interfaz C++ compilada con bindings de Python para control determinista de trayectoria (`moveL`), parada controlada (`stopL`), telemetría de alta resolución y activación de modo guiado manual (`teachMode`). Evita tener que implementar sockets TCP en bruto y parsear paquetes binarios propietarios de PolyScope. |
| **`socket` y `struct`** | Estándar de Python | Se implementan en `check_pose.py` como mecanismo de **fallback de emergencia** leyendo directamente el flujo de telemetría a 125/500 Hz del puerto **30003** (Real-Time Client). Permite inspeccionar la pose del robot en entornos donde `ur_rtde` no esté compilado localmente sin levantar el controlador C++. |
| **`threading`** | Estándar de Python | Permite lanzar el detector de teclado en un **hilo paralelo en segundo plano (`daemon=True`)** mientras el hilo principal monitoriza el movimiento asíncrono del robot en el bucle RTDE. Ambas tareas se comunican mediante un objeto `threading.Event()` de coste atómico. |
| **`msvcrt`** | Estándar (Windows) | Proporciona detección no bloqueante de pulsaciones de teclado (`msvcrt.kbhit()`) y lectura del carácter (`msvcrt.getch()`) en sistemas Windows sin pausar la ejecución del hilo. |
| **`termios`, `tty` y `select`** | Estándar (Linux / POSIX) | En entornos Linux y contenedores Docker con terminal TTY interactiva (`tty: true`), permite conmutar `sys.stdin` a **modo *cbreak*** (`tty.setcbreak`). Esto permite que `select.select([sys.stdin], [], [], 0.05)` capture pulsaciones inmediatas de `[ENTER]` o `[ESPACIO]` sin esperar a un retorno de carro ni bloquear el hilo. |
| **`python-dotenv`** | Externa (`pip install python-dotenv`) | Carga desacoplada de la dirección IP (`ROBOT_IP`) desde el archivo de configuración de entorno `.env` en la raíz del proyecto, garantizando que ninguna IP de laboratorio quede fijada en el código fuente. |
| **`json` y `re`** | Estándar de Python | `re` implementa el análisis de expresiones regulares (`^Point(\d+)$`) para el cálculo incremental del nombrado automático. `json` gestiona la carga y la serialización compacta en disco. |
| **`math`** | Estándar de Python | Se emplea en `offset_calculator.py` para calcular la norma euclídea tridimensional de desplazamiento ($d = \sqrt{\Delta X^2 + \Delta Y^2 + \Delta Z^2}$) y reportar la distancia 3D resultante. |

---

### 3. Funciones de `ur_rtde` Utilizadas y Análisis de Funcionamiento

A continuación se detallan las funciones de la API de Universal Robots implementadas, su comportamiento interno y la justificación de su uso:

#### 3.1. `RTDEReceiveInterface.getActualTCPPose()`
- **Qué hace:** Interroga el canal de telemetría RTDE y devuelve una lista de 6 números de coma flotante en doble precisión: `[X, Y, Z, Rx, Ry, Rz]`.
  - `X, Y, Z`: Coordenadas de posición del Tool Center Point (TCP) respecto al sistema de coordenadas de la base del robot (en metros).
  - `Rx, Ry, Rz`: Vector de rotación eje-ángulo (en radianes), donde la dirección del vector define el eje de rotación y su magnitud $\|\vec{R}\|$ define el ángulo girado.
- **Por qué se usa:** Es la función más precisa y de menor latencia para conocer la localización espacial real de la herramienta en cualquier instante.
- **Módulos donde se usa:** [`check_pose.py`](file:///c:/Users/Santi/Documents/GITHUB/TFG/src/check_pose.py), [`teach_mode.py`](file:///c:/Users/Santi/Documents/GITHUB/TFG/src/teach_mode.py), [`points_manager.py`](file:///c:/Users/Santi/Documents/GITHUB/TFG/src/points_manager.py).

#### 3.2. `RTDEControlInterface.moveL(pose, speed, acceleration, asynchronous=True)`
- **Qué hace:** Envía al controlador de movimiento del UR10e una orden de interpolación lineal en el espacio cartesiano. La herramienta se desplaza en línea recta desde su pose actual hasta `pose` con la velocidad máxima y aceleración especificadas.
- **Por qué el parámetro `asynchronous=True` es crítico:**
  - En modo síncrono (`asynchronous=False`), la llamada a `moveL` bloquea el hilo de Python hasta que el robot finaliza físicamente el movimiento. Durante ese tiempo, **Python queda congelado**, haciendo imposible detectar pulsaciones de teclado o reaccionar a emergencias.
  - Al activar `asynchronous=True`, `moveL` entrega la trayectoria al planificador cinemático del robot y devuelve inmediatamente el control al programa Python, permitiendo ejecutar un bucle de supervisión en tiempo real.
- **Módulos donde se usa:** [`move_to_point.py`](file:///c:/Users/Santi/Documents/GITHUB/TFG/src/move_to_point.py).

#### 3.3. `RTDEControlInterface.isSteady()`
- **Qué hace:** Consulta al controlador si el brazo se encuentra actualmente quieto (velocidad y aceleración nulas en todas sus articulaciones).
- **Por qué se usa:** Al operar en modo asíncrono, se utiliza como condición de parada del bucle de supervisión (`while not rtde_ctrl.isSteady():`). Permite saber de manera determinista cuándo el robot ha terminado su trayectoria sin recurrir a cálculos imprecisos de tiempo (`time.sleep`).
- **Módulos donde se usa:** [`move_to_point.py`](file:///c:/Users/Santi/Documents/GITHUB/TFG/src/move_to_point.py).

#### 3.4. `RTDEControlInterface.stopL(deceleration)`
- **Qué hace:** Detiene de forma controlada el movimiento lineal del robot aplicando la desaceleración máxima en $m/s^2$ pasada por parámetro (se utiliza `10.0` $m/s^2$).
- **Por qué se usa:** A diferencia de una parada de emergencia por desconexión de relé o corte eléctrico (que dispara los frenos mecánicos bruscamente desgastando las reductoras armónicas), `stopL` utiliza los servomotores para frenar suavemente pero en cuestión de milisegundos, manteniendo el robot alimentado y en posición fija.
- **Módulos donde se usa:** [`move_to_point.py`](file:///c:/Users/Santi/Documents/GITHUB/TFG/src/move_to_point.py).

#### 3.5. `RTDEControlInterface.teachMode()` y `endTeachMode()`
- **Qué hace:**
  - `teachMode()`: Activa el algoritmo interno de compensación de gravedad y modelo dinámico del UR10e, desengranando los frenos para que el usuario pueda mover el brazo con la mano libremente (Freedrive).
  - `endTeachMode()`: Desactiva el modo de guiado manual y restablece el control activo de posición en las articulaciones.
- **Por qué se usa:** Permite calibrar posiciones físicas complejas en planta llevando la herramienta manualmente sobre la pieza y guardando el punto exacto sin tener que estimar coordenadas numéricas a ciegas.
- **Módulos donde se usa:** [`teach_mode.py`](file:///c:/Users/Santi/Documents/GITHUB/TFG/src/teach_mode.py).

#### 3.6. `RTDEControlInterface.stopScript()`
- **Qué hace:** Finaliza la ejecución del hilo secundario de control (*control script*) que `ur_rtde` inyecta en el robot para comunicarse.
- **Por qué se usa:** Se ubica en los bloques `finally` de cada módulo para asegurar que, tanto si el script termina con éxito como si se produce una excepción, la conexión quede liberada y el controlador PolyScope del UR10e no quede bloqueado para sesiones posteriores.
- **Módulos donde se usa:** [`move_to_point.py`](file:///c:/Users/Santi/Documents/GITHUB/TFG/src/move_to_point.py), [`teach_mode.py`](file:///c:/Users/Santi/Documents/GITHUB/TFG/src/teach_mode.py).

---

### 4. Detalle Técnico Módulo por Módulo, Código y Salidas CLI

A continuación se desglosan los 8 módulos desarrollados en [`src/`](file:///c:/Users/Santi/Documents/GITHUB/TFG/src), explicando su código fuente, su algoritmo interno y las salidas reales obtenidas en la consola.

---

#### 4.1. Módulo Orquestador Central: `src/main.py`
Es el punto de entrada principal. Configura las rutas del entorno (`sys.path`), inicializa las variables de red desde `.env`, y ejecuta el bucle de eventos que ofrece el menú interactivo con las 8 opciones del sistema.

```python
# Extracto representativo de src/main.py
def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    load_dotenv(dotenv_path=os.path.join(base_dir, ".env"))
    robot_ip = os.getenv("ROBOT_IP", "192.168.1.210")

    if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
        set_puntos_path(sys.argv[1])
    elif os.getenv("POINTS_FILE"):
        set_puntos_path(os.getenv("POINTS_FILE"))

    config = cargar_config_movimiento()

    while True:
        archivo_activo = get_nombre_archivo_puntos()
        print("\n" + "=" * 55)
        print("          ORQUESTADOR DE CONTROL UR10e")
        print(f"  Archivo de posiciones activo: {archivo_activo}")
        print("=" * 55)
        # Presentación de opciones [1-8]
```

**Salida en consola al iniciar:**
```text
=======================================================
          ORQUESTADOR DE CONTROL UR10e
  Archivo de posiciones activo: points/points.json
=======================================================
  [1] Listar puntos disponibles
  [2] Comprobar pose TCP actual del robot
  [3] Mover el robot a un punto
  [4] Modo guiado manual libre (Teach Mode)
  [5] Almacenar posición actual
  [6] Seleccionar / Cambiar archivo de posiciones
  [7] Calcular punto final por offset XYZ (Experimental)
  [8] Salir
-------------------------------------------------------
Elige una opción [1-8]: 
```

---

#### 4.2. Módulo de Inspección de Pose: `src/check_pose.py`
Implementa una doble vía de consulta de la pose TCP actual:
1. **Primaria:** `RTDEReceiveInterface(robot_ip).getActualTCPPose()`.
2. **Fallback:** Conexión directa mediante `socket` TCP al puerto `30003`, leyendo el paquete de 1116 bytes emitido por el controlador y desempaquetando con `struct.unpack('!6d', data[444:492])`.

Formatea todas las coordenadas numéricas a 6 decimales (`.6f`) y desglosa la pose cartesiana en metros ($X, Y, Z$) y radianes ($Rx, Ry, Rz$).

**Salida en consola (Opción `[2]`):**
```text
[*] Conectando con UR10e en 192.168.1.210 para consultar pose TCP actual...
[OK] Pose TCP obtenida vía RTDE:
  Pose Vector: [-0.462130, -0.103808, 0.169564, 1.809200, 1.901000, 0.562500]
  Coordenadas cartesianas (m)  : X = -0.462130 | Y = -0.103808 | Z = 0.169564
  Orientación de la base (rad) : Rx = 1.809200 | Ry = 1.901000 | Rz = 0.562500
```

---

#### 4.3. Módulo de Parada de Emergencia Concurrente: `src/keyboard_listener.py`
Aísla la lógica de captura de teclado no bloqueante. Se ejecuta en un hilo demonio paralelo (`threading.Thread(target=escuchar_parada, args=(stop_requested,), daemon=True)`):

```python
# Fragmento de captura en Linux / Docker TTY
if sys.stdin.isatty():
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        while not stop_requested.is_set():
            rlist, _, _ = select.select([sys.stdin], [], [], 0.05)
            if rlist:
                ch = sys.stdin.read(1)
                if ch in ('\r', '\n', ' '):
                    stop_requested.set()
                    return
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
```

Al pulsar `[ENTER]` o `[ESPACIO]`, activa el evento `stop_requested`, permitiendo que el bucle de movimiento de `move_to_point.py` lo detecte en menos de 40 ms.

---

#### 4.4. Módulo de Movimiento Lineal Supervisado: `src/move_to_point.py`
Supervisa la trayectoria cartesiana `moveL` hasta el punto seleccionado del archivo activo:

```python
# Bucle de supervisión asíncrono con detección de frenado
rtde_ctrl.moveL(pose_destino, setup["speed"], setup["acceleration"], True)
time.sleep(0.15)

detenido_manualmente = False
while not rtde_ctrl.isSteady():
    if stop_requested.is_set():
        detenido_manualmente = True
        print("\n\n[PARADA DE EMERGENCIA] ¡Pulsación detectada! Frenando el robot...")
        rtde_ctrl.stopL(10.0)
        break
    time.sleep(0.04)
```

**Salida en consola cuando el movimiento finaliza normalmente:**
```text
--- Puntos disponibles en points/points.json ---
  [1] origin (Reference origin point for TFG scans)
      Pose: [-0.46213, -0.103808, 0.169564, 1.8092, 1.901, 0.5625]
  [2] end (Reference end point for TFG scans (synchronized Z))
      Pose: [-0.46213, -0.403808, 0.169564, 1.8092, 1.901, 0.5625]

Selecciona el punto objetivo [1-2] (o 'c' para cancelar): 1

--- Setups de Movimiento ---
  [1] movement (defecto): speed = 0.05 m/s, accel = 0.2 m/s^2
  [2] scan: speed = 0.008 m/s, accel = 0.1 m/s^2
Selecciona setup [1-2] (Enter para 'movement'): 1

[*] Preparando movimiento hacia 'origin' usando setup 'movement'...
    Destino   : [-0.46213, -0.103808, 0.169564, 1.8092, 1.901, 0.5625]
    Velocidad : 0.05 m/s | Aceleración: 0.2 m/s^2

[!] >> Pulsa [ENTER] o [ESPACIO] para PARAR el robot en cualquier momento <<

[*] Conectando con UR10e en 192.168.1.210...

[OK] Movimiento a 'origin' completado con éxito.
[*] Conexión liberada.
```

**Salida en consola si el operador acciona la parada de emergencia:**
```text
[!] >> Pulsa [ENTER] o [ESPACIO] para PARAR el robot en cualquier momento <<

[*] Conectando con UR10e en 192.168.1.210...

[PARADA DE EMERGENCIA] ¡Pulsación detectada! Frenando el robot...
[ALERTA] Movimiento hacia 'origin' DETENIDO por el usuario.
[*] Conexión liberada.
```

---

#### 4.5. Módulo de Guiado Manual Libre: `src/teach_mode.py`
Permite liberar articulaciones mediante `teachMode()`, esperando a que el operador termine de posicionar el robot. Al presionar `[ENTER]`, congela la postura con `endTeachMode()` y formula la pregunta de persistencia:

```python
if rtde_ctrl.teachMode():
    input("\n>> Pulsa [ENTER] cuando hayas terminado de posicionar el robot <<\n")
    rtde_ctrl.endTeachMode()

nueva_pose = comprobar_punto_actual(robot_ip)
if nueva_pose:
    guardar = input(f"\n¿Deseas almacenar esta posición en {archivo_activo}? (s/N): ").strip().lower()
    if guardar in ("s", "si", "y", "yes"):
        almacenar_posicion_actual(robot_ip, pose_previa=nueva_pose)
```

**Salida en consola (Opción `[4]`):**
```text
[*] Conectando con UR10e en 192.168.1.210...
[*] Activando teachMode() (Modo Guiado Manual / Freedrive)...

=======================================================
  MODO MANUAL (FREEDRIVE) ACTIVADO
  Mueve el brazo robótico libremente con la mano.
=======================================================

>> Pulsa [ENTER] cuando hayas terminado de posicionar el robot <<

[*] Desactivando modo manual con endTeachMode()...
[OK] Modo manual desactivado. Posición del robot fijada.
[*] Conexión liberada.

--- NUEVA POSICIÓN DEL ROBOT TRAS GUIADO MANUAL ---
[*] Conectando con UR10e en 192.168.1.210 para consultar pose TCP actual...
[OK] Pose TCP obtenida vía RTDE:
  Pose Vector: [-0.462130, -0.350120, 0.169564, 1.809200, 1.901000, 0.562500]
  Coordenadas cartesianas (m)  : X = -0.462130 | Y = -0.350120 | Z = 0.169564
  Orientación de la base (rad) : Rx = 1.809200 | Ry = 1.901000 | Rz = 0.562500

¿Deseas almacenar esta posición en points/points.json? (s/N): s

[*] Archivo de destino activo: points/points.json
Introduce una etiqueta para este punto (Enter para 'Point4'): 
[*] Asignada automáticamente la etiqueta incremental: 'Point4'
Introduce una breve descripción (opcional): Posición ajustada tras guiado manual

[OK] Punto 'Point4' almacenado exitosamente en points/points.json.
```

---

#### 4.6. Módulo de Gestión de Puntos y Nombrado Incremental: `src/points_manager.py`

##### Algoritmo de Nombrado Automático `PointN`:
Analiza las claves actuales del archivo activo con regex, extrayendo los números ya utilizados y previniendo colisiones incluso si existen claves con saltos de numeración o nombres personalizados (`origin`, `end`, etc.):

```python
def generar_siguiente_nombre_punto(puntos):
    numeros = []
    for clave in puntos.keys():
        match = re.match(r"^Point(\d+)$", clave, re.IGNORECASE)
        if match:
            numeros.append(int(match.group(1)))

    siguiente_n = max(numeros) + 1 if numeros else 1
    while f"Point{siguiente_n}" in puntos:
        siguiente_n += 1

    return f"Point{siguiente_n}"
```

##### Serialización Compacta:
Formatea las listas numéricas en una única línea dentro del JSON para ahorrar espacio en disco sin perder legibilidad:

```python
def serializar_puntos_compacto(puntos):
    lineas = ["{", '  "points": {']
    claves = list(puntos.keys())
    for i, clave in enumerate(claves):
        datos = puntos[clave]
        coma = "," if i < len(claves) - 1 else ""
        desc_json = json.dumps(datos.get("description", ""), ensure_ascii=False)
        pose_json = json.dumps(datos.get("pose", []), ensure_ascii=False)
        lineas.append(f'    "{clave}": {{')
        lineas.append(f'      "description": {desc_json},')
        lineas.append(f'      "pose": {pose_json}')
        lineas.append(f'    }}{coma}')
    lineas.append("  }")
    lineas.append("}\n")
    return "\n".join(lineas)
```

**Salida en consola al almacenar posición actual (Opción `[5]`):**
```text
[*] Conectando con UR10e en 192.168.1.210 para consultar pose TCP actual...
[OK] Pose TCP obtenida vía RTDE:
  Pose Vector: [-0.462130, -0.103808, 0.169564, 1.809200, 1.901000, 0.562500]

[*] Archivo de destino activo: points/points.json
Introduce una etiqueta para este punto (Enter para 'Point4'): inspeccion_mesa
Introduce una breve descripción (opcional): Esquina superior izquierda de la placa

[OK] Punto 'inspeccion_mesa' almacenado exitosamente en points/points.json.
```

**Salida en consola al cambiar de archivo de posiciones (Opción `[6]`):**
```text
=======================================================
      SELECCIÓN DE ARCHIVO DE PUNTOS / POSICIONES
  Activo actualmente: points/points.json
=======================================================

Archivos disponibles en 'points/':
  [1] escaneo_placa.json
  [2] points.json  <-- ACTIVO
  [3] Introducir nuevo nombre o ruta de archivo personalizada
  [c] Cancelar
-------------------------------------------------------
Selecciona una opción [1-3] (o 'c' para cancelar): 1

[OK] Archivo activo: points/escaneo_placa.json (4 puntos disponibles)
```

---

#### 4.7. Módulo de Gestión Protegida de Configuración: `src/config_manager.py`
Carga los perfiles cinemáticos desde `config/movement_config.json`:
- `movement`: Orientado al desplazamiento rápido entre puntos de inspección ($0.05\text{ m/s}$, $0.2\text{ m/s}^2$).
- `scan`: Orientado al desplazamiento lento y estable requerido en adquisición ($0.008\text{ m/s}$, $0.1\text{ m/s}^2$).

El archivo no expone ningún método de escritura, y se complementa con la directiva `:ro` en Docker Compose para asegurar que ningún operador pueda modificar accidentalmente los límites seguros del robot.

---

#### 4.8. Módulo Experimental de Cálculo por Offset XYZ: `src/offset_calculator.py`
Permite determinar algebraicamente la pose de destino aplicando desplazamientos de pieza:

```python
def calcular_punto_final(pose_origen, dx=0.0, dy=0.0, dz=0.0):
    x_fin = round(float(pose_origen[0]) + float(dx), 6)
    y_fin = round(float(pose_origen[1]) + float(dy), 6)
    z_fin = round(float(pose_origen[2]) + float(dz), 6)

    rx = round(float(pose_origen[3]), 6)
    ry = round(float(pose_origen[4]), 6)
    rz = round(float(pose_origen[5]), 6)

    return [x_fin, y_fin, z_fin, rx, ry, rz]
```

**Salida en consola (Opción `[7]`):**
```text
============================================================
  CÁLCULO DE PUNTO FINAL POR OFFSET DE PIEZA (XYZ) - EXPERIMENTAL
============================================================
¿Desde qué posición deseas partir?
  [1] Seleccionar un punto guardado del archivo activo
  [2] Capturar la pose TCP actual del robot (en tiempo real)
  [3] Introducir manualmente las coordenadas TCP [X,Y,Z,Rx,Ry,Rz]
  [c] Cancelar
------------------------------------------------------------
Elige una opción [1-3] (o 'c' para cancelar): 1

--- Puntos disponibles en points/points.json ---
  [1] origin (Reference origin point for TFG scans)
      Pose: [-0.46213, -0.103808, 0.169564, 1.8092, 1.901, 0.5625]

Selecciona el punto origen [1-1]: 1

--- Posición de Origen: origin ---
  Pose: [-0.46213, -0.103808, 0.169564, 1.8092, 1.901, 0.5625]
  X: -0.462130 m | Y: -0.103808 m | Z: 0.169564 m
  Rx: 1.809200 | Ry: 1.901000 | Rz: 0.562500

Introduce las distancias a sumar o restar respecto a la pieza (en metros):
  Desplazamiento en X (desplazamiento lateral) [0.0]: 0.0
  Desplazamiento en Y (desplazamiento longitudinal) [0.0]: -0.40
  Desplazamiento en Z (desplazamiento vertical / altura) [0.0]: 0.0

============================================================
                    RESULTADO DEL CÁLCULO
============================================================
  Punto Origen : [-0.46213, -0.103808, 0.169564, 1.8092, 1.901, 0.5625]
  Offset XYZ   : dX = +0.000000 m, dY = -0.400000 m, dZ = +0.000000 m
  Distancia 3D : 0.400000 m (400.00 mm)
  PUNTO FINAL  : [-0.46213, -0.503808, 0.169564, 1.8092, 1.901, 0.5625]
============================================================

¿Deseas almacenar este punto final en 'points/points.json'? (s/N): s
Introduce una etiqueta para este punto (Enter para 'Point4'): Point4
Descripción (Enter para 'Offset desde origin (dx=+0.0000, dy=-0.4000, dz=+0.0000)'): 

[OK] Punto 'Point4' almacenado exitosamente en points/points.json.
```

---

### 5. Métricas de Rendimiento y Tamaño de Archivos

| Archivo / Elemento | Estado Anterior | Estado Optimizado Actual | Reducción / Beneficio |
| :--- | :--- | :--- | :--- |
| **`points/points.json` (Líneas)** | 70 líneas | 29 líneas | **-58.6% de líneas** |
| **`points/points.json` (Bytes en disco)** | 1.261 bytes | 954 bytes | **-24.3% de espacio** |
| **Volumen `config/` en Docker** | Lectura/Escritura abierta | Montaje `:ro` estricto | Prevención total de sobreescritura accidental |
| **Contexto de build Docker** | Sin filtrar (copiaba `.git` y docs) | Filtrado con `.dockerignore` | Contexto de build transferido en <1 segundo |
| **Imagen Docker final** | Multi-etapa Bookworm | 216 MB (~75 MB en `.tar.gz`) | No satura el disco eMMC del Onboard IPC |

---

### 6. Historial Cronológico de Commits del Día 8

```text
* c143a79 docs: add Day 8 technical worklog detailing modular architecture and optimizations
* 535624c feat(config): protect movement_config with read-only volume mount
* 59a6754 docs(readme): document hot-reload and offline editing of points.json
* 1653f3d docs(readme): simplify execution guide to interactive Docker command
* e6967d5 docs(readme): decouple Gocator profilometer references from documentation and code
* d7a1f25 docs: rewrite README with full CLI user guide, Docker commands, and option outputs
* 675787b docs: update GEMINI.md project architecture and add RTDE documentation reference
* e40f246 feat(kinematics): add experimental piece offset XYZ calculator
* b00ba9e refactor(control): modularize UR10e system with interactive CLI orchestrator
```
