"""Independent V18 project peer: primitive records before reader implementation."""
from pathlib import Path
from html.parser import HTMLParser
import ast,hashlib,json,sys,copy,contextlib,io,re
AUTHOR=('content/assessments/parts/v18-project.html','content/projects/v18-assessment-inputs.json','content/projects/v18-assessment-analysis.py','content/projects/v18-assessment-output.json','content/projects/v18-assessment-manifest.json','content/projects/v18-assessment-README.txt','scripts/check_v18_project.py','content/reviews/v18-project-author.json','content/reviews/v18-project-sources.json')
SELF='scripts/check_v18_project_peer.py';REVIEW='content/reviews/v18-project-peer.json';FILES=AUTHOR+(SELF,REVIEW)
from fractions import Fraction as F
from itertools import combinations

def academic(d):
 a=d['academic']; options=a['options']; rows=[]
 for n in range(4):
  for ix in combinations(range(3),n):
   selected=[options[i] for i in ix]; ids=[o['id'] for o in selected]
   U=F(a['unrestricted'])-F(a['fixed']); R=F(a['restricted']); low=min(F(a['unrestricted']),U)
   dates=sorted(set([a['grant_day']]+[o['start_day'] for o in selected]))
   trace=[(0,F(a['unrestricted']),F(a['restricted'])),(1,U,R)]
   for day in dates:
    if day==a['grant_day']: R+=F(a['grant']); trace.append((day,U,R))
    for o in sorted(selected,key=lambda o:o['id']):
     if o['start_day']==day:
      grant=min(R,F(o['cost'])) if o['grant_eligible'] else F(0)
      R-=grant; U-=F(o['cost'])-grant; low=min(low,U);trace.append((day,U,R))
   staff=sum(o['staff'] for o in selected);cost=sum(o['cost'] for o in selected)
   score=sum(o['score'] for o in selected)+(a['complementarity'] if {'R','T'}<=set(ids) else 0)
   rows.append(dict(ids=ids,cost=cost,staff=staff,score=score,low=low,U=U,R=R,feasible=staff<=a['staff'] and low>=a['floor'],trace=trace))
 feasible=[r for r in rows if r['feasible']]
 winner=min(feasible,key=lambda r:(-r['score'],r['cost'],sorted(r['ids']))) if feasible else None
 return rows,winner

def incentive(d):
 a=d['incentives'];w=F(a['salary']);rho=F(a['intrinsic_quality']);rows=[]
 for b in map(F,a['bonuses']):
  # Compare endpoints and stationary candidate via utility, independently of clipping formula.
  U=lambda e:w+b*e+rho*(1-e)-(e*e+(1-e)**2)/2
  interior=(1+b-rho)/2; candidates=[F(0),F(1)]+([interior] if 0<=interior<=1 else [])
  e=max(candidates,key=U);q=1-e;reserve=w+b+F(a['nonpay_cost'])
  gates=[e>=F(a['minimum_output']),q>=F(a['minimum_quality']),U(e)>=F(a['outside_utility']),reserve<=F(a['personnel_envelope'])]
  rows.append((b,e,q,U(e),w+b*e,reserve,all(gates)))
 return rows

def ledger(d):
 a=d['finance_opening'];c=F(a['cash']);l=F(a['liabilities']);e=F(a['equity']);other=F(a['securities'])+F(a['loans']); approvals={};spent={};seen=set();rows=[];exceptions=[]
 for event in sorted(d['events'],key=lambda t:(t['time'],t['id'])):
  k=event['kind'];v=F(event['amount']);moved=False;ex=None
  if event['status']=='observed':
   if k=='approval':approvals[event['id']]=(event['time'],v)
   if k=='debt_payment':c-=v;l-=v;moved=True
   if k=='expense':
    aid=event['approval'];valid=aid in approvals and approvals[aid][0]<event['time'] and spent.get(aid,0)+v<=approvals[aid][1]
    if not valid:ex=event['id'];exceptions.append(ex)
    else:spent[aid]=spent.get(aid,0)+v
    c-=v;e-=v;moved=True
   if k=='income' and event['reference'] not in seen:
    seen.add(event['reference']);c+=v;e+=v;moved=True
  rows.append((event['id'],c,c+other,l,e,moved,c>=a['cash_floor'],e>=a['equity_floor'],ex))
 return rows,exceptions

def crisis(d):
 out=[];c=d['crisis'];f=d['finance_opening']
 for r in c['releases']:
  choices=[]
  for a in c['actions']:
   gates=(F(r['cash'])-F(a['cost'])>=F(f['cash_floor']),F(r['equity'])-F(a['cost'])>=F(f['equity_floor']),a['staff']<=c['staff'],r['minute']+a['minutes']<=c['deadline'],not a['requires_approval'] or a['id'] in r['approved'])
   choices.append((a['id'],gates,a['loss']))
  feasible=[t for t in choices if all(t[1])]
  winner=min(feasible,key=lambda t:(t[2],t[0]))[0] if feasible else None
  out.append((r['id'],choices,winner))
 return out

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
        if t=='li' and 'data-points' in a:self.tasks.append((a['id'],int(a['data-points'])))
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

def decode(v):
    if isinstance(v,list):return tuple(decode(x) for x in v)
    if isinstance(v,dict):return {k:decode(x) for k,x in v.items()}
    if type(v)is int:return F(v)
    if isinstance(v,str) and re.fullmatch(r'-?\d+(?:/\d+)?',v):return F(v)
    return v

def audit(data,reader):
    # Oracle constructed independently from input records before reading reader code.
    snapshot=copy.deepcopy(data);quiet=io.StringIO()
    with contextlib.redirect_stdout(quiet),contextlib.redirect_stderr(quiet):out=reader['run'](data)
    need(quiet.getvalue()=='' and data==snapshot,'quiet pure reader');json.dumps(out,allow_nan=False)
    got=decode(out);count=0
    def eq(x,y,label):
        nonlocal count
        need(x==y,label+': '+str((x,y)));count+=1
    ar,best=academic(data);table={r['bundle']:r for r in got['academic']['options']}
    for r in ar:
        name='+'.join(r['ids']) or 'none';g=table[name]
        for k,v in [('cost',r['cost']),('staff',r['staff']),('score',r['score']),('minimum_unrestricted',r['low']),('closing_unrestricted',r['U']),('closing_restricted',r['R']),('feasible',r['feasible'])]:eq(g[k],v,'academic '+name+' '+k)
        why=[]
        if r['staff']>data['academic']['staff']:why.append('staff_capacity')
        if r['low']<data['academic']['floor']:why.append('dated_unrestricted_floor')
        eq(g['diagnostics'],tuple(why),'resource causes')
        # Every dated balance, allowing reader's explicit fixed-day-zero convention.
        eq(tuple((x['unrestricted'],x['restricted']) for x in g['timeline']),tuple((x[1],x[2]) for x in r['trace'][1:]),'dated fund balances')
    eq(got['academic']['selected'],'+'.join(best['ids']) or 'none' if best else None,'selected bundle')
    for predicted,actual in zip(incentive(data),got['people']['contracts']):
        eq(tuple(actual[k] for k in ('bonus','effort','quality','utility','actual_pay','maximum_reserved_cost','feasible')),predicted,'global utility maximum')
    for p,g in zip(data['candidates'],got['people']['candidates']):
        known=sum(x or 0 for x in p['ratings']);missing=p['submitted'].count(False)
        eq(g['possible_equal_weight_score'],(F(known,2),F(known+10*missing,2)),'candidate bounds');eq(g['eligible'],missing==0,'candidate eligibility')
    v=data['vote'];n=len(v['present']);majority=next(k for k in range(n+2) if 2*k>n)
    eq(tuple(got['governance'][k] for k in ('eligible_members','present','yes','required_yes','quorum','approved')),(len(set(v['members'])-set(v['interested'])),n,len(v['yes']),majority,v['quorum'],n>=v['quorum'] and len(v['yes'])>=majority),'vote separate thresholds')
    lr,exceptions=ledger(data)
    for r,g in zip(lr,got['finance']['events']):
        eq(tuple(g[k] for k in ('id','cash','assets','liabilities','equity','booked_cash_effect')),r[:6],'event ledger')
        eq(g['assets'],g['liabilities']+g['equity'],'balance identity')
        eq('cash_floor' in g['diagnostics'],not r[6],'cash floor');eq('equity_floor' in g['diagnostics'],not r[7],'equity floor')
        eq('expense_without_sufficient_prior_approval' in g['diagnostics'],r[8] is not None,'authority exception')
    eq(tuple(got['finance']['closing'][k] for k in ('cash','assets','liabilities','equity')),lr[-1][1:5],'closing ledger')
    eq(tuple(x['event'] for x in got['finance']['exceptions'] if x['reason']=='expense_without_sufficient_prior_approval'),tuple(exceptions),'all control exceptions')
    for (rid,choices,winner),g in zip(crisis(data),got['crisis']):
        eq(g['selected'],winner,'crisis minimum')
        for (aid,gates,loss),a in zip(choices,g['actions']):
            eq(a['feasible'],all(gates),'action all gates');eq(a['loss'],loss,'loss includes expense')
            eq(a['diagnostics'],tuple(k for k,b in zip(('cash_floor','equity_floor','staff_capacity','setup_deadline','approval_missing'),gates) if not b),'crisis reasons')
    for status in ('observed_in_fiction','missing','proposed'):eq(got['evidence'][status],tuple(r['id'] for r in data['actual_records'] if r['status']==status),'evidence status')
    eq(got['evidence']['actual_learner_achievement'],'not supplied','no actual achievement')
    eq(got['scoring']['total'],100,'rubric total')
    return out,count

def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    review=json.loads((root/REVIEW).read_text());need(set(review['payloads'])==set(FILES)-{REVIEW},'ten nonself bindings')
    for name,expected in review['payloads'].items():need(digest(root/name)==expected,'bound payload '+name)
    sources=json.loads((root/AUTHOR[8]).read_text());page=Page();page.feed((root/AUTHOR[0]).read_text());need(not page.stack and page.h1==0,'HTML structure')
    tasks=[('project-task-'+str(i),p) for i,p in enumerate((10,10,20,20,20,10,10),1)];need(page.tasks==tasks and page.answers==[t[0] for t in tasks],'seven paired tasks')
    need(all(len(page.answertext[t])>500 for t,_ in tasks),'full artifacts');need(page.sources=={s['id']:s['url'] for s in sources['sources']},'bounded sources')
    data=json.loads((root/AUTHOR[1]).read_text());expected=json.loads((root/AUTHOR[3]).read_text())
    reader={'__name__':'peer_loaded_reader','__file__':str(root/AUTHOR[2])};q=io.StringIO()
    with contextlib.redirect_stdout(q),contextlib.redirect_stderr(q):exec(compile((root/AUTHOR[2]).read_text(),str(root/AUTHOR[2]),'exec'),reader)
    need(q.getvalue()=='','quiet module load');out,count=audit(data,reader);need(out==expected,'entire expected strictJSON output')
    need(literal(page.inputs['academic'])==tuple(map(F,(50,0,30,8,16,10,5,10))),'HTML academic primitives')
    need(literal(page.inputs['finance'])==tuple(map(F,(40,60,100,170,30,10,18))),'HTML financial primitives')
    need(literal(page.inputs['incentives'])==tuple(map(F,(4,'1/2',4,'1/2','2/5',6,'1/2'))),'HTML incentives')
    need(literal(page.results['closing'])==tuple(decode(out)['finance']['closing'][k] for k in ('cash','assets','liabilities','equity')),'HTML closing')
    need(literal(page.results['effort'])==tuple(x[1:6] for x in incentive(data)),'HTML effort');need(literal(page.results['vote'])==(5,4,3,3,4),'HTML vote');need(literal(page.results['task-points'])==tuple(p for _,p in tasks),'HTML scoring')
    # Compare full supplied menu and financial solution tables, rather than only anchors.
    menu=next(t for t in page.tables if t[0]==['Bundle','Cost','Staff','Score','Minimum unrestricted','Feasible?'])
    oracle_rows={'+'.join(r['ids']) or 'none':r for r in academic(data)[0]}
    for row in menu[1:]:
        r=oracle_rows[row[0]];need(tuple(map(F,row[1:5]))==(r['cost'],r['staff'],r['score'],r['low']) and (row[5]=='yes')==r['feasible'],'HTML full option row');count+=1
    table=next(t for t in page.tables if t[0]==['Event','Cash','Assets','Liabilities','Equity','Cash moved?'])
    for row,r in zip(table[1:],ledger(data)[0]):need(row[0]==r[0] and tuple(map(F,row[1:5]))==r[1:5] and (row[5]=='yes')==r[5],'HTML every ledger row');count+=1
    manifest=json.loads((root/AUTHOR[4]).read_text());need(set(manifest['payloads'])=={Path(AUTHOR[i]).name for i in (1,2,3,5)},'four reader bindings')
    for name,binding in manifest['payloads'].items():need(digest(root/'content/projects'/name)==binding,'reader manifest '+name)
    variants=[]
    for day in (2,6,7):
        d=copy.deepcopy(data);d['academic']['grant_day']=day;variants.append(d)
    for u in (37,38,44,60):
        d=copy.deepcopy(data);d['academic']['unrestricted']=u;variants.append(d)
    d=copy.deepcopy(data);d['academic']['options'][0]['start_day']=2;variants.append(d)
    for quality in ('3/5','1/2','0'):
        d=copy.deepcopy(data);d['incentives']['minimum_quality']=quality;variants.append(d)
    for rho in (0,2,4):
        d=copy.deepcopy(data);d['incentives']['intrinsic_quality']=rho;variants.append(d)
    d=copy.deepcopy(data);d['vote']['present'].remove('Fay');d['vote']['abstain']=[];variants.append(d)
    for amount in (0,2,9):
        d=copy.deepcopy(data);next(e for e in d['events'] if e['id']=='R1')['amount']=amount;variants.append(d)
    d=copy.deepcopy(data);next(e for e in d['events'] if e['id']=='R1')['status']='forecast';variants.append(d)
    d=copy.deepcopy(data);next(e for e in d['events'] if e['id']=='A2')['amount']=7;variants.append(d)
    for minute in (15,16):
        d=copy.deepcopy(data);d['crisis']['releases'][2]['minute']=minute;variants.append(d)
    d=copy.deepcopy(data);d['crisis']['staff']=8;d['crisis']['releases'][2]['approved']=['M','B'];variants.append(d)
    d=copy.deepcopy(data);d['crisis']['releases'][2]['cash']=9;variants.append(d)
    for d in variants:_,n=audit(d,reader);count+=n
    invalid=[]
    for path,value in [(('academic','unrestricted'),True),(('academic','grant'),-1),(('academic','grant_day'),'3/2'),(('incentives','minimum_quality'),2),(('incentives','bonuses'),[0,0]),(('finance_opening','equity'),31),(('crisis','staff'),-1),(('vote','present'),['Ada']),(('candidates',0,'ratings'),[11,2]),(('events',0,'amount'),1.5),(('events',1,'time'),'invalid'),(('actual_records',0,'status'),'verified_real')]:
        d=copy.deepcopy(data);p=d
        for key in path[:-1]:p=p[key]
        p[path[-1]]=value;invalid.append(d)
    d=copy.deepcopy(data);d['events'].append(copy.deepcopy(d['events'][-1]));invalid.append(d)
    d=copy.deepcopy(data);d['events'][7]['kind']='unsupported';invalid.append(d)
    for d in invalid:
        try:reader['run'](d)
        except (ValueError,TypeError,ZeroDivisionError):pass
        else:raise ValueError('invalid domain accepted')
    for raw in ('{"a":1,"a":2}','{"a":NaN}','{"a":Infinity}'):
        try:reader['strict_loads'](raw)
        except ValueError:pass
        else:raise ValueError('invalid JSON accepted')
    return {'component':'v18-project','status':'passed','comparisons':count,'changed_primitive_worlds':len(variants),'invalid_domains':len(invalid)+3,'tasks':7,'points':100,'author_checker':'opaque; bytes hashed only','review_scope':'internal machine-assisted independent peer; no actual learner certification'}

if __name__=='__main__':
    need(len(sys.argv)<=2,'optional book root');check(Path(sys.argv[1]) if len(sys.argv)==2 else None)
