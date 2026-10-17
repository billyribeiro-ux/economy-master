"""Quiet stdlib audit: exact plan decisions and independent normal-tail arithmetic."""
from pathlib import Path
from html.parser import HTMLParser
from hashlib import sha256
from fractions import Fraction as F
import ast,json,math,subprocess,sys,types
ROOT=Path(__file__).resolve().parents[1]
FILES=['production/v16-c08-working.html','production/check_v16_c08_working.py','production/v16-c08-sources-working.json','production/v16-c08-author-review-working.json']

def require(ok,msg):
    if not ok:raise ValueError('C08: '+msg)

def cdf(x):return math.erfc(-x/math.sqrt(2))/2

def inverse(p):
    require(0<p<1,'probability interior')
    lo,hi=-40.,40.
    for _ in range(90):
        mid=(lo+hi)/2
        if cdf(mid)<p:lo=mid
        else:hi=mid
    return (lo+hi)/2

def oracle(n,sigma,effect,alpha=.025):
    se=sigma*math.sqrt(2/n);cut=inverse(1-alpha/2);mu=abs(effect)/se
    return cdf(mu-cut)+cdf(-mu-cut)

def threshold(sigma,effect):
    for n in range(1,10001):
        if oracle(n,sigma,effect)>=.8:return n
    raise ValueError('threshold outside finite search')

class Page(HTMLParser):
    def __init__(self):
        super().__init__();self.stack=[];self.ids=[];self.worked=[];self.exercises=[];self.answers=[];self.sources={};self.markers={};self.capture=None;self.code='';self.incode=False;self.tables=[];self.row=None;self.cell=None
    def handle_starttag(self,tag,attrs):
        a=dict(attrs);require(len(a)==len(attrs),'unique attributes');require(tag!='h1','fragment h1')
        if 'id' in a:self.ids.append(a['id'])
        if tag=='article' and 'worked' in a.get('class','').split():self.worked.append(a.get('id'))
        if tag=='li' and any(t=='ol' and 'exercises' in d.get('class','').split() for t,d in self.stack):self.exercises.append(a.get('id'))
        if 'data-solution-for' in a:
            require(any(t=='details' and 'solutions' in d.get('class','').split() for t,d in self.stack),'disclosed solutions');self.answers.append(a['data-solution-for'])
        if 'data-source' in a:self.sources[a['data-source']]=a['href']
        for kind in ['input','result']:
            if 'data-'+kind in a:
                self.capture=(kind,a['data-'+kind]);require(self.capture not in self.markers,'unique number marker');self.markers[self.capture]=''
        if a.get('id')=='v16-c08-program':self.incode=True
        if tag=='table':self.tables.append([])
        if tag=='tr':self.row=[]
        if tag in ('th','td'):self.cell=''
        if tag not in ('br','hr','img','meta','link','input'):self.stack.append((tag,a))
    def handle_data(self,s):
        if self.capture:self.markers[self.capture]+=s
        if self.incode:self.code+=s
        if self.cell is not None:self.cell+=s
    def handle_endtag(self,tag):
        require(bool(self.stack) and self.stack[-1][0]==tag,'balanced HTML');_,a=self.stack.pop()
        if 'data-input' in a or 'data-result' in a:self.capture=None
        if a.get('id')=='v16-c08-program':self.incode=False
        if tag in ('th','td'):self.row.append(self.cell.strip());self.cell=None
        if tag=='tr':self.tables[-1].append(self.row);self.row=None

def check(root=None):
    root=Path(root) if root is not None else ROOT
    review=json.loads((root/FILES[-1]).read_text());require(set(review['payloads'])==set(FILES[:-1]),'three nonself runtime hashes')
    for name,rec in review['payloads'].items():
        b=(root/name).read_bytes();require(rec=={'bytes':len(b),'sha256':sha256(b).hexdigest()},'frozen '+name)
    require(all(review['review'].values()) and not review['open_material_findings'],'full author review')
    page=Page();page.feed((root/FILES[0]).read_text());page.close()
    require(not page.stack and len(page.ids)==len(set(page.ids)),'complete unique fragment')
    ids=[f'v16-c08-e{i}' for i in range(1,9)];require(page.exercises==ids and page.answers==ids,'eight paired prompts/solutions')
    require(page.worked==['v16-c08-case1','v16-c08-case2'],'two substantive artifacts')
    sources=json.loads((root/FILES[2]).read_text());require(page.sources=={s['id']:s['url'] for s in sources['sources']},'source routes')
    values={k:ast.literal_eval(v) for k,v in page.markers.items()};count=0
    def compare(a,b,label,tol=0):
        nonlocal count
        if isinstance(b,(list,tuple)):
            require(len(a)==len(b),label+' shape')
            for x,y in zip(a,b):compare(x,y,label,tol)
        elif isinstance(b,(int,float,F)):
            require(abs(a-b)<=tol,label);count+=1
        else:require(a==b,label);count+=1
    def displayed(name,value,tol=0):compare(values[('result',name)],value,name,tol)
    inputs=values[('input','baseline')];compare(inputs,(80,2,1,.025),'baseline')
    n,sigma,effect,alpha=inputs;se=sigma*math.sqrt(2/n);cut=inverse(1-alpha/2);base=oracle(*inputs)
    displayed('critical',cut,5.1e-7);displayed('se',se,5.1e-7);displayed('noncentrality',effect/se,5.1e-7);displayed('baseline-power',base,5.1e-7)
    scenarios=[(40,2,1),(76,2,1),(77,2,1),(80,2,1),(80,3,1),(80,2,.5)]
    table=page.tables[0];require(len(table)==7,'six sensitivity rows')
    for row,(size,sd,delta) in zip(table[1:],scenarios):
        compare([float(x) for x in row[:3]],(size,sd,delta),'actual visible scenario primitives')
        compare(float(row[3]),oracle(size,sd,delta),'actual visible power',5.1e-7)
    minima=[threshold(sd,d) for sd,d in [(2,1),(3,1),(2,.5)]];displayed('minimum-sizes',minima)
    for size,(sd,d) in zip(minima,[(2,1),(3,1),(2,.5)]):require(oracle(size-1,sd,d)<.8<=oracle(size,sd,d),'unrounded size boundary')
    # Execute actual copyable program, independently compare its stdout and API.
    module=types.ModuleType('C08_inline');exec(compile(page.code,'<C08-inline>','exec'),module.__dict__)
    proc=subprocess.run([sys.executable,'-I','-B','-O','-'],input=page.code,cwd='/',capture_output=True,text=True)
    require(proc.returncode==0 and not proc.stderr,'actual optimized inline code execution')
    expected=''.join(f'{size} {sd} {d} {oracle(size,sd,d):.6f}\n' for size,sd,d in scenarios)+'minimum per arm: '+str(minima)+'\n'
    compare(proc.stdout,expected,'complete inline stdout')
    for size,sd,d in scenarios:compare(module.power(size,sd,d),oracle(size,sd,d),'independent CDF oracle',1e-12)
    for sd,d in [(2,1),(3,1),(2,.5)]:compare(module.minimum_n(sd,d),threshold(sd,d),'actual minimum search')
    p=values[('input','raw-p')];compare(p,(.018,.041),'raw illustration')
    adjusted=tuple(min(F(1),2*F(str(x))) for x in p);displayed('adjusted-p',tuple(float(x) for x in adjusted))
    displayed('unadjusted-family',float(1-F(95,100)**2));displayed('adjusted-family',float(1-F(975,1000)**2))
    displayed('e1-se',4*math.sqrt(2/80),5.1e-7);displayed('e1-power',oracle(80,4,2),5.1e-7);displayed('e1-joint-lower',2*base-1,5.1e-7)
    displayed('e2-total',2*minima[0]);displayed('e3-total',2*minima[1]);ep=values[('input','exercise-p')];compare(ep,(.025,.026),'boundary p primitives');displayed('e4-adjusted',tuple(float(min(F(1),2*F(str(x)))) for x in ep))
    displayed('e5-powers',(base,oracle(80,2,.5)),5.1e-7)
    require([F(str(x))<=F(25,1000) for x in ep]==[True,False],'exact p-value boundary decisions')
    # Alternative/domain witnesses: no dependence on the six display cases alone.
    for size in (1,17,80,301):
        compare(module.power(size,2,0),.025,'null rejection probability',1e-12)
        for delta in (.1,1,4):
            compare(module.power(size,2,-delta),module.power(size,2,delta),'two-sided symmetry',1e-14)
            compare(module.power(size,6,3*delta),module.power(size,2,delta),'joint unit rescaling',1e-14)
    require(module.power(80,2,1,.05)>base,'one-test threshold would change power')
    # Bonferroni union bound illustrated without independence: disjoint null rejection events attain .05.
    sample=range(2000);r1={i for i in sample if i<50};r2={i for i in sample if 50<=i<100}
    compare(F(len(r1|r2),len(sample)),F(1,20),'sharp union bound without independence')
    rejected=0
    for args in [(True,2,1),(0,2,1),(2.5,2,1),(80,0,1),(80,-2,1),(80,True,1),(80,2,float('nan')),(80,2,float('inf')),(80,2,1,0),(80,2,1,1)]:
        try:module.power(*args)
        except ValueError:rejected+=1
        else:raise ValueError('bad power primitive accepted')
    for args in [(2,1,0),(2,1,1),(2,1,True),(2,1,float('nan')),(2,0,.8)]:
        try:module.minimum_n(*args)
        except ValueError:rejected+=1
        else:raise ValueError('bad/unreachable target accepted')
    return {'status':'passed','runtime_files':4,'worked_cases':2,'exercises_and_solutions':8,'numeric_markers':len(values),'comparisons':count,'power_scenarios':6,'integer_thresholds':3,'invalid_or_unreachable_domains':rejected,'actual_inline_optimized_executions':1,'qualitative_review':'Full plan, knowledge/timing, multiplicity and contingency reading recorded separately.'}

if __name__=='__main__':check(Path(sys.argv[1]) if len(sys.argv)>1 else None)
