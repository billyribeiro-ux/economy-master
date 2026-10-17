"""Independent visible-primitive peer oracle; author checker is an opaque payload."""
from pathlib import Path
from fractions import Fraction as F
from itertools import combinations, product
from html.parser import HTMLParser
import hashlib, json, sys

AUTHOR=('production/v17-c02-working.html','production/check_v17_c02_working.py','production/v17-c02-sources-working.json','production/v17-c02-author-review-working.json')
SELF='production/check_v17_c02_peer_working.py'
REVIEW='production/v17-c02-peer-review-working.json'
FILES=AUTHOR+(SELF,REVIEW)
def require(ok,message):
    if not ok:raise ValueError(message)
def digest(path):
    data=path.read_bytes();return {'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
def exact(s):
    return F(s.strip().replace('−','-'))
def vector(s):
    return tuple(exact(x) for x in s.strip().strip('()').split(',') if x.strip())

class Page(HTMLParser):
    def __init__(self):
        super().__init__();self.ids=[];self.inputs={};self.results={};self.mark=None;self.worked=[];self.exercises=[];self.solutions=[];self.sources=[];self.exercise_list=False;self.details=0;self.h1=False;self.tables=[];self.table=None;self.caption=False;self.row=None;self.cell=None
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if 'id' in a:self.ids.append(a['id'])
        if tag=='h1':self.h1=True
        if tag=='article' and 'worked' in a.get('class','').split():self.worked.append(a['id'])
        if tag=='ol' and 'exercises' in a.get('class','').split():self.exercise_list=True
        if tag=='li' and self.exercise_list:self.exercises.append(a['id'])
        if tag=='details' and 'solutions' in a.get('class','').split():self.details+=1
        if 'data-solution-for' in a:require(self.details>0,'solution outside wrapper');self.solutions.append(a['data-solution-for'])
        if 'data-source' in a:self.sources.append((a['data-source'],a['href']))
        for key,destination in [('data-input',self.inputs),('data-result',self.results)]:
            if key in a:require(a[key] not in destination,'duplicate marker');destination[a[key]]='';self.mark=(destination,a[key])
        if tag=='table':self.table={'caption':'','rows':[]}
        if tag=='caption':self.caption=True
        if tag=='tr':self.row=[]
        if tag in ('td','th'):self.cell=''
    def handle_endtag(self,tag):
        if tag=='span':self.mark=None
        if tag=='ol':self.exercise_list=False
        if tag=='details' and self.details:self.details-=1
        if tag=='caption':self.caption=False
        if tag in ('td','th') and self.cell is not None:self.row.append(self.cell.strip());self.cell=None
        if tag=='tr' and self.row is not None:self.table['rows'].append(self.row);self.row=None
        if tag=='table':self.tables.append(self.table);self.table=None
    def handle_data(self,text):
        if self.mark:self.mark[0][self.mark[1]]+=text
        if self.caption:self.table['caption']+=text
        if self.cell is not None:self.cell+=text

def capacity(m0,m1,p0,p1):
    require(all(type(x) in (int,F) for x in (m0,m1,p0,p1)),'exact numeric primitives')
    require(m0>0 and m1>=0 and p0>0 and p1>0,'capacity domain')
    q0,q1=F(m0)/p0,F(m1)/p1
    return q0,q1,F(m1-m0)/m0,F(p1-p0)/p0,(q1-q0)/q0

def lottery(schedule):
    require(type(schedule) is tuple and len(schedule)>=2 and len(schedule)%2==0,'positive even roster')
    require(all(type(r) is tuple and len(r)==2 and all(type(y) is int and y in (0,1) for y in r) for r in schedule),'binary potential outcomes')
    n=len(schedule);half=n//2;answers={}
    for selected in combinations(range(n),half):
        observed=[row[int(i in selected)] for i,row in enumerate(schedule)]
        offered=sum(observed[i] for i in selected);controls=sum(observed)-offered
        answers[selected]=F(offered,half)-F(controls,half)
    target=F(sum(b-a for a,b in schedule),n)
    return answers,target

def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    before={p:digest(root/p) for p in FILES};record=json.loads((root/REVIEW).read_text())
    require(set(record['payloads'])==set(FILES)-{REVIEW},'five peer bindings')
    for p,h in record['payloads'].items():require(before[p]==h,'peer payload '+p)
    author=json.loads((root/AUTHOR[3]).read_text())
    for p,h in author['payloads'].items():require(before[p]==h,'author payload '+p)
    page=Page();page.feed((root/AUTHOR[0]).read_text());sources=json.loads((root/AUTHOR[2]).read_text())
    require(not page.h1 and len(page.ids)==len(set(page.ids)),'HTML IDs/headings')
    tasks=['v17-c02-e'+str(i) for i in range(1,9)]
    require(page.exercises==tasks and page.solutions==tasks,'eight complete matched tasks')
    require(page.worked==['v17-c02-case1','v17-c02-case2'],'two actual lessons')
    require(set(page.sources)=={(s['id'],s['url']) for s in sources['sources']},'source URLs/scopes')
    tables={t['caption']:t['rows'] for t in page.tables};require(len(tables)==len(page.tables)==7,'seven distinct actual tables')
    rows=tables['Case 1 complete inputs and purchasing-capacity calculation'][1:]
    require(len(rows)==2,'two observed dates')
    m0,p0,q0=map(exact,rows[0][1:]);m1,p1,q1=map(exact,rows[1][1:]);base=capacity(m0,m1,p0,p1)
    require(base[:2]==(q0,q1),'case1 capacities')
    expected={'case1-rates':base[2:],'approximation-error':(base[4]-(base[2]-base[3]),)}
    count=2
    for row in tables['Holding M=220 fixed: the denominator changes capacity'][1:]:
        p,q=map(exact,row);require(q==m1/p,'fixed money capacity');count+=1
    inputs={k:vector(v) for k,v in page.inputs.items()}
    require(set(inputs)=={'e1-money','e1-price','e2-prices','e3-r','e3-pi','e8-cash'},'complete visible inputs')
    expected['e1']=capacity(m0,inputs['e1-money'][0],p0,inputs['e1-price'][0])
    expected['e2']=tuple(m1/p for p in inputs['e2-prices'])
    r,pi=inputs['e3-r'][0],inputs['e3-pi'][0]
    q=capacity(1,1+r,1,1+pi)[4];expected['e3']=(q,r-pi,100*(q-r+pi))
    outcomes=tables['Complete synthetic potential outcomes, fixed across assignment draws'][1:]
    names=[r[0] for r in outcomes];require(names==['A','B','C','D'],'bank labels')
    schedule=tuple(tuple(int(v) for v in row[1:3]) for row in outcomes)
    for row,(a,b) in zip(outcomes,schedule):require(exact(row[3])==b-a,'individual effect');count+=1
    contrasts,tau=lottery(schedule)
    expected.update({'roster-effect':(tau,),'realized-contrast':(contrasts[(0,1)],),'assignment-average':(sum(contrasts.values())/len(contrasts),),'e5':(contrasts[(0,2)],tau)})
    restricted=[v for k,v in contrasts.items() if 0 in k];mean=sum(restricted)/len(restricted);expected['e6']=(mean,tau,mean-tau)
    marginal=F(sum(0 in k for k in contrasts),len(contrasts));conditional=F(sum(0 in k and 1 in k for k in contrasts),sum(1 in k for k in contrasts));expected['e7']=(marginal,conditional)
    c,i,o=inputs['e8-cash'];expected['e8']=(i-o,c+i-o)
    displayed={k:vector(v) for k,v in page.results.items()}
    require(set(displayed)==set(expected),'all marked results')
    for k,v in expected.items():require(displayed[k]==v,'displayed '+k);count+=len(v)
    for row in tables['All possible invitation pairs under the uniform lottery'][1:]:
        pair=tuple(names.index(v.strip()) for v in row[0].split(','));require(exact(row[1])==contrasts[pair],'assignment table');count+=1
    actual=tables['One realized assignment: invite A and B'][1:]
    require([tuple(exact(v) for v in row[1:]) for row in actual]==[(F(1),F(2),F(1,2)),(F(2),F(2),F(1))],'realized observed groups');count+=6
    require([tuple(exact(v) for v in row) for row in tables['Capacity of a fixed 220 balance'][1:]]==list(zip(inputs['e2-prices'],expected['e2'])),'exercise2 table');count+=6
    cash=tuple(exact(row[1]) for row in tables['Cash reconciliation, common currency units'][1:]);require(cash==(c,i-o,c+i-o),'cash table');count+=3
    # Boundary witnesses use direct levels, independently checking growth algebra.
    for r,pi in [(F(0),F(0)),(F(-1),F(7,3)),(F(1,5),F(1,5)),(F(1,3),F(0)),(F(0),F(-1,2)),(F(-1,4),F(2,5))]:
        *_,g=capacity(100,100*(1+r),2,2*(1+pi));require(g==(r-pi)/(1+pi),'exact growth identity');require(g-r+pi==-pi*(r-pi)/(1+pi),'approximation error identity');count+=2
    # Verify the design property across all four-bank binary potential schedules.
    for bits in product((0,1),repeat=8):
        alt=tuple((bits[2*i],bits[2*i+1]) for i in range(4));values,target=lottery(alt);require(sum(values.values())/len(values)==target,'finite randomization expectation');count+=1
    # The smallest even roster and complete-zero/full outcome boundaries.
    for alt in (((0,1),(0,1)),((0,0),(0,0)),((1,1),(1,1))):
        values,target=lottery(alt);require(sum(values.values())/len(values)==target,'two-bank boundary');count+=1
    require(capacity(150,165,3,F(33,10))==(F(50),F(50),F(1,10),F(1,10),F(0)),'delayed retention');count+=5
    invalid=0
    for args in [(0,1,1,1),(1,-1,1,1),(1,1,0,1),(1,1,1,-1),(True,1,1,1),(1,1,1,1.0)]:
        try:capacity(*args)
        except ValueError:invalid+=1
        else:raise ValueError('invalid capacity accepted')
    for alt in ((),((0,1),),((0,1),(0,2)),((False,1),(0,1))):
        try:lottery(alt)
        except ValueError:invalid+=1
        else:raise ValueError('invalid lottery accepted')
    require(before=={p:digest(root/p) for p in FILES},'runtime changed')
    summary={'chapter':'v17-c02','status':'passed','runtime_files':6,'worked_lessons':2,'exact_solutions':8,'visible_tables':7,'result_groups':len(expected),'comparisons':count,'binary_four_bank_schedules':256,'invalid_domains':invalid,'scope':'Independent complete prose/proof review and visible-primitive arithmetic; no observed learner outcome or human teaching certification.'}
    json.dumps(summary,allow_nan=False);return summary
if __name__=='__main__':
    require(len(sys.argv)<=2,'usage: check_v17_c02_peer_working.py [book-root]');check(sys.argv[1] if len(sys.argv)==2 else None)
