# services/scraper.py

"""
Fetching and extracting article bodies.

Rewritten after measuring the old version against the real pipeline. Four defects,
all of which reached the PDF:

1. The Google News wrapper often never resolved. The old code did driver.get(url),
   then a flat time.sleep(2.0), then read driver.current_url. Two seconds is not
   enough for Google's redirect, so 3 of 53 items kept a news.google.com URL and
   were "scraped" from Google's own interstitial. That is how a 2012 article about
   AMD entered the clipping as this week's news: with no real URL there is no page
   to read a real date from.

2. Docling was fed the whole page_source. Measured over 18 real articles it
   returned a median of 10,498 characters against ~3,600 for the article itself,
   and carried 54 numbers that appear nowhere in the article — including a 55%
   discount on a Galaxy A37 inside a story about a TikTok data centre. That is the
   defect that put an invented "30%" into a published summary.

3. A new Chrome per article, with ChromeDriverManager().install() each time.
   Measured on the URLs the pipeline actually passes: 241.96s for 10 articles
   (~36 min for 90). The block is not driver.get() — on a wrapper that returns in
   1.3s — but the first command after it, which waits for the real article.

4. A failed fetch produced body="" and was summarised anyway, so "O artigo não
   contém informações acessíveis" reached the clipping. Worse, without clearing
   state between articles the second article from a domain came back as a 414-char
   Cloudflare shell, which is long enough to look like content.

See DECISOES.md for the decisions behind this.
"""

import time
import json
import re
from typing import List, Dict, Tuple, Optional
from datetime import datetime, timezone

import trafilatura
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException, TimeoutException

# Minimum body length. Measured over the 53 real articles, "shorter than this OR a
# block marker" catches all 8 genuine failures without discarding a correct article.
# Anything between 500 and 948 gives the same result on that sample — the range is
# empty — so this is judgement inside a measured interval, not a tuned number.
MIN_BODY_CHARS = 500

# Chrome is recycled every N articles: reuse is safe with state cleared, but a
# browser kept alive for 90 navigations grows without bound.
RECYCLE_EVERY = 15

PAGE_LOAD_TIMEOUT = 30        # seconds, per navigation
WRAPPER_RESOLVE_TIMEOUT = 15  # seconds to wait for Google's redirect

# Reusing one browser is fast, and it is also what trips bot detection: a site that
# answers with a challenge has marked the SESSION, not the address. Measured on six
# Data Center Dynamics articles — the most-used source in the clipping:
#
#   same driver, back to back ................ 1/5 usable
#   same driver, 20s pause between requests .. 1/5 usable, 82s
#   fresh driver per request ................. 4/5 usable, 7s
#
# Waiting does not help; a new Chrome does, and cheaply. So the driver is reused by
# default and recycled only when a page comes back blocked, paying the respawn just
# on the articles that need it.
BLOCK_RETRIES = 1

# A page that is a Cloudflare challenge or a paywall rather than an article.
# Challenge pages were the most frequent failure in the sample (6 cases), ahead of
# paywalls (2).
BLOCK_MARKERS = [
    # Cloudflare and similar challenge pages
    "verificação de segurança", "checking your browser", "just a moment",
    "enable javascript and cookies", "executando verificação",
    # Paywalls and subscription pitches. "com sua assinatura" is here because of a
    # real case: BNamericas returned 620 characters that were the headline, the
    # standfirst, and then the sales pitch — "+11.000 projetos", "+24.000 empresas",
    # "+83.000 contatos-chave". Above the length threshold, and every one of those
    # numbers would have been summarised as if it described the data centre.
    "com sua assinatura", "assine para continuar", "assine e tenha acesso",
    "conteúdo exclusivo para assinantes", "faça login para continuar",
    "este conteúdo é exclusivo", "already a subscriber",
]


# ─────────────────────────────────────────────────────────────────────
# Driver
# ─────────────────────────────────────────────────────────────────────

# The browser's own user-agent minus "Headless", found once per run (see _build).
_AGENTE: Optional[str] = None


class DriverPool:
    """
    One Chrome, reused across articles, with state cleared between them.

    Clearing state is not optional. Without it the second article from a domain
    came back as a 414-character Cloudflare shell while the first returned 17,377
    characters — and the old pipeline accepted that silently and summarised it.
    """

    def __init__(self, headless: bool = True, recycle_every: int = RECYCLE_EVERY):
        self.headless = headless
        self.recycle_every = recycle_every
        self.driver = None
        self._served = 0

    def _opcoes(self, agente: Optional[str] = None) -> Options:
        opts = Options()
        if self.headless:
            opts.add_argument("--headless")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--disable-dev-shm-usage")
        # "eager" returns once the DOM is ready instead of waiting for every image
        # and tracker. Three of twenty URLs, including Valor and g1, timed out at
        # 60s under the default strategy and loaded in 4-13s under this one.
        opts.page_load_strategy = "eager"
        if agente:
            opts.add_argument(f"--user-agent={agente}")
        return opts

    def _agente(self) -> Optional[str]:
        """
        The installed Chrome's user-agent, minus the "Headless" marker.

        The browser used to announce itself as Chrome 114, hard-coded, while the
        installed Chrome was years newer — an identity no real visitor has. It now
        reports its true version without "Headless", the word sites block on.

        It is passed as a launch flag, not set afterwards through CDP. The CDP
        override made Chrome stop sending its client hints (sec-ch-ua) altogether
        — measured 28 set 2026 against a local server — and "Chrome 153 with no
        client hints" is itself an identity no real Chrome has. The flag changes
        the string and leaves the hints alone. The price is one short extra launch
        per run, to read the version.
        """
        global _AGENTE
        if _AGENTE is None and self.headless:
            try:
                sonda = webdriver.Chrome(options=self._opcoes())
                try:
                    _AGENTE = sonda.execute_script("return navigator.userAgent") \
                        .replace("HeadlessChrome", "Chrome")
                finally:
                    sonda.quit()
            except Exception as e:
                print(f"⚠️  Não consegui ler o user-agent do Chrome ({type(e).__name__}); "
                      f"a coleta segue com o padrão.")
                _AGENTE = ""
        return _AGENTE or None

    def _build(self):
        # The driver is found by Selenium Manager, built into Selenium since 4.6: it
        # matches the installed Chrome and downloads the driver when needed. The
        # separate webdriver-manager package did the same job and was one more
        # dependency to fall out of step with Chrome (removed 28 set 2026).
        driver = webdriver.Chrome(options=self._opcoes(self._agente()))
        driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
        return driver

    def get(self):
        """Return a ready driver, recycling it when it has served enough articles."""
        if self.driver is not None and self._served >= self.recycle_every:
            self.close()
        if self.driver is None:
            self.driver = self._build()
            self._served = 0
        self._served += 1
        return self.driver

    def reset_state(self):
        """Clear cookies and storage so one article cannot contaminate the next."""
        if self.driver is None:
            return
        try:
            self.driver.delete_all_cookies()
            self.driver.execute_script(
                "try { window.localStorage.clear(); window.sessionStorage.clear(); } catch (e) {}"
            )
        except WebDriverException:
            # A driver too broken to clear state is too broken to reuse.
            self.close()

    def close(self):
        if self.driver is not None:
            try:
                self.driver.quit()
            except WebDriverException:
                pass
            self.driver = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


def resolve_google_wrapper(driver, url: str) -> Tuple[str, bool]:
    """
    Follow Google News's redirect to the real article URL.

    Replaces the old flat sleep(2.0), which was not enough and left 3 of 53 items
    pointing at news.google.com. Waits for the host to change instead of guessing
    at a duration, and reports when it does not.

    Returns:
        (url, resolved)
    """
    if "news.google.com" not in url:
        return url, True

    deadline = time.time() + WRAPPER_RESOLVE_TIMEOUT
    current = url
    while time.time() < deadline:
        try:
            current = driver.current_url
        except (WebDriverException, TimeoutException):
            # Reading the URL is where production actually blocks, waiting for the
            # article behind the wrapper. Keep what we have rather than die here.
            break
        if "news.google.com" not in current:
            return current, True
        time.sleep(0.25)

    return current, False


# ─────────────────────────────────────────────────────────────────────
# Extraction
# ─────────────────────────────────────────────────────────────────────

HEAD_CHARS = 1200


def looks_blocked(text: str) -> Optional[str]:
    """
    Return the block marker found near the START of the text, if any.

    A marker at the top means the page IS the block: a Cloudflare challenge or a
    paywall that gave nothing away. Those articles are discarded.
    """
    head = text[:HEAD_CHARS].lower()
    for marker in BLOCK_MARKERS:
        if marker in head:
            return marker
    return None


def cortar_no_paywall(text: str) -> Tuple[str, Optional[str]]:
    """
    Cut a leaky paywall off the end of an article, and say that it was cut.

    The other shape of paywall gives three or four paragraphs away and then
    starts selling. The body is then long past the minimum and the marker sits
    at character 2,000, outside the window looks_blocked reads — so the sales
    pitch went into the summary. That is the BNamericas case that put
    "+11.000 projetos, +24.000 empresas, +83.000 contatos-chave" one step away
    from being summarised as if it described a data centre.

    What is above the pitch is real reporting and is kept.

    Returns:
        (text, marker) — marker is None when nothing was cut.
    """
    baixo = text.lower()
    corte, achado = None, None
    for marker in BLOCK_MARKERS:
        posicao = baixo.find(marker, HEAD_CHARS)
        if posicao >= 0 and (corte is None or posicao < corte):
            corte, achado = posicao, marker

    if corte is None:
        return text, None
    return text[:corte].rstrip(), achado


def extract_body(html: str) -> str:
    """
    Pull the article body out of the page HTML.

    favor_precision drops the neighbouring headlines that leak in on portal pages —
    on one Valor article the default returned 1,322 characters of which about 60%
    were unrelated headlines carrying three R$ figures. It also drops the headline
    and standfirst, which do carry real numbers, so those come back through the
    metadata: 'excerpt' (the standfirst) is present on 44 of 53 articles, and
    without it one item lost the "US$ 2,3 bilhões" and "8,25%" its summary used.
    """
    if not html:
        return ""

    extracted = trafilatura.extract(
        html,
        output_format="json",
        favor_precision=True,
        with_metadata=True,
        include_comments=False,
        include_tables=True,
    )
    if not extracted:
        return ""

    try:
        data = json.loads(extracted)
    except json.JSONDecodeError:
        return ""

    title = (data.get("title") or "").strip()
    excerpt = (data.get("excerpt") or "").strip()
    text = (data.get("text") or "").strip()

    # The standfirst is often repeated as the opening line of the body.
    if excerpt and excerpt[:60] in text[:400]:
        excerpt = ""

    return "\n\n".join(part for part in (title, excerpt, text) if part)


# Publication date. The cascade is the article meta tag, then JSON-LD, then the
# older meta names. A fourth route through <time datetime> was measured and
# dropped: zero additional coverage, and it picks up comment and sidebar stamps.
_META_DATE_PATTERNS = [
    r'<meta[^>]+property=["\']article:published_time["\'][^>]+content=["\']([^"\']+)["\']',
    r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']article:published_time["\']',
]
_META_NAME_PATTERNS = [
    r'<meta[^>]+name=["\'](?:date|pubdate|DC\.date\.issued|publish-date)["\'][^>]+content=["\']([^"\']+)["\']',
    r'<meta[^>]+itemprop=["\']datePublished["\'][^>]+content=["\']([^"\']+)["\']',
]


def _parse_date(value: str) -> Optional[datetime]:
    if not value:
        return None
    text = value.strip().replace("Z", "+00:00")
    so_o_dia = bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", text))
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        match = re.match(r"(\d{4}-\d{2}-\d{2})", text)
        if not match:
            return None
        try:
            dt = datetime.fromisoformat(match.group(1))
        except ValueError:
            return None
        so_o_dia = True
    if dt.tzinfo is None:
        # "2026-09-28T00:00:00" with no offset is a date written as a timestamp.
        so_o_dia = so_o_dia or (dt.hour, dt.minute, dt.second) == (0, 0, 0)
        dt = dt.replace(tzinfo=timezone.utc)
    if so_o_dia:
        # A page that gives only the day means that day. Read as midnight UTC it
        # is 21h the evening before in Brasília, and the PDF and the date window
        # both moved it back a day. Noon UTC is the same day anywhere in the
        # Americas and Europe.
        dt = dt.replace(hour=12)
    return dt


def _dates_from_jsonld(html: str):
    """Yield every datePublished / dateCreated found in JSON-LD blocks."""
    for block in re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html, re.S | re.I,
    ):
        try:
            payload = json.loads(block.strip())
        except json.JSONDecodeError:
            continue

        pending = [payload]
        while pending:
            node = pending.pop()
            if isinstance(node, list):
                pending.extend(node)
            elif isinstance(node, dict):
                for key in ("datePublished", "dateCreated"):
                    if isinstance(node.get(key), str):
                        yield node[key]
                for key in ("@graph", "mainEntity", "mainEntityOfPage"):
                    if key in node:
                        pending.append(node[key])


def extract_published_date(html: str) -> Optional[datetime]:
    """
    Read the publication date from the page itself.

    Google News reported a 2012 article with a recent date; the page did not.

    Coverage measured in the real pipeline, over the 53 articles of the 21/09
    edition: 38 of the 47 pages that loaded, 81%. The 90.6% that used to be
    written here came from the investigation and was not reproducible against the
    pipeline — DECISOES.md says so explicitly, and this docstring was repeating
    the number it warns against.
    """
    if not html:
        return None

    for pattern in _META_DATE_PATTERNS:
        match = re.search(pattern, html, re.I)
        if match:
            parsed = _parse_date(match.group(1))
            if parsed:
                return parsed

    for value in _dates_from_jsonld(html):
        parsed = _parse_date(value)
        if parsed:
            return parsed

    for pattern in _META_NAME_PATTERNS:
        match = re.search(pattern, html, re.I)
        if match:
            parsed = _parse_date(match.group(1))
            if parsed:
                return parsed

    return None


# ─────────────────────────────────────────────────────────────────────
# Orchestration
# ─────────────────────────────────────────────────────────────────────

def _fetch_once(pool: DriverPool, url: str) -> Dict:
    """One navigation: fetch the page and report what came back."""
    out = {"html": "", "url": url, "resolved": False, "problem": None}

    driver = pool.get()
    pool.reset_state()

    try:
        driver.get(url)
    except TimeoutException:
        # "eager" plus a page load timeout means a slow page still leaves usable
        # HTML behind; carry on and read what loaded.
        out["problem"] = "timeout no carregamento"
    except WebDriverException as e:
        out["problem"] = f"navegação falhou ({type(e).__name__})"
        pool.close()
        return out

    real_url, resolved = resolve_google_wrapper(driver, url)
    out["url"] = real_url
    out["resolved"] = resolved
    if not resolved:
        out["problem"] = "redirecionamento do Google News não resolveu"

    # In production the block lands here rather than on get(), so this read is
    # protected: an escaping exception used to kill the driver and cost a respawn.
    try:
        out["html"] = driver.page_source
    except (WebDriverException, TimeoutException) as e:
        out["problem"] = f"não consegui ler a página ({type(e).__name__})"
        pool.close()

    return out


def scrape_article(pool: DriverPool, url: str) -> Dict:
    """
    Fetch one article, retrying with a fresh browser session if it comes back blocked.

    Returns a dict with: body, url, page_date, resolved, problem.
    """
    result = {"body": "", "url": url, "page_date": None, "resolved": False, "problem": None}

    for attempt in range(BLOCK_RETRIES + 1):
        if attempt > 0:
            # The site has marked this browser session, and waiting does not clear
            # it — only a new Chrome does. See BLOCK_RETRIES above for the numbers.
            pool.close()

        fetched = _fetch_once(pool, url)
        result["url"] = fetched["url"]
        result["resolved"] = fetched["resolved"]
        result["problem"] = fetched["problem"]

        html = fetched["html"]
        if not html:
            continue

        body = extract_body(html)
        result["page_date"] = extract_published_date(html)

        marker = looks_blocked(body) or looks_blocked(html)
        if marker:
            result["problem"] = f"página de bloqueio/paywall ({marker!r})"
            continue

        body, cortado = cortar_no_paywall(body)
        if len(body) < MIN_BODY_CHARS:
            result["problem"] = (
                f"corpo curto demais ({len(body)} caracteres)"
                + (f", depois de cortar o anúncio de assinatura ({cortado!r})"
                   if cortado else "")
            )
            continue

        result["body"] = body
        result["problem"] = (f"anúncio de assinatura cortado do fim ({cortado!r})"
                             if cortado else None)
        return result

    return result


def scrape_articles(items: List[Dict]) -> List[Dict]:
    """
    Fetch every item's body, annotating each with what was found.

    Adds 'body', 'page_date' and, when something went wrong, 'scrape_problem'.
    Nothing is dropped here — main.py decides — but nothing fails quietly either.
    """
    # Items held back as a group's reserve are not fetched unless the group's
    # first choices come back empty; see promover_reservas in the deduplicator.
    a_coletar = [item for item in items if not item.get("_reserva")]
    problems: List[str] = []
    unresolved = 0

    with DriverPool() as pool:
        for i, item in enumerate(a_coletar, 1):
            try:
                found = scrape_article(pool, item["url"])
            except Exception as e:
                found = {"body": "", "url": item["url"], "page_date": None,
                         "resolved": False,
                         "problem": f"erro inesperado ({type(e).__name__}: {e})"}

            item["url"] = found["url"]
            item["body"] = found["body"]
            item["page_date"] = found["page_date"]
            if not found["resolved"]:
                unresolved += 1
            if found["problem"]:
                item["scrape_problem"] = found["problem"]
                problems.append(
                    f"{item.get('source', '?')}: {found['problem']} — {item['url'][:70]}"
                )

            status = "ok" if found["body"] else "FALHOU"
            print(f"[{i}/{len(a_coletar)}] {status} ({len(found['body'])} chars) {item['url'][:70]}")

    if problems:
        print(f"\n⚠️  {len(problems)} de {len(a_coletar)} notícias tiveram problema na coleta:")
        for p in problems:
            print(f"     - {p}")
    if unresolved:
        print(f"⚠️  {unresolved} URLs do Google News não resolveram para a matéria real. "
              f"Sem a URL real não há data de página para conferir.")

    return items


if __name__ == "__main__":
    # Runs against Google News wrappers, which is what the pipeline actually passes.
    import urllib.parse
    import feedparser

    query = urllib.parse.quote_plus("data center")
    feed = feedparser.parse(
        f"https://news.google.com/rss/search?q={query}&hl=pt-BR&gl=BR&ceid=BR:pt-BR"
    )
    sample = [
        {"title": e.title, "url": e.link,
         "source": getattr(getattr(e, "source", None), "title", "?")}
        for e in feed.entries[:5]
    ]

    print(f"=== Testando {len(sample)} wrappers do Google News ===")
    started = time.time()
    results = scrape_articles(sample)
    elapsed = time.time() - started

    print(f"\n=== Resultado em {elapsed:.1f}s ({elapsed / max(len(sample), 1):.1f}s por artigo) ===")
    for item in results:
        print(f"  {len(item['body']):6} chars | data: {item['page_date']} | {item['url'][:60]}")
