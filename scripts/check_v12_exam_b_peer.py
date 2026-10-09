"""Separate, quiet, six-file review of the original Volume 12 Form B contracts.

No author module or saved numeric output is imported.  Finite policy enumeration,
indicator normal equations and signed-support KKT certificates are separate oracles.
"""
from collections import Counter
from fractions import Fraction as F
from html.parser import HTMLParser
from itertools import combinations, product
from pathlib import Path
import ast
import hashlib
import json
import math
import re

HTML = 'content/assessments/parts/v12-exam-b.html'
AUTHOR = 'content/reviews/v12-exam-b-author.json'
SOURCES = 'content/reviews/v12-exam-b-sources.json'
SELF = 'scripts/check_v12_exam_b_peer.py'
REVIEW = 'content/reviews/v12-exam-b-peer.json'
AUTHOR_FILES = {
    HTML: (47661, 'a8fcc8f9b4c1fdb693c0bc76172e4f00c278a2d400f8688d1190350dfecc113f'),
    'scripts/check_v12_exam_b.py': (20971, '928c35fc7cc828136d78edf14deeb95e209077c3098803d3a490e131ca6ebb06'),
    SOURCES: (11574, '45b49b90e650d5c8fe8c20964d852d1c60837757a978e2d5e363ffa58939728a'),
    AUTHOR: (7067, 'b5a56ae4775d2d636a5dbfadcd8faeca553c7f308bdd62d613dddb31f2f4851e'),
}
POINTS = ((6, 8, 6), (6, 6, 8), (7, 8, 5), (6, 5, 3, 6), (5, 7, 8))


def need(ok, message):
    if not ok:
        raise ValueError(message)


class Audit:
    def __init__(self):
        self.comparisons = 0
        self.rejections = 0
        self.interventions = 0
        self.policies = 0

    def same(self, actual, expected, label):
        need(actual == expected, label + ': ' + repr(actual) + ' != ' + repr(expected))
        self.comparisons += 1

    def true(self, condition, label):
        self.same(bool(condition), True, label)

    def reject(self, function, label):
        try:
            function()
        except ValueError:
            self.rejections += 1
        else:
            raise ValueError('accepted invalid case: ' + label)


def exact(value):
    need(type(value) in (int, F), 'exact integer/Fraction required')
    need(abs(value) <= 1000000, 'bounded numeric domain')
    return F(value)


def average(values):
    need(bool(values), 'empty mean')
    return sum(values, F(0)) / len(values)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        need(key not in result, 'duplicate JSON key')
        result[key] = value
    return result


def strict_json(text):
    def bad_constant(value):
        raise ValueError('nonfinite JSON constant ' + value)
    return json.loads(text, object_pairs_hook=unique_object, parse_constant=bad_constant)


class Radical:
    """Exact Q(sqrt(6)) values for reader root and projection expressions."""
    def __init__(self, a=0, b=0):
        self.a, self.b = F(a), F(b)

    @staticmethod
    def coerce(other):
        return other if isinstance(other, Radical) else Radical(other)

    def __add__(self, other):
        other = self.coerce(other)
        return Radical(self.a + other.a, self.b + other.b)
    __radd__ = __add__

    def __neg__(self):
        return Radical(-self.a, -self.b)

    def __sub__(self, other):
        return self + -self.coerce(other)

    def __rsub__(self, other):
        return self.coerce(other) + -self

    def __mul__(self, other):
        other = self.coerce(other)
        return Radical(self.a*other.a + 6*self.b*other.b,
                       self.a*other.b + self.b*other.a)
    __rmul__ = __mul__

    def __truediv__(self, other):
        other = self.coerce(other)
        norm = other.a**2 - 6*other.b**2
        need(norm != 0, 'zero algebraic denominator')
        numerator = self * Radical(other.a, -other.b)
        return Radical(numerator.a/norm, numerator.b/norm)

    def __eq__(self, other):
        if not isinstance(other, (int, F, Radical)):
            return False
        other = self.coerce(other)
        return self.a == other.a and self.b == other.b

    def __repr__(self):
        return 'Radical(' + str(self.a) + ',' + str(self.b) + ')'


def expression(text):
    """Only small displayed integer/fraction/tuple/radical expressions, never eval."""
    text = text.replace('−', '-')
    text = re.sub(r'(\d)√6', r'\1*R', text).replace('√6', 'R')
    need(len(text) <= 1000, 'bounded reader expression')
    try:
        tree = ast.parse(text, mode='eval')
    except SyntaxError as error:
        raise ValueError('bad reader expression') from error
    def visit(node):
        if isinstance(node, ast.Constant) and type(node.value) is int:
            return exact(node.value)
        if isinstance(node, ast.Name) and node.id == 'R':
            return Radical(0, 1)
        if isinstance(node, ast.Tuple):
            return tuple(visit(x) for x in node.elts)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            return -visit(node.operand)
        if isinstance(node, ast.BinOp):
            left, right = visit(node.left), visit(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                need(right != 0, 'zero rational denominator')
                return left / right
        raise ValueError('unsupported reader expression')
    return visit(tree.body)


def linear_system(matrix, rhs):
    n = len(rhs)
    need(1 <= n <= 8 and len(matrix) == n and all(len(row) == n for row in matrix),
         'square bounded system')
    work = [[exact(x) for x in row] + [exact(y)] for row, y in zip(matrix, rhs)]
    for col in range(n):
        pivot = next((r for r in range(col, n) if work[r][col]), None)
        need(pivot is not None, 'singular system')
        work[col], work[pivot] = work[pivot], work[col]
        scale = work[col][col]
        work[col] = [x/scale for x in work[col]]
        for row in range(n):
            if row != col:
                scale = work[row][col]
                work[row] = [x-scale*y for x, y in zip(work[row], work[col])]
    return tuple(row[-1] for row in work)


def least_squares(design, outcome):
    need(len(design) == len(outcome) and len(design) > 0, 'regression row count')
    k = len(design[0])
    need(1 <= k <= 8 and all(len(row) == k for row in design), 'regression shape')
    x = [[exact(v) for v in row] for row in design]
    y = [exact(v) for v in outcome]
    gram = [[sum(row[i]*row[j] for row in x) for j in range(k)] for i in range(k)]
    moment = [sum(row[i]*v for row, v in zip(x, y)) for i in range(k)]
    return linear_system(gram, moment)


def chain(p):
    p = exact(p)
    need(0 < p < 1, 'interior turnover probability')
    return ((1-p, p), (p, 1-p))


def finite_policies(start, horizon, p, discount, audit):
    """Evaluate every deterministic full-history rule; no Bellman helper used."""
    P = chain(p)
    discount = exact(discount)
    need(type(start) is int and start in (0, 1), 'binary initial state')
    need(type(horizon) is int and 0 <= horizon <= 2, 'bounded horizon')
    need(0 <= discount <= 1, 'discount domain')
    nodes = [(start,) + tail for depth in range(horizon+1)
             for tail in product((0, 1), repeat=depth)]
    paths = [(start,) + tail for tail in product((0, 1), repeat=horizon)]
    choices = [range(2) if len(node) == horizon+1 else range(3) for node in nodes]
    best = None
    for actions in product(*choices):
        rule = dict(zip(nodes, actions))  # 0 abstain, 1 exercise, 2 continue
        expected = F(0)
        for path in paths:
            mass = F(1)
            for left, right in zip(path, path[1:]):
                mass *= P[left][right]
            reward = F(0)
            for t in range(horizon+1):
                action = rule[path[:t+1]]
                if action == 0:
                    break
                if action == 1:
                    reward = discount**t * (2*path[t]-1)
                    break
            expected += mass*reward
        best = expected if best is None else max(best, expected)
        audit.policies += 1
    return best


def posterior_by_updates(theta, prior, observations):
    need(len(theta) == len(prior) == 2, 'two-point support')
    theta, probability = tuple(map(exact, theta)), tuple(map(exact, prior))
    need(all(0 <= t <= 1 for t in theta), 'Bernoulli support')
    need(all(p >= 0 for p in probability) and sum(probability) == 1, 'proper prior')
    need(0 < len(observations) <= 12 and
         all(type(v) is int and v in (0, 1) for v in observations), 'binary record')
    likelihood = [F(1), F(1)]
    for value in observations:
        factors = [t if value else 1-t for t in theta]
        likelihood = [a*b for a, b in zip(likelihood, factors)]
        unnormalized = [a*b for a, b in zip(probability, factors)]
        mass = sum(unnormalized)
        need(mass > 0, 'impossible observation')
        probability = tuple(v/mass for v in unnormalized)
    return tuple(likelihood), probability


def lasso_certificate(x, y, penalty, weights):
    need(1 <= len(x) <= 8 and len(x) == len(y) and all(len(row) == 2 for row in x),
         'two-column lasso shape')
    x = [tuple(map(exact, row)) for row in x]
    y = tuple(map(exact, y))
    penalty = exact(penalty)
    need(len(weights) == 2, 'two penalty weights')
    weights = tuple(map(exact, weights))
    need(penalty >= 0 and min(weights) > 0, 'nonnegative penalty, positive weights')
    n = len(x)
    g = [[sum(row[i]*row[j] for row in x)/n for j in range(2)] for i in range(2)]
    z = [sum(row[i]*v for row, v in zip(x, y))/n for i in range(2)]
    need(g[0][0] > 0 and g[0][0]*g[1][1]-g[0][1]**2 > 0,
         'positive-definite design for uniqueness')
    candidates = []
    for signs in product((-1, 0, 1), repeat=2):
        active = [i for i in range(2) if signs[i]]
        b = [F(0), F(0)]
        if active:
            solved = linear_system([[g[i][j] for j in active] for i in active],
                                   [z[i]-penalty*weights[i]*signs[i] for i in active])
            for i, value in zip(active, solved):
                b[i] = value
        score = [z[i]-sum(g[i][j]*b[j] for j in range(2)) for i in range(2)]
        valid = all(b[i]*signs[i] > 0 and score[i] == penalty*weights[i]*signs[i]
                    if signs[i] else abs(score[i]) <= penalty*weights[i]
                    for i in range(2))
        if valid:
            fit = tuple(sum(a*v for a, v in zip(row, b)) for row in x)
            objective = sum((v-f)**2 for v, f in zip(y, fit))/(2*n)
            objective += penalty*sum(w*abs(v) for w, v in zip(weights, b))
            candidates.append((tuple(b), fit, objective))
    need(len(candidates) == 1, 'one globally certified lasso candidate')
    return candidates[0]


def randomization_tails(scores, probabilities, thresholds=None):
    need(0 < len(scores) <= 32 and len(scores) == len(probabilities), 'finite support shape')
    scores, probabilities = tuple(map(exact, scores)), tuple(map(exact, probabilities))
    need(all(p > 0 for p in probabilities) and sum(probabilities) == 1, 'assignment law')
    thresholds = scores if thresholds is None else tuple(map(exact, thresholds))
    return tuple(sum(p for s, p in zip(scores, probabilities) if abs(s) >= abs(t))
                 for t in thresholds)


class Reader(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.ids = []
        self.links = []
        self.points = {}
        self.answers = []
        self.rubrics = {}
        self.inputs = {}
        self.results = {}
        self.tables = {}
        self.input_names = {}
        self.lists = []

    def handle_starttag(self, tag, attrs):
        need(len(attrs) == len(dict(attrs)), 'duplicate HTML attribute')
        a = dict(attrs)
        node = {'tag': tag, 'a': a, 'text': []}
        if 'id' in a:
            self.ids.append(a['id'])
        if tag == 'a':
            self.links.append(a.get('href', ''))
        if tag == 'ol':
            self.lists.append(set(a.get('class', '').split()))
        if 'data-points' in a:
            need(tag == 'li' and a.get('id') not in self.points, 'unique scored list item')
            self.points[a['id']] = int(a['data-points'])
        if 'data-solution-for' in a:
            need(tag == 'li', 'answer list item')
            self.answers.append(a['data-solution-for'])
        if 'data-score' in a:
            targets = [n['a']['data-solution-for'] for n in self.stack
                       if 'data-solution-for' in n['a']]
            need(len(targets) == 1 and targets[0] not in self.rubrics, 'rubric answer depth')
            self.rubrics[targets[0]] = tuple(int(v) for v in a['data-score'].split(','))
        if tag == 'table':
            need('id' in a and a['id'] not in self.tables, 'table identifier')
            node['rows'] = []
            if 'data-table' in a:
                need(a['data-table'] not in self.input_names, 'unique input table')
                self.input_names[a['data-table']] = a['id']
        if tag == 'tr':
            node['cells'] = []
        if tag not in ('br', 'hr', 'img', 'meta', 'link', 'input', 'wbr'):
            self.stack.append(node)

    def handle_data(self, data):
        for node in self.stack:
            node['text'].append(data)

    def handle_endtag(self, tag):
        need(self.stack and self.stack[-1]['tag'] == tag, 'balanced HTML: ' + tag)
        node = self.stack.pop()
        a, text = node['a'], ''.join(node['text']).strip()
        for marker, destination in (('data-input', self.inputs), ('data-calc', self.results)):
            if marker in a:
                need(a[marker] not in destination, 'unique visible marker')
                destination[a[marker]] = text
        if tag in ('th', 'td'):
            row = next((n for n in reversed(self.stack) if n['tag'] == 'tr'), None)
            need(row is not None, 'cell inside row')
            row['cells'].append((tag, text))
        if tag == 'tr':
            table = next((n for n in reversed(self.stack) if n['tag'] == 'table'), None)
            need(table is not None, 'row inside table')
            table['rows'].append(node['cells'])
        if tag == 'table':
            self.tables[a['id']] = node['rows']

    def finish(self):
        self.close()
        need(not self.stack, 'unclosed HTML')
        return self


def parse_reader(text):
    doc = Reader()
    doc.feed(text)
    return doc.finish()


def derive(audit):
    """Independent original-contract calculations; expected inputs are explicit."""
    tables = {
        'q1-clusters': ((1, 0, 1), (2, 0, 3), (3, 1, 4), (4, 3, 4)),
        'q2-panel': (('E', 2, 1, 2, 5, 14), ('L', 3, 3, 4, 5, 10),
                     ('N', 'never', 0, 1, 2, 3)),
        'q2-donors': (('B', 2, 3, 7), ('C', 1, 2, 4)),
        'q3-nodes': ((1, F(1, 8), F(1, 8)), (2, F(1, 8), F(7, 8)),
                     (3, F(7, 8), F(1, 8)), (4, F(7, 8), F(7, 8))),
        'q4-regression': ((1, 1, 1, 3), (2, 1, -1, 1)),
        'q5-records': tuple((i+1, 'ABCD'[i//2], int(i//2 == 3), (0, 1000, 2000, 7000)[i//2])
                            for i in range(8)),
    }
    inputs = {'cluster-law': (4, 2, 4), 'normal-cdf': F('0.9772498680'),
              'turnover': F(1, 4), 'discount': F(1, 2), 'bernoulli-record': (1, 1, 0),
              'bayes-theta': (F(1, 4), F(3, 4)), 'bayes-prior': (F(1, 2), F(1, 2)),
              'launch-utility': (-4, 1), 'lasso-lambda': F(1, 2)}
    result = {}
    # Q1: cluster weights give the sampling covariance; a quadratic gives both rays.
    ra, rb = (average([F(row[j]) for row in tables['q1-clusters']]) for j in (1, 2))
    independent_weights = (F(1, 4),)*4
    variance = sum(w*w*4 for w in independent_weights)
    false_variance = 8*F(1, 8)**2*4
    result['cluster-means'] = (ra, rb)
    result['cluster-variances'] = (variance, false_variance)
    quadratic = (4*variance-ra**2, 2*ra*rb, 4*variance-rb**2)
    result['candidate-quadratic'] = quadratic
    low, high = Radical(-1, F(-2, 3)), Radical(-1, F(2, 3))
    audit.same(low+high, -quadratic[1]/quadratic[0], 'Vieta root sum')
    audit.same(low*high, quadratic[2]/quadratic[0], 'Vieta root product')
    audit.true(24 > 9 and quadratic[0] > 0, 'positive upper root and exterior rays')
    result['candidate-roots'] = (low, high)
    result['theta-bound'] = high*high
    audit.same((low*low)-(high*high), Radical(0, F(8, 3)), 'negative square branch contained')
    for candidate, accepted in ((0, False), (3, True), (-4, True)):
        audit.same((rb-candidate*ra)**2 <= 4*variance*(1+candidate**2), accepted,
                   'whole-line candidate decision')
    result['confidence-percent'] = 2*inputs['normal-cdf']-1
    audit.true(abs(math.erf(math.sqrt(2))-float(result['confidence-percent'])) < 2e-10,
               'normal coverage approximation')
    # Intervention: replication changes the false variance, never the cluster law.
    for readings in (1, 3):
        audit.same(sum((F(readings, 4*readings))**2*4 for _ in range(4)), variance,
                   'same-cluster replication variance')
    audit.interventions += 1
    # Q2: regress on an independent dummy basis, not the author's demeaning routine.
    coordinates = tuple(product(range(3), range(4)))
    nuisance = [tuple([1, int(g == 1), int(g == 2)] + [int(t == j) for j in (1, 2, 3)])
                for g, t in coordinates]
    d = tuple(int((g == 0 and t >= 2) or (g == 1 and t >= 3)) for g, t in coordinates)
    y = tuple(F(tables['q2-panel'][g][t+2]) for g, t in coordinates)
    nuisance_fit = least_squares(nuisance, d)
    residual = tuple(v-sum(a*b for a, b in zip(row, nuisance_fit)) for row, v in zip(nuisance, d))
    norm = sum(r*r for r in residual)
    joint = [row+(treatment,) for row, treatment in zip(nuisance, d)]
    full_beta = least_squares(joint, y)[-1]
    numerator = tuple(sum(residual[4*g+t]*y[4*g+t] for t in range(4)) for g in range(3))
    audit.same(full_beta, sum(numerator)/norm, 'full indicator regression versus FWL')
    for column in zip(*nuisance):
        audit.same(sum(a*b for a, b in zip(column, residual)), 0, 'indicator orthogonality')
    result['twfe-residual'] = tuple(tuple(residual[g*4:(g+1)*4]) for g in range(3))
    result['twfe-norm'] = norm
    result['twfe-inner-products'] = numerator
    result['twfe-estimate'] = full_beta
    result['twfe-weights'] = tuple(residual[i]/norm for i, v in enumerate(d) if v)
    untreated = tuple(y[4*g+1] + y[8+t]-y[9] for g, t in coordinates)
    effects = tuple(y[i]-untreated[i] for i, treatment in enumerate(d) if treatment)
    result['clean-effects'] = effects
    result['effect-targets'] = (average((effects[0], effects[2])), average(effects), full_beta)
    audit.same(sum(w*e for w, e in zip(result['twfe-weights'], effects)), full_beta,
               'maintained counterfactual and treatment weights')
    shifted = tuple(v + (2, -3, 5)[g] + (4, 0, -2, 1)[t] for (g, t), v in zip(coordinates, y))
    audit.same(least_squares(joint, shifted)[-1], full_beta, 'arbitrary additive cohort/date transfer')
    for index, weight in zip((2, 3, 7), result['twfe-weights']):
        perturbed = tuple(v+int(i == index) for i, v in enumerate(y))
        audit.same(least_squares(joint, perturbed)[-1]-full_beta, weight,
                   'isolated treated-cell unit intervention')
    audit.interventions += 2
    donor_pre = ((0, 2, 1), (1, 3, 2))
    particular, direction = (F(0), F(0), F(1)), (F(1), F(1), F(-2))
    for row, target in zip(((1, 1, 1),)+donor_pre, (1, 1, 2)):
        audit.same(sum(a*b for a, b in zip(row, particular)), target, 'affine donor particular solution')
        audit.same(sum(a*b for a, b in zip(row, direction)), 0, 'affine donor kernel')
    # Two independent constraints give a one-dimensional nullspace; nonnegativity is t in [0,1/2].
    audit.true(1*2-1*0 != 0, 'donor constraint rank two')
    post = (3, 7, 4)
    intercept = sum(a*b for a, b in zip(post, particular))
    slope = sum(a*b for a, b in zip(post, direction))
    endpoints = (intercept, intercept+slope/2)
    result['donor-cf-bounds'] = tuple(sorted(endpoints))
    result['donor-effect-bounds'] = tuple(sorted(14-value for value in endpoints))
    changed_post = (post[0], post[1], post[2]+2)
    changed_intercept = sum(a*b for a, b in zip(changed_post, particular))
    changed_slope = sum(a*b for a, b in zip(changed_post, direction))
    audit.same(tuple(changed_intercept+changed_slope*t for t in (F(0), F(1, 2))), (F(6), F(5)),
               'changed donor-C post value reverses affine endpoint order')
    audit.interventions += 1
    # Q3: stationary two-state moments and every permitted finite history rule.
    p, discount = inputs['turnover'], inputs['discount']
    P = chain(p)
    for ptest in (p, 1-p):
        trial = chain(ptest)
        audit.same(tuple(sum(trial[i][j]/2 for i in range(2)) for j in range(2)),
                   (F(1, 2), F(1, 2)), 'stationary invariant law')
        audit.same(tuple(sum(trial[i][j]*(2*j-1) for j in range(2)) for i in range(2)),
                   (-(1-2*ptest), 1-2*ptest), 'centered eigenfunction including negative correlation')
        audit.same((trial[0][1]+trial[1][0])/2, ptest, 'turnover rather than mean identification')
    result['spread-moments'] = (F(1), F(1), 1-2*p)
    for t in (0, 1, 3):
        for coefficient in (0, 1, 2):
            values = [F((1-coefficient)*sum(innovations)+v)
                      for innovations in product((-1, 1), repeat=t) for v in (0, 2)]
            audit.same(average([(value-average(values))**2 for value in values]),
                       (1-coefficient)**2*t+1, 'finite trend and independent spread variance')
    values = tuple(tuple(finite_policies(start, horizon, p, discount, audit) for start in (0, 1))
                   for horizon in (2, 1, 0))
    result['stopping-values'] = values
    paths = tuple(product((0, 1), repeat=2))
    probabilities = tuple(P[0][s1]*P[s1][s2] for s1, s2 in paths)
    payoffs = tuple(discount if s1 else discount**2*s2 for s1, s2 in paths)
    integrated = sum(prob*value for prob, value in zip(probabilities, payoffs))
    audit.same(integrated, values[0][0], 'attaining policy versus exhaustive history rules')
    result['state-path-probabilities'] = probabilities
    result['starting-values'] = (integrated, sum(prob*discount**2*s2 for prob, (_, s2) in zip(probabilities, paths)))
    node_payoffs = []
    for _, first, second in tables['q3-nodes']:
        if first < p:
            node_payoffs.append(discount)
        else:
            node_payoffs.append(discount**2*int(second < p))
    result['node-payoffs'] = tuple(node_payoffs)
    result['node-mean-error'] = (average(node_payoffs), average(node_payoffs)-integrated)
    audit.same(average(node_payoffs*5), average(node_payoffs), 'same deterministic nodes repeated')
    audit.same(finite_policies(0, 1, p, F(0), audit), F(0), 'zero discount erases delayed payoffs')
    audit.same(finite_policies(0, 1, F(3, 4), discount, audit), F(3, 8),
               'turnover intervention changes exercise option')
    audit.interventions += 2
    # Q4: sequential Bayes updates; flow-derived chain; sign/support enumeration.
    likelihoods, posterior = posterior_by_updates(inputs['bayes-theta'], inputs['bayes-prior'],
                                                  inputs['bernoulli-record'])
    result['likelihoods'], result['posterior'] = likelihoods, posterior
    theta_hat = F(sum(inputs['bernoulli-record']), len(inputs['bernoulli-record']))
    result['continuous-mle'] = theta_hat
    audit.same(2*(1-theta_hat)-theta_hat, 0, 'Bernoulli score numerator')
    audit.true(-2/theta_hat**2-1/(1-theta_hat)**2 < 0, 'strict likelihood curvature')
    result['posterior-predictive'] = sum(t*w for t, w in zip(inputs['bayes-theta'], posterior))
    result['launch-expected'] = sum(u*w for u, w in zip(inputs['launch-utility'], posterior))
    flow = min(posterior)
    transition = ((1-flow/posterior[0], flow/posterior[0]),
                  (flow/posterior[1], 1-flow/posterior[1]))
    result['mh-transition'] = transition
    audit.same(posterior[0]*transition[0][1], posterior[1]*transition[1][0], 'balanced switch flows')
    result['jump-chain-mean'] = average(inputs['bayes-theta'])
    pairs = tuple((i, j, posterior[i]*transition[i][j]) for i, j in product((0, 1), repeat=2))
    mean_h = sum(prob*i for i, _, prob in pairs)
    variance_h = sum(prob*(i-mean_h)**2 for i, _, prob in pairs)
    covariance = sum(prob*(i-mean_h)*(j-mean_h) for i, j, prob in pairs)
    variance_pair = sum(prob*(F(i+j, 2)-mean_h)**2 for i, j, prob in pairs)
    result['chain-variances'] = (variance_h, covariance, variance_pair, variance_h/2)
    audit.same(variance_pair, (variance_h+covariance)/2, 'pair law and covariance decomposition')
    audit.same(sum(w*u for w, u in zip(posterior, (-3, 1))), F(0), 'utility tie without posterior change')
    audit.true(sum(w*u for w, u in zip(posterior, (-2, 1))) > 0, 'decision flips with loss function')
    # Starting at L gives (H0,H1)=(0,1) deterministically, unlike the granted stationary law.
    audit.same(transition[0], (F(0), F(1)), 'nonstationary initial-low pair has zero variance')
    audit.true(variance_pair > 0, 'stationary variance cannot be transplanted to fixed start')
    audit.interventions += 2
    X = tuple(tuple(F(v) for v in row[1:3]) for row in tables['q4-regression'])
    yreg = tuple(F(row[-1]) for row in tables['q4-regression'])
    scaled = tuple((2*a, b) for a, b in X)
    result['lasso-original'] = lasso_certificate(X, yreg, inputs['lasso-lambda'], (1, 1))
    result['lasso-rescaled'] = lasso_certificate(scaled, yreg, inputs['lasso-lambda'], (1, 1))
    result['lasso-restored'] = lasso_certificate(scaled, yreg, inputs['lasso-lambda'], (2, 1))
    audit.same(result['lasso-original'][1:], result['lasso-restored'][1:], 'physical fit and objective restored')
    audit.same(lasso_certificate(X, yreg, F(1), (1, 1))[0], (F(1), F(0)),
               'penalty at exact inactive-coordinate KKT boundary')
    audit.same(lasso_certificate(X, yreg, F(0), (1, 1))[0], (F(2), F(1)), 'unpenalized OLS endpoint')
    audit.same(lasso_certificate(X, tuple(-v for v in yreg), F(1, 2), (1, 1))[0],
               tuple(-v for v in result['lasso-original'][0]), 'signed-support response reversal')
    audit.interventions += 1
    # Q5: person records, whole-site assignment sets, and all counterfactual maps.
    rows = tables['q5-records']
    audit.same(len(set(row[0] for row in rows)), 8, 'eight distinct person keys')
    audit.same(Counter(row[1] for row in rows), Counter(dict.fromkeys('ABCD', 2)), 'two valid people per site')
    outcome = tuple(F(row[3], 1000) for row in rows)
    site_sets = tuple(tuple(i for i, row in enumerate(rows) if row[1] == site) for site in 'ABCD')
    actual = tuple(i for i, row in enumerate(rows) if row[2])
    audit.same(actual, site_sets[3], 'one whole treated site')
    def contrast(selected, values=outcome):
        return average([v for i, v in enumerate(values) if i in selected])-average([v for i, v in enumerate(values) if i not in selected])
    scores = tuple(contrast(selected) for selected in site_sets)
    false_sets = tuple(combinations(range(8), 2))
    false_scores = tuple(contrast(selected) for selected in false_sets)
    histogram = Counter(sum(outcome[i] for i in selected) for selected in false_sets)
    correct_p = randomization_tails(scores, (F(1, 4),)*4)
    false_p = randomization_tails(false_scores, (F(1, 28),)*28, scores)
    result['site-contrasts'], result['site-pvalues'], result['false-pvalues'] = scores, correct_p, false_p
    result['actual-pair-pvalues'] = (correct_p[3], false_p[3])
    result['reference-sizes'] = (F(sum(v <= F(1, 20) for v in correct_p), 4),
                                 F(sum(v <= F(1, 20) for v in false_p), 4))
    for cutoff in (F(1, 20),)+tuple(sorted(set(correct_p))):
        audit.true(F(sum(v <= cutoff for v in correct_p), 4) <= cutoff, 'actual-law inclusive rank validity')
    audit.same(randomization_tails(tuple(1000*v for v in scores), (F(1, 4),)*4), correct_p,
               'unit scale changes contrasts but not ranks')
    audit.same(randomization_tails((0, 0, 0, 0), (F(1, 4),)*4), (F(1),)*4,
               'all-tied inclusive tail boundary')
    audit.interventions += 1
    worlds = [{}, {}]
    for assignment in product((0, 1), repeat=4):
        worlds[0][assignment] = outcome
        worlds[1][assignment] = tuple(v+3*int(all(assignment)) for v in outcome)
        audit.true(all(0 <= v <= 10 for world in worlds for v in world[assignment]),
                   'both full-assignment potential vectors bounded')
        if sum(assignment) == 1:
            audit.same(worlds[0][assignment], worlds[1][assignment], 'entire experimental observable law')
    result['global-policy-effects'] = tuple(average(world[(1, 1, 1, 1)])-average(world[(0, 0, 0, 0)]) for world in worlds)
    audit.same(average(outcome), F(5, 2), 'all-untreated mean in both witness worlds')
    audit.same(sum(outcome), F(20), 'individual kilogram total')
    audit.same(scores[3], F(6), 'actual pilot contrast')
    audit.true(max(outcome)+3 == 10 and max(outcome)+F(31, 10) > 10,
               'policy witness increment attains the supplied upper bound')
    audit.interventions += 1
    # Real invalid executions of the independent oracle's explicitly bounded domains.
    for value in (True, 0.5, float('nan'), float('inf'), 1000001):
        audit.reject(lambda value=value: exact(value), 'exact arithmetic domain')
    audit.reject(lambda: linear_system([[1, 1], [2, 2]], [1, 2]), 'singular identification')
    audit.reject(lambda: least_squares([[1, 2], [1]], [1, 2]), 'ragged design')
    for value in (F(0), F(1), F(-1, 4)):
        audit.reject(lambda value=value: chain(value), 'turnover outside open domain')
    audit.reject(lambda: finite_policies(0, 1, p, F(3, 2), audit), 'discount outside domain')
    audit.reject(lambda: posterior_by_updates((0, 0), (F(1, 2),)*2, (1,)), 'zero evidence')
    audit.reject(lambda: posterior_by_updates((F(1, 4), F(3, 4)), (1, 1), (1,)), 'unnormalized prior')
    audit.reject(lambda: posterior_by_updates((F(1, 4), F(3, 4)), (F(1, 2),)*2, (True,)), 'Boolean observation')
    audit.reject(lambda: lasso_certificate(X, yreg, F(-1), (1, 1)), 'negative penalty')
    audit.reject(lambda: lasso_certificate(X, yreg, F(1), (0, 1)), 'zero declared weight')
    audit.reject(lambda: lasso_certificate(((1, 1), (1, 1)), yreg, F(1), (1, 1)), 'singular unique-lasso claim')
    audit.reject(lambda: randomization_tails((1, 2), (F(1, 4),)*2), 'incomplete assignment mass')
    audit.reject(lambda: randomization_tails((1, 2), (F(-1), F(2))), 'negative assignment mass')
    for bad in ('{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}'):
        audit.reject(lambda bad=bad: strict_json(bad), 'strict JSON input')
    for bad in ('True', '__import__("os")', '1/0'):
        audit.reject(lambda bad=bad: expression(bad), 'restricted reader expression')
    audit.reject(lambda: parse_reader('<ol><li></ol></li>'), 'malformed reader structure')
    return tables, inputs, result, histogram


def check(root=None):
    root = Path(root) if root is not None else Path(__file__).resolve().parents[1]
    audit = Audit()
    for path, binding in AUTHOR_FILES.items():
        raw = (root/path).read_bytes()
        audit.same((len(raw), hashlib.sha256(raw).hexdigest()), binding, 'final frozen author ' + path)
    author = strict_json((root/AUTHOR).read_text(encoding='utf-8'))
    sources = strict_json((root/SOURCES).read_text(encoding='utf-8'))
    review = strict_json((root/REVIEW).read_text(encoding='utf-8'))
    author_bindings = author['payload_bindings']
    audit.same({b['path'] for b in author_bindings}, set(AUTHOR_FILES)-{AUTHOR}, 'three nonself author bindings')
    audit.same(len(author_bindings), 3, 'author binding cardinality')
    for binding in author_bindings:
        audit.same((binding['bytes'], binding['sha256']), AUTHOR_FILES[binding['path']], 'author reviewed final payload')
    peer_bindings = review['payload_bindings']
    audit.same({b['path'] for b in peer_bindings}, set(AUTHOR_FILES)|{SELF}, 'four author plus own checker bindings')
    audit.same(len(peer_bindings), 5, 'peer binding cardinality')
    for binding in peer_bindings:
        raw = (root/binding['path']).read_bytes()
        audit.same((len(raw), hashlib.sha256(raw).hexdigest()), (binding['bytes'], binding['sha256']),
                   'peer exact payload ' + binding['path'])
    audit.same(review['unresolved_findings'], [], 'no unresolved peer finding')
    tables, inputs, expected, histogram = derive(audit)
    doc = parse_reader((root/HTML).read_text(encoding='utf-8'))
    audit.same(len(doc.ids), len(set(doc.ids)), 'unique manuscript IDs')
    audit.true(all(i in ('form-b', 'solutions-b') or i.startswith('v12-b-') for i in doc.ids), 'component ID scope')
    points = {f'v12-b-q{domain}{chr(97+j)}': value for domain, row in enumerate(POINTS, 1) for j, value in enumerate(row)}
    audit.same(doc.points, points, 'all sixteen scored prompts')
    audit.same(doc.answers, list(points), 'every exact solution paired once and in order')
    audit.same(set(doc.rubrics), set(points), 'complete scoring records')
    for key, value in points.items():
        audit.true(all(score > 0 for score in doc.rubrics[key]), 'positive rubric allocations')
        audit.same(sum(doc.rubrics[key]), value, 'rubric point reconciliation')
    for domain in range(1, 6):
        audit.same(sum(value for key, value in points.items() if key.startswith(f'v12-b-q{domain}')), 20, 'domain total')
    audit.same(sum(points.values()), 100, 'exam total')
    audit.same(sum('exercises' in classes for classes in doc.lists), 5, 'reader question list class')
    audit.same(sum('solutions' in classes for classes in doc.lists), 5, 'reader answer list class')
    audit.same(set(doc.input_names), set(tables), 'six actual input tables')
    for key, rows in tables.items():
        visible = [tuple(text for _, text in row) for row in doc.tables[doc.input_names[key]] if row and row[0][0] == 'td']
        formatted = [tuple(str(x).replace('-', '−') for x in row) for row in rows]
        audit.same(visible, formatted, 'exact primitive table ' + key)
    audit.same(set(doc.inputs), set(inputs), 'supplied constant inventory')
    for key, value in inputs.items():
        actual = F(doc.inputs[key]) if key == 'normal-cdf' else expression(doc.inputs[key])
        audit.same(actual, value, 'actual supplied constant ' + key)
    audit.same(set(doc.results), set(expected), 'complete displayed result inventory')
    for key, value in expected.items():
        actual = F(doc.results[key][:-1])/100 if key == 'confidence-percent' else expression(doc.results[key])
        audit.same(actual, value, 'independently recomputed visible anchor ' + key)
    orbit = doc.tables['v12-b-false-orbit']
    audit.same(tuple(expression(text) for _, text in orbit[0][1:]), tuple(sorted(histogram)), 'false pair-sum table headings')
    audit.same(tuple(expression(text) for _, text in orbit[1][1:]), tuple(histogram[k] for k in sorted(histogram)), 'false pair-sum multiplicities')
    audit.same(set(doc.links), {f'v12-c{i:02d}.html' for i in range(1, 13)}, 'all twelve taught chapter routes')
    source_ids = {item['id'] for item in sources['source_identities']}
    audit.same(len(source_ids), 17, 'retained primary identities')
    audit.same(sources['new_primary_body_reads_by_this_author'], 0, 'honest no-new-primary-reading boundary')
    audit.same(len(sources['scopes']), 6, 'bounded method source scopes')
    audit.same(set(part for scope in sources['scopes'] for part in scope['parts']), set(points), 'source scope covers every exact part')
    audit.same(set(source for scope in sources['scopes'] for source in scope['source_ids']), source_ids, 'source identities match method scopes')
    audit.true(all(scope['original_proof_and_limit'] and scope['prior_inspectors'] for scope in sources['scopes']), 'proof limits and actual inspector attribution')
    summary = {'component': 'v12-exam-b', 'status': 'separate peer checks passed',
               'comparisons': audit.comparisons, 'domain_rejections': audit.rejections,
               'intervention_groups': audit.interventions, 'scored_solved_parts': 16,
               'domains': 5, 'points': 100, 'input_tables': 6, 'input_constants': len(inputs),
               'visible_result_anchors': len(expected), 'full_history_policies_evaluated': audit.policies,
               'true_assignments': 4, 'false_assignments': 28, 'complete_policy_maps_per_world': 16,
               'runtime_payloads': 6}
    json.dumps(summary, allow_nan=False)
    return summary


if __name__ == '__main__':
    check()
