#!/bin/bash
set -e

DOCKER_SOCK="/var/run/docker.sock"
DS="python3 /app/app/docker_socket.py"

# Avvia un container e aspetta che finisca
docker_start_and_wait() {
    local name="$1"
    echo "▶ Avvio container $name..."
    $DS start "$name"

    echo "⏳ Attendo che $name finisca..."
    while [ "$($DS is_running "$name" 2>/dev/null)" = "True" ]; do
        sleep 5
    done

    local exit_code
    exit_code=$($DS exit_code "$name" 2>/dev/null)
    echo "Container $name terminato con exit code: $exit_code"
    return "$exit_code"
}

# Riavvia un container
docker_restart() {
    local name="$1"
    echo "🔄 Riavvio container $name..."
    $DS restart "$name"
}

# Verifica se un container è in esecuzione
docker_is_running() {
    local name="$1"
    [ "$($DS is_running "$name" 2>/dev/null)" = "True" ]
}

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

# Verifica che il socket Docker sia accessibile
if [ ! -S "$DOCKER_SOCK" ]; then
    echo "❌ ERRORE: Docker socket non trovato in $DOCKER_SOCK"
    exit 1
fi

start_time=$(date +%s)

# Se il builder è già in esecuzione, aspetta che finisca
if docker_is_running "openaccessmap-builder"; then
    echo "⏳ openaccessmap-builder già in esecuzione, attendo termine..."
    while docker_is_running "openaccessmap-builder"; do sleep 5; done
fi

# Avvia il builder (o riavvialo se il grafo non c'è ancora per race condition al primo boot)
if [ ! -s data/OTP_data/staging/graph.obj ]; then
    docker_start_and_wait "openaccessmap-builder"
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
docker_restart "openaccessmap-otp"
echo "🎉 [$(date +%T)] Aggiornamento completato!"
