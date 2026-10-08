"""Exact original acquisition cases. Standard library; no network or file writes.

Run with an optional input-file path; import analyze(data) for a quiet JSON API.
All financial output amounts are exact rational strings, not rounded estimates.
"""
from fractions import Fraction as F
import json
from pathlib import Path
import sys


def number(value, label, lower=None, strict=False):
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ValueError(label + ': use an integer or an exact decimal/fraction string')
    try:
        result = F(value)
    except (ValueError, ZeroDivisionError) as exc:
        raise ValueError(label + ': invalid finite rational') from exc
    if lower is not None and (result <= lower if strict else result < lower):
        raise ValueError(label + ': outside the documented domain')
    return result


def encode(value):
    if isinstance(value, F):
        return str(value)
    if isinstance(value, dict):
        return {key: encode(item) for key, item in value.items()}
    if isinstance(value, list):
        return [encode(item) for item in value]
    return value


def analyze(data):
    def n(value, label, lower=None, strict=False):
        return number(value, label, lower, strict)

    firms = {}
    for key in ('buyer', 'target'):
        raw = data[key]
        f = {field: n(raw[field], key + '.' + field, 0)
             for field in ('operating_value', 'excess_cash', 'debt', 'preferred')}
        f['shares'] = n(raw['shares'], key + '.shares', 0, True)
        f['equity'] = f['operating_value'] + f['excess_cash'] - f['debt'] - f['preferred']
        if f['equity'] <= 0:
            raise ValueError('Both standalone ordinary-equity values must be positive')
        f['price'] = f['equity'] / f['shares']
        firms[key] = f
    a, t = firms['buyer'], firms['target']
    raw = data['incremental']
    rate = n(raw['discount_rate'], 'incremental.discount_rate', -1, True)
    investment, integration_now, fee = [n(raw[k], k, 0) for k in
                                        ('investment_at_close', 'integration_at_close', 'fee_at_close')]
    annual = []
    years = []
    for row in raw['annual']:
        year = row['year']
        if isinstance(year, bool) or not isinstance(year, int) or year < 1:
            raise ValueError('Cash dates must be positive integer years')
        years.append(year)
        r = {key: n(row[key], key, 0) for key in
             ('control_gross', 'control_tax', 'cost_saving', 'customer_contribution', 'combination_tax', 'integration')}
        control_cash = r['control_gross'] - r['control_tax']
        combination_cash = r['cost_saving'] + r['customer_contribution'] - r['combination_tax']
        if min(control_cash, combination_cash) < 0:
            raise ValueError('This positive-benefit sensitivity requires nonnegative net receipts')
        annual.append({'year': year, 'control_cash': control_cash,
                       'combination_cash': combination_cash, 'integration_cash': r['integration'],
                       'control_pv': control_cash / (1 + rate)**year,
                       'combination_pv': combination_cash / (1 + rate)**year,
                       'integration_pv': r['integration'] / (1 + rate)**year})
    if not years or years != sorted(set(years)):
        raise ValueError('Use a nonempty chronological schedule with no repeated year')
    control = sum((r['control_pv'] for r in annual), F(0))
    combination = sum((r['combination_pv'] for r in annual), F(0))
    integration_future = sum((r['integration_pv'] for r in annual), F(0))
    immediate_costs = investment + integration_now + fee
    other_uses = t['debt'] + immediate_costs
    available_cash = a['excess_cash'] + t['excess_cash']
    debt_stock = other_uses - available_cash
    if debt_stock < 0:
        raise ValueError('This full-cash-use lab requires non-consideration uses at least equal to available cash')
    c = data['consideration']
    cash_offer = n(c['cash_offer'], 'cash_offer', 0)
    ratio = n(c['stock_ratio'], 'stock_ratio', 0)
    new_shares = ratio * t['shares']
    commitment = n(c['new_debt_commitment'], 'new_debt_commitment', 0)
    old_remaining_claims = a['debt'] + a['preferred'] + t['preferred']

    def value_case(realization, delay=0):
        gross = combination * realization / (1 + rate)**delay
        operating = a['operating_value'] + t['operating_value'] + control + gross - integration_future
        total_equity = operating - old_remaining_claims - debt_stock
        surplus = control + gross - immediate_costs - integration_future
        if total_equity <= 0 or a['equity'] + surplus <= 0:
            raise ValueError('Share formulas require positive combined equity and buyer equity plus surplus')
        cash_debt = debt_stock + cash_offer
        buyer_cash_wealth = operating - old_remaining_claims - cash_debt
        if buyer_cash_wealth < 0:
            raise ValueError('Cash-deal equity cannot be negative under this fixed-claim model')
        price = total_equity / (a['shares'] + new_shares)
        cash = {'offer': cash_offer, 'sources': available_cash + cash_debt,
                'uses': other_uses + cash_offer, 'new_debt': cash_debt,
                'funding_gap': max(F(0), cash_debt - commitment),
                'funding_slack': commitment - cash_debt,
                'feasible_under_commitment': cash_debt <= commitment,
                'buyer_wealth': buyer_cash_wealth, 'target_wealth': cash_offer,
                'buyer_gain': buyer_cash_wealth - a['equity'],
                'target_gain': cash_offer - t['equity']}
        stock = {'exchange_ratio': ratio, 'new_shares': new_shares,
                 'post_shares': a['shares'] + new_shares, 'post_price': price,
                 'combined_equity': total_equity, 'new_debt': debt_stock,
                 'sources': available_cash + debt_stock, 'uses': other_uses,
                 'funding_gap': max(F(0), debt_stock - commitment),
                 'feasible_under_commitment': debt_stock <= commitment,
                 'target_fraction': new_shares / (a['shares'] + new_shares),
                 'buyer_wealth': a['shares'] * price, 'target_wealth': new_shares * price,
                 'buyer_gain': a['shares'] * price - a['equity'],
                 'target_gain': new_shares * price - t['equity'],
                 'old_price_headline': new_shares * a['price']}
        return {'realization_fraction': realization, 'combination_delay_years': delay,
                'combination_pv': gross, 'net_surplus': surplus,
                'funded_operating_value': operating, 'cash': cash, 'stock': stock}

    base = value_case(F(1))
    surplus = base['net_surplus']
    combined = base['stock']['combined_equity']
    minimum = a['shares'] * t['equity'] / (a['equity'] + surplus)
    maximum = a['shares'] * (t['equity'] + surplus) / a['equity']
    if cash_offer >= combined:
        raise ValueError('Equivalent fixed-value stock offer requires offer below combined equity')
    equivalent_x = a['shares'] * cash_offer / (combined - cash_offer)
    equivalent_price = combined / (a['shares'] + equivalent_x)
    sensitivity = []
    for raw_fraction in data['realization_fractions']:
        fraction = n(raw_fraction, 'realization_fraction', 0)
        if fraction > 1:
            raise ValueError('Realization sensitivity is restricted to [0,1]')
        sensitivity.append(value_case(fraction))

    eraw = data['eps_case']
    ep = {key: n(eraw[key], 'eps.' + key, 0, True) for key in
          ('buyer_equity', 'target_equity', 'buyer_shares', 'target_shares', 'buyer_income', 'target_income')}
    ex = n(eraw['new_shares'], 'eps.new_shares', 0)
    eprice = (ep['buyer_equity'] + ep['target_equity']) / (ep['buyer_shares'] + ex)
    eps_before = ep['buyer_income'] / ep['buyer_shares']
    eps_after = (ep['buyer_income'] + ep['target_income']) / (ep['buyer_shares'] + ex)
    eps = {'post_price': eprice, 'eps_before': eps_before, 'eps_after': eps_after,
           'eps_accretion': eps_after / eps_before - 1,
           'buyer_wealth': ep['buyer_shares'] * eprice, 'target_wealth': ex * eprice,
           'buyer_gain': ep['buyer_shares'] * eprice - ep['buyer_equity'],
           'target_gain': ex * eprice - ep['target_equity'],
           'combined_pe': (ep['buyer_equity'] + ep['target_equity']) / (ep['buyer_income'] + ep['target_income']),
           'strict_eps_accretion_x_ceiling': ep['buyer_shares'] * ep['target_income'] / ep['buyer_income'],
           'buyer_value_x_ceiling': ep['buyer_shares'] * ep['target_equity'] / ep['buyer_equity']}

    sraw = data['signing_case']
    p = n(sraw['success_probability'], 'signing.success_probability', 0)
    if p > 1:
        raise ValueError('Success probability must be in [0,1]')
    sr = n(sraw['discount_rate'], 'signing.discount_rate', -1, True)
    signing_cost, success_buyer, success_target, failure_buyer, failure_target = [
        n(sraw[key], 'signing.' + key, 0) for key in
        ('buyer_immediate_cost', 'success_buyer_gain', 'success_target_gain', 'failure_buyer_cost', 'failure_target_cost')]
    if success_buyer + failure_buyer <= 0:
        raise ValueError('Probability-threshold illustration needs a positive success/failure buyer spread')
    sb = (p * success_buyer - (1-p) * failure_buyer) / (1+sr) - signing_cost
    st = (p * success_target - (1-p) * failure_target) / (1+sr)
    signing = {'success_probability': p, 'buyer_value': sb, 'target_value': st,
               'combined_value': sb + st,
               'buyer_break_even_probability': (signing_cost * (1+sr) + failure_buyer) / (success_buyer + failure_buyer),
               'valuation_basis': 'Supplied linear owner criterion; not an independently identified market price'}

    return encode({'chapter': 'v08-c09', 'units': data['units'], 'standalone': firms,
                   'benefit_ledger': annual,
                   'benefit_pvs': {'control': control, 'combination': combination,
                                   'initial_investment': investment,
                                   'integration_total': integration_now + integration_future,
                                   'deal_fee': fee},
                   'baseline': base,
                   'boundaries': {'economic_cash_ceiling': t['equity'] + surplus,
                                  'financeable_cash_ceiling': commitment + available_cash - other_uses,
                                  'stock_x_minimum': minimum, 'stock_x_maximum': maximum,
                                  'stock_ratio_minimum': minimum / t['shares'],
                                  'stock_ratio_maximum': maximum / t['shares'],
                                  'mutually_acceptable_stock_interval_exists': minimum <= maximum,
                                  'cash_operating_transaction_value': cash_offer + t['debt'] + t['preferred'] - t['excess_cash']},
                   'equivalent_fixed_value_stock': {'target_consideration': cash_offer,
                                                    'new_shares': equivalent_x,
                                                    'exchange_ratio': equivalent_x / t['shares'],
                                                    'post_price': equivalent_price,
                                                    'buyer_wealth': a['shares'] * equivalent_price},
                   'realization_sensitivity': sensitivity,
                   'one_year_combination_delay': value_case(F(1), 1),
                   'eps_case': eps, 'signing_case': signing})


def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name('v08-c09-inputs.json')
    data = json.loads(path.read_text(encoding='utf-8'), parse_float=str)
    print(json.dumps(analyze(data), indent=2, ensure_ascii=False, allow_nan=False))


if __name__ == '__main__':
    main()
