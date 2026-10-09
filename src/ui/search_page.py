"""Tela principal de pesquisa e coleta de licitações públicas."""
import os
from copy import deepcopy
from src.classification.store import ClassificationStore
from src.workers.task_worker import TaskWorker
from src.database.repositories import SavedSearchRepository, SettingsRepository
from src.domain.entities import PesquisaSalva
from PySide6.QtWidgets import QInputDialog, QScrollArea, QMenu, QSizePolicy
from pathlib import Path
from typing import Optional, List
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QLineEdit, QComboBox, QCheckBox, QGroupBox,
    QDateEdit, QProgressBar, QTableView, QHeaderView, QSplitter,
    QMessageBox, QFileDialog, QFrame
)
from PySide6.QtCore import Qt, QDate, Signal, Slot
from PySide6.QtGui import QFont, QDesktopServices
from PySide6.QtCore import QUrl

from src.application.collection_service import CollectionService
from src.application.export_service import ExportService
from src.application.location_service import LocationService
from src.application.search_service import SearchService
from src.domain.filters import LicitacaoFilter
from src.domain.validation import parse_currency_input
from src.utils.datetime_utils import parse_datetime
from src.ui.components.uf_selector import UFSelectorWidget
from src.ui.components.municipio_selector import MunicipioSelectorWidget
from src.ui.details_panel import DetailsDialog
from src.ui.results_table import ResultsTableModel
from src.utils.datetime_utils import get_current_time_sp
from src.utils.file_utils import get_default_export_dir
from src.utils.logging_config import get_logger
from src.workers.collection_worker import CollectionWorker
from src.workers.export_worker import ExportWorker

logger = get_logger()

# Modalidades oficiais mapeadas do PNCP
from src.domain.modalities import MODALITIES
MODALIDADES_OPCOES = [('Todas as modalidades',None)]+[(f'{name} ({id_})',id_) for id_,name in MODALITIES.items()]


class SearchPage(QWidget):
    """Tela mais importante da aplicação: filtros, coleta online, consulta local e exportação."""

    stats_changed = Signal()
    manage_classification = Signal()

    def __init__(
        self,
        search_service: SearchService,
        collection_service: CollectionService,
        export_service: ExportService,
        location_service: LocationService,
        parent=None,
    ):
        super().__init__(parent)
        self.search_service = search_service
        self.collection_service = collection_service
        self.export_service = export_service
        self.location_service = location_service

        self.query_worker = None
        self.current_offset = 0
        self.active_filters = None
        self.loaded_filters = None
        self.worker: Optional[CollectionWorker] = None
        self.export_worker: Optional[ExportWorker] = None

        self._init_ui()
        # Executa pesquisa local inicial ao abrir
        self._pesquisar_localmente()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # Divisor ajustável entre Área A (Filtros) e Áreas B/C (Ações e Tabela)
        self.splitter = QSplitter(Qt.Orientation.Vertical)

        # -------------------------------------------------------------
        # ÁREA A — FILTROS
        # -------------------------------------------------------------
        self.filters_container = QWidget()
        filters_layout = QVBoxLayout(self.filters_container)
        filters_layout.setContentsMargins(0, 0, 0, 0)
        filters_layout.setSpacing(8)

        # Cabeçalho dos filtros com botão para recolher
        filter_header = QHBoxLayout()
        lbl_filtros_title = QLabel("<b>Filtros de Pesquisa</b> (Portal Nacional de Contratações Públicas)")
        lbl_filtros_title.setFont(QFont("Segoe UI", 10))
        filter_header.addWidget(lbl_filtros_title)
        filter_header.addStretch()

        self.btn_toggle_filters = QPushButton("Recolher Filtros ▲")
        self.btn_toggle_filters.setFlat(True)
        self.btn_toggle_filters.setStyleSheet("color: #0284C7; font-weight: bold;")
        self.btn_toggle_filters.clicked.connect(self._toggle_filters)
        filter_header.addWidget(self.btn_toggle_filters)
        filters_layout.addLayout(filter_header)

        # Painel de Filtros em Grid
        self.filters_frame = QFrame()
        self.filters_frame.setObjectName("filtersPanel")
        self.filters_frame.setStyleSheet("""
            QFrame#filtersPanel {
                background-color: #F8FAFC;
                border: 1px solid #E2E8F0;
                border-radius: 6px;
                padding: 10px;
            }
        """)
        grid_filters = QGridLayout(self.filters_frame)
        grid_filters.setSpacing(10)

        # Linha 0: UFs e Municípios
        grid_filters.addWidget(QLabel("<b>Estados (UFs):</b>"), 0, 0)
        self.uf_selector = UFSelectorWidget(self.location_service, initial_ufs=["GO", "DF"])
        self.uf_selector.selection_changed.connect(self._on_ufs_changed)
        grid_filters.addWidget(self.uf_selector, 0, 1)

        grid_filters.addWidget(QLabel("<b>Municípios:</b>"), 0, 2)
        self.mun_selector = MunicipioSelectorWidget(self.location_service)
        grid_filters.addWidget(self.mun_selector, 0, 3)

        # Linha 1: Esferas e Situação
        grid_filters.addWidget(QLabel("<b>Esferas:</b>"), 1, 0)
        esferas_box = QHBoxLayout()
        self.chk_esfera_m = QCheckBox("Municipal (M)")
        self.chk_esfera_e = QCheckBox("Estadual (E)")
        self.chk_esfera_f = QCheckBox("Federal (F)")
        self.chk_esfera_d = QCheckBox("Distrital (D)")
        # Todos marcados por padrão reproduzindo link do proprietário esferas=M|D|E|F
        for chk in (self.chk_esfera_m, self.chk_esfera_e, self.chk_esfera_f, self.chk_esfera_d):
            chk.setChecked(True)
            esferas_box.addWidget(chk)
        esferas_box.addStretch()
        grid_filters.addLayout(esferas_box, 1, 1)

        grid_filters.addWidget(QLabel("<b>Situação Propostas:</b>"), 1, 2)
        self.combo_situacao = QComboBox()
        self.combo_situacao.addItems([
            "Recebendo Propostas (Aberto)",
            "Todas as Situações",
            "Propostas Encerradas"
        ])
        grid_filters.addWidget(self.combo_situacao, 1, 3)

        # Linha 2: Modalidade e Palavra-chave
        grid_filters.addWidget(QLabel("<b>Modalidade:</b>"), 2, 0)
        self.combo_modalidade = QComboBox()
        for label, _ in MODALIDADES_OPCOES:
            self.combo_modalidade.addItem(label)
        grid_filters.addWidget(self.combo_modalidade, 2, 1)

        grid_filters.addWidget(QLabel("<b>Palavra-chave (Objeto):</b>"), 2, 2)
        self.txt_palavra_chave = QLineEdit()
        self.txt_palavra_chave.setPlaceholderText("Ex: software, limpeza, veículos, reforma...")
        grid_filters.addWidget(self.txt_palavra_chave, 2, 3)

        # Linha 3: Órgão e Faixa de Valor
        grid_filters.addWidget(QLabel("<b>Órgão / CNPJ:</b>"), 3, 0)
        self.txt_orgao = QLineEdit()
        self.txt_orgao.setPlaceholderText("Nome da instituição ou CNPJ...")
        grid_filters.addWidget(self.txt_orgao, 3, 1)

        grid_filters.addWidget(QLabel("<b>Faixa de Valor (R$):</b>"), 3, 2)
        val_box = QHBoxLayout()
        self.txt_val_min = QLineEdit()
        self.txt_val_min.setPlaceholderText("Mínimo")
        self.txt_val_max = QLineEdit()
        self.txt_val_max.setPlaceholderText("Máximo")
        val_box.addWidget(self.txt_val_min)
        val_box.addWidget(QLabel("até"))
        val_box.addWidget(self.txt_val_max)
        grid_filters.addLayout(val_box, 3, 3)

        # Linha 4: Prazos e Atalhos de Dias
        grid_filters.addWidget(QLabel("<b>Prazo Propostas:</b>"), 4, 0)
        dias_box = QHBoxLayout()
        btn_3d = QPushButton("Próximos 3d")
        btn_7d = QPushButton("7d")
        btn_15d = QPushButton("15d")
        btn_30d = QPushButton("30d")
        btn_todos_dias = QPushButton("Qualquer")
        for b, d in [(btn_3d, 3), (btn_7d, 7), (btn_15d, 15), (btn_30d, 30)]:
            b.clicked.connect(lambda _, days=d: self._set_prazo_dias(days))
            dias_box.addWidget(b)
        btn_todos_dias.clicked.connect(lambda: self._set_prazo_dias(None))
        dias_box.addWidget(btn_todos_dias)
        self.current_prazo_dias: Optional[int] = None
        grid_filters.addLayout(dias_box, 4, 1)

        # Botão Limpar Filtros
        btn_limpar_filtros = QPushButton("Limpar Todos os Filtros")
        btn_limpar_filtros.clicked.connect(self._reset_filtros)
        grid_filters.addWidget(btn_limpar_filtros, 4, 3, Qt.AlignmentFlag.AlignRight)

        self.class_category=QComboBox(); self.class_subcategory=QComboBox(); self.class_confidence=QComboBox()
        self.class_confidence.addItems(['Todas as confianças','Alta','Média','Baixa','Manual','Não Classificado'])
        self.class_origin=QComboBox(); self.class_origin.addItem('Todas as origens',None); self.class_origin.addItem('Automática','automatic'); self.class_origin.addItem('Manual','manual')
        self.class_primary=QCheckBox('Somente categoria principal'); self.class_unclassified=QCheckBox('Não classificados')
        grid_filters.addWidget(QLabel('Categoria'),5,0); grid_filters.addWidget(self.class_category,5,1); grid_filters.addWidget(QLabel('Subcategoria'),5,2); grid_filters.addWidget(self.class_subcategory,5,3)
        grid_filters.addWidget(self.class_confidence,6,0); grid_filters.addWidget(self.class_origin,6,1); grid_filters.addWidget(self.class_primary,6,2); grid_filters.addWidget(self.class_unclassified,6,3)
        self.class_category.currentIndexChanged.connect(self.refresh_subcategories)
        self.refresh_classification_filters()
        self.date_fields={}
        for row,(key,label) in enumerate([('data_publicacao_inicio','Publicação inicial'),('data_publicacao_fim','Publicação final'),('data_encerramento_inicio','Encerramento inicial'),('data_encerramento_fim','Encerramento final')],7):
            box=QCheckBox(label); date=QDateEdit(QDate.currentDate()); date.setCalendarPopup(True); date.setDisplayFormat('dd/MM/yyyy'); date.setEnabled(False); box.toggled.connect(date.setEnabled)
            grid_filters.addWidget(box,row,0); grid_filters.addWidget(date,row,1); self.date_fields[key]=(box,date)
        grid_filters.addWidget(QLabel('Coleta: propostas até 90 dias por padrão; demais situações usam publicações dos últimos 30 dias. Ajuste as datas para ampliar.'),11,0,1,4)
        scroller=QScrollArea(); scroller.setWidgetResizable(True); scroller.setWidget(self.filters_frame)
        filters_layout.addWidget(scroller)
        self.splitter.addWidget(self.filters_container)

        # -------------------------------------------------------------
        # ÁREA B & C — AÇÕES, SITUAÇÃO E TABELA DE RESULTADOS
        # -------------------------------------------------------------
        results_container = QWidget()
        results_layout = QVBoxLayout(results_container)
        results_layout.setContentsMargins(0, 0, 0, 0)
        results_layout.setSpacing(10)

        # Barra de Ações
        actions_bar = QGridLayout()
        actions_bar.setSpacing(10)

        self.btn_pesquisar_local = QPushButton("Pesquisar no banco")
        self.btn_pesquisar_local.setStyleSheet("""
            QPushButton {
                background-color: #0284C7;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #0369A1; }
        """)
        self.btn_pesquisar_local.clicked.connect(self._pesquisar_localmente)
        actions_bar.addWidget(self.btn_pesquisar_local,0,0)

        self.btn_coletar_online = QPushButton("Coletar do PNCP")
        self.btn_coletar_online.setStyleSheet("""
            QPushButton {
                background-color: #1B365D;
                color: white;
                font-weight: bold;
                padding: 8px 18px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #2A4D7E; }
        """)
        self.btn_coletar_online.clicked.connect(self._iniciar_coleta_online)
        actions_bar.addWidget(self.btn_coletar_online,0,1)
        self.btn_sync=QPushButton('Sincronizar alterações')
        self.btn_sync.clicked.connect(self._sync_updates)
        actions_bar.addWidget(self.btn_sync,0,2)

        self.btn_cancelar = QPushButton("Cancelar Coleta")
        self.btn_cancelar.setEnabled(False)
        self.btn_cancelar.setStyleSheet("""
            QPushButton:enabled {
                background-color: #DC2626;
                color: white;
                font-weight: bold;
                padding: 8px 14px;
                border-radius: 4px;
            }
        """)
        self.btn_cancelar.clicked.connect(self._cancelar_coleta)
        actions_bar.addWidget(self.btn_cancelar,0,3)



        self.btn_exportar = QPushButton("Exportar Excel")
        self.btn_exportar.setStyleSheet("""
            QPushButton {
                background-color: #0E703C;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #14804A; }
        """)
        self.btn_exportar.clicked.connect(self._exportar_excel)
        actions_bar.addWidget(self.btn_exportar,0,4)



        # Badges de Contadores em tempo real
        self.badge_total = QLabel("Encontrados: <b>0</b>")
        self.badge_novos = QLabel("Novos: <b>0</b>")
        self.badge_atualizados = QLabel("Atualizados: <b>0</b>")
        for col,b in enumerate((self.badge_total, self.badge_novos, self.badge_atualizados)):
            b.setStyleSheet("background-color: #F1F5F9; border: 1px solid #CBD5E1; border-radius: 4px; padding: 4px 8px;")
            actions_bar.addWidget(b,1,col)

        results_layout.addLayout(actions_bar)

        # Barra de Progresso e Mensagem de Situação
        status_bar_layout = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #E2E8F0;
                border-radius: 4px;
                background-color: #F1F5F9;
            }
            QProgressBar::chunk {
                background-color: #1B365D;
                border-radius: 3px;
            }
        """)
        status_bar_layout.addWidget(self.progress_bar, 1)

        self.lbl_status_msg = QLabel("Pronto para pesquisar ou coletar.")
        self.lbl_status_msg.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Preferred)
        self.lbl_status_msg.setStyleSheet("color: #475569; font-size: 11px;")
        status_bar_layout.addWidget(self.lbl_status_msg,2)
        results_layout.addLayout(status_bar_layout)

        # Barra de Seleção da Tabela
        table_controls = QHBoxLayout()
        btn_sel_all = QPushButton("Selecionar página")
        btn_sel_all.clicked.connect(lambda: self.table_model.select_all(True))
        btn_desel_all = QPushButton("Desmarcar Todos")
        btn_desel_all.clicked.connect(lambda: self.table_model.select_all(False))

        btn_ver_detalhes = QPushButton("Ver Detalhes do Registro")
        btn_ver_detalhes.clicked.connect(self._abrir_detalhes_selecionado)

        btn_abrir_link = QPushButton("Abrir no PNCP")
        btn_abrir_link.clicked.connect(self._abrir_link_selecionado)

        table_controls.addWidget(btn_sel_all)
        table_controls.addWidget(btn_desel_all)
        table_controls.addWidget(btn_ver_detalhes)
        table_controls.addWidget(btn_abrir_link)
        prev=QPushButton('Página anterior'); prev.clicked.connect(lambda:self.change_page(-1)); table_controls.addWidget(prev)
        nxt=QPushButton('Próxima página'); nxt.clicked.connect(lambda:self.change_page(1)); table_controls.addWidget(nxt)
        save=QPushButton('Salvar filtros'); save.clicked.connect(self.save_filters); table_controls.addWidget(save)
        table_controls.addStretch()

        self.lbl_sel_count = QLabel("Selecionados: 0")
        self.lbl_sel_count.setStyleSheet("color: #64748B; font-size: 11px;")
        table_controls.addWidget(self.lbl_sel_count)
        results_layout.addLayout(table_controls)

        # Tabela Profissional de Resultados
        self.table_view = QTableView()
        self.table_model = ResultsTableModel()
        self.table_model.dataChanged.connect(self._atualizar_sel_count)
        self.table_model.modelReset.connect(self._atualizar_sel_count)
        self.table_view.setModel(self.table_model)
        self.table_view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table_view.setAlternatingRowColors(True)
        self.table_view.doubleClicked.connect(self._on_table_double_click)

        # Ajuste de larguras das colunas
        header = self.table_view.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.resizeSection(0, 45)   # Checkbox
        header.resizeSection(1, 210)  # Identificador PNCP
        header.resizeSection(2, 110)  # Edital
        header.resizeSection(3, 260)  # Órgão
        header.resizeSection(4, 140)  # Município
        header.resizeSection(5, 50)   # UF
        header.resizeSection(6, 160)  # Modalidade
        header.resizeSection(7, 340)  # Objeto
        header.resizeSection(8, 130)  # Valor
        header.resizeSection(9, 110)  # Publicação
        header.resizeSection(10, 130) # Prazo
        header.resizeSection(11, 110) # Situação

        results_layout.addWidget(self.table_view)
        self.splitter.addWidget(results_container)

        # Ajuste inicial das proporções do splitter
        self.splitter.setSizes([260, 500])
        main_layout.addWidget(self.splitter)
        self.table_model.sort_requested.connect(self.sort_results)
        self.table_view.setSortingEnabled(True)
        header.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        header.customContextMenuRequested.connect(self.column_menu)
        # Priorizar classificação e objeto; identificadores extensos continuam acessíveis no menu.
        for col in (1,2,6,9): self.table_view.setColumnHidden(col,True)
        for col in (12,13): header.resizeSection(col,170)
        header.resizeSection(14,90); header.resizeSection(15,90)
        for col,position in [(12,1),(13,2),(14,3),(15,4)]: header.moveSection(header.visualIndex(col),position)



    def _toggle_filters(self):
        if self.filters_frame.isVisible():
            self.filters_frame.setVisible(False)
            self.btn_toggle_filters.setText("Expandir Filtros ▼")
        else:
            self.filters_frame.setVisible(True)
            self.btn_toggle_filters.setText("Recolher Filtros ▲")

    def _on_ufs_changed(self, ufs: List[str]):
        self.mun_selector.update_ufs(ufs)

    def _set_prazo_dias(self, days: Optional[int]):
        self.current_prazo_dias = days
        msg = f"Filtro de prazo: próximos {days} dias." if days else "Filtro de prazo: sem restrição de dias."
        self.lbl_status_msg.setText(msg)

    def _construir_filtros(self) -> LicitacaoFilter:
        """Constrói objeto LicitacaoFilter a partir dos controles da UI."""
        ufs = self.uf_selector.get_selected_ufs()
        ibges = self.mun_selector.get_selected_ibges()

        # Esferas
        esferas = []
        if self.chk_esfera_m.isChecked(): esferas.append("M")
        if self.chk_esfera_e.isChecked(): esferas.append("E")
        if self.chk_esfera_f.isChecked(): esferas.append("F")
        if self.chk_esfera_d.isChecked(): esferas.append("D")

        # Situação
        idx_sit = self.combo_situacao.currentIndex()
        if idx_sit == 0:
            status_proposta = "recebendo_proposta"
        elif idx_sit == 2:
            status_proposta = "encerradas"
        else:
            status_proposta = "todas"

        # Modalidade
        idx_mod = self.combo_modalidade.currentIndex()
        modalidade_id = MODALIDADES_OPCOES[idx_mod][1]
        modalidades_ids = [modalidade_id] if modalidade_id is not None else []

        v_min=parse_currency_input(self.txt_val_min.text())
        v_max=parse_currency_input(self.txt_val_max.text())
        if v_min is not None and v_max is not None and v_min>v_max:
            raise ValueError('O valor mínimo não pode superar o máximo.')

        result = LicitacaoFilter(
            ufs=ufs,
            municipios_ibge=ibges,
            esferas=esferas,
            modalidades_ids=modalidades_ids,
            status_proposta=status_proposta,
            prazo_dias=self.current_prazo_dias,
            palavra_chave=self.txt_palavra_chave.text().strip() or None,
            orgao=self.txt_orgao.text().strip() or None,
            valor_min=v_min,
            valor_max=v_max,
            limite=200,
            category_ids=[self.class_category.currentData()] if self.class_category.currentData() and self.class_category.currentData()!=10 else [],
            subcategory_ids=[self.class_subcategory.currentData()] if self.class_subcategory.currentData() else [],
            confidence_levels=[self.class_confidence.currentText()] if self.class_confidence.currentIndex() and self.class_confidence.currentText()!='Não Classificado' else [],
            classification_origin=self.class_origin.currentData(),
            primary_category_only=self.class_primary.isChecked(),
            only_unclassified=self.class_unclassified.isChecked() or self.class_confidence.currentText()=='Não Classificado' or self.class_category.currentData()==10,
        )

        for key,(box,date) in self.date_fields.items():
            setattr(result,key,date.date().toString('yyyy-MM-dd') if box.isChecked() else None)
        if self.loaded_filters:
            # Preservar filtros multivalorados de favoritos que a seleção simples não representa.
            for key in ('modalidades_ids','category_ids','subcategory_ids','confidence_levels'):
                previous=getattr(self.loaded_filters,key)
                current=getattr(result,key)
                if len(previous)>1 and current and current[0]==previous[0]: setattr(result,key,previous)
            result.numero_edital=self.loaded_filters.numero_edital
        for first,last in [('data_publicacao_inicio','data_publicacao_fim'),('data_encerramento_inicio','data_encerramento_fim')]:
            if getattr(result,first) and getattr(result,last) and parse_datetime(getattr(result,first))>parse_datetime(getattr(result,last)):
                raise ValueError('A data inicial não pode ser posterior à final.')
        return result

    def _safe_filters(self):
        try: return self._construir_filtros()
        except (ValueError,TypeError) as error:
            QMessageBox.warning(self,'Filtros inválidos',str(error))
            return None

    def _pesquisar_localmente(self):
        """Executa consulta imediata nos dados armazenados em SQLite."""
        self.current_offset=0
        filtros=self._safe_filters()
        if filtros is not None: self._query(filtros)

    def _query(self,filtros):
        if self.query_worker and self.query_worker.isRunning(): return
        self.active_filters=deepcopy(filtros)
        self.lbl_status_msg.setText('Consultando dados locais...')
        self.btn_pesquisar_local.setEnabled(False)
        self.query_worker=TaskWorker(lambda progress,cancelled:self.search_service.search_licitacoes(filtros),self)
        self.query_worker.result.connect(self._query_result); self.query_worker.error.connect(self._query_error); self.query_worker.finished.connect(self._query_finished); self.query_worker.start()

    @Slot(object)
    def _query_result(self,result):
        itens,total=result; self.total_results=total; self.table_model.set_licitacoes(itens)
        self.badge_total.setText(f'Encontrados: <b>{total}</b>')
        self.lbl_status_msg.setText(f'{len(itens)} de {total} registros; página {self.current_offset//200+1}.')
    @Slot(str)
    def _query_error(self,error): self.lbl_status_msg.setText('Falha de consulta: '+error)
    @Slot()
    def _query_finished(self): self.btn_pesquisar_local.setEnabled(True)

    def change_page(self,delta):
        if self.query_worker and self.query_worker.isRunning(): return
        new=max(0,self.current_offset+delta*200)
        if new>=getattr(self,'total_results',0) and new: return
        self.current_offset=new; f=deepcopy(self.active_filters or self._construir_filtros()); f.offset=new; self._query(f)

    def _iniciar_coleta_online(self,service=None):
        """Inicia a coleta online assíncrona na API do PNCP."""
        if self.worker and self.worker.isRunning(): return
        filtros = self._safe_filters()
        if filtros is None: return
        self.btn_coletar_online.setEnabled(False)
        self.btn_pesquisar_local.setEnabled(False)
        self.btn_cancelar.setEnabled(True)
        self.progress_bar.setValue(0)

        self.worker = CollectionWorker(service if hasattr(service,"run_collection") else self.collection_service, filtros)
        self.worker.progress_updated.connect(self._on_collection_progress)
        self.worker.collection_finished.connect(self._on_collection_finished)
        self.worker.collection_error.connect(self._on_collection_error)
        self.worker.cancelled.connect(self._on_collection_cancelled)
        self.worker.start()

    def _cancelar_coleta(self):
        if self.worker:
            self.lbl_status_msg.setText("Cancelando coleta...")
            self.worker.cancel()

    def _on_collection_progress(self, msg: str, pag: int, total_pag: int, total_rec: int, novos: int, atualizados: int):
        self.lbl_status_msg.setText(msg)
        self.badge_novos.setText(f"Novos: <b>{novos}</b>")
        self.badge_atualizados.setText(f"Atualizados: <b>{atualizados}</b>")
        self.badge_total.setText(f"Recebidos: <b>{total_rec}</b>")
        if total_pag > 0:
            pct = min(int((pag / total_pag) * 100), 100)
            self.progress_bar.setValue(pct)

    def _on_collection_finished(self, resultado: dict):
        self.btn_coletar_online.setEnabled(True)
        self.btn_pesquisar_local.setEnabled(True)
        self.btn_cancelar.setEnabled(False)
        self.progress_bar.setValue(100)
        self.lbl_status_msg.setText(resultado.get("mensagem", "Coleta concluída."))
        self.stats_changed.emit()
        self._pesquisar_localmente()
        if resultado.get('erros'):
            QMessageBox.warning(self,'Coleta incompleta','\n'.join(resultado['erros'][:15]))

    def _on_collection_error(self, err_msg: str):
        self.btn_coletar_online.setEnabled(True)
        self.btn_pesquisar_local.setEnabled(True)
        self.btn_cancelar.setEnabled(False)
        self.lbl_status_msg.setText(f"Erro na coleta: {err_msg}")
        QMessageBox.warning(self, "Falha na Coleta", f"Não foi possível concluir a coleta:\n\n{err_msg}")

    def _on_collection_cancelled(self):
        self.btn_coletar_online.setEnabled(True)
        self.btn_pesquisar_local.setEnabled(True)
        self.btn_cancelar.setEnabled(False)
        self.lbl_status_msg.setText("Coleta cancelada pelo usuário.")
        self._pesquisar_localmente()

    def _atualizar_sel_count(self):
        count = self.table_model.get_selected_count()
        self.lbl_sel_count.setText(f"Selecionados: {count}")

    def _on_table_double_click(self, index):
        lic = self.table_model.get_licitacao(index.row())
        if lic:
            dlg = DetailsDialog(lic, self)
            dlg.exec()

    def _abrir_detalhes_selecionado(self):
        idx = self.table_view.currentIndex()
        if idx.isValid():
            lic = self.table_model.get_licitacao(idx.row())
            if lic:
                dlg = DetailsDialog(lic, self)
                dlg.exec()
        else:
            QMessageBox.information(self, "Aviso", "Selecione uma linha na tabela para ver os detalhes.")

    def _abrir_link_selecionado(self):
        idx = self.table_view.currentIndex()
        if idx.isValid():
            lic = self.table_model.get_licitacao(idx.row())
            if lic and lic.link_pncp:
                QDesktopServices.openUrl(QUrl(lic.link_pncp))
        else:
            QMessageBox.information(self, "Aviso", "Selecione uma linha na tabela para abrir o link.")

    def _exportar_excel(self):
        """Abre diálogo para salvar e dispara a exportação para XLSX."""
        if self.export_worker and self.export_worker.isRunning(): return
        filtros = deepcopy(self.active_filters or self._construir_filtros())
        selected_ids = self.table_model.get_selected_pncp_ids()

        choices=['Todos os resultados filtrados']+(['Somente selecionados'] if selected_ids else [])
        choice,ok=QInputDialog.getItem(self,'Exportar','Conjunto de registros:',choices,0,False)
        if not ok: return
        if choice==choices[0]: selected_ids=None
        export_dir = Path(SettingsRepository(self.search_service.repo.db).get('export_dir',str(get_default_export_dir())))
        agora_sp = get_current_time_sp()
        default_filename = f"Radar_Licitacoes_{agora_sp.strftime('%Y%m%d_%H%M%S')}.xlsx"
        default_path = export_dir / default_filename

        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Salvar Planilha de Licitações",
            str(default_path),
            "Arquivos Excel (*.xlsx)",
        )
        if not filepath:
            return

        self.btn_exportar.setEnabled(False)
        self.lbl_status_msg.setText("Gerando arquivo Excel (.xlsx)...")

        self.export_worker = ExportWorker(
            self.export_service,
            dest_path=filepath,
            filtros=filtros,
            selected_ids=selected_ids,
        )
        self.export_worker.export_finished.connect(self._on_export_finished)
        self.export_worker.export_error.connect(self._on_export_error)
        self.export_worker.start()

    def _on_export_finished(self, filepath: str):
        self.btn_exportar.setEnabled(True)
        self.lbl_status_msg.setText(f"Exportação concluída com sucesso: {filepath}")

        # Mensagem de sucesso com opção de abrir a pasta
        reply = QMessageBox.question(
            self,
            "Exportação Concluída",
            f"O arquivo Excel foi gerado com sucesso em:\n{filepath}\n\nDeseja abrir a pasta onde o arquivo foi salvo?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            folder = os.path.dirname(filepath)
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder))

    def _on_export_error(self, err_msg: str):
        self.btn_exportar.setEnabled(True)
        self.lbl_status_msg.setText(f"Erro na exportação: {err_msg}")
        QMessageBox.critical(self, "Erro na Exportação", f"Falha ao gerar planilha Excel:\n\n{err_msg}")

    def _reset_filtros(self):
        self.uf_selector.set_selected_ufs(["GO", "DF"])
        self.mun_selector.clear()
        for chk in (self.chk_esfera_m, self.chk_esfera_e, self.chk_esfera_f, self.chk_esfera_d):
            chk.setChecked(True)
        self.combo_situacao.setCurrentIndex(0)
        self.combo_modalidade.setCurrentIndex(0)
        self.txt_palavra_chave.clear()
        self.txt_orgao.clear()
        self.txt_val_min.clear()
        self.txt_val_max.clear()
        self.current_prazo_dias = None
        self.loaded_filters=None
        self.class_category.setCurrentIndex(0); self.class_subcategory.setCurrentIndex(0); self.class_confidence.setCurrentIndex(0); self.class_origin.setCurrentIndex(0); self.class_primary.setChecked(False); self.class_unclassified.setChecked(False)
        for box,date in self.date_fields.values(): box.setChecked(False)
        self._pesquisar_localmente()

    def refresh_classification_filters(self):
        catalog,_,_=ClassificationStore(self.search_service.repo.db).catalog(); self.class_catalog=catalog
        previous=self.class_category.currentData(); self.class_category.blockSignals(True); self.class_category.clear(); self.class_category.addItem('Todas as categorias',None)
        for c in catalog['categories']:
            self.class_category.addItem(c['name'],c['id'])
        self.class_category.setCurrentIndex(max(0,self.class_category.findData(previous))); self.class_category.blockSignals(False); self.refresh_subcategories()
    def refresh_subcategories(self,*_):
        previous=self.class_subcategory.currentData(); self.class_subcategory.clear(); self.class_subcategory.addItem('Todas as subcategorias',None)
        for s in self.class_catalog['subcategories']:
            if not self.class_category.currentData() or s['category_id']==self.class_category.currentData(): self.class_subcategory.addItem(s['name'],s['id'])
        self.class_subcategory.setCurrentIndex(max(0,self.class_subcategory.findData(previous)))
    def save_filters(self):
        name,ok=QInputDialog.getText(self,'Salvar pesquisa','Nome:')
        if ok and name.strip():
            filters=self._safe_filters()
            if filters is not None: SavedSearchRepository(self.search_service.repo.db).save(PesquisaSalva(name.strip(),filters.to_json(),get_current_time_sp().isoformat()))
    def apply_filters(self,f):
        self.loaded_filters=f
        self.uf_selector.set_selected_ufs(f.ufs); self.mun_selector.set_selected_ibges(f.municipios_ibge)
        self.txt_palavra_chave.setText(f.palavra_chave or ''); self.txt_orgao.setText(f.orgao or '')
        self.txt_val_min.setText(str(f.valor_min).replace('.',',') if f.valor_min is not None else ''); self.txt_val_max.setText(str(f.valor_max).replace('.',',') if f.valor_max is not None else '')
        for key,check in [('M',self.chk_esfera_m),('D',self.chk_esfera_d),('E',self.chk_esfera_e),('F',self.chk_esfera_f)]: check.setChecked(key in f.esferas)
        self.combo_situacao.setCurrentIndex({'recebendo_proposta':0,'todas':1,'encerradas':2}[f.status_proposta]); self.current_prazo_dias=f.prazo_dias
        self.combo_modalidade.setCurrentIndex(next((i for i,x in enumerate(MODALIDADES_OPCOES) if x[1]==(f.modalidades_ids[0] if f.modalidades_ids else None)),0))
        self.class_category.setCurrentIndex(max(0,self.class_category.findData(f.category_ids[0] if f.category_ids else None)))
        self.class_subcategory.setCurrentIndex(max(0,self.class_subcategory.findData(f.subcategory_ids[0] if f.subcategory_ids else None)))
        self.class_confidence.setCurrentIndex(max(0,self.class_confidence.findText(f.confidence_levels[0] if f.confidence_levels else 'Todas as confianças')))
        self.class_origin.setCurrentIndex(max(0,self.class_origin.findData(f.classification_origin))); self.class_primary.setChecked(f.primary_category_only); self.class_unclassified.setChecked(f.only_unclassified)
        for key,(box,date) in self.date_fields.items():
            value=getattr(f,key); box.setChecked(bool(value))
            if value: date.setDate(QDate.fromString(value.replace('-',''),'yyyyMMdd'))

    def _sync_updates(self):
        if self.worker and self.worker.isRunning(): return
        from src.application.synchronization_service import SynchronizationService
        if QMessageBox.question(self,'Sincronizar alterações oficiais','Consultar atualizações globais, incluindo alterações de situação? Neste fluxo, as datas de publicação do filtro serão usadas como período de atualização; sem datas, serão consultados os últimos 7 dias.')!=QMessageBox.StandardButton.Yes: return
        service=SynchronizationService(self.search_service.repo,self.collection_service.sync_repo,self.collection_service.client)
        self._iniciar_coleta_online(service)

    def sort_results(self,column,order):
        names={2:'numero_edital',3:'orgao_nome',4:'municipio_nome',5:'uf_sigla',8:'valor_estimado',9:'data_publicacao_pncp',10:'data_encerramento_proposta',12:'category_name',13:'subcategory_name',14:'classification_confidence',15:'classification_origin'}
        if column not in names or not self.active_filters: return
        f=deepcopy(self.active_filters); f.ordenar_por=names[column]; f.ordem_asc=order==Qt.SortOrder.AscendingOrder; f.offset=0; self.current_offset=0; self._query(f)
    def column_menu(self,point):
        from src.ui.results_table import COLUMNS
        menu=QMenu(self)
        for col,(name,width) in enumerate(COLUMNS):
            action=menu.addAction(name); action.setCheckable(True); action.setChecked(not self.table_view.isColumnHidden(col)); action.toggled.connect(lambda checked,c=col:self.table_view.setColumnHidden(c,not checked))
        menu.exec(self.table_view.horizontalHeader().mapToGlobal(point))
