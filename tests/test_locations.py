"""Testes unitários para o serviço de estados e municípios do IBGE."""
import pytest
from unittest.mock import MagicMock

from src.application.location_service import LocationService, FALLBACK_ESTADOS
from src.domain.entities import Estado, Municipio


def test_location_service_fallback(location_repo):
    # Simula cliente IBGE indisponível
    mock_ibge = MagicMock()
    mock_ibge.get_estados.side_effect = Exception("Sem conexão")

    service = LocationService(location_repo, mock_ibge)
    estados = service.get_all_estados()

    assert len(estados) == 27
    siglas = {e.uf_sigla for e in estados}
    assert "GO" in siglas
    assert "DF" in siglas
    assert "SP" in siglas


def test_location_service_cache_municipios(location_repo):
    mock_ibge = MagicMock()
    mock_ibge.get_municipios_por_uf.return_value = [
        Municipio("5200258", "Águas Lindas de Goiás", "GO", "Goiás"),
        Municipio("5208707", "Goiânia", "GO", "Goiás"),
    ]

    service = LocationService(location_repo, mock_ibge)

    # Primeira chamada: busca no IBGE e persiste
    muns = service.get_municipios_by_uf("GO")
    assert len(muns) == 2
    assert mock_ibge.get_municipios_por_uf.call_count == 1

    # Segunda chamada: deve vir diretamente do cache local do SQLite
    muns_cached = service.get_municipios_by_uf("GO")
    assert len(muns_cached) == 2
    assert mock_ibge.get_municipios_por_uf.call_count == 1  # Não deve chamar novamente a API


def test_location_service_search_municipios(location_repo):
    service = LocationService(location_repo)
    location_repo.save_municipios([
        Municipio("5200258", "Águas Lindas de Goiás", "GO", "Goiás"),
        Municipio("5208707", "Goiânia", "GO", "Goiás"),
        Municipio("5300108", "Brasília", "DF", "Distrito Federal"),
    ])

    res = service.search_municipios("Goiás", ufs=["GO"])
    assert len(res) == 1
    assert res[0].nome == "Águas Lindas de Goiás"
