"""C02 exact budgeting oracle: dated stock-flow transactions and incremental project cash."""
from pathlib import Path
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
import ast
import json
FILES=('production/v18-c02-working.html','production/check_v18_c02_working.py','production/v18-c02-sources-working.json','production/v18-c02-author-review-working.json')
def require(ok,message):
    if not ok: raise ValueError(message)


def numeric(text):
    text=text.rsplit('=',1)[-1].strip().replace('−','-')
    def walk(node):
        if isinstance(node,ast.Constant) and type(node.value) in (int,float):return F(str(node.value))
        if isinstance(node,ast.Tuple):return tuple(walk(x) for x in node.elts)
        if isinstance(node,ast.UnaryOp) and isinstance(node.op,ast.USub):return -walk(node.operand)
        if isinstance(node,ast.BinOp) and isinstance(node.op,ast.Div):return walk(node.left)/walk(node.right)
        raise ValueError('restricted rational syntax')
    return walk(ast.parse(text,mode='eval').body)


class BaseManuscript(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack=[];self.ids=[];self.inputs={};self.results={};self.prompts={};self.solutions={};self.sources={};self.worked=[];self.rows=[];self.row=None;self.cell=None;self.links=set();self.guides=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if 'id' in a:self.ids.append(a['id'])
        if tag=='h1':raise ValueError('chapter fragment cannot contain h1')
        for attr,dest in (('data-input',self.inputs),('data-result',self.results)):
            if attr in a:require(a[attr] not in dest,'duplicate marker');dest[a[attr]]=''
        if tag=='article' and 'worked' in a.get('class','').split():self.worked.append(a['id'])
        if tag=='li' and any(t=='ol' and 'exercises' in x.get('class','').split() for t,x in self.stack):self.prompts[a['id']]=''
        if 'data-solution-for' in a:
            require(any(t=='details' and 'solutions' in x.get('class','').split() for t,x in self.stack),'solution disclosure')
            require(a['data-solution-for'] not in self.solutions,'unique solution');self.solutions[a['data-solution-for']]=''
        if 'data-source' in a:require(a['data-source'] not in self.sources,'unique source');self.sources[a['data-source']]=a['href']
        if tag=='a':self.links.add(a['href'])
        if tag=='tr':self.row=[]
        if tag in ('td','th'):self.cell=''
        if tag not in ('br','hr','img'):self.stack.append((tag,a))
    def handle_data(self,text):
        if self.cell is not None:self.cell+=text
        for tag,a in self.stack:
            if 'data-input' in a:self.inputs[a['data-input']]+=text
            if 'data-result' in a:self.results[a['data-result']]+=text
            if tag=='li' and a.get('id') in self.prompts:self.prompts[a['id']]+=text
            if 'data-solution-for' in a:self.solutions[a['data-solution-for']]+=text
    def handle_endtag(self,tag):
        require(self.stack and self.stack[-1][0]==tag,'HTML nesting')
        if tag in ('td','th'):self.row.append(self.cell);self.cell=None
        if tag=='tr':self.rows.append(self.row);self.row=None
        self.stack.pop()


def strict_json(raw):
    def pairs(items):
        out={}
        for k,v in items:
            require(k not in out,'duplicate JSON key');out[k]=v
        return out
    def bad(v):raise ValueError('nonfinite JSON')
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=bad)


def npv(cost,annual,years,rate=F(1,10)):
    cost,annual,rate=map(F,(cost,annual,rate))
    require(cost>=0 and type(years) is int and years>0 and rate>-1,'capital cash domain')
    return -cost+sum((annual/(1+rate)**i for i in range(1,years+1)),F(0))


def draw(opening,ret,cap=8,floor=190):
    opening,ret,cap,floor=map(F,(opening,ret,cap,floor))
    require(opening>=0 and cap>=0 and floor>=0 and opening+ret>=0,'investment domain')
    payout=min(cap,max(F(0),opening+ret-floor))
    return payout,opening+ret-payout


def academic(cost=24,gross=16,delay=0,ret=10,active=True):
    cost,gross,delay,ret=map(F,(cost,gross,delay,ret))
    require(cost>=0 and gross>=0 and 0<=delay<=40 and type(active) is bool,'academic domain')
    require(active or cost==gross==0,'no asset means no capital cost/service receipts')
    payout,pool=draw(200,ret)
    u=F(60);restricted=F(30);equipment=F(40)
    u-=cost;equipment+=cost;cash=[u]
    u+=40-delay;u-=50;restricted-=12;cash.append(u)
    revenue2=58+gross if active else F(60)
    u+=revenue2+delay+payout;u-=50;restricted-=12;cash.append(u)
    depreciation=8+cost/2;equipment-=depreciation
    revenue=40+revenue2;operating=revenue-124-depreciation;movement=operating+ret
    assets=u+restricted+pool+equipment
    require(assets==330+movement,'academic stock flow reconciliation')
    unrestricted=100+revenue+payout-100-depreciation
    require(unrestricted+restricted+pool==assets,'three subfund bridge')
    return tuple(cash),restricted,payout,pool,equipment,operating,movement,assets,unrestricted


def lender(stress=False,funding=0,new=20,system=True,early=False):
    f,x=map(F,(funding,new));require(f>=0 and 0<=x<=20,'authorized funding/lending domain')
    require(all(type(v) is bool for v in (stress,system,early)),'declared scenario flags')
    cash=F(50)+f;gross=F(160);allowance=F(8);equipment=F(18);deposits=F(180);equity=F(40)+f
    cap=12 if system else 0;expense=8 if system else 13;dep=6 if system else 2
    withdrawal=35 if stress else 25;collected=12 if stress else 16;provision=10 if stress else 6
    cash-=cap;equipment+=cap;checkpoints=[cash]
    if early:cash+=20;gross-=20;checkpoints.append(cash)
    cash-=withdrawal;deposits-=withdrawal;checkpoints.append(cash)
    if not early:cash+=20;gross-=20
    cash-=x;gross+=x;checkpoints.append(cash)
    cash+=collected;cash-=5;cash-=expense;checkpoints.append(cash)
    receivable=20-collected;allowance+=provision;equipment-=dep
    profit=20-5-expense-provision-dep;equity+=profit
    assets=cash+gross-allowance+equipment+receivable
    require(assets==deposits+equity,'lender stock-flow reconciliation')
    return tuple(checkpoints),profit,equity,gross,allowance,gross-allowance,equipment,receivable,deposits,assets


def audit(d):
    count=0
    def eq(a,b,label):
        nonlocal count
        require(a==b,label);count+=1
    def yes(ok,label):
        nonlocal count
        require(ok,label);count+=1
    inp={k:numeric(v) for k,v in d.inputs.items()}
    eq(inp,{'academic-opening':(60,30,200,40,0),'academic-projects':((24,16,2,2),(36,22,2,2)),'lender-opening':(50,160,8,18,180,40),'lender-capital':(12,5,3,F(1,10))},'actual input tuples')
    a=academic();ast=academic(delay=20,ret=-10);fallback=academic(cost=0,gross=0,delay=20,ret=-10,active=False)
    b=lender();bs=lender(stress=True);br=lender(stress=True,funding=7,new=19);bad=lender(stress=True,funding=1,new=13);early=lender(stress=True,funding=1,new=13,early=True);manual=lender(system=False)
    c0,c1,c2=b[0][0],b[0][2],b[0][3]
    want={'academic-npv':tuple(npv(c,g-r,int(n)) for c,g,r,n in inp['academic-projects']),'academic-cash':(*a[0],a[1]),'academic-position':(a[5],a[6],a[4],a[3],a[7],a[8]),'academic-stress':(ast[0][1],ast[0][2],ast[2],ast[3],20-ast[0][1]),'academic-fallback':(*fallback[0],fallback[4],fallback[7],fallback[6]),'endowment-real':(200*(F(1,20)-F(1,50)),200*(1+F(1,50)),200*(1+F(1,50))-a[3]),'lender-npv':npv(12,5,3),'lender-base':(c0,c1,c2,b[1],b[2],b[5],b[6],b[7],b[8],b[9]),'lender-stress':(bs[0][2],bs[0][3],bs[1],bs[2],bs[5],bs[7],bs[9]),'lender-repair':(7,19,*br[0],br[2],br[5],br[9]),'e1':(a[7],a[7]+a[2]),'e2':(npv(24,16,2),npv(0,2,2),npv(0,14,2),30),'e3':(10,14),'e4':tuple(draw(200,r) for r in (-20,-10,0,10)),'e5':(manual[0][-1],manual[6],manual[1],manual[2],manual[9]),'e6-failed':(*bad[0],bad[2],10-bad[0][1]),'e7':(1,13,*early[0],early[2],early[5],early[9]),'retention':(academic(delay=6)[0][1],academic(delay=7)[0][1],academic(delay=6)[0][2],*lender(stress=True,funding=8,new=20)[0],lender(stress=True,funding=8,new=20)[2])}
    eq(set(want),set(d.results),'all result groups')
    for k,v in want.items():eq(numeric(d.results[k]),v,'displayed '+k)
    rows=d.rows
    eq(tuple(tuple(numeric(x) for x in row[1:]) for row in rows if row[0] in ('None','X','Y')),((0,0,0,0,0),(24,16,2,14,12),(36,22,2,20,18)),'complete capital menu actual cells')
    eq(tuple(tuple(numeric(x) for x in row[-2:]) for row in rows if row[0] in ('Opening','Date0 after equipment','Date1 after receipts then expenses','Date2 after receipts, distribution then expenses')),((60,30),(36,30),(26,18),(58,6)),'academic actual cash table')
    eq(tuple(numeric(row[-1]) for row in rows if row[0] in ('Date0 after system','Date1 after withdrawal','Date1 after principal receipt and new loans','Date2 after interest receipts and payments')),b[0],'lender actual cash table')
    eq((a[8]-100,a[1]-30,a[3]-200),(2,-24,2),'subfund movements')
    eq((b[1]+6+6-4,b[0][-1]-50),(3,-34),'income-to-cash bridge')
    eq((b[0][-1]-manual[0][-1],b[1]-manual[1]),(-7,1),'system incremental cash/income')
    eq((bs[0][-1]-b[0][-1],bs[2]-b[2]),(-14,-4),'stress cash and equity causes')
    eq((sum(inp['academic-opening'][:-1]),50+160-8+18),(330,220),'opening positions')
    eq((F(14)*F(210,121)-24,F(20)*F(210,121)-36),(F(36,121),F(-156,121)),'NPV explicit polynomial')
    eq(F(5)*F(3310,1331)-12,F(578,1331),'three year cash PV')
    eq(academic(cost=36,gross=22)[0],(24,14,52),'Y fails early cash despite annual close')
    eq((npv(0,2,2),npv(24,16,2)-npv(24,14,2)),(F(420,121),F(420,121)),'opportunity cost not sunk study')
    for c in (0,10,24,30,36,40,41):
        result=academic(cost=c);yes((min(result[0])>=20)==(c<=30),'base cash ceiling all dates')
        st=academic(cost=c,delay=20,ret=-10);yes((min(st[0])>=20)==(c<=10),'stress cash ceiling all dates')
        eq(result[7],330+result[6],'varied cost book identity')
    for rate,inflation in ((F(1,20),F(1,50)),(0,0),(F(-1,20),F(1,50)),(F(1,50),F(1,50))):
        limit=200*(rate-inflation)
        for payout in (0,6,8):
            yes((200*(1+rate)-payout>=200*(1+inflation))==(payout<=limit),'global real preservation algebra witness')
    worlds=0
    for f in (F(0),F(1),F(6),F(7),F(8),F(10)):
        for x in (F(0),F(12),F(13),F(19),F(20)):
            for earlier in (False,True):
                result=lender(stress=True,funding=f,new=x,early=earlier);worlds+=1
                feasible=min(result[0])>=10 and result[2]>=32
                criterion=f>=(1 if earlier else 7) and x<=min(20,12+f)
                eq(feasible,criterion,'entire feasible region/order witnesses')
                eq(result[2],31+f,'equity independent of later lending')
                eq(result[0][-1],22+f-x,'closing cash symbolic formula')
                eq(result[3],140+x,'gross loan flow')
    eq(min(lender(stress=True,funding=7,new=19)[0]),10,'boundary feasible')
    yes(min(lender(stress=True,funding=7,new=20)[0])<10,'one more loan breaches final floor')
    eq(min(lender(stress=True,funding=6,new=0)[0]),9,'zero loans cannot cure prior withdrawal')
    invalid=[lambda:npv(-1,2,2),lambda:npv(1,2,0),lambda:npv(1,2,2,-1),lambda:draw(200,-201),lambda:draw(200,0,-1),lambda:academic(delay=-1),lambda:academic(delay=41),lambda:academic(active=False),lambda:lender(funding=-1),lambda:lender(new=-1),lambda:lender(new=21),lambda:lender(early='yes')]
    for fn in invalid:
        try:fn()
        except ValueError:pass
        else:raise ValueError('invalid domain accepted')
    return count,len(invalid),len(want),worlds


def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    raw={f:(root/f).read_bytes() for f in FILES};review=strict_json(raw[FILES[3]]);sources=strict_json(raw[FILES[2]])
    require(set(review['payloads'])==set(FILES[:3]),'three nonself hashes')
    for f,v in review['payloads'].items():require(v=={'bytes':len(raw[f]),'sha256':sha256(raw[f]).hexdigest()},'changed frozen file '+f)
    d=BaseManuscript();d.feed(raw[FILES[0]].decode());require(not d.stack and len(d.ids)==len(set(d.ids)),'balanced unique fragment')
    ids={f'v18-c02-e{i}' for i in range(1,9)}
    require(set(d.prompts)==set(d.solutions)==set(review['exact_prompt_review'])==ids,'eight exact exercise/answer pairs')
    require(d.worked==['v18-c02-case1','v18-c02-case2'],'two complete worked cases')
    for k,v in review['exact_prompt_review'].items():require(v['prompt_sha256']==sha256(d.prompts[k].encode()).hexdigest() and v['solution_sha256']==sha256(d.solutions[k].encode()).hexdigest(),'reviewed pair changed')
    urls={'v07-c02-sec-guide':'https://www.sec.gov/investor/pubs/begfinstmtguide.htm','v08-c01-mit-budgeting':'https://ocw.mit.edu/courses/15-401-finance-theory-i-fall-2008/06b2ce70ad26ae3d3be8d94145495be6_MIT15_401F08_lec18.pdf','v11-c02-boe-capital':'https://www.bankofengland.co.uk/-/media/boe/files/quarterly-bulletin/2013/bank-capital-and-liquidity.pdf'}
    require(d.sources==urls=={s['id']:s['url'] for s in sources['sources']},'scoped exact source routes')
    require({a for a in d.links if not a.startswith('https://')}=={'curriculum.html#v18-c01','v07-c02.html','v08-c01.html','v11-c02.html','curriculum.html#v18-c03'},'prerequisite and continuation routes')
    comparisons,invalid,groups,worlds=audit(d)
    return {'chapter':'v18-c02','status':'passed','runtime_files':4,'worked_cases':2,'prompts':8,'solutions':8,'numeric_groups':groups,'comparisons':comparisons,'invalid_domains':invalid,'funding_order_worlds':worlds,'source_routes':3,'scope':'Full dated budgets, net-assets/equity/cash bridges, finite NPV choice, global funding-region proofs and exact qualitative answers reviewed; synthetic models only.'}


if __name__=='__main__':
    check()
