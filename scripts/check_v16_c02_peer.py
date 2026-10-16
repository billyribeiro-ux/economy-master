"""Independent C02 literature-instruction audit; never imports author checker."""
from pathlib import Path
from hashlib import sha256
from fractions import Fraction as F
from html.parser import HTMLParser
import ast
import json

FILES=('content/chapters/v16-c02.html','scripts/check_v16_c02.py','content/reviews/v16-c02-sources.json','content/reviews/v16-c02-author.json','scripts/check_v16_c02_peer.py','content/reviews/v16-c02-peer.json')

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


def observations(exposure, beta, common, demand):
    require(len(exposure)==2 and len(common)==2 and len(demand)==4,'two-firm two-bank domain')
    require(all(isinstance(x,F) for x in exposure+(beta,)+common+demand),'exact rational domain')
    return tuple(common[f]+beta*exposure[b]+demand[2*f+b] for f in range(2) for b in range(2))


def differences(values):
    require(len(values)==4,'four relationship outcomes')
    return tuple(values[2*i]-values[2*i+1] for i in range(2))


def ratios(exposure, values):
    require(len(exposure)==2 and exposure[0]!=exposure[1],'nonzero exposure contrast')
    return tuple(d/(exposure[0]-exposure[1]) for d in differences(values))


def numerical_audit(doc):
    inputs={k:numeric(v) for k,v in doc.inputs.items()};actual={k:numeric(v) for k,v in doc.results.items()}
    require(set(inputs)=={'baseline','demand','exercise-demand','exercise-common'},'four exact input groups')
    xa,xb,beta,a1,a2=inputs['baseline'];x=(xa,xb);a=(a1,a2);zero=(F(0),)*4
    baseline=observations(x,beta,a,zero);demand=observations(x,beta,a,inputs['demand'])
    e3=observations(x,beta,inputs['exercise-common'],zero);e4=observations(x,beta,a,inputs['exercise-demand'])
    expected={'baseline-y':baseline,'baseline-differences':differences(baseline),'baseline-slopes':ratios(x,baseline),'demand-y':demand,'demand-comparison':differences(demand)+ratios(x,demand),'e3-y':e3,'e3-slopes':ratios(x,e3),'e4-y':e4,'e4-slopes':ratios(x,e4)}
    require(set(actual)==set(expected),'nine result groups')
    for key,value in expected.items():require(actual[key]==value,'displayed reconstruction: '+key)
    require(observations(x,ratios(x,demand)[0],a,zero)==demand,'first observational equivalence')
    require(observations(x,ratios(x,e4)[0],a,zero)==e4,'exercise observational equivalence')
    # A second population and arbitrary rational effects demonstrate the identity,
    # rather than merely replaying the shown parameters.
    altx=(F(3,2),F(-1,2));altbeta=F(-7,3);alta=(F(11),F(-8))
    common_shock=(F(5),F(5),F(-2),F(-2))
    y=observations(altx,altbeta,alta,common_shock)
    require(ratios(altx,y)==(altbeta,altbeta),'common borrower shock cancels')
    relationship_shock=(F(1),F(0),F(0),F(3))
    z=observations(altx,altbeta,alta,relationship_shock)
    require(ratios(altx,z)==tuple(altbeta+u/(altx[0]-altx[1]) for u in differences(relationship_shock)),'general omitted-demand identity')
    require(ratios(altx,z)[0]!=ratios(altx,z)[1],'heterogeneous apparent response')
    # For arbitrary candidate beta, u can absorb the difference in every cell.
    for candidate in (F(-20),F(0),F(13,7)):
        remainder=tuple((altbeta-candidate)*altx[b]+relationship_shock[2*f+b] for f in range(2) for b in range(2))
        require(observations(altx,candidate,alta,remainder)==z,'unrestricted demand prevents identification')
    for shift in (F(-100),F(0),F(1,3)):
        moved=tuple(ai+shift for ai in alta)
        require(ratios(altx,observations(altx,altbeta,moved,zero))==(altbeta,altbeta),'common-effect invariance')
    require(observations((F(0),F(0)),beta,a,zero)==(a1,a1,a2,a2),'equal exposures yield no contrast')
    invalid=[lambda:ratios((F(0),F(0)),baseline),lambda:ratios((F(1),),baseline),lambda:differences((F(1),F(2))),lambda:observations(x,beta,(F(1),),zero),lambda:observations(x,beta,a,(F(0),)),lambda:numeric('True'),lambda:numeric('__import__("os")')]
    for fn in invalid:
        try:fn()
        except ValueError:pass
        else:raise ValueError('invalid domain accepted')
    return len(inputs),len(expected),sum(map(len,expected.values())),len(invalid)


def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    raw={p:(root/p).read_bytes() for p in FILES}
    author=json.loads(raw[FILES[3]]);peer=json.loads(raw[FILES[5]])
    for record,paths in ((author,set(FILES[:3])),(peer,set(FILES[:5]))):
        bindings=record['payload_bindings'];require(len(bindings)==len(paths) and {x['path'] for x in bindings}==paths,'nonself manifest')
        for item in bindings:
            b=raw[item['path']];require(len(b)==item['bytes'] and sha256(b).hexdigest()==item['sha256'],'payload binding '+item['path'])
    doc=Manuscript();doc.feed(raw[FILES[0]].decode());require(not doc.stack and len(doc.ids)==len(set(doc.ids)),'balanced unique fragment')
    targets={f'v16-c02-e{i}' for i in range(1,9)}
    require(set(doc.prompts)==set(doc.solutions)==targets and len(doc.worked)==2,'two worked artifacts and eight exact solutions')
    require(set(peer['exact_prompt_review'])==targets,'full reading record')
    for key in targets:
        binding=peer['exact_prompt_review'][key]
        require(sha256(doc.prompts[key].encode()).hexdigest()==binding['prompt_sha256'] and sha256(doc.solutions[key].encode()).hexdigest()==binding['solution_sha256'],'exact prompt/solution freeze')
    sources=json.loads(raw[FILES[2]])['sources']
    require(len(sources)==5 and doc.sources=={x['id']:x['url'] for x in sources},'five exact source routes')
    require({'v16-c01.html','curriculum.html#v16-c03'}<=doc.links,'dependency/successor routes')
    require('v16-c02-teachback' in doc.ids and peer['open_findings']==[],'teachback/retention and findings')
    inputs,results,scalars,invalid=numerical_audit(doc)
    return {'chapter':'v16-c02','review':'independent-peer','status':'passed','worked_cases':2,'exact_solutions':8,'input_groups':inputs,'result_groups':results,'displayed_scalar_results':scalars,'invalid_domain_rejections':invalid,'source_routes':5,'runtime_files':6,'scope':'Full qualitative two-paper evidence map and source-boundary reading separately recorded; primitive contrast reconstruction and alternative observational-equivalence witnesses.'}


if __name__=='__main__':check()
