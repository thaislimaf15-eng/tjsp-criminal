suppressMessages({library(tjsp); library(dplyr)})
base <- file.path(tempdir(), "validacao_tjsp")
dir_cjpg <- file.path(base, "cjpg"); dir_cpopg <- file.path(base, "cpopg")
unlink(c(dir_cjpg, dir_cpopg), recursive = TRUE); dir.create(dir_cjpg); dir.create(dir_cpopg)

varas <- sub("\t.*", "", grep("^#", readLines("varas_barra_funda.txt", encoding = "UTF-8"), invert = TRUE, value = TRUE))

# ---- CJPG: um dia, Barra Funda, ação penal ordinária
t0 <- Sys.time()
r <- try(tjsp_baixar_cjpg(classe = "8657", inicio = "05/03/2012", fim = "05/03/2012", diretorio = dir_cjpg))
cat("CJPG download:", round(as.numeric(difftime(Sys.time(), t0, units = "secs"))), "s; arquivos:", length(list.files(dir_cjpg)), "\n")
cj <- try(tjsp_ler_cjpg(diretorio = dir_cjpg))
if (!inherits(cj, "try-error")) {
  cat("CJPG linhas:", nrow(cj), "| distintas (cd_doc):", n_distinct(cj$cd_doc), "| colunas:", paste(names(cj), collapse = ", "), "\n")
  saveRDS(cj, file.path(base, "cjpg_r.rds"))
  write.csv(select(cj, -any_of(c("julgado"))), file.path(base, "cjpg_r.csv"), row.names = FALSE)
  if ("julgado" %in% names(cj)) {
    cl <- try(tjsp_classificar_sentenca(cj$julgado))
    if (!inherits(cl, "try-error")) { cat("tjsp_classificar_sentenca:\n"); print(table(cl, useNA = "ifany")); write.csv(data.frame(cd_doc = cj$cd_doc, processo = cj$processo, classe_r = cl), file.path(base, "classif_r.csv"), row.names = FALSE) }
  }
}

# ---- CPOPG: 5 processos do dia
procs <- if (!inherits(cj, "try-error")) head(unique(cj$processo[grepl("Barra Funda", cj$foro)]), 5) else character()
cat("processos:", procs, "\n")
t0 <- Sys.time()
try(tjsp_baixar_cpopg(procs, diretorio = dir_cpopg))
cat("CPOPG download:", round(as.numeric(difftime(Sys.time(), t0, units = "secs"))), "s; arquivos:", length(list.files(dir_cpopg)), "\n")
d <- try(tjsp_ler_dados_cpopg(diretorio = dir_cpopg)); if (!inherits(d, "try-error")) { cat("DADOS:", nrow(d), "linhas; colunas:", paste(names(d), collapse = ", "), "\n"); print(as.data.frame(d)) }
p <- try(tjsp_ler_partes(diretorio = dir_cpopg)); if (!inherits(p, "try-error")) { cat("PARTES:", nrow(p), "linhas\n"); print(as.data.frame(p)) }
m <- try(tjsp_ler_movimentacao(diretorio = dir_cpopg)); if (!inherits(m, "try-error")) { cat("MOVIMENTACOES:", nrow(m), "linhas\n"); print(head(as.data.frame(m), 5)) }
dist <- try(tjsp_parsear_distribuicao(d$distribuicao)); if (!inherits(dist, "try-error")) print(dist)
