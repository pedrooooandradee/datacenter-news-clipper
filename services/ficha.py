# services/ficha.py

"""
The structured record behind each article, and the ratios computed from it.

Two of the three things Pedro asked for live here: operational metrics under any
article that carries quantitative data, and a completeness measure good enough to
decide which of two duplicate articles gets published.

The design in one line: the model only ever COPIES numbers; Python decides what
they mean and whether they may be published.

Four gates, all in Python, all of them able to throw a figure away:

  1. the figure has to exist in the article body        (no invented numbers)
  2. the quoted sentence has to contain it              (no misattributed numbers)
  3. the figure has to appear in the published summary  (DECISOES.md, Q12 —
     the reader must be able to check it in the paragraph above)
  4. both sides of a ratio need the same scope, the same phase and the same
     currency                                           (DECISOES.md, Q2)

Gate 4 is the one that separates the week's good case from its bad one. On the
EVEO story BNamericas gave R$ 300 mi and 6 MW, both of the project, both total —
that pairs. Exame gave US$ 8 bi and 106 MW, both of the Brazilian market as a
whole, inside an article about one data centre in Recife. Without the scope mark
those two produce "R$ 75 mi/MW do data center da EVEO", a number that describes
nothing and looks authoritative.

When nothing pairs, no box is drawn, and the run says at the end how many articles
had figures that did not pair, and why.
"""

import json
import os
from typing import Dict, List, Optional, Tuple

from dotenv import load_dotenv
from openai import OpenAI

try:
    from services.utils import numeros
    from services.utils.projeto import ler_config, modelo
except ImportError:  # running this file directly
    from utils import numeros
    from utils.projeto import ler_config, modelo

load_dotenv()

PROMPT = ler_config("ficha_prompt.txt")

# The median article body is ~3,600 characters; 12,000 covers essentially all of
# them whole, and caps the one long feature that would otherwise cost a multiple.
MAX_BODY = 12000

CAMPOS_VALIDOS = {
    "capex", "capacidade_ti", "capacidade_contratada", "energia_contratada",
    "area_terreno", "area_construida", "consumo_agua", "empregos_diretos",
    "empregos_construcao", "receita", "racks",
}
ESCOPOS_VALIDOS = {"projeto", "empresa", "mercado_brasil", "mercado_global", "hipotetico"}
FASES_VALIDAS = {"total", "fase_1", "fase_2", "fase_3", "anunciado", "em_operacao"}

# Only these two scopes describe something a ratio can be attributed to. Market
# and hypothetical figures are captured and never divided by anything.
ESCOPOS_PARA_RATIO = {"projeto", "empresa"}

ROTULO_CAMPO = {
    "capex": "investimento",
    "capacidade_ti": "capacidade de TI",
    "capacidade_contratada": "capacidade contratada",
    "energia_contratada": "energia contratada",
    "area_terreno": "área do terreno",
    "area_construida": "área construída",
    "consumo_agua": "consumo de água",
    "empregos_diretos": "empregos diretos",
    "empregos_construcao": "empregos na construção",
    "receita": "receita",
    "racks": "racks",
}

ROTULO_FASE = {
    "total": "total", "fase_1": "1ª fase", "fase_2": "2ª fase", "fase_3": "3ª fase",
    "anunciado": "anunciado", "em_operacao": "em operação",
}

# The four ratios approved in propostas/3-ficha-schema.md. Deliberately short:
# each one is a number an infrastructure investor reads without explanation.
#
# All four divide by capacidade_ti and never by energia_contratada, because the
# two are not the same quantity — IT load against total contracted power differ by
# the facility's overhead, and the Brazilian press almost never says which it
# means. The cost is real and is reported: the end-of-run summary counts the
# articles that would have paired if the distinction were ignored.
RATIOS = [
    {"numerador": "capex", "denominador": "capacidade_ti", "sufixo": "/MW", "escala": 1.0},
    {"numerador": "capex", "denominador": "area_construida", "sufixo": "/m²", "escala": 1.0},
    {"numerador": "capex", "denominador": "area_terreno", "sufixo": "/m² de terreno", "escala": 1.0},
    {"numerador": "capacidade_ti", "denominador": "area_construida",
     "sufixo": " kW/m²", "escala": 1000.0, "sem_moeda": True},
]


# A guard against arithmetic that is right and absurd. On the real edition, g1
# reported "investimento de mais de R$ 580 bilhões" for the Caucaia project; with
# 200 MW beside it that divides into R$ 2,9 bilhões por MW, which is three orders
# of magnitude past anything in this industry. The division is correct and the
# number is nonsense, and a clipping that prints it loses the reader's trust in
# every other number on the page.
#
# The bands are deliberately four orders of magnitude wide: they catch absurdity,
# not disagreement. Nothing is dropped in silence — a ratio caught here is printed
# at the end of the run with its inputs, so the figure in the article can be
# checked by hand.
#
# This rule was NOT part of the approved design. It is here because the case
# appeared in real data, and it is the easiest thing in this file to remove.
FAIXAS_PLAUSIVEIS = {
    ("capex", "capacidade_ti"): (1e5, 1e9),
    ("capex", "area_construida"): (1e2, 1e6),
    ("capex", "area_terreno"): (1e1, 1e6),
    ("capacidade_ti", "area_construida"): (0.01, 100.0),
}


def _client() -> OpenAI:
    return OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def conferir_resumo(summary: str, body: str) -> List[str]:
    """
    Figures the published paragraph contains and the article does not.

    This is the same check the record gets, pointed at the text the reader
    actually sees. It found the failure that motivated it: the CNN opinion piece
    of 17/09 contains no figures at all, and the summary sent to investors
    reported "R$ 30 bilhões até 2025", "170 GW" installed and "200 GW" of demand.
    All three were invented.

    Nothing is deleted here. A parser that misses an unusual wording would
    otherwise destroy a good article; the finding is printed with the URL so a
    person can look.
    """
    if not summary or not body:
        return []
    return [
        quantia["texto"]
        for quantia in numeros.quantias_no_texto(summary)
        if not numeros.aparece_no_texto(quantia, body)
    ]


# ─────────────────────────────────────────────────────────────────────
# Extraction
# ─────────────────────────────────────────────────────────────────────

def extrair_ficha(item: Dict, model: Optional[str] = None) -> Optional[Dict]:
    """
    Ask the model to copy the article's figures into a structured record.

    Returns None when the call fails, so the caller can report it rather than
    letting one bad response end a run that has already been paid for.
    """
    body = (item.get("body") or "")[:MAX_BODY]
    if not body:
        return None

    payload = {
        "titulo": item.get("title", ""),
        "veiculo": item.get("source", ""),
        "resumo": item.get("summary", ""),
        "texto": body,
    }

    try:
        response = _client().chat.completions.create(
            model=model or modelo("ficha"),
            temperature=0.0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": PROMPT},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"⚠️  Ficha falhou em {item.get('url', '?')[:70]} ({type(e).__name__}: {e})")
        return None


# ─────────────────────────────────────────────────────────────────────
# Validation — every figure is checked against the text, in Python
# ─────────────────────────────────────────────────────────────────────

def validar_valores(valores: List[Dict], body: str, summary: str) -> Tuple[List[Dict], List[str]]:
    """
    Keep only the figures that survive every check, and say why the others fell.

    The checks are ordered by how bad the failure is. A figure that is not in the
    body at all is the model inventing; a figure whose quoted sentence does not
    contain it is the model attributing a real number to the wrong fact; a figure
    absent from the summary is honest but unpublishable as a ratio, because the
    reader cannot verify it in the paragraph above.
    """
    validos: List[Dict] = []
    rejeitados: List[str] = []

    for bruto in valores or []:
        if not isinstance(bruto, dict):
            continue

        campo = str(bruto.get("campo", "")).strip().lower()
        rotulo = f"{campo or '?'}={bruto.get('valor')!r}"

        if campo not in CAMPOS_VALIDOS:
            rejeitados.append(f"{rotulo}: campo fora da lista")
            continue

        escopo = str(bruto.get("escopo", "")).strip().lower()
        if escopo not in ESCOPOS_VALIDOS:
            rejeitados.append(f"{rotulo}: escopo {escopo!r} fora da lista")
            continue

        fase = str(bruto.get("fase", "")).strip().lower() or "total"
        if fase not in FASES_VALIDAS:
            rejeitados.append(f"{rotulo}: fase {fase!r} fora da lista")
            continue

        unidade, moeda = _separar_moeda(
            str(bruto.get("unidade", "") or ""), str(bruto.get("moeda", "") or "")
        )
        quantia = numeros.normalizar(bruto.get("valor"), unidade=unidade, moeda=moeda)
        if quantia is None:
            rejeitados.append(f"{rotulo}: valor não é número")
            continue

        no_corpo = numeros.aparece_no_texto(quantia, body)
        if not no_corpo:
            rejeitados.append(f"{rotulo}: NÃO EXISTE no corpo da matéria")
            continue

        frase = str(bruto.get("fonte_frase", "") or "").strip()
        if not numeros.aparece_no_texto(quantia, frase):
            rejeitados.append(f"{rotulo}: a frase citada não contém o número")
            continue

        no_resumo = numeros.aparece_no_texto(quantia, summary)

        validos.append({
            "campo": campo,
            "valor": float(bruto.get("valor")),
            "moeda": moeda,
            "unidade": unidade,
            "escopo": escopo,
            "fase": fase,
            "fonte_frase": frase,
            "no_corpo": no_corpo,
            "no_resumo": bool(no_resumo),
            "texto_no_resumo": no_resumo or "",
            "_quantia": quantia,
        })

    return validos, rejeitados


# Currency written where the unit belongs. The model does it often enough that
# "R$ 5,2 bi" was coming out as "5.200.000.000 BRL" in the box.
_MOEDAS_CONHECIDAS = {"BRL", "USD", "EUR", "GBP", "CHF", "R$", "US$"}

# What the reader needs to know about a reported indicator. A figure the
# government offered as an illustration must not read like a commitment.
ROTULO_ESCOPO = {
    "mercado_brasil": "mercado brasileiro",
    "mercado_global": "mercado global",
    "hipotetico": "estimativa",
}


def _separar_moeda(unidade: str, moeda: str) -> Tuple[str, str]:
    """Move a currency code out of the unit field, where it does not belong."""
    unidade, moeda = (unidade or "").strip(), (moeda or "").strip().upper()
    if not moeda and unidade.upper() in _MOEDAS_CONHECIDAS:
        moeda = {"R$": "BRL", "US$": "USD"}.get(unidade, unidade.upper())
        unidade = ""
    return unidade, moeda


def validar_kpis(kpis: List[Dict], body: str) -> List[Dict]:
    """
    Keep the reported indicators that are really in the article.

    These are never divided by anything (DECISOES.md, Q19): they are copied with
    the sentence they came from, and that is all.
    """
    validos: List[Dict] = []
    for bruto in kpis or []:
        if not isinstance(bruto, dict):
            continue
        nome = str(bruto.get("nome", "") or "").strip()
        unidade, moeda = _separar_moeda(
            str(bruto.get("unidade", "") or ""), str(bruto.get("moeda", "") or "")
        )
        quantia = numeros.normalizar(bruto.get("valor"), unidade=unidade, moeda=moeda)
        if not nome or quantia is None:
            continue
        if not numeros.aparece_no_texto(quantia, body):
            continue
        escopo = str(bruto.get("escopo", "") or "").strip().lower()
        validos.append({
            "nome": nome,
            "valor": float(bruto.get("valor")),
            "unidade": unidade,
            "escopo": escopo,
            "escopo_rotulo": ROTULO_ESCOPO.get(escopo, ""),
            "fonte_frase": str(bruto.get("fonte_frase", "") or "").strip(),
            "texto": numeros.formata_quantia(quantia),
        })
    return validos


# ─────────────────────────────────────────────────────────────────────
# Ratios
# ─────────────────────────────────────────────────────────────────────

def _indexar(valores: List[Dict]) -> Dict[Tuple[str, str, str], List[Dict]]:
    indice: Dict[Tuple[str, str, str], List[Dict]] = {}
    for v in valores:
        indice.setdefault((v["campo"], v["escopo"], v["fase"]), []).append(v)
    return indice


def calcular_ratios(valores: List[Dict]) -> Tuple[List[Dict], List[str]]:
    """
    Compute the ratios whose two inputs match on scope, phase and currency.

    Returns the ratios and, separately, the reasons the near misses did not make
    it. The second list is the point of the whole exercise being explicit: an
    empty metrics box with no explanation reads as "this article had no numbers",
    which is usually false.
    """
    ratios: List[Dict] = []
    quase: List[str] = []
    indice = _indexar(valores)

    for regra in RATIOS:
        num_campo, den_campo = regra["numerador"], regra["denominador"]

        for (campo, escopo, fase), entradas in sorted(indice.items()):
            if campo != num_campo or escopo not in ESCOPOS_PARA_RATIO:
                continue
            denominadores = indice.get((den_campo, escopo, fase), [])
            if not denominadores:
                continue

            # More than one figure for the same field, scope and phase is an
            # ambiguity the code must not resolve by guessing.
            if len(entradas) > 1 or len(denominadores) > 1:
                quase.append(
                    f"{num_campo}/{den_campo} ({escopo}, {fase}): "
                    f"mais de um valor para o mesmo campo, ambíguo"
                )
                continue

            numerador, denominador = entradas[0], denominadores[0]

            if not numerador["no_resumo"] or not denominador["no_resumo"]:
                faltando = [
                    ROTULO_CAMPO.get(v["campo"], v["campo"])
                    for v in (numerador, denominador) if not v["no_resumo"]
                ]
                quase.append(
                    f"{num_campo}/{den_campo} ({escopo}, {fase}): "
                    f"{', '.join(faltando)} não aparece no resumo"
                )
                continue

            if denominador["_quantia"]["valor"] == 0:
                continue

            resultado = (numerador["_quantia"]["valor"] / denominador["_quantia"]["valor"]) \
                * regra.get("escala", 1.0)

            faixa = FAIXAS_PLAUSIVEIS.get((num_campo, den_campo))
            if faixa and not (faixa[0] <= abs(resultado) <= faixa[1]):
                quase.append(
                    f"{num_campo}/{den_campo} ({escopo}, {fase}): conta dá "
                    f"{numeros.formata_quantia(numerador['_quantia'])} ÷ "
                    f"{numeros.formata_quantia(denominador['_quantia'])}, fora de "
                    f"qualquer ordem de grandeza do setor — confira o número na matéria"
                )
                continue

            if regra.get("sem_moeda"):
                texto = f"{numeros.numero_br(resultado, casas=2)}{regra['sufixo']}"
            else:
                if numerador["moeda"] != numerador["_quantia"]["unidade"]:
                    continue
                texto = numeros.formata_moeda(resultado, numerador["moeda"]) + regra["sufixo"]

            ratios.append({
                "texto": texto,
                "numerador": numeros.formata_quantia(numerador["_quantia"]),
                "denominador": numeros.formata_quantia(denominador["_quantia"]),
                "numerador_no_texto": numerador["texto_no_resumo"],
                "denominador_no_texto": denominador["texto_no_resumo"],
                "escopo": escopo,
                "fase": ROTULO_FASE.get(fase, fase),
            })

    return ratios, quase


def _quase_por_incompatibilidade(valores: List[Dict]) -> List[str]:
    """
    Explain figures that could have been a ratio but sit on different marks.

    Includes the case the design deliberately refuses: capex together with MW that
    the article never called IT load. Counting it is how the decision stays
    visible instead of silently costing metrics every week.
    """
    motivos: List[str] = []
    por_campo: Dict[str, List[Dict]] = {}
    for v in valores:
        por_campo.setdefault(v["campo"], []).append(v)

    if "capex" not in por_campo:
        return motivos

    for capex in por_campo["capex"]:
        for outro_campo in ("energia_contratada", "capacidade_contratada"):
            for outro in por_campo.get(outro_campo, []):
                if outro["escopo"] == capex["escopo"] and outro["fase"] == capex["fase"] \
                        and capex["escopo"] in ESCOPOS_PARA_RATIO:
                    motivos.append(
                        f"capex + {outro_campo}: parearia, mas a matéria não diz que "
                        f"os MW são de TI (regra da proposta 3)"
                    )
        for capacidade in por_campo.get("capacidade_ti", []):
            if "hipotetico" in (capex["escopo"], capacidade["escopo"]):
                continue
            if capacidade["escopo"] != capex["escopo"]:
                motivos.append(
                    f"capex ({capex['escopo']}) + capacidade_ti ({capacidade['escopo']}): "
                    f"escopos diferentes"
                )
            elif capacidade["fase"] != capex["fase"]:
                motivos.append(
                    f"capex ({capex['fase']}) + capacidade_ti ({capacidade['fase']}): "
                    f"fases diferentes"
                )
    return motivos


# ─────────────────────────────────────────────────────────────────────
# Completeness, for choosing between duplicates
# ─────────────────────────────────────────────────────────────────────

def completude(item: Dict) -> int:
    """
    How much this article says about its own subject, counted from the record.

    Replaces the earlier proxy, which counted figures in the summary and
    subtracted the ones inside market-framed sentences. The record answers the
    same question directly and without a heuristic: figures marked `projeto` or
    `empresa` are about the subject, everything else is context.

    Scope marks are what make this safe. On the EVEO cluster the Exame piece
    carried six figures of which four were about the Brazilian market; here those
    four score nothing, and BNamericas wins on the three that describe the site.
    """
    ficha = item.get("ficha") or {}
    valores = ficha.get("valores") or []
    pontos = sum(1 for v in valores if v.get("escopo") in ESCOPOS_PARA_RATIO)
    projeto = ficha.get("projeto") or {}
    pontos += sum(1 for chave in ("empresa", "local", "tipo", "previsao_operacao")
                  if str(projeto.get(chave, "")).strip())
    return pontos


# ─────────────────────────────────────────────────────────────────────
# Pipeline entry point
# ─────────────────────────────────────────────────────────────────────

def add_fichas(items: List[Dict], model: Optional[str] = None) -> List[Dict]:
    """
    Extract a record for every article, compute its ratios, and report out loud.

    Nothing here removes an article. The worst case is an article with no record,
    which keeps its summary and simply gets no metrics box.
    """
    print(f"Extraindo ficha de {len(items)} notícias...")

    sem_ficha: List[str] = []
    inventados: List[str] = []
    resumos_suspeitos: List[str] = []
    com_ratio = 0
    quase_total: List[str] = []

    for i, item in enumerate(items, 1):
        summary = item.get("summary", "") or ""
        body = item.get("body", "") or ""

        # Runs before anything else, and regardless of whether the record itself
        # succeeds: a figure in the published paragraph that is not in the article
        # is the most expensive defect this program can produce.
        nao_conferidos = conferir_resumo(summary, body)
        if nao_conferidos:
            item["numeros_nao_conferidos"] = nao_conferidos
            resumos_suspeitos.append(
                f"{item.get('source', '?')} — {item.get('title', '')[:50]}\n"
                f"       não achei no texto: {', '.join(nao_conferidos)}\n"
                f"       {item.get('url', '')}"
            )

        bruto = extrair_ficha(item, model=model)

        if bruto is None:
            sem_ficha.append(f"{item.get('source', '?')} — {item.get('title', '')[:55]}")
            item["ficha"] = {}
            item["ficha_failed"] = True
            continue

        valores, rejeitados = validar_valores(bruto.get("valores"), body, summary)
        kpis = validar_kpis(bruto.get("kpis_reportados"), body)
        ratios, quase = calcular_ratios(valores)
        quase += _quase_por_incompatibilidade(valores)

        projeto = bruto.get("projeto") or {}
        item["ficha"] = {
            "projeto": {
                chave: str(projeto.get(chave, "") or "").strip()
                for chave in ("empresa", "empresa_grupo", "local", "tipo", "previsao_operacao")
            },
            "valores": [
                {k: v for k, v in valor.items() if k != "_quantia"} for valor in valores
            ],
            "kpis_reportados": kpis,
            "ratios": ratios,
            "nao_pareou": sorted(set(quase)),
        }
        item["empresas_citadas"] = [
            str(nome).strip() for nome in (bruto.get("empresas_citadas") or [])
            if str(nome).strip()
        ]

        if ratios:
            com_ratio += 1
        if quase and not ratios:
            quase_total.extend(
                f"{item.get('source', '?')} — {motivo}" for motivo in sorted(set(quase))
            )
        for motivo in rejeitados:
            if "NÃO EXISTE" in motivo or "não contém" in motivo:
                inventados.append(
                    f"{item.get('source', '?')} — {item.get('title', '')[:45]}: {motivo}"
                )

        if i % 10 == 0:
            print(f"   {i}/{len(items)}")

    # DECISOES.md, Q24: nothing is dropped in silence.
    print(f"{com_ratio} notícias com indicador publicável; "
          f"{len(items) - com_ratio} sem.")
    if resumos_suspeitos:
        print()
        print(f"🚨 {len(resumos_suspeitos)} RESUMOS CITAM NÚMERO QUE NÃO ESTÁ NA MATÉRIA.")
        print(f"   Confira cada um antes de enviar. O resumo NÃO foi alterado — pode ser "
              f"o leitor de números errando uma grafia incomum, e pode ser o modelo "
              f"inventando, como aconteceu na edição de 21/09.")
        for entrada in resumos_suspeitos:
            print(f"     - {entrada}")
        print()
    if inventados:
        print(f"⚠️  {len(inventados)} números foram DESCARTADOS por não existirem no texto "
              f"(o modelo inventou ou trocou de lugar):")
        for entrada in inventados[:20]:
            print(f"     - {entrada}")
        if len(inventados) > 20:
            print(f"     ... e mais {len(inventados) - 20}")
    if quase_total:
        print(f"⚠️  {len(quase_total)} notícias tinham número mas não pareou:")
        for entrada in sorted(set(quase_total))[:20]:
            print(f"     - {entrada}")
        if len(set(quase_total)) > 20:
            print(f"     ... e mais {len(set(quase_total)) - 20}")
    if sem_ficha:
        print(f"⚠️  {len(sem_ficha)} notícias ficaram sem ficha (falha na chamada), "
              f"MANTIDAS sem caixa de métricas:")
        for entrada in sem_ficha:
            print(f"     - {entrada}")

    return items


if __name__ == "__main__":
    # Offline check of the rules. No API call: the record is written by hand so the
    # gates can be exercised one at a time.
    corpo = ("A Atlantic Data Centers investirá R$ 300 milhões em três fases no Recife. "
             "A primeira fase recebeu R$ 41 milhões. A capacidade de TI projetada é de "
             "6 MW de TI em 10 mil m² de área construída. A vacância do setor no Brasil "
             "está em 4%. Um data center de 100 MW poderia gerar R$ 25 bilhões.")
    resumo = ("A Atlantic Data Centers investe R$ 300 milhões em três fases no Recife, "
              "com 6 MW de TI e 10 mil m² de área construída; a vacância do setor no "
              "Brasil está em 4%.")

    valores_brutos = [
        {"campo": "capex", "valor": 300000000, "moeda": "BRL", "escopo": "projeto",
         "fase": "total", "fonte_frase": "investirá R$ 300 milhões em três fases"},
        {"campo": "capacidade_ti", "valor": 6, "unidade": "MW", "escopo": "projeto",
         "fase": "total", "fonte_frase": "capacidade de TI projetada é de 6 MW de TI"},
        {"campo": "area_construida", "valor": 10000, "unidade": "m²", "escopo": "projeto",
         "fase": "total", "fonte_frase": "10 mil m² de área construída"},
        {"campo": "capex", "valor": 41000000, "moeda": "BRL", "escopo": "projeto",
         "fase": "fase_1", "fonte_frase": "A primeira fase recebeu R$ 41 milhões"},
        {"campo": "capex", "valor": 25000000000, "moeda": "BRL", "escopo": "hipotetico",
         "fase": "total", "fonte_frase": "poderia gerar R$ 25 bilhões"},
        {"campo": "capex", "valor": 999000000, "moeda": "BRL", "escopo": "projeto",
         "fase": "total", "fonte_frase": "investimento de R$ 999 milhões"},
        {"campo": "capex", "valor": 300000000, "moeda": "BRL", "escopo": "projeto",
         "fase": "total", "fonte_frase": "a vacância do setor está em 4%"},
    ]

    validos, rejeitados = validar_valores(valores_brutos, corpo, resumo)
    print("=== portões de validação ===")
    for v in validos:
        marca = "no resumo" if v["no_resumo"] else "só no corpo"
        print(f"  ok       {v['campo']:18} {v['escopo']:12} {v['fase']:8} ({marca})")
    for motivo in rejeitados:
        print(f"  RECUSADO {motivo}")

    print("\n=== ratios ===")
    ratios, quase = calcular_ratios(validos)
    for r in ratios:
        print(f"  {r['numerador']} ÷ {r['denominador']} = {r['texto']}  ({r['fase']})")
    for motivo in quase + _quase_por_incompatibilidade(validos):
        print(f"  não pareou: {motivo}")

    print("\n=== completude, para a disputa de duplicatas ===")
    print("  ", completude({"ficha": {"valores": validos,
                                      "projeto": {"empresa": "Atlantic", "local": "Recife"}}}))
