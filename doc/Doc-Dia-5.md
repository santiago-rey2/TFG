# Informe de Progreso: Integración y Sincronización Gocator-UR10e

**Fecha:** 13 de mayo de 2026
**Proyecto:** Sistema de análisis de superficies - Gocator & UR10e
**Estado:** Fase 3 - Sincronización de Escaneo y Automatización Docker

---

## 1. Configuración del Perfilómetro Gocator (GoPxL)

Para permitir el control remoto y la captura de perfiles mediante scripts externos, se ha definido la siguiente configuración base en la interfaz GoPxL del sensor Gocator 2600:

| Parámetro | Configuración | Descripción |
| :--- | :--- | :--- |
| **Scan Mode** | Surface | Captura de datos volumétricos y mapas de relieve. |
| **Surface Generation** | Sequential / Software | Control de inicio de grabación del volumen 3D. |
| **Trigger Source** | Time / Software | Disparo continuo o disparado mediante comando externo. |
| **Ethernet Protocol** | ASCII | Habilita el puerto TCP 8190 para recepción de comandos. |

### 1.1. Gestión de Modos de Captura
*   **Modo Surface (Actual):** Se ha migrado del modo Profile al modo Surface para obtener nubes de puntos completas. 
*   **Generación Sequential:** La captura se inicia automáticamente al detectar el estado de adquisición.
*   **Disparo por Software:** Se ha implementado en el script la capacidad de enviar el comando `trigger` para sincronizar con precisión milimétrica el inicio del volumen 3D con el movimiento del robot.

## 2. Protocolo de Comunicación ASCII

La comunicación se realiza mediante sockets TCP/IP estándar (Puerto 8190) utilizando comandos finalizados en `\r\n`:

*   `start`: Activa la emisión láser y la adquisición de perfiles.
*   `stop`: Detiene la adquisición y apaga el láser de forma segura.
*   `trigger`: Inicia la grabación de un volumen 3D cuando el sensor está en modo *Surface/Software*.

## 3. Implementación de Software y Automatización

Se han desarrollado dos nuevos módulos en el directorio `src/` para gestionar la lógica del sensor y su sincronización con el brazo robótico.

### 3.1. Módulo de Control de Sensor (`gocator.py`)
Controla de forma aislada el ciclo de vida del sensor.
*   **Funcionalidad:** Permite realizar barridos temporizados mediante variables de entorno (`GOCATOR_IP`, `GOCATOR_PORT`, `SWEEP_TIME`).
*   **Comando Docker:** `docker-compose run gocator`

### 3.2. Módulo de Escaneo Sincronizado (`scan_sync.py`)
Integra el control del UR10e (vía `ur_rtde`) con el control del sensor.
*   **Flujo de Ejecución:**
    1.  Posicionamiento automático en coordenadas de origen (`origin_pose`).
    2.  Validación de estabilidad del brazo (`isSteady`).
    3.  Activación remota del láser (comando `start`).
    4.  Ejecución de barrido lineal horizontal (Z constante) a velocidad controlada.
    5.  Desactivación automática del láser (comando `stop`) al finalizar el movimiento.
*   **Comando Docker:** `docker-compose run scan`

## 4. Gestión de Datos y Post-procesamiento

El flujo de trabajo para el análisis de datos se ha estructurado de la siguiente manera:
1.  **Grabación:** Generación de archivos `.gprec` (Gocator Recording).
2.  **Transcodificación:** Automatización de `ReplayUtils.exe` mediante la librería `subprocess` para convertir grabaciones a CSV.
3.  **Análisis:** Ingesta de coordenadas absolutas en matrices de Python (`pandas`, `numpy`) para comparación con modelos CAD.

## Próximos Pasos
1.  Validar la precisión del barrido sincronizado sobre una probeta de referencia.
2.  Implementar la lógica de post-procesamiento automático en el contenedor Docker (requiere wine o entorno Windows para `ReplayUtils.exe`).
3.  Ajustar parámetros de velocidad (`ROBOT_VELOCITY`) para optimizar la densidad de puntos del perfil.
