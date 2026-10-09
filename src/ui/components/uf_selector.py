"""Componente de seleção múltipla das 27 Unidades Federativas (UFs)."""
from typing import List, Callable, Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QListWidget, QListWidgetItem, QDialog, QDialogButtonBox
)
from PySide6.QtCore import Qt, Signal

from src.application.location_service import LocationService, FALLBACK_ESTADOS
from src.domain.entities import Estado


class UFSelectorDialog(QDialog):
    """Diálogo modal com busca para seleção de uma ou múltiplas UFs brasileiras."""

    def __init__(self, estados: List[Estado], selected_ufs: List[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Selecionar Estados (UFs)")
        self.resize(380, 480)
        self.estados = estados
        self.selected_ufs = set(selected_ufs)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # Campo de busca rápida
        self.txt_busca = QLineEdit()
        self.txt_busca.setPlaceholderText("Buscar estado por nome ou sigla...")
        self.txt_busca.textChanged.connect(self._filtrar)
        layout.addWidget(self.txt_busca)

        # Ações rápidas
        btn_box = QHBoxLayout()
        btn_todos = QPushButton("Marcar Todos")
        btn_todos.clicked.connect(self._marcar_todos)
        btn_limpar = QPushButton("Limpar")
        btn_limpar.clicked.connect(self._limpar)
        btn_box.addWidget(btn_todos)
        btn_box.addWidget(btn_limpar)
        layout.addLayout(btn_box)

        # Lista de UFs com checkboxes
        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)
        self._popular_lista()

        # Botões de confirmação
        bbox = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bbox.accepted.connect(self.accept)
        bbox.rejected.connect(self.reject)
        layout.addWidget(bbox)

    def _popular_lista(self, filtro: str = ""):
        self.list_widget.clear()
        f = filtro.strip().upper()
        for e in self.estados:
            if not f or f in e.uf_sigla or f in e.nome.upper():
                item = QListWidgetItem(f"{e.uf_sigla} — {e.nome}")
                item.setData(Qt.ItemDataRole.UserRole, e.uf_sigla)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                check = Qt.CheckState.Checked if e.uf_sigla in self.selected_ufs else Qt.CheckState.Unchecked
                item.setCheckState(check)
                self.list_widget.addItem(item)

    def _filtrar(self, texto: str):
        self._salvar_estado_atual()
        self._popular_lista(texto)

    def _salvar_estado_atual(self):
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            sigla = item.data(Qt.ItemDataRole.UserRole)
            if item.checkState() == Qt.CheckState.Checked:
                self.selected_ufs.add(sigla)
            else:
                self.selected_ufs.discard(sigla)

    def _marcar_todos(self):
        for e in self.estados:
            self.selected_ufs.add(e.uf_sigla)
        self._popular_lista(self.txt_busca.text())

    def _limpar(self):
        self.selected_ufs.clear()
        self._popular_lista(self.txt_busca.text())

    def get_selected(self) -> List[str]:
        self._salvar_estado_atual()
        return sorted(list(self.selected_ufs))


class UFSelectorWidget(QWidget):
    """Widget de exibição resumida e botão de abertura do seletor de UFs."""

    selection_changed = Signal(list)

    def __init__(self, location_service: LocationService, initial_ufs: Optional[List[str]] = None, parent=None):
        super().__init__(parent)
        self.service = location_service
        self.selected_ufs: List[str] = list(initial_ufs) if initial_ufs is not None else ["GO", "DF"]
        self._init_ui()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.lbl_summary = QLabel()
        self.lbl_summary.setStyleSheet("background-color: white; border: 1px solid #CCC; border-radius: 4px; padding: 4px 8px;")
        layout.addWidget(self.lbl_summary, 1)

        btn_select = QPushButton("UFs...")
        btn_select.clicked.connect(self._abrir_dialogo)
        layout.addWidget(btn_select)

        self._atualizar_resumo()

    def _atualizar_resumo(self):
        if not self.selected_ufs:
            self.lbl_summary.setText("<b>Todo o Brasil</b> (Todas as 27 UFs)")
        elif len(self.selected_ufs) == 27:
            self.lbl_summary.setText("<b>Todas as 27 UFs</b> selecionadas")
        else:
            self.lbl_summary.setText(f"<b>UFs:</b> {', '.join(self.selected_ufs)}")

    def _abrir_dialogo(self):
        estados = self.service.get_all_estados()
        dlg = UFSelectorDialog(estados, self.selected_ufs, self)
        if dlg.exec():
            self.selected_ufs = dlg.get_selected()
            self._atualizar_resumo()
            self.selection_changed.emit(self.selected_ufs)

    def get_selected_ufs(self) -> List[str]:
        return list(self.selected_ufs)

    def set_selected_ufs(self, ufs: List[str]):
        self.selected_ufs = list(ufs)
        self._atualizar_resumo()
        self.selection_changed.emit(self.selected_ufs)
