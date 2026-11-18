# ============================================================
# ETAPA 2 — CPOPG: PÁGINA DE CADA PROCESSO + MOVIMENTAÇÕES
#
# Para cada processo que a etapa 1 encontrou, baixa:
#   (a) a página do processo (show.do): classe, assunto, foro,
#       vara, juiz atual, data e TIPO de distribuição (Livre,
#       Direcionada, Dependência...), partes com a marca "Réu
#       Preso", dados da delegacia (inquérito, flagrante),
#       audiências, histórico de classes e incidentes (execução
#       da pena, recursos);
#   (b) TODAS as movimentações. Desde 2026 o e-SAJ não manda mais
#       as movimentações junto com a página: elas são carregadas
#       quando se clica em "Exibir movimentações", pela chamada
#       carregarMovimentacoesAjax.do, de 5 em 5, com um "cursor"
#       para a página seguinte. Por isso o cpopg() do juscraper e
#       o pacote tjsp em R voltam sem movimentações; aqui fazemos
#       essa chamada diretamente.
#
# O HTML bruto fica guardado no banco; a leitura é a etapa 3.
#
# Uso:
#   python etapa2_cpopg.py                 (todos os pendentes)
#   python etapa2_cpopg.py --limite 50     (só 50 processos)
#   python etapa2_cpopg.py --aleatorio     (ordem aleatória: dá
#                                           uma amostra aleatória
#                                           se você parar no meio)
#   python etapa2_cpopg.py --refazer-erros
#   python etapa2_cpopg.py --sem-movs      (só a página do processo)
#   python etapa2_cpopg.py --com-movs      (página + movimentações; o
#                                           padrão vem do config:
#                                           BAIXAR_MOVIMENTACOES)
#   python etapa2_cpopg.py --lista arq.txt (fase 2: baixa de novo, COM
#                                           movimentações, só os
#                                           processos do arquivo: um
#                                           número CNJ ou cd_processo
#                                           por linha)
# ============================================================

import argparse
import re

import config
from base import Esaj, RoboParado, agora, comprimir, conectar, log

RE_CURSOR_1 = re.compile(r'id="cursorMovimentacoesPaginado"[^>]*value="([^"]+)"')
RE_CURSOR_N = re.compile(r'<tr[^>]*id="trCursorMovimentacoes"[^>]*data-cursor="([^"]+)"'
                         r'|<tr[^>]*data-cursor="([^"]+)"[^>]*id="trCursorMovimentacoes"')


def proximo_cursor(html, primeira):
    m = (RE_CURSOR_1 if primeira else RE_CURSOR_N).search(html)
    if not m:
        return None
    return next(g for g in m.groups() if g)


def baixar_processo(esaj, con, cd, com_movs=True):
    pagina = esaj.get("cpopg/show.do", {"processo.codigo": cd})
    if 'id="numeroProcesso"' not in pagina:
        # sem os dados básicos: segredo de justiça, processo removido ou página de erro
        with con:
            con.execute("INSERT OR REPLACE INTO cpopg_bruto VALUES (?,?,?,?)", (cd, "show", 0, comprimir(pagina)))
            con.execute("UPDATE cpopg_processo SET status='sem_acesso', baixado_em=? WHERE cd_processo=?", (agora(), cd))
        return "sem_acesso", 0

    paginas = [("show", 0, pagina)]
    n, completo = 0, 1
    if com_movs and "btnExibirMovimentacoes" in pagina:
        html = esaj.get("cpopg/carregarMovimentacoesAjax.do", {"processo.codigo": cd})
        paginas.append(("movs", 1, html))
        n = 1
        cursor = proximo_cursor(html, primeira=True)
        while cursor:
            if n >= config.MAX_PAGINAS_MOVIMENTACOES:
                completo = 0
                log.warning(f"{cd}: parou no limite de {n} páginas de movimentações.")
                break
            html = esaj.get("cpopg/carregarMovimentacoesAjax.do", {"processo.codigo": cd, "cursor": cursor})
            n += 1
            paginas.append(("movs", n, html))
            cursor = proximo_cursor(html, primeira=False)
    elif com_movs and "tabelaTodasMovimentacoes" in pagina:
        n = 0  # layout antigo: as movimentações já vieram na página
    elif not com_movs:
        completo = 0

    with con:  # grava tudo de uma vez: ou o processo fica completo, ou nada
        if com_movs:  # descarta páginas de uma coleta anterior
            con.execute("DELETE FROM cpopg_bruto WHERE cd_processo=? AND tipo='movs'", (cd,))
        con.executemany("INSERT OR REPLACE INTO cpopg_bruto VALUES (?,?,?,?)",
                        [(cd, t, p, comprimir(h)) for t, p, h in paginas])
        con.execute("UPDATE cpopg_processo SET status='ok', n_paginas_movs=?, completo=?, erro=NULL, baixado_em=? "
                    "WHERE cd_processo=?", (n, completo, agora(), cd))
    return "ok", n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limite", type=int, default=None)
    ap.add_argument("--aleatorio", action="store_true")
    ap.add_argument("--refazer-erros", action="store_true")
    ap.add_argument("--sem-movs", action="store_true")
    ap.add_argument("--com-movs", action="store_true")
    ap.add_argument("--lista", default=None)
    a = ap.parse_args()
    com_movs = (config.BAIXAR_MOVIMENTACOES or a.com_movs or bool(a.lista)) and not a.sem_movs

    con = conectar()
    if a.lista:
        # fase 2: processos escolhidos que ainda não têm as movimentações
        alvo = {l.strip() for l in open(a.lista, encoding="utf-8") if l.strip()}
        fila = [cd for cd, idp, st, comp in con.execute(
                    "SELECT cd_processo, id_processo, status, completo FROM cpopg_processo")
                if (cd in alvo or idp in alvo) and not (st == "ok" and comp == 1)]
        if a.aleatorio:
            import random
            random.shuffle(fila)
        fila = fila[:a.limite] if a.limite else fila
    else:
        estados = "('pendente','erro')" if a.refazer_erros else "('pendente')"
        sql = f"SELECT cd_processo FROM cpopg_processo WHERE status IN {estados}"
        sql += " ORDER BY random()" if a.aleatorio else " ORDER BY cd_processo"
        if a.limite:
            sql += f" LIMIT {int(a.limite)}"
        fila = [r[0] for r in con.execute(sql)]
    log.info(f"ETAPA 2 (CPOPG): {len(fila)} processos na fila.")

    esaj = Esaj()
    contagem = {"ok": 0, "sem_acesso": 0, "erro": 0}
    try:
        for i, cd in enumerate(fila, 1):
            try:
                st, n = baixar_processo(esaj, con, cd, com_movs=com_movs)
                contagem[st] += 1
            except RoboParado:
                raise
            except Exception as e:  # erro de leitura de um processo não para o robô
                contagem["erro"] += 1
                with con:
                    con.execute("UPDATE cpopg_processo SET status='erro', erro=?, baixado_em=? WHERE cd_processo=?",
                                (f"{type(e).__name__}: {str(e)[:300]}", agora(), cd))
                log.warning(f"{cd}: {type(e).__name__}: {str(e)[:150]}")
            if i % 25 == 0 or i == len(fila):
                log.info(f"  {i}/{len(fila)} processos | {contagem} | {esaj.n_requisicoes} requisições")
    except RoboParado as e:
        log.error(f"ROBÔ PAROU: {e} Rode de novo mais tarde; ele recomeça de onde parou.")
    except KeyboardInterrupt:
        log.info("Interrompido pelo usuário. O que já foi salvo continua no banco.")
    finally:
        con.close()


if __name__ == "__main__":
    main()
