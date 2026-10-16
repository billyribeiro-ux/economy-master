"""Independent policy synthesis peer oracle: no execution or import of author code."""
from pathlib import Path
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from itertools import product
from math import isfinite
import ast,json
FILES=('content/chapters/v15-c12.html','scripts/check_v15_c12.py','content/reviews/v15-c12-sources.json','content/reviews/v15-c12-author.json','scripts/check_v15_c12_peer.py','content/reviews/v15-c12-peer.json')
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
class Read(HTMLParser):
    def __init__(self):super().__init__();self.stack=[];self.ids=set();self.mark={};self.prompts=[];self.answers={};self.worked=[];self.sources={};self.links=[]
    def handle_starttag(self,t,attrs):
        a=dict(attrs);ensure(len(a)==len(attrs),'unique attributes')
        if 'id' in a:ensure(a['id'] not in self.ids and a['id'].startswith('v15-c12-'),'scoped unique ID');self.ids.add(a['id'])
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
def transfer(base,a,z):
    ensure(len(base)==3,'three people');base=tuple(map(real,base));a,z=map(real,(a,z));ensure(a>=0 and z>=0,'transfer resources');return base[0]-(1+a)*z,base[1],base[2]+z

def pareto(base,a):
    ensure(len(base)==3,'three people');base=tuple(map(real,base));a=real(a);ensure(a>=0 and base[1]>=0,'compensation setting');lo=max(F(0),-base[2]);hi=base[0]/(1+a);ensure(lo<=hi,'nonempty Pareto interval');return lo,hi

def lottery(low,high):
    low,high=map(real,(low,high));ensure(low<=high,'ordered possible payoffs');choices=[F(0),F(1)]
    if low<0<high:choices.append(high/(high-low))
    loss=lambda r:max(max(0,v)-r*v for v in (low,high));best=min(loss(r) for r in choices);return tuple(r for r in choices if loss(r)==best),best

def capacity(K,A=12,B=10):
    K,A,B=map(real,(K,A,B));ensure(K>=0 and A>=0 and B>=0,'capacity domains');Fv=lambda x,y:A*x-x*x+B*y-y*y;candidates=[(F(0),F(0)),(min(A/2,K/2),F(0)),(F(0),min(B/2,K))];x=max(F(0),min(K/2,(A-2*B+4*K)/10));candidates.append((x,K-2*x))
    if A+B/2<=K:candidates.append((A/2,B/2))
    best=max(Fv(x,y) for x,y in candidates);winners=set((x,y) for x,y in candidates if Fv(x,y)==best);ensure(len(winners)==1,'strict concavity unique');x,y=winners.pop();slack=K-2*x-y;lam=F(0) if slack>0 else B-2*y if y>0 else (A-2*x)/2 if x>0 else max(A/2,B);return x,y,lam,slack,2*(x+y),best

def coalition(base,admin,cap,rule):
    ensure(len(base)==3 and rule in ('majority','veto','unanimity'),'institution shape');base=tuple(map(real,base));admin,cap=map(real,(admin,cap));ensure(admin>=0 and cap>=0,'institution resources');menu=[]
    for a,b in product((False,True),repeat=2):
        ts=(max(F(0),-base[1]) if a else F(0),max(F(0),-base[2]) if b else F(0));cost=(1+admin)*sum(ts);g=(base[0]-cost,base[1]+ts[0],base[2]+ts[1]);votes=tuple(v>=0 for v in g);wins=sum(votes)>=2 and (rule!='veto' or votes[1]) and (rule!='unanimity' or all(votes))
        if wins and cost<=cap:menu.append((cost,ts,g))
    if not menu:return None
    cost,ts,g=min(menu);return ts,cost,g,sum(g)

def experiment(p,ph,pl,vh,vl,cost):
    p,ph,pl,vh,vl,cost=map(real,(p,ph,pl,vh,vl,cost));ensure(0<=p<=1 and 0<ph<1 and 0<pl<1 and cost>=0,'pilot domain');joint=((p*ph,(1-p)*pl),(p*(1-ph),(1-p)*(1-pl)));weights=tuple(sum(z) for z in joint);post=tuple(z[0]/sum(z) for z in joint);v=tuple((z[0]*vh+z[1]*vl)/sum(z) for z in joint);menus=[sum((joint[i][0]*vh+joint[i][1]*vl)*actions[i] for i in range(2)) for actions in product((0,1),repeat=2)];gross=max(menus);immediate=max(0,p*vh+(1-p)*vl);return weights,post,v,gross,gross-cost,gross-cost-immediate

def check(root=None):
    base=Path(root) if root is not None else Path(__file__).resolve().parents[1];raw={f:(base/f).read_bytes() for f in FILES};d=Read();d.feed(raw[FILES[0]].decode());d.close();ensure(not d.stack,'complete markup');peer,source,author=(strict(raw[FILES[i]]) for i in (5,2,3));targets=[f'v15-c12-e{i}' for i in range(1,11)];ensure(d.prompts==list(d.answers)==targets and len(d.worked)==5 and all(len(v)>400 for v in d.answers.values()),'five cases ten full answers');ensure(set(peer['exact_solution_review'])==set(targets) and not peer['open_findings'],'complete peer record');ensure(d.sources=={s['id']:s['url'] for s in source['sources']},'source routes');ensure('v15-c11.html'in d.links and 'curriculum.html#v16-c01'in d.links,'prerequisite/planned successor');ensure(set(peer['payload_bindings'])==set(FILES[:5]),'five nonself bindings')
    for f,b in peer['payload_bindings'].items():ensure(len(raw[f])==b['bytes'] and sha256(raw[f]).hexdigest()==b['sha256'],'peer frozen bytes')
    ensure(not author['open_findings'] and set(author['exact_prompt_review'])==set(targets),'author complete audit');bindings=author['payload_bindings'];ensure(len(bindings)==3 and {b['path'] for b in bindings}==set(FILES[:3]),'author three bindings')
    for b in bindings:ensure(b['bytes']==len(raw[b['path']]) and b['sha256']==sha256(raw[b['path']]).hexdigest(),'author freeze')
    x={k:parse(v[1]) for k,v in d.mark.items() if v[0]=='data-input'};count=0;rejects=0;seen=set()
    def eq(a,b):
        nonlocal count
        if isinstance(a,(tuple,list)):
            ensure(isinstance(b,(tuple,list)) and len(a)==len(b),'numeric shape')
            for c,e in zip(a,b):eq(c,e)
        else:ensure(a==b,'exact equality '+str((a,b)));count+=1
    def truth(ok,msg):
        nonlocal count
        ensure(ok,msg);count+=1
    def mark(k,v):eq(v,parse(d.mark[k][1]));seen.add(k)
    ensure(set(x)=={'benefits','taxes','transfer-cost','did','capacity','political','pilot'},'all inputs');g0=tuple(b-t for b,t in zip(x['benefits'],x['taxes']));a=x['transfer-cost'];lo,hi=pareto(g0,a);g=transfer(g0,a,lo);mark('initial-gains',g0);mark('compensation-interval',(lo,hi));mark('compensated',(*g,sum(g)));other=F(1,2);ll,hh=pareto(g0,other);gg=transfer(g0,other,ll);mark('e1',(ll,hh,*gg,sum(gg)));gg=transfer(g0,a,hi);mark('e2',(hi,*gg,gg[0]+gg[1]+2*gg[2],sum(gg)))
    for aa,w in product((F(0),F(1,5),F(1,2),F(2)),(F(0),F(1),F(6,5),F(2),F(3))):
        low,high=pareto(g0,aa);slope=w-1-aa;chosen=low if slope<=0 else high;objective=lambda z:sum(transfer(g0,aa,z)[:2])+w*transfer(g0,aa,z)[2]
        for r in (0,F(1,2),1):
            z=low*(1-r)+high*r;g=transfer(g0,aa,z);truth(min(g)>=0,'Pareto constraints');eq(sum(g),sum(g0)-aa*z);truth(objective(z)<=objective(chosen),'global weighted linear choice');truth(x['taxes'][0]+(1+aa)*z<=20,'prior resources')
        if slope==0:eq(objective(low),objective(high))
    t0,t1,c0,c1=x['did'];D=(t1-c1)-(t0-c0);eff=(D-2,D+1);trial=F(3,4);target=F(1,4);mark('effect-bounds',(*eff,*(trial*v for v in eff),*(target*v for v in eff)));pay=tuple(8*target*v-4 for v in eff);mark('target-payoff',pay);opt,L=lottery(*pay);mark('randomized-regret',(opt[0],L));eff2=(D-2,D+2);pay2=tuple(8*target*v-4 for v in eff2);opt2,L2=lottery(*pay2);mark('e3',(*pay2,opt2[0],L2));mark('e4',(8*target*eff[0],4/(8*eff[0])))
    for low,high in (pay,pay2,(1,4),(-4,-1),(0,0)):
        optimal,loss=lottery(low,high)
        for j in range(21):
            prob=F(j,20);truth(max(max(0,v)-prob*v for v in (low,high))>=loss,'global regret witnesses')
        for p in optimal:eq(max(max(0,v)-p*v for v in (low,high)),loss)
    for gamma in (F(-2),F(-1),F(0),F(1),F(2)):
        counterfactual=t0+c1-c0+gamma;tau=t1-counterfactual;eq(tau+gamma,D);eq(counterfactual+tau,t1)
    K,ag,bg,c,wx,wy=x['capacity'];A=ag-c;B=bg-c;eq((wx,wy),(2,1));X,Y,lam,slack,cost,V=capacity(K,A,B);mark('capacity-allocation',(X,Y,lam,cost,V));small=capacity(1,A,B);large=capacity(20,A,B);mark('e5',(*small[:3],small[4],small[5],*large[:2],large[3],large[4],large[5]));nxt=capacity(9,A,B);mark('e6',(nxt[5],nxt[5]-V,lam,nxt[5]-V-3,nxt[4]+3))
    for KK in (0,1,2,8,9,17,20):
        xx,yy,ll,ss,cc,vv=capacity(KK,A,B);truth(xx>=0 and yy>=0 and ss>=0,'capacity feasible');eq(ll*ss,0);truth(cc<=30,'operating appropriation');truth(A-2*xx<=2*ll and B-2*yy<=ll,'inactive margins');eq(xx*(A-2*xx-2*ll),0);eq(yy*(B-2*yy-ll),0)
        for j,k in product(range(9),repeat=2):
            u=F(j,2);v=F(k,2)
            if 2*u+v<=KK:
                candidate=A*u-u*u+B*v-v*v;truth(candidate<=vv,'candidate enumeration global witness');eq(vv-candidate,(u-xx)**2+(v-yy)**2+(A-2*xx)*(xx-u)+(B-2*yy)*(yy-v))
    for k in (F(2),F(8),F(9),F(17)):eq(capacity(k,A,B)[5],A*A/4+B*B/4-(17-k)**2/5)
    g1,g2,g3,adm,cap=x['political'];bgains=(g1,g2,g3);maj=coalition(bgains,adm,cap,'majority');veto=coalition(bgains,adm,cap,'veto');mark('majority',(*maj[2],maj[3],maj[1]));mark('veto',(*veto[2],veto[3],veto[1]));truth(coalition(bgains,adm,cap,'unanimity') is None,'unanimity budget');uni=coalition(bgains,adm,5,'unanimity');mark('e7',(*uni[0],uni[1],*uni[2],uni[3]));mark('e8',(maj[1],veto[1],maj[3],0));truth(coalition(bgains,adm,3,'veto') is None,'veto infeasible');eq(coalition(bgains,adm,3,'majority'),maj)
    for rule,M in (('majority',4),('veto',4),('unanimity',5)):
        best=coalition(bgains,adm,M,rule)
        for t2,t3 in product((F(0),F(1),F(2),F(3),F(4)),repeat=2):
            out=(1+adm)*(t2+t3);g=(g1-out,g2+t2,g3+t3);votes=[z>=0 for z in g];passes=sum(votes)>=2 and (rule!='veto' or votes[1]) and (rule!='unanimity' or all(votes))
            if passes and out<=M:truth(out>=best[1],'minimal coalition globally');truth(g[0]<=best[2][0],'sponsor global utility')
            eq(sum(g),sum(bgains)-adm*(t2+t3))
    p,ph,pl,vh,vl,pc=x['pilot'];weights,posterior,values,gross,net,gain=experiment(*x['pilot']);mark('pilot-decision',(weights[0],*posterior,*values,gross,net,gain));mark('e9',((pc+1)/7,(3-pc)/5));eq(pc+10*weights[0],F(21,4));truth(pc+10<=12,'worst branch funded');eq(p*ph*18+(1-p)*pl*6-(pc+10*weights[0]),net)
    for p0 in (0,F(1,7),F(1,4),F(1,3),F(2,5),F(9,20),F(3,5),1):
        ww,post,vv,gg,nn,delta=experiment(p0,ph,pl,vh,vl,pc);piece=0 if p0<=F(1,7) else 7*p0-1 if p0<=F(3,5) else 12*p0-4;eq(gg,piece);truth((delta>0)==(F(1,4)<p0<F(9,20)),'all strict prior regions');truth(max(0,p0*vh+(1-p0)*vl)<=gg<=p0*max(0,vh)+(1-p0)*max(0,vl),'information bounds');eq(sum(ww),1)
        for a1,a0 in product((0,1),repeat=2):truth(a1*ww[0]*vv[0]+a0*ww[1]*vv[1]<=gg,'all contingent actions')
    alpha=F(1,20);spent=sum(alpha/F(t*(t+1)) for t in range(1,6));mark('e10',(spent,alpha,1-(1-alpha)**5))
    for T in (1,2,5,10,100):eq(sum(alpha/F(t*(t+1)) for t in range(1,T+1)),alpha*(1-F(1,T+1)))
    invalid=(lambda:real(True),lambda:real(float('nan')),lambda:real(float('inf')),lambda:transfer((1,2),0,1),lambda:transfer((1,2,3),-1,0),lambda:transfer((1,2,3),0,-1),lambda:pareto((1,-1,0),0),lambda:pareto((1,1,-3),0),lambda:lottery(1,-1),lambda:capacity(-1),lambda:capacity(1,-1,1),lambda:coalition((8,-3,-1),0,-1,'majority'),lambda:coalition((8,-3,-1),0,1,'invalid'),lambda:experiment(-1,ph,pl,vh,vl,pc),lambda:experiment(2,ph,pl,vh,vl,pc),lambda:experiment(p,0,pl,vh,vl,pc),lambda:experiment(p,ph,pl,vh,vl,-1),lambda:parse('2**3'),lambda:parse('1/0'),lambda:strict('{"a":1,"a":2}'),lambda:strict('{"a":Infinity}'))
    for f in invalid:
        try:f()
        except (ValueError,TypeError,ZeroDivisionError):rejects+=1
        else:raise ValueError('invalid primitive accepted')
    ensure(seen=={k for k,v in d.mark.items() if v[0]=='data-result'},'all results covered');ensure(raw=={f:(base/f).read_bytes() for f in FILES},'runtime unchanged');result=dict(chapter='v15-c12',status='passed',worked_cases=5,solutions=10,inputs=len(x),results=len(seen),comparisons=count,domain_rejections=rejects,runtime_files=6);json.dumps(result,allow_nan=False);return result
if __name__=='__main__':check()
