# Proposta 2b — Empresas, com os dados verificados em fonte primária

Substitui a tabela de controle acionário da proposta 2, que eu tinha escrito **de
memória** e marcado `a_verificar`. Quatro agentes pesquisaram, quatro auditores
reabriram cada URL e conferiram se a fonte diz o que a ficha afirma.

**Nenhum dos quatro lotes passou limpo.** Os erros abaixo são os que os auditores
derrubaram; o que sobrou está com a fonte ao lado.

Legenda de evidência: **A** = fonte primária (RI, CVM, SEC, release oficial) ·
**B** = imprensa de referência · **não encontrado** = não existe em fonte aberta.

---

## 1. O que eu tinha escrito errado

| minha tabela (de memória) | o que a fonte diz |
|---|---|
| Atlantic Data Centers → V.tal | **Errado como escrito.** A Atlantic é subsidiária da pernambucana **Um Telecom**. A V.tal comprou 100% da Um Telecom — anúncio 29/12/2025, Cade aprovou sem restrições em 13/05/2026 (Despacho SG nº 604). **O fechamento não está confirmado em nenhuma fonte.** |
| Ascenty → Digital Realty + Brookfield | **Certo, mas não escreva "controlada pela Digital Realty".** É JV com **controle compartilhado igualmente**: DLR 49%, Brookfield 49% (US$ 702 mi). A DLR desconsolidou a Ascenty justamente por não controlá-la sozinha (10-K FY2019 e 10-Q 30/06/2026, citações literais conferidas). |
| Odata → Aligned Data Centers | **Confirmado (A).** Desde 22/05/2023, comprada da Pátria Investments. |
| Scala → DigitalBridge | **Confirmado (A).** DigitalBridge (NYSE: DBRG) fundou a plataforma em 2020; percentuais não divulgados. |
| Positivo Tecnologia → listada na B3 | **Confirmado (A).** POSI3. Mas **não é controlada por outra empresa**: bloco familiar com acordo de acionistas somando ~49,3% das ordinárias. |
| AZ Quest → Azimut | **Confirmado (A).** Azimut Brasil comprou 60% da Quest em 2015; XP Inc. tem participação minoritária. |
| Cosern → Neoenergia | **Não verificado** — ficou de fora desta rodada. |

## 2. Duas empresas mudaram e a whitelist da proposta 2 está desatualizada

- **Bitfarms não existe mais com esse nome.** Virou **Keel Infrastructure Corp.**,
  ticker **KEEL** (Nasdaq e TSX), desde a abertura do pregão de 06/04/2026,
  redomiciliada nos EUA. Receita de US$ 229 mi em 2025 (A). Deixou de ser
  mineradora de bitcoin e migra para data center de IA/HPC.
- **Elea Data Centers passou a ser controlada.** A **I Squared Capital** (gestora
  americana) adquiriu o controle indireto em **02/06/2026** (A). Receita líquida
  consolidada de **R$ 220,4 mi em 2025** (R$ 162,5 mi em 2024), prejuízo de
  R$ 72,9 mi. É companhia aberta categoria B na CVM (código 2694-8), sem ações
  listadas. Fundador Alessandro Lombardi segue como sócio minoritário e CEO.

## 3. Números que os auditores derrubaram — não usar

| empresa | o que a ficha dizia | o que a fonte diz |
|---|---|---|
| **Claranet** | receita de GBP 507 mi no exercício encerrado em **30/06/2025** | GBP 506,8 mi é do exercício encerrado em **30/06/2024**. Dado de um ano atrás apresentado como atual. **Não existe receita do FY25 em fonte aberta** — e a Claranet vendeu a operação de Portugal nesse exercício, então 507 provavelmente superestima o porte atual. |
| **V.tal** | receita consolidada R$ 7 bi · controladora R$ 5,18 bi · impairment R$ 11,89 bi · prejuízo R$ 13,85 bi | receita **líquida** R$ **7,05** bi · controladora R$ **5,19** bi · impairment R$ **11,90** bi · prejuízo R$ **13,86** bi. Os originais vieram de truncamento, não arredondamento. |
| **Kuehne+Nagel** | Kuehne Holding tinha 55,3% em 31/12/2024, "participação estável" | A página citada não contém "55.3" nem "2024". Só reporta a posição de 31/12/2025 (55,4%). **Cai.** |
| **Scala** | enterprise value de ~US$ 4,0 bi na compra da DigitalBridge pelo SoftBank | O 10-Q citado não contém "enterprise value" nem "4.0 billion". Número pode existir, a fonte citada não o sustenta. |
| **Elea** | "já na 5ª emissão de debêntures" | O CSV da CVM citado não tem campo de emissões. Sem lastro. |
| **EVEO** | "controlada pelos cofundadores" | Nenhuma fonte aberta identifica os acionistas nem acordo de acionistas. O certo é: cofundadores **seguem como co-CEOs**; composição do controle **não encontrada**. |
| **EVEO** | XP Asset detém 31,85% | A fonte diz "**ficará com** 31,85%", com aporte em parcelas condicionadas. Integralização total não confirmada. |

## 4. Dois avisos editoriais

**RT-One — não repita que a Hitachi Energy investiu.** A TELETIME e a Telesíntese,
**ambas tier 1**, escreveram que a rodada de R$ 15 bilhões "foi liderada pela
Hitachi Energy". O release da própria Hitachi Energy (12/01/2026) descreve apenas
colaboração de fornecimento — sistemas elétricos, subestações, equipe de engenharia
— e **não menciona aporte de capital nem valor**. O texto correto é "R$ 15 bilhões
anunciados, origem dos recursos não divulgada".

Vale registrar o que isso ensina sobre a proposta 1: **tier alto não é sinônimo de
verdade**. O portão de fonte protege contra blog de campanha e página de SEO, não
contra duas redações sérias repetindo o mesmo release mal lido.

**EAF não é operadora de data center.** É entidade privada sem fins lucrativos
criada por Claro, TIM e Vivo para cumprir as obrigações do edital do 5G, sob
supervisão da Anatel. Os projetos de data center que aparecem no noticiário são
**estudos de viabilidade a pedido do governo**, sem capex confirmado. Se a ficha
não disser isso, o leitor investidor vai lê-la como player do setor.

## 5. Fichas aprovadas para uso

Com as correções acima aplicadas. Quem não está aqui não tem dado suficiente.

| empresa | ficha |
|---|---|
| **EVEO S.A.** | Empresa brasileira de servidores dedicados, nuvem privada e colocation, fundada em 1998, com data centers em Cotia e Osasco (SP), Curitiba, Fortaleza e Miami. ARR de R$ 100 mi ao fim de 2025 (B). Capital fechado; o FIP XP Infra V (XP Asset) contratou aporte de R$ 100 mi anunciado em 11/12/2025 que lhe dará 31,85% do capital. |
| **Atlantic Data Centers** | Operadora de data center neutro criada pela pernambucana Um Telecom; constrói o Recife1 no Parqtel (Recife), R$ 300 mi em três fases, primeira etapa com 150+ racks e 1 MW de TI. A Um Telecom foi comprada pela V.tal, aprovada pelo Cade em 13/05/2026. |
| **V.tal** | Operadora brasileira de rede neutra de fibra e cabos submarinos, controlada por fundos do BTG Pactual, com receita líquida consolidada de R$ 7,05 bi em 2025 e braço de data centers na Tecto. |
| **Ascenty** | Operadora de data centers no Brasil, Chile e México, em joint venture de controle compartilhado entre Digital Realty (NYSE: DLR, 49%) e Brookfield Infrastructure (49%). Capital fechado. |
| **ODATA** | Operadora latino-americana de data centers, controlada pela americana Aligned Data Centers desde maio de 2023. Capital fechado. |
| **Scala Data Centers** | Operadora brasileira de data centers hyperscale, controlada por fundos do DigitalBridge (NYSE: DBRG), com mais de 1.100 funcionários (set/2024). Capital fechado. |
| **Elea Data Centers** | Operadora carioca de data centers neutros nascida dos ativos da Oi, receita líquida de R$ 220 mi em 2025; desde junho de 2026 controlada pela gestora americana I Squared Capital. |
| **TD SYNNEX** | Distribuidora americana de tecnologia (NYSE: SNX), receita de US$ 62,5 bi no ano fiscal encerrado em 30/11/2025 e cerca de 24 mil funcionários próprios. Sem acionista controlador. |
| **Positivo Tecnologia** | Fabricante brasileira de computadores e servidores (B3: POSI3), receita líquida de R$ 3,355 bi em 2025. Bloco de controle familiar com ~49,3% das ordinárias. |
| **AZ Quest** | Gestora brasileira de recursos do grupo italiano Azimut (Azimut Brasil comprou 60% da Quest em 2015), com participação minoritária da XP. Capital fechado. |
| **Kuehne+Nagel** | Operadora logística suíça (SIX: KNIN), receita líquida de CHF 24,5 bi e 85.407 funcionários ao fim de 2025. Controlada pela Kuehne Holding AG, com 55,4% dos votos. |
| **Keel Infrastructure** | Ex-Bitfarms; desenvolve data centers e infraestrutura de energia para IA e HPC na América do Norte (Nasdaq/TSX: KEEL), receita de US$ 229 mi em 2025. Rebatizada e redomiciliada nos EUA em abril de 2026; sem controlador. |
| **Century Telecom** | Provedora brasileira de telecom e data center com 249 colaboradores, capital fechado, controle majoritário de Fernando Antônio Barbosa. |
| **HostDime** | Provedora americana de data center e infraestrutura gerenciada, 223 funcionários, capital fechado, fundada em 2003 por Manny Vivar. |
| **NextStream** | Plataforma de data centers da gestora britânica **Actis**, formada a partir de 11 data centers adquiridos da espanhola Nabiax. Porte não divulgado. |
| **EAF** | Entidade privada sem fins lucrativos criada por Claro, TIM e Vivo para executar as obrigações do edital do 5G, sob supervisão da Anatel. **Não opera data centers.** |

**Sem ficha, por falta de dado:** **RT-One** (porte, controlador e nacionalidade da
controladora não divulgados; use só "R$ 15 bi anunciados, origem não divulgada") e
**Claranet Brasil** (a receita do grupo em fonte aberta é do exercício encerrado em
30/06/2024 — GBP 506,8 mi; não há número atual).

---

## O que preciso de você

1. **A whitelist da proposta 2 precisa de dois reparos:** `Bitfarms` vira
   `Keel Infrastructure` (com Bitfarms como alias), e `Elea` deixa de ser
   independente — passa a ter I Squared Capital como controladora.
2. **Confirma que fica fora do PDF** tudo que está marcado "não encontrado"? É a
   regra da proposta 2 (campo sem fonte não aparece), mas na prática isso significa
   RT-One e Claranet saindo **sem caixa nenhuma** quando aparecerem.
3. **Cosern → Neoenergia** ficou sem verificar. Só vale conferir se energia de
   distribuidora virar assunto recorrente no clipping.
