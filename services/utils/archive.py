# services/utils/archive.py

"""
Archiving of weekly editions.

Until now every run overwrote output/clippings.json and the PDF, so no past
edition survived. That destroyed the only record of which items a human
judged to be duplicates, irrelevant or important — the ground truth we need to tell
whether a change to the pipeline actually improved anything.

Two snapshots per edition, in output/archive/YYYY-MM-DD/:

  clippings.raw.json    what the pipeline produced, before any manual editing.
                        Frozen: never overwritten.
  clippings.final.json  what was actually built into the PDF, after manual editing.
                        Overwritten on every rebuild, so it always holds the last one.
  <nome do Drive>.pdf   the PDF of that last build, under the name it is filed with
                        in the company's Drive (see nome_do_pdf).

The difference between raw and final is the human judgement, captured for free on
every run.
"""

import os
import re
import json
import shutil
import unicodedata
from typing import List, Dict, Optional, Set, Tuple
from datetime import date, datetime, timedelta

# Paths resolved from this file, so archiving works whether the caller runs
# main.py from the project root or services/pdf_builder.py directly.
UTILS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(UTILS_DIR))
ARCHIVE_DIR = os.path.join(PROJECT_ROOT, "output", "archive")


def _relativo(caminho: str) -> str:
    """Relative to the project for display; on Windows, across drives, as is."""
    try:
        return os.path.relpath(caminho, PROJECT_ROOT)
    except ValueError:
        return caminho

RAW_NAME = "clippings.raw.json"
FINAL_NAME = "clippings.final.json"

# The name the edition is filed under in the company's Drive folder, "Clippings
# Semanais", copied from the files already there:
#
#   2026.09.21 Clipping Atualização Semanal (14_09 - 21_09 às 11h00).pdf
#   2026.01.05 Clipping Atualização Quinzenal (22_12_2025 - 05_01_2026 às 13h13).pdf
#
# The date of the closing; the kind of edition, which is a decision (--quinzenal)
# and not a count of days; the day of the PREVIOUS edition and the day of this
# one, with the year only when the two fall in different years; and the time of
# the closing, with no leading zero on the hour ("9h30").
#
# The first date is the previous edition's, not the first day searched. Read off
# the Drive's own files: the edition of 14/09 is named "(08_09 - 14_09 …)", after
# the Tuesday edition of 08/09, while its header says "Week 07 Sep". The two only
# differ when an edition comes out less than a week after the one before.
DIAS_DA_QUINZENAL = 14
SEMANAL, QUINZENAL = "Semanal", "Quinzenal"
PADRAO_DO_NOME = re.compile(r"^\d{4}\.\d{2}\.\d{2} +Clipping Atualização .*\.pdf$")


def nome_do_pdf(fechamento: datetime, desde: Optional[date] = None,
                tipo: Optional[str] = None) -> str:
    """
    The Drive file name of the edition closed at `fechamento`.

    `desde` is the previous edition's day (or, with no previous edition, the
    first day searched). `tipo` is Semanal or Quinzenal; editions recorded before
    it was stored fall back to counting the days.
    """
    desde = desde or (fechamento - timedelta(days=7)).date()
    fim = fechamento.date()
    if tipo not in (SEMANAL, QUINZENAL):
        tipo = QUINZENAL if (fim - desde).days >= DIAS_DA_QUINZENAL else SEMANAL
    formato = "%d_%m_%Y" if desde.year != fim.year else "%d_%m"
    return (f"{fechamento:%Y.%m.%d} Clipping Atualização {tipo} "
            f"({desde.strftime(formato)} - {fim.strftime(formato)} "
            f"às {fechamento.hour}h{fechamento.minute:02d}).pdf")



# When the edition was closed — that is, when the pipeline last collected news.
# It is written once, by archive_raw, and read by everything that needs to know
# which edition is being worked on.
#
# Two defects came from not having it. The archive folder was keyed on the date of
# the RUN, so an edition collected on Friday and rebuilt on Monday left the raw
# snapshot in one folder and the final version in another, and the raw-to-final
# difference — the reason archiving exists — never ran. And the PDF header was
# built from datetime.now(), so that Monday rebuild printed "Week 14 Sep – 21 Sep"
# over Friday's news on every page.
EDICAO_PATH = os.path.join(PROJECT_ROOT, "output", "edicao_atual.json")


def registrar_edicao(when: datetime, inicio_janela: Optional[date] = None,
                     desde: Optional[date] = None, tipo: Optional[str] = None) -> None:
    """
    Record when this edition was closed and what it covers.

    inicio_janela — the first day searched, printed in the PDF header;
    desde, tipo  — the previous edition's day and Semanal/Quinzenal, for the
                   Drive file name (see nome_do_pdf).
    """
    os.makedirs(os.path.dirname(EDICAO_PATH), exist_ok=True)
    registro = {"fechamento": when.isoformat(timespec="seconds")}
    if inicio_janela:
        registro["inicio_janela"] = inicio_janela.isoformat()
    if desde:
        registro["desde"] = desde.isoformat()
    if tipo:
        registro["tipo"] = tipo
    with open(EDICAO_PATH, "w", encoding="utf-8") as f:
        json.dump(registro, f)


def _registro() -> Dict:
    try:
        with open(EDICAO_PATH, "r", encoding="utf-8") as f:
            dados = json.load(f)
    except (OSError, ValueError):
        return {}
    return dados if isinstance(dados, dict) else {}


def nome_da_edicao_atual() -> str:
    """The Drive file name of the edition in output/edicao_atual.json."""
    registro = _registro()
    try:
        desde = date.fromisoformat(registro["desde"])
    except (KeyError, TypeError, ValueError):
        desde = inicio_da_janela()
    return nome_do_pdf(data_da_edicao() or datetime.now(), desde, registro.get("tipo"))


def inicio_da_janela() -> Optional[date]:
    """The first civil day the current edition covers, or None if not recorded."""
    try:
        with open(EDICAO_PATH, "r", encoding="utf-8") as f:
            return date.fromisoformat(json.load(f)["inicio_janela"])
    except (FileNotFoundError, json.JSONDecodeError, KeyError, TypeError, ValueError):
        return None


def data_da_edicao() -> Optional[datetime]:
    """When the edition being worked on was closed, or None if unknown."""
    try:
        with open(EDICAO_PATH, "r", encoding="utf-8") as f:
            return datetime.fromisoformat(json.load(f)["fechamento"])
    except (FileNotFoundError, json.JSONDecodeError, KeyError, TypeError, ValueError):
        return None


# Two archive folders closer together than this are the same edition run twice,
# not the previous one. Editions are weekly, so the real previous one sits six or
# seven days back; a rerun the next morning must not treat its own first attempt
# as something the reader already received.
DIAS_ENTRE_EDICOES = 3


def url_chave(url: str) -> str:
    """The same article is the same URL up to a fragment or a trailing slash."""
    return (url or "").split("#", 1)[0].rstrip("/")


def edicao_anterior(antes_de: Optional[datetime] = None) -> Tuple[Optional[str], Set[str]]:
    """
    The last edition actually built into a PDF, and the URLs it carried.

    Only folders holding clippings.final.json count: a raw snapshot with no final
    means the PDF was never built, so nothing reached a reader. The final is what
    was printed — after the manual corrections — so a story removed by hand last
    week is not in it, and stays governed by its own 'removidas' entry.

    Returns (folder name, set of URL keys), or (None, empty set) when there is no
    earlier edition to compare against.
    """
    antes_de = antes_de or datetime.now()
    limite = (antes_de - timedelta(days=DIAS_ENTRE_EDICOES)).date()
    if not os.path.isdir(ARCHIVE_DIR):
        return None, set()

    candidatas = []
    for nome in os.listdir(ARCHIVE_DIR):
        try:
            dia = datetime.strptime(nome, "%Y-%m-%d").date()
        except ValueError:
            continue
        if dia <= limite and os.path.exists(os.path.join(ARCHIVE_DIR, nome, FINAL_NAME)):
            candidatas.append((dia, nome))
    if not candidatas:
        return None, set()

    _, nome = max(candidatas)
    itens = _load(os.path.join(ARCHIVE_DIR, nome, FINAL_NAME)) or []
    return nome, {url_chave(i.get("url", "")) for i in itens if i.get("url")}


def _edition_dir(when: Optional[datetime] = None) -> str:
    """Return (and create) the archive folder for a given date."""
    when = when or data_da_edicao() or datetime.now()
    path = os.path.join(ARCHIVE_DIR, when.strftime("%Y-%m-%d"))
    os.makedirs(path, exist_ok=True)
    return path


def archive_raw(items: List[Dict], when: Optional[datetime] = None,
                inicio_janela: Optional[date] = None, desde: Optional[date] = None,
                tipo: Optional[str] = None) -> str:
    """
    Freeze the pipeline's raw output for this edition.

    Never overwrites: a second run on the same day is written alongside the first
    with a time suffix. Losing a raw snapshot is exactly the failure this module
    exists to prevent.

    Returns:
        str: path of the file written
    """
    when = when or datetime.now()
    # This is the moment the edition was closed; everything downstream dates
    # itself from here rather than from when it happened to run.
    registrar_edicao(when, inicio_janela, desde, tipo)
    folder = _edition_dir(when)
    path = os.path.join(folder, RAW_NAME)

    if os.path.exists(path):
        path = os.path.join(folder, f"clippings.raw.{when.strftime('%H%M%S')}.json")
        print(f"📦 Já existia uma saída crua de hoje; esta vai como {os.path.basename(path)}")

    with open(path, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

    print(f"📦 Saída crua arquivada em {_relativo(path)} ({len(items)} notícias)")
    return path


def archive_final(json_path: str, pdf_path: str, when: Optional[datetime] = None,
                  items: Optional[List[Dict]] = None) -> str:
    """
    Archive the version that was actually built into the PDF.

    Overwritten on each rebuild, so it always reflects the last build — which is
    the version that gets sent. Reports what changed against the raw snapshot.

    `items` is the corrected list the PDF was drawn from. Passing it matters:
    output/clippings.json on disk holds what the pipeline produced, BEFORE
    configs/overrides.json is applied. Copying that file archived a version that
    was never sent, and the raw-to-final difference — the whole point of
    archiving — came out empty every week no matter how much had been corrected.

    Returns:
        str: the archive folder for this edition
    """
    folder = _edition_dir(when)

    if items is not None:
        with open(os.path.join(folder, FINAL_NAME), "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2, default=str)
    elif os.path.exists(json_path):
        shutil.copy2(json_path, os.path.join(folder, FINAL_NAME))
    if os.path.exists(pdf_path):
        # Under the same name as in the Drive, so the archive copy is the file
        # that gets uploaded, and the two can be compared by name. The folder
        # keeps only the last build, as clippings.final.json does: a rebuild at
        # another hour has another name, and two PDFs of one edition side by side
        # leave nobody sure which was sent.
        nome = os.path.basename(pdf_path)
        for antigo in os.listdir(folder):
            normalizado = unicodedata.normalize("NFC", antigo)
            if antigo != nome and (antigo == "clipping.pdf" or PADRAO_DO_NOME.match(normalizado)):
                try:
                    os.remove(os.path.join(folder, antigo))
                except OSError:
                    pass
        shutil.copy2(pdf_path, os.path.join(folder, nome))

    print(f"📦 Edição arquivada em {_relativo(folder)}")
    _report_edits(folder)
    return folder


def _raw_mais_recente(folder: str) -> str:
    """
    The raw snapshot of the LAST run of this edition.

    Raw snapshots are never overwritten, so a second run on the same day lands
    beside the first with a time suffix. Comparing the final version against the
    FIRST one then measures the difference between two pipeline runs and calls it
    human editing: on 22 Sep 2026 two runs overlapped and the report announced
    "3 removed, 4 added, 20 summaries corrected" on an edition nobody had touched.
    """
    try:
        candidatos = [n for n in os.listdir(folder)
                      if n.startswith("clippings.raw") and n.endswith(".json")]
    except OSError:
        candidatos = []
    if not candidatos:
        return os.path.join(folder, RAW_NAME)
    mais_novo = max(candidatos,
                    key=lambda n: os.path.getmtime(os.path.join(folder, n)))
    return os.path.join(folder, mais_novo)


def _load(path: str) -> Optional[List[Dict]]:
    """Read a clippings JSON file, or return None if it is missing or malformed."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _report_edits(folder: str) -> None:
    """
    Print what the manual editing changed between the raw and the final version.

    This is the point of archiving: over the weeks these counts become the record
    of where the pipeline is wrong, and the raw/final pairs become the examples
    that feed the classification and deduplication prompts.
    """
    raw = _load(_raw_mais_recente(folder))
    final = _load(os.path.join(folder, FINAL_NAME))
    if raw is None:
        print("   Sem saída crua desta data para comparar (o pipeline completo não rodou hoje).")
        return
    if final is None:
        print("   Sem versão final legível para comparar.")
        return

    raw_by_url = {item.get("url"): item for item in raw}
    final_by_url = {item.get("url"): item for item in final}

    removed = set(raw_by_url) - set(final_by_url)
    added = set(final_by_url) - set(raw_by_url)
    recategorised = sum(
        1 for url, item in final_by_url.items()
        if url in raw_by_url and item.get("category") != raw_by_url[url].get("category")
    )
    rewritten = sum(
        1 for url, item in final_by_url.items()
        if url in raw_by_url and item.get("summary") != raw_by_url[url].get("summary")
    )
    highlighted = sum(1 for item in final_by_url.values() if item.get("highlight"))

    if not any([removed, added, recategorised, rewritten, highlighted]):
        print("   Nenhuma edição manual em relação à saída crua.")
        return

    print(
        f"   Edição manual: {len(removed)} removidas, {len(added)} incluídas, "
        f"{recategorised} recategorizadas, {rewritten} com resumo corrigido, "
        f"{highlighted} grifadas."
    )


if __name__ == "__main__":
    # Quick standalone test against a throwaway date.
    #
    # The throwaway date is not enough on its own: archive_raw calls
    # registrar_edicao, which rewrites output/edicao_atual.json — the file the
    # PDF reads to date its header. Running this test used to stamp the edition
    # being worked on as 01/01/1999, and the next rebuild of the PDF would carry
    # that date to the client. So the file is saved and put back.
    _edicao_antes = None
    if os.path.exists(EDICAO_PATH):
        with open(EDICAO_PATH, "r", encoding="utf-8") as f:
            _edicao_antes = f.read()

    test_when = datetime(1999, 1, 1)
    sample = [
        {"url": "https://example.com/a", "title": "A", "category": "governo",
         "summary": "resumo A", "highlight": False},
        {"url": "https://example.com/b", "title": "B", "category": "clientes",
         "summary": "resumo B", "highlight": False},
    ]

    raw_path = archive_raw(sample, when=test_when)
    folder = _edition_dir(test_when)

    # Simulate the manual editing: drop B, recategorise and highlight A.
    edited = [dict(sample[0], category="inovação", highlight=True)]
    edited_path = os.path.join(folder, "clippings.edited.json")
    with open(edited_path, "w", encoding="utf-8") as f:
        json.dump(edited, f, ensure_ascii=False, indent=2)

    archive_final(edited_path, pdf_path="/nonexistent.pdf", when=test_when)

    if _edicao_antes is not None:
        with open(EDICAO_PATH, "w", encoding="utf-8") as f:
            f.write(_edicao_antes)
        print("   (output/edicao_atual.json devolvido ao que era antes do teste)")
    elif os.path.exists(EDICAO_PATH):
        os.remove(EDICAO_PATH)

    print(f"\nTeste escreveu em {folder} — apague à mão se quiser.")
