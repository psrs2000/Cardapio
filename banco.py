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
    purê      : 1 receita R$ 21,10  rende 2.200 g     → R$ 0,0096 por g

A "quantidade útil" já embute a perda (limpeza, cozimento, espuma do chopp).
Por isso mão de obra NÃO tem tabela própria: é uma linha de `insumos` com
tipo = 'Mão de obra', e entra na ficha técnica como qualquer ingrediente.

O FEITO NA CASA (purê, molho, farofa — o que a casa produz e usa em vários
pratos; no código, "preparo")
segue exatamente a mesma fórmula; o que muda é de onde vem o preço: em vez de
digitado, ele é a soma da ficha do próprio preparo. Um preparo é, portanto,
uma linha de `insumos` com tipo = 'Feito na casa', cuja ficha mora em
`ficha_preparo` e cujo `preco_compra` é calculado, nunca digitado.
O que muda é só a leitura: o CMV continua sendo dos insumos (para bater com
a régua de 30–35% do ramo) e a mão de obra sai do lucro.
"""

import os
import re
import sys
import json
import shutil
import hashlib
import sqlite3
import datetime


def _app_dir() -> str:
    """Pasta do .exe (quando compilado) ou do .py (em desenvolvimento).

    Mesma solução do projeto Fluxo de Caixa: sem isto, o programa distribuído
    como .exe procuraria o banco na pasta temporária do PyInstaller.
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


DB_PATH = os.path.join(_app_dir(), "cardapio.db")

# Senha e backup ficam em config.json, fora do banco, porque são configuração
# da instalação e não do cardápio: têm de continuar valendo mesmo se o .db for
# substituído por um backup. (Os limites de cor, esses sim, são do cardápio e
# moram na tabela `config`, viajando junto no backup.)
CFG_PATH = os.path.join(_app_dir(), "config.json")

# quantos backups automáticos guardar antes de apagar os mais antigos
MAX_BACKUPS = 10

# os dois tipos de custo — mesma tabela, mesma conta, leitura diferente
TIPO_INSUMO = "Insumo"
TIPO_PREPARO = "Feito na casa"
TIPO_MAO_OBRA = "Mão de obra"
TIPOS = [TIPO_INSUMO, TIPO_PREPARO, TIPO_MAO_OBRA]

# a "compra" de um preparo é sempre uma receita dele; não se digita
UNIDADE_COMPRA_PREPARO = "receita"

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

# preparo: compra-se uma receita e ela "rende" o que sai da panela
UNIDADES_USO_PREPARO = ["g", "ml", "un", "porção", "fatia", "concha"]

UNIDADES_DE_FABRICA = {
    (TIPO_INSUMO, CAMPO_COMPRA): UNIDADES_COMPRA,
    (TIPO_INSUMO, CAMPO_USO): UNIDADES_USO,
    (TIPO_MAO_OBRA, CAMPO_COMPRA): UNIDADES_COMPRA_MO,
    (TIPO_MAO_OBRA, CAMPO_USO): UNIDADES_USO_MO,
    (TIPO_PREPARO, CAMPO_COMPRA): [UNIDADE_COMPRA_PREPARO],
    (TIPO_PREPARO, CAMPO_USO): UNIDADES_USO_PREPARO,
}


CATEGORIAS = ["Prato", "Porção", "Bebida", "Sobremesa", "Outro"]


# ── configuração da instalação (config.json) ──────────────────────
def cfg_load() -> dict:
    try:
        with open(CFG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def cfg_save(dados: dict):
    try:
        atual = cfg_load()
        atual.update(dados)
        with open(CFG_PATH, "w", encoding="utf-8") as f:
            json.dump(atual, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def cfg_remover(chave):
    atual = cfg_load()
    if atual.pop(chave, None) is None:
        return
    try:
        with open(CFG_PATH, "w", encoding="utf-8") as f:
            json.dump(atual, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


# ── senha de acesso ───────────────────────────────────────────────
TAMANHO_MINIMO_SENHA = 4


def _hash_senha(senha: str, salt: str) -> str:
    return hashlib.sha256((salt + senha).encode("utf-8")).hexdigest()


def senha_ativa() -> bool:
    return bool(cfg_load().get("auth"))


def definir_senha(senha, confirmacao) -> str:
    """Grava a senha. Devolve a mensagem de erro, ou '' se deu certo.

    Guarda só o resumo (SHA-256 com salt aleatório) — a senha em si não fica
    escrita em lugar nenhum. Se ele esquecer, não há como recuperar: apagar o
    config.json devolve o acesso, e é isso que a tela avisa.
    """
    if not senha:
        return "Digite a nova senha."
    if senha != confirmacao:
        return "As senhas não coincidem."
    if len(senha) < TAMANHO_MINIMO_SENHA:
        return f"A senha deve ter ao menos {TAMANHO_MINIMO_SENHA} caracteres."
    salt = os.urandom(16).hex()
    cfg_save({"auth": {"salt": salt, "hash": _hash_senha(senha, salt)}})
    return ""


def remover_senha():
    cfg_remover("auth")


def conferir_senha(senha) -> bool:
    auth = cfg_load().get("auth")
    if not auth:
        return True
    return _hash_senha(senha or "", auth.get("salt", "")) == auth.get("hash", "")


# ── backup ────────────────────────────────────────────────────────
def pasta_backup_auto() -> str:
    return cfg_load().get("backup_auto_dir") or os.path.join(
        os.path.dirname(DB_PATH), "backups")


def backup_automatico_ligado() -> bool:
    return bool(cfg_load().get("backup_auto"))


def ligar_backup_automatico(ligado):
    cfg_save({"backup_auto": bool(ligado)})


def definir_pasta_backup_auto(pasta):
    cfg_save({"backup_auto_dir": pasta})


def nome_sugerido_backup() -> str:
    return f"backup_cardapio_{datetime.datetime.now():%Y%m%d_%H%M%S}.db"


def fazer_backup(destino):
    """Cópia do banco para onde o dono escolher. Devolve erro ou ''."""
    try:
        shutil.copy2(DB_PATH, destino)
        cfg_save({"backup_dir": os.path.dirname(destino)})
        return ""
    except Exception as e:
        return str(e)


def listar_backups():
    """Backups automáticos existentes, do mais novo para o mais antigo."""
    pasta = pasta_backup_auto()
    try:
        return sorted((f for f in os.listdir(pasta)
                       if f.startswith("backup_auto_") and f.endswith(".db")),
                      reverse=True)
    except OSError:
        return []


def fazer_backup_automatico() -> str:
    """Copia o banco para a pasta de backups, guardando os mais recentes.

    Roda ao fechar o programa: é silenciosa e nunca levanta exceção — um erro
    de backup não pode impedir o programa de fechar. Devolve o caminho gravado
    (ou '' se não fez nada), só para quem quiser mostrar.
    """
    try:
        if not backup_automatico_ligado() or not os.path.isfile(DB_PATH):
            return ""
        pasta = pasta_backup_auto()
        os.makedirs(pasta, exist_ok=True)
        base = f"backup_auto_{datetime.datetime.now():%Y%m%d_%H%M%S}"
        destino = os.path.join(pasta, base + ".db")
        # dois backups no mesmo segundo não podem se sobrescrever
        n = 2
        while os.path.exists(destino):
            destino = os.path.join(pasta, f"{base}_{n}.db")
            n += 1
        shutil.copy2(DB_PATH, destino)
        # rotação pelo NOME, que carrega a data/hora: copy2 preserva a data do
        # arquivo de origem, então ordenar por data de modificação não serve
        for antigo in listar_backups()[MAX_BACKUPS:]:
            try:
                os.remove(os.path.join(pasta, antigo))
            except OSError:
                pass
        return destino
    except Exception:
        return ""


def conectar():
    con = sqlite3.connect(DB_PATH)
    con.execute("PRAGMA foreign_keys = ON")
    return con


def init_db():
    global _limites_em_memoria
    _limites_em_memoria = None
    con = conectar()
    con.execute("""
        CREATE TABLE IF NOT EXISTS ficha_preparo (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            preparo_id INTEGER NOT NULL REFERENCES insumos(id) ON DELETE CASCADE,
            insumo_id  INTEGER NOT NULL REFERENCES insumos(id) ON DELETE RESTRICT,
            quantidade REAL    NOT NULL DEFAULT 0,
            UNIQUE(preparo_id, insumo_id)
        )""")
    con.execute("""
        CREATE TABLE IF NOT EXISTS config (
            chave TEXT PRIMARY KEY,
            valor TEXT
        )""")
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
    recalcular_preparos()


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


# "2.500" é dois mil e quinhentos, não dois e meio: ponto separando grupos de
# exatamente três dígitos é separador de milhar no padrão brasileiro.
_MILHAR = re.compile(r"^\d{1,3}(\.\d{3})+$")


def parse_num(texto) -> float:
    """Aceita '1.234,56', '2.500', '1234.56' e '2,5'."""
    s = str(texto).strip().replace("R$", "").replace(" ", "")
    if not s:
        return 0.0
    negativo = s.startswith("-")
    s = s.lstrip("-+")
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".") if s.rindex(",") > s.rindex(".") \
            else s.replace(",", "")
    elif _MILHAR.match(s):
        s = s.replace(".", "")
    else:
        s = s.replace(",", ".")
    return -float(s) if negativo else float(s)


def fmt_num_edicao(v, casas=3) -> str:
    """Número para DENTRO de um campo de digitação: sem ponto de milhar.

    O campo tem de devolver, ao ser lido de novo, exatamente o que mostra —
    senão o dono abre um cadastro, clica em Atualizar e grava outro valor.
    """
    try:
        v = float(v)
    except (TypeError, ValueError):
        return ""
    s = f"{v:.{casas}f}".rstrip("0").rstrip(".")
    return (s or "0").replace(".", ",")


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
# não se paga.
CUSTO_TOTAL_BOM = 60.0
CUSTO_TOTAL_ATENCAO = 70.0

# Os quatro números acima são só o PADRÃO DE FÁBRICA. Quem manda é o gestor:
# cada casa tem a sua realidade, e ele edita os limites pela tela (Análise →
# "Limites das cores"), que grava na tabela `config`.
PADROES_LIMITES = {
    "cmv_bom": CMV_BOM,
    "cmv_atencao": CMV_ATENCAO,
    "cmv_total_bom": CUSTO_TOTAL_BOM,
    "cmv_total_atencao": CUSTO_TOTAL_ATENCAO,
}

ROTULOS_LIMITES = {
    "cmv_bom": "CMV — até quanto é verde",
    "cmv_atencao": "CMV — até quanto é amarelo",
    "cmv_total_bom": "CMV com mão de obra — até quanto é verde",
    "cmv_total_atencao": "CMV com mão de obra — até quanto é amarelo",
}

_limites_em_memoria = None


def limites():
    """Os quatro limites de cor em vigor — os do gestor, ou os de fábrica."""
    global _limites_em_memoria
    if _limites_em_memoria is None:
        atual = dict(PADROES_LIMITES)
        try:
            con = conectar()
            for chave, valor in con.execute("SELECT chave, valor FROM config"):
                if chave in atual:
                    try:
                        atual[chave] = float(valor)
                    except (TypeError, ValueError):
                        pass
            con.close()
        except sqlite3.Error:
            pass                      # banco ainda não criado: usa o padrão
        _limites_em_memoria = atual
    return _limites_em_memoria


def validar_limites(novos):
    """Devolve a lista de problemas — vazia quer dizer que dá para salvar."""
    erros = []
    for chave in PADROES_LIMITES:
        v = novos.get(chave)
        if v is None or v <= 0 or v >= 100:
            erros.append(f"{ROTULOS_LIMITES[chave]}: informe um número"
                         " entre 1 e 99.")
    if erros:
        return erros
    if novos["cmv_bom"] >= novos["cmv_atencao"]:
        erros.append("No CMV, o limite do verde tem de ser menor que o do"
                     " amarelo.")
    if novos["cmv_total_bom"] >= novos["cmv_total_atencao"]:
        erros.append("No CMV com mão de obra, o limite do verde tem de ser"
                     " menor que o do amarelo.")
    return erros


def salvar_limites(novos):
    """Grava os limites do gestor. Devolve a lista de problemas (vazia = ok)."""
    global _limites_em_memoria
    erros = validar_limites(novos)
    if erros:
        return erros
    con = conectar()
    con.executemany(
        "INSERT INTO config (chave, valor) VALUES (?,?)"
        " ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor",
        [(chave, str(novos[chave])) for chave in PADROES_LIMITES])
    con.commit()
    con.close()
    _limites_em_memoria = None
    return []


def restaurar_limites():
    """Volta aos números de fábrica."""
    global _limites_em_memoria
    con = conectar()
    con.execute("DELETE FROM config WHERE chave IN (%s)" %
                ",".join("?" * len(PADROES_LIMITES)), tuple(PADROES_LIMITES))
    con.commit()
    con.close()
    _limites_em_memoria = None
    return dict(PADROES_LIMITES)

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
    lim = limites()
    if cmv_total <= lim["cmv_total_bom"]:
        return "bom"
    if cmv_total <= lim["cmv_total_atencao"]:
        return "atencao"
    return "ruim"


def faixa_cmv(cmv, tem_dados=True) -> str:
    """Classifica o CMV em 'bom', 'atencao', 'ruim' ou 'sem_dado'.

    Sem preço de venda ou sem ficha técnica não dá para julgar o item —
    mostrar 0% de CMV nesse caso enganaria o usuário. Os limites são os que o
    gestor definiu na tela (veja `limites`).
    """
    if not tem_dados:
        return "sem_dado"
    lim = limites()
    if cmv <= lim["cmv_bom"]:
        return "bom"
    if cmv <= lim["cmv_atencao"]:
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
        linhas = con.execute(
            sql + " ORDER BY CASE tipo WHEN ? THEN 0 WHEN ? THEN 1 ELSE 2 END,"
                  " nome", (TIPO_INSUMO, TIPO_PREPARO)).fetchall()
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
    if tipo != TIPO_PREPARO:
        recalcular_preparos()      # mudou um preço: o que leva ele muda junto
    return iid


def excluir_insumo(iid):
    """Não exclui o que está em uso — devolve onde está sendo usado.

    Olha os dois lugares: as fichas dos pratos e as receitas do "Feito na
    casa". A batata pode não estar em prato nenhum e ainda assim estar dentro
    do purê.
    """
    con = conectar()
    usos = [u[0] for u in con.execute(
        "SELECT i.nome FROM ficha f JOIN itens i ON i.id = f.item_id"
        " WHERE f.insumo_id=? ORDER BY i.nome", (iid,)).fetchall()]
    usos += [f"{u[0]} (Feito na casa)" for u in con.execute(
        "SELECT p.nome FROM ficha_preparo f JOIN insumos p ON p.id = f.preparo_id"
        " WHERE f.insumo_id=? ORDER BY p.nome", (iid,)).fetchall()]
    if usos:
        con.close()
        return usos
    con.execute("DELETE FROM ficha_preparo WHERE preparo_id=?", (iid,))
    con.execute("DELETE FROM insumos WHERE id=?", (iid,))
    con.commit()
    con.close()
    recalcular_preparos()
    return []


# ── o custo de tudo, resolvendo a cadeia ──────────────────────────
def _zerado_tipo():
    return {"insumos": 0.0, "mao_obra": 0.0}


def custos_unitarios(precos_novos=None):
    """{insumo_id: {'insumos': x, 'mao_obra': y}} — custo de UMA unidade de uso.

    É o coração do programa desde que existe "Feito na casa": o custo do purê
    sai da ficha dele, que pode conter outro preparo, que contém outro… Aqui a
    cadeia inteira é resolvida de uma vez, em memória.

    O custo vem separado em insumo e mão de obra o caminho todo. Sem isso, o
    cozinheiro lançado na ficha do purê chegaria ao prato disfarçado de
    ingrediente e sujaria o CMV — que existe justamente para medir insumo.

    `precos_novos` ({insumo_id: preço}) recalcula tudo como se aquele insumo
    custasse outra coisa: é o que faz a simulação enxergar "a batata subiu →
    o purê subiu → estes pratos pioraram".
    """
    precos_novos = precos_novos or {}
    con = conectar()
    linhas = {iid: (tipo, preco, qtd) for iid, tipo, preco, qtd in con.execute(
        "SELECT id, tipo, preco_compra, qtd_util FROM insumos")}
    componentes = {}
    for pid, iid, qtd in con.execute(
            "SELECT preparo_id, insumo_id, quantidade FROM ficha_preparo"):
        componentes.setdefault(pid, []).append((iid, qtd))
    con.close()

    pronto, calculando = {}, set()

    def custo(iid):
        if iid in pronto:
            return pronto[iid]
        if iid in calculando:
            # volta (A dentro de B dentro de A). A tela impede que se crie uma,
            # mas se um banco antigo trouxer, o programa devolve zero e segue
            # em frente em vez de travar calculando para sempre.
            return _zerado_tipo()
        tipo, preco, qtd_util = linhas.get(iid, (TIPO_INSUMO, 0, 0))
        if tipo == TIPO_PREPARO:
            calculando.add(iid)
            receita = _zerado_tipo()
            for comp_id, quantidade in componentes.get(iid, []):
                parcial = custo(comp_id)
                receita["insumos"] += parcial["insumos"] * (quantidade or 0)
                receita["mao_obra"] += parcial["mao_obra"] * (quantidade or 0)
            calculando.discard(iid)
            rende = float(qtd_util or 0)
            resultado = ({"insumos": receita["insumos"] / rende,
                          "mao_obra": receita["mao_obra"] / rende}
                         if rende > 0 else _zerado_tipo())
        else:
            unitario = custo_unitario(precos_novos.get(iid, preco), qtd_util)
            resultado = ({"insumos": 0.0, "mao_obra": unitario}
                         if tipo == TIPO_MAO_OBRA
                         else {"insumos": unitario, "mao_obra": 0.0})
        pronto[iid] = resultado
        return resultado

    return {iid: custo(iid) for iid in linhas}


def custo_da_receita(preparo_id, precos_novos=None):
    """O que sai da panela: quanto custa fazer UMA receita do preparo."""
    unitarios = custos_unitarios(precos_novos)
    total = _zerado_tipo()
    for comp_id, quantidade in _componentes_preparo(preparo_id):
        parcial = unitarios.get(comp_id, _zerado_tipo())
        total["insumos"] += parcial["insumos"] * (quantidade or 0)
        total["mao_obra"] += parcial["mao_obra"] * (quantidade or 0)
    total["total"] = total["insumos"] + total["mao_obra"]
    return total


def _componentes_preparo(preparo_id):
    con = conectar()
    linhas = con.execute(
        "SELECT insumo_id, quantidade FROM ficha_preparo WHERE preparo_id=?",
        (preparo_id,)).fetchall()
    con.close()
    return linhas


def recalcular_preparos():
    """Grava em `preco_compra` de cada preparo o custo de uma receita dele.

    O valor de verdade é sempre a soma da ficha; esta cópia existe só para as
    listas e combos mostrarem o número certo sem refazer a conta. Por isso é
    chamada depois de toda alteração — nunca deixe de chamar ao mexer em
    insumo, preço ou ficha de preparo.
    """
    unitarios = custos_unitarios()
    con = conectar()
    preparos = [r[0] for r in con.execute(
        "SELECT id FROM insumos WHERE tipo=?", (TIPO_PREPARO,))]
    componentes = {}
    for pid, iid, qtd in con.execute(
            "SELECT preparo_id, insumo_id, quantidade FROM ficha_preparo"):
        componentes.setdefault(pid, []).append((iid, qtd))
    for pid in preparos:
        total = sum((unitarios.get(cid, _zerado_tipo())["insumos"] +
                     unitarios.get(cid, _zerado_tipo())["mao_obra"]) * (q or 0)
                    for cid, q in componentes.get(pid, []))
        con.execute("UPDATE insumos SET preco_compra=? WHERE id=?", (total, pid))
    con.commit()
    con.close()


# ── ficha do "Feito na casa" ──────────────────────────────────────
def listar_ficha_preparo(preparo_id):
    """O que entra em uma receita do preparo, com o custo de cada linha."""
    con = conectar()
    linhas = con.execute("""
        SELECT f.id, f.insumo_id, ins.nome, f.quantidade, ins.unidade_uso, ins.tipo
          FROM ficha_preparo f JOIN insumos ins ON ins.id = f.insumo_id
         WHERE f.preparo_id = ?
         ORDER BY CASE ins.tipo WHEN ? THEN 0 WHEN ? THEN 1 ELSE 2 END, ins.nome
    """, (preparo_id, TIPO_INSUMO, TIPO_PREPARO)).fetchall()
    con.close()
    unitarios = custos_unitarios()
    saida = []
    for fid, insumo_id, nome, qtd, un_uso, tipo in linhas:
        parcial = unitarios.get(insumo_id, _zerado_tipo())
        cu = parcial["insumos"] + parcial["mao_obra"]
        saida.append({"ficha_id": fid, "insumo_id": insumo_id, "insumo": nome,
                      "quantidade": qtd, "unidade": un_uso, "tipo": tipo,
                      "custo_unitario": cu, "custo": cu * (qtd or 0),
                      "custo_insumos": parcial["insumos"] * (qtd or 0),
                      "custo_mao_obra": parcial["mao_obra"] * (qtd or 0)})
    return saida


def criaria_volta(preparo_id, componente_id) -> bool:
    """Pôr este componente dentro deste preparo faria uma volta?

    Purê dentro de molho dentro de purê: o custo passaria a depender de si
    mesmo. Barrado na hora de adicionar, que é onde dá para explicar.
    """
    if not preparo_id or componente_id == preparo_id:
        return True
    con = conectar()
    ligacoes = {}
    for pid, iid in con.execute("SELECT preparo_id, insumo_id FROM ficha_preparo"):
        ligacoes.setdefault(pid, []).append(iid)
    con.close()
    a_visitar, vistos = [componente_id], set()
    while a_visitar:
        atual = a_visitar.pop()
        if atual == preparo_id:
            return True
        if atual in vistos:
            continue
        vistos.add(atual)
        a_visitar.extend(ligacoes.get(atual, []))
    return False


def salvar_componente_preparo(preparo_id, insumo_id, quantidade):
    """Põe (ou corrige) um item na receita. Devolve erro, ou '' se deu certo."""
    if criaria_volta(preparo_id, insumo_id):
        return ("Isso faria uma volta: este item já depende do preparo que "
                "você está montando, e o custo passaria a depender de si mesmo.")
    con = conectar()
    con.execute(
        "INSERT INTO ficha_preparo (preparo_id, insumo_id, quantidade)"
        " VALUES (?,?,?) ON CONFLICT(preparo_id, insumo_id)"
        " DO UPDATE SET quantidade=excluded.quantidade",
        (preparo_id, insumo_id, quantidade))
    con.commit()
    con.close()
    recalcular_preparos()
    return ""


def excluir_componente_preparo(ficha_id):
    con = conectar()
    con.execute("DELETE FROM ficha_preparo WHERE id=?", (ficha_id,))
    con.commit()
    con.close()
    recalcular_preparos()


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
        SELECT f.id, f.insumo_id, ins.nome, f.quantidade, ins.unidade_uso, ins.tipo
          FROM ficha f JOIN insumos ins ON ins.id = f.insumo_id
         WHERE f.item_id = ?
         ORDER BY CASE ins.tipo WHEN ? THEN 0 WHEN ? THEN 1 ELSE 2 END, ins.nome
    """, (item_id, TIPO_INSUMO, TIPO_PREPARO)).fetchall()
    con.close()
    unitarios = custos_unitarios()
    saida = []
    for fid, insumo_id, nome, qtd, un_uso, tipo in linhas:
        parcial = unitarios.get(insumo_id, _zerado_tipo())
        cu = parcial["insumos"] + parcial["mao_obra"]
        saida.append({"ficha_id": fid, "insumo_id": insumo_id, "insumo": nome,
                      "quantidade": qtd, "unidade": un_uso, "tipo": tipo,
                      "custo_unitario": cu, "custo": cu * (qtd or 0),
                      "custo_insumos": parcial["insumos"] * (qtd or 0),
                      "custo_mao_obra": parcial["mao_obra"] * (qtd or 0)})
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
    """{'insumos': x, 'mao_obra': y, 'total': x + y} de um item.

    A mão de obra que veio de dentro de um preparo continua contada como mão
    de obra aqui — o purê chega ao prato já sabendo quanto dele é ingrediente
    e quanto é gente trabalhando.
    """
    parcial = {"insumos": 0.0, "mao_obra": 0.0}
    for c in listar_ficha(item_id):
        parcial["insumos"] += c["custo_insumos"]
        parcial["mao_obra"] += c["custo_mao_obra"]
    parcial["total"] = parcial["insumos"] + parcial["mao_obra"]
    return parcial


def custo_do_item(item_id) -> float:
    """Custo total do item — insumos mais mão de obra."""
    return custos_do_item(item_id)["total"]


def custos_por_item(precos_novos=None):
    """{item_id: {'insumos','mao_obra','total'}} — o cardápio inteiro de uma vez.

    `precos_novos` responde "como ficaria se este insumo custasse outra coisa",
    já atravessando os preparos que o usam.
    """
    unitarios = custos_unitarios(precos_novos)
    con = conectar()
    linhas = con.execute(
        "SELECT item_id, insumo_id, quantidade FROM ficha").fetchall()
    con.close()
    saida = {}
    for item_id, insumo_id, quantidade in linhas:
        parcial = unitarios.get(insumo_id, _zerado_tipo())
        p = saida.setdefault(item_id, _zerado())
        p["insumos"] += parcial["insumos"] * (quantidade or 0)
        p["mao_obra"] += parcial["mao_obra"] * (quantidade or 0)
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
    para mão de obra ("e se o montador passar a custar R$ 120 por dia?") e
    atravessa o "Feito na casa": a batata sobe, o purê sobe junto, e os pratos
    que levam purê aparecem aqui mesmo sem ter batata na ficha.

    Devolve uma linha por item afetado, do pior resultado para o melhor, com
    `direto` e `por` dizendo se a mudança chegou direto ou por um preparo.
    """
    ins = obter_insumo(insumo_id)
    if not ins:
        return []
    unidade_uso, tipo = ins[4], ins[8]

    antes_un = custos_unitarios()
    depois_un = custos_unitarios({insumo_id: novo_preco})
    antes_itens = custos_por_item()
    depois_itens = custos_por_item({insumo_id: novo_preco})

    def mudou(comp_id):
        a, d = antes_un.get(comp_id, _zerado_tipo()), depois_un.get(comp_id, _zerado_tipo())
        return abs((a["insumos"] + a["mao_obra"]) - (d["insumos"] + d["mao_obra"])) > 1e-12

    con = conectar()
    itens = con.execute(
        "SELECT id, nome, categoria, preco_venda FROM itens").fetchall()
    componentes = {}
    for item_id, comp_id, qtd in con.execute(
            "SELECT item_id, insumo_id, quantidade FROM ficha"):
        componentes.setdefault(item_id, []).append((comp_id, qtd))
    nomes = dict(con.execute("SELECT id, nome FROM insumos"))
    con.close()

    saida = []
    for item_id, nome, categoria, preco_venda in itens:
        c = antes_itens.get(item_id, _zerado())
        d = depois_itens.get(item_id, _zerado())
        if abs(c["total"] - d["total"]) < 1e-9:
            continue                       # este prato não sente a mudança
        antes = avaliar(preco_venda, c["insumos"], c["mao_obra"])
        dep = avaliar(preco_venda, d["insumos"], d["mao_obra"])
        # por onde a mudança chegou: direto na ficha, ou dentro de um preparo
        direto, quantidade, por = False, 0.0, []
        for comp_id, qtd in componentes.get(item_id, []):
            if comp_id == insumo_id:
                direto, quantidade = True, float(qtd or 0)
            elif mudou(comp_id):
                por.append(nomes.get(comp_id, ""))
        saida.append({"id": item_id, "nome": nome, "categoria": categoria,
                      "preco": antes["preco"], "quantidade": quantidade,
                      "unidade": unidade_uso, "tipo": tipo,
                      "direto": direto, "por": por,
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


def preparos_afetados(insumo_id, novo_preco):
    """Os "Feito na casa" que mudam de custo se este insumo mudar de preço."""
    antes, depois = custos_unitarios(), custos_unitarios({insumo_id: novo_preco})
    con = conectar()
    preparos = con.execute(
        "SELECT id, nome, unidade_uso FROM insumos WHERE tipo=? ORDER BY nome",
        (TIPO_PREPARO,)).fetchall()
    con.close()
    saida = []
    for pid, nome, unidade in preparos:
        a, d = antes.get(pid, _zerado_tipo()), depois.get(pid, _zerado_tipo())
        ca, cd = a["insumos"] + a["mao_obra"], d["insumos"] + d["mao_obra"]
        if abs(ca - cd) > 1e-12:
            saida.append({"id": pid, "nome": nome, "unidade": unidade,
                          "antes": ca, "depois": cd})
    return saida


def custo_unitario_do_insumo(insumo_id) -> float:
    """Custo real de 1 unidade de uso — resolvendo o preparo, se for um."""
    parcial = custos_unitarios().get(insumo_id)
    return (parcial["insumos"] + parcial["mao_obra"]) if parcial else 0.0


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
