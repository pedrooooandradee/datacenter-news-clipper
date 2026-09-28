# O que falta fazer

Atualizado em 28 set 2026. As tarefas da versão 1 que estavam aqui foram todas
feitas e saíram: deduplicação (`services/deduplicator.py`, dois estágios),
prompt do classificador (segunda passagem em `services/classifier.py`) e o
título que carregava o nome do veículo (`get_search_results.py`).

O porquê de cada decisão está em `DECISOES.md`. Isto aqui é só a fila.

---

## Primeiro da fila

- **A segunda etapa da deduplicação deixou passar casos óbvios** na edição de 28/09:
  dois artigos de opinião com o mesmo texto palavra por palavra, e o mesmo anúncio do
  Google Cloud em dois veículos. Ela é a rede de segurança do desenho em dois
  estágios, e desde 28/09 recebe o Google em três grupos de título em vez de dois.
  Na próxima edição, medir: quantos grupos chegam a ela, quantos ela junta, e ler o
  motivo dos que não junta. Ver DECISOES.md, "A edição de 28 set 2026".

## O que a conferência de 28/09 mostrou e continua manual

- **Mesmo fato, outra URL, na semana seguinte.** A regra nova tira só a URL idêntica.
  AZ Quest (Estadão → Fiis) e Odata (TELETIME → IT Forum) repetiram por outro veículo
  e dependem do revisor.
- **Notícia de paywall não tem como entrar.** O BID Invest avaliando US$ 300 mi para a
  Scala (BNamericas, tier 1) caiu na coleta, corretamente. Um bloco de inclusão manual
  no `overrides.json` foi proposto e **não aprovado** por ora.
- **A ficha marca número de mercado como número de projeto.** Os 661 MW de São Paulo
  inteiro saíram com `escopo: projeto` nos três veículos do relatório da Cushman. Sem
  efeito visível hoje, porque nenhum indicador foi calculado; com efeito no dia em que
  um capex cair ao lado. Também infla a completude de matéria de relatório de mercado.
- **A quarentena foi de 10 para 42 nomes**, e parte não é empresa: ANEEL, ONS,
  "Governo Federal", Associação Brasileira de Data Center, a associação das empresas
  de TIC, LAWINFRA (um evento). Candidatos ao bloco `nao_empresas` de
  `configs/empresas.json`. Quinze nomes vêm de um único artigo (cryptoid.com.br) que
  lista fornecedores — padrão de conteúdo patrocinado.

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

- `configs/overrides.json` declara `"versao": 1` e nada lê essa chave.

## Fora do código

- **Transferir o repositório** (`https://github.com/pedrooooandradee/datacenter-news-clipper`) para uma conta da Elementum3 ou do
  conselho da 247 antes de janeiro de 2027. Está na conta pessoal do Pedro: depois
  que ele sair, ninguém transfere. O repositório antigo (`Orimadros`) é da conta do
  Leo e segue público com a v1 — vale pedir a ele que o arquive, com um aviso
  apontando para o novo.
- **Não existe documento de operação**: para quem vai o PDF, por qual canal, em
  que dia, quem aprova antes de enviar e quem paga a chave da
  OpenAI. Nada disso está escrito em lugar nenhum.
