"""Tela de configurações, preferências, backup e logs do aplicativo."""
import os
import shutil
import sqlite3
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QLineEdit, QGroupBox, QFileDialog, QMessageBox
)
from PySide6.QtCore import Qt, QUrl, Slot
from src.workers.task_worker import TaskWorker
from PySide6.QtGui import QFont, QDesktopServices

from src.database.repositories import SettingsRepository
from src.utils.file_utils import get_app_dir, get_db_path, get_default_export_dir, get_logs_dir, get_backups_dir
from src.utils.datetime_utils import get_current_time_sp


class SettingsPage(QWidget):
    """Permite ajustar preferências locais, gerenciar backups e inspecionar logs."""

    def __init__(self, settings_repo: SettingsRepository, parent=None):
        super().__init__(parent)
        self.repo = settings_repo
        self.worker = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Cabeçalho
        title = QLabel("Configurações do Aplicativo")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        layout.addWidget(title)

        desc = QLabel("Personalize os parâmetros de conexão, diretórios locais e realize cópias de segurança do banco.")
        desc.setStyleSheet("color: #64748B;")
        layout.addWidget(desc)

        # Grupo: Diretórios e Armazenamento
        grp_dir = QGroupBox("Diretórios e Armazenamento Local")
        grid_dir = QGridLayout(grp_dir)
        grid_dir.setSpacing(10)

        grid_dir.addWidget(QLabel("<b>Banco de Dados SQLite:</b>"), 0, 0)
        lbl_db = QLabel(str(get_db_path()))
        lbl_db.setStyleSheet("background-color: #F1F5F9; padding: 4px 8px; border-radius: 4px;")
        grid_dir.addWidget(lbl_db, 0, 1)

        grid_dir.addWidget(QLabel("<b>Diretório Padrão de Exportação:</b>"), 1, 0)
        self.txt_export_dir = QLineEdit(str(get_default_export_dir()))
        grid_dir.addWidget(self.txt_export_dir, 1, 1)
        btn_sel_export = QPushButton("Alterar...")
        btn_sel_export.clicked.connect(self._selecionar_export_dir)
        grid_dir.addWidget(btn_sel_export, 1, 2)

        layout.addWidget(grp_dir)

        # Grupo: Cópia de Segurança (Backup e Restauração)
        grp_backup = QGroupBox("Cópia de Segurança e Recuperação (Backup)")
        b_layout = QHBoxLayout(grp_backup)
        b_layout.setSpacing(12)

        btn_backup = QPushButton("Criar Backup do Banco de Dados")
        btn_backup.setStyleSheet("background-color: #1B365D; color: white; font-weight: bold; padding: 8px 16px; border-radius: 4px;")
        btn_backup.clicked.connect(self._criar_backup)
        b_layout.addWidget(btn_backup)

        btn_restore = QPushButton("Restaurar Banco de Dados...")
        btn_restore.setStyleSheet("background-color: #64748B; color: white; padding: 8px 16px; border-radius: 4px;")
        btn_restore.clicked.connect(self._restaurar_backup)
        b_layout.addWidget(btn_restore)

        b_layout.addStretch()
        layout.addWidget(grp_backup)

        # Grupo: Auditoria e Logs
        grp_logs = QGroupBox("Logs e Diagnóstico")
        l_layout = QHBoxLayout(grp_logs)
        btn_abrir_log = QPushButton("Abrir Arquivo de Log")
        btn_abrir_log.clicked.connect(self._abrir_log)
        l_layout.addWidget(btn_abrir_log)

        btn_abrir_pasta_app = QPushButton("Abrir Pasta de Dados do Aplicativo")
        btn_abrir_pasta_app.clicked.connect(self._abrir_pasta_app)
        l_layout.addWidget(btn_abrir_pasta_app)

        l_layout.addStretch()
        layout.addWidget(grp_logs)

        # Informações da Versão
        layout.addStretch()
        lbl_versao = QLabel("Radar Nacional de Licitações v1.1.0 — Motor de Coleta e Exportação Oficial PNCP")
        lbl_versao.setStyleSheet("color: #94A3B8; font-size: 11px;")
        layout.addWidget(lbl_versao)

    def _selecionar_export_dir(self):
        folder = QFileDialog.getExistingDirectory(self, "Selecionar Diretório de Exportação", self.txt_export_dir.text())
        if folder:
            self.txt_export_dir.setText(folder)
            self.repo.set("export_dir", folder)

    def _criar_backup(self):
        """Cria cópia consistente do arquivo SQLite utilizando a API de backup nativa."""
        self._run_maintenance(lambda progress,cancelled:self.repo.db.backup(),False)

    def _restaurar_backup(self):
        """Restaura o banco a partir de um backup validado."""
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar Arquivo de Backup",
            str(get_backups_dir()),
            "Banco SQLite (*.sqlite3 *.db)",
        )
        if not filepath:
            return

        reply = QMessageBox.warning(
            self,
            "Confirmar Restauração",
            "ATENÇÃO: A restauração substituirá os registros atuais pelo conteúdo do backup.\n"
            "Deseja realmente continuar?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._run_maintenance(lambda progress,cancelled:self.repo.db.restore(filepath),True)

    def _run_maintenance(self,fn,restore):
        window=self.window()
        if self.worker and self.worker.isRunning(): return
        if hasattr(window,'page_search'):
            page=window.page_search
            workers=[page.worker,page.export_worker,page.query_worker,page.mun_selector.worker,window.page_classification.worker]
            if any(w and w.isRunning() for w in workers):
                QMessageBox.information(self,'Operação em andamento','Aguarde o término da coleta, consulta, exportação ou classificação antes da manutenção.'); return
        self.restoring=restore
        self.worker=TaskWorker(fn,self); self.worker.result.connect(self._maintenance_done); self.worker.error.connect(self._maintenance_error); self.worker.finished.connect(self._maintenance_finished)
        window.setEnabled(False); self.worker.start()
    @Slot(object)
    def _maintenance_done(self,result):
        if self.restoring and hasattr(self.window(),'page_classification'):
            self.window().page_classification.refresh(); self.window().page_search.refresh_classification_filters(); self.window().page_dashboard.refresh_metrics()
        QMessageBox.information(self,'Operação concluída',('Banco restaurado. Backup anterior: ' if self.restoring else 'Backup criado: ')+str(result))
    @Slot(str)
    def _maintenance_error(self,error): QMessageBox.critical(self,'Falha na manutenção',error)
    @Slot()
    def _maintenance_finished(self): self.window().setEnabled(True)

    def _abrir_log(self):
        log_file = get_logs_dir() / "radar.log"
        if log_file.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(log_file)))
        else:
            QMessageBox.information(self, "Aviso", "Nenhum arquivo de log foi gerado ainda.")

    def _abrir_pasta_app(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(get_app_dir())))
