from datetime import date, timedelta
from contextlib import closing
from flask import Flask, redirect, render_template, request
from base import ouvrir_base
from regles import valider_salle, valider_reservation, entier_positif, valider_capacite_existante

app = Flask(__name__)


@app.errorhandler(ValueError)
def erreur_validation(erreur):
    return render_template("erreur.html", message=str(erreur)), 400


@app.get("/")
def accueil():
    with closing(ouvrir_base()) as conn:
        salles = conn.execute("SELECT * FROM salles ORDER BY nom, id").fetchall()
        selection = request.args.get("salle_id")
        salle_id = entier_positif(selection, "La salle") if selection else (salles[0]["id"] if salles else None)
        salle = next((s for s in salles if s["id"] == salle_id), None)
        if salle_id is not None and salle is None:
            return "Salle introuvable", 404
        try:
            jour = date.fromisoformat(request.args.get("semaine", date.today().isoformat()))
        except ValueError:
            raise ValueError("La date de la semaine est invalide.") from None
        lundi = jour - timedelta(days=jour.weekday())
        jours = [lundi + timedelta(days=i) for i in range(7)]
        reservations = conn.execute(
            "SELECT * FROM reservations WHERE salle_id = ? AND date BETWEEN ? AND ? ORDER BY date, debut",
            (salle_id, lundi.isoformat(), jours[-1].isoformat())).fetchall()
    return render_template("index.html", salles=salles, salle_selectionnee=salle,
                           jours=jours, reservations=reservations, lundi=lundi,
                           precedente=lundi - timedelta(days=7), suivante=lundi + timedelta(days=7))


@app.post("/salles")
def ajouter_salle():
    nom, capacite = valider_salle(request.form.get("nom", ""), request.form.get("capacite"))
    with closing(ouvrir_base()) as conn, conn:
        conn.execute("INSERT INTO salles (nom, capacite, projecteur) VALUES (?, ?, ?)",
                     (nom, capacite, int("projecteur" in request.form)))
    return redirect("/")


@app.post("/salles/<int:salle_id>/modifier")
def modifier_salle(salle_id):
    nom, capacite = valider_salle(request.form.get("nom", ""), request.form.get("capacite"))
    with closing(ouvrir_base()) as conn, conn:
        salle = conn.execute("SELECT * FROM salles WHERE id = ?", (salle_id,)).fetchone()
        if salle is None:
            return "Salle introuvable", 404
        maximum = conn.execute("SELECT MAX(participants) FROM reservations WHERE salle_id = ?", (salle_id,)).fetchone()[0]
        if maximum and maximum > capacite:
            raise ValueError("La capacité serait insuffisante pour une réservation existante.")
        conn.execute("UPDATE salles SET nom = ?, capacite = ?, projecteur = ? WHERE id = ?",
                     (nom, capacite, int("projecteur" in request.form), salle_id))
    return redirect("/")


@app.post("/salles/<int:salle_id>/supprimer")
def supprimer_salle(salle_id):
    with closing(ouvrir_base()) as conn, conn:
        if conn.execute("DELETE FROM salles WHERE id = ?", (salle_id,)).rowcount == 0:
            return "Salle introuvable", 404
    return redirect("/")


@app.post("/reservations")
def reserver_salle():
    salle_id = entier_positif(request.form.get("salle_id"), "La salle")
    with closing(ouvrir_base()) as conn, conn:
        # Verrouiller avant la lecture empêche deux demandes simultanées de se croiser.
        conn.execute("BEGIN IMMEDIATE")
        salle = conn.execute("SELECT * FROM salles WHERE id = ?", (salle_id,)).fetchone()
        if salle is None:
            return "Salle introuvable", 404
        reservations = conn.execute("SELECT * FROM reservations WHERE salle_id = ?", (salle_id,)).fetchall()
        valeurs = valider_reservation(
            request.form.get("personne", ""), request.form.get("date", ""),
            request.form.get("debut", ""), request.form.get("fin", ""),
            request.form.get("participants"), salle["capacite"], reservations)
        conn.execute("INSERT INTO reservations (salle_id, personne, date, debut, fin, participants) VALUES (?, ?, ?, ?, ?, ?)",
                     (salle_id, *valeurs))
    return redirect("/")


@app.post("/reservations/<int:reservation_id>/annuler")
def annuler_reservation(reservation_id):
    with closing(ouvrir_base()) as conn, conn:
        if conn.execute("DELETE FROM reservations WHERE id = ?", (reservation_id,)).rowcount == 0:
            return "Réservation introuvable", 404
    return redirect("/")


if __name__ == "__main__":
    app.run(debug=True)
