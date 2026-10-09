"""Testes reais opcionais. RADAR_ONLINE=1 habilita acesso às fontes oficiais."""
import os
import pytest
from src.integrations.pncp_client import PNCPClient
from src.integrations.ibge_client import IBGEClient
pytestmark=pytest.mark.skipif(os.environ.get('RADAR_ONLINE')!='1',reason='Integração online opcional; executar com RADAR_ONLINE=1')

def test_real_individual_procurement():
    with PNCPClient(max_retries=2) as client:
        data=client.get_compra('00394411000109',2026,9)
        assert data['numeroControlePNCP']=='00394411000109-1-000009/2026'

def test_real_ibge_go_df():
    with IBGEClient() as client:
        assert len(client.get_estados())==27
        go=client.get_municipios_por_uf('GO'); df=client.get_municipios_por_uf('DF')
        assert len(go)>200 and any(m.nome=='Goiânia' for m in go)
        assert any(m.codigo_ibge=='5300108' for m in df)
