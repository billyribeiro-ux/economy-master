"""Read-only four-file Form A audit; scoring, teaching artifacts and independent model calculations."""
import ast
import json
import math
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from itertools import product
from pathlib import Path
FILES=('content/assessments/parts/v17-exam-a.html','scripts/check_v17_exam_a.py','content/reviews/v17-exam-a-sources.json','content/reviews/v17-exam-a-author.json')
DOMAINS=('alignment_explanation','course_seminar_design','assessment_feedback','communication_supervision','observation_portfolio')
def need(ok,label):
    if not ok:raise ValueError(label)
def literal(text):
    def read(n):
        if isinstance(n,ast.Constant):
            need(type(n.value) in (int,float),'numeric literal');return F(str(n.value))
        if isinstance(n,(ast.Tuple,ast.List)):return tuple(read(x) for x in n.elts)
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,(ast.USub,ast.UAdd)):return (-1 if isinstance(n.op,ast.USub) else 1)*read(n.operand)
        if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Div):return read(n.left)/read(n.right)
        raise ValueError('exact literal expected')
    return read(ast.parse(text,mode='eval').body)
class Exam(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.stack=[];self.active=[];self.ids=[];self.inputs={};self.results={};self.questions=[];self.solutions=[];self.soltext={};self.rubrics={};self.domains=[];self.sources={};self.rows=[];self.headings=[]
    def handle_starttag(self,t,attrs):
        a=dict(attrs);need(t!='h1','fragment')
        if 'id' in a:
            need(a['id'] in ('form-a','solutions-a') or a['id'].startswith('v17-exam-a-'),'namespaced ID');need(a['id'] not in self.ids,'unique ID');self.ids.append(a['id'])
        if t=='h2':self.headings.append(a.get('id'))
        if 'data-domain' in a:self.domains.append((a['data-domain'],int(a['data-domain-points'])))
        if 'data-points' in a:
            need(t=='li' and any(x=='ol' and 'exercises' in y.get('class','').split() for x,y in self.stack),'scored prompt list')
            domain=next(y['data-domain'] for x,y in reversed(self.stack) if 'data-domain' in y);self.questions.append((a['id'],int(a['data-points']),domain,a['data-chapters'].split()))
        if 'data-solution-for' in a:
            need(any(x=='details' and 'solutions' in y.get('class','').split() for x,y in self.stack),'solution disclosure')
            k=a['data-solution-for'];self.solutions.append(k);self.soltext[k]='';self.rubrics[k]=[];self.active.append((self.soltext,k,len(self.stack)))
        if 'data-rubric-points' in a:
            k=next(y['data-solution-for'] for x,y in reversed(self.stack) if 'data-solution-for' in y);self.rubrics[k].append(int(a['data-rubric-points']))
        if 'data-source' in a:need(a['data-source'] not in self.sources,'source unique');self.sources[a['data-source']]=a['href']
        for attr,d in (('data-input',self.inputs),('data-result',self.results)):
            if attr in a:k=a[attr];need(k not in d,'marker unique');d[k]='';self.active.append((d,k,len(self.stack)))
        if t=='tr' and any(y.get('id')=='v17-exam-a-register' for x,y in self.stack):self.rows.append([])
        if t in ('th','td') and any(y.get('id')=='v17-exam-a-register' for x,y in self.stack):
            row=self.rows[-1];row.append('');self.active.append((row,len(row)-1,len(self.stack)))
        if t not in ('br','hr','img','meta','link','input'):self.stack.append((t,a))
    def handle_data(self,s):
        for d,k,_ in self.active:d[k]+=s
    def handle_endtag(self,t):
        need(self.stack and self.stack[-1][0]==t,'balanced HTML');self.stack.pop();self.active=[x for x in self.active if x[2]<len(self.stack)]
def digest(path):
    data=path.read_bytes();return {'bytes':len(data),'sha256':sha256(data).hexdigest()}
def tax(values):
    need(type(values) is tuple and len(values)==4 and all(type(x) in (int,F) for x in values),'exact tax tuple')
    a,b,d,t=map(F,values);need(a>0 and b>0 and d>0 and 0<=t<a/b,'positive-trade model domain')
    # Solve in quantity using inverse demand minus inverse supply, distinct from the text's seller-price substitution.
    q=(a/b-t)/(1/b+1/d);pc=(a-q)/b;ps=q/d;q0=(a/b)/(1/b+1/d);p0=q0/d
    cs=(a/b-pc)*q/2;surplus_s=ps*q/2;revenue=t*q
    total0=(a/b)*q0/2;loss=total0-cs-surplus_s-revenue
    need(a-b*pc==q==d*ps and pc-ps==t,'both market curves and wedge')
    return p0,q0,pc,ps,q,pc-p0,p0-ps,revenue,loss

def support(values,u,v):
    need(type(values) is tuple and len(values)==5 and all(type(x) in (int,F) for x in values+(u,v)),'exact support primitives')
    p,m1,m0,l,h=map(F,values);u,v=F(u),F(v)
    need(0<p<1 and l<h and all(l<=x<=h for x in (m1,m0,u,v)),'support domain')
    y1=p*m1+(1-p)*u;y0=p*v+(1-p)*m0
    return y1-y0

def completions(scores):
    need(type(scores) is tuple and scores and all(x is None or (type(x) is int and 0<=x<=2) for x in scores),'score domain')
    missing=[i for i,v in enumerate(scores) if v is None];values=[]
    for fill in product(range(3),repeat=len(missing)):
        full=list(scores)
        for i,v in zip(missing,fill):full[i]=v
        values.append(F(sum(full),len(full)))
    return tuple(values)

def fixed_supply(values):
    need(type(values) is tuple and len(values)==4 and all(type(x) in (int,F) for x in values),'exact fixed supply tuple')
    a,b,q,t=map(F,values);need(a>0 and b>0 and q>0 and t>=0,'fixed model domain')
    pc=(a-q)/b;ps=pc-t;need(ps>=0,'seller minimum price')
    return pc,pc,q,pc,ps,q,F(0),t,t*q

def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    before={f:digest(root/f) for f in FILES};review=json.loads((root/FILES[3]).read_text());sources=json.loads((root/FILES[2]).read_text())
    need(set(review['payloads'])==set(FILES[:3]),'three nonself bindings')
    for f,h in review['payloads'].items():need(before[f]==h,'payload binding '+f)
    doc=Exam();doc.feed((root/FILES[0]).read_text());doc.close();need(not doc.stack,'balanced document')
    qids=['v17-exam-a-q'+str(i) for i in range(1,21)];need([q[0] for q in doc.questions]==doc.solutions==qids,'twenty matched solutions')
    need(doc.headings==['form-a','solutions-a'],'required heading anchors');need(doc.domains==[(d,20) for d in DOMAINS],'five mapped domains')
    need(all(q[1]==5 for q in doc.questions) and sum(q[1] for q in doc.questions)==100,'100 point total')
    for domain in DOMAINS:need(sum(q[1] for q in doc.questions if q[2]==domain)==20,'domain20')
    need(all(doc.rubrics[q]==[1]*5 for q in qids),'five additive criteria per solution')
    coverage={c for q in doc.questions for c in q[3]};need(coverage=={'v17-c'+str(i).zfill(2) for i in range(1,13)},'all12 chapter coverage')
    need(set(review['exact_prompt_review'])==set(qids),'full prompt audit');need(review['chapter_coverage']=={q[0]:q[3] for q in doc.questions},'exact coverage record')
    need(doc.sources=={s['id']:s['url'] for s in sources['sources']} and len(doc.sources)==4,'four bounded source routes')
    inputs={k:literal(v) for k,v in doc.inputs.items()};shown={k:literal(v) for k,v in doc.results.items()}
    need(set(inputs)=={'tax','tax-scenarios','supply-transfer-input','identification','restriction','fixed-supply-input','diagnostic-tax','observation-tax'},'all input markers')
    a,b,d,t=inputs['tax'];base=tax(inputs['tax']);low=tax((a,b,d,inputs['tax-scenarios'][0]));high=tax((a,b,d,inputs['tax-scenarios'][1]));transfer=tax(inputs['supply-transfer-input'])
    expected={'tax-base':base[:7],'tax-high':high[2:],'tax-low':low[2:],'supply-transfer':transfer[:7],'response-score':(1,1,1,1,0,4)}
    population=inputs['identification'];lower,upper=population[-2:];bounds=(support(population,lower,upper),support(population,upper,lower));expected['ate-range']=bounds
    umin,vmax=inputs['restriction'];expected['restricted-range']=(support(population,umin,vmax),support(population,upper,lower))
    expected['observation-transfer']=tax((a,b,d,inputs['observation-tax']))[2:];expected['diagnostic-transfer']=tax((a,b,d,inputs['diagnostic-tax']))[2:7]
    expected['fixed-supply']=fixed_supply(inputs['fixed-supply-input'])
    need(len(doc.rows)==9 and [r[0] for r in doc.rows[1:]]==list('ABCDEFGH'),'complete register rows')
    initial=tuple(int(r[1]) for r in doc.rows[1:]);delayed=tuple(None if r[2]=='—' else int(r[2]) for r in doc.rows[1:])
    need(all(0<=v<=2 for v in initial),'initial score domain');im=F(sum(initial),len(initial));obs=tuple(x for x in delayed if x is not None);rm=F(sum(obs),len(obs));full=completions(delayed)
    expected['evidence-means']=(im,rm,min(full),max(full),min(full)-im,max(full)-im)
    need(set(shown)==set(expected),'all numeric answers covered');count=0
    for k,v in expected.items():need(shown[k]==v,'result '+k);count+=len(v)
    need(base[-2:]==(600,60) and high[-2]-base[-2]==360 and high[-1]-base[-1]==180,'policy comparison');count+=4
    need(base[1]*(a/b)/2==2160,'initial total surplus');count+=1
    # Exact market worlds check welfare accounting against lost-trade geometry and linear burden shares.
    market_worlds=0
    for slope in (F(1),F(2),F(3),F(6)):
        for rate in (F(0),F(5),F(10),F(20),F(59)):
            values=tax((a,b,slope,rate));market_worlds+=1
            need(values[-1]==rate*(values[1]-values[4])/2,'welfare identity');need(values[5]+values[6]==rate,'burdens sum to wedge');need(values[5]==rate*slope/(b+slope),'buyer burden comparative static');count+=3
    # Sharpness: full observed group outcomes remain fixed as both unobserved group means vary.
    worlds=0
    for u,v in product(range(10),repeat=2):
        value=support(population,F(u),F(v));need(bounds[0]<=value<=bounds[1],'support world bounds');worlds+=1;count+=1
    for i in range(9):
        lam=F(i,8);u=9*lam;v=9*(1-lam);need(support(population,u,v)==bounds[0]+(bounds[1]-bounds[0])*lam,'full interval construction');count+=1
        u=umin+(upper-umin)*lam;v=vmax*(1-lam);need(support(population,u,v)==1+5*lam,'restricted interval construction');count+=1
    need(support(population,F(6),F(3))==support(population,F(5),F(1))==3,'sufficient not necessary');count+=2
    need(len(full)==9 and tuple(sorted(set(full)))==tuple(F(7+i,8) for i in range(5)),'missing integer grid');count+=6
    need(completions((None,None))==(F(0),F(1,2),F(1),F(1,2),F(1),F(3,2),F(1),F(3,2),F(2)),'all missing');count+=9
    need(fixed_supply((120,2,60,30))[4]==0,'minimum seller price boundary');count+=1
    invalid=0
    bad=[(tax,(120,0,3,10)),(tax,(120,2,0,10)),(tax,(120,2,3,-1)),(tax,(120,2,3,60)),(tax,(120,2,3,True)),(fixed_supply,(120,2,60,31)),(fixed_supply,(120,2,0,10)),(completions,(0,3,None)),(completions,(True,None))]
    for fn,values in bad:
        try:fn(values)
        except ValueError:invalid+=1
        else:raise ValueError('invalid domain accepted')
    for values,u,v in [((0,6,3,0,9),0,0),((F(1,3),10,3,0,9),0,0),(population,10,0)]:
        try:support(values,u,v)
        except ValueError:invalid+=1
        else:raise ValueError('invalid support accepted')
    need(before=={f:digest(root/f) for f in FILES},'read-only runtime')
    summary={'volume':'v17','component':'exam_a','status':'passed','runtime_files':4,'prompts':20,'points':100,'domains':5,'chapter_coverage':12,'rubric_criteria':100,'result_groups':len(shown),'comparisons':count,'market_worlds':market_worlds,'counterfactual_worlds':worlds,'missing_completions':len(full),'invalid_domains':invalid,'scope':'Numeric/structure checks supplement complete author artifact/proof/scoring review; no observed learner or human certification.'}
    json.dumps(summary,allow_nan=False);return summary
if __name__=='__main__':
    import sys
    need(len(sys.argv)<=2,'usage: check_v17_exam_a.py [book-root]');check(sys.argv[1] if len(sys.argv)==2 else None)
