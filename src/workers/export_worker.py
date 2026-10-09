"""Worker assíncrono para exportação para Excel sem bloqueio da UI."""
from pathlib import Path
from typing import List, Optional
from PySide6.QtCore import QThread, Signal

from src.application.export_service import ExportService
from src.domain.filters import LicitacaoFilter
from src.utils.logging_config import get_logger

logger = get_logger()


class ExportWorker(QThread):
    """Executa a geração do arquivo Excel em background thread."""

    progress_updated = Signal(int, int)  # current, total
    export_finished = Signal(str)  # filepath
    export_error = Signal(str)

    def __init__(
        self,
        export_service: ExportService,
        dest_path: Path | str,
        filtros: LicitacaoFilter,
        selected_ids: Optional[List[str]] = None,
    ):
        super().__init__()
        self.service = export_service
        self.dest_path = dest_path
        self.filtros = filtros
        self.selected_ids = selected_ids

    def run(self):
        try:
            def on_progress(cur, total):
                self.progress_updated.emit(cur, total)

            result_path = self.service.export_to_excel(
                output_path=self.dest_path,
                filtros=self.filtros,
                selected_pncp_ids=self.selected_ids,
                on_progress=on_progress,
            )
            self.export_finished.emit(str(result_path))
        except Exception as e:
            logger.exception(f"Erro no ExportWorker: {e}")
            self.export_error.emit(str(e))
