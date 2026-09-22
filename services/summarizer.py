# services/summarizer.py

"""
Turning an article body into the paragraph that goes in the clipping.

Three things changed from the version that produced the 21/09 edition:

- The date stops being formatted here. It used to become "21 Set" at this point,
  which is why the deduplicator's tie-break on publication date could never have
  worked and why sorting by date was impossible downstream. The datetime now
  travels whole and is formatted in the template, at the last possible moment.

- The body stops being thrown away here. The structured record is extracted from
  it in the next stage, and it is dropped there, after it has been used.

- An empty summary is now a reported failure instead of an empty box in the PDF.
  It is retried once, and an article that still has nothing to say is taken out
  with its URL named, so it can be put back by hand.
"""

import os
from dotenv import load_dotenv
from typing import Dict, List
from datetime import datetime, timezone

from langchain_core.prompts import (
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate,
    ChatPromptTemplate,
)
from langchain_openai import ChatOpenAI

try:
    from services.utils.projeto import ler_config, modelo
except ImportError:
    from utils.projeto import ler_config, modelo

MAX_CHARS = 40000

# A summary shorter than this is not a summary. In the real edition every genuine
# paragraph is well past 120 characters; what comes in under it is the model
# saying, one way or another, that it could not read the page.
MIN_SUMMARY_CHARS = 120

load_dotenv()
SUMMARY_PROMPT_TEMPLATE = ler_config("summarization_prompt.txt")


def add_summaries(items: List[Dict]) -> List[Dict]:
    """
    Add a 'summary' to every item, keeping 'body' and the raw 'pubDate'.

    The body is needed by the next stage and is dropped there. The date stays a
    datetime all the way to the template.
    """
    system_msg = SystemMessagePromptTemplate.from_template(SUMMARY_PROMPT_TEMPLATE)
    human_msg = HumanMessagePromptTemplate.from_template(
        "Title: {title}\nSource: {source}\nURL: {url}\n\nArticle text:\n{body}"
    )
    prompt = ChatPromptTemplate.from_messages([system_msg, human_msg])

    llm = ChatOpenAI(
        temperature=0.0,
        model_name=modelo("resumo"),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        streaming=False,
    )

    falhas: List[str] = []

    for i, item in enumerate(items, 1):
        body = item.get("body", "") or ""
        if len(body) > MAX_CHARS:
            print(f"[{i}/{len(items)}] Corpo longo ({len(body)} caracteres), cortado "
                  f"em {MAX_CHARS}: {item.get('url', '')[:70]}")
            body = body[:MAX_CHARS]

        inputs = {
            "title": item.get("title", ""),
            "source": item.get("source", ""),
            "url": item.get("url", ""),
            "body": body,
        }

        texto = ""
        # One retry. The failures seen in practice are transient — a timeout, a
        # rate limit — and paying for a second call beats losing the article.
        for tentativa in (1, 2):
            try:
                response = llm.invoke(prompt.format_messages(**inputs))
                texto = (response.content or "").strip()
                if len(texto) >= MIN_SUMMARY_CHARS:
                    break
            except Exception as e:
                texto = ""
                if tentativa == 2:
                    falhas.append(f"{item.get('source', '?')} — "
                                  f"{item.get('title', '')[:50]} ({type(e).__name__})")

        item["summary"] = texto
        if len(texto) < MIN_SUMMARY_CHARS:
            item["summary_failed"] = True

    if falhas:
        print(f"⚠️  {len(falhas)} resumos falharam na chamada:")
        for entrada in falhas:
            print(f"     - {entrada}")

    return items


def drop_without_summary(items: List[Dict]) -> List[Dict]:
    """
    Remove the articles that ended up with no usable summary, and name them.

    An article with an empty summary reaches the PDF as a headline over a blank
    space — the reader sees a defect and cannot tell whether the news was empty or
    the program was. Taking it out and saying which one it was is the honest
    version, and the URL printed here is enough to put it back through
    configs/overrides.json.
    """
    kept, perdidas = [], []
    for item in items:
        resumo = (item.get("summary") or "").strip()
        if item.get("summary_failed") or len(resumo) < MIN_SUMMARY_CHARS:
            perdidas.append(f"{item.get('source', '?')} — {item.get('title', '')[:55]}\n"
                            f"       {item.get('url', '')}")
        else:
            kept.append(item)

    if perdidas:
        print(f"⚠️  {len(perdidas)} notícias DESCARTADAS por não terem resumo "
              f"aproveitável (a página carregou, o modelo não produziu texto):")
        for entrada in perdidas:
            print(f"     - {entrada}")

    return kept


if __name__ == "__main__":
    sample_items = [
        {
            "title": "Bitfarms forçada a interromper mineração de criptomoedas na Argentina",
            "source": "Data Center Dynamics",
            "url": "https://www.datacenterdynamics.com/br/noticias/bitfarms-argentina/",
            "pubDate": datetime.now(timezone.utc),
            "body": (
                "A Bitfarms, uma das maiores empresas de mineração de Bitcoin de capital "
                "aberto, foi forçada a interromper todas as operações em Río Cuarto, "
                "Argentina.\n\nA Bitfarms teve que cortar a energia em sua usina de 58 MW "
                "em Río Cuarto depois que a empresa local encarregada de fornecer energia "
                "para a instalação, a Generação Mediterránea SA (GMSA), foi forçada a "
                "pausar seu fornecimento em meio a uma disputa de reestruturação de "
                "crédito.\n\nInaugurada em 2022, a usina de Río Cuarto, de 58 MW, é a "
                "segunda maior instalação de mineração de Bitcoin da Bitfarms na América "
                "do Sul, perdendo apenas para a usina de Paso Pe, de 70 MW, no Paraguai."
            ),
        }
    ]
    result = add_summaries(sample_items)
    print("=== Resumo ===")
    for item in result:
        print(f"  {item['summary']}\n")
        print(f"  corpo preservado: {'body' in item}")
        print(f"  data ainda é datetime: {isinstance(item['pubDate'], datetime)}")
