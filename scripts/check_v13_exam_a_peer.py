#!/usr/bin/env python3
"""Independent V13 Form A peer oracle; six files, no author-code execution.

Quiet check(root=None) and no-argument CLI. Exact rational finite cases accompany
separately recorded analytic proof review; they do not prove continuum claims.
"""
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from itertools import product
from math import isqrt
from pathlib import Path
import json
import re
import sys

AUTHOR = (
    ('content/assessments/parts/v13-exam-a.html', 47901, '94c2ba8adcbe0064d41742182b23ed5dda24968840e8891e345ece17c455be97'),
    ('scripts/check_v13_exam_a.py', 31471, '05298cc8270e001fedc98e7614457469a3b9b0943edb98e23e70649b41516747'),
    ('content/reviews/v13-exam-a-sources.json', 18614, '6fad0aad05632f654c66c40ef35d9940309bea4cf9bb41de482f85b863b47d53'),
    ('content/reviews/v13-exam-a-author.json', 14422, 'ba61dbb19739bbb23fe870585180ea936ace4cc643108ac59ed42d2d04c4dbd8'),
)
SELF = 'scripts/check_v13_exam_a_peer.py'
RECORD = 'content/reviews/v13-exam-a-peer.json'
RUNTIME = tuple(x[0] for x in AUTHOR) + (SELF, RECORD)
POINTS = ((4, 6, 4, 6), (6, 5, 5, 4), (4, 4, 6, 6), (5, 6, 5, 4), (5, 5, 4, 6))
SCORES = {f'v13-exam-a-{i}{c}': p for i, row in enumerate(POINTS, 1) for c, p in zip('abcd', row)}
SOURCE_IDS = (
    'v05-c01-mit-preferences', 'v05-c02-consumer', 'mit-expected-utility',
    'v13-c03-borgers-blackwell2023', 'v13-c04-condie-existence', 'v05-c05-mit-welfare',
    'v13-c05-borgers-aggregation2021', 'v13-c06-manea-noncoop2017', 'v13-c06-yildiz-games2022',
    'v05-c08-holmstrom-screening', 'v05-c09-mit-contracts', 'v13-c10-ozdaglar-mechanism2010',
    'v05-c11-manea-matching', 'v13-c11-ght-menu2026', 'v13-c12-berk-harvey-hirshleifer-referee2015',
)
# Primitive inputs, not copied numerical answers or author-checker functions.
INPUTS = {
    'a1-choice6': '(3,3)', 'a1-p0': '(1,1)', 'a1-choice10': '(5,5)',
    'a1-prior': '(1/2,1/2)', 'a1-safe': '(2,2)', 'a1-risk-low': '(0,0)',
    'a1-risk-high': '(4,4)', 'a1-P': '((3/4,1/4),(1/4,3/4))', 'a1-flip': '1/4',
    'a1-incomes': '(6,10)', 'a1-p1': '(4,1)', 'a1-income-new': '10', 'a1-target': '5',
    'a2-transfer-range': '[0,6]', 'a2-shares': '(1/3,2/3)',
    'a2-endowments': '((6,0),(0,6))', 'a2-transfers': '(0,3,6)',
    'a3-benefit': '3', 'a3-cost': '2', 'a3-recommendation': '(1/2,1/2)',
    'a4-types': '{2,6}', 'a4-prior': '1/3', 'a4-success': '(3/4,1/4)',
    'a4-effort-cost': '(1,0)', 'a4-wage-bounds': '(0,2)', 'a4-cash': '(6,2,0)',
    'a4-prior-transfers': '(1/4,1/2)', 'a5-applicant-values': '((3,2,0),(2,3,0))',
    'a5-institution-values': '((1,2),(2,1))', 'a5-applicant-lists': '((X,Y),(Y,X))',
    'a5-priorities': '((B,A),(A,B))', 'a5-worlds': '(0,2)',
}


def need(ok, message):
    if not ok:
        raise ValueError(message)


def rational(x):
    need(type(x) is int or isinstance(x, F), 'exact integer/Fraction required')
    x = F(x)
    need(abs(x) <= 10**6 and x.denominator <= 10**9, 'bounded rational required')
    return x


def probability(x):
    x = rational(x)
    need(0 <= x <= 1, 'probability outside [0,1]')
    return x


def row(xs, size):
    need(type(xs) in (tuple, list) and len(xs) == size, 'wrong row dimension')
    return tuple(rational(x) for x in xs)


def law(xs, size):
    xs = row(xs, size)
    need(min(xs) >= 0 and sum(xs) == 1, 'invalid probability law')
    return xs


def square_root(x):
    x = rational(x)
    need(x >= 0, 'negative square-root input')
    a, b = isqrt(x.numerator), isqrt(x.denominator)
    need(a*a == x.numerator and b*b == x.denominator, 'oracle requires an exact rational root')
    return F(a, b)


def strict_json(text):
    def pairs(items):
        out = {}
        for k, v in items:
            need(k not in out, 'duplicate JSON key')
            out[k] = v
        return out
    def bad(s):
        raise ValueError('nonfinite JSON: ' + s)
    obj = json.loads(text, object_pairs_hook=pairs, parse_constant=bad)
    # allow_nan=False also rejects ordinary JSON exponent overflow in float parsing.
    json.dumps(obj, allow_nan=False)
    return obj


def fmt(x):
    if isinstance(x, (tuple, list)):
        return '(' + ','.join(fmt(y) for y in x) + ')'
    return str(x)


def flat(xs):
    return ','.join(fmt(x) for x in xs)


def compact(s):
    return re.sub(r'\s+', '', s).replace('−', '-')


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids = set()
        self.inputs, self.results, self.models = {}, {}, {}
        self.prompts, self.solutions, self.rubrics, self.routes = {}, {}, {}, {}
        self.links, self.stack = set(), []
        self.cases = []
        self.solution_boxes = 0

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        need(len(d) == len(attrs), 'duplicate HTML attribute')
        if 'id' in d:
            need(d['id'] not in self.ids, 'duplicate HTML id')
            self.ids.add(d['id'])
        capture = None
        for key, dest in (('data-input', self.inputs), ('data-calc', self.results), ('data-model', self.models)):
            if key in d:
                need(capture is None and not any(e[1] for e in self.stack), 'nested numeric/model capture')
                need(d[key] not in dest, 'duplicate visible marker')
                dest[d[key]] = ''
                capture = (dest, d[key])
        if 'data-points' in d and tag == 'li':
            need('id' in d and d['id'] not in self.prompts, 'scored prompt id')
            self.prompts[d['id']] = int(d['data-points'])
        if 'data-solution-for' in d:
            need(d['data-solution-for'] not in self.solutions, 'duplicate solution')
            self.solutions[d['data-solution-for']] = ''
        if 'data-rubric-for' in d:
            key = d['data-rubric-for']
            need(key not in self.rubrics, 'duplicate rubric')
            self.rubrics[key] = [int(d['data-points']), '']
        if 'data-source' in d:
            need(d['data-source'] not in self.routes and tag == 'a', 'duplicate/nonlink source')
            self.routes[d['data-source']] = d['href']
        if 'href' in d:
            self.links.add(d['href'])
        if tag == 'section' and 'data-domain' in d:
            self.cases.append(d['data-domain'])
        if tag == 'details' and 'solutions' in d.get('class', '').split():
            self.solution_boxes += 1
        if tag not in ('br', 'hr', 'img', 'meta', 'link', 'input'):
            self.stack.append((tag, capture, d))

    def handle_endtag(self, tag):
        need(self.stack and self.stack[-1][0] == tag, 'HTML nesting')
        self.stack.pop()

    def handle_data(self, text):
        for _, cap, d in self.stack:
            if cap:
                cap[0][cap[1]] += text
            if 'data-solution-for' in d:
                self.solutions[d['data-solution-for']] += text
            if 'data-rubric-for' in d:
                self.rubrics[d['data-rubric-for']][1] += text


class Audit:
    def __init__(self):
        self.comparisons = 0
        self.rejections = 0
        self.interventions = []

    def equal(self, actual, expected, label):
        self.comparisons += 1
        need(actual == expected, label + ': ' + repr(actual) + ' != ' + repr(expected))

    def true(self, condition, label):
        self.equal(bool(condition), True, label)

    def reject(self, call, label):
        try:
            call()
        except (ValueError, TypeError, json.JSONDecodeError):
            self.rejections += 1
            return
        raise ValueError('invalid input accepted: ' + label)


def demand(prices, wealth, share=None):
    p, q = row(prices, 2)
    wealth = rational(wealth)
    need(p > 0 and q > 0 and wealth >= 0, 'positive prices/nonnegative wealth')
    if share is None:
        z = wealth/(p+q)
        return z, z
    share = rational(share)
    need(0 < share < 1, 'interior share')
    return share*wealth/p, (1-share)*wealth/q


def dual(prices, target):
    p, q = row(prices, 2)
    target = rational(target)
    need(p > 0 and q > 0 and target >= 0, 'positive prices/nonnegative target')
    # Equality of the two expenditure contributions is the AM-GM certificate.
    spend = 2*target*square_root(p*q)
    return spend, (spend/(2*p), spend/(2*q))


def multiply(left, right):
    need(type(left) in (list, tuple) and len(left) == 2, 'two-state matrix')
    left = tuple(law(x, 2) for x in left)
    need(type(right) in (list, tuple) and len(right) == 2, 'two-signal matrix')
    right = tuple(law(x, 2) for x in right)
    return tuple(tuple(sum(left[s][j]*right[j][a] for j in range(2)) for a in range(2)) for s in range(2))


def decisions(experiment, prior, payoffs):
    prior = law(prior, 2)
    need(len(experiment) == 2, 'two states')
    experiment = tuple(law(x, 2) for x in experiment)
    need(len(payoffs) == 2, 'two actions')
    payoffs = tuple(row(x, 2) for x in payoffs)  # action, state
    masses = tuple(sum(prior[s]*experiment[s][j] for s in range(2)) for j in range(2))
    need(min(masses) > 0, 'posteriors need positive signal mass')
    posterior = tuple(prior[1]*experiment[1][j]/masses[j] for j in range(2))
    values = {}
    for acts in product(range(2), repeat=2):
        values[acts] = sum(prior[s]*experiment[s][j]*payoffs[acts[j]][s] for s in range(2) for j in range(2))
    best = max(values.values())
    return masses, posterior, best, tuple(k for k, v in values.items() if v == best)


def exchange(t, price=None):
    t = rational(t)
    need(0 <= t <= 6, 'transfer must be owned')
    r = (12-t)/12 if price is None else rational(price)
    need(r > 0, 'positive normalized price')
    incomes = 6*r+t, 6-t
    a = demand((r, 1), incomes[0], F(1, 3))
    b = demand((r, 1), incomes[1], F(2, 3))
    return r, incomes, a, b


def payoff(a, b):
    need(type(a) is int and type(b) is int and a in (0, 1) and b in (0, 1), 'binary pure actions')
    return (3*int(a+b > 0)-2*a, 3*int(a+b > 0)-2*b)


def plan_table():
    plans = ((1, 1), (1, 0), (0, 1), (0, 0))
    return tuple(tuple(payoff(a, z[1-a]) for z in plans) for a in (1, 0))


def plan_test(p, weights):
    p = probability(p)
    weights = law(weights, 4)
    tab = plan_table()
    one = tuple(sum(weights[j]*tab[i][j][0] for j in range(4)) for i in range(2))
    two = tuple(p*tab[0][j][1]+(1-p)*tab[1][j][1] for j in range(4))
    best = max(one), max(two)
    ok1 = (p == 0 or one[0] == best[0]) and (p == 1 or one[1] == best[0])
    ok2 = all(w == 0 or u == best[1] for w, u in zip(weights, two))
    return ok1 and ok2, one, two


def price_polygon(qlo, qhi):
    """Exact half-plane clipping of the complete price square, independent of rents."""
    qlo, qhi = probability(qlo), probability(qhi)
    poly = [(F(0), F(0)), (F(6), F(0)), (F(6), F(6)), (F(0), F(6))]
    # a*TL+b*TH <= c: two participation and both complete report comparisons.
    restrictions = ((1, 0, 2*qlo), (0, 1, 6*qhi), (1, -1, 2*(qlo-qhi)), (-1, 1, 6*(qhi-qlo)))
    for a, b, c in restrictions:
        if not poly:
            break
        out = []
        for start, end in zip(poly, poly[1:]+poly[:1]):
            f = c-a*start[0]-b*start[1]
            g = c-a*end[0]-b*end[1]
            if f >= 0:
                out.append(start)
            if (f < 0 <= g) or (g < 0 <= f):
                t = f/(f-g)
                out.append(tuple(start[k]+t*(end[k]-start[k]) for k in range(2)))
        poly = list(dict.fromkeys(out))
    return tuple(poly)


def menu_optimum(prior, allowed=(0, 1, 2)):
    prior = probability(prior)
    need(0 < prior < 1, 'both buyer types must have positive probability')
    need(type(allowed) is tuple and allowed and len(set(allowed)) == len(allowed)
         and all(type(k) is int and k in (0, 1, 2) for k in allowed), 'invalid modes')
    modes = ((F(0), F(0)), (F(1, 4), F(0)), (F(3, 4), F(3, 2)))
    result = {}
    for i, j in product(allowed, repeat=2):
        ql, cl = modes[i]
        qh, ch = modes[j]
        poly = price_polygon(ql, qh)
        if poly:
            scores = {xy: (1-prior)*(xy[0]-cl)+prior*(xy[1]-ch) for xy in poly}
            val = max(scores.values())
            result[i, j] = val, tuple(sorted(x for x, v in scores.items() if v == val))
    return result


def cash(price, wage):
    price, wage = rational(price), rational(wage)
    need(0 <= price <= 6 and 0 <= wage <= 2, 'buyer cash/committed wage bounds')
    return 6-price, 2+price-wage, wage


def preferences(a_report, b_report):
    reports = (a_report, b_report)
    for report in reports:
        need(type(report) is tuple and len(report) <= 2 and len(set(report)) == len(report)
             and all(s in ('X', 'Y') for s in report), 'strict ordered subset required')
    return reports


def stable(reports):
    """Exhaustive matching/blocking oracle, not the author's proposal algorithm."""
    need(type(reports) is tuple and len(reports) == 2, 'two applicant reports')
    reports = preferences(*reports)
    rankings = ({1: 0, 0: 1}, {0: 0, 1: 1})  # X prefers B; Y prefers A
    admissible, answer = [], []
    for mu in product((None, 'X', 'Y'), repeat=2):
        if mu[0] is not None and mu[0] == mu[1]:
            continue
        admissible.append(mu)
        if any(x is not None and x not in reports[i] for i, x in enumerate(mu)):
            continue
        blocked = False
        for i in range(2):
            for inst in reports[i]:
                if mu[i] == inst:
                    continue
                prefer = mu[i] is None or reports[i].index(inst) < reports[i].index(mu[i])
                incumbent = next((j for j in range(2) if mu[j] == inst), None)
                order = rankings[('X', 'Y').index(inst)]
                if prefer and (incumbent is None or order[i] < order[incumbent]):
                    blocked = True
        if not blocked:
            answer.append(mu)
    return tuple(admissible), tuple(answer)


def applicant_optimal(reports):
    _, outcomes = stable(reports)
    def rank(i, x):
        return reports[i].index(x) if x is not None else len(reports[i])
    good = [m for m in outcomes if all(all(rank(i, m[i]) <= rank(i, n[i]) for i in range(2)) for n in outcomes)]
    need(len(good) == 1, 'unique proposer optimum required')
    return good[0]


def allocation_values(mu, lam):
    lam = rational(lam)
    need(lam >= 0 and type(mu) is tuple and len(mu) == 2, 'externality/allocation domain')
    need(mu in tuple(m for m in product((None, 'X', 'Y'), repeat=2) if m[0] is None or m[0] != m[1]), 'invalid assignment')
    av = {None: 0, 'X': 3, 'Y': 2}[mu[0]] + lam*(mu[1] == 'X')
    bv = {None: 0, 'X': 2, 'Y': 3}[mu[1]]
    return av, F(bv), F(1*(mu[0] == 'X')+2*(mu[1] == 'X')), F(2*(mu[0] == 'Y')+1*(mu[1] == 'Y'))


def numerical(a):
    out = {}
    put = lambda name, value: out.update({name: fmt(value)})
    half = F(1, 2)
    for income, observed in ((6, (3, 3)), (10, (5, 5))):
        a.equal(demand((1, 1), income, half), observed, 'equal-price CD unique choice')
        a.equal(demand((1, 1), income), observed, 'equal-price minimum unique choice')
    put('a1-new-U', demand((4, 1), 10, half)); put('a1-new-L', demand((4, 1), 10))
    spend, h = dual((4, 1), 5)
    put('a1-e', spend); put('a1-h', h)
    a.equal((sum(p*x for p, x in zip((4, 1), h)), h[0]*h[1]), (spend, F(25)), 'dual budget and target')
    s = ((-h[0]/8, h[0]/2), (h[1]/8, -h[1]/2))
    put('a1-S', s)
    a.equal(tuple(sum(s[i][j]*(4, 1)[j] for j in range(2)) for i in range(2)), (0, 0), 'price null')
    a.equal((s[0][1], s[0][0]*s[1][1]-s[0][1]*s[1][0]), (s[1][0], 0), 'symmetric rank-one Hessian')
    a.true(s[0][0] < 0 and s[1][1] < 0, 'negative semidefinite eigenvalue certificate')
    a.equal((demand((4, 1), 0, half), dual((4, 1), 0)), ((0, 0), (0, (0, 0))), 'zero wealth and target')
    p = ((F(3, 4), F(1, 4)), (F(1, 4), F(3, 4)))
    g = p; q = multiply(p, g)
    put('a1-Q', q)
    for label, ex in (('P', p), ('Q', q)):
        masses, post, val, rules = decisions(ex, (half, half), ((2, 2), (0, 4)))
        a.equal(masses, (half, half), 'signal probabilities ' + label)
        a.equal(rules, ((0, 1),), 'all optimal signal rules ' + label)
        out['a1-post-' + label] = flat(post); put('a1-value-' + label, val)
    for rule in product((0, 1), repeat=2):
        d = tuple(tuple(F(int(k == rule[j])) for k in range(2)) for j in range(2))
        a.equal(multiply(p, multiply(g, d)), multiply(q, d), 'statewise deterministic simulation')
    d = ((F(1, 3), F(2, 3)), (F(4, 5), F(1, 5)))
    a.equal(multiply(p, multiply(g, d)), multiply(q, d), 'statewise randomized simulation')
    put('a1-lottery-U', (F(2), half*0+half*4)); put('a1-lottery-square', (F(2)**2, half*0+half*4**2))
    a.interventions += ['Q1: zero wealth/target and randomized decision simulation']

    base = exchange(0); change = exchange(3); end = exchange(6)
    for t in (0, 1, 3, 6):
        r, incomes, aa, bb = exchange(t)
        a.equal(tuple(aa[j]+bb[j] for j in range(2)), (6, 6), 'both commodities clear')
        a.equal((r*aa[0]+aa[1], r*bb[0]+bb[1]), incomes, 'owned household budgets')
        a.equal(sum(incomes), 6*r+6, 'aggregate wealth')
    put('a2-endpoint-price', end[0]); out['a2-endpoint-bundles'] = flat(end[2:])
    put('a2-base-incomes', base[1]); put('a2-transfer-price', change[0]); put('a2-transfer-incomes', change[1])
    put('a2-transfer-A', change[2]); put('a2-transfer-B', change[3])
    ua = lambda xy: xy[0]*xy[1]**2
    ub = lambda xy: xy[0]**2*xy[1]
    out['a2-cube-A'] = str(ua(base[2]))+'→'+str(ua(change[2]))
    out['a2-cube-B'] = str(ub(base[3]))+'→'+str(ub(change[3]))
    r, incomes, aa, bb = exchange(0, 2)
    excess = (aa[0]+bb[0]-6, aa[1]+bb[1]-6)
    a.equal((excess, r*excess[0]+excess[1]), ((-2, 4), 0), 'Walras identity without clearing')
    r = F(3, 4)
    before = demand((r, 1), 4, F(1, 3))[0]+demand((r, 1), 5, F(2, 3))[0]
    after = demand((r, 1), 5, F(1, 3))[0]+demand((r, 1), 4, F(2, 3))[0]
    a.equal(after-before, -1/(3*r), 'fixed-price heterogeneous wealth effect')
    a.interventions += ['Q2: owned transfer endpoint, nonclearing Walras witness and Engel slopes']

    table = tuple(tuple(payoff(i, j) for j in (1, 0)) for i in (1, 0))
    a.equal(table, (((1, 1), (1, 3)), ((3, 1), (0, 0))), 'all pure outcomes')
    # Exhaust the two pure supports and interior-indifference solution.
    pure = [(i, j) for i, j in product((0, 1), repeat=2)
            if payoff(i, j)[0] >= payoff(1-i, j)[0] and payoff(i, j)[1] >= payoff(i, 1-j)[1]]
    a.equal(pure, [(0, 1), (1, 0)], 'all pure Nash')
    mix = F(table[0][0][0]-table[1][1][0], table[1][0][0]-table[1][1][0])
    a.equal(mix, F(1, 3), 'interior indifference root')
    expected = tuple(sum((mix if i else 1-mix)*(mix if j else 1-mix)*payoff(i, j)[k]
                         for i, j in product((0, 1), repeat=2)) for k in range(2))
    put('a3-independent-payoffs', expected); put('a3-independent-provision', 1-(1-mix)**2)
    ce = ((1, 0, half), (0, 1, half))
    for player, rec in product(range(2), (0, 1)):
        gain = sum(prob*(payoff(i, j)[player]-payoff(1-i if player == 0 else i, 1-j if player == 1 else j)[player])
                   for i, j, prob in ce if (i, j)[player] == rec)
        a.equal(gain, half if rec else F(1), 'recommendation deviation margin')
    a.equal(tuple(sum(prob*payoff(i, j)[k] for i, j, prob in ce) for k in range(2)), (2, 2), 'CE utilities')
    a.equal(sum(prob*2*(i+j) for i, j, prob in ce), 2, 'actual input use')
    a.true(3*half > 1, 'independent same marginals fail best replies')
    for r in (F(0), F(1, 4), F(1, 3)):
        a.true(plan_test(1, (0, 0, r, 1-r))[0], 'first-V Nash family')
    a.true(not plan_test(1, (0, 0, F(7, 20), F(13, 20)))[0], 'off-path threat boundary')
    for r in (F(0), half, F(1)):
        a.true(plan_test(0, (r, 0, 1-r, 0))[0], 'first-N Nash family')
    for p in (F(1, 10), half, F(9, 10)):
        _, _, u = plan_test(p, (0, 0, 1, 0))
        a.equal(tuple(j for j in range(4) if u[j] == max(u)), (2,), 'unique interior-reach plan')
        a.true(not plan_test(p, (0, 0, 1, 0))[0], 'no first-player interior equilibrium')
    put('a3-SPE-payoffs', payoff(0, 1))
    for eps in (F(1, 100), F(1, 10), F(1, 4)):
        weights = (eps, eps, 1-3*eps, eps)
        _, one, two = plan_test(eps, weights)
        a.true(min(weights) > 0 and one[1] > one[0] and two[2] > max(two[:2]+two[3:]), 'fully mixed perfection witness')
        a.equal(one[1], 3-6*eps, 'tremble return')
    a.interventions += ['Q3: correlated versus independent law; complete-plan boundary; positive trembles']

    # The wage cap and incentive gap together force the unique H schedule.
    probabilities = F(3, 4), F(1, 4)
    incentive_gap = probabilities[0]-probabilities[1]
    necessary_spread = 1/incentive_gap
    a.equal(necessary_spread, 2, 'H-IC reaches maximum feasible wage spread')
    wages = necessary_spread, F(0)
    hc = probabilities[0]*wages[0]+(1-probabilities[0])*wages[1]
    put('a4-H-wages', wages); put('a4-H-cost', hc)
    a.equal((hc-1, probabilities[1]*wages[0]), (half, half), 'H participation and weak effort tie')
    a.equal((F(0)-1, F(0)), (-1, 0), 'L zero wages globally attain lower bound')
    results = menu_optimum(F(1, 3)); ordering = ((0, 0), (0, 1), (0, 2), (1, 1), (1, 2), (2, 2))
    a.equal(set(results), set(ordering), 'nine pairs screened by full IC price polytope')
    out['a4-baseline-profits'] = flat(results[x][0] for x in ordering)
    qs = (F(0), F(1, 4), F(3, 4))
    for i, j in ordering:
        a.equal(results[i, j][1], ((2*qs[i], 6*qs[j]-4*qs[i]),), 'independent polygon optimal prices')
    put('a4-price-0H', (qs[2], results[0, 2][1][0][1])); put('a4-price-LH', (qs[2], results[1, 2][1][0][1]))
    for prior, label, winning in ((F(1, 4), 'quarter', ((1, 2),)), (F(1, 2), 'half', ((0, 2),)), (F(1, 3), None, ((0, 2), (1, 2)))):
        items = menu_optimum(prior)
        val = max(z[0] for z in items.values())
        a.equal(tuple(k for k, z in items.items() if z[0] == val), winning, 'complete prior winner set')
        if label:
            put('a4-'+label+'-profit', val)
    # Every difference is affine; strict endpoint checks settle both open regimes.
    for prior in (F(1, 100), F(1, 3), F(99, 100)):
        m = menu_optimum(prior)
        a.equal(m[0, 2][0]-m[1, 2][0], (3*prior-1)/2, 'exact policy-crossing polynomial')
    for pair, tag in (((0, 2), '0H'), ((1, 2), 'LH')):
        tl, th = results[pair][1][0]
        lowq, highq = qs[pair[0]], qs[pair[1]]
        real = F(2, 3)*(2*lowq)+F(1, 3)*(6*highq-1)
        buyer = F(2, 3)*(2*lowq-tl)+F(1, 3)*(6*highq-th)
        worker = F(1, 3)*(hc-1)
        a.equal(real, results[pair][0]+buyer+worker, 'real surplus and expected transfers cancel')
        put('a4-surplus-'+tag, real)
        for outcome, wage in (('S', 2), ('F', 0)):
            ledger = cash(th, wage)
            a.equal((sum(ledger), min(ledger) >= 0), (8, True), 'funded output cash ledger')
            put('a4-cash-'+tag+'-'+outcome, ledger)
    put('a4-cash-L', cash(results[1, 2][1][0][0], 0))
    strict = menu_optimum(F(1, 3), (0, 1))
    top = max(z[0] for z in strict.values())
    a.equal((top, tuple(k for k, v in strict.items() if v[0] == top)), (half, ((0, 1), (1, 1))), 'strict effort changed feasible set')
    a.interventions += ['Q4: independent full IC price polytopes; prior switch; strict effort cap; funded state ledgers']

    reports = ((), ('X',), ('Y',), ('X', 'Y'), ('Y', 'X'))
    full = (('X', 'Y'), ('Y', 'X'))
    allm, stablem = stable(full)
    a.equal((len(allm), set(stablem)), (7, {('X', 'Y'), ('Y', 'X')}), 'all partial assignments and stable set')
    chosen = tuple(applicant_optimal((r, full[1])) for r in reports)
    a.equal(chosen, ((None, 'Y'), ('X', 'Y'), ('Y', 'X'), ('X', 'Y'), ('Y', 'X')), 'all ordered-subset report outcomes')
    a.equal({x[0] for x in chosen}, {None, 'X', 'Y'}, 'entire attainable menu')
    basepay = tuple(allocation_values(mu, 0)[0] for mu in chosen)
    slope = tuple(allocation_values(mu, 1)[0]-basepay[j] for j, mu in enumerate(chosen))
    out['a5-utilities'] = ','.join(str(c)+('+' if c else '')+'λ' if d else str(c) for c, d in zip(basepay, slope))
    a.equal(slope, (0, 0, 1, 0, 1), 'externality coefficients')
    for lam in (0, F(1, 2), 1, 2):
        vals = tuple(allocation_values(mu, lam)[0] for mu in chosen)
        a.equal(vals[3] == max(vals), lam <= 1, 'intrinsic-report best response threshold')
    old, new0, new2 = allocation_values(chosen[3], 0), allocation_values(chosen[2], 0), allocation_values(chosen[2], 2)
    a.equal(old, allocation_values(chosen[3], 2), 'complete old-law observational equivalence')
    a.true(new2[0] > old[0] and new2[1] < old[1], 'higher sum not Pareto')
    out['a5-sum-change'] = str(sum(old))+'→'+str(sum(new2))
    put('a5-old', old); put('a5-new-zero', new0); put('a5-new-two', new2)
    a.interventions += ['Q5: all partial stable assignments and five reports; spillover tie and observational equivalence']
    return out


def invalid(a):
    cases = [
        (lambda: rational(True), 'boolean'), (lambda: rational(0.5), 'inexact float outside exact oracle'),
        (lambda: rational(float('nan')), 'NaN'), (lambda: rational(float('inf')), 'infinity'),
        (lambda: rational(10**7), 'magnitude cap'), (lambda: rational(F(1, 10**10)), 'denominator cap'),
        (lambda: demand((0, 1), 1, F(1, 2)), 'zero price'), (lambda: demand((-1, 1), 1), 'negative price'),
        (lambda: demand((1, 1), -1), 'negative wealth'), (lambda: demand((1, 1, 1), 1), 'wrong price dimension'),
        (lambda: demand((1, 1), 1, 1), 'boundary share'), (lambda: dual((1, 1), -1), 'negative target'),
        (lambda: square_root(F(2)), 'nonrational root outside oracle'),
        (lambda: law((F(1, 2), F(1, 3)), 2), 'probability sum'), (lambda: law((-1, 2), 2), 'negative mass'),
        (lambda: decisions(((1, 0), (1, 0)), (F(1, 2), F(1, 2)), ((2, 2), (0, 4))), 'null signal posterior'),
        (lambda: multiply(((1, 0),), ((1, 0), (0, 1))), 'wrong state count'),
        (lambda: exchange(-1), 'negative transfer'), (lambda: exchange(7), 'unowned transfer'),
        (lambda: exchange(0, 0), 'zero normalized price'), (lambda: payoff(True, 1), 'boolean action'),
        (lambda: payoff(2, 0), 'unavailable action'), (lambda: plan_test(-1, (1, 0, 0, 0)), 'invalid mixing'),
        (lambda: plan_test(0, (1, 0)), 'incomplete contingent-plan law'),
        (lambda: menu_optimum(0), 'missing high type'), (lambda: menu_optimum(1), 'missing low type'),
        (lambda: menu_optimum(F(1, 2), (0, 0)), 'duplicate mode'), (lambda: price_polygon(-1, 0), 'negative quality'),
        (lambda: cash(7, 0), 'unfunded buyer payment'), (lambda: cash(0, 3), 'escrow exceeded'),
        (lambda: cash(-1, 0), 'prohibited reverse price'),
        (lambda: stable((('X', 'X'), ('Y',))), 'duplicate reported name'),
        (lambda: stable((('Z',), ('Y',))), 'unknown institution'),
        (lambda: allocation_values(('X', 'X'), 1), 'duplicate seat'),
        (lambda: allocation_values(('X', 'Y'), -1), 'negative externality outside scope'),
        (lambda: strict_json('{"x":1,"x":2}'), 'duplicate key'), (lambda: strict_json('{"x":NaN}'), 'JSON NaN'),
        (lambda: strict_json('{"x":1e999}'), 'JSON float overflow'),
    ]
    for call, label in cases:
        a.reject(call, label)


def check(root=None):
    root = Path(__file__).resolve().parents[1] if root is None else Path(root).resolve()
    payloads = {p: (root/p).read_bytes() for p in RUNTIME}
    a = Audit()
    for path, size, digest in AUTHOR:
        a.equal((len(payloads[path]), sha256(payloads[path]).hexdigest()), (size, digest), 'final author binding')
    author = strict_json(payloads[AUTHOR[3][0]].decode())
    source = strict_json(payloads[AUTHOR[2][0]].decode())
    peer = strict_json(payloads[RECORD].decode())
    for record, expected in ((author, set(RUNTIME[:3])), (peer, set(RUNTIME[:-1]))):
        bindings = record['bindings']
        a.equal({b['path'] for b in bindings}, expected, 'complete nonself binding set')
        a.equal(len(bindings), len(expected), 'no duplicate bindings')
        for b in bindings:
            raw = payloads[b['path']]
            a.equal((b['bytes'], b['sha256']), (len(raw), sha256(raw).hexdigest()), 'record bound payload')
    a.equal(peer['open_findings'], [], 'peer has no unresolved finding')
    a.equal(peer['source_inspection']['new_primary_retrievals'], 0, 'no invented retrieval')
    a.equal(peer['source_inspection']['new_primary_image_views'], 0, 'no invented image read')
    page = Page(); page.feed(payloads[AUTHOR[0][0]].decode()); page.close()
    a.equal(page.stack, [], 'closed HTML fragment')
    a.equal(page.prompts, SCORES, 'twenty prompt point allocations')
    a.equal(set(page.solutions), set(SCORES), 'twenty exact paired solutions')
    a.equal(set(page.rubrics), set(SCORES), 'twenty exact paired rubrics')
    a.equal(page.solution_boxes, 1, 'reader solution wrapper')
    a.equal(len(page.cases), 5, 'five domains')
    a.equal(tuple(sum(p) for p in POINTS), (20,)*5, 'domain totals')
    a.true(all(x in ('form-a', 'solutions-a') or x.startswith('v13-exam-a-') for x in page.ids), 'namespaced IDs')
    for key, score in SCORES.items():
        points, rubric = page.rubrics[key]
        a.equal((points, sum(map(int, re.findall(r'\b(\d+) for\b', rubric)))), (score, score), 'additive rubric ' + key)
        a.true(len(page.solutions[key].strip()) > 150, 'substantive paired answer ' + key)
    a.equal({r['id']: r['points'] for r in peer['prompt_solution_review']}, SCORES, 'peer exact-ID judgment coverage')
    a.equal(set(page.inputs), set(INPUTS), '32 original input markers')
    for k, value in INPUTS.items():
        a.equal(compact(page.inputs[k]), value, 'visible primitive ' + k)
    a.equal(set(page.models), {'choice', 'exchange', 'volunteer', 'buyer', 'externality'}, 'five explicit model laws')
    results = numerical(a)
    a.equal((len(results), set(page.results)), (43, set(results)), '43 independently computed result markers')
    for k, value in results.items():
        a.equal(compact(page.results[k]), compact(value), 'visible computed conclusion ' + k)
    for k in range(1, 13):
        a.true(f'v13-c{k:02}.html' in page.links, 'mapped accepted chapter route')
    sources = source['sources']
    a.equal(tuple(r['id'] for r in sources), SOURCE_IDS, 'fifteen canonical source identities')
    a.equal(page.routes, {r['id']: r['url'] for r in sources}, 'exact primary method routes')
    a.equal((source['new_primary_retrievals'], source['new_primary_image_views']), (0, 0), 'honest inherited evidence')
    for item in sources:
        a.equal(item['mode'], 'reuse_accepted_scoped_evidence', 'inherited source mode')
        a.true(all(item[k] for k in ('prior_actual_inspector', 'inherited_scope', 'current_exam_use', 'limits')), 'scoped provenance')
    invalid(a)
    a.equal({p: (root/p).read_bytes() for p in RUNTIME}, payloads, 'six runtime payloads unchanged')
    summary = {'status': 'passed', 'component': 'v13-exam-a-peer', 'comparisons': a.comparisons,
               'domain_rejections': a.rejections, 'intervention_groups': len(a.interventions),
               'visible_inputs': 32, 'computed_visible_results': 43, 'scored_parts': 20,
               'domains': 5, 'points': 100, 'source_routes': 15, 'runtime_files': 6,
               'author_execution': False}
    json.dumps(summary, allow_nan=False)
    return summary


if __name__ == '__main__':
    need(len(sys.argv) == 1, 'usage: python3 -B scripts/check_v13_exam_a_peer.py')
    check()
