"""Independent graduate oral/support audit; author executable is hashed, never run."""
import ast,json,re
from fractions import Fraction as Q
from hashlib import sha256
from html.parser import HTMLParser
from itertools import product
from math import isfinite
from pathlib import Path
FILES=('content/cross-assessments/parts/graduate-support-opening.html','content/cross-assessments/parts/graduate-support-closing.html','scripts/check_graduate_support.py','content/reviews/graduate-support-sources.json','content/reviews/graduate-support-author.json','scripts/check_graduate_support_peer.py','content/reviews/graduate-support-peer.json')
def require(ok,msg):
    if not ok:raise ValueError(msg)
def number(x):
    require(type(x) in (int,float,Q) and isfinite(float(x)),'finite nonboolean scalar');return Q(str(x)) if type(x) is float else Q(x)
def readnum(s):
    def visit(n):
        if isinstance(n,ast.Constant):return number(n.value)
        if isinstance(n,(ast.Tuple,ast.List)):return tuple(visit(e) for e in n.elts)
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,(ast.USub,ast.UAdd)):return (-1 if isinstance(n.op,ast.USub) else 1)*visit(n.operand)
        if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Div):
            b=visit(n.right);require(b!=0,'nonzero denominator');return visit(n.left)/b
        raise ValueError('numeric literal grammar')
    return visit(ast.parse(s.replace('−','-').rsplit('=',1)[-1].strip(),mode='eval').body)
def probabilities(ps):
    p=tuple(map(number,ps));require(p and min(p)>=0 and sum(p)==1,'probability law');return p
def sensitivity(delta,pi,epsilon):
    delta,pi,epsilon=map(number,(delta,pi,epsilon));require(pi!=0 and epsilon>=0,'nonzero firststage/positive radius');return tuple(sorted(((delta-epsilon)/pi,(delta+epsilon)/pi)))
def weak(delta,lo,hi):
    delta,lo,hi=map(number,(delta,lo,hi));require(delta>0 and lo<0<hi,'crossing firststage/positive reducedform');return delta/lo,delta/hi

def policy_bounds(means,cost,epsilon):
    means=tuple(map(number,means));cost,epsilon=map(number,(cost,epsilon));require(len(means)==4 and min(means)>=0 and max(means)<=1 and cost>=0 and epsilon>=0,'binary outcome means/cost/radius');effects=(means[0]-means[1],means[2]-means[3]);policies=((0,0),(1,0),(1,1));values=tuple(sum(Q(on,2)*(te-cost) for on,te in zip(p,effects)) for p in policies);radius=tuple(sum(p)*epsilon for p in policies);return values,tuple((v-r,v+r) for v,r in zip(values,radius))
def signal(prior,accuracy,fee):
    prior,accuracy,fee=map(number,(prior,accuracy,fee));require(0<prior<1 and 0<=accuracy<=1 and fee>=0 and fee+1<=2,'feasible information technology');joint=((1-prior)*accuracy,(1-prior)*(1-accuracy),prior*(1-accuracy),prior*accuracy);m0=joint[0]+joint[2];m1=joint[1]+joint[3];require(m0>0 and m1>0,'positive signal probabilities');posts=(joint[2]/m0,joint[3]/m1);gross=m0*posts[0]**2+m1*posts[1]**2;return (m0,m1),posts,gross,gross-fee,gross-fee-prior**2

def auction(values,bids,reserve,fee):
    values=tuple(map(number,values));bids=tuple(map(number,bids));reserve,fee=map(number,(reserve,fee));require(len(values)==len(bids)==2 and min(values)>=0 and 0<=fee<=4 and reserve>=0 and all(0<=b<=4-fee for b in bids),'affordable auction domain');winner=0 if bids[0]>=bids[1] else 1
    if bids[winner]<reserve:return Q(0),-2*fee,(-fee,-fee),None
    payment=max(reserve,bids[1-winner]);utilities=[-fee,-fee];utilities[winner]+=values[winner]-payment;return payment,values[winner]-2*fee,tuple(utilities),winner

def operator_bound(beta,reward_error,residual):
    beta,reward_error,residual=map(number,(beta,reward_error,residual));require(0<=beta<1 and min(reward_error,residual)>=0,'contractive error budget');E=(reward_error+residual)/(1-beta);action=reward_error+beta*E;return E,2*action

def guarantee(p,m,payoff,face):
    p=probabilities(p);m=tuple(map(number,m));payoff=tuple(map(number,payoff));face=number(face);require(len(p)==len(m)==len(payoff)==2 and min(m)>0 and min(payoff)>=0 and face>=0,'positive SDF and payoff domain');price=lambda x:sum(a*b*c for a,b,c in zip(p,m,x));safe=price((1,1));short=tuple(max(Q(0),face-y) for y in payoff);equity=tuple(max(Q(0),y-face) for y in payoff);reserve=max(short);premium=price(short);capital=safe*reserve-premium;return price,payoff,short,equity,reserve,premium,capital

class Reader(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.stack=[];self.active=[];self.inputs={};self.results={};self.solution_text={};self.prompt_text={};self.points={};self.ids=[];self.links=set();self.sources={};self.headings=[]
    def handle_starttag(self,t,attrs):
        a=dict(attrs);require(len(a)==len(attrs),'unique HTML attributes')
        if 'id' in a:require(a['id'] not in self.ids,'unique ID');self.ids.append(a['id'])
        require(t!='h1','no new page heading')
        if t=='h2':self.headings.append(a['id'])
        if t=='a':self.links.add(a.get('href'))
        if 'data-source' in a:self.sources[a['data-source']]=a['href']
        if 'data-points' in a:self.points[a['id']]=int(a['data-points']);self.prompt_text[a['id']]='';self.active.append((self.prompt_text,a['id'],len(self.stack)))
        if 'data-solution-for' in a:
            key=a['data-solution-for'];require(key not in self.solution_text and any(t=='details' and 'solutions' in at.get('class','').split() for t,at in self.stack),'matched solution enclosure');self.solution_text[key]='';self.active.append((self.solution_text,key,len(self.stack)))
        for attr,dest in (('data-input',self.inputs),('data-check',self.results)):
            if attr in a:
                key=a[attr];require(key not in dest,'unique numeric marker');dest[key]='';self.active.append((dest,key,len(self.stack)))
        if t not in ('br','hr','img','meta','link','input'):self.stack.append((t,a))
    def handle_data(self,s):
        for d,k,n in self.active:d[k]+=s
    def handle_endtag(self,t):
        require(self.stack and self.stack[-1][0]==t,'balanced tags');self.stack.pop();self.active=[x for x in self.active if x[2]<len(self.stack)]

def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1];raw={f:(root/f).read_bytes() for f in FILES};peer=json.loads(raw[FILES[-1]]);author=json.loads(raw[FILES[4]]);sources=json.loads(raw[FILES[3]]);doc=Reader()
    for f in FILES[:2]:doc.feed(raw[f].decode());require(not doc.stack,'complete fragment')
    for record,paths in ((author,FILES[:4]),(peer,FILES[:6])):
        bindings=record['payload_bindings'];require(len(bindings)==len(paths) and {b['path'] for b in bindings}==set(paths),'exact nonself bindings')
        for b in bindings:require((b['bytes'],b['sha256'])==(len(raw[b['path']]),sha256(raw[b['path']]).hexdigest()),'frozen payload bytes')
    ids=['graduate-oral-'+x for x in ('e1','e2','m1','m2','a1','a2')];require(list(doc.points)==list(doc.solution_text)==ids and all(p==10 for p in doc.points.values()),'six tenpoint exact prompt solutions');require(all('Change:' in doc.prompt_text[x] for x in ids),'six changed prompts');require(set(peer['exact_solution_review'])==set(ids),'full twelve-answer peer review')
    for x in ids:
        tail=doc.solution_text[x].split('Rubric:');require(len(tail)==2,'one rubric');scores=tuple(map(int,re.findall(r'\d+',tail[1])));require(scores in ((2,2,2,3,1),(2,2,2,2,2)) and sum(scores[:3])==6 and sum(scores[3:])==4,'six baseline/four changed rubric')
    require({f'v{v:02d}-c{c:02d}.html' for v in (12,13,14) for c in range(1,13)}<=doc.links,'all36 remediation routes');require({f'v{v}-assessment.html' for v in (12,13,14)}<=doc.links,'three prerequisite packages');require(doc.sources=={s['id']:s['url'] for s in sources['sources']} and len(doc.sources)==4,'four actual method URLs');require(all(s['verification'] and s['use'] for s in sources['sources']),'scoped provenance');require(doc.headings==['graduate-rules','graduate-oral','graduate-remediation','graduate-evaluator','graduate-source-scope'],'all support headings')
    opening=raw[FILES[0]].decode();closing=raw[FILES[1]].decode()
    for phrase in ('300minutes','85overall','15in every20-point','uncalibrated','not a university qualification'):require(phrase in opening,'administration scope '+phrase)
    for phrase in ('15/20','15minutes','self-study completion','unevaluated oral work','no new source-body'):require(phrase in closing,'oral/inspection boundary '+phrase)
    inp={k:readnum(v) for k,v in doc.inputs.items()};result={k:readnum(v) for k,v in doc.results.items()};expected={};count=0
    def equal(a,b,label='derived identity'):
        nonlocal count
        if isinstance(a,(tuple,list)) or isinstance(b,(tuple,list)):
            require(isinstance(a,(tuple,list)) and isinstance(b,(tuple,list)) and len(a)==len(b),label+' shape')
            for x,y in zip(a,b):equal(x,y,label)
        else:require(a==b,label+str((a,b)));count+=1
    primitive={'oral-e1-inputs':(Q(1,50),Q(1,10),Q(1,200),Q(-1,100),Q(1,100)),'oral-e2-inputs':((Q(4,5),Q(2,5),Q(2,5),Q(1,2)),Q(3,10),Q(1,25),Q(3,50)),'oral-m1-inputs':(Q(1,2),Q(1,10),Q(3,4),Q(1,20)),'oral-m2-inputs':(1,3,Q(1,2),Q(2,5),1,2),'oral-a1-inputs':(Q(4,5),Q(3,1000),Q(1,500),Q(3,100),Q(1,20),Q(1,2000)),'oral-a2-inputs':(Q(1,2),Q(6,5),Q(4,5),1,3,2)};require(set(inp)==set(primitive),'six actual input groups')
    for k,v in primitive.items():equal(inp[k],v,k)
    delta,pi,eps,lo,hi=inp['oral-e1-inputs'];interval=sensitivity(delta,pi,eps);branches=weak(delta,lo,hi);expected['oral-e1-set']=interval;expected['oral-e1-threshold']=branches[1];equal(branches[0],-branches[1]);equal(delta/pi,Q(1,5))
    for j in range(11):
        b=interval[0]+Q(j,10)*(interval[1]-interval[0]);g=delta-b*pi;require(abs(g)<=eps,'sensitivity attainability');equal(b*pi+g,delta)
    for b in (-100,-2,2,100):p=delta/b;require(lo<=p<=hi and p!=0,'weak branch attainability');equal(b*p,delta)
    means,cost,eps,changed=inp['oral-e2-inputs'];values,bounds=policy_bounds(means,cost,eps);expected['oral-e2-values']=values;expected['oral-e2-bounds']=bounds;_,new=policy_bounds(means,cost,changed);equal(new,((0,0),(Q(-1,100),Q(11,100)),(Q(-27,100),Q(-3,100))));require(bounds[1][0]>0 and bounds[1][0]>bounds[2][1] and new[1][0]<0<new[1][1] and new[2][1]<0,'policy certificates')
    for radius,limit in ((eps,bounds),(changed,new)):
        observed=[]
        for signs in product((-1,1),repeat=4):
            true=tuple(m+s*radius for m,s in zip(means,signs));v,_=policy_bounds(true,cost,0);observed.append(v)
            for x,(a,b) in zip(v,limit):require(a<=x<=b,'simultaneous propagation');count+=1
        equal(tuple((min(x[i] for x in observed),max(x[i] for x in observed)) for i in range(3)),limit)
    require('[−1/100,11/100]' in doc.solution_text[ids[1]] and '[−27/100,−3/100]' in doc.solution_text[ids[1]],'visible changed policy endpoints');equal(1-4*Q(1,20),Q(4,5))
    prior,perfectfee,accuracy,noisyfee=inp['oral-m1-inputs'];perfect=signal(prior,1,perfectfee);noisy=signal(prior,accuracy,noisyfee);expected['oral-m1-perfect']=perfect[-1];expected['oral-m1-noisy']=noisy[-1];equal(noisy[1],(Q(1,4),Q(3,4)));equal(noisy[3],Q(21,80))
    for experiment,fee in ((perfect,perfectfee),(noisy,noisyfee)):
        masses,post,gross,net,gain=experiment;equal(sum(w*p for w,p in zip(masses,post)),prior);equal(sum(w*(p-prior)**2 for w,p in zip(masses,post)),gross-prior**2)
        for p in post:
            for action in (Q(0),Q(1,4),p,Q(3,4),Q(1)):equal(2*p*action-action**2,p*p-(action-p)**2);require(action*action+fee<=2,'funded information action')
    low,high,p,fee,r1,r2=inp['oral-m2-inputs'];states=tuple(product((low,high),repeat=2));iid=(p*p,p*(1-p),(1-p)*p,(1-p)**2);correlated=(p,0,0,1-p);out=[]
    for law in (iid,correlated):
        probabilities(law);quantities=[]
        for reserve in (r1,r2):
            outcomes=[auction(s,s,reserve,fee) for s in states];revenue=sum(w*x[0] for w,x in zip(law,outcomes));surplus=sum(w*x[1] for w,x in zip(law,outcomes));quantities.append((revenue,surplus))
            for s,x in zip(states,outcomes):equal(sum(x[2])+x[0],x[1]);require(x[3] is None or max(s)+2*fee>=x[1],'real resource account')
        out.append((quantities[0][0],quantities[1][0],quantities[0][1],quantities[1][1]))
    expected['oral-m2-iid'],expected['oral-m2-correlated']=out;require(out[0][1]>out[0][0] and out[1][1]<out[1][0],'dependence revenue reversal')
    # Boundary/tie witnesses supplement the all-rival threshold proof reviewed in prose.
    bids=(Q(0),low,r1,Q(3,2),r2,high,Q(18,5))
    for value,rival,reserve,who in product((low,high),bids,(r1,r2),(0,1)):
        vals=[low,low];vals[who]=value;truth=[rival,rival];truth[who]=value;truthutility=auction(vals,truth,reserve,fee)[2][who]
        for deviation in bids:
            attempted=list(truth);attempted[who]=deviation;require(auction(vals,attempted,reserve,fee)[2][who]<=truthutility,'truthful auction deviation');count+=1
    beta,reward,residual,gap1,gap2,small=inp['oral-a1-inputs'];bound=operator_bound(beta,reward,residual);newbound=operator_bound(beta,small,residual);expected['oral-a1-base']=bound;expected['oral-a1-changed']=newbound;require(gap1<bound[1]<gap2 and gap1>newbound[1],'strict action certificates');equal(gap2-bound[1],Q(1,250));equal(gap1-newbound[1],Q(9,1000))
    # One-state primitive achieves the value-error upper bound; distinct reward errors bound every action.
    for error in (reward,small):
        trueV=Q(0);computedV=(error+residual)/(1-beta);computedT=error+beta*computedV;equal(abs(computedT-computedV),residual);equal(abs(computedV-trueV),operator_bound(beta,error,residual)[0])
    for mass in (Q(0),Q(1,3),Q(1)):equal((mass,1-mass),(mass*1+(1-mass)*0,mass*0+(1-mass)*1))
    p,mL,mH,yL,yH,face=inp['oral-a2-inputs'];price,y,g,e,reserve,premium,capital=guarantee((p,1-p),(mL,mH),(yL,yH),face);asset=price(y);bankequity=price(e);debt=price((face,face));expected['oral-a2-prices']=(asset,premium,bankequity,capital);equal(price((1,1)),1);equal(asset+premium,debt+bankequity);equal(premium+capital,reserve);remaining=tuple(reserve-x for x in g);equal(price(remaining),capital)
    for yy,gg,ee,rr in zip(y,g,e,remaining):equal(yy+gg,face+ee);equal(gg+rr,reserve);equal(yy+reserve,face+ee+rr)
    dividend=debt-asset;subsidy=dividend+bankequity;expected['oral-a2-subsidy']=subsidy;equal(subsidy,premium);equal(reserve-price(remaining),subsidy);equal(dividend,Q(1,5))
    require(set(expected)==set(result),'every displayed result')
    for k,v in expected.items():equal(result[k],v,k)
    invalid=(lambda:number(True),lambda:number(float('inf')),lambda:readnum('1/0'),lambda:readnum('__import__(1)'),lambda:probabilities((Q(1,3),Q(1,3))),lambda:probabilities((-1,2)),lambda:sensitivity(1,0,1),lambda:sensitivity(1,1,-1),lambda:weak(0,-1,1),lambda:weak(1,0,1),lambda:policy_bounds((2,0,0,0),0,0),lambda:policy_bounds((0,0,0,0),0,-1),lambda:signal(0,1,0),lambda:signal(Q(1,2),2,0),lambda:signal(Q(1,2),1,2),lambda:auction((1,3),(4,3),1,Q(2,5)),lambda:operator_bound(1,0,0),lambda:operator_bound(Q(1,2),-1,0),lambda:guarantee((Q(1,2),Q(1,2)),(0,1),(1,3),2),lambda:guarantee((Q(1,2),Q(1,2)),(1,1),(-1,3),2));rejected=0
    for fn in invalid:
        try:fn()
        except ValueError:rejected+=1
        else:raise ValueError('invalid domain accepted')
    for f,b in raw.items():require((root/f).read_bytes()==b,'no payload mutation')
    summary={'assessment':'graduate-qualifying','component':'support','review':'independent-peer','status':'passed','oral_prompts':6,'baseline_and_changed_answers':12,'remediation_routes':36,'input_groups':len(inp),'result_groups':len(result),'comparisons':count,'rejected_inputs':rejected,'runtime_files':7,'open_findings':[]};json.dumps(summary,allow_nan=False);return summary
if __name__=='__main__':check()
