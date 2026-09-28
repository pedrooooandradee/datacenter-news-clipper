import os
import json
import sys
import argparse
import traceback
from pathlib import Path

# Add project root to sys.path to allow absolute imports
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from datetime import date, datetime, timedelta
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
from services.pdf_builder import build_pdf, carregar_weasyprint, PDFIndisponivel
from services.utils.archive import (
    archive_raw, edicao_anterior, url_chave, DIAS_DA_QUINZENAL, SEMANAL, QUINZENAL,
)
from services.utils.projeto import (
    modelo, sem_credito, descrever_erro, SemCredito, preparar_terminal,
)
from services.utils.datetime_utils import dia_local
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
               "configs/fontes.json", "services/utils/fontes.py",
               "services/utils/archive.py", "main.py"],
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

    `days` is the edition's window, computed once by janela_desta_edicao() and
    passed to the search, to this filter and to the PDF header. It used to be a
    separate 7 in each of the three, with nothing keeping them equal.

    Two separate problems, both of which reached the PDF:

    - A failed fetch left body="" and was summarised anyway, producing "O artigo
      não contém informações acessíveis" in the clipping.
    - Google News reported a 2012 article about AMD with a recent date. The page's
      own metadata did not.

    The window is compared by civil day, not by rolling 24-hour periods: an article
    published on the morning the window opens is this week's news, and cutting at
    "now minus 168 hours" would have dropped six good articles from the sample week.
    """
    # The calendar of this computer, the same one the window and the PDF header are
    # counted in. It used to be UTC here, so a run after 21h in Brasília dropped
    # the first day the header said it covered.
    window_start = (datetime.now() - timedelta(days=days)).date()
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

        published = dia_local(page_date)
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


# How far back an edition looks: the configured week, stretched by at most a few
# days when the run is late. A first version (28 set 2026) stretched it all the way
# back to the previous edition, up to 21 days. An independent review the same day
# showed why that was wrong, with two measurements:
#
# - output/archive/ lives on ONE computer and is not in git. A machine whose copy
#   had stopped two editions back stretched the window to 21 days and compared the
#   repeats against the stale edition, so the two editions sent from another
#   computer came back, whole, under a three-week header.
# - The search then asked Google for no dates, got about 100 entries mixing weeks,
#   and a 14-day window recovered little of the skipped week. (The search now asks
#   for its dates, a week at a time, so this second reason is gone; the first
#   one is enough.)
#
# So nothing is stretched because of a gap in the local archive. A run one to
# three days late is: those days are few. Two weeks are covered when someone asks
# for them, with --quinzenal.
JANELA_PADRAO = 7
ATRASO_TOLERADO = 3


def janela_desta_edicao(agora=None, quinzenal: bool = False):
    """
    Days this edition covers, and a line explaining why.

    A fortnightly edition is asked for by name (--quinzenal): the company has
    sent them on purpose, over the year-end holidays and Carnival, and the Drive
    files them as "Clipping Atualização Quinzenal". It is a decision, never
    something the program infers from a gap in the archive (see the note above).

    The line starts with ⚠️ when the last edition on this computer is too old to
    be the real previous one: either a week was skipped or editions went out from
    another computer. The program cannot tell which, so it says both.
    """
    agora = agora or datetime.now()
    try:
        with open(PROJECT_ROOT / "configs/queries.json", "r", encoding="utf-8") as f:
            configurado = max([c.get("days", JANELA_PADRAO) for c in json.load(f)]
                              or [JANELA_PADRAO])
    except (OSError, ValueError):
        configurado = JANELA_PADRAO
    pedido = max(configurado, DIAS_DA_QUINZENAL) if quinzenal else configurado
    tipo = "edição quinzenal (--quinzenal)" if quinzenal else "edição semanal"

    nome, _ = edicao_anterior(agora)
    if not nome:
        return pedido, f"{tipo}; não há edição anterior neste computador"

    dias = (agora.date() - datetime.strptime(nome, "%Y-%m-%d").date()).days
    if quinzenal and dias < DIAS_DA_QUINZENAL - ATRASO_TOLERADO:
        return pedido, (
            f"⚠️  edição quinzenal, mas a última edição é de {nome}, há só {dias} dias:\n"
            f"     esta repete a semana dela. As mesmas URLs são retiradas; o mesmo fato "
            f"em outro veículo, não. Confira na revisão")
    if dias <= pedido:
        return pedido, f"{tipo}; a última edição é de {nome}"
    if dias <= pedido + ATRASO_TOLERADO:
        return dias, (f"{tipo}; a última edição foi há {dias} dias ({nome}), e a janela "
                      f"vai até ela para os dias de atraso não se perderem")
    dica = "" if quinzenal else "; para cobrir duas semanas, --quinzenal"
    return pedido, (
        f"⚠️  a última edição NESTE COMPUTADOR é de {nome}, há {dias} dias.\n"
        f"     Se uma edição foi pulada: o que saiu no intervalo NÃO entra nesta "
        f"(a janela fica em {pedido} dias{dica}).\n"
        f"     Se houve edições enviadas de outro computador: pare agora (Ctrl+C) e "
        f"copie a pasta delas para output/archive/ — sem isso, notícias que o "
        f"cliente já recebeu podem voltar")


def desde_para_o_nome(inicio_janela: date, quinzenal: bool = False, agora=None) -> date:
    """
    The first date in the Drive file name.

    It is the previous edition's day, the way the files have always been named
    by hand — the edition of 14/09 is "(08_09 - 14_09 …)", after the Tuesday
    edition of 08/09 — when that edition is plausibly the real previous one: a
    week back (a fortnight for --quinzenal), give or take ATRASO_TOLERADO days.
    Otherwise, with no previous edition or a stale archive, it is the first day
    searched.
    """
    agora = agora or datetime.now()
    nome, _ = edicao_anterior(agora)
    if nome:
        anterior = datetime.strptime(nome, "%Y-%m-%d").date()
        esperado = DIAS_DA_QUINZENAL if quinzenal else JANELA_PADRAO
        if abs((agora.date() - anterior).days - esperado) <= ATRASO_TOLERADO:
            return anterior
    return inicio_janela


def verificar_pdf() -> bool:
    """
    Whether the PDF can be drawn on this computer, checked before anything is paid.

    WeasyPrint needs system libraries that pip does not install, and each system
    installs them differently. A computer without them used to find out at the
    very end, after half an hour and the API bill.
    """
    try:
        carregar_weasyprint()
    except PDFIndisponivel as e:
        print(f"⛔ {e}\n   Nada foi gasto.")
        return False
    return True


def verificar_modelos(cliente=None) -> bool:
    """
    Check the key and every configured model before anything is paid for.

    A retired model or a revoked key used to surface halfway through the run, as
    a bare exception class name in a list of failures, after the search and the
    scrape had already been done. The README then pointed at the key even when
    the model was the problem. This asks the API about each model — a metadata
    lookup that costs no tokens — and stops in seconds with the actual cause.

    What it cannot see is an account with no credit: the lookup is free, so it
    answers either way. That shows up on the first paid call, the title triage,
    which stops the run right there (SemCredito) instead of keeping every story
    and scraping for half an hour before the summaries fail.
    """
    import openai
    if cliente is None:
        chave = os.getenv("OPENAI_API_KEY")
        if not chave:
            print("⛔ Não há OPENAI_API_KEY no arquivo .env. Nada foi gasto.\n"
                  "   Faça uma cópia do arquivo .env.example com o nome .env e ponha a "
                  "chave nela.")
            return False
        cliente = openai.OpenAI(api_key=chave)

    # The embedding model only pre-groups similar stories; deduplicator.py already
    # carries on without it. Stopping the whole edition over it would be worse
    # than the problem, so it gets a warning.
    so_avisa = {modelo("embedding")} - {modelo(e) for e in
                                        ("triagem", "resumo", "ficha", "reclassificacao", "dedup")}

    etapas = ("triagem", "resumo", "ficha", "reclassificacao", "dedup", "embedding")
    for nome in sorted({modelo(e) for e in etapas}):
        try:
            cliente.models.retrieve(nome)
        except openai.AuthenticationError:
            print("⛔ A OpenAI recusou a chave do .env (errada ou revogada). Nada foi gasto.\n"
                  "   Peça uma chave válida a quem administra a organização elementum3 na "
                  "OpenAI.")
            return False
        except (openai.NotFoundError, openai.PermissionDeniedError) as e:
            if nome in so_avisa:
                print(f"⚠️  O modelo de embedding '{nome}' não respondeu "
                      f"({descrever_erro(e)[:80]}). A edição sai, mas sem o agrupamento "
                      f"prévio de parecidas: sobram mais repetidas para a revisão.\n"
                      f"     Avise quem cuida do programa.")
                continue
            if isinstance(e, openai.PermissionDeniedError):
                # Not a retired model: the key is not allowed to use it, or — with
                # a restricted key — not even allowed to look it up. Changing the
                # model in modelos.json, which the old message said, fixes neither.
                print(f"⛔ A chave não tem permissão para o modelo '{nome}'. Nada foi "
                      f"gasto.\n"
                      f"   Peça a quem administra a organização elementum3 na OpenAI para "
                      f"liberar este modelo no projeto da chave (e, se a chave for "
                      f"'Restricted', a permissão 'Models: Read').\n"
                      f"   NÃO troque o modelo em configs/modelos.json: o problema é a "
                      f"permissão, não o modelo.")
                return False
            print(f"⛔ O modelo '{nome}' não existe mais na OpenAI (aposentado ou nome "
                  f"errado). Nada foi gasto.\n"
                  f"   Troque o nome em configs/modelos.json (ver LEIA-ME, 'Quando quebrar').")
            return False
        except openai.APIConnectionError:
            print("⛔ Sem conexão com a OpenAI. Confira a internet e rode de novo. "
                  "Nada foi gasto.")
            return False
        except openai.APIStatusError as e:
            if sem_credito(e):
                print("⛔ A conta da OpenAI ficou SEM CRÉDITO. Nada foi gasto.\n"
                      "   Peça a quem administra a organização elementum3 para pôr "
                      "crédito, e rode de novo.")
            else:
                print(f"⛔ A OpenAI respondeu com erro {e.status_code} ao conferir os "
                      f"modelos — instabilidade do lado dela. Nada foi gasto.\n"
                      f"   Espere alguns minutos e rode de novo.")
            return False
        except openai.OpenAIError as e:
            print(f"⛔ Erro inesperado ao conferir a chave com a OpenAI "
                  f"({descrever_erro(e)}). Nada foi gasto.")
            return False
    return True


def drop_already_published(items):
    """
    Remove what the previous edition already carried, by URL.

    The window is seven civil days and editions close weekly, so two consecutive
    editions share a day. On 28 set 2026 that put five of the previous week's
    stories back in front of the reader, three of them at the very same URL.

    This runs right after the scrape, where the Google News wrapper has already
    been resolved into the article's own address, and before anything is paid to
    summarise it. Matching the exact URL cannot drop a new story. What it does not
    catch is the same fact at another outlet's URL — the AZ Quest fund and the
    Odata cooling system that week — which still needs the reviewer.
    """
    nome, publicadas = edicao_anterior()
    if not publicadas:
        # Silent here was a defect: on a new machine, or with output/archive
        # missing, last week's stories came back with nothing saying the filter
        # had not run.
        print("⚠️  Nenhuma edição anterior em output/archive/: as notícias repetidas da "
              "semana passada NÃO foram retiradas.\n"
              "     Confira contra o último PDF enviado, ou copie a pasta da última "
              "edição para output/archive/ antes de rodar.")
        return items

    kept, repetidas = [], []
    for item in items:
        if url_chave(item.get("url", "")) in publicadas:
            repetidas.append(f"{item.get('source', '?')} — {item.get('title', '')[:60]}")
        else:
            kept.append(item)

    if repetidas:
        print(f"↩️  {len(repetidas)} notícias já saíram na edição de {nome} "
              f"(mesma URL) e foram retiradas:")
        for entrada in repetidas:
            print(f"     - {entrada}")
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
    parser.add_argument(
        "--quinzenal", action="store_true",
        help="Edição de duas semanas (14 dias), como nas festas de fim de ano. "
             "O PDF sai como 'Clipping Atualização Quinzenal'.",
    )
    parser.add_argument("--clear-cache", action="store_true",
                        help="Apaga todo o cache e sai.")
    return parser.parse_args()


def main():
    preparar_terminal()
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
    registro = _abrir_registro()
    # The error is written while the log is still open. Letting it propagate
    # printed the traceback after the log was closed, so the file that gets sent
    # to whoever fixes the problem ended one line before the problem.
    codigo = 0
    try:
        _executar(args)
    except KeyboardInterrupt:
        print("\n⛔ Execução interrompida (Ctrl+C). As etapas que terminaram ficam no "
              "cache; a edição NÃO foi montada.")
        codigo = 130
    except SemCredito as e:
        print(e)
        codigo = 1
    except Exception:
        traceback.print_exc()
        print("⛔ A execução PAROU com o erro acima. Mande este registro a quem for "
              "consertar (ver LEIA-ME, 'Quando quebrar').")
        codigo = 1
    finally:
        trava.liberar()
        _fechar_registro(registro)
    if codigo:
        sys.exit(codigo)


class _Duplicador:
    """Writes to the terminal and to a file at the same time."""

    def __init__(self, terminal, arquivo):
        self.terminal, self.arquivo = terminal, arquivo

    def write(self, texto):
        self.terminal.write(texto)
        try:
            self.arquivo.write(texto)
        except ValueError:          # file already closed at interpreter exit
            pass
        return len(texto)

    def flush(self):
        self.terminal.flush()
        try:
            self.arquivo.flush()
        except ValueError:
            pass

    def __getattr__(self, nome):
        return getattr(self.terminal, nome)


def _abrir_registro():
    """
    Save everything the run prints to output/logs/, as well as showing it.

    The review depends on what the run printed — the 🚨 block, the pages that
    could not be fetched, the stories dropped as repeats — and all of it lived
    only in a terminal window. Close the window, or run it in Cursor and review
    from another machine, and the warnings were gone. Now each run leaves a file.
    """
    pasta = PROJECT_ROOT / "output" / "logs"
    try:
        os.makedirs(pasta, exist_ok=True)
        caminho = pasta / f"execucao-{datetime.now().strftime('%Y-%m-%d-%H%M%S')}.log"
        # Line by line, not in 8 KB blocks: closing the terminal tab or killing a
        # stuck run skips every cleanup, and the last warnings were lost with it.
        arquivo = open(caminho, "w", encoding="utf-8", buffering=1)
    except OSError as e:
        print(f"⚠️  Não consegui abrir o registro da execução ({e}); segue sem ele.")
        return None
    originais = (sys.stdout, sys.stderr)
    sys.stdout = _Duplicador(originais[0], arquivo)
    sys.stderr = _Duplicador(originais[1], arquivo)
    return caminho, arquivo, originais


def _fechar_registro(registro):
    if not registro:
        return
    caminho, arquivo, originais = registro
    sys.stdout, sys.stderr = originais
    arquivo.close()
    print(f"📝 Tudo o que apareceu acima está salvo em "
          f"{caminho.relative_to(PROJECT_ROOT)} — é o que a revisão usa.")


def _executar(args):
    load_dotenv()

    start = args.from_stage or STAGES[0]
    start_idx = STAGES.index(start)

    # Free checks first: whether this computer can draw the PDF, and whether the
    # key and the models answer. Every stage up to dedup calls the OpenAI API,
    # and all of them come before the PDF.
    if not verificar_pdf():
        return
    if start_idx <= STAGES.index("dedup") and not verificar_modelos():
        return

    tipo = QUINZENAL if args.quinzenal else SEMANAL
    janela, porque = janela_desta_edicao(quinzenal=args.quinzenal)
    inicio = date.today() - timedelta(days=janela)
    desde = desde_para_o_nome(inicio, quinzenal=args.quinzenal)

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
        # The cached stories came from a search with its own window and kind.
        # Rebuilding them under other ones would print "Semanal" over a
        # fortnight's news, or — run a week later — "Quinzenal" over one week's,
        # so the edition's first day, its "since" date and its kind travel with
        # the cache. (Its closing date is still today: see LEIA-ME, --from.)
        salva = cache.edicao_salva(previous)
        if salva:
            inicio, desde, tipo = salva["inicio_janela"], salva["desde"], salva["tipo"]
            janela = (date.today() - inicio).days
            porque = f"{tipo.lower()}, a da busca guardada no cache"
            if args.quinzenal and tipo != QUINZENAL:
                print("⚠️  --quinzenal ignorado: o cache veio de uma busca semanal. Para "
                      "uma quinzenal, rode sem --from.")
        elif args.quinzenal:
            # A cache written before the window was recorded is always weekly.
            print("⚠️  --quinzenal ignorado: este cache é anterior ao registro da janela "
                  "e veio de uma busca semanal. Para uma quinzenal, rode sem --from.")
            tipo = SEMANAL
            janela, porque = janela_desta_edicao(quinzenal=False)
            inicio = date.today() - timedelta(days=janela)
            desde = desde_para_o_nome(inicio)

    if porque.startswith("⚠️"):
        print(f"📅 Janela desta edição: de {inicio:%d/%m} até hoje ({janela} dias).\n{porque}.")
    else:
        print(f"📅 Janela desta edição: de {inicio:%d/%m} até hoje ({janela} dias) — {porque}.")

    edicao = {"inicio_janela": inicio, "desde": desde, "tipo": tipo}

    def guardar(stage: str, conteudo, impressao: str) -> None:
        cache.save(stage, conteudo, impressao, edicao=edicao)

    # 1-3) Fetch RSS results and deduplicate by URL
    if runs("search"):
        with open(PROJECT_ROOT / "configs/queries.json", "r", encoding="utf-8") as f:
            configs = json.load(f)

        all_items = []
        problemas_da_busca = []
        buscas_vazias = []
        for cfg in configs:
            query = cfg.get("query")
            # One window for the whole edition: the search, the date filter and
            # the PDF header all use it. janela is already at least every
            # query's own "days".
            days = janela
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
        guardar("search", items, fingerprint("search"))

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
            guardar("classify_descartadas", discarded, fingerprint("classify"))
            print(f"   {len(discarded)} descartadas, registradas em "
                  f"output/cache/classify_descartadas.json para revisão")

        if not items:
            print("No relevant articles. Exiting.")
            return
        guardar("classify", items, fingerprint("classify"))

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
        items = drop_failed_and_stale(items, days=janela)
        items = drop_already_published(items)
        if not items:
            print("No usable articles after scraping. Exiting.")
            return
        guardar("scrape", items, fingerprint("scrape"))

    # 7) Summarize, then drop what came back without a usable paragraph
    if runs("summarize"):
        items = add_summaries(items)
        items = drop_without_summary(items)
        print(f"{len(items)} notícias com resumo aproveitável")
        if not items:
            print("Nenhum resumo aproveitável. Encerrando.")
            return
        guardar("summarize", items, fingerprint("summarize"))

    # 8) The structured record: final category decided with the summary in hand,
    #    figures copied from the body, ratios computed in Python
    if runs("ficha"):
        items = reclassify_with_summary(items)
        items = add_fichas(items)
        # The body has done its work. It is dropped here, not in the summarizer,
        # because this is the last stage that needs it.
        for item in items:
            item.pop("body", None)
        guardar("ficha", items, fingerprint("ficha"))

    # 9) Remove duplicate coverage based on summary similarity
    if runs("dedup"):
        items = deduplicate_by_summary(items)
        print(f"Final count after semantic deduplication: {len(items)} items")
        guardar("dedup", items, fingerprint("dedup"))

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
    archive_raw(items, inicio_janela=inicio, desde=desde, tipo=tipo)

    # 11) Apply configs/overrides.json and generate the PDF
    pdf_path = build_pdf()
    if not pdf_path:
        # build_pdf has already said why. The edition itself is saved; fixing
        # the cause and running command 2 builds it without paying again.
        print("⛔ A edição foi salva, mas o PDF NÃO foi montado (motivo acima). Depois de "
              "corrigir: python services/pdf_builder.py")


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
