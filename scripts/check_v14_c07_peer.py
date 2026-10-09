"""Independent C07 audit. No author checker imports/execution; six runtime files."""
import ast
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
import json
from math import exp, isfinite, log, sqrt
from pathlib import Path

AUTHOR=('content/chapters/v14-c07.html','scripts/check_v14_c07.py',
        'content/reviews/v14-c07-sources.json','content/reviews/v14-c07-author.json')
FILES=AUTHOR+('scripts/check_v14_c07_peer.py','content/reviews/v14-c07-peer.json')


def need(test,msg):
    if not test:raise ValueError(msg)


def num(x):
    need(not isinstance(x,bool) and isinstance(x,(int,float,F)),'real numeric scalar required')
    need(isfinite(float(x)),'finite scalar required');return float(x)


def seq(x,n=None):
    need(isinstance(x,(tuple,list)) and bool(x),'nonempty sequence required')
    need(n is None or len(x)==n,'sequence length');return tuple(num(y) for y in x)


def probabilities(p):
    p=seq(p);need(min(p)>0 and abs(sum(p)-1)<1e-12,'strictly positive probability vector');return p


def mean(x,p):return sum(a*b for a,b in zip(x,p))


def pricing(m,p,x):
    m=seq(m);p=probabilities(p);x=seq(x,len(m));need(len(p)==len(m) and min(m)>0,'positive SDF and dimensions')
    price=mean(tuple(a*b for a,b in zip(m,x)),p);need(price>0,'positive security price')
    em=mean(m,p);returns=tuple(v/price for v in x);er=mean(returns,p)
    vm=mean(tuple((a-em)**2 for a in m),p);vr=mean(tuple((a-er)**2 for a in returns),p)
    cov=mean(tuple((a-em)*(b-er) for a,b in zip(m,returns)),p)
    return dict(price=price,em=em,rf=1/em,er=er,returns=returns,sdr=sqrt(vr),cv=sqrt(vm)/em,cov=cov,premium=er-1/em)


def sharpe(stats):
    need(stats['sdr']>0,'nonconstant return for Sharpe ratio')
    return stats['premium']/stats['sdr']


def crra(beta,gamma,c0,c):
    beta,gamma,c0=map(num,(beta,gamma,c0));c=seq(c)
    need(0<beta<1 and gamma>0 and c0>0 and min(c)>0,'CRRA domain')
    return tuple(beta*(v/c0)**(-gamma) for v in c)


def lognormal(beta,mu,sigma,cv):
    beta,mu,sigma,cv=map(num,(beta,mu,sigma,cv))
    need(0<beta<1 and sigma>0 and cv>0,'lognormal diagnostic domain')
    gamma=sqrt(log(1+cv*cv))/sigma
    em=beta*exp(-gamma*mu+.5*gamma*gamma*sigma*sigma)
    return gamma,-log(em),1/em


def solve2(A,b):
    need(len(A)==2 and all(len(row)==2 for row in A) and len(b)==2,'two by two system')
    det=A[0][0]*A[1][1]-A[0][1]*A[1][0];need(det!=0,'singular matrix')
    return ((b[0]*A[1][1]-A[0][1]*b[1])/det,(A[0][0]*b[1]-b[0]*A[1][0])/det)


def tree(beta,gamma,P,g):
    beta=F(beta);gamma=num(gamma);g=tuple(F(x) for x in g)
    need(0<beta<1 and gamma>0 and len(g)==2 and min(g)>0,'tree primitives')
    need(len(P)==2 and all(len(row)==2 for row in P),'tree dimensions')
    P=tuple(tuple(F(x) for x in row) for row in P)
    need(all(min(row)>=0 and sum(row)==1 for row in P),'stochastic tree transition')
    power=1-gamma
    if power==int(power):A=tuple(tuple(beta*p*g[j]**int(power) for j,p in enumerate(row)) for row in P)
    else:A=tuple(tuple(float(beta*p)*float(g[j])**power for j,p in enumerate(row)) for row in P)
    row=max(sum(row) for row in A);need(row<1,'row-norm certificate premise')
    B=((1-A[0][0],-A[0][1]),(-A[1][0],1-A[1][1]));v=solve2(B,tuple(map(sum,A)))
    return A,row,v


def external(beta,gamma,c0,H0,c,H):
    beta,gamma,c0,H0=map(num,(beta,gamma,c0,H0));c=seq(c);H=seq(H,len(c))
    need(0<beta<1 and gamma>0 and c0>H0 and c0>0 and min(c)>0 and all(x>h for x,h in zip(c,H)),'positive habit surplus')
    m=tuple(beta*((x-h)/(c0-H0))**(-gamma) for x,h in zip(c,H))
    return m,gamma*c0/(c0-H0)


class Jet:
    """Five-variable second-order forward derivatives through primitive arithmetic."""
    def __init__(self,v,g=None,h=None):
        self.v=float(v);self.g=tuple(g) if g is not None else (0.0,)*5
        self.h=tuple(tuple(row) for row in h) if h is not None else ((0.0,)*5,)*5
    def __add__(self,other):
        if not isinstance(other,Jet):other=Jet(other)
        return Jet(self.v+other.v,tuple(a+b for a,b in zip(self.g,other.g)),tuple(tuple(a+b for a,b in zip(r,s)) for r,s in zip(self.h,other.h)))
    __radd__=__add__
    def __mul__(self,k):
        k=num(k);return Jet(self.v*k,tuple(v*k for v in self.g),tuple(tuple(v*k for v in row) for row in self.h))
    __rmul__=__mul__
    def power(self,r):
        r=num(r);need(self.v>0,'positive power argument')
        v=self.v**r;d=r*self.v**(r-1);dd=r*(r-1)*self.v**(r-2)
        return Jet(v,tuple(d*x for x in self.g),tuple(tuple(d*self.h[i][j]+dd*self.g[i]*self.g[j] for j in range(5)) for i in range(5)))
    def logarithm(self):
        need(self.v>0,'positive log argument');v=self.v
        return Jet(log(v),tuple(x/v for x in self.g),tuple(tuple(self.h[i][j]/v-self.g[i]*self.g[j]/(v*v) for j in range(5)) for i in range(5)))


def variable(v,i):return Jet(v,tuple(1.0 if j==i else 0.0 for j in range(5)))


def power_mean(xs,w,r):
    r=num(r);need(r!=0 and r<1,'nonzero power less than one')
    w=probabilities(w);need(len(xs)==len(w),'power-mean dimensions')
    need(all(isinstance(x,Jet) and x.v>0 for x in xs),'positive power-mean inputs')
    return sum((x.power(r)*p for x,p in zip(xs,w)),Jet(0)).power(1/r)


def recursive(cons,beta=.9,gamma=4,psi=2,p=(.5,.5),normalized=True):
    c=seq(cons,5);beta,gamma,psi=map(num,(beta,gamma,psi));p=probabilities(p)
    need(0<beta<1 and gamma>0 and gamma!=1 and psi>0 and psi!=1 and min(c)>0 and len(p)==2,'finite recursive preference domain')
    rho=1-1/psi;k=(1-beta)**(1/rho) if normalized else 1.0
    x=tuple(variable(v,i) for i,v in enumerate(c));terminal=(x[3]*k,x[4]*k)
    u=tuple(power_mean((x[i+1],terminal[i]),(1-beta,beta),rho) for i in range(2))
    ce=power_mean(u,p,1-gamma);root=power_mean((x[0],ce),(1-beta,beta),rho)
    m=tuple(root.g[i+1]/root.g[0]/p[i] for i in range(2))
    return root,u,ce,m


def internal(beta,a,c0,c1,H0=0):
    beta,a,c0,c1,H0=map(num,(beta,a,c0,c1,H0))
    need(0<beta<1 and a>=0 and c0>H0 and c1>a*c0,'internal habit positive surplus')
    x0=variable(c0,0);x1=variable(c1,1)
    utility=(x0+(-H0)).logarithm()+(x1+x0*(-a)).logarithm()*beta
    need(utility.g[0]>0,'positive net current marginal value')
    return utility.g[0],utility.g[1]/utility.g[0]


def parsed(s):
    def read(n):
        if isinstance(n,ast.Constant):return num(n.value)
        if isinstance(n,(ast.Tuple,ast.List)):return tuple(read(x) for x in n.elts)
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,(ast.USub,ast.UAdd)):return read(n.operand)*(-1 if isinstance(n.op,ast.USub) else 1)
        if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Div):
            d=read(n.right);need(d!=0,'zero marker denominator');return read(n.left)/d
        raise ValueError('invalid numeric marker')
    return read(ast.parse(s.strip(),mode='eval').body)


class Document(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.stack=[];self.mark={};self.pending=[];self.ids=[];self.ex=[];self.sol=[];self.worked=[];self.sources={};self.text=[]
    def handle_starttag(self,t,attrs):
        d=dict(attrs);cl=d.get('class','').split()
        if 'id' in d:need(d['id'] not in self.ids,'duplicate ID');self.ids.append(d['id'])
        if 'worked' in cl:self.worked.append(d.get('id'))
        if t=='li' and d.get('id','').startswith('v14-c07-e'):self.ex.append(d['id'])
        if 'data-solution-for' in d:
            need(any(tag=='details' and 'solutions' in a.get('class','').split() for tag,a in self.stack),'solution outside details');self.sol.append(d['data-solution-for'])
        if 'data-source' in d:self.sources[d['data-source']]=d.get('href')
        for typ in ('data-input','data-calc'):
            if typ in d:
                key=d[typ];need(key not in self.mark,'duplicate marker');self.mark[key]=[typ,''];self.pending.append((key,len(self.stack)))
        if t not in ('br','hr','img','input','link','meta'):self.stack.append((t,d))
    def handle_endtag(self,t):
        need(bool(self.stack) and self.stack[-1][0]==t,'unbalanced HTML');self.stack.pop();self.pending=[(k,n) for k,n in self.pending if n<len(self.stack)]
    def handle_data(self,s):
        self.text.append(s)
        for k,n in self.pending:self.mark[k][1]+=s


def check(root=None):
    base=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    payload={p:(base/p).read_bytes() for p in FILES};doc=Document();doc.feed(payload[AUTHOR[0]].decode());doc.close()
    need(not doc.stack and all(x.startswith('v14-c07-') for x in doc.ids),'closed prefixed HTML')
    ex=['v14-c07-e'+str(i) for i in range(1,13)];need(doc.ex==ex and doc.sol==ex,'full prompt/solution pairing')
    need(doc.worked==['v14-c07-w'+str(i) for i in range(1,6)],'worked cases')
    sources=json.loads(payload[AUTHOR[2]]);author=json.loads(payload[AUTHOR[3]]);peer=json.loads(payload[FILES[-1]])
    need(doc.sources=={s['id']:s['url'] for s in sources['sources']},'source routing')
    need(set(peer['exact_prompt_solution_audit'])==set(ex),'peer full exercise audit')
    for record,needed in ((author,set(AUTHOR[:3])),(peer,set(FILES[:-1]))):
        need(len(record['payload_bindings'])==len(needed) and {x['path'] for x in record['payload_bindings']}==needed,'nonself payload bindings')
        for b in record['payload_bindings']:need(len(payload[b['path']])==b['bytes'] and sha256(payload[b['path']]).hexdigest()==b['sha256'],'frozen payload changed')
    values={k:parsed(v[1]) for k,v in doc.mark.items() if v[0]=='data-calc'};inputs={k:parsed(v[1]) for k,v in doc.mark.items() if v[0]=='data-input'}
    comparisons=0;rejects=0
    def near(a,b,tol=6e-11):
        nonlocal comparisons
        if isinstance(b,(tuple,list)):
            need(isinstance(a,(tuple,list)) and len(a)==len(b),'comparison length')
            for x,y in zip(a,b):near(x,y,tol)
        else:need(isfinite(float(a)) and abs(float(a)-float(b))<=tol*max(1,abs(float(b))),f'{a} != {b}');comparisons+=1
    need(set(inputs)=={'base','lognormal'},'input markers')
    near(inputs['base'],(.96,2,1,.9,1.1,.5));near(inputs['lognormal'],(.99,.02,.02,.4))
    beta,gamma,c0,cL,cH,p=inputs['base'];probs=(p,1-p);m=crra(beta,gamma,c0,(cL,cH));stats=pricing(m,probs,(cL,cH))
    diagnostic=lognormal(*inputs['lognormal']);A,row,v=tree(F(19,20),2,((F(4,5),F(1,5)),(F(3,10),F(7,10))),(F(49,50),F(26,25)))
    hm,rra=external(.96,2,1,.8,(.95,1.05),(.8,.8));hstats=pricing(hm,(.5,.5),(1,1))
    root,us,ce,em=recursive((1,1,1,.8,1.2));earrow=tuple(.5*x for x in em);rf=1/sum(earrow)
    e2=crra(.95,2,1,(.8,1.2));e2q=tuple(.5*x for x in e2);e4=lognormal(.99,0,.02,.2)
    e7,_=external(.96,2,1,.8,(.95,1.05),(.9,.9));lam,price=internal(.9,.2,1,1.2)
    derived={'base-m':m,'base-em':stats['em'],'base-price':stats['price'],'base-rf':stats['rf'],'base-er':stats['er'],'base-premium':stats['premium'],'base-sdr':stats['sdr'],'base-hj':stats['cv'],
      'puzzle-gamma':diagnostic[0],'puzzle-logrf':diagnostic[1],'puzzle-rf':diagnostic[2],
      'tree-a':row,'tree-v':v,'habit-m':hm,'habit-rf':hstats['rf'],'habit-rra':rra,'habit-hj':hstats['cv'],
      'ez-u':tuple(x.v for x in us),'ez-ce':ce.v,'ez-m':em,'ez-q':earrow,'ez-rf':rf,
      'e2-m':e2,'e2-q':e2q,'e2-rf':1/sum(e2q),'e4-gamma':e4[0],'e4-rf':e4[2],
      'e7-m':e7,'e7-rf':1/mean(e7,(.5,.5)),'e8-lambda':lam,'e8-price':price,'e11-news':(.001/(1-.5),.001/(1-.95))}
    need(set(values)==set(derived),'displayed numeric coverage')
    for key,val in derived.items():
        try:near(values[key],val)
        except ValueError as e:raise ValueError(key+': '+str(e)) from e
    # All covariance identities, two-state equality, strict three-state inequality and repaired degenerate case.
    for sdf,prob,pay in ((m,probs,(cL,cH)),(m,probs,(cH,cL)),((1.3,1,.6),(.2,.3,.5),(.5,2,1.4)),((.9,.9),(.5,.5),(.8,1.2))):
        st=pricing(sdf,prob,pay);near(st['premium'],-st['cov']/st['em'],1e-12)
        need(abs(sharpe(st))<=st['cv']+1e-12,'HJ restriction');comparisons+=1
    near(sharpe(stats),stats['cv'],1e-12)
    deg=pricing((.9,.9),(.5,.5),(.8,1.2));near((deg['premium'],deg['cv']),(0,0),1e-12)
    need(deg['sdr']>0,'constant SDF does not imply constant return');comparisons+=1
    need(pricing(m,probs,(cH,cL))['price']>stats['price'],'insurance price sign');comparisons+=1
    # Finite global concavity support in CRRA economy, not merely equation matching.
    def u(c,g):return log(c) if g==1 else c**(1-g)/(1-g)
    U=u(c0,gamma)+beta*mean(tuple(u(c,gamma) for c in (cL,cH)),probs)
    for delta in (-.15,-.04,.04,.15):
        now=c0-delta*stats['price'];later=tuple(c+delta*x for c,x in zip((cL,cH),(cL,cH)))
        need(now>0 and min(later)>0,'feasible supporting deviation')
        alt=u(now,gamma)+beta*mean(tuple(u(c,gamma) for c in later),probs)
        need(alt<U,'strict global support');comparisons+=1
    # Exact rational tree equations, residual certificate and safe log-utility comparison.
    for i in range(2):near(v[i],sum(A[i][j]*(1+v[j]) for j in range(2)),1e-13)
    near(F(1,1)/(1-row),F(5096,213))
    _,_,logv=tree(F(19,20),1,((F(4,5),F(1,5)),(F(3,10),F(7,10))),(F(49,50),F(26,25)));near(logv,(19,19))
    for shift in ((F(1,1000),F(-1,2000)),(F(-1,500),F(1,800))):
        candidate=tuple(x+y for x,y in zip(v,shift));res=max(abs(candidate[i]-sum(A[i][j]*(1+candidate[j]) for j in range(2))) for i in range(2))
        need(max(map(abs,shift))<=res/(1-row),'row certificate');comparisons+=1
    # A row sum over one is not itself a failure of fundamental existence.
    other=((F(0),F(6,5)),(F(1,5),F(0)));other_v=solve2(((1,-F(6,5)),(-F(1,5),1)),tuple(map(sum,other)))
    need(min(other_v)>0 and sqrt(float(other[0][1]*other[1][0]))<1,'row bound is only sufficient');comparisons+=1
    bad=F(19,18);near(bad/(1-bad),-19);need(bad>1,'divergent positive dividend sum');comparisons+=1
    for T in (1,5,20):
        discount=F(4,5);B=F(3,7);bT=B/discount**T
        near(discount**T*bT,B);near(discount*(B/discount**(T+1)),bT)
    # Recursive SDF reconstructed from root gradients, checked by independent chain expression.
    for parameters,c,p in (((.9,4,2),(1,1,1,.8,1.2),(.5,.5)),((.8,2,.5),(1.1,.9,1.2,.7,1.4),(.3,.7)),((.7,.5,2),(1,.8,1.3,.9,1.1),(.4,.6))):
        b,g,psi=parameters;ut,un,ct,ms=recursive(c,b,g,psi,p)
        formula=tuple(b*(c[i+1]/c[0])**(-1/psi)*(un[i].v/ct.v)**(1/psi-g) for i in range(2))
        near(ms,formula,2e-12)
        for i in range(2):near(ut.g[i+3]/ut.g[i+1],b*(c[i+3]/c[i+1])**(-1/psi),2e-12)
        for direction in ((1,-1,0,0,0),(0,1,1,-1,-1),(.2,-.3,.5,.7,-.4)):
            curvature=sum(direction[i]*ut.h[i][j]*direction[j] for i in range(5) for j in range(5))
            need(curvature<=1e-9,'recursive Hessian concavity witness');comparisons+=1
        # Global full-tree tangent certificate at endowment with dated Arrow transfers.
        weights=tuple(ut.g[i]/ut.g[0] for i in range(1,5))
        for shift in ((.02,-.03,.01,-.01),(-.02,.02,-.01,.03)):
            new=(c[0]-sum(q*d for q,d in zip(weights,shift)),)+tuple(c[i+1]+shift[i] for i in range(4))
            alternative=recursive(new,b,g,psi,p)[0]
            need(alternative.v<=ut.v+1e-12,'recursive global supporting tangent');comparisons+=1
    # Terminal normalization and the same-tree CRRA special case.
    normal=recursive((1,1,1,.8,1.2),.9,4,2)[0];raw=recursive((1,1,1,.8,1.2),.9,4,2,normalized=False)[0]
    for i in range(2):near(raw.g[i+3]/raw.g[i+1],10*normal.g[i+3]/normal.g[i+1],2e-12)
    for psi in (.5,2):
        g=1/psi;c=(1.1,.9,1.2,.8,1.3);ms=recursive(c,.8,g,psi)[3]
        near(ms,crra(.8,g,c[0],c[1:3]),2e-12)
    swapped=recursive((1,1,1,1.2,.8));near(swapped[2].v,ce.v);near(swapped[3],tuple(reversed(em)))
    # Direct finite differences of utility do not use the printed SDF formula.
    c=[1,1,1,.8,1.2];eps=1e-5
    for i in range(3):
        plus=c.copy();minus=c.copy();plus[i]+=eps;minus[i]-=eps
        fd=(recursive(plus)[0].v-recursive(minus)[0].v)/(2*eps)
        near(fd,root.g[i],2e-9)
    # Power mean Hessian witness includes negative exponent and homogeneous zero direction.
    for r in (-3,-1,.2,.5):
        xs=(variable(.8,0),variable(1.3,1),variable(2,2));pm=power_mean(xs,(.2,.3,.5),r)
        for direction in ((1,-2,.5),(.8,1.3,2)):
            quad=sum(direction[i]*pm.h[i][j]*direction[j] for i in range(3) for j in range(3))
            need(quad<=1e-11,'power mean Hessian sign');comparisons+=1
            if direction==(.8,1.3,2):near(quad,0,1e-11)
    near(internal(.9,.2,1,1.2),(1-.9*.2,.9/(1-.9*.2)),1e-12)
    for rho in (.5,.95,-.5):
        near(sum(.001*rho**j for j in range(1000)),.001/(1-rho),1e-12)
    invalid=[(crra,(0,2,1,(.9,1.1))),(crra,(1,2,1,(.9,1.1))),(crra,(.9,0,1,(.9,1.1))),
      (crra,(.9,2,0,(.9,1.1))),(crra,(.9,2,1,(0,1.1))),
      (pricing,((1,-1),(.5,.5),(1,1))),(pricing,((1,1),(.5,.4),(1,1))),
      (pricing,((1,1),(.5,.5),(-1,-1))),(sharpe,(pricing((1,1),(.5,.5),(1,1)),)),
      (lognormal,(.99,0,0,.2)),(lognormal,(.99,0,.02,0)),
      (tree,(F(19,20),2,((1,0),(0,1)),(F(9,10),F(9,10)))),
      (tree,(F(19,20),2,((F(1,2),F(1,3)),(0,1)),(1,1))),
      (external,(.96,2,1,.8,(.95,1.05),(.95,.9))),
      (external,(.96,2,1,1,(.95,1.05),(.8,.8))),
      (internal,(.9,.8,1,.9)),(internal,(.9,.2,1,.1)),
      (recursive,((1,1,1,.8,1.2),.9,1,2)),(recursive,((1,1,1,.8,1.2),.9,4,1)),
      (recursive,((1,1,1,0,1.2),.9,4,2)),(recursive,((1,1,1,.8,1.2),0,4,2)),
      (recursive,((1,1,1,.8,1.2),.9,4,-1)),(power_mean,((Jet(1),Jet(2)),(.5,.5),0)),
      (power_mean,((Jet(0),Jet(2)),(.5,.5),.5)),(probabilities,((0,1),)),
      (num,(True,)),(num,(float('inf'),)),(parsed,('1/0',)),(parsed,('sum((1,2))',))]
    for fn,args in invalid:
        try:fn(*args)
        except (ValueError,OverflowError):rejects+=1
        else:raise ValueError('invalid domain accepted: '+fn.__name__)
    summary={'chapter':'v14-c07','status':'passed','review':'separate peer','comparisons':comparisons,'domain_rejections':rejects,
             'worked_cases':5,'solved_exercises':12,'input_markers':len(inputs),'result_markers':len(values),'runtime_files':6,
             'scope':'Independent exact finite pricing, tree equations, second-order recursive-utility derivatives and boundary audit; no author code executed.'}
    json.dumps(summary,allow_nan=False);return summary


if __name__=='__main__':check()
