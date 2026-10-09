"""Testes unitários para o adaptador de dados do PNCP."""
import pytest
from src.integrations.pncp_adapter import PNCPAdapter
from src.utils.datetime_utils import compute_situacao_prazo


def test_parse_valid_payload(sample_raw_pncp):
    lic = PNCPAdapter.parse_licitacao(sample_raw_pncp)

    assert lic.numero_controle_pncp == "54801121000161-1-000015/2026"
    assert lic.numero_edital == "06/2026"
    assert lic.ano == 2026
    assert lic.sequencial == 15
    assert lic.modalidade_id == 6
    assert lic.modalidade_nome == "Pregão - Eletrônico"
    assert lic.orgao_cnpj == "54801121000161"
    assert lic.orgao_nome == "MUNICÍPIO DE TESTE GOIÁS"
    assert lic.esfera_id == "M"
    assert lic.esfera_nome == "Municipal"
    assert lic.poder_id == "E"
    assert lic.poder_nome == "Executivo"
    assert lic.uf_sigla == "GO"
    assert lic.uf_nome == "Goiás"
    assert lic.municipio_nome == "Águas Lindas de Goiás"
    assert lic.municipio_ibge == "5200258"
    assert lic.valor_estimado == 199840.50
    assert lic.valor_homologado is None
    assert lic.link_pncp == "https://pncp.gov.br/app/editais/54801121000161/2026/15"
    assert lic.situacao_prazo == "Aberto"
    assert lic.fonte_dados == "PNCP"
    assert "Aquisição de computadores" in (lic.objeto or "")


def test_parse_payload_missing_and_null_fields():
    minimal_raw = {
        "numeroControlePNCP": "00000000000191-1-000001/2026",
        "anoCompra": 2026,
        "sequencialCompra": 1,
        "valorTotalEstimado": None,
        "orgaoEntidade": {
            "cnpj": "00000000000191",
            "razaoSocial": "ENTIDADE FEDERAL",
            "esferaId": "F"
        }
    }
    lic = PNCPAdapter.parse_licitacao(minimal_raw)

    assert lic.numero_controle_pncp == "00000000000191-1-000001/2026"
    assert lic.valor_estimado is None  # Não deve inventar 0.00
    assert lic.esfera_nome == "Federal"
    assert lic.uf_sigla is None
    assert lic.municipio_nome is None
    assert lic.situacao_prazo == "Não informado"
    assert lic.link_pncp == "https://pncp.gov.br/app/editais/00000000000191/2026/1"


def test_compute_situacao_prazo():
    # Prazo futuro
    assert compute_situacao_prazo("2099-12-31T23:59:59") == "Aberto"
    # Prazo passado
    assert compute_situacao_prazo("2020-01-01T10:00:00") == "Encerrado"
    # Sem data
    assert compute_situacao_prazo(None) == "Não informado"
    assert compute_situacao_prazo("") == "Não informado"
