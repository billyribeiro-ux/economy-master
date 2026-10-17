"""Quiet exact-four author audit; independent linear algebra and finite-law checks."""
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
from itertools import combinations, product
from pathlib import Path
FILES=('content/chapters/v16-c09.html','scripts/check_v16_c09.py','content/reviews/v16-c09-sources.json','content/reviews/v16-c09-author.json')
def need(ok,label):
    if not ok:raise ValueError(label)
def numeric(s):
    def read(n):
        if isinstance(n,ast.Constant):
            need(type(n.value) in (int,float),'numeric literal');return F(str(n.value))
        if isinstance(n,(ast.Tuple,ast.List)):return tuple(read(x) for x in n.elts)
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,(ast.USub,ast.UAdd)):return (-1 if isinstance(n.op,ast.USub) else 1)*read(n.operand)
        if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Div):return read(n.left)/read(n.right)
        raise ValueError('literal number required')
    return read(ast.parse(s,mode='eval').body)
class Reader(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.stack=[];self.active=[];self.inputs={};self.results={};self.code={};self.cells=[];self.ids=[];self.ex=[];self.sol=[];self.cases=[];self.sources={};self.plot=[]
    def handle_starttag(self,t,attrs):
        a=dict(attrs);need(t!='h1','fragment heading')
        if 'id' in a:need(a['id'] not in self.ids and a['id'].startswith('v16-c09-'),'prefixed unique IDs');self.ids.append(a['id'])
        if t=='article' and 'worked' in a.get('class','').split():self.cases.append(a['id'])
        if t=='li' and a.get('id','').startswith('v16-c09-e'):
            need(any(x=='ol' and 'exercises' in y.get('class','').split() for x,y in self.stack),'exercise list');self.ex.append(a['id'])
        if 'data-solution-for' in a:
            need(any(x=='details' and 'solutions' in y.get('class','').split() for x,y in self.stack),'solution disclosure');self.sol.append(a['data-solution-for'])
        if 'data-source' in a:need(a['data-source'] not in self.sources,'unique source');self.sources[a['data-source']]=a['href']
        for attr,d in (('data-input',self.inputs),('data-result',self.results)):
            if attr in a:
                k=a[attr];need(k not in d,'unique marker');d[k]='';self.active.append((d,k,len(self.stack)))
        if t=='code' and a.get('id')=='v16-c09-program':self.code['program']='';self.active.append((self.code,'program',len(self.stack)))
        if t=='td' and any(y.get('id')=='v16-c09-data' for x,y in self.stack):self.cells.append('');self.active.append((self.cells,len(self.cells)-1,len(self.stack)))
        if t=='polyline':self.plot.append(a.get('points'))
        if t not in ('br','hr','img','meta','link','input'):self.stack.append((t,a))
    def handle_data(self,s):
        for d,k,_ in self.active:d[k]+=s
    def handle_endtag(self,t):
        need(self.stack and self.stack[-1][0]==t,'balanced HTML');self.stack.pop();self.active=[x for x in self.active if x[2]<len(self.stack)]
def solve(matrix,rhs):
    a=[list(row)+[b] for row,b in zip(matrix,rhs)];n=len(a)
    for col in range(n):
        pivot=next((j for j in range(col,n) if a[j][col]),None);need(pivot is not None,'full rank')
        a[col],a[pivot]=a[pivot],a[col];div=a[col][col];a[col]=[v/div for v in a[col]]
        for j in range(n):
            if j!=col:
                scale=a[j][col];a[j]=[x-scale*y for x,y in zip(a[j],a[col])]
    return tuple(row[-1] for row in a)
def independent_estimates(x,y,t):
    z=tuple(F(i in t) for i in range(len(x)));rows=tuple((F(1),zi,xi) for zi,xi in zip(z,x))
    gram=tuple(tuple(sum(row[i]*row[j] for row in rows) for j in range(3)) for i in range(3))
    rhs=tuple(sum(row[j]*yi for row,yi in zip(rows,y)) for j in range(3));beta=solve(gram,rhs)
    # Balanced design contrast implemented as a signed dot product, not centering.
    contrast=lambda v:sum((2*zi-1)*vi for zi,vi in zip(z,v))/4
    return contrast(y),contrast(tuple(yi-xi for xi,yi in zip(x,y))),beta[1]
def quantile(p):
    lo,hi=-10.,10.
    for _ in range(100):
        m=(lo+hi)/2
        if math.erfc(-m/math.sqrt(2))/2<p:lo=m
        else:hi=m
    return (lo+hi)/2

def transport(shares,effects):
    need(len(shares)==len(effects) and len(shares)>0,'matching strata')
    need(all(type(x) in (int,F) for x in shares+effects),'exact rational inputs')
    need(all(x>=0 for x in shares) and sum(shares)==1,'probability shares')
    return sum(w*t for w,t in zip(shares,effects))
def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    raw={p:(root/p).read_bytes() for p in FILES};review=json.loads(raw[FILES[3]]);sources=json.loads(raw[FILES[2]])
    bindings=review['payload_bindings'];need(len(bindings)==3 and {b['path'] for b in bindings}==set(FILES[:3]),'three nonself bindings')
    for b in bindings:
        v=raw[b['path']];need((len(v),sha256(v).hexdigest())==(b['bytes'],b['sha256']),'author freeze')
    doc=Reader();doc.feed(raw[FILES[0]].decode());doc.close();need(not doc.stack,'closed fragment')
    ex=['v16-c09-e'+str(i) for i in range(1,11)];need(doc.ex==doc.sol==ex and set(review['exact_prompt_review'])==set(ex),'ten exact reviewed solutions')
    need(doc.cases==['v16-c09-case'+str(i) for i in range(1,4)],'three worked cases')
    need(doc.sources=={s['id']:s['url'] for s in sources['sources']} and len(doc.sources)==3,'scoped primary sources')
    actual_data=tuple(tuple(F(v) for v in doc.cells[j:j+3]) for j in range(0,len(doc.cells),3))
    expected_data=((1,8,12),(1,10,15),(1,12,16),(1,14,21),(0,6,8),(0,8,8),(0,10,12),(0,12,12))
    need(actual_data==expected_data,'actual reader input table')
    x=tuple(row[1] for row in actual_data);y=tuple(row[2] for row in actual_data);t=tuple(i for i,row in enumerate(actual_data) if row[0])
    obs=independent_estimates(x,y,t);assignments=list(combinations(range(8),4))
    family=[independent_estimates(x,y,a) for a in assignments];maxima=[max(map(abs,v)) for v in family];cutoff=max(map(abs,obs));tail=sum(v>=cutoff for v in maxima)
    inputs={k:numeric(v) for k,v in doc.inputs.items()};shown={k:numeric(v) for k,v in doc.results.items()}
    need(inputs=={'bias-inputs':(F(6,5),F(2,5),F(3,5)),'effects':(F(2),F(1,2)),'source-shares':(F(3,4),F(1,4)),'target-shares':(F(1,4),F(3,4))},'displayed assumptions')
    count=0
    def eq(a,b,label,tol=0):
        nonlocal count
        if isinstance(a,(tuple,list)) or isinstance(b,(tuple,list)):
            need(isinstance(a,(tuple,list)) and isinstance(b,(tuple,list)) and len(a)==len(b),label+' shape')
            for av,bv in zip(a,b):eq(av,bv,label,tol)
        else:
            count+=1;need(abs(float(a)-float(b))<=tol if tol else a==b,label)
    point,se,budget=map(float,inputs['bias-inputs']);z=quantile(.975)
    ps,pt,effects=inputs['source-shares'],inputs['target-shares'],inputs['effects']
    expected={'curve':obs,'joint-test':(tail,len(assignments),F(tail,len(assignments))),
              'base-ci':(point-z*se,point+z*se),'bias-ci':(point-budget-z*se,point+z*se),
              'tipping':(point,point-z*se),'two-sided-ci':(point-budget-z*se,point+budget+z*se),
              'transport-averages':(transport(ps,effects),transport(pt,effects)),
              'transport-gap':transport(ps,effects)-transport(pt,effects),
              'transport-weights':tuple(b/a for a,b in zip(ps,pt)),
              'mix-range':tuple(transport((h,1-h),effects) for h in (F(1,10),F(2,5))),
              'unsupported-range':(F(7,10)-F(1,5),F(7,10)+F(3,5)),
              'unstable-target':transport(pt,(F(1),F(-1,2))),
              'e5-lower':point-budget-z*se/2,'e8-supported':F(7,10)/F(4,5),
              'e9-gap':transport(pt,(F(1),F(-1,2)))-transport(pt,effects)}
    need(set(shown)==set(expected),'all displayed results')
    rounded={'base-ci','bias-ci','tipping','two-sided-ci','e5-lower'}
    for k,v in expected.items():eq(shown[k],v,k,5.01e-7 if k in rounded else 0)
    need(doc.plot==['140,146 260,140 380,80'],'plotted sorted estimates');eq(tuple(260-30*v for v in sorted(obs)),(146,140,80),'plot data coordinates')
    code=doc.code['program'];run=subprocess.run([sys.executable,'-I','-B','-O','-c',code],cwd='/',capture_output=True,text=True,timeout=15)
    transcript='estimates: '+','.join(map(str,obs))+'\ntail,total,p: '+str(tail)+' '+str(len(assignments))+' '+str(F(tail,len(assignments)))+'\n'
    need(run.returncode==0 and run.stderr=='' and run.stdout==transcript,'actual inline optimized exact transcript')
    ns={'__name__':'reader_api'};out=io.StringIO();err=io.StringIO()
    with contextlib.redirect_stdout(out),contextlib.redirect_stderr(err):exec(compile(code,'<reader>','exec'),ns)
    need(out.getvalue()==err.getvalue()=='','quiet reader import');need(ns['X']==x and ns['Y']==y,'embedded data match table')
    for a,v in zip(assignments,family):eq(ns['estimates'](a),v,'independent full OLS assignment')
    pvalues=[F(sum(v>=m for v in maxima),len(maxima)) for m in maxima]
    for alpha in (F(0),F(1,20),F(1,10),F(1,4),F(1,2),F(1)):
        need(F(sum(p<=alpha for p in pvalues),len(pvalues))<=alpha,'finite null size');count+=1
    for a,v in zip(assignments,family):
        complement=tuple(i for i in range(8) if i not in a);eq(independent_estimates(x,y,complement),tuple(-j for j in v),'assignment complement symmetry')
    for shift,scale in ((F(5),F(1)),(F(0),F(3)),(F(-2),F(2))):
        yy=tuple(shift+scale*yi for yi in y)
        eq(independent_estimates(tuple(scale*xi for xi in x),yy,t),tuple(scale*v for v in obs),'common flow units and outcome origin')
    # One common sampling-error event implies coverage of every allowed bias case.
    for bias in (0.,.2,.6):
        theta=point;tau=theta-bias
        for standardized in (-z,-1.,0.,1.,z):
            estimate=theta+se*standardized
            need(estimate-budget-z*se-1e-14<=tau<=estimate+z*se+1e-14,'uniform bias interval event');count+=1
    for source_h,target_h in product((F(1,10),F(1,2),F(9,10)),(F(0),F(1,4),F(3,4),F(1))):
        ss=(source_h,1-source_h);tt=(target_h,1-target_h);ww=tuple(t/s for s,t in zip(ss,tt))
        eq(sum(s*w for s,w in zip(ss,ww)),1,'weight normalization')
        eq(sum(s*w*e for s,w,e in zip(ss,ww,effects)),transport(tt,effects),'standardization identity')
    for u in (F(-1),F(0),F(1),F(2),F(3)):
        val=transport((F(1,5),F(3,5),F(1,5)),effects+(u,));eq(val,F(7,10)+u/5,'sharp unsupported witness');need(F(1,2)<=val<=F(13,10),'bounded witness')
    for desired in (F(-100),F(0),F(100)):
        u=5*(desired-F(7,10));eq(transport((F(1,5),F(3,5),F(1,5)),effects+(u,)),desired,'unrestricted unsupported witness')
    rejected=0
    for indices in ((),(0,1,2),(0,1,2,2),(0,1,2,8),(-1,1,2,3),(True,2,3,4),(0.,1,2,3)):
        try:ns['estimates'](indices)
        except ValueError:rejected+=1
        else:raise ValueError('invalid assignment accepted')
    for shares,eff in (((),()),((F(1),),effects),((F(-1),F(2)),effects),((F(1),F(1)),effects),((.5,.5),effects)):
        try:transport(shares,eff)
        except ValueError:rejected+=1
        else:raise ValueError('invalid transport domain accepted')
    for p,v in raw.items():need((root/p).read_bytes()==v,'runtime bytes unchanged')
    return {'chapter':'v16-c09','status':'passed','worked_cases':3,'solutions':10,'input_groups':len(inputs),'result_groups':len(shown),'comparisons':count,'exact_assignment_worlds':len(assignments),'rejected_inputs':rejected,'displayed_program_executed':True,'runtime_files':4,'qualitative_scope':'Full author proof/prose review recorded; independent acceptance pending.'}
if __name__=='__main__':check()
