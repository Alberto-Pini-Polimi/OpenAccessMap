from ORS_utility import Percorso
import json
import requests
import os
from shapely import geometry
from shapely.geometry import Point, Polygon, MultiPolygon
from pathlib import Path
from maps import Map # classe contenente tutte le funzioni necessarie per renderizzare la mappa finale
from ORS_utility import *
import polyline

# base directory per sapere dove andare a pescare i dati ORS
base_directory = Path(__file__).resolve().parent.parent # this corresponds to the base directory of the repo


# chiamata all'API di OpenRouteService per calcolare i percorsi
def callToORS(inizio, fine, elementi_da_evitare=None, waypoints=None, preferenza="fastest"):
    """
        Calcola uno o più percorsi pedonali usando OpenRouteService
    """

    # recupero la chiave di ORS
    ORS_API_KEY = os.getenv("ORS_API_KEY")
    if not ORS_API_KEY:
        print("⚠️ Attenzione: La variabile d'ambiente ORS_API_KEY non è settata!")
        
    # Costruisco il body & headers
    coordinates = [[inizio[1], inizio[0]]]
    # Aggiungi waypoints se presenti
    if waypoints and len(waypoints) > 0:
        for wp in waypoints:
            # waypoints sono [lat, lon], converto in [lon, lat] per ORS
            coordinates.append([wp[1], wp[0]])
    # Aggiungi la destinazione
    coordinates.append([fine[1], fine[0]])

    headers = {
        "Authorization": ORS_API_KEY,
        "Content-Type": "application/json; charset=utf-8",
        "Accept": "application/json, application/geo+json, application/gpx+xml, img/png; charset=utf-8"
    }

    body = {
        "coordinates": coordinates,
        "instructions": False,
        "preference": preferenza
    }
    
    # converto ogni elemento da evitare in un array di poligoni da evitare
    if elementi_da_evitare:
        poligoni_da_evitare = []
        for elemento_da_evitare in elementi_da_evitare:
            # Ottieni il centroide dell'elemento
            lon = elemento_da_evitare.coordinate_centroide["longitudine"]
            lat = elemento_da_evitare.coordinate_centroide["latitudine"]
            # Proietta il punto in UTM
            punto_utm = project_to_utm(lon, lat)
            # Crea un buffer in metri attorno al punto (ad esempio 10m)
            buffer_utm = Point(punto_utm).buffer(BUFFER_ATTORNO_AL_QUALE_SI_CREA_UNA_ZONA_PROIBITA_IN_METRI)
            # Riproietta il buffer in WGS84
            buffer_wgs84_coords = [project_to_wgs(x, y) for x, y in buffer_utm.exterior.coords]
            poligono = Polygon(buffer_wgs84_coords)
            poligoni_da_evitare.append(poligono)

        # se ho trovato almeno un poligono allora aggiungo alla richiesta ....
        if len(poligoni_da_evitare) > 0:
            # ... di evitare i poligoni contenenti le barriere
            body["options"] = {
                "avoid_polygons": geometry.mapping(MultiPolygon(poligoni_da_evitare))
            }
    
    # Faccio la call a ORS
    try:
        # faccio la chiamata
        call = requests.post('https://api.openrouteservice.org/v2/directions/foot-walking/json', json=body, headers=headers)
        call.raise_for_status()
        route_data = json.loads(call.text) # e parso la risposta JSON
        
        if "routes" in route_data and len(route_data["routes"]) > 0:
            return route_data["routes"] # ritorno quindi le routes trovate
        else:
            print("Nessun percorso trovato")
            return None
        
    except requests.exceptions.HTTPError as e:
        print(f"Errore HTTP nel calcolo del percorso: {e}")
        if call.status_code == 401:
            print("Chiave API non valida o mancante")
        elif call.status_code == 403:
            print("Accesso negato")
        elif call.status_code == 413:
            print("Richiesta troppo grande!") #TODO ho messo return al posto di exit. DA TESTARE
            return None
        elif call.status_code == 400:
            print("Richiesta malformata, controlla i parametri inviati")
        exit(-1)
    except Exception as e:
        print(f"Altro errore nel calcolo del percorso: {e}")
        exit(-1)








def calculateWalkingLegAndAddResultToMap(coordinateInizio, coordinateFine, percorsoPolyline, mappaACuiAggiungereLaLegCalcolata, wheelchair=False):
    """ritorna l'oggetto mappa aggiornato con percorso, barriere, infrastrutture e facilitatori a seconda che l'utente ha richiesto wheelchair"""

    # se il percorso è già stato calcolato da OTP allora skippo la call a ORS:
    percorso = None
    if percorsoPolyline is not None:
        percorso = Percorso({
            "summary": {
                "distance": 0,
                "duration": 0
            },
            "bbox": computeBbox(percorsoPolyline),
            "geometry": percorsoPolyline # to be decoded
        })
        #print("calcolato percorso con OTP")
    else: 
        # ------------ CALCOLO PERCORSO STANDARD ------------

        #print(f"Walk leg: {coordinateInizio} a {coordinateFine}...")
        # quello calcolato è il percorso di default ed anche il più veloce
        percorso = Percorso(callToORS(inizio=coordinateInizio, fine=coordinateFine)[0])

    # ------------ CARICAMENTO DATI DAL DB ------------

    # il percorso STANDARD mi è utile per caricare gli elementi dal DB in modo efficiente
    # non avrebbe senso caricare elementi in memoria che sono da tutt'altra parte del percorso calcolato
    elementi_osm_personalizzati_caricati_dal_db = caricaElementiDaJSON(
        directoryDatiORS=base_directory / "data" / "ORS_data", 
        bbox=percorso.bbox, 
        wheelchair=wheelchair
    )

    # ------------ TROVO GLI ELEMENTI VICINI AL PERCORSO ------------

    # dagli elementi estratti trovo quelli rientranti nei buffer del percorso separandoli fra barriere, facilitatori ed infrastrutture
    barriere, facilitatori, infrastrutture = percorso.trovaElementiSulPercorso(elementi_osm_personalizzati_caricati_dal_db, wheelchair=wheelchair)

    # se la mappa non ha alcuna barriera allora ho finito
    if len(barriere) == 0:
        # aggiungo barriere facilitatori e infrastrutture alla mappa
        mappaACuiAggiungereLaLegCalcolata.aggiungiBarriereFacilitatoriInfrastrutture(
            barriere,
            facilitatori,
            infrastrutture
        )
        # aggiungo il percorso stesso alla mappa
        mappaACuiAggiungereLaLegCalcolata.aggiungiPercorso(percorso)
        # e infine ritorno l'oggetto mappa aggiornato
        return mappaACuiAggiungereLaLegCalcolata
    # altrimenti itero cercando di migliorare il percorso evitando le barriere trovate finché ne trovo
    # o finché non arrivo ad un numero di iterazioni massimo (per evitare loop infiniti)

    # ------------ ITERAZIONI ------------

    # tendenzialmente rimuove tutte le barriere, ma non è mai detto con certezza
    # inoltre si fanno 3 chiamate all'api una dopo l'altra
    NUMERO_DI_ITERAZIONI = 3

    # parto dal percorso standard e scelgo di evitare tutte le barriere
    # faccio la stessa cosa per il percorso calcolato precedentemente
    tutte_barriere_da_evitare = barriere
    for i in range(NUMERO_DI_ITERAZIONI):
        # calcolo il nuovo percorso mettendo 
        percorso = Percorso(callToORS(inizio=coordinateInizio, fine=coordinateFine, avoid_polygons=tutte_barriere_da_evitare)[0])
        # dal percorso calcolato trovo tutte le barriere
        barriere, facilitatori, infrastrutture = percorso.trovaElementiSulPercorso(elementi_osm_personalizzati_caricati_dal_db, wheelchair=wheelchair)
        # le nuove barriere trovate le aggiungo per evitarle alla prossima iterazione
        # se non ci sono più barriere → fermati
        if len(barriere) == 0:
            # aggiungo barriere facilitatori e infrastrutture alla mappa
            mappaACuiAggiungereLaLegCalcolata.aggiungiBarriereFacilitatoriInfrastrutture(
                barriere,
                facilitatori,
                infrastrutture
            )
            # aggiungo il percorso stesso alla mappa
            mappaACuiAggiungereLaLegCalcolata.aggiungiPercorso(percorso)
            # e infine ritorno l'oggetto mappa aggiornato
            return mappaACuiAggiungereLaLegCalcolata

        # se sta finendo il for e non ho ancora trovato un percorso senza barriere
        # mi arrendo e stampo tutti i tracciati ottenuti fino ad ora
        if i == NUMERO_DI_ITERAZIONI - 1:
            # aggiungo barriere facilitatori e infrastrutture alla mappa
            mappaACuiAggiungereLaLegCalcolata.aggiungiBarriereFacilitatoriInfrastrutture(
                barriere,
                facilitatori,
                infrastrutture
            )
            # aggiungo il percorso stesso alla mappa
            mappaACuiAggiungereLaLegCalcolata.aggiungiPercorso(percorso)
            # e infine ritorno l'oggetto mappa aggiornato
            return mappaACuiAggiungereLaLegCalcolata

        # aggiungo le nuove barriere trovate per la prossima iterazione
        for barriera in barriere:
            if barriera not in tutte_barriere_da_evitare:
                tutte_barriere_da_evitare.append(barriera)

    return mappaACuiAggiungereLaLegCalcolata


def computeBbox(pol):
    """data una polyline ritorna la bbox che la contiene"""
    p = polyline.decode(pol)
    lats = [coord[0] for coord in p]
    lons = [coord[1] for coord in p]
    return [min(lats), min(lons), max(lats), max(lons)]
