# ============================================================
# ETAPA 4 — EXPORTAÇÃO PARA O STATA
#
# Lê as tabelas da etapa 3 e grava, em PASTA_EXPORTACAO:
#   reus.dta           1 linha por (processo, réu): a base de
#                      partida para o pareamento com o CadÚnico
#   processos.dta, eventos.dta, decisoes.dta, partes.dta,
#   movimentacoes.dta, audiencias.dta, historico_classes.dta,
#   incidentes.dta, delegacia.dta
#   decisoes_texto.parquet  (texto integral das sentenças)
#
# ATENÇÃO: reus.dta e partes.dta têm NOMES de pessoas. São dados
# públicos, mas pessoais (LGPD): não compartilhe esses arquivos.
#
# Uso:  python etapa4_exportar.py
# ============================================================

import pandas as pd

import config
from base import log

PASTA_TAB = config.PASTA_TRABALHO / "tabelas"
OUT = config.PASTA_EXPORTACAO


def ler(nome):
    p = PASTA_TAB / nome
    if p.is_dir():
        partes = sorted(p.glob("*.parquet"))
        return pd.concat([pd.read_parquet(f) for f in partes], ignore_index=True) if partes else pd.DataFrame()
    if p.with_suffix(".parquet").exists():
        return pd.read_parquet(p.with_suffix(".parquet"))
    return pd.DataFrame()


def para_stata(df, nome, rotulo):
    if df.empty:
        log.info(f"  {nome}: vazio, não exportado")
        return
    df = df.copy()
    datas = {}
    for c in df.columns:
        if c.startswith("dt_") or c in ("data", "distribuicao_data", "data_disponibilizacao", "data_janela", "data_decisao"):
            df[c] = pd.to_datetime(df[c], errors="coerce")
            datas[c] = "td"
        elif not (pd.api.types.is_numeric_dtype(df[c]) or pd.api.types.is_bool_dtype(df[c])):
            # texto (inclusive colunas inteiramente vazias): o Stata exige strings
            df[c] = df[c].map(lambda v: "" if v is None or (isinstance(v, float) and v != v) else str(v)[:2000]).astype(object)
        elif pd.api.types.is_bool_dtype(df[c]):
            df[c] = df[c].astype("int8")
    df.columns = [c[:32] for c in df.columns]
    df.to_stata(OUT / f"{nome}.dta", write_index=False, version=118, convert_dates=datas, data_label=rotulo[:80])
    log.info(f"  {nome}.dta: {len(df)} linhas, {df.shape[1]} variáveis")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    proc = ler("processos")
    partes = ler("partes")
    dec = ler("decisoes")

    # decisão principal de cada processo: a primeira com resultado identificado
    if not dec.empty:
        dec.drop(columns=["texto"]).to_parquet(OUT / "decisoes.parquet", index=False)
        dec[["hash", "cd_processo", "id_processo", "texto"]].to_parquet(OUT / "decisoes_texto.parquet", index=False)
        principal = (dec[dec["resultado"].notna() & (dec["resultado"] != "sem_texto")].sort_values("data_disponibilizacao")
                     .drop_duplicates("cd_processo"))
        principal = principal.drop(columns=["texto", "hash", "id_processo", "classe", "assunto", "comarca", "foro", "vara"])
        principal = principal.rename(columns={c: f"sent_{c}" for c in principal.columns if c != "cd_processo"})
        principal = principal.rename(columns={"sent_data_disponibilizacao": "data_decisao"})
    else:
        principal = pd.DataFrame(columns=["cd_processo"])

    if not proc.empty:
        proc = proc.merge(principal, on="cd_processo", how="left")
        reus = partes[partes["eh_reu"] == 1].drop(columns=["eh_reu"]).merge(proc, on="cd_processo", how="left")
    else:
        reus = pd.DataFrame()

    log.info(f"ETAPA 4: exportando para {OUT}")
    para_stata(reus, "reus", "TJSP robo: 1 linha por processo x reu (CPOPG + sentenca CJPG)")
    para_stata(proc, "processos", "TJSP robo: 1 linha por processo")
    para_stata(ler("eventos"), "eventos", "TJSP robo: eventos (prisao, soltura, denuncia, sentenca)")
    para_stata(dec.drop(columns=["texto"]) if not dec.empty else dec, "decisoes", "TJSP robo: decisoes do CJPG")
    para_stata(partes, "partes", "TJSP robo: partes do processo")
    for nome in ["movimentacoes", "audiencias", "historico_classes", "incidentes", "delegacia"]:
        para_stata(ler(nome), nome, f"TJSP robo: {nome}")
    log.info("ETAPA 4 concluída.")


if __name__ == "__main__":
    main()
