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
        raise RuntimeError("⚠️ Attenzione: La variabile d'ambiente ORS_API_KEY non è settata! Imposta ORS_API_KEY nel container/ambiente.")
        
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
        # Logga dettagli utili per il debug: metodo, url, headers e body della richiesta, e risposta completa da ORS
        try:
            req = call.request
            print("--- ORS request debug ---")
            print(f"Request method: {req.method}")
            print(f"Request url: {req.url}")
            try:
                # headers può contenere byte/None, stampiamo in modo sicuro
                print(f"Request headers: {dict(req.headers)}")
            except Exception:
                print(f"Request headers (raw): {req.headers}")
            try:
                print(f"Request body: {req.body}")
            except Exception:
                print("Request body: <could not decode>")
            print("--- ORS response ---")
            print(f"Status code: {call.status_code}")
            try:
                print(f"Response text: {call.text}")
            except Exception:
                print("Response text: <could not decode>")
            print("--- end debug ---")
        except Exception as _:
            print("Impossibile loggare i dettagli della request/response ORS.")
        if call.status_code == 401:
            raise RuntimeError("Chiave API ORS non valida o mancante. Controlla la variabile ORS_API_KEY.")
        elif call.status_code == 403:
            raise RuntimeError("Accesso negato da ORS. Verifica i permessi della chiave API.")
        elif call.status_code == 413:
            raise RuntimeError("La richiesta a ORS è troppo grande: troppe barriere da evitare o percorso troppo lungo.")
        elif call.status_code == 400:
            raise RuntimeError(f"Richiesta non valida inviata a ORS (400). Controlla i parametri del percorso: {e}")
        elif call.status_code == 404:
            print("Nessun percorso trovato da ORS (Errore 404: percorso impossibile con le restrizioni date).")
            return None
        else:
            raise RuntimeError(f"Errore HTTP da ORS ({call.status_code}): {e}")
    except RuntimeError:
        raise  # rilancia le RuntimeError tale e quale
    except Exception as e:
        raise RuntimeError(f"Errore imprevisto durante la comunicazione con ORS: {e}")








def calculateWalkingLegAndAddResultToMap(coordinateInizio, coordinateFine, percorsoPolyline, mappaSuCuiAggiungereLaWalkLegDaCalcolare, wheelchair=False):
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
        routes = callToORS(inizio=coordinateInizio, fine=coordinateFine)
        if not routes:
            raise RuntimeError("ORS non ha trovato nessun percorso pedonale tra i due punti indicati.")
        percorso = Percorso(routes[0])

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
    barriere, facilitatori, infrastrutture = percorso.trovaElementiSulPercorso(
        elementi_osm_personalizzati_caricati_dal_db, 
        wheelchair=wheelchair
    )

    # se la mappa non ha alcuna barriera allora ho finito
    if len(barriere) == 0:
        # aggiungo barriere facilitatori e infrastrutture alla mappa
        mappaSuCuiAggiungereLaWalkLegDaCalcolare.aggiungiBarriereFacilitatoriInfrastrutture(
            barriere,
            facilitatori,
            infrastrutture
        )
        # aggiungo il percorso stesso alla mappa
        mappaSuCuiAggiungereLaWalkLegDaCalcolare.aggiungiPercorso(percorso)
        # e infine ritorno l'oggetto mappa aggiornato
        return mappaSuCuiAggiungereLaWalkLegDaCalcolare
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

        # innanzitutto salvo il vecchio percorso:
        vecchioPercorso = percorso
        vecchieBarriere = barriere
        vecchiFacilitatori = facilitatori
        vecchieInfrastrutture = infrastrutture
        # così se quello nuovo dovesse avere ancora più barriere so che è meglio ritornare quello vecchio
        # dato che avrebbe meno barriere e sarebbe sicuramente più corto

        # calcolo il nuovo percorso evitando le barriere trovate
        routes = callToORS(inizio=coordinateInizio, fine=coordinateFine, elementi_da_evitare=tutte_barriere_da_evitare)
        if not routes:
            # Nessun percorso alternativo trovato, ritorno quello precedente
            print("ORS non ha trovato un percorso alternativo per evitare le barriere. Utilizzo il percorso precedente.")
            mappaSuCuiAggiungereLaWalkLegDaCalcolare.aggiungiBarriereFacilitatoriInfrastrutture(
                vecchieBarriere,
                vecchiFacilitatori,
                vecchieInfrastrutture
            )
            mappaSuCuiAggiungereLaWalkLegDaCalcolare.aggiungiPercorso(vecchioPercorso)
            return mappaSuCuiAggiungereLaWalkLegDaCalcolare
            
        percorso = Percorso(routes[0])
        # ricarico gli elementi dato che sarà cambiata la bbox
        elementi_osm_personalizzati_caricati_dal_db = caricaElementiDaJSON(
            directoryDatiORS=base_directory / "data" / "ORS_data", 
            bbox=percorso.bbox, 
            wheelchair=wheelchair
        )
        # dal percorso calcolato trovo tutte le barriere
        barriere, facilitatori, infrastrutture = percorso.trovaElementiSulPercorso(elementi_osm_personalizzati_caricati_dal_db, wheelchair=wheelchair)
        # le nuove barriere trovate le aggiungo per evitarle alla prossima iterazione
        
        # se ci sono state barriere in più nel nuovo percorso allora prendo quello vecchio
        if len(barriere) > len(vecchieBarriere):
            mappaSuCuiAggiungereLaWalkLegDaCalcolare.aggiungiBarriereFacilitatoriInfrastrutture(
                vecchieBarriere,
                vecchiFacilitatori,
                vecchieInfrastrutture
            )
            # aggiungo il percorso stesso alla mappa
            mappaSuCuiAggiungereLaWalkLegDaCalcolare.aggiungiPercorso(vecchioPercorso)
            # e infine ritorno l'oggetto mappa aggiornato
            return mappaSuCuiAggiungereLaWalkLegDaCalcolare


        # se non ci sono più barriere o se sta finendo il for e non ho ancora trovato un percorso senza barriere
        # mi arrendo e aggiungo tutti i tracciati ottenuti fino ad ora
        if len(barriere) == 0 or i == NUMERO_DI_ITERAZIONI - 1:
            # aggiungo barriere facilitatori e infrastrutture alla mappa
            mappaSuCuiAggiungereLaWalkLegDaCalcolare.aggiungiBarriereFacilitatoriInfrastrutture(
                barriere,
                facilitatori,
                infrastrutture
            )
            # aggiungo il percorso stesso alla mappa
            mappaSuCuiAggiungereLaWalkLegDaCalcolare.aggiungiPercorso(percorso)
            # e infine ritorno l'oggetto mappa aggiornato
            return mappaSuCuiAggiungereLaWalkLegDaCalcolare

        # aggiungo le nuove barriere trovate per la prossima iterazione
        for barriera in barriere:
            if barriera not in tutte_barriere_da_evitare:
                tutte_barriere_da_evitare.append(barriera)

    # aggiungo barriere facilitatori e infrastrutture alla mappa
    mappaSuCuiAggiungereLaWalkLegDaCalcolare.aggiungiBarriereFacilitatoriInfrastrutture(
        barriere,
        facilitatori,
        infrastrutture
    )

    return mappaSuCuiAggiungereLaWalkLegDaCalcolare


def computeBbox(pol):
    """data una polyline ritorna la bbox che la contiene"""
    p = polyline.decode(pol)
    lats = [coord[0] for coord in p]
    lons = [coord[1] for coord in p]
    return [min(lons), min(lats), max(lons), max(lats)]
