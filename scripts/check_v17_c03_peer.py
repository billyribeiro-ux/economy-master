"""Independent C03 primitive oracle. Author checker is opaque, hash-bound only."""
from pathlib import Path
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from itertools import permutations, product
import ast
import json
import re

FILES=('content/chapters/v17-c03.html','scripts/check_v17_c03.py','content/reviews/v17-c03-sources.json','content/reviews/v17-c03-author.json','scripts/check_v17_c03_peer.py','content/reviews/v17-c03-peer.json')
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
    def bad(value):raise ValueError('nonfinite JSON')
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=bad)


def value(flows,rate):
    require(rate>-1 and len(flows)>0,'dated value domain')
    # Accumulate discount factors from the date-zero primitive, not a stored formula.
    discount=F(1);total=F(0)
    for cash in flows:
        total+=cash*discount;discount/=1+rate
    return total


def weighted(scores,weights):
    require(len(scores)==len(weights)>0 and sum(weights)==100,'complete percentage weights')
    require(all(0<=x<=100 for x in scores) and all(x>=0 for x in weights),'score/weight range')
    return sum((s*w for s,w in zip(scores,weights)),F(0))/100


def missing(total,observed,population,low,high):
    require(type(observed) is int and type(population) is int and 0<=observed<=population and population>0,'roster counts')
    require(low<=high and observed*low<=total<=observed*high,'score support')
    return ((total+(population-observed)*low)/population,(total+(population-observed)*high)/population)


def percentage(score,possible):
    require(possible>0 and 0<=score<=possible,'rescale domain')
    return 100*score/possible


def audit(d):
    inputs={k:numeric(v) for k,v in d.inputs.items()};count=0
    def eq(a,b,label):
        nonlocal count
        require(a==b,label);count+=1
    expected_inputs={'weekly-hours':(3,2,2,2),'cash-reserve':(100,20),'machine-a':(90,55,55),'machine-b':(70,42,42),'rate':F(1,10),'loan':(10,11),'scores':(100,90,60,95,100),'weights':(10,15,25,40,10)}
    eq(inputs,expected_inputs,'all exact supplied input groups')
    cash,reserve=inputs['cash-reserve'];ca,a1,a2=inputs['machine-a'];cb,b1,b2=inputs['machine-b'];r=inputs['rate'];loan,repay=inputs['loan']
    va=value((-ca,a1,a2),r);vb=value((-cb,b1,b2),r);equity=(-ca+loan,a1-repay,a2);weekly=sum(inputs['weekly-hours'])
    changed=(-ca+loan,a1-12,a2);changedvalue=value(changed,r)
    bounds=missing(F(6*8),6,8,F(0),F(10))
    want={'diagnostic':(F(250,1000),F(88,80)-1,F(14-2,3)),'course-hours':12*weekly,'project-values':(va,vb),'cash-no-loan':(cash-ca,cash-cb),'equity-flows':equity,'value-advantage':va-vb,'short-hours':9*weekly,'lost-hours':3*weekly,'ex3':(sum((3,3,3,2)),sum((3,3,3,2))-weekly,3,2,2,2),'ex4':(changedvalue,changedvalue-va,changedvalue-vb),'ex5':weighted(inputs['scores'],inputs['weights']),'ex6':bounds+tuple(x-6 for x in bounds),'ex7':(value((F(-50),F(60)),F(1,5)),F(70-50),value((F(-51),F(60)),F(1,5)),F(70-51)),'ex8':percentage(F(75),F(100-15)),'retention':(10*8,8*8,2*8)}
    eq(set(d.results),set(want),'every displayed result accounted')
    for k,v in want.items():eq(numeric(d.results[k]),v,'visible '+k)
    eq((1/(1+r),1/(1+r)**2),(F(10,11),F(100,121)),'displayed discount factors')
    eq(value(equity,r),va,'original equity value')
    eq(value((loan,-repay),r),0,'matched loan value')
    eq(cash+loan-ca,reserve,'immediate reserve equality')
    eq((cash-ca>=reserve,cash-cb>=reserve,va>vb>0),(False,True,True),'no-loan selection')
    eq(changedvalue-va,value((loan,F(-12)),r),'changed loan decomposition')
    eq(changedvalue>vb,True,'costlier loan still favors A')
    eq(12*weekly/F(9)-weekly,3,'unchanged breadth exceeds ceiling')
    eq((sum((1,1,4)),sum((2,2,2))), (6,6),'late-week independent hours')
    eq(sum((3,4,4,5,4)),20,'project rubric')
    eq(sum((2,2,2,2,2)),10,'ex4 rubric')
    eq(weighted(inputs['scores'],inputs['weights'])>=85 and 50>=75,False,'readiness despite high mark')
    eq(round(want['ex8'],2),F(2206,25),'displayed 88.24 rounding')
    # Full actual schedule rows and all six objective alignments.
    longrows=[row for row in d.rows if len(row)==4 and re.match(r'^\d+\.',row[0])]
    eq([int(row[0].split('.')[0]) for row in longrows],list(range(1,13)),'twelve calendar weeks')
    shortrows=[row for row in d.rows if len(row)==3 and row[0].isdigit()]
    eq([int(row[0]) for row in shortrows],list(range(1,10)),'nine calendar weeks')
    eq([int(re.search(r'week (\d+)',row[1]).group(1)) for row in shortrows],[1,2,3,4,5,8,10,11,12],'actual retained sequence')
    eq({row[0].split(':')[0] for row in d.rows if len(row)==3 and re.match('O[1-6]:',row[0])},{f'O{i}' for i in range(1,7)},'all objective rows')
    # Exact DAG exercise, checking every edge and all possible valid orders.
    prompt=d.prompts['v17-c03-ex2'];edges=re.findall(r'([UAPCRM])→([UAPCRM])',prompt)
    eq(edges,[('U','A'),('U','P'),('A','C'),('P','C'),('C','M'),('R','M')],'actual six prerequisite edges')
    def violations(order):return [(a,b) for a,b in edges if order.index(a)>order.index(b)]
    eq(violations(tuple('UAPCRM')),[],'answer valid order')
    eq(violations(tuple('UACPMR')),[('P','C'),('R','M')],'both bad-order violations')
    valid=[o for o in permutations('UAPCRM') if not violations(o)]
    eq(len(valid),10,'all finite permissible orders')
    # Non-default rate/loan witnesses: PV is linear, financing and value are distinct.
    for rate in (F(-1,4),F(0),F(1,10),F(1,2)):
        for borrowing in (F(0),F(10)):
            financing=(borrowing,-borrowing*(1+rate),F(0))
            combined=tuple(x+y for x,y in zip((-ca,a1,a2),financing))
            eq(value(combined,rate),value((-ca,a1,a2),rate)+value(financing,rate),'PV linearity witness')
            eq(value(financing,rate),0,'zero-value matched loan witness')
    # Repayment tie separates financing cost from initial feasibility.
    tie=F(11)+(va-vb)*(1+r)
    eq(tie,F(152,11),'repayment at equal financed values')
    for delta in (F(-1),F(0),F(1)):
        adv=value((-ca+loan,a1-tie-delta,a2),r)-vb
        eq(adv,-delta/(1+r),'ranking across repayment boundary')
    for c in (F(49),F(50),F(51)):
        eq((value((-c,F(60)),F(1,5))>0,F(70)-c>=20),(c<50,c<=50),'value and reserve thresholds')
    completions=[(F(48)+x+y)/8 for x,y in product((F(0),F(5),F(10)),repeat=2)]
    eq((min(completions),max(completions)),bounds,'attainable missing-score bounds')
    eq(missing(F(48),6,6,F(0),F(10)),(8,8),'no-missing collapse')
    eq(missing(F(0),0,8,F(0),F(10)),(0,10),'all-missing support')
    eq(weighted((F(85),F(85)),(F(25),F(75))),85,'weighted threshold equality')
    eq(percentage(F(85),F(85)),100,'rescale full marks')
    invalid=[lambda:value((1,),F(-1)),lambda:value((),F(0)),lambda:weighted((50,),(90,)),lambda:weighted((101,),(100,)),lambda:weighted((0,0),(-10,110)),lambda:missing(F(48),9,8,F(0),F(10)),lambda:missing(F(48),6,8,F(10),F(0)),lambda:missing(F(61),6,8,F(0),F(10)),lambda:missing(F(0),0,0,F(0),F(10)),lambda:percentage(F(1),F(0)),lambda:percentage(F(86),F(85))]
    for fn in invalid:
        try:fn()
        except ValueError:pass
        else:raise ValueError('invalid input accepted')
    return count,len(invalid),len(want)


def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    raw={f:(root/f).read_bytes() for f in FILES};peer=strict_json(raw[FILES[5]]);author=strict_json(raw[FILES[3]]);sources=strict_json(raw[FILES[2]])
    require(set(peer['payloads'])==set(FILES[:5]),'five peer nonself bindings')
    require(set(author['payloads'])==set(FILES[:3]),'three author nonself bindings')
    for record in (author,peer):
        for f,v in record['payloads'].items():require(v=={'bytes':len(raw[f]),'sha256':sha256(raw[f]).hexdigest()},'payload changed '+f)
    d=BaseManuscript();d.feed(raw[FILES[0]].decode());require(not d.stack and len(d.ids)==len(set(d.ids)),'balanced unique IDs')
    ids={f'v17-c03-ex{i}' for i in range(1,9)}
    require(set(d.prompts)==set(d.solutions)==set(peer['exact_prompt_review'])==ids,'eight exact pairs/readings')
    require(d.worked==['v17-c03-case1','v17-c03-case2'],'two complete worked artifacts')
    for key in ids:
        binding=peer['exact_prompt_review'][key]
        require(binding['prompt_sha256']==sha256(d.prompts[key].encode()).hexdigest() and binding['solution_sha256']==sha256(d.solutions[key].encode()).hexdigest(),'reviewed prompt/answer changed')
    routes={'v17-c03-bok-course-design':'https://bokcenter.harvard.edu/learner-centered-design','v17-c03-bok-syllabus':'https://bokcenter.harvard.edu/syllabus-design','v17-c03-cmu-alignment':'https://www.cmu.edu/teaching/assessment/basics/alignment.html'}
    require(d.sources==routes=={s['id']:s['url'] for s in sources['sources']},'three exact scoped source routes')
    require(sources['actual_inspector']=='root','source attribution')
    require({f'v01-c{i:02}.html' for i in range(1,13)}|{'v17-c01.html','v17-c02.html'}=={x for x in d.links if not x.startswith('https://')},'all reading and prerequisite routes')
    comparisons,invalid,groups=audit(d)
    return {'chapter':'v17-c03','review':'independent internal peer','status':'passed','runtime_files':6,'worked_artifacts':2,'prompts':8,'solutions':8,'numeric_groups':groups,'comparisons':comparisons,'invalid_domains':invalid,'source_routes':3,'author_checker':'opaque hash only; never read as text/imported/executed','scope':'Full syllabus, prompts, solutions, rubrics and evidence boundaries read separately. No classroom implementation or human certification claimed.'}


if __name__=='__main__':
    check()
