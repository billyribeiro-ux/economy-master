"""Graduate micro field: original two-form numeric/structural author audit."""
from pathlib import Path
from hashlib import sha256
from fractions import Fraction as F
from html.parser import HTMLParser
from math import log,sqrt,exp,isfinite
import ast,json,re
FILES=('content/cross-assessments/parts/graduate-micro.html','scripts/check_graduate_micro.py','content/reviews/graduate-micro-sources.json','content/reviews/graduate-micro-author.json')
DOMAINS=('choice_duality_and_welfare','equilibrium_and_distribution','strategic_incentives_and_information','mechanism_contracts_and_matching','theory_to_research_evidence')
def need(ok,why):
    if not ok:raise ValueError(why)
def real(x):
    need(type(x) in (int,float,F) and isfinite(x),'finite real');return F(str(x)) if type(x)==float else F(x)
def probability(p):
    need(isinstance(p,(tuple,list)) and len(p)>0,'nonempty probability law');p=tuple(map(real,p));need(min(p)>=0 and sum(p)==1,'unit probability');return p
def literal(s):
    def read(n):
        if isinstance(n,ast.Constant):return real(n.value)
        if isinstance(n,(ast.Tuple,ast.List)):return tuple(read(v) for v in n.elts)
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,(ast.USub,ast.UAdd)):return (-1 if isinstance(n.op,ast.USub) else 1)*read(n.operand)
        if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Div):return read(n.left)/read(n.right)
        raise ValueError('literal-only expression')
    return read(ast.parse(s.replace('−','-').split('=',1)[-1].strip(),mode='eval').body)
def strict(raw):
    def pairs(items):
        out={}
        for key,value in items:need(key not in out,'duplicate JSON');out[key]=value
        return out
    def invalid(x):raise ValueError('nonfinite JSON')
    value=json.loads(raw,object_pairs_hook=pairs,parse_constant=invalid);json.dumps(value,allow_nan=False);return value

def harmonic(p,q,m):
    p,q,m=map(real,(p,q,m));need(p>0 and q>0 and m>=0,'harmonic choice domain');total=sqrt(p)+sqrt(q);return float(m)/(sqrt(p)*total),float(m)/(sqrt(q)*total),float(m)/total**2

def expense(p,q,u):
    p,q,u=map(real,(p,q,u));need(p>0 and q>0 and u>=0,'expense domain');h=(float(u)*(1+sqrt(q/p)),float(u)*(1+sqrt(p/q)));return float(p)*h[0]+float(q)*h[1],h

def max_choice(p,q,m):
    p,q,m=map(real,(p,q,m));need(p>0 and q>0 and m>=0,'max choice domain')
    if m==0:return ((F(0),F(0)),)
    return ((m/p,F(0)),) if p<q/2 else ((F(0),m/q),) if p>q/2 else ((m/p,F(0)),(F(0),m/q))

def price_supply(p,fixed=1):
    p,fixed=map(real,(p,fixed));need(p>=0 and fixed>0,'fixed-cost supply');profit=p*p/4-fixed
    return (F(0),) if profit<0 else (F(0),p/2) if profit==0 else (p/2,)

def core(matrix,u,v,assignment):
    need(len(matrix)==len(u)==len(v)==len(assignment)==2 and all(len(row)==2 for row in matrix),'assignment shape');need(set(assignment)=={0,1},'permutation');need(min(u)>=0 and min(v)>=0,'nonnegative payoffs');return all(u[i]+v[assignment[i]]==matrix[i][assignment[i]] for i in range(2)) and all(u[i]+v[j]>=matrix[i][j] for i in range(2) for j in range(2))

def bilateral(v,c):
    v,c=map(real,(v,c));need(0<=v<=1 and 0<=c<=1,'bilateral type domain');return (1,c,v) if v>c else (0,F(0),F(0))

def reservation(a,p,loss,benefit):
    a,p,L,b=map(real,(a,p,loss,benefit));need(a>=0 and 0<p<1 and L>0 and 0<=b<=L,'insurance domain')
    if a==0:return float(p*b)
    aa=float(a);return log((1-float(p)+float(p)*exp(aa*float(L)))/(1-float(p)+float(p)*exp(aa*float(L-b))))/aa

class Field(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.stack=[];self.ids=set();self.forms={};self.domains={};self.prompts={};self.answers={};self.rubrics={};self.mark={};self.sources={};self.h2=[];self.links=[]
    def handle_starttag(self,t,attrs):
        a=dict(attrs);need(len(a)==len(attrs),'duplicate attribute')
        if 'id' in a:need(a['id'] not in self.ids and a['id'].startswith('graduate-micro-'),'stable unique IDs');self.ids.add(a['id'])
        if t=='h1':raise ValueError('extra h1')
        if t=='h2':self.h2.append(a.get('id'))
        if 'data-form' in a:need(a['data-form'] not in self.forms,'duplicate form');self.forms[a['data-form']]=[]
        if 'data-domain' in a:
            form=next(d['data-form'] for tag,d in reversed(self.stack) if 'data-form' in d);key=(form,a['data-domain']);need(key not in self.domains,'duplicate domain');self.domains[key]=[int(a['data-domain-points']),[]]
        if 'data-points' in a:
            form=next(d['data-form'] for tag,d in reversed(self.stack) if 'data-form' in d);domain=next(d['data-domain'] for tag,d in reversed(self.stack) if 'data-domain' in d);key=a['id'];need(key not in self.prompts,'duplicate prompt');self.prompts[key]=int(a['data-points']);self.forms[form].append(key);self.domains[(form,domain)][1].append(key)
        if 'data-solution-for' in a:
            key=a['data-solution-for'];need(key not in self.answers and any(tag=='details' and 'solutions' in d.get('class','').split() for tag,d in self.stack),'paired disclosed answer');self.answers[key]=''
        if 'data-rubric-for' in a:need(a['data-rubric-for'] not in self.rubrics,'unique rubric');self.rubrics[a['data-rubric-for']]=tuple(map(int,a['data-rubric-points'].split(',')))
        for attr in ('data-input','data-result'):
            if attr in a:need(a[attr] not in self.mark,'unique marker');self.mark[a[attr]]=[attr,'']
        if 'data-source' in a:need(a['data-source'] not in self.sources,'unique source');self.sources[a['data-source']]=a['href']
        if 'href' in a:self.links.append(a['href'])
        if t not in ('br','hr','img','input','meta','link'):self.stack.append((t,a))
    def handle_data(self,s):
        for tag,a in self.stack:
            if 'data-solution-for' in a:self.answers[a['data-solution-for']]+=s
            for attr in ('data-input','data-result'):
                if attr in a:self.mark[a[attr]][1]+=s
    def handle_endtag(self,t):need(self.stack and self.stack[-1][0]==t,'balanced HTML');self.stack.pop()

def check(root=None):
    base=Path(root) if root is not None else Path(__file__).resolve().parents[1];raw={p:(base/p).read_bytes() for p in FILES};doc=Field();doc.feed(raw[FILES[0]].decode());doc.close();need(not doc.stack,'complete HTML');author=strict(raw[FILES[3]]);source=strict(raw[FILES[2]]);targets=[f'graduate-micro-{f}{i}{j}' for f in 'ab' for i in range(1,6) for j in 'abcd'];need(list(doc.prompts)==list(doc.answers)==targets and set(doc.rubrics)==set(targets),'forty exact matched scored answers');need(doc.h2==['graduate-micro-a','graduate-micro-b'],'two field form headings')
    for form in 'ab':
        need(doc.forms[form]==[x for x in targets if x.startswith('graduate-micro-'+form)] and sum(doc.prompts[x] for x in doc.forms[form])==100,'100 point form')
        for domain in DOMAINS:
            points,parts=doc.domains[(form,domain)];need(points==20 and len(parts)==4 and sum(doc.prompts[x] for x in parts)==20,'20 point domain')
    for key in targets:need(doc.prompts[key]==5 and sum(doc.rubrics[key])==5 and min(doc.rubrics[key])>0 and len(doc.answers[key])>550,'complete five-point solution/rubric')
    need(all(f'v13-c{i:02d}.html' in doc.links for i in range(1,13)) and 'v12-c03.html' in doc.links and 'v12-c04.html' in doc.links,'prerequisite and cross-volume routes');need(doc.sources=={x['id']:x['url'] for x in source['sources']},'exact source URLs');need(set(author['exact_prompt_solution_audit'])==set(targets) and author['open_findings']==[],'full author audit');bs=author['payload_bindings'];need(len(bs)==3 and {x['path'] for x in bs}==set(FILES[:3]),'three nonself hashes')
    for b in bs:need(len(raw[b['path']])==b['bytes'] and sha256(raw[b['path']]).hexdigest()==b['sha256'],'frozen payload')
    count=0;rejects=0;seen=set()
    def equal(a,b):
        nonlocal count
        if isinstance(b,(tuple,list)):
            need(isinstance(a,(tuple,list)) and len(a)==len(b),'matching numeric shape')
            for x,y in zip(a,b):equal(x,y)
        else:need(isfinite(float(a)) and abs(float(a)-float(b))<2e-9*max(1,abs(float(b))),str((a,b)));count+=1
    def witness(ok,label):
        nonlocal count
        need(ok,label);count+=1
    def mark(k,v):equal(literal(doc.mark[k][1]),v);seen.add(k)
    x={k:literal(v[1]) for k,v in doc.mark.items() if v[0]=='data-input'};expected={'a1':'(1,4,18,4,4)','a2':'(10,10,2,1)','a3':'(3/4,1/5)','a4':'(0,1,0,1)','a5':'((1/4,1/2,1/4),(2,4,-2),(1,5,1))','b1':'(1,2,6,6)','b2':'(10,3,1,1)','b3':'(8,0,2,1/2,4)','b4':'((8,6),(7,1))','b5':'(10,6,3,3,5/3,1/3)'};need(set(x)==set(expected),'primitive inventory')
    for k,v in expected.items():mark(k,literal(v))
    p,q,m,pn,qn=x['a1'];old=harmonic(p,q,m);new=harmonic(pn,qn,m);mark('a1-old',old);mark('a1-new',new);u=old[2];H=((-u*sqrt(q)/(2*float(p)**1.5),u/(2*sqrt(p*q))),(u/(2*sqrt(p*q)),-u*sqrt(p)/(2*float(q)**1.5)));mark('a1-hessian',H);mark('a1-money',(expense(pn,qn,u)[0]-float(m),float(m)-expense(p,q,new[2])[0]));equal((H[0][0]*p+H[0][1]*q,H[1][0]*p+H[1][1]*q),(0,0))
    for prices in ((1,4),(2,3),(3,3)):
        for wealth in (0,1,18):
            hx,hy,U=harmonic(*prices,wealth);equal(prices[0]*hx+prices[1]*hy,wealth);equal(expense(*prices,U)[0],wealth)
            for j in range(11):
                xx=wealth*j/10/prices[0];yy=(wealth-prices[0]*xx)/prices[1];val=xx*yy/(xx+yy) if xx+yy else 0;witness(val<=U+1e-12,'global consumer witness')
    w1,w2,t1,t2=x['a2'];taste=t1+t2;price=sqrt(2*float(taste));X=price/2;profit=price*X-X*X;ys=(float(w1)+profit/2-float(t1),float(w2)+profit/2-float(t2));mark('a2-private',(profit,*ys));Xe=sqrt(float(taste)/4);pc=float(taste)/Xe;tax=2*Xe;net=pc-tax;pre=net*Xe-Xe*Xe;revenue=tax*Xe;ye=(float(w1)+pre/2+revenue/2-float(t1),float(w2)+pre/2+revenue/2-float(t2));mark('a2-efficient-output-square',Xe*Xe);mark('a2-tax-accounts',(revenue,revenue/2,revenue/2,*ye));gains=tuple(yy-y+float(t)*log(Xe/X)+(X*X-Xe*Xe)/2 for yy,y,t in zip(ye,ys,(t1,t2)));mark('a2-gains',gains);equal(sum(ye)+Xe*Xe,w1+w2);equal(pc*Xe,net*Xe+revenue);witness(min(gains)>0,'funded Pareto improvement')
    delta,epsilon=x['a3'];mark('a3-threshold',F(1,2));effective=delta*(1-epsilon);V=2/(1-effective);mark('a3-monitor',(effective,V));equal(V,2+effective*V)
    for dd in (F(1,4),F(1,2),F(3,4)):
        value=2/(1-dd)
        if dd<F(1,2):witness(value<(value+4)/2<4,'attainable undercut')
        else:
            for bid in (0,F(3),F(39,10),F(399,100)):witness(bid<=value,'cooperative deviation bound')
    # Exact polynomial integration of gains over the uniform type square.
    first=F(1,2)*(1-F(1)+F(1,3));mark('a4-firstbest',first);mark('a4-subsidy',first);mark('a4-reserve',bilateral(1,0)[2]-bilateral(1,0)[1]);posted=F(1,2)*F(1,2)/2;mark('a4-posted',(posted,first-posted))
    grid=[F(i,4) for i in range(5)]
    for v in grid:
        for c in grid:
            trade,pay,receive=bilateral(v,c);truthbuyer=trade*v-pay;truthseller=receive-trade*c
            for report in grid:
                tr,pa,rr=bilateral(report,c);witness(tr*v-pa<=truthbuyer,'global buyer report');tr,pa,rr=bilateral(v,report);witness(rr-tr*c<=truthseller,'global seller report')
            equal(truthbuyer+truthseller-(receive-pay),trade*(v-c))
    masses,gains,costs=x['a5'];probability(masses);choices=tuple(tuple(int(g-c+s>=0) for g,c in zip(gains,costs)) for s in (0,2));take=tuple(sum(mu*d for mu,d in zip(masses,row)) for row in choices);fs=take[1]-take[0];itt=sum(mu*g*(d1-d0) for mu,g,d0,d1 in zip(masses,gains,*choices));mark('a5-experiment',(*take,fs,itt));ate=sum(mu*g for mu,g in zip(masses,gains));mark('a5-estimands',(itt/fs,ate));spending=2*take[1];private=sum(mu*((g-c+2)*d1-(g-c)*d0) for mu,g,c,d0,d1 in zip(masses,gains,costs,*choices));mark('a5-welfare',(private,-spending,private-spending));equal(private-spending,sum(mu*(g-c)*(d1-d0) for mu,g,c,d0,d1 in zip(masses,gains,costs,*choices)))
    p,q,m,u=x['b1'];mark('b1-demand',max_choice(p,q,m));mark('b1-hicks',u*min(p,q/2));mark('b1-supergradient',(u/2,u/4));mark('b1-cv',u*min(F(3,2),q/2)-m)
    for pp,qq in ((F(1,2),2),(2,2),(1,2)):
        for bundle in max_choice(pp,qq,m):equal(pp*bundle[0]+qq*bundle[1],m);equal(max(bundle[0],2*bundle[1]),max(m/pp,2*m/qq))
    w,theta,fixed,coef=x['b2'];X=(sqrt(1+2*float(theta))-1)/2;cost=float(fixed)+X*X;num=float(w)-cost;sub=float(fixed)-X*X;mark('b2-optimum',(X,num));mark('b2-subsidy',sub);mark('b2-cost-comparison',(fixed+F(1,4),fixed));equal(2*X,float(theta)/(1+X));equal(2*X*X+sub,cost);witness(float(theta)*log(1+X)-cost>0,'operation beats shutdown')
    for pp in (F(1,10),1,2,F(5,2),3,5):
        demand=max(F(0),theta/pp-1);witness(demand not in price_supply(pp),'no deterministic competitive match')
    intercept,cl,ch,pl,cap=x['b3'];mean=(intercept-(pl*cl+(1-pl)*ch))/3;ql=(intercept-cl-mean)/2;qh=(intercept-ch-mean)/2;expectedprofit=pl*ql*ql+(1-pl)*qh*qh;mark('b3-independent',(ql,qh,mean));mark('b3-independent-moments',(2*mean,expectedprofit,(ql-(intercept-cl)/3)**2));indvar=2*(pl*(ql-mean)**2+(1-pl)*(qh-mean)**2);corr=( (intercept-cl)/3,(intercept-ch)/3);cvar=pl*(2*corr[0]-2*mean)**2+(1-pl)*(2*corr[1]-2*mean)**2;cprofit=pl*corr[0]**2+(1-pl)*corr[1]**2;mark('b3-correlation-comparison',(indvar,cvar,cprofit))
    for ci,qi in ((cl,ql),(ch,qh)):
        obj=lambda z:z*(intercept-ci-mean-z)
        for z in (0,1,2,3,4):witness(obj(qi)>=obj(z),'global conditional Cournot payoff')
    S=x['b4'];cross=S[0][1]+S[1][0];mark('b4-surplus',cross);mark('b4-difference-domain',(S[0][0]-S[1][0],S[0][1]-S[1][1]));divisions=((3,1,6,3),(4,1,6,2));mark('b4-divisions',divisions)
    for division in divisions:witness(core(S,division[:2],division[2:],(1,0)),'funded stable assignment');equal(sum(division),cross)
    altered=((S[0][0],S[0][1]),(F(5),S[1][1]));newdiv=(4,1,4,2);mark('b4-new-division',newdiv);witness(core(altered,newdiv[:2],newdiv[2:],(1,0)),'changed stable assignment');witness(not core(altered,(3,1),(6,3),(1,0)),'old division unfunded')
    w,L,full,b,h,p=x['b5'];a=log(2)/3;partial=reservation(a,p,L,b);mark('b5-partial-reservation',partial);mark('b5-profit',h-p*b);mark('b5-mle',F(30,90));equal(reservation(a,p,L,L),full);witness(reservation(0,F(1,2),L,b)<float(h)<partial,'distinct world choices')
    for aa in (.01,.05,.1,.3,.6):
        pp=1/(1+exp(3*aa));equal(reservation(aa,pp,L,L),full);hh=reservation(aa,pp,L,b);witness(1.5<hh<3,'partial reservation range');witness(reservation(aa+.001,1/(1+exp(3*(aa+.001))),L,b)>hh,'monotonic identification witness')
    need(seen==set(doc.mark),'all visible primitive/result markers')
    malformed=[(real,(True,)),(real,(float('nan'),)),(probability,((F(1,4),F(1,4)),)),(probability,((-1,2),)),(literal,('x()',)),(literal,('True',)),(literal,('1/0',)),(strict,('{"x":1,"x":2}',)),(strict,('{"x":NaN}',)),(harmonic,(0,1,1)),(harmonic,(1,1,-1)),(expense,(1,0,1)),(expense,(1,1,-1)),(max_choice,(-1,1,1)),(price_supply,(-1,)),(price_supply,(1,0)),(core,(((1,2),(3,4)),(1,2),(3,4),(0,0))),(core,(((1,2),(3,4)),(-1,2),(3,4),(0,1))),(bilateral,(-1,0)),(bilateral,(1,2)),(reservation,(-1,F(1,2),6,3)),(reservation,(1,0,6,3)),(reservation,(1,F(1,2),6,7))]
    for fn,args in malformed:
        try:fn(*args)
        except (ValueError,ZeroDivisionError):rejects+=1
        else:raise ValueError('malformed accepted '+fn.__name__)
    need({p:(base/p).read_bytes() for p in FILES}==raw,'unchanged runtime');summary=dict(assessment='graduate-qualifying',field='micro',status='passed',forms=2,problems=10,scored_subparts=40,solutions=40,points_per_form=100,domains_per_form=5,comparisons=count,domain_rejections=rejects,primitive_markers=len(x),result_markers=len(doc.mark)-len(x),runtime_files=4);json.dumps(summary,allow_nan=False);return summary
if __name__=='__main__':check()
