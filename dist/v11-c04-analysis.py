"""Finite physical loss risk: exact atoms/dual certificates; qualified diagnostics.

Original synthetic teaching model. Standard library only. No market forecast,
regulatory capital calculation, trading recommendation or loss guarantee.
"""
from fractions import Fraction as F
from pathlib import Path
from statistics import NormalDist
import argparse
import json
import math
import re
import sys

DECIMAL = re.compile(r'-?(?:0|[1-9][0-9]{0,9})(?:\.[0-9]{1,10})?\Z')
IDENTIFIER = re.compile(r'[A-Za-z][A-Za-z0-9_]{0,39}\Z')


def need(condition, message):
    if not condition:
        raise ValueError(message)


def shape(value, keys, label):
    need(type(value) is dict and set(value) == set(keys), label + ': exact fields required')


def number(value, label, low=None, high=None):
    need(type(value) is str and DECIMAL.fullmatch(value) is not None,
         label + ': bounded decimal string required')
    result = F(value)
    need(low is None or result >= low, label + ': below domain')
    need(high is None or result <= high, label + ': above domain')
    return result


def integer(value, low, high, label):
    need(type(value) is int and low <= value <= high, label + ': bounded integer required')
    return value


def identifier(value, label):
    need(type(value) is str and IDENTIFIER.fullmatch(value) is not None, label + ': invalid identifier')
    return value


def confidence(value, label):
    result = number(value, label)
    need(0 < result < 1, label + ': require 0 < confidence < 1')
    return result


def validate(data):
    shape(data, ('schema', 'provenance', 'units', 'cases', 'horizon', 'backtest'), 'input')
    need(type(data['schema']) is int and data['schema'] == 1, 'schema must be integer1')
    for key in ('provenance', 'units'):
        need(type(data[key]) is str and 1 <= len(data[key]) <= 1000, key + ': descriptive string required')
    cases = data['cases']
    need(type(cases) is list and 1 <= len(cases) <= 8, 'require1–8 finite cases')
    case_ids = []
    for case in cases:
        shape(case, ('id', 'confidence', 'assets', 'holdings', 'states'), 'case')
        case_ids.append(identifier(case['id'], 'case ID'))
        confidence(case['confidence'], 'case confidence')
        assets = case['assets']
        need(type(assets) is list and 1 <= len(assets) <= 8, 'require1–8 assets')
        for asset in assets:
            identifier(asset, 'asset ID')
        need(len(set(assets)) == len(assets), 'duplicate asset ID')
        need(type(case['holdings']) is list and len(case['holdings']) == len(assets), 'holdings dimension')
        for value in case['holdings']:
            number(value, 'holding', -10, 10)
        states = case['states']
        need(type(states) is list and 1 <= len(states) <= 64, 'require1–64 states')
        state_ids, probabilities = [], []
        for state in states:
            shape(state, ('id', 'probability', 'losses'), 'state')
            state_ids.append(identifier(state['id'], 'state ID'))
            p = number(state['probability'], 'state probability', 0, 1)
            need(p > 0, 'omit zero-probability states')
            probabilities.append(p)
            need(type(state['losses']) is list and len(state['losses']) == len(assets), 'loss dimension')
            for value in state['losses']:
                number(value, 'loss', -1000000, 1000000)
        need(len(set(state_ids)) == len(state_ids), 'duplicate state ID')
        need(sum(probabilities) == 1, 'state probabilities must sum exactly to1')
    need(len(set(case_ids)) == len(case_ids), 'duplicate case ID')
    h = data['horizon']
    shape(h, ('days', 'daily_mean_loss', 'daily_sd_loss', 'lag_correlation', 'confidence'), 'horizon')
    integer(h['days'], 1, 250, 'days')
    number(h['daily_mean_loss'], 'daily mean loss', -1000000, 1000000)
    number(h['daily_sd_loss'], 'daily SD', 0, 1000000)
    rho = number(h['lag_correlation'], 'correlation')
    need(-1 < rho < 1, 'require stationary AR1 correlation in(-1,1)')
    a = confidence(h['confidence'], 'horizon confidence')
    need(F('0.5') <= a <= F('0.9999'), 'normal diagnostic confidence range[.5,.9999]')
    b = data['backtest']
    shape(b, ('trials', 'exception_probability', 'exception_positions'), 'backtest')
    n = integer(b['trials'], 1, 500, 'trials')
    confidence(b['exception_probability'], 'null exception probability')
    positions = b['exception_positions']
    need(type(positions) is list and len(positions) <= n, 'exception positions list')
    for pos in positions:
        integer(pos, 1, n, 'exception position')
    need(positions == sorted(set(positions)), 'exception positions must be unique and ascending')


def finite_risk(losses, probabilities, alpha, ids):
    """Internal routine; arguments come only from validate() and exact arithmetic."""
    order = sorted(range(len(losses)), key=lambda i: losses[i])
    cumulative, quantile = F(0), None
    for i in order:
        cumulative += probabilities[i]
        if cumulative >= alpha:
            quantile = losses[i]
            break
    tail = 1 - alpha
    remaining = tail
    masses = [F(0)] * len(losses)
    for i in reversed(order):
        masses[i] = min(probabilities[i], remaining)
        remaining -= masses[i]
        if remaining == 0:
            break
    es = sum(mass * loss for mass, loss in zip(masses, losses)) / tail
    mean = sum(p * loss for p, loss in zip(probabilities, losses))
    strict = sum(p for p, loss in zip(probabilities, losses) if loss > quantile)
    weak = sum(p for p, loss in zip(probabilities, losses) if loss >= quantile)
    excess = sum(p * max(loss - quantile, 0) for p, loss in zip(probabilities, losses))
    return {
        'var': str(quantile), 'es': str(es), 'mean': str(mean),
        'variance': str(sum(p * (loss - mean)**2 for p, loss in zip(probabilities, losses))),
        'strict_exceedance_probability': str(strict),
        'strict_tail_mean': None if strict == 0 else str(sum(p * loss for p, loss in zip(probabilities, losses) if loss > quantile) / strict),
        'weak_tail_mean': str(sum(p * loss for p, loss in zip(probabilities, losses) if loss >= quantile) / weak),
        'positive_part_objective_at_var': str(quantile + excess / tail),
        'tail_allocation': [{'state': name, 'loss': str(loss), 'available_probability': str(p),
                             'selected_probability': str(mass), 'dual_weight': str(mass / tail),
                             'es_contribution': str(mass * loss / tail)}
                            for name, loss, p, mass in zip(ids, losses, probabilities, masses)],
        'tie_rule': 'One exact optimizer; equal-loss states are filled in reverse input order. ES and VaR are invariant to that choice.'
    }


def run(data):
    """Quiet, nonmutating API returning a JSON-safe result; validate before work."""
    validate(data)
    output = {'schema': 1, 'units': data['units'], 'cases': []}
    for case in data['cases']:
        alpha = F(case['confidence'])
        weights = list(map(F, case['holdings']))
        probabilities = [F(state['probability']) for state in case['states']]
        matrix = [list(map(F, state['losses'])) for state in case['states']]
        ids = [state['id'] for state in case['states']]
        portfolio = [sum(w * loss for w, loss in zip(weights, row)) for row in matrix]
        components = {name: finite_risk([w * row[j] for row in matrix], probabilities, alpha, ids)
                      for j, (name, w) in enumerate(zip(case['assets'], weights))}
        risk = finite_risk(portfolio, probabilities, alpha, ids)
        output['cases'].append({'id': case['id'], 'confidence': str(alpha), 'portfolio': risk,
                                'held_components': components,
                                'sum_component_var': str(sum(F(x['var']) for x in components.values())),
                                'sum_component_es': str(sum(F(x['es']) for x in components.values()))})
    h = data['horizon']
    days, rho = h['days'], F(h['lag_correlation'])
    variance_factor = days + 2 * sum((days - k) * rho**k for k in range(1, days))
    variance = F(h['daily_sd_loss'])**2 * variance_factor
    mean = days * F(h['daily_mean_loss'])
    alpha = float(F(h['confidence']))
    z = NormalDist().inv_cdf(alpha)
    sd = math.sqrt(float(variance))
    output['horizon'] = {'mean': str(mean), 'variance': str(variance),
                         'variance_factor': str(variance_factor), 'sd_approx': sd,
                         'iid_variance': str(days * F(h['daily_sd_loss'])**2),
                         'normal_var_approx': float(mean) + sd * z,
                         'normal_es_approx': float(mean) + sd * math.exp(-z*z/2) / math.sqrt(2*math.pi) / (1-alpha),
                         'scope': 'Additive stationary daily losses with covariances SD^2*rho^lag; normal VaR/ES additionally assume joint normality. No fitted law or nonlinear revaluation is supplied.'}
    b = data['backtest']
    n, p = b['trials'], F(b['exception_probability'])
    positions = b['exception_positions']
    k = len(positions)
    probability = sum(F(math.comb(n, j)) * p**j * (1-p)**(n-j) for j in range(k, n+1))
    longest = current = 0
    observed = set(positions)
    for day in range(1, n+1):
        current = current + 1 if day in observed else 0
        longest = max(longest, current)
    output['backtest'] = {'trials': n, 'exceptions': k, 'expected_exceptions': str(n*p),
                          'one_sided_count_probability_approx': float(probability),
                          'longest_exception_run': longest,
                          'adjacent_exception_pairs': sum(pos+1 in observed for pos in observed),
                          'scope': 'Exact binomial null tail converted to float: fixed independent Bernoulli trials with the stated probability. Run/pair counts are descriptive; no independence or severity test is claimed.'}
    output['limits'] = ['Finite supplied physical scenarios only; no claim of complete support, empirical calibration, market prices or worst-case protection.',
                        'Finite risk strings are exact fractions. Normal and binomial diagnostics are explicitly labeled floating approximations.',
                        'An ES tail is a worst-case reweighting within a specified envelope, not a new physical forecast or evidence that omitted states cannot occur.']
    return output


def pairs_hook(pairs):
    result = {}
    for key, value in pairs:
        need(key not in result, 'duplicate JSON key: ' + key)
        result[key] = value
    return result


def invalid_constant(value):
    raise ValueError('nonfinite JSON constant: ' + value)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=Path(__file__).with_name('v11-c04-inputs.json'))
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    try:
        if args.output is not None:
            protected = {args.input.resolve(), Path(__file__).resolve()}
            same_file = args.output.exists() and any(args.output.samefile(path) for path in protected if path.exists())
            need(args.output.resolve() not in protected and not same_file, 'output cannot replace input or implementation')
        data = json.loads(args.input.read_text(encoding='utf-8'), object_pairs_hook=pairs_hook,
                          parse_constant=invalid_constant)
        result = run(data)
        payload = json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + '\n'
        if args.output is None:
            sys.stdout.write(payload)
        else:
            args.output.write_text(payload, encoding='utf-8')
    except (ValueError, TypeError, OSError, OverflowError) as error:
        print('Input/output error: ' + str(error), file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
