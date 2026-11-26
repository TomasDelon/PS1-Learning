# Carte PS1 et suivi local

## Ouvrir le parcours

Extraire le dossier complet, puis lancer depuis sa racine, par exemple dans le
terminal RStudio :

```sh
python3 tools/serve.py
```

Ouvrir `http://127.0.0.1:8765/app/`. Arrêter le serveur avec Ctrl+C. Si le port
est occupé, utiliser `python3 tools/serve.py --port 8766`. Python 3 suffit pour
ce tableau de bord. Mermaid et sa licence sont inclus localement; Node et les
outils de développement ne sont pas nécessaires pour l’utiliser.

Le tableau de bord relie **23 activités, 46 Rmd et 1200 minutes**. Les exercices
restent dans RStudio. Ouvrir le fichier Travail, sélectionner Visual, écrire
et exécuter les chunks. Le format `html_notebook` permet les résultats dans
l’éditeur; le corrigé se consulte dans son propre Rmd.

## Naviguer et choisir une activité

Le graphe est rendu par le moteur Mermaid local. Filtrer par module, cliquer
sur une étape ou utiliser « Accès direct ». Les repères montrent l’étape
ouverte, la suite proposée, les signalements à reprendre et le budget restant
selon les minutes déclarées. Choisir la suite ouvre ses détails sans démarrer
une séance, sans chronométrer et sans changer le suivi.

Les relations ont trois sens différents :

- **Prérequis pédagogiques** : une dépendance utile pour travailler l’activité.
- **Ordre de travail** : l’ordre proposé des 23 activités dans les 20 heures.
- **Catégorie et familles comprises** : le choix général d’un test comprend
  plusieurs familles. Une flèche pointillée va de la catégorie vers les
  activités qui développent ses familles. Elle n’ajoute aucun prérequis.

Cette dernière vue rend explicites cinq relations de thèmes requalifiées dans
`sequence/dependency_decisions.json`. La base historique reste inchangée.
« Source Mermaid » exporte la vue actuelle; `parcours.mmd` donne la carte des
prérequis sans suivi personnel.

Le sélecteur « Mode de travail » distingue cours/exercices et rappel/transfert.
Le rappel invite à choisir une variante non consultée selon une erreur réelle.
Cette variante remplace un créneau existant. Le sélecteur ne modifie aucun Rmd
et ne crée aucun résultat d’apprentissage.

Les liens Travail existent pour les 23 activités. Un lien de corrigé s’active
seulement après une action délibérée confirmant la conservation de la première
tentative. Le navigateur ne précharge ni ne prévisualise la correction. S01
propose uniquement son protocole et son audit, jamais une épreuve ou ses réponses.

## Avancement et compétence

**Parcours travaillé** compte les étapes déclarées « Parcourue ». Ce statut
ne valide aucune compétence. « À revoir » conserve un besoin de reprise visible.

**Compétences TP / blanc démontrées** concerne les 84 compétences du catalogue
hérité. La théorie CTD a aussi ses critères dans les leçons. L’affichage s’appuie
sur des preuves déclarées après vérification; il ne corrige pas les mathématiques.
Le seuil exige deux exercices distincts corrects sans aide, dont un transfert,
et un rappel différé mélangé à d’autres notions après une première preuve. Une
nouvelle réponse incorrecte remet le point à revoir. Ces critères ne garantissent
ni une note ni la maîtrise universelle d’un sujet.

Les « Premières applications » indiquent une introduction ciblée. Les
« Compétences à vérifier ici » indiquent où les prérequis du catalogue sont
réunis pour une vérification plus complète. Aucun crédit ne se transmet
automatiquement aux prérequis. Lire un corrigé ou réussir une carte Anki ne
remplace pas une application indépendante.

## Enregistrer et réviser par lots

Le chargement initial ne crée aucun suivi dans le navigateur. « Enregistrer
l’étape » et « Ajouter cette preuve » enregistrent une action explicite en
local. Les formulaires de compétences sont facultatifs. Il n’est pas nécessaire
de remplir 84 formulaires pour étudier.

Pour une révision par lots : conserver les Rmd et images des premières
réponses, exporter le JSON du suivi, puis fournir ces éléments lors d’une
demande de révision. Un fichier révisé peut être importé après validation et
confirmation de remplacement. Le tableau de bord ne synchronise pas les
fichiers, ne transmet rien à ChatGPT et ne surveille pas RStudio.

La démonstration utilise un état synthétique distinct, désactive les écritures
et exporte sous `PS1_suivi_DEMO.json`. Elle ne remplace pas le suivi personnel.
Le fichier `data/progress.example.json`, s’il est présent, est un exemple et
non un historique d’étudiant.

L’import refuse les versions incompatibles, IDs inconnus, états invalides,
doublons de preuve, affirmations sans critères et dates incohérentes. Les dates
ISO doivent avoir un fuseau explicite. Un léger décalage d’horloge de 60 secondes
est toléré; aucun enregistrement ne peut être postérieur à son conteneur.
L’effacement demandé par l’utilisateur ne supprime que la clé locale de cette
version de PS1. Les Rmd, images, exports et autres données du navigateur restent
indépendants de ce suivi.

## Validation et limites

Les tests utilisent un navigateur jetable et des fixtures synthétiques. Leurs
résultats sont dans `reports/graph_browser_results.json` et
`reports/integration_validation.json`. La validation native RStudio est un
reçu distinct. Le temps est déclaré, pas mesuré automatiquement. L’export JSON
permet de garder une copie si le navigateur ou son stockage change.

L’application n’inclut aucun contenu d’épreuve réservée. La situation de
récupération des sources du projet, y compris tout incident de préflight, est
consignée séparément dans le manifeste et les rapports d’audit; l’absence de
fichier d’épreuve dans le livrable n’est pas assimilée à un certificat de zéro
récupération pour toutes les opérations de la session.
