# tests/test_regras.py

"""
The rules that decide what an investor reads, tested without spending a cent.

Nothing here touches the network or the OpenAI API. Everything covered is a
decision the program makes in Python: which figure may be published, which outlet
may win a duplicate group, which company gets a box, and what a manual correction
does. Those are the places where being wrong is expensive, and they are exactly
the places a model is not involved.

The three test files that were here before imported `classify_items` and
`summarize_items`, which have never existed in this repository, and
`utils.get_search_results` under a module path that does not resolve. All three
failed at import, so the suite had been green-by-absence since the first commit.

Run it with:

    python -m unittest discover -s tests -v

No pytest, on purpose: setting this project up is already the hardest part of
using it, and unittest comes with Python.
"""

import os
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.utils import numeros
from services.utils.fontes import tier_of, apply_tier_gate, can_win_group
from services import empresas, overrides
from services.ficha import (
    validar_valores, validar_kpis, calcular_ratios, completude, conferir_resumo,
)
from services.classifier import normalize_category
from services.deduplicator import (
    select_survivor, subject_figures, promover_reservas, descartar_reservas,
    _agrupar, _resgatar_fontes_orfas,
)
from services.scraper import looks_blocked, cortar_no_paywall
from services.utils.get_search_results import collect_search_results_from_rss
from services.utils import trava, archive
from services.utils.projeto import preparar_terminal

# The code under test prints ⛔ and ✏️. On Windows, with the output going to a
# file or a pipe (as in the GitHub checks), Python would write in cp1252 and
# stop on the first one.
preparar_terminal()


# ─────────────────────────────────────────────────────────────────────

class LeituraDeNumeros(unittest.TestCase):
    """Brazilian formatting, scale words, and units that mean the same size."""

    def test_convencao_brasileira(self):
        self.assertEqual(numeros.parse_numero("1.234,56"), 1234.56)
        self.assertEqual(numeros.parse_numero("1.000"), 1000.0)
        self.assertEqual(numeros.parse_numero("1,8"), 1.8)
        self.assertEqual(numeros.parse_numero("10.000"), 10000.0)

    def test_escalas(self):
        for texto, esperado in [("R$ 300 milhões", 3e8), ("R$ 15 bi", 1.5e10),
                                ("US$ 2,3 bilhões", 2.3e9), ("R$ 220,4 mi", 2.204e8)]:
            with self.subTest(texto=texto):
                self.assertAlmostEqual(numeros.quantias_no_texto(texto)[0]["valor"], esperado)

    def test_unidades_equivalentes(self):
        """1,8 GW and 1800 MW are the same capacity and have to compare equal."""
        gw = numeros.normalizar(1.8, unidade="GW")
        mw = numeros.normalizar(1800, unidade="MW")
        self.assertTrue(numeros.mesma_quantia(gw, mw))

    def test_moeda_diferente_nao_casa(self):
        brl = numeros.normalizar(300000000, moeda="BRL")
        self.assertIsNone(numeros.aparece_no_texto(brl, "investimento de US$ 300 milhões"))

    def test_nao_inventa_numero_onde_nao_ha(self):
        """A year, a law number or a version string is not a quantity."""
        for texto in ["em 2026", "Portaria 1.234/2025", "Chrome/114.0.0.0", "artigo 5o"]:
            with self.subTest(texto=texto):
                self.assertEqual(numeros.quantias_no_texto(texto), [])

    def test_unidade_por_extenso(self):
        """The mistake that cost an hour: the press writes gigawatts, not GW."""
        for texto, esperado in [("1 gigawatt", 1000.0), ("400 megawatts (MW)", 400.0),
                                ("210 quilowatts", 0.21), ("20 gigawatts até 2032", 20000.0),
                                ("68 TWh", 68e6)]:
            with self.subTest(texto=texto):
                achados = numeros.quantias_no_texto(texto)
                self.assertTrue(achados, f"não leu {texto!r}")
                self.assertAlmostEqual(achados[0]["valor"], esperado)

    def test_abreviatura_e_extenso_sao_a_mesma_coisa(self):
        self.assertTrue(numeros.mesma_quantia(
            numeros.normalizar(4, unidade="GW"),
            numeros.quantias_no_texto("3 a 4 gigawatts para mercado local")[0]))

    def test_conferencia_nao_acusa_numero_escrito_por_extenso(self):
        """Six false alarms in one edition came from exactly this."""
        from services.ficha import conferir_resumo
        corpo = "A Ascenty deve chegar a 1 gigawatt de potência dedicada."
        self.assertEqual(conferir_resumo("A Ascenty projeta 1 GW de potência.", corpo), [])

    def test_unidade_desconhecida_cai_na_magnitude(self):
        """Litres per day is not in the table; the figure still has to be findable."""
        quantia = numeros.normalizar(3240000, unidade="litros/dia")
        texto = "poderia demandar até 3,24 milhões de litros de água tratada por dia"
        self.assertIsNotNone(numeros.aparece_no_texto(quantia, texto))


class PortaoDeFonte(unittest.TestCase):

    def test_dominio_resolve_para_o_tier_do_nome(self):
        """g1.globo.com and G1 are one outlet; a campaign blog must not beat it."""
        self.assertEqual(tier_of("g1.globo.com"), tier_of("G1"))
        self.assertLess(tier_of("g1.globo.com"), tier_of("samiabomfim.com.br"))

    def test_titulo_de_seo_vira_tier_4(self):
        self.assertEqual(tier_of("Exame", "Nuvem barata no Bedrock [2026]"), 4)
        self.assertNotEqual(tier_of("Exame", "Nuvem barata no Bedrock"), 4)

    def test_desconhecido_entra_mas_nao_vence(self):
        self.assertEqual(tier_of("jornal.que.nunca.vi.com.br"), 3)
        self.assertFalse(can_win_group("jornal.que.nunca.vi.com.br"))

    def test_gate_separa_e_nao_perde_ninguem(self):
        items = [{"source": "Valor Econômico", "title": "a"},
                 {"source": "shattered.io", "title": "b"},
                 {"source": "desconhecido.com", "title": "c"}]
        kept, excluded, unlisted = apply_tier_gate(items)
        self.assertEqual(len(kept) + len(excluded), len(items))
        self.assertEqual([i["source"] for i in excluded], ["shattered.io"])
        self.assertIn("desconhecido.com", unlisted)


class PortoesDaFicha(unittest.TestCase):
    """The four gates that stand between a model's output and a printed number."""

    CORPO = ("A Atlantic investirá R$ 300 milhões em três fases no Recife. A primeira "
             "fase recebeu R$ 41 milhões. A capacidade projetada é de 6 MW de TI em "
             "10 mil m² de área construída. A vacância do setor no Brasil está em 4%. "
             "Um data center de 100 MW poderia gerar R$ 25 bilhões.")
    RESUMO = ("A Atlantic investe R$ 300 milhões em três fases no Recife, com 6 MW de "
              "TI e 10 mil m² de área construída; a vacância do setor está em 4%.")

    def _valor(self, **kwargs):
        base = {"campo": "capex", "valor": 300000000, "moeda": "BRL",
                "escopo": "projeto", "fase": "total",
                "fonte_frase": "investirá R$ 300 milhões em três fases"}
        base.update(kwargs)
        return base

    def test_numero_inventado_e_recusado(self):
        validos, rejeitados = validar_valores(
            [self._valor(valor=999000000, fonte_frase="investimento de R$ 999 milhões")],
            self.CORPO, self.RESUMO)
        self.assertEqual(validos, [])
        self.assertIn("NÃO EXISTE", rejeitados[0])

    def test_frase_que_nao_contem_o_numero_e_recusada(self):
        validos, rejeitados = validar_valores(
            [self._valor(fonte_frase="a vacância do setor está em 4%")],
            self.CORPO, self.RESUMO)
        self.assertEqual(validos, [])
        self.assertIn("não contém", rejeitados[0])

    def test_campo_fora_da_lista_e_recusado(self):
        validos, _ = validar_valores([self._valor(campo="ebitda")],
                                     self.CORPO, self.RESUMO)
        self.assertEqual(validos, [])

    def test_numero_so_no_corpo_entra_na_ficha_mas_nao_vira_ratio(self):
        validos, _ = validar_valores([
            self._valor(),
            self._valor(campo="capacidade_ti", valor=6, moeda="", unidade="MW",
                        fonte_frase="capacidade projetada é de 6 MW de TI"),
            self._valor(valor=41000000, fase="fase_1",
                        fonte_frase="A primeira fase recebeu R$ 41 milhões"),
        ], self.CORPO, self.RESUMO)
        por_fase = {v["fase"]: v for v in validos if v["campo"] == "capex"}
        self.assertTrue(por_fase["total"]["no_resumo"])
        self.assertFalse(por_fase["fase_1"]["no_resumo"])

    def test_o_ratio_que_deve_sair(self):
        validos, _ = validar_valores([
            self._valor(),
            self._valor(campo="capacidade_ti", valor=6, moeda="", unidade="MW",
                        fonte_frase="capacidade projetada é de 6 MW de TI"),
        ], self.CORPO, self.RESUMO)
        ratios, _ = calcular_ratios(validos)
        self.assertEqual([r["texto"] for r in ratios], ["R$ 50 mi/MW"])

    def test_escopo_hipotetico_nunca_vira_ratio(self):
        """The government's illustration is not anybody's project."""
        validos, _ = validar_valores([
            self._valor(valor=25000000000, escopo="hipotetico",
                        fonte_frase="poderia gerar R$ 25 bilhões"),
            self._valor(campo="capacidade_ti", valor=100, moeda="", unidade="MW",
                        escopo="hipotetico",
                        fonte_frase="Um data center de 100 MW poderia gerar"),
        ], self.CORPO, self.CORPO)
        ratios, _ = calcular_ratios(validos)
        self.assertEqual(ratios, [])

    def test_escopos_diferentes_nao_pareiam(self):
        validos, _ = validar_valores([
            self._valor(escopo="mercado_brasil"),
            self._valor(campo="capacidade_ti", valor=6, moeda="", unidade="MW",
                        fonte_frase="capacidade projetada é de 6 MW de TI"),
        ], self.CORPO, self.RESUMO)
        ratios, quase = calcular_ratios(validos)
        self.assertEqual(ratios, [])

    def test_dois_valores_no_mesmo_escopo_e_fase_sao_ambiguos(self):
        validos, _ = validar_valores([
            self._valor(),
            self._valor(valor=41000000, fonte_frase="A primeira fase recebeu R$ 41 milhões"),
            self._valor(campo="capacidade_ti", valor=6, moeda="", unidade="MW",
                        fonte_frase="capacidade projetada é de 6 MW de TI"),
        ], self.CORPO, self.CORPO)
        ratios, quase = calcular_ratios(validos)
        self.assertEqual(ratios, [])
        self.assertTrue(any("ambíguo" in m for m in quase))

    def test_conta_absurda_nao_e_publicada(self):
        """R$ 580 bi over 200 MW is arithmetically right and three orders off."""
        corpo = "investimento de mais de R$ 580 bilhões e 200 MW de TI contratados"
        validos, _ = validar_valores([
            self._valor(valor=580000000000, fonte_frase="mais de R$ 580 bilhões"),
            self._valor(campo="capacidade_ti", valor=200, moeda="", unidade="MW",
                        fonte_frase="200 MW de TI contratados"),
        ], corpo, corpo)
        ratios, quase = calcular_ratios(validos)
        self.assertEqual(ratios, [])
        self.assertTrue(any("ordem de grandeza" in m for m in quase))

    def test_kpi_e_copiado_e_nunca_dividido(self):
        kpis = validar_kpis([{"nome": "vacância", "valor": 4, "unidade": "%",
                              "escopo": "mercado_brasil", "fonte_frase": "4%"}],
                            self.CORPO)
        self.assertEqual(kpis[0]["texto"], "4%")
        self.assertEqual(kpis[0]["escopo_rotulo"], "mercado brasileiro")

    def test_kpi_inexistente_no_corpo_nao_entra(self):
        self.assertEqual(validar_kpis(
            [{"nome": "PUE", "valor": 1.2, "unidade": "", "fonte_frase": "x"}],
            self.CORPO), [])

    def test_conferencia_do_resumo_pega_numero_fora_da_materia(self):
        """The real failure: three figures published, none of them in the article."""
        corpo = "O Brasil precisa resolver o gargalo da infraestrutura elétrica."
        resumo = "previsão de R$ 30 bilhões até 2025; a capacidade instalada é de 170 GW"
        faltando = conferir_resumo(resumo, corpo)
        self.assertEqual(sorted(faltando), ["170 GW", "R$ 30 bilhões"])

    def test_conferencia_nao_reclama_de_resumo_fiel(self):
        self.assertEqual(conferir_resumo(self.RESUMO, self.CORPO), [])


class EscolhaDoSobrevivente(unittest.TestCase):

    def test_tier_e_portao_nao_desempate(self):
        """The campaign blog had four figures against G1's one. G1 publishes."""
        items = [
            {"source": "samiabomfim.com.br", "summary": "R$ 5 bilhões, 1 GW, 944 mil m², 2029",
             "ficha": {"valores": [{"escopo": "projeto"}] * 4, "projeto": {}}},
            {"source": "g1.globo.com", "summary": "R$ 5 bilhões",
             "ficha": {"valores": [{"escopo": "projeto"}], "projeto": {}}},
        ]
        self.assertEqual(select_survivor(items, [0, 1]), 1)

    def test_grupo_todo_tier_3_ainda_escolhe_alguem(self):
        items = [{"source": "blog-a.com", "summary": "curto"},
                 {"source": "blog-b.com", "summary": "um resumo bem mais longo e completo"}]
        self.assertIn(select_survivor(items, [0, 1]), (0, 1))

    def test_completude_usa_a_ficha_quando_existe(self):
        com_ficha = {"ficha": {"valores": [{"escopo": "projeto"}, {"escopo": "mercado_brasil"}],
                               "projeto": {"empresa": "X", "local": "Recife"}}}
        self.assertEqual(completude(com_ficha), 3)

    def test_completude_desconta_numero_de_mercado(self):
        """The old proxy, kept as a fallback, still has to discount market framing."""
        self.assertEqual(subject_figures("R$ 300 milhões no projeto. O Brasil somou 106 MW."), 1)


class CaixasDeEmpresa(unittest.TestCase):

    def test_palavra_comum_nao_vira_empresa(self):
        self.assertEqual(empresas.identificar("O resultado positivo surpreendeu"), [])
        self.assertEqual(empresas.identificar("A meta do governo é dobrar"), [])

    def test_nome_composto_e_reconhecido(self):
        self.assertIn("Positivo Tecnologia",
                      empresas.identificar("Positivo Tecnologia amplia produção"))

    def test_apelido_confirmado_pelo_extrator(self):
        nomes = empresas.identificar("Eveo escolhe data center da Atlantic",
                                     ["EVEO", "Atlantic Data Centers"])
        self.assertIn("EVEO", nomes)
        self.assertIn("Atlantic Data Centers", nomes)

    def test_conhecida_nao_ganha_caixa(self):
        self.assertEqual(empresas.ficha_de("Amazon"), "")
        self.assertEqual(empresas.tipo_de("Amazon"), "conhecida")

    def test_sem_dado_publico_nao_ganha_caixa(self):
        self.assertEqual(empresas.ficha_de("RT-One"), "")

    def test_caixa_sai_uma_vez_por_edicao(self):
        edicao = [{"title": "EVEO cresce", "summary": "", "empresas_citadas": ["EVEO"]},
                  {"title": "EVEO de novo", "summary": "", "empresas_citadas": ["EVEO"]}]
        edicao, relatorio = empresas.atribuir_fichas(edicao)
        self.assertEqual(len(edicao[0]["fichas_empresa"]), 1)
        self.assertNotIn("fichas_empresa", edicao[1])
        self.assertEqual(relatorio["desenhadas"].count("EVEO"), 1)

    def test_empresa_nova_fica_em_quarentena(self):
        edicao = [{"title": "Datafoo anuncia", "summary": "",
                   "empresas_citadas": ["Datafoo"]}]
        edicao, relatorio = empresas.atribuir_fichas(edicao)
        self.assertNotIn("fichas_empresa", edicao[0])
        self.assertTrue(any("Datafoo" in n for n in relatorio["novas"]))

    def test_variantes_do_mesmo_nome_contam_uma_vez(self):
        """One article says "Omnia", another "Omnia WN Holding". One company."""
        edicao = [{"title": "A", "summary": "", "empresas_citadas": ["Omnia"]},
                  {"title": "B", "summary": "", "empresas_citadas": ["Omnia WN Holding"]}]
        _, relatorio = empresas.atribuir_fichas(edicao)
        self.assertEqual(len(relatorio["novas"]), 1)
        self.assertIn("Omnia WN Holding", relatorio["novas"][0])

    def test_entidade_de_classe_nao_entra_na_quarentena(self):
        edicao = [{"title": "A", "summary": "",
                   "empresas_citadas": ["Brasscom", "CNI", "Firjan", "Idema"]}]
        _, relatorio = empresas.atribuir_fichas(edicao)
        self.assertEqual(relatorio["novas"], [])

    def test_regime_tributario_nao_e_empresa(self):
        edicao = [{"title": "ReData vira lei", "summary": "",
                   "empresas_citadas": ["ReData", "Redata"]}]
        _, relatorio = empresas.atribuir_fichas(edicao)
        self.assertEqual(relatorio["novas"], [])


class CorrecoesManuais(unittest.TestCase):

    def _arquivo(self, dados):
        import json
        caminho = os.path.join(tempfile.mkdtemp(), "overrides.json")
        with open(caminho, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False)
        return caminho

    def _items(self):
        return [
            {"url": "https://ex.com/a", "title": "A", "source": "X", "category": "outros",
             "summary": "resumo A"},
            {"url": "https://ex.com/b", "title": "B", "source": "Y", "category": "clientes",
             "summary": "resumo B", "ficha": {"ratios": [{"texto": "R$ 50 mi/MW"}]}},
        ]

    def test_remocao_por_url(self):
        caminho = self._arquivo({"removidas": [{"url": "https://ex.com/a", "motivo": "x"}]})
        final, _ = overrides.aplicar(self._items(), caminho)
        self.assertEqual([i["url"] for i in final], ["https://ex.com/b"])

    def test_resumo_reescrito_apaga_as_metricas(self):
        """The rule is that the reader finds both figures above. The text changed."""
        caminho = self._arquivo({"resumo": [{"url": "https://ex.com/b", "texto": "novo",
                                             "motivo": "x"}]})
        final, _ = overrides.aplicar(self._items(), caminho)
        self.assertEqual(final[1]["summary"], "novo")
        self.assertEqual(final[1]["ficha"]["ratios"], [])

    def test_fusao_manual_vira_tambem_noticiado_por(self):
        caminho = self._arquivo({"dedup": [{"manter": "https://ex.com/b",
                                            "fundir": ["https://ex.com/a"], "motivo": "x"}]})
        final, _ = overrides.aplicar(self._items(), caminho)
        self.assertEqual(len(final), 1)
        self.assertEqual(final[0]["tambem_noticiado_por"], ["X"])

    def test_url_que_nao_casa_e_reportada(self):
        caminho = self._arquivo({"removidas": [{"url": "https://ex.com/sumiu", "motivo": "x"}]})
        final, relatorio = overrides.aplicar(self._items(), caminho)
        self.assertEqual(len(final), 2)
        self.assertTrue(any("não bateram" in linha for linha in relatorio))

    def test_correcao_sem_motivo_e_reportada(self):
        caminho = self._arquivo({"removidas": [{"url": "https://ex.com/a"}]})
        _, relatorio = overrides.aplicar(self._items(), caminho)
        self.assertTrue(any("SEM motivo" in linha for linha in relatorio))

    def test_arquivo_quebrado_para_e_diz_a_linha(self):
        """
        It used to be skipped with a warning, and the PDF went out with none of
        the week's corrections, "PDF gerado" at the end and the archive
        overwritten. A missing comma now stops the build and names the line.
        """
        caminho = os.path.join(tempfile.mkdtemp(), "overrides.json")
        with open(caminho, "w", encoding="utf-8") as f:
            f.write('{\n  "removidas": [\n    {"url": "https://ex.com/a"}\n    {"url": "b"}\n  ]\n}')
        with self.assertRaises(overrides.OverridesIlegivel) as erro:
            overrides.aplicar(self._items(), caminho)
        self.assertIn("linha 4", str(erro.exception))


class MontagemDoPDF(unittest.TestCase):
    """Imported here because WeasyPrint is slow to load and only this class needs it."""

    @classmethod
    def setUpClass(cls):
        from services import pdf_builder
        cls.pdf_builder = pdf_builder

    def test_categoria_invalida_nao_some_do_pdf(self):
        import json
        items = [{"url": "u1", "title": "T", "source": "Valor Econômico",
                  "category": "mercado", "summary": "s"}]
        caminho = os.path.join(tempfile.mkdtemp(), "clippings.json")
        with open(caminho, "w", encoding="utf-8") as f:
            json.dump(items, f)
        saida = self.pdf_builder.load_clippings(caminho)
        self.assertEqual(saida[0]["category"], "outros")

    def test_overrides_quebrado_nao_gera_nem_arquiva_pdf(self):
        """No PDF is better than a PDF without the week's corrections."""
        import io, json, contextlib
        pasta = tempfile.mkdtemp()
        entrada = os.path.join(pasta, "clippings.json")
        pdf = os.path.join(pasta, "clipping.pdf")
        with open(entrada, "w", encoding="utf-8") as f:
            json.dump([{"url": "u1", "title": "T", "source": "Valor Econômico",
                        "category": "outros", "summary": "s"}], f)

        def quebrado(_caminho):
            raise overrides.OverridesIlegivel("overrides.json tem um erro de sintaxe na linha 4")

        original = overrides.carregar
        overrides.carregar = quebrado
        saida = io.StringIO()
        try:
            with contextlib.redirect_stdout(saida):
                resultado = self.pdf_builder.build_pdf(entrada, pdf)
        finally:
            overrides.carregar = original
        self.assertEqual(resultado, "")
        self.assertFalse(os.path.exists(pdf))
        self.assertIn("NÃO foi gerado", saida.getvalue())

    def test_tier_4_nao_volta_num_json_antigo(self):
        import json
        items = [{"url": "u1", "title": "Nuvem no Bedrock [2026]", "source": "shattered.io",
                  "category": "clientes", "summary": "s"},
                 {"url": "u2", "title": "Notícia normal", "source": "Valor Econômico",
                  "category": "clientes", "summary": "s"}]
        caminho = os.path.join(tempfile.mkdtemp(), "clippings.json")
        with open(caminho, "w", encoding="utf-8") as f:
            json.dump(items, f)
        saida = self.pdf_builder.load_clippings(caminho)
        self.assertEqual([i["url"] for i in saida], ["u2"])

    def test_ordem_de_leitura_grifadas_primeiro_depois_mais_nova(self):
        import json
        items = [
            {"url": "u1", "title": "antiga", "source": "Valor Econômico",
             "category": "clientes", "summary": "s", "page_date": "2026-09-15T00:00:00"},
            {"url": "u2", "title": "nova", "source": "Valor Econômico",
             "category": "clientes", "summary": "s", "page_date": "2026-09-19T00:00:00"},
            {"url": "u3", "title": "grifada e antiga", "source": "Valor Econômico",
             "category": "clientes", "summary": "s", "highlight": True,
             "page_date": "2026-09-14T00:00:00"},
            {"url": "u4", "title": "outra seção", "source": "Valor Econômico",
             "category": "governo", "summary": "s", "page_date": "2026-09-20T00:00:00"},
        ]
        caminho = os.path.join(tempfile.mkdtemp(), "clippings.json")
        with open(caminho, "w", encoding="utf-8") as f:
            json.dump(items, f)
        saida = self.pdf_builder.load_clippings(caminho)
        self.assertEqual([i["url"] for i in saida], ["u3", "u2", "u1", "u4"])

    def test_data_da_pagina_ganha_da_data_do_feed(self):
        """Google News reported a 2012 article as this week's news. The page did not."""
        item = {"page_date": "2026-09-19T10:00:00+00:00", "pubDate": "2026-09-21T10:00:00+00:00"}
        self.assertEqual(self.pdf_builder._quando(item), "2026-09-19T10:00:00+00:00")


class JanelaDoFeed(unittest.TestCase):
    """The RSS window, which is the only place the pipeline had no report."""

    class _Entrada:
        def __init__(self, titulo, fonte, publicado):
            self.title = f"{titulo} - {fonte}"
            self.link = "https://ex.com/" + titulo.replace(" ", "-")
            self.published = publicado
            self.source = type("S", (), {"title": fonte})()

    class _Feed:
        def __init__(self, entradas):
            self.entries = entradas

    def _feed(self, idades_em_horas):
        from email.utils import format_datetime
        entradas = []
        for n, horas in enumerate(idades_em_horas):
            quando = datetime.now(timezone.utc) - timedelta(hours=horas)
            entradas.append(self._Entrada(f"Noticia {n}", "Valor Econômico",
                                          format_datetime(quando)))
        return self._Feed(entradas)

    def test_dia_civil_nao_corta_a_manha_em_que_a_janela_abre(self):
        """
        An article published on the civil day the window opens is this week's
        news, even though it is more than 7 * 24 hours old.

        This used to be written as a fixed age of `7 * 24 + 9` hours, which made
        the test depend on the hour it was run: the article only landed on the
        opening civil day when the current UTC time was past 09:00. Run at
        03:42 UTC it failed, and a suite that is green during office hours and
        red at night is worse than no suite. The age is now derived from the
        same boundary the code computes.
        """
        from email.utils import format_datetime
        from datetime import time

        abertura = (datetime.now() - timedelta(days=7)).date()
        # Right after midnight on the opening day, on this computer's calendar:
        # inside the window by civil day, and older than 7 * 24 hours at any hour
        # this is run.
        na_abertura = datetime.combine(abertura, time(0, 5)).astimezone()

        entradas = [
            self._Entrada("Noticia 0", "Valor Econômico",
                          format_datetime(datetime.now(timezone.utc) - timedelta(hours=1))),
            self._Entrada("Noticia 1", "Valor Econômico",
                          format_datetime(datetime.now(timezone.utc) - timedelta(hours=24))),
            self._Entrada("Noticia 2", "Valor Econômico", format_datetime(na_abertura)),
        ]

        resultados, descartados, _ = collect_search_results_from_rss(
            self._Feed(entradas), 7)
        self.assertEqual(len(resultados), 3)
        self.assertEqual(descartados, [])

    @unittest.skipUnless(hasattr(__import__("time"), "tzset"),
                         "time.tzset não existe no Windows")
    def test_rodar_a_noite_nao_perde_o_primeiro_dia(self):
        """
        The window used to be counted in UTC here and in local time in the PDF
        header. At 23:30 in Brasília it is already tomorrow in UTC, so the first
        day the header promised was cut from the search.
        """
        import time as relogio
        from email.utils import format_datetime
        from services.utils import get_search_results as busca

        fuso_antes = os.environ.get("TZ")
        os.environ["TZ"] = "America/Sao_Paulo"
        relogio.tzset()

        class Relogio(datetime):
            @classmethod
            def now(cls, tz=None):
                agora = datetime(2026, 10, 5, 23, 30).astimezone()
                return agora.replace(tzinfo=None) if tz is None else agora.astimezone(tz)

        original = busca.datetime
        busca.datetime = Relogio
        try:
            # 28/09 at 15:00 in Brasília: the first day of a 7-day window on 05/10.
            publicada = datetime(2026, 9, 28, 15, 0).astimezone()
            feed = self._Feed([self._Entrada("Ascenty", "Valor Econômico",
                                             format_datetime(publicada))])
            resultados, descartados, _ = collect_search_results_from_rss(feed, 7)
        finally:
            busca.datetime = original
            if fuso_antes is None:
                os.environ.pop("TZ", None)
            else:
                os.environ["TZ"] = fuso_antes
            relogio.tzset()
        self.assertEqual(len(resultados), 1)
        self.assertEqual(descartados, [])

    def test_data_so_com_o_dia_nao_volta_um_dia(self):
        """A page that says only "2026-09-28" was shown as 27 Set in Brasília."""
        from services.scraper import _parse_date
        from services.utils.datetime_utils import format_datetime_br
        for texto in ("2026-09-28", "2026-09-28T00:00:00"):
            self.assertEqual(format_datetime_br(_parse_date(texto)), "28 Set", texto)
        # A real instant keeps its own time.
        self.assertEqual(_parse_date("2026-09-28T10:00:00-03:00").hour, 10)

    def test_materia_realmente_velha_e_descartada_E_CONTADA(self):
        resultados, descartados, _ = collect_search_results_from_rss(
            self._feed([1, 40 * 24]), 7)
        self.assertEqual(len(resultados), 1)
        self.assertEqual(len(descartados), 1)

    def test_data_ilegivel_nao_vira_hoje(self):
        """Stamping "now" made the item pass the window and printed today's date."""
        feed = self._Feed([self._Entrada("Sem data", "Valor Econômico", "isto não é data")])
        resultados, _, sem_data = collect_search_results_from_rss(feed, 7)
        self.assertEqual(len(resultados), 1)
        self.assertIsNone(resultados[0]["pubDate"])
        self.assertEqual(len(sem_data), 1)


class Paywall(unittest.TestCase):

    def test_pagina_que_e_o_bloqueio_e_recusada(self):
        self.assertIsNotNone(looks_blocked("Just a moment... verificação de segurança"))

    def test_muro_que_vaza_e_cortado_e_a_reportagem_fica(self):
        """BNamericas gave four paragraphs and then sold; the pitch has numbers."""
        reportagem = "A Atlantic investe R$ 300 milhões no Recife. " * 40
        corpo, marca = cortar_no_paywall(
            reportagem + " Assine para continuar. +11.000 projetos, +24.000 empresas.")
        self.assertEqual(marca, "assine para continuar")
        self.assertNotIn("11.000", corpo)
        self.assertIn("R$ 300 milhões", corpo)

    def test_texto_limpo_nao_e_cortado(self):
        corpo, marca = cortar_no_paywall("Uma matéria normal, sem nada de assinatura.")
        self.assertIsNone(marca)


class ReservasDoGrupo(unittest.TestCase):
    """A copy held back is a copy still in hand when the chosen ones block."""

    def _grupo(self, corpos):
        return [{"source": f"v{i}", "_grupo_id": 1, "_grupo_ordem": i,
                 **({"body": corpo} if corpo is not None else {"_reserva": True})}
                for i, corpo in enumerate(corpos)]

    def test_reserva_acorda_quando_as_escolhidas_falham(self):
        itens = self._grupo(["", "", None])
        promovidos = promover_reservas(itens)
        self.assertEqual([i["source"] for i in promovidos], ["v2"])
        self.assertNotIn("_reserva", itens[2])

    def test_reserva_fica_quieta_quando_alguma_escolhida_carrega(self):
        itens = self._grupo(["texto", "", None])
        self.assertEqual(promover_reservas(itens), [])

    def test_reserva_dispensada_vira_nome_no_clipping(self):
        itens = self._grupo(["texto", "", None])
        final = descartar_reservas(itens)
        self.assertEqual(len(final), 2)
        self.assertEqual(final[0]["_fontes_do_grupo"], ["v2"])


class TravaDeExecucao(unittest.TestCase):
    """Two runs at once shared output/ and the cache on 22 set 2026."""

    def setUp(self):
        self._original = trava.TRAVA_PATH
        trava.TRAVA_PATH = os.path.join(tempfile.mkdtemp(), "execucao.lock")

    def tearDown(self):
        trava.TRAVA_PATH = self._original

    def test_pega_e_solta(self):
        self.assertTrue(trava.adquirir())
        self.assertTrue(os.path.exists(trava.TRAVA_PATH))
        trava.liberar()
        self.assertFalse(os.path.exists(trava.TRAVA_PATH))

    def test_a_propria_execucao_pode_readquirir(self):
        self.assertTrue(trava.adquirir())
        self.assertTrue(trava.adquirir())
        trava.liberar()

    def test_outra_execucao_viva_e_recusada(self):
        import json
        with open(trava.TRAVA_PATH, "w", encoding="utf-8") as f:
            json.dump({"pid": os.getppid(), "inicio": "2026-09-22T16:00:00"}, f)
        self.assertFalse(trava.adquirir())

    def test_trava_orfa_e_assumida(self):
        """A lock nobody can clean is a lock that gets deleted with a sledgehammer."""
        import json
        with open(trava.TRAVA_PATH, "w", encoding="utf-8") as f:
            json.dump({"pid": 999999, "inicio": "2026-09-22T16:00:00"}, f)
        self.assertTrue(trava.adquirir())
        trava.liberar()


class DiffDaEdicao(unittest.TestCase):

    def test_compara_com_o_cru_da_mesma_execucao(self):
        """Comparing against the FIRST run of the day reported edits nobody made."""
        import json, time
        pasta = tempfile.mkdtemp()
        for nome, urls in [("clippings.raw.json", ["a", "b", "c"]),
                           ("clippings.raw.164043.json", ["a", "b"])]:
            with open(os.path.join(pasta, nome), "w", encoding="utf-8") as f:
                json.dump([{"url": u, "category": "outros", "summary": "s"} for u in urls], f)
            time.sleep(0.01)
        self.assertTrue(archive._raw_mais_recente(pasta).endswith("164043.json"))


class Categorias(unittest.TestCase):

    def test_normalizacao(self):
        for bruto in ["inovação", "inovacao", "Inovação", " INOVAÇÃO "]:
            with self.subTest(bruto=bruto):
                self.assertEqual(normalize_category(bruto), ("inovação", True))

    def test_categoria_desconhecida_cai_em_outros_e_avisa(self):
        categoria, reconhecida = normalize_category("tecnologia")
        self.assertEqual(categoria, "outros")
        self.assertFalse(reconhecida)


class EdicaoDe28DeSetembro(unittest.TestCase):
    """
    The three defects the 28 set 2026 edition exposed, each pinned by the case
    that exposed it.
    """

    # ── Grouping titles: no chaining ─────────────────────────────────
    @staticmethod
    def _vetor(graus):
        import math
        return [math.cos(math.radians(graus)), math.sin(math.radians(graus))]

    def test_uma_manchete_ponte_nao_junta_duas_historias(self):
        """A~B and B~C above 0.75 while A and C are unrelated: A and C stay apart.

        Union-find joined all three, which is how Google and Alibaba became one
        group of forty titles.
        """
        a, b, c = self._vetor(0), self._vetor(35), self._vetor(70)   # cos 0.82, 0.82, 0.34
        grupos = _agrupar([a, b, c], 0.75)
        juntos = [g for g in grupos if 0 in g and 2 in g]
        self.assertEqual(juntos, [])
        self.assertEqual(len(grupos), 2)

    def test_historia_de_verdade_continua_um_grupo(self):
        vetores = [self._vetor(0), self._vetor(10), self._vetor(20), self._vetor(90)]
        grupos = _agrupar(vetores, 0.75)
        self.assertIn([0, 1, 2], grupos)
        self.assertIn([3], grupos)

    # ── The names of copies dropped before the scrape: once ──────────
    def test_nomes_das_copias_vao_para_uma_materia_so(self):
        """Both kept articles of one title group used to print the same list."""
        itens = [
            {"source": "Data Center Dynamics", "_grupo_id": 1, "_grupo_ordem": 0,
             "_fontes_do_grupo": ["UOL", "BOL"]},
            {"source": "TeleSíntese", "_grupo_id": 1, "_grupo_ordem": 1,
             "_fontes_do_grupo": ["UOL", "BOL"]},
        ]
        _resgatar_fontes_orfas(itens)
        self.assertEqual(itens[0].get("tambem_noticiado_por"), ["BOL", "UOL"])
        self.assertIsNone(itens[1].get("tambem_noticiado_por"))

    def test_grupo_ja_entregue_pelo_modelo_nao_entrega_de_novo(self):
        itens = [{"source": "X", "_grupo_id": 7, "_grupo_ordem": 1,
                  "_fontes_do_grupo": ["UOL"]}]
        _resgatar_fontes_orfas(itens, {7})
        self.assertIsNone(itens[0].get("tambem_noticiado_por"))

    # ── Numbers written out ──────────────────────────────────────────
    def test_um_quilowatt_e_1_kw(self):
        """O Globo: 'cerca de um quilowatt'; the summary's '1 kW' is not invented."""
        self.assertEqual(
            conferir_resumo("fornecerá cerca de 1 kW de energia",
                            "fornecerão apenas cerca de um quilowatt de energia"), [])

    def test_um_decimo_do_e_10_por_cento(self):
        """The Prates column: 'um décimo do crescimento'; the summary's 10% is right."""
        self.assertEqual(
            conferir_resumo("cerca de 10% do crescimento do consumo",
                            "responderão por cerca de um décimo do crescimento mundial"), [])

    def test_numero_inventado_continua_pego(self):
        self.assertEqual(
            conferir_resumo("cerca de 12% do crescimento",
                            "cerca de um décimo do crescimento mundial"), ["12%"])

    def test_palavra_comum_nao_vira_numero(self):
        for texto in ("um data center em Recife", "um quarto de hotel", "há dois anos"):
            self.assertEqual(numeros.quantias_no_texto(texto), [], texto)

    # ── The previous edition ─────────────────────────────────────────
    def test_edicao_anterior_ignora_a_propria_semana_e_a_que_nao_virou_pdf(self):
        import json
        pasta = tempfile.mkdtemp()
        def edicao(nome, final):
            os.makedirs(os.path.join(pasta, nome))
            arquivo = archive.FINAL_NAME if final else archive.RAW_NAME
            with open(os.path.join(pasta, nome, arquivo), "w", encoding="utf-8") as f:
                json.dump([{"url": f"https://ex.com/{nome}/"}], f)
        edicao("2026-09-15", final=True)
        edicao("2026-09-22", final=True)    # a de verdade
        edicao("2026-09-24", final=False)   # rodou e nunca virou PDF
        edicao("2026-09-27", final=True)    # a própria semana, rodada de novo

        original = archive.ARCHIVE_DIR
        archive.ARCHIVE_DIR = pasta
        try:
            nome, urls = archive.edicao_anterior(datetime(2026, 9, 28, 10, 0))
        finally:
            archive.ARCHIVE_DIR = original
        self.assertEqual(nome, "2026-09-22")
        self.assertEqual(urls, {"https://ex.com/2026-09-22"})

    def test_url_igual_ate_a_barra_e_o_fragmento(self):
        self.assertEqual(archive.url_chave("https://ex.com/a/#topo"),
                         archive.url_chave("https://ex.com/a"))


class PassagemDeBastao(unittest.TestCase):
    """
    What has to keep working when nobody who wrote this is around: the window of
    an edition, the checks that stop a run before it spends money, and the
    warnings that used to be silent.
    """

    def _arquivo_com(self, *edicoes):
        import json
        pasta = tempfile.mkdtemp()
        for nome in edicoes:
            os.makedirs(os.path.join(pasta, nome))
            with open(os.path.join(pasta, nome, archive.FINAL_NAME), "w", encoding="utf-8") as f:
                json.dump([{"url": f"https://ex.com/{nome}"}], f)
        return pasta

    def _com_arquivo(self, pasta, funcao):
        original = archive.ARCHIVE_DIR
        archive.ARCHIVE_DIR = pasta
        try:
            return funcao()
        finally:
            archive.ARCHIVE_DIR = original

    # ── The window ───────────────────────────────────────────────────
    def _janela(self, pasta, agora):
        import main
        return self._com_arquivo(pasta, lambda: main.janela_desta_edicao(agora))

    def test_janela_semana_normal_e_sete_dias(self):
        dias, porque = self._janela(self._arquivo_com("2026-09-28"), datetime(2026, 10, 5, 9))
        self.assertEqual(dias, 7)
        self.assertNotIn("⚠️", porque)

    def test_atraso_de_ate_tres_dias_e_coberto(self):
        """Run two or three days late: the days in between are not lost."""
        pasta = self._arquivo_com("2026-09-28")
        self.assertEqual(self._janela(pasta, datetime(2026, 10, 7, 9))[0], 9)
        self.assertEqual(self._janela(pasta, datetime(2026, 10, 8, 9))[0], 10)

    def test_arquivo_parado_nao_estica_a_janela(self):
        """
        The review of 28 set 2026: a computer whose output/archive/ stopped at
        14/09, while 21/09 and 28/09 went out from another one. Stretching to 21
        days brought both editions back under a three-week header. The window
        stays at 7 and the run says, loudly, what it cannot know.
        """
        dias, porque = self._janela(self._arquivo_com("2026-09-14"), datetime(2026, 10, 5, 9))
        self.assertEqual(dias, 7)
        self.assertIn("⚠️", porque)
        self.assertIn("outro computador", porque)

    def test_semana_pulada_nao_promete_o_que_nao_cobre(self):
        dias, porque = self._janela(self._arquivo_com("2026-09-28"), datetime(2026, 10, 12, 9))
        self.assertEqual(dias, 7)
        self.assertIn("NÃO entra", porque)

    def test_sem_arquivo_usa_o_padrao(self):
        dias, porque = self._janela(tempfile.mkdtemp(), datetime(2026, 10, 5, 9))
        self.assertEqual(dias, 7)
        self.assertIn("não há edição anterior", porque)

    def test_cabecalho_do_pdf_mostra_o_inicio_da_janela(self):
        from datetime import date
        from services import pdf_builder
        env = pdf_builder.init_jinja2_environment(pdf_builder.CONFIGS_DIR)
        html = pdf_builder.render_html(env, "clipping_template.html", [],
                                       today=datetime(2026, 10, 12, 10),
                                       inicio_janela=date(2026, 9, 28))
        self.assertIn("Week 28 Sep 2026", html)

    def test_janela_fica_registrada_para_a_remontagem_do_pdf(self):
        from datetime import date
        original = archive.EDICAO_PATH
        archive.EDICAO_PATH = os.path.join(tempfile.mkdtemp(), "edicao_atual.json")
        try:
            archive.registrar_edicao(datetime(2026, 10, 12, 10), inicio_janela=date(2026, 9, 28))
            self.assertEqual(archive.inicio_da_janela(), date(2026, 9, 28))
        finally:
            archive.EDICAO_PATH = original

    # ── Warnings that used to be silent ──────────────────────────────
    def test_sem_edicao_anterior_o_filtro_de_repetidas_avisa(self):
        import io, contextlib, main
        pasta = tempfile.mkdtemp()
        saida = io.StringIO()
        itens = [{"url": "https://ex.com/a", "title": "A", "source": "X"}]
        with contextlib.redirect_stdout(saida):
            resultado = self._com_arquivo(pasta, lambda: main.drop_already_published(itens))
        self.assertEqual(resultado, itens)
        self.assertIn("NÃO foram retiradas", saida.getvalue())

    def test_correcao_desta_semana_que_nao_bateu_aparece_as_antigas_so_contam(self):
        import json
        caminho = os.path.join(tempfile.mkdtemp(), "overrides.json")
        with open(caminho, "w", encoding="utf-8") as f:
            json.dump({"removidas": [
                {"url": "https://ex.com/digitada-errado", "motivo": "x", "data": "2026-10-05"},
                {"url": "https://ex.com/da-semana-passada", "motivo": "x", "data": "2026-09-28"},
            ]}, f)
        original = overrides.data_da_edicao
        overrides.data_da_edicao = lambda: datetime(2026, 10, 5, 10)
        try:
            _, relatorio = overrides.aplicar([{"url": "https://ex.com/outra"}], caminho)
        finally:
            overrides.data_da_edicao = original
        texto = "\n".join(relatorio)
        self.assertIn("digitada-errado", texto)
        self.assertNotIn("da-semana-passada", texto)
        self.assertIn("1 correções de edições anteriores", texto)

    def _nao_casou(self, entradas, fechamento):
        import json
        caminho = os.path.join(tempfile.mkdtemp(), "overrides.json")
        with open(caminho, "w", encoding="utf-8") as f:
            json.dump({"removidas": entradas}, f)
        original = overrides.data_da_edicao
        overrides.data_da_edicao = lambda: fechamento
        try:
            _, relatorio = overrides.aplicar([{"url": "https://ex.com/outra"}], caminho)
        finally:
            overrides.data_da_edicao = original
        return "\n".join(relatorio)

    def test_data_brasileira_da_semana_nao_some(self):
        """Compared as text, "05/10/2026" sorted before "2026-10-05" and was hidden."""
        texto = self._nao_casou([
            {"url": "https://ex.com/digitada-errado", "motivo": "x", "data": "05/10/2026"},
            {"url": "https://ex.com/antiga", "motivo": "x", "data": "28/09/2026"},
        ], datetime(2026, 10, 5, 10))
        self.assertIn("digitada-errado", texto)
        self.assertNotIn("ex.com/antiga", texto)

    def test_pdf_refeito_no_dia_seguinte_ainda_mostra_a_da_semana(self):
        """--from rewrites the closing date; Monday's correction is still this week's."""
        texto = self._nao_casou([
            {"url": "https://ex.com/digitada-errado", "motivo": "x", "data": "2026-10-05"},
        ], datetime(2026, 10, 6, 11))
        self.assertIn("digitada-errado", texto)

    def test_data_ilegivel_e_mostrada(self):
        texto = self._nao_casou([
            {"url": "https://ex.com/x", "motivo": "x", "data": "5 de outubro"},
        ], datetime(2026, 10, 5, 10))
        self.assertIn("data ilegível", texto)

    # ── Stopping before money is spent ───────────────────────────────
    def _cliente(self, erro=None):
        class Modelos:
            def retrieve(self, nome):
                if erro:
                    raise erro
        class Cliente:
            models = Modelos()
        return Cliente()

    def _erro(self, classe, status):
        import httpx
        resposta = httpx.Response(status, request=httpx.Request("GET", "https://api.openai.com"))
        return classe("erro de teste", response=resposta, body=None)

    def test_modelo_aposentado_para_antes_de_gastar(self):
        import io, contextlib, openai, main
        saida = io.StringIO()
        with contextlib.redirect_stdout(saida):
            ok = main.verificar_modelos(self._cliente(self._erro(openai.NotFoundError, 404)))
        self.assertFalse(ok)
        self.assertIn("configs/modelos.json", saida.getvalue())

    def test_chave_recusada_para_antes_de_gastar(self):
        import io, contextlib, openai, main
        saida = io.StringIO()
        with contextlib.redirect_stdout(saida):
            ok = main.verificar_modelos(self._cliente(self._erro(openai.AuthenticationError, 401)))
        self.assertFalse(ok)
        self.assertIn("recusou a chave", saida.getvalue())

    def test_tudo_certo_segue(self):
        import main
        self.assertTrue(main.verificar_modelos(self._cliente()))

    def _verificar(self, erro_por_modelo):
        import io, contextlib, main
        class Modelos:
            def retrieve(self, nome):
                if nome in erro_por_modelo:
                    raise erro_por_modelo[nome]
        class Cliente:
            models = Modelos()
        saida = io.StringIO()
        with contextlib.redirect_stdout(saida):
            ok = main.verificar_modelos(Cliente())
        return ok, saida.getvalue()

    def _erro_json(self, classe, status, corpo):
        import httpx
        resposta = httpx.Response(status, json=corpo,
                                  request=httpx.Request("GET", "https://api.openai.com"))
        return classe("erro de teste", response=resposta, body=corpo.get("error"))

    def test_sem_permissao_nao_manda_trocar_o_modelo(self):
        """A 403 is a permission to ask for, not a model to replace."""
        import openai
        from services.utils.projeto import modelo
        ok, texto = self._verificar({modelo("dedup"): self._erro(openai.PermissionDeniedError, 403)})
        self.assertFalse(ok)
        self.assertIn("permissão", texto)
        self.assertIn("NÃO troque", texto)

    def test_embedding_aposentado_ou_sem_permissao_so_avisa(self):
        """The pipeline already runs without it; it must not stop the edition."""
        import openai
        from services.utils.projeto import modelo
        for classe, status in ((openai.NotFoundError, 404), (openai.PermissionDeniedError, 403)):
            ok, texto = self._verificar({modelo("embedding"): self._erro(classe, status)})
            self.assertTrue(ok, classe.__name__)
            self.assertIn("⚠️", texto)

    def test_openai_instavel_para_sem_traceback(self):
        import openai
        from services.utils.projeto import modelo
        ok, texto = self._verificar({modelo("dedup"): self._erro(openai.InternalServerError, 503)})
        self.assertFalse(ok)
        self.assertIn("503", texto)

    def test_conta_sem_credito_para_na_primeira_chamada_paga(self):
        import openai
        from services.utils.projeto import parar_se_sem_credito, SemCredito
        erro = self._erro_json(openai.RateLimitError, 429, {"error": {
            "message": "You exceeded your current quota", "type": "insufficient_quota",
            "code": "insufficient_quota"}})
        with self.assertRaises(SemCredito) as parada:
            parar_se_sem_credito(erro, retomar_de="classify")
        self.assertIn("--from=classify", str(parada.exception))
        # An ordinary rate limit is not a lack of credit.
        comum = self._erro_json(openai.RateLimitError, 429, {"error": {
            "message": "Rate limit reached", "type": "requests", "code": "rate_limit_exceeded"}})
        parar_se_sem_credito(comum, retomar_de="classify")

    # ── The run log ──────────────────────────────────────────────────
    def test_registro_escreve_no_terminal_e_no_arquivo(self):
        import io, main
        terminal, arquivo = io.StringIO(), io.StringIO()
        duplo = main._Duplicador(terminal, arquivo)
        duplo.write("🚨 aviso\n")
        self.assertEqual(terminal.getvalue(), arquivo.getvalue())

    def test_erro_que_para_a_execucao_fica_no_registro(self):
        """
        The traceback used to be printed after the log was closed, so the file
        sent to whoever fixes the problem ended one line before the problem.
        """
        import io, contextlib, glob, main
        from pathlib import Path

        def quebra(_args):
            print("linha antes da falha")
            raise RuntimeError("erro no meio da execução")

        pasta = Path(tempfile.mkdtemp())
        salvos = (main.PROJECT_ROOT, main._executar, trava.adquirir, trava.liberar, sys.argv)
        main.PROJECT_ROOT, main._executar = pasta, quebra
        trava.adquirir, trava.liberar = (lambda: True), (lambda: None)
        sys.argv = ["main.py"]
        try:
            with contextlib.redirect_stderr(io.StringIO()), \
                 contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit) as saida:
                    main.main()
        finally:
            (main.PROJECT_ROOT, main._executar, trava.adquirir, trava.liberar,
             sys.argv) = salvos
        self.assertEqual(saida.exception.code, 1)
        [registro] = glob.glob(str(pasta / "output" / "logs" / "*.log"))
        conteudo = open(registro, encoding="utf-8").read()
        self.assertIn("linha antes da falha", conteudo)
        self.assertIn("RuntimeError: erro no meio da execução", conteudo)
        self.assertIn("PAROU", conteudo)



class NomeEQuinzenal(unittest.TestCase):
    """The Drive's file names, and the fortnightly edition the company sends on purpose."""

    # Real names from the Drive folder "Clippings Semanais", with the closing
    # time each one carries.
    NOMES_DO_DRIVE = [
        (datetime(2026, 9, 21, 11, 0), date(2026, 9, 14),
         "2026.09.21 Clipping Atualização Semanal (14_09 - 21_09 às 11h00).pdf"),
        (datetime(2026, 9, 8, 9, 30), date(2026, 8, 31),
         "2026.09.08 Clipping Atualização Semanal (31_08 - 08_09 às 9h30).pdf"),
        (datetime(2026, 1, 19, 14, 43), date(2026, 1, 12),
         "2026.01.19 Clipping Atualização Semanal (12_01 - 19_01 às 14h43).pdf"),
        (datetime(2026, 2, 23, 12, 50), date(2026, 2, 9),
         "2026.02.23 Clipping Atualização Quinzenal (09_02 - 23_02 às 12h50).pdf"),
        (datetime(2026, 1, 5, 13, 13), date(2025, 12, 22),
         "2026.01.05 Clipping Atualização Quinzenal (22_12_2025 - 05_01_2026 às 13h13).pdf"),
    ]

    def test_reproduz_os_nomes_do_drive(self):
        for fechamento, inicio, esperado in self.NOMES_DO_DRIVE:
            self.assertEqual(archive.nome_do_pdf(fechamento, inicio), esperado)

    def test_atraso_de_dois_dias_continua_semanal(self):
        nome = archive.nome_do_pdf(datetime(2026, 10, 7, 10, 5), date(2026, 9, 28))
        self.assertIn("Semanal (28_09 - 07_10 às 10h05)", nome)

    def test_sem_inicio_registrado_usa_sete_dias(self):
        nome = archive.nome_do_pdf(datetime(2026, 9, 28, 10, 19))
        self.assertEqual(nome, "2026.09.28 Clipping Atualização Semanal (21_09 - 28_09 às 10h19).pdf")

    def _janela(self, edicoes, agora):
        import json, main
        pasta = tempfile.mkdtemp()
        for nome in edicoes:
            os.makedirs(os.path.join(pasta, nome))
            with open(os.path.join(pasta, nome, archive.FINAL_NAME), "w", encoding="utf-8") as f:
                json.dump([], f)
        original = archive.ARCHIVE_DIR
        archive.ARCHIVE_DIR = pasta
        try:
            return main.janela_desta_edicao(agora, quinzenal=True)
        finally:
            archive.ARCHIVE_DIR = original

    def test_quinzenal_cobre_catorze_dias(self):
        dias, porque = self._janela(["2026-09-14"], datetime(2026, 9, 28, 9))
        self.assertEqual(dias, 14)
        self.assertNotIn("⚠️", porque)

    def test_quinzenal_com_arquivo_parado_nao_sugere_quinzenal(self):
        _, porque = self._janela(["2026-09-01"], datetime(2026, 9, 28, 9))
        self.assertIn("⚠️", porque)
        self.assertNotIn("--quinzenal", porque)

    def test_quinzenal_uma_semana_depois_avisa_que_repete(self):
        dias, porque = self._janela(["2026-09-21"], datetime(2026, 9, 28, 9))
        self.assertEqual(dias, 14)
        self.assertIn("repete a semana", porque)

    def test_edicao_viaja_com_o_cache(self):
        """
        A --from after a fortnightly run is still a fortnight, and a weekly one
        resumed a week later is still weekly (the review found it turning into
        "Quinzenal" when the kind was derived from the days).
        """
        from services.utils import cache
        original = cache.CACHE_DIR
        cache.CACHE_DIR = tempfile.mkdtemp()
        try:
            cache.save("search", [{"url": "u"}], "x", edicao={
                "inicio_janela": date(2026, 9, 14), "desde": date(2026, 9, 14),
                "tipo": "Semanal"})
            salva = cache.edicao_salva("search")
            self.assertEqual(salva["inicio_janela"], date(2026, 9, 14))
            self.assertIsNone(cache.edicao_salva("dedup"))
        finally:
            cache.CACHE_DIR = original
        # Resumed on 28/09: still "Semanal", even with 14 days between the dates.
        nome = archive.nome_do_pdf(datetime(2026, 9, 28, 10, 19), salva["desde"], salva["tipo"])
        self.assertIn("Semanal (14_09 - 28_09", nome)

    def test_sequencia_real_do_drive(self):
        """
        The Drive's names come from the previous edition's day, not from the
        first day searched: 14/09 is "(08_09 - 14_09 …)", after the Tuesday
        edition of 08/09, though its header says "Week 07 Sep". Run through the
        same functions main.py uses, over the real sequence of editions.
        """
        import json, main
        sequencia = [
            ("2026-08-24", datetime(2026, 8, 31, 14, 30),
             "2026.08.31 Clipping Atualização Semanal (24_08 - 31_08 às 14h30).pdf"),
            ("2026-08-31", datetime(2026, 9, 8, 9, 30),
             "2026.09.08 Clipping Atualização Semanal (31_08 - 08_09 às 9h30).pdf"),
            ("2026-09-08", datetime(2026, 9, 14, 9, 30),
             "2026.09.14 Clipping Atualização Semanal (08_09 - 14_09 às 9h30).pdf"),
            ("2026-09-14", datetime(2026, 9, 21, 11, 0),
             "2026.09.21 Clipping Atualização Semanal (14_09 - 21_09 às 11h00).pdf"),
        ]
        pasta = tempfile.mkdtemp()
        original = archive.ARCHIVE_DIR
        archive.ARCHIVE_DIR = pasta
        try:
            for anterior, fechamento, esperado in sequencia:
                os.makedirs(os.path.join(pasta, anterior), exist_ok=True)
                with open(os.path.join(pasta, anterior, archive.FINAL_NAME), "w",
                          encoding="utf-8") as f:
                    json.dump([], f)
                dias, _ = main.janela_desta_edicao(fechamento)
                inicio = fechamento.date() - timedelta(days=dias)
                desde = main.desde_para_o_nome(inicio, agora=fechamento)
                self.assertEqual(archive.nome_do_pdf(fechamento, desde, "Semanal"), esperado)
        finally:
            archive.ARCHIVE_DIR = original

    def test_busca_pede_uma_fatia_por_semana(self):
        from services.utils.get_search_results import _fatias
        hoje = date(2026, 9, 28)
        self.assertEqual(_fatias(7, hoje), [(date(2026, 9, 21), hoje)])
        fatias = _fatias(14, hoje)
        self.assertEqual(len(fatias), 2)
        self.assertEqual(fatias[0][0], date(2026, 9, 14))
        self.assertEqual(fatias[-1][1], hoje)
        # contiguous: no day left out, none asked twice
        self.assertEqual(fatias[0][1] + timedelta(days=1), fatias[1][0])

    def test_pdf_antigo_so_sai_de_output_se_estiver_arquivado(self):
        from services import pdf_builder
        raiz = tempfile.mkdtemp()
        saida, arquivo = os.path.join(raiz, "output"), os.path.join(raiz, "archive")
        os.makedirs(os.path.join(arquivo, "2026-09-21"))
        os.makedirs(saida)
        antigo = "2026.09.21 Clipping Atualização Semanal (14_09 - 21_09 às 11h00).pdf"
        sem_copia = "2026.09.14 Clipping Atualização Semanal (08_09 - 14_09 às 9h30).pdf"
        atual = "2026.09.28 Clipping Atualização Semanal (21_09 - 28_09 às 10h19).pdf"
        for nome in (antigo, sem_copia, atual, "outra coisa.pdf"):
            open(os.path.join(saida, nome), "wb").close()
        open(os.path.join(arquivo, "2026-09-21", antigo), "wb").close()
        original = pdf_builder.ARCHIVE_DIR
        pdf_builder.ARCHIVE_DIR = arquivo
        try:
            pdf_builder._limpar_pdfs_antigos(os.path.join(saida, atual))
        finally:
            pdf_builder.ARCHIVE_DIR = original
        self.assertEqual(sorted(os.listdir(saida)), sorted([sem_copia, atual, "outra coisa.pdf"]))


class OutrosComputadores(unittest.TestCase):
    """What used to assume a Mac."""

    def test_trava_nao_mata_ninguem_ao_perguntar(self):
        """os.kill(pid, 0) sends Ctrl+C on Windows; the check must only ask."""
        self.assertTrue(trava._vivo(os.getpid()))
        self.assertFalse(trava._vivo(0))
        self.assertFalse(trava._vivo(-5))
        self.assertFalse(trava._vivo(None))

    def test_sem_weasyprint_para_antes_de_gastar(self):
        import io, contextlib, main
        from services.pdf_builder import PDFIndisponivel

        def falta():
            raise PDFIndisponivel("A parte que desenha o PDF (WeasyPrint) não carregou")

        original = main.carregar_weasyprint
        main.carregar_weasyprint = falta
        saida = io.StringIO()
        try:
            with contextlib.redirect_stdout(saida):
                ok = main.verificar_pdf()
        finally:
            main.carregar_weasyprint = original
        self.assertFalse(ok)
        self.assertIn("Nada foi gasto", saida.getvalue())

    def test_fuso_de_brasilia_existe_neste_computador(self):
        """Windows has no time-zone database; the tzdata package has to be there."""
        from zoneinfo import ZoneInfo
        self.assertEqual(datetime(2026, 9, 28, 12, tzinfo=timezone.utc)
                         .astimezone(ZoneInfo("America/Sao_Paulo")).hour, 9)

    def test_fonte_do_pdf_vem_no_repositorio(self):
        """Fetched from Google on every build, the font fell back to Arial offline."""
        from services import pdf_builder
        modelo = open(os.path.join(pdf_builder.CONFIGS_DIR, "clipping_template.html"),
                      encoding="utf-8").read()
        self.assertNotIn("fonts.googleapis.com", modelo)
        for peso in (400, 500, 600, 700):
            self.assertIn(f"fontes/Montserrat-{peso}.ttf", modelo)
            self.assertTrue(os.path.exists(os.path.join(
                pdf_builder.CONFIGS_DIR, "fontes", f"Montserrat-{peso}.ttf")))


class RevisaoMultiplataforma(unittest.TestCase):
    """What the independent review of 28 set 2026 found in the first draft."""

    def test_busca_que_falha_para_e_nao_finge_que_nao_achou(self):
        """
        A network failure used to fall through to the undated search, which
        brings far fewer stories, and the report said "nada com a busca normal".
        """
        from services.utils import get_search_results as busca
        pedidos = []

        class Feed:
            entries = []

        def falha(url):
            pedidos.append(url)
            return Feed(), "HTTP 429"

        salvos = (busca._ler_feed, busca.time.sleep)
        busca._ler_feed, busca.time.sleep = falha, (lambda s: None)
        try:
            resultados, problemas = busca.get_search_results("aws", days=7)
        finally:
            busca._ler_feed, busca.time.sleep = salvos
        self.assertEqual(resultados, [])
        self.assertEqual(len(pedidos), 2)            # the slice, and one retry
        texto = "\n".join(problemas)
        self.assertIn("FALHOU duas vezes", texto)
        self.assertNotIn("busca normal", texto)

    def test_fuso_sem_dois_pontos_e_lido_em_qualquer_python(self):
        """Python 3.10 (Ubuntu 22.04) did not read "-0300"; the hour was lost."""
        from services.scraper import _parse_date
        self.assertEqual(_parse_date("2026-09-28T10:00:00-0300").hour, 10)
        self.assertEqual(_parse_date("2026-09-28T10:00:00+0000").utcoffset(), timedelta(0))
        self.assertEqual(_parse_date("2026-09-28T10:00:00.5-03:00").microsecond, 500000)

    def test_arquivo_guarda_so_o_ultimo_pdf_da_edicao(self):
        pasta_json = tempfile.mkdtemp()
        json_path = os.path.join(pasta_json, "clippings.json")
        with open(json_path, "w", encoding="utf-8") as f:
            f.write("[]")
        original = archive.ARCHIVE_DIR
        archive.ARCHIVE_DIR = tempfile.mkdtemp()
        try:
            quando = datetime(2026, 9, 28, 10, 19)
            pasta = os.path.join(archive.ARCHIVE_DIR, "2026-09-28")
            os.makedirs(pasta)
            for velho in ("clipping.pdf",
                          "2026.09.28 Clipping Atualização Semanal (21_09 - 28_09 às 9h00).pdf"):
                open(os.path.join(pasta, velho), "wb").close()
            novo = os.path.join(pasta_json,
                                "2026.09.28 Clipping Atualização Semanal (21_09 - 28_09 às 10h19).pdf")
            open(novo, "wb").close()
            import io, contextlib
            with contextlib.redirect_stdout(io.StringIO()):
                archive.archive_final(json_path, novo, when=quando, items=[])
            pdfs = [n for n in os.listdir(pasta) if n.endswith(".pdf")]
            self.assertEqual(pdfs, [os.path.basename(novo)])
        finally:
            archive.ARCHIVE_DIR = original

    def test_pdf_de_nome_antigo_sai_de_output(self):
        from services import pdf_builder
        raiz = tempfile.mkdtemp()
        saida, arquivo = os.path.join(raiz, "output"), os.path.join(raiz, "archive")
        os.makedirs(os.path.join(arquivo, "2026-09-22"))
        os.makedirs(saida)
        open(os.path.join(arquivo, "2026-09-22", "clipping.pdf"), "wb").close()
        atual = os.path.join(saida, "2026.09.28 Clipping Atualização Semanal (21_09 - 28_09 às 10h19).pdf")
        for caminho in (atual, os.path.join(saida, "clippings_output.pdf")):
            open(caminho, "wb").close()
        original = pdf_builder.ARCHIVE_DIR
        pdf_builder.ARCHIVE_DIR = arquivo
        try:
            pdf_builder._limpar_pdfs_antigos(atual)
        finally:
            pdf_builder.ARCHIVE_DIR = original
        self.assertEqual(os.listdir(saida), [os.path.basename(atual)])


if __name__ == "__main__":
    unittest.main(verbosity=2)
