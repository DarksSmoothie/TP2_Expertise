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
