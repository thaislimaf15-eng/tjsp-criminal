suppressMessages({library(tjsp); library(dplyr)})
d <- file.path(tempdir(), "validacao_tjsp_cpopg")
unlink(d, recursive = TRUE); dir.create(d)
incluir <- get(".tjsp_cpopg_incluir_movimentacoes", envir = asNamespace("tjsp"))
cds <- c("F000034Y50000", "6C0003E710000", "8E0006QSB0000")   # mesmos processos do piloto do robô
t0 <- Sys.time()
for (x in cds) {
  arq <- file.path(d, paste0("cpopg_cd_processo_", x, ".html"))
  httr::GET(paste0("https://esaj.tjsp.jus.br/cpopg/show.do?processo.codigo=", x), httr::write_disk(arq, overwrite = TRUE))
  incluir(arq, x)
  Sys.sleep(1.5)
}
cat("tempo:", round(as.numeric(difftime(Sys.time(), t0, units = "secs"))), "s\n")
dd <- tjsp_ler_dados_cpopg(diretorio = d)
cat("DADOS:", nrow(dd), "x", ncol(dd), "\n"); print(names(dd)); print(as.data.frame(dd)[, intersect(names(dd), c("processo", "situacao", "classe", "assunto", "distribuicao", "juiz", "controle"))])
p <- tjsp_ler_partes(diretorio = d); cat("PARTES:", if (is.null(p)) 0 else nrow(p), "\n"); if (!is.null(p)) print(as.data.frame(p))
m <- tjsp_ler_movimentacao(diretorio = d); cat("MOVIMENTACOES:", nrow(m), "\n"); print(table(m$processo)); print(head(as.data.frame(m)[, c("processo", "data", "movimentacao")[c("processo", "data", "movimentacao") %in% names(m)]], 3)); print(names(m))
h <- tjsp_ler_historico_classes(diretorio = d); cat("HIST CLASSES:", if (is.null(h)) 0 else nrow(h), "\n")
if ("distribuicao" %in% names(dd)) print(tjsp_parsear_distribuicao(dd$distribuicao))
