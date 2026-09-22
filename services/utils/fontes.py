# services/utils/fontes.py

"""
Source tiers: what each outlet is allowed to do.

The clipping goes to investors, and this week's edition reached them citing a
member of parliament's own campaign site and a page of SEO filler about token
pricing. Tiers decide three things:

  1  enters · can win a duplicate group · can be the sole source of a figure
  2  enters · can win a group · can be sole source for a figure about its own subject
  3  enters · never wins a group · never the sole source of a figure
  4  does not enter

An unlisted outlet is treated as tier 3 rather than dropped: the local paper in
Rio Grande do Norte covers grid news that no national outlet touches. What it
cannot do is win a group or carry a number on its own.

The lists live in configs/fontes.json so they can be edited without touching code.
"""

import json
import os
import re
from typing import Dict, List, Set, Tuple

CONFIGS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "configs",
)
FONTES_PATH = os.path.join(CONFIGS_DIR, "fontes.json")

DEFAULT_TIER = 3

# Titles that carry a bracketed year are the signature of SEO filler written to
# rank rather than to report: "GPT-6 Astra no AWS Bedrock: Sobretaxa de 10% [2026]".
_SEO_TITLE = re.compile(r"\[\s*(19|20)\d{2}\s*\]")


def _load() -> Dict:
    try:
        with open(FONTES_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


_CONFIG = _load()
_TIER_PADRAO = _CONFIG.get("tier_padrao", DEFAULT_TIER)

# Suffixes the feed adds to an outlet's name. Matching on the exact string alone
# sent "TELETIME News" and "Times Brasil | CNBC" to the default tier, not because
# they are unknown but because of a word. Only this closed list is stripped —
# a looser rule (prefix matching) would collapse "Terra" into "Terra Nova".
_SUFFIXES = (" news", " online", " notícias", " noticias", " brasil", " br")

# Lookup is case-insensitive: the feed reports "O GLOBO" where the list says "O Globo".
_TIER_BY_SOURCE: Dict[str, int] = {}


def _normalise(source: str) -> str:
    """Lowercase, drop a co-branding segment after '|', drop a trailing suffix."""
    text = (source or "").strip().lower()
    if "|" in text:
        text = text.split("|", 1)[0].strip()
    for suffix in _SUFFIXES:
        if text.endswith(suffix) and len(text) > len(suffix) + 2:
            text = text[: -len(suffix)].strip()
            break
    return text


for _tier, _sources in _CONFIG.get("tiers", {}).items():
    for _source in _sources:
        _TIER_BY_SOURCE[_source.strip().lower()] = int(_tier)
        _TIER_BY_SOURCE.setdefault(_normalise(_source), int(_tier))

# A bare domain and its display name are the same outlet. Resolving one into the
# other here means the tier is right wherever the check happens, instead of only
# after the feed parser has renamed the source: looking up "g1.globo.com" used to
# fall through to the default tier and let a campaign blog win a duplicate group
# against G1.
_DISPLAY_NAMES: Dict[str, str] = {
    _domain.strip().lower(): _name for _domain, _name in _CONFIG.get("nomes", {}).items()
}
for _domain, _name in _DISPLAY_NAMES.items():
    _tier_of_name = _TIER_BY_SOURCE.get(_name.strip().lower())
    if _tier_of_name is not None:
        _TIER_BY_SOURCE.setdefault(_domain, _tier_of_name)


def tier_of(source: str, title: str = "") -> int:
    """
    Return the tier of an outlet, and 4 for anything that looks like SEO filler.

    An outlet not on any list gets the default tier, which is deliberately 3:
    unknown means untrusted, not excluded.
    """
    if title and _SEO_TITLE.search(title):
        return 4

    key = (source or "").strip().lower()
    if key in _TIER_BY_SOURCE:
        return _TIER_BY_SOURCE[key]
    return _TIER_BY_SOURCE.get(_normalise(source), _TIER_PADRAO)


def is_listed(source: str) -> bool:
    """True when the outlet appears on one of the tier lists."""
    key = (source or "").strip().lower()
    return key in _TIER_BY_SOURCE or _normalise(source) in _TIER_BY_SOURCE


def can_win_group(source: str) -> bool:
    """Whether this outlet may be the surviving article of a duplicate group."""
    return tier_of(source) <= 2


def can_carry_figure_alone(source: str) -> bool:
    """Whether a figure from this outlet may be published without corroboration."""
    return tier_of(source) <= 2


def apply_tier_gate(items: List[Dict]) -> Tuple[List[Dict], List[Dict], Set[str]]:
    """
    Annotate every item with its tier and separate out the ones that do not enter.

    Returns:
        (kept, excluded, unlisted_sources)
    """
    kept: List[Dict] = []
    excluded: List[Dict] = []
    unlisted: Set[str] = set()

    for item in items:
        source = item.get("source", "")
        tier = tier_of(source, item.get("title", ""))
        item["source_tier"] = tier

        if not is_listed(source):
            unlisted.add(source)

        if tier >= 4:
            excluded.append(item)
        else:
            kept.append(item)

    return kept, excluded, unlisted


if __name__ == "__main__":
    print(f"Carregado de {FONTES_PATH}")
    print(f"{len(_TIER_BY_SOURCE)} fontes classificadas, padrão = tier {_TIER_PADRAO}\n")

    casos = [
        ("Valor Econômico", "", 1),
        ("O GLOBO", "", 1),
        ("Data Center Dynamics", "", 1),
        ("G1", "", 2),
        ("Exame", "", 2),
        ("agorarn.com.br", "", 3),
        ("samiabomfim.com.br", "", 3),
        ("shattered.io", "", 4),
        ("jornal.que.nunca.vi.com.br", "", 3),
        ("Exame", "Alguma coisa sobre nuvem [2026]", 4),
    ]
    print(f"{'fonte':32} {'tier':>4}  {'esperado':>8}  resultado")
    for source, title, esperado in casos:
        obtido = tier_of(source, title)
        marca = "ok" if obtido == esperado else "DIVERGE"
        rotulo = source + (f"  (título SEO)" if title else "")
        print(f"{rotulo[:32]:32} {obtido:>4}  {esperado:>8}  {marca}")
