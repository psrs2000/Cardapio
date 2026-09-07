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
        self._aba_cardapio = EmBreve(
            "Cardápio", "Aqui você vai montar a ficha técnica de cada prato,\n"
                        "porção e bebida — e ver o custo aparecer sozinho.")
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
        self.statusBar().showMessage("Custos recalculados", 3000)


if __name__ == "__main__":
    banco.init_db()
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())
