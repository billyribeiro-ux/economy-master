"""Separate macro qualifying review: six immutable payloads, no author execution."""
from pathlib import Path
from html.parser import HTMLParser
from fractions import Fraction as Q
from hashlib import sha256
from math import log,sqrt,isfinite
from itertools import product
import ast,json
FILES=('content/cross-assessments/parts/graduate-macro.html','scripts/check_graduate_macro.py','content/reviews/graduate-macro-sources.json','content/reviews/graduate-macro-author.json','scripts/check_graduate_macro_peer.py','content/reviews/graduate-macro-peer.json')
def require(x,m):
    if not x:raise ValueError(m)
def scalar(x):
    require(type(x)in(int,float,Q) and isfinite(float(x)),'finite nonboolean scalar');return Q(str(x))
def readnum(text):
    def run(n):
        if isinstance(n,ast.Constant):return scalar(n.value)
        if isinstance(n,(ast.Tuple,ast.List)):return tuple(run(z)for z in n.elts)
        if isinstance(n,ast.UnaryOp)and isinstance(n.op,ast.USub):return -run(n.operand)
        if isinstance(n,ast.BinOp)and isinstance(n.op,ast.Div):return run(n.left)/run(n.right)
        raise ValueError('literal syntax')
    return run(ast.parse(text.rsplit('=',1)[-1].strip().replace('−','-'),mode='eval').body)
class Reader(HTMLParser):
    def __init__(self):super().__init__();self.stack=[];self.ids=[];self.prompts={};self.answers=[];self.rubrics={};self.inputs={};self.outputs={};self.sources={};self.domains={}
    def handle_starttag(self,t,attrs):
        a=dict(attrs);require(len(a)==len(attrs),'duplicate attribute')
        if 'id'in a:self.ids.append(a['id'])
        if 'data-domain'in a:self.domains[(a['data-form'],a['data-domain'])]=int(a['data-domain-points'])
        if 'data-points'in a:self.prompts[a['id']]=int(a['data-points'])
        if 'data-solution-for'in a:
            require(any(t=='details'and 'solutions'in d.get('class','').split()for t,d in self.stack),'disclosed answers');self.answers.append(a['data-solution-for'])
        if 'data-rubric-points'in a:self.rubrics[next(d['data-solution-for']for t,d in reversed(self.stack)if 'data-solution-for'in d)]=tuple(map(int,a['data-rubric-points'].split(',')))
        if 'data-source'in a:self.sources[a['data-source']]=a['href']
        for attr,dest in [('data-input',self.inputs),('data-calc',self.outputs)]:
            if attr in a:require(a[attr]not in dest,'repeated number');dest[a[attr]]=''
        if t not in ('br','hr','img','meta','link','input'):self.stack.append((t,a))
    def handle_data(self,s):
        for t,a in self.stack:
            for attr,dest in [('data-input',self.inputs),('data-calc',self.outputs)]:
                if attr in a:dest[a[attr]]+=s
    def handle_endtag(self,t):require(self.stack and self.stack.pop()[0]==t,'balanced tags')
def two(a,b,c,d,y,z):
    a,b,c,d,y,z=map(scalar,(a,b,c,d,y,z));det=a*d-b*c;require(det!=0,'nonsingular');return ((y*d-b*z)/det,(a*z-y*c)/det)
def stop(beta,P,x,depth,state):
    beta=scalar(beta);require(0<beta<1 and type(depth)is int and depth>=0 and state in(0,1),'stop domain');require(len(P)==len(x)==2 and all(len(row)==2 and min(row)>=0 and sum(row)==1 for row in P),'stochastic law')
    if not depth:return x[state]
    return max(x[state],beta*sum(P[state][j]*stop(beta,P,x,depth-1,j)for j in(0,1)))
def household(y0,y1,lower=None):
    y0,y1=map(scalar,(y0,y1));require(y0>0 and y1>0,'positive incomes');s=(y0-y1)/2
    if lower is not None:lower=scalar(lower);require(-y1<lower<y0,'feasible lower saving');s=max(s,lower)
    return s,y0-s,y1+s

def check(root=None):
    root=Path(root)if root else Path(__file__).resolve().parents[1];raw={f:(root/f).read_bytes()for f in FILES};p=Reader();p.feed(raw[FILES[0]].decode());p.close();require(not p.stack and len(set(p.ids))==len(p.ids),'markup/unique IDs');targets=['graduate-macro-'+f+str(i).zfill(2)for f in('a','b')for i in range(1,21)];require(list(p.prompts)==p.answers==targets and set(p.rubrics)==set(targets),'all forty exact answers/rubrics');require(all(p.prompts[k]==5==sum(p.rubrics[k])and min(p.rubrics[k])>0 for k in targets),'five point rubric sums');require(len(p.domains)==10 and set(p.domains.values())=={20}and all(sum(v for(k,d),v in p.domains.items()if k==f)==100 for f in('a','b')),'two100point forms')
    source=json.loads(raw[FILES[2]]);require(p.sources=={s['id']:s['url']for s in source['sources']},'exact primary URLs');peer=json.loads(raw[FILES[5]]);require(set(peer['exact_prompt_review'])==set(targets),'complete substantive record')
    for record,expected in [(json.loads(raw[FILES[3]]),FILES[:3]),(peer,FILES[:5])]:
        bindings=record['payload_bindings'];require({v['path']for v in bindings}==set(expected)and len(bindings)==len(expected),'nonself inventory')
        for v in bindings:require(v['bytes']==len(raw[v['path']])and v['sha256']==sha256(raw[v['path']]).hexdigest(),'frozen payload')
    inp={k:readnum(v)for k,v in p.inputs.items()};out={k:readnum(v)for k,v in p.outputs.items()};seen=set();n=0
    def equal(a,b):
        nonlocal n
        if isinstance(b,(tuple,list)):
            require(isinstance(a,(tuple,list))and len(a)==len(b),'shape')
            for x,y in zip(a,b):equal(x,y)
        else:n+=1;require(isfinite(float(a))and abs(float(a)-float(b))<1e-9*max(1,abs(float(b))),'numerical disagreement '+str((a,b)))
    def shown(k,v):seen.add(k);equal(out[k],v)
    intended={'a-stop-P':((Q(3,4),Q(1,4)),(Q(1,2),Q(1,2))),'a-stop-payoff':(1,4),'a-stop-beta':Q(4,5),'a-olg-tax':(0,Q(1,3)),'a-olg-k0':1,'a-agency':(10,20,Q(4,5),Q(2,5),3,Q(11,10)),'a-portfolio':(2,1,3,Q(1,2),1,Q(17,16),2,Q(1,2)),'a-moments':(5,3,2,3),'b-growth':(3,Q(1,2),1,1),'b-transfer':(1,4,4,1,Q(1,2)),'b-bad-prices':(1,3),'b-international':(2,3,4,6,10,1),'b-causal':(1,2,3)};require(set(inp)==set(intended),'all primitive groups')
    for k,v in intended.items():equal(inp[k],v)
    beta=inp['a-stop-beta'];P=inp['a-stop-P'];x=inp['a-stop-payoff'];shown('a-stop-values',tuple(tuple(stop(beta,P,x,t,j)for j in(0,1))for t in range(3)))
    events=[(1,1,P[0][1]),(2,0,P[0][0]*P[0][0]),(2,1,P[0][0]*P[0][1])];shown('a-stop-distribution',tuple(e[2]for e in events)+(sum(t*pr for t,j,pr in events),sum(beta**t*x[j]*pr for t,j,pr in events)))
    for t,j,pr in events:equal(x[j]+(4-x[j]),4)
    vinf=(beta*P[0][1]*x[1]/(1-beta*P[0][0]),x[1]);shown('a-stop-infinite-value',vinf);discount=beta*P[0][1]/(1-beta*P[0][0]);shown('a-stop-infinite-time',(1/P[0][1],discount,x[1]*discount))
    # Finite tree reconstruction at changed discounts/depths and all Bellman actions.
    for bb in (Q(1,2),Q(4,5),Q(9,10)):
        v=x
        for depth in range(5):
            equal(tuple(stop(bb,P,x,depth,j)for j in(0,1)),v);v=tuple(max(x[j],bb*sum(P[j][k]*v[k]for k in(0,1)))for j in(0,1))
    for j in(0,1):equal(vinf[j],max(x[j],beta*sum(P[j][k]*vinf[k]for k in(0,1))))
    taxes=inp['a-olg-tax'];coeff=tuple((1-t)/(1+t)for t in taxes);shown('a-olg-coefficients',coeff);t=taxes[1];k=float(coeff[1])**1.5;w=2*k**(1/3);r=k**(-2/3);cy=(1-float(t))*w-k;co=r*k+float(t)*w;shown('a-olg-stationary',(k,r,w,cy,co));equal(cy+co+k,3*k**(1/3))
    k0=inp['a-olg-k0'];k1=coeff[1];cy0=2*(1-t)-k1;old0=1+2*t;co1=float(k1)**(1/3)*(1+2*float(t));shown('a-olg-transition',(old0,k1,cy0));shown('a-olg-welfare',(log(float(cy0)*co1),log(cy*co)));equal(old0+cy0+k1,3)
    for tax in (0,Q(1,3),Q(3,4)):
        state=2.0
        for period in range(8):
            wage=2*state**(1/3);new=float((1-tax)/(1+tax))*state**(1/3);futurew=2*new**(1/3);rent=new**(-2/3);pension=float(tax)*futurew;young=(1-float(tax))*wage-new;old=rent*new+pension;equal(1/young,rent/old);equal(young+new+state*state**(-2/3)+float(tax)*wage,3*state**(1/3));state=new
    I,Y,ph,pl,B,R=inp['a-agency'];maxdebt=Y-B/(ph-pl);minn=I-ph*maxdebt/R;shown('a-agency-threshold',minn);debt=R*(I-1)/ph;shown('a-agency-contract',(debt,(ph-pl)*(Y-debt)-B,ph*debt,ph*(Y-debt)-R));g=Q(5);dg=(R*I-(1-ph)*g)/ph;shown('a-guaranteed-debt',(dg,(ph-pl)*(Y-dg)-B,ph*dg+(1-ph)*g));shown('a-guarantee-funding',(g/R,(1-ph)*g,(1-ph)*g/R))
    for guarantee in(0,Q(9,2),Q(5)):
        d=(R*I-(1-ph)*guarantee)/ph;equal(ph*d+(1-ph)*guarantee,R*I);equal(d+(Y-d),Y);require(((ph-pl)*(Y-d)>=B)==(guarantee>=5),'sharp effort threshold');n+=1
    y0,yl,yh,prob,qd,qf,xl,xh=inp['a-portfolio'];ql,qh=two(1,1,xl,xh,qd,qf);shown('a-portfolio-arrows',(ql,qh));wealth=y0+ql*yl+qh*yh;c0=wealth/2;cl=prob*c0/ql;ch=(1-prob)*c0/qh;b,h=two(1,xl,1,xh,cl-yl,ch-yh);shown('a-portfolio-unconstrained',(b,h,c0,cl,ch));shown('a-portfolio-foreign',(4+b+qf*h,4-b-xl*h,4-b-xh*h))
    # Solve cap independently through the quadratic derived by clearing denominators.
    bc=(-141+9*sqrt(57))/64;cc=(float(y0-qf)-bc,float(yl+xl)+bc,float(yh+xh)+bc);mu=-float(qf)/cc[0]+float(prob*xl)/cc[1]+float((1-prob)*xh)/cc[2];shown('a-portfolio-cap',(bc,*cc,mu));equal(-1/cc[0]+.5/cc[1]+.5/cc[2],0);require(mu>0,'cap multiplier');n+=1
    value=lambda cs:log(float(cs[0]))+.5*log(float(cs[1]))+.5*log(float(cs[2]));shown('a-portfolio-loss',value((c0,cl,ch))-value(cc))
    for bb,hh in[(b,h),(bc,1)]:
        local=(float(y0-bb-qf*hh),float(yl+bb+xl*hh),float(yh+bb+xh*hh));other=(float(4+bb+qf*hh),float(4-bb-xl*hh),float(4-bb-xh*hh));require(min(local+other)>0,'both counterparties solvent');n+=1;equal(tuple(a+z for a,z in zip(local,other)),(6,5,7))
    for bb,hh in product((-2,-1,0),(Q(0),Q(1,2),Q(1))):
        test=(y0-bb-qf*hh,yl+bb+xl*hh,yh+bb+xh*hh)
        if min(test)>0:require(value(test)<=value(cc)+1e-12,'cap global witness');n+=1
    vz,czy,cwz,cwy=inp['a-moments'];theta=cwy/cwz;kappa=1-1/theta;shown('a-iv',(czy/vz,theta,kappa));thetahat=(2*3+Q(9,5))/5;res=(3-2*thetahat,Q(9,5)-thetahat);shown('a-overidentified',(thetahat,*res,sum(z*z for z in res)));true=Q(1,5)/(1-kappa);wrong=Q(1,5)/(1-Q(2,5));resid=wrong-Q(1,5)-kappa*wrong;shown('a-operator',(true,wrong,resid,resid/(1-kappa)));shown('a-exclusion-pairs',((1,theta-1),(theta,0)))
    for th in (Q(-2),Q(0),Q(1),theta,Q(3)):equal(th+(theta-th),theta)
    A,discount,kstart,consstart=inp['b-growth'];kk=kstart;cons=consstart
    for period in range(2):kk=A*kk-cons;cons*=discount*A
    shown('b-growth-report-t2',(kk,cons));optc=(1-discount)*A*kstart;shown('b-growth-optimal',(discount*A*kstart,optc,1/(1-discount)));unused=kstart-consstart/(A*(1-discount));tail=A*unused/consstart;shown('b-growth-loss',(tail,unused,log(float(optc/consstart))/float(1-discount)));shown('b-distribution-gap',(log(.5)+log(1.5))/(2*float(1-discount)))
    for cstart in(Q(1,2),Q(1),optc):
        kk=kstart;ccur=cstart
        for period in range(12):
            formula=A**period*(kstart-cstart*(1-discount**period)/(A*(1-discount)));equal(kk,formula);require(kk>=0,'Euler feasibility');n+=1;new=A*kk-ccur;equal(discount*A/float(ccur*discount*A),1/float(ccur));kk=new;ccur*=discount*A
    p0,p1,h0,h1,tau=inp['b-transfer'];bp=household(p0,p1,0);bh=household(h0,h1);ap=household(p0+tau,p1-tau,0);ah=household(h0+tau,h1-tau);shown('b-transfer-baseline',(bp[0],bh[0],*bp[1:],*bh[1:]));nfa=ap[0]+ah[0]-2*tau;shown('b-transfer-policy',(ap[0],ah[0],nfa,*ap[1:]));shown('b-transfer-gain',log(float(ap[1]*ap[2]/(bp[1]*bp[2]))));shown('b-transfer-unrestricted-saving',(household(p0,p1)[0],household(h0,h1)[0],household(p0+tau,p1-tau)[0],household(h0+tau,h1-tau)[0]))
    for pp,hh,debtgov in((bp,bh,0),(ap,ah,2*tau)):
        nf=pp[0]+hh[0]-debtgov;equal(pp[1]+hh[1]+2+nf,7);equal(pp[2]+hh[2]+2-nf,7)
    qs,qx=inp['b-bad-prices'];arrows=two(1,1,0,2,qs,qx);cost=qs-qx/2;shown('b-price-arbitrage',(*arrows,cost,1,0));shown('b-long-only',(0,0));good=two(1,1,0,2,1,1);prices=lambda q:(q[0]+2*q[1],q[1],q[0]+3*q[1]);shown('b-firm-values',(prices(arrows),prices(good)));debtprice=prices(good)[0];actual=(1/debtprice,2/debtprice);shown('b-debt-returns',(2/debtprice,*actual,sum(actual)/2,sum(actual)/2-1))
    eold,enew,af,lf,ad,loan=inp['b-international'];oldn=eold*(af-lf);newn=enew*(af-lf);shown('b-valuation',(oldn,ad+oldn,newn,ad+newn,newn-oldn,0));shown('b-gross-flows',(af+loan,lf+loan,newn,af,lf+loan,enew*(af-lf-loan),-enew*loan));shown('b-foreign-resources',(10+af-lf-loan,2+lf+loan-af,10+af-lf,2+lf-af));net=lf-af;pay=tuple(net*(E-eold)for E in(1,3));wealth=tuple(ad+(af-lf)*E+p for E,p in zip((1,3),pay));shown('b-hedge',(*pay,*wealth,max(abs(z)for z in pay)))
    strength,credit,latent=inp['b-causal'];vz=Q(1);vu=Q(1);vcredit=strength**2*vz+vu;covcredit=credit*vcredit+latent*vu;rf=credit*strength;shown('b-causal-slopes',(covcredit/vcredit,rf,rf/strength));conditional=two(1,strength,strength,vcredit,rf,covcredit);shown('b-conditioned',conditional);examples=tuple((th,rf-th*strength,credit+latent-th)for th in(2,1,0));shown('b-equivalence-examples',examples)
    for th,gamma,delta in examples:
        for z,u in((-1,2),(2,3),(0,-2)):equal(th*(strength*z+u)+gamma*z+delta*u,rf*z+(credit+latent)*u)
    amin,amax,bmin,bmax=Q(3,200),Q(1,40),Q(-1,200),Q(1,40);shown('b-weak-endpoints',(amin/bmin,amin/bmax))
    for ratio in(-100,-3,Q(3,5),1,2,100):
        denom=amin/ratio;require(bmin<=denom<=bmax and denom!=0,'ratio branch attainment');equal(amin/denom,ratio)
    require(seen==set(out),'all41 visible results independently checked')
    bad=[lambda:scalar(True),lambda:scalar(float('nan')),lambda:scalar(float('inf')),lambda:readnum('x+1'),lambda:readnum('1/0'),lambda:two(1,2,2,4,0,1),lambda:stop(0,P,x,2,0),lambda:stop(1,P,x,2,0),lambda:stop(beta,((Q(1),Q(1)),P[1]),x,2,0),lambda:stop(beta,P,x,-1,0),lambda:stop(beta,P,x,2.0,0),lambda:household(0,1),lambda:household(1,-1),lambda:household(1,2,1),lambda:household(1,2,-2)]
    for fn in bad:
        try:fn()
        except(ValueError,ZeroDivisionError):pass
        else:raise ValueError('malformed accepted')
    summary={'assessment':'graduate-qualifying','field':'macro','review':'separate peer','status':'passed','comparisons':n,'domain_rejections':len(bad),'solved_subparts':40,'forms':2,'primitive_groups':len(inp),'checked_results':len(out),'runtime_files':6,'limits':'Full proof reading separately recorded; finite witnesses do not establish universal claims alone.'};json.dumps(summary,allow_nan=False);return summary
if __name__=='__main__':check()
