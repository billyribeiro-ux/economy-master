"""C11 independent peer: derivative bisection, reward series, binomial enumeration."""
from pathlib import Path
from hashlib import sha256
from html.parser import HTMLParser
from fractions import Fraction as F
from math import log,sqrt,isfinite,comb
import ast,json
FILES=('content/chapters/v14-c11.html','scripts/check_v14_c11.py','content/reviews/v14-c11-sources.json','content/reviews/v14-c11-author.json','scripts/check_v14_c11_peer.py','content/reviews/v14-c11-peer.json')
def need(ok,msg):
    if not ok:raise ValueError(msg)
def real(x):
    need(type(x) in (int,float,F) and isfinite(float(x)),'finite real');return float(x)
def probability(x,closed=False):
    x=real(x);need(0<=x<=1 if closed else 0<x<1,'probability');return x

def action(beta,e,grid=None):
    beta,e=map(real,(beta,e));need(beta>0 and e>0,'action primitives')
    obj=lambda a:-a+beta*e*sqrt(a)
    if grid is not None:
        need(isinstance(grid,(tuple,list)) and len(grid)>0,'nonempty action grid')
        grid=tuple(map(real,grid));need(min(grid)>=1 and max(grid)<=4,'capacity grid')
        a=max(grid,key=obj);return a,obj(a)
    deriv=lambda a:-1+beta*e/(2*sqrt(a))
    if deriv(1)<=0:a=1.
    elif deriv(4)>=0:a=4.
    else:
        lo,hi=1.,4.
        for _ in range(90):
            mid=(lo+hi)/2
            if deriv(mid)>0:lo=mid
            else:hi=mid
        a=(lo+hi)/2
    return a,obj(a)

def economy(p,q,beta=.5,grid=None):
    p,q=probability(p,True),probability(q,True);beta=probability(beta)
    P=((1-p,p),(q,1-q));prod=(5.,7.);expected=tuple(sum(x*y for x,y in zip(row,prod)) for row in P)
    optimal=tuple(action(beta,e,grid) for e in expected);a=tuple(x[0] for x in optimal);d=tuple(x[1] for x in optimal)
    H=[0.,0.];term=d
    for _ in range(500):H=[x+y for x,y in zip(H,term)];term=tuple(beta*sum(x*y for x,y in zip(row,term)) for row in P)
    return dict(P=P,e=expected,a=a,d=d,H=tuple(H),V=tuple(A*sqrt(k)+H[z] for z,A in enumerate(prod) for k in (1,4)))

def counts(c):
    need(isinstance(c,(tuple,list)) and len(c)==4,'four counts');need(all(type(x)==int for x in c),'integer counts')
    n,m,h,j=c;need(n>0 and h>0 and 0<=m<=n and 0<=j<=h,'observed rows');return c

def scores(c,probs):
    counts(c);need(len(probs)==2,'two forecast probabilities');probs=tuple(probability(p,True) for p in probs)
    obs=[(v,probs[0]) for v in [1]*c[1]+[0]*(c[0]-c[1])]+[(v,probs[1]) for v in [1]*c[3]+[0]*(c[2]-c[3])]
    terms=[]
    for v,p in obs:
        weight=p if v else 1-p;terms.append(log(weight) if weight else float('-inf'))
    return sum(terms)/len(obs),sum((v-p)**2 for v,p in obs)/len(obs)

def moments(p,q):
    p,q=probability(p),probability(q)
    # Stationary odds from detailed balance; lag cross moment from actual joint law.
    mu=p/(p+q);joint11=mu*(1-q);var=mu*(1-mu);cov=joint11-mu*mu
    return mu,cov/var,var,cov

def inverse_moments(mu,rho):
    mu=probability(mu);rho=real(rho);p=mu*(1-rho);q=(1-mu)*(1-rho);probability(p);probability(q);return p,q

def binomial(n,p):
    need(type(n)==int and n>0,'positive count');p=probability(p,True)
    law=tuple(comb(n,j)*p**j*(1-p)**(n-j) for j in range(n+1));mean=sum(j/n*w for j,w in enumerate(law));variance=sum((j/n-mean)**2*w for j,w in enumerate(law));return mean,variance,law

def literal(s):
    def walk(n):
        if isinstance(n,ast.Constant):return real(n.value)
        if isinstance(n,(ast.Tuple,ast.List)):return tuple(walk(x) for x in n.elts)
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,(ast.UAdd,ast.USub)):return (-1 if isinstance(n.op,ast.USub) else 1)*walk(n.operand)
        if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Div):return walk(n.left)/walk(n.right)
        raise ValueError('literal numeric expression')
    return walk(ast.parse(s.replace('−','-').strip(),mode='eval').body)
class Reader(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.mark={};self.active=None;self.ids=[];self.ex=[];self.sol=[];self.work=[];self.sources={}
    def handle_starttag(self,t,attrs):
        a=dict(attrs)
        if 'id' in a:self.ids.append(a['id'])
        if 'worked' in a.get('class','').split():self.work.append(a['id'])
        if t=='li' and a.get('id','').startswith('v14-c11-e'):self.ex.append(a['id'])
        if 'data-solution-for' in a:self.sol.append(a['data-solution-for'])
        if 'data-source' in a:self.sources[a['data-source']]=a['href']
        for attr in ('data-input','data-calc'):
            if attr in a:need(a[attr] not in self.mark,'unique marker');self.active=a[attr];self.mark[self.active]=[attr,'']
    def handle_data(self,s):
        if self.active:self.mark[self.active][1]+=s
    def handle_endtag(self,t):
        if t=='span':self.active=None

def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1];raw={p:(root/p).read_bytes() for p in FILES};doc=Reader();doc.feed(raw[FILES[0]].decode());doc.close()
    ex=['v14-c11-e'+str(j) for j in range(1,13)];need(doc.ex==doc.sol==ex,'exact twelve pairs');need(doc.work==['v14-c11-w'+str(j) for j in range(1,6)],'five cases');need(len(doc.ids)==len(set(doc.ids)),'unique IDs')
    author=json.loads(raw[FILES[3]]);peer=json.loads(raw[FILES[5]]);source=json.loads(raw[FILES[2]])
    need(set(author['exact_prompt_solution_audit'])==set(peer['exact_prompt_review'])==set(ex),'full prompt review');need(doc.sources=={s['id']:s['url'] for s in source['sources']},'source routes')
    for rec,paths in ((author,FILES[:3]),(peer,FILES[:5])):
        bs=rec['payload_bindings'];need(len(bs)==len(paths) and {b['path'] for b in bs}==set(paths),'binding set')
        for b in bs:need(len(raw[b['path']])==b['bytes'] and sha256(raw[b['path']]).hexdigest()==b['sha256'],'exact payload')
    comparison=0;rejection=0;seen=set()
    def near(x,y):
        nonlocal comparison
        if isinstance(y,(tuple,list)):
            need(isinstance(x,(tuple,list)) and len(x)==len(y),'comparison shape')
            for a,b in zip(x,y):near(a,b)
        else:need(isfinite(float(x)) and abs(float(x)-float(y))<2e-9*max(1,abs(float(y))),str((x,y)));comparison+=1
    def yes(ok,msg):
        nonlocal comparison
        need(ok,msg);comparison+=1
    def mark(k,v):near(literal(doc.mark[k][1]),v);seen.add(k)
    primitives={'growth-primitives':(.5,.5,4),'growth-local':(.25,.25),'growth-far':100,'global-primitives':(.5,5,7,.3,.4),'fine-grid-gap':.25,'transition-perturbation':.05,'training-counts':(20,6,20,8),'p-scenario':.1,'coverage-design':(200,200,.2),'moment-alternative':(.15,.2),'validation-counts':(10,5,10,2),'validation-comparator':(.25,.25)}
    for k,v in primitives.items():mark(k,v)
    alpha,beta,A=.5,.5,4;s=alpha*beta;bar=(s*A)**(1/(1-alpha));B=alpha/(1-s);H=(log((1-s)*A)+beta*B*log(s*A))/(1-beta)
    mark('growth-constants',(s,bar,B));h=d=.25;exact=(1+h)**alpha;first=1+alpha*h;second=first+alpha*(alpha-1)*h*h/2
    mark('growth-local-values',(exact,first,second));mark('growth-local-errors',(first-exact,second-exact));bound=alpha*(1-alpha)*(2-alpha)*abs(h)**3/(6*(1-d)**(3-alpha));mark('growth-second-bound',bound);yes(abs(second-exact)<bound,'Taylor certificate');mark('growth-far-values',(s*A*100**alpha,1+alpha*99,A*100**alpha))
    for k in (.001,.75,1,1.25,100):
        value=0.;kt=k
        for t in range(120):
            resources=A*kt**alpha;kp=s*resources;value+=beta**t*log(resources-kp);kt=kp
        near(value,B*log(k)+H)
    for h in (-.25,-.1,0,.1,.25):
        vals=((1+h)**alpha-1,alpha*h,alpha*h+alpha*(alpha-1)*h*h/2);yes(all(-.25<=x<=.25 for x in vals),'invariant perturbation domain')
    full=economy(.3,.4);grid=economy(.3,.4,grid=(1,4))
    for key,val in (('global-actions',full['a']),('global-constants',full['H']),('global-values',full['V']),('grid-actions',grid['a']),('grid-rewards',grid['d']),('grid-constants',grid['H'])):mark(key,val)
    residual=tuple(a-b for a,b in zip(full['d'],grid['d']));loss=tuple(a-b for a,b in zip(full['H'],grid['H']));mark('grid-residuals',residual);mark('grid-losses',loss);mark('grid-bound',max(residual)/.5);yes(max(loss)<=max(residual)/.5,'policy certificate')
    mark('fine-grid-action-bound',.5*(7/8)*(.25/2)**2);mark('fine-grid-value-bound',(7/16)*(.25/2)**2/.5);mark('primitive-value-bound',.5*13*.1/.5**2)
    for p,q in ((.3,.4),(.15,.2),(.05,.95),(.8,.2)):
        model=economy(p,q)
        for z,e in enumerate(model['e']):
            optimum=model['d'][z]
            for i in range(21):
                a=1+3*i/20;yes(-a+.5*e*sqrt(a)<=optimum+1e-12,'global action optimum')
            for k in (1,1.37,2.25,3.6,4):
                a=model['a'][z];c=(5+2*z)*sqrt(k)-a;cont=sum(model['P'][z][j]*((5+2*j)*sqrt(a)+model['H'][j]) for j in (0,1));near((5+2*z)*sqrt(k)+model['H'][z],c+.5*cont);yes(c>=1-1e-12,'funded policy')
    for be,e,expected in ((.25,5,1),(.9,7,4),(.4,5,1),(.8,5,4)):near(action(be,e)[0],expected)
    # Independently check a finer actual grid against its proved value-loss bound.
    fine=economy(.3,.4,grid=tuple(1+i/4 for i in range(13)));yes(max(a-b for a,b in zip(full['H'],fine['H']))<=7/512+1e-12,'fine grid bound')
    training=(20,6,20,8);validation=(10,5,10,2);phat=6/20;qhat=8/20;mark('panel-mle',(phat,qhat));momL=binomial(20,phat);momH=binomial(20,qhat);mark('panel-se',(sqrt(momL[1]),sqrt(momH[1])))
    for n,p in ((5,.2),(20,.3),(20,.4)):
        mean,var,law=binomial(n,p);near(sum(law),1);near(mean,p);near(var,p*(1-p)/n)
        for eps in (.1,.3):
            tail=sum(w for j,w in enumerate(law) if abs(j/n-p)>=eps);yes(tail<=min(1,p*(1-p)/(n*eps*eps))+1e-12,'finite Chebyshev')
    mark('coverage-failure-bound',(1/200+1/200)/(4*.2**2))
    old=full['a'][0];new=economy(.4,.4)['a'][0];delta=.00001;dL=(economy(.3+delta,.4)['a'][0]-economy(.3-delta,.4)['a'][0])/(2*delta);dH=(economy(.3,.4+delta)['a'][1]-economy(.3,.4-delta)['a'][1])/(2*delta)
    mark('policy-derivatives',(dL,dH));mark('policy-shift-choice',new);mark('policy-shift-change',new-old);mark('policy-shift-linear',dL*.1);mark('policy-shift-remainder',new-old-dL*.1)
    mark('stationary-moments',moments(.3,.4));mark('alternative-moments',moments(.15,.2));mark('alternative-actions',economy(.15,.2)['a']);mark('moment-jacobian-det',-1/(.3+.4))
    for p,q in ((.3,.4),(.15,.2),(.9,.9),(.1,.8)):
        mu,rho,var,cov=moments(p,q);near(inverse_moments(mu,rho),(p,q));near((1-mu)*p,mu*q)
    for label,c in (('training',training),('validation',validation)):
        fitted=scores(c,(.3,.4));calibrated=scores(c,(.25,.25));mark(label+'-log-scores',(fitted[0],calibrated[0]));mark(label+'-brier',(fitted[1],calibrated[1]))
    # Proper expected scores checked independently over a grid of reports.
    for t in (.2,.5,.8):
        true_log=t*log(t)+(1-t)*log(1-t)
        for x in (.1,.3,.6,.9):
            yes(true_log>=t*log(x)+(1-t)*log(1-x),'proper log');near(t*(1-x)**2+(1-t)*x*x,t*(1-t)+(x-t)**2)
    yes(scores((5,1,5,2),(0,.5))[0]==float('-inf'),'zero probability forecast failure')
    mark('e4-bounds',((.001+.002)/.5,(2*(.001+.002)+.005)/.5));mark('e5-grid-bounds',((3/4)*(.25/2)/.5,(7/16)*(.25/2)**2/.5));mark('e6-tie-advantages',tuple(-4+.5*(7-2*q)*2-(-1+.5*(7-2*q)) for q in (.49,.51,.5)));mark('e9-infeasible-pair',(.8*1.5,.2*1.5))
    need(seen==set(doc.mark),'all primitives/results independently checked')
    bad=[(real,(True,)),(real,(float('nan'),)),(probability,(0,)),(probability,(1,)),(action,(0,5)),(action,(.5,0)),(action,(.5,6,())),(action,(.5,6,(0,1))), (economy,(-.1,.4)),(economy,(.3,.4,1)),(counts,((0,0,5,1),)),(counts,((5,6,5,1),)),(counts,((5,1,5,1.5),)),(counts,((True,0,5,1),)),(scores,((5,1,5,1),(.5,))), (scores,((5,1,5,1),(.5,1.1))), (moments,(0,.4)),(inverse_moments,(.8,-.5)),(inverse_moments,(.4,1)),(binomial,(0,.5)),(binomial,(5,-1)),(literal,('f(1)',)),(literal,('1/0',))]
    for fn,args in bad:
        try:fn(*args)
        except (ValueError,ZeroDivisionError):rejection+=1
        else:raise ValueError('invalid input accepted '+fn.__name__)
    out=dict(chapter='v14-c11',status='passed',comparisons=comparison,domain_rejections=rejection,worked_cases=5,solved_exercises=12,primitive_markers=sum(v[0]=='data-input' for v in doc.mark.values()),result_markers=sum(v[0]=='data-calc' for v in doc.mark.values()),runtime_files=6,method='Independent derivative bisection, discounted reward series, individual observation scores and finite-binomial moments; no author code execution')
    json.dumps(out,allow_nan=False);return out
if __name__=='__main__':check()
