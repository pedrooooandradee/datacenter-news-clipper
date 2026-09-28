# Clipping de Data Centers (cliente 247) — guia rápido

## O que o programa faz

Procura no Google Notícias as notícias da última semana sobre data centers, usa
inteligência artificial (OpenAI) para descartar o que não interessa, resumir o
resto em português e extrair os números de cada matéria, e monta um **PDF de
clipping** com a logo da 247.

---

## Antes de rodar pela primeira vez

### A instalação

Está no **`README.md`**, passo a passo: uns 20 minutos, uma vez por computador,
em **Mac, Windows ou Linux**. Em resumo: instalar o Git, o Google Chrome e o
Python; instalar as bibliotecas de sistema que desenham o PDF (o único passo que
muda de um sistema para outro); montar o `venv`; e instalar as bibliotecas pelo
arquivo de versões travadas:

```bash
pip install -r requirements.lock.txt
```

No fim, confira o computador inteiro, de graça:

```bash
python conferir_instalacao.py
```

Ele testa o Python, as bibliotecas, um PDF de teste com a fonte certa, o Chrome
abrindo uma página, o Google Notícias, a chave da OpenAI (pela consulta gratuita)
e os testes. Tudo tem de dar ✅; cada ⛔ diz o que fazer. Rode de novo sempre que
algo quebrar sem motivo aparente.

A armadilha que mais custou tempo, e que ele pega: em Mac com chip Apple, o
ambiente conda tem de ser criado **para chip Apple** (o comando do README começa
com `CONDA_SUBDIR=osx-arm64`). Um Anaconda de Intel cria ambientes de Intel, e aí
tudo instala, os testes passam, e a coleta trava em quase toda página de notícia.

### A logo da 247

Vem no repositório, em `configs/247.original.jpg`. Quem clona já gera a edição
com a logo no cabeçalho; não precisa pedir nada a ninguém.

Se o arquivo sumir, o PDF sai sem a imagem e o programa avisa no terminal. Para
recuperar:

```bash
git checkout configs/247.original.jpg
```

> O WeasyPrint, sozinho, não avisaria: ele simplesmente não desenha a imagem e
> devolve um PDF válido, sem uma palavra. O aviso é impresso pelo próprio
> programa, justamente para uma edição de cabeçalho vazio não chegar ao cliente.

### O Google Chrome

A etapa de coleta abre as páginas num Chrome invisível (Selenium). **Instale o
Chrome antes** — o `pip` não instala navegador. A peça que conversa com o Chrome o
próprio Selenium baixa, na primeira vez. Sem Chrome instalado, a coleta depende de
o Selenium conseguir baixar um navegador sozinho, o que não foi testado: não conte
com isso.

### O arquivo `.env`

Guarda a chave da OpenAI, ligada a um cartão de crédito. É **confidencial**: não
abra para mostrar a ninguém, não envie e não apague.

O arquivo não vem no repositório — ele nunca entra no git. O que vem é o molde:

```bash
cp .env.example .env
```

A chave vem da conta da OpenAI **da empresa** — a organização `elementum3` em
platform.openai.com. Quem administra essa organização cria a chave; o ideal é uma
**chave de conta de serviço** do projeto do clipping, que não pertence a nenhuma
pessoa e não para de funcionar quando alguém sai. Nunca use chave pessoal.

Se uma chave sua já apareceu em algum lugar que não devia — num print, num
arquivo dentro do iCloud, numa mensagem — revogue e crie outra. Revogar é um
clique e não quebra nada além do `.env` de quem a usava.

---

## Os comandos

Sempre com `(venv)` no início da linha do terminal (o terminal do Cursor já abre
assim). Se não estiver: `source venv/bin/activate` no Mac e no Linux,
`venv\Scripts\Activate.ps1` no Windows. Os comandos são os mesmos nos três.

### 1. Rodar o clipping completo

```bash
python main.py
```

⚠️ **Só com autorização do dono do clipping** (ver "Operação semanal"). Gasta
dinheiro de API (US$ 0,20 na edição de 22/09, com 56 matérias) e leva de 10 a 30
minutos. Sem nenhuma opção, roda tudo do zero — é sempre uma edição nova, nunca
reaproveita busca da semana passada.

> Desde 28/09 a busca pede ao Google as datas da semana e traz o **dobro** de
> notícias candidatas (457 contra 230, medido nas consultas reais), sobretudo de
> concorrentes e clientes. O custo e o tempo de uma edição com ela ainda não foram
> medidos: anote os da primeira.

**O PDF sai com o nome que a pasta do Drive usa**, pronto para subir:

```
output/2026.09.28 Clipping Atualização Semanal (21_09 - 28_09 às 10h19).pdf
```

A data e a hora são as do fechamento da edição; entre parênteses, o primeiro e o
último dia cobertos.

**Edição quinzenal** (festas de fim de ano, Carnaval — já foram feitas assim):

```bash
python main.py --quinzenal
```

Cobre 14 dias, buscando uma semana de cada vez, e o PDF sai como
"Clipping Atualização Quinzenal". Quando a janela cruza a virada do ano, as datas
levam o ano: `(22_12_2025 - 05_01_2026 às 13h13)`.

Antes de gastar qualquer coisa, o programa confere se a chave e os modelos da
OpenAI respondem. Se não, para na hora e diz por quê (ver "Quando quebrar"). O
que essa conferência não enxerga é conta **sem crédito**: aí o programa para na
primeira chamada paga (a triagem, centavos) e mostra o comando para retomar
depois, sem pagar de novo o que já rodou.

**A janela da edição** é de 7 dias. Se rodar até três dias atrasado, ela vai até
a última edição (nove ou dez dias), para os dias de atraso não se perderem. Mais
que isso, só pedindo: **uma semana pulada não é recuperada sozinha** — para cobrir
duas semanas, `--quinzenal`. A primeira linha que o programa imprime diz qual
janela usou; se vier com ⚠️ dizendo que a última edição **neste computador** é
antiga, leia antes de deixar seguir (ver "Quando quebrar").

**Tudo o que aparece no terminal fica salvo** em `output/logs/`. É dali que a
revisão lê os avisos, mesmo depois de fechar a janela.

### 2. Refazer só o PDF

```bash
python services/pdf_builder.py
```

De graça, leva segundos. Lê o `output/clippings.json` que já existe, aplica o
`configs/overrides.json` por cima e desenha o PDF de novo. É o comando para usar
depois de qualquer correção manual.

### 3. Refazer só uma etapa, sem repagar as anteriores

```bash
python main.py --from=dedup
```

Etapas, em ordem: `search` · `classify` · `scrape` · `summarize` · `ficha` ·
`dedup` · `pdf`. `--from=X` reaproveita o que já foi feito até antes de X e refaz
dali em diante.

Serve para experimentar: mudou o prompt do resumo, roda `--from=summarize` e não
paga a coleta de novo. Se o código da etapa mudou desde que o cache foi gerado, o
programa avisa em voz alta.

`--from` **fecha a edição de novo, com a data de hoje**: o cabeçalho do PDF e a
pasta do arquivo passam a ser de hoje, mesmo com as notícias do cache antigo. Para
corrigir uma edição já montada, use o **comando 2**, não o `--from`.

```bash
python main.py --list-cache     # o que está guardado
python main.py --clear-cache    # apaga o cache e SAI, sem rodar nada
```

⚠️ `--from` **reescreve** o `output/clippings.json`. A versão anterior é guardada
em `output/clippings.anterior.json`, mas correção feita à mão só sobrevive de
verdade se estiver no `configs/overrides.json` (abaixo).

### 4. Conferir que o programa continua certo

```bash
python -m unittest discover -s tests
```

De graça, um segundo, sem internet. São os testes das regras que decidem o que o
investidor lê — o comando diz quantos são. Rode depois de mexer em qualquer
configuração. **Se algum falhar, não envie o clipping.**

Para conferir o computador inteiro (Chrome, PDF, chave, internet), e não só as
regras: `python conferir_instalacao.py`.

---

## Revisão da edição, item a item

**Reserve o tempo.** Na edição de 28/09 a revisão levou uns 35 minutos, com IA
ajudando, e 11 das 36 notícias precisaram de correção — **nenhum desses erros
aparecia no terminal**. Sem IA, o tempo ainda não foi medido.

Abra lado a lado:
- o PDF da semana — `output/<data> Clipping Atualização Semanal (…).pdf`;
- o PDF da última edição **enviada** — na pasta "Clippings Semanais" do Drive,
  ou em `output/archive/<data>/`.
  Confira que é mesmo a última que o cliente recebeu; se ela saiu de outro
  computador, a cópia certa está na pasta da empresa;
- o registro da execução — `output/logs/execucao-<data>.log`.

1. **Os avisos do registro.**
   - **🚨 "número que não achei na matéria"** — abra o link e confira o número.
     Pode ser o modelo inventando (aconteceu em 21/09: R$ 30 bilhões, 170 GW e
     200 GW que não existiam na matéria) ou o leitor de números errando uma grafia
     incomum. Esse aviso reaparece toda vez que o PDF é refeito, até o resumo ser
     reescrito.
   - **"descartadas por falha de coleta"** — alguma é importante (veículo tier 1,
     concorrente, valor alto)? Paywall não tem como entrar; anote para o dono.
   - **"já saíram na edição de…"** — repetidas retiradas automaticamente, pela URL.
   - **"Nenhuma edição anterior em output/archive"** — as repetidas **não** foram
     retiradas. Faça o passo 2 com cuidado redobrado.
   - **"⚠️ a última edição NESTE COMPUTADOR é de…"** (logo no começo) — ou uma
     semana foi pulada, ou o arquivo deste computador está atrasado e as
     repetidas foram comparadas com a edição errada. Faça o passo 2 com cuidado
     redobrado.
2. **Repetidas da semana passada.** O mesmo fato — mesma empresa, mesmo número —
   está no PDF anterior, mesmo que por outro veículo? O programa só pega a mesma
   URL. → bloco `removidas`, motivo "mesmo fato publicado em DD/MM".
3. **Duplicatas dentro da edição.** Leia o índice inteiro procurando o mesmo fato
   duas vezes, inclusive em seções diferentes — em 28/09 o mesmo relatório saiu em
   três. → bloco `dedup`, mantendo a versão mais completa.
4. **Cada número de cada resumo.** Abra o link e confira três coisas: **o valor**,
   **quem disse** (a fonte citada no resumo é a mesma da matéria?) e **a que se
   refere** (ao projeto, ao mercado inteiro, ou a um exemplo hipotético?). Em
   28/09, uma estimativa da Agência Internacional de Energia saiu atribuída ao
   Fórum Econômico Mundial, e "R$ 25 bi por data center de 100 MW" saiu como
   "R$ 25 bi por projeto". → bloco `resumo`, reescrito só com o que está na matéria.
5. **Número de veículo pouco conhecido.** A regra de que veículo tier 3 não
   sustenta um número sozinho foi decidida e **não está ligada** no código: número
   de blog sai igual a número do Valor. Confira esses com mais cuidado.
6. **"Também noticiado por."** Os veículos listados cobriram mesmo aquela notícia?
7. **Opinião sem fato novo** — coluna, artigo assinado. → bloco `removidas`.
8. **Empresas novas e fontes novas** — os avisos "empresas novas, ainda sem ficha"
   e "fontes ainda não classificadas" não mudam o PDF desta semana. São a fila de
   curadoria de `configs/empresas.json` e `configs/fontes.json`.
9. Rode `python services/pdf_builder.py`, reabra o PDF e repita até não sobrar nada.

---

## Como corrigir a edição

**Não edite mais o `output/clippings.json` à mão.** Ele é reescrito na próxima
execução. As correções vão em **`configs/overrides.json`**, que é aplicado por
cima toda vez que o PDF é montado.

Abra o arquivo e acrescente na lista do bloco certo. A chave é sempre a **URL da
matéria**, copiada do `output/clippings.json`.

| Quero | Bloco | Exemplo |
|---|---|---|
| Tirar uma notícia | `removidas` | `{"url": "...", "motivo": "opinião sem fato novo", "data": "2026-09-22"}` |
| Mudar a seção | `categoria` | `{"url": "...", "de": "clientes", "para": "governo", "motivo": "...", "data": "2026-09-22"}` |
| Reescrever o resumo | `resumo` | `{"url": "...", "texto": "...", "motivo": "...", "data": "2026-09-22"}` |
| Grifar (fundo amarelo no índice) | `highlight` | `["url1", "url2"]` (só URLs, sem data) |
| Corrigir o nome do veículo | `fonte_nome` | `{"url": "...", "para": "Investing.com", "data": "2026-09-22"}` |
| Juntar duplicatas que passaram | `dedup` | `{"manter": "url-boa", "fundir": ["url-repetida"], "motivo": "...", "data": "2026-09-22"}` |
| Aprovar a ficha de uma empresa | `empresa` | `{"nome": "...", "overview": "...", "aprovado_por": "<dono do clipping>", "data": "2026-09-22"}` |

Depois rode o **comando 2**.

**O campo `motivo` é obrigatório** em `removidas`, `categoria`, `resumo` e
`dedup`. Não é burocracia: daqui a dois meses esses motivos são a única lista real
de onde o programa erra, e viram os exemplos dos prompts. Sem eles sobra uma lista
de URLs sem sentido.

Obrigatório pela regra da casa, não pelo programa: sem `motivo` a correção é
aplicada do mesmo jeito e sai um aviso no fim. O único campo que o código
realmente exige é o `aprovado_por` do bloco `empresa` — sem ele a ficha da
empresa não é registrada, porque ela vira texto publicado no PDF e precisa ter
dono.

Três armadilhas:
- Reescrever o resumo **apaga a caixa de métricas** daquela notícia. A regra é que
  o leitor tem de achar os dois números no parágrafo acima — e o parágrafo mudou.
- **Ponha sempre o campo `data`** (o dia da edição, `AAAA-MM-DD`; `DD/MM/AAAA`
  também vale). Correção desta semana cuja URL não bate com nenhuma notícia
  aparece em destaque — quase sempre é URL copiada errada, e a notícia que ela
  devia corrigir vai para o cliente sem correção. As de semanas anteriores só são
  contadas.
- **Não apague correções antigas.** Uma notícia removida pode voltar na semana
  seguinte pela mesma URL, e é a entrada antiga que a segura.

Se sobrar ou faltar uma vírgula ou uma aspa, o PDF **não** é gerado: o programa
para com `⛔ O PDF NÃO foi gerado` e diz a linha. Corrija e rode o comando 2 de
novo. (Antes, ele montava o PDF sem nenhuma correção e dizia "PDF gerado".)

---

## Onde ficam as coisas

| | |
|---|---|
| PDF da semana | `output/<data> Clipping Atualização Semanal (…).pdf` — o nome do Drive |
| Notícias da semana | `output/clippings.json` |
| Versão anterior, antes da última reescrita | `output/clippings.anterior.json` |
| Edições antigas | `output/archive/AAAA-MM-DD/` |
| O que cada execução imprimiu | `output/logs/` |
| Correções manuais | `configs/overrides.json` |
| Empresas com ficha | `configs/empresas.json` |
| Tiers de veículo | `configs/fontes.json` |
| Qual modelo cada etapa usa | `configs/modelos.json` |
| Por que o programa é assim | `DECISOES.md` |

Cada edição é arquivada em duas versões: `clippings.raw.json`, que é o que o
programa produziu e **nunca** é sobrescrito, e `clippings.final.json` com o PDF
(com o nome do Drive), que é o último PDF montado — o enviado, se ninguém remontou
depois. A diferença entre as duas é o julgamento humano da semana, e é com ela que
dá para medir se uma mudança no programa melhorou alguma coisa.

Na pasta `output/`, os PDFs das edições anteriores saem sozinhos quando a cópia
deles já está no arquivo; na pasta de cada edição no arquivo fica só o último PDF
montado.

---

## As caixas que aparecem sob uma notícia

**Métrica** — um indicador calculado a partir dos números da própria matéria, com
os dois insumos à vista (`R$ 300 mi ÷ 6 MW = R$ 50 mi/MW`). Só sai quando os dois
números são do mesmo projeto, da mesma fase, na mesma moeda, e **os dois aparecem
no resumo acima**. Se não fecha, a caixa não aparece — e o programa diz no fim
quantas notícias tinham número e não pareou.

**Reportado** — um indicador que a própria matéria publica (vacância, PUE,
impacto fiscal). É copiado, nunca calculado.

**Ficha de empresa** — quem é a empresa, para quem não a conhece. Aparece **uma
vez por edição**, na primeira notícia em que a empresa é citada. Empresa que o
leitor já conhece (AWS, Ascenty, V.tal) não ganha caixa.

---

## Importante

- O **comando 1** custa dinheiro e **só roda com autorização do dono do clipping**.
- Nenhum número vai para o PDF sem estar no texto da matéria. Quando o programa
  não consegue confirmar, ele avisa em vez de publicar.

---

## Quando quebrar

**Edição quebrada não é enviada.** Avise o dono do clipping. Se não der para
consertar até o horário de envio, o dono decide se a 247 recebe um aviso de "sem
clipping esta semana". A semana que não saiu **não** volta na seguinte.

Uma edição montada e **não enviada** fica em `output/archive/` como se tivesse
saído, e na semana seguinte o programa retiraria as notícias dela como "já
enviadas". Renomeie a pasta dela, acrescentando `-nao-enviada` ao nome (por
exemplo `2026-10-05-nao-enviada`): com isso o programa deixa de contá-la.

Qualquer linha com ⛔ para o programa antes de fazer estrago. Tudo o que ele
imprimiu está em `output/logs/`; é esse arquivo que vai para quem for consertar.

| O terminal diz | O que é | O que fazer |
|---|---|---|
| `⛔ A OpenAI recusou a chave` | Chave errada ou revogada | Pedir chave nova a quem administra a organização `elementum3` na OpenAI. Nada foi gasto |
| `⛔ O modelo '…' não existe mais` | A OpenAI aposentou um modelo | Trocar o nome em `configs/modelos.json` pelo sucessor que a OpenAI indicar; rodar os testes; comparar a edição nova com a anterior antes de enviar. Nada foi gasto |
| `⛔ A chave não tem permissão para o modelo` | A chave não pode usar (ou consultar) aquele modelo | Pedir a quem administra a organização para liberar. **Não** trocar o modelo. Nada foi gasto |
| `⛔ A OpenAI respondeu com erro …` | Instabilidade do lado da OpenAI | Esperar alguns minutos e rodar de novo. Nada foi gasto |
| `⛔ Sem conexão com a OpenAI` | Internet | Conferir a rede e rodar de novo |
| `⛔ A conta da OpenAI ficou SEM CRÉDITO` | Crédito acabou ou bateu o limite mensal | Pedir crédito a quem administra a organização; depois, o comando `--from=…` que o próprio aviso mostra |
| `⛔ O PDF NÃO foi gerado: configs/overrides.json tem um erro de sintaxe` | Vírgula ou aspa sobrando ou faltando | Corrigir na linha indicada e rodar o comando 2 |
| `⛔ A execução PAROU com o erro acima` | Erro que o programa não previu | Não enviar. Mandar o arquivo de `output/logs/` a quem for consertar |
| `⚠️ a última edição NESTE COMPUTADOR é de…` | Semana pulada, ou edições enviadas de outro computador | Se saíram de outro computador: Ctrl+C, copiar as pastas delas da pasta da empresa para `output/archive/`, rodar de novo. Se foi semana pulada: pode seguir |
| `⛔ Já existe uma execução` | Outra execução rodando, ou uma que morreu no meio | Se ninguém está rodando, veja o comando do processo com o número que aparece — Mac e Linux: `ps -p <número> -o command=`; Windows (PowerShell): `(Get-CimInstance Win32_Process -Filter "ProcessId=<número>").CommandLine`. Se não aparecer `main.py`, apague `output/execucao.lock` |
| `a busca por '…' FALHOU` em todas as consultas | Internet ou Google Notícias fora do ar | Esperar e rodar de novo |
| Quase todas "descartadas por falha de coleta" (com `timeout no carregamento` ou `TimeoutException`) | Em Mac com chip Apple, quase sempre o ambiente instalado para Intel; senão, internet ou Chrome | `python conferir_instalacao.py`: ele diz se o Chrome abre e, num Mac, se o Python é de Intel (aí, refazer o passo 3 do README). Se tudo der ✅, conferir a internet e atualizar o Chrome. A triagem (centavos) já foi paga: rodar de novo com `--from=scrape` |
| `No module named …` | O `venv` não está ativo | Mac e Linux: `source venv/bin/activate`; Windows: `venv\Scripts\Activate.ps1` |
| `⛔ … A parte que desenha o PDF (WeasyPrint) não carregou` | Faltam as bibliotecas de sistema do PDF | A própria mensagem diz o comando do seu sistema (README, passo 3). Nada foi gasto |
| Algo quebrou logo depois de reinstalar | Versão nova de alguma biblioteca | `pip install -r requirements.lock.txt`, antes de mexer em qualquer código |
| Testes falhando | O programa mudou de comportamento | Não enviar. `git status` mostra o que foi mexido; avise quem mexeu |

---

## Operação semanal

> **A definir com o Edson.** Os nomes abaixo ainda não existem. Enquanto não
> existirem, o clipping depende de alguém lembrar.

| Passo | Quando | Quem | Substituto |
|---|---|---|---|
| Autorizar a execução (~US$ 0,20) | [a definir — as últimas edições saíram às segundas] | [a definir] | [a definir] |
| Rodar `python main.py` | logo depois | [a definir] | |
| Revisão item a item (seção acima) | logo depois | [a definir] | |
| Aprovar a edição corrigida | antes do envio | [a definir] | |
| Enviar o PDF à 247 | até [horário a definir] | [a definir], pela caixa [a definir] | |
| Subir o PDF, com o nome que o programa deu, na pasta "Clippings Semanais" do Drive (elementum3 \| Geral › 247 DATA CENTERS) | depois do envio | quem enviou | |
| Copiar a pasta da edição (`output/archive/<data>/`) para [pasta da empresa a definir] | depois do envio | quem enviou | |

- **Destinatários na 247:** [a definir]. **Contato na 247:** [a definir].
- **A quem recorrer se o programa quebrar:** [a definir].
- **Computador novo, ou mais de um computador:** o `output/archive/` de cada
  computador só conhece as edições que saíram dele. Antes de rodar, copie da pasta
  da empresa para `output/archive/` a pasta da última edição enviada. É com ela
  que o programa sabe o que o cliente já recebeu.
