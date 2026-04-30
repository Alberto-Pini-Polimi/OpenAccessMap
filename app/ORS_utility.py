from pathlib import Path
from enum import Enum
from pyproj import Transformer
from shapely.geometry import Point, LineString, Polygon, MultiPolygon
import polyline
import os
import json

base_directory = Path(__file__).resolve().parent.parent # this corresponds to the base directory of the repo

# definisco un'area di distanza attorno ai percorsi
BUFFER_FACILITATORI_IN_METRI = 10
BUFFER_BARRIERE_IN_METRI = 5
BUFFER_INFRASTRUTTURE_IN_METRI = 50
BUFFER_ATTORNO_AL_QUALE_SI_CREA_UNA_ZONA_PROIBITA_IN_METRI = 15

# enum con problemi di mobilitò
class ProblemiMobilità(Enum):

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

# enum con tipologie di elementi nella mappa
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
    

class Elemento:
    """
        Classe base per qualsiasi elemento (barriera / facilitatore / infrastruttura)
    """
    
    def __init__(self, elemento_del_DB):
        self.id = elemento_del_DB['id']
        self.coordinate_centroide = elemento_del_DB["coordinateCentroide"]
        self.autore = elemento_del_DB["autore"]
        self.ranking = elemento_del_DB["ranking"]
        self.nome = elemento_del_DB["nome"]
        self.descrizione = elemento_del_DB["descrizione"]
        self.barriera_per = elemento_del_DB["barrieraPer"] 
        self.facilitatore_per = elemento_del_DB["facilitatorePer"] 
        self.infrastruttura_per = elemento_del_DB["infrastrutturaPer"] 

    def cambiaRanking(self, quantità):

        self.ranking += quantità

        # saturo
        if self.ranking > 100:
            self.ranking = 100
        elif self.ranking < 0:
            self.ranking = 0

    def per(self, problematica):
        """
            Ritorna cosa self è per l'utente (barriera / facilitatore / infrastruttura)
        """
        if problematica in self.barriera_per:
            return TipoElemento.BARRIERA
        elif problematica in self.facilitatore_per:
            return TipoElemento.FACILITATORE
        elif problematica in self.infrastruttura_per:
            return TipoElemento.INFRASTRUTTURA
        else:
            return None

# Definisci i sistemi di coordinate e le funzioni per la trasformazione tra i sistemi
wgs84 = 'EPSG:4326' # Sistema di coordinate geografiche (lat/lon)
utm_zone = 'EPSG:32632' # Proiezione UTM adatta (Milano nella zona UTM 32N)
project_to_utm = Transformer.from_crs(wgs84, utm_zone, always_xy=True).transform
project_to_wgs = Transformer.from_crs(utm_zone, wgs84, always_xy=True).transform

def inverti_coordinate(coord):
    return coord[1], coord[0]


class Percorso():

    """
        input per l'inizializzazione:
        percorso: {
            "summary": {
                "distance": 100,
                "duration": 100
            },
            "segments" <-- ignoro totalmente
            "bbox": [coordinate],
            "geometry": encoded_data_per_la_rappresentazione_del_percorso_come_un_poligono,
            "waypoints" <-- ignoro totalmente
        }
    
    """

    # geo = shapely -> formato "semplice" cioè insiemi di coordinate (con classi Point Line Polygon ...)
    # utm -> formato usato per le funzioni di buffer e contains
    
    def __init__(self, percorso):

        # prendo i dati del summary
        self.distanza = percorso["summary"]["distance"]
        self.durata = percorso["summary"]["duration"]
        # prendo il bbox (bounding box per acere un rang in cui cercare)
        self.bbox = percorso["bbox"] # lo userò per cercare barriere e facilitatori nel DB
        # faccio il decoding della polyline (encodata in geometry)
        self.coordinate_della_polyline = polyline.decode(percorso["geometry"]) # decode restituisce un inseme di nodi (coordinate)
        
        # Inverti le coordinate per shapely (lon, lat)
        coordinate_shapely = [inverti_coordinate(coord) for coord in self.coordinate_della_polyline]
        self.percorso_geo = LineString(coordinate_shapely)
        # Proietta la polyline in UTM
        percorso_utm_coords = [project_to_utm(lon, lat) for lat, lon in self.coordinate_della_polyline]
        self.percorso_utm = LineString(percorso_utm_coords)
        
        # Inizializza attributi
        self.barriere_trovate = []
        self.facilitatori_trovati = []
        self.infrastrutture_trovate = []
        self.barriere_da_evitare = []
        self.facilitatori_da_includere = []
        self.infrastrutture_da_includere = []
        
        # Crea il buffer di default
        self.creaBufferBarriere()
        self.creaBufferFacilitatori()
        self.creaBufferInfrastrutture()

    def creaBufferFacilitatori(self):
        """Crea un buffer attorno al percorso in UTM per i facilitatori"""
        self.bufferFacilitatori_utm = self.percorso_utm.buffer(BUFFER_FACILITATORI_IN_METRI)
        # Riproietta il buffer in WGS84 per la visualizzazione e il controllo dei facilitatori
        area_limitrofa_al_percorso_geo_coords = [project_to_wgs(x, y) for x, y in self.bufferFacilitatori_utm.exterior.coords]
        # Crea un poligono per i facilitatori
        self.bufferFacilitatori_geo = Polygon(area_limitrofa_al_percorso_geo_coords)

    def creaBufferBarriere(self):
        """Crea un buffer attorno al percorso in UTM per le barriere"""
        self.bufferBarriere_utm = self.percorso_utm.buffer(BUFFER_BARRIERE_IN_METRI)
        # Riproietta il buffer in WGS84 per la visualizzazione e il controllo delle barriere
        area_limitrofa_al_percorso_geo_coords = [project_to_wgs(x, y) for x, y in self.bufferBarriere_utm.exterior.coords]
        # Crea un poligono per le barriere
        self.bufferBarriere_geo = Polygon(area_limitrofa_al_percorso_geo_coords)

    def creaBufferInfrastrutture(self):
        """Crea un buffer attorno al percorso in UTM per le infrastrutture"""
        self.bufferInfrastrutture_utm = self.percorso_utm.buffer(BUFFER_INFRASTRUTTURE_IN_METRI)
        # Riproietta il buffer in WGS84 per la visualizzazione e il controllo delle infrastrutture
        area_limitrofa_al_percorso_geo_coords = [project_to_wgs(x, y) for x, y in self.bufferInfrastrutture_utm.exterior.coords]
        # Crea un poligono per le infrastrutture
        self.bufferInfrastrutture_geo = Polygon(area_limitrofa_al_percorso_geo_coords)

    def isNelBuffer(self, elemento_osm, tipo_buffer):
        """Verifica se un punto è all'interno del buffer"""

        punto_geo = Point([elemento_osm.coordinate_centroide.get("longitudine"), elemento_osm.coordinate_centroide.get("latitudine")])
            
        # Proietta il punto barriera in UTM
        punto_utm = project_to_utm(punto_geo.x, punto_geo.y)
        punto_utm_geo = Point(punto_utm)
        # Verifica il contenimento nel buffer UTM e ritorna vero o falso
        if tipo_buffer == "barriere":
            return self.bufferBarriere_utm.contains(punto_utm_geo)
        elif tipo_buffer == "facilitatori":
            return self.bufferFacilitatori_utm.contains(punto_utm_geo)
        elif tipo_buffer == "infrastrutture":
            return self.bufferInfrastrutture_utm.contains(punto_utm_geo)
        else:
            raise ValueError("Tipo di buffer non valido. Deve essere 'barriere' o 'facilitatori'.")

    def trovaElementiSulPercorso(self, elementsFromORS_Data, wheelchair=False):
        """
            Trova barriere, facilitatori ed infrastrutture sul percorso in base agli elementi caricati e all'utente.
            Categorizza gli elementi per un certo utente e verifica che questi rientrino nel buffer appositio della 
            categoria di elemento calcolata.
        """
        self.barriere_trovate = []
        self.facilitatori_trovati = []
        self.infrastrutture_trovate = []

        problematica = ""
        if wheelchair:
            problematica = "Motoria"

        for elemento in elementsFromORS_Data:
            
            # Verifica cosa l'elemento è per l'utente e se è nel rispettivo buffer

            if elemento.per(problematica) == TipoElemento.FACILITATORE and self.isNelBuffer(elemento, "facilitatori"):
                self.facilitatori_trovati.append(elemento)
            
            elif elemento.per(problematica) == TipoElemento.BARRIERA and self.isNelBuffer(elemento, "barriere"):
                self.barriere_trovate.append(elemento)
            
            elif elemento.per(problematica) == TipoElemento.INFRASTRUTTURA and self.isNelBuffer(elemento, "infrastrutture"):
                self.infrastrutture_trovate.append(elemento)
            
            else:
                continue
        
        return self.barriere_trovate, self.facilitatori_trovati, self.infrastrutture_trovate






def caricaElementiDaJSON(directoryDatiORS, bbox, wheelchair=False):
    """
        Carica tutti gli elementi dai file JSON che trova nella directory "data" che:
            - abbiano il centroide all'interno della bbox specificata
            - che siano di interesse per l'utente specificato
    """

    # itero tutti i file .json contenenti i potenziali elementi da caricare in memoria
    elementi = []
    for file_name in os.listdir(directoryDatiORS):

        #print(f"Trovato file: {file_name}")

        if file_name.endswith('.json'):
            file_path = os.path.join(directoryDatiORS, file_name)
            
            with open(file_path, 'r', encoding='utf-8') as file:

                contenuto = file.read()
                if not contenuto.strip():  # Verifica se il contenuto (dopo aver rimosso spazi bianchi) è vuoto
                    #print("Vuoto, skipppo\n")
                    continue  # Passa al file successivo

                # Carico il contenuto del file
                try:
                    data = json.loads(contenuto)
                    # Processa i dati JSON
                    aggiunti = 0
                    for elemento in data:
                        # controllo se rientra nella bounding box
                        if bbox[0] <= elemento["coordinateCentroide"]["longitudine"] <= bbox[2] and bbox[1] <= elemento["coordinateCentroide"]["latitudine"] <= bbox[3]:
                            elemento_osm = Elemento(elemento)  # Crea l'elemento OSM
                            # includo tutte le infrastrutture (purché siano per qualcuno) e, se voglio wheelchair anche tutte le barriere e i facilitatori per una problematica motoria
                            if elemento_osm.infrastruttura_per != [] or wheelchair and ("Motoria" in elemento_osm.barriera_per or "Motoria" in elemento_osm.facilitatore_per):
                                elementi.append(elemento_osm)  # E lo aggiunge agli altri
                                aggiunti += 1

                    
                    #print(f"{aggiunti} elementi aggiunti!\n")

                except json.JSONDecodeError:
                    print(f"Errore nel parsing del file JSON: {file_path}")
                except Exception as e:
                    print(f"Errore durante l'elaborazione del file {file_path}: {e}")
                    print(f"Errore: bbox: {bbox}")
                    print(f"Errore: elemento: {elemento['coordinateCentroide']}")
                    print(f"Id elemento: {elemento['id']}")


    
    #print(f"{len(elementi)} in totale trovati!")

    return elementi # Ritorna quindi tutti gli elementi parsati
