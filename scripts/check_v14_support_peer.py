"""Separate V14 support reconstruction. Never executes/imports author checker."""
import ast,json
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from itertools import product
from math import isfinite,isqrt,log,sqrt
from pathlib import Path
AUTHOR=('content/assessments/parts/v14-support-opening.html','content/assessments/parts/v14-support-closing.html','scripts/check_v14_support.py','content/reviews/v14-support-sources.json','content/reviews/v14-support-author.json')
FILES=AUTHOR+('scripts/check_v14_support_peer.py','content/reviews/v14-support-peer.json')
def need(ok,msg):
    if not ok:raise ValueError(msg)
def number(x):
    need(type(x) in (int,float,F) and isfinite(float(x)),'finite nonboolean scalar');return F(str(x)) if isinstance(x,float) else F(x)
def parsed(s):
    def read(n):
        if isinstance(n,ast.Constant):return number(n.value)
        if isinstance(n,(ast.Tuple,ast.List)):return tuple(read(x) for x in n.elts)
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,(ast.USub,ast.UAdd)):return (-1 if isinstance(n.op,ast.USub) else 1)*read(n.operand)
        if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Div):
            q=read(n.right);need(q!=0,'zero denominator');return read(n.left)/q
        raise ValueError('numeric grammar')
    return read(ast.parse(s.replace('−','-').strip(),mode='eval').body)
class Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.stack=[];self.active=[];self.mark={};self.prompts={};self.points={};self.answers={};self.ids=[];self.sources={};self.links=set()
    def handle_starttag(self,t,attrs):
        d=dict(attrs)
        if 'id' in d:need(d['id'] not in self.ids,'duplicate ID');self.ids.append(d['id'])
        if 'data-points' in d:
            k=d['id'];self.points[k]=int(d['data-points']);self.prompts[k]='';self.active.append((self.prompts,k,len(self.stack)))
        if 'data-solution-for' in d:
            need(any(tag=='details' and 'solutions' in a.get('class','').split() for tag,a in self.stack),'answer enclosure');k=d['data-solution-for'];need(k not in self.answers,'duplicate solution');self.answers[k]='';self.active.append((self.answers,k,len(self.stack)))
        if 'data-check' in d:
            k=d['data-check'];need(k not in self.mark,'duplicate result');self.mark[k]='';self.active.append((self.mark,k,len(self.stack)))
        if 'data-source' in d:self.sources[d['data-source']]=d['href']
        if t=='a':self.links.add(d.get('href',''))
        if t not in ('br','hr','img','meta','link','input'):self.stack.append((t,d))
    def handle_data(self,s):
        for dest,k,depth in self.active:dest[k]+=s
    def handle_endtag(self,t):
        need(self.stack and self.stack[-1][0]==t,'HTML nesting');self.stack.pop();self.active=[a for a in self.active if a[2]<len(self.stack)]
def linear(M,b):
    n=len(b);A=[list(r)+[x] for r,x in zip(M,b)]
    for j in range(n):
        i=next((i for i in range(j,n) if A[i][j]),None);need(i is not None,'nonsingular system');A[j],A[i]=A[i],A[j];q=A[j][j];A[j]=[x/q for x in A[j]]
        for i in range(n):
            if i!=j:
                q=A[i][j];A[i]=[x-q*y for x,y in zip(A[i],A[j])]
    return tuple(r[-1] for r in A)
def two_date(y,R,b):
    y=tuple(map(number,y));R=number(R);b=number(b);need(len(y)==2 and min(y)>0 and R>0 and b>0,'household domain')
    # Solve both PV budget and the log FOC c1=beta*R*c0.
    c=linear(((F(1),1/R),(-b*R,F(1))),(y[0]+y[1]/R,F(0)))
    return c,y[0]-c[0]
def state_price(p,m,x):
    p,m,x=[tuple(map(number,a)) for a in (p,m,x)];need(len(p)==len(m)==len(x)>0 and min(p)>0 and sum(p)==1 and min(m)>0,'state price domain')
    mean=lambda a:sum(pp*aa for pp,aa in zip(p,a));q=mean(tuple(a*b for a,b in zip(m,x)));need(q>0,'positive claim price');rf=1/mean(m);returns=tuple(a/q for a in x);em=mean(m);er=mean(returns)
    return dict(price=q,safe=rf,mean=er,premium=er-rf,cov=q-em*mean(x),vm=mean(tuple((a-em)**2 for a in m)),vr=mean(tuple((a-er)**2 for a in returns)))
def bank_sale(A,D,loss,L):
    A,D,loss,L=map(number,(A,D,loss,L));need(A>0 and D>=0 and 0<=loss<A-D and L>1,'solvent bank domain');n=A-loss-D;post=A-loss;z=max(F(0),post-L*n);need(z<=D,'sale repayment feasibility');return post/n,z,(post-z,D-z,n)
def search(r,s,k,eta,b,y):
    r,s,k,eta,b,y=map(number,(r,s,k,eta,b,y));need(r>0 and s>0 and k>0 and 0<eta<1 and y>b>=0,'active search domain')
    aa=k*eta;bb=k*(r+s);cc=-(1-eta)*(y-b);disc=bb*bb-4*aa*cc;sn=isqrt(disc.numerator);sd=isqrt(disc.denominator);need(sn*sn==disc.numerator and sd*sd==disc.denominator,'rational example root');x=(-bb+F(sn,sd))/(2*aa);theta=x*x;u=s/(s+x);v=theta*u;J=k*x;X=eta*J/(1-eta);w=y-(r+s)*J;U=(b+x*X)/r;flow=y*(1-u)+b*u-k*v
    return theta,x,1/x,u,v,J,X,w,U,flow

def collateral(k):
    k=number(k);need(0<=k<1,'cap domain');y,yp,D,R,beta,nu,W=map(F,(2,5,1,1,1,1,4));a=y-D
    # Solve the active linear price-cap equation, then independently test fixed-price household FOC.
    bound=k*(y+nu*a)/(R-k*nu);unconstrained=(yp-beta*R*a)/(R*(1+beta));ell=min(bound,unconstrained);c=(a+ell,yp-R*ell);p=c;private_wealth=(a+p[0],yp+p[1]);private_u=(private_wealth[1]-beta*R*private_wealth[0])/(R*(1+beta));private_cap=k*(y+p[0])/R
    need(min(private_u,private_cap)==ell,'private optimum at fixed equilibrium prices');return ell,c,W+D-ell

def network(cash,nominal,A):
    cash,nominal=tuple(map(number,cash)),tuple(map(number,nominal));A=tuple(tuple(map(number,r)) for r in A);n=len(cash)
    need(n>0 and len(nominal)==len(A)==n and all(len(r)==n for r in A),'network dimensions');need(min(cash)>=0 and min(nominal)>0 and all(min(r)>=0 and sum(r)<1 for r in A),'outside leakage domain');sol=[]
    for default in product((False,True),repeat=n):
        M=[];rhs=[]
        for i in range(n):
            M.append([F(i==j)-A[j][i] if default[i] else F(i==j) for j in range(n)]);rhs.append(cash[i] if default[i] else nominal[i])
        p=linear(M,rhs);resources=tuple(cash[i]+sum(A[j][i]*p[j] for j in range(n)) for i in range(n))
        if all(p[i]==min(nominal[i],resources[i]) and p[i]>=0 for i in range(n)):
            if p not in sol:sol.append(p)
    need(len(sol)==1,'unique network clearing');p=sol[0];equity=tuple(cash[i]+sum(A[j][i]*p[j] for j in range(n))-p[i] for i in range(n));outside=sum((1-sum(A[i]))*p[i] for i in range(n));return p,equity,outside,max(map(sum,A))

def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1];raw={p:(root/p).read_bytes() for p in FILES};doc=Text();doc.feed(raw[AUTHOR[0]].decode()+'\n'+raw[AUTHOR[1]].decode());need(not doc.stack,'balanced fragments');record=json.loads(raw[FILES[-1]]);ar=json.loads(raw[AUTHOR[-1]]);sources=json.loads(raw[AUTHOR[3]])
    targets={**{'v14-d'+str(i):5 for i in range(1,9)},**{'v14-o'+str(i):4 for i in range(1,6)},**{'v14-r'+str(i):10 for i in range(1,6)}};need(doc.points==targets and set(doc.answers)==set(targets),'18 exact pairings/points');need(set(record['exact_prompt_review'])==set(targets),'full peer review coverage');need(set(ar['exact_prompt_audit'])==set(targets),'author audit coverage');need(all('Rubric ('+str(p)+' points)' in doc.answers[k] for k,p in targets.items()),'visible rubric labels');need(all('v14-c'+str(i).zfill(2)+'.html' in doc.links for i in range(1,13)),'12 learning routes');need('curriculum.html#v15-c01' in doc.links,'planned successor route')
    need(doc.sources=={s['id']:s['url'] for s in sources['sources']},'exact source routes')
    for s in sources['sources']:need(s['checked'] and 'prior' in s['verification'] and s['limits'],'source reuse attribution')
    for rec,paths in ((ar,AUTHOR[:4]),(record,FILES[:-1])):
        bindings=rec['payload_bindings'];need({b['path'] for b in bindings}==set(paths) and len(bindings)==len(paths),'exact nonself bindings')
        for b in bindings:need((b['bytes'],b['sha256'])==(len(raw[b['path']]),sha256(raw[b['path']]).hexdigest()),'binding '+b['path'])
    # Visible primitive clauses are checked independently of the answer markers.
    clauses={'v14-d1':['incomes(10,121/10)','return11/10','log c₀+log c₁'],'v14-d2':['4x−x²','0≤x≤1'],'v14-d3':['((4/5,1/5),(3/10,7/10))','incomes are(1,3)'],'v14-d4':['m=(4/5,6/5)','X=(3,1)'],'v14-d5':['assets120','debt100','loss10','assets/equity to5'],'v14-d6':['Ten independent Bernoulli','three successes'],'v14-d7':['B₀=10','s₁=3','B₂=0'],'v14-d8':['T(x)=1/5+3x/5','x̂=3/5'],'v14-o1':['wealth fixed forever','equal probabilities','levels0 and1'],'v14-o2':['diag(3/2,1/2)','no predetermined'],'v14-o3':['capital1','goods3','I+I²/2≤3','6K−K²/2','discount1/2'],'v14-o4':['domestic currency per foreign unit','foreign payoff be Z'],'v14-o5':['residual below10⁻¹⁰','welfare recommendation'],'v14-r1':['production2√k','discount4/5','k₀=1','ε=1/4','residual1/25','[0,2]'],'v14-r2':['r=1/10,s=1/5','κ=2/5','η=1/2','b=1/5','y=61/125'],'v14-r3':['(1/4,3/4)','SDF(2,2/3)','X=(1,3)','asset50','debt65','cost10','adds20'],'v14-r4':['β=ν=R=1','y₀=2,y₁=5','D=1','W=4','κ=1/5 and1/10'],'v14-r5':['(4,4,4)','(1,1,1)','A12=1/2,A23=1/2','cash loss1/5','g1=a+b,g2=2a+2b','g3=a−b=.04']}
    for k,parts in clauses.items():
        for part in parts:need(part in doc.prompts[k],'visible primitive '+k+': '+part)
    count=0;rejections=0;expected={}
    def eq(x,y,label='comparison',tol=0):
        nonlocal count
        if isinstance(x,(tuple,list)) or isinstance(y,(tuple,list)):
            need(isinstance(x,(tuple,list)) and isinstance(y,(tuple,list)) and len(x)==len(y),label+' shape')
            for a,b in zip(x,y):eq(a,b,label,tol)
        else:count+=1;need(abs(x-y)<=tol if tol else x==y,label+str((x,y)))
    def out(k,v):expected[k]=v
    cons,saving=two_date((10,F(121,10)),F(11,10),1);out('d1-consumption',cons);out('d1-saving',saving);eq(cons[0]+cons[1]/F(11,10),10+F(121,10)/F(11,10));eq(-saving*F(11,10),F(121,10)-cons[1])
    for c0 in (F(1),F(5),F(10),F(15),F(20)):
        c1=F(11,10)*(21-c0);need(log(c0)+log(c1)<=log(cons[0])+log(cons[1]),'two-date global witness');count+=1
    B=F(1);x=min(F(2),B);obj=lambda x:4*x-x*x;out('d2-choice-value-multiplier',(x,obj(x),4-2*x));eq((obj(B+F(1,100))-obj(B-F(1,100)))/F(2,100),4-2*B)
    P=((F(4,5),F(1,5)),(F(3,10),F(7,10)));w=(F(1),F(0));w1=tuple(sum(w[i]*P[i][j] for i in range(2)) for j in range(2));w2=tuple(sum(w1[i]*P[i][j] for i in range(2)) for j in range(2));stat=linear(((P[0][0]-1,P[1][0]),(F(1),F(1))),(F(0),F(1)));out('d3-probabilities',(w1[1],w2[1],stat[1]));out('d3-income',stat[0]+3*stat[1])
    price=state_price((F(1,2),F(1,2)),(F(4,5),F(6,5)),(3,1));out('d4-price',price['price']);out('d4-returns',(price['mean'],price['premium']));out('d4-cov',price['cov']);eq(price['safe'],1)
    lev,sales,final=bank_sale(120,100,10,5);out('d5-leverage',lev);out('d5-sales',sales);out('d5-final',final);eq(final[0]-final[1],final[2]);eq(final[0]/final[2],5)
    n,k=10,3;phat=F(k,n);out('d6-mle',phat);out('d6-var',phat*(1-phat)/n);eq(k/phat-(n-k)/(1-phat),0)
    R=F(11,10);debt0=10;s1=3;debt1=R*debt0-s1;s2=R*debt1;out('d7-debt-surplus',(debt1,s2));out('d7-backing',s1/R+s2/R**2);eq(debt1*R-s2,0)
    a,rho,guess=F(1,5),F(3,5),F(3,5);fixed=a/(1-rho);res=abs(guess-a-rho*guess);out('d8-fixed',fixed);out('d8-residual',res);out('d8-bound',res/(1-rho));eq(abs(guess-fixed),res/(1-rho))
    need(doc.mark['o1-invariant']=='(t/2,t/2,(1−t)/2,(1−t)/2)' and doc.mark['o2-path']=='(0,(1/2)ᵗb)','symbolic family markers')
    Q=((F(1,2),F(1,2),0,0),)*2+((0,0,F(1,2),F(1,2)),)*2
    for t in (F(0),F(1,3),F(2,3),F(1)):
        w=(t/2,t/2,(1-t)/2,(1-t)/2);eq(tuple(sum(w[i]*Q[i][j] for i in range(4)) for j in range(4)),w);eq(sum(w),1)
    for t in range(8):
        b=F(-3);eq(F(1,2)*F(1,2)**t*b,F(1,2)**(t+1)*b)
    I=(F(1,2)*(6-1)-1)/(1+F(1,2));K=1+I;cost=I+I*I/2;pay=6*K-K*K/2;q=F(1,2)*(6-K);out('o3-values',(I,3-cost,pay,q,F(1,2)*pay/K));eq(q,1+I);need(cost<=3,'prefunded investment');count+=1
    for Ialt in (F(0),F(1,2),F(3,2)):
        cc=Ialt+Ialt*Ialt/2;kk=1+Ialt;need(cc<=3 and -cc+(6*kk-kk*kk/2)/2<=-cost+pay/2,'concave investment witness');count+=1
    beta,alpha,A,k=F(4,5),F(1,2),F(2),F(1);coef=alpha/(1-alpha*beta);share=beta*coef/(1+beta*coef);y=A;out('r1-growth',(share,share*y,(1-share)*y));epsilon=F(1,4);out('r1-distribution-bound',F(1,25)/epsilon)
    k=1.
    for T in range(25):
        y=2*sqrt(k);kp=float(share)*y;c=(1-float(share))*y;cp=(1-float(share))*2*sqrt(kp);eq(1/c,float(beta)/(sqrt(kp)*cp),'growth Euler',1e-12);eq(float(beta)**T*kp/c,float(beta)**T*float(share/(1-share)),'shadow tail',1e-12);k=kp
    z=search(F(1,10),F(1,5),F(2,5),F(1,2),F(1,5),F(61,125));out('r2-market',z[:5]);out('r2-flow',z[-1]);theta,f,q,u,v,J,X,w,U,flow=z;eq((J,X,w,U),(F(6,25),F(6,25),F(52,125),F(86,25)));eq(F(1,10)*U,F(1,5)+f*X);eq(F(61,125)-w,(F(1,10)+F(1,5))*J);eq(f*u,F(1,5)*(1-u));eq(F(2,5)*v,q*J*v)
    p=state_price((F(1,4),F(3,4)),(2,F(2,3)),(1,3));out('r3-price',p['price']);out('r3-variance-premium',(p['vm'],p['vr'],p['premium']));eq(p['premium']**2/p['vr'],p['vm']*p['safe']**2,'HJ equality')
    oldasset,oldface,cost,increment=map(F,(50,65,10,20));oldcreditor=min(oldasset,oldface);total=oldasset+increment;lower=oldcreditor;upper=total-cost;out('r3-debt-interval',(lower,upper));eq(max(total-oldface,0)-cost,-5);eq(increment-cost,10)
    for d in (lower,55,upper):need(min(d,total)>=oldcreditor and max(total-d,0)-cost>=0,'full weak bargain interval');count+=1
    base=collateral(F(1,5));stress=collateral(F(1,10));out('r4-loans',(base[0],stress[0]));out('r4-base-c',base[1]);out('r4-stress-c',stress[1])
    for ell,c,kf in (base,stress):eq(c[0]+kf,6);eq(c[1]+5,5+kf);need(1/c[0]-1/c[1]>0 and kf>=0,'positive multiplier/funding');count+=1
    liabilities=((F(0),F(1,2),F(0)),(F(0),F(0),F(1,2)),(F(0),F(0),F(0)));baseline=network((1,1,1),(4,4,4),liabilities);shock=network((F(4,5),1,1),(4,4,4),liabilities);loss=tuple(x-y for x,y in zip(baseline[0],shock[0]));out('r5-payments',baseline[0]);out('r5-residual-bound',F(1,100)/(1-baseline[3]));out('r5-payment-losses',loss);eq(baseline[1],(0,0,0));eq(baseline[2],3);eq(baseline[2]-shock[2],F(1,5));eq(sum(loss),F(7,20))
    a,b=linear(((F(1),F(1)),(F(1),F(-1))),(F(1,10),F(4,100)));out('r5-mechanisms',(a,b));eq(2*a+2*b,F(1,5))
    need(set(expected)|{'o1-invariant','o2-path'}==set(doc.mark),'all 35 displayed markers covered')
    for k,v in expected.items():eq(parsed(doc.mark[k]),v,'display '+k)
    invalid=[lambda:number(True),lambda:number(float('nan')),lambda:parsed('1/0'),lambda:parsed('open(1)'),lambda:two_date((0,1),1,1),lambda:two_date((1,1),0,1),lambda:two_date((1,1),1,0),lambda:state_price((F(1,2),),(1,),(1,)),lambda:state_price((1,),(-1,),(1,)),lambda:state_price((1,),(1,),(0,)),lambda:bank_sale(10,10,1,5),lambda:bank_sale(120,100,10,1),lambda:search(0,1,1,F(1,2),0,1),lambda:search(1,1,1,1,0,1),lambda:search(1,1,1,F(1,2),1,1),lambda:collateral(-1),lambda:collateral(1),lambda:network((-1,1,1),(4,4,4),liabilities),lambda:network((1,1,1),(4,4,4),((0,1,0),(0,0,0),(0,0,0)))]
    for fn in invalid:
        try:fn()
        except ValueError:rejections+=1
        else:raise ValueError('invalid domain accepted')
    for p,b in raw.items():need((root/p).read_bytes()==b,'payload changed')
    return {'volume':'v14','component':'support-peer','status':'passed','comparisons':count,'rejected_inputs':rejections,'diagnostic_tasks':8,'oral_tasks':5,'retention_tasks':5,'score_totals':[40,20,50],'displayed_results':len(doc.mark),'runtime_files':7,'author_code_executed':False,'open_issues':[]}
if __name__=='__main__':check()
