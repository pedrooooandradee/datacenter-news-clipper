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
| Q7 | Trabalho fora do iCloud (`~/dev/`); repo **público** (revisto em 23 set) |
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

## O docling saiu (23 set 2026)

Nenhum código do pipeline importava docling desde 22 set 2026 — só
`tests/test_scraper.ipynb`, e o caderno não rodava nem com ele: importava também
`requests`, `bs4` e `langchain.prompts`, nenhum declarado. O docling saiu do
`requirements.txt` e o caderno foi apagado, com a autonomia que o Pedro deu para
cortar o que fosse comprovadamente inútil. Numa instalação nova, deixam de vir
torch (583 MB), torchvision, transformers e accelerate.

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
conda create -p ~/.clipping247-python -c conda-forge python=3.12 pango cairo
~/.clipping247-python/bin/python3 -m venv venv
```

**Resolvido em 23 set 2026.** Por dois meses os quatro documentos deram só a
segunda linha, com o caminho absoluto — uma receita que só funcionava nesta
máquina e que, em qualquer outra, devolve "arquivo não encontrado". O
`README.md` (Step 3), o `LEIA-ME.md` e o `COMANDOS.txt` agora dão os dois
caminhos, Homebrew e conda, com o aviso de não misturar.

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

## A edição de 28 set 2026: a primeira conferida item a item

Rodada pelo Pedro no Cursor, sem nenhuma intervenção. O programa funcionou: v2,
66 testes verdes, trava liberada, nenhuma falha de resumo ou de classificação,
cabeçalho com a semana certa. Das **36 notícias, 11 não deveriam estar lá** e dois
resumos diziam o que a matéria não diz. Nenhum desses erros era visível para quem
só lesse o terminal. A conferência abriu cada caso contra o texto da matéria,
guardado no cache do resumo.

### O que foi achado

| Defeito | Casos | Causa |
|---|---|---|
| Repetida da edição anterior | 5 (3 com a mesma URL) | A janela de 7 dias sobrepõe as edições num dia; nada comparava com a anterior |
| Duplicata dentro da edição | 4 grupos: Google Cloud (2), Cushman (3, em três seções), DayOne (2), artigo NIMBY (2, texto idêntico) | A segunda etapa, com gpt-4o sobre os resumos, **não juntou casos óbvios** |
| Resumo com a fonte errada | 2 (o artigo NIMBY nos dois veículos) | Atribuiu ao Fórum Econômico Mundial uma estimativa que o artigo credita à Agência Internacional de Energia |
| Resumo que distorce o número | 1 (Monitor Mercantil) | "R$ 25 bi por projeto" onde a matéria diz "R$ 25 bi por data center de 100 MW, segundo a FGV". A ficha marcou como hipotético; o parágrafo não |
| "Também noticiado por" com veículos que não noticiaram | 5 nomes sob o Google Cloud | Agrupamento por título transitivo juntou Google e Alibaba |
| Alarme 🚨 falso | 2 de 3 | "um quilowatt" e "um décimo": o conferidor só lia algarismos |
| Notícia relevante perdida | BID Invest avalia US$ 300 mi para a Scala (BNamericas, tier 1) | Paywall. Correto não resumir; não há como incluir à mão |

### O que foi corrigido na edição

Em `configs/overrides.json`, com o motivo de cada um: 7 removidas, 3 grupos fundidos,
1 resumo reescrito (cada número conferido contra a matéria pelo mesmo conferidor do
pipeline, zero sem lastro). A edição saiu com 25 notícias.

**Uma exceção à regra de não editar `output/clippings.json` à mão**, autorizada pelo
Pedro: a lista "também noticiado por" do Google Cloud. Nenhum bloco de
`overrides.json` apaga nomes dessa lista — o `dedup` só acrescenta. Foram retirados
ADVFN, Demócrata, FinanceFeeds, cisoadvisor e tradingkey, conferidos veículo a
veículo contra o título que cada um publicou: os cinco escreveram só sobre a
Alibaba. A mudança está marcada no próprio item, no campo
`tambem_noticiado_por_corrigido_a_mao`. A saída intacta do programa está em
`output/archive/2026-09-28/clippings.raw.json`. A edição é de uma semana só:
nenhuma execução futura depende disso.

### O que mudou no código, para a semana seguinte

1. **Não repetir a edição anterior.** Depois da coleta, antes de pagar o resumo, sai
   toda notícia cuja URL já estava na última edição que virou PDF (`clippings.final.json`
   no arquivo, com pelo menos 3 dias de distância — para que um reprocessamento não
   compare a edição consigo mesma). Na edição de 28/09 teria tirado exatamente as 3
   repetidas pela URL. As 2 repetidas por fato, em outro veículo, continuam com o revisor.
2. **Agrupamento por título sem encadeamento.** União transitiva trocada por ligação
   média, escolhida por medição nos 91 títulos da semana: a união juntava 40 títulos
   de duas notícias; a ligação completa separava, mas partia o Google em 4 grupos; a
   média separa e parte o Google em 3. E os nomes das cópias dispensadas antes da
   coleta passam a ir para uma matéria por grupo, não para todas as que ficaram — era
   por isso que DCD e TeleSíntese imprimiam a mesma lista de 39 veículos.
3. **Números por extenso.** "um quilowatt", "mil megawatts", "um décimo do", "um quarto
   do", "metade dos". Só antes de unidade ou como fração de alguma coisa: "um data
   center", "um quarto de hotel" e "há dois anos" continuam sem número. Um número
   inventado continua sendo pego.

Dez testes novos, um por caso.

### O problema que ficou aberto

**A segunda etapa da deduplicação está falhando em casos óbvios.** Os dois artigos
NIMBY são o mesmo texto, palavra por palavra, e passaram. DCD e TeleSíntese relatam o
mesmo anúncio, no mesmo evento, com os mesmos números, e passaram. Ela é a rede de
segurança de todo o desenho em dois estágios — a razão de o agrupamento por título
poder errar para o lado de separar. Com a correção 2, o Google chega à segunda etapa
em três grupos em vez de dois. Se ela continuar deixando passar, a próxima edição
pode ter mais duplicatas, não menos.

Não foi mexida agora porque não era o combinado. É a primeira coisa a medir na
próxima edição: quantos grupos de título chegam, quantos ela junta, e ler o
porquê dos que ela não junta.

## Passagem de bastão (28 set 2026)

O Pedro sai da Elementum3 em janeiro de 2027. Uma auditoria com cinco olhares
independentes — contas e donos, o primeiro dia de um estagiário novo, o que
envelhece sozinho, a operação semanal e as decisões órfãs — levantou 48 achados;
um revisor fundiu os repetidos, derrubou 13 e confirmou 16. Três impediam a edição
de sair: ninguém definido para rodar, revisar e enviar; a chave da OpenAI sem dono
claro; e a instalação nunca testada fora do Mac do Pedro.

### O que foi apurado sobre a chave

Conferido com o próprio cliente da OpenAI, sem expor o valor: é uma chave de
projeto (`sk-proj-`) da **organização `elementum3`**, que funciona. Quem paga já é
a empresa. Ela chegou pelo Leo (o README da v1 dizia "Ask Leo for the API key") e
a mesma chave está na cópia antiga do iCloud. Chave de projeto comum fica ligada a
quem a criou; o conserto é uma chave de **conta de serviço**, criada por quem
administra a organização — pedido ao Edson.

### Três erros meus, corrigidos

- O LEIA-ME ainda mandava pedir autorização "do Gabriel ou do Leo" num segundo
  lugar, que escapou da correção de 23 set.
- O conserto para Mac com Homebrew recomendado em 23 set (`PKG_CONFIG_PATH` no
  `.env`) não tinha efeito: o WeasyPrint carrega pango e cairo pelo `dlopen` do cffi,
  que não lê essa variável. O conselho e o código que a copiava saíram.
- O filtro de repetidas feito nesta mesma data desligava **em silêncio** quando não
  achava a edição anterior. Agora avisa.

### O que mudou

- **Instalação: um caminho só, o testado.** Um Mac novo tem Python 3.9, e as
  bibliotecas exigem 3.10 ou mais — o caminho Homebrew quebrava no primeiro `pip`.
  Ficou o conda, com o comando exato que criou o ambiente em uso (tirado do
  histórico do próprio ambiente: faltavam `gdk-pixbuf`, `libffi` e
  `--override-channels` na receita de 23 set). Testado do zero: ambiente novo,
  `venv` novo, instalação, testes, PDF, checagem da OpenAI e coleta real.
- **Versões travadas** em `requirements.lock.txt` (78 pacotes), tiradas do ambiente
  limpo instalado com as versões que produziram as edições reais. O
  `requirements.txt` com `>=` puxaria em 2027 combinações que ninguém testou.
- **A armadilha do chip, achada no teste do zero.** A primeira instalação limpa
  seguindo a receita passou em tudo — testes, PDF, checagem da OpenAI — e a coleta
  travou em toda página pesada: 30 segundos de espera no Valor e no G1, que o
  ambiente antigo abria em 1 segundo. Pacotes Python idênticos, variáveis de
  ambiente idênticas, mesmo Chrome e mesmo driver. Foram cinco testes eliminando
  hipóteses: não era a ordem de acesso (o site não estava freando), nem a versão do
  Python, nem a pasta, nem o firewall, nem os pacotes a mais do ambiente antigo.
  Era a arquitetura: este Mac é Apple M1, o Anaconda instalado é o de Intel, e ele
  cria ambientes de Intel por padrão. O ambiente que funciona tinha sido criado
  forçando o chip Apple, e a receita não dizia isso. O Python de Intel roda
  traduzido pelo Rosetta, e o Chrome disparado por ele trava nas páginas pesadas.
  A receita agora começa com `CONDA_SUBDIR=osx-arm64`, conferida como está escrita
  (o ensaio do conda responde `Platform: osx-arm64`), e o README ensina a checar
  com `platform.machine()`. Refeita assim, a instalação limpa coletou as 8 páginas
  de teste idênticas à referência.
- **Chrome:** o driver passa a ser resolvido pelo próprio Selenium (o pacote
  `webdriver-manager` saiu) e o navegador se apresenta com a versão real, não com
  uma "Chrome 114" fixa. Coleta de 8 páginas: resultado idêntico, caractere por
  caractere. A versão vai como opção de abertura do Chrome, não por CDP depois de
  aberto: o CDP apagava os client hints (`sec-ch-ua`), o que é outra identidade que
  nenhum Chrome de verdade tem (ver a revisão, abaixo).
- **Antes de gastar, o programa confere a chave e os modelos** — consulta de
  metadados, sem custo. Modelo aposentado, chave revogada, chave sem permissão ou
  OpenAI instável param a execução em segundos, cada um com a sua causa. Conta sem
  crédito essa consulta não vê; ela para a execução na primeira chamada paga, a
  triagem, com o comando para retomar.
- **A janela da edição** é de 7 dias, estendida até a última edição quando a
  execução atrasa até três dias. O dia de início fica registrado e o cabeçalho do
  PDF passa a mostrá-lo. Busca, filtro de datas e cabeçalho usam a mesma janela e
  o mesmo calendário (o do computador; a busca contava em UTC e perdia o primeiro
  dia depois das 21h).
- **Tudo o que a execução imprime fica em `output/logs/`**, e o bloco 🚨 reaparece a
  cada montagem do PDF. A revisão depende desses avisos, que viviam só numa janela
  de terminal.
- O aviso de correção do `overrides.json` que não bateu separa **as desta semana**
  (em destaque — quase sempre URL digitada errado) das antigas (só contadas).
- Clone sem nenhuma edição: refazer o PDF explica o que fazer, em vez de estourar.
- **LEIA-ME:** revisão item a item (o que a conferência de 28/09 precisou achar),
  "Quando quebrar" e o esqueleto da "Operação semanal", com os nomes em branco até
  o Edson responder.

### A revisão antes de publicar

Antes do commit, o conjunto passou por uma revisão independente com três lentes
(código, documentos, regressão), cada achado reproduzido por um segundo revisor
cético. Confirmou 20. Os que mudaram decisão:

- **A janela esticada até a edição anterior (até 21 dias) foi desfeita.** Era o
  único achado grave. O `output/archive/` fica num computador só e fora do git.
  Num computador cujo arquivo parou em 14/09, enquanto 21/09 e 28/09 saíram de
  outro, a janela ia a 21 dias e o filtro de repetidas comparava com 14/09: as duas
  edições já enviadas voltavam inteiras, sob um cabeçalho de três semanas. E nem o
  benefício existia: o Google Notícias devolve no máximo 100 resultados por
  busca, e as duas buscas principais enchem 81 e 80 deles em 7 dias. Semana pulada
  não é recuperada, e agora o programa e o LEIA-ME dizem isso, em vez de prometer
  o contrário. Arquivo antigo neste computador gera ⚠️ no começo da execução.
- **`overrides.json` com erro de sintaxe para o PDF.** Antes, o arquivo era
  ignorado com um aviso e saía um PDF sem nenhuma correção, com "PDF gerado" no
  fim e o arquivo da edição sobrescrito.
- **As datas das correções são comparadas como datas.** Como texto, "05/10/2026"
  ficava antes de "2026-10-05", e a correção da semana com URL errada era
  escondida como antiga.
- **O registro em `output/logs/` guarda o erro.** O traceback era impresso depois
  de o arquivo fechar: o registro que ia para quem fosse consertar terminava uma
  linha antes do problema. Agora é gravado linha a linha, e sobrevive a fechar a
  aba do terminal.
- **Permissão não é modelo aposentado.** Um 403 mandava trocar o modelo em
  `configs/modelos.json`, o que muda quem escreve os resumos e não resolve nada. O
  modelo de embedding, sem o qual o programa já sabia seguir, só gera aviso.
- **Data só com o dia** ("2026-09-28") era lida como meia-noite em UTC, 21h da
  véspera em Brasília, e o PDF mostrava 27 Set. Passou a ser meio-dia UTC.
- Os documentos: o COMANDOS.txt tinha explicação na mesma linha do comando
  (colada inteira, a linha falhava); o README citava uma mensagem que o programa
  não imprime e dizia que nada fora pago quando a triagem já tinha rodado; o
  `.env.example` defendia uma chave por pessoa logo abaixo de recomendar uma
  chave de conta de serviço.

### O que continua dependendo de alguém

As oito definições pedidas ao Edson estão no topo do `TODO.md`. Sem elas o código
roda, mas ninguém sabe quem o roda, quem revisa e para quem vai.

## O nome do Drive, a quinzenal, a busca com datas e os outros computadores (28 set 2026)

Pedido do Pedro, com dez PDFs baixados da pasta "Clippings Semanais" do Drive como
referência: que o PDF saia com o mesmo título e formatação, e que o programa rode
em qualquer computador, não só no Mac.

**A formatação já era a mesma.** Os PDFs do Drive saem do mesmo modelo, pelo
WeasyPrint (o 67 até o começo do ano, o 70 no de 21/09): mesma logo, mesmo índice,
mesmas páginas. O que mudava era o nome do arquivo, que alguém digitava à mão. O
programa agora o escreve sozinho (`nome_do_pdf`, em `services/utils/archive.py`).

A regra do nome foi lida nos próprios arquivos, e a revisão independente corrigiu
a minha primeira leitura. A primeira data não é o início da busca: é o dia da
**edição anterior**. A de 14/09 se chama `(08_09 - 14_09 …)`, por causa da edição
de terça, 08/09, embora o cabeçalho dela diga "Week 07 Sep". E o tipo, Semanal ou
Quinzenal, é uma decisão de quem roda, não uma conta de dias. Os testes
reproduzem, letra por letra, cinco nomes reais e a sequência de 24/08 a 21/09
passando pelas mesmas funções que o `main.py` usa. Entre eles está
`2026.01.05 Clipping Atualização Quinzenal (22_12_2025 - 05_01_2026 às 13h13).pdf`.

**A quinzenal volta, pedida pelo nome.** Os nomes do Drive mostram que a empresa
fez edições de 14 dias de propósito, nas festas e no Carnaval. Na revisão desta
mesma data eu tinha tirado a janela que se esticava sozinha, e a razão continua
valendo: esticar por causa de um buraco no arquivo local trazia de volta edições
já enviadas. A quinzenal agora é uma decisão: `python main.py --quinzenal`. A
janela, o dia da edição anterior e o tipo viajam com o cache, para um `--from`
não trocar Semanal por Quinzenal (a revisão pegou a troca num `--from` uma semana
depois).

**Busca com datas.** O teste da quinzenal mostrou uma falha que valia para toda
edição. A busca pedia ao Google a consulta sem datas, recebia cerca de 100
resultados misturando semanas e ficava com o que era da semana. Pedindo as datas
(`after:`/`before:`), uma semana de cada vez, as 15 consultas reais trouxeram 457
notícias candidatas contra 230 — "aws" 13 → 58, "oracle cloud" 1 → 34, "scala data
centers" 4 → 15, "elea data centers" 1 → 9. Justamente concorrentes e clientes. A
semanal continua fazendo um pedido por consulta. O preço é uma edição maior e mais
cara, ainda não medida (TODO). Não é tudo: duas consultas batem no teto de 100
mesmo numa semana, e o programa avisa. Mesmo abaixo do teto, um intervalo menor
traz mais ("aws" em três dias trouxe 17 notícias que a semana inteira não
trouxe, a maioria fora do tema). Se isso compensa, as primeiras edições dirão
(TODO). Uma busca que falha é repetida uma vez; se falhar de novo, o programa
diz que falhou, em vez de cair numa busca pior sem avisar.

**A fonte deixou de vir da internet.** O modelo baixava a Montserrat do Google
Fonts a cada PDF. Sem internet, ou num firewall que bloqueia o Google, o PDF saía
em Helvetica ou Arial sem aviso nenhum. Os quatro arquivos que o Google entregava
ao WeasyPrint estão agora em `configs/fontes/` (licença SIL OFL, que permite
distribuir). O PDF da edição de 28/09 refeito com eles saiu idêntico ao anterior,
pixel por pixel, nas 15 páginas.

**Outros computadores.** O que prendia o programa ao Mac:

- **A trava de execução chamava `os.kill(pid, 0)`**, que no Mac e no Linux só
  pergunta se o processo existe. No Windows, o sinal 0 é Ctrl+C e qualquer outro
  número encerra o processo. O Windows agora pergunta ao sistema pelo processo.
- **O fuso de Brasília** vem do sistema no Mac e no Linux. O Windows não tem esse
  banco: entrou o pacote `tzdata`.
- **As bibliotecas do PDF** (pango, cairo, harfbuzz) não vêm do `pip`. Cada sistema
  tem uma receita no README: conda no Mac, MSYS2 no Windows, `apt` no Linux. O
  WeasyPrint deixou de ser importado na abertura do programa. Sem as bibliotecas,
  o programa diz o comando do sistema e para antes de gastar, em vez de quebrar em
  `import main` com um erro de `.dll`.
- **O terminal do Cursor** abria com o venv ativo só no Mac. Agora abre assim nos
  três. No Windows, o PowerShell do projeto contorna só para si a política de
  scripts, sem mudar nada na máquina.
- **Acentos e símbolos no Windows**, com a saída redirecionada, quebravam no
  primeiro ⛔ (página de código cp1252). A saída passou a ser UTF-8.

`python conferir_instalacao.py` confere tudo isso em qualquer computador, sem
gastar: o Python (e o Python de Intel num Mac de chip Apple), as bibliotecas, o
fuso, um PDF de teste com a fonte embutida, o Chrome abrindo uma página local, o
Google Notícias, a chave (pela consulta gratuita) e os testes. Neste Mac ele
passou com Python 3.12 e com 3.10 (o do Ubuntu 22.04). Para os sistemas que não
há aqui, o workflow do GitHub (`.github/workflows/instalacao.yml`) instala o
projeto do zero, pela receita do README, em Windows, Ubuntu 22.04 e 24.04 e Mac,
e roda o mesmo script. O cabeçalho dele diz o que não cobre.

A mesma revisão independente pegou ainda: os testes quebrando no Windows quando a
saída vai para um arquivo (os símbolos ⛔ e ✏️ não existem na página de código
do Windows); o pacote `libharfbuzz-subset0`, que não existe no Ubuntu 22.04 e,
pedido junto com os outros, fazia o `apt` desistir de todos; datas de página com
fuso escrito "-0300", que o Python 3.10 não lê; e o PDF aberto no Acrobat, que no
Windows impede a regravação e terminava num erro cru.

## Testes

Os três arquivos em `tests/` chamavam `classify_items` e `summarize_items`,
funções que **nunca existiram neste repositório**, e importavam
`utils.get_search_results` por um caminho que não resolve. Os três falhavam no
import desde o primeiro commit: a bateria estava verde por ausência.

No lugar, testes das regras que decidem o que o investidor lê (66 quando foram
escritos; o próprio comando diz quantos são hoje). Sem rede, sem API, sem pytest,
em menos de um segundo:

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

- ~~Tornar o repo privado.~~ **Revisto em 23 set 2026: fica público**, por
  decisão do Pedro. O argumento dele: não há informação confidencial no
  scraping, e o próximo estagiário tem de conseguir baixar e rodar o pacote sem
  pedir acesso a ninguém. A objeção original era o `queries.json` e o
  `classification_prompt.txt` exporem o critério de triagem — medida depois, ela
  não se sustenta: as 15 consultas são nomes óbvios de mercado (`ascenty`,
  `equinix`, `odata`, `scala data centers`, os hyperscalers). O que era mesmo do
  cliente eram 4 linhas em 2 arquivos, já generalizadas.

  O que fica fora do repositório, de propósito: o `.env` com a chave da OpenAI
  e o `output/archive/` (texto integral de matérias de terceiros e as edições
  corrigidas à mão).

  **A logo entrou em 28 set 2026**, por decisão do Pedro, depois de avisado de
  que commit em repositório público é permanente: a marca registrada do cliente
  fica publicada no histórico, e tornar o repositório privado depois não a
  remove. O argumento dele é o mesmo do repositório público: quem assumir tem de
  clonar e gerar a edição completa sem pedir arquivo a ninguém. O arquivo foi
  conferido antes: JPEG 1237×529 sem metadado de autor, copyright ou localização.

- **Onde o código mora.** O repositório original, `github.com/Orimadros/datacenter-news-clipper`,
  é da conta pessoal do Leo — não do Pedro, como este documento chegou a afirmar em
  23 set. O push da v2 foi recusado ali em 28 set 2026 (`403`, sem permissão). A v2
  foi publicada num repositório novo, na conta do Pedro: `https://github.com/pedrooooandradee/datacenter-news-clipper`, com a v2 como
  `main` e o histórico da v1 preservado por baixo.
- Transferir esse repositório para uma conta da Elementum3 ou do conselho da 247
  antes de janeiro de 2027. Ele é da conta pessoal do Pedro; depois que o acesso
  dele acaba, ninguém mais transfere. O da `Orimadros` continua público com a v1 de
  julho de 2025, e só o dono pode arquivá-lo.
- Pedir ao colega os PDFs das edições já enviadas (verdade de campo com
  julgamento humano dentro).
