# PS1 · Prise de notes

## Syntaxe R

- **Vecteurs :** `x[-1]` exclut le premier élément ; `class(x)` donne la classe ; `as.integer(x)` convertit les booléens en 0 et 1.
- **Inspection :** `names(d)`, `str(d)`, `head(d)`, `nrow(d)`, `ncol(d)`.
- **Sélection :** `d$mesure` extrait une colonne ; `d[condition, ]` sélectionne des lignes.
- **Valeurs manquantes :** `is.na(x)` détecte les NA ; `x |> mean(na.rm=TRUE)` calcule la moyenne des valeurs connues.
- **Documentation :** `args(mean)` affiche les arguments ; `?mean` ouvre l'aide.
