# Clipping de Data Centers (cliente 247) — guia rápido

## O que o programa faz

Procura no Google Notícias as notícias da última semana sobre data centers, usa
inteligência artificial (OpenAI) para descartar o que não interessa, resumir o
resto em português e extrair os números de cada matéria, e monta um **PDF de
clipping** com a logo da 247.

---

## Antes de rodar pela primeira vez

### O ambiente virtual tem de ser criado do jeito certo

O WeasyPrint (quem desenha o PDF) precisa das bibliotecas `libpango` e `libcairo`.
**Nesta máquina elas não vieram do Homebrew**: vêm de um ambiente conda em
`~/.clipping247-python`. Um `venv` criado com o `python3` do PATH instala tudo e
quebra na hora de gerar o PDF, com `cannot load library 'libpango-1.0-0'`.

```bash
/Users/pedroandrade/.clipping247-python/bin/python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Em outra máquina, o caminho do Homebrew descrito no `README.md` também funciona —
o que não funciona é misturar os dois.

### O arquivo `.env`

Guarda a chave da OpenAI, ligada a um cartão de crédito. É **confidencial**: não
abra para mostrar a ninguém, não envie e não apague.

---

## Os comandos

Sempre com `(venv)` no início da linha do terminal. Se não estiver:
`source venv/bin/activate`.

### 1. Rodar o clipping completo

```bash
python main.py
```

⚠️ **Só com autorização do Gabriel ou do Leo.** Gasta dinheiro de API e leva de
10 a 30 minutos. Sem nenhuma opção, roda tudo do zero — é sempre uma edição nova,
nunca reaproveita busca da semana passada.

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

```bash
python main.py --list-cache     # o que está guardado
python main.py --clear-cache    # apaga tudo e força execução completa
```

⚠️ `--from` **reescreve** o `output/clippings.json`. A versão anterior é guardada
em `output/clippings.anterior.json`, mas correção feita à mão só sobrevive de
verdade se estiver no `configs/overrides.json` (abaixo).

### 4. Conferir que o programa continua certo

```bash
python -m unittest discover -s tests
```

De graça, um segundo, sem internet. São 47 testes das regras que decidem o que o
investidor lê. Rode depois de mexer em qualquer configuração. **Se algum falhar,
não envie o clipping.**

---

## O que conferir antes de enviar

No fim da execução o programa imprime o que descartou e o que não conseguiu
fazer. Três avisos merecem atenção:

**🚨 "RESUMOS CITAM NÚMERO QUE NÃO ESTÁ NA MATÉRIA"** — o mais importante. O
programa leu cada número do resumo e foi procurá-lo no texto da matéria. Se
avisar, **abra o link e confira antes de enviar**. Na edição de 21/09/2026 três
números publicados (R$ 30 bilhões, 170 GW e 200 GW) não existiam em lugar nenhum
da matéria. Também pode ser o leitor de números errando uma grafia incomum — por
isso o resumo não é alterado sozinho.

**⚠️ "empresas novas, ainda sem ficha"** — apareceu uma empresa que não está em
`configs/empresas.json`. Ela **não** ganha caixa de apresentação nenhuma. Se valer
a pena, pesquise e acrescente ao arquivo.

**⚠️ "fontes ainda não classificadas"** — apareceu um veículo novo. Ele entra no
clipping como tier 3: não pode vencer uma disputa de duplicata nem sustentar um
número sozinho. Promova ou rebaixe em `configs/fontes.json`.

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
| Mudar a seção | `categoria` | `{"url": "...", "de": "clientes", "para": "governo", "motivo": "..."}` |
| Reescrever o resumo | `resumo` | `{"url": "...", "texto": "...", "motivo": "..."}` |
| Grifar (fundo amarelo no índice) | `highlight` | `["url1", "url2"]` |
| Corrigir o nome do veículo | `fonte_nome` | `{"url": "...", "para": "Investing.com"}` |
| Juntar duplicatas que passaram | `dedup` | `{"manter": "url-boa", "fundir": ["url-repetida"], "motivo": "..."}` |
| Aprovar a ficha de uma empresa | `empresa` | `{"nome": "...", "overview": "...", "aprovado_por": "Pedro", "data": "..."}` |

Depois rode o **comando 2**.

**O campo `motivo` é obrigatório** em `removidas`, `categoria`, `resumo` e
`dedup`. Não é burocracia: daqui a dois meses esses motivos são a única lista real
de onde o programa erra, e viram os exemplos dos prompts. Sem eles sobra uma lista
de URLs sem sentido.

Duas armadilhas:
- Reescrever o resumo **apaga a caixa de métricas** daquela notícia. A regra é que
  o leitor tem de achar os dois números no parágrafo acima — e o parágrafo mudou.
- Se a URL não bater com nenhuma notícia da edição, o programa avisa. Correção
  antiga que nunca mais casa pode sair do arquivo.

Se o comando 2 der erro depois de editar, sobrou ou faltou uma vírgula ou uma
aspa. O programa diz a linha.

---

## Onde ficam as coisas

| | |
|---|---|
| PDF da semana | `output/clippings_output.pdf` |
| Notícias da semana | `output/clippings.json` |
| Versão anterior, antes da última reescrita | `output/clippings.anterior.json` |
| Edições antigas | `output/archive/AAAA-MM-DD/` |
| Correções manuais | `configs/overrides.json` |
| Empresas com ficha | `configs/empresas.json` |
| Tiers de veículo | `configs/fontes.json` |
| Qual modelo cada etapa usa | `configs/modelos.json` |
| Por que o programa é assim | `DECISOES.md` |

Cada edição é arquivada em duas versões: `clippings.raw.json`, que é o que o
programa produziu e **nunca** é sobrescrito, e `clippings.final.json` com o
`clipping.pdf`, que é o que foi de fato enviado. A diferença entre as duas é o
julgamento humano da semana, e é com ela que dá para medir se uma mudança no
programa melhorou alguma coisa.

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

- O **comando 1** custa dinheiro e **só roda com autorização do Gabriel ou do Leo**.
- Nenhum número vai para o PDF sem estar no texto da matéria. Quando o programa
  não consegue confirmar, ele avisa em vez de publicar.
