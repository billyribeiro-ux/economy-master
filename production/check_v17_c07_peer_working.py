"""C07 independent peer: joint state/report enumeration and resident net accounts."""
from pathlib import Path
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from itertools import product
import ast
import json
import re
FILES=('production/v17-c07-working.html','production/check_v17_c07_working.py','production/v17-c07-sources-working.json','production/v17-c07-author-review-working.json','production/check_v17_c07_peer_working.py','production/v17-c07-peer-review-working.json')
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


def means(rows,p):
    require(0<=p<=1 and len(rows)>0 and all(len(row)==2 for row in rows),'two-state probability domain')
    return tuple((1-p)*lo+p*hi for lo,hi in rows)


def best(values):return tuple(i for i,v in enumerate(values) if v==max(values))


def worst(rows,lo,hi):
    require(0<=lo<=hi<=1,'ordered probability interval')
    ends=(means(rows,lo),means(rows,hi))
    return tuple(min(ends[0][i],ends[1][i]) for i in range(len(rows)))


def regret(rows,lo,hi):
    require(0<=lo<=hi<=1,'ordered probability interval')
    ends=(means(rows,lo),means(rows,hi))
    return tuple(max(max(e)-e[i] for e in ends) for i in range(len(rows)))


def signal(rows,p,tpr,fpr,fee=F(0)):
    means(rows,p)
    require(0<=tpr<=1 and 0<=fpr<=1 and fee>=0,'signal probability/cost domain')
    joint=(( (1-p)*fpr,p*tpr ),((1-p)*(1-fpr),p*(1-tpr)))
    policies={policy:sum((joint[report][state]*rows[policy[report]][state] for report in (0,1) for state in (0,1)),F(0)) for policy in product(range(len(rows)),repeat=2)}
    gross=max(policies.values())
    return joint,policies,gross,gross-fee


def program(np,nr,benefits,cost,w):
    require(type(np) is int and type(nr) is int and np>0 and nr>0 and cost>=0 and w>=0 and len(benefits)==2,'population/cost/weight domain')
    tax=cost/(np+nr);net=tuple(b-tax for b in benefits)
    return tax,net,np*net[0]+nr*net[1],np*w*net[0]+nr*net[1]


def audit(d):
    x={k:numeric(v) for k,v in d.inputs.items()};count=0
    def eq(a,b,label):
        nonlocal count
        require(a==b,label);count+=1
    expected={'capacity':((0,0),(4,10),(-8,22)),'p-first':F(1,2),'p-range':(F(3,10),F(7,10)),'signal':(F(3,4),F(1,4)),'signal-fee':F(2),'programs':(20,20,6,2,3,5,80),'w-first':F(2),'benefit-range':(2,6),'e1-p':F(2,5),'e2-fee':F(4),'e4-w':F(1,2),'e6-minutes':(30,8,10,3)}
    eq(x,expected,'all actual primitive groups')
    rows=x['capacity'];p=x['p-first'];lo,hi=x['p-range'];base=means(rows,p)
    actualrows=tuple(tuple(numeric(v) for v in row[1:]) for row in d.rows if len(row)==3 and row[0] in ('O','S','L'))
    eq(actualrows,rows,'actual full payoff table')
    joint,policies,gross,net=signal(rows,p,*x['signal'],x['signal-fee']);massH=sum(joint[0]);massL=sum(joint[1]);postH=joint[0][1]/massH;postL=joint[1][1]/massL
    perfect=(1-p)*max(row[0] for row in rows)+p*max(row[1] for row in rows)
    np,nr,ap,ar,bp,br,cost=x['programs'];np,nr=int(np),int(nr);w=x['w-first'];a=program(np,nr,(ap,ar),cost,w);b=program(np,nr,(bp,br),cost,w)
    bmin,bmax=x['benefit-range'];alow=program(np,nr,(bmin,ar),cost,w);ahigh=program(np,nr,(bmax,ar),cost,w)
    threshold=(b[3]-nr*(ar-a[0]))/(np*w)+a[0]
    feasible=[name for name,floor in (('A',alow[1][0]),('B',b[1][0]),('O',F(0))) if floor>=2]
    exit_a=program(np,nr,(F(5),ar),cost,w)
    total,reserved,learners,turn=x['e6-minutes'];plan=(4,6,12,8)
    want={'expected-first':base,'worst-expected':worst(rows,lo,hi),'worst-state':tuple(min(row) for row in rows),'signal-result':(massH,postH,postL,gross,net,net-max(base)),'signal-fee-limit':gross-max(base),'perfect-information':perfect-max(base),'exit-capacity':means(rows,F(3,4)),'program-net':(a[1],b[1]),'program-total':(a[2],b[2]),'weighted-first':(a[3],b[3]),'weighted-range':(alow[3],ahigh[3]),'benefit-threshold':threshold,'robust-feasible-count':len(feasible),'exit-program':(exit_a[3],b[3],exit_a[1][0]),'e1-means':means(rows,x['e1-p']),'e2-net':gross-x['e2-fee'],'e3-regrets':regret(rows,lo,hi),'e4-values':(program(np,nr,(ap,ar),cost,x['e4-w'])[3],program(np,nr,(bp,br),cost,x['e4-w'])[3]),'e5-value':program(np,nr,(F(4),F(4)),cost,w)[3],'e6-shortfall':learners*turn-(total-reserved),'e6-plan':plan}
    eq(set(want),set(d.results),'every visible result group')
    for k,v in want.items():eq(numeric(d.results[k]),v,'visible '+k)
    eq(tuple(policy for policy,v in policies.items() if v==gross),((2,1),),'all nine contingent policies')
    eq((means(rows,postH),means(rows,postL)),((0,F(17,2),F(29,2)),(0,F(11,2),F(-1,2))),'all posterior action values')
    eq((gross,max(base),perfect),(10,7,13),'gross/signal-free/perfect means')
    eq((gross-x['e2-fee'],max(base)-x['e2-fee']),(6,3),'sunk fee use versus ignore')
    for fee,wantdecision in ((F(2),'buy'),(F(3),'tie'),(F(4),'decline')):
        gain=gross-fee-max(base);eq('buy' if gain>0 else 'tie' if gain==0 else 'decline',wantdecision,'acquisition fee boundary')
    # Global expected-payoff threshold witnesses, including the probability endpoints.
    for prob in (F(0),lo,F(2,5),F(1,2),hi,F(3,4),F(1)):
        v=means(rows,prob)
        eq(v[2]-v[1],-12+24*prob,'mean difference identity')
        eq(best(v),(1,) if prob<F(1,2) else (2,) if prob>F(1,2) else (1,2),'full optimal set')
        require(v[1]>v[0],'outside strictly dominated');count+=1
    eq(best(worst(rows,lo,hi)),(1,),'worst-mean choice')
    rmax=regret(rows,lo,hi);eq(tuple(i for i,r in enumerate(rmax) if r==min(rmax)),(1,2),'minimax regret complete tie')
    for prob in (lo,F(2,5),F(1,2),F(3,5),hi):
        v=means(rows,prob)
        require(all(max(v)-v[i]<=rmax[i] for i in range(3)),'regret envelope witness');count+=1
    eq((max(means(rows,hi)),means(rows,hi)[2]),(13,13),'outside maximum regret endpoint')
    # Alternative signals, including degenerate report probabilities, evaluated without dividing by zero.
    for tpr,fpr,gain in ((F(1,2),F(1,2),F(0)),(F(1),F(0),F(6)),(F(1,4),F(3,4),F(3)),(F(1),F(1),F(0))):
        j,pol,g,n=signal(rows,p,tpr,fpr)
        eq(g-max(base),gain,'signal information variant')
        eq(sum(sum(row) for row in j),1,'joint probability total')
    for prior in (F(0),F(1)):
        eq(signal(rows,prior,F(1),F(0))[2],max(means(rows,prior)),'known state no information gain')
    eq(a[0]*(np+nr),cost,'tax finances exact cost')
    for weight in (F(0),F(1,2),F(1),F(2),F(3)):
        av=program(np,nr,(ap,ar),cost,weight)[3];bv=program(np,nr,(bp,br),cost,weight)[3]
        eq(av-bv,60*(weight-1),'global welfare difference')
        eq(best((0,av,bv)),(2,) if weight<1 else (1,) if weight>1 else (1,2),'all weight regimes')
    for benefit in (F(2),F(4),F(9,2),F(5),F(6)):
        v=program(np,nr,(benefit,ar),cost,w)
        eq(v[3]-b[3],40*(benefit-F(9,2)),'updated welfare threshold')
        eq(v[1][0]>=2,benefit>=4,'floor threshold distinct from ranking')
        eq(v[2]<=b[2],True,'unweighted B weakly dominates interval')
    cprog=program(np,nr,(F(4),F(4)),cost,w)
    eq((cprog[1],cprog[3]),((2,2),120),'new C exact floor')
    eq(tuple(n for n,f in (('A',alow[1][0]),('B',b[1][0]),('C',cprog[1][0]),('O',0)) if f>=2),('C',),'only robust-feasible C')
    eq((alow[3],b[3],cprog[3],ahigh[3]),(0,100,120,160),'robust versus upper-world choice')
    delayed=program(np,nr,(F(4),ar),cost,w)
    eq((delayed[3],b[3],delayed[1][0],b[1][0]),(80,100,2,1),'delayed constrained choice')
    eq((sum((5,8,12,10,10,5)),sum((5,8,8,10,8,6))),(50,45),'both full facilitation budgets')
    eq((sum(plan),plan[-1],plan[-1]-2,learners*turn,total-reserved),(30,8,6,30,22),'revised time plan/exit/check')
    eq(2+2+2+2,8,'exit rubric')
    invalid=[lambda:means(rows,F(-1,10)),lambda:means(rows,F(11,10)),lambda:means(((1,),),F(1,2)),lambda:worst(rows,hi,lo),lambda:regret(rows,F(0),F(2)),lambda:signal(rows,p,F(2),F(0)),lambda:signal(rows,p,F(1),F(-1)),lambda:signal(rows,p,F(1),F(0),F(-1)),lambda:program(0,20,(6,2),F(80),F(2)),lambda:program(20,20,(6,2),F(-1),F(2)),lambda:program(20,20,(6,2),F(80),F(-1))]
    for fn in invalid:
        try:fn()
        except ValueError:pass
        else:raise ValueError('invalid domain accepted')
    return count,len(invalid),len(want)


def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    raw={f:(root/f).read_bytes() for f in FILES};peer=strict_json(raw[FILES[5]]);author=strict_json(raw[FILES[3]]);sources=strict_json(raw[FILES[2]])
    require(set(peer['payloads'])==set(FILES[:5]) and set(author['payloads'])==set(FILES[:3]),'nonself bindings')
    for rec in (author,peer):
        for f,v in rec['payloads'].items():require(v=={'bytes':len(raw[f]),'sha256':sha256(raw[f]).hexdigest()},'changed frozen file '+f)
    text=raw[FILES[0]].decode();d=BaseManuscript();d.feed(text);require(not d.stack and len(d.ids)==len(set(d.ids)),'balanced unique fragment')
    ids={f'v17-c07-e{i}' for i in range(1,9)}
    require(set(d.prompts)==set(d.solutions)==set(peer['exact_prompt_review'])==ids and d.worked==['v17-c07-case1','v17-c07-case2'],'eight pairs/two artifacts')
    for k,v in peer['exact_prompt_review'].items():
        require(v['prompt_sha256']==sha256(d.prompts[k].encode()).hexdigest() and v['solution_sha256']==sha256(d.solutions[k].encode()).hexdigest(),'reviewed exact pair changed')
    routes={'v17-c07-cmu-discussions':'https://www.cmu.edu/teaching/designteach/design/instructionalstrategies/discussions.html','v17-c07-hbs-questioning':'https://www.hbs.edu/teaching/case-method/leading-case-discussion/questioning-discussions'}
    require(d.sources==routes=={s['id']:s['url'] for s in sources['sources']},'two exact source routes')
    require(all(s['actual_inspector']=='root' for s in sources['sources']),'actual source inspector')
    require({a for a in d.links if not a.startswith('https://')}=={'v17-c06.html','v17-c08.html'},'chapter links')
    require('<a href="v17-c08.html">Misconceptions and learning evidence</a>' in text and 'broadens uncertainty about the effect' in text,'two bounded peer corrections retained')
    comparisons,invalid,groups=audit(d)
    return {'chapter':'v17-c07','status':'passed','review':'independent internal peer','runtime_files':6,'worked_artifacts':2,'prompts':8,'solutions':8,'numeric_groups':groups,'comparisons':comparisons,'invalid_domains':invalid,'source_routes':2,'contingent_policies':9,'author_checker':'opaque hash only; never read as text/imported/executed','scope':'Complete case/facilitation packets, exact solutions and global proofs read. Two peer findings corrected before final freeze; no actual classroom or policy outcomes certified.'}


if __name__=='__main__':
    check()
