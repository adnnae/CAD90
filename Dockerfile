FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV WINEDEBUG=-all
ENV WINEPREFIX=/root/.wine
ENV DISPLAY=:99
ENV XDG_RUNTIME_DIR=/tmp/runtime-root

# Installation de Wine 64 bits et Xvfb
RUN dpkg --add-architecture amd64 && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        wine64 \
        wine \
        procps \
        xvfb \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Installation des dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copie de l'application et des moteurs legacy_bins
COPY . .

# Initialisation de Wine
RUN mkdir -p /tmp/runtime-root && chmod 700 /tmp/runtime-root && wineboot --init || true

# Port Render
EXPOSE 10000

# Démarrage de Xvfb (serveur d'affichage virtuel) puis de FastAPI
CMD ["sh", "-c", "Xvfb :99 -screen 0 1024x768x16 & sleep 1 && uvicorn api:app --host 0.0.0.0 --port ${PORT:-10000}"]
