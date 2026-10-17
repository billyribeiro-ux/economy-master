"""Original C10 scholarly-writing arithmetic and structural audit."""
from pathlib import Path
from hashlib import sha256
from fractions import Fraction as F
from html.parser import HTMLParser
import ast
import json
import re
from decimal import Decimal, ROUND_HALF_UP

FILES=('production/v16-c10-working.html','production/check_v16_c10_working.py','production/v16-c10-sources-working.json','production/v16-c10-author-review-working.json')

def require(ok,message):
    if not ok: raise ValueError(message)


def numeric(text):
    text=text.rsplit('=',1)[-1].strip().replace('−','-')
    def walk(node):
        if isinstance(node,ast.Constant) and type(node.value) is int:return F(node.value)
        if isinstance(node,ast.Tuple):return tuple(walk(x) for x in node.elts)
        if isinstance(node,ast.UnaryOp) and isinstance(node.op,ast.USub):return -walk(node.operand)
        if isinstance(node,ast.BinOp) and isinstance(node.op,ast.Div):return walk(node.left)/walk(node.right)
        raise ValueError('restricted rational syntax')
    return walk(ast.parse(text,mode='eval').body)


class Manuscript(HTMLParser):
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


def rates(initial,final):
    require(len(initial)==len(final)>0 and all(x>0 for x in initial) and all(y>=0 for y in final),'positive baselines/nonnegative final stocks')
    return tuple((b-a)/a for a,b in zip(initial,final))


def summaries(initial,final):
    changes=rates(initial,final)
    equal=sum(changes,F(0))/len(changes)
    aggregate=(sum(final)-sum(initial))/sum(initial)
    weights=tuple(x/sum(initial) for x in initial)
    require(aggregate==sum(w*g for w,g in zip(weights,changes)),'growth weighting identity')
    return changes,equal,aggregate,weights


def rounded_percent(value):
    return str((Decimal(value.numerator)*100/Decimal(value.denominator)).quantize(Decimal('.01'),rounding=ROUND_HALF_UP))


def analyze(doc):
    table={row[0]:row[1:] for row in doc.rows if row and row[0] in ('H1','H2','L1','L2')}
    require(set(table)=={'H1','H2','L1','L2'},'complete bank input')
    population=[]
    for name in ('H1','H2','L1','L2'):
        share,before,after,group=table[name];share,before,after=map(F,(share,before,after))
        require(0<=share<=1 and group==('H' if share>=F(1,2) else 'L'),'prewindow grouping')
        population.append((name,share,before,after,group))
    def group_result(group,pop=population):
        selected=[r for r in pop if r[4]==group]
        require(len(selected)==2,'two banks in group')
        return summaries(tuple(r[2] for r in selected),tuple(r[3] for r in selected))
    high=group_result('H');low=group_result('L')
    expected={'bank-growth':high[0]+low[0],'mean-comparison':(high[1],low[1],high[1]-low[1]),'total-comparison':(high[2],low[2],high[2]-low[2])}
    revision=numeric(doc.inputs['revised-h2']);revised=[r[:3]+(revision,)+r[4:] if r[0]=='H2' else r for r in population]
    changed=group_result('H',revised)
    revised_total=sum(r[3] for r in revised if r[4]=='H')
    expected['revised-comparisons']=(changed[0][1],changed[1],changed[1]-low[1],revised_total,changed[2],changed[2]-low[2])
    expected['revised-points']=(100*(changed[1]-low[1]),100*(changed[2]-low[2]))
    # Preserve rates while changing initial bank sizes, exactly as exercise asks.
    common=F(40);same_size=[r[:2]+(common,common*(1+g),r[4]) for r,g in zip(population,high[0]+low[0])]
    h_equal=group_result('H',same_size);l_equal=group_result('L',same_size)
    expected['equal-size-contrasts']=(h_equal[1]-l_equal[1],h_equal[2]-l_equal[2])
    actual={k:numeric(v) for k,v in doc.results.items()}
    require(set(actual)==set(expected),'all displayed result groups')
    comparisons=0
    for key,value in expected.items():require(actual[key]==value,'displayed calculation '+key);comparisons+=len(value)
    # Validate the displayed main table itself, including rational percent units
    # and decimal approximation, independently of the result spans.
    rows={r[0]:r[1:] for r in doc.rows if r and r[0] in ('Mean bank growth; equal weight per bank','Growth of loan total; initial-loan weights')}
    equal_row=rows['Mean bank growth; equal weight per bank']
    parsed=tuple(F(re.search(r'[−-]?\d+(?:/\d+)?',cell).group().replace('−','-')) for cell in equal_row)
    require(parsed==tuple(100*x for x in expected['mean-comparison']),'actual mean table')
    aggregate_row=rows['Growth of loan total; initial-loan weights']
    parsed=tuple(F(re.search(r'[−-]?\d+(?:/\d+)?',cell).group().replace('−','-')) for cell in aggregate_row)
    require(parsed==tuple(100*x for x in expected['total-comparison']),'actual total table')
    require(rounded_percent(high[2]) in aggregate_row[0] and rounded_percent(high[2]-low[2]) in aggregate_row[2],'rounding in actual table')
    require(rounded_percent(changed[2]-low[2])=='5.91','revised displayed approximation')
    require(high[1]<low[1] and high[2]>low[2],'versionA sign reversal')
    require(changed[1]>low[1] and changed[2]>low[2],'versionB removes reversal')
    # Nontrivial alternatives prove the tests are not a frozen-answer dictionary.
    for scale in (F(1,1000),F(3),F(1000)):
        h0=tuple(r[2]*scale for r in population if r[4]=='H');h1=tuple(r[3]*scale for r in population if r[4]=='H')
        require(summaries(h0,h1)==high,'currency invariance');comparisons+=4
    require(summaries((F(10),F(30)),(F(12),F(36)))[1:3]==(F(1,5),F(1,5)),'common growth equality')
    alternative=summaries((F(10),F(90)),(F(20),F(81)))
    require(alternative[1]==F(9,20) and alternative[2]==F(1,100),'different weighting witness')
    require(rates((F(10),),(F(0),))==(F(-1),),'zero final stock boundary')
    for share,group in ((F(0),'L'),(F(1,2),'H'),(F(1),'H')):
        require(('H' if share>=F(1,2) else 'L')==group,'threshold boundaries');comparisons+=1
    invalid=[lambda:rates((),()),lambda:rates((F(0),),(F(1),)),lambda:rates((F(-1),),(F(1),)),lambda:rates((F(1),),(F(-1),)),lambda:rates((F(1),),(F(1),F(2))),lambda:numeric('True'),lambda:numeric('__import__("os")')]
    for fn in invalid:
        try:fn()
        except ValueError:pass
        else:raise ValueError('invalid domain accepted')
    return len(expected),comparisons,len(invalid)


def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    raw={p:(root/p).read_bytes() for p in FILES};record=json.loads(raw[FILES[3]])
    bindings=record['payload_bindings'];require(len(bindings)==3 and {x['path'] for x in bindings}==set(FILES[:3]),'three nonself bindings')
    for item in bindings:
        b=raw[item['path']];require(len(b)==item['bytes'] and sha256(b).hexdigest()==item['sha256'],'payload binding '+item['path'])
    doc=Manuscript();doc.feed(raw[FILES[0]].decode());require(not doc.stack and len(doc.ids)==len(set(doc.ids)),'balanced unique HTML')
    targets={f'v16-c10-e{i}' for i in range(1,9)}
    require(set(doc.prompts)==set(doc.solutions)==targets and len(doc.worked)==2,'two cases/eight exact solutions')
    require(set(record['exact_prompt_review'])==targets,'complete author prompt review')
    sources=json.loads(raw[FILES[2]])['sources'];require(len(sources)==2 and doc.sources=={x['id']:x['url'] for x in sources},'two exact source routes')
    require(all(s.get('inspection') and s.get('limits') for s in sources),'bounded actual source records')
    require({'curriculum.html#v16-c09','v16-c07.html','curriculum.html#v16-c11'}<=doc.links,'dependency/successor')
    require('v16-c10-teachback' in doc.ids,'teaching guides')
    require(record['open_material_findings']==[],'unresolved author finding')
    groups,comparisons,invalid=analyze(doc)
    return {'chapter':'v16-c10','status':'passed','worked_cases':2,'solutions':8,'result_groups':groups,'comparisons':comparisons,'rejected_inputs':invalid,'runtime_files':4,'qualitative_scope':'Full compact-paper and revision-artifact author reading recorded; independent peer/root review required.'}


if __name__=='__main__':check()
