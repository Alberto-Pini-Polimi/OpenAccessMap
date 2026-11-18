import os
import csv
import zipfile
import shutil
import json # Aggiunto per salvare lo stato giornaliero
from pathlib import Path

# IMPORTO DAL PRIMO FILE!
from extractScraperData import DATA_URL, getData, Station

# path to the OTP data folder
BASE_OTP_DATA = Path(__file__).resolve().parent.parent / "data/OTP_data"
STAGING_FOLDER = BASE_OTP_DATA / "staging"
GTFS_FILE_PATH = STAGING_FOLDER / "Milano-gtfs.zip"

# File di appoggio per passare lo stato al terzo script (nella root di OTP_data per hourlyMonitor e maps)
BASELINE_FILE = BASE_OTP_DATA / "daily_accessibility_baseline.json"
# file di aggiornamento orario con i nuovi updates sull'accessibilità rispetto
# al momento in cui il GTFS viene aggiornato
HOURLY_DATA_UPDATE_FILE = BASE_OTP_DATA / "inaccessible_stations_till_last_GTFSzip_file_update.txt"

def unzip_gtfs(zip_path, extract_to):
    """Estrae il contenuto del file ZIP in una cartella specifica."""
    print(f"📦 Estrazione di {zip_path.name}...")
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_to)

def zip_gtfs(folder_to_zip, output_zip_path):
    """Comprime il contenuto della cartella in un file ZIP (senza includere la cartella stessa)."""
    print(f"🔒 Compressione in {output_zip_path.name}...")
    with zipfile.ZipFile(output_zip_path, 'w', zipfile.ZIP_DEFLATED) as zip_ref:
        for root, dirs, files in os.walk(folder_to_zip):
            for file in files:
                file_path = os.path.join(root, file)
                # arcname serve per non creare sottocartelle inutili dentro lo zip
                zip_ref.write(file_path, arcname=os.path.relpath(file_path, folder_to_zip))



def update_stops_file(stationsDictionary, stops_file_path):
    """Logica di modifica del file stops.txt."""

    # controllo che il file CSV esista nella stessa directory
    if not os.path.exists(stops_file_path):
        print(f"❌ Errore: {stops_file_path} non trovato.")
        return False

    # tengo traccia di cosa modifico così che alla fine posso scrivere le modifche sul file
    updatesToFile = []
    
    # apro in lettura il file stops.txt
    with open(stops_file_path, mode='r', encoding='utf-8') as file:
        # DictReader ci permette di interagire con le colonne usando il loro nome
        reader = csv.DictReader(file, quotechar='"')
        fieldnames = reader.fieldnames # Salviamo l'intestazione originale

        for row in reader:

            # devo assicurarmi che sia una fermata della metro quella che ho trovato nella row del file CSV
            # capisco che è uno stop della metro perchè il suo id non è numerico
            if row["stop_id"].isdigit():
                updatesToFile.append(row) # però mi salvo cmq la linea
                continue

            # prendo il nome della stazione in stops.txt
            stopNameCSV = row["stop_name"].upper()
            
            # ricerchiamo la stazione corrispondente nei dati dello scraper.
            matchedStation = None
            for stopNameScraper, stationObject in stationsDictionary.items():
                # se il nome della stazione scrapata è contenuto in quello di stops.txt o viceversa
                # per esempio il caso in cui il CSV abbia "CADORNA FN M1" e lo scraper abbia solo "CADORNA" 
                if stopNameScraper in stopNameCSV or stopNameCSV in stopNameScraper:
                    matchedStation = stationObject
                    break
            
            # se troviamo la stazione del file CSV, gli aggiorniamo il campo "wheelchair_boarding"
            # la scrittura avvine dopo la ricerca intera per questioni di performance
            if matchedStation:
                # per lo standard GTFS:
                # 1 = Accessibile, 2 = Non accessibile (0 o vuoto = info non disponibile)
                # faccio il controllo col metodo definedAsAccessible() definito nella classe
                row["wheelchair_boarding"] = "1" if matchedStation.definedAsAccessible() else "2"
            
            # mi salvo le righe aggiornate
            updatesToFile.append(row)

    # riscrivo il file stops.txt con le righe aggiornate
    with open(stops_file_path, mode='w', encoding='utf-8') as outfile:
        # scriviamo l'intestazione forzando le virgolette
        headerLine = ",".join(f'"{col}"' for col in fieldnames) + "\n"
        outfile.write(headerLine)

        # scrivo ogni riga formattata in modo da mettere le "virgolette" solo se il campo non è vuoto
        for row in updatesToFile:
            rowValues = [] # traccio i valori della riga
            for col in fieldnames: # per ogni colonna
                val = row.get(col, "") # prendo il suo valore
                # se il campo contiene qualcosa aggiungiamo le virgolette, 
                # altrimenti lo lasciamo completamente vuoto
                if val != "":
                    rowValues.append(f'"{val}"')
                else:
                    rowValues.append("")
                    
            outfile.write(",".join(rowValues) + "\n") # finalmente scrivo sul file
    
    print("✅ stops.txt aggiornato con successo.")
    return True

def onceEach24H():
    print("🚀 Avvio procedura di aggiornamento giornaliera...")
    data = getData(DATA_URL)
    if not data:
        print("❌ Impossibile recuperare i dati. Abortito.")
        return
    
    stations_dict = {s["station_name"].upper(): Station(s) for s in data}
    
    # salviamo la situazione "di base" di oggi per lo script orario
    # in questo modo l'altro script sa esattamente qual è lo stato di accessibilità
    # quando il file graph.obj è stato creato.
    # l'idea è che poi si riesce ad avvisare l'utente nel caso una fermata dovessere
    # diventare inaccessibile nelle ore fra l'ultimo aggiornamento del file graph.obj
    # e il momento in cui l'utente cerca il percorso
    daily_status = {name: station.definedAsAccessible() for name, station in stations_dict.items()}
    BASE_OTP_DATA.mkdir(parents=True, exist_ok=True)
    STAGING_FOLDER.mkdir(parents=True, exist_ok=True)

    with open(BASELINE_FILE, 'w') as f:
        json.dump(daily_status, f)
    print("💾 Stato giornaliero salvato per il monitoraggio orario.")

    # ora cancello i dati del monitoraggio orario delle 24h ormai passate (una sorta di reset)
    open(HOURLY_DATA_UPDATE_FILE, "w").close()

    extraction_folder = STAGING_FOLDER / "tmp_gtfs_unzip"

    try:
        # unzip del gtfs
        unzip_gtfs(GTFS_FILE_PATH, extraction_folder)
        
        # update the stops.txt file with new accessibility data
        file_stops_extracted = extraction_folder / "stops.txt"
        update_stops_file(stations_dict, file_stops_extracted)

        # zip the folder into the Milano-gtfs.zip for the next build to use it
        zip_gtfs(extraction_folder, GTFS_FILE_PATH)

    except Exception as e:
        print(f"Errore: {e}")
    finally:
        if extraction_folder.exists():
            shutil.rmtree(extraction_folder)
            print("🧹 File temporanei rimossi.")

def main():
    onceEach24H()
    print("Bon, finì")

if __name__ == "__main__":
    main()