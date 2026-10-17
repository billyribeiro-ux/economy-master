"""C06 exact author verification. Qualitative scoring is separately read, not automated."""
from pathlib import Path
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
import ast
import json
import re

FILES=('production/v17-c06-working.html','production/check_v17_c06_working.py','production/v17-c06-sources-working.json','production/v17-c06-author-review-working.json')
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


def pv(flows,rate):
    require(len(flows)>0 and rate>-1,'positive discount factors and nonempty flows')
    return sum((F(c)/(1+rate)**t for t,c in enumerate(flows)),F(0))


def grade(scores,maxima):
    require(len(scores)==len(maxima)>0 and all(m>=0 for m in maxima) and sum(maxima)>0,'rubric maxima')
    require(all(0<=s<=m for s,m in zip(scores,maxima)),'criterion range')
    return 100*sum(scores,F(0))/sum(maxima)


def calibration(a,b):
    require(len(a)==len(b)>0,'paired nonempty ratings')
    gaps=[x-y for x,y in zip(a,b)]
    return (sum(gaps,F(0))/len(gaps),sum((abs(g) for g in gaps),F(0))/len(gaps),F(sum(g==0 for g in gaps),len(gaps)))


def did(values):
    require(len(values)==4 and all(0<=v<=100 for v in values),'four percentage rates')
    a,b,c,d=values
    return b-a,d-c,(b-a)-(d-c)


def effects(contrast,low,high):
    require(low<=high,'ordered trend support')
    return contrast-high,contrast-low


def missing(total,observed,n,lo,hi):
    require(type(observed) is int and type(n) is int and 0<=observed<=n and n>0,'roster domain')
    require(lo<=hi and lo*observed<=total<=hi*observed,'score support')
    return ((total+(n-observed)*lo)/n,(total+(n-observed)*hi)/n)


def audit(d):
    x={k:numeric(v) for k,v in d.inputs.items()};count=0
    def eq(a,b,label):
        nonlocal count
        require(a==b,label);count+=1
    expected={'project':(64,50,50),'rate':F(1,4),'cash-reserve':(90,30),'loan':(4,5),'fresh-project':(54,36,36,F(1,5),80,30,4,F(24,5)),'fresh-did':(50,58,45,49,-1,2),'rater-a':(19,12,16),'rater-b':(17,12,18),'domains':(100,95,90,65)}
    eq(x,expected,'all exact supplied input groups')
    c,a,b=x['project'];r=x['rate'];cash,res=x['cash-reserve'];loan,repay=x['loan']
    p1=a/(1+r);p2=b/(1+r)**2;npv=pv((-c,a,b),r);equity=(-c+loan,a-repay,b)
    fmax=tuple(numeric(row[1]) for row in d.rows if row[0].startswith(('F1:','F2:','F3:','F4:','F5:','F6:')))
    emax=tuple(numeric(row[1]) for row in d.rows if row[0].startswith(('E1:','E2:','E3:','E4:','E5:')))
    eq(fmax,(2,4,4,4,4,2),'actual finance rubric');eq(emax,(4,4,6,2,4),'actual evidence rubric')
    eq((sum(fmax),sum(emax),4+4+6+2+4),(20,20,20),'all three task totals')
    # These vectors encode the full manual evidence adjudications, not NLP scoring.
    ns=(2,4,3,4,4,2);ks=(0,0,2,2,0,0);ps=(4,4,4,0,0)
    fc,f1,f2,fr,fcash,fres,fl,frepay=x['fresh-project'];fnpv=pv((-fc,f1,f2),fr);feq=(-fc+fl,f1-frepay,f2)
    observed={row[0]:tuple(numeric(v) for v in row[1:]) for row in d.rows if row[0] in ('T','C')}
    eq(set(observed),{'T','C'},'actual raw rate table')
    contrasts=did(observed['T']+observed['C']);D=contrasts[-1]
    fresh=did(x['fresh-did'][:4]);bound=effects(fresh[-1],*x['fresh-did'][4:])
    initial_world=(observed['T'][0]+contrasts[1],D,F(0));other_world=(observed['T'][1],F(0),D)
    miss=missing(F(8*9),8,10,F(0),F(10))
    want={'project-value':(p1,p2,npv),'equity':equity,'finance-check':(cash-c,cash+loan-c,pv(equity,r),pv((loan,-repay),r)),'n-score':ns,'n-total':sum(ns),'k-score':ks,'k-total':sum(ks),'fresh-values':(f1/(1+fr),f2/(1+fr)**2,fnpv,fcash-fc,fcash+fl-fc)+feq+(pv(feq,fr),),'did-values':contrasts,'worlds':initial_world+other_world,'p-score':ps,'p-total':sum(ps),'fresh-did-values':fresh+bound,'e1':(sum(ns),)+calibration(x['rater-a'],x['rater-b']),'e2':(2,3,5,7),'e3':(F(44)/(1+F(1,10)),pv((F(-36),F(44)),F(1,10)),45-36),'e5-score':sum(x['domains'])/4,'e5-bound':effects(F(6),F(-2),F(1)),'e6':did((60,63,50,55)),'e7':miss+tuple(v-7 for v in miss),'e8':(pv((F(-40),F(48)),F(1,5)),pv((F(-40),F(47)),F(1,5))),'retention':(F(90)/(1+F(1,4)),pv((F(-72),F(90)),F(1,4)),100-72)}
    eq(set(want),set(d.results),'every result group')
    for k,v in want.items():eq(numeric(d.results[k]),v,'actual result '+k)
    eq(tuple(grade(s,m) for s,m in ((ns,fmax),(ks,fmax),(ps,emax))), (F(95),F(20),F(60)),'score ranges and percentages')
    eq(sum((4,4,6,2,4)),20,'e4 full score')
    eq((sum(ns)-2,F((sum(ns)-2)+sum(ns),2)),(17,18),'initial rater and inappropriate average')
    eq((ns[1]+ns[2],2+3),(7,5),'N versus exponent-error subtotal')
    eq((-c+p1+30,-c+loan+(a-repay)/(1+r)+30),(6,6),'N carried wrong values consistent')
    eq((F(30)*(1+r)**2,F(32)*(1+r)**2),(F(375,8),50),'N inverse compounding check')
    eq((a+b-c,cash-c),(36,26),'K undiscounted arithmetic and immediate account')
    eq(50/(1+r)+50/(1+r)-64,16,'e2 wrong-denominator arithmetic')
    eq((fnpv,pv((fl,-frepay),fr),fcash+fl-fc>=fres,fcash+fl-fc>=31),(1,0,True,False),'fresh reserve alternative')
    eq(grade(x['domains'],(100,100,100,100))>=85 and min(x['domains'])>=75,False,'domain gate blocks high average')
    eq((F(12,20)*100,F(20,20)*100),(60,100),'assisted/independent status arithmetic')
    # Both original counterfactual worlds and fresh sensitivity endpoints reconstruct observations.
    for untreated,tau,gap in (initial_world,other_world):
        eq(untreated+tau,observed['T'][1],'original world post outcome')
        eq((untreated-observed['T'][0])-contrasts[1],gap,'original world trend gap')
        eq(tau+gap,D,'original identity')
    for gap in (F(-1),F(0),F(1),F(2)):
        untreated=F(50)+fresh[1]+gap;tau=F(58)-untreated
        eq(tau,fresh[-1]-gap,'fresh direct counterfactual calculation')
        require(0<=untreated<=100 and bound[0]<=tau<=bound[1],'fresh support');count+=1
    eq((50+4+2,50+4-1),(56,53),'fresh endpoint worlds')
    # Boundary/alternative arithmetic for the stated general claims.
    for rate in (F(-1,2),F(0),F(1,4),F(1)):
        financing=(F(4),-4*(1+rate),F(0));flows=(-c,a,b)
        eq(pv(tuple(v+w for v,w in zip(flows,financing)),rate),pv(flows,rate)+pv(financing,rate),'PV linearity')
        eq(pv(financing,rate),0,'matched financing neutral')
    for receipt in (F(47),F(48),F(49)):
        eq(pv((F(-40),receipt),F(1,5)),(receipt-48)*F(5,6),'strict-positive boundary')
    eq(calibration((0,2),(2,0)),(0,2,0),'zero mean but disagreement')
    eq(calibration((1,2),(1,2)),(0,0,1),'perfect sample agreement')
    eq(effects(F(4),F(0),F(0)),(4,4),'zero trend gap collapse')
    eq(effects(F(4),F(-1),F(6)),(-2,5),'wider support includes negative effect')
    eq(missing(F(72),8,8,F(0),F(10)),(9,9),'no missing outcomes')
    eq(missing(F(0),0,10,F(0),F(10)),(0,10),'all missing outcomes')
    completions=[(F(72)+a+b)/10 for a in (0,5,10) for b in (0,5,10)]
    eq((min(completions),max(completions)),miss,'attainable score bounds')
    invalid=[lambda:pv((1,),F(-1)),lambda:pv((),F(0)),lambda:grade((1,),(0,)),lambda:grade((3,),(2,)),lambda:grade((-1,),(2,)),lambda:calibration((),()),lambda:calibration((1,),(1,2)),lambda:did((0,101,0,0)),lambda:did((0,0,0)),lambda:effects(0,2,1),lambda:missing(F(72),11,10,F(0),F(10)),lambda:missing(F(81),8,10,F(0),F(10))]
    for fn in invalid:
        try:fn()
        except ValueError:pass
        else:raise ValueError('invalid domain accepted')
    return count,len(invalid),len(want)


def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    raw={f:(root/f).read_bytes() for f in FILES};review=strict_json(raw[FILES[3]]);sources=strict_json(raw[FILES[2]])
    require(set(review['payloads'])==set(FILES[:3]),'three nonself bindings')
    for f,v in review['payloads'].items():require(v=={'bytes':len(raw[f]),'sha256':sha256(raw[f]).hexdigest()},'changed payload '+f)
    d=BaseManuscript();d.feed(raw[FILES[0]].decode());require(not d.stack and len(set(d.ids))==len(d.ids),'balanced unique fragment')
    ids={f'v17-c06-e{i}' for i in range(1,9)}
    require(set(d.prompts)==set(d.solutions)==set(review['exact_prompt_review'])==ids,'eight actual prompts and full paired solutions')
    require(d.worked==['v17-c06-case1','v17-c06-case2'],'two worked grading packets')
    for k in ids:
        v=review['exact_prompt_review'][k]
        require(v['prompt_sha256']==sha256(d.prompts[k].encode()).hexdigest() and v['solution_sha256']==sha256(d.solutions[k].encode()).hexdigest(),'reviewed exact pair changed')
    routes={'v17-c06-cmu-rubrics':'https://www.cmu.edu/teaching/designteach/teach/rubrics.html','v17-c06-cornell-rubrics':'https://teaching.cornell.edu/teaching-resources/assessing-student-learning/using-rubrics','v17-c06-cmu-feedback':'https://www.cmu.edu/teaching/designteach/inclusiveexcellence/gradingandfeedback/index.html'}
    require(routes==d.sources=={s['id']:s['url'] for s in sources['sources']},'actual cited primary routes')
    require({a for a in d.links if not a.startswith('https://')}=={'v17-c05.html','v01-c05.html','v12-c07.html#did-target'},'prerequisite/disciplinary routes')
    comparisons,invalid,groups=audit(d)
    return {'chapter':'v17-c06','status':'passed','runtime_files':4,'worked_artifacts':2,'prompts':8,'solutions':8,'numeric_groups':groups,'comparisons':comparisons,'invalid_domains':invalid,'source_routes':3,'scope':'Full original response grading, feedback, repair, reassessment and qualitative evidence judgments separately read. No actual student achievement, grading reliability or external certification claimed.'}


if __name__=='__main__':
    check()
