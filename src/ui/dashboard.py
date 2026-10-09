"""Painel Geral com indicadores e métricas consolidadas do banco de dados local."""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QFrame, QScrollArea
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from src.database.repositories import ProcurementRepository
from src.utils.datetime_utils import format_datetime_br


class MetricCard(QFrame):
    """Card visual moderno para apresentação de um indicador numérico."""

    def __init__(self, title: str, value: str = "0", subtitle: str = "", color: str = "#1B365D", parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: white;
                border: 1px solid #E2E8F0;
                border-left: 5px solid {color};
                border-radius: 8px;
                padding: 14px;
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setSpacing(4)
        layout.setContentsMargins(0, 0, 0, 0)

        lbl_title = QLabel(title)
        lbl_title.setFont(QFont("Segoe UI", 9, QFont.Weight.Medium))
        lbl_title.setStyleSheet("color: #64748B; border: none;")
        layout.addWidget(lbl_title)

        self.lbl_value = QLabel(value)
        self.lbl_value.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))
        self.lbl_value.setStyleSheet(f"color: {color}; border: none;")
        layout.addWidget(self.lbl_value)

        if subtitle:
            lbl_sub = QLabel(subtitle)
            lbl_sub.setFont(QFont("Segoe UI", 8))
            lbl_sub.setStyleSheet("color: #94A3B8; border: none;")
            layout.addWidget(lbl_sub)

    def set_value(self, val: str):
        self.lbl_value.setText(val)


class DashboardPage(QWidget):
    """Tela do Painel Geral com visão resumida do acervo e indicadores em tempo real."""

    action_navigate_search = Signal()

    def __init__(self, procurement_repo: ProcurementRepository, parent=None):
        super().__init__(parent)
        self.repo = procurement_repo
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(20)

        # Cabeçalho da página
        header_layout = QHBoxLayout()
        header_text = QVBoxLayout()
        title = QLabel("Painel Geral — Radar Nacional de Licitações")
        title.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        title.setStyleSheet("color: #0F172A;")
        header_text.addWidget(title)

        desc = QLabel("Visão panorâmica dos registros oficiais de contratações públicas armazenados localmente.")
        desc.setFont(QFont("Segoe UI", 10))
        desc.setStyleSheet("color: #475569;")
        header_text.addWidget(desc)
        header_layout.addLayout(header_text)
        header_layout.addStretch()

        btn_primeira_coleta = QPushButton("Realizar Coleta Online")
        btn_primeira_coleta.setStyleSheet("""
            QPushButton {
                background-color: #1B365D;
                color: white;
                font-weight: bold;
                font-size: 13px;
                padding: 10px 20px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #2A4D7E;
            }
        """)
        btn_primeira_coleta.clicked.connect(self.action_navigate_search.emit)
        header_layout.addWidget(btn_primeira_coleta)

        main_layout.addLayout(header_layout)

        # Grade de Indicadores (Cards)
        cards_layout = QGridLayout()
        cards_layout.setSpacing(16)

        self.card_total = MetricCard("Total de Contratações", "0", "Acervo total armazenado", "#1B365D")
        self.card_aberto = MetricCard("Prazo de Propostas Aberto", "0", "Oportunidades ativas para envio", "#0E703C")
        self.card_encerrado = MetricCard("Prazo Encerrado", "0", "Propostas finalizadas", "#D4351C")
        self.card_nao_inf = MetricCard("Sem Data de Encerramento", "0", "Sem prazo informado pela fonte", "#D97706")

        self.card_ufs = MetricCard("Unidades Federativas", "0", "UFs distintas representadas", "#0284C7")
        self.card_orgaos = MetricCard("Órgãos Públicos", "0", "Entidades compradoras cadastradas", "#4F46E5")
        self.card_novos = MetricCard("Novos na Última Coleta", "0", "Inseridos na operação mais recente", "#059669")
        self.card_sync = MetricCard("Última Sincronização", "Nenhuma", "Data da última atualização concluída", "#475569")

        cards_layout.addWidget(self.card_total, 0, 0)
        cards_layout.addWidget(self.card_aberto, 0, 1)
        cards_layout.addWidget(self.card_encerrado, 0, 2)
        cards_layout.addWidget(self.card_nao_inf, 0, 3)

        cards_layout.addWidget(self.card_ufs, 1, 0)
        cards_layout.addWidget(self.card_orgaos, 1, 1)
        cards_layout.addWidget(self.card_novos, 1, 2)
        cards_layout.addWidget(self.card_sync, 1, 3)

        main_layout.addLayout(cards_layout)

        # Painel informativo com orientações
        info_frame = QFrame()
        info_frame.setStyleSheet("""
            QFrame {
                background-color: #F8FAFC;
                border: 1px solid #E2E8F0;
                border-radius: 8px;
                padding: 16px;
            }
        """)
        info_layout = QVBoxLayout(info_frame)
        info_title = QLabel("Como utilizar o Radar Nacional de Licitações")
        info_title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        info_title.setStyleSheet("color: #1E293B;")
        info_layout.addWidget(info_title)

        info_steps = QLabel(
            "<b>1. Pesquisar e Coletar:</b> Vá para a tela <i>Pesquisar Licitações</i> para buscar dados oficiais online do PNCP ou consultar o acervo local.<br>"
            "<b>2. Filtros e Localização:</b> Filtre por UFs (ex: GO e DF), municípios com código IBGE, esfera administrativa, modalidade ou palavras-chave.<br>"
            "<b>3. Funcionamento Offline:</b> Todos os registros já coletados permanecem armazenados localmente no seu computador e podem ser consultados sem internet.<br>"
            "<b>4. Exportação para Excel:</b> Exporte os resultados para planilhas profissionais no formato XLSX com colunas estruturadas com categorias por regras locais."
        )
        info_steps.setFont(QFont("Segoe UI", 10))
        info_steps.setStyleSheet("color: #334155; line-height: 140%;")
        info_layout.addWidget(info_steps)

        main_layout.addWidget(info_frame)
        main_layout.addStretch()

        self.refresh_metrics()

    def refresh_metrics(self):
        """Recarrega os indicadores reais a partir do banco de dados local."""
        stats = self.repo.get_statistics()
        self.card_total.set_value(f"{stats['total_registros']:,}".replace(",", "."))
        self.card_aberto.set_value(f"{stats['prazo_aberto']:,}".replace(",", "."))
        self.card_encerrado.set_value(f"{stats['prazo_encerrado']:,}".replace(",", "."))
        self.card_nao_inf.set_value(f"{stats['prazo_nao_informado']:,}".replace(",", "."))

        self.card_ufs.set_value(str(stats["total_ufs"]))
        self.card_orgaos.set_value(f"{stats['total_orgaos']:,}".replace(",", "."))
        self.card_novos.set_value(f"{stats['novos_ultima_sinc']:,}".replace(",", "."))

        dt_sync = stats["data_ultima_sinc"]
        if dt_sync:
            self.card_sync.set_value(format_datetime_br(dt_sync))
        else:
            self.card_sync.set_value("Nenhuma")
