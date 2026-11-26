# PS1 · Parcours de probabilités et statistique (20 h)

Parcours pédagogique indépendant en français. 17 leçons, 23 activités, documents Travail et Corrigé séparés, 71 cartes Anki et contrôles ciblés. Les supports universitaires originaux ne sont pas redistribués. Les références restent indicatives; ce dépôt n'est pas un corrigé officiel.

## Démarrer

Ouvrir `PS1.Rproj` dans RStudio, puis saisir dans la console :

```r
source("v21/coach.R")
ps1_demarrer()
```

Utiliser l'éditeur **Visual**. Importer une fois `anki/deck/deck.apkg` dans Anki. Ne pas réviser tout le paquet avant D00.

## Une activité

1. Répondre dans le fichier ouvert, avec ses images locales et le code R. Indiquer la confiance et l'aide éventuelle.
2. Enregistrer (`Ctrl+S`), puis `ps1_corriger()` dans la console. La première tentative est figée; le corrigé s'ouvre dans un autre onglet.
3. Annoter l'autocorrection dans Travail, enregistrer, puis `ps1_terminer(60)` (remplacer 60 par la durée réelle en minutes).
4. Dans le terminal du projet, vérifier et publier uniquement les fichiers voulus :

```sh
git status --short
git add progress/
git diff --cached --stat
git commit -m "D00 : tentative et autocorrection"
git push
```

5. Demander explicitement la revue au tuteur, en donnant le dépôt et le commit. Le tuteur doit lire la première tentative, l'autocorrection et les preuves; aucun jugement automatique à partir d'un push. Après une revue validée et enregistrée, synchroniser avec `git pull --ff-only`, puis relancer `ps1_demarrer()`.

## Important : dépôt public

Les réponses, erreurs, durées, images et toute donnée ajoutée à `progress/` deviennent accessibles à tous dès le push. Vérifier le contenu avant chaque publication. Ne pas y placer de nom, adresse, donnée personnelle, sujet d'examen, PDF de cours ou corrigé officiel. Les métadonnées des photos peuvent aussi révéler des informations. La suppression ultérieure ne retire pas nécessairement les anciennes copies de l'historique Git.

Le sujet réservé et les réponses à cette épreuve sont conservés hors dépôt, dans un dossier privé. Dans S01, ne conserver que le bilan de procédure et des constats génériques sans reproduire le sujet ni sa correction. Les originaux du parcours dans `lessons/` ne sont pas les copies personnelles; ces dernières sont générées dans `progress/`. Le clone doit être neuf (pas de migration automatique d'une session 2.1 antérieure). Ne pas mélanger les modifications d'une même session sur deux appareils; effectuer un pull avant de reprendre.

## Suivi et revue

`ps1_tableau()` ouvre le tableau Rmd. Pour le graphe optionnel, lancer `python3 tools/serve.py` depuis la racine, puis ouvrir http://127.0.0.1:8765/app/. Importer `progress/graph_progress.json` dans une vue vierge après revue. Le graphe ne remplace pas l'éditeur Visual.

Le tuteur complète le modèle JSON de revue indiqué par `ps1_terminer()`, puis exécute depuis la racine `python3 v21/coach.py review <fichier_de_revue.json>`. Cette validation est nécessaire avant la génération de la prochaine leçon. Voir `v21/REVUE.md` pour les critères et les preuves. Une revue avec GitHub nécessite toujours une invocation du tuteur, et un runtime Python pour la valider. Aucun agent permanent n'est déclenché par GitHub.

Le paquet Anki d'origine est conservé octet pour octet. Les cartes et l'historique Anki personnel sont indépendants du dépôt. Les sources du générateur et les archives d'audit privées restent dans la version complète v2.1, non publiée.

Les 1 200 min incluent D00, la simulation et les reprises. Les sondes supplémentaires utilisent exclusivement la marge libérée par des leçons évaluées. Un point indexé n'est pas une preuve de maîtrise.

## Installation initiale dans GitHub

Lancer `bash tools/publish_public.sh` depuis le dossier extrait pour créer un nouveau dépôt public `PS1-Learning` sur le compte GitHub CLI connecté. Le script ne modifie jamais un dépôt existant; il refuse de réutiliser un historique. Les futures séances utilisent seulement commit, push et pull.
