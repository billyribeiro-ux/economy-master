"""Independent C09 peer oracle; never imports, templates or executes the author checker."""
from pathlib import Path
from html.parser import HTMLParser
from hashlib import sha256
from fractions import Fraction as F
from itertools import combinations
from statistics import NormalDist
import ast,json,math,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
FILES=['production/v16-c09-working.html','production/check_v16_c09_working.py','production/v16-c09-sources-working.json','production/v16-c09-author-review-working.json','production/check_v16_c09_peer_working.py','production/v16-c09-peer-review-working.json']

def need(ok,reason):
    if not ok:raise ValueError('C09 peer: '+reason)

def numeric(text):
    def v(n):
        if isinstance(n,ast.Expression):return v(n.body)
        if isinstance(n,ast.Constant) and type(n.value) in (int,float):return F(str(n.value))
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,ast.USub):return -v(n.operand)
        if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Div):return v(n.left)/v(n.right)
        if isinstance(n,(ast.Tuple,ast.List)):return tuple(v(z) for z in n.elts)
        raise ValueError('unsupported arithmetic syntax')
    return v(ast.parse(text.replace('−','-'),mode='eval'))

class Page(HTMLParser):
    def __init__(self):
        super().__init__();self.stack=[];self.ids=[];self.answers=[];self.exercises=[];self.worked=[];self.sources={};self.values={};self.capture=None;self.code='';self.incode=False;self.data=[];self.row=None;self.cell=None;self.circles=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs);need(len(a)==len(attrs),'unique attributes');need(tag!='h1','fragment')
        if 'id' in a:self.ids.append(a['id'])
        if tag=='article' and 'worked' in a.get('class','').split():self.worked.append(a['id'])
        if tag=='li' and any(t=='ol' and 'exercises' in d.get('class','').split() for t,d in self.stack):self.exercises.append(a['id'])
        if 'data-solution-for' in a:
            need(any(t=='details' and 'solutions' in d.get('class','').split() for t,d in self.stack),'answer disclosure');self.answers.append(a['data-solution-for'])
        if 'data-source' in a:self.sources[a['data-source']]=a['href']
        for kind in ('input','result'):
            if 'data-'+kind in a:
                self.capture=(kind,a['data-'+kind]);need(self.capture not in self.values,'unique numeric marker');self.values[self.capture]=''
        if a.get('id')=='v16-c09-program':self.incode=True
        if tag=='tr':self.row=[]
        if tag in ('td','th'):self.cell=''
        if tag=='circle':self.circles.append((F(a['cx']),F(a['cy'])))
        if tag not in ('br','hr','img','input','meta','link'):self.stack.append((tag,a))
    def handle_data(self,text):
        if self.capture:self.values[self.capture]+=text
        if self.incode:self.code+=text
        if self.cell is not None:self.cell+=text
    def handle_endtag(self,tag):
        need(bool(self.stack) and self.stack[-1][0]==tag,'balanced HTML');_,a=self.stack.pop()
        if 'data-input' in a or 'data-result' in a:self.capture=None
        if a.get('id')=='v16-c09-program':self.incode=False
        if tag in ('td','th'):self.row.append(self.cell.strip());self.cell=None
        if tag=='tr':self.data.append(self.row);self.row=None

def det(m):
    return m[0][0]*(m[1][1]*m[2][2]-m[1][2]*m[2][1])-m[0][1]*(m[1][0]*m[2][2]-m[1][2]*m[2][0])+m[0][2]*(m[1][0]*m[2][1]-m[1][1]*m[2][0])

def primitive(x,y,t):
    n=len(x);need(n==8 and len(y)==n,'eight paired banks');need(len(t)==4 and len(set(t))==4 and all(type(i) is int and 0<=i<n for i in t),'four distinct integer indices')
    signs=tuple(F(1,4) if i in t else F(-1,4) for i in range(n));dy=sum(s*v for s,v in zip(signs,y));dx=sum(s*v for s,v in zip(signs,x))
    design=[(F(1),F(i in t),x[i]) for i in range(n)]
    gram=[[sum(row[i]*row[j] for row in design) for j in range(3)] for i in range(3)]
    rhs=[sum(row[i]*v for row,v in zip(design,y)) for i in range(3)]
    determinant=det(gram);need(determinant!=0,'full regression rank')
    replacement=[row[:] for row in gram]
    for i in range(3):replacement[i][1]=rhs[i]
    return dy,dy-dx,det(replacement)/determinant

def interval(theta,s,blo,bhi):
    need(all(type(v) in (int,float,F) and math.isfinite(v) for v in (theta,s,blo,bhi)),'finite interval inputs');need(s>0 and blo<=bhi,'positive SE and ordered bias')
    z=NormalDist().inv_cdf(.975);return float(theta)-float(bhi)-z*float(s),float(theta)-float(blo)+z*float(s)

def transport(effect,source,target):
    need(len(effect)==len(source)==len(target)>0,'matched strata');need(all(v>=0 for v in source+target) and sum(source)==sum(target)==1,'probability shares');need(all(s>0 or t==0 for s,t in zip(source,target)),'target overlap')
    weights=tuple(t/s if s else F(0) for s,t in zip(source,target));return sum(s*e for s,e in zip(source,effect)),sum(t*e for t,e in zip(target,effect)),weights

def check(root=None):
    root=Path(root) if root is not None else ROOT
    review=json.loads((root/FILES[-1]).read_text());need(set(review['payloads'])==set(FILES[:-1]),'five nonself bindings')
    for name,rec in review['payloads'].items():
        data=(root/name).read_bytes();need(rec=={'bytes':len(data),'sha256':sha256(data).hexdigest()},'frozen '+name)
    need(not review['open_material_findings'] and review['full_manuscript_and_solutions_read'],'full review')
    page=Page();page.feed((root/FILES[0]).read_text());page.close();need(not page.stack and len(page.ids)==len(set(page.ids)),'unique complete fragment')
    ids=[f'v16-c09-e{i}' for i in range(1,11)];need(page.exercises==page.answers==ids,'ten prompt/answer pairs');need(page.worked==[f'v16-c09-case{i}' for i in range(1,4)],'three cases')
    source=json.loads((root/FILES[2]).read_text());need(page.sources=={s['id']:s['url'] for s in source['sources']},'scoped source routes')
    values={k:numeric(v) for k,v in page.values.items()};seen=set();comparisons=0
    def eq(a,b,label,tol=0):
        nonlocal comparisons
        if isinstance(a,tuple) or isinstance(b,tuple):
            need(isinstance(a,tuple) and isinstance(b,tuple) and len(a)==len(b),label+' shape')
            for aa,bb in zip(a,b):eq(aa,bb,label,tol)
        else:need(abs(a-b)<=tol,label);comparisons+=1
    def get(kind,key):seen.add((kind,key));return values[kind,key]
    def output(key,value,tol=0):eq(get('result',key),value,key,tol)
    rows=page.data[1:];need([r[0] for r in rows]==list('ABCDEFGH'),'eight actual table rows')
    z=tuple(int(r[1]) for r in rows);x=tuple(F(r[2]) for r in rows);y=tuple(F(r[3]) for r in rows);t=tuple(i for i,v in enumerate(z) if v)
    need(z==(1,1,1,1,0,0,0,0),'display assignment');observed=primitive(x,y,t);output('curve',observed)
    draw=list(combinations(range(8),4));oracle={a:primitive(x,y,a) for a in draw};maxima={a:max(map(abs,v)) for a,v in oracle.items()};cutoff=max(map(abs,observed));tail=sum(m>=cutoff for m in maxima.values());output('joint-test',(tail,len(draw),F(tail,len(draw))))
    eq(observed,(F(6),F(4),F(19,5)),'raw-data estimates')
    # Complete randomization rank distribution, ties inclusive.
    pvalues=[F(sum(v>=m for v in maxima.values()),len(draw)) for m in maxima.values()]
    for k in range(71):need(F(sum(p<=F(k,70) for p in pvalues),70)<=F(k,70),'rank size');comparisons+=1
    for a in draw:
        complement=tuple(i for i in range(8) if i not in a);eq(oracle[a],tuple(-v for v in oracle[complement]),'assignment complement')
    # Verify actual embedded reader program after independent oracle construction.
    namespace={'__name__':'peer_reader'};exec(compile(page.code,'<actual-c09-reader>','exec'),namespace)
    eq(tuple(namespace['X']),x,'reader X matches table');eq(tuple(namespace['Y']),y,'reader Y matches table')
    for a in draw:eq(namespace['estimates'](a),oracle[a],'reader per-assignment estimates')
    proc=subprocess.run([sys.executable,'-I','-B','-O','-c',page.code],cwd='/',capture_output=True,text=True)
    expected='estimates: '+','.join(map(str,observed))+'\ntail,total,p: '+str(tail)+' '+str(len(draw))+' '+str(F(tail,len(draw)))+'\n'
    need(proc.returncode==0 and not proc.stderr and proc.stdout==expected,'actual optimized reader stdout')
    eq(tuple((px,F(260)-py) for px,py in page.circles),tuple((px,F(30)*v) for px,v in zip((140,260,380),sorted(observed))),'plot points')
    theta,s,b=get('input','bias-inputs');zcrit=NormalDist().inv_cdf(.975)
    output('base-ci',interval(theta,s,0,0),5e-7);output('bias-ci',interval(theta,s,0,b),5e-7);output('tipping',(theta,float(theta)-zcrit*float(s)),5e-7);output('two-sided-ci',interval(theta,s,-b,b),5e-7);output('e5-lower',interval(theta,s/2,0,b)[0],5e-7)
    # Direct Gaussian probability of the union covering tau, for all selected true biases.
    coverage=[]
    for actual in (0,float(b)/2,float(b)):
        # theta_hat = tau + actual + s Z; union covers iff -actual/s-z <= Z <= (B-actual)/s+z.
        c=NormalDist().cdf((float(b)-actual)/float(s)+zcrit)-NormalDist().cdf(-actual/float(s)-zcrit)
        need(c>=.95-1e-14,'uniform union coverage witness');coverage.append(c);comparisons+=1
    eq(NormalDist().cdf(zcrit)-NormalDist().cdf(-zcrit),.95,'central event',1e-14)
    need(interval(theta,s,0,b)[0]<0<interval(theta,s,0,b)[1] and theta-b>0,'point/sign distinction')
    effects=get('input','effects');source_shares=get('input','source-shares');target=get('input','target-shares');sm,tm,w=transport(effects,source_shares,target)
    output('transport-averages',(sm,tm));output('transport-gap',sm-tm);output('transport-weights',w);eq(sum(a*b for a,b in zip(source_shares,w)),1,'weight normalization');eq(sum(a*b*c for a,b,c in zip(source_shares,w,effects)),tm,'weighted target')
    output('mix-range',tuple(p*effects[0]+(1-p)*effects[1] for p in (F(1,10),F(2,5))))
    supported=F(1,5)*effects[0]+F(3,5)*effects[1];output('unsupported-range',(supported-F(1,5),supported+F(3,5)));output('e8-supported',supported/F(4,5))
    unstable=sum(p*e for p,e in zip(target,(F(1),F(-1,2))));output('unstable-target',unstable);output('e9-gap',unstable-tm)
    for missing in (F(-1),F(0),F(1),F(2),F(3)):
        full=supported+F(1,5)*missing;need(F(1,2)<=full<=F(13,10),'sharp interval witness');eq((full-supported)*5,missing,'recover unsupported effect')
    for desired in (F(-10),F(0),F(10)):eq(supported+F(1,5)*(5*(desired-supported)),desired,'unrestricted target witness')
    need(seen==set(values),'all numeric markers inspected')
    # Affine outcome and constant-shift cases independently test invariances.
    for yy in (tuple(v+7 for v in y),tuple(2*v for v in y),tuple(2+3*v for v in x)):
        vals=primitive(x,yy,t)
        if yy==tuple(v+7 for v in y):eq(vals,observed,'outcome location invariance')
        elif yy==tuple(2*v for v in y):eq(vals,(2*observed[0],observed[0]+observed[1],2*observed[2]),'outcome-only scale with fixed baseline')
        else:eq(vals,(F(6),F(4),F(0)),'exact baseline prediction')
    eq(transport((F(-1),F(3)),(F(1,2),F(1,2)),(F(1),F(0)))[1],F(-1),'alternative target')
    bad=[lambda:primitive(x,y,()),lambda:primitive(x,y,(0,0,1,2)),lambda:primitive(x,y,(0,1,2,8)),lambda:primitive(x,y,(False,1,2,3)),lambda:primitive((F(1),)*8,y,t),lambda:interval(1,0,0,1),lambda:interval(1,1,2,1),lambda:interval(float('nan'),1,0,1),lambda:transport(effects,(F(1),F(0)),target),lambda:transport(effects,(F(-1),F(2)),target),lambda:transport(effects,(F(1,2),F(1,2)),(F(1),F(1))),lambda:transport(effects,(F(1),),(F(1),))]
    bad_reader=[(),(0,0,1,2),(0,1,2,8),(False,1,2,3)]
    rejected=0
    for f in bad+[lambda a=a:namespace['estimates'](a) for a in bad_reader]:
        try:f()
        except ValueError:rejected+=1
        else:raise ValueError('C09 peer: invalid domain accepted')
    return {'chapter':'v16-c09','status':'passed','runtime_files':6,'worked_cases':3,'solutions':10,'numeric_markers':len(values),'comparisons':comparisons,'exact_assignment_worlds':len(draw),'union_coverage_witnesses':len(coverage),'invalid_domains':rejected,'actual_optimized_inline_executions':1,'author_checker':'hash-bound only; no template/import/execution','qualitative_review':'Full manuscript, proofs, all ten prompt/solutions, sources and retention read separately.'}

if __name__=='__main__':
    need(len(sys.argv)<=2,'at most one root argument');check(sys.argv[1] if len(sys.argv)==2 else None)
