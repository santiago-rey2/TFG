# TFG: Análisis de datos - Gocator & UR10e

Este repositorio contiene las herramientas de comunicación y control desarrolladas para el Trabajo de Fin de Grado centrado en el escaneo y análisis de datos con un perfilómetro **Gocator** montado en un robot **UR10e**.

## 🚀 Descripción General

El sistema utiliza el protocolo **ur_rtde** para establecer comunicación con el controlador del robot Universal Robots. Se han implementado dos servicios principales:
1.  **Status**: Diagnóstico rápido de conexión y lectura de telemetría.
2.  **Movement**: Ejecución de trayectorias lineales planas para escaneo de precisión.

---

## 🛠️ Requisitos Previos

Para ejecutar este proyecto de forma aislada y segura, es necesario disponer de:
*   [Docker](https://www.docker.com/get-started)
*   [Docker Compose](https://docs.docker.com/compose/install/)
*   Acceso por red al controlador del robot (Real o Simulador URSim).

---

## ⚙️ Configuración del Entorno

Antes de iniciar los servicios, debes configurar las direcciones IP y parámetros en un archivo `.env`:

1.  Crea un archivo llamado `.env` en la raíz del proyecto (basado en `.env.example`).
2.  Define las variables necesarias:
    ```env
    # Robot UR10e
    ROBOT_IP=192.168.1.210

    # Perfilómetro Gocator
    GOCATOR_IP=192.168.1.10
    GOCATOR_PORT=8190
    SWEEP_TIME=10
    ```

---

## 📦 Guía de Uso con Docker Compose

La imagen de Docker incluye todas las dependencias necesarias (`ur_rtde`, `socket`, etc.) configuradas.

### 1. Construcción de la imagen
```bash
docker compose build
```

### 2. Servicios de Diagnóstico
*   **Robot Status**: Ver telemetría actual del UR10e.
    ```bash
    docker compose run status
    ```
*   **Gocator Control**: Iniciar un escaneo temporizado aislado (barrido manual).
    ```bash
    docker compose run gocator
    ```

### 3. Ejecución de Trayectorias
*   **Movement**: Mueve el robot entre los puntos de origen y fin (sin sensor).
    ```bash
    docker compose run movement
    ```
*   **Scan (Sincronizado)**: **Comando principal de trabajo**. Coordina el movimiento del brazo con la activación/desactivación automática del Gocator.
    ```bash
    docker compose run scan
    ```

---

## 🔍 Configuración del Gocator (GoPxL)

Para que los comandos remotos funcionen, el sensor debe estar configurado en su interfaz web:
*   **Scan Mode**: `Surface` (para capturas volumétricas).
*   **Surface Generation**: `Sequential` o `Software`.
*   **Trigger Source**: `Time` o `Software`.
*   **Protocolo**: `ASCII` habilitado en la pestaña Output > Ethernet.

---

## 📐 Detalles de la Trayectoria

El script `robot_movement.py` está configurado con las siguientes coordenadas articulares (grados):

| Articulación | Origen (°) | Fin (°) |
| :--- | :---: | :---: |
| Base | -143.03 | -57.92 |
| Shoulder | -62.89 | -68.94 |
| Elbow | 81.82 | 88.45 |
| Wrist 1 | -110.44 | -113.97 |
| Wrist 2 | -92.18 | -88.96 |
| Wrist 3 | 0.00 | 0.03 |

**Nota técnica:** El sistema recalcula automáticamente la cinemática directa para forzar una trayectoria horizontal plana, evitando desniveles durante el escaneo.

---

## ⚠️ Diferencias entre URSim y Robot Real (PolyScope)

Para que el controlador físico admita comandos de movimiento enviados desde el exterior (como los de los scripts de Python a través de RTDE), es necesario realizar ajustes específicos en la interfaz del robot real que suelen estar pre-configurados en el simulador.

### Configuración del Control Remoto en el Robot Físico

Según el manual oficial del UR10e, siga estos pasos en la consola **PolyScope**:

1.  **Acceder a los Ajustes:** En el encabezado (esquina superior derecha), pulse el **Menú Hamburguesa** (tres líneas horizontales) y seleccione **Ajustes (Settings)**.
2.  **Navegar a Control Remoto:** En el menú de la izquierda, dentro de la categoría **Sistema (System)**, seleccione la opción **Control remoto (Remote Control)**.
3.  **Habilitar la función:** Pulse el botón **Habilitar (Enable)**. Esto elimina la restricción por defecto que bloquea el encendido, la liberación de frenos y la ejecución de programas vía red.
4.  **Activar el modo Remoto:** Una vez habilitado, debe indicarle activamente al robot que ceda el control. En la esquina superior derecha del encabezado, cambie el modo de **Control local** a **Control remoto**.

### Observaciones Importantes:

*   **Iconografía:** En el simulador URSim, el icono de "Local / Remote" aparece como una pantalla con una mano. En robots físicos con PolyScope 5, este cambio puede realizarse pulsando el **icono de perfil** en la esquina superior derecha para alternar entre el control de la consola portátil (Local) y el externo (Remoto).
*   **Seguridad:** Si el robot tiene configurada una "Contraseña de modo", el sistema la solicitará al intentar cambiar a modo Remoto o al seleccionar perfiles de Operador/Programador para autorizar el control externo.

---

## 📁 Estructura del Proyecto

*   `src/`: Scripts de control en Python.
*   `doc/`: Documentación adicional y capturas del proyecto.
*   `Dockerfile`: Definición de la imagen de compilación.
*   `docker-compose.yml`: Orquestación de servicios de ejecución.
*   `GEMINI.md`: Contexto extendido para el desarrollo asistido por IA.
