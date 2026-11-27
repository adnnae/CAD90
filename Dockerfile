FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV WINEDEBUG=-all
ENV WINEPREFIX=/root/.wine
ENV DISPLAY=:99
ENV XDG_RUNTIME_DIR=/root/.runtime

# Installation des dépendances système, Wine 32/64 bits, Xvfb, wget et ca-certificates
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

# Installation de Wine-Mono (nécessaire pour exécuter les binaires .NET v4.0.30319 comme CASIMPLE)
RUN mkdir -p /usr/share/wine/mono && \
    wget -q -O /usr/share/wine/mono/wine-mono-9.4.0-x86.msi https://dl.winehq.org/wine/wine-mono/9.4.0/wine-mono-9.4.0-x86.msi

WORKDIR /app

# Installation des dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copie du projet et des binaires
COPY . .

# Initialisation de Wine avec Wine-Mono
RUN mkdir -p /root/.runtime && chmod 700 /root/.runtime && \
    mkdir -p /root/.wine && \
    Xvfb :99 -screen 0 1024x768x16 & \
    sleep 1 && \
    wine msiexec /i /usr/share/wine/mono/wine-mono-9.4.0-x86.msi || true && \
    wineboot --init || true

EXPOSE 10000

# Lancement de Xvfb et de l'API FastAPI
CMD ["sh", "-c", "Xvfb :99 -screen 0 1024x768x16 & sleep 1 && uvicorn api:app --host 0.0.0.0 --port ${PORT:-10000}"]
