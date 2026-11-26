# Mémorisation et feuille A4 dans les 20 heures

Version 2.0.0. Ces choix organisent le travail; ils ne constituent aucun résultat d’apprentissage déjà observé.

## Retenir, reconstruire ou consulter

Mémoriser ce qui permet de choisir et de contrôler un raisonnement. Consulter ce qui est peu fréquent, chargé en symboles ou facile à confondre. L’A4 réduit le temps de recherche; elle conserve les hypothèses, les paramètres et le sens des formules.

Le programme PS1 prévoit une feuille A4 manuscrite. Le registre distingue cette source du nombre de faces autorisé rapporté par l’étudiant. Le programme exact de PS2 n’a pas été vérifié : les fondements sélectionnés sont utiles pour la suite, sans constituer une liste officielle d’exigences de PS2.

Sources : [manifeste](../sources/source_manifest.json), [programme de travail](PS1_Roadmap_20h_v2.md), [soutiens](../sources/soutien_mapping.json).

| Traitement | Contenu | Vérification |
|:--|:--|:--|
| Comprendre et rappeler | Conditionnement; espérance, variance, covariance, corrélation; paramètre, estimateur, estimation; p-valeur et couverture | Définir les objets et distinguer deux situations nouvelles |
| Retenir et reconstruire | Linéarité, transformation affine, variance d’une moyenne, standardisation, décomposition de l’EQM | Adapter signes, unités ou hypothèses et justifier les étapes |
| Exécuter avec une référence | Pivots, IC, choix d’un test, vraisemblance, MCO, bootstrap | Choisir sans que la question nomme la méthode; vérifier le plan et interpréter |
| Consulter au besoin | Paramétrages, lois moins fréquentes, variantes d’inférence, arguments R occasionnels | Trouver la référence, vérifier les conventions et tester une intuition |

Une identité importante peut aussi figurer sur l’A4. La consultation de secours ne supprime pas l’objectif de rappel. Les démonstrations longues se travaillent par leur structure et par des exercices, pas comme un unique verso à réciter.

## Priorités

| Domaine | À rappeler | À consulter selon les besoins |
|:--|:--|:--|
| Probabilités et moments | Conditionnement; intégrabilité; relations entre moments; indépendance et covariance | Supports, moments et paramétrages des lois |
| Échantillonnage et simulation | Objet qui converge; fluctuations; rôle de la racine de n; cible Monte-Carlo | Pivots, précision et conditions de validité |
| Estimation et tests | Fixe ou aléatoire; biais, variance, EQM; couverture; p-valeur; alternative | IC et statistiques par famille, avec degrés de liberté |
| Couples et régression | Marginale ou conditionnelle; variance totale; effet partiel; association et causalité | Équations de covariance, RSS/TSS/R² et inférence |
| R | Lire, filtrer, écrire une fonction, inspecter une sortie, chercher l’aide | Arguments : sd, lower.tail, alternative, paired, var.equal, référence du facteur |
| Rédaction | Objet, hypothèses, propriété, résultat, portée | Amorces de phrases avec champs à adapter |

## Construire et tester l’A4

À la correction d’une leçon, noter au plus un besoin réel de consultation. A4 dure 60 minutes : 10 de sélection, 40 d’écriture manuscrite, 10 de recherches chronométrées. F01 réserve dix minutes supplémentaires à sa révision, comprises dans ses 90 minutes.

Le test porte sur la recherche d’une condition, d’un paramètre ou d’un argument. Si la formule se trouve difficilement ou si ses hypothèses manquent, réorganiser la feuille. La banque de l’activité A4 n’a pas vocation à être recopiée intégralement.

## Cartes Anki livrées

Les 174 blocs pédagogiques possèdent des identifiants et sont extractibles. Parmi eux, 71 sont sélectionnés pour la mémoire dans [selection.json](../anki/build/selection.json). Les exemples, tentatives et corrigés d’exercices ne deviennent pas automatiquement des cartes.

Une DEF conserve ses objets et conditions. Un THM conserve hypothèses et conclusion. Une MTH précise quand appliquer la procédure et quoi vérifier. Une SYX indique ce que calcule R et les arguments qui changent son sens. Les cartes restent fidèles au bloc canonique, avec une présentation minimale.

Revoir le sous-paquet de la leçon dans le temps prévu. Aucun import personnel ni résultat de rappel n’a été créé pendant la construction. Voir [le guide Anki](../anki/README.md) pour la génération et les vérifications.

## Appliquer après le rappel

Une tâche nouvelle doit vérifier l’emploi d’une définition ou d’une identité rappelée. Une erreur peut venir d’une hypothèse, d’une unité ou d’une interprétation, pas seulement d’un manque de récitation.

Les six créneaux adaptatifs et les réparations de F01 permettent ce retour. Les tâches qui dépassent la capacité prévue restent signalées. Une compétence ne devient pas acquise parce que la carte a été lue ou que la correction semble claire.
