# ============================================================
# ETAPA 1 — CJPG: SENTENÇAS CRIMINAIS DE PRIMEIRO GRAU
#
# Percorre o período DIA A DIA e CLASSE A CLASSE (ação penal
# ordinária, sumária, sumaríssima e júri) e guarda cada decisão
# publicada: número do processo, código interno (cd_processo),
# magistrado que assinou, vara, foro e o TEXTO INTEIRO.
#
# Por que dia a dia: cada (dia, classe) vira uma "janela" pequena,
# registrada no banco. Se o robô parar (queda de internet,
# computador desligado), ele recomeça da primeira janela que
# falta, sem repetir nada.
#
# CONFERÊNCIA: o site informa quantas decisões existem na janela.
# A janela só é marcada como concluída ("ok") quando o número de
# decisões baixadas é igual ao anunciado. Um resultado ZERO só é
# aceito depois de uma segunda consulta, porque o e-SAJ às vezes
# responde "nenhum resultado" quando está sobrecarregado (vimos
# isso no teste de 18/11/2026). Janelas incompletas ficam com
# status "incompleta" e são refeitas na próxima rodada.
#
# Uso:
#   python etapa1_cjpg.py --inicio 2023-09-01 --fim 2023-09-30
#   python etapa1_cjpg.py                    (usa o período do config)
# ============================================================

import argparse
import hashlib
import math
import time
from datetime import date, timedelta

from bs4 import BeautifulSoup
from juscraper.courts.tjsp.cjpg_parse import _extrair_dados_processo, cjpg_n_results

import config
from base import Esaj, RoboParado, agora, comprimir, conectar, log

POR_PAGINA = 10  # o CJPG mostra 10 decisões por página
MAX_PASSADAS = config.MAX_PASSADAS


def ler_varas():
    if not config.ARQUIVO_VARAS:
        return ""
    linhas = config.ARQUIVO_VARAS.read_text(encoding="utf-8").splitlines()
    return ",".join(l.split("\t")[0].strip() for l in linhas if l.strip() and not l.startswith("#"))


VARAS = ler_varas()


def dias(inicio, fim):
    d, f = date.fromisoformat(inicio), date.fromisoformat(fim)
    while d <= f:
        yield d
        d += timedelta(days=1)


def ler_pagina(html):
    soup = BeautifulSoup(html, "lxml")
    div = soup.find("div", {"id": "divDadosResultado"})
    if not div:
        return []
    out = []
    for tr in div.find_all("tr", class_="fundocinza1"):
        tab = tr.find("table")
        if tab is not None:
            r = _extrair_dados_processo(tab)
            a = tab.find("a", {"style": "vertical-align: top"})
            r["doc_ref"] = a.get("name") if a is not None else None
            out.append(r)
    return out


def impressao_digital(r):
    # o atributo name do link (processo-foro-?-documento) identifica o
    # documento; sem ele, usa processo + data + início do texto
    if r.get("doc_ref"):
        return hashlib.sha1(r["doc_ref"].encode("utf-8")).hexdigest()
    base = f"{r.get('cd_processo')}|{r.get('data_disponibilizacao')}|{str(r.get('decisao'))[:3000]}"
    return hashlib.sha1(base.encode("utf-8")).hexdigest()


def consultar(esaj, dia, classe):
    d = dia.strftime("%d/%m/%Y")
    params = {
        "conversationId": "", "dadosConsulta.pesquisaLivre": "", "tipoNumero": "UNIFICADO",
        "classeTreeSelection.values": classe, "dadosConsulta.dtInicio": d, "dadosConsulta.dtFim": d,
        "dadosConsulta.ordenacao": "DESC", "varasTreeSelection.values": VARAS,
    }
    return esaj.get("cjpg/pesquisar.do", params)


def baixar_janela(esaj, dia, classe):
    """Devolve (linhas, n_anunciado, status)."""
    # 1) primeira página + total anunciado (com nova tentativa se vier zero ou ilegível)
    n = None
    for tentativa in range(3):
        html = consultar(esaj, dia, classe)
        try:
            n = cjpg_n_results(html)
        except ValueError as e:
            log.warning(f"  {dia} {classe}: primeira página ilegível ({str(e)[:80]}); repetindo")
            time.sleep(config.ESPERA_APOS_FALHA)
            continue
        if n > 0:
            break
        if tentativa == 0:
            time.sleep(10)  # zero: confirma com uma segunda consulta
            continue
        break
    if n is None:
        return [], None, "incompleta"
    if n == 0:
        return [], 0, "ok"

    # 2) demais páginas (o servidor guarda a busca na sessão).
    # Decisões do mesmo dia não têm ordem fixa entre uma página e
    # outra: algumas aparecem duas vezes e outras ficam de fora. Por
    # isso a janela é percorrida de novo (até MAX_PASSADAS vezes),
    # somando as decisões distintas, até chegar ao total anunciado
    # ou até uma passada inteira não trazer nada novo.
    unicos = {impressao_digital(r): r for r in ler_pagina(html)}
    for passada in range(1, MAX_PASSADAS + 1):
        antes = len(unicos)
        if passada > 1:
            html = consultar(esaj, dia, classe)
            unicos.update({impressao_digital(r): r for r in ler_pagina(html)})
        passada_inteira = True  # todas as páginas vieram completas?
        for p in range(2, math.ceil(n / POR_PAGINA) + 1):
            esperado = min(POR_PAGINA, n - (p - 1) * POR_PAGINA)
            for tentativa in range(3):
                novas = ler_pagina(esaj.get("cjpg/trocarDePagina.do", {"pagina": p, "conversationId": ""}))
                if len(novas) == esperado:
                    break
                log.warning(f"  {dia} {classe}: página {p} veio com {len(novas)} de {esperado}; repetindo")
                if not novas:
                    # página vazia = o servidor perdeu a busca da sessão
                    # (acontece depois de erros 500); refaz a consulta
                    time.sleep(5)
                    consultar(esaj, dia, classe)
                else:
                    time.sleep(5)
            else:
                passada_inteira = False
            unicos.update({impressao_digital(r): r for r in novas})
        if len(unicos) >= n:
            return list(unicos.items()), n, "ok"
        if passada == MAX_PASSADAS and len(unicos) >= config.FRACAO_MINIMA * n:
            return list(unicos.items()), n, "ok_quase"
        if passada > 1 and passada_inteira and len(unicos) == antes:
            # passada completa sem nada novo: o site lista decisões repetidas
            return list(unicos.items()), n, "ok_repetidas"
        log.info(f"  {dia} {classe}: {len(unicos)} de {n} distintas após a passada {passada}; repetindo a janela")
    return list(unicos.items()), n, "incompleta"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inicio", default=config.DATA_INICIO_PADRAO)
    ap.add_argument("--fim", default=config.DATA_FIM_PADRAO)
    ap.add_argument("--classes", nargs="*", default=list(config.CLASSES_CJPG))
    a = ap.parse_args()

    con = conectar()
    feitas = {(r[0], r[1]) for r in con.execute("SELECT data, classe FROM cjpg_janela WHERE status IN ('ok','ok_repetidas','ok_quase')")}
    janelas = [(d, c) for d in dias(a.inicio, a.fim) for c in a.classes if (d.isoformat(), c) not in feitas]
    log.info(f"ETAPA 1 (CJPG): {len(janelas)} janelas (dia × classe) a coletar entre {a.inicio} e {a.fim}.")

    esaj = Esaj()
    total, incompletas = 0, 0
    try:
        for i, (dia, classe) in enumerate(janelas, 1):
            linhas, n, status = baixar_janela(esaj, dia, classe)
            completa = status != "incompleta"
            reg = [(h, r.get("cd_processo"), r.get("id_processo"), r.get("classe"), r.get("assunto"),
                    r.get("magistrado"), r.get("comarca"), r.get("foro"), r.get("vara"),
                    str(r.get("data_disponibilizacao") or ""), dia.isoformat(), classe, comprimir(r.get("decisao")),
                    r.get("doc_ref"))
                   for h, r in linhas]
            incompletas += not completa
            with con:
                con.executemany("INSERT OR IGNORE INTO cjpg_decisao (hash, cd_processo, id_processo, classe, assunto, "
                                "magistrado, comarca, foro, vara, data_disponibilizacao, janela_data, janela_classe, "
                                "texto, doc_ref) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", reg)
                con.executemany(  # cada processo novo entra na fila da etapa 2
                    "INSERT OR IGNORE INTO cpopg_processo (cd_processo, id_processo, status) VALUES (?,?,'pendente')",
                    {(x[1], x[2]) for x in reg if x[1]})
                con.execute("INSERT OR REPLACE INTO cjpg_janela VALUES (?,?,?,?,?,?)",
                            (dia.isoformat(), classe, len(reg), status, agora(), n))
            total += len(reg)
            if not completa:
                log.warning(f"  {dia} classe {classe}: INCOMPLETA ({len(reg)} de {n}); será refeita na próxima rodada")
            if i % 10 == 0 or i == len(janelas):
                log.info(f"  {i}/{len(janelas)} janelas | {dia} classe {classe}: {len(reg)}/{n} | "
                         f"acumulado {total} | incompletas {incompletas} | {esaj.n_requisicoes} requisições")
    except RoboParado as e:
        log.error(f"ROBÔ PAROU: {e} Rode de novo mais tarde; ele recomeça de onde parou.")
    except KeyboardInterrupt:
        log.info("Interrompido pelo usuário. O que já foi salvo continua no banco.")
    finally:
        con.close()


if __name__ == "__main__":
    main()
