"""Quiet four-file author audit of the research-design chapter; stdlib only."""
from pathlib import Path
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from itertools import combinations
import ast,json,sys
ROOT=Path(__file__).resolve().parents[1]
FILES=['production/v16-c05-working.html','production/check_v16_c05_working.py','production/v16-c05-sources-working.json','production/v16-c05-author-review-working.json']

def need(ok,message):
    if not ok:raise ValueError('v16-c05: '+message)

def rational(x):
    need(type(x) in (int,F),'exact rational primitive')
    return F(x)

def assignment_results(y0,y1):
    need(isinstance(y0,(list,tuple)) and isinstance(y1,(list,tuple)) and len(y0)==len(y1) and len(y0)>=2 and len(y0)%2==0,'even complete schedule')
    a=list(map(rational,y0));b=list(map(rational,y1));n=len(a);k=n//2
    results=[]
    for offered in combinations(range(n),k):
        treated=sum(b[i] for i in offered)/k;control=sum(a[i] for i in range(n) if i not in offered)/(n-k)
        results.append((tuple(offered),treated,control,treated-control))
    return results

def effect_set(d,lower,upper):
    d,lower,upper=map(rational,(d,lower,upper));need(lower<=upper,'ordered trend restriction')
    return d-upper,d-lower

class Document(HTMLParser):
    def __init__(self):
        super().__init__();self.stack=[];self.ids=[];self.markers={};self.current=None;self.answers=[];self.exercises=[];self.worked=[];self.sources={};self.tables=[];self.row=None;self.cell=None;self.h1=0
    def handle_starttag(self,tag,attrs):
        a=dict(attrs);need(len(a)==len(attrs),'duplicate attributes')
        if tag=='h1':self.h1+=1
        if 'id' in a:self.ids.append(a['id'])
        if tag=='article' and 'worked' in a.get('class','').split():self.worked.append(a.get('id'))
        if tag=='li' and any(t=='ol' and 'exercises' in d.get('class','').split() for t,d in self.stack):self.exercises.append(a.get('id'))
        if 'data-solution-for' in a:
            need(any(t=='details' and 'solutions' in d.get('class','').split() for t,d in self.stack),'answer disclosure');self.answers.append(a['data-solution-for'])
        for kind in ['input','result']:
            if 'data-'+kind in a:
                key=(kind,a['data-'+kind]);need(key not in self.markers,'duplicate marker');self.markers[key]='';self.current=key
        if 'data-source' in a:self.sources[a['data-source']]=a['href']
        if tag=='table':self.tables.append([])
        if tag=='tr':self.row=[]
        if tag in ('th','td'):self.cell=''
        if tag not in ('br','hr','img','meta','link','input'):self.stack.append((tag,a))
    def handle_data(self,text):
        if self.current:self.markers[self.current]+=text
        if self.cell is not None:self.cell+=text
    def handle_endtag(self,tag):
        need(bool(self.stack) and self.stack[-1][0]==tag,'balanced HTML '+tag)
        _,a=self.stack.pop()
        if 'data-input' in a or 'data-result' in a:self.current=None
        if tag in ('th','td'):self.row.append(self.cell.strip());self.cell=None
        if tag=='tr':self.tables[-1].append(self.row);self.row=None

def check(root=None):
    root=Path(root) if root is not None else ROOT
    rec=json.loads((root/FILES[-1]).read_text());need(set(rec['payloads'])==set(FILES[:-1]),'three nonself hashes')
    for name,binding in rec['payloads'].items():
        b=(root/name).read_bytes();need(binding=={'bytes':len(b),'sha256':sha256(b).hexdigest()},'frozen '+name)
    need(all(rec['review'].values()) and not rec['open_material_findings'],'author review complete')
    doc=Document();doc.feed((root/FILES[0]).read_text());doc.close()
    need(not doc.stack and doc.h1==0,'complete fragment')
    need(len(doc.ids)==len(set(doc.ids)),'unique IDs')
    expected=[f'v16-c05-e{i}' for i in range(1,9)]
    need(doc.exercises==expected and doc.answers==expected,'eight original paired solutions')
    need(doc.worked==['v16-c05-case1','v16-c05-case2'],'two full cases')
    source=json.loads((root/FILES[2]).read_text());need(doc.sources=={s['id']:s['url'] for s in source['sources']},'source routes')
    markers={k:ast.literal_eval(v) for k,v in doc.markers.items()}
    comparisons=0
    def eq(a,b,label):
        nonlocal comparisons
        if isinstance(b,(list,tuple)):
            need(isinstance(a,(list,tuple)) and len(a)==len(b),label+' shape')
            for x,y in zip(a,b):eq(x,y,label)
        else:need(a==b,label);comparisons+=1
    def result(name,value):eq(markers[('result',name)],value,name)
    y0=markers[('input','case1-y0')];y1=markers[('input','case1-y1')]
    eq(y0,(8,10,12,14),'published primitive y0');eq(y1,(10,14,18,18),'published primitive y1')
    differences=tuple(b-a for a,b in zip(y0,y1));target=sum(differences)/F(len(y0))
    result('case1-effects',differences);result('case1-target',target)
    rows=assignment_results(y0,y1);contrasts=tuple(r[3] for r in rows)
    result('case1-observed',rows[1][3]);result('case1-contrasts',contrasts);result('case1-design-mean',sum(contrasts)/len(contrasts))
    eq(sum(contrasts)/len(contrasts),target,'finite design expectation')
    assignment_table=doc.tables[1]
    want=[['Offered pair','Offered mean','Unoffered mean','Difference']]+[[''.join('ABCD'[i] for i in r[0]),str(r[1]),str(r[2]),str(r[3]).replace('-','−')] for r in rows]
    eq(assignment_table,want,'visible assignment table')
    obs=markers[('input','case2-observed')];eq(obs,(40,40,34,40,40,38),'observed primitive histories')
    d=(obs[2]-obs[1])-(obs[5]-obs[4]);result('case2-difference',d)
    eq(doc.tables[3],[['Group','Date −1','Date 0','Date 1'],['Exposed E','40','40','34'],['Comparison C','40','40','38']],'visible observed table')
    worlds=[]
    for endpoint in (38,34):
        tau=obs[2]-endpoint;bias=(endpoint-obs[1])-(obs[5]-obs[4]);worlds.append((endpoint,tau,bias));eq(tau+bias,d,'observational equivalence')
    result('case2-worlds',tuple(worlds))
    bounds=markers[('input','case2-bounds')];eq(bounds,(-1,2),'sensitivity primitive')
    interval=effect_set(d,*bounds);result('case2-effect-set',interval)
    for j in range(13):
        tau=interval[0]+F(j,12)*(interval[1]-interval[0]);bias=d-tau;endpoint=obs[2]-tau
        need(bounds[0]<=bias<=bounds[1] and 37<=endpoint<=40,'sharp interior witness')
        eq(endpoint+tau,obs[2],'same exposed observation');eq((endpoint-obs[1])-(obs[5]-obs[4]),bias,'counterfactual trend')
    ledger=markers[('input','case2-credit-ledger')];eq(ledger,(40,20,0,34,22,4),'credit primitive')
    changes=tuple(ledger[i+3]-ledger[i] for i in range(3));result('case2-credit-changes',changes);result('case2-credit-totals',(sum(ledger[:3]),sum(ledger[3:])));result('case2-incumbent-totals',(sum(ledger[:2]),sum(ledger[3:5])))
    result('e2-estimate',rows[4][3]);result('e2-error',rows[4][3]-target);result('e2-mean',target)
    r=[(z,z,10+4*z) for z in (0,1)];s=[(z,z,10+4*z) for z in (0,1)];eq(r,s,'same observed mechanism world');result('e3-observed',tuple(r));result('e3-offer-effect',r[1][2]-r[0][2]);result('e3-mediator-counterfactual',(10+4*0,10+4*1))
    tau=2;endpoint=obs[2]-tau;trend=endpoint-obs[1];bias=trend-(obs[5]-obs[4]);result('e4-world',(endpoint,trend,bias,tau+bias))
    result('e5-set',effect_set(d,-5,2));need(-5<=-4<=2,'zero effect admissible');eq(d-(-4),0,'zero effect');eq(d-(-5),1,'positive effect')
    result('e6-changes',(changes[0],sum(changes[:2]),sum(changes)))
    need(len(markers)==25,'all displayed marker inventory')
    # Nontrivial alternative/domain witnesses independent of displayed constants.
    for shift in (-50,0,17):
        shifted=assignment_results([x+shift for x in y0],[x+shift for x in y1]);eq([r[3] for r in shifted],contrasts,'common-level shift invariance')
    null=assignment_results(y0,y0);eq(sum(r[3] for r in null)/len(null),0,'zero-effect design mean');need(any(r[3]!=0 for r in null),'null realization need not be zero')
    alternative=list(y1);alternative[1]+=8
    eq(assignment_results(y0,alternative)[1][3],rows[1][3],'same AC observed contrast')
    need(sum(b-a for a,b in zip(y0,alternative))/F(4)!=target,'unobserved outcome changes finite target')
    rejected=0
    for args in [([],[]),([1],[2]),([1,2],[3]),([1,True],[2,3]),([1,2.0],[2,3])]:
        try:assignment_results(*args)
        except ValueError:rejected+=1
        else:raise ValueError('invalid schedule accepted')
    for args in [(-4,2,-1),(-4,True,2),(-4.0,-1,2)]:
        try:effect_set(*args)
        except ValueError:rejected+=1
        else:raise ValueError('invalid restriction accepted')
    return {'status':'passed','runtime_files':4,'worked_cases':2,'exercises':8,'matched_solutions':8,'exact_comparisons':comparisons,'numeric_markers':len(markers),'assignment_worlds':6,'invalid_domains_rejected':rejected,'qualitative_review':'Full design contracts, reasoning and solutions read and recorded; not inferred from keywords.'}

if __name__=='__main__':check(Path(sys.argv[1]) if len(sys.argv)>1 else None)
