# 🍽️ Cardápio — Ficha Técnica e Custo

**Descubra quanto custa de verdade cada prato, porção e bebida do seu
restaurante ou bar — e quanto sobra de lucro em cada um.**

## O problema que ele resolve

A maioria dos donos precifica "no olho" ou copiando o concorrente. Aí acontece
o clássico: o item que **mais vende** é justamente o que **menos dá lucro** — e
ninguém percebe. O programa responde o que uma planilha de caixa não responde:
*a picanha dá lucro?*, *posso baixar o preço do chopp?*, *a carne subiu — quanto
isso me custou?*

## A ideia central

Todo insumo tem **preço de compra ÷ quantidade útil = custo unitário real**.
Um único conceito resolve cozinha e bar:

| Insumo | Compra | Rende | Custo real |
|---|---|---|---|
| Carne | 1 kg — R$ 32,00 | 700 g (perde 30% na limpeza) | **R$ 0,0457/g** |
| Cachaça | 1 garrafa — R$ 25,00 | 20 doses | **R$ 1,25/dose** |
| Barril de chopp | 50 L — R$ 400,00 | 150 copos | **R$ 2,67/copo** |
| Long neck | 1 un — R$ 4,10 | 1 unidade | **R$ 4,10/un** |

A "quantidade útil" já embute a perda — limpeza, cozimento, espuma do chopp.

## Como rodar

```bash
pip install -r requirements.txt
python cardapio.py
```

## O recurso mais útil: "e se a carne subir?"

Na aba **Análise**, escolha o insumo, digite o novo preço de compra e clique em
*Ver efeito*. O programa mostra, item por item, o custo e o lucro **antes e
depois**, e avisa quais pratos passam para a faixa vermelha. Nada é gravado até
você mandar aplicar o preço.

## Situação atual

- ✅ **Insumos** — cadastro com cálculo do custo real ao vivo
- ✅ **Cardápio** — ficha técnica com custo, margem e CMV se formando na tela
- ✅ **Análise** — ranking de margem, alerta dos itens com lucro baixo e a
  simulação de aumento de preço

Cada item recebe uma cor pelo CMV — 🟢 até 35%, 🟡 até 45%, 🔴 acima disso.
Item sem preço de venda ou sem ficha técnica fica em ⚪, dizendo o que falta.

## Arquivos

| Arquivo | O quê |
|---|---|
| `banco.py` | Dados e cálculos (SQLite puro, sem interface) |
| `cardapio.py` | Interface PyQt5 |
