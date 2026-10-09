"""Componente de seleção de municípios associados aos códigos oficiais do IBGE."""
from typing import List, Set, Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QListWidget, QListWidgetItem, QDialog, QDialogButtonBox
)
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import QMessageBox
from src.workers.task_worker import TaskWorker
from src.application.location_service import FALLBACK_ESTADOS

from src.application.location_service import LocationService
from src.domain.entities import Municipio


class MunicipioSelectorDialog(QDialog):
    """Diálogo modal para seleção de municípios com código IBGE."""

    def __init__(self, municipios: List[Municipio], selected_ibges: List[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Selecionar Municípios")
        self.resize(450, 520)
        self.municipios = municipios
        self.selected_ibges = set(selected_ibges)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        self.txt_busca = QLineEdit()
        self.txt_busca.setPlaceholderText("Buscar município pelo nome ou código IBGE...")
        self.txt_busca.textChanged.connect(self._filtrar)
        layout.addWidget(self.txt_busca)

        btn_box = QHBoxLayout()
        btn_todos = QPushButton("Marcar Todos")
        btn_todos.clicked.connect(self._marcar_todos)
        btn_limpar = QPushButton("Limpar Seleção")
        btn_limpar.clicked.connect(self._limpar)
        btn_box.addWidget(btn_todos)
        btn_box.addWidget(btn_limpar)
        layout.addLayout(btn_box)

        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)
        self._popular_lista()

        bbox = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bbox.accepted.connect(self.accept)
        bbox.rejected.connect(self.reject)
        layout.addWidget(bbox)

    def _popular_lista(self, filtro: str = ""):
        self.list_widget.clear()
        f = filtro.strip().upper()
        for m in self.municipios:
            if not f or f in m.nome.upper() or f in m.codigo_ibge:
                item = QListWidgetItem(f"{m.nome} ({m.uf_sigla}) — IBGE: {m.codigo_ibge}")
                item.setData(Qt.ItemDataRole.UserRole, m.codigo_ibge)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                check = Qt.CheckState.Checked if m.codigo_ibge in self.selected_ibges else Qt.CheckState.Unchecked
                item.setCheckState(check)
                self.list_widget.addItem(item)

    def _filtrar(self, texto: str):
        self._salvar_estado_atual()
        self._popular_lista(texto)

    def _salvar_estado_atual(self):
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            ibge = item.data(Qt.ItemDataRole.UserRole)
            if item.checkState() == Qt.CheckState.Checked:
                self.selected_ibges.add(ibge)
            else:
                self.selected_ibges.discard(ibge)

    def _marcar_todos(self):
        for m in self.municipios:
            self.selected_ibges.add(m.codigo_ibge)
        self._popular_lista(self.txt_busca.text())

    def _limpar(self):
        self.selected_ibges.clear()
        self._popular_lista(self.txt_busca.text())

    def get_selected(self) -> List[str]:
        self._salvar_estado_atual()
        return list(self.selected_ibges)


class MunicipioSelectorWidget(QWidget):
    """Widget de exibição de municípios selecionados."""

    selection_changed = Signal(list)

    def __init__(self, location_service: LocationService, parent=None):
        super().__init__(parent)
        self.service = location_service
        self.worker = None
        self.current_ufs: List[str] = ["GO", "DF"]
        self.selected_ibges: List[str] = []
        self._init_ui()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.lbl_summary = QLabel()
        self.lbl_summary.setStyleSheet("background-color: white; border: 1px solid #CCC; border-radius: 4px; padding: 4px 8px;")
        layout.addWidget(self.lbl_summary, 1)

        self.btn_select = QPushButton("Municípios...")
        self.btn_select.clicked.connect(self._abrir_dialogo)
        layout.addWidget(self.btn_select)

        self._atualizar_resumo()

    def update_ufs(self, ufs: List[str]):
        """Atualiza a lista de UFs ativas para carregar municípios correspondentes."""
        if set(ufs)!=set(self.current_ufs): self.selected_ibges=[]
        self.current_ufs = list(ufs)
        self._atualizar_resumo()

    def _atualizar_resumo(self):
        if not self.selected_ibges:
            if not self.current_ufs:
                self.lbl_summary.setText("Todos os municípios do Brasil")
            else:
                self.lbl_summary.setText(f"Todos os municípios de {', '.join(self.current_ufs)}")
        else:
            self.lbl_summary.setText(f"<b>{len(self.selected_ibges)} município(s)</b> selecionado(s)")

    def _abrir_dialogo(self):
        if self.worker and self.worker.isRunning(): return
        ufs=list(self.current_ufs) or [e.uf_sigla for e in FALLBACK_ESTADOS]
        def load(progress,cancelled):
            municipios=[]
            for i,uf in enumerate(ufs):
                if cancelled(): return None
                municipios.extend(self.service.get_municipios_by_uf(uf)); progress(i+1,len(ufs))
            return municipios
        self.btn_select.setEnabled(False)
        self.worker=TaskWorker(load,self); self.worker.result.connect(self._municipios_loaded); self.worker.error.connect(self._load_error); self.worker.finished.connect(self._load_finished); self.worker.start()

    @Slot(str)
    def _load_error(self,error): QMessageBox.warning(self,'Municípios indisponíveis',error)
    @Slot()
    def _load_finished(self): self.btn_select.setEnabled(True)
    @Slot(object)
    def _municipios_loaded(self,municipios):
        if municipios is None: return
        dlg = MunicipioSelectorDialog(municipios, self.selected_ibges, self)
        if dlg.exec():
            self.selected_ibges = dlg.get_selected()
            self._atualizar_resumo()
            self.selection_changed.emit(self.selected_ibges)

    def get_selected_ibges(self) -> List[str]:
        return list(self.selected_ibges)

    def set_selected_ibges(self, ibges: List[str]):
        self.selected_ibges = list(ibges)
        self._atualizar_resumo()
        self.selection_changed.emit(self.selected_ibges)

    def clear(self):
        self.selected_ibges = []
        self._atualizar_resumo()
        self.selection_changed.emit(self.selected_ibges)
