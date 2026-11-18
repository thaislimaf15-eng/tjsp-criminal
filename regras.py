# ============================================================
# REGRAS DE CLASSIFICAÇÃO (edite aqui, sem mexer no resto)
#
# Todas as regras são expressões regulares aplicadas a textos
# NORMALIZADOS: maiúsculas e sem acentos ("Prisão" -> "PRISAO").
#
# Depois de rodar a etapa 3, confira o arquivo
# titulos_movimentacao.csv: ele lista cada título de movimentação
# encontrado, quantas vezes aparece e qual evento recebeu. Títulos
# frequentes sem evento são candidatos a novas regras.
# ============================================================

import re
import unicodedata


def normalizar(texto):
    t = unicodedata.normalize("NFKD", str(texto or ""))
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", t).upper().strip()


# ----- 1. EVENTOS PELO TÍTULO DA MOVIMENTAÇÃO --------------------
# Os títulos seguem, em geral, a Tabela Processual Unificada (TPU)
# do CNJ, por isso são padronizados. Um título pode gerar mais de
# um evento.
EVENTOS_TITULO = [
    # prisão e liberdade antes da sentença
    ("flagrante",               r"FLAGRANTE"),
    ("audiencia_custodia",      r"CUSTODIA"),
    ("preventiva_decretada",    r"(DECRETAD|CONVERTID|CONVERSAO).{0,60}PREVENTIVA|PREVENTIVA.{0,30}DECRETAD"),
    ("temporaria_decretada",    r"TEMPORARIA.{0,30}DECRETAD|DECRETAD.{0,30}TEMPORARIA"),
    ("liberdade_provisoria",    r"LIBERDADE PROVISORIA"),
    ("prisao_relaxada",         r"RELAXAD.{0,30}PRISAO|RELAXAMENTO"),
    ("prisao_revogada",         r"REVOGAD.{0,30}PRIS|PRIS.{0,40}REVOGAD"),
    ("prisao_domiciliar",       r"DOMICILIAR"),
    ("cautelares_diversas",     r"CAUTELAR|MONITORAMENTO ELETRONICO|TORNOZELEIRA"),
    ("mandado_prisao_expedido", r"MANDADO DE PRISAO.{0,40}EXPEDID|EXPEDID.{0,40}MANDADO DE PRISAO|EXPEDICAO DE MANDADO DE PRISAO"),
    ("mandado_prisao_cumprido", r"MANDADO DE PRISAO.{0,40}CUMPRID|PRISAO EFETUADA|CUMPRIMENTO DE MANDADO DE PRISAO"),
    ("alvara_soltura",          r"ALVARA DE SOLTURA"),
    # andamento
    ("distribuicao_sorteio",    r"DISTRIBUIDO LIVREMENTE|REDISTRIBUIDO LIVREMENTE"),
    ("denuncia_oferecida",      r"DENUNCIA JUNTADA|OFERECIDA A DENUNCIA|OFERECIMENTO DA DENUNCIA"),
    ("denuncia_recebida",       r"RECEBIDA A DENUNCIA|DENUNCIA RECEBIDA|RECEBIMENTO DA DENUNCIA"),
    ("denuncia_rejeitada",      r"REJEITADA A DENUNCIA|DENUNCIA REJEITADA|REJEICAO DA DENUNCIA"),
    ("anpp",                    r"NAO PERSECUCAO"),
    ("transacao_penal",         r"TRANSACAO PENAL"),
    ("suspensao_processo",      r"SUSPENSAO CONDICIONAL DO PROCESSO"),
    ("suspenso_revelia",        r"ART\.? ?366|CITACAO POR EDITAL"),
    ("redistribuicao",          r"REDISTRIBU"),
    ("evolucao_classe",         r"EVOLUIDA A CLASSE"),
    # sentença
    ("condenacao_ppl",          r"CONDENACAO A PENA PRIVATIVA DE LIBERDADE(?!.{0,20}SUBSTITU)(?!.{0,40}(SURSIS|SUSPENSAO CONDICIONAL))"),
    ("condenacao_substituida",  r"CONDENACAO.{0,60}SUBSTITUIDA|SUBSTITUIDA POR RESTRITIVA"),
    ("condenacao_sursis",       r"CONDENACAO.{0,80}(SURSIS|SUSPENSAO CONDICIONAL DA PENA)"),
    ("condenacao_outra",        r"^CONDENACAO|PROCEDENCIA DA ACAO PENAL|JULGADA PROCEDENTE"),
    ("absolvicao_impropria",    r"ABSOLVICAO IMPROPRIA|MEDIDA DE SEGURANCA"),
    ("absolvicao",              r"ABSOLVI|IMPROCEDENCIA"),
    ("desclassificacao",        r"DESCLASSIFIC"),
    ("pronuncia",               r"^PRONUNCIA|PRONUNCIAD"),
    ("impronuncia",             r"IMPRONUNCIA"),
    ("condenacao_com_prisao",   r"COM DECRETACAO DA PRISAO"),   # soma-se a condenacao_ppl
    ("extincao_punibilidade",   r"EXTINTA A PUNIBILIDADE|EXTINCAO DA PUNIBILIDADE"),
    ("extincao_pena",           r"POR CUMPRIMENTO DA PENA|EXTINTA A PENA"),  # posterior à condenação
    # depois da sentença
    ("transito_julgado",        r"TRANSITO EM JULGADO|TRANSITAD"),
    ("recurso_ao_tribunal",     r"REMETIDOS OS AUTOS PARA O TRIBUNAL|RECEBIDO O RECURSO"),
    ("retorno_do_tribunal",     r"RECEBIDOS OS AUTOS DO TRIBUNAL"),
    ("execucao_cadastrada",     r"EXECUCAO DA PENA CADASTRAD|GUIA DE RECOLHIMENTO|GUIA DE EXECUCAO|GUIA ELETRONICA ENVIADA"),
    ("arquivamento",            r"ARQUIVADO DEFINITIVAMENTE"),
]
# "condenacao_outra" só vale se nenhuma condenação específica casou
CONDENACOES_ESPECIFICAS = {"condenacao_ppl", "condenacao_substituida", "condenacao_sursis"}

# ----- 2. EVENTOS DE PRISÃO NO TEXTO DA DECISÃO -------------------
# Muitas decisões sobre prisão aparecem com títulos genéricos
# ("Proferidas Outras Decisões não Especificadas"); o que decidiu
# está no texto (observação) da movimentação.
EVENTOS_TEXTO = [
    ("preventiva_decretada",    r"DECRETO A PRISAO PREVENTIVA|CONVERTO A PRISAO EM FLAGRANTE.{0,60}PREVENTIVA|CONVERTO .{0,60}EM PRISAO PREVENTIVA"),
    ("preventiva_mantida",      r"MANTENHO A (SUA )?PRISAO|MANTENHO A CUSTODIA CAUTELAR|MANTIDA A PRISAO PREVENTIVA"),
    ("liberdade_provisoria",    r"CONCEDO .{0,60}LIBERDADE PROVISORIA"),
    ("prisao_revogada",         r"REVOGO A (SUA )?PRISAO"),
    ("prisao_relaxada",         r"RELAXO A (SUA )?PRISAO"),
    ("prisao_domiciliar",       r"(CONCEDO|DEFIRO|SUBSTITUO).{0,80}PRISAO DOMICILIAR"),
    ("alvara_soltura",          r"EXPECA-SE (O )?ALVARA DE SOLTURA"),
    ("mandado_prisao_expedido", r"EXPECA-SE (O )?MANDADO DE PRISAO"),
]

# ----- 3. PARTES QUE SÃO RÉUS ------------------------------------
# Rótulo da parte (normalizado) que indica a pessoa acusada.
RE_TIPO_REU = re.compile(r"^(REU|RE|REUS|RES|ACUSAD|AVERIGUAD|INDICIAD|DENUNCIAD|QUERELAD|AUTORA? DO FATO|"
                         r"INVESTIGAD|FLAGRANTEAD|CONDUZID|SENTENCIAD|APENAD|EXECUTAD)")
# Rótulos no feminino (útil para identificar mães)
RE_TIPO_FEMININO = re.compile(r"^(RE|RES|ACUSADA|AVERIGUADA|INDICIADA|DENUNCIADA|QUERELADA|AUTORA DO FATO|"
                              r"INVESTIGADA|FLAGRANTEADA|CONDUZIDA|SENTENCIADA|APENADA|EXECUTADA)$")
RE_DEFENSORIA = re.compile(r"DEFENSORIA|DEF\.? ?PUB|DEFENSOR PUBLICO|CONVENIO")

# ----- 4. SENTENÇA (texto do CJPG) -------------------------------
# Aplicadas à parte final do texto (o dispositivo). O dispositivo
# começa na última expressão de fechamento ("ANTE O EXPOSTO", "ISTO
# POSTO"...), se ela estiver nos últimos MAX_DISPOSITIVO caracteres;
# sem ela, usam-se os últimos TAMANHO_DISPOSITIVO caracteres.
TAMANHO_DISPOSITIVO = 4000
MAX_DISPOSITIVO = 15000
RE_INICIO_DISPOSITIVO = re.compile(
    r"\bDISPOSITIVO\b|(ANTE|DIANTE|PELO|EM FACE|EM VISTA) D[OE] EXPOSTO|ISTO POSTO|POSTO ISSO|ISSO POSTO|"
    r"POR ESTES FUNDAMENTOS|POR ESSES FUNDAMENTOS|POR TODO O EXPOSTO")
SENTENCA = {
    "parcial":      r"PARCIALMENTE PROCEDENTE|PROCEDENTE EM PARTE",
    "condena":      r"JULG(O|A-SE) (TOTALMENTE )?PROCEDENTE|\bCONDENO\b|PARA CONDENAR|"
                    r"\bCONDENAR (O|A|OS|AS) (REU|RE|ACUSAD|DENUNCIAD|SENTENCIAD)",
    "absolve":      r"\bABSOLVO\b|JULG(O|A-SE) IMPROCEDENTE|PARA ABSOLVER|"
                    r"\bABSOLVER (O|A|OS|AS) (REU|RE|ACUSAD|DENUNCIAD)",
    # pena cumprida ou multa paga (art. 66, II, da LEP): decisão
    # posterior à condenação, não um julgamento do mérito
    # (o cumprimento das CONDIÇÕES da suspensão do processo ou do ANPP
    # não entra aqui: é extinção da punibilidade sem condenação)
    "extingue_pena": r"CUMPRIMENTO (INTEGRAL |EFETIVO )?DAS? PENAS?|(INTEGRAL|EFETIVO) CUMPRIMENTO(?! DAS? (CONDICOES|PROPOSTA|ACORDO))|"
                     r"PAGAMENTO DA (PENA DE )?MULTA|PELO (INTEGRAL )?PAGAMENTO|ART(IGO|\.)? ?66,? (INCISO )?II\b|EXTINTA A PENA",
    "extingue":     r"(DECLARO|JULGO|DECLARA-SE|JULGA-SE) EXTINT|EXTINTA A (PUNIBILIDADE|PRETENSAO PUNITIVA)",
    "pronuncia":    r"\bPRONUNCIO\b",
    "impronuncia":  r"\bIMPRONUNCIO\b",
    "desclassifica": r"DESCLASSIFICO",
}
SENTENCA_EXTRA = {
    "regime_fechado":       r"REGIME (INICIAL )?FECHADO",
    "regime_semiaberto":    r"REGIME (INICIAL )?SEMI-?ABERTO",
    "regime_aberto":        r"REGIME (INICIAL )?ABERTO",
    "substituicao":         r"SUBSTITUO A PENA|SUBSTITUIDA POR (DUAS )?(PENAS? )?RESTRITIVA",
    "sursis":               r"SURSIS|SUSPENSAO CONDICIONAL DA PENA",
    "nega_recorrer_liberdade": r"NAO PODERA RECORRER EM LIBERDADE|NEGO .{0,40}RECORRER EM LIBERDADE|MANTENHO A (SUA )?PRISAO|MANTENHO A CUSTODIA",
    "pode_recorrer_liberdade": r"PODERA RECORRER EM LIBERDADE|CONCEDO .{0,40}RECORRER EM LIBERDADE",
    "manda_soltar":         r"ALVARA DE SOLTURA",
    "manda_prender":        r"MANDADO DE PRISAO",
    "detracao":             r"DETRACAO",
}
# No texto inteiro: o réu estava preso durante o processo?
SENTENCA_TEXTO_INTEIRO = {
    "menciona_reu_preso":   r"REU PRESO|RE PRESA|ENCONTRA-SE PRES[OA]|PERMANECEU PRES[OA]|PRES[OA] PREVENTIVAMENTE|PRES[OA] EM FLAGRANTE",
    "menciona_preventiva":  r"PRISAO PREVENTIVA|PREVENTIVAMENTE",
    "menciona_flagrante":   r"FLAGRANTE",
    "menciona_filhos":      r"\bFILHOS?\b.{0,40}\b(MENOR|CRIANCA|DEPENDE)|GESTANTE|LACTANTE|MAE DE",
}

compilar = lambda d: {k: re.compile(v) for k, v in d.items()}
EVENTOS_TITULO_C = [(e, re.compile(r)) for e, r in EVENTOS_TITULO]
EVENTOS_TEXTO_C = [(e, re.compile(r)) for e, r in EVENTOS_TEXTO]
SENTENCA_C = compilar(SENTENCA)
SENTENCA_EXTRA_C = compilar(SENTENCA_EXTRA)
SENTENCA_TEXTO_INTEIRO_C = compilar(SENTENCA_TEXTO_INTEIRO)


def eventos_do_titulo(titulo_norm):
    achados = [e for e, r in EVENTOS_TITULO_C if r.search(titulo_norm)]
    if CONDENACOES_ESPECIFICAS & set(achados) and "condenacao_outra" in achados:
        achados.remove("condenacao_outra")
    if "absolvicao_impropria" in achados and "absolvicao" in achados:
        achados.remove("absolvicao")
    return achados


def eventos_do_texto(obs_norm):
    return [e for e, r in EVENTOS_TEXTO_C if r.search(obs_norm)]


def classificar_sentenca(texto):
    """Resultado da decisão a partir do dispositivo (fim do texto)."""
    t = normalizar(texto)
    marcas = [m.start() for m in RE_INICIO_DISPOSITIVO.finditer(t)]
    ini = marcas[-1] if marcas and 300 <= len(t) - marcas[-1] <= MAX_DISPOSITIVO else None
    disp = t[ini:] if ini is not None else t[-TAMANHO_DISPOSITIVO:]
    s = {k: bool(r.search(disp)) for k, r in SENTENCA_C.items()}
    if s["parcial"] or (s["condena"] and s["absolve"]):
        resultado = "condenacao_parcial"
    elif s["condena"]:
        resultado = "condenacao"
    elif s["absolve"]:
        resultado = "absolvicao"
    elif s["extingue_pena"]:
        resultado = "extincao_pena"
    elif s["pronuncia"]:
        resultado = "pronuncia"
    elif s["impronuncia"]:
        resultado = "impronuncia"
    elif s["extingue"]:
        resultado = "extincao_punibilidade"
    elif s["desclassifica"]:
        resultado = "desclassificacao"
    else:
        resultado = None
    out = {"resultado": resultado}
    out.update({k: int(bool(r.search(disp))) for k, r in SENTENCA_EXTRA_C.items()})
    out.update({k: int(bool(r.search(t))) for k, r in SENTENCA_TEXTO_INTEIRO_C.items()})
    # pena total aproximada: primeira menção a "X anos" e "Y meses" no dispositivo
    m = re.search(r"(\d{1,2})\s*(?:\([^)]{0,30}\)\s*)?ANOS?", disp)
    out["pena_anos_aprox"] = int(m.group(1)) if m else None
    m = re.search(r"(\d{1,2})\s*(?:\([^)]{0,30}\)\s*)?MES(?:ES)?", disp)
    out["pena_meses_aprox"] = int(m.group(1)) if m else None
    return out


# ----- 5. DADOS DE QUALIFICAÇÃO (para o pareamento) --------------
RE_CPF = re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b")
RE_RG = re.compile(r"\bR\.?G\.?\s*(?:N[º°O.]?\s*)?:?\s*([\dXx][\d.\-Xx]{5,14})")
RE_NASC = re.compile(r"NASCID[OA]\s+(?:EM|AOS?)\s+(\d{1,2}[/.]\d{1,2}[/.]\d{2,4})", re.I)
RE_FILIACAO = re.compile(r"FILH[OA]\s+DE\s+([A-ZÀ-Úa-zà-ú' ]{5,90}?(?:\s+E\s+(?:DE\s+)?[A-ZÀ-Úa-zà-ú' ]{5,90}?)?)(?=[,;.\n]|\s+NASCID|\s+PORTADOR|\s+RESIDENTE|\s+NATURAL)", re.I)


def qualificacao(texto):
    t = str(texto or "")
    return {
        "cpf_texto": "; ".join(dict.fromkeys(RE_CPF.findall(t)))[:200] or None,
        "rg_texto": "; ".join(dict.fromkeys(RE_RG.findall(t)))[:200] or None,
        "nascimento_texto": "; ".join(dict.fromkeys(RE_NASC.findall(t)))[:200] or None,
        "filiacao_texto": "; ".join(dict.fromkeys(m.strip() for m in RE_FILIACAO.findall(t)))[:400] or None,
    }
