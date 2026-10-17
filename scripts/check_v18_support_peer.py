"""Independent V18 diagnostic/oral/retention peer; opaque author checker."""
from pathlib import Path
from fractions import Fraction as F
from html.parser import HTMLParser
from itertools import combinations,product
import ast,hashlib,json,re,sys
AUTHOR=('content/assessments/parts/v18-support-opening.html','content/assessments/parts/v18-support-closing.html','scripts/check_v18_support.py','content/reviews/v18-support-sources.json','content/reviews/v18-support-author.json')
SELF='scripts/check_v18_support_peer.py';REVIEW='content/reviews/v18-support-peer.json';FILES=AUTHOR+(SELF,REVIEW)
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
def vector(x,n=None):
    need(type(x) is tuple and (n is None or len(x)==n) and all(type(v) in (int,F) for v in x),'exact vector');return tuple(F(v) for v in x)
def closing(values):
    c,n,d,e,loss,withdrawal=vector(values,6);need(min(c,n,d,e,loss,withdrawal)>=0 and c+n==d+e and loss<=n and withdrawal<=min(c,d),'ledger domain')
    c-=withdrawal;n-=loss;d-=withdrawal;e-=loss;need(c+n==d+e,'closing identity');return c,n,d,e,c+n
def project(cost,pay,periods,rate,cash,floor):
    cost,pay,rate,cash,floor=vector((cost,pay,rate,cash,floor));need(min(cost,pay,cash,floor)>=0 and rate>-1 and type(periods) is int and periods>0,'project domain')
    # Carry all costs/receipts to a common terminal date, then discount the surplus.
    terminal=-cost*(1+rate)**periods+sum(pay*(1+rate)**(periods-t) for t in range(1,periods+1));npv=terminal/(1+rate)**periods
    return npv+cost,npv,cash-cost,max(F(0),floor-(cash-cost))
def missing(total,known,success):
    need(all(type(x) is int for x in (total,known,success)) and total>0 and 0<=success<=known<=total,'roster domain')
    counts=[success+sum(bits) for bits in product((0,1),repeat=total-known)]
    return tuple(sorted(set(F(k,total) for k in counts))),len(counts)
def bayes(p,hit,false):
    p,hit,false=vector((p,hit,false));need(all(0<=x<=1 for x in (p,hit,false)),'probability domain');joint=p*hit;mass=joint+(1-p)*false;need(mass>0,'zero-probability evidence');return mass,joint,joint/mass
def allocation(cash,risk,rx,ry,px,py):
    cash,risk,rx,ry,px,py=vector((cash,risk,rx,ry,px,py));need(min(cash,risk)>=0 and min(rx,ry,px,py)>0 and rx!=ry,'allocation domain')
    # Eliminate y: positive py means y is on its upper envelope. Only kink/endpoints can maximize.
    xmax=min(cash,risk/rx);xs={F(0),xmax,(ry*cash-risk)/(ry-rx)};scores={}
    for x in xs:
        if 0<=x<=xmax:
            y=min(cash-x,(risk-rx*x)/ry)
            if y>=0:scores[(x,y)]=px*x+py*y
    best=max(scores.values());return tuple(sorted(k for k,v in scores.items() if v==best)),best

def incentive(b):
    b,=vector((b,),1);need(b>=0,'rate domain');actions={'L':(F(2),F(4),F(1)),'H':(F(5),F(1),F(3))}
    utilities={k:b*o-c for k,(o,q,c) in actions.items()};chosen=max(('outside','L','H'),key=lambda k:((utilities[k] if k!='outside' else 0),{'outside':0,'L':1,'H':2}[k]))
    payoff=F(0) if chosen=='outside' else actions[chosen][0]+2*actions[chosen][1]-b*actions[chosen][0]
    return chosen,utilities,payoff

def robust(adverse,pause,low,high):
    adverse,pause,low,high=vector((adverse,pause,low,high));need(adverse>0 and pause>=0 and 0<=low<=high<=1,'robust domain')
    states=[(p*adverse,pause) for p in (low,high)];worst=tuple(max(x[i] for x in states) for i in range(2));regret=tuple(max(x[i]-min(x) for x in states) for i in range(2));return (pause/adverse,)+worst+regret

def admissions(budget):
    budget,=vector((budget,),1);need(budget>=0,'scholarship domain');options={}
    for a in range(21):
        for b in range(16):
            n=a+b;hours=2*a+3*b
            if hours<=60 and 3*b>=n and 2*b<=budget:options[(a,b)]=(n,100-hours)
    score=max(options.values());chosen=tuple(p for p,v in options.items() if v==score);return chosen,score,options

def bargain(value,cost,ceiling):
    value,cost,ceiling=vector((value,cost,ceiling));need(min(value,cost,ceiling)>=0,'bargain domain');outside_u,outside_l=F(10),F(8);lo=cost+outside_l;hi=min(value-outside_u,ceiling)
    if hi<lo:return None
    # Product = fixed total-gain squared/4 minus squared distance from equal-gain transfer.
    target=(value-outside_u+cost+outside_l)/2;t=min(hi,max(lo,target));g=(value-t-outside_u,t-cost-outside_l)
    return (lo,hi),t,g,g[0]*g[1],target

def funding(required,ceiling):
    required,ceiling=vector((required,ceiling));need(required>=0 and ceiling>=0,'funding domain')
    # Eliminate borrowing: max funding at a sale is .8s+min(ceiling,30-s); equity limits s<=15.
    candidates={F(0),F(15),F(30)-ceiling,(required-ceiling)/F(4,5),(F(30)-required)/F(1,5)}
    feasible=[]
    for s in candidates:
        if 0<=s<=15:
            b=max(F(0),required-F(4,5)*s)
            if b<=min(ceiling,30-s):feasible.append((s,b))
    return min(feasible) if feasible else None

def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1];start={p:digest(root/p) for p in FILES};review=json.loads((root/REVIEW).read_text())
    need(set(review['payloads'])==set(FILES[:-1]),'six nonself bindings')
    for path,binding in review['payloads'].items():need(start[path]==binding,'peer binding '+path)
    author=json.loads((root/AUTHOR[4]).read_text())
    for path,binding in author['payloads'].items():need(start[path]==binding,'author binding '+path)
    page=Page()
    for path in AUTHOR[:2]:page.feed((root/path).read_text())
    need(not page.stack and page.h1==1,'assembled HTML')
    taskpoints=[('v18-d'+str(i),5) for i in range(1,9)]+[('v18-o'+str(i),4) for i in range(1,6)]+[('v18-r'+str(i),8) for i in range(1,6)]
    need(page.tasks==taskpoints and page.answers==[k for k,v in taskpoints],'18 exact tasks/answers/points')
    for k,points in taskpoints:
        text=page.answertext[k];match=re.search(r'Rubric'+str(points)+r':(.*?)(?:\. Repair|\.$)',text,re.S);need(match is not None,'rubric '+k)
        amounts=[int(x) for x in re.findall(r'(\d+)\s*(?:;|\.|$)',match.group(1))];need(sum(amounts)==points,'additive rubric '+k)
    need(all('v18-c'+str(i).zfill(2)+'.html' in page.hrefs for i in range(1,13)),'all12 chapter map')
    need({'diagnostic','administration','oral','retention','remediation','notation-index','concept-index','volume-synthesis'}<=set(page.ids),'assembly anchors')
    sources=json.loads((root/AUTHOR[3]).read_text());need(page.sources=={s['id']:s['url'] for s in sources['sources']},'sources')
    inp={k:literal(v) for k,v in page.inputs.items()};shown={k:literal(v) for k,v in page.results.items()};count=0
    expected={'d1':closing(inp['d1'])};z=inp['d2'];expected['d2']=project(z[0],z[1],int(z[2]),*z[3:]);lp,val=allocation(8,12,1,2,3,4);need(lp==((4,4),),'D3 unique');expected['d3']=lp[0]+(val,F(2),F(1));count+=1
    n,m,s=map(int,inp['d4']);rates,worlds=missing(n,m,s);expected['d4']=(F(s,m),rates)
    expected['d5']=bayes(*inp['d5']);posterior=expected['d5'][-1];expected['d6']=(F(30,100),100*posterior,F(30),100*posterior-30)
    expected['d7']=(F(120-100,120),F(120-100,100));expected['d8']=F(sum((1,1,2,1,1)))
    A,B,resource=inp['o1'];cash,floor,hours,priority=resource
    need(A[0]<=cash-floor and A[1]<=hours and A[3]>=priority and B[0]>cash-floor and B[3]<priority,'mission screens');count+=5
    expected['o1']=(cash-A[0],cash-floor,cash-19,floor-(cash-19))
    ah,u1,p1=incentive(1);al,ul,pl=incentive(F(3,5));need(ah=='H' and al=='L','incentive responses');count+=2
    expected['o2']=(F(3-1,5-2),u1['L'],u1['H'],p1,ul['L'],ul['H'],pl)
    expected['o3']=(F(3),F(4),F(6,8),F(4,8),F(6-4,8))
    need('purchase' not in page.answertext['v18-o3'] and 'procurement' not in page.answertext['v18-o3'],'audit-task repair')
    c,n,d,e,withdraw,loss,cf,ef=inp['o4'];cashbound=c-withdraw-cf;risk=e-loss-ef
    pts,best=allocation(cashbound,risk,F(1,10),F(1,5),F(1,5),F(3,10));need(len(pts)==1,'O4 unique');x,y=pts[0];newloss=x/10+y/5
    cc=c-withdraw-x-y;nn=n+x+y-loss-newloss;dd=d-withdraw;ee=e-loss-newloss;need(cc+nn==dd+ee,'O4 identity');count+=2
    expected['o4']=(x,y,best,cc,nn,dd,ee,cc+nn);expected['o5']=robust(20,8,F(1,10),F(1,2))
    admissions_results=[]
    for budget in (20,16):
        chosen,score,opts=admissions(budget);need(len(chosen)==1,'integer secondary unique');a,b=chosen[0];admissions_results.append((F(a),F(b),F(a+b),F(score[1]),F(2*b),F(budget-2*b)));count+=1
    expected['r1']=tuple(admissions_results)
    sale,borrow=funding(20,10);saleloss=sale/5;cash=5+sale*F(4,5)+borrow-20;sec=30-sale;loans=65-3;deposits=80-20;equity=20-3-saleloss
    need(borrow<=sec and equity>=14 and cash+sec+loans==deposits+borrow+equity,'R2 first ledger');count+=3
    repaymentcash=cash+6-borrow;newloans=loans-6;issue=max(F(0),5-repaymentcash)
    need(repaymentcash+sec+newloans==deposits+equity,'R2 repayment ledger');count+=1
    expected['r2']=(sale,borrow,saleloss,equity,cash+sec+loans,repaymentcash,issue,equity+issue,repaymentcash+issue+sec+newloans)
    ba=bargain(70,30,40);bb=bargain(60,20,40);expected['r3']=ba[:4]+bb[:4]+((bargain(70,30,50)[1],bargain(60,20,50)[1]),)
    contrast=(15-10)-(10-8);expected['r4']=(F(contrast),F(12),F(15-12),F(15),F(15-15))
    rates,more=missing(12,10,8);worlds+=more;expected['r5']=(rates,F(12-10),F(12-10,10))
    need(set(expected)==set(shown),'all18 result groups')
    def leaves(v):return sum(leaves(x) for x in v) if isinstance(v,tuple) else 1
    for k,v in expected.items():need(v==shown[k],'displayed '+k);count+=leaves(v)
    # Exhaust finite cohort witnesses, not a relaxed enrollment approximation.
    admission_worlds=0
    for budget in (0,2,16,18,20,30):
        chosen,score,opts=admissions(budget)
        for (a,b),(total,research) in opts.items():
            need(7*total<=180 and total<=3*(budget//2) and (total,research)<=score,'global integer bounds');count+=3;admission_worlds+=1
    # Lower-envelope capital allocation witnesses and positive-certificate equality.
    allocation_worlds=0
    for cb,rb in product((F(0),F(5),F(10)),(F(0),F(1),F(7,5),F(3))):
        opt,maximum=allocation(cb,rb,F(1,10),F(1,5),F(1,5),F(3,10));allocation_worlds+=1
        for j in range(11):
            xx=cb*j/10;yy=min(cb-xx,5*rb-xx/2)
            if yy>=0:need(xx/5+3*yy/10<=maximum,'independent allocation frontier');count+=1
    need(best==cashbound/10+risk and x+y==cashbound and x/10+y/5==risk,'positive dual certificate');count+=3
    # Global bargaining product certificate over budgets, including empty and singleton intervals.
    bargain_worlds=0
    for value,cost,budget in product((F(60),F(70)),(F(20),F(30)),(F(20),F(28),F(38),F(40),F(50))):
        z=bargain(value,cost,budget);bargain_worlds+=1
        if z is None:need(cost+8>min(value-10,budget),'empty participation region');count+=1;continue
        (lo,hi),t,g,maximum,center=z;surplus=value-cost-18
        for j in range(5):
            tt=lo+(hi-lo)*j/4;prod=(value-tt-10)*(tt-cost-8)
            need(prod==surplus**2/4-(tt-center)**2 and prod<=maximum,'gain-space global certificate');count+=2
    # Missing binary endpoint sharpness and no fabricated continuous set.
    for n,m,s in ((3,0,0),(3,3,2),(5,2,1),(10,6,4),(12,10,8)):
        rates,w=missing(n,m,s);need(rates[0]==F(s,n) and rates[-1]==F(s+n-m,n) and len(rates)==n-m+1,'binary identified set');count+=3
    # Causal worlds share observations while assigning different unobserved outcomes.
    for counter in (F(8),F(12),F(15),F(20)):
        effect=15-counter;trend=(counter-10)-(10-8);need(effect+trend==contrast,'DID decomposition');count+=1
    # Prior boundaries and incentive participation are explicit alternative cases.
    need(incentive(F(0))[0]=='outside' and incentive(F(1,2))[0]=='L' and incentive(F(2,3))[0]=='H','outside and tie conventions');count+=3
    for q in (F(0),F(1,4),F(1,2),F(1)):
        mass,joint,post=bayes(q,F(3,4),F(1,4));need(joint==mass*post and 0<=post<=1,'Bayes mass conservation');count+=2
    invalid=0
    bad=[lambda:closing((18,82,85,14,4,6)),lambda:closing((18,82,85,15,4,19)),lambda:project(10,6,2,-1,13,4),lambda:missing(10,6,7),lambda:missing(True,0,0),lambda:bayes(0,1,0),lambda:bayes(2,1,1),lambda:allocation(-1,2,1,2,3,4),lambda:allocation(8,12,1,1,3,4),lambda:incentive(-1),lambda:robust(20,8,F(1,2),F(1,10)),lambda:admissions(-1),lambda:bargain(70,-1,40),lambda:funding(-1,10),lambda:literal('(1,0.5)')]
    for fn in bad:
        try:fn()
        except ValueError:invalid+=1
        else:raise ValueError('invalid domain accepted')
    need(start=={p:digest(root/p) for p in FILES},'runtime mutation')
    out={'volume':'v18','component':'support','status':'passed','runtime_files':7,'tasks':18,'diagnostic_points':40,'oral_points':20,'retention_points':40,'result_groups':18,'comparisons':count,'primary_missing_worlds':worlds,'admission_witnesses':admission_worlds,'allocation_worlds':allocation_worlds,'bargaining_worlds':bargain_worlds,'invalid_domains':invalid,'scope':'Independent primitive record/terminal value/feasible frontier/integer cohort/gain-space oracle; full artifact and proof review separate. Author checker opaque; actual learner leadership and external evaluation unobserved.'}
    json.dumps(out,allow_nan=False);return out
if __name__=='__main__':
    need(len(sys.argv)<=2,'usage: check_v18_support_peer.py [book-root]');check(sys.argv[1] if len(sys.argv)==2 else None)
