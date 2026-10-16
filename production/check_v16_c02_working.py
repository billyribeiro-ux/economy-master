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

FILES = ('production/v16-c02-working.html',
         'production/check_v16_c02_working.py',
         'production/v16-c02-sources-working.json',
         'production/v16-c02-author-review-working.json')

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
            need(data['id'].startswith('v16-c02-') and data['id'] not in self.ids, 'unique chapter IDs')
            self.ids.append(data['id'])
        if tag=='article' and 'worked' in data.get('class','').split():
            self.cases.append(data['id'])
        if tag=='ol' and 'exercises' in data.get('class','').split():
            need(not any(t=='ol' and 'exercises' in a.get('class','').split() for t,a in self.stack), 'single exercise list')
        if tag=='li' and data.get('id','').startswith('v16-c02-e'):
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
        if tag=='td' and any(a.get('id')=='v16-c02-case2' for _,a in self.stack):
            self.cells.append(''); self.active.append((self.cells,len(self.cells)-1,len(self.stack)))
        if tag not in ('br','hr','img','meta','link','input'): self.stack.append((tag,data))
    def handle_data(self,text):
        for target,key,_ in self.active: target[key]+=text
    def handle_endtag(self,tag):
        need(self.stack and self.stack[-1][0]==tag,'balanced HTML')
        self.stack.pop();self.active=[x for x in self.active if x[2]<len(self.stack)]

def contrasts(x, a, beta, u):
    need(len(x)==2 and len(a)==2 and len(u)==4, 'two banks two firms')
    x=tuple(map(number,x));a=tuple(map(number,a));beta=number(beta);u=tuple(map(number,u))
    need(x[0]!=x[1], 'within-firm exposure variation')
    y=tuple(a[f]+beta*x[b]+u[2*f+b] for f in range(2) for b in range(2))
    differences=(y[0]-y[1], y[2]-y[3])
    ratios=tuple(d/(x[0]-x[1]) for d in differences)
    return y,differences,ratios

def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    raw={name:(root/name).read_bytes() for name in FILES}
    review=json.loads(raw[FILES[3]]);sources=json.loads(raw[FILES[2]])
    bindings=review['payload_bindings']
    need(len(bindings)==3 and {b['path'] for b in bindings}==set(FILES[:3]),'three nonself bindings')
    for b in bindings:
        payload=raw[b['path']]
        need((len(payload),sha256(payload).hexdigest())==(b['bytes'],b['sha256']),'frozen payload')
    doc=Read();doc.feed(raw[FILES[0]].decode());doc.close();need(not doc.stack,'closed fragment')
    exercises=['v16-c02-e'+str(i) for i in range(1,9)]
    need(doc.exercises==doc.solutions==exercises,'eight matched prompt/solution pairs')
    need(doc.cases==['v16-c02-case1','v16-c02-case2'] and doc.guides==3,'two actual cases and guides')
    need(set(review['exact_prompt_review'])==set(exercises),'full reading inventory')
    need(doc.sources=={s['id']:s['url'] for s in sources['sources']} and len(doc.sources)==5,'five scoped source routes')
    need({'v16-c01.html','curriculum.html#v16-c03'}<=doc.links,'dependency and successor')
    inputs={k:literal(v) for k,v in doc.inputs.items()};shown={k:literal(v) for k,v in doc.results.items()}
    need(inputs=={'baseline':(-1,0,2,3,5),'demand':(-1,0,-1,0),'exercise-demand':(-2,0,-2,0),'exercise-common':(7,-2)},'actual displayed assumptions')
    x=inputs['baseline'][:2];beta=inputs['baseline'][2];a=inputs['baseline'][3:]
    y,d,r=contrasts(x,a,beta,(0,0,0,0))
    expected={'baseline-y':y,'baseline-differences':d,'baseline-slopes':r}
    yy,dd,rr=contrasts(x,a,beta,inputs['demand'])
    expected.update({'demand-y':yy,'demand-comparison':(*dd,*rr)})
    e3,_,s3=contrasts(x,inputs['exercise-common'],beta,(0,0,0,0))
    e4,_,s4=contrasts(x,a,beta,inputs['exercise-demand'])
    expected.update({'e3-y':e3,'e3-slopes':s3,'e4-y':e4,'e4-slopes':s4})
    comparisons=0
    def eq(v,w,label):
        nonlocal comparisons
        if isinstance(v,(tuple,list)) or isinstance(w,(tuple,list)):
            need(isinstance(v,(tuple,list)) and isinstance(w,(tuple,list)) and len(v)==len(w),label+' shape')
            for q,z in zip(v,w):eq(q,z,label)
        else:
            comparisons+=1;need(v==w,label)
    need(set(expected)==set(shown),'all displayed result groups')
    for key,value in expected.items():eq(shown[key],value,'display '+key)
    eq(yy,contrasts(x,a,3,(0,0,0,0))[0],'case2 observational equivalence')
    eq(e4,contrasts(x,a,4,(0,0,0,0))[0],'exercise4 observational equivalence')
    # Complete finite alternative menu: common-component cancellation and differential contamination.
    for xx in ((-1,0),(0,2),(3,-2)):
        for aa in ((0,0),(7,-2),(-4,9)):
            for bb in (F(-2),F(0),F(2),F(5,2)):
                yy,dd,rr=contrasts(xx,aa,bb,(0,0,0,0));eq(rr,(bb,bb),'common component cancels')
                for gamma in (F(-1),F(0),F(3,2)):
                    uu=tuple(gamma*xx[b] for f in range(2) for b in range(2))
                    observed,_,ratios=contrasts(xx,aa,bb,uu)
                    alternative,_,_=contrasts(xx,aa,bb+gamma,(0,0,0,0))
                    eq(observed,alternative,'equivalent supply/demand decompositions')
                    eq(ratios,(bb+gamma,bb+gamma),'differential contamination')
    bad=[lambda:number(True),lambda:number(1.5),lambda:literal('f(1)'),lambda:literal('1/0'),lambda:contrasts((0,0),(3,5),2,(0,0,0,0)),lambda:contrasts((1,),(3,5),2,(0,0,0,0)),lambda:contrasts((-1,0),(3,),2,(0,0,0,0)),lambda:contrasts((-1,0),(3,5),2,(0,0)),lambda:contrasts((-1,0),(3,5),True,(0,0,0,0))]
    rejected=0
    for operation in bad:
        try:operation()
        except ValueError:rejected+=1
        else:raise ValueError('invalid domain accepted')
    for name,payload in raw.items():need((root/name).read_bytes()==payload,'immutable payload')
    return {'chapter':'v16-c02','status':'passed','worked_cases':2,'solutions':8,'input_groups':len(inputs),'result_groups':len(shown),'comparisons':comparisons,'rejected_inputs':rejected,'runtime_files':4,'qualitative_scope':'Full author reading and narrow source inspection recorded; independent root/peer review pending.'}

if __name__=='__main__':
    check()
