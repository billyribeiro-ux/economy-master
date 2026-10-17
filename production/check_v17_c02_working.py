"""C02 author checks: representation-preserving exact arithmetic and assignment law."""
from pathlib import Path
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from itertools import combinations
import ast
import json
import re

FILES=('production/v17-c02-working.html','production/check_v17_c02_working.py','production/v17-c02-sources-working.json','production/v17-c02-author-review-working.json')
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


def capacity(money,price):
    require(money>=0 and price>0,'nonnegative balance/positive price')
    return money/price


def real_growth(r,pi):
    require(r>=-1 and pi>-1,'growth domain')
    return (1+r)/(1+pi)-1


def bank_effects(schedule):
    require(len(schedule)>=2 and len(schedule)%2==0,'even nonempty roster')
    require(all(len(pair)==2 and all(type(y) is int and y in (0,1) for y in pair) for pair in schedule.values()),'complete binary potential outcomes')
    return sum((F(y1-y0) for y0,y1 in schedule.values()),F(0))/len(schedule)


def contrast(schedule,treated):
    bank_effects(schedule)
    require(len(treated)==len(set(treated))==len(schedule)//2 and set(treated)<=schedule.keys(),'fixed half-roster assignment')
    return sum((F(schedule[k][1]) for k in treated),F(0))/len(treated)-sum((F(v[0]) for k,v in schedule.items() if k not in treated),F(0))/(len(schedule)-len(treated))


def audit(d):
    inputs={k:numeric(v) for k,v in d.inputs.items()};counts=0
    def eq(a,b,label):
        nonlocal counts
        require(a==b,label);counts+=1
    dated={r[0]:tuple(numeric(v) for v in r[1:]) for r in d.rows if len(r)==4 and r[0] in ('0','1')}
    require(set(dated)=={'0','1'},'two date inputs')
    M0,P0,Q0=dated['0'];M1,P1,Q1=dated['1'];eq(capacity(M0,P0),Q0,'actual initial table');eq(capacity(M1,P1),Q1,'actual final table')
    r,pi=M1/M0-1,P1/P0-1;g=real_growth(r,pi)
    eq(g,Q1/Q0-1,'ratio versus directbasketgrowth')
    for row in d.rows:
        if len(row)==2:
            try:price,q=map(numeric,row)
            except (ValueError,SyntaxError):continue
            eq(capacity(M1,price),q,'actual conditionalcapacitytable')
    raw={r[0]:tuple(int(v) for v in r[1:]) for r in d.rows if len(r)==4 and r[0] in ('A','B','C','D')}
    require(set(raw)==set('ABCD'),'fourbank potentials')
    schedule={k:v[:2] for k,v in raw.items()}
    for k,v in raw.items():eq(v[2],v[1]-v[0],'actualindividualeffectcolumn')
    tau=bank_effects(schedule);pairs=list(combinations(sorted(schedule),2));values=tuple(contrast(schedule,pair) for pair in pairs)
    table={tuple(r[0].split(',')):numeric(r[1]) for r in d.rows if len(r)==2 and re.fullmatch('[ABCD],[ABCD]',r[0])}
    eq(table,dict(zip(pairs,values)),'all six actualassignmentrows')
    realized=[r for r in d.rows if len(r)==4 and r[0].startswith(('Invited','Control'))];require(len(realized)==2,'actualobservedtable')
    for row,want in zip(realized,((1,2,F(1,2)),(2,2,F(1)))):eq(tuple(numeric(x) for x in row[1:]),want,'observedcounts/rates')
    r1=inputs['e1-money']/M0-1;p1=inputs['e1-price']/P0-1;e3r,e3pi=inputs['e3-r'],inputs['e3-pi'];e3g=real_growth(e3r,e3pi)
    changed=[pair for pair in pairs if 'A' in pair];change_avg=sum((contrast(schedule,pair) for pair in changed),F(0))/len(changed)
    pA=F(sum('A'in pair for pair in pairs),len(pairs));givenB=[pair for pair in pairs if 'B'in pair];pAgivenB=F(sum('A'in pair for pair in givenB),len(givenB))
    cash,inflow,outflow=inputs['e8-cash']
    want={'case1-rates':(r,pi,g),'approximation-error':g-(r-pi),'roster-effect':tau,'realized-contrast':contrast(schedule,('A','B')),'assignment-average':sum(values,F(0))/len(values),'e1':(Q0,capacity(inputs['e1-money'],inputs['e1-price']),r1,p1,real_growth(r1,p1)),'e2':tuple(capacity(M1,p) for p in inputs['e2-prices']),'e3':(e3g,e3r-e3pi,100*(e3g-(e3r-e3pi))),'e5':(contrast(schedule,('A','C')),tau),'e6':(change_avg,tau,change_avg-tau),'e7':(pA,pAgivenB),'e8':(inflow-outflow,cash+inflow-outflow)}
    actual={k:numeric(v) for k,v in d.results.items()};eq(set(actual),set(want),'everydisplayedgroup')
    for k,v in want.items():eq(actual[k],v,'result '+k)
    cashrows={r[0]:numeric(r[1]) for r in d.rows if len(r)==2 and r[0] in ('Starting stock C₀','Net cash change I−O','Ending stock C₁')}
    eq(cashrows,{'Starting stock C₀':cash,'Net cash change I−O':inflow-outflow,'Ending stock C₁':cash+inflow-outflow},'actualcashtable')
    # Numbers in explanatory speech, boundaries and delayed guide.
    eq(capacity(F(10),F(2)),5,'firstcheck');eq(M1*(1-pi),165,'misleadingbucketnumber')
    eq(capacity(M1,P0),110,'e4changedprice');eq((capacity(F(150),F(3)),capacity(F(165),F(33,10))),(F(50),F(50)),'delayedcapacities')
    eq(real_growth(F(1,10),F(1,10)),0,'delayedgrowth')
    # Original analogy/algebra error identity and meaningful alternative cases.
    for r0,p0 in ((F(1,20),F(1,50)),(F(0),F(-1,5)),(F(-1),F(1,3)),(F(2,5),F(0)),(F(1,7),F(1,7))):
        value=real_growth(r0,p0)
        eq(value-(r0-p0),-p0*(r0-p0)/(1+p0),'generalapproximationerror')
        eq(value,capacity(F(100)*(1+r0),F(2)*(1+p0))/capacity(F(100),F(2))-1,'directquantityreconstruction')
    eq(capacity(F(0),F(2)),0,'zerofinalcapacity')
    for money in (F(0),F(2),F(100)):
        require(capacity(money,F(3))<=capacity(money,F(2)),'fullpriceorderwitness');counts+=1
    for factor in (F(1,100),F(1000)):
        eq(capacity(M1*factor,P1*factor),Q1,'commoncurrencyscale')
    alternative_schedules=[{'A':(0,0),'B':(1,1)}, {'A':(0,1),'B':(0,1)}, {'A':(1,0),'B':(1,0),'C':(0,0),'D':(1,1)}]
    for alt in alternative_schedules:
        combos=list(combinations(sorted(alt),len(alt)//2));avg=sum((contrast(alt,c) for c in combos),F(0))/len(combos)
        eq(avg,bank_effects(alt),'uniformexpectationalternative')
    eq(F(sum('A'in p for p in changed),len(changed)),1,'biasedinclusionA')
    for k in 'BCD':eq(F(sum(k in p for p in changed),len(changed)),F(1,3),'biasedotherinclusion')
    invalid=[lambda:capacity(F(1),F(0)),lambda:capacity(F(-1),F(1)),lambda:real_growth(F(0),F(-1)),lambda:real_growth(F(-2),F(0)),lambda:bank_effects({}),lambda:bank_effects({'A':(0,1)}),lambda:bank_effects({'A':(0,1),'B':(0,None)}),lambda:bank_effects({'A':(0,1),'B':(0,2)}),lambda:contrast(schedule,('A','A')),lambda:contrast(schedule,('A','X')),lambda:contrast(schedule,('A',))]
    for fn in invalid:
        try:fn()
        except ValueError:pass
        else:raise ValueError('invaliddomainaccepted')
    return counts,len(invalid),len(want)


def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    raw={name:(root/name).read_bytes() for name in FILES};review=json.loads(raw[FILES[3]])
    require(set(review['payloads'])==set(FILES[:3]),'threenonselfbindings')
    for name,v in review['payloads'].items():require(v['bytes']==len(raw[name]) and v['sha256']==sha256(raw[name]).hexdigest(),'bound '+name)
    d=BaseManuscript();d.feed(raw[FILES[0]].decode());require(not d.stack and len(d.ids)==len(set(d.ids)),'balanceduniquefragment')
    ids={f'v17-c02-e{i}' for i in range(1,9)};require(set(d.prompts)==set(d.solutions)==set(review['exact_prompt_review'])==ids and len(d.worked)==2,'twolessons/eightfullpairs')
    for k in ids:
        v=review['exact_prompt_review'][k];require(v['prompt_sha256']==sha256(d.prompts[k].encode()).hexdigest() and v['solution_sha256']==sha256(d.solutions[k].encode()).hexdigest(),'readingbinding')
    sources=json.loads(raw[FILES[2]])['sources'];require(len(sources)==2 and d.sources=={s['id']:s['url'] for s in sources},'twoboundedprimaryguidanceroutes')
    require(all(s['actual_primary_inspector'] and s['inspection'] and s['limits'] for s in sources),'inspectionattribution')
    require({'curriculum.html#v17-c01','v16-c05.html','curriculum.html#v17-c03'}<=d.links and 'v17-c02-teachback' in d.ids,'prerequisite/successor/guides')
    require(review['open_material_findings']==[],'openfindings')
    count,bad,groups=audit(d)
    return {'chapter':'v17-c02','status':'passed','runtime_files':4,'worked_lessons':2,'exact_solutions':8,'numeric_groups':groups,'comparisons':count,'invalid_domain_rejections':bad,'scope':'Full explanations/analogies/learner-dialogue/derivations read separately; original synthetic instruction, not observed teaching efficacy.'}

if __name__=='__main__':check()
