"""Original finite dated-cash laboratory; standard library only.

All financial numbers enter as exact decimal/fraction strings or integers.
No price feed, market calibration, exchange rule or universal valuation engine.
"""
import argparse
from fractions import Fraction as F
import json
from pathlib import Path


def fields(value, names, label):
    if not isinstance(value, dict) or set(value) != set(names.split()):
        raise ValueError(label + ': unexpected or missing fields')


def number(value, label, lower=-10**9, upper=10**9, positive=False):
    if type(value) not in (str, int) or (isinstance(value, str) and len(value) > 64):
        raise ValueError(label + ': use a bounded exact decimal/fraction string or integer')
    try:
        result = F(value)
    except (ValueError, ZeroDivisionError) as exc:
        raise ValueError(label + ': invalid rational') from exc
    if result.denominator > 10**12 or abs(result.numerator) > 10**24:
        raise ValueError(label + ': rational precision out of scope')
    if not lower <= result <= upper or (positive and result <= 0):
        raise ValueError(label + ': out of scope')
    return result


def vector(value, label, size=None, lower=-10**9, upper=10**9, positive=False):
    if not isinstance(value, list) or not 1 <= len(value) <= 24 or (size is not None and len(value) != size):
        raise ValueError(label + ': invalid list length')
    return [number(x, label, lower, upper, positive) for x in value]


def encoded(value):
    if isinstance(value, F):
        return str(value)
    if isinstance(value, dict):
        return {k: encoded(v) for k, v in value.items()}
    if isinstance(value, list):
        return [encoded(v) for v in value]
    return value


def run(data):
    fields(data, 'schema provenance carry fx tree margin swap collateral basis', 'root')
    if data['schema'] != 'v10-c05-1' or not isinstance(data['provenance'], str):
        raise ValueError('unknown schema or invalid provenance')
    c = data['carry']
    fields(c, 'spot maturity discount delivery_price events', 'carry')
    s = number(c['spot'], 'spot', positive=True)
    maturity = number(c['maturity'], 'maturity', 0, 30, True)
    d = number(c['discount'], 'discount', 0, 3, True)
    k = number(c['delivery_price'], 'delivery_price', 0)
    if not isinstance(c['events'], list) or len(c['events']) > 24:
        raise ValueError('carry events length')
    rows = []
    last = F(0)
    prepaid = s
    for e in c['events']:
        fields(e, 'time discount income cost', 'carry event')
        t = number(e['time'], 'event time', 0, 30, True)
        if not last < t < maturity:
            raise ValueError('carry events must be strictly increasing and before delivery')
        last = t
        df = number(e['discount'], 'event discount', 0, 3, True)
        income = number(e['income'], 'income', 0)
        cost = number(e['cost'], 'cost', 0)
        net = income - cost
        prepaid -= net * df
        rows.append({'time': t, 'asset_net_receipt': net,
                     'strip_borrowing_at_zero': net * df, 'strip_repayment': net,
                     'interim_net_cash': F(0)})
    if prepaid <= 0:
        raise ValueError('nonpositive prepaid delivery is outside this positive-asset model')
    carry = {'prepaid_delivery': prepaid, 'fair_forward': prepaid / d,
             'long_value': prepaid - k*d, 'terminal_excess_of_quoted_delivery': k - prepaid/d,
             'replication': rows, 'maturity_borrowing_at_zero': prepaid,
             'maturity_repayment': prepaid/d,
             'initial_cash_residual': prepaid + sum((r['strip_borrowing_at_zero'] for r in rows), F(0)) - s}

    x = data['fx']
    fields(x, 'spot_domestic_per_foreign domestic_discount foreign_discount delivery_price foreign_notional', 'fx')
    sx = number(x['spot_domestic_per_foreign'], 'FX spot', 0, 10**6, True)
    dd = number(x['domestic_discount'], 'domestic discount', 0, 3, True)
    df = number(x['foreign_discount'], 'foreign discount', 0, 3, True)
    kx = number(x['delivery_price'], 'FX delivery', 0, 10**6)
    n = number(x['foreign_notional'], 'foreign notional', 0, 10**9, True)
    fx = {'fair_domestic_per_foreign': sx*df/dd, 'domestic_prepaid_per_foreign': sx*df,
          'foreign_deposit_today': n*df, 'domestic_funding_today': n*sx*df,
          'domestic_funding_repayment': n*sx*df/dd,
          'long_value_domestic': n*(sx*df-kx*dd),
          'short_terminal_surplus_domestic': n*(kx-sx*df/dd)}

    z = data['tree']
    fields(z, 'first_gross probabilities second_gross terminal_spot', 'tree')
    r0 = number(z['first_gross'], 'first gross', F(1, 10), 3)
    p = vector(z['probabilities'], 'probabilities', lower=0, upper=1, positive=True)
    if sum(p) != 1:
        raise ValueError('probabilities must sum exactly to one')
    r = vector(z['second_gross'], 'second gross', len(p), F(1, 10), 3)
    st = vector(z['terminal_spot'], 'terminal spot', len(p), 0, positive=True)
    discounts = [1/(r0*a) for a in r]
    bond = sum((w*a for w, a in zip(p, discounts)), F(0))
    spot = sum((w*a*b for w, a, b in zip(p, discounts, st)), F(0))
    g = sum((w*a for w, a in zip(p, st)), F(0))
    forward = spot/bond
    terminal_futures = [(s2-g)*gross for s2, gross in zip(st, r)]
    tree = {'bond_price': bond, 'spot_price': spot, 'node_spot': [b/a for a,b in zip(r,st)],
            'path_discounts': discounts, 'forward_quote': forward, 'futures_quote': g,
            'futures_minus_forward': g-forward, 'covariance_spot_discount': spot-g*bond,
            'date_one_variation': [s2-g for s2 in st], 'funded_terminal_futures': terminal_futures,
            'forward_terminal': [s2-forward for s2 in st],
            'futures_discounted_value': sum((w*a*b for w,a,b in zip(p,discounts,terminal_futures)), F(0)),
            'forward_discounted_value': sum((w*a*(b-forward) for w,a,b in zip(p,discounts,st)), F(0))}

    m = data['margin']
    fields(m, 'contracts multiplier quotes initial maintenance funding_gross', 'margin')
    contracts = number(m['contracts'], 'contracts', -10000, 10000)
    if contracts.denominator != 1 or contracts == 0:
        raise ValueError('nonzero integer contracts required')
    mult = number(m['multiplier'], 'multiplier', 0, 10**6, True)
    quotes = vector(m['quotes'], 'quotes', lower=-10**6, upper=10**6)
    if len(quotes) < 2:
        raise ValueError('at least two settlement quotes required')
    gross = vector(m['funding_gross'], 'funding gross', len(quotes)-1, F(1, 10), 3)
    initial = number(m['initial'], 'initial', 0, 10**9, True)
    maintenance = number(m['maintenance'], 'maintenance', 0, initial, True)
    account, debt, posted = initial, initial, initial
    ledger = []
    for i, (old, new, rate) in enumerate(zip(quotes, quotes[1:], gross), 1):
        debt *= rate
        variation = contracts*mult*(new-old)
        account += variation
        before = account
        final = i == len(gross)
        call = max(-account, F(0)) if final else (initial-account if account < maintenance else F(0))
        account += call
        debt += call
        posted += call
        ledger.append({'date': i, 'variation': variation, 'balance_before_call': before,
                       'call': call, 'balance_after_call': account, 'funding_debt': debt})
    vm_total = sum((row['variation'] for row in ledger), F(0))
    margin = {'ledger': ledger, 'total_variation': vm_total, 'total_posted': posted,
              'terminal_release': account, 'terminal_funding_debt': debt,
              'funding_cost': debt-posted, 'net_after_funding': account-debt,
              'cash_identity_residual': account-posted-vm_total}

    a = data['swap']
    fields(a, 'notional accruals discounts projected_rates fixed_rate', 'swap')
    n = number(a['notional'], 'swap notional', 0, 10**9, True)
    alpha = vector(a['accruals'], 'accruals', lower=0, upper=5, positive=True)
    ds = vector(a['discounts'], 'swap discounts', len(alpha), 0, 3, True)
    fs = vector(a['projected_rates'], 'projected rates', len(alpha), -2, 2)
    fixed = number(a['fixed_rate'], 'fixed rate', -2, 2)
    if any(1+ac*f <= 0 for ac,f in zip(alpha,fs)):
        raise ValueError('projected gross factor must be positive')
    annuity = sum((ac*di for ac,di in zip(alpha,ds)), F(0))
    leg = sum((ac*di*fi for ac,di,fi in zip(alpha,ds,fs)), F(0))
    previous = [F(1)] + ds[:-1]
    single_rates = [(prior/di-1)/ac for prior,di,ac in zip(previous,ds,alpha)]
    swap = {'annuity': annuity, 'floating_pv': n*leg, 'fixed_pv': n*fixed*annuity,
            'payer_fixed_value': n*(leg-fixed*annuity), 'par_fixed': leg/annuity,
            'single_curve_rates': single_rates, 'single_curve_floating_pv': n*(1-ds[-1]),
            'single_curve_par': (1-ds[-1])/annuity,
            'pv_change_per_fixed_rate_unit': -n*annuity,
            'projected_coupon_amounts': [n*ac*fi for ac,fi in zip(alpha,fs)]}

    a = data['collateral']
    fields(a, 'receipt collateral_gross segregated_initial funding_rate remuneration_rate year_fraction', 'collateral')
    h = number(a['receipt'], 'receipt', 0, positive=True)
    cg = number(a['collateral_gross'], 'collateral gross', F(1,10), 3)
    im = number(a['segregated_initial'], 'segregated initial', 0)
    fr = number(a['funding_rate'], 'funding rate', -1, 2)
    cr = number(a['remuneration_rate'], 'remuneration rate', -1, 2)
    tau = number(a['year_fraction'], 'year fraction', 0, 5, True)
    if min(1+fr*tau,1+cr*tau) <= 0:
        raise ValueError('simple funding and remuneration gross factors must be positive')
    collateral = {'fully_reusable_claim_value': h/cg,
                  'segregated_funding_repayment': im*(1+fr*tau),
                  'segregated_margin_return': im*(1+cr*tau),
                  'segregated_net_cost': im*(fr-cr)*tau}

    a = data['basis']
    fields(a, 'units initial_futures terminal_futures terminal_local_spot contracts multiplier funding_cost', 'basis')
    units = number(a['units'], 'units', 0, positive=True)
    gi = number(a['initial_futures'], 'initial futures')
    gt = number(a['terminal_futures'], 'terminal futures')
    sl = number(a['terminal_local_spot'], 'local spot')
    cn = number(a['contracts'], 'short contracts', 0, 10000)
    if cn.denominator != 1:
        raise ValueError('basis contracts must be integers')
    mul = number(a['multiplier'], 'basis multiplier', 0, 10**6, True)
    fc = number(a['funding_cost'], 'funding cost')
    sale = units*sl
    futures = cn*mul*(gi-gt)
    basis = {'sale_receipt': sale, 'nominal_futures_receipt': futures,
             'terminal_local_basis': sl-gt, 'cash_before_funding': sale+futures,
             'cash_after_funding': sale+futures-fc,
             'matched_quantity': cn*mul == units}
    return encoded({'schema': data['schema'], 'carry': carry, 'fx': fx, 'tree': tree,
                    'margin': margin, 'swap': swap, 'collateral': collateral, 'basis': basis})


def reject_constant(value):
    raise ValueError('nonfinite JSON constant: '+value)


def unique_object(pairs):
    result = {}
    for key,value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key: '+key)
        result[key] = value
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    try:
        data = json.loads(args.input.read_text(), parse_constant=reject_constant, object_pairs_hook=unique_object)
        output = json.dumps(run(data), indent=2, allow_nan=False)+'\n'
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    if args.output:
        args.output.write_text(output)
    else:
        print(output, end='')


if __name__ == '__main__':
    main()
