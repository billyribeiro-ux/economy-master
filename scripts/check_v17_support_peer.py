"""Independent V17 diagnostic/oral/retention peer; opaque author checker."""
from pathlib import Path
from fractions import Fraction as F
from html.parser import HTMLParser
from itertools import combinations,product
import ast,hashlib,json,re,sys
AUTHOR=('content/assessments/parts/v17-support-opening.html','content/assessments/parts/v17-support-closing.html','scripts/check_v17_support.py','content/reviews/v17-support-sources.json','content/reviews/v17-support-author.json')
SELF='scripts/check_v17_support_peer.py';REVIEW='content/reviews/v17-support-peer.json';FILES=AUTHOR+(SELF,REVIEW)
def need(ok,msg):
    if not ok:raise ValueError(msg)
def digest(path):
    b=path.read_bytes();return {'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def literal(text):
    def visit(n):
        if isinstance(n,ast.Constant) and type(n.value) is int:return F(n.value)
        if isinstance(n,ast.Tuple):return tuple(visit(v) for v in n.elts)
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,ast.USub):return -visit(n.operand)
        if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Div):return visit(n.left)/visit(n.right)
        raise ValueError('exact rational marker')
    return visit(ast.parse(text.strip(),mode='eval').body)
class Page(HTMLParser):
    def __init__(self):
        super().__init__();self.stack=[];self.active=[];self.ids=[];self.inputs={};self.results={};self.tasks=[];self.answers=[];self.answertext={};self.sources={};self.hrefs=[];self.h1=0;self.tables=[]
    def handle_starttag(self,t,attrs):
        a=dict(attrs)
        if t=='h1':self.h1+=1
        if 'id' in a:need(a['id'] not in self.ids,'unique IDs');self.ids.append(a['id'])
        if 'href' in a:self.hrefs.append(a['href'])
        if 'data-points' in a:self.tasks.append((a['id'],int(a['data-points'])))
        if 'data-solution-for' in a:
            need(any(x=='details' and 'solutions' in v.get('class','').split() for x,v in self.stack),'solution disclosure');k=a['data-solution-for'];self.answers.append(k);self.answertext[k]='';self.active.append((self.answertext,k,len(self.stack)))
        if 'data-source' in a:self.sources[a['data-source']]=a['href']
        for k,d in [('data-input',self.inputs),('data-result',self.results)]:
            if k in a:need(a[k] not in d,'unique markers');d[a[k]]='';self.active.append((d,a[k],len(self.stack)))
        if t=='table':self.tables.append([])
        if t=='tr':self.tables[-1].append([])
        if t in ('td','th'):
            row=self.tables[-1][-1];row.append('');self.active.append((row,len(row)-1,len(self.stack)))
        if t not in ('br','hr','img','input','link','meta'):self.stack.append((t,a))
    def handle_data(self,s):
        for d,k,_ in self.active:d[k]+=s
    def handle_endtag(self,t):
        need(self.stack and self.stack[-1][0]==t,'balanced HTML');self.stack.pop();self.active=[v for v in self.active if v[2]<len(self.stack)]
def exact(values):return all(type(v) in (int,F) for v in values)
def real(values):
    need(type(values) is tuple and len(values)==4 and exact(values),'four real-growth primitives');w0,w1,p0,p1=map(F,values);need(min(w0,p0,p1)>0 and w1>=0,'real-growth domain')
    nominal=(w1-w0)/w0;inflation=(p1-p0)/p0;real=(w1/p1-w0/p0)/(w0/p0)
    return nominal,inflation,real,nominal-inflation,real-(nominal-inflation)
def project(cost,receipt,rate):
    need(exact((cost,receipt,rate)) and cost>=0 and receipt>=0 and rate>-1,'project domain');cost,receipt,rate=map(F,(cost,receipt,rate));future=receipt-cost*(1+rate)
    return receipt/(1+rate),future/(1+rate)
def cohort(values):
    need(type(values) is tuple and len(values)==4 and exact(values) and all(F(v).denominator==1 for v in values),'integer cohort');n,d,a,b=map(int,values);need(n>0 and 0<d<=n and 0<=a<=d and 0<=b<=n-d and a+b>0,'cohort domain')
    records=[(1,1)]*a+[(1,0)]*(d-a)+[(0,1)]*b+[(0,0)]*(n-d-b)
    cells=tuple(tuple(sum(x==xx and z==zz for x,z in records) for zz in (1,0)) for xx in (1,0));flags=sum(z for x,z in records)
    return cells,(d-a,n-d-b,flags,n-flags,F(a,d),F(a,flags))
def operating(a,cap,fixed):
    need(exact((a,cap,fixed)) and a>=0 and cap>0 and fixed>=0,'operating domain');a,cap,fixed=map(F,(a,cap,fixed));candidates={F(0):F(0),cap:a*cap-cap**2-fixed}
    q=a/2
    if 0<q<=cap:candidates[q]=a*q-q*q-fixed
    best=max(candidates.values());return tuple(sorted(q for q,v in candidates.items() if v==best)),best

def bounds(n,m,total,low,high):
    need(type(n) is int and type(m) is int and n>0 and 0<=m<=n and exact((total,low,high)) and low<=high and m*low<=total<=m*high,'missing domain')
    return (F(total)+(n-m)*low)/n,(F(total)+(n-m)*high)/n

def lottery(y1,y0):
    need(type(y1) is tuple and type(y0) is tuple and len(y1)==len(y0)==4 and exact(y1+y0),'four potential scores');need(all(0<=v<=2 for v in y1+y0),'score support');contrasts=[];marginal=[0]*4
    for selected in combinations(range(4),2):
        z=set(selected);contrasts.append(sum(F(y1[i],2) if i in z else -F(y0[i],2) for i in range(4)))
        for i in z:marginal[i]+=1
    return tuple(contrasts),tuple(marginal),sum(F(a-b,4) for a,b in zip(y1,y0))

def decision(good,bad,lo,hi):
    need(exact((good,bad,lo,hi)) and good>0>bad and 0<=lo<=hi<=1,'decision domain');good,bad,lo,hi=map(F,(good,bad,lo,hi));threshold=-bad/(good-bad)
    values=[p*good+(1-p)*bad for p in (lo,hi)];regret_o=max(max(v,0) for v in values);regret_a=max(max(-v,0) for v in values)
    return threshold,min(values),max(values),regret_o,regret_a

def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    before={f:digest(root/f) for f in FILES};review=json.loads((root/REVIEW).read_text());need(set(review['payloads'])==set(FILES)-{REVIEW},'six nonself bindings')
    for f,b in review['payloads'].items():need(before[f]==b,'peer binding '+f)
    author=json.loads((root/AUTHOR[4]).read_text())
    for f,b in author['payloads'].items():need(before[f]==b,'author binding '+f)
    p=Page()
    for file in AUTHOR[:2]:p.feed((root/file).read_text());need(not p.stack,'closed fragment')
    ids=['v17-d'+str(i) for i in range(1,9)]+['v17-o'+str(i) for i in range(1,6)]+['v17-r'+str(i) for i in range(1,6)]
    need([i for i,n in p.tasks]==p.answers==ids and p.h1==1,'18 paired tasks and only volume h1')
    need([n for i,n in p.tasks]==[5]*8+[4]*5+[8]*5,'40/20/40 points')
    for task,points in p.tasks:
        match=re.search(r'Rubric(\d+):([^.]*)\.',p.answertext[task]);need(match and int(match[1])==points,'stated rubric total '+task)
        weights=[int(v) for v in re.findall(r'\d+',match[2])];need(sum(weights)==points,'additive rubric '+task)
    need(set(review['exact_task_review'])==set(ids),'complete task review')
    need({'v17-c'+str(i).zfill(2)+'.html' for i in range(1,13)}<=set(p.hrefs),'all12 remediation routes')
    need(len(p.tables)==3 and len(p.tables[1])==13 and len(p.tables[2])==13,'full coverage and concept index')
    sources=json.loads((root/AUTHOR[3]).read_text());need(p.sources=={s['id']:s['url'] for s in sources['sources']},'source routes')
    inp={k:literal(v) for k,v in p.inputs.items()};shown={k:literal(v) for k,v in p.results.items()};count=0
    expected={'d1':real(inp['d1'])}
    cost,receipt,discount,cash,floor=inp['d2'];pv,npv=project(cost,receipt,discount);expected['d2']=(pv,npv,cash-cost,floor-(cash-cost))
    cells,expected['d3']=cohort(inp['d3']);table=p.tables[0]
    expectedrows=[('Default',)+cells[0]+(sum(cells[0]),),('No default',)+cells[1]+(sum(cells[1]),),('Total',)+tuple(cells[0][i]+cells[1][i] for i in range(2))+(sum(sum(r) for r in cells),)]
    for row,want in zip(table[1:],expectedrows):need(row[0]==want[0] and tuple(F(v) for v in row[1:])==want[1:],'complete cohort table');count+=3
    need(len(table)==4,'cohort table row count')
    need(operating(4,3,5)==((F(0),),F(0)),'global outside solution');expected['d4']=(2,-1,0);count+=1
    treated,control=inp['d5'];contrast=(treated[1]-treated[0])-(control[1]-control[0]);parallel=treated[0]+control[1]-control[0]
    expected['d5']=(contrast,parallel,treated[1]-parallel,treated[1],0)
    n,m,total,low,high,prior=inp['d6'];lo,hi=bounds(int(n),int(m),total,low,high);expected['d6']=(lo,hi,lo-prior,hi-prior)
    expected['d7']=(F(110-100,110),F(110-100,100));budget,*parts=inp['d8'];expected['d8']=(sum(parts),sum(parts)-budget,10,12,8,10,40)
    expected['o1']=real(inp['o1'])[2]
    q=80-4*10;eps=F(-4*10,q);expected['o2']=(q,-4,eps,2,80-4*5,F(-4*5,80-4*5))
    contrasts,marginal,ate=lottery(*inp['o3']);expected['o3']=(contrasts[0],ate,sum(contrasts)/len(contrasts));need(marginal==(3,3,3,3),'each half assigned');count+=4
    need(operating(12,4,33)==((F(0),),F(0)) and operating(12,4,31)==((F(4),),F(1)),'capacity and entry');expected['o4']=(4,32,-1,0,4,1);count+=2
    expected['r1']=project(*inp['r1'])+project(70,77,F(1,10))
    expected['r2']=(F(160+360,60),F(14-2,2),8,36,35,1)
    n,observed,low,high=inp['r3'];lowmean,highmean=bounds(int(n),len(observed),sum(observed),low,high);passed=sum(v>=3 for v in observed);expected['r3']=(sum(observed)/len(observed),lowmean,highmean,F(passed,n),F(passed+int(n)-len(observed),n))
    payoffs,interval=inp['r4'];expected['r4']=decision(*payoffs,*interval)
    pv,npv=project(70,88,F(1,10));expected['r5']=(pv,npv,80-70,20,6)
    need(set(expected)==set(shown),'all result groups')
    for key,v in expected.items():need(shown[key]==v,'result '+key);count+=len(v) if isinstance(v,tuple) else 1
    # Exact R1 evidence-sensitive credit: supplied final-only quote establishes PV, not its unshown setup.
    r1=p.answertext['v17-r1'];need('PV point1/4' in r1 and 'if its calculation is shown' in r1,'evidence-sensitive grade condition')
    need(sum((0,1,0,0))==1 and sum((1,1,0,0))==2,'R1 grade ledgers');count+=2
    # Enumerate actual missing support grids and their independently defined threshold rates.
    completion_worlds=0;meanvals=[];passvals=[]
    for x,y in product(range(5),repeat=2):
        full=tuple(observed)+(F(x),F(y));meanvals.append(sum(full)/len(full));passvals.append(F(sum(v>=3 for v in full),len(full)));completion_worlds+=1
    need((min(meanvals),max(meanvals))==(lowmean,highmean) and (min(passvals),max(passvals))==expected['r3'][3:],'joint missing-score/threshold witnesses');count+=4
    need(bounds(3,0,0,0,10)==(F(0),F(10)) and bounds(3,3,15,0,10)==(F(5),F(5)),'all/no missing');count+=4
    for i in range(9):
        lam=F(i,8);missing=20*lam;value=(48+missing)/10;need(value==F(24,5)+2*lam,'continuous support interiors');count+=1
    for mcf in (F(30),F(40),F(43),F(47),F(50)):
        need(contrast==(treated[1]-mcf)+(mcf-parallel),'DID decomposition');count+=1
    # Global proof witnesses respect the actual positive branch and compare the outside payoff.
    firm_worlds=0
    for a,cap,fixed in product((F(0),F(4),F(12)),(F(1),F(3),F(4)),(F(0),F(5),F(33))):
        choices,best=operating(a,cap,fixed);firm_worlds+=1
        for j in range(1,9):
            q=cap*j/8;need(a*q-q*q-fixed<=best,'global candidate against feasible grid');count+=1
    need(operating(4,3,4)[0]==(F(0),F(2)),'entry tie');count+=1
    # Regret is relative to best conditional expected action, restricted to the deterministic menu.
    threshold,lo,hi,ro,ra=expected['r4'];need(lo<0 and ra<ro,'opposing criteria');count+=2
    for i in range(101):
        pgood=F(1,4)+F(i,200);ev=pgood*12+(1-pgood)*(-6);best=max(ev,F(0));need(lo<=ev<=hi and best<=ro and best-ev<=ra,'expected payoff/regret envelopes');count+=3
    need(12*threshold-6*(1-threshold)==0,'threshold equality');count+=1
    need(36-(F(5)-6)**2==35 and max(12*F(i,2)-F(i,2)**2 for i in range(25))==36,'efficient quantity global square');count+=2
    invalid=0
    bad=[(real,((0,10,100,100),)),(real,((100,110,100,0),)),(real,((100,True,100,100),)),(project,(50,66,-1)),(project,(50,-1,0)),(cohort,((300,30,31,0),)),(cohort,((300,30,0,0),)),(operating,(4,0,5)),(operating,(4,3,-1)),(bounds,(5,6,6,0,2)),(bounds,(5,2,9,0,2)),(lottery,((2,2,0),(1,1,0))),(decision,(12,-6,F(3,4),F(1,4)))]
    for fn,args in bad:
        try:fn(*args)
        except ValueError:invalid+=1
        else:raise ValueError('invalid domain accepted')
    need(before=={f:digest(root/f) for f in FILES},'runtime unchanged')
    result={'volume':'v17','component':'support','status':'passed','runtime_files':7,'diagnostic_tasks':8,'oral_tasks':5,'retention_tasks':5,'points':[40,20,40],'chapters_mapped':12,'result_groups':len(shown),'comparisons':count,'assignment_worlds':len(contrasts),'missing_score_worlds':completion_worlds,'firm_worlds':firm_worlds,'invalid_domains':invalid,'scope':'Independent full task/proof/rubric review and primitive reconstruction; no actual learner or human teaching observation.'}
    json.dumps(result,allow_nan=False);return result
if __name__=='__main__':
    need(len(sys.argv)<=2,'usage: check_v17_support_peer.py [book-root]');check(sys.argv[1] if len(sys.argv)==2 else None)
