# Notas do projeto — contexto e decisões

> Documento de continuidade. Se você (pessoa ou assistente) está chegando
> agora neste projeto, **leia isto primeiro**: aqui está o *porquê* de cada
> decisão, que não cabe no código.

## Quem vai usar

Dono de um estabelecimento que funciona em **dois turnos**:

- ☀️ **Dia** — restaurante com **pratos feitos** (pensa em migrar para self-service)
- 🌙 **Noite** — bar com **porções** e **bebidas** (destilados em dose; cervejas
  e refrigerantes em garrafa/lata)

Perfil: **não tem intimidade com informática nem com planilhas**. Toda decisão
de interface deve favorecer a simplicidade — sem jargão, sem tela cheia de
opções, sem conceito que precise de explicação.

Tamanho: **~30 itens** no cardápio. Cadastro manual é viável; importação por
planilha **não é prioridade**.

## O problema que o programa resolve

O dono precifica "no olho" ou copiando o concorrente. O item que mais vende
costuma ser o que menos dá lucro — e ninguém percebe. O programa responde:

- Quanto custa **de verdade** cada prato/porção/bebida?
- Qual a **margem** e o **CMV %** de cada um? (CMV saudável no ramo: ~30–35%)
- A carne subiu — **quais itens** ficaram com lucro ruim?

## A decisão de projeto mais importante

Todo insumo tem:

```
custo unitário real = preço de compra ÷ quantidade útil
```

A **quantidade útil já embute a perda** (limpeza, cozimento, espuma do chopp).
Esse conceito único resolve os três casos do negócio — foi a sacada que
simplificou tudo:

| Caso | Compra | Rende | Custo real |
|---|---|---|---|
| Ingrediente com perda | carne, 1 kg — R$ 32,00 | 700 g | R$ 0,0457/g |
| Bebida dosada | cachaça, 1 garrafa — R$ 25,00 | 20 doses | R$ 1,25/dose |
| Chopp | barril — R$ 400,00 | 150 copos | R$ 2,67/copo |
| Revenda pura | long neck, 1 un — R$ 4,10 | 1 un | R$ 4,10/un |
| **Mão de obra** | montador, 1 dia — R$ 100,00 | 50 pratos | R$ 2,00/prato |

**Não crie estruturas separadas** para bebida, comida e mão de obra — a
unificação é o que mantém o programa simples. A mão de obra entrou como uma
linha da mesma tabela `insumos`, com `tipo = 'Mão de obra'`, e é lançada na
ficha técnica igual a um ingrediente: *1 prato de montador*.

## Decisões já tomadas (e por quê)

- **Sem separar "almoço" e "noite"**: a *categoria* do item (Prato, Porção,
  Bebida, Sobremesa) já separa isso na prática, sem um campo extra para
  preencher nem um conceito novo para o usuário entender.
- **Self-service ficou para depois**: exige outro modelo (custo do buffet ÷ kg
  vendidos, mais controle de sobra). O banco foi desenhado para aceitar isso
  depois sem refazer o que existe.
- **Nada de PDV/comanda**: ele já tem como anotar, e uma falha no sábado à
  noite seria grave. Risco alto, ganho baixo.
- **Estoque não entra agora**: exige contagem diária, que em restaurante
  costuma ser abandonada na segunda semana. Se um dia entrar, o caminho é
  estimar a baixa a partir das fichas técnicas, sem contagem manual.
- **Simulação não grava nada**: na Análise, o novo preço do insumo só entra no
  banco se o dono clicar em *Aplicar novo preço* e confirmar. Ele precisa poder
  brincar com "e se…" sem medo de estragar o cadastro.
- **Item sem preço ou sem ficha não recebe nota**: mostrar CMV 0% 🟢 para um
  prato sem ficha técnica seria mentira. Esses ficam em ⚪ *faltam dados*, com
  a frase do que está faltando, e fora do ranking de margem.
- **Faixas de CMV no `banco.py`** (`faixa_cmv` e `FAIXAS`): a cor 🟢🟡🔴 é
  regra de negócio, não decoração — as duas abas leem do mesmo lugar.
- **Quem dá a cor é o CMV com mão de obra** (decisão do dono, e ele tem
  razão). São dois números na tela:
  - **CMV** — só insumos, na régua de 30–35% do ramo. Serve para comparar com
    o mercado; é informação, não dá a cor.
  - **CMV com mão de obra** — insumos + quem faz, sobre o preço. Régua própria
    (`CUSTO_TOTAL_BOM`/`CUSTO_TOTAL_ATENCAO`, 60% e 70%), e é ele que decide
    🟢🟡🔴.

  A primeira versão pegava a **pior** das duas notas, e isso era injusto com o
  bar: um long neck de CMV 45,6% e **zero** mão de obra ficava 🔴 sendo que
  não dá trabalho nenhum. Julgando pelos dois juntos, cozinha e bar entram na
  mesma régua. Quando o insumo está em dia e ainda assim o item não vai bem,
  a tela diz *"a mão de obra pesa no custo"*.
- **Duas abas, um cadastro só**: Insumos e Mão de obra usam a mesma classe
  (`AbaCadastro`), mudando só os rótulos e as unidades. Duas telas porque na
  cabeça dele são duas coisas; um código porque a conta é a mesma.
- **Unidades são dados, não código**: as listas de "Comprado em", "Usado em",
  "Pago por" e "Produz em" moram na tabela `unidades` e o dono edita cada uma
  pelo ⚙ ao lado do combo. As listas em `banco.py` viraram só a semente da
  primeira execução. Renomear arrasta junto quem já usava a unidade (ninguém
  fica órfão) e excluir é barrado enquanto alguém usar.

## Situação atual

- ✅ `banco.py` — esquema, CRUD, custo, margem, CMV e simulação. **Sem interface**
- ✅ Aba **Insumos** — cadastro com o custo real calculado ao vivo
- ✅ Aba **Mão de obra** — montador, cozinheiro e quantos mais precisar, pela
  mesma conta (R$ 100 por dia ÷ 50 pratos = R$ 2,00 por prato)
- ✅ **Unidades editáveis** pelo dono, nas duas abas de cadastro
- ✅ Aba **Cardápio** — ficha técnica com custo, margem e CMV se formando na tela
- ✅ Aba **Análise** — ranking de margem, alerta de lucro baixo e a simulação
  "e se o insumo subir?"

O programa já responde as três perguntas do começo deste documento. Daqui para
frente é proteção do dado (backup, senha) e conveniência (impressão).

## Roadmap

1. ✅ **Cardápio**: cadastro do item + montagem da ficha (insumo + quantidade),
   com o custo se formando na tela
2. ✅ **Preço e margem**: preço de venda, CMV % e margem com cores 🟢🟡🔴
3. ✅ **Análise**: ranking por margem; ao mudar o preço de um insumo, listar os
   itens que ficaram com margem ruim (*o recurso mais valioso do programa*)
4. ✅ **Mão de obra**: cadastro próprio e lançamento na ficha; CMV, CMV com
   mão de obra e lucro lado a lado na Análise; unidades editáveis
5. Backup automático e senha (mesma solução do projeto Fluxo de Caixa)
6. Impressão da ficha para a cozinha
7. (Futuro) Self-service por quilo

### Como a aba Análise ficou

- **Quatro quadrinhos** no topo: quantos itens estão 🟢 saudáveis, 🟡 em
  atenção, 🔴 com lucro baixo e ⚪ com dado faltando
- **Uma frase de alerta** nomeando os itens que dão pouco lucro — é o que o
  dono precisa ler sem procurar
- **Ranking** filtrável por categoria, começando pelo pior CMV; dois cliques em
  uma linha abrem a ficha técnica daquele item na aba Cardápio. As colunas
  separam **Insumos**, **Mão de obra**, **CMV** e **CMV c/ mão de obra** — esta
  última é a que dá a cor
- **Simulador** "a carne subiu?": escolhe o insumo, digita o novo preço de
  compra e vê o antes e o depois de cada item que o usa, com destaque para os
  que caem na faixa vermelha. Só grava se ele mandar

## Convenções

- Interface e código em **português**
- PyQt5 + SQLite, dados **100% locais**, distribuído como `.exe`
- Botões coloridos: verde salvar, azul limpar, vermelho excluir
- Valores em R$ no padrão brasileiro (`banco.fmt_moeda`)
- **Confirmar antes de atualizar/excluir**; nunca deixar o usuário perder
  dado sem aviso
- Lógica de cálculo **sempre** em `banco.py`, nunca dentro da tela — foi o que
  permitiu, no projeto anterior, testar tudo sem abrir a interface

## Projeto irmão

**Fluxo de Caixa** (`psrs2000/Fluxo-de-Caixa`) — controle financeiro do mesmo
dono, feito antes deste. Mesma pilha e mesmas convenções; vale consultar
quando surgir dúvida de estilo ou de solução (backup, senha, exportação,
desfazer, validação de datas).
