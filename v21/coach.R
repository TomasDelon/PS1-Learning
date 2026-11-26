# PS1 2.1.1 : commandes à saisir dans la console du projet RStudio.
# Enregistrer le Rmd (Ctrl+S) avant chaque capture.
.ps1v21_root <- normalizePath(getwd(), mustWork = TRUE)
stopifnot(file.exists(file.path(.ps1v21_root, "PS1.Rproj")),
          file.exists(file.path(.ps1v21_root, "v21", "coach.py")))
.ps1v21_python <- unname(Sys.which("python3"))
if (!nzchar(.ps1v21_python)) stop("Python 3.10 ou supérieur est nécessaire.")
if (!requireNamespace("jsonlite", quietly = TRUE)) stop("Installer jsonlite dans R : install.packages('jsonlite')")
.ps1v21_session <- file.path(.ps1v21_root, "progress")
.ps1v21 <- function(...) {
  err <- tempfile(); on.exit(unlink(err))
  args <- c(file.path(.ps1v21_root, "v21", "coach.py"), "--workspace", .ps1v21_session, ...)
  out <- suppressWarnings(system2(.ps1v21_python, shQuote(args), stdout = TRUE, stderr = err))
  if (!is.null(attr(out, "status"))) stop(paste(readLines(err, warn = FALSE), collapse = "\n"), call. = FALSE)
  jsonlite::fromJSON(paste(out, collapse = "\n"), simplifyVector = FALSE)
}
ps1_demarrer <- function() {
  r <- .ps1v21("start")
  if (identical(r$phase, "review")) {
    cat("Tentative en attente de revue :\n", r$handoff, "\n", r$review_template, "\n", sep = "")
  } else {
    file.edit(r$path)
    if (identical(r$phase, "correction")) file.edit(r$correction_path)
    if (!is.null(r$minutes)) cat("Budget :", r$minutes, "min\n")
    if (identical(r$mode, "controle_avant_cours")) cat("Contrôler les exercices sans lire le cours, puis reprendre les blocs nécessaires.\n")
  }
  invisible(r)
}
ps1_corriger <- function() {
  r <- .ps1v21("first"); cat("Première tentative conservée :\n", r$first, "\n", sep = "")
  file.edit(r$path); invisible(r)
}
ps1_terminer <- function(minutes) {
  stopifnot(length(minutes) == 1L, is.numeric(minutes), is.finite(minutes), minutes == as.integer(minutes), minutes >= 1)
  r <- .ps1v21("finish", as.character(as.integer(minutes)))
  cat("Dossier à transmettre au tuteur :\n", r$handoff, "\n", sep = "")
  cat("Revue à compléter :\n", r$review_template, "\n", sep = "")
  invisible(r)
}
ps1_tableau <- function() {
  .ps1v21("status"); file.edit(file.path(.ps1v21_session, "Tableau.Rmd")); invisible(.ps1v21_session)
}
ps1_sonde <- function(id, forme = "A") {
  r <- .ps1v21("probe", id, forme); file.edit(r$path); cat("Budget :", r$minutes, "min\n"); invisible(r)
}
