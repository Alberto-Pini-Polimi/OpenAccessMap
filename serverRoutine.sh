#!/bin/bash
set -e

echo "🚀 [$(date +%T)] Avvio aggiornamento OTP in staging..."
mkdir -p data/OTP_data/live data/OTP_data/staging
rm -f data/OTP_data/staging/graph.obj

echo "🔄 1/3 - Scarico e aggiorno GTFS in staging..."
python3 app/dailyGTFSzipUpdater.py

echo "🏗️ 2/3 - Compilo graph.obj in staging (l'app resta online)..."
start_time=$(date +%s)
docker start -a openaccessmap-builder
end_time=$(date +%s)
echo "✅ Build completata in $((end_time - start_time)) secondi"

if [ ! -s data/OTP_data/staging/graph.obj ]; then
    echo "❌ ERRORE: graph.obj non generato. Mantengo il grafo live precedente."
    exit 1
fi

echo "🔄 3/3 - Sostituisco graph.obj e riavvio OTP..."
mv -f data/OTP_data/staging/graph.obj data/OTP_data/live/graph.obj
docker restart openaccessmap-otp
echo "🎉 [$(date +%T)] Aggiornamento completato!"