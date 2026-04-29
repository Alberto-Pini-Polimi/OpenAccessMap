import os
import glob
import requests
import json
from enum import Enum
import uuid


'''

Trova tutti i file .txt nella cartella "queries"
esegue questi file come se fossero query-QL con l'API di Overpass-Turbo
Raccoglie tutti i risultati in un unico grande array JSON nel file "fromOSM.json"
Il file .json generato avrà il formato e la classificazione giusta (rispetto alla tipologia e alla disabilità)

'''

def carica_query_da_file(nome_file):
    with open(nome_file, 'r', encoding='utf-8') as file:
        return file.read()

def esegui_query_overpass(query):
    url = "https://overpass-api.de/api/interpreter"
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'User-Agent': 'AccessibilityProject/1.0 (student project)'
    }
    response = requests.post(url, data={'data': query}, headers=headers)
    
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Errore {response.status_code}: {response.text}")

def salva_json(nome_file, dati):
    with open(nome_file, 'w', encoding='utf-8') as f:  # Sovrascrive il file invece di appendere
        json.dump(dati, f, default=convert_to_json, ensure_ascii=False, indent=4)


class ProblemiMobilita(Enum):

    # Disabilità Fisica
    MOTORIA = "Motoria"

    # Disabilità Sensoriali
    VISIVA = "Visiva"
    UDITIVA = "Uditiva"

    # Altre disabilità
    MULTIPLE = "Multiple"
    ALTRE = "Altre"

    def __str__(self):
        return self.value
    
    def to_json(self):
        """Metodo per serializzare l'Enum in JSON."""
        return self.value

class TipoElemento(Enum):
    # Barriera
    BARRIERA = "Barriera"

    # Facilitatore
    FACILITATORE = "Facilitatore"

    # Infrastruttura
    INFRASTRUTTURA = "Infrastruttura"

    def __str__(self):
        return self.value
    
    def to_json(self):
        """Metodo per serializzare l'Enum in JSON."""
        return self.value

def convert_to_json(obj):
    """Funzione di supporto per la serializzazione di oggetti complessi."""
    if isinstance(obj, Enum):
        return obj.to_json()
    elif isinstance(obj, uuid.UUID):
        return str(obj)  # Converti l'UUID in stringa
    raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")


def classifica_dati(elementoOSM):
    """
    Funzione per classificare i dati in base alla tipologia e alla disabilità,
    includendo nome e descrizione dell'elemento.

    Args:
        elementoOSM: Un oggetto che rappresenta un elemento di OpenStreetMap
                     e ha un attributo 'tags' (un dizionario).

    Returns:
        Una tupla contenente:
        - comeBarrieraPer: Lista di tuple (TipoElemento, ProblemiMobilita)
        - comeFacilitatorePer: Lista di tuple (TipoElemento, ProblemiMobilita)
        - comeInfrastrutturaPer: Lista di tuple (TipoElemento, ProblemiMobilita)
        - nome: Il nome dell'elemento (stringa)
        - descrizione: Una descrizione dell'elemento (stringa)
    """

    comeBarrieraPer = []
    comeFacilitatorePer = []
    comeInfrastrutturaPer = []
    nome = "Elemento Sconosciuto" #Valore di default
    descrizione = ""

    # ascensore
    if elementoOSM["tags"].get("highway") in ["elevator", "lift"]:
        nome = "Ascensore"
        comeFacilitatorePer.append(ProblemiMobilita.MOTORIA)
        descrizione = "Ascensore per superare dislivelli."

    # attraversamento pedonale
    elif elementoOSM["tags"].get("highway") == "crossing" or elementoOSM["tags"].get("footway") == "crossing":
        nome = "Attraversamento Pedonale"
        if elementoOSM["tags"].get("traffic_signals:sound") == "yes" or elementoOSM["tags"].get("tactile_paving") == "yes" or elementoOSM["tags"].get("traffic_signals:vibration") == "yes":
            comeFacilitatorePer.append(ProblemiMobilita.VISIVA)
            descrizione = "Attraversamento pedonale con ausili per non vedenti."
        else:
            comeBarrieraPer.append(ProblemiMobilita.VISIVA)
            descrizione = "Attraversamento pedonale senza ausili per non vedenti."

    # kerb (marciapiede/bordo strada)
    elif elementoOSM["tags"].get("barrier") == "kerb":
        nome = "Bordo Marciapiede"
        if elementoOSM["tags"].get("kerb") == "raised":
            comeBarrieraPer.append(ProblemiMobilita.MOTORIA)
            descrizione = "Marciapiede con bordo alto, difficile da superare."
        else:
            comeFacilitatorePer.append(ProblemiMobilita.MOTORIA)
            descrizione = "Marciapiede con bordo basso/smussato, facile da superare."
        if elementoOSM["tags"].get("tactile_paving") == "yes":
            comeFacilitatorePer.append(ProblemiMobilita.VISIVA)
            descrizione += "  Presenza di pavimentazione tattile per non vedenti."

    # panchina
    elif elementoOSM["tags"].get("amenity") == "bench":
        nome = "Panchina"
        comeInfrastrutturaPer.append(ProblemiMobilita.MOTORIA)
        comeInfrastrutturaPer.append(ProblemiMobilita.VISIVA)
        comeInfrastrutturaPer.append(ProblemiMobilita.UDITIVA)
        descrizione = "Panchina per sedersi e riposare."

    # fontana
    elif elementoOSM["tags"].get("amenity") == "drinking_water":
        nome = "Fontana"
        comeInfrastrutturaPer.append(ProblemiMobilita.MOTORIA)
        comeInfrastrutturaPer.append(ProblemiMobilita.VISIVA)
        comeInfrastrutturaPer.append(ProblemiMobilita.UDITIVA)
        descrizione = "Fontana per bere o riempire la borraccia."

    # bar
    elif elementoOSM["tags"].get("amenity") == "cafe" or elementoOSM["tags"].get("amenity") == "bar":
        nome = "Bar"
        comeInfrastrutturaPer.append(ProblemiMobilita.VISIVA)
        comeInfrastrutturaPer.append(ProblemiMobilita.UDITIVA)
        if elementoOSM["tags"].get("wheelchair") == "yes":
            comeInfrastrutturaPer.append(ProblemiMobilita.MOTORIA)
            descrizione = "Bar accessibile in sedia a rotelle"

    # bagno
    elif elementoOSM["tags"].get("amenity") == "toilets":
        nome = "Bagno"
        if elementoOSM["tags"].get("wheelchair") == "yes":
            comeInfrastrutturaPer.append(ProblemiMobilita.MOTORIA)
            descrizione = "Bagno accessibile per persone con disabilità motorie."
        else:
            comeInfrastrutturaPer.append(ProblemiMobilita.VISIVA)
            comeInfrastrutturaPer.append(ProblemiMobilita.UDITIVA)
            descrizione = "Bagno pubblico."

    # rampa
    elif elementoOSM["tags"].get("highway") == "ramp" or elementoOSM["tags"].get("access") == "ramp": #gestione di entrambi i tag
        nome = "Rampa"
        comeFacilitatorePer.append(ProblemiMobilita.MOTORIA)
        descrizione = "Rampa per superare dislivelli."
    elif elementoOSM["tags"].get("incline"):  # Gestione del tag incline
        nome = "Rampa" #Nome di default
        incline_value = elementoOSM["tags"].get("incline")
        if incline_value in ["up", "steep"]:
            comeBarrieraPer.append(ProblemiMobilita.MOTORIA)
            descrizione = f"Rampa ripida (inclinazione: {incline_value}), difficile da percorrere."
        elif incline_value in ["down", "gentle"]:
            comeFacilitatorePer.append(ProblemiMobilita.MOTORIA)
            descrizione = f"Rampa dolce (inclinazione: {incline_value}), facile da percorrere."
        else:
            comeFacilitatorePer.append(ProblemiMobilita.MOTORIA)
            descrizione = f"Rampa (inclinazione: {incline_value})." #inclinazione non specificata

    else:
        descrizione = "Elemento non classificato ai fini dell'accessibilità." #descrizione di default

    return comeBarrieraPer, comeFacilitatorePer, comeInfrastrutturaPer, nome, descrizione

def estrai_coordinate(elementoOSM):

    # se è un nodo allora semplicemente:
    latitudine = elementoOSM.get("lat")
    longitudine = elementoOSM.get("lon")

    # altrimenti è una way o una relation e quindi:
    if latitudine is None or longitudine is None:
        if elementoOSM.get("center") is not None:
            latitudine = elementoOSM["center"].get("lat")
            longitudine = elementoOSM["center"].get("lon")
        else:
            print("non si riescono a trovare le coordinate per:")
            print(elementoOSM)
            exit(-1)

    return {
        "longitudine": longitudine,
        "latitudine": latitudine
    }


def parsa_dati(risultatoQueryOSM):
    """
    Funzione per parsare l'elemento in base alla tipologia e alla disabilità
    """

    dati_parsati = []

    for elementoOSM in risultatoQueryOSM["elements"]:
        
        disabilitàPerCuiFungeDaBarriera, disabilitàPerCuiFungeDaFacilitatore, disabilitàPerCuiFungeDaInfrastruttura, nome, descrizione = classifica_dati(elementoOSM)
        coordinate_centroide = estrai_coordinate(elementoOSM)

        dati_parsati.append(
            {
                "id": str(uuid.uuid4()),  # Converto direttamente UUID in stringa
                "barrieraPer": disabilitàPerCuiFungeDaBarriera,
                "facilitatorePer": disabilitàPerCuiFungeDaFacilitatore,
                "infrastrutturaPer": disabilitàPerCuiFungeDaInfrastruttura,
                "autore": "OSM",
                "ranking": 100,
                "nome": nome,
                "descrizione": descrizione,
                "immagine": None, # in futuro conterrà il link all'immagine (o il path)
                "elementoOSM": elementoOSM,
                "coordinateCentroide": coordinate_centroide
            }
        )

    return dati_parsati


# === Main ===
def main():
    # Trovo le varie cartelle calcolandole dinamicamente a prescindere da dove avvio lo script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    cartella_queries = os.path.join(script_dir, "queries")
    
    # La cartella dei risultati sarà la cartella superiore (ORS_data)
    cartella_risultati = os.path.abspath(os.path.join(script_dir, ".."))

    # trova tutti i file .txt nella cartella "queries"
    file_txt = glob.glob(os.path.join(cartella_queries, "*.txt"))
    print(f"Trovati {len(file_txt)} file .txt nella cartella 'queries'")

    # Crea una lista vuota per raccogliere tutti i risultati
    tutti_risultati = []

    # per ogni file trovato...
    for path_file in file_txt:
        nome_file = os.path.basename(path_file)
        
        try:
            print(f"\nEseguo query da: {nome_file}")
            query = carica_query_da_file(path_file)  # carico query dai file
            risultato_query_in_json = esegui_query_overpass(query) # eseguo la query
            risultati_parziali = parsa_dati(risultato_query_in_json) # parso i dati
            
            # Aggiungo i risultati parziali all'array principale
            tutti_risultati.extend(risultati_parziali)
            
            print(f"✅ Elaborato: {nome_file} - Aggiunti {len(risultati_parziali)} elementi")
        except Exception as e:
            print(f"❌ Errore con {nome_file}: {e}")
            exit(-1)
    
    # Alla fine, salvo un unico file JSON con tutti i risultati
    output_path = os.path.join(cartella_risultati, "fromOSM.json")
    salva_json(output_path, tutti_risultati)
    print(f"\n\n✅ Salvato file unico: {output_path} con {len(tutti_risultati)} elementi totali")

if __name__ == "__main__":
    main()