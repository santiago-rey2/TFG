# TFG: Control Cinemático y Gestión de Trayectorias de Robot UR10e

Repositorio de control cinemático, posicionamiento y gestión de trayectorias desarrollado como parte del **Trabajo de Fin de Grado (TFG)** en **Ingeniería Informática**.

El proyecto implementa una arquitectura modular en Python desacoplada y containerizada en Docker para interactuar y controlar de forma segura un brazo robótico **Universal Robots UR10e**, montado sobre una plataforma móvil **Robotnik** y coordinado desde su computador industrial embarcado (**Onboard IPC**).

---

## 🎯 ¿Qué es este Proyecto?

El objetivo principal es el control cinemático de alta precisión, la captura de telemetría y la gestión dinámica de posiciones y trayectorias del brazo robótico UR10e para tareas de posicionamiento, inspección y guiado manual.

### Características Principales:
* **Comunicación de baja latencia con UR10e:** Utiliza el protocolo industrial **ur_rtde** (puerto de control 30004 y telemetría 30003) para lecturas de pose y trayectorias lineales en tiempo real.
* **Orquestador Interactivo en CLI:** Menú centralizado para inspeccionar poses, ejecutar trayectorias, guiar manualmente el brazo y calcular puntos relativos.
* **Parada de Emergencia Inmediata:** Monitoreo en hilo paralelo no bloqueante durante movimientos lineales; presionar `[ENTER]` o `[ESPACIO]` frena el robot al instante (`stopL`).
* **Modo Guiado Manual (Teach Mode / Freedrive):** Activación de guiado libre con la mano desde la consola y guardado directo de la pose fijada.
* **Gestión Dinámica de Puntos (`PointN`) y Edición en Caliente:** Almacenamiento y conmutación de archivos de posiciones `.json`. Los archivos de puntos son **modificables tanto con la aplicación en ejecución como en parado**, reflejándose cualquier cambio de forma inmediata sin reiniciar el contenedor.
* **Cálculo Experimental por Offset XYZ:** Determinación matemática de puntos de llegada aplicando traslaciones relativas en función de las dimensiones de la pieza.
* **Contenedor Ultraligero:** Imagen Docker multi-stage optimizada (~216 MB) para preservar el almacenamiento y recursos del IPC del Robotnik.

---

## 🏗️ Estructura del Proyecto

```text
├── config/
│   └── movement_config.json    # Perfiles de dinámica protegidos de solo lectura (:ro) (velocidad y aceleración)
├── points/
│   └── points.json             # Almacén de coordenadas cartesianas (modificable en caliente y en parado)
├── src/
│   ├── main.py                 # Orquestador principal y menú interactivo CLI
│   ├── check_pose.py           # Consulta en tiempo real de la pose TCP (RTDE y socket 30003)
│   ├── config_manager.py       # Carga y selección de setups de movimiento
│   ├── keyboard_listener.py    # Captura multiplataforma de parada de emergencia (ENTER / ESPACIO)
│   ├── move_to_point.py        # Movimiento lineal moveL con frenado de emergencia
│   ├── offset_calculator.py    # Cálculo de punto final aplicando offsets XYZ de pieza (Experimental)
│   ├── points_manager.py       # Serialización compacta, gestión de archivos y nombrado PointN
│   └── teach_mode.py           # Modo guiado manual libre (teachMode y endTeachMode)
├── doc/                        # Bitácoras de laboratorio y documentación técnica
├── .dockerignore               # Filtro de exclusión para compilaciones Docker limpias
├── .env.example                # Plantilla de variables de entorno de red
├── Dockerfile                  # Construcción multi-stage ligera en Python 3.11-slim
├── docker-compose.yml          # Orquestación del contenedor con TTY interactivo
└── requirements.txt            # Dependencias Python mínimas (ur_rtde, python-dotenv)
```

---

## ⚙️ Configuración Previa

### 1. Archivo de Entorno (`.env`)
Crea un archivo `.env` en la raíz del proyecto basado en `.env.example`:
```bash
cp .env.example .env
```
Edita la IP del controlador del robot (URSim o Robot Físico):
```env
ROBOT_IP=192.168.1.210
```

> [!IMPORTANT]
> El archivo `.env` contiene parámetros de red específicos del laboratorio y nunca debe subirse al control de versiones.

### 2. Control Remoto en el Robot Real (PolyScope)
Para que el UR10e acepte comandos de movimiento externos vía RTDE:
1. En la pantalla táctil de PolyScope, entra en **Ajustes (Settings) > Sistema (System) > Control remoto (Remote Control)** y pulsa **Habilitar (Enable)**.
2. En la esquina superior derecha del encabezado, cambia de **Control local** a **Control remoto**.

---

## 🚀 Guía de Ejecución

Para iniciar la sesión interactiva en la consola del robot, ejecuta el contenedor en Docker:

```bash
docker compose run --rm ur10e-control
```

> [!NOTE]
> El flag `--rm` asegura que el contenedor efímero se elimine automáticamente al salir, liberando recursos en el computador embarcado (IPC).

---

## 🖥️ Interacción y Salida CLI por Opción

Al iniciar el programa se despliega el menú principal con el archivo de posiciones activo:

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

### [1] Listar puntos disponibles
Lee el archivo de puntos actualmente activo y muestra los nombres de los puntos guardados, sus descripciones y sus coordenadas cartesianas de pose `[X, Y, Z, Rx, Ry, Rz]`.

> [!TIP]
> **Edición en Caliente y en Parado:** El archivo `points.json` (o cualquier otro archivo `.json` en `points/`) puede ser editado, ampliado o modificado manualmente **tanto con la aplicación en ejecución como en parado**. Gracias al montaje de volúmenes de Docker (`./points:/app/points`), el sistema lee directamente del disco en cada operación, por lo que cualquier cambio externo se reflejará de forma inmediata sin reiniciar el contenedor.

**Salida en consola:**
```text
--- Puntos disponibles en points/points.json ---
  [1] origin (Reference origin point for TFG scans)
      Pose: [-0.46213, -0.103808, 0.169564, 1.8092, 1.901, 0.5625]
  [2] end (Reference end point for TFG scans (synchronized Z))
      Pose: [-0.46213, -0.403808, 0.169564, 1.8092, 1.901, 0.5625]
  [3] middle (Reference middle point for TFG scans (synchronized Z))
      Pose: [-0.46213, -0.403808, 0.169564, 1.8092, 1.901, 0.5625]
  [4] Point1
      Pose: [-0.46213, -0.103808, 0.169564, 1.8092, 1.901, 0.5625]
  [5] Point2
      Pose: [-0.46213, -0.103808, 0.169564, 1.8092, 1.901, 0.5625]
  [6] Point3 (Offset desde Pose_Actual_Robot (dx=+0.0000, dy=-0.4000, dz=+0.0000))
      Pose: [-0.46213, -0.503808, 0.169564, 1.8092, 1.901, 0.5625]
```

---

### [2] Comprobar pose TCP actual del robot
Se conecta en tiempo real al robot vía RTDE (puerto 30004) con fallback al socket de telemetría (puerto 30003), reportando la posición del efector final con precisión de 6 decimales tanto en vector crudo como desglosado en metros y radianes.

**Salida en consola:**
```text
[*] Conectando con UR10e en 192.168.1.210 para consultar pose TCP actual...
[OK] Pose TCP obtenida vía RTDE:
  Pose Vector: [-0.462130, -0.103808, 0.169564, 1.809200, 1.901000, 0.562500]
  Coordenadas cartesianas (m)  : X = -0.462130 | Y = -0.103808 | Z = 0.169564
  Orientación de la base (rad) : Rx = 1.809200 | Ry = 1.901000 | Rz = 0.562500
```

---

### [3] Mover el robot a un punto
Permite seleccionar uno de los puntos guardados y escoger el perfil de dinámica (`movement` a 0.05 m/s para movimientos generales o `scan` a 0.008 m/s para movimientos lentos de alta estabilidad). Ejecuta el movimiento en modo asíncrono mientras vigila si el usuario presiona `[ENTER]` o `[ESPACIO]` para detenerlo inmediatamente.

**Caso 1: Movimiento completado con éxito:**
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

**Caso 2: Parada de emergencia accionada por el usuario:**
```text
[!] >> Pulsa [ENTER] o [ESPACIO] para PARAR el robot en cualquier momento <<

[*] Conectando con UR10e en 192.168.1.210...

[PARADA DE EMERGENCIA] ¡Pulsación detectada! Frenando el robot...
[ALERTA] Movimiento hacia 'origin' DETENIDO por el usuario.
[*] Conexión liberada.
```

---

### [4] Modo guiado manual libre (Teach Mode)
Activa la función `teachMode()` de RTDE, desengranando los frenos para mover el brazo libremente con la mano (Freedrive). Al presionar `[ENTER]`, fija la posición con `endTeachMode()`, muestra la nueva pose alcanzada y ofrece guardarla al instante en el archivo de puntos activo.

**Salida en consola:**
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

### [5] Almacenar posición actual
Captura la posición actual del robot y la añade al archivo activo. Si no se introduce un nombre específico, asigna automáticamente la etiqueta incremental `PointN` calculada según los puntos existentes.

**Salida en consola:**
```text
[*] Conectando con UR10e en 192.168.1.210 para consultar pose TCP actual...
[OK] Pose TCP obtenida vía RTDE:
  Pose Vector: [-0.462130, -0.103808, 0.169564, 1.809200, 1.901000, 0.562500]
  Coordenadas cartesianas (m)  : X = -0.462130 | Y = -0.103808 | Z = 0.169564
  Orientación de la base (rad) : Rx = 1.809200 | Ry = 1.901000 | Rz = 0.562500

[*] Archivo de destino activo: points/points.json
Introduce una etiqueta para este punto (Enter para 'Point4'): inspeccion_mesa
Introduce una breve descripción (opcional): Esquina superior izquierda de la placa

[OK] Punto 'inspeccion_mesa' almacenado exitosamente en points/points.json.
```

---

### [6] Seleccionar / Cambiar archivo de posiciones
Permite conmutar el archivo de puntos de trabajo en caliente sin reiniciar la aplicación. Detecta automáticamente los archivos `.json` en `points/` o permite indicar uno nuevo, creándolo con estructura básica si no existía.

**Salida en consola:**
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

### [7] Calcular punto final por offset XYZ (Experimental)
Calcula una nueva pose TCP sumando o restando distancias en los ejes $X, Y, Z$ (en metros) a partir de una posición inicial (un punto existente, la pose actual del robot o coordenadas manuales). Conserva la orientación angular del efector final, evalúa la distancia euclídea 3D e incluye una advertencia preventiva de seguridad si se modifica la altura $Z$ respecto al plano de trabajo original.

**Salida en consola:**
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

### [8] Salir
Cierra limpiamente el bucle interactivo del orquestador y libera cualquier conexión activa con el controlador.

**Salida en consola:**
```text
Elige una opción [1-8]: 8

Saliendo del orquestador.
```

---

## 🔒 Directrices de Seguridad y Buenas Prácticas

1. **Parada de Emergencia:** Mantén siempre accesible el teclado de la consola o la parada de emergencia física (seta de parada) del UR10e durante las pruebas en laboratorio.
2. **Plano de Altura Constante ($Z$):** Para operaciones que requieran mantener una distancia de trabajo fija, verifica que la coordenada $Z$ permanezca constante durante todo el recorrido.
3. **Protección de Dinámicas:** El directorio `config/` se monta en modo solo lectura (`:ro`) para impedir alteraciones de velocidad y aceleración fuera de los umbrales seguros calibrados para el UR10e.
4. **Mantenimiento de Imágenes:** No modificar la estructura de capas del `Dockerfile` para no incrementar el tamaño de la imagen sobre los 216 MB optimizados.
