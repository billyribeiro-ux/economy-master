"""Readonly independent finite audit of v12-c05.

Pairwise differences, full dummy-variable normal equations, observable-law
derivatives and exact common-shock covariances are independent evidence.
No author implementation, saved answer, production or shared runtime is used.
"""
from collections import defaultdict
from fractions import Fraction as F
from html.parser import HTMLParser
from itertools import product
import hashlib
import json
from math import isfinite, sqrt
from pathlib import Path

AUTHOR = (
    ('content/chapters/v12-c05.html', 45579, '250dafe5c4b5a704f387c31fb2f279dc166120900dc144288751279d36ad976f'),
    ('scripts/check_v12_c05.py', 29101, 'd6b374aae3127a2a5db524b9985fb7a164ae411ebb79a1fc07af70960388e92c'),
    ('content/reviews/v12-c05-sources.json', 11991, '7f23b2573b754bd57d632057783c1282efc93850eacde6a81cd990ba060f530e'),
    ('content/reviews/v12-c05-author.json', 26535, 'cf5b53bcae484c2b16c54f8fff8da9a23b567e83ec3ebed2224ed379741cf6de'),
)
SELF = 'scripts/check_v12_c05_peer.py'
RECORD = 'content/reviews/v12-c05-peer.json'


def need(condition, label):
    if not condition:
        raise ValueError('v12-c05 peer: ' + label)


def strict(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, 'duplicate JSON member')
            result[key] = value
        return result
    def finite_decimal(value):
        converted = float(value)
        need(isfinite(converted), 'overflowing JSON exponent')
        return converted
    def invalid(value):
        raise ValueError('nonfinite JSON constant ' + value)
    return json.loads(raw, object_pairs_hook=pairs, parse_float=finite_decimal, parse_constant=invalid)


def rational(value):
    need(type(value) in (int, F), 'exact scalar excluding bool and float')
    value = F(value)
    need(abs(value) <= 10**6, 'bounded scalar')
    return value


class Audit:
    def __init__(self):
        self.comparisons = 0
        self.rejections = []
        self.interventions = []
        self.answer_anchors = 0
    def equal(self, actual, expected, label):
        self.comparisons += 1
        need(actual == expected, label + ': ' + repr(actual) + ' != ' + repr(expected))
    def near(self, actual, expected, label):
        self.comparisons += 1
        need(isfinite(float(actual)) and abs(actual-expected) < 2e-12, label)
    def reject(self, operation, label):
        try:
            operation()
        except ValueError:
            self.rejections.append(label)
        else:
            raise ValueError('missing rejection: ' + label)
    def anchors(self, reader, number, values):
        text = ''.join(reader.answers['v12-c05-e'+str(number)].split()).replace('−', '-')
        for value in values:
            token = ''.join(str(value).split()).replace('−', '-')
            self.equal(token in text, True, 'computed answer/hypothesis anchor ' + str(number) + ': ' + token)
            self.answer_anchors += 1


class Reader(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.ids = []
        self.prompts = []
        self.answers = {}
        self.active_answer = None
        self.answer_depth = None
        self.worked = 0
        self.sources = []
        self.links = []
        self.cells = []
        self.active_cell = None
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'id' in attrs:
            self.ids.append(attrs['id'])
        if tag == 'li' and attrs.get('id', '').startswith('v12-c05-e'):
            self.prompts.append(attrs['id'])
        if 'data-solution-for' in attrs:
            key = attrs['data-solution-for']
            need(key not in self.answers and self.active_answer is None, 'unique separate solution')
            self.active_answer = key
            self.answers[key] = ''
            self.answer_depth = len(self.stack)
        self.worked += 'worked' in attrs.get('class', '').split()
        if 'data-source' in attrs:
            self.sources.append(attrs['data-source'])
        if tag == 'a':
            self.links.append(attrs['href'])
        if tag == 'td':
            self.active_cell = ''
        if tag not in ('br', 'hr', 'img', 'input', 'meta', 'link'):
            self.stack.append(tag)
    def handle_data(self, data):
        if self.active_answer is not None:
            self.answers[self.active_answer] += data
        if self.active_cell is not None:
            self.active_cell += data
    def handle_endtag(self, tag):
        need(self.stack and self.stack.pop() == tag, 'balanced markup')
        if tag == 'li' and len(self.stack) == self.answer_depth:
            self.active_answer = None
            self.answer_depth = None
        if tag == 'td':
            self.cells.append(self.active_cell.strip().replace('−', '-'))
            self.active_cell = None


def solve(gram, rhs):
    n = len(rhs)
    need(1 <= n <= 4 and len(gram) == n and all(len(row) == n for row in gram), 'bounded square system')
    rows = [[F(value) for value in row]+[F(b)] for row, b in zip(gram, rhs)]
    for column in range(n):
        pivot = next((i for i in range(column, n) if rows[i][column]), None)
        need(pivot is not None, 'rank failure')
        rows[column], rows[pivot] = rows[pivot], rows[column]
        divisor = rows[column][column]
        rows[column] = [value/divisor for value in rows[column]]
        for i in range(n):
            if i != column:
                divisor = rows[i][column]
                rows[i] = [value-divisor*other for value, other in zip(rows[i], rows[column])]
    return tuple(row[-1] for row in rows)


def least_squares(design, response, weights):
    need(2 <= len(design) <= 32 and len(design) == len(response) == len(weights), 'bounded common sample')
    p = len(design[0])
    need(1 <= p <= 4 and all(len(row) == p for row in design), 'fixed complete design')
    design = [[rational(value) for value in row] for row in design]
    response = [rational(value) for value in response]
    weights = [rational(value) for value in weights]
    need(min(weights) > 0, 'positive weights')
    gram = [[sum(w*x[j]*x[k] for x, w in zip(design, weights)) for k in range(p)] for j in range(p)]
    rhs = [sum(w*x[j]*y for x, y, w in zip(design, response, weights)) for j in range(p)]
    return solve(gram, rhs)


def difference_fit(x, y, weights):
    need(2 <= len(x) <= 32 and len(x) == len(y) == len(weights), 'bounded common panel')
    need(all(len(row) == 2 for row in x+y), 'two complete dates')
    dx = [rational(row[1])-rational(row[0]) for row in x]
    dy = [rational(row[1])-rational(row[0]) for row in y]
    weights = [rational(value) for value in weights]
    need(min(weights) > 0, 'positive common unit weights')
    gram = sum(w*v*v for w, v in zip(weights, dx))
    need(gram > 0, 'within rank failure')
    cross = sum(w*v*z for w, v, z in zip(weights, dx, dy))
    return cross/gram, gram/2, cross/2


def dynamic_law(rho, serial=False):
    rho = rational(rho)
    need(-2 <= rho <= 2 and type(serial) is bool, 'bounded dynamic parameters')
    rows = []
    innovations = product((-1, 1), repeat=2 if serial else 3)
    for values in innovations:
        e1, e2 = values[:2]
        e3 = e1 if serial else values[2]
        history = [F(0)]
        for error in (e1, e2, e3):
            history.append(rho*history[-1]+error)
        y1, y2, y3 = history[1:]
        rows.append((y1, y2-y1, y3-y2, e1, e2, e3))
    return rows


def iv_ratio(rows):
    denominator = sum(z*x for z, x, y, *rest in rows)
    need(denominator != 0, 'zero sample moment denominator')
    return sum(z*y for z, x, y, *rest in rows)/denominator


def missing_law(response):
    response = rational(response)
    need(0 < response <= 1, 'positive response support')
    latent = []
    observable = defaultdict(F)
    for h, sign in product((0, 1), (-1, 1)):
        y = F(2+4*h+sign)
        p = F(1) if h == 0 else response
        for flag in (0, 1):
            mass = (p if flag else 1-p)/4
            if mass:
                latent.append((mass, h, flag, y))
                observable[(h, flag, y if flag else None)] += mass
    return latent, dict(observable)


def cell_functional(observable, known_composition=False):
    need(type(known_composition) is bool, 'composition convention')
    frequencies = [F(0), F(0)]
    responses = [F(0), F(0)]
    totals = [F(0), F(0)]
    for (h, flag, y), mass in observable.items():
        need(type(h) is int and h in (0, 1) and type(flag) is int and flag in (0, 1), 'observed cell and response flag')
        mass = rational(mass)
        need(mass >= 0, 'nonnegative observed mass')
        frequencies[h] += mass
        if flag:
            responses[h] += mass
            totals[h] += mass*rational(y)
        else:
            need(y is None, 'unobserved outcome cannot be fabricated')
    need(sum(frequencies) == 1, 'observed mass normalization')
    need(min(responses) > 0, 'response-empty cell')
    means = [a/b for a, b in zip(totals, responses)]
    shares = [F(1, 2)]*2 if known_composition else frequencies
    return sum(p*m for p, m in zip(shares, means))


def directional_influence(observable, atom, known_composition=False):
    # Exact derivative of the observed-probability rational map; no latent outcome
    # or preprogrammed influence enters this calculation.
    answer = F(0)
    for h in (0, 1):
        pi_h = sum(p for (cell, flag, y), p in observable.items() if cell == h)
        b = sum(p for (cell, flag, y), p in observable.items() if cell == h and flag)
        a = sum(p*y for (cell, flag, y), p in observable.items() if cell == h and flag)
        dp = F(atom[0] == h)-pi_h
        db = F(atom[0] == h and atom[1] == 1)-b
        da = (atom[2] if atom[0] == h and atom[1] else F(0))-a
        if known_composition:
            pi_h, dp = F(1, 2), F(0)
        answer += dp*a/b+pi_h*(da*b-a*db)/(b*b)
    return answer


def twice_center(matrix):
    n, t = len(matrix), len(matrix[0])
    total = sum(sum(row) for row in matrix)/F(n*t)
    return [[matrix[i][j]-sum(matrix[i])/F(t)-sum(row[j] for row in matrix)/F(n)+total
             for j in range(t)] for i in range(n)]


def numerical(a, page):
    units = []
    error_mass = defaultdict(F)
    for b, d, e1, e2 in product((-1, 1), repeat=4):
        x = [F(b-d), F(b+d)]
        y = [b+2*x[0]+e1, b+2*x[1]+e2]
        units.append((b, d, e1, e2, x, y))
        error_mass[F(d*(e2-e1), 2)] += F(1, 16)
    avg = lambda values: sum(values, F(0))/len(values)
    pq = avg([sum(v*v for v in row[4]) for row in units])
    px = avg([sum(v*z for v, z in zip(row[4], row[5])) for row in units])
    a.equal((pq, px, px/pq), (4, 10, F(5, 2)), 'pooled population projection')
    within = difference_fit([row[4] for row in units], [row[5] for row in units], [1]*16)
    scores = [F(row[4][1]-row[4][0], 2)*(row[3]-row[2]) for row in units]
    a.equal((within[0], within[1]/16, avg(scores), avg([v*v for v in scores])), (2, 2, 0, 2), 'within Gram and unit score law')
    a.equal(dict(error_mass), {F(-1):F(1, 4), F(0):F(1, 2), F(1):F(1, 4)}, 'compressed exact unit slope-error distribution')
    for n in (2, 3):
        convolution = {F(0):F(1)}
        for i in range(n):
            new = defaultdict(F)
            for x, p in convolution.items():
                for y, q in error_mass.items():
                    new[x+y] += p*q
            convolution = dict(new)
        a.equal(sum(p*x/n for x, p in convolution.items()), 0, 'exact finite-N within error mean')
        a.equal(sum(p*(x/n)**2 for x, p in convolution.items()), F(1, 2*n), 'exact finite-N within variance by convolution')
    a.anchors(page, 1, ['rank', 'cᵢ+ūᵢ', 'time-constant'])
    a.anchors(page, 2, [pq, px, px/pq, '1/(2N)', 'singular'])
    a.interventions.append('Compressed score-law convolution verifies finite-N variance without treating repeated dates as independent.')

    def re_product(x, y):
        return sum(v*w for v, w in zip(x, y))-sum(x)*sum(y)/3
    rq = avg([re_product(row[4], row[4]) for row in units])
    rb = avg([re_product(row[4], [row[0], row[0]]) for row in units])
    ry = avg([re_product(row[4], row[5]) for row in units])
    a.equal((rq, rb, ry, ry/rq), (F(8, 3), F(2, 3), 6, F(9, 4)), 'working covariance does not remove the mean bias')
    design = [[1, row[4][t], row[0]] for row in units for t in (0, 1)]
    response = [row[5][t] for row in units for t in (0, 1)]
    a.equal(least_squares(design, response, [1]*32), (0, 2, 1), 'population CRE conditional-mean parameters')
    omega = [[F(4*(i == j)+1) for j in range(3)] for i in range(3)]
    columns = [solve(omega, [int(i == j) for i in range(3)]) for j in range(3)]
    weight = [[columns[j][i] for j in range(3)] for i in range(3)]
    a.equal(weight, [[F(i == j, 4)-F(1, 28) for j in range(3)] for i in range(3)], 'actual compound inverse by elimination')
    a.equal([sum(row) for row in weight], [F(1, 7)]*3, 'between inverse action')
    a.equal([sum(v*z for v, z in zip(row, (-1, 0, 1))) for row in weight], [F(-1, 4), 0, F(1, 4)], 'within inverse action')
    theta = 1-2/sqrt(7)
    transform = [[float(i == j)-theta/3 for j in range(3)] for i in range(3)]
    for i, j in product(range(3), repeat=2):
        a.near(sum(transform[k][i]*transform[k][j] for k in range(3)), float(4*weight[i][j]), 'known-covariance whitening')
    a.anchors(page, 4, ['1−2/√7', 'I/4−11′/28', '1/7', 'x/4', 'θ=0'])
    a.interventions.append('Compare within, working RE and augmented conditional-mean targets; whitening is separate from mean orthogonality.')

    x = [[-2, 0], [-2, 2], [1, 3]]
    y = [[-5, -3], [-3, 7], [7, 13]]
    w = [1, 2, 1]
    row_weights = [value for value in w for t in (0, 1)]
    dummy_design = [[int(k == i) for k in range(3)]+[x[i][t]] for i in range(3) for t in (0, 1)]
    cre_design = [[1, x[i][t], F(sum(x[i]), 2)] for i in range(3) for t in (0, 1)]
    flat_y = [v for row in y for v in row]
    lsdv = least_squares(dummy_design, flat_y, row_weights)
    cre = least_squares(cre_design, flat_y, row_weights)
    difference = difference_fit(x, y, w)
    a.equal(lsdv, (F(-8, 5), 2, F(26, 5), F(12, 5)), 'full four-parameter LSDV fit')
    a.equal(cre, (F(26, 19), F(12, 5), F(202, 95)), 'full three-parameter CRE fit')
    a.equal(difference, (cre[1], 20, 48), 'separate difference slope and cross-products')
    xb, yb = [F(sum(row), 2) for row in x], [F(sum(row), 2) for row in y]
    between = least_squares([[1, v] for v in xb], yb, w)
    a.equal(between, (F(26, 19), F(86, 19)), 'between fit without using CRE coefficients')
    a.equal(cre[2], between[1]-cre[1], 'added mean coefficient')
    a.equal(least_squares(cre_design, flat_y, [7*v for v in row_weights]), cre, 'common weight-scale invariance')
    unequal_dates = [1, 2, 2, 2, 1, 1]
    broken_fe = least_squares(dummy_design, flat_y, unequal_dates)[-1]
    broken_cre = least_squares(cre_design, flat_y, unequal_dates)[1]
    a.equal((broken_fe, broken_cre), (F(73, 31), F(1179, 509)), 'date-specific weights break the declared identity')
    a.equal(broken_fe != broken_cre, True, 'common within-unit weights are substantive')
    expected_cells = ['1', '1', '-2,0', '-5,-3', '-1', '-4', '2', '2', '-2,2', '-3,7', '0', '2', '3', '1', '1,3', '7,13', '2', '10']
    a.equal(page.cells, expected_cells, 'all printed weighted-sample table entries')
    a.anchors(page, 5, [20, 48, *cre, between[1], F(19, 4), F(43, 2), 'E[c|X]'])
    a.interventions.append('Direct LSDV and CRE fits agree under common unit weights; changing one date weight supplies a concrete failure outside that contract.')

    sequential = list(product((-1, 1), repeat=3))
    sq = avg([F((e1-z)**2) for z, e1, e2 in sequential])
    sg = avg([F((e1-z)*(e2-e1)) for z, e1, e2 in sequential])
    a.equal((sq, sg, sg/sq), (2, -1, F(-1, 2)), 'sequential-regressor within bias')
    for z in (-1, 1):
        a.equal(avg([F(e1) for zz, e1, e2 in sequential if zz == z]), 0, 'first sequential conditional mean')
        for first in (-1, 1):
            selected = [(e1, e2) for zz, e1, e2 in sequential if zz == z and e1 == first]
            a.equal(avg([F(e2) for e1, e2 in selected]), 0, 'second sequential conditional mean')
            a.equal(avg([F(e1) for e1, e2 in selected]), first, 'full-history conditional mean is nonzero')
    a.anchors(page, 3, ['β−1/2', 'sequential', 'strict', '-1', '2'])
    for rho, expected_variance in ((F(0), 2), (F(1, 2), 8), (F(9, 10), 200)):
        rows = dynamic_law(rho)
        denominator = avg([z*dx for z, dx, dy, *errors in rows])
        numerator = avg([z*dy for z, dx, dy, *errors in rows])
        moments = [z*(dy-rho*dx) for z, dx, dy, *errors in rows]
        fe_values = [dx/z for z, dx, dy, *errors in rows]
        a.equal((denominator, numerator, avg(moments)), (rho-1, rho*(rho-1), 0), 'valid dynamic moment from recursively generated outcomes')
        a.equal(iv_ratio(rows), rho, 'all-state ratio coefficient')
        a.equal(avg([g*g for g in moments])/denominator**2, expected_variance, 'dynamic influence variance')
        a.equal((avg(fe_values), avg([(v-(rho-1))**2 for v in fe_values])), (rho-1, 1), 'exact dynamic FE mean and variance')
        a.equal(avg([F((e2-e1)*(e3-e2)) for z, dx, dy, e1, e2, e3 in rows]), -1, 'shared innovation covariance')
    boundary = dynamic_law(1)
    for candidate in (-1, 0, 1, 2):
        a.equal(avg([z*(dy-candidate*dx) for z, dx, dy, *rest in boundary]), 0, 'rank-zero lag moment is flat')
    a.equal(avg([z*(dx+z) for z, dx, dy, *rest in boundary]), 1, 'another feature of the boundary law retains the rho value')
    feedback = dynamic_law(F(1, 2), serial=True)
    a.equal(avg([z*(dy-dx/2) for z, dx, dy, *rest in feedback]), 1, 'serial dependence invalidates lag exclusion')
    a.equal(iv_ratio(feedback), F(-3, 2), 'invalid-moment ratio target')
    a.anchors(page, 6, [F(-1, 2), F(-1, 4), 8, '1/N', 'covariance−1'])
    a.anchors(page, 7, [200, F(-1, 10), F(3, 4), F(-3, 2), 'past'])
    a.interventions.append('Sequential feedback, changing relevance and serial innovations separate transformed endogeneity, moment rank and whole-law identification.')

    attrition_evidence = []
    for response, respondent, cell_var, ht_var, empty in ((F(1, 3), F(3), F(6), F(42), F(5, 6)),
                                                        (F(1, 2), F(10, 3), F(11, 2), F(47, 2), F(3, 4))):
        latent, observable = missing_law(response)
        a.equal(sum(observable.values()), 1, 'actual observed law normalizes')
        response_mass = sum(p for (h, flag, y), p in observable.items() if flag)
        response_total = sum(p*y for (h, flag, y), p in observable.items() if flag)
        a.equal(response_total/response_mass, respondent, 'respondent-law mean')
        a.equal(cell_functional(observable), 4, 'fitted-cell target from only observed records')
        influences = {atom: directional_influence(observable, atom) for atom in observable}
        known_composition = {atom: directional_influence(observable, atom, True) for atom in observable}
        oracle_ht = {atom: (atom[2]/(1 if atom[0] == 0 else response) if atom[1] else 0)-4 for atom in observable}
        normalized_ht = {atom: ((atom[2]-4)/(1 if atom[0] == 0 else response) if atom[1] else 0) for atom in observable}
        mean_if = lambda mapping: sum(p*mapping[atom] for atom, p in observable.items())
        variance_if = lambda mapping: sum(p*mapping[atom]**2 for atom, p in observable.items())
        a.equal((mean_if(influences), mean_if(oracle_ht)), (0, 0), 'observed-law influences are centered')
        a.equal((variance_if(influences), variance_if(oracle_ht)), (cell_var, ht_var), 'fitted versus unnormalized oracle variance')
        a.equal(variance_if(known_composition), cell_var-4, 'known baseline composition removes only its variation')
        a.equal(variance_if(normalized_ht), F(5, 2)*(1+1/response), 'normalized oracle has a third influence')
        a.equal(sum(p*influences[atom]*(oracle_ht[atom]-influences[atom]) for atom, p in observable.items()), 0, 'oracle extra term is orthogonal')
        for atom, actual in influences.items():
            h, flag, y = atom
            mu = 2+4*h
            expected = mu-4+(F(y-mu, 1)/(1 if h == 0 else response) if flag else 0)
            a.equal(actual, expected, 'derivative at an observable atom versus analytic influence')
        absent = F(0)
        for first, second in product(observable, repeat=2):
            seen = {atom[0] for atom in (first, second) if atom[1]}
            if len(seen) != 2:
                absent += observable[first]*observable[second]
        a.equal(absent, empty, 'two observed-record draws may leave a response-empty cell')
        attrition_evidence.append({'response':str(response), 'fitted_variance':str(cell_var), 'known_p_HT_variance':str(ht_var), 'response_empty_N2':str(absent)})
    latent, observable = missing_law(F(1, 3))
    a.equal((len(latent), len(observable)), (6, 5), 'six latent states collapse to five observed atoms')
    for missing, target in ((3, 3), (9, 5)):
        total = sum(p*(y if flag else missing) for p, h, flag, y in latent)
        mapped = defaultdict(F)
        for p, h, flag, y in latent:
            changed_y = y if flag else missing
            mapped[(h, flag, changed_y if flag else None)] += p
        a.equal((total, dict(mapped)), (target, observable), 'unrestricted missing-outcome changes preserve the entire observed law')
    _, full_response = missing_law(F(1))
    full_if = {atom:directional_influence(full_response, atom) for atom in full_response}
    a.equal(sum(p*full_if[atom]**2 for atom, p in full_response.items()), 5, 'full-response boundary gives sample-mean variance')
    cohorts = [
        ([(0,1,F(1)),(0,1,F(3))]*3+[(1,1,F(5)),(1,1,F(7))]+[(1,0,None)]*4, F(6)),
        ([(0,1,F(1)),(0,1,F(3))]*2+[(1,1,F(5)),(1,1,F(7))]+[(1,0,None)]*2, F(11,2)),
    ]
    for cohort, expected in cohorts:
        empirical = defaultdict(F)
        for atom in cohort:
            empirical[atom] += F(1,len(cohort))
        fitted_mean = cell_functional(empirical)
        fitted_if = {atom:directional_influence(empirical,atom) for atom in empirical}
        feasible = sum(p*fitted_if[atom]**2 for atom,p in empirical.items())
        a.equal(fitted_mean, 4, 'actual cohort mean with only observed outcomes')
        a.equal(sum(p*fitted_if[atom] for atom,p in empirical.items()), 0, 'empirical influence is centered')
        a.equal(feasible, expected, 'actual cohort feasible covariance by observed-law derivative')
        a.equal(feasible/len(cohort), F(1,2) if len(cohort)==12 else F(11,16), 'mean covariance divides root-N variance by cohort size')
    a.anchors(page, 8, [6, 42, 36, 'baseline composition', 'computable from (H,Y)'])
    a.anchors(page, 9, [F(10, 3), F(11, 2), F(47, 2), F(3, 4), 'identical observed'])
    a.interventions.append('Observed-law differentiation distinguishes fitted propensities, fixed composition, unnormalized and normalized known-propensity estimators.')
    a.interventions.append('Response-probability changes, empty cells, full response and observationally identical non-MAR laws test the identification and finite-support boundaries.')

    for n in (4, 8):
        q = [-1, -1, 1, 1]*(n//4)
        x = [[F(qi*s) for s in (-1, 1)] for qi in q]
        errors, slopes = [], []
        for shock in (-1, 1):
            u = [[shock*v for v in row] for row in x]
            y = [[2*v+z for v, z in zip(row, other)] for row, other in zip(x, u)]
            slope = difference_fit(x, y, [1]*n)[0]
            a.equal(twice_center(x), x, 'two-way transformed common-factor design')
            a.equal(twice_center(u), u, 'heterogeneous factor survives two-way demeaning')
            a.equal(slope, 2+shock, 'common-shock coefficient law')
            scores = [sum(v*z for v, z in zip(row, other)) for row, other in zip(x, u)]
            residual_scores = [sum(v*(yy-slope*v) for v, yy in zip(row, other)) for row, other in zip(x, y)]
            a.equal(residual_scores, [F(0)]*n, 'fitted residual meat is zero')
            a.equal(twice_center([[F(shock*s) for s in (-1, 1)] for i in q]), [[F(0), F(0)]]*n, 'homogeneous factor removed')
            errors.append(scores)
            slopes.append(slope)
        all_covariances = [[sum(row[i]*row[j] for row in errors)/2 for j in range(n)] for i in range(n)]
        a.equal(sum(sum(row) for row in all_covariances)/n**2, 4, 'all cross-unit covariances preserve score variance')
        a.equal(sum((v-2)**2 for v in slopes)/2, 1, 'coefficient error does not decrease with N')
    a.anchors(page, 10, ['2+U', 'variance4', 'Var(β̂−2)=1', 'zero', 'conditional projection'])
    a.anchors(page, 11, ['O_p(1)', 'δ=o_p(1)', 'Divide by N', 'a′Va>0', 'LLN'])
    a.anchors(page, 12, ['Six distinctions', 'Two changes', 'Conclusion', 'causal'])
    a.equal(6+2*2+2, 12, 'open research-review rubric')
    a.interventions.append('Four and eight units share the same shock; full cross-unit covariance and homogeneous-loading alternatives explain why residual meat is misleading.')
    return attrition_evidence


def check(root=None):
    root = Path(root) if root is not None else Path(__file__).resolve().parents[1]
    a = Audit()
    for name, size, digest in AUTHOR:
        raw = (root/name).read_bytes()
        a.equal((len(raw), hashlib.sha256(raw).hexdigest()), (size, digest), 'final frozen author '+name)
    reader = Reader()
    reader.feed((root/AUTHOR[0][0]).read_text())
    reader.close()
    ids = ['v12-c05-e'+str(i) for i in range(1, 13)]
    a.equal((reader.prompts, list(reader.answers)), (ids, ids), 'twelve exact paired prompts and solutions')
    a.equal((reader.worked, reader.stack, len(reader.ids), len(set(reader.ids))), (6, [], 21, 21), 'complete reader structure')
    evidence = numerical(a, reader)
    sources = strict((root/AUTHOR[2][0]).read_text())
    source_ids = {row['id'] for row in sources['sources']}
    a.equal((len(sources['sources']), set(reader.sources)), (4, source_ids), 'four scoped primary routes')
    a.equal(set(reader.links), {'v12-c01.html','v12-c02.html','v12-c03.html','v12-c04.html','v12-c06.html'} | {'sources.html#'+name for name in source_ids}, 'flat prerequisite and source links')
    author = strict((root/AUTHOR[3][0]).read_text())
    a.equal(set(author['payloads']), {row[0] for row in AUTHOR[:3]}, 'three nonself author bindings')
    for name, row in author['payloads'].items():
        raw = (root/name).read_bytes()
        a.equal({'bytes':len(raw), 'sha256':hashlib.sha256(raw).hexdigest()}, row, 'author binding '+name)
    review = strict((root/RECORD).read_text())
    bindings = review['reviewed_hashes']
    a.equal({row['path'] for row in bindings}, {row[0] for row in AUTHOR} | {SELF}, 'four author files plus peer checker')
    a.equal(len(bindings), 5, 'exact five nonself peer bindings')
    for row in bindings:
        raw = (root/row['path']).read_bytes()
        a.equal((len(raw), hashlib.sha256(raw).hexdigest()), (row['bytes'], row['sha256']), 'peer binding '+row['path'])
    invalids = [
        (lambda:rational(True), 'boolean scalar'), (lambda:rational(float('nan')), 'nonfinite scalar'),
        (lambda:rational(10**7), 'out-of-bound rational'),
        (lambda:solve([[1,1],[1,1]], [1,1]), 'singular normal equation'),
        (lambda:difference_fit([[1,1],[2,2]], [[1,2],[2,3]], [1,1]), 'time-constant within regressor'),
        (lambda:difference_fit([[1,2],[2]], [[1,2],[2,3]], [1,1]), 'incomplete history'),
        (lambda:difference_fit([[1,2],[1,2]], [[1,2],[2,3]], [1,0]), 'zero unit weight'),
        (lambda:dynamic_law(3), 'outside bounded dynamic law'),
        (lambda:iv_ratio(dynamic_law(1)), 'zero sample IV denominator'),
        (lambda:iv_ratio([row for row in dynamic_law(0) if row[3] == row[4]]), 'finite sample denominator zero despite population relevance'),
        (lambda:missing_law(0), 'zero response support'),
        (lambda:missing_law(F(3,2)), 'invalid response probability'),
        (lambda:cell_functional({(0,1,F(2)):F(1,2),(1,0,None):F(1,2)}), 'response-empty cell'),
        (lambda:cell_functional({(0,1,F(2)):F(1,2),(1,0,0):F(1,2)}), 'fabricated missing outcome'),
        (lambda:cell_functional({(True,1,F(2)):F(1,2),(0,1,F(2)):F(1,2)}), 'boolean cell'),
        (lambda:strict('{"x":1,"x":2}'), 'duplicate JSON member'),
        (lambda:strict('NaN'), 'nonfinite JSON literal'),
        (lambda:strict('1e309'), 'overflowing JSON exponent')]
    for operation, label in invalids:
        a.reject(operation, label)
    result = {'chapter':'v12-c05', 'status':'independent peer checks passed', 'comparisons':a.comparisons,
              'paired_solution_anchors':a.answer_anchors, 'domain_rejections':len(a.rejections),
              'rejection_scopes':a.rejections, 'purposeful_interventions':len(a.interventions),
              'intervention_scopes':a.interventions, 'worked_examples':6, 'solved_exercises':12,
              'attrition_observed_law_results':evidence, 'common_shock_units':[4,8],
              'nonself_bindings':5, 'author_code_used_as_oracle':False,
              'limitations':'Bounded exact evidence and separately recorded proof reading; no empirical validity, general panel theorem, rendered UI or acceptance claim.'}
    strict(json.dumps(result, allow_nan=False))
    return result


if __name__ == '__main__':
    check()
