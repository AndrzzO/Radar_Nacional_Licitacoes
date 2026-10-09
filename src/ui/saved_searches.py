"""Tela de gerenciamento de pesquisas salvas e filtros favoritos."""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QInputDialog, QFrame
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from src.database.repositories import SavedSearchRepository
from src.domain.entities import PesquisaSalva
from src.domain.filters import LicitacaoFilter
from src.utils.datetime_utils import format_datetime_br


class SavedSearchesPage(QWidget):
    """Permite visualizar, executar, renomear e excluir pesquisas salvas."""

    load_search_signal = Signal(str)  # Emite JSON dos filtros para a tela de busca

    def __init__(self, saved_repo: SavedSearchRepository, parent=None):
        super().__init__(parent)
        self.repo = saved_repo
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Cabeçalho
        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("Pesquisas Salvas e Filtros Favoritos")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title_box.addWidget(title)

        desc = QLabel("Acesse e reutilize suas pesquisas frequentes com apenas um clique.")
        desc.setStyleSheet("color: #64748B;")
        title_box.addWidget(desc)
        header.addLayout(title_box)
        header.addStretch()

        btn_nova = QPushButton("+ Criar Pesquisa Padrão GO/DF")
        btn_nova.setStyleSheet("background-color: #1B365D; color: white; padding: 8px 16px; font-weight: bold; border-radius: 4px;")
        btn_nova.clicked.connect(self._criar_pesquisa_padrao)
        header.addWidget(btn_nova)

        layout.addLayout(header)

        # Tabela de Pesquisas Salvas
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["ID", "Nome da Pesquisa", "Data de Criação", "Ações"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().resizeSection(0, 60)
        self.table.horizontalHeader().resizeSection(2, 160)
        self.table.horizontalHeader().resizeSection(3, 220)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)

        self.refresh_list()

    def refresh_list(self):
        """Carrega pesquisas do banco de dados na grade."""
        self.table.setRowCount(0)
        pesquisas = self.repo.list_all()

        for row, p in enumerate(pesquisas):
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(str(p.id)))
            self.table.setItem(row, 1, QTableWidgetItem(p.nome))
            self.table.setItem(row, 2, QTableWidgetItem(format_datetime_br(p.data_criacao)))

            # Botões de ação
            actions_widget = QWidget()
            act_layout = QHBoxLayout(actions_widget)
            act_layout.setContentsMargins(4, 2, 4, 2)
            act_layout.setSpacing(6)

            btn_carregar = QPushButton("Carregar")
            btn_carregar.setStyleSheet("background-color: #0284C7; color: white; font-size: 11px; padding: 4px 8px; border-radius: 3px;")
            btn_carregar.clicked.connect(lambda _, json_str=p.filtros_json: self.load_search_signal.emit(json_str))
            act_layout.addWidget(btn_carregar)

            btn_renomear = QPushButton("Renomear")
            btn_renomear.setStyleSheet("font-size: 11px; padding: 4px 8px;")
            btn_renomear.clicked.connect(lambda _, item=p: self._renomear(item))
            act_layout.addWidget(btn_renomear)

            btn_excluir = QPushButton("Excluir")
            btn_excluir.setStyleSheet("color: #DC2626; font-size: 11px; padding: 4px 8px;")
            btn_excluir.clicked.connect(lambda _, item_id=p.id: self._excluir(item_id))
            act_layout.addWidget(btn_excluir)

            self.table.setCellWidget(row, 3, actions_widget)

    def _criar_pesquisa_padrao(self):
        from src.utils.datetime_utils import get_current_time_sp
        f = LicitacaoFilter(ufs=["GO", "DF"], esferas=["M", "D", "E", "F"], status_proposta="recebendo_proposta")
        p = PesquisaSalva(
            nome="Oportunidades — Goiás e Distrito Federal",
            filtros_json=f.to_json(),
            data_criacao=get_current_time_sp().isoformat(),
            descricao="Pesquisa inicial em GO e DF com propostas abertas",
        )
        self.repo.save(p)
        self.refresh_list()
        QMessageBox.information(self, "Sucesso", "Pesquisa padrão para GO e DF criada com sucesso!")

    def _renomear(self, item: PesquisaSalva):
        novo_nome, ok = QInputDialog.getText(self, "Renomear Pesquisa", "Novo nome:", text=item.nome)
        if ok and novo_nome.strip():
            item.nome = novo_nome.strip()
            self.repo.save(item)
            self.refresh_list()

    def _excluir(self, item_id: int):
        reply = QMessageBox.question(
            self,
            "Confirmar Exclusão",
            "Deseja realmente excluir esta pesquisa salva?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.repo.delete(item_id)
            self.refresh_list()
