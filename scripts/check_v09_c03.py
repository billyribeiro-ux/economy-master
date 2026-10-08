"""Exact independent portfolio certificates and fixture/HTML boundaries.

Quiet check() returns strict JSON. Primary-source scope and complete instruction
review are recorded separately; these checks are not empirical validation.
"""
from collections import Counter
from contextlib import redirect_stdout
from copy import deepcopy
from fractions import Fraction as F
import hashlib
from html.parser import HTMLParser
import importlib.util
from io import StringIO
from itertools import product
import json
from math import exp, isclose, sqrt
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT/'content/projects'


def require(condition, label):
    if not condition:
        raise AssertionError(label)


def dot(a, b):
    return sum((x*y for x, y in zip(a, b)), F(0))


def variance(w, s):
    return sum(w[i]*s[i][j]*w[j] for i in range(len(w)) for j in range(len(w)))


def numbers(xs):
    return [F(x) for x in xs]


def load_lab():
    path = PROJECT/'v09-c03-analysis.py'
    spec = importlib.util.spec_from_file_location('v09_c03_lab_checked', path)
    module = importlib.util.module_from_spec(spec)
    capture = StringIO()
    with redirect_stdout(capture):
        spec.loader.exec_module(module)
    require(not capture.getvalue(), 'Lab import must be quiet')
    return module


def run_quiet(lab, data):
    capture = StringIO()
    with redirect_stdout(capture):
        result = lab.run(data)
    require(not capture.getvalue(), 'Lab run must be quiet')
    json.dumps(result, allow_nan=False)
    return result


def covariance_from_loadings(raw):
    loadings = [numbers(row) for row in raw]
    return [[dot(a, b) for b in loadings] for a in loadings]


def state_portfolio(weights, cash, rf, means, loadings):
    # Project factor exposures first, then enumerate a scalar portfolio law.
    # This reverses the lab's asset-state covariance-first calculation.
    factor_weights = [sum(weights[i]*loadings[i][j] for i in range(len(weights)))
                      for j in range(len(loadings[0]))]
    predicted = dot(weights, means)+cash*rf
    returns = [predicted+dot(factor_weights, signs)
               for signs in product((-1, 1), repeat=len(factor_weights))]
    mean = sum(returns)/len(returns)
    var = sum((r-mean)**2 for r in returns)/len(returns)
    return mean, var


def main_law_check(data, out):
    mu = numbers(data['main']['means'])
    loading = [numbers(row) for row in data['main']['factor_loadings']]
    sigma = covariance_from_loadings(data['main']['factor_loadings'])
    expected = [[F(x, 100) for x in row] for row in ((2, 1, 1), (1, 5, 1), (1, 1, 10))]
    require(sigma == expected and [[F(x) for x in row] for row in out['main']['covariance']] == sigma,
            'Main covariance must match independent loading Gram')
    # Sylvester's criterion checks SPD independently of the lab's LDL routine.
    minor2 = sigma[0][0]*sigma[1][1]-sigma[0][1]**2
    determinant = (sigma[0][0]*(sigma[1][1]*sigma[2][2]-sigma[1][2]*sigma[2][1])
                   -sigma[0][1]*(sigma[1][0]*sigma[2][2]-sigma[1][2]*sigma[2][0])
                   +sigma[0][2]*(sigma[1][0]*sigma[2][1]-sigma[1][1]*sigma[2][0]))
    require(sigma[0][0] > 0 and minor2 > 0 and determinant > 0,
            'Main covariance positive principal minors')
    reports = [out['main']['GMV']]+out['main']['target_frontier']
    for report in reports:
        w = numbers(report['weights'])
        state_mean, state_var = state_portfolio(w, F(0), F(0), mu, loading)
        require(sum(w) == 1 and state_mean == F(report['mean']) and
                state_var == F(report['variance']), 'Main projected scalar-state moments')
        require(isclose(report['volatility_approx'], sqrt(float(state_var)), rel_tol=1e-12, abs_tol=1e-12),
                'Volatility display approximation')
    require(out['main']['physical_states'] == 16 and F(out['main']['probability_per_state']) == F(1, 16),
            'Main physical rather than sample moment law')
    return mu, sigma


def frontier_check(mu, sigma, out):
    g = numbers(out['main']['GMV']['weights'])
    require(g == [F(36, 49), F(9, 49), F(4, 49)] and
            dot(mu, g) == F(66, 1225) and variance(g, sigma) == F(17, 980), 'GMV anchors')
    require(all(dot(row, g) == F(17, 980) for row in sigma), 'GMV full stationarity certificate')
    expected = [(F(2, 25), [F(4, 13), F(5, 13), F(4, 13)], F(1, 1300), F(4, 13), F(33, 1300)),
                (F(1, 10), [F(-1, 52), F(7, 13), F(25, 52)], F(-31, 2600), F(113, 208), F(441, 10400))]
    for report, (target, w, lam, eta, v) in zip(out['main']['target_frontier'], expected):
        require(numbers(report['weights']) == w and sum(w) == 1 and dot(mu, w) == target,
                'Target budget and mean certificate')
        require(all(dot(row, w) == lam+eta*m for row, m in zip(sigma, mu)) and
                variance(w, sigma) == lam+eta*target == v, 'Target dual stationary variance')
        # z=(1,-2,1) preserves both equalities for these equally spaced means.
        for scale in (F(-3), F(-1, 3), F(1, 7), F(2)):
            z = [scale, -2*scale, scale]
            alternative = [x+y for x, y in zip(w, z)]
            require(variance(alternative, sigma)-v == variance(z, sigma) > 0,
                    'Exact feasible-direction optimality gap')
    lower = [2*x-y for x, y in zip(g, expected[0][1])]
    require(lower == [F(740, 637), F(-11, 637), F(-92, 637)] and
            dot(mu, lower) == F(34, 1225) and variance(lower, sigma) == F(33, 1300),
            'Exercise 2 dominated reflected boundary')
    constants = {k: F(v) for k, v in out['main']['frontier_constants'].items()}
    require(constants == {'A': F(980, 17), 'B': F(264, 85), 'C': F(536, 2125), 'Delta': F(416, 85)},
            'Frontier determinant/nondegeneracy')
    return {'GMV_variance': '17/980', 'target_variances': ['33/1300', '441/10400'],
            'reflected_lower_target': '34/1225'}


def allocation_check(lab, data, mu, sigma, out):
    allocation = out['main']['safe_and_risky_allocation']
    x, cash = numbers(allocation['risky_exposures']), F(allocation['safe_weight'])
    rf, gamma = F(1, 50), F(4)
    q = [m-rf for m in mu]
    require(x == [F(1, 85), F(43, 170), F(19, 85)] and cash == F(87, 170) and sum(x)+cash == 1,
            'Risky versus total wealth budget')
    require(all(gamma*dot(row, x) == p for row, p in zip(sigma, q)), 'Demand first-order certificate')
    loading = [numbers(row) for row in data['main']['factor_loadings']]
    m, v = state_portfolio(x, cash, rf, mu, loading)
    require((m, v) == (F(491, 8500), F(321, 34000)) and
            (F(allocation['mean']), F(allocation['variance'])) == (m, v),
            'Total cash-inclusive state moments')
    optimum = m-gamma*v/2
    for delta in ([F(1), F(0), F(0)], [F(-1), F(2), F(-3)], [F(1, 3)]*3):
        y = [a+b for a, b in zip(x, delta)]
        utility = rf+dot(q, y)-gamma*variance(y, sigma)/2
        require(optimum-utility == gamma*variance(delta, sigma)/2 > 0,
                'Completed-square global allocation certificate')
    t = numbers(allocation['tangency_fund']['weights'])
    require(t == [F(2, 83), F(43, 83), F(38, 83)] and
            dot(t, q)**2/variance(t, sigma) == F(321, 2125), 'Positive tangency ray')
    for coefficient, mean, var, expected_cash in (
            (2, F(203, 2125), F(321, 8500), F(2, 85)),
            (1, F(727, 4250), F(321, 2125), F(-81, 85))):
        revised = deepcopy(data); revised['main']['gamma'] = str(coefficient)
        result = run_quiet(lab, revised)['main']['safe_and_risky_allocation']
        require((F(result['mean']), F(result['variance']), F(result['safe_weight'])) ==
                (mean, var, expected_cash), 'Exercise 3 gamma/funding sensitivity')
    for rate, status in ((F(66, 1225), 'zero_net_risky_direction_no_fund_normalization'),
                         (F(1, 10), 'negative_normalizer_no_positive_premium_fund_claim')):
        revised = deepcopy(data); revised['main']['risk_free'] = str(rate)
        result = run_quiet(lab, revised)['main']['safe_and_risky_allocation']
        require(result['normalization_status'] == status and result['tangency_fund'] is None,
                'Nonpositive normalizer must not be sold as positive tangency')
    neutral = deepcopy(data)
    neutral['main'].update(means=['1/50']*3, targets=['1/50'], long_only_target='1/50')
    result = run_quiet(lab, neutral)['main']['safe_and_risky_allocation']
    require(result['normalization_status'] == 'all_safe_optimum' and
            numbers(result['risky_exposures']) == [0, 0, 0] and F(result['safe_weight']) == 1,
            'Zero-premium and redundant target boundary')
    # Exercise 4 is a separate two-asset model, independently priced by moments.
    sign_cases = []
    for q2 in ([F(-1, 50)]*2, [F(1, 50), F(-1, 50)]):
        direction = [p/F(1, 25) for p in q2]
        holdings = [a/2 for a in direction]
        c = 1-sum(holdings)
        premium = dot(q2, holdings)
        var = F(1, 25)*dot(holdings, holdings)
        require(premium == F(1, 100) and var == F(1, 200), 'Exercise 4 sign-safe demand')
        sign_cases.append((sum(direction), c))
    require(sign_cases == [(-1, F(3, 2)), (0, 1)], 'Exercise 4 distinct normalization failures')
    return {'total_mean_gamma4': '491/8500', 'total_variance_gamma4': '321/34000',
            'normalization_boundaries': ['positive', 'zero', 'negative', 'zero_premium']}


def constraint_check(lab, data, mu, sigma, out):
    constrained = out['main']['long_only']
    w = numbers(constrained['selected']['weights'])
    require(w == [0, F(1, 2), F(1, 2)] and constrained['faces_enumerated'] == 7 and
            variance(w, sigma) == F(17, 400), 'Long-only exact result')
    # Independent scalar restriction: w=(t-.5,1.5-2t,t), .5<=t<=.75.
    t0 = F(1, 2)
    for t in (t0, F(3, 5), F(3, 4)):
        weights = [t-F(1, 2), F(3, 2)-2*t, t]
        polynomial = F(41, 400)-t/4+F(13, 50)*t*t
        derivative = -F(1, 4)+F(13, 25)*t
        require(min(weights) >= 0 and variance(weights, sigma) == polynomial and derivative > 0,
                'Long-only scalar convex boundary certificate')
    lam, eta, nu = -F(1, 50), F(5, 8), [F(1, 200), 0, 0]
    require(all(dot(row, w) == lam+eta*m+n for row, m, n in zip(sigma, mu, nu)) and
            dot(w, nu) == 0, 'Long-only KKT multipliers')
    require(F(17, 400)-F(441, 10400) == F(1, 10400) and
            dot(mu, [F(0), F(28, 53), F(25, 53)]) == F(131, 1325) < F(1, 10),
            'Constraint risk cost and clipping target failure')
    infeasible = deepcopy(data); infeasible['main']['long_only_target'] = '13/100'
    result = run_quiet(lab, infeasible)['main']['long_only']
    require(result['status'] == 'infeasible' and 'selected' not in result and
            not result['feasible_face_candidates'], 'No invented portfolio at infeasible target')
    cap_w = [F(1, 20), F(13, 20), F(3, 10)]
    cap_lam, cap_eta, cap_xi = -F(3, 200), F(51, 80), F(49, 2000)
    require(sum(cap_w) == 1 and dot(mu, cap_w) == F(9, 100) and
            variance(cap_w, sigma) == F(1401, 40000), 'Exercise 5 capped allocation')
    require(all(dot(row, cap_w)-cap_lam-cap_eta*m+(cap_xi if i == 2 else 0) == 0
                for i, (row, m) in enumerate(zip(sigma, mu))), 'Exercise 5 KKT certificate')
    require(dot(mu, [0, F(7, 10), F(3, 10)]) == F(23, 250), 'Exercise 5 feasible maximum mean')
    return {'long_only_variance': '17/400', 'clipped_mean': '131/1325',
            'capped_variance': '1401/40000', 'capped_max_mean': '23/250'}


def shrinkage_check(lab, data, out):
    expected = [[F(1, 2), F(1, 2)], [F(-1, 8), F(9, 8)],
                [F(197, 404), F(207, 404)], [F(399, 808), F(409, 808)]]
    audit_sigma = [[F(1, 25), F(1, 50)], [F(1, 50), F(1, 25)]]
    estimated = covariance_from_loadings(data['shrinkage']['estimated_factor_loadings'])
    require(estimated == [[F(1, 25), F(99, 2500)], [F(99, 2500), F(1, 25)]] and
            covariance_from_loadings(data['shrinkage']['audit_factor_loadings']) == audit_sigma,
            'Both separate two-asset laws coherent')
    results = []
    for row, weights in zip(out['shrinkage']['rules'], expected):
        mu = numbers(row['used_means']);s = [[F(x) for x in line] for line in row['used_covariance']]
        d = (mu[1]-mu[0])/(2*4*(s[0][0]-s[0][1]))
        require([F(1, 2)-d, F(1, 2)+d] == weights == numbers(row['fit_moments']['weights']),
                'Independent scalar utility optimum for each shrink rule')
        risk = F(3, 100)+F(1, 25)*d*d
        objective = F(2, 25)-2*risk
        require(variance(weights, audit_sigma) == risk == F(row['common_audit_moments']['variance'])
                and objective == F(row['common_audit_moments']['objective']),
                'All decisions evaluated under one audit law')
        results.append((risk, objective))
    require(results == [(F(3, 100), F(1, 50)), (F(73, 1600), -F(9, 800)),
                        (F(122437, 4080400), F(40779, 2040200)),
                        (F(489673, 16321600), F(163191, 8160800))], 'Audit table anchors')
    require(F('0.0796')/F('0.0004') == 199 and
            F('0.0598')/F('0.0202') == F(299, 101), 'Covariance eigenvalue conditioning')
    # Exercise 7: a different pair of intensities; preserve all named raw rules.
    revised = deepcopy(data)
    revised['shrinkage']['rules'][3]['alpha'] = '1/4'
    changed = run_quiet(lab, revised)['shrinkage']['rules'][3]
    require(numbers(changed['fit_moments']['weights']) == [F(201, 412), F(211, 412)] and
            F(changed['common_audit_moments']['variance']) == F(127333, 4243600) and
            F(changed['common_audit_moments']['objective']) == F(42411, 2121800),
            'Exercise 7 altered shrinkage')
    require(F('0.0697')/F('0.0103') == F(697, 103), 'Exercise 7 conditioning')
    # Alternative true population equals the original raw forecast. Compare
    # utilities directly against the completed-square certificate.
    raw_mu = [F(2, 25), F(41, 500)]
    def utility(d):
        weights = [F(1, 2)-d, F(1, 2)+d]
        return dot(weights, raw_mu)-2*variance(weights, estimated)
    optimum, alternative = F(5, 8), F(5, 412)
    require(utility(optimum)-utility(alternative) ==
            4*F('0.0004')*(alternative-optimum)**2 > 0,
            'Shrinkage is not universally better under the same preference')
    d = F(1, 160)
    require(F(3, 100)+F(1, 25)*d*d == F('0.0300015625') and
            F(2, 25)-2*(F(3, 100)+F(1, 25)*d*d) == F('0.019996875'),
            'Delayed complete-shrinkage reconstruction')
    return {'raw_condition_ratio': 199, 'half_shrunk_condition_ratio': '299/101',
            'audit_objectives': [str(row[1]) for row in results],
            'quarter_covariance_half_mean_weights': ['201/412', '211/412']}


def other_exercises_check():
    u = F(8, 11)
    v = F('.04')*u*u+2*F('.01')*u*(1-u)+F('.09')*(1-u)**2
    require(v == F(7, 220) and u*F('.06')+(1-u)*F('.10') == F(39, 550), 'Exercise 1 GMV')
    for alternate in (F(-1), F(0), F(1), F(2)):
        actual = F('.11')*alternate**2-F('.16')*alternate+F('.09')
        require(actual-v == F('.11')*(alternate-u)**2, 'Exercise 1 unique optimum proof')
    laws = [([F(0), F(1, 5)], [F(1, 2)]*2),
            ([F(-1, 10), F(1, 10), F(3, 10)], [F(1, 8), F(3, 4), F(1, 8)])]
    utilities, losses = [], []
    for returns, probabilities in laws:
        mean = dot(returns, probabilities)
        var = dot([(r-mean)**2 for r in returns], probabilities)
        require(mean == F(1, 10) and var == F(1, 100), 'Exercise 6 equal moments')
        losses.append(sum(p for r, p in zip(returns, probabilities) if r < 0))
        utilities.append(sum(-float(p)*exp(-10*float(r)) for r, p in zip(returns, probabilities)))
    require(losses == [0, F(1, 8)] and utilities[0] > utilities[1] and
            isclose(utilities[0], -0.5676676416183064, abs_tol=1e-12) and
            isclose(utilities[1], -0.6219181929819454, abs_tol=1e-12), 'Exercise 6 utility/tail distinction')
    for weight in (F(-2), F(0), F(1, 2), F(1), F(3)):
        w = [weight, 1-weight]
        require(dot(w, [F('.06')]*2) == F('.06') and
                variance(w, [[F('.04')]*2 for _ in range(2)]) == F('.04'),
                'Exercise 8 duplicate-claim nonunique weights')
    return {'exercise1_GMV': ['8/11', '3/11'], 'exercise6_utilities_approx': utilities,
            'exercise8': 'constant means differ from singular covariance'}


def domain_check(lab, data):
    bad = []
    x = deepcopy(data);x['conventions']['return'] = 'log';bad.append(('log-label', x))
    x = deepcopy(data);x['conventions']['fees'] = 'charged';bad.append(('unmodeled-fees', x))
    x = deepcopy(data);x['conventions']['analytic_rights'] = 'long_only';bad.append(('wrong-short-right', x))
    x = deepcopy(data);x['conventions']['sign_probability'] = '1/3';bad.append(('wrong-physical-law', x))
    x = deepcopy(data);x['main']['gamma'] = '0';bad.append(('zero-gamma', x))
    x = deepcopy(data);x['main']['risk_free'] = '-1';bad.append(('zero-safe-gross', x))
    x = deepcopy(data);x['main']['factor_loadings'][2] = x['main']['factor_loadings'][1][:];bad.append(('redundancy', x))
    x = deepcopy(data);x['main']['means'][0] = '-2';bad.append(('individual-return-below-minus-one', x))
    x = deepcopy(data);x['main']['gamma'] = 4.0;bad.append(('binary-float-input', x))
    x = deepcopy(data);x['shrinkage']['rules'][0]['alpha'] = '1/2';bad.append(('raw-label-contradiction', x))
    x = deepcopy(data);x['shrinkage']['rules'][2]['alpha'] = '2';bad.append(('invalid-intensity', x))
    x = deepcopy(data);x['shrinkage']['rules'][2]['kappa'] = '1/2';bad.append(('covariance-only-label-contradiction', x))
    for label, value in bad:
        try:
            lab.run(value)
        except ValueError:
            continue
        raise AssertionError('Invalid named fixture accepted: '+label)
    return {'meaningful_rejections': [label for label, _ in bad]}


class Chapter(HTMLParser):
    void = {'br', 'hr', 'img', 'input', 'meta', 'link', 'col', 'wbr'}

    def __init__(self):
        super().__init__()
        self.stack, self.ids, self.links, self.text = [], [], [], []
        self.worked = self.exercise_count = self.solution_count = 0
        self.exercise_depth = self.solution_depth = None

    def handle_starttag(self, tag, attributes):
        a = dict(attributes)
        if tag not in self.void:
            self.stack.append(tag)
        if 'id' in a:self.ids.append(a['id'])
        if tag == 'a':self.links.append(a['href'])
        if a.get('class') == 'worked':self.worked += 1
        if tag == 'ol' and a.get('class') == 'exercises':self.exercise_depth = len(self.stack)
        if tag == 'details' and a.get('class') == 'solutions':self.solution_depth = len(self.stack)
        if tag == 'li' and self.exercise_depth is not None:self.exercise_count += 1
        if tag == 'li' and self.solution_depth is not None:self.solution_count += 1

    def handle_endtag(self, tag):
        require(self.stack and self.stack[-1] == tag, 'Misnested manuscript tag '+tag)
        if tag == 'ol' and self.exercise_depth == len(self.stack):self.exercise_depth = None
        if tag == 'details' and self.solution_depth == len(self.stack):self.solution_depth = None
        self.stack.pop()

    def handle_data(self, text):self.text.append(text)


def artifact_check():
    content = (ROOT/'content/chapters/v09-c03.html').read_text(encoding='utf-8')
    parsed = Chapter();parsed.feed(content);parsed.close()
    require(not parsed.stack and len(parsed.ids) == len(set(parsed.ids)), 'Chapter nesting/IDs')
    require(parsed.worked >= 3 and parsed.exercise_count == parsed.solution_count == 8,
            'Chapter substantive examples and matched exercises')
    sources = json.loads((ROOT/'content/reviews/v09-c03-sources.json').read_text())
    linked_sources = {x.split('#')[1] for x in parsed.links if x.startswith('sources.html#')}
    require(linked_sources <= {x['id'] for x in sources}, 'All cited method records proposed')
    expected = {'v09-c03-inputs.json', 'v09-c03-analysis.py', 'v09-c03-output.json', 'v09-c03-README.txt'}
    manifest = json.loads((PROJECT/'v09-c03-manifest.json').read_text())
    require(Counter(x['file'] for x in manifest['files']) == Counter(expected), 'Four distributed file manifest')
    for item in manifest['files']:
        payload = (PROJECT/item['file']).read_bytes()
        require(len(payload) == item['bytes'] and hashlib.sha256(payload).hexdigest() == item['sha256'],
                'Manifest identity: '+item['file'])
    require(expected | {'v09-c03-manifest.json'} <= set(parsed.links), 'Flat downloadable asset links')
    require('v09-c02.html' in parsed.links and 'curriculum.html#v09-c04' in parsed.links,
            'Prerequisite and planned successor routes')
    return {'worked_examples': parsed.worked, 'exercises': parsed.exercise_count,
            'full_solutions': parsed.solution_count,
            'words': len(re.findall(r'\b[\w’−]+\b', ' '.join(parsed.text))),
            'manifest_files': 4, 'source_records': len(sources)}


def check():
    lab = load_lab()
    data = json.loads((PROJECT/'v09-c03-inputs.json').read_text())
    out = run_quiet(lab, data)
    require(out == json.loads((PROJECT/'v09-c03-output.json').read_text()), 'Complete reference output equality')
    mu, sigma = main_law_check(data, out)
    result = {'status': 'passed',
              'groups': [
                  'Independent loading-Gram and projected state-law moments, SPD principal minors',
                  'GMV/target primal-dual and feasible-direction certificates, dominated branch',
                  'Cash-inclusive optimum and all tangency normalization boundaries',
                  'Long-only scalar/KKT and capped inequality certificates, infeasible target',
                  'Scalar shrinkage reconstruction and common synthetic audit versus alternate truth',
                  'Remaining exercises: independent GMV, utility/tail counterexample and degeneracies',
                  'Named fixture rejects contradictory policies and invalid mathematical domains',
                  'Complete reference, strict HTML, examples/solutions and four-file manifest',
              ],
              'numerical_anchors': {'frontier': frontier_check(mu, sigma, out),
                                    'allocation': allocation_check(lab, data, mu, sigma, out),
                                    'constraints': constraint_check(lab, data, mu, sigma, out),
                                    'shrinkage': shrinkage_check(lab, data, out),
                                    'exercises': other_exercises_check()},
              'domain_checks': domain_check(lab, data),
              'structure': artifact_check(),
              'limits': 'Conditional exact arithmetic and source-fragment checks; no empirical validation, UI QA or external human certification.'}
    json.dumps(result, allow_nan=False)
    return result


if __name__ == '__main__':
    print(json.dumps(check(), indent=2, allow_nan=False))
