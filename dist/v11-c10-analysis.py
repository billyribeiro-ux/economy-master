#!/usr/bin/env python3
"""Original finite regulation cases. Exact arithmetic; no current-law inference."""
import argparse
from fractions import Fraction
import json
from pathlib import Path
import re

MAX_BYTES = 262144
NUM = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+|/[1-9][0-9]*)?\Z")
NAME = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,31}\Z")


def require(ok, message):
    if not ok:
        raise ValueError(message)


def obj(value, keys, label):
    require(type(value) is dict, label + ': object required')
    require(set(value) == set(keys.split()), label + ': unexpected or missing fields')
    return value


def number(value, label, low=Fraction(0), high=Fraction(1000000)):
    require(type(value) is str and len(value) <= 40 and NUM.fullmatch(value),
            label + ': bounded rational string required')
    try:
        n = Fraction(value)
    except (ValueError, ZeroDivisionError) as exc:
        raise ValueError(label + ': invalid rational') from exc
    require(abs(n.numerator) <= 10**12 and n.denominator <= 10**6,
            label + ': numerator or denominator too large')
    require(low <= n <= high, label + ': outside supported bounds')
    return n


def name(value, label):
    require(type(value) is str and NAME.fullmatch(value), label + ': invalid identifier')
    return value


def sequence(value, label, low, high):
    require(type(value) is list and low <= len(value) <= high, label + ': invalid list length')
    return value


def best(rows, field):
    if not rows:
        return []
    m = max(row[field] for row in rows)
    return [row['id'] for row in rows if row[field] == m]


def pack(value):
    if isinstance(value, Fraction):
        return str(value)
    if isinstance(value, list):
        return [pack(x) for x in value]
    if isinstance(value, dict):
        return {k: pack(v) for k, v in value.items()}
    return value


def portfolio(raw):
    obj(raw, 'initial_assets capital insurer_reserve harm_if_default probabilities options policies capture_weight', 'portfolio')
    a0 = number(raw['initial_assets'], 'initial_assets', Fraction(1))
    k = number(raw['capital'], 'capital', high=a0)
    deposits = a0-k
    reserve = number(raw['insurer_reserve'], 'insurer_reserve')
    harm = number(raw['harm_if_default'], 'harm_if_default')
    weight = number(raw['capture_weight'], 'capture_weight', high=Fraction(10))
    probs = [number(x, 'state probability', high=Fraction(1))
             for x in sequence(raw['probabilities'], 'probabilities', 2, 6)]
    require(sum(probs) == 1, 'state probabilities must sum exactly to one')
    rows, exposures, seen = [], {}, set()
    for r in sequence(raw['options'], 'options', 1, 6):
        obj(r, 'id assets reported_exposure lookthrough_exposure', 'option')
        ident = name(r['id'], 'option id')
        require(ident not in seen, 'duplicate option id')
        seen.add(ident)
        values = [number(x, 'terminal asset') for x in sequence(r['assets'], 'assets', len(probs), len(probs))]
        exposures[ident] = {basis: number(r[basis+'_exposure'], basis+' exposure')
                           for basis in ('reported', 'lookthrough')}
        states = []
        for p, a in zip(probs, values):
            short = max(deposits-a, Fraction(0))
            require(short <= reserve, 'insurer reserve does not fund every supported state')
            residual = max(a-deposits, Fraction(0))
            states.append({'probability': p, 'assets': a, 'deposit_from_bank': min(a, deposits),
                           'insurance_payment': short, 'deposit_total': deposits,
                           'equity_residual': residual, 'insurer_closing_reserve': reserve-short,
                           'real_harm': harm if a < deposits else Fraction(0),
                           'default': a < deposits})
        expected_assets = sum(p*a for p, a in zip(probs, values))
        premium_transfer = sum(s['probability']*s['insurance_payment'] for s in states)
        private = sum(s['probability']*s['equity_residual'] for s in states)-k
        external = sum(s['probability']*s['real_harm'] for s in states)
        rows.append({'id': ident, 'states': states, 'expected_assets': expected_assets,
                     'asset_gain': expected_assets-a0, 'private_profit': private,
                     'expected_insurance': premium_transfer,
                     'default_probability': sum((s['probability'] for s in states if s['default']), Fraction(0)),
                     'expected_real_harm': external, 'welfare_before_policy_cost': expected_assets-a0-external})
    policies, policy_seen = [], set()
    for p in sequence(raw['policies'], 'policies', 1, 6):
        obj(p, 'id basis ratio resource_cost', 'policy')
        ident = name(p['id'], 'policy id')
        require(ident not in policy_seen, 'duplicate policy id')
        policy_seen.add(ident)
        require(p['basis'] in ('reported', 'lookthrough'), 'unsupported exposure basis')
        ratio = number(p['ratio'], 'ratio', high=Fraction(1))
        cost = number(p['resource_cost'], 'policy resource cost')
        required = {r['id']: ratio*exposures[r['id']][p['basis']] for r in rows}
        feasible = [r for r in rows if k >= required[r['id']]]
        choices = best(feasible, 'private_profit')
        outcomes = []
        for r in feasible:
            if r['id'] in choices:
                w = r['welfare_before_policy_cost']-cost
                outcomes.append({'choice': r['id'], 'private_profit': r['private_profit'],
                                 'welfare': w, 'score': w+weight*r['private_profit']})
        policies.append({'id': ident, 'required_capital': required,
                         'feasible': [r['id'] for r in feasible], 'best_responses': choices,
                         'status': 'feasible' if feasible else 'no feasible option',
                         'outcomes': outcomes})
    active = [p for p in policies if p['outcomes']]
    ambiguous = any(len({r['score'] for r in p['outcomes']}) > 1 for p in active)
    rankings = None if ambiguous else best(
        [{'id': p['id'], 'score': p['outcomes'][0]['score']} for p in active], 'score')
    return {'initial_deposits': deposits, 'options': rows, 'policies': policies,
            'score_maximizers': rankings,
            'ranking_status': 'tie-dependent; inspect all outcomes' if ambiguous else 'determinate over feasible policies'}


def conduct(raw):
    obj(raw, 'fee gross_benefit care_cost harm care_harm_probability shortcut_harm_probability inspection_probability fine pledged_funds inspection_cost authority_budget', 'conduct')
    x = {k: number(v, k, high=Fraction(1) if k.endswith('probability') else Fraction(1000000))
         for k, v in raw.items()}
    require(x['care_cost'] <= x['fee'], 'care cost must be financed by fee in this case family')
    require(x['care_harm_probability'] <= x['shortcut_harm_probability'], 'care cannot increase harm in this family')
    a = x['inspection_probability']
    require(a == 0 or x['authority_budget'] >= x['inspection_cost'], 'inspection not funded in every inspection state')
    collectible = min(x['fine'], x['pledged_funds'])
    expense = a*x['inspection_cost']
    rows = []
    for ident, cost, probability, payment in (
        ('care', x['care_cost'], x['care_harm_probability'], Fraction(0)),
        ('shortcut', Fraction(0), x['shortcut_harm_probability'], a*collectible)):
        harm = probability*x['harm']
        seller = x['fee']-cost-payment
        buyer = x['gross_benefit']-x['fee']-harm
        authority = payment-expense
        rows.append({'id': ident, 'seller_profit': seller, 'buyer_net': buyer,
                     'authority_net': authority, 'expected_fine': payment, 'expected_harm': harm,
                     'expected_real_care_cost': cost, 'expected_inspection_cost': expense,
                     'welfare': buyer+seller+authority})
    return {'collectible_fine': collectible, 'deterrence_margin': a*collectible-x['care_cost'],
            'best_responses': best(rows, 'seller_profit'), 'actions': rows}


def resolution(raw):
    obj(raw, 'cash long_assets asset_loss deposits senior junior conversion capital_floor due_first bridge_capacity lender_cash bridge_rate liquidation_cost', 'resolution')
    x = {k: number(v, k, high=Fraction(1) if k == 'bridge_rate' else Fraction(1000000)) for k, v in raw.items()}
    cash, long = x['cash'], x['long_assets']
    d, s, j = x['deposits'], x['senior'], x['junior']
    initial_equity = cash+long-d-s-j
    require(initial_equity >= 0, 'opening balance sheet must have nonnegative equity')
    require(x['asset_loss'] <= long, 'asset loss exceeds long assets')
    remaining_assets = cash+long-x['asset_loss']
    require(d <= remaining_assets <= d+s, 'supported resolution family wipes old equity and junior, protects deposits')
    senior_after = remaining_assets-d
    conversion = x['conversion']
    require(conversion <= senior_after, 'conversion exceeds surviving senior claim')
    require(x['due_first'] <= d, 'first deposit payment exceeds total deposits')
    require(x['bridge_capacity'] <= x['lender_cash'], 'committed bridge is not externally funded')
    require(x['liquidation_cost'] <= remaining_assets, 'liquidation cost exceeds remaining assets')
    gap = max(x['due_first']-cash, Fraction(0))
    interest = gap*x['bridge_rate']
    funding_ok = gap <= x['bridge_capacity']
    terminal_ok = conversion >= interest
    snapshots = []
    def snap(label, c, la, de, se, ju, br, e):
        require(c+la == de+se+ju+br+e, 'internal journal does not balance')
        snapshots.append({'stage': label, 'cash': c, 'long_assets': la, 'deposits': de,
                          'senior': se, 'junior': ju, 'bridge': br, 'equity': e})
    z = Fraction(0)
    snap('opening', cash, long, d, s, j, z, initial_equity)
    long -= x['asset_loss']
    snap('after_asset_loss', cash, long, d, s, j, z, initial_equity-x['asset_loss'])
    snap('after_write_down', cash, long, d, senior_after, z, z, z)
    snap('after_conversion', cash, long, d, senior_after-conversion, z, z, conversion)
    final = None
    if funding_ok:
        snap('after_bridge', cash+gap, long, d, senior_after-conversion, z, gap, conversion)
        cash = cash+gap-x['due_first']
        dep = d-x['due_first']
        snap('after_first_payment', cash, long, dep, senior_after-conversion, z, gap, conversion)
        cash += long
        snap('maturity_before_payments', cash, z, dep, senior_after-conversion, z, gap+interest, conversion-interest)
        if terminal_ok:
            cash -= dep+(senior_after-conversion)+gap+interest
            snap('after_final_payments', cash, z, z, z, z, z, cash)
            final = {'cash_and_equity': cash, 'deposit_receipts_total': d,
                     'old_senior_debt_receipts': senior_after-conversion,
                     'old_senior_new_equity_value': cash,
                     'old_senior_total_value': senior_after-interest,
                     'lender_repayment': gap+interest, 'lender_net_interest': interest,
                     'old_claims_total_value': d+senior_after-interest}
    liquid = remaining_assets-x['liquidation_cost']
    liquid_d = min(d, liquid)
    liquid_s = min(s, max(z, liquid-d))
    return {'original_equity': initial_equity, 'remaining_assets': remaining_assets,
            'loss_absorption': {'old_equity': initial_equity, 'junior': j, 'senior': s-senior_after},
            'surviving_senior_before_conversion': senior_after,
            'first_cash_gap': gap, 'minimum_external_advance': gap,
            'unfunded_first_gap': max(z, gap-x['bridge_capacity']),
            'bridge_interest_if_funded': interest,
            'first_cutoff_funded': funding_ok, 'terminal_claims_funded_if_bridge': terminal_ok,
            'capital_after_conversion': conversion,
            'capital_after_interest_if_funded': conversion-interest,
            'immediate_capital_pass': conversion >= x['capital_floor'],
            'continuing_capital_pass': funding_ok and conversion-interest >= x['capital_floor'],
            'status': ('first cutoff unfunded; no payment continuation assumed' if not funding_ok else
                       'terminal claims underfunded; no final allocation assumed' if not terminal_ok else 'funded continuation'),
            'snapshots': snapshots, 'final': final,
            'liquidation': {'net_assets': liquid, 'deposit_receipts': liquid_d,
                            'senior_receipts': liquid_s, 'junior_receipts': z, 'old_equity_receipts': z}}


def run(data):
    """Validate and return JSON-safe exact-rational results; never mutate data or print."""
    obj(data, 'schema provenance portfolio conduct resolution', 'root')
    require(type(data['schema']) is int and data['schema'] == 1, 'schema must be integer 1')
    require(type(data['provenance']) is str and 1 <= len(data['provenance']) <= 1000, 'provenance required')
    return pack({'schema': 1, 'chapter': 'v11-c10', 'portfolio': portfolio(data['portfolio']),
                 'conduct': conduct(data['conduct']), 'resolution': resolution(data['resolution'])})


def unique(pairs):
    result = {}
    for k, v in pairs:
        require(k not in result, 'duplicate JSON key: '+k)
        result[k] = v
    return result


def bad_constant(value):
    raise ValueError('nonfinite JSON number: '+value)


def load(path):
    raw = path.read_bytes()
    require(len(raw) <= MAX_BYTES, 'input exceeds byte limit')
    return json.loads(raw.decode('utf-8'), object_pairs_hook=unique, parse_constant=bad_constant)


def protect_output(destination, source):
    for protected in (source, Path(__file__)):
        require(destination.resolve() != protected.resolve(), 'output aliases input or implementation')
        if destination.exists() and protected.exists():
            require(not destination.samefile(protected), 'output aliases input or implementation')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=Path(__file__).with_name('v11-c10-inputs.json'))
    parser.add_argument('--output', type=Path, default=Path(__file__).with_name('v11-c10-output.json'))
    args = parser.parse_args()
    try:
        protect_output(args.output, args.input)
        result = run(load(args.input))
        encoded = json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False)+'\n'
        args.output.write_text(encoded, encoding='utf-8')
    except (ValueError, TypeError, OSError, UnicodeError, RecursionError) as exc:
        parser.exit(2, 'error: '+str(exc)+'\n')


if __name__ == '__main__':
    main()
