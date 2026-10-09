"""Separate Form A six-payload oracle. Author checker is read only as bytes."""
import ast,json
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from itertools import product
from math import isfinite,log,sqrt,isqrt
from pathlib import Path
AUTHOR=('content/assessments/parts/v14-exam-a.html','scripts/check_v14_exam_a.py','content/reviews/v14-exam-a-sources.json','content/reviews/v14-exam-a-author.json')
FILES=AUTHOR+('scripts/check_v14_exam_a_peer.py','content/reviews/v14-exam-a-peer.json')
def need(ok,msg):
    if not ok:raise ValueError(msg)
def num(x):
    need(type(x) in (int,float,F) and isfinite(float(x)),'finite scalar');return F(str(x)) if isinstance(x,float) else F(x)
def literal(s):
    def read(n):
        if isinstance(n,ast.Constant):return num(n.value)
        if isinstance(n,(ast.Tuple,ast.List)):return tuple(read(x) for x in n.elts)
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,(ast.USub,ast.UAdd)):return (-1 if isinstance(n.op,ast.USub) else 1)*read(n.operand)
        if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Div):
            d=read(n.right);need(d!=0,'zero divisor');return read(n.left)/d
        raise ValueError('numeric marker syntax')
    return read(ast.parse(s.replace('−','-').rsplit('=',1)[-1].strip(),mode='eval').body)
def law(p):
    p=tuple(map(num,p));need(p and min(p)>0 and sum(p)==1,'positive exhaustive probability law');return p
def solve(M,b):
    n=len(b);need(n>0 and len(M)==n and all(len(r)==n for r in M),'square system');a=[list(r)+[x] for r,x in zip(M,b)]
    for j in range(n):
        k=max(range(j,n),key=lambda i:abs(a[i][j]));need(a[k][j]!=0,'nonsingular system');a[j],a[k]=a[k],a[j];q=a[j][j];a[j]=[x/q for x in a[j]]
        for i in range(n):
            if i!=j:
                q=a[i][j];a[i]=[x-q*y for x,y in zip(a[i],a[j])]
    return tuple(r[-1] for r in a)
def multiply(A,B):return tuple(tuple(sum(A[i][k]*B[k][j] for k in range(len(B))) for j in range(len(B[0]))) for i in range(len(A)))
def rational_sqrt(x):
    need(x>=0,'nonnegative square root');a=isqrt(x.numerator);b=isqrt(x.denominator);need(a*a==x.numerator and b*b==x.denominator,'exact rational root required');return F(a,b)
def default_contract(face,y,p,loss,R):
    face,loss,R=map(num,(face,loss,R));y=tuple(map(num,y));p=law(p);need(len(y)==len(p) and min(y)>0 and face>=0 and 0<loss<1 and R>0,'default domain');H=tuple(int(face<=loss*income) for income in y);price=sum(w*h for w,h in zip(p,H))/R;cons=tuple(income-face if h else income*(1-loss) for income,h in zip(y,H));return price,H,cons

def hj(p,m,returns):
    p=law(p);m=tuple(map(num,m));returns=tuple(map(num,returns));need(len(p)==len(m)==len(returns) and min(m)>0,'HJ domain');mean=lambda x:sum(w*y for w,y in zip(p,x));em=mean(m);er=mean(returns);vr=mean(tuple((r-er)**2 for r in returns));vm=mean(tuple((x-em)**2 for x in m));need(vr>0 and mean(tuple(x*r for x,r in zip(m,returns)))==1,'positive return variance and priced claim');return abs(float(er-1/em))/sqrt(vr),sqrt(vm)/float(em),vm,vr

def invest(Q,n=None):
    Q=num(Q);need(Q>0,'positive marginal value');uncon=max(F(0),Q-1)
    if n is None:return uncon
    n=num(n);need(n>=0,'internal cash domain');cap=(-1+rational_sqrt(1+8*n))/2;I=min(uncon,cap);cost=I+I*I/2;loan=max(F(0),cost-n);mult=(Q-1-I)/(F(1,2)+I) if I==cap else F(0);deriv=1/(F(1,2)+I) if cap<uncon else F(0);return I,loan,mult,deriv

def dealers(mu,var,risk,supply,caps):
    mu,var,risk,supply=map(num,(mu,var,risk,supply));caps=tuple(map(num,caps));need(mu>0 and var>0 and risk>0 and supply>0 and len(caps)==2 and min(caps)>0,'dealer domain');h=risk*var;found=[]
    # Enumerate every cap active set instead of iterating aggregate demand.
    for active in product((False,True),repeat=2):
        unbound=2-sum(active);cash=sum(c for c,on in zip(caps,active) if on)
        if unbound:
            bb=float(supply*h-unbound*mu);disc=bb*bb+4*unbound*float(h*cash);p=(-bb+sqrt(disc))/(2*unbound)
        else:p=float(cash/supply)
        if not 0<p<float(mu):continue
        unc=(float(mu)-p)/float(h);x=tuple(float(c)/p if on else unc for c,on in zip(caps,active))
        if all((float(c)/p<=unc+1e-12) if on else (p*xx<=float(c)+1e-12) for c,on,xx in zip(caps,active,x)):
            if not any(abs(p-old[0])<1e-10 for old in found):found.append((p,x,active))
    need(len(found)==1,'unique admissible cap regime');return found[0]
def counts(c):
    need(len(c)==4 and all(type(x) is int for x in c),'integer counts');n,m,h,j=c;need(n>0 and h>0 and 0<=m<=n and 0<=j<=h,'count domain');return F(m,n),F(j,h)
def score(c,forecast):
    counts(c);p,q=map(num,forecast);need(0<p<1 and 0<q<1,'interior predictive law');n,m,h,j=c
    ll=(m*log(p)+(n-m)*log(1-p)+j*log(q)+(h-j)*log(1-q))/(n+h);brier=(m*(1-p)**2+(n-m)*p*p+j*(1-q)**2+(h-j)*q*q)/(n+h);return ll,brier

def clearing(e,b,A):
    e,b=tuple(map(num,e)),tuple(map(num,b));A=tuple(tuple(map(num,r)) for r in A);n=len(e);need(n and len(b)==len(A)==n and all(len(r)==n for r in A),'network shape');need(min(e)>=0 and min(b)>0 and all(min(r)>=0 and sum(r)<1 for r in A),'outside leakage');found=[]
    for defaults in product((False,True),repeat=n):
        M=tuple(tuple(F(i==j)-A[j][i] if defaults[i] else F(i==j) for j in range(n)) for i in range(n));rhs=tuple(e[i] if defaults[i] else b[i] for i in range(n));p=solve(M,rhs);resources=tuple(e[i]+sum(A[j][i]*p[j] for j in range(n)) for i in range(n))
        if all(p[i]==min(b[i],resources[i]) and p[i]>=0 for i in range(n)) and p not in found:found.append(p)
    need(len(found)==1,'unique clearing');p=found[0];equity=tuple(e[i]+sum(A[j][i]*p[j] for j in range(n))-p[i] for i in range(n));outside=sum((1-sum(A[i]))*p[i] for i in range(n));return p,equity,outside

class Document(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.stack=[];self.active=[];self.mark={};self.inputs={};self.ids=[];self.prompts={};self.answers=[];self.rubrics={};self.domains={};self.sources={};self.headings=[]
    def handle_starttag(self,t,attrs):
        d=dict(attrs);need(len(d)==len(attrs),'unique attributes')
        if 'id' in d:need(d['id'] not in self.ids,'unique IDs');self.ids.append(d['id'])
        need(t!='h1','no extra h1')
        if t=='h2':self.headings.append(d.get('id'))
        if 'data-domain' in d:self.domains[d['data-domain']]=[int(d['data-domain-points']),[]]
        if 'data-points' in d:
            domain=next(a['data-domain'] for tag,a in reversed(self.stack) if 'data-domain' in a);self.prompts[d['id']]=(int(d['data-points']),d['data-chapters'].split());self.domains[domain][1].append(d['id'])
        if 'data-solution-for' in d:
            need(any(tag=='details' and 'solutions' in a.get('class','').split() for tag,a in self.stack),'disclosed answers');self.answers.append(d['data-solution-for'])
        if 'data-rubric-points' in d:
            target=next(a['data-solution-for'] for tag,a in reversed(self.stack) if 'data-solution-for' in a);need(target not in self.rubrics,'one rubric per part');self.rubrics[target]=tuple(int(x) for x in d['data-rubric-points'].split(','))
        if 'data-source' in d:self.sources[d['data-source']]=d['href']
        for key,dest in (('data-input',self.inputs),('data-calc',self.mark)):
            if key in d:
                k=d[key];need(k not in dest,'unique marker');dest[k]='';self.active.append((dest,k,len(self.stack)))
        if t not in ('br','hr','img','meta','link','input'):self.stack.append((t,d))
    def handle_data(self,s):
        for dest,k,n in self.active:dest[k]+=s
    def handle_endtag(self,t):
        need(self.stack and self.stack[-1][0]==t,'balanced HTML');self.stack.pop();self.active=[x for x in self.active if x[2]<len(self.stack)]

def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1];raw={f:(root/f).read_bytes() for f in FILES};doc=Document();doc.feed(raw[AUTHOR[0]].decode());need(not doc.stack,'closed HTML');author=json.loads(raw[AUTHOR[3]]);peer=json.loads(raw[FILES[5]]);src=json.loads(raw[AUTHOR[2]]);targets=['v14-exam-a-q'+str(i).zfill(2) for i in range(1,21)]
    need(list(doc.prompts)==doc.answers==targets and set(doc.rubrics)==set(targets),'20 exact prompt/answer/rubric pairs');need(doc.headings==['form-a','solutions-a'],'assessment anchors');need(all(i.startswith('v14-exam-a-') or i in doc.headings for i in doc.ids),'ID prefix');need(all(doc.prompts[t][0]==sum(doc.rubrics[t])==5 and min(doc.rubrics[t])>0 for t in targets),'additive five points');need(list(doc.domains)==['dynamic_distribution','labor_policy','pricing_investment','liquidity_international','quantitative_research'],'five domains');need(all(total==20 and len(ids)==4 for total,ids in doc.domains.values()),'four parts each domain');need({c for p,cc in doc.prompts.values() for c in cc}=={'v14-c'+str(i).zfill(2) for i in range(1,13)},'twelve chapter coverage');need(set(author['exact_prompt_solution_audit'])==set(peer['exact_prompt_review'])==set(targets),'full prose audit coverage')
    need(doc.sources=={s['id']:s['url'] for s in src['sources']},'source routes');need(all(s['inherited_scope'] and s['limits'] and 'no new' in s['attribution'] for s in src['sources']),'bounded inherited sources')
    for record,paths in ((author,AUTHOR[:3]),(peer,FILES[:-1])):
        bind=record['payload_bindings'];need(len(bind)==len(paths) and {b['path'] for b in bind}==set(paths),'nonself membership')
        for b in bind:need((b['bytes'],b['sha256'])==(len(raw[b['path']]),sha256(raw[b['path']]).hexdigest()),'exact binding')
    inputs={k:literal(v) for k,v in doc.inputs.items()};outputs={k:literal(v) for k,v in doc.mark.items()};expected={};count=0;policies=0
    def eq(a,b,label='identity',tol=8e-10):
        nonlocal count
        if isinstance(a,(tuple,list)) or isinstance(b,(tuple,list)):
            need(isinstance(a,(tuple,list)) and isinstance(b,(tuple,list)) and len(a)==len(b),label+' shape')
            for x,y in zip(a,b):eq(x,y,label,tol)
        else:count+=1;need(isfinite(float(a)) and isfinite(float(b)) and abs(float(a)-float(b))<=tol*max(1,abs(float(b))),label+str((a,b)))
    def out(k,v):expected[k]=v
    intended={'exchange-beta':F(9,10),'exchange-P':((F(3,4),F(1,4)),(F(1,4),F(3,4))),'rbc':(F(1,3),F(3,4),F(8,9)),'matching':(F(1,4),F(1,4),F(1,2),F(1,2),F(3,2),F(1,2)),'nk':(F(1,2),F(1,2),1,2,F(1,2)),'fiscal':(6,1,2,F(5,4)),'sovereign':(2,5,F(1,2),F(1,4),F(5,4)),'pricing-probabilities':(F(1,4),F(3,4)),'pricing-consumption':(F(9,10),1,F(1,2),F(3,2)),'investment-Q':2,'investment-cash':F(3,8),'deposit':(F(1,2),F(9,4),F(1,4)),'dealer':(2,F(1,4),2,2,F(1,2),4),'international':(F(1,2),F(1,2),3,1,F(7,2),F(5,2),F(1,2),F(3,2)),'currency':(F(1,4),F(9,5),F(3,5),3,F(1,2),F(3,2)),'sequence-K':((F(1,4),F(1,4)),(F(1,8),F(1,4))),'sequence-d':(F(1,10),0),'training-counts':(30,9,20,4),'holdout-counts':(8,2,12,3),'network-b':(4,4,4),'network-e':(1,0,0),'network-A':((0,F(1,2),0),(0,0,F(1,2)),(F(1,2),0,0))};need(set(inputs)==set(intended),'all22 inputs')
    for k,v in intended.items():eq(inputs[k],v,'visible primitive '+k)
    # Enumerate every feasible policy using its own matrix and reward; no author execution.
    beta=inputs['exchange-beta'];P=inputs['exchange-P'];assets=(-1,1);income=(2,6);states=list(product(assets,range(2)));C=[[a+income[z]-ap for ap in assets] for a,z in states];feasible=[[j for j,c in enumerate(row) if c>0] for row in C];optimal=[]
    for g in product(*feasible):
        policies+=1;Q=tuple(tuple(P[z][zp] if assets[g[i]]==ap else F(0) for ap,zp in states) for i,(a,z) in enumerate(states));M=tuple(tuple(F(i==j)-beta*Q[i][j] for j in range(4)) for i in range(4));V=solve(M,tuple(log(C[i][g[i]]) for i in range(4)));gaps=[]
        for i,(a,z) in enumerate(states):
            for j in feasible[i]:
                if j!=g[i]:gaps.append(V[i]-log(C[i][j])-float(beta)*sum(float(P[z][zp])*V[2*j+zp] for zp in range(2)))
        if min(gaps)>0:optimal.append((g,Q,V,gaps))
    need(len(optimal)==1,'unique strict policy');g,Q,V,gaps=optimal[0];eq(g,(0,1,0,1));out('exchange-gaps',gaps);c=tuple(C[i][g[i]] for i in range(4));mass=solve(tuple(tuple(Q[j][i]-F(i==j) for j in range(4)) for i in range(3))+((F(1),)*4,),(F(0),F(0),F(0),F(1)));out('exchange-mass',mass);eq(tuple(sum(mass[i]*Q[i][j] for i in range(4)) for j in range(4)),mass);Q2=multiply(Q,Q);eq(min(x for row in Q2 for x in row),F(1,16));eq(sum(mass[i]*states[i][0] for i in range(4)),0);eq(sum(mass[i]*assets[g[i]] for i in range(4)),0);meaninc=sum(mass[i]*income[z] for i,(a,z) in enumerate(states));out('exchange-goods',(meaninc,sum(w*cc for w,cc in zip(mass,c))));out('exchange-covariance',sum(mass[i]*a*income[z] for i,(a,z) in enumerate(states)))
    alpha,beta,chi=inputs['rbc'];B=alpha/(1-alpha*beta);share=beta*B/(1+beta*B);labor=(1+beta*B)*(1-alpha)/((1+beta*B)*(1-alpha)+chi);out('rbc-policy',(share,labor,B));const=log(share)+float(1-alpha)*log(labor);mean=const/float(1-alpha);out('rbc-geometric-capital',2**(mean/log(2)));out('rbc-log-variance-multiple',1/(1-alpha*alpha));out('rbc-output-correlation',alpha)
    for k,z in product((.01,.5,1,3),(.5,2)):
        Y=z*k**float(alpha)*float(labor)**float(1-alpha);kp=float(share)*Y;cc=(1-float(share))*Y;w=(1-float(alpha))*Y/float(labor);rent=float(alpha)*Y/k;eq(w*float(labor)+rent*k,Y);eq(float(chi)*cc/(1-float(labor)),w);rhs=0.
        for zp in (.5,2):
            yp=zp*kp**float(alpha)*float(labor)**float(1-alpha);rhs+=.5*float(beta)*float(alpha)*yp/kp/((1-float(share))*yp)
        eq(rhs,1/cc);eq(kp/cc,float(share/(1-share)))
    r,s,k,b,y,eta=inputs['matching'];aa=k*eta;bb=k*(r+s);cc=-(1-eta)*(y-b);x=(-bb+rational_sqrt(bb*bb-4*aa*cc))/(2*aa);theta=x*x;J=k*x;X=eta*J/(1-eta);U=(b+x*X)/r;E=U+X;w=y-(r+s)*J;unemp=s/(s+x);out('matching-quantities',(theta,x,1/x,w,J,U,E,unemp));eq(r*E,w+s*(U-E));eq(x*unemp,s*(1-unemp));eq(k,(1/x)*J)
    be,kappa,sigma,phi,rho=inputs['nk'];a,b,i=solve(((1-rho,-rho/sigma,1/sigma),(-kappa,1-be*rho,F(0)),(F(0),-phi,F(1))),(F(0),F(0),F(1)));out('nk-response',(a,b,i));eq(a,rho*a-(i-rho*b)/sigma);eq(b,be*rho*b+kappa*a);N=((F(0),F(0)),(F(-1),F(0)));eq(multiply(N,N),((0,0),(0,0)));A=((F(2),F(0)),(F(-1),F(2)));inv=tuple(zip(*(solve(A,(F(j==0),F(j==1))) for j in range(2))));power=((F(1),F(0)),(F(0),F(1)))
    for n in range(1,9):
        power=multiply(power,inv);formula=((F(1,2)**n,F(0)),(F(n,2)*F(1,2)**n,F(1,2)**n));eq(power,formula,'Jordan inverse power')
    D,s0,s1,R=inputs['fiscal'];b0=D-s0;b1=R*b0-s1;s2=R*b1;out('fiscal-terminal-surplus',s2);out('fiscal-pv',s0+s1/R+s2/R**2)
    for terminal in (F(0),F(3)):eq(s0+s1/R+(R*b1-terminal)/R**2+terminal/R**2,D)
    yl,yh,pL,loss,R=inputs['sovereign'];prob=(pL,1-pL);q,H,c=default_contract(1,(yl,yh),prob,loss,R);out('default-proceeds',q)
    for face in (F(0),loss*yl,loss*yl+F(1,1000),F(1),loss*yh,loss*yh+F(1,1000),F(8)):
        q,H,c=default_contract(face,(yl,yh),prob,loss,R);eq(R*q*face,sum(p*h*face for p,h in zip(prob,H)))
        for yy,h,cc in zip((yl,yh),H,c):eq(cc+h*face+(1-h)*loss*yy,yy);need(cc>0,'positive terminal utility');count+=1
    beta,c0,cL,cH=inputs['pricing-consumption'];p=law(inputs['pricing-probabilities']);m=(beta*c0/cL,beta*c0/cH);arrow=tuple(w*x for w,x in zip(p,m));safe=sum(arrow);risky=2*arrow[1];ret=(F(0),2/risky);mean=sum(w*x for w,x in zip(p,ret));out('arrow-prices',arrow);out('claim-prices',(safe,risky));out('risk-premium',mean-1/safe);left,right,vm,vr=hj(p,m,ret);out('risk-bound-sides',(left,right));eq((vm,vr),(F(27,100),F(25,27)));eq(left,right);eq(hj((F(1,2),F(1,2)),(1,1),(F(1,2),F(3,2)))[:2],(0,0))
    Qval=inputs['investment-Q'];n=inputs['investment-cash'];out('investment-unconstrained',invest(Qval));con=invest(Qval,n);out('investment-constrained',con);I,loan,mult,derivative=con;cost=I+I*I/2;eq(cost,n+loan);eq(loan,I/2);eq(Qval*I-loan-n,(Qval-1)*I-I*I/2)
    for q in (F(1,2),F(1),F(3,2),F(3)):
        opt=invest(q)
        for trial in (F(0),F(1,4),F(1),F(3)):need((q-1)*trial-trial*trial/2<=(q-1)*opt-opt*opt/2,'global investment boundary');count+=1
    lam,R,kappa=inputs['deposit'];rroot=rational_sqrt(R);c1,c2=solve(((lam,(1-lam)/R),(-rroot,F(1))),(F(1),(rroot-1)*kappa));storage=lam*c1;out('deposit-allocation',(c1,c2,storage));eq(R*(1-storage),(1-lam)*c2);need(c2>c1>1,'waiting and private-storage incentives');count+=1
    utility=lambda x:-1/(x+kappa);best=lam*utility(c1)+(1-lam)*utility(c2)
    for j in range(21):
        trial=F(j,20)/lam;late=R*(1-lam*trial)/(1-lam);need(lam*utility(trial)+(1-lam)*utility(late)<=best,'global insurance comparison');count+=1
    mu,var,risk,supply,C1,C2=inputs['dealer'];price,positions,active=dealers(mu,var,risk,supply,(C1,C2));out('dealer-price',price);out('dealer-holdings',positions);need(active==(True,False),'actual cap pattern');eq(sum(positions),supply);eq(price*positions[0],C1);eq(price*sum(positions),price*float(supply));need(price*positions[1]<float(C2),'second cap slack');count+=1
    beta,pL,h0,f0,hL,hH,fL,fH=inputs['international'];world=(h0+f0,hL+fL,hH+fH);p=(pL,1-pL);arrows=tuple(beta*w*world[0]/endow for w,endow in zip(p,world[1:]));wealthH=h0+arrows[0]*hL+arrows[1]*hH;total=world[0]+sum(q*e for q,e in zip(arrows,world[1:]));weight=wealthH/total;hc=tuple(weight*y for y in world);fc=tuple((1-weight)*y for y in world);out('international-arrows',arrows);out('international-H-trades',(hc[1]-hL,hc[2]-hH));eq(hc,(3,3,3));eq(fc,(1,1,1));eq(hc[0]+sum(q*x for q,x in zip(arrows,hc[1:])),wealthH);eq(fc[0]+sum(q*x for q,x in zip(arrows,fc[1:])),f0+arrows[0]*fL+arrows[1]*fH);eq(sum(q*(c-e) for q,c,e in zip(arrows,hc[1:],(hL,hH))),0)
    pL,mL,mH,E0,xL,xH=inputs['currency'];prob=(pL,1-pL);m=(mL,mH);X=(xL,xH);foreign=tuple(a*x for a,x in zip(m,X));em=sum(p*x for p,x in zip(prob,m));ef=sum(p*x for p,x in zip(prob,foreign));ex=sum(p*x for p,x in zip(prob,X));rd,rf=1/em,1/ef;cov=ef-em*ex;out('currency-safe-returns',(rd,rf));out('currency-forward',E0*rd/rf);out('currency-expected-spot',E0*ex);out('currency-covariance',cov);out('currency-premium',rf*ex-rd);eq(rf*ex-rd,-rd*rf*cov)
    for Z in ((1,0),(0,1),(2,3)):eq(sum(p*mm*E0*xx*z for p,mm,xx,z in zip(prob,m,X,Z))/E0,sum(p*mm*z for p,mm,z in zip(prob,foreign,Z)))
    K=inputs['sequence-K'];d=inputs['sequence-d'];M=tuple(tuple(F(i==j)-K[i][j] for j in range(2)) for i in range(2));y=solve(M,d);out('sequence-solution',y);out('sequence-cross',solve(M,(F(1),F(0)))[1]);norm=max(sum(abs(x) for x in row) for row in K);out('sequence-error',F(1,10000)/(1-norm));eq(tuple(y[i]-sum(K[i][j]*y[j] for j in range(2)) for i in range(2)),d)
    train=tuple(int(x) for x in inputs['training-counts']);hold=tuple(int(x) for x in inputs['holdout-counts']);p,q=counts(train);out('transition-estimates',(p,q));mean=p/(p+q);rho=1-p-q;out('transition-moments',(mean,rho));eq((mean*(1-rho),(1-mean)*(1-rho)),(p,q));fitted=score(hold,(p,q));constant=score(hold,(F(1,4),F(1,4)));out('holdout-log-scores',(fitted[0],constant[0]));out('holdout-brier',(fitted[1],constant[1]));need(constant[0]>fitted[0] and constant[1]<fitted[1],'prespecified holdout ranking');count+=1
    for truth,forecast in product((F(1,10),F(2,5),F(9,10)),repeat=2):eq(truth*(1-forecast)**2+(1-truth)*forecast**2,truth*(1-truth)+(forecast-truth)**2,'Brier proper loss')
    paid,equity,outside=clearing(inputs['network-e'],inputs['network-b'],inputs['network-A']);out('network-payments',paid);out('network-outside',outside);eq(equity,(0,0,0));eq(sum(inputs['network-e']),sum(equity)+outside);eq(max(map(sum,inputs['network-A'])),F(1,2))
    need(set(expected)==set(outputs),'all38 results independently reconstructed')
    for k,v in expected.items():eq(outputs[k],v,'display '+k)
    invalid=[lambda:num(True),lambda:num(float('inf')),lambda:literal('1/0'),lambda:literal('f(1)'),lambda:law((F(1,2),F(1,3))),lambda:law((0,1)),lambda:solve(((1,2),(2,4)),(1,2)),lambda:solve(((1,),),(1,2)),lambda:default_contract(-1,(2,5),(F(1,2),F(1,2)),F(1,4),F(5,4)),lambda:default_contract(1,(2,5),(F(1,2),F(1,2)),0,F(5,4)),lambda:hj((F(1,2),F(1,2)),(1,1),(1,1)),lambda:hj((F(1,2),F(1,2)),(0,1),(F(1,2),F(3,2))),lambda:invest(0),lambda:invest(2,-1),lambda:dealers(2,0,2,2,(1,4)),lambda:dealers(2,F(1,4),2,0,(1,4)),lambda:counts((0,0,2,1)),lambda:counts((2,3,2,1)),lambda:counts((2,1,2,True)),lambda:score((2,1,2,1),(0,F(1,2))),lambda:clearing((-1,0,0),(4,4,4),inputs['network-A']),lambda:clearing((1,0),(4,4),((0,1),(1,0)))];rejections=0
    for fn in invalid:
        try:fn()
        except ValueError:rejections+=1
        else:raise ValueError('invalid input accepted')
    for f,b in raw.items():need((root/f).read_bytes()==b,'runtime mutation')
    result={'volume':'v14','component':'exam-a-peer','status':'passed','comparisons':count,'rejected_inputs':rejections,'household_policies_enumerated':policies,'network_default_sets':8,'scored_prompts':20,'solutions':20,'domains':5,'total_points':100,'chapter_coverage':12,'input_markers':len(inputs),'result_markers':len(outputs),'runtime_files':6,'author_code_executed':False,'open_issues':[]};json.dumps(result,allow_nan=False);return result
if __name__=='__main__':check()
