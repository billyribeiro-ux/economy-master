#!/usr/bin/env python3
"""Independent C12 finite oracle for the frozen canonical six-file package.

No author code, blueprint numerical outputs or source artifacts are executed.
Exact support cells and direct state accounts supplement separate proof review.
"""
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from itertools import product
from math import isqrt
from pathlib import Path
import json
import re
import sys


AUTHORS = ('content/chapters/v13-c12.html', 'scripts/check_v13_c12.py',
           'content/reviews/v13-c12-sources.json', 'content/reviews/v13-c12-author.json')
SELF, RECORD = 'scripts/check_v13_c12_peer.py', 'content/reviews/v13-c12-peer.json'
SOURCES = {
    'v13-c12-board-meyer-theory2018': 'http://www.econ.ucla.edu/sboard/teaching/WritingEconomicTheory.pdf',
    'v13-c12-berk-harvey-hirshleifer-referee2015': 'https://www.aeaweb.org/content/file?id=222.',
    'v13-c06-yildiz-games2022': 'https://ocw.mit.edu/courses/14.126-game-theory-spring-2024/mit14_126_s24_yildiz-lecture-notes.pdf',
}


def need(ok, label):
    if not ok: raise ValueError(label)


def q(value):
    need(type(value) in (int, F), 'exact rational witness; bool and float excluded')
    value = F(value)
    need(abs(value) <= 10**6 and value.denominator <= 10**9, 'bounded rational witness')
    return value


def vector(value, n):
    need(type(value) in (tuple, list) and len(value) == n, 'exact vector dimension')
    return tuple(q(x) for x in value)


def weighted(resource, weight):
    resource, weight = q(resource), q(weight)
    need(resource > 0 and 0 <= weight <= 1, 'positive resource and normalized welfare weight')
    x = min(resource, max(F(0), (resource+2)*weight-1))
    return x, resource-x


def poly(coefficients, x):
    need(type(coefficients) in (tuple, list) and 1 <= len(coefficients) <= 6, 'bounded polynomial')
    coefficients = tuple(q(z) for z in coefficients); x = q(x)
    result = F(0)
    for coefficient in reversed(coefficients): result = result*x+coefficient
    return result


def multiply(a, b):
    out = [F(0)]*(len(a)+len(b)-1)
    for i, x in enumerate(a):
        for j, y in enumerate(b): out[i+j] += x*y
    return tuple(out)


def quartic_candidates(cap):
    cap = q(cap); need(0 < cap <= 5, 'capacity-domain witness')
    candidates = sorted({F(0), cap} | {F(x) for x in (1, 2, 4) if x <= cap})
    values = tuple(poly((0, 96, -84, 28, -3), x) for x in candidates)
    best = max(values)
    return tuple(candidates), values, tuple(x for x, v in zip(candidates, values) if v == best)


def sharp(epsilon, eta):
    epsilon, eta = q(epsilon), q(eta); need(min(epsilon, eta) >= 0, 'nonnegative approximation bounds')
    true, approximate = (F(0), 2*epsilon+eta), (epsilon, epsilon+eta)
    return true, approximate, max(abs(x-y) for x, y in zip(true, approximate)), max(approximate)-approximate[0], true[1]-true[0]


def matching_pair():
    proposers = ((0, 1), (1, 0)); recipients = ((1, 0), (0, 1))
    feasible, stable = [], []
    for match in product((-1, 0, 1), repeat=2):
        used = [j for j in match if j >= 0]
        if len(used) != len(set(used)): continue
        feasible.append(match); blockers = []
        for i in range(2):
            for j in range(2):
                if match[i] == j: continue
                incumbent = next((k for k in range(2) if match[k] == j), None)
                willing_i = match[i] == -1 or proposers[i].index(j) < proposers[i].index(match[i])
                willing_j = incumbent is None or recipients[j].index(i) < recipients[j].index(incumbent)
                if willing_i and willing_j: blockers.append((i, j))
        if not blockers: stable.append(match)
    left, right = ((5, 4), (4, 5)), ((1, 100), (100, 1))
    totals = lambda scale: tuple(sum(scale*left[i][j]+right[j][i] for i, j in enumerate(match)) for match in stable)
    return tuple(feasible), tuple(stable), totals(1), totals(100)


def game(benefit, costs, grants):
    b = q(benefit); c, s = vector(costs, 2), vector(grants, 2)
    need(b > 0 and all(0 < z < b for z in c) and min(s) >= 0, 'declared coordination-game domain')
    return b, c, s


def intersect(a, b):
    lo, hi = max(a[0], b[0]), min(a[1], b[1])
    left_open = (a[2] if a[0] == lo else False) or (b[2] if b[0] == lo else False)
    right_open = (a[3] if a[1] == hi else False) or (b[3] if b[1] == hi else False)
    if lo > hi or (lo == hi and (left_open or right_open)): return None
    return lo, hi, left_open, right_open


def support_cells(benefit, costs, grants):
    """Solve all nine support patterns by intersecting exact interval constraints."""
    b, c, s = game(benefit, costs, grants)
    domains = {'0': (F(0), F(0), False, False), 'M': (F(0), F(1), True, True),
               '1': (F(1), F(1), False, False)}
    cells = {}
    for pattern in product(('0', 'M', '1'), repeat=2):
        bounds = [domains[k] for k in pattern]
        for i, own in enumerate(pattern):
            threshold = (c[i]-s[i])/b
            condition = (F(0), threshold, False, False) if own == '0' else (
                (threshold, F(1), False, False) if own == '1' else (threshold, threshold, False, False))
            bounds[1-i] = intersect(bounds[1-i], condition)
            if bounds[1-i] is None: break
        if all(x is not None for x in bounds): cells[''.join(pattern)] = tuple(bounds)
    return cells


def mixed(cells):
    need('MM' in cells and all(x[0] == x[1] for x in cells['MM']), 'unique fully mixed witness')
    return tuple(x[0] for x in cells['MM'])


def independent_law(probabilities):
    p = vector(probabilities, 2); need(all(0 <= z <= 1 for z in p), 'adoption probabilities')
    return tuple((p[0] if i else 1-p[0])*(p[1] if j else 1-p[1]) for i, j in product((0, 1), repeat=2))


def accounts(benefit, costs, grants, budget, law):
    b, c, s = game(benefit, costs, grants); budget = q(budget); law = vector(law, 4)
    need(budget >= sum(s), 'cash covers every possible grant obligation')
    need(min(law) >= 0 and sum(law) == 1, 'normalized joint action law')
    utilities = [F(0), F(0)]; spending = welfare = F(0); closing = []
    for mass, actions in zip(law, product((0, 1), repeat=2)):
        state_payments = sum(s[i]*actions[i] for i in range(2)); closing.append(budget-state_payments)
        state_utility = tuple(actions[i]*(b*actions[1-i]-c[i]+s[i]) for i in range(2))
        for i in range(2): utilities[i] += mass*state_utility[i]
        spending += mass*state_payments
        welfare += mass*(2*b*actions[0]*actions[1]-sum(c[i]*actions[i] for i in range(2)))
    need(min(closing) >= 0, 'actual sponsor balances nonnegative')
    need(sum(utilities)-spending == welfare, 'transfers cancel from real welfare')
    return tuple(utilities), spending, welfare, tuple(closing)


def obedience(benefit, costs, grants, law):
    b, c, s = game(benefit, costs, grants); law = vector(law, 4)
    need(min(law) >= 0 and sum(law) == 1, 'joint recommendation law')
    result = []
    for i in range(2):
        for recommendation in (0, 1):
            difference = F(0)
            for mass, actions in zip(law, product((0, 1), repeat=2)):
                if actions[i] == recommendation:
                    difference += mass*(2*recommendation-1)*(b*actions[1-i]-c[i]+s[i])
            result.append(difference)
    return tuple(result)


def activity(theta, x):
    theta, x = q(theta), q(x)
    need(0 <= theta <= 3 and 0 <= x <= 1, 'invariant adjustment-law domain')
    return (theta+x*x)/4


def rational_roots(theta):
    theta = q(theta); activity(theta, 0)
    d = 4-theta; n, m = isqrt(d.numerator), isqrt(d.denominator)
    need(n*n == d.numerator and m*m == d.denominator, 'perfect-square rational discriminant witness')
    return 2-F(n, m), 2+F(n, m)


def market(model, state, tax):
    need(model in ('A', 'B') and type(state) is int and state in (-1, 1), 'two maintained markets and two states')
    tax = q(tax); need(0 <= tax <= 1, 'maintained tax domain')
    # Benefit is intercept*q - curvature*q^2/2; eliminate prices with MC=q/2.
    intercept, curvature = ((4+2*state, F(1, 2)) if model == 'A' else (3+F(3, 2)*state, F(1, 4)))
    quantity = (intercept-tax)/(curvature+F(1, 2)); seller = quantity/2; buyer = seller+tax
    cost = quantity*quantity/4; benefit = intercept*quantity-curvature*quantity*quantity/2
    spending = buyer*quantity; government = tax*quantity
    need(quantity > 0 and seller > 0 and cost < 10 and spending < 20, 'displayed equilibrium has strictly slack prefunding')
    buyer_cash, producer_cash = 20-spending, 10-cost+seller*quantity
    welfare = benefit-cost
    need(buyer_cash+producer_cash+government == 30-cost, 'all monetary recipients and real production expense')
    need((benefit-spending)+(seller*quantity-cost)+government == welfare, 'tax cancels from welfare')
    optimum_quantity = intercept/(curvature+F(1, 2))
    optimum_value = intercept*optimum_quantity-(curvature+F(1, 2))*optimum_quantity**2/2
    return {'q': quantity, 'ps': seller, 'pb': buyer, 'revenue': government,
            'welfare': welfare, 'loss': optimum_value-welfare, 'cost': cost, 'spending': spending,
            'cash': (buyer_cash, producer_cash, government)}


def average_market(model, tax):
    rows = tuple(market(model, z, tax) for z in (-1, 1))
    return {key: sum(row[key] for row in rows)/2 for key in ('q', 'ps', 'pb', 'revenue', 'welfare', 'loss')}


class Audit:
    def __init__(self): self.comparisons = 0; self.rejections = 0
    def eq(self, actual, expected, label):
        self.comparisons += 1; need(actual == expected, label+': '+repr(actual)+' != '+repr(expected))
    def yes(self, actual, label): self.eq(bool(actual), True, label)
    def reject(self, fn, *args):
        try: fn(*args)
        except ValueError: self.rejections += 1
        else: raise ValueError('invalid domain accepted by '+fn.__name__)


def derive(a):
    inputs = {'w1-resource': 12, 'w1-scale': 4, 'w2-coefficients': (96, -84, 28, -3),
              'w2-concave-candidate': F(23, 6), 'w3-benefit-cost': (3, 1), 'w3-subsidy': F(1, 2),
              'w4-theta': F(7, 4), 'w4-candidate': F(3, 5), 'w4-new-theta': F(51, 25),
              'w4-claimed-error': F(1, 100), 'w5-slopes': (2, 4), 'w5-funds': (20, 10), 'w5-tax': 1,
              'w6-benefit-costs': '(b,c₁,c₂)=(3,1,2)', 'w6-policy': '(K,s₁,s₂)=(1,1/2,1/2)',
              'w6-robust-grant': (F(11, 8), 0), 'e1-weights': (F(1, 4), F(3, 4), F(1, 14), F(13, 14)),
              'e2-scale': 100, 'e3-cap': '[0,3]', 'e4-errors': '(ε,η)=(3/4,1/2)', 'e5-cost': F(3, 2),
              'e6-probability': F(1, 4), 'e7-theta': F(15, 16), 'e9-tax': F(1, 2),
              'e10-error': F(1, 6), 'e11-budget': F(3, 2)}
    result = {}
    result['w1-equal'] = weighted(12, F(1, 2)); result['w1-scaled'] = weighted(12, F(4, 5))
    result['w1-weight-boundaries'] = (F(1, 12+2), F(12+1, 12+2)); result['w1-sensitivity'] = 12+2
    result['e1-allocations'] = tuple(weighted(12, lam) for lam in inputs['e1-weights'])
    a.eq((weighted(12, 0), weighted(12, 1)), ((0, 12), (12, 0)), 'endpoint weights have unique endpoints')
    for lam in inputs['e1-weights']:
        x, y = weighted(12, lam)
        numerator = lam*(1+y)-(1-lam)*(1+x)
        a.eq(numerator, 14*lam-1-x, 'entire derivative numerator identity')
    feasible, stable, old, new = matching_pair()
    a.eq(stable, ((0, 1), (1, 0)), 'all matching outcomes surviving every blocking pair')
    a.yes(old[0] < old[1] and new[0] > new[1], 'interpersonal rescaling reverses the aggregate ranking')
    result.update({'e2-feasible-count': len(feasible), 'e2-original-totals': old, 'e2-scaled-totals': new})
    derivative = (96, -168, 84, -12)
    factored = multiply(multiply((-1, 1), (-2, 1)), (-4, 1))
    a.eq(tuple(-12*x for x in factored), derivative, 'full cubic derivative coefficient identity')
    critical = (1, 2, 4); second = (-168, 168, -36)
    _, values, best = quartic_candidates(5)
    a.eq(best, (4,), 'all endpoint/stationary comparisons give the unique original global optimum')
    result.update({'w2-critical': critical, 'w2-curvatures': tuple(poly(second, x) for x in critical),
                   'w2-values': values, 'w2-regret': max(values)-poly((0, 96, -84, 28, -3), 1),
                   'w2-concave-loss': 3*(F(23, 6)-4)**2})
    a.eq(-6*(F(23, 6)-4), 1, 'changed concave objective has the claimed nonzero derivative')
    _, changed_values, changed_best = quartic_candidates(3)
    a.eq(changed_best, (3,), 'changed domain is solved globally')
    result.update({'e3-values': changed_values, 'e3-regret': max(changed_values)-37,
                   'e3-endpoint-derivative': poly(derivative, 3)})
    f, fhat, error, gap, regret = sharp(F(3, 4), F(1, 2))
    a.eq((error, gap, regret), (F(3, 4), F(1, 2), 2), 'global approximation bound is attained')
    result['e4-sharp-regret'] = regret
    for subsidy, keys in ((F(0), {'00', 'MM', '11'}), (F(1, 2), {'00', 'MM', '11'}),
                          (F(1), {'00', '11'}), (F(3, 2), {'11'})):
        a.eq(set(support_cells(3, (1, 1), (subsidy, subsidy))), keys, 'all nine supports at subsidy regimes and equality')
    p0 = mixed(support_cells(3, (1, 1), (0, 0))); ph = mixed(support_cells(3, (1, 1), (F(1, 2),)*2))
    u, spending, welfare, _ = accounts(3, (1, 1), (F(1, 2),)*2, 1, independent_law(ph))
    full = accounts(3, (1, 1), (F(1, 2),)*2, 1, (0, 0, 0, 1))
    a.eq(u, (0, 0), 'each agent indifferent at the subsidized independent mixture')
    result.update({'w3-mix-zero': p0, 'w3-mix-half': ph, 'w3-mixed-welfare': welfare,
                   'w3-mixed-spending': spending, 'w3-full-accounts': (sum(full[0]), full[1], full[2])})
    ec = (F(3, 2),)*2; changed_supports = support_cells(3, ec, (F(1, 2),)*2)
    a.eq(set(changed_supports), {'00', 'MM', '11'}, 'changed-cost complete support set')
    ep = mixed(changed_supports)
    e5 = accounts(3, ec, (F(1, 2),)*2, 1, independent_law(ep))
    result.update({'e5-mixed': ep, 'e5-zero-mixed': mixed(support_cells(3, ec, (0, 0))),
                   'e5-full-welfare': accounts(3, ec, (F(1, 2),)*2, 1, (0, 0, 0, 1))[2], 'e5-mixed-welfare': e5[2]})
    ce_law = (F(3, 4), 0, 0, F(1, 4)); ce = accounts(3, (1, 1), (F(1, 2),)*2, 1, ce_law)
    margins = obedience(3, (1, 1), (F(1, 2),)*2, ce_law)
    a.eq(margins, (F(3, 8), F(5, 8), F(3, 8), F(5, 8)), 'all four unconditional CE obedience inequalities')
    a.yes(min(obedience(3, (1, 1), (F(1, 2),)*2, independent_law((F(1, 4),)*2))) < 0,
          'independent marginals fail an actual deviation inequality')
    result.update({'e6-accounts': (sum(ce[0]), ce[1], ce[2]), 'e6-independent-gain': 3*F(1, 4)-1+F(1, 2)})
    theta, candidate = F(7, 4), F(3, 5); roots = rational_roots(theta)
    first = activity(theta, 0); second = activity(theta, first)
    residual = abs(candidate-activity(theta, candidate)); distance = abs(candidate-roots[0])
    new_theta = F(51, 25); parameter_gap = new_theta-theta
    a.eq(activity(new_theta, candidate), candidate, 'changed map exactly fixes the returned candidate')
    a.yes(residual > F(2, 100) and distance > F(4, 100), 'claimed computed and map errors are jointly inconsistent')
    shifted_residual = abs(candidate-(activity(theta, candidate)+F(1, 100)))
    a.eq(shifted_residual, residual-F(1, 100), 'constant map shift attains the minimum possible computed residual')
    a.yes(0 <= activity(theta, 0)+F(1, 100) < activity(theta, 1)+F(1, 100) <= 1,
          'the attaining computed map remains within the original interval')
    a.eq((activity(theta, 0)+F(1, 100), activity(theta, 1)+F(1, 100)),
         (F(179, 400), F(279, 400)), 'printed image endpoints of the attaining map')
    result.update({'w4-roots': roots, 'w4-iterates': (first, second), 'w4-error': (residual, 2*residual, distance),
                   'w4-new-fixed': rational_roots(new_theta)[0], 'w4-sensitivity': (parameter_gap, distance/parameter_gap),
                   'w4-local-derivative': 1/(4-2*roots[0]), 'w4-false-distance-bound': F(4, 100),
                   'w4-minimum-numerical-residual': residual-F(1, 100),
                   'e8-minimum-residual': residual-F(1, 100), 'e8-map-error': parameter_gap/4, 'e8-bound': parameter_gap/2})
    etheta, ecandidate = F(15, 16), F(1, 3); eroots = rational_roots(etheta)
    eresidual = abs(ecandidate-activity(etheta, ecandidate))
    result.update({'e7-roots': eroots, 'e7-residual': eresidual, 'e7-bound': 2*eresidual,
                   'e7-distance': ecandidate-eroots[0], 'e7-derivative': 1/(4-2*eroots[0])})
    a.eq((rational_roots(0)[0], rational_roots(3)[0]), (0, 1), 'full parameter endpoints are in the invariant domain')
    for th in (F(0), theta, etheta, new_theta, F(3)):
        root = rational_roots(th)[0]; a.eq(activity(th, root), root, 'exact admissible fixed point')
        a.yes(0 <= activity(th, 0) <= activity(th, 1) <= 1, 'domain invariance at monotone extrema')
    baseline = {m: tuple((z, market(m, z, 0)['ps'], market(m, z, 0)['q']) for z in (-1, 1)) for m in ('A', 'B')}
    a.eq(baseline['A'], baseline['B'], 'the whole observed two-state joint law agrees')
    result['w5-baseline-states'] = baseline['A']
    a.eq(F(8)**2/4, 16, 'unrestricted producer quantity at price four would exceed ten-unit prefunding')
    a.eq(F(9, 4)*9, F(81, 4), 'unrestricted B demand at price nine-quarters would exceed twenty cash')
    a.eq(F(20)/F(9, 4), F(80, 9), 'funded quantity at that buyer price')
    taxed = [average_market(m, 1) for m in ('A', 'B')]
    for name, key in (('quantities', 'q'), ('seller-prices', 'ps'), ('buyer-prices', 'pb'), ('revenue', 'revenue'), ('real-losses', 'loss')):
        result['w5-'+('mean-'+name if name != 'real-losses' else name)] = tuple(row[key] for row in taxed)
    result['w5-baseline-welfare'] = tuple(average_market(m, 0)['welfare'] for m in ('A', 'B'))
    no_tax_rows = tuple(market(m, z, 0) for m in ('A', 'B') for z in (-1, 1))
    result['w5-resource-bounds'] = (max(row['spending'] for row in no_tax_rows), max(row['cost'] for row in no_tax_rows))
    for m in ('A', 'B'):
        for tax in (F(0), F(1, 2), F(1)):
            for z in (-1, 1):
                row = market(m, z, tax)
                a.eq(row['loss'], (F(1, 2) if m == 'A' else F(2, 3))*tax*tax, 'statewise real loss from primitive benefit and cost')
                a.yes(row['spending'] <= 18 and row['cost'] <= 9, 'clearing allocations strictly respect endowed cash')
        mean = average_market(m, F(1, 2))
        result['e9-'+m] = tuple(mean[key] for key in ('q', 'ps', 'pb', 'revenue', 'loss'))
    gap = taxed[0]['q']-taxed[1]['q']; boundary = gap/2
    result.update({'e10-critical-error': 'ε<'+str(boundary), 'e10-touch': (taxed[0]['q']+taxed[1]['q'])/2})
    a.eq(taxed[0]['q']-boundary, taxed[1]['q']+boundary, 'closed intervals touch at the exact error threshold')
    fair = support_cells(3, (1, 2), (F(1, 2),)*2); zero = support_cells(3, (1, 2), (0, 0))
    a.eq(set(fair), {'00', 'MM', '11'}, 'complete submitted-game Nash set')
    fm = mixed(fair); fu = accounts(3, (1, 2), (F(1, 2),)*2, 1, (0, 0, 0, 1))
    fa = accounts(3, (1, 2), (F(1, 2),)*2, 1, independent_law(fm))
    result.update({'w6-fair-mix': fm, 'w6-zero-mix': mixed(zero), 'w6-full-utilities': fu[0],
                   'w6-full-surplus': fu[2], 'w6-mixed-accounts': (fa[1], fa[2]), 'w6-budget-condition': 'K>'+str(min(1, 2))})
    equality = support_cells(3, (1, 2), (1, 0))
    a.eq(set(equality), {'00', 'M0', '11'}, 'strict funding equality retains the full one-sided mixed segment')
    a.eq(equality['M0'], ((F(0), F(2, 3), True, False), (F(0), F(0), False, False)), 'exact segment endpoints and inclusion')
    opposite_equality = support_cells(3, (1, 2), (0, 2))
    a.eq(set(opposite_equality), {'00', '0M', '11'}, 'other asymmetric equality orientation is also complete')
    a.eq(opposite_equality['0M'], ((F(0), F(0), False, False), (F(0), F(1, 3), True, False)),
         'other closed union segment extends to its exact indifference boundary')
    result['w6-boundary-limit'] = equality['M0'][0][1]
    costs_rectangle = tuple(product((F(3, 4), F(5, 4)), (F(7, 4), F(9, 4))))
    robust_welfare = []
    for cost in costs_rectangle:
        a.eq(set(support_cells(3, cost, (F(11, 8), 0))), {'11'}, 'funded grant remains strictly implementing at every rectangular corner')
        robust_welfare.append(accounts(3, cost, (F(11, 8), 0), F(3, 2), (0, 0, 0, 1))[2])
    result.update({'w6-robust-infimum': min(F(5, 4), F(9, 4)),
                   'w6-robust-welfare': '['+str(min(robust_welfare))+','+str(max(robust_welfare))+']'})
    a.yes('00' in support_cells(3, (F(5, 4), F(9, 4)), (F(5, 4), 0)), 'upper-corner equality defeats robust uniqueness')
    target = (F(5, 4), 0); a.eq(set(support_cells(3, (1, 2), target)), {'11'}, 'targeted funded strict dominance excludes every other support')
    ta = accounts(3, (1, 2), target, F(3, 2), (0, 0, 0, 1))
    equal_supports = support_cells(3, (1, 2), (F(3, 4),)*2)
    a.eq(set(equal_supports), {'00', 'MM', '11'}, 'equal-grant restriction retains all three equilibria')
    eqmix = mixed(equal_supports)
    ea = accounts(3, (1, 2), (F(3, 4),)*2, F(3, 2), independent_law(eqmix))
    result.update({'e11-target-accounts': (ta[0], ta[1], ta[2]), 'e11-equal-infimum': 2*min(1, 2),
                   'e11-equal-mix': eqmix, 'e11-mixed-welfare': ea[2]})
    fresh_c, fresh_s = (F(3, 2), F(5, 2)), (F(3, 4),)*2
    fresh_supports = support_cells(4, fresh_c, fresh_s)
    a.eq(set(fresh_supports), {'00', 'MM', '11'}, 'fresh referee case full support set')
    fresh_p = mixed(fresh_supports)
    fresh_m = accounts(4, fresh_c, fresh_s, F(3, 2), independent_law(fresh_p))
    fresh_f = accounts(4, fresh_c, fresh_s, F(3, 2), (0, 0, 0, 1))
    result.update({'e12-mix': fresh_p, 'e12-sponsor-loss': fresh_m[1], 'e12-mixed-welfare': fresh_m[2],
                   'e12-full-utilities': fresh_f[0], 'e12-full-welfare': fresh_f[2], 'e12-infimum': min(fresh_c)})
    return inputs, result


def pairs(items):
    out = {}
    for key, value in items:
        need(key not in out, 'duplicate JSON key'); out[key] = value
    return out


def nonfinite(value):
    raise ValueError('nonfinite JSON constant '+value)


def finite_float(text):
    value = float(text); need(-float('inf') < value < float('inf'), 'finite JSON number')
    return value


def read_json(raw):
    need(type(raw) is bytes, 'JSON bytes')
    return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs, parse_constant=nonfinite, parse_float=finite_float)


def display(value):
    if type(value) is str: return value
    if type(value) in (tuple, list): return '('+','.join(display(x) for x in value)+')'
    return str(F(value))


def compact(text):
    return re.sub(r'\s+', '', text).replace('−', '-')


class Fragment(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.ids, self.worked, self.prompts, self.answers = [], [], [], [], []
        self.sources, self.links, self.markers = {}, set(), {'data-input': {}, 'data-calc': {}}
        self.exercise_depth = self.solution_depth = self.capture = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs); classes = attrs.get('class', '').split()
        if 'id' in attrs: self.ids.append(attrs['id'])
        if 'worked' in classes: self.worked.append(attrs.get('id'))
        if tag == 'ol' and 'exercises' in classes: self.exercise_depth = len(self.stack)
        if tag == 'details' and 'solutions' in classes: self.solution_depth = len(self.stack)
        if tag == 'li' and self.exercise_depth is not None: self.prompts.append(attrs.get('id'))
        if 'data-solution-for' in attrs:
            need(self.solution_depth is not None, 'paired answer inside the full solutions disclosure')
            self.answers.append(attrs['data-solution-for'])
        if 'href' in attrs: self.links.add(attrs['href'])
        if 'data-source' in attrs:
            key, url = attrs['data-source'], attrs.get('href')
            need(key in SOURCES and url == SOURCES[key], 'exact source identity and primary URL')
            self.sources[key] = url
        for kind in self.markers:
            if kind in attrs:
                key = attrs[kind]
                need(tag == 'span' and key not in self.markers[kind] and self.capture is None, 'unique numeric marker')
                self.markers[kind][key] = ''; self.capture = (kind, key)
        if tag not in {'br', 'hr', 'img', 'meta', 'link', 'input'}: self.stack.append(tag)

    def handle_data(self, text):
        if self.capture is not None:
            kind, key = self.capture; self.markers[kind][key] += text

    def handle_endtag(self, tag):
        need(bool(self.stack) and self.stack[-1] == tag, 'balanced HTML fragment')
        self.stack.pop()
        if tag == 'span': self.capture = None
        if tag == 'ol' and self.exercise_depth == len(self.stack): self.exercise_depth = None
        if tag == 'details' and self.solution_depth == len(self.stack): self.solution_depth = None


def inspect_manuscript(text, audit, inputs, results):
    fragment = Fragment(); fragment.feed(text); fragment.close()
    audit.yes(not fragment.stack and fragment.capture is None, 'complete closed manuscript')
    audit.eq(len(fragment.ids), len(set(fragment.ids)), 'unique IDs')
    audit.yes(all(key.startswith('v13-c12-') for key in fragment.ids), 'chapter ID namespace')
    audit.eq(fragment.worked, ['v13-c12-w'+str(i) for i in range(1, 7)], 'all six worked cases use actual shared token')
    exercises = ['v13-c12-e'+str(i) for i in range(1, 13)]
    audit.eq(fragment.prompts, exercises, 'twelve exact transfer prompts')
    audit.eq(fragment.answers, exercises, 'all twelve complete paired solutions')
    audit.eq(fragment.sources, SOURCES, 'three precise primary-source routes')
    audit.eq({url for url in fragment.links if not url.startswith(('http://', 'https://'))},
             {'v13-c'+str(i).zfill(2)+'.html' for i in (1, 2, 4, 6, 8, 9, 10, 11)}, 'flat prerequisite links')
    for kind, expected in (('data-input', inputs), ('data-calc', results)):
        audit.eq(set(fragment.markers[kind]), set(expected), 'full '+kind+' inventory')
        for name, value in expected.items():
            audit.eq(compact(fragment.markers[kind][name]), compact(display(value)), 'independent '+kind+' '+name)
    for phrase in ('independent mixed Nash', 'global</em> objective certificate',
                   'actual prefunded supply', 'Actual supply is nondecreasing',
                   '20/p<sub>b</sub>', 'no budget-minimizing uniquely implementing grant attains it',
                   'within a declared two-model class', 'Teach-back benchmark', 'delayed retention',
                   'This minimum is attained:', 'image [179/400,279/400] inside [0,1]'):
        audit.yes(phrase in text, 'reviewed proof, source or repair boundary '+phrase)


def bindings(rows):
    need(type(rows) is list, 'binding list'); out = {}
    for row in rows:
        need(type(row) is dict and set(row) == {'path', 'bytes', 'sha256'}, 'binding fields')
        name = row['path']; need(type(name) is str and name not in out, 'unique bound path')
        need(type(row['bytes']) is int and row['bytes'] > 0, 'positive payload byte size')
        need(type(row['sha256']) is str and re.fullmatch('[0-9a-f]{64}', row['sha256']) is not None, 'SHA256 format')
        out[name] = row
    return out


def invalid_domains(a):
    for value in (True, False, 0.5, '1/2', None, float('nan'), float('inf'), 10**7, F(1, 10**10)):
        a.reject(q, value)
    a.reject(vector, (1, 2), 3)
    for resource, weight in ((0, F(1, 2)), (12, -1), (12, 2)): a.reject(weighted, resource, weight)
    a.reject(poly, [], 1)
    a.reject(poly, (1,)*7, 1)
    a.reject(quartic_candidates, 0)
    a.reject(quartic_candidates, 6)
    a.reject(sharp, -1, 0)
    a.reject(sharp, 0, -1)
    for b, c, s in ((0, (1, 1), (0, 0)), (3, (0, 1), (0, 0)), (3, (1, 3), (0, 0)), (3, (1, 2), (-1, 0))):
        a.reject(support_cells, b, c, s)
    a.reject(independent_law, (F(1, 2), 2))
    a.reject(accounts, 3, (1, 1), (1, 1), 1, (0, 0, 0, 1))
    a.reject(accounts, 3, (1, 1), (0, 0), 0, (1, 0, 0, 1))
    a.reject(obedience, 3, (1, 1), (0, 0), (2, -1, 0, 0))
    for theta, x in ((-1, 0), (4, 0), (1, -1), (1, 2)): a.reject(activity, theta, x)
    a.reject(rational_roots, F(1))
    for model, state, tax in (('C', 1, 0), ('A', 0, 0), ('B', True, 0), ('A', 1, -1), ('A', -1, 2)):
        a.reject(market, model, state, tax)
    for raw in (b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":Infinity}', b'{"x":1e9999}'):
        a.reject(read_json, raw)


def check(root=None):
    """Quiet, no-write review; read only four authors and this peer pair."""
    need(root is None or isinstance(root, (str, Path)), 'root must be a path or None')
    base = Path(__file__).resolve().parents[1] if root is None else Path(root)
    names = AUTHORS+(SELF, RECORD)
    raw = {name: (base/name).read_bytes() for name in names}
    a = Audit()
    inputs, results = derive(a)
    inspect_manuscript(raw[AUTHORS[0]].decode('utf-8'), a, inputs, results)
    source, author, peer = (read_json(raw[name]) for name in (AUTHORS[2], AUTHORS[3], RECORD))
    for record in (source, author, peer):
        a.eq(record['chapter'], 'v13-c12', 'record chapter identity')
    entries = source['sources']
    a.eq(len(entries), len(SOURCES), 'source record has exactly the three reviewed scopes')
    a.eq({row['id']: row['url'] for row in entries}, SOURCES, 'source provenance and exact primary URLs')
    a.eq([row['reuse'] for row in entries], [False, False, True], 'fresh and inherited inspections remain distinct')
    a.yes('No new whole-PDF reading' in entries[2]['inspection_attribution'], 'source reuse does not claim new inspection')
    a.yes('c05_review' in peer['source_audit']['inspection_attribution'], 'peer attributes actual fresh source inspection')
    proofs = {'v13-c12-'+name for name in ('welfare', 'global', 'selection', 'approximation', 'identification', 'referee')}
    prompts = {'v13-c12-e'+str(i) for i in range(1, 13)}
    a.eq(set(author['proof_audit']), proofs, 'author covers every printed proof')
    a.eq(set(peer['proof_audit']), proofs, 'peer separately covers every printed proof')
    a.eq(set(author['exact_prompt_solution_audit']), prompts, 'author solves every exact prompt')
    a.eq(set(peer['exercise_audit']), prompts, 'peer solves every exact prompt')
    a.eq(author['unresolved_findings'], [], 'no unresolved author finding')
    a.eq(peer['open_findings'], [], 'no unresolved peer finding')
    a.eq({row['id'] for row in peer['resolved_findings']},
         {'off-equilibrium-prefunding', 'complete-teach-back-answer', 'minimum-residual-attainment'},
         'all three reviewed repairs remain recorded')
    for record, field, expected in ((author, 'payload_bindings', set(AUTHORS[:3])),
                                     (peer, 'bindings', set(AUTHORS+(SELF,)))):
        rows = bindings(record[field])
        a.eq(set(rows), expected, 'exact nonself binding set')
        for name, row in rows.items():
            a.eq((len(raw[name]), sha256(raw[name]).hexdigest()), (row['bytes'], row['sha256']),
                 'final payload size and SHA256 '+name)
    invalid_domains(a)
    a.reject(check, True)
    a.eq({name: (base/name).read_bytes() for name in names}, raw, 'all six runtime payloads unchanged')
    summary = {
        'chapter': 'v13-c12', 'status': 'passed', 'comparisons': a.comparisons,
        'domain_rejections': a.rejections, 'worked_cases': 6, 'solved_exercises': 12,
        'primitive_markers': len(inputs), 'result_markers': len(results),
        'feasible_matchings': 7, 'stable_matchings': 2,
        'support_patterns_per_game': 9, 'runtime_files': len(names),
        'interventions': [
            'welfare normalization and full matching rescaling',
            'global polynomial candidates, changed cap and sharp objective certificate',
            'complete mixed supports, strict grants and both equality segments',
            'recommendation-conditioned incentives and funded state accounts',
            'robust cost bounds and equal-grant restrictions',
            'map invariance, true/computed error and attained residual minimum',
            'observational equivalence, actual prefunding and tax discrimination'
        ],
        'proof_scope': 'Finite witnesses supplement the full separate proof and exact-solution audit; no author code is executed.'
    }
    read_json(json.dumps(summary, allow_nan=False).encode('utf-8'))
    return summary


if __name__ == '__main__':
    need(len(sys.argv) == 1, 'silent checker accepts no CLI arguments')
    check()
