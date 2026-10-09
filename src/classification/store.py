"""Catálogo relacional versionado, evidências imutáveis e decisões manuais."""
import copy
import hashlib
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
from src.classification.engine import Classifier, DEFAULT_SETTINGS, normalize

SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_migrations(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS classification_catalog(version INTEGER PRIMARY KEY, document TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS categories(id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, description TEXT NOT NULL, active INTEGER NOT NULL, priority INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS subcategories(id INTEGER PRIMARY KEY, category_id INTEGER NOT NULL REFERENCES categories(id), name TEXT NOT NULL, description TEXT NOT NULL, active INTEGER NOT NULL, UNIQUE(category_id,name));
CREATE TABLE IF NOT EXISTS classification_rules(id INTEGER PRIMARY KEY, subcategory_id INTEGER NOT NULL REFERENCES subcategories(id), expression TEXT NOT NULL, kind TEXT NOT NULL, weight INTEGER NOT NULL, active INTEGER NOT NULL, synonyms TEXT NOT NULL, context TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_rules_sub ON classification_rules(subcategory_id,active);
CREATE TABLE IF NOT EXISTS classification_runs(id INTEGER PRIMARY KEY, procurement_id INTEGER NOT NULL REFERENCES licitacoes(id), origin TEXT NOT NULL CHECK(origin IN ('automatic','manual')), version INTEGER NOT NULL REFERENCES classification_catalog(version), text_hash TEXT NOT NULL, created_at TEXT NOT NULL, result TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_runs_lic ON classification_runs(procurement_id,id);
CREATE TABLE IF NOT EXISTS classification_state(procurement_id INTEGER PRIMARY KEY REFERENCES licitacoes(id), automatic_id INTEGER REFERENCES classification_runs(id), manual_id INTEGER REFERENCES classification_runs(id), error TEXT);
CREATE TABLE IF NOT EXISTS classifications(id INTEGER PRIMARY KEY, run_id INTEGER NOT NULL REFERENCES classification_runs(id), category_id INTEGER NOT NULL REFERENCES categories(id), subcategory_id INTEGER REFERENCES subcategories(id), score INTEGER NOT NULL, confidence TEXT NOT NULL, is_primary INTEGER NOT NULL, UNIQUE(run_id,category_id));
CREATE INDEX IF NOT EXISTS idx_class_filter ON classifications(category_id,subcategory_id,confidence,run_id);
CREATE INDEX IF NOT EXISTS idx_class_run ON classifications(run_id,is_primary,confidence);
CREATE TABLE IF NOT EXISTS classification_evidence(id INTEGER PRIMARY KEY, classification_id INTEGER NOT NULL REFERENCES classifications(id), rule_id INTEGER NOT NULL, matched TEXT NOT NULL, score INTEGER NOT NULL, snapshot TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS classification_events(id INTEGER PRIMARY KEY, procurement_id INTEGER REFERENCES licitacoes(id), created_at TEXT NOT NULL, action TEXT NOT NULL, detail TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS reclassification_jobs(id INTEGER PRIMARY KEY, started_at TEXT NOT NULL, ended_at TEXT, version INTEGER NOT NULL, mode TEXT NOT NULL, processed INTEGER DEFAULT 0, changed INTEGER DEFAULT 0, unchanged INTEGER DEFAULT 0, errors INTEGER DEFAULT 0, status TEXT NOT NULL);
"""


def now():
    return datetime.now(timezone.utc).isoformat()


def default_catalog():
    return json.loads(Path(__file__).with_name('default_catalog.json').read_text(encoding='utf8'))


def validate_catalog(document):
    d = copy.deepcopy(document)
    if not isinstance(d, dict) or d.get('schema_version') != 1:
        raise ValueError('Versão do catálogo incompatível.')
    for key in ('categories','subcategories','rules'):
        if not isinstance(d.get(key),list) or len(d[key])>20000:
            raise ValueError('Lista inválida ou excessiva: '+key)
        ids=[x.get('id') for x in d[key]]
        if any(type(i) is not int or i<=0 for i in ids) or len(ids)!=len(set(ids)):
            raise ValueError('Identificadores inválidos/duplicados: '+key)
    cats={c['id']:c for c in d['categories']}; subs={s['id']:s for s in d['subcategories']}
    if 10 not in cats or cats[10]['name']!='Não Classificado' or not cats[10]['active']:
        raise ValueError('A categoria reservada Não Classificado (ID 10) deve ser preservada.')
    if any(s.get('category_id')==10 for s in d['subcategories']):
        raise ValueError('Não Classificado é um resultado reservado e não recebe subcategorias.')
    for key in ('categories','subcategories'):
        names=set()
        for row in d[key]:
            if not isinstance(row.get('name'),str) or not row['name'].strip() or len(row['name'])>150:
                raise ValueError('Nome inválido.')
            if type(row.get('active')) is not bool:
                raise ValueError('Situação deve ser booleana.')
            row.setdefault('description','')
            ident=(row.get('category_id'), normalize(row['name']))
            if ident in names: raise ValueError('Nome duplicado: '+row['name'])
            names.add(ident)
            if key=='subcategories' and row.get('category_id') not in cats: raise ValueError('Categoria inexistente.')
            if key=='categories':
                row.setdefault('priority',0)
                if type(row['priority']) is not int: raise ValueError('Prioridade inválida.')
    seen=set()
    for r in d['rules']:
        if r.get('subcategory_id') not in subs: raise ValueError('Subcategoria inexistente.')
        if r.get('kind') not in ('inclusion','exclusion','synonym','contextual'): raise ValueError('Tipo de regra inválido.')
        if type(r.get('weight')) is not int or not 0<=r['weight']<=100: raise ValueError('Peso deve ser inteiro de 0 a 100.')
        if r['kind']!='exclusion' and not r['weight']: raise ValueError('Inclusão exige peso positivo.')
        if type(r.get('active')) is not bool: raise ValueError('Situação inválida.')
        if not isinstance(r.get('expression'),str) or not normalize(r['expression']) or len(r['expression'])>250: raise ValueError('Expressão inválida.')
        for k in ('synonyms','context'):
            r.setdefault(k,[])
            if not isinstance(r[k],list) or len(r[k])>100 or any(not isinstance(v,str) or not normalize(v) or len(v)>250 for v in r[k]): raise ValueError('Lista inválida: '+k)
        if r['kind']=='contextual' and not r['context']: raise ValueError('Regra contextual exige contexto.')
        ident=(r['subcategory_id'],r['kind'],normalize(r['expression']),tuple(sorted(normalize(v) for v in r['context'])))
        if ident in seen: raise ValueError('Regra duplicada: '+r['expression'])
        seen.add(ident)
    d['settings']={**DEFAULT_SETTINGS,**d.get('settings',{})}
    if any(type(v) is not int or v<0 for v in d['settings'].values()): raise ValueError('Limiares inválidos.')
    v=d['settings']
    if not 1<=v['minimum']<=v['medium']<=v['high'] or not 1<=v['context_window']<=50 or v['margin']<1: raise ValueError('Limiares fora de ordem ou contexto inválido.')
    return d


def write_catalog(conn,d):
    for c in d['categories']:
        conn.execute('INSERT INTO categories VALUES (?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,description=excluded.description,active=excluded.active,priority=excluded.priority',(c['id'],c['name'],c['description'],c['active'],c['priority']))
    for s in d['subcategories']:
        conn.execute('INSERT INTO subcategories VALUES (?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET category_id=excluded.category_id,name=excluded.name,description=excluded.description,active=excluded.active',(s['id'],s['category_id'],s['name'],s['description'],s['active']))
    for r in d['rules']:
        conn.execute('INSERT INTO classification_rules VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET subcategory_id=excluded.subcategory_id,expression=excluded.expression,kind=excluded.kind,weight=excluded.weight,active=excluded.active,synonyms=excluded.synonyms,context=excluded.context',(r['id'],r['subcategory_id'],r['expression'],r['kind'],r['weight'],r['active'],json.dumps(r['synonyms'],ensure_ascii=False),json.dumps(r['context'],ensure_ascii=False)))


def migrate(conn):
    # Não usar executescript: ele faria COMMIT implícito e quebraria atomicidade.
    for statement in SCHEMA.split(';'):
        if statement.strip(): conn.execute(statement)
    if not conn.execute('SELECT 1 FROM classification_catalog LIMIT 1').fetchone():
        d=validate_catalog(default_catalog()); write_catalog(conn,d)
        conn.execute('INSERT INTO classification_catalog VALUES (1,?,?)',(json.dumps(d,ensure_ascii=False),now()))
    conn.execute('INSERT OR IGNORE INTO schema_migrations VALUES (2,?)',(now(),))


class ClassificationStore:
    def __init__(self,db): self.db=db

    def catalog(self):
        with self.db.session() as c:
            row=c.execute('SELECT * FROM classification_catalog ORDER BY version DESC LIMIT 1').fetchone()
            return json.loads(row['document']),row['version'],row['created_at']

    def preview(self,document):
        d=validate_catalog(document); old,version,_=self.catalog(); changes=[]
        for key in ('categories','subcategories','rules'):
            prior={r['id']:r for r in old[key]}; incoming={r['id']:r for r in d[key]}
            missing=set(prior)-set(incoming)
            if missing: raise ValueError('Importação não pode remover IDs históricos. Desative os itens: '+key+' '+str(sorted(missing)))
            changes.append(f"{key}: {len(set(incoming)-set(prior))} novos, {sum(prior[i]!=incoming[i] for i in prior)} alterados")
        terms={}
        for r in d['rules']:
            if r['active'] and r['kind']!='exclusion': terms.setdefault(normalize(r['expression']),set()).add(r['subcategory_id'])
        conflicts=[t for t,ids in terms.items() if len(ids)>1]
        return d,version,'\n'.join(changes)+('\nExpressões em múltiplas subcategorias (revisar contexto): '+', '.join(conflicts) if conflicts else '')

    def save_catalog(self,document,expected_version):
        d,version,_=self.preview(document)
        if version!=expected_version: raise ValueError('O catálogo mudou; recarregue a prévia.')
        backup=self.db.backup()
        with self.db.session() as c:
            if c.execute('SELECT max(version) FROM classification_catalog').fetchone()[0]!=version: raise ValueError('Alteração concorrente. Recarregue.')
            write_catalog(c,d)
            c.execute('INSERT INTO classification_catalog VALUES (?,?,?)',(version+1,json.dumps(d,ensure_ascii=False),now()))
        return backup

    def next_id(self,kind):
        if kind not in ('categories','subcategories','rules'): raise ValueError('Tipo inválido')
        with self.db.session() as c:
            return 1+max((item['id'] for row in c.execute('SELECT document FROM classification_catalog') for item in json.loads(row[0])[kind]),default=0)

    def deletion_blocker(self,kind,item_id):
        checks={
            'categories': [('subcategories','category_id'),('classifications','category_id')],
            'subcategories': [('classification_rules','subcategory_id'),('classifications','subcategory_id')],
            'rules': [('classification_evidence','rule_id')]}
        if kind not in checks: raise ValueError('Tipo inválido')
        if kind=='categories' and item_id==10: return 'Categoria reservada.'
        with self.db.session() as c:
            for table,column in checks[kind]:
                if c.execute(f'SELECT 1 FROM {table} WHERE {column}=? LIMIT 1',(item_id,)).fetchone():
                    return 'Há dependências ou evidências históricas. Use desativação.'
        return None

    def delete_unused(self,kind,item_id,expected_version):
        blocker=self.deletion_blocker(kind,item_id)
        if blocker: raise ValueError(blocker)
        d,v,_=self.catalog()
        if v!=expected_version: raise ValueError('Catálogo mudou; recarregue.')
        d[kind]=[x for x in d[kind] if x['id']!=item_id]; d=validate_catalog(d)
        backup=self.db.backup()
        table={'categories':'categories','subcategories':'subcategories','rules':'classification_rules'}[kind]
        with self.db.session() as c:
            if c.execute('SELECT max(version) FROM classification_catalog').fetchone()[0]!=v: raise ValueError('Alteração concorrente.')
            # Evidências também são verificadas dentro da transação.
            if kind=='rules' and c.execute('SELECT 1 FROM classification_evidence WHERE rule_id=?',(item_id,)).fetchone(): raise ValueError('Regra passou a possuir histórico; desative.')
            c.execute(f'DELETE FROM {table} WHERE id=?',(item_id,))
            c.execute('INSERT INTO classification_catalog VALUES (?,?,?)',(v+1,json.dumps(d,ensure_ascii=False),now()))
        return backup

    def save_result(self,c,lic,result,version,origin='automatic'):
        current=c.execute('SELECT objeto FROM licitacoes WHERE id=?',(lic.id,)).fetchone()
        if not current or (current['objeto'] or '')!=(lic.objeto or ''):
            raise ValueError('Objeto alterado durante a classificação; reprocessamento necessário.')
        digest=hashlib.sha256((lic.objeto or '').encode()).hexdigest()
        cur=c.execute('INSERT INTO classification_runs(procurement_id,origin,version,text_hash,created_at,result) VALUES (?,?,?,?,?,?)',(lic.id,origin,version,digest,now(),json.dumps(result,ensure_ascii=False)))
        run_id=cur.lastrowid
        for entry in result['classifications']:
            row=c.execute('INSERT INTO classifications(run_id,category_id,subcategory_id,score,confidence,is_primary) VALUES (?,?,?,?,?,?)',(run_id,entry['category_id'],entry['subcategory_id'],entry['score'],entry['confidence'],entry['primary']))
            for e in entry.get('evidence',[]):
                c.execute('INSERT INTO classification_evidence(classification_id,rule_id,matched,score,snapshot) VALUES (?,?,?,?,?)',(row.lastrowid,e['rule_id'],e['matched'],e['weight'],json.dumps(e,ensure_ascii=False)))
        col='manual_id' if origin=='manual' else 'automatic_id'
        c.execute(f'INSERT INTO classification_state(procurement_id,{col}) VALUES (?,?) ON CONFLICT(procurement_id) DO UPDATE SET {col}=excluded.{col},error=NULL',(lic.id,run_id))
        return run_id

    def classify_batch(self,items,engine=None,version=None,force=False):
        if engine is None:
            d,version,_=self.catalog(); engine=Classifier(d)
        stats={'changed':0,'unchanged':0,'errors':0}
        with self.db.session() as c:
            for lic in items:
                c.execute('SAVEPOINT classify_one')
                try:
                    old=c.execute('SELECT r.* FROM classification_state s JOIN classification_runs r ON r.id=s.automatic_id WHERE s.procurement_id=?',(lic.id,)).fetchone()
                    digest=hashlib.sha256((lic.objeto or '').encode()).hexdigest()
                    current=c.execute('SELECT objeto FROM licitacoes WHERE id=?',(lic.id,)).fetchone()
                    if not current or (current['objeto'] or '')!=(lic.objeto or ''):
                        raise ValueError('Objeto alterado durante a classificação; reprocessamento necessário.')
                    if not force and old and old['version']==version and old['text_hash']==digest:
                        c.execute('UPDATE classification_state SET error=NULL WHERE procurement_id=?',(lic.id,))
                        stats['unchanged']+=1
                    else:
                        result=engine.classify(lic.objeto)
                        self.save_result(c,lic,result,version)
                        key='unchanged' if old and json.loads(old['result'])==result else 'changed'
                        stats[key]+=1
                    c.execute('RELEASE classify_one')
                except Exception as e:
                    c.execute('ROLLBACK TO classify_one'); c.execute('RELEASE classify_one')
                    from src.utils.logging_config import get_logger
                    get_logger().exception('Falha de classificação %s',lic.id)
                    c.execute('INSERT INTO classification_state(procurement_id,error) VALUES (?,?) ON CONFLICT(procurement_id) DO UPDATE SET error=excluded.error',(lic.id,str(e)))
                    stats['errors']+=1
        return stats

    def effective(self,ids):
        result={}
        with self.db.session() as c:
            for offset in range(0,len(ids),500):
                batch=ids[offset:offset+500]
                marks=','.join('?' for _ in batch)
                rows=c.execute(f'SELECT s.procurement_id,s.error,r.* FROM classification_state s LEFT JOIN classification_runs r ON r.id=coalesce(s.manual_id,s.automatic_id) WHERE s.procurement_id IN ({marks})',batch)
                for r in rows:
                    if r['result']:
                        result[r['procurement_id']]={**json.loads(r['result']),'origin':r['origin'],'date':r['created_at'],'version':r['version'],'error':r['error']}
        return result

    def set_manual(self,lic,category_id,subcategory_id,reason):
        if not reason.strip(): raise ValueError('Informe justificativa da correção manual.')
        d,v,_=self.catalog(); cats={x['id']:x for x in d['categories']}; subs={x['id']:x for x in d['subcategories']}
        cat=cats.get(category_id); sub=subs.get(subcategory_id)
        if not cat or not cat['active'] or not sub or not sub['active'] or sub['category_id']!=category_id: raise ValueError('Categoria/subcategoria inválida ou inativa.')
        entry=dict(category_id=category_id,category=cat['name'],subcategory_id=subcategory_id,subcategory=sub['name'],score=0,confidence='Manual',primary=True,evidence=[])
        result=dict(primary=entry,classifications=[entry],reason=reason,exclusions=[],suppressed=[])
        with self.db.session() as c:
            self.save_result(c,lic,result,v,'manual')
            c.execute('INSERT INTO classification_events(procurement_id,created_at,action,detail) VALUES (?,?,?,?)',(lic.id,now(),'manual',reason))

    def return_automatic(self,lic):
        self.classify_batch([lic],force=True)
        with self.db.session() as c:
            c.execute('UPDATE classification_state SET manual_id=NULL WHERE procurement_id=?',(lic.id,))
            c.execute('INSERT INTO classification_events(procurement_id,created_at,action,detail) VALUES (?,?,?,?)',(lic.id,now(),'automatic','Retorno explícito à classificação automática'))

    def statistics(self):
        _,v,_=self.catalog()
        with self.db.session() as c:
            row=c.execute("""SELECT count(*) total,
            sum(CASE WHEN EXISTS(SELECT 1 FROM classifications x WHERE x.run_id=coalesce(s.manual_id,s.automatic_id) AND x.is_primary=1) THEN 1 ELSE 0 END) classified,
            sum(CASE WHEN EXISTS(SELECT 1 FROM classifications x WHERE x.run_id=coalesce(s.manual_id,s.automatic_id) AND x.confidence='Baixa') THEN 1 ELSE 0 END) low,
            sum(CASE WHEN r.version IS NULL OR r.version<? OR r.text_hash!=content_hash(l.objeto) OR s.error IS NOT NULL THEN 1 ELSE 0 END) pending,
            max(r.created_at) latest FROM licitacoes l LEFT JOIN classification_state s ON s.procurement_id=l.id LEFT JOIN classification_runs r ON r.id=s.automatic_id""",(v,)).fetchone()
            return dict(row)
