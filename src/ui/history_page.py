"""Tela de histórico de operações e coletas executadas."""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from src.database.repositories import SyncRepository
from src.utils.datetime_utils import format_datetime_br


class HistoryPage(QWidget):
    """Apresenta o log persistente de todas as coletas e sincronizações realizadas."""

    def __init__(self, sync_repo: SyncRepository, parent=None):
        super().__init__(parent)
        self.repo = sync_repo
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("Histórico de Coletas e Sincronizações")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title_box.addWidget(title)

        desc = QLabel("Auditoria de todas as consultas executadas contra fontes oficiais.")
        desc.setStyleSheet("color: #64748B;")
        title_box.addWidget(desc)
        header.addLayout(title_box)
        header.addStretch()

        btn_atualizar = QPushButton("Atualizar Histórico")
        btn_atualizar.clicked.connect(self.refresh_history)
        header.addWidget(btn_atualizar)
        layout.addLayout(header)

        # Tabela de Histórico
        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels([
            "ID", "Início", "Término", "Fonte",
            "Recebidos", "Novos", "Atualizados", "Status", "Erros / Detalhes"
        ])
        header_v = self.table.horizontalHeader()
        header_v.resizeSection(0, 50)
        header_v.resizeSection(1, 140)
        header_v.resizeSection(2, 140)
        header_v.resizeSection(3, 80)
        header_v.resizeSection(4, 80)
        header_v.resizeSection(5, 80)
        header_v.resizeSection(6, 90)
        header_v.resizeSection(7, 130)
        header_v.setSectionResizeMode(8, QHeaderView.ResizeMode.Stretch)

        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.doubleClicked.connect(self._mostrar_detalhes_erro)
        layout.addWidget(self.table)

        self.refresh_history()

    def refresh_history(self):
        """Carrega os registros de sincronização mais recentes do banco."""
        self.table.setRowCount(0)
        historico = self.repo.list_history(limit=100)

        for row, s in enumerate(historico):
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(str(s.id)))
            self.table.setItem(row, 1, QTableWidgetItem(format_datetime_br(s.data_inicio)))
            self.table.setItem(row, 2, QTableWidgetItem(format_datetime_br(s.data_fim) if s.data_fim else "-"))
            self.table.setItem(row, 3, QTableWidgetItem(s.fonte))
            self.table.setItem(row, 4, QTableWidgetItem(str(s.total_recebidos)))
            self.table.setItem(row, 5, QTableWidgetItem(str(s.novos)))
            self.table.setItem(row, 6, QTableWidgetItem(str(s.atualizados)))

            # Status estilizado
            item_status = QTableWidgetItem(s.status)
            if s.status == "Concluída":
                item_status.setForeground(Qt.GlobalColor.darkGreen)
            elif s.status == "Concluída com ressalvas":
                item_status.setForeground(Qt.GlobalColor.darkYellow)
            elif s.status == "Interrompida":
                item_status.setForeground(Qt.GlobalColor.darkCyan)
            else:
                item_status.setForeground(Qt.GlobalColor.red)
            self.table.setItem(row, 7, item_status)

            erros_resumo = (s.erros[:80] + "...") if s.erros and len(s.erros) > 80 else (s.erros or "Nenhum")
            item_erro = QTableWidgetItem(erros_resumo)
            item_erro.setData(Qt.ItemDataRole.UserRole, s.erros or "")
            self.table.setItem(row, 8, item_erro)

    def _mostrar_detalhes_erro(self, index):
        if index.column() == 8:
            erro_completo = self.table.item(index.row(), 8).data(Qt.ItemDataRole.UserRole)
            if erro_completo:
                QMessageBox.information(self, "Detalhes da Sincronização", erro_completo)
