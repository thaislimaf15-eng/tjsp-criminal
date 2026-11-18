# ============================================================
# TESTE DO PACOTE tjsp (R) COM LOGIN NO e-SAJ
#
# Rode no RStudio, linha a linha ou com "Source". O script:
#   1. faz o login no e-SAJ com CPF e senha (digitados numa janela,
#      sem aparecer na tela) e com o código de 6 dígitos que o e-SAJ
#      manda por e-mail (você digita o código);
#   2. testa as funções do pacote que exigem login.
#
# Nenhuma credencial é gravada em arquivo. O login vale só para esta
# sessão do R. A função tjsp_autenticar() do pacote lê o código
# direto do Gmail, mas isso exige criar uma credencial OAuth no
# Google Cloud. Aqui o código é digitado à mão, o resto do fluxo é
# o mesmo da função do pacote.
# ============================================================

library(tjsp)
library(httr)

base <- "https://esaj.tjsp.jus.br/"
servico <- paste0(base, "sajcas/login?service=",
                  utils::URLencode(paste0(base, "esaj/j_spring_cas_security_check"), reserved = TRUE))

# ---- 1. LOGIN ------------------------------------------------
login <- getPass::getPass("CPF (só números): ")
senha <- getPass::getPass("Senha do e-SAJ: ")

GET(paste0(base, "esaj/portal.do?servico=740000"))
pagina <- xml2::read_html(content(GET(servico), "text"))
lt <- xml2::xml_attr(xml2::xml_find_first(pagina, "//input[@name='lt']"), "value")
execution <- xml2::xml_attr(xml2::xml_find_first(pagina, "//input[@name='execution']"), "value")

POST(servico, encode = "form",
     body = list(username = login, password = senha, lt = lt, execution = execution,
                 `_eventId` = "submit", pbEntrar = "Entrar", signature = "",
                 certificadoSelecionado = "", certificado = ""))

token <- readline("Digite o código de 6 dígitos que chegou no seu e-mail: ")
POST(servico, encode = "form",
     body = list(username = login, password = senha, lt = lt, execution = execution,
                 token = token, `_eventId` = "submit", signature = "",
                 certificadoSelecionado = "", certificado = ""))
rm(login, senha, token)

logado <- get("check_login", envir = asNamespace("tjsp"))()
cat("Logado:", logado, "\n")
stopifnot(logado)

# ---- 2. TESTES -------------------------------------------------
# Processo de teste: ação penal pública já usada no piloto do robô.
processo <- "1501632-16.2023.8.26.0540"
cd_processo <- "F000034Y50000"
pasta <- file.path(tempdir(), "teste_login_tjsp")
dir.create(pasta, showWarnings = FALSE)

# 2a. página do processo pelo número (sem login, cai na tela de login)
try(tjsp_baixar_cpopg(processo, diretorio = pasta))
print(tjsp_ler_dados_cpopg(diretorio = pasta))
print(tjsp_ler_partes(diretorio = pasta))
m <- tjsp_ler_movimentacao(diretorio = pasta)
cat("Movimentações:", nrow(m), "(o robô encontrou 119)\n")

# 2b. tabela de documentos da pasta digital
try(tjsp_baixar_tabela_cd_processo(cd_processo, diretorio = pasta))
docs <- try(tjsp_ler_tabela_docs_cd_processo(diretorio = pasta))
if (!inherits(docs, "try-error")) { cat("Documentos na pasta digital:", nrow(docs), "\n"); print(head(docs, 20)) }

# 2c. denúncia (petição inicial)
try(tjsp_baixar_inicial(processo, diretorio = pasta))

cat("\nArquivos baixados em", pasta, ":\n")
print(list.files(pasta))
# Me mande a saída do console (sem dados pessoais) para registrarmos o resultado.
