"""Quiet finite-economy audit; four runtime files; no writes or network."""
import ast
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from itertools import product
import json
from math import isfinite, log, sqrt
from pathlib import Path

FILES=('production/v14-c03-working.html','production/check_v14_c03_working.py',
       'production/v14-c03-sources-working.json','production/v14-c03-author-review-working.json')


def need(ok,msg):
    if not ok:raise ValueError(msg)


def scalar(x):
    need(not isinstance(x,bool) and isinstance(x,(int,float,F)),'numeric scalar required')
    need(isfinite(float(x)),'finite scalar required')
    return float(x)


def vector(xs,n=None):
    need(isinstance(xs,(list,tuple)) and bool(xs),'nonempty vector required')
    need(n is None or len(xs)==n,'vector dimension')
    return tuple(scalar(x) for x in xs)


def stochastic(q):
    need(isinstance(q,(tuple,list)) and bool(q),'nonempty stochastic matrix')
    n=len(q); out=tuple(vector(row,n) for row in q)
    need(all(min(row)>=0 and abs(sum(row)-1)<1e-12 for row in out),'stochastic rows')
    return out


def matmul(a,b):
    need(bool(a) and bool(b) and all(len(row)==len(b) for row in a),'matrix dimensions')
    need(all(len(row)==len(b[0]) for row in b),'ragged right matrix')
    return tuple(tuple(sum(a[i][k]*b[k][j] for k in range(len(b))) for j in range(len(b[0]))) for i in range(len(a)))


def law(mu,q):
    q=stochastic(q);mu=vector(mu,len(q));need(min(mu)>=0 and abs(sum(mu)-1)<1e-12,'unit probability mass')
    return matmul((mu,),q)[0]


def linear(a,b):
    n=len(b);need(n>0 and len(a)==n,'linear dimension')
    m=[list(vector(row,n))+[scalar(rhs)] for row,rhs in zip(a,b)]
    for j in range(n):
        pivot=max(range(j,n),key=lambda i:abs(m[i][j]));need(abs(m[pivot][j])>1e-13,'singular linear system')
        m[j],m[pivot]=m[pivot],m[j];d=m[j][j];m[j]=[x/d for x in m[j]]
        for i in range(n):
            if i!=j:
                d=m[i][j];m[i]=[x-d*y for x,y in zip(m[i],m[j])]
    return tuple(row[-1] for row in m)


def economy(assets,income,beta,q=1,R=1,P=((.5,.5),(.5,.5))):
    assets=vector(assets);income=vector(income);beta,q,R=map(scalar,(beta,q,R));P=stochastic(P)
    need(0<beta<1 and q>0 and R>0 and min(income)>0,'economic parameter domain')
    need(tuple(sorted(set(assets)))==assets,'strictly increasing asset grid')
    need(len(income)==len(P),'income transition dimension')
    states=tuple(product(range(len(assets)),range(len(income))))
    choices=[];cons=[]
    for ia,ie in states:
        row=tuple(R*assets[ia]+income[ie]-q*b for b in assets)
        feasible=tuple(j for j,c in enumerate(row) if c>0)
        need(bool(feasible),'empty feasible action set');choices.append(feasible);cons.append(row)
    return dict(assets=assets,income=income,beta=beta,q=q,R=R,P=P,states=states,choices=tuple(choices),cons=tuple(cons))


def evaluate(t,g):
    n=len(t['states']);need(isinstance(g,(tuple,list)) and len(g)==n,'policy shape')
    need(all(not isinstance(j,bool) and isinstance(j,int) and j in t['choices'][i] for i,j in enumerate(g)),'infeasible policy')
    ne=len(t['income']);Q=[];c=[]
    for s,((ia,ie),j) in enumerate(zip(t['states'],g)):
        Q.append(tuple(t['P'][ie][je] if ja==j else 0.0 for ja,je in t['states']));c.append(t['cons'][s][j])
    Q=stochastic(Q);r=tuple(log(x) for x in c)
    v=linear(tuple(tuple((1 if i==j else 0)-t['beta']*Q[i][j] for j in range(n)) for i in range(n)),r)
    gaps=[]
    for i,(ia,ie) in enumerate(t['states']):
        row=[]
        for j in t['choices'][i]:
            alt=log(t['cons'][i][j])+t['beta']*sum(t['P'][ie][je]*v[j*ne+je] for je in range(ne))
            row.append((j,v[i]-alt))
        gaps.append(tuple(row))
    return dict(policy=tuple(g),Q=Q,c=tuple(c),v=v,gaps=tuple(gaps))


def solve(t):
    candidates=[]
    for g in product(*t['choices']):
        e=evaluate(t,g)
        if all(gap>=-1e-11 for row in e['gaps'] for j,gap in row):candidates.append(e)
    need(len(candidates)==1,'unique optimal deterministic policy needed by this benchmark')
    return candidates[0]


def risky(x):
    x=scalar(x);need(x>0,'positive cash')
    certain=max(0,(x-2)/2)
    s=max(0,(x-6+sqrt((6-x)**2-8*(3-2*x)))/4)
    need(0<=s<x,'risk saving feasibility')
    return certain,s,(x-s,s+1,s+3)


def debt(y,R):
    y,R=map(scalar,(y,R));need(y>0 and R>1,'positive income and return exceeding one for perpetuity')
    return -y/(R-1)


def production(K,L,alpha,delta,Z):
    K,L,a,d,Z=map(scalar,(K,L,alpha,delta,Z))
    need(K>0 and L>0 and 0<a<1 and 0<d<=1 and Z>0,'production domain')
    y=Z*K**a*L**(1-a);r=a*y/K;w=(1-a)*y/L
    return y,r,w,1-d+r


def aggregate(assets,mass):
    assets=vector(assets);mass=vector(mass,len(assets));need(min(mass)>=0 and abs(sum(mass)-1)<1e-12,'aggregation masses')
    saving=tuple(max((a-2)/2,0) for a in assets)
    need(min(assets)>=0,'aggregation case asset domain')
    A=sum(a*m for a,m in zip(assets,mass));S=sum(s*m for s,m in zip(saving,mass))
    return A,S,A+1-S


def grid_price(q,beta=.5,y=4):
    q,beta,y=map(scalar,(q,beta,y));need(0<q<y/2 and 0<beta<1 and y>1,'two-date bond domain')
    lo=log(y+q)+beta*log(y-1);hi=log(y-2*q)+beta*log(y+2)
    return lo,hi


def parsed(s):
    def node(n):
        if isinstance(n,ast.Constant):return scalar(n.value)
        if isinstance(n,(ast.Tuple,ast.List)):return tuple(node(v) for v in n.elts)
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,(ast.UAdd,ast.USub)):return node(n.operand)*(-1 if isinstance(n.op,ast.USub) else 1)
        if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Div):
            d=node(n.right);need(d!=0,'zero denominator');return node(n.left)/d
        raise ValueError('nonliteral numerical marker')
    return node(ast.parse(s.strip(),mode='eval').body)


class HTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.stack=[];self.ids=[];self.worked=[];self.ex=[];self.sol=[];self.sources={};self.mark={};self.pending=[];self.links=[]
    def handle_starttag(self,t,attrs):
        d=dict(attrs);cs=d.get('class','').split()
        if 'id' in d:need(d['id'] not in self.ids,'duplicate ID');self.ids.append(d['id'])
        if 'worked' in cs:self.worked.append(d.get('id'))
        if t=='li' and d.get('id','').startswith('v14-c03-e'):self.ex.append(d['id'])
        if 'data-solution-for' in d:
            need(any(k=='details' and 'solutions' in v.get('class','').split() for k,v in self.stack),'solution disclosure missing');self.sol.append(d['data-solution-for'])
        if 'data-source' in d:self.sources[d['data-source']]=d.get('href')
        if t=='a':self.links.append(d.get('href',''))
        for k in ('data-input','data-calc'):
            if k in d:
                need(d[k] not in self.mark,'duplicate numeric marker');self.mark[d[k]]=[k,''];self.pending.append((d[k],len(self.stack)))
        if t not in ('br','hr','img','link','meta','input'):self.stack.append((t,d))
    def handle_endtag(self,t):
        need(bool(self.stack) and self.stack[-1][0]==t,'unbalanced HTML');self.stack.pop();self.pending=[(k,n) for k,n in self.pending if n<len(self.stack)]
    def handle_data(self,d):
        for k,n in self.pending:self.mark[k][1]+=d


def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    payload={p:(root/p).read_bytes() for p in FILES}
    doc=HTML();doc.feed(payload[FILES[0]].decode());doc.close();need(not doc.stack,'unclosed HTML')
    need(all(i.startswith('v14-c03-') for i in doc.ids),'ID prefix')
    need(doc.worked==['v14-c03-w'+str(i) for i in range(1,6)],'worked count')
    ex=['v14-c03-e'+str(i) for i in range(1,13)];need(doc.ex==ex and doc.sol==ex,'prompt solution pairing')
    need(all(h.startswith(('https://','v','curriculum.html#','#')) for h in doc.links),'flat source/chapter links')
    src=json.loads(payload[FILES[2]]);review=json.loads(payload[FILES[3]])
    need(doc.sources=={s['id']:s['url'] for s in src['sources']},'source links')
    need(set(review['exact_prompt_solution_audit'])==set(ex),'review coverage')
    bindings=review['payload_bindings'];need(len(bindings)==3 and {b['path'] for b in bindings}==set(FILES[:3]),'three nonself bindings')
    for b in bindings:need(len(payload[b['path']])==b['bytes'] and sha256(payload[b['path']]).hexdigest()==b['sha256'],'payload binding')
    inp={k:parsed(v[1]) for k,v in doc.mark.items() if v[0]=='data-input'}
    vals={k:parsed(v[1]) for k,v in doc.mark.items() if v[0]=='data-calc'}
    primitives={'risk-cash':4,'risk-income':(1,3),'hug-assets':(-.5,.5),'hug-income':(1,4),'hug-beta':.75,'hug-price':1,
     'aiy-assets':(0,1),'aiy-efficiency':(.5,1.5),'aiy-beta':.8,'aiy-alpha':.1,'aiy-delta':4/9,
     'price-endowment':4,'price-beta':.5,'price-grid':(-1,2)}
    comparisons=0;rejections=0
    def near(x,y,tol=6e-11):
        nonlocal comparisons
        if isinstance(y,(tuple,list)):
            need(isinstance(x,(tuple,list)) and len(x)==len(y),'comparison dimensions')
            for a,b in zip(x,y):near(a,b,tol)
        else:
            need(isfinite(float(x)) and abs(float(x)-float(y))<=tol*max(1,abs(float(y))),f'{x} != {y}');comparisons+=1
    need(set(inp)==set(primitives),'primitive coverage')
    for k,v in primitives.items():near(inp[k],v)
    H=economy(inp['hug-assets'],inp['hug-income'],inp['hug-beta'],inp['hug-price']);hs=solve(H)
    K=.5;L=1;Z=(20/9)*2**inp['aiy-alpha'];pr=production(K,L,inp['aiy-alpha'],inp['aiy-delta'],Z)
    A=economy(inp['aiy-assets'],tuple(pr[2]*e for e in inp['aiy-efficiency']),inp['aiy-beta'],R=pr[3]);as_=solve(A)
    changed=economy(inp['hug-assets'],inp['hug-income'],2/3);cs=solve(changed)
    def alternatives(t,e):return tuple(gap for i,row in enumerate(e['gaps']) for j,gap in row if j!=e['policy'][i])
    risk=risky(inp['risk-cash']);r5=risky(5);qstar=4*(sqrt(2)-1)/(1+2*sqrt(2));mu=(.25,)*4
    Q=hs['Q'];m1=law((1,0,0,0),Q);m2=law(m1,Q)
    changedA=economy((0,1),(1,3),.75);ca=solve(changedA)
    results={
     'risk-certain':risk[0],'risk-saving':risk[1],'risk-consumption':risk[2],'risk-threshold':1/(.5/1+.5/3),'risk-multiplier':1-(.5/1+.5/3),
     'hug-consumption':hs['c'],'hug-values':hs['v'],'hug-gaps':alternatives(H,hs),'hug-distribution':mu,
     'hug-assets-clear':sum(H['assets'][ia]*m for (ia,ie),m in zip(H['states'],mu)),
     'hug-goods':(sum(c*m for c,m in zip(hs['c'],mu)),sum(H['income'][ie]*m for (ia,ie),m in zip(H['states'],mu))),
     'aiy-prices':pr,'aiy-consumption':as_['c'],'aiy-gaps':alternatives(A,as_),'aiy-values':as_['v'],
     'aiy-aggregates':(K,L,sum(c*m for c,m in zip(as_['c'],mu)),inp['aiy-delta']*K),
     'aggregation-mean':aggregate((2,),(1,))[0],'aggregation-A':aggregate((2,),(1,))[1:],
     'aggregation-B':aggregate((0,4),(.5,.5))[1:],'price-tie':qstar,'price-min-error':min(abs(x) for x in inp['price-grid']),
     'price-positive-mass':-inp['price-grid'][0]/(inp['price-grid'][1]-inp['price-grid'][0]),'price-goods':(4,4),
     'e1-saving':r5[1],'e1-consumption':r5[2],'e2-natural':debt(.5,1.1),'e2-bond':1.1*debt(.5,1.1),
     'e3-multiplier':(1-.8)*2,'e4-values':cs['v'],'e4-gaps':alternatives(changed,cs),'e5-mu1':m1,'e5-mu2':m2,
     'e5-date1':(sum(H['assets'][ia]*m for (ia,ie),m in zip(H['states'],m1)),sum(H['assets'][j]*m for j,m in zip(hs['policy'],m1)),sum(c*m for c,m in zip(hs['c'],m1)),sum(H['income'][ie]*m for (ia,ie),m in zip(H['states'],m1))),
     'e7-gap':alternatives(changedA,ca)[0],'e8-distance':sum(abs(x-.25) for x in (.4,.1,.1,.4)),
     'e8-bound':2*sum(abs(x-y) for x,y in zip(law((.4,.1,.1,.4),Q),(.4,.1,.1,.4))),
     'e9-aggregate':aggregate((1,3),(.5,.5))[1:],'e10-price':inp['price-beta'],'e10-consumption':(4,4),
     'e11-iteration':.0002/(1-.9),'e11-total':(.0002+.003)/(1-.9),'e11-distribution':4*.0001/.2,'e11-assets':(8-(-2))/2*4*.0001/.2}
    need(set(vals)==set(results),'displayed result coverage')
    for k,v in results.items():
        try:near(vals[k],v)
        except ValueError as e:raise ValueError(k+': '+str(e)) from e
    # Household certificates from every feasible action, not just a displayed selected policy.
    for t,s in ((H,hs),(A,as_),(changed,cs),(changedA,ca)):
        near(s['policy'],(0,1,0,1))
        for row in s['gaps']:
            for j,gap in row:need(gap>=-1e-12,'profitable finite deviation');comparisons+=1
        for i,row in enumerate(s['Q']):near(s['v'][i],log(s['c'][i])+t['beta']*sum(p*v for p,v in zip(row,s['v'])),1e-12)
        near(law(mu,s['Q']),mu,1e-12)
        near(matmul(s['Q'],s['Q']),(mu,)*4,1e-12)
        # Aggregate current plus next asset expenditures obey the aggregated household budgets.
        for mass in (mu,(1,0,0,0),(.1,.2,.3,.4)):
            c=sum(m*x for m,x in zip(mass,s['c']));now=sum(m*t['assets'][ia] for m,(ia,ie) in zip(mass,t['states']))
            nxt=sum(m*t['assets'][j] for m,j in zip(mass,s['policy']));inc=sum(m*t['income'][ie] for m,(ia,ie) in zip(mass,t['states']))
            near(c+t['q']*nxt,t['R']*now+inc,1e-12)
    near(pr[1]*K+pr[2]*L,pr[0],1e-12);near(results['aiy-aggregates'][2]+inp['aiy-delta']*K,pr[0],1e-12)
    # Below the exact patience threshold the proposed production policy has a profitable deviation.
    less=economy((0,1),(1,3),.7);bad=evaluate(less,(0,1,0,1))
    need(alternatives(less,bad)[0]<0,'patience perturbation did not invalidate policy');comparisons+=1
    # Independent state-distribution tests, mixing failure and residual bound.
    identitywealth=((.5,.5,0,0),(.5,.5,0,0),(0,0,.5,.5),(0,0,.5,.5))
    for weight in (0,.3,1):
        mass=(weight/2,weight/2,(1-weight)/2,(1-weight)/2);near(law(mass,identitywealth),mass,1e-12)
    near(law((1,0),((0,1),(1,0))),(0,1));near(law((0,1),((0,1),(1,0))),(1,0))
    near(law((.5,.5),((0,1),(1,0))),(.5,.5))
    for mass in ((.4,.1,.1,.4),(1,0,0,0),(.1,.2,.3,.4)):
        distance=sum(abs(x-.25) for x in mass);residual=sum(abs(x-y) for x,y in zip(law(mass,Q),mass))
        need(distance<=2*residual+1e-12,'distribution certificate');comparisons+=1
    # Precautionary mechanism plus boundary signs and first-order/global concavity checks.
    for cash in (1,1.5,2,4,5):
        certain,s,cc=risky(cash);der=-1/(cash-s)+.5/(s+1)+.5/(s+3)
        if s>0:near(der,0,1e-12)
        else:need(der<=1e-12,'borrowing-bound derivative');comparisons+=1
        need(s>=certain-1e-12,'precautionary monotonicity');comparisons+=1
        value=log(cc[0])+.5*log(cc[1])+.5*log(cc[2])
        for trial in (0,.25*cash,.75*cash):
            alt=log(cash-trial)+.5*log(trial+1)+.5*log(trial+3)
            need(alt<=value+1e-12,'global two-date comparison');comparisons+=1
    # Genuine grid clearing failure and explicitly implementable indifferent allocation.
    near(*grid_price(qstar),tol=1e-12)
    for q in (.1,.3,.6,1,1.9):
        lo,hi=grid_price(q);need((hi>lo)==(q<qstar),'bond price sign');comparisons+=1
    mass=results['price-positive-mass'];near((1-mass)*(-1)+mass*2,0,1e-12)
    near((1-mass)*(4+qstar)+mass*(4-2*qstar),4,1e-12)
    near((1-mass)*3+mass*6,4,1e-12)
    near(-.5/4+.5/4,0)
    # Infinite-horizon linear-utility selection example and alternate stationary equilibrium.
    beta=.75;C=4/(1-beta)
    for asset in (-1,2):
        for nxt in (-1,2):near(asset+C,asset+4-beta*nxt+beta*(nxt+C),1e-12)
    near((-1)*(2/3)+2*(1/3),0)
    # Invalid-domain behavior must survive optimized execution.
    invalid=[(economy,((0,1),(1,3),0)),(economy,((0,1),(1,3),1)),(economy,((0,1),(1,3),.8,0)),
      (economy,((0,1),(1,3),.8,1,0)),(economy,((1,0),(1,3),.8)),(economy,((0,0),(1,3),.8)),
      (economy,((0,1),(0,3),.8)),(economy,((-10,-9),(.1,.2),.8,1,2)),(economy,((0,1),(1,),.8)),
      (evaluate,(H,(1,1,0,1))),(evaluate,(H,(0,1))),(evaluate,(H,(False,1,0,1))),
      (stochastic,(((.5,.4),(.5,.5)),)),(stochastic,(((1.1,-.1),(.5,.5)),)),(stochastic,(((1,),(.5,.5)),)),
      (law,((1,1),((.5,.5),(.5,.5)))),(law,((-.1,1.1),((.5,.5),(.5,.5)))),
      (linear,(((1,1),(2,2)),(1,2))),(risky,(0,)),(risky,(-1,)),(debt,(.5,1)),(debt,(.5,.9)),(debt,(0,1.1)),
      (production,(0,1,.1,.4,2)),(production,(1,0,.1,.4,2)),(production,(1,1,1,.4,2)),(production,(1,1,.1,1.1,2)),
      (aggregate,((1,2),(.5,.4))),(aggregate,((-1,2),(.5,.5))),(grid_price,(0,)),(grid_price,(2,)),
      (scalar,(True,)),(scalar,(float('nan'),)),(scalar,('1',)),(parsed,('1/0',)),(parsed,('sum([1])',))]
    for fn,args in invalid:
        try:fn(*args)
        except (ValueError,OverflowError):rejections+=1
        else:raise ValueError('invalid domain accepted: '+fn.__name__)
    out={'chapter':'v14-c03','status':'passed','comparisons':comparisons,'domain_rejections':rejections,
         'worked_cases':5,'solved_exercises':12,'primitive_markers':len(inp),'result_markers':len(vals),'runtime_files':4,
         'scope':'Finite household global certificates, joint distributions, exact exchange/production accounts, precautionary and price-selection counterexamples; no continuous-economy or historical replication claim.'}
    json.dumps(out,allow_nan=False);return out


if __name__=='__main__':check()
