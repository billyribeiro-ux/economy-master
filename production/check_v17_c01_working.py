"""Bounded author checks; qualitative teaching judgment is recorded separately."""
import ast, hashlib, json, sys
from fractions import Fraction as Q
from html.parser import HTMLParser
from pathlib import Path

FILES=('production/v17-c01-working.html','production/check_v17_c01_working.py','production/v17-c01-sources-working.json','production/v17-c01-author-review-working.json')
def need(ok,why):
    if not ok:raise ValueError(why)
def digest(p):
    b=p.read_bytes();return {'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
class Document(HTMLParser):
    def __init__(self):
        super().__init__();self.ids=[];self.inputs={};self.results={};self.capture=None;self.solutions=[];self.worked=[];self.sources=[];self.h1=0;self.depth=0;self.exercises=[];self.in_exercises=False;self.tables={};self.table=None;self.row=None;self.cell=None
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if 'id' in a:self.ids.append(a['id'])
        if tag=='h1':self.h1+=1
        if tag=='article' and 'worked' in a.get('class','').split():self.worked.append(a.get('id'))
        if tag=='ol' and 'exercises' in a.get('class','').split():self.in_exercises=True
        if tag=='li' and self.in_exercises:self.exercises.append(a.get('id'))
        if tag=='details' and 'solutions' in a.get('class','').split():self.depth+=1
        if 'data-solution-for' in a:need(self.depth>0,'answer outside solutions');self.solutions.append(a['data-solution-for'])
        if 'data-source' in a:self.sources.append((a['data-source'],a['href']))
        for kind in ('input','result'):
            k='data-'+kind
            if k in a:
                dest=self.inputs if kind=='input' else self.results;need(a[k] not in dest,'duplicate marker');dest[a[k]]='';self.capture=(dest,a[k])
        if tag=='table':self.table=a.get('id');self.tables[self.table]=[]
        if tag=='tr' and self.table:self.row=[]
        if tag in ('td','th') and self.row is not None:self.cell=''
    def handle_endtag(self,tag):
        if tag=='span':self.capture=None
        if tag=='ol':self.in_exercises=False
        if tag=='details' and self.depth:self.depth-=1
        if tag in ('td','th') and self.cell is not None:self.row.append(self.cell.strip());self.cell=None
        if tag=='tr' and self.row is not None:self.tables[self.table].append(self.row);self.row=None
        if tag=='table':self.table=None
    def handle_data(self,data):
        if self.capture:self.capture[0][self.capture[1]]+=data
        if self.cell is not None:self.cell+=data

def choice(data):
    need(type(data) is tuple and len(data)==6 and all(type(x) is int for x in data),'six exact integer primitives')
    benefit=data[:4];price,cash=data[4:];need(price>=0 and cash>=0,'nonnegative price and cash')
    costs=tuple(price*q for q in range(4));net=tuple(b-c for b,c in zip(benefit,costs));feasible=tuple(q for q,c in enumerate(costs) if c<=cash)
    highest=max(net[q] for q in feasible);best=tuple(q for q in feasible if net[q]==highest)
    return costs,net,feasible,best

def contrast(v):
    need(type(v) is tuple and len(v)==4 and all(type(x) is int for x in v),'four exact group/date means')
    t0,t1,c0,c1=v
    return t1-t0,c1-c0,(t1-c1)-(t0-c0)

def order(nodes,edges):
    need(set(sum((list(e) for e in edges),[]))<=set(nodes),'unknown prerequisite')
    pending=set(nodes);done=[]
    while pending:
        ready=sorted(n for n in pending if not any(b==n and a in pending for a,b in edges))
        need(bool(ready),'cyclic prerequisite design')
        done.extend(ready);pending.difference_update(ready)
    return done

def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    before={p:digest(root/p) for p in FILES};review=json.loads((root/FILES[3]).read_text())
    need(set(review['payloads'])==set(FILES[:3]),'three nonself bindings')
    for p,b in review['payloads'].items():need(before[p]==b,'payload '+p)
    d=Document();d.feed((root/FILES[0]).read_text());sources=json.loads((root/FILES[2]).read_text())
    need(d.h1==0 and len(d.ids)==len(set(d.ids)),'HTML hierarchy/IDs')
    expected_ex=['v17-c01-ex'+str(i) for i in range(1,9)]
    need(d.exercises==expected_ex and d.solutions==expected_ex,'eight exact prompt/answer pairs')
    need(d.worked==['v17-c01-case1','v17-c01-case2'],'two worked artifacts')
    need(set(d.sources)=={(s['id'],s['url']) for s in sources['sources']},'scoped source links')
    inputs={k:ast.literal_eval(v) for k,v in d.inputs.items()};results={k:ast.literal_eval(v) for k,v in d.results.items()};expected={};count=0
    need(set(inputs)=={'dag','choice','choice-transfer','did','trend-bounds','exercise-choice','exercise-did'},'complete actual inputs')
    for source,prefix in [('choice','choice'),('choice-transfer','transfer'),('exercise-choice','exercise')]:
        costs,net,feasible,best=choice(inputs[source]);expected.update({prefix+'-net':net,prefix+'-feasible':feasible,prefix+'-best':best})
        if prefix=='exercise':expected['exercise-cost']=costs
        # Independent marginal accumulation checks direct net-benefit calculation.
        running=inputs[source][0]
        need(running==net[0],'q0 value');count+=1
        for q in range(1,4):
            running+=inputs[source][q]-inputs[source][q-1]-inputs[source][4];need(running==net[q],'marginal reconciliation');count+=1
    expected['did']=contrast(inputs['did']);t0,t1,c0,c1=inputs['did'];common=c1-c0
    expected['did-worlds']=(t0+common,t1-t0-common,t0+common+4,t1-t0-common-4)
    lo,hi=inputs['trend-bounds'];need(lo<=hi,'ordered bounds');D=expected['did'][2];expected['did-range']=(D-hi,D-lo)
    ex=inputs['exercise-did'];a,b,c=contrast(ex[:4]);first=ex[0]+ex[4];second=ex[0]+ex[5]
    expected['exercise-did']=(a,b,c,first,ex[1]-first,second,ex[1]-second,ex[5]-b)
    edges=inputs['dag'];nodes=('U','S','F','N','C','R');order(nodes,edges)
    displayed=results['dag-order'];need(set(displayed)==set(nodes) and len(displayed)==len(nodes),'displayed order')
    need(all(displayed.index(a)<displayed.index(b) for a,b in edges),'prerequisites before dependents');expected['dag-order']=displayed
    need(set(results)==set(expected),'all displayed results verified')
    for k,v in expected.items():need(results[k]==v,'result '+k);count+=len(v)
    table=d.tables['v17-c01-choice-table'];cost,net,feasible,best=choice(inputs['choice'])
    need(len(table)==5,'complete choice table')
    for q,row in enumerate(table[1:]):
        need(row==[str(q),str(inputs['choice'][q]),str(cost[q]),str(net[q]),'Yes' if q in feasible else 'No'],'choice table row');count+=5
    # Meaningful boundary and changed-assumption witnesses.
    witnesses=[((0,18,34,48,16,15),(0,)),((0,18,34,48,16,48),(1,2)),((0,18,34,48,10,30),(3,)),((0,0,0,0,0,0),(0,1,2,3)),((0,-1,-2,-3,0,0),(0,))]
    for v,w in witnesses:need(choice(v)[3]==w,'choice boundary/transfer');count+=1
    for delta in (-2,0,4):
        missing=t0+common+delta;tau=t1-missing;need(D==tau+delta,'DiD decomposition');need(expected['did-range'][0]<=tau<=expected['did-range'][1],'range witness');count+=2
    # The corrected and equal-baseline counterexample both preserve common trends.
    need(contrast((50,62,40,46))[2]==contrast((40,52,40,46))[2]==6,'baseline equality unnecessary');count+=2
    invalid=0
    for v in ((0,18,34,48,-1,20),(0,18,34,48,10,-1),(0,18,34,48,True,20),(0,18,34,48,10),(0,18,34,48,10.0,20)):
        try:choice(v)
        except ValueError:invalid+=1
        else:raise ValueError('choice domain accepted')
    try:order(nodes,edges+(('R','F'),))
    except ValueError:invalid+=1
    else:raise ValueError('cycle accepted')
    need(before=={p:digest(root/p) for p in FILES},'runtime mutation')
    result={'chapter':'v17-c01','status':'passed','runtime_files':4,'worked_artifacts':2,'exercises':8,'inputs':len(inputs),'result_markers':len(results),'comparisons':count,'invalid_domains':invalid,'scope':'Arithmetic/structure/source bindings; complete qualitative design/proof review recorded separately, no measured teaching effect.'}
    json.dumps(result,allow_nan=False);return result
if __name__=='__main__':
    need(len(sys.argv)<=2,'usage: check_v17_c01_working.py [book-root]');check(sys.argv[1] if len(sys.argv)==2 else None)
