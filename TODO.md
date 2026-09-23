# O que falta fazer

Atualizado em 23 set 2026. As tarefas da versão 1 que estavam aqui foram todas
feitas e saíram: deduplicação (`services/deduplicator.py`, dois estágios),
prompt do classificador (segunda passagem em `services/classifier.py`) e o
título que carregava o nome do veículo (`get_search_results.py`).

O porquê de cada decisão está em `DECISOES.md`. Isto aqui é só a fila.

---

## Decisões que dependem de mais edições

Nada a fazer agora: falta dado, não falta código.

- **As métricas (R$/MW, R$/m²) não renderizaram nenhuma vez.** Em 56 matérias,
  zero indicadores, e só duas quase-passagens — as duas barradas pela regra de
  que `capacidade_ti` exige a matéria dizer "MW de TI". Decidir depois de 2 ou 3
  edições: ou a regra afrouxa, ou a caixa de métricas sai do template.
- **Dez empresas na quarentena** (Terranova, Omnia WN Holding, CleanSpark,
  Munters, Moore Threads, BRQ, Anviran, PSR, Thymos, NEO). Pesquisar ficha só
  quando uma delas aparecer em 2 ou 3 edições seguidas.

## Regras decididas e não implementadas

- **Tier de fonte não protege número.** `can_carry_figure_alone()` existe em
  `services/utils/fontes.py` e ninguém a chama: um número de veículo tier 3 é
  publicado igual a um do Valor. Antes de ligar, decidir o que acontece quando o
  número reprova — derruba a notícia, publica sem o número, ou marca para
  conferência humana.

## Marcas que o programa grava e o PDF nunca mostra

Três campos são escritos no `output/clippings.json` e não aparecem em lugar
nenhum do PDF. Quem lê a edição não tem como saber:

- `date_unverified` — a data de publicação não pôde ser lida (8 notícias na
  edição de 22/09).
- `date_outside_window` — a notícia é mais velha que a janela de 7 dias.
- `numeros_nao_conferidos` — o resumo cita número que não está na matéria. Hoje
  isso só sai como o bloco 🚨 no terminal, durante a execução completa; quem só
  refaz o PDF não vê.

Decidir se viram marca no PDF, linha no rodapé, ou nada.

## Limpeza

- `tests/test_scraper.ipynb` — caderno da versão 1. Não roda: importa
  `requests`, `bs4` e `langchain.prompts`, nenhum dos três declarado. Era o
  único motivo de o `docling` estar no requirements.txt (1,3 GB de torch).
  O `docling` já saiu; o caderno pode sair junto.
- `configs/test_queries.json` — uma consulta só ("huawei cloud"), nenhum código
  lê, nenhum documento cita.
- `configs/overrides.json` declara `"versao": 1` e nada lê essa chave.

## Fora do código

- **O repositório está em conta pessoal do GitHub** (`Orimadros`). Transferir
  para uma conta da Elementum3 ou do conselho da 247 antes de janeiro de 2027.
- **Não existe documento de operação**: para quem vai o PDF, por qual canal, em
  que dia, quem aprova antes de enviar, quem tem a logo e quem paga a chave da
  OpenAI. Nada disso está escrito em lugar nenhum.
