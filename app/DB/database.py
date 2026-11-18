import os
import sqlite3
from pathlib import Path
from typing import Optional


DB_PATH = Path(os.getenv("DATABASE_PATH", "data/database.db"))  # salvato nella cartella persistente data/


def get_connection(db_path: Path | str = DB_PATH) -> sqlite3.Connection:
    """
    Apre una connessione SQLite e abilita le foreign keys.
    Imposta anche row_factory per leggere i risultati come dict-like rows.
    Inizializza automaticamente le tabelle se il database è nuovo.
    """
    path_obj = Path(db_path)
    path_obj.parent.mkdir(parents=True, exist_ok=True)
    is_new = not path_obj.exists()

    conn = sqlite3.connect(path_obj)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row  # permette di accedere alle colonne per nome, e di convertire facilmente in dict

    if is_new:
        try:
            from DB.init_db import create_tables, create_triggers
            create_tables(conn)
            create_triggers(conn)
        except Exception:
            try:
                from app.DB.init_db import create_tables, create_triggers
                create_tables(conn)
                create_triggers(conn)
            except Exception as e:
                print(f"⚠️ Inizializzazione automatica schema DB fallita: {e}")

    return conn


# =========================
# USERS
# =========================

def create_user(
    conn: sqlite3.Connection,
    username: str,
    email: str,
    password_hash: str,
    mobility_problem: Optional[str] = None,
) -> int:
    """
    Crea un nuovo utente e ritorna l'id inserito.
    Lancia sqlite3.IntegrityError se username o email esistono già.
    """
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO users (username, email, password_hash, mobility_problem)
        VALUES (?, ?, ?, ?)
        """,
        (username.strip(), email.strip().lower(), password_hash, mobility_problem),
    )
    conn.commit()
    return cursor.lastrowid


def get_user_by_username(conn: sqlite3.Connection, username: str) -> Optional[sqlite3.Row]:
    """
    Ritorna l'utente con questo username, oppure None.
    """
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT *
        FROM users
        WHERE username = ?
        """,
        (username.strip(),),
    )
    return cursor.fetchone()


def get_user_by_email(conn: sqlite3.Connection, email: str) -> Optional[sqlite3.Row]:
    """
    Ritorna l'utente con questa email, oppure None.
    """
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT *
        FROM users
        WHERE email = ?
        """,
        (email.strip().lower(),),
    )
    return cursor.fetchone()


def get_user_by_id(conn: sqlite3.Connection, user_id: int) -> Optional[sqlite3.Row]:
    """
    Ritorna l'utente con questo id, oppure None.
    """
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT *
        FROM users
        WHERE id = ?
        """,
        (user_id,),
    )
    return cursor.fetchone()

'''TODO REMOVE?
def update_last_login(conn: sqlite3.Connection, user_id: int) -> None:
    """
    Aggiorna last_login_at al timestamp corrente.
    """
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE users
        SET last_login_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (user_id,),
    )
    conn.commit()'''

# =========================
# FAVOURITES
# =========================

def add_favourite(
    conn: sqlite3.Connection,
    user_id: int,
    label: str,
    latitude: float,
    longitude: float,
) -> int:
    """
    Aggiunge un luogo preferito per l'utente.
    Lancia sqlite3.IntegrityError se lo stesso user ha già quel label.
    """
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO favourites (user_id, label, latitude, longitude)
        VALUES (?, ?, ?, ?)
        """,
        (user_id, label.strip(), latitude, longitude),
    )
    conn.commit()
    return cursor.lastrowid


def get_user_favourites(conn: sqlite3.Connection, user_id: int) -> list[sqlite3.Row]:
    """
    Ritorna tutti i preferiti di un utente ordinati per label.
    """
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT *
        FROM favourites
        WHERE user_id = ?
        ORDER BY label COLLATE NOCASE ASC
        """,
        (user_id,),
    )
    return cursor.fetchall()


'''
def get_favourite_by_label(
    conn: sqlite3.Connection,
    user_id: int,
    label: str,
) -> Optional[sqlite3.Row]:
    """
    Ritorna un preferito dato user_id + label, oppure None.
    TODO puo tornare utile per farlo cercare a un user per label
    invece che scegliere dalla lista, ma non è usato al momento.
    """
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT *
        FROM favourites
        WHERE user_id = ? AND label = ?
        """,
        (user_id, label.strip()),
    )
    return cursor.fetchone()'''


def delete_favourite(conn: sqlite3.Connection, user_id: int, label: str) -> bool:
    """
    Elimina un preferito solo se appartiene all'utente.
    Ritorna True se ha eliminato una riga, altrimenti False.
    TODO al momento non usato
    """
    cursor = conn.cursor()
    cursor.execute(
        """
        DELETE FROM favourites
        WHERE label = ? AND user_id = ?
        """,
        (label, user_id),
    )
    conn.commit()
    return cursor.rowcount > 0


def update_favourite(
    conn: sqlite3.Connection,
    user_id: int,
    old_label: str,
    new_label: str,
    latitude: float,
    longitude: float
) -> bool:
    """
    Aggiorna un preferito solo se appartiene all'utente.
    Ritorna True se ha modificato una riga, altrimenti False.
    """
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE favourites
        SET label = ?, latitude = ?, longitude = ?
        WHERE label = ? AND user_id = ?
        """,
        (new_label.strip(), latitude, longitude, old_label, user_id), #TODO testala non sono sicuro
    )
    conn.commit()
    return cursor.rowcount > 0


# =========================
# HELPERS
# =========================

def row_to_dict(row: Optional[sqlite3.Row]) -> Optional[dict]:
    """
    Converte una singola Row in dict.
    """
    if row is None:
        return None
    return dict(row)


def rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict]:
    """
    Converte una lista di Row in lista di dict.
    """
    return [dict(r) for r in rows]