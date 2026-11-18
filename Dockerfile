# Usa un'immagine Python leggera ma completa
FROM python:3.10-slim

# Installa le dipendenze di sistema necessarie per librerie spaziali come shapely e pyproj
RUN apt-get update && apt-get install -y --no-install-recommends docker.io && rm -rf /var/lib/apt/lists/*

# Imposta la cartella di lavoro dentro il container
WORKDIR /usr/src/project

# Copia il requirements e installa le dipendenze
COPY app/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Il codice vero e proprio lo monteremo tramite docker-compose per comodità,
# ma definiamo il comando di default per tenere in vita il container
CMD ["python", "app/main.py"]