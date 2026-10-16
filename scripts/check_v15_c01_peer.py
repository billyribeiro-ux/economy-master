"""Independent public-economics audit; no author code is executed or imported."""
from pathlib import Path
from fractions import Fraction as Q
from hashlib import sha256
from html.parser import HTMLParser
from math import log,exp,isfinite
import ast,json,re
FILES=('content/chapters/v15-c01.html','scripts/check_v15_c01.py','content/reviews/v15-c01-sources.json','content/reviews/v15-c01-author.json','scripts/check_v15_c01_peer.py','content/reviews/v15-c01-peer.json')
def require(ok,label):
    if not ok:raise ValueError(label)
def real(x):
    require(type(x) in (int,float,Q) and isfinite(x),'finite real');return Q(str(x)) if type(x)==float else Q(x)
def probability(p):
    require(isinstance(p,(tuple,list)) and len(p)>0,'probability vector');p=tuple(map(real,p));require(min(p)>=0 and sum(p)==1,'unit probabilities');return p
def literal(text):
    def visit(n):
        if isinstance(n,ast.Constant):return real(n.value)
        if isinstance(n,(ast.Tuple,ast.List)):return tuple(visit(e) for e in n.elts)
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,(ast.USub,ast.UAdd)):return visit(n.operand)*(-1 if isinstance(n.op,ast.USub) else 1)
        if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Div):return visit(n.left)/visit(n.right)
        raise ValueError('numeric expression')
    return visit(ast.parse(text.replace('−','-').split('=',1)[-1].strip(),mode='eval').body)
def strict(raw):
    def pairs(items):
        out={}
        for k,v in items:require(k not in out,'duplicate key');out[k]=v
        return out
    def invalid(x):raise ValueError('nonfinite JSON')
    out=json.loads(raw,object_pairs_hook=pairs,parse_constant=invalid);json.dumps(out,allow_nan=False);return out
def incidence(intercept,demand,supply,tax):
    a,b,c,t=map(real,(intercept,demand,supply,tax));require(a>0 and b>0 and c>0 and 0<=t<=a/b,'positive trade incidence domain');q=(a-b*t)/(1+b/c);pp=q/c;pc=(a-q)/b;revenue=t*q;q0=a/(1+b/c);dwl=(q0-q)**2*(1/b+1/c)/2;return pp,pc,q,revenue,dwl

def tax_welfare(tau,masses,ability,weights):
    mu=probability(masses);tau=real(tau);require(0<=tau<=1 and len(mu)==len(ability)==len(weights),'tax dimensions/domain');a=tuple(map(real,ability));g=tuple(map(real,weights));require(min(a)>0 and min(g)>=0 and sum(p*w for p,w in zip(mu,g))==1,'normalized welfare weights');labor=tuple((1-tau)*x for x in a);earn=tuple(x*l for x,l in zip(a,labor));B=tau*sum(p*z for p,z in zip(mu,earn));cons=tuple((1-tau)*z+B for z in earn);utility=tuple(c-l*l/2 for c,l in zip(cons,labor));return B,sum(p*w*u for p,w,u in zip(mu,g,utility)),labor,earn,cons,utility

def menu(abilities,earnings):
    require(len(abilities)==len(earnings)==2,'menu shape');a,b=map(real,abilities);z,Z=map(real,earnings);require(0<a<b and 0<=z<=Z,'ordered types and outputs');low=(Z*Z-z*z)/(2*b*b);high=(Z*Z-z*z)/(2*a*a);c=(z+Z-low)/2;C=(z+Z+low)/2;return low,high,c,C,c-z*z/(2*a*a),C-Z*Z/(2*b*b)

def insured(wealth,loss,premium,benefit):
    w,L,pr,b=map(real,(wealth,loss,premium,benefit));require(w>L>0 and pr>=0 and 0<=b<=L,'insurance contract');cg=w-pr;cb=w-L-pr+b;require(min(cg,cb)>0,'positive insured consumption');return cg,cb

def effort_benefit(w,L,p0,p1,cost):
    w,L,p0,p1=map(real,(w,L,p0,p1));require(w>L>0 and 0<p1<p0<1 and real(cost)>=0,'effort primitives');k=float(cost);gap=float(p0-p1)
    def advantage(b):
        cg,cb=insured(w,L,p1*real(b),real(b));return gap*log(float(cg/cb))-k
    require(advantage(0)>=-1e-12,'effort feasible')
    if advantage(L)>=-1e-12:return float(L)
    lo,hi=0.,float(L)
    for _ in range(80):
        mid=(lo+hi)/2
        if advantage(mid)>=0:lo=mid
        else:hi=mid
    return (lo+hi)/2
class Manuscript(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.stack=[];self.ids=set();self.cases=[];self.exercises=[];self.answers={};self.mark={};self.urls={}
    def handle_starttag(self,t,attrs):
        a=dict(attrs);require(len(a)==len(attrs),'duplicate attribute')
        if 'id' in a:
            require(a['id'] not in self.ids,'duplicate ID');self.ids.add(a['id'])
            if 'worked' in a.get('class','').split():self.cases.append(a['id'])
            if re.fullmatch('v15-c01-e[0-9]+',a['id']):self.exercises.append(a['id'])
        if 'data-solution-for' in a:
            key=a['data-solution-for'];require(key not in self.answers and any(tag=='details' and 'solutions' in d.get('class','').split() for tag,d in self.stack),'paired disclosed solution');self.answers[key]=''
        for attr in ('data-input','data-result'):
            if attr in a:require(a[attr] not in self.mark,'duplicate marker');self.mark[a[attr]]=[attr,'']
        if 'data-source' in a:require(a['data-source'] not in self.urls,'duplicate source');self.urls[a['data-source']]=a['href']
        if t not in ('br','hr','img','meta','link','input'):self.stack.append((t,a))
    def handle_data(self,s):
        for tag,a in self.stack:
            if 'data-solution-for' in a:self.answers[a['data-solution-for']]+=s
            for attr in ('data-input','data-result'):
                if attr in a:self.mark[a[attr]][1]+=s
    def handle_endtag(self,t):require(self.stack and self.stack[-1][0]==t,'balanced HTML');self.stack.pop()
def check(root=None):
    base=Path(root) if root is not None else Path(__file__).resolve().parents[1];raw={p:(base/p).read_bytes() for p in FILES};doc=Manuscript();doc.feed(raw[FILES[0]].decode());doc.close();require(not doc.stack,'closed HTML');author=strict(raw[FILES[3]]);source=strict(raw[FILES[2]]);peer=strict(raw[FILES[5]]);targets=[f'v15-c01-e{i}' for i in range(1,13)];require(doc.cases==[f'v15-c01-case{i}' for i in range(1,7)] and doc.exercises==list(doc.answers)==targets,'six cases/twelve exact solutions');require(all(len(x)>250 for x in doc.answers.values()),'substantive solutions');require(doc.urls=={x['id']:x['url'] for x in source['sources']},'source URLs');require(set(peer['exact_prompt_review'])==set(targets),'full peer proof record');require(author['open_findings']==peer['open_findings']==[],'open findings')
    for record,paths in ((author,set(FILES[:3])),(peer,set(FILES[:5]))):
        bs=record['payload_bindings'];require(len(bs)==len(paths) and {x['path'] for x in bs}==paths,'nonself bindings')
        for b in bs:require(len(raw[b['path']])==b['bytes'] and sha256(raw[b['path']]).hexdigest()==b['sha256'],'payload freeze')
    count=0;rejects=0;seen=set()
    def near(a,b):
        nonlocal count
        if isinstance(b,(tuple,list)):
            require(isinstance(a,(tuple,list)) and len(a)==len(b),'shape')
            for x,y in zip(a,b):near(x,y)
        else:require(isfinite(float(a)) and abs(float(a)-float(b))<2e-9*max(1,abs(float(b))),str((a,b)));count+=1
    def test(ok,label):
        nonlocal count
        require(ok,label);count+=1
    def mark(k,value):near(literal(doc.mark[k][1]),value);seen.add(k)
    inputs={k:literal(v[1]) for k,v in doc.mark.items() if v[0]=='data-input'}
    expected={'incidence':'(120,2,3,10)','linear-tax':'(1/2,1/2,1,3,3/2,1/2)','menu-abilities':'(1,2)','menu-earnings':'(1,2)','public-values':'(2,1,1)','insurance':'(10,6,1/2,1/4)','tax-evidence':'(100,90,80,84,1/5,3/10)'}
    require(set(inputs)==set(expected),'primitive inventory')
    for k,v in expected.items():mark(k,literal(v))
    a,b,c,t=inputs['incidence'];basecase=incidence(a,b,c,0);case=incidence(a,b,c,t);mark('incidence-result',case[:4]);mark('incidence-dwl',case[4]);mark('e1',incidence(a,b,c,5))
    for tt in (0,5,10,20,60):
        pp,pc,q,rev,dwl=incidence(a,b,c,tt);near(pc-pp,tt);cs=(a/b-pc)*q/2;ps=pp*q/2;cs0=(a/b-basecase[1])*basecase[2]/2;ps0=basecase[0]*basecase[2]/2;near(cs0+ps0-cs-ps,rev+dwl)
    for primitives in ((90,3,2,4),(40,1,4,2)):
        aa,bb,cc,tt=map(Q,primitives);h=Q(1,10000);low=incidence(aa,bb,cc,tt);high=incidence(aa,bb,cc,tt+h);near((high[1]-low[1])/h,cc/(bb+cc));near((high[0]-low[0])/h,-bb/(bb+cc))
    mu=inputs['linear-tax'][:2];ability=inputs['linear-tax'][2:4];weights=inputs['linear-tax'][4:];A=sum(p*x*x for p,x in zip(mu,ability));H=sum(p*g*x*x for p,g,x in zip(mu,weights,ability));tau=(A-H)/(2*A-H);calc=tax_welfare(tau,mu,ability,weights);mark('linear-optimum',(tau,calc[0]));mark('linear-welfare',calc[1]);near(sum(p*x for p,x in zip(mu,calc[3])),sum(p*x for p,x in zip(mu,calc[4])))
    for gg in (weights,(Q(7,4),Q(1,4)),(Q(1),Q(1)),(Q(0),Q(2))):
        HH=sum(p*g*x*x for p,g,x in zip(mu,gg,ability));opt=max(Q(0),(A-HH)/(2*A-HH)) if HH<A else Q(0);best=tax_welfare(opt,mu,ability,gg)
        for i in range(21):test(tax_welfare(Q(i,20),mu,ability,gg)[1]<=best[1],'global tax witness')
        if gg==(Q(7,4),Q(1,4)):mark('e3',(opt,best[0],best[1]))
    aa=inputs['menu-abilities'];zz=inputs['menu-earnings'];m=menu(aa,zz);mark('menu-consumption',m[2:4]);changed=menu(aa,(1,3));mark('e4',changed[2:])
    for targets in (zz,(1,3),(0,2)):
        lo,hi,cl,ch,ul,uh=menu(aa,targets);near(cl+ch,sum(targets));test(ul>=ch-targets[1]**2/(2*aa[0]**2),'low IC');near(uh,cl-targets[0]**2/(2*aa[1]**2));test(lo<=hi,'IC interval')
    v1,v2,cost=inputs['public-values'];nash=max(0,v1/cost-1);planner=max(0,(v1+v2)/cost-1);mark('public-private',(nash,0,nash));mark('public-optimum',planner);bills=(Q(17,10),Q(3,10));gain=(float(nash-bills[0])+float(v1)*log(float((1+planner)/(1+nash))),-float(bills[1])+float(v2)*log(float((1+planner)/(1+nash))));mark('public-gains',gain);near(sum(bills),cost*planner);test(min(gain)>0,'funded Pareto bills');mark('e5',(max(0,v1/2-1),max(0,(v1+v2)/2-1),2*max(0,(v1+v2)/2-1)))
    sigma=1-v1/(1+planner);tax=sigma*planner/2;payment=((1-sigma)*planner+tax,tax);mark('e6-payments',payment);mark('e6-gains',(float(nash-payment[0])+float(v1)*log(float((1+planner)/(1+nash))),-float(payment[1])+float(v2)*log(float((1+planner)/(1+nash)))));near(sum(payment),planner)
    q0=(100-20)/4;q1=(100-20-10)/4;p0=100-2*q0;p1=100-2*q1;mark('e2',(q0,p0,q1,p1,(p1-p0)/10));integral=lambda q:80*q-q*q;mark('e2-surplus-loss',integral(q0)-integral(q1))
    w,L,p0,p1=inputs['insurance'];k=log(1.5)/4;benefit=effort_benefit(w,L,p0,p1,k);premium=float(p1)*benefit;cg,cb=insured(w,L,premium,benefit);value=(1-float(p1))*log(float(cg))+float(p1)*log(float(cb))-k;baseline=log(float(w-p0*L));mark('insurance-effort',(benefit,premium,cg,cb));mark('insurance-gain',value-baseline)
    for cost,ratio in ((0,1),(k,1.5),(log(2)/4,2)):
        bb=effort_benefit(w,L,p0,p1,cost);cg,cb=insured(w,L,float(p1)*bb,bb);near(float(cg/cb),ratio);val=(1-float(p1))*log(float(cg))+float(p1)*log(float(cb))-cost;near((1-float(p1))*float(cg)+float(p1)*float(cb),w-p1*L)
        for frac in (0,.25,.5,.75,1):
            btrial=bb*frac;g,bad=insured(w,L,float(p1)*btrial,btrial);u=(1-float(p1))*log(float(g))+float(p1)*log(float(bad))-cost;test(u<=val+1e-12,'best effort contract witness');test(float(p0-p1)*log(float(g/bad))>=cost-1e-12,'fixed premium effort IC')
        if ratio==2:mark('e8-effort',(bb,float(p1)*bb,cg,cb));test(val<baseline,'higher cost full insurance beats effort')
    mark('e7',(w-p1*L,w-p0*L))
    tp,tpost,cp,cpost,old,new=inputs['tax-evidence'];cf=tp+cpost-cp;effect=tpost-cf;elasticity=log(float(tpost/cf))/log(float((1-new)/(1-old)));mark('tax-elasticity',elasticity);net=new*tpost-old*cf;mark('tax-revenue-change',net);near(net,(new-old)*cf+new*effect);mark('e9',tuple(new*(cf+x)-old*cf for x in (-20,-8)));mark('e11-welfare',Q(3,2)*10-Q(1,2)*12)
    require(seen==set(doc.mark),'all displayed inputs/results checked')
    malformed=[(real,(True,)),(real,(float('nan'),)),(probability,((Q(1,4),Q(1,4)),)),(probability,((-1,2),)),(literal,('f(1)',)),(literal,('True',)),(literal,('1/0',)),(strict,('{"x":1,"x":2}',)),(strict,('{"x":NaN}',)),(incidence,(120,0,3,1)),(incidence,(120,2,3,-1)),(incidence,(120,2,3,61)),(tax_welfare,(Q(1,2),(Q(1,2),Q(1,2)),(1,3),(1,2))),(tax_welfare,(2,(1,),(1,),(1,))),(menu,((2,1),(1,2))),(menu,((1,2),(2,1))),(insured,(10,6,10,1)),(insured,(5,6,0,0)),(effort_benefit,(10,6,Q(1,4),Q(1,2),0)),(effort_benefit,(10,6,Q(1,2),Q(1,4),10))]
    for f,args in malformed:
        try:f(*args)
        except (ValueError,ZeroDivisionError):rejects+=1
        else:raise ValueError('malformed domain accepted '+f.__name__)
    require({p:(base/p).read_bytes() for p in FILES}==raw,'runtime unchanged');summary=dict(chapter='v15-c01',review='separate_peer',status='passed',comparisons=count,domain_rejections=rejects,worked_cases=6,exercises=12,solutions=12,input_markers=len(inputs),result_markers=len(doc.mark)-len(inputs),runtime_files=6);json.dumps(summary,allow_nan=False);return summary
if __name__=='__main__':check()
