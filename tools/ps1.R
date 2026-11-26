# Utilitaires locaux du parcours. Aucune commande n'évalue automatiquement
# une réponse, n'appelle une IA ou ne modifie votre collection Anki.

ps1_racine <- function(depart = getwd()) {
  chemin <- normalizePath(depart, mustWork = TRUE)
  repeat {
    if (file.exists(file.path(chemin, "PS1.Rproj"))) return(chemin)
    parent <- dirname(chemin)
    if (identical(parent, chemin)) stop("Ouvrir d'abord le projet PS1.Rproj.")
    chemin <- parent
  }
}

ps1_python <- function() {
  p <- Sys.which("python3")
  if (!nzchar(p)) p <- Sys.which("python")
  if (!nzchar(p)) stop("Python 3 est nécessaire aux instantanés et au graphe.")
  unname(p)
}

ps1_ouvrir <- function(lecon, corrige = FALSE) {
  stopifnot(is.character(lecon), length(lecon) == 1L,
            grepl("^(L[0-9]{2}|D00|X0[12]|A4|F01|S01)$", lecon))
  fichier <- file.path(ps1_racine(), "lessons", lecon,
                       paste0(lecon, if (corrige) "_Corrige.Rmd" else "_Travail.Rmd"))
  if (!file.exists(fichier)) stop("Document absent : ", fichier)
  file.edit(fichier)
  invisible(fichier)
}

ps1_conserver <- function(lecon, phase = c("initial", "corrige"), fichier = NULL) {
  phase <- match.arg(phase)
  stopifnot(is.character(lecon), length(lecon) == 1L,
            grepl("^(L[0-9]{2}|D00|X0[12]|A4|F01|S01)$", lecon))
  racine <- ps1_racine()
  if (is.null(fichier)) fichier <- file.path(racine, "lessons", lecon,
                                            paste0(lecon, "_Travail.Rmd"))
  destination <- file.path(racine, "evidence", lecon,
    paste0(phase, "-", format(Sys.time(), "%Y%m%dT%H%M%SZ", tz = "UTC")))
  resultat <- system2(ps1_python(), c(shQuote(file.path(racine, "tools",
    "snapshot_attempt.py")), shQuote(normalizePath(fichier, mustWork = TRUE)),
    shQuote(destination)))
  if (resultat != 0L) stop("Instantané refusé. Lire le message ci-dessus.")
  invisible(destination)
}

ps1_graphe <- function() {
  racine <- ps1_racine()
  script <- file.path(racine, "tools", "serve.py")
  journal <- file.path(tempdir(), "ps1-graphe.log")
  ancien <- getwd(); on.exit(setwd(ancien), add = TRUE); setwd(racine)
  system2(ps1_python(), shQuote(script), wait = FALSE,
          stdout = journal, stderr = journal)
  message("Graphe : http://127.0.0.1:8765/app/\nJournal : ", journal)
  invisible("http://127.0.0.1:8765/app/")
}
