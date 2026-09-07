"""
Cardápio — Ficha Técnica e Custo de Pratos
Para restaurante/bar: descubra quanto custa cada prato, porção e bebida,
e quanto de fato sobra de lucro em cada um.
"""

import sys

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QTabWidget,
    QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QGroupBox,
    QMessageBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QStatusBar, QDialog,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QBrush, QFont

import banco


def _btn(texto, cor, slot, largura=130):
    b = QPushButton(texto)
    b.setFixedHeight(30)
    b.setFixedWidth(largura)
    b.setStyleSheet(
        f"QPushButton{{background:{cor};color:white;border:none;"
        f"border-radius:4px;font-weight:bold;}}"
        f"QPushButton:hover{{background:{cor}dd;}}"
        f"QPushButton:disabled{{background:#bdbdbd;}}")
    b.clicked.connect(slot)
    return b


# ═══════════════════════════════════════════════════════════
#  ABA INSUMOS  e  ABA MÃO DE OBRA
#  O mesmo cadastro serve aos dois: ambos são "preço ÷ quantidade
#  útil". O que muda é só a conversa da tela.
# ═══════════════════════════════════════════════════════════
ICONES_TIPO = {banco.TIPO_INSUMO: "🥕", banco.TIPO_MAO_OBRA: "👨‍🍳"}

CFG_CADASTRO = {
    banco.TIPO_INSUMO: {
        "grupo": "Cadastro de Insumo",
        "rotulos": ["Insumo:", "Comprado em:", "Preço de compra:", "Usado em:",
                    "Rende quanto?:", "Fornecedor:"],
        "ph_preco": "32,00",
        "ph_qtd": "700",
        "colunas": ["id", "Insumo", "Compra", "Preço", "Rende", "Custo real",
                    "Fornecedor"],
        "dica": ("<b>Como preencher o rendimento:</b><br><br>"
                 "🥩 Carne: comprada em <b>kg</b> a R$ 32,00 que, limpa e pronta,<br>"
                 "rende <b>700 g</b> → custo real por grama.<br><br>"
                 "🥃 Destilado: 1 <b>garrafa</b> a R$ 25,00 rende <b>20 doses</b>.<br><br>"
                 "🍺 Revenda (lata/long neck): comprado em <b>un</b>, rende <b>1</b>."),
        "falta_nome": "Informe o nome do insumo.",
        "erro_qtd": ("O rendimento deve ser maior que zero.\n"
                     "Se for revenda (lata, long neck), use 1."),
        "confirma": ("Atualizar este insumo?\n\n"
                     "O custo de todos os itens que o usam será recalculado."),
        "confirma_excluir": "Excluir este insumo?",
        "sem_selecao": "Selecione um insumo na lista.",
        "em_uso": "Não dá para excluir: este insumo é usado em",
        "status": "%d insumos cadastrados",
    },
    banco.TIPO_MAO_OBRA: {
        "grupo": "Cadastro de Mão de obra",
        "rotulos": ["Mão de obra:", "Pago por:", "Quanto custa:", "Produz em:",
                    "Faz quantos?:", "Observação:"],
        "ph_preco": "100,00",
        "ph_qtd": "50",
        "colunas": ["id", "Mão de obra", "Pago por", "Custo", "Faz",
                    "Custo real", "Observação"],
        "dica": ("<b>É a mesma conta dos insumos:</b><br><br>"
                 "👨‍🍳 <b>Montador</b>: custa <b>R$ 100,00</b> por <b>dia</b> e "
                 "monta <b>50 pratos</b> por dia → R$ 2,00 por prato.<br><br>"
                 "🔪 <b>Cozinheiro</b>: <b>R$ 150,00</b> por <b>dia</b> e dá conta "
                 "de <b>60 pratos</b> → R$ 2,50 por prato.<br><br>"
                 "Depois, na aba Cardápio, lance <b>1 prato</b> de cada um na "
                 "ficha do item — igual a um ingrediente."),
        "falta_nome": "Informe o nome da mão de obra (montador, cozinheiro…).",
        "erro_qtd": ("Informe quantos ele faz no período pago — 50 pratos por "
                     "dia, por exemplo.\nPrecisa ser maior que zero."),
        "confirma": ("Atualizar esta mão de obra?\n\n"
                     "O custo de todos os itens que a usam será recalculado."),
        "confirma_excluir": "Excluir esta mão de obra?",
        "sem_selecao": "Selecione uma mão de obra na lista.",
        "em_uso": "Não dá para excluir: esta mão de obra é usada em",
        "status": "%d tipos de mão de obra cadastrados",
    },
}


class AbaCadastro(QWidget):
    """Cadastro de um tipo de custo, com o cálculo do custo real ao vivo."""

    def __init__(self, tipo, ao_mudar=None):
        super().__init__()
        self._tipo = tipo
        self._cfg = CFG_CADASTRO[tipo]
        self._edit_id = None
        self._ao_mudar = ao_mudar          # avisa as outras abas
        self._build()
        self.recarregar()

    def _build(self):
        cfg = self._cfg
        un_compra, un_uso = banco.unidades_de(self._tipo)
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 8)

        grp = QGroupBox(cfg["grupo"])
        form = QGridLayout(grp)
        form.setSpacing(6)
        form.setColumnStretch(0, 1)
        form.setColumnStretch(5, 1)

        self._ed_nome = QLineEdit(); self._ed_nome.setFixedWidth(260)
        self._cb_un_compra = QComboBox(); self._cb_un_compra.addItems(un_compra)
        self._cb_un_compra.setFixedWidth(110)
        self._ed_preco = QLineEdit(); self._ed_preco.setFixedWidth(110)
        self._ed_preco.setPlaceholderText(cfg["ph_preco"])
        self._cb_un_uso = QComboBox(); self._cb_un_uso.addItems(un_uso)
        self._cb_un_uso.setFixedWidth(110)
        self._ed_qtd = QLineEdit(); self._ed_qtd.setFixedWidth(110)
        self._ed_qtd.setPlaceholderText(cfg["ph_qtd"])
        self._ed_forn = QLineEdit(); self._ed_forn.setFixedWidth(260)

        campos = [self._ed_nome, self._cb_un_compra, self._ed_preco,
                  self._cb_un_uso, self._ed_qtd, self._ed_forn]
        for i, (rot, w) in enumerate(zip(cfg["rotulos"], campos)):
            form.addWidget(QLabel(rot), i, 1, Qt.AlignRight)
            form.addWidget(w, i, 2, Qt.AlignLeft)

        dica = QLabel(cfg["dica"])
        dica.setWordWrap(True)
        dica.setFixedWidth(330)
        dica.setStyleSheet(
            "color:#555;font-size:11px;background:#fff8e1;"
            "border:1px solid #ffe082;border-radius:6px;padding:8px;")
        form.addWidget(dica, 0, 3, 4, 1, Qt.AlignTop)

        self._lbl_custo = QLabel("—")
        self._lbl_custo.setStyleSheet(
            "font-size:16px;font-weight:bold;color:#1565C0;"
            "border:2px solid #1565C0;border-radius:6px;padding:6px;")
        self._lbl_custo.setAlignment(Qt.AlignCenter)
        form.addWidget(self._lbl_custo, 4, 3, 2, 1)

        for w in (self._ed_preco, self._ed_qtd):
            w.textChanged.connect(self._preview)
        self._cb_un_uso.currentTextChanged.connect(self._preview)

        botoes = QHBoxLayout()
        self._btn_salvar = _btn("Salvar", "#4CAF50", self._salvar, 110)
        botoes.addWidget(self._btn_salvar)
        botoes.addWidget(_btn("Limpar", "#2196F3", self.limpar, 110))
        botoes.addWidget(_btn("Excluir", "#f44336", self._excluir, 110))
        botoes.addStretch()
        form.addLayout(botoes, len(cfg["rotulos"]), 1, 1, 2)
        root.addWidget(grp)

        self._tab = QTableWidget(0, len(cfg["colunas"]))
        self._tab.setHorizontalHeaderLabels(cfg["colunas"])
        self._tab.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._tab.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._tab.setAlternatingRowColors(True)
        self._tab.verticalHeader().setVisible(False)
        self._tab.setColumnHidden(0, True)
        self._tab.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self._tab.itemSelectionChanged.connect(self._selecionar)
        root.addWidget(self._tab, 1)

        self._status = QLabel("")
        self._status.setStyleSheet("color:#555;font-size:11px")
        root.addWidget(self._status)

    # ── cálculo ao vivo ───────────────────────────────────
    def _preview(self):
        try:
            preco = banco.parse_num(self._ed_preco.text())
            qtd = banco.parse_num(self._ed_qtd.text())
        except ValueError:
            self._lbl_custo.setText("valor inválido")
            return
        cu = banco.custo_unitario(preco, qtd)
        if not cu:
            self._lbl_custo.setText("—")
            return
        self._lbl_custo.setText(
            f"{banco.fmt_moeda(cu, 4)}\npor {self._cb_un_uso.currentText()}")

    # ── CRUD ──────────────────────────────────────────────
    def _salvar(self):
        cfg = self._cfg
        nome = self._ed_nome.text().strip()
        if not nome:
            QMessageBox.warning(self, "Atenção", cfg["falta_nome"])
            return
        try:
            preco = banco.parse_num(self._ed_preco.text())
            qtd = banco.parse_num(self._ed_qtd.text())
        except ValueError:
            QMessageBox.warning(self, "Atenção",
                                "Preço e rendimento devem ser números.")
            return
        if qtd <= 0:
            QMessageBox.warning(self, "Atenção", cfg["erro_qtd"])
            return
        if self._edit_id and QMessageBox.question(
                self, "Confirmar", cfg["confirma"],
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            return
        try:
            banco.salvar_insumo(self._edit_id, nome,
                                self._cb_un_compra.currentText(), preco,
                                self._cb_un_uso.currentText(), qtd,
                                self._ed_forn.text().strip(), self._tipo)
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Não foi possível salvar:\n{e}")
            return
        self.limpar()
        self.recarregar()
        if self._ao_mudar:
            self._ao_mudar()

    def _excluir(self):
        cfg = self._cfg
        if not self._edit_id:
            QMessageBox.information(self, "Info", cfg["sem_selecao"])
            return
        if QMessageBox.question(self, "Confirmar", cfg["confirma_excluir"],
                                QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
        usos = banco.excluir_insumo(self._edit_id)
        if usos:
            QMessageBox.warning(
                self, "Em uso", cfg["em_uso"] + "\n\n• " + "\n• ".join(usos) +
                "\n\nRemova das fichas primeiro.")
            return
        self.limpar()
        self.recarregar()
        if self._ao_mudar:
            self._ao_mudar()

    def limpar(self):
        self._edit_id = None
        self._ed_nome.clear(); self._ed_preco.clear()
        self._ed_qtd.clear(); self._ed_forn.clear()
        self._cb_un_compra.setCurrentIndex(0)
        self._cb_un_uso.setCurrentIndex(0)
        self._btn_salvar.setText("Salvar")
        self._tab.clearSelection()
        self._preview()

    def _selecionar(self):
        sel = self._tab.selectionModel().selectedRows()
        if not sel:
            return
        r = sel[0].row()
        self._edit_id = int(self._tab.item(r, 0).text())
        dados = banco.obter_insumo(self._edit_id)
        if not dados:
            return
        _, nome, un_c, preco, un_u, qtd, forn, _atu, _tipo = dados
        self._ed_nome.setText(nome)
        self._cb_un_compra.setCurrentText(un_c)
        self._ed_preco.setText(banco.fmt_num(preco))
        self._cb_un_uso.setCurrentText(un_u)
        self._ed_qtd.setText(banco.fmt_num(qtd, 3).rstrip("0").rstrip(","))
        self._ed_forn.setText(forn or "")
        self._btn_salvar.setText("Atualizar")

    def recarregar(self):
        linhas = banco.listar_insumos(self._tipo)
        self._tab.setRowCount(0)
        for (iid, nome, un_c, preco, un_u, qtd, forn, _atu, _tipo) in linhas:
            i = self._tab.rowCount()
            self._tab.insertRow(i)
            cu = banco.custo_unitario(preco, qtd)
            valores = [str(iid), nome, un_c, banco.fmt_moeda(preco),
                       f"{banco.fmt_num(qtd, 2).rstrip('0').rstrip(',')} {un_u}",
                       f"{banco.fmt_moeda(cu, 4)} / {un_u}", forn or ""]
            for j, v in enumerate(valores):
                it = QTableWidgetItem(v)
                if j in (3, 5):
                    it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                if j == 5:
                    it.setForeground(QBrush(QColor("#1565C0")))
                    it.setFont(QFont("Segoe UI", 9, QFont.Bold))
                self._tab.setItem(i, j, it)
        self._tab.resizeColumnsToContents()
        self._status.setText(self._cfg["status"] % len(linhas))


# ═══════════════════════════════════════════════════════════
#  ABA CARDÁPIO  (ficha técnica)
# ═══════════════════════════════════════════════════════════
COLS_FICHA = ["ficha_id", "insumo_id", "O que entra", "Quantidade",
              "Custo unit.", "Custo"]


class AbaCardapio(QWidget):
    """Cadastro dos itens vendidos e montagem da ficha técnica de cada um."""

    def __init__(self, ao_mudar=None):
        super().__init__()
        self._item_id = None
        self._ao_mudar = ao_mudar
        self._build()
        self.recarregar()

    def _build(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 8)

        # ── esquerda: lista de itens do cardápio ──────────
        esq = QVBoxLayout()
        grp_item = QGroupBox("Item do cardápio")
        f = QGridLayout(grp_item)
        self._ed_item = QLineEdit(); self._ed_item.setFixedWidth(220)
        self._cb_cat = QComboBox(); self._cb_cat.addItems(banco.CATEGORIAS)
        self._cb_cat.setFixedWidth(220)
        self._ed_preco_v = QLineEdit(); self._ed_preco_v.setFixedWidth(220)
        self._ed_preco_v.setPlaceholderText("45,00")
        for i, (rot, w) in enumerate([("Nome:", self._ed_item),
                                      ("Categoria:", self._cb_cat),
                                      ("Preço de venda:", self._ed_preco_v)]):
            f.addWidget(QLabel(rot), i, 0, Qt.AlignRight)
            f.addWidget(w, i, 1)
        bl = QHBoxLayout()
        self._btn_item = _btn("Salvar", "#4CAF50", self._salvar_item, 100)
        bl.addWidget(self._btn_item)
        bl.addWidget(_btn("Novo", "#2196F3", self.limpar_item, 90))
        bl.addWidget(_btn("Excluir", "#f44336", self._excluir_item, 90))
        f.addLayout(bl, 3, 0, 1, 2)
        esq.addWidget(grp_item)

        self._tab_itens = QTableWidget(0, 4)
        self._tab_itens.setHorizontalHeaderLabels(["id", "Item", "Categoria", "Preço"])
        self._tab_itens.setColumnHidden(0, True)
        self._tab_itens.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._tab_itens.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._tab_itens.setAlternatingRowColors(True)
        self._tab_itens.verticalHeader().setVisible(False)
        self._tab_itens.itemSelectionChanged.connect(self._selecionar_item)
        esq.addWidget(self._tab_itens, 1)
        root.addLayout(esq, 2)

        # ── direita: ficha técnica do item selecionado ────
        dir_ = QVBoxLayout()
        self._lbl_titulo = QLabel("Selecione um item para montar a ficha")
        self._lbl_titulo.setStyleSheet(
            "font-size:15px;font-weight:bold;color:#1565C0;padding:4px;")
        dir_.addWidget(self._lbl_titulo)

        grp_add = QGroupBox("Adicionar à ficha (insumo ou mão de obra)")
        ga = QHBoxLayout(grp_add)
        self._cb_insumo = QComboBox(); self._cb_insumo.setMinimumWidth(240)
        self._ed_qtd_uso = QLineEdit(); self._ed_qtd_uso.setFixedWidth(90)
        self._ed_qtd_uso.setPlaceholderText("250")
        self._lbl_un = QLabel("—"); self._lbl_un.setFixedWidth(50)
        self._lbl_un.setStyleSheet("color:#555;font-weight:bold;")
        self._cb_insumo.currentIndexChanged.connect(self._mostrar_unidade)
        ga.addWidget(QLabel("O que entra:")); ga.addWidget(self._cb_insumo)
        ga.addWidget(QLabel("Qtd:")); ga.addWidget(self._ed_qtd_uso)
        ga.addWidget(self._lbl_un)
        ga.addWidget(_btn("Adicionar", "#00897B", self._add_componente, 110))
        ga.addStretch()
        dir_.addWidget(grp_add)

        self._tab_ficha = QTableWidget(0, len(COLS_FICHA))
        self._tab_ficha.setHorizontalHeaderLabels(COLS_FICHA)
        self._tab_ficha.setColumnHidden(0, True)
        self._tab_ficha.setColumnHidden(1, True)
        self._tab_ficha.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._tab_ficha.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._tab_ficha.setAlternatingRowColors(True)
        self._tab_ficha.verticalHeader().setVisible(False)
        dir_.addWidget(self._tab_ficha, 1)

        lr = QHBoxLayout()
        lr.addWidget(_btn("Remover da ficha", "#f44336", self._del_componente, 170))
        lr.addStretch()
        dir_.addLayout(lr)

        self._painel = QLabel("—")
        self._painel.setAlignment(Qt.AlignCenter)
        self._painel.setStyleSheet(
            "font-size:14px;padding:10px;border:2px solid #1565C0;border-radius:8px;"
            "background:#f5f5f5;")
        dir_.addWidget(self._painel)
        root.addLayout(dir_, 3)

    # ── itens ─────────────────────────────────────────────
    def limpar_item(self):
        self._item_id = None
        self._ed_item.clear(); self._ed_preco_v.clear()
        self._cb_cat.setCurrentIndex(0)
        self._btn_item.setText("Salvar")
        self._tab_itens.clearSelection()
        self._lbl_titulo.setText("Selecione um item para montar a ficha")
        self._tab_ficha.setRowCount(0)
        self._painel.setText("—")

    def _salvar_item(self):
        nome = self._ed_item.text().strip()
        if not nome:
            QMessageBox.warning(self, "Atenção", "Informe o nome do item.")
            return
        try:
            preco = banco.parse_num(self._ed_preco_v.text())
        except ValueError:
            QMessageBox.warning(self, "Atenção", "Preço de venda deve ser um número.")
            return
        if self._item_id and QMessageBox.question(
                self, "Confirmar", "Atualizar este item?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            return
        try:
            novo = banco.salvar_item(self._item_id, nome,
                                     self._cb_cat.currentText(), preco)
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Não foi possível salvar:\n{e}")
            return
        self.recarregar()
        self._selecionar_por_id(novo)
        if self._ao_mudar:
            self._ao_mudar()

    def _excluir_item(self):
        if not self._item_id:
            QMessageBox.information(self, "Info", "Selecione um item na lista.")
            return
        if QMessageBox.question(
                self, "Confirmar",
                "Excluir este item e a ficha técnica dele?",
                QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
        banco.excluir_item(self._item_id)
        self.limpar_item()
        self.recarregar()
        if self._ao_mudar:
            self._ao_mudar()

    def _selecionar_item(self):
        sel = self._tab_itens.selectionModel().selectedRows()
        if not sel:
            return
        r = sel[0].row()
        self._item_id = int(self._tab_itens.item(r, 0).text())
        self._ed_item.setText(self._tab_itens.item(r, 1).text())
        self._cb_cat.setCurrentText(self._tab_itens.item(r, 2).text())
        preco = self._tab_itens.item(r, 3).data(Qt.UserRole)
        self._ed_preco_v.setText(banco.fmt_num(preco or 0))
        self._btn_item.setText("Atualizar")
        self._lbl_titulo.setText(f"Ficha técnica — {self._ed_item.text()}")
        self.recarregar_ficha()

    def abrir_item(self, iid):
        """Seleciona um item vindo de outra aba (duplo clique na Análise)."""
        self._selecionar_por_id(iid)

    def _selecionar_por_id(self, iid):
        for i in range(self._tab_itens.rowCount()):
            if self._tab_itens.item(i, 0).text() == str(iid):
                self._tab_itens.selectRow(i)
                return

    # ── ficha ─────────────────────────────────────────────
    def _mostrar_unidade(self):
        dados = self._cb_insumo.currentData()
        self._lbl_un.setText(dados[1] if dados else "—")

    def _add_componente(self):
        if not self._item_id:
            QMessageBox.information(self, "Info", "Selecione um item primeiro.")
            return
        dados = self._cb_insumo.currentData()
        if not dados:
            QMessageBox.information(self, "Info", "Cadastre insumos na aba Insumos.")
            return
        try:
            qtd = banco.parse_num(self._ed_qtd_uso.text())
        except ValueError:
            QMessageBox.warning(self, "Atenção", "Quantidade deve ser um número.")
            return
        if qtd <= 0:
            QMessageBox.warning(self, "Atenção", "Informe uma quantidade maior que zero.")
            return
        banco.salvar_componente(self._item_id, dados[0], qtd)
        self._ed_qtd_uso.clear()
        self.recarregar_ficha()
        if self._ao_mudar:
            self._ao_mudar()

    def _del_componente(self):
        sel = self._tab_ficha.selectionModel().selectedRows()
        if not sel:
            QMessageBox.information(self, "Info", "Selecione uma linha da ficha.")
            return
        fid = int(self._tab_ficha.item(sel[0].row(), 0).text())
        banco.excluir_componente(fid)
        self.recarregar_ficha()
        if self._ao_mudar:
            self._ao_mudar()

    def recarregar_ficha(self):
        self._tab_ficha.setRowCount(0)
        if not self._item_id:
            return
        comps = banco.listar_ficha(self._item_id)
        for c in comps:
            i = self._tab_ficha.rowCount()
            self._tab_ficha.insertRow(i)
            icone = ICONES_TIPO.get(c["tipo"], "")
            vals = [str(c["ficha_id"]), str(c["insumo_id"]),
                    f"{icone} {c['insumo']}",
                    f"{banco.fmt_num(c['quantidade'], 2).rstrip('0').rstrip(',')} {c['unidade']}",
                    banco.fmt_moeda(c["custo_unitario"], 4),
                    banco.fmt_moeda(c["custo"])]
            for j, v in enumerate(vals):
                it = QTableWidgetItem(v)
                if j >= 3:
                    it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self._tab_ficha.setItem(i, j, it)
        self._tab_ficha.resizeColumnsToContents()
        self._atualizar_painel()

    def _atualizar_painel(self):
        c = banco.custos_do_item(self._item_id)
        try:
            preco = banco.parse_num(self._ed_preco_v.text())
        except ValueError:
            preco = 0.0
        r = banco.avaliar(preco, c["insumos"], c["mao_obra"])
        f = banco.FAIXAS[r["faixa"]]

        partes = [f"Insumos <b>{banco.fmt_moeda(c['insumos'])}</b>"]
        if c["mao_obra"]:
            partes.append(f"Mão de obra <b>{banco.fmt_moeda(c['mao_obra'])}</b>")
        if preco:
            partes.append(f"Venda <b>{banco.fmt_moeda(preco)}</b>")
        if r["completo"]:
            partes.append(f"Lucro <b>{banco.fmt_moeda(r['margem'])}</b>")

        if not preco:
            rodape = ("<span style='font-size:12px'>informe o preço de venda "
                      "para ver a margem</span>")
        elif c["total"] <= 0:
            rodape = ("<span style='font-size:12px'>monte a ficha técnica para "
                      "ver o custo e a margem</span>")
        else:
            rodape = ("<span style='font-size:20px'>CMV "
                      f"{banco.fmt_num(r['cmv'], 1)}% {f['sinal']}</span>")
            if c["mao_obra"]:
                rodape += ("<span style='font-size:12px'> &nbsp;•&nbsp; com a mão "
                           "de obra, o custo é "
                           f"{banco.fmt_num(r['custo_pct'], 0)}% do preço</span>")
            if r["situacao"]:
                rodape += f"<br><span style='font-size:12px'>{r['situacao']}</span>"
        self._painel.setText(" &nbsp;•&nbsp; ".join(partes) + "<br>" + rodape)
        self._painel.setStyleSheet(
            f"font-size:14px;padding:10px;border:2px solid {f['cor']};"
            f"border-radius:8px;background:{f['fundo']};color:{f['cor']};")

    # ── recarga geral ─────────────────────────────────────
    def recarregar(self):
        # combo de insumos
        atual = self._cb_insumo.currentData()
        self._cb_insumo.blockSignals(True)
        self._cb_insumo.clear()
        for (iid, nome, _uc, preco, un_uso, qtd, _f, _a, tipo) in banco.listar_insumos():
            cu = banco.custo_unitario(preco, qtd)
            self._cb_insumo.addItem(
                f"{ICONES_TIPO.get(tipo, '')} {nome}  ({banco.fmt_moeda(cu, 4)}"
                f"/{un_uso})", (iid, un_uso))
        if atual:
            for i in range(self._cb_insumo.count()):
                if self._cb_insumo.itemData(i)[0] == atual[0]:
                    self._cb_insumo.setCurrentIndex(i)
                    break
        self._cb_insumo.blockSignals(False)
        self._mostrar_unidade()

        # tabela de itens
        guardado = self._item_id
        self._tab_itens.blockSignals(True)
        self._tab_itens.setRowCount(0)
        for (iid, nome, cat, preco, _obs) in banco.listar_itens():
            i = self._tab_itens.rowCount()
            self._tab_itens.insertRow(i)
            self._tab_itens.setItem(i, 0, QTableWidgetItem(str(iid)))
            self._tab_itens.setItem(i, 1, QTableWidgetItem(nome))
            self._tab_itens.setItem(i, 2, QTableWidgetItem(cat or ""))
            it = QTableWidgetItem(banco.fmt_moeda(preco))
            it.setData(Qt.UserRole, preco)
            it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self._tab_itens.setItem(i, 3, it)
        self._tab_itens.resizeColumnsToContents()
        self._tab_itens.blockSignals(False)
        self._item_id = guardado
        if self._item_id:
            self.recarregar_ficha()


# ═══════════════════════════════════════════════════════════
#  ABA ANÁLISE  (ranking de margem e simulação de aumento)
# ═══════════════════════════════════════════════════════════
COLS_ANALISE = ["id", "Item", "Categoria", "Insumos", "Mão de obra",
                "Preço de venda", "Lucro", "CMV", "Situação"]

ORDENS = ["Pior margem primeiro", "Melhor margem primeiro",
          "Maior lucro em R$", "Nome do item"]


def _cartao(texto, faixa):
    """Quadrinho colorido do resumo (🟢 saudáveis, 🟡 atenção, 🔴 lucro baixo)."""
    f = banco.FAIXAS[faixa]
    lbl = QLabel(texto)
    lbl.setAlignment(Qt.AlignCenter)
    lbl.setFixedHeight(52)
    lbl.setMinimumWidth(150)
    lbl.setStyleSheet(
        f"font-size:13px;font-weight:bold;color:{f['cor']};background:{f['fundo']};"
        f"border:1px solid {f['cor']};border-radius:8px;padding:4px;")
    return lbl


class DialogoSimulacao(QDialog):
    """Mostra o antes e o depois de cada item quando um insumo muda de preço."""

    def __init__(self, pai, insumo_id, nome_insumo, preco_atual, novo_preco, linhas):
        super().__init__(pai)
        self._insumo_id = insumo_id
        self._novo_preco = novo_preco
        self.aplicado = False
        self.setWindowTitle("E se o preço mudar?")
        self.resize(1080, 470)

        root = QVBoxLayout(self)
        cu_antes = banco.custo_unitario_do_insumo(insumo_id)
        ins = banco.obter_insumo(insumo_id)
        unidade = ins[4] if ins else ""
        tipo = ins[8] if ins else banco.TIPO_INSUMO
        cu_depois = banco.custo_unitario(novo_preco, ins[5]) if ins else 0.0

        topo = QLabel(
            f"{ICONES_TIPO.get(tipo, '')} <b>{nome_insumo}</b> — de "
            f"{banco.fmt_moeda(preco_atual)} para "
            f"<b>{banco.fmt_moeda(novo_preco)}</b><br>"
            f"custo por {unidade}: {banco.fmt_moeda(cu_antes, 4)} → "
            f"<b>{banco.fmt_moeda(cu_depois, 4)}</b>")
        topo.setStyleSheet(
            "font-size:13px;padding:8px;background:#e3f2fd;"
            "border:1px solid #90caf9;border-radius:6px;")
        root.addWidget(topo)

        cols = ["Item", "Preço de venda", "Custo antes", "Custo depois",
                "Lucro antes", "Lucro depois", "CMV antes", "CMV depois"]
        tab = QTableWidget(0, len(cols))
        tab.setHorizontalHeaderLabels(cols)
        tab.setEditTriggers(QAbstractItemView.NoEditTriggers)
        tab.setSelectionBehavior(QAbstractItemView.SelectRows)
        tab.setAlternatingRowColors(True)
        tab.verticalHeader().setVisible(False)
        for l in linhas:
            i = tab.rowCount()
            tab.insertRow(i)
            f_antes = banco.FAIXAS[l["faixa_antes"]]
            f_depois = banco.FAIXAS[l["faixa_depois"]]
            vals = [l["nome"], banco.fmt_moeda(l["preco"]),
                    banco.fmt_moeda(l["custo_antes"]),
                    banco.fmt_moeda(l["custo_depois"]),
                    banco.fmt_moeda(l["margem_antes"]),
                    banco.fmt_moeda(l["margem_depois"]),
                    f"{banco.fmt_num(l['cmv_antes'], 1)}% {f_antes['sinal']}"
                    if l["faixa_antes"] != "sem_dado" else f_antes["sinal"],
                    f"{banco.fmt_num(l['cmv_depois'], 1)}% {f_depois['sinal']}"
                    if l["faixa_depois"] != "sem_dado" else f_depois["sinal"]]
            for j, v in enumerate(vals):
                it = QTableWidgetItem(v)
                if j:
                    it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                if j in (3, 5, 7):
                    it.setForeground(QBrush(QColor(f_depois["cor"])))
                    it.setFont(QFont("Segoe UI", 9, QFont.Bold))
                if l["piorou"]:
                    it.setBackground(QBrush(QColor(banco.FAIXAS["ruim"]["fundo"])))
                tab.setItem(i, j, it)
        tab.resizeColumnsToContents()
        root.addWidget(tab, 1)

        pioraram = [l["nome"] for l in linhas if l["piorou"]]
        if pioraram:
            aviso = ("⚠️ <b>Passam a ter lucro baixo:</b> " + ", ".join(pioraram))
            faixa = "ruim"
        elif linhas:
            aviso = "✅ Nenhum item passa para a faixa vermelha com esse preço."
            faixa = "bom"
        else:
            aviso = "Isso ainda não é usado em nenhuma ficha técnica."
            faixa = "sem_dado"
        f = banco.FAIXAS[faixa]
        lbl = QLabel(aviso)
        lbl.setWordWrap(True)
        lbl.setStyleSheet(
            f"font-size:13px;padding:8px;color:{f['cor']};background:{f['fundo']};"
            f"border:1px solid {f['cor']};border-radius:6px;")
        root.addWidget(lbl)

        bl = QHBoxLayout()
        bl.addStretch()
        bl.addWidget(_btn("Aplicar novo custo", "#4CAF50", self._aplicar, 180))
        bl.addWidget(_btn("Fechar", "#2196F3", self.reject, 110))
        root.addLayout(bl)

    def _aplicar(self):
        if QMessageBox.question(
                self, "Confirmar",
                f"Gravar o novo custo "
                f"({banco.fmt_moeda(self._novo_preco)})?\n\n"
                "O custo de todos os itens que o usam será recalculado.",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            return
        ins = banco.obter_insumo(self._insumo_id)
        if not ins:
            QMessageBox.warning(self, "Atenção", "Insumo não encontrado.")
            return
        _id, nome, un_compra, _preco, un_uso, qtd_util, forn, _atu, tipo = ins
        try:
            banco.salvar_insumo(self._insumo_id, nome, un_compra, self._novo_preco,
                                un_uso, qtd_util, forn or "", tipo)
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Não foi possível salvar:\n{e}")
            return
        self.aplicado = True
        self.accept()


class AbaAnalise(QWidget):
    """Ranking de margem e o alerta dos itens que dão pouco lucro."""

    def __init__(self, ao_abrir_item=None, ao_mudar=None):
        super().__init__()
        self._ao_abrir_item = ao_abrir_item   # leva o usuário à ficha do item
        self._ao_mudar = ao_mudar             # avisa as outras abas
        self._build()
        self.recarregar()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 8)

        # ── resumo em quadrinhos ──────────────────────────
        resumo = QHBoxLayout()
        self._cartoes = {}
        for faixa, titulo in [("bom", "saudáveis"), ("atencao", "atenção"),
                              ("ruim", "lucro baixo"), ("sem_dado", "faltam dados")]:
            c = _cartao("—", faixa)
            self._cartoes[faixa] = (c, titulo)
            resumo.addWidget(c)
        resumo.addStretch()
        root.addLayout(resumo)

        self._alerta = QLabel("")
        self._alerta.setWordWrap(True)
        root.addWidget(self._alerta)

        # ── filtros ───────────────────────────────────────
        filtros = QHBoxLayout()
        self._cb_cat = QComboBox(); self._cb_cat.setFixedWidth(180)
        self._cb_ordem = QComboBox(); self._cb_ordem.addItems(ORDENS)
        self._cb_ordem.setFixedWidth(200)
        self._cb_cat.currentIndexChanged.connect(self._preencher_tabela)
        self._cb_ordem.currentIndexChanged.connect(self._preencher_tabela)
        filtros.addWidget(QLabel("Categoria:")); filtros.addWidget(self._cb_cat)
        filtros.addSpacing(16)
        filtros.addWidget(QLabel("Ordenar por:")); filtros.addWidget(self._cb_ordem)
        filtros.addStretch()
        filtros.addWidget(_btn("Atualizar", "#2196F3", self.recarregar, 110))
        root.addLayout(filtros)

        # ── ranking ───────────────────────────────────────
        self._tab = QTableWidget(0, len(COLS_ANALISE))
        self._tab.setHorizontalHeaderLabels(COLS_ANALISE)
        self._tab.setColumnHidden(0, True)
        self._tab.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._tab.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._tab.setAlternatingRowColors(True)
        self._tab.verticalHeader().setVisible(False)
        self._tab.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self._tab.doubleClicked.connect(self._abrir_item)
        root.addWidget(self._tab, 1)

        dica = QLabel("Dê dois cliques em um item para abrir a ficha técnica dele.")
        dica.setStyleSheet("color:#777;font-size:11px;")
        root.addWidget(dica)

        # ── simulação de aumento ──────────────────────────
        grp = QGroupBox("A carne subiu? O montador pediu aumento?"
                        "  Veja o efeito antes de mudar o preço")
        gl = QHBoxLayout(grp)
        self._cb_insumo = QComboBox(); self._cb_insumo.setMinimumWidth(260)
        self._ed_novo = QLineEdit(); self._ed_novo.setFixedWidth(110)
        self._ed_novo.setPlaceholderText("38,00")
        self._ed_novo.returnPressed.connect(self._simular)
        self._lbl_atual = QLabel("—")
        self._lbl_atual.setStyleSheet("color:#555;font-size:12px;")
        self._cb_insumo.currentIndexChanged.connect(self._mostrar_preco_atual)
        gl.addWidget(QLabel("Insumo ou mão de obra:"))
        gl.addWidget(self._cb_insumo)
        gl.addWidget(QLabel("Novo custo:")); gl.addWidget(self._ed_novo)
        gl.addWidget(self._lbl_atual)
        gl.addWidget(_btn("Ver efeito", "#00897B", self._simular, 130))
        gl.addStretch()
        root.addWidget(grp)

        self._status = QLabel("")
        self._status.setStyleSheet("color:#555;font-size:11px;")
        root.addWidget(self._status)

    # ── ranking ───────────────────────────────────────────
    def _preencher_tabela(self):
        cat = self._cb_cat.currentText()
        linhas = [l for l in self._dados
                  if cat in ("Todas as categorias", "") or (l["categoria"] or "") == cat]

        ordem = self._cb_ordem.currentText()
        if ordem == ORDENS[0]:      # pior margem primeiro
            chave = lambda l: (l["completo"] is False, -l["cmv"], l["nome"].lower())
        elif ordem == ORDENS[1]:    # melhor margem primeiro
            chave = lambda l: (l["completo"] is False, l["cmv"], l["nome"].lower())
        elif ordem == ORDENS[2]:    # maior lucro em R$
            chave = lambda l: (l["completo"] is False, -l["margem"], l["nome"].lower())
        else:                       # nome
            chave = lambda l: l["nome"].lower()
        linhas.sort(key=chave)

        self._tab.setRowCount(0)
        for l in linhas:
            f = banco.FAIXAS[l["faixa"]]
            i = self._tab.rowCount()
            self._tab.insertRow(i)
            cmv = "—" if not l["completo"] else f"{banco.fmt_num(l['cmv'], 1)}%"
            situacao = l["situacao"] or f"{f['sinal']} {f['rotulo']}"
            vals = [str(l["id"]), l["nome"], l["categoria"] or "",
                    banco.fmt_moeda(l["custo_insumos"])
                    if l["custo_insumos"] > 0 else "—",
                    banco.fmt_moeda(l["custo_mao_obra"])
                    if l["custo_mao_obra"] > 0 else "—",
                    banco.fmt_moeda(l["preco"]) if l["preco"] > 0 else "—",
                    banco.fmt_moeda(l["margem"]) if l["completo"] else "—",
                    cmv, situacao]
            for j, v in enumerate(vals):
                it = QTableWidgetItem(v)
                if j in (3, 4, 5, 6, 7):
                    it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                if j in (6, 7, 8):
                    it.setForeground(QBrush(QColor(f["cor"])))
                if j in (7, 8):
                    it.setFont(QFont("Segoe UI", 9, QFont.Bold))
                if l["faixa"] == "ruim":
                    it.setBackground(QBrush(QColor(f["fundo"])))
                self._tab.setItem(i, j, it)
        self._tab.resizeColumnsToContents()
        self._status.setText(
            f"{len(linhas)} itens listados de {len(self._dados)} no cardápio")

    def _abrir_item(self):
        sel = self._tab.selectionModel().selectedRows()
        if sel and self._ao_abrir_item:
            self._ao_abrir_item(int(self._tab.item(sel[0].row(), 0).text()))

    # ── simulação ─────────────────────────────────────────
    def _mostrar_preco_atual(self):
        iid = self._cb_insumo.currentData()
        ins = banco.obter_insumo(iid) if iid else None
        self._lbl_atual.setText(
            f"(hoje: {banco.fmt_moeda(ins[3])} por {ins[2]})" if ins else "—")

    def _simular(self):
        iid = self._cb_insumo.currentData()
        if not iid:
            QMessageBox.information(
                self, "Info", "Cadastre algo nas abas Insumos ou Mão de obra.")
            return
        try:
            novo = banco.parse_num(self._ed_novo.text())
        except ValueError:
            QMessageBox.warning(self, "Atenção", "O novo custo deve ser um número.")
            return
        if novo <= 0:
            QMessageBox.warning(self, "Atenção",
                                "Informe o novo custo (maior que zero).")
            return
        ins = banco.obter_insumo(iid)
        linhas = banco.simular_preco_insumo(iid, novo)
        dlg = DialogoSimulacao(self, iid, ins[1], ins[3], novo, linhas)
        dlg.exec_()
        if dlg.aplicado:
            self._ed_novo.clear()
            self.recarregar()
            if self._ao_mudar:
                self._ao_mudar()

    # ── recarga geral ─────────────────────────────────────
    def recarregar(self):
        self._dados = banco.analise_itens()

        contagem = {"bom": 0, "atencao": 0, "ruim": 0, "sem_dado": 0}
        for l in self._dados:
            contagem[l["faixa"]] += 1
        for faixa, (cartao, titulo) in self._cartoes.items():
            sinal = banco.FAIXAS[faixa]["sinal"]
            cartao.setText(f"{sinal} {contagem[faixa]}\n{titulo}")

        ruins = [l["nome"] for l in self._dados if l["faixa"] == "ruim"]
        if ruins:
            f = banco.FAIXAS["ruim"]
            texto = ("⚠️ <b>Estes itens dão pouco lucro</b> (CMV acima de "
                     f"{banco.fmt_num(banco.CMV_ATENCAO, 0)}%): " + ", ".join(ruins))
        elif any(l["completo"] for l in self._dados):
            f = banco.FAIXAS["bom"]
            texto = "✅ Nenhum item com lucro baixo. O cardápio está saudável."
        else:
            f = banco.FAIXAS["sem_dado"]
            texto = ("Cadastre os itens na aba Cardápio, com preço de venda e ficha "
                     "técnica, para ver a margem de cada um aqui.")
        self._alerta.setText(texto)
        self._alerta.setStyleSheet(
            f"font-size:13px;padding:8px;color:{f['cor']};background:{f['fundo']};"
            f"border:1px solid {f['cor']};border-radius:6px;")

        # filtro de categorias: só as que existem no cardápio
        cat_atual = self._cb_cat.currentText()
        cats = sorted({(l["categoria"] or "").strip() for l in self._dados} - {""})
        self._cb_cat.blockSignals(True)
        self._cb_cat.clear()
        self._cb_cat.addItem("Todas as categorias")
        self._cb_cat.addItems(cats)
        if cat_atual:
            i = self._cb_cat.findText(cat_atual)
            self._cb_cat.setCurrentIndex(i if i >= 0 else 0)
        self._cb_cat.blockSignals(False)

        # combo de insumos da simulação
        atual = self._cb_insumo.currentData()
        self._cb_insumo.blockSignals(True)
        self._cb_insumo.clear()
        for (iid, nome, un_c, preco, _un_u, _qtd, _f, _a, tipo) in banco.listar_insumos():
            self._cb_insumo.addItem(
                f"{ICONES_TIPO.get(tipo, '')} {nome}  "
                f"({banco.fmt_moeda(preco)}/{un_c})", iid)
        if atual:
            i = self._cb_insumo.findData(atual)
            if i >= 0:
                self._cb_insumo.setCurrentIndex(i)
        self._cb_insumo.blockSignals(False)
        self._mostrar_preco_atual()

        self._preencher_tabela()


# ═══════════════════════════════════════════════════════════
#  JANELA PRINCIPAL
# ═══════════════════════════════════════════════════════════
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Cardápio — Ficha Técnica e Custo")
        self.resize(1150, 680)

        self._aba_insumos = AbaCadastro(banco.TIPO_INSUMO,
                                        ao_mudar=self._atualizar_tudo)
        self._aba_mao_obra = AbaCadastro(banco.TIPO_MAO_OBRA,
                                         ao_mudar=self._atualizar_tudo)
        self._aba_cardapio = AbaCardapio(ao_mudar=self._atualizar_tudo)
        self._aba_analise = AbaAnalise(ao_abrir_item=self._abrir_ficha,
                                       ao_mudar=self._atualizar_tudo)

        self._tabs = QTabWidget()
        self._tabs.addTab(self._aba_insumos, "  Insumos  ")
        self._tabs.addTab(self._aba_mao_obra, "  Mão de obra  ")
        self._tabs.addTab(self._aba_cardapio, "  Cardápio  ")
        self._tabs.addTab(self._aba_analise, "  Análise  ")
        self._tabs.currentChanged.connect(self._trocou_de_aba)
        self.setCentralWidget(self._tabs)

        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Pronto")

    def _atualizar_tudo(self):
        """Mudou um insumo ou uma ficha: recalcula o que depende disso."""
        self._aba_insumos.recarregar()
        self._aba_mao_obra.recarregar()
        self._aba_cardapio.recarregar()
        self._aba_analise.recarregar()
        self.statusBar().showMessage("Custos recalculados", 3000)

    def _trocou_de_aba(self, indice):
        """A Análise sempre abre com os números do momento."""
        if self._tabs.widget(indice) is self._aba_analise:
            self._aba_analise.recarregar()

    def _abrir_ficha(self, item_id):
        """Duplo clique na Análise leva direto à ficha técnica do item."""
        self._tabs.setCurrentWidget(self._aba_cardapio)
        self._aba_cardapio.abrir_item(item_id)


if __name__ == "__main__":
    banco.init_db()
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())
