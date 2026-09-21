# Guía de Formatos de Rutas y Trayectorias (UR10e & Gocator 2600)

Este directorio contiene las definiciones de rutas de movimiento e inspección para el robot UR10e y el perfilómetro Gocator.

Las rutas pueden definirse en dos formatos de archivo: **JSON** y **CSV**, o bien pasarse directamente por **Consola (CLI)**.

---

## 1. Tipos de Movimiento Soportados

| Tipo de Movimiento | Función `ur_rtde` | Parámetros Clave | Descripción |
| :--- | :--- | :--- | :--- |
| **`lineal`** | `moveL` | `destino`, `velocidad`, `aceleracion` | Movimiento en línea recta cartesiana del TCP. |
| **`circular`** | `moveC` | `pose_via`, `destino`, `blend_radius`, `modo_orientacion` | Movimiento en arco pasando por `pose_via` hasta alcanzar `destino`. |

> **Nota sobre movimientos circulares (`moveC`):**
> Requieren obligatoriamente un punto intermedio (`pose_via` o columnas `via_*`) y el punto final (`destino`). El punto inicial es la posición actual en la que se encuentra el robot.

---

## 2. Tipos de Coordenadas

* **`articulares_deg`**: 6 ángulos en grados `[Base, Shoulder, Elbow, Wrist 1, Wrist 2, Wrist 3]` (ej. `[60.0, -118.0, -75.0, -75.0, 89.0, 149.0]`). Se convierten automáticamente a radianes y se calcula su pose TCP mediante cinemática directa.
* **`articulares_rad`**: 6 ángulos en radianes.
* **`cartesianas`**: Vector cartesiano del TCP `[X, Y, Z, Rx, Ry, Rz]` donde $X, Y, Z$ están en metros y $Rx, Ry, Rz$ son el vector de rotación en radianes.

---

## 3. Formato JSON

El formato JSON es el más flexible y expresivo. Permite definir parámetros globales por defecto, puntos de referencia y una lista de pasos (`rutas`).

### Ejemplo:
```json
{
  "nombre_trayectoria": "Soldadura_Mixta",
  "descripcion": "Aproximacion, barrido lineal y tramo curvo",
  "parametros_defecto": {
    "velocidad": 0.05,
    "aceleracion": 0.2,
    "forzar_z_constante": true,
    "lead_in_mm": 20.0,
    "lead_out_mm": 20.0
  },
  "rutas": [
    {
      "id": 1,
      "nombre": "Aproximacion_Home",
      "tipo_movimiento": "lineal",
      "tipo_coordenadas": "articulares_deg",
      "destino": [60.0, -118.0, -75.0, -75.0, 89.0, 149.0],
      "escanear": false
    },
    {
      "id": 2,
      "nombre": "Barrido_Lineal_Soldadura",
      "tipo_movimiento": "lineal",
      "tipo_coordenadas": "articulares_deg",
      "origen": [60.0, -118.0, -75.0, -75.0, 89.0, 149.0],
      "destino": [132.0, -108.0, -87.0, -72.0, 90.0, 220.0],
      "velocidad": 0.05,
      "escanear": true
    },
    {
      "id": 3,
      "nombre": "Inspeccion_Arco_Curvo",
      "tipo_movimiento": "circular",
      "tipo_coordenadas": "cartesianas",
      "pose_via": [0.450, -0.200, 0.150, 3.1415, 0.0, 0.0],
      "destino": [0.500, -0.150, 0.150, 3.1415, 0.0, 0.0],
      "blend_radius": 0.01,
      "modo_orientacion": 0,
      "escanear": true
    }
  ]
}
```

---

## 4. Formato CSV

El formato CSV es ideal para editar secuencias de puntos en hojas de cálculo como Microsoft Excel o LibreOffice Calc.

### Estructura de Columnas:
```csv
id,nombre,tipo_movimiento,tipo_coordenadas,escanear,velocidad,aceleracion,blend_radius,x,y,z,rx,ry,rz,via_x,via_y,via_z,via_rx,via_ry,via_rz
```

* Si `tipo_coordenadas` es `articulares_deg`, los campos `x, y, z, rx, ry, rz` corresponden a los 6 ángulos articulares en grados: `q1, q2, q3, q4, q5, q6`.
* Si `tipo_movimiento` es `lineal`, los campos `via_*` pueden dejarse vacíos.
* Si `tipo_movimiento` es `circular`, los campos `via_*` representan el punto intermedio de la circunferencia/arco.
* `escanear`: `true` o `false`.

---

## 5. Ejemplos de Ejecución desde Consola

### Con Docker Compose:
```bash
# 1. Ejecutar escaneo sincronizado con archivo JSON
docker compose run scan python src/scan_sync.py --json routes/default_tfg.json

# 2. Ejecutar movimiento sin sensor con archivo CSV
docker compose run movement python src/robot_movement.py --csv routes/ejemplo_ruta.csv

# 3. Modo interactivo asistido en consola
docker compose run scan python src/scan_sync.py --interactivo

# 4. Movimiento lineal rápido directamente por CLI
docker compose run scan python src/scan_sync.py --modo cli --tipo-mov lineal \
    --coord-tipo articulares_deg \
    --origen 60 -118 -75 -75 89 149 \
    --destino 132 -108 -87 -72 90 220 \
    --escanear --velocidad 0.05
```

### Ejecución Directa (Python local):
```bash
python src/scan_sync.py --json routes/default_tfg.json
python src/robot_movement.py --csv routes/ejemplo_ruta.csv
```
