FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV WINEDEBUG=-all
ENV WINEPREFIX=/root/.wine
ENV DISPLAY=:99
ENV XDG_RUNTIME_DIR=/root/.runtime

# Installation du support multiarch 32-bit (i386) et 64-bit pour Wine
RUN dpkg --add-architecture i386 && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        wine \
        wine32 \
        wine64 \
        procps \
        xvfb \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Installation des dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copie du projet et des binaires legacy_bins
COPY . .

# Préparation du répertoire runtime et initialisation silencieuse de Wine
RUN mkdir -p /root/.runtime && chmod 700 /root/.runtime && \
    mkdir -p /root/.wine && wineboot --init || true

EXPOSE 10000

# Lancement de Xvfb et de l'API FastAPI
CMD ["sh", "-c", "Xvfb :99 -screen 0 1024x768x16 & sleep 1 && uvicorn api:app --host 0.0.0.0 --port ${PORT:-10000}"]
