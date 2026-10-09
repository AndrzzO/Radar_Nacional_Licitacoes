"""Worker assíncrono para coleta de dados sem bloqueio da interface gráfica."""
from PySide6.QtCore import QThread, Signal
from src.application.collection_service import CollectionService
from src.domain.filters import LicitacaoFilter
from src.utils.logging_config import get_logger

logger = get_logger()


class CollectionWorker(QThread):
    """Executa a coleta de licitações em background thread do Qt."""

    # Sinais emitidos para a UI
    # (mensagem, pagina_atual, total_paginas, total_recebidos, novos, atualizados)
    progress_updated = Signal(str, int, int, int, int, int)
    collection_finished = Signal(dict)
    collection_error = Signal(str)
    cancelled = Signal()

    def __init__(self, collection_service: CollectionService, filtros: LicitacaoFilter):
        super().__init__()
        self.service = collection_service
        self.filtros = filtros
        self._is_cancelled = False

    def cancel(self):
        """Sinaliza pedido cooperativo de cancelamento."""
        logger.info("Pedido de cancelamento recebido pelo CollectionWorker.")
        self._is_cancelled = True

    def is_cancelled_check(self) -> bool:
        return self._is_cancelled

    def run(self):
        try:
            def on_progress(msg, pag, total_pag, total_rec, novos, atualizados):
                self.progress_updated.emit(msg, pag, total_pag, total_rec, novos, atualizados)

            resultado = self.service.run_collection(
                filtros=self.filtros,
                on_progress=on_progress,
                is_cancelled=self.is_cancelled_check,
            )

            if self._is_cancelled:
                self.cancelled.emit()
            else:
                self.collection_finished.emit(resultado)

        except Exception as e:
            logger.exception(f"Erro fatal no CollectionWorker: {e}")
            self.collection_error.emit(str(e))
