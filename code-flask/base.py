import sqlite3
from pathlib import Path

RACINE = Path(__file__).parent.parent
BASE = RACINE / "data.db"


def ouvrir_base():
    """Ouvre la base et ajoute les nouvelles colonnes sans perdre les données."""
    neuve = not BASE.exists()
    conn = sqlite3.connect(BASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    if neuve:
        conn.executescript((RACINE / "base.sql").read_text(encoding="utf-8"))
    # Compatibilité avec les bases créées avant l'ajout du type de local.
    try:
        with conn:
            conn.execute("BEGIN IMMEDIATE")
            colonnes = {colonne["name"] for colonne in conn.execute("PRAGMA table_info(salles)")}
            if "type_local" not in colonnes:
                conn.execute("ALTER TABLE salles ADD COLUMN type_local TEXT NOT NULL DEFAULT 'Salle'")
    except Exception:
        conn.close()
        raise
    return conn
