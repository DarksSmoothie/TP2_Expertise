import sqlite3
from contextlib import closing

import pytest
import base
from app import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(base, "BASE", tmp_path / "test.db")
    app.config.update(TESTING=True)
    return app.test_client()


def test_accueil(client):
    assert client.get("/").status_code == 200


def test_gestion_salles(client):
    assert client.post("/salles", data={"nom": "S3", "capacite": "30", "projecteur": "on"}).status_code == 302
    assert client.post("/salles/3/modifier", data={"nom": "Amphi", "capacite": "40"}).status_code == 302
    with base.ouvrir_base() as conn:
        salle = conn.execute("SELECT * FROM salles WHERE id = 3").fetchone()
        assert (salle["nom"], salle["capacite"], salle["projecteur"]) == ("Amphi", 40, 0)
    assert client.post("/salles/1/supprimer").status_code == 302
    with base.ouvrir_base() as conn:
        assert conn.execute("SELECT COUNT(*) FROM reservations WHERE salle_id = 1").fetchone()[0] == 0


@pytest.mark.parametrize("data", [{"nom": " ", "capacite": "3"}, {"nom": "S", "capacite": "0"}, {"nom": "S", "capacite": "abc"}, {}])
def test_salle_invalide(client, data):
    assert client.post("/salles", data=data).status_code == 400


def test_reduction_capacite_refusee(client):
    assert client.post("/salles/1/modifier", data={"nom": "S1", "capacite": "10"}).status_code == 400


def test_salle_absente(client):
    assert client.post("/salles/999/supprimer").status_code == 404
    assert client.post("/salles/999/modifier", data={"nom": "X", "capacite": "10"}).status_code == 404


def reservation(**changements):
    return dict(salle_id="1", personne="Bob", date="2026-11-09", debut="12:00", fin="13:00", participants="20") | changements


@pytest.mark.parametrize("changements", [
    {"debut": "11:00", "fin": "13:00"},
    {"debut": "09:00", "fin": "11:00"},
    {"debut": "09:00", "fin": "13:00"},
    {"debut": "10:30", "fin": "11:00"},
    {"participants": "25"}, {"participants": "0"},
    {"debut": "07:30", "fin": "09:00"},
    {"debut": "19:30", "fin": "20:30"},
    {"debut": "14:00", "fin": "14:20"},
    {"date": "2026-11-10", "debut": "08:00", "fin": "13:00"},
    {"debut": "14:00", "fin": "13:00"},
    {"date": "invalide"}, {"debut": "invalide"}, {"personne": " "},
])
def test_reservation_refusee(client, changements):
    assert client.post("/reservations", data=reservation(**changements)).status_code == 400
    with base.ouvrir_base() as conn:
        assert conn.execute("SELECT COUNT(*) FROM reservations").fetchone()[0] == 1


@pytest.mark.parametrize("changements", [
    {}, {"debut": "09:30", "fin": "10:00"},
    {"date": "2026-11-10", "debut": "08:00", "fin": "12:00"},
    {"salle_id": "2", "debut": "10:00", "fin": "12:00", "participants": "8"},
    {"debut": "19:30", "fin": "20:00"},
])
def test_reservation_acceptee(client, changements):
    assert client.post("/reservations", data=reservation(**changements)).status_code == 302
    with base.ouvrir_base() as conn:
        assert conn.execute("SELECT COUNT(*) FROM reservations").fetchone()[0] == 2


def test_annulation(client):
    assert client.post("/reservations/1/annuler").status_code == 302
    assert client.post("/reservations/1/annuler").status_code == 404
    assert client.post("/reservations", data=reservation(debut="10:00", fin="12:00")).status_code == 302


def test_reservation_salle_absente(client):
    assert client.post("/reservations", data=reservation(salle_id="999")).status_code == 404


def test_planning_semaine_et_salle(client):
    for jour, personne in [("2026-11-08", "Avant"), ("2026-11-15", "Dimanche"), ("2026-11-16", "Apres")]:
        assert client.post("/reservations", data=reservation(date=jour, personne=personne)).status_code == 302
    client.post("/reservations", data=reservation(salle_id="2", participants="8", personne="Autre salle"))
    page = client.get("/?salle_id=1&semaine=2026-11-11").get_data(as_text=True)
    assert "du 09/11/2026 au 15/11/2026" in page
    assert "Alice" in page and "Dimanche —" in page
    assert "Avant —" not in page and "Apres —" not in page and "Autre salle —" not in page
    assert "Semaine précédente" in page and "Semaine suivante" in page
    assert "Libre" in page


def test_planning_invalide(client):
    assert client.get("/?semaine=incorrecte").status_code == 400
    assert client.get("/?salle_id=999").status_code == 404
    assert client.get("/?salle_id=abc").status_code == 400


def test_aucune_salle(client):
    client.post("/salles/1/supprimer")
    client.post("/salles/2/supprimer")
    page = client.get("/")
    assert page.status_code == 200
    assert "Aucune salle à afficher" in page.get_data(as_text=True)


def test_echappement_html(client):
    client.post("/reservations", data=reservation(personne="<script>alert(1)</script>"))
    page = client.get("/?semaine=2026-11-09").get_data(as_text=True)
    assert "<script>alert(1)</script>" not in page
    assert "&lt;script&gt;" in page


@pytest.mark.parametrize("personne", ["Alice", " alice ", "ALICE"])
def test_conflit_personne_autre_salle(client, personne):
    reponse = client.post("/reservations", data=reservation(
        salle_id="2", personne=personne, debut="11:00", fin="13:00", participants="8"))
    assert reponse.status_code == 400
    assert "Cette personne" in reponse.get_data(as_text=True)
    with base.ouvrir_base() as conn:
        assert conn.execute("SELECT COUNT(*) FROM reservations").fetchone()[0] == 1


@pytest.mark.parametrize("changements", [
    {"debut": "12:00", "fin": "13:00"},
    {"debut": "09:00", "fin": "10:00"},
    {"date": "2026-11-10", "debut": "10:00", "fin": "12:00"},
    {"personne": "Bob", "debut": "10:00", "fin": "12:00"},
])
def test_personne_creneaux_autorises(client, changements):
    donnees = reservation(salle_id="2", personne="Alice", participants="8") | changements
    assert client.post("/reservations", data=donnees).status_code == 302


def test_personne_espaces_internes(client):
    assert client.post("/reservations", data=reservation(personne="Jean Dupont")).status_code == 302
    assert client.post("/reservations", data=reservation(
        salle_id="2", personne=" jean   DUPONT ", participants="8")).status_code == 400


def test_type_local_creation_modification(client):
    assert client.post("/salles", data={
        "nom": "Labo", "capacite": "12", "type_local": " Laboratoire "}).status_code == 302
    with closing(base.ouvrir_base()) as conn:
        assert conn.execute("SELECT type_local FROM salles WHERE id = 3").fetchone()[0] == "Laboratoire"
    assert "Laboratoire" in client.get("/").get_data(as_text=True)
    assert client.post("/salles/3/modifier", data={
        "nom": "Labo", "capacite": "15", "type_local": "Informatique"}).status_code == 302
    with closing(base.ouvrir_base()) as conn:
        assert conn.execute("SELECT type_local FROM salles WHERE id = 3").fetchone()[0] == "Informatique"
    assert "Informatique" in client.get("/?salle_id=3").get_data(as_text=True)


@pytest.mark.parametrize("url", ["/salles", "/salles/1/modifier"])
def test_type_local_vide_refuse(client, url):
    assert client.post(url, data={"nom": "S1", "capacite": "20", "type_local": " "}).status_code == 400


def test_migration_type_local_conserve_donnees(tmp_path, monkeypatch):
    chemin = tmp_path / "ancienne.db"
    schema = (base.RACINE / "base.sql").read_text(encoding="utf-8")
    schema = schema.replace("    type_local TEXT NOT NULL DEFAULT 'Salle',\n", "")
    with closing(sqlite3.connect(chemin)) as conn:
        conn.executescript(schema)
    monkeypatch.setattr(base, "BASE", chemin)
    for _ in range(2):
        with closing(base.ouvrir_base()) as conn:
            assert conn.execute("SELECT nom, type_local FROM salles WHERE id = 1").fetchone()[:] == ("S1", "Salle")
            assert conn.execute("SELECT personne FROM reservations WHERE id = 1").fetchone()[0] == "Alice"


def test_reservations_hebdomadaires(client):
    assert client.post("/reservations", data=reservation(
        date="2026-12-28", nombre_semaines="3")).status_code == 302
    with closing(base.ouvrir_base()) as conn:
        lignes = conn.execute("SELECT * FROM reservations WHERE personne = 'Bob' ORDER BY date").fetchall()
        assert [r["date"] for r in lignes] == ["2026-12-28", "2027-01-04", "2027-01-11"]
        assert all((r["salle_id"], r["debut"], r["fin"], r["participants"]) ==
                   (1, "12:00", "13:00", 20) for r in lignes)
    assert "Bob —" in client.get("/?salle_id=1&semaine=2027-01-04").get_data(as_text=True)
    assert client.post(f"/reservations/{lignes[1]['id']}/annuler").status_code == 302
    with closing(base.ouvrir_base()) as conn:
        assert conn.execute("SELECT COUNT(*) FROM reservations WHERE personne = 'Bob'").fetchone()[0] == 2


@pytest.mark.parametrize("salle_id,personne", [("1", "Autre"), ("2", "Bob")])
def test_repetition_conflit_ulterieur_annule_tout(client, salle_id, personne):
    assert client.post("/reservations", data=reservation(
        salle_id=salle_id, personne=personne, participants="8", date="2026-11-23")).status_code == 302
    reponse = client.post("/reservations", data=reservation(nombre_semaines="3"))
    assert reponse.status_code == 400
    assert "2026-11-23" in reponse.get_data(as_text=True)
    with closing(base.ouvrir_base()) as conn:
        assert conn.execute("SELECT COUNT(*) FROM reservations").fetchone()[0] == 2
        assert conn.execute("SELECT COUNT(*) FROM reservations WHERE date = '2026-11-16'").fetchone()[0] == 0


@pytest.mark.parametrize("nombre", ["0", "-1", "", "abc", "1.5", "999999999999999999999"])
def test_nombre_semaines_invalide(client, nombre):
    assert client.post("/reservations", data=reservation(nombre_semaines=nombre)).status_code == 400
    with closing(base.ouvrir_base()) as conn:
        assert conn.execute("SELECT COUNT(*) FROM reservations").fetchone()[0] == 1


def test_repetition_date_hors_limites(client):
    assert client.post("/reservations", data=reservation(
        date="9999-12-31", nombre_semaines="2")).status_code == 400


def test_repetition_creneaux_adjacents(client):
    assert client.post("/reservations", data=reservation(
        personne="Alice", nombre_semaines="3")).status_code == 302
    assert client.post("/reservations", data=reservation(
        personne="Alice", salle_id="2", participants="8",
        debut="13:00", fin="14:00", nombre_semaines="3")).status_code == 302
