# ============================================================
# VALIDAÇÃO CRUZADA COM O juscraper (versão do GitHub)
#
# Compara, para os mesmos dias e processos, o que o robô guardou no
# banco com o que o juscraper baixa de forma independente:
#   - CJPG: número de decisões por dia e processos em comum;
#   - CPOPG: número de movimentações por processo.
#
# Rode num ambiente SEPARADO do robô (o robô fixa o juscraper 0.5.0
# do PyPI, que não traz movimentações):
#   python -m venv %USERPROFILE%\.venvs\juscraper_dev
#   %USERPROFILE%\.venvs\juscraper_dev\Scripts\pip install git+https://github.com/jtrecenti/juscraper pandas pyarrow
#   %USERPROFILE%\.venvs\juscraper_dev\Scripts\python -X utf8 validacao\comparar_juscraper.py --dias 2012-03-05 --processos 5
# ============================================================

import argparse
import os
import random
import sqlite3
from datetime import date
from pathlib import Path

import juscraper as jus
import pandas as pd

BANCO = Path(os.environ.get("TJSP_ROBO_TRABALHO", Path.home() / "TJSP_ROBO")) / "tjsp_robo.sqlite"
CLASSE = "8657"  # Ação Penal - Procedimento Ordinário


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dias", nargs="+", required=True, help="datas AAAA-MM-DD já coletadas pelo robô")
    ap.add_argument("--processos", type=int, default=5, help="quantos processos sortear para comparar movimentações")
    ap.add_argument("--saida", default="validacao_juscraper.csv")
    a = ap.parse_args()

    con = sqlite3.connect(BANCO)
    t = jus.scraper("tjsp")
    linhas = []

    for dia in a.dias:
        d = date.fromisoformat(dia).strftime("%d/%m/%Y")
        robo = {r[0] for r in con.execute(
            "SELECT DISTINCT id_processo FROM cjpg_decisao WHERE janela_data=? AND janela_classe=?", (dia, CLASSE))}
        js = t.cjpg(pesquisa="", classes=[CLASSE], data_inicio=d, data_fim=d)
        # o robô filtra por vara; o juscraper traz o estado inteiro, então comparamos só os foros do robô
        foros = {r[0] for r in con.execute("SELECT DISTINCT foro FROM cjpg_decisao WHERE janela_data=?", (dia,))}
        js = js[js["foro"].isin(foros)] if foros else js
        jsp = set(js["id_processo"].dropna())
        linhas.append({"teste": "cjpg_processos", "chave": dia, "robo": len(robo), "juscraper": len(jsp),
                       "em_comum": len(robo & jsp), "so_robo": len(robo - jsp), "so_juscraper": len(jsp - robo)})

    cds = [r for r in con.execute("SELECT cd_processo, id_processo FROM cpopg_processo WHERE status='ok' AND completo=1")]
    for cd, idp in random.sample(cds, min(a.processos, len(cds))):
        n_robo = con.execute("SELECT COUNT(*) FROM cpopg_bruto WHERE cd_processo=? AND tipo='movs'", (cd,)).fetchone()[0]
        r = t.cpopg(idp)
        n_js = len(r["movimentacoes"]) if isinstance(r, dict) and "movimentacoes" in r else None
        linhas.append({"teste": "cpopg_movimentacoes", "chave": idp, "robo_paginas": n_robo, "juscraper": n_js})

    out = pd.DataFrame(linhas)
    out.to_csv(a.saida, index=False)
    print(out.to_string(index=False))
    print("\nObs.: para as movimentações, compare com a tabela movimentacoes da etapa 3 (o robô conta páginas de 5).")


if __name__ == "__main__":
    main()
