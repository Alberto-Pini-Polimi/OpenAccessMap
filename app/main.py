import router
import os
import sqlite3
import time
import requests
import sys
import bcrypt
import re
from datetime import datetime, timezone

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    jsonify,
    send_from_directory,
)

from DB.database import (
    get_connection,
    create_user,
    get_user_by_username,
    get_user_by_email,
    get_user_favourites,
    add_favourite,
)

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-key-change-me")

# URL di OpenTripPlanner
OTP_URL = os.getenv("OTP_URL", "http://localhost:8080/otp/transmodel/v3")

# =========================
# OTP helpers
# =========================

def attendi_otp(url_otp, timeout_minuti=10):
    """
    Aspetta finché OTP non risponde.
    Utile perché il routing non può partire se il servizio OTP non è ancora pronto.
    """
    print(f"⏳ Attendo che OpenTripPlanner sia pronto all'indirizzo: {url_otp}")

    inizio = time.time()
    timeout_secondi = timeout_minuti * 60

    while True:
        try:
            # Qui facciamo una richiesta semplice per verificare se OTP è vivo
            response = requests.get("http://otp:8080/otp/", timeout=5)
            if response.status_code < 500:
                print("✅ OTP pronto.")
                return True
        except requests.RequestException:
            pass

        tempo_trascorso = time.time() - inizio
        if tempo_trascorso > timeout_secondi:
            print("\n❌ Timeout: OTP non sembra essere partito o c'è un errore")
            sys.exit(1)

        time.sleep(10)


def now_utc_iso() -> str:
    """
    Restituisce timestamp in formato ISO UTC compatibile con quello atteso da OTP.
    Esempio: 2026-04-03T10:15:00.123Z
    """
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def format_result_text(text: str) -> str:
    """
    Trasforma il testo degli itinerari in HTML strutturato:
    - Converte "--- Itinerario #N ---" in tag h3
    - Crea elenchi ordinati <ol> per le legs
    - Rimuove i numeri duplicati dalle righe
    """
    lines = text.replace("-->", "&#8594;").split("\n") # rimpiazzo --> con la freccia in html e splitto sul new line
    result = []
    in_itinerary = False
    
    for line in lines:
        # Titolo itinerario
        match_title = re.match(r"--- Itinerario #(\d+) ---", line)
        if match_title:
            # Chiudi la lista precedente se era aperta
            if in_itinerary:
                result.append("</ol>")
            num = match_title.group(1)
            result.append(f"<h3>{num}° Itinerario</h3>")
            in_itinerary = True
            continue
        
        # Info del viaggio (generalized cost, durata)
        if line.startswith("Generalized cost:"):
            result.append(f"<p>{line}</p>")
            result.append("<ol>")
            continue
        
        # Legs (elementi con tab e numero)
        if line.startswith("\t"):
            # Rimuovi il tab iniziale, poi rimuovi il numero duplicato (es. "1. ")
            leg_content = line.lstrip("\t")
            # Rimuove il pattern "N. " dove N è uno o più cifre
            leg_content = re.sub(r"^\d+\.\s+", "", leg_content)
            result.append(f"<li>{leg_content}</li>")
            continue
        
        # Linee vuote
        if line.strip() == "":
            continue
        
        # Altre linee (se ce ne sono)
        if line.strip():
            result.append(f"<p>{line}</p>")
    
    # Chiudi l'ultima lista se era aperta
    if in_itinerary:
        result.append("</ol>")
    
    return "\n".join(result)


# =========================
# Password helpers
# =========================

def hash_password(password: str) -> str:
    password_bytes = password.encode("utf-8")
    hashed = bcrypt.hashpw(password_bytes, bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        password_bytes = password.encode("utf-8")
        stored_hash_bytes = stored_hash.encode("utf-8")
        return bcrypt.checkpw(password_bytes, stored_hash_bytes)
    except Exception:
        return False


# =========================
# Utils
# =========================

def get_logged_user():
    """
    Recupera i dati minimi dell'utente loggato dalla sessione Flask.
    Se non c'è user_id, l'utente non è autenticato.
    """
    user_id = session.get("user_id")
    username = session.get("username")
    if not user_id:
        return None
    return {"id": user_id, "username": username}


def build_point_from_form(prefix: str):
    """
    Costruisce il punto 'from' o 'to' leggendo i campi hidden:
    - from_lat / from_lon
    - to_lat / to_lon

    Questi campi vengono riempiti dal frontend quando l'utente seleziona
    un indirizzo dalla lista dei risultati geocodificati.

    prefix sarà quindi "from" oppure "to".
    """
    lat = request.form.get(f"{prefix}_lat", "").strip().replace(",", ".")
    lon = request.form.get(f"{prefix}_lon", "").strip().replace(",", ".")

    if not lat or not lon:
        raise ValueError(f"Seleziona un indirizzo valido per {prefix}")

    try:
        lat = float(lat)
        lon = float(lon)
    except ValueError:
        raise ValueError(f"Coordinate non valide per {prefix}")

    return {
        "coordinates": {
            "latitude": lat,
            "longitude": lon,
        }
    }


def point_from_favourite(fav):
    """
    Converte un preferito salvato nel formato atteso dal payload OTP.
    """
    return {
        "coordinates": {
            "latitude": fav["latitude"],
            "longitude": fav["longitude"],
        }
    }


def get_default_variables(wheelchair=True):
    """
    Payload base per OTP da sovrascrivere.
    """
    return {
        "from": {"coordinates": {"latitude": 45.47437, "longitude": 9.183323}},
        "to": {"coordinates": {"latitude": 45.48535, "longitude": 9.20944}},
        "dateTime": "2026-02-28T16:07:08.511Z",
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
        "arriveBy": False,
        "searchWindow": 40,
    }


# =========================
# API geocoding
# =========================

@app.route("/api/geocode")
def api_geocode():
    """
    Endpoint chiamato dal frontend (dashboard.js inline nel template).

    Flusso:
    1. l'utente scrive un indirizzo
    2. il frontend chiama /api/geocode?q=...
    3. qui interroghiamo Nominatim
    4. restituiamo JSON semplificato con label / lat / lon

    Il frontend poi usa quei risultati per:
    - mostrare la lista
    - far scegliere un punto
    - salvare nei campi hidden del form
    """
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])

    try:
        response = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={
                "q": q,
                "format": "jsonv2",
                "limit": 5,
                "addressdetails": 1,
                "countrycodes": "it",
            },
            headers={
                # Nominatim richiede uno User-Agent sensato
                "User-Agent": "route-app/1.0"
            },
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()

        # Normalizziamo il formato dei risultati per il frontend
        results = []
        for item in data:
            results.append({
                "label": item.get("display_name", "Risultato"),
                "lat": float(item["lat"]),
                "lon": float(item["lon"]),
            })

        return jsonify(results)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# =========================
# Routes
# =========================

@app.route("/")
def home():
    """
    Redirect iniziale:
    - se l'utente è già loggato va in dashboard
    - altrimenti va in login
    """
    if session.get("user_id"):
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    """
    Login classico con verifica password hashata.
    """
    if request.method == "POST":
        conn = get_connection()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        user = get_user_by_username(conn, username)
        conn.close()

        if not user:
            flash("Utente non trovato.", "error")
            return render_template("login.html")

        if not verify_password(password, user["password_hash"]):
            flash("Password errata.", "error")
            return render_template("login.html")

        session["user_id"] = user["id"]
        session["username"] = user["username"]

        flash(f"Benvenuto, {user['username']}.", "success")
        return redirect(url_for("dashboard"))

    return render_template("login.html")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    """
    Registrazione utente.
    Fa i controlli minimi su:
    - campi obbligatori
    - unicità username
    - unicità email
    """
    if request.method == "POST":
        conn = get_connection()

        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()
        mobility_problem = request.form.get("mobility_problem", "").strip() or None

        if not username or not email or not password:
            flash("Username, email e password sono obbligatori.", "error")
            conn.close()
            return render_template("signup.html")

        if get_user_by_username(conn, username):
            flash("Username già esistente.", "error")
            conn.close()
            return render_template("signup.html")

        if get_user_by_email(conn, email):
            flash("Email già esistente.", "error")
            conn.close()
            return render_template("signup.html")

        password_hash = hash_password(password)

        try:
            create_user(
                conn=conn,
                username=username,
                email=email,
                password_hash=password_hash,
                mobility_problem=mobility_problem,
            )
            conn.close()
            flash("Utente creato con successo. Ora puoi fare login.", "success")
            return redirect(url_for("login"))

        except sqlite3.IntegrityError as e:
            conn.close()
            flash(f"Errore database: {e}", "error")
            return render_template("signup.html")

    return render_template("signup.html")


@app.route("/logout")
def logout():
    """
    Logout: svuota la sessione.
    """
    session.clear()
    flash("Logout effettuato.", "success")
    return redirect(url_for("login"))


@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    """
    Route principale dell'app.

    GET:
    - mostra la dashboard con i preferiti

    POST:
    - legge input utente
    - costruisce payload per OTP
    - eventualmente salva nuovi preferiti
    - aspetta che OTP sia pronto
    - cancella la vecchia mappa
    - chiama OTP_routing.route(...)
    - mostra result.html con iframe verso la mappa
    """
    user = get_logged_user()
    if not user:
        return redirect(url_for("login"))

    conn = get_connection()
    favourites = get_user_favourites(conn, user["id"])

    if request.method == "POST":
        try:
            variables = get_default_variables(wheelchair=True)

            # =========================
            # ORIGINE
            # =========================
            # Se l'utente ha scelto "preferito", prendiamo lat/lon dal DB.
            # Altrimenti leggiamo from_lat/from_lon che arrivano dal frontend
            # dopo la selezione di un indirizzo sulla mappa.
            from_mode = request.form.get("from_mode", "manual")
            if from_mode == "favourite":
                from_fav_id = request.form.get("from_favourite")
                selected = next((f for f in favourites if str(f["id"]) == str(from_fav_id)), None)
                if not selected:
                    raise ValueError("Preferito FROM non valido.")
                from_obj = point_from_favourite(selected)
            else:
                from_obj = build_point_from_form("from")

                # Se l'utente ha spuntato "salva nei preferiti" salviamo
                # il punto selezionato con la label indicata.
                save_from = request.form.get("save_from")
                from_label = request.form.get("from_label", "").strip()
                if save_from and from_label:
                    try:
                        add_favourite(
                            conn,
                            user["id"],
                            from_label,
                            from_obj["coordinates"]["latitude"],
                            from_obj["coordinates"]["longitude"],
                        )
                    except sqlite3.IntegrityError:
                        flash("Label FROM già esistente tra i preferiti.", "error")

            # =========================
            # DESTINAZIONE
            # =========================
            to_mode = request.form.get("to_mode", "manual")
            if to_mode == "favourite":
                to_fav_id = request.form.get("to_favourite")
                selected = next((f for f in favourites if str(f["id"]) == str(to_fav_id)), None)
                if not selected:
                    raise ValueError("Preferito TO non valido.")
                to_obj = point_from_favourite(selected)
            else:
                to_obj = build_point_from_form("to")

                save_to = request.form.get("save_to")
                to_label = request.form.get("to_label", "").strip()
                if save_to and to_label:
                    try:
                        add_favourite(
                            conn,
                            user["id"],
                            to_label,
                            to_obj["coordinates"]["latitude"],
                            to_obj["coordinates"]["longitude"],
                        )
                    except sqlite3.IntegrityError:
                        flash("Label TO già esistente tra i preferiti.", "error")

            
            # =========================
            # COMPLETAMENTO PAYLOAD OTP
            # =========================
            variables["from"] = from_obj
            variables["to"] = to_obj
            
            if request.form.get("on_foot") == "on":
                variables["modes"]["transportModes"] = []
                
            variables["wheelchair"] = request.form.get("wheelchair") == "on"

            # additional fixed parameters
            variables["searchWindow"] = 40
            variables["dateTime"] = now_utc_iso()

            # Prima di fare il routing aspettiamo che OTP sia disponibile
            otp_ready = attendi_otp(OTP_URL, timeout_minuti=3)
            if not otp_ready:
                conn.close()
                flash("OTP non è raggiungibile al momento.", "error")
                return render_template("dashboard.html", user=user, favourites=favourites)


            # PROVO A FARE IL ROUTING
            try:
                # questo esegue OTP, divide in legs e aggiunge tutto alla mappa (i legs a piedi vengono calcolati di ORS)
                resultMap, resultData = router.route(variables=variables) # resultMap è la mappa risultato 

            except ImportError as e:
                conn.close()
                flash(f"Non trovo OTP_routing.py: {e}", "error")
                return render_template("dashboard.html", user=user, favourites=favourites)
            except RuntimeError as e:
                conn.close()
                flash(f"Percorso troppo fuori da Milano: {e}", "error")
                return render_template("dashboard.html", user=user, favourites=favourites)
            except Exception as e:
                conn.close()
                flash(f"Errore generico durante il routing: {e}", "error")
                return render_template("dashboard.html", user=user, favourites=favourites)

            conn.close()

            # result.html incorpora la mappa vera tramite iframe verso /output-map
            return render_template(
                "result.html",
                variables=variables,
                result=resultMap.getMappaInHTML(), # converto la mappa da oggetto a pagina HTML da mettere in un iframe
                #resultHTML=format_result_text(resultText)
                resultData=resultData
            )

        except ValueError as e:
            conn.close()
            flash(str(e), "error")
            return render_template("dashboard.html", user=user, favourites=favourites)

        except Exception as e:
            conn.close()
            flash(f"Errore imprevisto: {e}", "error")
            return render_template("dashboard.html", user=user, favourites=favourites)

    conn.close()
    return render_template("dashboard.html", user=user, favourites=favourites)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)