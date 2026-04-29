#!/bin/bash

echo ""
echo "🚀 Avvio aggiornamento OTP per Milano..."

# 1/5 - Spegni il servizio
echo "prima fermo il servizio OTP!"
docker compose down
if [ $? -ne 0 ]; then
    echo "❌ Errore durante l'arresto del servizio"
    exit 1
fi

echo ""

# 2/5 - Esegui lo script di aggiornamento GTFS
echo "🔄 2/5 - Eseguo dailyGTFSzipUpdater.py..."
python3 app/dailyGTFSzipUpdater.py
if [ $? -ne 0 ]; then
    echo "❌ Errore durante l'aggiornamento GTFS"
    exit 1
fi

echo ""

# 3/5 - Elimina graph.obj vecchio
echo "🗑️ 3/5 - Rimuovo graph.obj esistente..."
rm -f data/OTP_data/graph.obj
echo "✅ graph.obj rimosso (se presente)"

echo ""

# 4/5 - Ribuilda OTP con timer
echo "🏗️ 4/5 - Avvio build OTP con nuovi dati..."
echo "⏳ Build in corso... (questo potrebbe richiedere alcuni minuti)"
start_time=$(date +%s)
docker compose run --rm otp-builder > /dev/null 2>&1
end_time=$(date +%s)
duration=$((end_time - start_time))
echo "✅ Build completata in $duration secondi"

echo ""

# 5/5 - Istruzioni per avvio manuale
echo "📌 5/5 - Avvio servizio in background"
docker compose up -d
echo "✅ servizio avviato"

echo ""
echo "📜 I log di python-app verranno salvati in 'server.log' in background..."
docker compose logs -f python-app > server.log 2>&1 &