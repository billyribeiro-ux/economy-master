"""Independent C03 peer oracle: candidate objective maximization and statewise action comparison."""
from pathlib import Path
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
import ast
import json
FILES=('production/v18-c03-working.html','production/check_v18_c03_working.py','production/v18-c03-sources-working.json','production/v18-c03-author-review-working.json','production/check_v18_c03_peer_working.py','production/v18-c03-peer-review-working.json')
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


def agent(b,m=F(1,2),capacity=F(1)):
    b,m,capacity=map(F,(b,m,capacity))
    require(b>=0 and m>=0 and capacity>0,'nonnegative bonus/motive, positive capacity')
    # Enumerate every vertex, stationary point on each edge, and interior stationary point.
    candidates={(F(0),F(0)),(capacity,F(0)),(F(0),capacity)}
    candidates.update(((min(b,capacity),F(0)),(F(0),min(m,capacity))))
    e=max(F(0),min(capacity,(b+capacity-m)/2));candidates.add((e,capacity-e))
    if b+m<=capacity:candidates.add((b,m))
    utility=lambda pair:b*pair[0]+m*pair[1]-(pair[0]**2+pair[1]**2)/2
    best=max(map(utility,candidates));winners=[pair for pair in candidates if utility(pair)==best]
    require(len(winners)==1,'strictly concave candidate optimum unique')
    return (*winners[0],best)


def outcomes(b,k=3):
    e,q,u=agent(b);w=F(b)*e;gross=e+F(k)*q
    return e,q,w,gross,gross-w,u


def delegated(p,alpha,d,tie_large=True):
    p,alpha,d=map(F,(p,alpha,d));require(0<=p<=1 and 0<=alpha<=1 and d>=0,'probability/share/cost domain')
    require(type(tie_large) is bool,'declared tie rule')
    result=[]
    for large in (F(20),F(-12)):
        menu=[(F(8),F(0)),(large,F(1))]
        utilities=[alpha*max(v,0)-effort for v,effort in menu]
        choice=1 if utilities[1]>utilities[0] or (utilities[1]==utilities[0] and tie_large) else 0
        v,effort=menu[choice];w=alpha*max(v,0)
        result.append((choice,v,w,effort,w-effort,v-w-d))
    weighted=tuple(p*result[0][j]+(1-p)*result[1][j] for j in range(1,6))
    return tuple(row[0] for row in result),weighted,tuple(result)


def audit(d):
    count=0
    def eq(a,b,label):
        nonlocal count
        require(a==b,label);count+=1
    def yes(ok,label):
        nonlocal count
        require(ok,label);count+=1
    inputs={k:numeric(v) for k,v in d.inputs.items()}
    eq(inputs,{'tasks':(3,F(1,2),1),'delegation':(F(1,2),8,20,-12,1,2)},'visible primitive tuples')
    k,m,capacity=inputs['tasks'];p,small,high,low,effort,cost=inputs['delegation']
    bonuses=(F(0),F(1,2),F(1),F(3,2),F(2))
    rows=tuple((b,*outcomes(b)[:5]) for b in bonuses)
    at=outcomes(F(1,2));policy=delegated(p,F(1,12),cost)[1]
    strict=delegated(p,F(1,10),cost)[1]
    quarter=delegated(F(1,4),F(1,12),cost)[1]
    expensive=delegated(p,F(1,12),5)[1]
    want={'task-rows':rows,'task-optimum':(F(1,2),at[0],at[1],at[4],at[5]),'delegation-baselines':(small,p*high+(1-p)*low,p*high+(1-p)*low-2),'delegation-contract':(F(1,12),policy[0],policy[1],policy[3],policy[4]),'audit-boundary':(policy[4]+cost,policy[4]+cost-small,policy[4]-small),'strict-contract':(F(1,10),strict[4],strict[3]),'e1':outcomes(1),'e3':(F(1,2),outcomes(F(1,2),1)[4]),'e5':(expensive[4],small,expensive[4]-small),'e6':(quarter[4],small,F(1,4)*high+F(3,4)*low,quarter[4]-small)}
    eq(set(want),set(d.results),'all visible result groups')
    for key,value in want.items():eq(numeric(d.results[key]),value,'displayed '+key)
    table=[tuple(numeric(x) for x in r) for r in d.rows[1:]];eq(tuple(table),rows,'actual table cells')
    # Finite witnesses supplement, not substitute for, manually read global concavity proof.
    bonus_grid=tuple(F(i,8) for i in range(21))
    triangle=tuple((F(i,4),F(j,4)) for i in range(5) for j in range(5-i))
    for b in bonus_grid:
        e,q,u=agent(b)
        branch=(b,m) if b<=F(1,2) else ((b+m)/2,(F(3,2)-b)/2) if b<F(3,2) else (1,0)
        eq((e,q),branch,'piecewise choices against candidate optimization')
        yes(u>=0 and e>=0 and q>=0 and e+q<=1,'participation and feasibility')
        for ee,qq in triangle:
            delta=(b-e)*(ee-e)+(m-q)*(qq-q)
            yes(delta<=0,'global gradient inequality witness')
            other=b*ee+m*qq-(ee**2+qq**2)/2
            eq(other-u,delta-((ee-e)**2+(qq-q)**2)/2,'exact concavity remainder identity')
        for weight in (1,3):
            net=outcomes(b,weight)[4]
            poly=b+F(weight,2)-b*b if b<=F(1,2) else (b+F(1,2))/2+weight*(F(3,2)-b)/2-b*(b+F(1,2))/2 if b<F(3,2) else 1-b
            eq(net,poly,'principal objective all branches')
            yes(net<=outcomes(F(1,2),weight)[4],'global principal optimum witnesses')
    eq(agent(F(1,2)),(F(1,2),F(1,2),F(1,4)),'first switch unique')
    eq(agent(F(3,2)),(1,0,1),'second switch unique')
    eq(agent(0,0),(0,0,0),'no professional motive boundary')
    eq(agent(1,0),(1,0,F(1,2)),'different motive counterexample')
    eq(agent(0,2),(0,1,F(3,2)),'quality-only capacity corner')
    eq(agent(F(1,4),F(1,4),F(1,4)),(F(1,8),F(1,8),F(3,64)),'changed capacity')
    # All four action policies are evaluated directly in each state, including unfavorable ties.
    alphas=(F(0),F(1,24),F(1,12),F(1,10),F(1,2),F(1))
    worlds=0
    for prob in (F(0),F(1,4),F(1,2),F(1)):
        for a in alphas:
            for tie in (False,True):
                choices,values,state=delegated(prob,a,2,tie);worlds+=1
                expected=(1,0) if a>F(1,12) or a==F(1,12) and tie else (0,0)
                eq(choices,expected,'direct statewise incentive choice')
                yes(all(r[4]>=0 for r in state),'statewise participation')
                gross=8+12*prob if choices==(1,0) else 8
                eq(values[0],gross,'state-weighted value')
                eq(values[4],gross*(1-a)-2,'wages and audit separated')
    eq(delegated(p,F(1,12),2,False)[1][4],F(16,3),'unsupported tie destroys benchmark')
    eq(delegated(p,F(1,12),F(29,6))[1][4],8,'audit indifference boundary')
    eq(delegated(F(8,33),F(1,12),2)[1][4],8,'frequency indifference boundary')
    for prob in (F(0),F(1,4),F(1,2),F(1)):
        value=delegated(prob,F(1,12),2)[1][4]
        eq(value,F(22,3)+11*prob-2,'general probability formula')
        eq(prob*20+(1-prob)*(-12)-1,32*prob-13,'central L participation cost')
    for eps in (F(1,120),F(1,1200),F(1,12000)):
        value=delegated(p,F(1,12)+eps,2)[1][4]
        eq(value,F(65,6)-14*eps,'strict supremum gap positive')
        yes(value<F(65,6),'supremum unachieved')
    eq((outcomes(F(3,2))[4],outcomes(F(1,2))[4]),(F(-1,2),F(7,4)),'delayed exact outcomes')
    eq(sum((7,7,7,9)),30,'thirty day evidence plan')
    invalid=[lambda:agent(-1),lambda:agent(0,-1),lambda:agent(0,0,0),lambda:agent(0,0,-1),lambda:delegated(-1,0,0),lambda:delegated(2,0,0),lambda:delegated(0,-1,0),lambda:delegated(0,2,0),lambda:delegated(0,0,-1),lambda:delegated(0,0,0,'true')]
    for fn in invalid:
        try:fn()
        except ValueError:pass
        else:raise ValueError('invalid domain accepted')
    return count,len(invalid),len(want),worlds


def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    raw={f:(root/f).read_bytes() for f in FILES};peer=strict_json(raw[FILES[5]]);author=strict_json(raw[FILES[3]]);sources=strict_json(raw[FILES[2]])
    require(set(peer['payloads'])==set(FILES[:5]) and set(author['payloads'])==set(FILES[:3]),'nonself bindings')
    for rec in (author,peer):
        for f,v in rec['payloads'].items():require(v=={'bytes':len(raw[f]),'sha256':sha256(raw[f]).hexdigest()},'changed frozen file '+f)
    text=raw[FILES[0]].decode();d=BaseManuscript();d.feed(text);require(not d.stack and len(d.ids)==len(set(d.ids)),'balanced unique fragment')
    ids={f'v18-c03-e{i}' for i in range(1,9)}
    require(set(d.prompts)==set(d.solutions)==set(peer['exact_prompt_review'])==ids and d.worked==['v18-c03-case1','v18-c03-case2'],'eight pairs/two complete cases')
    for k,v in peer['exact_prompt_review'].items():
        require(v['prompt_sha256']==sha256(d.prompts[k].encode()).hexdigest() and v['solution_sha256']==sha256(d.solutions[k].encode()).hexdigest(),'reviewed exact pair changed')
    routes={'v05-c09-mit-contracts':'https://ocw.mit.edu/courses/14-124-microeconomic-theory-iv-spring-2017/0a3d53590f17f81f1561eb7d7922329d_MIT14_124S17_Slide2.pdf','v05-c09-hart-control':'https://hart.scholars.harvard.edu/sites/g/files/omnuum10571/files/hart/files/incomplete_contracts_and_control.pdf'}
    require(d.sources==routes=={s['id']:s['url'] for s in sources['sources']},'exact scoped source routes')
    require(all(s['inherited_record']=='content/reviews/v05-c09-sources.json' and 'Original named inspector not specified' in s['current_author_inspection'] for s in sources['sources']),'preserved source provenance limit')
    require({a for a in d.links if not a.startswith('https://')}=={'curriculum.html#v18-c01','curriculum.html#v18-c02','curriculum.html#v18-c04','v05-c09.html','v13-c09.html'},'chapter routes')
    comparisons,invalid,groups,worlds=audit(d)
    return {'chapter':'v18-c03','status':'passed','review':'independent internal peer','runtime_files':6,'worked_artifacts':2,'prompts':8,'solutions':8,'numeric_groups':groups,'comparisons':comparisons,'invalid_domains':invalid,'delegation_worlds':worlds,'source_routes':2,'author_checker':'opaque hash only; never read as text/imported/executed','scope':'Full models, global proofs, role maps, decision memos, exact solutions and bounded sources read; no actual organizational performance certified.'}


if __name__=='__main__':
    check()
