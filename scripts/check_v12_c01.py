"""Focused exact checks for the original graduate identification chapter.

No network, random simulation, model import or file write. The inequalities and
asymptotic proofs require the separate full reading; finite checks do not prove
general probability theorems. Canonical chapter checks remain separate from acceptance and rendered UI QA.
"""
from fractions import Fraction as F
from html.parser import HTMLParser
from math import comb, sqrt, isclose
from pathlib import Path
from statistics import NormalDist
import json
import re


class Audit:
    def __init__(self):
        self.comparisons = 0

    def equal(self, actual, expected, label):
        self.comparisons += 1
        if actual != expected:
            raise ValueError(label + ': ' + repr(actual) + ' != ' + repr(expected))

    def near(self, actual, expected, tolerance, label):
        self.comparisons += 1
        if not isclose(actual, expected, rel_tol=0, abs_tol=tolerance):
            raise ValueError(label + ': numerical mismatch')


class Document(HTMLParser):
    VOID = {'br', 'hr', 'img', 'input', 'meta', 'link'}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.ids, self.links, self.sources, self.text = [], [], [], [], []
        self.worked = self.exercises = self.solutions = 0
        self.in_exercises = self.in_solutions = False
        self.ol_depth = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'id' in attrs:
            self.ids.append(attrs['id'])
        if tag == 'a':
            self.links.append(attrs.get('href', ''))
        if 'data-source' in attrs:
            self.sources.append(attrs['data-source'])
        if 'worked' in attrs.get('class', '').split():
            self.worked += 1
        if tag == 'ol':
            self.ol_depth += 1
            if 'exercises' in attrs.get('class', '').split():
                self.in_exercises = True
        if tag == 'details' and 'solutions' in attrs.get('class', '').split():
            self.in_solutions = True
        if tag == 'li' and self.ol_depth == 1:
            self.exercises += int(self.in_exercises)
            self.solutions += int(self.in_solutions)
        if tag not in self.VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if not self.stack or self.stack.pop() != tag:
            raise ValueError('Unbalanced HTML at ' + tag)
        if tag == 'ol':
            self.ol_depth -= 1
            if not self.ol_depth:
                self.in_exercises = False
        if tag == 'details':
            self.in_solutions = False

    def handle_data(self, data):
        self.text.append(data)


def joint(theta, alpha, beta):
    """Late/flag cells from an explicit probability tree."""
    return (theta*(1-beta), theta*beta, (1-theta)*alpha, (1-theta)*(1-alpha))


def mean_variance(values, weights):
    mean = sum(x*p for x, p in zip(values, weights))
    return mean, sum(p*(x-mean)**2 for x, p in zip(values, weights))


def corrected(p, alpha, beta):
    denominator = 1-alpha-beta
    if denominator == 0:
        raise ValueError('Uninformative measurement kernel')
    return (p-alpha)/denominator


def binomial_coverage(n, p, z):
    """Exact rational probabilities; numerical z classifies count endpoints.

    We separately record the distance of the standardized count error from z,
    so rounding in the normal quantile cannot silently alter an inclusion.
    A count with zero sample variance covers iff its point estimate equals p.
    """
    included, margins = [], []
    for k in range(n+1):
        estimate = F(k, n)
        variance = estimate*(1-estimate)/n
        if variance:
            statistic = abs(float(estimate-p))/sqrt(float(variance))
            margins.append(abs(statistic-z))
            covers = statistic <= z
        else:
            covers = estimate == p
        if covers:
            included.append(k)
    exact = sum((F(comb(n, k))*p**k*(1-p)**(n-k) for k in included), F())
    total = sum((F(comb(n, k))*p**k*(1-p)**(n-k) for k in range(n+1)), F())
    return exact, included, min(margins), total


def check():
    a = Audit()
    root = Path(__file__).resolve().parents[1]
    path = root/'content/chapters/v12-c01.html'
    page = Document()
    page.feed(path.read_text(encoding='utf-8'))
    page.close()
    a.equal(page.stack, [], 'balanced complete fragment')
    a.equal(len(page.ids), len(set(page.ids)), 'unique anchors')
    a.equal((page.worked, page.exercises, page.solutions), (5, 12, 12), 'complete graduate package')
    sources = {'v12-c01-mit-limit-tools', 'v12-c01-mit-extremum', 'v12-c01-mit-delta', 'v12-c01-aldous-chewi-cw'}
    a.equal(set(page.sources), sources, 'scoped primary sources')
    for href in page.links:
        if href.startswith('sources.html#'):
            a.equal(href.split('#')[1] in sources, True, 'declared source anchor')
        elif re.fullmatch(r'v\d\d-c\d\d\.html', href):
            a.equal(href in {'v03-c06.html', 'v03-c07.html', 'v03-c08.html', 'v04-c01.html', 'v04-c07.html', 'v04-c08.html'}, True, 'declared prerequisite route')
        else:
            raise ValueError('Unexpected reader link ' + href)

    first = joint(F(5, 7), F(1, 10), F(1, 5))
    second = joint(F(4, 7), F(1, 5), F(1, 10))
    a.equal(first, (F(4, 7), F(1, 7), F(1, 35), F(9, 35)), 'first observational world')
    a.equal(second, (F(18, 35), F(2, 35), F(3, 35), F(12, 35)), 'second observational world')
    for cells, target in ((first, F(5, 7)), (second, F(4, 7))):
        a.equal(sum(cells), 1, 'joint probability sum')
        a.equal(min(cells) >= 0, True, 'nonnegative probabilities')
        a.equal(cells[0]+cells[2], F(3, 5), 'same recorded flag law')
        a.equal(cells[0]+cells[1], target, 'different latent targets')
    low = corrected(F(3, 5), F(3, 20), F(3, 20))
    high = corrected(F(3, 5), F(1, 20), F(1, 4))
    a.equal((low, high, high-low), (F(9, 14), F(11, 14), F(1, 7)), 'sharp partial-ID endpoints')
    # Derivative numerators have fixed signs on the entire given rectangle.
    a.equal(F(3, 5)+F(1, 4)-1 < 0, True, 'maximum alpha-derivative numerator negative')
    a.equal(F(3, 5)-F(3, 20)>0, True, 'minimum beta-derivative numerator positive')
    a.equal(1-F(3, 20)-F(1, 4)>0, True, 'minimum denominator positive')
    for theta in (F(0), F(1, 3), F(1)):
        cells = joint(theta, F(2, 5), F(3, 5))
        a.equal(cells[0]+cells[2], F(2, 5), 'zero-information kernel')
    # Negative slope is still invertible; error-rate inversion is not restricted
    # to a better-than-random flag when rates are assumed known.
    cells = joint(F(1, 4), F(7, 10), F(1, 2))
    a.equal(corrected(cells[0]+cells[2], F(7, 10), F(1, 2)), F(1, 4), 'negative-slope identification')

    for n in (2, 25, 400):
        mean, variance = mean_variance((0, n), (1-F(1, n), F(1, n)))
        a.equal((mean, variance), (1, n-1), 'rare-tail moments')
        left, right = 1-F(1, n), 1-F(1, 2*n)
        a.equal(left < right < 1, True, 'nonempty moving dip excludes endpoint')
        a.equal(left*left-2 < 0, True, 'dip beats all outside nonnegative values')
    a.equal((2*F(2, 1000)+F(1, 1000))/4, F(1, 800), 'finite optimization-error square')

    p, alpha, beta = F(3, 5), F(1, 10), F(1, 5)
    theta = corrected(p, alpha, beta)
    # Reconstruct sensitivity via the differential of p=alpha+d*theta.
    d = 1-alpha-beta
    gradient = (1/d, -(1-theta)/d, theta/d)
    a.equal(gradient, (F(10, 7), -F(20, 49), F(50, 49)), 'inverse-equation derivative')
    variances = (p*(1-p), alpha*(1-alpha), beta*(1-beta))
    contributions = tuple(g*g*v for g, v in zip(gradient, variances))
    a.equal(contributions, (F(24, 49), F(36, 2401), F(400, 2401)), 'independent validation contributions')
    a.equal(sum(contributions), F(1612, 2401), 'equal validation sampling')
    unequal = contributions[0]+2*contributions[1]+contributions[2]/2
    a.equal(unequal, F(1448, 2401), 'unequal validation sample ratios')
    # Centered influence from each entire Bernoulli support independently.
    influence_values, weights = [], []
    for main in (0, 1):
        for fp in (0, 1):
            for fn in (0, 1):
                weights.append((p if main else 1-p)*(alpha if fp else 1-alpha)*(beta if fn else 1-beta))
                influence_values.append(gradient[0]*(main-p)+gradient[1]*(fp-alpha)+gradient[2]*(fn-beta))
    a.equal(mean_variance(influence_values, weights), (0, F(1612, 2401)), 'all eight joint validation outcomes')
    a.equal(F(1, 10)*F(9, 10)/d**2, F(9, 49), 'boundary unprojected normal scale')

    values = ((0, 0), (2, 1), (8, 1))
    weights = (F(3, 5), F(1, 5), F(1, 5))
    amean, avar = mean_variance([x for x, _ in values], weights)
    dmean, dvar = mean_variance([y for _, y in values], weights)
    covariance = sum(w*(x-amean)*(y-dmean) for (x, y), w in zip(values, weights))
    a.equal((amean, dmean, avar, covariance, dvar), (2, F(2, 5), F(48, 5), F(6, 5), F(6, 25)), 'raw joint moments')
    mu = amean/dmean
    psi = tuple((x-mu*y)/dmean for x, y in values)
    a.equal(psi, (0, -F(15, 2), F(15, 2)), 'ratio influence support')
    a.equal(mean_variance(psi, weights), (0, F(45, 2)), 'ratio influence variance')
    grad = (1/dmean, -amean/dmean**2)
    variance = grad[0]**2*avar+2*grad[0]*grad[1]*covariance+grad[1]**2*dvar
    a.equal(variance, F(45, 2), 'full sandwich equals influence route')
    a.equal(grad[0]**2*avar+grad[1]**2*dvar, F(195, 2), 'independence mistake')
    a.equal(sum(F(n, 500)*v*v for n, v in zip((300, 100, 100), psi)), variance, 'observed count plug-in')

    a.equal(4*2**2*4, 64, 'regular squared-profit contrast variance')
    for n in (16, 256):
        for lam, expected in ((F(1, round(n**.25)), F(1, round(sqrt(n)))),
                              (F(1, round(sqrt(n))), F(1)),
                              (F(1, round(n**.75)), F(round(sqrt(n))))):
            a.equal(1/(n*lam*lam), expected, 'exact weak-information sequence variance')

    z = NormalDist().inv_cdf(.975)
    known_se = sqrt(float(contributions[0]/400))
    ratio_se = sqrt(float(variance/500))
    numeric_displays = {
        '.714286': float(theta), '.642857': float(low), '.785714': float(high),
        '.034992711': known_se, '.645701262': float(theta)-z*known_se,
        '.782870167': float(theta)+z*known_se, '1.959963985': z,
        '.040969102': sqrt(float(sum(contributions)/400)),
        '.038829179': sqrt(float(unequal/400)),
        '.212132034': ratio_se, '4.584228853': 5-z*ratio_se,
        '5.415771147': 5+z*ratio_se, '.035355339': sqrt(1/800),
        '.024874686': sqrt(99)/400,
    }
    coverages = []
    for n, boundaries, printed in ((25, (11, 19), '.936246277'), (100, (51, 69), '.948117979'), (400, (221, 258), '.947392305')):
        exact, included, margin, total = binomial_coverage(n, p, z)
        a.equal(total, 1, 'full binomial mass')
        a.equal((min(included), max(included)), boundaries, 'coverage count boundaries')
        a.equal(included, list(range(boundaries[0], boundaries[1]+1)), 'complete included count set')
        a.equal(margin>1e-6, True, 'normal quantile numerical classification safely away from boundary')
        numeric_displays[printed] = float(exact)
        coverages.append({'n':n, 'accepted_counts':list(boundaries), 'coverage':float(exact), 'minimum_z_margin':margin})
    a.equal(corrected(F(11, 20), F(1, 20), F(3, 20)), F(5, 8), 'retention estimand')
    a.equal(F(11, 20)*F(9, 20)/F(4, 5)**2, F(99, 256), 'retention asymptotic variance')
    text = ' '.join(page.text)
    for printed, value in numeric_displays.items():
        a.equal(printed in text, True, 'visible numerical result '+printed)
        places = len(printed.split('.')[1])
        a.near(float(printed), value, .50001*10**(-places), 'printed rounding '+printed)
    for anchor in ('estimand-identification', 'stochastic-orders', 'consistency-proof', 'linearization', 'delta-proof', 'nonregular-limits', 'exercises', 'teach-retain', 'sources-next'):
        a.equal(anchor in page.ids, True, 'required explanatory section')
    return {'chapter':'v12-c01', 'status':'passed',
            'comparisons':a.comparisons, 'worked_examples':5, 'exercises':12,
            'solutions':12, 'rounded_displays_checked':len(numeric_displays),
            'coverage_enumeration':coverages,
            'proof_scope':'Arithmetic and full finite supports checked; separate mathematical reading required for all general proofs, asymptotic assumptions and open-ended critique.'}


if __name__ == '__main__':
    print(json.dumps(check(), allow_nan=False, sort_keys=True))
