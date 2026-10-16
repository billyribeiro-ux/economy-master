"""Exact four-file environmental chapter audit. Quiet API and CLI."""
import ast,json
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from math import isfinite,log
from pathlib import Path
FILES=('content/chapters/v15-c12.html','scripts/check_v15_c12.py','content/reviews/v15-c12-sources.json','content/reviews/v15-c12-author.json')
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
def compensation(a,w=1):
    a,w=map(num,(a,w));need(a>=0 and w>=0,'compensation domain');lo=F(3);hi=9/(1+a);need(lo<=hi,'Pareto feasibility');slope=w-(1+a);opt=(lo,lo) if slope<0 else ((hi,hi) if slope>0 else (lo,hi));return lo,hi,opt
def gains(x,a):
    x,a=map(num,(x,a));need(x>=0 and a>=0,'transfer domain');return 9-(1+a)*x,F(2),-3+x

def bounds(D,l,u,share,cost):
    D,l,u,share,cost=map(num,(D,l,u,share,cost));need(l<=u and 0<=share<=1 and cost>=0,'bound domain');return 8*share*(D-u)-cost,8*share*(D-l)-cost

def regret(low,high):
    low,high=map(num,(low,high));need(low<=high,'ordered payoff interval')
    if low>=0:return F(1),F(0)
    if high<=0:return F(0),F(0)
    r=high/(high-low);return r,-low*r

def workload(K):
    K=num(K);need(K>=0,'capacity nonnegative')
    if K<=2:x,y,lam=F(0),K,10-2*K
    elif K<=17:x,y,lam=(2*K-4)/5,(K+8)/5,(34-2*K)/5
    else:x,y,lam=F(6),F(5),F(0)
    value=12*x-x*x+10*y-y*y;return x,y,lam,K-2*x-y,2*(x+y),value

def coalition(capacity,rule):
    M=num(capacity);need(M>=0 and rule in ('majority','veto','unanimity'),'institution domain');pairs={'majority':((F(0),F(1)),(F(3),F(0))), 'veto':((F(3),F(0)),), 'unanimity':((F(3),F(1)),)}[rule];feasible=[(a,b) for a,b in pairs if F(5,4)*(a+b)<=min(M,8)]
    if not feasible:return None
    a,b=min(feasible,key=lambda x:sum(x));out=F(5,4)*(a+b);g=(8-out,-3+a,-1+b);return a,b,out,g,sum(g)
def pilot(p,cost=F(3,4)):
    p,cost=map(num,(p,cost));need(0<=p<=1 and cost>=0,'pilot domain');mass=(1+2*p)/4;postp=3*p/(1+2*p);postn=p/(3-2*p);vp=12*postp-4;vn=12*postn-4;G=mass*max(0,vp)+(1-mass)*max(0,vn);immediate=max(0,12*p-4);return mass,postp,postn,vp,vn,G,G-cost,G-cost-immediate

def alpha_budget(alpha,n):
    alpha=num(alpha);need(0<alpha<1 and type(n) is int and n>=1,'error budget domain');return sum(alpha/F(t*(t+1)) for t in range(1,n+1))
class Read(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.stack=[];self.active=[];self.inputs={};self.outputs={};self.prompts=[];self.solutions=[];self.cases=[];self.ids=[];self.sources={};self.links=set();self.disclosures=0
    def handle_starttag(self,t,attrs):
        a=dict(attrs);need(len(a)==len(attrs),'unique attributes');need(t!='h1','fragment heading')
        if 'id' in a:need(a['id'].startswith('v15-c12-') and a['id'] not in self.ids,'chapter unique IDs');self.ids.append(a['id'])
        if t=='article' and 'worked' in a.get('class','').split():self.cases.append(a['id'])
        if t=='li' and a.get('id','').startswith('v15-c12-e'):self.prompts.append(a['id'])
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
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1];raw={f:(root/f).read_bytes() for f in FILES};doc=Read();doc.feed(raw[FILES[0]].decode());need(not doc.stack,'closed HTML');review=json.loads(raw[FILES[3]]);sources=json.loads(raw[FILES[2]]);bb=review['payload_bindings'];need(len(bb)==3 and {b['path'] for b in bb}==set(FILES[:3]),'three nonself hashes')
    for b in bb:need((len(raw[b['path']]),sha256(raw[b['path']]).hexdigest())==(b['bytes'],b['sha256']),'frozen binding')
    ex=['v15-c12-e'+str(i) for i in range(1,11)];need(doc.prompts==doc.solutions==ex and set(review['exact_prompt_review'])==set(ex),'ten matched exact solutions');need(doc.cases==['v15-c12-case'+str(i) for i in range(1,6)] and doc.disclosures==3,'five cases and answer guides');need({'v15-c11.html','curriculum.html#v16-c01'}<=doc.links,'dependency and planned successor');need(doc.sources=={s['id']:s['url'] for s in sources['sources']} and len(doc.sources)==2,'two scoped method sources')
    inputs={k:literal(v) for k,v in doc.inputs.items()};shown={k:literal(v) for k,v in doc.outputs.items()};expected={};count=0
    def eq(a,b,msg='identity'):
        nonlocal count
        if isinstance(a,(tuple,list)) or isinstance(b,(tuple,list)):
            need(isinstance(a,(tuple,list)) and isinstance(b,(tuple,list)) and len(a)==len(b),msg+'shape')
            for x,y in zip(a,b):eq(x,y,msg)
        else:count+=1;need(a==b,msg+str((a,b)))
    primitives={'benefits':(12,6,2),'taxes':(3,4,5),'transfer-cost':F(1,5),'did':(10,15,8,10),'capacity':(8,14,12,2,2,1),'political':(8,-3,-1,F(1,4),4),'pilot':(F(2,5),F(3,4),F(1,4),8,-4,F(3,4))};need(set(inputs)==set(primitives),'input groups')
    for k,v in primitives.items():eq(inputs[k],v,k)
    benefit,tax,a=inputs['benefits'],inputs['taxes'],inputs['transfer-cost'];base=tuple(x-y for x,y in zip(benefit,tax));expected['initial-gains']=base;eq(sum(tax),12);lo,hi,opt=compensation(a);expected['compensation-interval']=(lo,hi);g=gains(lo,a);expected['compensated']=(*g,sum(g));eq(sum(g),sum(benefit)-sum(tax)-a*lo);need(tax[0]+(1+a)*hi<=20,'all feasible transfers prefunded');count+=1
    lo2,hi2,_=compensation(F(1,2));g=gains(lo2,F(1,2));expected['e1']=(lo2,hi2,*g,sum(g));_,_,oo=compensation(a,2);g=gains(oo[0],a);expected['e2']=(oo[0],*g,g[0]+g[1]+2*g[2],sum(g))
    for aa in (F(0),F(1,5),F(1,2),F(2)):
        low,high,_=compensation(aa)
        for w in (F(0),F(1),1+aa,F(3)):
            _,_,(l,h)=compensation(aa,w);obj=lambda x:sum(gains(x,aa)[:2])+w*gains(x,aa)[2];eq(obj(l),obj(h))
            for x in (low,(low+high)/2,high):
                need(min(gains(x,aa))>=0,'Pareto constraints');need(obj(x)<=obj(l),'linear global comparison');eq(sum(gains(x,aa)),8-aa*x);count+=2
    t0,t1,c0,c1=inputs['did'];D=(t1-t0)-(c1-c0);eff=(D-2,D+1);expected['effect-bounds']=(*eff,*(F(3,4)*v for v in eff),*(F(1,4)*v for v in eff));pay=bounds(D,-1,2,F(1,4),4);expected['target-payoff']=pay;expected['randomized-regret']=regret(*pay);other=bounds(D,-2,2,F(1,4),4);expected['e3']=(*other,*regret(*other));expected['e4']=(8*F(1,4)*eff[0],4/(8*eff[0]));eq(tuple(8*F(3,4)*v-4 for v in eff),(2,20))
    for gamma in (F(-2),F(-1),F(0),F(1),F(2)):
        untreated=t0+(c1-c0)+gamma;tau=t1-untreated;eq(tau+gamma,D);eq(untreated+tau,t1)
    for lower,upper in ((F(-2),F(4)),(F(-2),F(6)),(F(1),F(4)),(F(-4),F(-1))):
        r,v=regret(lower,upper)
        for rr in (F(0),F(1,4),F(1,2),F(3,4),F(1)):
            L=max(max(0,lower)-rr*lower,max(0,upper)-rr*upper);need(L>=v,'minimax global witnesses');count+=1
        eq(v,max(max(0,lower)-r*lower,max(0,upper)-r*upper))
    K=inputs['capacity'][0];x,y,lam,slack,outlay,value=workload(K);expected['capacity-allocation']=(x,y,lam,outlay,value);eq(2*x+y,K);eq((14*x-x*x)+(12*y-y*y)-outlay,value);eq(100-outlay+outlay,100)
    for X in (F(0),F(1),F(2),F(4)):
        for Y in (F(0),F(1),F(2),F(4),F(8)):
            if 2*X+Y<=K:eq(value-(12*X-X*X+10*Y-Y*Y),(X-x)**2+(Y-y)**2+lam*(K-2*X-Y))
    for kk in (F(0),F(1),F(2),F(8),F(9),F(17),F(20)):
        xx,yy,ll,unused,cost,V=workload(kk);need(min(xx,yy,ll,unused)>=0,'workload feasibility');eq(ll*unused,0);need((xx==0 and 12-2*xx<=2*ll) or (xx>0 and 12-2*xx==2*ll),'A KKT');need((yy==0 and 10-2*yy<=ll) or (yy>0 and 10-2*yy==ll),'B KKT');need(cost<=30,'funded optimum');count+=3
    small,large=workload(1),workload(20);expected['e5']=(*small[:3],small[4],small[5],*large[:2],large[3],large[4],large[5]);next_=workload(9);expected['e6']=(next_[5],next_[5]-value,lam,next_[5]-value-3,next_[4]+3);eq(next_[5],61-(17-F(9))**2/5);eq(next_[5]-value,lam-F(1,5));need(next_[4]+3<=30,'capacity expansion funding')
    M=inputs['political'][-1];maj=coalition(M,'majority');veto=coalition(M,'veto');expected['majority']=(*maj[3],maj[4],maj[2]);expected['veto']=(*veto[3],veto[4],veto[2]);need(coalition(M,'unanimity') is None,'unanimity budget failure');un=coalition(5,'unanimity');expected['e7']=(*un[:3],*un[3],un[4]);expected['e8']=(maj[2],veto[2],maj[4],F(0));need(coalition(3,'veto') is None and coalition(3,'majority')==maj,'reduced authorization');eq(8+(-3)+(-1),4)
    for rule,M in (('majority',4),('veto',4),('unanimity',5)):
        chosen=coalition(M,rule);threshold=chosen[2]
        for t2 in (F(0),F(1),F(3),F(4)):
            for t3 in (F(0),F(1),F(2),F(4)):
                out=F(5,4)*(t2+t3);gg=(8-out,-3+t2,-1+t3);votes=tuple(v>=0 for v in gg);passed=sum(votes)>=2 and (rule!='veto' or votes[1]) and (rule!='unanimity' or all(votes))
                if passed and out<=M:need(out>=threshold,'minimal winning coalition');count+=1
                eq(sum(gg),4-F(1,4)*(t2+t3));need(4+out<=100,'district funding');count+=1
    p,ph,pl,vh,vl,pcost=inputs['pilot'];pi=pilot(p,pcost);expected['pilot-decision']=pi;mass=pi[0];eq(pi[1],p*ph/(p*ph+(1-p)*pl));eq(pi[2],p*(1-ph)/(p*(1-ph)+(1-p)*(1-pl)));eq(p*vh+(1-p)*vl,F(4,5));eq(p*ph*18+(1-p)*pl*6,F(63,10));eq(pcost+10*mass,F(21,4));eq(pcost+10,F(43,4));need(pcost+10<=12,'worst-case appropriation');eq(p*ph*18+(1-p)*pl*6-(pcost+10*mass),pi[6]);eq(p*vh-max(0,p*vh+(1-p)*vl),F(12,5))
    for prior in (F(0),F(1,7),F(1,4),F(1,3),F(2,5),F(9,20),F(3,5),F(1)):
        m,post1,post0,V1,V0,G,net,gain=pilot(prior);piece=F(0) if prior<=F(1,7) else (7*prior-1 if prior<=F(3,5) else 12*prior-4);eq(G,piece);need((gain>0)==(F(1,4)<prior<F(9,20)),'complete pilot prior region');need(max(0,12*prior-4)<=G<=8*prior,'information bounds');count+=2
        for adopt1 in (0,1):
            for adopt0 in (0,1):need(m*adopt1*V1+(1-m)*adopt0*V0<=G,'full contingent menu');count+=1
    expected['e9']=(F(1,4),F(9,20));tie=pilot(F(1,4));eq((tie[0],tie[3],tie[5],tie[6]),(F(3,8),2,F(3,4),0));alpha=F(1,20);expected['e10']=(alpha_budget(alpha,5),alpha,1-(1-alpha)**5)
    for n in (1,2,5,10,100):eq(alpha_budget(alpha,n),alpha*(1-F(1,n+1)))
    need(set(expected)==set(shown),'all displayed result groups')
    for k,v in expected.items():eq(shown[k],v,'display '+k)
    invalid=(lambda:num(True),lambda:num(float('inf')),lambda:literal('1/0'),lambda:literal('f(1)'),lambda:compensation(-1),lambda:compensation(3),lambda:compensation(0,-1),lambda:gains(-1,0),lambda:bounds(3,2,-1,F(1,4),4),lambda:bounds(3,-1,2,2,4),lambda:bounds(3,-1,2,F(1,4),-1),lambda:regret(4,-2),lambda:workload(-1),lambda:coalition(-1,'majority'),lambda:coalition(4,'dictator'),lambda:pilot(-1),lambda:pilot(2),lambda:pilot(F(1,2),-1),lambda:alpha_budget(0,5),lambda:alpha_budget(alpha,True),lambda:alpha_budget(alpha,0));reject=0
    for fn in invalid:
        try:fn()
        except ValueError:reject+=1
        else:raise ValueError('invalid domain accepted')
    for f,b in raw.items():need((root/f).read_bytes()==b,'unchanged author payload')
    result={'chapter':'v15-c12','status':'passed','worked_cases':5,'solutions':10,'input_groups':len(inputs),'result_groups':len(shown),'comparisons':count,'rejected_inputs':reject,'runtime_files':4,'open_findings':[]};json.dumps(result,allow_nan=False);return result
if __name__=='__main__':check()
