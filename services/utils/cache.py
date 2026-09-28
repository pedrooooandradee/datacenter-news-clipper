# services/utils/cache.py

"""
Per-stage caching, so a failed or unsatisfying run can be resumed instead of paid for twice.

Running the whole pipeline costs API money and up to half an hour of Selenium, which is
why COMANDOS.txt says it only runs with authorisation. That makes the pipeline almost
impossible to improve: tuning deduplication meant re-scraping and re-summarising
everything first.

Every stage writes its output to output/cache/<stage>.json. Passing --from=<stage> to
main.py loads the cache of the stage before it and re-runs from there.

Reading the cache is never automatic. A plain `python main.py` is always a full, fresh
run — reusing last week's RSS results without being asked is how a stale clipping gets
sent. The cache is written on every run so it is there when wanted, and only read when
--from says so.

Each entry stores a fingerprint of the code and config that produced it. When --from
reuses a stage whose fingerprint has changed, it says so loudly rather than quietly
handing back output built by a prompt that no longer exists.
"""

import os
import json
import hashlib
from typing import List, Dict, Optional, Tuple
from datetime import datetime

UTILS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(UTILS_DIR))
CACHE_DIR = os.path.join(PROJECT_ROOT, "output", "cache")


def _relativo(caminho: str) -> str:
    """Relative to the project for display; on Windows, across drives, as is."""
    try:
        return os.path.relpath(caminho, PROJECT_ROOT)
    except ValueError:
        return caminho


# ─────────────────────────────────────────────────────────────────────
# JSON with datetime support
# ─────────────────────────────────────────────────────────────────────
# Items carry a real datetime in 'pubDate' until the summarizer formats it as
# "21 Set", so the cache has to survive both shapes.

def _encode(obj):
    if isinstance(obj, datetime):
        return {"__datetime__": obj.isoformat()}
    raise TypeError(f"Não sei serializar {type(obj).__name__} para o cache")


def _decode(d: Dict):
    if "__datetime__" in d:
        return datetime.fromisoformat(d["__datetime__"])
    return d


# ─────────────────────────────────────────────────────────────────────
# Fingerprints
# ─────────────────────────────────────────────────────────────────────

def file_digest(*paths: str) -> str:
    """
    Short hash of one or more files, used to tell whether the code and config that
    produced a cached stage still look the same.

    Hashing the service module itself (not just the prompt) means a changed model
    name or a changed parsing rule also invalidates the cache.
    """
    h = hashlib.sha256()
    for path in sorted(paths):
        try:
            with open(path, "rb") as f:
                h.update(f.read())
        except FileNotFoundError:
            h.update(b"<ausente>")
    return h.hexdigest()[:12]


# ─────────────────────────────────────────────────────────────────────
# Read and write
# ─────────────────────────────────────────────────────────────────────

def save(stage: str, items: List[Dict], fingerprint: str = "",
         edicao: Optional[Dict] = None) -> str:
    """
    Write a stage's output to the cache. Always called, on every run.

    `edicao` holds what the search was run for: the first day searched
    (inicio_janela), the previous edition's day (desde) and the kind (tipo,
    Semanal or Quinzenal). A run resumed with --from reuses them, so an edition
    rebuilt from its cache keeps its header and its Drive name.
    """
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = os.path.join(CACHE_DIR, f"{stage}.json")
    payload = {
        "stage": stage,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "fingerprint": fingerprint,
        "count": len(items),
        "items": items,
    }
    if edicao:
        payload["edicao"] = {k: (v.isoformat() if hasattr(v, "isoformat") else v)
                             for k, v in edicao.items()}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, default=_encode)
    return path


def load(stage: str, fingerprint: str = "") -> Optional[Tuple[List[Dict], str]]:
    """
    Read a stage's cached output.

    Returns (items, created_at), or None if there is no usable cache. Prints what it
    found either way — a silently missing cache would send the run back to a full,
    paid execution without explanation.
    """
    path = os.path.join(CACHE_DIR, f"{stage}.json")
    if not os.path.exists(path):
        print(f"⚠️  Não há cache da etapa '{stage}' em {_relativo(path)}.")
        return None

    try:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f, object_hook=_decode)
    except json.JSONDecodeError:
        print(f"⚠️  O cache da etapa '{stage}' está corrompido e será ignorado.")
        return None

    items = payload.get("items", [])
    created_at = payload.get("created_at", "data desconhecida")
    print(f"♻️  Reaproveitando cache de '{stage}': {len(items)} itens, gerado em {created_at}")

    # A cache never expires on its own, and the PDF header is built from the date
    # of the BUILD. Resuming from a three-week-old cache therefore produces a
    # document that says "Week <last week> – <today>" over last month's news.
    try:
        idade = (datetime.now() - datetime.fromisoformat(created_at)).days
    except (TypeError, ValueError):
        idade = None
    if idade is not None and idade >= 2:
        print(f"⚠️  Este cache tem {idade} dias. As notícias dentro dele são de "
              f"{idade} dias atrás, e o PDF vai ser datado de hoje.")
        if idade >= 7:
            print(f"⚠️  ATENÇÃO: mais de uma semana. Quase certamente você quer uma "
                  f"execução completa (python main.py, sem --from).")

    stored = payload.get("fingerprint", "")
    if fingerprint and stored and fingerprint != stored:
        print(
            f"⚠️  ATENÇÃO: o código ou o prompt da etapa '{stage}' mudou desde que este "
            f"cache foi gerado ({stored} → {fingerprint})."
        )
        print(
            f"⚠️  Os itens reaproveitados foram produzidos pela versão antiga. "
            f"Para refazer esta etapa, rode com --from={stage}."
        )

    return items, created_at


def edicao_salva(stage: str) -> Optional[Dict]:
    """What a cached stage was searched for (see save), or None for older caches."""
    from datetime import date
    try:
        with open(os.path.join(CACHE_DIR, f"{stage}.json"), "r", encoding="utf-8") as f:
            dados = json.load(f)["edicao"]
        return {"inicio_janela": date.fromisoformat(dados["inicio_janela"]),
                "desde": date.fromisoformat(dados["desde"]),
                "tipo": dados["tipo"] if dados["tipo"] in ("Semanal", "Quinzenal") else "Semanal"}
    except (OSError, ValueError, KeyError, TypeError):
        return None


def clear(stage: Optional[str] = None) -> None:
    """Delete one stage's cache, or all of them."""
    if not os.path.isdir(CACHE_DIR):
        return
    for name in sorted(os.listdir(CACHE_DIR)):
        if not name.endswith(".json"):
            continue
        if stage and name != f"{stage}.json":
            continue
        os.remove(os.path.join(CACHE_DIR, name))
        print(f"🗑️  Cache removido: {name}")


def describe() -> None:
    """Print what is currently in the cache, so --from is an informed choice."""
    if not os.path.isdir(CACHE_DIR) or not os.listdir(CACHE_DIR):
        print("Cache vazio — a próxima execução será completa.")
        return
    print("Cache disponível:")
    for name in sorted(os.listdir(CACHE_DIR)):
        if not name.endswith(".json"):
            continue
        try:
            with open(os.path.join(CACHE_DIR, name), "r", encoding="utf-8") as f:
                payload = json.load(f, object_hook=_decode)
            print(f"  {payload.get('stage','?'):12} {payload.get('count',0):4} itens   "
                  f"{payload.get('created_at','?')}")
        except (json.JSONDecodeError, OSError):
            print(f"  {name:12} (ilegível)")


if __name__ == "__main__":
    # Standalone test, on a stage name no real run uses.
    sample = [
        {"url": "https://example.com/a", "title": "A", "pubDate": datetime(2026, 9, 21, 10, 0)},
        {"url": "https://example.com/b", "title": "B", "pubDate": "21 Set"},
    ]
    save("_teste", sample, fingerprint="aaaaaaaaaaaa")

    result = load("_teste", fingerprint="aaaaaaaaaaaa")
    assert result is not None
    items, _ = result
    assert isinstance(items[0]["pubDate"], datetime), "datetime não sobreviveu ao cache"
    assert items[1]["pubDate"] == "21 Set", "string de data não sobreviveu ao cache"
    print("   datetime e string de data sobreviveram ao ciclo")

    print("\n-- agora com fingerprint diferente, deve avisar --")
    load("_teste", fingerprint="bbbbbbbbbbbb")

    print()
    describe()
    clear("_teste")
