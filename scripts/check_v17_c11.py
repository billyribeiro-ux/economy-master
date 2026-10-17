"""V17C11 author verification; full qualitative review recorded separately."""
from pathlib import Path
from fractions import Fraction as F
from html.parser import HTMLParser
from hashlib import sha256
import ast
import json

FILES = ('content/chapters/v17-c11.html','scripts/check_v17_c11.py','content/reviews/v17-c11-sources.json','content/reviews/v17-c11-author.json')

def require(ok, message):
    if not ok:
        raise ValueError(message)

def number(text):
    def walk(n):
        if isinstance(n, ast.Constant) and type(n.value) is int: return F(n.value)
        if isinstance(n, (ast.Tuple, ast.List)): return tuple(walk(x) for x in n.elts)
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.USub): return -walk(n.operand)
        if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Div): return walk(n.left)/walk(n.right)
        raise ValueError('numeric grammar')
    return walk(ast.parse(text, mode='eval').body)

class Reader(HTMLParser):
    def __init__(self):
        super().__init__(); self.markers={}; self.active=None; self.ids=[]; self.solutions=[]; self.sources={}; self.maps={k:[] for k in ('data-artifact','data-prerequisite','data-chapter')}
    def handle_starttag(self, tag, attrs):
        d=dict(attrs)
        if 'id' in d:self.ids.append(d['id'])
        if 'data-solution-for' in d:self.solutions.append(d['data-solution-for'])
        if 'data-source' in d:self.sources[d['data-source']]=d['href']
        for k in self.maps:
            if k in d:self.maps[k].append(d[k])
        for kind in ('data-input','data-result'):
            if kind in d:
                require(d[kind] not in self.markers,'duplicate numeric marker');self.active=d[kind];self.markers[self.active]=''
    def handle_data(self, data):
        if self.active:self.markers[self.active]+=data
    def handle_endtag(self, tag):
        if tag=='span':self.active=None

def demand(a,b,p):
    require(a>0 and b>0 and p>0 and a-b*p>0,'positive demand domain')
    q=a-b*p
    return q,-b,-b*p/q

def moments(x,y,w):
    require(len(x)==len(y) and len(x)>0 and 0<=w<=1,'return domain')
    n=len(x);mx=sum(x)/n;my=sum(y)/n
    vx=sum((v-mx)**2 for v in x)/n;vy=sum((v-my)**2 for v in y)/n;cov=sum((a-mx)*(b-my) for a,b in zip(x,y))/n
    port=tuple(w*a+(1-w)*b for a,b in zip(x,y));mean=sum(port)/n;variance=sum((a-mean)**2 for a in port)/n
    require(variance==w*w*vx+(1-w)**2*vy+2*w*(1-w)*cov,'variance identity')
    return (vx,vy,cov),port,mean,variance

def proportion_bound(known_pass,observed,total):
    require(0<=known_pass<=observed<=total and total>0,'roster domain')
    return F(known_pass,total),F(known_pass+total-observed,total)

def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    record=json.loads((root/FILES[3]).read_text());require(set(record['payloads'])==set(FILES[:3]),'payload inventory')
    for f,v in record['payloads'].items():
        raw=(root/f).read_bytes();require(len(raw)==v['bytes'] and sha256(raw).hexdigest()==v['sha256'],'changed '+f)
    r=Reader();r.feed((root/FILES[0]).read_text());m={k:number(v) for k,v in r.markers.items()};count=0
    def eq(a,b,label):
        nonlocal count
        require(a==b,label);count+=1
    eq(len(r.ids),len(set(r.ids)),'unique IDs');eq(r.solutions,[f'v17-c11-e{i}' for i in range(1,9)],'eight paired solutions');eq(r.sources,{s['id']:s['url'] for s in json.loads((root/FILES[2]).read_text())['sources']},'source URLs')
    a,b,p=m['demand'];eq(demand(a,b,p),m['demand-result'],'initial demand');eq((demand(a,b,p),demand(a,b,F(4))),m['e2-comparison'],'point comparison');eq(demand(F(120),F(20),F(2)),m['fresh-elasticity'],'changed curve');eq((demand(F(90),F(15),F(2)),demand(F(90),F(15),F(3))),m['e4-demand'],'new task')
    eq(m['initial-counts'],(2,1,1),'four actual response judgments');bound=proportion_bound(2,3,4);eq(bound,m['followup-range'],'roster performance');eq(tuple(x-F(1,4) for x in bound),m['e3-change'],'descriptive change')
    x,y=m['returns'];mom,port,mean,var=moments(x,y,F(1,2));eq(mom,m['moments'],'moments');eq(port,m['portfolio-returns'],'state returns');eq(mean,F(0),'zero portfolio mean');eq(var,m['portfolio-variance'],'portfolio variance')
    positive=tuple(2*v for v in x);negative=tuple(-2*v for v in x);eq(tuple(moments(x,yy,F(1,2))[3] for yy in (positive,negative)),m['covariance-boundaries'],'perfect comovement')
    zero=moments(x,negative,F(2,3));eq((F(2,3),F(1,3),zero[3],zero[2]),m['zero-risk'],'zero risk/zero return')
    mm,pp,mu,vv=moments(x,y,F(3,4));eq(pp,m['e6-returns'],'changed weights');opt=F(4,5);minimum=moments(x,y,opt)[3];eq((vv,opt,minimum),m['e6-risk'],'minimum variance')
    for i in range(21):
        w=F(i,20);var=moments(x,y,w)[3];eq(var-minimum,20*(w-opt)**2,'global square proof');eq(moments(x,negative,w)[3],4*(3*w-2)**2,'negative comovement global')
        price=F(i+1,3);q,slope,e=demand(a,b,price);eq(q*(1+e),a-2*b*price,'revenue derivative identity')
    eq(m['e7-plan'][:2],(29,4),'time excess');eq(sum(m['e7-plan'][2:]),25,'feasible revision time')
    for n in (1,4,9):
        for observed in range(n+1):
            for passed in range(observed+1):
                lower,upper=proportion_bound(passed,observed,n);eq(lower,F(passed,n),'all missing fail');eq(upper,F(passed+n-observed,n),'all missing pass')
    bad=[lambda:demand(0,1,1),lambda:demand(100,0,2),lambda:demand(100,10,0),lambda:demand(100,10,10),lambda:demand(100,10,11),lambda:moments((),(),F(1,2)),lambda:moments(x,y[:-1],F(1,2)),lambda:moments(x,y,F(-1)),lambda:moments(x,y,F(2)),lambda:proportion_bound(0,0,0),lambda:proportion_bound(3,2,4),lambda:proportion_bound(1,5,4)]
    for f in bad:
        try:f()
        except ValueError:pass
        else:raise ValueError('invalid domain accepted')
    return {'chapter':'v17-c11','status':'passed','runtime_files':4,'worked_dossiers':2,'exact_solutions':8,'numeric_markers':len(m),'comparisons':count,'invalid_domains':len(bad),'scope':'Full observation/response/rubric/feedback/revision evidence and global proofs read separately; no actual observation or causal teaching effect certified.'}

if __name__=='__main__':check()
