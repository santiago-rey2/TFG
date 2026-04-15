# TFG: Análisis de datos - Gocator 2600 & UR10e

Este repositorio contiene las herramientas de comunicación y control desarrolladas para el Trabajo de Fin de Grado centrado en el escaneo y análisis de datos con un perfilómetro **Gocator 2600** montado en un robot **UR10e**.

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

Antes de iniciar los servicios, debes configurar la dirección IP de tu robot:

1.  Crea un archivo llamado `.env` en la raíz del proyecto (puedes copiar el ejemplo si existe).
2.  Define la variable `ROBOT_IP`:
    ```env
    ROBOT_IP=192.168.1.210
    ```

---

## 📦 Guía de Uso con Docker Compose

La imagen de Docker incluye todas las dependencias necesarias (`cmake`, `libboost-all-dev`, `ur_rtde`) pre-instaladas y configuradas.

### 1. Construcción de la imagen
Si es la primera vez que usas el proyecto o has realizado cambios en el código:
```bash
docker compose build
```

### 2. Verificar Conexión (Status)
Utiliza este comando para confirmar que el robot es accesible y ver su posición actual:
```bash
docker compose run status
```

### 3. Ejecutar Trayectoria de Escaneo (Movement)
Este comando moverá el robot desde la posición de **Origen** a la de **Fin** de manera lineal, asegurando una altura (Z) constante:
```bash
docker compose run movement
```

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

## 📁 Estructura del Proyecto

*   `src/`: Scripts de control en Python.
*   `doc/`: Documentación adicional y capturas del proyecto.
*   `Dockerfile`: Definición de la imagen de compilación.
*   `docker-compose.yml`: Orquestación de servicios de ejecución.
*   `GEMINI.md`: Contexto extendido para el desarrollo asistido por IA.
