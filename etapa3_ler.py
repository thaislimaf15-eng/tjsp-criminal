# ============================================================
# ETAPA 3 — LEITURA: DO HTML BRUTO PARA TABELAS
#
# Não faz nenhuma requisição. Lê o que as etapas 1 e 2 guardaram
# no banco e monta as tabelas abaixo (formato parquet, na pasta
# PASTA_TRABALHO/tabelas). Pode ser rodada quantas vezes quiser:
# se você mudar uma regra em regras.py, basta rodar de novo.
#
#   processos        1 linha por processo (dados da página, partes,
#                    datas do primeiro evento de cada tipo)
#   partes           1 linha por parte (réus marcados)
#   movimentacoes    1 linha por movimentação (data, título, texto)
#   eventos          1 linha por evento identificado (prisão,
#                    soltura, denúncia, sentença, execução...)
#   audiencias, historico_classes, incidentes, delegacia
#   decisoes         1 linha por decisão do CJPG, com o resultado,
#                    regime, sinais de prisão e qualificação
#   titulos_movimentacao.csv   para conferir as regras
#
# Uso:  python etapa3_ler.py
# ============================================================

import re
import shutil
from collections import Counter
from datetime import datetime

import pandas as pd
from bs4 import BeautifulSoup, NavigableString, Tag

import config
import regras as R
from base import conectar, descomprimir, log

PASTA_TAB = config.PASTA_TRABALHO / "tabelas"
LOTE = 1000  # processos por arquivo parcial (evita estourar a memória)

try:
    import lxml  # noqa: F401
    PARSER = "lxml"
except ImportError:
    PARSER = "html.parser"


def data_br(s):
    m = re.search(r"(\d{2})/(\d{2})/(\d{4})", str(s or ""))
    if not m:
        return None
    try:
        return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).date().isoformat()
    except ValueError:
        return None


def texto(el):
    return re.sub(r"\s+", " ", el.get_text(" ", strip=True)) if el else None


# ----- PÁGINA DO PROCESSO (show.do) ------------------------------
CAMPOS = {
    "id_processo": "numeroProcesso", "situacao": "labelSituacaoProcesso",
    "classe": "classeProcesso", "assunto": "assuntoProcesso", "foro": "foroProcesso",
    "vara": "varaProcesso", "juiz_atual": "juizProcesso",
    "distribuicao": "dataHoraDistribuicaoProcesso", "controle": "numeroControleProcesso",
    "area": "areaProcesso", "outros_assuntos": "outrosAssuntosProcesso",
}


def tabela_da_secao(soup, titulo):
    """Linhas (lista de células) da tabela que vem logo depois do título <h2>."""
    for h2 in soup.find_all("h2"):
        if texto(h2).startswith(titulo):
            tab = h2.find_next("table")
            if not tab:
                return []
            linhas = []
            for tr in tab.find_all("tr"):
                cel = [texto(td) for td in tr.find_all("td")]
                if any(cel):
                    linhas.append((cel, tr))
            return linhas
    return []


def ler_partes(soup, cd):
    tab = soup.find(id="tableTodasPartes") or soup.find(id="tablePartesPrincipais")
    partes = []
    if not tab:
        return partes
    for ordem, tr in enumerate(tab.find_all("tr", recursive=False) or tab.find_all("tr")):
        lab, cel = tr.find("td", class_="label"), tr.find("td", class_="nomeParteEAdvogado")
        if not cel:
            continue
        tipo = texto(lab).replace("\xa0", " ").strip() if lab else ""
        nome, reu_preso = [], False
        for c in cel.children:
            if isinstance(c, NavigableString):
                nome.append(str(c))
            elif isinstance(c, Tag):
                if "reuPreso" in (c.get("class") or []):
                    reu_preso = True
                    continue
                if c.name == "br" or "mensagemExibindo" in (c.get("class") or []):
                    break
                nome.append(c.get_text(" "))
        resto = texto(cel) or ""
        tipo_n = R.normalizar(tipo)
        partes.append({
            "cd_processo": cd, "ordem": ordem, "tipo": tipo,
            "nome": re.sub(r"\s+", " ", " ".join(nome)).strip(),
            "eh_reu": int(bool(R.RE_TIPO_REU.match(tipo_n))),
            "feminino_pelo_rotulo": int(bool(R.RE_TIPO_FEMININO.match(tipo_n))),
            "marca_reu_preso": int(reu_preso),
            "defensoria": int(bool(R.RE_DEFENSORIA.search(R.normalizar(resto)))),
            "tem_advogado": int("ADVOGAD" in R.normalizar(resto)),
        })
    return partes


def ler_movimentacoes(htmls, cd):
    """htmls: páginas de movimentações em ordem (ou a página antiga com a tabela)."""
    movs = []
    for h in htmls:
        soup = BeautifulSoup(h, PARSER)
        linhas = soup.select("tr.containerMovimentacao") or soup.select("#tabelaTodasMovimentacoes tr")
        for tr in linhas:
            d, desc = tr.find("td", class_="dataMovimentacao"), tr.find("td", class_="descricaoMovimentacao")
            if not desc:
                continue
            span = desc.find("span")
            obs = texto(span) if span else ""
            if span:
                span.extract()
            link = tr.find("a", href=re.compile("cdDocumento="))
            doc = re.search(r"cdDocumento=(\d+)", link["href"]).group(1) if link else None
            movs.append({"cd_processo": cd, "data": data_br(texto(d)), "titulo": texto(desc),
                         "observacao": obs, "cd_documento": doc})
    # o e-SAJ lista da mais recente para a mais antiga; ordem 1 = mais antiga
    for i, m in enumerate(reversed(movs), 1):
        m["ordem"] = i
    return movs


def ler_processo(cd, brutos):
    show = brutos.get(("show", 0), "")
    soup = BeautifulSoup(show, PARSER)
    p = {"cd_processo": cd}
    for campo, el_id in CAMPOS.items():
        p[campo] = texto(soup.find(id=el_id))
    dist = p.pop("distribuicao") or ""
    p["distribuicao_data"] = data_br(dist)
    m = re.search(r"às\s*(\d{1,2}:\d{2})", dist)
    p["distribuicao_hora"] = m.group(1) if m else None
    p["distribuicao_tipo"] = dist.split(" - ", 1)[1].strip() if " - " in dist else None

    # seções
    deleg = [{"cd_processo": cd, "documento": c[0], "numero": c[1] if len(c) > 1 else None,
              "distrito": c[2] if len(c) > 2 else None, "municipio": c[3] if len(c) > 3 else None}
             for c, _ in tabela_da_secao(soup, "Dados da delegacia") if c[0] and c[0] != "Documento"]
    aud = [{"cd_processo": cd, "data": data_br(c[0]), "audiencia": c[1] if len(c) > 1 else None,
            "situacao": c[2] if len(c) > 2 else None, "qt_pessoas": c[3] if len(c) > 3 else None}
           for c, _ in tabela_da_secao(soup, "Audiências") if data_br(c[0])]
    hist = [{"cd_processo": cd, "data": data_br(c[0]), "tipo": c[1] if len(c) > 1 else None,
             "classe": c[2] if len(c) > 2 else None}
            for c, _ in tabela_da_secao(soup, "Histórico de classes") if data_br(c[0])]
    inc = []
    for c, tr in tabela_da_secao(soup, "Incidentes"):
        a = tr.find("a", href=re.compile(r"processo\.codigo="))
        if a or data_br(c[0]):
            inc.append({"cd_processo": cd, "data": data_br(c[0]), "descricao": " | ".join(x for x in c if x),
                        "cd_incidente": re.search(r"processo\.codigo=([A-Z0-9]+)", a["href"]).group(1) if a else None})

    partes = ler_partes(soup, cd)
    pags = sorted(k[1] for k in brutos if k[0] == "movs")
    htmls = [brutos[("movs", k)] for k in pags] if pags else [show]
    movs = ler_movimentacoes(htmls, cd)

    # eventos
    evs = []
    for m in movs:
        tn, on = R.normalizar(m["titulo"]), R.normalizar(m["observacao"])
        m["eventos"] = ";".join(R.eventos_do_titulo(tn)) or None
        for e in R.eventos_do_titulo(tn):
            evs.append({"cd_processo": cd, "data": m["data"], "evento": e, "fonte": "titulo", "ordem_mov": m["ordem"]})
        for e in R.eventos_do_texto(on):
            evs.append({"cd_processo": cd, "data": m["data"], "evento": e, "fonte": "texto", "ordem_mov": m["ordem"]})
    if any("FLAGRANTE" in R.normalizar(d["documento"]) for d in deleg) or \
            any("FLAGRANTE" in R.normalizar(h["classe"]) for h in hist):
        datas = [h["data"] for h in hist if h["tipo"] and "Inicial" in h["tipo"]] or [p["distribuicao_data"]]
        evs.append({"cd_processo": cd, "data": min(d for d in datas if d) if any(datas) else None,
                    "evento": "flagrante", "fonte": "delegacia_ou_classe", "ordem_mov": None})

    # resumo do processo
    reus = [x for x in partes if x["eh_reu"]]
    # Em processos extintos o TJSP oculta a linha do réu e deixa só os
    # advogados como linhas soltas ("Def. Púb", "Advogado"). O nome do
    # réu continua no texto da sentença (CJPG).
    defesa_solta = [x for x in partes if re.match(r"^(DEF|ADV)", R.normalizar(x["tipo"]))]
    p.update({
        "n_reus": len(reus),
        "reu_oculto": int(not reus and bool(defesa_solta)),
        "algum_reu_preso_hoje": int(any(x["marca_reu_preso"] for x in reus)),
        "alguma_re_mulher": int(any(x["feminino_pelo_rotulo"] for x in reus)),
        "defensoria": int(any(x["defensoria"] for x in reus)
                          or any(R.RE_DEFENSORIA.search(R.normalizar(x["tipo"] + " " + x["nome"])) for x in defesa_solta)),
        "classe_inicial": next((h["classe"] for h in hist if h["tipo"] and "Inicial" in h["tipo"]), None),
        "n_movimentacoes": len(movs),
        "n_audiencias": len(aud),
        "n_incidentes": len(inc),
        "tem_execucao": int(any("EXECU" in R.normalizar(i["descricao"]) for i in inc)),
        "delegacia_documentos": "; ".join(d["documento"] for d in deleg)[:300] or None,
    })
    primeiro = {}
    for e in evs:
        if e["data"] and (e["evento"] not in primeiro or e["data"] < primeiro[e["evento"]]):
            primeiro[e["evento"]] = e["data"]
    for e, d in primeiro.items():
        p[f"dt_{e}"] = d
    return p, partes, movs, evs, aud, hist, inc, deleg


# ----- GRAVAÇÃO EM LOTES -----------------------------------------
def gravar(nome, linhas, lote):
    if not linhas:
        return
    pasta = PASTA_TAB / nome
    pasta.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(linhas).to_parquet(pasta / f"parte_{lote:05d}.parquet", index=False)


def ler_decisoes(con):
    linhas = []
    for row in con.execute("SELECT hash, cd_processo, id_processo, classe, assunto, magistrado, comarca, foro, vara, "
                           "data_disponibilizacao, janela_data, texto, doc_ref FROM cjpg_decisao"):
        txt = descomprimir(row[11])
        d = dict(zip(["hash", "cd_processo", "id_processo", "classe", "assunto", "magistrado", "comarca", "foro",
                      "vara", "data_disponibilizacao", "data_janela"], row[:11]))
        d["data_disponibilizacao"] = data_br(d["data_disponibilizacao"]) or d["data_janela"]
        d["doc_ref"] = row[12]
        # sem texto no CJPG: em geral é uma certidão (ex.: trânsito em
        # julgado) indexada na base de julgados, não a sentença em si;
        # o PDF pode ser aberto com doc_ref (ver LEIAME)
        d["tem_texto"] = int(bool(txt.strip()))
        d.update(R.classificar_sentenca(txt))
        if not d["tem_texto"]:
            d["resultado"] = "sem_texto"

        d.update(R.qualificacao(txt))
        d["tamanho_texto"] = len(txt)
        d["texto"] = txt
        linhas.append(d)
    return pd.DataFrame(linhas)


def main():
    if PASTA_TAB.exists():
        shutil.rmtree(PASTA_TAB)
    PASTA_TAB.mkdir(parents=True)
    con = conectar()

    log.info("ETAPA 3: lendo decisões do CJPG...")
    dec = ler_decisoes(con)
    if len(dec):
        dec.to_parquet(PASTA_TAB / "decisoes.parquet", index=False)
    log.info(f"  {len(dec)} decisões | resultado: {dec['resultado'].value_counts(dropna=False).to_dict() if len(dec) else {}}")

    cds = [r[0] for r in con.execute("SELECT cd_processo FROM cpopg_processo WHERE status='ok' ORDER BY cd_processo")]
    log.info(f"ETAPA 3: lendo {len(cds)} processos do CPOPG...")
    titulos = Counter()
    mapa_eventos = {}
    for lote, ini in enumerate(range(0, len(cds), LOTE), 1):
        bloco = cds[ini:ini + LOTE]
        acum = {k: [] for k in ["processos", "partes", "movimentacoes", "eventos", "audiencias",
                                "historico_classes", "incidentes", "delegacia"]}
        marc = ",".join("?" * len(bloco))
        brutos = {}
        for cd, tipo, pag, html in con.execute(
                f"SELECT cd_processo, tipo, pagina, html FROM cpopg_bruto WHERE cd_processo IN ({marc})", bloco):
            brutos.setdefault(cd, {})[(tipo, pag)] = descomprimir(html)
        for cd in bloco:
            try:
                p, partes, movs, evs, aud, hist, inc, deleg = ler_processo(cd, brutos.get(cd, {}))
            except Exception as e:
                log.warning(f"  leitura falhou em {cd}: {type(e).__name__}: {e}")
                continue
            acum["processos"].append(p)
            acum["partes"] += partes
            acum["movimentacoes"] += movs
            acum["eventos"] += evs
            acum["audiencias"] += aud
            acum["historico_classes"] += hist
            acum["incidentes"] += inc
            acum["delegacia"] += deleg
            for m in movs:
                titulos[m["titulo"]] += 1
                mapa_eventos[m["titulo"]] = m["eventos"]
        for nome, linhas in acum.items():
            gravar(nome, linhas, lote)
        log.info(f"  lote {lote}: {min(ini + LOTE, len(cds))}/{len(cds)} processos")

    pd.DataFrame([{"titulo": t, "n": n, "evento": mapa_eventos.get(t)} for t, n in titulos.most_common()]) \
        .to_csv(PASTA_TAB / "titulos_movimentacao.csv", index=False, encoding="utf-8-sig", sep=";")
    log.info(f"ETAPA 3 concluída. Tabelas em {PASTA_TAB}")
    con.close()


if __name__ == "__main__":
    main()
