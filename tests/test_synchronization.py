"""Testes unitários para a rotina de coleta e sincronização incremental."""
import pytest
from unittest.mock import MagicMock

from src.application.collection_service import CollectionService
from src.domain.filters import LicitacaoFilter


def test_collection_service_pagination(procurement_repo, sync_repo, sample_raw_pncp):
    mock_client = MagicMock()
    # Simula 2 páginas retornadas
    item_p1 = dict(sample_raw_pncp, numeroControlePNCP="11111111000111-1-000001/2026")
    item_p2 = dict(sample_raw_pncp, numeroControlePNCP="22222222000122-1-000002/2026")

    mock_client.get_propostas.side_effect = [
        {"data": [item_p1], "totalRegistros": 2, "totalPaginas": 2, "numeroPagina": 1},
        {"data": [item_p2], "totalRegistros": 2, "totalPaginas": 2, "numeroPagina": 2},
    ]

    service = CollectionService(procurement_repo, sync_repo, mock_client)
    filtros = LicitacaoFilter(ufs=["GO"], status_proposta="recebendo_proposta")

    progresso_msgs = []
    def on_prog(msg, cur, tot, rec, nov, upd):
        progresso_msgs.append((cur, tot, rec, nov, upd))

    resultado = service.run_collection(filtros, on_progress=on_prog)

    assert resultado["status"] == "Concluída"
    assert resultado["novos"] == 2
    assert resultado["paginas"] == 2
    assert mock_client.get_propostas.call_count == 2

    # Verifica se os registros foram persistidos no repositório
    stats = procurement_repo.get_statistics()
    assert stats["total_registros"] == 2


def test_collection_service_cancellation(procurement_repo, sync_repo, sample_raw_pncp):
    mock_client = MagicMock()
    mock_client.get_propostas.return_value = {
        "data": [sample_raw_pncp], "totalRegistros": 10, "totalPaginas": 10, "numeroPagina": 1
    }

    service = CollectionService(procurement_repo, sync_repo, mock_client)
    filtros = LicitacaoFilter(ufs=["GO"])

    # Cancela imediatamente
    resultado = service.run_collection(filtros, is_cancelled=lambda: True)

    assert resultado["status"] == "Interrompida"
    assert resultado["novos"] == 0
