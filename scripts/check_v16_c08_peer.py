"""Independent C08 peer audit. Author checker is hashed only, never executed/read as code."""
import ast
import contextlib
import io
import json
import math
import subprocess
import sys
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from pathlib import Path

FILES=('content/chapters/v16-c08.html','scripts/check_v16_c08.py','content/reviews/v16-c08-sources.json','content/reviews/v16-c08-author.json','scripts/check_v16_c08_peer.py','content/reviews/v16-c08-peer.json')
def require(ok,label):
    if not ok:raise ValueError(label)
class Manuscript(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.stack=[];self.active=[];self.values={};self.inputs={};self.code={};self.cells=[];self.ex=[];self.sol=[];self.cases=[];self.sources={};self.ids=[]
    def handle_starttag(self,t,attrs):
        a=dict(attrs);require(t!='h1','fragment headings')
        if 'id' in a:
            require(a['id'] not in self.ids,'unique IDs');self.ids.append(a['id'])
        if t=='article' and 'worked' in a.get('class','').split():self.cases.append(a.get('id'))
        if t=='li' and a.get('id','').startswith('v16-c08-e'):self.ex.append(a['id'])
        if 'data-solution-for' in a:
            require(any(x=='details' and 'solutions' in y.get('class','').split() for x,y in self.stack),'solution context');self.sol.append(a['data-solution-for'])
        if 'data-source' in a:self.sources[a['data-source']]=a.get('href')
        for key,d in (('data-input',self.inputs),('data-result',self.values)):
            if key in a:
                name=a[key];require(name not in d,'unique numeric marker');d[name]='';self.active.append((d,name,len(self.stack)))
        if t=='code' and a.get('id')=='v16-c08-program':
            self.code['program']='';self.active.append((self.code,'program',len(self.stack)))
        if t=='td' and any(y.get('id')=='v16-c08-case1' for x,y in self.stack):
            self.cells.append('');self.active.append((self.cells,len(self.cells)-1,len(self.stack)))
        if t not in ('br','hr','img','meta','link','input'):self.stack.append((t,a))
    def handle_data(self,s):
        for d,k,_ in self.active:d[k]+=s
    def handle_endtag(self,t):
        require(self.stack and self.stack[-1][0]==t,'balanced fragment');self.stack.pop();self.active=[a for a in self.active if a[2]<len(self.stack)]
def cdf(x):return math.erfc(-x/math.sqrt(2))/2
def quantile(p):
    lo,hi=-12.,12.
    for _ in range(100):
        mid=(lo+hi)/2
        if cdf(mid)<p:lo=mid
        else:hi=mid
    return (lo+hi)/2
CRITICAL=quantile(.9875)
def oracle(n,sigma,effect,alpha=.025):
    shift=abs(effect)*math.sqrt(n/2)/sigma
    c=CRITICAL if alpha==.025 else quantile(1-alpha/2)
    return cdf(shift-c)+cdf(-shift-c)
def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    payload={p:(root/p).read_bytes() for p in FILES}
    review=json.loads(payload[FILES[5]]);sources=json.loads(payload[FILES[2]])
    bindings=review['payload_bindings'];require(len(bindings)==5 and {b['path'] for b in bindings}==set(FILES[:5]),'five nonself hashes')
    for b in bindings:
        p=payload[b['path']];require((len(p),sha256(p).hexdigest())==(b['bytes'],b['sha256']),'exact frozen peer inputs')
    doc=Manuscript();doc.feed(payload[FILES[0]].decode());doc.close();require(not doc.stack,'closed HTML')
    ex=['v16-c08-e'+str(i) for i in range(1,9)]
    require(doc.ex==doc.sol==ex and set(review['exact_prompt_review'])==set(ex),'eight complete reviewed solutions')
    require(doc.cases==['v16-c08-case1','v16-c08-case2'],'two full cases')
    require(doc.sources=={s['id']:s['url'] for s in sources['sources']},'source mappings')
    require(sources['actual_inspector']=='integrated_case_peer','preserve primary inspector')
    inputs={k:ast.literal_eval(v) for k,v in doc.inputs.items()};values={k:ast.literal_eval(v) for k,v in doc.values.items()}
    require(inputs=={'baseline':(80,2,1,.025),'raw-p':(.018,.041),'exercise-p':(.025,.026)},'actual numerical inputs')
    count=0
    def near(a,b,label,tol=5.01e-7):
        nonlocal count
        if isinstance(a,(tuple,list)) or isinstance(b,(tuple,list)):
            require(isinstance(a,(tuple,list)) and isinstance(b,(tuple,list)) and len(a)==len(b),label+' shape')
            for x,y in zip(a,b):near(x,y,label,tol)
        else:count+=1;require(abs(float(a)-float(b))<=tol,label)
    # Thresholds derive from every preceding integer, not an approximation followed by rounding.
    thresholds=[]
    for sigma,delta in ((2,1),(3,1),(2,.5)):
        powers=[oracle(n,sigma,delta) for n in range(1,306)]
        n=next(i+1 for i,p in enumerate(powers) if p>=.8);thresholds.append(n)
        require(all(p<.8 for p in powers[:n-1]) and powers[n-1]>=.8,'first integer boundary');count+=n
    power=oracle(*inputs['baseline']);se=2*math.sqrt(2/80)
    expected={'critical':CRITICAL,'se':se,'noncentrality':1/se,'baseline-power':power,'minimum-sizes':tuple(thresholds),
              'adjusted-p':tuple(min(1,2*p) for p in inputs['raw-p']),
              'unadjusted-family':1-F(95,100)**2,'adjusted-family':1-F(975,1000)**2,
              'e1-se':4*math.sqrt(2/80),'e1-power':oracle(80,4,2),'e1-joint-lower':max(0,2*power-1),
              'e2-total':2*thresholds[0],'e3-total':2*thresholds[1],
              'e4-adjusted':tuple(min(1,2*p) for p in inputs['exercise-p']),
              'e5-powers':(oracle(80,2,1),oracle(80,2,.5))}
    require(set(values)==set(expected),'every visible numeric result')
    for k,v in expected.items():near(values[k],v,k)
    scenarios=((40,2,1),(76,2,1),(77,2,1),(80,2,1),(80,3,1),(80,2,.5))
    require(len(doc.cells)==24,'six actual table rows')
    for i,(n,s,e) in enumerate(scenarios):
        near(tuple(float(x) for x in doc.cells[4*i:4*i+3]),(s,e,oracle(n,s,e)),'actual table row')
    code=doc.code['program'];run=subprocess.run([sys.executable,'-I','-B','-O','-c',code],cwd='/',capture_output=True,text=True,timeout=15)
    transcript=''.join(f'{n} {s} {e} {oracle(n,s,e):.6f}\n' for n,s,e in scenarios)+'minimum per arm: '+str(thresholds)+'\n'
    require(run.returncode==0 and run.stdout==transcript and run.stderr=='','actual inline program independent transcript')
    ns={'__name__':'independent_reader_module'};out=io.StringIO();err=io.StringIO()
    with contextlib.redirect_stdout(out),contextlib.redirect_stderr(err):exec(compile(code,'<reader-code>','exec'),ns)
    require(out.getvalue()==err.getvalue()=='','inline module quiet')
    actual=ns['power'];minimum=ns['minimum_n']
    for n in (1,40,80,305):
        for s in (1,2,4):
            for effect in (0,.5,1,-1,2):
                for alpha in (.025,.05,.1):near(actual(n,s,effect,alpha),oracle(n,s,effect,alpha),'independent alternative normal probabilities',3e-13)
    for s,e,n in ((2,1,77),(3,1,172),(2,.5,305)):
        near(minimum(s,e),n,'actual threshold',0);near(minimum(s,-e),n,'effect sign symmetry',0)
    # Independent joint-null witnesses: coincident versus disjoint false-rejection events.
    grid=[F(i,400) for i in range(1,401)];alpha=F(1,40)
    same=sum(u<=alpha for u in grid)/400
    shifted=sum(u<=alpha or ((u+alpha-1) if u+alpha>1 else u+alpha)<=alpha for u in grid)/400
    near(same,alpha,'perfect dependence family',0);near(shifted,2*alpha,'disjoint family bound attained',0)
    near(1-F(19,20)**2,F(39,400),'unadjusted independent family exact',0)
    require([p<=.025 for p in inputs['raw-p']]==[True,False] and [p<=.025 for p in inputs['exercise-p']]==[True,False],'inclusive unrounded decision boundary')
    # A common uniform latent variable gives joint success p; complementary intervals give max(0,2p-1).
    require(max(0,2*power-1)<power*power<power,'marginal power does not identify joint success')
    invalid=[(0,2,1),(-1,2,1),(True,2,1),(1.5,2,1),(80,0,1),(80,-1,1),(80,2,float('nan')),(80,float('inf'),1),(80,2,True),(80,2,1,0),(80,2,1,1),(80,2,1,float('nan'))]
    rejected=0
    for args in invalid:
        try:actual(*args)
        except ValueError:rejected+=1
        else:raise ValueError('invalid inline input accepted')
    for args in ((2,1,0),(2,1,1),(2,1,True),(2,1,float('nan')),(2,0,.8)):
        try:minimum(*args)
        except ValueError:rejected+=1
        else:raise ValueError('invalid or unreachable target accepted')
    for p,b in payload.items():require((root/p).read_bytes()==b,'runtime payload changed')
    return {'chapter':'v16-c08','status':'passed','runtime_files':6,'worked_cases':2,'solutions':8,'result_groups':len(values),'independent_comparisons':count,'integer_thresholds':thresholds,'actual_inline_program_executed':True,'invalid_or_unreachable_domains':rejected,'qualitative_review':'Full independent prose, PAP, exact prompt and source-record reading separately recorded.'}
if __name__=='__main__':check()
