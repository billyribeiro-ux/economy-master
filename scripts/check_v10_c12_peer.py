"""Separate c12 peer audit: cash accumulation, interpolation and policy boundaries."""
from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
from datetime import date
from fractions import Fraction as Q
from hashlib import sha256
from html.parser import HTMLParser
from io import StringIO
from itertools import product
import json
import math
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
ASSETS=ROOT/'content/projects'
AUTHOR_PATHS=['content/chapters/v10-c12.html']+['content/projects/v10-c12-'+s for s in ('inputs.json','analysis.py','output.json','manifest.json','README.txt')]+['scripts/check_v10_c12.py','content/reviews/v10-c12-author.json','content/reviews/v10-c12-sources.json']
PEER_PATHS=['scripts/check_v10_c12_peer.py','content/reviews/v10-c12-peer.json']


def require(ok,label):
    if not ok:raise AssertionError(label)


class Audit:
    def __init__(self):self.comparisons=0;self.rejections=0;self.interventions=0;self.groups=[]
    def eq(self,a,b,label):
        self.comparisons+=1
        require(a==b,label+': '+repr(a)+' != '+repr(b))
    def true(self,ok,label):
        self.comparisons+=1;require(ok,label)
    def near(self,a,b,label):
        self.comparisons+=1
        require(type(a) in (float,int) and math.isfinite(a) and math.isclose(a,float(b),rel_tol=3e-14,abs_tol=1e-13),label)


def replace(data,path,value):
    x=deepcopy(data);p=x
    for key in path[:-1]:p=p[key]
    p[path[-1]]=value
    return x


def affine(t1,t2,q1,q2,target):
    # Cramer's rule, independent of the model's interpolation-weight evaluation.
    det=t2-t1
    intercept=(q1*t2-q2*t1)/det
    slope=(q2-q1)/det
    return intercept+slope*target


def online_moments(values):
    # Welford recurrence in exact arithmetic, independent of centered-sum formula.
    mean=Q(0);m2=Q(0)
    for n,x in enumerate(values,1):
        previous=mean;mean+=(x-mean)/n;m2+=(x-previous)*(x-mean)
    return mean,m2


def inspect(a,data,out,label):
    b=data['bond'];cash=list(map(Q,b['cash_flows']));ds=list(map(Q,b['benchmark_discounts']));dc=list(map(Q,b['candidate_discounts']))
    # Accumulate dated receipts into terminal bank wealth, then discount back.
    wealth0=sum(c*d/ds[-1] for c,d in zip(cash,ds));wealth1=sum(c*d/dc[-1] for c,d in zip(cash,dc))
    p0=wealth0*ds[-1];p1=wealth1*dc[-1];err=p1-p0
    expected={'benchmark_value':p0,'candidate_value':p1,'price_error':err,'position_value_error':Q(b['position'])*err}
    for k,v in expected.items():a.eq(Q(out['bond'][k]),v,label+' bank accumulation '+k)
    a.eq(list(map(Q,out['bond']['per_cash_flow_error'])),[c*(nd-od) for c,nd,od in zip(cash,dc,ds)],label+' cash attribution')
    bp=abs(err)<=Q(b['price_tolerance']);a.eq(out['bond']['absolute_error_pass'],bp,label+' bond inclusive gate')
    c=data['curve_family'];p1=Q(c['price_at_one']);p2=Q(c['price_at_two']);t=Q(c['requested_tenor'])
    first=p1-100;second=((p2-p1)-first)/2
    # Newton divided-difference polynomial through 0,1,2 plus vanishing basis.
    low,high=Q(c['curvature_lower']),Q(c['curvature_upper'])
    def f(u,k):return 100+first*u+second*u*(u-1)+k*u*(u-1)*(u-2)
    candidates=[f(t,low+(high-low)*Q(j,7)) for j in range(8)]
    a.eq((Q(out['curve_family']['linear_coefficient']),Q(out['curve_family']['quadratic_coefficient'])),(first-second,second),label+' divided differences')
    for k in (low,high):a.eq((f(0,k),f(1,k),f(2,k)),(100,p1,p2),label+' null perturbation calibration')
    lo,hi=min(candidates),max(candidates)
    a.eq((Q(out['curve_family']['target_lower']),Q(out['curve_family']['target_upper'])),(lo,hi),label+' identified range')
    a.eq(Q(out['curve_family']['target_spread']),hi-lo,label+' target width')
    a.eq(Q(out['curve_family']['unidentified_loading']),f(t,1)-f(t,0),label+' free loading')
    cp=hi-lo<=Q(c['spread_limit']);a.eq(out['curve_family']['spread_within_limit'],cp,label+' scope inclusive gate')
    c=data['conditioning'];t1,t2,y1,y2,target,eps=(Q(c[k]) for k in ('first_tenor','second_tenor','first_quote','second_quote','target_tenor','quote_error_bound'))
    pred=affine(t1,t2,y1,y2,target)
    w1=affine(t1,t2,y1+1,y2,target)-pred;w2=affine(t1,t2,y1,y2+1,target)-pred
    vertices=[affine(t1,t2,y1+e1,y2+e2,target)-pred for e1,e2 in product((-eps,eps),repeat=2)]
    for k,v in {'prediction':pred,'first_weight':w1,'second_weight':w2,'slope':(y2-y1)/(t2-t1),'intercept':affine(t1,t2,y1,y2,0),'absolute_condition_factor':abs(w1)+abs(w2),'two_quote_error_bound':max(map(abs,vertices)),'second_quote_plus_bound_change':affine(t1,t2,y1,y2+eps,target)-pred}.items():a.eq(Q(out['conditioning'][k]),v,label+' determinant/vertex '+k)
    b=data['book'];old,new,pos,eps=(list(map(Q,b[k])) for k in ('benchmark_prices','candidate_prices','positions','unit_tolerances'))
    errors=[y-x for x,y in zip(old,new)];contributions=[q*y-q*x for x,y,q in zip(old,new,pos)]
    signed=sum(q*y for q,y in zip(pos,new))-sum(q*x for q,x in zip(pos,old))
    positive=sum(x for x in contributions if x>0);negative=sum(x for x in contributions if x<0);gross=positive-negative
    a.eq(list(map(Q,out['book']['unit_errors'])),errors,label+' unit discrepancies')
    a.eq(list(map(Q,out['book']['position_contributions'])),contributions,label+' marked position differences')
    a.eq(Q(out['book']['signed_error']),signed,label+' aggregate valuation difference')
    a.eq(Q(out['book']['gross_comparison_error']),gross,label+' gross positive-minus-negative')
    if len(pos)<=4:
        bound=max(abs(sum(p*e*z for p,e,z in zip(pos,eps,sign))) for sign in product((-1,1),repeat=len(pos)))
    else:bound=sum(abs(p)*e for p,e in zip(pos,eps))
    a.eq(Q(out['book']['bound_from_unit_tolerances']),bound,label+' simultaneous rectangle extremum')
    units=[abs(e)<=t for e,t in zip(errors,eps)];sp=abs(signed)<=Q(b['signed_error_limit']);gp=gross<=Q(b['gross_error_limit'])
    a.eq((out['book']['unit_passes'],out['book']['signed_pass'],out['book']['gross_pass']),(units,sp,gp),label+' book gates')
    a.near(out['book']['unit_rmse_approx'],math.sqrt(float(sum(e*e for e in errors)/len(errors))),label+' unit RMS')
    errors=list(map(Q,data['holdout']['forecast_errors']));n=len(errors);mean,m2=online_moments(errors)
    a.eq(out['holdout']['observations'],n,label+' holdout count')
    a.eq(Q(out['holdout']['mean_error']),mean,label+' online mean')
    a.eq(Q(out['holdout']['sample_variance']),m2/(n-1),label+' online variance')
    a.eq(Q(out['holdout']['mean_squared_error']),m2/n+mean*mean,label+' decomposition MSE')
    a.near(out['holdout']['rmse_approx'],math.sqrt(float(m2/n+mean*mean)),label+' holdout RMSE')
    a.near(out['holdout']['iid_standard_error_if_assumed_approx'],math.sqrt(float(m2/(n*(n-1)))),label+' conditional SE')
    d=data['decision'];ex=d['exception']
    active=bool(ex['enabled'] and len({ex['approver'],d['owner'],d['challenger']})==3 and date.fromisoformat(ex['expires'])>=date.fromisoformat(d['as_of']))
    # If owner/challenger coincide, an independent approver still makes a size
    # exception valid; independent_challenge separately rejects the request.
    if d['owner']==d['challenger']:
        active=bool(ex['enabled'] and ex['approver']!=d['owner'] and date.fromisoformat(ex['expires'])>=date.fromisoformat(d['as_of']))
    limit=Q(d['ordinary_limit'])
    if active:limit=max(limit,Q(ex['notional_limit']))
    gates={'numeric_benchmark':bp,'curve_scope':cp,'book_units':all(units),'book_signed':sp,'book_gross':gp,'version_binding':d['requested_version']==d['reviewed_version'],'independent_challenge':d['owner']!=d['challenger'],'fresh_evidence':d['data_age_days']<=d['max_data_age_days'],'notional_limit':Q(d['requested_notional'])<=limit}
    failed=[k for k,v in gates.items() if not v]
    a.eq(out['decision']['checks'],gates,label+' independent gate dictionary')
    a.eq(out['decision']['failed_gates'],failed,label+' exact ordered failures')
    a.eq(Q(out['decision']['effective_notional_limit']),limit,label+' only size limit changed')
    a.eq(out['decision']['exception_valid_for_size_only'],active,label+' exception validity')
    a.eq(out['decision']['recommendation'],'reject_requested_use' if failed else 'eligible_with_stated_limits',label+' policy conclusion')


class Fragment(HTMLParser):
    def __init__(self):super().__init__();self.stack=[];self.hrefs=[];self.ids=[];self.worked=0;self.problems=0;self.answers=0
    def handle_starttag(self,t,attrs):
        x=dict(attrs)
        if 'href'in x:self.hrefs.append(x['href'])
        if 'id'in x:self.ids.append(x['id'])
        if 'worked'in x.get('class','').split():self.worked+=1
        if t=='li' and self.stack and self.stack[-1][0]=='ol':
            if 'exercises'in self.stack[-1][1].get('class','').split():self.problems+=1
            if any(k=='details' and 'solutions'in a.get('class','').split() for k,a in self.stack):self.answers+=1
        if t not in ('br','hr','meta','input','link','img'):self.stack.append((t,x))
    def handle_endtag(self,t):require(self.stack and self.stack[-1][0]==t,'balanced HTML '+t);self.stack.pop()


def check():
    a=Audit();raw=json.loads((ASSETS/'v10-c12-inputs.json').read_text());before=deepcopy(raw);cap=StringIO()
    with redirect_stdout(cap),redirect_stderr(cap):
        run=runpy.run_path(str(ASSETS/'v10-c12-analysis.py'))['run'];base=run(raw)
    a.eq(cap.getvalue(),'','quiet import/run');a.eq(raw,before,'nonmutating API');a.eq(json.loads(json.dumps(base,allow_nan=False)),base,'strict JSON safe')
    a.eq(base,json.loads((ASSETS/'v10-c12-output.json').read_text()),'complete reproducible saved output')
    inspect(a,raw,base,'baseline')
    # Exact independent question anchors.
    values=[(Q(50)*Q('0.99')+1050*Q('.95'),Q(1047)),(Q(50)*Q('.99')+1050*Q('.94'),Q(2073,2)),(-20*1050*(Q('.94')-Q('.95')),Q(210)),(88-6*Q(1,2),Q(85)),(88+6*Q(1,2),Q(91)),(affine(Q(1),Q('1.1'),Q(99),Q('98.9'),Q(3)),Q(97)),(affine(Q(1),Q('1.1'),Q('98.99'),Q('98.91'),Q(3))-97,Q(39,100)),(100*Q('.01')+50*Q('.03')+200*Q('.005'),Q(7,2)),(Q(12)-5-4,Q(3)),(Q(8)-5-4,Q(-1)),(Q(1000000)*Q('.0005')*2,Q(1000)),(Q(10,8),Q(5,4)),(Q(10)*Q('.1')+20*Q('.2'),Q(5))]
    for got,want in values:a.eq(got,want,'exercise/retention independent anchor')
    for rho,want in [(1,1000),(0,500*math.sqrt(2)),(-1,0)]:a.near(math.sqrt(500**2+500**2+2*rho*500**2),want,'covariance transfer')
    a.eq((affine(Q(1),Q('1.5'),1,0,Q(3)),affine(Q(1),Q('1.5'),0,1,Q(3))),(-3,4),'retention target weights')
    a.groups.append('independent bank accumulation, Newton null direction, determinant perturbations, portfolio vertices and online moments; all determinate exercise anchors')

    scenarios=[]
    # Finance: zero/signed receipts, discounts above1, two sides of null-loading
    # zeros, exact-input boundaries and independent holdout transformations.
    for path,value in [(('bond','cash_flows'),['-100','0','2100']),(('bond','benchmark_discounts'),['1.01','1.02','1.03']),(('bond','candidate_discounts'),['1.01','1.02','1.03']),(('bond','position'),'-40'),(('curve_family','requested_tenor'),'0'),(('curve_family','requested_tenor'),'1/2'),(('curve_family','requested_tenor'),'3/2'),(('curve_family','requested_tenor'),'2'),(('curve_family','curvature_lower'),'1'),(('conditioning','target_tenor'),'0'),(('conditioning','target_tenor'),'201/200'),(('conditioning','second_tenor'),'10001/10000'),(('conditioning','second_tenor'),'11/10'),(('conditioning','quote_error_bound'),'0'),(('book','positions'),['200','150','100']),(('book','positions'),['0','0','0']),(('book','candidate_prices'),['100.03','80','50']),(('holdout','forecast_errors'),list(reversed(raw['holdout']['forecast_errors']))),(('holdout','forecast_errors'),[str(Q(x)+3) for x in raw['holdout']['forecast_errors']]),(('holdout','forecast_errors'),[str(-2*Q(x)) for x in raw['holdout']['forecast_errors']]),(('holdout','forecast_errors'),['0']*8)]:scenarios.append(replace(raw,path,value))
    for n in (2,100):
        x=deepcopy(raw);x['holdout']['evaluation_ids']=['sample_'+str(i) for i in range(n)];x['holdout']['forecast_errors']=['-1000','1000']*(n//2);scenarios.append(x)
    repaired=deepcopy(raw);repaired['bond']['candidate_discounts']=deepcopy(raw['bond']['benchmark_discounts']);repaired['book']['candidate_prices']=deepcopy(raw['book']['benchmark_prices']);repaired['curve_family']['requested_tenor']='2';scenarios.append(repaired)
    for path,value in [(('decision','exception','expires'),'2026-10-05'),(('decision','exception','expires'),'2026-10-06'),(('decision','exception','enabled'),False),(('decision','exception','approver'),'developer_a'),(('decision','exception','approver'),'reviewer_b'),(('decision','exception','notional_limit'),'40000'),(('decision','requested_notional'),'120000'),(('decision','requested_notional'),'120000.00000001'),(('decision','requested_version'),'sable_3'),(('decision','challenger'),'developer_a'),(('decision','data_age_days'),5),(('decision','data_age_days'),6)]:scenarios.append(replace(repaired,path,value))
    for amount in ('50000','50000.00000001'):
        x=replace(repaired,('decision','exception','expires'),'2026-10-05');x['decision']['requested_notional']=amount;scenarios.append(x)
    for x in scenarios:
        original=deepcopy(x);o=run(x);inspect(a,x,o,'intervention '+str(a.interventions));a.eq(x,original,'intervention preserves input');a.interventions+=1
    a.eq(run(repaired)['decision']['failed_gates'],[],'three repairs pass')
    a.eq(base['decision']['failed_gates'],['numeric_benchmark','curve_scope','book_signed','book_gross'],'all four baseline blocking findings')
    a.groups.append('38 financial/policy interventions: negative-rate receipts, signed book, null-loading sign, tight tenor gap, holdout invariances, inclusive expiry and size-only exceptions')

    invalid=[None,[],{}]
    for path,value in [(('bond','position'),True),(('bond','position'),1.0),(('bond','position'),'1e2'),(('bond','position'),'1/0'),(('bond','position'),'0.000000001'),(('bond','position'),'10001'),(('bond','cash_flows'),[]),(('bond','cash_flows'),['0']*25),(('bond','cash_flows'),['1000001','0','0']),(('bond','benchmark_discounts'),['0','1','1']),(('bond','candidate_discounts'),['3.01','1','1']),(('curve_family','curvature_lower'),'1.01'),(('curve_family','requested_tenor'),'3.01'),(('conditioning','second_tenor'),'1'),(('conditioning','second_tenor'),'1.00001'),(('book','positions'),['0']),(('book','unit_tolerances'),['-1','0','0']),(('holdout','training_ids'),['hold_1']),(('holdout','evaluation_ids'),['same']*8),(('holdout','forecast_errors'),['1001']*8),(('holdout','forecast_errors'),['0']),(('decision','as_of'),'2026-02-29'),(('decision','as_of'),'1999-12-31'),(('decision','as_of'),'2101-01-01'),(('decision','data_age_days'),True),(('decision','data_age_days'),366),(('decision','requested_version'),'UPPER'),(('decision','exception','enabled'),1),(('decision','exception','reason'),'   '),(('decision','exception','reason'),'a'*241),(('decision','exception','expires'),'2026-10-00'),(('decision','requested_notional'),'100000001')]:invalid.append(replace(raw,path,value))
    x=deepcopy(raw);x['extra']=0;invalid.append(x)
    x=deepcopy(raw);del x['decision']['exception']['approver'];invalid.append(x)
    x=replace(raw,('curve_family','curvature_lower'),'1');x['curve_family']['curvature_upper']='-1';invalid.append(x)
    for x in invalid:
        before=deepcopy(x)
        try:run(x)
        except ValueError:a.rejections+=1
        else:raise AssertionError('invalid peer case accepted')
        a.eq(x,before,'rejected input unchanged')
    a.groups.append('independently selected strict shape, financial-string, scalar bounds, split leakage, dates and policy-type rejections')

    with tempfile.TemporaryDirectory(prefix='v10-c12-peer-') as td:
        p=Path(td);assets=p/'download';assets.mkdir();cwd=p/'elsewhere';cwd.mkdir()
        for name in ('analysis.py','inputs.json'):shutil.copy2(ASSETS/('v10-c12-'+name),assets)
        script=assets/'v10-c12-analysis.py'
        for opt in ([],['-O']):
            cmd=[sys.executable]+opt+[str(script)]
            proc=subprocess.run(cmd,cwd=cwd,capture_output=True,text=True)
            a.eq((proc.returncode,proc.stderr),(0,''),'isolated default status');a.eq(json.loads(proc.stdout),base,'isolated default output')
            dest=p/'result.json';proc=subprocess.run(cmd+['--input',str(assets/'v10-c12-inputs.json'),'--output',str(dest)],cwd=cwd,capture_output=True,text=True)
            a.eq((proc.returncode,proc.stdout,proc.stderr),(0,'',''),'explicit CLI quiet');a.eq(json.loads(dest.read_text()),base,'explicit CLI complete output')
            for content in ('{"schema":1,"schema":2}',json.dumps(raw).replace('"position": "40"','"position": NaN',1),json.dumps(invalid[-1])):
                bad=p/'bad.json';bad.write_text(content);dest.write_text('do not replace')
                proc=subprocess.run(cmd+['--input',str(bad),'--output',str(dest)],cwd=cwd,capture_output=True,text=True)
                a.true(proc.returncode!=0,'invalid CLI nonzero');a.eq(proc.stdout,'','invalid CLI no data');a.eq(dest.read_text(),'do not replace','invalid CLI preserves existing output')
    a.groups.append('isolated normal/-O default and explicit CLIs, strict duplicate/nonfinite JSON and failure-before-output replacement')

    chapter=(ROOT/'content/chapters/v10-c12.html').read_text();f=Fragment();f.feed(chapter)
    a.eq(f.stack,[],'complete fragment');a.eq((f.worked,f.problems,f.answers),(5,10,10),'all cases/prompts/solutions')
    a.eq(len(f.ids),len(set(f.ids)),'unique anchors')
    for ext in ('inputs.json','analysis.py','output.json','README.txt','manifest.json'):a.true('v10-c12-'+ext in f.hrefs,'flat downloadable '+ext)
    a.true('Teach-back and delayed retention' in chapter and 'Answers.' in chapter,'answered teaching/retention')
    for s in ('SR 26-2','17 April 2026','supersedes SR 11-7 and SR 21-8','generative and agentic AI','guidance rather than enforceable prescriptive standards'):a.true(s in chapter,'scoped source statement '+s)
    author=json.loads((ROOT/'content/reviews/v10-c12-author.json').read_text())
    a.eq({x['path'] for x in author['reviewed_hashes']},set(AUTHOR_PATHS)-{'content/reviews/v10-c12-author.json'},'author binds exactly eight nonself files')
    for record in author['reviewed_hashes']:
        blob=(ROOT/record['path']).read_bytes();a.eq((len(blob),sha256(blob).hexdigest()),(record['bytes'],record['sha256']),'author original hash')
    manifest=json.loads((ASSETS/'v10-c12-manifest.json').read_text())
    a.eq({r['file'] for r in manifest['files']},{'v10-c12-'+s for s in ('inputs.json','analysis.py','output.json','README.txt')},'original four-payload manifest')
    for r in manifest['files']:
        blob=(ASSETS/r['file']).read_bytes();a.eq((len(blob),sha256(blob).hexdigest()),(r['bytes'],r['sha256']),'original manifest digest')
    peer=json.loads((ROOT/'content/reviews/v10-c12-peer.json').read_text())
    a.eq({r['path'] for r in peer['reviewed_hashes']},set(AUTHOR_PATHS),'peer binds nine authors');a.eq(len(peer['reviewed_hashes']),9,'nine without duplicates')
    for r in peer['reviewed_hashes']:
        blob=(ROOT/r['path']).read_bytes();a.eq((len(blob),sha256(blob).hexdigest()),(r['bytes'],r['sha256']),'peer author digest')
    m=json.loads((ROOT/'content/reviews/v10-c12-peer-manifest.json').read_text())
    a.eq(m['author_files'],peer['reviewed_hashes'],'manifest same frozen author set')
    a.eq({r['path'] for r in m['peer_payloads']},set(PEER_PATHS),'manifest binds peer record and checker')
    for r in m['peer_payloads']:
        blob=(ROOT/r['path']).read_bytes();a.eq((len(blob),sha256(blob).hexdigest()),(r['bytes'],r['sha256']),'peer payload digest')
    a.groups.append('complete manuscript, all ten exact solutions, dated source scope and nine author/two peer-payload bindings')
    return {'chapter':'v10-c12','status':'passed','peer_comparisons':a.comparisons,'invalid_inputs_rejected':a.rejections,'financial_interventions':a.interventions,'author_files_bound':9,'worked_examples_reviewed':5,'solved_exercises_reviewed':10,'count_definition':'Each executed scalar/vector/object comparison counts once; invalid API cases and targeted interventions have separate counters. The independent proof/source review is recorded separately.','groups':a.groups,'limits':'Separate machine-assisted peer review, not external human certification, empirical adequacy, real approval or visual UI QA. No author implementation helpers are used as numerical oracles.'}


if __name__=='__main__':print(json.dumps(check(),indent=2,allow_nan=False))
