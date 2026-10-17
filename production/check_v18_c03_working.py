"""V18 C03 author arithmetic, incentive domains and frozen payloads."""
from pathlib import Path
from fractions import Fraction as F
from html.parser import HTMLParser
from hashlib import sha256
import ast,json
def strict(s):
    def pairs(xs):
        out={}
        for k,v in xs:
            if k in out:raise ValueError("duplicate JSON key")
            out[k]=v
        return out
    return json.loads(s,object_pairs_hook=pairs,parse_constant=lambda x:(_ for _ in ()).throw(ValueError("nonfinite")))
FILES=('production/v18-c03-working.html','production/check_v18_c03_working.py','production/v18-c03-sources-working.json','production/v18-c03-author-review-working.json')
def require(ok, message):
    if not ok:
        raise ValueError(message)

def number(text):
    def walk(n):
        if isinstance(n, ast.Constant) and type(n.value) is int: return F(n.value)
        if isinstance(n, (ast.Tuple, ast.List)): return tuple(walk(x) for x in n.elts)
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.USub): return -walk(n.operand)
        if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Div): return walk(n.left)/walk(n.right)
        raise ValueError('numeric grammar')
    return walk(ast.parse(text, mode='eval').body)

class Reader(HTMLParser):
    def __init__(self):
        super().__init__(); self.markers={}; self.active=None; self.ids=[]; self.solutions=[]; self.sources={}; self.maps={k:[] for k in ('data-artifact','data-prerequisite','data-chapter')}
    def handle_starttag(self, tag, attrs):
        d=dict(attrs)
        if 'id' in d:self.ids.append(d['id'])
        if 'data-solution-for' in d:self.solutions.append(d['data-solution-for'])
        if 'data-source' in d:self.sources[d['data-source']]=d['href']
        for k in self.maps:
            if k in d:self.maps[k].append(d[k])
        for kind in ('data-input','data-result'):
            if kind in d:
                require(d[kind] not in self.markers,'duplicate numeric marker');self.active=d[kind];self.markers[self.active]=''
    def handle_data(self, data):
        if self.active:self.markers[self.active]+=data
    def handle_endtag(self, tag):
        if tag=='span':self.active=None


def task(b,quality=F(3)):
    b,quality=F(b),F(quality);require(b>=0 and quality>=0,'task domain')
    if b<=F(1,2):e,q=b,F(1,2)
    elif b<F(3,2):e,q=(b+F(1,2))/2,(F(3,2)-b)/2
    else:e,q=F(1),F(0)
    wage=b*e;gross=e+quality*q;utility=wage+q/2-(e*e+q*q)/2
    return e,q,wage,gross,gross-wage,utility

def delegate(alpha,d,p=F(1,2),tie=True):
    alpha,d,p=F(alpha),F(d),F(p);require(0<=alpha<=1 and d>=0 and 0<=p<=1 and type(tie) is bool,'delegation domain')
    take_large=(12*alpha>1 or (12*alpha==1 and tie))
    high=F(20) if take_large else F(8);gross=p*high+(1-p)*8;wage=alpha*gross;effort=p if take_large else F(0)
    return gross,wage,wage-effort,gross-wage-d

def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    rec=strict((root/FILES[3]).read_text());require(set(rec['payloads'])==set(FILES[:3]),'three nonself hashes')
    for name,v in rec['payloads'].items():
        raw=(root/name).read_bytes();require(len(raw)==v['bytes'] and sha256(raw).hexdigest()==v['sha256'],'changed '+name)
    page=Reader();page.feed((root/FILES[0]).read_text());m={k:number(v) for k,v in page.markers.items()};count=0
    def eq(a,b,label):
        nonlocal count
        require(a==b,label);count+=1
    eq(len(page.ids),len(set(page.ids)),'unique ids');eq(page.solutions,[f'v18-c03-e{i}' for i in range(1,9)],'eight complete solutions');eq(page.sources,{s['id']:s['url'] for s in strict((root/FILES[2]).read_text())['sources']},'source routes')
    eq(m['tasks'],(3,F(1,2),1),'task primitives');eq(m['delegation'],(F(1,2),8,20,-12,1,2),'delegation primitives')
    rows=tuple((b,*task(b)[:5]) for b in (F(0),F(1,2),F(1),F(3,2),F(2)));eq(rows,m['task-rows'],'full task table')
    t=task(F(1,2));eq((F(1,2),t[0],t[1],t[4],t[5]),m['task-optimum'],'optimal contract');eq(task(F(1)),m['e1'],'full e1')
    eq((F(1,2),task(F(1,2),1)[4]),m['e3'],'changed objective')
    eq((8,F(20-12,2),F(20-12,2)-2),m['delegation-baselines'],'baseline')
    eq((F(1,12),*delegate(F(1,12),2)),m['delegation-contract'],'full delegated ledger')
    eq((F(77,6),F(77,6)-8,F(77,6)-2-8),m['audit-boundary'],'audit boundary')
    out=delegate(F(1,10),2);eq((F(1,10),out[-1],out[-2]),m['strict-contract'],'strict implementation')
    out=delegate(F(1,12),5);eq((out[-1],8,out[-1]-8),m['e5'],'audit5')
    out=delegate(F(1,12),2,F(1,4));eq((out[-1],8,F(1,4)*20-F(3,4)*12,out[-1]-8),m['e6'],'changed state')
    # Independent candidate verification by gradient inequality and direct objective comparison.
    task_worlds=0
    for j in range(25):
        bonus=F(j,8);e,q,_,_,net,u=task(bonus)
        eq(e>=0 and q>=0 and e+q<=1,True,'feasible')
        for x in range(9):
            for y in range(9-x):
                ee,qq=F(x,8),F(y,8);eq(u>=bonus*ee+qq/2-(ee*ee+qq*qq)/2,True,'global agent witness');eq((bonus-e)*(ee-e)+(F(1,2)-q)*(qq-q)<=0,True,'supporting gradient')
        for quality in (F(1),F(3)):eq(task(F(1,2),quality)[4]>=task(bonus,quality)[4],True,'global principal witness')
        task_worlds+=1
    delegation_worlds=0
    for p in (F(0),F(1,4),F(1,2),F(1)):
        for d in (F(0),F(2),F(29,6),F(5)):
            chosen=delegate(F(1,12),d,p)
            eq(chosen[-1],F(22,3)+11*p-d,'general distribution ledger')
            for a in (F(0),F(1,24),F(1,12),F(1,10),F(1,2),F(1)):
                r=delegate(a,d,p);eq(r[0]-r[1]-d,r[-1],'principal reconciliation');eq(r[2]>=0,True,'IR')
                eq((20*a-1>=8*a),(a>=F(1,12)),'high IC threshold');eq(8*a>-1,True,'down strict IC');delegation_worlds+=1
    eq(delegate(F(1,12),2,tie=False)[0],8,'tie failure');eq(delegate(F(1,12),F(29,6))[-1],8,'audit tie');eq(task(F(3,2))[4],F(-1,2),'retention')
    bad=[lambda:task(-1),lambda:task(1,-1),lambda:delegate(-1,2),lambda:delegate(2,2),lambda:delegate(0,-1),lambda:delegate(0,2,-1),lambda:delegate(0,2,2),lambda:delegate(0,2,tie=1),lambda:strict('{"x":1,"x":2}'),lambda:strict('{"x":NaN}')]
    for f in bad:
        try:f()
        except ValueError:pass
        else:raise ValueError('invalid domain accepted')
    return {'chapter':'v18-c03','status':'passed','comparisons':count,'task_worlds':task_worlds,'delegation_worlds':delegation_worlds,'numeric_markers':len(m),'invalid_domains':len(bad),'runtime_files':4,'scope':'Complete manual two-case/eight-answer/global proof review; no actual workforce response or institutional authorization certified.'}
if __name__=='__main__':check()
