# ============================================================
# FUNÇÕES COMUNS: banco de dados, registro (log) e acesso ao e-SAJ
#
# Tudo o que o robô baixa vai para um único banco SQLite. O HTML
# bruto é guardado comprimido, para que a leitura (etapa 3) possa
# ser refeita e corrigida sem baixar nada de novo.
# ============================================================

import logging
import random
import sqlite3
import time
import zlib
from datetime import datetime

import requests

import config

config.PASTA_TRABALHO.mkdir(parents=True, exist_ok=True)

# ----- REGISTRO (LOG) -----------------------------------------
log = logging.getLogger("robo")
if not log.handlers:
    log.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s", "%Y-%m-%d %H:%M:%S")
    for h in (logging.FileHandler(config.LOG, encoding="utf-8"), logging.StreamHandler()):
        h.setFormatter(fmt)
        log.addHandler(h)


# ----- BANCO DE DADOS -----------------------------------------
ESQUEMA = """
-- Controle da etapa 1: cada (dia, classe) do CJPG já coletado
CREATE TABLE IF NOT EXISTS cjpg_janela (
    data TEXT, classe TEXT, n_decisoes INTEGER, status TEXT, atualizado_em TEXT,
    n_anunciado INTEGER,             -- total que o site disse ter
    PRIMARY KEY (data, classe)
);
-- Etapa 1: uma linha por decisão publicada no CJPG
CREATE TABLE IF NOT EXISTS cjpg_decisao (
    hash TEXT PRIMARY KEY,           -- impressão digital da decisão (evita duplicar)
    cd_processo TEXT, id_processo TEXT, classe TEXT, assunto TEXT,
    magistrado TEXT, comarca TEXT, foro TEXT, vara TEXT,
    data_disponibilizacao TEXT, janela_data TEXT, janela_classe TEXT,
    texto BLOB,                       -- texto da decisão, comprimido
    doc_ref TEXT                      -- cdProcesso-cdForo-?-cdDocumento (abre o PDF)
);
CREATE INDEX IF NOT EXISTS ix_dec_cd ON cjpg_decisao (cd_processo);

-- Etapa 2: fila e situação de cada processo no CPOPG
CREATE TABLE IF NOT EXISTS cpopg_processo (
    cd_processo TEXT PRIMARY KEY, id_processo TEXT,
    status TEXT,                      -- pendente | ok | erro | sem_acesso
    n_paginas_movs INTEGER, completo INTEGER, erro TEXT, baixado_em TEXT
);
-- Etapa 2: HTML bruto (página do processo e páginas de movimentações)
CREATE TABLE IF NOT EXISTS cpopg_bruto (
    cd_processo TEXT, tipo TEXT, pagina INTEGER, html BLOB,
    PRIMARY KEY (cd_processo, tipo, pagina)
);
"""


def conectar():
    con = sqlite3.connect(config.BANCO, timeout=60)
    con.execute("PRAGMA journal_mode=WAL")
    con.executescript(ESQUEMA)
    cols = {r[1] for r in con.execute("PRAGMA table_info(cjpg_decisao)")}
    if "doc_ref" not in cols:  # banco criado antes de 18/11/2026
        con.execute("ALTER TABLE cjpg_decisao ADD COLUMN doc_ref TEXT")
    return con


def comprimir(texto):
    return zlib.compress((texto or "").encode("utf-8"), 6)


def descomprimir(blob):
    return zlib.decompress(blob).decode("utf-8") if blob else ""


def agora():
    return datetime.now().isoformat(timespec="seconds")


# ----- ACESSO AO e-SAJ ----------------------------------------
class RoboParado(Exception):
    """Levantada quando o robô deve parar (falhas seguidas, bloqueio)."""


class Esaj:
    """Sessão HTTP educada: uma requisição por vez, com pausa e recuo."""

    BASE = "https://esaj.tjsp.jus.br/"

    def __init__(self):
        self.s = requests.Session()
        self.s.headers["User-Agent"] = config.USER_AGENT
        self._ultima = 0.0
        self.falhas_seguidas = 0
        self.n_requisicoes = 0

    def _esperar_vez(self):
        if config.JANELA_HORARIO:
            ini, fim = config.JANELA_HORARIO
            while True:
                h = datetime.now().hour
                dentro = (ini <= h or h < fim) if ini > fim else (ini <= h < fim)
                if dentro:
                    break
                log.info("Fora da janela de horário; aguardando 10 min.")
                time.sleep(600)
        pausa = config.PAUSA_MINIMA + random.random() * config.PAUSA_ALEATORIA
        falta = self._ultima + pausa - time.time()
        if falta > 0:
            time.sleep(falta)

    def get(self, caminho, params):
        """GET com pausa e recuo. Devolve o texto da resposta."""
        while True:
            self._esperar_vez()
            self._ultima = time.time()
            self.n_requisicoes += 1
            try:
                r = self.s.get(self.BASE + caminho, params=params, timeout=config.TEMPO_LIMITE)
                if r.status_code == 200:
                    self.falhas_seguidas = 0
                    return r.text
                motivo = f"HTTP {r.status_code}"
            except requests.RequestException as e:
                motivo = f"{type(e).__name__}: {e}"
            self.falhas_seguidas += 1
            if self.falhas_seguidas >= config.MAX_FALHAS_SEGUIDAS:
                raise RoboParado(f"{self.falhas_seguidas} falhas seguidas (última: {motivo}).")
            espera = config.ESPERA_APOS_FALHA * 2 ** (self.falhas_seguidas - 1)
            log.warning(f"Falha ({motivo}) em {caminho}; nova tentativa em {espera} s.")
            time.sleep(espera)
