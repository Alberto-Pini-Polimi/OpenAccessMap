#!/bin/bash
set -e

echo "🚀 [$(date +%T)] Avvio container OpenAccessMap Web..."

# 1. Inizializzazione atomica dal template se il volume host è vuoto
if [ ! -f data/OTP_data/staging/MyMilan.osm.pbf ] && [ -d /app/data_template ]; then
    echo "📋 Cartella dati montata vuota: preparo i file in area temporanea..."
    rm -rf data/.tmp_init
    mkdir -p data/.tmp_init
    cp -r /app/data_template/* data/.tmp_init/

    mkdir -p data/.tmp_init/OTP_data/live data/.tmp_init/OTP_data/staging data/.tmp_init/ORS_data
    cp -f data/.tmp_init/OTP_data/otp-config.json data/.tmp_init/OTP_data/live/ 2>/dev/null || true
    cp -f data/.tmp_init/OTP_data/router-config.json data/.tmp_init/OTP_data/live/ 2>/dev/null || true
    cp -f data/.tmp_init/OTP_data/otp-config.json data/.tmp_init/OTP_data/staging/ 2>/dev/null || true
    cp -f data/.tmp_init/OTP_data/build-config.json data/.tmp_init/OTP_data/staging/ 2>/dev/null || true

    # Spostamento atomico nella cartella dati reale
    cp -rn data/.tmp_init/* data/ 2>/dev/null || cp -r data/.tmp_init/* data/
    rm -rf data/.tmp_init
fi

mkdir -p data/OTP_data/live data/OTP_data/staging data/ORS_data
chmod -R 777 data/OTP_data 2>/dev/null || true

# 2. Assicura file di configurazione aggiornati
cp -f data/OTP_data/otp-config.json data/OTP_data/live/ 2>/dev/null || true
cp -f data/OTP_data/router-config.json data/OTP_data/live/ 2>/dev/null || true
cp -f data/OTP_data/otp-config.json data/OTP_data/staging/ 2>/dev/null || true
cp -f data/OTP_data/build-config.json data/OTP_data/staging/ 2>/dev/null || true

# 3. Inizializza schema SQLite se non esiste
python3 -c "from DB.database import get_connection; get_connection()" 2>/dev/null || \
python3 -c "from app.DB.database import get_connection; get_connection()" 2>/dev/null || \
echo "Verifica schema database completata."

# 4. Build iniziale se live/graph.obj non esiste
if [ ! -s data/OTP_data/live/graph.obj ]; then
    echo "⚠️ Nessun graph.obj trovato in data/OTP_data/live! Avvio build iniziale..."
    if [ -f data/OTP_data/staging/MyMilan.osm.pbf ] && [ -f data/OTP_data/staging/Milano-gtfs.zip ]; then
        /bin/bash /app/serverRoutine.sh || echo "⚠️ Build iniziale non terminata, riproverà al prossimo ciclo."
    else
        echo "⚠️ Dati OSM o GTFS mancanti in staging."
    fi
else
    echo "✅ graph.obj presente in live."
fi

# 5. Avvia il server Flask
echo "🌐 Avvio server web Flask..."
exec python3 app/main.py