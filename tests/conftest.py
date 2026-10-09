"""Fixtures compartilhadas para a suíte de testes do Radar Nacional de Licitações."""
import pytest
import tempfile
import shutil
import sys
from pathlib import Path

# Garante que o diretório raiz esteja no sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.database.connection import DatabaseConnection
from src.database.migrations import init_database
from src.database.repositories import (
    ProcurementRepository, LocationRepository, SyncRepository,
    SavedSearchRepository, SettingsRepository
)
from src.domain.entities import Licitacao


@pytest.fixture
def temp_dir():
    """Diretório temporário isolado para testes."""
    d = tempfile.mkdtemp(prefix="radar_test_")
    yield Path(d)
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def db_conn(temp_dir):
    """Conexão com banco SQLite temporário e inicializado."""
    db_file = temp_dir / "test_radar.sqlite3"
    conn_mgr = DatabaseConnection(db_file)
    with conn_mgr.session() as conn:
        init_database(conn)
    return conn_mgr


@pytest.fixture
def procurement_repo(db_conn):
    return ProcurementRepository(db_conn)


@pytest.fixture
def location_repo(db_conn):
    return LocationRepository(db_conn)


@pytest.fixture
def sync_repo(db_conn):
    return SyncRepository(db_conn)


@pytest.fixture
def saved_repo(db_conn):
    return SavedSearchRepository(db_conn)


@pytest.fixture
def sample_raw_pncp():
    """Exemplo de payload bruto real retornado pela API do PNCP."""
    return {
        "numeroControlePNCP": "54801121000161-1-000015/2026",
        "anoCompra": 2026,
        "sequencialCompra": 15,
        "numeroCompra": "06/2026",
        "processo": "16-2026",
        "modalidadeId": 6,
        "modalidadeNome": "Pregão - Eletrônico",
        "modoDisputaId": 3,
        "modoDisputaNome": "Aberto-Fechado",
        "tipoInstrumentoConvocatorioCodigo": 1,
        "tipoInstrumentoConvocatorioNome": "Edital",
        "objetoCompra": "Aquisição de computadores e servidores para a Secretaria Municipal",
        "informacaoComplementar": "Itens com entrega imediata conforme edital.",
        "valorTotalEstimado": 199840.50,
        "valorTotalHomologado": None,
        "dataPublicacaoPncp": "2026-02-11T12:23:43",
        "dataAberturaProposta": "2026-02-12T08:00:00",
        "dataEncerramentoProposta": "2026-12-31T18:00:00",
        "dataAtualizacaoPncp": "2026-09-24T09:34:05",
        "dataAtualizacaoGlobal": "2026-10-07T11:04:13",
        "situacaoCompraId": 1,
        "situacaoCompraNome": "Divulgada no PNCP",
        "linkSistemaOrigem": "https://bllcompras.com/Process/ProcessView?param1=test",
        "orgaoEntidade": {
            "cnpj": "54801121000161",
            "razaoSocial": "MUNICÍPIO DE TESTE GOIÁS",
            "poderId": "E",
            "esferaId": "M"
        },
        "unidadeOrgao": {
            "ufSigla": "GO",
            "ufNome": "Goiás",
            "municipioNome": "Águas Lindas de Goiás",
            "codigoIbge": "5200258",
            "codigoUnidade": "10",
            "nomeUnidade": "SECRETARIA DE ADMINISTRACAO"
        }
    }
