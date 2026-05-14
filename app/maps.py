import folium
from pathlib import Path
import polyline
import re

base_directory = Path(__file__).resolve().parent.parent
ICONS_DIR = Path(__file__).resolve().parent / "templates" / "icons"

class Map:

    def __init__(self, center=[45.4642, 9.1900], zoomStart=14):
        self.mappa = folium.Map(
            location=center,
            zoom_start=zoomStart,
            control_scale=True,
            tiles=None # per non caricare la mappa di default 
        )

        # Aggiungi vari strati per far scegliere l'utente.
        # OSM resta il default, così all'apertura si vedono subito le vie.
        folium.TileLayer('openstreetmap', name="OSM", show=True).add_to(self.mappa)
        folium.TileLayer(
            'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
            attr='Esri',
            name='Satellitare',
            show=False #false per vedere bene le vie etichette, true per visione più realistica
        ).add_to(self.mappa)
        folium.TileLayer(
            'https://services.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}',
            attr='Esri',
            name='Etichette (vie/luoghi)',
            overlay=True,
            control=True,
            show=True
        ).add_to(self.mappa)
        
        # Aggiunge il selettore in alto a destra
        folium.LayerControl().add_to(self.mappa)

    # tipicamente il segmento da percorrere
    def aggiungiPolyline(self, coordinate, colore="blue", peso=5, opacità=0.7, tratteggio=None, tooltip="Percorso"):
        """Aggiunge una polyline alla mappa"""
        folium.PolyLine(
            locations=coordinate,
            color=colore,
            weight=peso,
            opacity=opacità,
            dash_array=tratteggio,
            tooltip=tooltip
        ).add_to(self.mappa)
    
    # può essere usato per un edificio o una qualsiasi area
    def aggiungiPoligono(self, coordinate, colore="yellow", fill=True, fill_opacity=0.2, tooltip=None):
        """Aggiunge un poligono alla mappa"""
        folium.Polygon(
            locations=coordinate,
            color=colore,
            fill=fill,
            fill_opacity=fill_opacity,
            tooltip=tooltip
        ).add_to(self.mappa)
    
    # ideale per indicare un singolo punto come una panchina o una fontanella
    def aggiungiMarker(self, punto, colore="blue", icona=None, tooltip=None, popup=None):
        """Aggiunge un marker alla mappa"""
        # Se 'icona' è una stringa (es. "info-sign") o None, creo un folium.Icon normale.
        # Se invece è già un oggetto (come un DivIcon o un Icon personalizzato), lo uso direttamente!
        if type(icona) is str or icona is None:
            icona_folium = folium.Icon(color=colore, icon=icona if icona else 'info-sign', prefix='glyphicon')
        else:
            icona_folium = icona

        folium.Marker(
            location=punto,
            icon=icona_folium,
            tooltip=tooltip,
            popup=popup
        ).add_to(self.mappa)
    
    def aggiungiPercorso(self, percorso, descrizione="Percorso a piedi"):

        self.aggiungiPolyline(
            coordinate=percorso.coordinate_della_polyline,
            tooltip=descrizione
        )

    # per aggiungere una pannello in alto a sinistra con i dettagli del percorso
    def aggiungiDettagli(self, durata, distanza, numero_barriere_trovate):
        """Aggiunge un pannello con i dettagli del percorso alla mappa"""
        html_content = f"""
            <div id="info-panel" style="position: fixed;
                        top: 10px;
                        right: 10px;
                        z-index:9999;
                        background-color:white;
                        opacity:0.9;
                        border:2px solid grey;
                        padding:10px;">
                <h3>Info sul Percorso</h3>
                distanza: {distanza:.2f} m<br>
                durata: {self.formatta_durata(durata)}<br>
                # barriere trovate: {numero_barriere_trovate}
            </div>
        """
        self.mappa.get_root().html.add_child(folium.Element(html_content))

    # serve solo per la funzione di prima
    def formatta_durata(self, secondi):
        """Formatta la durata in ore, minuti e secondi"""
        ore = int(secondi // 3600)
        minuti = int((secondi % 3600) // 60)
        secondi_rimanenti = int(secondi % 60)
        return f"{ore} h : {minuti} min : {secondi_rimanenti} sec"
    

    # helper per creare un'icona SVG personalizzata da file
    def _creaIconaSVG(self, nome_file, size=40, anchor=None):
        """
        Legge un file SVG da ICONS_DIR e restituisce un folium.DivIcon.

        nome_file: nome del file senza estensione (es. "barriera")
        size:      larghezza in pixel dell'icona renderizzata (default 40)
        anchor:    (x, y) del punto di ancoraggio rispetto al top-left del div;
                   default = centro-basso (punta del pin).
        """
        svg_path = ICONS_DIR / f"{nome_file}.svg"
        svg_content = svg_path.read_text(encoding="utf-8")

        # Rimuove gli attributi width/height fissi dal tag <svg> e li sostituisce con 100%/100%
        # così il div CSS controlla la dimensione effettiva.
        # Cattura l'intero tag <svg ...>, rimuove width/height, poi reinietta width="100%" height="100%"
        def _strip_svg_size(m):
            tag = m.group(0)
            tag = re.sub(r'\s+width="[^"]*"', '', tag)
            tag = re.sub(r'\s+height="[^"]*"', '', tag)
            tag = tag.replace('<svg', '<svg width="100%" height="100%"', 1)
            return tag
        svg_content = re.sub(r'<svg\b[^>]*>', _strip_svg_size, svg_content, count=1)

        # Il viewBox degli SVG del progetto è "0 0 100 140": ratio altezza/larghezza = 1.4
        # → l'altezza renderizzata = size * 1.4; la punta del pin è al centro-basso.
        rendered_h = size * 1.4
        if anchor is None:
            anchor = (size / 2, rendered_h)

        return folium.DivIcon(
            html=f'<div style="width:{size}px;height:{rendered_h}px;overflow:visible">{svg_content}</div>',
            icon_size=(size, rendered_h),
            icon_anchor=anchor
        )

    # per aggiungere un elemento OSM con tanto di popup nella mappa e link a street view!
    def aggiungiElemento(self, elemento, colore="red", icona="warning-sign", svg=None):
        """
        Aggiunge un ElementoOSM (Barriera o Facilitatore) alla mappa.

        svg: nome del file SVG (senza .svg) in templates/icons/ da usare come icona;
             se None, usa l'icona glyphicon standard (colore + icona).
        """
        
        punto = (elemento.coordinate_centroide.get("latitudine"), elemento.coordinate_centroide.get("longitudine"))
        
        # URL di Street View utilizzando le coordinate
        sv_url = f"https://www.google.com/maps?layer=c&cbll={punto[0]},{punto[1]}"

        # creo il popup
        popup = folium.Popup(
            f"""
                <h3>{elemento.nome}</h3>
                Descrizione: {elemento.descrizione}<br>
                <a href="{sv_url}" target="_blank" rel="noopener">Immagine Street View</a><br>
                ID: {elemento.id}
            """,
            max_width=300
        )

        # scelgo l'icona: SVG personalizzata oppure glyphicon standard
        icona_finale = self._creaIconaSVG(svg) if svg else icona

        # e aggiungo il marker
        self.aggiungiMarker(
            punto=punto,
            colore=colore,
            icona=icona_finale,
            tooltip=elemento.nome,
            popup=popup
        )

    def aggiungiBarriereFacilitatoriInfrastrutture(self, barriere, facilitatori, infrastrutture):
        """semplicemente aggiungo quelle cose (gli argomenti del metodo) alla mappa"""

        # Aggiungi le infrastrutture
        for infrastruttura in infrastrutture:
            self.aggiungiElemento(infrastruttura, svg="infrastruttura")
        # Aggiungi i facilitatori
        for facilitatore in facilitatori:
            self.aggiungiElemento(facilitatore, svg="facilitatore")
        # Aggiungi le barriere
        for barriera in barriere:
            self.aggiungiElemento(barriera, svg="barriera")

    def aggiungiMezzoPubblico(self, inizio, fine, nome_inizio, nome_fine, tipologia_mezzo, nome_linea, traccia, dati_accessibilita=True):
        """
        disegna la tratta dei mezzi pubblici tra inizio e fine,
        se in futuro si useranno piu mappe si potra passare quella desiderata

        inizio/fine: (lat, lon)
        tipologia_mezzo: es "metro", "bus", "tram", "treno"
        nome_linea: es "M1", "Tram 2", "Bus 90/91"
        """

        mezzo = str(tipologia_mezzo).lower()
        linea = str(nome_linea).strip()
        start = (float(inizio[0]), float(inizio[1]))
        end   = (float(fine[0]), float(fine[1]))

        stile = {
            "metro": {"color": "#8E44AD", "dash_array": "8,6", "weight": 6},
            "bus":   {"color": "#2980B9", "dash_array": "4,6", "weight": 5},
            "tram":  {"color": "#27AE60", "dash_array": "2,6", "weight": 5},
            "treno": {"color": "#2C3E50", "dash_array": "10,8", "weight": 6},
        }
        s = stile.get(mezzo, {"color": "#E67E22", "dash_array": "6,6", "weight": 5})

        # aggiungo la polyline col percorso che inizia e finisce in due punti diversi
        self.aggiungiPolyline(
            coordinate=polyline.decode(traccia), 
            colore=s["color"],
            peso=s["weight"],
            opacità=0.9,
            tratteggio=s["dash_array"],
            tooltip=f"{tipologia_mezzo} - {linea}"
        )
        
        # aggiungo il marker per la salita sul mezzo
        self.aggiungiMarker(
            punto=start,
            icona=self._creaIconaSVG("salire"), #folium.Icon(color="orange", icon="arrow-up"),
            tooltip=f'Sali su "{linea}"'
        )

        # aggiungo il marker per l'usciata dal mezzo
        self.aggiungiMarker(
            punto=end,
            icona=self._creaIconaSVG("scendere"), #folium.Icon(color="blue", icon="arrow-down"),
            tooltip=f'Scendi da "{linea}"'
        )

        messaggioSalita = f'⬆️ Sali su "{linea}" a "{nome_inizio}"'
        messaggioDiscesa = f'⬇️ Scendi da "{linea}" a "{nome_fine}"'

        # se voglio aggiungere i dati dell'accessibilità
        if dati_accessibilita:
            # prendo la lista di tutte le stazioni che sono diventate inaccessibili dall'ultima 
            # build del graph.obj questa lista deve essere aggiornata periodicamente
            stationsBecomeUnaccessible = []
            if tipologia_mezzo == "metro":
                try:
                    with open(base_directory / "data" / "OTP_data" / "inaccessible_stations_till_last_GTFSzip_file_update.txt", "r", encoding='utf-8') as recentlyInaccessibleStationsFile:
                        for stazione in recentlyInaccessibleStationsFile:
                            stationsBecomeUnaccessible.append(stazione.strip())
                except FileNotFoundError:
                    print("manca il file delle stazioni diventate inaccessibili dall'ultima build!")

            # e ora devo capire se le stazioni che sto considerando sono incluse tra quelle diventate inaccessibili
            # per farlo mi serve sapere il nome della stazione!
            if str(nome_inizio) in stationsBecomeUnaccessible:
                messaggioSalita += f'<br>ATTENZIONE! In questa stazione non si garantisce completa accessibilità'
            else:
                messaggioSalita += f'<br>Stazione accessibile!'

            if str(nome_fine) in stationsBecomeUnaccessible:
                messaggioDiscesa += f'<br>ATTENZIONE! In questa stazione non si garantisce completa accessibilità'
            else:
                messaggioDiscesa += f'<br>Stazione accessibile!'

        # helper per label sempre visibili
        def _div_label(text, dx_px=10, dy_px=-10, w=320, h=28):
            return folium.DivIcon(
                html=f"""
                <div style="
                    transform: translate({dx_px}px, {dy_px}px);
                    display: inline-block;
                    font-size: 12px;
                    font-weight: bold;
                    color: black;
                    background-color: white;
                    padding: 2px 6px;
                    border-radius: 6px;
                    border: 1px solid black;
                    white-space: nowrap;
                    pointer-events: none;
                ">{text}</div>
                """,
                icon_size=(w, h),
                icon_anchor=(0, 0)
            )

        # finalmente aggiungo i marker 
        self.aggiungiMarker(
            punto=start,
            icona=_div_label(messaggioSalita, dx_px=10, dy_px=-10)
        )
        self.aggiungiMarker(
            punto=end,
            icona=_div_label(messaggioDiscesa, dx_px=10, dy_px=-10)
        )

        return self



    def adattaVistaAlPercorso(self, coordinate_partenza, coordinate_arrivo, coordinate_extra=None):
        """
        Centra e zooma la mappa per includere tutto il percorso.

        coordinate_partenza: (lat, lon) del punto di partenza
        coordinate_arrivo:   (lat, lon) del punto di arrivo
        coordinate_extra:    lista opzionale di (lat, lon) aggiuntive (es. stazioni intermedie)
                             per rendere il bounding box più preciso
        """
        tutti_i_punti = [coordinate_partenza, coordinate_arrivo]
        if coordinate_extra:
            tutti_i_punti.extend(coordinate_extra)

        # Filtra punti non validi (None o con valori None al loro interno)
        punti_validi = [
            p for p in tutti_i_punti
            if p is not None and p[0] is not None and p[1] is not None
        ]

        if not punti_validi:
            return  # nessun punto valido, non fare nulla

        lats = [p[0] for p in punti_validi]
        lons = [p[1] for p in punti_validi]

        # calcolo il bounding box
        south_west = [min(lats), min(lons)]
        north_east = [max(lats), max(lons)]

        self.mappa.fit_bounds([south_west, north_east], padding=(40, 40))

    # al posto di salvare la mappa la estraggo in html così da poterla mettere nell'iframe della pagina dei risultati per gli utenti
    def getMappaInHTML(self):
        """Restituisce il codice HTML della mappa come stringa"""
        self.mappa.render()
        return self.mappa.get_root().render()