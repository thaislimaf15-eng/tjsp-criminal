# Histórico de versões

## 0.1.0 — 18/11/2026

Primeira versão, testada num piloto (04/09/2023, ação penal ordinária, estado inteiro) e usada na coleta de 2012 do Foro Central Criminal Barra Funda.

- **Etapa 1 (CJPG).**
  - Usa sessão própria e confere o total anunciado pelo site.
  - Confirma resultados zero com uma segunda consulta.
  - Refaz a busca quando o servidor perde a sessão.
  - Faz até 2 passadas por janela e aceita a janela com 97% das decisões distintas.
  - Filtra por vara (`varas_barra_funda.txt`).
  - Guarda `doc_ref`, o identificador do documento que abre o PDF.
- **Etapa 2 (CPOPG).**
  - Baixa a página do processo pelo código interno, sem login.
  - Baixa as movimentações sob demanda (`carregarMovimentacoesAjax.do`, páginas de 5 com cursor) com `--com-movs` ou `--lista`.
- **Etapa 3.** Aplica as regras de eventos (prisão, soltura, andamento, sentença) e de classificação da sentença:
  - o dispositivo é localizado pela última fórmula de fechamento;
  - "extinção da pena" fica separada de "extinção da punibilidade";
  - processos extintos ganham a marca de réu oculto.
- **Etapa 4.** Exporta para Stata (`.dta`, versão 118).
