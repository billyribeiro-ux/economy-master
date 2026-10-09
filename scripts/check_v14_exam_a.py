"""Form A original numerical and structural audit; exactly four runtime payloads."""
from pathlib import Path
from hashlib import sha256
from html.parser import HTMLParser
from math import log,sqrt,isfinite
import ast,json
FILES=('content/assessments/parts/v14-exam-a.html','scripts/check_v14_exam_a.py','content/reviews/v14-exam-a-sources.json','content/reviews/v14-exam-a-author.json')
def require(ok,msg):
    if not ok:raise ValueError(msg)
def number(x):
    require(type(x) in (int,float) and isfinite(x),'finite real');return float(x)
def vector(x,n=None):
    require(isinstance(x,(tuple,list)) and len(x)>0,'nonempty vector');require(n is None or len(x)==n,'vector length');return tuple(map(number,x))
def probability(x):
    x=vector(x);require(min(x)>=0 and abs(sum(x)-1)<1e-12,'probability law');return x
def matrix(a):
    require(isinstance(a,(list,tuple)) and len(a)>0,'nonempty matrix');return tuple(vector(row,len(a)) for row in a)
def solve(a,b):
    a=matrix(a);b=vector(b,len(a));n=len(b);m=[list(row)+[rhs] for row,rhs in zip(a,b)]
    for k in range(n):
        pivot=max(range(k,n),key=lambda j:abs(m[j][k]));require(abs(m[pivot][k])>1e-13,'singular system');m[k],m[pivot]=m[pivot],m[k];div=m[k][k];m[k]=[x/div for x in m[k]]
        for j in range(n):
            if j!=k:
                factor=m[j][k];m[j]=[x-factor*y for x,y in zip(m[j],m[k])]
    return tuple(row[-1] for row in m)
def mv(a,b):return tuple(sum(x*y for x,y in zip(row,b)) for row in a)
def mm(a,b):return tuple(tuple(sum(a[i][k]*b[k][j] for k in range(len(b))) for j in range(len(b[0]))) for i in range(len(a)))
def bracket_root(f,lo,hi):
    lo,hi=number(lo),number(hi);require(lo<hi,'ordered bracket');fl,fh=f(lo),f(hi);require(fl*fh<=0,'bracket signs')
    if fl==0:return lo
    if fh==0:return hi
    for _ in range(90):
        mid=(lo+hi)/2;fm=f(mid)
        if fm==0:return mid
        if fm*fl>0:lo=mid;fl=fm
        else:hi=mid
    return (lo+hi)/2

def debtprice(face,incomes,probs,loss,R):
    face,loss,R=map(number,(face,loss,R));incomes=vector(incomes);probs=probability(probs)
    require(face>=0 and 0<loss<1 and R>0 and len(incomes)==len(probs) and min(incomes)>0,'default domain')
    repays=tuple(face<=loss*y for y in incomes);q=sum(pi for pi,rep in zip(probs,repays) if rep)/R
    return q,repays

def panel(c):
    require(isinstance(c,(tuple,list)) and len(c)==4 and all(type(v)==int for v in c),'integer count tuple')
    n,m,h,j=c;require(n>0 and h>0 and 0<=m<=n and 0<=j<=h,'observed count rows');return m/n,j/h

def scores(c,forecasts):
    panel(c);forecasts=vector(forecasts,2);require(all(0<x<1 for x in forecasts),'interior forecast')
    observations=[(y,forecasts[0]) for y in [1]*c[1]+[0]*(c[0]-c[1])]+[(y,forecasts[1]) for y in [1]*c[3]+[0]*(c[2]-c[3])]
    return sum(log(p if y else 1-p) for y,p in observations)/len(observations),sum((y-p)**2 for y,p in observations)/len(observations)

def strict_json(raw):
    def pairs(items):
        out={}
        for k,v in items:require(k not in out,'duplicate JSON key');out[k]=v
        return out
    def invalid(x):raise ValueError('nonfinite JSON')
    result=json.loads(raw,object_pairs_hook=pairs,parse_constant=invalid);json.dumps(result,allow_nan=False);return result

def literal(s):
    s=s.replace('−','-').split('=',1)[-1].strip()
    def walk(n):
        if isinstance(n,ast.Constant):return number(n.value)
        if isinstance(n,(ast.Tuple,ast.List)):return tuple(walk(x) for x in n.elts)
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,(ast.USub,ast.UAdd)):return (-1 if isinstance(n.op,ast.USub) else 1)*walk(n.operand)
        if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Div):return walk(n.left)/walk(n.right)
        raise ValueError('numeric literal only')
    return walk(ast.parse(s,mode='eval').body)

class Read(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.stack=[];self.ids=[];self.prompts={};self.solutions={};self.rubrics={};self.domains={};self.mark={};self.sources={};self.headings=[]
    def handle_starttag(self,t,attrs):
        a=dict(attrs);require(len(a)==len(attrs),'duplicate attribute')
        if 'id' in a:require(a['id'] not in self.ids,'duplicate ID');self.ids.append(a['id'])
        if t=='h1':raise ValueError('no extra h1')
        if t=='h2':self.headings.append(a.get('id'))
        if 'data-domain' in a:
            require(a['data-domain'] not in self.domains,'duplicate domain');self.domains[a['data-domain']]=[int(a['data-domain-points']),[]]
        if 'data-points' in a:
            domain=next((d['data-domain'] for tag,d in reversed(self.stack) if 'data-domain' in d),None);require(domain in self.domains,'scored domain')
            key=a['id'];require(key not in self.prompts,'duplicate prompt');self.prompts[key]=[int(a['data-points']),domain,a['data-chapters'].split()];self.domains[domain][1].append(key)
        if 'data-solution-for' in a:
            require(any(tag=='details' and 'solutions' in d.get('class','').split() for tag,d in self.stack),'solution disclosure');key=a['data-solution-for'];require(key not in self.solutions,'duplicate solution');self.solutions[key]=''
        if 'data-rubric-points' in a:
            key=next(d['data-solution-for'] for tag,d in reversed(self.stack) if 'data-solution-for' in d);require(key not in self.rubrics,'duplicate rubric');self.rubrics[key]=tuple(int(x) for x in a['data-rubric-points'].split(','))
        for attr in ('data-input','data-calc'):
            if attr in a:require(a[attr] not in self.mark,'duplicate marker');self.mark[a[attr]]=[attr,'']
        if 'data-source' in a:require(a['data-source'] not in self.sources,'duplicate source');self.sources[a['data-source']]=a['href']
        if t not in ('br','hr','img','meta','link','input'):self.stack.append((t,a))
    def handle_data(self,s):
        for tag,a in self.stack:
            if 'data-solution-for' in a:self.solutions[a['data-solution-for']]+=s
            for attr in ('data-input','data-calc'):
                if attr in a:self.mark[a[attr]][1]+=s
    def handle_endtag(self,t):
        require(self.stack and self.stack[-1][0]==t,'HTML nesting');self.stack.pop()

def check(root=None):
    base=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    raw={p:(base/p).read_bytes() for p in FILES};doc=Read();doc.feed(raw[FILES[0]].decode());doc.close();require(not doc.stack,'unclosed HTML')
    targets=['v14-exam-a-q'+str(j).zfill(2) for j in range(1,21)]
    require(list(doc.prompts)==list(doc.solutions)==targets and set(doc.rubrics)==set(targets),'twenty exact paired prompts')
    require(doc.headings==['form-a','solutions-a'] and all(x.startswith('v14-exam-a-') or x in doc.headings for x in doc.ids),'stable assessment IDs')
    require(sum(x[0] for x in doc.prompts.values())==100,'100 scored points')
    for p in targets:require(doc.prompts[p][0]==5 and sum(doc.rubrics[p])==5 and min(doc.rubrics[p])>0 and len(doc.solutions[p])>600,'substantive additive five-point solution')
    expected_domains=('dynamic_distribution','labor_policy','pricing_investment','liquidity_international','quantitative_research')
    require(tuple(doc.domains)==expected_domains,'five named domains')
    for total,items in doc.domains.values():require(total==20 and len(items)==4 and sum(doc.prompts[p][0] for p in items)==20,'twenty-point domain')
    require({c for p in doc.prompts.values() for c in p[2]}=={'v14-c'+str(j).zfill(2) for j in range(1,13)},'all twelve chapters')
    source=strict_json(raw[FILES[2]]);author=strict_json(raw[FILES[3]])
    require(doc.sources=={s['id']:s['url'] for s in source['sources']},'source routes')
    require(set(author['exact_prompt_solution_audit'])==set(targets),'twenty author audits')
    require(author['unresolved_findings']==[],'no unresolved author finding')
    bindings=author['payload_bindings'];require(len(bindings)==3 and {b['path'] for b in bindings}==set(FILES[:3]),'three nonself bindings')
    for b in bindings:require(len(raw[b['path']])==b['bytes'] and sha256(raw[b['path']]).hexdigest()==b['sha256'],'frozen payload')
    ncheck=0;nreject=0;used=set()
    def near(a,b):
        nonlocal ncheck
        if isinstance(b,(tuple,list)):
            require(isinstance(a,(tuple,list)) and len(a)==len(b),'comparison shape')
            for x,y in zip(a,b):near(x,y)
        else:require(isfinite(float(a)) and abs(float(a)-float(b))<2e-9*max(1,abs(float(b))),str((a,b)));ncheck+=1
    def yes(ok,msg):
        nonlocal ncheck
        require(ok,msg);ncheck+=1
    def mark(k,value):require(k in doc.mark,'missing '+k);near(literal(doc.mark[k][1]),value);used.add(k)
    inputs={k:literal(v[1]) for k,v in doc.mark.items() if v[0]=='data-input'}
    intended={'exchange-beta':.9,'exchange-P':((.75,.25),(.25,.75)),'rbc':(1/3,.75,8/9),'matching':(.25,.25,.5,.5,1.5,.5),'nk':(.5,.5,1,2,.5),'fiscal':(6,1,2,1.25),'sovereign':(2,5,.5,.25,1.25),'pricing-probabilities':(.25,.75),'pricing-consumption':(.9,1,.5,1.5),'investment-Q':2,'investment-cash':.375,'deposit':(.5,2.25,.25),'dealer':(2,.25,2,2,.5,4),'international':(.5,.5,3,1,3.5,2.5,.5,1.5),'currency':(.25,1.8,.6,3,.5,1.5),'sequence-K':((.25,.25),(.125,.25)),'sequence-d':(.1,0),'training-counts':(30,9,20,4),'holdout-counts':(8,2,12,3),'network-b':(4,4,4),'network-e':(1,0,0),'network-A':((0,.5,0),(0,0,.5),(.5,0,0))}
    require(set(inputs)==set(intended),'primitive coverage')
    for k,v in intended.items():mark(k,v)
    beta=inputs['exchange-beta'];P=inputs['exchange-P'];assets=(-1,1);income=(2,6);g=(0,1,0,1);states=((0,0),(0,1),(1,0),(1,1));c=tuple(assets[a]+income[e]-assets[j] for (a,e),j in zip(states,g));Q=tuple(tuple(P[e][f] if j==b else 0 for b,f in states) for (a,e),j in zip(states,g))
    V=solve(tuple(tuple((1 if i==j else 0)-beta*Q[i][j] for j in range(4)) for i in range(4)),tuple(map(log,c)))
    gaps=[]
    for i,((a,e),chosen) in enumerate(zip(states,g)):
        near(V[i],log(c[i])+beta*sum(q*v for q,v in zip(Q[i],V)))
        for j in (0,1):
            cc=assets[a]+income[e]-assets[j]
            if cc>0 and j!=chosen:
                diff=V[i]-(log(cc)+beta*sum(P[e][f]*V[2*j+f] for f in (0,1)));gaps.append(diff);yes(diff>0,'strict household choice')
    mark('exchange-gaps',gaps)
    M=tuple(tuple(Q[j][i]-(1 if i==j else 0) for j in range(4)) for i in range(3))+((1,1,1,1),);pi=solve(M,(0,0,0,1));mark('exchange-mass',pi);near(tuple(sum(pi[i]*Q[i][j] for i in range(4)) for j in range(4)),pi);yes(min(x for row in mm(Q,Q) for x in row)>=1/16-1e-12,'two-step minorization')
    meanb=sum(w*assets[a] for w,(a,e) in zip(pi,states));meang=sum(w*assets[j] for w,j in zip(pi,g));meaninc=sum(w*income[e] for w,(a,e) in zip(pi,states));meanc=sum(w*x for w,x in zip(pi,c));near((meanb,meang),(0,0));near(meanc+meang,meanb+meaninc);mark('exchange-goods',(meaninc,meanc));mark('exchange-covariance',sum(w*assets[a]*income[e] for w,(a,e) in zip(pi,states))-meanb*meaninc)
    alpha,beta,chi=inputs['rbc'];s=alpha*beta;B=alpha/(1-s);labor=(1-alpha)/((1-alpha)+chi*(1-s));mark('rbc-policy',(s,labor,B));L=log(2);constant=log(s)+(1-alpha)*log(labor);mean=constant/(1-alpha);v=L*L/(1-alpha*alpha);mark('rbc-log-variance-multiple',v/(L*L));mark('rbc-geometric-capital',2**(mean/L));mark('rbc-output-correlation',alpha)
    for k in (.01,.1,1,4):
        for z in (.5,2):
            Y=z*k**alpha*labor**(1-alpha);kp=s*Y;cons=(1-s)*Y;w=(1-alpha)*Y/labor;r=alpha*Y/k;near(chi*cons/(1-labor),w);near(w*labor+r*k,Y)
            rhs=0.
            for zp in (.5,2):
                yp=zp*kp**alpha*labor**(1-alpha);rhs+=.5*beta*alpha*yp/kp/((1-s)*yp)
            near(1/cons,rhs);near(cons+kp,Y)
    r,sep,cost,home,y,eta=inputs['matching'];H=lambda theta:cost*((r+sep)*sqrt(theta)+eta*theta)-(1-eta)*(y-home);theta=bracket_root(H,0,10);finding=sqrt(theta);filling=1/finding;S=(y-home)/(r+sep+eta*finding);J=(1-eta)*S;U=(home+finding*eta*S)/r;E=U+eta*S;w=eta*y+(1-eta)*home+eta*cost*theta;unemp=sep/(sep+finding);mark('matching-quantities',(theta,finding,filling,w,J,U,E,unemp));near(cost,filling*J);near(r*E,w+sep*(U-E));near(sep*(1-unemp),finding*unemp)
    be,ka,sigma,phipi,rho=inputs['nk'];A=((1+ka/(be*sigma),(phipi-1/be)/sigma),(-ka/be,1/be));ab=solve(((rho-A[0][0],-A[0][1]),(-A[1][0],rho-A[1][1])),(1/sigma,0));ia=phipi*ab[1]+1;mark('nk-response',(*ab,ia));near(ab[0],rho*ab[0]-(ia-rho*ab[1])/sigma);near(ab[1],be*rho*ab[1]+ka*ab[0]);near(mm(((0,0),(-1,0)),((0,0),(-1,0))),((0,0),(0,0)))
    D,s0,s1,R=inputs['fiscal'];b0=D-s0;b1=R*b0-s1;s2=R*b1;mark('fiscal-terminal-surplus',s2);mark('fiscal-pv',s0+s1/R+s2/R**2)
    for terminal in (0,3):near(s0+s1/R+(R*b1-terminal)/R**2+terminal/R**2,D)
    yl,yh,pl,loss,R=inputs['sovereign'];probs=(pl,1-pl);pr,repays=debtprice(1,(yl,yh),probs,loss,R);mark('default-proceeds',pr)
    for face in (0,.5,.50001,1,1.25,1.25001,3):
        q,rep=debtprice(face,(yl,yh),probs,loss,R);near(R*q*face,sum(p*face*int(pay) for p,pay in zip(probs,rep)))
        for y,pay in zip((yl,yh),rep):
            c=y-face if pay else (1-loss)*y;destroyed=0 if pay else loss*y;paid=face if pay else 0;yes(c>0,'positive terminal consumption');near(c+destroyed+paid,y)
    be,c0,cl,ch=inputs['pricing-consumption'];pi=inputs['pricing-probabilities'];m=(be*c0/cl,be*c0/ch);arrows=tuple(p*z for p,z in zip(pi,m));safe=sum(arrows);price=2*arrows[1];returns=(0,2/price);rf=1/safe;er=sum(p*r for p,r in zip(pi,returns));vm=sum(p*(z-safe)**2 for p,z in zip(pi,m));vr=sum(p*(r-er)**2 for p,r in zip(pi,returns));mark('arrow-prices',arrows);mark('claim-prices',(safe,price));mark('risk-premium',er-rf);mark('risk-bound-sides',((er-rf)/sqrt(vr),sqrt(vm)/safe));near(sum(p*z*r for p,z,r in zip(pi,m,returns)),1)
    Q=inputs['investment-Q'];I=max(0,Q-1);mark('investment-unconstrained',I);n=inputs['investment-cash'];Ic=bracket_root(lambda x:x/2+x*x/2-n,0,3);loan=max(0,Ic+Ic*Ic/2-n);lam=(Q-1-Ic)/(.5+Ic);dIdn=1/(.5+Ic);mark('investment-constrained',(Ic,loan,lam,dIdn));near(n+loan,Ic+Ic*Ic/2);yes(loan<=Ic/2+1e-12,'pledgeability');near((Q*Ic-loan)-n,(Q-1)*Ic-Ic*Ic/2)
    for trial in (0,.1,.3,Ic):yes((Q-1)*trial-trial*trial/2<=(Q-1)*Ic-Ic*Ic/2+1e-12,'global feasible investment')
    early,R,k=inputs['deposit'];late=lambda c:R*(1-early*c)/(1-early);c1=bracket_root(lambda c:1/(c+k)**2-R/(late(c)+k)**2,0,1/early);c2=late(c1);storage=early*c1;mark('deposit-allocation',(c1,c2,storage));near(R*(1-storage),(1-early)*c2);yes(c2>c1,'patient no-run incentive')
    util=lambda c:-1/(c+k);best=early*util(c1)+(1-early)*util(c2)
    for j in range(21):
        trial=j/(20*early);yes(early*util(trial)+(1-early)*util(late(trial))<=best+1e-12,'global insurance allocation')
    mu,var,a,supply,C1,C2=inputs['dealer'];demand=lambda p,C:min(max((mu-p)/(a*var),0),C/p);p=bracket_root(lambda p:demand(p,C1)+demand(p,C2)-supply,.001,mu);positions=(demand(p,C1),demand(p,C2));mark('dealer-price',p);mark('dealer-holdings',positions);near(sum(positions),supply);near(p*positions[0],C1);yes(p*positions[1]<C2,'second mandate slack');near(sum(p*x for x in positions),p*supply)
    for C,x in zip((C1,C2),positions):
        obj=lambda z:(mu-p)*z-a*var*z*z/2
        for trial in (0,C/(2*p),C/p):yes(obj(trial)<=obj(x)+1e-12,'global dealer optimum')
    be,pl,h0,f0,hl,hh,fl,fh=inputs['international'];world0=h0+f0;world=(hl+fl,hh+fh);ap=(be*pl*world0/world[0],be*(1-pl)*world0/world[1]);wealthH=h0+ap[0]*hl+ap[1]*hh;wealthW=world0+sum(x*y for x,y in zip(ap,world));share=wealthH/wealthW;hc=(share*world0,share*world[0],share*world[1]);fc=tuple(w-h for w,h in zip((world0,*world),hc));mark('international-arrows',ap);mark('international-H-trades',(hc[1]-hl,hc[2]-hh));near(hc,(3,3,3));near(fc,(1,1,1));near(hc[0]+sum(q*c for q,c in zip(ap,hc[1:])),wealthH);near(be*pl*hc[0]/hc[1],ap[0]);near(be*pl*fc[0]/fc[1],ap[0])
    pl,ml,mh,E0,xl,xh=inputs['currency'];prob=(pl,1-pl);m=(ml,mh);X=(xl,xh);em=sum(p*v for p,v in zip(prob,m));emx=sum(p*v*x for p,v,x in zip(prob,m,X));ex=sum(p*x for p,x in zip(prob,X));rd,rf=1/em,1/emx;cov=emx-em*ex;mark('currency-safe-returns',(rd,rf));mark('currency-forward',E0*rd/rf);mark('currency-expected-spot',E0*ex);mark('currency-covariance',cov);mark('currency-premium',rf*ex-rd);near(rf*ex-rd,-rd*rf*cov)
    K=inputs['sequence-K'];d=inputs['sequence-d'];M=tuple(tuple((1 if i==j else 0)-K[i][j] for j in range(2)) for i in range(2));ys=solve(M,d);cross=solve(M,(1,0))[1];norm=max(sum(abs(x) for x in row) for row in K);mark('sequence-solution',ys);mark('sequence-cross',cross);mark('sequence-error',.0001/(1-norm));near(ys,tuple(x+y for x,y in zip(d,mv(K,ys))))
    train=tuple(int(x) for x in inputs['training-counts']);fit=panel(train);mark('transition-estimates',fit);stationary=fit[0]/sum(fit);persist=1-sum(fit);mark('transition-moments',(stationary,persist));near((stationary*(1-persist),(1-stationary)*(1-persist)),fit)
    hold=tuple(int(x) for x in inputs['holdout-counts']);scfit=scores(hold,fit);scc=scores(hold,(.25,.25));mark('holdout-log-scores',(scfit[0],scc[0]));mark('holdout-brier',(scfit[1],scc[1]));yes(scc[0]>scfit[0] and scc[1]<scfit[1],'heldout ranking')
    for true in (.1,.4,.9):
        for forecast in (.2,.5,.8):near(true*(1-forecast)**2+(1-true)*forecast**2,true*(1-true)+(forecast-true)**2)
    A=inputs['network-A'];b=inputs['network-b'];e=inputs['network-e'];M=tuple(tuple((1 if i==j else 0)-A[j][i] for j in range(3)) for i in range(3));paid=solve(M,e);mark('network-payments',paid);yes(all(0<=x<cap for x,cap in zip(paid,b)),'strict default regime');equity=tuple(e[i]+sum(A[j][i]*paid[j] for j in range(3))-paid[i] for i in range(3));outside=sum((1-sum(row))*x for row,x in zip(A,paid));mark('network-outside',outside);near(sum(e),sum(equity)+outside);near(max(map(sum,A)),.5)
    require(used==set(doc.mark),'every primitive and result audited')
    invalid=[(number,(True,)),(number,(float('nan'),)),(probability,((.4,.4),)),(probability,((-.1,1.1),)),(vector,([],)),(solve,(((1,0),(0,1),(0,0)),(1,2))),(solve,(((1,2),(2,4)),(1,2))),(bracket_root,(lambda x:x*x+1,-1,1)),(bracket_root,(lambda x:x,1,0)),(debtprice,(-1,(2,5),(.5,.5),.25,1.25)),(debtprice,(1,(2,5),(.5,.5),0,1.25)),(debtprice,(1,(2,5),(.5,.5),.25,0)),(panel,((0,0,2,1),)),(panel,((2,3,2,1),)),(panel,((2,1,2,True),)),(scores,((2,1,2,1),(.2,0))), (literal,('f(1)',)),(literal,('1/0',)),(strict_json,('{"x":1,"x":2}',)),(strict_json,('{"x":NaN}',))]
    for fn,args in invalid:
        try:fn(*args)
        except (ValueError,ZeroDivisionError):nreject+=1
        else:raise ValueError('invalid domain accepted '+fn.__name__)
    require({p:(base/p).read_bytes() for p in FILES}==raw,'runtime mutated')
    result=dict(volume='v14',component='exam_a',status='passed',comparisons=ncheck,domain_rejections=nreject,scored_prompts=20,solutions=20,total_points=100,domains=5,chapter_coverage=12,primitive_markers=len(inputs),result_markers=len(doc.mark)-len(inputs),runtime_files=4)
    json.dumps(result,allow_nan=False);return result
if __name__=='__main__':check()
