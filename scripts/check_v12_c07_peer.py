"""Independent, quiet, read-only finite-contract review of v12-c07.

No author functions or author numerical output are used as an oracle.  Exact
orthogonalization, forward derivatives and half-plane intersections reconstruct
the original contracts.  Analytic proofs and source scope are reviewed separately.
"""
from decimal import Decimal, localcontext
from fractions import Fraction as Q
from html.parser import HTMLParser
from itertools import combinations, product
from pathlib import Path
import hashlib
import json
import math
import re

ROOT = Path(__file__).resolve().parents[1]
AUTHOR = {
    'content/chapters/v12-c07.html': (44031, '43332ecc8582880b3e2ffc9f92980bbb83a55014d4c564a76bcff54cd9d2cee7'),
    'scripts/check_v12_c07.py': (30182, 'a3dde3b958f87e128182dd86d2345db8f31698129552ad1a2d4b4a41c50d47b4'),
    'content/reviews/v12-c07-sources.json': (13293, '25b05577bf982cc536e786714958709d788a2a11ebc19e3cf61196a4943abf70'),
    'content/reviews/v12-c07-author.json': (26964, '2cce28728a625d1ce7fd7dcd3884daeb9d811171c689f1602835db17c2464bf4'),
}
SELF = 'scripts/check_v12_c07_peer.py'
RECORD = 'content/reviews/v12-c07-peer.json'
FILES = tuple(AUTHOR) + (SELF, RECORD)
SOURCE_IDS = {
    'v12-c07-callaway-santanna2020', 'v12-c07-sun-abraham2020',
    'v12-c07-goodman-bacon2020', 'v12-c07-rambachan-roth2023',
}


def need(ok, label):
    if not ok:
        raise ValueError(label)


def exact(x):
    need(type(x) in (int, Q), 'finite exact scalar required')
    need(abs(x) <= 10**6, 'scalar outside finite audit domain')
    return Q(x)


def strict(text):
    def pairs(items):
        result = {}
        for k, v in items:
            need(k not in result, 'duplicate JSON key')
            result[k] = v
        return result
    def constant(value):
        raise ValueError('invalid JSON number: ' + value)
    def decimal(value):
        number = float(value)
        need(math.isfinite(number), 'overflowed JSON number')
        return number
    return json.loads(text, object_pairs_hook=pairs, parse_constant=constant,
                      parse_float=decimal)


class Tally:
    def __init__(self):
        self.comparisons = 0
        self.rejections = 0
        self.anchors = 0

    def equal(self, got, wanted, label):
        self.comparisons += 1
        need(got == wanted, label + ': ' + repr(got) + ' != ' + repr(wanted))

    def close(self, got, wanted, label, tolerance=8e-12):
        self.comparisons += 1
        need(math.isfinite(float(got)) and math.isfinite(float(wanted)), label)
        need(abs(float(got)-float(wanted)) <= tolerance, label)

    def rejected(self, call, label):
        self.comparisons += 1
        try:
            call()
        except ValueError:
            self.rejections += 1
        else:
            raise ValueError('invalid input accepted: ' + label)

    def visible(self, text, value):
        self.equal(compact(str(value)) in compact(text), True,
                   'visible answer ' + str(value))
        self.anchors += 1


def compact(s):
    return re.sub(r'\s+', '', s).replace('−', '-')


class Element:
    def __init__(self, tag, attrs=()):
        self.tag, self.attrs, self.parts = tag, dict(attrs), []

    def text(self):
        return ''.join(p.text() if isinstance(p, Element) else p for p in self.parts)

    def descendants(self):
        for p in self.parts:
            if isinstance(p, Element):
                yield p
                yield from p.descendants()


class Tree(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.root = Element('root')
        self.stack = [self.root]
        self.feed(text)
        self.close()
        need(len(self.stack) == 1, 'unclosed HTML element')

    def handle_starttag(self, tag, attrs):
        e = Element(tag, attrs)
        self.stack[-1].parts.append(e)
        if tag not in {'br', 'hr', 'img', 'meta', 'link', 'input'}:
            self.stack.append(e)

    def handle_endtag(self, tag):
        need(len(self.stack) > 1 and self.stack[-1].tag == tag, 'HTML nesting')
        self.stack.pop()

    def handle_data(self, value):
        self.stack[-1].parts.append(value)


class Tangent:
    """Rational first-order dual number for empirical-mass derivatives."""
    def __init__(self, value, slope=0):
        self.value, self.slope = Q(value), Q(slope)

    @staticmethod
    def cast(x):
        return x if isinstance(x, Tangent) else Tangent(x)

    def __add__(self, x):
        x = self.cast(x)
        return Tangent(self.value+x.value, self.slope+x.slope)

    __radd__ = __add__

    def __neg__(self):
        return Tangent(-self.value, -self.slope)

    def __sub__(self, x):
        return self + -self.cast(x)

    def __rsub__(self, x):
        return self.cast(x) + -self

    def __mul__(self, x):
        x = self.cast(x)
        return Tangent(self.value*x.value, self.slope*x.value+self.value*x.slope)

    __rmul__ = __mul__

    def __truediv__(self, x):
        x = self.cast(x)
        need(x.value != 0, 'zero dual denominator')
        return Tangent(self.value/x.value,
                       (self.slope*x.value-self.value*x.slope)/x.value**2)


def fitted(atoms, weights=None):
    """Recompute the weighted empirical contrast from cell totals alone."""
    need(type(atoms) is list and 4 <= len(atoms) <= 32, 'finite atom table')
    for row in atoms:
        need(type(row) is tuple and len(row) == 4, 'atom shape')
        mass, a, h, y = row
        need(exact(mass) > 0, 'positive atom mass')
        need(type(a) is int and a in (0, 1) and type(h) is int and h in (0, 1),
             'binary integer group/cell')
        exact(y)
    need(sum(r[0] for r in atoms) == 1, 'probability total')
    if weights is None:
        weights = [r[0] for r in atoms]
    need(len(weights) == len(atoms), 'mass direction dimension')
    n, total = {}, {}
    for a, h in product((0, 1), repeat=2):
        terms = [(w, r[3]) for w, r in zip(weights, atoms) if r[1:3] == (a, h)]
        need(bool(terms), 'unobserved group/cell')
        n[a, h] = sum(w for w, _ in terms)
        total[a, h] = sum(w*y for w, y in terms)
    n1 = n[1, 0]+n[1, 1]
    return sum((total[1, h]-n[1, h]*total[0, h]/n[0, h])/n1 for h in (0, 1))


def atomic_law(masses=(Q(1, 8), Q(3, 8), Q(3, 8), Q(1, 8)),
               effects=(2, 4), noise=1):
    exact(noise)
    return [(Q(w, 2), a, h, 1+2*h+a*effects[h]+sign*noise)
            for (a, h), w in zip(((1, 0), (1, 1), (0, 0), (0, 1)), masses)
            for sign in (-1, 1)]


def population_parts(atoms):
    fitted(atoms)
    pi = sum(w*a for w, a, _, _ in atoms)
    mu, p = {}, {}
    for a, h in product((0, 1), repeat=2):
        subset = [r for r in atoms if r[1:3] == (a, h)]
        mu[a, h] = sum(w*y for w, _, _, y in subset)/sum(w for w, *_ in subset)
    for h in (0, 1):
        p[h] = sum(w*a for w, a, cell, _ in atoms if cell == h)/sum(w for w, _, cell, _ in atoms if cell == h)
    return pi, mu, p


def candidate(atoms, ps, ms, normalize_controls=False):
    need(type(ps) is tuple and type(ms) is tuple and len(ps) == len(ms) == 2,
         'two candidate cells')
    ps = tuple(exact(x) for x in ps)
    ms = tuple(exact(x) for x in ms)
    need(all(0 < x < 1 for x in ps), 'strict working overlap')
    pi, _, _ = population_parts(atoms)
    treat = sum(w*a*(y-ms[h]) for w, a, h, y in atoms)/pi
    mass = sum(w*(1-a)*ps[h]/(1-ps[h]) for w, a, h, _ in atoms)
    control = sum(w*(1-a)*ps[h]*(y-ms[h])/(1-ps[h]) for w, a, h, y in atoms)
    return treat-control/(mass if normalize_controls else pi)


def dot(a, b):
    need(len(a) == len(b), 'dot dimensions')
    return sum(x*y for x, y in zip(a, b))


def orthogonalize(columns):
    """Exact Gram–Schmidt; no normal-matrix inverse or author demeaning."""
    need(type(columns) is list and 1 <= len(columns) <= 12, 'column count')
    need(all(type(c) is list for c in columns), 'column sequences')
    n = len(columns[0])
    need(1 <= n <= 20 and all(len(c) == n for c in columns), 'design dimensions')
    cols = [[exact(x) for x in c] for c in columns]
    q, norms = [], []
    for c in cols:
        v = c[:]
        for prev, norm in zip(q, norms):
            coefficient = dot(prev, c)/norm
            v = [x-coefficient*y for x, y in zip(v, prev)]
        norm = dot(v, v)
        need(norm > 0, 'rank deficient design')
        q.append(v)
        norms.append(norm)
    # X=Q R with diagonal R=1. Back substitute whole outcome operators.
    operator = [None]*len(cols)
    for j in range(len(cols)-1, -1, -1):
        row = [v/norms[j] for v in q[j]]
        for k in range(j+1, len(cols)):
            coefficient = dot(q[j], cols[k])/norms[j]
            row = [v-coefficient*w for v, w in zip(row, operator[k])]
        operator[j] = row
    return q, norms, operator


def layout():
    rows = [(g, t) for g in (2, 4, None) for t in range(1, 5)]
    fixed = [[Q(g == cohort) for g, _ in rows] for cohort in (2, 4, None)]
    fixed += [[Q(t == date) for _, t in rows] for date in (2, 3, 4)]
    treated = [Q(g is not None and t >= g) for g, t in rows]
    event = [[Q(g is not None and t-g == k) for g, t in rows]
             for k in (-3, -2, 0, 1, 2)]
    return rows, fixed, treated, event


def contrast_vector(target, control, pre, post):
    v = [Q(0)]*12
    for group, sign in ((target, 1), (control, -1)):
        for times, direction in ((pre, -1), (post, 1)):
            for t in times:
                v[4*group+t-1] += Q(sign*direction, len(times))
    return v


def corners(inequalities):
    need(type(inequalities) is list and 3 <= len(inequalities) <= 8,
         'bounded half-plane list')
    need(all(type(r) is tuple and len(r) == 3 for r in inequalities), 'half-plane shape')
    lines = [tuple(exact(v) for v in r) for r in inequalities]
    vertices = set()
    for (a, b, c), (d, e, f) in combinations(lines, 2):
        det = a*e-b*d
        if det:
            x, y = (c*e-b*f)/det, (a*f-c*d)/det
            if all(u*x+v*y <= w for u, v, w in lines):
                vertices.add((x, y))
    return sorted(vertices)


def restricted_vertices(kind, amount, slope=1, pre_scale=1):
    amount, slope, pre_scale = exact(amount), exact(slope), exact(pre_scale)
    need(0 <= amount <= 4 and pre_scale >= 0, 'sensitivity domain')
    need(kind in {'relative', 'smooth'}, 'declared restriction')
    if kind == 'relative':
        r = amount*pre_scale
        lines = [(1, 0, r), (-1, 0, r), (-1, 1, r), (1, -1, r)]
    else:
        lines = [(1, 0, slope+amount), (-1, 0, amount-slope),
                 (-2, 1, amount), (2, -1, amount)]
    v = corners(lines)
    need(bool(v), 'empty restriction fiber')
    return v


def confidence_box(pre, post, amount):
    need(type(pre) is tuple and type(post) is tuple and len(pre) == len(post) == 2,
         'two interval endpoints')
    pre, post = tuple(map(exact, pre)), tuple(map(exact, post))
    amount = exact(amount)
    need(pre[0] <= pre[1] and post[0] <= post[1] and 0 <= amount <= 4,
         'valid bounded confidence box')
    edge = max(pre, key=abs)
    radius = amount*abs(edge)
    return (post[0]-radius, post[1]+radius), edge, radius


def normal_probability(x):
    """Independent Decimal integral of the Gaussian density, |x|<=3.

    The power-series tail after 120 terms is <1e-100 on this interval;
    55-digit arithmetic and a 50-digit pi dominate that truncation error.
    No NormalDist, erf or author quantile routine is used.
    """
    with localcontext() as context:
        context.prec = 55
        x = Decimal(x)
        need(x.is_finite() and abs(x) <= 3, 'bounded Gaussian integration')
        pi = Decimal('3.14159265358979323846264338327950288419716939937510')
        term = x
        integral = term
        for j in range(1, 121):
            term *= -x*x/(2*j)
            integral += term/(2*j+1)
        return Decimal('0.5') + integral/(2*pi).sqrt()


def known_quantile(probability):
    p = exact(probability)
    need(Q(1, 2) < p < Q(998, 1000), 'quantile in scoped integration bracket')
    with localcontext() as context:
        context.prec = 55
        target = Decimal(p.numerator)/p.denominator
        lo, hi = Decimal(0), Decimal(3)
        for _ in range(85):
            mid = (lo+hi)/2
            if normal_probability(mid) < target:
                lo = mid
            else:
                hi = mid
        return (lo+hi)/2


def eligibility(g, t, anticipation, last_observed, control):
    need(all(type(x) is int for x in (g, t, anticipation, last_observed)),
         'integer calendar inputs')
    need(0 <= anticipation <= 4 and 1 <= g <= t <= last_observed <= 20,
         'calendar order')
    baseline = g-anticipation-1
    need(baseline >= 1, 'unobserved unaffected baseline')
    need(control == 'never' or type(control) is int, 'known adoption status required')
    return baseline, control == 'never' or control > t+anticipation


def numerical(tally, page, answers, tables):
    atoms = atomic_law()
    tau = fitted(atoms)
    pi, mu, ps = population_parts(atoms)
    tally.equal((pi, ps, mu), (Q(1, 2), {0: Q(1, 4), 1: Q(3, 4)},
                {(0, 0): Q(1), (0, 1): Q(3), (1, 0): Q(3), (1, 1): Q(7)}), 'joint cell reconstruction')
    group_means = [sum(w*y for w, a, _, y in atoms if a == group)/sum(w for w, a, _, _ in atoms if a == group)
                   for group in (1, 0)]
    tally.equal((tau, group_means, group_means[0]-group_means[1]),
                (Q(7, 2), [Q(6), Q(3, 2)], Q(9, 2)), 'conditional and raw targets')
    odds = [sum(w*ps[h]/(1-ps[h]) for w, a, cell, _ in atoms if a == 0 and cell == h)
            for h in (0, 1)]
    tally.equal(odds, [Q(1, 8), Q(3, 8)], 'true odds cell masses')
    tally.equal(dot(odds, [mu[0, h] for h in (0, 1)])/sum(odds), Q(5, 2), 'counterfactual mean')
    for p, m in product(((ps[0], ps[1]), (Q(1, 2),)*2), ((mu[0, 0], mu[0, 1]), (0, 0))):
        value = candidate(atoms, p, m)
        bias = sum(w*(ps[h]-p[h])*(mu[0, h]-m[h])/(1-p[h]) for w, _, h, _ in atoms)/pi
        tally.equal(value-tau, bias, 'actual-pi exact remainder')
        tally.equal(value, Q(9, 2) if p == (Q(1, 2),)*2 and m == (0, 0) else tau, 'four candidate combinations')
    tally.equal(candidate(atoms, (Q(1, 3),)*2, (0, 0)), Q(21, 4), 'misspecified odds mass transfer')
    tally.equal(candidate(atoms, (Q(1, 3),)*2, (0, 0), True), Q(9, 2), 'separate normalization changes functional')
    # Differentiate the empirical cell functional rather than inserting a saved IF.
    derivatives = []
    for j in range(len(atoms)):
        direction = [Tangent(r[0], Q(i == j)-r[0]) for i, r in enumerate(atoms)]
        dual = fitted(atoms, direction)
        tally.equal(dual.value, tau, 'same base functional')
        derivatives.append(dual.slope)
    explicit, components = [], []
    for w, a, h, y in atoms:
        d = mu[1, h]-mu[0, h]
        parts = (a*(d-tau)/pi, a*(y-mu[1, h])/pi,
                 -(1-a)*ps[h]*(y-mu[0, h])/(pi*(1-ps[h])))
        components.append(parts)
        explicit.append(sum(parts))
    tally.equal(derivatives, explicit, 'empirical-mass derivative equals claimed influence')
    tally.equal(dot([r[0] for r in atoms], derivatives), 0, 'centered derivative')
    variances = [sum(r[0]*c[j]**2 for r, c in zip(atoms, components)) for j in range(3)]
    tally.equal(variances, [Q(3, 2), Q(2), Q(14, 3)], 'three uncertainty sources')
    for i, j in combinations(range(3), 2):
        tally.equal(sum(r[0]*c[i]*c[j] for r, c in zip(atoms, components)), 0, 'orthogonal uncertainty components')
    covariance = sum((Q(i == j)*atoms[i][0]-atoms[i][0]*atoms[j][0])*derivatives[i]*derivatives[j]
                     for i, j in product(range(8), repeat=2))
    tally.equal(covariance, Q(49, 6), 'multinomial tangent covariance')
    tally.equal(sum(variances[1:]), Q(20, 3), 'wrong omission of estimated composition')
    for changed, wanted in ((atomic_law(noise=0), Q(7, 2)),
                            (atomic_law(effects=(3, 3)), Q(3)),
                            (atomic_law(masses=(Q(1, 4),)*4), Q(3))):
        tally.equal(fitted(changed), wanted, 'noise/effect/composition transfer')
    no_noise = atomic_law(noise=0)
    phi_no_noise = [fitted(no_noise, [Tangent(r[0], Q(i == j)-r[0]) for i, r in enumerate(no_noise)]).slope
                    for j in range(8)]
    tally.equal(sum(r[0]*v*v for r, v in zip(no_noise, phi_no_noise)), Q(3, 2), 'composition remains without outcome noise')

    rows, fixed, treatment, event = layout()
    q, norms, op = orthogonalize(fixed+[treatment])
    y = [Q(v) for row in ((0, 1, 3, 7), (0, 0, 0, 2), (0, 0, 0, 0)) for v in row]
    tally.equal([int(cell) for row in tables[0][1:] for cell in row[1:]], list(y), 'reader outcome table')
    residual12 = [12*v for v in q[-1]]
    tally.equal(residual12, [-5, 3, 3, -1, 1, -3, -3, 5, 4, 0, 0, -4], 'full design treatment residual')
    tally.equal(norms[-1], Q(5, 6), 'treatment residual norm')
    tally.equal(dot(op[-1], y), Q(3, 2), 'full-design coefficient')
    effect_weights = [op[-1][i] for i in (1, 2, 3, 7)]
    tally.equal(effect_weights, [Q(3, 10), Q(3, 10), -Q(1, 10), Q(1, 2)], 'signed effect weights')
    tally.equal(sum(effect_weights), 1, 'effect normalization')
    contrasts = [contrast_vector(0, 2, (1,), (2, 3, 4)),
                 contrast_vector(1, 2, (1, 2, 3), (4,)),
                 contrast_vector(0, 1, (1,), (2, 3)),
                 contrast_vector(1, 0, (2, 3), (4,))]
    values = [dot(v, y) for v in contrasts]
    tally.equal(values, [Q(11, 3), Q(2), Q(2), Q(-3)], 'four declared comparisons')
    contrast_op = orthogonalize(contrasts)[2]
    weights = [dot(v, op[-1]) for v in contrast_op]
    tally.equal(weights, [Q(3, 10), Q(3, 10), Q(1, 5), Q(1, 5)], 'solve comparison weights from full operator')
    tally.equal([sum(weights[j]*contrasts[j][i] for j in range(4)) for i in range(12)], op[-1], 'all-table coefficient identity')
    tally.equal(dot(weights, values), dot(op[-1], y), 'aggregate contrast value')
    root = -sum(op[-1][i]*y[i] for i in range(12) if i != 3)/op[-1][3]
    tally.equal(root, Q(22), 'derived sign threshold')
    for x, wanted in ((Q(43, 2), Q(1, 20)), (root, Q(0)), (Q(23), -Q(1, 10))):
        altered = y[:]; altered[3] = x
        tally.equal(dot(op[-1], altered), wanted, 'positive-effect boundary transfer')

    eq, en, eo = orthogonalize(fixed+event)
    residuals = []
    for c in event:
        residuals.append([c[i]-sum(dot(qj, c)*qj[i]/nj for qj, nj in zip(eq[:6], en[:6])) for i in range(12)])
    gram12 = [[12*dot(c, d) for d in residuals] for c in residuals]
    tally.equal(gram12, [[6, -2, -1, 1, 1], [-2, 6, -5, 1, 1], [-1, -5, 14, -1, -5],
                         [1, 1, -1, 6, -2], [1, 1, -5, -2, 6]], 'complete event Gram')
    printed_operator = [[Q(int(v), 8) for cell in row[1:] for v in re.findall(r'-?\d+', compact(cell))]
                        for row in tables[1][1:]]
    tally.equal(eo[6:], printed_operator, 'all sixty reader operator entries')
    tally.equal([12*n for n in en[6:]], [6, Q(16, 3), Q(17, 2), Q(93, 17), Q(96, 31)], 'orthogonal-norm rank certificate')
    determinant = math.prod(en[6:])
    tally.equal((determinant, determinant*12**5), (Q(1, 54), Q(4608)), 'Gram determinant from volume')
    tally.equal([12*dot(c, y) for c in residuals], [7, 3, -17, 4, 28], 'event outcome cross-products')
    coefficients = [dot(row, y) for row in eo[6:]]
    tally.equal(coefficients, [-Q(3, 8), -Q(1, 8), Q(3, 2), Q(27, 8), Q(57, 8)], 'five event coefficients')
    for i, row in enumerate(eo[6:]):
        tally.equal([dot(row, col) for col in fixed+event], [Q(j == i+6) for j in range(11)], 'full design action')
    for a, b, c, d in ((1, 1, 3, 7), (2, 5, -1, 9), (1, 2, 1, 1)):
        altered = [Q(0), Q(a), Q(c), Q(d), 0, 0, 0, Q(b), 0, 0, 0, 0]
        tally.equal([dot(row, altered) for row in eo[6:]],
                    [Q(3*(a-b), 8), Q(a-b, 8), Q(a+b, 2), c+Q(3*(b-a), 8), d+Q(b-a, 8)],
                    'heterogeneous effect transfer across all columns')
    additive = [Q((0, 5, -2)[i//4]+(1, -3, 8, 2)[i % 4]) for i in range(12)]
    tally.equal([dot(row, [v+w for v, w in zip(y, additive)]) for row in eo[6:]], coefficients,
                'calendar and cohort offsets removed')
    for early in ((1, 3, 7), (1, 1, 1)):
        changing = (Q(early[0]+2, 2), Q(early[1]))
        fixed_e = (Q(early[0]), Q(early[1]))
        tally.equal((changing[1]-changing[0], fixed_e[1]-fixed_e[0]),
                    (Q(3, 2), Q(2)) if early[1] == 3 else (-Q(1, 2), Q(0)), 'aggregation support transfer')

    target, never, late = [1, 4, 8, 9], [1, 2, 3, 4], [1, 2, 5, 9]
    did = lambda b, t, control: target[t-1]-control[t-1]-(target[b-1]-control[b-1])
    tally.equal((did(2, 3, never), did(1, 3, never), did(1, 3, late), did(1, 4, never)),
                (3, 5, 3, 5), 'dated clean and contaminated contrasts')
    for control, eligible in ((4, False), (5, True), ('never', True)):
        tally.equal(eligibility(3, 3, 1, 4, control), (1, eligible), 'strict eligible-control boundary')
    tally.equal(eligibility(3, 4, 1, 4, 6), (1, True), 'known future status beyond observed calendar')

    for kind in ('relative', 'smooth'):
        for amount in (Q(0), Q(1, 2), Q(1)):
            vertices = restricted_vertices(kind, amount)
            outcomes = [(Q(4)-x+Q(6)-y)/2 for x, y in vertices]
            center, multiplier = (Q(5), Q(3, 2)) if kind == 'relative' else (Q(7, 2), Q(2))
            tally.equal((min(outcomes), max(outcomes)), (center-multiplier*amount, center+multiplier*amount), 'half-plane sensitivity extrema')
            for x, y in vertices:
                if kind == 'relative':
                    tally.equal(max(abs(x), abs(y-x)) <= amount, True, 'relative first-difference feasibility')
                else:
                    tally.equal(max(abs(x-1), abs(y-2*x)) <= amount, True, 'curvature feasibility')
                tally.equal([x+(4-x), y+(6-y)], [4, 6], 'constructed observed potential means')
            low = vertices[outcomes.index(min(outcomes))]
            high = vertices[outcomes.index(max(outcomes))]
            for fraction in (Q(0), Q(2, 5), Q(1)):
                x, y = [(1-fraction)*l+fraction*h for l, h in zip(low, high)]
                tally.equal((10-x-y)/2, (1-fraction)*min(outcomes)+fraction*max(outcomes), 'attained interior sharpness witness')
    tally.equal(restricted_vertices('relative', 2, pre_scale=0), [(0, 0)], 'zero preincrement scale')
    tally.equal(restricted_vertices('smooth', 0, slope=-2), [(-2, -4)], 'zero curvature negative trend')
    tally.equal(corners([(1, 0, 0), (-1, 0, -1), (0, 1, 1), (0, -1, 1)]), [], 'incompatible fiber stays empty')
    tally.equal((0+4, 3+1), (4, 4), 'observationally equal post worlds')

    z = known_quantile(Q(79, 80))
    half = z/Decimal(5)
    tally.close(normal_probability(z), Decimal(79)/80, 'independent Gaussian integrated quantile')
    tally.close(half, .448280545521, 'printed coordinate halfwidth')
    tally.equal((Q(1)-Q(1, 40))**2, Q(1521, 1600), 'independent-coordinate joint coverage')
    tally.equal(2*Q(1, 40), Q(1, 20), 'arbitrary-correlation union failure bound')
    tally.equal(Q(39, 40) >= Q(19, 20), True, 'perfect-correlation endpoint coverage')
    decimals = []
    for bound, displayed in ((1, (3.103438908958, 4.896561091042)), (2, (2.655158363437, 5.344841636563))):
        endpoints = [Decimal(4)-Decimal(1+bound)*half, Decimal(4)+Decimal(1+bound)*half]
        for actual, expected in zip(endpoints, displayed):
            tally.close(actual, expected, 'rounded projected endpoint')
            tally.visible(answers[11], format(expected, '.12f'))
        decimals.extend(displayed)
    for pre, post, amount in (((-2, 1), (3, 5), Q(3, 2)), ((2, 3), (-1, 4), Q(1)),
                               ((-3, -2), (4, 4), Q(2)), ((0, 0), (3, 5), Q(2)),
                               ((-2, 1), (3, 5), Q(0))):
        interval, edge, radius = confidence_box(pre, post, amount)
        for fraction in (Q(0), Q(1, 3), Q(1)):
            post_value = (1-fraction)*post[0]+fraction*post[1]
            departure = (1-fraction)*radius-fraction*radius
            tally.equal(abs(departure) <= amount*abs(edge), True, 'projected interior admissibility')
            tally.equal(post_value-departure, (1-fraction)*interval[0]+fraction*interval[1], 'complete projection witness')
    tally.equal(abs(1) <= abs(-1) and abs(1) <= abs(1), True, 'two compatible triples')
    tally.equal(abs(1) <= abs(0), False, 'their midpoint is incompatible: joint nonconvexity')

    anchors = {
        1: ('ATT', 'g−a−1', 'G>t+a', 'interference'),
        2: (tau, Q(9, 2), Q(5, 2), '1/8', '3/8'),
        3: (tau, Q(9, 2), 'actual π', 'different remainder'),
        4: (*variances, covariance, Q(20, 3), 'V/N', 'N_ah=0'),
        5: (norms[-1], *effect_weights, '(22−x)/10', 'x=22', 'x>22'),
        6: (*values, Q(3, 2), '7−(1+3)/2=5', 'FWL operator'),
        7: (*coefficients, determinant, determinant*12**5, '0,0,1,3,7'),
        8: (Q(3, 2), -Q(1, 2), 'difference 0', 'not an observed zero'),
        9: ('(8−4)−(3−2)=3', '(8−1)−(3−1)=5', 'G>3+1', 'unsupported', 't+a>T'),
        10: (Q(17, 4), Q(23, 4), Q(5, 2), Q(9, 2), '{5}', '{7/2}', 'squared period'),
        11: ('α/2', 'union bound', '4−2h', '4+2h', '4−3h', '4+3h', 'different information'),
        12: ('Six distinctions', 'Two repairs', 'Conclusion', '95%', 'sampling uncertainty'),
    }
    for exercise, values in anchors.items():
        for value in values:
            tally.visible(answers[exercise], value)
    for row in gram12:
        tally.visible(page, '('+','.join(str(x) for x in row)+')')
    tally.equal(6+2*2+2, 12, 'open research rubric allocation')
    invalid = [
        (lambda: exact(True), 'boolean scalar'), (lambda: exact(float('nan')), 'nonfinite scalar'),
        (lambda: exact(10**7), 'magnitude'), (lambda: fitted(atoms[:-1]), 'mass total'),
        (lambda: fitted([(Q(1, 4), 1, 0, y) for y in (1, 2, 3, 4)]), 'missing group/cell'),
        (lambda: candidate(atoms, (0, 1), (0, 0)), 'overlap boundary'),
        (lambda: candidate(atoms, (Q(1, 2),), (0, 0)), 'candidate shape'),
        (lambda: orthogonalize([[1, 1], [2, 2]]), 'rank'),
        (lambda: orthogonalize([[1, 0], [1]]), 'ragged design'),
        (lambda: orthogonalize([[True, 0]]), 'boolean design'),
        (lambda: restricted_vertices('other', 1), 'unknown restriction'),
        (lambda: restricted_vertices('smooth', -1), 'negative radius'),
        (lambda: restricted_vertices('relative', 1, pre_scale=-1), 'negative pre scale'),
        (lambda: confidence_box((1, -1), (3, 5), 1), 'reversed box'),
        (lambda: confidence_box((-1, 1), (3, 5), 5), 'bounded projection scope'),
        (lambda: known_quantile(1), 'unbounded Gaussian quantile'),
        (lambda: known_quantile(True), 'boolean probability'),
        (lambda: normal_probability(4), 'Gaussian integration bracket'),
        (lambda: eligibility(1, 3, 1, 4, 'never'), 'missing baseline'),
        (lambda: eligibility(3, 3, True, 4, 5), 'boolean horizon'),
        (lambda: eligibility(3, 4, 1, 4, 'not yet observed'), 'unknown future status'),
        (lambda: eligibility(3, 2, 1, 4, 5), 'pretarget calendar'),
    ]
    for call, label in invalid:
        tally.rejected(call, label)
    return {'joint_atoms': 8, 'directional_derivatives': 8, 'event_design': [12, 11],
            'event_operator_entries': 60, 'conditional_ATT': str(tau),
            'root_variance': str(covariance), 'TWFE_zero_boundary': str(root),
            'event_coefficients': [str(v) for v in coefficients],
            'sensitivity_families': 2, 'independent_Gaussian_halfwidth': float(half)}


def binding(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def check():
    raw = {p: (ROOT/p).read_bytes() for p in FILES}
    tally = Tally()
    for path, (size, digest) in AUTHOR.items():
        tally.equal(binding(raw[path]), {'bytes': size, 'sha256': digest}, 'frozen author '+path)
    root = Tree(raw['content/chapters/v12-c07.html'].decode()).root
    elements = list(root.descendants())
    ids = [e.attrs['id'] for e in elements if 'id' in e.attrs]
    tally.equal(len(ids), len(set(ids)), 'unique chapter IDs')
    prompts = [p for e in elements if e.tag == 'ol' and 'exercises' in e.attrs.get('class', '').split()
               for p in e.parts if isinstance(p, Element) and p.tag == 'li']
    solutions = [e for e in elements if 'data-solution-for' in e.attrs]
    expected = {'v12-c07-e'+str(i) for i in range(1, 13)}
    tally.equal({e.attrs.get('id') for e in prompts}, expected, 'exact twelve prompts')
    tally.equal({e.attrs.get('data-solution-for') for e in solutions}, expected, 'exact twelve solutions')
    tally.equal((len(prompts), len(solutions)), (12, 12), 'no duplicate pairing')
    disclosures = [e for e in elements if e.tag == 'details' and 'solutions' in e.attrs.get('class', '').split()]
    tally.equal(len(disclosures), 1, 'reader answer disclosure')
    tally.equal(sum('data-solution-for' in e.attrs for e in disclosures[0].descendants()), 12, 'all answers inside disclosure')
    tally.equal(sum('worked' in e.attrs.get('class', '').split() for e in elements), 6, 'six complete cases')
    tally.equal(sum(e.tag == 'details' and 'solution' in e.attrs.get('class', '').split() for e in elements), 2, 'answered teaching and retention')
    tally.equal({e.attrs['data-source'] for e in elements if 'data-source' in e.attrs}, SOURCE_IDS, 'four cited scopes')
    source = strict(raw['content/reviews/v12-c07-sources.json'].decode())
    tally.equal({e['id'] for e in source['sources']}, SOURCE_IDS, 'source record matches reader')
    links = [e.attrs['href'] for e in elements if 'href' in e.attrs]
    tally.equal(set(links), {'v12-c01.html', 'v12-c02.html', 'v12-c03.html', 'v12-c05.html',
                'v12-c06.html', 'v12-c08.html'} | {'sources.html#'+s for s in SOURCE_IDS}, 'declared reader routes')
    tables = []
    for table in (e for e in elements if e.tag == 'table'):
        tables.append([[p.text() for p in row.parts if isinstance(p, Element) and p.tag in {'td', 'th'}]
                       for row in table.descendants() if row.tag == 'tr'])
    tally.equal([len(t) for t in tables], [4, 6], 'complete numeric tables')
    answers = {int(e.attrs['data-solution-for'].split('-e')[-1]): e.text() for e in solutions}
    evidence = numerical(tally, root.text(), answers, tables)
    author = strict(raw['content/reviews/v12-c07-author.json'].decode())
    tally.equal(set(author['payloads']), set(AUTHOR)-{'content/reviews/v12-c07-author.json'}, 'author three nonself bindings')
    for path, row in author['payloads'].items():
        tally.equal(row, binding(raw[path]), 'author exact binding')
    peer = strict(raw[RECORD].decode())
    tally.equal(set(peer['payloads']), set(AUTHOR) | {SELF}, 'peer five nonself bindings')
    for path, row in peer['payloads'].items():
        tally.equal(row, binding(raw[path]), 'peer exact binding')
    tally.equal({row['id'] for row in peer['exercise_audit']}, expected, 'every exact prompt reviewed')
    tally.equal(peer['open_findings'], [], 'no unresolved finding at freeze')
    for invalid in ('NaN', 'Infinity', '-Infinity', '1e9999', '{"x":1,"x":2}', '{}{}'):
        tally.rejected(lambda s=invalid: strict(s), 'strict JSON boundary')
    for path in FILES:
        tally.equal((ROOT/path).read_bytes(), raw[path], 'read-only payload '+path)
    summary = {'chapter': 'v12-c07', 'status': 'separate peer finite checks passed',
               'comparisons': tally.comparisons, 'explicit_rejections': tally.rejections,
               'visible_answer_anchors': tally.anchors, 'worked_cases': 6,
               'exact_prompt_solution_pairs': 12, 'primary_source_scopes': 4,
               'independent_evidence': evidence,
               'limits': 'Finite original contracts plus separate proof reading; no empirical parallel-trend validation, generic clustered/uniform inference, rendered UI or human certification.'}
    strict(json.dumps(summary, allow_nan=False))
    return summary


if __name__ == '__main__':
    check()
