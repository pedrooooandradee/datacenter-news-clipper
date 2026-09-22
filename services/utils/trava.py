# services/utils/trava.py

"""
One run at a time.

Two complete runs went off at once on 22 Sep 2026 — one launched from Cursor and
one from the assistant, 110 seconds apart. They shared output/ and output/cache/
with nothing in the way. The damage was mild by luck of ordering, but it was real:

  - every cache file was written twice, and any stage could have ended up holding
    one run's items under the other run's fingerprint;
  - the archive received two raw snapshots, and the raw-to-final report compared
    one run's output against the other's, announcing "3 removed, 4 added, 20
    summaries corrected" on an edition nobody had touched by hand.

A run costs money and half an hour. Finding out afterwards that two of them
interleaved is worse than being told, at the start, that one is already going.

The lock is advisory and holds a pid. A stale lock from a crashed run is detected
and taken over, because a lock that needs manual cleaning is a lock that gets
deleted with a sledgehammer the first time it is in the way.
"""

import os
import json
from datetime import datetime
from typing import Optional

UTILS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(UTILS_DIR))
TRAVA_PATH = os.path.join(PROJECT_ROOT, "output", "execucao.lock")


def _vivo(pid: int) -> bool:
    """Whether a process with this pid is still running."""
    try:
        os.kill(pid, 0)
    except (OSError, TypeError):
        return False
    return True


def _ler() -> Optional[dict]:
    try:
        with open(TRAVA_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def adquirir() -> bool:
    """
    Take the lock, or explain who has it and refuse.

    Returns True when the caller may proceed.
    """
    dono = _ler()
    if dono and dono.get("pid") == os.getpid():
        return True
    if dono and _vivo(dono.get("pid")):
        print("⛔ Já existe uma execução em andamento neste projeto.")
        print(f"   Começou em {dono.get('inicio', '?')}, processo {dono.get('pid')}.")
        print("   Duas execuções ao mesmo tempo escrevem no mesmo output/ e no mesmo")
        print("   cache, e o relatório de edição manual sai errado. Espere a outra")
        print("   terminar, ou encerre-a antes de rodar esta.")
        return False

    if dono:
        print(f"ℹ️  Havia uma trava de uma execução que não terminou "
              f"(processo {dono.get('pid')}, de {dono.get('inicio', '?')}). "
              f"Assumindo o lugar dela.")

    os.makedirs(os.path.dirname(TRAVA_PATH), exist_ok=True)
    with open(TRAVA_PATH, "w", encoding="utf-8") as f:
        json.dump({"pid": os.getpid(),
                   "inicio": datetime.now().isoformat(timespec="seconds")}, f)
    return True


def liberar() -> None:
    """Release the lock, but only if it is still ours."""
    dono = _ler()
    if dono and dono.get("pid") == os.getpid():
        try:
            os.remove(TRAVA_PATH)
        except OSError:
            pass


if __name__ == "__main__":
    print("primeira aquisição:", adquirir())
    print("segunda, do mesmo processo:", adquirir())
    liberar()
    print("depois de liberar, o arquivo existe?", os.path.exists(TRAVA_PATH))
