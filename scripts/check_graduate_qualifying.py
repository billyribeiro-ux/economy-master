"""Exact graduate qualifying assembly and separately reviewed component gates."""
import importlib,json
from html.parser import HTMLParser
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PARTS=('graduate-support-opening.html','graduate-econometrics.html','graduate-micro.html','graduate-macro.html','graduate-support-closing.html')
PREFIX='<p class="eyebrow">Cumulative assessment · Volumes 12–14</p>\n<h1>Graduate qualifying sequence</h1>\n<p class="lead">Defend an econometric conclusion, an economic mechanism and a funded macro-finance allocation through complete derivations and changed assumptions.</p>\n\n'
class Structure(HTMLParser):
    def __init__(self):super().__init__();self.stack=[];self.ids=[];self.h1=0;self.prompts=[];self.answers=[]
    def handle_starttag(self,t,a):
        a=dict(a)
        if 'id'in a:self.ids.append(a['id'])
        if t=='h1':self.h1+=1
        if t=='li' and 'id'in a and 'data-points'in a:self.prompts.append(a['id'])
        if 'data-solution-for'in a:self.answers.append(a['data-solution-for'])
        if t not in('br','hr','img','meta','link','input'):self.stack.append(t)
    def handle_endtag(self,t):
        if not self.stack or self.stack.pop()!=t:raise ValueError('unbalanced qualifying markup')
def check():
    expected=PREFIX+'\n\n'.join((ROOT/'content/cross-assessments/parts'/f).read_text().strip()for f in PARTS)+'\n';actual=(ROOT/'content/cross-assessments/graduate-qualifying.html').read_text()
    if actual!=expected:raise ValueError('qualifying assembly differs from frozen components')
    p=Structure();p.feed(actual);p.close()
    if p.stack or p.h1!=1 or len(set(p.ids))!=len(p.ids):raise ValueError('qualifying headings/IDs')
    anchors={'graduate-rules','graduate-oral','graduate-remediation','graduate-evaluator','graduate-source-scope'}|{'graduate-'+field+'-'+form for field in('econometrics','micro','macro')for form in('a','b')}
    if not anchors<=set(p.ids):raise ValueError('qualifying missing field/support anchor')
    # Component parsers validate their exact scoring conventions and all numerical displays.
    results={}
    for field in('support','econometrics','micro','macro'):
        for suffix in('','_peer'):
            m=importlib.import_module('check_graduate_'+field+suffix);results[field+suffix]=m.check(ROOT)
    if len(p.prompts)!=126 or len(p.answers)!=126 or set(p.prompts)!=set(p.answers):raise ValueError('120 written subparts and six two-part oral answers required')
    result={'status':'passed','fields':3,'written_forms':6,'written_solved_subparts':120,'oral_problems':6,'oral_baseline_changed_parts':12,'remediation_chapters':36,'unique_ids':len(p.ids),'exact_parts':list(PARTS),'component_checks':results,'limits':'Machine-assisted substantive and numerical review; uncalibrated timing/score thresholds; no human credential or rendered UI claim.'};json.dumps(result,allow_nan=False);return result
if __name__=='__main__':check()
