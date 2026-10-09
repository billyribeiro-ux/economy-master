"""Bounded independent author checks for the original Cedar payment-control lab.

No model helper is an oracle. Job-slot matching, orthogonal-fit certificates,
first-valid identity sets and finite failure-state weights check separate claims.
check() is quiet, strict-JSON-safe and active under python -O. Machine-assisted
author validation is not separate peer acceptance or institutional certification.
"""
import contextlib
import copy
from fractions import Fraction as F
import hashlib
from html.parser import HTMLParser
import io
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
PREFIX='v11-c06'
PROJECT=ROOT/'content/projects'
MODEL=PROJECT/(PREFIX+'-analysis.py')
INPUT=PROJECT/(PREFIX+'-inputs.json')
OWNED=[
    'content/chapters/v11-c06.html',
    'content/projects/v11-c06-inputs.json',
    'content/projects/v11-c06-analysis.py',
    'content/projects/v11-c06-output.json',
    'content/projects/v11-c06-manifest.json',
    'content/projects/v11-c06-README.txt',
    'scripts/check_v11_c06.py',
    'content/reviews/v11-c06-author.json',
    'content/reviews/v11-c06-sources.json',
]
COUNTS={}


def need(condition,label):
    COUNTS['comparisons']+=1
    if not condition:
        raise ValueError('v11-c06 check: '+label)


def eq(actual,expected,label):
    need(actual==expected,label+': '+repr(actual)+' != '+repr(expected))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def strict(text):
    def unique(pairs):
        out={}
        for key,value in pairs:
            if key in out:raise ValueError('duplicate JSON key')
            out[key]=value
        return out
    def invalid(value):raise ValueError('nonfinite JSON constant: '+value)
    return json.loads(text,object_pairs_hook=unique,parse_constant=invalid)


def matched_jobs(payments,capacities):
    """Independent maximum cardinality matching to feasible dated service slots.

    An augmenting path can move an already matched job, unlike the model's EDF
    queue. No more than N copies per window are useful to N unit jobs.
    """
    slots=[t for t,n in enumerate(capacities,1) for _ in range(min(n,len(payments)))]
    owner={}
    def augment(i,visited):
        p=payments[i]
        for slot,t in enumerate(slots):
            if slot not in visited and p['release']<=t<=p['deadline']:
                visited.add(slot)
                if slot not in owner or augment(owner[slot],visited):
                    owner[slot]=i
                    return True
        return False
    return sum(augment(i,set()) for i in range(len(payments)))


def fit_certificate(data,out):
    theta=F(out['calibration']['rate_per_staff_cutoff'])
    xs=[r['staff'] for r in data['training']]
    ys=[r['throughput'] for r in data['training']]
    errors=[theta*x-y for x,y in zip(xs,ys)]
    sxx=sum(x*x for x in xs)
    eq(sum(x*e for x,e in zip(xs,errors)),0,'fit residual orthogonal to design')
    need(sxx>0,'positive quadratic curvature identifies unique fit')
    eq(list(map(F,out['calibration']['training_errors'])),errors,'reported residuals')
    sse=sum(e*e for e in errors)
    eq(F(out['calibration']['sum_squared_error']),sse,'squared residual norm')
    eq(F(out['calibration']['max_absolute_error']),max(map(abs,errors)),'maximum absolute residual')
    for displacement in (F(-3,7),F(2,5)):
        perturbed=sum(((theta+displacement)*x-y)**2 for x,y in zip(xs,ys))
        eq(perturbed-sse,sxx*displacement**2,'global quadratic minimizer certificate')
    for k,x in zip(out['capacity']['staff_only'],data['operation']['staff']):
        need(type(k) is int and k<=theta*x<k+1,'integer capacity floor certificate')
    eq(out['capacity']['constrained'],[min(a,b) for a,b in zip(out['capacity']['staff_only'],data['operation']['gateway_capacity'])],'two-resource bottleneck')
    chosen='staff_only' if data['operation']['deployed_rule']=='staff_only' else 'constrained'
    eq(out['capacity']['deployed'],out['capacity'][chosen],'deployed implementation identity')


def queue_certificate(data,result,capacities):
    inventory={p['id']:p for p in data['payments']}
    unit=F(data['unit_amount']);cash=F(data['opening_cash'])
    order=lambda key:(inventory[key]['deadline'],inventory[key]['release'],key)
    eq(len(result['rows']),data['horizon'],'one queue report per window')
    completed={}
    for t,row in enumerate(result['rows'],1):
        released={key for key,p in inventory.items() if p['release']<=t}
        available=released-set(completed)
        served=row['completed_ids']
        need(len(served)==len(set(served)) and set(served)<=available,'service consumes unique released pending jobs')
        eq(served,sorted(available,key=order)[:min(capacities[t-1],len(available))],'work conservation and EDF choice certificate')
        completed.update({key:t for key in served})
        left=released-set(completed)
        eq((row['cutoff'],row['arrivals'],row['available_before_service'],row['capacity'],row['unused_slots'],row['backlog_after']),
           (t,[p['id'] for p in data['payments'] if p['release']==t],len(available),capacities[t-1],capacities[t-1]-len(served),len(left)),
           'dated queue stock-flow reconciliation')
        eq(row['due_and_unfinished_ids'],sorted([key for key in left if inventory[key]['deadline']<=t],key=order),'uncompleted due obligations retained')
        eq((F(row['planned_cash_after']),F(row['planned_payment_liability_after'])),(cash-unit*len(completed),unit*(len(inventory)-len(completed))),'cash and liabilities fall together for proposed legitimate service')
    eq(result['completion_cutoffs'],completed,'completion map agrees with unique service rows')
    missed=[key for key,p in inventory.items() if key not in completed or completed[key]>p['deadline']]
    late=[key for key,p in inventory.items() if key in completed and completed[key]>p['deadline']]
    unfinished=[key for key in inventory if key not in completed]
    eq((result['deadline_missed_ids'],result['completed_late_ids'],result['unfinished_ids'],result['on_time_count'],result['all_deadlines_met']),
       (missed,late,unfinished,len(inventory)-len(missed),not missed),'deadline and stock status are distinct')
    matching=matched_jobs(data['payments'],capacities)
    eq(result['all_deadlines_met'],matching==len(inventory),'EDF all-on-time claim against independent augmenting-path matching')
    need(result['on_time_count']<=matching,'reported timely subset cannot exceed maximum feasible matching')
    return matching


def identity_certificate(data,out):
    """Find each instruction's first valid external row by a set-based scan.

    Unknown/premature/duplicate cash debits are retained; aggregation cannot
    infer identity. This oracle does not share the model's stateful classify loop.
    """
    rows=data['observed_settlements'];inventory={p['id']:p for p in data['payments']}
    first={}
    for key,p in inventory.items():
        candidates=[i for i,r in enumerate(rows) if r['id']==key and r['cutoff']>=p['release']]
        if candidates:first[key]=min(candidates)
    expected=[]
    for i,r in enumerate(rows):
        key,t=r['id'],r['cutoff']
        if key not in inventory:kind='unknown_instruction'
        elif t<inventory[key]['release']:kind='before_authorization'
        elif i!=first[key]:kind='duplicate_settlement'
        else:kind='authorized_on_time' if t<=inventory[key]['deadline'] else 'authorized_late'
        expected.append(dict(r,classification=kind))
    actual=out['observed_reconciliation']
    eq(actual['rows'],expected,'independent first-valid occurrence classification')
    anomalies=[{'id':r['id'],'cutoff':r['cutoff'],'reason':r['classification']} for r in expected if not r['classification'].startswith('authorized_')]
    missing=[key for key in inventory if key not in first]
    late=[key for key,i in sorted(first.items(),key=lambda pair:pair[1]) if rows[i]['cutoff']>inventory[key]['deadline']]
    eq((actual['anomalies'],actual['missing_instruction_ids'],actual['authorized_late_ids']),
       (anomalies,missing,late),'identity anomalies and separate late obligations')
    counts=[sum(r['cutoff']==t for r in rows) for t in range(1,data['horizon']+1)]
    eq((actual['slot_counts'],actual['acknowledgment_count'],actual['unique_authorized_settlements'],actual['on_time_count']),
       (counts,len(rows),len(first),len(first)-len(late)),'observation counts cannot infer discharged inventory')
    u=F(data['unit_amount']);m=len(rows);n=len(first)
    # Legitimate postings are (-u,-u,0); exceptions are (-u,0,-u).
    balances=(F(data['opening_cash'])-m*u,F(data['opening_payment_liability'])-n*u,F(data['opening_equity'])-(m-n)*u)
    eq(tuple(F(actual[k]) for k in ('closing_cash','closing_payment_liability','closing_equity')),balances,'independent journal-vector addition')
    eq(tuple(F(actual[k]) for k in ('cash_debits','authorized_liability_discharged','bank_borne_exception_loss')),(m*u,n*u,(m-n)*u),'debits versus discharges versus irrecoverable loss')
    eq(F(actual['identity_residual']),balances[0]-balances[1]-balances[2],'complete account identity')
    eq(actual['within_stipulated_capacity'],all(n<=c for n,c in zip(counts,out['capacity']['constrained'])),'observed capacity contradiction is reported')


def failure_certificate(data,out):
    risk=data['control_risk'];c=F(risk['common_failure_probability'])
    q=F(risk['first_miss_given_no_common']);r=F(risk['second_miss_given_no_common'])
    f=F(risk['second_control_coverage']);a=F(risk['unauthorized_attempt_probability'])
    states=[(c,True,True)]
    for first,p in ((True,q),(False,1-q)):
        for second,s in ((True,r),(False,1-r)):
            states.append(((1-c)*p*s,first,second))
    eq(sum(w for w,_,_ in states),1,'failure branches are a probability partition')
    m1=sum(w for w,x,y in states if x);m2=sum(w for w,x,y in states if y)
    joint=sum(w for w,x,y in states if x and y)
    conditional=sum(w*coverage for w,x,y in states for applied,coverage in ((False,1-f),(True,f)) if x and (y or not applied))
    escaped=F(0);mass=F(0)
    for attempted,p in ((False,1-a),(True,a)):
        for applied,coverage in ((False,1-f),(True,f)):
            for w,x,y in states:
                weight=p*coverage*w;mass+=weight
                if attempted and x and (y or not applied):escaped+=weight
    eq(mass,1,'full request/coverage/failure partition normalized')
    expected=escaped*risk['requests']*F(risk['loss_per_escape'])
    report=out['separate_control_experiment']
    eq(tuple(F(report[k]) for k in ('first_control_marginal_miss','second_control_marginal_miss','joint_miss_when_both_applied','incorrect_product_of_marginal_misses','escape_given_unauthorized_attempt','escape_per_request','expected_escapes','expected_loss')),
       (m1,m2,joint,m1*m2,conditional,escaped,escaped*risk['requests'],expected),'weighted state losses, coverage and marginal law')
    eq(joint-m1*m2,c*(1-c)*(1-q)*(1-r),'common-cause covariance factorization')
    eq(out['closure_gates']['expected_loss_within_fictional_bound'],expected<=F(data['closure']['maximum_expected_loss']),'exact fictional risk inequality')


def case(run,data,label):
    before=copy.deepcopy(data);buffer=io.StringIO()
    with contextlib.redirect_stdout(buffer),contextlib.redirect_stderr(buffer):out=run(data)
    eq(buffer.getvalue(),'','quiet API '+label)
    eq(data,before,'nonmutating input '+label)
    eq(strict(json.dumps(out,allow_nan=False)),out,'strict JSON output '+label)
    fit_certificate(data,out)
    queue_certificate(data,out['deployed_forecast'],out['capacity']['deployed'])
    queue_certificate(data,out['constrained_plan'],out['capacity']['constrained'])
    identity_certificate(data,out);failure_certificate(data,out)
    gates=out['closure_gates']
    eq(len(gates),12,'twelve distinct closure gates')
    need(all(type(v) is bool for v in gates.values()),'closure gate values are boolean')
    eq(out['failed_closure_gates'],[k for k,v in gates.items() if not v],'no failed gate omitted')
    eq(out['disposition'],'eligible_for_independent_closure_review' if all(gates.values()) else 'keep_incident_open_or_restrict_use','no favorable gate overrides failure')
    COUNTS['cases']+=1
    return out


def changed(base,path,value):
    data=copy.deepcopy(base);target=data
    for key in path[:-1]:target=target[key]
    target[path[-1]]=value
    return data


def financial_interventions(run,base,initial):
    cases=[]
    def exercise(data,label):
        COUNTS['intervention_groups']+=1
        result=case(run,data,label);cases.append((label,result));return result
    b=initial
    eq([r['backlog_after'] for r in b['constrained_plan']['rows']],[2,5,4,0],'worked1 backlogs')
    eq(b['constrained_plan']['deadline_missed_ids'],['B05','C01','C02','C03'],'worked1 exact missed IDs')
    eq((b['constrained_plan']['on_time_count'],b['deployed_forecast']['on_time_count']),(10,14),'fit-versus-use deadline consequence')
    eq(matched_jobs(base['payments'],[2,2,4,6]),10,'deadline cut attained by independent maximum matching')
    due3=sum(p['deadline']<=3 for p in base['payments'])
    eq(due3-sum([2,2,4]),4,'twelve due versus eight usable slots proves necessary repair')
    eq(tuple(F(b['observed_reconciliation'][k]) for k in ('closing_cash','closing_payment_liability','closing_equity','bank_borne_exception_loss')),(60,10,50,10),'worked2 final accounts')
    eq(F(b['separate_control_experiment']['expected_loss']),F('42.1'),'worked3 weighted baseline loss')
    eq(F(b['calibration']['rate_per_staff_cutoff']),2,'worked4 fitted rate')
    honest=changed(base,['operation','deployed_rule'],'bottleneck')
    r=exercise(honest,'mapping repair alone')
    eq((r['closure_gates']['runtime_bottleneck_included'],r['constrained_plan']['on_time_count']),(True,10),'honest mapping supplies no new slots')
    retimed=changed(honest,['operation','gateway_capacity'],[2,2,8,2])
    r=exercise(retimed,'timely resource counterfactual with unchanged incident log')
    eq([z['backlog_after'] for z in r['constrained_plan']['rows']],[2,5,0,0],'resource repair all-on-time schedule')
    eq((r['constrained_plan']['all_deadlines_met'],r['closure_gates']['observed_records_within_stated_capacity']),(True,False),'new reservation cannot rewrite old window4 evidence')
    # Construct an independent good rehearsal; do not draw it from the forecast.
    rehearsal=copy.deepcopy(retimed);rehearsal['run_label']='new_authorized_rehearsal'
    schedule=[(1,['A01','A02']),(2,['A03','A04']),(3,['B01','B02','B03','B04','B05','C01','C02','C03']),(4,['D01','D02'])]
    rehearsal['observed_settlements']=[{'id':key,'cutoff':t} for t,ids in schedule for key in ids]
    rehearsal['control_risk']['common_failure_probability']='0';rehearsal['control_risk']['second_control_coverage']='1'
    for key in ('legal_basis_verified','restore_evidence_verified','replay_evidence_verified','external_confirmation_verified'):rehearsal['closure'][key]=True
    rehearsal['closure']['reviewed_version']=rehearsal['closure']['deployed_version']='capacity_v2'
    good=exercise(rehearsal,'separately labeled correct rehearsal')
    eq(good['disposition'],'eligible_for_independent_closure_review','all declared evidence and numerical gates pass, not real approval')
    for field,value,gate in [
        ('deployed_version','unreviewed_v3','reviewed_version_matches_deployment'),
        ('approver',rehearsal['closure']['preparer'],'distinct_preparer_and_approver_declared'),
        ('reviewer',rehearsal['closure']['developer'],'independent_model_challenger_declared'),
        ('legal_basis_verified',False,'legal_basis_evidence_declared'),
        ('replay_evidence_verified',False,'restore_replay_external_evidence_declared')]:
        r=exercise(changed(rehearsal,['closure',field],value),'closure evidence '+field)
        eq(r['failed_closure_gates'],[gate],'each distinct material evidence defect blocks closure')
    no_duplicate=copy.deepcopy(base);del no_duplicate['observed_settlements'][11]
    r=exercise(no_duplicate,'remove duplicate only')
    a=r['observed_reconciliation']
    eq(tuple(F(a[k]) for k in ('cash_debits','authorized_liability_discharged','bank_borne_exception_loss','closing_cash','closing_payment_liability','closing_equity')),(130,130,0,70,10,60),'exercise2 remove-only accounts')
    eq((a['on_time_count'],len(a['authorized_late_ids']),a['missing_instruction_ids']),(10,3,['C03']),'remove-only retains missing and late obligations')
    replaced=changed(base,['observed_settlements',11,'id'],'C03')
    r=exercise(replaced,'replace with late missing ID')
    a=r['observed_reconciliation']
    eq(tuple(F(a[k]) for k in ('cash_debits','authorized_liability_discharged','bank_borne_exception_loss','closing_cash','closing_payment_liability','closing_equity')),(140,140,0,60,0,60),'exercise2 replacement accounts')
    eq((a['on_time_count'],len(a['authorized_late_ids']),a['missing_instruction_ids']),(10,4,[]),'identity repair cannot undo lateness')
    r=exercise(changed(base,['observed_settlements',11,'id'],'X99'),'unknown debit')
    eq(r['observed_reconciliation']['anomalies'],[{'id':'X99','cutoff':4,'reason':'unknown_instruction'}],'unknown paid ID is meaningful anomaly')
    r=exercise(changed(base,['observed_settlements',1,'id'],'C03'),'premature debit')
    eq(tuple(F(r['observed_reconciliation'][k]) for k in ('closing_cash','closing_payment_liability','closing_equity','bank_borne_exception_loss')),(60,20,40,20),'premature payment cannot discharge future authorization')
    later_valid=changed(base,['observed_settlements',1,'id'],'C03')
    later_valid['observed_settlements'][11]['id']='C03'
    r=exercise(later_valid,'proper settlement after earlier premature debit')
    eq((r['observed_reconciliation']['rows'][11]['classification'],r['observed_reconciliation']['missing_instruction_ids'],F(r['observed_reconciliation']['bank_borne_exception_loss'])),('authorized_late',['A02'],F(10)),'premature debit does not preclude later legitimate discharge')
    full=changed(base,['control_risk','second_control_coverage'],'1')
    r=exercise(full,'full coverage with common failure')
    eq(F(r['separate_control_experiment']['expected_loss']),F('34.5'),'coverage floor exceeds20')
    exact=changed(full,['control_risk','common_failure_probability'],'1/49')
    r=exercise(exact,'exact common-cause boundary')
    eq(F(r['separate_control_experiment']['expected_loss']),20,'exact maximum c boundary')
    r=exercise(changed(exact,['control_risk','common_failure_probability'],'0.02040817'),'above common-cause boundary')
    eq(r['closure_gates']['expected_loss_within_fictional_bound'],False,'strictly excessive c rejected by decision gate')
    no_common=changed(base,['control_risk','common_failure_probability'],'0')
    r=exercise(changed(no_common,['control_risk','second_control_coverage'],'0.75'),'exact coverage boundary')
    eq(F(r['separate_control_experiment']['expected_loss']),20,'minimum coverage boundary')
    r=exercise(changed(no_common,['control_risk','second_control_coverage'],'0.74999999'),'below coverage boundary')
    eq(r['closure_gates']['expected_loss_within_fictional_bound'],False,'just insufficient coverage fails')
    eq(F(b['separate_control_experiment']['expected_loss'])-F(good['separate_control_experiment']['expected_loss'])-12,F('20.1'),'exercise4 same-horizon net benefit')
    # Nonzero training residual tests both fit curvature and its decision use.
    noisy=changed(rehearsal,['training',1,'throughput'],5)
    r=exercise(noisy,'nonzero fitted error with unchanged declared tolerance')
    eq(r['closure_gates']['training_error_within_stated_tolerance'],False,'a fit defect cannot be hidden by otherwise good evidence')
    recovery=copy.deepcopy(rehearsal)
    recovery.update(run_label='separate_recovery',horizon=2,opening_cash='40',opening_payment_liability='30',opening_equity='10',payments=[{'id':key,'release':1,'deadline':2} for key in ['E01','E02','E03']])
    recovery['operation']={'staff':[2,2],'gateway_capacity':[4,4],'deployed_rule':'bottleneck'}
    recovery['observed_settlements']=[{'id':'E01','cutoff':1},{'id':'E02','cutoff':1},{'id':'E02','cutoff':2},{'id':'E03','cutoff':2}]
    r=exercise(recovery,'blind replay after restored-state omission')
    eq(tuple(F(r['observed_reconciliation'][k]) for k in ('closing_cash','closing_payment_liability','closing_equity')),(0,0,0),'exercise6 duplicate replay consumes equity')
    safe=copy.deepcopy(recovery);del safe['observed_settlements'][2]
    r=exercise(safe,'external reconciliation before replay')
    eq(tuple(F(r['observed_reconciliation'][k]) for k in ('closing_cash','closing_payment_liability','closing_equity')),(10,0,10),'exercise6 safe replay preserves equity')
    one=copy.deepcopy(rehearsal)
    one.update(run_label='release_timing',horizon=2,opening_cash='10',opening_payment_liability='10',opening_equity='0',payments=[{'id':'J01','release':2,'deadline':2}],observed_settlements=[])
    one['operation']={'staff':[1,1],'gateway_capacity':[1,0],'deployed_rule':'bottleneck'}
    r=exercise(one,'capacity before release is unusable')
    eq(r['constrained_plan']['all_deadlines_met'],False,'equal total slots not sufficient with release constraint')
    r=exercise(changed(one,['operation','gateway_capacity'],[0,1]),'slot supplied at release and deadline')
    eq(r['constrained_plan']['all_deadlines_met'],True,'same total capacity at useful date is sufficient')
    # Retention and risk endpoints: exact algebra, not broad random testing.
    eq(F(1,10)+F(9,10)*F(1,10)**2,F('0.109'),'retention common joint')
    eq((F(1,10)+F(9,10)*F(1,10))**2,F('0.0361'),'retention marginal product')
    retention=copy.deepcopy(one)
    retention.update(run_label='retention_queue',opening_cash='50',opening_payment_liability='50',opening_equity='0',payments=[{'id':'R'+str(i),'release':1 if i<3 else 2,'deadline':1 if i<3 else 2} for i in range(5)])
    retention['operation']={'staff':[1,2],'gateway_capacity':[2,3],'deployed_rule':'bottleneck'}
    r=exercise(retention,'retention queue')
    eq(([z['backlog_after'] for z in r['constrained_plan']['rows']],r['constrained_plan']['on_time_count']),([1,0],4),'retention late work clears final queue')
    for c,q1,q2,f,expected in [('1','0','0','1','500'),('0','0','1','0','0'),('0','1','0','1','0'),('0','1','0','0','500')]:
        d=copy.deepcopy(base);d['control_risk'].update(common_failure_probability=c,first_miss_given_no_common=q1,second_miss_given_no_common=q2,second_control_coverage=f)
        r=exercise(d,'failure-law endpoint '+','.join([c,q1,q2,f]))
        eq(F(r['separate_control_experiment']['expected_loss']),F(expected),'endpoint loss has exact statewise meaning')
    return cases


def invalid_cases(run,base):
    alterations=[
        (['schema'],'wrong'),(['provenance'],'observed real incident'),(['run_label'],'bad label'),
        (['horizon'],True),(['horizon'],0),(['horizon'],13),(['unit_amount'],'0'),
        (['unit_amount'],10),(['unit_amount'],'1e1'),(['unit_amount'],'01'),(['unit_amount'],'1/0'),
        (['unit_amount'],'0/2'),(['unit_amount'],' 10'),(['unit_amount'],'0.000000001'),
        (['opening_cash'],'199'),(['opening_payment_liability'],'130'),(['opening_equity'],'-60'),
        (['payments'],[]),(['payments',1,'id'],'A01'),(['payments',0,'release'],3),
        (['payments',0,'deadline'],0),(['payments',0,'deadline'],True),
        (['training'],[{'staff':0,'throughput':1},{'staff':0,'throughput':0}]),
        (['training',0,'staff'],-1),(['training',0,'throughput'],True),
        (['operation','staff'],[1,1]),(['operation','gateway_capacity',0],-1),
        (['operation','deployed_rule'],'unknown'),(['operation','staff',0],1.0),
        (['observed_settlements',0,'cutoff'],4),(['observed_settlements',0,'id'],'9invalid'),
        (['control_risk','requests'],0),(['control_risk','requests'],True),
        (['control_risk','common_failure_probability'],'1.00000001'),
        (['control_risk','second_control_coverage'],'-0.01'),
        (['control_risk','loss_per_escape'],25),(['closure','legal_basis_verified'],1),
        (['closure','maximum_expected_loss'],'-1'),(['closure','reviewer'],None),
    ]
    bad=[changed(base,path,value) for path,value in alterations]
    extra=copy.deepcopy(base);extra['unmodeled_credit']=1;bad.append(extra)
    missing=copy.deepcopy(base);del missing['closure'];bad.append(missing)
    debtless=copy.deepcopy(base);debtless.update(opening_cash='130',opening_equity='-10');bad.append(debtless)
    excessive=copy.deepcopy(base);excessive['observed_settlements'] += [{'id':'X99','cutoff':4}]*7;bad.append(excessive)
    for i,data in enumerate(bad):
        original=copy.deepcopy(data);buf=io.StringIO()
        with contextlib.redirect_stdout(buf),contextlib.redirect_stderr(buf):
            try:run(data)
            except ValueError:COUNTS['invalid_data_rejections']+=1
            else:raise ValueError('invalid API data accepted: '+str(i))
        eq(buf.getvalue(),'','invalid API remains quiet')
        eq(data,original,'invalid input remains unchanged')


class Chapter(HTMLParser):
    def __init__(self):
        super().__init__();self.ids=[];self.sources=[];self.hrefs=[];self.worked=0
        self.stack=[];self.exercises=0;self.solutions=0
    def handle_starttag(self,tag,attrs):
        a=dict(attrs);classes=a.get('class','').split()
        if 'id' in a:self.ids.append(a['id'])
        if 'data-source' in a:self.sources.append(a['data-source'])
        if 'href' in a:self.hrefs.append(a['href'])
        if tag=='aside' and 'worked' in classes:self.worked+=1
        if tag=='li':
            if any(t=='ol' and 'exercises' in c for t,c in self.stack):self.exercises+=1
            if any(t=='details' and 'solutions' in c for t,c in self.stack):self.solutions+=1
        if tag not in ('area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'):self.stack.append((tag,classes))
    def handle_endtag(self,tag):
        if not self.stack or self.stack[-1][0]!=tag:raise ValueError('unbalanced chapter markup '+tag)
        self.stack.pop()


def bindings_and_structure():
    chapter=ROOT/'content/chapters/v11-c06.html';parser=Chapter();parser.feed(chapter.read_text(encoding='utf-8'));parser.close()
    eq(parser.stack,[],'balanced chapter fragment')
    eq(len(parser.ids),len(set(parser.ids)),'unique local IDs')
    eq((parser.worked,parser.exercises,parser.solutions),(4,8,8),'four worked cases and eight exact solved prompts')
    eq(set(parser.sources),{'v11-c06-bcbs-resilience2021','v10-c12-fed-letter','v10-c12-fed-guidance'},'specific primary source routes')
    assets=[PREFIX+suffix for suffix in ('-inputs.json','-analysis.py','-output.json','-manifest.json','-README.txt')]
    eq(sorted(h for h in parser.hrefs if h.startswith(PREFIX+'-')),sorted(assets),'all five flat reader asset links')
    need(not any(h.startswith('projects/') for h in parser.hrefs),'builder flat attachment convention')
    sources=strict((ROOT/'content/reviews/v11-c06-sources.json').read_text())
    eq([p['id'] for p in sources['proposals']],['v11-c06-bcbs-resilience2021'],'only new source proposal')
    eq(set(sources['reused_source_ids']),{'v10-c12-fed-letter','v10-c12-fed-guidance'},'reused exact guidance source IDs')
    eq(sources['proposals'][0]['url'],'https://www.bis.org/publications/202103-guidelines-principles-operational-resilience.pdf','actual final BCBS PDF route')
    eq(sources['unresolved_source_items'],[],'no unresolved source retrieval item')
    manifest=strict((PROJECT/(PREFIX+'-manifest.json')).read_text())
    expected={PREFIX+s for s in ('-inputs.json','-analysis.py','-output.json','-README.txt')}
    eq({r['file'] for r in manifest['files']},expected,'exact four portable payloads in manifest')
    eq(len(manifest['files']),4,'no duplicate manifest member')
    for item in manifest['files']:
        path=PROJECT/item['file']
        eq((item['bytes'],item['sha256']),(path.stat().st_size,digest(path)),'manifest byte binding '+item['file'])
    review=strict((ROOT/'content/reviews/v11-c06-author.json').read_text())
    bound=review['reviewed_hashes'];wanted=set(OWNED)-{'content/reviews/v11-c06-author.json'}
    eq({r['path'] for r in bound},wanted,'author binds eight exact nonself files')
    eq(len(bound),8,'no duplicate author binding')
    for item in bound:
        path=ROOT/item['path']
        eq((item['bytes'],item['sha256']),(path.stat().st_size,digest(path)),'author byte binding '+item['path'])
    eq(len(review['exercise_audit']),8,'all eight exact prompt audits recorded')
    eq(len(review['worked_audit']),4,'all four complete worked audits recorded')
    return review


def portable_cli(base,expected):
    with tempfile.TemporaryDirectory(prefix='v11-c06-portable-') as directory:
        folder=Path(directory);model=folder/MODEL.name;input_path=folder/INPUT.name
        shutil.copy2(MODEL,model);shutil.copy2(INPUT,input_path)
        env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1')
        for optimized in (False,True):
            command=[sys.executable]+(['-O'] if optimized else [])+[str(model)]
            def execute(args):return subprocess.run(command+args,cwd='/',env=env,text=True,capture_output=True,timeout=20)
            result=execute([])
            eq((result.returncode,result.stderr),(0,''),'portable default CLI mode '+str(optimized))
            eq(strict(result.stdout),expected,'portable sibling input independent of cwd')
            output=folder/'result.json';result=execute(['--input',str(input_path),'--output',str(output)])
            eq((result.returncode,result.stdout,result.stderr),(0,'',''),'portable output-file CLI quiet success')
            eq(strict(output.read_text()),expected,'portable explicit paths saved full result')
            for protected in (input_path,model):
                for alias in ('direct','symbolic','hard'):
                    candidate=protected if alias=='direct' else folder/(protected.name+'.'+alias)
                    if alias!='direct':
                        if candidate.exists() or candidate.is_symlink():candidate.unlink()
                        if alias=='symbolic':candidate.symlink_to(protected)
                        else:os.link(protected,candidate)
                    before=(input_path.read_bytes(),model.read_bytes())
                    result=execute(['--input',str(input_path),'--output',str(candidate)])
                    need(result.returncode!=0 and result.stdout=='' and result.stderr.startswith('error:'),'protected output alias must reject')
                    eq((input_path.read_bytes(),model.read_bytes()),before,'protected input/model bytes unchanged')
                    COUNTS['protected_output_rejections']+=1
                    if alias!='direct':candidate.unlink()
            malformed=[
                '{"schema":1,"schema":2}',
                input_path.read_text().replace('"opening_cash": "200"','"opening_cash": NaN'),
                json.dumps(changed(base,['horizon'],True)),
                ' '*1000001,
            ]
            for text in malformed:
                bad=folder/'invalid.json';bad.write_text(text);output.write_text('PRESERVE OUTPUT\n')
                result=execute(['--input',str(bad),'--output',str(output)])
                need(result.returncode!=0 and result.stdout=='' and result.stderr.startswith('error:'),'invalid CLI contract rejected before output')
                eq(output.read_text(),'PRESERVE OUTPUT\n','invalid input leaves existing output unchanged')
                COUNTS['invalid_data_rejections']+=1
        return {'model_input_portable':True,'normal_and_optimized_cli':True,'output_alias_guards':'direct, symbolic and hard links for input and model in both modes'}


def check():
    global COUNTS
    COUNTS={'comparisons':0,'cases':0,'intervention_groups':0,'invalid_data_rejections':0,'protected_output_rejections':0}
    buffer=io.StringIO()
    with contextlib.redirect_stdout(buffer),contextlib.redirect_stderr(buffer):model=runpy.run_path(str(MODEL))
    eq(buffer.getvalue(),'','quiet model import')
    data=strict(INPUT.read_text());output=case(model['run'],data,'baseline incident')
    eq(output,strict((PROJECT/(PREFIX+'-output.json')).read_text()),'saved baseline reproduction after independent certificates')
    financial_interventions(model['run'],data,output)
    invalid_cases(model['run'],data)
    portable=portable_cli(data,output)
    bindings_and_structure()
    summary={'chapter':PREFIX,'status':'passed',**COUNTS,
             'worked_examples':4,'solved_exercises':8,'independent_methods':['orthogonal least-squares and curvature certificates','unit-job dated-slot augmenting-path matching','queue and account stock-flow certificates','first-valid external identity sets','finite request/coverage/common-cause failure states'],
             'portable':portable,'limits':'Bounded synthetic author validation; no real control effectiveness, legal conclusion, cyber certification, human academic review or publication acceptance.'}
    json.dumps(summary,allow_nan=False)
    return summary


if __name__=='__main__':
    print(json.dumps(check(),indent=2,allow_nan=False))
