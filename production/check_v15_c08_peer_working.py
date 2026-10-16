"""Independent six-file behavioral chapter peer. No author execution/import."""
import ast,json
from fractions import Fraction as Q
from hashlib import sha256
from html.parser import HTMLParser
from math import log,sqrt,isfinite
from pathlib import Path
FILES=('production/v15-c08-working.html','production/check_v15_c08_working.py','production/v15-c08-sources-working.json','production/v15-c08-author-review-working.json','production/check_v15_c08_peer_working.py','production/v15-c08-peer-review-working.json')
def need(ok,msg):
    if not ok:raise ValueError(msg)
def number(x):
    need(type(x) in (int,float,Q) and isfinite(float(x)),'finite numeric domain');return Q(str(x)) if isinstance(x,float) else Q(x)
def literal(s):
    def rec(n):
        if isinstance(n,ast.Constant):return number(n.value)
        if isinstance(n,(ast.Tuple,ast.List)):return tuple(rec(t) for t in n.elts)
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,(ast.USub,ast.UAdd)):return (-1 if isinstance(n.op,ast.USub) else 1)*rec(n.operand)
        if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Div):
            b=rec(n.right);need(b!=0,'denominator');return rec(n.left)/b
        raise ValueError('literal only')
    return rec(ast.parse(s.replace('−','-').rsplit('=',1)[-1].strip(),mode='eval').body)
def saved(E,R,b,d,floor=0):
    E,R,b,d,floor=map(number,(E,R,b,d,floor));need(E>0 and R>0 and 0<b<=1 and 0<d<=1 and 0<=floor<E,'saving domain');return max(floor,E/(1+1/(b*d))),E/(1+1/d)
def ref_value(x,r,lam):
    x,r,lam=map(number,(x,r,lam));need(lam>=1,'loss aversion domain');return x-r if x>=r else lam*(x-r)
def social_utility(x,y,a,g):
    x,y,a,g=map(number,(x,y,a,g));need(min(x,y)>=0 and a>=g>=0 and g<1,'social domain');return x-a*max(y-x,0)-g*max(x-y,0)
def gifts(B,a,g):
    B,a,g=map(number,(B,a,g));need(B>0 and a>=g>=0 and g<1,'dictator domain');return (Q(0),Q(0)) if g<Q(1,2) else ((Q(0),B/2) if g==Q(1,2) else (B/2,B/2))
def posterior(pr,hi,lo):
    pr,hi,lo=map(number,(pr,hi,lo));need(all(0<=x<=1 for x in (pr,hi,lo)),'probabilities');den=pr*hi+(1-pr)*lo;need(den>0,'positive signal probability');return pr*hi/den

def score(q,y):
    q=number(q);need(0<=q<=1 and type(y) is int and y in (0,1),'score domain');return 1-(q-y)**2

def cash_report(p):
    p=number(p);need(0<=p<=1,'belief');
    if p in (0,1):return float(p)
    # Squared derivative equality; both sides nonnegative on the open interval.
    def f(q):return p*p*(1-q)**2*(1-q*q)-(1-p)**2*q*q*(2*q-q*q)
    lo,hi=Q(0),Q(1)
    for _ in range(90):
        mid=(lo+hi)/2
        if f(mid)>0:lo=mid
        else:hi=mid
    return float((lo+hi)/2)

def weighted_report(p,a,b):
    p,a,b=map(number,(p,a,b));need(0<=p<=1 and a>0 and b>0,'state prize domain');return p*a/(p*a+(1-p)*b)
def pool(x,y,sx,sy):
    x,y,sx,sy=map(number,(x,y,sx,sy));need(sx>0 and sy>0,'positive standard errors');v=1/(1/sx**2+1/sy**2);return (x/sx**2+y/sy**2)*v,float(v)**.5,float(x-y)/sqrt(float(sx*sx+sy*sy))
class Read(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.stack=[];self.active=[];self.inputs={};self.outputs={};self.prompts=[];self.solutions=[];self.cases=[];self.ids=[];self.sources={};self.links=set();self.disclosures=0
    def handle_starttag(self,t,attrs):
        a=dict(attrs);need(len(a)==len(attrs),'unique attributes');need(t!='h1','fragment heading')
        if 'id' in a:need(a['id'].startswith('v15-c08-') and a['id'] not in self.ids,'chapter unique IDs');self.ids.append(a['id'])
        if t=='article' and 'worked' in a.get('class','').split():self.cases.append(a['id'])
        if t=='li' and a.get('id','').startswith('v15-c08-e'):self.prompts.append(a['id'])
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
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1];raw={f:(root/f).read_bytes() for f in FILES};doc=Read();doc.feed(raw[FILES[0]].decode());need(not doc.stack,'closed document');review=json.loads(raw[FILES[-1]]);author=json.loads(raw[FILES[3]]);sources=json.loads(raw[FILES[2]]);bindings=review['payload_bindings'];need(len(bindings)==5 and {b['path'] for b in bindings}==set(FILES[:-1]),'five nonself bindings')
    for b in bindings:need((len(raw[b['path']]),sha256(raw[b['path']]).hexdigest())==(b['bytes'],b['sha256']),'peer frozen binding')
    for f,b in author['payload_bindings'].items():need((len(raw[f]),sha256(raw[f]).hexdigest())==(b['bytes'],b['sha256']),'author record binding')
    prompts=['v15-c08-e'+str(i) for i in range(1,11)];need(doc.prompts==doc.solutions==prompts and set(review['exact_prompt_review'])==set(prompts),'ten exact solutions');need(doc.cases==['v15-c08-case'+str(i) for i in range(1,6)] and doc.disclosures==3,'cases and retention guides');need({'v15-c07.html','curriculum.html#v15-c09'}<=doc.links,'chapter routes');need(doc.sources=={s['id']:s['url'] for s in sources['sources']},'source identities')
    inp={k:literal(v) for k,v in doc.inputs.items()};shown={k:literal(v) for k,v in doc.outputs.items()};expected={};count=0
    def eq(a,b,name='identity'):
        nonlocal count
        if isinstance(a,(tuple,list)) or isinstance(b,(tuple,list)):
            need(isinstance(a,(tuple,list)) and isinstance(b,(tuple,list)) and len(a)==len(b),name+' shape')
            for x,y in zip(a,b):eq(x,y,name)
        else:
            count+=1
            if isinstance(a,float) or isinstance(b,float):need(abs(float(a)-float(b))<=2e-11*max(1,abs(float(b))),name+str((a,b)))
            else:need(a==b,name+str((a,b)))
    primitives={'time':(12,1,Q(1,2),1),'time-fee':Q(1,20),'reference':(10,6,16,Q(1,2),2),'reference-grid':(0,8,10,12,20),'social':(10,1,Q(3,4)),'belief':(Q(1,2),Q(3,4),Q(1,4),20,0),'factorial':(10,2,3,-1),'replication':(2,Q(4,5),1,1),'multiplicity':(4,Q(1,20))};need(set(inp)==set(primitives),'input set')
    for k,v in primitives.items():eq(inp[k],v,k)
    E,R,b,d=inp['time'];actual,plan=saved(E,R,b,d);earlier=lambda s:float(b*d)*(log(float(E-s))+float(d)*log(float(R*s)));later=lambda s:log(float(E-s))+float(b*d)*log(float(R*s));willing=earlier(plan)-earlier(actual);expected['time-saving']=(actual,plan);expected['time-willingness']=willing;expected['time-later-change']=later(plan)-later(actual);expected['e2-net']=willing-float(inp['time-fee']);expected['e1-saving']=tuple(saved(E,R,b,d,L)[0] for L in (2,6,9));need(0<inp['time-fee']<1 and willing>inp['time-fee'],'voluntary funded service');eq(1-inp['time-fee']+inp['time-fee'],1)
    for bb in (Q(1,4),Q(1,2),Q(1)):
        for dd in (Q(1,2),Q(1)):
            aa,pp=saved(12,2,bb,dd);eq(-1/(12-aa)+bb*dd/aa,0);eq(-1/(12-pp)+dd/pp,0);need(aa<=pp,'earlier desired saving');count+=1
            for L in (Q(0),Q(2),Q(6),Q(9)):
                chosen,_=saved(12,2,bb,dd,L);der=-1/(12-chosen)+bb*dd/chosen;need((chosen>L and der==0) or (chosen==L and der<=0),'floor KKT');eq((12-chosen)+chosen,12);eq(2*chosen,chosen*2);count+=1
    safe,lo,hi,p,lam=inp['reference'];gap=lambda r,prob=p:prob*ref_value(hi,r,lam)+(1-prob)*ref_value(lo,r,lam)-ref_value(safe,r,lam);expected['reference-values']=tuple(gap(r) for r in inp['reference-grid']);expected['reference-log-gap']=float(p)*log(float(hi))+float(1-p)*log(float(lo))-log(float(safe));threshold=lam*(safe-lo)/((hi-safe)+lam*(safe-lo));expected['e4-threshold']=threshold;eq(gap(10,threshold),0)
    for r in (Q(-5),Q(0),Q(6),Q(7),Q(8),Q(9),Q(10),Q(11),Q(12),Q(16),Q(20)):
        branch=Q(1) if r<=6 else (4-r/2 if r<=10 else (-6+r/2 if r<=16 else Q(2)));eq(gap(r),branch);need((gap(r)<0)==(8<r<12),'global reference sign');count+=1
    for pp in (Q(0),Q(1,2),threshold,Q(3,4),Q(1)):eq(gap(10,pp),(6+4*lam)*(pp-threshold))
    budget,alpha,gamma=inp['social'];gift=gifts(budget,alpha,gamma)[0];cut=budget*alpha/(1+2*alpha);expected['social-results']=(gift,social_utility(budget-gift,gift,alpha,gamma),social_utility(budget,0,alpha,gamma),cut,budget-cut);eq(social_utility(cut,budget-cut,alpha,gamma),0);expected['e6-grid']=min(t for t in range(11) if social_utility(t,budget-t,alpha,gamma)>0)
    for gg in (Q(0),Q(1,4),Q(1,2),Q(3,4)):
        l,h=gifts(10,1,gg);best=social_utility(10-l,l,1,gg);eq(best,social_utility(10-h,h,1,gg))
        for t in (Q(j,2) for j in range(21)):
            val=social_utility(10-t,t,1,gg);need(val<=best,'dictator global piece');need((val==best)==(l<=t<=h),'entire dictator argmax');count+=2
    for t in (Q(0),Q(1),cut,Q(4),Q(5),Q(9),Q(10)):
        ur=social_utility(t,10-t,alpha,gamma);need((ur>0)==(t>cut) and (ur==0)==(t==cut),'response threshold');count+=1
        if t>cut:
            smaller=(t+cut)/2;need(cut<smaller<t and 10-smaller>10-t,'strict tie no attained best');count+=1
    for t in (Q(1),Q(3),Q(5),Q(9)):
        need(float(t)+6*log(float(11-t))>0,'altruist accepts positive');der=-1+6/(1+t);need((der>0)==(t<5),'altruist dictator derivative');count+=2
    prior,ph,pl,H,L=inp['belief'];post=posterior(prior,ph,pl);s1,s0=score(post,1),score(post,0);ES=post*s1+(1-post)*s0;expected['belief-scores']=(post,s1,s0,ES);expected['belief-cash-report']=cash_report(post);expected['belief-payment']=L+(H-L)*ES;expected['e7-score-gain']=ES-score(Q(1,2),0);expected['e8-distorted']=weighted_report(post,2,1);eq(ES,Q(13,16));eq(expected['belief-payment']+H-expected['belief-payment'],H);need(0<=expected['belief-payment']<=H,'escrow funded')
    # Polynomial root independent of author's derivative solver, then verify unsquared FOC.
    q=expected['belief-cash-report'];der=float(post)*(1-q)/sqrt(2*q-q*q)-float(1-post)*q/sqrt(1-q*q);eq(der,0.0);need(.5<q<float(post),'report distortion direction');count+=1
    for pp in (Q(0),Q(1,4),Q(1,2),Q(3,4),Q(1)):
        truthful=pp*score(pp,1)+(1-pp)*score(pp,0);cashsol=cash_report(pp)
        for qq in (Q(j,8) for j in range(9)):
            value=pp*score(qq,1)+(1-pp)*score(qq,0);eq(truthful-value,(qq-pp)**2)
            for prizes in ((Q(20),Q(0)),(Q(5),Q(1))):
                h,l=prizes;ev=sqrt(float(l))+(sqrt(float(h))-sqrt(float(l)))*float(value);direct=float(pp)*(float(score(qq,1))*sqrt(float(h))+float(1-score(qq,1))*sqrt(float(l)))+float(1-pp)*(float(score(qq,0))*sqrt(float(h))+float(1-score(qq,0))*sqrt(float(l)));eq(ev,direct)
            eu=lambda z:float(pp)*sqrt(max(0.,2*z-z*z))+float(1-pp)*sqrt(max(0.,1-z*z));need(eu(cashsol)>=eu(float(qq))-1e-12,'cash global witness');count+=1
    for aa,bb in ((Q(1),Q(1)),(Q(2),Q(1)),(Q(1),Q(3))):
        opt=weighted_report(post,aa,bb);eq(post*aa*(1-opt),(1-post)*bb*opt)
    base,tau,eta,interaction=inp['factorial'];cells=tuple(base+tau*z+eta*m+interaction*z*m for z,m in ((0,0),(1,0),(0,1),(1,1)));neutral=cells[1]-cells[0];messaged=cells[3]-cells[2];expected['factorial-cells']=cells;expected['factorial-effects']=(neutral,messaged,(neutral+messaged)/2,messaged-neutral)
    # Enumerate a four-cell assignment law exactly for a finite potential-outcome population.
    probabilities=(Q(1,8),Q(3,8),Q(1,4),Q(1,4));eq(sum(probabilities),1)
    for unit in range(4):
        for target in range(4):
            y=cells[target]+unit;ht=sum(probabilities[assigned]*(y/probabilities[target] if assigned==target else 0) for assigned in range(4));eq(ht,y)
    xx,yy,sx,sy=inp['replication'];pooled,se,z=pool(xx,yy,sx,sy);expected['replication-statistics']=(z,pooled,se);eq(pooled,(xx+yy)/2);eq(z,(float(xx)-float(yy))/sqrt(2));need(xx/sx>1.96 and yy/sy<1.96 and abs(z)<1.96,'significance labels not disagreement');count+=1
    mean2,se2,z2=pool(1,4,1,2);eq(mean2,Q(8,5));eq(se2,sqrt(.8));eq(z2,-3/sqrt(5));n,level=inp['multiplicity'];expected['multiplicity-error']=1-(1-level)**int(n);eq(n*level/n,level);expected['e9-transport']=(Q(1,4)*4+Q(3,4)*0,Q(3,4)*4+Q(1,4)*0)
    # Independent four-null Bernoulli enumeration, rather than relying only on complement formula.
    from itertools import product
    rejection=Q(0)
    for bits in product((0,1),repeat=4):
        mass=Q(1)
        for bit in bits:mass*=level if bit else 1-level
        if any(bits):rejection+=mass
    eq(rejection,expected['multiplicity-error'])
    need(set(expected)==set(shown),'every numerical display')
    for key,v in expected.items():eq(shown[key],v,'display '+key)
    invalid=(lambda:number(True),lambda:number(float('inf')),lambda:literal('1/0'),lambda:literal('f(1)'),lambda:saved(0,1,Q(1,2),1),lambda:saved(12,0,Q(1,2),1),lambda:saved(12,1,0,1),lambda:saved(12,1,1,1,12),lambda:ref_value(10,0,Q(1,2)),lambda:social_utility(-1,2,1,Q(1,2)),lambda:social_utility(1,2,0,Q(1,2)),lambda:gifts(10,2,1),lambda:posterior(0,1,0),lambda:posterior(2,1,0),lambda:score(-1,0),lambda:score(Q(1,2),True),lambda:cash_report(2),lambda:weighted_report(Q(1,2),0,1),lambda:pool(1,2,0,1));reject=0
    for call in invalid:
        try:call()
        except ValueError:reject+=1
        else:raise ValueError('invalid domain accepted')
    for f,b in raw.items():need((root/f).read_bytes()==b,'unchanged files')
    result={'chapter':'v15-c08','status':'passed','worked_cases':5,'solutions':10,'input_groups':len(inp),'result_groups':len(shown),'comparisons':count,'rejected_inputs':reject,'runtime_files':6,'open_findings':[]};json.dumps(result,allow_nan=False);return result
if __name__=='__main__':check()
