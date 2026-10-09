"""Testes unitários para o cliente HTTP do PNCP com mocks."""
import pytest
import httpx
from unittest.mock import MagicMock, patch

from src.integrations.pncp_client import PNCPClient, PNCPClientError, PNCPRateLimitError


def test_pncp_client_success():
    client = PNCPClient(max_retries=2, request_interval=0.0)
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "data": [{"numeroControlePNCP": "123"}],
        "totalRegistros": 1,
        "totalPaginas": 1
    }

    with patch.object(client.client, "get", return_value=mock_resp):
        res = client.get_propostas(data_final="20261020", uf="GO")
        assert res["totalRegistros"] == 1
        assert len(res["data"]) == 1


def test_pncp_client_cancellation():
    client = PNCPClient(max_retries=3, request_interval=0.0)
    cancelled = True

    with pytest.raises(PNCPClientError, match="cancelada pelo usuário"):
        client.get_propostas(data_final="20261020", check_cancelled=lambda: cancelled)


def test_pncp_client_retry_on_429():
    client = PNCPClient(max_retries=3, request_interval=0.0)

    # Primeira chamada 429, segunda 200
    resp_429 = MagicMock()
    resp_429.status_code = 429
    resp_429.headers = {"Retry-After": "0"}

    resp_200 = MagicMock()
    resp_200.status_code = 200
    resp_200.json.return_value = {"data": [], "totalRegistros": 0}

    with patch.object(client.client, "get", side_effect=[resp_429, resp_200]):
        with patch.object(client, "_wait"):  # Evita atrasos reais no teste
            res = client.get_propostas(data_final="20261020")
            assert res["totalRegistros"] == 0


def test_pncp_client_exceed_max_retries_429():
    client = PNCPClient(max_retries=2, request_interval=0.0)

    resp_429 = MagicMock()
    resp_429.status_code = 429
    resp_429.headers = {}

    with patch.object(client.client, "get", return_value=resp_429):
        with patch.object(client, "_wait"):
            with pytest.raises(PNCPRateLimitError):
                client.get_propostas(data_final="20261020")
