def entier_positif(valeur, champ):
    try:
        nombre = int(valeur)
    except (ValueError, TypeError):
        raise ValueError(f"{champ} doit être un entier positif.") from None
    if nombre < 1:
        raise ValueError(f"{champ} doit être un entier positif.")
    return nombre


def valider_salle(nom, capacite):
    nom = nom.strip()
    if not nom:
        raise ValueError("Le nom de la salle est obligatoire.")
    return nom, entier_positif(capacite, "La capacité")


def valider_type_local(type_local):
    type_local = type_local.strip()
    if not type_local:
        raise ValueError("Le type de local est obligatoire.")
    return type_local


def dates_hebdomadaires(jour, nombre_semaines):
    from datetime import date, timedelta

    nombre = entier_positif(nombre_semaines, "Le nombre de semaines")
    try:
        premier_jour = date.fromisoformat(jour)
        # Vérifier la dernière date avant de construire la série.
        premier_jour + timedelta(weeks=nombre - 1)
    except (ValueError, TypeError, OverflowError):
        raise ValueError("La date ou le nombre de semaines est invalide.") from None
    return [(premier_jour + timedelta(weeks=i)).isoformat() for i in range(nombre)]


def cle_personne(personne):
    return " ".join(personne.split()).casefold()


def valider_reservation(personne, jour, debut, fin, participants, capacite, reservations,
                       reservations_personne=()):
    from datetime import date, datetime

    personne = personne.strip()
    if not personne:
        raise ValueError("Le nom de la personne est obligatoire.")
    try:
        jour = date.fromisoformat(jour).isoformat()
        debut_dt = datetime.strptime(debut, "%H:%M")
        fin_dt = datetime.strptime(fin, "%H:%M")
    except (ValueError, TypeError):
        raise ValueError("La date ou les heures sont invalides.") from None
    debut = debut_dt.strftime("%H:%M")
    fin = fin_dt.strftime("%H:%M")
    if debut < "08:00" or fin > "20:00":
        raise ValueError("La réservation doit avoir lieu entre 8 h et 20 h.")
    duree = (fin_dt - debut_dt).total_seconds() / 60
    if not 30 <= duree <= 240:
        raise ValueError("La durée doit être comprise entre 30 minutes et 4 heures.")
    participants = entier_positif(participants, "Le nombre de participants")
    if participants > capacite:
        raise ValueError("Le nombre de participants dépasse la capacité de la salle.")
    if any(r["date"] == jour and debut < r["fin"] and fin > r["debut"] for r in reservations):
        raise ValueError("Ce créneau chevauche une réservation existante.")
    if any(cle_personne(r["personne"]) == cle_personne(personne)
           and r["date"] == jour and debut < r["fin"] and fin > r["debut"]
           for r in reservations_personne):
        raise ValueError("Cette personne a déjà une réservation sur ce créneau.")
    return personne, jour, debut, fin, participants


def valider_capacite_existante(capacite, maximum_participants):
    if maximum_participants and maximum_participants > capacite:
        raise ValueError("La capacité serait insuffisante pour une réservation existante.")
