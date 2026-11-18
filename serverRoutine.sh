#!/bin/bash
set -e

echo "🚀 [$(date +%T)] Avvio aggiornamento OTP in staging..."
mkdir -p data/OTP_data/live data/OTP_data/staging
chmod -R 777 data/OTP_data 2>/dev/null || true
rm -f data/OTP_data/staging/graph.obj
rm -rf data/OTP_data/staging/tmp_gtfs_unzip

# Assicura la presenza dei file di configurazione
cp -f data/OTP_data/build-config.json data/OTP_data/staging/ 2>/dev/null || true
cp -f data/OTP_data/otp-config.json data/OTP_data/staging/ 2>/dev/null || true
cp -f data/OTP_data/router-config.json data/OTP_data/staging/ 2>/dev/null || true
cp -f data/OTP_data/otp-config.json data/OTP_data/live/ 2>/dev/null || true
cp -f data/OTP_data/router-config.json data/OTP_data/live/ 2>/dev/null || true

echo "🔄 1/3 - Scarico e aggiorno GTFS in staging..."
python3 app/dailyGTFSzipUpdater.py

echo "🏗️ 2/3 - Compilo graph.obj in staging (l'app resta online)..."
if ! command -v docker &>/dev/null; then
    echo "❌ ERRORE: Il comando 'docker' non è installato in questo container."
    echo "💡 Ricostruisci l'immagine da Portainer (toggle 'Re-build image') oppure dall'host con: docker compose build --no-cache python-app"
    echo "👉 In alternativa puoi avviare il builder direttamente dall'host: docker start -a openaccessmap-builder"
    exit 1
fi
start_time=$(date +%s)
if [ "$(docker inspect -f '{{.State.Running}}' openaccessmap-builder 2>/dev/null)" = "true" ]; then
    echo "⏳ openaccessmap-builder è già in esecuzione, attendo il termine..."
    docker wait openaccessmap-builder
fi

# Se il grafo non è ancora stato generato (es. il primo avvio parallelo è fallito a cartella vuota), avvialo ora
if [ ! -s data/OTP_data/staging/graph.obj ]; then
    echo "🏗️ Avvio compilazione con openaccessmap-builder..."
    docker start -a openaccessmap-builder
fi
end_time=$(date +%s)
echo "✅ Build completata in $((end_time - start_time)) secondi"

if [ ! -s data/OTP_data/staging/graph.obj ]; then
    echo "❌ ERRORE: graph.obj non generato. Mantengo il grafo live precedente."
    exit 1
fi

echo "🔄 3/3 - Sostituisco graph.obj e riavvio OTP..."
mv -f data/OTP_data/staging/graph.obj data/OTP_data/live/graph.obj
chmod 666 data/OTP_data/live/graph.obj 2>/dev/null || true
docker restart openaccessmap-otp
echo "🎉 [$(date +%T)] Aggiornamento completato!"
