# ==========================================
# Etapa 1: Builder (Construcción)
# ==========================================
FROM python:3.11-slim-bookworm AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    cmake \
    build-essential \
    libboost-all-dev \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt


# ==========================================
# Etapa 2: Runner (Imagen Final Ligera)
# ==========================================
FROM python:3.11-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    libboost-system1.81.0 \
    libboost-thread1.81.0 \
    libboost-program-options1.81.0 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app
COPY src/ ./src/
COPY routes/ ./routes/

CMD ["python", "src/robot_status.py"]