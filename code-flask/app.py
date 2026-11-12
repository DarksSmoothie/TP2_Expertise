from datetime import date, timedelta
from contextlib import closing
from flask import Flask, redirect, render_template, request
from base import ouvrir_base
from regles import (valider_salle, valider_reservation, entier_positif,
                    valider_capacite_existante, valider_type_local, dates_hebdomadaires)

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
    type_local = valider_type_local(request.form.get("type_local", "Salle"))
    with closing(ouvrir_base()) as conn, conn:
        conn.execute("INSERT INTO salles (nom, capacite, projecteur, type_local) VALUES (?, ?, ?, ?)",
                     (nom, capacite, int("projecteur" in request.form), type_local))
    return redirect("/")


@app.post("/salles/<int:salle_id>/modifier")
def modifier_salle(salle_id):
    nom, capacite = valider_salle(request.form.get("nom", ""), request.form.get("capacite"))
    with closing(ouvrir_base()) as conn, conn:
        conn.execute("BEGIN IMMEDIATE")
        salle = conn.execute("SELECT * FROM salles WHERE id = ?", (salle_id,)).fetchone()
        if salle is None:
            return "Salle introuvable", 404
        type_local = valider_type_local(request.form.get("type_local", salle["type_local"]))
        maximum = conn.execute("SELECT MAX(participants) FROM reservations WHERE salle_id = ?", (salle_id,)).fetchone()[0]
        valider_capacite_existante(capacite, maximum)
        conn.execute("UPDATE salles SET nom = ?, capacite = ?, projecteur = ?, type_local = ? WHERE id = ?",
                     (nom, capacite, int("projecteur" in request.form), type_local, salle_id))
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
    jours = dates_hebdomadaires(request.form.get("date", ""), request.form.get("nombre_semaines", "1"))
    with closing(ouvrir_base()) as conn, conn:
        # Verrouiller avant la lecture empêche deux demandes simultanées de se croiser.
        conn.execute("BEGIN IMMEDIATE")
        salle = conn.execute("SELECT * FROM salles WHERE id = ?", (salle_id,)).fetchone()
        if salle is None:
            return "Salle introuvable", 404
        reservations = conn.execute(
            "SELECT * FROM reservations WHERE date BETWEEN ? AND ?", (jours[0], jours[-1])).fetchall()
        reservations_salle = [r for r in reservations if r["salle_id"] == salle_id]
        for jour in jours:
            try:
                valeurs = valider_reservation(
                    request.form.get("personne", ""), jour,
                    request.form.get("debut", ""), request.form.get("fin", ""),
                    request.form.get("participants"), salle["capacite"], reservations_salle, reservations)
            except ValueError as erreur:
                raise ValueError(f"Le {jour} : {erreur}") from None
            # Une seule transaction : un refus annule toutes les occurrences.
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
