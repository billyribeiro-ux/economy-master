"""V17 Form B: visible raw archives, dated prices, exact grading and evidence gates."""
from pathlib import Path
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from itertools import product
import ast
import json
FILES=('content/assessments/parts/v17-exam-b.html','scripts/check_v17_exam_b.py','content/reviews/v17-exam-b-sources.json','content/reviews/v17-exam-b-author.json')
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


def price(face,years,yield_rate):
    require(type(face) in (int,F) and type(yield_rate) in (int,F),'exact monetary primitives')
    require(face>0 and type(years) is int and years>=0 and yield_rate>-1,'positive face, whole remaining years, yield above minus one')
    return F(face)/(1+F(yield_rate))**years


def holding(initial,final):
    require(initial>0 and final>=0,'positive investment and nonnegative proceeds')
    return (F(final)-initial)/initial


def rate(success,total):
    require(type(success) is int and type(total) is int and total>0 and 0<=success<=total,'binary count domain')
    return F(success,total)


def standardized(high,low,w):
    require(0<=high<=1 and 0<=low<=1 and 0<=w<=1,'rate and common share domain')
    return w*high+(1-w)*low


def bound(success,observed,total):
    require(type(observed) is int and type(total) is int and 0<=observed<=total,'observed roster domain')
    rate(success,total);require(success<=observed,'successes observed')
    return F(success,total),F(success+total-observed,total)


def numeric_gate(scores,overall,minimum):
    require(len(scores)==5 and all(type(v) is int and 0<=v<=20 for v in scores),'five domain scores')
    return sum(scores)>=overall and min(scores)>=minimum


def audit(d):
    count=0
    def eq(a,b,label):
        nonlocal count
        require(a==b,label);count+=1
    x={k:numeric(v) for k,v in d.inputs.items()}
    eq(x,{'overall-gate':85,'domain-gate':15,'bond':(144,2,F(1,5)),'later-yield-percent':10,'q3-yield-percent':60,'q10-face':121,'q10-purchase-yield-percent':10,'q10-sale-yield-percent':25,'q12-purchase':90,'q12-face':100,'q12-sale-yield-percent':25,'candidate-j':(19,18,17,16,15),'candidate-k':(18,19,18,19,14)},'all actual input markers')
    face,years,y0=x['bond'];p0=price(face,int(years),y0);p1=price(face,int(years)-1,x['later-yield-percent']/100);gain=p1-p0;h=holding(p0,p1)
    threshold=face/p0-1;p60=price(face,1,x['q3-yield-percent']/100)
    archive={};learn=[]
    for row in d.rows:
        if len(row)==4 and row[0] in ('New','Legacy'):
            key=(row[0],row[1]);require(key not in archive,'unique archive row');archive[key]=tuple(map(int,row[2:]))
        if len(row)==4 and row[0] in tuple('ABCDEF'):
            learn.append((row[0],int(row[1]),int(row[2]),None if row[3]=='Missing' else int(row[3])))
    eq(archive,{('New','High'):(9,10),('New','Low'):(27,90),('Legacy','High'):(72,90),('Legacy','Low'):(2,10)},'actual full repayment archive')
    rh,rl,lh,ll=(rate(*archive[k]) for k in (('New','High'),('New','Low'),('Legacy','High'),('Legacy','Low')))
    nr=rate(archive[('New','High')][0]+archive[('New','Low')][0],archive[('New','High')][1]+archive[('New','Low')][1]);lr=rate(archive[('Legacy','High')][0]+archive[('Legacy','Low')][0],archive[('Legacy','High')][1]+archive[('Legacy','Low')][1])
    sn=standardized(rh,rl,F(1,2));sl=standardized(lh,ll,F(1,2))
    eq(learn,[('A',0,1,1),('B',1,1,1),('C',0,1,None),('D',1,1,0),('E',0,1,1),('F',0,1,None)],'full actual teaching roster')
    initial=rate(sum(v[1] for v in learn),len(learn));assist=rate(sum(v[2] for v in learn),len(learn));responders=[v[3] for v in learn if v[3] is not None];response=rate(sum(responders),len(responders));lb=bound(sum(responders),len(responders),len(learn));change=tuple(v-initial for v in lb)
    fp0=price(x['q10-face'],2,x['q10-purchase-yield-percent']/100);fp1=price(x['q10-face'],1,x['q10-sale-yield-percent']/100)
    diag=price(x['q12-face'],1,x['q12-sale-yield-percent']/100)
    grades=((1,0,0,0,0),(1,1,1,1,1),(1,1,0,1,1));totals=tuple(sum(g) for g in grades)
    missing=5;states=[]
    for u in range(missing+1):
        newrate=rate(36+u,100);std=standardized(rh,rate(27+u,90),F(1,2));states.append((newrate,newrate-lr,std,std-sl))
    ranges=tuple((min(row[i] for row in states),max(row[i] for row in states)) for i in range(4))
    sj=tuple(int(v) for v in x['candidate-j']);sk=tuple(int(v) for v in x['candidate-k'])
    want={'q1':(price(110,1,F(1,10)),holding(100,110)),'q2':(p0,p1,gain,h),'q3':(threshold,p60,holding(p0,p60)),'q4':(nr,lr,nr-lr,rh,lh,rl,ll,sn,sl,sn-sl),'q5':(4*2,4*2,4*4),'q6':(10,30,20,40,sum((10,30,20,40))),'q7':(4*25,4*25-90,10,20,20,25,15),'q8':(standardized(rh,rl,F(4,5)),standardized(lh,ll,F(4,5)),sn-sl),'q9':(*grades,totals),'q10':(fp0,fp1,holding(fp0,fp1)),'q11':(initial,assist,response,*lb,*change),'q12':(diag,holding(x['q12-purchase'],diag)),'q13':(4,8,8,6,4,sum((4,8,8,6,4))),'q16':ranges,'q18':(3,3,4,sum((3,3,4))),'q20':(sum(sj),min(sj),sum(sk),min(sk))}
    eq(set(d.results),set(want),'all actual visible result groups')
    for k,v in want.items():eq(numeric(d.results[k]),v,'displayed '+k)
    eq(holding(p0,face),F(11,25),'two-year total maturity return')
    eq((1+y0)**2-1,holding(p0,face),'compound annual maturity relation')
    eq(holding(p0,price(face,1,y0)),y0,'unchanged yield special case')
    eq((h*100,gain),(F(340,11),F(340,11)),'percentage numeric matches gain only because original investment100')
    eq(holding(F(200),2*p1),h,'scaled investment same return distinct currency gain')
    eq(gain/p1,F(17,72),'N actual erroneous final-price ratio')
    eq(holding(80,diag),0,'q12 changed original investment probe')
    eq((diag-x['q12-purchase'])/diag,F(-1,8),'q12 wrong final-price denominator')
    for later in (F(-1,2),F(0),F(1,10),y0,threshold,F(3,5),F(1)):
        ret=holding(p0,price(face,1,later))
        eq(ret,(threshold-later)/(1+later),'exact global holding-return sign factorization')
        eq((ret>0)-(ret<0),(threshold>later)-(threshold<later),'zero threshold and signs')
    eq(price(face,0,F(-1,2)),face,'maturity payment has no discount years')
    # Exact affine coefficient identities prove the common-weight result for all admissible shares.
    eq((rl-ll,(rh-rl)-(lh-ll)),(F(1,10),0),'common-weight difference constant coefficients')
    eq((rh-rl,lh-ll),(F(3,5),F(3,5)),'both mixture slopes')
    for w in (F(0),F(1,10),F(1,2),F(4,5),F(9,10),F(1)):
        eq(standardized(rh,rl,w)-standardized(lh,ll,w),F(1,10),'common-weight endpoints and alternatives')
    wn=F(archive[('New','High')][1],100);wl=F(archive[('Legacy','High')][1],100)
    eq((wn,wl),(F(1,10),F(9,10)),'actual stratum shares')
    eq(standardized(rh,rl,wn)-standardized(lh,ll,wl),nr-lr,'different weights reconstruct raw gap')
    for wnew,wold in ((F(0),F(1)),(F(1),F(0)),(F(1,3),F(1,2)),(F(1,2),F(1,2))):
        gap=standardized(rh,rl,wnew)-standardized(lh,ll,wold)
        eq(gap,F(1,10)+F(3,5)*(wnew-wold),'general composition identity')
        eq((gap>0)-(gap<0),(wnew-wold>F(-1,6))-(wnew-wold<F(-1,6)),'aggregate sign threshold including equality')
    # Enumerate all underlying missing schedules, rather than assuming continuous intermediate rates.
    worlds={(F(3+sum(bits),6),F(3+sum(bits),6)-initial) for bits in product((0,1),repeat=2)}
    eq(tuple(sorted(v[0] for v in worlds)),(F(1,2),F(2,3),F(5,6)),'all delayed-roster compatible rates')
    eq((min(v[1] for v in worlds),max(v[1] for v in worlds)),change,'attained descriptive change extrema')
    repayments={(F(36+sum(bits),100),standardized(rh,F(27+sum(bits),90),F(1,2))) for bits in product((0,1),repeat=5)}
    eq(len(repayments),6,'32 binary schedules yield six count-compatible points')
    eq(set((s[0],s[2]) for s in states),repayments,'exact Release2 finite law')
    eq((27+58+5,10+27+58+5),(90,100),'Release2 roster conservation')
    require(all(s[1]<0 and s[3]>0 for s in states),'both signs robust to supplied missingness');count+=1
    eq(bound(3,6,6),(F(1,2),F(1,2)),'fully observed roster bounds collapse')
    eq(bound(0,0,6),(0,1),'entirely missing roster bounds')
    eq((sum((10,20,20,25,15)),sum((4,8,8,6,4)),sum((3,3,4))),(90,30,10),'three complete live plans feasible')
    eq(numeric_gate(sj,int(x['overall-gate']),int(x['domain-gate'])),True,'J numeric gate only')
    eq(numeric_gate(sk,int(x['overall-gate']),int(x['domain-gate'])),False,'K domain failure despite88')
    eq(numeric_gate((17,17,17,17,17),85,15),True,'overall threshold equality')
    eq(numeric_gate((16,17,17,17,17),85,15),False,'one below overall threshold')
    eq(totals[2]-2,2,'N fair criterion repair changes2to4')
    # The numerical gate is deliberately not an implementation of human certification.
    invalid=[lambda:price(0,2,F(1,10)),lambda:price(100,-1,F(1,10)),lambda:price(100,F(1,2),F(1,10)),lambda:price(100,1,F(-1)),lambda:price(100,1,F(-2)),lambda:holding(0,100),lambda:holding(100,-1),lambda:rate(3,2),lambda:rate(0,0),lambda:rate(-1,5),lambda:standardized(rh,rl,F(11,10)),lambda:bound(3,2,6),lambda:bound(1,7,6),lambda:numeric_gate((21,20,20,20,20),85,15),lambda:numeric_gate((20,20),85,15)]
    for fn in invalid:
        try:fn()
        except ValueError:pass
        else:raise ValueError('invalid domain accepted')
    return count,len(invalid),len(want)


def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    raw={f:(root/f).read_bytes() for f in FILES};review=strict_json(raw[FILES[3]]);sources=strict_json(raw[FILES[2]])
    require(set(review['payloads'])==set(FILES[:3]),'three nonself bindings')
    for f,v in review['payloads'].items():require(v=={'bytes':len(raw[f]),'sha256':sha256(raw[f]).hexdigest()},'frozen payload changed '+f)
    d=Manuscript();d.feed(raw[FILES[0]].decode());require(not d.stack and len(d.ids)==len(set(d.ids)),'balanced unique fragment')
    expected={f'v17-exam-b-q{i:02d}' for i in range(1,21)}
    require(set(d.prompts)==set(d.solutions)==set(d.points)==set(d.rubrics)==set(review['exact_prompt_review'])==expected,'twenty exact scored/solved pairs')
    require(all(v==5 for v in d.points.values()) and sum(d.points.values())==100,'hundred point form')
    require(all(v==[1]*5 for v in d.rubrics.values()),'five additive distinct point criteria')
    require(set(d.domain.values())==set(DOMAINS),'five explicit domains')
    for domain in DOMAINS:require(sum(d.points[k] for k in expected if d.domain[k]==domain)==20,'twenty per domain')
    require({c for cs in d.chapters.values() for c in cs}=={f'v17-c{i:02d}' for i in range(1,13)},'all twelve chapter outcomes mapped')
    require({'form-b','solutions-b'}<=set(d.ids) and all(i in ('form-b','solutions-b') or i.startswith('v17-exam-b-') for i in d.ids),'specified stable IDs')
    for k,v in review['exact_prompt_review'].items():
        require(v['prompt_sha256']==sha256(d.prompts[k].encode()).hexdigest() and v['solution_sha256']==sha256(d.solutions[k].encode()).hexdigest(),'exact reviewed pair changed')
        require(v['chapters']==d.chapters[k] and v['domain']==d.domain[k],'exact coverage mapping')
    routes={'v17-exam-b-cmu-alignment':'https://www.cmu.edu/teaching/assessment/basics/alignment.html','v17-exam-b-cmu-rubrics':'https://www.cmu.edu/teaching/designteach/teach/rubrics.html'}
    require(d.sources==routes=={s['id']:s['url'] for s in sources['sources']},'actual scoped source links')
    comparisons,invalid,groups=audit(d)
    return {'volume':'v17','component':'exam_b','status':'passed','runtime_files':4,'points':100,'domains':5,'points_per_domain':20,'prompts':20,'solutions':20,'additive_rubrics':20,'chapter_outcomes':12,'numeric_groups':groups,'comparisons':comparisons,'invalid_domains':invalid,'missing_repayment_schedules':32,'missing_learner_schedules':4,'source_routes':2,'scope':'Full original audit/repair artifacts and exact solutions manually read; numerical gates do not certify actual teaching or independent human evaluation.'}


if __name__=='__main__':
    check()
