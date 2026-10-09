"""Quiet four-file finite-design evidence for v12-c07; standard library only."""
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
FILES = ('content/chapters/v12-c07.html', 'scripts/check_v12_c07.py',
         'content/reviews/v12-c07-sources.json', 'content/reviews/v12-c07-author.json')
SOURCES = {'v12-c07-callaway-santanna2020', 'v12-c07-sun-abraham2020',
           'v12-c07-goodman-bacon2020', 'v12-c07-rambachan-roth2023'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def rational(value):
    require(type(value) is int or isinstance(value, F), 'exact rational required')
    value = F(value)
    require(abs(value) <= 10**6, 'bounded rational required')
    return value


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


def average(row):
    return sum(row, F())/len(row)


def transpose(a):
    return [list(row) for row in zip(*a)]


def multiply(a, b):
    return [[sum(x*y for x, y in zip(row, col)) for col in transpose(b)] for row in a]


def inverse(matrix):
    require(type(matrix) is list and 1 <= len(matrix) <= 11, 'matrix order 1..11')
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
                factor = a[i][j]
                a[i] = [v-factor*w for v, w in zip(a[i], a[j])]
    return [row[n:] for row in a]


def two_way(table):
    require(type(table) is list and 2 <= len(table) <= 4, '2..4 groups')
    require(type(table[0]) is list and 2 <= len(table[0]) <= 5, '2..5 dates')
    n = len(table); t = len(table[0])
    require(all(type(row) is list and len(row) == t for row in table), 'balanced table')
    a = [[rational(v) for v in row] for row in table]
    grand = sum(map(sum, a), F())/(n*t)
    return [[a[i][j]-average(a[i])-average([a[k][j] for k in range(n)])+grand
             for j in range(t)] for i in range(n)]


def twfe(treatment, outcomes):
    dr = two_way(treatment); yr = two_way(outcomes)
    require(len(dr) == len(yr) and len(dr[0]) == len(yr[0]), 'common table dimensions')
    den = sum(x*x for row in dr for x in row)
    require(den > 0, 'no residual treatment variation')
    coefficient = sum(x*y for r, s in zip(dr, yr) for x, y in zip(r, s))/den
    return coefficient, dr, den


def conditional_law():
    masses = {(1, 0): F(1, 8), (1, 1): F(3, 8), (0, 0): F(3, 8), (0, 1): F(1, 8)}
    rows = []
    for (a, h), mass in masses.items():
        for e in (-1, 1):
            m0 = F(1+2*h); tau = F(2+2*h); dy = m0+a*tau+e
            p = (F(1, 4), F(3, 4))[h]; pi = F(1, 2)
            composition = a*(tau-F(7, 2))/pi
            treated_noise = a*e/pi
            comparison_noise = -(1-a)*p*e/(pi*(1-p))
            rows.append((mass/2, {'a': a, 'h': h, 'e': e, 'm0': m0, 'tau': tau,
                         'dy': dy, 'p': p, 'composition': composition,
                         'treated_noise': treated_noise, 'comparison_noise': comparison_noise,
                         'phi': composition+treated_noise+comparison_noise}))
    return rows


def expect(rows, function):
    return sum(p*function(r) for p, r in rows)


def dr_functional(rows, propensity, mean0):
    require(type(propensity) is list and type(mean0) is list and len(propensity) == len(mean0) == 2,
            'two finite baseline cells')
    p = [rational(v) for v in propensity]; m = [rational(v) for v in mean0]
    require(all(0 < v < 1 for v in p), 'strict candidate overlap')
    pi = expect(rows, lambda r: r['a'])
    require(pi > 0, 'positive treated share')
    return expect(rows, lambda r: (r['a']-(1-r['a'])*p[r['h']]/(1-p[r['h']]))*(r['dy']-m[r['h']]))/pi


def cell_fit(records):
    require(type(records) is list and 4 <= len(records) <= 64, '4..64 complete unit records')
    cells = {(a, h): [] for a, h in itertools.product((0, 1), repeat=2)}
    for row in records:
        require(type(row) is tuple and len(row) == 3, 'record (A,H,change)')
        a, h, dy = row
        require(type(a) is int and type(h) is int and a in (0, 1) and h in (0, 1),
                'binary integer group/cell')
        cells[a, h].append(rational(dy))
    require(all(cells.values()), 'empty group/cell: estimate unavailable')
    n = len(records); n1 = sum(len(cells[1, h]) for h in (0, 1)); pi = F(n1, n)
    p = [F(len(cells[1, h]), len(cells[1, h])+len(cells[0, h])) for h in (0, 1)]
    mu0 = [average(cells[0, h]) for h in (0, 1)]
    tau = sum(F(len(cells[1, h]), n1)*(average(cells[1, h])-mu0[h]) for h in (0, 1))
    phi = [(a*(dy-mu0[h]-tau)-(1-a)*p[h]*(dy-mu0[h])/(1-p[h]))/pi for a, h, dy in records]
    return {'ATT': tau, 'influence_mean': average(phi), 'root_variance': average([v*v for v in phi]),
            'propensities': p, 'treated_share': pi}


def contrasts(table):
    require(type(table) is list and len(table) == 3 and all(type(r) is list and len(r) == 4 for r in table),
            'original three-cohort four-date table')
    e, l, n = [[rational(x) for x in row] for row in table]
    return [(average(e[1:])-e[0])-(average(n[1:])-n[0]),
            (l[3]-average(l[:3]))-(n[3]-average(n[:3])),
            (average(e[1:3])-e[0])-(average(l[1:3])-l[0]),
            (l[3]-average(l[1:3]))-(e[3]-average(e[1:3]))]


def sensitivity(kind, bound):
    bound = rational(bound)
    require(0 <= bound <= 4, 'sensitivity evidence bound 0..4')
    require(kind in ('relative', 'smooth'), 'known restriction family')
    rows = []
    for a, b in itertools.product((-bound, bound), repeat=2):
        post = [a, a+b] if kind == 'relative' else [1+a, 2+2*a+b]
        departure = [F(-2), F(-1), F(0)]+post
        effects = [F(4)-post[0], F(6)-post[1]]
        rows.append({'parameters': (a, b), 'departure': departure, 'effects': effects,
                     'target': average(effects)})
    return rows


def gaussian_projection(alpha, sd, bound):
    require(type(alpha) in (int, float) and math.isfinite(alpha) and 0 < alpha < 1,
            'finite alpha strictly between zero and one')
    require(type(sd) in (int, float) and math.isfinite(sd) and 0 < sd <= 10,
            'positive bounded known standard deviation')
    bound = rational(bound); require(0 <= bound <= 4, 'nonnegative bounded sensitivity')
    level = 1-alpha/4
    require(.5 < level < 1, 'confidence quantile must be representable below one')
    z = NormalDist().inv_cdf(level); h = z*sd
    return z, h, (4-(1+float(bound))*h, 4+(1+float(bound))*h)


def normalize(text):
    return re.sub(r'\s+', '', text).replace('−', '-')


class Reader(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []; self.ids = []; self.links = []; self.sources = []
        self.worked = 0; self.prompts = {}; self.answers = {}; self.text = []
        self.exercise_count = 0; self.solution_count = 0
        self.exercise_depth = None; self.solution_depth = None; self.capture = []
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
                    require(key and key not in dest, 'missing or duplicated pairing')
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
            raise ValueError('accepted invalid domain: '+label)
    def anchor(self, page, exercise, *values):
        text = normalize(page.answers['v12-c07-e'+str(exercise)])
        for v in values:
            self.eq(normalize(str(v)) in text, True, 'solution '+str(exercise)+' anchor '+str(v))
            self.anchors += 1
    def body(self, page, value):
        self.eq(normalize(str(value)) in normalize(' '.join(page.text)), True, 'manuscript exact value '+str(value))
        self.anchors += 1


def numerical(a, page):
    law = conditional_law(); E = lambda f: expect(law, f)
    a.eq(sum(p for p, _ in law), 1, 'finite law mass')
    a.eq(E(lambda r: r['a']), F(1, 2), 'treated probability')
    for h, expected_p in ((0, F(1, 4)), (1, F(3, 4))):
        a.eq(E(lambda r: int(r['h'] == h)), F(1, 2), 'baseline cell share')
        a.eq(E(lambda r: int(r['h'] == h)*r['a'])/F(1, 2), expected_p, 'propensity')
    att = 2*E(lambda r: r['a']*r['tau'])
    treated = 2*E(lambda r: r['a']*r['dy']); comparison = 2*E(lambda r: (1-r['a'])*r['dy'])
    a.eq((att, treated, comparison, treated-comparison), (F(7, 2), 6, F(3, 2), F(9, 2)), 'conditional and unconditional contrasts')
    odds_mass = E(lambda r: (1-r['a'])*r['p']/(1-r['p']))
    weighted_mean = E(lambda r: (1-r['a'])*r['p']*r['dy']/(1-r['p']))/odds_mass
    a.eq((odds_mass, weighted_mean, treated-weighted_mean), (F(1, 2), F(5, 2), att), 'normalized true odds')
    for correct_p, correct_m in itertools.product((False, True), repeat=2):
        p = [F(1, 4), F(3, 4)] if correct_p else [F(1, 2)]*2
        m = [F(1), F(3)] if correct_m else [F(0)]*2
        estimate = dr_functional(law, p, m)
        remainder = 2*E(lambda r: (r['p']-p[r['h']])*(r['m0']-m[r['h']])/(1-p[r['h']]))
        a.eq(estimate-att, remainder, 'exact DR remainder')
        a.eq(estimate, att if correct_p or correct_m else F(9, 2), 'DR combinations')
    components = ('composition', 'treated_noise', 'comparison_noise')
    a.eq([E(lambda r: r[k]**2) for k in components], [F(3, 2), F(2), F(14, 3)], 'three influence variances')
    for left, right in itertools.combinations(components, 2):
        a.eq(E(lambda r: r[left]*r[right]), 0, 'influence cross covariance')
    a.eq((E(lambda r: r['phi']), E(lambda r: r['phi']**2)), (0, F(49, 6)), 'fitted-cell influence moments')
    records = []
    for mass, row in law:
        require((mass*16).denominator == 1, 'finite cohort multiplicity')
        records.extend([(row['a'], row['h'], row['dy'])]*int(mass*16))
    fit = cell_fit(records)
    a.eq((fit['ATT'], fit['influence_mean'], fit['root_variance']), (att, 0, F(49, 6)), 'actual fitted sixteen-record cohort')
    a.eq(fit['propensities'], [F(1, 4), F(3, 4)], 'fitted cell propensities')
    a.anchor(page, 1, 'ATT', 'g−a−1', 'G>t+a', 'interference')
    a.anchor(page, 2, F(7, 2), F(9, 2), F(5, 2), '1/8', '3/8', 'normalization')
    a.anchor(page, 3, F(7, 2), F(9, 2), 'remainder', 'actual π', 'different remainder')
    a.anchor(page, 4, F(3, 2), F(14, 3), F(49, 6), F(20, 3), 'V/N', 'N_ah=0')

    d = [[0, 1, 1, 1], [0, 0, 0, 1], [0, 0, 0, 0]]
    y = [[0, 1, 3, 7], [0, 0, 0, 2], [0, 0, 0, 0]]
    coefficient, dr, den = twfe(d, y)
    residual12 = [[12*v for v in row] for row in dr]
    a.eq(residual12, [[-5, 3, 3, -1], [1, -3, -3, 5], [4, 0, 0, -4]], 'full residual treatment table')
    a.eq((den, coefficient), (F(5, 6), F(3, 2)), 'TWFE norm and coefficient')
    effect_weights = [dr[i][t]/den for i, t in ((0, 1), (0, 2), (0, 3), (1, 3))]
    a.eq(effect_weights, [F(3, 10), F(3, 10), -F(1, 10), F(1, 2)], 'all treated effect weights')
    a.eq(sum(effect_weights), 1, 'effect weights sum one')
    cs = contrasts(y); comparison_weights = [F(3, 10), F(3, 10), F(1, 5), F(1, 5)]
    a.eq(cs, [F(11, 3), F(2), F(2), F(-3)], 'four comparisons')
    a.eq(sum(v*w for v, w in zip(cs, comparison_weights)), coefficient, 'comparison aggregation')
    # Every basis table proves the finite coefficient identity on all 12 cells.
    finite_operator = [v/den for row in dr for v in row]
    expected_operator = [F(v) for v in ('-1/2', '3/10', '3/10', '-1/10', '1/10', '-3/10', '-3/10', '1/2', '2/5', '0', '0', '-2/5')]
    a.eq(finite_operator, expected_operator, 'full FWL operator')
    for cell in range(12):
        basis = [[F(i*4+t == cell) for t in range(4)] for i in range(3)]
        a.eq(sum(v*w for v, w in zip(contrasts(basis), comparison_weights)), finite_operator[cell], 'full comparison coefficient identity')
    for last, expected in ((7, F(3, 2)), (22, F(0)), (23, -F(1, 10))):
        changed = [list(row) for row in y]; changed[0][3] = last
        a.eq(twfe(d, changed)[0], expected, 'positive-effect sign intervention')
        a.eq(expected, F(22-last, 10), 'exact sign boundary formula')
    a.anchor(page, 5, '5/6', '120/144', *effect_weights, '(22−x)/10', 'x=22', 'x>22')
    a.anchor(page, 6, *cs, '3/2', 'FWL operator', '7−(1+3)/2=5')

    # Full eleven-column regression is independent of the five-column residual route.
    cohorts = (2, 4, None); times = (1, 2, 3, 4); events = (-3, -2, 0, 1, 2)
    full = []; event = []
    for i, g in enumerate(cohorts):
        for t in times:
            z = [F(g is not None and t-g == k) for k in events]
            event.append(z)
            full.append([F(i == j) for j in range(3)]+[F(t == s) for s in (2, 3, 4)]+z)
    fullgram = multiply(transpose(full), full); fullinv = inverse(fullgram)
    a.eq(multiply(fullgram, fullinv), [[F(i == j) for j in range(11)] for i in range(11)], 'full event design rank')
    fulloperator = multiply(fullinv, transpose(full))[6:]
    residual_columns = []
    for j in range(5):
        table = [[event[i*4+t][j] for t in range(4)] for i in range(3)]
        residual_columns.append([v for row in two_way(table) for v in row])
    residual = transpose(residual_columns)
    gram = multiply(transpose(residual), residual)
    A = [[6, -2, -1, 1, 1], [-2, 6, -5, 1, 1], [-1, -5, 14, -1, -5], [1, 1, -1, 6, -2], [1, 1, -5, -2, 6]]
    a.eq([[12*v for v in row] for row in gram], A, 'full residual five by five Gram')
    residual_operator = multiply(inverse(gram), transpose(residual))
    a.eq(fulloperator, residual_operator, 'full eleven-column versus FWL event operator')
    operator8 = [[-3, 3, 0, 0, 8, 0, -5, -3, -5, -3, 5, 3],
                 [-1, 1, 0, 0, 0, 8, -7, -1, 1, -9, 7, 1],
                 [-4, 4, 0, 0, 0, 0, -4, 4, 4, -4, 4, -4],
                 [-5, -3, 8, 0, 0, 0, -3, 3, 5, 3, -5, -3],
                 [-7, -1, 0, 8, 0, 0, -1, 1, 7, 1, 1, -9]]
    a.eq([[8*v for v in row] for row in fulloperator], operator8, 'all sixty event operator entries')
    a.eq(multiply(fulloperator, full), [[F(j == i+6) for j in range(11)] for i in range(5)], 'event operator annihilates fixed effects and selects event columns')
    flaty = [[F(v)] for row in y for v in row]
    beta = [row[0] for row in multiply(fulloperator, flaty)]
    a.eq(beta, [-F(3, 8), -F(1, 8), F(3, 2), F(27, 8), F(57, 8)], 'five event coefficients')
    a.eq([12*row[0] for row in multiply(transpose(residual), flaty)], [7, 3, -17, 4, 28], 'residual outcome cross product')
    # Fraction elimination certificate for the printed determinant and pivots.
    work = [[F(v) for v in row] for row in A]; pivots = []; determinant = F(1)
    for j in range(5):
        pivot = work[j][j]; pivots.append(pivot); determinant *= pivot
        for i in range(j+1, 5):
            factor = work[i][j]/pivot
            for k in range(j, 5):
                work[i][k] -= factor*work[j][k]
    a.eq(pivots, [F(6), F(16, 3), F(17, 2), F(93, 17), F(96, 31)], 'rank pivots')
    a.eq((determinant, determinant/12**5), (4608, F(1, 54)), 'exact determinant')
    for early_impact, late_impact, early_one, early_two in ((1, 2, 3, 7), (1, 1, 3, 7), (1, 2, 1, 1)):
        changed = [[0, early_impact, early_one, early_two], [0, 0, 0, late_impact], [0, 0, 0, 0]]
        got = [row[0] for row in multiply(fulloperator, [[F(v)] for row in changed for v in row])]
        formula = [F(3*(early_impact-late_impact), 8), F(early_impact-late_impact, 8),
                   F(early_impact+late_impact, 2), early_one+F(3*(late_impact-early_impact), 8),
                   early_two+F(late_impact-early_impact, 8)]
        a.eq(got, formula, 'effect contamination formula and interventions')
        if early_impact == late_impact:
            a.eq(got, [0, 0, 1, 3, 7], 'equal impact removes artificial leads')
    a.anchor(page, 7, *beta, '4608', '1/54', '0,0,1,3,7', 'heterogeneity')
    for row in A:
        a.body(page, '('+','.join(str(v) for v in row)+')')
    for row in operator8:
        for start in (0, 4, 8):
            a.body(page, '('+','.join(str(v) for v in row[start:start+4])+')')
    a.eq((F(1+2, 2), F(3), F(3)-F(3, 2), F(3)-1), (F(3, 2), 3, F(3, 2), 2), 'changing versus fixed supported cohorts')
    a.eq((F(1+2, 2), F(1), F(1)-F(3, 2), F(1)-1), (F(3, 2), 1, -F(1, 2), 0), 'constant-cohort effect composition counterexample')
    a.anchor(page, 8, '3/2', '−1/2', 'difference 0', 'beyond', 'not an observed zero')

    target = [1, 4, 8, 9]; never = [1, 2, 3, 4]; anticipatory = [1, 2, 5, None]
    contrast = lambda y, c, b, t: (y[t]-y[b])-(c[t]-c[b])
    a.eq(contrast(target, never, 1, 2), 3, 'contaminated target baseline')
    a.eq(contrast(target, never, 0, 2), 5, 'unaffected baseline target')
    a.eq(contrast(target, never, 0, 3), 5, 'last-date target with never controls')
    a.eq(contrast(target, anticipatory, 0, 2), 3, 'not-yet-treated but anticipating control')
    a.eq(3-1-1, 1, 'baseline calendar rule')
    a.eq(4 > 3+1, False, 'control eligibility boundary')
    a.eq(5 > 3+1, True, 'first eligible future cohort')
    a.anchor(page, 9, '3', '5', 'G>3+1', 'unsupported', 't+a>T', 'known later adoption')

    for kind in ('relative', 'smooth'):
        for bound in (F(0), F(1, 2), F(1)):
            vertices = sensitivity(kind, bound); values = [r['target'] for r in vertices]
            center = F(5) if kind == 'relative' else F(7, 2)
            radius = F(3, 2)*bound if kind == 'relative' else 2*bound
            a.eq((min(values), max(values)), (center-radius, center+radius), 'sharp '+kind+' square extrema')
            for row in vertices:
                path = row['departure']; differences = [path[i+1]-path[i] for i in range(4)]
                if kind == 'relative':
                    a.eq(max(abs(v) for v in differences[2:]) <= bound, True, 'relative restriction')
                else:
                    a.eq(max(abs(differences[j+1]-differences[j]) for j in (1, 2)) <= bound, True, 'smoothness restriction')
                a.eq([path[3+i]+row['effects'][i] for i in range(2)], [4, 6], 'sharp compatible observed law')
            left = min(vertices, key=lambda r: r['target']); right = max(vertices, key=lambda r: r['target'])
            # A convex mixture constructs a prescribed interior target, not a grid claim.
            mixture = [F(1, 3)*x+F(2, 3)*y for x, y in zip(left['departure'], right['departure'])]
            mix_target = average([F(4)-mixture[3], F(6)-mixture[4]])
            a.eq(mix_target, F(1, 3)*min(values)+F(2, 3)*max(values), 'interior sharpness witness')
    a.anchor(page, 10, '17/4', '23/4', '5/2', '9/2', '{5}', '{7/2}', 'compatible', 'squared period')
    a.eq((0+4, 3+1), (4, 4), 'identical observed post gap under different counterfactuals')
    a.body(page, 'untreated post gap 0 and effect 4')
    a.body(page, 'untreated post gap 3 and effect 1')

    z, h, bounds = gaussian_projection(.05, .2, 1)
    # Independent inverse-CDF bisection through erf, distinct from NormalDist.
    lo, hi = 0.0, 5.0
    for _ in range(80):
        middle = (lo+hi)/2; cdf = (1+math.erf(middle/math.sqrt(2)))/2
        if cdf < .9875:
            lo = middle
        else:
            hi = middle
    a.near(z, (lo+hi)/2, 'independent normal quantile')
    a.near(2*(1-NormalDist().cdf(z)), .025, 'marginal coordinate failure')
    a.near(2*.025, .05, 'union failure bound')
    a.near(z, 2.2414027276049464, 'critical value')
    a.near(h, .4482805455209893, 'coordinate halfwidth')
    for actual, printed in zip(bounds, (3.103438908958, 4.896561091042)):
        a.near(actual, printed, 'rounded projected interval')
        a.body(page, format(printed, '.12f'))
    for bound in (0, 1, 2):
        _, _, interval = gaussian_projection(.05, .2, bound)
        endpoints = [post-sign*bound*abs(pre) for post, pre, sign in itertools.product((4-h, 4+h), (-h, h), (-1, 1))]
        a.near(interval[0], min(endpoints), 'attained projected lower endpoint')
        a.near(interval[1], max(endpoints), 'attained projected upper endpoint')
        if bound == 2:
            for actual, printed in zip(interval, (2.655158363437, 5.344841636563)):
                a.near(actual, printed, 'changed sensitivity confidence interval')
                a.body(page, format(printed, '.12f'))
    a.anchor(page, 11, 'union bound', 'α/2', '4−2h', '4+2h', '4−3h', '4+3h', 'different information')
    a.anchor(page, 12, 'Six distinctions', 'Two repairs', 'Conclusion', '95%', 'sampling uncertainty')

    cases = [
        (lambda: rational(True), 'boolean numeric'), (lambda: rational(float('nan')), 'nonfinite numeric'),
        (lambda: rational(10**7), 'magnitude bound'), (lambda: inverse([[1, 1], [1, 1]]), 'singular Gram'),
        (lambda: two_way([[1, 2], [3]]), 'unbalanced design'),
        (lambda: twfe([[0, 0], [0, 0]], [[1, 2], [2, 3]]), 'zero treatment variation'),
        (lambda: dr_functional(law, [0, 1], [1, 3]), 'candidate overlap failure'),
        (lambda: cell_fit([(0, 0, 1)]*4), 'missing group cells'),
        (lambda: cell_fit([(True, 0, 1)]*4), 'boolean treatment'),
        (lambda: contrasts([[0, 1], [0, 0], [0, 0]]), 'changed unmodeled design'),
        (lambda: sensitivity('relative', -1), 'negative sensitivity'),
        (lambda: sensitivity('other', 1), 'unknown sensitivity family'),
        (lambda: sensitivity('relative', 5), 'bounded evidence domain'),
        (lambda: gaussian_projection(True, .2, 1), 'boolean alpha'),
        (lambda: gaussian_projection(0, .2, 1), 'invalid confidence level'),
        (lambda: gaussian_projection(.05, 0, 1), 'zero stated Gaussian scale'),
        (lambda: gaussian_projection(.05, float('inf'), 1), 'nonfinite scale'),
        (lambda: gaussian_projection(1e-300, .2, 1), 'rounded-to-one quantile')]
    for call, label in cases:
        a.reject(call, label)
    return {'conditional_joint_atoms': 8, 'fitted_sample_records': 16,
            'TWFE_basis_cells': 12, 'event_full_design_shape': [12, 11],
            'event_operator_entries': 60, 'event_coefficients': [str(v) for v in beta],
            'conditional_root_variance': '49/6', 'sensitivity_families': 2}


def hashrow(path):
    raw = (BASE/path).read_bytes()
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def check():
    before = {p: (BASE/p).read_bytes() for p in FILES}; audit = Audit(); page = Reader()
    page.feed(before[FILES[0]].decode('utf-8')); page.close()
    audit.eq(page.stack, [], 'balanced complete fragment')
    audit.eq((page.worked, page.exercise_count, page.solution_count), (6, 12, 12), 'reader structure')
    expected = {'v12-c07-e'+str(i) for i in range(1, 13)}
    audit.eq(set(page.prompts), expected, 'twelve prompts')
    audit.eq(set(page.answers), expected, 'twelve paired answers')
    audit.eq(len(page.ids), len(set(page.ids)), 'unique IDs')
    audit.eq(set(page.sources), SOURCES, 'four scoped source citations')
    allowed = {'v12-c01.html', 'v12-c02.html', 'v12-c03.html', 'v12-c05.html', 'v12-c06.html', 'v12-c08.html'}
    for link in page.links:
        audit.eq(link in allowed or link in {'sources.html#'+s for s in SOURCES}, True, 'flat declared route')
    evidence = numerical(audit, page)
    sources = strict(before[FILES[2]].decode('utf-8'))
    audit.eq({r['id'] for r in sources['sources']}, SOURCES, 'source proposal identities')
    audit.eq(len(sources['sources']), 4, 'four source scopes')
    review = strict(before[FILES[3]].decode('utf-8'))
    audit.eq(set(review['payloads']), set(FILES[:3]), 'three nonself bindings')
    for name in FILES[:3]:
        audit.eq(review['payloads'][name], hashrow(name), 'payload unchanged '+name)
    rejected = 0
    for invalid in ('{"x":1,"x":2}', 'NaN', 'Infinity', '-Infinity', '1e10000', '{}{}'):
        try:
            strict(invalid)
        except ValueError:
            rejected += 1
        else:
            raise ValueError('permissive JSON parser')
    audit.eq(rejected, 6, 'strict JSON boundaries')
    for path, raw in before.items():
        audit.eq((BASE/path).read_bytes(), raw, 'read-only execution '+path)
    result = {'chapter': 'v12-c07', 'status': 'author checks passed; separate review required',
              'comparisons': audit.count, 'domain_rejections': audit.rejections,
              'strict_JSON_rejections': rejected, 'worked_examples': 6, 'exact_prompts_and_solutions': 12,
              'visible_anchors': audit.anchors, 'primary_scopes': 4, 'finite_evidence': evidence,
              'limits': 'Finite original laws and separate analytic proof audit; no empirically verified parallel trends, generic nuisance/cluster/uniform-inference theorem, rendered UI or external human certification.'}
    strict(json.dumps(result, allow_nan=False))
    return result


def portable():
    with tempfile.TemporaryDirectory(prefix='v12-c07-author-') as directory:
        target = Path(directory)
        for path in FILES:
            (target/path).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(BASE/path, target/path)
        before = {p: (target/p).read_bytes() for p in FILES}; results = []
        code = ("import contextlib,importlib.util,io,json;s=importlib.util.spec_from_file_location('a',"
                +repr(str(target/FILES[1]))+");m=importlib.util.module_from_spec(s)\n"
                "with contextlib.redirect_stdout(io.StringIO()) as o,contextlib.redirect_stderr(io.StringIO()) as e:\n"
                " s.loader.exec_module(m);r=m.check()\n"
                "if o.getvalue() or e.getvalue():raise ValueError('nonquiet API')\n"
                "print(json.dumps(r,allow_nan=False,sort_keys=True))")
        for flags in ([], ['-O']):
            result = subprocess.run([sys.executable, '-B']+flags+['-c', code], cwd='/',
                                    capture_output=True, text=True, timeout=30,
                                    env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
            require(result.returncode == 0 and not result.stderr, 'isolated API failed '+result.stderr)
            results.append(strict(result.stdout))
            cli = subprocess.run([sys.executable, '-B']+flags+[str(target/FILES[1])], cwd='/',
                                 capture_output=True, text=True, timeout=30,
                                 env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
            require(cli.returncode == 0 and not cli.stdout and not cli.stderr, 'isolated CLI failed '+cli.stderr)
        require(results[0] == results[1], 'normal/optimized mismatch')
        require(before == {p: (target/p).read_bytes() for p in FILES}, 'isolated payload mutation')
        require({str(p.relative_to(target)) for p in target.rglob('*') if p.is_file()} == set(FILES), 'exact four-file membership')
        return {'status': 'passed', 'files': 4, 'cwd': '/', 'normal_and_optimized_API_CLI': True,
                'no_mutation': True, 'summary': results[0]}


if __name__ == '__main__':
    check()
