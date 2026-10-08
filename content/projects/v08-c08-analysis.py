#!/usr/bin/env python3
"""Original finite real-options lab. Exact arithmetic; no network or packages."""
from fractions import Fraction as F
import json
from pathlib import Path
import sys


def require(condition, message):
    if not condition:
        raise ValueError(message)


def number(value):
    require(isinstance(value, (str, int)) and not isinstance(value, bool),
            'Use integer or exact decimal/fraction strings for numeric inputs')
    return F(value)


def probability(value):
    x = number(value)
    require(0 <= x <= 1, 'Probability must lie in [0,1]')
    return x


def gross_rate(value):
    g = 1 + number(value)
    require(g > 0, 'Gross discount factor must be positive')
    return g


def compute(data):
    d = data['delay']
    require(d['valuation'] == 'traded_clone_replication', 'Delay case requires the traded-clone contract')
    s, u, down, k = (number(d[x]) for x in ('spot', 'up', 'down', 'exercise_cost'))
    g = gross_rate(d['risk_free'])
    p = probability(d['physical_up'])
    require(0 < p < 1, 'The traded-clone model requires both physical states to be possible')
    receipt = number(d['interim_receipt_if_immediate'])
    require(s > 0 and down >= 0 and k >= 0 and receipt >= 0, 'Clone, cost and receipt bounds invalid')
    require(down < g * s < u, 'Strict no-arbitrage condition down < gross*spot < up required')
    pricing_up = (g * s - down) / (u - down)
    cu, cd = max(u - k, F(0)), max(down - k, F(0))
    delta = (cu - cd) / (u - down)
    bond = (cd - delta * down) / g
    value = delta * s + bond
    expected = p * cu + (1 - p) * cd
    underlying_expected_return = (p * u + (1 - p) * down) / s - 1
    immediate = s - k
    delay = dict(pricing_up=pricing_up, up_payoff=cu, down_payoff=cd,
                 delta=delta, bond_now=bond, value=value,
                 immediate_npv=immediate, preferred_base_value=max(F(0), immediate, value),
                 physical_expected_payoff=expected,
                 underlying_expected_return=underlying_expected_return,
                 option_expected_return=expected / value - 1 if value > 0 else None,
                 wrong_physical_risk_free_pv=expected / g,
                 wrong_underlying_return_pv=expected / (1 + underlying_expected_return) if underlying_expected_return > -1 else None,
                 immediate_package_with_receipt=s + receipt / g,
                 immediate_npv_with_receipt=immediate + receipt / g,
                 interim_receipt_switch=(value - immediate) * g)

    d = data['operations']
    require(d['valuation'] == 'linear_owner_expected_money', 'Owner case has no supplied market pricing model')
    g = gross_rate(d['rate'])
    initial, cash = number(d['initial_cost']), number(d['expansion_cash_available'])
    require(initial >= 0 and cash >= 0, 'Initial cost and funding capacity must be nonnegative')
    probs = [probability(row['probability']) for row in d['states']]
    require(bool(probs) and sum(probs) == 1, 'State probabilities must sum exactly to one')
    require(len({row['name'] for row in d['states']}) == len(probs), 'Distinct state names required')
    rows = []
    for p, row in zip(probs, d['states']):
        base, extra, cost, salvage = (number(row[x]) for x in ('base', 'expansion_gross', 'expansion_cost', 'salvage'))
        require(cost >= 0, 'Expansion cost must be nonnegative')
        choices = {'continue': base, 'abandon': salvage}
        if cost <= cash:
            choices['expand'] = base + extra - cost
        best = max(choices, key=choices.get)
        rows.append(dict(name=row['name'], probability=p, base=base, choices=choices,
                         action=best, optimal=choices[best],
                         expansion_only=max(base, choices.get('expand', base)),
                         abandonment_only=max(base, salvage)))
    base = sum(row['probability'] * row['base'] for row in rows) / g
    flex = sum(row['probability'] * row['optimal'] for row in rows) / g
    operations = dict(states=rows, base_value=base, flexible_value=flex,
                      base_npv=base-initial, flexible_npv=flex-initial, flexibility_gain=flex-base,
                      expansion_only_gain=sum(row['probability'] * (row['expansion_only']-row['base']) for row in rows)/g,
                      abandonment_only_gain=sum(row['probability'] * (row['abandonment_only']-row['base']) for row in rows)/g)

    d = data['stage']
    require(d['valuation'] == 'linear_owner_expected_money', 'Owner case has no supplied market pricing model')
    g = gross_rate(d['rate'])
    p = probability(d['validation_probability'])
    pilot, cost, success, failure = (number(d[x]) for x in ('pilot_cost', 'scale_cost', 'validated_receipt', 'failed_receipt'))
    require(min(pilot, cost, success, failure) >= 0, 'Costs and final receipts must be nonnegative')
    high, low = success / g - cost, failure / g - cost
    staged = -pilot + (p * max(F(0), high) + (1-p) * max(F(0), low)) / g
    forced = -pilot + (p * high + (1-p) * low) / g
    stage = dict(validated_continuation=high, failed_continuation=low, staged_npv=staged,
                 forced_npv=forced, stopping_gain=staged-forced,
                 minimum_validation_probability=pilot*g/high if high > 0 and low <= 0 else None)

    d = data['information']
    require(d['valuation'] == 'linear_owner_expected_money', 'Owner case has no supplied market pricing model')
    g = gross_rate(d['rate'])
    p = probability(d['good_prior'])
    likelihoods = [probability(d['positive_if_good']), probability(d['positive_if_bad'])]
    k, high, low, fee = (number(d[x]) for x in ('launch_cost', 'good_receipt', 'bad_receipt', 'report_fee_now'))
    require(min(k, high, low, fee) >= 0 and high > low, 'Nonnegative amounts and ordered receipts required')
    baseline_node = max(F(0), (p*high+(1-p)*low)/g-k)
    rows = []
    for label, hg, lb in [('positive', *likelihoods), ('negative', 1-likelihoods[0], 1-likelihoods[1])]:
        probability_signal = p*hg+(1-p)*lb
        if probability_signal == 0:
            rows.append(dict(signal=label, probability=F(0), posterior_good=None,
                             launch_npv=None, action='unreachable', optimal=F(0)))
            continue
        posterior = p*hg/probability_signal
        npv = (posterior*high+(1-posterior)*low)/g-k
        rows.append(dict(signal=label, probability=probability_signal, posterior_good=posterior,
                         launch_npv=npv, action='launch' if npv >= 0 else 'reject', optimal=max(F(0), npv)))
    baseline = baseline_node/g
    informed = sum(row['probability']*row['optimal'] for row in rows)/g
    perfect = (p*max(F(0), high/g-k)+(1-p)*max(F(0), low/g-k))/g
    information = dict(signals=rows, posterior_threshold=(k*g-low)/(high-low),
                       no_report_value=baseline, gross_report_value=informed,
                       net_report_value=informed-fee, evsi=informed-baseline,
                       perfect_information_value=perfect, evpi=perfect-baseline,
                       buy_report=(informed-fee >= baseline))
    return dict(delay=delay, operations=operations, stage=stage, information=information)


def serial(value):
    if isinstance(value, F):
        return {'exact': str(value), 'decimal': round(float(value), 9)}
    if isinstance(value, dict):
        return {k: serial(v) for k, v in value.items()}
    if isinstance(value, list):
        return [serial(v) for v in value]
    return value


if __name__ == '__main__':
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name('v08-c08-inputs.json')
    try:
        result = compute(json.loads(path.read_text()))
        print(json.dumps(serial(result), indent=2, allow_nan=False))
    except (KeyError, TypeError, ValueError, ZeroDivisionError) as exc:
        print('Invalid model input: ' + str(exc), file=sys.stderr)
        raise SystemExit(2)
