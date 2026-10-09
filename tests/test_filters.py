"""Testes unitários para filtros estruturados e consultas."""
import pytest
from src.domain.filters import LicitacaoFilter
from src.integrations.pncp_adapter import PNCPAdapter


def test_filter_serialization():
    f = LicitacaoFilter(
        ufs=["GO", "DF"],
        municipios_ibge=["5200258"],
        esferas=["M", "D"],
        modalidades_ids=[6, 4],
        status_proposta="recebendo_proposta",
        palavra_chave="segurança",
        valor_min=1000.0,
        valor_max=50000.0,
    )

    json_str = f.to_json()
    f_restored = LicitacaoFilter.from_json(json_str)

    assert f_restored.ufs == ["GO", "DF"]
    assert f_restored.municipios_ibge == ["5200258"]
    assert f_restored.esferas == ["M", "D"]
    assert f_restored.modalidades_ids == [6, 4]
    assert f_restored.status_proposta == "recebendo_proposta"
    assert f_restored.palavra_chave == "segurança"
    assert f_restored.valor_min == 1000.0
    assert f_restored.valor_max == 50000.0


def test_filter_database_queries(procurement_repo, sample_raw_pncp):
    # Insere 2 registros distintos
    lic1 = PNCPAdapter.parse_licitacao(sample_raw_pncp)
    procurement_repo.upsert(lic1)

    raw2 = dict(
        sample_raw_pncp,
        numeroControlePNCP="77777777000177-1-000001/2026",
        valorTotalEstimado=50000.0,
        modalidadeId=8, # Dispensa
        objetoCompra="Contratação de serviços de engenharia civil",
        orgaoEntidade={"cnpj": "77777777000177", "razaoSocial": "TRIBUNAL REGIONAL", "esferaId": "F"},
        unidadeOrgao={"ufSigla": "DF", "municipioNome": "Brasília", "codigoIbge": "5300108"},
    )
    lic2 = PNCPAdapter.parse_licitacao(raw2)
    procurement_repo.upsert(lic2)

    # 1. Filtro por Esfera F (Federal) -> deve achar lic2
    f_esfera = LicitacaoFilter(esferas=["F"])
    itens, total = procurement_repo.search(f_esfera)
    assert total == 1
    assert itens[0].numero_controle_pncp == "77777777000177-1-000001/2026"

    # 2. Filtro por Modalidade 6 (Pregão) -> deve achar lic1
    f_mod = LicitacaoFilter(modalidades_ids=[6])
    itens, total = procurement_repo.search(f_mod)
    assert total == 1
    assert itens[0].numero_controle_pncp == "54801121000161-1-000015/2026"

    # 3. Filtro por Faixa de Valor (R$ 10.000 a R$ 60.000) -> deve achar lic2 (50.000)
    f_val = LicitacaoFilter(valor_min=10000.0, valor_max=60000.0)
    itens, total = procurement_repo.search(f_val)
    assert total == 1
    assert itens[0].valor_estimado == 50000.0

    # 4. Filtro por UFs múltiplas (GO e DF) -> deve achar ambos (total 2)
    f_multi_uf = LicitacaoFilter(ufs=["GO", "DF"])
    itens, total = procurement_repo.search(f_multi_uf)
    assert total == 2
