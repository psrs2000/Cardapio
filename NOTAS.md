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

**Não crie estruturas separadas** para bebida e comida — a unificação é o que
mantém o programa simples.

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

## Situação atual

- ✅ `banco.py` — esquema, CRUD, custo, margem e CMV. **Sem interface**
- ✅ Aba **Insumos** — cadastro com o custo real calculado ao vivo
- 🚧 Aba **Cardápio** — montar a ficha técnica de cada item
- 🚧 Aba **Análise** — ranking de margem e alerta de itens com lucro baixo

## Roadmap

1. **Cardápio**: cadastro do item + montagem da ficha (insumo + quantidade),
   com o custo se formando na tela
2. **Preço e margem**: preço de venda, CMV % e margem com cores 🟢🟡🔴
3. **Análise**: ranking por margem; ao mudar o preço de um insumo, listar os
   itens que ficaram com margem ruim (*o recurso mais valioso do programa*)
4. Backup automático e senha (mesma solução do projeto Fluxo de Caixa)
5. Impressão da ficha para a cozinha
6. (Futuro) Self-service por quilo

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
