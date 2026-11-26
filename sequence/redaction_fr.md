# Protocole transversal de rédaction mathématique

Version 2.0.0. Protocole appliqué aux leçons du parcours, sans note attribuée à l’étudiant.

## Objectif

Chaque réponse doit permettre à un lecteur de savoir quels objets sont étudiés, quelles hypothèses sont utilisées, quelle propriété justifie le calcul et ce que le résultat signifie. La rédaction n’est pas un exercice supplémentaire ajouté au budget: elle est évaluée dans les réponses de mathématiques et de R, avec un retour bref.

Les appuis du programme sont la justification des choix et la critique des modèles. ST01 pp.11-13 distingue variables et réalisations; ST04-ST05 pp.6 et9-15 travaille les objets de l’estimation; ST06 risques pp.2-8 impose de préciser le conditionnement d’une décision; ST09 p.7 invite à relier vocabulaire, raisonnement et difficulté concrète. Les fichiers sont identifiés dans [le manifeste](../sources/source_manifest.json) et les adaptations dans [le registre des soutiens](../sources/soutien_mapping.json).

## Une structure stable en cinq étapes

1. **Objets.** «On note [variable/statistique/paramètre] ...» Définir la population, les unités et les symboles utiles.
2. **Hypothèses.** «On suppose que ...» ou «Sous l’hypothèse ...». Nommer uniquement les conditions réellement utilisées et contrôler qu’elles sont pertinentes.
3. **Propriété.** «Par [propriété], puisque [condition], ...». Faire le lien entre la condition et l’étape du calcul.
4. **Résultat.** Donner le calcul, le code ou l’estimation, avec l’égalité exacte ou le signe d’approximation approprié.
5. **Portée.** «Ainsi, dans ce modèle/pour cette population, ...». Inclure les unités, l’incertitude et une limite pertinente lorsque nécessaire.

Une réponse courte peut réunir plusieurs étapes dans une phrase. La structure sert à vérifier le sens, pas à remplir cinq paragraphes mécaniques.

## Formulations à compléter, et condition de validité

| Situation | Formulation de départ | Vérification indispensable |
|---|---|---|
| Conditionnement | «Parmi les observations vérifiant [condition], la proportion de [événement] est ...» | Le dénominateur correspond à la condition; le sens ne s’inverse pas |
| Espérance | «Par linéarité de l’espérance, les variables étant intégrables, ...» | L’indépendance n’est pas ajoutée quand elle n’est pas nécessaire |
| Variance | «Les moments d’ordre deux existent. En développant la variance et les covariances, ...» | Les coefficients sont au carré dans les termes de variance; les covariances conservent les signes |
| Approximation | «Sous [hypothèses], [résultat asymptotique] justifie l’approximation ... pour ...» | Ne pas remplacer une limite par une loi exacte à taille finie |
| Estimation | «Le paramètre [symbole] est fixe et inconnu. L’estimateur [symbole] dépend de l’échantillon; sa valeur observée est ...» | Paramètre, variable aléatoire et valeur numérique restent distincts |
| IC | «La procédure utilisée a un niveau de couverture [niveau], sous [hypothèses]. L’intervalle obtenu est ...» | La couverture décrit les répétitions de la procédure; elle ne devient pas une probabilité fréquentiste du paramètre fixé après observation |
| Test | «On teste [H0] contre [H1], au seuil [alpha] fixé. Sous H0, ...» | L’alternative et la statistique sont définies avant la lecture de la p-valeur |
| Décision | «La p-valeur étant [comparaison au seuil], on [rejette/ne rejette pas] H0 au seuil ...» | Le non-rejet ne démontre pas H0; la p-valeur n’est pas la probabilité de H0 |
| Régression | «À [covariables] fixées, le modèle associe une augmentation d’une unité de [X] à une variation moyenne de ... de [Y].» | L’interprétation correspond aux unités et à la population; une interaction peut faire varier le contraste; le coefficient n’est pas automatiquement causal |
| R | «Cette instruction calcule [objet] sur [lignes/colonnes]; [argument] fixe ...» | Décrire le résultat mathématique du code, pas seulement répéter son nom |

## Intuition et formulation exacte

Chaque nouveau concept reçoit deux couches courtes dans les leçons. La première explique ce que la notion permet de comprendre en langue ordinaire. La deuxième donne les objets, conditions et limites exacts. Elles doivent être compatibles.

Pour la p-valeur, l’idée intuitive est la compatibilité d’un résultat au moins aussi extrême avec le modèle nul, dans le sens choisi par l’alternative. La formulation précise ajoute le conditionnement sous H0, la statistique utilisée et la règle d’extrémité. Une phrase comme «probabilité que notre décision observée soit fausse» ne remplace pas cette définition. Pour une hypothèse nulle composite, la règle de calibrage sous l’ensemble de H0 doit aussi être précisée au niveau exigé par l’exercice.

L’intuition ne remplace pas le calcul. Après l’explication, une tâche brève doit vérifier que l’étudiant distingue deux situations proches: variable et réalisation, variance et écart-type, loi exacte et approximation, non-rejet et preuve, association et causalité.

## Feedback bref, puis transfert

La correction conserve la première phrase de l’étudiant. Elle identifie au plus deux erreurs prioritaires, explique le défaut de sens, puis propose une reformulation minimale. Elle distingue un défaut de vocabulaire d’un défaut mathématique. Les noms des objets et la direction d’un conditionnement passent avant les raffinements stylistiques.

Le prochain fichier ne répète pas la même phrase à recopier. Il demande une interprétation semblable sur une autre situation et vérifie que la condition pertinente réapparaît. Un progrès de rédaction est confirmé par cette nouvelle application, pas par l’acceptation de la reformulation proposée.

## Rubrique indépendante, sans score actif

| Dimension | Critère observable |
|---|---|
| Objets | Les symboles sont définis; variable, réalisation, paramètre et estimateur sont distingués |
| Hypothèses | Les conditions nécessaires sont citées et reliées au contexte |
| Raisonnement | Chaque propriété utilisée justifie effectivement l’étape qui suit |
| Calcul et notation | Sens du conditionnement, égalité/approximation, unités et paramètres sont cohérents |
| Interprétation | La conclusion répond à la question et n’ajoute pas une portée causale ou probabiliste injustifiée |

Ces critères peuvent être satisfaits à des niveaux différents. Ils ne sont pas remplacés par une unique appréciation «bonne réponse». Aucun résultat d’évaluation de l’étudiant n’est créé par ce document.
