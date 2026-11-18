#!/bin/bash
set -e

echo "🚀 [$(date +%T)] Avvio aggiornamento OTP in staging..."
mkdir -p data/OTP_data/live data/OTP_data/staging
chmod -R 777 data/OTP_data 2>/dev/null || true
rm -f data/OTP_data/staging/graph.obj

# Assicura la presenza dei file di configurazione
cp -n data/OTP_data/build-config.json data/OTP_data/staging/ 2>/dev/null || true
cp -n data/OTP_data/otp-config.json data/OTP_data/staging/ 2>/dev/null || true
cp -n data/OTP_data/router-config.json data/OTP_data/staging/ 2>/dev/null || true
cp -n data/OTP_data/otp-config.json data/OTP_data/live/ 2>/dev/null || true
cp -n data/OTP_data/router-config.json data/OTP_data/live/ 2>/dev/null || true

echo "🔄 1/3 - Scarico e aggiorno GTFS in staging..."
python3 app/dailyGTFSzipUpdater.py

echo "🏗️ 2/3 - Compilo graph.obj in staging (l'app resta online)..."
start_time=$(date +%s)
if [ "$(docker inspect -f '{{.State.Running}}' openaccessmap-builder 2>/dev/null)" = "true" ]; then
    echo "⏳ openaccessmap-builder è già in esecuzione, attendo il termine..."
    docker wait openaccessmap-builder
else
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
