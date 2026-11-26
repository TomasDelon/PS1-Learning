args <- commandArgs(trailingOnly = TRUE)
root <- normalizePath(if (length(args)) args[[1]] else ".", mustWork = TRUE)
out <- if (length(args) >= 2L) args[[2]] else file.path(tempdir(), "ps1-native-r-validation")
dir.create(out, recursive = TRUE, showWarnings = FALSE)
stopifnot(requireNamespace("knitr", quietly = TRUE),
          requireNamespace("rmarkdown", quietly = TRUE),
          requireNamespace("jsonlite", quietly = TRUE))
files <- sort(list.files(file.path(root, "lessons"), pattern = "_(Travail|Corrige)\\.Rmd$",
                         recursive = TRUE, full.names = TRUE))
if (length(args) >= 3L) files <- files[grepl(args[[3]], basename(files))]
if (!length(files)) stop("No authored lesson Rmds")
results <- vector("list", length(files))
for (i in seq_along(files)) {
  file <- files[[i]]
  destination <- file.path(out, tools::file_path_sans_ext(basename(file)))
  dir.create(destination, recursive = TRUE, showWarnings = FALSE)
  messages <- character()
  warnings <- character()
  started <- proc.time()[["elapsed"]]
  result <- tryCatch(withCallingHandlers({
    # Only generated lesson files are rendered. Official sources are never run.
    target <- rmarkdown::render(file, output_format = "html_document",
      output_dir = destination, intermediates_dir = destination,
      envir = new.env(parent = globalenv()), quiet = TRUE, clean = TRUE)
    list(status = "PASS", output = target)
  }, warning = function(w) {
    warnings <<- c(warnings, conditionMessage(w)); invokeRestart("muffleWarning")
  }, message = function(m) {
    messages <<- c(messages, conditionMessage(m)); invokeRestart("muffleMessage")
  }), error = function(e) list(status = "BLOCKED", error = conditionMessage(e)))
  results[[i]] <- c(list(file = substring(file, nchar(root) + 2L),
                        seconds = unname(proc.time()[["elapsed"]] - started),
                        warnings = warnings, messages = messages), result)
  cat(basename(file), result$status, "\n")
  flush.console()
}
receipt <- list(runtime = R.version.string,
  versions = lapply(c("knitr", "rmarkdown", "jsonlite"), function(p) list(package = p, version = as.character(packageVersion(p)))),
  scope = "Generated Rmd parse, chunk execution and full native knitr/Pandoc render; no learner state and no official source execution.",
  count = length(results), passed = sum(vapply(results, function(x) x$status == "PASS", logical(1))),
  results = results)
jsonlite::write_json(receipt, file.path(out, "native_R_receipt.json"), pretty = TRUE, auto_unbox = TRUE, null = "null")
if (receipt$passed != receipt$count) quit(status = 1L)
