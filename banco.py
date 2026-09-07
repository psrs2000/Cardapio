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


def analise_itens():
    """Custo, preço, margem e CMV de cada item do cardápio."""
    resultado = []
    for iid, nome, categoria, preco, _obs in listar_itens():
        custo = custo_do_item(iid)
        preco = float(preco or 0)
        margem = preco - custo
        cmv = (custo / preco * 100) if preco else 0.0
        resultado.append({"id": iid, "nome": nome, "categoria": categoria,
                          "custo": custo, "preco": preco, "margem": margem,
                          "margem_pct": (margem / preco * 100) if preco else 0.0,
                          "cmv": cmv})
    return resultado


def itens_que_usam(insumo_id):
    """Itens do cardápio afetados por uma mudança de preço deste insumo."""
    con = conectar()
    linhas = con.execute(
        "SELECT DISTINCT i.id, i.nome FROM ficha f JOIN itens i ON i.id=f.item_id"
        " WHERE f.insumo_id=? ORDER BY i.nome", (insumo_id,)).fetchall()
    con.close()
    return linhas
