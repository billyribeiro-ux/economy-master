"""Independent capstone oracle; author checker is hash-bound only."""
from pathlib import Path
from fractions import Fraction as F
from html.parser import HTMLParser
from hashlib import sha256
import ast
import json

FILES = ('production/research-portfolio-working.html', 'production/check_research_portfolio_working.py', 'production/research-portfolio-sources-working.json', 'production/research-portfolio-author-review-working.json', 'production/check_research_portfolio_peer_working.py', 'production/research-portfolio-peer-review-working.json')

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

def discount(principal, payments, gross):
    require(principal>=0 and gross>0 and len(payments)>0 and all(p>=0 for p in payments),'discount domain')
    # Backward cash-flow recursion, independent of the displayed sum.
    value=F(0)
    for payment in reversed(payments):value=(payment+value)/gross
    return value,value-principal

def risk(left, right, lower, upper):
    require(left>0 and right>0 and 0<=lower<=upper<=1,'risk domain')
    kink=left/(left+right)
    candidates=(F(0),kink,F(1))
    def objective(a):return max(p*left*(1-a)+(1-p)*right*a for p in (lower,upper))
    values=tuple(objective(a) for a in candidates);best=min(values)
    optimizers=tuple(a for a,v in zip(candidates,values) if v==best)
    return (min(optimizers),max(optimizers)),best

def demand(table,beta):
    require(beta>=0 and len(table)>0 and all(c>=1 and r==c+1 and q>0 for c,r,q in table),'demand domain')
    intercept=tuple(q+beta*r for c,r,q in table)
    revised=tuple(a-beta*(r-1) for a,(c,r,q) in zip(intercept,table))
    return intercept,revised,tuple(v-row[2] for v,row in zip(revised,table))

def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    record=json.loads((root/FILES[5]).read_text())
    require(set(record['payloads'])==set(FILES[:5]),'peer bindings')
    for path,binding in record['payloads'].items():
        raw=(root/path).read_bytes();require(len(raw)==binding['bytes'] and sha256(raw).hexdigest()==binding['sha256'],'changed '+path)
    r=Reader();r.feed((root/FILES[0]).read_text());m={k:number(v) for k,v in r.markers.items()};count=0
    def equal(a,b,label):
        nonlocal count
        require(a==b,label);count+=1
    equal(len(r.ids),len(set(r.ids)),'unique IDs')
    equal(r.solutions,[f'research-calibration{i}' for i in range(1,4)],'exact three solutions')
    equal(len([x for x in r.ids if x.startswith('research-form-')]),8,'eight operational forms')
    equal(len(r.maps['data-artifact']),5,'five actual-work contracts')
    equal(r.maps['data-prerequisite'],[f'v{i}' for i in range(12,17)],'prerequisites')
    equal(r.maps['data-chapter'],[f'v16-c{i:02d}' for i in range(1,13)],'chapter map')
    source=json.loads((root/FILES[2]).read_text())['sources']
    equal(r.sources,{s['id']:s['url'] for s in source},'source URLs and attribution scope')
    equal(sum(m['defense-minutes']),m['defense-total'],'session sum')
    pv,npv=discount(m['loan-principal'],m['loan-payments'],m['loan-gross'])
    equal(pv,m['loan-pv'],'PV');equal(npv,m['loan-npv'],'NPV')
    equal(tuple(a-b for a,b in zip((pv,npv),m['loan-saved'])),m['loan-discrepancy'],'stale output difference')
    intercepts=[];counter=[];gains=[]
    for beta in m['demand-betas']:
        a,q,g=demand(m['market-table'],beta);intercepts.append(a);counter.append(q);equal(g,(beta,)*3,'constant intervention response');gains.append(g[0])
    equal(tuple(intercepts),m['demand-intercepts'],'latent intercepts');equal(tuple(counter),m['demand-counterfactuals'],'policy quantities');equal(tuple(gains),m['demand-gains'],'policy gains')
    for beta in (F(0),F(1,100),F(100)):
        a,q,g=demand(m['market-table'],beta)
        for state,(c,rate,quantity) in enumerate(m['market-table']):
            equal(a[state]-beta*rate,quantity,'observational equivalence');equal(g[state],beta,'alternative policy response')
    A,B=m['risk-losses']
    for key in ('initial','low','high'):
        span,value=risk(A,B,*m['risk-'+key]);equal(span[0],span[1],'unique supplied interval');equal((span[0],value),m['risk-'+key+'-result'],'risk '+key)
    tie=m['risk-tie'];span,value=risk(A,B,tie,tie);equal(span,(0,1),'full tie set');equal(value,m['risk-tie-value'],'tie value')
    equal(tuple(risk(A,B,*interval)[0] for interval in m['risk-boundary-inputs']),m['risk-boundary-sets'],'boundary minimizer intervals')
    worlds=0
    # Direct upper-envelope evaluation over dense rational allocations, including
    # equality regimes and changed coefficients. Analytic global proof read separately.
    for A,B in ((F(2),F(3)),(F(1),F(1)),(F(5),F(2))):
        threshold=B/(A+B);points=sorted({F(0),threshold/2,threshold,(1+threshold)/2,F(1)})
        for lower in points:
            for upper in points:
                if upper<lower:continue
                span,best=risk(A,B,lower,upper);worlds+=1
                allocations=sorted({F(i,20) for i in range(21)}|{span[0],span[1],A/(A+B),(span[0]+span[1])/2})
                for a in allocations:
                    value=max(p*A*(1-a)+(1-p)*B*a for p in (lower,upper))
                    equal(value==best,span[0]<=a<=span[1],'complete minimizer interval');require(value>=best,'global lower bound')
    invalid=[lambda:discount(-1,(F(1),),F(1)),lambda:discount(1,(),F(1)),lambda:discount(1,(F(-1),),F(1)),lambda:discount(1,(F(1),),F(0)),lambda:risk(F(0),F(1),F(0),F(1)),lambda:risk(F(1),F(-1),F(0),F(1)),lambda:risk(F(1),F(1),F(-1),F(1)),lambda:risk(F(1),F(1),F(0),F(2)),lambda:risk(F(1),F(1),F(1),F(0)),lambda:demand(m['market-table'],F(-1)),lambda:demand((),F(1))]
    for f in invalid:
        try:f()
        except ValueError:pass
        else:raise ValueError('invalid domain accepted')
    return {'assessment':'research-portfolio','review':'independent-peer','status':'passed','runtime_files':6,'numeric_markers':len(m),'comparisons':count,'robust_worlds':worlds,'invalid_domains':len(invalid),'scope':'Full forms, three cases/solutions/global proofs and staged judgments read separately; author checker never executed; no actual learner or human certification.'}

if __name__=='__main__':check()
