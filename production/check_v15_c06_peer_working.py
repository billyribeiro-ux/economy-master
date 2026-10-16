"""Independent political-economy reconstruction; six-file quiet review API."""
from pathlib import Path
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from math import sqrt,log,isfinite
from itertools import product
import ast,json
FILES=('production/v15-c06-working.html','production/check_v15_c06_working.py','production/v15-c06-sources-working.json','production/v15-c06-author-review-working.json','production/check_v15_c06_peer_working.py','production/v15-c06-peer-review-working.json')
def require(v,msg):
    if not v:raise ValueError(msg)
def number(v):
    require(type(v)in(int,float,F)and isfinite(float(v)),'finite real scalar');return F(str(v))
def vote(tastes,limit):
    a=tuple(map(number,tastes));limit=number(limit);require(a and len(a)%2==1 and min(a)>0 and limit>0,'voting domain');n=len(a);peaks=tuple(min(limit,max(n*v-1,0))for v in a);return peaks,sorted(peaks)[n//2],min(limit,max(sum(a)-1,0))
def election(pH,pL,beta,rent,cost,accuracy):
    pH,pL,beta,rent,cost,accuracy=map(number,(pH,pL,beta,rent,cost,accuracy));require(0<pL<pH<1 and 0<beta<=1 and rent>0 and cost>0 and F(1,2)<accuracy<=1,'agency domain');qh=accuracy*pH+(1-accuracy)*(1-pH);ql=accuracy*pL+(1-accuracy)*(1-pL);gain=beta*rent*(qh-ql)-cost;act=int(gain>=0);types=((F(1,4),True,1),(F(1,4),False,0),(F(1,2),False,act));good=sum(m*(qh if effort else ql)for m,_,effort in types);jointgood=sum(m*(qh if effort else ql)for m,diligent,effort in types if diligent);jointbad=F(1,4)-jointgood;postgood=jointgood/good;postbad=jointbad/(1-good);challenger=pL+(pH-pL)/4;sg=pL+(pH-pL)*postgood;sb=challenger;final=good*sg+(1-good)*sb;first=sum(m*(pH if effort else pL)for m,_,effort in types);return(qh,ql,good,postgood,postbad,gain),first,sg,sb,final

def influence(benefit,loss,counter):
    benefit,loss,counter=map(number,(benefit,loss,counter));require(benefit>0 and loss>=0 and counter>=0,'influence domain');d=1+counter;l=max(sqrt(float(benefit*d))-float(d),0);p=l/(float(d)+l);private=float(benefit)*p-l;welfare=float(benefit-loss)*p-l-float(counter);return l,p,private,welfare

def contract(b,d=0,nonnegative_intercept=False,audit=0):
    b,d,audit=map(number,(b,d,audit));require(b>=0 and d>=0 and audit>=0 and type(nonnegative_intercept)is bool,'contract domain');q=min(b,3);e=min(d,3);cost=(q*q+e*e)/2;A=cost-b*q-d*e
    if nonnegative_intercept:A=max(A,0)
    salary=A+b*q+d*e;rent=salary-cost;public=q+2*e-salary-audit;social=q+2*e-cost-audit;return A,q,e,salary,rent,public,social

def capacity(base,cost,R=1):
    base,cost,R=map(number,(base,cost,R));require(base>0 and cost>0 and R>0,'capacity domain');k=max(sqrt(float(base/(4*R*cost)))-1,0);rho=k/(1+k);T=float(base)*rho/4;bill=float(cost)*k;G=T-float(R)*bill;return k,F(1,2)if k>0 else None,rho,T,G,bill
class Read(HTMLParser):
    def __init__(self):super().__init__();self.ids=[];self.cases=[];self.prompts=[];self.solutions=[];self.markers={};self.stack=[];self.sources={}
    def handle_starttag(self,t,a):
        a=dict(a)
        if 'id'in a:self.ids.append(a['id'])
        if 'worked'in a.get('class','').split():self.cases.append(a['id'])
        if t=='li'and any(tag=='ol'and 'exercises'in d.get('class','').split()for tag,d in self.stack):self.prompts.append(a['id'])
        if 'data-solution-for'in a:
            require(any(tag=='details'and 'solutions'in d.get('class','').split()for tag,d in self.stack),'disclosed answers');self.solutions.append(a['data-solution-for'])
        if 'data-source'in a:self.sources[a['data-source']]=a['href']
        for k in ('data-input','data-result'):
            if k in a:require(a[k]not in self.markers,'unique markers');self.markers[a[k]]=''
        if t not in ('br','hr','img','meta','link','input'):self.stack.append((t,a))
    def handle_endtag(self,t):require(self.stack and self.stack.pop()[0]==t,'balanced tags')
    def handle_data(self,s):
        for _,a in self.stack:
            for k in ('data-input','data-result'):
                if k in a:self.markers[a[k]]+=s

def parse(s):
    def walk(n):
        if isinstance(n,(ast.Tuple,ast.List)):return tuple(walk(x)for x in n.elts)
        if isinstance(n,ast.Constant)and type(n.value)in(int,float):return number(n.value)
        if isinstance(n,ast.UnaryOp)and isinstance(n.op,ast.USub):return -walk(n.operand)
        if isinstance(n,ast.BinOp)and isinstance(n.op,ast.Div):return walk(n.left)/walk(n.right)
        raise ValueError('numeric literal grammar')
    return walk(ast.parse(s.split('=')[-1].strip().replace('−','-'),mode='eval').body)

def check(root=None):
    root=Path(root)if root else Path(__file__).resolve().parents[1];r=Read();r.feed((root/FILES[0]).read_text());r.close();require(not r.stack and len(set(r.ids))==len(r.ids),'HTML/IDs');require(len(r.cases)==5 and len(r.prompts)==10 and r.prompts==r.solutions,'full exact solution coverage');src=json.loads((root/FILES[2]).read_text());require(r.sources=={x['id']:x['url']for x in src['sources']},'exact source routes');peer=json.loads((root/FILES[5]).read_text());require(set(peer['payload_bindings'])==set(FILES[:5]),'five peer nonself bindings')
    for path,v in peer['payload_bindings'].items():
        data=(root/path).read_bytes();require(len(data)==v['bytes']and sha256(data).hexdigest()==v['sha256'],'peer freeze')
    author=json.loads((root/FILES[3]).read_text());bindings=author['payload_bindings'];require(len(bindings)==3 and {x['path']for x in bindings}==set(FILES[:3]),'author binding set')
    for v in bindings:
        data=(root/v['path']).read_bytes();require(len(data)==v['bytes']and sha256(data).hexdigest()==v['sha256'],'author freeze')
    count=0
    def eq(x,y):
        nonlocal count
        if isinstance(y,(tuple,list)):
            require(isinstance(x,(tuple,list))and len(x)==len(y),'shape')
            for a,b in zip(x,y):eq(a,b)
        else:require(abs(float(x)-float(y))<2e-9*max(1,abs(float(y))),'mismatch '+str((x,y)));count+=1
    def truth(x,msg):
        nonlocal count
        require(x,msg);count+=1
    inputs={'voting':(1,2,4),'agency':(F(4,5),F(2,5),F(3,4),1,F(1,10),F(3,4)),'lobby':(9,12),'capacity':(100,1,1)}
    for k,v in inputs.items():eq(parse(r.markers[k]),v)
    tastes=parse(r.markers['voting']);peaks,median,social=vote(tastes,30);ph,pl,be,R,k,al=parse(r.markers['agency']);high=election(ph,pl,be,R,k,al);low=election(ph,pl,be,R,k,F(3,5));tie=election(ph,pl,be,R,k,F(2,3));benefit,loss=parse(r.markers['lobby']);l0=influence(benefit,loss,0);l1=influence(benefit,loss,1);l3=influence(benefit,loss,3);deter=benefit-1;ld=influence(benefit,loss,deter);qonly=contract(1);audited=contract(1,2,audit=F(2,5));restricted=contract(F(1,2),nonnegative_intercept=True);expensive=contract(1,2,audit=3);scale,unit,rate=parse(r.markers['capacity']);cap=capacity(scale,unit,rate);expensivecap=capacity(scale,4,rate);newpeaks,newmed,newsoc=vote((1,2,7),30)
    out={'voting-choice':(median,social),'agency-high':high[0],'lobby-base':l0,'bureaucracy':(qonly[1],qonly[2],qonly[5],audited[1],audited[2],audited[3],audited[5]),'capacity-result':cap[:5],'e1':(*newpeaks,newmed,newsoc),'e3':tie[0],'e4':(high[2],high[4],low[2],low[4]),'e5':(*l3,deter,ld[3]),'e7':(F(1,2),restricted[1],restricted[3],restricted[4],restricted[5],restricted[6]),'e8':(expensive[5],qonly[5]),'e9':(expensivecap[0],expensivecap[5],expensivecap[2],expensivecap[3],expensivecap[4])}
    for name,value in out.items():eq(parse(r.markers[name]),value)
    require(set(r.markers)==set(inputs)|set(out),'all markers independently recomputed')
    # Whole-proof witnesses supplement explicit written global/conditional arguments.
    eq(peaks,(2,5,11));eq(vote((1,1,1),30)[1],2);eq(vote((F(1,10),1,20),10)[0],(0,2,10));truth(7*log(7/6)-1>0,'positive sum welfare gain');truth(2*log(7/6)-F(1,3)<0,'median voter loss');truth(2*log(F(10,6))-F(4,3)<0,'exercise nonPareto')
    for alt in (0,2,4,6,11,30):
        preferred=sum(float(a)*log((1+median)/(1+alt))-float(median-alt)/3>0 for a in tastes);truth(preferred>=2,'majority comparison')
    rankings=('ABC','BCA','CAB')
    def pair(x,y):return x if sum(s.index(x)<s.index(y)for s in rankings)>=2 else y
    eq(tuple(pair(pair(x,y),z)=='ABC'[i]for i,(x,y,z)in enumerate((('B','C','A'),('C','A','B'),('A','B','C')))),(1,1,1))
    eq(low[0],(F(14,25),F(12,25),F(1,2),F(7,25),F(11,50),F(-1,25)));eq((high[1],low[1]),(F(7,10),F(1,2)));eq((high[3],low[3]),(F(1,2),F(1,2)))
    for accuracy in (F(51,100),F(3,5),F(2,3),F(3,4),1):
        values=election(ph,pl,be,R,k,accuracy);qh,ql,g,pg,pb,adv=values[0];truth(pg>F(1,4)>pb,'credible election action');eq(g*pg+(1-g)*pb,F(1,4));truth(qh>ql,'informative report');eq(adv,be*R*(2*accuracy-1)*(ph-pl)-k)
    eq(l1[3],-2-2*sqrt(2));eq(influence(F(1,4),loss,0),(0,0,0,0));eq(ld,(0,0,0,-8))
    for counter in (0,1,3,8,9):
        l,p,pr,w=influence(benefit,loss,counter);eq(w,pr-float(loss)*p-counter)
        for trial in (0,1,2,4,10):truth(pr+1e-10>=float(benefit)*trial/(1+counter+trial)-trial,'global influence branch')
    for bonus in (0,F(1,2),1,3,4):
        A,q,e,wage,rent,net,welfare=contract(bonus);eq(rent,0);eq(wage,q*q/2);truth(net<=qonly[5],'unrestricted q-only maximum')
        for trial in (0,F(1,2),1,2,3):truth(bonus*q-q*q/2>=bonus*trial-trial*trial/2,'global bounded official quantity')
    for b,d in ((0,0),(1,2),(3,3),(4,4)):
        A,q,e,wage,rent,net,wel=contract(b,d,audit=F(2,5));eq(net+rent,wel);truth(net<=audited[5],'full-information upper bound')
    A,q,e,wage,rent,net,wel=audited;signals=(e-1,e+1);wages=tuple(A+q+2*z for z in signals);eq(wages,(F(1,2),F(9,2)));eq(sum(wages)/2,wage);eq((A-2,A+3+2*4),(F(-9,2),F(17,2)));truth(10>=-float(A-2)and 20>=float(A+3+8+F(2,5)),'state funding reserve')
    for bonus in (0,F(1,2),1,3,4):truth(contract(bonus,nonnegative_intercept=True)[5]<=restricted[5],'limited intercept treasury optimum')
    for base,cost,R0 in ((100,1,1),(100,4,1),(4,1,1),(3,1,1),(100,1,2)):
        optimum=capacity(base,cost,R0);kk,t,rho,T,G,bill=optimum;eq(T,G+R0*bill);truth(G>=-1e-10,'loan repayment feasible')
        for ktrial,ttrial in ((0,0),(1,F(1,4)),(2,F(1,2)),(4,F(3,4)),(10,1)):
            candidate=base*ktrial/(1+ktrial)*float(ttrial*(1-ttrial))-R0*cost*ktrial;truth(G+1e-10>=candidate,'capacity global witness')
    eq(capacity(4,1)[0],0);eq(capacity(3,1)[0],0)
    bad=[lambda:number(True),lambda:number(float('nan')),lambda:vote((1,2),30),lambda:vote((0,1,2),30),lambda:vote((1,2,3),0),lambda:election(ph,pl,be,R,k,F(1,2)),lambda:election(pl,ph,be,R,k,al),lambda:election(ph,pl,be,R,0,al),lambda:election(ph,pl,2,R,k,al),lambda:influence(0,12,1),lambda:influence(9,-1,1),lambda:influence(9,12,-1),lambda:contract(-1),lambda:contract(1,-1),lambda:contract(1,audit=-1),lambda:capacity(0,1),lambda:capacity(100,0),lambda:capacity(100,1,0),lambda:parse('1+1')]
    rejected=0
    for fn in bad:
        try:fn()
        except(ValueError,TypeError,ZeroDivisionError):rejected+=1
        else:raise ValueError('invalid domain accepted')
    return {'chapter':'v15-c06','role':'separate-peer','status':'pass','comparisons':count,'domain_rejections':rejected,'worked_cases':5,'solutions':10,'input_groups':len(inputs),'output_groups':len(out),'runtime_files':6}
if __name__=='__main__':check()
