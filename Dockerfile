FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV WINEDEBUG=-all
ENV WINEPREFIX=/root/.wine

# Installation de Wine 64 bits et utilitaires nécessaires
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
RUN wineboot --init || true

# Port Render
EXPOSE 10000

# Démarrage de l'API FastAPI
CMD ["sh", "-c", "uvicorn api:app --host 0.0.0.0 --port ${PORT:-10000}"]
