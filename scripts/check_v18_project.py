"""Independent primitive model/data oracle and exact-nine author package check."""
import ast
import contextlib
import copy
from fractions import Fraction as F
import hashlib
from html.parser import HTMLParser
import io
import json
from pathlib import Path
import runpy
import sys

FILES = ('content/assessments/parts/v18-project.html',
         'content/projects/v18-assessment-inputs.json',
         'content/projects/v18-assessment-analysis.py',
         'content/projects/v18-assessment-output.json',
         'content/projects/v18-assessment-manifest.json',
         'content/projects/v18-assessment-README.txt',
         'scripts/check_v18_project.py',
         'content/reviews/v18-project-author.json',
         'content/reviews/v18-project-sources.json')


def need(ok, message):
    if not ok:
        raise ValueError('V18 project: '+message)


def strict(text):
    def pairs(items):
        d = {}
        for k, v in items:
            need(k not in d, 'duplicate JSON key'); d[k] = v
        return d
    def reject(value):
        raise ValueError('nonfinite JSON')
    return json.loads(text, object_pairs_hook=pairs, parse_constant=reject)


def pack(x):
    if isinstance(x, F):
        return x.numerator if x.denominator == 1 else str(x)
    if isinstance(x, (tuple, list)):
        return [pack(v) for v in x]
    if isinstance(x, dict):
        return {k: pack(v) for k, v in x.items()}
    return x


def oracle(data):
    c=data['academic'];U=F(c['unrestricted'])-F(c['fixed']);g=F(c['grant']);day=F(c['grant_day']);opts=c['options'];bundles=[]
    for mask in range(8):
        chosen=[o for i,o in enumerate(opts) if mask>>i&1];paid_grant={o['id']:min(g,F(o['cost'])) if o['grant_eligible'] and F(o['start_day'])>=day else F(0) for o in chosen};timeline=[{'day':0,'event':'fixed','unrestricted':U,'restricted':F(0)}];ordered=sorted([(day,0,'grant')]+[(F(o['start_day']),1,o['id'])for o in chosen]);seen=[]
        for date,kind,code in ordered:
            seen.append(code);completed=[o for o in chosen if o['id']in seen];uncash=U-sum(F(o['cost'])-paid_grant[o['id']]for o in completed);restricted=(g if 'grant'in seen else 0)-sum(paid_grant[o['id']]for o in completed);timeline.append({'day':date,'event':code,'unrestricted':uncash,'restricted':restricted})
        total=sum(F(o['cost'])for o in chosen);staff=sum(F(o['staff'])for o in chosen);ids=[o['id']for o in chosen];score=sum(F(o['score'])for o in chosen)+(F(c['complementarity'])if 'R'in ids and'T'in ids else 0);minimum=min(t['unrestricted']for t in timeline);why=[]
        if staff>F(c['staff']):why.append('staff_capacity')
        if minimum<F(c['floor']):why.append('dated_unrestricted_floor')
        bundles.append({'bundle':'+'.join(ids)or'none','cost':total,'staff':staff,'score':score,'minimum_unrestricted':minimum,'closing_unrestricted':timeline[-1]['unrestricted'],'closing_restricted':timeline[-1]['restricted'],'feasible':not why,'diagnostics':why,'timeline':timeline})
    feasible=[r for r in bundles if r['feasible']];best=sorted(feasible,key=lambda r:(-r['score'],r['cost'],r['bundle']))[0]['bundle']if feasible else None
    candidates=[]
    for p in data['candidates']:
        known=[F(s)for s in p['ratings']if s is not None];missing=p['ratings'].count(None);lo=sum(known)/2;hi=lo+5*missing;candidates.append({'id':p['id'],'eligible':missing==0,'score':lo if not missing else None,'possible_equal_weight_score':[lo,hi]})
    eligible=[p for p in candidates if p['eligible']];winner=sorted(p['id']for p in eligible if p['score']==max(x['score']for x in eligible))if eligible else []
    inc=data['incentives'];w=F(inc['salary']);rho=F(inc['intrinsic_quality']);contracts=[]
    for raw in inc['bonuses']:
        b=F(raw);utility=lambda e:w+b*e+rho*(1-e)-(e*e+(1-e)**2)/2;candidates_e=[F(0),F(1)];stationary=(1+b-rho)/2
        if 0<stationary<1:candidates_e.append(stationary)
        e=max(candidates_e,key=utility);q=1-e;reserve=w+b+F(inc['nonpay_cost']);why=[]
        if e<F(inc['minimum_output']):why.append('minimum_output')
        if q<F(inc['minimum_quality']):why.append('minimum_quality')
        if utility(e)<F(inc['outside_utility']):why.append('participation')
        if reserve>F(inc['personnel_envelope']):why.append('personnel_envelope')
        contracts.append({'bonus':b,'effort':e,'quality':q,'utility':utility(e),'actual_pay':w+b*e,'maximum_reserved_cost':reserve,'feasible':not why,'diagnostics':why})
    v=data['vote'];n=len(v['present']);threshold=next(k for k in range(n+2)if 2*k>n);vote={'eligible_members':len(set(v['members'])-set(v['interested'])),'present':n,'yes':len(v['yes']),'required_yes':threshold,'quorum':v['quorum'],'approved':n>=v['quorum']and len(v['yes'])>=threshold,'scope':v['scope']}
    opening=data['finance_opening'];cash0,sec,loan,debt0,equity0=(F(opening[k])for k in ('cash','securities','loans','liabilities','equity'));deltas=[];approvals={};spent={};receipts=set();history=[];exceptions=[]
    for event in data['events']:
        amount=F(event['amount']);kind=event['kind'];observed=event['status']=='observed';delta=(F(0),F(0),F(0));why=[];effect=False
        if observed and kind=='approval':approvals[event['id']]=amount;spent[event['id']]=0
        if observed and kind=='expense':
            ref=event['approval'];allowed=ref in approvals and spent[ref]+amount<=approvals[ref]
            if not allowed:why.append('expense_without_sufficient_prior_approval')
            else:spent[ref]+=amount
            delta=(-amount,F(0),-amount);effect=True
        if observed and kind=='debt_payment':delta=(-amount,-amount,F(0));effect=True
        if observed and kind=='income':delta=(amount,F(0),amount);receipts.add(event['reference']);effect=True
        if observed and kind=='notification':why.append('duplicate_receipt_notice'if event['reference']in receipts else'unconfirmed_receipt_notice')
        deltas.append(delta);cash=cash0+sum(x[0]for x in deltas);debt=debt0+sum(x[1]for x in deltas);equity=equity0+sum(x[2]for x in deltas)
        if cash<F(opening['cash_floor']):why.append('cash_floor')
        if equity<F(opening['equity_floor']):why.append('equity_floor')
        history.append({'id':event['id'],'status':event['status'],'booked_cash_effect':effect,'cash':cash,'assets':cash+sec+loan,'liabilities':debt,'equity':equity,'diagnostics':why});exceptions.extend({'event':event['id'],'reason':x}for x in why if x!='duplicate_receipt_notice')
    final=history[-1];closing={'cash':final['cash'],'securities':sec,'loans':loan,'assets':final['assets'],'liabilities':final['liabilities'],'equity':final['equity']};releases=[]
    for rel in data['crisis']['releases']:
        actions=[]
        for act in data['crisis']['actions']:
            cash=F(rel['cash'])-F(act['cost']);equity=F(rel['equity'])-F(act['cost']);checks=[(cash<F(opening['cash_floor']),'cash_floor'),(equity<F(opening['equity_floor']),'equity_floor'),(F(act['staff'])>F(data['crisis']['staff']),'staff_capacity'),(act['id']!='H'and F(rel['minute'])+F(act['minutes'])>F(data['crisis']['deadline']),'setup_deadline'),(act['requires_approval']and act['id']not in rel['approved'],'approval_missing')];why=[name for failed,name in checks if failed];actions.append({'action':act['id'],'loss':F(act['loss']),'cash_after':cash,'equity_after':equity,'feasible':not why,'diagnostics':why})
        available=sorted([a for a in actions if a['feasible']],key=lambda x:(x['loss'],x['action']));releases.append({'release':rel['id'],'actions':actions,'selected':available[0]['action']if available else None})
    domains=data['project_domains'];tasks={k:v for domain in domains for k,v in domain['tasks'].items()};records=data['actual_records']
    return pack({'schema':data['schema'],'academic':{'options':bundles,'selected':best,'diagnostic':None if feasible else'no_feasible_bundle_even_without_expansion'},'people':{'candidates':candidates,'eligible_winners':winner,'contracts':contracts},'governance':vote,'finance':{'events':history,'closing':closing,'unique_receipts':len(receipts),'exceptions':exceptions},'crisis':releases,'evidence':{'observed_in_fiction':[r['id']for r in records if r['status']=='observed_in_fiction'],'missing':[r['id']for r in records if r['status']=='missing'],'proposed':[r['id']for r in records if r['status']=='proposed'],'actual_learner_achievement':'not supplied'},'scoring':{'domains':domains,'tasks':tasks,'total':sum(tasks.values())}})

def literal(text):
    def visit(n):
        if isinstance(n, ast.Tuple): return tuple(visit(x) for x in n.elts)
        if isinstance(n, ast.Constant) and type(n.value) is int: return F(n.value)
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.USub): return -visit(n.operand)
        if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Div): return visit(n.left)/visit(n.right)
        raise ValueError('unsupported numeric literal')
    return visit(ast.parse(text.strip(), mode='eval').body)


class Page(HTMLParser):
    def __init__(self):
        super().__init__(); self.alltext=[]; self.stack=[]; self.ids=[]; self.tasks=[]; self.answers=[]; self.sources=[]; self.links=[]; self.markers={}; self.active=None; self.tables={}; self.table=None; self.row=None; self.cell=None
    def handle_starttag(self, tag, attrs):
        a=dict(attrs); need(len(a)==len(attrs), 'duplicate attrs'); need(tag!='h1', 'part h1')
        if 'id' in a:
            need(a['id']=='project' or a['id'].startswith('project-'), 'project prefix'); self.ids.append(a['id'])
        if tag=='li' and any(t=='ol' and 'exercises' in d.get('class','').split() for t,d in self.stack): self.tasks.append((a['id'], a['data-domain'], int(a['data-points'])))
        if 'data-solution-for' in a:
            need(any(t=='details' and 'solutions' in d.get('class','').split() for t,d in self.stack), 'solution disclosure'); self.answers.append(a['data-solution-for'])
        if 'data-source' in a: self.sources.append((a['data-source'],a['href']))
        if 'href' in a: self.links.append(a['href'])
        for kind in ('input','result'):
            if 'data-'+kind in a:
                key=(kind,a['data-'+kind]); need(key not in self.markers and self.active is None, 'unique markers'); self.markers[key]=''; self.active=(tag,key)
        if tag=='table': self.table=a['id']; self.tables[self.table]=[]
        if tag=='tr': self.row=[]
        if tag in ('th','td'): self.cell=[]
        if tag not in ('br','hr','img','input','meta','link'): self.stack.append((tag,a))
    def handle_data(self, text):
        self.alltext.append(text)
        if self.active: self.markers[self.active[1]]+=text
        if self.cell is not None: self.cell.append(text)
    def handle_endtag(self, tag):
        need(bool(self.stack) and self.stack.pop()[0]==tag, 'balanced fragment')
        if self.active and self.active[0]==tag: self.active=None
        if tag in ('th','td'): self.row.append(''.join(self.cell).strip()); self.cell=None
        if tag=='tr': self.tables[self.table].append(self.row); self.row=None
        if tag=='table': self.table=None


def check(root=None):
    root=Path(root).resolve() if root is not None else Path(__file__).resolve().parents[1];blobs={name:(root/name).read_bytes()for name in FILES};review=strict(blobs[FILES[7]].decode());need(review['full_reading_complete']and not review['open_material_findings'],'full review');need(set(review['payloads'])==set(FILES)-{FILES[7]},'eight nonself bindings')
    for name,binding in review['payloads'].items():need(binding=={'bytes':len(blobs[name]),'sha256':hashlib.sha256(blobs[name]).hexdigest()},'author hash '+name)
    manifest=strict(blobs[FILES[4]].decode());downloads=(FILES[1],FILES[2],FILES[3],FILES[5]);need(set(manifest['payloads'])=={Path(x).name for x in downloads},'four manifest hashes')
    for name in downloads:need(manifest['payloads'][Path(name).name]=={'bytes':len(blobs[name]),'sha256':hashlib.sha256(blobs[name]).hexdigest()},'manifest '+name)
    data=strict(blobs[FILES[1]].decode());expected=oracle(data);stream=io.StringIO();before=copy.deepcopy(data)
    with contextlib.redirect_stdout(stream),contextlib.redirect_stderr(stream):reader=runpy.run_path(str(root/FILES[2]));actual=reader['run'](data)
    need(not stream.getvalue()and before==data,'quiet immutable reader');count=0
    def eq(a,b,label):
        nonlocal count
        if isinstance(a,dict)or isinstance(b,dict):
            need(isinstance(a,dict)and isinstance(b,dict)and set(a)==set(b),'keys '+label)
            for k in a:eq(a[k],b[k],label+'/'+str(k))
        elif isinstance(a,(tuple,list))or isinstance(b,(tuple,list)):
            need(isinstance(a,(tuple,list))and isinstance(b,(tuple,list))and len(a)==len(b),'shape '+label)
            for i,(x,y)in enumerate(zip(a,b)):eq(x,y,label+'/'+str(i))
        else:count+=1;need(a==b and (type(a)==type(b)if isinstance(a,bool)or isinstance(b,bool)else True),label+': '+str(a)+' != '+str(b))
    eq(actual,expected,'independent primitive oracle');eq(strict(blobs[FILES[3]].decode()),expected,'retained result');page=Page();page.feed(blobs[FILES[0]].decode());page.close();need(not page.stack and page.active is None and len(page.ids)==len(set(page.ids)),'complete HTML');wantids=['project-task-'+str(i)for i in range(1,8)];need(page.answers==wantids and [x[0]for x in page.tasks]==wantids,'seven pairs');mapping={k:(d['id'],v)for d in data['project_domains']for k,v in d['tasks'].items()};eq(page.tasks,[(wantids[i-1],*mapping[str(i)])for i in range(1,8)],'task mapping');sources=strict(blobs[FILES[8]].decode())['sources'];need(set(page.sources)=={(s['id'],s['url'])for s in sources},'source routes');need(set(x for x in page.links if x.startswith('v18-assessment-'))=={Path(x).name for x in FILES[1:6]},'five flat downloads')
    menu=page.tables['project-solution-menu'][1:];eq(len(menu),8,'all subsets')
    for row,model in zip(menu,expected['academic']['options']):eq(row[0],model['bundle'],'bundle');eq([pack(F(x))for x in row[1:5]],[model[k]for k in ('cost','staff','score','minimum_unrestricted')],'visible subset values');eq(row[5], 'yes'if model['feasible']else'no','visible subset feasibility')
    for row,model in zip(page.tables['project-solution-ledger'][1:],expected['finance']['events']):eq(row[0],model['id'],'event ID');eq([pack(F(x))for x in row[1:5]],[model[k]for k in ('cash','assets','liabilities','equity')],'visible ledger');eq(row[5],'yes'if model['booked_cash_effect']else'no','visible cash status')
    eq(len(page.tables['project-solution-ledger'])-1,len(data['events']),'every event')
    for row,primitive in zip(page.tables['project-options'][1:],data['academic']['options']):eq(row[:5],[str(primitive[k])for k in ('id','cost','staff','score','start_day')],'option inputs');eq(row[5],'yes'if primitive['grant_eligible']else'no','grant eligibility');eq(row[6],primitive['deliverable'],'full option text')
    for row,primitive in zip(page.tables['project-events'][1:],data['events']):eq(row[0],primitive['id']+' '+primitive['time'],'visible event timestamp');eq(row[1],primitive['kind']+' / '+primitive['status']+' / '+str(primitive['amount']),'visible event inputs');eq(row[3],primitive['note'],'full event record')
    for row,primitive in zip(page.tables['project-releases'][1:],data['crisis']['releases']):eq(row,[str(primitive[k])for k in ('id','minute','cash','equity','approved','evidence')],'release inputs')
    numbers={k:literal(v)for k,v in page.markers.items()};used=set()
    def marker(kind,key,value):used.add((kind,key));eq(pack(numbers[kind,key]),pack(value),'HTML '+key)
    marker('input','academic',tuple(F(data['academic'][k])for k in ('unrestricted','restricted','fixed','floor','staff','grant','grant_day','complementarity')));marker('input','finance',tuple(F(data['finance_opening'][k])for k in ('cash','securities','loans','liabilities','equity','cash_floor','equity_floor')));marker('input','incentives',tuple(F(data['incentives'][k])for k in ('salary','intrinsic_quality','outside_utility','minimum_output','minimum_quality','personnel_envelope','nonpay_cost')));marker('result','effort',[[F(str(c[k]))for k in ('effort','quality','utility','actual_pay','maximum_reserved_cost')]for c in expected['people']['contracts']]);marker('result','closing',[expected['finance']['closing'][k]for k in ('cash','assets','liabilities','equity')]);marker('result','vote',[expected['governance'][k]for k in ('eligible_members','present','yes','required_yes','quorum')]);marker('result','task-points',[mapping[str(i)][1]for i in range(1,8)]);need(used==set(numbers),'all numeric markers')
    eq([int(row[-1])for row in page.tables['project-rubric'][1:]],[mapping[str(i)][1]for i in range(1,8)],'actual additive points')
    # Complete candidate/policy/feedback text must be in the actual rendered fragment.
    text=' '.join(page.alltext)
    for record in list(data['policies'].values())+list(data['feedback'].values())+[x['text']for x in data['actual_records']]+[x[k]for x in data['candidates']for k in ('research_work','teaching_work')if x[k]]:need(record in text,'full supplied evidence text')
    variants=[]
    for day in (1,7):
        v=copy.deepcopy(data);v['academic']['grant_day']=day;variants.append(v)
    v=copy.deepcopy(data);v['academic']['options'][0]['start_day']=2;variants.append(v)
    v=copy.deepcopy(data);v['academic']['unrestricted']=35;variants.append(v)
    for rho in (0,3):
        v=copy.deepcopy(data);v['incentives']['intrinsic_quality']=rho;variants.append(v)
    v=copy.deepcopy(data);v['incentives']['minimum_quality']='3/5';variants.append(v)
    v=copy.deepcopy(data);v['vote']['present'].remove('Fay');v['vote']['abstain']=[];variants.append(v)
    v=copy.deepcopy(data);v['events'][7]['amount']=3;variants.append(v)
    v=copy.deepcopy(data);v['events'][7]['status']='forecast';variants.append(v)
    v=copy.deepcopy(data);v['crisis']['staff']=8;v['crisis']['releases'][2]['approved']=['M','B'];variants.append(v)
    v=copy.deepcopy(data);v['crisis']['releases'][2]['minute']=16;variants.append(v)
    for i,v in enumerate(variants):
        want=oracle(v);prior=copy.deepcopy(v)
        with contextlib.redirect_stdout(stream),contextlib.redirect_stderr(stream):got=reader['run'](v)
        need(v==prior and not stream.getvalue(),'variant API purity');eq(got,want,'changed primitives '+str(i))
    invalid=0
    changes=[lambda d:d.update(schema='wrong'),lambda d:d['academic'].update(grant=-1),lambda d:d['academic']['options'][0].update(cost=True),lambda d:d['candidates'][2]['ratings'].__setitem__(1,0),lambda d:d['candidates'][0]['ratings'].__setitem__(0,11),lambda d:d['incentives'].update(minimum_quality=2),lambda d:d['vote']['present'].append('Ada'),lambda d:d['vote']['yes'].append('Fay'),lambda d:d['finance_opening'].update(equity=31),lambda d:d['events'][0].update(time='bad'),lambda d:d['events'][1].update(amount=171),lambda d:d['events'][2].update(status='magic'),lambda d:d['events'][7].update(reference=''),lambda d:d['crisis']['actions'][1].update(minutes=-1),lambda d:d['project_domains'][0].update(points=19),lambda d:d['actual_records'][0].update(status='real')]
    for change in changes:
        bad=copy.deepcopy(data);change(bad)
        try:reader['run'](bad)
        except (ValueError,TypeError,KeyError,ZeroDivisionError):invalid+=1
        else:raise ValueError('invalid input accepted')
    need(not stream.getvalue(),'reader remains quiet');return {'volume':'v18','component':'project','status':'passed','runtime_files':9,'comparisons':count,'academic_bundles':8,'dated_financial_events':12,'crisis_releases':4,'changed_primitive_worlds':len(variants),'invalid_domains':invalid,'tasks':7}
if __name__=='__main__':
    need(len(sys.argv)<=2,'usage checker [root]');check(sys.argv[1]if len(sys.argv)==2 else None)
