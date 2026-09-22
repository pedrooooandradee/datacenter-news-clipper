# Proposta 2 — Empresas conhecidas, aliases e cadeia de controle

Para aprovar item a item.

## O critério, antes da lista

"Conhecida" é **conhecida do seu leitor**: executivo de private equity de
infraestrutura (Arch, KINEA, Just Climate) e conselho da 247. Não é "famosa no
mundo da tecnologia". Isso muda os dois lados:

- **Entram como conhecidas** empresas que um leitor de tecnologia talvez não
  saiba de cor, mas um investidor de infra sabe: V.tal, Casa dos Ventos, Auren.
- **Saem para desconhecidas** empresas gigantes no seu mercado mas invisíveis
  para quem lê: TD SYNNEX (distribuidora, receita na casa das dezenas de bilhões
  de dólares) não diz nada a um investidor de infraestrutura brasileiro.

**Consequência prática:** empresa conhecida **não precisa de nenhum dado** no
arquivo — é só uma lista de filtro, com os aliases. Só as **desconhecidas**
precisam de perfil pesquisado, e só quando aparecem.

## Por que aliases e cadeia de controle (Q18)

A manchete real desta semana:

> "Eveo escolhe data center da **Atlantic**, da **V.tal**, para expansão no Nordeste"

Três empresas numa frase. V.tal é conhecida do leitor; Atlantic e EVEO não. E a
relação entre elas **é a notícia**. Lista plana produz três caixas soltas; com
cadeia de controle, uma frase explica o negócio.

---

## Lista de conhecidas (não geram overview)

### Hyperscalers e clientes-alvo
Amazon / AWS · Microsoft / Azure · Google / Alphabet / Google Cloud · Meta /
Facebook · Oracle / OCI · Apple · IBM · ByteDance / TikTok · Alibaba Cloud ·
Tencent Cloud · Huawei Cloud · Nvidia · OpenAI · Anthropic · xAI · Salesforce · SAP

### Operadores de data center
Ascenty · Equinix · Odata · Scala Data Centers · Elea Digital · Digital Realty ·
NTT · CyrusOne · Vantage · EdgeConneX · STACK · QTS · Switch · Iron Mountain

### Energia
Eletrobras · Petrobras · Engie · Enel · Neoenergia · CPFL · Cemig · Copel · EDP ·
Casa dos Ventos · Auren · Serena

### Telecom e fibra
Vivo / Telefônica · Claro / América Móvil · TIM · Oi · V.tal

### Equipamento e semicondutores
Schneider Electric · Vertiv · ABB · Siemens · Cisco · Dell · HPE · Supermicro ·
AMD · Intel · TSMC · Samsung · SK Hynix

### Capital
Itaú · Bradesco · BTG Pactual · XP · Brookfield · Blackstone · KKR · Actis ·
Pátria · Vinci · DigitalBridge · GIC · CPPIB · Mubadala · IFC · BNDES · KINEA

## Aliases (o trabalho real do arquivo)

| canônico | também escrito como |
|---|---|
| Amazon | AWS, Amazon Web Services, Amazon AWS |
| Microsoft | Azure, Microsoft Azure, Azure AI Foundry |
| Alphabet | Google, Google Cloud, GCP |
| ByteDance | TikTok |
| Meta | Facebook |
| Telefônica Brasil | Vivo |
| América Móvil | Claro, Embratel |
| Neoenergia | Cosern, Coelba, Celpe, Elektro |

## Cadeia de controle — **tudo aqui precisa ser verificado antes de publicar**

Escrevi de memória para você ver o formato. **Nenhuma destas linhas pode ir para
o arquivo sem confirmação em fonte primária** (site de RI, fato relevante, CVM).

| empresa | controlador / grupo | status |
|---|---|---|
| Atlantic Data Centers | V.tal | a_verificar |
| Ascenty | Digital Realty + Brookfield | a_verificar |
| Odata | Aligned Data Centers | a_verificar |
| Scala Data Centers | DigitalBridge | a_verificar |
| Cosern | Neoenergia | a_verificar |
| Positivo Tecnologia | listada na B3 | a_verificar |
| AZ Quest | Azimut | a_verificar |

---

## Desconhecidas desta semana (geram overview)

Semente para a pesquisa, tirada dos 53 itens da edição de 21 set:

EVEO · Atlantic Data Centers · TD SYNNEX · Positivo Tecnologia · AZ Quest ·
Century · Bitfarms · EAF · Kuehne+Nagel · HostDime · Claranet · NextStream · RT-One

## Formato do overview — **aprove isto antes de eu pesquisar 15 empresas**

Uma frase, máximo duas linhas no PDF, sob o resumo:

> **EVEO** — provedora brasileira de servidores dedicados e nuvem privada, com
> operação em Fortaleza; capital fechado. *(receita: a confirmar)*

Campos: o que faz · nacionalidade · tamanho (receita, market cap ou funcionários,
o que existir em fonte pública) · ticker, se listada · controlador, se relevante
para a notícia.

Quando um campo não existir em fonte pública, ele **não aparece** — não se
escreve "porte não divulgado", simplesmente some. Empresa sem nenhum dado
confirmável não gera caixa e entra na lista de quarentena do fim da execução.

---

## Quatro decisões de fronteira

Estas eu não consigo decidir por você — dependem de quem lê:

1. **Vertiv** — listada em NYSE, fornecedora de energia e refrigeração para data
   center. Pus como conhecida. Um investidor de infra digital conhece; um
   generalista talvez não.
2. **TD SYNNEX** — receita enorme, invisível para o leitor. Pus como desconhecida.
3. **AZ Quest** — gestora brasileira. KINEA e Itaú conhecem; Just Climate (UK)
   provavelmente não. O leitor é misto.
4. **Kuehne+Nagel** — top-5 global de logística. Conhecida em infraestrutura,
   não em data center. Pus como desconhecida.
