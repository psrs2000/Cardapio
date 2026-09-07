"""
Camada de dados do Cardápio — SQLite puro, sem dependência de interface.

Modelo (o coração do programa):

    insumo → preço de compra ÷ quantidade útil = CUSTO UNITÁRIO REAL

Esse único conceito resolve todos os casos do estabelecimento — inclusive a
mão de obra, que é a mesma conta:

    carne     : 1 kg por R$ 32,00  rende 700 g       → R$ 0,0457 por g
    cachaça   : 1 garrafa R$ 25,00 rende 20 doses    → R$ 1,25 por dose
    long neck : 1 un por R$ 4,10   rende 1 un        → R$ 4,10 por un
    montador  : 1 dia por R$ 100   monta 50 pratos   → R$ 2,00 por prato

A "quantidade útil" já embute a perda (limpeza, cozimento, espuma do chopp).
Por isso mão de obra NÃO tem tabela própria: é uma linha de `insumos` com
tipo = 'Mão de obra', e entra na ficha técnica como qualquer ingrediente.
O que muda é só a leitura: o CMV continua sendo dos insumos (para bater com
a régua de 30–35% do ramo) e a mão de obra sai do lucro.
"""

import os
import sqlite3
import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cardapio.db")

# os dois tipos de custo — mesma tabela, mesma conta, leitura diferente
TIPO_INSUMO = "Insumo"
TIPO_MAO_OBRA = "Mão de obra"
TIPOS = [TIPO_INSUMO, TIPO_MAO_OBRA]

# os dois campos de unidade de um cadastro
CAMPO_COMPRA = "compra"
CAMPO_USO = "uso"
COLUNA_DO_CAMPO = {CAMPO_COMPRA: "unidade_compra", CAMPO_USO: "unidade_uso"}

# listas de fábrica — servem só para semear a tabela na primeira execução;
# daí em diante quem manda é o que o dono cadastrou em `unidades`
UNIDADES_COMPRA = ["kg", "g", "L", "ml", "un", "garrafa", "barril", "caixa",
                   "pacote", "maço", "dúzia"]
UNIDADES_USO = ["g", "ml", "un", "dose", "copo", "fatia", "porção"]

# mão de obra: compra-se tempo e "rende" itens prontos
UNIDADES_COMPRA_MO = ["dia", "hora", "turno", "semana", "mês", "serviço"]
UNIDADES_USO_MO = ["prato", "porção", "un", "item", "kg", "hora"]

UNIDADES_DE_FABRICA = {
    (TIPO_INSUMO, CAMPO_COMPRA): UNIDADES_COMPRA,
    (TIPO_INSUMO, CAMPO_USO): UNIDADES_USO,
    (TIPO_MAO_OBRA, CAMPO_COMPRA): UNIDADES_COMPRA_MO,
    (TIPO_MAO_OBRA, CAMPO_USO): UNIDADES_USO_MO,
}


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
            atualizado_em  TEXT    DEFAULT '',
            tipo           TEXT    NOT NULL DEFAULT 'Insumo'
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
    con.execute("""
        CREATE TABLE IF NOT EXISTS unidades (
            id    INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo  TEXT    NOT NULL,
            campo TEXT    NOT NULL,
            nome  TEXT    NOT NULL,
            ordem INTEGER NOT NULL DEFAULT 0,
            UNIQUE(tipo, campo, nome)
        )""")
    # primeira execução: as listas de fábrica viram dados que o dono edita
    for (tipo, campo), nomes in UNIDADES_DE_FABRICA.items():
        ja_tem = con.execute("SELECT COUNT(*) FROM unidades WHERE tipo=? AND campo=?",
                             (tipo, campo)).fetchone()[0]
        if not ja_tem:
            con.executemany(
                "INSERT INTO unidades (tipo, campo, nome, ordem) VALUES (?,?,?,?)",
                [(tipo, campo, nome, i) for i, nome in enumerate(nomes)])

    # banco criado antes da mão de obra: ganha a coluna sem perder nada
    colunas = [c[1] for c in con.execute("PRAGMA table_info(insumos)")]
    if "tipo" not in colunas:
        con.execute("ALTER TABLE insumos ADD COLUMN tipo TEXT NOT NULL"
                    " DEFAULT '%s'" % TIPO_INSUMO)
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


# ── unidades (o dono cadastra as dele) ────────────────────────────
def listar_unidades(tipo, campo):
    con = conectar()
    linhas = con.execute(
        "SELECT nome FROM unidades WHERE tipo=? AND campo=? ORDER BY ordem, nome",
        (tipo, campo)).fetchall()
    con.close()
    return [l[0] for l in linhas]


def unidades_de(tipo):
    """(unidades de compra, unidades de uso) conforme o tipo de custo."""
    return listar_unidades(tipo, CAMPO_COMPRA), listar_unidades(tipo, CAMPO_USO)


def adicionar_unidade(tipo, campo, nome):
    """Cria uma unidade. Devolve False se o nome já existe."""
    nome = (nome or "").strip()
    if not nome:
        return False
    con = conectar()
    try:
        ordem = con.execute(
            "SELECT COALESCE(MAX(ordem), 0) + 1 FROM unidades WHERE tipo=? AND campo=?",
            (tipo, campo)).fetchone()[0]
        con.execute("INSERT INTO unidades (tipo, campo, nome, ordem) VALUES (?,?,?,?)",
                    (tipo, campo, nome, ordem))
        con.commit()
    except sqlite3.IntegrityError:
        return False
    finally:
        con.close()
    return True


def renomear_unidade(tipo, campo, antigo, novo):
    """Renomeia a unidade e corrige quem já a usava — ninguém fica órfão."""
    novo = (novo or "").strip()
    if not novo or novo == antigo:
        return False
    coluna = COLUNA_DO_CAMPO[campo]
    con = conectar()
    try:
        con.execute("UPDATE unidades SET nome=? WHERE tipo=? AND campo=? AND nome=?",
                    (novo, tipo, campo, antigo))
        con.execute(f"UPDATE insumos SET {coluna}=? WHERE tipo=? AND {coluna}=?",
                    (novo, tipo, antigo))
        con.commit()
    except sqlite3.IntegrityError:
        return False
    finally:
        con.close()
    return True


def unidade_em_uso(tipo, campo, nome):
    """Cadastros que usam esta unidade — vazio quer dizer que dá para excluir."""
    coluna = COLUNA_DO_CAMPO[campo]
    con = conectar()
    linhas = con.execute(
        f"SELECT nome FROM insumos WHERE tipo=? AND {coluna}=? ORDER BY nome",
        (tipo, nome)).fetchall()
    con.close()
    return [l[0] for l in linhas]


def excluir_unidade(tipo, campo, nome):
    """Exclui a unidade se ninguém a estiver usando (devolve quem usa)."""
    usos = unidade_em_uso(tipo, campo, nome)
    if usos:
        return usos
    con = conectar()
    con.execute("DELETE FROM unidades WHERE tipo=? AND campo=? AND nome=?",
                (tipo, campo, nome))
    con.commit()
    con.close()
    return []


# ── faixas de CMV ─────────────────────────────────────────────────
# CMV = quanto de cada real vendido vai embora só em insumo.
# No ramo, até ~35% é saudável; acima de 45% o item quase não dá lucro.
CMV_BOM = 35.0
CMV_ATENCAO = 45.0

# CMV com mão de obra (o "custo primário") = insumos + mão de obra sobre o
# preço de venda. É ESTE número que dá a cor do item: é o que sobra de verdade.
# A régua é mais folgada que a do CMV puro porque agora a conta inclui a gente
# que faz — no ramo trabalha-se com algo em torno de 60%; acima de 70% o item
# não se paga. Mexa aqui se a realidade da casa for outra: é o único lugar
# onde esses números existem.
CUSTO_TOTAL_BOM = 60.0
CUSTO_TOTAL_ATENCAO = 70.0

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


def faixa_cmv_total(cmv_total, tem_dados=True) -> str:
    """Mesma ideia do CMV, na régua do CMV com mão de obra."""
    if not tem_dados:
        return "sem_dado"
    if cmv_total <= CUSTO_TOTAL_BOM:
        return "bom"
    if cmv_total <= CUSTO_TOTAL_ATENCAO:
        return "atencao"
    return "ruim"


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
def listar_insumos(tipo=None):
    """Todos os custos cadastrados, ou só os de um tipo (Insumo / Mão de obra)."""
    con = conectar()
    sql = ("SELECT id, nome, unidade_compra, preco_compra, unidade_uso, qtd_util,"
           " fornecedor, atualizado_em, tipo FROM insumos")
    if tipo:
        linhas = con.execute(sql + " WHERE tipo=? ORDER BY nome", (tipo,)).fetchall()
    else:
        linhas = con.execute(sql + " ORDER BY tipo, nome").fetchall()
    con.close()
    return linhas


def obter_insumo(iid):
    con = conectar()
    r = con.execute(
        "SELECT id, nome, unidade_compra, preco_compra, unidade_uso, qtd_util,"
        " fornecedor, atualizado_em, tipo FROM insumos WHERE id=?",
        (iid,)).fetchone()
    con.close()
    return r


def salvar_insumo(iid, nome, unidade_compra, preco_compra, unidade_uso,
                  qtd_util, fornecedor="", tipo=TIPO_INSUMO):
    """Insere (iid=None) ou atualiza um insumo ou mão de obra. Devolve o id."""
    agora = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    con = conectar()
    try:
        if iid:
            con.execute(
                "UPDATE insumos SET nome=?, unidade_compra=?, preco_compra=?,"
                " unidade_uso=?, qtd_util=?, fornecedor=?, atualizado_em=?,"
                " tipo=? WHERE id=?",
                (nome, unidade_compra, preco_compra, unidade_uso, qtd_util,
                 fornecedor, agora, tipo, iid))
        else:
            cur = con.execute(
                "INSERT INTO insumos (nome, unidade_compra, preco_compra,"
                " unidade_uso, qtd_util, fornecedor, atualizado_em, tipo)"
                " VALUES (?,?,?,?,?,?,?,?)",
                (nome, unidade_compra, preco_compra, unidade_uso, qtd_util,
                 fornecedor, agora, tipo))
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
               ins.preco_compra, ins.qtd_util, ins.tipo
          FROM ficha f JOIN insumos ins ON ins.id = f.insumo_id
         WHERE f.item_id = ?
         ORDER BY ins.tipo, ins.nome""", (item_id,)).fetchall()
    con.close()
    saida = []
    for fid, insumo_id, nome, qtd, un_uso, preco, qtd_util, tipo in linhas:
        cu = custo_unitario(preco, qtd_util)
        saida.append({"ficha_id": fid, "insumo_id": insumo_id, "insumo": nome,
                      "quantidade": qtd, "unidade": un_uso, "tipo": tipo,
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


def custos_do_item(item_id):
    """{'insumos': x, 'mao_obra': y, 'total': x + y} de um item."""
    parcial = {"insumos": 0.0, "mao_obra": 0.0}
    for c in listar_ficha(item_id):
        alvo = "mao_obra" if c["tipo"] == TIPO_MAO_OBRA else "insumos"
        parcial[alvo] += c["custo"]
    parcial["total"] = parcial["insumos"] + parcial["mao_obra"]
    return parcial


def custo_do_item(item_id) -> float:
    """Custo total do item — insumos mais mão de obra."""
    return custos_do_item(item_id)["total"]


def custos_por_item():
    """{item_id: {'insumos','mao_obra','total'}} — o cardápio em uma consulta."""
    con = conectar()
    linhas = con.execute("""
        SELECT f.item_id, ins.tipo,
               SUM(f.quantidade * ins.preco_compra /
                   CASE WHEN ins.qtd_util > 0 THEN ins.qtd_util END)
          FROM ficha f JOIN insumos ins ON ins.id = f.insumo_id
         GROUP BY f.item_id, ins.tipo""").fetchall()
    con.close()
    saida = {}
    for iid, tipo, custo in linhas:
        p = saida.setdefault(iid, {"insumos": 0.0, "mao_obra": 0.0, "total": 0.0})
        alvo = "mao_obra" if tipo == TIPO_MAO_OBRA else "insumos"
        p[alvo] += float(custo or 0.0)
        p["total"] = p["insumos"] + p["mao_obra"]
    return saida


def _zerado():
    return {"insumos": 0.0, "mao_obra": 0.0, "total": 0.0}


def avaliar(preco, custo_insumos, custo_mao_obra=0.0):
    """A régua do programa, num lugar só: como julgar um item.

    Dois números, cada um com a sua régua:

    - **CMV** — só insumos. Serve para comparar com os 30–35% que se falam no
      ramo. É informação, não é ele que dá a cor.
    - **CMV com mão de obra** — insumos + quem faz, sobre o preço. É o número
      realista, e é ele que decide 🟢🟡🔴. Foi decisão do dono: uma bebida de
      revenda tem CMV alto e nenhuma mão de obra, e nem por isso é um mau
      negócio; um prato barato de insumo pode dar trabalho demais e não pagar
      a conta. Julgar pelos dois juntos põe cozinha e bar na mesma régua.
    """
    preco = float(preco or 0)
    custo_insumos = float(custo_insumos or 0)
    custo_mao_obra = float(custo_mao_obra or 0)
    total = custo_insumos + custo_mao_obra
    margem = preco - total
    cmv = (custo_insumos / preco * 100) if preco else 0.0
    cmv_total = (total / preco * 100) if preco else 0.0
    if preco <= 0:
        situacao, faixa = "falta o preço de venda", "sem_dado"
    elif total <= 0:
        situacao, faixa = "falta montar a ficha", "sem_dado"
    elif margem <= 0:
        situacao, faixa = "o preço não cobre o custo", "ruim"
    else:
        faixa = faixa_cmv_total(cmv_total)
        # quando o insumo está em dia e mesmo assim o item não vai bem,
        # quem está pesando é a mão de obra — vale dizer isso na tela
        situacao = ("a mão de obra pesa no custo"
                    if faixa != "bom" and custo_mao_obra > 0
                    and faixa_cmv(cmv) == "bom" else "")
    return {"custo_insumos": custo_insumos, "custo_mao_obra": custo_mao_obra,
            "custo": total, "preco": preco, "margem": margem,
            "margem_pct": (margem / preco * 100) if preco else 0.0,
            "cmv": cmv, "cmv_total": cmv_total, "faixa_insumos": faixa_cmv(cmv, preco > 0),
            "completo": faixa != "sem_dado", "situacao": situacao, "faixa": faixa}


def analise_itens():
    """Custo, preço, margem, CMV e situação de cada item do cardápio.

    'situacao' diz o que ainda falta preencher; enquanto faltar, o item entra
    como 'sem_dado' e fica fora do ranking de margem.
    """
    custos = custos_por_item()
    resultado = []
    for iid, nome, categoria, preco, _obs in listar_itens():
        c = custos.get(iid, _zerado())
        linha = {"id": iid, "nome": nome, "categoria": categoria}
        linha.update(avaliar(preco, c["insumos"], c["mao_obra"]))
        resultado.append(linha)
    return resultado


def simular_preco_insumo(insumo_id, novo_preco):
    """Como fica o cardápio se este custo passar a valer outro preço.

    Responde a pergunta mais valiosa do programa — "a carne subiu, quais
    pratos ficaram com lucro ruim?" — sem gravar nada no banco. Serve igual
    para mão de obra: "e se o montador passar a custar R$ 120 por dia?".
    Devolve uma linha por item afetado, com o antes e o depois, do pior
    resultado para o melhor.
    """
    ins = obter_insumo(insumo_id)
    if not ins:
        return []
    _id, _nome, _un_compra, preco_atual, unidade_uso, qtd_util, _forn, _atu, tipo = ins
    delta = custo_unitario(novo_preco, qtd_util) - custo_unitario(preco_atual, qtd_util)
    alvo = "mao_obra" if tipo == TIPO_MAO_OBRA else "insumos"

    con = conectar()
    linhas = con.execute(
        "SELECT f.item_id, i.nome, i.categoria, i.preco_venda, f.quantidade"
        "  FROM ficha f JOIN itens i ON i.id = f.item_id"
        " WHERE f.insumo_id = ?", (insumo_id,)).fetchall()
    con.close()

    custos = custos_por_item()
    saida = []
    for item_id, nome, categoria, preco_venda, qtd in linhas:
        c = custos.get(item_id, _zerado())
        depois = dict(c)
        depois[alvo] = c[alvo] + delta * float(qtd or 0)
        antes = avaliar(preco_venda, c["insumos"], c["mao_obra"])
        dep = avaliar(preco_venda, depois["insumos"], depois["mao_obra"])
        saida.append({"id": item_id, "nome": nome, "categoria": categoria,
                      "preco": antes["preco"], "quantidade": float(qtd or 0),
                      "unidade": unidade_uso, "tipo": tipo,
                      "custo_antes": antes["custo"], "custo_depois": dep["custo"],
                      "margem_antes": antes["margem"], "margem_depois": dep["margem"],
                      "cmv_antes": antes["cmv"], "cmv_depois": dep["cmv"],
                      "cmv_total_antes": antes["cmv_total"],
                      "cmv_total_depois": dep["cmv_total"],
                      "faixa_antes": antes["faixa"], "faixa_depois": dep["faixa"],
                      "piorou": dep["faixa"] == "ruim" and antes["faixa"] != "ruim"})
    saida.sort(key=lambda l: (0 if l["margem_depois"] else 1, l["margem_depois"],
                              l["nome"].lower()))
    return saida


def custo_unitario_do_insumo(insumo_id) -> float:
    """Custo real de 1 unidade de uso do insumo, como está gravado hoje."""
    ins = obter_insumo(insumo_id)
    return custo_unitario(ins[3], ins[5]) if ins else 0.0


def itens_com_mao_de_obra(insumo_id=None):
    """Quantos itens do cardápio já têm mão de obra lançada na ficha."""
    con = conectar()
    n = con.execute(
        "SELECT COUNT(DISTINCT f.item_id) FROM ficha f"
        "  JOIN insumos ins ON ins.id = f.insumo_id"
        " WHERE ins.tipo = ?", (TIPO_MAO_OBRA,)).fetchone()[0]
    con.close()
    return n


def itens_que_usam(insumo_id):
    """Itens do cardápio afetados por uma mudança de preço deste insumo."""
    con = conectar()
    linhas = con.execute(
        "SELECT DISTINCT i.id, i.nome FROM ficha f JOIN itens i ON i.id=f.item_id"
        " WHERE f.insumo_id=? ORDER BY i.nome", (insumo_id,)).fetchall()
    con.close()
    return linhas
