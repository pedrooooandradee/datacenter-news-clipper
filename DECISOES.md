# Decisões de arquitetura — versão 2 do clipping 247

Registro da sessão de 21–22 set 2026 (Pedro + Claude). Fechado após 24 decisões.
Este arquivo é a fonte de verdade do desenho. Mudou de ideia? Edite aqui primeiro.

## Contexto

Clipping semanal de notícias de data center para os executivos e o conselho da
247. Público: investidores de infraestrutura, não leitores de tecnologia.
O documento circula por e-mail. Toda decisão abaixo parte disso.

## Por que a versão 2

Diagnóstico sobre a edição de 21 set 2026 (`output/clippings.json`, 53 itens,
saída crua do modelo, antes da edição manual):

- **Dedup falhou.** 3 itens do cluster EVEO/Recife sobreviveram; 14 itens tocam a
  sanção do ReData; 2 itens idênticos sobre a sanção (UOL e 18horas).
- **O resumo inventa sujeito.** `agorarn.com.br`: "A Redata anunciou a construção
  de um data center" — ReData é o regime tributário, não uma empresa.
- **O resumo mistura escopos.** Exame: números do mercado brasileiro (106 MW,
  US$ 8 bi, vacância 4%) dentro da notícia do data center da EVEO.
- **Fonte sem filtro.** `samiabomfim.com.br` (site de mandato parlamentar) e
  `shattered.io` (conteúdo SEO, "[2026]" no título) na edição enviada.
- **A dedup roda depois de pagar tudo.** Scrape (um Chrome novo por artigo) e
  resumo de todos os itens antes de descartar os duplicados.

## Decisões

### Arquitetura
| # | Decisão |
|---|---|
| Q1 | Dedup em dois estágios: embeddings antes do scrape, LLM sobre os resumos depois |
| Q13 | Classificação em dois passes: triagem barata no título (só descarta lixo óbvio) → re-classificação com o resumo define a categoria final |
| Q22 | O cluster pré-scrape scrapeia os dois melhores por tier; a ficha decide entre eles |
| Q6 | Cache por etapa, com `--from=<etapa>` para refazer sem repagar |
| Q7 | Trabalho fora do iCloud (`~/dev/`), repo privado |
| Q23 | Continua específico da 247; sem camada de multi-cliente |

### Deduplicação
| # | Decisão |
|---|---|
| Q8 | `text-embedding-3-small`, limiar alto e conservador, calibrado nos 53 itens reais. A fusão pré-scrape é irreversível |
| Q14 | Sobrevivente = mais completo medido na **ficha** (fatos sobre o sujeito, não sobre o mercado), com tier de fonte como **portão de elegibilidade**, não desempate |
| Q9 | O descartado não some: fica com `duplicate_of` e vira a linha "também noticiado por: …" |

### Features novas
| # | Decisão |
|---|---|
| Q2 | Ficha estruturada + ratio calculado em Python. Não pareou mesmo projeto e mesma fase, não publica |
| Q12 | Extração lê o corpo; só publica ratio cujos dois números também aparecem no resumo acima |
| Q19 | Ficha estendida. PUE, vacância, R$/kW-mês: capturados com fonte, nunca derivados |
| Q3/Q4/Q18 | Lista curada de empresas conhecidas, com aliases e cadeia de controle; empresa nova → busca ao vivo → quarentena |
| Q20 | Overview uma vez por edição, na primeira aparição |
| Q16/Q17 | Tudo inline sob a notícia; sem apêndice, sem benchmark de mercado |

### Operação
| # | Decisão |
|---|---|
| Q11 | Econômico na triagem; médio no resumo, ficha, re-classificação e confirmação de dedup. ID escolhido por teste nos 53 itens |
| Q15 | `overrides.json` commitado — vira o conjunto de exemplos reais para os prompts |
| Q21 | Arquivamento entra primeiro. Teste inicial: rotular à mão os grupos nos 53 itens |
| Q24 | **Nenhum corte silencioso.** Toda notícia, duplicata ou caixa omitida é reportada em voz alta no fim da execução |

## Regras que valem em todo o sistema

1. **Nenhum corte silencioso** (Q24). O que o código descarta, ele diz.
2. **Não pareou, não publica** (Q2). Ratio sem fase e escopo casados não sai.
3. **Auditável contra o texto acima** (Q12). Número que o leitor não consegue
   conferir no resumo não vira ratio.
4. **Captura, não deriva** (Q19). KPI de mercado se copia com a fonte.
5. **Empresa nova fica em quarentena** (Q3). Nunca se publica perfil não revisado.

## Ordem de trabalho

1. ~~Arquivamento das edições (`output/archive/AAAA-MM-DD/`)~~ — **feito em 22 set 2026**
2. ~~Cache por etapa~~ — **feito em 22 set 2026** (`--from=<etapa>`)
3. ~~Camada de extração~~ — **feita em 22 set 2026**: nome da fonte, erro tratado
   por item, categoria normalizada e validada, driver único, trafilatura no lugar
   do Docling, filtro de data por metadados, corpo mínimo, portão de tier
4. ~~Deduplicação~~ — **feita em 22 set 2026**
5. ~~Features novas atrás do portão de confiança~~ — **feitas em 22 set 2026**:
   ficha estruturada, ratios em Python, caixas de empresa, segunda passagem de
   classificação
6. ~~`overrides.json`~~ — **feito em 22 set 2026**
7. ~~LEIA-ME e COMANDOS atualizados~~ — **feitos em 22 set 2026**, mais três
   correções cirúrgicas no `README.md`

## Correções pequenas que entram na etapa 3

- Nome da fonte: `rsplit(" - ")` em `get_search_results.py:61` corta pelo
  separador errado ("Finanças, Câmbio e Investimentos" para o Investing.com).
  Usar `entry.source.title` do feed e limpar sufixos do título.
- Índice cortando palavra no meio ("Inves[...]"): cortar na última palavra inteira.
- Ordem dentro da categoria: grifadas primeiro, depois data decrescente.
- ~~`pdf_builder.py`: a linha `today = datetime(2026, 9, 14, 9, 30)` é código
  morto~~ — removida.
- ~~`select_best_from_group` nunca é chamada e não funcionaria: o `pubDate` já
  chega como "18 Set"~~ — a função saiu na reescrita, e a data agora **atravessa
  o pipeline como `datetime`** e só vira texto no template. A exibição passou a
  preferir a data da própria página (`page_date`) à data do feed, que é a que
  mentiu no caso da matéria de 2012 sobre a AMD.

## Fora de escopo, registrado

- **Grifo automático** das notícias mais importantes. Hoje é manual. A ficha já
  carrega os sinais que um ranqueador precisaria, então não fica bloqueado.

## Medições da camada de extração (22 set 2026)

Investigação com três agentes, cada um com um refutador adversarial. **Os
refutadores derrubaram 2 das 3 recomendações**, e num caso a instrução original
teria destruído a manchete da semana.

**Extrator de corpo.** Docling contra trafilatura, sobre o MESMO HTML, 18 artigos:

| método | contaminação | mediana de chars | números fantasma |
|---|---|---|---|
| Docling (o antigo) | 78% (14/18) | 10.498 | **54**, em 14 de 18 |
| trafilatura | 22% | ~3.600 | 0 |

Exemplos de número fantasma do Docling: "Galaxy A37 tem queda de 55% com cupom"
dentro da matéria do data center do TikTok; "2026%" e "09%" vindos de URLs de
compartilhamento percent-encoded. É a mesma família do "30%" que foi publicado.

Correções do refutador que entraram no código:
- `d.get("description")` **não existe** no trafilatura 2.2.0 — o campo é `excerpt`
  (ausente em 0/53 contra presente em 44/53). Com o campo errado o InvestNews
  perdia "US$ 2,3 bilhões" e "8,25%".
- Limiar de corpo: **500**, não 700. "menor que 500 OU marcador de bloqueio" pega
  as 8 falhas verdadeiras sem descartar matéria boa; 700 descartaria o Valor.

**Data de publicação.** Cobertura real 90,6% (48/53), não os 94,3% publicados pelo
investigador — não era reproduzível. A janela é por **dia civil**, não por
`agora − 7×24h`: a regra original descartaria 6 matérias legítimas, incluindo
"Lula sanciona ReData" em três veículos. Descarte só acima de 30 dias de margem
(a matéria da AMD está 5.060 dias fora). Sem data: mantém e marca.

**Causa-raiz que os dois agentes acharam junto:** o `sleep(2.0)` fixo não resolvia
o redirecionamento do Google News, e 3 de 53 URLs nunca viravam a matéria real.
Sem URL real não há data de página — era por aí que a AMD de 2012 entrava.

**Bloqueio por sessão do navegador.** O reuso do driver, recomendado pela
velocidade, é o que ativa a detecção de robô. Medido em 5 matérias da DCD:

| estratégia | aproveitadas | tempo |
|---|---|---|
| mesmo driver, sem espera | 1/5 | — |
| mesmo driver, 20s entre cada | 1/5 | 82s |
| driver novo a cada requisição | 4/5 | 7s |

Não é taxa nem IP: é a sessão que fica marcada, e esperar não limpa. O código reusa
por padrão e recicla o Chrome só quando a página volta bloqueada. Duas hipóteses
minhas foram derrubadas pelos dados antes disso: `page_load_strategy` (a DCD
funciona nas duas, isolada) e o `reset_state()` apagando o cookie do Cloudflare
(piora de 2/6 para 1/6, mas não é a causa).

**Resultado final nas 53 URLs reais:**

| | antes | depois |
|---|---|---|
| corpo aproveitável | — | **47/53 (89%)** |
| falhas da DCD | 6 | **1** |
| tempo por artigo | ~24s | **2,4s** |
| data da página | — | 38/47 (81%) das que carregaram |

As 6 restantes são bloqueio real: 1 DCD, vocativo e Revista Empreende (Cloudflare),
2 BNamericas (paywall de verdade) e inforchannel (403 por qualquer método).

A cobertura de data que eu medi (81% das que carregaram) ficou **abaixo dos 90,6%
apurados na investigação**. Não sei explicar a diferença com o que tenho; o número
a usar é o medido no pipeline real, não o da investigação.

## Medições da deduplicação (22 set 2026)

**Limiar de embedding, calibrado nas 53 reais.** Os pares verdadeiros descem até
0.768 e o primeiro falso está em 0.722 — há um vão, e 0.75 cai dentro dele.

Sinal que apareceu na calibragem: **para duplicata de verdade, somar o resumo
AUMENTA a semelhança** (EVEO 0.799 → 0.899, MP Campinas 0.673 → 0.819); para
vizinho de assunto, DIMINUI (0.722 → 0.667). É por isso que o estágio barato usa
título e o estágio de confirmação usa resumo.

**Medida de completude.** Números do resumo descontados os que estão em frase
enquadrada no mercado. No cluster EVEO: BNamericas 9, Exame 2, DCD 2 — e a
BNamericas é a única com capex, capacidade e fase do projeto. Por caracteres, a
Exame venceria (620 contra 516).

**O portão de tier é o que salva o caso de Campinas.** O site de mandato tinha 4
números contra 1 do g1. Por completude, o blog de campanha seria publicado.

**Resultado nas 53:** 52 → 46, 6 grupos de duplicatas, incluindo a cobertura
redundante da Computer Weekly sobre o ReData. Os sobreviventes batem com o que
vocês escolheram à mão: MegaWhat em vez da DCD, UOL em vez de 18horas.

**Economia do estágio pré-scrape: 1 coleta em 53.** Bem menos do que eu sugeri ao
propor o desenho. Guardar os dois melhores de cada grupo (Q22) significa que grupo
de 2 não economiza nada — só o grupo de 3 rendeu. O valor do estágio é o
agrupamento, não a economia.

## Correções de apresentação (22 set 2026)

- Linha "Também noticiado por" sob o resumo, no PDF.
- Índice cortava no meio da palavra em **14 de 18** títulos longos. Trocado pelo
  `truncate` do Jinja, que corta na última palavra inteira.
- Ordem dentro da categoria: grifadas primeiro, depois por data decrescente.
  Antes era a ordem do RSS, que não é ordem nenhuma.

## A ficha, os ratios e as caixas de empresa (22 set 2026)

**O desenho em uma linha: o modelo só COPIA número; o Python decide o que ele
significa e se pode sair.** Quatro portões, todos em código, todos capazes de
jogar um número fora:

1. o número tem de existir no corpo da matéria — contra número inventado
2. a frase citada tem de conter o número — contra número atribuído ao fato errado
3. o número tem de aparecer no resumo publicado — Q12, o leitor tem de conferir
4. os dois lados do ratio precisam do mesmo escopo, da mesma fase e da mesma moeda

**Medição nas matérias reais desta edição.** Sete das oito notícias com número
foram recoletadas e passadas pelo extrator (a oitava, da BNamericas, tem paywall).

| caso | o que aconteceu | certo? |
|---|---|---|
| ReData, "data center de 100 MW podendo gerar R$ 25 bi" | marcado `hipotetico`, nenhum ratio | sim — é exemplo do governo |
| Exame / EVEO, US$ 8 bi + 106 MW | marcados `mercado_brasil`, nenhum ratio | sim — são do mercado, não do projeto |
| Exame, vacância de 4% | virou KPI reportado, nunca dividido | sim (Q19) |
| g1 / Caucaia, R$ 580 bi + 200 MW | nenhum ratio | sim, mas por acidente — ver faixa abaixo |
| samiabomfim, dois capex no mesmo escopo e fase | nenhum ratio, ambiguidade reportada | sim |
| CNN, "R$ 30 bi", "170 GW", "200 GW" | **os três recusados: não existem na matéria** | sim — ver abaixo |

**Ratios publicáveis nesta amostra: zero.** É resultado honesto, não defeito: das
sete, nenhuma tinha capex e capacidade do mesmo projeto, na mesma fase, os dois no
resumo. O programa diz isso em voz alta no fim da execução, com o motivo de cada
não-pareamento.

### O achado mais caro da auditoria

O artigo da CNN de 17/09 é uma **coluna de opinião sem um único número**. A palavra
"bilhões" aparece **zero vezes na página inteira** — não no corpo extraído, na
página. E o resumo publicado na edição de 21/09 diz:

> "previsão de investimento de **R$ 30 bilhões** até 2025 [...] a capacidade
> instalada é de **170 GW**, mas a demanda pode chegar a **200 GW**"

Os três números foram inventados pelo modelo de resumo e foram para os
investidores. Não é contaminação do Docling (que explicaria números de outra parte
da página): não há número nenhum na página.

Por isso a conferência do resumo passou a rodar em **toda** notícia, não só nas
que geram ficha, e imprime um bloco 🚨 no fim da execução. O resumo **não** é
alterado sozinho — o leitor de números pode errar uma grafia incomum, e destruir
resumo bom por causa disso seria pior. Segundo caso na mesma amostra: o agorarn,
com "R$ 1 bilhão" que também não está na matéria.

### Caixas de empresa

Identificação por apelido, com uma regra contra falso positivo: apelido de uma só
palavra e até 10 caracteres ("Positivo", "Atlantic", "Meta") exige a grafia exata
do arquivo **e** confirmação de que o extrator listou aquilo como empresa. Sem
isso, "resultado positivo da companhia" ganharia uma caixa sobre fabricante de
computador. Testado: "resultado positivo" e "a meta do governo" não casam;
"Positivo Tecnologia" casa.

Na edição real: **7 caixas**, uma por empresa, na primeira aparição de cada
(Kuehne+Nagel, EVEO, Atlantic, Positivo, TD SYNNEX, AZ Quest, EAF). A quarentena
pegou 4 empresas novas sem ficha, que **não** saem no PDF.

A quarentena também pegou "**Redata**" como empresa nova — que é exatamente o
defeito diagnosticado ("A Redata anunciou a construção de um data center"). Daí o
bloco `nao_empresas` no `configs/empresas.json`.

### Segunda passagem de classificação (Q13)

Estava decidida e não existia no código. Agora roda depois do resumo, com o
resumo à vista, e só define a categoria final — não descarta nada. Notícia que a
segunda passagem considera irrelevante é **mantida e reportada**; quem tira é uma
pessoa, pelo `overrides.json`.

## Regras acrescentadas na implementação — ACEITAS pelo Pedro em 22 set 2026

Nenhuma destas estava nas 24 decisões originais. Todas apareceram em dado real
durante a implementação ou na primeira execução completa, foram apresentadas uma
a uma com o custo de não tê-las, e foram aceitas em bloco.

A única que o Pedro foi avisado ser discutível é a **A**: ela esconde do leitor um
número que o jornal publicou. As outras oito apenas impedem defeito.

| # | regra | por quê | onde |
|---|---|---|---|
| A | **Faixa de plausibilidade** nos ratios: fora de quatro ordens de grandeza, não publica e reporta | g1 escreveu "investimento de mais de R$ 580 bilhões" para Caucaia; ao lado de 200 MW isso dá **R$ 2,9 bi/MW**. A conta está certa e o número é absurdo | `ficha.py`, `FAIXAS_PLAUSIVEIS` |
| B | **Conferir todo número do resumo** contra o corpo, e avisar | o caso da CNN acima | `ficha.py`, `conferir_resumo` |
| C | **Portão de tier também na montagem do PDF** | remontar um `clippings.json` antigo pulava o portão; no teste, o item de SEO "[2026]" voltou ao índice | `pdf_builder.py` |
| D | **Resumo vazio descarta a notícia**, com URL nomeada | resumo vazio vira caixa em branco no PDF; o leitor vê defeito e não sabe de quem | `summarizer.py` |
| E | **Bloco `nao_empresas`** | ReData, FGV e ABEEólica voltavam toda semana na lista de quarentena, que é lida por gente | `configs/empresas.json` |
| F | **`configs/modelos.json`** | a Q11 separou econômico de médio mas deixou o ID em aberto. O arquivo centraliza a escolha sem inventar um ID: tudo aponta para `gpt-4o-mini`, que é o único comportamento medido | `configs/modelos.json` |
| G | **Cópia da versão anterior** do `clippings.json` antes de reescrever | `--from` reescreve o arquivo e levaria junto edição manual não salva em overrides | `main.py` |
| H | **`gpt-4o` só na confirmação de duplicatas** | o `gpt-4o-mini` agrupava por assunto e removia 8 notícias boas por edição; é uma chamada por edição, ~US$ 0,04 | `configs/modelos.json` |
| I | **Trava de execução, uma por vez** | duas execuções simultâneas em 22 set 2026 disputaram o mesmo `output/` e fizeram o relatório de edição manual mentir | `services/utils/trava.py` |

Duas decisões menores, também minhas: `ano_operacao` virou `previsao_operacao` e
guarda o texto como veio ("primeiro semestre de 2026"), que é o que a decisão 3 da
proposta 3 pedia; e o ratio `capacidade_ti / area_construida` sai em **kW/m²**,
que é como o setor escreve densidade de potência.

## O custo da regra de MW de TI, medido

A proposta 3 decidiu marcar `capacidade_ti` só quando a matéria disser "MW de TI",
e os quatro ratios aprovados dividem por `capacidade_ti`. Na prática a imprensa
brasileira quase nunca faz a distinção.

**Nas 7 matérias testadas, 2 teriam pareado se `energia_contratada` valesse**
(g1/Caucaia e samiabomfim/Campinas). O programa conta isso toda semana, na linha
"parearia, mas a matéria não diz que os MW são de TI".

Se depois de algumas edições o número for alto, a saída não é afrouxar a regra: é
publicar o ratio **com o rótulo explícito** ("R$ 50 mi por MW contratado"). Não
fiz isso agora porque não estava na proposta aprovada. Sua chamada.

## Decisão pendente: remover o docling?

Nenhum código do pipeline importa docling desde 22 set 2026 — só
`tests/test_scraper.ipynb`. Tirá-lo do `requirements.txt` leva junto torch (583 MB),
torchvision, transformers e accelerate. O venv cai de 1,5 GB para algo perto de
200 MB, e a instalação para gente nova deixa de levar dez minutos.

Custo: o notebook de teste para de rodar sem ajuste. Decisão do Pedro.

## Ruído no terminal: acabou

Esta seção registrava que toda execução imprimia
`Preset 'granite_vision_v4' already registered ...`, vindo do import do docling.

**Não imprime mais.** Conferido em 22 set 2026: `python main.py --help` sai limpo,
e importar o `pdf_builder` também. O aviso desapareceu junto com o import do
docling, e a seção antiga contradizia a seção de baixo, do próprio documento, que
diz que nada no pipeline importa docling. Comentário que mente é defeito, e este
estava no arquivo que é a fonte de verdade do desenho.

## Nota de ambiente (descoberta em 22 set 2026)

O `README.md` manda instalar cairo/pango pelo Homebrew. **Não foi assim que esta
máquina foi montada.** Não há Homebrew; existe um ambiente conda dedicado em
`~/.clipping247-python` (Python 3.12.2) que já traz `libpango`, `libcairo` e
companhia, e é dele que o venv que funciona foi criado.

Consequência prática: um venv criado com o `python3` do PATH (que aqui resolve
para o Anaconda) instala o WeasyPrint mas quebra no import, com
`cannot load library 'libpango-1.0-0'`. O venv tem de ser criado assim:

```
/Users/pedroandrade/.clipping247-python/bin/python3 -m venv venv
```

Isso precisa entrar no README na etapa 7, senão queima a próxima pessoa que
montar o projeto — inclusive se isto virar a versão oficial da Elementum3.

## Auditoria adversarial (22 set 2026)

Quatro auditores, um por dimensão — fluxo de dados, risco editorial, robustez e
coerência com este documento —, cada achado submetido a três céticos com lentes
diferentes (reproduzir, procurar a guarda que já existe, julgar se importa).
Maioria refutando mata o achado.

**48 achados, 16 sobreviveram.** Os 32 derrubados incluem coisas que pareciam
graves e não eram, e é por isso que a refutação existe.

Cinco dos 16 já estavam consertados quando o laudo chegou — eu os tinha corrigido
enquanto a auditoria rodava. Os outros onze entraram:

| # | o que estava errado | conserto |
|---|---|---|
| 1 | O corte de janela do RSS era por **24h rolante** e não contava nada. Único ponto do pipeline sem relato, e a matéria da manhã em que a janela abre morria ali, antes de qualquer contador | dia civil, igual ao filtro de baixo, e relatório por consulta |
| 2 | **Consulta que falha na rede é indistinguível de "não houve notícia".** O `feedparser` não levanta exceção: um 429 do Google devolve feed vazio. Um concorrente inteiro sumiria da edição e pareceria semana parada | checagem de `bozo`/`status`, e a execução diz quais consultas falharam e quais vieram vazias |
| 3 | **Paywall que vaza** passava: `looks_blocked` só olhava os primeiros 1.200 caracteres, então o anúncio de assinatura no fim de uma matéria longa ia para o resumo | marcador no fim corta o texto ali e mantém a reportagem de cima |
| 4 | **Data ilegível no RSS virava "agora"**, o que fazia o item passar na janela e imprimia a data de hoje ao lado da manchete | `pubDate = None`, contado e relatado; a data vem da página |
| 5 | `archive_final` gravava na pasta do **dia da reconstrução**, não da edição: cru e final em pastas diferentes, e o diff nunca rodava | `output/edicao_atual.json` guarda o fechamento; tudo se data por ele |
| 6 | O **cabeçalho de toda página** vinha de `datetime.now()`: refazer na segunda o PDF de sexta declarava a semana errada | cabeçalho pela data da edição |
| 7 | **Cache sem prazo**: `--from` sobre cache de três semanas publica notícia velha sob cabeçalho de hoje | aviso a partir de 2 dias, aviso graúdo a partir de 7 |
| 8 | O grupo pré-scrape **descartava as cópias antes de saber se as escolhidas eram coletáveis** — e as duas melhores por tier são justamente as mais prováveis de estar atrás de Cloudflare | as cópias viram **reserva**: não são coletadas, mas acordam se as escolhidas voltarem vazias |
| 9 | A impressão digital do cache de `scrape` não cobria `TITLE_THRESHOLD` nem `STALE_MARGIN_DAYS`; a de `dedup` não cobria `fontes.json` | `main.py` entrou em todas as listas, mais os arquivos que cada etapa de fato lê |
| 10 | Ordenação por data comparava **texto ISO**: 21/09 23:00 BRT aparecia depois de 22/09 01:00 UTC, que é o mesmo momento | ordena por instante |
| 11 | O docstring de `extract_published_date` publicava os **90,6%** que este documento manda não usar | trocado pelos 81% medidos no pipeline |

**Uma ressalva de um refutador que vale registrar.** O auditor do achado 1 disse
que era "o mesmo corte que derrubou 6 matérias legítimas". O refutador conferiu e
mostrou que não: aquelas 6 passaram pelo RSS na execução real e foram medidas no
filtro de data de página, na investigação do dia seguinte. O defeito é real e foi
reproduzido; a história causal estava errada. Achado confirmado, narrativa
corrigida — que é exatamente o que a camada de refutação existe para fazer.

## Execução real de 22 set 2026, e um erro meu que quase virou decisão

Primeira execução completa da versão 2. 13 minutos, cerca de US$ 0,20.

```
244 brutos → 203 únicos → 201 após o portão de tier → 76 relevantes
62 coletadas (14 em reserva, nenhuma precisou acordar) → 56 com corpo
56 resumos, nenhuma falha → 35 após dedup (21 duplicatas)
3 caixas de empresa · 0 caixas de métrica · 29 empresas novas em quarentena
```

### O erro: acusei o modelo de inventar número, e era o meu leitor

Reportei que 6 dos 56 resumos (11%) citavam capacidade inexistente, que isso era
sistemático, e que a causa era a linha 10 do `summarization_prompt.txt` ("sempre
incluir valores e unidades técnicas"). **Estava errado nos três pontos.**

O `numeros.py` só conhecia as abreviaturas `MW`, `GW`, `kW`. A imprensa escreve
por extenso o tempo todo, e era o que essas matérias faziam: "1 gigawatt de carga
de TI", "400 megawatts (MW)", "210 quilowatts", "20 gigawatts até 2032", "15 a 18
gigawatts". Todos os seis números estavam na matéria.

Agravante: eu disse ter confirmado na página bruta. Confirmei mal — procurei só
`GW` e `MW` no HTML, achei zero e concluí invenção. E afirmei que a matéria de
Campinas dizia "386 MW, não 400"; ela diz os dois.

Com o leitor consertado, medindo os mesmos resumos: **zero invenções em 56.**

### O que sobrevive: o caso da CNN é real

Refeito com o leitor certo, o corpo da coluna da CNN de 17/09 tem zero ocorrências
de `gigawatt`, `bilh`, `milh`, `GW`, `MW` e `%`, e o leitor não acha número nenhum
nele. Os "R$ 30 bilhões", "170 GW" e "200 GW" do resumo publicado continuam não
existindo.

Taxa real: **1 caso em ~109 matérias**, não 11%. O bloco 🚨 tem valor — e só tem
valor agora que lê direito. Um verificador que grita seis falsos alarmes por
edição é ignorado na terceira semana, e aí o caso verdadeiro passa junto com eles.

### O prompt de resumo NÃO foi trocado, e a decisão é medida

Quatro agentes escreveram candidatos por ângulos diferentes; escrevi um quinto.
Medidos nas mesmas 56 matérias, três repetições dos dois finalistas:

| prompt | números legítimos citados | amplitude |
|---|---|---|
| **atual** | 140, 140, 140 — média **140** | **0** |
| candidato "copiar" | 147, 129, 110 — média 129 | 37 |

O atual é melhor na média **e** é perfeitamente estável a temperatura 0. O
candidato varia 37 números entre execuções idênticas, o que num entregável semanal
é pior do que ser um pouco mais pobre. Nenhum dos dois inventa nada.

Uma medição intermediária deu 121 para o atual e quase me fez trocar: aquela
execução teve 7 resumos vazios por limite de taxa, e os 7 artigos não contribuíram
número. Artefato do arranjo de medição, não do prompt.

### Outros defeitos que só a execução real mostrou

- **Fontes oficiais em tier 3.** O Senado ficou atrás do G1 e do UOL numa disputa
  de duplicata. A proposta 1 listou os órgãos por domínio (`senado.leg.br`) e o
  Google Notícias os reporta por nome ("Senado"). 16 nomes acrescentados ao tier 1.
- **Duas execuções simultâneas.** Uma pelo Cursor e uma pelo assistente, 110
  segundos de diferença, compartilhando `output/` e o cache sem nenhuma proteção.
  O relatório de edição manual anunciou "3 removidas, 4 incluídas, 20 com resumo
  corrigido" numa edição em que ninguém tocou. Agora há trava por pid, e o diff
  compara com o cru da mesma execução.
- **Relatório de janela ilegível.** O Google Notícias devolve ~100 resultados por
  consulta independentemente da data, então o relatório saía com 75 linhas de
  comportamento esperado. Agora: contagem sempre, exemplos só a até 3 dias da borda.

### A dedup estava removendo notícia de verdade, e a Q11 fica respondida

Defeito que só a execução real mostrou. Com `gpt-4o-mini`, a confirmação de
duplicatas agrupou num único grupo de 8: a regra ambiental do Rio Grande do Norte,
**as sete leis da Califórnia**, um senador defendendo gás natural, a conexão de
data centers às distribuidoras e a autorização da Aneel para a Ascenty. Em outro
grupo, TD SYNNEX com três matérias da Ascenty. O modelo agrupa por ASSUNTO, não
por FATO.

Medido nas mesmas 56 matérias, uma chamada por configuração:

| configuração | removidas | erros visíveis |
|---|---|---|
| gpt-4o-mini, prompt original | 23 | Califórnia + RN + gás natural juntos; TD SYNNEX com Ascenty |
| gpt-4o-mini, prompt reparado | 19 | funde Casa dos Ventos com Alibaba |
| **gpt-4o, prompt reparado** | **15** | **nenhum** |

O mini removia **8 notícias que não eram duplicatas, por edição**. Na edição
refeita, 33 → 40 matérias.

Duas mudanças, as duas necessárias: a regra de "mesmo ato, mesmo ator, mesmo
lugar, mesma data" entrou no `CONFIRM_PROMPT`, e a etapa `dedup` passou a
`gpt-4o` em `configs/modelos.json`. O prompt sozinho não resolvia — introduzia
erros novos.

Isto responde a Q11, que deixou o ID do nível "médio" para ser escolhido por
teste. A resposta é específica da etapa: **só a confirmação de duplicatas precisa
do modelo melhor**, porque é uma chamada por edição que decide sobre todas as
matérias de uma vez. Resumo, ficha e reclassificação são por matéria, custariam
vinte vezes mais, e nelas o mini foi medido e não erra.

### Limitação conhecida do leitor de números

"3 a 4 gigawatts" é lido como 4 GW; o limite inferior de um intervalo não é
capturado. Se um resumo citar o "3", ele será acusado sem razão. Não consertei
porque o caso não apareceu e a correção mexe no ponto mais delicado do módulo.

## Testes

Os três arquivos em `tests/` chamavam `classify_items` e `summarize_items`,
funções que **nunca existiram neste repositório**, e importavam
`utils.get_search_results` por um caminho que não resolve. Os três falhavam no
import desde o primeiro commit: a bateria estava verde por ausência.

No lugar, 56 testes das regras que decidem o que o investidor lê. Sem rede, sem
API, sem pytest, em 0,3 segundo:

```
python -m unittest discover -s tests
```

## Quarentena de empresas, triada em 22 set 2026

A primeira execução devolveu 35 nomes novos. Triados com o Pedro:

- **16 foram para `nao_empresas`** — entidades de classe (ABDC, ABES, Assespro,
  Associação Brasil Digital, Brasscom, CNI, Conexis, Data Center Coalition,
  Fecomercio SP, Firjan, TelComp, Movimento Brasil Competitivo), a UNCTAD e o
  Idema, o órgão ambiental do RN, que aparecia com o nome curto e o longo.
- **9 foram para `conhecidas`** — Morgan Stanley, Moody's, SoftBank, LG
  Electronics, TotalEnergies, Serpro, Dataprev, Aligned Data Centers (que já
  estava no arquivo como controladora da ODATA) e Voltalia. Não geram caixa;
  entram só para serem reconhecidas.
- **10 seguem em quarentena**, à espera de pesquisa: Terranova (Campinas),
  Omnia WN Holding (Caucaia/TikTok), CleanSpark, Munters, Moore Threads, BRQ,
  Anviran, PSR, Thymos e NEO. Decisão do Pedro: **não pesquisar agora**. Empresa
  que aparecer em duas ou três edições seguidas justifica a pesquisa; a que
  aparecer uma vez, não.

A lista semanal caiu de 35 para 10.

Dois detalhes que entraram no código junto:
- `Moody's` tem apóstrofe reta e curva como apelidos. O extrator devolve a curva,
  que não é a mesma letra, e sem isso a empresa nunca seria reconhecida.
- Nome curto que começa um nome longo conta uma vez só no relatório. "Omnia" e
  "Omnia WN Holding" são a mesma empresa, e a lista é lida por gente.

Duas ressalvas registradas na hora da triagem: **Voltalia** foi classificada por
conhecimento, sem conferência em fonte; e **Serpro e Dataprev** são estatais que
operam data center de verdade — tratá-las como "conhecidas do leitor" é juízo
editorial, não fato.

## Pendências fora do código

- Tornar o repo `github.com/Orimadros/datacenter-news-clipper` privado. Hoje é
  público e `configs/classification_prompt.txt` + `configs/queries.json` expõem
  o critério de triagem e a lista de concorrentes monitorados.
- Pedir ao colega os PDFs das edições já enviadas (verdade de campo com
  julgamento humano dentro).
