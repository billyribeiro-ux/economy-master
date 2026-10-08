"""Small exact mean-variance teaching fixture. Quiet import and run(inputs).

This is a three-asset frontier/face enumeration and a separate two-asset
forecast-perturbation audit, not an empirical estimator or a general optimizer.
"""
import argparse
from fractions import Fraction as F
from itertools import combinations, product
import json
from math import sqrt
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONVENTIONS = {
    'horizon': 'one_year', 'return': 'simple_total_decimal', 'currency': 'CU',
    'trading': 'date_0_buy_and_hold', 'taxes': 'none', 'fees': 'none',
    'analytic_rights': 'shorting_and_equal_rate_borrowing_allowed',
    'constrained_rights': 'three_risky_assets_long_only_no_cash',
    'sign_probability': '1/2',
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def number(value):
    require(type(value) in (str, int), 'Numbers must be rational strings or integers, not floats/bools.')
    try:
        return F(value)
    except (ValueError, ZeroDivisionError) as exc:
        raise ValueError('Invalid finite rational input.') from exc


def vector(value, size):
    require(isinstance(value, list) and len(value) == size, 'Unexpected vector dimension.')
    return [number(x) for x in value]


def matrix(value, rows, columns):
    require(isinstance(value, list) and len(value) == rows, 'Unexpected matrix dimension.')
    return [vector(row, columns) for row in value]


def dot(a, b):
    return sum((x*y for x, y in zip(a, b)), F(0))


def mv(a, x):
    return [dot(row, x) for row in a]


def solve(a, b):
    """Exact elimination; tiny dimensions are fixed by the input contract."""
    n = len(b)
    table = [list(row)+[rhs] for row, rhs in zip(a, b)]
    for col in range(n):
        pivot = next((row for row in range(col, n) if table[row][col]), None)
        require(pivot is not None, 'Singular linear system; do not silently use inverse formulas.')
        table[col], table[pivot] = table[pivot], table[col]
        factor = table[col][col]
        table[col] = [x/factor for x in table[col]]
        for row in range(n):
            if row != col:
                factor = table[row][col]
                table[row] = [x-factor*y for x, y in zip(table[row], table[col])]
    return [row[-1] for row in table]


def positive_definite(a):
    """Exact LDL diagonal pivots certify SPD without square-root rounding."""
    n = len(a)
    require(all(a[i][j] == a[j][i] for i in range(n) for j in range(n)), 'Covariance must be symmetric.')
    lower = [[F(i == j) for j in range(n)] for i in range(n)]
    diagonal = []
    for j in range(n):
        pivot = a[j][j]-sum(lower[j][k]**2*diagonal[k] for k in range(j))
        require(pivot > 0, 'SPD required: remove true redundancy or specify an estimation model.')
        diagonal.append(pivot)
        for i in range(j+1, n):
            lower[i][j] = (a[i][j]-sum(lower[i][k]*lower[j][k]*diagonal[k]
                                     for k in range(j)))/pivot
    return diagonal


def population(means, loadings):
    """Enumerate independent equiprobable signs; these are physical moments."""
    states = [tuple(means[i]+dot(loadings[i], z) for i in range(len(means)))
              for z in product((-1, 1), repeat=len(loadings[0]))]
    require(all(value > -1 for state in states for value in state),
            'Named finite-state individual asset returns must exceed -1.')
    probability = F(1, len(states))
    average = [sum(state[i] for state in states)*probability for i in range(len(means))]
    covariance = [[sum((state[i]-average[i])*(state[j]-average[j]) for state in states)*probability
                   for j in range(len(means))] for i in range(len(means))]
    return average, covariance, len(states)


def moments(weights, means, covariance):
    variance = dot(weights, mv(covariance, weights))
    require(variance >= 0, 'A reported variance cannot be negative.')
    return {'weights': weights, 'mean': dot(weights, means), 'variance': variance,
            'volatility_approx': sqrt(float(variance))}


def coefficients(means, covariance):
    one = [F(1)]*len(means)
    a, b = solve(covariance, one), solve(covariance, means)
    aa, bb, cc = sum(a), sum(b), dot(means, b)
    return a, b, aa, bb, cc, aa*cc-bb*bb


def target_weights(means, covariance, target):
    a, b, aa, bb, cc, delta = coefficients(means, covariance)
    if not delta:
        require(all(mu == target for mu in means), 'Target infeasible with identical means.')
        return [x/aa for x in a]
    require(delta > 0, 'Target equalities require positive frontier determinant.')
    lam, eta = (cc-bb*target)/delta, (aa*target-bb)/delta
    return [lam*x+eta*y for x, y in zip(a, b)]


def long_only(means, covariance, target):
    candidates = []
    for size in (1, 2, 3):
        for active in combinations(range(3), size):
            m = [means[i] for i in active]
            if not min(m) <= target <= max(m):
                continue
            sub = [[covariance[i][j] for j in active] for i in active]
            weights = target_weights(m, sub, target)
            if min(weights) < 0:
                continue
            full = [F(0)]*3
            for i, value in zip(active, weights):
                full[i] = value
            report = moments(full, means, covariance)
            report['candidate_face'] = [i+1 for i in active]
            candidates.append(report)
    if not candidates:
        return {'status': 'infeasible', 'target': target,
                'feasible_mean_interval': [min(means), max(means)],
                'faces_enumerated': 7, 'feasible_face_candidates': []}
    selected = min(candidates, key=lambda row: row['variance'])
    return {'status': 'optimal', 'target': target, 'selected': selected,
            'faces_enumerated': 7, 'feasible_face_candidates': candidates}


def cash_allocation(means, covariance, risk_free, gamma):
    premium = [mu-risk_free for mu in means]
    direction = solve(covariance, premium)
    normalizer = sum(direction)
    exposures = [x/gamma for x in direction]
    variance = dot(exposures, mv(covariance, exposures))
    value = {'risky_direction': direction, 'normalizer': normalizer,
             'risky_exposures': exposures, 'safe_weight': 1-sum(exposures),
             'mean': risk_free+dot(premium, exposures), 'variance': variance,
             'volatility_approx': sqrt(float(variance)),
             'objective': risk_free+dot(premium, exposures)-gamma*variance/2,
             'tangency_fund': None}
    if not any(premium):
        value['normalization_status'] = 'all_safe_optimum'
    elif normalizer > 0:
        weights = [x/normalizer for x in direction]
        fund = moments(weights, means, covariance)
        fund['premium'] = dot(weights, premium)
        fund['sharpe_squared'] = fund['premium']**2/fund['variance']
        fund['sharpe_approx'] = float(fund['premium'])/fund['volatility_approx']
        value['tangency_fund'] = fund
        value['normalization_status'] = 'positive_premium_risky_fund'
    elif normalizer == 0:
        value['normalization_status'] = 'zero_net_risky_direction_no_fund_normalization'
    else:
        value['normalization_status'] = 'negative_normalizer_no_positive_premium_fund_claim'
    return value


def budget_utility(means, covariance, gamma):
    """Fully invested risky utility, different from free cash/risky allocation."""
    a = solve(covariance, [F(1)]*len(means))
    b = solve(covariance, means)
    budget_multiplier = (sum(b)-gamma)/sum(a)
    return [(y-budget_multiplier*x)/gamma for x, y in zip(a, b)]


def serialize(value):
    if isinstance(value, F):
        return str(value)
    if isinstance(value, dict):
        return {k: serialize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [serialize(x) for x in value]
    return value


def run(inputs=None):
    if inputs is None:
        inputs = json.loads((HERE/'v09-c03-inputs.json').read_text(encoding='utf-8'))
    require(isinstance(inputs, dict) and inputs.get('case_id') == 'v09-c03-allocation-1',
            'This script supports only the named allocation fixture.')
    require(inputs.get('conventions') == CONVENTIONS,
            'Contradictory horizon, return, funding, fee, tax or constraint label.')
    main, shrink = inputs['main'], inputs['shrinkage']
    require(main['asset_labels'] == ['A', 'B', 'C'] and shrink['asset_labels'] == ['D', 'E'],
            'Fixed three-asset and two-asset identities are required.')
    means, covariance, state_count = population(vector(main['means'], 3),
                                              matrix(main['factor_loadings'], 3, 4))
    pivots = positive_definite(covariance)
    gamma, risk_free = number(main['gamma']), number(main['risk_free'])
    require(gamma > 0 and risk_free > -1, 'Positive gamma and positive safe gross return required.')
    targets = [number(x) for x in main['targets']]
    a, b, aa, bb, cc, delta = coefficients(means, covariance)
    gmv = moments([x/aa for x in a], means, covariance)
    frontier = []
    for target in targets:
        report = moments(target_weights(means, covariance, target), means, covariance)
        report['target'] = target
        report['efficient_branch'] = target >= gmv['mean']
        frontier.append(report)

    require(shrink['covariance_target'] == 'trace_mean_times_identity' and
            shrink['mean_target'] == 'cross_section_mean' and
            shrink['evaluation'] == 'disclosed_synthetic_population_no_fit_selection',
            'Unsupported shrinkage or evaluation policy label.')
    base = vector(shrink['base_means'], 2)
    perturbed = vector(shrink['perturbed_means'], 2)
    loadings = matrix(shrink['estimated_factor_loadings'], 2, 5)
    _, estimated, forecast_states = population(perturbed, loadings)
    population(base, loadings)
    positive_definite(estimated)
    audit_means, audit_covariance, audit_states = population(
        vector(shrink['audit_means'], 2), matrix(shrink['audit_factor_loadings'], 2, 6))
    positive_definite(audit_covariance)
    tau = sum(estimated[i][i] for i in range(2))/2
    target_covariance = [[tau if i == j else F(0) for j in range(2)] for i in range(2)]
    expected_ids = ['baseline_raw', 'perturbed_raw', 'covariance_shrunk', 'covariance_and_mean_shrunk']
    require([r['id'] for r in shrink['rules']] == expected_ids,
            'Keep all four declared forecast comparison policies in order.')
    shrink_rows = []
    for rule in shrink['rules']:
        alpha, kappa = number(rule['alpha']), number(rule['kappa'])
        require(0 <= alpha <= 1 and 0 <= kappa <= 1, 'Shrinkage intensities must lie in [0,1].')
        expected_mean = 'base' if rule['id'] == 'baseline_raw' else 'perturbed'
        require(rule['mean_set'] == expected_mean, 'Policy label conflicts with selected forecast means.')
        if rule['id'].endswith('_raw'):
            require(alpha == kappa == 0, 'Raw policy cannot secretly shrink inputs.')
        elif rule['id'] == 'covariance_shrunk':
            require(alpha > 0 and kappa == 0, 'Covariance-only policy requires positive alpha and zero kappa.')
        else:
            require(alpha > 0 and kappa > 0, 'Joint-shrinkage policy requires both intensities positive.')
        supplied_means = base if expected_mean == 'base' else perturbed
        center = sum(supplied_means)/2
        used_means = [(1-kappa)*x+kappa*center for x in supplied_means]
        used_covariance = [[(1-alpha)*estimated[i][j]+alpha*target_covariance[i][j]
                            for j in range(2)] for i in range(2)]
        positive_definite(used_covariance)
        weights = budget_utility(used_means, used_covariance, gamma)
        fit = moments(weights, used_means, used_covariance)
        audit = moments(weights, audit_means, audit_covariance)
        fit['objective'] = fit['mean']-gamma*fit['variance']/2
        audit['objective'] = audit['mean']-gamma*audit['variance']/2
        shrink_rows.append({'policy': rule['id'], 'alpha': alpha, 'kappa': kappa,
                            'used_means': used_means, 'used_covariance': used_covariance,
                            'fit_moments': fit, 'common_audit_moments': audit})

    result = serialize({
        'case_id': inputs['case_id'], 'status': 'calculated',
        'units': 'one-year decimal simple returns; variance is decimal-return squared',
        'main': {'physical_states': state_count, 'probability_per_state': F(1, state_count),
                 'means': means, 'covariance': covariance, 'LDL_pivots': pivots,
                 'frontier_constants': {'A': aa, 'B': bb, 'C': cc, 'Delta': delta},
                 'GMV': gmv, 'target_frontier': frontier,
                 'safe_and_risky_allocation': cash_allocation(means, covariance, risk_free, gamma),
                 'long_only': long_only(means, covariance, number(main['long_only_target']))},
        'shrinkage': {'forecast_physical_states': forecast_states,
                      'audit_physical_states': audit_states,
                      'estimated_covariance': estimated, 'target_covariance': target_covariance,
                      'audit_means': audit_means, 'audit_covariance': audit_covariance,
                      'rules': shrink_rows},
        'limits': ['Population scenarios and parameter perturbations are invented, not observed samples.',
                   'Fixed shrinkage intensities are not estimated optimal coefficients or universal prescriptions.',
                   'No empirical backtest, costs, taxes, unequal funding rates or dynamic strategy is modeled.',
                   'Exact rational moments/weights; only explicitly named approximate square roots use floats.'],
    })
    json.dumps(result, allow_nan=False)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=HERE/'v09-c03-inputs.json')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    data = json.loads(args.input.read_text(encoding='utf-8'))
    rendered = json.dumps(run(data), ensure_ascii=False, indent=2, allow_nan=False)+'\n'
    if args.output:
        args.output.write_text(rendered, encoding='utf-8')
    else:
        print(rendered, end='')


if __name__ == '__main__':
    main()
