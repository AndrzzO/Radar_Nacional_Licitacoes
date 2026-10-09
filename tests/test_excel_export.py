"""Testes unitários para exportação profissional para Excel (OpenPyXL)."""
import pytest
from pathlib import Path
from openpyxl import load_workbook

from src.application.export_service import ExportService, HEADER_COLUMNS
from src.domain.filters import LicitacaoFilter
from src.integrations.pncp_adapter import PNCPAdapter
from src.utils.file_utils import sanitize_for_excel


def test_sanitize_for_excel():
    # Texto normal
    assert sanitize_for_excel("Licitação de TI") == "Licitação de TI"
    # Números e bools preservados
    assert sanitize_for_excel(1234.56) == 1234.56
    assert sanitize_for_excel(None) == ""

    # Fórmulas maliciosas sanitizadas com apóstrofo prefixado
    assert sanitize_for_excel("=cmd|'/C calc'!A0") == "'=cmd|'/C calc'!A0"
    assert sanitize_for_excel("+12345") == "'+12345"
    assert sanitize_for_excel("-12345") == "'-12345"
    assert sanitize_for_excel("@SUM(A1:A10)") == "'@SUM(A1:A10)"


def test_excel_export_structure_and_metadata(procurement_repo, temp_dir, sample_raw_pncp):
    # Insere 2 registros
    lic1 = PNCPAdapter.parse_licitacao(sample_raw_pncp)
    procurement_repo.upsert(lic1)

    sample_raw_pncp["numeroControlePNCP"] = "99999999000199-1-000001/2026"
    sample_raw_pncp["objetoCompra"] = "=SOMA(1,2) Objeto com fórmula simulada"
    sample_raw_pncp["valorTotalEstimado"] = None  # Ausente
    lic2 = PNCPAdapter.parse_licitacao(sample_raw_pncp)
    procurement_repo.upsert(lic2)

    export_service = ExportService(procurement_repo)
    dest_file = temp_dir / "teste_export.xlsx"

    filtros = LicitacaoFilter(ufs=["GO"], status_proposta="recebendo_proposta")
    result_path = export_service.export_to_excel(dest_file, filtros)

    assert result_path.exists()

    # Inspeciona o arquivo XLSX gerado com openpyxl
    wb = load_workbook(str(result_path))

    # Verifica as abas obrigatórias
    assert "LICITAÇÕES" in wb.sheetnames
    assert "METADADOS" in wb.sheetnames

    # Inspeciona aba LICITAÇÕES
    ws_lic = wb["LICITAÇÕES"]
    # 25 colunas
    assert ws_lic.max_column == len(HEADER_COLUMNS)
    assert ws_lic.max_column == 31
    # 1 cabeçalho + 2 dados = 3 linhas
    assert ws_lic.max_row == 3

    # Cabeçalho da coluna 1 deve ser ID PNCP
    assert ws_lic.cell(row=1, column=1).value == "ID PNCP"

    # Linha 2: primeiro registro
    assert ws_lic.cell(row=2, column=1).value == "54801121000161-1-000015/2026"
    assert ws_lic.cell(row=2, column=13).value == 199840.50

    # Linha 3: segundo registro com fórmula sanitizada e valor nulo preservado
    obj_cel = ws_lic.cell(row=3, column=12).value
    assert obj_cel.startswith("'=SOMA")
    val_cel = ws_lic.cell(row=3, column=13).value
    assert val_cel is None  # Não inventou 0.00!

    # Inspeciona aba METADADOS
    ws_meta = wb["METADADOS"]
    assert "RADAR NACIONAL DE LICITAÇÕES" in str(ws_meta.cell(row=1, column=1).value)
    # Total de registros exportados
    assert ws_meta.cell(row=5, column=2).value == 2


def test_excel_export_selected_only(procurement_repo, temp_dir, sample_raw_pncp):
    lic1 = PNCPAdapter.parse_licitacao(sample_raw_pncp)
    procurement_repo.upsert(lic1)

    sample_raw_pncp["numeroControlePNCP"] = "88888888000188-1-000001/2026"
    lic2 = PNCPAdapter.parse_licitacao(sample_raw_pncp)
    procurement_repo.upsert(lic2)

    export_service = ExportService(procurement_repo)
    dest_file = temp_dir / "teste_selecionados.xlsx"

    filtros = LicitacaoFilter()
    # Exporta apenas o lic1
    export_service.export_to_excel(
        dest_file,
        filtros,
        selected_pncp_ids=["54801121000161-1-000015/2026"]
    )

    wb = load_workbook(str(dest_file))
    ws_lic = wb["LICITAÇÕES"]
    # 1 cabeçalho + 1 registro selecionado = 2 linhas
    assert ws_lic.max_row == 2
    assert ws_lic.cell(row=2, column=1).value == "54801121000161-1-000015/2026"
