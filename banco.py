"""
Camada de dados do Cardápio — SQLite puro, sem dependência de interface.

Modelo (o coração do programa):

    insumo → preço de compra ÷ quantidade útil = CUSTO UNITÁRIO REAL

Esse único conceito resolve os três casos do estabelecimento:

    carne     : 1 kg por R$ 32,00  rende 700 g       → R$ 0,0457 por g
    cachaça   : 1 garrafa R$ 25,00 rende 20 doses    → R$ 1,25 por dose
    long neck : 1 un por R$ 4,10   rende 1 un        → R$ 4,10 por un

A "quantidade útil" já embute a perda (limpeza, cozimento, espuma do chopp).
"""

import os
import sqlite3
import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cardapio.db")

# unidades sugeridas nos combos da tela
UNIDADES_COMPRA = ["kg", "g", "L", "ml", "un", "garrafa", "barril", "caixa",
                   "pacote", "maço", "dúzia"]
UNIDADES_USO = ["g", "ml", "un", "dose", "copo", "fatia", "porção"]

CATEGORIAS = ["Prato", "Porção", "Bebida", "Sobremesa", "Outro"]


def conectar():
    con = sqlite3.connect(DB_PATH)
    con.execute("PRAGMA foreign_keys = ON")
    return con


def init_db():
    con = conectar()
    con.execute("""
        CREATE TABLE IF NOT EXISTS insumos (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            nome           TEXT    NOT NULL UNIQUE,
            unidade_compra TEXT    NOT NULL,
            preco_compra   REAL    NOT NULL DEFAULT 0,
            unidade_uso    TEXT    NOT NULL,
            qtd_util       REAL    NOT NULL DEFAULT 1,
            fornecedor     TEXT    DEFAULT '',
            atualizado_em  TEXT    DEFAULT ''
        )""")
    con.execute("""
        CREATE TABLE IF NOT EXISTS itens (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            nome        TEXT    NOT NULL UNIQUE,
            categoria   TEXT    DEFAULT '',
            preco_venda REAL    DEFAULT 0,
            observacao  TEXT    DEFAULT ''
        )""")
    con.execute("""
        CREATE TABLE IF NOT EXISTS ficha (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id    INTEGER NOT NULL REFERENCES itens(id)   ON DELETE CASCADE,
            insumo_id  INTEGER NOT NULL REFERENCES insumos(id) ON DELETE RESTRICT,
            quantidade REAL    NOT NULL DEFAULT 0,
            UNIQUE(item_id, insumo_id)
        )""")
    con.commit()
    con.close()


# ── formatação ────────────────────────────────────────────────────
def fmt_moeda(v, casas=2) -> str:
    """R$ 1.234,56 (padrão brasileiro)."""
    try:
        v = float(v)
    except (TypeError, ValueError):
        return ""
    s = f"{abs(v):,.{casas}f}".replace(",", "#").replace(".", ",").replace("#", ".")
    return f"-R$ {s}" if v < 0 else f"R$ {s}"


def fmt_num(v, casas=2) -> str:
    try:
        v = float(v)
    except (TypeError, ValueError):
        return ""
    return f"{v:,.{casas}f}".replace(",", "#").replace(".", ",").replace("#", ".")


def parse_num(texto) -> float:
    """Aceita '1.234,56' e '1234.56'."""
    s = str(texto).strip().replace("R$", "").replace(" ", "")
    if not s:
        return 0.0
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".") if s.rindex(",") > s.rindex(".") \
            else s.replace(",", "")
    else:
        s = s.replace(",", ".")
    return float(s)


def custo_unitario(preco_compra, qtd_util) -> float:
    """Custo real de 1 unidade de USO do insumo."""
    try:
        qtd_util = float(qtd_util)
        if qtd_util <= 0:
            return 0.0
        return float(preco_compra) / qtd_util
    except (TypeError, ValueError, ZeroDivisionError):
        return 0.0


# ── faixas de CMV ─────────────────────────────────────────────────
# CMV = quanto de cada real vendido vai embora só em insumo.
# No ramo, até ~35% é saudável; acima de 45% o item quase não dá lucro.
CMV_BOM = 35.0
CMV_ATENCAO = 45.0

FAIXAS = {
    "bom":      {"sinal": "🟢", "rotulo": "Saudável",
                 "cor": "#1b5e20", "fundo": "#e8f5e9"},
    "atencao":  {"sinal": "🟡", "rotulo": "Atenção",
                 "cor": "#ef6c00", "fundo": "#fff3e0"},
    "ruim":     {"sinal": "🔴", "rotulo": "Lucro baixo",
                 "cor": "#c62828", "fundo": "#ffebee"},
    "sem_dado": {"sinal": "⚪", "rotulo": "Faltam dados",
                 "cor": "#616161", "fundo": "#f5f5f5"},
}


def faixa_cmv(cmv, tem_dados=True) -> str:
    """Classifica o CMV em 'bom', 'atencao', 'ruim' ou 'sem_dado'.

    Sem preço de venda ou sem ficha técnica não dá para julgar o item —
    mostrar 0% de CMV nesse caso enganaria o usuário.
    """
    if not tem_dados:
        return "sem_dado"
    if cmv <= CMV_BOM:
        return "bom"
    if cmv <= CMV_ATENCAO:
        return "atencao"
    return "ruim"


# ── insumos ───────────────────────────────────────────────────────
def listar_insumos():
    con = conectar()
    linhas = con.execute(
        "SELECT id, nome, unidade_compra, preco_compra, unidade_uso, qtd_util,"
        " fornecedor, atualizado_em FROM insumos ORDER BY nome").fetchall()
    con.close()
    return linhas


def obter_insumo(iid):
    con = conectar()
    r = con.execute(
        "SELECT id, nome, unidade_compra, preco_compra, unidade_uso, qtd_util,"
        " fornecedor, atualizado_em FROM insumos WHERE id=?", (iid,)).fetchone()
    con.close()
    return r


def salvar_insumo(iid, nome, unidade_compra, preco_compra, unidade_uso,
                  qtd_util, fornecedor=""):
    """Insere (iid=None) ou atualiza um insumo. Devolve o id."""
    agora = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    con = conectar()
    try:
        if iid:
            con.execute(
                "UPDATE insumos SET nome=?, unidade_compra=?, preco_compra=?,"
                " unidade_uso=?, qtd_util=?, fornecedor=?, atualizado_em=?"
                " WHERE id=?",
                (nome, unidade_compra, preco_compra, unidade_uso, qtd_util,
                 fornecedor, agora, iid))
        else:
            cur = con.execute(
                "INSERT INTO insumos (nome, unidade_compra, preco_compra,"
                " unidade_uso, qtd_util, fornecedor, atualizado_em)"
                " VALUES (?,?,?,?,?,?,?)",
                (nome, unidade_compra, preco_compra, unidade_uso, qtd_util,
                 fornecedor, agora))
            iid = cur.lastrowid
        con.commit()
    finally:
        con.close()
    return iid


def excluir_insumo(iid):
    """Não deixa excluir insumo usado em alguma ficha (devolve a lista de itens)."""
    con = conectar()
    usos = con.execute(
        "SELECT i.nome FROM ficha f JOIN itens i ON i.id = f.item_id"
        " WHERE f.insumo_id=? ORDER BY i.nome", (iid,)).fetchall()
    if usos:
        con.close()
        return [u[0] for u in usos]
    con.execute("DELETE FROM insumos WHERE id=?", (iid,))
    con.commit()
    con.close()
    return []


# ── itens do cardápio e fichas ────────────────────────────────────
def listar_itens():
    con = conectar()
    linhas = con.execute(
        "SELECT id, nome, categoria, preco_venda, observacao"
        " FROM itens ORDER BY categoria, nome").fetchall()
    con.close()
    return linhas


def salvar_item(iid, nome, categoria, preco_venda, observacao=""):
    con = conectar()
    try:
        if iid:
            con.execute(
                "UPDATE itens SET nome=?, categoria=?, preco_venda=?, observacao=?"
                " WHERE id=?", (nome, categoria, preco_venda, observacao, iid))
        else:
            cur = con.execute(
                "INSERT INTO itens (nome, categoria, preco_venda, observacao)"
                " VALUES (?,?,?,?)", (nome, categoria, preco_venda, observacao))
            iid = cur.lastrowid
        con.commit()
    finally:
        con.close()
    return iid


def excluir_item(iid):
    con = conectar()
    con.execute("DELETE FROM ficha WHERE item_id=?", (iid,))
    con.execute("DELETE FROM itens WHERE id=?", (iid,))
    con.commit()
    con.close()


def listar_ficha(item_id):
    """Componentes do item, já com o custo calculado de cada linha."""
    con = conectar()
    linhas = con.execute("""
        SELECT f.id, f.insumo_id, ins.nome, f.quantidade, ins.unidade_uso,
               ins.preco_compra, ins.qtd_util
          FROM ficha f JOIN insumos ins ON ins.id = f.insumo_id
         WHERE f.item_id = ?
         ORDER BY ins.nome""", (item_id,)).fetchall()
    con.close()
    saida = []
    for fid, insumo_id, nome, qtd, un_uso, preco, qtd_util in linhas:
        cu = custo_unitario(preco, qtd_util)
        saida.append({"ficha_id": fid, "insumo_id": insumo_id, "insumo": nome,
                      "quantidade": qtd, "unidade": un_uso,
                      "custo_unitario": cu, "custo": cu * (qtd or 0)})
    return saida


def salvar_componente(item_id, insumo_id, quantidade):
    con = conectar()
    con.execute(
        "INSERT INTO ficha (item_id, insumo_id, quantidade) VALUES (?,?,?)"
        " ON CONFLICT(item_id, insumo_id) DO UPDATE SET quantidade=excluded.quantidade",
        (item_id, insumo_id, quantidade))
    con.commit()
    con.close()


def excluir_componente(ficha_id):
    con = conectar()
    con.execute("DELETE FROM ficha WHERE id=?", (ficha_id,))
    con.commit()
    con.close()


def custo_do_item(item_id) -> float:
    return sum(c["custo"] for c in listar_ficha(item_id))


def custos_por_item():
    """{item_id: custo da ficha} — o cardápio inteiro em uma consulta só."""
    con = conectar()
    linhas = con.execute("""
        SELECT f.item_id,
               SUM(f.quantidade * ins.preco_compra /
                   CASE WHEN ins.qtd_util > 0 THEN ins.qtd_util END)
          FROM ficha f JOIN insumos ins ON ins.id = f.insumo_id
         GROUP BY f.item_id""").fetchall()
    con.close()
    return {iid: float(custo or 0.0) for iid, custo in linhas}


def analise_itens():
    """Custo, preço, margem, CMV e situação de cada item do cardápio.

    'situacao' diz o que ainda falta preencher; enquanto faltar, o item entra
    como 'sem_dado' e fica fora do ranking de margem.
    """
    custos = custos_por_item()
    resultado = []
    for iid, nome, categoria, preco, _obs in listar_itens():
        custo = custos.get(iid, 0.0)
        preco = float(preco or 0)
        margem = preco - custo
        cmv = (custo / preco * 100) if preco else 0.0
        if preco <= 0:
            situacao = "falta o preço de venda"
        elif custo <= 0:
            situacao = "falta montar a ficha"
        else:
            situacao = ""
        completo = not situacao
        resultado.append({"id": iid, "nome": nome, "categoria": categoria,
                          "custo": custo, "preco": preco, "margem": margem,
                          "margem_pct": (margem / preco * 100) if preco else 0.0,
                          "cmv": cmv, "completo": completo,
                          "situacao": situacao,
                          "faixa": faixa_cmv(cmv, completo)})
    return resultado


def simular_preco_insumo(insumo_id, novo_preco):
    """Como fica o cardápio se este insumo passar a custar outro preço.

    Responde a pergunta mais valiosa do programa — "a carne subiu, quais
    pratos ficaram com lucro ruim?" — sem gravar nada no banco.
    Devolve uma linha por item que usa o insumo, com o antes e o depois,
    do pior resultado para o melhor.
    """
    ins = obter_insumo(insumo_id)
    if not ins:
        return []
    _id, _nome, _un_compra, preco_atual, unidade_uso, qtd_util, _forn, _atu = ins
    cu_antes = custo_unitario(preco_atual, qtd_util)
    cu_depois = custo_unitario(novo_preco, qtd_util)
    delta = cu_depois - cu_antes

    con = conectar()
    linhas = con.execute(
        "SELECT f.item_id, i.nome, i.categoria, i.preco_venda, f.quantidade"
        "  FROM ficha f JOIN itens i ON i.id = f.item_id"
        " WHERE f.insumo_id = ?", (insumo_id,)).fetchall()
    con.close()

    custos = custos_por_item()
    saida = []
    for item_id, nome, categoria, preco_venda, qtd in linhas:
        preco_venda = float(preco_venda or 0)
        custo_antes = custos.get(item_id, 0.0)
        custo_depois = custo_antes + delta * float(qtd or 0)
        completo_antes = preco_venda > 0 and custo_antes > 0
        completo_depois = preco_venda > 0 and custo_depois > 0
        cmv_antes = (custo_antes / preco_venda * 100) if preco_venda else 0.0
        cmv_depois = (custo_depois / preco_venda * 100) if preco_venda else 0.0
        faixa_antes = faixa_cmv(cmv_antes, completo_antes)
        faixa_depois = faixa_cmv(cmv_depois, completo_depois)
        saida.append({"id": item_id, "nome": nome, "categoria": categoria,
                      "preco": preco_venda, "quantidade": float(qtd or 0),
                      "unidade": unidade_uso,
                      "custo_antes": custo_antes, "custo_depois": custo_depois,
                      "margem_antes": preco_venda - custo_antes,
                      "margem_depois": preco_venda - custo_depois,
                      "cmv_antes": cmv_antes, "cmv_depois": cmv_depois,
                      "faixa_antes": faixa_antes, "faixa_depois": faixa_depois,
                      "piorou": faixa_depois == "ruim" and faixa_antes != "ruim"})
    saida.sort(key=lambda l: (0 if l["cmv_depois"] else 1, -l["cmv_depois"],
                              l["nome"].lower()))
    return saida


def custo_unitario_do_insumo(insumo_id) -> float:
    """Custo real de 1 unidade de uso do insumo, como está gravado hoje."""
    ins = obter_insumo(insumo_id)
    return custo_unitario(ins[3], ins[5]) if ins else 0.0


def itens_que_usam(insumo_id):
    """Itens do cardápio afetados por uma mudança de preço deste insumo."""
    con = conectar()
    linhas = con.execute(
        "SELECT DISTINCT i.id, i.nome FROM ficha f JOIN itens i ON i.id=f.item_id"
        " WHERE f.insumo_id=? ORDER BY i.nome", (insumo_id,)).fetchall()
    con.close()
    return linhas
