"""Independent C12 peer audit: raw-table oracle; author checker opaque."""
from pathlib import Path
from hashlib import sha256
from fractions import Fraction as F
from html.parser import HTMLParser
import ast
import json
import contextlib
import io

FILES=('content/chapters/v16-c12.html','scripts/check_v16_c12.py','content/reviews/v16-c12-sources.json','content/reviews/v16-c12-author.json','scripts/check_v16_c12_peer.py','content/reviews/v16-c12-peer.json')

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


class Manuscript(BaseManuscript):
    def __init__(self):
        super().__init__();self.blocks={}
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if a.get('id') in ('v16-c12-program','v16-c12-transcript'):self.blocks[a['id']]=''
        super().handle_starttag(tag,attrs)
    def handle_data(self,text):
        for tag,a in self.stack:
            if a.get('id') in self.blocks:self.blocks[a['id']]+=text
        super().handle_data(text)


def oracle(values):
    """Partition observed bank/date records, never impute missing cells."""
    require(len(values)==6 and all(type(x) is int and x>=0 for x in values),'six nonnegative integers')
    a0,a1,b0,b1,c0,d1=values
    require(a0>0 and b0>0,'positive matched baselines')
    dates=({'A':a0,'B':b0,'C':c0},{'A':a1,'B':b1,'D':d1})
    common=dates[0].keys() & dates[1].keys()
    raw=tuple(sum(d.values()) for d in dates)
    matched=tuple(sum(d[k] for k in common) for d in dates)
    equal=sum((F(dates[1][k],dates[0][k])-1 for k in common),F(0))/len(common)
    result=raw+matched+(F(raw[1],raw[0])-1,F(matched[1],matched[0])-1,equal)
    decomposition=(matched[1]-matched[0],sum(v for k,v in dates[1].items() if k not in common),-sum(v for k,v in dates[0].items() if k not in common),raw[1]-raw[0])
    require(sum(decomposition[:3])==decomposition[3],'partition identity')
    return result,decomposition


def score(weights,scores):
    require(len(weights)==len(scores)==5 and all(type(w) is int and w>0 for w in weights) and sum(weights)==100,'weights')
    require(all(type(s) is int and 0<=s<=4 for s in scores),'scores')
    return sum((F(w*s,4) for w,s in zip(weights,scores)),F(0))


def ready(scores,complete,critical):
    require(len(scores)==5 and all(type(s) is int and 0<=s<=4 for s in scores),'scores')
    require(type(complete) is bool and type(critical) is bool,'gate booleans')
    return min(scores)>=3 and complete and not critical


def numerical_audit(doc):
    rows={row[0]:row[1:3] for row in doc.rows if row and row[0] in ('A','B','C','D')}
    require(set(rows)==set('ABCD') and rows['C'][1]==rows['D'][0]=='Absent','raw observed perimeter')
    v=tuple(int(rows[k][t]) for k,t in (('A',0),('A',1),('B',0),('B',1),('C',0),('D',1)))
    require(numeric(doc.inputs['ledger'])==v,'tuple versus actual source table')
    newer,bridge=oracle(v);old=v[:3]+(55,)+v[4:];older,_=oracle(old)
    weights=tuple(map(int,numeric(doc.inputs['weights'])))
    initial=tuple(map(int,numeric(doc.inputs['initial-scores'])))
    revised=tuple(map(int,numeric(doc.inputs['revised-scores'])))
    hours=tuple(map(int,numeric(doc.inputs['hours'])))
    require(hours==(120,60,20,20,20),'actual agenda constraints')
    alternative=v[:-1]+(50,)
    expected={'ledger':newer,'bridge':bridge,'old-release':older,'initial-score':score(weights,initial),'revised-score':score(weights,revised),'hours':sum(hours[1:]),'ex1':oracle(alternative)[0][4:],'ex4':tuple(a-b for a,b in zip(newer[4:],older[4:])),'ex5':(score(weights,(4,4,4,1,4)),score(weights,(3,3,3,3,3))),'ex7':(60,0,20,30,10)}
    require(set(doc.results)==set(expected),'all result groups covered')
    comparisons=0
    def equal(a,b,label):
        nonlocal comparisons
        require(a==b,label);comparisons+=1
    for k,val in expected.items():equal(numeric(doc.results[k]),val,'result '+k)
    equal(sum(expected['ex7']),hours[0],'revised total');equal(30-hours[-1],10,'new access shortfall')
    equal(ready(initial,True,False),False,'initial domain failures')
    equal(ready(revised,True,False),True,'revised internal gate')
    equal(ready(revised,True,True),False,'critical issue overrides scores')
    equal(ready(revised,False,False),False,'incomplete release')
    equal(ready((4,4,4,1,4),True,True),False,'high average fails')
    equal(ready((3,3,3,3,3),True,False),True,'all domains minimum')
    equal(score(weights,(0,0,0,0,0)),0,'bottom anchor');equal(score(weights,(4,4,4,4,4)),100,'top anchor')
    # Actual reader program is self-contained and was read in full. The above
    # independently persisted bank/date oracle precedes any inline execution.
    out=io.StringIO();err=io.StringIO();ns={'__name__':'__main__'}
    with contextlib.redirect_stdout(out),contextlib.redirect_stderr(err):
        exec(compile(doc.blocks['v16-c12-program'],'<actual-reader-program>','exec'),ns)
    transcript={'v1':list(map(str,older)),'v2':list(map(str,newer)),'bridge_v2':list(map(str,bridge))}
    equal(err.getvalue(),'','reader stderr');equal(json.loads(out.getvalue()),transcript,'actual reader stdout')
    equal(json.loads(doc.blocks['v16-c12-transcript']),transcript,'displayed transcript')
    equal(ns['v2'],v,'actual inline primitives');equal(ns['v1'],old,'old inline primitives')
    alternatives=[alternative,(10,0,20,0,0,0),(5,10,5,0,0,0),(10,9,10,11,7,7),(100,110,10,8,1,50)]
    for data in [v,old]+alternatives:
        result,parts=oracle(data)
        equal(ns['ledger'](data),result,'reader arithmetic versus independent records')
        equal(ns['bridge'](data),parts,'reader bridge versus partition')
        scaled=tuple(x*7 for x in data)
        equal(oracle(scaled)[0][4:],result[4:],'common scaling of rates')
    equal(oracle((10,0,20,0,0,0))[0][4:],(F(-1),F(-1),F(-1)),'zero final boundary')
    equal(oracle((5,10,5,0,0,0))[0][5:],(F(0),F(0)),'equal sizes make weighting equivalent')
    invalid=[(),(0,1,1,1,0,0),(1,1,0,1,0,0),(1,-1,1,1,0,0),(True,1,1,1,0,0),(1.0,1,1,1,0,0)]
    rejected=0
    for bad in invalid:
        for fn in (oracle,ns['ledger'],ns['bridge']):
            try:fn(bad)
            except ValueError:rejected+=1
            else:raise ValueError('invalid ledger accepted')
    for fn in (lambda:score(weights,(3,3,3,3,5)),lambda:score((25,25,20,15,14),revised),lambda:ready(revised,1,False)):
        try:fn()
        except ValueError:rejected+=1
        else:raise ValueError('invalid rubric accepted')
    return comparisons,rejected,len(expected),len(alternatives)


def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    raw={p:(root/p).read_bytes() for p in FILES};author=json.loads(raw[FILES[3]]);peer=json.loads(raw[FILES[5]])
    require(set(author['payloads'])==set(FILES[:3]),'author three nonself bindings')
    for name,item in author['payloads'].items():
        require(len(raw[name])==item['bytes'] and sha256(raw[name]).hexdigest()==item['sha256'],'author freeze '+name)
    require(set(peer['payloads'])==set(FILES[:5]),'peer five nonself bindings')
    for name,item in peer['payloads'].items():
        require(len(raw[name])==item['bytes'] and sha256(raw[name]).hexdigest()==item['sha256'],'peer freeze '+name)
    doc=Manuscript();doc.feed(raw[FILES[0]].decode());require(not doc.stack and len(doc.ids)==len(set(doc.ids)),'balanced unique fragment')
    targets={f'v16-c12-ex{i}' for i in range(1,9)}
    require(set(doc.prompts)==set(doc.solutions)==targets and len(doc.worked)==2,'two complete artifacts/eight solutions')
    require(set(peer['exact_prompt_review'])==targets,'eight reading records')
    for k in targets:
        item=peer['exact_prompt_review'][k]
        require(sha256(doc.prompts[k].encode()).hexdigest()==item['prompt_sha256'] and sha256(doc.solutions[k].encode()).hexdigest()==item['solution_sha256'],'exact prompt/solution binding')
    sources=json.loads(raw[FILES[2]])
    require(sources['actual_inspector']=='root' and doc.sources=={s['id']:s['url'] for s in sources['sources']},'attributed source routes')
    require(len(doc.sources)==2 and all(s['inspection'] and s['limits'] for s in sources['sources']),'bounded sources')
    require({'v16-c11.html','v16-c10.html','assessments.html#research-portfolio'}<=doc.links and 'v16-c12-retention' in doc.ids,'dependency and guides')
    require(peer['open_material_findings']==[],'open findings')
    count,bad,groups,alternatives=numerical_audit(doc)
    return {'chapter':'v16-c12','review':'independent-peer','status':'passed','runtime_files':6,'worked_artifacts':2,'exact_solutions':8,'result_groups':groups,'comparisons':count,'invalid_domain_rejections':bad,'alternative_ledgers':alternatives,'inline_program':'actual execution matched independent raw-table oracle and transcript','qualitative_scope':'Complete portfolio, contribution, ethics/access, mock evaluation and agenda read separately; no external human or rendered UI review claimed.'}

if __name__=='__main__':check()
