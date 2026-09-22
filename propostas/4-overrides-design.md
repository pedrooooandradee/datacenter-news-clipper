# Proposta 4 — `overrides.json`

Para aprovar item a item. Resolve o problema de hoje: as edições manuais são
feitas direto no `clippings.json` e somem na execução seguinte.

## Onde entra

Última etapa antes de montar o PDF. O pipeline escreve `clippings.json`; o
`overrides.json` é aplicado por cima; o PDF sai do resultado. Rodar de novo o
comando do PDF reaplica tudo.

Commitado no repo (Q15): o valor está no acúmulo. Depois de oito semanas, é o
único conjunto real de casos em que o modelo errou — e vira exemplo para os
prompts de classificação e de dedup, em vez de exemplo inventado.

## Formato

```json
{
  "versao": 1,
  "removidas": [
    {"url": "https://…", "motivo": "opiniao_sem_fato_novo", "data": "2026-09-21"}
  ],
  "categoria": [
    {"url": "https://…", "de": "clientes", "para": "inovação",
     "motivo": "produto de software da AWS, não expansão de infraestrutura"}
  ],
  "resumo": [
    {"url": "https://…", "texto": "…",
     "motivo": "modelo tratou ReData (regime tributário) como empresa"}
  ],
  "highlight": ["https://…", "https://…"],
  "fonte_nome": [
    {"url": "https://…", "para": "Investing.com"}
  ],
  "dedup": [
    {"manter": "https://…", "fundir": ["https://…", "https://…"],
     "motivo": "mesma sanção, enfoques diferentes"}
  ],
  "empresa": [
    {"nome": "EVEO", "overview": "…", "aprovado_por": "Pedro", "data": "2026-09-22"}
  ]
}
```

Chave é sempre a **URL final** (depois do redirecionamento do Google News), não
a do feed.

## Por que `motivo` é obrigatório

É o campo que transforma o arquivo de "lista de remendos" em corpus. Sem ele,
daqui a dois meses você tem 40 URLs removidas e nenhuma ideia do padrão. Com ele,
os motivos mais frequentes viram os exemplos novos do
`classification_prompt.txt` — que hoje só tem exemplos escritos no vazio.

## `empresa`: a saída da quarentena

Pela Q3, empresa nova entra como rascunho e não vai ao PDF até revisão. O bloco
`empresa` é onde a revisão fica registrada. Uma vez aprovado, o overview passa a
sair e migra para o arquivo de empresas na semana seguinte.

---

## Duas decisões suas

1. **Remoção é permanente ou só daquela semana?** Proposta: **permanente por
   URL**. A mesma matéria não deve voltar. Notícia diferente sobre o mesmo
   assunto tem URL diferente e passa normalmente.
2. **O bloco `dedup` deve realimentar o limiar de embedding automaticamente?**
   Proposta: **não, por enquanto.** Ele vira conjunto de teste, que você usa para
   recalibrar à mão. Ajuste automático de limiar com 20 exemplos é como se
   introduz um viés sem perceber.
