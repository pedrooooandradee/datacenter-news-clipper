# Proposta 1 — Tiers de fonte

Para aprovar item a item. Decide três coisas: quem pode ser **sobrevivente** de um
grupo de duplicatas (Q14), quem pode ser **fonte única de um número** que vira
ratio (Q2), e quem **nem entra** no clipping.

## A regra

| tier | pode entrar | pode ser sobrevivente | pode ser fonte única de número |
|---|---|---|---|
| 1 | sim | sim | sim |
| 2 | sim | sim | sim, se o número for do próprio sujeito da matéria |
| 3 | sim | **não** | **não** — precisa de corroboração tier 1/2 |
| 4 | **não** | — | — |

**Domínio novo, não listado → tier 3 por padrão.** Conservador: não descarta
notícia local legítima e não deixa um domínio desconhecido vencer um grupo nem
sustentar um ratio sozinho. E no fim da execução o programa lista os domínios
novos da semana, para você promovê-los ou rebaixá-los (Q24).

---

## Tier 1 — referência

**Oficiais** (primários sobre os próprios atos): gov.br, senado.leg.br,
camara.leg.br, aneel.gov.br, epe.gov.br, mme.gov.br, ons.org.br, bndes.gov.br,
cvm.gov.br, e páginas de RI das empresas.

**Negócios**: Valor Econômico, Estadão / Broadcast, Folha de S.Paulo, O Globo,
Reuters, Bloomberg, Financial Times, Wall Street Journal.

**Setoriais de data center / telecom / energia**: Data Center Dynamics,
Data Center Frontier, BNamericas, TeleSíntese, Teletime, Mobile Time,
Agência iNFRA, MegaWhat, Canal Energia, epbr.

## Tier 2 — confiável, menos densidade setorial

g1 / Globo, UOL, CNN Brasil, InfoMoney, Exame, IstoÉ Dinheiro, Poder360,
InvestNews, Monitor Mercantil, Convergência Digital, TI Inside, IT Forum,
Computer Weekly, Tecmundo, Olhar Digital, DPL News, IPNews, Inforchannel,
The Register, Ars Technica, Tom's Hardware.

## Tier 3 — admissível, nunca autoritativo

- **Imprensa regional pequena**: agorarn.com.br, 18horas.com.br, al1.com.br,
  mais.opovo.com.br, Tribuna, vocativo.com
- **Sites de mandato parlamentar e partidários**: samiabomfim.com.br
- **Agregadores e sites de IA/tecnologia de qualidade variável**: Unite.AI
- **Qualquer domínio novo não listado**

Motivo de manter o tier 3 em vez de cortar: a matéria do `agorarn.com.br` sobre
energia no RN é notícia local de verdade, que veículo nacional não cobre. O que
não pode é ela vencer a disputa de um grupo ou sustentar um número sozinha.

## Tier 4 — excluir

- **Conteúdo gerado para SEO**: `shattered.io` é o caso desta semana. Heurística
  de detecção, não só lista de domínio: ano entre colchetes no título
  ("[2026]"), slug traduzido do tipo `/pt/`, sem autor nem expediente.
- **Agregadores sem redação própria** e sites de afiliados
- **Release puro** republicado sem veículo identificável

---

## Três decisões suas

1. **Exame e Computer Weekly em tier 2** — ambas apareceram esta semana com
   problema: a Exame misturando números de mercado no projeto da EVEO, a
   Computer Weekly repetindo os fatos do ReData sem fato novo. Tier 2 me parece
   certo (o problema é de extração, não de veículo), mas é discutível.
2. **Unite.AI em tier 3** — apareceu 2 vezes. Não conheço a redação bem o
   suficiente para colocar em 2. Se você conhece, corrija.
3. **DPL News e IPNews em tier 2** — setoriais pequenos de telecom LatAm.
   Podem merecer tier 1 setorial. Sua chamada.
