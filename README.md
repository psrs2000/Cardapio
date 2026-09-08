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
| Montador | 1 dia — R$ 100,00 | 50 pratos montados | **R$ 2,00/prato** |

A "quantidade útil" já embute a perda — limpeza, cozimento, espuma do chopp.
E como a **mão de obra** obedece à mesma conta, ela entra na ficha técnica do
prato igual a um ingrediente: *1 prato de montador, 1 prato de cozinheiro*.

## Como rodar

```bash
pip install -r requirements.txt
python cardapio.py
```

## Gerar o programa (.exe) para Windows

Dê **dois cliques em `gerar_exe.bat`**. Ele instala o que falta, empacota tudo
e avisa onde ficou o programa (`dist\Cardapio.exe`) — um arquivo só, que roda
em qualquer Windows, sem precisar de Python instalado na máquina de destino.

Depois:

1. Crie uma pasta só dele, por exemplo `C:\Cardapio`
2. Copie o `Cardapio.exe` para lá
3. Botão direito no arquivo → *Enviar para → Área de trabalho (criar atalho)*

**Onde ficam os seus dados:** na mesma pasta do `Cardapio.exe` — o banco
(`cardapio.db`), as configurações (`config.json`) e a pasta `backups`. Por isso
não vale pôr o programa em *Arquivos de Programas*: o Windows não deixa gravar
lá. Para levar tudo para outro computador, basta copiar a pasta inteira.

Duas coisas normais que assustam na primeira vez: o arquivo tem uns 50 MB (leva
o Python e o PyQt5 dentro) e demora uns segundos para abrir na primeira vez.
Alguns antivírus implicam com programas empacotados assim — se o seu reclamar,
é falso positivo, e você libera nas exceções dele.

Quer um ícone próprio? Ponha um arquivo chamado `icone.ico` na pasta do projeto
antes de gerar; o script usa sozinho.

## O recurso mais útil: "e se a carne subir?"

Na aba **Análise**, escolha o insumo, digite o novo preço de compra e clique em
*Ver efeito*. O programa mostra, item por item, o custo e o lucro **antes e
depois**, e avisa quais pratos passam para a faixa vermelha. Nada é gravado até
você mandar aplicar o preço.

## Situação atual

- ✅ **Insumos** — cadastro com cálculo do custo real ao vivo
- ✅ **Mão de obra** — montador, cozinheiro e quantos mais precisar, com as
  unidades de medida editáveis por você (⚙ ao lado de cada lista)
- ✅ **Cardápio** — ficha técnica com custo, margem e CMV se formando na tela
- ✅ **Análise** — ranking de margem, alerta dos itens com lucro baixo e a
  simulação de aumento de preço
- ✅ **Configurações** — senha de acesso, backup automático e os limites das cores

A Análise mostra dois números por item: o **CMV** (só insumos, para você
comparar com os 30–35% do ramo) e o **CMV com mão de obra** (insumos + quem
faz, sobre o preço). É o segundo que dá a cor — 🟢 até 60%, 🟡 até 70%, 🔴
acima — porque é ele que diz o que sobra de verdade. Item sem preço de venda
ou sem ficha técnica fica em ⚪, dizendo o que falta.

**Esses limites são seus.** Em *Análise → Limites das cores* você define a
partir de que ponto um item fica amarelo ou vermelho, com um botão para voltar
ao padrão. Cada casa tem a sua realidade.

## Arquivos

| Arquivo | O quê |
|---|---|
| `banco.py` | Dados e cálculos (SQLite puro, sem interface) |
| `cardapio.py` | Interface PyQt5 |
| `cardapio.db` | Seus dados — fica na pasta do programa |
| `config.json` | Senha e preferências de backup |

## Seus dados não se perdem

Ligue **backup automático ao fechar** nas Configurações e escolha a pasta (um
pen drive, uma pasta da nuvem). A cada vez que você fecha o programa ele guarda
uma cópia, mantendo sempre as 10 mais recentes. Dá também para salvar uma cópia
na hora, a qualquer momento.

Se quiser, ponha uma **senha** para abrir o programa. Ela não fica escrita em
lugar nenhum — só uma marca embaralhada dela —, então guarde bem: esquecendo,
a única saída é apagar o `config.json` (os dados do cardápio ficam intactos).
