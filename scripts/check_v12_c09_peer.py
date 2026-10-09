"""Independent, read-only finite oracles for the frozen C09 chapter.

Gaussian polynomial moments, triangular impulse sums and innovation loadings
are computed here. The author checker is never imported or used as an oracle.
"""
from fractions import Fraction as R
from html.parser import HTMLParser
from pathlib import Path
import hashlib
import json
import math
import re


AUTHOR = (
    ('content/chapters/v12-c09.html', 56629, 'c809929afde736f4dc1327bcb1431d5e1b4232dc0a4b7fdce711ab9391315866'),
    ('scripts/check_v12_c09.py', 33013, '80eeded6d3ede65c8a69edf064c82bb3c2d556c7c12df2a3c482750fa9644270'),
    ('content/reviews/v12-c09-sources.json', 27039, 'd8bbf09bcda9d10f4d421af4b59affadf95947267d1b046f61d89209868a8cfe'),
    ('content/reviews/v12-c09-author.json', 39335, 'a7764ad9c79f85b2c3cc4a8359c5dfcc017f29eb6e9fa108c3777bae9c59604d'),
)
SELF = 'scripts/check_v12_c09_peer.py'
RECORD = 'content/reviews/v12-c09-peer.json'


def need(test, message):
    if not test:
        raise ValueError(message)


def exact(x):
    need(type(x) is int or type(x) is R, 'an exact nonboolean number is required')
    x = R(x)
    need(abs(x) <= 10**6, 'outside bounded arithmetic domain')
    return x


def count(n, lo=1, hi=10):
    need(type(n) is int and lo <= n <= hi, 'unsupported integer dimension')
    return n


def strict(text):
    def pairs(items):
        out = {}
        for k, v in items:
            need(k not in out, 'duplicate JSON member')
            out[k] = v
        return out
    def invalid(x):
        raise ValueError('nonfinite JSON number: '+x)
    def number(x):
        y = float(x)
        need(math.isfinite(y), 'overflowed JSON number')
        return y
    return json.loads(text, object_pairs_hook=pairs,
                      parse_constant=invalid, parse_float=number)


class Polynomial:
    """Small exact polynomials in independent centered Gaussian coordinates."""
    def __init__(self, n, terms):
        self.n = count(n)
        need(type(terms) is dict and len(terms) <= 512, 'bounded polynomial dictionary')
        self.terms = {}
        for powers, coefficient in terms.items():
            need(type(powers) is tuple and len(powers) == n, 'monomial dimension')
            need(all(type(j) is int and 0 <= j <= 12 for j in powers)
                 and sum(powers) <= 12, 'bounded nonnegative polynomial degree')
            v = exact(coefficient)
            if v:
                self.terms[powers] = v

    @classmethod
    def constant(cls, n, value):
        return cls(n, {(0,)*n: value})

    @classmethod
    def variable(cls, n, j):
        count(n)
        need(type(j) is int and 0 <= j < n, 'coordinate index')
        powers = [0]*n
        powers[j] = 1
        return cls(n, {tuple(powers): R(1)})

    def __add__(self, other):
        if not isinstance(other, Polynomial):
            other = Polynomial.constant(self.n, other)
        need(other.n == self.n, 'polynomial dimensions differ')
        terms = dict(self.terms)
        for k, v in other.terms.items():
            terms[k] = terms.get(k, R())+v
        return Polynomial(self.n, terms)

    __radd__ = __add__

    def __mul__(self, other):
        if not isinstance(other, Polynomial):
            other = Polynomial.constant(self.n, other)
        need(other.n == self.n, 'polynomial dimensions differ')
        terms = {}
        for a, x in self.terms.items():
            for b, y in other.terms.items():
                key = tuple(i+j for i, j in zip(a, b))
                terms[key] = terms.get(key, R())+x*y
        return Polynomial(self.n, terms)

    __rmul__ = __mul__

    def mean(self, variances):
        need(type(variances) in (list, tuple) and len(variances) == self.n,
             'Gaussian variance dimension')
        variances = tuple(exact(v) for v in variances)
        need(all(v > 0 for v in variances), 'positive Gaussian variances')
        total = R()
        for powers, coefficient in self.terms.items():
            term = coefficient
            for power, variance in zip(powers, variances):
                if power % 2:
                    term = R()
                    break
                # Integration by parts gives E Z^(2r)=(2r-1)!! variance^r.
                for k in range(1, power, 2):
                    term *= k
                term *= variance**(power//2)
            total += term
        return total

    def evaluate(self, values):
        need(type(values) in (list, tuple) and len(values) == self.n,
             'polynomial evaluation dimension')
        values = tuple(exact(v) for v in values)
        return sum((c*math.prod(x**j for x, j in zip(values, p))
                    for p, c in self.terms.items()), R())


def variance(poly, scales):
    return (poly*poly).mean(scales)-poly.mean(scales)**2


def covariance(left, right, scales):
    return (left*right).mean(scales)-left.mean(scales)*right.mean(scales)


def filter_coefficients(phi, theta, n, inverse=False):
    phi, theta = exact(phi), exact(theta)
    count(n)
    need(abs(phi) < 1, 'causal stable filter required')
    need(type(inverse) is bool, 'explicit inversion flag')
    if inverse:
        need(abs(theta) < 1, 'past-observation recovery requires invertibility')
        multiplier, forcing = -theta, -phi
    else:
        multiplier, forcing = phi, theta
    out = [R(1)]
    for j in range(1, n):
        out.append(multiplier*out[-1]+(forcing if j == 1 else 0))
    return out


def future_arma(phi, theta, current_x, current_e, n):
    phi, theta = exact(phi), exact(theta)
    need(abs(phi) < 1, 'fixed stable ARMA law')
    count(n, 1, 6)
    x = Polynomial.constant(n, exact(current_x))
    old_e = Polynomial.constant(n, exact(current_e))
    paths = []
    for j in range(n):
        e = Polynomial.variable(n, j)
        x = phi*x+e+theta*old_e
        paths.append(x)
        old_e = e
    return paths


def geometric_inner(left, right):
    """Inner product of finite sums of decaying exponential sequences."""
    need(type(left) is list and type(right) is list
         and 1 <= len(left) <= 3 and 1 <= len(right) <= 3, 'bounded exponential sums')
    result = R()
    for a, c in left:
        for b, d in right:
            a, b, c, d = map(exact, (a, b, c, d))
            need(abs(a) < 1 and abs(b) < 1, 'summable exponential sequence')
            result += c*d/(1-a*b)
    return result


def matrix(values):
    need(type(values) in (tuple, list) and 1 <= len(values) <= 8, 'bounded matrix rows')
    need(all(type(row) in (tuple, list) for row in values), 'matrix row sequence')
    width = len(values[0])
    count(width, 1, 8)
    need(all(len(row) == width for row in values), 'rectangular matrix')
    return tuple(tuple(exact(x) for x in row) for row in values)


def multiply(left, right):
    left, right = matrix(left), matrix(right)
    need(len(left[0]) == len(right), 'matrix multiplication dimensions')
    return tuple(tuple(sum((left[i][k]*right[k][j] for k in range(len(right))), R())
                       for j in range(len(right[0]))) for i in range(len(left)))


def trans(a):
    return tuple(zip(*matrix(a)))


def stable_polynomials(phi, sigma2, n):
    phi, sigma2 = exact(phi), exact(sigma2)
    need(abs(phi) < 1 and sigma2 > 0, 'fixed stationary Gaussian AR law')
    count(n, 1, 6)
    x = Polynomial.variable(n+1, 0)
    score = Polynomial.constant(n+1, 0)
    denominator = Polynomial.constant(n+1, 0)
    for j in range(1, n+1):
        e = Polynomial.variable(n+1, j)
        score = score+x*e
        denominator = denominator+x*x
        x = phi*x+e
    return score, denominator, [sigma2/(1-phi*phi)]+[sigma2]*n


def regression(increments):
    need(type(increments) in (tuple, list), 'increment sequence')
    count(len(increments), 2, 8)
    e = tuple(exact(x) for x in increments)
    x = [R()]
    for value in e:
        x.append(x[-1]+value)
    lag, current = x[:-1], x[1:]
    denominator = sum(t*t for t in lag)
    need(denominator > 0, 'positive lagged design')
    slope = sum(a*b for a, b in zip(lag, current))/denominator
    residuals = [b-slope*a for a, b in zip(lag, current)]
    rss = sum(t*t for t in residuals)
    need(rss > 0, 'positive residual variance for studentization')
    return x, denominator, slope, residuals, rss


def garch_moments(omega, alpha, beta, kappa):
    omega, alpha, beta, kappa = map(exact, (omega, alpha, beta, kappa))
    need(omega > 0 and alpha >= 0 and beta >= 0 and kappa >= 1,
         'positive intercept, nonnegative coefficients and possible fourth moment')
    rho = alpha+beta
    multiplier_variance = alpha*alpha*(kappa-1)
    a2 = rho*rho+multiplier_variance
    if rho >= 1:
        return rho, a2, None, None
    mean_h = omega/(1-rho)
    if a2 >= 1:
        return rho, a2, mean_h, None
    # Center the random-affine recursion instead of solving its raw moment equation.
    var_h = multiplier_variance*mean_h*mean_h/(1-a2)
    return rho, a2, mean_h, mean_h*mean_h+var_h


def overlapping(n, horizon=2, offset=0, coordinates=None):
    count(n, 1, 6)
    count(horizon, 1, 3)
    count(offset, 0, 8)
    dimension = offset+n+horizon-1 if coordinates is None else count(coordinates)
    count(dimension)
    need(offset+n+horizon-1 <= dimension, 'future-innovation index support')
    errors = []
    for origin in range(offset, offset+n):
        errors.append(sum((Polynomial.variable(dimension, j)
                           for j in range(origin, origin+horizon)),
                          Polynomial.constant(dimension, 0)))
    return errors


def normal_text(text):
    return re.sub(r'\s+', '', text).replace('−', '-')


class Fragment(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.frames = []
        self.ids = []
        self.links = []
        self.citations = []
        self.worked = []
        self.prompts = {}
        self.answers = {}
        self.text = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if a.get('id'):
            self.ids.append(a['id'])
        if a.get('href'):
            self.links.append(a['href'])
        if a.get('data-source'):
            self.citations.append(a['data-source'])
        key = a.get('data-solution-for')
        kind = 'answer' if key else None
        if tag == 'li' and a.get('id', '').startswith('v12-c09-e'):
            kind, key = 'prompt', a['id']
        if 'worked' in a.get('class', '').split():
            kind, key = 'worked', str(len(self.worked)+1)
        if tag not in ('br', 'hr', 'img', 'meta', 'link', 'input'):
            self.frames.append((tag, kind, key, []))

    def handle_data(self, data):
        self.text.append(data)
        for _, kind, _, values in self.frames:
            if kind:
                values.append(data)

    def handle_endtag(self, tag):
        need(self.frames and self.frames[-1][0] == tag, 'unbalanced fragment '+tag)
        _, kind, key, values = self.frames.pop()
        if kind == 'worked':
            self.worked.append(' '.join(values))
        elif kind:
            destination = self.prompts if kind == 'prompt' else self.answers
            need(key not in destination, 'duplicate prompt or answer')
            destination[key] = ' '.join(values)


class Audit:
    def __init__(self):
        self.comparisons = 0
        self.anchors = 0
        self.rejections = []
        self.interventions = []

    def eq(self, actual, expected, label):
        self.comparisons += 1
        need(actual == expected, label+': '+repr(actual)+' != '+repr(expected))

    def near(self, actual, expected, label, tolerance=2e-12):
        self.comparisons += 1
        need(math.isfinite(actual) and math.isclose(actual, expected,
             rel_tol=tolerance, abs_tol=tolerance), label)

    def anchor(self, fragment, exercise, *values):
        text = normal_text(fragment.answers['v12-c09-e'+str(exercise)])
        for value in values:
            self.eq(normal_text(str(value)) in text, True, 'computed answer anchor '+str(exercise)+' '+str(value))
            self.anchors += 1

    def reject(self, fn, label):
        self.comparisons += 1
        try:
            fn()
        except ValueError:
            self.rejections.append(label)
        else:
            raise ValueError('invalid input accepted: '+label)


def numerical(a, page):
    # Case 1: advance the actual law as a polynomial in future shocks.
    phi, theta, s2 = R(1, 2), R(1, 3), R(9, 4)
    future = future_arma(phi, theta, 2, -R(3, 2), 3)
    means = [p.mean([s2]*3) for p in future]
    variances = [variance(p, [s2]*3) for p in future]
    a.eq(means, [R(1, 2), R(1, 4), R(1, 8)], 'recursive ARMA means')
    a.eq(variances, [R(9, 4), R(61, 16), R(269, 64)], 'future-shock forecast variances')
    # State covariance of (X,epsilon): Cov(X,epsilon)=sigma2.
    gamma0 = s2*(1+theta*theta+2*phi*theta)/(1-phi*phi)
    gamma1 = phi*gamma0+theta*s2
    a.eq((gamma0, gamma1), (R(13, 3), R(35, 12)), 'stationary state covariance')
    coeff = filter_coefficients(phi, theta, 7)
    inverse = filter_coefficients(phi, theta, 7, True)
    a.eq(coeff[:3], [1, R(5, 6), R(5, 12)], 'polynomial division coefficients')
    for lag in range(7):
        a.eq(sum(coeff[j]*inverse[lag-j] for j in range(lag+1)), R(lag == 0), 'inverse composition')
    a.eq(filter_coefficients(phi, -phi, 5), [1, 0, 0, 0, 0], 'cancelled root')
    a.eq((-theta)**3, -R(1, 27), 'nonzero three-date recovery-initialization error')
    a.interventions.append('Cancellation and finite recovery initialization are distinct from infinite-past recovery.')
    # Triple repeated root, including a negative root parameter: direct convolution.
    t = -R(1, 3)
    triple = [sum(t**i*t**j*t**(k-i-j) for i in range(k+1)
                  for j in range(k-i+1)) for k in range(6)]
    a.eq(triple, [R(math.comb(k+2, 2))*t**k for k in range(6)], 'repeated inverse-factor count')
    covariances = []
    for ma, noise in ((R(2), R(1)), (R(1, 2), R(4))):
        row = [noise*(1+ma*ma), noise*ma, R(0)]
        covariances.append(row)
    a.eq(covariances, [[5, 2, 0], [5, 2, 0]], 'Gaussian MA observational covariance equality')
    a.anchor(page, 1, 'Cauchy', 'binom', 'White noise', 'absolute', 'conditional means')
    a.anchor(page, 2, gamma0, gamma1, *variances, '5,2', 'θ=−φ')

    # Case 2: closed triangular powers; no Lyapunov linear-system oracle.
    p, r, d = R(1, 2), R(1, 3), R(3, 2)
    row1 = [[(p, 1+d), (r, -d)], [(p, d), (r, -d)]]
    row2 = [[(r, R(1))], [(r, R(1))]]
    rows = [row1, row2]
    stationary = tuple(tuple(sum(geometric_inner(rows[i][k], rows[j][k])
                                 for k in range(2)) for j in range(2)) for i in range(2))
    a.eq(stationary, ((R(479, 240), R(57, 40)), (R(57, 40), R(9, 4))), 'infinite impulse inner products')
    A = ((p, R(1, 4)), (0, r))
    B = ((1, 0), (1, 1))
    Q = ((R(3, 5), -R(4, 5)), (R(4, 5), R(3, 5)))
    A2 = ((p*p, d*(p*p-r*r)), (R(0), r*r))
    a.eq(multiply(A, A), A2, 'closed triangular power')
    a.eq(sum(x*x for row in A for x in row), R(61, 144), 'Frobenius contraction')
    mean2 = multiply(A2, ((2,), (-1,)))
    a.eq(mean2, ((R(7, 24),), (-R(1, 9),)), 'two-step mean')
    AB = multiply(A, B)
    horizon_loadings = tuple(tuple(B[i])+tuple(AB[i]) for i in range(2))
    cov2 = multiply(horizon_loadings, trans(horizon_loadings))
    a.eq(cov2, ((R(13, 8), R(4, 3)), (R(4, 3), R(20, 9))), 'independent two-date shock loadings')
    rotated = multiply(B, Q)
    a.eq(multiply(Q, trans(Q)), ((1, 0), (0, 1)), 'orthogonal rotation')
    a.eq(multiply(B, trans(B)), multiply(rotated, trans(rotated)), 'preserved Gaussian innovation law')
    a.eq(tuple(row[0] for row in rotated), (R(3, 5), R(7, 5)), 'rotated named impact')
    responses = [multiply(A, tuple((row[0],) for row in f)) for f in (B, rotated)]
    a.eq(responses, [((R(3, 4),), (R(1, 3),)), ((R(13, 20),), (R(7, 15),))], 'distinct named lag-one responses')
    a.interventions.append('Orthogonal shock rotation preserves the observed law and changes named responses.')
    a.anchor(page, 3, '61/144', '479/240', '57/40', '9/4', '7/24,−1/9', '13/8', '4/3', '20/9', '13/20,7/15')

    # Case 3: direct Gaussian polynomial expectations instead of a trace oracle.
    for ar, n in ((R(1, 2), 4), (-R(1, 2), 4), (R(0), 3)):
        score, den, scales = stable_polynomials(ar, R(3, 4), n)
        a.eq(score.mean(scales), 0, 'zero unconditional score mean')
        a.eq(variance(score, scales), n*scales[0]*R(3, 4), 'score variance by independent Gaussian moments')
        a.eq(den.mean(scales)/n, scales[0], 'stationary denominator mean')
        den_variance = variance(den, scales)/n**2
        bound = 2*scales[0]**2/n*(1+2*ar*ar/(1-ar*ar))
        a.eq(den_variance <= bound, True, 'denominator finite bound')
        # Every quadratic cross coefficient is twice the symmetric raw matrix entry.
        raw = [[R() for _ in scales] for _ in scales]
        for powers, c in score.terms.items():
            indices = [i for i, k in enumerate(powers) if k]
            a.eq((sum(powers), len(indices)), (2, 2), 'off-diagonal score monomial')
            i, j = indices
            raw[i][j] = raw[j][i] = c/2
        maxrow = max(sum(abs(float(raw[i][j]))*math.sqrt(float(scales[i]*scales[j]))
                         for j in range(n+1)) for i in range(n+1))
        c = max(math.sqrt(float(R(3, 4)*scales[0]))/(2*(1-abs(float(ar)))),
                math.sqrt(float(R(3, 4)*scales[0]))/2+.75/(1-abs(float(ar))))
        a.eq(maxrow <= c+1e-14, True, 'standardized uniform row bound')
    z = Polynomial.variable(1, 0)
    square = z*z
    a.eq([(z*z).mean([1]), (square*square).mean([1]), (square*square*square).mean([1])],
         [1, 3, 15], 'Gaussian even moments by integration-by-parts recurrence')
    a.eq(((square+1)*(square+1)*(square+1)).mean([1]), 28, 'absolute third-moment envelope')
    a.eq((square+(-1)).mean([1]), 0, 'centered chi-square mean')
    # Construct the smooth cutoff by integrating the nonnegative beta(4,4) density.
    cutoff = [R(1)]+[R(0)]*7
    for j in range(4):
        cutoff[j+4] = -R(140*(-1)**j*math.comb(3, j), j+4)
    a.eq(cutoff, [1, 0, 0, 0, -35, 84, -70, 20], 'integrated C3 cutoff')
    derivative = cutoff
    for order in range(4):
        a.eq((derivative[0], sum(derivative)), (1, 0) if order == 0 else (0, 0), 'cutoff endpoint derivatives')
        derivative = [j*derivative[j] for j in range(1, len(derivative))]
    a.eq(R(3, 4)/(R(3, 4)/(1-R(1, 2)**2)), R(3, 4), 'root-T coefficient variance')
    lag = [R(1), R(2), -R(1)]
    conditional_mean = sum(lag[j]*(lag[j+1]-R(1, 2)*lag[j]) for j in range(2))
    a.eq((conditional_mean, R(3, 4)*lag[-1]**2), (-R(5, 2), R(3, 4)), 'full-design conditional score law')
    a.eq(R(3, 4)*sum(x*x for x in lag), R(9, 2), 'false fixed-design variance differs')
    a.interventions.append('Negative and zero stable coefficients, and full-lag conditioning, retain the actual score law.')
    a.anchor(page, 4, '28', '14', 'C³', '3/4', 'nonzero mean', 'σ²X_{T−1}²')

    levels, den, slope, residuals, rss = regression([1, -1, 2, 1])
    a.eq((levels, den, slope), ([0, 1, 0, 2, 3], 5, R(6, 5)), 'unit-root finite regression')
    a.eq(residuals, [1, -R(6, 5), 2, R(3, 5)], 'all finite residuals')
    score = (levels[-1]**2-sum(v*v for v in (1, -1, 2, 1)))/2
    a.eq((score, rss, rss/4), (1, R(34, 5), R(17, 10)), 'telescoped score and residual scale')
    a.eq(4*(slope-1), R(4, 5), 'unit-root scaled change')
    t2 = (slope-1)**2*den/(rss/4)
    a.eq(t2, R(2, 17), 'finite conventional statistic squared')
    a.near(math.sqrt(float(t2)), .342997170285, 'printed square-root rounding')
    scaled = regression([-3, 3, -6, -3])
    a.eq((scaled[2], scaled[4]), (slope, 9*rss), 'measurement-unit/sign intervention')
    for n in (4, 8):
        variables = [Polynomial.variable(n, j) for j in range(n)]
        qv = sum((v*v for v in variables), Polynomial.constant(n, 0))
        a.eq((qv.mean([R(1, n)]*n), variance(qv, [R(1, n)]*n)), (1, R(2, n)), 'Brownian-grid quadratic variation moments')
        a.eq(sum(R(j, n) for j in range(n))/n, R(n-1, 2*n), 'left-grid expected Brownian denominator')
        a.eq(sum(R(j, n) for j in range(1, n+1))/n, R(n+1, 2*n), 'right-grid expected Brownian denominator')
    a.anchor(page, 5, rss, rss/4, 4*(slope-1), t2, '0.342997170285', 'J>0', 'non-Gaussian')

    # Case 4: expand the entire spread from independent v0,eta1,...,eta4.
    x = [R(1), R(0), R(2), R(3)]
    v = [R(1, 2), -R(1, 2), R(1), -R(1)]
    y = [2*a+b for a, b in zip(x, v)]
    a.eq(y, [R(5, 2), -R(1, 2), 5, 5], 'cointegrated observed outcomes')
    D = sum(a*a for a in x)
    bhat = sum(a*b for a, b in zip(x, y))/D
    a.eq((D, bhat), (14, R(55, 28)), 'direct level normal equation')
    spread = Polynomial.variable(5, 0)
    numerator = Polynomial.constant(5, 0)
    for j, weight in enumerate(x, 1):
        spread = R(1, 2)*spread+Polynomial.variable(5, j)
        numerator = numerator+weight*spread
    numerator_variance = variance(numerator, [1]+[R(3, 4)]*4)
    a.eq((numerator_variance, numerator_variance/D**2), (R(87, 4), R(87, 784)), 'independent innovation-loading sampling variance')
    initial_loading = numerator.terms[(1, 0, 0, 0, 0)]
    a.eq(initial_loading, R(15, 16), 'stationary initial-spread loading')
    a.eq((numerator_variance-initial_loading**2)/D**2, R(5343, 50176), 'changed zero-initial-spread law')
    a.eq(R(1, D), R(1, 14), 'changed iid-spread law')
    innovations = [v[j]-v[j-1]/2 for j in range(1, 4)]
    a.eq(innovations, [-R(3, 4), R(5, 4), -R(3, 2)], 'only recoverable adjacent innovations')
    for j in range(1, 4):
        a.eq(y[j]-y[j-1], 2*(x[j]-x[j-1])-v[j-1]/2+innovations[j-1], 'error-correction identity')
    forecast = 2*x[-1]+v[-1]/4
    future_error = 2*Polynomial.variable(4, 0)+2*Polynomial.variable(4, 1)
    future_error = future_error+R(1, 2)*Polynomial.variable(4, 2)+Polynomial.variable(4, 3)
    forecast_var = variance(future_error, [1, 1, R(3, 4), R(3, 4)])
    a.eq((forecast, forecast_var), (R(23, 4), R(143, 16)), 'current-state future-innovation forecast')
    a.interventions.append('Stationary, fixed-zero-initial and iid spreads yield different slope variances; current-state forecasting has another information set.')
    a.anchor(page, 6, bhat, numerator_variance, numerator_variance/D**2,
             forecast, forecast_var, '−3/4,5/4,−3/2', 'v₀', 'O_P(1)')

    # Case 5: centered random-affine moment equation, then squared-filter algebra.
    rho, a2, mean_h, second_h = garch_moments(R(1, 10), R(1, 10), R(4, 5), 3)
    a.eq((rho, a2, mean_h, second_h), (R(9, 10), R(83, 100), 1, R(19, 17)), 'GARCH centered multiplier moments')
    nu_variance = 2*second_h
    gamma_square0 = nu_variance*(1+R(1, 10)**2/(1-rho*rho))
    gamma_square1 = nu_variance*(R(1, 10)+R(1, 10)**2*rho/(1-rho*rho))
    a.eq((3*second_h, 3*second_h/mean_h**2-3), (R(57, 17), R(6, 17)), 'raw and excess kurtosis')
    a.eq((gamma_square0, gamma_square1, gamma_square1/gamma_square0),
         (R(40, 17), R(28, 85), R(7, 50)), 'squared-return filter variance and covariance')
    a.eq(gamma_square1*rho**2, R(567, 2125), 'squared-return lag-three covariance')
    conditional_h = Polynomial.constant(3, R(1, 10)+R(1, 10)*9+R(4, 5)*2)
    forecasts = [conditional_h.mean([1]*3)]
    for j in range(3):
        innovation = Polynomial.variable(3, j)
        conditional_h = R(1, 10)+(R(1, 10)*innovation*innovation+R(4, 5))*conditional_h
        forecasts.append(conditional_h.mean([1]*3))
    a.eq(forecasts, [R(13, 5), R(61, 25), R(287, 125), R(1354, 625)], 'conditional expectations from Gaussian shock polynomials')
    a.eq(sum(forecasts), R(5939, 625), 'four-period return variance')
    heavy = garch_moments(R(1, 10), R(2, 5), R(1, 2), 3)
    a.eq(heavy, (R(9, 10), R(113, 100), 1, None), 'finite second, infinite fourth transfer')
    multipliers = [R(1, 5), R(2)]
    a.eq(sum(multipliers)/2, R(11, 10), 'discrete multiplier mean')
    a.eq(R(1, 2)*0+R(1, 4)*2+R(1, 4)*2, 1, 'actual discrete innovation second moment')
    a.eq(R(1, 4)*4+R(1, 4)*4, 2, 'actual discrete innovation fourth moment')
    a.eq(multipliers[0]*multipliers[1], R(2, 5), 'negative mean log via exact product below one')
    # (sqrt(1/5)+sqrt(2))/2 < 1 follows after squaring from 2/5 < (9/10)^2.
    # The product-series square-root bound therefore also gives a finite first return moment.
    a.eq(R(2, 5) < R(9, 10)**2, True, 'infinite-variance example still has an integrable centered return')
    elog = sum(math.log(float(v)) for v in multipliers)/2
    a.near(elog, -.458145365937, 'printed log rounding')
    a.eq(garch_moments(1, R(9, 10), R(1, 5), 2)[2:], (None, None), 'no finite unconditional return variance')
    const = garch_moments(R(1, 10), 0, R(4, 5), 3)
    a.eq(const, (R(4, 5), R(16, 25), R(1, 2), R(1, 4)), 'alpha-zero stationary variance')
    a.eq((3*const[3]/const[2]**2-3, const[3]-const[2]**2), (0, 0), 'alpha-zero Gaussian excess and variance-process covariance')
    a.eq(garch_moments(1, 0, 0, 3), (0, 0, 1, 1), 'zero multiplier finite-mean route without log zero')
    a.interventions.append('Separate Gaussian fourth-moment failure, discrete strict-stationary infinite variance and alpha-zero/zero-multiplier boundaries.')
    a.anchor(page, 7, 'tight', 'E A', 'a₂', 'fourth', 'stationarity')
    a.anchor(page, 8, a2, second_h, 3*second_h, 3*second_h-3,
             forecasts[-1], sum(forecasts), gamma_square0, gamma_square1, gamma_square1/gamma_square0)
    a.anchor(page, 9, heavy[1], R(11, 10), 'log(2/5)', '−0.458145365937', 'excess 0')

    # Case 6: Gaussian fourth moments of primitive innovations, not a supplied loss matrix.
    errors = overlapping(4)
    scales = [1]*5
    errors_cov = tuple(tuple(covariance(a, b, scales) for b in errors) for a in errors)
    losses = [e*e for e in errors]
    losses_cov = tuple(tuple(covariance(a, b, scales) for b in losses) for a in losses)
    a.eq(errors_cov, ((2, 1, 0, 0), (1, 2, 1, 0), (0, 1, 2, 1), (0, 0, 1, 2)), 'full overlapping-error matrix')
    a.eq(losses_cov, ((8, 2, 0, 0), (2, 8, 2, 0), (0, 2, 8, 2), (0, 0, 2, 8)), 'Gaussian moment-derived squared-loss matrix')
    average_loss = sum(losses, Polynomial.constant(5, 0))*R(1, 4)
    average_error = sum(errors, Polynomial.constant(5, 0))*R(1, 4)
    a.eq((average_loss.mean(scales), variance(average_loss, scales)), (2, R(11, 4)), 'mean squared-loss moments')
    fixed_difference = R(1, 4)+(-1)*average_error
    a.eq((fixed_difference.mean(scales), variance(fixed_difference, scales)), (R(1, 4), R(7, 8)), 'fixed comparison exact affine-Gaussian moments')
    a.eq((losses_cov[0][0]/4, errors_cov[0][0]/4), (2, R(1, 2)), 'false iid mean variances')
    a.eq(variance(Polynomial.constant(5, 0), scales), 0, 'c-zero degenerate comparison')
    in_sample = (-1)*average_error*average_error
    a.eq(in_sample.mean(scales), -R(7, 8), 'selected in-sample expected loss difference')
    old = sum(overlapping(4, coordinates=10), Polynomial.constant(10, 0))*R(1, 4)
    fresh = sum(overlapping(4, offset=5, coordinates=10), Polynomial.constant(10, 0))*R(1, 4)
    adjacent = sum(overlapping(4, offset=4, coordinates=10), Polynomial.constant(10, 0))*R(1, 4)
    a.eq(covariance(old, fresh, [1]*10), 0, 'genuinely disjoint new innovations')
    a.eq(covariance(old, adjacent, [1]*10), R(1, 16), 'adjacent-block shared innovation')
    a.eq((old*old+(-2)*old*fresh).mean([1]*10), R(7, 8), 'fresh-block expected selected difference')
    a.eq((old*old+(-2)*old*adjacent).mean([1]*10), R(3, 4), 'changed adjacent-block expectation')
    observed_errors = [e.evaluate([1, 0, 2, -1, 1]) for e in errors]
    a.eq(observed_errors, [1, 2, 1, 0], 'synthetic overlapping errors')
    a.eq((average_error.evaluate([1, 0, 2, -1, 1]), in_sample.evaluate([1, 0, 2, -1, 1])), (1, -1), 'fitted synthetic offset and loss')
    independent_errors = overlapping(4, 1)
    independent_average = sum(independent_errors, Polynomial.constant(4, 0))*R(1, 4)
    a.eq(variance(independent_average, [1]*4), R(1, 4), 'changed one-step nonoverlapping horizon')
    # A common symmetric +/-1 variable is non-Gaussian, stationary, and never averages away.
    a.eq(sum(R(1, 2)*z*z for z in (-1, 1)), 1, 'common-shock average variance for every sample size')
    a.interventions.append('Fixed-zero comparison, one-step horizon and adjacent versus disjoint evaluation blocks change the relevant law.')
    a.anchor(page, 10, '11/4', '7/8', '1/2', '1/4', 'c=0', 'always Z')
    a.anchor(page, 11, '-7/8', '+7/8', '1,2,1,0', '-1', 'u₅', 'u₆')
    a.anchor(page, 12, 'Six objections', 'Two revised analyses', 'Conclusion', 'nonzero conditional mean', '113/100')
    return {'ARMA_variances': [str(v) for v in variances],
            'VAR_stationary_covariance': [[str(v) for v in row] for row in stationary],
            'stable_Gaussian_polynomial_designs': 3,
            'unit_root_slope': str(slope), 'unit_root_statistic_squared': str(t2),
            'spread_sampling_variance': str(numerator_variance/D**2),
            'GARCH_return_fourth_moment': str(3*second_h),
            'GARCH_four_period_variance': str(sum(forecasts)),
            'selected_fresh_adjacent_expected_losses': ['-7/8', '7/8', '3/4']}


def check(root=None):
    root = Path(root) if root is not None else Path(__file__).resolve().parents[1]
    names = tuple(p for p, _, _ in AUTHOR)+(SELF, RECORD)
    before = {p: (root/p).read_bytes() for p in names}
    a = Audit()
    for name, size, digest in AUTHOR:
        a.eq((len(before[name]), hashlib.sha256(before[name]).hexdigest()),
             (size, digest), 'frozen author payload '+name)
    page = Fragment()
    page.feed(before[AUTHOR[0][0]].decode('utf-8'))
    page.close()
    ids = ['v12-c09-e'+str(i) for i in range(1, 13)]
    a.eq((list(page.prompts), list(page.answers)), (ids, ids), 'all exact paired prompts')
    a.eq((len(page.worked), len(page.ids), len(set(page.ids)), page.frames), (6, 22, 22, []), 'complete fragment structure')
    evidence = numerical(a, page)
    source = strict(before[AUTHOR[2][0]].decode('utf-8'))
    author = strict(before[AUTHOR[3][0]].decode('utf-8'))
    source_ids = {r['id'] for r in source['sources']}
    a.eq((len(source_ids), set(page.citations)), (5, source_ids), 'five accurately scoped sources')
    a.eq(all(r.get('verification') for r in source['sources']), True, 'source verification fields')
    a.eq(set(page.links), {'v12-c08.html', 'v12-c01.html', 'v12-c02.html',
        'v02-c10.html#spectral-proof', 'v03-c06.html#clt-proof',
        'v03-c12.html#integrable-strong-law-proof', 'v10-c07.html#quadratic-variation',
        'v12-c10.html'} | {'sources.html#'+s for s in source_ids}, 'flat method routes')
    a.eq(set(author['payloads']), {r[0] for r in AUTHOR[:3]}, 'author nonself bindings')
    for name, record in author['payloads'].items():
        a.eq(record, {'bytes': len(before[name]), 'sha256': hashlib.sha256(before[name]).hexdigest()}, 'author binding '+name)
    peer = strict(before[RECORD].decode('utf-8'))
    bindings = peer['reviewed_hashes']
    a.eq((len(bindings), {r['path'] for r in bindings}), (5, set(names)-{RECORD}), 'peer five nonself bindings')
    for row in bindings:
        raw = before[row['path']]
        a.eq((row['bytes'], row['sha256']), (len(raw), hashlib.sha256(raw).hexdigest()), 'peer binding '+row['path'])
    a.eq([r['id'] for r in peer['exercise_audit']], ids, 'all exact prompt audits')
    for row in peer['exercise_audit']:
        text = normal_text(page.prompts[row['id']]).encode('utf-8')
        a.eq(row['normalized_prompt_sha256'], hashlib.sha256(text).hexdigest(), 'exact reviewed prompt '+row['id'])
    invalid = [
        (lambda: exact(True), 'boolean numeric input'),
        (lambda: exact(float('nan')), 'nonfinite numeric input'),
        (lambda: exact(10**7), 'numeric magnitude bound'),
        (lambda: count(True), 'boolean dimension'),
        (lambda: filter_coefficients(1, 0, 3), 'unit-root stable filter'),
        (lambda: filter_coefficients(R(1, 2), 2, 3, True), 'noninvertible recovery'),
        (lambda: future_arma(0, 0, 0, 0, 7), 'forecast horizon bound'),
        (lambda: geometric_inner([(1, 1)], [(R(1, 2), 1)]), 'nondecaying impulse series'),
        (lambda: matrix([[1, 2], [1]]), 'ragged matrix'),
        (lambda: multiply([[1, 2]], [[1]]), 'matrix conformability'),
        (lambda: stable_polynomials(1, 1, 4), 'unit-root stable-score law'),
        (lambda: stable_polynomials(0, 0, 4), 'zero innovation variance'),
        (lambda: regression([1]), 'one-date zero-start regression'),
        (lambda: regression([0, 0]), 'zero lagged design'),
        (lambda: garch_moments(0, 0, 0, 3), 'zero GARCH intercept'),
        (lambda: garch_moments(1, -1, 0, 3), 'negative GARCH coefficient'),
        (lambda: garch_moments(1, 0, 0, R(1, 2)), 'impossible standardized fourth moment'),
        (lambda: overlapping(4, 4), 'unsupported overlap horizon'),
        (lambda: overlapping(4, offset=4, coordinates=5), 'unavailable future innovation'),
        (lambda: Polynomial(1, {(-1,): 1}), 'negative polynomial degree'),
        (lambda: Polynomial(1, {(13,): 1}), 'polynomial degree bound'),
        (lambda: Polynomial.variable(1, 1), 'coordinate support'),
        (lambda: Polynomial.variable(1, 0).mean([0]), 'degenerate Gaussian input'),
        (lambda: strict('{"x":1,"x":2}'), 'duplicate JSON'),
        (lambda: strict('NaN'), 'nonfinite JSON'),
        (lambda: strict('1e500'), 'overflowed JSON'),
    ]
    for fn, label in invalid:
        a.reject(fn, label)
    for name, raw in before.items():
        a.eq((root/name).read_bytes(), raw, 'read-only execution '+name)
    result = {'chapter': 'v12-c09', 'status': 'independent peer checks passed',
              'comparisons': a.comparisons, 'computed_solution_anchors': a.anchors,
              'domain_rejections': len(a.rejections), 'rejection_scopes': a.rejections,
              'purposeful_interventions': len(a.interventions), 'intervention_scopes': a.interventions,
              'worked_cases': 6, 'exact_exercises_and_solutions': 12,
              'nonself_peer_bindings': 5, 'author_code_used_as_oracle': False,
              'finite_evidence': evidence,
              'limits': 'Finite independent evidence plus separate proof audit; no general dependent-data, unit-root, VAR, cointegration-rank, QMLE or selected-forecast theorem, empirical validation, rendered UI or acceptance claim.'}
    strict(json.dumps(result, allow_nan=False))
    return result


if __name__ == '__main__':
    check()
