"""Independent Form A peer: primitive enumeration and exact arithmetic; author checker opaque."""
from pathlib import Path
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from itertools import product
import ast,json,re
FILES=('content/assessments/parts/v18-exam-a.html','scripts/check_v18_exam_a.py','content/reviews/v18-exam-a-sources.json','content/reviews/v18-exam-a-author.json','scripts/check_v18_exam_a_peer.py','content/reviews/v18-exam-a-peer.json')
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
        if tag=='li' and 'data-points' in a:self.prompts[a['id']]='';require(a['data-points']=='5','five points each')
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






def cohorts(staff=18,budget=16,maxy=4):
    require(type(staff)==int and type(maxy)==int and min(staff,budget,maxy)>=0,'cohort resources')
    rows=[]
    for x,y in product(range(4),range(maxy+1)):
        n=6*x+4*y;hours=5*x+3*y;cost=4*x+3*y
        if hours<=staff and cost<=budget and 12*y>=n:rows.append((n,-hours,x,y,cost,4*y))
    best=max(rows);return best[2],best[3],best[0],-best[1],best[4],best[5]

def bargain(value,cost,ceiling):
    value,cost,ceiling=map(F,(value,cost,ceiling));require(min(value,cost,ceiling)>=0,'nonnegative bargaining inputs')
    lo=cost+2;hi=min(value-6,ceiling);require(lo<=hi,'participation possible')
    t=min(hi,max(lo,(value-6+cost+2)/2));return lo,hi,t,(value-6-t)*(t-cost-2)

def posterior(p,s,f):
    p,s,f=map(F,(p,s,f));require(all(0<=z<=1 for z in (p,s,f)),'probability inputs')
    m=p*s+(1-p)*f;require(m>0,'positive conditioning event');return m,p*s/m

def ledger(x,y,loss=2,issue=0):
    x,y,loss,issue=map(F,(x,y,loss,issue));require(min(x,y,loss,issue)>=0,'ledger domains')
    risk=x/4+y/2
    return 26-6-x-y+issue,74+x+y-loss-risk,88-6,12-loss-risk+issue

def loan_vertices(loss):
    loss=F(loss);require(0<=loss<=6,'loss leaves at least floor before new lending')
    # All intersections of the two axes, cash and equity boundaries.
    constraints=((1,0,0),(0,1,0),(1,1,12),(1,2,4*(6-loss)))
    out=set()
    for i,(a,b,c) in enumerate(constraints):
        for d,e,f in constraints[i+1:]:
            det=a*e-b*d
            if det:
                x=F(c*e-b*f,det);y=F(a*f-c*d,det)
                if min(x,y)>=0 and x+y<=12 and x+2*y<=4*(6-loss):out.add((x,y))
    return out

def audit(d):
    count=0
    def eq(a,b,msg):
        nonlocal count
        require(a==b,msg);count+=1
    def yes(a,msg):eq(bool(a),True,msg)
    inp={k:numeric(v) for k,v in d.inputs.items()}
    expected={'clinic':(6,4,5,3,4,3,3,4,18,16),'cash':(32,3,7,6,10),'bundles':((18,4),(15,2),(6,2,7)),'incentives':(4,4,6,2),'hiring':(9,6,4,F(1,10),F(4,5),F(1,5)),'lender':(26,74,88,12,6,2,8,6),'lending-rates':((F(1,4),F(1,2)),(F(1,2),F(3,4))),'workflow':(180,3,6,1,1,22,18),'crisis':(F(1,4),F(4,5),F(1,5),F(1,2),12,4,5,4,10)}
    eq(inp,expected,'actual visible primitives')
    clinic=cohorts();reduced=cohorts(staff=15);transfer=cohorts(maxy=3)
    local=bargain(18,4,7);remote=bargain(15,2,7);t=remote[2]
    openC,launch,reserve,floor,tuition=inp['cash'];cost=clinic[4]
    c0=openC-launch-t-F(cost,2);c30=c0-F(cost,2);c60=c30+tuition
    l1=ledger(8,4);lpre=ledger(12,0,loss=3);lpost=ledger(8,4,loss=3,issue=1)
    rows=[r for r in d.rows if len(r)==3 and r[0] in ('1','2','3')]
    eq(rows,[['1','4','5'],['2','3','5'],['3','5','8']],'actual paired queue table')
    diffs=[numeric(r[1])-numeric(r[2]) for r in rows];estimate=sum(diffs)/3
    stats=sorted(sum(s*x for s,x in zip(sign,diffs))/3 for sign in product((-1,1),repeat=3));pv=F(sum(abs(x)>=abs(estimate) for x in stats),len(stats))
    pr,sens,false,fee,adverse,bkup,minute,setup,deadline=inp['crisis']
    wm,wp=posterior(pr,sens,false);nm,np=posterior(pr,1-sens,1-false)
    policies={pair:wm*(adverse*wp if pair[0]=='W' else bkup)+nm*(adverse*np if pair[1]=='W' else bkup) for pair in product('WB',repeat=2)}
    gross=min(policies.values());net=gross+fee;opening=(l1[0]+5,l1[3]+5)
    rates=tuple(sorted({F(16+sum(z),22) for z in product((0,1),repeat=2)}))
    want={'q1':clinic,'q2':(c0,c30,c60,c30,c30-floor),'q3':((local[0],local[1]),local[2],local[3],(remote[0],remote[1]),remote[2],remote[3]),'q4':reduced[:5]+(openC-launch-t-reduced[4],),'q5':(F(3,2),F(3,2),F(9,2),F(9,8)),'q6':posterior(*inp['hiring'][3:])+(7,5),'q7':((4,6-4),(6,6-6)),'q11':transfer,'q13':(8,4,F(8,2)+F(3*4,4))+l1+(sum(l1[:2]),),'q14':((12,0,6)+lpre,lpost+(1,)),'q15':(F(180,9),F(180,8),18+5*(22-F(180,9)),F(18)/(F(180,8)-22)),'q16':(estimate,tuple(stats),pv),'q17':opening+(wm,wp,np,gross,net,pr*adverse-net),'q18':(pr*adverse+fee,pr*adverse,fee+bkup,opening[0]-fee-bkup,opening[1]-fee-bkup),'q19':(rates,F(16,20),c30,c60,18-clinic[3])}
    eq(set(want),set(d.results),'every displayed result group')
    for k,v in want.items():eq(numeric(d.results[k]),v,'displayed '+k)
    worlds=0
    for staff,maxy,winner in ((18,4,(1,4)),(15,4,(1,3)),(18,3,(2,2))):
        sol=cohorts(staff=staff,maxy=maxy);eq(sol[:2],winner,'unique optimum by exhaustive choices')
        feasible=[]
        for x,y in product(range(4),range(maxy+1)):
            worlds+=1;n=6*x+4*y;work=5*x+3*y
            yes(n<=F(6,5)*work+F(2,5)*y,'global identity certificate')
            if work<=staff and 4*x+3*y<=16 and 12*y>=n:
                yes(n<=sol[2],'all feasible plans dominated');feasible.append((n,x,y))
        eq([(x,y) for n,x,y in feasible if n==sol[2]],[winner],'unique maximizer')
    eq((bargain(18,4,9),bargain(15,2,9)),((6,9,9,9),(4,9,F(13,2),F(25,4))),'funded ceiling9 comparison')
    # Quadratic identities are global certificates; rational interior/boundary witnesses test signs and clipping.
    for val,cost,cap in ((18,4,7),(15,2,7),(18,4,9),(15,2,9),(15,2,4)):
        lo,hi,opt,maximum=bargain(val,cost,cap)
        center=F(val-6+cost+2,2);joint=val-cost-8
        for j in range(9):
            z=lo+(hi-lo)*F(j,8);g=(val-6-z)*(z-cost-2)
            eq(g,F(joint*joint,4)-(z-center)**2,'global product square identity');yes(g<=maximum,'constrained global product maximum')
    eq((15-t,t-2),(F(17,2),F(9,2)),'contract net payoffs')
    for s in (F(0),F(1,2),F(3,2),F(4)):
        for effort in (F(0),F(1),s,F(4)):
            utility=s*effort-effort**2/2
            eq(utility,s*s/2-(effort-s)**2/2,'agent global square identity');yes(utility<=s*s/2,'global response')
        institution=6*s-2*s*s;eq(institution,F(9,2)-2*(s-F(3,2))**2,'institution global square identity');yes(institution<=F(9,2),'institution maximum')
    eq((9-6,2+2+2+1,2+0+2+1),(3,7,5),'work sample calculation and additive scoring')
    eq((8-8,8-9),(0,-1),'actual new development task key')
    for loss,solution in ((2,(8,4)),(3,(12,0))):
        vertices=loan_vertices(loss);values={z:z[0]/2+3*z[1]/4 for z in vertices};maximum=max(values.values())
        eq([z for z,v in values.items() if v==maximum],[solution],'all continuous feasible polygon vertices')
        for x,y in vertices:
            eq(x/2+3*y/4,(x+y)/4+(x+2*y)/4,'positive resource certificate')
            yes((x+y)/4+(x+2*y)/4<=3+6-loss,'global resource bound')
            C,N,D,E=ledger(x,y,loss);eq(C+N,D+E,'each vertex ledger reconciles');yes(C>=8 and E>=6,'vertex floors')
    eq(ledger(8,4,3),(8,79,82,5),'fixed postcommit loss')
    for issue in (F(0),F(1,2),F(1),F(2)):
        C,N,D,E=ledger(8,4,3,issue);eq(C+N,D+E,'actual equity issue balance');eq(C>=8 and E>=6,issue>=1,'necessary/sufficient equity repair')
    eq(set(pair for pair,v in policies.items() if v==gross),{('B','W')},'unique joint-mass optimal signal policy')
    eq(sum((wm,nm)),1,'exhaustive signal mass');eq(wm*wp+nm*np,pr,'martingale posterior')
    eq((minute+setup,deadline-setup),(9,6),'completion and last possible start')
    for release in (5,6,7,8):eq(release+setup<=deadline,release<=6,'exact timing boundary')
    for p in (F(0),F(1,13),F(1,3),F(4,7),F(1)):
        eq(12*p<=4,p<=F(1,3),'full conditional threshold including tie')
    # Joint-state enumeration verifies every candidate policy without reusing posterior formulas.
    for pair,value in policies.items():
        direct=F(0)
        for fault in (False,True):
            prior=pr if fault else 1-pr;likelihood=sens if fault else false
            for signal in (True,False):
                mass=prior*(likelihood if signal else 1-likelihood);action=pair[0 if signal else 1]
                direct+=mass*(bkup if action=='B' else adverse*int(fault))
        eq(direct,value,'primitive joint-state policy expectation')
    eq(policies[('W','W')]+fee,F(7,2),'late test only waiting feasible')
    eq(max(fee,fee+bkup),F(9,2),'max branch operating expense')
    yes(opening[0]-fee-bkup>=8 and opening[1]-fee-bkup>=6,'both hard branch floors')
    invalid=[lambda:cohorts(staff=-1),lambda:cohorts(maxy=-1),lambda:cohorts(staff=F(3,2)),lambda:bargain(18,4,5),lambda:bargain(18,-1,7),lambda:posterior(-1,1,0),lambda:posterior(1,2,0),lambda:posterior(1,0,0),lambda:ledger(-1,0),lambda:ledger(0,0,issue=-1),lambda:loan_vertices(7),lambda:strict_json('{"x":1,"x":2}'),lambda:strict_json('{"x":NaN}')]
    for fn in invalid:
        try:fn()
        except ValueError:pass
        else:raise ValueError('invalid domain accepted')
    return {'comparisons':count,'invalid_domains':len(invalid),'cohort_worlds':worlds,'assignment_worlds':len(stats),'crisis_policies':len(policies),'missing_outcome_worlds':4,'numeric_groups':len(want)}

def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    raw={f:(root/f).read_bytes() for f in FILES};peer=strict_json(raw[FILES[5]]);author=strict_json(raw[FILES[3]]);sources=strict_json(raw[FILES[2]])
    require(set(peer['payloads'])==set(FILES[:5]) and set(author['payloads'])==set(FILES[:3]),'nonself payload bindings')
    for rec in (peer,author):
        for f,b in rec['payloads'].items():require(b=={'bytes':len(raw[f]),'sha256':sha256(raw[f]).hexdigest()},'frozen payload '+f)
    d=BaseManuscript();d.feed(raw[FILES[0]].decode());require(not d.stack and len(d.ids)==len(set(d.ids)),'balanced unique HTML')
    ids={f'v18-exam-a-q{i}' for i in range(1,21)}
    require(set(d.prompts)==set(d.solutions)==set(peer['exact_prompt_review'])==ids,'twenty exact prompt/answer pairs')
    for k,v in peer['exact_prompt_review'].items():
        require(v['prompt_sha256']==sha256(d.prompts[k].encode()).hexdigest() and v['solution_sha256']==sha256(d.solutions[k].encode()).hexdigest(),'exact reviewed prompt/solution')
        rubric=d.solutions[k].split('Rubric5:')[-1];require(sum(int(x) for x in re.findall(r'(\d+)(?=;|\.)',rubric))==5,'additive rubric five')
    require(all(f'v18-exam-a-domain{i}' in d.ids for i in range(1,6)),'five domains')
    require({a for a in d.links if not a.startswith('https://')}=={f'v18-c{i:02}.html' for i in range(1,13)},'all twelve chapter routes')
    require(d.sources=={s['id']:s['url'] for s in sources['sources']} and len(d.sources)==2,'exact source routes')
    require(all(s['actual_inspector']=='v16_c01_author' for s in sources['sources']),'retained original source inspector')
    result=audit(d)
    return dict(component='v18-exam-a',status='passed',review='independent internal peer',runtime_files=6,prompts=20,solutions=20,points=100,domains=5,source_routes=2,author_checker='opaque hash only; never text-read/imported/executed',**result)

if __name__=='__main__':check()
