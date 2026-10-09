"""Original intermediary models; quiet four-file portable checks."""
import ast,json
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from math import isfinite,sqrt,exp
from pathlib import Path
FILES=('content/chapters/v14-c09.html','scripts/check_v14_c09.py','content/reviews/v14-c09-sources.json','content/reviews/v14-c09-author.json')
def require(ok,message):
    if not ok:raise ValueError(message)
def scalar(x):
    require(type(x) in (int,float,F) and isfinite(float(x)),'finite numeric scalar');return float(x)
def insurance(lam,R,kappa):
    lam,R,kappa=map(scalar,(lam,R,kappa));require(0<lam<1 and R>1 and kappa>0,'insurance domain')
    c1=(1-(1-lam)/R*(sqrt(R)-1)*kappa)/(lam+(1-lam)/sqrt(R));c2=sqrt(R)*c1+(sqrt(R)-1)*kappa
    require(c1>0 and c2>0 and 0<lam*c1<1,'interior allocation');return c1,c2,lam*c1

def sales(K,D,L,p0,alpha):
    K,D,L,p0,alpha=map(scalar,(K,D,L,p0,alpha));require(K>0 and D>=0 and L>1 and p0>0 and alpha>0,'sale primitives')
    aa=alpha;bb=alpha*(L-1)*K-p0;cc=L*D-(L-1)*K*p0;disc=bb*bb-4*aa*cc
    if disc< -1e-12:return []
    roots=((-bb-sqrt(max(0,disc)))/(2*aa),(-bb+sqrt(max(0,disc)))/(2*aa));valid=[]
    for z in roots:
        p=p0-alpha*z;n=p*K-D;debt=D-p*z
        if 0<=z<=K and p>0 and n>0 and debt>=-1e-12 and all(abs(z-r[0])>1e-10 for r in valid):valid.append((z,p,n,debt,p*(K-z),L*D*alpha/(p*p)))
    return valid

def demand(mu,var,a,C,p):
    mu,var,a,C,p=map(scalar,(mu,var,a,C,p));require(mu>0 and var>0 and a>0 and C>0 and p>0,'dealer primitives')
    return min(max((mu-p)/(a*var),0),C/p)
def clear(mu,var,risk,caps,X):
    mu,var,X=map(scalar,(mu,var,X));risk=tuple(map(scalar,risk));caps=tuple(map(scalar,caps));require(mu>0 and var>0 and len(risk)==len(caps)>0 and min(risk+caps)>0,'market primitives')
    require(0<X<sum(mu/(a*var) for a in risk),'strict supply bound')
    lo,hi=0.,mu
    for _ in range(100):
        p=(lo+hi)/2
        if sum(demand(mu,var,a,C,p) for a,C in zip(risk,caps))>X:lo=p
        else:hi=p
    p=(lo+hi)/2;return p,tuple(demand(mu,var,a,C,p) for a,C in zip(risk,caps))

class Read(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.stack=[];self.ids=[];self.worked=[];self.prompts=[];self.solutions=[];self.markers={};self.sources={}
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if 'id' in a:self.ids.append(a['id'])
        if 'worked' in a.get('class','').split():self.worked.append(a['id'])
        if tag=='li' and any(t=='ol' and 'exercises' in q.get('class','').split() for t,q in self.stack):self.prompts.append(a['id'])
        if 'data-solution-for' in a:
            require(any(t=='details' and 'solutions' in q.get('class','').split() for t,q in self.stack),'undisclosed answer');self.solutions.append(a['data-solution-for'])
        if 'data-source' in a:self.sources[a['data-source']]=a['href']
        for attr in ('data-calc','data-input'):
            if attr in a:
                require(a[attr] not in self.markers,'duplicate marker');self.markers[a[attr]]=[attr,'']
        if tag not in ('br','hr','img','meta','link','input'):self.stack.append((tag,a))
    def handle_data(self,text):
        for _,a in self.stack:
            for attr in ('data-calc','data-input'):
                if attr in a:self.markers[a[attr]][1]+=text
    def handle_endtag(self,tag):
        require(self.stack and self.stack[-1][0]==tag,'HTML nesting');self.stack.pop()
def parse(s):
    def walk(n):
        if isinstance(n,ast.Constant):return scalar(n.value)
        if isinstance(n,(ast.Tuple,ast.List)):return tuple(walk(x) for x in n.elts)
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,(ast.UAdd,ast.USub)):return (-1 if isinstance(n.op,ast.USub) else 1)*walk(n.operand)
        if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Div):return walk(n.left)/walk(n.right)
        raise ValueError('numeric marker syntax')
    return walk(ast.parse(s.strip(),mode='eval').body)

def check(root=None):
    b=Path(root) if root is not None else Path(__file__).resolve().parents[1];payload={p:(b/p).read_bytes() for p in FILES};doc=Read();doc.feed(payload[FILES[0]].decode())
    require(not doc.stack and len(doc.ids)==len(set(doc.ids)) and all(i.startswith('v14-c09-') for i in doc.ids),'HTML and IDs')
    targets=[f'v14-c09-e{i}' for i in range(1,13)];require(doc.prompts==doc.solutions==targets,'12 exact pairs');require(doc.worked==[f'v14-c09-w{i}' for i in range(1,6)],'five cases')
    src=json.loads(payload[FILES[2]]);require(doc.sources=={s['id']:s['url'] for s in src['sources']},'source routing');rev=json.loads(payload[FILES[3]])
    require(set(rev['exact_prompt_solution_audit'])==set(targets),'all prompt audit');require(len(rev['payload_bindings'])==3 and {x['path'] for x in rev['payload_bindings']}==set(FILES[:3]),'three bindings')
    for x in rev['payload_bindings']:require((len(payload[x['path']]),sha256(payload[x['path']]).hexdigest())==(x['bytes'],x['sha256']),'payload hash')
    vals={k:parse(v[1]) for k,v in doc.markers.items()};count=0;rejections=0
    def near(x,y,label='comparison',tol=6e-11):
        nonlocal count
        if isinstance(y,(tuple,list)):
            require(isinstance(x,(tuple,list)) and len(x)==len(y),label+' shape')
            for xx,yy in zip(x,y):near(xx,yy,label,tol)
        else:
            require(isfinite(float(x)) and abs(float(x)-float(y))<tol*max(1,abs(float(y))),f'{label}: {x} != {y}');count+=1
    c1,c2,store=insurance(.25,1.44,.1);u=lambda c:-1/(c+.1);prob=1/c1;run=prob*u(c1)+(1-prob)*u(0);roots=sales(1,.805,5,1,.2);flat=sales(1,.805,5,1,.1);pb,xb=clear(1.2,.04,(2,2),(1.5,3),2);ps,xs=clear(1.2,.04,(2,2),(.54,3),2);pe,xe=clear(1.2,.04,(2,2),(.265,3),2);cc1,cc2,xx=insurance(.5,1.44,.1)
    expected={'balance-leverage':95/5,'balance-sale':95-10*5,'balance-cash-injection':(95-10*5)/(10-1),
              'deposit-c1':c1,'deposit-c2':c2,'deposit-storage':store,'deposit-utility':.25*u(c1)+.75*u(c2),'autarky-utility':.25*u(1)+.75*u(1.44),'run-probability':prob,'run-utility':run,
              'sale-roots':tuple(r[0] for r in roots),'sale-prices':tuple(r[1] for r in roots),'sale-equities':tuple(r[2] for r in roots),'sale-debts':tuple(r[3] for r in roots),'sale-slopes':tuple(r[5] for r in roots),'sale-debt-boundary':4.05/5,
              'dealer-base-price':pb,'dealer-base-premium':1.2/pb-1,'dealer-shock-price':ps,'dealer-shock-premium':1.2/ps-1,
              'e1-leverage':93/3,'e1-sale':93-30,'e2-consumption':(cc1,cc2),'e2-storage':xx,'e4-patient-utility':u(c2),'e6-guarantee':c1+.05,'e7-sale':flat[0][0],'e7-price':flat[0][1],'e8-slope':5*.81*.2/.9**2,
              'e9-price':pe,'e9-holdings':xe,'e9-premium':1.2/pe-1,'e10-capacity':pb,'e11-assets':5/.2,'e11-sale':95-5/.2}
    require(set(vals)==set(expected),'every visible result')
    for key,value in expected.items():near(vals[key],value,key)
    # Exact rational insurance, welfare and queue calculation.
    one=F(95,84);two=F(241,175);R=F(36,25);k=F(1,10);lam=F(1,4);uf=lambda c:-1/(c+k)
    near((c1,c2,store),(one,two,lam*one));near(lam*one+(1-lam)*two/R,1);near(1/(one+k)**2,R/(two+k)**2)
    near(lam*uf(one)+(1-lam)*uf(two),F(-735,1034));near(lam*uf(1)+(1-lam)*uf(R),F(-5,7));near(uf(one)/one+(1-1/one)*uf(0),F(-970,517))
    require(u(0)<run<u(c2) and .25*u(c1)+.75*u(c2)>.25*u(1)+.75*u(1.44),'incentive and welfare order');count+=1
    for fraction in (.1,.25,.5,.9):
        a,z,x=insurance(fraction,1.44,.1);near(fraction*a+(1-fraction)*z/1.44,1);near(1/(a+.1)**2,1.44/(z+.1)**2)
        optimum=fraction*u(a)+(1-fraction)*u(z)
        for ratio in (.2,.8,1.1):
            alt=a*ratio;later=1.44*(1-fraction*alt)/(1-fraction)
            if later>=0:require(optimum>=fraction*u(alt)+(1-fraction)*u(later)-1e-12,'global insured allocation');count+=1
    # Suspension at every sampled withdrawal mass and fully funded off-path guarantees.
    total=1.44*(1-store)+store;G=c1+.05
    for j in range(101):
        w=.25*j/100;waiting=(total-w*c1)/(1-w)
        near(waiting-c1,.75*(c2-c1)/(1-w));require(waiting>c1,'suspension waiting incentive');count+=1
        mass=j/100
        for payment in (0,.5,G,c2):
            transfer=mass*max(G-payment,0);require(0<=transfer<=G+1e-12,'guarantor capacity');count+=1
    require(G<c2 and G>c1,'normal zero-transfer guarantee');count+=1
    # All sale roots: buyer FOC, cap, original balance-sheet identity and debt repayment.
    for D,alpha in ((.805,.2),(.805,.1),(.81,.2)):
        for z,p,n,debt,assets,slope in sales(1,D,5,1,alpha):
            near(p,1-alpha*z);near(assets-debt,n);near(assets,5*n);near(debt+p*z,D);near(z,5*D/p-4);require(min(p,n,debt)>0 and 0<z<1,'economic root domain');count+=1
    require(len(roots)==2 and len(flat)==1 and len(sales(1,.81,5,1,.2))==1 and sales(1,.82,5,1,.2)==[],'root regimes');count+=1
    def update(z):return 5*.805/(1-.2*z)-4
    for root in roots:
        z=root[0];h=1e-6;near((update(z+h)-update(z-h))/(2*h),root[5],tol=1e-8)
    iterate=0.
    for _ in range(300):iterate=update(iterate)
    near(iterate,roots[0][0],tol=1e-9)
    require(roots[0][5]<1<roots[1][5],'iteration-only local stability');count+=1
    # Dealer demand globally optimizes the quadratic and the exact exponential objective.
    for caps in ((1.5,3),(.54,3),(.265,3),(.1,.2),(5,5)):
        p,hold=clear(1.2,.04,(2,2),caps,2);near(sum(hold),2)
        for C,x in zip(caps,hold):
            cap=C/p;grad=1.2-p-.08*x
            require(0<=x<=cap+1e-12 and (abs(grad)<1e-12 or (abs(x-cap)<1e-12 and grad>=0)),'dealer KKT');count+=1
            objective=lambda z:(1.2-p)*z-.04*z*z
            utility=lambda z:-exp(-2*(1.2-p)*z+2*.04*z*z)
            for z in (0,cap/2,cap):
                require(objective(x)>=objective(z)-1e-12 and utility(x)>=utility(z)-1e-12,'exact CARA optimum');count+=1
        near(sum(p*x for x in hold),p*2)
    near(xb,(1,1));near(xs,(.5,1.5));near(xe,(.25,1.75))
    # Loss, sale and both injection uses reconcile equity, never treating debt repayment as new output.
    for loss,h in ((5,.1),(7,.1),(5,.2)):
        assets=100-loss;equity=10-loss;sale=assets-equity/h;debt=90-sale;near((assets-sale)-debt,equity);near(assets-sale,equity/h)
    near(95-85.5,9.5);near(95/9.5,10);near((95+5)/(5+5),10)
    bad=(lambda:insurance(0,1.44,.1),lambda:insurance(.25,1,.1),lambda:insurance(.25,1.44,0),lambda:insurance(.25,1.44,100),lambda:sales(0,.8,5,1,.2),lambda:sales(1,.8,1,1,.2),lambda:sales(1,.8,5,1,0),lambda:demand(1,0,2,1,1),lambda:demand(1,.1,0,1,1),lambda:demand(1,.1,2,0,1),lambda:demand(1,.1,2,1,0),lambda:clear(1,.1,(2,),(1,),5),lambda:clear(1,.1,(2,),(1,),0),lambda:clear(1,.1,(2,3),(1,),1),lambda:scalar(True),lambda:scalar(float('nan')))
    for fn in bad:
        try:fn()
        except ValueError:rejections+=1
        else:raise ValueError('invalid domain accepted')
    return {'chapter':'v14-c09','status':'passed','comparisons':count,'domain_rejections':rejections,'worked_examples':5,'solutions':12,'result_markers':len(vals),'runtime_files':4}

if __name__=='__main__':
    check()

