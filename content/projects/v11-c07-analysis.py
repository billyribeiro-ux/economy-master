"""Exact synthetic stress, funding and two-node clearing; standard library only.

Public run(data) is quiet and nonmutating. No estimated scenario probabilities,
automatic refinancing, current regulatory ratios or accounting compliance.
"""
import argparse
from fractions import Fraction as F
import json
from pathlib import Path
import re

NUMBER = re.compile(r'-?(?:0|[1-9][0-9]*)(?:\.[0-9]+|/[1-9][0-9]*)?\Z')
NAME = re.compile(r'[a-z][a-z0-9_]{0,31}\Z')
MAX_BYTES = 65536


def obj(value, keys, label):
    if type(value) is not dict or set(value) != set(keys):
        raise ValueError(label+': exact object keys required')


def number(value, label, low=0, high=1000):
    if type(value) is not str or len(value) > 32 or not NUMBER.fullmatch(value):
        raise ValueError(label+': bounded decimal or fraction string required')
    result = F(value)
    if abs(result.numerator) > 10**9 or result.denominator > 10**9 or not low <= result <= high:
        raise ValueError(label+': value or rational complexity out of bounds')
    return result


def values(raw, keys, label):
    obj(raw, keys, label)
    return {k:number(raw[k], label+'.'+k) for k in keys}


def wire(value):
    if isinstance(value,F): return str(value)
    if isinstance(value,dict): return {k:wire(v) for k,v in value.items()}
    if isinstance(value,list): return [wire(v) for v in value]
    return value


def clearing(T, a, b, c):
    """Solve all four saturation regimes, then certify the unique fixed point."""
    candidates = [(T,T), (b+a*T,T), (T,c+a*T),
                  ((b+a*c)/(1-a*a),(c+a*b)/(1-a*a))]
    valid = {pair for pair in candidates if pair[0] == min(T,b+a*pair[1])
             and pair[1] == min(T,c+a*pair[0])}
    if len(valid) != 1:
        raise ValueError('clearing certificate failed')
    p,q = valid.pop()
    retained_b,retained_c = b+a*q-p,c+a*p-q
    receipt = (1-a)*p
    standalone = (1-a)*min(T,b+a*T)
    return dict(payment_b=p,payment_c=q,interbank_b_receipt=a*q,interbank_c_receipt=a*p,
        institution_receipt=receipt,other_outside_receipt=(1-a)*q,
        retained_b=retained_b,retained_c=retained_c,unpaid_b=T-p,unpaid_c=T-q,
        external_resource_residual=b+c-receipt-(1-a)*q-retained_b-retained_c,
        standalone_institution_receipt=standalone,feedback_loss=standalone-receipt)


def parse(data):
    obj(data,('schema','institution','network','reference','scenarios','reverse'),'root')
    if type(data['schema']) is not str or data['schema'] != 'v11-c07-inputs-1':
        raise ValueError('unsupported schema')
    keys = ('cash','bond_face','bond_years','loan_face','base_yield','deposits','secured_old',
            'pledged_fraction','facility_limit','secured_daily_rate','cash_floor','equity_floor')
    obj(data['institution'],keys,'institution')
    years = data['institution']['bond_years']
    if type(years) is not int or not 1 <= years <= 5:
        raise ValueError('bond_years: integer in [1,5] required')
    i = {k:number(data['institution'][k],'institution.'+k) for k in keys if k != 'bond_years'}
    i['bond_years'] = years
    if not i['bond_face'] > 0 or not i['loan_face'] > 0 or i['base_yield'] > F(1,2):
        raise ValueError('positive claim faces and base yield in [0,0.5] required')
    if i['pledged_fraction'] > 1 or i['secured_daily_rate'] > F(1,100):
        raise ValueError('pledged fraction or daily funding rate out of bounds')
    n = values(data['network'],('obligation','interbank_share','external_b','external_c'),'network')
    if n['obligation'] <= 0 or n['interbank_share'] > F(3,4):
        raise ValueError('positive obligation and interbank share in [0,0.75] required')
    outside = (1-n['interbank_share'])*n['obligation']
    if min(n['external_b'],n['external_c']) < outside:
        raise ValueError('reference network must pay all promised obligations')
    ref = values(data['reference'],('haircut','withdrawal'),'reference')
    if ref['haircut'] > F(9,10) or ref['withdrawal'] > i['deposits']:
        raise ValueError('reference haircut or withdrawal out of bounds')
    i['bond_open'] = i['bond_face']/(1+i['base_yield'])**years
    i['loan_open'] = i['loan_face']/(1+i['base_yield'])
    i['network_open'] = outside
    i['equity_open'] = i['cash']+i['bond_open']+i['loan_open']+outside-i['deposits']-i['secured_old']
    if i['equity_open'] <= 0 or i['secured_old'] > (1-ref['haircut'])*i['pledged_fraction']*i['bond_open']:
        raise ValueError('positive opening equity and adequately secured opening funding required')
    raw_scenarios = data['scenarios']
    if type(raw_scenarios) is not list or not 1 <= len(raw_scenarios) <= 8:
        raise ValueError('one to eight scenarios required')
    skeys = ('id','yield','loan_loss_fraction','external_b','external_c','haircut','withdrawal',
             'operating_cash_loss','facility_limit')
    scenarios = []
    for raw in raw_scenarios:
        obj(raw,skeys,'scenario')
        if type(raw['id']) is not str or not NAME.fullmatch(raw['id']):
            raise ValueError('scenario id: bounded lower-case identifier required')
        s = {k:number(raw[k],'scenario.'+k,low=F(-1,2) if k == 'yield' else 0,
                      high=1 if k == 'yield' else 1000) for k in skeys if k != 'id'}
        s['id'] = raw['id']
        validate_scenario(i,s)
        scenarios.append(s)
    if len({s['id'] for s in scenarios}) != len(scenarios):
        raise ValueError('scenario identifiers must be unique')
    rkeys = ('yield_increase','loan_loss_increase','b_resource_drop','c_resource_drop',
             'haircut_increase','withdrawal_increase','operating_loss_increase','bisections')
    obj(data['reverse'],rkeys,'reverse')
    steps = data['reverse']['bisections']
    if type(steps) is not int or not 8 <= steps <= 48:
        raise ValueError('bisections: integer in [8,48] required')
    reverse = {k:number(data['reverse'][k],'reverse.'+k) for k in rkeys if k != 'bisections'}
    reverse['bisections'] = steps
    end = severity(i,n,ref,reverse,F(1))
    if end['yield'] > 1 or min(end['external_b'],end['external_c']) < 0:
        raise ValueError('reverse endpoint yield or external resources out of bounds')
    validate_scenario(i,end)
    return i,n,ref,scenarios,reverse


def validate_scenario(i,s):
    if s['loan_loss_fraction'] > 1 or s['haircut'] > F(19,20):
        raise ValueError('scenario credit fraction or haircut out of bounds')
    if s['withdrawal'] > i['deposits'] or s['operating_cash_loss'] > i['cash']:
        raise ValueError('withdrawal exceeds deposits or initial cash incident exceeds cash')
    if s['facility_limit'] > i['facility_limit']:
        raise ValueError('scenario cannot invent a larger committed facility')


def severity(i,n,ref,r,x):
    return {
        'id':'reverse','yield':i['base_yield']+r['yield_increase']*x,
        'loan_loss_fraction':r['loan_loss_increase']*x,
        'external_b':n['external_b']-r['b_resource_drop']*x,
        'external_c':n['external_c']-r['c_resource_drop']*x,
        'haircut':ref['haircut']+r['haircut_increase']*x,
        'withdrawal':ref['withdrawal']+r['withdrawal_increase']*x,
        'operating_cash_loss':r['operating_loss_increase']*x,'facility_limit':i['facility_limit']}


def scenario(i,n,s,ledger=True):
    bond = i['bond_face']/(1+s['yield'])**i['bond_years']
    recovery = i['loan_face']*(1-s['loan_loss_fraction'])
    loan = recovery/(1+s['yield'])
    network = clearing(n['obligation'],n['interbank_share'],s['external_b'],s['external_c'])
    receipt = network['institution_receipt']
    losses = dict(bond=i['bond_open']-bond,loan=i['loan_open']-loan,
                  network=i['network_open']-receipt,operating=s['operating_cash_loss'])
    total_loss = sum(losses.values(),F(0))
    equity = i['equity_open']-total_loss
    margin = max(F(0),i['secured_old']-(1-s['haircut'])*i['pledged_fraction']*bond)
    cap = min(s['facility_limit'],(1-s['haircut'])*(1-i['pledged_fraction'])*bond)
    available = i['cash']-s['operating_cash_loss']+receipt
    full_payment_cash = available+cap-margin-s['withdrawal']
    required = max(F(0),margin+s['withdrawal']+i['cash_floor']-available)
    draw = min(required,cap)
    capital_slack = equity-i['equity_floor']
    funding_slack = full_payment_cash-i['cash_floor']
    short = dict(equity=equity,capital_slack=capital_slack,funding_slack=funding_slack)
    if not ledger:
        return short
    balances = dict(cash=i['cash'],bond=i['bond_open'],loan=i['loan_open'],
                    network_claim=i['network_open'],deposits=i['deposits'],
                    secured_old=i['secured_old'],secured_new=F(0),equity=i['equity_open'])
    rows = []
    def post(event,changes):
        for key,amount in changes.items(): balances[key] += amount
        assets = sum(balances[key] for key in ('cash','bond','loan','network_claim'))
        residual = assets-sum(balances[key] for key in ('deposits','secured_old','secured_new','equity'))
        if residual != 0 or balances['cash'] < 0:
            raise ValueError('funded journal certificate failed')
        rows.append(dict(event=event,**balances,assets=assets,accounting_residual=residual))
    post('opening',{})
    post('joint_asset_marks',dict(bond=-losses['bond'],loan=-losses['loan'],
        network_claim=-losses['network'],equity=-sum(v for k,v in losses.items() if k != 'operating')))
    post('cash_incident',dict(cash=-s['operating_cash_loss'],equity=-s['operating_cash_loss']))
    post('network_batch_settles',dict(cash=receipt,network_claim=-receipt))
    post('new_secured_funding',dict(cash=draw,secured_new=draw))
    margin_paid = min(balances['cash'],margin)
    post('old_secured_principal_paydown',dict(cash=-margin_paid,secured_old=-margin_paid))
    withdrawal_paid = min(balances['cash'],s['withdrawal'])
    post('deposit_payment',dict(cash=-withdrawal_paid,deposits=-withdrawal_paid))
    new_pledged = draw/((1-s['haircut'])*bond)
    principal_due = balances['secured_old']+draw
    return dict(id=s['id'],scenario=s,loss_components=losses,total_loss=total_loss,
        **short,network=network,ledger=rows,
        funding=dict(margin_required=margin,margin_paid=margin_paid,margin_unpaid=margin-margin_paid,
            facility_capacity=cap,draw_to_meet_cash_floor=required,actual_draw=draw,
            cash_capacity_after_full_payments=full_payment_cash,withdrawal_requested=s['withdrawal'],
            withdrawal_paid=withdrawal_paid,withdrawal_unpaid=s['withdrawal']-withdrawal_paid,
            closing_cash=balances['cash'],all_payments_met=margin_paid == margin and withdrawal_paid == s['withdrawal'],
            reserve_trigger=funding_slack <= 0,capital_trigger=capital_slack <= 0),
        collateral=dict(original_fraction_reserved=i['pledged_fraction'],new_fraction_pledged=new_pledged,
            fraction_remaining_free=1-i['pledged_fraction']-new_pledged,
            original_pool_capacity=(1-s['haircut'])*i['pledged_fraction']*bond),
        later_cash=dict(next_day_secured_principal=principal_due,
            next_day_secured_interest=principal_due*i['secured_daily_rate'],
            next_day_secured_total=principal_due*(1+i['secured_daily_rate']),
            year_one_loan_receipt=recovery,bond_maturity_year=i['bond_years'],bond_maturity_receipt=i['bond_face']))


def reverse_boundary(i,n,ref,r,key):
    def evaluate(x):
        z = scenario(i,n,severity(i,n,ref,r,x),ledger=False)
        return min(z['capital_slack'],z['funding_slack']) if key == 'first' else z[key]
    lo,hi = F(0),F(1)
    low_value,high_value = evaluate(lo),evaluate(hi)
    if low_value <= 0:
        return dict(status='triggered_at_reference',lower=lo,upper=lo,lower_slack=low_value,
                    upper_slack=low_value,width=F(0))
    if high_value > 0:
        return dict(status='no_trigger_in_supported_interval',lower=None,upper=None,
                    reference_slack=low_value,endpoint_slack=high_value,width=None)
    for unused in range(r['bisections']):
        mid = (lo+hi)/2
        value = evaluate(mid)
        if value > 0: lo,low_value = mid,value
        else: hi,high_value = mid,value
    return dict(status='boundary_bracketed',lower=lo,upper=hi,lower_slack=low_value,
                upper_slack=high_value,width=hi-lo)


def run(data):
    """Return strict-JSON-compatible exact results, without I/O or input mutation."""
    i,n,ref,scenarios,r = parse(data)
    results = [scenario(i,n,s) for s in scenarios]
    component_max = {key:max(row['loss_components'][key] for row in results)
                     for key in ('bond','loan','network','operating')}
    joint_max = max(row['total_loss'] for row in results)
    return wire(dict(schema='v11-c07-output-1',opening=dict(bond=i['bond_open'],loan=i['loan_open'],
        network_claim=i['network_open'],assets=i['cash']+i['bond_open']+i['loan_open']+i['network_open'],
        equity=i['equity_open']),scenarios=results,
        aggregation=dict(component_maxima=component_max,sum_component_maxima=sum(component_max.values(),F(0)),
            largest_common_scenario_loss=joint_max,overstatement=sum(component_max.values(),F(0))-joint_max,
            maximizing_scenarios=[z['id'] for z in results if z['total_loss'] == joint_max]),
        reverse={key:reverse_boundary(i,n,ref,r,key) for key in ('capital_slack','funding_slack','first')}))


def pairs(rows):
    result = {}
    for key,value in rows:
        if key in result: raise ValueError('duplicate JSON key: '+key)
        result[key] = value
    return result


def constant(value):
    raise ValueError('nonfinite JSON token: '+value)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    here = Path(__file__).resolve().parent
    parser.add_argument('--input',type=Path,default=here/'v11-c07-inputs.json')
    parser.add_argument('--output',type=Path,default=here/'v11-c07-output.json')
    args = parser.parse_args(argv)
    try:
        for protected in (args.input,Path(__file__)):
            if args.output.resolve() == protected.resolve() or (args.output.exists() and protected.exists() and args.output.samefile(protected)):
                raise ValueError('output must not overwrite input or implementation')
        with args.input.open('rb') as stream: raw = stream.read(MAX_BYTES+1)
        if len(raw) > MAX_BYTES: raise ValueError('input exceeds65536 bytes')
        data = json.loads(raw.decode('utf-8'),object_pairs_hook=pairs,parse_constant=constant)
        result = run(data)
        args.output.write_text(json.dumps(result,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8')
    except (ValueError,TypeError,RuntimeError,OSError) as error:
        parser.exit(2,'v11-c07: '+str(error)+'\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
