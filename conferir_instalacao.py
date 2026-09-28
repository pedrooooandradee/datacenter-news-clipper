"""
Confere se este computador consegue rodar o clipping. Não gasta nada.

    python conferir_instalacao.py

Roda depois de instalar (README, passo 6), num computador novo, ou quando
alguma coisa quebrar sem motivo aparente. Cada linha diz o que foi conferido e,
quando falha, o que fazer. Nenhuma chamada paga é feita: a chave da OpenAI é
conferida pela consulta gratuita de modelos, e o PDF de teste é desenhado numa
pasta temporária, sem tocar em output/.

Opções:
    --sem-chave      não confere o .env nem a OpenAI (usado nos testes do GitHub)
    --sem-internet   não confere o Google Notícias

Why this file exists: the program is installed on Macs, Windows and Linux by
people who did not write it, and the failures that matter show up late — the PDF
at the end of a paid run, the scrape after the search. Each check here exercises
the real code path, on this machine, in seconds, and the same script runs in the
GitHub checks on all three systems.
"""

import argparse
import os
import platform
import sys
import tempfile
import threading
import unittest

RAIZ = os.path.dirname(os.path.abspath(__file__))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

resultados = []


def registrar(ok, titulo, detalhe=""):
    """ok: True (✅), False (⛔) or None (⚠️, works but deserves attention)."""
    simbolo = {True: "✅", False: "⛔", None: "⚠️ "}[ok]
    print(f"{simbolo} {titulo}" + (f"\n     {detalhe}" if detalhe else ""), flush=True)
    resultados.append(ok)


def conferir_python():
    versao = ".".join(map(str, sys.version_info[:3]))
    maquina = platform.machine()
    if sys.version_info < (3, 10):
        registrar(False, f"Python {versao}",
                  "As bibliotecas exigem 3.10 ou mais (recomendado: 3.12). Refaça o venv "
                  "com o Python do passo 3 do README.")
        return
    if sys.platform == "darwin" and maquina == "x86_64" and _rosetta():
        registrar(False, f"Python {versao} de Intel num Mac com chip Apple",
                  "Roda traduzido (Rosetta), e a coleta trava nas páginas pesadas. Refaça o "
                  "passo 3 do README com CONDA_SUBDIR=osx-arm64.")
        return
    registrar(True, f"Python {versao} ({maquina}, {platform.system()})")


def _rosetta():
    import subprocess
    try:
        saida = subprocess.run(["sysctl", "-in", "sysctl.proc_translated"],
                               capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        return False
    return saida.strip() == "1"


def conferir_bibliotecas():
    faltando = []
    for modulo in ("jinja2", "feedparser", "trafilatura", "selenium", "langchain_openai",
                   "openai", "dotenv"):
        try:
            __import__(modulo)
        except ImportError:
            faltando.append(modulo)
    if faltando:
        registrar(False, f"Bibliotecas faltando: {', '.join(faltando)}",
                  "O venv está ativo? Depois: pip install -r requirements.lock.txt")
    else:
        registrar(True, "Bibliotecas do projeto instaladas")


def conferir_fuso():
    try:
        from datetime import datetime, timezone
        from zoneinfo import ZoneInfo
        hora = datetime(2026, 9, 28, 12, tzinfo=timezone.utc).astimezone(
            ZoneInfo("America/Sao_Paulo")).hour
        registrar(hora == 9, "Fuso de Brasília disponível",
                  "" if hora == 9 else f"Brasília deu {hora}h para 12h UTC.")
    except Exception as e:
        registrar(False, "Fuso de Brasília indisponível",
                  f"{type(e).__name__}: {e}. No Windows: pip install -r requirements.lock.txt "
                  f"(traz o pacote tzdata).")


def conferir_pdf():
    try:
        from datetime import datetime, date
        from services import pdf_builder
        pdf_builder.carregar_weasyprint()
    except Exception as e:
        registrar(False, "PDF: o WeasyPrint não carregou", str(e).replace("\n", "\n     "))
        return
    item = {"id": "item-1", "url": "https://exemplo.com/a", "title": "Notícia de teste",
            "source": "Valor Econômico", "category": "clientes", "summary": "Resumo de teste.",
            "highlight": False, "data_exibida": "28 Set"}
    try:
        env = pdf_builder.init_jinja2_environment(pdf_builder.CONFIGS_DIR)
        html = pdf_builder.render_html(env, "clipping_template.html", [item],
                                       today=datetime(2026, 9, 28, 10), inicio_janela=date(2026, 9, 21))
        destino = os.path.join(tempfile.mkdtemp(), "teste.pdf")
        # Uncompressed, so the embedded font names can be read in the bytes.
        HTML = pdf_builder.carregar_weasyprint()
        HTML(string=html, base_url=pdf_builder.CONFIGS_DIR).write_pdf(
            destino, uncompressed_pdf=True)
        with open(destino, "rb") as f:
            conteudo = f.read()
    except Exception as e:
        registrar(False, "PDF: o WeasyPrint carregou mas não desenhou",
                  f"{type(e).__name__}: {str(e)[:200]}")
        return
    if b"Montserrat" not in conteudo:
        registrar(None, "PDF desenhado, mas SEM a fonte Montserrat",
                  "Confira se configs/fontes/ veio no clone (git status).")
    else:
        registrar(True, f"PDF: desenhado com a fonte Montserrat ({len(conteudo) // 1024} KB)")


def conferir_chrome():
    import http.server

    class Pagina(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            corpo = "<html><body><p>clipping-247-ok</p></body></html>".encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(corpo)))
            self.end_headers()
            self.wfile.write(corpo)

        def log_message(self, *args):
            pass

    servidor = http.server.HTTPServer(("127.0.0.1", 0), Pagina)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    pool = None
    try:
        from services.scraper import DriverPool
        pool = DriverPool()
        driver = pool.get()
        driver.get(f"http://127.0.0.1:{servidor.server_port}/")
        leu = "clipping-247-ok" in driver.page_source
        agente = driver.execute_script("return navigator.userAgent")
        versao = next((p for p in agente.split() if p.startswith("Chrome/")), "Chrome")
        if not leu:
            registrar(False, "Chrome abriu, mas não leu a página de teste")
        elif "Headless" in agente:
            registrar(None, f"Chrome lê páginas ({versao}), mas se apresenta como 'Headless'",
                      "Alguns sites bloqueiam. Avise quem cuida do programa.")
        else:
            registrar(True, f"Chrome: abre e lê páginas ({versao})")
    except Exception as e:
        registrar(False, "Chrome não abriu",
                  f"{type(e).__name__}: {str(e).splitlines()[0][:160] if str(e) else ''}\n"
                  f"     Instale o Google Chrome. Na primeira vez o Selenium baixa o driver: "
                  f"precisa de internet.")
    finally:
        if pool:
            pool.close()
        servidor.shutdown()


def conferir_internet():
    try:
        from services.utils.get_search_results import _ler_feed, build_google_news_rss_url
        feed, erro = _ler_feed(build_google_news_rss_url("data center"))
    except Exception as e:
        registrar(False, "Google Notícias não respondeu", f"{type(e).__name__}: {e}")
        return
    if erro or not feed.entries:
        registrar(False, "Google Notícias não respondeu",
                  f"{erro or 'nenhuma notícia'} — internet, proxy ou firewall da rede.")
    else:
        registrar(True, f"Google Notícias responde ({len(feed.entries)} notícias de teste)")


def conferir_chave():
    from dotenv import load_dotenv
    caminho = os.path.join(RAIZ, ".env")
    if not os.path.exists(caminho):
        registrar(False, "Não há arquivo .env",
                  "Faça uma cópia do .env.example com o nome .env e ponha a chave da OpenAI "
                  "da empresa (README, passo 5).")
        return
    load_dotenv(dotenv_path=caminho)
    import io
    import contextlib
    import main
    saida = io.StringIO()
    with contextlib.redirect_stdout(saida):
        ok = main.verificar_modelos()
    if ok:
        registrar(True, "Chave da OpenAI aceita e modelos disponíveis (consulta gratuita)")
    else:
        registrar(False, "Chave da OpenAI com problema",
                  saida.getvalue().strip().replace("\n", "\n     "))


def conferir_testes():
    import io
    carregador = unittest.TestLoader()
    suite = carregador.discover(os.path.join(RAIZ, "tests"), top_level_dir=os.path.join(RAIZ, "tests"))
    fluxo = io.StringIO()
    import contextlib
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        resultado = unittest.TextTestRunner(stream=fluxo, verbosity=0).run(suite)
    problemas = len(resultado.failures) + len(resultado.errors)
    if problemas:
        nomes = [t.id().split(".")[-1] for t, _ in resultado.failures + resultado.errors][:5]
        registrar(False, f"Testes: {problemas} de {resultado.testsRun} falharam",
                  "Não rode o clipping. Detalhes: python -m unittest discover -s tests\n"
                  f"     {', '.join(nomes)}")
    else:
        registrar(True, f"Testes: {resultado.testsRun}, todos certos")


def main():
    from services.utils.projeto import preparar_terminal
    preparar_terminal()
    parser = argparse.ArgumentParser(description="Confere a instalação do clipping, sem gastar nada.")
    parser.add_argument("--sem-chave", action="store_true", help="não confere o .env nem a OpenAI")
    parser.add_argument("--sem-internet", action="store_true", help="não confere o Google Notícias")
    args = parser.parse_args()

    print("Conferindo a instalação do clipping (nada aqui gasta dinheiro).\n", flush=True)
    conferir_python()
    conferir_bibliotecas()
    conferir_fuso()
    conferir_pdf()
    conferir_chrome()
    if not args.sem_internet:
        conferir_internet()
    if not args.sem_chave:
        conferir_chave()
    conferir_testes()

    falhas = resultados.count(False)
    print()
    if falhas:
        print(f"⛔ {falhas} item(ns) acima precisam de conserto antes de rodar o clipping.")
        return 1
    print("Tudo certo neste computador. O clipping roda com: python main.py "
          "(só com autorização do dono do clipping).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
