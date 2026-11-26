# Revue d'une tentative réelle

Le tuteur lit d'abord `coach_state.json` et le modèle dans `review_queue/`.
Il vérifie le dossier `handoffs/attempt-.../`, notamment les trois instantanés
`first`, `corrected`, `reference`, leurs manifestes et les images associées.
Ne pas ouvrir de sujet réservé. Ne pas modifier les instantanés.

Pour chaque exercice, relire l'énoncé, le premier raisonnement, le corrigé et
la révision personnelle. Évaluer le premier raisonnement indépendamment de
l'autocorrection. Compléter les champs du modèle JSON avec les résultats
réellement observés et les indices de critères (à partir de 0). Les points
admissibles sont les liens explicites du champ `eligible_points`; ne pas
attribuer de crédit à un point simplement parce qu'il est voisin dans le graphe.
`unassessed` signifie absence de preuve, et non échec. Pour un résultat
`correct`, tous les critères de l'exercice doivent être établis. Une réponse
partielle ne suffit pas à attribuer une réussite complète du point.

Chaque constat évalué cite un élément figé de la première tentative :
`snapshot`, `path` (relatif à cet instantané), `sha256`, `medium` (`text` ou
`image`), `certainty`, `visually_reviewed`, `locator_fr`, et si possible `quote`
exacte pour le texte. Pour qualifier une autocorrection et créer une reprise
adaptative, citer aussi `corrected` et `reference`. Ne jamais inventer une
citation ou une lecture visuelle. Une photo illisible reste non évaluée.

Préciser en français : erreur principale, justification minimale et action
ciblée. Consigner confiance et aide déclarées, sans les deviner. `novel`,
`method_choice`, `changed_context` et `explanation_verified` ne sont vrais que
si l'énoncé, l'absence d'aide déclarée et le raisonnement le justifient.
Ne pas interpréter la réussite d'une forme B comme la preuve complète de A.
Pour la première heure, relever si disponibles les temps de consignes,
tentative et correction et la friction dans `pilot_metrics`; ne pas les
reconstruire a posteriori. Garder les durées réellement déclarées.

Les candidats A4 doivent être associés à un bloc existant, une raison et une
priorité explicites. Évaluer les critères de sortie et confirmer la correction
et la révision Anki seulement si elles ont réellement été effectuées (pour une
activité sans cartes, évaluer le rappel prévu). Les zones non évaluées restent
visibles. La durée n'est jamais libérée sur simple auto-déclaration de maîtrise.

Enregistrer une **copie** du modèle complété, puis, depuis le projet :

```sh
python3 v21/coach.py review /chemin/revue-completee.json
```

Relire `plan.json`, `Tableau.Rmd` et le reçu de revue. Présenter un retour
pédagogique bref et la prochaine action. Si le déficit de temps est positif,
réviser le budget avant toute activité supplémentaire. Les reprises non
réalisées ne deviennent pas automatiquement acquises. Le tuteur reste chargé
d'interpréter les réponses et de choisir les ajustements justifiés.
