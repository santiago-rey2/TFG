# Informe de Progreso: Implementación de Control Externo y Dockerización

**Fecha:** 15 de abril de 2026  
**Proyecto:** Sistema de análisis de superficies - Gocator & UR10e  
**Estado:** Fase 2 - Protocolo `ur_rtde` y entorno de ejecución aislado.

---

## 1. Implementación de Comunicación Programática

Tras la fase inicial de toma de contacto con Polyscope, se ha procedido a externalizar el control del brazo utilizando la librería **RTDE (Real-Time Data Exchange)** a través del paquete `ur_rtde`.

### 1.1. Estructura de Scripts
Se ha abandonado el script monolítico inicial en favor de una arquitectura modular:
*   `robot_status.py`: Monitorización de telemetría (Joints y TCP Pose).
*   `robot_movement.py`: Ejecución de trayectorias de escaneo.

### 1.2. Lógica de Trayectoria Plana (Flat Scan)
Para garantizar la validez de los datos del perfilómetro Gocator, se ha implementado una restricción por software:
*   **Problema:** El movimiento entre dos puntos articulares puede generar una pendiente en el eje Z si no se calcula con precisión.
*   **Solución:** El script captura la coordenada Z del punto de origen y la sobrescribe en el punto de destino tras el cálculo de cinemática directa. Esto asegura que el `moveL` se realice en un plano perfectamente paralelo a la base.

---

## 2. Infraestructura de Ejecución (Docker)

Para solventar las dependencias complejas de compilación de `ur_rtde` (C++11, Boost, CMake), se ha migrado el entorno de desarrollo a **Docker**.

### Configuración del Contenedor:
*   **Imagen Base:** `python:3.10-slim`.
*   **Dependencias de Sistema:** `cmake`, `libboost-all-dev`, `build-essential`.
*   **Orquestación:** `docker-compose.yml` define dos servicios (`status` y `movement`) que comparten una misma imagen optimizada.
*   **Seguridad y Portabilidad:** La IP del robot se desacopla del código mediante un archivo `.env`, facilitando el cambio entre el simulador URSim y el robot real de Robotnik.

---

## 3. Resultados de Pruebas de Movimiento

Se ha validado la trayectoria lineal entre los puntos críticos del TFG:
*   **Origen:** `[-143.03, -62.89, 81.82, -110.44, -92.18, 0.00]` (Grados)
*   **Fin:** `[-57.92, -68.94, 88.45, -113.97, -88.96, 0.03]` (Grados)
*   **Resultado:** Movimiento lineal estable a 250 mm/s con corrección de altura Z activa.

---

## Próximos Pasos (Fase 3):
1.  Integración del SDK de LMI Technologies para el control del perfilómetro Gocator.
2.  Sincronización de timestamps entre la posición del robot y las nubes de puntos capturadas.
