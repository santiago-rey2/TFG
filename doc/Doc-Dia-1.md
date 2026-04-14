# Informe de Progreso: Puesta en situación y primera toma de contacto (UR10e)

**Fecha:** 9 de mayo de 2026  
**Proyecto:** Sistema de análisis de superficies mediante perfilometría de masas y brazo robótico UR10e.  
**Estado:** Fase 1 - Comunicación y control básico del movimiento.

---

## 1. Acceso y Configuración de Red

En esta primera fase se ha establecido la conectividad con el ecosistema robótico proporcionado por la plataforma **Robotnik**. El sistema integra una base móvil que actúa como gateway para el brazo **Universal Robots UR10e**.

### 1.1. Conexión de Red y HMI
Para interactuar con el sistema, es necesario conectarse a la red WiFi local generada por el controlador del robot:

* **SSID:** `SXLSK-220622AA`
* **PSK:** `R0b0tn1K`

La gestión general de la plataforma móvil (Robotnik) se realiza mediante la interfaz web (HMI) accesible en: `http://192.168.0.200/robotnik_hmi`.

### 1.2. Acceso Remoto al Brazo (UR10e)
Al no disponer físicamente del *Teach Pendant* (consola de control), se han habilitado dos vías de comunicación con el brazo:

1.  **Terminal (SSH):** Para administración del sistema operativo interno.
    * **Comando:** `ssh root@192.168.0.210`
    * **Password:** `easybot`
  
2.  **Interfaz Gráfica (VNC):** Para interactuar con el entorno **Polyscope**. 
    * Se requiere el uso de un cliente como **TightVNC**.
    * **Procedimiento:** Es necesario conectar por SSH previamente y ejecutar el script `start_vnc.sh`. Este indicará el puerto de escucha (habitualmente `50002`).
    * **Password VNC:** `easybot`

---

## 2. Entorno de Control Polyscope

Una vez dentro de la interfaz gráfica, se han identificado los módulos críticos para el desarrollo. Es importante destacar que, aunque el robot tenga corriente, los motores deben activarse manualmente desde el menú de estado (esquina inferior izquierda) para permitir cualquier movimiento.

### Módulos Principales:
* **Move:** Permite el movimiento manual de las articulaciones y la activación del modo **Freedrive** (movimiento libre manual).
* **Program:** Entorno de desarrollo para la lógica de ejecución del brazo.
* **Installation:** Configuración de parámetros de seguridad, TCP (*Tool Center Point*) y planos de referencia.
* **Log:** Registro histórico de eventos, alarmas y errores de ejecución.

---

## 3. Lógica de Programación y Trayectorias

Se ha validado la creación de una rutina de movimiento lineal entre dos puntos predefinidos para simular una pasada de escaneo del perfilómetro.

### 3.1. Análisis de Primitivas de Movimiento
Para que el análisis de superficies sea preciso, se han evaluado los tres tipos de movimiento disponibles:

| Comando | Tipo de Trayectoria | Observación |
| :--- | :--- | :--- |
| **MoveJ** | Movimiento de ejes | No garantiza trayectoria recta; el brazo busca la configuración de motores más eficiente. |
| **MoveL** | **Lineal** | El TCP sigue una línea recta perfecta entre puntos. **Seleccionado para el escaneo.** |
| **MoveP** | De proceso | Mantiene una velocidad constante en curvas. Útil para trayectorias complejas de escaneo continuo. |

### 3.2. Configuración del Programa de Escaneo
Se ha implementado una estructura `MoveL` con dos *Waypoints* (`punto_inicial` y `punto_final`):
* **Velocidad:** Se ha limitado a un máximo de **250 mm/s**.
* **Aceleración:** Ajustada para evitar vibraciones que puedan afectar a la futura lectura del perfilómetro.
* **Control de Parada:** Se ha insertado un comando `Halt` al final del flujo para evitar la ejecución en bucle y garantizar una parada segura tras la pasada.

---

## 4. Comunicación Externa mediante Scripting

Aunque el sistema ofrece integración con **ROS (Robot Operating System)** mediante la directiva *External Control*, se ha decidido explorar una vía de comunicación directa.

El objetivo es desarrollar un protocolo de comunicación general que no dependa estrictamente de los nodos de ROS, permitiendo una mayor portabilidad del sistema de análisis. Para ello:
1.  Se ha comenzado a trabajar con un **script de Python** que utiliza los drivers directos del brazo.
2.  Este script permite enviar comandos de movimiento y recibir telemetría en tiempo real, lo que facilitará la sincronización futura entre la posición del brazo (coordenadas X, Y, Z) y las capturas del perfilómetro de masas.

---
