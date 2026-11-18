import os
import sqlite3
from pathlib import Path


# === CONFIG ===
DB_PATH = Path(os.getenv("DATABASE_PATH", "data/database.db"))


def get_connection(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def create_tables(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()

    # =========================
    # TABella users
    # =========================
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    mobility_problem TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # =========================
    # TABella favourites
    # =========================
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS favourites (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        label TEXT NOT NULL,
        latitude REAL NOT NULL,
        longitude REAL NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

        FOREIGN KEY (user_id) REFERENCES users(id)
            ON DELETE CASCADE
            ON UPDATE CASCADE,

        CONSTRAINT uq_user_label UNIQUE (user_id, label),

        CONSTRAINT chk_latitude CHECK (latitude >= -90 AND latitude <= 90),
        CONSTRAINT chk_longitude CHECK (longitude >= -180 AND longitude <= 180)
    );
    """)

    # =========================
    # INDICI
    # =========================
    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_favourites_user_id
    ON favourites(user_id);
    """)

    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_favourites_coordinates
    ON favourites(latitude, longitude);
    """)

    conn.commit()


def create_triggers(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()

    # aggiorna updated_at su users
    cursor.execute("""
    CREATE TRIGGER IF NOT EXISTS trg_users_updated_at
    AFTER UPDATE ON users
    FOR EACH ROW
    BEGIN
        UPDATE users
        SET updated_at = CURRENT_TIMESTAMP
        WHERE id = NEW.id;
    END;
    """)

    # aggiorna updated_at su favourites
    cursor.execute("""
    CREATE TRIGGER IF NOT EXISTS trg_favourites_updated_at
    AFTER UPDATE ON favourites
    FOR EACH ROW
    BEGIN
        UPDATE favourites
        SET updated_at = CURRENT_TIMESTAMP
        WHERE id = NEW.id;
    END;
    """)

    conn.commit()


def main() -> None:
    # crea la cartella se non esiste
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    with get_connection(DB_PATH) as conn:
        create_tables(conn)
        create_triggers(conn)

    print(f"Database inizializzato correttamente: {DB_PATH}")


if __name__ == "__main__":
    main()