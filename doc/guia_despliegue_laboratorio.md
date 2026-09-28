# Guía Técnica: Despliegue de Contenedores Docker y Operativa en el Laboratorio
## Proyecto TFG: Perfilómetro Gocator 2600 y Robot UR10e

Esta guía detalla el procedimiento exacto paso a paso para transferir las imágenes Docker y el software desarrollado en el entorno de desarrollo/casa al equipo físico del laboratorio, verificar la comunicación y ejecutar las pruebas de movimiento y escaneo.

---

## 1. Métodos de Transferencia de las Imágenes Docker

Existen dos alternativas dependiendo de si el equipo del laboratorio dispone o no de conexión a Internet.

### Método A: Exportación Offline a Archivo TAR (Recomendado)
Este método es el más seguro y rápido, ya que **no requiere conexión a Internet en el laboratorio ni volver a compilar `ur_rtde` ni paquetes C++**.

#### 1. En el ordenador de desarrollo (en casa):
Ejecutar en la terminal para empaquetar las imágenes ya compiladas en un único archivo:
```bash
docker save -o robot_images.tar robot-status:0.1 robot-movement:0.1
```
*(Opcional: comprimir para que ocupe menos en el pendrive USB: `gzip robot_images.tar`)*.

Copiar al pendrive:
- El archivo `robot_images.tar` (o `.tar.gz`).
- El repositorio clonado con los últimos cambios (`git pull` o copia de la carpeta del proyecto).

#### 2. En el ordenador del laboratorio:
Copiar el archivo desde el pendrive y cargarlo en el daemon de Docker:
```bash
docker load -i robot_images.tar
```
Verificar que las imágenes están cargadas:
```bash
docker images
```
*Deberán aparecer listadas `robot-status:0.1` y `robot-movement:0.1`.*

---

### Método B: Vía Git + Construcción Local (Si el laboratorio tiene Internet)
Si el equipo del laboratorio tiene acceso a internet:
```bash
git pull origin main
docker compose build status movement
```
*(Gracias a la migración a Debian Bookworm, la compilación de `numpy` y `ur_rtde` se completará en pocos minutos de forma automatizada).*

---

## 2. Configuración de Red en el Laboratorio

### 2.1. Tarjeta de Red del PC del Laboratorio
El PC debe estar configurado con una IP estática dentro del rango de trabajo del robot y el sensor:
- **IP del PC:** `192.168.0.100` (o similar, terminada entre .100 y .200)
- **Máscara de subred:** `255.255.255.0`
- **Puerta de enlace:** Vacía (o según la red del laboratorio)

### 2.2. Archivo de Variables de Entorno (`.env`)
Dado que el archivo `.env` está en `.gitignore` por seguridad, al llegar al laboratorio se debe crear en la raíz del proyecto:
```bash
# Crear o editar archivo .env
cat <<EOF > .env
ROBOT_IP=192.168.0.210
GOCATOR_IP=192.168.0.10
GOCATOR_PORT=8190
SWEEP_TIME=30
EOF
```

---

## 3. Preparación del Robot UR10e (Teach Pendant)

Antes de lanzar cualquier comando que intente mover el robot:
1. **Encender el Robot:** Pulsar el botón verde en el Teach Pendant y liberar los frenos (modo Normal / Running).
2. **Activar Modo Remoto:**
   - En la esquina superior derecha de la interfaz de Polyscope, pulsar sobre el icono del mando / robot.
   - Seleccionar **"Remote Control" (Control Remoto)**.
   - *Nota:* Si el robot no está en modo remoto, responderá al estado y telemetría, pero rechazará las órdenes cinemáticas de movimiento.

---

## 4. Secuencia de Verificación y Puesta en Marcha

### Paso 1: Diagnóstico Rápido de Comunicación (Sin mover el robot)
Desde la terminal del PC del laboratorio, ejecutar el script de comprobación general:
```bash
python src/robot_check_connection.py --ip 192.168.0.210
```
**Comprobar que indique:**
- `Dashboard Server (29999): OK` (Robotmode: RUNNING, Remote Control: `true`)
- `Telemetría Real-time (30003): OK` (500 Hz, muestra articulaciones reales)
- `Puerto RTDE (30004): ABIERTO`

Verificar también la disponibilidad del sensor láser:
```bash
python src/gocator.py --status
```
*(Debe reportar `Disponible: True` y latencia en ms).*

---

### Paso 2: Comprobación del Contenedor Docker de Telemetría
Verificar que el contenedor Docker montado conecta por RTDE nativo con el robot físico:
```bash
docker compose run --rm status
```
Debe devolver la telemetría en tiempo real, temperaturas de juntas y estado seguro.

---

### Paso 3: Operativa Desacoplada en Laboratorio (Dos Terminales)

#### Terminal 1 — Control del Brazo UR10e:
Lanzar la consola interactiva dentro de Docker:
```bash
docker compose run --rm movement
```
*(O directamente en host si se dispone de Python: `python src/robot_movement.py -i --json routes/default_tfg.json`)*.

**Flujo en la Consola Interactiva:**
1. Pulsar `[5]` para ver la posición y pose actual.
2. Pulsar `[2]` para posicionar suavemente en el punto de **ORIGEN / HOME** sin barrido.
3. Comprobar visualmente la alineación con la probeta.
4. Si se necesitan ajustar cotas, editar `routes/default_tfg.json` o `routes/ejemplo_ruta.csv` en el editor, guardar, y en la consola pulsar `[3]` (**Hot-Reload**) para recargar al instante sin reconectar RTDE.
5. Pulsar `[1]` para ejecutar la trayectoria.

#### Terminal 2 — Actuación del Perfilómetro Láser Gocator 2600:
En una segunda terminal independiente:
```bash
# Opción A: Barrido temporizado de 30 segundos (ideal para coordinar con el movimiento del robot)
python src/gocator.py --sweep 30

# Opción B: Consola interactiva del sensor (encender / apagar manualmente)
python src/gocator.py -i

# Opción C: Encendido directo
python src/gocator.py --cmd start
# ... realizar escaneo ...
python src/gocator.py --cmd stop
```

---

## 5. Tabla de Solución de Problemas Comunes

| Síntoma / Error | Causa Probable | Solución |
| :--- | :--- | :--- |
| `El robot rechazó la conexión o control` | El Teach Pendant no está en modo remoto. | Cambiar en la pantalla táctil de Polyscope a modo "Remote Control". |
| `Protective Stop activo` | El robot detectó colisión previa o límite singular. | Desbloquear desde el Teach Pendant antes de reintentar. |
| `Gocator Timeout / No responde` | IP incorrecta o cable Ethernet desconectado. | Comprobar con `ping 192.168.0.10` y revisar puerto 8190 en GoPxL. |
| `Z no constante / trayectoria inclinada` | Restricción Z desactivada. | Asegurar que `force_constant_z: true` en el JSON o no pasar `--sin-z-constante`. |
| `Docker: network not found` | Primera ejecución de docker compose. | Se crea automáticamente al hacer `docker compose run --rm status`. |
