#!/bin/bash
set -e

DOCKER_SOCK="/var/run/docker.sock"

# Helper: chiama le API Docker via socket senza il binario docker
docker_api() {
    curl -s --unix-socket "$DOCKER_SOCK" "$@"
}

# Avvia un container per nome e aspetta che finisca
docker_start_and_wait() {
    local name="$1"
    echo "▶ Avvio container $name via Docker API..."
    docker_api -X POST "http://localhost/containers/$name/start"

    echo "⏳ Attendo che $name finisca..."
    while true; do
        state=$(docker_api "http://localhost/containers/$name/json" | \
            python3 -c "import sys,json; d=json.load(sys.stdin); print(d['State']['Running'])" 2>/dev/null)
        if [ "$state" = "False" ]; then
            break
        fi
        sleep 5
    done

    exit_code=$(docker_api "http://localhost/containers/$name/json" | \
        python3 -c "import sys,json; d=json.load(sys.stdin); print(d['State']['ExitCode'])" 2>/dev/null)
    echo "✅ Container $name terminato con exit code: $exit_code"
    return "$exit_code"
}

# Riavvia un container per nome
docker_restart() {
    local name="$1"
    echo "🔄 Riavvio container $name via Docker API..."
    docker_api -X POST "http://localhost/containers/$name/restart"
}

# Verifica se un container è in esecuzione
docker_is_running() {
    local name="$1"
    state=$(docker_api "http://localhost/containers/$name/json" | \
        python3 -c "import sys,json; d=json.load(sys.stdin); print(d['State']['Running'])" 2>/dev/null)
    [ "$state" = "True" ]
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

# Se il grafo non esiste ancora (es. primo avvio con race condition), avvia il builder
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
