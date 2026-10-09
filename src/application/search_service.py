"""Serviço de consulta e pesquisa nos registros armazenados localmente."""
from typing import List, Tuple, Optional
from src.database.repositories import ProcurementRepository
from src.domain.entities import Licitacao
from src.domain.filters import LicitacaoFilter


class SearchService:
    """Gerencia consultas locais filtradas aos dados persistidos em SQLite."""

    def __init__(self, procurement_repo: ProcurementRepository):
        self.repo = procurement_repo

    def search_licitacoes(self, filtros: LicitacaoFilter) -> Tuple[List[Licitacao], int]:
        """
        Executa pesquisa nos dados locais aplicando filtros estruturados.
        Retorna (lista_de_licitacoes, total_encontradas).
        """
        return self.repo.search(filtros)

    def get_details(self, numero_controle_pncp: str) -> Optional[Licitacao]:
        """Retorna uma licitação completa pelo identificador único oficial."""
        return self.repo.get_by_pncp_id(numero_controle_pncp)
