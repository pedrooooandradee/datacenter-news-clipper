# services/deduplicator.py

"""
Removing duplicate coverage, in two stages.

The old version ran a single LLM pass after everything had been scraped and
summarised, and eleven duplicates still reached the PDF. Three separate defects:

1. It asked the model to echo every article back with title, summary and source,
   under max_tokens=4096. A batch of fifteen Portuguese summaries overflows that,
   the JSON arrived truncated, parsing failed, and the code kept everything.
   This version asks only for lists of ids — sixty articles fit in one call.
2. Above 25 items it split into batches of 15 that overlapped by 3, so two
   articles in distant batches were never compared. The three articles about the
   US House sat at positions 16, 21 and 33.
3. It kept whichever article came first, not the best one. select_best_from_group
   existed but was never called, and would have failed anyway because pubDate had
   already been formatted as "18 Set".

The stages now are:

  cluster_by_title    before scraping. Embeddings over titles only, with a
                      deliberately high threshold. Cheap, and it saves scraping
                      and summarising the copies.
  confirm_groups      after summarising. An LLM decides which candidates really
                      are the same story, and finds the ones the titles missed.

Measured on the 53 real articles of the 21/09/2026 edition: for true duplicates,
adding the summary RAISES the cosine (EVEO 0.799 -> 0.899, MP Campinas 0.673 ->
0.819); for articles that merely share a topic it LOWERS it (0.722 -> 0.667).
That is why the cheap stage uses titles and the confirming stage uses summaries.
"""

import os
import json
import math
import re
from typing import List, Dict, Optional

from dotenv import load_dotenv
from openai import OpenAI

try:
    from services.utils.fontes import tier_of, can_win_group
    from services.utils.projeto import modelo
    from services.ficha import completude as completude_da_ficha
except ImportError:
    from utils.fontes import tier_of, can_win_group
    from utils.projeto import modelo
    from ficha import completude as completude_da_ficha

load_dotenv()

EMBEDDING_MODEL = modelo("embedding")

# Calibrated on the 53 real articles. The true pairs run down to 0.768 and the
# first false pair sits at 0.722 — "Incentivo a data centers amplia infraestrutura"
# against "Data centers: energia, água e o impacto real da infraestrutura", which
# share a subject and no facts. 0.75 sits in that gap with room on both sides.
#
# Erring high is deliberate: merging before the scrape decides which article is
# never fetched. What the titles miss, the summaries catch in the second stage.
# One week of data is one week of data — re-check against the archive once a few
# editions have accumulated (DECISOES.md, Q21).
TITLE_THRESHOLD = 0.75


def _client() -> OpenAI:
    return OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def _cosine(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    return dot / (na * nb) if na and nb else 0.0


# ─────────────────────────────────────────────────────────────────────
# Stage 1 — cluster by title, before scraping
# ─────────────────────────────────────────────────────────────────────

def cluster_by_title(items: List[Dict], threshold: float = TITLE_THRESHOLD) -> List[List[int]]:
    """
    Group items whose titles are near-identical.

    Returns a list of groups of indices, singletons included, so the caller can
    treat the output as a partition of the input.
    """
    if len(items) <= 1:
        return [[i] for i in range(len(items))]

    titles = [item.get("title", "") for item in items]
    try:
        response = _client().embeddings.create(model=EMBEDDING_MODEL, input=titles)
        vectors = [row.embedding for row in response.data]
    except Exception as e:
        print(f"⚠️  Não consegui gerar embeddings ({type(e).__name__}); "
              f"nenhum agrupamento prévio será feito.")
        return [[i] for i in range(len(items))]

    parent = list(range(len(items)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[max(ri, rj)] = min(ri, rj)

    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            if _cosine(vectors[i], vectors[j]) >= threshold:
                union(i, j)

    grouped: Dict[int, List[int]] = {}
    for i in range(len(items)):
        grouped.setdefault(find(i), []).append(i)
    return list(grouped.values())


# ─────────────────────────────────────────────────────────────────────
# Stage 2 — confirm with the LLM, over the summaries
# ─────────────────────────────────────────────────────────────────────

CONFIRM_PROMPT = """Você identifica cobertura duplicada em notícias de um clipping do setor de data centers.

Duas notícias são DUPLICATAS quando relatam o MESMO FATO:
- mesmo anúncio de investimento (mesma empresa, mesmo valor, mesmo local)
- mesma decisão de governo, mesma lei, mesma sanção
- mesmo estudo, mesmo relatório, mesmos números
- mesmo processo, mesma investigação, mesmo evento

Também conte como duplicata a COBERTURA REDUNDANTE: notícia que repete os fatos de
outra do mesmo grupo sem trazer nenhum fato novo, mesmo com enfoque diferente.

NÃO são duplicatas:
- empresas diferentes, mesmo com valores parecidos
- decisões de governo diferentes, mesmo sobre o mesmo tema
- análise geral do setor contra anúncio específico
- reação ou entrevista que acrescenta fato novo (número, prazo, decisão) à notícia original

EXEMPLOS:
- "Lula sanciona incentivos para data centers" + "Presidente sanciona ReData" = DUPLICATA
- "Câmara dos EUA aprova projeto sobre data centers" (dois veículos) = DUPLICATA
- "EVEO terá data center em Recife" + "Eveo escolhe data center da Atlantic" = DUPLICATA
- "ReData vira lei" + "CEO da Scala diz que ReData não destrava projetos" = NÃO é duplicata (a entrevista traz avaliação nova)
- "EPE alerta para duplicidade de pedidos" + "Aneel autoriza conexão da Ascenty" = NÃO é duplicata

Responda SOMENTE com um objeto JSON, no formato:
{"grupos": [[3, 17, 29], [8, 12]]}

Cada lista interna é um grupo de ids que cobrem o mesmo fato. Inclua apenas grupos
com dois ou mais ids. Não repita um id em mais de um grupo. Não escreva mais nada.

REGRA QUE VENCE TODAS AS OUTRAS: lugar e jurisdição diferentes são fatos
diferentes. Uma lei da Califórnia e uma regra do Rio Grande do Norte NÃO são
duplicatas, ainda que as duas regulem data centers. O mesmo vale para projetos em
cidades diferentes, decisões de órgãos diferentes e empresas diferentes.

Antes de juntar duas notícias, pergunte: elas relatam o MESMO ATO, do MESMO ator,
no MESMO lugar, na MESMA data? Se a resposta for não em qualquer um dos quatro,
não são duplicatas — são notícias do mesmo assunto, e assunto não é fato.

Grupo grande é suspeito. Um grupo com mais de 4 ids só se justifica quando é um
único ato muito coberto, como uma sanção presidencial. Se você está juntando mais
de 4 porque todas falam do mesmo TEMA, você errou."""


def confirm_groups(items: List[Dict], model: Optional[str] = None) -> List[List[int]]:
    """
    Ask the model which articles cover the same story, over titles and summaries.

    Only ids come back. The old prompt asked for the whole article echoed back,
    overflowed the token limit, and every duplicate survived the failed parse.
    """
    if len(items) <= 1:
        return []

    # How much of the summary the confirming model gets to read.
    #
    # This is a calibration, not a formatting choice. The whole two-stage design
    # rests on the summary separating a duplicate from a neighbour on the same
    # topic (EVEO 0.799 -> 0.899, MP Campinas 0.673 -> 0.819, common-topic pair
    # 0.722 -> 0.667). Cutting it short moves this stage back towards stage one,
    # which has already seen the title.
    #
    # Measured on the 22 set 2026 edition: median summary is 687 characters and
    # 28 of 40 articles are longer than 600 — so in most cases the model judges
    # on the first two thirds. Raising it buys precision and costs tokens;
    # lowering it is moving the calibration, not saving money.
    RESUMO_PARA_CONFIRMAR = 600

    payload = [
        {
            "id": i,
            "titulo": item.get("title", ""),
            "fonte": item.get("source", ""),
            "resumo": (item.get("summary", "") or "")[:RESUMO_PARA_CONFIRMAR],
        }
        for i, item in enumerate(items)
    ]

    try:
        response = _client().chat.completions.create(
            model=model or modelo("dedup"),
            temperature=0.0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": CONFIRM_PROMPT},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
        )
        parsed = json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"⚠️  A confirmação de duplicatas falhou ({type(e).__name__}: {e}). "
              f"Nenhum grupo foi formado — nenhuma notícia foi perdida.")
        return []

    groups: List[List[int]] = []
    seen: set = set()
    for group in parsed.get("grupos", []):
        if not isinstance(group, list):
            continue
        valid = [i for i in group
                 if isinstance(i, int) and 0 <= i < len(items) and i not in seen]
        if len(valid) >= 2:
            groups.append(valid)
            seen.update(valid)
    return groups


def prune_clusters_before_scrape(items: List[Dict]) -> List[Dict]:
    """
    Group near-identical titles and mark all but the two best-sourced as reserve.

    Two, not one: the article that wins on source is not always the one carrying
    the project's figures. In the EVEO cluster the best-sourced piece has no capex
    and no capacity, while the one that does — BNamericas — would have been thrown
    away by a rule that kept a single winner. Keeping two lets the real contest
    happen later, over what the articles say.

    The rest are MARKED, not removed. They used to be deleted here, before anyone
    knew whether the two chosen ones could even be fetched — and the two best by
    tier are exactly the ones most likely to be behind Cloudflare or a paywall. A
    week where the sanction was covered by two tier-1 outlets that both blocked
    and one tier-3 outlet that loaded would have lost the story entirely, and the
    third copy was already in hand. The measured saving of not fetching them was
    one article in fifty-three, so holding them costs almost nothing.
    """
    if len(items) <= 1:
        return items

    groups = cluster_by_title(items)
    multi = [g for g in groups if len(g) > 1]
    if not multi:
        print(f"Agrupamento por título: nenhum par acima de {TITLE_THRESHOLD}.")
        return items

    reservas = 0
    for numero, group in enumerate(multi, 1):
        ranked = sorted(group, key=lambda i: (tier_of(items[i].get("source", "")), i))
        keep, reserva = ranked[:2], ranked[2:]

        for posicao, i in enumerate(ranked):
            items[i]["_grupo_id"] = numero
            items[i]["_grupo_ordem"] = posicao
        for i in reserva:
            items[i]["_reserva"] = True
            reservas += 1

        print(f"  Grupo de {len(group)} títulos quase idênticos: "
              f"coleta {', '.join(items[i].get('source', '?') for i in keep)}"
              + (f" · reserva {', '.join(items[i].get('source', '?') for i in reserva)}"
                 if reserva else ""))

    print(f"Agrupamento por título: {len(multi)} grupos, "
          f"{reservas} cópias guardadas como reserva (não serão coletadas "
          f"a menos que as escolhidas falhem)")
    return items


def promover_reservas(items: List[Dict]) -> List[Dict]:
    """
    Wake up a group's reserve when every article chosen for it came back empty.

    Returns the items that now need fetching, in the caller's list, already
    unmarked. An empty list is the normal case.
    """
    grupos: Dict[int, List[Dict]] = {}
    for item in items:
        if item.get("_grupo_id"):
            grupos.setdefault(item["_grupo_id"], []).append(item)

    promovidos: List[Dict] = []
    for numero, membros in sorted(grupos.items()):
        escolhidos = [m for m in membros if not m.get("_reserva")]
        if any(m.get("body") for m in escolhidos):
            continue
        reservas = sorted((m for m in membros if m.get("_reserva")),
                          key=lambda m: m.get("_grupo_ordem", 99))
        if not reservas:
            continue
        melhor = reservas[0]
        melhor.pop("_reserva", None)
        promovidos.append(melhor)
        print(f"↩️  Grupo {numero}: as escolhidas não carregaram "
              f"({', '.join(m.get('source', '?') for m in escolhidos)}); "
              f"coletando a reserva {melhor.get('source', '?')}")

    return promovidos


def descartar_reservas(items: List[Dict]) -> List[Dict]:
    """
    Drop the copies that were never needed, remembering the outlets by name.

    The names land on the surviving members of the group, so the "também
    noticiado por" line still credits every outlet that covered the story.
    """
    restantes, descartadas = [], 0
    por_grupo: Dict[int, List[str]] = {}

    for item in items:
        if item.get("_reserva"):
            por_grupo.setdefault(item.get("_grupo_id"), []).append(
                item.get("source", "?"))
            descartadas += 1
        else:
            restantes.append(item)

    for item in restantes:
        nomes = por_grupo.get(item.get("_grupo_id"))
        if not nomes:
            continue
        existentes = set(item.get("_fontes_do_grupo") or [])
        item["_fontes_do_grupo"] = sorted(
            (existentes | set(nomes)) - {item.get("source", "")})

    if descartadas:
        print(f"{descartadas} cópias de reserva dispensadas (as escolhidas do grupo "
              f"foram coletadas); os veículos seguem nomeados no clipping.")
    return restantes


# ─────────────────────────────────────────────────────────────────────
# Choosing which article survives
# ─────────────────────────────────────────────────────────────────────

_NUMBER = re.compile(
    r'(?:R\$|US\$|CHF|€)\s?[\d\.,]+\s*(?:mil|milh[õo]es|bilh[õo]es|tri)?'
    r'|[\d\.,]+\s*(?:MW|GW|kW|kV|m²|mil m²|hectares?|%)',
    re.I,
)

# Sentences framed around the market rather than the company. Figures inside them
# describe something else, and counting them rewards the wrong article: the Exame
# piece on EVEO's Recife site carried six figures, four of which were about the
# Brazilian market as a whole (106 MW added, US$ 8bn, 4% vacancy).
_MARKET_FRAME = re.compile(
    r'\bo Brasil\b|\bno pa[ií]s\b|\bo setor\b|\bmercado\b|Am[ée]rica Latina|vac[âa]ncia',
    re.I,
)


def subject_figures(summary: str) -> int:
    """
    Count the figures that describe the article's own subject.

    Measured on the EVEO cluster: BNamericas 9, Exame 2, Data Center Dynamics 2 —
    and BNamericas is the article carrying the project's capex, its capacity and
    the phase they belong to.
    """
    if not summary:
        return 0
    all_figures = {m.group(0).strip() for m in _NUMBER.finditer(summary)}
    market_figures: set = set()
    for sentence in re.split(r'(?<=[.;])\s+', summary):
        if _MARKET_FRAME.search(sentence):
            market_figures |= {m.group(0).strip() for m in _NUMBER.finditer(sentence)}
    return len(all_figures - market_figures)


def completeness(item: Dict) -> int:
    """
    How much an article says about its own subject.

    Reads the structured record when there is one (DECISOES.md, Q14): figures
    marked `projeto` or `empresa` describe the subject, market figures do not, and
    the scope mark answers that directly instead of inferring it from wording.

    Falls back to counting figures in the summary, discounting those inside
    market-framed sentences, when there is no record — which happens when dedup is
    re-run over a cache produced before records existed. The fallback is the
    weaker measure, which is precisely why it is only the fallback.
    """
    if item.get("ficha"):
        return completude_da_ficha(item)
    return subject_figures(item.get("summary", ""))


def select_survivor(items: List[Dict], group: List[int]) -> int:
    """
    Pick which article of a group is published.

    Tier is a gate, not a tiebreaker. On the Campinas investigation the deputy's
    campaign site carried four figures against one in the G1 piece, so completeness
    alone would have published the campaign site. Tier 3 outlets are excluded from
    the contest unless the whole group is tier 3.

    Among the eligible, the winner is the most complete. When that genuinely ties,
    the better-sourced article wins, and length decides only after that. Length is
    the weak measure that would have picked the Exame piece over BNamericas in the
    EVEO cluster; it must never beat a stronger outlet.
    """
    # can_win_group, não `tier_of(...) <= 2` escrito à mão. A regra existia nos
    # dois lugares: a função, que os testes cobrem, e esta cópia, que era a que
    # rodava. Apertar o critério na função deixava os 66 testes verdes e o
    # programa inalterado; apertá-lo aqui mudava o programa e deixava o teste da
    # função verde do mesmo jeito. Teste que passa sobre código que ninguém
    # executa vale menos que teste nenhum, porque dá confiança falsa.
    eligible = [i for i in group if can_win_group(items[i].get("source", ""))]
    if not eligible:
        eligible = list(group)

    return max(
        eligible,
        key=lambda i: (
            completeness(items[i]),
            -tier_of(items[i].get("source", "")),
            len(items[i].get("summary", "") or ""),
        ),
    )


# ─────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────

def deduplicate_by_summary(items: List[Dict]) -> List[Dict]:
    """
    Remove duplicate coverage, keeping a record of what was merged.

    The survivor gains 'tambem_noticiado_por', which becomes the "também noticiado
    por: …" line in the PDF. Fourteen outlets covering the same sanction is
    information for the reader, not noise — and it makes the deduplication
    auditable instead of a black box.

    There used to be a `confidence_threshold=0.7` parameter in this signature,
    left over from the single-pass version. Nothing in the body read it and no
    caller passed it, but it was the most inviting knob in the project: anyone
    trying to make deduplication less aggressive would turn that 0.7 first, pay
    for a full run, see nothing change, and conclude the stage is unpredictable.
    The threshold that exists is TITLE_THRESHOLD, at the top of this file, and
    it only decides which pairs are *shown* to the model. The merge itself is
    the model's call, under CONFIRM_PROMPT.
    """
    if not items or len(items) <= 1:
        return items

    print(f"Procurando cobertura duplicada em {len(items)} notícias...")
    groups = confirm_groups(items)

    if not groups:
        print("Nenhum grupo de duplicatas identificado.")
        return _resgatar_fontes_orfas(items)

    dropped: set = set()
    for group in groups:
        survivor = select_survivor(items, group)
        others = [i for i in group if i != survivor]
        dropped.update(others)

        # Outlets dropped before the scrape are named here too, so the line does
        # not quietly shrink just because a copy never got fetched.
        names = {items[i].get("source", "?") for i in others}
        for i in group:
            names |= set(items[i].get("_fontes_do_grupo", []))
        names.discard(items[survivor].get("source", "?"))
        items[survivor]["tambem_noticiado_por"] = sorted(names)

        for i in others:
            items[i]["duplicate_of"] = items[survivor].get("url", "")

        print(f"  Grupo de {len(group)}: fica {items[survivor].get('source', '?')} "
              f"(tier {tier_of(items[survivor].get('source', ''))}, "
              f"completude {completeness(items[survivor])})")
        for i in others:
            print(f"     sai {items[i].get('source', '?')}: {items[i].get('title', '')[:60]}")

    kept = [item for i, item in enumerate(items) if i not in dropped]
    print(f"{len(items)} -> {len(kept)} notícias ({len(dropped)} duplicatas removidas)")
    return _resgatar_fontes_orfas(kept)


def _resgatar_fontes_orfas(items: List[Dict]) -> List[Dict]:
    """
    Make sure an outlet dropped before the scrape still gets named.

    The title stage drops the third and further copies of a group and records
    their names on the survivors. Those names only became the "também noticiado
    por" line if the LLM stage later confirmed the same group — and when it did
    not, the outlet disappeared from the edition with no trace. That is a silent
    cut (DECISOES.md, Q24), caused by a step whose whole purpose is to keep the
    merge visible.
    """
    resgatadas = 0
    for item in items:
        do_grupo = set(item.get("_fontes_do_grupo") or [])
        if not do_grupo:
            continue
        do_grupo.discard(item.get("source", ""))
        existentes = set(item.get("tambem_noticiado_por") or [])
        if do_grupo - existentes:
            item["tambem_noticiado_por"] = sorted(existentes | do_grupo)
            resgatadas += 1

    if resgatadas:
        print(f"   {resgatadas} notícias recuperaram o nome de veículos descartados "
              f"antes da coleta (o grupo não foi reconfirmado sobre os resumos).")
    return items


if __name__ == "__main__":
    with open("output/clippings.json", "r", encoding="utf-8") as f:
        real = json.load(f)

    print(f"=== {len(real)} notícias reais ===\n")

    print("--- números do sujeito, no cluster EVEO ---")
    for i in (1, 12, 23):
        print(f"  [{i:2}] {real[i]['source'][:18]:20} {subject_figures(real[i]['summary']):2} números")

    print("\n--- sobrevivente por grupo conhecido ---")
    for label, group, expected in [
        ("EVEO/Recife", [1, 12, 23], 12),
        ("ReData sanção", [18, 50], 18),
        ("MP Campinas", [15, 30], 15),
        ("Câmara dos EUA", [21, 26], None),
    ]:
        winner = select_survivor(real, group)
        mark = "" if expected is None else ("  ok" if winner == expected else "  DIVERGE")
        print(f"  {label:16} fica [{winner}] {real[winner]['source'][:22]}{mark}")
