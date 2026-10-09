"""Reclassificação em lotes, sem rede e com histórico persistente."""
from src.classification.store import ClassificationStore, now
from src.classification.engine import Classifier
from src.domain.entities import Licitacao


class ReclassificationService:
    def __init__(self,db): self.db=db; self.store=ClassificationStore(db)

    def run(self,mode='all',progress=None,cancelled=None):
        if mode not in ('all','unclassified','low','pending'): raise ValueError('Modo inválido')
        catalog,version,_=self.store.catalog(); engine=Classifier(catalog)
        cond={'all':'1=1','unclassified':"NOT EXISTS(SELECT 1 FROM classifications x WHERE x.run_id=coalesce(s.manual_id,s.automatic_id) AND x.is_primary=1)",'low':"EXISTS(SELECT 1 FROM classifications x WHERE x.run_id=coalesce(s.manual_id,s.automatic_id) AND x.confidence='Baixa')",'pending':f'(r.version IS NULL OR r.version<{version} OR r.text_hash!=content_hash(l.objeto) OR s.error IS NOT NULL)'}[mode]
        base='FROM licitacoes l LEFT JOIN classification_state s ON s.procurement_id=l.id LEFT JOIN classification_runs r ON r.id=s.automatic_id WHERE '+cond
        with self.db.session() as c:
            maximum=c.execute('SELECT coalesce(max(id),0) FROM licitacoes').fetchone()[0]
            total=c.execute('SELECT count(*) '+base+' AND l.id<=?',(maximum,)).fetchone()[0]
            job=c.execute('INSERT INTO reclassification_jobs(started_at,version,mode,status) VALUES (?,?,?,?)',(now(),version,mode,'Em andamento')).lastrowid
        stats=dict(processed=0,changed=0,unchanged=0,errors=0,status='Concluída'); last=0
        try:
            while last<maximum:
                if cancelled and cancelled(): stats['status']='Interrompida'; break
                with self.db.session() as c:
                    rows=c.execute('SELECT l.* '+base+' AND l.id>? AND l.id<=? ORDER BY l.id LIMIT 100',(last,maximum)).fetchall()
                if not rows: break
                items=[Licitacao(**dict(r)) for r in rows]; last=items[-1].id
                counts=self.store.classify_batch(items,engine,version,force=mode=='all')
                stats['processed']+=len(items)
                for key in counts: stats[key]+=counts[key]
                with self.db.session() as c:
                    c.execute('UPDATE reclassification_jobs SET processed=?,changed=?,unchanged=?,errors=? WHERE id=?',(stats['processed'],stats['changed'],stats['unchanged'],stats['errors'],job))
                if progress: progress(stats['processed'],total)
            if stats['errors'] and stats['status']=='Concluída': stats['status']='Concluída com erros'
        except Exception:
            stats['status']='Falhou'; raise
        finally:
            with self.db.session() as c:
                c.execute('UPDATE reclassification_jobs SET ended_at=?,status=? WHERE id=?',(now(),stats['status'],job))
        return stats
