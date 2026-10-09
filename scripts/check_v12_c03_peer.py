"""Independent, read-only finite evidence for v12-c03.

The oracle uses finite probability laws, rational orthogonalization and Cramer's
rule. It imports no author implementation. Probability proofs were read separately.
Quiet check() uses exactly the four author files, this checker and its peer record.
"""
from fractions import Fraction as F
from html.parser import HTMLParser
from itertools import product
from math import exp, isfinite, sqrt
from pathlib import Path
from statistics import NormalDist
import hashlib
import json


MANUSCRIPT = 'content/chapters/v12-c03.html'
AUTHOR_CHECKER = 'scripts/check_v12_c03.py'
AUTHOR = 'content/reviews/v12-c03-author.json'
SOURCES = 'content/reviews/v12-c03-sources.json'
SELF = 'scripts/check_v12_c03_peer.py'
RECORD = 'content/reviews/v12-c03-peer.json'
FROZEN = {
    MANUSCRIPT: (60382, '99dd513f4ea3807db23aee28df6bf25f296cefaa0700f49a8ed8199efd9149d5'),
    AUTHOR_CHECKER: (29895, '4a1564024ea314918f1ede4246fa26204575c11b6b9c828fbb8023fa0c48b950'),
    SOURCES: (10219, 'ed46fe4af4920a7c831c974942d56568bc44ce42bde9873db3d353e22218d837'),
    AUTHOR: (20588, 'dde10dde432de486a75fa6def1cd12845008fadfa4fe61f80b2fc3ddd00e32a9'),
}


def demand(condition, message):
    if not condition:
        raise ValueError('v12-c03 peer: ' + message)


def exact(value):
    demand(type(value) in (int, F), 'exact finite rational required')
    return F(value)


def dot(x, y):
    demand(len(x) == len(y), 'vector dimensions')
    return sum((a*b for a, b in zip(x, y)), F(0))


def transpose(a):
    return [list(row) for row in zip(*a)]


def multiply(a, b):
    demand(len(a[0]) == len(b), 'matrix dimensions')
    return [[dot(row, col) for col in transpose(b)] for row in a]


def determinant(a):
    n = len(a)
    demand(1 <= n <= 4 and all(len(row) == n for row in a), 'bounded square determinant')
    a = [[exact(v) for v in row] for row in a]
    if n == 1:
        return a[0][0]
    return sum(((-1)**j*a[0][j]*determinant(
        [row[:j]+row[j+1:] for row in a[1:]]) for j in range(n)), F(0))


def solve(a, b):
    denominator = determinant(a)
    demand(denominator != 0 and len(b) == len(a), 'identified square system')
    out = []
    for j in range(len(a)):
        replaced = [list(row) for row in a]
        for i in range(len(a)):
            replaced[i][j] = exact(b[i])
        out.append(determinant(replaced)/denominator)
    return out


def inverse(a):
    return transpose([solve(a, [int(i == j) for i in range(len(a))]) for j in range(len(a))])


def spd(a):
    demand(len(a) == len(a[0]) and a == transpose(a), 'symmetric covariance/weight')
    for k in range(1, len(a)+1):
        demand(determinant([row[:k] for row in a[:k]]) > 0, 'positive principal minor')
    return a


def project(columns, v):
    """Rational Gram-Schmidt; no inverse of the instrument Gram is used."""
    demand(1 <= len(columns) <= 4 and 1 <= len(v) <= 80, 'bounded projection dimensions')
    basis = []
    for col in columns:
        demand(len(col) == len(v), 'instrument row count')
        residual = [exact(x) for x in col]
        for old in basis:
            coefficient = dot(old, residual)/dot(old, old)
            residual = [x-coefficient*y for x, y in zip(residual, old)]
        demand(dot(residual, residual) > 0, 'full instrument rank')
        basis.append(residual)
    result = [F(0)]*len(v)
    for old in basis:
        coefficient = dot(old, v)/dot(old, old)
        result = [x+coefficient*y for x, y in zip(result, old)]
    return result


def weights(b, w):
    """k-by-m influence matrix via separately solved normal equations."""
    spd(w)
    btw = multiply(transpose(b), w)
    curvature = multiply(btw, b)
    return transpose([solve(curvature, col) for col in transpose(btw)])


def covariance(k, omega):
    return multiply(multiply(k, omega), transpose(k))


def acceptance(a, b, c, variance, cutoff):
    a, b, c, variance, cutoff = [exact(x) for x in (a, b, c, variance, cutoff)]
    demand(a >= 0 and c >= 0 and b*b <= a*c, 'projection Gram feasibility')
    demand(variance > 0 and cutoff >= 0, 'known positive variance and nonnegative cutoff')
    budget = variance*cutoff
    if a == 0:
        return ('all',) if c <= budget else ('empty',)
    center = b/a
    excess = budget-c+b*b/a
    if excess < 0:
        return ('empty',)
    return ('singleton' if excess == 0 else 'interval', center, excess/a)


def quadratic_coefficients(columns, x, y):
    px, py = project(columns, x), project(columns, y)
    return dot(px, px), dot(px, py), dot(py, py)


def observed(types, assignment, direct=F(0)):
    assignment = exact(assignment)
    demand(0 < assignment < 1, 'positive assignment support')
    demand(sum(row[0] for row in types) == 1, 'unit type probability mass')
    law = {}
    for mass, d0, d1, y0, y1 in types:
        demand(mass >= 0 and d0 in (0, 1) and d1 in (0, 1), 'type domain')
        for z, pz in ((0, 1-assignment), (1, assignment)):
            d = d0 if z == 0 else d1
            y = (y1 if d else y0)+z*direct
            atom = (z, d, y, y1-y0)
            law[atom] = law.get(atom, F(0))+mass*pz
    marginal = {}
    for (z, d, y, effect), mass in law.items():
        key = (z, d, y)
        marginal[key] = marginal.get(key, F(0))+mass
    dmeans = [sum(p*d for (z, d, y, tau), p in law.items() if z == zz)/pz
              for zz, pz in ((0, 1-assignment), (1, assignment))]
    ymeans = [sum(p*y for (z, d, y, tau), p in law.items() if z == zz)/pz
              for zz, pz in ((0, 1-assignment), (1, assignment))]
    demand(dmeans[1] != dmeans[0], 'nonzero compliance first stage')
    treated = sum(p*d for (z, d, y, tau), p in law.items())
    demand(treated > 0, 'nonempty treated population')
    return dict(d=dmeans, y=ymeans, wald=(ymeans[1]-ymeans[0])/(dmeans[1]-dmeans[0]),
                ate=sum(p*tau for (z, d, y, tau), p in law.items()), treated=treated,
                att=sum(p*d*tau for (z, d, y, tau), p in law.items())/treated, law=marginal)


def strict_json(raw):
    def pairs(rows):
        out = {}
        for key, value in rows:
            demand(key not in out, 'duplicate JSON member')
            out[key] = value
        return out
    def number(value):
        parsed = float(value)
        demand(isfinite(parsed), 'finite JSON number')
        return parsed
    def bad(value):
        raise ValueError('nonfinite JSON constant: '+value)
    return json.loads(raw, object_pairs_hook=pairs, parse_float=number, parse_constant=bad)


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []; self.ids = []; self.prompts = []; self.solutions = []
        self.worked = []; self.links = []; self.sources = []; self.anchors = {}
        self.active = None; self.exercise_depth = None; self.prose = []
    def handle_starttag(self, tag, attrs):
        d = dict(attrs); classes = d.get('class', '').split()
        if 'id' in d: self.ids.append(d['id'])
        if 'worked' in classes: self.worked.append(d.get('id'))
        if 'data-solution-for' in d: self.solutions.append(d['data-solution-for'])
        if 'data-source' in d: self.sources.append(d['data-source'])
        if tag == 'a': self.links.append(d.get('href'))
        if tag == 'ol' and 'exercises' in classes: self.exercise_depth = len(self.stack)+1
        if tag == 'li' and self.exercise_depth == len(self.stack): self.prompts.append(d.get('id'))
        if 'data-calc' in d:
            demand(self.active is None and d['data-calc'] not in self.anchors, 'unique numerical marker')
            self.active = d['data-calc']; self.anchors[self.active] = ''
        if tag not in ('br', 'hr', 'img', 'input', 'meta', 'link'): self.stack.append(tag)
    def handle_endtag(self, tag):
        demand(self.stack and self.stack[-1] == tag, 'balanced fragment '+tag)
        if tag == 'span': self.active = None
        if tag == 'ol' and self.exercise_depth == len(self.stack): self.exercise_depth = None
        self.stack.pop()
    def handle_data(self, data):
        demand(self.stack or not data.strip(), 'no stray text outside fragment')
        self.prose.append(data)
        if self.active is not None: self.anchors[self.active] += data


class Audit:
    def __init__(self):
        self.count = 0; self.rejected = 0; self.interventions = []
    def eq(self, actual, expected, label):
        self.count += 1
        demand(actual == expected, label+': '+repr(actual)+' != '+repr(expected))
    def near(self, actual, expected, tolerance, label):
        self.count += 1
        demand(isfinite(float(actual)) and abs(float(actual)-float(expected)) <= tolerance, label)
    def reject(self, call, label):
        try:
            call()
        except ValueError:
            self.rejected += 1
        else:
            raise ValueError('missing rejection: '+label)


def finite_evidence(a):
    v = {}; rounded = {}
    atoms = list(product((-1, 1), repeat=3))
    expectation = lambda fn: sum((F(fn(*atom)) for atom in atoms), F(0))/len(atoms)
    first = expectation(lambda z, e, w: z*(z+e))
    reduced = expectation(lambda z, e, w: z*(2*(z+e)+e+w))
    v['case1-iv'] = reduced/first
    v['case1-ols'] = expectation(lambda z, e, w: (z+e)*(2*(z+e)+e+w))/expectation(lambda z, e, w: (z+e)**2)
    v['case1-meat'] = expectation(lambda z, e, w: (z*(e+w))**2)
    v['case1-wrong-meat'] = expectation(lambda z, e, w: (z*(3*e+w))**2)
    v['case1-invalid-iv'] = expectation(lambda z, e, w: z*(2*(z+e)+e+w+F(2, 5)*z))/first
    a.eq((first, reduced), (F(1), F(2)), 'finite-law valid first stage and reduced form')
    a.eq([v[k] for k in ('case1-iv', 'case1-ols', 'case1-meat', 'case1-wrong-meat')],
         [F(2), F(5, 2), F(2), F(10)], 'coefficient versus structural score')
    v['ex1-ols'] = expectation(lambda z, e, w: (2*z+e)*(2*(2*z+e)+e+w))/expectation(lambda z, e, w: (2*z+e)**2)
    v['ex1-invalid'] = expectation(lambda z, e, w: (z+e)*(2*(2*z+e)+e+w))/expectation(lambda z, e, w: (z+e)*(2*z+e))
    a.eq(expectation(lambda z, e, w: z*(e+w)), 0, 'valid score')
    a.eq(expectation(lambda z, e, w: (z+e)*(e+w)), 1, 'predictive invalid score')
    a.eq(v['ex1-ols'], F(11, 5), 'changed OLS target')
    a.eq(v['ex1-invalid'], F(7, 3), 'changed invalid IV target')
    a.interventions.append('Change direct exclusion and instrument contamination separately from relevance.')

    observations = []
    for group, sign, shock in product((1, 2), (-1, 1), (-1, 1)):
        z = [F(sign) if group == j else F(0) for j in (1, 2)]
        observations += [(z, F(sign), sign*(F(2*group+1, 2)+group*shock))]*5
    n = len(observations)
    zcols = transpose([row[0] for row in observations])
    x = [row[1] for row in observations]; y = [row[2] for row in observations]
    xhat = project(zcols, x)
    beta0 = dot(xhat, y)/dot(xhat, xhat)
    b = [[dot(col, x)/n] for col in zcols]; outcome = [dot(col, y)/n for col in zcols]
    score = [[zi*(yy-xx*beta0) for zi in zz] for zz, xx, yy in observations]
    omega = [[dot(r, s)/n for s in transpose(score)] for r in transpose(score)]
    a.eq((n, beta0, b, outcome), (40, F(2), [[F(1, 2)], [F(1, 2)]], [F(3, 4), F(5, 4)]), 'forty-row normal equations')
    a.eq(omega, [[F(5, 8), F(0)], [F(0), F(17, 8)]], 'preliminary uncentered structural covariance')
    k = weights(b, inverse(omega)); beta = dot(k[0], outcome)
    moment = [yy-row[0]*beta for yy, row in zip(outcome, b)]
    j = n*dot(moment, [dot(row, moment) for row in inverse(omega)])
    variance = covariance(k, omega)[0][0]
    v.update({'case2-feasible-beta': beta, 'case2-g1': moment[0], 'case2-g2': moment[1],
              'case2-feasible-j': j, 'case2-plugin-v': variance})
    rounded['case2-se'] = sqrt(float(variance/n))
    a.eq((beta, j, variance), (F(19, 11), F(40, 11), F(85, 44)), 'fixed second-step results')
    fresh_score = [[zi*(yy-xx*beta) for zi in zz] for zz, xx, yy in observations]
    fresh = [[dot(r, s)/n for s in transpose(fresh_score)] for r in transpose(fresh_score)]
    a.eq(fresh, [[F(509, 968), F(0)], [F(0), F(2225, 968)]], 'distinct updated residual covariance')
    a.eq(fresh != omega, True, 'preliminary covariance cannot silently change')
    # A bounded alternate innovation law has the same required second moments.
    population_scores = []
    for group, sign, innovation in product((1, 2), (-1, 1), (-1, 1)):
        population_scores.append([F(sign*group*innovation) if j == group else F(0) for j in (1, 2)])
    popomega = [[dot(r, s)/8 for s in transpose(population_scores)] for r in transpose(population_scores)]
    a.eq(popomega, [[F(1, 2), F(0)], [F(0), F(2)]], 'separate population score moments')
    ko = weights(b, inverse(popomega)); ki = weights(b, [[F(1), F(0)], [F(0), F(1)]])
    v['case2-pop-2sls-v'] = covariance(ki, popomega)[0][0]
    v['case2-pop-efficient-v'] = covariance(ko, popomega)[0][0]
    v['case2-efficiency-gap'] = v['case2-pop-2sls-v']-v['case2-pop-efficient-v']
    v['case2-oracle-beta'] = dot(ko[0], outcome)
    om = [yy-row[0]*v['case2-oracle-beta'] for yy, row in zip(outcome, b)]
    v['case2-oracle-j'] = n*dot(om, [dot(row, om) for row in inverse(popomega)])
    a.eq((v['case2-pop-2sls-v'], v['case2-pop-efficient-v'], v['case2-oracle-j']), (F(5, 2), F(8, 5), F(4)), 'population variance and oracle J')
    cutoff = NormalDist().inv_cdf(.975)**2
    a.near(cutoff, 3.841459, 5e-7, 'supplied cutoff rounding')
    a.eq(float(j) < cutoff < float(v['case2-oracle-j']), True, 'distinct finite test decisions')
    transform = [[F(1), F(2)], [F(2), F(-1)]]
    newcols = multiply(transform, zcols)
    a.eq(project(newcols, y), project(zcols, y), 'instrument basis preserves projection')
    a.eq(project(newcols, x), xhat, 'instrument basis preserves fitted regressor')
    newb = multiply(transform, b); newout = [dot(row, outcome) for row in transform]
    ti = inverse(transform)
    neww = multiply(multiply(transpose(ti), inverse(omega)), ti)
    a.eq(dot(weights(newb, neww)[0], newout), beta, 'transformed inverse weight preserves estimate')
    a.eq(dot(weights(newb, [[F(1), F(0)], [F(0), F(1)]])[0], newout) != beta, True, 'naive transformed weighting changes coefficient')
    a.interventions.extend(['Hold preliminary covariance fixed versus update it; compare oracle and feasible finite decisions.',
                            'Change instrument basis and moment units, carrying the inverse-transpose weight.'])

    deficient = [[F(1), F(2)], [F(2), F(4)], [F(-1), F(-2)]]
    for t in (F(-2), F(0), F(5, 3)):
        a.eq([dot(row, [3-2*t, t]) for row in deficient], [F(3), F(6), F(-3)], 'entire affine identified-set family')
    a.eq([dot(row, [F(-2), F(1)]) for row in deficient], [F(0)]*3, 'null direction')
    v['ex3-beta1'] = solve([[F(1), F(2)], [F(0), F(1)]], [F(3), F(1)])[0]
    a.interventions.append('Add an independent valid moment instead of duplicating a rank-deficient equation.')

    b6 = [[F(1)], [F(2)]]; omega6 = [[F(2), F(1)], [F(1), F(3)]]
    identity2 = [[F(1), F(0)], [F(0), F(1)]]
    kw = weights(b6, identity2); ke = weights(b6, inverse(omega6))
    kd = weights(b6, [[F(1, 2), F(0)], [F(0), F(1, 3)]])
    v['ex6-identity-v'] = covariance(kw, omega6)[0][0]
    v['ex6-efficient-v'] = covariance(ke, omega6)[0][0]
    v['ex6-gap'] = v['ex6-identity-v']-v['ex6-efficient-v']
    v['ex6-diagonal-v'] = covariance(kd, omega6)[0][0]
    a.eq((kw, ke, kd), ([[F(1, 5), F(2, 5)]], [[F(1, 7), F(3, 7)]], [[F(3, 11), F(4, 11)]]), 'correlated moment influence weights')
    a.eq(v['ex6-diagonal-v'] > v['ex6-identity-v'] > v['ex6-efficient-v'], True, 'marginal-only weighting loses efficiency')
    # Independent multi-coefficient example exercises the matrix PSD certificate.
    bm = [[F(2), F(1)], [F(1), F(0)], [F(0), F(1)]]
    factor = [[F(1), F(0), F(0)], [F(1), F(2), F(0)], [F(0), F(1), F(1)]]
    omatrix = multiply(factor, transpose(factor))
    wm = [[F(1), F(0), F(0)], [F(0), F(2), F(0)], [F(0), F(0), F(3)]]
    km = weights(bm, wm); em = weights(bm, inverse(omatrix))
    diff = [[r-s for r, s in zip(row, other)] for row, other in zip(km, em)]
    a.eq(multiply(diff, bm), [[F(0), F(0)], [F(0), F(0)]], 'matrix influence difference annihilates B')
    a.eq(multiply(multiply(em, omatrix), transpose(diff)), [[F(0), F(0)], [F(0), F(0)]], 'matrix cross covariance zero')
    covariance_gap = [[r-s for r, s in zip(row, other)] for row, other in zip(covariance(km, omatrix), covariance(em, omatrix))]
    a.eq(covariance_gap, covariance(diff, omatrix), 'matrix covariance difference factorization')
    for contrast in ([F(1), F(0)], [F(0), F(1)], [F(1), F(-3)]):
        a.eq(dot(contrast, [dot(row, contrast) for row in covariance_gap]) >= 0, True, 'PSD contrast variance')
    a.interventions.append('Retain full score covariance and verify a separate two-coefficient PSD certificate.')

    ones = [F(1)]*3; score = [F(1), F(-1), F(2)]
    fitted = project([ones], score); residual = [x-y for x, y in zip(score, fitted)]
    a.eq(residual, [F(1, 3), F(-5, 3), F(4, 3)], 'whitened residual score')
    v['ex7-j'] = dot(residual, residual)
    residual_matrix = []
    for j in range(3):
        ej = [F(i == j) for i in range(3)]; pj = project([ones], ej)
        residual_matrix.append([u-vv for u, vv in zip(ej, pj)])
    a.eq(multiply(residual_matrix, residual_matrix), residual_matrix, 'idempotent J residual projection')
    a.eq(sum(residual_matrix[i][i] for i in range(3)), 2, 'J residual rank by projection trace')
    shifted = [F(7, 3)]*3
    a.eq(project([ones], shifted), shifted, 'aligned invalidity has zero J residual')
    a.interventions.append('Keep a moment violation inside the fitted span; J cannot see the wrong structural target.')

    theta = F(21, 10); mean = F(441, 100); linear = 2+(mean-4)/4
    v.update({'case3-v': F(1), 'case3-estimate': theta, 'case3-linearized': linear,
              'case3-remainder': theta-linear, 'case3-plugin-se': F(4)/(2*theta*10)})
    a.eq(theta**2, mean, 'nonlinear moment solved')
    a.eq((mean-theta**2)-(mean-4), -(theta+2)*(theta-2), 'integrated signed Jacobian identity')
    a.eq(theta-linear, -(theta-2)**2/4, 'nonlinear remainder')
    for mean, selected in ((F(-1), F(1)), (F(1), F(1)), (F(4), F(2)), (F(9), F(3)), (F(12), F(3))):
        for trial in (F(1), F(3, 2), F(2), F(3)):
            a.eq((mean-selected**2)**2 <= (mean-trial**2)**2, True, 'compact-domain global choice')
    a.eq((4-F(-2)**2, 4-F(2)**2), (F(0), F(0)), 'two globally competing locally regular roots')
    for scale in (2, 3):
        for normalized in (F(-1), F(1)):
            root = normalized/scale
            a.eq(root**3, normalized/scale**3, 'real cube-root sample identity')
            a.eq(root*scale, normalized, 'n^(1/6) normalization')
    a.eq(NormalDist().cdf(.5**3) != NormalDist().cdf(.5), True, 'cube-root Gaussian limit is not standard Gaussian')
    a.interventions.append('Change parameter boundaries, global root multiplicity and derivative rank separately.')

    def ratio(u, vv, strength):
        demand(strength+vv != 0, 'nonzero observed IV denominator')
        return u/(strength+vv)
    v['ex9-error100'] = ratio(F(3, 5), F(-1, 5), F(5))
    v['ex9-error400'] = ratio(F(3, 5), F(-1, 5), F(10))
    v['ex9-weak-error'] = ratio(F(3, 5), F(-1, 5), F(1, 2))
    a.eq(determinant([[F(1), F(1, 2)], [F(1, 2), F(1)]]), F(3, 4), 'nondegenerate Gaussian pair covariance')
    for eps in (F(-1, 100), F(1, 100)):
        a.eq(ratio(F(3, 5), -F(1, 5)+eps, F(1, 5)), F(3, 5)/eps, 'near cancellation can reverse and enlarge error')
    a.reject(lambda: ratio(F(3, 5), F(-1, 5), F(1, 5)), 'zero sample denominator')
    a.interventions.append('Compare fixed and shrinking relevance, then approach the zero denominator from both sides.')

    z4 = [[F(1), F(-1), F(0), F(0)], [F(0), F(0), F(1), F(-1)]]
    abc = quadratic_coefficients(z4, [1, -1, 1, -1], [2, -2, 0, 0])
    a.eq(abc, (F(4), F(4), F(8)), 'worked exact candidate Gram')
    a.eq(acceptance(*abc, 1, 8), ('interval', F(1), F(1)), 'worked full candidate set')
    v.update({'case4-left': F(0), 'case4-right': F(2)})
    for cutoff, kind in ((4, 'singleton'), (3, 'empty')):
        a.eq(acceptance(*abc, 1, cutoff)[0], kind, 'critical boundary')
    for yy, label, kind in (([1, -1, 0, 0], 'case4-constant-small', 'all'), ([3, -3, 0, 0], 'case4-constant-large', 'empty')):
        constant = quadratic_coefficients(z4, [1, 1, -1, -1], yy)
        a.eq(constant[:2], (F(0), F(0)), 'zero projected regressor')
        v[label] = constant[2]
        a.eq(acceptance(*constant, 1, 8), (kind,), 'constant statistic classification')
    a.near(1-exp(-4), .981684, 5e-7, 'confidence coefficient display')
    z10 = [[F(1), F(0), F(0)], [F(0), F(1), F(0)]]
    abc10 = quadratic_coefficients(z10, [1, 1, 1], [2, 4, 0])
    a.eq(abc10, (F(2), F(6), F(20)), 'exercise candidate Gram')
    a.eq(acceptance(*abc10, 1, 8), ('interval', F(3), F(3)), 'exercise exact set')
    rounded['ex10-left'] = 3-sqrt(3); rounded['ex10-right'] = 3+sqrt(3)
    a.eq(acceptance(*abc10, 1, 2), ('singleton', F(3), F(0)), 'exercise singleton')
    a.eq(acceptance(*abc10, 1, 1), ('empty',), 'exercise empty set')
    for yy, kind in (([2, 4, 0], 'empty'), ([1, 1, 0], 'all')):
        constant = quadratic_coefficients(z10, [0, 0, 1], yy)
        a.eq(acceptance(*constant, 1, 8), (kind,), 'exercise no relevance')
    # Nonzero but tiny projection: a finite display grid cannot bound the set.
    small = quadratic_coefficients([[F(1), F(0)]], [F(1, 100), F(1)], [F(1), F(0)])
    a.eq(acceptance(*small, 1, 4), ('interval', F(100), F(40000)), 'small relevance wide exact interval')
    for trial, expected in ((F(-101), False), (F(-100), True), (F(100), True), (F(300), True), (F(301), False)):
        aa, bb, cc = small
        a.eq(aa*trial**2-2*bb*trial+cc <= 4, expected, 'wide interval endpoints and exterior')
    a.interventions.append('Cross quadratic cutoff equality, remove projected relevance, and retain remote finite endpoints.')

    types = [(F(1, 4), 0, 0, F(2), F(10)), (F(1, 4), 1, 1, F(1), F(3)), (F(1, 2), 0, 1, F(4), F(8))]
    base = observed(types, F(1, 2))
    v.update({'case5-y0': base['y'][0], 'case5-y1': base['y'][1], 'case5-late': base['wald'],
              'case5-ate': base['ate'], 'case5-att': base['att']})
    a.eq(base['d'], [F(1, 4), F(3, 4)], 'conditional treatment means')
    a.eq(sum(base['law'].values()), F(1), 'observed joint probability total')
    pz = F(1, 2); ey = sum(p*y for (z, d, y), p in base['law'].items()); ed = base['treated']
    covzy = sum(p*(z-pz)*(y-ey) for (z, d, y), p in base['law'].items())
    covzd = sum(p*(z-pz)*(d-ed) for (z, d, y), p in base['law'].items())
    a.eq(covzy/covzd, base['wald'], 'intercept IV covariance ratio equals LATE')
    defiers = [(F(1, 8), 0, 0, F(2), F(10)), types[1], types[2], (F(1, 8), 1, 0, F(0), F(12))]
    df = observed(defiers, F(1, 2)); dc = observed(types, F(1, 2), F(1, 2))
    v['case5-defier-wald'] = df['wald']; v['case5-direct-wald'] = dc['wald']
    a.eq(df['wald'] < min(row[4]-row[3] for row in defiers), True, 'signed compliance weight leaves effect range')
    a.eq(dc['d'], base['d'], 'direct outcome effect preserves first stage')
    a.eq(dc['ate'], base['ate'], 'direct encouragement channel is not a treatment effect')
    rare = observed(types, F(1, 4))
    altered = observed([(F(1, 4), 0, 0, F(2), F(6)), types[1], types[2]], F(1, 4))
    a.eq(rare['law'], altered['law'], 'every observable cell unchanged by never-treated counterfactual')
    a.eq(rare['ate']-altered['ate'], F(1), 'unidentified ATE changes by one')
    a.eq(rare['wald'], base['wald'], 'encouragement frequency preserves conditional LATE')
    v.update({'ex11-treated': rare['treated'], 'ex11-att': rare['att'], 'ex11-alternative-ate': altered['ate']})
    a.interventions.extend(['Introduce defiers versus a direct encouragement channel under the same assignment law.',
                            'Change assignment frequency and an unobserved counterfactual; distinguish ATT composition from ATE identification.'])
    kr = weights([[F(1)], [F(1)]], [[F(1), F(0)], [F(0), F(1, 9)]])
    beta = dot(kr[0], [F(1), F(3)]); residual = [1-beta, 3-beta]
    v.update({'retention-beta': beta, 'retention-v': covariance(kr, [[F(1), F(0)], [F(0), F(9)]])[0][0],
              'retention-j': 10*(residual[0]**2+residual[1]**2/9)})
    a.eq(acceptance(0, 0, 3, 1, 2), ('empty',), 'retention constant test')

    invalid = [
        (lambda: exact(True), 'boolean'), (lambda: exact(float('nan')), 'nonfinite'),
        (lambda: solve([[1, 2], [2, 4]], [1, 2]), 'unidentified coefficient'),
        (lambda: project([[1, 2], [2, 4]], [1, 1]), 'dependent instruments'),
        (lambda: spd([[F(1), F(2)], [F(2), F(1)]]), 'indefinite covariance'),
        (lambda: spd([[F(1), F(1)], [F(0), F(1)]]), 'asymmetric covariance'),
        (lambda: acceptance(0, 1, 1, 1, 8), 'impossible zero Gram cross term'),
        (lambda: acceptance(1, 2, 1, 1, 8), 'impossible Gram determinant'),
        (lambda: acceptance(1, 0, 1, 0, 8), 'zero known variance'),
        (lambda: acceptance(1, 0, 1, 1, -1), 'negative critical value'),
        (lambda: observed(types, F(0)), 'no assignment overlap'),
        (lambda: observed([(F(1), 0, 0, F(2), F(3))], F(1, 2)), 'zero first stage'),
        (lambda: strict_json('{"a":1,"a":2}'), 'duplicate JSON'),
        (lambda: strict_json('{"a":NaN}'), 'nonfinite JSON'),
        (lambda: strict_json('{"a":1e999}'), 'overflowed JSON number'),
        (lambda: Page().feed('HTML'), 'stray fragment text'),
    ]
    for call, label in invalid: a.reject(call, label)
    return v, rounded


def check(root=None):
    root = Path(root) if root is not None else Path(__file__).resolve().parents[1]
    a = Audit()
    for name, expected in FROZEN.items():
        content = (root/name).read_bytes()
        a.eq((len(content), hashlib.sha256(content).hexdigest()), expected, 'final frozen author '+name)
    page = Page(); page.feed((root/MANUSCRIPT).read_text()); page.close()
    prompts = ['v12-c03-e'+str(i).zfill(2) for i in range(1, 13)]
    a.eq(page.prompts, prompts, 'all exact prompts')
    a.eq(page.solutions, prompts, 'all paired complete solutions')
    a.eq(len(page.worked), 5, 'worked cases')
    a.eq((len(page.ids), len(set(page.ids)), page.stack), (29, 29, []), 'reader identifiers and balanced fragment')
    exact_values, decimals = finite_evidence(a)
    for key, expected in exact_values.items():
        a.eq(F(page.anchors[key].strip().replace('−', '-')), expected, 'independent printed anchor '+key)
    for key, expected in decimals.items():
        a.near(float(page.anchors[key]), expected, 5e-10, 'independent rounded anchor '+key)
    a.eq(set(page.anchors), set(exact_values)|set(decimals), 'all marked numerical values recomputed')
    source = strict_json((root/SOURCES).read_text())
    author = strict_json((root/AUTHOR).read_text())
    record = strict_json((root/RECORD).read_text())
    expected_sources = {'v12-c03-mit-iv2017', 'v12-c03-mit-gmm2017', 'v12-c03-mit-nonlinear2017', 'v12-c03-imbens-angrist1994'}
    a.eq({row['id'] for row in source['proposals']}, expected_sources, 'primary scope identifiers')
    a.eq(set(page.sources), expected_sources, 'source-to-method routes')
    for href in page.links:
        a.eq(href in {'v12-c01.html', 'v12-c02.html'} | {'sources.html#'+s for s in expected_sources}, True, 'flat scoped reader link')
    for owner, rows, expected_paths in (
        ('author', author['reviewed_hashes'], {MANUSCRIPT, AUTHOR_CHECKER, SOURCES}),
        ('peer', record['reviewed_hashes'], set(FROZEN)|{SELF}),
    ):
        a.eq({row['path'] for row in rows}, expected_paths, owner+' exact nonself binding set')
        a.eq(len(rows), len(expected_paths), owner+' no duplicate binding')
        for row in rows:
            payload = (root/row['path']).read_bytes()
            a.eq((len(payload), hashlib.sha256(payload).hexdigest()), (row['bytes'], row['sha256']), owner+' payload '+row['path'])
    a.eq(record['open_findings'], [], 'no unresolved peer finding')
    a.eq(record['decision'], 'pass within declared scope; coordinator acceptance separate', 'bounded peer decision')
    summary = dict(chapter='v12-c03', status='passed', comparisons=a.count,
                   executed_domain_rejections=a.rejected, purposeful_interventions=len(a.interventions),
                   intervention_scopes=a.interventions, exact_numeric_anchors=len(exact_values),
                   rounded_numeric_anchors=len(decimals), worked_cases=5, exercises=12, solutions=12,
                   author_inputs_bound=4, peer_nonself_bindings=5, author_code_used_as_oracle=False,
                   limits='Independent finite evidence and separate full proof/solution reading; no empirical validity, uniform weak or dependent-data theorem, rendered UI, human certification or coordinator acceptance implied.')
    strict_json(json.dumps(summary, allow_nan=False))
    return summary


if __name__ == '__main__':
    print(json.dumps(check(), ensure_ascii=False, allow_nan=False, indent=2))
