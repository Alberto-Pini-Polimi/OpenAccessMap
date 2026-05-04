import json
import os
import requests
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

URL = os.getenv("OTP_URL", "http://localhost:8080/otp/transmodel/v3")
HEADERS = {"Content-Type": "application/json"}

QUERY = """
query trip(
  $dateTime: DateTime,
  $from: Location!,
  $to: Location!,
  $modes: Modes,
  $wheelchair: Boolean,
  $searchWindow: Int,
  $arriveBy: Boolean,
  $walkSpeed: Float,
  $timetableView: Boolean
) {
  trip(
    dateTime: $dateTime,
    from: $from,
    to: $to,
    modes: $modes,
    wheelchairAccessible: $wheelchair,
    searchWindow: $searchWindow,
    arriveBy: $arriveBy,
    walkSpeed: $walkSpeed,
    timetableView: $timetableView
  ) {
    tripPatterns {
      duration
      distance
      generalizedCost
      systemNotices { tag text }
      legs {
        mode
        expectedStartTime
        expectedEndTime
        duration
        fromPlace {
            name
            latitude
            longitude
            quay { id name latitude longitude }
        }
        toPlace {
            name
            latitude
            longitude
            quay { id name latitude longitude }
        }
        line { 
          publicCode 
          name 
          id 
          presentation { 
            colour 
          } 
        }
        pointsOnLink {
          points
          length
          distance
        }
      }
    }
  }
}
"""


def get_now_local_iso():
    milan_tz = ZoneInfo("Europe/Rome")
    now = datetime.now(milan_tz)

    # Formatta in ISO 8601 UTC (OTP richiede UTC)
    # Converti a UTC per evitare problemi di interpretazione del timezone
    # Risultato es: '2026-05-03T13:50:00Z' (UTC, 2 ore prima di Milano)
    now_utc = now.astimezone(timezone.utc)
    return now_utc.replace(microsecond=0, tzinfo=timezone.utc).isoformat()

# used by main.py to build the payload for OTP
def get_default_variables():
    """
    Payload base per OTP da sovrascrivere.
    """
    return {
        "from": {"coordinates": {"latitude": 45.47437, "longitude": 9.183323}}, # queste sono solo coordinate di default, verranno sovrascritte da main.py
        "to": {"coordinates": {"latitude": 45.48535, "longitude": 9.20944}},
        "dateTime": get_now_local_iso(), # ora di partenza (in formato ISO locale) viene presa al momento della richiesta
        "timetableView": False,
        "arriveBy": False, # alla destinazione ci arrivo quando voglio ma il trip parte da "dateTime"
        "searchWindow": 40,
        "modes": {
            "transportModes": [
                {"transportMode": "bus"},
                {"transportMode": "metro"},
                {"transportMode": "tram"},
                {"transportMode": "rail"},
            ],
            "accessMode": "foot",
            "egressMode": "foot",
            "directMode": "foot",
        },
        "wheelchair": False,
        "walkSpeed": 1.3 # m/s, velocità di camminata impostata a 1.3 m/s (4.68 km/h), equivalente al passo medio di un essere umano adulto in piano.  
    }

def extractLegs(patterns):
    """
    Estrae la lista delle legs dal primo tripPattern.
    Ritorna una lista di dict, ciascuna rappresentante una leg.
    """
    if not patterns:
        return []
    p = patterns[0]
    legs = p.get("legs") or []
    return legs 

def route_OTP(variables, numberOfPatterns=2):

    # request to OTP
    otp_request = requests.post(
        url=URL,  # URL del server OTP
        json={"query": QUERY, "variables": variables},  # Payload GraphQL con query e variabili
        headers=HEADERS,  # Headers con Content-Type application/json
        timeout=60  # Timeout di 60 secondi per la richiesta
    )
    otp_request.raise_for_status()  # Solleva eccezione se la risposta ha status code di errore
    responce_data = otp_request.json()  # Parso la risposta JSON

    # handling Graph.obj errors
    if responce_data.get("errors"):
        print("GraphQL errors:")
        for errore in responce_data["errors"]:
            print(" -", errore.get("message"))
        return None  # Ritorna None in caso di errori

    # Estrai i tripPatterns dalla risposta
    patterns = (
        (responce_data.get("data") or {}).get("trip") or {}
    ).get("tripPatterns") or []
    if not patterns:
        print("Nessun tripPattern trovato.")
        return None

    # Filtra i pattern marcati da OTP come "outside-search-window"
    # (es. corse notturne con costo basso ma fuori dalla finestra di ricerca)
    valid_patterns = [
        p for p in patterns
        if not any(
            n.get("tag") == "outside-search-window"
            for n in (p.get("systemNotices") or [])
        )
    ]
    if not valid_patterns:
        print("Nessun tripPattern valido dopo il filtro outside-search-window.")
        return None

    # Ordina i patterns per generalizedCost (costo generale) e prendi i migliori N
    ordered_patterns = sorted(
        valid_patterns,
        key=lambda p: p.get("generalizedCost") if p.get("generalizedCost") is not None else float("inf")
    )[:numberOfPatterns]


    # print the query with variables for debug
    #print("\n=== VARIABLES SENT TO OTP ===\n", json.dumps({"query": QUERY, "variables": variables, "result": responce_data}))

    return ordered_patterns

