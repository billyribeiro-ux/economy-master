"""Bounded original-contract reconstruction for structural estimation.

No network, random draws, source PDFs, saved numeric oracle, prior chapter or
shared verifier is needed at runtime. Import and a successful CLI are silent.
The separate author record documents proof reading; this checker is not a
general structural estimator or a substitute for identification arguments.
"""
import ast
from fractions import Fraction as F
from html.parser import HTMLParser
from itertools import product
import hashlib
import json
from math import exp, isclose, isfinite, log, sqrt
from pathlib import Path

HTML = 'production/v12-c10-working.html'
SELF = 'production/check_v12_c10_working.py'
SOURCES = 'production/v12-c10-sources-working.json'
REVIEW = 'production/v12-c10-author-review-working.json'


def need(ok, message):
    if not ok:
        raise ValueError('v12-c10: ' + message)


def number(x):
    need(type(x) in (int, float, F), 'real numeric value excluding bool')
    try:
        finite = isfinite(float(x))
    except (ValueError, OverflowError):
        finite = False
    need(finite, 'finite representable numeric value')
    return F(str(x)) if type(x) is float else F(x)


def positive_integer(n):
    need(type(n) is int and n > 0, 'strict positive integer')
    return n


def vector(x):
    need(isinstance(x, (list, tuple)) and len(x) > 0, 'nonempty vector')
    return [number(t) for t in x]


def matrix(x):
    need(isinstance(x, (list, tuple)) and len(x) > 0, 'nonempty matrix')
    out = [vector(row) for row in x]
    need(all(len(row) == len(out[0]) for row in out), 'rectangular matrix')
    return out


def transpose(A):
    return [list(row) for row in zip(*A)]


def mm(A, B):
    A, B = matrix(A), matrix(B)
    need(len(A[0]) == len(B), 'conformable matrix product')
    return [[sum(x*y for x, y in zip(row, col)) for col in zip(*B)] for row in A]


def mv(A, x):
    A, x = matrix(A), vector(x)
    need(len(A[0]) == len(x), 'conformable matrix vector product')
    return [sum(a*b for a, b in zip(row, x)) for row in A]


def solve(A, b):
    A, b = matrix(A), vector(b)
    n = len(A)
    need(len(A[0]) == n and len(b) == n, 'square linear system')
    aug = [row+[value] for row, value in zip(A, b)]
    for k in range(n):
        pivots = [i for i in range(k, n) if aug[i][k] != 0]
        need(bool(pivots), 'nonsingular linear system')
        j = pivots[0]
        aug[k], aug[j] = aug[j], aug[k]
        d = aug[k][k]
        aug[k] = [x/d for x in aug[k]]
        for i in range(n):
            if i != k:
                d = aug[i][k]
                aug[i] = [x-d*y for x, y in zip(aug[i], aug[k])]
    return [row[-1] for row in aug]


def mean(x):
    x = vector(x)
    return sum(x)/len(x)


def cov(x, y):
    x, y = vector(x), vector(y)
    need(len(x) == len(y), 'paired covariance records')
    mx, my = mean(x), mean(y)
    return mean([(a-mx)*(b-my) for a, b in zip(x, y)])


def market(A, b, c, d, g, z, tax=0):
    A, b, c, d, g, z, tax = map(number, (A, b, c, d, g, z, tax))
    need(b > 0 and d > 0, 'positive demand and supply slopes')
    return solve([[b, 1], [-d, 1]], [A, c-g*z-d*tax])


def projection(G, m, weights, sigma):
    G, m, weights, sigma = matrix(G), vector(m), vector(weights), vector(sigma)
    need(len(G) == len(m) == len(weights) == len(sigma), 'moment dimensions')
    need(all(w > 0 for w in weights), 'positive diagonal criterion weights')
    need(all(s >= 0 for s in sigma), 'nonnegative known moment variances')
    W = [[weights[i] if i == j else F(0) for j in range(len(G))] for i in range(len(G))]
    S = [[sigma[i] if i == j else F(0) for j in range(len(G))] for i in range(len(G))]
    normal = mm(mm(transpose(G), W), G)
    rhs = mm(transpose(G), W)
    A = transpose([solve(normal, col) for col in transpose(rhs)])
    theta = mv(A, m)
    residual = [y-f for y, f in zip(m, mv(G, theta))]
    loss = sum(w*r*r for w, r in zip(weights, residual))
    V = mm(mm(A, S), transpose(A))
    return dict(normal=normal, A=A, theta=theta, residual=residual, loss=loss, V=V)


def competitive_quantity(price, a, b):
    price, a, b = map(number, (price, a, b))
    need(b > 0, 'strictly increasing linear marginal cost')
    return max(F(0), (price-a)/b)


def simulation_variance(N, R, shared):
    N, R = positive_integer(N), positive_integer(R)
    need(type(shared) is bool, 'explicit simulation coupling flag')
    return F(1, N) + (F(1, R) if shared else F(1, N*R))


def difference_variance(R, h, common):
    R, h = positive_integer(R), number(h)
    need(h > 0 and type(common) is bool, 'positive difference step and explicit coupling')
    return F(0) if common else F(2, R)/h**2


def binary_atoms(p, truth, amplitude=F(1, 5)):
    p, truth, amplitude = map(number, (p, truth, amplitude))
    need(0 < amplitude < F(1, 2), 'positive bounded simulation amplitude')
    need(amplitude < p < 1-amplitude, 'positive simulated binary probabilities')
    need(0 <= truth <= 1, 'Bernoulli probability')
    rows = []
    for y, z in product((0, 1), (-1, 1)):
        mass = (truth if y else 1-truth)/2
        q = p+amplitude*z
        score = F(y)/q-F(1-y)/(1-q)
        curvature = F(y)/q**2+F(1-y)/(1-q)**2
        rows.append((mass, q, score, curvature, y))
    return rows


def binary_stats(p, truth):
    rows = binary_atoms(p, truth)
    score = sum(w*s for w, q, s, H, y in rows)
    H = sum(w*curvature for w, q, s, curvature, y in rows)
    omega = sum(w*(s-score)**2 for w, q, s, H, y in rows)
    Q = sum(float(w)*(y*log(float(q))+(1-y)*log(float(1-q))) for w, q, s, H, y in rows)
    return score, H, omega, Q


def bisection(f, left, right, iterations=90):
    left, right = float(number(left)), float(number(right))
    positive_integer(iterations)
    need(left < right, 'ordered root bracket')
    fl, fr = f(left), f(right)
    need(isfinite(fl) and isfinite(fr) and fl*fr <= 0, 'finite sign-changing bracket')
    if fl == 0:
        return left
    if fr == 0:
        return right
    for _ in range(iterations):
        mid = (left+right)/2
        fm = f(mid)
        need(isfinite(fm), 'finite root function')
        if fm == 0 or mid in (left, right):
            return mid
        if fl*fm < 0:
            right = mid
        else:
            left, fl = mid, fm
    return (left+right)/2


def binary_target(truth):
    truth = number(truth)
    need(0 <= truth <= 1, 'Bernoulli target domain')
    lo, hi = F(1, 4), F(3, 4)
    if binary_stats(lo, truth)[0] <= 0:
        return float(lo)
    if binary_stats(hi, truth)[0] >= 0:
        return float(hi)
    return bisection(lambda p: float(binary_stats(p, truth)[0]), lo, hi)


def indirect_estimate(D, upper=3):
    D, upper = number(D), number(upper)
    need(upper > 0, 'positive binding upper bound')
    return sqrt(float(min(upper**2, max(F(0), D))))


def indirect_law(H, theta, shared=True, upper=3):
    H, theta, upper = positive_integer(H), number(theta), number(upper)
    need(0 < theta < upper, 'interior binding parameter for regular law')
    need(type(shared) is bool, 'explicit covariate coupling')
    observed = F(2)
    simulated = 1+F(1, H) if shared else F(2, H)
    cross = F(1) if shared else F(0)
    difference = observed+simulated-2*cross
    return observed, simulated, cross, difference, difference/(4*theta**2)


def logsum(a, b):
    a, b = float(number(a)), float(number(b))
    m = max(a, b)
    return m+log(exp(a-m)+exp(b-m))


def choice_inputs(beta, r, c):
    beta, r, c = map(lambda x: float(number(x)), (beta, r, c))
    need(0 <= beta < 1 and c >= 0, 'discounted choice model with nonnegative deterioration')
    need(abs(r) <= 20 and c <= 20, 'bounded numerical utility domain')
    return beta, r, c


def bellman(beta, r, c, tol=1e-13):
    beta, r, c = choice_inputs(beta, r, c)
    tol = float(number(tol))
    need(tol > 0, 'positive residual tolerance')
    v = [0., 0.]
    for _ in range(100000):
        new = [logsum(-c*s+beta*v[1], -r+beta*v[0]) for s in (0, 1)]
        v = new
        residual = max(abs(logsum(-c*s+beta*v[1], -r+beta*v[0])-v[s]) for s in (0, 1))
        if residual <= tol:
            probs = [exp((-r+beta*v[0])-logsum(-c*s+beta*v[1], -r+beta*v[0])) for s in (0, 1)]
            return v, probs, residual
    raise ValueError('v12-c10: residual target not reached')


def scalar_choice(beta, r, c):
    """Independent ratio equation: x=exp(V1-V0), no Bellman iteration."""
    beta, r, c = choice_inputs(beta, r, c)
    A, B = exp(-r), exp(-c)
    if c == 0:
        x = 1.
    else:
        x = bisection(lambda x: (x-B)*x**beta+A*(x-1), B, 1.)
    v0 = log(x**beta+A)/(1-beta)
    v1 = v0+log(x)
    return [v0, v1], [A/(x**beta+A), A/(B*x**beta+A)]


def inverse_choice(p0, p1, beta):
    p0, p1, beta = map(lambda x: float(number(x)), (p0, p1, beta))
    need(0 < p0 < 1 and 0 < p1 < 1 and 0 <= beta < 1, 'interior choices and discount')
    delta = log(p0/p1)
    k0, k1 = log((1-p0)/p0), log((1-p1)/p1)
    need(k0 >= k1, 'nonnegative deterioration implied by observed choices')
    return k0-beta*delta, k0-k1, delta


def equilibrium_curve(q, b):
    """Evaluate the centered curve with its exact reflection symmetry.

    This preserves the paired fold levels at machine precision, instead of
    misclassifying a reflected tangency because of one rounding unit.
    """
    q, b = float(number(q)), float(number(b))
    need(0 < q < 1, 'interior logit curve domain')
    if q > .5:
        return -equilibrium_curve(1-q, b)
    return log(q/(1-q))-b*(q-.5)


def equilibrium_roots(b, h):
    """All roots on analytic monotonic intervals of the declared bounded model."""
    b, h = float(number(b)), float(number(h))
    need(0 <= b <= 8 and abs(h) <= 1, 'bounded logit-interaction root domain')
    fun = lambda q: equilibrium_curve(q, b)-h
    cuts = [1e-12, 1-1e-12]
    if b > 4:
        gap = sqrt(1-4/b)
        lower = (1-gap)/2
        cuts = [cuts[0], lower, 1-lower, cuts[1]]
    roots = []
    for a, c in zip(cuts, cuts[1:]):
        fa, fc = fun(a), fun(c)
        if fa == 0 and a not in roots:
            roots.append(a)
        if fa*fc < 0:
            roots.append(bisection(fun, a, c))
        if fc == 0 and c not in roots:
            roots.append(c)
    need(bool(roots), 'at least one located equilibrium')
    return sorted(roots)


def branch_derivative(q, b):
    q, b = float(number(q)), float(number(b))
    need(0 < q < 1, 'interior equilibrium probability')
    denominator = 1-b*q*(1-q)
    need(abs(denominator) > 1e-12, 'regular branch away from numerical fold tolerance')
    return q*(1-q)/denominator


def strict(text):
    def pairs(items):
        out = {}
        for k, v in items:
            need(k not in out, 'unique JSON keys')
            out[k] = v
        return out
    def bad(x):
        raise ValueError('v12-c10: nonfinite JSON token ' + x)
    obj = json.loads(text, object_pairs_hook=pairs, parse_constant=bad)
    def scan(x):
        if isinstance(x, float):
            need(isfinite(x), 'finite JSON number')
        elif isinstance(x, dict):
            for v in x.values():
                scan(v)
        elif isinstance(x, list):
            for v in x:
                scan(v)
    scan(obj)
    return obj


def displayed_value(text):
    tree = ast.parse(text.strip().replace('−', '-'), mode='eval')
    def visit(node):
        if isinstance(node, ast.Expression):
            return visit(node.body)
        if isinstance(node, ast.Constant):
            return number(node.value)
        if isinstance(node, ast.Tuple):
            return [visit(v) for v in node.elts]
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            return -visit(node.operand) if isinstance(node.op, ast.USub) else visit(node.operand)
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
            a, b = visit(node.left), visit(node.right)
            if isinstance(node.op, ast.Add):
                return a+b
            if isinstance(node.op, ast.Sub):
                return a-b
            if isinstance(node.op, ast.Mult):
                return a*b
            need(b != 0, 'nonzero displayed denominator')
            return a/b
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ('sqrt', 'log'):
            need(len(node.args) == 1 and not node.keywords, 'unary displayed function')
            x = float(visit(node.args[0]))
            need(x >= 0 if node.func.id == 'sqrt' else x > 0, 'displayed function domain')
            return sqrt(x) if node.func.id == 'sqrt' else log(x)
        raise ValueError('v12-c10: unsupported displayed expression')
    return visit(tree)


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.ids, self.links, self.sources = [], [], [], []
        self.prompts, self.targets = [], []
        self.answers, self.values = {}, {}
        self.worked, self.exercise_count, self.solution_count = 0, 0, 0
        self.marker, self.answer = None, None
        self.h1 = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        classes = a.get('class', '').split()
        need(tag not in ('script', 'iframe'), 'static chapter markup')
        if tag == 'h1':
            self.h1 += 1
        if 'id' in a:
            self.ids.append(a['id'])
        if 'href' in a:
            self.links.append(a['href'])
        if 'data-source' in a:
            self.sources.append(a['data-source'])
        if 'worked' in classes:
            self.worked += 1
        if tag == 'li' and any(t == 'ol' and 'exercises' in c for t, c in self.stack):
            self.exercise_count += 1
            self.prompts.append(a.get('id'))
        if tag == 'li' and any(t == 'details' and 'solutions' in c for t, c in self.stack):
            self.solution_count += 1
            target = a.get('data-solution-for')
            need(target is not None and target not in self.answers, 'unique solution target')
            self.targets.append(target)
            self.answers[target] = ''
            self.answer = (target, len(self.stack))
        if 'data-calc' in a:
            key = a['data-calc']
            need(self.marker is None and key not in self.values, 'unique unnested calculation marker')
            self.values[key] = ''
            self.marker = (key, len(self.stack))
        if tag not in ('br', 'hr', 'img', 'meta', 'link', 'input'):
            self.stack.append((tag, classes))

    def handle_endtag(self, tag):
        need(self.stack and self.stack[-1][0] == tag, 'balanced semantic markup')
        self.stack.pop()
        if self.marker and len(self.stack) == self.marker[1]:
            self.marker = None
        if self.answer and len(self.stack) == self.answer[1]:
            self.answer = None

    def handle_data(self, text):
        need(bool(self.stack) or not text.strip(), 'no stray top-level text')
        if self.marker:
            self.values[self.marker[0]] += text
        if self.answer:
            self.answers[self.answer[0]] += text


class Audit:
    def __init__(self):
        self.comparisons = 0
        self.interventions, self.rejections = [], []

    def eq(self, actual, expected, label):
        need(actual == expected, label)
        self.comparisons += 1

    def near(self, actual, expected, label, tol=2e-9):
        if isinstance(expected, (list, tuple)):
            need(isinstance(actual, (list, tuple)) and len(actual) == len(expected), label+' shape')
            for a, e in zip(actual, expected):
                self.near(a, e, label, tol)
        else:
            need(isfinite(float(actual)) and isfinite(float(expected)), label+' finite')
            need(isclose(float(actual), float(expected), rel_tol=tol, abs_tol=tol), label)
            self.comparisons += 1

    def reject(self, action, label):
        try:
            action()
        except (ValueError, TypeError, SyntaxError):
            self.comparisons += 1
            self.rejections.append(label)
        else:
            raise ValueError('v12-c10: expected rejection: '+label)

    def intervention(self, label):
        self.interventions.append(label)


def calculate(a):
    out = {}
    # Exact simultaneous equations for every atom; regressions are solved via
    # full normal systems, not the manuscript's partial-regression arithmetic.
    atoms = []
    for w, z, u, v in product((-1, 1), repeat=4):
        p, q = market(10+w+u, 2, 1+v, 1, 1, z)
        a.eq(q, 10+w-2*p+u, 'atom demand identity')
        a.eq(q, 1+p-z+v, 'atom supply identity')
        atoms.append(list(map(F, (w, z, u, v)))+[p, q])
    w, z, u, v, p, q = map(list, zip(*atoms))
    out['supply-means'] = [mean(p), mean(q)]
    out['cost-covs'] = [cov(z, p), cov(z, q)]
    out['demand-covs'] = [cov(w, p), cov(w, q)]
    slopes = []
    for control in (w, z):
        design = [[1, pi, xi] for pi, xi in zip(p, control)]
        slopes.append(solve(mm(transpose(design), design), mv(transpose(design), q))[1])
    out['demand-ols'], out['supply-ols'] = slopes
    taxed = [market(10+wi+ui, 2, 1+vi, 1, 1, zi, 1) for wi, zi, ui, vi, pi, qi in atoms]
    out['tax-rich'] = [mean([row[j] for row in taxed]) for j in (0, 1)]
    family = []
    for d in (F(1), F(1, 2), F(2)):
        c, g = 4-3*d, (2+d)/3
        for zi in (-1, 0, 1):
            a.eq(market(10, 2, c, d, g, zi), [3+F(zi, 3), 4-F(2*zi, 3)], 'entire cost-only mapping')
        family.append(market(10, 2, c, d, g, 0, 1))
    out['tax-family1'], out['tax-family2'], out['e2-d2-tax'] = family
    calibrated_d = 3*F(5, 6)-2
    out['e2-calibrated-d'] = calibrated_d
    out['e2-calibrated-tax'] = market(10, 2, 4-3*calibrated_d, calibrated_d, F(5, 6), 0, 1)
    out['e1-iv'] = [cov(z, q)/cov(z, p), cov(w, q)/cov(w, p)]
    invalid = [x+y for x, y in zip(z, u)]
    out['e1-invalid-iv'] = cov(invalid, q)/cov(invalid, p)
    a.eq(cov(invalid, u), 1, 'invalid instrument actually correlates with disturbance')
    a.intervention('Independent shifters versus cost-only calibration and invalid instrument')
    # Weighted normal equations, exact covariance and a separately perturbed fit.
    G, m, S = [[1, 0], [1, 1], [1, 2]], [1, 3, 6], [1, F(1, 2), 1]
    fit = projection(G, m, [1, 2, 1], S)
    for suffix, key in [('normal', 'normal'), ('map', 'A'), ('target', 'theta'), ('residual', 'residual'), ('loss', 'loss'), ('covariance', 'V')]:
        out['md-'+suffix] = fit[key]
    aa, bb = fit['theta']
    quantity = competitive_quantity(5, aa, bb)
    grad = [-1/bb, -quantity/bb]
    sensitivity = mv(transpose(fit['A']), grad)
    out['md-output'], out['md-gradient'] = quantity, sensitivity
    out['md-delta-variance'] = sum(x*y for x, y in zip(grad, mv(fit['V'], grad)))
    perturbed = projection(G, [1, 3, F(61, 10)], [1, 2, 1], S)
    out['md-perturbed'] = competitive_quantity(5, *perturbed['theta'])
    out['md-exact-change'] = out['md-perturbed']-quantity
    out['md-linear-change'] = sensitivity[2]/10
    a.eq(mv(transpose(G), [w*r for w, r in zip([1, 2, 1], fit['residual'])]), [0, 0], 'weighted projection orthogonality')
    changed_weight = projection(G, m, [1, 1, 1], S)
    out['e3-target'], out['e3-loss'] = changed_weight['theta'], changed_weight['loss']
    out['e3-output'] = competitive_quantity(5, *changed_weight['theta'])
    a.eq(changed_weight['theta'] != fit['theta'], True, 'weights alter misspecified target')
    a.eq(competitive_quantity(0, aa, bb), 0, 'nonnegative output corner')
    a.intervention('Moment perturbation, changed minimum-distance weights and output corner')
    mc = lambda q, k: 1+2*q+k*q*(q-1)*(q-2)
    out['extrapolation-outputs'] = [competitive_quantity(13, 1, 2), F(3)]
    for k in (F(0), F(1, 2), F(1)):
        for qi in (0, 1, 2):
            a.eq(mc(qi, k), 1+2*qi, 'perfect fit for different extrapolations')
        root = bisection(lambda q: float(mc(q, k)-13), 3, 6)
        a.near(mc(root, float(k)), 13, 'global output crossing')
        a.eq(3 <= root <= 6, True, 'monotone output range')
    out['e4-policy-derivative'] = -F(3*2*1, 2-1+3*(3-1)**2)
    a.intervention('Strictly increasing nonlinear technology with identical observed moments')
    # Sampling and simulation sums are reconstructed from their coefficients.
    out['sim-independent-variance'] = simulation_variance(100, 4, False)
    out['sim-shared-variance'] = simulation_variance(100, 4, True)
    out['sim-fd-variance'] = difference_variance(4, F(1, 100), False)
    out['sim-crn-derivative'], out['sim-crn-variance'] = F(1), difference_variance(4, F(1, 100), True)
    out['e5-variances'] = [simulation_variance(80, 5, False), simulation_variance(80, 5, True)]
    out['e5-fd'], out['e5-crn'] = difference_variance(5, F(1, 50), False), difference_variance(5, F(1, 50), True)
    a.eq(simulation_variance(100, 4, True)-simulation_variance(100000, 4, True), F(999, 100000), 'data growth leaves common simulation floor')
    a.eq(difference_variance(4, F(1, 100), False)/100, 50, 'N independent row differences divide variance')
    a.intervention('Coupling across rows versus coupling across parameter trials, with changed N R h')
    truth = F(9, 25)
    target = F(binary_target(truth)).limit_denominator(1000)
    score, H, Omega, Q = binary_stats(target, truth)
    a.eq(score, 0, 'computed rational pseudo-target solves expected score')
    out.update({'msl-score-truth': binary_stats(truth, truth)[0], 'msl-target': target,
                'mle-target': truth, 'msl-bias': target-truth, 'msl-H': H,
                'msl-Omega': Omega, 'msl-variance': Omega/H**2, 'mle-variance': truth*(1-truth)})
    a.eq(binary_stats(F(1, 4), truth)[0] > 0 > binary_stats(F(3, 4), truth)[0], True, 'interior pseudo-maximum bracket')
    a.eq(Q > binary_stats(truth, truth)[3], True, 'simulated criterion prefers wrong target')
    a.eq(Q < float(truth)*log(float(target))+float(1-truth)*log(float(1-target)), True, 'strict Jensen criterion bias')
    symmetric = F(binary_target(F(1, 2))).limit_denominator(1000)
    score, Hhalf, Ohalf, Qhalf = binary_stats(symmetric, F(1, 2))
    cross = sum((1/(symmetric+F(z, 5))+1/(1-symmetric-F(z, 5)))/2 for z in (-1, 1))
    out.update({'e6-target': symmetric, 'e6-H': Hhalf, 'e6-cross-derivative': cross,
                'e6-target-derivative': cross/Hhalf, 'e6-variance': Ohalf/Hhalf**2})
    a.eq(score, 0, 'symmetric expected score')
    a.eq(Qhalf < log(.5), True, 'strict Jensen bias without parameter shift')
    step = 1e-5
    a.near((binary_target(.5+step)-binary_target(.5-step))/(2*step), cross/Hhalf, 'independent pseudo-target derivative', 2e-8)
    a.eq([binary_target(0), binary_target(1)], [.25, .75], 'boundary likelihood optima need not have zero score')
    a.intervention('Symmetric truth, local target response and endpoint Bernoulli laws')
    # Enumerated two-sign average verifies simulator positivity and the
    # expectation bound without Monte Carlo or a blanket rate theorem.
    for R in (1, 2, 4):
        absolute = F(0)
        for signs in product((-1, 1), repeat=R):
            zbar = mean(signs)
            absolute += abs(zbar)/2**R
            a.eq(F(1, 4)+zbar/5 >= F(1, 20), True, 'growing R simulator lower probability')
            a.eq(F(3, 4)+zbar/5 <= F(19, 20), True, 'growing R simulator upper probability')
        a.eq(absolute**2 <= F(1, R), True, 'exact sign law Cauchy bound')
    a.intervention('Increasing sign averages preserve the uniform log-probability domain')
    # Shared-X coefficient law, not independent marginal-variance addition.
    X, Y = [-1, 0, 1, 0], [0, 2, 4, 3]
    streams = [[-1, 0, 1, 2], [-1, 0, 0, 1]]
    ybar, ubar = mean(Y), mean([x for row in streams for x in row])
    D = ybar-mean(X)-ubar
    out.update({'ii-ymean': ybar, 'ii-umean': ubar, 'ii-D': D, 'ii-estimate': indirect_estimate(D)})
    observed, simulated, cross, diff, tv = indirect_law(2, F(3, 2))
    out.update({'ii-observed-var': observed, 'ii-sim-var': simulated, 'ii-cross': cross,
                'ii-diff-var': diff, 'ii-theta-var': tv,
                'ii-wrong-independent': (observed+simulated)/9,
                'ii-wrong-blanket': observed*F(3, 2)/9, 'ii-boundary-atom': F(1, 2)})
    fresh = indirect_law(2, F(3, 2), False)
    out['e7-difference-variance'], out['e7-theta-variance'] = fresh[3:]
    out['e8-signed-estimates'] = [-sqrt(float(D)), sqrt(float(D))]
    a.eq(observed+simulated-2*cross, diff, 'joint covariance cancellation')
    a.eq(fresh[2], 0, 'fresh-X experiment removes cross covariance')
    for z in (F(-1), F(0), F(1)):
        # Exact transformed-law identities at both boundaries; N is a fourth power.
        N = 10000
        a.near(N**.25*indirect_estimate(z/100), sqrt(float(max(0, z))), 'zero-boundary fourth-root identity')
        top = sqrt(N)*(indirect_estimate(9+z/100)-3)
        denominator = sqrt(float(9+z/100))+3
        a.near(top, float(min(z, 0))/denominator, 'upper-boundary clipped identity')
    a.eq(indirect_estimate(-2), 0, 'negative sample binding clips to zero')
    a.eq(indirect_estimate(10), 3, 'upper sample binding clips to three')
    a.intervention('Fresh versus shared covariates, sign roots and both clipping boundaries')
    # Dynamic closed candidate, independent scalar ratio oracle, policy transfer
    # and exact matrix derivatives, including a zero-deterioration boundary.
    beta, r, c = .5, log(5), log(20/11)
    vv, probs, residual = bellman(beta, r, c)
    v_scalar, p_scalar = scalar_choice(beta, r, c)
    a.near(vv, v_scalar, 'Bellman versus scalar reduction')
    a.near(probs, p_scalar, 'choice probability versus scalar reduction')
    a.near(vv, [0, log(16/25)], 'exact fixed-point candidate')
    p0, p1 = F(4, 20), F(5, 16)
    a.near(probs, [p0, p1], 'forward model equals observed replacement fractions')
    out['dynamic-v0'], out['dynamic-v1'] = 0, log(16/25)
    out['dynamic-probs'] = [p0, p1]
    P = [[p0, 1-p0], [p1, 1-p1]]
    out['dynamic-transition'] = P
    stationary = [p1/(1-p0+p1), (1-p0)/(1-p0+p1)]
    out['dynamic-stationary'] = stationary
    out['dynamic-replace-rate'] = sum(x*y for x, y in zip(stationary, [p0, p1]))
    a.eq(mv(transpose(P), stationary), stationary, 'invariant distribution equation')
    out['dynamic-ll'] = 4*log(float(p0))+16*log(float(1-p0))+5*log(float(p1))+11*log(float(1-p1))
    inverse = [[F(i == j)-F(1, 2)*P[i][j] for j in range(2)] for i in range(2)]
    vr = solve(inverse, [-p0, -p1])
    vc = solve(inverse, [0, -(1-p1)])
    dlog = [[-1+F(1, 2)*(vr[0]-vr[1]), s+F(1, 2)*(vc[0]-vc[1])] for s in (0, 1)]
    dp = [[p*(1-p)*d for d in row] for p, row in zip([p0, p1], dlog)]
    out['dynamic-dV'], out['dynamic-dlogit'], out['dynamic-dp'] = transpose([vr, vc]), dlog, dp
    out['e10-dVc'], out['e10-dpc'] = vc, [row[1] for row in dp]
    for j in (0, 1):
        step = 1e-5
        plus, minus = [r, c], [r, c]
        plus[j] += step
        minus[j] -= step
        vp, pp = scalar_choice(beta, *plus)
        vm, pm = scalar_choice(beta, *minus)
        for i in (0, 1):
            a.near((vp[i]-vm[i])/(2*step), out['dynamic-dV'][i][j], 'independent value derivative')
            a.near((pp[i]-pm[i])/(2*step), dp[i][j], 'independent probability derivative')
    out['dynamic-subsidy'] = scalar_choice(.5, r-log(2), c)[1]
    out['static-subsidy'] = [F(1, 3), F(10, 21)]
    for b in (0, .5, .9):
        rr, cc, delta = inverse_choice(p0, p1, b)
        vfit, pfit = scalar_choice(b, rr, cc)
        a.near(pfit, [p0, p1], 'unknown-discount observational equivalence')
        vi, pi, err = bellman(b, rr-log(2), cc)
        vs, ps = scalar_choice(b, rr-log(2), cc)
        a.near(pi, ps, 'discount and subsidy intervention')
        a.eq(max(abs(x-y) for x, y in zip(vi, vs)) <= err/(1-b)+2e-12, True, 'residual value certificate')
    a.near(scalar_choice(0, log(4)-log(2), c)[1], out['static-subsidy'], 'static subsidy fractions')
    vzero, pzero, _ = bellman(.5, r, 0)
    a.near(vzero[0], vzero[1], 'no deterioration gives identical states')
    a.near(pzero[0], pzero[1], 'no deterioration gives identical probabilities')
    a.eq(dp[0][1] != 0, True, 'continuation derivative matters even in state zero')
    a.intervention('Unknown discount family, subsidy responses and zero deterioration')
    # A common utility shift moves values by k/(1-beta), never the policy.
    shift = .7/(1-beta)
    shifted = [x+shift for x in vv]
    for s in (0, 1):
        a.near(.7+logsum(-c*s+beta*shifted[1], -r+beta*shifted[0]), shifted[s], 'common shock location shift')
    bv, delta = F(9, 10), F(1, 1000)
    out['e9-value-bound'] = delta/(1-bv)
    out['e9-log-bound'] = 2*bv*delta/(1-bv)
    out['e9-sum-bound'] = 36*out['e9-log-bound']
    # Perturb the exact candidate deliberately and test actual likelihood error.
    approximate = [vv[0]+.01, vv[1]-.02]
    err = max(abs(logsum(-c*s+beta*approximate[1], -r+beta*approximate[0])-approximate[s]) for s in (0, 1))
    for s in (0, 1):
        lp = -r+beta*approximate[0]-logsum(-c*s+beta*approximate[1], -r+beta*approximate[0])
        a.eq(abs(lp-log(probs[s])) <= 2*beta*err/(1-beta)+1e-12, True, 'deliberately inexact likelihood certificate')
    a.intervention('Common shock shift and deliberately inexact value with a likelihood bound')
    # Fold locations split a complete root search; no opaque solver output is
    # treated as a proof of uniqueness or an economic selection rule.
    b = 4*log(3)
    baseline = equilibrium_roots(b, 0)
    lower_critical = (1-sqrt(1-4/b))/2
    critical = [lower_critical, 1-lower_critical]
    curve = lambda q: equilibrium_curve(q, b)
    fold = curve(critical[0])
    small, large = equilibrium_roots(b, .02), equilibrium_roots(b, .1)
    negative = equilibrium_roots(b, -.02)
    out.update({'eq-unique': equilibrium_roots(2, 0)[0], 'eq-unique-modulus': F(2, 4),
                'eq-unique-derivative': branch_derivative(.5, 2), 'eq-baseline': baseline,
                'eq-critical': critical, 'eq-fold': fold,
                'eq-derivatives': [branch_derivative(q, b) for q in baseline],
                'eq-slopes': [b*q*(1-q) for q in baseline], 'eq-small-policy': small,
                'eq-large-policy': large[0], 'eq-mean-set': [small[0], small[-1]],
                'e11-negative-roots': negative, 'e11-mean-set': [negative[0], negative[-1]]})
    for policy, expected_count in [(0, 3), (.02, 3), (.1, 1), (fold, 2), (-fold, 2), (fold-1e-6, 3), (fold+1e-6, 1)]:
        roots = equilibrium_roots(b, policy)
        a.eq(len(roots), expected_count, 'root count across actual fold boundary')
        for root in roots:
            a.near(curve(root), policy, 'equilibrium equation at isolated root')
    a.near(negative, [1-x for x in reversed(small)], 'negative policy symmetry')
    a.eq(out['eq-slopes'][0] < 1 < out['eq-slopes'][1], True, 'specified iteration stability')
    for target in (small[0], .6, small[-1]):
        weight = (target-small[0])/(small[-1]-small[0])
        a.eq(0 <= weight <= 1, True, 'admissible extreme-root selection mixture')
        a.near((1-weight)*small[0]+weight*small[-1], target, 'selection mean construction')
    a.intervention('Both fold crossings, negative policy and randomized extreme-root selection')
    # Focused invalid domains and semantic failures, all explicitly exercised.
    invalid = [
        (lambda: number(True), 'boolean numeric input'),
        (lambda: number(float('nan')), 'NaN parameter'),
        (lambda: number(float('inf')), 'infinite parameter'),
        (lambda: market(10, 0, 1, 1, 1, 0), 'zero demand slope'),
        (lambda: market(10, 2, 1, -1, 1, 0), 'negative supply slope'),
        (lambda: solve([[1, 1], [2, 2]], [1, 2]), 'unidentified linear system'),
        (lambda: projection(G, m, [1, 0, 1], S), 'nonpositive distance weight'),
        (lambda: projection(G, m, [1, 2], S), 'moment weight shape'),
        (lambda: projection(G, m, [1, 2, 1], [1, -1, 1]), 'negative Gaussian variance'),
        (lambda: projection([[1, 1], [2, 2]], [1, 2], [1, 1], [1, 1]), 'rank-deficient moment map'),
        (lambda: competitive_quantity(5, 1, 0), 'flat marginal-cost output denominator'),
        (lambda: simulation_variance(0, 4, False), 'empty observed sample'),
        (lambda: simulation_variance(100, 2.5, False), 'fractional simulation count'),
        (lambda: simulation_variance(100, 4, 1), 'ambiguous simulation flag'),
        (lambda: difference_variance(4, 0, False), 'zero difference step'),
        (lambda: binary_atoms(F(1, 5), F(1, 2)), 'zero simulated probability'),
        (lambda: binary_atoms(F(1, 2), F(6, 5)), 'invalid observed probability'),
        (lambda: binary_atoms(F(1, 2), F(1, 2), F(1, 2)), 'unbounded simulator support'),
        (lambda: indirect_estimate(2, 0), 'invalid binding upper domain'),
        (lambda: indirect_law(2, 0), 'lower boundary is not regular'),
        (lambda: indirect_law(2, 3), 'upper boundary is not interior'),
        (lambda: indirect_law(0, F(3, 2)), 'empty simulation paths'),
        (lambda: bellman(1, r, c), 'undiscounted fixed-point gate'),
        (lambda: bellman(-.1, r, c), 'negative discount'),
        (lambda: bellman(.5, r, -1), 'negative deterioration outside declared domain'),
        (lambda: bellman(.5, r, c, 0), 'nonpositive Bellman tolerance'),
        (lambda: inverse_choice(0, .3, .5), 'zero baseline choice probability'),
        (lambda: inverse_choice(.5, .2, .5), 'choice rates contradict nonnegative deterioration'),
        (lambda: equilibrium_roots(9, 0), 'interaction outside bounded numerical scope'),
        (lambda: equilibrium_roots(b, 2), 'policy outside bounded root scope'),
        (lambda: branch_derivative(critical[0], b), 'fold derivative singularity'),
        (lambda: branch_derivative(0, b), 'boundary logit probability'),
        (lambda: bisection(lambda x: x*x+1, -1, 1), 'unbracketed numerical root'),
        (lambda: strict('{"x":1,"x":2}'), 'duplicate JSON member'),
        (lambda: strict('{"x":NaN}'), 'nonstandard JSON constant'),
        (lambda: strict('{"x":1e400}'), 'overflowed JSON number'),
        (lambda: displayed_value('__import__("os")'), 'arbitrary displayed expression'),
        (lambda: displayed_value('log(0)'), 'invalid displayed logarithm'),
        (lambda: Page().feed('HTML'), 'stray reader delimiter'),
        (lambda: Page().feed('<section><p></section>'), 'unbalanced reader markup'),
    ]
    for action, label in invalid:
        a.reject(action, label)
    return out


def check(root=None):
    root = Path(root) if root is not None else Path(__file__).resolve().parents[1]
    a = Audit()
    raw = (root/HTML).read_text()
    page = Page()
    page.feed(raw)
    page.close()
    ids = ['v12-c10-e'+str(i).zfill(2) for i in range(1, 13)]
    a.eq(page.prompts, ids, 'all exact prompt IDs')
    a.eq(page.targets, ids, 'all exact solution pairings')
    a.eq((page.worked, page.exercise_count, page.solution_count), (6, 12, 12), 'standard reader conventions')
    a.eq((page.stack, page.marker, page.answer, page.h1), ([], None, None, 0), 'complete chapter fragment')
    a.eq(len(page.ids), len(set(page.ids)), 'unique reader IDs')
    a.eq(all(x.startswith('v12-c10-') for x in page.ids), True, 'owned ID namespace')
    a.eq(raw.count('<details class="solutions"'), 1, 'single standard disclosed solutions block')
    a.eq('Benchmark answer.' in raw and '<strong>Answers.</strong>' in raw, True, 'answered teach-back and retention')
    for target in ids:
        a.eq(len(page.answers[target]) > 350, True, 'substantive exact solution '+target)
    calculated = calculate(a)
    a.eq(set(page.values), set(calculated), 'every visible marker independently reconstructed')
    for key, expected in calculated.items():
        a.near(displayed_value(page.values[key]), expected, 'visible result '+key, 7e-10)
    sources = strict((root/SOURCES).read_text())
    review = strict((root/REVIEW).read_text())
    source_ids = {'v12-c10-train-simulation2009', 'v12-c10-rust1987', 'v12-c10-gourieroux-monfort-renault1993'}
    a.eq({x['id'] for x in sources['proposals']}, source_ids, 'three scoped primary sources')
    a.eq(len(sources['proposals']), 3, 'no additional proposal')
    a.eq(set(page.sources), source_ids, 'all source routes actually used')
    for s in sources['proposals']:
        a.eq(s['inspection']['reader'], 'c05_review', 'honest primary inspector attribution')
        a.eq(bool(s['inspection']['read_pages']) and bool(s['inspection']['rendered_pages']), True, 'actual body and equation scopes')
        a.eq('verification' in s and 'status' not in s, True, 'catalogue verification field')
        a.eq(s['checked'], '2026-10-09', 'dated scoped inspection')
    allowed = {'v12-c09.html', 'v02-c10.html', 'v12-c01.html', 'v12-c03.html', 'v12-c04.html'} | {'sources.html#'+s for s in source_ids}
    for href in page.links:
        a.eq(href in allowed, True, 'flat reader prerequisite or source route')
    hashes = review['reviewed_hashes']
    a.eq({x['path'] for x in hashes}, {HTML, SELF, SOURCES}, 'three nonself runtime bindings')
    a.eq(len(hashes), 3, 'no repeated or self binding')
    for row in hashes:
        payload = (root/row['path']).read_bytes()
        a.eq((len(payload), hashlib.sha256(payload).hexdigest()), (row['bytes'], row['sha256']), 'final author payload '+row['path'])
    result = dict(chapter='v12-c10', status='passed', working_only=True, worked_cases=6,
                  exercises=12, solutions=12, comparisons=a.comparisons,
                  visible_calculation_markers=len(calculated), purposeful_interventions=len(a.interventions),
                  intervention_scopes=a.interventions, executed_rejections=len(a.rejections),
                  rejection_scopes=a.rejections, primary_inspection_scopes=3,
                  nonself_author_bindings=3,
                  limits='Bounded finite laws, exact projections and model-specific Gaussian/delta calculations; proofs are separately author-reviewed. No generic dynamic-data or simulation CLT, empirical policy identification, human certification, UI check or chapter acceptance implied.')
    strict(json.dumps(result, allow_nan=False))
    return result


if __name__ == '__main__':
    check()
