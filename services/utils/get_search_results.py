"""
Google News RSS Feed Scraper

This script provides functionality to search Google News via RSS feeds,
using a constructed RSS URL with query, country, and UI language parameters,
and extracts result titles and links published within a given number of days.

Functions:
- collect_search_results_from_rss(feed, days):
    Extracts all items published in the last `days` days from a feedparser feed object.
    Each item is a dict containing 'title' and 'url'.

- build_google_news_rss_url(query, country='br', ui_lang='pt-BR'):
    Constructs the Google News RSS search URL for the given query and localization.

- get_search_results(query, days=7, country='br', ui_lang='pt-BR'):
    Fetches news articles matching `query` from Google News RSS,
    filters by the last `days` days, and returns a list of dicts with 'title', 'source', 'url', and 'pubDate'.

Requirements:
    feedparser
"""

import feedparser
import time
import json
import os
from datetime import datetime, timedelta, timezone
import urllib.parse
from email.utils import parsedate_to_datetime

try:
    from services.utils.datetime_utils import dia_local
except ImportError:          # run directly, from services/utils
    from datetime_utils import dia_local

# Display names for outlets that Google News reports as a bare domain.
_CONFIGS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "configs",
)
try:
    with open(os.path.join(_CONFIGS_DIR, "fontes.json"), "r", encoding="utf-8") as _f:
        SOURCE_NAMES = json.load(_f).get("nomes", {})
except (FileNotFoundError, json.JSONDecodeError):
    SOURCE_NAMES = {}


def split_title_and_source(entry):
    """
    Separate the headline from the outlet name.

    Google News reports the outlet in entry.source.title and repeats it at the end
    of entry.title as " - <outlet>". Splitting the title on the last " - " breaks
    whenever the outlet's own name contains one, which is common:

        source: "Investing.com Brasil - Finanças, Câmbio e Investimentos"
        title:  "Empresas adiam IPOs - Investing.com Brasil - Finanças, Câmbio e Investimentos"

    The old split returned "Finanças, Câmbio e Investimentos" as the outlet and
    left " - Investing.com Brasil" stuck on the headline. Using the feed's own
    source field and stripping exactly that suffix fixes both halves at once.

    Returns:
        (title, source)
    """
    full_title = entry.title
    feed_source = getattr(getattr(entry, "source", None), "title", None)

    if feed_source:
        suffix = f" - {feed_source}"
        title = full_title[: -len(suffix)] if full_title.endswith(suffix) else full_title
        # Compound outlet names carry the brand first: "CIMI - Conselho Indigenista
        # Missionário" is shown as "CIMI".
        source = feed_source.split(" - ", 1)[0].strip()
    else:
        # No source in the feed: fall back to the old behaviour rather than guess.
        if " - " in full_title:
            title, source = (part.strip() for part in full_title.rsplit(" - ", 1))
        else:
            title, source = full_title, "Unknown"

    # A bare domain gets a readable name when we have one; otherwise it is shown as
    # it came, which is honest, rather than de-accented into something wrong.
    source = SOURCE_NAMES.get(source, source)
    return title.strip(), source.strip()


def collect_search_results_from_rss(feed, days):
    """
    Given a feedparser feed object, collect all items published within the last
    `days` days.

    The window is counted in CIVIL DAYS, not in rolling 24-hour periods. This is
    the same rule the date filter downstream uses (main.py, drop_failed_and_stale)
    and it was only ever applied there: an article published at nine in the
    morning on the day the window opens is seven days and some hours old, and the
    rolling cut threw it away here — upstream of every counter, so the "Fetched N
    items" line could never show the loss.

    Returns:
        (results, descartados, sem_data)
    """
    results, descartados, sem_data = [], [], []
    # Counted on this computer's calendar, like the rest of the edition. In UTC,
    # a run after 21h in Brasília started the window a day later than the PDF
    # header said, and that day's news was lost here, before any report.
    window_start = (datetime.now() - timedelta(days=days)).date()

    for entry in feed.entries:
        title, source = split_title_and_source(entry)
        rotulo = f"{source} — {title[:60]}"

        try:
            pub_dt = parsedate_to_datetime(entry.published)
            if pub_dt.tzinfo is None or pub_dt.tzinfo.utcoffset(pub_dt) is None:
                pub_dt = pub_dt.replace(tzinfo=timezone.utc)
        except Exception:
            # An unreadable date used to be stamped with "now", which made the
            # item pass the window because it had just been "published" and put
            # today's date next to the headline in the PDF. A date we cannot read
            # is not a date; the page's own metadata fills it in later.
            pub_dt = None

        if pub_dt is None:
            sem_data.append(rotulo)
        elif dia_local(pub_dt) < window_start:
            # Google News answers with up to a hundred results per query whatever
            # their age, so most queries discard seventy to a hundred entries that
            # are plainly old. Counting them all and listing only the ones NEAR
            # the edge is the difference between a report that is read and
            # seventy-five lines of expected behaviour that buries the signal.
            dias_fora = (window_start - dia_local(pub_dt)).days
            descartados.append((dias_fora, f"{rotulo} [{dia_local(pub_dt)}]"))
            continue

        results.append({
            'title': title,
            'source': source,
            'url': entry.link,
            'pubDate': pub_dt,
        })

    return results, descartados, sem_data


def build_google_news_rss_url(query, country='br', ui_lang='pt-BR'):
    """
    Build a Google News RSS search URL for `query`, localized to `country` and `ui_lang`.
    """
    encoded_query = urllib.parse.quote_plus(query)
    ceid = f"{country.upper()}:{ui_lang}"
    return (
        f"https://news.google.com/rss/search?"
        f"q={encoded_query}&hl={ui_lang}&gl={country.upper()}&ceid={ceid}"
    )


# How close to the window an entry has to be for its discard to be worth showing.
# Further out than this and the cut is obviously right, so only the count is kept.
DIAS_DE_BORDA = 3


def _ler_feed(url):
    """
    Fetch one feed and say whether it actually came back.

    feedparser does not raise. A 429 from Google, a dropped connection or a
    malformed document all produce a feed object with zero entries — exactly what
    a query with no news this week produces. Without this check, throttling one
    query silently removes a whole competitor from the edition, and the only
    visible effect is that Ascenty had a quiet week.
    """
    feed = feedparser.parse(url)
    status = getattr(feed, "status", None)
    if status is not None and status >= 400:
        return feed, f"HTTP {status}"
    if getattr(feed, "bozo", False) and not feed.entries:
        motivo = getattr(feed, "bozo_exception", "documento malformado")
        return feed, f"{type(motivo).__name__ if isinstance(motivo, Exception) else 'erro'}: {motivo}"
    return feed, None


# Google News answers each query with about a hundred entries, whatever their
# dates. Asked with no dates at all, as it was until 28 set 2026, it mixes weeks,
# and the week being edited got what was left. Measured that day, the last 7 days
# with no dates versus the same 7 days asked with after:/before: —
#
#   "aws" ............ 13 versus 55
#   "data center" .... 81 versus 100 (the ceiling)
#   "google cloud" ... 80 versus 100 (the ceiling)
#
# So each query asks for its dates, one slice of at most FATIA_DIAS civil days
# at a time: a weekly edition is one request per query, as before, and a
# fortnightly one is two, so its first week is not crowded out by the second.
#
# It is still not everything. A narrower range returns more: "aws" asked for
# three days brought 17 stories its weekly slice did not (measured the same day,
# in an independent review), most of them not about data centres. Slices of a day
# would multiply the requests by seven and the stories to triage and review by
# more; whether the extra stories are worth it is to be measured on real
# editions (TODO.md). A slice that hits the ceiling is reported, because there
# the loss is certain.
FATIA_DIAS = 8          # a 7-day window spans 8 civil days: the 21st to the 28th
TETO_DO_GOOGLE = 100
ESPERA_ANTES_DE_REPETIR = 3   # seconds, before asking again for a slice that failed


def _fatias(days, hoje=None):
    """The window, from its first day to today, cut into slices of FATIA_DIAS days."""
    hoje = hoje or datetime.now().date()
    inicio = hoje - timedelta(days=days)
    fatias, fim = [], hoje
    while fim >= inicio:
        comeco = max(inicio, fim - timedelta(days=FATIA_DIAS - 1))
        fatias.append((comeco, fim))
        fim = comeco - timedelta(days=1)
    return list(reversed(fatias))


def _com_periodo(query, comeco, fim):
    """
    The query restricted to [comeco, fim].

    after: and before: exclude the day they name, and Google's day is not
    necessarily Brasília's, so each side gets a day of slack. The window itself
    is cut afterwards, by date, in collect_search_results_from_rss.
    """
    return (f"{query} after:{(comeco - timedelta(days=1)).isoformat()} "
            f"before:{(fim + timedelta(days=1)).isoformat()}")


def _buscar(query, days, country, ui_lang, fatiar=True):
    """
    One attempt at a query: every slice, merged.

    Returns (results, descartados, sem_data, problemas, falhou). A slice that
    fails is asked for once more, after a pause; `falhou` says one still failed.
    """
    results, descartados, sem_data, problemas, vistos = [], [], [], [], set()
    falhou = False
    for comeco, fim in (_fatias(days) if fatiar else [(None, None)]):
        busca = _com_periodo(query, comeco, fim) if comeco else query
        rotulo = f"'{query}'" + (f" ({comeco:%d/%m}–{fim:%d/%m})" if comeco else "")
        url = build_google_news_rss_url(busca, country=country, ui_lang=ui_lang)
        feed, erro = _ler_feed(url)
        if erro:
            time.sleep(ESPERA_ANTES_DE_REPETIR)
            feed, erro = _ler_feed(url)
        if erro:
            falhou = True
            problemas.append(f"a busca por {rotulo} FALHOU duas vezes ({erro}) — as "
                             f"notícias dela não entraram na edição")
            continue
        if comeco and len(feed.entries) >= TETO_DO_GOOGLE:
            problemas.append(f"{rotulo}: {len(feed.entries)} resultados, o teto do Google "
                             f"— há notícias desta consulta que não vieram")
        achados, fora, sem = collect_search_results_from_rss(feed, days)
        for item in achados:
            if item["url"] not in vistos:
                vistos.add(item["url"])
                results.append(item)
        descartados += fora
        sem_data += sem
    return results, descartados, sem_data, problemas, falhou


def get_search_results(query, days=7, country='br', ui_lang='pt-BR'):
    """
    Fetch the items matching `query`, filtered to the last `days` civil days.

    Up to three attempts, stopping at the first that finds something: the query
    with its dates; the same query with no dates, in case Google ever stops
    honouring after:/before:; and the query between quotes, with its dates. A
    network failure is not "found nothing": it stops here and is reported, rather
    than being papered over by a weaker search.

    Returns:
        (results, problemas) — problemas is a list of lines for the caller to
        print. Nothing is dropped in silence (DECISOES.md, Q24).
    """
    tentativas = [(query, True, None),
                  (query, False, "sem período"),
                  (f'"{query}"', True, "entre aspas")]
    problemas, results, descartados, sem_data = [], [], [], []
    for busca, fatiar, como in tentativas:
        results, descartados, sem_data, probs, falhou = _buscar(
            busca, days, country, ui_lang, fatiar)
        problemas += probs
        if results:
            if como:
                problemas.append(f"'{query}': a busca normal não achou nada na janela; "
                                 f"as {len(results)} notícias vieram da busca {como}")
            break
        if falhou:
            break

    # Only the attempt that counted is reported, and each story once.
    descartados = sorted(set(descartados))
    if descartados:
        na_borda = [d for d in descartados if d[0] <= DIAS_DE_BORDA]
        problemas.append(f"'{query}': {len(descartados)} entradas fora da janela "
                         f"de {days} dias"
                         + (f", {len(na_borda)} delas a até {DIAS_DE_BORDA} dias "
                            f"da borda:" if na_borda else " (todas bem antigas)"))
        problemas += [f"     - {texto}" for _, texto in na_borda[:5]]
    if sem_data:
        problemas.append(f"'{query}': {len(set(sem_data))} entradas sem data legível no "
                         f"feed, MANTIDAS — a data virá da própria página")

    return results, problemas


if __name__ == '__main__':
    # Example usage
    query = 'datacenter brasil'
    results, problemas = get_search_results(query, days=7, country='br')
    for linha in problemas:
        print(f"⚠️  {linha}")
    for i, item in enumerate(results, 1):
        print(f"{i}. {item['title']} - {item['source']} - {item['url']} (Published: {item['pubDate']})")
