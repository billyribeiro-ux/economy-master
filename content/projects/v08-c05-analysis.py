#!/usr/bin/env python3
"""Original finite financing contracts; standard library, exact rational arithmetic."""
from fractions import Fraction as F
import json
from pathlib import Path
import sys

DEFAULT = Path(__file__).with_name('v08-c05-inputs.json')
TAX_RULE = 'Refund on full promised interest only after full repayment; none in default; no bridge or carryforward.'


def number(value):
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ValueError('Use an integer or exact decimal/fraction string.')
    try:
        return F(value)
    except (ValueError, ZeroDivisionError) as exc:
        raise ValueError('A finite rational value is required.') from exc


def vector(values, length=None):
    if not isinstance(values, list) or not values:
        raise ValueError('A nonempty list is required.')
    out = list(map(number, values))
    if length is not None and len(out) != length:
        raise ValueError('State vectors must have matching lengths.')
    return out


def law(values):
    out = vector(values)
    if min(out) <= 0 or sum(out) != 1:
        raise ValueError('Probabilities/valuation weights must be positive and sum to one.')
    return out


def weighted(cash, weights):
    if len(cash) != len(weights):
        raise ValueError('Cash and weights differ in length.')
    return sum(a * b for a, b in zip(cash, weights))


def price(cash, weights, rate=F(0)):
    if rate <= -1:
        raise ValueError('The gross discount factor must be positive.')
    return weighted(cash, weights) / (1 + rate)


def claims(cash, face, weights, rate=F(0)):
    if face < 0 or min(cash) < 0:
        raise ValueError('This limited-liability contract requires nonnegative cash and face.')
    debt = [min(x, face) for x in cash]
    equity = [x - d for x, d in zip(cash, debt)]
    return dict(debt_cash=debt, equity_cash=equity,
                debt_value=price(debt, weights, rate),
                equity_value=price(equity, weights, rate),
                total_value=price(cash, weights, rate))


def fair_face(cash, funding, weights):
    """Find the smallest face raising funding in the zero-rate finite-state contract."""
    if min(cash) < 0 or funding <= 0 or funding > price(cash, weights):
        raise ValueError('Funding must be positive and cannot exceed all available cash value.')
    lower = F(0)
    for upper in sorted(set(cash)):
        fixed = sum(w * x for w, x in zip(weights, cash) if x <= lower)
        alive = sum(w for w, x in zip(weights, cash) if x > lower)
        if alive:
            face = (funding - fixed) / alive
            if lower <= face <= upper:
                return face
        lower = upper
    raise ValueError('No finite face funds this contract.')


def compute(data):
    if data.get('units') != 'kCU':
        raise ValueError('The packet is denominated in kCU.')
    b = data['pricing_case']
    p, q = law(b['physical_probabilities']), law(b['valuation_weights'])
    x = vector(b['operating_cash'], len(q))
    if len(p) != len(q) or min(x) <= 0:
        raise ValueError('Positive operating cash and matched state laws are required.')
    rf = number(b['risk_free_rate'])
    tax, cost = number(b['tax_rate']), number(b['distress_cost'])
    if rf < 0 or not 0 <= tax < 1 or not 0 <= cost <= min(x):
        raise ValueError('Require nonnegative rate, tax in [0,1), and feasible distress loss.')
    if b.get('tax_rule') != TAX_RULE:
        raise ValueError('A different tax/default sequence needs a different model.')
    vu = price(x, q, rf)
    ru = weighted(x, p) / vu - 1
    mm = []
    for face in vector(b['mm_faces']):
        row = claims(x, face, q, rf)
        d, e = row['debt_value'], row['equity_value']
        if not d > 0 or not e > 0:
            raise ValueError('MM return comparisons need positive debt and equity values.')
        rd = weighted(row['debt_cash'], p) / d - 1
        re = weighted(row['equity_cash'], p) / e - 1
        row.update(face=face, debt_expected_return=rd, equity_expected_return=re,
                   debt_promised_yield=face / d - 1,
                   weighted_return=(d * rd + e * re) / vu,
                   equity_return_from_leverage=ru + (ru - rd) * d / e)
        mm.append(row)
    policies = []
    names = set()
    for policy in b['policies']:
        name, face, fee = policy['name'], number(policy['face']), number(policy['issue_fee'])
        if not isinstance(name, str) or not name or name in names or min(face, fee) < 0:
            raise ValueError('Policies need unique names and nonnegative face/fees.')
        names.add(name)
        default = [v < face for v in x]
        losses = [cost if flag else F(0) for flag in default]
        debt_cash = [v - c if flag else face for v, c, flag in zip(x, losses, default)]
        d = price(debt_cash, q, rf)
        interest = face - d
        if interest < 0 or fee > d:
            raise ValueError('This packet requires nonnegative promised interest and fees funded by proceeds.')
        shield = [F(0) if flag else tax * interest for flag in default]
        eq_cash = [v - c + s - pay for v, c, s, pay in zip(x, losses, shield, debt_cash)]
        e = price(eq_cash, q, rf)
        policies.append(dict(name=name, face=face, debt_value=d, promised_interest=interest,
                             default_states=default, debt_cash=debt_cash, equity_cash=eq_cash,
                             shield_cash=shield, distress_cash=losses, equity_value=e,
                             shield_value=price(shield, q, rf), distress_value=price(losses, q, rf),
                             total_value=d + e, issue_fee=fee, owner_wealth=d - fee + e))
    if not policies:
        raise ValueError('At least one financing policy is required.')
    best_wealth = max(v['owner_wealth'] for v in policies)

    a = data['agency_pricing']
    ap = law(a['probabilities'])
    if number(a['risk_free_rate']) != 0 or a.get('risk_neutral') is not True:
        raise ValueError('The agency/information packet explicitly assumes risk neutrality and a zero rate.')
    r = data['risk_shifting']
    choices = {name: vector(r[name + '_cash'], len(ap)) for name in ('prudent', 'gamble')}
    face, funding, fee = map(number, (r['old_face'], r['new_funding'], r['covenant_fee']))
    if fee < 0:
        raise ValueError('Covenant cost cannot be negative.')
    old = {name: claims(v, face, ap) for name, v in choices.items()}
    equilibria = []
    for anticipated, cash in choices.items():
        new_face = fair_face(cash, funding, ap)
        values = {name: claims(v, new_face, ap) for name, v in choices.items()}
        chosen_equity = values[anticipated]['equity_value']
        if chosen_equity == max(v['equity_value'] for v in values.values()):
            equilibria.append(dict(policy=anticipated, face=new_face, debt_value=funding,
                                   equity_value=chosen_equity, all_choice_equity_values={
                                       name: v['equity_value'] for name, v in values.items()},
                                   owner_wealth=funding + chosen_equity))
    if not equilibria:
        raise ValueError('No pure policy/price equilibrium in the stated two-policy menu.')
    prudent_contract = fair_face(choices['prudent'], funding, ap)
    risk = dict(old_claims=old,
                equity_value_change=old['gamble']['equity_value'] - old['prudent']['equity_value'],
                debt_value_change=old['gamble']['debt_value'] - old['prudent']['debt_value'],
                net_value_change=old['gamble']['total_value'] - old['prudent']['total_value'],
                new_debt_equilibria=equilibria, covenant_face=prudent_contract,
                covenant_owner_wealth=old['prudent']['total_value'] - fee)

    h = data['overhang']
    before = vector(h['existing_cash'], len(ap))
    increment = vector(h['incremental_cash'], len(ap))
    old_face, investment, contribution = map(number, (h['old_face'], h['investment'], h['creditor_contribution']))
    if investment <= 0 or min(increment) < 0 or not 0 <= contribution <= investment:
        raise ValueError('Positive investment, nonnegative additions and contribution within cost are required.')
    after = [a + b for a, b in zip(before, increment)]
    old_claims, new_claims = claims(before, old_face, ap), claims(after, old_face, ap)
    gain_d = new_claims['debt_value'] - old_claims['debt_value']
    gain_e = new_claims['equity_value'] - old_claims['equity_value']
    project_npv = price(increment, ap) - investment
    junior_face = fair_face(new_claims['equity_cash'], investment, ap)
    junior = claims(new_claims['equity_cash'], junior_face, ap)
    if min(after) < investment:
        raise ValueError('The displayed senior-finance alternative must be safe in every state.')
    senior_residual = [v - investment for v in after]
    senior = claims(senior_residual, old_face, ap)
    repaired_e, repaired_d = gain_e - investment + contribution, gain_d - contribution
    overhang = dict(before=old_claims, after=new_claims, project_npv=project_npv,
                    creditor_gain_before_contribution=gain_d, equity_gain_before_funding=gain_e,
                    equity_funded_npv=gain_e - investment,
                    creditor_contribution=contribution, repaired_equity_gain=repaired_e,
                    repaired_creditor_gain=repaired_d,
                    repair_individually_acceptable=(repaired_e >= 0 and repaired_d >= 0),
                    mutually_acceptable_contribution_min=max(F(0), investment - gain_e),
                    mutually_acceptable_contribution_max=min(investment, gain_d),
                    junior_face=junior_face, junior_price=junior['debt_value'],
                    equity_after_junior=junior['equity_value'],
                    consented_senior_price=investment,
                    old_debt_after_senior=senior['debt_value'], equity_after_senior=senior['equity_value'])

    t = data['information']
    low, high, prior, invest, payoff = map(number, (t['low_asset_payoff'], t['high_asset_payoff'],
        t['high_type_prior'], t['investment'], t['project_payoff']))
    if not 0 < low < high or not 0 < prior < 1 or invest <= 0 or payoff < invest:
        raise ValueError('Ordered positive types, interior prior and nonnegative project NPV required.')
    if invest >= low + payoff:
        raise ValueError('New shares must be a proper fraction and the alternative loan must be safe.')
    pooled_asset = (1 - prior) * low + prior * high
    fraction = invest / (pooled_asset + payoff)
    pool_gains = {name: (1 - fraction) * (asset + payoff) - asset
                  for name, asset in [('low', low), ('high', high)]}
    low_fraction = invest / (low + payoff)
    low_gain = (1 - low_fraction) * (low + payoff) - low
    high_deviation_gain = (1 - low_fraction) * (high + payoff) - high
    separation = low_gain >= 0 and high_deviation_gain <= 0
    information = dict(pooling_fraction=fraction, pooling_old_owner_gains=pool_gains,
                       pooling_incentive_compatible=all(v >= 0 for v in pool_gains.values()),
                       low_only_fraction=low_fraction, low_old_owner_value=low + low_gain,
                       high_old_owner_value_without_issue=high,
                       high_deviation_value=high + high_deviation_gain,
                       low_only_equilibrium_valid=separation,
                       expected_project_npv_lost=prior * (payoff - invest) if separation else None,
                       safe_debt_price=invest, safe_debt_face=invest,
                       safe_debt_old_owner_values={'low': low + payoff - invest,
                                                   'high': high + payoff - invest})
    return dict(title=data['title'], units='kCU', unlevered_value=vu, unlevered_expected_return=ru,
                mm=mm, financing_policies=policies,
                best_menu_policies=[v['name'] for v in policies if v['owner_wealth'] == best_wealth],
                risk_shifting=risk, overhang=overhang, information=information)


def serializable(value):
    if isinstance(value, F):
        return float(value)
    if isinstance(value, dict):
        return {k: serializable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [serializable(v) for v in value]
    return value


def main():
    if len(sys.argv) > 2:
        raise SystemExit('Usage: python3 v08-c05-analysis.py [input.json]')
    path = Path(sys.argv[1]) if len(sys.argv) == 2 else DEFAULT
    result = compute(json.loads(path.read_text()))
    print(json.dumps(serializable(result), indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
