import json
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape
from dotenv import load_dotenv

load_dotenv()

# There used to be a PKG_CONFIG_PATH hook here, and three documents told
# Apple-Silicon users to set it in .env. It never did anything: WeasyPrint loads
# pango and cairo at run time through cffi's dlopen, which does not read
# PKG_CONFIG_PATH (that variable is for compiling). Removed 28 set 2026, with the
# advice; the supported install is the conda one in README.md, Step 3.
from weasyprint import HTML

# Running this file directly is the documented way to rebuild only the PDF, so the
# project root has to be importable either way.
_SERVICES_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SERVICES_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from services.utils.archive import archive_final, data_da_edicao, inicio_da_janela
from services.utils.datetime_utils import format_datetime_br
from services.utils.fontes import tier_of
from services import empresas, overrides

# ─────────────────────────────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────────────────────────────
PROJECT_ROOT = _PROJECT_ROOT
JSON_PATH = os.path.join(PROJECT_ROOT, "output", "clippings.json")
CONFIGS_DIR = os.path.join(PROJECT_ROOT, "configs")
OUTPUT_PDF = os.path.join(PROJECT_ROOT, "output", "clippings_output.pdf")

# The order the sections are printed in. It is defined here, not only in the
# template, because "first appearance" of a company is defined by reading order.
ORDEM_CATEGORIAS = ["clientes", "competidores", "governo", "inovação", "outros"]
CATEGORIA_PADRAO = "outros"


# ─────────────────────────────────────────────────────────────────────
# 1) Load, correct, and put in reading order
# ─────────────────────────────────────────────────────────────────────

def _quando(item: Dict) -> str:
    """
    The date to show and to sort by, as text.

    The page's own metadata wins over the feed's. Google News reported a 2012
    article about AMD as this week's news; the page did not. When the page carries
    no date, the feed's is what there is.
    """
    return str(item.get("page_date") or item.get("pubDate") or "")


def _instante(item: Dict) -> Optional[datetime]:
    """The moment the article was published, in a comparable form."""
    texto = _quando(item)
    if not texto:
        return None
    try:
        quando = datetime.fromisoformat(texto)
    except ValueError:
        return None
    return quando if quando.tzinfo else quando.replace(tzinfo=timezone.utc)


def _chave_de_ordem(item: Dict):
    """Section order, then highlights, then most recent first."""
    categoria = item.get("category", CATEGORIA_PADRAO)
    indice = ORDEM_CATEGORIAS.index(categoria) if categoria in ORDEM_CATEGORIAS \
        else len(ORDEM_CATEGORIAS)
    quando = _instante(item)
    # Sorted by instant, not by the text of the date. The stored strings keep the
    # page's own offset — "-03:00" for a Brazilian outlet, "+00:00" for a foreign
    # one — so comparing them as text put 21/09 23:00 BRT after 22/09 01:00 UTC,
    # which is the same moment plus two hours, in the wrong order.
    return (indice, not item.get("highlight", False), quando is None,
            -(quando.timestamp() if quando else 0.0))


def load_clippings(json_filepath: str) -> List[Dict]:
    """
    Read the edition, apply the manual corrections, and put it in reading order.

    Everything that decides what the reader sees happens here, in this order:
    corrections from configs/overrides.json, then the category a template can
    actually draw, then the order, then the company boxes — which depend on the
    order, because a box appears at a company's first appearance.
    """
    with open(json_filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    data, relatorio = overrides.aplicar(data)
    overrides.relatar(relatorio)

    # The source gate runs at search time, where it is cheapest. It runs again
    # here because rebuilding the PDF from an older clippings.json skips that
    # stage entirely — which is how, in the test of this very change, the SEO
    # filler titled "… Sobretaxa de 10% [2026]" came back into the index of a
    # rebuilt edition. Only tier 4 is refused; an unlisted outlet is tier 3 and
    # goes through, so a story added by hand is never blocked by this.
    bloqueadas = [item for item in data
                  if tier_of(item.get("source", ""), item.get("title", "")) >= 4]
    if bloqueadas:
        print(f"⚠️  {len(bloqueadas)} notícias de fonte tier 4 retiradas na montagem "
              f"do PDF (conteúdo de SEO / sem redação identificável):")
        for item in bloqueadas:
            print(f"     - {item.get('source', '?')}: {item.get('title', '')[:60]}")
        bloqueadas_urls = {item.get("url") for item in bloqueadas}
        data = [item for item in data if item.get("url") not in bloqueadas_urls]

    # The template draws five sections. Anything else used to be dropped with no
    # message: the article simply was not in the PDF and nothing said so.
    fora = [item for item in data if item.get("category") not in ORDEM_CATEGORIAS]
    for item in fora:
        print(f"⚠️  Categoria {item.get('category')!r} não existe no PDF; "
              f"'{item.get('title', '')[:50]}' foi para {CATEGORIA_PADRAO}.")
        item["category"] = CATEGORIA_PADRAO

    # The 🚨 block used to be printed once, in the middle of a full run, and never
    # again. Whoever only rebuilt the PDF after correcting it never saw it. It is
    # repeated on every build, minus the summaries already rewritten by hand.
    suspeitos = [item for item in data
                 if item.get("numeros_nao_conferidos") and not item.get("override_resumo")]
    if suspeitos:
        print(f"🚨 {len(suspeitos)} resumos citam número que não achei na matéria — "
              f"confira cada um antes de enviar:")
        for item in suspeitos:
            print(f"     - {item.get('source', '?')} — {item.get('title', '')[:50]}\n"
                  f"       não achei: {', '.join(item['numeros_nao_conferidos'])}\n"
                  f"       {item.get('url', '')}")

    data.sort(key=_chave_de_ordem)

    # Anchor ids follow reading order, so the index links land where they should.
    for idx, item in enumerate(data, start=1):
        item["id"] = f"item-{idx}"
        item["data_exibida"] = _data_br(_quando(item))

    data, relatorio_empresas = empresas.atribuir_fichas(data)
    empresas.relatar(relatorio_empresas)

    return data


# ─────────────────────────────────────────────────────────────────────
# 2) Jinja2
# ─────────────────────────────────────────────────────────────────────

def _data_br(valor) -> str:
    """Render a stored date as "21 Set", tolerating text, datetime or nothing."""
    if not valor:
        return ""
    if isinstance(valor, datetime):
        return format_datetime_br(valor)
    try:
        return format_datetime_br(datetime.fromisoformat(str(valor)))
    except ValueError:
        # Editions produced before the date travelled whole already hold "21 Set".
        return str(valor)


def init_jinja2_environment(configs_dir: str) -> Environment:
    """Configure Jinja2 to load HTML templates from the configs directory."""
    env = Environment(
        loader=FileSystemLoader(configs_dir),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["data_br"] = _data_br
    return env


# ─────────────────────────────────────────────────────────────────────
# 3) Render
# ─────────────────────────────────────────────────────────────────────

def render_html(env: Environment, template_name: str, items: List[Dict],
                today: Optional[datetime] = None, inicio_janela=None) -> str:
    """
    Render the template. `today` exists so a rebuild can be dated on purpose.

    `inicio_janela` is the first day the edition covers. When it is not known —
    editions closed before 28 set 2026 — the header falls back to seven days.
    """
    template = env.get_template(template_name)
    return template.render(
        items=items,
        today=today or datetime.now(),
        inicio_janela=inicio_janela,
        ordered_categories=ORDEM_CATEGORIAS,
        timedelta=timedelta,
    )


LOGO_PATH = os.path.join(CONFIGS_DIR, "247.original.jpg")


def generate_pdf_from_html(html_string: str, output_path: str) -> None:
    """
    Write the HTML to a PDF.

    base_url=CONFIGS_DIR is what makes the logo's relative path resolve.

    The logo is in the repository (since 28 set 2026). If it goes missing,
    WeasyPrint does not complain: it drops the <img> and returns a valid
    document, exit code 0, nothing on stderr — measured on 23 set 2026. That is
    how an edition reaches the client with an empty header, so the warning is
    printed here, by us.
    """
    if not os.path.exists(LOGO_PATH):
        print("⚠️  configs/247.original.jpg não está aqui. O PDF vai sair SEM a "
              "logo no cabeçalho.\n"
              "     Ela vem no repositório; para recuperar: "
              "git checkout configs/247.original.jpg\n"
              "     Para conferir a edição enquanto trabalha, tudo bem. Para "
              "ENVIAR ao cliente, não.")

    HTML(string=html_string, base_url=CONFIGS_DIR).write_pdf(output_path)


# ─────────────────────────────────────────────────────────────────────
# 4) Orchestration
# ─────────────────────────────────────────────────────────────────────

def build_pdf(json_path: str = JSON_PATH, output_pdf: str = OUTPUT_PDF) -> str:
    """
    Build the PDF from output/clippings.json and archive what was built.

    Returns the PDF's path, or "" when nothing was built — no edition yet, or an
    overrides.json that cannot be read. Nothing is archived in either case.
    """
    if not os.path.exists(json_path):
        # A fresh clone has no edition yet, and this used to end in a raw
        # FileNotFoundError traceback — the first thing a new person saw.
        print(f"⛔ Ainda não existe nenhuma edição em {os.path.relpath(json_path, PROJECT_ROOT)}.\n"
              f"   Este comando só REFAZ o PDF de uma edição que já rodou. Para gerar a "
              f"primeira: python main.py")
        return ""
    try:
        clippings = load_clippings(json_path)
    except overrides.OverridesIlegivel as e:
        print(f"⛔ O PDF NÃO foi gerado: configs/{e}\n"
              f"   Corrija o arquivo e rode de novo: python services/pdf_builder.py")
        return ""

    env = init_jinja2_environment(CONFIGS_DIR)

    # The header dates the edition, not the build. Rebuilding Friday's clipping on
    # Monday used to print "Week 14 Sep – 21 Sep" over Friday's news.
    fechamento = data_da_edicao()
    if fechamento is None:
        print("⚠️  Não sei quando esta edição foi fechada (output/edicao_atual.json "
              "não existe); o cabeçalho vai sair com a data de hoje.")
    html_str = render_html(env, "clipping_template.html", clippings, today=fechamento,
                           inicio_janela=inicio_da_janela())
    generate_pdf_from_html(html_str, output_pdf)

    com_metricas = sum(1 for item in clippings if (item.get("ficha") or {}).get("ratios"))
    com_caixa = sum(1 for item in clippings if item.get("fichas_empresa"))
    print(f"⚙️  PDF gerado em {output_pdf}")
    print(f"   {len(clippings)} notícias · {com_metricas} com caixa de métricas · "
          f"{com_caixa} com ficha de empresa")

    # Archive the version that was actually built — this is the one that gets
    # sent, corrections and all, which is not what is on disk.
    archive_final(json_path, output_pdf, items=clippings)

    return output_pdf


if __name__ == "__main__":
    # A non-zero exit when nothing was built, so a script or a person checking
    # "$?" does not take a refusal for a PDF.
    sys.exit(0 if build_pdf() else 1)
