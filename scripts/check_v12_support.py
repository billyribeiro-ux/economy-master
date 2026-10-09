"""Reconstruct Volume 12 diagnostic, oral and retention calculations."""
from fractions import Fraction as F
from html.parser import HTMLParser
from itertools import combinations, product
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
FILES = (
    'content/assessments/parts/v12-support-opening.html',
    'content/assessments/parts/v12-support-closing.html',
    'scripts/check_v12_support.py',
    'content/reviews/v12-support-sources.json',
    'content/reviews/v12-support-author.json',
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


class Support(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack = []
        self.ids = []
        self.points = {}
        self.solutions = []
        self.markers = {}
        self.capture = None
        self.text = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if 'id' in a:
            require(a['id'] not in self.ids, 'duplicate id')
            self.ids.append(a['id'])
        if 'data-points' in a:
            require(a.get('id') and a['id'] not in self.points, 'scored id')
            self.points[a['id']] = int(a['data-points'])
        if 'data-solution-for' in a:
            self.solutions.append(a['data-solution-for'])
        if 'data-check' in a:
            require(self.capture is None and a['data-check'] not in self.markers,
                    'unique unnested calculation marker')
            self.capture = a['data-check']
            self.markers[self.capture] = ''
        if tag not in ('br', 'hr', 'img', 'meta', 'link', 'input'):
            self.stack.append(tag)

    def handle_endtag(self, tag):
        require(self.stack and self.stack[-1] == tag, 'balanced support HTML')
        self.stack.pop()
        if tag == 'span':
            self.capture = None

    def handle_data(self, data):
        self.text.append(data)
        if self.capture is not None:
            self.markers[self.capture] += data


def check(root=None):
    root = Path(root) if root is not None else ROOT
    parser = Support()
    for rel in FILES[:2]:
        parser.feed((root / rel).read_text())
        require(not parser.stack, 'closed support fragment')
    count = 0
    printed = set()

    def eq(got, expected, label):
        nonlocal count
        count += 1
        require(got == expected, label + ': ' + repr(got))

    def mark(key, value):
        eq(parser.markers.get(key), str(value).replace('-', '−'), key)
        printed.add(key)

    def variance(values, masses=None):
        masses = masses or [F(1, len(values))] * len(values)
        mean = sum(x * p for x, p in zip(values, masses))
        return sum((x - mean) ** 2 * p for x, p in zip(values, masses))

    expected_points = {f'v12-d{i}': 5 for i in range(1, 9)}
    expected_points.update({f'v12-o{i}': 4 for i in range(1, 6)})
    expected_points.update({f'v12-r{i}': 10 for i in range(1, 6)})
    eq(parser.points, expected_points, '18 complete scored prompts')
    eq(sorted(parser.solutions), sorted(expected_points), '18 exact solution pairs')
    for prefix, total in [('d', 40), ('o', 20), ('r', 50)]:
        eq(sum(v for k, v in parser.points.items() if k.startswith('v12-' + prefix)),
           total, prefix + ' scoring')

    # Diagnostic: compute from the primitive laws in each question.
    cells = [(x, d, F(1, 2) * ((F(1, 4) + x * F(1, 2)) if d else
                                (F(3, 4) - x * F(1, 2))))
             for x, d in product((0, 1), repeat=2)]
    means = [sum((2*x+3*d)*p for x, d, p in cells if d == arm) /
             sum(p for x, d, p in cells if d == arm) for arm in (0, 1)]
    mark('d1-observed', means[1] - means[0]); mark('d1-effect', 3)
    pairs = [(5+c+e1, 5+c+e2) for c, e1, e2 in product((-1, 1), repeat=3)]
    mark('d2-variance', variance([F(a+b, 2) for a, b in pairs]))
    mark('d2-false', (variance([a for a, b in pairs]) +
                      variance([b for a, b in pairs])) / 4)
    x, y = [F(0), F(1), F(2)], [F(1), F(2), F(6)]
    xm, ym = sum(x)/3, sum(y)/3
    b = sum((a-xm)*(z-ym) for a, z in zip(x, y))/sum((a-xm)**2 for a in x)
    a = ym-b*xm; residual = [z-a-b*t for t, z in zip(x, y)]
    mark('d3-slope', b); mark('d3-intercept', a)
    mark('d3-sse', sum(e*e for e in residual))
    eq((sum(residual), sum(t*e for t, e in zip(x, residual))), (0, 0), 'normal equations')
    optimum = F(2 + 2*(-1), 1+2)
    mark('d4-minimizer', optimum); mark('d4-loss', (optimum-2)**2 + 2*(optimum+1)**2)
    mark('d5-root-variance', F(9, 4**4)); mark('d5-se', F(3, 4**2*10))
    mark('d6-bounds', '[15/4,25/4]'); mark('d6-complete', F(3+5+7, 3))
    eq([F(3+5+v+7, 4) for v in (0, 10)], [F(15, 4), F(25, 4)], 'missing completions')
    p = F(5, 8); mark('d7-mle', p)
    eq(5/p - 3/(1-p), 0, 'Bernoulli score')
    values = (1, 3, 5, 7)
    orbit = [F(sum(values[i] for i in c), 2) -
             F(sum(values[i] for i in range(4) if i not in c), 2)
             for c in combinations(range(4), 2)]
    mark('d8-orbit', ','.join(str(v) for v in orbit))
    mark('d8-tail', F(sum(abs(v) >= abs(orbit[-1]) for v in orbit), len(orbit)))

    # Oral: point identification, unsupported comparisons and sufficient conditions.
    endpoints = [(F(4)-gamma)/2 for gamma in (F(1), F(-1))]
    eq(endpoints, [F(3, 2), F(5, 2)], 'direct-effect set')
    mark('o1-bounds', '[3/2,5/2]')
    for beta, gamma in zip(endpoints, (1, -1)):
        for z in (-1, 1):
            eq(beta*2*z + gamma*z, 4*z, 'observationally equivalent full witness')
    mark('o2-contaminated', (2-0)-(6-5)); mark('o2-effect', 2-0)
    for t in range(1, 8):
        eq(variance([sum(path) for path in product((-1, 1), repeat=t)]), t,
           'random walk finite variance')
    mark('o3-level-variance', 'Var(Xₜ)=t')
    eq(F(1, 2)-F(1, 5)-F(1, 5), F(1, 10), 'insufficient rate bound')
    eq(F(1, 2)-F(1, 2)-F(1, 5), F(-1, 5), 'improved rate bound')
    mark('o4-scaled-order', 'Oₚ(n^(1/10))')

    # R1: linear algebra and covariance decomposition, not saved exam outputs.
    B = (F(1), F(3)); omega = ((F(2), F(1)), (F(1), F(4)))
    K = tuple(v/sum(t*t for t in B) for v in B)
    quad = lambda k: sum(k[i]*omega[i][j]*k[j] for i, j in product(range(2), repeat=2))
    mark('r1-identity-variance', quad(K))
    inverse_times_B = ((4*B[0]-B[1])/7, (-B[0]+2*B[1])/7)
    norm = sum(a*b for a, b in zip(B, inverse_times_B))
    efficient = tuple(v/norm for v in inverse_times_B)
    eq(efficient, (F(1, 16), F(5, 16)), 'efficient row')
    mark('r1-efficient-variance', quad(efficient))
    for h in (F(-2), F(0), F(1, 3), F(4)):
        H = (3*h, -h); L = tuple(a+b for a, b in zip(efficient, H))
        eq(sum(a*b for a, b in zip(L, B)), 1, 'admissible GMM row')
        eq(quad(L)-quad(efficient), quad(H), 'covariance difference identity')

    # R2: build full potential response/outcome marginals and cross them.
    def arm_law(response_mean, missing_mean):
        return {(r, y): (F(3, 4) if r else F(1, 4)) *
                ((response_mean if r else missing_mean) if y else
                 (1-(response_mean if r else missing_mean)))
                for r, y in product((0, 1), repeat=2)}
    def completed_effect(m1, m0):
        arms = (arm_law(F(2, 3), m1), arm_law(F(1, 3), m0))
        for law, mean in zip(arms, (F(2, 3), F(1, 3))):
            eq(sum(law.values()), 1, 'complete arm probability')
            eq(sum(p for (r, y), p in law.items() if r), F(3, 4), 'response probability')
            eq(sum(y*p for (r, y), p in law.items() if r)/F(3, 4), mean, 'respondent mean')
        return sum((y1-y0)*p1*p0 for (r1, y1), p1 in arms[0].items()
                   for (r0, y0), p0 in arms[1].items())
    eq([completed_effect(a, b) for a, b in [(0, 1), (1, 0)]], [0, F(1, 2)], 'ATE endpoints')
    mark('r2-original-bounds', '[0,1/2]'); mark('r2-complete', F(2, 3)-F(1, 3))
    eq([completed_effect(a, b) for a, b in [(F(1, 5), F(4, 5)),
                                           (F(2, 5), F(3, 5))]],
       [F(1, 10), F(1, 5)], 'refined endpoints')
    mark('r2-refined-bounds', '[1/10,1/5]')

    # R3: sum the actual innovation coefficients of the sample mean.
    coefficient = {t: F(0) for t in range(6)}
    for t in range(1, 6):
        coefficient[t] += F(1, 5); coefficient[t-1] -= F(1, 15)
    gamma0, gamma1 = 9*(1+F(1, 9)), -3
    mark('r3-long-run', gamma0+2*gamma1)
    mark('r3-mean-variance', 9*sum(c*c for c in coefficient.values()))
    mark('r3-false', gamma0/5); mark('r3-forecast-mean', -F(3, 3))
    mark('r3-forecast-variance', 9)

    # R4: direct Gram/KKT equations; independent joint Bayes masses.
    lam = F(3, 4); z = (F(2), F(-1, 2))
    beta = tuple((1 if v >= 0 else -1)*max(abs(v)-lam, 0) for v in z)
    mark('r4-original', '('+','.join(str(v) for v in beta)+')')
    eq(z[0]-beta[0], lam, 'active KKT'); eq(abs(z[1]) <= lam, True, 'inactive KKT')
    scaled = (2*z[0]-lam)/4
    mark('r4-scaled-coefficient', scaled); mark('r4-scaled-contribution', 2*scaled)
    eq(2*(2*z[0]-2*lam)/4, beta[0], 'restored weighted penalty')
    high, low = F(1, 4)*F(3, 4), F(3, 4)*F(1, 4)
    mark('r4-posterior', high/(high+low))

    # R5: independent-square complement and affine target mixture.
    u = F(1, 25); adjusted = 1-(1-u)**2
    mark('r5-adjusted', adjusted); eq(adjusted > F(1, 20), True, 'adjusted decision')
    mark('r5-source', F(3, 4)*(-2)+F(1, 4)*4)
    mark('r5-target', F(1, 3)*(-2)+F(2, 3)*4)
    eq([-2+6*w for w in (F(2, 5), F(4, 5))], [F(2, 5), F(14, 5)], 'target endpoints')
    mark('r5-bounds', '[2/5,14/5]')
    eq(set(parser.markers), printed, 'every displayed numeric marker reconstructed')
    source = json.loads((root / FILES[3]).read_text())
    author = json.loads((root / FILES[4]).read_text())
    eq(source['new_primary_body_reads'], [], 'no invented primary inspection')
    eq(author['open_findings'], [], 'resolved author findings')
    eq(set(author['reviewed_hashes']), set(FILES[:4]), 'complete nonself bindings')
    for rel, binding in author['reviewed_hashes'].items():
        raw = (root / rel).read_bytes()
        eq({'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}, binding,
           'frozen support '+rel)
    return {'status': 'passed', 'comparisons': count, 'numeric_markers': len(printed),
            'diagnostic_questions': 8, 'oral_questions': 5, 'retention_questions': 5,
            'scored_points': {'diagnostic': 40, 'oral': 20, 'retention': 50},
            'limitations': 'Numerical/structural checks; proof and exact-prompt judgments remain substantive review.'}


if __name__ == '__main__':
    check()
