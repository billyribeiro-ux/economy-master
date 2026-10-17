"""Independent C07 peer oracle: integer cohort search and pool-by-pool cash recursion."""
from pathlib import Path
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
import ast
import json
FILES=('content/chapters/v18-c07.html','scripts/check_v18_c07.py','content/reviews/v18-c07-sources.json','content/reviews/v18-c07-author.json','scripts/check_v18_c07_peer.py','content/reviews/v18-c07-peer.json')
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




def cohort(T=100,floor=40,ready=40,bridge=30,budget=60,share=F(1,4)):
    T,floor,budget,share=map(F,(T,floor,budget,share))
    require(type(ready) is int and type(bridge) is int and min(ready,bridge)>=0,'integer nonnegative applicant counts')
    require(min(T,floor,budget)>=0 and 0<=share<=1,'nonnegative resources and valid share')
    candidates=[]
    for a in range(ready+1):
        for b in range(bridge+1):
            n=a+b;instruction=20+F(n,2)+b;research=T-instruction
            if research>=floor and b>=share*n and 3*b<=budget:
                candidates.append((a,b,n,instruction,research,3*b,budget-3*b))
    if not candidates:return None,()
    largest=max(x[2] for x in candidates);ties=tuple(x for x in candidates if x[2]==largest)
    return max(ties,key=lambda x:x[4]),ties


def draw(E,returns=(F(-1,20),F(1,20),F(3,20)),q=F(9,10),inflation=F(1,50)):
    E,q,inflation=map(F,(E,q,inflation));returns=tuple(map(F,returns))
    require(E>0 and 0<=q<=1 and inflation>-1 and returns and min(returns)>=-1,'valid pool/scenario domain')
    headrooms=tuple(E*(1+r)-q*E*(1+inflation) for r in returns)
    return min(headrooms) if min(headrooms)>=0 else None


def closing(E,returns,payments):
    require(len(returns)==len(payments) and E>0 and all(p>=0 for p in payments),'valid dated cash sequence')
    out=[];balance=F(E)
    for r,p in zip(returns,payments):
        require(r>=-1,'return at least minus one');balance=balance*(1+r)-p;out.append(balance)
    return tuple(out)


def audit(d):
    count=0
    def eq(a,b,label):
        nonlocal count
        require(a==b,label);count+=1
    def yes(ok,label):
        nonlocal count
        require(ok,label);count+=1
    eq({k:numeric(v) for k,v in d.inputs.items()},{'cohort':(100,20,40,F(1,2),1,40,30,3,60),'endowment':(100,3,2,20,1,F(1,50),F(9,10),F(-1,20))},'complete visible primitives')
    original,ties=cohort();changed=[cohort(floor=39)[0],cohort(T=101)[0]];scholar=cohort(budget=36)[0];extra=cohort(T=102,ready=44)[0];ret=cohort(share=F(1,3))[0]
    rate=draw(1);base=draw(100);gift=draw(20);center=base-3+gift;gap=2-center;minimum=(2-(base-3))/rate
    two=closing(100,(F(-1,20),)*2,(base,base));zero=closing(100,(F(-1,20),)*2,(base,0));floor2=F(90)*F(51,50)**2
    better=draw(120,(F(-1,25),F(1,20),F(3,20)))
    want={'cohort-optimum':original,'cohort-changes':tuple((T,fl,*r[:3],r[4]) for T,fl,r in zip((100,101),(39,40),changed)),'draw-rate':rate,'gift-budget':(base,gift,base+gift,center,gap),'minimum-gift':(minimum,base-3,draw(minimum),base+draw(minimum)),'two-period':(*two,floor2,floor2-two[-1],zero[-1]),'e2':tuple(changed),'e3':scholar,'e4':(102,*extra[:3],extra[3],extra[4],extra[5]),'e5':(gap,gap-1,minimum),'e6':(better/120,better,better-5,F(19,20)-F(19,20)*F(51,50)),'e7':(floor2-two[-1],floor2-zero[-1]),'retention':(*ret[:3],ret[4],ret[5],ret[6],draw(150),5-draw(150))}
    eq(set(want),set(d.results),'all displayed result groups')
    for k,v in want.items():eq(numeric(d.results[k]),v,'derived result '+k)
    eq(tuple(x[1] for x in ties),(14,13),'both largest-cohort ties before secondary selection')
    ledger={r[0]:r[1] for r in d.rows if len(r)==3 and r[0] in ('Ready / bridge / total places','Fixed / core / extra bridge hours','Research hours','Scholarship expenditure / remainder','Bridge share')}
    eq(ledger,{'Ready / bridge / total places':'39 / 13 / 52','Fixed / core / extra bridge hours':'20 / 26 / 13','Research hours':'41','Scholarship expenditure / remainder':'39 / 21','Bridge share':'1/4'},'actual cohort table complete')
    funds={r[0]:tuple(numeric(x) for x in r[1:]) for r in d.rows if r[0] in ('Base','Center-restricted gift','Total')}
    eq(funds,{'Base':(100,base,3,base-3),'Center-restricted gift':(20,gift,0,gift),'Total':(120,base+gift,3,center)},'actual restricted funding table')
    eq(F(40)/(F(1,2)+F(1,4)),F(160,3),'continuous upper bound')
    eq(F(53,2)+14,F(81,2),'integer53 exclusion')
    eq(F(55,2)+15,F(85,2),'readycap excludes55')
    eq(F(57,2)+15,F(87,2),'quarter excludes57')
    eq(cohort(T=101,ready=44)[0][2],54,'one extra hour cannot support56')
    eq(cohort(T=102,ready=44)[0][2],56,'two extra hours attainable')
    # Complete finite candidate searches at material neighboring resource/access boundaries.
    worlds=0
    for T in (99,100,101,102):
        for budget in (0,36,60):
            for share in (F(1,4),F(1,3)):
                chosen,ts=cohort(T=T,budget=budget,share=share);worlds+=1
                yes(chosen is not None,'zero cohort feasible at these resources')
                a,b,n,ins,research,spent,left=chosen
                eq(ins+research,T,'faculty ledger')
                eq(spent+left,budget,'scholarship ledger')
                yes(n<=int((T-60)/(F(1,2)+share)),'continuous global bound respected')
                yes(n<=int(budget/3/share),'scholarship/access bound respected')
                eq(b,min(x[1] for x in ts),'secondary research objective selects minimum bridge')
    eq(cohort(T=59),(None,()),'fixed preparation and research make even empty program infeasible')
    eq(cohort(T=60)[0],(0,0,0,20,40,0,60),'empty program exact boundary')
    # Separate each restricted pool and test actual capital inequalities in every supplied scenario.
    funding_worlds=0
    for E in (F(20),F(50),minimum,F(100)):
        permitted=draw(E)
        for r in (F(-1,20),F(1,20),F(3,20)):
            for payment in (F(0),permitted/2,permitted):
                funding_worlds+=1
                close=E*(1+r)-payment;target=F(9,10)*E*F(51,50)
                yes(close>=target,'actual pool scenario passes')
                if r==F(-1,20) and payment==permitted:eq(close,target,'binding worst case')
        yes(E*F(19,20)-(permitted+F(1,100))<F(9,10)*E*F(51,50),'any extra positive draw fails worst scenario')
    eq((F(9,2)-(base+gift),1-(F(9,2)-(base+gift))),(F(33,50),F(17,50)),'smaller temporary center balances')
    eq((base-3+draw(minimum),base+draw(minimum)),(2,5),'minimum gift constructive restrictions')
    yes(base-3+draw(minimum-F(1,100))<2,'strictly smaller gift insufficient')
    eq((draw(100,(F(-1,25),))-3,draw(20,(F(-1,25),))), (F(6,5),F(21,25)),'better return separate allocation')
    yes(F(4,5)<=draw(20,(F(-1,25),)),'only .8 of restricted draw required')
    for E in (1,20,100,1000):eq(draw(E,q=F(19,20)),None,'larger proportionally restricted gift cannot fix negative coefficient')
    eq(draw(100,(F(-1,20),),q=F(95,102)),0,'zero draw exact boundary')
    eq((two[0],two[1],zero[1]),(F(459,5),F(8401,100),F(8721,100)),'actual two cash recursions')
    ratchet=two[0]*F(9,10)*F(51,50)
    yes(ratchet<floor2,'reset target is a different smaller target')
    eq(two[0]*F(19,20)-draw(two[0]),ratchet,'reset compliant draw uses depleted opening')
    invalid=[lambda:cohort(ready=F(1,2)),lambda:cohort(bridge=-1),lambda:cohort(T=-1),lambda:cohort(floor=-1),lambda:cohort(budget=-1),lambda:cohort(share=2),lambda:draw(0),lambda:draw(1,q=2),lambda:draw(1,returns=()),lambda:draw(1,inflation=-1),lambda:draw(1,returns=(-2,)),lambda:closing(1,(0,),()),lambda:closing(1,(0,),(-1,))]
    for fn in invalid:
        try:fn()
        except ValueError:pass
        else:raise ValueError('invalid domain accepted')
    return count,len(invalid),len(want),worlds,funding_worlds


def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    raw={f:(root/f).read_bytes() for f in FILES};peer=strict_json(raw[FILES[5]]);author=strict_json(raw[FILES[3]]);sources=strict_json(raw[FILES[2]])
    require(set(peer['payloads'])==set(FILES[:5]) and set(author['payloads'])==set(FILES[:3]),'nonself bindings')
    for rec in (author,peer):
        for f,v in rec['payloads'].items():require(v=={'bytes':len(raw[f]),'sha256':sha256(raw[f]).hexdigest()},'changed frozen file '+f)
    d=BaseManuscript();d.feed(raw[FILES[0]].decode());require(not d.stack and len(d.ids)==len(set(d.ids)),'balanced unique fragment')
    ids={f'v18-c07-e{i}' for i in range(1,9)}
    require(set(d.prompts)==set(d.solutions)==set(peer['exact_prompt_review'])==ids and d.worked==['v18-c07-case1','v18-c07-case2'],'eight pairs/two complete cases')
    for k,v in peer['exact_prompt_review'].items():require(v['prompt_sha256']==sha256(d.prompts[k].encode()).hexdigest() and v['solution_sha256']==sha256(d.solutions[k].encode()).hexdigest(),'reviewed exact pair changed')
    routes={'v18-c07-aaup-government':'https://www.aaup.org/reports-publications/aaup-policies-reports/topical-reports/statement-government-colleges-and','v18-c07-aaup-freedom':'https://www.aaup.org/reports-publications/aaup-policies-reports/policy-statements/1940-statement-principles-academic'}
    require(d.sources==routes=={s['id']:s['url'] for s in sources['sources']},'exact scoped source routes')
    require(sources['actual_inspector']=='root','source inspector preserved')
    require({a for a in d.links if not a.startswith('https://')}=={'curriculum.html#v18-c01','v07-c03.html','v17-c12.html','curriculum.html#v18-c08'},'chapter routes')
    comparisons,invalid,groups,cohorts,funds=audit(d)
    return {'chapter':'v18-c07','status':'passed','review':'independent internal peer','runtime_files':6,'worked_artifacts':2,'prompts':8,'solutions':8,'numeric_groups':groups,'comparisons':comparisons,'invalid_domains':invalid,'cohort_worlds':cohorts,'funding_worlds':funds,'source_routes':2,'author_checker':'opaque hash only; never read as text/imported/executed','scope':'Full integer and capital-floor proofs, authority/academic standards/donor decisions, exact answers and bounded source record read; no actual institution or learner achievement certified.'}


if __name__=='__main__':
    check()
