# tjsp-criminal

Coleta de processos criminais de primeiro grau do Tribunal de Justiça de São Paulo (TJSP) a partir das consultas públicas do e-SAJ, sem login. O objetivo é montar uma base para estimar efeitos da prisão de pais e mães sobre os filhos, com um desenho de juiz sorteado como instrumento (Norris, Pecenco e Weaver, 2021).

Versão: ver `VERSION` e `CHANGELOG.md`.

## O que o robô faz

| Etapa | Arquivo | Fonte | O que guarda |
|---|---|---|---|
| 1 | `etapa1_cjpg.py` | CJPG (Consulta de Julgados de 1º Grau) | Cada sentença das classes de ação penal (ordinária, sumária, sumaríssima, júri), dia a dia, com o filtro de varas do `config.py`. Guarda número do processo, código interno, **magistrado que assinou**, vara, foro e texto integral. |
| 2 | `etapa2_cpopg.py` | CPOPG (Consulta Processual de 1º Grau) | Para cada processo da etapa 1, guarda a página do processo: **tipo de distribuição (Livre, Prevenção...)**, juiz atual, partes com a marca **"Réu Preso"**, delegacia, audiências, histórico de classes e incidentes. Com `--com-movs` ou `--lista`, baixa também **todas as movimentações**. |
| 3 | `etapa3_ler.py` | banco local | Monta as tabelas de processos, partes, movimentações, **eventos com data** (flagrante, preventiva, alvará de soltura, mandado de prisão, denúncia, sentença, execução...) e decisões classificadas. |
| 4 | `etapa4_exportar.py` | tabelas da etapa 3 | Gera arquivos `.dta` para o Stata. A base de partida é `reus.dta`. |

- `status.py` mostra quanto já foi coletado e estima o tempo que falta.
- `config.py` reúne tudo o que se ajusta: período, classes, varas, pausas, pastas.
- `regras.py` reúne as regras (expressões regulares) que transformam texto em eventos e resultados.

## Instalação

Requer Python 3.12.

```
python -m venv %USERPROFILE%\.venvs\tjsp
%USERPROFILE%\.venvs\tjsp\Scripts\pip install -r requirements.txt
```

O ambiente e o banco de trabalho devem ficar **fora** de pastas sincronizadas (Google Drive, OneDrive). A sincronização deixa tudo lento e pode corromper o banco SQLite.

## Como rodar

Use `rodar_robo.bat`, ajustando o período e as pastas, ou rode a partir desta pasta:

```
python -X utf8 etapa1_cjpg.py --inicio 2012-01-01 --fim 2012-12-31
python -X utf8 etapa2_cpopg.py --aleatorio
python -X utf8 etapa3_ler.py
python -X utf8 etapa4_exportar.py
python -X utf8 status.py
```

Algumas opções:
- `TJSP_ROBO_TRABALHO`: variável de ambiente que define a pasta do banco. O padrão é `~/TJSP_ROBO`.
- `TJSP_ROBO_EXPORTACAO`: variável de ambiente que define a pasta dos `.dta`.
- `etapa2_cpopg.py --lista processos.txt`: baixa as movimentações só dos processos listados, um número CNJ ou código por linha.

As etapas 1 e 2 podem ser interrompidas a qualquer momento e recomeçam de onde pararam. As etapas 3 e 4 não acessam a internet. Elas podem ser refeitas, por exemplo, depois de mudar uma regra em `regras.py`.

## Cuidados com o servidor

- O robô faz uma requisição por vez, com pausa de 1,5 a 2,5 s entre elas.
- Se o servidor falha, ele espera cada vez mais (30 s, 60 s, 120 s...) e para depois de 6 falhas seguidas.
- Para rodar só à noite, use `JANELA_HORARIO = (19, 7)` em `config.py`.

## O que os testes mostraram (18/11/2026)

1. **Movimentações sob demanda.** O e-SAJ deixou de mandar as movimentações junto com a página do processo. Elas carregam por `carregarMovimentacoesAjax.do`, em páginas de 5, com um cursor criptografado: não há como pular páginas nem pedir páginas maiores. Um processo criminal exigiu 42 requisições em média, de 100 a 400 movimentações. Por isso a fase 1 não baixa as movimentações.
2. **Zeros falsos no CJPG.** Quando sobrecarregado, o CJPG às vezes responde "nenhum resultado". A etapa 1 confere o total anunciado e repete a consulta.
3. **Ordem instável.** A ordem dos resultados no CJPG muda entre páginas, então uma decisão pode se repetir e outra faltar. A etapa 1 faz até duas passadas.
4. **Sessão perdida.** Depois de vários erros 500, o servidor esquece a busca. A etapa 1 refaz a consulta quando uma página vem vazia.
5. **Nem toda linha do CJPG é sentença.** No piloto, 28% das linhas vieram sem texto. As que abrimos eram certidões de trânsito em julgado. Elas recebem `resultado = "sem_texto"`. O PDF pode ser aberto com `doc_ref`:
   - `cjpg/obterArquivo.do?cdProcesso=..&cdForo=..&cdDocumento=..` leva à pasta digital;
   - o campo `parametros` da pasta digital vai em `pastadigital/getPDF.do?`.
6. **Réu oculto.** Em processos extintos, a página omite o réu e mostra só os advogados (`reu_oculto = 1`). O nome continua no texto da sentença.

## Validação

A coleta usa um único instrumento: este robô. Dois pacotes de referência servem para validar amostras, em `validacao/`:

| Pacote | Versão testada | Situação em 18/11/2026 |
|---|---|---|
| `juscraper`, Python (J. Trecenti) | PyPI 0.5.0 e GitHub `871d141` | A versão do PyPI volta sem movimentações. A do GitHub já traz as movimentações sob demanda e coincidiu com o robô: 119 de 119 num processo; 69 de 69 sentenças num dia de 2012. O robô usa funções de leitura do CJPG do `juscraper`. |
| `tjsp`, R (J. de Jesus Filho) | GitHub `4053743` (2.6.1.9005) | **CJPG:** coincidiu, 69 de 69, mas quebra com filtro de muitas varas. **CPOPG:** cai na tela de login por causa de `&gateway=true`; com um contorno, coincidiu com o robô (119, 123 e 139 movimentações). **Classificação:** `tjsp_classificar_sentenca` concorda com o robô em 52 de 68 sentenças; nas divergências lidas, marcou extinções da punibilidade como "procedente". |

A validação manual de uma amostra aleatória de sentenças completa a conferência.

## Limitações

- Só entram processos com sentença publicada no CJPG. Processos suspensos, em andamento ou arquivados sem decisão ficam de fora.
- O juiz da página do processo é o juiz atual da vara. Quem assinou a sentença está em `magistrado` (CJPG).
- Os eventos das movimentações valem para o processo, não para cada réu. A variável `n_reus` permite separar os processos com mais de um réu.
- Processos em segredo de justiça ficam com `status = sem_acesso`.

## Dados pessoais

As bases geradas contêm nomes de pessoas. São dados públicos, mas pessoais (LGPD). **Nenhum dado coletado é versionado neste repositório** (ver `.gitignore`).
