"""Massa sintética explícita: desempenho local, não valida API."""
import sys,time,json,tracemalloc,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from src.classification.store import default_catalog
from src.classification.engine import Classifier
from src.database.connection import DatabaseConnection
from src.database.migrations import init_database
from src.database.repositories import ProcurementRepository
from src.domain.entities import Licitacao
from src.domain.filters import LicitacaoFilter
from src.application.reclassification_service import ReclassificationService
texts=['Compra de notebooks','Licenciamento de software de gestão municipal','manutenção preventiva e corretiva de computadores e equipamentos de rede','manutenção predial','rede de abastecimento de água','medicamentos','serviços diversos','videomonitoramento câmeras de segurança e infraestrutura de rede']
engine=Classifier(default_catalog()); tracemalloc.start(); start=time.perf_counter()
for i in range(10000): engine.classify(texts[i%len(texts)])
engine_time=time.perf_counter()-start; _,peak=tracemalloc.get_traced_memory(); tracemalloc.stop()
with tempfile.TemporaryDirectory() as folder:
 db=DatabaseConnection(Path(folder)/'benchmark.db')
 with db.session() as c: init_database(c)
 repo=ProcurementRepository(db); start=time.perf_counter()
 for offset in range(0,10000,100): repo.upsert_batch([Licitacao(str(i),objeto=texts[i%len(texts)],uf_sigla='GO') for i in range(offset,offset+100)])
 persist_time=time.perf_counter()-start
 start=time.perf_counter(); _,count=repo.search(LicitacaoFilter(ufs=['GO'],category_ids=[1],status_proposta='todas',limite=200)); query_time=time.perf_counter()-start
 start=time.perf_counter(); report=ReclassificationService(db).run('pending'); pending_time=time.perf_counter()-start
 result=dict(synthetic=True,count=10000,rules=len(default_catalog()['rules']),engine_seconds=engine_time,engine_peak_mib=peak/1024/1024,persist_and_classify_seconds=persist_time,category_query_seconds=query_time,category_matches=count,pending_reclassification_seconds=pending_time,pending_result=report)
 out=ROOT/'scratch'/'benchmark.json'; out.write_text(json.dumps(result,indent=2),encoding='utf8'); print(json.dumps(result,indent=2))
