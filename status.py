# ============================================================
# SITUAÇÃO DO ROBÔ: quanto já foi coletado e quanto falta
# Uso:  python status.py
# ============================================================

import config
from base import conectar

con = conectar()
q = lambda sql: con.execute(sql).fetchall()

print(f"Banco: {config.BANCO}\n")
print("ETAPA 1 (CJPG)")
(n_jan, n_dec, ini, fim), = q("SELECT COUNT(*), COALESCE(SUM(n_decisoes),0), MIN(data), MAX(data) FROM cjpg_janela WHERE status IN ('ok','ok_repetidas','ok_quase')")
(n_inc,), = q("SELECT COUNT(*) FROM cjpg_janela WHERE status='incompleta'")
print(f"  janelas (dia × classe) concluídas: {n_jan}  | incompletas (serão refeitas): {n_inc}  | período: {ini} a {fim}")
print(f"  decisões guardadas: {q('SELECT COUNT(*) FROM cjpg_decisao')[0][0]}"
      f"  | processos distintos: {q('SELECT COUNT(DISTINCT cd_processo) FROM cjpg_decisao')[0][0]}")

print("\nETAPA 2 (CPOPG)")
for st, n in q("SELECT status, COUNT(*) FROM cpopg_processo GROUP BY status"):
    print(f"  {st:12s} {n}")
(media,), = q("SELECT AVG(n_paginas_movs) FROM cpopg_processo WHERE status='ok'")
(pend,), = q("SELECT COUNT(*) FROM cpopg_processo WHERE status='pendente'")
if media is not None:
    req = pend * (1 + media)
    seg = req * (config.PAUSA_MINIMA + config.PAUSA_ALEATORIA / 2 + 0.4)
    print(f"  média de páginas de movimentações por processo: {media:.1f}")
    print(f"  estimativa para os pendentes: {req:,.0f} requisições ≈ {seg / 3600:,.0f} horas ({seg / 86400:,.1f} dias)")
con.close()
