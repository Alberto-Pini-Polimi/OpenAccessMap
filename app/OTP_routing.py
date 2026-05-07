import requests
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
      expectedStartTime
      expectedEndTime
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

# helper function for construct_variables()
def get_now_local_iso():
    milan_tz = ZoneInfo("Europe/Rome")
    now = datetime.now(milan_tz)

    # Formatta in ISO 8601 UTC (OTP richiede UTC)
    # Converti a UTC per evitare problemi di interpretazione del timezone
    # Risultato es: '2026-05-03T13:50:00Z' (UTC, 2 ore prima di Milano)
    now_utc = now.astimezone(timezone.utc)
    return now_utc.replace(microsecond=0, tzinfo=timezone.utc).isoformat()

# constructing variable to pass along query to OTPv2 local server instance
def construct_variables(from_obj, to_obj, on_foot, wheelchair, walkSpeed):
    vars = {
        "from": from_obj, # queste sono solo coordinate di default, verranno sovrascritte da main.py
        "to": to_obj,
        "dateTime": get_now_local_iso(), # ora di partenza (in formato ISO locale) viene presa al momento della richiesta
        "timetableView": False,
        "arriveBy": False, # alla destinazione ci arrivo quando voglio ma il trip parte da "dateTime"
        "searchWindow": 40, # finestra del tempo di partenza
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
        "wheelchair": wheelchair,
        "walkSpeed": walkSpeed # m/s, velocità di camminata impostata a 1.3 m/s (4.68 km/h), equivalente al passo medio di un essere umano adulto in piano.  
    }

    if on_foot: # if user wants on_foot, I will not use public transport
        vars["modes"]["transportModes"] = []

    return vars

def route_OTP(from_obj, to_obj, on_foot, wheelchair, walkSpeed, numberOfPatterns=2):

    # construct variables to pass to OTP
    variables = construct_variables(from_obj, to_obj, on_foot, wheelchair, walkSpeed)

    # request to OTP
    otp_request = requests.post(
        url=URL,  # URL del server OTP
        json={"query": QUERY, "variables": variables},  # Payload GraphQL con query e variabili
        headers=HEADERS,  # Headers con Content-Type application/json
        timeout=60  # Timeout di 60 secondi per la richiesta
    )
    otp_request.raise_for_status()  # If there is any error, raise it
    responce_data = otp_request.json() # parsing the data

    # handling Graph.obj errors
    if responce_data.get("errors"):
        print("GraphQL errors:")
        for errore in responce_data["errors"]:
            print(" -", errore.get("message"))
        return None  # Ritorna None in caso di errori

    # Extracting trip patterns from response (these are the segments)
    patterns = responce_data.get("data").get("trip").get("tripPatterns") or []
    if not patterns:
        print("Nessun tripPattern trovato.")
        return None

    # Ordering patterns based on the generalizedCost OTP2 assigned them:
    ordered_patterns = sorted(
        patterns, # if no generalized cost is assigne then it is set to inf and thus it is put last
        key=lambda p: p.get("generalizedCost") if p.get("generalizedCost") is not None else float("inf")
    )

    # Now we want to extract 1 pattern: 
    #  - least generalized cost if it is within the search window
    #  - fastest arrival time if it is outside the search window

    # final patterns to return in here:
    result_patterns = []

    # split patterns from the response into outside or inside the search window
    patternsInsideSearchWindow  = []
    patternsOutsideSearchWindow = [] # ordered by arrival time and not generalized cost
    # simply populate the ordered lists
    for pattern in ordered_patterns:
        # First I need to understand weather this pattern is inside the search window:
        if isPatternOutsideOfSearchWindow(pattern):
            patternsOutsideSearchWindow.append(pattern)
        else: # if the pattern is within the search window
            patternsInsideSearchWindow.append(pattern)

    # now I still need to reorder the patterns outside the search window by the arrival times
    patternsOutsideSearchWindow.sort(
        key=lambda p: p.get("expectedEndTime") if p.get("expectedEndTime") is not None else float("inf")
    )

    # and now I need to choose the patterns to take the `numberOfPatterns` patterns

    # start by adding all the packets inside the search window
    result_patterns.extend(patternsInsideSearchWindow[:numberOfPatterns])
    if numberOfPatterns > len(patternsInsideSearchWindow):
        # and then add the ones outside the search window up to filling the requested number of packets
        result_patterns.extend(
            patternsOutsideSearchWindow[:numberOfPatterns - len(patternsInsideSearchWindow)]
        )

    # print the query with variables for debug
    #print("\n=== VARIABLES SENT TO OTP ===\n", json.dumps({"query": QUERY, "variables": variables, "result": responce_data}))

    return result_patterns

# helper function
def isPatternOutsideOfSearchWindow(pattern):

    # if no system notices exist then I am sure it is inside the search window
    if pattern.get("systemNotices") is None:
        return False

    # iterate all notices to see if one says that it is outside of search window
    for notice in pattern.get("systemNotices"):
        if notice.get("tag") == "outside-search-window":
            return True

    return False
    
    