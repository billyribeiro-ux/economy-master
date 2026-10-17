"""V18C09 independent workload, pair-label assignment and casewise routing oracle."""
from pathlib import Path
from fractions import Fraction as F
from html.parser import HTMLParser
from itertools import product, combinations
import hashlib,json,sys,ast,math
FILES=('content/chapters/v18-c09.html','scripts/check_v18_c09.py','content/reviews/v18-c09-sources.json','content/reviews/v18-c09-author.json','scripts/check_v18_c09_peer.py','content/reviews/v18-c09-peer.json')
def need(ok,msg):
    if not ok:raise ValueError(msg)
def digest(p):
    b=p.read_bytes();return {'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def values(text):return tuple(F(t.strip().replace('−','-')) for t in text.strip().strip('()').split(',') if t.strip())
class Page(HTMLParser):
    def __init__(self):
        super().__init__();self.ids=[];self.h1=False;self.worked=[];self.exercises=[];self.answers=[];self.sources=[];self.inputs={};self.results={};self.marker=None;self.details=0;self.in_ex=False;self.tables={};self.table=None;self.row=None;self.cell=None;self.points={}
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if 'id' in a:self.ids.append(a['id'])
        if tag=='h1':self.h1=True
        if tag=='article' and 'worked' in a.get('class','').split():self.worked.append(a['id'])
        if tag=='ol' and 'exercises' in a.get('class','').split():self.in_ex=True
        if tag=='li' and self.in_ex:self.exercises.append(a['id'])
        if tag=='details' and 'solutions' in a.get('class','').split():self.details+=1
        if 'data-solution-for' in a:need(self.details>0,'answer outside solution wrapper');self.answers.append(a['data-solution-for'])
        if 'data-source' in a:self.sources.append((a['data-source'],a['href']))
        for k,d in [('data-input',self.inputs),('data-result',self.results)]:
            if k in a:need(a[k] not in d,'duplicate marker');d[a[k]]='';self.marker=(d,a[k])
        if tag=='table':self.table=a.get('id');self.tables[self.table]=[]
        if tag=='tr' and self.table:self.row=[]
        if tag in ('td','th') and self.row is not None:self.cell=''
        if 'data-points' in a:self.points.setdefault(self.table,[]).append(int(a['data-points']))
    def handle_endtag(self,tag):
        if tag=='span':self.marker=None
        if tag=='ol':self.in_ex=False
        if tag=='details' and self.details:self.details-=1
        if tag in ('th','td') and self.cell is not None:self.row.append(self.cell.strip());self.cell=None
        if tag=='tr' and self.row is not None:self.tables[self.table].append(self.row);self.row=None
        if tag=='table':self.table=None
    def handle_data(self,text):
        if self.marker:self.marker[0][self.marker[1]]+=text
        if self.cell is not None:self.cell+=text



def parse(text):
    def walk(node):
        if isinstance(node,ast.Tuple):return tuple(walk(x) for x in node.elts)
        if isinstance(node,ast.Constant) and type(node.value) in (int,float):return F(str(node.value))
        if isinstance(node,ast.UnaryOp) and isinstance(node.op,ast.USub):return -walk(node.operand)
        if isinstance(node,ast.BinOp) and isinstance(node.op,ast.Div):return walk(node.left)/walk(node.right)
        raise ValueError('unsupported exact literal')
    return walk(ast.parse(text.replace('−','-'),mode='eval').body)
def vector(x,n=None):
    need(type(x) is tuple and (n is None or len(x)==n) and len(x)>0 and all(type(t) in (int,F) for t in x),'exact nonempty vector')
    return tuple(F(t) for t in x)

def cap(a,v,f,r):
    a,v,f,r=vector((a,v,f,r));need(min(a,v,f)>=0 and 0<=r<1,'capacity domain')
    workload=(F(1),1/(1-r),F(1));return min(z/w for z,w in zip((a,v,f),workload))
def ledger(q,arrival,capacity,days):
    q,arrival,capacity=vector((q,arrival,capacity));need(min(q,arrival,capacity)>=0 and type(days) is int and days>=0,'ledger domain')
    completed=F(0)
    for _ in range(days):
        available=q+arrival;done=min(available,capacity);q=available-done;completed+=done
    return q,completed
def drain(q,arrival,capacity):
    q,arrival,capacity=vector((q,arrival,capacity));need(min(q,arrival,capacity)>=0,'drain domain')
    return F(0) if q==0 else (q/(capacity-arrival) if capacity>arrival else None)
def options(data,changes):
    a,v,f,r,arrival,q,budget=vector(data,7);cr,vr=vector(changes[0],2);ci,ai,ri=vector(changes[1],3);cf,ff=vector(changes[2],2)
    need(min(cr,ci,cf,vr,ai,ff,budget)>=0 and 0<=ri<1,'change domain')
    out={}
    for mask in product((0,1),repeat=3):
        R,I,Ff=mask;cost=R*cr+I*ci+Ff*cf;av=ai if I else a;rv=ri if I else r;vv=v+R*vr;fv=f+Ff*ff
        name='+'.join(k for k,b in zip('RIF',mask) if b) or 'None';out[name]=(cost,av,vv,rv,fv,cap(av,vv,fv,rv))
    return out
def choose(opts,budget):
    need(type(budget) in (int,F) and budget>=0,'budget domain');available=[(v[-1],-v[0],name) for name,v in opts.items() if v[0]<=budget];need(bool(available),'empty option set')
    best=max((a,b) for a,b,_ in available);return tuple(name for a,b,name in available if (a,b)==best)
def randomize(pairs):
    need(type(pairs) is tuple and len(pairs)>0,'pairs domain');pairs=tuple(vector(p,2) for p in pairs);m=len(pairs)
    obs=sum(a-b for a,b in pairs)/m;dist=[]
    for flips in product((0,1),repeat=m):
        treated=[p[f] for p,f in zip(pairs,flips)];control=[p[1-f] for p,f in zip(pairs,flips)];dist.append((sum(treated)-sum(control))/m)
    tail=sum(abs(x)>=abs(obs) for x in dist);return obs,tail,len(dist),F(tail,len(dist)),tuple(dist)
def expand(rows):
    records=[]
    for row in rows:
        band=row[0];counts=[int(x) for x in row[1:5]];need(min(counts)>=0 and sum(counts)==int(row[5]),'confusion count domain')
        for count,(truth,pred) in zip(counts,((1,1),(1,0),(0,1),(0,0))):records.extend((band,truth,pred) for _ in range(count))
    need(bool(records),'nonempty records');return tuple(records)
def policy(records,automatic,costs,human_misses=0):
    miss,false,human,infer=vector(costs,4);need(min(miss,false,human,infer)>=0 and type(human_misses) is int and human_misses>=0,'policy costs domain')
    n=len(records);need(n>0,'empty test');auto=errors=reviews=0;loss=F(0);urgentauto=missauto=0
    for band,truth,pred in records:
        if band in automatic:
            auto+=1;errors+=truth!=pred;urgentauto+=truth;missauto+=truth==1 and pred==0
            if truth!=pred:loss+=miss if truth else false
        else:reviews+=1;loss+=human
    need(human_misses<=reviews,'human misses domain')
    if automatic:loss+=n*infer
    loss+=human_misses*miss
    return (F(auto,n),errors,reviews,loss),(urgentauto,missauto)
def cdf(n,x,p):
    need(type(n) is int and n>0 and type(x) is int and 0<=x<=n and type(p) in (int,F) and 0<=p<=1,'binomial domain')
    return sum(F(math.comb(n,k))*p**k*(1-p)**(n-k) for k in range(x+1))
def bound(n,alpha=F(1,20)):
    need(type(n) is int and n>0 and type(alpha) in (int,F) and 0<alpha<1,'bound domain')
    # Bracket the zero-count binomial probability, independently of the displayed root formula.
    left,right=0.0,1.0
    for _ in range(70):
        mid=(left+right)/2
        if (1-mid)**n>alpha:left=mid
        else:right=mid
    return (left+right)/2

def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1];start={p:digest(root/p) for p in FILES}
    review=json.loads((root/FILES[5]).read_text());need(set(review['payloads'])==set(FILES[:5]),'five nonself bindings')
    for path,binding in review['payloads'].items():need(start[path]==binding,'binding '+path)
    author=json.loads((root/FILES[3]).read_text())
    for path,binding in author['payloads'].items():need(start[path]==binding,'author binding '+path)
    page=Page();page.feed((root/FILES[0]).read_text());sources=json.loads((root/FILES[2]).read_text())
    tasks=['v18-c09-e'+str(i) for i in range(1,9)]
    need(not page.h1 and len(page.ids)==len(set(page.ids)) and page.exercises==page.answers==tasks,'structure/exact solutions')
    need(page.worked==['v18-c09-case1','v18-c09-case2'],'worked artifacts')
    need(set(page.sources)=={(s['id'],s['url']) for s in sources['sources']},'exact source URLs')
    inputs={k:parse(v) for k,v in page.inputs.items()};shown={k:parse(v) for k,v in page.results.items()}
    need(set(inputs)=={'process','changes','ai-costs'},'all primitive groups')
    data=inputs['process'];a,v,f,r,arrival,q,budget=vector(data,7);opts=options(data,inputs['changes']);count=0
    for row in page.tables['v18-c09-options'][1:]:need(tuple(F(x) for x in row[1:])==opts[row[0]],'complete option '+row[0]);count+=6
    need(len(opts)==8 and choose(opts,budget)==('R',),'global cost tie break');count+=1
    Rcap=opts['R'][-1];q10,_=ledger(q,arrival,Rcap,10);_,done30=ledger(q,arrival,Rcap,30)
    expected={'process-choice':(opts['None'][-1],Rcap,opts['R'][0],drain(q,arrival,Rcap),q10,done30)}
    pairs=tuple(tuple(F(x) for x in row[1:3]) for row in page.tables['v18-c09-pilot'][1:])
    need(all(a-b==F(row[3]) for (a,b),row in zip(pairs,page.tables['v18-c09-pilot'][1:])),'raw pair differences');count+=4
    result=randomize(pairs);expected['pilot']=(sum(a for a,b in pairs)/len(pairs),sum(b for a,b in pairs)/len(pairs))+result[:4]
    changed=pairs[:-1]+((F(11),pairs[-1][1]),);rc=randomize(changed);expected['pilot-change']=rc[:4]
    records=expand(page.tables['v18-c09-ai'][1:]);costs=inputs['ai-costs'][:4];daily,staff=inputs['ai-costs'][4:]
    policies=[policy(records,auto,costs) for auto in (('H',),('H','M'),('H','M','L'),())];expected['ai-policies']=tuple(x[0] for x in policies)
    base=policies[0][0];fraction=F(base[2],len(records));need(policies[0][1]==(4,0) and policies[1][1]==(12,2),'conditional denominators');count+=2
    need(sum(t for _,t,_ in records)==30 and sum(t==p for _,t,p in records)==83,'all-test urgent and accuracy');count+=2
    expected['zero-bound-sizes']=(F(policies[0][1][0]),F(58),F(59))
    expected['zero-bound-display']=tuple(F(f'{bound(n):.6f}') for n in (policies[0][1][0],58,59))
    need(cdf(58,0,F(1,20))>F(1,20)>=cdf(59,0,F(1,20)),'exact minimal n');count+=2
    qstaff,_=ledger(q,F(38),Rcap,10);reduced=cap(a,45,f,r);qreduced,_=ledger(q,F(38),reduced,10)
    expected['staff-change']=(qstaff,drain(q,38,Rcap),reduced,qreduced)
    need(drain(q,38,reduced) is None and choose(opts,13)==('R+I',),'arrival stability/budget change');count+=2
    ricap=opts['R+I'][-1];_,done9=ledger(q,arrival,ricap,9);expected['budget-change']=(ricap,opts['R+I'][0],drain(q,arrival,ricap),done9)
    changedcost=policy(records,('H',),costs,1)[0][-1]
    expected['fallback-change']=(100*fraction,staff/fraction,changedcost,F(1,sum(t for _,t,_ in records)))
    retcap=cap(a,50,f,F(1,4));demand=daily*fraction;backlog,_=ledger(0,demand,45,8);expected['retention']=(retcap,drain(q,arrival,retcap),demand,demand-45,backlog)
    need(set(shown)==set(expected),'all numerical result groups')
    def leaves(x):return sum(leaves(y) for y in x) if isinstance(x,tuple) else 1
    for k,value in expected.items():need(value==shown[k],'displayed '+k);count+=leaves(value)
    # Pairwise weight threshold from per-case costs, including a changed human error.
    for h in (F(0),F(19),F(39,2),F(20),F(30)):
        cs=(h,)+costs[1:];s=policy(records,('H',),cs)[0][-1];aa=policy(records,('H','M'),cs)[0][-1]
        need(aa-s==2*h-39,'pairwise miss-cost boundary');count+=1
    processworlds=0
    for rv,visits,lam in product((F(0),F(1,5),F(1,4),F(9,10)),(F(0),F(40),F(50)),(F(0),F(36),F(38),F(60))):
        cp=cap(a,visits,f,rv);processworlds+=1
        for days in (0,1,10,30):
            backlog,finished=ledger(q,lam,cp,days);need(backlog==max(F(0),q+(lam-cp)*days) and finished+backlog==q+lam*days,'daily conservation versus closed form');count+=2
        partial=sum(rv**j for j in range(12));need(partial+rv**12/(1-rv)==1/(1-rv),'geometric partial sum and tail');count+=1
    # Inclusive exact randomization size, checked at every attainable tail fraction.
    for z in (result,rc):
        dist=z[-1];pvals=[F(sum(abs(v)>=abs(t) for v in dist),len(dist)) for t in dist]
        for alpha in (F(1,20),F(1,8),F(1,4),F(1,2),F(1)):
            need(F(sum(p<=alpha for p in pvals),len(dist))<=alpha,'sharp-null randomization size');count+=1
    # Unbiased pair ATE directly from both assignments in heterogeneous potential-outcome worlds.
    pairworlds=0
    for y0i,y1i,y0j,y1j in product((F(0),F(2)),repeat=4):
        average=((y1i-y0j)+(y1j-y0i))/2;need(average==((y1i-y0i)+(y1j-y0j))/2,'pair ATE');count+=1;pairworlds+=1
    # Full count procedure: candidate p is excluded exactly at a small lower-CDF tail.
    coverageworlds=0
    for n,p in product((1,2,4,7),(F(0),F(1,20),F(1,4),F(1,2),F(1))):
        excluded=F(0)
        for x in range(n+1):
            mass=F(math.comb(n,x))*p**x*(1-p)**(n-x)
            if cdf(n,x,p)<F(1,20):excluded+=mass
        need(excluded<=F(1,20),'binomial endpoint noncoverage bound');count+=1;coverageworlds+=1
    invalid=0
    bad=[lambda:cap(60,40,50,1),lambda:cap(60,-1,50,0),lambda:cap(True,40,50,0),lambda:ledger(-1,1,1,1),lambda:ledger(1,1,1,-1),lambda:ledger(1,1,1,True),lambda:drain(1,-1,2),lambda:choose(opts,-1),lambda:randomize(()),lambda:policy(records,('H',),(-1,1,2,F(1,10))),lambda:policy(records,('H',),costs,61),lambda:bound(0),lambda:bound(4,1),lambda:cdf(4,5,F(1,2)),lambda:cdf(4,1,F(11,10))]
    for fbad in bad:
        try:fbad()
        except ValueError:invalid+=1
        else:raise ValueError('invalid domain accepted')
    need(start=={p:digest(root/p) for p in FILES},'read-only runtime')
    out={'chapter':'v18-c09','status':'passed','runtime_files':6,'worked_cases':2,'exercises':8,'result_groups':len(shown),'comparisons':count,'process_worlds':processworlds,'pair_ATE_worlds':pairworlds,'randomized_assignments':len(result[-1]),'binomial_coverage_worlds':coverageworlds,'invalid_domains':invalid,'scope':'Independent primitive workload, swapped pair labels, expanded casewise routing and binomial-tail oracle. Full qualitative/proof review separate; author checker opaque; no actual deployment or human leadership evaluation.'}
    json.dumps(out,allow_nan=False);return out
if __name__=='__main__':
    need(len(sys.argv)<=2,'usage: check_v18_c09_peer_working.py [book-root]');check(sys.argv[1] if len(sys.argv)==2 else None)
