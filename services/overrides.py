# services/overrides.py

"""
Manual corrections that survive the next run.

Until now the manual editing was done straight in output/clippings.json, and the
next execution overwrote it. Every week the same corrections were made again, and
the record of what the pipeline gets wrong — the most valuable thing the process
produces — was destroyed each time.

configs/overrides.json is applied as the last step before the PDF is built, over
whatever the pipeline produced. Rebuilding the PDF reapplies everything.

The file is committed (DECISOES.md, Q15). After a couple of months it is the only
real corpus of cases where the model was wrong, and those cases become the
examples in the classification and deduplication prompts — which today carry
examples written from imagination.

`motivo` is required on anything that removes or rewrites. Without it, in two
months there are forty removed URLs and no idea what the pattern was.

The key is always the FINAL url, the article's own, after Google News's redirect —
never the news.google.com wrapper.
"""

import json
import os
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple

try:
    from services.utils.projeto import caminho_config
    from services.utils.archive import data_da_edicao, DIAS_ENTRE_EDICOES
    from services import empresas
except ImportError:
    from utils.projeto import caminho_config
    from utils.archive import data_da_edicao, DIAS_ENTRE_EDICOES
    import empresas

OVERRIDES_PATH = caminho_config("overrides.json")

BLOCOS_COM_MOTIVO = ("removidas", "categoria", "resumo", "dedup")


class OverridesIlegivel(ValueError):
    """overrides.json exists but cannot be read, so no correction can be applied."""


def carregar(caminho: str = OVERRIDES_PATH) -> Dict:
    """
    Read overrides.json, or return an empty set of blocks if it is not there.

    A file with a syntax error raises OverridesIlegivel. It used to be skipped
    with a warning, and the PDF was built anyway — with none of the week's
    corrections, the usual "PDF gerado" at the end, and the archive overwritten
    with that uncorrected version. A missing comma is the most common mistake in
    hand-edited JSON, so it has to stop the build, not slip past it.
    """
    if not os.path.exists(caminho):
        return {}
    try:
        with open(caminho, "r", encoding="utf-8") as f:
            dados = json.load(f)
    except json.JSONDecodeError as e:
        raise OverridesIlegivel(
            f"{os.path.basename(caminho)} tem um erro de sintaxe na linha "
            f"{e.lineno}, coluna {e.colno} ({e.msg}). Quase sempre é uma vírgula que "
            f"faltou ou sobrou, ou uma aspa sem par, nessa linha ou na de cima."
        ) from e
    return dados if isinstance(dados, dict) else {}


def _dia(valor) -> Optional[date]:
    """The date of a correction, written 2026-09-28 or 28/09/2026."""
    texto = str(valor or "").strip()
    for formato in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(texto, formato).date()
        except ValueError:
            pass
    return None


def _indexar(items: List[Dict]) -> Dict[str, Dict]:
    return {item.get("url", ""): item for item in items}


def aplicar(items: List[Dict], caminho: str = OVERRIDES_PATH) -> Tuple[List[Dict], List[str]]:
    """
    Apply the manual corrections, and report every one of them.

    Returns the corrected list and the lines to print. An override whose URL is
    not in this edition is reported too: an entry that silently matches nothing is
    how the file rots without anyone noticing.
    """
    dados = carregar(caminho)
    if not dados:
        return items, []

    relatorio: List[str] = []
    sem_motivo: List[str] = []
    nao_casou: List[str] = []
    por_url = _indexar(items)

    def exige_motivo(bloco: str, entrada: Dict, rotulo: str) -> None:
        if bloco in BLOCOS_COM_MOTIVO and not str(entrada.get("motivo", "") or "").strip():
            sem_motivo.append(f"{bloco}: {rotulo}")

    # 1) Outlet name. First, because everything below shows the source.
    for entrada in dados.get("fonte_nome") or []:
        url = entrada.get("url", "")
        item = por_url.get(url)
        if not item:
            nao_casou.append((f"fonte_nome: {url[:70]}", entrada.get("data")))
            continue
        antes = item.get("source", "")
        item["source"] = entrada.get("para", antes)
        relatorio.append(f"fonte: {antes!r} → {item['source']!r}")

    # 2) Category.
    for entrada in dados.get("categoria") or []:
        url = entrada.get("url", "")
        item = por_url.get(url)
        if not item:
            nao_casou.append((f"categoria: {url[:70]}", entrada.get("data")))
            continue
        exige_motivo("categoria", entrada, item.get("title", "")[:50])
        antes = item.get("category", "")
        item["category"] = entrada.get("para", antes)
        item["override_categoria"] = True
        relatorio.append(f"categoria: {antes} → {item['category']} "
                         f"({item.get('title', '')[:45]})")

    # 3) Summary rewritten by hand.
    for entrada in dados.get("resumo") or []:
        url = entrada.get("url", "")
        item = por_url.get(url)
        if not item:
            nao_casou.append((f"resumo: {url[:70]}", entrada.get("data")))
            continue
        texto = str(entrada.get("texto", "") or "").strip()
        if not texto:
            continue
        exige_motivo("resumo", entrada, item.get("title", "")[:50])
        item["summary"] = texto
        item["override_resumo"] = True
        # A hand-written summary invalidates the metrics computed from the old
        # one: the ratio rule is that the reader finds both figures in the
        # paragraph above, and the paragraph just changed.
        if item.get("ficha", {}).get("ratios"):
            item["ficha"]["ratios"] = []
            relatorio.append(f"métricas retiradas (resumo reescrito à mão): "
                             f"{item.get('title', '')[:45]}")
        relatorio.append(f"resumo reescrito: {item.get('title', '')[:45]}")

    # 4) Highlights.
    grifadas = {str(url) for url in (dados.get("highlight") or [])}
    for url in grifadas:
        item = por_url.get(url)
        if not item:
            # A highlight that matches nothing harms nobody — it just does not
            # highlight. It never counts as this week's typo.
            nao_casou.append((f"highlight: {url[:70]}", "antiga"))
            continue
        item["highlight"] = True
    if grifadas:
        relatorio.append(f"{len([u for u in grifadas if u in por_url])} notícias grifadas à mão")

    # 5) Duplicate groups the pipeline missed.
    for entrada in dados.get("dedup") or []:
        manter = entrada.get("manter", "")
        principal = por_url.get(manter)
        if not principal:
            nao_casou.append((f"dedup: {manter[:70]}", entrada.get("data")))
            continue
        exige_motivo("dedup", entrada, principal.get("title", "")[:50])
        fundidas = []
        for url in entrada.get("fundir") or []:
            outro = por_url.get(url)
            if not outro:
                nao_casou.append((f"dedup/fundir: {str(url)[:70]}", entrada.get("data")))
                continue
            fundidas.append(outro.get("source", "?"))
            outro["_override_removida"] = True
        if fundidas:
            nomes = set(principal.get("tambem_noticiado_por") or []) | set(fundidas)
            nomes.discard(principal.get("source", ""))
            principal["tambem_noticiado_por"] = sorted(nomes)
            relatorio.append(f"fundidas à mão em {principal.get('source', '?')}: "
                             f"{', '.join(sorted(set(fundidas)))}")

    # 6) Removals. Last, so the blocks above can still name the items they touch.
    removidas = set()
    for entrada in dados.get("removidas") or []:
        url = entrada.get("url", "")
        if url not in por_url:
            nao_casou.append((f"removida: {url[:70]}", entrada.get("data")))
            continue
        exige_motivo("removidas", entrada, por_url[url].get("title", "")[:50])
        removidas.add(url)

    # 7) Company profiles approved by hand — the way out of quarantine (Q3).
    for entrada in dados.get("empresa") or []:
        nome = str(entrada.get("nome", "") or "").strip()
        texto = str(entrada.get("overview", "") or "").strip()
        if not nome or not texto:
            continue
        if not str(entrada.get("aprovado_por", "") or "").strip():
            sem_motivo.append(f"empresa: {nome} (sem 'aprovado_por')")
            continue
        empresas.registrar_perfil(nome, texto, entrada.get("aliases"))
        relatorio.append(f"ficha de empresa aprovada à mão: {nome}")

    final = [
        item for item in items
        if item.get("url") not in removidas and not item.pop("_override_removida", False)
    ]
    if len(final) != len(items):
        relatorio.append(f"{len(items) - len(final)} notícias removidas à mão")

    if sem_motivo:
        relatorio.append(
            f"⚠️  {len(sem_motivo)} correções SEM motivo declarado — o campo 'motivo' é "
            f"o que transforma este arquivo em exemplo para os prompts: "
            + "; ".join(sem_motivo[:5])
        )
    # The file keeps every week's corrections — a removal has to survive the
    # following week, when the same URL can come back. So most entries that
    # match nothing are simply old, and listing them all buried the one that
    # mattered: a correction written THIS week whose URL has a typo, which means
    # the story it was meant to fix is going to the client unfixed.
    #
    # Dates are compared as dates. Compared as text, "05/10/2026" sorted before
    # "2026-10-05" and this week's typo was filed as old. The cut sits a few days
    # before the closing, because `--from` rewrites the closing with the day it
    # is run: a correction dated Monday must still count as this edition's when
    # the PDF is rebuilt on Tuesday.
    fechamento = data_da_edicao()
    corte = (fechamento.date() - timedelta(days=DIAS_ENTRE_EDICOES)) if fechamento else None
    desta_semana, antigas = [], 0
    for texto, data in nao_casou:
        if data == "antiga":
            antigas += 1
            continue
        dia = _dia(data)
        if data and dia is None:
            desta_semana.append(f"{texto}  (data ilegível: {data!r} — use AAAA-MM-DD)")
        elif dia is None or corte is None or dia >= corte:
            desta_semana.append(texto)
        else:
            antigas += 1
    if desta_semana:
        relatorio.append(
            f"⚠️  {len(desta_semana)} correções DESTA edição não bateram com nenhuma "
            f"notícia — confira a URL (e ponha o campo 'data' nas que não têm):"
        )
        relatorio.extend(f"     - {entrada}" for entrada in desta_semana[:15])
        if len(desta_semana) > 15:
            relatorio.append(f"     … e mais {len(desta_semana) - 15}")
    if antigas:
        relatorio.append(f"   ({antigas} correções de edições anteriores não se aplicam "
                         f"a esta — normal)")

    return final, relatorio


def relatar(relatorio: List[str]) -> None:
    if not relatorio:
        return
    print(f"✏️  Correções manuais de configs/overrides.json:")
    for linha in relatorio:
        print(f"   {linha}" if not linha.startswith("     ") else linha)


if __name__ == "__main__":
    import tempfile

    exemplo = {
        "versao": 1,
        "removidas": [{"url": "https://ex.com/a", "motivo": "opinião sem fato novo",
                       "data": "2026-09-22"}],
        "categoria": [{"url": "https://ex.com/b", "de": "clientes", "para": "inovação",
                       "motivo": "produto de software, não expansão de infraestrutura"}],
        "resumo": [{"url": "https://ex.com/c", "texto": "Resumo corrigido à mão.",
                    "motivo": "modelo tratou o ReData como empresa"}],
        "highlight": ["https://ex.com/b"],
        "fonte_nome": [{"url": "https://ex.com/c", "para": "Investing.com"}],
        "dedup": [{"manter": "https://ex.com/b", "fundir": ["https://ex.com/d"],
                   "motivo": "mesma sanção"}],
        "empresa": [{"nome": "Datafoo", "overview": "Provedora fictícia, para teste.",
                     "aprovado_por": "Pedro", "data": "2026-09-22"}],
    }
    caminho = os.path.join(tempfile.gettempdir(), "overrides_teste.json")
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(exemplo, f, ensure_ascii=False)

    items = [
        {"url": "https://ex.com/a", "title": "Sai", "source": "X", "category": "outros"},
        {"url": "https://ex.com/b", "title": "Fica e muda", "source": "Y",
         "category": "clientes", "summary": "s"},
        {"url": "https://ex.com/c", "title": "Resumo novo", "source": "errado",
         "category": "governo", "summary": "antigo",
         "ficha": {"ratios": [{"texto": "R$ 50 mi/MW"}]}},
        {"url": "https://ex.com/d", "title": "Fundida", "source": "Z", "category": "governo"},
    ]

    final, relatorio = aplicar(items, caminho)
    relatar(relatorio)
    print(f"\n{len(items)} → {len(final)} notícias")
    for item in final:
        print(f"  {item['title']:16} categoria={item.get('category'):12} "
              f"fonte={item.get('source'):16} grifada={item.get('highlight', False)}")
    print(f"\nMétricas da 'Resumo novo': {final[1].get('ficha', {}).get('ratios')}")
    os.remove(caminho)
