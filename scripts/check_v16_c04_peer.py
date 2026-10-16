"""Independent C04 research-judgment audit; never imports author checker."""
from pathlib import Path
from hashlib import sha256
from fractions import Fraction as F
from html.parser import HTMLParser
import ast
import json
import re

FILES=('content/chapters/v16-c04.html','scripts/check_v16_c04.py','content/reviews/v16-c04-sources.json','content/reviews/v16-c04-author.json','scripts/check_v16_c04_peer.py','content/reviews/v16-c04-peer.json')

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


def mean(values):
    require(values,'nonempty population')
    return sum(values,F(0))/len(values)


def differences(before,after):
    require(len(before)==len(after)>0,'matched population')
    return tuple(y-x for x,y in zip(before,after))


def counterfactual(t0,t1,c0,c1,untreated):
    require(len(t0)==len(t1)==len(untreated)>0 and len(c0)==len(c1)>0,'counterfactual population')
    require(all(x>=0 for x in t0+t1+c0+c1+untreated),'nonnegative investment')
    effect=mean(differences(untreated,t1))
    bias=mean(differences(t0,untreated))-mean(differences(c0,c1))
    return effect,bias


def buffer_candidates(cost,capacity=F(4)):
    require(isinstance(cost,F) and cost>=0 and capacity>=0,'cost and capacity domain')
    candidates={F(0),capacity};vertex=(6-cost)/2
    if 0<=vertex<=capacity:candidates.add(vertex)
    objective=lambda b:(6-cost)*b-b*b
    value=max(map(objective,candidates));winners=[b for b in candidates if objective(b)==value]
    require(len(winners)==1,'unique constrained maximizer')
    return winners[0],value


def real_growth(nominal,prices):
    require(len(nominal)==len(prices)==2 and nominal[0]>0 and all(p>0 for p in prices) and nominal[1]>=0,'real-income domain')
    real=tuple(nominal[i]/prices[i] for i in range(2))
    return real[1]/real[0]-1


def numerical_audit(doc):
    inp={k:numeric(v) for k,v in doc.inputs.items()};actual={k:numeric(v) for k,v in doc.results.items()}
    require(set(inp)=={'investment','counterfactual-one','counterfactual-two','costs','exercise-counterfactual'},'five actual input groups')
    vals=inp['investment'];require(len(vals)==8,'eight table cells')
    table={row[0]:row[1:] for row in doc.rows if row and row[0] in ('T1','T2','C1','C2')}
    for j,key in enumerate(('T1','T2','C1','C2')):
        require(table[key]==[('Yes' if j<2 else 'No'),str(vals[2*j]),str(vals[2*j+1])],'actual investment table')
    t0=(vals[0],vals[2]);t1=(vals[1],vals[3]);c0=(vals[4],vals[6]);c1=(vals[5],vals[7])
    tchange=mean(differences(t0,t1));cchange=mean(differences(c0,c1));did=tchange-cchange
    expected={'changes':(tchange,cchange,did),'compatible-effects':counterfactual(t0,t1,c0,c1,inp['counterfactual-one'])+counterfactual(t0,t1,c0,c1,inp['counterfactual-two']),'exercise-effects':counterfactual(t0,t1,c0,c1,inp['exercise-counterfactual'])}
    # Read the extra sensitivity premise from the exact exercise, not solution outputs.
    found=re.search(r'δ∈\[([−-]?\d+),(\d+)\]',doc.prompts['v16-c04-e2']);require(found is not None,'sensitivity premise')
    low,high=(F(x.replace('−','-')) for x in found.groups());require(low<=high,'sensitivity interval')
    expected['sensitivity']=(did-high,did-low)
    for delta in (low,(low+high)/2,high):
        untreated=tuple(b+cchange+delta for b in t0)
        tau,bias=counterfactual(t0,t1,c0,c1,untreated)
        require(tau==did-delta and bias==delta,'sharp attainable counterfactual interval')
    choices=tuple(buffer_candidates(c) for c in inp['costs'])
    expected['buffers']=tuple(x[0] for x in choices);expected['objective-values']=tuple(x[1] for x in choices)
    e8=doc.prompts['v16-c04-e8'];n=re.search(r'nominal income (\d+) then(\d+) CU, with price indices(\d+) then(\d+)',e8)
    require(n is not None,'actual nominal/price input prose');numbers=tuple(F(x) for x in n.groups())
    expected['real-growth']=real_growth(numbers[:2],numbers[2:])
    require(set(expected)==set(actual),'all seven displayed outputs')
    for key,value in expected.items():require(actual[key]==value,'primitive-derived result: '+key)
    for name in ('counterfactual-one','counterfactual-two','exercise-counterfactual'):
        tau,bias=counterfactual(t0,t1,c0,c1,inp[name]);require(tau+bias==did,'DiD decomposition')
    # Alternative heterogeneous firms show result is a mean identity, not identical changes.
    a0=(F(10),F(25));a1=(F(17),F(35));b0=(F(8),F(12));b1=(F(9),F(17))
    alt_did=mean(differences(a0,a1))-mean(differences(b0,b1))
    for unknown in ((F(10),F(25)),(F(15),F(33)),(F(20),F(40))):
        effect,bias=counterfactual(a0,a1,b0,b1,unknown);require(effect+bias==alt_did,'alternative population identity')
    # Exact polynomial loss identity supports the separately read global proof.
    for c in (F(0),F(1,3),F(5),F(6),F(25,4),F(100)):
        best,value=buffer_candidates(c)
        require(best==(6-c)/2 if c<6 else best==0,'piecewise solution')
        for b in (F(0),F(1,4),F(2),F(4)):
            loss=value-((6-c)*b-b*b)
            require(loss==((b-best)**2 if c<6 else b*b+(c-6)*b) and loss>=0,'global quadratic loss certificate')
            require((loss==0)==(b==best),'strict uniqueness witness')
    require(buffer_candidates(F(0),F(1))==(F(1),F(5)),'changed capacity upper corner')
    require(buffer_candidates(F(8))==(F(0),F(0)) and (6-F(8))/2<0,'admissible counterexample')
    require(6-F(6)-2*buffer_candidates(F(6))[0]==0,'boundary FOC not interior')
    require(real_growth((F(100),F(110)),(F(100),F(100)))==F(1,10),'different inflation witness')
    invalid=[lambda:mean(()),lambda:differences((F(1),),()),lambda:counterfactual(t0,t1,c0,c1,(F(-1),F(2))),lambda:buffer_candidates(F(-1)),lambda:buffer_candidates(F(1),F(-1)),lambda:real_growth((F(1),F(2)),(F(0),F(1))),lambda:numeric('True'),lambda:numeric('__import__("os")')]
    for fn in invalid:
        try:fn()
        except ValueError:pass
        else:raise ValueError('invalid domain accepted')
    return len(inp),len(expected),len(invalid)


def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    raw={p:(root/p).read_bytes() for p in FILES};author=json.loads(raw[FILES[3]]);peer=json.loads(raw[FILES[5]])
    for record,paths in ((author,set(FILES[:3])),(peer,set(FILES[:5]))):
        bindings=record['payload_bindings'];require(len(bindings)==len(paths) and {x['path'] for x in bindings}==paths,'nonself manifest')
        for item in bindings:
            b=raw[item['path']];require(len(b)==item['bytes'] and sha256(b).hexdigest()==item['sha256'],'payload binding '+item['path'])
    doc=Manuscript();doc.feed(raw[FILES[0]].decode());require(not doc.stack and len(doc.ids)==len(set(doc.ids)),'balanced unique fragment')
    targets={f'v16-c04-e{i}' for i in range(1,9)}
    require(set(doc.prompts)==set(doc.solutions)==targets and len(doc.worked)==2,'two worked reports and eight exact solutions')
    require(set(peer['exact_prompt_review'])==targets,'full reading record')
    for key in targets:
        binding=peer['exact_prompt_review'][key]
        require(sha256(doc.prompts[key].encode()).hexdigest()==binding['prompt_sha256'] and sha256(doc.solutions[key].encode()).hexdigest()==binding['solution_sha256'],'exact prompt/solution freeze')
    sources=json.loads(raw[FILES[2]])['sources']
    require(len(sources)==3 and doc.sources=={x['id']:x['url'] for x in sources},'three exact source routes')
    require(all(s.get('inspection') and s.get('limits') for s in sources),'bounded source scopes')
    require({'v16-c02.html','curriculum.html#v16-c03','curriculum.html#v16-c05'}<=doc.links,'dependency/successor routes')
    require('v16-c04-teachback' in doc.ids and peer['open_findings']==[],'guides and findings')
    inputs,results,invalid=numerical_audit(doc)
    return {'chapter':'v16-c04','review':'independent-peer','status':'passed','worked_cases':2,'exact_solutions':8,'input_groups':inputs,'result_groups':results,'invalid_domain_rejections':invalid,'source_routes':3,'runtime_files':6,'scope':'Full constructive-report, counterfactual and global-proof reading separately recorded; table/prompt-derived arithmetic and alternative witnesses.'}


if __name__=='__main__':check()
