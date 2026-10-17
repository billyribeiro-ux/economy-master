"""Read-only author audit of original leadership calibration and artifact protocol."""
from pathlib import Path
from fractions import Fraction as F
from itertools import product, combinations
from hashlib import sha256
from html.parser import HTMLParser
import ast
import json
FILES=('production/leadership-portfolio-working.html','production/check_leadership_portfolio_working.py','production/leadership-portfolio-sources-working.json','production/leadership-portfolio-author-review-working.json')
def require(ok,msg):
    if not ok:raise ValueError(msg)
def strict(raw):
    def pairs(items):
        out={}
        for k,v in items:
            require(k not in out,'duplicate JSON key');out[k]=v
        return out
    def bad(v):raise ValueError('nonfinite JSON')
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=bad)
def numeric(raw):
    def go(n):
        if isinstance(n,ast.Constant) and type(n.value) in (int,float):return F(str(n.value))
        if isinstance(n,ast.Tuple):return tuple(go(x) for x in n.elts)
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,ast.USub):return -go(n.operand)
        if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Div):return go(n.left)/go(n.right)
        raise ValueError('restricted rational syntax')
    return go(ast.parse(raw.strip().replace('−','-'),mode='eval').body)
class Manuscript(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.stack=[];self.ids=[];self.results={};self.prompts={};self.answers={};self.sources={};self.tables={};self.row=None;self.cell=None;self.h1=0;self.worked=[];self.groups=[];self.links=set()
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if 'id' in a:self.ids.append(a['id'])
        if tag=='h1':self.h1+=1
        if 'data-result' in a:require(a['data-result'] not in self.results,'duplicate result');self.results[a['data-result']]=''
        if tag=='article' and 'worked' in a.get('class','').split():self.worked.append(a['id'])
        if 'data-artifact' in a:self.groups.append(a['data-artifact'])
        if tag=='li' and any(t=='ol' and 'exercises' in z.get('class','').split() for t,z in self.stack):self.prompts[a['id']]=''
        if 'data-solution-for' in a:
            require(any(t=='details' and 'solutions' in z.get('class','').split() for t,z in self.stack),'answer disclosure');require(a['data-solution-for'] not in self.answers,'duplicate answer');self.answers[a['data-solution-for']]=''
        if 'data-source' in a:self.sources[a['data-source']]=a['href']
        if tag=='a':self.links.add(a['href'])
        if tag=='table' and 'id' in a:self.tables[a['id']]=[]
        if tag=='tr':self.row=[]
        if tag in ('th','td'):self.cell=''
        if tag not in ('br','hr','img','input','meta','link'):self.stack.append((tag,a))
    def handle_data(self,data):
        if self.cell is not None:self.cell+=data
        for tag,a in self.stack:
            if 'data-result' in a:self.results[a['data-result']]+=data
            if tag=='li' and a.get('id') in self.prompts:self.prompts[a['id']]+=data
            if 'data-solution-for' in a:self.answers[a['data-solution-for']]+=data
    def handle_endtag(self,tag):
        require(self.stack and self.stack[-1][0]==tag,'HTML nesting '+tag)
        if tag in ('th','td'):self.row.append(self.cell);self.cell=None
        if tag=='tr':
            tab=next((a.get('id') for t,a in reversed(self.stack) if t=='table'),None)
            if tab in self.tables:self.tables[tab].append(self.row)
            self.row=None
        self.stack.pop()
def selection(cost,hours,score,budget,capacity,grant=0):
    require(len(cost)==len(hours)==len(score)==3,'three options')
    cost,hours,score=tuple(map(F,cost)),tuple(map(F,hours)),tuple(map(F,score));budget,capacity,grant=map(F,(budget,capacity,grant))
    require(min((*cost,*hours,*score,budget,capacity,grant))>=0 and grant<=cost[0],'nonnegative resources and eligible grant')
    feasible=[]
    for bits in product((0,1),repeat=3):
        c=sum(x*y for x,y in zip(cost,bits))-grant*bits[0];h=sum(x*y for x,y in zip(hours,bits));v=sum(x*y for x,y in zip(score,bits))
        if c<=budget and h<=capacity:feasible.append((bits,c,h,v))
    best=max(x[3] for x in feasible);return feasible,[x for x in feasible if x[3]==best]
def ledger(opening,events):
    require(len(opening)==5 and all(len(e)==5 for e in events),'five accounts')
    state=tuple(map(F,opening));require(min(state)>=0 and sum(state[:3])==sum(state[3:]),'balanced nonnegative opening')
    rows=[state]
    for e in events:
        state=tuple(x+F(y) for x,y in zip(state,e));require(sum(state[:3])==sum(state[3:]),'balanced event');require(min(state)>=0,'nonnegative recorded accounts');rows.append(state)
    return rows
def schedule(A=4,B=4,rx=8,ry=6):
    A,B,rx,ry=map(F,(A,B,rx,ry));require(A>=0 and B>=0 and rx>0 and ry>0,'capacity/positive targets')
    # Independent vertex oracle for the rectangle split by equal target ratios.
    candidates={(F(0),F(0)),(A,F(0)),(F(0),B),(A,B)}
    # (3ry+rx)t+(ry+2rx)u=rx(A+2B)
    at=3*ry+rx;au=ry+2*rx;rhs=rx*(A+2*B)
    for t in (F(0),A):
        u=(rhs-at*t)/au
        if 0<=u<=B:candidates.add((t,u))
    for u in (F(0),B):
        t=(rhs-au*u)/at
        if 0<=t<=A:candidates.add((t,u))
    rows=[(min((3*t+u)/rx,(A-t+2*(B-u))/ry),t,u,3*t+u,A-t+2*(B-u)) for t,u in candidates]
    z=max(x[0] for x in rows);return z,sorted(x for x in rows if x[0]==z)
def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    payload={p:(root/p).read_bytes() for p in FILES};author=strict(payload[FILES[3]]);sources=strict(payload[FILES[2]])
    require(set(author['payloads'])==set(FILES[:3]),'exact three nonself hashes')
    for p in FILES[:3]:require(author['payloads'][p]=={'bytes':len(payload[p]),'sha256':sha256(payload[p]).hexdigest()},'changed payload '+p)
    m=Manuscript();m.feed(payload[FILES[0]].decode());require(not m.stack and m.h1==1 and len(m.ids)==len(set(m.ids)),'structure')
    require(len(m.worked)==3 and len(m.groups)==6 and len(m.prompts)==9 and set(m.prompts)==set(m.answers),'full cases/artifacts/paired tasks')
    require(all(f'leadership-form-{x}' in m.tables for x in ('role','claim','resource','observer','response','defense')),'six operational forms')
    require(m.sources=={x['id']:x['url'] for x in sources['sources']},'exact source routes')
    require(all(f'v18-c{i:02}.html' in m.links for i in range(1,13)) and all(f'v{x:02}-assessment.html' in m.links for x in (7,8,11,16,17,18)),'all prerequisite/capability routes')
    comparisons=0
    def eq(a,b,label):
        nonlocal comparisons
        require(a==b,label);comparisons+=1
    rows=m.tables['leadership-options'][1:];cost=[F(x[1]) for x in rows];hours=[F(x[2]) for x in rows];score=[F(x[3]) for x in rows]
    eq((cost,hours,score),([6,4,5],[4,5,3],[9,8,7]),'actual option primitives')
    f,best=selection(cost,hours,score,10,8);fg,bg=selection(cost,hours,score,10,8,2)
    eq([x[0] for x in f],[(0,0,0),(0,0,1),(0,1,0),(0,1,1),(1,0,0)],'exhaustive feasible menu')
    eq(numeric(m.results['case1']),(best[0][1:],(*bg[0][1:],8-bg[0][2])),'case1 full result')
    eventrows=m.tables['leadership-finance-events'][1:];events=[]
    for row in eventrows:events.append((F(row[1]),F(row[2]),F(0),F(row[3]),F(row[4])))
    actual=ledger((18,0,82,85,15),events);eq(numeric(m.results['case2-ledgers']),tuple(actual[:5]),'all actual balance sheets');eq(actual[-1],actual[-2],'promise zero')
    final=actual[-1];gap=max(F(0),6-final[0]);repaired=ledger(final,[(gap,0,0,0,gap)])[-1]
    staged=ledger((18,0,82,85,15),[(-5,5,0,0,0),events[1],events[2],events[3]])[-1]
    eq(numeric(m.results['case2-repair']),(gap,repaired,staged,3),'funded and staged repair')
    z,plans=schedule();eq(len(plans),1,'unique original maximum');_,t,u,x,y=plans[0]
    eq(numeric(m.results['case3']),((12,8,F(3,2),F(4,3),F(4,3)),(t,u,x,y,z),z-F(4,3)),'full original schedule')
    z1,p1=schedule(B=3);_,t1,u1,x1,y1=p1[0];z2,p2=schedule(rx=6,ry=6);_,t2,u2,x2,y2=p2[0]
    eq(numeric(m.results['case3-transfer']),((t1,u1,x1,y1,z1,7),(t2,u2,x2,y2,z2)),'changed schedules')
    _,bd=selection(cost,hours,score,11,8);eq(numeric(m.results['defense1']),(*bd[0][1:],8-bd[0][2]),'budget defense')
    partial=ledger(final,[(2,0,0,0,2)])[-1];eq(numeric(m.results['defense2']),(partial,6-partial[0]),'partial equity defense')
    eq(set(m.results),{'case1','case2-ledgers','case2-repair','case3','case3-transfer','defense1','defense2'},'all numerical groups')
    # Changed budgets/capacity and a separately enumerated bitmask reference.
    worlds=0
    for budget,cap,g in product((0,4,9,10,11,15),(0,3,7,8,12),(0,2,6)):
        fs,bs=selection(cost,hours,score,budget,cap,g);reference=[]
        for mask in range(8):
            chosen=[i for i in range(3) if mask&(1<<i)];c=sum(cost[i] for i in chosen)-(g if 0 in chosen else 0);h=sum(hours[i] for i in chosen);v=sum(score[i] for i in chosen)
            if c<=budget and h<=cap:reference.append((c,h,v))
        eq(max(x[3] for x in bs),max(x[2] for x in reference),'changed selection optimum');eq(len(fs),len(reference),'changed feasible inventory');worlds+=1
    schedworlds=0
    for A,B,rx,ry in product((0,2,4),(0,3,4),(6,8),(4,6)):
        zz,pp=schedule(A,B,rx,ry)
        for _,tt,uu,xx,yy in pp:
            eq(xx,3*tt+uu,'schedule production X');eq(yy,A-tt+2*(B-uu),'schedule production Y');require(0<=tt<=A and 0<=uu<=B,'capacity bounds')
        # Both general resource upper bounds hold for every candidate optimum.
        require((rx+3*ry)*zz<=3*A+6*B and (2*rx+ry)*zz<=6*A+2*B,'global linear resource bounds')
        for tt,uu in product((F(0),F(A,2),F(A)),(F(0),F(B,2),F(B))):require(min((3*tt+uu)/rx,(A-tt+2*(B-uu))/ry)<=zz,'feasible witness not better')
        schedworlds+=1
    fundingworlds=0
    for e in range(7):
        rr=ledger(final,[(e,0,0,0,e)])[-1];eq(rr[0]>=6,e>=3,'receipt threshold');eq(sum(rr[:3]),sum(rr[3:]),'actual equity balance');fundingworlds+=1
    invalid=[lambda:selection([1],hours,score,10,8),lambda:selection(cost,hours,score,-1,8),lambda:selection(cost,hours,score,10,-1),lambda:selection(cost,hours,score,10,8,7),lambda:selection(cost,hours,score,10,8,-1),lambda:ledger((18,0,82,85,14),[]),lambda:ledger((18,0,82,85,15),[(1,0,0,0,0)]),lambda:ledger((18,0,82,85,15),[(-19,19,0,0,0)]),lambda:ledger((18,0),[]),lambda:schedule(A=-1),lambda:schedule(B=-1),lambda:schedule(rx=0),lambda:schedule(ry=-1),lambda:numeric('__import__("os")'),lambda:strict('{"a":1,"a":2}')]
    for call in invalid:
        try:call()
        except (ValueError,ZeroDivisionError):continue
        raise ValueError('invalid domain accepted')
    result={'assessment':'leadership-portfolio','status':'passed','runtime_files':4,'comparisons':comparisons,'selection_worlds':worlds,'schedule_worlds':schedworlds,'funding_worlds':fundingworlds,'invalid_domains':len(invalid),'cases':3,'complete_task_answers':9,'artifact_groups':6,'forms':6,'scope':'Original complete synthetic calibration and actual-work protocol; actual learner evidence and human evaluation remain required.'}
    json.dumps(result,allow_nan=False);return result
if __name__=='__main__':check()
