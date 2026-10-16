"""Exact four-file environmental chapter audit. Quiet API and CLI."""
import ast,json
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from math import isfinite,log
from pathlib import Path
FILES=('content/chapters/v15-c09.html','scripts/check_v15_c09.py','content/reviews/v15-c09-sources.json','content/reviews/v15-c09-author.json')
def need(ok,msg):
    if not ok:raise ValueError(msg)
def num(x):
    need(type(x) in (int,float,F) and isfinite(float(x)),'finite nonboolean');return F(str(x)) if type(x) is float else F(x)
def literal(s):
    def walk(n):
        if isinstance(n,ast.Constant):return num(n.value)
        if isinstance(n,(ast.Tuple,ast.List)):return tuple(walk(v) for v in n.elts)
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,(ast.USub,ast.UAdd)):return (-1 if isinstance(n.op,ast.USub) else 1)*walk(n.operand)
        if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Div):
            d=walk(n.right);need(d!=0,'nonzero divisor');return walk(n.left)/d
        raise ValueError('literal only')
    return walk(ast.parse(s.replace('−','-').rsplit('=',1)[-1].strip(),mode='eval').body)
def cap(a_total,b=(6,6),k=(1,2)):
    A=num(a_total);b=tuple(map(num,b));k=tuple(map(num,k));need(len(b)==len(k)==2 and min(b)>0 and min(k)>0 and 0<=A<=sum(b),'cap domain');lo=max(F(0),A-b[1]);hi=min(b[0],A);a0=max(lo,min(hi,k[1]*A/sum(k)));a=(a0,A-a0);inter=[k[i]*a[i] for i in range(2) if 0<a[i]<b[i]];price=inter[0] if inter else max(k[i]*a[i] for i in range(2));return a,price,sum(k[i]*a[i]**2/2 for i in range(2))
def risk(B,c,k,d,theta):
    B,c,k,d,theta=map(num,(B,c,k,d,theta));need(min(B,c,k,d)>0 and c+theta>0,'risk primitives');bar=(d*B-c)/(k+d);tau=d*(B-bar);full=bar-theta/(k+d);tax=bar-theta/k;need(0<min(bar,full,tax) and max(bar,full,tax)<B,'interior comparison');cost=lambda a:(c+theta)*a+k*a*a/2+d*(B-a)**2/2;return bar,tau,full,tax,cost

def protection(k,bad=True):
    k=num(k);need(0<k<100 and type(bad) is bool,'protection domain');C=50 if bad else 150;zero=(900-k*C)/(29*k);return max(F(0),min(F(1),zero))
def resource(S,beta=F(4,5),cost=2):
    S,beta,cost=map(num,(S,beta,cost));need(S>=0 and 0<beta<=1 and 0<=cost<12,'resource domain');A=12-cost;B=14-cost
    if S==0:q0,q1,lam=F(0),F(0),max(A,beta*B)
    elif S>=A+B:q0,q1,lam=A,B,F(0)
    else:
        q0=max(F(0),min(S,(A-beta*B+beta*S)/(1+beta)));q1=S-q0;lam=A-q0 if q0>0 else beta*(B-q1)
    return q0,q1,lam,S-q0-q1

def energy(c,h):
    c,h=map(num,(c,h));need(c>0 and h>0,'energy cost domain')
    if c>3*h/4:return F(0),F(0)
    if c==3*h/4:return F(0),F(10)
    if c>h/4:return F(10),F(10)
    if c==h/4:return F(10),F(20)
    return F(20),F(20)
def pulse(beta,rho,damage,T):
    beta,rho,damage=map(num,(beta,rho,damage));need(0<beta<=1 and 0<=rho<=1 and damage>=0 and type(T) is int and T>0,'pulse domain');return sum(beta**j*damage*rho**(j-1) for j in range(1,T+1))
class Read(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.stack=[];self.active=[];self.inputs={};self.outputs={};self.prompts=[];self.solutions=[];self.cases=[];self.ids=[];self.sources={};self.links=set();self.disclosures=0
    def handle_starttag(self,t,attrs):
        a=dict(attrs);need(len(a)==len(attrs),'unique attributes');need(t!='h1','fragment heading')
        if 'id' in a:need(a['id'].startswith('v15-c09-') and a['id'] not in self.ids,'chapter unique IDs');self.ids.append(a['id'])
        if t=='article' and 'worked' in a.get('class','').split():self.cases.append(a['id'])
        if t=='li' and a.get('id','').startswith('v15-c09-e'):self.prompts.append(a['id'])
        if t=='details' and 'solutions' in a.get('class','').split():self.disclosures+=1
        if 'data-solution-for' in a:need(any(t=='details' and 'solutions' in d.get('class','').split() for t,d in self.stack),'solution enclosure');self.solutions.append(a['data-solution-for'])
        if t=='a':self.links.add(a.get('href'))
        if 'data-source' in a:self.sources[a['data-source']]=a['href']
        for attr,d in (('data-input',self.inputs),('data-result',self.outputs)):
            if attr in a:k=a[attr];need(k not in d,'unique data marker');d[k]='';self.active.append((d,k,len(self.stack)))
        if t not in ('br','hr','img','meta','link','input'):self.stack.append((t,a))
    def handle_data(self,s):
        for d,k,n in self.active:d[k]+=s
    def handle_endtag(self,t):
        need(self.stack and self.stack[-1][0]==t,'balanced HTML');self.stack.pop();self.active=[x for x in self.active if x[2]<len(self.stack)]

def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1];raw={f:(root/f).read_bytes() for f in FILES};doc=Read();doc.feed(raw[FILES[0]].decode());need(not doc.stack,'complete HTML');review=json.loads(raw[FILES[3]]);sources=json.loads(raw[FILES[2]]);bind=review['payload_bindings'];need(len(bind)==3 and {b['path'] for b in bind}==set(FILES[:3]),'three nonself bindings')
    for b in bind:need((b['bytes'],b['sha256'])==(len(raw[b['path']]),sha256(raw[b['path']]).hexdigest()),'frozen binding')
    ex=['v15-c09-e'+str(i) for i in range(1,11)];need(doc.prompts==doc.solutions==ex and set(review['exact_prompt_review'])==set(ex),'ten full matched solutions');need(doc.cases==['v15-c09-case'+str(i) for i in range(1,6)] and doc.disclosures==1,'five worked cases');need({'v15-c08.html','curriculum.html#v15-c10'}<=doc.links,'correct routes');need(doc.sources=={s['id']:s['url'] for s in sources['sources']} and len(doc.sources)==3,'three exact sources');need(all(s['verification'] and s['limits'] for s in sources['sources']),'bounded source scopes')
    inp={k:literal(v) for k,v in doc.inputs.items()};shown={k:literal(v) for k,v in doc.outputs.items()};expected={};comparisons=0
    def eq(a,b,label='identity'):
        nonlocal comparisons
        if isinstance(a,(tuple,list)) or isinstance(b,(tuple,list)):
            need(isinstance(a,(tuple,list)) and isinstance(b,(tuple,list)) and len(a)==len(b),label+' shape')
            for x,y in zip(a,b):eq(x,y,label)
        else:
            comparisons+=1
            if isinstance(a,float) or isinstance(b,float):need(abs(float(a)-float(b))<1e-10*max(1,abs(float(b))),label+str((a,b)))
            else:need(a==b,label+str((a,b)))
    primitives={'abatement':(6,6,1,2,F(1,2),60),'uncertainty':(10,2,2,1,-1,1,F(1,2)),'protection':(100,50,150,F(9,10),F(1,2),9,20),'resource':(8,F(4,5),2,12,14),'energy':(10,1,F(1,2),F(1,2),4,5,2)};need(set(inp)==set(primitives),'five primitive groups')
    for k,v in primitives.items():eq(inp[k],v,k)
    b0,b1,k0,k1,d,end=inp['abatement'];E=(b0+b1)/(1+d*(1/k0+1/k1));tau=d*E;a=(tau/k0,tau/k1);costs=(k0*a[0]**2/2,k1*a[1]**2/2);D=d*E*E/2;taxes=tuple(tau*(b-a_) for b,a_ in zip((b0,b1),a));G=sum(taxes);u=tuple(end-costs[i]-taxes[i]+G/2-D/2 for i in range(2));loss=sum(costs)+D
    expected['planner']=(*a,E,tau);expected['planner-loss']=(sum(costs),D,loss,d*(b0+b1)**2/2-loss);expected['distribution']=u;eq(sum(u),2*end-loss);eq(G,tau*E);eq(taxes,(F(432,49),F(720,49)));eq(G/2,F(576,49));need(all(costs[i]+taxes[i]<=end for i in range(2)),'operating funding')
    ac,pc,cc=cap(10);expected['e1']=(*ac,pc,cc,F(1),2*pc);u1=end-costs[0]-taxes[0]-D/2;u2=end-costs[1]-taxes[1]+G-D/2;baseline=end-d*(b0+b1)**2/4;expected['e2']=(u1,u2,baseline-u1);eq(u1+u2,sum(u));eq(u2-(baseline-u1),F(402,7))
    # Exact convex tangent remainder for every tested alternative, not a grid proof substitute.
    for x in (F(0),F(1),F(3),F(6)):
        for y in (F(0),F(2),F(4),F(6)):
            other=k0*x*x/2+k1*y*y/2+d*(12-x-y)**2/2;remainder=k0*(x-a[0])**2/2+k1*(y-a[1])**2/2+d*((x-a[0])+(y-a[1]))**2/2;eq(other-loss,remainder);need(remainder>=0,'global planner remainder');comparisons+=1
    for A in (0,1,6,9,10,12):
        aa,pp,co=cap(A);eq(sum(aa),A)
        for x in (max(0,A-6),min(6,A)):
            alt=F(x*x,2)+F((A-x)**2);need(co<=alt,'cap boundary deviations');comparisons+=1
    B,c,k,d,low,high,p=inp['uncertainty'];losses=[];regrets=[]
    for dd in (d,F(4)):
        sums=[F(0)]*3;rr=[F(0)]*2
        for theta in (low,high):
            bar,tax,full,at,L=risk(B,c,k,dd,theta)
            for j,z in enumerate((full,bar,at)):sums[j]+=L(z)/2;eq(L(z)-L(full),(k+dd)*(z-full)**2/2)
            rr[0]+=(L(bar)-L(full))/2;rr[1]+=(L(at)-L(full))/2;need((c+theta)*at+k*at*at/2+tax*(B-at)<=200,'state operating funding');comparisons+=1
            if dd==d:eq(L(at),F(877 if theta==-1 else 1005,24))
        eq(rr[1]/rr[0],(dd/k)**2)
        if dd==d:expected['regrets']=tuple(rr);expected['expected-losses']=tuple(sums)
        else:expected['e3']=(bar,tax,*rr)
    bar=F(9,2);tax=F(11);vals=[];reg=[]
    for dd in (F(1),F(3)):
        _,_,full,_,L=risk(10,2,2,dd,0);vals.append(L(bar));reg.append(L(bar)-L(full));eq((tax-2)/2,bar)
    expected['e4']=(bar,tax,sum(vals)/2,sum(reg)/2);eq(sum(vals)/2-sum(reg)/2,F(832,15))
    C0,Cl,Ch,beta,p,kcost,benefit=inp['protection'];m=(beta*C0/Cl,beta*C0/Ch);expected['shadow']=(*m,p*m[0]*benefit,(1-p)*m[1]*benefit,p*m[0]+(1-p)*m[1]);gains=tuple(log(float((C0-kcost)/C0))+float(beta*p)*log(float((C+benefit)/C)) for C in (Cl,Ch));expected['utility-gains']=gains;eq((protection(9),protection(9,False)),(1,0));x=protection(15);expected['e5']=(x,protection(15,False),C0-15*x,Cl+benefit*x);eq(-15/(C0-15*x)+beta*p*benefit/(Cl+benefit*x),0)
    for cost in (F(1),F(9),F(15),F(30),F(90)):
        for bad in (True,False):
            xx=protection(cost,bad);C=Cl if bad else Ch;deriv=-cost/(C0-cost*xx)+beta*p*benefit/(C+benefit*xx);need((xx==0 and deriv<=0) or (xx==1 and deriv>=0) or (0<xx<1 and deriv==0),'protection KKT');comparisons+=1
            obj=lambda z:log(float(C0-cost*z))+float(beta*p)*log(float(C+benefit*z));val=obj(xx)
            for alt in (F(0),F(1,4),F(1,2),F(3,4),F(1)):need(obj(alt)<=val+1e-12,'strict concavity witness');comparisons+=1
    rate=F(101,100)**3;expected['e6']=(rate,float(F(100)/rate**30));need(F(100)/rate**30>40,'marginal PV comparison')
    S,beta,c,A,B=inp['resource'];q0,q1,lam,unused=resource(S,beta,c);prices=(A-q0,B-q1);expected['extraction']=(q0,q1,*prices,lam);cs=(q0*q0+beta*q1*q1)/2;rent=lam*S;W=(A-c)*q0-q0*q0/2+beta*((B-c)*q1-q1*q1/2);expected['resource-welfare']=(cs,rent,W);eq(cs+rent,W);eq(prices[1]-c,(prices[0]-c)/beta)
    for stock in (F(0),F(1,5),F(2,5),F(8),F(22),F(25)):
        q,r,l,u_=resource(stock);eq(q+r+u_,stock);need(l>=0 and u_>=0 and q>=0 and r>=0,'resource feasibility');eq(l*u_,0)
        need((q==0 and 10-q<=l) or (q>0 and 10-q==l),'date0 KKT');need((r==0 and beta*(12-r)<=l) or (r>0 and beta*(12-r)==l),'date1 KKT');comparisons+=2
        for z,aa,price in ((q,12,12-q),(r,14,14-r)):
            need(price*z<=100,'date consumer finance');eq(100-price*z+(price-c)*z,100-c*z)
    sm=resource(F(1,5));lg=resource(25);expected['e7']=(*sm[:3],*lg[:2],lg[3]);q,r,l,_=resource(8,cost=3);px=(12-q,14-r);G=q+beta*r;expected['e8']=(q,r,*px,px[0]-3,px[1]-3,G);eq(px[1]-3,(px[0]-3)/beta)
    for z,pr in zip((q,r),px):eq(100-pr*z+z+(pr-3)*z,100-2*z);need(pr*z<=100,'tax consumer finance')
    load,av1,av2,p,c,h,damage=inp['energy'];priv=energy(c,h);social=energy(c,h+damage);eq(priv,(0,0));eq(social,(10,10));K=social[0];Gs=tuple(max(F(0),load-av*K) for av in (av1,av2));EG=sum(Gs)/2;real=c*K+h*EG;dam=damage*EG;expected['capacity']=(priv[0],K,(h+damage)*load,real+dam,(h+damage)*load-real-dam);expected['energy-accounts']=(damage*EG,real+damage*EG,real,dam)
    for av,Gs_ in zip((av1,av2),Gs):
        eq(min(load,av*K)+Gs_,load);need(c*K<=100 and (h+damage)*Gs_<=100,'state funding');eq((h+damage)*Gs_-damage*Gs_,h*Gs_)
    for hh in (F(5),F(7)):
        for cc in (F(1),hh/4,F(3),3*hh/4,F(7)):
            lo,hi=energy(cc,hh);J=lambda z:cc*z+hh*(max(F(0),10-z)+max(F(0),10-z/2))/2;eq(J(lo),J(hi))
            for alt in (F(0),F(5),F(10),F(15),F(20)):need(J(alt)>=J(lo),'capacity convex boundary');comparisons+=1
    expected['e9']=(energy(3,5)[0],energy(3,7)[0],energy(1,5)[0],energy(1,7)[0],energy(F(7,4),5)[0],*energy(F(7,4),7));expected['e10']=(pulse(F(9,10),F(1,2),4,2),pulse(F(9,10),1,4,2))
    for rho in (F(0),F(1,2),F(1)):
        stock=F(1);value=F(0)
        for j in range(1,7):value+=F(9,10)**j*4*stock;stock*=rho
        eq(value,pulse(F(9,10),rho,4,6))
    need(set(shown)==set(expected),'all displayed numerical groups')
    for key,v in expected.items():eq(shown[key],v,'HTML '+key)
    invalid=(lambda:num(True),lambda:num(float('nan')),lambda:literal('1/0'),lambda:literal('f(1)'),lambda:cap(-1),lambda:cap(13),lambda:cap(2,k=(0,2)),lambda:risk(10,2,0,1,0),lambda:risk(10,2,2,1,-2),lambda:risk(10,2,2,1,8),lambda:protection(100),lambda:protection(0),lambda:protection(9,1),lambda:resource(-1),lambda:resource(8,0),lambda:resource(8,cost=12),lambda:energy(0,5),lambda:energy(4,-1),lambda:pulse(0,1,4,2),lambda:pulse(F(9,10),2,4,2),lambda:pulse(F(9,10),1,4,True),lambda:pulse(F(9,10),1,-4,2));reject=0
    for fn in invalid:
        try:fn()
        except ValueError:reject+=1
        else:raise ValueError('invalid input accepted')
    for f,b in raw.items():need((root/f).read_bytes()==b,'unchanged payload')
    result={'chapter':'v15-c09','status':'passed','worked_cases':5,'solutions':10,'comparisons':comparisons,'rejected_inputs':reject,'input_groups':len(inp),'result_groups':len(shown),'runtime_files':4,'open_findings':[]};json.dumps(result,allow_nan=False);return result
if __name__=='__main__':check()
