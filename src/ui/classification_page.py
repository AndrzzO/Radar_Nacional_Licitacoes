"""Gerenciamento persistente de categorias, regras, teste e revisão."""
import copy
import json
from pathlib import Path
from PySide6.QtCore import Signal, Slot, Qt
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QTabWidget,QLabel,QPushButton,QTableWidget,QTableWidgetItem,QLineEdit,QTextEdit,QComboBox,QCheckBox,QSpinBox,QDialog,QFormLayout,QDialogButtonBox,QMessageBox,QFileDialog,QProgressBar,QHeaderView)
from src.classification.store import ClassificationStore, default_catalog
from src.classification.engine import Classifier
from src.application.reclassification_service import ReclassificationService
from src.workers.task_worker import TaskWorker
from src.domain.filters import LicitacaoFilter


def explain(result):
    p=result.get('primary') or {}
    lines=[f"Principal: {p.get('category','Não Classificado')} / {p.get('subcategory','—')}",f"Confiança: {p.get('confidence','Não Classificado')} | Pontuação: {p.get('score',0)}",result.get('reason','Pendente de classificação'),f"Origem: {result.get('origin','teste')} | Versão: {result.get('version','atual')} | Data: {result.get('date','—')}"]
    for c in result.get('classifications',[]):
        lines.append(f"{c['category']} / {c['subcategory']}: {c['score']} pontos ({'principal' if c['primary'] else 'secundária/candidata'})")
        for e in c.get('evidence',[]): lines.append(f"  Regra {e['rule_id']}: {e['matched']} (+{e['weight']})")
    for e in result.get('exclusions',[]): lines.append(f"Exclusão {e['rule_id']}: {e['matched']}")
    for e in result.get('suppressed',[]): lines.append(f"Não pontuado: {e['matched']} — {e['reason']}")
    if result.get('error'): lines.append('Pendente: '+result['error'])
    return '\n'.join(lines)


class CatalogEditor(QDialog):
    def __init__(self,kind,catalog,item=None,parent=None):
        super().__init__(parent); self.kind=kind; self.item=copy.deepcopy(item or {})
        self.setWindowTitle('Editar '+{'categories':'categoria','subcategories':'subcategoria','rules':'regra'}[kind]); self.resize(580,460)
        layout=QFormLayout(self); self.fields={}
        keys=['name','description','active','priority'] if kind=='categories' else ['category_id','name','description','active'] if kind=='subcategories' else ['subcategory_id','expression','kind','weight','synonyms','context','active']
        labels=dict(name='Nome',description='Descrição',active='Ativa',priority='Prioridade',category_id='Categoria',subcategory_id='Subcategoria',expression='Expressão completa',kind='Tipo',weight='Peso',synonyms='Sinônimos / plurais (um por linha)',context='Contexto próximo (um por linha)')
        for key in keys:
            val=self.item.get(key)
            if key=='active': widget=QCheckBox(); widget.setChecked(val if val is not None else True)
            elif key in ('weight','priority'):
                widget=QSpinBox(); widget.setRange(0,100); widget.setValue(val if val is not None else 5)
            elif key in ('category_id','subcategory_id','kind'):
                widget=QComboBox()
                if key=='kind': options=[('Inclusão','inclusion'),('Exclusão','exclusion'),('Sinônimo','synonym'),('Contextual','contextual')]
                else:
                    source=catalog['categories' if key=='category_id' else 'subcategories']; cats={c['id']:c['name'] for c in catalog['categories']}
                    options=[((cats[x['category_id']]+' / ' if key=='subcategory_id' else '')+x['name'],x['id']) for x in source]
                for name,id_ in options: widget.addItem(name,id_)
                if val is not None: widget.setCurrentIndex(widget.findData(val))
            elif key in ('synonyms','context'):
                widget=QTextEdit(); widget.setPlainText('\n'.join(val or [])); widget.setMaximumHeight(80)
            else: widget=QLineEdit(val or '')
            self.fields[key]=widget; layout.addRow(labels[key],widget)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); layout.addRow(buttons)

    def value(self):
        row=dict(self.item)
        for key,w in self.fields.items():
            row[key]=w.isChecked() if isinstance(w,QCheckBox) else w.value() if isinstance(w,QSpinBox) else w.currentData() if isinstance(w,QComboBox) else [x.strip() for x in w.toPlainText().splitlines() if x.strip()] if isinstance(w,QTextEdit) else w.text().strip()
        return row


class ClassificationPanel(QWidget):
    changed=Signal()
    manage_requested=Signal()
    def __init__(self,db,lic,parent=None):
        super().__init__(parent); self.store=ClassificationStore(db); self.lic=lic
        layout=QVBoxLayout(self); layout.addWidget(QLabel('Classificação por regras locais'))
        self.text=QTextEdit(); self.text.setReadOnly(True); layout.addWidget(self.text)
        buttons=QHBoxLayout()
        for title,slot in [('Corrigir categoria',self.manual),('Testar novamente',self.test),('Voltar à automática',self.automatic),('Gerenciar regras',self.manage_requested.emit)]:
            b=QPushButton(title); b.clicked.connect(slot); buttons.addWidget(b)
        layout.addLayout(buttons); self.refresh()

    def refresh(self): self.text.setPlainText(explain(self.store.effective([self.lic.id]).get(self.lic.id,{})))
    def test(self):
        d,v,_=self.store.catalog(); self.text.setPlainText('SIMULAÇÃO — registro preservado\n'+explain(Classifier(d).classify(self.lic.objeto)))
    def manual(self):
        d,_,_=self.store.catalog(); dlg=QDialog(self); dlg.setWindowTitle('Correção manual'); form=QFormLayout(dlg)
        combo=QComboBox(); cats={c['id']:c for c in d['categories']}
        for sub in d['subcategories']:
            if sub['active'] and cats[sub['category_id']]['active']: combo.addItem(cats[sub['category_id']]['name']+' / '+sub['name'],(sub['category_id'],sub['id']))
        reason=QLineEdit(); form.addRow('Categoria / subcategoria',combo); form.addRow('Justificativa',reason)
        bbox=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel); bbox.accepted.connect(dlg.accept); bbox.rejected.connect(dlg.reject); form.addRow(bbox)
        if dlg.exec():
            try:
                self.store.set_manual(self.lic,*combo.currentData(),reason.text()); self.refresh(); self.changed.emit()
            except Exception as e: QMessageBox.warning(self,'Correção não salva',str(e))
    def automatic(self):
        if QMessageBox.question(self,'Retornar à automática','Retirar a prioridade manual? O histórico será preservado.')==QMessageBox.StandardButton.Yes:
            try: self.store.return_automatic(self.lic); self.refresh(); self.changed.emit()
            except Exception as e: QMessageBox.warning(self,'Falha',str(e))


class ClassificationPage(QWidget):
    changed=Signal()
    def __init__(self,db,repo,parent=None):
        super().__init__(parent); self.db=db; self.repo=repo; self.store=ClassificationStore(db); self.worker=None
        root=QVBoxLayout(self); root.addWidget(QLabel('<h2>Classificação Automática</h2>'))
        self.tabs=QTabWidget(); root.addWidget(self.tabs)
        overview=QWidget(); overview_layout=QVBoxLayout(overview); self.summary=QLabel(); self.summary.setWordWrap(True); overview_layout.addWidget(self.summary)
        tools=QHBoxLayout()
        for label,slot in [('Atualizar',self.refresh),('Exportar catálogo JSON',self.export_catalog),('Importar catálogo JSON',self.import_catalog),('Restaurar regras padrão',self.restore_defaults),('Configurar limiares',self.edit_settings)]:
            button=QPushButton(label); button.clicked.connect(slot); tools.addWidget(button)
        overview_layout.addLayout(tools); overview_layout.addStretch(); self.tabs.addTab(overview,'Visão Geral')
        self.tables={}; self.searches={}; self.category_filters={}
        for kind,title in [('categories','Categorias'),('subcategories','Subcategorias'),('rules','Palavras-chave e Regras')]:
            page=QWidget(); layout=QVBoxLayout(page); bar=QHBoxLayout(); search=QLineEdit(); search.setPlaceholderText('Buscar por nome ou expressão'); self.searches[kind]=search; search.textChanged.connect(self.refresh_tables); bar.addWidget(search)
            combo=QComboBox(); self.category_filters[kind]=combo; combo.currentIndexChanged.connect(self.refresh_tables); bar.addWidget(combo)
            for label,action in [('Adicionar','new'),('Editar','edit'),('Desativar / Ativar','toggle'),('Excluir com verificação','delete')]:
                button=QPushButton(label); button.clicked.connect(lambda _,k=kind,a=action:self.edit(k,a)); bar.addWidget(button)
            layout.addLayout(bar); table=QTableWidget(); table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows); table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers); table.setAlternatingRowColors(True); layout.addWidget(table); self.tables[kind]=table; self.tabs.addTab(page,title)
        tester=QWidget(); layout=QVBoxLayout(tester); self.input=QTextEdit(); self.input.setPlaceholderText('Digite o objeto da licitação'); layout.addWidget(self.input); button=QPushButton('Testar classificação'); button.clicked.connect(self.test); layout.addWidget(button); self.output=QTextEdit(); self.output.setReadOnly(True); layout.addWidget(self.output); self.tabs.addTab(tester,'Testar Classificação')
        batch=QWidget(); layout=QVBoxLayout(batch); self.mode=QComboBox()
        for label,mode in [('Todos os registros','all'),('Não classificados','unclassified'),('Baixa confiança','low'),('Pendentes / regras atualizadas','pending')]: self.mode.addItem(label,mode)
        layout.addWidget(self.mode); button=QPushButton('Reclassificar licitações armazenadas'); button.clicked.connect(self.reclassify); layout.addWidget(button)
        self.jobs=QTextEdit(); self.jobs.setReadOnly(True); layout.addWidget(self.jobs); self.tabs.addTab(batch,'Reclassificar Registros')
        review=QWidget(); layout=QVBoxLayout(review); button=QPushButton('Atualizar revisão (até 200 registros)'); button.clicked.connect(self.review); layout.addWidget(button); self.review_table=QTableWidget(); self.review_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers); self.review_table.cellDoubleClicked.connect(self.open_review); layout.addWidget(self.review_table); self.tabs.addTab(review,'Revisão de Classificações')
        self.progress=QProgressBar(); root.addWidget(self.progress); self.status=QLabel('Pronto.'); self.status.setWordWrap(True); root.addWidget(self.status); self.cancel_button=QPushButton('Cancelar reclassificação'); self.cancel_button.clicked.connect(self.cancel); self.cancel_button.setEnabled(False); root.addWidget(self.cancel_button)
        self.refresh()

    def refresh(self):
        self.catalog,self.version,updated=self.store.catalog(); st=self.store.statistics()
        self.summary.setText(f"Classificados: {st['classified'] or 0} | Não classificados: {st['total']-(st['classified'] or 0)} | Baixa confiança: {st['low'] or 0} | Pendentes: {st['pending'] or 0}\nCategorias: {len(self.catalog['categories'])} | Regras ativas: {sum(r['active'] for r in self.catalog['rules'])} | Versão: {self.version}\nÚltima classificação: {st['latest'] or 'Nenhuma'} | Regras atualizadas: {updated}")
        for combo in self.category_filters.values():
            old=combo.currentData(); combo.blockSignals(True); combo.clear(); combo.addItem('Todas as categorias',None)
            for c in self.catalog['categories']: combo.addItem(c['name'],c['id'])
            combo.setCurrentIndex(max(0,combo.findData(old))); combo.blockSignals(False)
        self.refresh_tables()
        with self.db.session() as c: rows=[dict(x) for x in c.execute('SELECT * FROM reclassification_jobs ORDER BY id DESC LIMIT 30')]
        self.jobs.setPlainText('\n'.join(f"{r['started_at']} | {r['status']} | versão {r['version']} | processados {r['processed']} | alterados {r['changed']} | inalterados {r['unchanged']} | erros {r['errors']}" for r in rows))

    def refresh_tables(self,*_):
        if not hasattr(self,'catalog'): return
        cats={c['id']:c['name'] for c in self.catalog['categories']}; subs={s['id']:s for s in self.catalog['subcategories']}
        for kind,table in self.tables.items():
            query=self.searches[kind].text().casefold(); cid=self.category_filters[kind].currentData()
            rows=[]
            for row in self.catalog[kind]:
                category=row['id'] if kind=='categories' else row['category_id'] if kind=='subcategories' else subs[row['subcategory_id']]['category_id']
                if query not in row.get('name',row.get('expression','')).casefold() or (cid and category!=cid): continue
                vals=[row['id'],row.get('name',row.get('expression')),cats[category], 'Ativa' if row['active'] else 'Inativa']
                if kind=='rules': vals += [subs[row['subcategory_id']]['name'],row['kind'],row['weight'],', '.join(row['context']),', '.join(row['synonyms'])]
                elif kind=='categories': vals += [row['priority']]
                rows.append(vals)
            headers=['ID','Nome / expressão','Categoria','Situação']+(['Subcategoria','Tipo','Peso','Contexto','Sinônimos'] if kind=='rules' else ['Prioridade'] if kind=='categories' else [])
            table.setColumnCount(len(headers)); table.setHorizontalHeaderLabels(headers); table.setRowCount(len(rows))
            for i,row in enumerate(rows):
                for j,value in enumerate(row): table.setItem(i,j,QTableWidgetItem(str(value)))
            table.horizontalHeader().setSectionResizeMode(1,QHeaderView.ResizeMode.Stretch)

    def edit(self,kind,action):
        if self.worker and self.worker.isRunning(): return
        d=copy.deepcopy(self.catalog); item=None
        if action!='new':
            row=self.tables[kind].currentRow()
            if row<0: return
            id_=int(self.tables[kind].item(row,0).text()); item=next(x for x in d[kind] if x['id']==id_)
        if action=='delete':
            blocker=self.store.deletion_blocker(kind,item['id'])
            if blocker:
                if QMessageBox.question(self,'Dependências existentes',blocker+'\nDesativar o item preservando o histórico?')!=QMessageBox.StandardButton.Yes: return
                item['active']=False
            else:
                if QMessageBox.question(self,'Excluir item sem dependências','Excluir este item? Um backup e as versões anteriores do catálogo serão preservados.')!=QMessageBox.StandardButton.Yes: return
                id_=item['id']; version=self.version
                self.start(lambda progress,cancelled:self.store.delete_unused(kind,id_,version),'Excluindo item com backup...')
                return
        elif action=='toggle': item['active']=not item['active']
        else:
            editor=CatalogEditor(kind,d,item,self)
            if not editor.exec(): return
            value=editor.value()
            if item is None: value['id']=self.store.next_id(kind); d[kind].append(value)
            else: item.update(value)
        self.save(d)

    def save(self,document):
        try:
            d,v,preview=self.store.preview(document)
            if QMessageBox.question(self,'Aplicar alterações',preview+'\nUm backup será criado antes da alteração. Continuar?')!=QMessageBox.StandardButton.Yes: return
            self.start(lambda progress,cancelled:self.store.save_catalog(d,v),'Salvando catálogo e backup...')
        except Exception as e: QMessageBox.warning(self,'Catálogo inválido',str(e))

    def edit_settings(self):
        dlg=QDialog(self); form=QFormLayout(dlg); widgets={}
        for key,label in [('minimum','Mínimo'),('medium','Confiança média'),('high','Confiança alta'),('margin','Margem entre categorias'),('context_window','Janela de contexto (palavras)')]:
            w=QSpinBox(); w.setRange(1,1000); w.setValue(self.catalog['settings'][key]); widgets[key]=w; form.addRow(label,w)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel); buttons.accepted.connect(dlg.accept); buttons.rejected.connect(dlg.reject); form.addRow(buttons)
        if dlg.exec():
            d=copy.deepcopy(self.catalog); d['settings']={k:w.value() for k,w in widgets.items()}; self.save(d)

    def test(self):
        try:
            d,v,_=self.store.catalog(); self.output.setPlainText(explain(Classifier(d).classify(self.input.toPlainText())))
        except Exception as e: QMessageBox.warning(self,'Falha no teste',str(e))

    def export_catalog(self):
        path,_=QFileDialog.getSaveFileName(self,'Exportar catálogo','','JSON (*.json)')
        if path:
            try: Path(path).write_text(json.dumps(self.store.catalog()[0],ensure_ascii=False,indent=2),encoding='utf8')
            except Exception as e: QMessageBox.warning(self,'Falha de exportação',str(e))
    def import_catalog(self):
        path,_=QFileDialog.getOpenFileName(self,'Importar catálogo','','JSON (*.json)')
        if path:
            try:
                if Path(path).stat().st_size>10_000_000: raise ValueError('Arquivo excede 10 MB.')
                self.save(json.loads(Path(path).read_text(encoding='utf-8-sig')))
            except Exception as e: QMessageBox.warning(self,'Falha de importação',str(e))
    def restore_defaults(self):
        d=copy.deepcopy(self.catalog); defaults=default_catalog()
        for kind in ('categories','subcategories','rules'):
            mapping={x['id']:x for x in defaults[kind]}
            d[kind]=[mapping.pop(x['id'],{**x,'active':False}) for x in d[kind]]+list(mapping.values())
        d['settings']=defaults['settings']; self.save(d)
    def reclassify(self):
        mode=self.mode.currentData()
        self.start(lambda progress,cancelled:ReclassificationService(self.db).run(mode,progress,cancelled),'Reclassificando...',True)
    def start(self,fn,message,cancel=False):
        if self.worker and self.worker.isRunning(): return
        self.status.setText(message); self.tabs.setEnabled(False); self.cancel_button.setEnabled(cancel)
        self.worker=TaskWorker(fn,self); self.worker.progress.connect(self.on_progress); self.worker.result.connect(self.done); self.worker.error.connect(self.failed); self.worker.finished.connect(self.finished); self.worker.start()
    @Slot(int,int)
    def on_progress(self,current,total): self.progress.setRange(0,max(1,total)); self.progress.setValue(current); self.status.setText(f'{current} de {total} processados')
    @Slot(object)
    def done(self,result): self.status.setText(str(result)); self.refresh(); self.changed.emit()
    @Slot(str)
    def failed(self,message): self.status.setText('Falha: '+message); QMessageBox.warning(self,'Operação não concluída',message)
    @Slot()
    def finished(self): self.tabs.setEnabled(True); self.cancel_button.setEnabled(False)
    def cancel(self):
        if self.worker: self.worker.cancel()
    def review(self):
        self.review_items,_=self.repo.search(LicitacaoFilter(status_proposta='todas',only_unclassified=True,limite=200))
        low,_=self.repo.search(LicitacaoFilter(status_proposta='todas',confidence_levels=['Baixa'],limite=200))
        ids={x.id for x in self.review_items}; self.review_items.extend(x for x in low if x.id not in ids); self.review_items=self.review_items[:200]
        self.review_table.setColumnCount(2); self.review_table.setHorizontalHeaderLabels(['PNCP','Objeto — duplo clique para revisar']); self.review_table.setRowCount(len(self.review_items))
        for i,x in enumerate(self.review_items):
            self.review_table.setItem(i,0,QTableWidgetItem(x.numero_controle_pncp)); self.review_table.setItem(i,1,QTableWidgetItem(x.objeto or ''))
        self.review_table.horizontalHeader().setSectionResizeMode(1,QHeaderView.ResizeMode.Stretch)
    def open_review(self,row,col):
        dlg=QDialog(self); dlg.resize(850,600); layout=QVBoxLayout(dlg); panel=ClassificationPanel(self.db,self.review_items[row],dlg); panel.changed.connect(self.changed.emit); panel.manage_requested.connect(dlg.accept); layout.addWidget(panel); dlg.exec()
