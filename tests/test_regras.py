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
from datetime import datetime, timedelta, timezone

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
)
from services.scraper import looks_blocked, cortar_no_paywall
from services.utils.get_search_results import collect_search_results_from_rss
from services.utils import trava, archive


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

    def test_arquivo_quebrado_nao_derruba_a_execucao(self):
        caminho = os.path.join(tempfile.mkdtemp(), "overrides.json")
        with open(caminho, "w", encoding="utf-8") as f:
            f.write("{ isto não é json,")
        final, relatorio = overrides.aplicar(self._items(), caminho)
        self.assertEqual(len(final), 2)


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

        abertura = (datetime.now(timezone.utc) - timedelta(days=7)).date()
        # Right after midnight on the opening day: inside the window by civil
        # day, and older than 7 * 24 hours at any hour this is run.
        na_abertura = datetime.combine(abertura, time(0, 0), tzinfo=timezone.utc)

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


if __name__ == "__main__":
    unittest.main(verbosity=2)
