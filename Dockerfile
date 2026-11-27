FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV WINEDEBUG=-all
ENV WINEPREFIX=/root/.wine
ENV DISPLAY=:99

# Installation de Wine 32/64 bits, Xvfb et utilitaires de téléchargement
RUN dpkg --add-architecture i386 && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        wine \
        wine32 \
        wine64 \
        procps \
        xvfb \
        wget \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Téléchargement du composant officiel Wine-Mono dans le dossier standard où Wine le cherche
RUN mkdir -p /usr/share/wine/mono && \
    wget -q -O /usr/share/wine/mono/wine-mono-9.4.0-x86.msi https://dl.winehq.org/wine/wine-mono/9.4.0/wine-mono-9.4.0-x86.msi

WORKDIR /app

# Installation des dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copie de l'application et des binaires
COPY . .

# Initialisation silencieuse du wineprefix avec Mono (SANS daemon d'arrière-plan bloquant)
RUN mkdir -p /root/.runtime && chmod 700 /root/.runtime && \
    wineboot -u || true

EXPOSE 10000

# Démarrage de Xvfb et de l'API FastAPI au runtime uniquement
CMD ["sh", "-c", "Xvfb :99 -screen 0 1024x768x16 & sleep 1 && uvicorn api:app --host 0.0.0.0 --port ${PORT:-10000}"]
