import os
import json
import sys
import argparse
from pathlib import Path

# Add project root to sys.path to allow absolute imports
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from services.utils.get_search_results import get_search_results
from services.classifier import (
    add_classifications, drop_irrelevant, reclassify_with_summary,
)
from services.scraper import scrape_articles
from services.summarizer import add_summaries, drop_without_summary
from services.ficha import add_fichas
from services.deduplicator import (
    deduplicate_by_summary, prune_clusters_before_scrape,
    promover_reservas, descartar_reservas,
)
from services.pdf_builder import build_pdf
from services.utils.archive import archive_raw
from services.utils import cache
from services.utils import trava
from services.utils.fontes import apply_tier_gate

"""
Entry point for the DC News pipeline:
1. Load query configs
2. Fetch RSS search results
3. Deduplicate by URL
4. Classify items as relevant or irrelevant (adds 'class' key)
5. Filter only relevant news pieces
6. Scrape article bodies via Selenium + trafilatura
7. Summarize bodies via LangChain
8. Extract the structured record from the body, decide the final category with the
   summary in hand, and compute the ratios that pair
9. Remove duplicate coverage based on summary similarity
10. Store news piece metadata and summaries in output/clippings.json
11. Apply configs/overrides.json and generate the PDF clipping

Every stage writes its output to output/cache/. A plain run is always full and fresh;
--from=<etapa> reuses the cache of the earlier stages so a single stage can be
re-run without paying for the whole pipeline again. See services/utils/cache.py.
"""

# The pipeline in order. --from=X reuses the cache of the stage before X.
STAGES = ["search", "classify", "scrape", "summarize", "ficha", "dedup", "pdf"]

# What each stage's output depends on. Hashing the service module as well as the
# prompt means a changed model name or parsing rule also invalidates the cache.
# main.py is in every list because the orchestration lives here: the tier gate,
# the date window and the order of the calls all shape what a stage produces, and
# a cache built before they changed is not the same cache.
FINGERPRINT_SOURCES = {
    "search": ["configs/queries.json", "configs/fontes.json",
               "services/utils/get_search_results.py", "services/utils/fontes.py",
               "main.py"],
    "classify": ["configs/classification_prompt.txt", "services/classifier.py",
                 "configs/modelos.json", "main.py"],
    # The scrape stage also runs prune_clusters_before_scrape (TITLE_THRESHOLD)
    # and drop_failed_and_stale (STALE_MARGIN_DAYS). Changing either changed the
    # stage's output and left the cache looking untouched.
    "scrape": ["services/scraper.py", "services/deduplicator.py",
               "configs/fontes.json", "services/utils/fontes.py", "main.py"],
    "summarize": ["configs/summarization_prompt.txt", "services/summarizer.py",
                  "configs/modelos.json", "main.py"],
    "ficha": ["configs/ficha_prompt.txt", "services/ficha.py",
              "services/utils/numeros.py", "configs/classification_prompt.txt",
              "services/classifier.py", "configs/modelos.json", "main.py"],
    # select_survivor decides eligibility with tier_of, which reads fontes.json,
    # and ranks the eligible ones with completude(), which lives in ficha.py.
    # ficha.py was missing here: changing how completeness is scored changed
    # which article of a duplicate group gets published, and left the cache
    # looking untouched.
    "dedup": ["services/deduplicator.py", "configs/fontes.json",
              "services/utils/fontes.py", "services/ficha.py",
              "configs/modelos.json", "main.py"],
}


def fingerprint(stage: str) -> str:
    """Hash of the code and config behind a stage, used to spot a stale cache."""
    paths = [str(PROJECT_ROOT / p) for p in FINGERPRINT_SOURCES.get(stage, [])]
    return cache.file_digest(*paths) if paths else ""


# How far outside the week a page has to be before it is thrown away rather than
# flagged. The 2012 AMD article sat 5,060 days outside; a story published the
# evening before the window opens sits one day outside and is perfectly good.
# Discarding near the edge would have cost six legitimate articles in the sample
# week, including the week's lead story in three outlets.
STALE_MARGIN_DAYS = 30


def drop_failed_and_stale(items, days: int = 7):
    """
    Remove what the collector failed to fetch, and what the page itself says is old.

    `days` HAS TO MATCH the window in configs/queries.json, and today nothing
    enforces that. The number lives in three independent places: every query in
    queries.json carries its own "days", this default, and the header line in
    configs/clipping_template.html, which says "Week …" off its own hardcoded 7.
    Widen queries.json to 14 for a fortnightly edition and leave this at 7, and
    the whole second week arrives marked `date_outside_window` — a mark that is
    written to the JSON, printed once in the terminal, and never rendered in the
    PDF. The reader gets a 13-day-old story under a header that says one week.

    Two separate problems, both of which reached the PDF:

    - A failed fetch left body="" and was summarised anyway, producing "O artigo
      não contém informações acessíveis" in the clipping.
    - Google News reported a 2012 article about AMD with a recent date. The page's
      own metadata did not.

    The window is compared by civil day, not by rolling 24-hour periods: an article
    published on the morning the window opens is this week's news, and cutting at
    "now minus 168 hours" would have dropped six good articles from the sample week.
    """
    window_start = (datetime.now(timezone.utc) - timedelta(days=days)).date()
    hard_cutoff = window_start - timedelta(days=STALE_MARGIN_DAYS)

    kept, no_body, stale, unverified, borderline = [], [], [], [], []

    for item in items:
        label = f"{item.get('source', '?')} — {item.get('title', '')[:60]}"

        if not item.get("body"):
            no_body.append(f"{label} [{item.get('scrape_problem', 'sem corpo')}]")
            continue

        page_date = item.get("page_date")
        if page_date is None:
            # 81% of the pages that load carry a readable date; the rest are kept
            # and marked, because no date is not evidence of being old.
            item["date_unverified"] = True
            unverified.append(label)
            kept.append(item)
            continue

        published = page_date.date()
        if published < hard_cutoff:
            stale.append(f"{label} [publicada em {published}]")
            continue
        if published < window_start:
            item["date_outside_window"] = True
            borderline.append(f"{label} [publicada em {published}]")

        kept.append(item)

    print(f"{len(kept)} notícias seguem para o resumo "
          f"(de {len(items)} coletadas)")
    if no_body:
        print(f"⚠️  {len(no_body)} descartadas por falha de coleta:")
        for entry in no_body:
            print(f"     - {entry}")
    if stale:
        print(f"⚠️  {len(stale)} descartadas por serem mais de {STALE_MARGIN_DAYS} dias "
              f"mais antigas que a janela:")
        for entry in stale:
            print(f"     - {entry}")
    if borderline:
        print(f"⚠️  {len(borderline)} um pouco fora da janela, MANTIDAS e marcadas "
              f"para revisão manual:")
        for entry in borderline:
            print(f"     - {entry}")
    if unverified:
        print(f"⚠️  {len(unverified)} sem data na página, MANTIDAS e marcadas "
              f"como data não verificada.")

    return kept


def parse_args():
    parser = argparse.ArgumentParser(
        description="Pipeline do clipping de data centers (cliente 247).",
        epilog=("Sem --from, roda tudo do zero: gasta API e leva de 10 a 30 minutos. "
                "Com --from, reaproveita o cache das etapas anteriores."),
    )
    parser.add_argument(
        "--from", dest="from_stage", choices=STAGES, metavar="ETAPA",
        help=f"Retoma a partir desta etapa. Opções: {', '.join(STAGES)}",
    )
    parser.add_argument("--list-cache", action="store_true",
                        help="Mostra o que há em cache e sai.")
    parser.add_argument("--clear-cache", action="store_true",
                        help="Apaga todo o cache e sai.")
    return parser.parse_args()


def main():
    args = parse_args()

    if args.list_cache:
        cache.describe()
        return
    if args.clear_cache:
        cache.clear()
        return

    # One run at a time. Two at once share output/ and the cache, and the
    # edition report comes out wrong — measured, on 22 set 2026.
    if not trava.adquirir():
        return
    try:
        _executar(args)
    finally:
        trava.liberar()


def _executar(args):
    # Load environment variables
    load_dotenv()
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

    start = args.from_stage or STAGES[0]
    start_idx = STAGES.index(start)

    def runs(stage: str) -> bool:
        """True when this stage should actually execute rather than come from cache."""
        return STAGES.index(stage) >= start_idx

    items = None

    # Resuming: load the output of the stage right before the starting point.
    if start_idx > 0:
        previous = STAGES[start_idx - 1]
        print(f"Retomando a partir de '{start}'.")
        loaded = cache.load(previous, fingerprint=fingerprint(previous))
        if loaded is None:
            print(f"Sem cache utilizável de '{previous}'. "
                  f"Rode sem --from para uma execução completa.")
            return
        items, _ = loaded

    # 1-3) Fetch RSS results and deduplicate by URL
    if runs("search"):
        with open(PROJECT_ROOT / "configs/queries.json", "r", encoding="utf-8") as f:
            configs = json.load(f)

        all_items = []
        problemas_da_busca = []
        buscas_vazias = []
        for cfg in configs:
            query = cfg.get("query")
            days = cfg.get("days", 7)
            country = cfg.get("country", "br")
            print(f"[{datetime.now()}] Searching for '{query}' (last {days} days, country={country})...")
            encontrados, problemas = get_search_results(query, days=days, country=country)
            all_items.extend(encontrados)
            problemas_da_busca += problemas
            if not encontrados:
                buscas_vazias.append(query)
        print(f"Fetched {len(all_items)} items from RSS feeds")

        # A query that fails on the network looks exactly like a query with no
        # news this week. Saying which is which is the difference between "a
        # competitor was quiet" and "we did not look".
        if problemas_da_busca:
            print(f"⚠️  Problemas na busca:")
            for linha in problemas_da_busca:
                print(f"     {linha}" if linha.startswith("     ") else f"     - {linha}")
        if buscas_vazias:
            print(f"⚠️  {len(buscas_vazias)} consultas voltaram sem nenhuma notícia: "
                  f"{', '.join(buscas_vazias)}")

        seen = set()
        items = []
        for item in all_items:
            if item["url"] not in seen:
                seen.add(item["url"])
                items.append(item)
        print(f"{len(items)} unique items after deduplication")

        if not items:
            print("No items fetched. Exiting.")
            return

        # The tier of an outlet is known from the feed, so the gate runs here —
        # before anything has been classified, scraped or summarised.
        items, blocked, unlisted = apply_tier_gate(items)
        if blocked:
            print(f"⚠️  {len(blocked)} excluídas por fonte de tier 4:")
            for entry in blocked:
                print(f"     - {entry.get('source', '?')}: {entry.get('title', '')[:65]}")
        if unlisted:
            print(f"⚠️  {len(unlisted)} fontes ainda não classificadas, tratadas como "
                  f"tier {3} — promova ou rebaixe em configs/fontes.json:")
            for source in sorted(unlisted):
                print(f"     - {source}")
        print(f"{len(items)} itens após o portão de fonte")

        if not items:
            print("No items left after the source gate. Exiting.")
            return
        cache.save("search", items, fingerprint("search"))

    # 4-5) Classify and keep only the relevant items
    if runs("classify"):
        annotated = add_classifications(items)
        print(f"Annotated {len(annotated)} items with class labels")
        items = drop_irrelevant(annotated)
        print(f"{len(items)} relevant items remain after filtering")

        # What the classifier threw away is what you need in order to improve it.
        # Keeping it out of the pipeline but on disk costs nothing and is the only
        # record of the calls it got wrong.
        discarded = [i for i in annotated if i.get("class", "").lower() != "relevant"]
        if discarded:
            cache.save("classify_descartadas", discarded, fingerprint("classify"))
            print(f"   {len(discarded)} descartadas, registradas em "
                  f"output/cache/classify_descartadas.json para revisão")

        if not items:
            print("No relevant articles. Exiting.")
            return
        cache.save("classify", items, fingerprint("classify"))

    # 6) Scrape article bodies, then drop what failed to fetch or is genuinely old
    if runs("scrape"):
        # Group near-identical titles first: fetching three copies of the same
        # announcement costs Selenium time and a summarisation each.
        items = prune_clusters_before_scrape(items)
        items = scrape_articles(items)
        # A group whose chosen articles all came back blocked still has a copy in
        # hand. Fetching it costs one navigation and saves the story.
        resgate = promover_reservas(items)
        if resgate:
            scrape_articles(resgate)
        items = descartar_reservas(items)
        print(f"Scraped bodies for {len(items)} items")
        items = drop_failed_and_stale(items)
        if not items:
            print("No usable articles after scraping. Exiting.")
            return
        cache.save("scrape", items, fingerprint("scrape"))

    # 7) Summarize, then drop what came back without a usable paragraph
    if runs("summarize"):
        items = add_summaries(items)
        items = drop_without_summary(items)
        print(f"{len(items)} notícias com resumo aproveitável")
        if not items:
            print("Nenhum resumo aproveitável. Encerrando.")
            return
        cache.save("summarize", items, fingerprint("summarize"))

    # 8) The structured record: final category decided with the summary in hand,
    #    figures copied from the body, ratios computed in Python
    if runs("ficha"):
        items = reclassify_with_summary(items)
        items = add_fichas(items)
        # The body has done its work. It is dropped here, not in the summarizer,
        # because this is the last stage that needs it.
        for item in items:
            item.pop("body", None)
        cache.save("ficha", items, fingerprint("ficha"))

    # 9) Remove duplicate coverage based on summary similarity
    if runs("dedup"):
        items = deduplicate_by_summary(items)
        print(f"Final count after semantic deduplication: {len(items)} items")
        cache.save("dedup", items, fingerprint("dedup"))

    for item in items:
        if 'highlight' not in item:
            item['highlight'] = False
        # Dates travel through the pipeline as datetimes and are formatted in the
        # template. The JSON the PDF builder reads, and the archive, need text.
        for campo in ('page_date', 'pubDate'):
            if isinstance(item.get(campo), datetime):
                item[campo] = item[campo].isoformat()

    # 10) Write output file, keeping whatever was there before
    output_file = PROJECT_ROOT / "output" / "clippings.json"
    os.makedirs(output_file.parent, exist_ok=True)
    _preservar_anterior(output_file, items)
    with open(output_file, "w", encoding="utf-8") as out_f:
        json.dump(items, out_f, ensure_ascii=False, indent=2)
    print(f"Wrote clippings JSON to {output_file}")

    # 10b) Freeze the raw output, before anyone edits clippings.json by hand
    archive_raw(items)

    # 11) Apply configs/overrides.json and generate the PDF
    pdf_path = build_pdf()
    print(f"Generated PDF clipping at {pdf_path}")


def _preservar_anterior(output_file, items) -> None:
    """
    Never overwrite an edition without keeping the one that was there.

    This matters most for `--from=pdf` and `--from=dedup`, which rebuild
    clippings.json out of the cache. Anything corrected by hand in the file and
    not yet written into configs/overrides.json would be gone, with no warning and
    no copy. The durable place for a manual correction is overrides.json; this is
    the seat belt for the times it has not got there yet.
    """
    if not output_file.exists():
        return

    try:
        anterior = json.loads(output_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        anterior = None

    if anterior == items:
        return

    copia = output_file.with_name("clippings.anterior.json")
    try:
        copia.write_text(output_file.read_text(encoding="utf-8"), encoding="utf-8")
    except OSError as e:
        print(f"⚠️  Não consegui guardar a versão anterior de clippings.json ({e}).")
        return

    quantas = len(anterior) if isinstance(anterior, list) else "?"
    print(f"💾 A versão anterior de clippings.json ({quantas} notícias) foi guardada "
          f"em output/{copia.name} antes de ser substituída.")
    print(f"   Correções feitas à mão só sobrevivem à próxima execução se estiverem "
          f"em configs/overrides.json.")


if __name__ == "__main__":
    main()
