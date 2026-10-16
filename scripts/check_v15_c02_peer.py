"""Independent labor/human-capital review; exactly six frozen payloads."""
import ast,json
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from itertools import product
from math import isfinite,sqrt
from pathlib import Path
FILES=('content/chapters/v15-c02.html','scripts/check_v15_c02.py','content/reviews/v15-c02-sources.json','content/reviews/v15-c02-author.json','scripts/check_v15_c02_peer.py','content/reviews/v15-c02-peer.json')
def need(ok,why):
    if not ok:raise ValueError(why)
def num(x):
    need(type(x) in (int,float,F) and isfinite(float(x)),'finite nonboolean number');return F(str(x)) if type(x) is float else F(x)
def literal(s):
    def rec(n):
        if isinstance(n,ast.Constant):return num(n.value)
        if isinstance(n,(ast.Tuple,ast.List)):return tuple(rec(x) for x in n.elts)
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,(ast.USub,ast.UAdd)):return (-1 if isinstance(n.op,ast.USub) else 1)*rec(n.operand)
        if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Div):
            d=rec(n.right);need(d!=0,'nonzero divisor');return rec(n.left)/d
        raise ValueError('numeric literals only')
    return rec(ast.parse(s.replace('−','-').rsplit('=',1)[-1].strip(),mode='eval').body)
def law(p):
    p=tuple(map(num,p));need(p and min(p)>=0 and sum(p)==1,'probability law');return p
def investment(cost,gains,R):
    cost,R=map(num,(cost,R));gains=tuple(map(num,gains));need(cost>=0 and R>0 and gains,'investment domain');return -cost+sum(g/R**t for t,g in enumerate(gains,1))
def compliance(shares,base,effects,direct=0):
    shares=law(shares);base=tuple(map(num,base));effects=tuple(map(num,effects));direct=num(direct);need(len(shares)==len(base)==len(effects)==3 and shares[1]>0,'three types and positive firststage');observed=[];mom=[]
    for z in (0,1):
        cells=[]
        for t in range(3):
            d=int(t==0 or t==1 and z==1);y=base[t]+d*effects[t]+z*direct;cells.append((shares[t],d,y));observed.append((shares[t]/2,d,y))
        mom.append((sum(w*d for w,d,y in cells),sum(w*y for w,d,y in cells)))
    first=mom[1][0]-mom[0][0];rf=mom[1][1]-mom[0][1];means=tuple(sum(w*y for w,d,y in observed if d==a)/sum(w for w,d,y in observed if d==a) for a in (0,1));return (mom[0][0],mom[1][0],mom[0][1],mom[1][1]),(rf/first,sum(w*t for w,t in zip(shares,effects)),means[1]-means[0]),first,rf

def hiring(A,b,s,floor):
    A,b,s,floor=map(num,(A,b,s,floor));need(A>0 and b>=0 and s>0 and floor>=0,'positive marginal revenue/supply domain');kink=max(F(0),(floor-b)/s);flat=min(kink,max(F(0),A-floor));rising=max(kink,(A-b)/(1+2*s));candidates={F(0),kink,flat,rising};profit=lambda l:A*l-l*l/2-max(floor,b+s*l)*l;l=max(candidates,key=profit);w=max(floor,b+s*l);opportunity=b*l+s*l*l/2;revenue=A*l-l*l/2;return l,w,profit(l),w*l-opportunity,revenue-opportunity

def participation(w,K,T):
    w,K,T=map(num,(w,K,T));need(w>=0 and K>0 and T>0,'labor/time/fixedcost domain');l=min(w,T);gain=w*l-l*l/2-K
    if l==0 or gain<0:return (F(0),)
    return (F(0),l) if gain==0 else (l,)
def taste(d):
    d=num(d);need(d>=0,'nonnegative taste penalty');la=F(4);lb=max(F(0),(8-d)/2);wa=4+la;wb=4+lb;money=(12-wa)*la+(12-wb)*lb;return la,wa,lb,wb,money,money-d*lb

def posterior(prior,accuracy):
    prior,accuracy=map(num,(prior,accuracy));need(0<prior<1 and 0<=accuracy<=1,'Bayes signal domain');hi=prior*accuracy+(1-prior)*(1-accuracy);lo=1-hi;need(min(hi,lo)>0,'positive signal events');return (prior*accuracy/hi,prior*(1-accuracy)/lo),(hi,lo)
def callback(nA,nB,cA,cB):
    nA,nB,cA,cB=map(num,(nA,nB,cA,cB));need(all(x.denominator==1 for x in (nA,nB,cA,cB)) and min(nA,nB)>0 and 0<=cA<=nA and 0<cB<=nB,'integer valid callback counts/positive baseline');a=cA/nA;b=cB/nB;v=a*(1-a)/nA+b*(1-b)/nB;se=sqrt(float(v));difference=a-b;return a/b,se,float(difference)-1.96*se,float(difference)+1.96*se

def migration(primitives,kappa,subsidy=0):
    oL,dL,oH,dH,cost=map(num,primitives);kappa,subsidy=map(num,(kappa,subsidy));need(cost>=0 and kappa>=0 and subsidy>=0,'migration costs/congestion domain');low=dL-oL-cost+subsidy;high=dH-oH-cost+subsidy;need(low<=0<high,'high-only migration regime');mass=min(F(1,2),high/kappa) if kappa else F(1,2);need(low-kappa*mass<=0 and (high-kappa*mass==0 or mass==F(1,2)),'private equilibrium');return mass,mass*2,dL-kappa*mass,dH-kappa*mass,mass*subsidy

def moments(rho,variance,error):
    rho,variance,error=map(num,(rho,variance,error));need(abs(rho)<1 and variance>0 and error>=0,'stationary second moment domain');V=variance/(1-rho*rho);return V,rho,rho*V/(V+error)

class Read(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.stack=[];self.active=[];self.inputs={};self.results={};self.prompts=[];self.solutions=[];self.cases=[];self.ids=[];self.sources={};self.links=set();self.disclosures=0
    def handle_starttag(self,t,attrs):
        a=dict(attrs);need(len(a)==len(attrs),'unique attributes')
        if 'id' in a:need(a['id'] not in self.ids and a['id'].startswith('v15-c02-'),'unique chapter IDs');self.ids.append(a['id'])
        if t=='li' and a.get('id','').startswith('v15-c02-e'):self.prompts.append(a['id'])
        if t=='article' and 'worked' in a.get('class','').split():self.cases.append(a['id'])
        if t=='details' and 'solutions' in a.get('class','').split():self.disclosures+=1
        if 'data-solution-for' in a:need(any(t=='details' and 'solutions' in d.get('class','').split() for t,d in self.stack),'enclosed solution');self.solutions.append(a['data-solution-for'])
        if t=='a':self.links.add(a.get('href'))
        if 'data-source' in a:self.sources[a['data-source']]=a['href']
        need(t!='h1','fragment heading')
        for attr,d in (('data-input',self.inputs),('data-result',self.results)):
            if attr in a:k=a[attr];need(k not in d,'unique numeric marker');d[k]='';self.active.append((d,k,len(self.stack)))
        if t not in ('br','hr','img','meta','link','input'):self.stack.append((t,a))
    def handle_data(self,s):
        for d,k,n in self.active:d[k]+=s
    def handle_endtag(self,t):
        need(self.stack and self.stack[-1][0]==t,'balanced markup');self.stack.pop();self.active=[x for x in self.active if x[2]<len(self.stack)]

def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1];raw={f:(root/f).read_bytes() for f in FILES};doc=Read();html=raw[FILES[0]].decode();doc.feed(html);need(not doc.stack,'complete markup');author=json.loads(raw[FILES[3]]);peer=json.loads(raw[FILES[5]]);sources=json.loads(raw[FILES[2]])
    for record,files in ((author,FILES[:3]),(peer,FILES[:5])):
        bind=record['payload_bindings'];need(len(bind)==len(files) and {x['path'] for x in bind}==set(files),'exact nonself binding set')
        for b in bind:need((b['bytes'],b['sha256'])==(len(raw[b['path']]),sha256(raw[b['path']]).hexdigest()),'frozen bytes')
    exercise=['v15-c02-e'+str(i) for i in range(1,11)];need(doc.prompts==doc.solutions==exercise and set(peer['exact_prompt_review'])==set(exercise),'ten exact reviewed solutions');need(doc.cases==['v15-c02-case'+str(i) for i in range(1,6)] and doc.disclosures==3,'five cases and exercise/teach/retention solutions');need('v15-c01.html' in doc.links,'accepted prerequisite');need(doc.sources=={s['id']:s['url'] for s in sources['sources']} and len(doc.sources)==5,'five precise source URLs');need(all(s['verification'] and s['limits'] for s in sources['sources']),'source limits');need('identically distributed' in html or 'i.i.d.' in html or 'iid' in html,'stationary distribution iid correction')
    inp={k:literal(v) for k,v in doc.inputs.items()};shown={k:literal(v) for k,v in doc.results.items()};expected={};comparisons=0
    def equal(a,b,label='identity',tol=2e-10):
        nonlocal comparisons
        if isinstance(a,(tuple,list)) or isinstance(b,(tuple,list)):
            need(isinstance(a,(tuple,list)) and isinstance(b,(tuple,list)) and len(a)==len(b),label+' shape')
            for x,y in zip(a,b):equal(x,y,label,tol)
        else:
            comparisons+=1
            if isinstance(a,float) or isinstance(b,float):need(isfinite(float(a)) and isfinite(float(b)) and abs(float(a)-float(b))<=tol*max(1,abs(float(b))),label)
            else:need(a==b,label+str((a,b)))
    primitive={'school':(30,20,F(11,10)),'iv-shares':(F(1,5),F(2,5),F(2,5)),'iv-baseline':(30,20,10),'iv-effects':(5,10,20),'labor':(20,2,1),'signal':(F(3,4),F(1,4),F(3,4)),'callbacks':(1000,1000,120,80),'migration':(6,8,10,16,3),'mobility':(F(3,5),F(16,25),1)};need(set(inp)==set(primitive),'nine input groups')
    for k,v in primitive.items():equal(inp[k],v,k)
    cost,gain,R=inp['school'];expected['school-npv']=investment(cost,(gain,gain),R);expected['e1']=investment(cost+5,(gain,gain),R);rootR=(1+sqrt(7))/3;equal(investment(cost,(gain,gain),rootR),0.0);need(investment(cost,(gain,gain),F(6,5))>0>investment(cost,(gain,gain),F(5,4)),'strict present value crossing')
    for tuition,loan in ((10,3),(15,8)):equal(12+loan-tuition,5);equal(loan-(loan*R)/R,0);need(loan*R<=50,'feasible date1 repayment')
    shares,base,effects=(inp[x] for x in ('iv-shares','iv-baseline','iv-effects'));mom,returns,first,rf=compliance(shares,base,effects);expected['iv-moments']=mom;expected['iv-returns']=returns;expected['iv-net']=rf-first*6;expected['e3']=(rf-first*11,rf/first);directmom,directreturns,fs,red=compliance(shares,base,effects,2);expected['e2']=(red/fs,(red-2)/fs,red/fs);equal(fs,first);equal(red-rf,2)
    for gamma in (F(0),F(1,2),F(1),F(2)):
        effect=(red-gamma)/fs;equal(fs*effect+gamma,red);need((red-2)/fs<=effect<=red/fs,'identified set')
    A,b,s=inp['labor'];baseline=hiring(A,b,s,0);ten=hiring(A,b,s,10);twelve=hiring(A,b,s,12);expected['labor-results']=(*baseline[:4],ten[0],ten[2],ten[3],twelve[0],twelve[2],twelve[3]);competitive=(A-b)/(1+s);equal(competitive,9);equal(A*competitive-competitive**2/2-(b*competitive+s*competitive**2/2),81)
    fourteen=hiring(A,b,s,14);l,w,profit,workers,total=fourteen;available=(14-b)/s;alternative_cost=b*l+s*((4+l)**2-4**2)/2;alternative_workers=w*l-alternative_cost;expected['e4']=(l,available,profit,workers,total,alternative_workers,profit+alternative_workers)
    # Independently solve each concave branch; dense deviations also check boundaries and altered primitives.
    for aa,bb,ss in ((A,b,s),(F(15),F(3),F(2))):
        for floor in (0,2,7,8,9,10,11,12,14,19,20,21):
            l,w,p,ws,ts=hiring(aa,bb,ss,floor);equal(p+ws,ts);equal(w*l-p,2*w*l-(aa*l-l*l/2))
            for j in range(25):
                deviation=F(j,2);value=aa*deviation-deviation*deviation/2-max(F(floor),bb+ss*deviation)*deviation;need(value<=p,'global hiring deviation');comparisons+=1
    for floor in (8,11,20):
        l=hiring(A,b,s,floor)[0];equal(l,{8:6,11:9,20:0}[floor])
    expected['e5']=(sqrt(2*8),sqrt(2*18))
    for K,threshold in ((F(8),F(4)),(F(18),F(6))):
        equal(participation(threshold,K,10),(0,threshold));equal(participation(threshold-F(1,10),K,10),(0,));equal(participation(threshold+F(1,10),K,10),(threshold+F(1,10),));equal(participation(12,K,10),(10,));equal(participation(0,K,10),(0,))
    expected['e6']=taste(6);equal(taste(2),(4,8,3,7,31,25));equal(taste(0),(4,8,4,8,32,32));equal(taste(8)[2],0);equal(taste(12)[2],0)
    pA,pB,accuracy=inp['signal'];postA,massA=posterior(pA,accuracy);postB,massB=posterior(pB,accuracy);wage=lambda p:8+8*p;expected['signal-wages']=(wage(postA[0]),wage(postB[0]),wage(postA[1]),wage(postB[1]));nullA,_=posterior(pA,F(1,2));nullB,_=posterior(pB,F(1,2));perf,_=posterior(pA,1);expected['e7']=(wage(nullA[0]),wage(nullB[0]),wage(perf[0]),wage(perf[1]))
    for prior in (pA,pB):
        for acc in (0,F(1,2),F(3,4),1):
            posts,ps=posterior(prior,acc);equal(sum(a*b for a,b in zip(posts,ps)),prior);equal(sum(wage(a)*b for a,b in zip(posts,ps)),wage(prior))
    expected['e8']=callback(*inp['callbacks']);nA,nB,cA,cB=inp['callbacks'];equal(cA/nA-cB/nB,F(1,25))
    origins=inp['migration'];m0=migration(origins,12);m1=migration(origins,12,1);expected['e9']=(m0[0],m0[1],m0[2],m0[3],m1[0],m1[4]);equal(migration(origins,4)[0],F(1,2));equal(migration(origins,8)[0],F(3,8));equal(migration(origins,6)[0],F(1,2));equal(migration(origins,0)[0],F(1,2));equal(origins[3]-origins[0],10);equal(origins[3]-origins[2]-origins[4],3);equal(((origins[1]-origins[0])+(origins[3]-origins[2]))/2,4)
    rho,variance,error=inp['mobility'];mm=moments(rho,variance,error);expected['mobility-results']=mm;expected['e10']=moments(rho,variance,error/2)[2];V=mm[0];equal(rho*rho*V+variance,V);equal(moments(F(4,5),F(9,25),0)[0],V)
    for n in range(1,9):
        partial=sum(rho**(2*j)*variance for j in range(n));tail=V*rho**(2*n);equal(partial+tail,V);equal(sum(rho**(2*j+1)*variance for j in range(n)),rho*partial)
    need(set(expected)==set(shown),'every17 result group')
    for k,v in expected.items():equal(shown[k],v,'display '+k)
    invalid=(lambda:num(True),lambda:num(float('nan')),lambda:literal('1/0'),lambda:literal('f(1)'),lambda:law((1,1)),lambda:law((-1,2)),lambda:investment(30,(20,20),0),lambda:compliance((F(1,2),0,F(1,2)),base,effects),lambda:hiring(20,2,0,10),lambda:hiring(20,2,1,-1),lambda:participation(-1,8,10),lambda:participation(4,8,0),lambda:taste(-1),lambda:posterior(0,F(1,2)),lambda:posterior(F(1,2),2),lambda:callback(0,1000,0,80),lambda:callback(10,10,11,1),lambda:callback(10,10,1,0),lambda:callback(F(3,2),10,1,1),lambda:migration(origins,-1),lambda:migration(origins,12,4),lambda:moments(1,1,0),lambda:moments(0,0,0),lambda:moments(F(1,2),1,-1));rejected=0
    for fn in invalid:
        try:fn()
        except ValueError:rejected+=1
        else:raise ValueError('invalid input accepted')
    for f,b in raw.items():need((root/f).read_bytes()==b,'unchanged payload')
    summary={'chapter':'v15-c02','review':'separate-peer','status':'passed','worked_cases':5,'solutions':10,'input_groups':len(inp),'result_groups':len(shown),'comparisons':comparisons,'rejected_inputs':rejected,'runtime_files':6,'resolved_findings':1,'open_findings':[]};json.dumps(summary,allow_nan=False);return summary
if __name__=='__main__':check()
