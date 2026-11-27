FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV WINEDEBUG=-all
ENV WINEPREFIX=/root/.wine
ENV DISPLAY=:99

# Installation de Wine 32/64 bits, Xvfb et wget
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

# Téléchargement et installation silencieuse de Wine-Mono (requis pour .NET 4.0)
RUN mkdir -p /usr/share/wine/mono /root/.wine && \
    wget -q -O /usr/share/wine/mono/wine-mono-9.4.0-x86.msi https://dl.winehq.org/wine/wine-mono/9.4.0/wine-mono-9.4.0-x86.msi && \
    DISPLAY="" WINEDLLOVERRIDES="mscoree,mshtml=" wineboot --init && \
    DISPLAY="" wine msiexec /i /usr/share/wine/mono/wine-mono-9.4.0-x86.msi /qn && \
    wineserver -w

WORKDIR /app

# Dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copie du code et des moteurs
COPY . .

EXPOSE 10000

# Démarrage propre en production
CMD ["sh", "-c", "Xvfb :99 -screen 0 1024x768x16 & sleep 1 && uvicorn api:app --host 0.0.0.0 --port ${PORT:-10000}"]
