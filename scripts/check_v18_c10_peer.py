"""Independent C10 peer oracle: affine envelopes, branch posteriors and endpoint regret."""
from pathlib import Path
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
import ast
import json
FILES=('content/chapters/v18-c10.html','scripts/check_v18_c10.py','content/reviews/v18-c10-sources.json','content/reviews/v18-c10-author.json','scripts/check_v18_c10_peer.py','content/reviews/v18-c10-peer.json')
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





def losses(actions,p):
    p=F(p);require(0<=p<=1,'probability domain')
    return {k:s+(v-s)*p for k,(s,v,c,t) in actions.items()}


def feasible(actions,cash,minute,deadline,reserve=0):
    require(min(cash,minute,deadline,reserve)>=0 and reserve<=cash,'valid available cash/time/reserve')
    require(actions and all(min(row)>=0 and len(row)==4 for row in actions.values()),'nonnegative complete action data')
    return {k:v for k,v in actions.items() if v[2]<=cash-reserve and minute+v[3]<=deadline}


def minimum(actions,p):
    require(bool(actions),'nonempty feasible menu');v=losses(actions,p);low=min(v.values())
    return low,tuple(k for k in v if v[k]==low)


def signal_policy(actions,p,lp,ls,fee=1,cash=13,minute=10,deadline=30):
    p,lp,ls,fee,cash=map(F,(p,lp,ls,fee,cash));require(all(0<=q<=1 for q in (p,lp,ls)) and 0<=fee<=cash,'valid diagnostic domain/funding')
    menu=feasible(actions,cash-fee,minute,deadline);require(menu,'no response fits after diagnosis')
    branches=[];gross=F(0);expected=fee;maximum=fee
    for likelihoodP,likelihoodS in ((lp,ls),(1-lp,1-ls)):
        adverse=p*likelihoodP;normal=(1-p)*likelihoodS;mass=adverse+normal
        if not mass:branches.append((mass,None,(),F(0)));continue
        posterior=adverse/mass;value,ties=minimum(menu,posterior);chosen=ties[0]
        branches.append((mass,posterior,ties,value));gross+=mass*value;expected+=mass*menu[chosen][2];maximum=max(maximum,fee+menu[chosen][2])
    return tuple(branches),gross,gross+fee,expected,maximum


def robust(actions,lo,hi):
    lo,hi=F(lo),F(hi);require(0<=lo<=hi<=1 and actions,'ordered probability interval/nonempty menu')
    endpoints=[losses(actions,p) for p in (lo,hi)]
    worst={k:max(v[k] for v in endpoints) for k in actions}
    regret={k:max(v[k]-min(v.values()) for v in endpoints) for k in actions}
    return worst,regret


def audit(d):
    count=0
    def eq(a,b,label):
        nonlocal count
        require(a==b,label);count+=1
    def yes(ok,label):
        nonlocal count
        require(ok,label);count+=1
    academic={r[0][0]:tuple(numeric(x) for x in r[1:]) for r in d.rows if len(r)==5 and r[0] in ('W — wait for platform','M — phased manual contingency','B — full backup assessment')}
    financial={r[0][0]:tuple(numeric(x) for x in r[1:]) for r in d.rows if len(r)==5 and r[0] in ('R — retain original route','A — verified alternate route','H — hold for controlled later processing')}
    eq(academic,{'W':(0,48,0,0),'M':(6,22,6,10),'B':(12,12,12,15)},'actual academic action table')
    eq(financial,{'R':(0,20,0,0),'A':(6,6,6,5),'H':(9,9,0,0)},'actual financial action table')
    inp={k:numeric(v) for k,v in d.inputs.items()}
    eq(inp,{'academic-resources':(13,300,2,150,30),'diagnostic':(F(1,4),F(3,4),F(1,4),1,10),'financial-resources':(F(1,10),F(2,5),8,2,15),'financial-flow-timing':(3,3,8,11)},'all visible primitive inputs')
    cash,roster,rooms,seats,deadline=inp['academic-resources'];p,lp,ls,fee,release=inp['diagnostic'];lo,hi,fcash,reserve,fdeadline=inp['financial-resources'];payment,receipt,arrival,late=inp['financial-flow-timing']
    pri=losses(academic,p);prior=min(pri.values());policy=signal_policy(academic,p,lp,ls,fee,cash,release,deadline);branches,gross,net,ec,mc=policy
    perfect=(1-p)*minimum(academic,0)[0]+p*minimum(academic,1)[0]
    worst,regret=robust(financial,lo,hi);noA={k:v for k,v in financial.items() if k!='A'};changed=robust(noA,lo,F(3,5));non=signal_policy(academic,p,F(1,2),F(1,2));t20=signal_policy(academic,p,lp,ls,minute=20);t25=signal_policy(academic,p,lp,ls,minute=25);ret=signal_policy(academic,F(1,2),lp,ls);rw,rr=robust(financial,lo,F(3,10))
    wrong=p*lp**2/(p*lp**2+(1-p)*ls**2)
    want={'academic-prior-losses':tuple(pri.values()),'diagnostic-policy':(branches[0][0],branches[0][1],branches[1][1],gross,net,prior-net),'diagnostic-cash':(ec,mc),'financial-worst':tuple(worst.values()),'financial-regrets':tuple(regret.values()),'financial-cash':(fcash,fcash-payment,fcash-payment+receipt,fcash-payment+receipt-financial['A'][2]),'academic-boundaries':tuple(tuple(losses(academic,q).values()) for q in (F(3,16),F(3,8))),'information-limits':(perfect,prior-perfect,prior-gross,prior-gross,cash-academic['B'][2]),'fee-reoptimization':(cash-academic['B'][2],prior-t20[1]),'noninformation':(non[0][0][1],non[0][1][1],non[2],branches[0][1],wrong),'late-diagnostics':(t20[1],t20[2],t25[1],t25[2]),'receipt-control':(fcash-payment+receipt-6,fcash-payment+2*receipt-6,late+financial['A'][3]),'changed-interval':(tuple(changed[0].values()),tuple(changed[1].values()),F(9,20)),'retention':((ret[0][0][0],ret[0][0][1],ret[0][1][1],ret[1],ret[2]),tuple(rw.values()),tuple(rr.values()))}
    eq(set(want),set(d.results),'all result groups')
    for k,v in want.items():eq(numeric(d.results[k]),v,'displayed '+k)
    eq(rooms*seats,roster,'actual accessible capacity')
    eq((10+15,28-10,28-(10+15),30-28),(25,18,3,2),'planned/actual readiness and remaining slack')
    eq((arrival+5,14-(arrival+5),fdeadline-14),(13,1,1),'financial actual completion timing')
    eq(tuple(b[2] for b in branches),(('B',),('W',)),'actual diagnostic policy')
    # All affine pair crossings and intervals, including the dominated W/B crossing.
    crossings={F(0),F(1)};keys=list(academic)
    for i,k in enumerate(keys):
        for j in keys[i+1:]:
            a,b=academic[k],academic[j];slope=(a[1]-a[0])-(b[1]-b[0])
            if slope:
                cross=(b[0]-a[0])/slope
                if 0<=cross<=1:crossings.add(cross)
    eq(tuple(sorted(crossings)),(0,F(3,16),F(1,4),F(3,8),1),'all line crossings derived')
    for q,optimal in ((0,('W',)),(F(3,32),('W',)),(F(3,16),('W','M')),(F(7,32),('M',)),(F(1,4),('M',)),(F(5,16),('M',)),(F(3,8),('M','B')),(F(11,16),('B',)),(1,('B',))):eq(minimum(academic,q)[1],optimal,'full lower-envelope interval and ties')
    eq(minimum(academic,p)[1],('M',),'no-test recommendation')
    # Fee boundaries endogenously change which actions can be selected.
    fee_worlds=0
    for k in (F(0),F(1,2),F(1),F(101,100),F(7,4),F(9,5),F(5,2),F(7),F(701,100),F(13)):
        got=signal_policy(academic,p,lp,ls,fee=k);fee_worlds+=1
        expectedgross=F(15,2) if k<=1 else F(33,4) if k<=7 else F(12)
        eq(got[1],expectedgross,'funded lower-envelope branch value')
        eq(got[2]<=prior,k<=F(7,4),'globally worthwhile funded fee ceiling')
        yes(got[4]<=cash,'every branch funded after fee')
    eq(signal_policy(academic,p,lp,ls,fee=F(5,2),cash=100)[2],prior,'unchanged-menu economic fee equality')
    eq((set(feasible(academic,12,20,30)),set(feasible(academic,12,25,30))),({'W','M'},{'W'}),'late diagnostic removes setup actions')
    eq((t20[4],t25[4]),(7,1),'late policy maximum cash')
    probability_worlds=0
    for priorp in (F(0),F(1,10),F(1,4),F(1,2),F(1)):
        for a,b in ((F(3,4),F(1,4)),(F(1,2),F(1,2)),(F(1),F(0)),(F(0),F(0))):
            got=signal_policy(academic,priorp,a,b,fee=0);probability_worlds+=1
            eq(sum(z[0] for z in got[0]),1,'signal masses exhaustive')
            eq(sum(z[0]*(z[1] if z[1] is not None else 0) for z in got[0]),priorp,'posterior weighted mean')
            yes(got[1]<=minimum(academic,priorp)[0],'free ignore-able information cannot worsen same-menu decision')
            for mass,posterior,ties,value in got[0]:
                if mass:
                    for action,row in academic.items():yes(value<=row[0]+(row[1]-row[0])*posterior,'branch global action domination')
    eq(min(worst,key=worst.get),'A','worst expected loss criterion')
    eq(min(regret,key=regret.get),'R','minimax regret criterion')
    interval_worlds=0
    for menu,low,high in ((financial,lo,hi),(noA,lo,hi),(noA,lo,F(3,5)),(financial,lo,F(3,10)),(noA,lo,F(9,20))):
        w,g=robust(menu,low,high)
        for j in range(9):
            q=low+(high-low)*F(j,8);v=losses(menu,q);interval_worlds+=1
            for action in menu:
                yes(v[action]<=w[action],'affine loss no interior maximum above endpoint')
                yes(v[action]-min(v.values())<=g[action],'convex regret endpoint certificate')
    eq(robust(noA,lo,F(9,20))[0],{'R':9,'H':9},'fallback exact threshold tie')
    for upper in (lo,F(2,5),F(9,20),F(3,5),F(1)):
        w,_=robust(noA,lo,upper);eq(w['R']<=w['H'],upper<=F(9,20),'full fallback global threshold')
    eq(set(feasible(financial,fcash-payment,4,fdeadline,reserve)),{'R','H'},'settled payment removes alternate')
    eq(set(feasible(financial,fcash-payment+receipt,arrival,fdeadline,reserve)),{'R','A','H'},'unique settled timely receipt restores alternate')
    eq(set(feasible(financial,fcash-payment+receipt,late,fdeadline,reserve)),{'R','H'},'late receipt funds but cannot enable alternate')
    invalid=[lambda:losses(academic,-1),lambda:losses(academic,2),lambda:minimum({},F(1,2)),lambda:feasible(academic,-1,0,30),lambda:feasible(academic,1,0,30,2),lambda:signal_policy(academic,p,2,ls),lambda:signal_policy(academic,p,lp,-1),lambda:signal_policy(academic,p,lp,ls,fee=-1),lambda:signal_policy(academic,p,lp,ls,fee=14),lambda:signal_policy(academic,p,lp,ls,minute=31),lambda:robust(financial,F(1,2),F(1,4)),lambda:robust(financial,-1,1),lambda:robust({},0,1)]
    for fn in invalid:
        try:fn()
        except ValueError:pass
        else:raise ValueError('invalid domain accepted')
    return count,len(invalid),len(want),fee_worlds,probability_worlds,interval_worlds


def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    raw={f:(root/f).read_bytes() for f in FILES};peer=strict_json(raw[FILES[5]]);author=strict_json(raw[FILES[3]]);sources=strict_json(raw[FILES[2]])
    require(set(peer['payloads'])==set(FILES[:5]) and set(author['payloads'])==set(FILES[:3]),'nonself bindings')
    for rec in (author,peer):
        for f,v in rec['payloads'].items():require(v=={'bytes':len(raw[f]),'sha256':sha256(raw[f]).hexdigest()},'changed frozen file '+f)
    d=BaseManuscript();d.feed(raw[FILES[0]].decode());require(not d.stack and len(d.ids)==len(set(d.ids)),'balanced unique fragment')
    ids={f'v18-c10-ex{i}' for i in range(1,9)}
    require(set(d.prompts)==set(d.solutions)==set(peer['exact_prompt_review'])==ids and d.worked==['v18-c10-case1','v18-c10-case2'],'eight pairs/two complete cases')
    for k,v in peer['exact_prompt_review'].items():require(v['prompt_sha256']==sha256(d.prompts[k].encode()).hexdigest() and v['solution_sha256']==sha256(d.solutions[k].encode()).hexdigest(),'reviewed exact pair changed')
    routes={'v18-c10-cdc-communication':'https://www.cdc.gov/field-epi-manual/php/chapters/communicating-investigation.html','v18-c10-nist-response':'https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-61r3.pdf'}
    require(d.sources==routes=={s['id']:s['url'] for s in sources['sources']},'exact scoped source routes')
    require(all(s['actual_inspector']=='v16_c01_author' for s in sources['sources']),'source inspector preserved')
    require({a for a in d.links if not a.startswith('https://')}=={'curriculum.html#v18-c09','v15-c12.html','curriculum.html#v18-c11'},'chapter routes')
    comparisons,invalid,groups,fees,probabilities,intervals=audit(d)
    return {'chapter':'v18-c10','status':'passed','review':'independent internal peer','runtime_files':6,'worked_artifacts':2,'prompts':8,'solutions':8,'numeric_groups':groups,'comparisons':comparisons,'invalid_domains':invalid,'fee_worlds':fees,'probability_worlds':probabilities,'interval_worlds':intervals,'source_routes':2,'author_checker':'opaque hash only; never read as text/imported/executed','scope':'Full contingent-decision/global proofs, dated incidents and communication/after-action artifacts, eight exact answers and bounded sources read; no real drill or human leadership competence certified.'}


if __name__=='__main__':
    check()
