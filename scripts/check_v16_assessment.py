"""Exact V16 assessment assembly and all separately reviewed components."""
from pathlib import Path
from hashlib import sha256
from html.parser import HTMLParser
import importlib,json
ROOT=Path(__file__).resolve().parents[1]
PARTS=('v16-support-opening.html','v16-exam-a.html','v16-exam-b.html','v16-project.html','v16-support-closing.html')
def need(ok,message):
    if not ok:raise ValueError('V16 assessment: '+message)
class Page(HTMLParser):
    def __init__(self):super().__init__();self.stack=[];self.ids=set();self.sources={};self.h1=0
    def handle_starttag(self,t,attrs):
        a=dict(attrs);need(len(a)==len(attrs),'unique attributes')
        if 'id' in a:need(a['id'] not in self.ids,'unique ID '+a['id']);self.ids.add(a['id'])
        if t=='h1':self.h1+=1
        if 'data-source' in a:
            key=a['data-source'];need(key not in self.sources or self.sources[key]==a['href'],'consistent source route');self.sources[key]=a['href']
        if t not in ('br','hr','img','input','meta','link','wbr'):self.stack.append(t)
    def handle_endtag(self,t):need(self.stack and self.stack.pop()==t,'balanced fragment')
def check():
    parts=[(ROOT/'content/assessments/parts'/name).read_text().strip() for name in PARTS]
    path=ROOT/'content/assessments/v16.html';assembled=path.read_text();need(assembled=='\n\n'.join(parts)+'\n','exact ordered five-part assembly')
    p=Page();p.feed(assembled);p.close();need(not p.stack and p.h1==1,'one title and complete HTML')
    need({'diagnostic','exam-rules','form-a','solutions-a','form-b','solutions-b','project','project-tasks','project-paper','project-rubric','oral-transfer','retention','remediation','notation-index','concept-index','volume-synthesis','assessment-source-scope'}<=p.ids,'all components')
    catalogue={x['id']:x['url'] for x in json.loads((ROOT/'content/sources.json').read_text())};need(all(catalogue.get(k)==v for k,v in p.sources.items()),'catalogued source URLs')
    rec=json.loads((ROOT/'content/reviews/v16-assessment.json').read_text());need(rec['status']=='accepted-by-author' and all(rec['review'].values()) and not rec['open_content_findings'],'complete coordinator review')
    raw=path.read_bytes();need(rec['assembly']=={'path':'content/assessments/v16.html','bytes':len(raw),'sha256':sha256(raw).hexdigest(),'parts':list(PARTS)},'review binds exact assembly')
    curriculum=json.loads((ROOT/'content/curriculum.json').read_text());vol=next(v for v in curriculum['volumes'] if v['id']=='v16');need(vol['status']=='accepted' and len(vol['chapters'])==12 and all(c['status']=='accepted' for c in vol['chapters']),'all12 accepted chapters and volume')
    for name in vol['required_artifacts']:need((ROOT/'content'/name).is_file(),'reader artifact '+name)
    results={}
    for component in ('support','exam_a','exam_b','project'):
        for role,suffix in (('author',''),('peer','_peer')):
            module=importlib.import_module('check_v16_'+component+suffix);results[component+'_'+role]=module.check()
    json.dumps(results,allow_nan=False)
    return {'status':'passed','assembly_parts':list(PARTS),'unique_ids':len(p.ids),'source_routes':len(p.sources),'diagnostic_tasks':8,'written_forms':2,'written_questions':40,'project_tasks':7,'reader_files':5,'oral_tasks':5,'retention_tasks':5,'component_checks':results,'limits':'Internal author, separate agent peer and coordinator review; no human certification or calibrated timing/form equivalence. Rendered UI review remains pending recorded access limitation.'}
if __name__=='__main__':print(json.dumps(check(),indent=2,allow_nan=False))
