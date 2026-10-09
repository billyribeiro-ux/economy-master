"""Quiet five-file checks for V13 diagnostic, oral and retention support."""
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
import json
from math import isqrt
from pathlib import Path
import re
import sys

FILES = ('content/assessments/parts/v13-support-opening.html',
         'content/assessments/parts/v13-support-closing.html',
         'scripts/check_v13_support.py', 'content/reviews/v13-support-sources.json',
         'content/reviews/v13-support-author.json')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def rational(x):
    require(type(x) in (int, F), 'exact rational scalar, excluding bool')
    return F(x)


def square_root(x):
    x = rational(x)
    require(x >= 0, 'nonnegative wealth')
    n, d = isqrt(x.numerator), isqrt(x.denominator)
    require(n*n == x.numerator and d*d == x.denominator, 'rational-square witness')
    return F(n, d)


def demand(prices, wealth):
    require(type(prices) in (tuple, list) and len(prices) == 2, 'two prices')
    p = tuple(rational(x) for x in prices); m = rational(wealth)
    require(min(p) > 0 and m >= 0, 'positive prices and nonnegative wealth')
    return tuple(m/(2*x) for x in p)


def capacity(a, bound):
    a, bound = rational(a), rational(bound)
    require(bound >= 0, 'nonnegative capacity')
    x = min(bound, max(F(0), a))
    return x, a*x-x*x/2


def mixed_zero_sum(matrix):
    require(type(matrix) in (tuple, list) and len(matrix) == 2 and
            all(type(row) in (tuple, list) and len(row) == 2 for row in matrix), 'two by two game')
    a, b, c, d = (rational(x) for row in matrix for x in row)
    den = a-b-c+d
    require(den != 0, 'nondegenerate interior indifference equations')
    p, q = (d-c)/den, (d-b)/den
    require(0 < p < 1 and 0 < q < 1, 'strictly interior support witness')
    return p, q, p*q*a+p*(1-q)*b+(1-p)*q*c+(1-p)*(1-q)*d


EDGES = ((0, 1), (0, 2), (1, 2))


def graph(mask, rho, cost, transfer=0):
    require(type(mask) is int and 0 <= mask < 8, 'three-node edge mask')
    r, c, t = map(rational, (rho, cost, transfer))
    require(0 < r < 1 and min(c, t) >= 0, 'link model parameters')
    neighbors = [set() for _ in range(3)]
    for k, (i, j) in enumerate(EDGES):
        if mask & (1 << k):
            neighbors[i].add(j); neighbors[j].add(i)
    benefits = tuple(sum((r if j in neighbors[i] else r*r if neighbors[i] & neighbors[j]
                          else F(0)) for j in range(3) if i != j) for i in range(3))
    net, paid = [F(0)]*3, [F(0)]*3
    for leaf in (0, 2):
        if 1 in neighbors[leaf]:
            net[leaf] -= t; net[1] += t; paid[leaf] += t
    costs = tuple(c*len(n) for n in neighbors)
    utility = tuple(benefits[i]-costs[i]+net[i] for i in range(3))
    return utility, tuple(net), tuple(costs[i]+paid[i] for i in range(3))


def stable(mask, rho, cost, transfer=0):
    u = graph(mask, rho, cost, transfer)[0]
    for k, ends in enumerate(EDGES):
        v = graph(mask ^ (1 << k), rho, cost, transfer)[0]
        gains = tuple(v[i]-u[i] for i in ends)
        if mask & (1 << k):
            if max(gains) > 0:
                return False
        elif min(gains) >= 0 and max(gains) > 0:
            return False
    return True


def display(x):
    if type(x) in (tuple, list):
        return '('+','.join(display(v) for v in x)+')'
    return str(x).replace('-', '−')


class Support(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.ids, self.points, self.solutions = [], set(), {}, []
        self.markers, self.capture, self.sources, self.links = {}, None, {}, set()

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        require(len(a) == len(attrs), 'no duplicate attributes')
        if 'id' in a:
            require(a['id'] not in self.ids, 'unique support ID'); self.ids.add(a['id'])
        if 'data-points' in a:
            require(a.get('id') and a['id'] not in self.points, 'scored prompt ID')
            self.points[a['id']] = int(a['data-points'])
        if 'data-solution-for' in a:
            require(any(t == 'details' and 'solutions' in d.get('class', '').split()
                        for t, d in self.stack), 'solution disclosure')
            self.solutions.append(a['data-solution-for'])
        if 'data-check' in a:
            name = a['data-check']
            require(self.capture is None and name not in self.markers, 'unique unnested result')
            self.capture = name; self.markers[name] = ''
        if 'href' in a:
            self.links.add(a['href'])
        if 'data-source' in a:
            self.sources[a['data-source']] = a['href']
        require(tag not in ('script', 'iframe', 'object'), 'static support fragments')
        if tag not in ('br', 'hr', 'img', 'meta', 'link', 'input', 'wbr'):
            self.stack.append((tag, a))

    def handle_data(self, text):
        if self.capture is not None:
            self.markers[self.capture] += text

    def handle_endtag(self, tag):
        require(self.stack and self.stack[-1][0] == tag, 'balanced support HTML')
        self.stack.pop()
        if tag == 'span':
            self.capture = None


def read_json(raw):
    def pairs(items):
        d = {}
        for k, v in items:
            require(k not in d, 'duplicate JSON key'); d[k] = v
        return d
    def bad(_):
        raise ValueError('nonfinite JSON constant')
    def finite(text):
        x = float(text)
        require(-float('inf') < x < float('inf'), 'finite JSON number')
        return x
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=bad, parse_float=finite)


def check(root=None):
    require(root is None or type(root) is str or isinstance(root, Path), 'root path')
    root = Path(root) if root is not None else Path(__file__).resolve().parents[1]
    raw = {p: (root/p).read_bytes() for p in FILES}
    page = Support(); count = 0; rejections = 0
    def eq(a, b, label):
        nonlocal count
        count += 1
        require(a == b, label+': '+repr(a)+' != '+repr(b))
    for path in FILES[:2]:
        page.feed(raw[path].decode('utf-8'))
        eq(page.stack, [], 'each complete fragment closes')
    page.close()
    expected = {f'v13-d{i}': 5 for i in range(1, 9)}
    expected.update({f'v13-o{i}': 4 for i in range(1, 6)})
    expected.update({f'v13-r{i}': 10 for i in range(1, 6)})
    eq(page.points, expected, 'all18 scored prompts')
    eq(sorted(page.solutions), sorted(expected), 'all18 complete paired answers')
    for prefix, total in (('d', 40), ('o', 20), ('r', 50)):
        eq(sum(v for k, v in page.points.items() if k.startswith('v13-'+prefix)), total, 'score total')
    require({'diagnostic', 'exam-rules', 'oral-transfer', 'retention', 'remediation', 'notation-index',
             'concept-index', 'volume-synthesis', 'assessment-source-scope'} <= page.ids, 'support sections')
    marks = {}
    x, value = capacity(6, 4)
    marks.update({'d2-choice': x, 'd2-value': value, 'd2-multiplier': 6-x})
    wealth = (F(4), F(16)); eu = sum(square_root(w) for w in wealth)/2
    marks.update({'d3-wealth': sum(wealth)/2, 'd3-utility': eu,
                  'd3-ce': eu*eu, 'd3-premium': sum(wealth)/2-eu*eu})
    relative_price = F(2, 2); marks['d4-price'] = relative_price
    for r in (F(1, 2), F(1), F(2)):
        a, b = demand((r, 1), 2*r), demand((r, 1), 2)
        z = tuple(a[i]+b[i]-2 for i in range(2))
        eq(r*z[0]+z[1], 0, 'Walras law away from clearing')
        if r == 1:
            eq((a, b), ((1, 1), (1, 1)), 'complete computed clearing')
    p, q, value = mixed_zero_sum(((2, -1), (-2, 1)))
    marks.update({'d5-column': q, 'd5-row': p, 'd5-value': value})
    eq(3*q-1, 1-3*q, 'row indifference'); eq(4*p-2, 1-2*p, 'column indifference')
    types, allocations, payments = (F(1), F(3)), (F(1), F(2)), (F(1), F(7, 2))
    buyer = tuple(types[i]*allocations[i]-payments[i] for i in range(2))
    profits = tuple(payments[i]-allocations[i]**2/2 for i in range(2))
    for i in range(2):
        require(buyer[i] > types[i]*allocations[1-i]-payments[1-i], 'strict menu IC')
        require(buyer[i] >= 0 and allocations[i]**2/2 <= 2 and payments[i] <= 5, 'IR and prefunding')
    marks.update({'d7-profits': profits, 'd7-mean-profit': sum(profits)/2,
                  'd7-buyer': sum(buyer)/2, 'd7-total': sum(profits+buyer)/2})
    fixed = F(1, 2)/(1-F(1, 4)); candidate = F(7, 10)
    residual = abs(candidate-(F(1, 2)+candidate/4))
    marks.update({'d8-fixed': fixed, 'd8-residual': residual, 'd8-bound': residual/(1-F(1, 4))})
    eq(marks['d8-bound'], abs(candidate-fixed), 'residual certificate attained')
    marks.update({'o1-before': (3, 2), 'o1-after': (3, 2*2)})
    low, high, effort = F(1, 4), F(3, 4), F(1)
    wage = effort/(high-low); mean = high*wage
    marks.update({'o4-wages': (0, wage), 'o4-mean': mean, 'o4-rent': mean-effort,
                  'o4-high-profit': 4*high-mean, 'o4-low-profit': 4*low})
    eq(mean-effort, low*wage, 'weak hidden-action IC binds')
    require(high*(wage+F(1, 10))-effort > low*(wage+F(1, 10)), 'strict nearby wage witness')
    marks['r1-marshallian'] = demand((2, 1), 12)
    hx_coeff, hy_coeff = F(3, 2), F(3)  # coefficients of sqrt(2)
    eq(2*hx_coeff*hy_coeff, 9, 'Hicksian utility target squared')
    eq(2*hx_coeff, hy_coeff, 'global AM-GM equality condition')
    eq(2*hx_coeff+hy_coeff, 6, 'expenditure sqrt2 coefficient')
    utility = lambda own, other: 2*(own+other)-own*own/2
    ne, planner = (F(2),)*2, (F(4),)*2
    nu = tuple(utility(ne[i], ne[1-i]) for i in range(2))
    pu = tuple(utility(planner[i], planner[1-i]) for i in range(2))
    marks.update({'r2-nash': ne, 'r2-nash-utilities': nu, 'r2-nash-welfare': sum(nu),
                  'r2-planner': planner, 'r2-planner-utilities': pu, 'r2-planner-welfare': sum(pu),
                  'r2-deviation': utility(ne[0], planner[1])})
    for x, y in ((F(0), F(0)), (F(1), F(3)), (F(4), F(4))):
        eq(utility(x, y)+utility(y, x), 16-((x-4)**2+(y-4)**2)/2, 'global welfare-square identity')
    delta = F(3, 5); reward, temptation, punishment = F(3), F(5), F(1)
    threshold = (temptation-reward)/(temptation-punishment)
    cv, dv = reward/(1-delta), temptation+delta*punishment/(1-delta)
    marks.update({'r3-threshold': 'δ≥'+str(threshold), 'r3-cooperate': cv,
                  'r3-deviate': dv, 'r3-margin': cv-dv})
    cap, price = F(4), F(2)
    marks.update({'r4-max-fee': cap*cap/8, 'r4-revenue': (cap*cap/3)/8,
                  'r4-posted-revenue': price*(cap-price)/cap})
    for theta, report in ((F(0), F(4)), (F(2), F(3)), (F(4), F(4))):
        eq(theta*theta/8-(theta*report/4-report*report/8), (theta-report)**2/8, 'global report-loss square')
    rho, cost, fee = F(1, 2), F(9, 16), F(1, 8)
    welfare = {g: sum(graph(g, rho, cost)[0]) for g in range(8)}
    eq([g for g in range(8) if stable(g, rho, cost)], [0], 'complete original stable set')
    eq([g for g in range(8) if welfare[g] == max(welfare.values())], [3, 5, 6], 'all labeled efficient paths')
    target, removed, added = (graph(g, rho, cost, fee)[0] for g in (5, 4, 7))
    require(stable(5, rho, cost, fee), 'target survives every link deviation')
    for g in range(8):
        u, net, due = graph(g, rho, cost, fee)
        eq(sum(net), 0, 'every-graph transfer balance')
        require(max(due) < 2, 'every-graph prefunding')
        eq(sum(u), welfare[g], 'transfers preserve real welfare')
    marks.update({'r5-welfare': tuple(welfare[g] for g in (0, 1, 5, 7)),
                  'r5-payoffs': target, 'r5-keep': target[1]-removed[1],
                  'r5-add': added[0]-target[0], 'r5-leaf-funding': 2*cost+fee,
                  'r5-center-funding': 2*cost, 'r5-first-link': 2*rho-2*cost})
    eq(set(page.markers), set(marks), 'complete result inventory')
    for key, value in marks.items():
        eq(re.sub(r'\s+', '', page.markers[key]), re.sub(r'\s+', '', display(value)), 'printed '+key)
    invalid = [lambda: rational(True), lambda: rational(0.5), lambda: square_root(-1),
               lambda: square_root(2), lambda: capacity(6, -1), lambda: demand((0, 1), 12),
               lambda: demand((2, 1), -1), lambda: demand((1,), 12),
               lambda: mixed_zero_sum(((1, 1), (1, 1))), lambda: graph(True, rho, cost),
               lambda: graph(8, rho, cost), lambda: graph(0, 0, cost), lambda: graph(0, 1, cost),
               lambda: graph(0, rho, -1), lambda: graph(0, rho, cost, -1),
               lambda: read_json(b'{"x":1,"x":2}'), lambda: read_json(b'{"x":NaN}'),
               lambda: read_json(b'{"x":Infinity}'), lambda: read_json(b'{"x":1e9999}')]
    for fn in invalid:
        try:
            fn()
        except ValueError:
            rejections += 1
        else:
            raise ValueError('invalid witness was accepted')
    source, author = (read_json(raw[p]) for p in FILES[3:])
    eq(page.sources, {s['id']: s['url'] for s in source['sources']}, 'exact source routes')
    eq(set(author['prompt_audit']), set(expected), 'all18 exact audits')
    eq({v['path'] for v in author['bindings']}, set(FILES[:4]), 'four nonself bindings')
    for item in author['bindings']:
        content = raw[item['path']]
        eq((len(content), sha256(content).hexdigest()), (item['bytes'], item['sha256']), 'bound payload')
    eq(author['open_findings'], [], 'no unresolved author finding')
    eq({p: (root/p).read_bytes() for p in FILES}, raw, 'no runtime writes')
    result = {'volume': 'v13', 'component': 'support', 'status': 'passed', 'comparisons': count,
              'domain_rejections': rejections, 'solved_prompts': len(expected), 'result_markers': len(marks),
              'diagnostic_points': 40, 'oral_points': 20, 'retention_points': 50, 'runtime_files': 5,
              'scope': 'Exact original calculations and complete proof/prompt review; separate peer and full assembly remain required.'}
    json.dumps(result, allow_nan=False)
    return result


if __name__ == '__main__':
    require(len(sys.argv) == 1, 'silent CLI has no arguments')
    check()
