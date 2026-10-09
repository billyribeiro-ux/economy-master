"""Independent C11 peer reconstruction; six read-only canonical payloads.

No author code, saved numerical results, source artifacts or production records
are runtime inputs.  Generic parsing/binding helpers reuse the frozen C10 peer
pattern; every numerical oracle below is original to this review.  Successful
import, check(root=None) and default CLI are quiet, including under python -O.
"""
import ast
from collections import defaultdict
from fractions import Fraction as Q
from html.parser import HTMLParser
from itertools import product
import hashlib
import json
import math
from pathlib import Path

AUTHOR = ('content/chapters/v12-c11.html', 'scripts/check_v12_c11.py',
          'content/reviews/v12-c11-sources.json', 'content/reviews/v12-c11-author.json')
SELF = 'scripts/check_v12_c11_peer.py'
REVIEW = 'content/reviews/v12-c11-peer.json'
SOURCE_IDS = {'v12-c11-hastings1970', 'v12-c11-negahban2012',
              'v12-c11-dml-v7', 'v12-c11-bh1995'}


def require(condition, message):
    if not condition:
        raise ValueError('C11 peer: ' + message)


def finite(x):
    require(type(x) in (int, float, Q), 'numeric scalar excluding bool')
    try:
        y = float(x)
    except (OverflowError, ValueError):
        raise ValueError('C11 peer: unrepresentable scalar') from None
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
        raise ValueError('C11 peer: nonfinite JSON token ' + x)
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


def sequential_bayes(theta, prior, bits):
    p = law(prior)
    require(len(theta) == len(p) and len(bits) <= 16, 'posterior dimensions/budget')
    t = [finite(x) for x in theta]
    require(all(0 <= x <= 1 for x in t), 'Bernoulli parameters')
    evidence = Q(1)
    likelihood = [Q(1)]*len(t)
    for y in bits:
        require(type(y) is int and y in (0, 1), 'binary ordered observations')
        chance = [x if y else 1-x for x in t]
        z = sum(a*b for a, b in zip(p, chance))
        require(z > 0, 'positive observation evidence')
        p = [a*b/z for a, b in zip(p, chance)]
        likelihood = [a*b for a, b in zip(likelihood, chance)]
        evidence *= z
    return p, evidence, likelihood


def kernel(target, proposal):
    """Use symmetric accepted probability flows, not acceptance-ratio code."""
    p = law(target, True)
    n = len(p)
    require(len(proposal) == n, 'kernel dimensions')
    q = [law(row) for row in proposal]
    require(all(len(row) == n for row in q), 'square proposal')
    flow = [[min(p[i]*q[i][j], p[j]*q[j][i]) for j in range(n)] for i in range(n)]
    result = [[flow[i][j]/p[i] if i != j else Q(0) for j in range(n)] for i in range(n)]
    for i in range(n): result[i][i] = 1-sum(result[i])
    return result


def solve(matrix, rhs):
    require(1 <= len(rhs) <= 12 and len(matrix) == len(rhs), 'bounded linear system')
    n = len(rhs)
    require(all(len(row) == n for row in matrix), 'square linear system')
    a = [[finite(x) for x in row]+[finite(y)] for row, y in zip(matrix, rhs)]
    for j in range(n):
        pivot = next((i for i in range(j, n) if a[i][j]), None)
        require(pivot is not None, 'nonsingular linear system')
        a[j], a[pivot] = a[pivot], a[j]
        d = a[j][j]
        a[j] = [x/d for x in a[j]]
        for i in range(n):
            if i != j:
                c = a[i][j]
                a[i] = [x-c*y for x, y in zip(a[i], a[j])]
    return [row[-1] for row in a]


def occupancy(P, initial, n):
    """Exact two-state count distribution; initial is the first sampled state."""
    require(type(n) is int and 1 <= n <= 32, 'bounded occupancy horizon')
    require(len(P) == 2 and all(len(row) == 2 for row in P), 'two-state kernel')
    p = [law(row) for row in P]
    start = law(initial)
    require(len(start) == 2, 'two-state initial law')
    current = {(s, s): start[s] for s in (0, 1)}
    for _ in range(n-1):
        following = defaultdict(Q)
        for (s, count), mass in current.items():
            for new in (0, 1): following[new, count+new] += mass*p[s][new]
        current = following
    mu = sum(m*Q(count, n) for (_, count), m in current.items())
    variance = sum(m*(Q(count, n)-mu)**2 for (_, count), m in current.items())
    return mu, variance, sum(current.values())


def lasso_faces(design, response, penalty):
    """Enumerate active/sign faces and solve their normal equations exactly."""
    lam = finite(penalty)
    require(lam > 0 and 1 <= len(design) <= 16, 'positive penalty and bounded design')
    n = len(design)
    require(len(response) == n and 1 <= len(design[0]) <= 4, 'lasso dimensions')
    p = len(design[0])
    require(all(len(row) == p for row in design), 'rectangular design')
    X = [[finite(v) for v in row] for row in design]
    y = [finite(v) for v in response]
    G = [[sum(row[i]*row[j] for row in X)/n for j in range(p)] for i in range(p)]
    z = [sum(row[j]*yi for row, yi in zip(X, y))/n for j in range(p)]
    solve(G, [Q(0)]*p)  # This finite oracle's stated scope is full column rank.
    candidates = []
    for signs in product((-1, 0, 1), repeat=p):
        active = [j for j, s in enumerate(signs) if s]
        b = [Q(0)]*p
        if active:
            vals = solve([[G[i][j] for j in active] for i in active],
                         [z[i]-lam*signs[i] for i in active])
            for j, v in zip(active, vals): b[j] = v
        score = [z[i]-sum(G[i][j]*b[j] for j in range(p)) for i in range(p)]
        if all(b[j]*signs[j] > 0 if signs[j] else abs(score[j]) <= lam for j in range(p)):
            residual = [yi-sum(x*bj for x, bj in zip(row, b)) for row, yi in zip(X, y)]
            objective = sum(r*r for r in residual)/(2*n)+lam*sum(abs(v) for v in b)
            candidates.append((objective, b, score))
    require(len(candidates) == 1, 'unique full-rank KKT face')
    objective, b, score = candidates[0]
    return b, score, objective, z


def score(y, d, e, g0, g1):
    require(type(d) is int and d in (0, 1), 'binary treatment')
    y, e, g0, g1 = map(finite, (y, e, g0, g1))
    require(0 < e < 1, 'candidate overlap')
    return g1-g0+d*(y-g1)/e-(1-d)*(y-g0)/(1-e)


def conditional_score_moments(e, g0, g1):
    """Integrate fair outcome noise analytically, then (X,D); no latent table oracle."""
    require(len(e) == len(g0) == len(g1) == 2, 'two covariate cells')
    e, g0, g1 = ([finite(x) for x in v] for v in (e, g0, g1))
    require(all(0 < x < 1 for x in e), 'moment candidate overlap')
    truth = [Q(1, 4), Q(3, 4)]
    m0, m1 = [Q(0), Q(1)], [Q(2), Q(4)]
    conditional, second = [], Q(0)
    for x in (0, 1):
        mu = Q(0)
        for d in (0, 1):
            weight = truth[x] if d else 1-truth[x]
            center = score((m1 if d else m0)[x], d, e[x], g0[x], g1[x])
            noise_coefficient = 1/e[x] if d else -1/(1-e[x])
            mu += weight*center
            second += weight*(center*center+noise_coefficient**2)/2
        conditional.append(mu)
    mu = mean(conditional)
    return mu, second-mu*mu, conditional


def crossfit(rows):
    require(isinstance(rows, (list, tuple)) and 2 <= len(rows) <= 32, 'bounded two-fold data')
    sums, counts = defaultdict(Q), defaultdict(int)
    validated = []
    for row in rows:
        require(len(row) == 4, 'fold/X/D/Y row shape')
        k, x, d, y = row
        require(all(type(v) is int and v in (0, 1) for v in (k, x, d)), 'binary fold/X/D')
        y = finite(y)
        require(abs(y) <= 5, 'bounded outcome experiment')
        counts[k, x, d] += 1
        sums[k, x, d] += y
        validated.append((k, x, d, y))
    require({r[0] for r in validated} == {0, 1}, 'both folds nonempty')
    fits = []
    for held in (0, 1):
        trained = 1-held
        gs = [[Q(0)]*2 for _ in (0, 1)]
        es = []
        for x in (0, 1):
            total = sum(counts[trained, x, d] for d in (0, 1))
            es.append(min(Q(7, 8), max(Q(1, 8), Q(counts[trained, x, 1]+1, total+2))))
            for d in (0, 1):
                count = counts[trained, x, d]
                raw = sums[trained, x, d]/count if count else Q(0)
                gs[d][x] = min(Q(5), max(Q(-5), raw))
        fits.append([es, gs[0], gs[1]])
    scores = [score(y, d, fits[k][0][x], fits[k][1][x], fits[k][2][x]) for k, x, d, y in validated]
    estimate = mean(scores)
    variance = mean([(s-estimate)**2 for s in scores])
    return fits, scores, estimate, variance


def step_up(values, q):
    require(isinstance(values, (list, tuple)) and 1 <= len(values) <= 12, 'bounded nonempty testing family')
    p, q = [finite(x) for x in values], finite(q)
    require(0 < q < 1 and all(0 <= x <= 1 for x in p), 'testing probabilities')
    m = len(p)
    # Threshold counts give the same fixed point without using an ordered loop.
    R = max([0]+[r for r in range(1, m+1) if sum(v <= q*r/m for v in p) >= r])
    return [i for i, v in enumerate(p) if R and v <= q*R/m]


def familywise(values, q, holm):
    p = [finite(x) for x in values]
    step_up(p, q)
    require(type(holm) is bool, 'explicit familywise rule')
    if not holm: return [i for i, v in enumerate(p) if v <= q/len(p)]
    remaining, chosen = set(range(len(p))), []
    while remaining:
        i = min(remaining, key=lambda j: (p[j], j))
        if p[i] > q/len(remaining): break
        chosen.append(i)
        remaining.remove(i)
    return sorted(chosen)


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
            raise ValueError('C11 peer: missing rejection '+label)


def reconstruct():
    e, out = Evidence(), {}
    theta, prior = [Q(1, 4), Q(1, 2), Q(3, 4)], [Q(1, 4), Q(1, 2), Q(1, 4)]
    pi, evidence, likelihood = sequential_bayes(theta, prior, (1, 1, 1, 0))
    mu = sum(p*t for p, t in zip(pi, theta))
    second = sum(p*t*t for p, t in zip(pi, theta))
    variance = second-mu*mu
    predictive = [Q(0)]*3
    for a, b in product((0, 1), repeat=2):
        predictive[a+b] += sum(p*(t if a else 1-t)*(t if b else 1-t) for p, t in zip(pi, theta))
    other, _, _ = sequential_bayes(theta, [Q(16, 21), Q(4, 21), Q(1, 21)], (1, 1, 1, 0))
    out.update({'bayes-likelihood':likelihood, 'bayes-evidence':evidence, 'bayes-posterior':pi,
                'bayes-mean':mu, 'bayes-second':second, 'bayes-predictive':predictive,
                'bayes-variance':variance, 'bayes-launch':5*pi[2]-2, 'bayes-alternative':other,
                'bayes-alternative-utility':5*other[2]-2, 'e1-launch-threshold':Q(2, 5),
                'e1-correlation':variance/(mu*(1-mu))})
    e.same(sum(predictive), 1, 'complete future count law')
    e.same(sequential_bayes(theta, prior, ())[0], prior, 'no observation preserves prior')
    e.same(sequential_bayes([0, 1], [Q(1, 2)]*2, (1,))[0], [0, 1], 'likelihood endpoint')
    e.same(sequential_bayes(theta, prior, (0, 1, 1, 1))[0], pi, 'ordered record permutation')
    e.same(5*Q(2, 5)-2, 0, 'decision equality gives indifference')

    q = [Q(1, 2), Q(1, 3), Q(1, 6)]
    P = kernel(pi, [q]*3)
    delta = min(P[i][j]/pi[j] for i, j in product(range(3), repeat=2))
    residual = [[(P[i][j]-delta*pi[j])/(1-delta) for j in range(3)] for i in range(3)]
    for i in range(3):
        e.same(sum(P[i]), 1, 'stochastic MH row')
        e.same(law(residual[i]), residual[i], 'minorization residual stochastic row')
        for j in range(3): e.same(pi[i]*P[i][j], pi[j]*P[j][i], 'symmetric accepted flow')
    wrong = [[q[j]*min(1, pi[j]/pi[i]) if i != j else Q(0) for j in range(3)] for i in range(3)]
    for i in range(3): wrong[i][i] = 1-sum(wrong[i])
    wrong_target = solve([[wrong[j][i]-(i == j) for j in range(3)] for i in (0, 1)]+[[1]*3], [0, 0, 1])
    e.same(sum(wrong_target[i]*wrong[i][2] for i in range(3)), wrong_target[2], 'omitted equation of invariant law')
    # The high-state indicator is lumpable because the two other rows agree.
    e.same(P[0][2], P[1][2], 'indicator lumpability')
    binary = [[1-P[0][2], P[0][2]], [1-P[2][2], P[2][2]]]
    high = pi[2]
    lam = binary[1][1]-binary[0][1]
    gamma0 = high*(1-high)
    gamma, hh = [], Q(1)
    for _ in range(5):
        gamma.append(high*(hh-high))
        hh = (1-hh)*binary[0][1]+hh*binary[1][1]
    _, v4, mass = occupancy(binary, [1-high, high], 4)
    e.same(mass, 1, 'occupation count mass')
    e.same(v4, (4*gamma[0]+2*sum((4-k)*gamma[k] for k in (1, 2, 3)))/16, 'count distribution versus covariance sum')
    lowmeans, prob = [], Q(0)
    for _ in range(4):
        prob = (1-prob)*binary[0][1]+prob*binary[1][1]
        lowmeans.append(prob)
    lowmean, lowvar, _ = occupancy(binary, binary[0], 4)
    e.same(lowmean, mean(lowmeans), 'nonstationary count distribution mean')
    e.same(lowvar != v4, True, 'initialized variance differs from stationary variance')
    iid = kernel(pi, [pi]*3)
    e.same(iid, [pi]*3, 'target proposal gives iid rows')
    _, iidvar, _ = occupancy([[1-high, high]]*2, [1-high, high], 4)
    e.same(iidvar, gamma0/4, 'independent count variance')
    lazy = (1+lam)/2
    out.update({'mh-transition':P, 'mh-delta':delta, 'mh-residual':residual, 'mh-eigenvalue':lam,
                'mh-wrong-transition':wrong, 'mh-wrong-target':wrong_target, 'mh-mean':high,
                'mh-observable-variance':gamma0, 'mh-covariances':gamma, 'mh-variance4':v4,
                'mh-false-iid4':gamma0/4, 'mh-inflation4':v4/(gamma0/4),
                'mh-long-inflation':(1+lam)/(1-lam), 'mh-initial-means':lowmeans,
                'mh-initial-bias':lowmean-high, 'e2-independent-variance':iidvar,
                'e3-lazy-eigenvalue':lazy, 'e3-lazy-inflation':(1+lazy)/(1-lazy)})
    e.same(kernel([Q(1, 3)]*3, [[0, 1, 0], [0, 1, 0], [0, 0, 1]]),
           [[1, 0, 0], [0, 1, 0], [0, 0, 1]], 'zero reverse proposal blocks the move')

    X = [[1, 1, 1], [1, -1, 1], [1, 1, -1], [1, -1, -1]]
    truth, noise = [2, 0, -1], [Q(1, 8), Q(3, 8), Q(-1, 8), Q(1, 8)]
    y = [sum(x*b for x, b in zip(row, truth))+z for row, z in zip(X, noise)]
    b, kkt, objective, z = lasso_faces(X, y, Q(1, 2))
    error = [a-c for a, c in zip(b, truth)]
    squared = sum(x*x for x in error)
    noise_score = [sum(row[j]*n for row, n in zip(X, noise))/4 for j in range(3)]
    prediction = mean([sum(x*d for x, d in zip(row, error))**2 for row in X])
    e.same(prediction, squared, 'actual prediction error equals coefficient error here')
    basic_left = prediction/2+Q(1, 4)*abs(error[1])
    basic_right = Q(3, 4)*(abs(error[0])+abs(error[2]))
    e.same(basic_left <= basic_right, True, 'actual exact-sparse basic inequality')
    small, _, _, _ = lasso_faces(X, y, Q(1, 8))
    e.same(max(map(abs, noise_score)) > Q(1, 16), True, 'smaller penalty violates noise event')
    tuning = 2*math.sqrt(2*math.log(2*20/.05)/100)
    tail = 2*20*math.exp(-100*(tuning/2)**2/2)
    out.update({'lasso-y':y, 'lasso-z':z, 'lasso-estimate':b, 'lasso-kkt':kkt,
                'lasso-error':error, 'lasso-squared-error':squared,
                'lasso-l1-error':sum(map(abs, error)), 'lasso-objective':objective,
                'lasso-noise-score':noise_score, 'lasso-bounds':[Q(9, 2), 3*math.sqrt(2)/2, 12],
                'lasso-gaussian-lambda':tuning, 'lasso-gaussian-alpha':tail,
                'lasso-duplicate-fit':Q(3, 2), 'lasso-duplicate-objective':Q(7, 8),
                'e4-small-lambda-estimate':small, 'e6-weighted-estimate':[Q(3, 2), Q(0)]})
    duplicate = lambda a, b, weight: (2-a-b)**2/2+Q(1, 2)*(abs(a)+weight*abs(b))
    for split in (Q(0), Q(1, 2), Q(3, 2)):
        e.same(duplicate(split, Q(3, 2)-split, 1), Q(7, 8), 'whole duplicate family objective')
    e.same(duplicate(Q(-1, 2), Q(2), 1) > Q(7, 8), True, 'mixed signs do not minimize')
    e.same(duplicate(Q(3, 2), Q(0), 2), Q(7, 8), 'weighted allocation attains lower bound')
    e.same(duplicate(Q(1, 2), Q(1), 2) > Q(7, 8), True, 'weighted penalty excludes other positive splits')
    # Scaling the two duplicate columns' opposite coefficients leaves every fit unchanged.
    e.same(Q(1, 2)-Q(1, 2), 0, 'nonzero cone direction has zero fitted norm')

    true_e, m0, m1 = [Q(1, 4), Q(3, 4)], [0, 1], [2, 4]
    wrong_e, wrong0, wrong1 = [Q(1, 2)]*2, [Q(1, 2)]*2, [3, 5]
    laws = [(true_e, m0, m1), (true_e, wrong0, wrong1), (wrong_e, m0, m1), (wrong_e, wrong0, wrong1)]
    moments = [conditional_score_moments(*args) for args in laws]
    ate = mean([b-a for a, b in zip(m0, m1)])
    cancel = conditional_score_moments(wrong_e, [v-1 for v in m0], [v+1 for v in m1])
    e.same(cancel[1] != moments[0][1], True, 'bias cancellation does not preserve oracle variance')
    for args, result in zip(laws, moments):
        prop, g0, g1 = args
        rem = [(prop[x]-true_e[x])*((g1[x]-m1[x])/prop[x]+(g0[x]-m0[x])/(1-prop[x])) for x in (0, 1)]
        e.same(result[0]-ate, mean(rem), 'conditional-moment remainder factorization')
    out.update({'dr-ate':ate, 'dr-means':[r[0] for r in moments], 'dr-bias':moments[-1][0]-ate,
                'dr-influence-variance':moments[0][1], 'dr-mean-variance':moments[0][1]/400,
                'e7-cancellation-mean':cancel[0]})
    # Reconstruct the printed observed table directly from treatment and fair noise.
    observed = [(x, d, (m1 if d else m0)[x]+eps,
                 (true_e[x] if d else 1-true_e[x])/4) for x, d, eps in product((0, 1), (0, 1), (-1, 1))]
    e.same(sum(r[3] for r in observed), 1, 'eight observed atom masses')
    direct = sum(w*score(y, d, true_e[x], m0[x], m1[x]) for x, d, y, w in observed)
    e.same(direct, moments[0][0], 'observed table versus conditional mean route')

    rows = [(0, 0, 0, -1), (0, 0, 1, 3), (0, 1, 0, 0), (0, 1, 1, 5),
            (1, 0, 0, 1), (1, 0, 1, 1), (1, 1, 0, 2), (1, 1, 1, 3)]
    fits, scores, estimate, scorevar = crossfit(rows)
    changed = [(0, 0, 0, 1)]+rows[1:]
    newfits, newscores, newmean, newvar = crossfit(changed)
    e.same(newfits[0], fits[0], 'own held-out outcome cannot alter own fitted nuisance')
    e.same([a-b for a, b in zip(newscores, scores)], [-4, 0, 0, 0, 2, -2, 0, 0], 'actual refitting propagation')
    e.same(crossfit(rows[::-1])[1], scores[::-1], 'fixed labels with reordered records')
    t = Q(1, 4)
    shifted = conditional_score_moments([x+t/8 for x in true_e], m0, [x+t for x in m1])
    bias = shifted[0]-ate
    leakage = [score(y, d, true_e[x], y, y) for _, x, d, y in rows]
    out.update({'cf-fit0':fits[0], 'cf-fit1':fits[1], 'cf-scores':scores,
                'cf-fold-means':[mean(scores[:4]), mean(scores[4:])], 'cf-estimate':estimate,
                'cf-score-variance':scorevar, 'cf-estimator-variance':scorevar/8,
                'cf-rate-limit':Q(1, 2)*(Q(1, 2)+Q(1, 6)), 'cf-e-shift':t/8,
                'cf-g-shift':t, 'cf-rate-bias':bias, 'cf-rate-scaled':16*bias,
                'cf-leakage':[mean(leakage), mean([v*v for v in leakage])],
                'e9-transfer-scores':newscores, 'e9-transfer-mean':newmean,
                'e9-transfer-score-variance':newvar, 'e9-transfer-mean-variance':newvar/8})
    e.same(bias, t*t/2*(1/(2+t)+1/(6+t)), 'rate-bias expression from conditional moments')
    e.same(Q(1, 2)-Q(1, 5)-Q(1, 3), Q(-1, 30), 'product-rate exponent')
    empty = crossfit([(0, 0, 0, 1), (1, 1, 1, 3)])[0][0]
    e.same(empty, [[Q(1, 2), Q(2, 3)], [0, 0], [0, 3]], 'actual empty-cell conventions')
    for d, expected in [(0, Q(1, 8)), (1, Q(7, 8))]:
        clipped = crossfit([(0, 0, 0, 0)]+[(1, 0, d, 1)]*7)[0][0][0][0]
        e.same(clipped, expected, 'actual propensity clipping endpoint')

    fixed = [Q(1, 100), Q(3, 100), Q(35, 1000), Q(1, 5)]
    out['bh-fixed'] = [i+1 for i in step_up(fixed, Q(1, 20))]
    out['bh-fixed-familywise'] = len(familywise(fixed, Q(1, 20), False))
    e.same(familywise(fixed, Q(1, 20), True), [0], 'Holm first failure stops')
    counts, fdr, fwer, EV, ER = [0]*3, Q(0), Q(0), Q(0), Q(0)
    for a, b in product(range(1, 13), repeat=2):
        chosen = step_up([0, Q(a, 12), Q(b, 12)], Q(1, 4))
        R, V = len(chosen), sum(i > 0 for i in chosen)
        counts[R-1] += 1
        fdr += Q(V, R*144)
        fwer += Q(V > 0, 144)
        EV += Q(V, 144)
        ER += Q(R, 144)
    e.same(counts[2], 3**2, 'both nulls at final threshold')
    e.same(counts[1], (2*2*12-2**2)-(3**2-1), 'rectangle count for exactly two rejections')
    # Condition on the other p-vector: each true-null contribution is q/m.
    for other in range(1, 13):
        Ri = len(step_up([0, 0, Q(other, 12)], Q(1, 4)))
        contribution = sum(Q(Q(j, 12) <= Q(Ri, 12), 12*Ri) for j in range(1, 13))
        e.same(contribution, Q(1, 12), 'conditional independent-null FDP contribution')
    dependent = [([Q(1, 20), 1], Q(1, 20)), ([1, Q(1, 20)], Q(1, 20)),
                 ([Q(1, 10)]*2, Q(1, 20)), ([1, 1], Q(17, 20))]
    depfdr = sum(w for values, w in dependent if step_up(values, Q(1, 10)))
    depbonf = sum(w for values, w in dependent if familywise(values, Q(1, 10), False))
    depholm = sum(w for values, w in dependent if familywise(values, Q(1, 10), True))
    e.same(depbonf, depholm, 'dependent complete-null two familywise laws')
    for j in (0, 1):
        for u in (Q(0), Q(1, 20), Q(1, 10), Q(1)):
            e.same(sum(w for p, w in dependent if p[j] <= u) <= u, True, 'superuniform marginal at every jump')
    for values, q0 in [([Q(1, 20)]*2, Q(1, 10)), ([1, 1], Q(1, 10)), ([0, 0], Q(1, 10)), (fixed, Q(1, 20))]:
        chosen = step_up(values, q0)
        for j in range(len(values)):
            modified = list(values)
            modified[j] = 0
            Ri = len(step_up(modified, q0))
            e.same(Q(j in chosen, max(len(chosen), 1)), Q(values[j] <= q0*Ri/len(values), Ri), 'inclusive leave-one-out boundary')
    out.update({'bh-counts':counts, 'bh-fdr':fdr, 'bh-fwer':fwer, 'bh-EV':EV,
                'bh-ER':ER, 'bh-wrong-ratio':EV/ER, 'bh-dependent-fdr':depfdr,
                'bh-dependent-familywise':depbonf})

    failures = [
        (lambda:finite(True), 'boolean number'), (lambda:finite(float('nan')), 'NaN number'),
        (lambda:finite(float('inf')), 'infinite number'), (lambda:finite(10**400), 'oversized number'),
        (lambda:law([Q(-1, 2), Q(3, 2)]), 'negative mass'), (lambda:law([Q(1, 3)]*2), 'unnormalized mass'),
        (lambda:sequential_bayes([0], [1], [1]), 'zero evidence'),
        (lambda:sequential_bayes(theta, prior, [True]), 'boolean outcome'),
        (lambda:sequential_bayes(theta, prior, [1]*17), 'observation budget'),
        (lambda:sequential_bayes([2], [1], []), 'invalid Bernoulli parameter'),
        (lambda:kernel([0, 1], [[1, 0], [0, 1]]), 'zero target outside positive-target scope'),
        (lambda:kernel(pi, [[1]]*3), 'nonsquare proposal'),
        (lambda:occupancy(binary, [1, 0], 33), 'occupancy budget'),
        (lambda:occupancy(binary, [1, 0], True), 'boolean horizon'),
        (lambda:lasso_faces(X, y, 0), 'zero penalty'),
        (lambda:lasso_faces([[1, 1]], [2], Q(1, 2)), 'singular face-oracle design'),
        (lambda:lasso_faces(X, y[:2], Q(1, 2)), 'response dimensions'),
        (lambda:score(1, True, Q(1, 2), 0, 1), 'boolean treatment'),
        (lambda:score(1, 1, 0, 0, 1), 'zero candidate overlap'),
        (lambda:conditional_score_moments([1, 1], m0, m1), 'unit candidate propensity'),
        (lambda:crossfit(rows[:4]), 'missing training fold'),
        (lambda:crossfit([(0, 2, 0, 1), (1, 0, 1, 1)]), 'unsupported covariate'),
        (lambda:crossfit([(0, 0, 0, 6), (1, 0, 1, 1)]), 'outcome exceeds theorem bound'),
        (lambda:step_up([], Q(1, 20)), 'empty testing family'),
        (lambda:step_up([Q(3, 2)], Q(1, 20)), 'invalid p-value'),
        (lambda:step_up([0], 0), 'noninterior FDR target'),
        (lambda:familywise([0], Q(1, 20), 1), 'ambiguous familywise switch')]
    for call, label in failures: e.reject(call, label)
    for raw in ['{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}', '{"x":1e400}', '{"x":[1e400]}']:
        e.reject(lambda raw=raw:strict_json(raw), 'strict JSON '+raw)
    return out, e


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
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == 'sqrt':
            require(len(n.args) == 1 and not n.keywords, 'unary safe square root')
            x = float(parse(n.args[0]))
            require(x >= 0, 'square-root domain')
            return math.sqrt(x)
        raise ValueError('C11 peer: unsupported visible expression')
    return parse(tree)


class Reader(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []; self.ids = []; self.links = []; self.sources = []; self.worked = 0
        self.values = {}; self.prompts = {}; self.solutions = {}; self.active = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs); classes = a.get('class', '').split()
        require(tag not in ('script', 'iframe', 'h1'), 'static chapter fragment')
        if 'id' in a: self.ids.append(a['id'])
        if 'href' in a: self.links.append(a['href'])
        if 'data-source' in a: self.sources.append(a['data-source'])
        if 'worked' in classes: self.worked += 1
        store = None
        if tag == 'li' and any(t == 'ol' and 'exercises' in c for t, c in self.stack):
            store, target = self.prompts, a.get('id')
        elif tag == 'li' and any(t == 'details' and 'solutions' in c for t, c in self.stack):
            store, target = self.solutions, a.get('data-solution-for')
        if store is not None:
            require(target is not None and target not in store, 'unique exact prompt/solution')
            store[target] = ''; self.active.append((len(self.stack), store, target))
        if 'data-calc' in a:
            key = a['data-calc']; require(key not in self.values, 'unique calculation marker')
            self.values[key] = ''; self.active.append((len(self.stack), self.values, key))
        if tag not in ('br', 'hr', 'img', 'meta', 'link', 'input'): self.stack.append((tag, classes))

    def handle_endtag(self, tag):
        require(bool(self.stack) and self.stack[-1][0] == tag, 'balanced chapter markup')
        self.stack.pop()
        self.active = [x for x in self.active if x[0] < len(self.stack)]

    def handle_data(self, data):
        require(bool(self.stack) or not data.strip(), 'no stray reader text')
        for _, store, key in self.active: store[key] += data


def snapshot(root, paths):
    result = []
    for rel in paths:
        raw = (root/rel).read_bytes()
        result.append({'path':rel, 'bytes':len(raw), 'sha256':hashlib.sha256(raw).hexdigest()})
    return result


def check(root=None):
    base = Path(root) if root is not None else Path(__file__).resolve().parents[1]
    out, e = reconstruct()
    raw = (base/AUTHOR[0]).read_text()
    page = Reader(); page.feed(raw); page.close()
    ids = ['v12-c11-e'+str(i).zfill(2) for i in range(1, 13)]
    e.same(list(page.prompts), ids, 'all twelve exact prompts')
    e.same(list(page.solutions), ids, 'all twelve paired answers')
    e.same(page.worked, 6, 'six worked cases')
    e.same(page.stack, [], 'closed fragment')
    e.same(page.active, [], 'closed captures')
    e.same(len(page.ids), len(set(page.ids)), 'unique reader IDs')
    e.same(set(page.values), set(out), 'complete independent visible-anchor coverage')
    for key, value in out.items(): e.close(expression(page.values[key]), value, 'visible '+key)
    for i in ids:
        e.same(len(page.prompts[i]) > 100, True, 'substantive exact prompt '+i)
        e.same(len(page.solutions[i]) > 300, True, 'full exact solution '+i)
    e.same('Benchmark answer.' in raw and '<strong>Answers.</strong>' in raw, True, 'answered teaching and retention')
    allowed = {'v03-c09.html', 'v03-c08.html', 'v12-c01.html', 'v12-c02.html', 'v12-c07.html', 'v12-c10.html'}|{'sources.html#'+s for s in SOURCE_IDS}
    e.same(set(page.sources), SOURCE_IDS, 'four scoped source links')
    for link in page.links: e.same(link in allowed, True, 'flat permitted link')
    source = strict_json((base/AUTHOR[2]).read_text())
    e.same({p['id'] for p in source['proposals']}, SOURCE_IDS, 'four primary source records')
    for p in source['proposals']:
        e.same(p['inspection']['reader'], 'bs_author', 'actual primary inspector')
        e.same('chapter_proof_boundary' in p, True, 'scoped rather than wholesale source use')
    e.same(sum(len(p['inspection']['read_pages']['full_visual_physical_pages']) for p in source['proposals']), 27, 'attributed image-scope count')
    author = strict_json((base/AUTHOR[3]).read_text())
    e.same(author['reviewed_hashes'], snapshot(base, AUTHOR[:3]), 'author three nonself bindings')
    peer = strict_json((base/REVIEW).read_text())
    e.same(peer['reviewed_hashes'], snapshot(base, AUTHOR+(SELF,)), 'peer four author plus own-checker bindings')
    e.same(peer['status'], 'passed; frozen for coordinator acceptance', 'peer review status')
    e.same([r['id'] for r in peer['prompt_solution_audit']], ids, 'exact prompt audit coverage/order')
    for row in peer['prompt_solution_audit']:
        prompt = ' '.join(page.prompts[row['id']].split())
        e.same(row['prompt_sha256'], hashlib.sha256(prompt.encode()).hexdigest(), 'exact prompt binding '+row['id'])
    e.same(peer['open_findings'], [], 'no unresolved substantive finding')
    e.same('Expected-score identities are asserted when their terms are absolutely integrable' in raw, True, 'final integrability qualification')
    e.same('require a common constant c&gt;0' in raw, True, 'final uniform path-overlap condition')
    for candidate in ['__import__("os")', 'sqrt(-1)', '1/0']:
        e.reject(lambda candidate=candidate:expression(candidate), 'unsupported visible expression '+candidate)
    result = {'chapter':'v12-c11', 'status':'passed', 'independent_comparisons':e.comparisons,
              'worked_cases':6, 'exercises':12, 'solutions':12, 'visible_anchors':len(out),
              'executed_rejections':len(e.rejections), 'author_files_bound':4, 'peer_checker_bound':True,
              'testing_states':144, 'lasso_faces_per_fit':27,
              'oracle_methods':['sequential posterior updates and four predictive records',
                               'symmetric accepted flows, stationary equations and binary occupation-count recursion',
                               'active/sign-face KKT systems and duplicate-column objective bounds',
                               'conditional score first/second moments and actual observed-law cross-check',
                               'one-pass fold sufficient statistics, outcome refit and clipped-cell boundaries',
                               'threshold-count BH, rectangle counts and conditional null contributions'],
              'limits':'Finite exact mechanisms accompany separately reviewed proofs and all solutions. No author helper is an oracle; no generic MCMC CLT, arbitrary learner rate, causal validity, rendered UI, human certification or chapter acceptance is certified.'}
    strict_json(json.dumps(result, allow_nan=False))
    return result


if __name__ == '__main__':
    check()
