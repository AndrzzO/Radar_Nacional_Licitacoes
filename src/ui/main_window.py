"""Janela principal do aplicativo desktop Radar Nacional de Licitações."""
from typing import Optional
from src.domain.filters import LicitacaoFilter
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QPushButton,
    QStackedWidget, QLabel, QFrame, QStatusBar, QApplication
)
from PySide6.QtGui import QFont, QIcon
from PySide6.QtCore import Qt

from src.application.collection_service import CollectionService
from src.application.export_service import ExportService
from src.application.location_service import LocationService
from src.application.search_service import SearchService
from src.database.connection import DatabaseConnection
from src.database.repositories import (
    ProcurementRepository, LocationRepository, SyncRepository,
    SavedSearchRepository, SettingsRepository
)
from src.ui.dashboard import DashboardPage
from src.ui.search_page import SearchPage
from src.ui.saved_searches import SavedSearchesPage
from src.ui.history_page import HistoryPage
from src.ui.settings_page import SettingsPage
from src.ui.classification_page import ClassificationPage
from src.ui.course_page import CoursePage
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QMessageBox


class NavButton(QPushButton):
    """Botão personalizado para o menu lateral de navegação."""

    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setCheckable(True)
        self.setFont(QFont("Segoe UI", 10, QFont.Weight.Medium))
        self.setFixedHeight(44)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #CBD5E1;
                text-align: left;
                padding-left: 20px;
                border: none;
                border-left: 4px solid transparent;
            }
            QPushButton:hover {
                background-color: #1E293B;
                color: white;
            }
            QPushButton:checked {
                background-color: #1E293B;
                color: #38BDF8;
                border-left: 4px solid #38BDF8;
                font-weight: bold;
            }
        """)


class MainWindow(QMainWindow):
    """Janela desktop corporativa com barra de navegação lateral e pilha de telas."""

    def __init__(self, db_conn: DatabaseConnection):
        super().__init__()
        self.db_conn = db_conn

        # Repositórios
        self.procurement_repo = ProcurementRepository(db_conn)
        self.location_repo = LocationRepository(db_conn)
        self.sync_repo = SyncRepository(db_conn)
        self.saved_repo = SavedSearchRepository(db_conn)
        self.settings_repo = SettingsRepository(db_conn)

        # Serviços de Aplicação
        self.location_service = LocationService(self.location_repo)
        self.collection_service = CollectionService(self.procurement_repo, self.sync_repo)
        self.search_service = SearchService(self.procurement_repo)
        self.export_service = ExportService(self.procurement_repo)

        self._init_window()
        self._init_ui()

    def _init_window(self):
        self.setWindowTitle("Radar Nacional de Licitações — Coleta e Monitoramento PNCP")
        # Dimensões adequadas para visualização confortável em telas Full HD
        self.resize(1380, 880)
        self.setMinimumSize(1024, 680)

    def _init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        root_layout = QHBoxLayout(central_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # -------------------------------------------------------------
        # BARRA LATERAL (MENU DE NAVEGAÇÃO)
        # -------------------------------------------------------------
        sidebar = QFrame()
        sidebar.setFixedWidth(240)
        sidebar.setStyleSheet("background-color: #0F172A;")  # Dark slate elegante
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(0, 20, 0, 20)
        side_layout.setSpacing(4)

        # Título / Marca
        brand_box = QVBoxLayout()
        brand_box.setContentsMargins(20, 0, 20, 24)
        lbl_brand = QLabel("RADAR NACIONAL")
        lbl_brand.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        lbl_brand.setStyleSheet("color: white; letter-spacing: 1px;")

        lbl_sub = QLabel("LICITAÇÕES PÚBLICAS")
        lbl_sub.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
        lbl_sub.setStyleSheet("color: #38BDF8; letter-spacing: 0.5px;")

        brand_box.addWidget(lbl_brand)
        brand_box.addWidget(lbl_sub)
        side_layout.addLayout(brand_box)

        # Botões de Navegação
        self.btn_nav_dashboard = NavButton(" Painel Geral")
        self.btn_nav_search = NavButton(" Pesquisar Licitações")
        self.btn_nav_stored = NavButton(" Licitações Armazenadas")
        self.btn_nav_saved = NavButton(" Pesquisas Salvas")
        self.btn_nav_history = NavButton(" Histórico de Coletas")
        self.btn_nav_settings = NavButton(" Configurações")

        self.btn_nav_classification = NavButton(" Classificação Automática")
        self.btn_nav_course = NavButton(" Curso de Licitações")
        self.nav_buttons = [
            self.btn_nav_dashboard,
            self.btn_nav_search,
            self.btn_nav_stored,
            self.btn_nav_saved,
            self.btn_nav_history,
            self.btn_nav_settings,
            self.btn_nav_classification,
            self.btn_nav_course,
        ]

        for i, btn in enumerate(self.nav_buttons):
            btn.clicked.connect(lambda _, index=i: self._navigate(index))
            side_layout.addWidget(btn)

        side_layout.addStretch()

        # Rodapé da Barra Lateral
        footer_box = QVBoxLayout()
        footer_box.setContentsMargins(20, 0, 20, 0)
        lbl_source = QLabel("Fonte: PNCP Oficial")
        lbl_source.setFont(QFont("Segoe UI", 8))
        lbl_source.setStyleSheet("color: #64748B;")
        footer_box.addWidget(lbl_source)
        side_layout.addLayout(footer_box)

        root_layout.addWidget(sidebar)

        # -------------------------------------------------------------
        # ÁREA DE CONTEÚDO (PILHA DE TELAS)
        # -------------------------------------------------------------
        self.stack = QStackedWidget()
        self.stack.setStyleSheet("background-color: #FFFFFF;")

        # Instanciar telas
        self.page_dashboard = DashboardPage(self.procurement_repo)
        self.page_dashboard.action_navigate_search.connect(lambda: self._navigate(1))

        self.page_search = SearchPage(
            self.search_service,
            self.collection_service,
            self.export_service,
            self.location_service,
        )
        self.page_search.stats_changed.connect(self.page_dashboard.refresh_metrics)

        self.page_saved = SavedSearchesPage(self.saved_repo)
        self.page_saved.load_search_signal.connect(self._carregar_pesquisa_salva)

        self.page_history = HistoryPage(self.sync_repo)
        self.page_settings = SettingsPage(self.settings_repo)
        self.page_course = CoursePage(self.settings_repo)
        self.page_classification = ClassificationPage(self.db_conn,self.procurement_repo)
        self.page_classification.changed.connect(self.page_search.refresh_classification_filters)
        self.page_search.manage_classification.connect(lambda:self._navigate(6))

        # Adicionar à pilha:
        # 0: Painel Geral
        # 1: Pesquisar Licitações
        # 2: Licitações Armazenadas (utiliza a tela de pesquisa com foco em dados locais)
        # 3: Pesquisas Salvas
        # 4: Histórico de Coletas
        # 5: Configurações
        self.stack.addWidget(self.page_dashboard)
        self.stack.addWidget(self.page_search)
        self.stack.addWidget(QWidget())  # Índice reservado à consulta local
        self.stack.addWidget(self.page_saved)
        self.stack.addWidget(self.page_history)
        self.stack.addWidget(self.page_settings)
        self.stack.addWidget(self.page_classification)
        self.stack.addWidget(self.page_course)

        root_layout.addWidget(self.stack, 1)

        # Barra de Status
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Radar Nacional de Licitações pronto para uso.")

        # Inicia na primeira tela
        self._navigate(0)

    def _navigate(self, index: int):
        # Desmarca todos e marca o ativo
        for i, btn in enumerate(self.nav_buttons):
            btn.setChecked(i == index)

        if index == 0:
            self.page_dashboard.refresh_metrics()
            self.stack.setCurrentIndex(0)
        elif index == 1:
            self.stack.setCurrentIndex(1)
        elif index == 2:
            # Licitações Armazenadas: pesquisa dados locais imediatamente
            self.stack.setCurrentIndex(1)
            self.page_search._pesquisar_localmente()
        elif index == 3:
            self.page_saved.refresh_list()
            self.stack.setCurrentIndex(3)
        elif index == 4:
            self.page_history.refresh_history()
            self.stack.setCurrentIndex(4)
        elif index == 5:
            self.stack.setCurrentIndex(5)
        elif index == 6:
            self.page_classification.refresh()
            self.stack.setCurrentIndex(6)

        elif index == 7:
            self.page_course.refresh_progress()
            self.stack.setCurrentIndex(7)

    def _carregar_pesquisa_salva(self, json_str: str):
        """Carrega filtros de uma pesquisa favorita diretamente na tela de busca."""
        try:
            filtros = LicitacaoFilter.from_json(json_str)
            self.page_search.apply_filters(filtros)
            self._navigate(1)
            self.page_search._pesquisar_localmente()
        except Exception as e:
            self.status_bar.showMessage(f"Erro ao carregar pesquisa salva: {e}")

    def closeEvent(self,event):
        workers=[self.page_search.worker,self.page_search.export_worker,self.page_search.query_worker,self.page_search.mun_selector.worker,self.page_classification.worker,self.page_settings.worker]
        running=[w for w in workers if w and w.isRunning()]
        if running:
            for worker in running:
                if hasattr(worker,'cancel'): worker.cancel()
            event.ignore()
            self.status_bar.showMessage('Aguardando finalização segura das operações...')
            QTimer.singleShot(300,self.close)
            return
        self.collection_service.client.close(); self.location_service.ibge_client.close()
        event.accept()
