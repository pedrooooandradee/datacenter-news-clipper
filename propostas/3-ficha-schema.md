# Proposta 3 — Esquema da ficha e regras de ratio

Para aprovar item a item. É a peça que decide se a caixa de ratios ajuda ou
envergonha.

## O princípio

Todo número carrega **três marcas**: a que projeto pertence, de que **fase** é, e
se o escopo é **do projeto ou do mercado**. Sem as três, não vira ratio.

É o que separa o certo do lixo no caso real desta semana:

| fonte | o que o extrator vê | ratio |
|---|---|---|
| BNamericas | R$ 300 mi (projeto, total) + 6 MW (projeto, total) | **R$ 50 mi/MW** — certo |
| Exame | US$ 8 bi (**mercado**, ano) + 106 MW (**mercado**, semestre) | nenhum — escopos não casam |

Sem a marca de escopo, a Exame produz "R$ 75 mi/MW do data center da EVEO".

## Esquema

```json
{
  "projeto": {
    "empresa": "Atlantic Data Centers",
    "empresa_grupo": "V.tal",
    "local": "Recife, PE",
    "tipo": "colocation",
    "ano_operacao": 2027
  },
  "valores": [
    {
      "campo": "capex",
      "valor": 300000000, "moeda": "BRL",
      "escopo": "projeto", "fase": "total",
      "fonte_frase": "investimento total estimado em R$ 300 milhões",
      "no_resumo": true
    },
    {
      "campo": "capex",
      "valor": 41000000, "moeda": "BRL",
      "escopo": "projeto", "fase": "fase_1",
      "fonte_frase": "a primeira fase recebeu R$ 41 milhões do BNDES",
      "no_resumo": true
    },
    {
      "campo": "capacidade_ti",
      "valor": 6, "unidade": "MW",
      "escopo": "projeto", "fase": "total",
      "fonte_frase": "capacidade projetada de 6 MW",
      "no_resumo": true
    }
  ],
  "kpis_reportados": [
    {
      "nome": "vacancia", "valor": 4, "unidade": "%",
      "escopo": "mercado_brasil",
      "fonte_frase": "a taxa de vacância no setor está em apenas 4%"
    }
  ],
  "ratios": []
}
```

### Campos de `valores`
`capex` · `capacidade_ti` (MW) · `capacidade_contratada` (MW) · `area_terreno` (m²)
· `area_construida` (m²) · `energia_contratada` (MW) · `consumo_agua` (m³/dia) ·
`empregos_diretos` · `empregos_construcao`

### Valores de `escopo`
`projeto` · `empresa` · `mercado_brasil` · `mercado_global` · `hipotetico`

`hipotetico` existe por causa do ReData: *"um data center de 100 MW podendo gerar
R$ 25 bilhões em investimentos"* é exemplo ilustrativo do governo, não projeto.
Hoje isso viraria um ratio atribuído a uma empresa.

### Valores de `fase`
`total` · `fase_1` · `fase_2` · `fase_3` · `anunciado` · `em_operacao`

## Regras de ratio — executadas em Python, nunca pelo modelo

Um ratio só é calculado e publicado se **todas** forem verdadeiras:

1. Os dois números têm o **mesmo `escopo`**, e ele é `projeto` ou `empresa`
2. Os dois números têm a **mesma `fase`**
3. Os dois números têm `no_resumo: true` (Q12 — o leitor precisa conferir no
   parágrafo acima)
4. A mesma moeda, ou conversão com a taxa e a data declaradas

Ratios calculados: `capex / capacidade_ti` · `capex / area_construida` ·
`capex / area_terreno` · `capacidade_ti / area_construida`

**`kpis_reportados` nunca entra em cálculo.** É copiado com a frase de origem, e
só isso (Q19).

## Como sai no PDF

Os insumos ficam à vista, para o leitor auditar de cabeça:

> **Métricas** · R$ 300 mi ÷ 6 MW = **R$ 50 mi/MW** (total)
> *Reportado:* vacância do setor no Brasil, 4%

Se nenhuma regra fecha, **a caixa não aparece** — e a execução reporta no fim
quantas notícias tinham número mas não pareavam (Q24).

---

## Três decisões suas

1. **`capacidade_ti` em MW de TI ou de energia total?** O mercado fala em MW de
   TI; a imprensa brasileira quase sempre não distingue. Proposta: capturar como
   vem, marcar `capacidade_ti` só quando a matéria disser "MW de TI"; caso
   contrário `energia_contratada`. Isso vai deixar muita caixa vazia no começo —
   é o preço de não publicar número ambíguo.
2. **Conversão de moeda.** A BNamericas dá os dois (R$ 300 mi / US$ 54 mi).
   Proposta: nunca converter; publicar na moeda em que o número veio.
3. **`ano_operacao` quando a matéria diz "primeiro semestre de 2026" e outra diz
   "primeiro trimestre de 2026"** (aconteceu com a Century). Proposta: guardar o
   texto como veio, não normalizar para um ano.
