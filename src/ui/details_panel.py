"""Painel e diálogo de visualização detalhada de uma contratação do PNCP."""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
    QPushButton, QGroupBox, QGridLayout, QFrame, QApplication
)
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtCore import QUrl, Qt

from src.domain.entities import Licitacao
from src.domain.normalization import format_currency_br, format_cnpj
from src.utils.datetime_utils import format_datetime_br


class DetailsDialog(QDialog):
    """Janela modal organizada com todos os metadados oficiais da licitação."""

    def __init__(self, licitacao: Licitacao, parent=None):
        super().__init__(parent)
        self.lic = licitacao
        self.setWindowTitle(f"Detalhes da Licitação — {licitacao.numero_controle_pncp}")
        self.resize(800, 680)
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(16, 16, 16, 16)

        # Cabeçalho
        header_frame = QFrame()
        header_frame.setStyleSheet("background-color: #F0F4F8; border-radius: 6px; padding: 10px;")
        header_layout = QVBoxLayout(header_frame)

        title = QLabel(f"<b>Controle PNCP:</b> {self.lic.numero_controle_pncp}")
        title.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        title.setStyleSheet("color: #1B365D;")
        header_layout.addWidget(title)

        sub_info = QLabel(
            f"<b>Modalidade:</b> {self.lic.modalidade_nome or '-'} &nbsp;&nbsp;|&nbsp;&nbsp; "
            f"<b>Situação:</b> <span style='color: {'#0E703C' if self.lic.situacao_prazo == 'Aberto' else '#D4351C'}; font-weight: bold;'>{self.lic.situacao_prazo}</span>"
        )
        header_layout.addWidget(sub_info)
        main_layout.addWidget(header_frame)

        # Grupo: Órgão e Localização
        grid_group = QGroupBox("Identificação do Órgão e Localidade")
        grid = QGridLayout(grid_group)
        grid.setSpacing(8)

        grid.addWidget(QLabel("<b>Órgão:</b>"), 0, 0)
        grid.addWidget(QLabel(self.lic.orgao_nome or "-"), 0, 1)

        grid.addWidget(QLabel("<b>CNPJ:</b>"), 0, 2)
        grid.addWidget(QLabel(format_cnpj(self.lic.orgao_cnpj)), 0, 3)

        grid.addWidget(QLabel("<b>UF:</b>"), 1, 0)
        grid.addWidget(QLabel(f"{self.lic.uf_sigla or '-'} ({self.lic.uf_nome or '-'})"), 1, 1)

        grid.addWidget(QLabel("<b>Município:</b>"), 1, 2)
        grid.addWidget(QLabel(f"{self.lic.municipio_nome or '-'} (IBGE: {self.lic.municipio_ibge or '-'})"), 1, 3)

        grid.addWidget(QLabel("<b>Esfera:</b>"), 2, 0)
        grid.addWidget(QLabel(self.lic.esfera_nome or "-"), 2, 1)

        grid.addWidget(QLabel("<b>Poder:</b>"), 2, 2)
        grid.addWidget(QLabel(self.lic.poder_nome or "-"), 2, 3)

        main_layout.addWidget(grid_group)

        # Grupo: Valores e Datas
        values_group = QGroupBox("Valores e Prazos Oficiais")
        vgrid = QGridLayout(values_group)
        vgrid.setSpacing(8)

        vgrid.addWidget(QLabel("<b>Valor Estimado:</b>"), 0, 0)
        val_est_lbl = QLabel(format_currency_br(self.lic.valor_estimado))
        val_est_lbl.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        val_est_lbl.setStyleSheet("color: #1B365D;")
        vgrid.addWidget(val_est_lbl, 0, 1)

        vgrid.addWidget(QLabel("<b>Data Publicação:</b>"), 0, 2)
        vgrid.addWidget(QLabel(format_datetime_br(self.lic.data_publicacao_pncp)), 0, 3)

        vgrid.addWidget(QLabel("<b>Início das Propostas:</b>"), 1, 0)
        vgrid.addWidget(QLabel(format_datetime_br(self.lic.data_abertura_proposta)), 1, 1)

        vgrid.addWidget(QLabel("<b>Encerramento das Propostas:</b>"), 1, 2)
        vgrid.addWidget(QLabel(format_datetime_br(self.lic.data_encerramento_proposta)), 1, 3)

        main_layout.addWidget(values_group)

        # Grupo: Objeto Completo
        obj_group = QGroupBox("Objeto da Contratação")
        obj_layout = QVBoxLayout(obj_group)
        self.txt_objeto = QTextEdit()
        self.txt_objeto.setReadOnly(True)
        self.txt_objeto.setPlainText(self.lic.objeto or "Nenhum objeto informado.")
        obj_layout.addWidget(self.txt_objeto)

        if self.lic.informacao_complementar:
            obj_layout.addWidget(QLabel("<b>Informações Complementares:</b>"))
            self.txt_comp = QTextEdit()
            self.txt_comp.setReadOnly(True)
            self.txt_comp.setMaximumHeight(80)
            self.txt_comp.setPlainText(self.lic.informacao_complementar)
            obj_layout.addWidget(self.txt_comp)

        main_layout.addWidget(obj_group)

        if self.parent() and hasattr(self.parent(),'search_service'):
            from src.ui.classification_page import ClassificationPanel
            panel=ClassificationPanel(self.parent().search_service.repo.db,self.lic,self)
            panel.changed.connect(self.parent()._pesquisar_localmente)
            panel.manage_requested.connect(self._manage_classification)
            main_layout.addWidget(panel)

        # Botões de Ação
        btn_layout = QHBoxLayout()

        btn_copiar = QPushButton("Copiar Link PNCP")
        btn_copiar.clicked.connect(self._copiar_link)
        btn_layout.addWidget(btn_copiar)

        btn_abrir = QPushButton("Abrir no Portal PNCP")
        btn_abrir.setStyleSheet("background-color: #1B365D; color: white; font-weight: bold; padding: 6px 14px;")
        btn_abrir.clicked.connect(self._abrir_pncp)
        btn_layout.addWidget(btn_abrir)

        btn_layout.addStretch()

        btn_fechar = QPushButton("Fechar")
        btn_fechar.clicked.connect(self.accept)
        btn_layout.addWidget(btn_fechar)

        main_layout.addLayout(btn_layout)

    def _copiar_link(self):
        if self.lic.link_pncp:
            QApplication.clipboard().setText(self.lic.link_pncp)

    def _abrir_pncp(self):
        if self.lic.link_pncp:
            QDesktopServices.openUrl(QUrl(self.lic.link_pncp))

    def _manage_classification(self):
        self.parent().manage_classification.emit()
        self.accept()
