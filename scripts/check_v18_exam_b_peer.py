"""Independent V18 Form B peer: dated ledger, full records and action enumeration."""
from pathlib import Path
from fractions import Fraction as F
from html.parser import HTMLParser
from itertools import combinations,product
import ast,hashlib,json,re,sys
AUTHOR=('content/assessments/parts/v18-exam-b.html','scripts/check_v18_exam_b.py','content/reviews/v18-exam-b-sources.json','content/reviews/v18-exam-b-author.json')
SELF='scripts/check_v18_exam_b_peer.py';REVIEW='content/reviews/v18-exam-b-peer.json';FILES=AUTHOR+(SELF,REVIEW)
def need(ok,msg):
    if not ok:raise ValueError(msg)
def digest(path):
    b=path.read_bytes();return {'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def literal(text):
    def visit(n):
        if isinstance(n,ast.Constant) and type(n.value) is int:return F(n.value)
        if isinstance(n,ast.Tuple):return tuple(visit(v) for v in n.elts)
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,ast.USub):return -visit(n.operand)
        if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Div):return visit(n.left)/visit(n.right)
        raise ValueError('exact rational marker')
    return visit(ast.parse(text.strip(),mode='eval').body)
class Page(HTMLParser):
    def __init__(self):
        super().__init__();self.stack=[];self.active=[];self.ids=[];self.inputs={};self.results={};self.tasks=[];self.answers=[];self.answertext={};self.sources={};self.hrefs=[];self.h1=0;self.tables=[]
    def handle_starttag(self,t,attrs):
        a=dict(attrs)
        if t=='h1':self.h1+=1
        if 'id' in a:need(a['id'] not in self.ids,'unique IDs');self.ids.append(a['id'])
        if 'href' in a:self.hrefs.append(a['href'])
        if 'data-points' in a:self.tasks.append((a['id'],int(a['data-points'])))
        if 'data-solution-for' in a:
            need(any(x=='details' and 'solutions' in v.get('class','').split() for x,v in self.stack),'solution disclosure');k=a['data-solution-for'];self.answers.append(k);self.answertext[k]='';self.active.append((self.answertext,k,len(self.stack)))
        if 'data-source' in a:self.sources[a['data-source']]=a['href']
        for k,d in [('data-input',self.inputs),('data-result',self.results)]:
            if k in a:need(a[k] not in d,'unique markers');d[a[k]]='';self.active.append((d,a[k],len(self.stack)))
        if t=='table':self.tables.append([])
        if t=='tr':self.tables[-1].append([])
        if t in ('td','th'):
            row=self.tables[-1][-1];row.append('');self.active.append((row,len(row)-1,len(self.stack)))
        if t not in ('br','hr','img','input','link','meta'):self.stack.append((t,a))
    def handle_data(self,s):
        for d,k,_ in self.active:d[k]+=s
    def handle_endtag(self,t):
        need(self.stack and self.stack[-1][0]==t,'balanced HTML');self.stack.pop();self.active=[v for v in self.active if v[2]<len(self.stack)]
class ExamPage(Page):
    def __init__(self):
        super().__init__();self.rubrics={};self.domain=None;self.domain_tasks={};self.chapters={}
    def handle_starttag(self,t,attrs):
        a=dict(attrs);super().handle_starttag(t,attrs)
        if 'data-domain' in a:self.domain=a['data-domain'];self.domain_tasks[self.domain]=[]
        if 'data-points' in a:self.domain_tasks[self.domain].append(a['id']);self.chapters[a['id']]=a.get('data-chapters','').split()
        if 'data-rubric-points' in a:
            need(bool(self.answers),'rubric has answer');self.rubrics.setdefault(self.answers[-1],[]).append(int(a['data-rubric-points']))
    def handle_endtag(self,t):
        super().handle_endtag(t)
        if t=='section':self.domain=None

def vec(x,n=None):
    need(type(x) is tuple and (n is None or len(x)==n) and all(type(z) in (int,F) for z in x),'exact vector');return tuple(F(z) for z in x)
def schedule(cash,project,advance):
    opening,payroll,research,floor,rate=vec(cash,5);price,original,fees,reimbursement=vec(project,4);advance,=vec((advance,),1)
    need(min(opening,payroll,research,floor,price,original,fees,reimbursement,advance)>=0 and 0<=original<=price and advance<=price and rate>-1,'schedule domain')
    common=opening-payroll-research;after=common-advance;invoice=price-advance;received=after+fees+reimbursement;closed=received-invoice
    # Terminal wealth comparison discounts one accumulated initial outflow and the net final inflow.
    incremental_final=fees+reimbursement-invoice-advance*(1+rate);npv=incremental_final/(1+rate)
    return {'common':common,'after':after,'invoice':invoice,'received':received,'closed':closed,'npv':npv,'passes':min(common,after,received,closed)>=floor,'gap':max(F(0),floor-after)}
def timing(lower,upper):
    lower,upper=vec((lower,upper));need(lower>=0 and lower<=upper,'timing interval');mid=(lower+upper)/2;return mid,((upper-lower)/2,)*2,(upper-lower)**2/4

def effort(params,b):
    h,l,cost,cap,defect,audit=vec(params,6);b,=vec((b,),1);need(0<=l<h<=1 and min(cost,cap,defect,b)>=0 and 0<=audit<=1,'effort domain')
    utilities=(h*b-cost,l*b);return utilities,(cost/(h-l),cap/h),h*b

def workload(values):
    total,fixed,research,teach,feedback,original,proposed=vec(values,7);need(min(total,fixed,research,teach,feedback)>=0 and teach+feedback>0 and original.denominator==proposed.denominator==1,'workload domain')
    remaining=total-fixed-research;need(remaining>=0,'fixed workload infeasible');maximum=remaining//(teach+feedback)
    research_at=lambda n:total-fixed-n*(teach+feedback)
    return F(maximum),research_at(maximum),research_at(original),research_at(proposed),fixed+research+proposed*(teach+feedback)

def transactions(values,equity_issue=0,borrowing=0):
    c,n,d,e,loss,withdraw,expense,cf,ef,bforecast,forecast=vec(values,11);equity_issue,borrowing=vec((equity_issue,borrowing));need(min(c,n,d,e,loss,withdraw,expense,cf,ef,equity_issue,borrowing)>=0 and c+n==d+e and loss<=n and withdraw<=d,'balance domain')
    cash=c+equity_issue+borrowing;eq=e+equity_issue;debt=borrowing;states=[(cash,n,d,debt,eq)]
    n-=loss;eq-=loss;states.append((cash,n,d,debt,eq));cash-=withdraw;d-=withdraw;states.append((cash,n,d,debt,eq));cash-=expense;eq-=expense;states.append((cash,n,d,debt,eq))
    for cc,nn,dd,bb,ee in states:need(cc+nn==dd+bb+ee,'all-stage balance identity')
    return tuple(states),all(s[0]>=cf and s[4]>=ef for s in states)

def classify(rows,costs):
    miss,false,review=vec(costs,3);need(min(miss,false,review)>=0,'classification costs');records=[]
    for row in rows:
        truth=int(row[0]=='Urgent')
        for pred,count in ((1,int(row[1])),(0,int(row[2]))):
            need(count>=0,'classification counts');records.extend((truth,pred) for _ in range(count))
    need(bool(records),'nonempty classifier test');results={}
    for policy in ('Auto','FlagReview','AllHuman'):
        total=F(0);urgent_misses=reviews=0
        for truth,pred in records:
            usehuman=policy=='AllHuman' or policy=='FlagReview' and pred==1
            if usehuman:total+=review;reviews+=1;pred=truth
            if truth and not pred:total+=miss;urgent_misses+=1
            elif pred and not truth:total+=false
        results[policy]=(total,urgent_misses,reviews)
    accuracy=F(sum(t==p for t,p in records),len(records));return accuracy,results,tuple(records)

def flow(q,arrival,capacity,days):
    q,arrival,capacity=vec((q,arrival,capacity));need(min(q,arrival,capacity)>=0 and type(days) is int and days>=0,'flow domain');finished=F(0)
    for _ in range(days):
        ready=q+arrival;done=min(ready,capacity);finished+=done;q=ready-done
    return q,finished

def composition(rows):
    records=[]
    for row in rows:
        a,ma,b,mb=(F(x) for x in row[1:]);need(a.denominator==b.denominator==1 and min(a,b)>=0 and a+b>0,'composition domain');records.append((tuple([ma]*int(a)+[mb]*int(b)),(a,b),(ma,mb)))
    before,after=records;mean0=sum(before[0])/len(before[0]);mean1=sum(after[0])/len(after[0]);standard=sum(n*value for n,value in zip(before[1],after[2]))/len(before[0]);return mean0,mean1,mean1-mean0,standard,standard-mean0

def robust(lo,hi,adverse,pause):
    lo,hi,adverse,pause=vec((lo,hi,adverse,pause));need(0<=lo<=hi<=1 and adverse>0 and pause>=0,'robust interval domain');worst=(max(adverse*lo,adverse*hi),pause);best=min(worst);return worst,tuple(i for i,x in enumerate(worst) if x==best)

def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1];start={p:digest(root/p) for p in FILES};review=json.loads((root/REVIEW).read_text());need(set(review['payloads'])==set(FILES[:-1]),'five nonself bindings')
    for path,binding in review['payloads'].items():need(start[path]==binding,'peer binding '+path)
    author=json.loads((root/AUTHOR[3]).read_text())
    bindings=author.get('payloads',author.get('payload_bindings'))
    need(isinstance(bindings,dict),'author bindings mapping')
    for path,binding in bindings.items():need(start[path]==binding,'author binding '+path)
    p=ExamPage();p.feed((root/AUTHOR[0]).read_text());tasks=[('v18-exam-b-q'+str(i).zfill(2),5) for i in range(1,21)]
    need(not p.stack and p.h1==0 and p.tasks==tasks and p.answers==[k for k,_ in tasks],'all20 exact prompts/solutions')
    need(all(k in ('form-b','solutions-b') or k.startswith('v18-exam-b-') for k in p.ids),'scoped identifiers')
    need(set(p.rubrics)==set(p.answers) and all(v==[1]*5 for v in p.rubrics.values()),'all additive five-point rubrics')
    domains=('strategy_resources','people_organization','governance_academic','finance_operations','crisis_evidence_integration');need(tuple(p.domain_tasks)==domains,'five declared domains')
    for i,name in enumerate(domains):need(p.domain_tasks[name]==[k for k,_ in tasks[4*i:4*i+4]],'20point domain '+name)
    need(set(ch for cs in p.chapters.values() for ch in cs)=={'v18-c'+str(i).zfill(2) for i in range(1,13)},'all12 exact task mappings')
    sources=json.loads((root/AUTHOR[2]).read_text());need(p.sources=={s['id']:s['url'] for s in sources['sources']},'source URLs')
    inp={k:literal(v) for k,v in p.inputs.items()};shown={k:literal(v) for k,v in p.results.items()};count=0
    need(set(inp)=={'academic-cash','academic-outcomes','academic-hours','incentives','balance','losses','process','crisis','execution','scores'},'all primitive groups')
    projectrows=next(t for t in p.tables if t and t[0][0]=='Version');projects={row[0]:tuple(F(x) for x in row[1:]) for row in projectrows[1:]};cash=inp['academic-cash'];lower=F(5);upper=cash[0]-cash[1]-cash[2]-cash[3];t,gains,prod=timing(lower,upper)
    sp=schedule(cash,projects['P'],projects['P'][1]);sq=schedule(cash,projects['Q'],t);unamended=schedule(cash,projects['Q'],projects['Q'][1]);need(sq['passes'] and not sp['passes'] and not unamended['passes'],'dated feasibility screens');count+=3
    expected={'q02':(sq['common'],sq['after'],sq['invoice'],sq['closed'],sp['gap'],unamended['gap']),'q03':(sp['npv'],sq['npv'],schedule(cash,projects['Q'],t+F(1,4))['npv']-sq['npv'])}
    expected['q03']=expected['q03'][:2]+(expected['q03'][2]/F(1,4),)
    expected['q04']=((lower,upper),t,gains,prod,sq['invoice'])
    util,bounds,pay=effort(inp['incentives'],F(9,2));expected['q05']=(bounds,util,util[0]-util[1],pay)
    h,l,ecost,pcap,defective,audit=inp['incentives'];truth,_,_=effort(inp['incentives'],defective);expected['q06']=((1-audit)*defective,)+truth
    # Manual item-level judgments on the full quoted work samples, retaining actual first ratings.
    item_scores={'I':(1,1,1,1,1,1),'J':(0,0,0,0,1,0),'K':(1,1,1,1,1,0)}
    vectors={k:tuple(sum(bits[i:i+2]) for i in (0,2,4)) for k,bits in item_scores.items()};expected['q07']=tuple(F(sum(item_scores[k])) for k in 'IJK')
    ratings=next(t for t in p.tables if t and t[0][0]=='Candidate');need(all(literal(row[2])==vectors[row[0]] for row in ratings[1:]),'Y ratings versus original response item audit');count+=3
    need(literal(ratings[2][1])!=(vectors['J']) and [k for k,v in vectors.items() if v[:2]==(2,2)]==['I','K'],'unanimity and eligibility');count+=2
    eligible={'C','D','E'};threshold=len(eligible)//2+1;present0={'A','B','C','D','E'};yes0={'A','B','C','D'};present1={'D','E'};yes1={'D','E'}
    expected['q09']=tuple(map(F,(len(eligible),threshold,len(eligible&present0),len(eligible&yes0),len(eligible&present1),len(eligible&yes1))))
    need(len(eligible&present0)==3 and len(eligible&yes0)>=threshold and len(eligible&present1)<3,'independent quorum and majority');count+=3
    expected['q11']=workload(inp['academic-hours']);outcomes=vec(inp['academic-outcomes']);need(all(x in (0,1) for x in outcomes),'binary criterion outcomes');whole=sum(outcomes)/len(outcomes);retained=sum(x for x in outcomes if x)/sum(x==1 for x in outcomes);expected['q12']=(whole,retained,retained-whole)
    balance=inp['balance'];states,ok=transactions(balance);unfunded=states[-1];bs,bok=transactions(balance,borrowing=balance[9]);borrowed=bs[-1];issue=max(F(0),balance[7]-unfunded[0],balance[8]-unfunded[4]);fs,fok=transactions(balance,equity_issue=issue);funded=fs[-1]
    need(not ok and not bok and fok,'separate cash and capital gates');count+=3
    expected['q13']=((unfunded[0],unfunded[1],unfunded[2],unfunded[4]),(borrowed[0],borrowed[3],borrowed[4]),issue,(funded[0],funded[1],funded[2],funded[4]))
    classrows=next(t for t in p.tables if t and t[0][0]=='True class');accuracy,policies,records=classify(classrows[1:],inp['losses']);expected['q14']=(accuracy,)+tuple(policies[k][0] for k in ('Auto','FlagReview','AllHuman'))+(F(policies['FlagReview'][2]),)
    need([k for k,v in policies.items() if v[1]==0]==['AllHuman'],'only human test gate');count+=1
    intake,rev,release,arrivals,q,newintake,newreview=inp['process'];base=min(intake,rev,release);server=min(newintake,rev,release);staff=min(intake,newreview,release);qbase,_=flow(q,arrivals,base,3);qserver,_=flow(q,arrivals,server,3);qstaff,done3=flow(q,arrivals,staff,3);_,done6=flow(q,arrivals,staff,6)
    expected['q15']=(base,qbase,server,qserver,staff,qstaff,q/(staff-arrivals),done3,done6)
    comprows=next(t for t in p.tables if t and t[0][0]=='Period');expected['q16']=composition(comprows[1:])
    low,oldhi,newhi,adverse,pause=inp['crisis'];initial,ic=robust(low,oldhi,adverse,pause);revised,rc=robust(low,newhi,adverse,pause);boundary=pause/adverse;expected['q17']=(initial,revised,boundary)
    need(ic==(0,) and rc==(1,) and robust(low,boundary,adverse,pause)[1]==(0,1),'crisis choices/tie');count+=3
    n,ontime,actual,baseline,ceiling=inp['execution'];expected['q18']=(ontime/n,actual-baseline,ceiling-actual)
    scores=inp['scores'];updated=scores[:3]+(F(15),)+scores[4:];expected['q19']=((sum(scores),sum(updated)),scores[3],updated[3]);need(sum(scores)>=85 and min(scores)<15 and sum(updated)>=85 and min(updated)>=15,'numeric score/domain gates');count+=4
    need(set(expected)==set(shown),'every result group')
    def leaves(v):return sum(leaves(x) for x in v) if isinstance(v,tuple) else 1
    for key,value in expected.items():need(value==shown[key],'displayed '+key);count+=leaves(value)
    timing_worlds=0
    for numerator in range(20,25):
        advance=F(numerator,4);ss=schedule(cash,projects['Q'],advance);timing_worlds+=1
        need(ss['passes'] and ss['closed']==13 and ss['invoice']+advance==8,'all feasible timing cash');count+=3
        productvalue=(upper-advance)*(advance-lower);need(productvalue==prod-(advance-t)**2 and productvalue<=prod,'timing global certificate');count+=2
    for b in (F(0),F(3),F(4),F(9,2),F(5),F(6)):
        u,interval,paid=effort(inp['incentives'],b);need((u[0]>=u[1] and paid<=pcap)==(interval[0]<=b<=interval[1]),'weak incentive region');need((u[0]>u[1] and paid<=pcap)==(interval[0]<b<=interval[1]),'strict tie region');count+=2
    # Full finite enumeration of attendance/votes keeps recusal, quorum and passage separate.
    vote_worlds=0
    for presentbits in product((0,1),repeat=3):
        for votebits in product((0,1),repeat=sum(presentbits)):
            present=sum(presentbits);yes=sum(votebits);passes=present==3 and yes>=2;need(not passes or present==3 and yes>=threshold,'vote conjunction');count+=1;vote_worlds+=1
    workload_worlds=0
    total,fixed,research,teach,feedback,original,proposed=inp['academic-hours']
    for cohort in range(41):
        remaining=total-fixed-cohort*(teach+feedback);need((remaining>=research)==(cohort<=expected['q11'][0]),'global integer workload');count+=1;workload_worlds+=1
    for issue0 in (F(0),F(1,2),F(1),F(2)):
        ss,passes=transactions(balance,equity_issue=issue0);need(passes==(issue0>=issue),'minimum equity and allstage protection');count+=1
    for days in (0,1,3,4,6,10):
        backlog,completed=flow(q,arrivals,staff,days);need(backlog==max(F(0),q+(arrivals-staff)*days) and completed+backlog==q+arrivals*days,'daily recursion versus conservation');count+=2
    # All policies' per-record cost totals versus independently aggregated confusion counts.
    tn=sum(not t and not pr for t,pr in records);tp=sum(t and pr for t,pr in records);fn=sum(t and not pr for t,pr in records);fp=sum(not t and pr for t,pr in records)
    for miss in (F(0),F(3),F(12),F(30)):
        costs=(miss,)+inp['losses'][1:];_,ps,_=classify(classrows[1:],costs);need(ps['Auto'][0]==fn*miss+fp*costs[1] and ps['FlagReview'][0]==fn*miss+(tp+fp)*costs[2] and ps['AllHuman'][0]==len(records)*costs[2],'individual versus aggregate classification loss');count+=3
    for upper in (low,oldhi,boundary,newhi,F(1)):
        worst,ch=robust(low,upper,adverse,pause)
        for j in range(9):
            prob=low+(upper-low)*j/8;need(adverse*prob<=worst[0] and pause==worst[1],'global interval bound');count+=2
    invalid=0
    bad=[lambda:schedule(cash,projects['Q'],9),lambda:schedule(cash[:-1]+(-1,),projects['Q'],5),lambda:timing(6,5),lambda:effort((F(1,5),F(3,10),2,4,3,F(1,4)),4),lambda:effort(inp['incentives'],-1),lambda:workload((10,8,12,F(1,2),F(1,4),24,32)),lambda:transactions(balance,equity_issue=-1),lambda:transactions((14,86,88,11)+balance[4:]),lambda:classify(classrows[1:],(-1,2,F(1,2))),lambda:flow(20,40,45,True),lambda:flow(-1,40,45,3),lambda:robust(F(1,2),F(1,10),30,7),lambda:robust(0,1,0,7),lambda:literal('(1,0.5)')]
    for fn in bad:
        try:fn()
        except ValueError:invalid+=1
        else:raise ValueError('invalid domain accepted')
    need(start=={p:digest(root/p) for p in FILES},'runtime mutation')
    out={'volume':'v18','component':'exam_b','status':'passed','runtime_files':6,'prompts':20,'points':100,'domains':5,'chapters':12,'result_groups':len(shown),'comparisons':count,'timing_worlds':timing_worlds,'vote_worlds':vote_worlds,'workload_cohorts':workload_worlds,'classifier_records':len(records),'invalid_domains':invalid,'scope':'Independent dated-ledger, item-level evidence, payoff, per-record classifier and flow oracle; full artifact/proof review separate; author checker opaque; no actual learner leadership certification.'}
    json.dumps(out,allow_nan=False);return out
if __name__=='__main__':
    need(len(sys.argv)<=2,'usage: check_v18_exam_b_peer.py [book-root]');check(sys.argv[1] if len(sys.argv)==2 else None)
