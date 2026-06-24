import json
from pathlib import Path

# file di estrazione
from extractScraperData import DATA_URL, getData, Station

OTP_DATA_FOLDER = Path(__file__).resolve().parent.parent / "data/OTP_data"
BASELINE_FILE = OTP_DATA_FOLDER / "daily_accessibility_baseline.json"
# Nuovo path per il file di testo
OUTPUT_FILE = OTP_DATA_FOLDER / "inaccessible_stations_till_last_GTFSzip_file_update.txt"

def check_new_breakdowns():
    print("🔍 Controllo orario guasti ascensori/scale mobili...")
    
    # 1. Controlliamo se esiste la baseline delle 24H
    if not BASELINE_FILE.exists():
        print("⚠️ Nessun file baseline trovato. Fai girare prima GTFSzipUpdater.py!")
        return
        
    with open(BASELINE_FILE, 'r') as f:
        daily_baseline = json.load(f)

    # 2. Scarichiamo i dati live dallo scraper
    live_data = getData(DATA_URL)
    if not live_data:
        print("❌ Errore nel recupero dati live.")
        return
        
    # 3. Creiamo gli oggetti per valutare l'accessibilità live
    live_stations = {s["station_name"].upper(): Station(s) for s in live_data}
    
    broken_stations = []

    # 4. Confrontiamo!
    for name, live_station in live_stations.items():
        # Se la stazione esiste nella nostra baseline
        if name in daily_baseline:
            was_accessible = daily_baseline[name]
            is_accessible_now = live_station.definedAsAccessible()
            
            # Se all'aggiornamento del GTFS era accessibile, ma ORA NON lo è più:
            if was_accessible and not is_accessible_now:
                broken_stations.append(name) # aggiungo il nome della stazione al file

    # 5. Scriviamo/Aggiorniamo il file di output
    # Sovrascriviamo il file ('w') ad ogni esecuzione. (per garantire che le riparazioni di stazioni siano considerati di nuovo come funzionanti)
    try:
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as out_f:
            for station in broken_stations:
                out_f.write(f"{station}\n")
        print(f"📝 File '{OUTPUT_FILE.name}' aggiornato con successo.")
    except Exception as e:
        print(f"❌ Errore durante la scrittura del file di output: {e}")

    # 6. Risultati a schermo
    if broken_stations:
        print(f"🚨 ATTENZIONE! Rilevati {len(broken_stations)} guasti rispetto all'ultimo aggiornamento GTFS:")
        for station in sorted(broken_stations):
            print(f"   ❌ {station}")
    else:
        print("✅ Nessun nuovo guasto rilevante. Tutte le stazioni accessibili prima lo sono ancora.")

if __name__ == "__main__":
    check_new_breakdowns()