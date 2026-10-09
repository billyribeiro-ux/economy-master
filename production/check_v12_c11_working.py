"""Original finite-law reconstruction for Bayesian, sparse and causal learning.

Only the four adjacent working payloads are runtime inputs. No PDF, network,
saved numerical oracle, prior chapter, shared verifier or random simulation is
used. Import and successful CLI are silent. Analytic proof reading is recorded
separately; these bounded routines are not general MCMC or machine-learning
software and do not imply chapter acceptance or external human certification.
"""
import ast
from fractions import Fraction as F
from html.parser import HTMLParser
from itertools import product
import hashlib
import json
from math import exp, isclose, isfinite, log, sqrt
from pathlib import Path

HTML = 'production/v12-c11-working.html'
SELF = 'production/check_v12_c11_working.py'
SOURCES = 'production/v12-c11-sources-working.json'
REVIEW = 'production/v12-c11-author-review-working.json'


def need(ok, message):
    if not ok:
        raise ValueError('v12-c11: ' + message)


def number(x):
    need(type(x) in (int, float, F), 'numeric value excluding bool')
    try:
        finite = isfinite(float(x))
    except (ValueError, OverflowError):
        finite = False
    need(finite, 'finite representable number')
    return F(str(x)) if type(x) is float else F(x)


def positive_integer(n):
    need(type(n) is int and n > 0, 'positive integer')
    return n


def vector(x):
    need(isinstance(x, (list, tuple)) and len(x) > 0, 'nonempty vector')
    return [number(v) for v in x]


def matrix(x):
    need(isinstance(x, (list, tuple)) and len(x) > 0, 'nonempty matrix')
    out = [vector(row) for row in x]
    need(all(len(row) == len(out[0]) for row in out), 'rectangular matrix')
    return out


def probability(x):
    x = number(x)
    need(0 <= x <= 1, 'probability in [0,1]')
    return x


def distribution(x, positive=False):
    p = [probability(v) for v in vector(x)]
    need(sum(p) == 1, 'probability mass sums exactly to one')
    need(not positive or all(v > 0 for v in p), 'positive target probabilities')
    return p


def kernel(P):
    P = matrix(P)
    need(len(P) == len(P[0]), 'square transition kernel')
    return [distribution(row) for row in P]


def transpose(A):
    return list(map(list, zip(*A)))


def mm(A, B):
    A, B = matrix(A), matrix(B)
    need(len(A[0]) == len(B), 'conformable matrix product')
    return [[sum(x*y for x, y in zip(row, col)) for col in zip(*B)] for row in A]


def mv(A, x):
    A, x = matrix(A), vector(x)
    need(len(A[0]) == len(x), 'conformable matrix vector product')
    return [sum(a*b for a, b in zip(row, x)) for row in A]


def identity(n):
    positive_integer(n)
    return [[F(i == j) for j in range(n)] for i in range(n)]


def mean(x):
    x = vector(x)
    return sum(x)/len(x)


def variance(x):
    x = vector(x)
    m = mean(x)
    return mean([(v-m)**2 for v in x])


def posterior(theta, prior, successes, failures):
    theta = [probability(t) for t in vector(theta)]
    prior = distribution(prior)
    need(len(theta) == len(prior), 'prior parameter dimensions')
    need(type(successes) is int and successes >= 0 and type(failures) is int and failures >= 0,
         'nonnegative integer Bernoulli counts')
    likelihood = [t**successes*(1-t)**failures for t in theta]
    unnormalized = [w*l for w, l in zip(prior, likelihood)]
    evidence = sum(unnormalized)
    need(evidence > 0, 'positive observation marginal')
    return likelihood, evidence, [x/evidence for x in unnormalized]


def metropolis(target, proposals, include_ratio=True):
    target, proposals = distribution(target, positive=True), kernel(proposals)
    n = len(target)
    need(len(proposals) == n, 'target proposal dimensions')
    need(type(include_ratio) is bool, 'explicit proposal correction flag')
    P = []
    for i in range(n):
        row = [F(0)]*n
        for j in range(n):
            if i != j and proposals[i][j] > 0:
                ratio = target[j]/target[i]
                if include_ratio:
                    ratio *= proposals[j][i]/proposals[i][j]
                row[j] = proposals[i][j]*min(F(1), ratio)
        row[i] = 1-sum(row)
        P.append(row)
    return kernel(P)


def stationary_covariances(target, P, f, max_lag):
    target, P, f = distribution(target), kernel(P), vector(f)
    need(len(target) == len(P) == len(f), 'stationary observable dimensions')
    need(type(max_lag) is int and 0 <= max_lag <= 20, 'bounded nonnegative covariance lags')
    need(mm([target], P)[0] == target, 'stationarity required for this covariance formula')
    mu = sum(p*x for p, x in zip(target, f))
    h = [x-mu for x in f]
    power = identity(len(P))
    covariances = []
    for lag in range(max_lag+1):
        covariances.append(sum(target[i]*h[i]*z for i, z in enumerate(mv(power, h))))
        power = mm(power, P)
    return covariances


def path_mean_moments(initial, P, f, n):
    """First sampled state has law initial; n-1 subsequent transitions."""
    initial, P, f = distribution(initial), kernel(P), vector(f)
    n = positive_integer(n)
    need(len(initial) == len(P) == len(f) and n <= 6 and len(P) <= 4,
         'bounded exhaustive finite path domain')
    mass = first = second = F(0)
    count = 0
    for path in product(range(len(P)), repeat=n):
        weight = initial[path[0]]
        for i, j in zip(path, path[1:]):
            weight *= P[i][j]
        average = sum(f[i] for i in path)/n
        mass += weight
        first += weight*average
        second += weight*average**2
        count += 1
    need(mass == 1, 'exhaustive path probability conservation')
    return first, second-first**2, count


def soft(z, penalty):
    z, penalty = number(z), number(penalty)
    need(penalty > 0, 'positive penalty')
    return max(F(0), z-penalty) if z >= 0 else min(F(0), z+penalty)


def objective(X, y, b, penalty, weights=None):
    X, y, b, penalty = matrix(X), vector(y), vector(b), number(penalty)
    need(len(X) == len(y) and len(X[0]) == len(b), 'regression dimensions')
    need(penalty > 0, 'positive penalty')
    weights = [F(1)]*len(b) if weights is None else vector(weights)
    need(len(weights) == len(b) and all(w > 0 for w in weights), 'positive penalty weights')
    residual = [a-c for a, c in zip(y, mv(X, b))]
    return sum(v*v for v in residual)/(2*len(y))+penalty*sum(w*abs(v) for w, v in zip(weights, b))


def orthogonal_lasso(X, y, penalty):
    X, y, penalty = matrix(X), vector(y), number(penalty)
    need(len(X) == len(y), 'response and design rows')
    n, p = len(X), len(X[0])
    gram = [[x/n for x in row] for row in mm(transpose(X), X)]
    need(gram == identity(p), 'exact orthonormal design required for this routine')
    z = [x/n for x in mv(transpose(X), y)]
    b = [soft(x, penalty) for x in z]
    residual = [yi-fi for yi, fi in zip(y, mv(X, b))]
    scores = [v/n for v in mv(transpose(X), residual)]
    return z, b, residual, scores


def tuning(n, p, sigma, alpha):
    n, p = positive_integer(n), positive_integer(p)
    sigma, alpha = number(sigma), number(alpha)
    need(sigma > 0 and 0 < alpha < 1, 'positive noise and interior tail target')
    lam = 2*float(sigma)*sqrt(2*log(float(2*p/alpha))/n)
    bound = 2*p*exp(-n*(lam/2)**2/(2*float(sigma)**2))
    return lam, bound


def score(y, d, e, g0, g1):
    y, e, g0, g1 = map(number, (y, e, g0, g1))
    need(type(d) is int and d in (0, 1), 'binary treatment indicator')
    need(0 < e < 1, 'strict fitted overlap')
    return g1-g0+d*(y-g1)/e-(1-d)*(y-g0)/(1-e)


def causal_law(px, e, m0, m1):
    px, e, m0, m1 = distribution(px), vector(e), vector(m0), vector(m1)
    need(len(px) == len(e) == len(m0) == len(m1), 'causal table dimensions')
    need(all(0 < v < 1 for v in e), 'strict true overlap')
    # Explicitly integrate independent potential-noise signs, including the
    # unobserved sign, then merge identical observed records.
    observed = {}
    for x, d, eps0, eps1 in product(range(len(px)), (0, 1), (-1, 1), (-1, 1)):
        y = (m1[x]+eps1) if d else (m0[x]+eps0)
        w = px[x]*(e[x] if d else 1-e[x])/4
        key = (x, d, y)
        observed[key] = observed.get(key, F(0))+w
    return [(w, *key) for key, w in sorted(observed.items())]


def population_scores(atoms, e, g0, g1):
    e, g0, g1 = vector(e), vector(g0), vector(g1)
    need(len(e) == len(g0) == len(g1), 'candidate nuisance dimensions')
    values = [(w, score(y, d, e[x], g0[x], g1[x])) for w, x, d, y in atoms]
    mu = sum(w*s for w, s in values)
    return mu, sum(w*(s-mu)**2 for w, s in values)


def fit_folds(rows):
    """Bounded two-fold, binary-X learner; actually fits each training sample."""
    need(isinstance(rows, (list, tuple)) and len(rows) >= 2, 'nonempty training and held-out folds')
    data = []
    for row in rows:
        need(isinstance(row, (list, tuple)) and len(row) == 4, 'fold,X,D,Y record')
        fold, x, d, y = row
        need(all(type(v) is int and v in (0, 1) for v in (fold, x, d)), 'binary fold, covariate and treatment')
        y = number(y)
        need(abs(y) <= 5, 'bounded outcomes in declared learner experiment')
        data.append((fold, x, d, y))
    need({r[0] for r in data} == {0, 1}, 'both folds populated')
    fits = {}
    for held in (0, 1):
        training = [r for r in data if r[0] != held]
        e, g0, g1 = [], [], []
        for x in (0, 1):
            local = [r for r in training if r[1] == x]
            e.append(min(F(7, 8), max(F(1, 8), F(sum(r[2] for r in local)+1, len(local)+2))))
            for d, container in ((0, g0), (1, g1)):
                ys = [r[3] for r in local if r[2] == d]
                estimate = mean(ys) if ys else F(0)
                container.append(min(F(5), max(F(-5), estimate)))
        fits[held] = [e, g0, g1]
    scores = []
    for fold, x, d, y in data:
        e, g0, g1 = fits[fold]
        scores.append(score(y, d, e[x], g0[x], g1[x]))
    fold_means = [mean([s for r, s in zip(data, scores) if r[0] == k]) for k in (0, 1)]
    return fits, scores, fold_means, mean(scores), variance(scores), variance(scores)/len(scores)


def bh(pvalues, q):
    p = [probability(v) for v in vector(pvalues)]
    q = probability(q)
    need(0 < q < 1, 'interior testing target')
    m = len(p)
    R = max([k for k, value in enumerate(sorted(p), 1) if value <= q*k/m]+[0])
    return [i for i, value in enumerate(p) if value <= q*R/m] if R else []


def familywise(pvalues, q, holm=False):
    p = [probability(v) for v in vector(pvalues)]
    q = probability(q)
    need(0 < q < 1 and type(holm) is bool, 'familywise procedure domain')
    if not holm:
        return [i for i, value in enumerate(p) if value <= q/len(p)]
    selected = []
    for rank, i in enumerate(sorted(range(len(p)), key=lambda j: p[j])):
        if p[i] > q/(len(p)-rank):
            break
        selected.append(i)
    return sorted(selected)


def superuniform(masses):
    """For a finite law, check each CDF jump; between jumps it is constant."""
    need(bool(masses), 'nonempty p-value law')
    total = F(0)
    for p, w in masses.items():
        probability(p)
        probability(w)
        total += w
    need(total == 1, 'p-value law normalized')
    cumulative = F(0)
    for p in sorted(masses):
        cumulative += masses[p]
        if cumulative > p:
            return False
    return True


def strict(text):
    def pairs(items):
        out = {}
        for k, v in items:
            need(k not in out, 'unique JSON keys')
            out[k] = v
        return out
    def bad(x):
        raise ValueError('v12-c11: nonfinite JSON token ' + x)
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
        raise ValueError('v12-c11: unsupported displayed expression')
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
            raise ValueError('v12-c11: expected rejection: '+label)

    def intervention(self, label):
        self.interventions.append(label)


def calculate(a):
    out = {}
    theta, prior = [F(1, 4), F(1, 2), F(3, 4)], [F(1, 4), F(1, 2), F(1, 4)]
    likelihood, evidence, pi = posterior(theta, prior, 3, 1)
    mu = sum(t*w for t, w in zip(theta, pi))
    second = sum(t*t*w for t, w in zip(theta, pi))
    predictive = [F(0)]*3
    # Enumerate conditional binary future records instead of using the count
    # formula printed in the manuscript.
    for t, w in zip(theta, pi):
        for y1, y2 in product((0, 1), repeat=2):
            predictive[y1+y2] += w*(t if y1 else 1-t)*(t if y2 else 1-t)
    a.eq(sum(predictive), F(1), 'future predictive conservation')
    a.eq(sum(k*w for k, w in enumerate(predictive)), 2*mu, 'predictive count mean')
    alternative = posterior(theta, [F(16, 21), F(4, 21), F(1, 21)], 3, 1)[2]
    launch = sum(w*(3 if t == F(3, 4) else -2) for t, w in zip(theta, pi))
    alt_launch = sum(w*(3 if t == F(3, 4) else -2) for t, w in zip(theta, alternative))
    a.eq(launch > 0 > alt_launch, True, 'same evidence different prior decision')
    a.eq(sum(w*(t-mu)**2 for t, w in zip(theta, pi)), second-mu**2, 'two posterior variance routes')
    a.eq(posterior(theta, prior, 0, 0)[2], prior, 'no data returns prior')
    a.eq(posterior([0, 1], [F(1, 2)]*2, 1, 0)[2], [0, 1], 'valid endpoint likelihood')
    out.update({'bayes-likelihood': likelihood, 'bayes-evidence': evidence, 'bayes-posterior': pi,
                'bayes-mean': mu, 'bayes-second': second, 'bayes-predictive': predictive,
                'bayes-variance': second-mu**2, 'bayes-launch': launch,
                'bayes-alternative': alternative, 'bayes-alternative-utility': alt_launch,
                'e1-launch-threshold': F(2, 5), 'e1-correlation': (second-mu**2)/(mu*(1-mu))})
    a.intervention('Alternative prior changes decision; no-data and parameter-endpoint likelihoods')

    q = [F(1, 2), F(1, 3), F(1, 6)]
    P = metropolis(pi, [q]*3)
    a.eq(mm([pi], P)[0], pi, 'correct target invariance')
    for i, j in product(range(3), repeat=2):
        a.eq(pi[i]*P[i][j], pi[j]*P[j][i], 'all detailed-balance flows')
    delta = min(P[i][j]/pi[j] for i, j in product(range(3), repeat=2))
    residual = [[(P[i][j]-delta*pi[j])/(1-delta) for j in range(3)] for i in range(3)]
    a.eq(kernel(residual), residual, 'minorization residual stochasticity')
    wrong = metropolis(pi, [q]*3, include_ratio=False)
    weights = [p*v for p, v in zip(pi, q)]
    wrong_target = [w/sum(weights) for w in weights]
    a.eq(mm([wrong_target], wrong)[0], wrong_target, 'omitted-ratio actual invariant law')
    a.eq(mm([pi], wrong)[0] != pi, True, 'omitted-ratio chain misses desired target')
    f = [0, 0, 1]
    observable_mean = sum(p*v for p, v in zip(pi, f))
    h = [v-observable_mean for v in f]
    lam = 1-delta
    a.eq(mv(P, h), [lam*v for v in h], 'observable eigenfunction')
    gammas = stationary_covariances(pi, P, f, 4)
    a.eq(gammas, [gammas[0]*lam**k for k in range(5)], 'matrix powers versus eigen covariance')
    exact_mean, exact_variance, path_count = path_mean_moments(pi, P, f, 4)
    covariance_variance = (4*gammas[0]+2*sum((4-k)*gammas[k] for k in range(1, 4)))/16
    a.eq(path_count, 81, 'complete stationary path law')
    a.eq(exact_mean, observable_mean, 'enumerated stationary expectation')
    a.eq(exact_variance, covariance_variance, 'enumerated versus covariance stationary variance')
    initialized, initial_means = [F(1), F(0), F(0)], []
    for t in range(1, 5):
        initialized = mm([initialized], P)[0]
        initial_means.append(sum(p*v for p, v in zip(initialized, f)))
        a.eq(initial_means[-1], observable_mean*(1-lam**t), 'separate initialized expectation')
        distance = sum(abs(x-y) for x, y in zip(initialized, pi))/2
        a.eq(distance <= lam**t*(1-pi[0]), True, 'actual initial law obeys TV bound')
    initial_path = path_mean_moments(P[0], P, f, 4)
    a.eq(initial_path[0], mean(initial_means), 'initialized path and iterative expectation')
    a.eq(initial_path[1] != exact_variance, True, 'stationary variance not reused for low start')
    independent = metropolis(pi, [pi]*3)
    a.eq(independent, [pi]*3, 'target proposal gives iid transitions')
    a.eq(path_mean_moments(pi, independent, f, 4)[1], gammas[0]/4, 'iid target path variance')
    lazy = [[(P[i][j]+int(i == j))/2 for j in range(3)] for i in range(3)]
    lazy_eigen = (1+lam)/2
    a.eq(mv(lazy, h), [lazy_eigen*x for x in h], 'lazy eigenfunction')
    a.eq((1+lazy_eigen)/(1-lazy_eigen) > (1+lam)/(1-lam), True, 'laziness increases this long variance')
    sparse_proposal = [[0, 1], [0, 1]]
    a.eq(metropolis([F(1, 2)]*2, sparse_proposal), identity(2), 'unsupported reverse proposal rejected')
    periodic = [[0, 1], [1, 0]]
    a.eq(mm([[F(1, 2)]*2], periodic)[0], [F(1, 2)]*2, 'periodic chain has invariant law')
    a.eq(mm([[1, 0]], mm(periodic, periodic))[0], [1, 0], 'invariance alone fails convergence')
    out.update({'mh-transition': P, 'mh-delta': delta, 'mh-residual': residual,
                'mh-eigenvalue': lam, 'mh-wrong-transition': wrong, 'mh-wrong-target': wrong_target,
                'mh-mean': observable_mean, 'mh-observable-variance': gammas[0], 'mh-covariances': gammas,
                'mh-variance4': exact_variance, 'mh-false-iid4': gammas[0]/4,
                'mh-inflation4': exact_variance/(gammas[0]/4), 'mh-long-inflation': (1+lam)/(1-lam),
                'mh-initial-means': initial_means, 'mh-initial-bias': mean(initial_means)-observable_mean,
                'e2-independent-variance': gammas[0]/4, 'e3-lazy-eigenvalue': lazy_eigen,
                'e3-lazy-inflation': (1+lazy_eigen)/(1-lazy_eigen)})
    a.intervention('Omitted proposal ratio, low initialization, exact-target proposal, laziness and zero reverse support')

    X = [[1, 1, 1], [1, -1, 1], [1, 1, -1], [1, -1, -1]]
    reference, noise, penalty = [2, 0, -1], [F(1, 8), F(3, 8), F(-1, 8), F(1, 8)], F(1, 2)
    y = [v+e for v, e in zip(mv(X, reference), noise)]
    z, estimate, residuals, scores = orthogonal_lasso(X, y, penalty)
    for b, s in zip(estimate, scores):
        a.eq(s == (penalty if b > 0 else -penalty) if b else abs(s) <= penalty,
             True, 'coordinate KKT for all penalized coefficients')
    error = [b-t for b, t in zip(estimate, reference)]
    squared_error = sum(v*v for v in error)
    prediction_error = mean([v*v for v in mv(X, error)])
    a.eq(squared_error, prediction_error, 'orthogonal coefficient prediction equality')
    noise_score = [x/4 for x in mv(transpose(X), noise)]
    a.eq(max(map(abs, noise_score)) <= penalty/2, True, 'declared noise event holds at baseline')
    inside, outside = abs(error[0])+abs(error[2]), abs(error[1])
    a.eq(prediction_error/2+penalty*outside/2 <= 3*penalty*inside/2, True, 'exact basic inequality witness')
    a.eq(outside <= 3*inside, True, 'exact cone witness')
    a.eq(prediction_error <= 9*penalty**2*2, True, 'conditional prediction bound witness')
    small = orthogonal_lasso(X, y, F(1, 8))
    a.eq(max(map(abs, noise_score)) > F(1, 16), True, 'smaller penalty fails original noise event')
    a.eq(small[1][1], 0, 'inclusive soft-threshold equality')
    for b, s in zip(small[1], small[3]):
        a.eq(s == (F(1, 8) if b > 0 else F(-1, 8)) if b else abs(s) <= F(1, 8), True,
             'small-penalty KKT still valid')
    gaussian_lambda, union_bound = tuning(100, 20, 1, F(1, 20))
    a.near(union_bound, F(1, 20), 'Gaussian tail target substitution')
    duplicate_fit = soft(2, penalty)
    duplicate_min = objective([[1, 1]], [2], [duplicate_fit, 0], penalty)
    for b in ([0, duplicate_fit], [F(1, 2), 1], [duplicate_fit, 0]):
        a.eq(objective([[1, 1]], [2], b, penalty), duplicate_min, 'duplicate-column continuum witnesses')
    a.eq(objective([[1, 1]], [2], [-1, F(5, 2)], penalty) > duplicate_min, True, 'mixed signs lose penalty equality')
    weighted = [duplicate_fit, F(0)]
    a.eq(objective([[1, 1]], [2], weighted, penalty, [1, 2]), duplicate_min, 'weighted unique allocation value')
    for b in ([0, duplicate_fit], [F(1, 2), 1]):
        a.eq(objective([[1, 1]], [2], b, penalty, [1, 2]) > duplicate_min, True, 'positive second weight removes former minimizers')
    a.eq(mv([[1, 1]], [1, -1]), [0], 'full-vector curvature obstructed by cone null vector')
    out.update({'lasso-y': y, 'lasso-z': z, 'lasso-estimate': estimate, 'lasso-kkt': scores,
                'lasso-error': error, 'lasso-squared-error': squared_error,
                'lasso-l1-error': sum(map(abs, error)), 'lasso-objective': objective(X, y, estimate, penalty),
                'lasso-noise-score': noise_score, 'lasso-bounds': [9*penalty**2*2, 3*float(penalty)*sqrt(2), 12*penalty*2],
                'lasso-gaussian-lambda': gaussian_lambda, 'lasso-gaussian-alpha': union_bound,
                'lasso-duplicate-fit': duplicate_fit, 'lasso-duplicate-objective': duplicate_min,
                'e4-small-lambda-estimate': small[1], 'e6-weighted-estimate': weighted})
    a.intervention('Penalty threshold and noise-event boundary, duplicate null direction and (1,2) weighted penalty')

    px, e0, m0, m1 = [F(1, 2)]*2, [F(1, 4), F(3, 4)], [0, 1], [2, 4]
    atoms = causal_law(px, e0, m0, m1)
    a.eq(len(atoms), 8, 'potential-law integration gives eight observed atoms')
    a.eq(sum(row[0] for row in atoms), 1, 'observed law conserves probability')
    for x, d in product((0, 1), repeat=2):
        local = [(w, y) for w, xx, dd, y in atoms if (xx, dd) == (x, d)]
        a.eq(sum(w for w, y in local), px[x]*(e0[x] if d else 1-e0[x]), 'observed cell mass')
        a.eq(sum(w*y for w, y in local)/sum(w for w, y in local), m1[x] if d else m0[x], 'true outcome cell mean')
    ate = sum(p*(a1-a0) for p, a0, a1 in zip(px, m0, m1))
    ew, g0w, g1w = [F(1, 2)]*2, [F(1, 2)]*2, [3, 5]
    configurations = [(e0, m0, m1), (e0, g0w, g1w), (ew, m0, m1), (ew, g0w, g1w)]
    means = [population_scores(atoms, *case)[0] for case in configurations]
    for e, g0, g1 in configurations:
        bias = sum(p*(ef-true)*((b1-a1)/ef+(b0-a0)/(1-ef))
                   for p, ef, true, b0, b1, a0, a1 in zip(px, e, e0, g0, g1, m0, m1))
        a.eq(population_scores(atoms, e, g0, g1)[0]-ate, bias, 'atom score versus factored population remainder')
    oracle_variance = population_scores(atoms, e0, m0, m1)[1]
    effect_variance = sum(p*((b-a0)-ate)**2 for p, a0, b in zip(px, m0, m1))
    residual_variance = sum(p*(1/e+1/(1-e)) for p, e in zip(px, e0))
    a.eq(oracle_variance, effect_variance+residual_variance, 'atom influence variance versus conditional decomposition')
    cancellation = population_scores(atoms, ew, [v-1 for v in m0], [v+1 for v in m1])
    a.eq(cancellation[0], ate, 'both-wrong exact cancellation')
    a.eq(cancellation[1] != oracle_variance, True, 'zero bias does not ensure oracle variance')
    out.update({'dr-ate': ate, 'dr-means': means, 'dr-bias': means[-1]-ate,
                'dr-influence-variance': oracle_variance, 'dr-mean-variance': oracle_variance/400,
                'e7-cancellation-mean': cancellation[0]})
    a.intervention('All four nuisance truth combinations and both-wrong cancellation with changed variance')

    rows = [[0, 0, 0, -1], [0, 0, 1, 3], [0, 1, 0, 0], [0, 1, 1, 5],
            [1, 0, 0, 1], [1, 0, 1, 1], [1, 1, 0, 2], [1, 1, 1, 3]]
    fitted = fit_folds(rows)
    changed = [list(row) for row in rows]
    changed[0][-1] = 1
    refitted = fit_folds(changed)
    a.eq(refitted[0][0], fitted[0][0], 'held-out outcome never enters its own fit')
    a.eq(refitted[0][1][1][0]-fitted[0][1][1][0], 2, 'other-fold training mean genuinely refitted')
    a.eq([b-a0 for a0, b in zip(fitted[1], refitted[1])], [-4, 0, 0, 0, 2, -2, 0, 0], 'exact propagation of changed training outcome')
    # Missing cells are valid procedure boundaries, not silently removed rows.
    empty = fit_folds([[0, 0, 0, 1], [1, 1, 1, 3]])
    a.eq(empty[0][0][1][0], 0, 'empty outcome cell convention is zero')
    a.eq(empty[0][0][0][0], F(1, 2), 'empty X cell Laplace propensity')
    a.eq(empty[0][0][0][1], F(2, 3), 'observed treated cell Laplace propensity')
    one_class = fit_folds([[0, 0, 0, 1]]+[[1, 0, 1, 3]]*10)
    a.eq(one_class[0][0][0][0], F(7, 8), 'propensity clipping actually activates')
    t = F(1, 4)
    shifted_e, shifted_g1 = [e+t/8 for e in e0], [v+t for v in m1]
    shifted_bias = population_scores(atoms, shifted_e, m0, shifted_g1)[0]-ate
    formula_bias = t*t/2*(1/(2+t)+1/(6+t))
    a.eq(shifted_bias, formula_bias, 'quarter-rate bias from all observed atoms')
    a.eq(F(1, 5)+F(1, 3)-F(1, 2), F(1, 30), 'strictly sufficient product exponent')
    a.eq(2*F(1, 4)-F(1, 2), 0, 'two big-O quarter rates do not imply little-o')
    # Finite witnessed overwrites; zero fresh-law mass of these identifiers is
    # an analytic continuous-law claim documented in the manuscript, not an
    # assertion estimated by random sampling.
    reused = [score(y, d, e0[x], y, y) for fold, x, d, y in rows]
    heldout = [score(y, d, e0[x], m0[x], m1[x]) for fold, x, d, y in rows]
    a.eq(reused, [0]*8, 'each own-identifier score collapses to zero')
    a.eq(any(v != 0 for v in heldout), True, 'held-out identifier rule recovers distinct oracle scores')
    out.update({'cf-fit0': fitted[0][0], 'cf-fit1': fitted[0][1], 'cf-scores': fitted[1],
                'cf-fold-means': fitted[2], 'cf-estimate': fitted[3], 'cf-score-variance': fitted[4],
                'cf-estimator-variance': fitted[5], 'cf-rate-limit': F(1, 2)*(F(1, 2)+F(1, 6)),
                'cf-e-shift': t/8, 'cf-g-shift': t, 'cf-rate-bias': shifted_bias,
                'cf-rate-scaled': 16*shifted_bias, 'cf-leakage': [mean(reused), variance(reused)],
                'e9-transfer-scores': refitted[1], 'e9-transfer-mean': refitted[3],
                'e9-transfer-score-variance': refitted[4], 'e9-transfer-mean-variance': refitted[5]})
    a.intervention('Actually refitted outcome transfer, empty training cells and active propensity clipping')
    a.intervention('Quarter-rate inference-scale bias and own-identifier leakage versus held-out oracle')

    p_fixed = [F(1, 100), F(3, 100), F(7, 200), F(1, 5)]
    fixed = bh(p_fixed, F(1, 20))
    bonf, holm = familywise(p_fixed, F(1, 20)), familywise(p_fixed, F(1, 20), True)
    a.eq(bonf, holm, 'fixed familywise procedures agree')
    a.eq(p_fixed[1] > F(1, 40) and p_fixed[2] <= F(3, 80), True, 'step-up continues after failed earlier comparison')
    counts = {1: 0, 2: 0, 3: 0}
    FDR = FWER = EV = ER = F(0)
    grid = [F(j, 12) for j in range(1, 13)]
    a.eq(superuniform({p: F(1, 12) for p in grid}), True, 'discrete null CDF validity at every jump')
    for p1, p2 in product(grid, repeat=2):
        values = [F(0), p1, p2]
        selected = bh(values, F(1, 4))
        R, V = len(selected), sum(i > 0 for i in selected)
        counts[R] += 1
        FDR += F(V, max(R, 1))/144
        FWER += F(V > 0, 144)
        EV += F(V, 144)
        ER += F(R, 144)
        for i in (1, 2):
            zeroed = list(values)
            zeroed[i] = F(0)
            Ri = len(bh(zeroed, F(1, 4)))
            a.eq(F(i in selected, max(R, 1)), F(values[i] <= F(Ri, 12), Ri), 'leave-one-out identity at every joint-law state')
    a.eq(sum(counts.values()), 144, 'all independent joint-testing states counted')
    a.eq(FDR, F(2, 3)*F(1, 4), 'finite grid attains independent FDR bound')
    a.eq(FDR != EV/ER, True, 'FDR differs from ratio of expectations')
    a.eq(bh([F(1, 10)]*2, F(1, 10)), [0, 1], 'inclusive simultaneous BH ties')
    a.eq(bh([1, 1], F(1, 10)), [], 'no-rejection zero-denominator convention')
    dependent = [(F(1, 20), [F(1, 20), F(1)]), (F(1, 20), [F(1), F(1, 20)]),
                 (F(1, 20), [F(1, 10), F(1, 10)]), (F(17, 20), [F(1), F(1)])]
    for i in (0, 1):
        marginal = {}
        for w, p in dependent:
            marginal[p[i]] = marginal.get(p[i], F(0))+w
        a.eq(superuniform(marginal), True, 'dependent null marginal valid at every jump')
    dep_bh = sum(w for w, p in dependent if bh(p, F(1, 10)))
    dep_bonf = sum(w for w, p in dependent if familywise(p, F(1, 10)))
    dep_holm = sum(w for w, p in dependent if familywise(p, F(1, 10), True))
    a.eq(dep_bonf, dep_holm, 'both familywise methods in dependence counterexample')
    a.eq(dep_bh > F(1, 10) >= dep_bonf, True, 'valid marginals alone fail BH guarantee')
    out.update({'bh-fixed': [i+1 for i in fixed], 'bh-fixed-familywise': bonf[0]+1,
                'bh-counts': [counts[k] for k in (1, 2, 3)], 'bh-fdr': FDR, 'bh-fwer': FWER,
                'bh-EV': EV, 'bh-ER': ER, 'bh-wrong-ratio': EV/ER,
                'bh-dependent-fdr': dep_bh, 'bh-dependent-familywise': dep_bonf})
    a.intervention('Early-failure/later-pass and tied thresholds; complete independent and dependent testing laws')

    invalid = [
        (lambda: number(True), 'boolean numerical input'),
        (lambda: number(float('nan')), 'nonfinite parameter'),
        (lambda: number(float('inf')), 'infinite parameter'),
        (lambda: distribution([F(1, 3)]*2), 'unnormalized law'),
        (lambda: distribution([-1, 2]), 'signed probability law'),
        (lambda: posterior(theta, prior, 1.5, 0), 'fractional success count'),
        (lambda: posterior(theta, prior, 1, -1), 'negative failure count'),
        (lambda: posterior(theta, prior[:2], 3, 1), 'prior dimension mismatch'),
        (lambda: posterior([0], [1], 1, 0), 'zero observation marginal'),
        (lambda: metropolis([0, 1], [[F(1, 2)]*2]*2), 'zero target state outside positive-target scope'),
        (lambda: metropolis(pi, [[1, 0], [0, 1]]), 'proposal target size mismatch'),
        (lambda: metropolis(pi, [[1, 0, 0]]*2), 'nonsquare proposal'),
        (lambda: metropolis(pi, [[1, 1, 0]]*3), 'proposal row mass exceeds one'),
        (lambda: metropolis(pi, [q]*3, 1), 'ambiguous ratio flag'),
        (lambda: stationary_covariances([1, 0, 0], P, f, 4), 'nonstationary law in stationary covariance routine'),
        (lambda: path_mean_moments(pi, P, f, 7), 'path enumeration outside bounded scope'),
        (lambda: soft(1, 0), 'zero penalty excluded by coercivity contract'),
        (lambda: soft(1, -1), 'negative penalty'),
        (lambda: orthogonal_lasso([[1, 1]], [2], F(1, 2)), 'duplicate design in orthogonal-only solver'),
        (lambda: orthogonal_lasso(X, y[:2], F(1, 2)), 'response shape mismatch'),
        (lambda: objective([[1, 1]], [2], [1, 0], F(1, 2), [1, 0]), 'nonpositive penalty weight'),
        (lambda: tuning(0, 20, 1, F(1, 20)), 'zero tuning sample size'),
        (lambda: tuning(100, 20, 0, F(1, 20)), 'degenerate Gaussian variance outside tuning scope'),
        (lambda: tuning(100, 20, 1, 1), 'noninterior tail target'),
        (lambda: score(1, True, F(1, 2), 0, 1), 'boolean treatment indicator'),
        (lambda: score(1, 2, F(1, 2), 0, 1), 'nonbinary treatment indicator'),
        (lambda: score(1, 1, 0, 0, 1), 'zero fitted overlap'),
        (lambda: score(1, 0, 1, 0, 1), 'unit fitted propensity'),
        (lambda: causal_law(px, [0, 1], m0, m1), 'true overlap failure'),
        (lambda: fit_folds([[0, 0, 0, 1], [0, 1, 1, 3]]), 'empty held-out/training fold'),
        (lambda: fit_folds([[0, 2, 0, 1], [1, 1, 1, 3]]), 'covariate outside binary learner scope'),
        (lambda: fit_folds([[0, 0, 0, 6], [1, 1, 1, 3]]), 'outcome outside bounded theorem experiment'),
        (lambda: fit_folds([[0, 0, 0], [1, 1, 1, 3]]), 'malformed learner row'),
        (lambda: bh([], F(1, 10)), 'empty testing family'),
        (lambda: bh([F(11, 10)], F(1, 10)), 'p-value exceeds one'),
        (lambda: bh([F(1, 2)], 0), 'zero testing target outside specified domain'),
        (lambda: familywise([F(1, 2)], F(1, 10), 1), 'ambiguous familywise rule'),
        (lambda: superuniform({F(1, 2): F(1, 2)}), 'incomplete null-law mass'),
        (lambda: strict('{"x":1,"x":2}'), 'duplicate JSON key'),
        (lambda: strict('{"x":NaN}'), 'nonstandard nonfinite JSON token'),
        (lambda: strict('{"x":1e400}'), 'overflowed JSON number'),
        (lambda: displayed_value('__import__("os")'), 'unsupported displayed code'),
        (lambda: displayed_value('sqrt(-1)'), 'displayed square-root domain'),
        (lambda: Page().feed('HTML'), 'stray top-level delimiter'),
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
    ids = ['v12-c11-e'+str(i).zfill(2) for i in range(1, 13)]
    a.eq(page.prompts, ids, 'all exact prompt IDs')
    a.eq(page.targets, ids, 'all exact solution pairings')
    a.eq((page.worked, page.exercise_count, page.solution_count), (6, 12, 12), 'standard reader conventions')
    a.eq((page.stack, page.marker, page.answer, page.h1), ([], None, None, 0), 'complete static chapter fragment')
    a.eq(len(page.ids), len(set(page.ids)), 'unique reader IDs')
    a.eq(all(x.startswith('v12-c11-') for x in page.ids), True, 'owned reader namespace')
    a.eq(raw.count('<details class="solutions"'), 1, 'one standard solutions disclosure')
    a.eq('Benchmark answer.' in raw and '<strong>Answers.</strong>' in raw, True, 'answered teaching and retention')
    rubric = raw.split('<caption>Research-audit rubric</caption>')[-1].split('</table>')[0]
    a.eq('Scored benchmark, 12 points.' in raw and rubric.count('<td>2</td>') == 6, True, 'six-domain twelve-point research audit')
    for target in ids:
        a.eq(len(page.answers[target]) > 700, True, 'substantive complete solution '+target)
    calculated = calculate(a)
    a.eq(set(page.values), set(calculated), 'every displayed marker independently reconstructed')
    for key, expected in calculated.items():
        a.near(displayed_value(page.values[key]), expected, 'visible result '+key, 8e-11)
    sources = strict((root/SOURCES).read_text())
    review = strict((root/REVIEW).read_text())
    source_ids = {'v12-c11-hastings1970', 'v12-c11-negahban2012', 'v12-c11-dml-v7', 'v12-c11-bh1995'}
    a.eq({s['id'] for s in sources['proposals']}, source_ids, 'four scoped primary sources')
    a.eq(len(sources['proposals']), 4, 'exact primary source count')
    a.eq(set(page.sources), source_ids, 'all four actual manuscript source routes')
    for s in sources['proposals']:
        a.eq(s['inspection']['reader'], 'bs_author', 'actual primary inspector attribution')
        a.eq(bool(s['inspection']['rendered_pages']), True, 'retained actual equation-image scope')
        a.eq('verification' in s and 'status' not in s, True, 'catalogue verification field')
        a.eq(s['checked'], '2026-10-09', 'dated source scope')
    a.eq(review['chapter'], 'v12-c11', 'correct working author record')
    a.eq(len(review['exercise_audit']), 12, 'every exact solution analytically audited')
    a.eq(len(review['worked_case_audit']), 6, 'every worked case analytically audited')
    a.eq(review['open_findings'], [], 'no unresolved author finding')
    allowed = {'v03-c09.html', 'v03-c08.html', 'v12-c01.html', 'v12-c02.html', 'v12-c07.html', 'v12-c10.html'}
    allowed |= {'sources.html#'+s for s in source_ids}
    for href in page.links:
        a.eq(href in allowed, True, 'flat reader prerequisite or source link')
    bindings = review['reviewed_hashes']
    a.eq({b['path'] for b in bindings}, {HTML, SELF, SOURCES}, 'three nonself author payload bindings')
    a.eq(len(bindings), 3, 'no duplicate or self binding')
    for b in bindings:
        payload = (root/b['path']).read_bytes()
        a.eq((len(payload), hashlib.sha256(payload).hexdigest()), (b['bytes'], b['sha256']), 'bound author payload '+b['path'])
    result = dict(chapter='v12-c11', status='passed', working_only=True, worked_cases=6,
                  exercises=12, solutions=12, comparisons=a.comparisons,
                  visible_calculation_markers=len(calculated), purposeful_interventions=len(a.interventions),
                  intervention_scopes=a.interventions, executed_rejections=len(a.rejections),
                  rejection_scopes=a.rejections, exact_stationary_paths=81, independent_testing_states=144,
                  leave_one_out_state_identities=288, primary_inspection_scopes=4, nonself_author_bindings=3,
                  limits='Finite original laws and bounded exact procedures. Analytic proofs are separately author-reviewed; no generic MCMC CLT, arbitrary learner rates, empirical causal validity, human certification, reader UI check or chapter acceptance implied.')
    strict(json.dumps(result, allow_nan=False))
    return result


if __name__ == '__main__':
    check()
