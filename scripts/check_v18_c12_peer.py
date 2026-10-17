"""V18C12 independent resource frontier and supported-state transaction oracle."""
from pathlib import Path
from fractions import Fraction as F
from html.parser import HTMLParser
from itertools import product, combinations
import hashlib,json,sys,ast,math
FILES=('content/chapters/v18-c12.html','scripts/check_v18_c12.py','content/reviews/v18-c12-sources.json','content/reviews/v18-c12-author.json','scripts/check_v18_c12_peer.py','content/reviews/v18-c12-peer.json')
def need(ok,msg):
    if not ok:raise ValueError(msg)
def digest(p):
    b=p.read_bytes();return {'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def values(text):return tuple(F(t.strip().replace('−','-')) for t in text.strip().strip('()').split(',') if t.strip())
class Page(HTMLParser):
    def __init__(self):
        super().__init__();self.ids=[];self.h1=False;self.worked=[];self.exercises=[];self.answers=[];self.sources=[];self.inputs={};self.results={};self.marker=None;self.details=0;self.in_ex=False;self.tables={};self.table=None;self.row=None;self.cell=None;self.points={}
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if 'id' in a:self.ids.append(a['id'])
        if tag=='h1':self.h1=True
        if tag=='article' and 'worked' in a.get('class','').split():self.worked.append(a['id'])
        if tag=='ol' and 'exercises' in a.get('class','').split():self.in_ex=True
        if tag=='li' and self.in_ex:self.exercises.append(a['id'])
        if tag=='details' and 'solutions' in a.get('class','').split():self.details+=1
        if 'data-solution-for' in a:need(self.details>0,'answer outside solution wrapper');self.answers.append(a['data-solution-for'])
        if 'data-source' in a:self.sources.append((a['data-source'],a['href']))
        for k,d in [('data-input',self.inputs),('data-result',self.results)]:
            if k in a:need(a[k] not in d,'duplicate marker');d[a[k]]='';self.marker=(d,a[k])
        if tag=='table':self.table=a.get('id');self.tables[self.table]=[]
        if tag=='tr' and self.table:self.row=[]
        if tag in ('td','th') and self.row is not None:self.cell=''
        if 'data-points' in a:self.points.setdefault(self.table,[]).append(int(a['data-points']))
    def handle_endtag(self,tag):
        if tag=='span':self.marker=None
        if tag=='ol':self.in_ex=False
        if tag=='details' and self.details:self.details-=1
        if tag in ('th','td') and self.cell is not None:self.row.append(self.cell.strip());self.cell=None
        if tag=='tr' and self.row is not None:self.tables[self.table].append(self.row);self.row=None
        if tag=='table':self.table=None
    def handle_data(self,text):
        if self.marker:self.marker[0][self.marker[1]]+=text
        if self.cell is not None:self.cell+=text



def parse(text):
    def walk(node):
        if isinstance(node,ast.Tuple):return tuple(walk(x) for x in node.elts)
        if isinstance(node,ast.Constant) and type(node.value) in (int,float):return F(str(node.value))
        if isinstance(node,ast.UnaryOp) and isinstance(node.op,ast.USub):return -walk(node.operand)
        if isinstance(node,ast.BinOp) and isinstance(node.op,ast.Div):return walk(node.left)/walk(node.right)
        raise ValueError('unsupported exact literal')
    return walk(ast.parse(text.replace('−','-'),mode='eval').body)
def vector(x,n=None):
    need(type(x) is tuple and (n is None or len(x)==n) and len(x)>0 and all(type(t) in (int,F) for t in x),'exact nonempty vector')
    return tuple(F(t) for t in x)

def alter(data,index,value):
    out=list(data);out[index]=F(value);return tuple(out)
def academic(data):
    unrestricted,grant,fixed,floor,staff,alpha,beta,rtarget,ttarget=vector(data,9)
    need(min(unrestricted,grant,fixed,floor,staff)>=0 and min(alpha,beta,rtarget,ttarget)>0,'academic domain')
    budget=unrestricted-fixed-floor
    if budget<0:return None
    a=(rtarget/alpha)**2;b=(ttarget/beta)**2
    # Eliminate x on the total-effort frontier. Compare its endpoints and the kink of min(x/a,y/b).
    ceiling=min(staff,budget+grant);ymax=min(budget,ceiling);balanced_y=ceiling*b/(a+b)
    ys={F(0),ymax,min(ymax,balanced_y)}
    best=max(min((ceiling-y)/a,y/b) for y in ys)
    x=a*best;y=b*best;usedgrant=min(x,grant);unrestrictedclose=unrestricted-fixed-(x-usedgrant)-y;grantclose=grant-usedgrant
    return {'B':budget,'a':a,'b':b,'u':best,'x':x,'y':y,'U':unrestrictedclose,'G':grantclose,'total':unrestrictedclose+grantclose,'unused':staff-x-y,'ceiling':ceiling}
def actions(rows):
    out={}
    for row in rows:
        k=row[0].split(':')[0];vals=tuple(F(x) for x in row[1:]);need(len(vals)==5 and vals[0]>=0,'action primitive')
        need(vals[1]-vals[0]==vals[3] and vals[2]-vals[0]==vals[4],'net payoff table');out[k]=vals[:3]
    return out
def path(finance,fee,action,state):
    cash,other,liab,equity,training,cf,ef=vector(finance,7);fee,=vector((fee,),1);setup,gain_g,gain_b=vector(action,3)
    need(min(cash,other,liab,equity,training,cf,ef,fee,setup)>=0 and cash+other==liab+equity and state in (0,1),'financial domain')
    steps=[(cash,equity)]
    for expense in (training,fee,setup):cash-=expense;equity-=expense;steps.append((cash,equity))
    gain=(gain_g,gain_b)[state];cash+=gain;equity+=gain;steps.append((cash,equity))
    for c,e in steps:need(c+other==liab+e,'transaction identity')
    return tuple(steps),all(c>=cf and e>=ef for c,e in steps)
def policy(finance,acts,signal):
    p,hit,false,fee=vector(signal,4);need(0<=p<=1 and 0<=hit<=1 and 0<=false<=1 and fee>=0,'signal domain')
    joint=(p*hit,(1-p)*false,p*(1-hit),(1-p)*(1-false));masses=(joint[0]+joint[1],joint[2]+joint[3]);post=tuple(joint[2*i]/mass if mass else None for i,mass in enumerate(masses))
    scores={};ledgers={}
    for pair in product(acts,repeat=2):
        total=F(0);feasible=True;rows=[]
        for j,mass in enumerate(joint):
            action=acts[pair[j//2]];steps,valid=path(finance,fee,action,j%2)
            if mass and not valid:feasible=False
            total+=mass*(steps[-1][1]-(finance[3]-finance[4]));rows.append(steps[-1])
        if feasible:scores[''.join(pair)]=total;ledgers[''.join(pair)]=tuple(rows)
    skip={}
    for key,action in acts.items():
        total=F(0);valid=True
        for state,mass in enumerate((p,1-p)):
            steps,ok=path(finance,0,action,state)
            if mass and not ok:valid=False
            total+=mass*(steps[-1][1]-(finance[3]-finance[4]))
        if valid:skip[key]=total
    return {'joint':joint,'masses':masses,'post':post,'scores':scores,'ledgers':ledgers,'skip':skip}
def resource_tuple(z):return tuple(z[k] for k in ('u','x','y','U','G','total','unused'))

def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1];start={p:digest(root/p) for p in FILES}
    review=json.loads((root/FILES[5]).read_text());need(set(review['payloads'])==set(FILES[:5]),'five nonself bindings')
    for p,b in review['payloads'].items():need(start[p]==b,'peer binding '+p)
    ar=json.loads((root/FILES[3]).read_text())
    for p,b in ar['payloads'].items():need(start[p]==b,'author binding '+p)
    page=Page();page.feed((root/FILES[0]).read_text());sources=json.loads((root/FILES[2]).read_text());tasks=['v18-c12-e'+str(i) for i in range(1,9)]
    need(not page.h1 and len(page.ids)==len(set(page.ids)) and page.exercises==page.answers==tasks,'actual task/answer/structure')
    need(page.worked==['v18-c12-case1','v18-c12-case2'],'complete dossiers')
    need(set(page.sources)=={(s['id'],s['url']) for s in sources['sources']},'source URLs')
    inputs={k:parse(v) for k,v in page.inputs.items()};shown={k:parse(v) for k,v in page.results.items()};need(set(inputs)=={'academic','finance','signal'},'all input groups')
    data=inputs['academic'];finance=inputs['finance'];signal=inputs['signal'];z=academic(data);act=actions(page.tables['v18-c12-actions'][1:]);need(tuple(act)==('H','C','F'),'action order');count=0
    need(z['x']==4 and z['y']==9,'baseline mission allocations');count+=2
    # Squared indices recover exact displayed positive output levels without invoking a floating square root.
    expected={'academic-choice':tuple(z[k] for k in ('B','a','b','u','x','y'))+(F(4),F(3))}
    need(data[5]**2*z['x']==4**2 and data[6]**2*z['y']==3**2,'positive output squares');count+=2
    ledgers=((data[0],data[2],max(z['x']-data[1],0),z['y'],z['U']),(data[1],F(0),min(z['x'],data[1]),F(0),z['G']))
    total=tuple(sum(row[i] for row in ledgers) for i in range(5));ledgers+=(total,)
    for row,calc in zip(page.tables['v18-c12-academic-ledger'][1:],ledgers):need(tuple(F(x) for x in row[1:])==calc,'complete academic ledger');count+=5
    model=policy(finance,act,signal);need(set(model['scores'])=={'HH','CH','HC','CC'} and max(model['scores'],key=model['scores'].get)=='CH','feasible optimal policy');count+=2
    need(model['skip']=={'H':0,'C':-1},'no-test actions and values');count+=2
    joint=model['joint'];terminal=model['ledgers']['CH'];mean_cash=sum(p*x[0] for p,x in zip(joint,terminal));mean_equity=sum(p*x[1] for p,x in zip(joint,terminal));other=finance[1]
    expected.update({'joint':joint,'policy-value':model['scores']['CH'],'policy-menu':tuple(model['scores'][k] for k in ('HH','CH','HC','CC')),'finance-ledger':(mean_cash,mean_equity,mean_cash+other,min(x[0] for x in terminal),min(x[1] for x in terminal))})
    for index,row in enumerate(page.tables['v18-c12-terminal'][1:]):
        c,e=terminal[index];need(F(row[1])==joint[index] and row[2]=='CH'[index//2] and tuple(F(x) for x in row[3:])==(c,c+other,e),'complete supported terminal row');count+=5
    highstaff=academic(alter(data,4,16));xmin=highstaff['a']*highstaff['u'];y=highstaff['b']*highstaff['u'];xmax=min(F(16)-y,highstaff['B']+data[1]-y)
    expected['extra-staff']=(highstaff['u'],xmin,xmax,y,highstaff['unused'])
    nogrant=academic(alter(data,1,0));highfloor=academic(alter(data,3,12));expected['resource-changes']=(resource_tuple(nogrant),resource_tuple(highfloor))
    target=academic(alter(data,7,6));expected['new-target']=resource_tuple(target)[:-1]
    fee0=policy(finance,act,alter(signal,3,0));threshold=fee0['scores']['CH'];atfee=policy(finance,act,alter(signal,3,threshold));rows=atfee['ledgers']['CH'];expected['fee-boundary']=(threshold,min(x[1] for x in rows),min(x[0] for x in rows))
    noinfo=policy(finance,act,(signal[0],F(1,2),F(1,2),signal[3]));tight=alter(finance,6,12);tightresult=policy(tight,act,signal)
    need(tightresult['scores']=={'HH':-signal[3]} and tightresult['skip']=={'H':0,'C':-1},'fee removes capped action');count+=2
    plainbad,_=path(tight,0,act['C'],1);feebad,_=path(tight,signal[3],act['C'],1)
    expected['changed-decisions']=noinfo['post']+(max(noinfo['scores'].values()),max(noinfo['skip'].values()),plainbad[-1][1],feebad[-1][1])
    greaterbudget=academic(alter(data,0,data[0]+3));expected['retention']=(greaterbudget['u'],greaterbudget['x'],greaterbudget['y'],greaterbudget['B']-(max(greaterbudget['x']-data[1],0)+greaterbudget['y']))+terminal[1]
    need(set(expected)==set(shown),'all result groups')
    def leaves(v):return sum(leaves(x) for x in v) if isinstance(v,tuple) else 1
    for key,value in expected.items():need(value==shown[key],'displayed '+key);count+=leaves(value)
    # Resource frontier worlds separately reconstruct the three-bound certificate and verify sampled feasible points.
    academic_worlds=0
    for grant,staff,budget in product((F(0),F(6),F(10)),(F(0),F(13),F(16)),(F(0),F(7),F(9),F(12))):
        dd=alter(alter(alter(data,1,grant),4,staff),0,data[2]+data[3]+budget);zz=academic(dd);academic_worlds+=1
        a,b=zz['a'],zz['b'];certificate=min(staff/(a+b),budget/b,(budget+grant)/(a+b))
        need(zz['u']==certificate and max(zz['x']-grant,0)+zz['y']<=budget and zz['x']+zz['y']<=staff,'resource certificate');count+=3
        for i,j in product(range(5),repeat=2):
            x=staff*i/4;y=staff*j/4
            if x+y<=staff and max(x-grant,0)+y<=budget:
                need(min(x/a,y/b)<=zz['u'],'global feasible witness');count+=1
    need(academic(alter(data,0,14)) is None,'unfunded fixed obligation');count+=1
    # Full primary solution interval and secondary uniqueness under higher staff.
    for x in (F(4),F(5),F(6)):
        need(min(x/4,F(9,9))==1 and max(x-6,0)+9<=9 and x+9<=16 and x+9>=13,'primary plateau');count+=4
    finance_worlds=0
    for fee,floor,likelihood in product((F(0),F(1,2),F(7,10),F(2)),(F(8),F(12)),((F(4,5),F(1,5)),(F(1,2),F(1,2)),(F(1),F(0)))):
        fdata=alter(finance,6,floor);sg=(signal[0],)+likelihood+(fee,);pm=policy(fdata,act,sg);finance_worlds+=1
        need(bool(pm['scores']) and bool(pm['skip']),'hold feasible');count+=1
        # Independent posterior branch maximization, then compare with exhaustive world-by-world policies.
        branchsum=-fee
        for branch,mass in enumerate(pm['masses']):
            if not mass:continue
            candidates=[]
            for action in act.values():
                score=F(0);feasible=True
                for state in (0,1):
                    prob=pm['joint'][2*branch+state]/mass;steps,ok=path(fdata,fee,action,state)
                    if prob and not ok:feasible=False
                    score+=prob*((action[1],action[2])[state]-action[0])
                if feasible:candidates.append(score)
            branchsum+=mass*max(candidates)
        need(branchsum==max(pm['scores'].values()),'posterior branch and full policy equivalence');count+=1
        if floor==8 and likelihood==(F(4,5),F(1,5)):
            need(set(pm['scores'])=={'HH','CH','HC','CC'} and ((max(pm['scores'].values())>=max(pm['skip'].values()))==(fee<=threshold)),'constant-menu fee rule');count+=2
    # Degenerate signals: no posterior assigned to impossible observations, no unsupported adverse state veto.
    for prior in (F(0),F(1)):
        pm=policy(finance,act,(prior,F(1),F(0),F(1,2)));need(pm['masses'].count(0)==1 and pm['post'].count(None)==1,'zero-probability branch');count+=2
    perfect=policy(finance,act,(F(1,2),F(1),F(0),F(1,2)));need('FH' in perfect['scores'] and max(perfect['scores'],key=perfect['scores'].get)=='FH','perfect signal changes supported menu');count+=2
    invalid=0
    bad=[lambda:academic(alter(data,1,-1)),lambda:academic(alter(data,4,-1)),lambda:academic(alter(data,5,0)),lambda:academic(alter(data,7,0)),lambda:academic((True,)+data[1:]),lambda:policy(finance,act,alter(signal,0,2)),lambda:policy(finance,act,alter(signal,1,-1)),lambda:policy(finance,act,alter(signal,3,-1)),lambda:path(alter(finance,3,19),0,act['H'],0),lambda:path(finance,0,act['H'],2),lambda:path(finance,-1,act['H'],0),lambda:parse('(1,"wrong")')]
    for fn in bad:
        try:fn()
        except ValueError:invalid+=1
        else:raise ValueError('invalid domain accepted')
    need(start=={p:digest(root/p) for p in FILES},'runtime mutation')
    out={'chapter':'v18-c12','status':'passed','runtime_files':6,'worked_dossiers':2,'exercises':8,'result_groups':len(shown),'comparisons':count,'academic_worlds':academic_worlds,'finance_worlds':finance_worlds,'policies_per_finance_world':9,'invalid_domains':invalid,'scope':'Independent effort-frontier and supported-state transaction oracle; complete qualitative/proof review separate; author checker opaque; actual research/teaching/leadership unobserved.'}
    json.dumps(out,allow_nan=False);return out
if __name__=='__main__':
    need(len(sys.argv)<=2,'usage: check_v18_c12_peer_working.py [book-root]');check(sys.argv[1] if len(sys.argv)==2 else None)
