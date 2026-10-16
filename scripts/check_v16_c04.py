"""Author audit of exact referee-training witnesses, not a score for judgment."""
from pathlib import Path
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
import ast, json
FILES=('content/chapters/v16-c04.html','scripts/check_v16_c04.py','content/reviews/v16-c04-sources.json','content/reviews/v16-c04-author.json')
def require(ok,msg):
    if not ok:raise ValueError(msg)
def numbers(s):
    def walk(n):
        if isinstance(n,ast.Constant) and type(n.value)is int:return F(n.value)
        if isinstance(n,ast.Tuple):return tuple(walk(x) for x in n.elts)
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,ast.USub):return -walk(n.operand)
        if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Div):
            den=walk(n.right);require(den!=0,'nonzero denominator');return walk(n.left)/den
        raise ValueError('exact numeric syntax')
    return walk(ast.parse(s.rsplit('=',1)[-1].strip(),mode='eval').body)
class Read(HTMLParser):
    def __init__(self):
        super().__init__();self.stack=[];self.ids=[];self.inputs={};self.results={};self.worked=[];self.exercises=[];self.solutions=[];self.sources={};self.links=set();self.cells=[];self.collect=[]
    def handle_starttag(self,t,attrs):
        a=dict(attrs);require(len(a)==len(attrs),'duplicate attrs');require(t!='h1','fragment title')
        if 'id'in a:require(a['id'] not in self.ids,'duplicate ID');self.ids.append(a['id'])
        if 'worked'in a.get('class','').split():self.worked.append(a['id'])
        if t=='li' and a.get('id','').startswith('v16-c04-e'):self.exercises.append(a['id'])
        if 'data-solution-for'in a:
            require(any(t=='details' and 'solutions'in d.get('class','').split() for t,d in self.stack),'solution disclosure');self.solutions.append(a['data-solution-for'])
        if 'data-source'in a:self.sources[a['data-source']]=a['href']
        if 'href'in a:self.links.add(a['href'])
        for field,target in [('data-input',self.inputs),('data-result',self.results)]:
            if field in a:
                key=a[field];require(key not in target,'duplicate marker');target[key]='';self.collect.append((len(self.stack),target,key))
        if t=='td':self.cells.append('');self.collect.append((len(self.stack),self.cells,len(self.cells)-1))
        if t not in ('hr','br','img'):self.stack.append((t,a))
    def handle_data(self,s):
        for _,d,key in self.collect:d[key]+=s
    def handle_endtag(self,t):
        require(self.stack and self.stack[-1][0]==t,'balanced HTML');self.stack.pop();self.collect=[x for x in self.collect if x[0]<len(self.stack)]
def optimizer(c):
    require(type(c)in(int,F) and c>=0,'nonnegative exact cost');return max(F(0),(F(6)-F(c))/2)
def effects(obs,untreated):
    require(len(obs)==8 and len(untreated)==2,'complete observation/counterfactual shape')
    require(all(type(x)in(int,F) for x in (*obs,*untreated)),'exact nonboolean input')
    obs=tuple(map(F,obs));untreated=tuple(map(F,untreated))
    treated=((obs[1]-obs[0])+(obs[3]-obs[2]))/2
    control=((obs[5]-obs[4])+(obs[7]-obs[6]))/2
    no=((untreated[0]-obs[0])+(untreated[1]-obs[2]))/2
    return treated-no,no-control

def check(root=None):
    root=Path(root) if root else Path(__file__).resolve().parents[1];payload={p:(root/p).read_bytes() for p in FILES};review=json.loads(payload[FILES[3]])
    require({x['path'] for x in review['payload_bindings']}==set(FILES[:3]) and len(review['payload_bindings'])==3,'freeze inventory')
    for x in review['payload_bindings']:
        b=payload[x['path']];require(x['bytes']==len(b) and x['sha256']==sha256(b).hexdigest(),'frozen payload')
    doc=Read();doc.feed(payload[FILES[0]].decode());doc.close();require(not doc.stack,'closed fragment')
    ids=[f'v16-c04-e{i}' for i in range(1,9)];require(doc.exercises==doc.solutions==ids,'eight pairs');require(len(doc.worked)==2,'two worked reports');require(set(review['exact_prompt_review'])==set(ids),'complete author reading')
    src=json.loads(payload[FILES[2]])['sources'];require(doc.sources=={x['id']:x['url'] for x in src},'exact source routes');require({'curriculum.html#v16-c03','curriculum.html#v16-c05','v16-c02.html'}<=doc.links,'chapter routes')
    require(doc.cells==['Yes','20','32','Yes','30','42','No','20','22','No','30','32'],'actual packet table')
    inp={k:numbers(v) for k,v in doc.inputs.items()};out={k:numbers(v) for k,v in doc.results.items()}
    require(inp=={'investment':(20,32,30,42,20,22,30,32),'counterfactual-one':(22,32),'counterfactual-two':(27,37),'costs':(0,2,5,6,8),'exercise-counterfactual':(30,40)},'actual primitives')
    comparisons=0
    def equal(a,b,label):
        nonlocal comparisons
        if isinstance(a,tuple):
            require(isinstance(b,tuple) and len(a)==len(b),label+' shape')
            for x,y in zip(a,b):equal(x,y,label)
        else:require(a==b,label);comparisons+=1
    obs=inp['investment'];t=((obs[1]-obs[0])+(obs[3]-obs[2]))/2;c=((obs[5]-obs[4])+(obs[7]-obs[6]))/2
    bs=tuple(optimizer(c) for c in inp['costs']);expected={'changes':(t,c,t-c),'compatible-effects':effects(obs,inp['counterfactual-one'])+effects(obs,inp['counterfactual-two']),'buffers':bs,'objective-values':tuple((6-c)*b-b*b for c,b in zip(inp['costs'],bs)),'exercise-effects':effects(obs,inp['exercise-counterfactual']),'sensitivity':(t-c-3,t-c+2),'real-growth':F(110)/(F(110)/100)/(F(100)/(F(100)/100))-1}
    require(out.keys()==expected.keys(),'all displayed results')
    for key,val in expected.items():equal(out[key],val,key)
    # Independent domain consequences including both boundary regimes and closed sharp set.
    for delta in (F(-2),F(-1),F(0),F(3)):
        cf=(obs[0]+c+delta,obs[2]+c+delta);tau,d=effects(obs,cf);equal((tau,d),(10-delta,delta),'constructive sharpness')
    for cost in (F(0),F(2),F(5),F(6),F(8),F(100)):
        best=optimizer(cost);require(0<=best<=4,'admissible optimum')
        for trial in (F(0),F(1,4),F(1),F(2),F(3),F(4)):
            jb=(6-cost)*best-best*best;jt=(6-cost)*trial-trial*trial
            require(jb>=jt and (jb!=jt or best==trial),'unique finite witness');comparisons+=1
            # Exact completed-square difference for all tested trials.
            equal(jb-jt,(trial-(6-cost)/2)**2-(best-(6-cost)/2)**2,'square identity')
    require(optimizer(F(6))==0 and optimizer(F(8))==0 and (6-F(8))/2<0,'boundary refutations')
    bad=[lambda:optimizer(-1),lambda:optimizer(True),lambda:optimizer(1.5),lambda:numbers('1/0'),lambda:numbers('True'),lambda:numbers('f(1)'),lambda:effects(obs,(1,)),lambda:effects(obs,(True,1))]
    for f in bad:
        try:f()
        except ValueError:pass
        else:raise ValueError('invalid domain accepted')
    return {'chapter':'v16-c04','status':'passed','worked_reports':2,'exact_solutions':8,'input_groups':len(inp),'result_groups':len(out),'comparisons':comparisons,'rejected_domains':len(bad),'runtime_files':4,'scope':'Exact numeric witnesses; full qualitative referee judgment reviewed separately.'}
if __name__=='__main__':check()
