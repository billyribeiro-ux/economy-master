"""Development chapter author check: four-file portable pure read API."""
from pathlib import Path
from fractions import Fraction as Q
from hashlib import sha256
from html.parser import HTMLParser
from itertools import product,combinations
from math import sqrt,isfinite
import ast,json
FILES=('production/v15-c04-working.html','production/check_v15_c04_working.py','production/v15-c04-sources-working.json','production/v15-c04-author-review-working.json')
def need(ok,msg):
    if not ok:raise ValueError(msg)
def real(x):need(type(x) in (int,float,Q) and isfinite(x),'finite real');return Q(str(x))
def literal(s):
    def go(n):
        if isinstance(n,ast.Constant):return real(n.value)
        if isinstance(n,(ast.Tuple,ast.List)):return tuple(go(z) for z in n.elts)
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,ast.USub):return -go(n.operand)
        if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Div):return go(n.left)/go(n.right)
        raise ValueError('literal grammar')
    return go(ast.parse(s.split('=',1)[-1].strip(),mode='eval').body)
def strict(raw):
    def pairs(items):
        out={}
        for k,v in items:need(k not in out,'duplicate JSON');out[k]=v
        return out
    def bad(x):raise ValueError('nonfinite JSON')
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=bad)
def poverty(y,z,weights=None):
    need(len(y)>0,'nonempty population');y=tuple(map(real,y));z=real(z);need(z>0 and min(y)>=0,'poverty domain');w=tuple([Q(1,len(y))]*len(y) if weights is None else map(real,weights));need(len(w)==len(y) and min(w)>=0 and sum(w)==1,'population weights');g=[max(1-v/z,0) for v in y];return (sum(t*(v<z) for t,v in zip(w,y)),sum(t*v for t,v in zip(w,g)),sum(t*v*v for t,v in zip(w,g)))
def credit(A,F,R,w,cap):
    A,F,R,w,cap=map(real,(A,F,R,w,cap));need(A>0 and F>0 and R>0 and w>=0 and cap>=0,'project domain');K=w+cap-F
    if K<=0:return (0.,0.,0.,float(R*w))
    k=min(K,(A/(2*R))**2);out=float(A)*sqrt(k);profit=out-float(R*(F+k))
    if profit<=1e-13:return (0.,0.,0.,float(R*w))
    return float(k),profit,out,float(R*w)+profit

def bundles(a,b,c,ce,ch,w,eta=0):
    a,b,c,ce,ch,w,eta=map(real,(a,b,c,ce,ch,w,eta));need(min(a,b,c,w,eta)>=0 and min(ce,ch)>0,'capability domain');options=((0,0),(1,0),(0,1),(1,1));net=[a*e+b*h+c*e*h-ce*e-ch*h for e,h in options];feasible=[i for i,(e,h) in enumerate(options) if ce*e+ch*h<=w];best=max(net[i] for i in feasible);return tuple(net),tuple(net[i]+eta*options[i][1] for i in range(4)),tuple(options[i] for i in feasible if net[i]==best)
def equilibrium(theta,bar,A,B):
    theta,bar,A,B=map(real,(theta,bar,A,B));need(0<theta<1 and bar>=0 and A>bar and B>0,'interior two-sector domain');p=B/A;la=theta+(1-theta)*bar/A;return p,la,A*la,B*(1-la)
def bounds(response,observed,low,high,control):
    r,m,L,U,c=map(real,(response,observed,low,high,control));need(0<r<=1 and L<=m<=U and L<=c<=U,'observed support');return (r*m+(1-r)*L-c,r*m+(1-r)*U-c)
class Document(HTMLParser):
    def __init__(self):super().__init__();self.stack=[];self.ids=set();self.mark={};self.sources={};self.prompts=[];self.answers={};self.worked=[];self.h1=0
    def handle_starttag(self,t,attrs):
        a=dict(attrs);need(len(a)==len(attrs),'attributes unique')
        if 'id' in a:need(a['id'] not in self.ids and a['id'].startswith('v15-c04-'),'scoped IDs');self.ids.add(a['id'])
        if t=='h1':self.h1+=1
        if 'worked' in a.get('class','').split():self.worked.append(a['id'])
        if t=='li' and any('exercises' in v.get('class','').split() for k,v in self.stack):self.prompts.append(a['id'])
        if 'data-solution-for' in a:
            k=a['data-solution-for'];need(k not in self.answers and any(t=='details' and 'solutions' in d.get('class','').split() for t,d in self.stack),'unique disclosed answer');self.answers[k]=''
        for kind in ('data-input','data-result'):
            if kind in a:need(a[kind] not in self.mark,'unique numerical marker');self.mark[a[kind]]=[kind,'']
        if 'data-source' in a:need(a['data-source'] not in self.sources,'unique source');self.sources[a['data-source']]=a['href']
        if t not in ('br','hr','img','input','meta','link'):self.stack.append((t,a))
    def handle_data(self,s):
        for t,a in self.stack:
            if 'data-solution-for' in a:self.answers[a['data-solution-for']]+=s
            for kind in ('data-input','data-result'):
                if kind in a:self.mark[a[kind]][1]+=s
    def handle_endtag(self,t):need(self.stack and self.stack[-1][0]==t,'balanced HTML');self.stack.pop()
def check(root=None):
    base=Path(root) if root is not None else Path(__file__).resolve().parents[1];raw={f:(base/f).read_bytes() for f in FILES};d=Document();d.feed(raw[FILES[0]].decode());d.close();need(not d.stack and d.h1==1,'complete chapter');targets=[f'v15-c04-ex{i}' for i in range(1,11)];need(d.prompts==list(d.answers)==targets and len(d.worked)==5,'five cases ten matched solutions');need(all(len(v)>450 for v in d.answers.values()),'substantive solutions');sources=strict(raw[FILES[2]]);author=strict(raw[FILES[3]]);need(d.sources=={x['id']:x['url'] for x in sources['sources']},'exact source links');need(set(author['exact_solution_review'])==set(targets) and not author['open_findings'],'complete author review');need(set(author['payload_bindings'])==set(FILES[:3]),'nonself bindings')
    for f,b in author['payload_bindings'].items():need(len(raw[f])==b['bytes'] and sha256(raw[f]).hexdigest()==b['sha256'],'frozen bytes')
    x={k:literal(v[1]) for k,v in d.mark.items() if v[0]=='data-input'};seen=set();count=0;rejects=0
    def eq(a,b):
        nonlocal count
        if isinstance(a,(tuple,list)):
            need(isinstance(b,(tuple,list)) and len(a)==len(b),'shape')
            for v,w in zip(a,b):eq(v,w)
        else:need(isfinite(float(a)) and abs(float(a)-float(b))<=1e-9*max(1,abs(float(b))),str((a,b)));count+=1
    def output(k,v):eq(v,literal(d.mark[k][1]));seen.add(k)
    def truth(ok,message):
        nonlocal count
        need(ok,message);count+=1
    expected={'poverty-y':'(2,6,9,15)','poverty-z':'10','poverty-budget':'4','credit':'(8,4,1,3)','credit-wealth':'(0,2,5)','capability':'(1,1,4,2,2,2,1)','structural':'(1/3,1,4,8,2)','experiment-size':'4','experiment':'(4,2,1,1/2)','experiment-response':'4/5','experiment-observed':'11/2','experiment-support':'(0,10)'};need(set(expected)==set(x),'primitive inventory')
    for k,v in expected.items():eq(x[k],literal(v))
    y=x['poverty-y'];z=x['poverty-z'];budget=x['poverty-budget'];output('poverty-indices',poverty(y,z));output('poverty-progressive',poverty((y[0]+1,y[1]-1,*y[2:]),z));output('poverty-headcount-policy',poverty((y[0],y[1]+3,y[2]+1,y[3]),z));best=(y[0]+budget,*y[1:]);output('poverty-severity-policy',poverty(best,z));output('ex1-r',poverty(y[:2],z));output('ex1-u',poverty(y[2:],z));output('ex2-budget',sum(max(z-v,0) for v in y));eq(tuple((a+b)/2 for a,b in zip(poverty(y[:2],z),poverty(y[2:],z))),poverty(y,z))
    for t0,t1,t2 in product(range(9),repeat=3):
        transfer=tuple(Q(t,2) for t in (t0,t1,t2));total=sum(transfer)
        if total<=budget:
            values=tuple(y[i]+transfer[i] for i in range(3))+(y[3],);truth(poverty(values,z)[2]>=poverty(best,z)[2],'severity global witness');truth(poverty(values,z)[0]>=Q(1,2),'headcount lower bound')
    eq(poverty((0,10,20),10),(Q(1,3),Q(1,3),Q(1,3)));eq(poverty((2,6,9,15),10,(0,0,0,1)),(0,0,0))
    A,F,R,cap=x['credit'];k=(A/(2*R))**2;output('credit-unconstrained',(k,A*A/(4*R)-R*F));choices=[credit(A,F,R,w,cap) for w in x['credit-wealth']];output('credit-choices',tuple(c[:2] for c in choices));c=credit(A,F,R,5,0);output('ex3-noloan',(c[0],c[2],c[3],c[1]));output('ex4-best',Q(9,4)-4)
    for w,cap0 in product((0,1,2,5,10),(0,3,10)):
        selected=credit(A,F,R,w,cap0);K=w+cap0-F
        if K>=0:
            for j in range(21):
                kj=float(K)*j/20;surplus=float(A)*sqrt(kj)-float(R)*(float(F)+kj);truth(selected[1]>=surplus-1e-10,'credit global witness')
        if selected[0]>0:
            cost=float(F)+selected[0];borrow=max(cost-w,0);saved=max(w-cost,0);eq(selected[3],selected[2]-float(R)*borrow+float(R)*saved);truth(borrow<=cap0+1e-10,'loan cap')
    threshold=29-16*sqrt(3);truth(credit(A,F,R,threshold-1e-6,3)[1]==0,'below activation');truth(credit(A,F,R,threshold+1e-6,3)[1]>0,'above activation');truth(credit(3,4,1,100,100)[1]==0,'unprofitable opportunity');truth(credit(4,4,1,100,100)[1]==0,'entry tie convention')
    a,b,c,ce,ch,w,eta=x['capability'];net,social,choice=bundles(a,b,c,ce,ch,w,eta);output('capability-private',net);output('capability-social',social);eq(choice,((0,0),));private=a+b+c-ce;funded=(private,eta,-ch,private+eta-ch);output('capability-funded',funded);output('ex5-small',(1,0,-1,0));output('ex5-large',funded);output('ex6-interaction',(a+b+c)-a-b);eq(bundles(a,b,c,ce,ch,w+1,eta)[2],((0,0),));eq(bundles(a,b,c,ce,ch,w+2,eta)[2],((1,1),));truth(a+c>ce,'schooling induced by supplied health')
    theta,bar,A0,A1,B=x['structural'];old=equilibrium(theta,bar,A0,B);new=equilibrium(theta,bar,A1,B);output('structural-old',old);output('structural-new',new);p0=old[0];Y0=p0*old[2]+old[3];Y1=p0*new[2]+new[3];q0=(p0*A0,B);q1=(p0*A1,B);l0=(old[1],1-old[1]);l1=(new[1],1-new[1]);within=sum(l*(b-a) for l,a,b in zip(l0,q0,q1));realloc=sum((b-a)*q for a,b,q in zip(l0,l1,q1));output('structural-output',Y1);output('structural-decomposition',(within,realloc,Y1-Y0));eq(within+realloc,Y1-Y0);output('ex8-decomposition',(sum(l*(b-a) for l,a,b in zip(l1,q0,q1)),sum((b-a)*q for a,b,q in zip(l0,l1,q0)),sum((b-a)*(d-c) for a,b,c,d in zip(l0,l1,q0,q1))))
    h0=equilibrium(theta,0,A0,B);h1=equilibrium(theta,0,A1,B);output('ex7-shares',(h0[1],h1[1]));output('ex7-growth',p0*(h1[2]-h0[2])+h1[3]-h0[3])
    for theta0,bar0,A0 in product((Q(1,4),Q(1,2),Q(3,4)),(0,1),(2,4,8)):
        p,la,food,m=equilibrium(theta0,bar0,A0,B);eq(p*food+m,B);eq(p*A0,B);truth(0<la<1 and food>bar0 and m>0,'interior allocation');u=(float(food-bar0)**float(theta0))*float(m)**float(1-theta0)
        for j in range(1,20):
            candidate=bar0+(A0-bar0)*Q(j,20);man=B-p*candidate;u1=float(candidate-bar0)**float(theta0)*float(man)**float(1-theta0);truth(u>=u1-1e-10,'global utility witness')
    n=x['experiment-size'];baseline,direct,spill,g=x['experiment'];need(n.denominator==1 and n*g==2,'exposure counts');n=int(n);Y=lambda d,s:baseline+direct*d+spill*s;treated=Y(1,g);untreated=Y(0,g);policy=g*treated+(1-g)*untreated;output('experiment-effects',(treated-untreated,untreated-baseline,policy-baseline));output('experiment-wald',(policy-baseline)/g);output('ex9-target',direct*g)
    assignments=list(combinations(range(n),2))
    for i in range(n):
        for own in (0,1):eq(sum(Q(1,len(assignments))*int((i in selected)==bool(own))*Y(own,g)/Q(1,2) for selected in assignments),Y(own,g))
    r=x['experiment-response'];obs=x['experiment-observed'];L,U=x['experiment-support'];output('experiment-bounds',bounds(r,obs,L,U,baseline));eq(bounds(Q(1,2),obs,L,U,baseline),(Q(-5,4),Q(15,4)))
    for fn in (lambda:real(True),lambda:real(float('inf')),lambda:poverty((),10),lambda:poverty((1,),0),lambda:poverty((-1,),10),lambda:poverty((1,2),10,(1,)),lambda:poverty((1,),10,(-1,)),lambda:credit(8,0,1,2,3),lambda:credit(8,4,0,2,3),lambda:credit(8,4,1,-1,3),lambda:credit(8,4,1,1,-1),lambda:bundles(1,1,-1,2,2,2),lambda:bundles(1,1,1,0,2,2),lambda:equilibrium(0,1,4,2),lambda:equilibrium(Q(1,3),4,4,2),lambda:equilibrium(Q(1,3),1,4,0),lambda:bounds(0,5,0,10,4),lambda:bounds(1,11,0,10,4),lambda:literal('1+1'),lambda:strict('{"x":1,"x":2}'),lambda:strict('{"x":NaN}')):
        try:fn()
        except (ValueError,TypeError,ZeroDivisionError):rejects+=1
        else:raise ValueError('invalid input accepted')
    need(seen=={k for k,v in d.mark.items() if v[0]=='data-result'},'all visible results');need(raw=={f:(base/f).read_bytes() for f in FILES},'unchanged files');summary=dict(chapter='v15-c04',status='passed',worked_cases=5,solutions=10,comparisons=count,domain_rejections=rejects,inputs=len(x),results=len(seen),runtime_files=4);json.dumps(summary,allow_nan=False);return summary
if __name__=='__main__':check()
