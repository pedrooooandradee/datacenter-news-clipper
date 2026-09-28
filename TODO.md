# O que falta fazer

Atualizado em 28 set 2026. As tarefas da versão 1 que estavam aqui foram todas
feitas e saíram: deduplicação (`services/deduplicator.py`, dois estágios),
prompt do classificador (segunda passagem em `services/classifier.py`) e o
título que carregava o nome do veículo (`get_search_results.py`).

O porquê de cada decisão está em `DECISOES.md`. Isto aqui é só a fila.

---

## Antes de janeiro de 2027: o que depende do Edson

O Pedro sai da Elementum3 em janeiro. Estas definições são o que separa o clipping
de rodar sozinho ou parar. Levadas ao Edson em 28 set 2026; respostas pedidas até
o fim de outubro.

1. **Dono do clipping e substituto** — autoriza, aprova, decide o editorial.
2. **Envio** — destinatários na 247, contato lá, caixa de e-mail da empresa.
3. **OpenAI** — quem administra a organização `elementum3`; uma chave de conta de
   serviço num projeto só do clipping, com limite mensal. A chave em uso hoje chegou
   pelo Leo e está também na cópia antiga do iCloud: trocar e depois revogar.
4. **GitHub** — organização da Elementum3, para o Pedro transferir o repositório.
5. **Pasta corporativa** para `output/archive/`. Os PDFs enviados já têm lugar: a
   pasta "Clippings Semanais" do Drive (elementum3 | Geral › 247 DATA CENTERS), e o
   programa já os salva com o nome que ela usa.
6. **Máquina** — em qual computador roda. O README tem a instalação para Mac,
   Windows e Linux; o workflow do GitHub as instala do zero a cada mudança. O que
   falta é saber qual computador, e alguém instalar nele seguindo só o README.
7. **Uso de IA na revisão** — pode? Com qual conta?
8. **Suporte técnico** depois de janeiro.

Quando as respostas vierem: preencher a seção "Operação semanal" do `LEIA-ME.md`.

## Antes de janeiro de 2027: o que é do Pedro

- Revisar as edições de 05/10 e 12/10 **só com o checklist do LEIA-ME, sem IA**, e
  anotar o tempo. É o número que dimensiona a semana do sucessor.
- O sucessor instala tudo **sozinho**, no computador dele, seguindo só o README; cada
  tropeço vira linha no documento.
- Transferir o repositório; copiar `output/archive/` para a pasta da empresa; apagar
  a cópia do iCloud; no último dia, `gh auth logout`.
- Pedir ao Leo que arquive o repositório antigo (`github.com/Orimadros/…`), que
  segue público com a v1, com um aviso apontando para o novo.
- Na primeira edição com a busca nova (05/10), anotar o custo, o tempo e o número
  de notícias: ela traz o dobro de candidatas. Se a revisão ficar pesada demais,
  é a busca que se ajusta (DECISOES.md, "Busca com datas").
- Fatias de busca menores que uma semana: mesmo abaixo do teto de 100, pedir um
  intervalo menor traz mais notícias ("aws" em três dias trouxe 17 que a semana
  inteira não trouxe, a maioria fora do tema). Decidir com os números das
  primeiras edições se o que se ganha compensa a triagem e a revisão a mais.

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
- `date_outside_window` — a notícia é mais velha que a janela da edição.
- `numeros_nao_conferidos` — o resumo cita número que não está na matéria. Desde
  28/09 o bloco 🚨 reaparece no terminal a cada montagem do PDF, mas não no PDF.

Decidir se viram marca no PDF, linha no rodapé, ou nada.

## Limpeza

- `configs/overrides.json` declara `"versao": 1` e nada lê essa chave.
