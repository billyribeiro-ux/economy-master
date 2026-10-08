"""Original finite project cash-flow lab. Standard library; no external data.

run(data) is quiet. Monetary computations use Fraction; output contains exact
strings and display floats. IRR search is explicitly limited to conventional
cash flows. Two-date nonconventional roots are solved as a quadratic in 1+r.
"""
from fractions import Fraction as F
from itertools import product
from math import isqrt, sqrt
from pathlib import Path
import argparse
import json

HERE = Path(__file__).resolve().parent
DEFAULT_INPUT = HERE / 'v08-c01-inputs.json'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def number(value, label):
    require(not isinstance(value, bool) and isinstance(value, (int, str)),
            label + ' must be an integer or finite decimal/fraction string')
    try:
        return F(value)
    except (ValueError, ZeroDivisionError) as exc:
        raise ValueError(label + ' must be finite') from exc


def amount(value):
    return {'exact': str(value), 'decimal': float(value)}


def npv(cash_flows, rate):
    rate = F(rate)
    require(rate > -1, 'discount rate must exceed -1')
    return sum((F(c) / (1 + rate) ** t for t, c in enumerate(cash_flows)), F(0))


def conventional_irr(cash_flows):
    """Unique root on r > -1; negative roots are retained, not called failure."""
    c = [F(v) for v in cash_flows]
    require(len(c) >= 2 and c[0] < 0 and all(v >= 0 for v in c[1:])
            and any(v > 0 for v in c[1:]), 'IRR bisection requires conventional investment cash flows')
    # Search in x = 1+r > 0. Lower endpoint zero is a limit, never evaluated.
    low, high = F(0), F(1)
    for _ in range(128):
        if npv(c, high-1) <= 0:
            break
        high *= 2
    else:
        raise ValueError('IRR exceeds this small teaching solver search range')
    for _ in range(90):
        middle = (low + high) / 2
        if npv(c, middle-1) > 0:
            low = middle
        else:
            high = middle
    return {'lower': str(low-1), 'upper': str(high-1),
            'estimate': float((low+high)/2-1),
            'domain': 'r > -1; unique conventional root; estimate is rounded'}


def two_period_roots(cash_flows):
    """All real admissible roots for C0 + C1/x + C2/x^2, x=1+r>0."""
    require(len(cash_flows) == 3, 'quadratic routine requires exactly three dates')
    a, b, c = map(F, cash_flows)
    require(a != 0, 'quadratic initial flow must be nonzero')
    discriminant = b*b - 4*a*c
    if discriminant < 0:
        return {'roots': [], 'discriminant': str(discriminant), 'classification': 'no real IRR'}
    n, d = isqrt(discriminant.numerator), isqrt(discriminant.denominator)
    if n*n == discriminant.numerator and d*d == discriminant.denominator:
        radical = F(n, d)
        roots = sorted({x-1 for x in ((-b-radical)/(2*a), (-b+radical)/(2*a)) if x > 0})
        return {'roots': [amount(v) for v in roots], 'discriminant': str(discriminant),
                'classification': 'all admissible exact roots'}
    radical = sqrt(float(discriminant))
    roots = sorted({x-1 for x in ((-float(b)-radical)/(2*float(a)),
                                  (-float(b)+radical)/(2*float(a))) if x > 0})
    return {'roots': [{'decimal': v} for v in roots], 'discriminant': str(discriminant),
            'classification': 'all admissible rounded roots'}


def run(data):
    require(isinstance(data, dict), 'inputs must be an object')
    require(data['units'] == 'kCU', 'units must be kCU')
    require(data['timing'] == 'time_0_then_annual_end_dates', 'unsupported cash timing')
    require(data['tax_convention'] == 'immediate_full_use_of_all_incremental_tax_effects',
            'tax loss/use convention must be explicit')
    rate = number(data['discount_rate'], 'discount_rate')
    require(rate > -1, 'discount rate must exceed -1')
    m = data['main']
    n = len(m['revenue'])
    require(1 <= n <= 30, 'main case requires 1 to 30 annual periods')
    names = ('revenue', 'cash_operating_cost', 'additional_fixed_cost',
             'lost_existing_contribution', 'foregone_rent', 'tax_depreciation',
             'unchanged_allocated_cost')
    arrays = {}
    for name in names:
        require(isinstance(m[name], list) and len(m[name]) == n, name + ' horizon mismatch')
        arrays[name] = [number(v, name) for v in m[name]]
        require(all(v >= 0 for v in arrays[name]), name + ' must be nonnegative')
    capex = number(m['equipment_outlay'], 'equipment_outlay')
    tau = number(m['tax_rate'], 'tax_rate')
    sale = number(m['terminal_sale'], 'terminal_sale')
    sunk = number(m['sunk_study'], 'sunk_study')
    funding = number(m['committed_time_0_funding'], 'committed_time_0_funding')
    require(capex > 0 and sale >= 0 and sunk >= 0 and funding >= 0, 'invalid cash input')
    require(0 <= tau <= 1, 'tax rate must be between zero and one')
    require(sum(arrays['tax_depreciation']) <= capex, 'tax depreciation exceeds equipment basis')
    require(isinstance(m['working_capital_balances'], list)
            and len(m['working_capital_balances']) == n+1, 'working-capital horizon mismatch')
    wc = [number(v, 'working_capital_balances') for v in m['working_capital_balances']]
    require(all(v >= 0 for v in wc) and wc[-1] == 0,
            'finite liquidated case requires nonnegative operating capital and terminal zero')
    terminal_basis = capex-sum(arrays['tax_depreciation'])
    sale_tax = tau*(sale-terminal_basis)
    after_tax_sale = sale-sale_tax
    flows = [-capex-wc[0]]
    rows = []
    for j in range(n):
        margin = (arrays['revenue'][j]-arrays['cash_operating_cost'][j]
                  -arrays['additional_fixed_cost'][j]-arrays['lost_existing_contribution'][j]
                  -arrays['foregone_rent'][j])
        taxable = margin-arrays['tax_depreciation'][j]
        tax = tau*taxable
        operating_cash = margin-tax
        delta_wc = wc[j+1]-wc[j]
        terminal = after_tax_sale if j == n-1 else F(0)
        flow = operating_cash-delta_wc+terminal
        flows.append(flow)
        rows.append({key: amount(value) for key, value in {
            'year': F(j+1), 'cash_margin': margin, 'tax_depreciation': arrays['tax_depreciation'][j],
            'taxable_operating_profit': taxable, 'operating_tax_cash': tax,
            'after_tax_operating_profit': taxable-tax,
            'operating_cash_before_working_capital': operating_cash,
            'working_capital_change': delta_wc, 'after_tax_sale': terminal,
            'project_cash_flow': flow}.items()})
    main = {'rows': rows, 'cash_flows': [amount(c) for c in flows], 'npv': amount(npv(flows, rate)),
            'terminal_tax_basis': amount(terminal_basis), 'sale_tax_cash': amount(sale_tax),
            'time_0_cash_required': amount(-flows[0]),
            'unfunded_at_time_0': amount(max(F(0), -flows[0]-funding)),
            'ignored_sunk_study': amount(sunk),
            'ignored_unchanged_allocations': [amount(v) for v in arrays['unchanged_allocated_cost']]}
    if flows[0] < 0 and all(v >= 0 for v in flows[1:]) and any(v > 0 for v in flows[1:]):
        main['irr'] = conventional_irr(flows)
    else:
        main['irr'] = {'classification': 'outside conventional IRR solver; NPV remains defined'}
    comparisons = {}
    for name, source in data['comparisons'].items():
        require(isinstance(source, list) and len(source) >= 2, name + ' needs at least two dates')
        c = [number(v, name) for v in source]
        item = {'cash_flows': [amount(v) for v in c], 'npv': amount(npv(c, rate))}
        if c[0] < 0 and all(v >= 0 for v in c[1:]) and any(v > 0 for v in c[1:]):
            item['irr'] = conventional_irr(c)
        elif len(c) == 3:
            item['irr'] = two_period_roots(c)
        elif len(c) == 2 and c[0] != 0 and -c[1]/c[0] > 0:
            item['irr'] = {'roots': [amount(-c[1]/c[0]-1)], 'classification': 'one-period root; cash orientation matters'}
        else:
            item['irr'] = {'classification': 'not analyzed; no general all-root claim'}
        comparisons[name] = item
    service = data['equal_service']
    years = service['years']
    require(type(years) is int and 1 <= years <= 30, 'service horizon must be 1 to 30 years')
    require(service['identical_replacement_available'] is True
            and service['same_service_and_zero_terminal_resale'] is True,
            'replacement comparison requires explicit same-service/repeatability/resale conditions')
    service_report = []
    for option in service['options']:
        life = option['life']
        require(type(life) is int and life > 0 and years % life == 0,
                'service horizon must be an integer multiple of each life')
        initial = number(option['initial_cost'], 'initial_cost')
        annual = number(option['annual_cost'], 'annual_cost')
        require(initial > 0 and annual >= 0, 'service costs must be nonnegative')
        costs = [F(0)]*(years+1)
        for t in range(years):
            if t % life == 0:
                costs[t] += initial
            costs[t+1] += annual
        annuity = sum((1/(1+rate)**t for t in range(1, life+1)), F(0))
        single_cost = initial+annual*annuity
        service_report.append({'name': option['name'], 'cash_costs': [amount(v) for v in costs],
                               'present_cost': amount(npv(costs, rate)),
                               'equivalent_annual_cost': amount(single_cost/annuity)})
    budget = data['capital_budget']
    require(budget['indivisible_and_additive'] is True, 'budget enumeration requires independent indivisible projects')
    available = number(budget['available_now'], 'available_now')
    require(available >= 0 and 1 <= len(budget['projects']) <= 12, 'small finite budget domain')
    projects = []
    for p in budget['projects']:
        cost = number(p['initial_cost'], 'initial_cost')
        receipt = number(p['year_1_receipt'], 'year_1_receipt')
        require(cost > 0 and receipt >= 0, 'budget project amounts invalid')
        projects.append((p['name'], cost, receipt/(1+rate)-cost))
    require(len({p[0] for p in projects}) == len(projects), 'budget project names must be unique')
    feasible = []
    for flags in product((0, 1), repeat=len(projects)):
        picked = [p for p, flag in zip(projects, flags) if flag]
        cost = sum((p[1] for p in picked), F(0))
        if cost <= available:
            value = sum((p[2] for p in picked), F(0))
            feasible.append((value, cost, [p[0] for p in picked]))
    best = max(p[0] for p in feasible)
    result = {'case_id': data['case_id'], 'units': data['units'], 'rate': amount(rate),
              'main': main, 'comparisons': comparisons, 'equal_service': service_report,
              'capital_budget': {'feasible_subsets': len(feasible), 'maximum_npv': amount(best),
                                 'optimal_sets': [p[2] for p in feasible if p[0] == best]},
              'limits': ['Fictional, immediately usable linear tax effects; no actual jurisdiction.',
                         'Supplied rate, not a rate-estimation or financing-value model.',
                         'Time-0 funding gap only; no full treasury calendar.',
                         'General nonconventional IRRs require separate all-root analysis.']}
    json.dumps(result, allow_nan=False)
    return result


def read_inputs(path=DEFAULT_INPUT):
    return json.loads(Path(path).read_text(), parse_float=str)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('inputs', nargs='?', type=Path, default=DEFAULT_INPUT)
    args = parser.parse_args()
    try:
        result = run(read_inputs(args.inputs))
    except (ValueError, KeyError, TypeError, OSError) as exc:
        parser.exit(2, 'Input error: '+str(exc)+'\n')
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
