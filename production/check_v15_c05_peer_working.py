"""Independent trade peer oracle: no execution or import of author code."""
from pathlib import Path
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from itertools import product
from math import isfinite
import ast,json
FILES=('production/v15-c05-working.html','production/check_v15_c05_working.py','production/v15-c05-sources-working.json','production/v15-c05-author-review-working.json','production/check_v15_c05_peer_working.py','production/v15-c05-peer-review-working.json')
def ensure(ok,msg):
    if not ok:raise ValueError(msg)
def real(x):ensure(type(x) in (int,float,F) and isfinite(x),'finite real');return F(str(x))
def parse(s):
    def visit(n):
        if isinstance(n,ast.Constant):return real(n.value)
        if isinstance(n,(ast.Tuple,ast.List)):return tuple(visit(z) for z in n.elts)
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,ast.USub):return -visit(n.operand)
        if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Div):return visit(n.left)/visit(n.right)
        raise ValueError('numeric literal only')
    return visit(ast.parse(s.split('=',1)[-1].strip(),mode='eval').body)
def strict(raw):
    def pairs(rows):
        out={}
        for k,v in rows:ensure(k not in out,'unique JSON key');out[k]=v
        return out
    def fail(s):raise ValueError('finite JSON')
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=fail)
def solve2(a,b):
    ensure(len(a)==len(b)==2 and all(len(row)==2 for row in a),'two by two shape');a=tuple(tuple(map(real,row)) for row in a);b=tuple(map(real,b));det=a[0][0]*a[1][1]-a[0][1]*a[1][0];ensure(det!=0,'nonsingular');return ((b[0]*a[1][1]-a[0][1]*b[1])/det,(a[0][0]*b[1]-b[0]*a[1][0])/det)
def exporter(B,w,fee,phi,tau,sunk=False):
    B,w,fee,phi,tau=map(real,(B,w,fee,phi,tau));ensure(min(B,w,fee,phi)>0 and tau>=1 and type(sunk)is bool,'export domain');cost=w*tau/phi;price=2*cost;q=B/price**2;revenue=price*q;contribution=revenue-cost*q;actions=(q,) if sunk or contribution>fee else (F(0),q) if contribution==fee else (F(0),);return actions,(q,price,tau*q,tau*q/phi,revenue,contribution-fee)
def network(a,b,vh,vf,y,th=0,tf=0):
    a,b,vh,vf,y,th,tf=map(real,(a,b,vh,vf,y,th,tf));ensure(min(a,b,th,tf)>=0 and a*b<1 and min(vh,vf,y)>0,'productive nonnegative network');xh,xf=solve2(((1,-a),(-b,1)),(y,0));ph,pf=solve2(((1,-b),(-a,1)),(vh+b*th,vf+a*tf));gh=th*b*xh;gf=tf*a*xf;vah=vh*xh;vaf=vf*xf;return xh,xf,ph,pf,vah,vaf,gh,gf,(vah+gh)/ph,(vaf+gf)/ph

def processing(tout,tin):
    tout,tin=map(real,(tout,tin));ensure(0<=tout<=4 and 0<=tin<=4,'import parity rectangle');D=10-tout;q=max(F(0),2+tout-tin);M=D-q;C=2*q+q*q/2;profit=(10+tout-6-tin)*q-C;gov=tout*M+tin*q;utility=20*D-D*D/2;W=utility-C-10*M-6*q;return D,q,M,q,gov,profit,W,F(52)-W,(tout-tin)/4

def movement(old,intercept,slope,maximum,subsidy=0,reduction=1,fee=0,training=0):
    old,intercept,slope,maximum,subsidy,reduction,fee,training=map(real,(old,intercept,slope,maximum,subsidy,reduction,fee,training));ensure(old>=0 and intercept>0 and slope>0 and maximum>0 and reduction>0 and min(subsidy,fee,training)>=0,'moving domain');m=max(F(0),min(F(1),(intercept-old+subsidy-fee)/(slope+reduction*maximum)));w=intercept-slope*m;output=intercept*m-slope*m*m/2;moving=reduction*maximum*m*m/2;W=old*(1-m)+output-moving-training*m;tax=(subsidy+training-fee)*m;profit=output-w*m;return m,w,W,tax,profit

def slope(x,y):
    ensure(len(x)==len(y)>1,'regression dimensions');x=tuple(map(real,x));y=tuple(map(real,y));mx=sum(x)/len(x);my=sum(y)/len(y);den=sum((a-mx)**2 for a in x);ensure(den>0,'nonzero exposure variance');return sum((a-mx)*(b-my) for a,b in zip(x,y))/den
class Read(HTMLParser):
    def __init__(self):super().__init__();self.stack=[];self.ids=set();self.mark={};self.prompts=[];self.answers={};self.worked=[];self.sources={};self.links=[]
    def handle_starttag(self,t,attrs):
        a=dict(attrs);ensure(len(a)==len(attrs),'unique attributes')
        if 'id' in a:ensure(a['id'] not in self.ids and a['id'].startswith('v15-c05-'),'scoped unique ID');self.ids.add(a['id'])
        if 'href' in a:self.links.append(a['href'])
        if 'worked' in a.get('class','').split():self.worked.append(a['id'])
        if t=='li' and any('exercises' in a.get('class','').split() for t,a in self.stack):self.prompts.append(a['id'])
        if 'data-solution-for' in a:
            k=a['data-solution-for'];ensure(k not in self.answers and any(t=='details' and 'solutions' in a.get('class','').split() for t,a in self.stack),'unique disclosed solution');self.answers[k]=''
        for attr in ('data-input','data-result'):
            if attr in a:ensure(a[attr] not in self.mark,'unique number');self.mark[a[attr]]=[attr,'']
        if 'data-source' in a:ensure(a['data-source'] not in self.sources,'unique source');self.sources[a['data-source']]=a['href']
        if t not in ('br','hr','img','input','meta','link'):self.stack.append((t,a))
    def handle_data(self,s):
        for t,a in self.stack:
            if 'data-solution-for' in a:self.answers[a['data-solution-for']]+=s
            for attr in ('data-input','data-result'):
                if attr in a:self.mark[a[attr]][1]+=s
    def handle_endtag(self,t):ensure(self.stack and self.stack[-1][0]==t,'balanced markup');self.stack.pop()
def check(root=None):
    base=Path(root) if root is not None else Path(__file__).resolve().parents[1];raw={f:(base/f).read_bytes() for f in FILES};d=Read();d.feed(raw[FILES[0]].decode());d.close();ensure(not d.stack,'complete document');peer=strict(raw[FILES[5]]);source=strict(raw[FILES[2]]);author=strict(raw[FILES[3]]);targets=[f'v15-c05-e{i}' for i in range(1,11)];ensure(d.prompts==list(d.answers)==targets and len(d.worked)==5 and all(len(v)>450 for v in d.answers.values()),'complete chapter package');ensure(set(peer['exact_solution_review'])==set(targets) and not peer['open_findings'],'complete peer review');ensure(d.sources=={s['id']:s['url'] for s in source['sources']},'source routes');ensure('curriculum.html#v15-c06' in d.links,'planned successor route');ensure(set(peer['payload_bindings'])==set(FILES[:5]),'five nonself bindings')
    for f,b in peer['payload_bindings'].items():ensure(len(raw[f])==b['bytes'] and sha256(raw[f]).hexdigest()==b['sha256'],'payload freeze')
    ensure(not author['open_findings'] and set(author['exact_prompt_review'])==set(targets),'complete author audit');bindings=author['payload_bindings'];ensure(len(bindings)==3 and {b['path'] for b in bindings}==set(FILES[:3]),'author nonself bindings')
    for b in bindings:ensure(b['bytes']==len(raw[b['path']]) and b['sha256']==sha256(raw[b['path']]).hexdigest(),'author frozen bytes')
    x={k:parse(v[1]) for k,v in d.mark.items() if v[0]=='data-input'};count=0;rejects=0;seen=set()
    def eq(a,b):
        nonlocal count
        if isinstance(a,(tuple,list)):
            ensure(isinstance(b,(tuple,list)) and len(a)==len(b),'numeric shape')
            for c,e in zip(a,b):eq(c,e)
        else:ensure(isfinite(float(a)) and abs(float(a)-float(b))<1e-9,'numeric equality '+str((a,b)));count+=1
    def mark(k,v):eq(v,parse(d.mark[k][1]));seen.add(k)
    def truth(ok,msg):
        nonlocal count
        ensure(ok,msg);count+=1
    ensure(set(x)=={'firms','network','tariffs','workers','exposure'},'primitive groups');B,w,fee,types=x['firms'];before=[exporter(B,w,fee,p,2) for p in types];after=[exporter(B,w,fee,p,F(3,2)) for p in types];active0=[(p,r) for p,(a,r) in zip(types,before) if a[0]>0];active1=[(p,r) for p,(a,r) in zip(types,after) if a[0]>0]
    sumcol=lambda A,j:sum(r[j] for p,r in A);delivered=sumcol(active1,0);produced=sumcol(active1,2);labor=sumcol(active1,3);mark('firm-after',(delivered,produced,labor,labor+len(active1)*fee/w,sumcol(active1,4),sumcol(active1,5)));mark('firm-selection',(len(active0),len(active1),sum(p for p,r in active0)/len(active0),sum(p for p,r in active1)/len(active1),sumcol(active0,2)/sumcol(active0,3),produced/labor))
    for selected in (active0,active1):
        wages=w*sumcol(selected,3)+len(selected)*fee;profits=sumcol(selected,5);revenue=sumcol(selected,4);eq(wages+profits,revenue);home=100-wages+revenue;foreign=200-revenue;eq(home,100+profits);eq(home+foreign,300-wages)
    choices=[exporter(B,w,12,p,F(3,2)) for p in types];mark('e1-choices',tuple(a for a,r in choices));mark('e1-sunk',tuple(exporter(B,w,12,p,F(3,2),True)[1][5] for p in types));e2=[(p,r) for p in types for a,r in [exporter(16,w,fee,p,1)] if a[0]>0];mark('e2',(len(e2),sumcol(e2,0),sumcol(e2,4),sumcol(e2,5)));truth(all(exporter(8,w,fee,p,1)[0]==(0,) for p in types),'declining sales alternative')
    for B0,phi,tau in product((8,20,36),(1,2,4),(1,F(3,2),2)):
        actions,row=exporter(B0,1,9,phi,tau);q,price,produced,var,rev,profit=row;eq(rev-var,rev/2);eq(q,B0/price**2)
        for scale in (0,F(1,4),F(1,2),1,2,3):
            # Revenue at a scaled square root of q, retaining exact arithmetic.
            alt=rev*scale-var*scale*scale-9;truth(max(0,profit)>=alt,'all-quantity square proof witness')
        if actions[0]>0:truth(profit>0,'strict entrant')
    a,b,vh,vf,y=x['network'];r=network(a,b,vh,vf,y);xh,xf,ph,pf,vah,vaf,gh,gf,home,foreign=r;mark('network-base',r[:6]);r1=network(a,b,vh,vf,y,1);mark('network-tariff',(r1[2],r1[3],r1[6],y*r1[2],r1[8],r1[9]));r2=network(a,b,vh,vf,77);mark('e3',(r2[0],r2[1],r2[4],r2[5],r2[8],r2[9]));r3=network(a,b,vh,vf,y,1,1);mark('e4',(r3[2],r3[3],r3[6],r3[7],y*r3[2],r3[8],r3[9]))
    for aa,bb,Y,th,tf in product((F(1,4),F(1,3)),(F(1,2),F(2,3)),(70,77),(0,1),(0,1)):
        h,f,ph,pf,vh0,vf0,gh,gf,hfinal,ffinal=network(aa,bb,3,2,Y,th,tf);eq(h,aa*f+Y);eq(f,bb*h);eq(ph,3+bb*(pf+th));eq(pf,2+aa*(ph+tf));eq(ph*Y,vh0+vf0+gh+gf);eq(hfinal+ffinal,Y);eq(aa*f*ph+ffinal*ph,bb*h*pf);eq(gh,th*bb*h);eq(gf,tf*aa*f)
    world,component,tout,tin=x['tariffs'];eq((world,component),(10,6));t=processing(tout,tin);mark('tariff-case',(t[0],t[1],t[2],t[4],t[5],t[6],t[7],t[8]));rows=[processing(0,v) for v in (1,4)];mark('e5',tuple((z[1],z[2],z[3],z[4],z[8],z[6]) for z in rows));rows=[processing(2,v) for v in (0,2,3)];mark('e6',(tuple(z[1] for z in rows),tuple(z[7] for z in rows)))
    for tout,tin in product(range(5),repeat=2):
        D,q,M,inputs,G,profit,W,loss,ep=processing(tout,tin);eq(W,F(52)-((D-10)**2+(q-2)**2)/2);truth(M>=0 and q>=0,'nonnegative trade');N=100+profit+G-(10+tout)*D;eq(N+2*q+q*q/2+10*M+6*q,100);truth(N>=0,'financeable consumption');eq(profit,q*q/2)
    old,intercept,slope0,maximum=x['workers'];m0,w0,W0,tax0,profit0=movement(old,intercept,slope0,maximum);m1,w1,W1,tax1,profit1=movement(old,intercept,slope0,maximum,subsidy=1);mark('worker-subsidy',(m0,w0,W0,m1,w1,tax1,W1));free=movement(old,intercept,slope0,maximum,reduction=F(1,2),training=1);paid=movement(old,intercept,slope0,maximum,reduction=F(1,2),fee=1,training=1);mark('worker-training',(free[0],free[2],paid[0],paid[2]));mark('e7',profit1-profit0);mark('e8',(free[2],paid[2],paid[2]-free[2]));eq((maximum-(w1-old+1))/maximum,F(9,16))
    for j in range(21):
        f=F(j,20);m,wnew,W,tax,profit=movement(old,intercept,slope0,maximum,reduction=F(1,2),fee=f,training=1);eq(tax,(1-f)*m);eq(W,F(29,4)-(1-f)**2/20);truth(W<=paid[2],'fee optimum');mtest=F(j,20);resources=old*(1-mtest)+intercept*mtest-slope0*mtest*mtest/2-maximum*mtest*mtest/2;eq(resources,W0-8*(mtest-m0)**2);truth(resources<=W0,'original efficient assignment')
    shares,multiplier,theta,gamma=x['exposure'];exposures=tuple(multiplier*s for s in shares);ys=tuple(100+theta*z+gamma*s for z,s in zip(exposures,shares));observed=slope(exposures,ys);mark('exposure-set',(observed,observed-F(1,2),observed));mark('e9',(observed-1,observed+F(1,2)));mark('e10',-2-F(-1,2))
    for g in [F(j,10) for j in range(-10,21)]:
        t=(multiplier*observed-g)/multiplier;eq(tuple(100+t*z+g*s for z,s in zip(exposures,shares)),ys)
    eq(tuple(z-multiplier*s for z,s in zip(exposures,shares)),(0,0,0))
    for fn in (lambda:real(True),lambda:real(float('nan')),lambda:solve2(((1,0),),(1,)),lambda:solve2(((1,0),(0,0)),(1,2)),lambda:exporter(0,1,9,1,2),lambda:exporter(36,1,9,0,2),lambda:exporter(36,1,9,1,F(1,2)),lambda:network(1,1,3,2,70),lambda:network(-1,0,3,2,70),lambda:network(0,0,0,2,70),lambda:processing(-1,1),lambda:processing(0,5),lambda:movement(6,12,0,12),lambda:movement(6,12,4,0),lambda:movement(6,12,4,12,reduction=0),lambda:slope((1,1),(1,2)),lambda:slope((1,2),(1,)),lambda:parse('1+2'),lambda:strict('{"a":1,"a":2}'),lambda:strict('{"a":NaN}')):
        try:fn()
        except (ValueError,TypeError,ZeroDivisionError):rejects+=1
        else:raise ValueError('invalid domain accepted')
    ensure(seen=={k for k,v in d.mark.items() if v[0]=='data-result'},'all numerical results covered');ensure(raw=={f:(base/f).read_bytes() for f in FILES},'unchanged runtime');result=dict(chapter='v15-c05',status='passed',worked_cases=5,solutions=10,inputs=len(x),results=len(seen),comparisons=count,domain_rejections=rejects,runtime_files=6);json.dumps(result,allow_nan=False);return result
if __name__=='__main__':check()
