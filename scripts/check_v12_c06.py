"""Readonly, bounded original-contract checks for the experiments chapter.

Exact assignment enumeration and distinct moment identities are compared with
the manuscript. Analytic proof reading is recorded separately. There is no
network, random simulation, third-party module or external runtime input.
check() returns a strict JSON-safe summary; the successful CLI is silent.
"""
from fractions import Fraction as F
from html.parser import HTMLParser
from itertools import combinations, product
import hashlib
import json
from math import ceil, erfc, floor, isclose, isfinite, sqrt
from pathlib import Path
from statistics import NormalDist

HTML = 'content/chapters/v12-c06.html'
SELF = 'scripts/check_v12_c06.py'
SOURCES = 'content/reviews/v12-c06-sources.json'
REVIEW = 'content/reviews/v12-c06-author.json'


def need(ok, message):
    if not ok:
        raise ValueError('v12-c06: ' + message)


def scalar(x):
    need(type(x) in (int, float, F), 'numeric value excluding bool')
    try:
        finite = isfinite(float(x))
    except (OverflowError, ValueError):
        finite = False
    need(finite, 'finite representable numeric value')
    return F(str(x)) if type(x) is float else F(x)


def vector(x):
    need(isinstance(x, (list, tuple)) and len(x) > 0, 'nonempty vector')
    return tuple(scalar(v) for v in x)


def count(x, minimum=1):
    need(type(x) is int and x >= minimum, 'integer count in domain')
    return x


def probability(x, open_interval=False):
    x = scalar(x)
    need(0 < x < 1 if open_interval else 0 <= x <= 1, 'probability in domain')
    return x


def weights(x):
    x = vector(x)
    need(all(p > 0 for p in x) and sum(x) == 1, 'positive normalized finite-law weights')
    return x


def mean(x):
    return sum(x) / F(len(x))


def variance(x, ddof=0):
    need(len(x) > ddof, 'variance degrees of freedom')
    mu = mean(x)
    return sum((v-mu)**2 for v in x) / (len(x)-ddof)


def assignments(n, n1):
    count(n, 2)
    count(n1)
    need(n <= 12 and n1 < n, 'bounded finite enumeration, nonempty arms')
    return tuple(tuple(int(i in selected) for i in range(n))
                 for selected in combinations(range(n), n1))


def binary(z):
    need(isinstance(z, (list, tuple)) and z, 'nonempty binary vector')
    need(all(type(v) is int and v in (0, 1) for v in z), 'binary integer labels')
    return tuple(z)


def contrast(y, z):
    y, z = vector(y), binary(z)
    need(len(y) == len(z), 'outcome and assignment lengths agree')
    need(0 < sum(z) < len(z), 'observed contrast requires both arms')
    return mean([v for v, d in zip(y, z) if d]) - mean([v for v, d in zip(y, z) if not d])


def observed(y0, y1, z):
    return tuple(b if d else a for a, b, d in zip(y0, y1, z))


def finite_law(y0, y1, n1):
    y0, y1 = vector(y0), vector(y1)
    need(len(y0) == len(y1), 'equal potential-table lengths')
    zs = assignments(len(y0), n1)
    out = []
    for z in zs:
        y = observed(y0, y1, z)
        vhat = None
        if 1 < n1 < len(z)-1:
            a = [v for v, d in zip(y, z) if d]
            b = [v for v, d in zip(y, z) if not d]
            vhat = variance(a, 1)/len(a)+variance(b, 1)/len(b)
        out.append((z, contrast(y, z), vhat))
    return out


def finite_formula(y0, y1, n1):
    n = len(y0)
    return variance(y1, 1)/n1 + variance(y0, 1)/(n-n1) - variance([b-a for a, b in zip(y0, y1)], 1)/n


def rank_p_values(stats, probs):
    stats, probs = vector(stats), weights(probs)
    need(len(stats) == len(probs), 'matching finite statistic/weight dimensions')
    return tuple(sum(q for t, q in zip(stats, probs) if t >= s) for s in stats)


def fisher_p(y, z, effect=0):
    y, z, effect = vector(y), binary(z), scalar(effect)
    need(len(y) == len(z), 'matching sharp-null data')
    actual = abs(contrast([v-effect*d for v, d in zip(y, z)], z))
    base = [v-effect*d for v, d in zip(y, z)]
    zs = assignments(len(y), sum(z))
    return F(sum(abs(contrast(base, a)) >= actual for a in zs), len(zs))


def stratified_law(y0, y1, groups, counts):
    y0, y1 = vector(y0), vector(y1)
    need(len(y0) == len(y1) <= 12, 'bounded equal potential-table dimensions')
    need(isinstance(groups, (tuple, list)) and isinstance(counts, (tuple, list))
         and len(groups) == len(counts) > 0, 'matching strata and counts')
    need(all(isinstance(g, (tuple, list)) and len(g) >= 2 for g in groups), 'nonempty two-arm stratum identity lists')
    flat = [i for g in groups for i in g]
    need(all(type(i) is int for i in flat) and sorted(flat) == list(range(len(y0))), 'strata partition all unit identities once')
    choices = [assignments(len(g), k) for g, k in zip(groups, counts)]
    need(len(groups) <= 6, 'bounded stratum enumeration')
    out = []
    for local in product(*choices):
        z = [0]*len(y0)
        estimates = []
        for g, zg in zip(groups, local):
            for i, d in zip(g, zg):
                z[i] = d
            estimates.append(contrast(observed([y0[i] for i in g], [y1[i] for i in g], zg), zg))
        weighted = sum(F(len(g), len(y0))*d for g, d in zip(groups, estimates))
        out.append((tuple(z), weighted, contrast(observed(y0, y1, z), z)))
    return out


def gaussian_power(var1, var0, n1, n0, effect, alpha):
    var1, var0, effect = scalar(var1), scalar(var0), scalar(effect)
    count(n1)
    count(n0)
    alpha = probability(alpha, True)
    need(var1 > 0 and var0 > 0, 'positive known arm variances')
    v = float(scalar(var1/n1+var0/n0))
    q = 1-float(alpha)/2
    need(isfinite(v) and v > 0 and 0 < q < 1, 'numerically resolved variance and Gaussian critical probability')
    z = NormalDist().inv_cdf(q)
    lam = float(effect)/sqrt(v)
    need(isfinite(lam), 'finite Gaussian noncentrality')
    cdf = lambda x: erfc(-x/sqrt(2))/2
    return cdf(lam-z)+cdf(-lam-z)


def best_allocation(n, var1, var0):
    count(n, 2)
    var1, var0 = scalar(var1), scalar(var0)
    need(var1 > 0 and var0 > 0, 'positive allocation variances')
    opt = n*sqrt(float(var1))/(sqrt(float(var1))+sqrt(float(var0)))
    candidates = {max(1, min(n-1, k)) for k in (floor(opt), ceil(opt))}
    n1 = min(candidates, key=lambda k: (var1/k+var0/(n-k), k))
    return n1, n-n1, var1/n1+var0/(n-n1)


def cluster_variance(j, m, common, individual):
    count(j)
    count(m)
    common, individual = scalar(common), scalar(individual)
    need(common >= 0 and individual >= 0 and common+individual > 0, 'nonnegative nonzero Gaussian components')
    return 2*(common+individual/m)/j


def encouragement(types, p, direct=0):
    p, direct = probability(p, True), scalar(direct)
    need(isinstance(types, (list, tuple)) and 0 < len(types) <= 16, 'bounded nonempty compliance types')
    need(all(isinstance(t, (tuple, list)) and len(t) == 5 for t in types), 'share, D0, D1, Y0, Y1 type rows')
    shares = weights([t[0] for t in types])
    rows = []
    for q, (_, d0, d1, y0, y1) in zip(shares, types):
        binary((d0, d1))
        y0, y1 = scalar(y0), scalar(y1)
        for z, pz in ((0, 1-p), (1, p)):
            d = d1 if z else d0
            rows.append((q*pz, z, d, (y1 if d else y0)+direct*z, y1-y0))
    yd = tuple(sum(q*y for q, z, d, y, t in rows if z == arm)/(p if arm else 1-p) for arm in (0, 1))
    dd = tuple(sum(q*d for q, z, d, y, t in rows if z == arm)/(p if arm else 1-p) for arm in (0, 1))
    itt, gamma = yd[1]-yd[0], dd[1]-dd[0]
    need(gamma != 0, 'Wald ratio requires nonzero first stage; ITT alone can still exist')
    beta = itt/gamma
    scores = []
    for q, z, d, y, t in rows:
        factor = 1/p if z else -1/(1-p)
        scores.append((q, factor*(y-yd[z]), factor*(d-dd[z])))
    vy = sum(q*sy**2 for q, sy, sd in scores)
    vd = sum(q*sd**2 for q, sy, sd in scores)
    cov = sum(q*sy*sd for q, sy, sd in scores)
    treated = sum(q*d for q, z, d, y, t in rows)
    need(treated > 0, 'treated-effect mixture requires treated mass')
    return dict(rows=rows, yd=yd, dd=dd, itt=itt, gamma=gamma, beta=beta, vy=vy, vd=vd, cov=cov,
                variance=(vy+beta**2*vd-2*beta*cov)/gamma**2,
                ate=sum(q*t for q, z, d, y, t in rows), treated=treated,
                att=sum(q*d*t for q, z, d, y, t in rows)/treated, scores=scores)


def sample_wald(rows):
    need(isinstance(rows, (list, tuple)) and rows, 'nonempty observed encouragement sample')
    need(all(isinstance(r, (list, tuple)) and len(r) == 3 for r in rows), 'observed Z,D,Y rows')
    zs = binary([r[0] for r in rows])
    ds = binary([r[1] for r in rows])
    ys = vector([r[2] for r in rows])
    gamma = contrast(ds, zs)
    need(gamma != 0, 'sample first stage is zero')
    return contrast(ys, zs)/gamma


def path_exposure(z, i):
    z = binary(z)
    need(len(z) == 3 and type(i) is int and 0 <= i <= 2, 'three-node path identity')
    neighbors = ((1,), (0, 2), (1,))[i]
    return z[i], int(any(z[j] for j in neighbors))


def path_design(p):
    p = probability(p, True)
    return tuple((z, p**sum(z)*(1-p)**(3-sum(z))) for z in product((0, 1), repeat=3))


def check_design(design):
    need(isinstance(design, (list, tuple)) and 0 < len(design) <= 8, 'bounded nonempty three-unit design')
    need(all(isinstance(row, (list, tuple)) and len(row) == 2 for row in design), 'assignment/probability rows')
    zs = [binary(row[0]) for row in design]
    need(all(len(z) == 3 for z in zs) and len(set(zs)) == len(zs), 'distinct three-node assignments')
    ps = weights([row[1] for row in design])
    return tuple(zip(zs, ps))


def ht_law(design, table):
    design = check_design(design)
    need(isinstance(table, (tuple, list)) and len(table) == 3, 'three complete exposure potential dictionaries')
    exposures = tuple(product((0, 1), repeat=2))
    need(all(isinstance(t, dict) and set(t) == set(exposures) for t in table), 'complete four-exposure potential tables')
    table = [{h: scalar(v) for h, v in t.items()} for t in table]
    hs, signs = ((0, 0), (1, 0)), {(0, 0): -1, (1, 0): 1}
    pi = {(i, h): sum(q for z, q in design if path_exposure(z, i) == h) for i in range(3) for h in hs}
    need(all(v > 0 for v in pi.values()), 'positive target exposure probability for every unit')
    law = []
    for z, q in design:
        value = F(0)
        for i in range(3):
            h = path_exposure(z, i)
            if h in hs:
                value += F(signs[h], 3)*table[i][h]/pi[i, h]
        law.append((q, z, value))
    mu = sum(q*v for q, z, v in law)
    actual = sum(q*(v-mu)**2 for q, z, v in law)
    covariance_sum = F(0)
    joint = {}
    for i, j, h, k in product(range(3), range(3), hs, hs):
        pij = sum(q for z, q in design if path_exposure(z, i) == h and path_exposure(z, j) == k)
        joint[i, j, h, k] = pij
        covariance_sum += F(signs[h]*signs[k], 9)*table[i][h]*table[j][k]*(pij-pi[i, h]*pi[j, k])/(pi[i, h]*pi[j, k])
    return dict(law=law, mean=mu, variance=actual, covariance_formula=covariance_sum, pi=pi, joint=joint)


def validate_mapping(design, outcome):
    seen = {}
    for z, q in check_design(design):
        for i in range(3):
            key = i, path_exposure(z, i)
            value = scalar(outcome(i, z))
            if key in seen:
                need(value == seen[key], 'equal exposure labels must give equal potential outcomes')
            seen[key] = value
    return seen


def bounded_mean(response, respondent, lower, upper):
    response, lower, upper = probability(response), scalar(lower), scalar(upper)
    need(lower <= upper, 'ordered outcome support')
    if response == 0:
        need(respondent is None, 'zero response has no respondent mean')
        return lower, upper
    respondent = scalar(respondent)
    need(lower <= respondent <= upper, 'respondent mean inside known support')
    return response*respondent+(1-response)*lower, response*respondent+(1-response)*upper


def attrition_interval(r1, m1, r0, m0, lower=0, upper=10):
    a = bounded_mean(r1, m1, lower, upper)
    b = bounded_mean(r0, m0, lower, upper)
    return a[0]-b[1], a[1]-b[0]


def endpoint_law(upper_endpoint):
    rows = []
    for r0, r1 in product((0, 1), repeat=2):
        q = (F(4, 5) if r0 else F(1, 5))*(F(4, 5) if r1 else F(1, 5))
        y0 = F(6) if r0 else F(0 if upper_endpoint else 10)
        y1 = F(8) if r1 else F(10 if upper_endpoint else 0)
        rows.append((q, r0, r1, y0, y1))
    return rows


def observable_law(rows):
    out = {}
    for q, r0, r1, y0, y1 in rows:
        for z, r, y in ((0, r0, y0), (1, r1, y1)):
            key = z, r, y if r else None
            out[key] = out.get(key, F(0))+q/2
    return out


def strict(raw):
    def pairs(items):
        out = {}
        for key, value in items:
            need(key not in out, 'duplicate JSON member')
            out[key] = value
        return out
    def bad(token):
        raise ValueError('v12-c06: forbidden JSON constant ' + token)
    def decimal(token):
        value = float(token)
        need(isfinite(value), 'finite JSON decimal')
        return value
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=bad, parse_float=decimal)


class Audit:
    def __init__(self):
        self.comparisons = 0
        self.interventions = []
        self.rejections = []

    def eq(self, actual, expected, label):
        self.comparisons += 1
        need(actual == expected, label + ': ' + repr(actual) + ' != ' + repr(expected))

    def near(self, actual, expected, label, tolerance=1e-12):
        self.comparisons += 1
        need(isfinite(float(actual)) and isfinite(float(expected)) and
             isclose(actual, expected, rel_tol=0, abs_tol=tolerance), label + ': numerical disagreement')

    def reject(self, operation, label):
        try:
            operation()
        except ValueError:
            self.rejections.append(label)
        else:
            raise ValueError('v12-c06: missing rejection: ' + label)


class Page(HTMLParser):
    void = {'br', 'hr', 'img', 'meta', 'link', 'input'}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.ids = []
        self.links = []
        self.sources = []
        self.prompts = []
        self.targets = []
        self.answers = {}
        self.answer = None
        self.values = {}
        self.marker = None
        self.worked = 0
        self.h1 = 0
        self.exercise_count = 0
        self.solution_count = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        need(len(a) == len(attrs), 'duplicate HTML attribute')
        if tag == 'h1':
            self.h1 += 1
        if 'id' in a:
            self.ids.append(a['id'])
        if 'href' in a:
            self.links.append(a['href'])
        if 'data-source' in a:
            self.sources.append(a['data-source'])
        if 'worked' in a.get('class', '').split():
            self.worked += 1
        exercise = any(t == 'ol' and 'exercises' in attr.get('class', '').split() for t, attr in self.stack)
        solution = any(t == 'details' and 'solutions' in attr.get('class', '').split() for t, attr in self.stack)
        if tag == 'li' and exercise:
            need('id' in a, 'scored exercise ID')
            self.prompts.append(a['id'])
            self.exercise_count += 1
        if tag == 'li' and solution:
            need(self.answer is None and 'data-solution-for' in a, 'one explicit answer per solution item')
            self.answer = a['data-solution-for']
            need(self.answer not in self.answers, 'unique solution target')
            self.targets.append(self.answer)
            self.answers[self.answer] = ''
            self.solution_count += 1
        if 'data-calc' in a:
            need(tag == 'span' and self.marker is None and a['data-calc'] not in self.values, 'unique visible calculation marker')
            self.marker = a['data-calc']
            self.values[self.marker] = ''
        if tag not in self.void:
            self.stack.append((tag, a))

    def handle_endtag(self, tag):
        need(self.stack and self.stack[-1][0] == tag, 'balanced explicit HTML fragment: ' + tag)
        _, attrs = self.stack.pop()
        if tag == 'span' and 'data-calc' in attrs:
            self.marker = None
        if tag == 'li' and 'data-solution-for' in attrs:
            self.answer = None

    def handle_data(self, data):
        need(bool(self.stack) or not data.strip(), 'no stray top-level text delimiter')
        if self.marker:
            self.values[self.marker] += data
        if self.answer:
            self.answers[self.answer] += data


def calculate(a, page):
    exact, rounded = {}, {}
    y0 = tuple(map(F, range(6)))
    tau = (F(0), F(2))*3
    y1 = tuple(x+t for x, t in zip(y0, tau))
    law = finite_law(y0, y1, 3)
    ds = [row[1] for row in law]
    hats = [row[2] for row in law]
    exact.update({'finite-assignments': len(law), 'finite-ate': mean(ds),
                  'finite-s0': variance(y0, 1), 'finite-s1': variance(y1, 1), 'finite-stau': variance(tau, 1),
                  'finite-variance': variance(ds), 'finite-neyman': mean(hats)})
    a.eq(mean(ds), mean(tau), 'finite enumeration unbiasedness')
    a.eq(variance(ds), finite_formula(y0, y1, 3), 'independent inclusion-moment variance')
    a.eq(variance(ds), F(44, 15), 'heterogeneous finite design anchor')
    a.eq(mean(hats)-variance(ds), variance(tau, 1)/6, 'expected Neyman excess')
    for i in range(6):
        a.eq(mean([F(z[i]) for z, d, v in law]), F(1, 2), 'single inclusion identity')
        for j in range(i):
            a.eq(mean([F(z[i]*z[j]) for z, d, v in law]), F(1, 5), 'pair inclusion identity')
    realized = next(row for row in law if row[0] == (1, 0, 1, 0, 1, 0))
    exact['finite-realized-estimate'], exact['finite-realized-neyman'] = realized[1:]
    a.eq(realized[2] < variance(ds), True, 'actual below-variance realization')
    # Pair-difference and centered definitions are independently compared in every observed arm.
    for z, d, v in law:
        obs = observed(y0, y1, z)
        for arm in (0, 1):
            values = [x for x, zi in zip(obs, z) if zi == arm]
            pairs = sum((x-y)**2 for x, y in combinations(values, 2))/F(len(values)*(len(values)-1))
            a.eq(pairs, variance(values, 1), 'sample pair identity')
    c = F(6, 20)*(F(7**2, 3)+F(5**2, 3))
    exact['finite-range-bound'] = c
    rounded['ex2-halfwidth'] = sqrt(float(c/F(1, 10)))
    a.eq(c >= variance(ds), True, 'known-range variance bound')
    a.eq(mean([F(abs(d-1) >= sqrt(74)) for d in ds]) <= F(1, 10), True, 'actual finite Chebyshev coverage')
    changed = finite_law([100-2*x for x in y0], [100-2*x for x in y1], 3)
    a.eq([r[1] for r in changed], [-2*r[1] for r in law], 'common shift and sign/scale intervention')
    a.eq(variance([r[1] for r in changed]), 4*variance(ds), 'outcome scale squares design variance')
    unbalanced = finite_law(y0, y1, 2)
    a.eq(mean([r[1] for r in unbalanced]), 1, 'changed arm count preserves target')
    a.eq(variance([r[1] for r in unbalanced]), finite_formula(y0, y1, 2), 'changed count covariance identity')
    constant_effect = finite_law(y0, [x+2 for x in y0], 3)
    a.eq(mean([r[2] for r in constant_effect]), variance([r[1] for r in constant_effect]), 'zero effect heterogeneity removes expected Neyman excess')
    constant_levels = finite_law([2]*6, [5]*6, 3)
    a.eq({(r[1], r[2]) for r in constant_levels}, {(F(3), F(0))}, 'zero known ranges make the finite estimate exact')
    a.interventions.extend(['Finite outcome translation/sign/scale preserves the target transform and squares variance.',
                            'Changing complete-randomization arm counts preserves the finite target but changes variance.'])

    # Generate alternative data anew for every actual assignment, then apply the same sharp-zero procedure.
    zs = assignments(6, 3)
    rejection_counts = []
    for effect in range(5):
        ps = [fisher_p([v+effect*d for v, d in zip(y0, z)], z) for z in zs]
        rejected = sum(p <= F(1, 10) for p in ps)
        rejection_counts.append(rejected)
        exact['power-t'+str(effect)] = F(rejected, len(zs))
        exact['ex4-count-t'+str(effect)] = rejected
        a.eq(sum(p <= F(1, 20) for p in ps), 0, 'complement-pair minimum p-value')
    a.eq(rejection_counts, [2, 1, 2, 4, 8], 'actual alternative exact Fisher rejection counts')
    yobs, zobs = tuple(map(F, (0, 1, 2, 5, 6, 7))), (0, 0, 0, 1, 1, 1)
    exact['fisher-observed-difference'] = contrast(yobs, zobs)
    exact['fisher-endpoint-p'] = fisher_p(yobs, zobs, 3)
    a.eq(fisher_p(yobs, zobs, 7), exact['fisher-endpoint-p'], 'both closed acceptance endpoints')
    a.eq(fisher_p(yobs, zobs, 5), 1, 'inversion center statistic zero')
    # Each absolute-statistic comparison changes only where one of two affine factors is zero.
    # Exhausting those rational roots and the resulting open cells certifies the whole real line.
    obs_intercept, obs_slope = contrast(yobs, zobs), -contrast(zobs, zobs)
    breaks = set()
    for z in zs:
        intercept, slope = contrast(yobs, z), -contrast(zobs, z)
        for sign in (-1, 1):
            den = slope+sign*obs_slope
            if den:
                breaks.add(-(intercept+sign*obs_intercept)/den)
    breaks = sorted(breaks)
    probes = [breaks[0]-1, breaks[-1]+1]+breaks+[(x+y)/2 for x, y in zip(breaks, breaks[1:])]
    for candidate in probes:
        a.eq(fisher_p(yobs, zobs, candidate) > F(1, 10), F(3) <= candidate <= F(7), 'complete affine-root inversion cell certificate')
    shifted = [v+F(37, 3) for v in yobs]
    a.eq([fisher_p(shifted, zobs, c) for c in (2, 3, 5, 7, 8)],
         [fisher_p(yobs, zobs, c) for c in (2, 3, 5, 7, 8)], 'sharp-test common-outcome translation')
    a.interventions.extend(['Fisher power regenerates alternative data at five effects under a fixed rejection rule and two sizes.',
                            'All affine-statistic breakpoints and intervening cells certify the continuous inversion; common outcome translation leaves ranks unchanged.'])
    probs, stats = (F(1, 2), F(1, 4), F(1, 4)), (2, 2, 0)
    ps = rank_p_values(stats, probs)
    exact['ex3-top-p'] = ps[0]
    exact['ex3-inclusive-size'] = sum(q for q, p in zip(probs, ps) if p <= F(1, 4))
    strict_ps = [sum(q for q, t in zip(probs, stats) if t > s) for s in stats]
    exact['ex3-strict-size'] = sum(q for q, p in zip(probs, strict_ps) if p <= F(1, 4))
    a.eq(ps, (F(3, 4), F(3, 4), F(1)), 'weighted inclusive tie groups')
    for alpha in sorted(set(ps) | {F(1, 4), F(1, 2)}):
        a.eq(sum(q for q, p in zip(probs, ps) if p <= alpha) <= alpha, True, 'weighted-rank size at all relevant jumps')
    a.eq(exact['ex3-strict-size'], F(3, 4), 'strict-tail invalidity counterexample')
    a.interventions.append('Nonuniform assignment weights and ties expose the failure of a strict-greater randomization tail.')

    sy0 = tuple(map(F, (0, 1, 2, 3, 10, 11, 12, 13)))
    sy1 = tuple(x+2 for x in sy0)
    groups = ((0, 1, 2, 3), (4, 5, 6, 7))
    complete = finite_law(sy0, sy1, 4)
    blocked = stratified_law(sy0, sy1, groups, (2, 2))
    uneven = stratified_law(sy0, sy1, groups, (1, 3))
    exact.update({'strata-complete-count': len(complete), 'strata-complete-variance': variance([r[1] for r in complete]),
                  'strata-blocked-count': len(blocked), 'strata-blocked-variance': variance([r[1] for r in blocked]),
                  'strata-target': mean([r[1] for r in blocked]), 'ex5-assignments': len(uneven),
                  'ex5-weighted-mean': mean([r[1] for r in uneven]), 'ex5-weighted-variance': variance([r[1] for r in uneven]),
                  'ex5-pooled-mean': mean([r[2] for r in uneven])})
    a.eq(exact['strata-complete-variance'], finite_formula(sy0, sy1, 4), 'complete eight-unit inclusion variance')
    for rows, counts in ((blocked, (2, 2)), (uneven, (1, 3))):
        v = sum(F(1, 4)*finite_formula([sy0[i] for i in g], [sy1[i] for i in g], n1) for g, n1 in zip(groups, counts))
        a.eq(variance([r[1] for r in rows]), v, 'independent target-weighted stratum variance')
    a.eq((exact['ex5-weighted-mean'], exact['ex5-weighted-variance'], exact['ex5-pooled-mean']),
         (F(2), F(10, 9), F(7)), 'unequal treatment fractions change pooled target')
    a.interventions.append('Unequal within-stratum treatment fractions reveal pooled composition bias while retaining target-weighted unbiasedness.')

    exact.update({'gaussian-fraction': F(3, 4), 'gaussian-optimal-coefficient': (3+1)**2,
                  'gaussian-balanced-coefficient': F(9, 1)/F(1, 2)+F(1, 1)/F(1, 2)})
    for n in (125, 126):
        n1, n0, v = best_allocation(n, 9, 1)
        a.eq((n1, n0), (94, n-94), 'integer boundary allocation')
        brute = min((F(9, k)+F(1, n-k), k) for k in range(1, n))
        a.eq((v, n1), brute, 'independent complete allocation search at boundary')
        exact['gaussian-v'+str(n)] = v
        rounded['gaussian-p'+str(n)] = gaussian_power(9, 1, n1, n0, 1, F(1, 20))
    rounded['gaussian-p156'] = gaussian_power(9, 1, 78, 78, 1, F(1, 20))
    rounded['gaussian-p158'] = gaussian_power(9, 1, 79, 79, 1, F(1, 20))
    a.eq(rounded['gaussian-p125'] < .8 <= rounded['gaussian-p126'], True, 'optimized minimum sample-size boundary')
    a.eq(rounded['gaussian-p156'] < .8 <= rounded['gaussian-p158'], True, 'equal-allocation minimum even-total boundary')
    a.near(rounded['gaussian-p126'], .8012698751691925, 'exact two-tail Gaussian anchor')
    a.near(gaussian_power(9, 1, 94, 32, 0, F(1, 20)), .05, 'Gaussian null size')
    a.near(gaussian_power(9, 1, 94, 32, -1, F(1, 20)), rounded['gaussian-p126'], 'two-sided effect sign symmetry')
    a.near(gaussian_power(36, 4, 94, 32, 2, F(1, 20)), rounded['gaussian-p126'], 'common outcome unit scaling')
    a.eq(best_allocation(126, 1, 9)[:2], (32, 94), 'arm-label reversal allocation')
    a.interventions.append('Gaussian boundary optimization is independently searched; sign, outcome-unit and arm-label changes preserve appropriate power/allocation identities.')

    m, j = 10, 10
    mean_variance = sum(F(1)+(4 if a == b else 0) for a, b in product(range(m), repeat=2))/m**2
    exact['cluster-variance'] = 2*mean_variance/j
    exact['cluster-wrong-variance'] = F(2*5, j*m)
    exact['cluster-factor'] = exact['cluster-variance']/exact['cluster-wrong-variance']
    rounded['ex7-se-factor'] = sqrt(float(exact['cluster-factor']))
    exact['retention-cluster-limit'] = F(2, j)
    a.eq(exact['cluster-variance'], cluster_variance(j, m, 1, 4), 'row covariance sum versus common-component decomposition')
    a.eq(exact['cluster-factor'], 1+(m-1)*F(1, 5), 'cluster variance factor uses common share')
    a.eq(cluster_variance(10, 10, 0, 5), F(1, 10), 'no common shock restores independent-row variance')
    a.eq(cluster_variance(10, 1, 1, 4), 1, 'one row per cluster')
    a.eq(cluster_variance(10, 100, 1, 4), F(26, 125), 'more dependent rows approaches positive variance floor')
    a.eq(cluster_variance(10, 10, 1, 0), F(1, 5), 'all-common shocks already reach floor')
    a.interventions.append('Removing common shocks, removing idiosyncratic shocks and enlarging existing clusters expose the information boundary.')

    types = ((F(1, 2), 0, 0, 1, 7), (F(1, 8), 1, 1, 2, 6), (F(3, 8), 0, 1, 3, 5))
    comp = encouragement(types, F(1, 2))
    for name, value in (('d0', comp['dd'][0]), ('d1', comp['dd'][1]), ('y0', comp['yd'][0]), ('y1', comp['yd'][1]),
                        ('first-stage', comp['gamma']), ('itt', comp['itt']), ('late', comp['beta']), ('ate', comp['ate']),
                        ('treated', comp['treated']), ('att', comp['att']), ('vy', comp['vy']), ('vd', comp['vd']),
                        ('cov', comp['cov']), ('variance', comp['variance'])):
        exact['compliance-'+name] = value
    qvalues = (F(1), F(4), F(3))
    qs = tuple(row[0] for row in types)
    qmean = sum(p*v for p, v in zip(qs, qvalues))
    qvar = sum(p*(v-qmean)**2 for p, v in zip(qs, qvalues))
    exact['compliance-qmean'], exact['compliance-qvar'] = qmean, qvar
    exact['compliance-wrong-variance'] = (comp['vy']+comp['beta']**2*comp['vd'])/comp['gamma']**2
    a.eq(comp['variance'], 4*qvar/comp['gamma']**2, 'independent type-invariant residual certificate')
    a.eq(comp['variance'], F(116, 3), 'encouragement root-n covariance anchor')
    a.eq([sum(q*s for q, sy, sd in comp['scores'] for s in ([sy] if k == 0 else [sd])) for k in (0, 1)], [0, 0], 'joint score centering')
    expanded = []
    for share, d0, d1, y0i, y1i in types:
        for z in (0, 1):
            d = d1 if z else d0
            expanded.extend([(z, d, y1i if d else y0i)]*int(share*8))
    a.eq(sample_wald(expanded), 2, 'actual finite observed ratio construction')
    # Reconstruct feasible scores from the actual sixteen observed rows, not population helpers.
    phat = F(sum(z for z, d, y in expanded), len(expanded))
    yhat = [mean([F(y) for z, d, y in expanded if z == arm]) for arm in (0, 1)]
    dhat = [mean([F(d) for z, d, y in expanded if z == arm]) for arm in (0, 1)]
    ghat, bhat = dhat[1]-dhat[0], sample_wald(expanded)
    feasible = [(1/phat if z else -1/(1-phat))*((y-yhat[z])-bhat*(d-dhat[z]))/ghat for z, d, y in expanded]
    a.eq(mean(feasible), 0, 'actual fitted ratio influences are centered')
    a.eq(mean([v*v for v in feasible]), comp['variance'], 'empirical plug-in score squares for the exactly proportioned finite sample')
    direct = encouragement(types, F(1, 2), F(1, 2))
    exact['ex8-direct-itt'], exact['ex8-direct-ratio'] = direct['itt'], direct['beta']
    a.eq((direct['itt'], direct['beta']), (F(5, 4), F(10, 3)), 'exclusion failure despite randomized assignment')
    a.eq(direct['gamma'], comp['gamma'], 'direct channel leaves uptake unchanged')
    changed_p = encouragement(types, F(1, 4))
    a.eq((changed_p['beta'], changed_p['ate']), (comp['beta'], comp['ate']), 'encouragement frequency preserves these targets')
    a.eq((changed_p['treated'], changed_p['att']), (F(7, 32), F(22, 7)), 'encouragement frequency changes treated mixture')
    a.eq(changed_p['variance'] != comp['variance'], True, 'encouragement frequency changes iid ratio precision')
    a.interventions.extend(['A direct encouragement outcome increment preserves uptake but breaks the treatment interpretation of the Wald ratio.',
                            'Changing independent encouragement frequency changes the treated mixture and variance, while preserving LATE and ATE.'])

    table = tuple({(d, g): F(i+1+(2*i+2)*d+3*g) for d, g in product((0, 1), repeat=2)} for i in range(3))
    design = path_design(F(1, 2))
    exposure = ht_law(design, table)
    exact['interference-target'] = exposure['mean']
    exact['interference-edge-prob'], exact['interference-center-prob'] = exposure['pi'][0, (0, 0)], exposure['pi'][1, (0, 0)]
    for q, z, v in exposure['law']:
        exact['ht-'+''.join(map(str, z))] = v
    exact['interference-variance'] = exposure['variance']
    exact['ex9-second-moment'] = sum(q*v*v for q, z, v in exposure['law'])
    target = mean([t[1, 0]-t[0, 0] for t in table])
    a.eq(exposure['mean'], target, 'HT enumeration versus complete potential target')
    a.eq(exposure['variance'], exposure['covariance_formula'], 'full joint-inclusion covariance formula')
    a.eq(exposure['variance'], F(688, 9), 'finite interference variance anchor')
    a.eq(exposure['joint'][0, 1, (1, 0), (1, 0)], 0, 'incompatible neighboring exposures')
    validate_mapping(design, lambda i, z: table[i][path_exposure(z, i)])
    p = F(1, 3)
    altered = ht_law(path_design(p), table)
    a.eq(altered['mean'], target, 'unequal Bernoulli exposure weighting remains unbiased')
    a.eq(altered['variance'], altered['covariance_formula'], 'nonuniform assignment joint covariance')
    for i in range(3):
        neighbors = 2 if i == 1 else 1
        a.eq(altered['pi'][i, (0, 0)], (1-p)**(neighbors+1), 'zero-own zero-neighbor marginal probability')
        a.eq(altered['pi'][i, (1, 0)], p*(1-p)**neighbors, 'treated-own zero-neighbor marginal probability')
    a.eq(altered['variance'] != exposure['variance'], True, 'exposure weights alter precision')
    scaled = ht_law(design, [{h: 2*v for h, v in t.items()} for t in table])
    a.eq((scaled['mean'], scaled['variance']), (2*target, 4*exposure['variance']), 'exposure outcome scale')
    fixed_one = tuple((z, F(1, 3)) for z in assignments(3, 1))
    a.reject(lambda: ht_law(fixed_one, table), 'fixed-one design removes center untreated-unexposed support')
    changed_outcome = lambda i, z: table[i][path_exposure(z, i)]+(2*z[2] if i == 0 else 0)
    exact['ex10-remote-outcome'] = changed_outcome(0, (0, 0, 1))
    a.reject(lambda: validate_mapping(design, changed_outcome), 'remote treatment violates old exposure mapping')
    a.interventions.extend(['Nonuniform Bernoulli exposure probabilities and outcome scaling are checked against the full joint-covariance identity.',
                            'Fixed-one assignment fails target positivity; a remote spillover separately fails exposure-map sufficiency.'])

    a1 = bounded_mean(F(4, 5), 8, 0, 10)
    a0 = bounded_mean(F(4, 5), 6, 0, 10)
    interval = attrition_interval(F(4, 5), 8, F(4, 5), 6)
    exact.update({'attrition-y1-low': a1[0], 'attrition-y1-high': a1[1], 'attrition-y0-low': a0[0], 'attrition-y0-high': a0[1],
                  'attrition-low': interval[0], 'attrition-high': interval[1]})
    low, high = endpoint_law(False), endpoint_law(True)
    a.eq(observable_law(low), observable_law(high), 'entire observed law is identical at opposite ATE endpoints')
    for rows, endpoint in ((low, interval[0]), (high, interval[1])):
        a.eq(sum(q for q, r0, r1, y0i, y1i in rows), 1, 'endpoint potential-law normalization')
        a.eq(sum(q*(y1i-y0i) for q, r0, r1, y0i, y1i in rows), endpoint, 'sharp endpoint attained')
    mix = [(q*F(2, 3), r0, r1, y0i, y1i) for q, r0, r1, y0i, y1i in low]
    mix += [(q*F(1, 3), r0, r1, y0i, y1i) for q, r0, r1, y0i, y1i in high]
    a.eq(observable_law(mix), observable_law(low), 'interior mixture preserves observable distribution')
    a.eq(sum(q*(y1i-y0i) for q, r0, r1, y0i, y1i in mix), F(2, 3)*interval[0]+F(1, 3)*interval[1], 'interior effect is the matching convex combination')
    a.eq(attrition_interval(1, 8, 1, 6), (F(2), F(2)), 'complete response collapses identification interval')
    a.eq(bounded_mean(0, None, 0, 10), (F(0), F(10)), 'no response supplies only the stated support')
    treatment_mean = F(4, 5)*8+F(1, 5)*4
    exact['retention-attrition-low'], exact['retention-attrition-high'] = treatment_mean-a0[1], treatment_mean-a0[0]
    a.eq((exact['retention-attrition-low'], exact['retention-attrition-high']), (F(2, 5), F(12, 5)), 'actual treatment follow-up narrows the interval')
    a.interventions.append('Opposite missing-outcome laws and their mixture preserve all observed data; actual follow-up and complete response narrow the identification set.')

    # Actual failed evaluations, not a list of hypothetical invalid cases.
    a.reject(lambda: scalar(True), 'boolean numeric input')
    a.reject(lambda: scalar(float('nan')), 'NaN outcome')
    a.reject(lambda: scalar(float('inf')), 'infinite outcome')
    a.reject(lambda: finite_law([], [], 1), 'empty finite population')
    a.reject(lambda: finite_law([0, 1], [1], 1), 'mismatched potential table')
    a.reject(lambda: finite_law([0, 1], [1, 2], 0), 'empty treated arm')
    a.reject(lambda: finite_law([0, 1], [1, 2], 2), 'empty control arm')
    a.reject(lambda: assignments(13, 6), 'outside bounded finite-enumeration scope')
    a.reject(lambda: contrast([1, 2], [True, 0]), 'boolean assignment label')
    a.reject(lambda: contrast([1, 2], [0, 0]), 'observed empty treated arm')
    a.reject(lambda: rank_p_values([1, 2], [F(1, 4), F(1, 4)]), 'unnormalized assignment law')
    a.reject(lambda: rank_p_values([1, 2], [F(-1), F(2)]), 'negative assignment probability')
    a.reject(lambda: rank_p_values([1, 2], [0, 1]), 'zero-probability assignment retained in support')
    a.reject(lambda: rank_p_values([1], [F(1, 2), F(1, 2)]), 'statistic weight dimension mismatch')
    a.reject(lambda: stratified_law(sy0, sy1, ((0, 1, 2, 3), (3, 5, 6, 7)), (2, 2)), 'overlapping and omitted stratum identities')
    a.reject(lambda: stratified_law(sy0, sy1, groups, (2,)), 'missing stratum treatment count')
    a.reject(lambda: stratified_law(sy0, sy1, (None, groups[1]), (2, 2)), 'malformed stratum identity list')
    a.reject(lambda: stratified_law(sy0, sy1, groups, (4, 2)), 'stratum with no controls')
    a.reject(lambda: gaussian_power(0, 1, 2, 2, 1, .05), 'zero Gaussian arm variance')
    a.reject(lambda: gaussian_power(-1, 1, 2, 2, 1, .05), 'negative Gaussian variance')
    a.reject(lambda: gaussian_power(1, 1, True, 2, 1, .05), 'boolean Gaussian arm count')
    a.reject(lambda: gaussian_power(1, 1, 2, 2, 1, 0), 'zero Gaussian significance level')
    a.reject(lambda: gaussian_power(1, 1, 2, 2, 1, 1), 'unit Gaussian significance level')
    a.reject(lambda: gaussian_power(1, 1, 2, 2, 1, 1e-300), 'unresolved extreme Gaussian critical probability')
    a.reject(lambda: gaussian_power(1e308, 1e308, 1, 1, 1, .05), 'unrepresentable Gaussian contrast variance')
    a.reject(lambda: best_allocation(1, 9, 1), 'insufficient total for two arms')
    a.reject(lambda: cluster_variance(10, 0, 1, 4), 'empty cluster')
    a.reject(lambda: cluster_variance(10, 10, -1, 4), 'negative common component')
    a.reject(lambda: cluster_variance(10, 10, 0, 0), 'degenerate claimed Gaussian variance')
    a.reject(lambda: encouragement(types, 0), 'encouragement arm with zero probability')
    a.reject(lambda: encouragement(((F(1), 0, 0, 1, 7),), F(1, 2)), 'zero population first stage for a ratio')
    a.reject(lambda: sample_wald([(0, 0, 1), (0, 1, 2)]), 'finite encouragement sample has empty arm')
    a.reject(lambda: sample_wald([(0, 0, 1), (1, 0, 2)]), 'finite sample ratio has zero first stage')
    a.reject(lambda: path_design(1), 'degenerate interference assignment')
    a.reject(lambda: check_design([((0, 0, 0), F(1, 2)), ((0, 0, 0), F(1, 2))]), 'duplicate assignment identity')
    a.reject(lambda: ht_law(design, [table[0], table[1]]), 'missing unit exposure potential table')
    a.reject(lambda: bounded_mean(F(6, 5), 8, 0, 10), 'response probability exceeds one')
    a.reject(lambda: bounded_mean(F(4, 5), 11, 0, 10), 'respondent mean violates outcome support')
    a.reject(lambda: bounded_mean(F(4, 5), 8, 10, 0), 'reversed outcome bounds')
    a.reject(lambda: bounded_mean(0, 8, 0, 10), 'invented respondent mean in zero-response arm')
    a.reject(lambda: strict('{"x":1,"x":2}'), 'duplicate JSON member')
    a.reject(lambda: strict('{"x":NaN}'), 'nonfinite JSON constant')
    a.reject(lambda: strict('{"x":1e400}'), 'overflowed JSON decimal')
    a.reject(lambda: Page().feed('HTML'), 'stray manuscript delimiter')
    a.reject(lambda: Page().feed('<section><p></section>'), 'unbalanced reader markup')
    a.eq(set(page.values), set(exact) | set(rounded), 'every printed marker has an independently reconstructed value')
    for key, value in exact.items():
        a.eq(F(page.values[key].strip().replace('−', '-')), value, 'printed exact value ' + key)
    for key, value in rounded.items():
        a.near(float(page.values[key]), value, 'printed six-place value ' + key, 5e-7)
    return len(exact), len(rounded), len(breaks), len(probes)


def check(root=None):
    root = Path(root) if root is not None else Path(__file__).resolve().parents[1]
    raw = (root/HTML).read_text()
    page = Page()
    page.feed(raw)
    page.close()
    a = Audit()
    expected_prompts = ['v12-c06-e'+str(i).zfill(2) for i in range(1, 13)]
    a.eq(page.prompts, expected_prompts, 'twelve exact original prompt IDs')
    a.eq(page.targets, expected_prompts, 'twelve exact paired solution IDs')
    a.eq((page.exercise_count, page.solution_count, page.worked), (12, 12, 7), 'standard reader exercise/solution/worked conventions')
    a.eq((page.h1, page.stack, page.answer, page.marker), (0, [], None, None), 'balanced chapter fragment')
    a.eq(len(page.ids), len(set(page.ids)), 'unique reader IDs')
    a.eq(all(i.startswith('v12-c06-') for i in page.ids), True, 'owned ID namespace')
    a.eq(raw.count('<details class="solutions"'), 1, 'standard disclosed complete solutions')
    for prompt in expected_prompts:
        a.eq(len(page.answers[prompt]) > 550, True, 'substantive full solution ' + prompt)
    a.eq('Teach-back benchmark' in raw and 'Retention answers' in raw, True, 'answered teach-back and retention')
    exact, rounded, roots, cells = calculate(a, page)
    sources, review = strict((root/SOURCES).read_text()), strict((root/REVIEW).read_text())
    source_ids = {'v12-c06-ding-experiments', 'v12-c06-aronow-samii-interference', 'v12-c06-dgk-toolkit'}
    reused = {'v12-c03-imbens-angrist1994'}
    a.eq({s['id'] for s in sources['proposals']}, source_ids, 'three exact scoped primary source proposals')
    a.eq(len(sources['proposals']), 3, 'no extra or duplicate source proposal')
    a.eq({s['id'] for s in sources['reused']}, reused, 'accepted compliance source reuse')
    a.eq(set(page.sources), source_ids | reused, 'all source routes used in the manuscript')
    for source in sources['proposals']:
        a.eq(source['inspection']['reader'], 'root', 'honest primary inspection attribution')
        a.eq(bool(source['inspection']['read_pages']) and bool(source['inspection']['rendered_pages']), True, 'scoped actual primary body/equation evidence')
        a.eq(source['checked'], '2026-10-09', 'recorded preparation date')
    allowed = {'v12-c01.html', 'v12-c03.html', 'v12-c05.html'} | {'sources.html#'+s for s in source_ids | reused}
    for href in page.links:
        a.eq(href in allowed, True, 'flat canonical reader route')
    bindings = review['reviewed_hashes']
    a.eq({row['path'] for row in bindings}, {HTML, SELF, SOURCES}, 'three nonself runtime payload bindings')
    a.eq(len(bindings), 3, 'no duplicate payload bindings')
    for row in bindings:
        payload = (root/row['path']).read_bytes()
        a.eq((len(payload), hashlib.sha256(payload).hexdigest()), (row['bytes'], row['sha256']), 'author final payload ' + row['path'])
    result = dict(chapter='v12-c06', status='passed', working_only=False, worked_cases=7,
                  exercises=12, solutions=12, comparisons=a.comparisons,
                  exact_numeric_anchors=exact, rounded_numeric_anchors=rounded,
                  purposeful_interventions=len(a.interventions), intervention_scopes=a.interventions,
                  executed_rejections=len(a.rejections), rejection_scopes=a.rejections,
                  analytic_inversion_breakpoints=roots, inversion_root_and_open_cell_checks=cells,
                  primary_inspection_scopes_reused=3, accepted_compliance_source_reused=1,
                  nonself_author_bindings=3,
                  limits='Exact bounded finite-law and known-Gaussian calculations; analytic proofs are separately author-reviewed. No finite-population CLT, generic dependent inference, empirical identification, browser QA, human certification or acceptance is implied.')
    strict(json.dumps(result, allow_nan=False))
    return result


if __name__ == '__main__':
    check()
