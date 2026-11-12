# Réservation de salles

## Le projet
Permettre au personnel d'un bâtiment universitaire de réserver lui-même une salle, sans conflit et dans la limite de sa capacité.

## Technologies
Python, SQLite, pytest. Framework : Flask (`code-flask`) ou Streamlit (`code-streamlit`).

## Commandes
- Lancer l'application : `python app.py` dans `code-flask`, `streamlit run app.py` dans `code-streamlit`
- Lancer les tests : `pytest` dans le dossier de code

## Base de données
Tables et exemples dans `base.sql`. `data.db` se crée au premier lancement. L'ajout de `type_local` est migré automatiquement dans `base.py`, sans effacer les données.

## Règles métier
- Deux réservations d'une même salle ne se chevauchent pas. Finir à 12 h et commencer à 12 h est autorisé.
- Une personne ne peut pas avoir de réservations qui se chevauchent, même dans des salles différentes. Comparer les noms sans tenir compte de la casse ni des espaces superflus.
- Chaque salle a un type de local en texte libre, non vide.
- Les réservations peuvent être répétées chaque semaine : le nombre de semaines inclut la première occurrence. Un conflit annule la création de toute la série. L'annulation supprime uniquement l'occurrence choisie.
- Le nombre de participants ne dépasse pas la capacité de la salle.
- Une réservation a lieu entre 8 h et 20 h et dure de 30 min à 4 h.
- Supprimer une salle supprime ses réservations.
- Il n'y a pas d'authentification. La semaine va du lundi au dimanche.

## Façon de travailler
- Une fonctionnalité à la fois.
- Ajouter ou mettre à jour les tests à chaque fonctionnalité, puis lancer `pytest`.
- Ne pas ajouter d'autre dépendance sans le demander.
- Ne faire `git push` que si le binôme le demande.
- Ne rien ajouter qui n'est pas demandé.
- Mettre les règles dans un fichier `regles.py`, sans framework.
- Utiliser une base séparée pour les tests.

