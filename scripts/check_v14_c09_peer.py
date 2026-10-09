"""Independent peer reconstruction: planner derivative, bracketed sales, enumerated dealer regimes."""
import json,math,re
from itertools import product
from pathlib import Path
from hashlib import sha256
from fractions import Fraction
from html.parser import HTMLParser
FILES=('content/chapters/v14-c09.html','scripts/check_v14_c09.py','content/reviews/v14-c09-sources.json','content/reviews/v14-c09-author.json','scripts/check_v14_c09_peer.py','content/reviews/v14-c09-peer.json')
def need(ok,msg):
    if not ok:raise ValueError(msg)
def number(x):
    need(type(x) in (float,int) and math.isfinite(x),'finite real');return float(x)
def bisect(f,a,b):
    a,b=number(a),number(b);need(a<b,'ordered interval');fa,fb=f(a),f(b);need(fa*fb<=0,'bracket sign')
    if fa==0:return a
    if fb==0:return b
    for _ in range(90):
        m=(a+b)/2;fm=f(m)
        if fm==0:return m
        if fm*fa>0:a=m;fa=fm
        else:b=m
    return (a+b)/2

def planner(lam,R,k):
    lam,R,k=map(number,(lam,R,k));need(0<lam<1 and R>1 and k>0,'planner domain')
    later=lambda early:R*(1-lam*early)/(1-lam)
    derivative=lambda early:1/(early+k)**2-R/(later(early)+k)**2
    need(derivative(0)>0 and derivative(1/lam)<0,'positive interior planner')
    early=bisect(derivative,0,1/lam);return early,later(early),lam*early

def feedback(D,alpha):
    D,alpha=map(number,(D,alpha));need(D>=0 and 0<alpha<1,'feedback parameters')
    f=lambda z:(z+4)*(1-alpha*z)-5*D
    peak=(1-4*alpha)/(2*alpha);points=sorted(set((0.,1.,max(0.,min(1.,peak)))))
    roots=[]
    for a,b in zip(points,points[1:]):
        if f(a)*f(b)<=0:
            z=bisect(f,a,b)
            if not any(abs(z-old)<1e-9 for old in roots):roots.append(z)
    out=[]
    for z in roots:
        p=1-alpha*z;n=p-D;debt=D-p*z
        if p>0 and n>0 and debt>=-1e-12 and z>=0:out.append((z,p,n,debt,5*D*alpha/p**2))
    return out

def dealers(mu,var,aversions,caps,X):
    mu,var,X=map(number,(mu,var,X));need(mu>0 and var>0,'payoff moments')
    need(isinstance(aversions,(list,tuple)) and isinstance(caps,(list,tuple)) and len(aversions)==len(caps)>0,'dealer vectors')
    aversions=tuple(map(number,aversions));caps=tuple(map(number,caps));need(min(aversions+caps)>0,'positive capacities and risk aversion')
    b=tuple(1/(a*var) for a in aversions);need(0<X<mu*sum(b),'open supply domain')
    solutions=[]
    # Independently solve every choice of cash-binding dealers. At equality either label is valid.
    for binding in product((False,True),repeat=len(caps)):
        B=sum(v for v,bind in zip(b,binding) if not bind);S=sum(C for C,bind in zip(caps,binding) if bind)
        if B==0:p=S/X
        else:
            linear=X-mu*B;disc=linear*linear+4*B*S
            p=(-linear+math.sqrt(disc))/(2*B)
        if not 0<p<mu:continue
        holdings=tuple(C/p if bind else v*(mu-p) for C,v,bind in zip(caps,b,binding))
        valid=all((v*(mu-p)>=C/p-1e-10 if bind else v*(mu-p)<=C/p+1e-10) for C,v,bind in zip(caps,b,binding))
        if valid and not any(abs(p-old[0])<1e-9 for old in solutions):solutions.append((p,holdings,binding))
    need(len(solutions)==1,'unique feasible active-set price');return solutions[0]

class Read(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.mark={};self.active=None;self.ex=[];self.sol=[];self.work=[];self.ids=[];self.sources={}
    def handle_starttag(self,t,attrs):
        a=dict(attrs)
        if 'id' in a:self.ids.append(a['id'])
        if 'worked' in a.get('class','').split():self.work.append(a['id'])
        if t=='li' and re.fullmatch('v14-c09-e[0-9]+',a.get('id','')):self.ex.append(a['id'])
        if 'data-solution-for' in a:self.sol.append(a['data-solution-for'])
        if 'data-source' in a:self.sources[a['data-source']]=a.get('href')
        if 'data-calc' in a:
            self.active=a['data-calc'];need(self.active not in self.mark,'unique marker');self.mark[self.active]=''
    def handle_data(self,s):
        if self.active:self.mark[self.active]+=s
    def handle_endtag(self,t):
        if t=='span':self.active=None

def numeric(s):
    parts=[x.strip() for x in s.strip().strip('()').split(',')]
    need(all(re.fullmatch(r'[+-]?\d+(?:\.\d+)?(?:/\d+(?:\.\d+)?)?',p) for p in parts),'literal only')
    vals=tuple(float(Fraction(p)) for p in parts);return vals[0] if len(vals)==1 else vals

def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    raw={p:(root/p).read_bytes() for p in FILES};d=Read();d.feed(raw[FILES[0]].decode());d.close()
    need(len(d.ids)==len(set(d.ids)),'unique HTML IDs');ex=['v14-c09-e'+str(j) for j in range(1,13)]
    need(d.ex==d.sol==ex,'exact twelve prompt pairs');need(d.work==['v14-c09-w'+str(j) for j in range(1,6)],'five cases')
    author=json.loads(raw[FILES[3]]);peer=json.loads(raw[FILES[5]]);sources=json.loads(raw[FILES[2]])
    need(set(author['exact_prompt_solution_audit'])==set(peer['exact_prompt_review'])==set(ex),'review coverage')
    need(d.sources=={s['id']:s['url'] for s in sources['sources']},'source routing')
    for rec,paths in ((author,FILES[:3]),(peer,FILES[:5])):
        bs=rec['payload_bindings'];need(len(bs)==len(paths) and {b['path'] for b in bs}==set(paths),'binding set')
        for b in bs:need(len(raw[b['path']])==b['bytes'] and sha256(raw[b['path']]).hexdigest()==b['sha256'],'bound payload')
    comparisons=0;rejections=0;seen=set()
    def close(a,b):
        nonlocal comparisons
        if isinstance(b,(tuple,list)):
            need(isinstance(a,(tuple,list)) and len(a)==len(b),'comparison dimension')
            for x,y in zip(a,b):close(x,y)
        else:need(math.isfinite(float(a)) and abs(a-b)<1e-9*max(1,abs(b)),str((a,b)));comparisons+=1
    def marker(k,v):need(k in d.mark,'missing '+k);close(numeric(d.mark[k]),v);seen.add(k)
    def truth(b,msg):
        nonlocal comparisons
        need(b,msg);comparisons+=1
    marker('balance-leverage',(100-5)/(10-5));marker('balance-sale',95-10*5);marker('balance-cash-injection',bisect(lambda e:(95+e)/(5+e)-10,0,20))
    for loss,h in ((5,.1),(7,.1),(5,.2)):
        A=100-loss;n=A-90;sale=A-n/h;D=90-sale
        close((A-sale)-D,n);close(A-sale,n/h);truth(D>=0,'nonnegative debt')
    marker('e1-leverage',93/3);marker('e1-sale',93-3/.1);marker('e11-assets',5/.2);marker('e11-sale',95-5/.2)
    c1,c2,x=planner(.25,1.44,.1);u=lambda c:-1/(c+.1)
    marker('deposit-c1',c1);marker('deposit-c2',c2);marker('deposit-storage',x);marker('deposit-utility',.25*u(c1)+.75*u(c2));marker('autarky-utility',.25*u(1)+.75*u(1.44))
    serve=1/c1;lottery=serve*u(c1)+(1-serve)*u(0)
    marker('run-probability',serve);marker('run-utility',lottery);marker('e4-patient-utility',u(c2))
    truth(u(0)<lottery<u(c2),'run comparison');truth(c2>c1>1,'two equilibrium incentives');truth(.25*u(c1)+.75*u(c2)>.25*u(1)+.75*u(1.44),'insurance welfare')
    changed=planner(.5,1.44,.1);marker('e2-consumption',changed[:2]);marker('e2-storage',changed[2]);G=c1+.05;marker('e6-guarantee',G)
    # Planner global optimality and incentive accounting under multiple primitive changes.
    for lam,R,k in ((.25,1.44,.1),(.5,1.44,.1),(.1,2,.05),(.8,1.2,.2)):
        a,b,storage=planner(lam,R,k);util=lambda c:-1/(c+k);opt=lam*util(a)+(1-lam)*util(b)
        close(lam*a+(1-lam)*b/R,1);close(1/(a+k)**2,R/(b+k)**2);close(R*(1-storage),(1-lam)*b)
        for j in range(21):
            ca=j/(20*lam);cb=R*(1-lam*ca)/(1-lam)
            truth(opt>=lam*util(ca)+(1-lam)*util(cb)-1e-12,'global planner allocation')
    total=1.44*(1-x)+x
    for j in range(26):
        w=.25*j/25;wait=(total-w*c1)/(1-w)
        close(wait-c1,.75*(c2-c1)/(1-w));truth(wait>c1,'suspension every sampled mass')
        mass=j/25
        for bankpay in (0,.5,G,c2):truth(mass*max(G-bankpay,0)<=G+1e-12,'funded guarantee')
    truth(c1<G<c2,'good equilibrium zero topup');close(.4-.25,.15)
    roots=feedback(.805,.2);truth(len(roots)==2,'two feasible roots')
    for key,col in (('sale-roots',0),('sale-prices',1),('sale-equities',2),('sale-debts',3),('sale-slopes',4)):marker(key,tuple(r[col] for r in roots))
    flat=feedback(.805,.1);truth(len(flat)==1,'single feasible flatter root');marker('e7-sale',flat[0][0]);marker('e7-price',flat[0][1])
    peak=.5;bound=(peak+4)*(1-.2*peak)/5;marker('sale-debt-boundary',bound);marker('e8-slope',5*bound*.2/(1-.2*peak)**2)
    # Floating root tangency verified directly, without making rounded discriminant a theorem.
    close((peak+4)*(1-.2*peak),5*.81);truth((peak+4)*(1-.2*peak)<5*.82,'no root at high debt')
    for D,alpha,rs in ((.805,.2,roots),(.805,.1,flat),(.81,.2,[(.5,.9,.09,.36,1)])):
        for z,p,n,debt,slope in rs:
            close(p,1-alpha*z);close(p*(1-z)-debt,n);close(p*(1-z),5*n);close(z,5*D/p-4);close(debt+p*z,D)
            truth(0<z<1 and min(p,n,debt)>0,'economic feasibility')
            # Central difference is separate from analytic feedback derivative.
            h=1e-6;F=lambda t:5*D/(1-alpha*t)-4
            close((F(z+h)-F(z-h))/(2*h),slope)
    truth(roots[0][-1]<1<roots[1][-1],'specified update regimes')
    base=dealers(1.2,.04,(2,2),(1.5,3),2);shock=dealers(1.2,.04,(2,2),(.54,3),2);deep=dealers(1.2,.04,(2,2),(.265,3),2)
    marker('dealer-base-price',base[0]);marker('dealer-base-premium',1.2/base[0]-1);marker('dealer-shock-price',shock[0]);marker('dealer-shock-premium',1.2/shock[0]-1)
    marker('e9-price',deep[0]);marker('e9-holdings',deep[1]);marker('e9-premium',1.2/deep[0]-1);marker('e10-capacity',base[0]*base[1][0])
    for mu,var,aa,cc,X in ((1.2,.04,(2,2),(1.5,3),2),(1.2,.04,(2,2),(.54,3),2),(1.2,.04,(2,2),(.265,3),2),(1.2,.04,(2,2),(.1,.2),2),(2,.1,(1,3),(.2,5),3)):
        p,hold,bind=dealers(mu,var,aa,cc,X);close(sum(hold),X);close(sum(p*z for z in hold),p*X)
        for a,C,z,active in zip(aa,cc,hold,bind):
            truth(0<=z<=C/p+1e-12,'dealer feasible');grad=mu-p-a*var*z
            truth(grad>=-1e-12 if active else abs(grad)<1e-12,'dealer KKT')
            obj=lambda t:(mu-p)*t-a*var*t*t/2
            for j in range(11):truth(obj(z)>=obj(j*C/(10*p))-1e-12,'global CARA-normal optimum')
            # Expected exponential utility factors in wealth and preserves the same ordering.
            for W in (0,3):
                eu=lambda t:-math.exp(-a*W-a*(mu-p)*t+a*a*var*t*t/2)
                truth(eu(z)>=eu(0)-1e-12,'wealth-independent optimum')
    need(seen==set(d.mark),'every numerical marker checked')
    invalid=[(number,(True,)),(number,(float('inf'),)),(numeric,('f(1)',)),(numeric,('1/0',)),(bisect,(lambda z:z*z+1,-1,1)),(bisect,(lambda z:z,1,0)),(planner,(0,1.44,.1)),(planner,(1,1.44,.1)),(planner,(.25,1,.1)),(planner,(.25,1.44,0)),(planner,(.25,1.44,100)),(feedback,(-1,.2)),(feedback,(.8,0)),(feedback,(.8,1)),(dealers,(1,0,(2,),(1,),1)),(dealers,(1,.1,(0,),(1,),1)),(dealers,(1,.1,(2,),(0,),1)),(dealers,(1,.1,(2,),(1,),5)),(dealers,(1,.1,(2,),(1,),0)),(dealers,(1,.1,(2,3),(1,),1))]
    for fn,args in invalid:
        try:fn(*args)
        except (ValueError,ZeroDivisionError):rejections+=1
        else:raise ValueError('invalid domain accepted '+fn.__name__)
    result=dict(chapter='v14-c09',status='passed',comparisons=comparisons,domain_rejections=rejections,worked_examples=5,solutions=12,result_markers=len(d.mark),runtime_files=6,method='Independent planner and sale-root bisection; exhaustive dealer-cap regime equations; no author code imported or executed')
    json.dumps(result,allow_nan=False);return result
if __name__=='__main__':check()
