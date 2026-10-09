"""Cliente HTTP para consulta de estados e municípios na API oficial de localidades do IBGE."""
from typing import List, Optional
import httpx

from src.domain.entities import Estado, Municipio
from src.utils.logging_config import get_logger

logger = get_logger()

IBGE_BASE_URL = "https://servicodados.ibge.gov.br/api/v1/localidades"


class IBGEClient:
    """Cliente para consulta da API oficial de localidades do IBGE."""

    def __init__(self, timeout: float = 15.0):
        self.timeout = timeout
        headers = {
            "User-Agent": "RadarNacionalLicitacoes/1.0 (Windows; Desktop; Localidades IBGE)",
            "Accept": "application/json",
            "Accept-Encoding": "gzip, deflate",
        }
        self.client = httpx.Client(timeout=self.timeout, headers=headers)

    def close(self):
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def get_estados(self) -> List[Estado]:
        """Obtém a lista oficial das 27 Unidades Federativas do Brasil."""
        url = f"{IBGE_BASE_URL}/estados"
        try:
            response = self.client.get(url)
            response.raise_for_status()
            data = response.json()
            estados = []
            for item in data:
                estados.append(
                    Estado(
                        uf_sigla=item.get("sigla", "").upper(),
                        nome=item.get("nome", ""),
                        id_ibge=item.get("id"),
                    )
                )
            return sorted(estados, key=lambda e: e.uf_sigla)
        except Exception as e:
            logger.error(f"Erro ao consultar UFs na API do IBGE: {e}")
            raise

    def get_municipios_por_uf(self, uf_sigla: str) -> List[Municipio]:
        """Obtém a lista oficial de municípios de uma UF específica do IBGE."""
        uf_clean = uf_sigla.strip().upper()
        url = f"{IBGE_BASE_URL}/estados/{uf_clean}/municipios"
        try:
            response = self.client.get(url)
            response.raise_for_status()
            data = response.json()
            municipios = []
            for item in data:
                municipios.append(
                    Municipio(
                        codigo_ibge=str(item.get("id")),
                        nome=item.get("nome", ""),
                        uf_sigla=uf_clean,
                        uf_nome=(((item.get("microrregiao") or {}).get("mesorregiao") or {}).get("UF") or {}).get("nome"),
                    )
                )
            return sorted(municipios, key=lambda m: m.nome)
        except Exception as e:
            logger.error(f"Erro ao consultar municípios de {uf_clean} no IBGE: {e}")
            raise
