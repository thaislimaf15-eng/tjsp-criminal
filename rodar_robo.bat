@echo off
REM ============================================================
REM ROBO TJSP - roda as etapas em sequencia (fase 1: sem movimentacoes).
REM Edite PY, as datas e as pastas abaixo antes de rodar.
REM Pode fechar a janela a qualquer momento: na proxima vez o
REM robo recomeca de onde parou.
REM ============================================================
chcp 65001 > nul
set PY=%USERPROFILE%\.venvs\tjsp\Scripts\python.exe
set INICIO=2012-01-01
set FIM=2012-12-31
REM Pasta do banco de trabalho (fora do Google Drive):
set TJSP_ROBO_TRABALHO=%USERPROFILE%\TJSP_ROBO
REM Pasta para os .dta (pode ser a pasta de dados no Drive):
REM set TJSP_ROBO_EXPORTACAO=G:\caminho\para\DADOS\TJSP_ROBO
cd /d "%~dp0"

echo === ETAPA 1: sentencas (CJPG) de %INICIO% a %FIM% ===
"%PY%" -X utf8 etapa1_cjpg.py --inicio %INICIO% --fim %FIM%

echo === ETAPA 2: paginas dos processos (CPOPG), em ordem aleatoria ===
"%PY%" -X utf8 etapa2_cpopg.py --aleatorio

echo === ETAPA 3: leitura ===
"%PY%" -X utf8 etapa3_ler.py

echo === ETAPA 4: exportacao para o Stata ===
"%PY%" -X utf8 etapa4_exportar.py

"%PY%" -X utf8 status.py
pause
