import copy
import json
import pytest
from src.classification.engine import Classifier,normalize
from src.classification.store import ClassificationStore,default_catalog,validate_catalog
from src.application.reclassification_service import ReclassificationService
from src.domain.entities import Licitacao
from src.domain.filters import LicitacaoFilter

@pytest.mark.parametrize('text,category,sub',[
 ('Compra de notebooks','Tecnologia da Informação','Hardware e Equipamentos'),
 ('Licenciamento de software de gestão municipal','Tecnologia da Informação','Software e Sistemas'),
 ('Equipamentos de INFORMÁTICA','Tecnologia da Informação','Hardware e Equipamentos'),
 ('Compra de microcomputadores','Tecnologia da Informação','Hardware e Equipamentos'),
 ('manutenção preventiva e corretiva de computadores e equipamentos de rede','Tecnologia da Informação','Manutenção e Suporte Técnico'),
 ('Manutenção predial','Serviços Gerais','Manutenção predial'),
 ('Implantação de rede de abastecimento de água','Construção Civil','Infraestrutura urbana'),
 ('Aquisição de medicamentos','Saúde','Medicamentos'),
 ('Merenda escolar','Alimentação','Merenda escolar'),
 ('Prestação de serviços diversos',None,None),
 ('sistema rede manutenção',None,None),
 ('notebookista microssistema',None,None),
 ('',None,None),
 (None,None,None),
])
def test_examples(text,category,sub):
    result=Classifier(default_catalog()).classify(text)
    if category is None: assert result['primary'] is None
    else:
        assert result['primary']['category']==category
        assert result['primary']['subcategory']==sub


def test_overlap_and_repetition():
    e=Classifier(default_catalog())
    result=e.classify('Licenciamento de software software software')
    # A expressão simples pode pontuar uma ocorrência independente; repetição não multiplica regra.
    assert result['primary']['score']==13
    result=e.classify('Licenciamento de software')
    assert result['primary']['score']==8
    assert result['suppressed']


def test_multiple_categories_and_conflict():
    e=Classifier(default_catalog())
    r=e.classify('Instalação de câmeras de segurança com servidores e infraestrutura de rede')
    assert {c['category'] for c in r['classifications']}=={'Segurança','Tecnologia da Informação'}
    assert r['primary'] is None  # empate: não inventar vencedora
    r=e.classify('videomonitoramento câmeras de segurança e infraestrutura de rede')
    assert r['primary']['category']=='Segurança'


def test_local_exclusion():
    d=default_catalog(); d['rules'].append(dict(id=999,subcategory_id=3,expression='rede',synonyms=[],kind='inclusion',weight=5,context=[],active=True))
    e=Classifier(d)
    r=e.classify('rede de esgoto e infraestrutura de rede')
    assert r['exclusions'] and any(x.get('exclusion_rules') for x in r['suppressed'])
    assert any(c['category']=='Tecnologia da Informação' for c in r['classifications'])


def test_catalog_changes_manual_and_history(db_conn,procurement_repo):
    store=ClassificationStore(db_conn)
    lic=Licitacao('test',objeto='Compra de notebooks')
    procurement_repo.upsert_batch([lic])
    original=store.effective([lic.id])[lic.id]
    assert original['primary']['category_id']==1
    assert store.classify_batch([lic])['unchanged']==1
    store.set_manual(lic,3,12,'Correção humana de teste')
    ReclassificationService(db_conn).run()
    assert store.effective([lic.id])[lic.id]['origin']=='manual'
    store.return_automatic(lic)
    assert store.effective([lic.id])[lic.id]['origin']=='automatic'
    d,v,_=store.catalog()
    for r in d['rules']:
        if r['expression']=='notebook': r['active']=False
    backup=store.save_catalog(d,v); assert backup.exists()
    ReclassificationService(db_conn).run('pending')
    assert store.effective([lic.id])[lic.id]['primary'] is None
    with db_conn.session() as c:
        assert c.execute('SELECT count(*) FROM classification_events').fetchone()[0]==2
        assert c.execute('PRAGMA foreign_key_check').fetchone() is None


def test_secondary_filters_no_duplicates(procurement_repo):
    lic=Licitacao('multi',objeto='videomonitoramento câmeras de segurança e infraestrutura de rede')
    procurement_repo.upsert_batch([lic])
    assert procurement_repo.search(LicitacaoFilter(status_proposta='todas',category_ids=[1]))[1]==1
    assert procurement_repo.search(LicitacaoFilter(status_proposta='todas',category_ids=[1],primary_category_only=True))[1]==0
    assert procurement_repo.search(LicitacaoFilter(status_proposta='todas',category_ids=[1,5]))[1]==1
    assert procurement_repo.search(LicitacaoFilter(status_proposta='todas',category_ids=[1],subcategory_ids=[3]))[1]==1


def test_failure_preserves_official_record(procurement_repo,db_conn,monkeypatch):
    monkeypatch.setattr(Classifier,'classify',lambda *a:(_ for _ in ()).throw(ValueError('regra inválida')))
    lic=Licitacao('error',objeto='Texto oficial')
    procurement_repo.upsert_batch([lic])
    assert procurement_repo.get_by_pncp_id('error').objeto=='Texto oficial'
    with db_conn.session() as c: assert c.execute('SELECT error FROM classification_state').fetchone()[0]=='regra inválida'


def test_changed_text_reclassifies(procurement_repo,db_conn):
    lic=Licitacao('change',objeto='notebooks'); procurement_repo.upsert_batch([lic]); lic.objeto='medicamentos'; procurement_repo.upsert_batch([lic])
    assert ClassificationStore(db_conn).effective([lic.id])[lic.id]['primary']['category']=='Saúde'

@pytest.mark.parametrize('mutation',[
 lambda d:d.update(schema_version=99),
 lambda d:d['rules'][0].update(weight=-1),
 lambda d:d['rules'][0].update(subcategory_id=9999),
 lambda d:d['rules'].append(dict(d['rules'][0])),
 lambda d:d['rules'][0].update(expression='  '),
 lambda d:d['rules'][0].update(kind='regex'),
 lambda d:d['settings'].update(minimum=20,high=4),
])
def test_invalid_catalog(mutation):
    d=default_catalog(); mutation(d)
    with pytest.raises(ValueError): validate_catalog(d)


def test_import_preview_and_conflicts(db_conn):
    store=ClassificationStore(db_conn); d,v,_=store.catalog()
    d['rules'][0]['weight']=9
    checked,version,preview=store.preview(d)
    assert '1 alterados' in preview
    store.save_catalog(checked,version)
    with pytest.raises(ValueError,match='mudou'): store.save_catalog(d,version)
    d,_,_=store.catalog(); d['rules'].pop()
    with pytest.raises(ValueError,match='remover'): store.preview(d)


def test_cancellation_and_offline(db_conn,procurement_repo):
    procurement_repo.upsert_batch([Licitacao(str(i),objeto='notebooks') for i in range(205)])
    calls=[]
    result=ReclassificationService(db_conn).run('all',lambda a,b:calls.append((a,b)),lambda:bool(calls))
    assert result['status']=='Interrompida' and result['processed']==100
    assert calls==[(100,205)]
    assert procurement_repo.search(LicitacaoFilter(status_proposta='todas',limite=500))[1]==205


def test_delete_only_without_dependencies(db_conn,procurement_repo):
    store=ClassificationStore(db_conn); d,v,_=store.catalog()
    next_id=store.next_id('rules'); d['rules'].append(dict(id=next_id,subcategory_id=1,expression='regra temporária',synonyms=[],context=[],weight=8,kind='inclusion',active=True)); store.save_catalog(d,v)
    store.delete_unused('rules',next_id,v+1)
    assert store.next_id('rules')==next_id+1
    with pytest.raises(ValueError,match='dependências'): store.delete_unused('categories',1,v+2)
    procurement_repo.upsert_batch([Licitacao('evidence',objeto='software')])
    with pytest.raises(ValueError,match='dependências'): store.delete_unused('rules',1,v+2)


def test_stale_object_cannot_overwrite_classification(db_conn,procurement_repo):
    store=ClassificationStore(db_conn); old=Licitacao('race',objeto='notebooks'); procurement_repo.upsert_batch([old])
    updated=Licitacao('race',objeto='medicamentos'); procurement_repo.upsert_batch([updated])
    assert store.classify_batch([old],force=True)['errors']==1
    assert store.effective([updated.id])[updated.id]['primary']['category']=='Saúde'
    assert store.statistics()['pending']==1
    ReclassificationService(db_conn).run('pending')
    assert store.statistics()['pending']==0
