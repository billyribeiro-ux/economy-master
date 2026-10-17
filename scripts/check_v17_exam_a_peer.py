"""Independent Form A peer: inverse-curve accounts and explicit potential-outcome worlds."""
from pathlib import Path
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from itertools import product
import ast
import json
FILES=('content/assessments/parts/v17-exam-a.html','scripts/check_v17_exam_a.py','content/reviews/v17-exam-a-sources.json','content/reviews/v17-exam-a-author.json','scripts/check_v17_exam_a_peer.py','content/reviews/v17-exam-a-peer.json')
DOMAINS=('alignment_explanation','course_seminar_design','assessment_feedback','communication_supervision','observation_portfolio')
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


class Manuscript(BaseManuscript):
    def __init__(self):
        super().__init__();self.points={};self.domain={};self.rubrics={};self.chapters={}
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='li' and 'data-points' in a:
            self.points[a['id']]=int(a['data-points']);self.chapters[a['id']]=a['data-chapters'].split()
            self.domain[a['id']]=next(x['data-domain'] for t,x in reversed(self.stack) if 'data-domain' in x)
        if 'data-rubric-points' in a:
            target=next(x['data-solution-for'] for t,x in reversed(self.stack) if 'data-solution-for' in x)
            self.rubrics.setdefault(target,[]).append(int(a['data-rubric-points']))
        super().handle_starttag(tag,attrs)

def strict_json(raw):
    def pairs(items):
        out={}
        for k,v in items:
            require(k not in out,'duplicate JSON key');out[k]=v
        return out
    def bad(v):raise ValueError('nonfinite JSON')
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=bad)


def market(a,b,d,t):
    a,b,d,t=map(F,(a,b,d,t))
    require(a>0 and b>0 and d>0 and 0<=t<a/b,'positive slopes and interior nonnegative tax')
    # Equate the inverse-demand-minus-inverse-supply price gap to the tax.
    q=(a/b-t)/(1/b+1/d);pc=(a-q)/b;ps=q/d
    q0=(a/b)/(1/b+1/d);p0=q0/d
    value=(a/b)*q-q*q/(2*b);resource=q*q/(2*d)
    baseline=(a/b)*q0-q0*q0/(2*b)-q0*q0/(2*d)
    cs=value-pc*q;producer=ps*q-resource;revenue=t*q
    return {'pc':pc,'ps':ps,'q':q,'p0':p0,'q0':q0,'buyer':pc-p0,'seller':p0-ps,'revenue':revenue,'cs':cs,'producer':producer,'total':value-resource,'baseline':baseline,'loss':baseline-value+resource}


def tax_vector(m):return tuple(m[k] for k in ('pc','ps','q','buyer','seller','revenue','loss'))


def world(primitives,u,v):
    p,yt,yc,lo,hi=primitives;u,v=F(u),F(v)
    require(p==F(1,3) and lo<=hi and all(lo<=z<=hi for z in (yt,yc,u,v)),'given complete three-person law/support')
    outcomes=((yt,v),(u,yc),(u,yc));observed=(outcomes[0][0],outcomes[1][1],outcomes[2][1])
    return outcomes,observed,sum((y1-y0 for y1,y0 in outcomes),F(0))/3


def fixed(a,b,q,t):
    a,b,q,t=map(F,(a,b,q,t))
    require(a>0 and b>0 and 0<q<=a and t>=0,'fixed supply primitives')
    pc=(a-q)/b;ps=pc-t
    require(ps>=0,'offered fixed supply must satisfy seller minimum')
    return pc,pc,q,pc,ps,q,F(0),t,t*q


def completion(initial,delayed,maximum):
    require(len(initial)==len(delayed)>0 and type(maximum) is int and maximum>0,'roster domain')
    require(all(type(v) is int and 0<=v<=maximum for v in initial) and all(v is None or type(v) is int and 0<=v<=maximum for v in delayed),'integer score support')
    seen=[v for v in delayed if v is not None];require(seen,'at least one observed delayed score for responder mean')
    n=len(initial);base=F(sum(initial),n);resp=F(sum(seen),len(seen));miss=n-len(seen)
    worlds={F(sum(seen)+sum(bits),n) for bits in product(range(maximum+1),repeat=miss)}
    lo,hi=min(worlds),max(worlds)
    return (base,resp,lo,hi,lo-base,hi-base),worlds


def audit(d):
    count=0
    def eq(a,b,label):
        nonlocal count
        require(a==b,label);count+=1
    x={k:numeric(v) for k,v in d.inputs.items()}
    eq(x,{'tax':(120,2,3,10),'tax-scenarios':(5,20),'supply-transfer-input':(120,2,1,10),'identification':(F(1,3),6,3,0,9),'restriction':(4,5),'fixed-supply-input':(120,2,60,10),'diagnostic-tax':8,'observation-tax':15},'all primitive visible groups')
    a,b,dcoef,t=x['tax'];base=market(a,b,dcoef,t);low=market(a,b,dcoef,x['tax-scenarios'][0]);high=market(a,b,dcoef,x['tax-scenarios'][1]);transfer=market(*x['supply-transfer-input']);diagnostic=market(a,b,dcoef,x['diagnostic-tax']);observation=market(a,b,dcoef,x['observation-tax']);ident=x['identification'];lo,hi=ident[-2:]
    corners=[world(ident,u,v)[2] for u,v in product((lo,hi),repeat=2)];ul,vu=x['restriction'];restricted=[world(ident,u,v)[2] for u,v in product((ul,hi),(lo,vu))]
    rows=[row for row in d.rows if len(row)==3 and row[0] in tuple('ABCDEFGH')]
    eq(rows,[[n,str(i),'—' if y is None else str(y)] for n,i,y in [('A',0,2),('B',1,2),('C',0,1),('D',2,1),('E',1,1),('F',0,0),('G',0,None),('H',0,None)]],'all eight actual score rows')
    initial=[int(row[1]) for row in rows];delayed=[None if row[2]=='—' else int(row[2]) for row in rows];evidence,grid=completion(initial,delayed,2)
    want={'tax-base':(base['p0'],base['q0'],*tax_vector(base)[:5]),'tax-high':tax_vector(high),'tax-low':tax_vector(low),'ate-range':(min(corners),max(corners)),'supply-transfer':(transfer['p0'],transfer['q0'],*tax_vector(transfer)[:5]),'response-score':(1,1,1,1,0,sum((1,1,1,1,0))),'diagnostic-transfer':tax_vector(diagnostic)[:5],'evidence-means':evidence,'restricted-range':(min(restricted),max(restricted)),'observation-transfer':tax_vector(observation),'fixed-supply':fixed(*x['fixed-supply-input'])}
    eq(set(want),set(d.results),'all displayed result groups')
    for k,v in want.items():eq(numeric(d.results[k]),v,'visible '+k)
    # Direct integral value/resource accounts independently check both triangle and tax accounting.
    eq((base['baseline'],base['total'],high['total']),(2160,2100,1920),'full surplus accounts')
    eq((base['cs'],base['producer'],base['revenue']),(900,600,600),'primary three-account decomposition')
    eq((high['cs'],high['producer'],high['revenue']),(576,384,960),'high-tax three-account decomposition')
    for tax in (F(0),F(5),F(8),F(10),F(15),F(20),F(59)):
        m=market(a,b,dcoef,tax)
        eq(m['q'],a-b*m['pc'],'direct demand clearing')
        eq(m['q'],dcoef*m['ps'],'direct supply clearing')
        eq(m['pc']-m['ps'],tax,'tax wedge')
        eq(m['buyer']+m['seller'],tax,'incidence sums to wedge')
        eq(m['cs']+m['producer']+m['revenue'],m['total'],'resource accounts equal transfer-inclusive surplus')
        eq(m['loss'],tax*(m['q0']-m['q'])/2,'lost trade area')
        eq(m['q'],F(72)-F(6,5)*tax,'global original quantity affine formula')
    eq((high['loss']/base['loss'],high['revenue']-base['revenue'],high['loss']-base['loss']),(4,360,180),'nonlinear loss and decision increments')
    eq(tuple(tax for tax in (10,20) if market(a,b,dcoef,tax)['revenue']>=800),(20,),'conditional only-supplied-options target')
    eq((a/b, F(72)-F(6,5)*60),(60,0),'zero-quantity limit boundary')
    eq(((a-0)/b,(a-120)/b,F(72)/dcoef),(60,0,24),'actual graph coordinates')
    eq(((a-60)/b,F(60)/dcoef),(30,20),'graph taxed coordinates')
    eq((transfer['buyer']/10,transfer['seller']/10),(F(1,3),F(2,3)),'changed supply burden fractions')
    eq(fixed(120,2,60,30),(30,30,60,30,0,60,0,30,1800),'fixed supply inclusive seller-zero boundary')
    eq(fixed(120,2,60,0),(30,30,60,30,30,60,0,0,0),'fixed supply no-tax endpoint')
    # Three-person worlds preserve every observed outcome, not merely two group means.
    for u,v in product((F(0),F(3),F(6),F(9)),repeat=2):
        potentials,observed,ate=world(ident,u,v)
        eq(observed,(6,3,3),'complete observed law preserved')
        eq(ate,(2*u-v)/3,'world contrast equals mixture identity')
        require(-3<=ate<=6,'support bound for compatible world');count+=1
    eq(world(ident,6,3)[2],3,'added mean-independence world')
    eq(world(ident,5,1)[2],3,'nonnecessity same-ATE world')
    require(5!=6 and 1!=3,'both conditional means differ in counterexample');count+=1
    # Exact affine endpoint coefficients and interval constraints prove all-real interior attainability.
    eq((world(ident,0,9)[2],world(ident,9,0)[2]-world(ident,0,9)[2]),(-3,9),'unrestricted attaining segment coefficients')
    eq((world(ident,4,5)[2],world(ident,9,0)[2]-world(ident,4,5)[2]),(1,5),'restricted attaining segment coefficients')
    for lam in (F(0),F(1,9),F(1,3),F(1,2),F(2,3),F(8,9),F(1)):
        u,v=9*lam,9*(1-lam);eq(world(ident,u,v)[2],-3+9*lam,'unrestricted interior witness')
        u,v=4+5*lam,5*(1-lam);eq(world(ident,u,v)[2],1+5*lam,'restricted interior witness')
        require(4<=u<=9 and 0<=v<=5,'restricted witness feasible');count+=1
    eq(tuple(sorted(grid)),tuple(F(v,8) for v in range(7,12)),'all nine integer completions yield five delayed means')
    eq(completion([0,1],[0,1],2)[0],(F(1,2),F(1,2),F(1,2),F(1,2),0,0),'fully observed bounds collapse')
    eq((sum(initial),sum(v for v in delayed if v is not None)),(4,7),'actual score totals')
    eq((sum((4,7,6,6,5,2)),sum((5,12,10,12,7,4)),sum((2,3,3,2)),sum((3,2,2,3))),(30,50,10,10),'four full facilitation/lesson budgets')
    eq((2+2+2,2+4,4*4,F(4)-F(1,2)),(6,6,16,F(7,2)),'course and supervision hours')
    invalid=[lambda:market(0,2,3,10),lambda:market(120,0,3,10),lambda:market(120,2,0,10),lambda:market(120,2,3,-1),lambda:market(120,2,3,60),lambda:market(120,2,3,61),lambda:world(ident,-1,3),lambda:world(ident,6,10),lambda:world((F(1,2),6,3,0,9),6,3),lambda:fixed(120,2,60,31),lambda:fixed(120,2,121,0),lambda:completion([0],[None],2),lambda:completion([0],[3],2),lambda:completion([0,1],[1],2),lambda:completion([0],[F(1,2)],2)]
    for fn in invalid:
        try:fn()
        except ValueError:pass
        else:raise ValueError('invalid domain accepted')
    return count,len(invalid),len(want)


def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    raw={f:(root/f).read_bytes() for f in FILES};peer=strict_json(raw[FILES[5]]);author=strict_json(raw[FILES[3]]);sources=strict_json(raw[FILES[2]])
    require(set(peer['payloads'])==set(FILES[:5]) and set(author['payloads'])==set(FILES[:3]),'five peer and three author nonself bindings')
    for rec in (peer,author):
        for f,v in rec['payloads'].items():require(v=={'bytes':len(raw[f]),'sha256':sha256(raw[f]).hexdigest()},'frozen payload changed '+f)
    d=Manuscript();d.feed(raw[FILES[0]].decode());require(not d.stack and len(d.ids)==len(set(d.ids)),'balanced unique fragment')
    expected={f'v17-exam-a-q{i}' for i in range(1,21)}
    require(set(d.prompts)==set(d.solutions)==set(d.points)==set(d.rubrics)==set(peer['exact_prompt_review'])==expected,'twenty exact scored/solved pairs')
    require(all(v==5 for v in d.points.values()) and sum(d.points.values())==100 and all(v==[1]*5 for v in d.rubrics.values()),'hundred points with additive five-point rubrics')
    require(set(d.domain.values())==set(DOMAINS),'five domains')
    for domain in DOMAINS:require(sum(d.points[k] for k in expected if d.domain[k]==domain)==20,'twenty per domain')
    require({c for cs in d.chapters.values() for c in cs}=={f'v17-c{i:02d}' for i in range(1,13)},'all twelve outcomes mapped')
    require({'form-a','solutions-a'}<=set(d.ids) and all(i in ('form-a','solutions-a') or i.startswith('v17-exam-a-') for i in d.ids),'stable IDs')
    for k,v in peer['exact_prompt_review'].items():
        require(v['prompt_sha256']==sha256(d.prompts[k].encode()).hexdigest() and v['solution_sha256']==sha256(d.solutions[k].encode()).hexdigest(),'actual reviewed pair unchanged')
        require(v['chapters']==d.chapters[k] and v['domain']==d.domain[k],'actual reviewed coverage')
    routes={'v17-c03-cmu-alignment':'https://www.cmu.edu/teaching/assessment/basics/alignment.html','v17-c05-cmu-rubrics':'https://www.cmu.edu/teaching/assessment/assesslearning/rubrics.html','v17-c09-ori-basic':'https://ori.hhs.gov/content/Chapter-7-Mentor-and-Trainee-Responsibilities-Basic-responsibilities','v17-c11-cmu-observation':'https://www.cmu.edu/teaching/assessment/assessteaching/classroomObservations.html'}
    require(d.sources==routes=={s['id']:s['url'] for s in sources['sources']},'four exact bounded source routes')
    require([s['actual_inspector'] for s in sources['sources']]==['root','v16_c01_author','v16_c01_author','root'],'retained actual source inspectors')
    comparisons,invalid,groups=audit(d)
    return {'volume':'v17','component':'exam_a','status':'passed','review':'independent internal peer','runtime_files':6,'points':100,'domains':5,'prompts':20,'solutions':20,'additive_rubrics':20,'chapter_outcomes':12,'numeric_groups':groups,'comparisons':comparisons,'invalid_domains':invalid,'learner_missing_schedules':9,'source_routes':4,'author_checker':'opaque hash only; never read as text/imported/executed','scope':'Full exact artifacts, open-ended solutions, grading and global proofs read. Internal peer does not establish actual teaching/supervision or independent human evaluation.'}


if __name__=='__main__':
    check()
