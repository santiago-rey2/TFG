# Usar una imagen base de Python oficial
FROM python:3.10-slim

# Instalar las dependencias del sistema necesarias para compilar ur_rtde
RUN apt-get update && apt-get install -y \
    cmake \
    libboost-all-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Crear el directorio de trabajo
WORKDIR /app

# Copiar el archivo de requerimientos e instalar dependencias de Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código fuente
COPY src/ ./src/


CMD ["python", "src/robot_status.py"]
