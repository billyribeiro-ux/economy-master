"""V18C10 crisis author checks; full artifact and proof review is separate."""
from pathlib import Path
from fractions import Fraction as F
from html.parser import HTMLParser
from itertools import product, combinations
import hashlib,json,sys,ast,math
FILES=('content/chapters/v18-c10.html','scripts/check_v18_c10.py','content/reviews/v18-c10-sources.json','content/reviews/v18-c10-author.json')
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
        if isinstance(node,ast.Constant) and type(node.value) is int:return F(node.value)
        if isinstance(node,ast.UnaryOp) and isinstance(node.op,ast.USub):return -walk(node.operand)
        if isinstance(node,ast.BinOp) and isinstance(node.op,ast.Div):return walk(node.left)/walk(node.right)
        raise ValueError('unsupported exact literal')
    return walk(ast.parse(text.replace('−','-'),mode='eval').body)
def vector(x,n=None):
    need(type(x) is tuple and (n is None or len(x)==n) and len(x)>0 and all(type(t) in (int,F) for t in x),'exact nonempty vector')
    return tuple(F(t) for t in x)

def probability(p):
    need(type(p) in (int,F) and 0<=p<=1,'probability domain');return F(p)
def action_table(rows):
    out={}
    for row in rows:
        name=row[0].split(' — ')[0];v=tuple(F(x) for x in row[1:]);need(len(v)==4 and min(v)>=0,'action domain');out[name]=v
    return out
def losses(actions,p):
    p=probability(p);return {k:(1-p)*v[0]+p*v[1] for k,v in actions.items()}
def menu(actions,cash,fee,release,deadline,reserve=0):
    cash,fee,release,deadline,reserve=vector((cash,fee,release,deadline,reserve),5)
    need(min(cash,fee,release,deadline,reserve)>=0,'resource domain')
    return {k:v for k,v in actions.items() if fee+v[2]+reserve<=cash and release+v[3]<=deadline}
def diagnostic(actions,p,red_p,red_s,fee,release,cash,deadline):
    p=probability(p);red_p=probability(red_p);red_s=probability(red_s)
    available=menu(actions,cash,fee,release,deadline);need(bool(available),'empty menu')
    joints=((p*red_p,(1-p)*red_s),(p*(1-red_p),(1-p)*(1-red_s)))
    masses=tuple(sum(j) for j in joints);post=tuple(j[0]/m if m else None for j,m in zip(joints,masses))
    # Exhaust all complete deterministic two-branch policies directly in joint-state mass space.
    scores=[]
    for policy in product(available,repeat=2):
        loss=F(fee)+sum(j[0]*available[a][1]+j[1]*available[a][0] for j,a in zip(joints,policy))
        scores.append((loss,policy))
    best=min(x[0] for x in scores);policies=tuple(x[1] for x in scores if x[0]==best)
    branchbest=F(fee)+sum(min(j[0]*a[1]+j[1]*a[0] for a in available.values()) for j in joints)
    need(branchbest==best,'branch separability')
    policy=policies[0];expectedcash=F(fee)+sum(m*available[a][2] for m,a in zip(masses,policy));maxcash=F(fee)+max(available[a][2] for m,a in zip(masses,policy) if m)
    return {'masses':masses,'post':post,'net':best,'gross':best-fee,'policies':policies,'cash':(expectedcash,maxcash),'available':tuple(available)}
def robust(actions,lower,upper):
    lower=probability(lower);upper=probability(upper);need(lower<=upper and bool(actions),'interval/menu domain')
    ends=[losses(actions,p) for p in (lower,upper)]
    worst={a:max(e[a] for e in ends) for a in actions}
    regret={a:max(e[a]-min(e.values()) for e in ends) for a in actions}
    return worst,regret

def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    start={p:digest(root/p) for p in FILES};review=json.loads((root/FILES[3]).read_text())
    need(set(review['payloads'])==set(FILES[:3]),'three nonself bindings')
    for p,b in review['payloads'].items():need(start[p]==b,'payload '+p)
    page=Page();page.feed((root/FILES[0]).read_text());sources=json.loads((root/FILES[2]).read_text())
    need(not page.h1 and len(page.ids)==len(set(page.ids)),'unique IDs/no h1')
    tasks=['v18-c10-ex'+str(i) for i in range(1,9)];need(page.exercises==page.answers==tasks,'eight matched exercises')
    need(page.worked==['v18-c10-case1','v18-c10-case2'],'two worked cases')
    need(set(page.sources)=={(s['id'],s['url']) for s in sources['sources']},'source URLs')
    inputs={k:parse(v) for k,v in page.inputs.items()};shown={k:parse(v) for k,v in page.results.items()}
    need(set(inputs)=={'academic-resources','diagnostic','financial-resources','financial-flow-timing'},'all primitives')
    ac=action_table(page.tables['v18-c10-academic-actions'][1:]);fi=action_table(page.tables['v18-c10-financial-actions'][1:]);need(tuple(ac)==('W','M','B') and tuple(fi)==('R','A','H'),'menus')
    cash,roster,rooms,seats,deadline=vector(inputs['academic-resources'],5);need(rooms*seats>=roster,'backup capacity')
    p,rp,rs,fee,release=vector(inputs['diagnostic'],5);lo,hi,fcash,reserve,fdeadline=vector(inputs['financial-resources'],5)
    payment,receipt,arrive,late=vector(inputs['financial-flow-timing'],4)
    d=diagnostic(ac,p,rp,rs,fee,release,cash,deadline);initial=tuple(losses(ac,p).values());immediate=min(initial)
    need(d['policies']==(('B','W'),),'unique diagnostic policy')
    expected={'academic-prior-losses':initial,'diagnostic-policy':(d['masses'][0],)+d['post']+(d['gross'],d['net'],immediate-d['net']),'diagnostic-cash':d['cash']}
    w,g=robust(fi,lo,hi);expected.update({'financial-worst':tuple(w.values()),'financial-regrets':tuple(g.values()),'financial-cash':(fcash,fcash-payment,fcash-payment+receipt,fcash-payment+receipt-fi['A'][2])})
    thresholds=[]
    for a,b in [('W','M'),('M','B')]:
        va,vb=ac[a],ac[b];thresholds.append((vb[0]-va[0])/((va[1]-va[0])-(vb[1]-vb[0])))
    expected['academic-boundaries']=tuple(tuple(losses(ac,q).values()) for q in thresholds)
    perfect=(1-p)*min(v[0] for v in ac.values())+p*min(v[1] for v in ac.values())
    grossgain=immediate-d['gross'];expected['information-limits']=(perfect,immediate-perfect,grossgain,grossgain,cash-ac['B'][2])
    no=diagnostic(ac,p,F(1,2),F(1,2),fee,release,cash,deadline);wrong=p*rp**2/(p*rp**2+(1-p)*rs**2)
    expected['noninformation']=no['post']+(no['net'],d['post'][0],wrong)
    d20=diagnostic(ac,p,rp,rs,fee,F(20),cash,deadline);d25=diagnostic(ac,p,rp,rs,fee,F(25),cash,deadline)
    expected['late-diagnostics']=(d20['gross'],d20['net'],d25['gross'],d25['net'])
    expected['fee-reoptimization']=(cash-ac['B'][2],immediate-d20['gross'])
    endcash=fcash-payment+receipt-fi['A'][2];expected['receipt-control']=(endcash,endcash+receipt,late+fi['A'][3])
    rh={k:v for k,v in fi.items() if k!='A'};wc,rc=robust(rh,lo,F(3,5));boundary=(fi['H'][0]-fi['R'][0])/(fi['R'][1]-fi['R'][0]);expected['changed-interval']=(tuple(wc.values()),tuple(rc.values()),boundary)
    dt=diagnostic(ac,F(1,2),rp,rs,fee,release,cash,deadline);wt,rt=robust(fi,lo,F(3,10));expected['retention']=((dt['masses'][0],)+dt['post']+(dt['gross'],dt['net']),tuple(wt.values()),tuple(rt.values()))
    need(set(expected)==set(shown),'all displayed result groups');count=0
    def leaves(v):return sum(leaves(x) for x in v) if isinstance(v,tuple) else 1
    for key,value in expected.items():need(value==shown[key],'displayed '+key);count+=leaves(value)
    # Exact lower-envelope boundaries and adjacent interior witnesses.
    for q,optimal in [(0,{'W'}),(thresholds[0],{'W','M'}),(F(1,4),{'M'}),(thresholds[1],{'M','B'}),(1,{'B'})]:
        ls=losses(ac,q);need({k for k,v in ls.items() if v==min(ls.values())}==optimal,'threshold policy');count+=1
    worlds=0
    for q,accuracy,time,budget in product((F(0),F(1,4),F(1,2),F(1)),((F(3,4),F(1,4)),(F(1,2),F(1,2)),(F(1),F(0))),(F(10),F(20),F(25)),(F(7),F(13))):
        z=diagnostic(ac,q,*accuracy,fee,time,budget,deadline);worlds+=1
        available=menu(ac,budget,fee,time,deadline)
        # Ignore the signal: every affordable constant policy is an admissible upper bound.
        need(z['net']<=fee+min(losses(available,q).values()),'ignore-signal bound');count+=1
        need(z['cash'][1]<=budget and z['gross']>=((1-q)*min(v[0] for v in available.values())+q*min(v[1] for v in available.values())),'cash/perfect-information bounds');count+=2
        for policy in z['policies']:
            for signal,a in enumerate(policy):
                if z['masses'][signal]:need(losses(available,z['post'][signal])[a]==min(losses(available,z['post'][signal]).values()),'posterior optimal action');count+=1
    for k in (F(0),F(1),F(5,4),F(7,4),F(2),F(5,2),F(7),F(8)):
        z=diagnostic(ac,p,rp,rs,k,release,cash,deadline);need((z['net']<=immediate)==(k<=F(7,4)),'funded fee threshold');count+=1
    # Timing and cash jointly constrain financial action availability.
    need(tuple(menu(fi,fcash-payment,0,4,fdeadline,reserve))==('R','H'),'settled payment removes A');count+=1
    need(tuple(menu(fi,fcash-payment+receipt,0,arrive,fdeadline,reserve))==('R','A','H'),'actual timely receipt restores A');count+=1
    need(tuple(menu(fi,fcash-payment+receipt,0,late,fdeadline,reserve))==('R','H'),'late receipt does not restore A');count+=1
    robustworlds=0
    for acts,upper in product((fi,rh),(F(1,10),F(3,10),F(2,5),F(9,20),F(3,5),F(1))):
        worst,regret=robust(acts,lo,upper);robustworlds+=1
        for j in range(9):
            q=lo+(upper-lo)*j/8;ls=losses(acts,q)
            for a in acts:
                need(ls[a]<=worst[a] and ls[a]-min(ls.values())<=regret[a],'interval endpoint bounds');count+=2
        # Alternative pairwise-affine endpoint computation of regret.
        for a in acts:
            pairmax=max(losses(acts,q)[a]-losses(acts,q)[b] for b,q in product(acts,(lo,upper)))
            need(regret[a]==pairmax,'pairwise regret oracle');count+=1
    need([row[0] for row in page.tables['v18-c10-academic-log'][1:]]==['08:00','08:05','08:10','08:28','08:40','09:15'],'academic releases')
    need([row[0] for row in page.tables['v18-c10-financial-log'][1:]]==['09:00','09:04','09:06','09:08','09:09','09:14'],'financial releases');count+=2
    invalid=0
    bad=[lambda:probability(-1),lambda:probability(F(11,10)),lambda:probability(True),lambda:probability(.5),lambda:robust(fi,F(1,2),F(1,4)),lambda:robust({},0,1),lambda:menu(ac,-1,0,0,30),lambda:menu(ac,13,-1,0,30),lambda:menu(ac,13,0,-1,30),lambda:menu(ac,13,0,0,30,-1),lambda:diagnostic(ac,p,2,rs,fee,release,cash,deadline),lambda:diagnostic(ac,p,rp,rs,14,release,cash,deadline),lambda:vector((True,1)),lambda:parse('(1,0.5)')]
    for f in bad:
        try:f()
        except ValueError:invalid+=1
        else:raise ValueError('invalid domain accepted')
    need(start=={p:digest(root/p) for p in FILES},'runtime mutation')
    result={'chapter':'v18-c10','status':'passed','runtime_files':4,'worked_cases':2,'exercises':8,'result_groups':len(shown),'comparisons':count,'diagnostic_worlds':worlds,'robust_worlds':robustworlds,'invalid_domains':invalid,'scope':'Original fictional crisis policies and dated controls; separate full proof/artifact review. No actual emergency, legal validation or learner leadership observation.'}
    json.dumps(result,allow_nan=False);return result
if __name__=='__main__':
    need(len(sys.argv)<=2,'usage: check_v18_c10_working.py [book-root]');check(sys.argv[1] if len(sys.argv)==2 else None)
