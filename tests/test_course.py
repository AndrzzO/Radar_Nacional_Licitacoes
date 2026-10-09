import json
from pathlib import Path
import pytest
from src.learning import course


def test_complete_course_and_pdf_match():
    data = course.load_course()
    assert len(data['modules']) == 15
    assert {'empresa', 'cadastros', 'proposta', 'contrato', 'execucao', 'pagamento', 'leilao'} <= {m['id'] for m in data['modules']}
    assert len(data['external_courses']) == 3
    for i, module in enumerate(data['modules']):
        assert module['title'] in course.lesson_html(data, i)
        assert module['steps'] and module['checklist'] and module['references']
    assert course.verify_pdf_assets().read_bytes().startswith(b'%PDF-')


def test_pdf_export_offline_with_extension(tmp_path):
    result = course.export_course_pdf(tmp_path / 'apostila')
    assert result.name == 'apostila.pdf'
    assert result.read_bytes() == course.verify_pdf_assets().read_bytes()


def test_failed_export_preserves_existing_document(tmp_path, monkeypatch):
    target = tmp_path / 'apostila.pdf'
    target.write_bytes(b'original')
    def fail(*args):
        raise PermissionError('arquivo ocupado')
    monkeypatch.setattr(course.os, 'replace', fail)
    with pytest.raises(PermissionError):
        course.export_course_pdf(target)
    assert target.read_bytes() == b'original'
    assert list(tmp_path.iterdir()) == [target]


def test_stale_pdf_is_rejected(tmp_path, monkeypatch):
    for name in ('course.json', 'course.pdf', 'course_pdf_manifest.json'):
        (tmp_path / name).write_bytes((course.ASSETS / name).read_bytes())
    (tmp_path / 'course.json').write_text('{}', encoding='utf8')
    monkeypatch.setattr(course, 'ASSETS', tmp_path)
    with pytest.raises(ValueError, match='apostila'):
        course.verify_pdf_assets()


@pytest.mark.parametrize('url', ['file:///C:/Windows', 'https://www.gov.br.evil.test', 'http://www.gov.br', 'https://user@www.gov.br', 'javascript:alert(1)'])
def test_non_official_links_blocked(url):
    assert not course.official_url(url)


@pytest.mark.parametrize('raw', ['null', '[]', '{broken', '"string"', '{"unknown":{},"mapa":null}'])
def test_invalid_progress_does_not_break_course(raw):
    class Settings:
        def get(self, *args):
            return raw
    assert course.read_progress(Settings(), course.load_course()) == {}
