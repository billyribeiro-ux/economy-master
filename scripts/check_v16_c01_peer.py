"""Independent C01 research-instruction audit; never imports author checker."""
from pathlib import Path
from hashlib import sha256
from fractions import Fraction as F
from html.parser import HTMLParser
import ast
import json

FILES=('content/chapters/v16-c01.html','scripts/check_v16_c01.py','content/reviews/v16-c01-sources.json','content/reviews/v16-c01-author.json','scripts/check_v16_c01_peer.py','content/reviews/v16-c01-peer.json')

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


def aggregates(before,after):
    require(len(before)==len(after)>0 and all(x>=0 for x in before+after) and sum(before)>0,'population domain')
    return (sum(after)-sum(before))/sum(before)


def individual_mean(before,after):
    require(len(before)==len(after)>0 and all(x>0 for x in before) and all(x>=0 for x in after),'individual growth domain')
    return sum(((y-x)/x for x,y in zip(before,after)),F(0))/len(before)


def numerical_audit(doc):
    inp={k:numeric(v) for k,v in doc.inputs.items()};out={k:numeric(v) for k,v in doc.results.items()}
    require(set(inp)=={'time','allocation','stocks','completion-one','completion-two','task-hours','alternative-a1','extra-hours','overrun-hours'},'all nine actual input groups')
    stocks=inp['stocks'];a0,a1,b0,b1,c1,d0=stocks
    table={row[0]:row[1:] for row in doc.rows if row and row[0] in ('A','B','C','D')}
    require(table=={'A':[str(a0),str(a1),'Matched'],'B':[str(b0),str(b1),'Matched'],'C':['Missing',str(c1),'Observed only at date 1'],'D':[str(d0),'Missing','Observed only at date 0']},'actual displayed stock table')
    before=(a0,b0);after=(a1,b1);raw0=sum(before)+d0;raw1=sum(after)+c1
    expected={'hours':inp['time'][0]*inp['time'][1],'allocated':sum(inp['allocation']),'raw-totals':(raw0,raw1),'raw-growth':aggregates((raw0,),(raw1,)),'matched-totals':(sum(before),sum(after)),'matched-growth':aggregates(before,after),'mean-growth':individual_mean(before,after),'decomposition':(sum(after)-sum(before),c1,d0,raw1-raw0)}
    for name in ('completion-one','completion-two'):
        c0,d1=inp[name];full0=raw0+c0;full1=raw1+d1
        expected[name]=(full0,full1,aggregates((full0,),(full1,)))
    ar,am,br,bm=inp['task-hours']
    require(min(ar,am,br,bm)>0 and ar<br and am<bm,'absolute task advantage')
    expected['e1-costs']=(ar/am,br/bm);expected['e1-inverse']=(am/ar,bm/br)
    require(ar/am<br/bm and bm/br<am/ar,'relative advantage')
    changed=(inp['alternative-a1'],b1)
    expected['e3-aggregate']=aggregates(before,changed);expected['e3-mean']=individual_mean(before,changed)
    allocation=list(inp['allocation']);extra=inp['extra-hours'];allocation[0]+=extra;allocation[-1]-=extra
    expected['e5-allocation']=tuple(allocation);expected['e5-overrun']=sum(inp['allocation'][:-1])+inp['overrun-hours']
    require(set(out)==set(expected),'every displayed result')
    for key,value in expected.items():require(out[key]==value,'computed manuscript result: '+key)
    require(expected['hours']==expected['allocated']==sum(allocation) and allocation[-1]>=0,'actual time feasibility')
    require(expected['e5-overrun']>expected['hours'],'actual overrun')
    # Independent identities and alternative populations rather than a dictionary of answers.
    require(raw1-raw0==(a1-a0)+(b1-b0)+c1-d0,'coverage decomposition')
    require(expected['raw-growth']>0>expected['matched-growth'],'observed sign reversal')
    require(expected['completion-one'][2]<0<expected['completion-two'][2],'opposite missing-data witnesses')
    require(expected['e3-aggregate']==sum(x/sum(before)*(y-x)/x for x,y in zip(before,changed)),'baseline-weighted identity')
    for scale in (F(1,10),F(2),F(1000)):
        require(aggregates(tuple(scale*x for x in before),tuple(scale*y for y in changed))==expected['e3-aggregate'],'unit invariance')
    alt0=(F(10),F(90));alt1=(F(20),F(81))
    require(aggregates(alt0,alt1)==F(1,100) and individual_mean(alt0,alt1)==F(9,20),'unequal population witness')
    require(aggregates((F(10),F(0)),(F(9),F(1)))==0,'aggregate zero-baseline member is permissible')
    # Missing values nonnegative: choose completions with equal full totals,
    # arbitrarily high decline or growth. Observed six cells stay fixed.
    require(aggregates((raw0+c1,),(raw1+c1-(raw1-raw0),))==0,'zero growth missingness witness')
    require(aggregates((raw0+10000,),(raw1,))<0 and aggregates((raw0,),(raw1+10000,))>0,'unrestricted missingness directions')
    for extra_cost in (F(0),inp['allocation'][-1],inp['allocation'][-1]+1):
        need=sum(inp['allocation'][:-1])+extra_cost
        require((need<=expected['hours'])==(extra_cost<=inp['allocation'][-1]),'reserve boundary')
    invalid=[lambda:aggregates((),()),lambda:aggregates((F(0),),(F(1),)),lambda:aggregates((F(-1),),(F(1),)),lambda:individual_mean((F(0),),(F(1),)),lambda:individual_mean((F(1),),(F(-1),)),lambda:numeric('True'),lambda:numeric('__import__("os")')]
    for fn in invalid:
        try:fn()
        except ValueError:pass
        else:raise ValueError('invalid domain accepted')
    return len(inp),len(expected),len(invalid)


def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    raw={p:(root/p).read_bytes() for p in FILES}
    author=json.loads(raw[FILES[3]]);peer=json.loads(raw[FILES[5]])
    for record,paths in ((author,set(FILES[:3])),(peer,set(FILES[:5]))):
        bindings=record['payload_bindings'];require(len(bindings)==len(paths) and {x['path'] for x in bindings}==paths,'nonself manifest')
        for item in bindings:
            b=raw[item['path']];require(len(b)==item['bytes'] and sha256(b).hexdigest()==item['sha256'],'payload binding '+item['path'])
    doc=Manuscript();doc.feed(raw[FILES[0]].decode());require(not doc.stack and len(doc.ids)==len(set(doc.ids)),'balanced unique fragment')
    targets={f'v16-c01-e{i}' for i in range(1,9)}
    require(set(doc.prompts)==set(doc.solutions)==targets and len(doc.worked)==2,'two cases/eight exact solutions')
    require(set(peer['exact_prompt_review'])==targets,'full reading record')
    for key in targets:
        binding=peer['exact_prompt_review'][key]
        require(sha256(doc.prompts[key].encode()).hexdigest()==binding['prompt_sha256'] and sha256(doc.solutions[key].encode()).hexdigest()==binding['solution_sha256'],'full prompt/solution freeze')
    sources=json.loads(raw[FILES[2]])['sources']
    require(len(sources)==3 and doc.sources=={x['id']:x['url'] for x in sources},'three exact source routes')
    require(all(s.get('inspection') and s.get('limits') for s in sources),'bounded source scopes')
    require({'curriculum.html#v12','curriculum.html#v13','curriculum.html#v14','curriculum.html#v15','curriculum.html#v16-c02'}<=doc.links,'prerequisites and successor')
    require('v16-c01-teachback' in doc.ids and peer['open_findings']==[],'teaching guide and findings')
    inputs,results,rejections=numerical_audit(doc)
    return {'chapter':'v16-c01','status':'passed','review':'independent-peer','worked_cases':2,'exact_solutions':8,'input_groups':inputs,'result_groups':results,'invalid_domain_rejections':rejections,'source_routes':3,'runtime_files':6,'scope':'Full qualitative research-instruction reading separately recorded; exact table/input reconstruction and alternative population/missingness witnesses.'}


if __name__=='__main__':check()
