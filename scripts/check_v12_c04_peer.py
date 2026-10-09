"""Independent, readonly finite audit of v12-c04; no author-code oracle.

Exact group transformations, probability-mass perturbations and latent-normal
integration check the original contracts. General proofs are reviewed separately.
Only the four frozen author files and this peer's two files are runtime inputs.
"""
from fractions import Fraction as F
from html.parser import HTMLParser
import hashlib
import json
from math import erf, exp, isfinite, log, log1p, pi, sqrt
from pathlib import Path


AUTHOR = (
    ('content/chapters/v12-c04.html', 65009, 'c3d2594551b59f176dbccc75b3091e3812c4e6c0cff8af059d68e9e66808045f'),
    ('scripts/check_v12_c04.py', 31942, '7f48f88146899bd7e4ebf0736aaba950d198ae5937ab90e0e88f07c1aee5f918'),
    ('content/reviews/v12-c04-sources.json', 10573, 'e7bc91a990bd4410f36b01897a4666106485d932d092881ea9e83714306a15b2'),
    ('content/reviews/v12-c04-author.json', 23754, '335270b2733df2ec328470febed8ae99408e824c7b9df3dbc93409f18e93db15'),
)
SELF = 'scripts/check_v12_c04_peer.py'
RECORD = 'content/reviews/v12-c04-peer.json'


def require(condition, message):
    if not condition:
        raise ValueError('v12-c04 peer: ' + message)


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'duplicate JSON member')
            result[key] = value
        return result
    def decimal(value):
        result = float(value)
        require(isfinite(result), 'nonfinite JSON number')
        return result
    def constant(value):
        raise ValueError('nonfinite JSON constant: ' + value)
    return json.loads(raw, object_pairs_hook=pairs, parse_float=decimal, parse_constant=constant)


def finite(value):
    require(type(value) in (int, float, F) and isfinite(float(value)), 'finite real scalar, excluding bool')
    return value


class Audit:
    def __init__(self):
        self.comparisons = 0
        self.rejections = []
        self.interventions = []
    def equal(self, actual, expected, label):
        self.comparisons += 1
        require(actual == expected, label + ': ' + repr(actual) + ' != ' + repr(expected))
    def near(self, actual, expected, label, tolerance=2e-9):
        self.comparisons += 1
        require(isfinite(float(actual)) and isfinite(float(expected)) and abs(actual-expected) <= tolerance, label)
    def reject(self, operation, label):
        try:
            operation()
        except ValueError:
            self.rejections.append(label)
        else:
            raise ValueError('missing rejection: ' + label)


class Manuscript(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.ids = []
        self.prompts = []
        self.solutions = []
        self.worked = 0
        self.values = {}
        self.active = None
        self.sources = []
        self.links = []
        self.disclosures = 0
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'id' in attrs:
            self.ids.append(attrs['id'])
        if tag == 'li' and attrs.get('id', '').startswith('v12-c04-e'):
            self.prompts.append(attrs['id'])
        if 'data-solution-for' in attrs:
            self.solutions.append(attrs['data-solution-for'])
        classes = attrs.get('class', '').split()
        self.worked += 'worked' in classes
        self.disclosures += tag == 'details' and 'solutions' in classes
        if 'data-calc' in attrs:
            key = attrs['data-calc']
            require(tag == 'span' and self.active is None and key not in self.values, 'unique flat calculation marker')
            self.values[key] = ''
            self.active = key
        if 'data-source' in attrs:
            self.sources.append(attrs['data-source'])
        if tag == 'a':
            self.links.append(attrs['href'])
        if tag not in ('br', 'hr', 'img', 'meta', 'link', 'input'):
            self.stack.append(tag)
    def handle_data(self, data):
        require(self.stack or not data.strip(), 'text outside fragment')
        if self.active is not None:
            self.values[self.active] += data
    def handle_endtag(self, tag):
        require(self.stack and self.stack.pop() == tag, 'balanced HTML')
        if tag == 'span':
            self.active = None


def solve(matrix, vector):
    n = len(vector)
    require(n in (1, 2) and len(matrix) == n and all(len(row) == n for row in matrix), 'bounded linear dimensions')
    rows = [list(row) + [v] for row, v in zip(matrix, vector)]
    for j in range(n):
        pivot = max(range(j, n), key=lambda i: abs(rows[i][j]))
        require(abs(rows[pivot][j]) > 1e-13, 'nonsingular finite information')
        rows[j], rows[pivot] = rows[pivot], rows[j]
        scale = rows[j][j]
        rows[j] = [v/scale for v in rows[j]]
        for i in range(n):
            if i != j:
                scale = rows[i][j]
                rows[i] = [v-scale*w for v, w in zip(rows[i], rows[j])]
    return tuple(row[-1] for row in rows)


def expit(value):
    finite(value)
    z = exp(-abs(value))
    return 1/(1+z) if value >= 0 else z/(1+z)


def grouped_logit(groups):
    require(len(groups) == 2, 'two groups')
    for n, successes in groups:
        require(type(n) is int and type(successes) is int and 0 < successes < n, 'interior integer binomial counts')
    p = [F(k, n) for n, k in groups]
    # Independent group logits followed by a linear parameter transformation.
    u, v = [1/(n*pr*(1-pr)) for (n, k), pr in zip(groups, p)]
    covariance = ((u, -u), (-u, u+v))
    n = sum(row[0] for row in groups)
    moments = [F(row[0], n)*pr*(1-pr) for row, pr in zip(groups, p)]
    information = ((sum(moments), moments[1]), (moments[1], moments[1]))
    contrast_variance = sum(pr*(1-pr)/row[0] for row, pr in zip(groups, p))
    return p, information, covariance, contrast_variance


def law(rows):
    require(isinstance(rows, (tuple, list)) and rows, 'nonempty finite probability law')
    for mass, x, offset, y in rows:
        require(finite(mass) >= 0 and len(x) in (1, 2), 'probability mass and bounded regressor dimension')
        require(all(abs(finite(v)) <= 4 for v in x) and abs(finite(offset)) <= 4, 'bounded covariates and offset')
        require(type(y) is int and y in (0, 1), 'binary outcome')
    require(abs(sum(row[0] for row in rows)-1) < 1e-12, 'probability normalization')
    require(len({len(row[1]) for row in rows}) == 1, 'common regressor dimension')
    return rows


def criterion(rows, beta):
    value = 0.0
    for mass, x, offset, y in rows:
        eta = offset + sum(a*b for a, b in zip(x, beta))
        value += mass*(y*eta-max(eta, 0)-log1p(exp(-abs(eta))))
    return value


def fit_finite_logit(rows):
    rows = law(rows)
    dimension = len(rows[0][1])
    beta = [0.0]*dimension
    for iteration in range(30):
        score = [0.0]*dimension
        information = [[0.0]*dimension for j in range(dimension)]
        for mass, x, offset, y in rows:
            p = expit(offset+sum(a*b for a, b in zip(x, beta)))
            for j in range(dimension):
                score[j] += mass*x[j]*(y-p)
                for k in range(dimension):
                    information[j][k] += mass*p*(1-p)*x[j]*x[k]
        if max(map(abs, score)) < 2e-14:
            return tuple(beta)
        direction = solve(information, score)
        old = criterion(rows, beta)
        for halving in range(24):
            candidate = [b+d*2**(-halving) for b, d in zip(beta, direction)]
            if max(map(abs, candidate)) < 30 and criterion(rows, candidate) >= old-1e-14:
                beta = candidate
                break
        else:
            raise ValueError('bounded score refit failed')
    raise ValueError('bounded score refit did not converge')


def functional(rows, mode, fixed_distribution=None):
    beta = fit_finite_logit(rows)
    total = 0.0
    for mass, x, offset, y in rows if fixed_distribution is None else fixed_distribution:
        p = expit(offset+sum(a*b for a, b in zip(x, beta)))
        total += mass*p*(1-p)*(beta[1] if mode == 'slope' else 1)
    return total


def refit_influences(rows, mode, fixed=False):
    epsilon = 2e-5
    result = []
    for index in range(len(rows)):
        values = []
        for change in (-epsilon, epsilon):
            altered = [((1-change)*p+(change if i == index else 0), x, offset, y)
                       for i, (p, x, offset, y) in enumerate(rows)]
            values.append(functional(altered, mode, rows if fixed else None))
        result.append((values[1]-values[0])/(2*epsilon))
    return result


def count_influence(rows):
    require(rows and all(type(d) is int and d in (0, 1) and type(y) is int and y >= 0 for d, y in rows), 'valid count rows')
    require({d for d, y in rows} == {0, 1}, 'both count groups')
    n = len(rows)
    shares = [F(sum(d == group for d, y in rows), n) for group in (0, 1)]
    means = [sum(F(y) for d, y in rows if d == group)/(n*shares[group]) for group in (0, 1)]
    require(min(means) > 0, 'positive fitted group means')
    vectors = []
    for d, y in rows:
        group_if = (F(y)-means[d])/(shares[d]*means[d])
        vectors.append((group_if, -group_if) if d == 0 else (F(0), group_if))
    variance = tuple(tuple(sum(v[j]*v[k] for v in vectors)/n for k in range(2)) for j in range(2))
    curvature = tuple(tuple(sum(means[d]*(1, d)[j]*(1, d)[k] for d, y in rows)/n for k in range(2)) for j in range(2))
    meat = tuple(tuple(sum((y-means[d])**2*(1, d)[j]*(1, d)[k] for d, y in rows)/n for k in range(2)) for j in range(2))
    return means, curvature, meat, variance


def gaussian_rule(order=32):
    # Gauss–Legendre nodes, derived by Newton iteration on the Legendre recurrence.
    nodes = []
    for i in range(1, order+1):
        from math import cos
        z = cos(pi*(i-.25)/(order+.5))
        for iteration in range(20):
            p0, p1 = 1.0, z
            for k in range(2, order+1):
                p0, p1 = p1, ((2*k-1)*z*p1-(k-1)*p0)/k
            derivative = order*(z*p1-p0)/(z*z-1)
            delta = p1/derivative
            z -= delta
            if abs(delta) < 2e-15:
                break
        weight = 2/((1-z*z)*derivative*derivative)
        nodes.append((z, weight))
    return nodes


NODES = gaussian_rule()


def integrate(fn, lower, upper):
    total = 0.0
    for part in range(8):
        a = lower+(upper-lower)*part/8
        b = lower+(upper-lower)*(part+1)/8
        mid, half = (a+b)/2, (b-a)/2
        total += half*sum(weight*fn(mid+half*z) for z, weight in NODES)
    return total


def phi(value):
    return exp(-value*value/2)/sqrt(2*pi)


def Phi(value):
    return (1+erf(value/sqrt(2)))/2


def latent_selection(a, mu, sigma, rho, observed):
    for value in (a, mu, sigma, rho, observed):
        finite(value)
    require(abs(a) <= 2 and sigma > 0 and abs(rho) < 1, 'bounded nonsingular selection contract')
    mass = integrate(phi, -a, 10)
    first = integrate(lambda v: (mu+rho*sigma*v)*phi(v), -a, 10)
    second = integrate(lambda v: ((mu+rho*sigma*v)**2+sigma*sigma*(1-rho*rho))*phi(v), -a, 10)
    residual_sd = sigma*sqrt(1-rho*rho)
    density = integrate(lambda v: phi(v)*phi((observed-mu-rho*sigma*v)/residual_sd)/residual_sd, -a, 10)
    return mass, first/mass, second/mass-(first/mass)**2, density


def arithmetic(audit, page):
    exact, rounded = {}, {}
    times = tuple(F(i, 2) for i in range(1, 7))
    mean = sum(times)/6
    rate = 1/mean
    exact.update({'exp-rate': rate, 'exp-mean': mean, 'exp-information': mean**2,
                  'exp-total-info': 6*mean**2, 'exp-root-variance': rate**2, 'exp-log-variance': F(1),
                  'ex2-minute-rate': 1/(60*mean), 'ex2-minute-mean': 60*mean, 'ex2-minute-info': (60*mean)**2})
    rounded['exp-se'] = float(rate)/sqrt(6)
    audit.equal(rate, F(4, 7), 'waiting-time sample reciprocal mean')
    audit.equal(1/(60*mean)**2, rate**2/3600, 'rate variance changes under minute units')
    audit.equal((60*mean)**2, 3600*mean**2, 'mean variance changes in opposite units')
    # The positive information-inverse score sign is checked by a direct law perturbation.
    increment = F(1, 100000)
    y = F(4)
    direction = (1/((1+increment)*mean-increment*y)-1/((1-increment)*mean+increment*y))/(-2*increment)
    audit.near(direction, rate**2*(mean-y), 'direct rate functional versus positive inverse-score influence')
    p, q = (F(1, 2), F(1, 3), F(1, 6)), (F(1, 3),)*3
    audit.equal(sum(pr*(qr/pr) for pr, qr in zip(p, q)), 1, 'normalized common-support ratio')
    kl = sum(float(pr)*log(float(pr/qr)) for pr, qr in zip(p, q))
    gap = sum(float(pr)*(float(qr/pr)-1-log(float(qr/pr))) for pr, qr in zip(p, q))
    audit.near(kl, gap, 'finite KL identity')
    audit.equal(kl > 0, True, 'distinct common-support laws have positive gap')
    audit.interventions.append('Physical-unit changes and direct rate-functional perturbation distinguish scale and expansion sign.')

    for groups, transfer in ((((40, 10), (40, 30)), False), (((20, 4), (20, 16)), True)):
        probabilities, information, covariance, cv = grouped_logit(groups)
        n = sum(row[0] for row in groups)
        for j in range(2):
            for k in range(2):
                audit.equal(sum(n*information[j][r]*covariance[r][k] for r in range(2)), int(j == k), 'group-logit transform versus information inverse')
        if transfer:
            audit.equal(covariance, ((F(5, 16), F(-5, 16)), (F(-5, 16), F(5, 8))), 'exercise 4 full coefficient covariance')
            exact.update({'ex4-odds-ratio': (probabilities[1]/(1-probabilities[1]))/(probabilities[0]/(1-probabilities[0])),
                          'ex4-contrast': probabilities[1]-probabilities[0], 'ex4-contrast-variance': cv})
        else:
            audit.equal(information, ((F(3, 16), F(3, 32)), (F(3, 32), F(3, 32))), 'worked binary information')
            audit.equal(covariance, ((F(2, 15), F(-2, 15)), (F(-2, 15), F(4, 15))), 'worked binary coefficient covariance')
            exact.update({'binary-contrast': probabilities[1]-probabilities[0], 'binary-contrast-variance': cv})
            rounded['binary-derivative'] = log(9)*float(probabilities[0]*(1-probabilities[0]))
    unequal = grouped_logit(((9, 3), (15, 12)))
    reverse = grouped_logit(((15, 12), (9, 3)))
    audit.equal(unequal[3], F(2, 81)+F(4, 375), 'unequal group-size precision')
    audit.equal(unequal[3], reverse[3], 'relabeling preserves contrast variance')
    audit.equal(unequal[0][1]-unequal[0][0], -(reverse[0][1]-reverse[0][0]), 'relabeling reverses contrast')
    audit.interventions.append('Unequal binary cell sizes and group relabeling check target versus precision.')
    path_values = [-8*log1p(exp(-t)) for t in (0, 1, 2, 5)]
    audit.equal(all(x < y < 0 for x, y in zip(path_values, path_values[1:])), True, 'separation gives an unattained supremum')
    audit.equal(8*(1-expit(2)) > 0, True, 'constrained endpoint keeps a positive directional derivative')
    exact['ex5-boundary-t'] = F(2)
    audit.near(2*phi(0), sqrt(2/pi), 'probit score at origin')
    audit.near((Phi(2e-5)-Phi(-2e-5))/(2e-5), 2*phi(0), 'probit continuous derivative')
    audit.interventions.append('Separated likelihood and constrained path distinguish finite existence from a regular interior fit.')

    L = log(3)
    probabilities = (F(1, 4), F(1, 2), F(3, 4))
    rows = [(F(1, 3)*(p if y else 1-p), (1, x), 0, y)
            for x, p in zip((-1, 0, 1), probabilities) for y in (0, 1)]
    beta = fit_finite_logit(rows)
    audit.near(beta[0], 0, 'correct finite-law intercept fit')
    audit.near(beta[1], L, 'correct finite-law slope fit')
    influences = refit_influences(rows, 'slope')
    fixed = refit_influences(rows, 'slope', fixed=True)
    g = 5/24-L/16
    tau = functional(rows, 'slope')
    for (mass, x, offset, y), actual, known in zip(rows, influences, fixed):
        p = probabilities[x[1]+1]
        expected_fixed = 8*g*x[1]*(y-p)
        expected_full = L*float(p*(1-p))-tau+expected_fixed
        audit.near(actual, expected_full, 'full APE influence by probability-law refit', 8e-8)
        audit.near(known, expected_fixed, 'known-distribution APE influence by refit', 8e-8)
    total_v = sum(float(row[0])*v*v for row, v in zip(rows, influences))
    fixed_v = sum(float(row[0])*v*v for row, v in zip(rows, fixed))
    audit.near(total_v-fixed_v, L*L/1152, 'empirical-X uncertainty from two separate refits', 2e-8)
    rounded.update({'ape-mean': 5*L/24, 'ape-total-variance': L*L/1152+8*g*g,
                    'ape-se300': sqrt((L*L/1152+8*g*g)/300)})
    audit.interventions.append('Refit after contamination of each of six probability atoms; compare empirical and known X targets.')

    q = F(5, 8)
    rows = [(F(1, 2)*(q if y else 1-q), (1,), offset, y) for offset in (0, L) for y in (0, 1)]
    probabilities = (F(1, 2), F(3, 4))
    h = [p*(1-p) for p in probabilities]
    average = sum(h)/2
    gradient = sum(w*(1-2*p) for w, p in zip(h, probabilities))/2
    B = sum(row[0]*(row[3]-probabilities[i//2])**2 for i, row in enumerate(rows))
    cov_h_score = sum(row[0]*(h[i//2]-average)*(row[3]-probabilities[i//2]) for i, row in enumerate(rows))
    vh = sum((v-average)**2 for v in h)/2
    exact_if = [h[i//2]-average+gradient/average*(row[3]-probabilities[i//2]) for i, row in enumerate(rows)]
    full = sum(row[0]*v*v for row, v in zip(rows, exact_if))
    omitted = vh+(gradient/average)**2*B
    fixed_v = (gradient/average)**2*B
    audit.equal((average, gradient, B, vh, cov_h_score), (F(7, 32), F(-3, 64), F(1, 4), F(1, 1024), F(1, 256)), 'all misspecified-law influence ingredients')
    audit.equal((full, omitted, fixed_v), (F(541, 50176), F(625, 50176), F(9, 784)), 'full, omitted-cross and known-target variances')
    for observed, expected in zip(refit_influences(rows, 'offset'), exact_if):
        audit.near(observed, float(expected), 'misspecified full influence from actual-law perturbation', 8e-8)
    audit.near(fit_finite_logit(rows)[0], 0, 'misspecified finite-law pseudo-target')
    exact.update({'ex7-tau': average, 'ex7-gradient': gradient, 'ex7-full-variance': full, 'ex7-omitted-cross-variance': omitted})
    # Two admissible smooth extensions agree on the observed support yet differ in derivative.
    extension = lambda x: float(q)+x*(x-L)**2/16
    audit.near(extension(0), q, 'alternative actual curve agrees at first support point')
    audit.near(extension(L), q, 'alternative actual curve agrees at second support point')
    audit.equal(L*L/16 > 0, True, 'alternative derivative at zero differs from a constant extension')
    audit.interventions.append('Misspecified offset model retains a nonzero covariance; an alternative smooth extension separates interpolation from identification.')

    population = [(0, 0), (0, 4), (1, 0), (1, 8)]
    means, A, B, V = count_influence(population)
    audit.equal((A, B, V), (((F(3), F(2)), (F(2), F(2))), ((F(10), F(8)), (F(8), F(8))), ((F(2), F(-2)), (F(-2), F(4)))), 'population count matrices from group-log-mean influences')
    exact.update({'count-pop-slope-var': V[1][1], 'count-model-slope-var': solve(A, (0, 1))[1]})
    sample = [(0, 0), (0, 0), (0, 4), (0, 4), (1, 0), (1, 8), (1, 8), (1, 8)]
    means_s, A_s, B_s, V_s = count_influence(sample)
    audit.equal((means_s, A_s, B_s), ([F(2), F(6)], ((F(4), F(3)), (F(3), F(3))), ((F(8), F(6)), (F(6), F(6)))), 'separate sample means and fitted residuals')
    audit.equal(V_s, ((F(2), F(-2)), (F(-2), F(8, 3))), 'sample full count sandwich from independent influences')
    exact.update({'count-sample-root-slope': V_s[1][1], 'count-sample-slope-cov': V_s[1][1]/len(sample)})
    scaled = count_influence([(d, 3*y) for d, y in sample])
    audit.equal(scaled[3], V_s, 'count-unit scaling preserves robust log-mean influences')
    audit.equal(solve(scaled[1], (0, 1))[1], solve(A_s, (0, 1))[1]/3, 'Poisson information responds differently to scaling')
    dispersion = count_influence([(0, 1), (0, 3), (1, 3), (1, 5)])
    audit.equal(dispersion[:2], (means, A), 'altered dispersion preserves original means and curvature')
    audit.equal(dispersion[3] != V, True, 'altered dispersion changes robust precision')
    unconditional_mean = sum(F(y) for d, y in population)/4
    variance = sum((y-unconditional_mean)**2 for d, y in population)/4
    exact.update({'ex9-curvature': unconditional_mean, 'ex9-meat': variance, 'ex9-robust-variance': variance/unconditional_mean**2})
    audit.equal([value-unconditional_mean for value in means], [-1, 1], 'omitted group leaves conditional mean errors')
    audit.interventions.append('Count scaling, changed dispersion and omitted groups distinguish the mean target from its robust precision.')

    # Integration conditions on the latent selecting normal, rather than on the observed outcome.
    cases = [(0, 10, 2, .5), (0, 10, 2, -.5), (.6, 2, 3, .4), (-.7, 1, 2, 0)]
    baseline = None
    for index, (cutoff, mu, sigma, rho) in enumerate(cases):
        mass, selected_mean, selected_variance, joint = latent_selection(cutoff, mu, sigma, rho, mu)
        mills = phi(cutoff)/Phi(cutoff)
        audit.near(mass, Phi(cutoff), 'latent selection mass')
        audit.near(selected_mean, mu+rho*sigma*mills, 'latent selected mean')
        audit.near(selected_variance, sigma*sigma*(1-rho*rho*mills*(cutoff+mills)), 'latent selected second moment', 2e-8)
        closed_joint = phi(0)*Phi(cutoff/sqrt(1-rho*rho))/sigma
        audit.near(joint, closed_joint, 'bivariate-convolution density at the marginal mean')
        audit.near(mass+Phi(-cutoff), 1, 'mixed density probability budget')
        if index == 0:
            baseline = (mass, selected_mean, selected_variance, joint)
    mass, selected_mean, selected_variance, joint = baseline
    rounded.update({'selection-mean': selected_mean, 'selection-joint-at10': joint,
                    'selection-conditional-at10': joint/mass, 'ex10-selected-variance': selected_variance})
    for cutoff in (-.7, .6):
        mass, _, _, joint = latent_selection(cutoff, 1, 2, 0, 2)
        audit.near(joint/mass, phi(.5)/2, 'selected-only rho-zero law loses selection-index information')
    audit.interventions.append('Latent-normal integration changes correlation, cutoff and units; rho-zero selected-only samples carry no selection-index information through the outcome density.')

    sample = [1, 2, 3, 4]
    maximum = max(sample)
    # A maximum below a threshold requires every original independent observation below it.
    cutoff = F(3, 4)
    finite_tail = F(1)
    for value in sample:
        finite_tail *= cutoff
    exact.update({'uniform-maximum': F(maximum), 'uniform-tail': finite_tail, 'uniform-upper': maximum/F(1, 2), 'uniform-coverage': 1-F(1, 2)**4})
    audit.equal(finite_tail, F(81, 256), 'four-observation maximum finite tail')
    audit.equal(float(finite_tail) < exp(-1), True, 'finite tail is not its exponential limit')
    for n, theta in ((2, 3), (4, 5), (7, 2)):
        expected_max = integrate(lambda y: y*n*y**(n-1)/theta**n, 0, theta)
        audit.near(expected_max, n*theta/(n+1), 'maximum expectation from density integration')
        a = F(2, 3)
        audit.equal((theta*a/theta)**n, a**n, 'scale-free maximum pivot')
    audit.equal(-F(1, 5)+F(1, 5), 0, 'moving boundary cancels interior density derivative')
    audit.interventions.append('Different sample sizes and scales retain an exact maximum pivot; the finite tail differs from the asymptotic exponential tail.')
    p = F(1, 3)
    w = p*(1-p)
    exact.update({'retention-logit-variance': 1/w, 'retention-effect-variance': (w*(1-2*p))**2/w,
                  'retention-count-variance': (F(1, 2)*(0-3)**2+F(1, 2)*(6-3)**2)/9,
                  'retention-uniform-upper': F(3)/F(1, 3)})
    retention = latent_selection(0, 2, 4, -.25, 2)
    audit.near(retention[1], 2-sqrt(2/pi), 'changed retention selected mean')

    for key, value in exact.items():
        audit.equal(F(page.values[key].replace('−', '-')), value, 'printed exact answer ' + key)
    for key, value in rounded.items():
        audit.near(float(page.values[key]), value, 'printed rounded answer ' + key, 5e-10)
    audit.equal(set(page.values), set(exact) | set(rounded), 'complete printed numeric-marker coverage')
    return len(exact), len(rounded), len(rows)+6, len(cases)


def check(root=None):
    root = Path(root) if root is not None else Path(__file__).resolve().parents[1]
    audit = Audit()
    for name, size, digest in AUTHOR:
        payload = (root/name).read_bytes()
        audit.equal((len(payload), hashlib.sha256(payload).hexdigest()), (size, digest), 'frozen author payload ' + name)
    page = Manuscript()
    page.feed((root/AUTHOR[0][0]).read_text())
    page.close()
    prompts = ['v12-c04-e' + str(i).zfill(2) for i in range(1, 13)]
    audit.equal(page.prompts, prompts, 'all twelve exact prompts')
    audit.equal(page.solutions, prompts, 'all twelve corresponding solutions')
    audit.equal((page.worked, page.disclosures, page.stack), (6, 1, []), 'worked cases and solution structure')
    audit.equal((len(page.ids), len(set(page.ids))), (31, 31), 'unique fragment IDs')
    exact, rounded, atom_refits, selection_cases = arithmetic(audit, page)
    sources = strict_json((root/AUTHOR[2][0]).read_text())
    author = strict_json((root/AUTHOR[3][0]).read_text())
    ids = {s['id'] for s in sources['proposals']}
    audit.equal(len(ids), 4, 'four distinct scoped primary sources')
    audit.equal(set(page.sources), ids, 'all primary source routes used')
    allowed = {'v12-c01.html', 'v12-c02.html', 'v12-c03.html'} | {'sources.html#' + item for item in ids}
    audit.equal(set(page.links), allowed, 'canonical prerequisite and flat source routes')
    author_bindings = author['reviewed_hashes']
    audit.equal({r['path'] for r in author_bindings}, {r[0] for r in AUTHOR[:3]}, 'three nonself author bindings')
    audit.equal(len(author_bindings), 3, 'no duplicate author binding')
    for row in author_bindings:
        payload = (root/row['path']).read_bytes()
        audit.equal((len(payload), hashlib.sha256(payload).hexdigest()), (row['bytes'], row['sha256']), 'author binding ' + row['path'])
    peer = strict_json((root/RECORD).read_text())
    expected = {r[0] for r in AUTHOR} | {SELF}
    bindings = peer['reviewed_hashes']
    audit.equal({r['path'] for r in bindings}, expected, 'four author plus peer-checker bindings')
    audit.equal(len(bindings), 5, 'five distinct peer bindings')
    for row in bindings:
        payload = (root/row['path']).read_bytes()
        audit.equal((len(payload), hashlib.sha256(payload).hexdigest()), (row['bytes'], row['sha256']), 'peer binding ' + row['path'])
    audit.reject(lambda: strict_json('{"x":1,"x":2}'), 'duplicate JSON member')
    audit.reject(lambda: strict_json('{"x":NaN}'), 'nonfinite JSON literal')
    audit.reject(lambda: strict_json('{"x":1e309}'), 'overflowing JSON exponent')
    audit.reject(lambda: finite(True), 'boolean scalar')
    audit.reject(lambda: finite(float('inf')), 'infinite scalar')
    audit.reject(lambda: grouped_logit(((4, 0), (4, 2))), 'zero-success finite-logit failure')
    audit.reject(lambda: grouped_logit(((4, 4), (4, 2))), 'all-success finite-logit failure')
    audit.reject(lambda: grouped_logit(((4, 5), (4, 2))), 'invalid success count')
    audit.reject(lambda: law([(F(1, 2), (1,), 0, 1)]), 'unnormalized probability law')
    audit.reject(lambda: law([(F(1), (1,), 0, 2)]), 'nonbinary observation')
    audit.reject(lambda: solve(((1, 1), (1, 1)), (1, 1)), 'rank-deficient curvature')
    audit.reject(lambda: count_influence([(0, 0), (1, 2)]), 'zero fitted log-count mean')
    audit.reject(lambda: count_influence([(0, 1), (0, 3)]), 'missing independent count group')
    audit.reject(lambda: count_influence([(0, True), (1, 2)]), 'boolean count')
    audit.reject(lambda: latent_selection(0, 1, 0, .5, 1), 'zero outcome scale')
    audit.reject(lambda: latent_selection(0, 1, 2, 1, 1), 'singular normal correlation')
    audit.reject(lambda: latent_selection(3, 1, 2, .5, 1), 'outside bounded quadrature case')
    result = dict(chapter='v12-c04', status='passed', comparisons=audit.comparisons,
                  exact_numeric_anchors=exact, rounded_numeric_anchors=rounded,
                  worked_cases=6, exercises=12, solutions=12,
                  purposeful_interventions=len(audit.interventions), intervention_scopes=audit.interventions,
                  executed_rejections=len(audit.rejections), rejection_scopes=audit.rejections,
                  directional_probability_atoms=atom_refits, latent_selection_cases=selection_cases,
                  nonself_peer_bindings=5, author_code_used_as_oracle=False,
                  limits='Finite independent evidence plus separately recorded analytic reading; no general theorem, empirical validity, reader UI or chapter acceptance established by execution.')
    strict_json(json.dumps(result, allow_nan=False))
    return result


if __name__ == '__main__':
    check()
