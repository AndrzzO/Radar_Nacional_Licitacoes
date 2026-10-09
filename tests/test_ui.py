import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import time
import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from src.ui.main_window import MainWindow
from src.domain.entities import Licitacao
from src.domain.filters import LicitacaoFilter
from src.database.repositories import ProcurementRepository,LocationRepository
from src.application.location_service import FALLBACK_ESTADOS

@pytest.fixture
def window(db_conn):
    app=QApplication.instance() or QApplication([])
    LocationRepository(db_conn).save_estados(FALLBACK_ESTADOS)
    w=MainWindow(db_conn); w.show()
    deadline=time.monotonic()+10
    while w.page_search.query_worker.isRunning() and time.monotonic()<deadline: app.processEvents(); time.sleep(.01)
    app.processEvents()
    yield w
    w.close()
    deadline=time.monotonic()+10
    while w.isVisible() and time.monotonic()<deadline: app.processEvents(); time.sleep(.01)
    assert not w.isVisible()


def test_navigation(window):
    expected=[window.page_dashboard,window.page_search,window.page_search,window.page_saved,window.page_history,window.page_settings,window.page_classification,window.page_course]
    for i,page in enumerate(expected):
        window._navigate(i)
        assert window.stack.currentWidget() is page


def test_favorite_filter_roundtrip(window):
    f=LicitacaoFilter(ufs=['SP'],municipios_ibge=['3550308'],status_proposta='todas',esferas=['F'],modalidades_ids=[6],category_ids=[1],subcategory_ids=[1],confidence_levels=['Alta'],classification_origin='manual',primary_category_only=True,palavra_chave='software',valor_min=1250.5,data_publicacao_inicio='2026-10-01')
    window.page_search.apply_filters(f)
    result=window.page_search._construir_filtros()
    for key in ('ufs','municipios_ibge','status_proposta','esferas','modalidades_ids','category_ids','subcategory_ids','confidence_levels','classification_origin','primary_category_only','palavra_chave','valor_min','data_publicacao_inicio'): assert getattr(result,key)==getattr(f,key)


def test_tester_and_checkbox(window):
    page=window.page_classification; page.input.setPlainText('Compra de notebooks'); page.test()
    assert 'Hardware e Equipamentos' in page.output.toPlainText()
    lic=Licitacao('ui',objeto='notebooks'); ProcurementRepository(window.db_conn).upsert_batch([lic])
    items,_=window.procurement_repo.search(LicitacaoFilter(status_proposta='todas'))
    model=window.page_search.table_model; model.set_licitacoes(items)
    assert model.data(model.index(0,12),Qt.ItemDataRole.DisplayRole)=='Tecnologia da Informação'
    model.setData(model.index(0,0),Qt.CheckState.Checked.value,Qt.ItemDataRole.CheckStateRole)
    assert model.get_selected_count()==1


def test_catalog_editor_persists_and_affects_engine(window):
    from src.ui.classification_page import CatalogEditor
    from src.classification.store import ClassificationStore
    from src.classification.engine import Classifier
    store=ClassificationStore(window.db_conn); d,v,_=store.catalog()
    dialog=CatalogEditor('rules',d,parent=window)
    dialog.fields['subcategory_id'].setCurrentIndex(dialog.fields['subcategory_id'].findData(1))
    dialog.fields['expression'].setText('plataforma municipal digital')
    dialog.fields['weight'].setValue(9)
    rule=dialog.value(); rule['id']=max(r['id'] for r in d['rules'])+1; d['rules'].append(rule)
    store.save_catalog(d,v)
    assert Classifier(store.catalog()[0]).classify('plataforma municipal digital')['primary']['subcategory']=='Software e Sistemas'


def test_course_progress_quiz_and_reopen(window):
    from src.ui.course_page import CoursePage
    page = window.page_course
    window._navigate(7)
    assert window.stack.currentWidget() is page
    page.module_list.setCurrentRow(11)
    assert 'Emita a nota' in page.reader.toPlainText()
    page.check_answer()
    assert 'Selecione' in page.feedback.text()
    correct = page.data['modules'][11]['quiz']['correct']
    page.answers.button((correct + 1) % 3).setChecked(True)
    page.check_answer()
    assert 'Reveja' in page.feedback.text()
    page.answers.button(correct).setChecked(True)
    page.check_answer()
    assert 'correta' in page.feedback.text()
    page.toggle_complete()
    assert page.progress_bar.value() == 1
    reopened = CoursePage(window.settings_repo)
    try:
        reopened.module_list.setCurrentRow(11)
        assert reopened.progress_bar.value() == 1
        assert reopened.answers.checkedId() == correct
        assert 'correta' in reopened.feedback.text()
        reopened.toggle_complete()
        assert reopened.progress_bar.value() == 0
        reopened.next_button.click()
        assert reopened.index == 12
        reopened.previous_button.click()
        assert reopened.index == 11
    finally:
        reopened.close()


def test_course_pdf_button_and_cancel(window, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog, QMessageBox
    from src.learning.course import verify_pdf_assets
    target = tmp_path / 'curso.pdf'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *a: (str(target), ''))
    messages = []
    monkeypatch.setattr(QMessageBox, 'information', lambda *a: messages.append(a[-1]))
    window.page_course.pdf_button.click()
    assert target.read_bytes() == verify_pdf_assets().read_bytes()
    assert messages
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *a: ('', ''))
    window.page_course.pdf_button.click()
    assert len(messages) == 1


def test_course_links_open_browser_only_when_official(window, monkeypatch):
    from PySide6.QtGui import QDesktopServices
    from PySide6.QtCore import QUrl
    urls = []
    monkeypatch.setattr(QDesktopServices, 'openUrl', lambda u: urls.append(u.toString()) or True)
    page = window.page_course
    for item in page.data['external_courses']:
        page.open_reference(QUrl(item['url']))
    page.open_reference(QUrl('file:///C:/Windows'))
    assert urls == [item['url'] for item in page.data['external_courses']]
