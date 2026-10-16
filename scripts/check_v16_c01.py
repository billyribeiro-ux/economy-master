"""Quiet, read-only four-file author audit for a research-design chapter.

Numerical witnesses test the actual displayed inputs. They do not certify
qualitative contribution judgments, which require the retained full reading.
"""
import ast
import json
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from pathlib import Path

FILES = ('content/chapters/v16-c01.html',
         'scripts/check_v16_c01.py',
         'content/reviews/v16-c01-sources.json',
         'content/reviews/v16-c01-author.json')

def need(ok, message):
    if not ok:
        raise ValueError(message)

def number(value):
    need(type(value) in (int, F), 'exact nonboolean number required')
    return F(value)

def literal(text):
    def walk(node):
        if isinstance(node, ast.Constant):
            return number(node.value)
        if isinstance(node, (ast.Tuple, ast.List)):
            return tuple(walk(v) for v in node.elts)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            return (-1 if isinstance(node.op, ast.USub) else 1) * walk(node.operand)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            den = walk(node.right)
            need(den != 0, 'nonzero denominator')
            return walk(node.left) / den
        raise ValueError('numeric literals only')
    return walk(ast.parse(text.rsplit('=', 1)[-1].strip(), mode='eval').body)

def growth(before, after):
    before, after = number(before), number(after)
    need(before > 0 and after >= 0, 'growth requires positive baseline, nonnegative end')
    return (after-before)/before

def opportunity(reconstruction, model):
    reconstruction, model = number(reconstruction), number(model)
    need(reconstruction > 0 and model > 0, 'positive task hours')
    return reconstruction/model, model/reconstruction

class Read(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack=[]; self.ids=[]; self.exercises=[]; self.solutions=[]
        self.cases=[]; self.guides=0; self.sources={}; self.links=set()
        self.inputs={}; self.results={}; self.active=[]; self.cells=[]
    def handle_starttag(self, tag, attrs):
        data=dict(attrs)
        need(len(data)==len(attrs), 'duplicate HTML attribute')
        need(tag!='h1', 'fragment must not have h1')
        if 'id' in data:
            need(data['id'].startswith('v16-c01-') and data['id'] not in self.ids, 'unique chapter IDs')
            self.ids.append(data['id'])
        if tag=='article' and 'worked' in data.get('class','').split():
            self.cases.append(data['id'])
        if tag=='ol' and 'exercises' in data.get('class','').split():
            need(not any(t=='ol' and 'exercises' in a.get('class','').split() for t,a in self.stack), 'single exercise list')
        if tag=='li' and data.get('id','').startswith('v16-c01-e'):
            need(any(t=='ol' and 'exercises' in a.get('class','').split() for t,a in self.stack), 'exercise enclosure')
            self.exercises.append(data['id'])
        if tag=='details' and 'solutions' in data.get('class','').split(): self.guides+=1
        if 'data-solution-for' in data:
            need(any(t=='details' and 'solutions' in a.get('class','').split() for t,a in self.stack), 'solution disclosure')
            self.solutions.append(data['data-solution-for'])
        if tag=='a': self.links.add(data.get('href'))
        if 'data-source' in data:
            need(data['data-source'] not in self.sources,'unique source')
            self.sources[data['data-source']]=data['href']
        for attr, target in (('data-input',self.inputs),('data-result',self.results)):
            if attr in data:
                key=data[attr];need(key not in target,'unique marker');target[key]=''
                self.active.append((target,key,len(self.stack)))
        if tag=='td' and any(a.get('id')=='v16-c01-case2' for _,a in self.stack):
            self.cells.append(''); self.active.append((self.cells,len(self.cells)-1,len(self.stack)))
        if tag not in ('br','hr','img','meta','link','input'): self.stack.append((tag,data))
    def handle_data(self,text):
        for target,key,_ in self.active: target[key]+=text
    def handle_endtag(self,tag):
        need(self.stack and self.stack[-1][0]==tag,'balanced HTML')
        self.stack.pop();self.active=[x for x in self.active if x[2]<len(self.stack)]

def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    raw={name:(root/name).read_bytes() for name in FILES}
    review=json.loads(raw[FILES[3]]); sources=json.loads(raw[FILES[2]])
    bindings=review['payload_bindings']
    need(len(bindings)==3 and {b['path'] for b in bindings}==set(FILES[:3]),'three nonself bindings')
    for binding in bindings:
        payload=raw[binding['path']]
        need((len(payload),sha256(payload).hexdigest())==(binding['bytes'],binding['sha256']),'frozen payload')
    doc=Read();doc.feed(raw[FILES[0]].decode());doc.close();need(not doc.stack,'closed fragment')
    exercises=['v16-c01-e'+str(i) for i in range(1,9)]
    need(doc.exercises==doc.solutions==exercises,'eight exact prompt/solution pairs')
    need(doc.cases==['v16-c01-case1','v16-c01-case2'] and doc.guides==3,'worked cases and answer guides')
    need(set(review['exact_prompt_review'])==set(exercises),'full prompt review inventory')
    need(doc.sources=={s['id']:s['url'] for s in sources['sources']},'source map')
    need({'curriculum.html#v'+str(i) for i in (12,13,14,15)}|{'curriculum.html#v16-c02'}<=doc.links,'prerequisites and successor')
    need(doc.cells==['40','36','Matched','60','54','Matched','Missing','90','Observed only at date 1','20','Missing','Observed only at date 0'],'actual table cells')
    inputs={k:literal(v) for k,v in doc.inputs.items()};shown={k:literal(v) for k,v in doc.results.items()}
    expected_inputs={'time':(12,10),'allocation':(20,30,20,30,20),'stocks':(40,36,60,54,90,20),'completion-one':(90,20),'completion-two':(0,100),'task-hours':(8,20,12,24),'alternative-a1':44,'extra-hours':15,'overrun-hours':25}
    need(inputs==expected_inputs,'actual displayed assumptions')
    comparisons=0
    def eq(a,b,label):
        nonlocal comparisons
        if isinstance(a,(tuple,list)) or isinstance(b,(tuple,list)):
            need(isinstance(a,(tuple,list)) and isinstance(b,(tuple,list)) and len(a)==len(b),label+' shape')
            for x,y in zip(a,b):eq(x,y,label)
        else:
            comparisons+=1;need(a==b,label)
    A0,A1,B0,B1,C1,D0=inputs['stocks']
    raw0,raw1=A0+B0+D0,A1+B1+C1
    matched0,matched1=A0+B0,A1+B1
    expected={'hours':inputs['time'][0]*inputs['time'][1], 'allocated':sum(inputs['allocation']),
              'raw-totals':(raw0,raw1), 'raw-growth':growth(raw0,raw1),
              'matched-totals':(matched0,matched1),'matched-growth':growth(matched0,matched1),
              'mean-growth':(growth(A0,A1)+growth(B0,B1))/2,
              'decomposition':(matched1-matched0,C1,D0,raw1-raw0)}
    eq(matched1-matched0+C1-D0,raw1-raw0,'coverage accounting')
    for key in ('completion-one','completion-two'):
        C0,D1=inputs[key];before=raw0+C0;after=raw1+D1
        expected[key]=(before,after,growth(before,after))
    need(expected['completion-one'][2]<0<expected['completion-two'][2],'opposite signs consistent with observed cells')
    a,b,c,d=inputs['task-hours'];oa,ia=opportunity(a,b);ob,ib=opportunity(c,d)
    expected['e1-costs']=(oa,ob);expected['e1-inverse']=(ia,ib)
    need(a<c and b<d and oa<ob and ib<ia,'absolute and comparative advantages')
    alt=inputs['alternative-a1'];expected['e3-aggregate']=growth(matched0,alt+B1)
    expected['e3-mean']=(growth(A0,alt)+growth(B0,B1))/2
    eq(expected['e3-aggregate'],A0/matched0*growth(A0,alt)+B0/matched0*growth(B0,B1),'weighted growth identity')
    need(expected['e3-aggregate']!=expected['e3-mean'],'different estimands')
    allocation=inputs['allocation'];extra=inputs['extra-hours']
    expected['e5-allocation']=(allocation[0]+extra,*allocation[1:4],allocation[4]-extra)
    expected['e5-overrun']=sum(allocation[:4])+inputs['overrun-hours']
    eq(sum(expected['e5-allocation']),expected['hours'],'budget balance')
    eq(expected['e5-overrun']-expected['hours'],5,'overrun')
    need(set(shown)==set(expected),'all displayed result groups')
    for key,result in expected.items():eq(shown[key],result,'display '+key)
    # Alternative populations, units and missing-data completions; not novel research results.
    for endA in (0,36,40,44,80):
        for endB in (0,54,60,120):
            aggregate=growth(A0+B0,endA+endB)
            eq(aggregate,A0/(A0+B0)*growth(A0,endA)+B0/(A0+B0)*growth(B0,endB),'weighted identity alternatives')
            for scale in (F(1,1000),F(1),F(10)):
                eq(aggregate,growth(scale*(A0+B0),scale*(endA+endB)),'unit invariance')
            eq(endA+endB+C1-(A0+B0+D0),endA+endB-A0-B0+C1-D0,'coverage alternatives')
    for c0 in (0,20,90,200):
        for d1 in (0,20,100,200):
            eq((raw1+d1)-(raw0+c0),(matched1-matched0)+(C1-c0)+(d1-D0),'completed four-bank identity')
    for extra in (0,15,20):
        eq(sum(allocation[:4])+extra+allocation[4]-extra,120,'reserve domain')
        need(allocation[4]-extra>=0,'nonnegative reserve')
    invalid=[lambda:number(True),lambda:number(1.0),lambda:literal('f(1)'),lambda:literal('1/0'),lambda:growth(0,1),lambda:growth(-1,1),lambda:growth(1,-1),lambda:opportunity(0,2),lambda:opportunity(2,-1)]
    rejected=0
    for operation in invalid:
        try:operation()
        except ValueError:rejected+=1
        else:raise ValueError('invalid numeric domain accepted')
    for name,payload in raw.items():need((root/name).read_bytes()==payload,'immutable payload')
    return {'chapter':'v16-c01','status':'passed','worked_cases':2,'solutions':8,'input_groups':len(inputs),'result_groups':len(shown),'comparisons':comparisons,'rejected_inputs':rejected,'runtime_files':4,'qualitative_scope':'Retained full author reading; independent root/peer review still required.'}

if __name__=='__main__':
    check()
