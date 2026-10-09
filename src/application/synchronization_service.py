"""Serviço para atualizações e sincronização incremental dos registros."""
from typing import Dict, Any, Optional, Callable
from src.database.repositories import ProcurementRepository, SyncRepository
from src.integrations.pncp_client import PNCPClient
from src.domain.filters import LicitacaoFilter
from src.application.collection_service import CollectionService
from src.utils.logging_config import get_logger

logger = get_logger()


class SynchronizationService:
    """Gerencia sincronizações incrementais e atualizações de registros conhecidos."""

    def __init__(
        self,
        procurement_repo: ProcurementRepository,
        sync_repo: SyncRepository,
        pncp_client: Optional[PNCPClient] = None,
    ):
        self.repo = procurement_repo
        self.sync_repo = sync_repo
        self.client = pncp_client or PNCPClient()
        self.collection_service = CollectionService(procurement_repo, sync_repo, self.client)

    def sync_open_proposals(
        self,
        filtros: LicitacaoFilter,
        on_progress: Optional[Callable[[str, int, int, int, int, int], None]] = None,
        is_cancelled: Optional[Callable[[], bool]] = None,
    ) -> Dict[str, Any]:
        """
        Executa sincronização de oportunidades abertas, atualizando editais existentes
        e inserindo novas publicações de forma incremental.
        """
        logger.info("Iniciando sincronização incremental de propostas abertas...")
        from copy import deepcopy
        from datetime import timedelta
        from src.utils.datetime_utils import get_current_time_sp
        f=deepcopy(filtros)
        f.status_proposta='todas'
        current=get_current_time_sp()
        if not f.data_publicacao_inicio: f.data_publicacao_inicio=(current-timedelta(days=7)).date().isoformat()
        if not f.data_publicacao_fim: f.data_publicacao_fim=current.date().isoformat()
        # Datas representam atualização global neste fluxo explícito.
        return self.collection_service.run_collection(f,on_progress,is_cancelled,collection_mode='updates')

    def run_collection(self,filtros,on_progress=None,is_cancelled=None):
        return self.sync_open_proposals(filtros,on_progress,is_cancelled)
