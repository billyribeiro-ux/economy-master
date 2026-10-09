"""Quiet, bounded exact checks for the four-file v12-c05 working package.

Finite calculations support the separate analytic audit; they are not proofs of
general identification, normal approximation, or empirical causal validity.
"""
from fractions import Fraction as F
from html.parser import HTMLParser
from pathlib import Path
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

BASE = Path(__file__).resolve().parent
FILES = ('v12-c05-working.html', 'check_v12_c05_working.py',
         'v12-c05-sources-working.json', 'v12-c05-author-review-working.json')
SOURCES = {'v12-c05-mit-panel2017', 'v12-c05-imbens-wooldridge-panel2014',
           'v12-c05-arellano-predetermined2009', 'v12-c05-wooldridge-ipw2004'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def number(value):
    require(type(value) is int or isinstance(value, F), 'exact rational required')
    value = F(value)
    require(abs(value) <= 10**6, 'bounded rational required')
    return value


def strict(text):
    def pairs(rows):
        out = {}
        for key, value in rows:
            require(key not in out, 'duplicate JSON member')
            out[key] = value
        return out
    def invalid(value):
        raise ValueError('nonfinite JSON number: ' + value)
    def finite(value):
        result = float(value)
        require(math.isfinite(result), 'overflowed JSON number')
        return result
    return json.loads(text, object_pairs_hook=pairs, parse_constant=invalid,
                      parse_float=finite)


def mean(values):
    return sum(values, F()) / len(values)


def inverse(matrix):
    require(type(matrix) is list and 1 <= len(matrix) <= 3, 'matrix order 1..3')
    n = len(matrix)
    require(all(type(row) is list and len(row) == n for row in matrix), 'square matrix')
    a = [[number(v) for v in row] + [F(i == j) for j in range(n)]
         for i, row in enumerate(matrix)]
    for j in range(n):
        pivot = next((i for i in range(j, n) if a[i][j]), None)
        require(pivot is not None, 'singular matrix')
        a[j], a[pivot] = a[pivot], a[j]
        divisor = a[j][j]
        a[j] = [v/divisor for v in a[j]]
        for i in range(n):
            if i != j:
                multiple = a[i][j]
                a[i] = [v-multiple*w for v, w in zip(a[i], a[j])]
    return [row[n:] for row in a]


def within_fit(x, y, weights=None):
    require(type(x) is list and type(y) is list and 2 <= len(x) <= 64,
            'panel has 2..64 units')
    require(len(y) == len(x) and type(x[0]) is list and 2 <= len(x[0]) <= 4,
            'balanced panel has 2..4 dates')
    t = len(x[0]); n = len(x)
    require(all(type(row) is list and len(row) == t for row in x+y),
            'complete common balanced panel')
    x = [[number(v) for v in row] for row in x]
    y = [[number(v) for v in row] for row in y]
    if weights is None:
        weights = [F(1)]*n
    require(type(weights) is list and len(weights) == n, 'one weight per unit')
    w = [number(v) for v in weights]
    require(all(v > 0 for v in w), 'positive common unit weights')
    xt = [[v-mean(row) for v in row] for row in x]
    yt = [[v-mean(row) for v in row] for row in y]
    h = [sum(v*v for v in row) for row in xt]
    cross = [sum(v*z for v, z in zip(row, other)) for row, other in zip(xt, yt)]
    gram = sum(a*b for a, b in zip(w, h))
    require(gram > 0, 'within rank failure')
    slope = sum(a*b for a, b in zip(w, cross))/gram
    scores = [w[i]*(cross[i]-h[i]*slope) for i in range(n)]
    q = gram/n; meat = mean([v*v for v in scores])
    return {'slope': slope, 'Q': q, 'meat': meat, 'root_variance': meat/q**2,
            'within_x': xt, 'within_y': yt, 'scores': scores}


def compound(t, su, sa):
    require(type(t) is int and 2 <= t <= 4, 'T is integer 2..4')
    su = number(su); sa = number(sa)
    require(su > 0 and sa >= 0, 'positive idiosyncratic and nonnegative effect variance')
    omega = [[su*F(i == j)+sa for j in range(t)] for i in range(t)]
    weight = [[F(i == j)/su-sa/(su*(su+t*sa)) for j in range(t)] for i in range(t)]
    theta = 1-math.sqrt(float(su/(su+t*sa)))
    return omega, weight, theta


def scalar_iv(x, y, z):
    require(all(type(v) is list for v in (x, y, z)) and 2 <= len(x) <= 64,
            'IV sample has 2..64 units')
    require(len(y) == len(x) == len(z), 'common IV sample')
    x, y, z = ([number(v) for v in row] for row in (x, y, z))
    denominator = sum(a*b for a, b in zip(x, z))
    require(denominator != 0, 'zero sample IV denominator')
    return sum(a*b for a, b in zip(y, z))/denominator


def dynamic(rho, feedback=False):
    rho = number(rho)
    require(-2 <= rho <= 2 and type(feedback) is bool, 'bounded rho and boolean mechanism')
    rows = []
    for e1, e2, independent_e3 in itertools.product((-1, 1), repeat=3):
        e3 = e1 if feedback else independent_e3
        y1 = F(e1); y2 = rho*y1+e2; y3 = rho*y2+e3
        rows.append((F(1, 8), {'y1': y1, 'y2': y2, 'y3': y3,
                              'FE': y2/y1-1, 'x': y2-y1, 'y': y3-y2,
                              'B': y1*(y2-y1), 'A': y1*(y3-y2),
                              'g': y1*(e3-e2), 'de2': e2-e1, 'de3': e3-e2}))
    return rows


def expectation(rows, function):
    return sum(p*function(row) for p, row in rows)


def attrition(p1):
    p1 = number(p1)
    require(0 < p1 <= 1, 'positive response probability at most one')
    rows = []
    for h, v, r in itertools.product((0, 1), (-1, 1), (0, 1)):
        p = F(1) if h == 0 else p1
        probability = F(1, 4)*(p if r else 1-p)
        if probability:
            mu = F(2+4*h); y = mu+v
            rows.append((probability, {'h': h, 'r': r, 'y': y, 'p': p,
                         'observed_y': y if r else None,
                         'fitted_IF': mu-4+r*(y-mu)/p, 'HT_IF': r*y/p-4,
                         'composition': mu-4, 'response_noise': r*(y-mu)/p,
                         'IF_difference': mu*(r/p-1)}))
    return rows


def cell_fit(rows):
    require(type(rows) is list and 2 <= len(rows) <= 64, 'cohort has 2..64 records')
    counts = [0, 0]; outcomes = [[], []]
    for row in rows:
        require(type(row) is tuple and len(row) == 3, 'record is (H,R,observed Y)')
        h, r, y = row
        require(type(h) is int and h in (0, 1) and type(r) is int and r in (0, 1),
                'binary integer cell and response flag')
        counts[h] += 1
        if r:
            outcomes[h].append(number(y))
        else:
            require(y is None, 'missing Y must be unavailable, not a numeric zero')
    require(all(outcomes), 'response-empty cell: estimate unavailable')
    n = len(rows); shares = [F(v, n) for v in counts]
    p = [F(len(outcomes[h]), counts[h]) for h in (0, 1)]
    mu = [mean(row) for row in outcomes]
    fitted = sum(a*b for a, b in zip(shares, mu))
    variances = [mean([(y-mu[h])**2 for y in outcomes[h]]) for h in (0, 1)]
    root_variance = sum(shares[h]*((mu[h]-fitted)**2+variances[h]/p[h]) for h in (0, 1))
    ipw = sum(F(r)*number(y)/p[h] for h, r, y in rows if r)/n
    return {'mean': fitted, 'root_variance': root_variance, 'IPW': ipw,
            'probabilities': p, 'cell_means': mu}


def normalize(text):
    return re.sub(r'\s+', '', text).replace('−', '-')


class Reader(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []; self.ids = []; self.sources = []; self.links = []
        self.worked = 0; self.prompts = {}; self.answers = {}; self.text = []
        self.exercise_count = 0; self.solution_count = 0
        self.captures = []; self.exercise_depth = None; self.solution_depth = None
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
                self.captures.append((len(self.stack), self.prompts, a.get('id'), []))
            if 'data-solution-for' in a:
                require(self.solution_depth is not None, 'paired answer outside solutions')
                self.solution_count += 1
                self.captures.append((len(self.stack), self.answers, a['data-solution-for'], []))
        if tag not in ('br', 'hr', 'img', 'meta', 'link', 'input'):
            self.stack.append(tag)
    def handle_endtag(self, tag):
        require(bool(self.stack) and self.stack[-1] == tag, 'unbalanced '+tag)
        depth = len(self.stack)-1
        if tag == 'li':
            for captured in list(self.captures):
                level, destination, key, chunks = captured
                if level == depth:
                    require(key and key not in destination, 'missing or duplicate exercise key')
                    destination[key] = ' '.join(chunks); self.captures.remove(captured)
        if tag == 'ol' and depth == self.exercise_depth:
            self.exercise_depth = None
        if tag == 'details' and depth == self.solution_depth:
            self.solution_depth = None
        self.stack.pop()
    def handle_data(self, value):
        self.text.append(value)
        for _, _, _, chunks in self.captures:
            chunks.append(value)


class Audit:
    def __init__(self):
        self.count = 0; self.rejections = 0; self.anchors = 0
    def eq(self, actual, expected, label):
        self.count += 1
        require(actual == expected, label+': '+repr(actual)+' != '+repr(expected))
    def near(self, actual, expected, label):
        self.count += 1
        require(math.isclose(actual, expected, rel_tol=2e-13, abs_tol=2e-13), label)
    def reject(self, call, label):
        self.count += 1
        try:
            call()
        except ValueError:
            self.rejections += 1
        else:
            raise ValueError('domain not rejected: '+label)
    def anchor(self, page, exercise, *values):
        text = normalize(page.answers['v12-c05-e'+str(exercise)])
        for value in values:
            self.eq(normalize(str(value)) in text, True, 'solution '+str(exercise)+' anchor '+str(value))
            self.anchors += 1


def numerical(a, page):
    # Different constructions: finite-law expectations versus centered regressions.
    rows = []
    for b, d, e1, e2 in itertools.product((-1, 1), repeat=4):
        x = [F(b-d), F(b+d)]; e = [F(e1), F(e2)]
        y = [b+2*v+u for v, u in zip(x, e)]
        rows.append((F(1, 16), {'b': b, 'd': d, 'x': x, 'y': y, 'e': e}))
    E = lambda fn: expectation(rows, fn)
    pooled_q = E(lambda r: sum(v*v for v in r['x']))
    pooled_xy = E(lambda r: sum(x*y for x, y in zip(r['x'], r['y'])))
    a.eq((pooled_q, pooled_xy, pooled_xy/pooled_q), (4, 10, F(5, 2)), 'pooled omitted effect target')
    fe = within_fit([r['x'] for _, r in rows], [r['y'] for _, r in rows])
    a.eq((fe['slope'], fe['Q'], fe['meat'], fe['root_variance']), (2, 2, 2, F(1, 2)), 'finite FE law')
    for i, (_, row) in enumerate(rows):
        a.eq(fe['scores'][i], row['d']*(row['e'][1]-row['e'][0]), 'score construction')
        a.eq(fe['within_x'][i], [-row['d'], row['d']], 'effect removal')
    a.eq(E(lambda r: r['d']*(r['e'][1]-r['e'][0])), 0, 'centered whole-unit score')
    a.eq(E(lambda r: r['d']**2*(r['e'][1]-r['e'][0])**2), 2, 'unit variance')
    # Exact two-unit sampling is 256 labeled states, not simulated evidence.
    estimate_law = [(p*q, 2+(r['d']*(r['e'][1]-r['e'][0])+s['d']*(s['e'][1]-s['e'][0]))/F(4))
                    for p, r in rows for q, s in rows]
    a.eq(sum(p*x for p, x in estimate_law), 2, 'exact finite N mean')
    a.eq(sum(p*(x-2)**2 for p, x in estimate_law), F(1, 4), 'exact N=2 variance')
    a.anchor(page, 1, 'rank', 'time-constant', 'fixed T', 'cᵢ+ūᵢ')
    a.anchor(page, 2, pooled_q, pooled_xy, F(5, 2), '1/(2N)', 'singular')

    omega, weight, theta = compound(2, 1, 1)
    a.eq(weight, inverse(omega), 'compound inverse from separate elimination')
    weighted = lambda x, y: sum(x[i]*weight[i][j]*y[j] for i in range(2) for j in range(2))
    req = E(lambda r: weighted(r['x'], r['x']))
    rea = E(lambda r: weighted(r['x'], [F(r['b'])]*2))
    rey = E(lambda r: weighted(r['x'], r['y']))
    a.eq((req, rea, rey, rey/req), (F(8, 3), F(2, 3), 6, F(9, 4)), 'working RE target')
    a.near(theta, 1-1/math.sqrt(3), 'RE quasi-demeaning factor')
    # Solve the full CRE population moment independently of the within helper.
    gram = [[E(lambda r: sum([F(1), r['x'][t], F(r['b'])][i]*[F(1), r['x'][t], F(r['b'])][j]
                          for t in range(2))) for j in range(3)] for i in range(3)]
    cross = [E(lambda r: sum([F(1), r['x'][t], F(r['b'])][i]*r['y'][t] for t in range(2))) for i in range(3)]
    inv = inverse(gram)
    a.eq([sum(inv[i][j]*cross[j] for j in range(3)) for i in range(3)], [0, 2, 1], 'population CRE equation')
    for t, su, sa in ((3, 4, 1), (2, 4, 0)):
        om, w, th = compound(t, su, sa)
        a.eq([[sum(om[i][k]*w[k][j] for k in range(t)) for j in range(t)] for i in range(t)],
             [[F(i == j) for j in range(t)] for i in range(t)], 'compound identity')
        transform = [[F(i == j)-th/t for j in range(t)] for i in range(t)]
        for i in range(t):
            for j in range(t):
                a.near(sum(transform[k][i]*transform[k][j] for k in range(t)), float(su*w[i][j]), 'A prime A')
    _, w, th = compound(3, 4, 1)
    a.eq([sum(row) for row in w], [F(1, 7)]*3, 'between inverse eigenvalue')
    a.eq([sum(row[j]*(-1, 0, 1)[j] for j in range(3)) for row in w], [-F(1, 4), 0, F(1, 4)], 'within eigenvalue')
    a.anchor(page, 4, '1−2/√7', 'I/4−11′/28', '1/7', 'x/4', 'θ=0', 'mean restriction')

    x = [[-2, 0], [-2, 2], [1, 3]]; y = [[-5, -3], [-3, 7], [7, 13]]; w = [1, 2, 1]
    sample = within_fit(x, y, w)
    # A direct full normal equation is the oracle for the split objective.
    design = [[F(1), F(x[i][t]), mean(x[i])] for i in range(3) for t in range(2)]
    response = [F(v) for row in y for v in row]; flatw = [v for v in w for _ in range(2)]
    gram = [[sum(flatw[k]*row[i]*row[j] for k, row in enumerate(design)) for j in range(3)] for i in range(3)]
    cross = [sum(flatw[k]*row[i]*response[k] for k, row in enumerate(design)) for i in range(3)]
    gi = inverse(gram); beta = [sum(gi[i][j]*cross[j] for j in range(3)) for i in range(3)]
    a.eq(beta, [F(26, 19), F(12, 5), F(202, 95)], 'full sample CRE coefficients')
    a.eq(sample['slope'], beta[1], 'sample FE CRE equality')
    between_x = [mean(row) for row in x]; between_y = [mean(row) for row in y]
    xb = sum(wi*xi for wi, xi in zip(w, between_x))/sum(w)
    yb = sum(wi*yi for wi, yi in zip(w, between_y))/sum(w)
    bg = sum(wi*(xi-xb)**2 for wi, xi in zip(w, between_x))
    bc = sum(wi*(xi-xb)*(yi-yb) for wi, xi, yi in zip(w, between_x, between_y))
    a.eq((xb, yb, bg, bc, bc/bg), (F(1, 4), F(5, 2), F(19, 4), F(43, 2), F(86, 19)), 'between calculation')
    # An off-fit candidate checks the entire objective decomposition, not just its optimizer.
    for aa, bb, dd in ((F(0), F(1), F(2)), (beta[0], beta[1], beta[2])):
        full = sum(w[i]*(y[i][t]-aa-bb*x[i][t]-dd*between_x[i])**2 for i in range(3) for t in range(2))
        split = sum(w[i]*((y[i][t]-between_y[i])-bb*(x[i][t]-between_x[i]))**2 for i in range(3) for t in range(2))
        split += 2*sum(w[i]*(between_y[i]-aa-(bb+dd)*between_x[i])**2 for i in range(3))
        a.eq(full, split, 'weighted objective orthogonality')
    a.anchor(page, 5, '20', '48', *beta, F(86, 19), F(19, 4), F(43, 2), 'same wᵢ', 'E[c|X]')

    seq = [(z, e1, e2) for z, e1, e2 in itertools.product((-1, 1), repeat=3)]
    a.eq(mean([F((e1-z)**2) for z, e1, e2 in seq]), 2, 'sequential Gram')
    a.eq(mean([F((e1-z)*(e2-e1)) for z, e1, e2 in seq]), -1, 'sequential transformed score')
    for z in (-1, 1):
        a.eq(mean([F(e1) for zz, e1, e2 in seq if zz == z]), 0, 'first sequential mean')
        for e1 in (-1, 1):
            a.eq(mean([F(e2) for zz, ee, e2 in seq if zz == z and ee == e1]), 0, 'second sequential mean')
            a.eq(mean([F(ee) for zz, ee, e2 in seq if zz == z and ee == e1]), e1, 'full history fails')
    a.anchor(page, 3, 'sequential', 'strict', '-1', '2', 'β−1/2')

    for rho, target_variance in ((F(1, 2), F(8)), (F(0), F(2)), (F(9, 10), F(200))):
        law = dynamic(rho); de = lambda fn: expectation(law, fn)
        a.eq(de(lambda r: r['FE']), rho-1, 'dynamic FE mean')
        a.eq(de(lambda r: (r['FE']-(rho-1))**2), 1, 'dynamic FE unit variance')
        b = de(lambda r: r['B']); aa = de(lambda r: r['A']); g = de(lambda r: r['g'])
        a.eq((b, aa, g), (rho-1, rho*(rho-1), 0), 'dynamic IV expectations')
        a.eq(de(lambda r: r['g']**2)/b**2, target_variance, 'dynamic IV root-N variance')
        a.eq(scalar_iv([r['x'] for _, r in law], [r['y'] for _, r in law], [r['y1'] for _, r in law]), rho, 'all-state IV ratio')
        a.eq(de(lambda r: r['de2']*r['de3']), -1, 'adjacent differenced error covariance')
    boundary = dynamic(1)
    a.eq(expectation(boundary, lambda r: r['B']), 0, 'population rank boundary')
    for proposed in (-1, 0, 1):
        a.eq(expectation(boundary, lambda r: r['A']-proposed*r['B']), 0, 'boundary moment flat in candidate')
    perturbed = dynamic(F(1, 2), feedback=True)
    a.eq(expectation(perturbed, lambda r: r['g']), 1, 'serial perturbation invalidates moment')
    a.eq(expectation(perturbed, lambda r: r['A']), F(3, 4), 'perturbed numerator')
    a.eq(scalar_iv([r['x'] for _, r in perturbed], [r['y'] for _, r in perturbed], [r['y1'] for _, r in perturbed]), -F(3, 2), 'invalid IV target')
    a.anchor(page, 6, '-1/2', '1/N', '-1/4', '2', '8', '−1', 'unit')
    a.anchor(page, 7, '200', '−1/10', '−3/2', '3/4', 'rank', 'past')

    for p1, respondent, fitted_var, ht_var in ((F(1, 3), F(3), F(6), F(42)), (F(1, 2), F(10, 3), F(11, 2), F(47, 2))):
        law = attrition(p1); ae = lambda fn: expectation(law, fn)
        a.eq(sum(p for p, _ in law), 1, 'complete attrition mass')
        a.eq((ae(lambda r: r['y']), ae(lambda r: (r['y']-4)**2)), (4, 5), 'cohort moments')
        a.eq(ae(lambda r: r['r']*r['y'])/ae(lambda r: r['r']), respondent, 'respondent target')
        a.eq(ae(lambda r: r['r']*r['y']/r['p']), 4, 'MAR weighted mean')
        a.eq(ae(lambda r: r['r']*r['y']**2/r['p']), 21, 'MAR second-moment identity')
        a.eq((ae(lambda r: r['fitted_IF']), ae(lambda r: r['HT_IF'])), (0, 0), 'centered influence pair')
        a.eq((ae(lambda r: r['fitted_IF']**2), ae(lambda r: r['HT_IF']**2)), (fitted_var, ht_var), 'different nuisance influences')
        a.eq(ae(lambda r: r['composition']*r['response_noise']), 0, 'composition/residual orthogonality')
        a.eq(ae(lambda r: r['fitted_IF']*r['IF_difference']), 0, 'HT/fitted variance difference orthogonality')
        a.eq(ae(lambda r: r['IF_difference']**2), ht_var-fitted_var, 'nonnegative variance difference')
        empty = F()
        for p, r in law:
            for q, s in law:
                seen = {v['h'] for v in (r, s) if v['r']}
                if len(seen) != 2:
                    empty += p*q
        formula = F(1, 2)**2+(1-p1/2)**2-((1-p1)/2)**2
        a.eq(empty, formula, 'exact N=2 empty-response probability')
        a.eq(empty, F(5, 6) if p1 == F(1, 3) else F(3, 4), 'finite positivity is not observed support')
    law = attrition(F(1, 3))
    a.eq(len(law), 6, 'latent atoms')
    observed = {(r['h'], r['r'], r['observed_y']) for _, r in law}
    a.eq(len(observed), 5, 'observable atoms merge missing outcomes')
    for missing, target in ((3, 3), (9, 5)):
        changed = [(p, dict(r, y=r['y'] if r['r'] else F(missing))) for p, r in law]
        a.eq(expectation(changed, lambda r: r['y']), target, 'non-MAR unidentified mean')
        a.eq({(r['h'], r['r'], r['y'] if r['r'] else None): sum(q for q, s in changed if (s['h'], s['r'], s['y'] if s['r'] else None) == (r['h'], r['r'], r['y'] if r['r'] else None)) for _, r in changed},
             {(r['h'], r['r'], r['observed_y']): sum(q for q, s in law if (s['h'], s['r'], s['observed_y']) == (r['h'], r['r'], r['observed_y'])) for _, r in law}, 'identical observable law')
    cohort = [(0, 1, 1), (0, 1, 3)]*3+[(1, 1, 5), (1, 1, 7)]+[(1, 0, None)]*4
    cf = cell_fit(cohort)
    a.eq((cf['mean'], cf['IPW'], cf['root_variance']), (4, 4, 6), 'fitted probabilities actual cohort')
    a.eq(cf['probabilities'], [F(1), F(1, 3)], 'cohort response estimates')
    cf2 = cell_fit([(0, 1, 1), (0, 1, 3)]*2+[(1, 1, 5), (1, 1, 7)]+[(1, 0, None)]*2)
    a.eq((cf2['mean'], cf2['root_variance']), (4, F(11, 2)), 'changed response cohort')
    a.anchor(page, 8, '6', '42', '36', 'μ_H−μ', 'baseline composition', 'delta')
    a.anchor(page, 9, F(10, 3), F(11, 2), F(47, 2), F(3, 4), '3', '5', 'identical observed')

    for n in (4, 8):
        q = [-1, -1, 1, 1]*(n//4); s = [-1, 1]
        x = [[F(qi*st) for st in s] for qi in q]
        for shock in (-1, 1):
            y = [[(2+shock)*v for v in row] for row in x]
            fit = within_fit(x, y)
            a.eq((fit['slope'], fit['meat']), (2+shock, 0), 'common shock fitted slope and false meat')
            u = [[shock*v for v in row] for row in x]
            for matrix in (x, u):
                gm = mean([v for row in matrix for v in row])
                tw = [[matrix[i][t]-mean(matrix[i])-mean([row[t] for row in matrix])+gm for t in range(2)] for i in range(n)]
                a.eq(tw, matrix, 'two-way demeaning cannot remove centered heterogeneous factor')
            g = [sum(x[i][t]*u[i][t] for t in range(2)) for i in range(n)]
            a.eq(g, [F(2*shock)]*n, 'whole-unit common score')
            a.eq(mean(g)**2, 4, 'average score variance remains four')
            homogeneous = [[F(st*shock) for st in s] for _ in q]
            a.eq([[homogeneous[i][t]-mean([r[t] for r in homogeneous]) for t in range(2)] for i in range(n)], [[0, 0] for _ in q], 'homogeneous time shock removed')
    a.anchor(page, 10, '2+U', 'variance 4', 'zero', 'Var(β̂−2)=1', 'conditional projection')
    a.anchor(page, 11, 'O_p(1)', 'δ=o_p(1)', 'Divide by N', 'a′Va>0', 'LLN')
    a.anchor(page, 12, 'Six distinctions', 'Two changes', 'Conclusion', 'eight firms', 'causal')

    domains = [
        (lambda: number(True), 'boolean number'), (lambda: number(float('nan')), 'nonfinite float'),
        (lambda: number(10**7), 'magnitude bound'), (lambda: inverse([[1, 1], [1, 1]]), 'singular matrix'),
        (lambda: within_fit([[1, 1], [2, 2]], [[1, 2], [2, 3]]), 'time-invariant regressor'),
        (lambda: within_fit([[1, 2], [1]], [[1, 2], [2, 3]]), 'unbalanced panel'),
        (lambda: within_fit([[1, 2], [1, 2]], [[1, 2], [1, 2]], [1, 0]), 'zero weight'),
        (lambda: compound(True, 1, 1), 'boolean T'), (lambda: compound(2, 0, 1), 'zero innovation variance'),
        (lambda: compound(2, 1, -1), 'negative effect variance'), (lambda: dynamic(3), 'rho outside bounded evidence'),
        (lambda: scalar_iv([1, -1], [1, 2], [1, 1]), 'zero sample IV rank'),
        (lambda: attrition(0), 'zero response support'), (lambda: attrition(F(3, 2)), 'invalid probability'),
        (lambda: cell_fit([(0, 1, 1), (1, 0, None)]), 'empty respondent cell'),
        (lambda: cell_fit([(0, 1, 1), (1, 0, 0)]), 'fabricated missing zero'),
        (lambda: cell_fit([(True, 1, 1), (1, 1, 5)]), 'boolean baseline cell')]
    for call, label in domains:
        a.reject(call, label)
    return {'finite_FE_states': 16, 'exact_two_unit_FE_states': 256,
            'dynamic_states_per_law': 8, 'attrition_latent_atoms': 6,
            'attrition_observed_atoms': 5, 'common_shock_unit_counts': [4, 8],
            'sample_CRE': [str(v) for v in beta]}


def hashrow(path):
    raw = (BASE/path).read_bytes()
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def check():
    before = {p: (BASE/p).read_bytes() for p in FILES}
    a = Audit(); page = Reader(); page.feed(before[FILES[0]].decode('utf-8')); page.close()
    a.eq(page.stack, [], 'balanced HTML fragment')
    a.eq((page.worked, page.exercise_count, page.solution_count), (6, 12, 12), 'reader markers')
    expected = {'v12-c05-e'+str(i) for i in range(1, 13)}
    a.eq(set(page.prompts), expected, 'twelve exact prompts')
    a.eq(set(page.answers), expected, 'twelve exact paired answers')
    a.eq(len(page.ids), len(set(page.ids)), 'unique IDs')
    a.eq(set(page.sources), SOURCES, 'four scoped primary citations')
    for href in page.links:
        a.eq(href in {'v12-c01.html', 'v12-c02.html', 'v12-c03.html', 'v12-c04.html', 'v12-c06.html'}
             or href in {'sources.html#'+s for s in SOURCES}, True, 'flat recognized route syntax')
    evidence = numerical(a, page)
    sources = strict(before[FILES[2]].decode('utf-8'))
    a.eq({r['id'] for r in sources['sources']}, SOURCES, 'source proposal identities')
    a.eq(len(sources['sources']), 4, 'exact source count')
    review = strict(before[FILES[3]].decode('utf-8'))
    a.eq(set(review['payloads']), set(FILES[:3]), 'three nonself author bindings')
    for p in FILES[:3]:
        a.eq(review['payloads'][p], hashrow(p), 'bound payload '+p)
    json_rejections = 0
    for invalid in ('{"a":1,"a":2}', 'NaN', 'Infinity', '-Infinity', '1e10000', '{}{}'):
        try:
            strict(invalid)
        except ValueError:
            json_rejections += 1
        else:
            raise ValueError('permissive JSON parsing')
    a.eq(json_rejections, 6, 'strict JSON boundaries')
    for path, raw in before.items():
        a.eq((BASE/path).read_bytes(), raw, 'check does not mutate '+path)
    result = {'chapter': 'v12-c05', 'status': 'author checks passed; separate review required',
              'comparisons': a.count, 'domain_rejections': a.rejections,
              'strict_JSON_rejections': json_rejections, 'worked_examples': 6,
              'exact_prompts_and_solutions': 12, 'paired_anchors': a.anchors,
              'primary_scopes': 4, 'finite_evidence': evidence,
              'limitations': 'Finite exact calculations and separate analytic review; no empirical validation, general dynamic or interactive-factor theorem, uniform coverage, rendered UI or human certification.'}
    strict(json.dumps(result, allow_nan=False))
    return result


def portable():
    with tempfile.TemporaryDirectory(prefix='v12-c05-author-') as directory:
        target = Path(directory)
        for path in FILES:
            shutil.copy2(BASE/path, target/path)
        before = {p: (target/p).read_bytes() for p in FILES}; results = []
        code = ("import contextlib,importlib.util,io,json;"
                "s=importlib.util.spec_from_file_location('author',"+repr(str(target/FILES[1]))+");"
                "m=importlib.util.module_from_spec(s)\n"
                "with contextlib.redirect_stdout(io.StringIO()) as o,contextlib.redirect_stderr(io.StringIO()) as e:\n"
                " s.loader.exec_module(m);r=m.check()\n"
                "if o.getvalue() or e.getvalue():raise ValueError('nonquiet import/check')\n"
                "print(json.dumps(r,allow_nan=False,sort_keys=True))")
        for flags in ([], ['-O']):
            api = subprocess.run([sys.executable, '-B']+flags+['-c', code], cwd='/',
                                 capture_output=True, text=True, timeout=30,
                                 env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
            require(api.returncode == 0 and not api.stderr, 'isolated API failed: '+api.stderr)
            results.append(strict(api.stdout))
            cli = subprocess.run([sys.executable, '-B']+flags+[str(target/FILES[1])], cwd='/',
                                 capture_output=True, text=True, timeout=30,
                                 env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
            require(cli.returncode == 0 and not cli.stdout and not cli.stderr, 'isolated CLI failure: '+cli.stderr)
        require(results[0] == results[1], 'optimized mismatch')
        require(before == {p: (target/p).read_bytes() for p in FILES}, 'isolated mutation')
        require({p.name for p in target.iterdir()} == set(FILES), 'exact four-file membership')
        return {'status': 'passed', 'files': 4, 'cwd': '/', 'normal_and_optimized_API_CLI': True,
                'no_mutation': True, 'summary': results[0]}


if __name__ == '__main__':
    check()
