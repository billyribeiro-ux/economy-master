"""Original fiscal/default laboratory; four runtime files, no writes/network."""
import ast
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
import json
from math import isfinite,log
from pathlib import Path
FILES=('production/v14-c06-working.html','production/check_v14_c06_working.py','production/v14-c06-sources-working.json','production/v14-c06-author-review-working.json')
def require(ok,message):
    if not ok:raise ValueError(message)
def scalar(x):
    require(type(x) in (int,float,F) and isfinite(float(x)),'finite numeric scalar');return float(x)
def tax(Y0,Y1,R,beta,D,lower=0):
    Y0,Y1,R,beta,D,lower=map(scalar,(Y0,Y1,R,beta,D,lower))
    require(min(Y0,Y1,R,beta,D)>0 and lower>=0,'tax domain')
    require(lower<=D/Y0,'infeasible nonnegative-tax financing')
    t0=max(lower,D/(Y0+Y1/(beta*R*R)));t1=R*(D-Y0*t0)/Y1
    return t0,t1,(Y0*t0*t0+beta*Y1*t1*t1)/2
def debt_ratio(R,G,d,s):
    R,G,d,s=map(scalar,(R,G,d,s));require(R>0 and G>0,'positive gross factors');return R/G*d-s
def price(L,R,s):
    L,R,s=map(scalar,(L,R,s));require(L>0 and R>1 and s>0,'positive finite fiscal backing');return L*(R-1)/(s*R)
def local(R,gamma,phi,bbar,x):
    R,gamma,phi,bbar,x=map(scalar,(R,gamma,phi,bbar,x))
    require(R>1 and 0<=gamma<=R and phi>=0 and bbar>0,'local rule domain');a=R-gamma
    require(abs(a-1)>1e-12 and abs(phi-1)>1e-12,'unit-root boundary excluded')
    if phi>1 and a<1:return 'unique monetary',0.,a*x
    if phi<1 and a>1:return 'unique fiscal',a*x/(R*bbar),0.
    if phi<1 and a<1:return 'indeterminate',None,None
    return ('exceptional zero' if x==0 else 'no bounded path'),None,None

def default_menu(y0,beta,R,ys,ks,probs,debts):
    y0,beta,R=map(scalar,(y0,beta,R));ys=tuple(map(scalar,ys));ks=tuple(map(scalar,ks));probs=tuple(map(scalar,probs));debts=tuple(map(scalar,debts))
    require(y0>0 and 0<beta<1 and R>0,'default primitive domain')
    require(len(ys)==len(ks)==len(probs)>0,'state shapes')
    require(all(y>k>=0 for y,k in zip(ys,ks)),'positive exclusion consumption')
    require(all(p>=0 for p in probs) and abs(sum(probs)-1)<1e-12,'probability simplex')
    require(bool(debts) and 0 in debts and all(d>=0 for d in debts) and len(set(debts))==len(debts),'debt menu domain')
    rows=[]
    for d in debts:
        repay=tuple(d<=k for k in ks)
        q=sum(p*yes for p,yes in zip(probs,repay))/R;c=y0+q*d
        ev=sum(p*log(y-d if yes else y-k) for y,k,p,yes in zip(ys,ks,probs,repay))
        rows.append({'debt':d,'repay':repay,'price':q,'current':c,'value':log(c)+beta*ev})
    return rows,max(rows,key=lambda z:(z['value'],-z['debt']))['debt']

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
    b=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    payload={p:(b/p).read_bytes() for p in FILES};doc=Read();doc.feed(payload[FILES[0]].decode());require(not doc.stack,'unclosed HTML')
    require(len(doc.ids)==len(set(doc.ids)) and all(x.startswith('v14-c06-') for x in doc.ids),'IDs')
    target=[f'v14-c06-e{i}' for i in range(1,13)];require(doc.prompts==doc.solutions==target,'12 exact pairs');require(doc.worked==[f'v14-c06-w{i}' for i in range(1,6)],'five cases')
    src=json.loads(payload[FILES[2]]);require(doc.sources=={s['id']:s['url'] for s in src['sources']},'source routes')
    rev=json.loads(payload[FILES[3]]);require(set(rev['exact_prompt_solution_audit'])==set(target),'prompt review')
    require({x['path'] for x in rev['payload_bindings']}==set(FILES[:3]) and len(rev['payload_bindings'])==3,'author bindings')
    for x in rev['payload_bindings']:require((len(payload[x['path']]),sha256(payload[x['path']]).hexdigest())==(x['bytes'],x['sha256']),'binding mismatch')
    ins={k:parse(v[1]) for k,v in doc.markers.items() if v[0]=='data-input'};vals={k:parse(v[1]) for k,v in doc.markers.items() if v[0]=='data-calc'};count=0;rejections=0
    def near(a,b,label='comparison',tol=6e-11):
        nonlocal count
        if isinstance(b,(tuple,list)):
            require(isinstance(a,(tuple,list)) and len(a)==len(b),label+' shape')
            for x,y in zip(a,b):near(x,y,label,tol)
        else:
            require(isfinite(float(a)) and abs(float(a)-float(b))<tol*max(1,abs(float(b))),f'{label}: {a} != {b}');count+=1
    expected_ins={'debt-parameters':(1.05,1.02,.8,.03),'tax-parameters':(100,120,1.05,20/21,40),'nominal-parameters':(100,1.05,3,2.4),'default-grid':(0,.2,.5,.8)}
    require(set(ins)==set(expected_ins),'input names')
    for k,v in expected_ins.items():near(ins[k],v,k)
    R,G,d,s=ins['debt-parameters'];Y0,Y1,tr,tb,D=ins['tax-parameters'];t0,t1,loss=tax(Y0,Y1,tr,tb,D);ca=tax(Y0,Y1,tr,tb,D,.3);L,nR,ss,ssnew=ins['nominal-parameters']
    rows,best=default_menu(.5,.9,1.05,(.8,1.4),(.15,.6),(.5,.5),ins['default-grid']);stress,sbest=default_menu(.5,.9,1.05,(.8,1.4),(.15,.6),(.75,.25),ins['default-grid']);ext,ebest=default_menu(.5,.9,1.05,(.8,1.4),(.15,.6),(.5,.5),(0,.15,.2,.5,.8));added=next(z for z in ext if z['debt']==.15);e3=tax(100,100,1,.5,30)
    expected={'debt-ratio':debt_ratio(R,G,d,s),'stabilizing-share':(R/G-1)*d,'stress-ratio':debt_ratio(1.10,G,d,s),'fiscal-root':R-.1,'fiscal-five':10*(R-.1)**5,
    'tax-rate':t0,'tax-receipts':(Y0*t0,Y1*t1),'tax-debt':D-Y0*t0,'tax-loss':loss,'tax-cap-rates':ca[:2],'tax-cap-loss':ca[2],'tax-cap-gap':ca[2]-loss,
    'backing':ss*nR/(nR-1),'price-original':price(L,nR,ss),'backing-new':ssnew*nR/(nR-1),'price-new':price(L,nR,ssnew),'price-change':ss/ssnew-1,'real-debt-pair':(ss/(nR-1),ssnew/(nR-1)),
    'regime-passive-x0':(R-.1)*.6,'regime-selected-p':(R-.02)*.6/(R*60),'regime-exact-inflation':R*60.6/(R*60+.02*.6),
    'default-prices':tuple(z['price'] for z in rows),'default-current-consumption':tuple(z['current'] for z in rows),'default-values':tuple(z['value'] for z in rows),'default-expected-repayment':.5*.5,'default-proceeds':.5*.5/1.05,'default-stress-price':.25/1.05,'default-stress-values':tuple(z['value'] for z in stress),
    'e2-debt':debt_ratio(1.06,1.03,.7,.02),'e2-share':(1.06/1.03-1)*.7,'e2-root':1.06-.08,'e3-rates':e3[:2],'e3-loss':e3[2],'e4-rates':(.4,0),'e4-loss':.5*100*.4**2,'e6-backing':4*1.1/.1,'e6-price':price(120,1.1,4),'e6-debt':4/.1,'e9-price':added['price'],'e9-consumption':added['current'],'e9-value':added['value'],'e10-price':(.5+.5*.4)/1.05,'e10-guarantee':.5*.4*.5}
    require(set(expected)==set(vals),'all displayed results')
    for k,v in expected.items():near(vals[k],v,k)
    require((best,sbest,ebest)==(.5,0,.15),'full menu optima');count+=3
    # Exact rational fiscal accounts, every candidate financing equality and global cost differences.
    near(F(1349,1700),vals['debt-ratio']);near(F(2,85),vals['stabilizing-share']);near(F(14,75),t0);near(F(56,15),loss);near(F(79,16),ca[2]);near(F(289,240),ca[2]-loss)
    for prm in ((100,120,1.05,20/21,40),(80,130,1.1,.8,25),(100,100,1,.5,30)):
        y0,y1,r,bb,dd=prm;a,z,l=tax(*prm)
        near(y0*a+y1*z/r,dd);near(bb*r*z,a)
        for f in (.2,.8,1.2,1.6):
            alt=a*f
            if alt<=dd/y0:
                future=r*(dd-y0*alt)/y1;gap=(y0*alt**2+bb*y1*future**2)/2-l
                near(gap,(y0*(alt-a)**2+bb*y1*(future-z)**2)/2)
                require(gap>=-1e-12,'global convex cost');count+=1
    for lo in (0,.1,.2,.3,.4):
        a,z,l=tax(100,120,1.05,20/21,40,lo);near(100*a+120*z/1.05,40);require(a>=lo-1e-12 and z>=-1e-12,'cap feasibility');count+=1
    # Finite telescoping with nonconstant gross returns and signed surpluses.
    debt=F(10);discount=F(1);pv=F(0)
    for rr,sur in zip((F(11,10),F(21,20),F(6,5)),(F(2),F(-1),F(4))):
        debt=rr*debt-sur;discount/=rr;pv+=discount*sur;near(pv+discount*debt,10)
    # Distinct local regimes and exact nominal timing.
    require(local(R,.1,1.5,60,.6)[0]=='unique monetary','M regime');require(local(R,.02,.5,60,.6)[0]=='unique fiscal','F regime');require(local(R,.1,.5,60,.6)[0]=='indeterminate','stable pair');require(local(R,.02,1.5,60,.6)[0]=='no bounded path','unstable pair');count+=4
    pi=R*60.6/(R*60+.02*.6);debt=R*60.6/pi-3-.02*.6;near(debt,60)
    for _ in range(20):
        nominal=R*pi**.5;nextpi=pi**.5;near(nominal/nextpi,R);debt=nominal/nextpi*debt-(3+.02*(debt-60));near(debt,60);pi=nextpi
    # Lender break-even, resource clearing and whole-menu values at multiple probabilities.
    for ph in (.1,.25,.5,.75,.9):
        rr,_=default_menu(.5,.9,1.05,(.8,1.4),(.15,.6),(1-ph,ph),(0,.15,.2,.5,.8))
        for z in rr:
            expected_payment=z['debt']*sum(p*h for p,h in zip((1-ph,ph),z['repay']))
            near(expected_payment,1.05*z['price']*z['debt']);near(z['current']-.5,z['price']*z['debt'])
    # Current default cannot improve on the zero-issue option in the case.
    immediate=log(.4)+.9*(log(.65)+log(.8))/2;require(immediate<rows[0]['value'],'current default domination');count+=1
    # Liquidity counterexample: separate concave optima rather than an assertion of aggregate neutrality.
    for e0,e1 in ((1,3),(1.5,2.5)):
        require(-1/e0+1/e1<0,'binding no-borrowing derivative');near(e0+e1,4);count+=1
    invalid=[lambda:tax(0,100,1,1,30),lambda:tax(100,100,0,1,30),lambda:tax(100,100,1,0,30),lambda:tax(100,100,1,1,30,.31),lambda:tax(100,100,1,1,-1),lambda:debt_ratio(1,0,1,0),lambda:price(1,1,1),lambda:price(1,.9,1),lambda:price(1,1.1,0),lambda:local(1.05,.05,.5,60,.6),lambda:local(1.05,.1,1,60,.6),lambda:local(1.05,-.1,.5,60,.6),lambda:scalar(True),lambda:scalar(float('nan')),lambda:parse('__import__("os")'),lambda:parse('True'),lambda:default_menu(.5,.9,1.05,(.8,1.4),(.15,.6),(.5,.4),(0,.2)),lambda:default_menu(.5,.9,1.05,(.8,1.4),(.8,.6),(.5,.5),(0,.2)),lambda:default_menu(.5,.9,1.05,(.8,1.4),(.15,.6),(.5,.5),(.2,)),lambda:default_menu(.5,.9,1.05,(.8,1.4),(.15,.6),(.5,.5),(0,.2,.2)),lambda:default_menu(.5,1,1.05,(.8,1.4),(.15,.6),(.5,.5),(0,.2))]
    for f in invalid:
        try:f()
        except (ValueError,ZeroDivisionError):rejections+=1
        else:raise ValueError('invalid primitive accepted')
    return {'chapter':'v14-c06','status':'passed','comparisons':count,'domain_rejections':rejections,'worked_cases':5,'solved_exercises':12,'primitive_markers':len(ins),'result_markers':len(vals),'runtime_files':4,'scope':'Exact dated fiscal accounts, global reduced-form tax optimum, conditional deterministic policy classification and finite-horizon debt-menu equilibrium; not a general infinite-horizon default existence or empirical policy result.'}
if __name__=='__main__':check()
