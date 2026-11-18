# ============================================================
# CONFIGURAÇÃO DO ROBÔ TJSP (CJPG + CPOPG)
#
# Este é o único arquivo que você precisa editar no dia a dia.
# Os demais arquivos leem estas variáveis.
# ============================================================

import os
from pathlib import Path

# ----- ONDE FICAM OS DADOS ------------------------------------
# O banco de trabalho (SQLite) fica FORA do Google Drive: o Drive
# sincroniza o arquivo enquanto o robô escreve nele, o que deixa
# tudo lento e pode corromper o banco. Só as tabelas finais
# (etapa 4) vão para a pasta DADOS do Drive.
PASTA_TRABALHO = Path(os.environ.get("TJSP_ROBO_TRABALHO", Path.home() / "TJSP_ROBO"))
BANCO = PASTA_TRABALHO / "tjsp_robo.sqlite"
LOG = PASTA_TRABALHO / "robo.log"

# Defina TJSP_ROBO_EXPORTACAO para mandar os .dta para outra pasta
# (por exemplo, a pasta de dados da tese no Google Drive).
PASTA_EXPORTACAO = Path(os.environ.get("TJSP_ROBO_EXPORTACAO", PASTA_TRABALHO / "exportacao"))

# ----- O QUE BUSCAR NO CJPG -----------------------------------
# IDs internos das classes no e-SAJ (árvore "PROCESSO CRIMINAL >
# Procedimento Comum"), conferidos com tjsp.listar_classes(grau="1")
# em 18/11/2026. São IDs do e-SAJ, NÃO os códigos CNJ da TPU.
CLASSES_CJPG = {
    "8657": "Ação Penal - Procedimento Ordinário",
    "8803": "Ação Penal - Procedimento Sumário",
    "8804": "Ação Penal - Procedimento Sumaríssimo",
    "8656": "Ação Penal de Competência do Júri",
}

# Recorte geográfico: arquivo com os códigos de vara (um por linha,
# código antes do TAB) usados como filtro no CJPG. None = estado inteiro.
# Fase 1: Foro Central Criminal Barra Funda (capital), ~30 varas
# criminais com distribuição por sorteio.
ARQUIVO_VARAS = Path(__file__).with_name("varas_barra_funda.txt")

# Uma janela (dia × classe) conta como concluída quando as decisões
# distintas chegam a esta fração do total anunciado. No piloto, a
# 1ª passada trouxe 98,5%; as passadas extras custaram o dobro para
# ganhar 2 decisões.
MAX_PASSADAS = 2
FRACAO_MINIMA = 0.97

# Período padrão das sentenças (data de disponibilização no CJPG).
# Pode ser sobrescrito na linha de comando (--inicio / --fim).
DATA_INICIO_PADRAO = "2012-01-01"
DATA_FIM_PADRAO = "2024-12-31"

# ----- RITMO DAS REQUISIÇÕES ----------------------------------
# O robô faz UMA requisição por vez (nunca em paralelo) e espera
# pelo menos este intervalo entre duas requisições ao e-SAJ.
PAUSA_MINIMA = 1.5          # segundos
PAUSA_ALEATORIA = 1.0       # soma até 1 s aleatório à pausa mínima

# Quando o servidor recusa ou falha (429, 5xx, tempo esgotado),
# o robô espera cada vez mais (30 s, 60 s, 120 s...) e PARA depois
# de MAX_FALHAS_SEGUIDAS falhas consecutivas, para não insistir
# num servidor sobrecarregado.
ESPERA_APOS_FALHA = 30
MAX_FALHAS_SEGUIDAS = 6
TEMPO_LIMITE = 60           # segundos por requisição

# Horário de funcionamento (opcional): None = roda a qualquer hora.
# Ex.: (19, 7) roda só das 19h às 7h, fora do horário de expediente.
JANELA_HORARIO = None

# Cabeçalho que identifica o robô ao servidor.
USER_AGENT = "Mozilla/5.0 (robo de pesquisa academica; coleta de dados publicos do e-SAJ)"

# ----- CPOPG ---------------------------------------------------
# Baixar TODAS as movimentações custa ~1 requisição a cada 5
# movimentações (o e-SAJ entrega em páginas de 5). Um processo
# criminal típico tem de 50 a 150 movimentações = 10 a 30
# requisições. Limite de segurança por processo:
MAX_PAGINAS_MOVIMENTACOES = 150

# Fase 1: só a página do processo (1 requisição). As movimentações
# custam ~42 requisições por processo (piloto de 18/11/2026) e ficam
# para a fase 2, com --com-movs ou --lista.
BAIXAR_MOVIMENTACOES = False
