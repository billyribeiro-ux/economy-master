"""Independent C03 reviewer: value iteration and derivative bisection, no author imports."""
from pathlib import Path
from html.parser import HTMLParser
from fractions import Fraction
from hashlib import sha256
import json
import math
import re

FILES=('production/v14-c03-working.html','production/check_v14_c03_working.py','production/v14-c03-sources-working.json','production/v14-c03-author-review-working.json','production/check_v14_c03_peer_working.py','production/v14-c03-peer-review-working.json')

def require(ok,message):
    if not ok: raise ValueError(message)

def num(x):
    require(type(x) in (int,float) and math.isfinite(x),'finite real')
    return float(x)

def prob(xs,n=None):
    require(isinstance(xs,(tuple,list)) and len(xs)>0,'probability sequence')
    require(n is None or len(xs)==n,'probability dimension')
    out=tuple(num(x) for x in xs)
    require(min(out)>=0 and abs(sum(out)-1)<1e-12,'probability mass')
    return out

def advance(mu,Q):
    mu=prob(mu); require(len(Q)==len(mu),'transition size')
    Q=tuple(prob(row,len(mu)) for row in Q)
    return tuple(sum(mu[i]*Q[i][j] for i in range(len(mu))) for j in range(len(mu)))

def root_decreasing(f,lo,hi):
    lo,hi=num(lo),num(hi);require(lo<hi,'bracket order')
    require(f(lo)>=0 and f(hi)<=0,'decreasing root bracket')
    for _ in range(90):
        mid=(lo+hi)/2
        if f(mid)>0:lo=mid
        else:hi=mid
    return (lo+hi)/2

def save(x,ys):
    x=num(x);require(x>0 and isinstance(ys,(tuple,list)) and len(ys)>0,'saving inputs')
    ys=tuple(num(y) for y in ys);require(min(ys)>0,'positive future income')
    d=lambda s:-1/(x-s)+sum(1/(s+y) for y in ys)/len(ys)
    return 0.0 if d(0)<=0 else root_decreasing(d,0,x*(1-1e-12))

def household(assets,income,beta,price=1,ret=1,P=((.5,.5),(.5,.5))):
    require(isinstance(assets,(tuple,list)) and len(assets)>0,'asset vector')
    assets=tuple(num(a) for a in assets);income=tuple(num(y) for y in income)
    beta,price,ret=map(num,(beta,price,ret))
    require(0<beta<1 and price>0 and ret>0 and min(income)>0,'household domain')
    require(all(a<b for a,b in zip(assets,assets[1:])),'ordered distinct assets')
    require(len(P)==len(income),'income matrix')
    P=tuple(prob(p,len(income)) for p in P)
    states=[(a,i) for a in assets for i in range(len(income))]; n=len(states)
    actions=[]
    for a,i in states:
        row=[(j,ret*a+income[i]-price*b) for j,b in enumerate(assets) if ret*a+income[i]-price*b>0]
        require(bool(row),'empty action set'); actions.append(row)
    def rhs(v):
        rows=[]
        for (_,i),row in zip(states,actions):
            rows.append([(j,math.log(c)+beta*sum(p*v[j*len(income)+k] for k,p in enumerate(P[i]))) for j,c in row])
        return rows
    v=[0.0]*n
    for _ in range(20000):
        rows=rhs(v);nv=[max(z for j,z in row) for row in rows]
        if max(abs(x-y) for x,y in zip(nv,v))<2e-14*(1-beta):v=nv;break
        v=nv
    else:raise ValueError('value iteration did not converge')
    rows=rhs(v);g=[max(row,key=lambda x:x[1])[0] for row in rows]
    c=[ret*a+income[i]-price*assets[j] for (a,i),j in zip(states,g)]
    Q=[[P[i][k] if b==j else 0 for b in range(len(assets)) for k in range(len(income))] for (_,i),j in zip(states,g)]
    gaps=[v[s]-z for s,row in enumerate(rows) for j,z in row if j!=g[s]]
    residual=max(abs(v[s]-max(z for j,z in row)) for s,row in enumerate(rows))
    return dict(v=v,g=g,c=c,Q=Q,gaps=gaps,residual=residual,states=states,assets=assets,income=income,beta=beta,price=price,ret=ret)

class Document(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.ids=[];self.ex=[];self.sol=[];self.work=[];self.mark={};self.active=None;self.sources={}
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if 'id' in a:self.ids.append(a['id'])
        if 'worked' in a.get('class','').split():self.work.append(a.get('id'))
        if tag=='li' and re.fullmatch('v14-c03-e[0-9]+',a.get('id','')):self.ex.append(a['id'])
        if 'data-solution-for' in a:self.sol.append(a['data-solution-for'])
        if 'data-source' in a:self.sources[a['data-source']]=a.get('href')
        for key in ('data-input','data-calc'):
            if key in a:
                require(a[key] not in self.mark,'duplicate marker');self.active=a[key];self.mark[self.active]=[key,'']
    def handle_data(self,s):
        if self.active:self.mark[self.active][1]+=s
    def handle_endtag(self,t):
        if t=='span':self.active=None

def literal(s):
    s=s.strip().strip('()[]')
    parts=[p.strip() for p in s.split(',')]
    require(all(re.fullmatch(r'[+-]?\d+(?:\.\d+)?(?:/\d+(?:\.\d+)?)?',p) for p in parts),'numeric literal only')
    vals=[]
    for p in parts:
        vals.append(float(Fraction(p)))
    return vals[0] if len(vals)==1 else tuple(vals)

def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    raw={p:(root/p).read_bytes() for p in FILES};d=Document();d.feed(raw[FILES[0]].decode());d.close()
    require(len(d.ids)==len(set(d.ids)),'unique IDs')
    ex=['v14-c03-e'+str(i) for i in range(1,13)]
    require(d.ex==ex and d.sol==ex,'twelve exact prompt pairs')
    require(d.work==['v14-c03-w'+str(i) for i in range(1,6)],'five cases')
    author=json.loads(raw[FILES[3]]);peer=json.loads(raw[FILES[5]]);src=json.loads(raw[FILES[2]])
    require(set(author['exact_prompt_solution_audit'])==set(ex)==set(peer['exact_prompt_review']),'full prompt records')
    require(d.sources=={s['id']:s['url'] for s in src['sources']},'source coverage')
    for record,expected in ((author,set(FILES[:3])),(peer,set(FILES[:5]))):
        bs=record['payload_bindings'];require(len(bs)==len(expected) and {b['path'] for b in bs}==expected,'binding membership')
        for b in bs:require(len(raw[b['path']])==b['bytes'] and sha256(raw[b['path']]).hexdigest()==b['sha256'],'binding bytes')
    count=0;used=set();reject=0
    def close(a,b):
        nonlocal count
        if isinstance(b,(list,tuple)):
            require(isinstance(a,(list,tuple)) and len(a)==len(b),'numeric shape')
            for x,y in zip(a,b):close(x,y)
        else:require(math.isfinite(a) and abs(a-b)<8e-10*max(1,abs(b)),f'{a} differs from {b}');count+=1
    def claim(key,value):
        require(key in d.mark,'missing '+key);close(literal(d.mark[key][1]),value);used.add(key)
    # Inputs are bound to this independently designed reconstruction, not an author oracle.
    inputs={'risk-cash':4,'risk-income':(1,3),'hug-assets':(-.5,.5),'hug-income':(1,4),'hug-beta':.75,'hug-price':1,'aiy-assets':(0,1),'aiy-efficiency':(.5,1.5),'aiy-beta':.8,'aiy-alpha':.1,'aiy-delta':4/9,'price-endowment':4,'price-beta':.5,'price-grid':(-1,2)}
    for k,v in inputs.items():claim(k,v)
    for x,prefix in ((4,'risk'),(5,'e1')):
        s=save(x,(1,3));claim(prefix+'-saving',s);claim(prefix+'-consumption',(x-s,s+1,s+3))
    claim('risk-certain',save(4,(2,)));claim('risk-threshold',1/(sum(1/y for y in (1,3))/2));claim('risk-multiplier',1-sum(1/y for y in (1,3))/2)
    H=household((-.5,.5),(1,4),.75);A=household((0,1),(1,3),.8);H2=household((-.5,.5),(1,4),2/3);A2=household((0,1),(1,3),.75)
    for econ,prefix in ((H,'hug'),(A,'aiy')):
        claim(prefix+'-consumption',econ['c']);claim(prefix+'-values',econ['v']);claim(prefix+'-gaps',econ['gaps'])
    claim('e4-values',H2['v']);claim('e4-gaps',H2['gaps']);claim('e7-gap',A2['gaps'][0])
    pi=advance(advance((1,0,0,0),H['Q']),H['Q']);claim('hug-distribution',pi)
    def account(e,mu):
        now=sum(m*a for m,(a,i) in zip(mu,e['states']));nxt=sum(m*e['assets'][j] for m,j in zip(mu,e['g']))
        c=sum(m*c for m,c in zip(mu,e['c']));y=sum(m*e['income'][i] for m,(a,i) in zip(mu,e['states']))
        close(c+e['price']*nxt,e['ret']*now+y);return now,nxt,c,y
    hacc=account(H,pi);claim('hug-assets-clear',hacc[0]);claim('hug-goods',hacc[2:])
    k=sum(m*a for m,(a,i) in zip(pi,A['states']));L=sum(m*e for m,e in zip(pi,(.5,1.5,.5,1.5)))
    Y=(20/9)*2**.1*k**.1*L**.9;r=.1*Y/k;w=.9*Y/L;R=1-4/9+r
    claim('aiy-prices',(Y,r,w,R));claim('aiy-aggregates',(k,L,account(A,pi)[2],4*k/9));close(w*L+r*k,Y);close(account(A,pi)[2]+4*k/9,Y)
    for e in (H,A,H2,A2):
        close(e['g'],[0,1,0,1]);close(e['residual']/(1-e['beta']),0)
        require(min(e['gaps'])>0,'strict finite optimum');count+=1
        for mu in ((1,0,0,0),(0,0,1,0),(.1,.2,.3,.4),pi):
            account(e,mu);close(advance(advance(mu,e['Q']),e['Q']),pi)
        # Sum discounted realized rewards directly, with explicit geometric tail bound.
        for state in range(4):
            mu=tuple(int(j==state) for j in range(4));total=0.0
            for t in range(400):
                total+=e['beta']**t*sum(m*math.log(c) for m,c in zip(mu,e['c']));mu=advance(mu,e['Q'])
            close(total,e['v'][state])
    def aggregates(xs):
        saving=[save(a+1,(3,)) for a in xs]
        return sum(xs)/len(xs),sum(saving)/len(xs),sum(a+1-s for a,s in zip(xs,saving))/len(xs)
    claim('aggregation-mean',aggregates((2,))[0]);claim('aggregation-A',aggregates((2,))[1:]);claim('aggregation-B',aggregates((0,4))[1:]);claim('e9-aggregate',aggregates((1,3))[1:])
    advantage=lambda q:math.log(4-2*q)+.5*math.log(6)-math.log(4+q)-.5*math.log(3)
    qt=root_decreasing(advantage,0,1.999);claim('price-tie',qt);claim('price-min-error',min(abs(z) for z in (-1,2)))
    theta=1/3;claim('price-positive-mass',theta);claim('price-goods',((1-theta)*(4+qt)+theta*(4-2*qt),(1-theta)*3+theta*6))
    for q in (.1,.3,.6,1.2,1.9):require((advantage(q)>0)==(q<qt),'monotone grid price');count+=1
    qcont=root_decreasing(lambda q:-q/4+.5/4,.01,1);claim('e10-price',qcont);claim('e10-consumption',(4,4))
    close((1-theta)*(-1)+theta*2,0);require(qt<qcont,'different feasible sets');count+=1
    claim('e2-natural',-.5/(1.1-1));claim('e2-bond',1.1*(-.5/(1.1-1)));claim('e3-multiplier',2-.8*2)
    m1=advance((1,0,0,0),H['Q']);m2=advance(m1,H['Q']);claim('e5-mu1',m1);claim('e5-mu2',m2);claim('e5-date1',account(H,m1))
    md=(.4,.1,.1,.4);dist=sum(abs(x-y) for x,y in zip(md,pi));res=sum(abs(x-y) for x,y in zip(md,advance(md,H['Q'])))
    claim('e8-distance',dist);claim('e8-bound',2*res);close(advance(md,H['Q']),pi)
    claim('e11-iteration',.0002/.1);claim('e11-total',(.0002+.003)/.1);claim('e11-distribution',4*.0001/.2);claim('e11-assets',10/2*4*.0001/.2)
    keep=((.5,.5,0,0),(.5,.5,0,0),(0,0,.5,.5),(0,0,.5,.5));flip=((0,1),(1,0))
    for t in (0,.2,.5,1):
        mu=(t/2,t/2,(1-t)/2,(1-t)/2);close(advance(mu,keep),mu)
    close(advance((1,0),flip),(0,1));close(advance((.5,.5),flip),(.5,.5))
    for cash in (1,1.5,2,4,5,8):
        s=save(cash,(1,3));sc=save(cash,(2,));require(s>=sc-1e-12,'precaution');count+=1
        best=math.log(cash-s)+sum(math.log(s+y) for y in (1,3))/2
        for frac in (.0,.1,.3,.7,.9):
            trial=cash*frac;require(best>=math.log(cash-trial)+sum(math.log(trial+y) for y in (1,3))/2-1e-12,'global saving');count+=1
    # Alternative primitive: below threshold proposed production actions lose optimality.
    B=household((0,1),(1,3),.7);require(B['g']!=[0,1,0,1],'patience threshold');count+=1
    for a in (-1,2):
        for b in (-1,2):close(a+16,a+4-.75*b+.75*(b+16))
    require(used==set(d.mark),'all primitive and computed markers independently checked')
    invalid=[(num,(True,)),(num,(float('nan'),)),(num,('2',)),(prob,([],)),(prob,((.3,.3),)),(prob,((-.1,1.1),)),(prob,((1,0),3)),(advance,((1,0),((1,),))), (root_decreasing,(lambda x:x,0,1)),(root_decreasing,(lambda x:-x,1,0)),(save,(0,(1,3))),(save,(2,(0,1))),(literal,('sum([1])',)),(literal,('1/0',)),(household,((0,1),(1,3),1)),(household,((0,1),(1,3),0)),(household,((1,0),(1,3),.8)),(household,((0,0),(1,3),.8)),(household,((0,1),(1,3),.8,0)),(household,((0,1),(1,3),.8,1,0)),(household,((-10,-9),(.1,.2),.8,1,2)),(household,((0,1),(1,3),.8,1,1,((1,0),(.2,.7))))]
    for fn,args in invalid:
        try:fn(*args)
        except (ValueError,ZeroDivisionError):reject+=1
        else:raise ValueError('accepted invalid '+fn.__name__)
    out=dict(chapter='v14-c03',status='passed',comparisons=count,domain_rejections=reject,worked_cases=5,solved_exercises=12,primitive_markers=14,result_markers=43,runtime_files=6,method='Independent Bellman value iteration, discounted reward sums, derivative bisection, transition propagation and equilibrium accounting; no author execution')
    json.dumps(out,allow_nan=False);return out

if __name__=='__main__':check()
