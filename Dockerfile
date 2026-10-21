# ==========================================
# Etapa 1: Builder (Instalación y Limpieza)
# ==========================================
FROM python:3.11-slim-bookworm AS builder

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Limpieza exhaustiva del entorno virtual para minimizar el tamaño final:
# - Eliminar tests y archivos de documentación de paquetes
# - Eliminar cachés bytecode __pycache__ y *.pyc
# - Eliminar herramientas de instalación pip y setuptools (innecesarias en runtime)
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

# Copiar únicamente el entorno virtual optimizado (sin capas extras de apt ni librerías redundantes)
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app
COPY src/ ./src/
COPY config/ ./config/
COPY points/ ./points/

CMD ["python", "src/main.py"]