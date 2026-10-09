"""Gera a apostila empacotada a partir da mesma fonte JSON da interface.
Requer reportlab apenas no ambiente de autoria; o aplicativo salva o PDF pronto.
"""
import hashlib
import json
from html import escape
from pathlib import Path
import sys
from reportlab.pdfgen import canvas
from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, PageBreak, KeepTogether, Flowable)
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.learning.course import load_course, ASSETS

FONT_DIR = Path('C:/Windows/Fonts')
pdfmetrics.registerFont(TTFont('Radar', str(FONT_DIR / 'segoeui.ttf')))
pdfmetrics.registerFont(TTFont('RadarBold', str(FONT_DIR / 'segoeuib.ttf')))
pdfmetrics.registerFontFamily('Radar', normal='Radar', bold='RadarBold', italic='Radar', boldItalic='RadarBold')
styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name='Text', fontName='Radar', fontSize=10.5, leading=15, spaceAfter=8, textColor=colors.HexColor('#243449')))
styles.add(ParagraphStyle(name='SmallRadar', parent=styles['Text'], fontSize=8.5, leading=12, spaceAfter=6))
styles.add(ParagraphStyle(name='TitleRadar', parent=styles['Text'], fontName='RadarBold', fontSize=24, leading=30, spaceAfter=18, textColor=colors.HexColor('#0f172a')))
styles.add(ParagraphStyle(name='SectionRadar', parent=styles['Text'], fontName='RadarBold', fontSize=12, leading=16, spaceBefore=9, spaceAfter=6, keepWithNext=True, textColor=colors.HexColor('#075985')))
styles.add(ParagraphStyle(name='IntroRadar', parent=styles['Text'], fontSize=14, leading=21, spaceAfter=18))
styles.add(ParagraphStyle(name='URLRadar', parent=styles['SmallRadar'], wordWrap='CJK', textColor=colors.HexColor('#0369a1')))
styles.add(ParagraphStyle(name='TOCRadar', parent=styles['Text'], fontSize=10.5, leading=16, leftIndent=0, firstLineIndent=0, spaceBefore=4))


def plain(text):
    return escape(str(text).replace('—', '-').replace('–', '-').replace('‑', '-'))


def para(text, style='Text'):
    return Paragraph(plain(text), styles[style])


def link(title, url):
    return Paragraph(f'<link href="{escape(url, quote=True)}" color="#0369a1">{plain(title)}</link>', styles['SmallRadar'])


class Notes(Flowable):
    def __init__(self):
        super().__init__()
        self.height = 90
    def draw(self):
        self.canv.setStrokeColor(colors.HexColor('#cbd5e1'))
        for y in (15, 38, 61, 84):
            self.canv.line(0, y, 470, y)


class CourseDocument(BaseDocTemplate):
    def afterFlowable(self, flowable):
        if hasattr(flowable, 'course_anchor'):
            anchor = flowable.course_anchor
            self.canv.bookmarkPage(anchor)
            self.canv.addOutlineEntry(flowable.getPlainText(), anchor, 0, False)
            self.notify('TOCEntry', (0, flowable.getPlainText(), self.page, anchor))


def footer(c, doc):
    width, height = A4
    c.saveState()
    c.setFillColor(colors.HexColor('#0284c7'))
    c.rect(0, height - 8, width, 8, fill=1, stroke=0)
    c.setFont('Radar', 8)
    c.setFillColor(colors.HexColor('#64748b'))
    if doc.page > 1:
        c.drawString(44, height - 30, 'RADAR NACIONAL | CURSO PARA FORNECEDORES')
    c.setStrokeColor(colors.HexColor('#cbd5e1'))
    c.line(44, 37, width - 44, 37)
    c.drawString(44, 23, 'Edição 1.0 | Revisão de fontes: 08/10/2026 | Material educacional')
    c.drawRightString(width - 44, 23, str(doc.page))
    c.restoreState()


def heading(text, anchor):
    h = para(text, 'TitleRadar')
    h.course_anchor = anchor
    return h


def build():
    data = load_course()
    out = ROOT / 'output' / 'pdf' / 'Curso_Radar_Licitacoes.pdf'
    out.parent.mkdir(parents=True, exist_ok=True)
    doc = CourseDocument(str(out), pagesize=A4, leftMargin=44, rightMargin=44,
        topMargin=50, bottomMargin=50, title=data['title'], author='Radar Nacional de Licitações')
    doc.addPageTemplates(PageTemplate(id='course', frames=[Frame(44, 50, A4[0]-88, A4[1]-100, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)], onPage=footer))
    story = [Spacer(1, 75), para('RADAR NACIONAL DE LICITAÇÕES', 'SectionRadar'),
             Spacer(1, 25), para(data['title'], 'TitleRadar'), para(data['subtitle'], 'IntroRadar'),
             para('15 módulos para organizar a empresa, participar da disputa, executar o contrato e acompanhar o recebimento.', 'IntroRadar'),
             Spacer(1, 20), para('INCLUI', 'SectionRadar'),
             para('Passo a passo • Exemplos práticos • Listas de conferência • Exercícios com gabarito • Fontes oficiais • Cursos gratuitos EV.G'),
             Spacer(1, 25), para(data['scope'], 'SmallRadar'),
             para('Trilha adicional: compra de bens públicos em leilão. Pregão e leilão têm finalidades diferentes.', 'SmallRadar'), PageBreak(),
             para('Seu roteiro de estudo', 'TitleRadar'),
             para('Leia cada aula, faça o exercício antes de consultar o gabarito e use as listas para conferir seu entendimento. Na aplicação, marque as aulas lidas e acompanhe suas respostas. Os exemplos são hipotéticos.'),
             para('A numeração abaixo é clicável no PDF. As fontes ao final também contêm links diretos.', 'SmallRadar')]
    toc = TableOfContents()
    toc.levelStyles = [styles['TOCRadar']]
    story += [toc, PageBreak()]
    for i, m in enumerate(data['modules'], 1):
        story += [heading(f'{i:02d}. {m["title"]}', m['id']), para('Objetivo: ' + m['goal'], 'SmallRadar')]
        for c in m['concepts']:
            story += [para(c['title'], 'SectionRadar'), para(c['text'])]
        story += [para('Passo a passo', 'SectionRadar')]
        for n, step in enumerate(m['steps'], 1):
            story += [para(f'{n}. {step}')]
        story += [PageBreak(), para(f'{i:02d}. Pratique e confira', 'TitleRadar'),
                  para('Exemplo prático', 'SectionRadar'), para(m['example']),
                  para('Lista de conferência', 'SectionRadar')]
        story += [para('[  ] ' + item) for item in m['checklist']]
        story += [para('Exercício de revisão', 'SectionRadar'), para(m['quiz']['question'])]
        for n, option in enumerate(m['quiz']['options']):
            story += [para(f'{chr(65+n)}. {option}')]
        story += [para('Responda antes de consultar o gabarito ao final.', 'SmallRadar'),
                  para('Anotações e aplicação ao seu edital', 'SectionRadar'), Notes(),
                  para('Base legal e fontes', 'SectionRadar')]
        for ref in m['references']:
            s = data['sources'][ref['source']]
            story += [link(s['title'] + ' - ' + ref['detail'], s['url'])]
        story += [PageBreak()]
    story += [heading('Gabarito comentado', 'gabarito')]
    for i,m in enumerate(data['modules'], 1):
        if i == 9:
            story += [PageBreak(), para('Gabarito comentado - continuação', 'TitleRadar')]
        story += [KeepTogether([para(f'{i:02d}. Alternativa {chr(65+m["quiz"]["correct"])}', 'SectionRadar'), para(m['quiz']['explanation'])])]
    story += [PageBreak(), heading('Cursos gratuitos da EV.G', 'evg'), para(data['external_note'])]
    for c in data['external_courses']:
        story += [para(c['title'], 'SectionRadar'), para(c['description']), link('Acessar o curso', c['url']), para(c['url'], 'URLRadar')]
        if c.get('alternative_url'):
            story += [link('Endereço alternativo do mesmo curso', c['alternative_url'])]
    story += [PageBreak(), heading('Fontes oficiais e abrangência', 'fontes'), para(data['scope'])]
    for n, s in enumerate(data['sources'].values()):
        if n == 6:
            story += [PageBreak(), para('Fontes oficiais - continuação', 'TitleRadar')]
        story += [KeepTogether([para(s['title'], 'SectionRadar'), link('Abrir fonte oficial', s['url']), para(s['url'], 'URLRadar')])]
    doc.multiBuild(story)
    payload = out.read_bytes()
    (ASSETS / 'course.pdf').write_bytes(payload)
    manifest = dict(version=data['version'], reviewed_on=data['reviewed_on'],
        content_sha256=hashlib.sha256((ASSETS / 'course.json').read_bytes()).hexdigest(),
        pdf_sha256=hashlib.sha256(payload).hexdigest())
    (ASSETS / 'course_pdf_manifest.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf8')
    print(out)

if __name__ == '__main__':
    build()
