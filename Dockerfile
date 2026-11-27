FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV WINEDEBUG=-all
ENV WINEPREFIX=/root/.wine

# Installation de Wine 64 bits et utilitaires
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

# Copie de l'ensemble du projet (code et moteurs legacy_bins)
COPY . .

# Initialisation silencieuse de l'environnement Wine
RUN wineboot --init || true

# Port Render (par défaut 10000)
EXPOSE 10000

# Commande de démarrage Streamlit
CMD ["sh", "-c", "streamlit run app_web.py --server.port=${PORT:-10000} --server.address=0.0.0.0 --server.headless=true"]
