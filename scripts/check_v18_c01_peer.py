"""Independent primitive audit; author checker is an opaque hash-bound payload."""
import ast, hashlib, json, sys
from fractions import Fraction as Q
from html.parser import HTMLParser
from itertools import product
from pathlib import Path
FILES=('content/chapters/v18-c01.html','scripts/check_v18_c01.py','content/reviews/v18-c01-sources.json','content/reviews/v18-c01-author.json','scripts/check_v18_c01_peer.py','content/reviews/v18-c01-peer.json')
def require(x,msg):
    if not x:raise ValueError('C01 peer: '+msg)
def strict(text):
    def pairs(items):
        d={}
        for k,v in items:
            require(k not in d,'duplicate JSON key');d[k]=v
        return d
    def reject(x):raise ValueError('nonfinite JSON')
    return json.loads(text,object_pairs_hook=pairs,parse_constant=reject)
def rational(text):
    def visit(n):
        if isinstance(n,ast.Tuple):return tuple(visit(x) for x in n.elts)
        if isinstance(n,ast.Constant) and type(n.value) is int:return Q(n.value)
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,ast.USub):return -visit(n.operand)
        if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Div):return visit(n.left)/visit(n.right)
        raise ValueError('unsupported exact literal')
    return visit(ast.parse(text.strip(),mode='eval').body)
class Reader(HTMLParser):
    def __init__(self):
        super().__init__();self.stack=[];self.ids=[];self.tasks=[];self.answers=[];self.worked=[];self.sources=[];self.numbers={};self.active=None;self.tables={};self.table=None;self.row=None;self.cell=None
    def handle_starttag(self,t,attrs):
        a=dict(attrs);require(len(a)==len(attrs),'duplicate attrs');require(t!='h1','chapter h1')
        if 'id' in a:self.ids.append(a['id'])
        if t=='article' and 'worked' in a.get('class','').split():self.worked.append(a['id'])
        if t=='li' and any(z=='ol' and 'exercises' in d.get('class','').split() for z,d in self.stack):self.tasks.append(a['id'])
        if 'data-solution-for' in a:
            require(any(z=='details' and 'solutions' in d.get('class','').split() for z,d in self.stack),'answer disclosure');self.answers.append(a['data-solution-for'])
        if 'data-source' in a:self.sources.append((a['data-source'],a['href']))
        for kind in ('input','result'):
            if 'data-'+kind in a:
                key=(kind,a['data-'+kind]);require(key not in self.numbers and self.active is None,'numeric marker');self.active=(t,key);self.numbers[key]=''
        if t=='table':self.table=a.get('id','anonymous-'+str(len(self.tables)));self.tables[self.table]=[]
        if t=='tr':self.row=[]
        if t in ('th','td'):self.cell=[]
        if t not in ('br','hr','img','input','meta','link'):self.stack.append((t,a))
    def handle_data(self,s):
        if self.active:self.numbers[self.active[1]]+=s
        if self.cell is not None:self.cell.append(s)
    def handle_endtag(self,t):
        require(bool(self.stack) and self.stack.pop()[0]==t,'balanced fragment')
        if self.active and self.active[0]==t:self.active=None
        if t in ('th','td'):self.row.append(''.join(self.cell).strip());self.cell=None
        if t=='tr':self.tables[self.table].append(self.row);self.row=None
        if t=='table':self.table=None

def exact(x,n):
    require(isinstance(x,(tuple,list)) and len(x)==n,'input dimension');require(all(type(v) in (int,Q) for v in x),'exact finite inputs');return tuple(Q(v) for v in x)
def portfolios(modules,resources,studio=0):
    cash,floor,hours,priority=exact(resources,4);require(min(cash,floor,hours,priority,studio)>=0,'resource domain')
    require(len(modules)==3,'module count');modules=tuple(exact(row,5) for row in modules);require(all(min(row)>=0 for row in modules),'module domain')
    rows={}
    for bits in product((0,1),repeat=3):
        values=tuple(sum((row[j]*b for row,b in zip(modules,bits)),Q(0)) for j in range(5))
        eligible=values[0]<=cash-floor and values[1]<=hours and values[3]>=priority and values[4]>=studio
        rows[bits]=(values,eligible)
    feasible=[(bits,row[0]) for bits,row in rows.items() if row[1]]
    best=max((row[2] for bits,row in feasible),default=None)
    return rows,tuple(bits for bits,row in feasible if row[2]==best)
def ledger(resources,plan):
    cash,loans,deposits,equity,cf,ef,priority=exact(resources,7);c,w,l,total,target,income=exact(plan,6)
    require(min(cash,loans,deposits,equity,cf,ef,priority,c,w,l,total,target)>=0 and target<=total,'bank domain')
    require(cash+loans==deposits+equity and l<=loans and w<=deposits,'opening identity and accounting domain')
    # Independent transaction-vector reconstruction, preserving each stage.
    balance=(cash,loans,deposits,equity);stages=[balance]
    for transaction in ((-c,0,0,-c),(-w,0,-w,0),(0,-l,0,-l)):
        balance=tuple(a+b for a,b in zip(balance,transaction));stages.append(balance)
    eligible=balance[0]>=cf and balance[3]>=ef and target>=priority and income>0
    return balance,eligible,stages

def check(root=None):
    root=Path(root).resolve() if root is not None else Path(__file__).resolve().parents[1];review=strict((root/FILES[5]).read_text())
    require(review['full_reading_complete'] and not review['open_material_findings'],'manual review');require(set(review['payloads'])==set(FILES[:5]),'five bindings')
    for name,d in review['payloads'].items():
        b=(root/name).read_bytes();require(d=={'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()},'freeze '+name)
    author=strict((root/FILES[3]).read_text());sources=strict((root/FILES[2]).read_text())['sources'];require(not author['open_material_findings'],'author findings')
    p=Reader();p.feed((root/FILES[0]).read_text());p.close();require(not p.stack and p.active is None and len(p.ids)==len(set(p.ids)),'fragment');require(p.tasks==p.answers==['v18-c01-ex'+str(i) for i in range(1,9)],'eight paired solutions');require(p.worked==['v18-c01-case1','v18-c01-case2'],'two cases');require(set(p.sources)=={(s['id'],s['url']) for s in sources},'source URLs')
    marks={k:rational(v) for k,v in p.numbers.items()};used=set();count=0
    def eq(a,b,label):
        nonlocal count
        if isinstance(a,tuple) or isinstance(b,tuple):
            require(isinstance(a,tuple) and isinstance(b,tuple) and len(a)==len(b),'shape '+label)
            for x,y in zip(a,b):eq(x,y,label)
        else:count+=1;require(a==b,label)
    def read(kind,key):used.add((kind,key));return marks[kind,key]
    def result(key,v):eq(read('result',key),v,key)
    modules=tuple(tuple(Q(x) for x in row[1:]) for row in p.tables['v18-c01-modules'][1:]);eq(modules,((40,400,24,16,0),(50,300,12,4,12),(30,200,18,2,0)),'visible module primitives')
    resources=read('input','academic-resources');rows,optimal=portfolios(modules,resources);eq(optimal,((1,0,1),),'academic maximizer')
    codes={'None':(0,0,0),'B':(1,0,0),'R':(0,1,0),'E':(0,0,1),'B+R':(1,1,0),'B+E':(1,0,1),'R+E':(0,1,1),'B+R+E':(1,1,1)}
    table=p.tables['v18-c01-portfolios'][1:];require(len(table)==8 and {r[0] for r in table}==set(codes),'complete visible menu')
    for row in table:eq(tuple(Q(x) for x in row[1:5]),rows[codes[row[0]]][0][:4],'visible portfolio sum')
    chosen=rows[optimal[0]][0];result('academic-choice',chosen[:4]+(resources[0]-chosen[0],resources[0]-resources[1]-chosen[0]))
    n,success,fail,missing=42,30,7,5;eq(success+fail+missing,n,'outcome reconciliation');rates=tuple(Q(success+k,n) for k in range(missing+1));result('academic-evidence',(Q(success,success+fail),rates[0],rates[-1]));result('academic-rate-set',rates)
    changed=((Q(51),)+modules[0][1:],)+modules[1:];r,o=portfolios(changed,resources);eq(o,((1,0,0),),'quote51 optimum');v=r[o[0]][0];result('academic-cost-change',v[:4]+(90-v[0],80-v[0],600-v[1]))
    r,o=portfolios(modules,(100,10,700,12),12);eq(o,((1,1,0),),'expanded optimum');result('academic-expanded',r[o[0]][0]+(100-r[o[0]][0][0],))
    for res in (resources,(100,10,600,12),(90,10,700,12)):eq(portfolios(modules,res,12)[1],(),'single resource cannot fix')
    plans=tuple(tuple(Q(x) for x in row[1:]) for row in p.tables['v18-c01-bank-plans'][1:]);bank=read('input','bank-resources');eq(plans,((0,20,5,0,0,2),(6,35,7,80,48,4),(10,30,6,120,24,5),(4,50,12,150,60,6)),'visible plan primitives')
    balances=[ledger(bank,plan) for plan in plans];eq(tuple(i for i,b in enumerate(balances) if b[1]),(1,),'unique eligible channel')
    for row,b in zip(p.tables['v18-c01-bank-balances'][1:],balances):eq(tuple(Q(x) for x in row[1:5]),b[0],'visible bank ledger')
    C,N,D,E=balances[1][0];result('bank-choice',(C,E,C-bank[4],E-bank[5],plans[1][4]));result('bank-thresholds',(bank[0]-plans[1][0]-bank[4],bank[3]-plans[1][0]-bank[5],bank[0]-plans[3][0]-bank[4],10,11))
    revised=(plans[3][0],Q(45))+plans[3][2:];b,eligible,_=ledger(bank,revised);eq(eligible,True,'broker revised eligible');eq(revised[4]>plans[1][4],True,'broker revised selected');result('broker-revision',b+(b[0]+b[1],revised[4]))
    revised=(Q(12),)+plans[1][1:];b,eligible,_=ledger(bank,revised);eq(eligible,False,'relationship revised fails');result('relationship-cost-change',(b[0],b[3],b[0]-bank[4],b[3]-bank[5]));eq(balances[2][0][0]+balances[2][0][3],34,'wrong buffer arithmetic')
    r,o=portfolios(((Q(49),)+modules[0][1:],)+modules[1:],resources);v=r[o[0]][0];result('academic-review',(v[0],90-v[0],80-v[0]))
    r,o=portfolios(((Q(50),)+modules[0][1:],)+modules[1:],resources);v=r[o[0]][0];b=ledger(bank,plans[1][:2]+(Q(12),)+plans[1][3:])[0];beyond=ledger(bank,plans[1][:2]+(Q(13),)+plans[1][3:])[0];result('retention-boundaries',(v[0],90-v[0],b[0],b[3],beyond[3]))
    academic_worlds=0
    for cost,hours,cash in product((40,50,51,81),(600,700),(90,100)):
        ms=((Q(cost),)+modules[0][1:],)+modules[1:];res=(cash,10,hours,12);r,o=portfolios(ms,res)
        eligible=[(bits,v) for bits,(v,ok) in r.items() if ok]
        for bits in o:
            v=r[bits][0];eq(all(v[2]>=other[2] for _,other in eligible),True,'global finite comparison')
        eq(bool(o),bool(eligible),'empty versus maximizer');academic_worlds+=1
    # Independent threshold and identity witnesses over cash/equity boundaries.
    bank_worlds=0
    for c,w,l in product((0,6,12),(35,44,45),(7,12,13)):
        plan=(c,w,l,80,48,4);b,ok,stages=ledger(bank,plan)
        for a,n,d,e in stages:eq(a+n,d+e,'every transaction balances')
        eq(ok,c+w<=50 and c+l<=18,'separate linear screens');eq(b[0],min(s[0] for s in stages),'cash timing');eq(b[3],min(s[3] for s in stages),'equity timing');bank_worlds+=1
    # A genuine tie, an empty menu, and zero positive-income screen.
    tie=((1,1,1,1,0),(1,1,1,1,0),(9,9,0,0,0));eq(portfolios(tie,(1,0,1,1))[1],((0,1,0),(1,0,0)),'multiple maximizers');eq(portfolios(modules,(0,10,600,12))[1],(),'cash below reserve infeasible');eq(ledger(bank,(0,20,5,80,48,0))[1],False,'income screen zero')
    invalid=0
    for f in (lambda:portfolios(modules,(-1,0,1,0)),lambda:portfolios(modules,(1,0,-1,0)),lambda:portfolios(modules[:2],resources),lambda:portfolios(((-1,1,1,1,0),)+modules[1:],resources),lambda:ledger((60,140,170,31,10,12,40),plans[1]),lambda:ledger(bank,(6,171,7,80,48,4)),lambda:ledger(bank,(6,35,141,80,48,4)),lambda:ledger(bank,(-1,35,7,80,48,4)),lambda:ledger(bank,(6,35,7,40,48,4)),lambda:exact((True,),1),lambda:strict('{"a":1,"a":2}'),lambda:strict('{"a":NaN}'),lambda:rational('x()')):
        try:f()
        except (ValueError,TypeError):invalid+=1
        else:raise ValueError('invalid accepted')
    require(used==set(marks),'every numerical marker covered')
    return {'chapter':'v18-c01','status':'passed','runtime_files':6,'comparisons':count,'academic_worlds':academic_worlds,'bank_worlds':bank_worlds,'invalid_domains':invalid,'scope':'Both complete strategy cases, eight full answers, proofs, boundaries and bounded source scopes independently reviewed; author checker opaque.'}
if __name__=='__main__':
    require(len(sys.argv)<=2,'usage peer [root]');check(sys.argv[1] if len(sys.argv)==2 else None)
