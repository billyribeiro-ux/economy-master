"""Original V15 construction assessment: exact four-file author oracle."""
from pathlib import Path
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from itertools import product
from math import isfinite
import ast,json
FILES=('content/assessments/parts/v15-exam-a.html','scripts/check_v15_exam_a.py','content/reviews/v15-exam-a-sources.json','content/reviews/v15-exam-a-author.json')
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
def labor(w,t):
    w,t=map(real,(w,t));ensure(w>0 and 0<=t<=1,'labor domain');n=w*(1-t);return n,t*w*n,w*n-n*n/2

def vertical(z,a=0):
    z,a=map(real,(z,a));ensure(z>=0 and 0<=a<=1,'trade domain')
    if z>=8:return (F(0),)*7
    q=(8-z)/4;v=6-z/2;p=10-q;ret=q*q;foreign=2*q*q;H=q*q/2+ret+z*q+a*foreign;world=8*q-q*q/2;return q,v,p,ret,foreign,H,world

def optimal_tariff(a):
    a=real(a);ensure(0<=a<=1,'ownership fraction');return max(F(0),8-32/(5-4*a))
def archives(N,n,mean,lo,hi):
    ensure(type(N)is int and type(n)is int and 0<=n<=N and N>0,'archive counts');mean,lo,hi=map(real,(mean,lo,hi));ensure(lo<=hi,'support order');return ((n*mean+(N-n)*lo)/N,(n*mean+(N-n)*hi)/N)
def politics(q,f,b):
    q,f,b=map(real,(q,f,b));ensure(0<=q<=1 and 0<=f<=2 and 0<=b<=2,'contract bounds');act=q*(f+b)>=1;tax=(6*q+q*b)/3;vA=F(1,4)*(5+q*b)-tax if act else -F(1,4)*q*f-tax;vB=2-tax if act else -tax;vC=-tax;gain=9-6*q if act else -6*q;return act,tax,vA,vB,vC,gain

def spatial(n,k,theta=1,admin=0):
    n,k,theta,admin=map(real,(n,k,theta,admin));ensure(0<=k<=n<=6 and theta>=0 and admin>=0,'spatial domain');output=12*n+10*(6-n);housing=(n*n+(6-n)**2)/2;health=k*k/2;damage=theta*(n-k)**2/2;return output-housing-health-damage-admin
class Read(HTMLParser):
    def __init__(self):super().__init__();self.stack=[];self.ids=set();self.mark={};self.prompts={};self.answers={};self.rubrics={};self.sources={};self.links=[];self.domains={};self.coverage=set()
    def handle_starttag(self,t,attrs):
        a=dict(attrs);ensure(len(a)==len(attrs),'unique attributes')
        if 'id'in a:ensure(a['id'] not in self.ids and (a['id'].startswith('v15-exam-a-') or a['id'] in ('form-a','solutions-a')),'scoped unique ID');self.ids.add(a['id'])
        if t=='h1':raise ValueError('no h1')
        if 'href'in a:self.links.append(a['href'])
        if 'data-points'in a:
            ensure(t=='li','scored prompt');self.prompts[a['id']]=int(a['data-points']);self.coverage.update(a['data-chapters'].split())
        if 'data-domain'in a:ensure(a['data-domain'] not in self.domains,'unique domain');self.domains[a['data-domain']]=[int(a['data-domain-points']),[]]
        if 'data-points'in a:
            dom=next(d['data-domain'] for tag,d in reversed(self.stack) if 'data-domain'in d);self.domains[dom][1].append(a['id'])
        if 'data-solution-for'in a:
            k=a['data-solution-for'];ensure(k not in self.answers and any(tag=='details' and 'solutions'in d.get('class','').split() for tag,d in self.stack),'disclosed unique answer');self.answers[k]=''
        if 'data-rubric-points'in a:
            k=next(d['data-solution-for'] for tag,d in reversed(self.stack) if 'data-solution-for'in d);ensure(k not in self.rubrics,'one rubric');self.rubrics[k]=tuple(int(v) for v in a['data-rubric-points'].split(','))
        for attr in ('data-input','data-result'):
            if attr in a:ensure(a[attr] not in self.mark,'unique marker');self.mark[a[attr]]=[attr,'']
        if 'data-source'in a:ensure(a['data-source'] not in self.sources,'unique source');self.sources[a['data-source']]=a['href']
        if t not in ('br','hr','img','input','meta','link'):self.stack.append((t,a))
    def handle_data(self,s):
        for t,a in self.stack:
            if 'data-solution-for'in a:self.answers[a['data-solution-for']]+=s
            for attr in ('data-input','data-result'):
                if attr in a:self.mark[a[attr]][1]+=s
    def handle_endtag(self,t):ensure(self.stack and self.stack[-1][0]==t,'balanced markup');self.stack.pop()
def check(root=None):
    base=Path(root) if root is not None else Path(__file__).resolve().parents[1];raw={f:(base/f).read_bytes() for f in FILES};d=Read();d.feed(raw[FILES[0]].decode());d.close();ensure(not d.stack,'complete markup');source=strict(raw[FILES[2]]);record=strict(raw[FILES[3]]);targets=[f'v15-exam-a-q{i:02}' for i in range(1,21)];ensure(list(d.prompts)==list(d.answers)==targets and set(d.rubrics)==set(targets),'twenty exact pairs');ensure(all(d.prompts[k]==sum(d.rubrics[k])==5 and min(d.rubrics[k])>0 and len(d.answers[k])>500 for k in targets),'complete additive solutions');ensure(sum(d.prompts.values())==100 and len(d.domains)==5 and all(n==20 and len(ids)==4 and sum(d.prompts[k] for k in ids)==20 for n,ids in d.domains.values()),'five twenty-point domains');ensure(d.coverage=={f'v15-c{i:02}' for i in range(1,13)} and all(f'v15-c{i:02}.html'in d.links for i in range(1,13)),'all twelve chapter routes');ensure(d.sources=={r['id']:r['url'] for r in source['sources']},'source routes');ensure(set(record['exact_prompt_review'])==set(targets) and not record['open_findings'],'full author review');ensure(set(record['payload_bindings'])==set(FILES[:3]),'three nonself bindings')
    for f,b in record['payload_bindings'].items():ensure(len(raw[f])==b['bytes'] and sha256(raw[f]).hexdigest()==b['sha256'],'author freeze')
    x={k:parse(v[1]) for k,v in d.mark.items() if v[0]=='data-input'};n=0;rejects=0;seen=set()
    def eq(a,b):
        nonlocal n
        if isinstance(a,(tuple,list)):
            ensure(isinstance(b,(tuple,list)) and len(a)==len(b),'numeric shape')
            for c,e in zip(a,b):eq(c,e)
        else:ensure(a==b,'exact equality '+str((a,b)));n+=1
    def mark(k,v):eq(v,parse(d.mark[k][1]));seen.add(k)
    def truth(a,m):
        nonlocal n
        ensure(a,m);n+=1
    ensure(set(x)=={'labor','vertical','grid','archive','politics','spatial'},'all inputs read');w,G,B,cost,wnew=x['labor'];eq((w,G,B,cost,wnew),(4,3,5,2,5));roots=(F(1,4),F(3,4));lo,hi=[labor(w,t) for t in roots];mark('q01',(roots[0],lo[0],roots[1],hi[0]));laborbase=labor(w,0)[2];mark('q02',(laborbase,lo[2]-G+B,hi[2]-G+B,laborbase-G+B));new=labor(wnew,roots[0]);gross=((wnew*(1-roots[0]))**2-(w*(1-roots[0]))**2)/2;private=gross-cost;extra=new[1]-lo[1];total=new[2]-cost-lo[2];mark('q03',(new[0],private,extra,total));grant=cost-F(1,2)-1;mark('q04',(grant,private+grant,extra-grant,total));eq(private+extra,total)
    for wage,t in product((F(1),F(4),F(5)),(0,F(1,4),F(1,2),F(3,4),1)):
        opt,rev,W=labor(wage,t)
        for alternative in (0,1,2,3,4,5):
            value=(1-t)*wage*alternative-F(alternative*alternative,2);eq(opt*opt/2-value,(real(alternative)-opt)**2/2);truth(value<=opt*opt/2,'global labor square')
        eq(rev,t*wage*opt)
    eq(x['vertical'],(10,2));r=vertical(0);q,v,p,ret,foreign,H,world=r;mark('q05',(v,q,p,ret,foreign,0));z=optimal_tariff(0);r1=vertical(z);q,v,p,ret,foreign,H,world=r1;mark('q06',(z,q,H,H-r[5],world,r[6]-world));qint=F(8,2);fee=qint*qint;mark('q07',(2,fee,qint,10-qint,qint*qint/2,fee,8*qint-qint*qint/2));mark('q08',tuple(optimal_tariff(a) for a in (0,F(1,8),F(1,4),1)))
    for a in (0,F(1,8),F(1,4),F(1,2),1):
        optimum=vertical(optimal_tariff(a),a)[5]
        for j in range(41):
            tariff=F(j,4);q,v,p,ret,foreign,H,world=vertical(tariff,a);truth(H<=optimum,'national global policy witness')
            if tariff<8:eq(H,8*q-(F(5,2)-2*a)*q*q);eq(world,q*q/2+ret+foreign+tariff*q);eq(p*q,v*q+tariff*q+ret)
    N,wealth,banks,treasury,K,grid,y,y0,pledge=x['grid'];needloan=K-wealth;aftertax=y-2;enforced=pledge*aftertax;public=needloan-enforced;mark('q09',(pledge*y0,pledge*y,needloan,K,K-pledge*y));entrepreneur=aftertax-enforced;bankfinal=N*(enforced+public);govfinal=N*2+(treasury-grid)-N*public;totalfinal=N*entrepreneur+bankfinal+govfinal;mark('q10',(public,entrepreneur,bankfinal,govfinal,totalfinal));egain=N*(entrepreneur-wealth);ggain=govfinal-treasury;mark('q11',(egain,bankfinal-banks,ggain,totalfinal-(N*wealth+banks+treasury),-egain/ggain));eq(N*K+grid+(treasury-grid),N*wealth+banks+treasury);eq(totalfinal,N*y+treasury-grid)
    NT,nt,mt,NC,nc,mc,lower,upper=x['archive'];T=archives(int(NT),int(nt),mt,lower,upper);C=archives(int(NC),int(nc),mc,lower,upper);mark('q12',(*T,*C,T[0]-C[1],T[1]-C[0]));
    for j in range(11):
        mix=F(j,10);t=(nt*mt+(NT-nt)*(lower*(1-mix)+upper*mix))/NT;c=(nc*mc+(NC-nc)*(upper*(1-mix)+lower*mix))/NC;eq(t-c,(1-mix)*(T[0]-C[1])+mix*(T[1]-C[0]))
    betaA,betaB,effort,own,spill,maxf,maxb,slope=x['politics'];eq(x['politics'],(F(1,4),F(1,2),3,8,4,2,2,6));need=effort-betaA*own;mark('q13',(betaA*own-effort,betaB*own-effort,need,betaA*(own-effort)));r=politics(F(1,2),maxf,0);mark('q14',r[1:]);r=politics(F(1,4),maxf,maxb);mark('q15',(F(1,4),maxf,maxb,F(1,4)*maxb,*r[1:]));mark('q16',(betaA*(own-effort),own-9,own-9,own-9+1));truth(r[2]>=0 and r[3]>=0 and r[4]<0,'majority')
    for q,f,b in product((0,F(1,8),F(1,4),F(3,8),F(1,2),1),(0,1,2),(0,1,2)):
        act,tax,a,bb,cc,gain=politics(q,f,b)
        if act:truth(q>=F(1,4),'audit lower bound');truth(gain<=F(15,2),'global resource optimum');eq(3*tax,6*q+q*b)
    eq(x['spatial'],(6,12,10,1,1,1));nstar=F(16,5);kstar=nstar/2;baseline=spatial(4,0);W=spatial(nstar,kstar);mark('q17',(4,baseline,nstar,kstar,W,W-baseline));tau=nstar-kstar;receipts=tau*nstar;bill=kstar*kstar/2;rebate=(receipts-bill)/6;owner=(nstar*nstar+(6-nstar)**2)/2;workers=6*(10-(6-nstar)+rebate)-(nstar-kstar)**2/2;mark('q18',(tau,receipts,bill,rebate,workers,owner,workers+owner));eq(workers+owner,W);capW=spatial(3,1);mark('q19',(3,1,capW,2,6,F(11,12),W-capW,W-capW-F(2,5)));ends=tuple(spatial(3,1,t,1)-spatial(4,0,t) for t in (F(1,2),F(3,2)));mark('q20',(*ends,F(9,2),F(3,4),F(1,40)))
    for j in range(25):
        loc=F(j,4)
        for k in (F(0),loc/2,loc):
            dloc=loc-nstar;dk=k-kstar;eq(W-spatial(loc,k),F(5,4)*dloc*dloc+(dk-dloc/2)**2);truth(spatial(loc,k)<=W,'joint global certificate')
            if k<=1:truth(spatial(loc,k)<=capW,'capacity global witness')
    for th in (F(1,2),1,F(3,2)):eq(spatial(3,1,th,1)-spatial(4,0,th),F(-5,2)+6*th)
    invalid=(lambda:real(True),lambda:real(float('nan')),lambda:real(float('inf')),lambda:labor(0,0),lambda:labor(4,-1),lambda:labor(4,2),lambda:vertical(-1),lambda:vertical(0,2),lambda:optimal_tariff(-1),lambda:archives(1,2,0,0,1),lambda:archives(0,0,0,0,1),lambda:archives(1,0,0,1,0),lambda:politics(-1,0,0),lambda:politics(1,3,0),lambda:politics(1,0,3),lambda:spatial(7,0),lambda:spatial(1,2),lambda:spatial(1,0,-1),lambda:spatial(1,0,1,-1),lambda:parse('1+2'),lambda:strict('{"x":1,"x":2}'),lambda:strict('{"x":NaN}'))
    for f in invalid:
        try:f()
        except (ValueError,TypeError,ZeroDivisionError):rejects+=1
        else:raise ValueError('invalid accepted')
    ensure(seen=={k for k,v in d.mark.items() if v[0]=='data-result'},'all results covered');ensure(raw=={f:(base/f).read_bytes() for f in FILES},'runtime unchanged');result=dict(volume='v15',component='exam_a',status='passed',points=100,domains=5,solved_subparts=20,chapter_routes=12,input_groups=len(x),result_groups=len(seen),comparisons=n,domain_rejections=rejects,runtime_files=4);json.dumps(result,allow_nan=False);return result
if __name__=='__main__':check()
