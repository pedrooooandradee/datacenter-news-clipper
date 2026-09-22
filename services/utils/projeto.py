# services/utils/projeto.py

"""
Where the project is on disk, and which model each stage uses.

Two small things that were spread around and broke in the same way.

Paths: summarizer.py and classifier.py opened "configs/…" as a relative path, so
both worked from the project root and raised FileNotFoundError from anywhere else
— including from inside tests/ and from a scheduled run whose working directory
is the user's home. The prompt is part of the program; it is found relative to the
program, not to whoever called it.

Models: the model name was written into five different files. Changing it meant
finding all five, and missing one meant an edition summarised by two different
models without anyone noticing.
"""

import json
import os
from typing import Dict

UTILS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(UTILS_DIR))
CONFIGS_DIR = os.path.join(PROJECT_ROOT, "configs")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output")

MODELO_PADRAO = "gpt-4o-mini"
EMBEDDING_PADRAO = "text-embedding-3-small"


def caminho_config(nome: str) -> str:
    """Absolute path of a file in configs/."""
    return os.path.join(CONFIGS_DIR, nome)


def ler_config(nome: str) -> str:
    """Read a text file from configs/, as text."""
    with open(caminho_config(nome), "r", encoding="utf-8") as f:
        return f.read().strip()


def _carregar_modelos() -> Dict[str, str]:
    try:
        with open(caminho_config("modelos.json"), "r", encoding="utf-8") as f:
            dados = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    return {k: v for k, v in dados.items() if isinstance(v, str)}


_MODELOS = _carregar_modelos()


def modelo(etapa: str) -> str:
    """
    The model a stage should use.

    Falls back to the model that was hard-coded before this file existed, so a
    missing or malformed configs/modelos.json degrades into the old behaviour
    instead of stopping a paid run.
    """
    padrao = EMBEDDING_PADRAO if etapa == "embedding" else MODELO_PADRAO
    return _MODELOS.get(etapa, padrao)


if __name__ == "__main__":
    print(f"PROJECT_ROOT = {PROJECT_ROOT}")
    for etapa in ("triagem", "resumo", "ficha", "reclassificacao", "dedup", "embedding"):
        print(f"  {etapa:16} {modelo(etapa)}")
    print(f"  {'inexistente':16} {modelo('inexistente')}  (cai no padrão)")
