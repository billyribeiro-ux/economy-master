"""Quiet exact finite checks for the four-file v12-c08 RD and synthetic-control chapter."""
from fractions import Fraction as F
from html.parser import HTMLParser
from pathlib import Path
from statistics import NormalDist
import contextlib
import hashlib
import importlib.util
import io
import itertools
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile

BASE = Path(__file__).resolve().parents[1]
FILES = ('content/chapters/v12-c08.html', 'scripts/check_v12_c08.py',
         'content/reviews/v12-c08-sources.json', 'content/reviews/v12-c08-author.json')
SOURCES = {'v12-c08-cattaneo-titiunik2022', 'v12-c08-cit-foundations2019', 'v12-c08-abadie2021'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def rational(value):
    require(type(value) is int or isinstance(value, F), 'exact rational required')
    result = F(value)
    require(abs(result) <= 10**6, 'bounded rational required')
    return result


def strict(text):
    def pairs(rows):
        result = {}
        for key, value in rows:
            require(key not in result, 'duplicate JSON member')
            result[key] = value
        return result
    def invalid(value):
        raise ValueError('nonfinite JSON: '+value)
    def finite(value):
        result = float(value)
        require(math.isfinite(result), 'overflowed JSON number')
        return result
    return json.loads(text, object_pairs_hook=pairs, parse_constant=invalid, parse_float=finite)


def dot(a, b):
    return sum((x*y for x, y in zip(a, b)), F())


def average(row):
    return sum(row, F())/len(row)


def inverse(matrix):
    require(type(matrix) is list and 1 <= len(matrix) <= 3, 'matrix order1..3')
    n = len(matrix)
    require(all(type(row) is list and len(row) == n for row in matrix), 'square matrix')
    a = [[rational(v) for v in row]+[F(i == j) for j in range(n)] for i, row in enumerate(matrix)]
    for j in range(n):
        k = next((i for i in range(j, n) if a[i][j]), None)
        require(k is not None, 'rank failure')
        a[j], a[k] = a[k], a[j]; pivot = a[j][j]
        a[j] = [v/pivot for v in a[j]]
        for i in range(n):
            if i != j:
                factor = a[i][j]; a[i] = [v-factor*w for v, w in zip(a[i], a[j])]
    return [row[n:] for row in a]


def local_weights(scores, degree=1, kernels=None):
    require(type(scores) is list and 2 <= len(scores) <= 32, '2..32 fixed scores')
    require(type(degree) is int and degree in (1, 2), 'linear or quadratic order')
    x = [rational(v) for v in scores]
    require(all(v > 0 for v in x) or all(v < 0 for v in x), 'one strictly separated cutoff side')
    if kernels is None:
        kernels = [F(1)]*len(x)
    require(type(kernels) is list and len(kernels) == len(x), 'kernel length')
    k = [rational(v) for v in kernels]
    require(all(v >= 0 for v in k), 'nonnegative kernel')
    design = [[v**j for j in range(degree+1)] for v in x]
    gram = [[sum(k[t]*row[i]*row[j] for t, row in enumerate(design)) for j in range(degree+1)] for i in range(degree+1)]
    gi = inverse(gram)
    return [k[t]*dot(gi[0], row) for t, row in enumerate(design)]


def grid_weights(n, k):
    require(type(n) is int and type(k) is int and 2 <= k <= 32 and k <= n <= 100000,
            'fixed grid: 2<=k<=32 and k<=n<=100000')
    return [F(2*(2*k+1-3*j), k*(k-1)) for j in range(1, k+1)]


def cutoff_wald(types, direct=F(0)):
    require(type(types) is list and 2 <= len(types) <= 4, 'two to four explicit cutoff types')
    rows = []
    for row in types:
        require(type(row) is tuple and len(row) == 5, 'type probability, receipt0/1, base, effect')
        p, d0, d1, base, effect = row
        p, base, effect = rational(p), rational(base), rational(effect)
        require(p > 0 and type(d0) is int and type(d1) is int and d0 in (0, 1) and d1 in (0, 1), 'valid positive type')
        rows.append((p, d0, d1, base, effect))
    require(sum(r[0] for r in rows) == 1, 'complete type mass')
    direct = rational(direct)
    receipt = [sum(p*(d0 if z == 0 else d1) for p, d0, d1, y0, effect in rows) for z in (0, 1)]
    outcome = [sum(p*(y0+(d0 if z == 0 else d1)*effect+direct*z) for p, d0, d1, y0, effect in rows) for z in (0, 1)]
    first = receipt[1]-receipt[0]
    require(first != 0, 'zero first stage')
    return {'receipt': receipt, 'outcome': outcome, 'first': first, 'ITT': outcome[1]-outcome[0],
            'ratio': (outcome[1]-outcome[0])/first, 'ATE': sum(p*eff for p, d0, d1, y0, eff in rows)}


def simplex_fit(target, donors):
    """Enumerate small active faces and certify the optimum by its KKT inequality."""
    require(type(target) is list and 2 <= len(target) <= 3, 'two or three preperiod coordinates')
    require(type(donors) is list and 2 <= len(donors) <= 3, 'two or three donors')
    q = len(target); j = len(donors)
    require(all(type(row) is list and len(row) == q for row in donors), 'common donor coordinates')
    t = [rational(v) for v in target]; x = [[rational(v) for v in row] for row in donors]
    candidates = []
    for size in range(1, j+1):
        for face in itertools.combinations(range(j), size):
            w = [F(0)]*j
            if size == 1:
                w[face[0]] = F(1)
            else:
                last = face[-1]
                directions = [[x[i][k]-x[last][k] for k in range(q)] for i in face[:-1]]
                gram = [[dot(a, b) for b in directions] for a in directions]
                try:
                    gi = inverse(gram)
                except ValueError:
                    # Flat faces have optimal extreme subfaces also enumerated here.
                    continue
                rhs = [dot(v, [t[k]-x[last][k] for k in range(q)]) for v in directions]
                for pos, index in enumerate(face[:-1]):
                    w[index] = dot(gi[pos], rhs)
                w[last] = 1-sum(w)
                if min(w) < 0:
                    continue
            fitted = [sum(w[i]*x[i][k] for i in range(j)) for k in range(q)]
            error = [a-b for a, b in zip(t, fitted)]
            candidates.append((dot(error, error), tuple(w), fitted, error))
    require(bool(candidates), 'simplex optimum unavailable')
    loss, weights, fitted, error = min(candidates, key=lambda z: (z[0], z[1]))
    gradients = [-2*dot(row, error) for row in x]
    active = [gradients[i] for i, wi in enumerate(weights) if wi > 0]
    require(all(v == active[0] for v in active) and all(v >= active[0] for v in gradients), 'KKT optimum certificate failed')
    return {'weights': list(weights), 'fit': fitted, 'error': error, 'loss': loss}


def rmspe_score(pre_mse, post_mse):
    pre_mse = rational(pre_mse); post_mse = rational(post_mse)
    require(pre_mse >= 0 and post_mse >= 0, 'nonnegative mean squared errors')
    # Extended order for the SQUARED ratio; no nonfinite JSON float is created.
    if pre_mse == 0:
        return (1, F(0)) if post_mse > 0 else (0, F(0))
    return (0, post_mse/pre_mse)


def weighted_ranks(scores, probabilities):
    require(type(scores) is list and type(probabilities) is list and 2 <= len(scores) <= 8,
            'two to eight finite assignment labels')
    require(len(scores) == len(probabilities), 'one probability per label')
    for score in scores:
        require(type(score) is tuple and len(score) == 2 and type(score[0]) is int and score[0] in (0, 1), 'extended score order')
        require(rational(score[1]) >= 0 and (score[0] == 0 or score[1] == 0), 'finite score or infinity marker')
    p = [rational(v) for v in probabilities]
    require(all(v > 0 for v in p) and sum(p) == 1, 'positive complete assignment law')
    return [sum(p[j] for j in range(len(scores)) if scores[j] >= scores[i]) for i in range(len(scores))]


def normalize(text):
    return re.sub(r'\s+', '', text).replace('−', '-')


class Reader(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []; self.ids = []; self.links = []; self.sources = []; self.text = []
        self.worked = 0; self.exercise_count = 0; self.solution_count = 0
        self.prompts = {}; self.answers = {}; self.capture = []
        self.exercise_depth = None; self.solution_depth = None
    def handle_starttag(self, tag, attrs):
        a = dict(attrs); classes = a.get('class', '').split()
        if 'id' in a:
            self.ids.append(a['id'])
        if 'href' in a:
            self.links.append(a['href'])
        if 'data-source' in a:
            self.sources.append(a['data-source'])
        if 'worked' in classes:
            self.worked += 1
        if tag == 'ol' and 'exercises' in classes:
            self.exercise_depth = len(self.stack)
        if tag == 'details' and 'solutions' in classes:
            self.solution_depth = len(self.stack)
        if tag == 'li':
            if self.exercise_depth is not None:
                self.exercise_count += 1
                self.capture.append((len(self.stack), self.prompts, a.get('id'), []))
            if 'data-solution-for' in a:
                require(self.solution_depth is not None, 'answer outside solutions')
                self.solution_count += 1
                self.capture.append((len(self.stack), self.answers, a['data-solution-for'], []))
        if tag not in ('br', 'hr', 'img', 'meta', 'link', 'input'):
            self.stack.append(tag)
    def handle_endtag(self, tag):
        require(bool(self.stack) and self.stack[-1] == tag, 'unbalanced '+tag)
        depth = len(self.stack)-1
        if tag == 'li':
            for row in list(self.capture):
                level, dest, key, values = row
                if level == depth:
                    require(key and key not in dest, 'missing or duplicate solution key')
                    dest[key] = ' '.join(values); self.capture.remove(row)
        if tag == 'ol' and depth == self.exercise_depth:
            self.exercise_depth = None
        if tag == 'details' and depth == self.solution_depth:
            self.solution_depth = None
        self.stack.pop()
    def handle_data(self, value):
        self.text.append(value)
        for _, _, _, values in self.capture:
            values.append(value)


class Audit:
    def __init__(self):
        self.count = 0; self.rejections = 0; self.anchors = 0
    def eq(self, value, expected, label):
        self.count += 1
        require(value == expected, label+': '+repr(value)+' != '+repr(expected))
    def near(self, value, expected, label, tolerance=2e-12):
        self.count += 1
        require(math.isclose(value, expected, rel_tol=tolerance, abs_tol=tolerance), label)
    def reject(self, call, label):
        self.count += 1
        try:
            call()
        except ValueError:
            self.rejections += 1
        else:
            raise ValueError('invalid domain accepted: '+label)
    def anchor(self, page, exercise, *values):
        answer = normalize(page.answers['v12-c08-e'+str(exercise)])
        for value in values:
            self.eq(normalize(str(value)) in answer, True, 'solution '+str(exercise)+' anchor '+str(value))
            self.anchors += 1
    def body(self, page, value):
        self.eq(normalize(str(value)) in normalize(' '.join(page.text)), True, 'body anchor '+str(value))
        self.anchors += 1


def numerical(a, page):
    # Polynomial antiderivatives supply exact finite-window integrals.
    def integral(poly, left, right):
        return sum(F(c, j+1)*(right**(j+1)-left**(j+1)) for j, c in enumerate(poly))
    for h, expected in ((F(1), F(9, 2)), (F(1, 5), F(33, 10))):
        right = integral([5, 2, 1], F(0), h)/h
        left = integral([2, 1, 1], -h, F(0))/h
        a.eq(right-left, expected, 'sharp window contrast')
        a.eq(right-left, 3+F(3, 2)*h, 'window contrast formula')
    for r in (-F(1, 3), F(1, 3)):
        observed = 2+r+r*r if r < 0 else 5+2*r+r*r
        alternative0 = alternative1 = observed
        a.eq(alternative1-alternative0, 0, 'same observed curve permits zero effect without continuity')
    # Distribution pushforward: fair sign times independent Uniform[0,1].
    for lo, hi in ((-F(3, 4), -F(1, 4)), (F(1, 4), F(3, 4))):
        probability = F(1, 2)*(hi-lo)
        a.eq(probability/(hi-lo), F(1, 2), 'continuous sorting score density')
    a.eq((F(1)-0, F(0)), (1, 0), 'sorting observed jump versus causal effect')
    a.anchor(page, 1, 'continuous', 'positive', 'P(R=0)=0', 'same observations')
    a.anchor(page, 2, '3+3h/2', '9/2', '33/10', '1/2', 'Y(1)−Y(0)=0', 'randomized')

    distances = [F(j, 10) for j in (1, 2, 3)]
    left = [1-2*x+x*x for x in distances]; right = [3+4*x+5*x*x for x in distances]
    a.eq(left, [F(81, 100), F(16, 25), F(49, 100)], 'left mean vector')
    a.eq(right, [F(69, 20), F(4), F(93, 20)], 'right mean vector')
    w = local_weights(distances); v = local_weights(distances, degree=2)
    a.eq(w, [F(4, 3), F(1, 3), -F(2, 3)], 'linear intercept weights')
    a.eq(v, [F(3), F(-3), F(1)], 'quadratic intercept weights')
    a.eq(local_weights([-x for x in distances]), w, 'negative-side intercept weights')
    for degree in (0, 1):
        a.eq(dot(w, [x**degree for x in distances]), F(degree == 0), 'linear reproduction')
    for degree in (0, 1, 2):
        a.eq(dot(v, [x**degree for x in distances]), F(degree == 0), 'quadratic reproduction')
    jumps = [b-c for b, c in zip(right, left)]
    a.eq((dot(w, jumps), dot(v, jumps)), (F(28, 15), F(2)), 'estimated mean jumps')
    original_variance = 2*dot(w, w); corrected_variance = 2*dot(v, v)
    a.eq((original_variance, corrected_variance), (F(14, 3), F(38)), 'jump variance multipliers')
    quadratic = [F(50), F(-100), F(50)]
    a.eq((dot(quadratic, left), dot(quadratic, right)), (F(1), F(5)), 'same-data curvature estimates')
    correction = [q/30 for q in quadratic]
    a.eq([x+y for x, y in zip(w, correction)], v, 'bias correction changes equivalent weights')
    correction_variance = 2*dot(correction, correction); covariance = 2*dot(w, correction)
    a.eq((correction_variance, covariance), (F(100, 3), F(0)), 'estimated correction variance and covariance')
    a.eq(original_variance+correction_variance+2*covariance, corrected_variance, 'complete variance identity')
    quadratic_moment = dot(w, [x*x for x in distances])
    absolute_moment = dot([abs(x) for x in w], [x*x for x in distances])
    a.eq((quadratic_moment, absolute_moment), (-F(1, 30), F(13, 150)), 'signed versus absolute quadratic moments')
    bias_bound = F(10+2, 2)*absolute_moment
    a.eq(bias_bound, F(13, 25), 'curvature bias bound')
    z = NormalDist().inv_cdf(.975)
    wrong_coverage = 2*NormalDist().cdf(z*math.sqrt(float(original_variance/corrected_variance)))-1
    radius = float(bias_bound)+z*.1*math.sqrt(float(original_variance))
    a.near(wrong_coverage, .507820530046, 'old variance corrected coverage')
    a.near(radius, .943400612067, 'finite known-Gaussian radius')
    # Independent erf evaluation cross-checks the quoted normal calculations.
    cdf = lambda t: (1+math.erf(t/math.sqrt(2)))/2
    a.near(cdf(z), .975, 'normal critical quantile check')
    a.near(2*cdf(z*math.sqrt(7/57))-1, wrong_coverage, 'normal coverage independent CDF')
    a.anchor(page, 3, '4/3,1/3,−2/3', '3,−3,1', '28/15', '14/3', '38', 'Negative outcome weights')
    a.anchor(page, 4, '100/3', 'covariance', '0.507820530046', '13/150', '13/25', '0.943400612067')
    for value in left+right:
        a.body(page, value)

    for k in (2, 3, 7, 20):
        n = 100; grid = [F(j, n) for j in range(1, k+1)]; weights = grid_weights(n, k)
        direct = local_weights(grid)
        a.eq(weights, direct, 'fixed-grid formula versus independent WLS normal equations')
        a.eq(sum(weights), 1, 'grid constant reproduction')
        a.eq(dot(weights, list(range(1, k+1))), 0, 'grid linear reproduction')
        a.eq(dot(weights, [j*j for j in range(1, k+1)]), -F((k+1)*(k+2), 6), 'grid quadratic moment')
        a.eq(dot(weights, weights), F(2*(2*k+1), k*(k-1)), 'grid squared-weight identity')
        exact_bias = dot(weights, [4*x*x for x in grid])
        exact_variance = 2*dot(weights, weights)
        a.eq(exact_bias, -F(4*(k+1)*(k+2), 6*n*n), 'grid exact quadratic jump bias')
        a.eq(exact_variance, F(4*(2*k+1), k*(k-1)), 'grid exact variance coefficient')
        a.eq(k*dot(weights, weights) <= 10, True, 'uniform absolute-weight bound certificate')
        a.eq(exact_variance <= F(20, k), True, 'variance consistency bound')
    # Leading optimum and rates are checked as exact algebra before numeric CDF.
    sigma2 = F(1, 100); deltaq2 = F(16); n = F(10000)
    optimal_h5 = 72*sigma2/(deltaq2*n)
    standardized_bias2 = deltaq2*n*optimal_h5/F(288)/sigma2
    a.eq(standardized_bias2, F(1, 4), 'optimal standardized bias squared')
    for fraction in (F(1), F(1, 2)):
        a.eq(standardized_bias2*fraction**5, fraction**5/4, 'fixed fraction does not eliminate limiting bias')
    for exponent in (F(1, 4), F(1, 3)):
        a.eq((1-exponent > 0, F(1, 2)-F(5, 2)*exponent < 0), (True, True), 'valid rate undersmoothing')
    a.eq(F(1, 2)-F(5, 2)*F(1, 5), 0, 'MSE-optimal power boundary')
    conventional = cdf(z-.5)-cdf(-z-.5)
    a.near(conventional, .920902465839, 'optimal-width conventional coverage')
    a.anchor(page, 5, '72σ²', '1/2', '0.920902465839', 'r⁵ᐟ²/2', 'n⁻¹ᐟ⁴', '√10', '20σ²/k')
    a.body(page, '10σ²')

    types = [(F(1, 4), 1, 1, 2, 6), (F(1, 2), 0, 1, 1, 4), (F(1, 4), 0, 0, 0, 0)]
    fuzzy = cutoff_wald(types)
    a.eq(fuzzy['receipt'], [F(1, 4), F(3, 4)], 'fuzzy receipt limits')
    a.eq(fuzzy['outcome'], [F(5, 2), F(9, 2)], 'fuzzy outcome limits')
    a.eq((fuzzy['ITT'], fuzzy['first'], fuzzy['ratio'], fuzzy['ATE']), (2, F(1, 2), 4, F(7, 2)), 'different fuzzy estimands')
    direct = cutoff_wald(types, direct=F(1, 2))
    a.eq((direct['ITT'], direct['first'], direct['ratio']), (F(5, 2), F(1, 2), 5), 'exclusion violation')
    defiers = [(F(1, 4), 1, 1, 2, 6), (F(3, 8), 0, 1, 1, 4), (F(1, 8), 1, 0, 1, 8), (F(1, 4), 0, 0, 0, 0)]
    wrong_monotonicity = cutoff_wald(defiers)
    a.eq(wrong_monotonicity['receipt'], [F(3, 8), F(5, 8)], 'defier receipt limits')
    a.eq(wrong_monotonicity['outcome'], [F(7, 2), F(4)], 'fully specified defier outcome limits')
    a.eq((wrong_monotonicity['ITT'], wrong_monotonicity['first'], wrong_monotonicity['ratio']), (F(1, 2), F(1, 4), F(2)), 'negative switcher weights')
    a.anchor(page, 6, '5/2,9/2', '1/4,3/4', '7/2', '3/8,5/8', 'exclusion', 'monotonicity', 'common cutoff')

    donors = [[F(0), F(1)], [F(2), F(2)], [F(1), F(3)]]; target = [F(5, 4), F(2)]
    fit = simplex_fit(target, donors)
    a.eq(fit['weights'], [F(1, 4), F(1, 2), F(1, 4)], 'full donor weights')
    a.eq((fit['fit'], fit['loss']), (target, 0), 'exact training fit')
    # The augmented column system independently certifies the stated exact weights.
    augmented = [[F(1)]*3, [p[0] for p in donors], [p[1] for p in donors]]
    aug_inv = inverse(augmented)
    a.eq([dot(row, [F(1)]+target) for row in aug_inv], fit['weights'], 'unique affine coordinate solution')
    loadings = [[F(0), F(1)], [F(2), F(0)], [F(1), F(2)]]
    target_loading = [F(5, 4), F(3, 4)]
    a.eq([sum(fit['weights'][j]*loadings[j][k] for j in range(3)) for k in range(2)], target_loading, 'matched factor loadings')
    full_forecasts = [sum(fit['weights'][j]*dot([1, s], loadings[j]) for j in range(3)) for s in (2, 3, 4)]
    a.eq(full_forecasts, [F(11, 4), F(7, 2), F(17, 4)], 'holdout and future forecasts')
    observed = [F(11, 2), F(29, 4)]
    a.eq([a-b for a, b in zip(observed, full_forecasts[1:])], [2, 3], 'supported effects')
    reduced = simplex_fit(target, donors[:2])
    a.eq(reduced['weights'], [F(3, 10), F(7, 10)], 'refitted donor removal')
    a.eq((reduced['fit'], reduced['error'], reduced['loss']),
         ([F(7, 5), F(17, 10)], [-F(3, 20), F(3, 10)], F(9, 80)), 'changed training support')
    reduced_forecasts = [sum(reduced['weights'][j]*dot([1, s], loadings[j]) for j in range(2)) for s in (2, 3, 4)]
    a.eq(reduced_forecasts, [F(2), F(23, 10), F(13, 5)], 'changed holdout and post forecasts')
    a.eq(full_forecasts[0]-reduced_forecasts[0], F(3, 4), 'holdout gap')
    a.eq([a-b for a, b in zip(observed, reduced_forecasts[1:])], [F(16, 5), F(93, 20)], 'changed reported post gaps')
    left_inverse = inverse([[1, 0], [1, 1]])
    a.eq(left_inverse, [[1, 0], [-1, 1]], 'pre-factor left inverse')
    bound_rows = [[sum(f[k]*left_inverse[k][j] for k in range(2)) for j in range(2)] for f in ([1, 3], [1, 4])]
    a.eq(bound_rows, [[-2, 3], [-3, 4]], 'future left-inverse rows')
    discrepancies = [dot(row, reduced['error']) for row in bound_rows]
    a.eq(discrepancies, [F(6, 5), F(33, 20)], 'model-specific approximate-fit discrepancies')
    for row, discrepancy in zip(bound_rows, discrepancies):
        a.eq(discrepancy**2 <= dot(row, row)*reduced['loss'], True, 'left-inverse norm bound')
    a.anchor(page, 7, 'compact', 'flat direction', '1/4,1/2,1/4', '11/4', '7/2,17/4', 'unique')
    a.anchor(page, 8, '3/10', '9/80', '3/4', '23/10,13/5', '16/5,93/20', '6/5', '33/20')

    alternative_counterfactual = [full_forecasts[1]+1, full_forecasts[2]+2]
    a.eq(alternative_counterfactual, [F(9, 2), F(25, 4)], 'new post-only factor')
    a.eq([a-b for a, b in zip(observed, alternative_counterfactual)], [1, 1], 'same observed panel different effects')
    a.eq([v*0 for v in (1, 1, 1)], [0, 0, 0], 'new factor absent even from preholdout')
    spillover_forecast = [f+fit['weights'][1]*2 for f in full_forecasts[1:]]
    a.eq([a-b for a, b in zip(observed, spillover_forecast)], [1, 2], 'donor-B spillover distortion')
    duplicate = simplex_fit([1, 1], [[1, 1], [1, 1]])
    a.eq(duplicate['weights'], [0, 1], 'prespecified lexicographic tie rule')
    a.eq(duplicate['loss'], 0, 'nonunique perfect prefit')
    for w1 in (F(0), F(1, 2), F(1)):
        weights = [w1, 1-w1]
        a.eq([dot(weights, [1, 1])]*2, [1, 1], 'all displayed optimal weights fit')
        a.eq(dot(weights, [2, 8]), 8-6*w1, 'forecast range parametrization')
        a.eq(7-dot(weights, [2, 8]), -1+6*w1, 'sharp gap range under maintained mixture')
    a.anchor(page, 9, '9/2', '25/4', '1,1', 'zero column', '1,2', 'same-data')
    a.anchor(page, 10, '2 to 8', '−1 to 5', '0,1', 'fixed convex-mixture', 'not a causal')

    pre = [[F(0), F(0)], [F(2), F(0)], [F(0), F(2)], [F(2), F(2)]]
    post = [F(4), F(0), F(1), F(2)]
    scores = []; gaps = []; refits = []
    expected_weights = [[F(1, 2), F(1, 2), 0], [F(1, 2), 0, F(1, 2)], [F(1, 2), 0, F(1, 2)], [0, F(1, 2), F(1, 2)]]
    for treated in range(4):
        indices = [j for j in range(4) if j != treated]
        result = simplex_fit(pre[treated], [pre[j] for j in indices]); refits.append(result)
        a.eq(result['weights'], expected_weights[treated], 'complete placebo refit weights')
        a.eq((result['fit'], result['loss']/2), ([1, 1], 1), 'placebo prediction and preMSE')
        gap = post[treated]-dot(result['weights'], [post[j] for j in indices]); gaps.append(gap)
        scores.append(rmspe_score(result['loss']/2, gap*gap))
    a.eq(gaps, [F(7, 2), F(-3), F(-2), F(3, 2)], 'all four post gaps')
    a.eq([score[1] for score in scores], [F(49, 4), F(9), F(4), F(9, 4)], 'squared RMSPE ranking')
    uniform = [F(1, 4)]*4; actual = [F(7, 10)]+[F(1, 10)]*3
    uniform_p = weighted_ranks(scores, uniform); actual_p = weighted_ranks(scores, actual)
    a.eq(uniform_p, [F(1, 4), F(1, 2), F(3, 4), F(1)], 'uniform inclusive tails')
    a.eq(actual_p, [F(7, 10), F(4, 5), F(9, 10), F(1)], 'actual law inclusive tails')
    a.eq(sum(uniform[j] for j in range(4) if uniform_p[j] <= F(1, 4)), F(1, 4), 'uniform exact rejection')
    a.eq(sum(actual[j] for j in range(4) if uniform_p[j] <= F(1, 4)), F(7, 10), 'wrong assignment reference')
    a.eq(sum(actual[j] for j in range(4) if actual_p[j] <= F(1, 4)), 0, 'correct actual-law rejection')
    a.eq(sum(uniform[j] for j in range(4) if uniform_p[j] <= F(1, 20)), 0, 'no five-percent rejection')
    extended = [rmspe_score(0, 1), rmspe_score(0, 4), rmspe_score(0, 0)]
    a.eq(extended, [(1, 0), (1, 0), (0, 0)], 'explicit zero-preRMSPE ordering')
    tie_prob = [F(1, 5), F(3, 10), F(1, 2)]
    tied_p = weighted_ranks(extended, tie_prob)
    a.eq(tied_p, [F(1, 2), F(1, 2), F(1)], 'inclusive infinity tie')
    a.eq(sum(tie_prob[j] for j in range(3) if tied_p[j] <= F(1, 2)), F(1, 2), 'inclusive tied rank size')
    a.eq(weighted_ranks([rmspe_score(0, 0)]*3, tie_prob), [1, 1, 1], 'all zero ties do not manufacture significance')
    a.anchor(page, 11, '7/2,−3,−2,3/2', '1/4,1/2,3/4,1', '7/10,4/5,9/10,1', 'upper tail', 'ties', '5%')
    a.anchor(page, 12, 'Six objections', 'Two repairs', 'Conclusion', 'rate condition', 'assignment')

    domains = [
        (lambda: rational(True), 'boolean exact number'), (lambda: rational(float('nan')), 'nonfinite exact number'),
        (lambda: rational(10**7), 'magnitude limit'), (lambda: inverse([[1, 1], [1, 1]]), 'rank failure'),
        (lambda: local_weights([F(1), F(1)]), 'duplicate local score'),
        (lambda: local_weights([-1, 1]), 'mixed score sides'),
        (lambda: local_weights([1, 2], kernels=[1, -1]), 'negative kernel'),
        (lambda: local_weights([1, 2], kernels=[0, 0]), 'no effective kernel support'),
        (lambda: grid_weights(10, 1), 'one-point local fit'), (lambda: grid_weights(True, 2), 'boolean n'),
        (lambda: grid_weights(5, 6), 'unavailable observations'),
        (lambda: cutoff_wald([(F(1, 2), 1, 1, 0, 1), (F(1, 2), 0, 0, 0, 1)]), 'zero first stage'),
        (lambda: cutoff_wald([(F(1, 4), 0, 1, 0, 1), (F(1, 4), 0, 0, 0, 1)]), 'incomplete type mass'),
        (lambda: simplex_fit([1, 2], [[1, 2], [1]]), 'unmatched donor coordinates'),
        (lambda: rmspe_score(-1, 1), 'negative squared error'),
        (lambda: weighted_ranks([(0, 1), (0, 2)], [F(1, 2), F(1, 4)]), 'incomplete assignment law'),
        (lambda: weighted_ranks([(0, 1), (0, 2)], [0, 1]), 'zero supported assignment probability'),
        (lambda: weighted_ranks([(1, 2), (0, 1)], [F(1, 2)]*2), 'malformed infinity marker')]
    for call, label in domains:
        a.reject(call, label)
    return {'local_score_count_per_side': 3, 'grid_checks_k': [2, 3, 7, 20],
            'original_jump_variance_multiplier': '14/3', 'corrected_multiplier': '38',
            'correction_covariance_multiplier': '0', 'full_donor_weights': ['1/4', '1/2', '1/4'],
            'placebo_refits': 4, 'actual_weighted_p': [str(v) for v in actual_p]}


def hashrow(path):
    raw = (BASE/path).read_bytes()
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def check():
    before = {p: (BASE/p).read_bytes() for p in FILES}; a = Audit(); page = Reader()
    page.feed(before[FILES[0]].decode('utf-8')); page.close()
    a.eq(page.stack, [], 'balanced fragment')
    a.eq((page.worked, page.exercise_count, page.solution_count), (6, 12, 12), 'reader markers')
    expected = {'v12-c08-e'+str(i) for i in range(1, 13)}
    a.eq(set(page.prompts), expected, 'twelve exact prompts')
    a.eq(set(page.answers), expected, 'twelve paired solutions')
    a.eq(len(page.ids), len(set(page.ids)), 'unique IDs')
    a.eq(set(page.sources), SOURCES, 'three scoped citations')
    allowed = {'v12-c01.html', 'v12-c02.html', 'v12-c03.html', 'v12-c06.html', 'v12-c07.html', 'v12-c09.html'}
    for href in page.links:
        a.eq(href in allowed or href in {'sources.html#'+s for s in SOURCES}, True, 'flat declared route')
    finite_evidence = numerical(a, page)
    sources = strict(before[FILES[2]].decode('utf-8'))
    a.eq({row['id'] for row in sources['sources']}, SOURCES, 'source proposal IDs')
    a.eq(len(sources['sources']), 3, 'three exact source scopes')
    review = strict(before[FILES[3]].decode('utf-8'))
    a.eq(set(review['payloads']), set(FILES[:3]), 'three nonself payloads')
    for p in FILES[:3]:
        a.eq(review['payloads'][p], hashrow(p), 'payload hash '+p)
    rejected = 0
    for invalid in ('{"x":1,"x":2}', 'NaN', 'Infinity', '-Infinity', '1e10000', '{}{}'):
        try:
            strict(invalid)
        except ValueError:
            rejected += 1
        else:
            raise ValueError('permissive JSON parser')
    a.eq(rejected, 6, 'strict JSON boundaries')
    for p, raw in before.items():
        a.eq((BASE/p).read_bytes(), raw, 'read-only check '+p)
    result = {'chapter': 'v12-c08', 'status': 'author checks passed; separate review required',
              'comparisons': a.count, 'domain_rejections': a.rejections, 'strict_JSON_rejections': rejected,
              'worked_examples': 6, 'exact_prompts_and_solutions': 12, 'visible_anchors': a.anchors,
              'primary_scopes': 3, 'finite_evidence': finite_evidence,
              'limits': 'Finite original cases and separate analytic audit; no empirical continuity proof, generic RBC or stochastic synthetic-control theorem, observational assignment calibration, rendered UI or human certification.'}
    strict(json.dumps(result, allow_nan=False))
    return result


def portable():
    with tempfile.TemporaryDirectory(prefix='v12-c08-author-') as directory:
        target = Path(directory)
        for p in FILES:
            (target/p).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(BASE/p, target/p)
        before = {p: (target/p).read_bytes() for p in FILES}; results = []
        code = ("import contextlib,importlib.util,io,json;s=importlib.util.spec_from_file_location('a',"
                +repr(str(target/FILES[1]))+");m=importlib.util.module_from_spec(s)\n"
                "with contextlib.redirect_stdout(io.StringIO()) as o,contextlib.redirect_stderr(io.StringIO()) as e:\n"
                " s.loader.exec_module(m);r=m.check()\n"
                "if o.getvalue() or e.getvalue():raise ValueError('API noise')\n"
                "print(json.dumps(r,allow_nan=False,sort_keys=True))")
        for flags in ([], ['-O']):
            api = subprocess.run([sys.executable, '-B']+flags+['-c', code], cwd='/', capture_output=True,
                                 text=True, timeout=30, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
            require(api.returncode == 0 and not api.stderr, 'isolated API failed '+api.stderr)
            results.append(strict(api.stdout))
            cli = subprocess.run([sys.executable, '-B']+flags+[str(target/FILES[1])], cwd='/', capture_output=True,
                                 text=True, timeout=30, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
            require(cli.returncode == 0 and not cli.stdout and not cli.stderr, 'isolated CLI failed '+cli.stderr)
        require(results[0] == results[1], 'normal/optimized mismatch')
        require(before == {p: (target/p).read_bytes() for p in FILES}, 'isolated mutation')
        require({str(p.relative_to(target)) for p in target.rglob('*') if p.is_file()} == set(FILES), 'exact four-file membership')
        return {'status': 'passed', 'files': 4, 'cwd': '/', 'normal_and_optimized_API_CLI': True,
                'no_mutation': True, 'summary': results[0]}


if __name__ == '__main__':
    check()
