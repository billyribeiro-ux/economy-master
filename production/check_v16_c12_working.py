"""C12 portfolio arithmetic and artifact checks; qualitative audit is separate."""
from pathlib import Path
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
import ast, contextlib, io, json, subprocess, sys

ROOT=Path(__file__).resolve().parents[1]
FILES=['production/v16-c12-working.html','production/check_v16_c12_working.py','production/v16-c12-sources-working.json','production/v16-c12-author-review-working.json']

def need(ok,why):
    if not ok: raise ValueError('C12: '+why)

def numeric(s):
    def go(n):
        if isinstance(n,ast.Expression):return go(n.body)
        if isinstance(n,(ast.Tuple,ast.List)):return tuple(go(v) for v in n.elts)
        if isinstance(n,ast.Constant) and type(n.value) is int:return F(n.value)
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,ast.USub):return -go(n.operand)
        if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Div):return go(n.left)/go(n.right)
        raise ValueError('unexpected numeric annotation')
    return go(ast.parse(s,mode='eval'))

class Page(HTMLParser):
    def __init__(self):
        super().__init__();self.stack=[];self.ids=[];self.tasks=[];self.answers=[];self.cases=[];self.sources={};self.values={};self.active=None;self.code='';self.transcript='';self.capture=None
    def handle_starttag(self,t,attrs):
        a=dict(attrs);need(len(a)==len(attrs),'unique attrs');need(t!='h1','fragment heading')
        if 'id' in a:self.ids.append(a['id'])
        if t=='article' and 'worked' in a.get('class','').split():self.cases.append(a.get('id'))
        if t=='li' and any(tag=='ol' and 'exercises' in at.get('class','').split() for tag,at in self.stack):self.tasks.append(a.get('id'))
        if 'data-solution-for' in a:
            need(any(tag=='details' and 'solutions' in at.get('class','').split() for tag,at in self.stack),'solution disclosure');self.answers.append(a['data-solution-for'])
        if 'data-source' in a:self.sources[a['data-source']]=a['href']
        for k in ('input','result'):
            if 'data-'+k in a:
                self.active=(k,a['data-'+k]);need(self.active not in self.values,'unique marker');self.values[self.active]=''
        if a.get('id')=='v16-c12-program':self.capture='code'
        if a.get('id')=='v16-c12-transcript':self.capture='transcript'
        if t not in ('br','hr','img','input','meta','link'):self.stack.append((t,a))
    def handle_data(self,s):
        if self.active:self.values[self.active]+=s
        if self.capture:setattr(self,self.capture,getattr(self,self.capture)+s)
    def handle_endtag(self,t):
        need(bool(self.stack) and self.stack[-1][0]==t,'balanced HTML');_,a=self.stack.pop()
        if any('data-'+k in a for k in ('input','result')):self.active=None
        if a.get('id') in ('v16-c12-program','v16-c12-transcript'):self.capture=None

def reconcile(v):
    need(len(v)==6 and all(type(x) in (int,F) and x>=0 for x in v),'amount domain')
    a0,a1,b0,b1,c0,d1=map(F,v);need(a0>0 and b0>0,'nonzero bank denominators')
    raw0=a0+b0+c0;raw1=a1+b1+d1;m0=a0+b0;m1=a1+b1
    return (raw0,raw1,m0,m1,(raw1-raw0)/raw0,(m1-m0)/m0,((a1-a0)/a0+(b1-b0)/b0)/2)

def score(w,s):
    need(len(w)==len(s)==5,'five domains');need(all(type(x) in (int,F) and x>=0 for x in w) and sum(w)==100,'weights')
    need(all(type(x) in (int,F) and 0<=x<=4 and F(x).denominator==1 for x in s),'score domain')
    return sum(F(a)*b/4 for a,b in zip(w,s))

def ready(s,complete,critical):
    score((25,25,20,15,15),s);need(type(complete) is bool and type(critical) is bool,'boolean gates')
    return min(s)>=3 and complete and not critical

def check(root=None):
    root=Path(root) if root is not None else ROOT
    rec=json.loads((root/FILES[3]).read_text());need(all(rec['review'].values()) and not rec['open_material_findings'],'author full-reading record')
    need(set(rec['payloads'])==set(FILES[:3]),'three nonself bindings')
    for name,binding in rec['payloads'].items():
        data=(root/name).read_bytes();need(binding=={'bytes':len(data),'sha256':sha256(data).hexdigest()},'freeze '+name)
    p=Page();p.feed((root/FILES[0]).read_text());p.close();need(not p.stack and len(p.ids)==len(set(p.ids)),'complete unique fragment')
    need(p.tasks==p.answers==[f'v16-c12-ex{i}' for i in range(1,9)],'eight exact solutions');need(p.cases==['v16-c12-case1','v16-c12-case2'],'two complete artifacts')
    src=json.loads((root/FILES[2]).read_text());need(p.sources=={x['id']:x['url'] for x in src['sources']},'source routes')
    values={k:numeric(v) for k,v in p.values.items()};count=0
    def eq(a,b,label):
        nonlocal count
        if isinstance(b,(list,tuple)):
            need(len(a)==len(b),label+' width')
            for x,y in zip(a,b):eq(x,y,label)
        else:need(a==b,label);count+=1
    v=values['input','ledger'];eq(v,(100,90,50,60,50,80),'raw inputs');result=reconcile(v);eq(values['result','ledger'],result,'release2');eq(values['result','bridge'],(result[3]-result[2],v[5],-v[4],result[1]-result[0]),'bridge')
    old=v[:3]+(F(55),)+v[4:];r1=reconcile(old);eq(values['result','old-release'],r1,'release1');eq(values['result','ex4'],tuple(a-b for a,b in zip(result[4:],r1[4:])),'correction differences')
    eq(values['result','ex1'],reconcile(v[:5]+(F(50),))[4:],'changed perimeter')
    w=values['input','weights'];eq(w,(25,25,20,15,15),'weights');s0=values['input','initial-scores'];s1=values['input','revised-scores'];eq(s0,(3,2,4,2,3),'initial domains');eq(s1,(3,3,4,3,3),'revised domains')
    eq(values['result','initial-score'],score(w,s0),'initial summary');eq(values['result','revised-score'],score(w,s1),'revised summary');need(not ready(s0,True,False) and ready(s1,True,False) and not ready(s1,True,True) and not ready(s1,False,False),'critical/complete gates')
    eq(values['result','ex5'],(score(w,(4,4,4,1,4)),score(w,(3,3,3,3,3))),'summary cannot override');need(not ready((4,4,4,1,4),True,True) and ready((3,3,3,3,3),True,False),'exercise5 gates')
    h=values['input','hours'];eq(h,(120,60,20,20,20),'hours');eq(values['result','hours'],sum(h[1:]),'allocation');eq(sum(h[1:])+30-h[-1]-h[0],10,'access shortfall');eq(values['result','ex7'],(60,0,20,30,10),'new agenda');eq(sum(values['result','ex7']),h[0],'agenda conservation')
    need(len(values)==15,'complete marker inventory')
    # Execute exact reader program and compare its exact JSON transcript with independent accounting.
    run=subprocess.run([sys.executable,'-I','-B','-O','-c',p.code],cwd='/',capture_output=True,text=True)
    need(run.returncode==0 and not run.stderr and run.stdout.strip()==p.transcript.strip(),'actual program transcript')
    output=json.loads(run.stdout);need(output=={'v1':[str(x) for x in r1],'v2':[str(x) for x in result],'bridge_v2':['0','80','-50','30']},'independent transcript arithmetic')
    ns={};out=io.StringIO();err=io.StringIO()
    with contextlib.redirect_stdout(out),contextlib.redirect_stderr(err):exec(compile(p.code,'reader-program','exec'),ns)
    need(not err.getvalue() and out.getvalue()==run.stdout,'executed reader API')
    worlds=[(10,15,20,18,1,3),(4,0,8,0,0,0),(1,2,1,3,9,20),(30,45,15,18,0,0)]
    for world in worlds:
        expected=reconcile(world);eq(ns['ledger'](world),expected,'alternative raw ledger');a0,a1,b0,b1,c0,d1=map(F,world)
        eq(expected[1]-expected[0],(a1-a0)+(b1-b0)+d1-c0,'partition identity')
        eq(ns['bridge'](world),(a1-a0+b1-b0,d1,-c0,expected[1]-expected[0]),'actual program bridge')
        eq(expected[5],a0/(a0+b0)*(a1/a0-1)+b0/(a0+b0)*(b1/b0-1),'weighted individual identity')
    rejected=0
    bad=[(0,1,50,60,50,80),(100,90,0,60,50,80),(-1,90,50,60,50,80),(True,90,50,60,50,80),(1.,90,50,60,50,80),(100,90,50,60,50)]
    for world in bad:
        for fn in (reconcile,ns['ledger']):
            try:fn(world)
            except ValueError:rejected+=1
            else:raise ValueError('accepted invalid amount')
    for weights,scores in [((25,25,20,15,14),(3,3,3,3,3)),((25,25,20,15,15),(3,3,5,3,3)),((25,25,20,15,15),(3,3,F(7,2),3,3)),((25,25,20,15,15),(True,3,3,3,3)),((25,25,20,15,15),(3,3,3,3))]:
        try:score(weights,scores)
        except ValueError:rejected+=1
        else:raise ValueError('accepted invalid rubric')
    return {'chapter':'v16-c12','status':'passed','runtime_files':4,'worked_cases':2,'full_solutions':8,'comparisons':count,'numeric_groups':len(values),'actual_inline_program_executed':True,'alternative_ledgers':len(worlds),'invalid_domain_rejections':rejected,'qualitative_scope':'Full argument, mock audit/defense, ethics/access and exact solutions read separately; numerical checks do not certify novelty or real learner achievement.'}

if __name__=='__main__':check(Path(sys.argv[1]) if len(sys.argv)>1 else None)
