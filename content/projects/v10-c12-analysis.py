"""Exact synthetic pricing evidence and a declared Sable review policy.

Policy recommendations are fictional case outputs, not production approvals.
Only standard-library Python; import and run(data) are quiet and nonmutating.
"""
import argparse
from datetime import date
from fractions import Fraction as F
import json
import math
from pathlib import Path
import re

PROVENANCE = 'Original synthetic Sable model-review evidence; no market observations or real approval authority.'
HOLDOUT = 'Errors are frozen forecast minus subsequent comparison value in CU; the synthetic list does not establish an IID sampling law.'
NUMBER = re.compile(r'-?\d{1,9}(?:\.\d{1,8}|/[1-9]\d{0,8})?\Z')
ID = re.compile(r'[a-z][a-z0-9_]{0,39}\Z')


def need(condition, message):
    if not condition:
        raise ValueError(message)


def fields(value, names):
    need(type(value) is dict and set(value) == set(names.split()), 'Missing or unexpected fields')


def number(value, lo, hi):
    need(type(value) is str and NUMBER.fullmatch(value) is not None, 'Exact bounded decimal/rational strings required')
    value = F(value)
    need(lo <= value <= hi, 'Numeric value outside teaching domain')
    return value


def vector(value, lo, hi, minimum=1, maximum=24):
    need(type(value) is list and minimum <= len(value) <= maximum, 'Invalid bounded vector length')
    return [number(x, lo, hi) for x in value]


def identifier(value):
    need(type(value) is str and ID.fullmatch(value) is not None, 'Bounded identifier required')
    return value


def day(value):
    need(type(value) is str and re.fullmatch(r'\d{4}-\d{2}-\d{2}', value) is not None, 'ISO calendar date required')
    parsed = date.fromisoformat(value)
    need(date(2000, 1, 1) <= parsed <= date(2100, 12, 31), 'Date outside teaching domain')
    return parsed


def serial(value):
    if isinstance(value, F):
        return str(value)
    if isinstance(value, list):
        return [serial(x) for x in value]
    if isinstance(value, dict):
        return {k: serial(v) for k, v in value.items()}
    return value


def run(data):
    fields(data, 'schema provenance bond curve_family conditioning book holdout decision')
    need(data['schema'] == 'v10-c12-sable-1' and data['provenance'] == PROVENANCE, 'Fixed synthetic evidence contract required')
    b = data['bond'];fields(b, 'cash_flows benchmark_discounts candidate_discounts position price_tolerance')
    cash = vector(b['cash_flows'], -1000000, 1000000)
    discounts = vector(b['benchmark_discounts'], F(1,1000), 3)
    candidate = vector(b['candidate_discounts'], F(1,1000), 3)
    need(len(cash) == len(discounts) == len(candidate), 'One discount per dated cash flow required')
    position = number(b['position'], -10000, 10000);tolerance = number(b['price_tolerance'], 0, 100)
    benchmark = sum((cf*d for cf,d in zip(cash,discounts)), F(0))
    observed = sum((cf*d for cf,d in zip(cash,candidate)), F(0))
    error = observed-benchmark
    bond = {'benchmark_value': benchmark, 'candidate_value': observed, 'price_error': error,
            'position_value_error': position*error, 'absolute_error_pass': abs(error) <= tolerance,
            'per_cash_flow_error': [cf*(new-old) for cf,new,old in zip(cash,candidate,discounts)]}

    c = data['curve_family'];fields(c, 'price_at_one price_at_two curvature_lower curvature_upper requested_tenor spread_limit')
    p1 = number(c['price_at_one'], 90, 105);p2 = number(c['price_at_two'], 85, 110)
    low = number(c['curvature_lower'], -1, 1);high = number(c['curvature_upper'], -1, 1)
    t = number(c['requested_tenor'], 0, 3);limit = number(c['spread_limit'], 0, 100)
    need(low <= high, 'Curvature interval must be ordered')
    # P(t)=100+a*t+b*t^2+c*t*(t-1)*(t-2), per100 terminal CU.
    quadratic = (p2-2*p1+100)/2;linear = p1-100-quadratic
    base = 100+linear*t+quadratic*t*t;loading=t*(t-1)*(t-2)
    endpoints = [base+low*loading,base+high*loading]
    need(min(endpoints) > 0, 'Every allowed requested-tenor discount price must be positive')
    curve = {'linear_coefficient':linear,'quadratic_coefficient':quadratic,
             'calibration_residuals':[100+linear+quadratic-p1,100+2*linear+4*quadratic-p2],
             'unidentified_loading':loading,'target_lower':min(endpoints),'target_upper':max(endpoints),
             'target_spread':max(endpoints)-min(endpoints),'spread_within_limit':max(endpoints)-min(endpoints) <= limit,
             'interpretation':'Assumption-conditioned range over supplied curvature interval; not a confidence interval or empirical price guarantee.'}

    c = data['conditioning'];fields(c, 'first_tenor second_tenor first_quote second_quote target_tenor quote_error_bound')
    t1 = number(c['first_tenor'], 0, 5);t2 = number(c['second_tenor'], 0, 5)
    need(t2-t1 >= F(1,10000), 'Ordered tenor gap at least1/10000 required')
    q1 = number(c['first_quote'], 0, 1000);q2 = number(c['second_quote'], 0, 1000)
    target = number(c['target_tenor'], 0, 10);epsilon = number(c['quote_error_bound'], 0, 10)
    w=(target-t1)/(t2-t1);slope=(q2-q1)/(t2-t1)
    conditioning={'slope':slope,'intercept':q1-slope*t1,'first_weight':1-w,'second_weight':w,
                  'prediction':(1-w)*q1+w*q2,'second_quote_plus_bound_change':w*epsilon,
                  'two_quote_error_bound':(abs(1-w)+abs(w))*epsilon,
                  'absolute_condition_factor':abs(1-w)+abs(w)}

    b=data['book'];fields(b,'benchmark_prices candidate_prices positions unit_tolerances signed_error_limit gross_error_limit')
    old=vector(b['benchmark_prices'],0,1000000);new=vector(b['candidate_prices'],0,1000000)
    quantities=vector(b['positions'],-10000,10000);eps=vector(b['unit_tolerances'],0,100)
    need(len(old)==len(new)==len(quantities)==len(eps),'Matched book vectors required')
    signed_limit=number(b['signed_error_limit'],0,1000000);gross_limit=number(b['gross_error_limit'],0,1000000)
    errors=[y-x for x,y in zip(old,new)];contributions=[q*e for q,e in zip(quantities,errors)]
    signed=sum(contributions,F(0));gross=sum((abs(v) for v in contributions),F(0))
    book={'unit_errors':errors,'unit_passes':[abs(e)<=bound for e,bound in zip(errors,eps)],
          'position_contributions':contributions,'signed_error':signed,'gross_comparison_error':gross,
          'bound_from_unit_tolerances':sum((abs(q)*bound for q,bound in zip(quantities,eps)),F(0)),
          'signed_pass':abs(signed)<=signed_limit,'gross_pass':gross<=gross_limit,
          'unit_rmse_approx':math.sqrt(float(sum((e*e for e in errors),F(0))/len(errors)))}

    h=data['holdout'];fields(h,'training_ids evaluation_ids forecast_errors contract')
    need(h['contract']==HOLDOUT,'Holdout interpretation must remain explicit')
    for ids in (h['training_ids'],h['evaluation_ids']):
        need(type(ids) is list and 1<=len(ids)<=100,'Bounded nonempty observation identifiers required')
        for ident in ids:identifier(ident)
        need(len(set(ids))==len(ids),'Observation IDs must be unique within a split')
    need(not set(h['training_ids']) & set(h['evaluation_ids']),'Training and evaluation identifiers must be disjoint')
    errors=vector(h['forecast_errors'],-1000,1000,2,100)
    need(len(errors)==len(h['evaluation_ids']),'One held-out error per evaluation ID required')
    n=len(errors);mean=sum(errors,F(0))/n;mse=sum((e*e for e in errors),F(0))/n
    variance=sum(((e-mean)**2 for e in errors),F(0))/(n-1)
    holdout={'observations':n,'mean_error':mean,'mean_squared_error':mse,'sample_variance':variance,
             'rmse_approx':math.sqrt(float(mse)),'iid_standard_error_if_assumed_approx':math.sqrt(float(variance/n)),
             'scope':'Descriptive synthetic outcome comparison. The conditional IID standard error is not a verified sampling law, coverage guarantee or causal test.'}

    d=data['decision'];fields(d,'as_of requested_version reviewed_version owner challenger data_age_days max_data_age_days requested_notional ordinary_limit exception')
    asof=day(d['as_of'])
    for name in ('requested_version','reviewed_version','owner','challenger'):identifier(d[name])
    for name in ('data_age_days','max_data_age_days'):
        need(type(d[name]) is int and 0<=d[name]<=365,'Integer evidence ages from0to365 required')
    requested=number(d['requested_notional'],0,100000000);ordinary=number(d['ordinary_limit'],0,100000000)
    exception=d['exception'];fields(exception,'enabled approver reason expires notional_limit')
    need(type(exception['enabled']) is bool,'Exception enabled must be Boolean')
    approver=identifier(exception['approver']);expires=day(exception['expires'])
    need(type(exception['reason']) is str and 1<=len(exception['reason'])<=240 and exception['reason'].strip(),'Bounded written exception reason required')
    exception_limit=number(exception['notional_limit'],0,100000000)
    independent=approver not in (d['owner'],d['challenger'])
    valid_exception=exception['enabled'] and independent and asof<=expires
    allowed=max(ordinary,exception_limit) if valid_exception else ordinary
    failures=[]
    conditions=[('numeric_benchmark',bond['absolute_error_pass']),('curve_scope',curve['spread_within_limit']),
                ('book_units',all(book['unit_passes'])),('book_signed',book['signed_pass']),('book_gross',book['gross_pass']),
                ('version_binding',d['requested_version']==d['reviewed_version']),
                ('independent_challenge',d['owner']!=d['challenger']),
                ('fresh_evidence',d['data_age_days']<=d['max_data_age_days']),('notional_limit',requested<=allowed)]
    for label,passed in conditions:
        if not passed:failures.append(label)
    decision={'as_of':d['as_of'],'effective_notional_limit':allowed,'exception_valid_for_size_only':valid_exception,
              'checks':dict(conditions),'failed_gates':failures,'recommendation':'reject_requested_use' if failures else 'eligible_with_stated_limits',
              'scope':'Declared fictional policy only. Size exceptions waive no numerical, model-scope, version, challenger or evidence-age gate; no real authority is exercised.'}
    result=serial({'schema':'v10-c12-sable-output-1','bond':bond,'curve_family':curve,'conditioning':conditioning,
                   'book':book,'holdout':holdout,'decision':decision})
    json.dumps(result,allow_nan=False)
    return result


def strict_pairs(pairs):
    result={}
    for key,value in pairs:
        need(key not in result,'Duplicate JSON key');result[key]=value
    return result


def reject_constant(value):
    raise ValueError('Nonfinite JSON token: '+value)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,default=Path(__file__).with_name('v10-c12-inputs.json'))
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    result=run(json.loads(args.input.read_text(),object_pairs_hook=strict_pairs,parse_constant=reject_constant))
    output=json.dumps(result,indent=2,allow_nan=False)+'\n'
    if args.output:args.output.write_text(output)
    else:print(output,end='')


if __name__=='__main__':
    main()
