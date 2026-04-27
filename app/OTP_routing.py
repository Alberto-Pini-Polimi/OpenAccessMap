import os
import requests

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
  $arriveBy: Boolean
) {
  trip(
    dateTime: $dateTime,
    from: $from,
    to: $to,
    modes: $modes,
    wheelchairAccessible: $wheelchair,
    searchWindow: $searchWindow,
    arriveBy: $arriveBy
  ) {
    tripPatterns {
      duration
      distance
      generalizedCost
      systemNotices { tag text }
      legs {
        mode
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
        line { publicCode name id presentation { colour } }
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

# ALTRE FUNZIONI

# def sign_up(users: dict) -> str | None:
#     username = input("Scegli username: ").strip()
#     if not username:
#         print("Username vuoto.")
#         return None
#     if username in users:
#         print("Username già esistente.")
#         return None
#     users[username] = {"favorite": None}
#     print("Registrazione OK.")
#     return username

# def sign_in(users: dict) -> str | None:
#     username = input("Username: ").strip()
#     if username not in users:
#         print("Utente non trovato.")
#         return None
#     print("Login OK.")
#     return username

# def set_favorite(users: dict, username: str, from_obj: dict, to_obj: dict) -> None:
#     users[username]["favorite"] = {"from": from_obj, "to": to_obj}






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

    # Ordina i patterns per generalizedCost (costo generale) e prendi i top 3 per debug
    ordered_patterns = sorted(
        patterns,
        key=lambda p: p.get("generalizedCost") if p.get("generalizedCost") is not None else float("inf")
    )[:numberOfPatterns] # prendo i due migliori pattern

    return ordered_patterns

