#!/usr/bin/env python3
"""Independently recompute Sable evidence, perturbations and bounded policy cases."""
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
from datetime import date
from fractions import Fraction as F
import hashlib
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

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'content/projects'


def need(condition, label):
    if not condition:
        raise RuntimeError(label)


class Audit:
    def __init__(self):
        self.comparisons = self.rejections = self.interventions = 0

    def eq(self, actual, expected, label):
        self.comparisons += 1
        if isinstance(expected, F):
            actual = F(actual)
        need(actual == expected, f'{label}: {actual!r} != {expected!r}')

    def close(self, actual, expected, label):
        self.comparisons += 1
        need(math.isfinite(actual) and math.isclose(actual, expected, rel_tol=2e-14, abs_tol=1e-13), label)


def solve(matrix, vector):
    """Small exact Gaussian elimination, independent of model coefficient formulas."""
    rows = [[F(x) for x in row] + [F(y)] for row, y in zip(matrix, vector)]
    n = len(rows)
    for j in range(n):
        pivot = next(i for i in range(j, n) if rows[i][j])
        rows[j], rows[pivot] = rows[pivot], rows[j]
        scale = rows[j][j]
        rows[j] = [x / scale for x in rows[j]]
        for i in range(n):
            if i != j:
                scale = rows[i][j]
                rows[i] = [x-scale*y for x, y in zip(rows[i], rows[j])]
    return [row[-1] for row in rows]


def fitted_value(t1, t2, y1, y2, t):
    alpha, beta = solve([[1,t1],[1,t2]], [y1,y2])
    return alpha + beta*t


def audit_evidence(a, data, result):
    b=data['bond']; r=result['bond']
    cf=list(map(F,b['cash_flows'])); old=list(map(F,b['benchmark_discounts'])); new=list(map(F,b['candidate_discounts']))
    pv=[sum((cf[i]*ds[i] for i in range(len(cf))),F(0)) for ds in (old,new)]
    differences=[x*(y-z) for x,y,z in zip(cf,new,old)]
    for name, value in [('benchmark_value',pv[0]),('candidate_value',pv[1]),('price_error',sum(differences,F(0))),
                        ('position_value_error',(pv[1]-pv[0])*F(b['position']))]:
        a.eq(r[name],value,'dated bond '+name)
    for x,y in zip(r['per_cash_flow_error'],differences):a.eq(x,y,'cash contribution')
    a.eq(r['absolute_error_pass'],abs(pv[1]-pv[0])<=F(b['price_tolerance']),'bond gate')

    c=data['curve_family']; r=result['curve_family']; t=F(c['requested_tenor'])
    constant,linear,quadratic=solve([[1,0,0],[1,1,1],[1,2,4]],[100,F(c['price_at_one']),F(c['price_at_two'])])
    a.eq(constant,F(100),'fixed present receipt');a.eq(r['linear_coefficient'],linear,'calibration system linear')
    a.eq(r['quadratic_coefficient'],quadratic,'calibration system quadratic')
    low,high=F(c['curvature_lower']),F(c['curvature_upper'])
    values=[]
    for j in range(9):
        curvature=low+(high-low)*F(j,8)
        # Expanded cubic coefficients explicitly expose the quote-null vector.
        polynomial=[constant,linear+2*curvature,quadratic-3*curvature,curvature]
        def value(tenor):
            return sum((coefficient*tenor**power for power,coefficient in enumerate(polynomial)),F(0))
        a.eq(value(F(1)),F(c['price_at_one']),'unchanged first fitted quote')
        a.eq(value(F(2)),F(c['price_at_two']),'unchanged second fitted quote')
        values.append(value(t))
    for name,v in [('unidentified_loading',t**3-3*t*t+2*t),('target_lower',min(values)),
                   ('target_upper',max(values)),('target_spread',max(values)-min(values))]:a.eq(r[name],v,'null direction '+name)
    curve_spread=max(values)-min(values)
    a.eq(r['calibration_residuals'],['0','0'],'zero residuals')
    a.eq(r['spread_within_limit'],max(values)-min(values)<=F(c['spread_limit']),'scope gate')

    c=data['conditioning'];r=result['conditioning']
    t1,t2,y1,y2,target,epsilon=(F(c[k]) for k in ('first_tenor','second_tenor','first_quote','second_quote','target_tenor','quote_error_bound'))
    alpha,beta=solve([[1,t1],[1,t2]],[y1,y2]);base=alpha+beta*target
    weights=[fitted_value(t1,t2,F(1),F(0),target),fitted_value(t1,t2,F(0),F(1),target)]
    vertices=[fitted_value(t1,t2,y1+e1,y2+e2,target)-base for e1,e2 in product((-epsilon,epsilon),repeat=2)]
    expected={'slope':beta,'intercept':alpha,'first_weight':weights[0],'second_weight':weights[1],
              'prediction':base,'second_quote_plus_bound_change':fitted_value(t1,t2,y1,y2+epsilon,target)-base,
              'two_quote_error_bound':max(map(abs,vertices)),'absolute_condition_factor':sum(map(abs,weights),F(0))}
    for name,v in expected.items():a.eq(r[name],v,'perturbed linear systems '+name)

    b=data['book'];r=result['book']
    old,new,qty,eps=(list(map(F,b[k])) for k in ('benchmark_prices','candidate_prices','positions','unit_tolerances'))
    errors=[y-x for x,y in zip(old,new)]
    contributions=[q*y-q*x for x,y,q in zip(old,new,qty)]
    signed=sum((q*y for q,y in zip(qty,new)),F(0))-sum((q*x for q,x in zip(qty,old)),F(0))
    gross=sum(map(abs,contributions),F(0))
    # Enumerate the simultaneous error rectangle's vertices for the small cases.
    if len(qty)<=5:
        bound=max(abs(sum((q*e*sign for q,e,sign in zip(qty,eps,signs)),F(0))) for signs in product((-1,1),repeat=len(qty)))
    else:
        bound=sum((q*(e if q>=0 else -e) for q,e in zip(qty,eps)),F(0))
    for name,values in [('unit_errors',errors),('position_contributions',contributions)]:
        a.eq(len(r[name]),len(values),'book shape')
        for actual,v in zip(r[name],values):a.eq(actual,v,'book '+name)
    unitpasses=[-e<=v<=e for v,e in zip(errors,eps)]
    a.eq(r['unit_passes'],unitpasses,'all unit bounds')
    for name,v in [('signed_error',signed),('gross_comparison_error',gross),('bound_from_unit_tolerances',bound)]:a.eq(r[name],v,'book '+name)
    a.eq(r['signed_pass'],abs(signed)<=F(b['signed_error_limit']),'signed gate')
    a.eq(r['gross_pass'],gross<=F(b['gross_error_limit']),'gross gate')
    a.close(r['unit_rmse_approx'],math.sqrt(float(sum((e*e for e in errors),F(0))/len(errors))),'unit RMSE')

    errors=list(map(F,data['holdout']['forecast_errors']));n=len(errors);r=result['holdout']
    mean=sum(errors,F(0))/n;mse=sum((e*e for e in errors),F(0))/n
    # Pairwise differences provide a separate variance identity.
    variance=sum(((errors[i]-errors[j])**2 for i in range(n) for j in range(i+1,n)),F(0))/(n*(n-1))
    for name,v in [('observations',n),('mean_error',mean),('mean_squared_error',mse),('sample_variance',variance)]:a.eq(r[name],v,'holdout '+name)
    a.eq(mse,F(n-1,n)*variance+mean*mean,'variance-bias identity')
    a.close(r['rmse_approx'],math.sqrt(float(mse)),'holdout RMSE')
    a.close(r['iid_standard_error_if_assumed_approx'],math.sqrt(float(variance/n)),'conditional IID SE')

    d=data['decision'];e=d['exception'];r=result['decision']
    active=e['enabled'] and e['approver']!=d['owner'] and e['approver']!=d['challenger'] and date.fromisoformat(d['as_of'])<=date.fromisoformat(e['expires'])
    allowed=F(d['ordinary_limit'])
    if active and F(e['notional_limit'])>allowed:allowed=F(e['notional_limit'])
    expected={}
    expected['numeric_benchmark']=abs(pv[1]-pv[0])<=F(data['bond']['price_tolerance'])
    expected['curve_scope']=curve_spread<=F(data['curve_family']['spread_limit'])
    expected.update(book_units=all(unitpasses),book_signed=abs(signed)<=F(b['signed_error_limit']),book_gross=gross<=F(b['gross_error_limit']),
                    version_binding=d['requested_version']==d['reviewed_version'],independent_challenge=d['owner']!=d['challenger'],
                    fresh_evidence=d['data_age_days']<=d['max_data_age_days'],notional_limit=F(d['requested_notional'])<=allowed)
    a.eq(r['effective_notional_limit'],allowed,'effective size limit');a.eq(r['exception_valid_for_size_only'],active,'size exception validity')
    a.eq(r['checks'],expected,'all independent policy gates')
    failures=[k for k,v in expected.items() if not v]
    a.eq(r['failed_gates'],failures,'ordered gate failures')
    a.eq(r['recommendation'],'reject_requested_use' if failures else 'eligible_with_stated_limits','recommendation')


class Fragment(HTMLParser):
    def __init__(self):
        super().__init__();self.stack=[];self.ids=[];self.worked=self.exercises=self.solutions=0;self.sources=set()
    def handle_starttag(self,tag,attrs):
        d=dict(attrs);need(tag!='h1','chapter title generated once')
        if 'id' in d:self.ids.append(d['id'])
        if 'data-source' in d:self.sources.add(d['data-source'])
        if tag=='aside' and 'worked' in d.get('class','').split():self.worked+=1
        if tag=='li' and self.stack and self.stack[-1][0]=='ol':
            if 'exercises' in self.stack[-1][1].get('class','').split():self.exercises+=1
            if any(t=='details' and 'solutions' in x.get('class','').split() for t,x in self.stack):self.solutions+=1
        if tag not in ('br','hr','img','input','meta','link'):self.stack.append((tag,d))
    def handle_endtag(self,tag):
        need(self.stack and self.stack[-1][0]==tag,'balanced fragment '+tag);self.stack.pop()


def replace(data,path,value):
    new=deepcopy(data);node=new
    for key in path[:-1]:node=node[key]
    node[path[-1]]=value
    return new


def check():
    a=Audit();raw=json.loads((ASSETS/'v10-c12-inputs.json').read_text());original=deepcopy(raw);capture=StringIO()
    with redirect_stdout(capture),redirect_stderr(capture):
        run=runpy.run_path(str(ASSETS/'v10-c12-analysis.py'))['run'];result=run(raw)
    a.eq(capture.getvalue(),'','quiet import/API');a.eq(raw,original,'input immutability')
    a.eq(result,json.loads((ASSETS/'v10-c12-output.json').read_text()),'frozen output regeneration')
    audit_evidence(a,raw,result)

    # Fresh problems and explicit quantitative anchors; prose proofs are separately audited.
    for value,expected in [(50*F('0.99')+1050*F('0.95'),F(1047)),(50*F('0.99')+1050*F('0.94'),F(2073,2)),
                           (-20*1050*(F('.94')-F('.95')),F(210)),(88-6*F(1,2),F(85)),(88+6*F(1,2),F(91)),
                           (fitted_value(F(1),F('1.1'),F(99),F('98.9'),F(3)),F(97)),
                           (fitted_value(F(1),F('1.1'),F('98.99'),F('98.91'),F(3)),F('97.39')),
                           (100*F('.01')+50*F('.03')+200*F('.005'),F('3.5')),
                           (F(10,8),F(5,4)),(2000000*F('.0005'),F(1000)),(F(12-5-4),F(3)),(F(8-5-4),F(-1)),
                           ((F(3)-1)/(F('1.5')-1),F(4)),(10*F('.1')+20*F('.2'),F(5))]:a.eq(value,expected,'exercise/retention arithmetic')
    for rho,target in [(F(1),1000.0),(F(0),500*math.sqrt(2)),(F(-1),0.0)]:a.close(math.sqrt(float(2*500**2*(1+rho))),target,'correlated-error scenario')

    scenarios=[]
    for tenor in ('0','1','1.5','2','3'):
        scenarios.append(('curve tenor '+tenor,replace(raw,('curve_family','requested_tenor'),tenor)))
    for lower,upper in (('0','0'),('-0.5','0.5'),('-1','-1')):
        x=replace(raw,('curve_family','curvature_lower'),lower);x['curve_family']['curvature_upper']=upper;scenarios.append(('restricted family',x))
    for second,target in (('1.1','3'),('1.1','1.05'),('1.0001','10'),('5','0')):
        x=replace(raw,('conditioning','second_tenor'),second);x['conditioning']['target_tenor']=target;scenarios.append(('conditioning boundaries',x))
    for path,value in [(('bond','position'),'-40'),(('bond','cash_flows'),['0','0','0']),
                       (('bond','cash_flows'),['-100','100','0']),(('book','positions'),['200','150','100']),
                       (('book','positions'),['0','0','0']),(('book','candidate_prices'),['100.1','80','50']),
                       (('holdout','forecast_errors'),['2']*8),(('holdout','forecast_errors'),['-1','1']*4)]:
        scenarios.append(('financial intervention',replace(raw,path,value)))
    repaired=deepcopy(raw);repaired['bond']['candidate_discounts']=deepcopy(raw['bond']['benchmark_discounts'])
    repaired['curve_family']['requested_tenor']='2';repaired['book']['candidate_prices']=deepcopy(raw['book']['benchmark_prices'])
    scenarios.append(('repaired',repaired))
    for path,value in [(('decision','exception','expires'),'2026-10-05'),(('decision','exception','expires'),'2026-10-06'),
                       (('decision','exception','enabled'),False),(('decision','exception','approver'),'developer_a'),
                       (('decision','exception','approver'),'reviewer_b'),(('decision','exception','notional_limit'),'10000'),
                       (('decision','requested_notional'),'120000'),(('decision','requested_notional'),'120000.01'),
                       (('decision','requested_version'),'sable_3'),(('decision','challenger'),'developer_a'),
                       (('decision','data_age_days'),5),(('decision','data_age_days'),6)]:
        scenarios.append(('policy boundary',replace(repaired,path,value)))
    expired=replace(repaired,('decision','exception','expires'),'2026-10-05');expired['decision']['requested_notional']='50000'
    scenarios.append(('ordinary limit without exception',expired))
    for label,scenario in scenarios:
        before=deepcopy(scenario);reported=run(scenario);audit_evidence(a,scenario,reported);a.eq(scenario,before,label+' immutability');a.interventions+=1
    a.eq(run(repaired)['decision']['failed_gates'],[],'repaired has no failures')
    a.eq(run(expired)['decision']['recommendation'],'eligible_with_stated_limits','expired exception ordinary-size permission')
    a.eq(result['decision']['failed_gates'],['numeric_benchmark','curve_scope','book_signed','book_gross'],'worked example 5 exact baseline')

    invalid=[]
    for group in raw:
        x=deepcopy(raw);del x[group];invalid.append(x)
    x=deepcopy(raw);x['extra']=0;invalid.append(x)
    for group in ('bond','curve_family','conditioning','book','holdout','decision'):
        x=deepcopy(raw);x[group]['extra']=0;invalid.append(x)
        invalid.append(replace(raw,(group,),[]))
    for value in (True,1,0.1,None,'NaN','Infinity','1e2',' 1','1 ','1/0','1/00','1000000000','0.000000001','--1'):
        invalid.append(replace(raw,('bond','position'),value))
    for path,values in [(('bond','cash_flows'),([],['1000001'],['0']*25)),
                        (('bond','benchmark_discounts'),(['0','1','1'],['0.0001','1','1'],['3.1','1','1'],['1'])),
                        (('bond','price_tolerance'),('-1','101')),
                        (('curve_family','price_at_one'),('89.9','105.1')),
                        (('curve_family','price_at_two'),('84.9','110.1')),
                        (('curve_family','curvature_lower'),('-1.1','1.1')),
                        (('curve_family','requested_tenor'),('-0.1','3.1')),
                        (('conditioning','second_tenor'),('1','0','1.00001','5.1')),
                        (('conditioning','target_tenor'),('-1','10.1')),
                        (('conditioning','quote_error_bound'),('-1','10.1')),
                        (('book','positions'),([],['1'],['10001','0','0'])),
                        (('book','candidate_prices'),(['-1','1','1'],['1000001','1','1'])),
                        (('book','unit_tolerances'),(['-1','1','1'],['101','1','1'])),
                        (('holdout','training_ids'),([],['same','same'],['hold_1'],['INVALID'],['a']*101)),
                        (('holdout','evaluation_ids'),(['one'],['hold_1']*8)),
                        (('holdout','forecast_errors'),(['1'],['1001']*8)),
                        (('holdout','contract'),('',)),
                        (('decision','as_of'),('2026-1-1','2026-02-30','1999-12-31','2101-01-01',None)),
                        (('decision','data_age_days'),(True,-1,366,'1',1.5)),
                        (('decision','requested_version'),('', 'bad version', 'v'*41,1)),
                        (('decision','requested_notional'),('-1','100000001')),
                        (('decision','exception','enabled'),(0,1,'true')),
                        (('decision','exception','reason'),('', '   ', 'a'*241, False))]:
        for value in values:invalid.append(replace(raw,path,value))
    x=replace(raw,('curve_family','curvature_lower'),'1');x['curve_family']['curvature_upper']='-1';invalid.append(x)
    for scenario in invalid:
        before=deepcopy(scenario)
        try:run(scenario)
        except ValueError:a.rejections+=1
        else:raise RuntimeError('Invalid contract accepted')
        a.eq(scenario,before,'rejected input remains unchanged')

    # Downloaded lab works independently from the checkout, under both Python modes.
    with tempfile.TemporaryDirectory() as td:
        folder=Path(td)
        for suffix in ('analysis.py','inputs.json','output.json','README.txt','manifest.json'):
            shutil.copy2(ASSETS/('v10-c12-'+suffix),folder)
        script=folder/'v10-c12-analysis.py'
        for flags in ([],['-O']):
            p=subprocess.run([sys.executable,*flags,str(script)],cwd=folder.parent,capture_output=True,text=True)
            a.eq(p.returncode,0,'isolated CLI status');a.eq(p.stderr,'','isolated CLI stderr');a.eq(json.loads(p.stdout),result,'isolated CLI values')
            out=folder/'generated.json'
            p=subprocess.run([sys.executable,*flags,str(script),'--output',str(out)],cwd=folder.parent,capture_output=True,text=True)
            a.eq(p.returncode,0,'quiet output status');a.eq(p.stdout,'','quiet output stdout');a.eq(json.loads(out.read_text()),result,'quiet output values')
            badcases=[json.dumps(invalid[0]),'{"schema":1,"schema":2}',json.dumps(raw).replace('"position": "40"','"position": NaN')]
            for badtext in badcases:
                bad=folder/'bad.json';bad.write_text(badtext);out.write_text('preserve existing result')
                p=subprocess.run([sys.executable,*flags,str(script),'--input',str(bad),'--output',str(out)],capture_output=True,text=True)
                a.eq(p.returncode!=0,True,'invalid CLI fails');a.eq(p.stdout,'','invalid CLI no result');a.eq(out.read_text(),'preserve existing result','invalid CLI atomic result');a.rejections+=1

    fragment=Fragment();fragment.feed((ROOT/'content/chapters/v10-c12.html').read_text())
    need(not fragment.stack,'complete HTML fragment');a.eq(len(fragment.ids),len(set(fragment.ids)),'unique anchors')
    a.eq(fragment.worked,5,'worked count');a.eq(fragment.exercises,10,'exercise count');a.eq(fragment.solutions,10,'solution count')
    proposed=json.loads((ROOT/'content/reviews/v10-c12-sources.json').read_text())['proposals']
    a.eq(fragment.sources,{p['id'] for p in proposed},'actually cited primary proposals')
    manifest=json.loads((ASSETS/'v10-c12-manifest.json').read_text())
    a.eq({item['file'] for item in manifest['files']},{'v10-c12-'+s for s in ('analysis.py','inputs.json','output.json','README.txt')},'complete payload manifest')
    for item in manifest['files']:
        payload=(ASSETS/item['file']).read_bytes();a.eq(len(payload),item['bytes'],'payload bytes');a.eq(hashlib.sha256(payload).hexdigest(),item['sha256'],'payload hash')
    for name in ('v10-c12-author.json','v10-c12.json'):
        path=ROOT/'content/reviews'/name
        if path.exists():
            record=json.loads(path.read_text())
            for item in record['reviewed_hashes']:
                payload=(ROOT/item['path']).read_bytes();a.eq(hashlib.sha256(payload).hexdigest(),item['sha256'],name+' bound artifact')
    return {'chapter':'v10-c12','status':'passed','comparisons':a.comparisons,
            'count_definition':'Executed exact/approximate numerical, intervention, protocol, structural and hash comparisons; qualitative require gates are not counted.',
            'invalid_inputs_rejected':a.rejections,'financial_interventions':a.interventions,'worked_examples':fragment.worked,'solved_exercises':fragment.exercises,
            'groups':['exact dated cash reconciliation','Gaussian calibration systems and null-direction perturbations',
                      'quote-error and position-error vertex bounds','pairwise variance and bias identities',
                      'size-only policy boundaries, portability, strict input and artifact bindings'],
            'limits':'Author recomputation and analytic proof review. No empirical validity, authenticated real authority, human certification or visual UI QA claimed.'}


if __name__=='__main__':
    print(json.dumps(check(),indent=2))
