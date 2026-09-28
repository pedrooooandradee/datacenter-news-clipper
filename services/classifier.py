import json
import unicodedata
from datetime import datetime, timezone
from typing import List, Dict, Tuple

from dotenv import load_dotenv, find_dotenv
from langchain_core.prompts import (
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate,
    ChatPromptTemplate,
)
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser

try:
    from services.utils.projeto import (
        ler_config, modelo, descrever_erro, parar_se_sem_credito,
    )
except ImportError:
    from utils.projeto import ler_config, modelo, descrever_erro, parar_se_sem_credito

# Load environment exactly as in the notebook
_ = load_dotenv(find_dotenv())

# The prompt is part of the program, so it is found relative to the program. The
# old relative path worked only when the caller happened to be standing in the
# project root, and raised FileNotFoundError from anywhere else.
CLASSIFICATION_PROMPT_TEMPLATE = ler_config("classification_prompt.txt")

# The template only renders these five. A category outside the list makes the news
# item vanish from the PDF without a word, so every label is normalised back into it.
VALID_CATEGORIES = ["clientes", "competidores", "governo", "inovação", "outros"]
FALLBACK_CATEGORY = "outros"


def _strip_accents(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn"
    )


def normalize_category(raw: str) -> Tuple[str, bool]:
    """
    Map whatever the model returned onto one of the five categories the template
    renders.

    "inovacao" without the cedilla, "Inovação" capitalised, or " governo " with
    stray spaces used to reach the PDF unchanged — and anything the template does
    not recognise is simply not drawn, so the article disappears with no error.

    Returns:
        (category, was_recognised)
    """
    if not raw:
        return FALLBACK_CATEGORY, False

    key = _strip_accents(raw.strip().lower())
    for valid in VALID_CATEGORIES:
        if key == _strip_accents(valid):
            return valid, True
    return FALLBACK_CATEGORY, False


def add_classifications(items: List[Dict]) -> List[Dict]:
    """
    Annotate each item with 'class' and 'category'.

    A single malformed response used to raise out of json.loads and kill the run
    after the API had already been paid for. Each item is now handled on its own,
    and an item that cannot be classified is KEPT rather than dropped: this pass
    exists to discard obvious noise, so when in doubt the article survives to be
    judged later, by a human or by a second pass over the summary.
    """
    system_msg = SystemMessagePromptTemplate.from_template(CLASSIFICATION_PROMPT_TEMPLATE)
    human_msg = HumanMessagePromptTemplate.from_template("News Piece Title: {title}\nURL: {url}")
    prompt = ChatPromptTemplate.from_messages([system_msg, human_msg])

    # JSON mode makes the model return parseable output instead of prose around it.
    llm = ChatOpenAI(
        temperature=0.0,
        model_name=modelo("triagem"),
        model_kwargs={"response_format": {"type": "json_object"}},
    )
    chain = prompt | llm | StrOutputParser()

    failures: List[str] = []
    unknown_categories: List[str] = []

    for item in items:
        title = item.get("title", "")
        try:
            raw = chain.invoke({"title": title, "url": item.get("url", "")})
            result = json.loads(raw)
        except Exception as e:
            # No credit is not a failure of this one story: every call after it
            # fails the same way. This is the first paid call of the run, so it
            # stops here, before half an hour of scraping.
            parar_se_sem_credito(e, retomar_de="classify")
            # Keep the article and say so; losing it silently is the worse failure.
            # The class name alone ("NotFoundError") hid the reason; the message
            # says "model ... does not exist" or "invalid api key".
            failures.append(f"{title[:70]} ({descrever_erro(e)})")
            item["class"] = "relevant"
            item["category"] = FALLBACK_CATEGORY
            item["classification_failed"] = True
            continue

        label = str(result.get("label", "irrelevant")).strip().lower()
        if label not in ("relevant", "irrelevant"):
            failures.append(f"{title[:70]} (label inesperado: {label!r})")
            label = "relevant"

        if label == "relevant":
            raw_category = str(result.get("category", ""))
            category, recognised = normalize_category(raw_category)
            if not recognised:
                unknown_categories.append(f"{raw_category!r} → {category} ({title[:50]})")
        else:
            category = ""

        item["class"] = label
        item["category"] = category

    # Nothing the pipeline could not handle stays quiet (DECISOES.md, Q24).
    if failures:
        print(f"⚠️  {len(failures)} notícias não puderam ser classificadas e foram MANTIDAS "
              f"como '{FALLBACK_CATEGORY}' para revisão manual:")
        for f in failures:
            print(f"     - {f}")
    if unknown_categories:
        print(f"⚠️  {len(unknown_categories)} categorias fora da lista foram normalizadas:")
        for u in unknown_categories:
            print(f"     - {u}")

    return items


SEGUNDA_PASSAGEM = """SEGUNDA PASSAGEM.

Na primeira vez você viu apenas o título e a URL, e sua tarefa era descartar lixo
óbvio. Agora você recebe também o RESUMO já publicado da matéria, que é a evidência
principal. Os critérios das cinco categorias são exatamente os mesmos de cima.

Duas diferenças:

1. Sua tarefa aqui é definir a CATEGORIA FINAL. Um título sobre "IA no Brasil" que
   o resumo revela ser um anúncio de capex da AWS é clientes, não outros.
2. Se, com o resumo à vista, a matéria não atender a nenhum critério, responda
   label "irrelevant". Isso NÃO descarta a notícia: ela é apenas marcada para
   revisão humana. Quem decide tirar é uma pessoa.

Responda no mesmo formato de antes, um único objeto JSON com label e category."""


def reclassify_with_summary(items: List[Dict]) -> List[Dict]:
    """
    Decide the final category with the summary in hand (DECISOES.md, Q13).

    The first pass sees a headline, which is written to be clicked. "Governo
    discute infraestrutura digital" and "Nova fábrica de chips no Ceará" land in
    the wrong section often enough that the section stopped meaning anything.

    Nothing is removed here. An article the model now calls irrelevant keeps its
    place and is reported, because the first pass exists to discard noise and this
    one exists to file what survived.
    """
    if not items:
        return items

    system_msg = SystemMessagePromptTemplate.from_template(CLASSIFICATION_PROMPT_TEMPLATE)
    addendum = SystemMessagePromptTemplate.from_template(SEGUNDA_PASSAGEM)
    human_msg = HumanMessagePromptTemplate.from_template(
        "News Piece Title: {title}\nSource: {source}\nSummary: {summary}"
    )
    prompt = ChatPromptTemplate.from_messages([system_msg, addendum, human_msg])

    llm = ChatOpenAI(
        temperature=0.0,
        model_name=modelo("reclassificacao"),
        model_kwargs={"response_format": {"type": "json_object"}},
    )
    chain = prompt | llm | StrOutputParser()

    mudancas: List[str] = []
    agora_irrelevantes: List[str] = []
    falhas: List[str] = []

    for item in items:
        summary = item.get("summary", "") or ""
        if not summary:
            continue

        antes = item.get("category", "")
        try:
            raw = chain.invoke({
                "title": item.get("title", ""),
                "source": item.get("source", ""),
                "summary": summary[:2000],
            })
            result = json.loads(raw)
        except Exception as e:
            # The first pass already gave this item a category; keeping it is
            # strictly better than losing the article to a parsing error.
            falhas.append(f"{item.get('title', '')[:60]} ({type(e).__name__})")
            continue

        label = str(result.get("label", "relevant")).strip().lower()
        if label == "irrelevant":
            item["segunda_passagem_irrelevante"] = True
            agora_irrelevantes.append(
                f"{item.get('source', '?')} — {item.get('title', '')[:60]}"
            )
            continue

        categoria, reconhecida = normalize_category(str(result.get("category", "")))
        if not reconhecida:
            continue
        if categoria != antes:
            item["category"] = categoria
            item["categoria_primeira_passagem"] = antes
            mudancas.append(f"{antes} → {categoria}: {item.get('title', '')[:55]}")

    print(f"Segunda passagem de classificação: {len(mudancas)} categorias corrigidas "
          f"pelo resumo.")
    for entrada in mudancas:
        print(f"     - {entrada}")
    if agora_irrelevantes:
        print(f"⚠️  {len(agora_irrelevantes)} notícias que o resumo mostra não atender aos "
              f"critérios. MANTIDAS — quem tira é uma pessoa, por configs/overrides.json:")
        for entrada in agora_irrelevantes:
            print(f"     - {entrada}")
    if falhas:
        print(f"⚠️  {len(falhas)} reclassificações falharam; a categoria da primeira "
              f"passagem foi mantida:")
        for entrada in falhas:
            print(f"     - {entrada}")

    return items


def drop_irrelevant(items: List[Dict]) -> List[Dict]:
    """
    Filter the list of items to include only those classified as "relevant".
    """
    return [item for item in items if item.get("class", "").lower() == "relevant"]


if __name__ == "__main__":
    # Category normalisation runs without touching the API.
    print("=== Normalização de categorias ===")
    for raw in ["inovação", "inovacao", "Inovação", " GOVERNO ", "Competidores",
                "tecnologia", "mercado", "", "hardware"]:
        category, recognised = normalize_category(raw)
        status = "reconhecida" if recognised else "NÃO reconhecida, virou fallback"
        print(f"  {raw!r:16} → {category!r:14} ({status})")

    # Sample test items (hits the API)
    test_items = [
        {
            "title": "Bitfarms forçada a interromper mineração de criptomoedas em seu data center na Argentina",
            "source": "Data Center Dynamics",
            "url": "https://www.datacenterdynamics.com/br/noticias/bitfarms-argentina/",
            "pubDate": datetime.now(timezone.utc),
        },
        {
            "title": "Equinix investe em datacenters no Rio Grande do Norte",
            "source": "Tech News Brasil",
            "url": "https://example.com/equinix-rio-grande-do-norte",
            "pubDate": datetime.now(timezone.utc),
        },
    ]

    print("\n=== Classification Results (usa a API) ===")
    for idx, item in enumerate(add_classifications(test_items), start=1):
        print(f"Item {idx}:")
        print(f"  Title: {item['title']}")
        print(f"  Class: {item['class']}")
        print(f"  Category: {item['category']}\n")
