FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Installation ultra-rapide de DOSBox (émulateur MS-DOS 16-bit natif pour les moteurs originaux)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        dosbox \
        procps \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copie du code et des moteurs MS-DOS originaux (dos_bins)
COPY . .

EXPOSE 10000

# Démarrage de l'API FastAPI
CMD ["sh", "-c", "uvicorn api:app --host 0.0.0.0 --port ${PORT:-10000}"]
