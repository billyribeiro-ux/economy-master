"""Graduate macro-finance: original four-payload, quiet standard-library audit."""
import ast,json
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from itertools import product
from math import isfinite,log,sqrt
from pathlib import Path
FILES=('content/cross-assessments/parts/graduate-macro.html','scripts/check_graduate_macro.py','content/reviews/graduate-macro-sources.json','content/reviews/graduate-macro-author.json')
def need(ok,msg):
    if not ok:raise ValueError(msg)
def num(x):
    need(type(x) in (int,float,F) and isfinite(float(x)),'finite nonboolean number');return F(str(x)) if isinstance(x,float) else F(x)
def literal(s):
    def rec(n):
        if isinstance(n,ast.Constant):return num(n.value)
        if isinstance(n,(ast.Tuple,ast.List)):return tuple(rec(x) for x in n.elts)
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,(ast.USub,ast.UAdd)):return (-1 if isinstance(n.op,ast.USub) else 1)*rec(n.operand)
        if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Div):
            d=rec(n.right);need(d!=0,'zero divisor');return rec(n.left)/d
        raise ValueError('numeric syntax only')
    return rec(ast.parse(s.replace('−','-').rsplit('=',1)[-1].strip(),mode='eval').body)
def law(p):
    p=tuple(map(num,p));need(p and min(p)>=0 and sum(p)==1,'stochastic row');return p
def solve(M,b):
    n=len(b);need(n and len(M)==n and all(len(r)==n for r in M),'square system');a=[list(r)+[x] for r,x in zip(M,b)]
    for j in range(n):
        k=max(range(j,n),key=lambda i:abs(a[i][j]));need(a[k][j]!=0,'invertible system');a[j],a[k]=a[k],a[j];q=a[j][j];a[j]=[x/q for x in a[j]]
        for i in range(n):
            if i!=j:
                q=a[i][j];a[i]=[x-q*y for x,y in zip(a[i],a[j])]
    return tuple(r[-1] for r in a)
def stopping(P,x,beta,T):
    P=tuple(law(r) for r in P);x=tuple(map(num,x));beta=num(beta);need(len(P)==len(x)==2 and all(len(r)==2 for r in P) and min(x)>=0 and 0<beta<1 and type(T) is int and T>=0,'stopping domain');v=x;values=[v]
    for _ in range(T):v=tuple(max(x[i],beta*sum(P[i][j]*v[j] for j in range(2))) for i in range(2));values.append(v)
    return tuple(values)
def olg(k,t):
    k,t=map(num,(k,t));need(k>0 and 0<=t<1,'positive capital and tax domain');w=2*float(k)**(1/3);R=float(k)**(-2/3);nextk=float((1-t)/(1+t))*float(k)**(1/3);cy=(1-float(t))*w-nextk;nextR=nextk**(-2/3);nextw=2*nextk**(1/3);co=nextR*nextk+float(t)*nextw;return nextk,w,R,cy,co

def contract(primitives,n,g=0):
    I,Y,pH,pL,B,R=map(num,primitives);n,g=map(num,(n,g));need(I>0 and Y>0 and 0<=pL<pH<=1 and B>=0 and R>0 and 0<=n<=I and g>=0,'agency domain');d=(R*(I-n)-(1-pH)*g)/pH;residual=Y-d;ic=(pH-pL)*residual-B;participation=pH*residual-R*n
    return {'debt':d,'ic':ic,'participation':participation,'implemented':0<=d<=Y and ic>=0 and participation>=0,'lender_receipts':pH*d+(1-pH)*g,'reserve':g/R,'fiscal_payment':(1-pH)*g}

def portfolio(primitives,cap=None):
    y0,yL,yH,pL,qD,qF,xL,xH=map(num,primitives);p=(pL,1-pL);need(min(y0,yL,yH,qD,qF,xL,xH)>0 and 0<pL<1 and xL!=xH,'portfolio primitives');q=solve(((F(1),F(1)),(xL,xH)),(qD,qF));need(min(q)>0,'positive Arrow budget');wealth=y0+q[0]*yL+q[1]*yH;c0=wealth/2;c=(c0,p[0]*c0/q[0],p[1]*c0/q[1]);b,h=solve(((F(1),xL),(F(1),xH)),(c[1]-yL,c[2]-yH))
    if cap is None or h<=num(cap):return q,(b,h),c,F(0)
    cap=num(cap);lo=max(-float(yL+xL*cap),-float(yH+xH*cap));hi=float((y0-qF*cap)/qD);need(lo<hi,'positive feasible constrained portfolio')
    for _ in range(100):
        bfloat=(lo+hi)/2;cc=(float(y0-qF*cap)-float(qD)*bfloat,float(yL+xL*cap)+bfloat,float(yH+xH*cap)+bfloat);deriv=-float(qD)/cc[0]+float(p[0])/cc[1]+float(p[1])/cc[2]
        if deriv>0:lo=bfloat
        else:hi=bfloat
    b=(lo+hi)/2;cc=(float(y0-qF*cap)-float(qD)*b,float(yL+xL*cap)+b,float(yH+xH*cap)+b);mu=-float(qF)/cc[0]+float(p[0]*xL)/cc[1]+float(p[1]*xH)/cc[2];return q,(b,float(cap)),cc,mu

def growth(A,beta,k0,c0):
    A,beta,k0,c0=map(num,(A,beta,k0,c0));need(A>0 and 0<beta<1 and k0>0 and 0<c0<=A*(1-beta)*k0,'feasible positive Euler path');return [(A**t*(k0-c0*(1-beta**t)/(A*(1-beta))),c0*(beta*A)**t) for t in range(12)]
def fiscal_transfer(primitive,restricted=True,policy=True):
    p0,p1,h0,h1,tau=map(num,primitive);need(min(p0,p1,h0,h1)>0 and 0<=tau<min(p1,h1),'transfer domain');t=tau if policy else F(0);sP=(p0+t-p1+t)/2;sP=max(F(0),sP) if restricted else sP;sH=(h0+t-h1+t)/2;cP=(p0+t-sP,p1-t+sP);cH=(h0+t-sH,h1-t+sH);net=sP+sH-2*t;return (sP,sH),cP,cH,net

def weak_bounds(amin,amax,bmin,bmax):
    amin,amax,bmin,bmax=map(num,(amin,amax,bmin,bmax));need(0<amin<=amax and bmin<0<bmax,'positive numerator and crossing denominator');return amin/bmin,amin/bmax

class HTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.stack=[];self.active=[];self.inputs={};self.outputs={};self.ids=[];self.prompts={};self.answers=[];self.rubrics={};self.domains={};self.sources={};self.links=set();self.headings=[]
    def handle_starttag(self,t,attrs):
        d=dict(attrs);need(len(d)==len(attrs),'unique attributes')
        if 'id' in d:need(d['id'].startswith('graduate-macro') and d['id'] not in self.ids,'prefixed unique IDs');self.ids.append(d['id'])
        need(t!='h1','no new h1')
        if t=='h2':self.headings.append(d.get('id'))
        if 'data-domain' in d:self.domains[(d['data-form'],d['data-domain'])]=[int(d['data-domain-points']),[]]
        if 'data-points' in d:
            form,domain=next((a['data-form'],a['data-domain']) for tag,a in reversed(self.stack) if 'data-domain' in a);self.prompts[d['id']]=int(d['data-points']);self.domains[(form,domain)][1].append(d['id'])
        if 'data-solution-for' in d:
            need(any(tag=='details' and 'solutions' in a.get('class','').split() for tag,a in self.stack),'solution enclosure');self.answers.append(d['data-solution-for'])
        if 'data-rubric-points' in d:
            key=next(a['data-solution-for'] for tag,a in reversed(self.stack) if 'data-solution-for' in a);need(key not in self.rubrics,'one rubric each');self.rubrics[key]=tuple(int(x) for x in d['data-rubric-points'].split(','))
        if 'data-source' in d:self.sources[d['data-source']]=d['href']
        if t=='a':self.links.add(d.get('href',''))
        for attr,dest in (('data-input',self.inputs),('data-calc',self.outputs)):
            if attr in d:
                key=d[attr];need(key not in dest,'unique numerical marker');dest[key]='';self.active.append((dest,key,len(self.stack)))
        if t not in ('br','hr','img','meta','link','input'):self.stack.append((t,d))
    def handle_data(self,s):
        for dest,k,n in self.active:dest[k]+=s
    def handle_endtag(self,t):
        need(self.stack and self.stack[-1][0]==t,'balanced HTML');self.stack.pop();self.active=[x for x in self.active if x[2]<len(self.stack)]

def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1];raw={f:(root/f).read_bytes() for f in FILES};doc=HTML();doc.feed(raw[FILES[0]].decode());need(not doc.stack,'closed markup');author=json.loads(raw[FILES[3]]);source=json.loads(raw[FILES[2]]);targets=['graduate-macro-'+f+str(i).zfill(2) for f in ('a','b') for i in range(1,21)];need(list(doc.prompts)==doc.answers==targets and set(doc.rubrics)==set(targets),'40 exact prompt/solution/rubric pairs');need(doc.headings==['graduate-macro-a','graduate-macro-b'],'two form headings');need(all(doc.prompts[k]==sum(doc.rubrics[k])==5 and min(doc.rubrics[k])>0 for k in targets),'40 additive five-point parts');need(len(doc.domains)==10 and all(points==20 and len(ids)==4 for points,ids in doc.domains.values()),'five20point problems per form');need({'v13-c09.html','v12-c03.html','v12-c06.html'}<=doc.links,'scored cross-volume prerequisites');need(set(author['exact_prompt_review'])==set(targets),'all40 proof audits');need(doc.sources=={s['id']:s['url'] for s in source['sources']},'source routes');need(all(s['prior_inspector'] and s['scope'] and s['limits'] for s in source['sources']),'bounded source provenance')
    domains={'dynamic_optimality_and_distribution','aggregate_equilibrium_and_policy','asset_prices_and_financial_constraints','international_risk_and_funding','numerical_identification_and_research'}
    need(set(doc.domains)=={(f,d) for f in ('a','b') for d in domains},'exact five domain names in each form')
    bind=author['payload_bindings'];need(len(bind)==3 and {x['path'] for x in bind}==set(FILES[:3]),'three nonself bindings')
    for b in bind:need((b['bytes'],b['sha256'])==(len(raw[b['path']]),sha256(raw[b['path']]).hexdigest()),'exact author binding')
    inp={k:literal(v) for k,v in doc.inputs.items()};shown={k:literal(v) for k,v in doc.outputs.items()};expected={};comparisons=0
    def eq(a,b,label='identity',tol=8e-10):
        nonlocal comparisons
        if isinstance(a,(tuple,list)) or isinstance(b,(tuple,list)):
            need(isinstance(a,(tuple,list)) and isinstance(b,(tuple,list)) and len(a)==len(b),label+' shape')
            for x,y in zip(a,b):eq(x,y,label,tol)
        else:comparisons+=1;need(isfinite(float(a)) and isfinite(float(b)) and abs(float(a)-float(b))<=tol*max(1,abs(float(b))),label+str((a,b)))
    def out(k,v):expected[k]=v
    intended={'a-stop-P':((F(3,4),F(1,4)),(F(1,2),F(1,2))),'a-stop-payoff':(1,4),'a-stop-beta':F(4,5),'a-olg-tax':(0,F(1,3)),'a-olg-k0':1,'a-agency':(10,20,F(4,5),F(2,5),3,F(11,10)),'a-portfolio':(2,1,3,F(1,2),1,F(17,16),2,F(1,2)),'a-moments':(5,3,2,3),'b-growth':(3,F(1,2),1,1),'b-transfer':(1,4,4,1,F(1,2)),'b-bad-prices':(1,3),'b-international':(2,3,4,6,10,1),'b-causal':(1,2,3)};need(set(inp)==set(intended),'13 primitive groups')
    for k,v in intended.items():eq(inp[k],v,'HTML input '+k)
    P=inp['a-stop-P'];x=inp['a-stop-payoff'];beta=inp['a-stop-beta'];values=stopping(P,x,beta,2);out('a-stop-values',values);m1=P[0][1];m2L=P[0][0]*P[0][0];m2H=P[0][0]*P[0][1];etime=m1+2*(m2L+m2H);ev=beta*m1*x[1]+beta**2*(m2L*x[0]+m2H*x[1]);out('a-stop-distribution',(m1,m2L,m2H,etime,ev));eq(m1+m2L+m2H,1);eq(ev,values[-1][0]);nominal=m1*x[1]+m2L*x[0]+m2H*x[1];eq(nominal+(4-nominal),4);eq(nominal,F(37,16))
    opt=[]
    for exercise in product((False,True),repeat=2):
        M=tuple(tuple(F(i==j)-(F(0) if exercise[i] else beta*P[i][j]) for j in range(2)) for i in range(2));rhs=tuple(x[i] if exercise[i] else F(0) for i in range(2));V=solve(M,rhs);bell=tuple(max(x[i],beta*sum(P[i][j]*V[j] for j in range(2))) for i in range(2))
        if V==bell:opt.append((exercise,V))
    need(len(opt)==1 and opt[0][0]==(False,True),'all four infinite stopping policies');V=opt[0][1];out('a-stop-infinite-value',V);q=P[0][1];wait=P[0][0];edisc=beta*q/(1-beta*wait);out('a-stop-infinite-time',(1/q,edisc,x[1]*edisc));eq(V[0],x[1]*edisc)
    for n in range(1,8):eq(sum(wait**(t-1)*q for t in range(1,n+1))+wait**n,1,'cohort survival')
    taxes=inp['a-olg-tax'];k0=inp['a-olg-k0'];coeff=tuple((1-t)/(1+t) for t in taxes);out('a-olg-coefficients',coeff);t=taxes[1];ks=float(coeff[1])**1.5;kn,w,R,cy,co=olg(ks,t);out('a-olg-stationary',(ks,R,w,cy,co));eq(kn,ks);eq(cy+co+kn,3*ks**(1/3));eq((1-float(t))*w-kn,cy)
    k1,w0,R0,cy0,co1=olg(k0,t);old=R0*float(k0)+float(t)*w0;out('a-olg-transition',(old,k1,cy0));out('a-olg-welfare',(log(cy0*co1),log(cy*co)));eq(old+cy0+k1,3*float(k0)**(1/3));eq(float(t)*w0,old-R0*float(k0))
    for initial in (.01,.2,2,20):
        k=initial
        for j in range(12):
            nxt,w,r,c1,c2=olg(k,t);eq(log(nxt)-log(ks),(log(k)-log(ks))/3,'OLG contraction');futurep=float(t)*2*nxt**(1/3);futureR=nxt**(-2/3);eq(1/c1,futureR/c2,'private Euler');eq(c2,futureR*nxt+futurep);k=nxt
    I,Y,pH,pL,B,R=inp['a-agency'];dmax=Y-B/(pH-pL);threshold=I-pH*dmax/R;out('a-agency-threshold',threshold);ct=contract(inp['a-agency'],1);out('a-agency-contract',(ct['debt'],ct['ic'],ct['lender_receipts'],ct['participation']));need(ct['implemented'],'n1 IC');eq(ct['debt']+Y-ct['debt'],Y);bad=contract(inp['a-agency'],0);need(not bad['implemented'] and bad['ic']<0,'inconsistent high-effort contract');eq(pL*bad['debt'],F(11,2));eq(contract(inp['a-agency'],threshold)['ic'],0)
    guar=contract(inp['a-agency'],0,5);out('a-guaranteed-debt',(guar['debt'],guar['ic'],guar['lender_receipts']));out('a-guarantee-funding',(guar['reserve'],guar['fiscal_payment'],guar['fiscal_payment']/R));need(guar['implemented'] and not contract(inp['a-agency'],0,F(499,100))['implemented'],'guarantee sharpness');eq(R*guar['reserve'],5);eq(pH*(Y-guar['debt']),pL*(Y-guar['debt'])+B)
    q,hold,c,mu=portfolio(inp['a-portfolio']);out('a-portfolio-arrows',q);out('a-portfolio-unconstrained',(*hold,*c));q2,h2,c2,mu2=portfolio(inp['a-portfolio'],1);out('a-portfolio-cap',(h2[0],*c2,mu2));need(mu2>0 and min(c2)>0,'binding cap global tangent');eq(-1/c2[0]+.5/c2[1]+.5/c2[2],0);eq(128*h2[0]**2+564*h2[0]+477,0)
    y0,yL,yH,pL,qD,qF,xL,xH=inp['a-portfolio'];foreign=(4+qD*hold[0]+qF*hold[1],4-hold[0]-xL*hold[1],4-hold[0]-xH*hold[1]);out('a-portfolio-foreign',foreign);utility=lambda cs:log(cs[0])+float(pL)*log(cs[1])+float(1-pL)*log(cs[2]);out('a-portfolio-loss',utility(c)-utility(c2))
    for hh,cc in ((hold,c),(h2,c2)):
        ff=(4+float(qD)*float(hh[0])+float(qF)*float(hh[1]),4-float(hh[0])-float(xL)*float(hh[1]),4-float(hh[0])-float(xH)*float(hh[1]));need(min(ff)>0,'counterparty consumption');eq(tuple(float(a)+b for a,b in zip(cc,ff)),(6,5,7))
    for bb,hh in product((-2.,-1.,0.),(-.5,0.,.5,1.)):
        cs=(2-bb-float(qF)*hh,1+bb+2*hh,3+bb+.5*hh)
        if min(cs)>0:need(utility(cs)<=utility(c2)+1e-12,'constrained global witness');comparisons+=1
    vz,zy,wz,wy=inp['a-moments'];naive=zy/vz;theta=wy/wz;kappa=1-1/theta;out('a-iv',(naive,theta,kappa));a=(wy,F(9,5));b=(wz,F(1));gmm=sum(x*y for x,y in zip(a,b))/sum(y*y for y in b);mom=tuple(x-gmm*y for x,y in zip(a,b));out('a-overidentified',(gmm,*mom,sum(x*x for x in mom)));eq(sum(y*x for x,y in zip(mom,b)),0)
    d=F(1,5);truth=d/(1-kappa);wrong=d/(1-F(2,5));res=wrong-d-kappa*wrong;out('a-operator',(truth,wrong,res,res/(1-kappa)));eq(abs(wrong-truth),abs(res)/(1-kappa));out('a-exclusion-pairs',((F(1),F(1,2)),(F(3,2),F(0))))
    A,beta,k0,c0=inp['b-growth'];path=growth(A,beta,k0,c0);out('b-growth-report-t2',path[2]);optimal_c=A*(1-beta)*k0;out('b-growth-optimal',(beta*A*k0,optimal_c,1/(1-beta)));shadowlimit=A*k0/c0-1/(1-beta);unused=k0-c0/(A*(1-beta));loss=log(optimal_c/c0)/float(1-beta);out('b-growth-loss',(shadowlimit,unused,loss));out('b-distribution-gap',(log(F(1,2))+log(F(3,2)))/(2*float(1-beta)))
    for t,(k,curr) in enumerate(path[:-1]):eq(curr+path[t+1][0],A*k);eq(path[t+1][1],beta*A*curr);eq(beta**t*path[t+1][0]/curr,shadowlimit+beta**t/(1-beta)*beta,'Euler shadow formula')
    base=fiscal_transfer(inp['b-transfer'],True,False);policy=fiscal_transfer(inp['b-transfer'],True,True);out('b-transfer-baseline',(*base[0],*base[1],*base[2]));out('b-transfer-policy',(*policy[0],policy[3],*policy[1]));out('b-transfer-gain',log(policy[1][0]*policy[1][1]/(base[1][0]*base[1][1])));before=fiscal_transfer(inp['b-transfer'],False,False);after=fiscal_transfer(inp['b-transfer'],False,True);out('b-transfer-unrestricted-saving',(*before[0],*after[0]));eq(before[1:3],after[1:3]);eq(before[3],after[3])
    for model in (base,policy,before,after):
        savings,cp,ch,net=model;cf=(2+net,2-net);need(min(cf)>0,'foreign financing');eq(cp[0]+ch[0]+cf[0],7);eq(cp[1]+ch[1]+cf[1],7)
    qs,qx=inp['b-bad-prices'];arrows=solve(((F(1),F(1)),(F(0),F(2))),(qs,qx));cost=qs-qx/2;out('b-price-arbitrage',(*arrows,cost,F(1),F(0)));need(arrows[0]<0 and cost<0,'explicit no-arbitrage violation');out('b-long-only',(0,0));debt=(1,2);equity=(0,1);firm=(1,3);values=[]
    for qp in (arrows,(F(1,2),F(1,2))):
        vals=tuple(sum(q*x for q,x in zip(qp,pay)) for pay in (debt,equity,firm));eq(vals[0]+vals[1],vals[2]);values.append(vals)
    out('b-firm-values',tuple(values));price=values[1][0];returns=tuple(F(x)/price for x in debt);mean=sum(returns)/2;out('b-debt-returns',(2/price,*returns,mean,mean-1));eq(mean,1)
    E0,E1,assets,liabs,domestic,loan=inp['b-international'];nfa0=E0*(assets-liabs);nfa1=E1*(assets-liabs);out('b-valuation',(nfa0,domestic+nfa0,nfa1,domestic+nfa1,nfa1-nfa0,0));afterdeposit=(assets+loan,liabs+loan);nfadeposit=E1*(afterdeposit[0]-afterdeposit[1]);nfaimport=E1*(assets-liabs-loan);out('b-gross-flows',(*afterdeposit,nfadeposit,assets,liabs+loan,nfaimport,-E1*loan));eq(nfaimport-nfa0,(nfa1-nfa0)-E1*loan)
    endowD,endowF=F(10),F(2);cD=endowD+assets-liabs-loan;cF=endowF+liabs+loan-assets;out('b-foreign-resources',(cD,cF,endowD+assets-liabs,endowF+liabs-assets));eq(cD+cF,endowD+endowF);eq(loan+(2-loan),2)
    hedge=liabs-assets;spots=(F(1),F(3));pays=tuple(hedge*(spot-E0) for spot in spots);worth=tuple(domestic+(assets-liabs)*spot+pay for spot,pay in zip(spots,pays));out('b-hedge',(*pays,*worth,max(abs(x) for x in pays)));eq(worth[0],worth[1]);eq(hedge,(liabs+loan-assets)-loan)
    first,credit,directU=inp['b-causal'];zy=first*credit;uY=credit+directU;varC=first*first+1;covCY=first*zy+uY;out('b-causal-slopes',(covCY/varC,zy,zy/first));reg=solve(((F(1),first),(first,varC)),(zy,covCY));out('b-conditioned',reg);examples=tuple((tt,zy-first*tt,uY-tt) for tt in (F(2),F(1),F(0)));out('b-equivalence-examples',examples)
    for tt,gamma,delta in examples:eq(tt*first+gamma,zy);eq(tt+delta,uY)
    bounds=weak_bounds(F(3,200),F(1,40),F(-1,200),F(1,40));out('b-weak-endpoints',bounds)
    for tt in (F(-100),F(-3),F(3,5),F(2),F(100)):
        aa=F(3,200);bb=aa/tt;need(F(-1,200)<=bb<=F(1,40) and bb!=0,'ratio branch attainable');eq(aa/bb,tt)
    need(set(expected)==set(shown),'all displayed result groups: '+str(set(expected)^set(shown)))
    for k,v in expected.items():eq(shown[k],v,'HTML result '+k)
    invalid=[lambda:num(True),lambda:num(float('nan')),lambda:literal('1/0'),lambda:literal('f(1)'),lambda:law((F(1,3),F(1,3))),lambda:law((-1,2)),lambda:solve(((1,2),(2,4)),(1,2)),lambda:stopping(P,x,1,2),lambda:stopping(P,x,F(4,5),True),lambda:olg(0,F(1,3)),lambda:olg(1,1),lambda:contract(inp['a-agency'],-1),lambda:contract(inp['a-agency'],1,-1),lambda:portfolio((2,1,3,F(1,2),1,3,2,F(1,2))),lambda:growth(3,F(1,2),1,2),lambda:growth(3,1,1,1),lambda:fiscal_transfer((1,4,4,1,2)),lambda:weak_bounds(0,1,-1,1),lambda:weak_bounds(1,2,0,1)];rejected=0
    for fn in invalid:
        try:fn()
        except ValueError:rejected+=1
        else:raise ValueError('invalid primitive accepted')
    for f,b in raw.items():need((root/f).read_bytes()==b,'runtime mutation')
    result={'assessment':'graduate-qualifying','field':'macro','status':'passed','forms':2,'problems':10,'solutions':40,'points_per_form':100,'domains_per_form':5,'input_groups':len(inp),'result_groups':len(shown),'comparisons':comparisons,'rejected_inputs':rejected,'runtime_files':4,'open_issues':[]};json.dumps(result,allow_nan=False);return result
if __name__=='__main__':check()
