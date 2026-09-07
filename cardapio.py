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
    QAbstractItemView, QStatusBar,
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
#  ABA INSUMOS
# ═══════════════════════════════════════════════════════════
COLS_INSUMOS = ["id", "Insumo", "Compra", "Preço", "Rende", "Custo real", "Fornecedor"]


class AbaInsumos(QWidget):
    """Cadastro dos ingredientes/bebidas com o cálculo do custo real."""

    def __init__(self, ao_mudar=None):
        super().__init__()
        self._edit_id = None
        self._ao_mudar = ao_mudar          # avisa as outras abas
        self._build()
        self.recarregar()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 8)

        grp = QGroupBox("Cadastro de Insumo")
        form = QGridLayout(grp)
        form.setSpacing(6)
        form.setColumnStretch(0, 1)
        form.setColumnStretch(5, 1)

        self._ed_nome = QLineEdit(); self._ed_nome.setFixedWidth(260)
        self._cb_un_compra = QComboBox(); self._cb_un_compra.addItems(banco.UNIDADES_COMPRA)
        self._cb_un_compra.setFixedWidth(110)
        self._ed_preco = QLineEdit(); self._ed_preco.setFixedWidth(110)
        self._ed_preco.setPlaceholderText("32,00")
        self._cb_un_uso = QComboBox(); self._cb_un_uso.addItems(banco.UNIDADES_USO)
        self._cb_un_uso.setFixedWidth(110)
        self._ed_qtd = QLineEdit(); self._ed_qtd.setFixedWidth(110)
        self._ed_qtd.setPlaceholderText("700")
        self._ed_forn = QLineEdit(); self._ed_forn.setFixedWidth(260)

        linhas = [
            ("Insumo:", self._ed_nome),
            ("Comprado em:", self._cb_un_compra),
            ("Preço de compra:", self._ed_preco),
            ("Usado em:", self._cb_un_uso),
            ("Rende quanto?:", self._ed_qtd),
            ("Fornecedor:", self._ed_forn),
        ]
        for i, (rot, w) in enumerate(linhas):
            form.addWidget(QLabel(rot), i, 1, Qt.AlignRight)
            form.addWidget(w, i, 2, Qt.AlignLeft)

        dica = QLabel(
            "<b>Como preencher o rendimento:</b><br><br>"
            "🥩 Carne: comprada em <b>kg</b> a R$ 32,00 que, limpa e pronta,<br>"
            "rende <b>700 g</b> → custo real por grama.<br><br>"
            "🥃 Destilado: 1 <b>garrafa</b> a R$ 25,00 rende <b>20 doses</b>.<br><br>"
            "🍺 Revenda (lata/long neck): comprado em <b>un</b>, rende <b>1</b>.")
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
        form.addLayout(botoes, len(linhas), 1, 1, 2)
        root.addWidget(grp)

        self._tab = QTableWidget(0, len(COLS_INSUMOS))
        self._tab.setHorizontalHeaderLabels(COLS_INSUMOS)
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
        nome = self._ed_nome.text().strip()
        if not nome:
            QMessageBox.warning(self, "Atenção", "Informe o nome do insumo.")
            return
        try:
            preco = banco.parse_num(self._ed_preco.text())
            qtd = banco.parse_num(self._ed_qtd.text())
        except ValueError:
            QMessageBox.warning(self, "Atenção", "Preço e rendimento devem ser números.")
            return
        if qtd <= 0:
            QMessageBox.warning(self, "Atenção",
                                "O rendimento deve ser maior que zero.\n"
                                "Se for revenda (lata, long neck), use 1.")
            return
        if self._edit_id and QMessageBox.question(
                self, "Confirmar", "Atualizar este insumo?\n\n"
                "O custo de todos os itens que o usam será recalculado.",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            return
        try:
            banco.salvar_insumo(self._edit_id, nome,
                                self._cb_un_compra.currentText(), preco,
                                self._cb_un_uso.currentText(), qtd,
                                self._ed_forn.text().strip())
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Não foi possível salvar:\n{e}")
            return
        self.limpar()
        self.recarregar()
        if self._ao_mudar:
            self._ao_mudar()

    def _excluir(self):
        if not self._edit_id:
            QMessageBox.information(self, "Info", "Selecione um insumo na lista.")
            return
        if QMessageBox.question(self, "Confirmar", "Excluir este insumo?",
                                QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
        usos = banco.excluir_insumo(self._edit_id)
        if usos:
            QMessageBox.warning(
                self, "Insumo em uso",
                "Não dá para excluir: ele é usado em\n\n• " + "\n• ".join(usos) +
                "\n\nRemova-o dessas fichas primeiro.")
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
        _, nome, un_c, preco, un_u, qtd, forn, _ = dados
        self._ed_nome.setText(nome)
        self._cb_un_compra.setCurrentText(un_c)
        self._ed_preco.setText(banco.fmt_num(preco))
        self._cb_un_uso.setCurrentText(un_u)
        self._ed_qtd.setText(banco.fmt_num(qtd, 3).rstrip("0").rstrip(","))
        self._ed_forn.setText(forn or "")
        self._btn_salvar.setText("Atualizar")

    def recarregar(self):
        linhas = banco.listar_insumos()
        self._tab.setRowCount(0)
        for (iid, nome, un_c, preco, un_u, qtd, forn, _atu) in linhas:
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
        self._status.setText(f"{len(linhas)} insumos cadastrados")


# ═══════════════════════════════════════════════════════════
#  ABA CARDÁPIO  (ficha técnica)
# ═══════════════════════════════════════════════════════════
COLS_FICHA = ["ficha_id", "insumo_id", "Insumo", "Quantidade", "Custo unit.", "Custo"]


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

        grp_add = QGroupBox("Adicionar insumo à ficha")
        ga = QHBoxLayout(grp_add)
        self._cb_insumo = QComboBox(); self._cb_insumo.setMinimumWidth(240)
        self._ed_qtd_uso = QLineEdit(); self._ed_qtd_uso.setFixedWidth(90)
        self._ed_qtd_uso.setPlaceholderText("250")
        self._lbl_un = QLabel("—"); self._lbl_un.setFixedWidth(50)
        self._lbl_un.setStyleSheet("color:#555;font-weight:bold;")
        self._cb_insumo.currentIndexChanged.connect(self._mostrar_unidade)
        ga.addWidget(QLabel("Insumo:")); ga.addWidget(self._cb_insumo)
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
            vals = [str(c["ficha_id"]), str(c["insumo_id"]), c["insumo"],
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
        custo = banco.custo_do_item(self._item_id)
        try:
            preco = banco.parse_num(self._ed_preco_v.text())
        except ValueError:
            preco = 0.0
        if not preco:
            self._painel.setText(
                f"Custo do item: <b>{banco.fmt_moeda(custo)}</b>"
                "<br><span style='color:#888;font-size:12px'>"
                "informe o preço de venda para ver a margem</span>")
            self._painel.setStyleSheet(
                "font-size:14px;padding:10px;border:2px solid #1565C0;"
                "border-radius:8px;background:#f5f5f5;")
            return
        margem = preco - custo
        cmv = custo / preco * 100
        cor = "#1b5e20" if cmv <= 35 else ("#ef6c00" if cmv <= 45 else "#c62828")
        fundo = "#e8f5e9" if cmv <= 35 else ("#fff3e0" if cmv <= 45 else "#ffebee")
        sinal = "🟢" if cmv <= 35 else ("🟡" if cmv <= 45 else "🔴")
        self._painel.setText(
            f"Custo <b>{banco.fmt_moeda(custo)}</b> &nbsp;•&nbsp; "
            f"Venda <b>{banco.fmt_moeda(preco)}</b> &nbsp;•&nbsp; "
            f"Margem <b>{banco.fmt_moeda(margem)}</b><br>"
            f"<span style='font-size:20px'>CMV {cmv:.1f}% {sinal}</span>")
        self._painel.setStyleSheet(
            f"font-size:14px;padding:10px;border:2px solid {cor};"
            f"border-radius:8px;background:{fundo};color:{cor};")

    # ── recarga geral ─────────────────────────────────────
    def recarregar(self):
        # combo de insumos
        atual = self._cb_insumo.currentData()
        self._cb_insumo.blockSignals(True)
        self._cb_insumo.clear()
        for (iid, nome, _uc, preco, un_uso, qtd, _f, _a) in banco.listar_insumos():
            cu = banco.custo_unitario(preco, qtd)
            self._cb_insumo.addItem(
                f"{nome}  ({banco.fmt_moeda(cu, 4)}/{un_uso})", (iid, un_uso))
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
#  JANELA PRINCIPAL
# ═══════════════════════════════════════════════════════════
class EmBreve(QWidget):
    def __init__(self, titulo, texto):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.addStretch()
        t = QLabel(titulo)
        t.setAlignment(Qt.AlignCenter)
        t.setStyleSheet("font-size:20px;font-weight:bold;color:#1565C0;")
        d = QLabel(texto)
        d.setAlignment(Qt.AlignCenter)
        d.setStyleSheet("color:#666;font-size:12px;")
        lay.addWidget(t); lay.addWidget(d)
        lay.addStretch()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Cardápio — Ficha Técnica e Custo")
        self.resize(1150, 680)

        self._aba_insumos = AbaInsumos(ao_mudar=self._atualizar_tudo)
        self._aba_cardapio = AbaCardapio(ao_mudar=self._atualizar_tudo)
        self._aba_analise = EmBreve(
            "Análise", "Ranking de margem, CMV e alerta dos itens\n"
                       "que ficaram com lucro baixo.")

        tabs = QTabWidget()
        tabs.addTab(self._aba_insumos, "  Insumos  ")
        tabs.addTab(self._aba_cardapio, "  Cardápio  ")
        tabs.addTab(self._aba_analise, "  Análise  ")
        self.setCentralWidget(tabs)

        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Pronto")

    def _atualizar_tudo(self):
        """Mudou um insumo ou uma ficha: recalcula o que depende disso."""
        self._aba_cardapio.recarregar()
        self.statusBar().showMessage("Custos recalculados", 3000)


if __name__ == "__main__":
    banco.init_db()
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())
