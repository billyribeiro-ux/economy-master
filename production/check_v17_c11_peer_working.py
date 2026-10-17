"""Independent C11 peer oracle: raw state moments and proportional demand changes."""
from pathlib import Path
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
import ast
import json
FILES=('production/v17-c11-working.html','production/check_v17_c11_working.py','production/v17-c11-sources-working.json','production/v17-c11-author-review-working.json','production/check_v17_c11_peer_working.py','production/v17-c11-peer-review-working.json')
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


def demand(a,b,p):
    a,b,p=map(F,(a,b,p))
    require(a>0 and b>0 and 0<p<a/b,'positive demand interior')
    q=a-b*p
    # Relative quantity change per relative price change on the supplied linear law.
    h=F(1,10000)
    slope=((a-b*(p+h))-q)/h
    elasticity=((a-b*(p+h))-q)/q/(h/p)
    return q,slope,elasticity


def moments(x,y):
    require(len(x)>0 and len(x)==len(y),'nonempty paired complete state law')
    require(all(type(v) in (int,F) for v in (*x,*y)),'exact state values')
    n=len(x);mx=sum(x,F(0))/n;my=sum(y,F(0))/n
    return mx,my,sum(((v-mx)**2 for v in x),F(0))/n,sum(((v-my)**2 for v in y),F(0))/n,sum(((a-mx)*(b-my) for a,b in zip(x,y)),F(0))/n


def portfolio(x,y,w):
    moments(x,y);w=F(w)
    require(0<=w<=1,'long-only weight')
    z=tuple(w*a+(1-w)*b for a,b in zip(x,y))
    mz,_,vz,_,_=moments(z,z)
    return z,mz,vz


def missing_bounds(success,observed,total):
    require(all(type(v) is int for v in (success,observed,total)) and total>0 and 0<=success<=observed<=total,'binary roster counts')
    return F(success,total),F(success+total-observed,total)


def audit(d):
    count=0
    def eq(a,b,label):
        nonlocal count
        require(a==b,label);count+=1
    inputs={k:numeric(v) for k,v in d.inputs.items()}
    eq(inputs,{'demand':(100,10,2),'returns':((2,2,-2,-2),(-4,4,-4,4))},'all visible primitives')
    a,b,p=inputs['demand'];x,y=inputs['returns'];mx,my,vx,vy,cov=moments(x,y)
    z,mz,vz=portfolio(x,y,F(1,2));z34,m34,v34=portfolio(x,y,F(3,4))
    plus=tuple(2*v for v in x);minus=tuple(-2*v for v in x)
    # These coefficients come from expanding centered raw state returns, not author code.
    quadratic=vx+vy-2*cov;linear=2*(cov-vy);constant=vy
    opt=-linear/(2*quadratic);optv=portfolio(x,y,opt)[2]
    initial_numeric=(False,True,True,False);initial_full=(False,False,True,False)
    bounds=missing_bounds(2,3,4);change=tuple(v-F(1,4) for v in bounds)
    want={'demand-result':demand(a,b,p),'initial-counts':(sum(initial_numeric),sum(initial_full),1),'fresh-elasticity':demand(120,20,2),'followup-range':bounds,'moments':(vx,vy,cov),'portfolio-returns':z,'portfolio-variance':vz,'covariance-boundaries':(portfolio(x,plus,F(1,2))[2],portfolio(x,minus,F(1,2))[2]),'zero-risk':(F(2,3),F(1,3),portfolio(x,minus,F(2,3))[2],portfolio(x,minus,F(2,3))[1]),'e2-comparison':(demand(a,b,2),demand(a,b,4)),'e3-change':change,'e4-demand':(demand(90,15,2),demand(90,15,3)),'e6-returns':z34,'e6-risk':(v34,opt,optv),'e7-plan':(sum((8,8,8,5)),sum((8,8,8,5))-25,6,6,8,5)}
    eq(set(want),set(d.results),'every displayed result group')
    for k,v in want.items():eq(numeric(d.results[k]),v,'visible '+k)
    eq((mx,my,mz,m34),(0,0,0,0),'means of complete laws')
    eq((vx,vy,cov),(4,16,0),'centered moment computation')
    eq((sum(v*v for v in z),vz),(20,5),'direct squared state total')
    eq((F(2)**2,F(4)**2,F(3)**2),(vx,vy,9),'individual SD squares and false averaged SD square')
    require(F(2)**2<vz<F(3)**2,'positive sqrt5 between2and3');count+=1
    eq(moments(x,plus)[2:],(4,16,8),'positive comovement moments')
    eq(moments(x,minus)[2:],(4,16,-8),'negative comovement moments')
    eq(portfolio(x,plus,F(1,2)),(tuple(F(3,2)*v for v in x),0,9),'SD3 special case')
    eq(portfolio(x,minus,F(1,2)),(tuple(-F(1,2)*v for v in x),0,1),'SD1 negative comovement')
    eq((quadratic,linear,constant),(20,-32,16),'exact variance polynomial coefficients')
    eq((quadratic,-2*quadratic*opt,quadratic*opt**2+optv),(quadratic,linear,constant),'global completed square coefficient identity')
    require(quadratic>0 and 0<opt<1,'unique feasible global minimum');count+=1
    eq((opt,optv),(F(4,5),F(16,5)),'derived optimum')
    nx,ny,nvx,nvy,ncov=moments(x,minus)
    eq((nvx+nvy-2*ncov,2*(ncov-nvy),nvy),(36,-48,16),'negative covariance polynomial equals4(3w-2)^2')
    eq(portfolio(x,minus,F(2,3)),((0,0,0,0),0,0),'zero variance exact statewise zero, no positive profit')
    for w in (F(0),F(1,4),F(1,2),F(2,3),F(3,4),F(4,5),F(1)):
        for alt in (y,plus,minus):
            ax,ay,avx,avy,acov=moments(x,alt);r,mean,var=portfolio(x,alt,w)
            eq(mean,w*ax+(1-w)*ay,'mean linearity')
            eq(var,w*w*avx+(1-w)**2*avy+2*w*(1-w)*acov,'cross term from raw states')
        eq(portfolio(x,y,w)[2],20*(w-F(4,5))**2+F(16,5),'completed square witness')
        eq(portfolio(x,minus,w)[2],4*(3*w-2)**2,'negative comovement witness')
    # Translation and identical assets show the centered identity does not require zero means or independence.
    shifted=tuple(v+7 for v in x)
    eq(moments(shifted,y),(7,0,4,16,0),'translated raw law')
    eq(portfolio(shifted,y,F(1,2))[1:],(F(7,2),5),'translation preserves variance')
    eq(portfolio(x,x,F(1,2))[1:],(0,4),'perfect identical assets')
    for aa,bb,pp,q,eps,rev in ((100,10,2,80,F(-1,4),60),(100,10,4,60,F(-2,3),20),(120,20,2,80,F(-1,2),40),(120,20,3,60,F(-1),0),(90,15,2,60,F(-1,2),30),(90,15,3,45,F(-1),0)):
        got=demand(aa,bb,pp);eq((got[0],got[2]),(q,eps),'unmarked point comparison')
        eq(got[0]*(1+got[2]),rev,'revenue derivative product identity')
        eq(aa-2*bb*pp,rev,'revenue polynomial derivative')
    eq(F(2,3),F(2)/3,'observed denominator')
    eq(tuple(F(2+u,4) for u in (0,1)),bounds,'attainable complete roster worlds')
    eq(tuple(100*v for v in change),(25,50),'percentage point changes')
    eq(missing_bounds(2,4,4),(F(1,2),F(1,2)),'fully observed bounds collapse')
    eq(missing_bounds(0,0,4),(0,1),'all missing bounds')
    eq((sum((3,3,3,1)),sum((4,4,4,3)),sum((6,6,8,5))),(10,15,25),'full revised time budgets')
    eq((portfolio(x,y,1)[1:],portfolio(x,y,1)[2]-optv),((0,4),F(4,5)),'delayed retention exact key')
    invalid=[lambda:demand(100,10,0),lambda:demand(100,10,10),lambda:demand(100,10,11),lambda:demand(0,10,2),lambda:demand(100,0,2),lambda:moments((),()),lambda:moments((1,2),(1,)),lambda:moments((1.0,),(1,)),lambda:portfolio(x,y,F(-1,10)),lambda:portfolio(x,y,F(11,10)),lambda:missing_bounds(3,2,4),lambda:missing_bounds(1,4,3),lambda:missing_bounds(0,0,0)]
    for fn in invalid:
        try:fn()
        except ValueError:pass
        else:raise ValueError('invalid domain accepted')
    return count,len(invalid),len(want)


def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    raw={f:(root/f).read_bytes() for f in FILES};peer=strict_json(raw[FILES[5]]);author=strict_json(raw[FILES[3]]);sources=strict_json(raw[FILES[2]])
    require(set(peer['payloads'])==set(FILES[:5]) and set(author['payloads'])==set(FILES[:3]),'nonself bindings')
    for rec in (author,peer):
        for f,v in rec['payloads'].items():require(v=={'bytes':len(raw[f]),'sha256':sha256(raw[f]).hexdigest()},'changed frozen file '+f)
    text=raw[FILES[0]].decode();d=BaseManuscript();d.feed(text);require(not d.stack and len(d.ids)==len(set(d.ids)),'balanced unique fragment')
    ids={f'v17-c11-e{i}' for i in range(1,9)}
    require(set(d.prompts)==set(d.solutions)==set(peer['exact_prompt_review'])==ids and d.worked==['v17-c11-case1','v17-c11-case2'],'eight pairs/two full dossiers')
    for k,v in peer['exact_prompt_review'].items():
        require(v['prompt_sha256']==sha256(d.prompts[k].encode()).hexdigest() and v['solution_sha256']==sha256(d.solutions[k].encode()).hexdigest(),'reviewed exact pair changed')
    routes={'v17-c11-cmu-observation':'https://www.cmu.edu/teaching/assessment/assessteaching/classroomObservations.html','v17-c11-cornell-observation':'https://teaching.cornell.edu/programs/faculty-instructors/classroom-observation-program'}
    require(d.sources==routes=={s['id']:s['url'] for s in sources['sources']},'exact scoped source routes')
    require(all(s['actual_inspector']=='root' for s in sources['sources']),'preserved actual source inspector')
    require({a for a in d.links if not a.startswith('https://')}=={'v17-c08.html','v17-c06.html','v17-c10.html','v17-c12.html'},'chapter routes')
    comparisons,invalid,groups=audit(d)
    return {'chapter':'v17-c11','status':'passed','review':'independent internal peer','runtime_files':6,'worked_artifacts':2,'prompts':8,'solutions':8,'numeric_groups':groups,'comparisons':comparisons,'invalid_domains':invalid,'source_routes':2,'author_checker':'opaque hash only; never read as text/imported/executed','scope':'Full observation dossiers, actual responses, exact solutions, global proofs and qualitative decisions read; no actual teaching or learner achievement certified.'}


if __name__=='__main__':
    check()
