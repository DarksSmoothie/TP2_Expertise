---
name: commit-push
description: Vérifie le travail, écrit un message de commit clair, puis pousse sur GitHub. À utiliser quand on demande de faire un commit ou de pousser.
---

1. Regarde `git status` et `git diff`. Si un fichier ne doit pas partir (mot de passe, `data.db`, `.venv`), arrête-toi et préviens.
2. Lance `pytest` dans le dossier de code. Si un test échoue, arrête-toi et donne le résultat.
3. Fais `git add -A`, puis un commit avec un message en français qui commence par un verbe et dit ce qui change. Exemple : « Ajoute l'annulation d'une réservation ».
4. Si la branche existe déjà sur GitHub, fais `git pull --no-rebase --no-edit`. En cas de conflit, arrête-toi et liste les fichiers, sans rien résoudre seul.
5. Fais `git push`, avec `-u origin <branche>` si la branche est nouvelle, puis donne le message du commit et le résultat.
