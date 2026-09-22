# services/utils/numeros.py

"""
Reading numbers out of Portuguese text, and writing them back.

This module exists because of one rule: a number only becomes a published ratio
if the reader can find both of its inputs in the paragraph above it (DECISOES.md,
Q12). Checking that means comparing "R$ 300 milhões" written in a summary with
300000000 extracted into a structured record — which is a parsing problem, not a
judgement call, so it happens here in Python and never in a prompt.

Three things it has to get right:

- Brazilian formatting. "1.234,56" is one thousand two hundred, "1,8" is one point
  eight, and "10.000" is ten thousand. A parser that assumes the English
  convention turns R$ 1.234 into R$ 1,234 — a factor of a thousand, in a document
  that goes to investors.
- Scale words. "R$ 300 milhões", "R$ 300 mi" and "R$ 15 bi" are the normal way the
  Brazilian press writes money, and the scale carries most of the magnitude.
- Units that mean the same size. 1,8 GW and 1800 MW are the same capacity, and a
  comparison that missed that would reject a legitimate pairing.
"""

import re
import unicodedata
from typing import Dict, List, Optional, Tuple

# ─────────────────────────────────────────────────────────────────────
# Scales and units
# ─────────────────────────────────────────────────────────────────────

_ESCALAS = {
    "mil": 1e3,
    "mi": 1e6, "milhao": 1e6, "milhoes": 1e6,
    "bi": 1e9, "bilhao": 1e9, "bilhoes": 1e9,
    "tri": 1e12, "trilhao": 1e12, "trilhoes": 1e12,
}

# Currency symbols as the Brazilian press writes them. "U$" is a common sloppy
# variant of "US$" and does appear in real copy.
_MOEDAS = {
    "r$": "BRL",
    "us$": "USD", "u$": "USD", "usd": "USD",
    "eur": "EUR",
    "chf": "CHF",
    "gbp": "GBP",
}
_MOEDAS_SIMBOLO = {"€": "EUR", "£": "GBP"}

# Everything comparable is normalised to one canonical unit per family, so that
# 1,8 GW and 1800 MW compare equal.
_UNIDADES = {
    "kw": ("potencia", 0.001),
    "mw": ("potencia", 1.0),
    "gw": ("potencia", 1000.0),
    "tw": ("potencia", 1e6),
    "kwh": ("energia", 0.001),
    "mwh": ("energia", 1.0),
    "gwh": ("energia", 1000.0),
    "twh": ("energia", 1e6),
    # Spelled out. The Valor piece writes "15 a 18 gigawatts (GW)" and then
    # "3 a 4 gigawatts" without the abbreviation, and a reader that only knew
    # "GW" reported the second one as a figure invented by the model — a false
    # alarm against five different prompts before anyone looked at the article.
    "quilowatt": ("potencia", 0.001), "quilowatts": ("potencia", 0.001),
    "kilowatt": ("potencia", 0.001), "kilowatts": ("potencia", 0.001),
    "megawatt": ("potencia", 1.0), "megawatts": ("potencia", 1.0),
    "gigawatt": ("potencia", 1000.0), "gigawatts": ("potencia", 1000.0),
    "terawatt": ("potencia", 1e6), "terawatts": ("potencia", 1e6),
    "megawatt-hora": ("energia", 1.0), "megawatts-hora": ("energia", 1.0),
    "gigawatt-hora": ("energia", 1000.0), "gigawatts-hora": ("energia", 1000.0),
    "terawatt-hora": ("energia", 1e6), "terawatts-hora": ("energia", 1e6),
    "m2": ("area", 1.0),
    "metros quadrados": ("area", 1.0),
    "km2": ("area", 1e6),
    "hectare": ("area", 10000.0), "hectares": ("area", 10000.0), "ha": ("area", 10000.0),
    "%": ("percentual", 1.0),
    # Water is reported in litres per day in Brazilian coverage and in cubic
    # metres in filings; they are the same quantity and have to compare.
    "litros": ("volume", 1.0), "litro": ("volume", 1.0),
    "m3": ("volume", 1000.0), "metros cubicos": ("volume", 1000.0),
}

_CANONICA = {"potencia": "MW", "energia": "MWh", "area": "m2",
             "percentual": "%", "volume": "L"}
_ROTULO_UNIDADE = {"m2": "m²"}


def _sem_acento(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", texto or "")
        if unicodedata.category(c) != "Mn"
    )


def _dobrar_superscrito(texto: str) -> str:
    """m² and km² are written with a superscript; compare them as m2 and km2."""
    return (texto or "").replace("²", "2").replace("³", "3")


# ─────────────────────────────────────────────────────────────────────
# Parsing a single figure
# ─────────────────────────────────────────────────────────────────────

def parse_numero(texto: str) -> Optional[float]:
    """
    Read a number written in Brazilian convention.

    The ambiguous case is a single dot: "1.000" is a thousand and "1.5" is one and
    a half. The rule is the one the language actually follows — a dot with exactly
    three digits after it is a thousands separator, anything else is a decimal
    point — and it is applied only when there is no comma to settle the question.
    """
    if texto is None:
        return None
    limpo = str(texto).strip().replace(" ", "").replace(" ", "")
    if not limpo or not re.search(r"\d", limpo):
        return None

    if "," in limpo and "." in limpo:
        limpo = limpo.replace(".", "").replace(",", ".")
    elif "," in limpo:
        limpo = limpo.replace(",", ".")
    elif limpo.count(".") > 1:
        limpo = limpo.replace(".", "")
    elif "." in limpo:
        inteiro, _, decimal = limpo.partition(".")
        if len(decimal) == 3 and decimal.isdigit():
            limpo = inteiro + decimal

    try:
        return float(limpo)
    except ValueError:
        return None


# ─────────────────────────────────────────────────────────────────────
# Finding every figure in a block of text
# ─────────────────────────────────────────────────────────────────────

_ESCALA_ALT = "|".join(sorted(_ESCALAS, key=len, reverse=True))
_UNIDADE_ALT = "|".join(re.escape(u) for u in sorted(_UNIDADES, key=len, reverse=True))
_MOEDA_ALT = "|".join(
    re.escape(m) for m in sorted(
        list(_MOEDAS) + list(_MOEDAS_SIMBOLO), key=len, reverse=True
    )
)

# Money: symbol first ("R$ 300 milhões") or spelled out after ("300 milhões de reais").
_RE_MOEDA = re.compile(
    r"(?P<simbolo>" + _MOEDA_ALT + r")\s*(?P<numero>\d[\d.,]*)"
    r"\s*(?P<escala>" + _ESCALA_ALT + r")?",
    re.IGNORECASE,
)
_RE_MOEDA_POR_EXTENSO = re.compile(
    r"(?P<numero>\d[\d.,]*)\s*(?P<escala>" + _ESCALA_ALT + r")?\s*de\s+"
    r"(?P<nome>reais|dolares|euros|libras|francos)",
    re.IGNORECASE,
)
_NOME_MOEDA = {
    "reais": "BRL", "dolares": "USD", "euros": "EUR",
    "libras": "GBP", "francos": "CHF",
}

# Physical units. A scale word may sit between number and unit ("mil m²").
_RE_UNIDADE = re.compile(
    r"(?P<numero>\d[\d.,]*)\s*(?P<escala>" + _ESCALA_ALT + r")?"
    r"\s*(?P<unidade>" + _UNIDADE_ALT + r")(?![a-z0-9])",
    re.IGNORECASE,
)


def _quantia(valor: float, familia: str, unidade: str, texto: str) -> Dict:
    return {"valor": valor, "familia": familia, "unidade": unidade, "texto": texto.strip()}


def quantias_no_texto(texto: str) -> List[Dict]:
    """
    Every comparable figure in a block of text, normalised.

    Each entry is {valor, familia, unidade, texto}: the magnitude in the family's
    canonical unit, the family ("moeda", "potencia", "area", "percentual", …), the
    unit label, and the exact substring it came from, so a caller can show the
    reader where it was read.
    """
    if not texto:
        return []

    plano = _sem_acento(_dobrar_superscrito(texto))
    achados: List[Dict] = []
    ocupado: List[Tuple[int, int]] = []

    def livre(inicio: int, fim: int) -> bool:
        return all(fim <= a or inicio >= b for a, b in ocupado)

    alinhado = len(plano) == len(texto)

    def bruto(m) -> str:
        # Slice the ORIGINAL string, so the quoted wording keeps its accents.
        # Stripping accents preserves length for precomposed characters (NFC),
        # which is what web pages carry; text already in NFD would shift the
        # offsets, and then the accent-free copy is the honest thing to quote.
        return texto[m.start():m.end()] if alinhado else plano[m.start():m.end()]

    for m in _RE_MOEDA.finditer(plano):
        numero = parse_numero(m.group("numero"))
        if numero is None:
            continue
        escala = _ESCALAS.get((m.group("escala") or "").lower(), 1.0)
        simbolo = m.group("simbolo").lower()
        moeda = _MOEDAS.get(simbolo) or _MOEDAS_SIMBOLO.get(m.group("simbolo"))
        if not moeda:
            continue
        achados.append(_quantia(numero * escala, "moeda", moeda, bruto(m)))
        ocupado.append((m.start(), m.end()))

    for m in _RE_MOEDA_POR_EXTENSO.finditer(plano):
        if not livre(m.start(), m.end()):
            continue
        numero = parse_numero(m.group("numero"))
        if numero is None:
            continue
        escala = _ESCALAS.get((m.group("escala") or "").lower(), 1.0)
        achados.append(
            _quantia(numero * escala, "moeda", _NOME_MOEDA[m.group("nome").lower()], bruto(m))
        )
        ocupado.append((m.start(), m.end()))

    for m in _RE_UNIDADE.finditer(plano):
        if not livre(m.start(), m.end()):
            continue
        # "ha" is hectares; "há" is the verb, and it is one of the most common
        # words in Portuguese. Stripping accents makes them identical, so
        # "investiu 100 mil há dois anos" was reading as 100 thousand hectares.
        # The accents are still there in the original, so ask it.
        if m.group("unidade").lower() == "ha" and "há" in bruto(m).lower():
            continue
        numero = parse_numero(m.group("numero"))
        if numero is None:
            continue
        escala = _ESCALAS.get((m.group("escala") or "").lower(), 1.0)
        familia, fator = _UNIDADES[m.group("unidade").lower()]
        achados.append(
            _quantia(numero * escala * fator, familia, _CANONICA[familia], bruto(m))
        )
        ocupado.append((m.start(), m.end()))

    return achados


# ─────────────────────────────────────────────────────────────────────
# Comparing a structured value against the text
# ─────────────────────────────────────────────────────────────────────

def normalizar(valor, unidade: str = "", moeda: str = "") -> Optional[Dict]:
    """Put a structured value into the same shape quantias_no_texto returns."""
    if valor is None:
        return None
    try:
        valor = float(valor)
    except (TypeError, ValueError):
        return None

    if moeda:
        return _quantia(valor, "moeda", str(moeda).upper(), "")

    chave = _sem_acento(_dobrar_superscrito(unidade or "")).strip().lower()
    if chave in _UNIDADES:
        familia, fator = _UNIDADES[chave]
        return _quantia(valor * fator, familia, _CANONICA[familia], "")

    # A unit we do not convert (racks, empregos, m³/dia) still compares, as itself.
    return _quantia(valor, "outra", (unidade or "").strip(), "")


def mesma_quantia(a: Optional[Dict], b: Optional[Dict], tolerancia: float = 0.01) -> bool:
    """
    Whether two normalised quantities are the same figure.

    The tolerance absorbs rounding in the prose — a summary that writes "R$ 300
    milhões" for 299,700,000 is reporting the same number to its reader. It does
    not absorb a different number: 1% of 300 million is 3 million, far below the
    gap between any two figures a clipping would confuse.
    """
    if not a or not b:
        return False
    if a["familia"] != b["familia"]:
        return False
    if a["familia"] in ("moeda", "outra") and a["unidade"] != b["unidade"]:
        return False
    if a["valor"] == 0 or b["valor"] == 0:
        return a["valor"] == b["valor"]
    return abs(a["valor"] - b["valor"]) / max(abs(a["valor"]), abs(b["valor"])) <= tolerancia


# Bare numbers, with or without a scale word. Used only as a fallback for units
# this module does not convert — racks, jobs, cubic metres per day. Matching on
# magnitude alone is weaker than matching a unit, which is why it is never the
# first route: it exists because rejecting a number for having an unusual unit
# would throw away figures that are plainly in the article.
_RE_NUMERO_SOLTO = re.compile(
    r"(?<![\w.,])(?P<numero>\d[\d.,]*)\s*(?P<escala>" + _ESCALA_ALT + r")?(?![\d,.])",
    re.IGNORECASE,
)


def numeros_soltos(texto: str) -> List[Dict]:
    """Every bare magnitude in the text, ignoring what it measures."""
    if not texto:
        return []
    plano = _sem_acento(texto)
    achados: List[Dict] = []
    for m in _RE_NUMERO_SOLTO.finditer(plano):
        numero = parse_numero(m.group("numero"))
        if numero is None:
            continue
        escala = _ESCALAS.get((m.group("escala") or "").lower(), 1.0)
        achados.append(
            _quantia(numero * escala, "numero", "", texto[m.start():m.end()])
        )
    return achados


def aparece_no_texto(quantia: Optional[Dict], texto: str,
                     tolerancia: float = 0.01) -> Optional[str]:
    """
    Find a figure in a block of text, and return the exact words it was written as.

    Returning the substring rather than True is deliberate: it is what lets the
    metrics line quote the article's own wording back at the reader instead of a
    number the code reformatted.
    """
    if not quantia:
        return None
    for candidata in quantias_no_texto(texto):
        if mesma_quantia(quantia, candidata, tolerancia):
            return candidata["texto"]

    # Fallback for a unit this module does not convert: compare the magnitude.
    if quantia["familia"] == "outra":
        for candidata in numeros_soltos(texto):
            if mesma_quantia(
                {**quantia, "familia": "numero", "unidade": ""}, candidata, tolerancia
            ):
                return candidata["texto"]
    return None


# ─────────────────────────────────────────────────────────────────────
# Writing a figure back out
# ─────────────────────────────────────────────────────────────────────

_SIMBOLO = {"BRL": "R$", "USD": "US$", "EUR": "€", "GBP": "£", "CHF": "CHF"}


def _numero_br(valor: float, casas: int = 1) -> str:
    """Format a number the Brazilian way, without trailing zeros."""
    texto = f"{valor:,.{casas}f}"
    texto = texto.replace(",", "|").replace(".", ",").replace("|", ".")
    if "," in texto:
        texto = texto.rstrip("0").rstrip(",")
    return texto


def formata_moeda(valor: float, moeda: str) -> str:
    """R$ 300 mi, US$ 2,3 bi, R$ 41 mi — the scale the press itself uses."""
    simbolo = _SIMBOLO.get((moeda or "").upper(), (moeda or "").upper())
    absoluto = abs(valor)
    if absoluto >= 1e12:
        return f"{simbolo} {_numero_br(valor / 1e12)} tri"
    if absoluto >= 1e9:
        return f"{simbolo} {_numero_br(valor / 1e9)} bi"
    if absoluto >= 1e6:
        return f"{simbolo} {_numero_br(valor / 1e6)} mi"
    if absoluto >= 1e3:
        return f"{simbolo} {_numero_br(valor / 1e3)} mil"
    return f"{simbolo} {_numero_br(valor, casas=2)}"


# Public alias: other modules format plain numbers the Brazilian way too.
numero_br = _numero_br


def formata_quantia(quantia: Optional[Dict]) -> str:
    """Render a normalised quantity for the reader."""
    if not quantia:
        return ""
    if quantia["familia"] == "moeda":
        return formata_moeda(quantia["valor"], quantia["unidade"])
    unidade = _ROTULO_UNIDADE.get(quantia["unidade"], quantia["unidade"])
    junto = "" if unidade == "%" else " "
    return f"{_numero_br(quantia['valor'], casas=2)}{junto}{unidade}"


if __name__ == "__main__":
    print("=== leitura de números em português ===")
    casos = [
        ("R$ 300 milhões", 3e8, "moeda"),
        ("R$ 15 bi", 1.5e10, "moeda"),
        ("US$ 2,3 bilhões", 2.3e9, "moeda"),
        ("R$ 1.234", 1234.0, "moeda"),
        ("R$ 3,355 bilhões", 3.355e9, "moeda"),
        ("300 milhões de reais", 3e8, "moeda"),
        ("6 MW", 6.0, "potencia"),
        ("1,8 GW", 1800.0, "potencia"),
        ("10 mil m²", 10000.0, "area"),
        ("4%", 4.0, "percentual"),
        ("R$ 220,4 mi", 2.204e8, "moeda"),
    ]
    falhas = 0
    for texto, esperado, familia in casos:
        achados = quantias_no_texto(texto)
        ok = bool(achados) and abs(achados[0]["valor"] - esperado) < 1e-6 \
            and achados[0]["familia"] == familia
        falhas += 0 if ok else 1
        obtido = achados[0]["valor"] if achados else None
        print(f"  {texto:22} -> {obtido!s:16} esperado {esperado!s:16} {'ok' if ok else 'DIVERGE'}")

    print("\n=== armadilhas que não podem virar número ===")
    for texto in ["Chrome/114.0.0.0", "artigo 5o da lei", "em 2026", "Portaria 1.234/2025"]:
        print(f"  {texto:26} -> {[q['texto'] for q in quantias_no_texto(texto)]}")

    print("\n=== o número da ficha aparece no resumo? ===")
    resumo = ("A Atlantic Data Centers investe R$ 300 milhões em três fases no Recife, "
              "com capacidade projetada de 6 MW e mais de 150 racks na primeira etapa; "
              "a vacância do setor no Brasil está em 4%.")
    for valor, unidade, moeda, rotulo in [
        (300000000, "", "BRL", "capex de R$ 300 mi"),
        (6, "MW", "", "capacidade de 6 MW"),
        (41000000, "", "BRL", "capex de R$ 41 mi (não citado)"),
        (0.006, "GW", "", "6 MW escritos como 0,006 GW"),
        (300000000, "", "USD", "US$ 300 mi (moeda errada)"),
    ]:
        achado = aparece_no_texto(normalizar(valor, unidade, moeda), resumo)
        print(f"  {rotulo:34} -> {achado!r}")

    print("\n=== escrita ===")
    for valor, moeda in [(3e8, "BRL"), (5e7, "BRL"), (2.3e9, "USD"), (41e6, "BRL")]:
        print(f"  {valor:>16,.0f} {moeda} -> {formata_moeda(valor, moeda)}")

    print(f"\n{falhas} divergências na leitura." if falhas else "\nLeitura sem divergências.")
