# services/empresas.py

"""
Who gets a presentation box in the clipping, and who does not.

The reader is an infrastructure investor, not a technology reader. "Conhecida"
means known to THEM: V.tal and Casa dos Ventos need no introduction, and TD SYNNEX
— tens of billions of dollars in revenue — needs one, because it means nothing to
someone who invests in Brazilian data centres.

Three lists in configs/empresas.json decide it:

  conhecidas        the reader already knows them. No box. They are on the list
                    only so their aliases are recognised in the text.
  perfis            a researched profile, sourced and dated. This is the box.
  sem_dado_publico  researched and there is nothing solid in the open. No box,
                    and no re-researching them every week.

A company on none of the three is NEW, and a new company never reaches the PDF
with a profile (DECISOES.md, Q3). It is reported at the end of the run so it can
be researched by hand and added to the file — or approved through overrides.json,
which is the way out of quarantine.

The box appears ONCE per edition, at the company's first appearance in reading
order (Q20). Repeating EVEO's profile under all three of its articles is noise.
"""

import json
import os
import re
import unicodedata
from typing import Dict, List, Optional, Set, Tuple

try:
    from services.utils.projeto import caminho_config
except ImportError:
    from utils.projeto import caminho_config

EMPRESAS_PATH = caminho_config("empresas.json")

# A single short word is where false positives come from. "Positivo" is an
# ordinary Portuguese adjective, "Meta" is a goal, "Oi" is a greeting, and a box
# about a computer maker under an article on a positive result is worse than no
# box at all. Short one-word aliases therefore have to match the exact
# capitalisation on file, and — when the article has a record — also be named as a
# company by the extractor. Multi-word names carry their own evidence.
MAX_ALIAS_AMBIGUO = 10


def _sem_acento(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", texto or "")
        if unicodedata.category(c) != "Mn"
    )


def _carregar() -> Dict:
    try:
        with open(EMPRESAS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"⚠️  Não consegui ler {EMPRESAS_PATH} ({type(e).__name__}); "
              f"nenhuma caixa de empresa será gerada.")
        return {}


_CONFIG = _carregar()


class _Entrada:
    """One company: its canonical name, what it is, and how it is written."""

    __slots__ = ("nome", "tipo", "ficha", "aliases")

    def __init__(self, nome: str, tipo: str, ficha: str, aliases: List[str]):
        self.nome = nome
        self.tipo = tipo          # "conhecida" | "perfil" | "sem_dado"
        self.ficha = ficha
        self.aliases = aliases


def _montar_indice(config: Dict) -> Tuple[Dict[str, _Entrada],
                                          List[Tuple[re.Pattern, str, bool]],
                                          Dict[str, re.Pattern]]:
    entradas: Dict[str, _Entrada] = {}

    for nome, aliases in (config.get("conhecidas") or {}).items():
        entradas[nome] = _Entrada(nome, "conhecida", "", [nome] + list(aliases or []))

    for nome, dados in (config.get("perfis") or {}).items():
        ficha = str((dados or {}).get("ficha", "") or "").strip()
        aliases = list((dados or {}).get("aliases") or [])
        # A profile with no text is a profile that must not be drawn.
        tipo = "perfil" if ficha else "sem_dado"
        entradas[nome] = _Entrada(nome, tipo, ficha, [nome] + aliases)

    for nome, dados in (config.get("sem_dado_publico") or {}).items():
        aliases = list((dados or {}).get("aliases") or [])
        entradas[nome] = _Entrada(nome, "sem_dado", "", [nome] + aliases)

    padroes: List[Tuple[re.Pattern, str, bool]] = []
    confirma: Dict[str, re.Pattern] = {}

    for entrada in entradas.values():
        corpos: List[str] = []
        for alias in entrada.aliases:
            alias = (alias or "").strip()
            if not alias:
                continue
            ambiguo = (" " not in alias) and len(alias) <= MAX_ALIAS_AMBIGUO
            flags = 0 if ambiguo else re.IGNORECASE
            corpo = re.escape(_sem_acento(alias))
            corpos.append(corpo)
            # \b does not fire next to "+" or ".", so the boundary is written by
            # hand: "Kuehne+Nagel" and "V.tal" have to match.
            padrao = re.compile(r"(?<![\w])" + corpo + r"(?![\w])", flags)
            padroes.append((padrao, entrada.nome, ambiguo))

        # The confirmation pattern ignores case on purpose. It answers "did the
        # extractor call this a company?", not "is it spelled the same way" — the
        # feed writes "Eveo" in a headline and the extractor returns "EVEO", and a
        # case-sensitive confirmation lost the box on the article that actually
        # broke the story.
        if corpos:
            confirma[entrada.nome] = re.compile(
                r"(?<![\w])(?:" + "|".join(corpos) + r")(?![\w])", re.IGNORECASE
            )

    # Longest alias first: "Atlantic Data Centers" should win over "Atlantic".
    padroes.sort(key=lambda p: -len(p[0].pattern))
    return entradas, padroes, confirma


_ENTRADAS, _PADROES, _CONFIRMA = _montar_indice(_CONFIG)


# ─────────────────────────────────────────────────────────────────────
# Identification
# ─────────────────────────────────────────────────────────────────────

def identificar(texto: str, citadas: Optional[List[str]] = None) -> List[str]:
    """
    Canonical names of the companies named in a block of text, in order.

    `citadas` is the extractor's own list of companies in the article. It is used
    only to confirm the ambiguous short aliases; it never adds a company the text
    does not contain, because a box under a name the reader cannot see is worse
    than no box.
    """
    if not texto:
        return []

    plano = _sem_acento(texto)
    citadas_plano = _sem_acento(" ; ".join(citadas or "")) if citadas else ""
    tem_citadas = citadas is not None and len(citadas) > 0

    achados: List[Tuple[int, str]] = []
    vistos: Set[str] = set()

    for padrao, nome, ambiguo in _PADROES:
        if nome in vistos:
            continue
        m = padrao.search(plano)
        if not m:
            continue
        if ambiguo and tem_citadas:
            confirmacao = _CONFIRMA.get(nome)
            if not confirmacao or not confirmacao.search(citadas_plano):
                continue
        vistos.add(nome)
        achados.append((m.start(), nome))

    achados.sort()
    return [nome for _, nome in achados]


# Names the extractor keeps returning as companies that are not companies: a tax
# regime, a foundation, a trade association. They are listed so the quarantine
# report stays readable — it is read by a person every week, and a report full of
# things nobody will ever research is a report nobody reads.
_NAO_EMPRESAS = {
    _sem_acento(str(nome)).lower()
    for nome in (_CONFIG.get("nao_empresas") or {})
    if not str(nome).startswith("_")
}


def _nao_e_empresa(nome: str) -> bool:
    return _sem_acento(nome).strip().lower() in _NAO_EMPRESAS


def tipo_de(nome: str) -> str:
    """"conhecida", "perfil", "sem_dado", or "" when the company is unknown."""
    entrada = _ENTRADAS.get(nome)
    return entrada.tipo if entrada else ""


def ficha_de(nome: str) -> str:
    """The profile text, or "" when the company gets no box."""
    entrada = _ENTRADAS.get(nome)
    return entrada.ficha if entrada and entrada.tipo == "perfil" else ""


def conhecida(nome: str) -> bool:
    return bool(identificar(nome))


def registrar_perfil(nome: str, ficha: str, aliases: Optional[List[str]] = None) -> None:
    """
    Add a profile approved by hand (the overrides.json route out of quarantine).

    Lives in memory only: the durable record is overrides.json, and the migration
    into configs/empresas.json stays a human decision.
    """
    global _PADROES
    nome = (nome or "").strip()
    ficha = (ficha or "").strip()
    if not nome or not ficha:
        return
    entradas, novos, confirma = _montar_indice(
        {"perfis": {nome: {"ficha": ficha, "aliases": aliases or []}}}
    )
    _ENTRADAS[nome] = entradas[nome]
    _CONFIRMA.update(confirma)
    _PADROES = sorted(_PADROES + novos, key=lambda p: -len(p[0].pattern))


# ─────────────────────────────────────────────────────────────────────
# Assigning the boxes over an edition
# ─────────────────────────────────────────────────────────────────────

def atribuir_fichas(items: List[Dict]) -> Tuple[List[Dict], Dict[str, List[str]]]:
    """
    Attach each profile box to the first article that names that company.

    `items` must already be in the order the PDF renders them, because "first
    appearance" is defined by what the reader sees, not by what the pipeline
    happened to produce first.

    Returns the items and a report: which boxes were drawn, which companies were
    recognised and need none, and which are new and therefore in quarantine.
    """
    desenhadas: List[str] = []
    ja_apareceu: Set[str] = set()
    novas: Dict[str, str] = {}
    sem_dado: Set[str] = set()

    for item in items:
        texto = f"{item.get('title', '')} {item.get('summary', '')}"
        citadas = item.get("empresas_citadas")
        nomes = identificar(texto, citadas)

        fichas = []
        for nome in nomes:
            entrada = _ENTRADAS.get(nome)
            if not entrada or entrada.tipo != "perfil":
                if entrada and entrada.tipo == "sem_dado":
                    sem_dado.add(nome)
                continue
            if nome in ja_apareceu:
                continue
            ja_apareceu.add(nome)
            desenhadas.append(nome)
            fichas.append({"nome": nome, "texto": entrada.ficha})

        if fichas:
            item["fichas_empresa"] = fichas
        else:
            item.pop("fichas_empresa", None)

        # Quarantine: a company the extractor named and no list recognises.
        for citada in (citadas or []):
            citada = str(citada).strip()
            if not citada or identificar(citada) or _nao_e_empresa(citada):
                continue
            novas.setdefault(citada, item.get("title", "")[:60])

    return items, {
        "desenhadas": desenhadas,
        "sem_dado": sorted(sem_dado),
        "novas": [f"{nome}  (em: {onde})"
                  for nome, onde in sorted(_juntar_variantes(novas).items())],
    }


def _juntar_variantes(novas: Dict[str, str]) -> Dict[str, str]:
    """
    Collapse a short name into the longer one it starts, in the quarantine report.

    One article calls it "Omnia" and another "Omnia WN Holding", and the list a
    person reads every week should not carry the same company twice. Only the
    report is affected: nothing is published either way, and the longer form is
    the one kept, because it is the one worth searching for.
    """
    nomes = sorted(novas, key=len, reverse=True)
    mantidos: Dict[str, str] = {}
    for nome in nomes:
        plano = _sem_acento(nome).lower()
        if any(_sem_acento(m).lower().startswith(plano + " ") for m in mantidos):
            continue
        mantidos[nome] = novas[nome]
    return mantidos


def relatar(relatorio: Dict[str, List[str]]) -> None:
    """Print what the boxes did and did not cover (DECISOES.md, Q24)."""
    desenhadas = relatorio.get("desenhadas") or []
    if desenhadas:
        print(f"{len(desenhadas)} caixas de empresa, na primeira aparição de cada: "
              f"{', '.join(desenhadas)}")
    else:
        print("Nenhuma caixa de empresa nesta edição.")

    sem_dado = relatorio.get("sem_dado") or []
    if sem_dado:
        print(f"   {len(sem_dado)} citadas sem dado público suficiente, portanto sem caixa: "
              f"{', '.join(sem_dado)}")

    novas = relatorio.get("novas") or []
    if novas:
        print(f"⚠️  {len(novas)} empresas novas, ainda sem ficha — em quarentena, NÃO saem "
              f"no PDF. Pesquise e acrescente a configs/empresas.json:")
        for entrada in novas:
            print(f"     - {entrada}")


if __name__ == "__main__":
    print(f"{len(_ENTRADAS)} empresas no arquivo "
          f"({sum(1 for e in _ENTRADAS.values() if e.tipo == 'perfil')} com ficha).\n")

    print("=== identificação ===")
    casos = [
        ("Eveo escolhe data center da Atlantic, da V.tal, para expansão no Nordeste", None),
        ("Bitfarms forçada a interromper mineração na Argentina", None),
        ("Elea Data Centers cresce e projeta faturar R$ 200 milhões", None),
        ("Resultado positivo da companhia surpreendeu o mercado", None),
        ("Positivo Tecnologia amplia produção de servidores", None),
        ("A EAF estuda data center público de IA para o governo federal", None),
        ("A meta do governo é dobrar a capacidade instalada", None),
    ]
    for texto, citadas in casos:
        nomes = identificar(texto, citadas)
        rotulos = [f"{n} [{tipo_de(n)}]" for n in nomes]
        print(f"  {texto[:62]:64} {rotulos}")

    print("\n=== caixa uma vez por edição ===")
    edicao = [
        {"title": "Eveo escolhe data center da Atlantic para expansão", "summary": "",
         "empresas_citadas": ["EVEO", "Atlantic Data Centers", "Datafoo"]},
        {"title": "EVEO projeta crescimento de 60% em 2026", "summary": "",
         "empresas_citadas": ["EVEO"]},
        {"title": "RT-One anuncia rodada de R$ 15 bilhões", "summary": "",
         "empresas_citadas": ["RT-One"]},
    ]
    edicao, relatorio = atribuir_fichas(edicao)
    for i, item in enumerate(edicao, 1):
        nomes = [f["nome"] for f in item.get("fichas_empresa", [])]
        print(f"  item {i}: {nomes or '—'}")
    print()
    relatar(relatorio)
