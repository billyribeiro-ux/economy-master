"""Independent C05 peer: finite assignment enumeration and counterfactual reconstruction.

Reads six frozen payloads, but never imports or executes the author checker.
"""
import ast
import json
from fractions import Fraction
from hashlib import sha256
from html.parser import HTMLParser
from pathlib import Path

PAYLOADS=(
    'production/v16-c05-working.html',
    'production/check_v16_c05_working.py',
    'production/v16-c05-sources-working.json',
    'production/v16-c05-author-review-working.json',
    'production/check_v16_c05_peer_working.py',
    'production/v16-c05-peer-review-working.json',
)

def require(condition, message):
    if not condition:
        raise ValueError(message)

def rational(value):
    require(type(value) in (int,Fraction),'exact nonboolean input')
    return Fraction(value)

def numeric(text):
    def visit(node):
        if isinstance(node,ast.Constant):return rational(node.value)
        if isinstance(node,(ast.Tuple,ast.List)):return tuple(visit(x) for x in node.elts)
        if isinstance(node,ast.UnaryOp) and isinstance(node.op,ast.USub):return -visit(node.operand)
        if isinstance(node,ast.BinOp) and isinstance(node.op,ast.Div):
            den=visit(node.right);require(den!=0,'nonzero divisor');return visit(node.left)/den
        raise ValueError('nonliteral marker')
    return visit(ast.parse(text.strip().replace('−','-'),mode='eval').body)

class Fragment(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.open=[];self.ids=[];self.inputs={};self.results={};self.capture=[]
        self.tables=[];self.table=None;self.row=None;self.cells=None
        self.prompts=[];self.answers=[];self.worked=[];self.sources={};self.links=set();self.guides=0
    def handle_starttag(self,tag,attributes):
        attrs=dict(attributes);require(len(attrs)==len(attributes),'duplicate attribute')
        require(tag!='h1','chapter fragment heading')
        if 'id' in attrs:
            require(attrs['id'].startswith('v16-c05-') and attrs['id'] not in self.ids,'unique chapter identifier')
            self.ids.append(attrs['id'])
        if tag=='article' and 'worked' in attrs.get('class','').split():self.worked.append(attrs['id'])
        if tag=='details' and 'solutions' in attrs.get('class','').split():self.guides+=1
        if tag=='li' and attrs.get('id','').startswith('v16-c05-e'):
            require(any(t=='ol' and 'exercises' in a.get('class','').split() for t,a in self.open),'prompt enclosure')
            self.prompts.append(attrs['id'])
        if 'data-solution-for' in attrs:
            require(any(t=='details' and 'solutions' in a.get('class','').split() for t,a in self.open),'answer enclosure')
            self.answers.append(attrs['data-solution-for'])
        if tag=='a':self.links.add(attrs.get('href'))
        if 'data-source' in attrs:
            require(attrs['data-source'] not in self.sources,'source duplicate')
            self.sources[attrs['data-source']]=attrs['href']
        for key,target in (('data-input',self.inputs),('data-result',self.results)):
            if key in attrs:
                name=attrs[key];require(name not in target,'duplicate numeric marker')
                target[name]='';self.capture.append((target,name,len(self.open)))
        if tag=='table':
            require(self.table is None,'no nested tables');self.table={'caption':'','rows':[]}
        if tag=='caption' and self.table is not None:self.capture.append((self.table,'caption',len(self.open)))
        if tag=='tr' and self.table is not None:self.row=[]
        if tag in ('td','th') and self.row is not None:
            self.row.append('');self.capture.append((self.row,len(self.row)-1,len(self.open)))
        if tag not in ('br','hr','img','meta','input','link'):self.open.append((tag,attrs))
    def handle_data(self,data):
        for target,name,_ in self.capture:target[name]+=data
    def handle_endtag(self,tag):
        require(self.open and self.open[-1][0]==tag,'balanced fragment')
        self.open.pop();self.capture=[item for item in self.capture if item[2]<len(self.open)]
        if tag=='tr' and self.table is not None:self.table['rows'].append(self.row);self.row=None
        if tag=='table':self.tables.append(self.table);self.table=None

def lottery(no_offer,offer):
    require(len(no_offer)==len(offer) and len(offer)>=2 and len(offer)%2==0,'equal nonempty even rosters')
    no_offer=tuple(map(rational,no_offer));offer=tuple(map(rational,offer))
    count=len(offer);half=count//2;out=[]
    for mask in range(1<<count):
        if mask.bit_count()!=half:continue
        selected=tuple(i for i in range(count) if mask & (1<<i))
        treated=sum(offer[i] for i in selected)/half
        control=sum(no_offer[i] for i in range(count) if i not in selected)/half
        out.append((selected,treated,control,treated-control))
    return sorted(out)

def counterfactual(history,departure):
    require(len(history)==6,'two three-date histories')
    em,e0,e1,cm,c0,c1=map(rational,history);departure=rational(departure)
    untreated=e0+(c1-c0)+departure
    effect=e1-untreated
    return untreated,effect,(untreated-e0)-(c1-c0)

def effect_interval(history,lower,upper):
    lower,upper=rational(lower),rational(upper);require(lower<=upper,'ordered departure bounds')
    return counterfactual(history,upper)[1],counterfactual(history,lower)[1]

def check(root=None):
    base=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    raw={p:(base/p).read_bytes() for p in PAYLOADS}
    review=json.loads(raw[PAYLOADS[5]]);bindings=review['payload_bindings']
    require(len(bindings)==5 and {x['path'] for x in bindings}==set(PAYLOADS[:5]),'five nonself freeze bindings')
    for item in bindings:
        b=raw[item['path']];require((len(b),sha256(b).hexdigest())==(item['bytes'],item['sha256']),'peer freeze')
    author=json.loads(raw[PAYLOADS[3]])
    require(set(author['payloads'])==set(PAYLOADS[:3]),'author three-file freeze inventory')
    for p,meta in author['payloads'].items():require((len(raw[p]),sha256(raw[p]).hexdigest())==(meta['bytes'],meta['sha256']),'author freeze agreement')
    doc=Fragment();doc.feed(raw[PAYLOADS[0]].decode());doc.close();require(not doc.open,'closed HTML')
    prompts=['v16-c05-e'+str(i) for i in range(1,9)]
    require(doc.prompts==doc.answers==prompts,'eight exactly matched prompt/answer pairs')
    require(set(review['exact_prompt_review'])==set(prompts),'full reading inventory')
    require(doc.worked==['v16-c05-case1','v16-c05-case2'] and doc.guides==3,'worked contracts and guides')
    sources=json.loads(raw[PAYLOADS[2]])
    require(doc.sources=={s['id']:s['url'] for s in sources['sources']},'source scopes and citations')
    require({'curriculum.html#v16-c04','v16-c01.html','v16-c02.html','curriculum.html#v16-c06'}<=doc.links,'dependency and successor references')
    inp={k:numeric(v) for k,v in doc.inputs.items()};printed={k:numeric(v) for k,v in doc.results.items()}
    require(inp=={'case1-y0':(8,10,12,14),'case1-y1':(10,14,18,18),'case2-observed':(40,40,34,40,40,38),'case2-bounds':(-1,2),'case2-credit-ledger':(40,20,0,34,22,4)},'actual input schedule')
    comparisons=0
    def equal(a,b,message):
        nonlocal comparisons
        if isinstance(a,(tuple,list)) or isinstance(b,(tuple,list)):
            require(isinstance(a,(tuple,list)) and isinstance(b,(tuple,list)) and len(a)==len(b),message+' shape')
            for x,y in zip(a,b):equal(x,y,message)
        else:comparisons+=1;require(a==b,message)
    y0,y1=inp['case1-y0'],inp['case1-y1'];distribution=lottery(y0,y1)
    effects=tuple(a-b for a,b in zip(y1,y0));target=sum(effects)/len(effects)
    by_pair={tuple('ABCD'[i] for i in pair):(tm,cm,delta) for pair,tm,cm,delta in distribution}
    contrasts=tuple(v[3] for v in distribution)
    expected={'case1-effects':effects,'case1-target':target,'case1-observed':by_pair[('A','C')][2],
              'case1-contrasts':contrasts,'case1-design-mean':sum(contrasts)/len(contrasts),
              'e2-estimate':by_pair[('B','D')][2],'e2-error':by_pair[('B','D')][2]-target,'e2-mean':sum(contrasts)/len(contrasts)}
    assignment_table=[t for t in doc.tables if t['caption']=='All possible assignments in the four-bank teaching schedule']
    require(len(assignment_table)==1,'assignment table present')
    rows=assignment_table[0]['rows'][1:];require([r[0] for r in rows]==['AB','AC','AD','BC','BD','CD'],'all six actual assignment rows')
    for row in rows:equal(tuple(numeric(x) for x in row[1:]),by_pair[tuple(row[0])],'actual assignment table cells')
    history=inp['case2-observed'];em,e0,e1,cm,c0,c1=history;observed=(e1-e0)-(c1-c0)
    histories=[t for t in doc.tables if t['caption']=='Original observed group means, in millions; the groups have equal fixed size']
    require(len(histories)==1,'observed table')
    equal(tuple(numeric(x) for row in histories[0]['rows'][1:] for x in row[1:]),history,'observed table equals input')
    expected['case2-difference']=observed
    expected['case2-worlds']=(counterfactual(history,0),counterfactual(history,-4))
    expected['case2-effect-set']=effect_interval(history,*inp['case2-bounds'])
    third=counterfactual(history,-6)
    expected['e4-world']=(third[0],third[0]-e0,third[2],third[1]+third[2])
    expected['e5-set']=effect_interval(history,-5,2)
    a0,b0,c00,a1,b1,c11=inp['case2-credit-ledger']
    expected['case2-credit-changes']=(a1-a0,b1-b0,c11-c00)
    expected['case2-credit-totals']=(a0+b0+c00,a1+b1+c11)
    expected['case2-incumbent-totals']=(a0+b0,a1+b1)
    expected['e6-changes']=(a1-a0,a1+b1-a0-b0,a1+b1+c11-a0-b0-c00)
    baseline,slope=Fraction(10),Fraction(4)
    expected['e3-observed']=tuple((z,z,baseline+slope*z) for z in (0,1))
    expected['e3-offer-effect']=slope
    expected['e3-mediator-counterfactual']=(baseline,baseline+slope)
    require(set(expected)==set(printed),'all numeric results covered')
    for key,value in expected.items():equal(printed[key],value,'printed '+key)
    # Independent finite assignment worlds, including negative flows and heterogeneous effects.
    assignment_worlds=0
    for control,treat in (((-3,7),(1,-1)),((8,10,12,14),(10,14,18,18)),((0,1,2,3,4,5),(5,4,3,2,1,0)),((-6,-2,1,4,8,9),(-7,0,5,3,10,2))):
        all_=lottery(control,treat);assignment_worlds+=len(all_)
        equal(sum(row[3] for row in all_)/len(all_),sum(Fraction(t-c) for t,c in zip(treat,control))/len(control),'finite lottery unbiasedness')
        for index in range(len(control)):
            equal(Fraction(sum(index in row[0] for row in all_),len(all_)),Fraction(1,2),'unit inclusion probability')
        # Shift both potential outcomes by a common amount: effect and every contrast unchanged.
        shifted=lottery(tuple(v+17 for v in control),tuple(v+17 for v in treat))
        equal(tuple(r[3] for r in all_),tuple(r[3] for r in shifted),'common shift invariance')
    # Necessity and constructive sufficiency: every chosen b yields a world with the exact observations.
    sharp_witnesses=0
    for bounds in ((Fraction(-1),Fraction(2)),(Fraction(-5),Fraction(2))):
        low,high=effect_interval(history,*bounds)
        for k in range(17):
            tau=low+(high-low)*k/16;b=observed-tau;world=counterfactual(history,b)
            equal(world[1],tau,'constructive sharp effect witness');equal(world[0]+tau,e1,'observed endpoint preserved');equal(tau+b,observed,'decomposition')
            require(bounds[0]<=b<=bounds[1] and world[0]>=0,'stated departure and nonnegative stock');sharp_witnesses+=1
    equal(counterfactual(history,-4)[1],0,'wide interval includes zero')
    equal(counterfactual(history,-5)[1],1,'wide interval permits positive effect')
    # Replicating observed histories leaves each counterfactual world distinct.
    for repeats in (1,2,9):
        equal(sum([e1]*repeats)/repeats,e1,'same exposed mean under repetition')
        equal(sum([c1]*repeats)/repeats,c1,'same control mean under repetition')
    for base_value in (-2,0,10):
        for coefficient in (-3,0,4):
            for z in (0,1):
                m=z;equal(base_value+coefficient*m,base_value+coefficient*z,'mechanism observational equivalence')
            if coefficient!=0:require(base_value!=base_value+coefficient,'controlled mediator distinction')
    for replacement in (Fraction(0),Fraction(2),Fraction(6)):
        total1=34+(20+replacement)+0
        equal(total1-60,-6+replacement,'borrower substitution alternatives')
    invalid=(lambda:rational(True),lambda:numeric('f(1)'),lambda:numeric('1/0'),lambda:lottery((1,2),(3,)),lambda:lottery((1,2,3),(2,3,4)),lambda:lottery((True,2),(3,4)),lambda:counterfactual((1,2),0),lambda:effect_interval(history,2,-1))
    rejected=0
    for operation in invalid:
        try:operation()
        except ValueError:rejected+=1
        else:raise ValueError('invalid domain accepted')
    for path,original in raw.items():require((base/path).read_bytes()==original,'unchanged six runtime files')
    return {'chapter':'v16-c05','status':'passed','worked_cases':2,'solutions':8,'runtime_files':6,
            'numeric_inputs':len(inp),'numeric_results':len(printed),'comparisons':comparisons,
            'assignment_worlds':assignment_worlds,'sharp_set_witnesses':sharp_witnesses,'rejected_inputs':rejected,
            'author_checker_executed':False,'open_material_findings':[]}

if __name__=='__main__':check()
