"""Original finite fiscal paths; exact arithmetic, no network or file writes."""
from fractions import Fraction as F
from pathlib import Path
import json
import sys


def need(ok, message):
    if not ok:
        raise ValueError(message)


def number(value, name):
    need(isinstance(value, (str, int, float)) and not isinstance(value, bool), name+' must be numeric')
    try:
        out = F(str(value))
    except (ValueError, ZeroDivisionError, OverflowError) as exc:
        raise ValueError(name+' must be a finite rational number') from exc
    need(abs(out) <= 1000000, name+' exceeds the laboratory bound')
    return out


def path(case):
    keys = {'name', 'initial_debt', 'initial_gdp', 'periods', 'interest',
            'inflation', 'growth', 'primary_base', 'target_ratio', 'feedback',
            'surplus_cap', 'adjustment_ratios', 'maturity_fraction'}
    need(isinstance(case, dict) and set(case) == keys, 'exact case fields required')
    name = case['name']
    need(isinstance(name, str) and 0 < len(name) <= 80, 'case name required')
    n = case['periods']
    need(type(n) is int and 1 <= n <= 60, 'periods must be an integer in 1..60')
    vals = {k: number(case[k], k) for k in keys - {'name', 'periods', 'surplus_cap', 'adjustment_ratios'}}
    cap = None if case['surplus_cap'] is None else number(case['surplus_cap'], 'surplus_cap')
    adj = case['adjustment_ratios']
    need(isinstance(adj, list) and len(adj) == n, 'one adjustment ratio per period')
    adj = [number(a, 'adjustment') for a in adj]
    b, z = vals['initial_debt'], vals['initial_gdp']
    need(b >= 0 and z > 0, 'nonnegative debt and positive GDP required')
    interest, inflation, growth = (vals[k] for k in ('interest', 'inflation', 'growth'))
    need(all(-1 < v <= 1 for v in (interest, inflation, growth)), 'rate bounds are (-1,1]')
    need(0 <= vals['feedback'] <= 3 and 0 <= vals['target_ratio'] <= 5, 'feedback/target bounds')
    need(-1 <= vals['primary_base'] <= 1 and all(abs(a) <= 1 for a in adj), 'fiscal-ratio bounds')
    need(cap is None or 0 <= cap <= 1, 'surplus cap must be in [0,1]')
    mature = vals['maturity_fraction']
    need(0 <= mature <= 1, 'maturity fraction must be in [0,1]')
    r, gamma = 1+interest, (1+inflation)*(1+growth)
    initial, discount, pv_net_cash = b, F(1), F(0)
    rows = []
    for t, a in enumerate(adj, 1):
        previous_b, previous_z = b, z
        d = b/z
        requested = vals['primary_base']+vals['feedback']*(d-vals['target_ratio'])
        p = requested if cap is None else min(requested, cap)
        z *= gamma
        surplus, adjustment = p*z, a*z
        bill, maturing = interest*previous_b, mature*previous_b
        issuance = maturing+bill-surplus+adjustment
        b = previous_b-maturing+issuance
        need(b >= 0, name+': gross debt would become negative; specify an asset regime')
        need(issuance >= 0, name+': negative issuance requires an explicit buyback rule')
        ratio_from_law = (r/gamma)*d-p+a
        need(b/z == ratio_from_law, 'nominal/ratio reconciliation failed')
        discount *= r
        pv_net_cash += (surplus-adjustment)/discount
        rows.append(dict(period=t, opening_debt=previous_b, gdp=z, interest_bill=bill,
                         requested_primary_ratio=requested, primary_ratio=p,
                         surplus=surplus, adjustment=adjustment, maturing=maturing,
                         issuance=issuance, debt=b, ratio=b/z,
                         cap_limited=requested > p))
    terminal = b/discount
    need(initial == pv_net_cash+terminal, 'finite discounted identity failed')
    return dict(name=name, alpha=r/gamma, rows=rows,
                discounted_net_cash=pv_net_cash, discounted_terminal_debt=terminal,
                finite_identity_residual=initial-pv_net_cash-terminal,
                terminal_repayment_satisfied=(b == 0))


def solve(data):
    need(isinstance(data, dict) and set(data) == {'provenance', 'cases'}, 'exact root fields required')
    need(isinstance(data['provenance'], str) and bool(data['provenance']), 'provenance required')
    cases = data['cases']
    need(isinstance(cases, list) and 1 <= len(cases) <= 20, 'supply 1..20 cases')
    results = [path(case) for case in cases]
    names = [r['name'] for r in results]
    need(len(names) == len(set(names)), 'duplicate case names')
    return {'provenance': data['provenance'], 'cases': results}


def encoded(value):
    if isinstance(value, F):
        return str(value)
    if isinstance(value, dict):
        return {k: encoded(v) for k, v in value.items()}
    if isinstance(value, list):
        return [encoded(v) for v in value]
    return value


def main():
    try:
        need(len(sys.argv) <= 2, 'usage: python3 v06-c09-fiscal.py [inputs.json]')
        source = Path(sys.argv[1]) if len(sys.argv) == 2 else Path(__file__).with_name('v06-c09-fiscal-inputs.json')
        data = json.loads(source.read_text(encoding='utf-8'))
        print(json.dumps(encoded(solve(data)), indent=2))
        return 0
    except (ValueError, OSError, TypeError) as exc:
        print(json.dumps({'error': str(exc)}), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
