"""V18 Form B: restricted cash, evidence controls and complete institutional repair."""
from pathlib import Path
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from itertools import product
import ast
import json
FILES=('content/assessments/parts/v18-exam-b.html','scripts/check_v18_exam_b.py','content/reviews/v18-exam-b-sources.json','content/reviews/v18-exam-b-author.json')
DOMAINS=('strategy_resources','people_organization','governance_academic','finance_operations','crisis_evidence_integration')
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



def course(version,t=None):
    price,upfront,fees,grant=map(F,version);t=upfront if t is None else F(t)
    require(min(price,upfront,fees,grant,t)>=0 and t<=price,'nonnegative course ledger and bounded upfront payment')
    before=F(22-8-6);remaining=price-t;first=before-t;last=first+fees+grant-remaining
    npv=-t+(fees+grant-remaining)/F(11,10)
    return before,first,remaining,last,npv


def bargaining(lo=5,hi=6):
    lo,hi=F(lo),F(hi);require(0<=lo<=hi,'nonnegative ordered timing bounds')
    t=(lo+hi)/2;return t,hi-t,t-lo,(hi-t)*(t-lo)


def incentives(b,ph=F(4,5),pl=F(3,10),cost=2):
    b,ph,pl,cost=map(F,(b,ph,pl,cost));require(b>=0 and cost>=0 and 0<=pl<ph<=1,'ordered success probabilities and nonnegative contract')
    return ph*b-cost,pl*b,ph*b


def ledger(e=0,borrow=0):
    e,borrow=F(e),F(borrow);require(min(e,borrow)>=0,'nonnegative new funding')
    return (F(14)+e+borrow-8-2,F(86-5),F(88-8),borrow,F(12)+e-5-2)


def flow(capacities,arrival,backlog,days):
    require(capacities and min((*capacities,arrival,backlog,days))>=0,'nonnegative fluid inputs')
    mu=min(map(F,capacities));arrival,backlog,days=map(F,(arrival,backlog,days));remaining=max(F(0),backlog+(arrival-mu)*days)
    return mu,remaining,backlog+arrival*days-remaining


def score_gate(scores):
    require(len(scores)==5 and all(type(x) is int and 0<=x<=20 for x in scores),'five valid domain scores')
    return sum(scores)>=85 and min(scores)>=15


def audit(d):
    count=0
    def eq(a,b,label):
        nonlocal count
        require(a==b,label);count+=1
    def yes(ok,label):
        nonlocal count
        require(ok,label);count+=1
    x={k:numeric(v) for k,v in d.inputs.items()}
    eq(x,{'academic-cash':(22,8,6,2,F(1,10)),'academic-outcomes':(1,1,1,1,1,1,0,0),'academic-hours':(40,8,12,F(1,2),F(1,4),24,32),'incentives':(F(4,5),F(3,10),2,4,3,F(1,4)),'balance':(14,86,88,12,5,8,2,5,6,3,4),'losses':(12,2,F(1,2)),'process':(60,30,45,40,20,90,45),'crisis':(F(1,10),F(1,5),F(3,10),30,7),'execution':(10,8,11,10,12),'scores':(20,18,19,14,19)},'all actual visible inputs')
    versions={r[0]:tuple(numeric(v) for v in r[1:]) for r in d.rows if len(r)==5 and r[0] in ('P','Q')}
    eq(versions,{'P':(12,12,15,6),'Q':(8,8,9,4)},'actual course rows')
    ratings={r[0]:tuple(numeric(v) for v in r[1:]) for r in d.rows if len(r)==3 and r[0] in ('I','J','K')}
    eq(ratings,{'I':((2,1,1),(2,2,2)),'J':((2,2,2),(0,0,1)),'K':((2,1,1),(2,2,1))},'both actual initial rating sheets')
    cls={r[0]:tuple(numeric(v) for v in r[1:]) for r in d.rows if len(r)==3 and r[0] in ('Urgent','Normal')}
    eq(cls,{'Urgent':(8,2),'Normal':(6,34)},'actual complete confusion matrix')
    mix={r[0]:tuple(numeric(v) for v in r[1:]) for r in d.rows if len(r)==5 and r[0] in ('Before','After')}
    eq(mix,{'Before':(10,2,30,6),'After':(30,2,10,6)},'actual observational full mix')
    t,g1,g2,prod=bargaining();p=course(versions['P']);q=course(versions['Q'],t);u=course(versions['Q']);ih,il,pay=incentives(F(9,2));bh,bl,bpay=incentives(3)
    T,fixed,research,core,feedback,n0,nprop=x['academic-hours'];per=core+feedback;maxn=int((T-fixed-research)/per);outcomes=x['academic-outcomes'];rate=sum(outcomes)/F(len(outcomes))
    no=ledger();br=ledger(borrow=3);fund=ledger(e=1);miss,false,human=x['losses'];tp,fn=cls['Urgent'];fp,tn=cls['Normal'];N=tp+fn+fp+tn;accuracy=(tp+tn)/N;auto=fn*miss+fp*false;flag=fn*miss+(tp+fp)*human;allhuman=N*human
    ai,rv,rel,arr,back,newi,newr=x['process'];baseline=flow((ai,rv,rel),arr,back,3);server=flow((newi,rv,rel),arr,back,3);staff=flow((ai,newr,rel),arr,back,3)
    means={k:(r[0]*r[1]+r[2]*r[3])/(r[0]+r[2]) for k,r in mix.items()};w=mix['Before'][0]/(mix['Before'][0]+mix['Before'][2]);standard=w*mix['After'][1]+(1-w)*mix['After'][3]
    low,high,newhigh,adverse,pause=x['crisis'];total,on,actual,base,ceiling=x['execution'];scores=tuple(map(int,x['scores']));revised=(*scores[:3],15,scores[4])
    want={'q02':(q[0],q[1],q[2],q[3],2-p[1],2-u[1]),'q03':(p[4],q[4],F(-1,11)),'q04':((5,6),t,(g1,g2),prod,q[2]),'q05':((4,5),(ih,il),ih-il,pay),'q06':((1-x['incentives'][5])*3,bh,bl),'q07':tuple(sum(ratings[k][1]) for k in ('I','J','K')),'q09':(3,3//2+1,3,2,2,2),'q11':(maxn,T-fixed-per*maxn,T-fixed-per*n0,T-fixed-per*nprop,fixed+per*nprop+research),'q12':(rate,1,1-rate),'q13':((*no[:3],no[4]),(br[0],br[3],br[4]),1,(*fund[:3],fund[4])),'q14':(accuracy,auto,flag,allhuman,tp+fp),'q15':(baseline[0],baseline[1],server[0],server[1],staff[0],staff[1],back/(staff[0]-arr),staff[2],flow((ai,newr,rel),arr,back,6)[2]),'q16':(means['Before'],means['After'],means['After']-means['Before'],standard,standard-means['Before']),'q17':((adverse*high,pause),(adverse*newhigh,pause),pause/adverse),'q18':(on/total,actual-base,ceiling-actual),'q19':((sum(scores),sum(revised)),scores[3],revised[3])}
    eq(set(want),set(d.results),'all result groups')
    for k,v in want.items():eq(numeric(d.results[k]),v,'displayed '+k)
    eq(q[4],(50-t)/11,'general deferred-payment NPV')
    eq(q[3],13,'full remaining invoice prevents fictitious surplus')
    yes(p[4]>q[4] and p[1]<2<=q[1],'higher value but unfunded alternative')
    timing_worlds=0
    for i in range(9):
        payment=F(5)+F(i,8);c=course(versions['Q'],payment);timing_worlds+=1
        yes(c[1]>=2 and payment>=5,'all feasible timing witnesses')
        eq((6-payment)*(payment-5),F(1,4)-(payment-F(11,2))**2,'global timing completed square')
        yes((6-payment)*(payment-5)<=prod,'optimum domination')
        eq(c[4],(50-payment)/11,'all timing NPV identity')
    for payment in (F(0),F(4),F(5),F(6),F(7),F(8)):
        c=course(versions['Q'],payment);eq(payment>=5 and c[1]>=2,5<=payment<=6,'full timing feasibility iff interval')
    incentive_worlds=0
    for bonus in (F(0),F(3),F(4),F(9,2),F(5),F(6)):
        h,l,cost=incentives(bonus);incentive_worlds+=1
        eq(h-l,bonus/2-2,'global utility difference')
        eq(h>=l and cost<=4,4<=bonus<=5,'weak incentive/budget intersection')
        eq(h>l and cost<=4,4<bonus<=5,'strict incentive/budget intersection')
    eq(incentives(4)[0],incentives(4)[1],'real lower-bound indifference')
    yes(ih>il>0,'repaired truthful participation and Fzero loses')
    eq(tuple(sum(ratings[k][0]) for k in ('I','J','K')),(4,6,4),'retained conflicted scores')
    eq(tuple(k for k in ('I','J','K') if ratings[k][1][:2]==(2,2)),('I','K'),'announced selection gate')
    yes(2>F(3,2) and 3>=3,'initial eligible vote passes both gates')
    yes(2>F(3,2) and not 2>=3,'later majority cannot cure absent quorum')
    yes(T-fixed-per*maxn>=research and T-fixed-per*(maxn+1)<research,'integer maximum attainment/exclusion')
    eq(per*nprop-core*nprop,8,'omitted feedback hours')
    for e in (F(0),F(1,2),F(1),F(2),F(5)):
        c,n,dep,borr,eqty=ledger(e=e);eq(c+n,dep+borr+eqty,'equity issue balance identity');eq(c>=5 and eqty>=6,e>=1,'both floors global equity threshold')
    for borrow in (0,1,3,10):
        c,n,dep,borr,eqty=ledger(borrow=borrow);eq(c+n,dep+borr+eqty,'borrowing balance identity');eq(eqty,5,'borrowing never repairs equity')
    eq((14+1,14+1-8,14+1-8-2),(15,7,5),'all cash stages protected')
    eq((12+1,12+1-5,12+1-5-2),(13,8,6),'all equity stages protected')
    eq((tp+fn,fp+tn,N),(10,40,50),'original class denominators')
    yes(allhuman<flag<auto,'loss ranking')
    eq((fn,fn,0),(2,2,0),'only AllHuman test miss-gate pass')
    for days in (0,1,3,4,5,6):
        mu,remaining,done=flow((ai,newr,rel),arr,back,days)
        eq(remaining+done,back+arr*days,'whole-flow conservation')
        yes(done<=mu*days,'never above capacity')
    eq(flow((60,40,45),40,20,3)[1],20,'equal capacity cannot drain backlog')
    eq(flow((60,0,45),40,20,3),(0,140,0),'zero review stops all completed output')
    eq(tuple(mix['After'][i]-mix['Before'][i] for i in (1,3)),(0,0),'unchanged stratum means')
    for simple_share in (F(0),F(1,4),F(1,2),F(3,4),F(1)):
        common=simple_share*2+(1-simple_share)*6;eq(common,6-4*simple_share,'composition affine identity')
    for upper in (low,high,pause/adverse,newhigh,F(1)):
        eq(adverse*upper<=pause,upper<=F(7,30),'crisis global threshold and tie')
    eq((score_gate(scores),score_gate(revised)),(False,True),'score numeric gates only')
    eq(score_gate((17,17,17,17,17)),True,'exact overall threshold')
    eq(score_gate((16,17,17,17,17)),False,'overall one below')
    invalid=[lambda:course(versions['Q'],9),lambda:course(versions['Q'],-1),lambda:bargaining(6,5),lambda:incentives(-1),lambda:incentives(4,ph=F(1,5),pl=F(3,10)),lambda:incentives(4,cost=-1),lambda:ledger(e=-1),lambda:ledger(borrow=-1),lambda:flow((),40,20,3),lambda:flow((60,-1,45),40,20,3),lambda:flow((60,30,45),40,20,-1),lambda:score_gate((20,20)),lambda:score_gate((21,20,20,20,20))]
    for fn in invalid:
        try:fn()
        except ValueError:pass
        else:raise ValueError('invalid domain accepted')
    return count,len(invalid),len(want),timing_worlds,incentive_worlds


def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    raw={f:(root/f).read_bytes() for f in FILES};review=strict_json(raw[FILES[3]]);sources=strict_json(raw[FILES[2]])
    require(set(review['payloads'])==set(FILES[:3]),'three nonself bindings')
    for f,v in review['payloads'].items():require(v=={'bytes':len(raw[f]),'sha256':sha256(raw[f]).hexdigest()},'frozen payload changed '+f)
    d=Manuscript();d.feed(raw[FILES[0]].decode());require(not d.stack and len(d.ids)==len(set(d.ids)),'balanced unique fragment')
    expected={f'v18-exam-b-q{i:02d}' for i in range(1,21)}
    require(set(d.prompts)==set(d.solutions)==set(d.points)==set(d.rubrics)==set(review['exact_prompt_review'])==expected,'twenty exact scored/solved pairs')
    require(all(v==5 for v in d.points.values()) and sum(d.points.values())==100,'hundred point form')
    require(all(v==[1]*5 for v in d.rubrics.values()),'five additive distinct point criteria')
    require(set(d.domain.values())==set(DOMAINS),'five explicit domains')
    for domain in DOMAINS:require(sum(d.points[k] for k in expected if d.domain[k]==domain)==20,'twenty per domain')
    require({c for cs in d.chapters.values() for c in cs}=={f'v18-c{i:02d}' for i in range(1,13)},'all twelve chapter outcomes mapped')
    require({'form-b','solutions-b'}<=set(d.ids) and all(i in ('form-b','solutions-b') or i.startswith('v18-exam-b-') for i in d.ids),'specified stable IDs')
    for k,v in review['exact_prompt_review'].items():
        require(v['prompt_sha256']==sha256(d.prompts[k].encode()).hexdigest() and v['solution_sha256']==sha256(d.solutions[k].encode()).hexdigest(),'exact reviewed pair changed')
        require(v['chapters']==d.chapters[k] and v['domain']==d.domain[k],'exact coverage mapping')
    routes={'v18-exam-b-opm':'https://www.opm.gov/policy-data-oversight/assessment-and-selection/structured-interviews/','v18-exam-b-bis':'https://www.bis.org/publications/fsi-summary-corporate-governance-principles-banks-executive-summary','v18-exam-b-nist':'https://airc.nist.gov/airmf-resources/playbook/measure/'}
    require(d.sources==routes=={s['id']:s['url'] for s in sources['sources']},'actual scoped source links')
    require(all(s['original_inspector']=='integrated_case_peer' for s in sources['sources']),'preserved original source inspector')
    comparisons,invalid,groups,timing,effort=audit(d)
    return {'volume':'v18','component':'exam_b','status':'passed','runtime_files':4,'points':100,'domains':5,'points_per_domain':20,'prompts':20,'solutions':20,'additive_rubrics':20,'chapter_outcomes':12,'numeric_groups':groups,'comparisons':comparisons,'invalid_domains':invalid,'timing_worlds':timing,'incentive_worlds':effort,'source_routes':3,'scope':'Full original institutional audit/repair evidence packets and exact solutions/rubrics manually read; written/synthetic gates do not certify actual leadership or independent human evaluation.'}


if __name__=='__main__':
    check()
