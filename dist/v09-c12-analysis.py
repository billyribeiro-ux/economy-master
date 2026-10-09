#!/usr/bin/env python3
"""Larch: exact finite mandate selection and dated cash audit; standard library only."""
import argparse
import json
from fractions import Fraction as F
from math import sqrt
from pathlib import Path


def number(value):
    """Accept exact decimal/fraction strings or integers; never booleans/floats."""
    if isinstance(value,F):
        return value
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ValueError("numbers must be finite rational strings or integers")
    try:
        return F(value)
    except (ValueError, ZeroDivisionError, OverflowError) as exc:
        raise ValueError("invalid rational number") from exc


def keys(obj, expected):
    if not isinstance(obj, dict) or set(obj) != set(expected.split()):
        raise ValueError("missing or unknown input field")


def moments(data):
    states = data['moment_states']
    means = [sum(number(s['probability']) * number(s[k]) for s in states)
             for k in ('equity_return', 'bond_return')]
    cov = [[sum(number(s['probability']) *
                (number(s[('equity_return', 'bond_return')[i]]) - means[i]) *
                (number(s[('equity_return', 'bond_return')[j]]) - means[j])
                for s in states) for j in range(2)] for i in range(2)]
    return means, cov


def quadratic(h, cov):
    return sum(h[i] * cov[i][j] * h[j] for i in range(2) for j in range(2))


def position(data, equity, bond):
    x, y = number(equity), number(bond)
    fee = sum(number(data['entry_fee'][a]) * abs(v-number(data['initial'][a]))
              for a, v in [('equity', x), ('bond', y)])
    cash = number(data['wealth']) - x - y - fee
    return {'equity': x, 'bond': y, 'fee': fee, 'cash': cash}


def ledger(data, holding, scenario, draw=F(0), contribution=F(0)):
    """An unfunded payment has no fictional negative-cash terminal outcome."""
    draw, contribution = number(draw), number(contribution)
    if draw < 0 or draw > number(data['line_capacity']) or contribution < 0:
        raise ValueError("draw outside facility or negative contribution")
    g = number(data['cash_half_year_factor'])
    h = number(data['line_repayment_factor'])
    L1, L2 = number(scenario['grant_t1']), number(scenario['grant_t2'])
    opening = holding['cash'] * g
    available = opening + draw + contribution
    payment_gap = max(F(0), L1 - available)
    required = L1 + number(data['policy']['cash_buffer'])
    buffer_gap = max(F(0), required - available)
    after = available - L1 if payment_gap == 0 else None
    asset_proceeds = holding['equity'] * (1+number(scenario['equity_return'])) + \
        holding['bond'] * (1+number(scenario['bond_return']))
    before_obligations = None if after is None else asset_proceeds + g*after
    terminal_due = L2+h*draw
    terminal_gap = None if after is None else max(F(0), terminal_due-before_obligations)
    reserve = None if after is None or terminal_gap > 0 else before_obligations-terminal_due
    floor_gap = None if reserve is None else max(F(0), number(data['policy']['reserve_floor'])-reserve)
    return {'cash_before_t1': opening, 'contribution_t1': contribution, 'draw_t1': draw,
            'available_t1': available, 'grant_t1': L1, 'payment_gap_t1': payment_gap,
            'buffer_gap_t1': buffer_gap, 'cash_after_t1': after,
            'mandate_proceeds_t2': asset_proceeds,
            'cash_before_obligations_t2': before_obligations, 'grant_t2': L2,
            'loan_repayment_t2': h*draw, 'payment_gap_t2': terminal_gap,
            'terminal_reserve': reserve, 'reserve_floor_gap': floor_gap,
            'payments_funded': payment_gap == 0 and terminal_gap == 0,
            'policy_cash_and_floor_pass': buffer_gap == 0 and floor_gap == 0}


def assess(data, equity, bond):
    p = position(data, equity, bond)
    mu, cov = moments(data)
    x, y, c = p['equity'], p['bond'], p['cash']
    g, W = number(data['cash_half_year_factor']), number(data['wealth'])
    v = quadratic([x, y], cov)
    active = [x-number(data['benchmark']['equity']), y-number(data['benchmark']['bond'])]
    av = quadratic(active, cov)
    expected = x*(1+mu[0]) + y*(1+mu[1]) + g*g*c - \
        g*number(data['planning_grants']['t1']) - number(data['planning_grants']['t2'])
    score = expected - number(data['policy']['gamma'])*v/(2*W)
    max_grant = max([number(data['planning_grants']['t1'])] +
                    [number(s['grant_t1']) for s in data['design_stresses']])
    liquidity_margin = g*c-max_grant-number(data['policy']['cash_buffer'])
    reasons = []
    if any(vv < 0 or vv > number(data['caps'][a]) for a,vv in [('equity',x),('bond',y)]):
        reasons.append('position_bounds')
    if any(vv % number(data['lot']) != 0 for vv in (x,y)):
        reasons.append('lot')
    if c < 0:
        reasons.append('cash')
    if v > number(data['policy']['variance_limit']):
        reasons.append('total_risk')
    if av > number(data['policy']['active_variance_limit']):
        reasons.append('active_risk')
    if liquidity_margin < 0:
        reasons.append('date1_buffer')
    stress_results = {s['name']: ledger(data,p,s) for s in data['design_stresses']}
    if any(not r['policy_cash_and_floor_pass'] for r in stress_results.values()):
        reasons.append('design_stress')
    p.update({'expected_reserve':expected, 'variance':v, 'active_variance':av,
              'criterion':score, 'date1_liquidity_margin':liquidity_margin,
              'feasible':not reasons, 'violations':reasons, 'stresses':stress_results})
    return p


def solve(data):
    lot = number(data['lot'])
    candidates, feasible, rejects = 0, [], {}
    for i in range(int(number(data['caps']['equity'])/lot)+1):
        for j in range(int(number(data['caps']['bond'])/lot)+1):
            p = assess(data,i*lot,j*lot)
            candidates += 1
            if p['feasible']:
                feasible.append(p)
            for why in p['violations']:
                rejects[why] = rejects.get(why,0)+1
    feasible.sort(key=lambda p:(-p['criterion'],p['variance'],p['fee'],p['equity'],p['bond']))
    if not feasible:
        raise ValueError('no feasible portfolio under the stated mandate')
    return {'candidates':candidates, 'feasible_count':len(feasible),
            'nonexclusive_rejection_counts':rejects, 'selected':feasible[0],
            'feasible_ranked':[{k:p[k] for k in ('equity','bond','fee','cash','expected_reserve',
                              'variance','active_variance','criterion')} for p in feasible]}


def repair(data, holding, scenario, draw):
    D = number(draw)
    if not 0 <= D <= number(data['line_capacity']):
        raise ValueError('draw outside facility')
    g, h = number(data['cash_half_year_factor']), number(data['line_repayment_factor'])
    L1, L2 = number(scenario['grant_t1']), number(scenario['grant_t2'])
    A = holding['equity']*(1+number(scenario['equity_return'])) + \
        holding['bond']*(1+number(scenario['bond_return']))
    cash_need = L1+number(data['policy']['cash_buffer'])-g*holding['cash']-D
    floor_need = (number(data['policy']['reserve_floor'])-A-g*g*holding['cash']+g*L1+L2+(h-g)*D)/g
    X = max(F(0),cash_need,floor_need)
    return {'draw':D, 'cash_constraint_contribution':cash_need,
            'floor_constraint_contribution':floor_need, 'minimum_contribution':X,
            'ledger':ledger(data,holding,scenario,D,X)}


def cheapest_repair(data, holding, scenario):
    """Max of decreasing cash bound, increasing floor bound and zero; finite kink proof."""
    g,h = number(data['cash_half_year_factor']),number(data['line_repayment_factor'])
    zero = repair(data,holding,scenario,F(0))
    a,b = zero['cash_constraint_contribution'],zero['floor_constraint_contribution']
    cap = number(data['line_capacity'])
    crossing = (a-b)*g/h
    draws = sorted({F(0),cap,max(F(0),min(cap,crossing)),max(F(0),min(cap,a))})
    candidates = [repair(data,holding,scenario,D) for D in draws]
    return min(candidates,key=lambda r:(r['minimum_contribution'],r['draw']))


def validate(data):
    keys(data,'schema case provenance conventions wealth lot initial caps entry_fee cash_half_year_factor line_capacity line_repayment_factor benchmark policy planning_grants moment_states design_stresses reverse_stress report_fixture')
    if data['schema'] != 'v09-c12-larch-1':
        raise ValueError('unsupported schema')
    for field in ('case','provenance'):
        if not isinstance(data[field],str) or not data[field].strip():
            raise ValueError('nonempty descriptive strings required')
    expected = {'unit':'kCU','dates':['t0','t1_half_year','t2_one_year'],
                'grants':'t1 after cash growth; t2 after all mandate proceeds and before final reserve',
                'mandates':'one-year funded positions; no interim redemption or pledge; terminal factors net of all exit costs',
                'line':'contingent t1 only; may count toward cash buffer; fully repaid at t2; excluded from ordinary feasibility',
                'moment_witness':'synthetic planning law only; design, reverse and reporting fixtures are separate conditional scenarios without probabilities',
                'benchmark':'same initial wealth, inherited positions, date-0 fee rule and grant dates; pre-cost target with fees deducted from cash'}
    if data['conventions'] != expected:
        raise ValueError('fixed units, dates and mandate conventions cannot be edited')
    for k in ('initial','caps','entry_fee','benchmark'):
        keys(data[k],'equity bond')
    keys(data['policy'],'gamma variance_limit active_variance_limit cash_buffer reserve_floor')
    keys(data['planning_grants'],'t1 t2')
    W,lot = number(data['wealth']),number(data['lot'])
    if not 0 < W <= 1000000 or lot <= 0:
        raise ValueError('positive bounded wealth and lot required')
    if any(number(data[k][a]) < 0 for k in ('initial','caps','benchmark') for a in ('equity','bond')):
        raise ValueError('long-only holdings and caps required')
    if sum(number(v) for v in data['initial'].values()) > W:
        raise ValueError('inherited positions exceed wealth')
    if any(number(v) % lot != 0 for k in ('initial','caps','benchmark') for v in data[k].values()):
        raise ValueError('position and cap fields must be multiples of lot')
    if any(number(v) > W for v in data['caps'].values()) or \
            (number(data['caps']['equity'])/lot+1)*(number(data['caps']['bond'])/lot+1)>20000:
        raise ValueError('bounded enumeration required')
    if any(not 0 <= number(v) < 1 for v in data['entry_fee'].values()):
        raise ValueError('entry fee rates must lie in [0,1)')
    g,h = number(data['cash_half_year_factor']),number(data['line_repayment_factor'])
    if not 1 <= g <= h <= 2 or not 0 <= number(data['line_capacity']) <= W:
        raise ValueError('require 1 <= cash factor <= line factor <= 2 and bounded line')
    if number(data['policy']['gamma']) <= 0 or any(number(v) < 0 for v in data['policy'].values()):
        raise ValueError('positive gamma and nonnegative risk/liquidity limits required')
    if any(number(v) < 0 for v in data['planning_grants'].values()):
        raise ValueError('grants must be nonnegative')
    states = data['moment_states']
    if not isinstance(states,list) or not 3 <= len(states) <= 100:
        raise ValueError('bounded moment witness required')
    for s in states:
        keys(s,'probability equity_return bond_return')
        if number(s['probability']) <= 0 or any(not -1 <= number(s[a]) <= 10 for a in ('equity_return','bond_return')):
            raise ValueError('positive probabilities and bounded limited-liability returns required')
    if sum(number(s['probability']) for s in states) != 1:
        raise ValueError('probabilities must sum to one')
    _,cov = moments(data)
    if cov[0][0] <= 0 or cov[0][0]*cov[1][1]-cov[0][1]**2 <= 0:
        raise ValueError('planning covariance must be positive definite')
    stresses = data['design_stresses']
    if not isinstance(stresses,list) or not 1 <= len(stresses) <= 20:
        raise ValueError('one to twenty design stresses required')
    names = set()
    for s in stresses+[data['reverse_stress'],data['report_fixture']]:
        extra = ' unfilled_equity_lots' if s is data['report_fixture'] else ''
        keys(s,'name equity_return bond_return grant_t1 grant_t2'+extra)
        if not isinstance(s['name'],str) or not s['name'] or s['name'] in names:
            raise ValueError('unique scenario names required')
        names.add(s['name'])
        if any(not -1 <= number(s[a]) <= 10 for a in ('equity_return','bond_return')) or \
                any(number(s[a]) < 0 for a in ('grant_t1','grant_t2')):
            raise ValueError('bounded returns and nonnegative grants required')
    n = data['report_fixture']['unfilled_equity_lots']
    if isinstance(n,bool) or not isinstance(n,int) or n < 0:
        raise ValueError('unfilled lots must be a nonnegative integer')
    benchmark = assess(data,number(data['benchmark']['equity']),number(data['benchmark']['bond']))
    if not benchmark['feasible']:
        raise ValueError('the declared benchmark must satisfy its own costs and mandate constraints')


def pack(obj):
    if isinstance(obj,F):
        return str(obj)
    if isinstance(obj,dict):
        return {k:pack(v) for k,v in obj.items()}
    if isinstance(obj,(list,tuple)):
        return [pack(v) for v in obj]
    return obj


def run(data):
    validate(data)
    solved = solve(data)
    chosen = solved['selected']
    mu,cov = moments(data)
    benchmark = assess(data,number(data['benchmark']['equity']),number(data['benchmark']['bond']))
    initial = assess(data,number(data['initial']['equity']),number(data['initial']['bond']))
    risk = [chosen['equity'],chosen['bond']]
    av = [risk[i]-number(data['benchmark'][a]) for i,a in enumerate(('equity','bond'))]
    marginal = [sum(cov[i][j]*risk[j] for j in range(2)) for i in range(2)]
    amarginal = [sum(cov[i][j]*av[j] for j in range(2)) for i in range(2)]
    rc = [risk[i]*marginal[i] for i in range(2)]
    arc = [av[i]*amarginal[i] for i in range(2)]
    sigma = sqrt(float(chosen['variance']))
    reverse, cap = data['reverse_stress'],number(data['line_capacity'])
    max_line = ledger(data,chosen,reverse,cap)
    buffer_repair = ledger(data,chosen,reverse,cap,max_line['buffer_gap_t1'])
    g = number(data['cash_half_year_factor'])
    cash_bill = g*chosen['cash']-number(data['policy']['cash_buffer'])
    reverse_report = {'no_external_funding_max_line':max_line,
                      'buffer_only_external_funding_max_line':buffer_repair,
                      'both_constraints_no_line':repair(data,chosen,reverse,F(0)),
                      'both_constraints_max_line':repair(data,chosen,reverse,cap),
                      'minimum_external_funding':cheapest_repair(data,chosen,reverse)}
    report_s = data['report_fixture']
    actual_e = chosen['equity']-report_s['unfilled_equity_lots']*number(data['lot'])
    if actual_e < number(data['initial']['equity']) or chosen['equity'] < number(data['initial']['equity']):
        report = {'available':False,'reason':'buy-order partial-fill fixture requires nonnegative remaining equity purchases'}
    else:
        actual = assess(data,actual_e,chosen['bond'])
        target_ledger,actual_ledger,bmark_ledger = [ledger(data,p,report_s) for p in (chosen,actual,benchmark)]
        reserves = [r['terminal_reserve'] for r in (target_ledger,actual_ledger,bmark_ledger)]
        gaps = None if any(r is None for r in reserves) else {
            'policy_selection':reserves[0]-reserves[2],
            'implementation':reserves[1]-reserves[0],
            'total_vs_benchmark':reserves[1]-reserves[2]}
        report = {'available':True, 'unfilled_equity':chosen['equity']-actual_e,
                  'actual_position':actual, 'target_ledger':target_ledger,
                  'actual_ledger':actual_ledger, 'benchmark_ledger':bmark_ledger,
                  'reserve_gap_decomposition':gaps,
                  'initial_active_budget_breach':actual['active_variance']>number(data['policy']['active_variance_limit'])}
    return pack({'case':data['case'],'units':{'cash':'kCU','variance':'kCU squared',
                 'return':'simple one-year decimal','risk_denominator':'original pretrade wealth'},
                 'moment_witness':{'mean':mu,'covariance':cov,'determinant':cov[0][0]*cov[1][1]-cov[0][1]**2},
                 'optimization':solved,'benchmark':benchmark,'inherited_position':initial,
                 'risk_decomposition':{'variance_contributions':rc,'active_variance_contributions':arc,
                 'volatility_kCU_approx':sigma,'volatility_contributions_kCU_approx':None if sigma == 0 else [float(v)/sigma for v in rc],
                 'active_volatility_kCU_approx':sqrt(float(chosen['active_variance'])),
                 'volatility_fraction_initial_wealth_approx':sigma/float(number(data['wealth']))},
                 'date1_bill_thresholds':{'no_line_keep_buffer':cash_bill,
                 'max_line_keep_buffer':cash_bill+cap,'max_line_allow_zero_cash':g*chosen['cash']+cap},
                 'reverse_stress':reverse_report,'execution_report':report})


def reject_constant(value):
    raise ValueError('nonfinite JSON constant: '+value)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,default=Path(__file__).with_name('v09-c12-inputs.json'))
    parser.add_argument('--output',type=Path)
    args = parser.parse_args()
    result = run(json.loads(args.input.read_text(),parse_constant=reject_constant))
    text = json.dumps(result,indent=2,allow_nan=False)+'\n'
    if args.output:
        args.output.write_text(text)
    else:
        print(text,end='')


if __name__ == '__main__':
    main()
