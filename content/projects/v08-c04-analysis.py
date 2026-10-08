#!/usr/bin/env python3
"""Original finite cost-of-capital lab; standard library only, no network."""
from fractions import Fraction
import json
from pathlib import Path
import sys


def q(value):
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ValueError('Exact inputs must be integer or rational/decimal strings')
    return Fraction(value)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def pv(cash, rate):
    require(rate > -1, 'Discount rate must exceed -100%')
    return sum((x / (1 + rate) ** t for t, x in enumerate(cash, 1)), Fraction(0))


def moments(prob, x, y):
    require(len(prob) == len(x) == len(y) and bool(prob), 'State lengths must match')
    require(all(p > 0 for p in prob) and sum(prob) == 1, 'Positive probabilities must sum to one')
    mx = sum(p * a for p, a in zip(prob, x))
    my = sum(p * b for p, b in zip(prob, y))
    vx = sum(p * (a - mx) ** 2 for p, a in zip(prob, x))
    vy = sum(p * (b - my) ** 2 for p, b in zip(prob, y))
    cov = sum(p * (a - mx) * (b - my) for p, a, b in zip(prob, x, y))
    require(vx > 0, 'Market variance must be positive')
    return dict(market_mean=mx, claim_mean=my, market_variance=vx,
                claim_variance=vy, covariance=cov, beta=cov / vx)


def compute(data):
    p = data['moment_case']
    probabilities = list(map(q, p['probabilities']))
    market = list(map(q, p['market_shocks']))
    residual = list(map(q, p['residual_shocks']))
    require(len(market) == len(residual), 'Residual and market state lengths must match')
    moment_results = {}
    for claim in ('x', 'z'):
        loading = q(p[claim + '_market_loading'])
        noise = q(p[claim + '_residual_loading'])
        shocks = [loading * m + noise * e for m, e in zip(market, residual)]
        row = moments(probabilities, market, shocks)
        row['required_return'] = q(p['risk_free']) + row['beta'] * q(p['equity_premium'])
        row['centered_claim_shocks'] = shocks
        moment_results[claim] = row
    require(moment_results['x']['market_mean'] == 0, 'These input market shocks must be centered')
    require(sum(a * b for a, b in zip(probabilities, residual)) == 0,
            'These input residual shocks must be centered')

    p = data['one_period']
    equity, debt = q(p['market_equity']), q(p['market_debt'])
    be, bd = q(p['book_equity']), q(p['book_debt'])
    rf, rd, premium = q(p['risk_free']), q(p['debt_return']), q(p['equity_premium'])
    beta, tax, cash = q(p['equity_beta']), q(p['current_tax_rate']), q(p['expected_unlevered_cash'])
    require(equity > 0 and debt >= 0 and be > 0 and bd >= 0, 'Positive equity and nonnegative debt required')
    require(rf >= 0 and rd == rf, 'This one-period contract requires nonnegative risk-free par debt pricing')
    require(0 <= tax < 1 and p['fully_usable_current_deduction'] is True,
            'One-period deduction must be fully usable currently at a rate in [0,1)')
    value = equity + debt
    re = rf + beta * premium
    wacc = (equity * re + debt * rd * (1 - tax)) / value
    require(1 + re > 0 and 1 + wacc > 0, 'Positive expected gross returns required')
    shield_cash = tax * rd * debt
    creditor_cash = debt * (1 + rd)
    equity_cash = equity * (1 + re)
    require(cash + shield_cash == creditor_cash + equity_cash,
            'Supplied one-period cash and market claims do not close at required returns')
    states = [equity * (1 + re + beta * m) + creditor_cash - shield_cash for m in market]
    require(all(x + shield_cash >= creditor_cash for x in states), 'State cash fails the promised risk-free debt payment')
    shield_value = shield_cash / (1 + rf)
    unlevered_value = value - shield_value
    require(unlevered_value > 0, 'Positive unlevered value required')
    unlevered_beta = beta * equity / unlevered_value
    unlevered_return = rf + unlevered_beta * premium
    book_wacc = (be * re + bd * rd * (1 - tax)) / (be + bd)
    one_period = dict(equity_return=re, debt_return=rd, wacc=wacc,
                      operating_value=cash / (1 + wacc), expected_operating_cash=cash,
                      expected_equity_cash=equity_cash, debt_cash=creditor_cash,
                      shield_cash=shield_cash, state_operating_cash=states,
                      book_weight_wacc=book_wacc, wrong_book_weight_value=cash / (1 + book_wacc),
                      shield_value=shield_value, unlevered_value=unlevered_value,
                      unlevered_beta=unlevered_beta, unlevered_return=unlevered_return,
                      apv_value=cash / (1 + unlevered_return) + shield_value)

    p = data['no_tax_comparable']
    e, d = q(p['peer_equity']), q(p['peer_debt'])
    fraction = q(p['target_debt_fraction'])
    require(e > 0 and d >= 0 and 0 <= fraction < 1, 'Invalid comparable market weights')
    bu = (e * q(p['peer_equity_beta']) + d * q(p['peer_debt_beta'])) / (e + d)
    beta_d = q(p['target_debt_beta'])
    beta_e = (bu - fraction * beta_d) / (1 - fraction)
    rf, erp = q(p['risk_free']), q(p['equity_premium'])
    re, rd, ru = rf + beta_e * erp, rf + beta_d * erp, rf + bu * erp
    comparable = dict(operating_beta=bu, target_equity_beta=beta_e,
                      debt_to_equity=fraction / (1 - fraction), equity_return=re,
                      debt_return=rd, unlevered_return=ru,
                      no_tax_wacc=(1 - fraction) * re + fraction * rd)

    p = data['finite_apv']
    cash = list(map(q, p['expected_unlevered_cash']))
    balances = list(map(q, p['debt_balances']))
    initial, ru, rf, tax = map(q, (p['initial_investment'], p['unlevered_return'], p['risk_free'], p['tax_rate']))
    require(len(cash) > 0 and len(balances) == len(cash) + 1, 'APV cash and debt schedule horizons differ')
    require(initial > 0 and 0 <= balances[0] <= initial, 'Investment and initial funding shares invalid')
    require(balances[-1] == 0 and all(a >= b >= 0 for a, b in zip(balances, balances[1:])),
            'This finite loan must amortize monotonically to zero')
    require(rf >= 0 and ru > -1 and 0 <= tax < 1, 'Invalid APV rates')
    interest = [rf * x for x in balances[:-1]]
    principal = [a - b for a, b in zip(balances, balances[1:])]
    credits = [tax * x for x in interest]
    policy = p['tax_use']
    require(policy in ('current', 'deferred_to_final', 'none'), 'Unknown tax-use policy')
    shields = credits if policy == 'current' else [Fraction(0)] * len(cash)
    if policy == 'deferred_to_final':
        shields[-1] = sum(credits)
    vu, s = pv(cash, ru), pv(shields, rf)
    service = [i + principal_t for i, principal_t in zip(interest, principal)]
    apv = dict(tax_use=policy, unlevered_value=vu, interest=interest,
               principal_repayment=principal, debt_service=service, debt_service_value=pv(service, rf),
               accrued_tax_credits=credits, paid_tax_shields=shields, shield_value=s,
               levered_value=vu + s, apv_npv=vu + s - initial,
               equity_value=vu + s - balances[0], equity_initial_contribution=initial - balances[0])
    return dict(moment_case=moment_results, one_period=one_period,
                no_tax_comparable=comparable, finite_apv=apv)


def serializable(value):
    if isinstance(value, Fraction):
        return float(value)
    if isinstance(value, dict):
        return {k: serializable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [serializable(x) for x in value]
    return value


def main():
    require(len(sys.argv) <= 2, 'Usage: python3 v08-c04-analysis.py [inputs.json]')
    path = Path(sys.argv[1]) if len(sys.argv) == 2 else Path(__file__).with_name('v08-c04-inputs.json')
    print(json.dumps(serializable(compute(json.loads(path.read_text()))), indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
