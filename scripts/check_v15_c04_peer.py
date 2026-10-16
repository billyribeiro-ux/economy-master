"""Independent development chapter reconstruction; author checker never executed."""
from pathlib import Path
from fractions import Fraction as F
from html.parser import HTMLParser
from hashlib import sha256
from itertools import combinations,product
from math import sqrt,isfinite
import ast,json
FILES=('content/chapters/v15-c04.html','scripts/check_v15_c04.py','content/reviews/v15-c04-sources.json','content/reviews/v15-c04-author.json','scripts/check_v15_c04_peer.py','content/reviews/v15-c04-peer.json')
def require(v,msg):
    if not v:raise ValueError(msg)
def number(v):
    require(type(v)in(int,float,F)and isfinite(float(v)),'finite scalar');return F(str(v))
def poverty(values,z,weights=None):
    y=tuple(map(number,values));z=number(z);require(y and min(y)>=0 and z>0,'poverty domain');w=tuple(map(number,weights))if weights is not None else (F(1,len(y)),)*len(y);require(len(w)==len(y)and min(w)>=0 and sum(w)==1,'population weights');g=tuple(max(z-v,0)/z for v in y);return sum(wi for wi,yi in zip(w,y)if yi<z),sum(wi*gi for wi,gi in zip(w,g)),sum(wi*gi*gi for wi,gi in zip(w,g))
def credit(A,C,R,ceiling,wealth):
    A,C,R,ceiling,wealth=map(number,(A,C,R,ceiling,wealth));require(A>0 and C>0 and R>0 and ceiling>=0 and wealth>=0,'credit domain');room=wealth+ceiling-C
    if room<=0:return(0.,0.,0.,float(R*wealth),0.,0.)
    # Active candidates from derivative in t=sqrt(k); evaluate actual dated accounts.
    candidates=[0.,float(room),min(float(room),float((A/(2*R))**2))];best=(0.,0.,0.,float(R*wealth),0.,0.)
    for k in candidates:
        loan=max(float(C)+k-float(wealth),0);saved=max(float(wealth)-float(C)-k,0);output=float(A)*sqrt(k);terminal=output+float(R)*(saved-loan);gain=terminal-float(R*wealth)
        if gain>best[1]+1e-12:best=(k,gain,output,terminal,loan,saved)
    return best

def bundles(a,b,c,ce,ch,w,eta):
    a,b,c,ce,ch,w,eta=map(number,(a,b,c,ce,ch,w,eta));require(min(a,b,c,w,eta)>=0 and min(ce,ch)>0,'bundle domain');rows=[]
    for e,h in ((0,0),(1,0),(0,1),(1,1)):
        cost=ce*e+ch*h;gross=a*e+b*h+c*e*h;rows.append((e,h,cost,gross,gross-cost,gross-cost+eta*h,cost<=w))
    mx=max(r[4]for r in rows if r[6]);return rows,tuple((r[0],r[1])for r in rows if r[6]and r[4]==mx)
def equilibrium(theta,subs,A,B):
    theta,subs,A,B=map(number,(theta,subs,A,B));require(0<theta<1 and subs>=0 and A>subs and B>0,'strict feasible economy');p=B/A;income=B;discretionary=income-p*subs;food=subs+theta*discretionary/p;manufactures=(1-theta)*discretionary;return p,food/A,food,manufactures

def bounds(response,mean,lo,hi,control):
    response,mean,lo,hi,control=map(number,(response,mean,lo,hi,control));require(0<response<=1 and lo<=mean<=hi and lo<=hi,'observed response/support');return response*mean+(1-response)*lo-control,response*mean+(1-response)*hi-control
class Read(HTMLParser):
    def __init__(self):super().__init__();self.ids=[];self.cases=[];self.prompts=[];self.solutions=[];self.markers={};self.stack=[];self.sources={}
    def handle_starttag(self,t,a):
        a=dict(a)
        if 'id'in a:self.ids.append(a['id'])
        if 'worked'in a.get('class','').split():self.cases.append(a['id'])
        if t=='li' and any(tag=='ol' and 'exercises'in d.get('class','').split()for tag,d in self.stack):self.prompts.append(a['id'])
        if 'data-solution-for'in a:
            require(any(tag=='details'and 'solutions'in d.get('class','').split()for tag,d in self.stack),'solution disclosure');self.solutions.append(a['data-solution-for'])
        if 'data-source'in a:self.sources[a['data-source']]=a['href']
        for k in ('data-input','data-result'):
            if k in a:require(a[k]not in self.markers,'unique marker');self.markers[a[k]]=''
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
        raise ValueError('numeric-only expression')
    return walk(ast.parse(s.split('=')[-1].strip().replace('−','-'),mode='eval').body)

def check(root=None):
    root=Path(root)if root else Path(__file__).resolve().parents[1];html=(root/FILES[0]).read_text();r=Read();r.feed(html);r.close();require(not r.stack and len(r.ids)==len(set(r.ids)),'structure');require(len(r.cases)==5 and len(r.prompts)==10 and r.prompts==r.solutions,'exact prompt coverage')
    source=json.loads((root/FILES[2]).read_text());require(r.sources=={s['id']:s['url']for s in source['sources']},'scoped citations');peer=json.loads((root/FILES[5]).read_text());require(set(peer['payload_bindings'])==set(FILES[:5]),'five nonself bindings')
    for path,b in peer['payload_bindings'].items():
        data=(root/path).read_bytes();require(len(data)==b['bytes']and sha256(data).hexdigest()==b['sha256'],'frozen payload')
    author=json.loads((root/FILES[3]).read_text());require(set(author['payload_bindings'])==set(FILES[:3]),'author nonself binding set')
    for path,b in author['payload_bindings'].items():
        data=(root/path).read_bytes();require(len(data)==b['bytes']and sha256(data).hexdigest()==b['sha256'],'author nonself payload')
    comparisons=0
    def eq(x,y):
        nonlocal comparisons
        if isinstance(y,(tuple,list)):
            require(isinstance(x,(tuple,list))and len(x)==len(y),'shape')
            for a,b in zip(x,y):eq(a,b)
        else:require(abs(float(x)-float(y))<2e-9*max(1,abs(float(y))),'mismatch '+str((x,y)));comparisons+=1
    inp={'poverty-y':(2,6,9,15),'poverty-z':10,'poverty-budget':4,'credit':(8,4,1,3),'credit-wealth':(0,2,5),'capability':(1,1,4,2,2,2,1),'structural':(F(1,3),1,4,8,2),'experiment-size':4,'experiment':(4,2,1,F(1,2)),'experiment-response':F(4,5),'experiment-observed':F(11,2),'experiment-support':(0,10)}
    for k,v in inp.items():eq(parse(r.markers[k]),v)
    y=parse(r.markers['poverty-y']);z=parse(r.markers['poverty-z']);budget=parse(r.markers['poverty-budget']);A,C,R,limit=parse(r.markers['credit']);wealths=parse(r.markers['credit-wealth']);a,b,c,ce,ch,w,eta=parse(r.markers['capability']);rows,choices=bundles(a,b,c,ce,ch,w,eta);theta,subs,A0,A1,B=parse(r.markers['structural']);e0=equilibrium(theta,subs,A0,B);e1=equilibrium(theta,subs,A1,B);price=e0[0];prod0=(price*A0,B);prod1=(price*A1,B);ls0=(e0[1],1-e0[1]);ls1=(e1[1],1-e1[1]);dL=tuple(v-u for u,v in zip(ls0,ls1));dq=tuple(v-u for u,v in zip(prod0,prod1));within=sum(l*d for l,d in zip(ls0,dq));realloc=sum(l*p for l,p in zip(dL,prod1));oldout=sum(l*p for l,p in zip(ls0,prod0));newout=sum(l*p for l,p in zip(ls1,prod1));base,direct,spill,sat=parse(r.markers['experiment']);n=int(parse(r.markers['experiment-size']));assigned=list(combinations(range(n),int(n*sat)));Y=lambda d,g:base+direct*d+spill*g;treated=Y(1,sat);untreated=Y(0,sat);polmean=sum(sum(Y(int(i in S),sat)for i in range(n))/n for S in assigned)/len(assigned);effect=polmean-base;response=parse(r.markers['experiment-response']);observed=parse(r.markers['experiment-observed']);lo,hi=parse(r.markers['experiment-support']);no=credit(A,C,R,0,5);hom0=equilibrium(theta,0,A0,B);hom1=equilibrium(theta,0,A1,B)
    outputs={'poverty-indices':poverty(y,z),'poverty-progressive':poverty((y[0]+1,y[1]-1,y[2],y[3]),z),'poverty-headcount-policy':poverty((2,9,10,15),z),'poverty-severity-policy':poverty((6,6,9,15),z),'credit-unconstrained':((A/(2*R))**2,A*A/(4*R)-R*C),'credit-choices':tuple(credit(A,C,R,limit,ww)[:2]for ww in wealths),'capability-private':tuple(t[4]for t in rows),'capability-social':tuple(t[5]for t in rows),'capability-funded':(a+b+c-ce,eta,-ch,a+b+c-ce+eta-ch),'structural-old':e0,'structural-new':e1,'structural-output':newout,'structural-decomposition':(within,realloc,newout-oldout),'experiment-effects':(treated-untreated,untreated-base,effect),'experiment-wald':effect/sat,'experiment-bounds':bounds(response,observed,lo,hi,base),'ex1-r':poverty(y[:2],z),'ex1-u':poverty(y[2:],z),'ex2-budget':sum(max(z-v,0)for v in y),'ex3-noloan':(no[0],no[2],no[3],no[1]),'ex4-best':F(3)**2/4-4,'ex5-small':(1,0,-1,0),'ex5-large':(a+b+c-ce,eta,-ch,a+b+c-ce+eta-ch),'ex6-interaction':rows[3][3]-rows[1][3]-rows[2][3]+rows[0][3],'ex7-shares':(hom0[1],hom1[1]),'ex7-growth':price*(hom1[2]-hom0[2])+hom1[3]-hom0[3],'ex8-decomposition':(sum(l*d for l,d in zip(ls1,dq)),sum(l*p for l,p in zip(dL,prod0)),sum(l*d for l,d in zip(dL,dq))),'ex9-target':direct*sat}
    for k,v in outputs.items():eq(parse(r.markers[k]),v)
    require(set(r.markers)==set(inp)|set(outputs),'all markers reconstructed')
    # Subgroup identities, line equality, convex supporting-gradient and pure transfer accounting.
    eq(poverty((0,10,20),10),(F(1,3),F(1,3),F(1,3)));eq(tuple((u+v)/2 for u,v in zip(outputs['ex1-r'],outputs['ex1-u'])),outputs['poverty-indices'])
    for t in ((0,0,0,0),(4,0,0,0),(0,4,0,0),(1,3,0,0),(2,2,0,0),(0,0,1,3),(0,0,0,4)):
        actual=poverty(tuple(v+dv for v,dv in zip(y,t)),z)[2];tangent=F(-8,400)*(t[0]-4+t[1])+F(-2,400)*t[2];require(actual-outputs['poverty-severity-policy'][2]>=tangent>=0,'global convex certificate');comparisons+=1
    exits=sorted(max(z-v,0)for v in y if v<z);eq(sum(exits[:2]),5)
    for ww in (0,1,2,5,20):
        chosen=credit(A,C,R,limit,ww);k,gain,out,terminal,loan,saved=chosen;eq(terminal-R*ww,gain)
        if gain>0:eq(ww+loan,C+k+saved);eq(terminal,out+R*saved-R*loan);require(loan<=limit,'lender capacity');comparisons+=1
    for ww in (0,4,20,100):eq(credit(3,4,1,100,ww)[:2],(0,0))
    eq(credit(4,4,1,100,10)[:2],(0,0));threshold=29-16*sqrt(3);k0=threshold+3-4;eq(8*sqrt(k0)-(4+k0),0);require(credit(8,4,1,3,threshold-1e-5)[1]==0 and credit(8,4,1,3,threshold+1e-5)[1]>0,'strict entry threshold');comparisons+=1
    eq(choices,((0,0),));eq(bundles(a,b,c,ce,ch,w+1,eta)[1],((0,0),));eq(bundles(a,b,c,ce,ch,w+2,eta)[1],((1,1),));eq(sum(outputs['capability-funded'][:3]),outputs['capability-funded'][3])
    for th,ab,aa,bb in ((F(1,3),1,4,2),(F(1,3),1,8,2),(F(1,2),0,4,3),(F(2,3),1,2,5)):
        p,la,food,m=equilibrium(th,ab,aa,bb);eq(p*food+m,bb);eq(food/aa+m/bb,1);eq(th/(food-ab),(1-th)*p/m);require(0<la<1,'strict sector shares');comparisons+=1
    # Actual two-stage assignment enumeration proves unit-specific HT identities even with heterogeneity.
    events=[(F(1,2),(),F(0))]+[(F(1,12),S,sat)for S in assigned]
    for i in range(n):
        for dd,gg in ((0,F(0)),(0,sat),(1,sat)):
            prob=sum(weight for weight,S,g in events if int(i in S)==dd and g==gg);potential=base+i+direct*dd+spill*gg;ht=sum(weight*(base+i+direct*int(i in S)+spill*g)/prob for weight,S,g in events if int(i in S)==dd and g==gg);eq(ht,potential)
    eq(bounds(F(1,2),observed,lo,hi,base),(F(-5,4),F(15,4)));eq(bounds(1,observed,lo,hi,base),(observed-base,observed-base))
    bad=[lambda:number(True),lambda:number(float('inf')),lambda:poverty([],10),lambda:poverty((1,-1),10),lambda:poverty((1,),0),lambda:poverty((1,2),10,(1,1)),lambda:poverty((1,2),10,(1,)),lambda:credit(0,4,1,3,2),lambda:credit(8,0,1,3,2),lambda:credit(8,4,0,3,2),lambda:credit(8,4,1,-1,2),lambda:credit(8,4,1,3,-2),lambda:bundles(1,1,-1,2,2,2,1),lambda:bundles(1,1,4,0,2,2,1),lambda:equilibrium(0,1,4,2),lambda:equilibrium(1,1,4,2),lambda:equilibrium(F(1,3),4,4,2),lambda:equilibrium(F(1,3),-1,4,2),lambda:bounds(0,5,0,10,4),lambda:bounds(F(6,5),5,0,10,4),lambda:bounds(F(4,5),11,0,10,4),lambda:parse('f(1)')]
    rejected=0
    for fn in bad:
        try:fn()
        except(ValueError,TypeError,ZeroDivisionError):rejected+=1
        else:raise ValueError('domain guard failed')
    return {'chapter':'v15-c04','role':'separate-peer','status':'pass','comparisons':comparisons,'domain_rejections':rejected,'worked_cases':5,'solutions':10,'input_groups':len(inp),'output_groups':len(outputs),'runtime_files':6}
if __name__=='__main__':check()
