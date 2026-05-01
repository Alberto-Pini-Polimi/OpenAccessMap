#!/bin/bash

# Configurazione
ONE_HOUR=3600
UPDATE_CYCLES_BEFORE_TOTAL_UPDATE=3


echo "🤖 Orchestratore avviato. Ciclo: 1 Build + $UPDATE_CYCLES_BEFORE_TOTAL_UPDATE Monitoraggi."

while true; do
    # --- ORA X: BUILD TOTALE ---
    echo ""
    echo "--- [$(date +%T)] FASE 1: Esecuzione serverRoutine.sh (Build) ---"
    ./serverRoutine.sh
    
    for ((i=1; i<=UPDATE_CYCLES_BEFORE_TOTAL_UPDATE; i++)); do
        echo "💤 In attesa per 1 ora..."
        sleep $ONE_HOUR
        
        echo "--- [$(date +%T)] FASE $((i+1)): Esecuzione hourlyMonitor.py (Check $i/$UPDATE_CYCLES_BEFORE_TOTAL_UPDATE) ---"
        python3 app/hourlyMonitor.py # updato le fermate inaccessibili
    done

    echo "💤 Ciclo completato. Aspetto un'ora prima della prossima build..."
    sleep $ONE_HOUR # aspetto ancora un'ora dato che ho appena aggiornato i dati con hourlyMonitor
done