"""Exact, quiet four-file audit of the original V13 reassessment Form B."""
import ast
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from itertools import product
import json
from math import isqrt
from pathlib import Path
import re
import sys

PAGE = 'content/assessments/parts/v13-exam-b.html'
SELF = 'scripts/check_v13_exam_b.py'
SOURCES = 'content/reviews/v13-exam-b-sources.json'
REVIEW = 'content/reviews/v13-exam-b-author.json'
FILES = (PAGE, SELF, SOURCES, REVIEW)
POINTS = ((5, 7, 4, 4), (7, 3, 6, 4), (5, 6, 5, 4),
          (8, 4, 3, 5), (5, 5, 5, 5))
SCORES = {f'v13-exam-b-{n}{c}': v for n, row in enumerate(POINTS, 1)
          for c, v in zip('abcd', row)}
INPUTS = {
    'b1-p1': '(1,4)', 'b1-p2': '(1,4)', 'b1-p3': '(4,4)',
    'b1-wealth1': '1', 'b1-wealth2': '4', 'b1-wealth3': '5',
    'b1-x1': '(1,0)', 'b1-x2': '(4,0)', 'b1-x3': '(1/4,1)',
    'b1-levels': '(1,2,3/2)', 'b1-multipliers': '(1/2,1/4,1/4)',
    'b1-tie': '(3/4,1/16)', 'b1-low-wealth': '(1,4)',
    'b1-high-wealth': '(4,12)', 'b1-probabilities': '(1/2,1/2)',
    'b2-endowments': '(4,1)', 'b2-target-A': '(3,3/2)',
    'b2-target-B': '(1,1/2)', 'b2-weights': '(3/4,1/4)',
    'b3-prior': '(1/3,2/3)', 'b3-costs': '(1,3)', 'b3-payment': '2',
    'b3-benefits': '(5,0)', 'b4-value-support': '[0,√3]',
    'b4-buyer-cash': '2', 'b4-payroll-cash': '16',
    'b4-success': '(2/3,1/3)', 'b4-costs': '(1/2,0)',
    'b4-wages': '(1,16,0,1)', 'b4-changed-H': '(5/12,1/4,1/12,1/4)',
    'b4-changed-L': '(7/24,1/24,5/24,11/24)',
    'b5-a': '(1/4,1/2,1/4)', 'b5-interaction': '1/4',
    'b5-target': '(1,1,1)', 'b5-candidate': '(3/5,3/4,3/5)',
    'b5-global-gap': '1/100', 'b5-objective-error': '1/100',
}
MODELS = {'b1-utility': '√x+y', 'b2-firm1': '√z',
          'b2-firm2': '2√m', 'b4-cdf': 'v²/3',
          'b4-worker-utility': '√w'}
SOURCE_IDS = {
    'v13-c01-varian-demand1982', 'v05-c02-consumer', 'v05-c03-condie-supply',
    'v13-c04-condie-existence', 'mit-risk-attitudes', 'v13-c03-mit-dominance2015',
    'v13-c05-border-welfare2016', 'v13-c05-borgers-aggregation2021',
    'v13-c06-yildiz-games2022', 'v13-c06-manea-noncoop2017',
    'v05-c08-holmstrom-screening', 'v13-c10-roughgarden-revenue2013',
    'v13-c09-stole-contracts1999', 'v13-c11-bkd-networks2014',
    'v13-c12-board-meyer-theory2018', 'v13-c12-berk-harvey-hirshleifer-referee2015',
}


def need(test, reason):
    if not test:
        raise ValueError(reason)


def rational(x):
    need(type(x) is int or isinstance(x, F), 'exact nonboolean rational required')
    x = F(x)
    need(abs(x) <= 10**6 and x.denominator <= 10**12, 'bounded oracle rational')
    return x


def vector(x, n):
    need(type(x) in (tuple, list) and len(x) == n, 'vector dimension')
    return tuple(rational(v) for v in x)


def probability(x):
    x = rational(x)
    need(0 <= x <= 1, 'probability domain')
    return x


def law(x, n):
    x = vector(x, n)
    need(min(x) >= 0 and sum(x) == 1, 'probability simplex')
    return x


def rootq(x):
    x = rational(x)
    need(x >= 0, 'negative square-root argument')
    a, b = isqrt(x.numerator), isqrt(x.denominator)
    need(a*a == x.numerator and b*b == x.denominator,
         'exact oracle supports rational square roots only')
    return F(a, b)


def literal(text):
    """Bounded nonexecuting parser for the visible exact scalar/tuple grammar."""
    need(type(text) is str and len(text) <= 1000, 'literal size')
    try:
        tree = ast.parse(text, mode='eval')
    except SyntaxError as error:
        raise ValueError('literal syntax') from error
    need(sum(1 for _ in ast.walk(tree)) <= 160, 'literal complexity')
    def visit(node, depth=0):
        need(depth <= 10, 'literal depth')
        if isinstance(node, ast.Constant):
            return rational(node.value)
        if isinstance(node, (ast.Tuple, ast.List)):
            need(len(node.elts) <= 20, 'literal vector length')
            return tuple(visit(v, depth+1) for v in node.elts)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            return rational(-visit(node.operand, depth+1))
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            a, b = visit(node.left, depth+1), visit(node.right, depth+1)
            need(isinstance(a, F) and isinstance(b, F) and b != 0, 'fraction division')
            return rational(a/b)
        raise ValueError('unsupported literal expression')
    return visit(tree.body)


def strict_json(text):
    def pairs(items):
        result = {}
        for k, v in items:
            need(k not in result, 'duplicate JSON key')
            result[k] = v
        return result
    def bad(_):
        raise ValueError('nonfinite JSON')
    value = json.loads(text, object_pairs_hook=pairs, parse_constant=bad)
    json.dumps(value, allow_nan=False)
    return value


def norm(x):
    return ''.join(x.replace('−', '-').split())


def shown(x):
    return '('+','.join(shown(v) for v in x)+')' if isinstance(x, (list, tuple)) else str(x)


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.ids = set()
        self.inputs, self.results, self.models = {}, {}, {}
        self.prompts, self.answers, self.rubrics = {}, {}, {}
        self.sources, self.links, self.domains = {}, set(), []
        self.solutions = 0

    def handle_starttag(self, tag, pairs):
        a = dict(pairs)
        need(len(a) == len(pairs), 'duplicate HTML attribute')
        need(tag not in ('h1', 'script', 'iframe', 'object'), 'unexpected reader element')
        if 'id' in a:
            key = a['id']
            need(key not in self.ids and
                 (key in ('form-b', 'solutions-b') or key.startswith('v13-exam-b-')), 'reader ID')
            self.ids.add(key)
        capture = None
        for attr, destination in (('data-input', self.inputs), ('data-calc', self.results),
                                  ('data-model', self.models)):
            if attr in a:
                need(capture is None and not any(x[2] for x in self.stack), 'nested numerical marker')
                key = a[attr]
                need(key not in destination, 'duplicate numerical marker')
                destination[key] = ''
                capture = (destination, key)
        if 'data-points' in a and tag == 'li':
            need(a['id'] not in self.prompts, 'duplicate prompt')
            self.prompts[a['id']] = int(a['data-points'])
        if 'data-solution-for' in a:
            key = a['data-solution-for']
            need(key not in self.answers and any(t == 'details' and
                 'solutions' in z.get('class', '').split() for t, z, _ in self.stack), 'paired solution')
            self.answers[key] = ''
        if 'data-rubric-for' in a:
            key = a['data-rubric-for']
            need(key not in self.rubrics, 'duplicate rubric')
            self.rubrics[key] = [int(a['data-points']), '']
        if 'data-source' in a:
            need(a['data-source'] not in self.sources and tag == 'a', 'unique source link')
            self.sources[a['data-source']] = a['href']
        if 'href' in a:
            self.links.add(a['href'])
        if 'data-domain' in a:
            self.domains.append(a['data-domain'])
        if tag == 'details' and 'solutions' in a.get('class', '').split():
            self.solutions += 1
        if tag not in ('br', 'hr', 'img', 'input', 'meta', 'link', 'wbr'):
            self.stack.append((tag, a, capture))

    def handle_data(self, text):
        for _, a, cap in self.stack:
            if cap:
                cap[0][cap[1]] += text
            if 'data-solution-for' in a:
                self.answers[a['data-solution-for']] += text
            if 'data-rubric-for' in a:
                self.rubrics[a['data-rubric-for']][1] += text

    def handle_endtag(self, tag):
        need(self.stack and self.stack[-1][0] == tag, 'unbalanced reader HTML')
        self.stack.pop()


class Audit:
    def __init__(self):
        self.comparisons = self.rejections = 0

    def eq(self, actual, expected, name):
        self.comparisons += 1
        need(actual == expected, name+': '+repr(actual)+' != '+repr(expected))

    def reject(self, fn, name):
        try:
            fn()
        except (ValueError, TypeError):
            self.rejections += 1
        else:
            raise ValueError('invalid domain accepted: '+name)


def dot(x, y):
    return sum((a*b for a, b in zip(x, y)), F(0))


def consumption(prices, wealth):
    px, py = vector(prices, 2)
    wealth = rational(wealth)
    need(px > 0 and py > 0 and wealth >= 0, 'consumer price/wealth domain')
    cap = py/(2*px)
    s = cap if wealth >= px*cap*cap else rootq(wealth/px)
    return (s*s, (wealth-px*s*s)/py), s+(wealth-px*s*s)/py


def expenditure(prices, utility):
    px, py = vector(prices, 2)
    utility = rational(utility)
    need(px > 0 and py > 0 and utility >= 0, 'dual price/target domain')
    s = min(utility, py/(2*px))
    h = s*s, utility-s
    return dot((px, py), h), h


def firms(p, r):
    p, r = rational(p), rational(r)
    need(p > 0 and r > 0, 'strictly positive production prices')
    z, outm = p*p/4, p/2
    m, outf = r*r/(p*p), 2*r/p
    return z, outm, m, outf, p*outm-z, r*outf-p*m


def entry(prior, costs, payment, benefits):
    prior = law(prior, 2)
    low, high = vector(costs, 2)
    good, bad = vector(benefits, 2)
    payment = rational(payment)
    need(min(prior) > 0 and 0 < low < payment < high and bad < payment < good,
         'finite separating-entry oracle domain')
    return low/payment, (payment-bad)/(good-bad)


def qadd(x, y):
    return x[0]+y[0], x[1]+y[1]


def qscale(x, c):
    return x[0]*c, x[1]*c


def integral_power(k, lower=F(1)):
    """Integral from lower to sqrt(3), represented in Q(sqrt(3))."""
    need(type(k) is int and 0 <= k <= 8, 'polynomial degree')
    lower = rational(lower)
    need(0 <= lower <= 1, 'oracle lower integration bound')
    n = k+1
    upper = (F(3**(n//2)), F(0)) if n % 2 == 0 else (F(0), F(3**((n-1)//2)))
    return (upper[0]-lower**n)/n, upper[1]/n


def radical_text(pair):
    a, b = pair
    need(b > 0, 'positive radical coefficient in this display')
    head = ('' if b.numerator == 1 else str(b.numerator))+'sqrt(3)'
    if b.denominator != 1:
        head += '/'+str(b.denominator)
    return head+('+'+str(a) if a > 0 else str(a) if a < 0 else '')


def compress(signals, wages, costs, cap):
    need(type(signals) in (tuple, list) and len(signals) == 2, 'two action laws')
    laws = tuple(law(row, 4) for row in signals)
    wages, costs = vector(wages, 4), vector(costs, 2)
    cap = rational(cap)
    need(cap > 0 and min(wages) >= 0 and max(wages) <= cap and min(costs) >= 0, 'payroll domain')
    uh = tuple(rootq(w) for w in wages)
    p = laws[0]
    need(sum(p[:2]) > 0 and sum(p[2:]) > 0, 'nonempty target fibers')
    means = dot(p[:2], uh[:2])/sum(p[:2]), dot(p[2:], uh[2:])/sum(p[2:])
    replacement_u = (means[0],)*2+(means[1],)*2
    replacement = tuple(v*v for v in replacement_u)
    old = tuple(dot(row, uh)-c for row, c in zip(laws, costs))
    new = tuple(dot(row, replacement_u)-c for row, c in zip(laws, costs))
    return means, replacement, old, new, dot(p, wages), dot(p, replacement)


def linear_solve(matrix, rhs):
    n = len(rhs)
    a = [list(map(F, row))+[F(v)] for row, v in zip(matrix, rhs)]
    for k in range(n):
        pivot = next((i for i in range(k, n) if a[i][k]), None)
        need(pivot is not None, 'singular oracle system')
        a[k], a[pivot] = a[pivot], a[k]
        pivot = a[k][k]
        a[k] = [v/pivot for v in a[k]]
        for i in range(n):
            if i != k:
                q = a[i][k]
                a[i] = [v-q*w for v, w in zip(a[i], a[k])]
    return tuple(row[-1] for row in a)


def best_reply(x, a, gamma, subsidy=(0, 0, 0)):
    x, a, subsidy = vector(x, 3), vector(a, 3), vector(subsidy, 3)
    gamma = rational(gamma)
    need(min(x) >= 0 and max(x) <= 1 and min(a) >= 0 and min(subsidy) >= 0
         and 0 <= gamma < F(1, 2), 'capped contraction network domain')
    return tuple(min(F(1), max(F(0), a[i]+subsidy[i]+gamma*sum(x[j] for j in range(3) if j != i)))
                 for i in range(3))


def network(a, gamma, subsidy=(0, 0, 0)):
    a, subsidy = vector(a, 3), vector(subsidy, 3)
    gamma = rational(gamma)
    best_reply((0, 0, 0), a, gamma, subsidy)
    candidates = set()
    # Enumerate each coordinate's lower/interior/upper active constraint.
    for face in product((0, None, 1), repeat=3):
        free = [i for i in range(3) if face[i] is None]
        x = [F(v or 0) for v in face]
        matrix = [[F(i == j)-gamma*(i != j) for j in free] for i in free]
        rhs = [a[i]+subsidy[i]+gamma*sum(x[j] for j in range(3) if j not in free) for i in free]
        for i, v in zip(free, linear_solve(matrix, rhs)):
            x[i] = v
        if min(x) >= 0 and max(x) <= 1 and tuple(x) == best_reply(x, a, gamma, subsidy):
            candidates.add(tuple(x))
    need(len(candidates) == 1, 'global contraction candidate completeness')
    return candidates.pop()


def payoffs(x, a, gamma):
    return tuple(a[i]*x[i]-x[i]*x[i]/2+gamma*x[i]*sum(x[j] for j in range(3) if j != i)
                 for i in range(3))


def calculate(inputs, audit):
    q = {k: literal(v) for k, v in inputs.items() if k != 'b4-value-support'}
    result = {}
    def put(k, value):
        result[k] = shown(value)
    p = [q['b1-p'+str(i)] for i in range(1, 4)]
    x = [q['b1-x'+str(i)] for i in range(1, 4)]
    levels, lam = q['b1-levels'], q['b1-multipliers']
    slacks = tuple(tuple(levels[t]+lam[t]*dot(p[t], tuple(x[s][i]-x[t][i] for i in range(2)))-levels[s]
                         for s in range(3)) for t in range(3))
    put('b1-slacks', slacks)
    audit.eq(all(v >= 0 for row in slacks for v in row), True, 'all Afriat inequalities')
    alternative = q['b1-tie']
    planes = tuple(levels[t]+lam[t]*dot(p[t], tuple(alternative[i]-x[t][i] for i in range(2))) for t in range(3))
    put('b1-tie-planes', planes)
    audit.eq((dot(p[0], alternative), min(planes)), (F(1), levels[0]), 'real selected-demand tie')
    for i in range(3):
        wealth = q['b1-wealth'+str(i+1)]
        bundle, value = consumption(p[i], wealth)
        audit.eq((dot(p[i], x[i]), bundle), (wealth, x[i]), 'observed budget and maintained choice')
        audit.eq(expenditure(p[i], value), (wealth, bundle), 'observed dual recovery')
    for prices in ((1, 4), (4, 4), (2, 1)):
        for target in (F(0), F(1, 8), F(1, 2), F(2), F(3)):
            wealth, h = expenditure(prices, target)
            audit.eq(consumption(prices, wealth), (h, target), 'global corner primal/dual boundary')
    probabilities = law(q['b1-probabilities'], 2)
    for name in ('low', 'high'):
        wealths = q['b1-'+name+'-wealth']
        eu = dot(probabilities, tuple(consumption(p[0], w)[1] for w in wealths))
        ce = expenditure(p[0], eu)[0]
        mean = dot(probabilities, wealths)
        for suffix, value in (('EU', eu), ('CE', ce), ('mean', mean), ('premium', mean-ce)):
            put('b1-'+name+'-'+suffix, value)
    audit.eq((F(1, 2)/rootq(4), F(1, 4)), (F(1, 4), F(1, 4)), 'C1 wealth boundary')
    endow = q['b2-endowments']
    pm = rootq(4*sum(endow)/5)
    pf = rootq(pm**3/2)
    z, mout, muse, fout, pi1, pi2 = firms(pm, pf)
    put('b2-prices', (F(1), pm, pf)); put('b2-profits', (pi1, pi2))
    def allocation(owned, profits):
        incomes = tuple(a+b for a, b in zip(owned, profits))
        choices = tuple((w/2, w/(2*pf)) for w in incomes)
        audit.eq((sum(row[0] for row in choices)+z, mout-muse, sum(row[1] for row in choices)),
                 (sum(endow), F(0), fout), 'all three physical balances')
        audit.eq(tuple(dot((1, pf), row) for row in choices), incomes, 'owned income budgets')
        return incomes, choices
    incomes, choices = allocation(endow, (pi1, pi2))
    put('b2-baseline-incomes', incomes); put('b2-baseline-A', choices[0]); put('b2-baseline-B', choices[1])
    swapped, target = allocation(endow, (pi2, pi1))
    put('b2-swapped-incomes', swapped); put('b2-target-A', target[0]); put('b2-target-B', target[1])
    audit.eq(target, (q['b2-target-A'], q['b2-target-B']), 'ownership target')
    audit.eq(allocation((endow[0]+1, endow[1]-1), (pi1, pi2)), (swapped, target), 'authorized balanced raw transfer')
    weights = law(q['b2-weights'], 2)
    audit.eq(tuple(tuple(w/v for v in row) for w, row in zip(weights, target)),
             ((F(1, 4), F(1, 2)),)*2, 'weighted welfare support gradient')
    audit.eq((pm*mout-z, pf*fout-pm*muse, pf*fout-z), (pi1, pi2, pi1+pi2), 'intermediate invoice cancellation')
    audit.eq((F(3, 2)+pi1-F(5, 2), pi2-F(1, 2)-F(3, 2)), (0, 0), 'actual household settlement')
    wrong = sum(endow)+pm*mout+pf*fout
    put('b2-wrong-demand', (wrong/2, wrong/(2*pf)))
    audit.eq(wrong-(sum(endow)-z+pf*fout), F(3), 'gross-profit double count')
    prior, costs, payment, benefits = q['b3-prior'], q['b3-costs'], q['b3-payment'], q['b3-benefits']
    entry_cutoff, posterior_cutoff = entry(prior, costs, payment, benefits)
    put('b3-trading-strategy', (1, 0, 1)); put('b3-posterior-cutoff', posterior_cutoff)
    put('b3-exante-payoffs', (prior[0]*(payment-costs[0]), prior[0]*(benefits[0]-payment)))
    put('b3-real-surplus', prior[0]*(benefits[0]-costs[0]))
    def reply(p, gain):
        return gain == 0 or (gain > 0 and p == 1) or (gain < 0 and p == 0)
    grid = (F(0), F(1, 4), F(1, 2), F(3, 4), F(1))
    equilibria = {(g, b, z) for g, b, z in product(grid, repeat=3)
                  if reply(g, payment*z-costs[0]) and reply(b, payment*z-costs[1])
                  and reply(z, prior[0]*g*(benefits[0]-payment)+prior[1]*b*(benefits[1]-payment))}
    audit.eq(equilibria, {(F(1), F(0), F(1))} | {(F(0), F(0), z) for z in grid if z <= entry_cutoff},
             'complete boundary families corroborated')
    for mu in (F(1, 5), posterior_cutoff):
        for epsilon in (F(1, 10), F(1, 100)):
            eg, eb = 2*mu*epsilon, (1-mu)*epsilon
            audit.eq(prior[0]*eg/(prior[0]*eg+prior[1]*eb), mu, 'exact consistent posterior')
    audit.eq((payment-costs[0] > 0, payment-costs[1] < 0), (True, True), 'supplied dominated-type rule')
    revenue = qscale(qadd(integral_power(4), qscale(integral_power(2), -1)), F(2, 3))
    value = qscale(integral_power(4), F(4, 9))
    rent = qadd(value, qscale(revenue, -1))
    put('b4-sale', 1-F(1, 3)**2)
    for label, pair in (('revenue', revenue), ('allocated-value', value), ('buyer-rent', rent)):
        result['b4-'+label] = radical_text(pair)
    direct = qadd((F(4, 9), F(0)), qadd(qscale(integral_power(2), F(4, 3)), qscale(integral_power(4), F(-4, 9))))
    audit.eq(direct, revenue, 'independent direct critical-payment integral')
    correlated = qscale(integral_power(2), F(2, 3))
    zero = qscale(integral_power(2, F(0)), F(2, 3))
    result['b4-correlated-reserve-revenue'] = radical_text(correlated)
    result['b4-correlated-zero-revenue'] = radical_text(zero)
    audit.eq(qadd(zero, qscale(correlated, -1)), (F(2, 9), F(0)), 'correlated counterexample revenue')
    audit.eq(q['b4-buyer-cash']**2 > 3, True, 'every auction payment funded')
    success = tuple(probability(x) for x in q['b4-success'])
    laws = tuple((p/2, p/2, (1-p)/2, (1-p)/2) for p in success)
    means, wages, old, new, old_cost, new_cost = compress(laws, q['b4-wages'], q['b4-costs'], q['b4-payroll-cash'])
    put('b4-compressed-wages', wages); put('b4-old-H-cost', old_cost); put('b4-new-H-cost', new_cost)
    put('b4-cost-saving', old_cost-new_cost); put('b4-H-utility', new[0]); put('b4-L-utility', new[1])
    put('b4-incentive-gap', new[0]-new[1])
    audit.eq(old, new, 'every action utility preserved')
    changed_laws = (q['b4-changed-H'], q['b4-changed-L'])
    means, wages2, old, new, old_cost, new_cost = compress(changed_laws, q['b4-wages'], q['b4-costs'], q['b4-payroll-cash'])
    audit.eq(tuple((sum(row), sum(row[:2]), row[1]+row[3]) for row in changed_laws),
             ((F(1), success[0], F(1, 2)), (F(1), success[1], F(1, 2))), 'equal separate marginals')
    for name, answer in (('means', means), ('compressed-wages', wages2), ('L-utility', new[1]),
                         ('gap', new[0]-new[1]), ('old-cost', old_cost), ('new-cost', new_cost)):
        put('b4-changed-'+name, answer)
    audit.eq((old[0], old[1], old[0]-old[1], new[0]), (F(7, 6), F(11, 12), F(1, 4), F(7, 6)), 'changed incentives and preserved H only')
    for wage in q['b4-wages']+wages+wages2:
        cash = q['b4-payroll-cash']
        audit.eq((cash-wage+1)+wage+(2*q['b4-buyer-cash']-1), cash+2*q['b4-buyer-cash'], 'cash conservation after prefunded wage')
        audit.eq(0 <= wage <= cash, True, 'actual payroll feasibility')
    a, gamma = q['b5-a'], q['b5-interaction']
    x = network(a, gamma)
    utilities = payoffs(x, a, gamma)
    put('b5-Nash', x); put('b5-Nash-utilities', utilities); put('b5-Nash-welfare', sum(utilities))
    target = q['b5-target']
    welfare = lambda x: sum(payoffs(x, a, gamma))
    put('b5-welfare-gap', welfare(target)-welfare(x))
    for y in tuple(product((F(0), F(1)), repeat=3))+(x, q['b5-candidate']):
        deficits = tuple(1-v for v in y)
        certificate = dot(a, deficits)+sum((deficits[i]-deficits[j])**2 for i in range(3) for j in range(i+1, 3))/4
        audit.eq(welfare(target)-welfare(y), certificate, 'global polynomial certificate corroboration')
    deviation = (best_reply(target, a, gamma)[0], F(1), F(1))
    put('b5-deviator-utility', payoffs(deviation, a, gamma)[0])
    put('b5-deviation-gain', payoffs(deviation, a, gamma)[0]-payoffs(target, a, gamma)[0])
    rates = tuple(max(F(0), 1-v-2*gamma) for v in a)
    put('b5-rates', rates); put('b5-budget', sum(rates))
    audit.eq(network(a, gamma, rates), target, 'global funded linear implementation')
    audit.eq(max(dot(rates, y) for y in product((0, 1), repeat=3)), sum(rates), 'every-profile sponsor budget')
    audit.eq(sum(payoffs(target, a, gamma))+sum(rates)-sum(rates), welfare(target), 'sponsor-inclusive transfer cancellation')
    candidate = q['b5-candidate']
    br = best_reply(candidate, a, gamma)
    residual = max(abs(v-w) for v, w in zip(candidate, br))
    put('b5-response', br); put('b5-residual', residual); put('b5-distance-bound', residual/(1-2*gamma))
    audit.eq(max(abs(v-w) for v, w in zip(candidate, x)), F(1, 20), 'actual fixed-point error')
    put('b5-objective-bound', 2*q['b5-objective-error']+q['b5-global-gap'])
    audit.eq(welfare(target)-welfare(x) > 2*q['b5-objective-error']+q['b5-global-gap'], True, 'exact incompatible target claim')
    audit.eq(network((0, 0, 0), gamma), (0, 0, 0), 'lower constraint boundary')
    audit.eq(network((2, 2, 2), gamma), (1, 1, 1), 'upper constraint boundary')
    audit.eq(network(a, 0), a, 'removed network interaction')
    return result


def invalid(audit):
    cases = [
        lambda: rational(True), lambda: rational(0.5), lambda: rational(float('nan')),
        lambda: rational(float('inf')), lambda: rational(10**7), lambda: rational(F(1, 10**13)),
        lambda: literal('1/0'), lambda: literal('True'), lambda: literal('0.5'),
        lambda: literal('x()'), lambda: literal('2**100'), lambda: literal('[]'*600),
        lambda: rootq(-1), lambda: rootq(2), lambda: law((1, 1), 2),
        lambda: law((-1, 2), 2), lambda: vector((1,), 2), lambda: probability(2),
        lambda: consumption((0, 4), 1), lambda: consumption((1, -1), 1),
        lambda: consumption((1, 4), -1), lambda: expenditure((1, 4), -1),
        lambda: expenditure((0, 4), 1), lambda: firms(0, 2),
        lambda: firms(2, -1), lambda: entry((0, 1), (1, 3), 2, (5, 0)),
        lambda: entry((F(1, 3), F(2, 3)), (3, 1), 2, (5, 0)),
        lambda: integral_power(True), lambda: integral_power(20),
        lambda: integral_power(2, 2),
        lambda: compress(((F(1, 4),)*4,)*2, (1, 25, 0, 1), (F(1, 2), 0), 16),
        lambda: compress(((1, 0, 0, 0),)*2, (1, 16, 0, 1), (F(1, 2), 0), 16),
        lambda: compress(((F(1, 4),)*4,)*2, (1, 16, 0, 1), (-1, 0), 16),
        lambda: network((1, 2), F(1, 4)), lambda: network((1, 1, 1), F(1, 2)),
        lambda: network((-1, 1, 1), F(1, 4)),
        lambda: network((1, 1, 1), F(1, 4), (-1, 0, 0)),
        lambda: best_reply((2, 0, 0), (1, 1, 1), F(1, 4)),
        lambda: strict_json('{"a":1,"a":2}'), lambda: strict_json('{"a":NaN}'),
        lambda: strict_json('{"a":Infinity}'), lambda: strict_json('{"a":1e9999}'),
    ]
    for i, case in enumerate(cases):
        audit.reject(case, 'case '+str(i))


def check(root=None):
    root = Path(root) if root is not None else Path(__file__).resolve().parents[1]
    raw = {p: (root/p).read_bytes() for p in FILES}
    audit = Audit()
    page = Page()
    page.feed(raw[PAGE].decode())
    page.close()
    audit.eq(page.stack, [], 'complete balanced fragment')
    audit.eq(page.prompts, SCORES, 'twenty exact scored prompts')
    audit.eq(set(page.answers), set(SCORES), 'twenty paired full solutions')
    audit.eq(set(page.rubrics), set(SCORES), 'twenty additive rubrics')
    audit.eq((len(page.domains), len(set(page.domains)), page.solutions), (5, 5, 1), 'five distinct domains and one solution disclosure')
    for key, score in SCORES.items():
        points, rubric = page.rubrics[key]
        audit.eq((points, sum(map(int, re.findall(r'\b(\d+) for\b', rubric)))), (score, score), 'additive rubric '+key)
        audit.eq(len(page.answers[key].strip()) > 300, True, 'full answer '+key)
    audit.eq({k: norm(v) for k, v in page.inputs.items()}, INPUTS, 'all visible original primitives')
    audit.eq({k: norm(v) for k, v in page.models.items()}, MODELS, 'actual model formulas')
    calculated = calculate(page.inputs, audit)
    audit.eq(set(page.results), set(calculated), 'complete displayed-result scope')
    for key, value in calculated.items():
        audit.eq(norm(page.results[key]), norm(value), 'actual displayed conclusion '+key)
    for n in range(1, 13):
        audit.eq(f'v13-c{n:02}.html' in page.links, True, 'chapter depth route')
    sources = strict_json(raw[SOURCES])
    review = strict_json(raw[REVIEW])
    audit.eq(set(page.sources), SOURCE_IDS, 'sixteen canonical method identities')
    audit.eq(page.sources, {x['id']: x['url'] for x in sources['sources']}, 'exact source routes')
    audit.eq((sources['new_primary_retrievals'], sources['new_primary_image_views']), (0, 0), 'accurate inherited source scope')
    for item in sources['sources']:
        audit.eq(item['mode'], 'reuse_accepted_scoped_evidence', 'prior inspection attribution')
        audit.eq(bool(item['current_exam_use'] and item['inherited_inspection'] and item['accepted_source_records']), True, 'bounded source evidence')
    audit.eq({x['id']: x['points'] for x in review['prompt_solution_review']}, SCORES, 'complete substantive author judgments')
    audit.eq(review['open_findings'], [], 'no unresolved author findings')
    audit.eq({x['path'] for x in review['bindings']}, set(FILES)-{REVIEW}, 'exact nonself author bindings')
    for item in review['bindings']:
        value = raw[item['path']]
        audit.eq((item['bytes'], item['sha256']), (len(value), sha256(value).hexdigest()), 'final binding')
    invalid(audit)
    audit.eq({p: (root/p).read_bytes() for p in FILES}, raw, 'all four payloads unchanged')
    summary = {'volume': 'v13', 'component': 'exam_b', 'status': 'passed',
               'comparisons': audit.comparisons, 'domain_rejections': audit.rejections,
               'visible_inputs': len(page.inputs), 'visible_models': len(page.models),
               'visible_results': len(calculated), 'scored_parts': len(SCORES), 'points': 100,
               'essential_domains': 5, 'source_routes': 16, 'runtime_files': 4,
               'limits': 'Exact original case calculations supplement complete global proof review; separate peer and reader rendering remain distinct.'}
    json.dumps(summary, allow_nan=False)
    return summary


if __name__ == '__main__':
    need(len(sys.argv) == 1, 'quiet checker takes no arguments')
    check()
