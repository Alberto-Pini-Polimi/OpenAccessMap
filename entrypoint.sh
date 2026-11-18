#!/bin/bash
set -e

echo "🚀 [$(date +%T)] Avvio container OpenAccessMap Web..."

# 1. Se il volume montato dall'host è vuoto o mancano i file sorgente, inizializza dal template
if [ ! -f data/OTP_data/staging/MyMilan.osm.pbf ] && [ -d /app/data_template ]; then
    echo "📋 Cartella dati montata vuota o incompleta: inizializzo i file di base da /app/data_template..."
    mkdir -p data/OTP_data/staging data/OTP_data/live data/ORS_data
    cp -rn /app/data_template/* data/ 2>/dev/null || cp -r /app/data_template/* data/
fi

mkdir -p data/OTP_data/live data/OTP_data/staging data/ORS_data
chmod -R 777 data/OTP_data 2>/dev/null || true

# 2. Assicura file di configurazione
cp -n data/OTP_data/otp-config.json data/OTP_data/live/ 2>/dev/null || true
cp -n data/OTP_data/router-config.json data/OTP_data/live/ 2>/dev/null || true
cp -n data/OTP_data/build-config.json data/OTP_data/staging/ 2>/dev/null || true

# 3. Inizializza schema SQLite se non esiste
python3 -c "from DB.database import get_connection; get_connection()" 2>/dev/null || \
python3 -c "from app.DB.database import get_connection; get_connection()" 2>/dev/null || \
echo "Verifica schema database completata."

# 4. Se live/graph.obj non esiste ancora (primo deployment), avvia la routine di build iniziale
if [ ! -s data/OTP_data/live/graph.obj ]; then
    echo "⚠️ Nessun graph.obj trovato in data/OTP_data/live! Avvio build iniziale..."
    if [ -f data/OTP_data/staging/MyMilan.osm.pbf ] && [ -f data/OTP_data/staging/Milano-gtfs.zip ]; then
        /bin/bash /app/serverRoutine.sh || echo "⚠️ Build iniziale non terminata con successo, il container builder o OTP riproveranno."
    else
        echo "⚠️ Dati OSM o GTFS mancanti in staging. Assicurati che MyMilan.osm.pbf e Milano-gtfs.zip siano in /opt/openaccessmap/data/OTP_data/staging."
    fi
else
    echo "✅ graph.obj presente in live."
fi

# 5. Avvia il server Flask
echo "🌐 Avvio server web Flask..."
exec python3 app/main.py
