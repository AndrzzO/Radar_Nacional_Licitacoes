"""Testes unitários para persistência, deduplicação e busca no SQLite."""
import pytest
from src.domain.entities import Licitacao, PesquisaSalva
from src.domain.filters import LicitacaoFilter
from src.integrations.pncp_adapter import PNCPAdapter


def test_insert_and_deduplication(procurement_repo, sample_raw_pncp):
    lic = PNCPAdapter.parse_licitacao(sample_raw_pncp)

    # 1. Primeira inserção
    salva, is_new = procurement_repo.upsert(lic)
    assert is_new is True
    assert salva.id is not None
    primeira_data_inclusao = salva.data_inclusao_local

    # 2. Segunda inserção com mesmo número de controle oficial
    sample_raw_pncp["valorTotalEstimado"] = 250000.00
    sample_raw_pncp["objetoCompra"] = "Objeto atualizado pelo órgão"
    lic2 = PNCPAdapter.parse_licitacao(sample_raw_pncp)

    salva2, is_new2 = procurement_repo.upsert(lic2)
    assert is_new2 is False
    assert salva2.id == salva.id  # Mesmo ID interno
    assert salva2.valor_estimado == 250000.00
    assert salva2.objeto == "Objeto atualizado pelo órgão"
    # Data de inclusão original é estritamente preservada
    assert salva2.data_inclusao_local == primeira_data_inclusao


def test_search_filters(procurement_repo, sample_raw_pncp):
    lic = PNCPAdapter.parse_licitacao(sample_raw_pncp)
    procurement_repo.upsert(lic)

    # 1. Busca por UF GO -> Encontra
    f_go = LicitacaoFilter(ufs=["GO"])
    itens, total = procurement_repo.search(f_go)
    assert total == 1
    assert itens[0].numero_controle_pncp == lic.numero_controle_pncp

    # 2. Busca por UF SP -> Não encontra
    f_sp = LicitacaoFilter(ufs=["SP"])
    itens_sp, total_sp = procurement_repo.search(f_sp)
    assert total_sp == 0

    # 3. Busca por Município IBGE 5200258 -> Encontra
    f_mun = LicitacaoFilter(municipios_ibge=["5200258"])
    itens_mun, total_mun = procurement_repo.search(f_mun)
    assert total_mun == 1

    # 4. Busca por palavra-chave 'computadores' -> Encontra
    f_kw = LicitacaoFilter(palavra_chave="computadores")
    itens_kw, total_kw = procurement_repo.search(f_kw)
    assert total_kw == 1

    # 5. Busca por palavra-chave inexistente -> Zero
    f_kw_none = LicitacaoFilter(palavra_chave="medicamentos")
    itens_none, total_none = procurement_repo.search(f_kw_none)
    assert total_none == 0


def test_statistics_calculation(procurement_repo, sample_raw_pncp):
    lic = PNCPAdapter.parse_licitacao(sample_raw_pncp)
    procurement_repo.upsert(lic)

    stats = procurement_repo.get_statistics()
    assert stats["total_registros"] == 1
    assert stats["prazo_aberto"] == 1
    assert stats["prazo_encerrado"] == 0
    assert stats["total_ufs"] == 1
    assert stats["total_orgaos"] == 1


def test_saved_searches(saved_repo):
    p = PesquisaSalva(
        nome="Oportunidades GO TI",
        filtros_json='{"ufs": ["GO"], "palavra_chave": "software"}',
        data_criacao="2026-10-08T10:00:00",
    )
    p_id = saved_repo.save(p)
    assert p_id is not None

    todas = saved_repo.list_all()
    assert len(todas) == 1
    assert todas[0].nome == "Oportunidades GO TI"

    # Atualiza nome
    p.nome = "Oportunidades GO Geral"
    saved_repo.save(p)
    atualizadas = saved_repo.list_all()
    assert atualizadas[0].nome == "Oportunidades GO Geral"

    # Exclui
    saved_repo.delete(p_id)
    assert len(saved_repo.list_all()) == 0
