"""Independent historical inference peer oracle: no execution or import of author code."""
from pathlib import Path
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from itertools import product
from math import isfinite
import ast,json
FILES=('production/v15-c07-working.html','production/check_v15_c07_working.py','production/v15-c07-sources-working.json','production/v15-c07-author-review-working.json','production/check_v15_c07_peer_working.py','production/v15-c07-peer-review-working.json')
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
def index(old,new,basket):
    ensure(len(old)==len(new)==len(basket)>0,'price dimensions');old,new,basket=[tuple(map(real,z)) for z in (old,new,basket)];ensure(min(old)>0 and min(new)>0 and min(basket)>=0 and sum(basket)>0,'positive prices and basket');return sum(p*q for p,q in zip(new,basket))/sum(p*q for p,q in zip(old,basket))
def completion(total,observed,mean,missing):
    ensure(type(total)is int and type(observed)is int and 0<=observed<=total and total>0,'population counts');mean,missing=map(real,(mean,missing));ensure(mean>=0 and missing>=0,'nonnegative earnings');return (observed*mean+(total-observed)*missing)/total

def technique(w,e,methods):
    w,e=map(real,(w,e));ensure(w>0 and e>0 and len(methods)>0,'prices and alternatives');rows=[]
    for method in methods:
        ensure(len(method)==3,'labor energy rental');l,n,k=map(real,method);ensure(min(l,n,k)>=0,'nonnegative technology');rows.append(l*w+n*e+k)
    best=min(rows);return tuple(i for i,c in enumerate(rows) if c==best),tuple(rows)
def invention(cost,save,capture,prob):
    cost,save,capture,prob=map(real,(cost,save,capture,prob));ensure(cost>=0 and save>0 and 0<capture<=1 and 0<prob<=1,'invention domain');unit=save*capture*prob;return (cost.numerator*unit.denominator+cost.denominator*unit.numerator-1)//(cost.denominator*unit.numerator)
def affine_range(D,d,s):
    D=real(D);ensure(len(d)==len(s)==2,'sensitivity dimensions');d,s=tuple(map(real,d)),tuple(map(real,s));ensure(d[0]<=d[1] and s[0]<=s[1],'closed ordered bounds');values=[D-a+b for a,b in product(d,s)];return min(values),max(values)
def direct_iv(reduced,first,bounds):
    reduced,first=map(real,(reduced,first));ensure(first!=0 and len(bounds)==2,'identified slope domain');a,b=map(real,bounds);ensure(a<=b,'direct effect bounds');worlds=tuple((reduced-g)/first for g in (a,b));return min(worlds),max(worlds)
def accounts(cash,face,recovery,debt,withdrawal,price,rate,pledge):
    cash,face,recovery,debt,withdrawal,price,rate,pledge=map(real,(cash,face,recovery,debt,withdrawal,price,rate,pledge));ensure(cash>=0 and face>0 and 0<=recovery<=1 and cash<withdrawal<=debt and price>0 and rate>0 and 0<=pledge<=face,'bank domains');gap=withdrawal-cash;face_sold=gap/price;ensure(face_sold<=face,'liquidation feasible');return dict(gap=gap,initial=cash+recovery*face-debt,sold=face_sold,retained=face-face_sold,remaining_debt=debt-withdrawal,liquidation=(face-face_sold)*recovery-(debt-withdrawal),repayment=gap*rate,borrow=face*recovery-(debt-withdrawal)-gap*rate,collateral=pledge*recovery)
def bayes(prior,likelihood1,likelihood2):
    prior=real(prior);ensure(0<prior<1 and len(likelihood1)==len(likelihood2)>0,'belief dimensions');weights=[prior,1-prior]
    for i,ls in enumerate((likelihood1,likelihood2)):
        for z in ls:
            z=real(z);ensure(0<=z<=1,'probability');weights[i]*=z
    ensure(sum(weights)>0,'possible evidence');return weights[0]/sum(weights)

class Read(HTMLParser):
    def __init__(self):super().__init__();self.stack=[];self.ids=set();self.mark={};self.prompts=[];self.answers={};self.worked=[];self.sources={};self.links=[]
    def handle_starttag(self,t,attrs):
        a=dict(attrs);ensure(len(a)==len(attrs),'unique attributes')
        if 'id' in a:ensure(a['id'] not in self.ids and a['id'].startswith('v15-c07-'),'scoped unique ID');self.ids.add(a['id'])
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
    base=Path(root) if root is not None else Path(__file__).resolve().parents[1];raw={f:(base/f).read_bytes() for f in FILES};d=Read();d.feed(raw[FILES[0]].decode());d.close();ensure(not d.stack,'complete markup');peer,source,author=(strict(raw[FILES[i]]) for i in (5,2,3));targets=[f'v15-c07-e{i}' for i in range(1,11)];ensure(d.prompts==list(d.answers)==targets and len(d.worked)==5 and all(len(v)>350 for v in d.answers.values()),'five cases ten full answers');ensure(set(peer['exact_solution_review'])==set(targets) and not peer['open_findings'],'full peer review');ensure(d.sources=={s['id']:s['url'] for s in source['sources']},'source routes');ensure('v15-c06.html' in d.links and 'v15-c08.html' in d.links,'chapter routes');ensure(set(peer['payload_bindings'])==set(FILES[:5]),'five nonself bindings')
    for f,b in peer['payload_bindings'].items():ensure(len(raw[f])==b['bytes'] and sha256(raw[f]).hexdigest()==b['sha256'],'peer payload freeze')
    ensure(not author['open_findings'],'author findings');bindings=author['payload_bindings'];ensure(len(bindings)==3 and {b['path'] for b in bindings}==set(FILES[:3]),'author nonself bindings')
    for b in bindings:ensure(b['bytes']==len(raw[b['path']]) and b['sha256']==sha256(raw[b['path']]).hexdigest(),'author frozen bytes')
    x={k:parse(v[1]) for k,v in d.mark.items() if v[0]=='data-input'};count=0;rejects=0;seen=set()
    def eq(a,b):
        nonlocal count
        if isinstance(a,(tuple,list)):
            ensure(isinstance(b,(tuple,list)) and len(a)==len(b),'numeric shape')
            for c,e in zip(a,b):eq(c,e)
        else:ensure(a==b,'exact equality '+str((a,b)));count+=1
    def truth(a,m):
        nonlocal count
        ensure(a,m);count+=1
    def mark(k,v):eq(v,parse(d.mark[k][1]));seen.add(k)
    ensure(set(x)=={'prices','tech','border','bank','history-beliefs'},'all primitive groups')
    w0,w1,d0,d1,*p=x['prices'];p0,p1,q0,q1=p[:2],p[2:4],p[4:6],p[6:];L=index(p0,p1,q0);P=index(p0,p1,q1);mark('price-results',(L,P,w1/w0/L,w1/w0/P,w1*d1/(w0*d0)/L,w1*d1/(w0*d0)/P));mark('archive-bounds',tuple(completion(100,80,2400,z) for z in (0,3000)));mark('e1',(w1*180,w1*180/(w0*d0)/L,w1*180/(w0*d0)/P));mark('e2',tuple(completion(100,60,2400,z) for z in (1000,3000)))
    for N,n,lo,hi in ((100,80,0,3000),(100,60,1000,3000),(7,0,0,8),(7,7,0,8)):
        ends=tuple(completion(N,n,2400,z) for z in (lo,hi))
        for k in range(11):
            mix=F(k,10);missing=lo*(1-mix)+hi*mix;avg=completion(N,n,2400,missing);eq(avg,ends[0]*(1-mix)+ends[1]*mix);truth(ends[0]<=avg<=ends[1],'sharp continuous completions')
    for scaling in (F(1,5),F(1),F(7)):
        eq(index(tuple(scaling*v for v in p0),tuple(scaling*v for v in p1),q0),L);eq(index(p0,p1,tuple(scaling*v for v in q1)),P)
    oldl,olde,newl,newe,rental,wh,eh,wl,el=x['tech'];methods=((oldl,olde,0),(newl,newe,rental));h=technique(wh,eh,methods)[1];low=technique(wl,el,methods)[1];mark('tech-results',(*h,h[0]-h[1],*low,low[0]-low[1]));row=technique(3,2,methods)[1];cutoff=(rental+(newe-olde)*2)/(oldl-newl);refined=technique(wl,el,((oldl,olde,0),(3,3,8)))[1];mark('e3',(*row,row[0]-row[1],cutoff,refined[1],refined[0]-refined[1]));mark('e4',tuple(invention(80,h[0]-h[1],F(1,2),s) for s in (1,F(1,2))))
    for energy in (F(1,2),F(1),F(2),F(5)):
        threshold=(rental+(newe-olde)*energy)/(oldl-newl)
        for gap in (F(-1,4),F(0),F(1,4)):
            wage=threshold+gap;choice,cost=technique(wage,energy,methods);eq(cost[0]-cost[1],(oldl-newl)*gap);eq(choice,(0,) if gap<0 else (0,1) if gap==0 else (1,))
    for saving,capture,success in product((F(2),F(8),F(9)),(F(1,3),F(1,2)),(F(1),F(1,2))):
        users=invention(80,saving,capture,success);truth(users*saving*capture*success>=80,'invention covers cost');truth((users-1)*saving*capture*success<80,'smallest feasible integer')
    T=x['border'][:3];C=x['border'][3:];pre=(T[1]-C[1])-(T[0]-C[0]);D=(T[2]-C[2])-(T[1]-C[1]);mark('border-results',(pre,D,*affine_range(D,(F(-1,2),F(1,2)),(0,1))));mark('e5',affine_range(D,(0,1),(0,F(1,2))));RF=F(-3,5);g=(F(-3,20),F(3,20));mark('iv-bounds',(RF/F(-3,10),*direct_iv(RF,F(-3,10),g)));iv=direct_iv(RF,F(-1,10),g);mark('e6',(*iv,iv[1]-iv[0]))
    for dd,ss in (((F(-1,2),F(1,2)),(0,1)),((0,1),(0,F(1,2))),((0,0),(0,0))):
        lo,hi=affine_range(D,dd,ss)
        for u,v in product((0,F(1,2),1),repeat=2):
            delta=dd[0]*(1-u)+dd[1]*u;spill=ss[0]*(1-v)+ss[1]*v;effect=D-delta+spill;truth(lo<=effect<=hi,'bounded direct effect');eq(effect+delta-spill,D)
    for first in (F(-3,10),F(-1,10),F(1,10),F(3,10)):
        lo,hi=direct_iv(RF,first,g);eq(hi-lo,(g[1]-g[0])/abs(first))
        for gamma in (g[0],F(0),g[1]):
            beta=(RF-gamma)/first;eq(beta*first+gamma,RF);truth(lo<=beta<=hi,'signed IV range')
    truth(not(g[0]<=RF<=g[1]),'zero first stage inconsistent with current direct bound')
    cash,face,recovery,debt,withdrawal,price,rate=x['bank'];b=accounts(*x['bank'],50);mark('bank-results',tuple(b[k] for k in ('initial','sold','liquidation','repayment','borrow','collateral')));changed=accounts(cash,face,recovery,debt,withdrawal,F(3,4),rate,50);private=(face*recovery-changed['remaining_debt']-changed['liquidation'])/changed['gap'];secured=changed['collateral']/changed['gap'];mark('e7',(changed['sold'],changed['retained']*recovery,changed['liquidation'],private,secured));bad=accounts(cash,face,F(3,5),debt,withdrawal,price,rate,50);mark('e8',(bad['initial'],bad['collateral'],bad['repayment'],-bad['borrow']))
    for rec,sale,r in product((F(3,5),F(9,10)),(F(3,4),F(4,5)),(1,F(21,20),F(9,8))):
        z=accounts(cash,face,rec,debt,withdrawal,sale,r,50);eq(cash+z['sold']*sale,withdrawal);eq(z['liquidation']+z['remaining_debt'],z['retained']*rec);eq(z['borrow']+z['remaining_debt']+z['repayment'],face*rec);eq(z['initial']-z['borrow'],z['gap']*(r-1));eq(z['initial']-z['liquidation'],z['sold']*(rec-sale));buyer_gain=z['sold']*(rec-sale);eq(z['liquidation']+buyer_gain,z['initial']);eq(z['borrow']+z['gap']*(r-1),z['initial'])
    for r in (F(1,2),F(1),secured,private,F(5,4)):
        z=accounts(cash,face,recovery,debt,withdrawal,F(3,4),r,50);truth((z['borrow']>=changed['liquidation'])==(r<=private),'private rate boundary');truth((z['repayment']<=z['collateral'])==(r<=secured),'pledge boundary')
    eq(-bad['borrow'], -bad['initial']+bad['gap']*(rate-1));eq(bad['borrow']-bad['borrow'],0)
    prior,a,b,c,e=x['history-beliefs'];first=(a,c);second=(b,e);mark('history-results',(a*c,b*e,bayes(prior,first,second),bayes(prior,(a,c,a),(b,e,b)),bayes(prior,(a,F(1,2)),(b,F(1,2)))));mark('e9',(bayes(F(1,4),first,second),bayes(F(1,4),(a,c,a),(b,e,b))))
    for prior in (F(1,10),F(1,4),F(1,2),F(9,10)):
        posterior=bayes(prior,first,second);odds=posterior/(1-posterior);eq(odds,prior/(1-prior)*(a/b)*(c/e));afterE=bayes(prior,(a,),(b,));eq(bayes(afterE,(c,),(e,)),posterior);eq(bayes(prior,(a,1),(b,1)),afterE);eq(bayes(prior,(a,F(1,2)),(b,F(1,2))),afterE);truth(bayes(prior,(a,c,a),(b,e,b))>posterior,'copied evidence distortion')
    eq(bayes(F(1,2),(0,),(1,)),0);eq(bayes(F(1,2),(1,),(0,)),1)
    invalid=(lambda:real(True),lambda:real(float('inf')),lambda:real(float('nan')),lambda:index((1,),(1,2),(1,)),lambda:index((0,),(1,),(1,)),lambda:index((1,),(1,),(0,)),lambda:completion(10,11,2,2),lambda:completion(0,0,2,2),lambda:completion(10,1,2,-1),lambda:technique(0,1,((1,1,1),)),lambda:technique(1,1,((1,-1,1),)),lambda:invention(80,0,F(1,2),1),lambda:invention(80,8,F(1,2),0),lambda:affine_range(1,(1,0),(0,1)),lambda:direct_iv(1,0,(0,1)),lambda:direct_iv(1,1,(1,0)),lambda:accounts(20,120,2,100,60,1,1,50),lambda:accounts(20,120,1,100,60,F(1,10),1,50),lambda:accounts(20,120,1,100,10,1,1,50),lambda:accounts(20,120,1,100,60,1,1,121),lambda:bayes(0,(1,),(1,)),lambda:bayes(F(1,2),(0,),(0,)),lambda:bayes(F(1,2),(2,),(1,)),lambda:parse('1+2'),lambda:strict('{"a":1,"a":2}'),lambda:strict('{"a":NaN}'))
    for f in invalid:
        try:f()
        except (ValueError,TypeError,ZeroDivisionError):rejects+=1
        else:raise ValueError('invalid primitive accepted')
    ensure(seen=={k for k,v in d.mark.items() if v[0]=='data-result'},'all result groups reconstructed');ensure(raw=={f:(base/f).read_bytes() for f in FILES},'unchanged runtime');result=dict(chapter='v15-c07',status='passed',worked_cases=5,solutions=10,inputs=len(x),results=len(seen),comparisons=count,domain_rejections=rejects,runtime_files=6);json.dumps(result,allow_nan=False);return result
if __name__=='__main__':check()
