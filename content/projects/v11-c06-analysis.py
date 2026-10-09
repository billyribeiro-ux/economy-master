"""Cedar critical-payment controls: original bounded operational teaching lab.

All service capacities, probabilities, loss bounds and legal/evidence declarations
are synthetic. The queue is a deterministic unit-job plan, not a production
payment system. run(data) is quiet and nonmutating; fractions remain exact strings.
"""
import argparse
from fractions import Fraction as F
import json
from pathlib import Path
import re
import sys

SCHEMA = 'v11-c06-cedar-1'
PROVENANCE = 'Original synthetic Cedar critical-payment operation; no observed incident, estimated control effectiveness, legal conclusion or real approval.'
IDENTIFIER = re.compile(r'[A-Za-z][A-Za-z0-9_-]{0,39}\Z')
NUMBER = re.compile(r'-?(?:(?:0|[1-9][0-9]{0,8})(?:\.[0-9]{1,8})?|[1-9][0-9]{0,8}/[1-9][0-9]{0,8})\Z')


def require(condition, label):
    if not condition:
        raise ValueError(label)


def fields(value, names, label):
    require(type(value) is dict and set(value)==set(names.split()),label+': exact fields required')


def integer(value, low, high, label):
    require(type(value) is int and low<=value<=high,label+': bounded integer required')
    return value


def number(value, low, high, label):
    require(type(value) is str and len(value)<=32 and NUMBER.fullmatch(value) is not None,
            label+': bounded plain decimal or rational string required')
    x=F(value)
    require(low<=x<=high,label+': outside declared range')
    return x


def identifier(value,label):
    require(type(value) is str and IDENTIFIER.fullmatch(value) is not None,label+': invalid identifier')
    return value


def validate(data):
    fields(data,'schema provenance run_label horizon unit_amount opening_cash opening_payment_liability opening_equity payments training operation observed_settlements control_risk closure','input')
    require(data['schema']==SCHEMA and data['provenance']==PROVENANCE,'unknown schema or provenance')
    identifier(data['run_label'],'run_label')
    horizon=integer(data['horizon'],1,12,'horizon')
    unit=number(data['unit_amount'],F(1,100000000),1000000,'unit_amount')
    cash=number(data['opening_cash'],0,999999999,'opening_cash')
    debt=number(data['opening_payment_liability'],0,999999999,'opening_payment_liability')
    equity=number(data['opening_equity'],-999999999,999999999,'opening_equity')
    require(cash==debt+equity,'opening cash-only balance sheet must reconcile')
    payments=data['payments']
    require(type(payments) is list and 1<=len(payments)<=200,'payments:1–200 instructions required')
    ids=set()
    for p in payments:
        fields(p,'id release deadline','payment')
        key=identifier(p['id'],'payment id');require(key not in ids,'duplicate authorized payment id');ids.add(key)
        release=integer(p['release'],1,horizon,'release')
        deadline=integer(p['deadline'],1,horizon,'deadline')
        require(release<=deadline,'instruction cannot first arrive after its own contractual deadline')
    require(debt==unit*len(payments),'opening payment liability must equal the complete authorized instruction inventory')
    require(cash>=debt,'this operational lab requires funding for all authorized payments')
    training=data['training']
    require(type(training) is list and 2<=len(training)<=20,'training:2–20 rows required')
    for row in training:
        fields(row,'staff throughput','training row')
        integer(row['staff'],0,50,'training staff');integer(row['throughput'],0,500,'training throughput')
    require(sum(row['staff']**2 for row in training)>0,'training cannot identify a slope with all staffing zero')
    op=data['operation']
    fields(op,'staff gateway_capacity deployed_rule','operation')
    for key,high in [('staff',50),('gateway_capacity',500)]:
        require(type(op[key]) is list and len(op[key])==horizon,key+': one entry per cutoff required')
        for x in op[key]:integer(x,0,high,key)
    require(op['deployed_rule'] in ('staff_only','bottleneck') and type(op['deployed_rule']) is str,'unknown deployed_rule')
    observed=data['observed_settlements']
    require(type(observed) is list and len(observed)<=400,'observed_settlements: at most400 rows')
    previous=0
    for row in observed:
        fields(row,'id cutoff','observed settlement')
        identifier(row['id'],'observed id')
        cutoff=integer(row['cutoff'],1,horizon,'observed cutoff')
        require(cutoff>=previous,'observed settlement log must be chronological');previous=cutoff
    require(cash>=unit*len(observed),'observed cash debits require credit outside this funded lab')
    risk=data['control_risk']
    fields(risk,'requests unauthorized_attempt_probability common_failure_probability first_miss_given_no_common second_miss_given_no_common second_control_coverage loss_per_escape','control_risk')
    integer(risk['requests'],1,1000000,'requests')
    for key in ('unauthorized_attempt_probability','common_failure_probability','first_miss_given_no_common','second_miss_given_no_common','second_control_coverage'):
        number(risk[key],0,1,key)
    number(risk['loss_per_escape'],0,1000000,'loss_per_escape')
    closure=data['closure']
    fields(closure,'preparer approver developer reviewer reviewed_version deployed_version legal_basis_verified restore_evidence_verified replay_evidence_verified external_confirmation_verified maximum_expected_loss maximum_fit_error','closure')
    for key in ('preparer','approver','developer','reviewer','reviewed_version','deployed_version'):
        identifier(closure[key],key)
    for key in ('legal_basis_verified','restore_evidence_verified','replay_evidence_verified','external_confirmation_verified'):
        require(type(closure[key]) is bool,key+': boolean required')
    number(closure['maximum_expected_loss'],0,999999999,'maximum_expected_loss')
    number(closure['maximum_fit_error'],0,1000000,'maximum_fit_error')


def queue(payments,capacities,unit,cash):
    """Work-conserving earliest-deadline-first unit jobs, including overdue jobs.

    All arrivals are available before that cutoff's service; every job consumes
    one slot. Late jobs remain obligations. This finds a feasible all-on-time
    schedule when one exists in this domain; no maximum-on-time-count claim is
    made for general infeasible instances.
    """
    waiting=[]; completed={}; rows=[]
    for cutoff,capacity in enumerate(capacities,1):
        arrived=[p for p in payments if p['release']==cutoff]
        waiting.extend(arrived)
        waiting.sort(key=lambda p:(p['deadline'],p['release'],p['id']))
        before=len(waiting); chosen=waiting[:capacity];waiting=waiting[capacity:]
        for p in chosen:completed[p['id']]=cutoff
        require(before-len(chosen)==len(waiting),'queue conservation failed')
        rows.append({'cutoff':cutoff,'arrivals':[p['id'] for p in arrived],
                     'available_before_service':before,'capacity':capacity,
                     'completed_ids':[p['id'] for p in chosen],'unused_slots':capacity-len(chosen),
                     'backlog_after':len(waiting),
                     'due_and_unfinished_ids':[p['id'] for p in waiting if p['deadline']<=cutoff],
                     'planned_cash_after':cash-unit*len(completed),
                     'planned_payment_liability_after':unit*(len(payments)-len(completed))})
    misses=[p['id'] for p in payments if p['id'] not in completed or completed[p['id']]>p['deadline']]
    late=[p['id'] for p in payments if p['id'] in completed and completed[p['id']]>p['deadline']]
    unfinished=[p['id'] for p in payments if p['id'] not in completed]
    return {'rows':rows,'completion_cutoffs':completed,'deadline_missed_ids':misses,
            'completed_late_ids':late,'unfinished_ids':unfinished,
            'on_time_count':len(payments)-len(misses),'all_deadlines_met':not misses}


def serial(value):
    if isinstance(value,F):return str(value)
    if type(value) is dict:return {k:serial(v) for k,v in value.items()}
    if type(value) is list:return [serial(v) for v in value]
    return value


def run(data):
    """Return a fresh strict-JSON-compatible result without printing or mutation."""
    validate(data)
    unit=F(data['unit_amount']);cash=F(data['opening_cash']);debt=F(data['opening_payment_liability'])
    equity=F(data['opening_equity']);payments=data['payments'];horizon=data['horizon']
    training=data['training'];op=data['operation'];policy=data['closure']
    numerator=sum(row['staff']*row['throughput'] for row in training)
    denominator=sum(row['staff']**2 for row in training)
    rate=F(numerator,denominator)
    errors=[rate*row['staff']-row['throughput'] for row in training]
    staff_capacity=[(rate*x).numerator//(rate*x).denominator for x in op['staff']]
    constrained=[min(a,b) for a,b in zip(staff_capacity,op['gateway_capacity'])]
    deployed=staff_capacity if op['deployed_rule']=='staff_only' else constrained
    forecast=queue(payments,deployed,unit,cash)
    constrained_plan=queue(payments,constrained,unit,cash)
    inventory={p['id']:p for p in payments};legitimate={};anomalies=[];record_rows=[]
    observed_counts=[0]*horizon
    for row in data['observed_settlements']:
        key,cutoff=row['id'],row['cutoff'];observed_counts[cutoff-1]+=1
        if key not in inventory:classification='unknown_instruction'
        elif cutoff<inventory[key]['release']:classification='before_authorization'
        elif key in legitimate:classification='duplicate_settlement'
        else:
            legitimate[key]=cutoff
            classification='authorized_on_time' if cutoff<=inventory[key]['deadline'] else 'authorized_late'
        if not classification.startswith('authorized_'):anomalies.append({'id':key,'cutoff':cutoff,'reason':classification})
        record_rows.append({'id':key,'cutoff':cutoff,'classification':classification})
    missing=[p['id'] for p in payments if p['id'] not in legitimate]
    late=[key for key,cutoff in legitimate.items() if cutoff>inventory[key]['deadline']]
    actual_debits=unit*len(record_rows);discharged=unit*len(legitimate);loss=actual_debits-discharged
    final_cash=cash-actual_debits;final_liability=debt-discharged;final_equity=equity-loss
    require(final_cash==final_liability+final_equity,'observed cash/liability/loss reconciliation failed')
    observed={'rows':record_rows,'slot_counts':observed_counts,'acknowledgment_count':len(record_rows),
              'unique_authorized_settlements':len(legitimate),'missing_instruction_ids':missing,
              'authorized_late_ids':late,'anomalies':anomalies,
              'on_time_count':len(legitimate)-len(late),
              'cash_debits':actual_debits,'authorized_liability_discharged':discharged,
              'bank_borne_exception_loss':loss,'closing_cash':final_cash,
              'closing_payment_liability':final_liability,'closing_equity':final_equity,
              'identity_residual':final_cash-final_liability-final_equity,
              'within_stipulated_capacity':all(n<=c for n,c in zip(observed_counts,constrained))}
    risk=data['control_risk'];a=F(risk['unauthorized_attempt_probability']);c=F(risk['common_failure_probability'])
    q1=F(risk['first_miss_given_no_common']);q2=F(risk['second_miss_given_no_common']);f=F(risk['second_control_coverage'])
    first=c+(1-c)*q1;second=c+(1-c)*q2;joint=c+(1-c)*q1*q2
    escape=(1-f)*first+f*joint
    expected_escapes=risk['requests']*a*escape
    expected_loss=expected_escapes*F(risk['loss_per_escape'])
    risk_result={'first_control_marginal_miss':first,'second_control_marginal_miss':second,
                 'joint_miss_when_both_applied':joint,'incorrect_product_of_marginal_misses':first*second,
                 'escape_given_unauthorized_attempt':escape,'escape_per_request':a*escape,
                 'expected_escapes':expected_escapes,'expected_loss':expected_loss,
                 'scope':'Separate stipulated control experiment, not an estimated probability law for the observed payment log. Expectation does not determine a tail probability or guarantee control effectiveness.'}
    gates={'training_error_within_stated_tolerance':max(map(abs,errors))<=F(policy['maximum_fit_error']),
           'runtime_bottleneck_included':op['deployed_rule']=='bottleneck' and deployed==constrained,
           'constrained_plan_meets_all_deadlines':constrained_plan['all_deadlines_met'],
           'observed_instruction_identity_complete':not anomalies and not missing,
           'observed_all_authorized_payments_on_time':len(legitimate)-len(late)==len(payments),
           'observed_records_within_stated_capacity':observed['within_stipulated_capacity'],
           'distinct_preparer_and_approver_declared':policy['preparer']!=policy['approver'],
           'independent_model_challenger_declared':policy['developer']!=policy['reviewer'],
           'reviewed_version_matches_deployment':policy['reviewed_version']==policy['deployed_version'],
           'expected_loss_within_fictional_bound':expected_loss<=F(policy['maximum_expected_loss']),
           'legal_basis_evidence_declared':policy['legal_basis_verified'],
           'restore_replay_external_evidence_declared':all(policy[k] for k in ('restore_evidence_verified','replay_evidence_verified','external_confirmation_verified'))}
    output={'schema':SCHEMA+'-output','provenance':PROVENANCE,'run_label':data['run_label'],
            'calibration':{'rate_per_staff_cutoff':rate,'training_errors':errors,
                           'sum_squared_error':sum(x*x for x in errors),'max_absolute_error':max(map(abs,errors))},
            'capacity':{'staff_only':staff_capacity,'constrained':constrained,'deployed':deployed},
            'deployed_forecast':forecast,'constrained_plan':constrained_plan,'observed_reconciliation':observed,
            'separate_control_experiment':risk_result,'closure_gates':gates,
            'failed_closure_gates':[key for key,value in gates.items() if not value],
            'disposition':'eligible_for_independent_closure_review' if all(gates.values()) else 'keep_incident_open_or_restrict_use',
            'limits':'Queue capacities are stipulated consequences of a fitted rate and gateway limit, not empirical certainty. Historical late or wrong payments cannot be relabeled by a successful later test. Metadata flags/version labels do not authenticate documents or artifacts. One first authorized settlement discharges each instruction; duplicate, unknown and premature debits are assumed irreversible bank-borne losses without recovery, not a general legal/accounting rule.'}
    result=serial(output);json.dumps(result,allow_nan=False);return result


def load(path):
    require(path.stat().st_size<=1000000,'input exceeds one megabyte')
    def unique(pairs):
        result={}
        for key,value in pairs:
            require(key not in result,'duplicate JSON key: '+key);result[key]=value
        return result
    def invalid(value):raise ValueError('nonfinite JSON constant: '+value)
    return json.loads(path.read_text(encoding='utf-8'),object_pairs_hook=unique,parse_constant=invalid)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,default=Path(__file__).with_name('v11-c06-inputs.json'))
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    try:
        if args.output:
            for protected in (args.input,Path(__file__)):
                require(args.output.resolve()!=protected.resolve(),'output cannot overwrite input or implementation')
                require(not(args.output.exists() and protected.exists() and args.output.samefile(protected)),
                        'output cannot overwrite an alias of input or implementation')
        text=json.dumps(run(load(args.input)),indent=2,allow_nan=False)+'\n'
        if args.output:args.output.write_text(text,encoding='utf-8')
        else:print(text,end='')
    except (ValueError,TypeError,KeyError,OSError,RecursionError) as exc:
        print('error: '+str(exc),file=sys.stderr);return 2
    return 0


if __name__=='__main__':
    raise SystemExit(main())
