from lib2to3.fixes import fix_itertools_imports
from typing import Dict
import OTP_routing
import ORS_routing
import maps


# Main Function that main.py (server) calls
# then this calls route_OTP() and route_ORS()
def route(variables):

    # creating empty folium map to return with the result
    map = maps.Map()

    # ===============
    # |  OTP part   |
    # ===============

    # first I call OTP with all the variables
    otp_patterns = OTP_routing.route_OTP(variables, numberOfPatterns=1)
    # check if no error occured
    if otp_patterns is None:
        # throw an error
        raise RuntimeError("Impossibile calcolare questo percorso con OTP!")
    # deduplicate patterns that are equal
    if len(otp_patterns) > 1:
        otp_patterns = deduplicatePatterns(otp_patterns)

    # variabile locale per capire se l'utente è in sedia a rotelle
    wheelchair = variables["wheelchair"]

    # logs calculated patterns:
    outputData = log(otp_patterns, wheelchair)

    # =================================
    # |  Working on OTP output part   |
    # =================================

    # work only on the best itinerary (pattern)
    best_pattern = otp_patterns[0]

    # extract legs from the best pattern
    legs = best_pattern.get("legs") or []

    # create a list of legs with mode=WALK and mode=TRANSIT
    walk_legs = []
    transit_legs = []
    for leg in legs:
        if leg.get("mode").upper() == "FOOT":
            # extract walk leg data and add it to the list
            walk_legs.append(extractWalkLegData(leg))
        else:
            # extract transit leg data and add it to the list
            transit_legs.append(extractTransitLegData(leg))

    # ======================
    # |  Constructing Map  |
    # ======================

    # add transit legs to the map
    for leg in transit_legs:
        map = map.aggiungiMezzoPubblico(
            inizio=leg.get("start_coordinates"),
            fine=leg.get("end_coordinates"),
            nome_inizio=leg.get("start_name"),
            nome_fine=leg.get("end_name"),
            tipologia_mezzo=leg.get("type"),
            nome_linea=leg.get("line_name"),
            traccia=leg.get("track")
        )
    
    # add foot legs to the map
    for leg in walk_legs:
        map = ORS_routing.calculateWalkingLegAndAddResultToMap(
            coordinateInizio=leg.get("start_coordinates"),  # Coordinate di inizio del segmento pedonale
            coordinateFine=leg.get("end_coordinates"),  # Coordinate di fine del segmento pedonale
            percorsoPolyline=leg.get("track"),
            mappaACuiAggiungereLaLegCalcolata=map,  # Oggetto mappa da aggiornare
            wheelchair=wheelchair
        )
    
    return map, outputData



# ==== LEG DATA EXTRACTORS ====

def extractWalkLegData(leg) -> Dict:
    start = leg.get('fromPlace') or {}
    end   = leg.get('toPlace') or {}
    start_coord = (start.get("latitude"), start.get("longitude"))
    end_coord   = (end.get("latitude")  , end.get("longitude")  )
    start_name  = start.get("name") or "?"
    end_name    = end.get("name") or "?"
    foot_polyline = leg.get("pointsOnLink").get("points")

    return {
        "start_coordinates": start_coord,
        "end_coordinates": end_coord,
        "start_name": start_name,
        "end_name": end_name,
        "track": foot_polyline
    }

def extractTransitLegData(leg) -> Dict:

    # get transport mode (FOOT, BUS, ecc.)
    modeOfTransit = (leg.get('mode') or "").upper()
    
    # start and end
    start = leg.get('fromPlace') or {}
    end   = leg.get('toPlace') or {}
    start_coord = (start.get("latitude"), start.get("longitude"))
    end_coord   = (end.get("latitude")  , end.get("longitude")  )
    start_name  = start.get("name") or "?"
    end_name    = end.get("name") or "?"

    # line characteristics
    line = leg.get("line") or {}
    line_code = line.get("publicCode") or "?"
    line_name = line.get("name") or "?"
    line_extended_name = (f"{line_code} {line_name}").strip() or "Linea sconosciuta"
    line_polyline = leg.get("pointsOnLink").get("points")

    return {
        "start_coordinates": start_coord,
        "end_coordinates": end_coord,
        "start_name": start_name,
        "end_name": end_name,
        "type": modeOfTransit,
        "line_name": line_extended_name,
        "track": line_polyline
    }












# WIP
def deduplicatePatterns(patterns):
    return patterns

def log(patterns, wheelchair):

    outputData = []

    # SVARIATE RIGHE SOLTANTO PER STAMPARE!!
    stringaOutput = ""
    print(f"Top {len(patterns)} itinerari (wheelchair={wheelchair}):")
    for idx, p in enumerate(patterns, 1):
        # cose per il print
        costo_secondi = p.get("generalizedCost")
        durata_secondi = p.get("duration")

        costo_minuti = (costo_secondi / 60.0) if isinstance(costo_secondi, (int, float)) else None
        durata_minuti = int(durata_secondi / 60) if isinstance(durata_secondi, (int, float)) else None

        costo_str = f"{costo_minuti:.1f} min" if costo_minuti is not None else "n/d"
        durata_str = f"{durata_minuti} min" if durata_minuti is not None else "n/d"

        stringaOutput += f"\n--- Itinerario #{idx} ---\n"
        stringaOutput += f"Generalized cost: {costo_str} | Durata prevista: {durata_str}\n"

        # STAMPO LE INFO SULLE SINGOLE LEGS
        legs = p.get("legs") or []
        for j, leg in enumerate(legs, 1):
            mode = (leg.get("mode") or "?").upper()
            fp = leg.get("fromPlace") or {}
            tp = leg.get("toPlace") or {}
            nome_partenza = fp.get("name") or "?"
            nome_arrivo = tp.get("name") or "?"
            distance = leg.get("pointsOnLink").get("distance")
            #length = leg.get("pointsOnLink").get("length")

            if mode == "FOOT":
                stringaOutput += (
                    f"{j:>2}. "
                    f"{'🚶':<5}"
                    f"{distance:>6} m   "
                    f"{nome_partenza:<25} -> "
                    f"{nome_arrivo:<25}\n"
                )

                outputData.append({
                    "mode": mode,
                    "distance": distance,
                    "start_name": nome_partenza,
                    "end_name": nome_arrivo
                })

            else:
                line = leg.get("line") or {}

                codice_linea = line.get("publicCode") or ""
                nome_linea = line.get("name") or ""

                linea_completa = (
                    f"{codice_linea} {nome_linea}"
                ).strip() or "Linea sconosciuta"

                stringaOutput += (
                    f"{j:>2}. "
                    f"{mode:<5}"
                    f"{distance:>6} m   "
                    f"{nome_partenza:<25} -> "
                    f"{nome_arrivo:<25} "
                    f"{linea_completa:<30}\n"
                )

                outputData.append({
                    "mode": mode,
                    "distance": distance,
                    "start_name": nome_partenza,
                    "end_name": nome_arrivo,
                    "line_name": linea_completa
                })
    
    # print output string
    print(stringaOutput)

    # return output data (to be rendered on the results.html page)
    return outputData

# HELPER FUNCTIONS PER route()

def format_coordinates(place: dict) -> str: #formatta coordinate
    lat = place.get("latitude")
    lon = place.get("longitude")
    if lat is None or lon is None:
        return "(?,?)"
    return f"({lat:.6f},{lon:.6f})"