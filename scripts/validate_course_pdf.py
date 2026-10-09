"""QA textual do PDF final; use o runtime de autoria com pypdf."""
import json
from pathlib import Path
import sys
from pypdf import PdfReader
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
from src.learning.course import load_course, verify_pdf_assets
p=verify_pdf_assets()
r=PdfReader(p)
texts=[page.extract_text() or '' for page in r.pages]
all_text=' '.join(texts)
data=load_course()
for module in data['modules']:
    assert module['title'] in all_text, module['title']
    assert module['quiz']['question'] in all_text, module['id']
assert 'Gabarito comentado' in all_text
uris=[]
for page in r.pages:
    for ann in page.get('/Annots', []):
        action=ann.get_object().get('/A', {})
        if action.get('/URI'):
            uris.append(action['/URI'])
for c in data['external_courses']:
    assert c['url'] in uris
assert all(len(t)>150 for t in texts)
result=dict(pages=len(r.pages),modules=len(data['modules']),external_courses=len(data['external_courses']),links=len(uris),all_modules_and_questions_present=True)
(root/'scratch'/'course_pdf_validation.json').write_text(json.dumps(result,indent=2),encoding='utf8')
print(json.dumps(result))
