"""Serviço de gerenciamento e cache de estados e municípios do IBGE."""
from typing import List, Optional
from src.database.repositories import LocationRepository
from src.domain.entities import Estado, Municipio
from src.integrations.ibge_client import IBGEClient
from src.utils.logging_config import get_logger

logger = get_logger()

# Lista canônica estática das 27 UFs para fallback instantâneo se offline
FALLBACK_ESTADOS = [
    Estado("AC", "Acre", 12), Estado("AL", "Alagoas", 27), Estado("AP", "Amapá", 16),
    Estado("AM", "Amazonas", 13), Estado("BA", "Bahia", 29), Estado("CE", "Ceará", 23),
    Estado("DF", "Distrito Federal", 53), Estado("ES", "Espírito Santo", 32), Estado("GO", "Goiás", 52),
    Estado("MA", "Maranhão", 21), Estado("MT", "Mato Grosso", 51), Estado("MS", "Mato Grosso do Sul", 50),
    Estado("MG", "Minas Gerais", 31), Estado("PA", "Pará", 15), Estado("PB", "Paraíba", 25),
    Estado("PR", "Paraná", 41), Estado("PE", "Pernambuco", 26), Estado("PI", "Piauí", 22),
    Estado("RJ", "Rio de Janeiro", 33), Estado("RN", "Rio Grande do Norte", 24), Estado("RS", "Rio Grande do Sul", 43),
    Estado("RO", "Rondônia", 11), Estado("RR", "Roraima", 14), Estado("SC", "Santa Catarina", 42),
    Estado("SP", "São Paulo", 35), Estado("SE", "Sergipe", 28), Estado("TO", "Tocantins", 17)
]


class LocationService:
    """Fornece dados de localidades com persistência em cache SQLite local."""

    def __init__(self, location_repo: LocationRepository, ibge_client: Optional[IBGEClient] = None):
        self.repo = location_repo
        self.ibge_client = ibge_client or IBGEClient()

    def get_all_estados(self) -> List[Estado]:
        """Retorna todos os estados a partir do cache local ou consulta a API do IBGE."""
        estados = self.repo.get_estados()
        if estados and len(estados) == 27:
            return estados

        try:
            logger.info("Carregando lista de estados via API oficial do IBGE...")
            estados = self.ibge_client.get_estados()
            self.repo.save_estados(estados)
            return estados
        except Exception as e:
            logger.warning(f"Falha ao consultar IBGE online ({e}). Usando lista padrão de UFs.")
            self.repo.save_estados(FALLBACK_ESTADOS)
            return FALLBACK_ESTADOS

    def get_municipios_by_uf(self, uf: str) -> List[Municipio]:
        """Retorna municípios de uma UF. Se não estiverem no cache, consulta o IBGE e persiste."""
        uf_clean = uf.strip().upper()
        municipios = self.repo.get_municipios_por_uf(uf_clean)
        if municipios:
            return municipios

        try:
            logger.info(f"Carregando municípios da UF {uf_clean} via API do IBGE...")
            municipios = self.ibge_client.get_municipios_por_uf(uf_clean)
            self.repo.save_municipios(municipios)
            return municipios
        except Exception as e:
            logger.error(f"Não foi possível carregar municípios para {uf_clean}: {e}")
            raise RuntimeError(f"Municípios de {uf_clean} indisponíveis e sem cache local: {e}") from e

    def search_municipios(self, query: str, ufs: Optional[List[str]] = None) -> List[Municipio]:
        """Pesquisa municípios pelo nome, com filtro opcional de UFs."""
        return self.repo.search_municipios(query, ufs=ufs)
