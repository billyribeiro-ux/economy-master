"""Original bounded Form A audit. Standard library; four read-only payloads.

check(root=None) returns a strict JSON-safe summary; successful import/API/CLI
are silent. No chapter, source artifact, proposal or saved numeric oracle is
needed at runtime. Generic parsers/guards adapt the frozen C11 peer helpers.
"""
import ast
from collections import defaultdict
from fractions import Fraction as Q
from html.parser import HTMLParser
from itertools import product, combinations
import hashlib
import json
import math
from pathlib import Path

FILES = ('content/assessments/parts/v12-exam-a.html', 'scripts/check_v12_exam_a.py',
         'content/reviews/v12-exam-a-sources.json', 'content/reviews/v12-exam-a-author.json')
SOURCE_IDS = {'v12-c01-mit-limit-tools', 'v12-c04-counts1999',
              'v12-c06-aronow-samii-interference', 'v12-c07-callaway-santanna2020',
              'v12-c08-cattaneo-titiunik2022', 'v12-c09-mit-vars',
              'v12-c11-dml-v7', 'v12-c11-bh1995', 'asa-pvalues-2016', 'v04-c01-aea-data-faq'}
POINTS = [4, 6, 6, 4, 6, 7, 7, 5, 7, 8, 8, 6, 6, 5, 8, 7]
PARTS = ['v12-a-q'+str(c)+part for c, letters in [(1,'abcd'),(2,'abc'),(3,'abc'),(4,'abc'),(5,'abc')] for part in letters]

def require(condition, message):
    if not condition:
        raise ValueError('V12 Form A: ' + message)


def finite(x):
    require(type(x) in (int, float, Q), 'numeric scalar excluding bool')
    try:
        y = float(x)
    except (OverflowError, ValueError):
        raise ValueError('V12 Form A: unrepresentable scalar') from None
    require(math.isfinite(y) and abs(y) <= 10**12, 'bounded finite scalar')
    return Q(str(x)) if type(x) is float else Q(x)


def law(values, positive=False):
    require(isinstance(values, (list, tuple)) and 1 <= len(values) <= 12,
            'bounded finite probability vector')
    p = [finite(x) for x in values]
    require(sum(p) == 1 and all(x > 0 if positive else x >= 0 for x in p),
            'normalized nonnegative probability law')
    return p


def strict_json(raw):
    def pairs(items):
        out = {}
        for k, v in items:
            require(k not in out, 'duplicate JSON key')
            out[k] = v
        return out
    def bad(x):
        raise ValueError('V12 Form A: nonfinite JSON token ' + x)
    out = json.loads(raw, object_pairs_hook=pairs, parse_constant=bad)
    def scan(x):
        if isinstance(x, float):
            require(math.isfinite(x), 'overflowed JSON number')
        elif isinstance(x, dict):
            for v in x.values(): scan(v)
        elif isinstance(x, list):
            for v in x: scan(v)
    scan(out)
    return out


def mean(x):
    require(bool(x), 'nonempty mean')
    return sum(x, Q(0))/len(x)


def score(y, d, e, g0, g1):
    require(type(d) is int and d in (0, 1), 'binary treatment')
    y, e, g0, g1 = map(finite, (y, e, g0, g1))
    require(0 < e < 1, 'candidate overlap')
    return g1-g0+d*(y-g1)/e-(1-d)*(y-g0)/(1-e)


def step_up(values, q):
    require(isinstance(values, (list, tuple)) and 1 <= len(values) <= 12, 'bounded nonempty testing family')
    p, q = [finite(x) for x in values], finite(q)
    require(0 < q < 1 and all(0 <= x <= 1 for x in p), 'testing probabilities')
    m = len(p)
    # Threshold counts give the same fixed point without using an ordered loop.
    R = max([0]+[r for r in range(1, m+1) if sum(v <= q*r/m for v in p) >= r])
    return [i for i, v in enumerate(p) if R and v <= q*R/m]


class Evidence:
    def __init__(self):
        self.comparisons = 0
        self.rejections = []

    def same(self, actual, expected, label):
        require(actual == expected, label)
        self.comparisons += 1

    def close(self, actual, expected, label, tolerance=8e-12):
        if isinstance(expected, (list, tuple)):
            require(isinstance(actual, (list, tuple)) and len(actual) == len(expected), label+' shape')
            for a, b in zip(actual, expected): self.close(a, b, label, tolerance)
        elif type(actual) in (int, Q) and type(expected) in (int, Q):
            self.same(actual, expected, label+' exact')
        else:
            a, b = float(actual), float(expected)
            require(math.isfinite(a) and math.isfinite(b) and abs(a-b) <= tolerance*max(1., abs(b)), label)
            self.comparisons += 1

    def reject(self, call, label):
        try:
            call()
        except (ValueError, TypeError, SyntaxError):
            self.rejections.append(label)
            self.comparisons += 1
        else:
            raise ValueError('V12 Form A: missing rejection '+label)


def expression(raw):
    require(isinstance(raw, str) and len(raw) < 350, 'bounded visible expression')
    tree = ast.parse(raw.replace('−', '-').strip(), mode='eval')
    require(len(list(ast.walk(tree))) < 120, 'bounded expression tree')
    def parse(n):
        if isinstance(n, ast.Expression): return parse(n.body)
        if isinstance(n, ast.Constant) and type(n.value) in (int, float):
            return finite(n.value) if type(n.value) is int else float(finite(n.value))
        if isinstance(n, ast.Tuple): return [parse(x) for x in n.elts]
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.USub, ast.UAdd)):
            return -parse(n.operand) if isinstance(n.op, ast.USub) else parse(n.operand)
        if isinstance(n, ast.BinOp) and isinstance(n.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
            a, b = parse(n.left), parse(n.right)
            if isinstance(n.op, ast.Add): return a+b
            if isinstance(n.op, ast.Sub): return a-b
            if isinstance(n.op, ast.Mult): return a*b
            require(b != 0, 'nonzero visible denominator')
            return a/b
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in ('sqrt', 'log'):
            require(len(n.args) == 1 and not n.keywords, 'unary safe square root')
            x = float(parse(n.args[0]))
            require(x > 0 if n.func.id == 'log' else x >= 0, 'safe function domain')
            return math.log(x) if n.func.id == 'log' else math.sqrt(x)
        raise ValueError('V12 Form A: unsupported visible expression')
    return parse(tree)


def ratio(numerator, denominator):
    a, b = finite(numerator), finite(denominator)
    require(b != 0, 'observed zero denominator is a failure')
    return a/b


def panel(beta):
    beta = finite(beta)
    require(-2 <= beta <= 2, 'bounded positive-count panel scope')
    rows = []
    for z, u, e1, e2 in product((-1, 1), repeat=4):
        alpha, x1, x2 = 10+2*z, 0, z+u
        y1, y2 = alpha+e1, alpha+beta*x2+u+e2
        rows.append((z, x2-x1, y1, y2, y2-y1, u+e2-e1))
    dx2 = mean([x*x for _, x, _, _, _, _ in rows])
    dxdy = mean([r[1]*r[4] for r in rows])
    zdx, zdy = [mean([r[0]*r[j] for r in rows]) for j in (1, 4)]
    scores = [r[0]*r[5] for r in rows]
    ymean = mean([r[3] for r in rows])
    yvar = mean([(r[3]-ymean)**2 for r in rows])
    lagdx, lagv, lagdy = [mean([r[2]*r[j] for r in rows]) for j in (1, 5, 4)]
    return rows, [dx2, dxdy, ratio(dxdy, dx2)], [zdx, zdy, mean([v*v for v in scores])], [ymean, yvar], [lagdx, lagv, ratio(lagdy, lagdx)]


def poisson_fit(counts):
    require(isinstance(counts, (list, tuple)) and 1 <= len(counts) <= 32, 'bounded count sample')
    y = [finite(v) for v in counts]
    require(all(v >= 0 and v.denominator == 1 for v in y), 'nonnegative integer counts')
    require(sum(y) > 0, 'all-zero sample has no finite log-mean maximum')
    return math.log(float(mean(y)))


def pilot(assignment):
    require(len(assignment) == 2 and all(type(v) is int and v in (0, 1) for v in assignment), 'binary pilot assignment')
    a, b = assignment
    outcomes = [2+a+2*b, 4+3*b+a]
    statistic = sum(Q(2)*((assignment[i] == 1 and assignment[1-i] == 0)
                        -(assignment[i] == 0 and assignment[1-i] == 0))*outcomes[i] for i in (0, 1))
    return outcomes, statistic


def did_effect(t):
    t = finite(t)
    require(-1 <= t <= 1, 'coupled trend-departure interval')
    # Construct the treated untreated-post means from baseline plus changed trend.
    counterfactual = [1+t, 6-t]
    effects = [5-counterfactual[0], 9-counterfactual[1]]
    return Q(3, 4)*effects[0]+Q(1, 4)*effects[1]


def cutoff_world(always0, never1):
    a0, n1 = finite(always0), finite(never1)
    require(0 <= a0 <= 20 and 0 <= n1 <= 20, 'bounded cutoff potential outcomes')
    masses = [Q(1, 5), Q(3, 5), Q(1, 5)]
    pairs = [(a0, 4), (2, 5), (5, n1)]
    observed = defaultdict(Q)
    means, receipts = [], []
    # Uniform R independent of type: each half has mass 1/2, and conditional
    # R is uniform within its half. Observed values are constant there by type.
    for side in (0, 1):
        ds = [1, side, 0]
        means.append(sum(w*p[d] for w, p, d in zip(masses, pairs, ds)))
        receipts.append(sum(w*d for w, d in zip(masses, ds)))
        for w, p, d in zip(masses, pairs, ds): observed[side, d, p[d]] += w/2
    ate = sum(w*(p[1]-p[0]) for w, p in zip(masses, pairs))
    return means, receipts, ate, dict(observed)


def innovation_maps(n):
    require(type(n) is int and 1 <= n <= 8, 'bounded consecutive forecast origins')
    return [{(t+2, 0):Q(1), (t+1, 0):Q(1, 2), (t+1, 1):Q(1, 4)} for t in range(n)]


def covariance_maps(maps):
    return [[sum(v*b.get(k, 0) for k, v in a.items()) for b in maps] for a in maps]


def policy_mean(b):
    b = finite(b)
    require(Q(1, 2) <= b <= 1, 'admissible structural curve')
    c = Q(1, 4)/b
    return 2+2*b*(c-Q(1, 4)), c


def fit_folds(rows):
    require(isinstance(rows, (list, tuple)) and 2 <= len(rows) <= 32, 'bounded fold data')
    data = []
    for row in rows:
        require(len(row) == 3, 'fold/D/Y row shape')
        k, d, y = row
        require(type(k) is int and k in (0, 1) and type(d) is int and d in (0, 1), 'binary fold and treatment')
        y = finite(y)
        require(abs(y) <= 7, 'outcome theorem bound')
        data.append((k, d, y))
    require({r[0] for r in data} == {0, 1}, 'both held-out folds nonempty')
    fits = []
    for held in (0, 1):
        train = [r for r in data if r[0] != held]
        e = min(Q(3, 4), max(Q(1, 4), Q(sum(r[1] for r in train)+1, len(train)+2)))
        gs = []
        for d in (0, 1):
            ys = [r[2] for r in train if r[1] == d]
            gs.append(min(Q(7), max(Q(-7), mean(ys))) if ys else Q(0))
        fits.append([e]+gs)
    values = [score(y, d, *fits[k]) for k, d, y in data]
    estimate = mean(values)
    variance = mean([(v-estimate)**2 for v in values])
    folds = [mean([v for v, r in zip(values, data) if r[0] == k]) for k in (0, 1)]
    return fits, values, folds, estimate, variance


RAW = [(1, 'v1', True, 60, 60), (2, 'v1', True, 40, 0),
       (3, 'v1', True, 20, 40), (4, 'draft', False, 20, 20), (4, 'v2', True, 0, 20)]


def approved_rows(raw):
    require(isinstance(raw, (list, tuple)) and 4 <= len(raw) <= 12, 'bounded versioned records')
    out = {}
    for row in raw:
        require(len(row) == 5, 'versioned record shape')
        i, version, approved, a, b = row
        require(type(i) is int and i in (1, 2, 3, 4), 'roster key')
        require(type(version) is str and bool(version) and type(approved) is bool, 'explicit version and approval')
        a, b = finite(a), finite(b)
        require(a.denominator == b.denominator == 1, 'integer tenths')
        if approved:
            require(i not in out, 'exactly one approved record per school')
            out[i] = (a/10, b/10)
    require(set(out) == {1, 2, 3, 4}, 'approved keys equal roster')
    return [out[i] for i in (1, 2, 3, 4)]


def contrast(values, treated):
    require(len(values) == 4 and len(treated) == 2 and len(set(treated)) == 2
            and all(type(i) is int and 0 <= i < 4 for i in treated), 'four-school balanced assignment')
    y = [finite(v) for v in values]
    return mean([v for i, v in enumerate(y) if i in treated])-mean([v for i, v in enumerate(y) if i not in treated])


def selected(a, b):
    a, b = finite(a), finite(b)
    return (abs(a), 0) if abs(a) >= abs(b) else (abs(b), 1)


def target_effect(k):
    require(type(k) is int and 3 <= k <= 9, 'admitted unreleased integer roster count')
    effects = [-1]*(12-k)+[3]*k
    return mean(effects)


def reconstruct():
    e, out = Evidence(), {}
    rows, ols, iv, moments, lag = panel(2)
    for z, x, y1, y2, dy, v in rows:
        e.same(dy, 2*x+v, 'panel difference cancels the unit effect')
        e.same(y2 > 0 and y2.denominator == 1, True, 'true positive count support')
    out.update({'panel-ols':ols, 'panel-iv':iv, 'panel-count-moments':moments,
                'panel-qml-variances':[moments[1]/moments[0]**2, 1/moments[0]], 'panel-lag':lag})
    e.close(poisson_fit([r[3] for r in rows]), math.log(10), 'actual finite log-mean maximizer')
    e.same(mean([r[0]*r[5] for r in rows]), 0, 'IV centering')
    e.same(panel(0)[1][2], Q(1, 2), 'changed structural truth changes projection target')
    e.same(panel(0)[2][1], 0, 'changed truth changes valid moment target')
    e.same(panel(0)[4][2], Q(-1, 2), 'lag bias persists after changed truth')
    # The mean-criterion gap from its optimum is 10*(exp(h)-1-h)>0 for h!=0.
    for h in (-1., .5):
        e.same(10*(math.exp(h)-1-h) > 0, True, 'strict global expected criterion loss')

    assignments = [(0, 0), (1, 0), (0, 1), (1, 1)]
    pilot_rows = [pilot(z) for z in assignments]
    ht = [r[1] for r in pilot_rows]
    direct = ((pilot((1, 0))[0][0]-pilot((0, 0))[0][0])
             +(pilot((0, 1))[0][1]-pilot((0, 0))[0][1]))/2
    e.same(mean(ht), direct, 'finite exposure-unbiasedness identity')
    e.same(mean([(v-mean(ht))**2 for v in ht]), 90, 'finite pilot variance cross-check')
    out['pilot-statistics'] = ht
    out['pilot-total-effect'] = mean([a-b for a, b in zip(pilot((1, 1))[0], pilot((0, 0))[0])])
    treated, comparison = [5, 5], [1, 2]
    out['did-targets'] = [mean(treated)-(Q(1, 4)*comparison[0]+Q(3, 4)*comparison[1]), did_effect(0)]
    out['did-range'] = [did_effect(1), did_effect(-1)]
    for t in (Q(-1), Q(0), Q(1, 3), Q(1)):
        e.same(did_effect(t), Q(15, 4)-t/2, 'counterfactual-mean sensitivity construction')
    w1, w2 = cutoff_world(1, 8), cutoff_world(6, 12)
    e.same(w1[3], w2[3], 'full observed cutoff law equal in two complete worlds')
    e.same(sum(w1[3].values()), 1, 'uniform-score half/type atom total')
    jump_d, jump_y = w1[1][1]-w1[1][0], w1[0][1]-w1[0][0]
    out['cutoff-local'] = w1[0]+[jump_d, jump_y, ratio(jump_y, jump_d)]
    out['cutoff-global'] = [w1[2], w2[2]]

    A = [[Q(1, 2), Q(1, 4)], [Q(0), Q(1, 2)]]
    out['input-var-A'] = A
    apply = lambda v: [sum(a*x for a, x in zip(row, v)) for row in A]
    first = apply([4, 2]); second = apply(first)
    out['var-means'] = [first, second]
    out['var-covariance'] = [[Q(i == j)+sum(A[i][k]*A[j][k] for k in (0, 1)) for j in (0, 1)] for i in (0, 1)]
    maps = innovation_maps(4); covariance = covariance_maps(maps)
    out['overlap-covariance'] = covariance
    # Independent coordinate map for the actual mean, versus covariance summation.
    average_map = defaultdict(Q)
    for row in maps:
        for key, value in row.items(): average_map[key] += value/4
    variance = sum(v*v for v in average_map.values())
    e.same(variance, sum(map(sum, covariance))/16, 'direct mean coordinate norm versus covariance sum')
    out['overlap-variances'] = [variance, covariance[0][0]/4]
    out['policy-range'] = [policy_mean(1)[0], policy_mean(Q(1, 2))[0]]
    for m in (Q(2), Q(17, 8), Q(9, 4)):
        b = 5-2*m; actual, c = policy_mean(b)
        e.same(b*c, Q(1, 4), 'observational-equivalence curve')
        e.same(actual, m, 'policy inverse construction')
    e.same(policy_mean(1)[1]-Q(1, 4), 0, 'zero post-policy c endpoint admitted')

    observed = [(0, 0, 0), (0, 1, 2), (1, 0, 1), (1, 0, 3), (1, 1, 5), (1, 1, 7)]
    fits, scores, folds, estimate, variance = fit_folds(observed)
    out.update({'fold-fits':fits, 'fold-scores':scores, 'fold-means':folds+[estimate, mean(folds)],
                'fold-variances':[variance, variance/6]})
    e.same(estimate, folds[0]/3+2*folds[1]/3, 'actual unequal-fold observation weights')
    e.same(fit_folds(observed[::-1])[1], scores[::-1], 'record reordering with fixed fold labels')
    y0, y1 = [0, 1, 3], [2, 5, 7]
    m0, m1 = mean(y0), mean(y1)
    v0, v1 = mean([(y-m0)**2 for y in y0]), mean([(y-m1)**2 for y in y1])
    oracle = [score(hi if d else lo, d, Q(1, 2), m0, m1) for lo, hi, d in product(y0, y1, (0, 1))]
    e.same(len(oracle), 18, 'complete equiprobable oracle law')
    e.same(mean(oracle), m1-m0, 'oracle ATE identity')
    oracle_var = mean([(v-mean(oracle))**2 for v in oracle])
    e.same(oracle_var, 2*(v0+v1), 'latent-atom variance versus conditional variance')
    out['oracle-moments'] = [m0, m1, v0, v1]
    out['oracle-variances'] = [oracle_var, oracle_var/6]
    e.same(Q(1, 2)-Q(1, 6)-Q(2, 5), Q(-1, 15), 'inference-scale product exponent')
    for d, endpoint in [(0, Q(1, 4)), (1, Q(3, 4))]:
        fit = fit_folds([(0, 0, 0)]+[(1, d, 1)]*3)[0][0]
        e.same(fit[0], endpoint, 'active propensity clipping and empty opposite cell')
        e.same(fit[2-d], 0, 'empty outcome cell uses zero')
    pvalues = [Q(2, 125), Q(23, 1000), Q(39, 1000), Q(1, 5)]
    out['input-pvalues'] = pvalues
    out['bh-full'] = [i+1 for i in step_up(pvalues, Q(1, 20))]
    out['bh-trimmed'] = [i+1 for i in step_up(pvalues[:-1], Q(1, 20))]
    out['minimum-cdf'] = 1-(1-Q(1, 20))**4
    e.same(out['minimum-cdf'] > Q(1, 20), True, 'selected minimum fails ordinary super-uniformity')
    e.same(step_up([Q(1, 40), Q(1, 40)], Q(1, 20)), [0, 1], 'inclusive BH tie')
    e.same(step_up([1, 1], Q(1, 20)), [], 'no BH rejection')

    approved = approved_rows(RAW)
    av, bv = [r[0] for r in approved], [r[1] for r in approved]
    out['approved-vectors'] = [av, bv]
    out['approved-contrasts'] = [contrast(v, (0, 1)) for v in (av, bv)]
    out['unfiltered-contrasts'] = [mean([Q(r[j], 10) for r in RAW if r[0] in (1, 2)])
                                 -mean([Q(r[j], 10) for r in RAW if r[0] not in (1, 2)]) for j in (3, 4)]
    pairs = list(combinations(range(4), 2))
    orbit = [[contrast(v, pair) for v in (av, bv)] for pair in pairs]
    rule = [selected(*r) for r in orbit]
    maxima = [r[0] for r in rule]
    pfull = [Q(sum(m >= value for m in maxima), 6) for value in maxima]
    pnaive = [Q(sum(abs(row[j]) >= m for row in orbit), 6) for m, j in rule]
    out['assignment-orbit'] = orbit; out['selected-scores'] = maxima
    out['selection-pvalues'] = [pnaive[0], pfull[0]]
    out['selection-sizes'] = [Q(sum(p <= Q(1, 3) for p in pnaive), 6), Q(sum(p <= Q(1, 3) for p in pfull), 6)]
    for alpha in (Q(0), Q(1, 3), Q(2, 3), Q(1)):
        e.same(Q(sum(p <= alpha for p in pfull), 6) <= alpha, True, 'inclusive rank law at every attainable boundary')
    e.same(selected(-2, 2), (2, 0), 'selection tie goes to endpoint A')
    lattice = [target_effect(k) for k in range(3, 10)]
    out['target-lattice'] = lattice; out['target-envelope'] = [min(lattice), max(lattice)]
    e.same(Q(1, 6) in lattice, False, 'sharp real envelope is not the exact integer completion set')
    for k, effect in zip(range(3, 10), lattice):
        potential0 = [1]*(12-k)+[0]*k; potential1 = [0]*(12-k)+[3]*k
        e.same(mean([b-a for a, b in zip(potential0, potential1)]), effect, 'target potential-outcome attainment')

    bad = [
        (lambda:finite(True), 'boolean number'), (lambda:finite(float('nan')), 'nonfinite number'),
        (lambda:finite(float('inf')), 'infinite number'), (lambda:finite(10**400), 'oversized number'),
        (lambda:ratio(1, 0), 'actual zero ratio denominator'), (lambda:panel(3), 'panel scope'),
        (lambda:poisson_fit([0, 0]), 'unattained finite QMLE'), (lambda:poisson_fit([Q(1, 2)]), 'fractional count'),
        (lambda:pilot((True, 0)), 'boolean assignment'), (lambda:did_effect(2), 'sensitivity outside interval'),
        (lambda:cutoff_world(1, 21), 'cutoff outcome bound'), (lambda:innovation_maps(9), 'forecast budget'),
        (lambda:innovation_maps(True), 'boolean forecast count'), (lambda:policy_mean(Q(1, 4)), 'structural curve domain'),
        (lambda:fit_folds(observed[:2]), 'missing training fold'), (lambda:fit_folds([(0, 0, 8), (1, 1, 2)]), 'outcome bound'),
        (lambda:score(1, 1, 0, 0, 1), 'zero overlap'), (lambda:step_up([], Q(1, 20)), 'empty family'),
        (lambda:step_up([2], Q(1, 20)), 'invalid p-value'), (lambda:step_up([0], 0), 'invalid testing target'),
        (lambda:approved_rows(RAW+[RAW[0]]), 'duplicate approved scientific key'),
        (lambda:approved_rows(RAW[:-1]), 'missing approved roster member'),
        (lambda:approved_rows([(1, 'v1', 1, 60, 60)]+RAW[1:]), 'ambiguous approval metadata'),
        (lambda:contrast(av, (0, 0)), 'duplicate assigned unit'),
        (lambda:target_effect(Q(7, 2)), 'fractional unreleased count'), (lambda:target_effect(10), 'outside roster information')]
    for call, label in bad: e.reject(call, label)
    for raw in ['{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}', '{"x":1e400}']:
        e.reject(lambda raw=raw:strict_json(raw), 'strict JSON '+raw)
    tables = {
        'v12-a-did-input':[['Treated','0','0','5','3/4'],['Treated','1','4','9','1/4'],['Comparison','0','1','2','1/4'],['Comparison','1','6','8','3/4']],
        'v12-a-cutoff-input':[['Always','1/5','(1,4)','(6,4)'],['Complier','3/5','(2,5)','(2,5)'],['Never','1/5','(5,8)','(5,12)']],
        'v12-a-fold-input':[[str(x) for x in row] for row in observed],
        'v12-a-raw-input':[[str(x).lower() if type(x) is bool else str(x) for x in row] for row in RAW]}
    return out, tables, e


class Reader(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack=[]; self.ids=[]; self.links=[]; self.sources=[]; self.active=[]
        self.prompts={}; self.solutions={}; self.points={}; self.grading={}; self.values={}
        self.tables={}; self.table=None; self.row=[]; self.cell=None

    def handle_starttag(self, tag, attrs):
        a=dict(attrs); classes=a.get('class','').split()
        require(tag not in ('script','iframe','h1'), 'static assessment fragment')
        if 'id' in a:self.ids.append(a['id'])
        if 'href' in a:self.links.append(a['href'])
        if 'data-source' in a:self.sources.append(a['data-source'])
        store=None
        if tag=='li' and any(t=='ol' and 'exercises' in c for t,c in self.stack):
            store=self.prompts; target=a.get('id')
            require(a.get('data-points','').isdigit(),'explicit integer prompt points')
            self.points[target]=int(a['data-points'])
        elif tag=='li' and any(t=='details' and 'solutions' in c for t,c in self.stack):
            store=self.solutions; target=a.get('data-solution-for')
        if store is not None:
            require(target is not None and target not in store,'unique paired prompt/answer')
            store[target]=''; self.active.append((len(self.stack),store,target))
        if 'data-calc' in a:
            key=a['data-calc']; require(key not in self.values,'unique numeric marker')
            self.values[key]=''; self.active.append((len(self.stack),self.values,key))
        if 'data-score' in a:
            key=next((k for _,s,k in self.active if s is self.solutions),None)
            require(key is not None and key not in self.grading,'one grading split per solution')
            self.grading[key]=[int(x) for x in a['data-score'].split(',')]
            require(all(x>0 for x in self.grading[key]),'positive point components')
        if tag=='table':
            require(self.table is None and 'id' in a,'identified nonnested table')
            self.table=a['id']; self.tables[self.table]=[]
        if tag=='tr':self.row=[]
        if tag=='td':self.cell=''
        if tag not in ('br','hr','img','meta','link','input'):self.stack.append((tag,classes))

    def handle_endtag(self, tag):
        require(bool(self.stack) and self.stack[-1][0]==tag,'balanced assessment markup')
        if tag=='td':self.row.append(' '.join(self.cell.split())); self.cell=None
        if tag=='tr' and self.row:self.tables[self.table].append(self.row); self.row=[]
        if tag=='table':self.table=None
        self.stack.pop(); self.active=[v for v in self.active if v[0]<len(self.stack)]

    def handle_data(self, data):
        require(bool(self.stack) or not data.strip(),'no stray reader text')
        if self.cell is not None:self.cell+=data
        for _,store,key in self.active:store[key]+=data


def snapshot(root, paths):
    out=[]
    for path in paths:
        raw=(root/path).read_bytes()
        out.append({'path':path,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
    return out


def check(root=None):
    base=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    out,tables,e=reconstruct()
    raw=(base/FILES[0]).read_text(); page=Reader(); page.feed(raw); page.close()
    e.same(list(page.prompts),PARTS,'all sixteen exact prompt IDs')
    e.same(list(page.solutions),PARTS,'all sixteen paired solutions')
    e.same([page.points[k] for k in PARTS],POINTS,'exact points by part')
    e.same(sum(POINTS),100,'one hundred total points')
    for c in range(1,6):e.same(sum(v for k,v in page.points.items() if k.startswith('v12-a-q'+str(c))),20,'twenty-point essential domain')
    for key in PARTS:
        e.same(sum(page.grading[key]),page.points[key],'solution grading reconciles '+key)
        e.same(len(page.prompts[key])>80 and len(page.solutions[key])>400,True,'complete prompt/answer '+key)
    e.same(page.stack,[],'closed fragment'); e.same(page.active,[],'closed captures')
    e.same(len(page.ids),len(set(page.ids)),'unique reader IDs')
    e.same({'form-a','solutions-a'}.issubset(page.ids),True,'assessment integration anchors')
    e.same(set(out),set(page.values),'complete numeric display coverage')
    for key,value in out.items():e.close(expression(page.values[key]),value,'visible '+key)
    for key,value in tables.items():e.same(page.tables[key],value,'actual input table '+key)
    for text in ['α=10+2Z','X₂=Z+U','Y₁=α+E₁','Y₂=α+βX₂+U+E₂',
                 'teaching truth for calculations is β=2','Y₁(z)=2+z₁+2z₂','Y₂(z)=4+3z₂+z₁',
                 'uniformly distributed on [−1,1], independent of principal type',
                 'uniform on {0,1,3} and {2,5,7}', 'before assignment and outcome access']:
        e.same(text.casefold() in raw.casefold(),True,'visible primitive law '+text)
    e.same(set(page.sources),SOURCE_IDS,'scoped method citations')
    e.same(set(page.links),{'sources.html#'+s for s in SOURCE_IDS},'flat source routes')
    sources=strict_json((base/FILES[2]).read_text())
    e.same({r['id'] for r in sources['reused_sources']},SOURCE_IDS,'source reuse coverage')
    e.same(sources['new_primary_retrieval'],False,'no invented fresh primary reading')
    author=strict_json((base/FILES[3]).read_text())
    e.same(author['reviewed_hashes'],snapshot(base,FILES[:3]),'three nonself author bindings')
    e.same([r['id'] for r in author['part_audit']],PARTS,'all sixteen author audits')
    for row in author['part_audit']:
        prompt=' '.join(page.prompts[row['id']].split())
        e.same(row['prompt_sha256'],hashlib.sha256(prompt.encode()).hexdigest(),'exact author-audited prompt '+row['id'])
    e.same(author['open_findings'],[],'no unresolved author finding')
    for candidate in ['__import__("os")','1/0','sqrt(-1)']:
        e.reject(lambda candidate=candidate:expression(candidate),'restricted displayed expression')
    result={'volume':'v12','form':'A','status':'passed','comparisons':e.comparisons,
            'scored_parts':16,'solutions':16,'points':100,'domains':5,'points_per_domain':20,
            'visible_calculation_markers':len(out),'visible_input_tables':len(tables),
            'panel_atoms':16,'pilot_assignments':4,'complete_cutoff_worlds':2,
            'oracle_atoms':18,'sharp_null_assignments':6,'target_roster_completions':7,
            'executed_rejections':len(e.rejections),'nonself_author_bindings':3,
            'limits':'Exact original finite laws and bounded procedures plus separately read proofs/solutions. No calibrated timing/equating, empirical identification, arbitrary learner inference, fresh source-body inspection, rendered UI or component acceptance is certified.'}
    strict_json(json.dumps(result,allow_nan=False))
    return result


if __name__=='__main__':
    check()


