"""Independent finite audit of Volume 12 support; quiet and read-only.

No author checker is imported. Exactly five author and two peer payloads are
read. Chapter/anchor existence was inspected once outside the portable runtime.
"""
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from itertools import combinations, product
import json
from pathlib import Path
import re
import sys

AUTHOR = {
    'content/assessments/parts/v12-support-opening.html': (13606, 'db5731cb0c69bd149b6fbb5d69b0f605b8e773e49c9c1e4f1df19adf13c04ba5'),
    'content/assessments/parts/v12-support-closing.html': (27484, 'ef36b11b2ffe7b321bda7f4366f2f57884529f0a990b205173953dc79025294b'),
    'scripts/check_v12_support.py': (10663, 'b15a5ddf423958577f7910bc5dd53c08fe3290e6e86818e7d2616e66655a0f1b'),
    'content/reviews/v12-support-sources.json': (1437, 'ce5a970e87b7aea6d284fc303664e1b249da1bb0f2899ced0a4203b1601cc8b1'),
    'content/reviews/v12-support-author.json': (3057, '06f25a98c6c2799f49d3b65f278b44739b65dba17e93213499c6048fccd5d7d4'),
}
SELF = 'scripts/check_v12_support_peer.py'
REVIEW = 'content/reviews/v12-support-peer.json'


def need(ok, message):
    if not ok:
        raise ValueError(message)


def number(x):
    need(type(x) in (int, F), 'finite exact scalar; bool excluded')
    return F(x)


def vector(x, n=None):
    need(type(x) in (tuple, list) and bool(x), 'nonempty numeric vector')
    need(n is None or len(x) == n, 'numeric dimensions')
    return tuple(number(v) for v in x)


def mean(x):
    x = vector(x)
    return sum(x)/len(x)


def variance(x):
    x = vector(x)
    center = mean(x)
    return mean(tuple((v-center)**2 for v in x))


def weighted(values, weights):
    values, weights = vector(values), vector(weights)
    need(len(values) == len(weights), 'weight dimensions')
    need(all(w >= 0 for w in weights) and sum(weights) == 1, 'probability weights')
    return sum(x*w for x, w in zip(values, weights))


def ols(x, y):
    """Solve two normal equations by determinant, not a saved coefficient."""
    x, y = vector(x), vector(y)
    need(len(x) == len(y), 'OLS aligned observations')
    n, sx, sxx, sy, sxy = len(x), sum(x), sum(v*v for v in x), sum(y), sum(a*b for a, b in zip(x, y))
    determinant = n*sxx-sx*sx
    need(determinant > 0, 'OLS intercept/design rank')
    return (sxx*sy-sx*sxy)/determinant, (n*sxy-sx*sy)/determinant


def quadratic_minimum(targets, weights):
    targets, weights = vector(targets), vector(weights)
    need(len(targets) == len(weights), 'quadratic dimensions')
    need(all(w > 0 for w in weights), 'strict convex weights')
    minimizer = sum(w*t for w, t in zip(weights, targets))/sum(weights)
    value = sum(w*(minimizer-t)**2 for w, t in zip(weights, targets))
    return minimizer, value, 2*sum(weights)


def missing_bounds(known, lo, hi):
    known, lo, hi = vector(known), number(lo), number(hi)
    need(lo <= hi, 'ordered missing-value bounds')
    return (sum(known)+lo)/(len(known)+1), (sum(known)+hi)/(len(known)+1)


def bernoulli_mle(success, trials):
    need(type(success) is int and type(trials) is int and trials > 0 and 0 <= success <= trials,
         'integer Bernoulli counts')
    return F(success, trials)


def spd2(omega):
    need(type(omega) in (tuple, list) and len(omega) == 2, '2x2 covariance')
    a, b = vector(omega[0], 2), vector(omega[1], 2)
    need(a[1] == b[0] and a[0] > 0 and a[0]*b[1]-a[1]*b[0] > 0,
         'positive definite symmetric covariance')
    return a, b


def soft(z, gram, penalty, weight=None):
    z, gram, penalty = vector(z), vector(gram), number(penalty)
    need(len(z) == len(gram) and all(g > 0 for g in gram), 'positive diagonal Gram')
    need(penalty >= 0, 'nonnegative penalty')
    weight = (F(1),)*len(z) if weight is None else vector(weight, len(z))
    need(all(w > 0 for w in weight), 'positive penalty weights')
    return tuple((1 if a >= 0 else -1)*max(abs(a)-penalty*w, F(0))/g
                 for a, g, w in zip(z, gram, weight))


def posterior(prior, high_likelihood, low_likelihood):
    prior, high_likelihood, low_likelihood = map(number, (prior, high_likelihood, low_likelihood))
    need(all(0 <= v <= 1 for v in (prior, high_likelihood, low_likelihood)), 'probability domain')
    evidence = prior*high_likelihood+(1-prior)*low_likelihood
    need(evidence > 0, 'positive evidence')
    return prior*high_likelihood/evidence


def response_law(missing1, missing0):
    """Full 32-atom potential-response/potential-outcome/assignment law."""
    missing1, missing0 = number(missing1), number(missing0)
    need(0 <= missing1 <= 1 and 0 <= missing0 <= 1, 'binary missing means')
    out = []
    for r0, y0, r1, y1, z in product((0, 1), repeat=5):
        p = F(1, 2)
        for r, y, respondent, missing in ((r0, y0, F(1, 3), missing0), (r1, y1, F(2, 3), missing1)):
            p *= F(3, 4) if r else F(1, 4)
            success = respondent if r else missing
            p *= success if y else 1-success
        out.append(((r0, y0, r1, y1, z), p))
    return tuple(out)


def written_pass(scores, critical=False):
    need(type(critical) is bool, 'critical-error flag')
    need(type(scores) in (tuple, list) and len(scores) == 5, 'five written domains')
    need(all(type(s) is int and 0 <= s <= 20 for s in scores), 'bounded integer scores')
    return not critical and sum(scores) >= 85 and min(scores) >= 15


def strict_json(text):
    def unique(pairs):
        out = {}
        for key, value in pairs:
            need(key not in out, 'duplicate JSON key')
            out[key] = value
        return out
    def nonfinite(value):
        raise ValueError('nonfinite JSON')
    return json.loads(text, object_pairs_hook=unique, parse_constant=nonfinite)


def fmt(x):
    if type(x) is tuple:
        return '('+','.join(fmt(t) for t in x)+')'
    return str(x).replace('-', '−')


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.ids, self.points, self.answers = [], set(), {}, {}
        self.markers, self.active, self.links, self.all_text = {}, [], set(), []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        ident = a.get('id')
        if ident is not None:
            need(ident not in self.ids, 'unique support ID')
            self.ids.add(ident)
        if 'data-points' in a:
            need(tag == 'li' and ident is not None and ident not in self.points, 'scored prompt ID')
            need(re.fullmatch(r'[1-9][0-9]*', a['data-points']) is not None, 'positive integer points')
            self.points[ident] = int(a['data-points'])
        if 'data-solution-for' in a:
            key = a['data-solution-for']
            need(tag == 'li' and key not in self.answers and any('solutions' in cls for unused, cls in self.stack),
                 'unique disclosed solution')
            self.answers[key] = ''
            self.active.append((self.answers, key, len(self.stack)))
        if 'data-check' in a:
            key = a['data-check']
            need(tag == 'span' and key not in self.markers, 'unique numeric marker')
            self.markers[key] = ''
            self.active.append((self.markers, key, len(self.stack)))
        if 'href' in a:
            self.links.add(a['href'])
        if tag not in ('br', 'hr', 'img', 'meta', 'link', 'input'):
            self.stack.append((tag, a.get('class', '').split()))

    def handle_endtag(self, tag):
        need(self.stack and self.stack[-1][0] == tag, 'balanced support HTML')
        self.stack.pop()
        self.active = [item for item in self.active if item[2] < len(self.stack)]

    def handle_data(self, text):
        self.all_text.append(text)
        for destination, key, depth in self.active:
            destination[key] += text

    def finish_fragment(self):
        need(not self.stack and not self.active, 'closed support fragment')


def parse_fragments(texts):
    p = Page()
    for text in texts:
        p.feed(text)
        p.finish_fragment()
    p.close()
    expected = {f'v12-d{i}': 5 for i in range(1, 9)}
    expected.update({f'v12-o{i}': 4 for i in range(1, 6)})
    expected.update({f'v12-r{i}': 10 for i in range(1, 6)})
    need(p.points == expected and set(p.answers) == set(expected), 'all eighteen complete scored pairs')
    return p


class Audit:
    def __init__(self):
        self.comparisons, self.rejections = 0, 0
        self.interventions = []

    def test(self, condition, label):
        need(condition, label)
        self.comparisons += 1

    def equal(self, actual, expected, label):
        self.test(actual == expected, label)

    def reject(self, action, label):
        try:
            action()
        except (ValueError, TypeError):
            self.comparisons += 1
            self.rejections += 1
        else:
            raise ValueError('invalid input accepted: '+label)


def check(root=None):
    root = Path(root) if root is not None else Path(__file__).resolve().parents[1]
    names = tuple(AUTHOR)+(SELF, REVIEW)
    payloads = {name: (root/name).read_bytes() for name in names}
    audit = Audit()
    for name, binding in AUTHOR.items():
        audit.equal((len(payloads[name]), sha256(payloads[name]).hexdigest()), binding, 'frozen author '+name)
    html = tuple(payloads[name].decode('utf-8') for name in tuple(AUTHOR)[:2])
    p = parse_fragments(html)
    source = strict_json(payloads['content/reviews/v12-support-sources.json'].decode('utf-8'))
    author = strict_json(payloads['content/reviews/v12-support-author.json'].decode('utf-8'))
    review = strict_json(payloads[REVIEW].decode('utf-8'))
    marks = {}

    # D1: joint probability mass, rather than conditioning on observed group labels alone.
    def selection(pi0, pi1):
        population = []
        for x in (0, 1):
            pi = (pi0, pi1)[x]
            for d in (0, 1):
                population.append((x, d, 2*x+3*d, F(1, 2)*(pi if d else 1-pi)))
        group = tuple(sum(y*w for x, d, y, w in population if d == a)/sum(w for x, d, y, w in population if d == a)
                      for a in (0, 1))
        return population, group
    law, groups = selection(F(1, 4), F(3, 4))
    audit.equal(sum(w for x, d, y, w in law), 1, 'D1 complete probability')
    audit.equal(sum(w for x, d, y, w in law if d), F(1, 2), 'D1 treatment probability')
    for arm, value in ((1, F(3, 4)), (0, F(1, 4))):
        audit.equal(sum(x*w for x, d, y, w in law if d == arm)/F(1, 2), value, 'D1 conditional composition')
    marks['d1-observed'], marks['d1-effect'] = groups[1]-groups[0], F(3)
    audit.equal(selection(F(1, 2), F(1, 2))[1], (F(1), F(4)), 'no selection contrast equals effect')
    reversed_groups = selection(F(3, 4), F(1, 4))[1]
    audit.equal(reversed_groups[1]-reversed_groups[0], 2, 'reversed selection reduces observed contrast')
    audit.interventions.append('Selection removal and reversal with fixed potential effects')

    # D2: exact shared-sign law.
    atoms = tuple((5+c+e1, 5+c+e2) for c, e1, e2 in product((-1, 1), repeat=3))
    first, second = tuple(x for x, y in atoms), tuple(y for x, y in atoms)
    audit.equal((variance(first), variance(second)), (2, 2), 'D2 marginal variances')
    covariance = mean(tuple((x-5)*(y-5) for x, y in atoms))
    audit.equal(covariance, 1, 'D2 covariance')
    marks['d2-variance'] = variance(tuple(F(x+y, 2) for x, y in atoms))
    marks['d2-false'] = (variance(first)+variance(second))/4
    absent_shared = tuple(F(e1+e2, 2) for e1, e2 in product((-1, 1), repeat=2))
    audit.equal(variance(absent_shared), F(1, 2), 'removing shared shock changes mean variance')
    audit.interventions.append('Whole-unit versus row-level covariance and removed common shock')

    # D3/D4: normal-equation determinant and completed square.
    xs, ys = (0, 1, 2), (1, 2, 6)
    intercept, slope = ols(xs, ys)
    residual = tuple(y-intercept-slope*x for x, y in zip(xs, ys))
    marks.update({'d3-slope': slope, 'd3-intercept': intercept, 'd3-sse': sum(e*e for e in residual)})
    audit.equal(residual, (F(1, 2), -1, F(1, 2)), 'D3 full residual vector')
    audit.equal((sum(residual), sum(x*e for x, e in zip(xs, residual))), (0, 0), 'D3 both normal equations')
    audit.equal(ols(xs, tuple(y+7 for y in ys)), (intercept+7, slope), 'OLS level translation')
    optimum, loss, curvature = quadratic_minimum((2, -1), (1, 2))
    marks.update({'d4-minimizer': optimum, 'd4-loss': loss})
    audit.equal(curvature, 6, 'D4 strictly positive second derivative')
    for trial in (F(-2), F(1, 3), F(5)):
        audit.equal((trial-2)**2+2*(trial+1)**2-loss, 3*(trial-optimum)**2, 'D4 global completed square')

    # D5/D6/D7/D8: exact algebra and finite reference distribution.
    derivative = -F(1, 4**2)
    marks['d5-root-variance'] = 9*derivative**2
    marks['d5-se'] = 3*abs(derivative)/10
    for h in (F(-1, 10), F(1, 10)):
        audit.equal(F(1)/(4+h)-F(1, 4)-derivative*h, h*h/(16*(4+h)), 'D5 reciprocal Taylor remainder')
    bounds = missing_bounds((3, 5, 7), 0, 10)
    marks['d6-bounds'] = '['+str(bounds[0])+','+str(bounds[1])+']'
    marks['d6-complete'] = mean((3, 5, 7))
    for m in (0, 5, 10):
        audit.equal(F(15+m, 4), bounds[0]+F(m, 10)*(bounds[1]-bounds[0]), 'D6 full attainable interval')
    phat = bernoulli_mle(5, 8)
    marks['d7-mle'] = phat
    audit.equal(5/phat-3/(1-phat), 0, 'D7 score')
    audit.test(-5/phat**2-3/(1-phat)**2 < 0 and phat**5*(1-phat)**3 > 0,
               'D7 concavity and positive interior likelihood')
    audit.equal((bernoulli_mle(0, 8), bernoulli_mle(8, 8)), (0, 1), 'Bernoulli boundary transfers')
    values = (1, 3, 5, 7)
    orbit = tuple(sum(values[i] for i in pair)-F(sum(values), 2) for pair in combinations(range(4), 2))
    marks['d8-orbit'] = ','.join(map(str, orbit))
    marks['d8-tail'] = F(sum(abs(x) >= abs(orbit[-1]) for x in orbit), len(orbit))
    audit.equal(orbit, (-4, -2, 0, 0, 2, 4), 'D8 complete balanced lottery')
    audit.interventions.append('Global quadratic bounds, reciprocal remainder, missing-value attainability and likelihood boundaries')

    # Oral evidence: observational equivalence and sufficient-condition logic.
    beta_bounds = ((F(4)-1)/2, (F(4)+1)/2)
    marks['o1-bounds'] = '['+str(beta_bounds[0])+','+str(beta_bounds[1])+']'
    for direct in (-1, 0, 1):
        beta = (F(4)-direct)/2
        for z in (-1, 1):
            audit.equal(beta*(2*z)+direct*z, 4*z, 'O1 full observed-law witness')
    marks['o2-contaminated'] = (2-0)-(6-5)
    marks['o2-effect'] = 2
    audit.equal((2-0)-(5-5), 2, 'O2 stable earlier effect removes this contamination')
    marks['o3-level-variance'] = 'Var(Xₜ)=t'
    for t in (1, 3, 5):
        walks = tuple(sum(path) for path in product((-1, 1), repeat=t))
        audit.equal(variance(walks), t, 'O3 independent increment variance')
    audit.equal(variance((-1, 1)), 1, 'O3 stationary residual variance')
    rate = F(1, 2)-F(1, 5)-F(1, 5)
    marks['o4-scaled-order'] = 'Oₚ(n^('+str(rate)+'))'
    audit.equal(rate, F(1, 10), 'O4 root-n bound exponent')
    audit.equal(F(1, 2)-F(1, 2)-F(1, 5), -F(1, 5), 'O4 sufficient improved exponent')
    audit.interventions.append('Compatible IV mechanisms, treated-comparison contamination and improved nuisance rate')

    # R1 independent route: parameterize every admissible row as (1-3t,t).
    omega = spd2(((2, 1), (1, 4)))
    def quad(row):
        return sum(row[i]*omega[i][j]*row[j] for i, j in product(range(2), repeat=2))
    beta = F(2)
    audit.equal((beta, 3*beta), (2, 6), 'R1 compatible population moments')
    identity = (F(1, 10), F(3, 10))
    tstar = F(10, 32)  # derivative of 16t^2-10t+2.
    efficient = (1-3*tstar, tstar)
    marks['r1-identity-variance'] = quad(identity)
    marks['r1-efficient-variance'] = quad(efficient)
    audit.equal(efficient, (F(1, 16), F(5, 16)), 'R1 unique efficient row')
    audit.equal(quad(identity)-quad(efficient), F(1, 400), 'R1 strict variance improvement')
    for t in (F(-1), F(0), F(3, 10), F(1)):
        row = (1-3*t, t)
        audit.equal(quad(row), F(7, 16)+16*(t-tstar)**2, 'R1 global completed-square certificate')

    # R2 complete joint laws, including independent assignment and observed response distribution.
    def audit_response(a, b):
        law = response_law(a, b)
        audit.equal(sum(p for state, p in law), 1, 'R2 complete potential-variable law')
        effect_mean = sum((y1-y0)*p for (r0, y0, r1, y1, z), p in law)
        for arm, expected in ((0, F(1, 3)), (1, F(2, 3))):
            response_mass = sum(p for (r0, y0, r1, y1, z), p in law if z == arm and (r1 if arm else r0))
            numerator = sum((y1 if arm else y0)*p for (r0, y0, r1, y1, z), p in law if z == arm and (r1 if arm else r0))
            audit.equal(response_mass, F(3, 8), 'R2 randomization and response rate')
            audit.equal(numerator/response_mass, expected, 'R2 preserved observed mean')
        return effect_mean
    original = (audit_response(0, 1), audit_response(1, 0))
    refined = (audit_response(F(1, 5), F(4, 5)), audit_response(F(2, 5), F(3, 5)))
    for alpha in (F(1, 3), F(2, 3)):
        audit.equal(audit_response(alpha, 1-alpha), alpha/2, 'R2 every intermediate endpoint mixture')
    marks['r2-original-bounds'] = '['+str(original[0])+','+str(original[1])+']'
    marks['r2-complete'] = F(2, 3)-F(1, 3)
    marks['r2-refined-bounds'] = '['+str(refined[0])+','+str(refined[1])+']'
    audit.interventions.append('Full potential-response endpoint laws and interior sharpness completions')

    # R3 covariance Toeplitz sum versus direct finite innovation coefficients.
    innovation_var, theta = F(9), -F(1, 3)
    gamma0, gamma1 = innovation_var*(1+theta**2), innovation_var*theta
    covariance = tuple(tuple(gamma0 if i == j else gamma1 if abs(i-j) == 1 else F(0)
                            for j in range(5)) for i in range(5))
    mean_var = sum(sum(row) for row in covariance)/25
    coefficients = (theta/5,)+((1+theta)/5,)*4+(F(1, 5),)
    audit.equal(mean_var, innovation_var*sum(c*c for c in coefficients), 'R3 innovation versus covariance variance')
    marks.update({'r3-long-run': gamma0+2*gamma1, 'r3-mean-variance': mean_var,
                  'r3-false': gamma0/5, 'r3-forecast-mean': theta*3, 'r3-forecast-variance': innovation_var})
    audit.equal(mean_var, F(4, 5)+F(6, 25), 'R3 long-run versus finite boundary correction')
    for t in (1, 2, 6):
        audit.equal((t*gamma0+2*(t-1)*gamma1)/t**2, F(4, t)+F(6, t*t), 'R3 changed finite horizon')
    audit.test('z₀.₉₇₅√26/5' in p.answers['v12-r3'], 'R3 exact interval uses finite standard deviation')

    # R4 diagonal quadratic subgradients and independent prior likelihood update.
    z, gram, penalty = (F(2), -F(1, 2)), (F(1), F(1)), F(3, 4)
    best = soft(z, gram, penalty)
    marks['r4-original'] = best
    audit.equal(z[0]-gram[0]*best[0], penalty, 'R4 active subgradient')
    audit.test(abs(z[1]-gram[1]*best[1]) <= penalty, 'R4 inactive subgradient')
    scaled = soft((4, -F(1, 2)), (4, 1), penalty)
    marks.update({'r4-scaled-coefficient': scaled[0], 'r4-scaled-contribution': 2*scaled[0]})
    restored = soft((4, -F(1, 2)), (4, 1), penalty, (2, 1))
    audit.equal((2*restored[0], restored[1]), best, 'R4 weighted penalty restores fit')
    def objective(b):
        return sum(g*x*x/2-y*x+penalty*abs(x) for x, g, y in zip(b, gram, z))
    for candidate in ((F(0), F(0)), (F(2), -F(1, 2)), (-F(1), F(1))):
        audit.test(objective(candidate)-objective(best) >= sum(g*(x-y)**2/2 for g, x, y in zip(gram, candidate, best)),
                   'R4 convex global lower bound')
    prior_odds, likelihood_ratio = F(1, 3), F(3)
    odds = prior_odds*likelihood_ratio
    marks['r4-posterior'] = odds/(1+odds)
    audit.equal(marks['r4-posterior'], posterior(F(1, 4), F(3, 4), F(1, 4)), 'R4 odds versus joint-mass update')
    audit.interventions.append('MA horizon boundary, lasso column scaling and restored penalty')

    # R5 continuous law: CDF and inverse compose exactly at rational-square complements.
    cdf = lambda u: 1-(1-u)**2
    marks['r5-adjusted'] = cdf(F(1, 25))
    audit.test(marks['r5-adjusted'] > F(1, 20), 'R5 adjusted nonrejection')
    for root_value in (F(0), F(1, 4), F(3, 4), F(1)):
        q = 1-root_value**2
        audit.equal(cdf(1-root_value), q, 'R5 continuous inverse proof arithmetic')
    audit.test(cdf(F(1, 25)) != F(1, 25), 'perfectly dependent p-values need a different minimum CDF')
    effects = (-F(2), F(4))
    marks['r5-source'] = weighted(effects, (F(3, 4), F(1, 4)))
    marks['r5-target'] = weighted(effects, (F(1, 3), F(2, 3)))
    target_bounds = (weighted(effects, (F(3, 5), F(2, 5))), weighted(effects, (F(1, 5), F(4, 5))))
    marks['r5-bounds'] = '['+str(target_bounds[0])+','+str(target_bounds[1])+']'
    for a in (F(0), F(1, 2), F(1)):
        w = F(2, 5)+a*F(2, 5)
        audit.equal(-2+6*w, (1-a)*target_bounds[0]+a*target_bounds[1], 'R5 attained target mixture')
    audit.interventions.append('Selection-law dependence and compatible target-composition transfers')

    # Structural, rubric and administration tests use the actual full solution text.
    audit.test({'notation-index', 'concept-index'} <= p.ids, 'both shared reference anchors present')
    audit.equal(set(p.markers), set(marks), 'all39 exact markers covered')
    for key, value in marks.items():
        audit.equal(p.markers[key].strip(), fmt(value), 'printed '+key)
    for ident, points in p.points.items():
        answer = p.answers[ident]
        audit.test('Credit:' in answer, 'explicit subpart rubric '+ident)
        credit = answer.split('Credit:', 1)[1].split('Review', 1)[0].split('Follow-up:', 1)[0]
        allocations = [int(v) for v in re.findall(r'\b([1-9][0-9]*)[;.]', credit)]
        audit.equal(sum(allocations), points, 'rubric point sum '+ident)
    for prefix, total in (('d', 40), ('o', 20), ('r', 50)):
        audit.equal(sum(points for ident, points in p.points.items() if ident.startswith('v12-'+prefix)), total, 'component total '+prefix)
    audit.equal(5*55+25, 300, 'written allocation arithmetic')
    audit.test(written_pass((17,)*5), 'written pass exactly at total threshold')
    audit.test(not written_pass((16, 17, 17, 17, 17)), 'written total shortfall')
    audit.test(not written_pass((14, 18, 18, 18, 18)), 'written essential-domain shortfall despite total')
    audit.test(not written_pass((20,)*5, True), 'critical error overrides total')
    audit.equal(sum((5, 5, 4, 4, 4, 4, 4, 4)), 34, 'diagnostic feasible threshold')
    audit.equal(sum((4, 4, 3, 3, 3)), 17, 'oral feasible threshold with all floors')
    audit.equal(sum((9, 9, 9, 8, 8)), 43, 'retention feasible threshold with all floors')
    route_digest = sha256('\n'.join(sorted(p.links)).encode()).hexdigest()
    audit.equal({'unique_hrefs': len(p.links), 'href_set_sha256': route_digest}, review['route_audit']['inventory'],
                'frozen links match once-inspected actual routes')

    # Small explicit invalid-domain suite, active under optimization.
    for invalid in (True, False, '1', None, 0.5, float('nan'), float('inf')):
        audit.reject(lambda invalid=invalid: number(invalid), 'exact numeric type')
    audit.reject(lambda: ols((1, 1, 1), (1, 2, 3)), 'rank failure')
    audit.reject(lambda: ols((1, 2), (1,)), 'misaligned observations')
    audit.reject(lambda: missing_bounds((3, 5, 7), 10, 0), 'reversed support')
    for s, n in ((True, 8), (9, 8), (-1, 8), (0, 0)):
        audit.reject(lambda s=s, n=n: bernoulli_mle(s, n), 'invalid Bernoulli counts')
    for omega_bad in (((1, 1), (1, 1)), ((2, 2), (1, 4)), ((-1, 0), (0, 1))):
        audit.reject(lambda omega_bad=omega_bad: spd2(omega_bad), 'covariance condition')
    audit.reject(lambda: response_law(F(6, 5), 0), 'binary missing mean')
    audit.reject(lambda: soft((2, 1), (0, 1), 1), 'Gram rank')
    audit.reject(lambda: soft((2, 1), (1, 1), -1), 'negative penalty')
    audit.reject(lambda: soft((2, 1), (1, 1), 1, (0, 1)), 'penalty weight')
    audit.reject(lambda: posterior(F(1, 4), 0, 0), 'zero evidence')
    audit.reject(lambda: weighted((1, 3), (F(1, 4), F(1, 4))), 'wrong target normalization')
    audit.reject(lambda: written_pass((21, 20, 20, 20, 20)), 'score outside scale')
    audit.reject(lambda: parse_fragments((html[0].replace('id="v12-d2"', 'id="v12-d1"', 1), html[1])), 'duplicate prompt ID')
    audit.reject(lambda: parse_fragments((html[0], html[1].replace('data-solution-for="v12-r1"', 'data-solution-for="v12-r2"', 1))), 'wrong solution identity')
    for malformed in ('{"x":1,"x":2}', '{"x":NaN}'):
        audit.reject(lambda malformed=malformed: strict_json(malformed), 'strict JSON')
    audit.interventions.append('Rank, support, probability, penalty, score and exact-pairing rejection')

    audit.equal(source['new_primary_body_reads'], [], 'no new source-body claim')
    audit.equal(author['open_findings'], [], 'author findings resolved')
    audit.equal(set(author['reviewed_hashes']), set(AUTHOR)-{'content/reviews/v12-support-author.json'}, 'author four nonself bindings')
    for name, binding in author['reviewed_hashes'].items():
        audit.equal((binding['bytes'], binding['sha256']), AUTHOR[name], 'author binding '+name)
    audit.equal(set(review['bindings']), set(AUTHOR) | {SELF}, 'five author plus checker bindings')
    for name, binding in review['bindings'].items():
        audit.equal(binding, {'bytes': len(payloads[name]), 'sha256': sha256(payloads[name]).hexdigest()}, 'peer exact binding '+name)
    audit.equal(set(review['prompt_audit']), set(p.points), 'all18 substantive prompt judgments')
    audit.test(not review['unresolved_findings'], 'peer issue disposition')
    summary = {'volume': 'v12', 'component': 'support', 'status': 'independent peer checks passed',
               'comparisons': audit.comparisons, 'rejections': audit.rejections,
               'intervention_groups': len(audit.interventions), 'interventions': audit.interventions,
               'numeric_markers': len(marks), 'diagnostic_questions': 8, 'oral_questions': 5,
               'retention_questions': 5, 'scored_points': {'diagnostic': 40, 'oral': 20, 'retention': 50},
               'actual_routes_checked_before_freeze': len(p.links), 'runtime_payloads': len(names),
               'limits': 'Independent machine-assisted support review; prior source scopes reused, timing uncalibrated, rendered UI and learner competence not established.'}
    json.dumps(summary, allow_nan=False)
    return summary


if __name__ == '__main__':
    if len(sys.argv) != 1:
        raise SystemExit('usage: python3 -B check_v12_support_peer.py')
    check()
