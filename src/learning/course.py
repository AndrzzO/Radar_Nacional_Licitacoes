"""Conteúdo compartilhado pela interface e pela apostila offline."""
import hashlib
import json
import os
from html import escape
from pathlib import Path
import tempfile
from urllib.parse import urlparse

ASSETS = Path(__file__).resolve().parent
ALLOWED_HOSTS = {"www.planalto.gov.br", "www.gov.br", "pncp.gov.br", "www.escolavirtual.gov.br", "www5.escolavirtual.gov.br"}


def official_url(url):
    parsed = urlparse(url)
    return parsed.scheme == "https" and parsed.hostname in ALLOWED_HOSTS and not parsed.username and not parsed.password and parsed.port in (None, 443)


def load_course():
    data = json.loads((ASSETS / "course.json").read_text(encoding="utf8"))
    ids = [m["id"] for m in data["modules"]]
    if not ids or len(ids) != len(set(ids)):
        raise ValueError("Identificadores de módulos inválidos")
    for source in data["sources"].values():
        if not official_url(source["url"]):
            raise ValueError("Referência não oficial")
    for course in data["external_courses"]:
        for key in ("url", "alternative_url"):
            if key in course and not official_url(course[key]):
                raise ValueError("Link de curso não oficial")
    for module in data["modules"]:
        quiz = module["quiz"]
        if not 0 <= quiz["correct"] < len(quiz["options"]):
            raise ValueError("Gabarito inválido")
        for ref in module["references"]:
            if ref["source"] not in data["sources"]:
                raise ValueError("Referência ausente")
    return data


def html_document(body):
    return '<html><head><style>body {font-family:Segoe UI; font-size:11pt; color:#243449;} h1 {font-size:20pt; color:#0f172a;} h2 {font-size:14pt; color:#075985;} p,li {line-height:1.5;} a {color:#0369a1;} .meta {color:#526479;}</style></head><body>' + body + '</body></html>'


def lesson_html(data, index):
    m = data["modules"][index]
    parts = [f'<p class="meta">MÓDULO {index + 1:02d} / {len(data["modules"])} · Revisão: 08/10/2026</p>',
             f'<h1>{escape(m["title"])}</h1>', f'<p><b>Objetivo:</b> {escape(m["goal"])}</p>']
    for section in m["concepts"]:
        parts += [f'<h2>{escape(section["title"])}</h2>', f'<p>{escape(section["text"])}</p>']
    parts += ['<h2>Passo a passo</h2><ol>']
    parts += [f'<li>{escape(step)}</li>' for step in m["steps"]]
    parts += ['</ol><h2>Exemplo prático</h2>', f'<p>{escape(m["example"])}</p>', '<h2>Antes de avançar</h2><ul>']
    parts += [f'<li>{escape(item)}</li>' for item in m["checklist"]]
    parts += ['</ul><h2>Base legal e fontes</h2>']
    for ref in m["references"]:
        source = data["sources"][ref["source"]]
        parts += [f'<p><a href="{escape(source["url"], quote=True)}">{escape(source["title"])}</a><br>{escape(ref["detail"])}</p>']
    return html_document(''.join(parts))


def resources_html(data):
    parts = ['<h1>Cursos gratuitos da EV.G</h1>', f'<p>{escape(data["external_note"])}</p>']
    for course in data["external_courses"]:
        parts += [f'<h2>{escape(course["title"])}</h2><p>{escape(course["description"])}</p>',
                  f'<p><a href="{escape(course["url"], quote=True)}">Acessar o curso na EV.G</a></p>']
        if course.get("alternative_url"):
            parts += [f'<p><a href="{escape(course["alternative_url"], quote=True)}">Endereço alternativo do mesmo curso</a></p>']
    return html_document(''.join(parts))


def sources_html(data):
    parts = ['<h1>Fontes e abrangência</h1>', f'<p>{escape(data["scope"])}</p>']
    for source in data["sources"].values():
        parts += [f'<p><a href="{escape(source["url"], quote=True)}">{escape(source["title"])}</a></p>']
    return html_document(''.join(parts))


def verify_pdf_assets():
    manifest = json.loads((ASSETS / "course_pdf_manifest.json").read_text(encoding="utf8"))
    for name, key in (("course.json", "content_sha256"), ("course.pdf", "pdf_sha256")):
        if hashlib.sha256((ASSETS / name).read_bytes()).hexdigest() != manifest[key]:
            raise ValueError("A apostila não corresponde à versão do curso. Gere novamente o PDF.")
    return ASSETS / "course.pdf"


def export_course_pdf(destination):
    source = verify_pdf_assets()
    target = Path(destination)
    if target.suffix.lower() != ".pdf":
        target = target.with_suffix(".pdf")
    if target.resolve() == source.resolve():
        raise ValueError("Escolha outra pasta para salvar a apostila.")
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent, suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(source.read_bytes())
        os.replace(temporary, target)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()
    return target


def read_progress(settings, data):
    key = "course_progress_" + data["version"]
    try:
        progress = json.loads(settings.get(key, "{}"))
        if not isinstance(progress, dict):
            return {}
    except (ValueError, TypeError):
        return {}
    valid_ids = {m["id"] for m in data["modules"]}
    return {k: v for k, v in progress.items() if k in valid_ids and isinstance(v, dict)}
