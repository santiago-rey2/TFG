# Guía Técnica: Generación, Exportación y Despliegue de la Imagen Docker desde Cero

Este documento describe el procedimiento completo y detallado para compilar la imagen Docker optimizada del controlador **UR10e**, exportarla a un paquete portable comprimido, transferirla al computador industrial embarcado (**Onboard IPC**) de la plataforma móvil **Robotnik** y ejecutarla en el entorno de producción en planta/laboratorio.

---

## 1. Contexto de la Plataforma y Restricciones de Hardware

El sistema de control está diseñado para operar en una arquitectura ciberfísica compuesta por:
- **Brazo Robótico:** Universal Robots UR10e (controlador e-Series con PolyScope).
- **Plataforma Móvil:** Robotnik (con red Gigabit interna propia).
- **Computador Central:** Onboard IPC montado dentro de la base móvil Robotnik, actuando como nodo maestro y pasarela de comunicaciones.

### Desafíos Técnicos de Despliegue:
1. **Almacenamiento Reducido:** Los computadores industriales embebidos suelen contar con unidades eMMC o SSDs industriales de capacidad moderada (16 a 64 GB), compartidos con el sistema operativo de navegación (ROS) de Robotnik.
2. **Entornos Aislados (Air-Gapped):** En muchas zonas del laboratorio o planta industrial, el robot no dispone de acceso a Internet, por lo que **no es viable ejecutar `docker compose build` ni descargar paquetes de `pip` directamente en el robot**.
3. **Solución:** Generar una imagen ultra-ligera multi-stage en el equipo de desarrollo, empaquetarla en un archivo `.tar.gz` de solo **~75 MB** y cargarla mediante `docker load` en el IPC del robot.

---

## 2. Anatomía de la Construcción Multi-Stage (`Dockerfile`)

El archivo [Dockerfile](file:///c:/Users/Santi/Documents/GITHUB/TFG/Dockerfile) utiliza una estrategia de dos fases (*Multi-Stage Build*) basada en Debian Bookworm:

```dockerfile
# ==========================================
# Etapa 1: Builder (Compilación y Limpieza)
# ==========================================
FROM python:3.11-slim-bookworm AS builder

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Limpieza exhaustiva:
# - Elimina directorios tests de las librerías
# - Elimina bytecode compilado __pycache__ y *.pyc
# - Elimina pip y setuptools (no necesarios en tiempo de ejecución)
RUN find /opt/venv -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true \
    && find /opt/venv -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true \
    && find /opt/venv -name "*.pyc" -delete \
    && rm -rf /opt/venv/lib/python3.11/site-packages/pip* \
    && rm -rf /opt/venv/lib/python3.11/site-packages/setuptools* \
    && rm -rf /opt/venv/share

# ==========================================
# Etapa 2: Runner (Imagen Final Mínima)
# ==========================================
FROM python:3.11-slim-bookworm

# Copia únicamente el entorno virtual procesado (sin capas temporales de build)
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app
COPY src/ ./src/
COPY config/ ./config/
COPY points/ ./points/

CMD ["python", "src/main.py"]
```

### Papel de `.dockerignore`:
El archivo [.dockerignore](file:///c:/Users/Santi/Documents/GITHUB/TFG/.dockerignore) excluye la carpeta de control de versiones `.git`, la documentación `doc/`, los entornos virtuales locales y archivos temporales. Esto reduce el contexto enviado al Docker daemon de más de 100 MB a menos de **500 KB**, acelerando la construcción drásticamente.

---

## 3. Paso 1: Construcción de la Imagen desde Cero (Máquina de Desarrollo)

Desde el directorio raíz del proyecto (`c:\Users\Santi\Documents\GITHUB\TFG` o equivalente en Linux/macOS), ejecuta la construcción mediante Docker Compose o Docker CLI directo:

### Opción A (Recomendada con Docker Compose):
```bash
docker compose build --no-cache
```

### Opción B (Con Docker CLI puro):
```bash
docker build --no-cache -t ur10e-control:0.1 .
```

*El uso de `--no-cache` garantiza que todas las dependencias (`ur_rtde` 1.6.3 y `python-dotenv`) se descarguen limpias y se reempaquete el código más reciente.*

### Verificación de la Imagen Creada:
Comprueba que la imagen existe y valida su tamaño:
```bash
docker images ur10e-control:0.1
```

**Salida esperada:**
```text
REPOSITORY        TAG       IMAGE ID       CREATED          SIZE
ur10e-control     0.1       a1b2c3d4e5f6   Hace 1 minuto    216MB
```
*(El tamaño sin comprimir se mantiene en unos 216 MB).*

---

## 4. Paso 2: Exportación y Compresión a un Archivo Portable

Para poder trasladar la imagen a través de red o mediante un pendrive USB al robot, se serializa la imagen con `docker save` y se comprime con `gzip`.

### En Entornos Linux, macOS o WSL:
```bash
docker save ur10e-control:0.1 | gzip > ur10e-control-0.1.tar.gz
```

### En Windows (PowerShell):
```powershell
# 1. Exportar el archivo tar crudo:
docker save ur10e-control:0.1 -o ur10e-control-0.1.tar

# 2. Comprimir con tar nativo de Windows (o 7-Zip):
tar -czvf ur10e-control-0.1.tar.gz ur10e-control-0.1.tar

# 3. Eliminar el archivo tar sin comprimir para ahorrar espacio:
Remove-Item ur10e-control-0.1.tar
```

### Comprobación del Paquete Generado:
Verifica el tamaño del archivo comprimido resultante:
```powershell
Get-Item ur10e-control-0.1.tar.gz | Select-Object Name, @{Name="MB";Expression={[math]::round($_.Length/1MB, 2)}}
```
**Resultado esperado:** Un archivo de aproximadamente **~70 a 78 MB**, ideal para transferencia instantánea.

---

## 5. Paso 3: Transferencia al Onboard IPC de Robotnik

Conecta tu equipo de desarrollo a la red local del robot (mediante cable Ethernet Gigabit o Wi-Fi del laboratorio).

### Vía SCP (Línea de Comandos):
Sustituye la IP y usuario por los configurados en el IPC de Robotnik (ejemplo: `robotnik` en `192.168.0.200`):
```bash
scp ur10e-control-0.1.tar.gz robotnik@192.168.0.200:/home/robotnik/
```

### Vía Memoria USB:
Si el IPC no está accesible por red externa:
1. Copia `ur10e-control-0.1.tar.gz` a una memoria USB (formato ext4, FAT32 o NTFS).
2. Conéctala a un puerto USB libre del Onboard IPC de Robotnik.
3. Monta la unidad y copia el archivo al directorio de usuario:
   ```bash
   cp /media/usb/ur10e-control-0.1.tar.gz /home/robotnik/
   ```

---

## 6. Paso 4: Importación y Carga de la Imagen en el Robot

Inicia sesión por SSH en el IPC de Robotnik:
```bash
ssh robotnik@192.168.0.200
```

Descomprime e importa la imagen al Docker daemon local del robot mediante `docker load`:
```bash
docker load < /home/robotnik/ur10e-control-0.1.tar.gz
```

**Salida en consola del robot:**
```text
Loaded image: ur10e-control:0.1
```

Verifica que el robot ya reconoce la imagen:
```bash
docker images
```

Una vez cargada, puedes borrar el archivo `.tar.gz` en el robot para liberar espacio en disco:
```bash
rm /home/robotnik/ur10e-control-0.1.tar.gz
```

---

## 7. Paso 5: Preparación de la Carpeta de Operación en el Robot

Para ejecutar el contenedor con volúmenes montados (permitiendo modificar o añadir archivos de puntos en caliente), crea la estructura de trabajo en el IPC:

```bash
mkdir -p /home/robotnik/tfg-control/config
mkdir -p /home/robotnik/tfg-control/points
```

Copia o crea los siguientes archivos esenciales en `/home/robotnik/tfg-control/`:

### 1. `docker-compose.yml`
```yaml
services:
  ur10e-control:
    image: ur10e-control:0.1
    stdin_open: true
    tty: true
    env_file:
      - .env
    volumes:
      - ./config:/app/config:ro
      - ./points:/app/points
    command: python src/main.py
```

### 2. Archivo `.env`
```env
ROBOT_IP=192.168.1.210
```

### 3. Archivo de Configuración Protegido (`config/movement_config.json`)
```json
{
  "setups": {
    "movement": {
      "description": "Standard velocity for positioning and general movements",
      "speed": 0.05,
      "acceleration": 0.2
    },
    "scan": {
      "description": "Slow and stable velocity for profilometer scan acquisition",
      "speed": 0.008,
      "acceleration": 0.1
    }
  },
  "default_setup": "movement"
}
```

### 4. Archivo Inicial de Puntos (`points/points.json`)
```json
{
  "points": {
    "origin": {
      "description": "Reference origin point for TFG scans",
      "pose": [-0.46213, -0.103808, 0.169564, 1.8092, 1.901, 0.5625]
    },
    "end": {
      "description": "Reference end point for TFG scans (synchronized Z)",
      "pose": [-0.46213, -0.403808, 0.169564, 1.8092, 1.901, 0.5625]
    }
  }
}
```

---

## 8. Paso 6: Puesta en Marcha y Verificación

Desde la carpeta `/home/robotnik/tfg-control/`, lanza la aplicación:

```bash
docker compose run --rm ur10e-control
```

### Comprobaciones Inmediatas en Consola:
1. **Opción `[2]` (Comprobar pose actual):** Confirma que el canal RTDE con la IP `192.168.1.210` en el puerto 30004 responde correctamente y reporta las coordenadas reales del brazo.
2. **Opción `[4]` (Teach Mode):** Verifica que se liberan los frenos, mueve el brazo unos centímetros y pulsa Enter para asegurar que se fijan los frenos y se lee la nueva pose.
3. **Opción `[1]` (Listar puntos):** Comprueba que se leen correctamente las coordenadas de `points.json`.

---

## 9. Resolución de Problemas Frecuentes (Troubleshooting)

### A. Error de permisos de Docker en el IPC:
Si al ejecutar `docker` aparece `permission denied while trying to connect to the Docker daemon socket`:
```bash
sudo usermod -aG docker $USER
newgrp docker
```

### B. El contenedor no conecta con el UR10e:
- Realiza un ping al controlador del robot desde el IPC:
  ```bash
  ping -c 3 192.168.1.210
  ```
- Comprueba que el puerto RTDE 30004 está abierto:
  ```bash
  nc -zv 192.168.1.210 30004
  ```
- Verifica en la consola táctil PolyScope que el modo de **Control Remoto (Remote Control)** está habilitado y seleccionado.

### C. La consola interactiva no captura pulsaciones o se sale sola:
- Asegúrate de incluir siempre las directivas `stdin_open: true` y `tty: true` en el archivo `docker-compose.yml` para que Docker asigne un pseudoterminal (TTY) y permita la captura no bloqueante de teclas con `termios`.
