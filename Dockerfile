# Usa un'immagine Python leggera ma completa
FROM python:3.10-slim

# Installa il client Docker per pilotare i container otp e otp-builder tramite socket
RUN apt-get update && apt-get install -y --no-install-recommends docker.io && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copia e installa le dipendenze Python
COPY app/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copia l'intero progetto dentro il container
COPY . /app

# Crea la cartella template di backup per inizializzare il volume montato dall'host se vuoto
RUN cp -r /app/data /app/data_template

# Rendi eseguibili gli script
RUN chmod +x /app/serverRoutine.sh /app/entrypoint.sh /app/main.sh

ENTRYPOINT ["/bin/bash", "/app/entrypoint.sh"]
