"""Bounded exact checks for V13-C01. No network or shared runtime imports.

Import and successful CLI are silent. check(root=None) returns strict JSON data.
Only the four canonical payloads are read; none is written. Finite checks
support, but do not replace, the full infinite-domain proofs in the manuscript.
"""
from __future__ import annotations

import ast
from collections import deque
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from itertools import combinations, product
import json
import math
from pathlib import Path
import sys

FILES = (
    'content/chapters/v13-c01.html',
    'scripts/check_v13_c01.py',
    'content/reviews/v13-c01-sources.json',
    'content/reviews/v13-c01-author.json',
)
SOURCE_IDS = {'v05-c01-mit-preferences', 'v05-c01-bergstrom-revealed',
              'v13-c01-varian-demand1982'}


def need(condition, message):
    if not condition:
        raise ValueError(message)


def number(x):
    need(type(x) in (int, float, F), 'numeric type excludes bool and strings')
    if type(x) is float:
        need(math.isfinite(x), 'nonfinite input')
        return F(str(x))
    return F(x)


def vector(x, size=None):
    need(type(x) in (tuple, list) and len(x) > 0, 'nonempty vector required')
    need(size is None or len(x) == size, 'vector dimension')
    return tuple(number(t) for t in x)


def matrix(x, rows=None, cols=None):
    need(type(x) in (tuple, list) and len(x) > 0, 'nonempty matrix required')
    need(rows is None or len(x) == rows, 'matrix row dimension')
    first = vector(x[0], cols)
    return (first,) + tuple(vector(row, len(first)) for row in x[1:])


def dot(x, y):
    need(len(x) == len(y), 'dot dimension')
    return sum((a*b for a, b in zip(x, y)), F(0))


def paths(edges):
    """Breadth-first path witnesses, independently of matrix-closure updates."""
    need(type(edges) in (tuple, list) and len(edges) > 0, 'graph dimension')
    n = len(edges)
    need(all(type(row) in (tuple, list) and len(row) == n for row in edges),
         'square graph')
    need(all(type(t) is bool for row in edges for t in row), 'Boolean edges')
    all_paths = []
    for source in range(n):
        found = {source: (source,)}
        todo = deque([source])
        while todo:
            i = todo.popleft()
            for j, yes in enumerate(edges[i]):
                if yes and j not in found:
                    found[j] = found[i] + (j,)
                    todo.append(j)
        all_paths.append(found)
    return tuple(all_paths)


def closure(edges):
    found = paths(edges)
    return tuple(tuple(j in row for j in range(len(edges))) for row in found)


def budgets(prices, quantities):
    p = matrix(prices)
    x = matrix(quantities, len(p), len(p[0]))
    need(all(t > 0 for row in p for t in row), 'strictly positive prices')
    need(all(t >= 0 for row in x for t in row), 'nonnegative quantities')
    e = tuple(tuple(dot(pi, xs) for xs in x) for pi in p)
    direct = tuple(tuple(e[t][s] <= e[t][t] for s in range(len(x)))
                   for t in range(len(x)))
    r = closure(direct)
    violations = tuple((t, s) for t in range(len(x)) for s in range(len(x))
                       if r[t][s] and e[s][t] < e[s][s])
    pair_warp = all(e[s][t] >= e[s][s] for t in range(len(x))
                    for s in range(len(x)) if direct[t][s])
    return p, x, e, direct, r, violations, pair_warp


def construct(prices, quantities):
    p, x, e, direct, r, bad, pair = budgets(prices, quantities)
    need(not bad, 'GARP violation precludes positive construction')
    remaining = set(range(len(x)))
    old, levels, multipliers, groups = [], {}, {}, []
    while remaining:
        maxima = [i for i in sorted(remaining)
                  if all(not r[j][i] or r[i][j] for j in remaining)]
        need(bool(maxima), 'finite maximal class must exist')
        i = maxima[0]
        group = sorted(j for j in remaining if r[i][j] and r[j][i])
        if not old:
            level, multiplier = F(1), F(1)
        else:
            level = min(value for i in group for j in old
                        for value in (levels[j], levels[j] +
                                      multipliers[j]*(e[j][i]-e[j][j])))
            ratios = []
            for i in group:
                for j in old:
                    difference = e[i][j]-e[i][i]
                    need(difference > 0, 'maximal-class denominator')
                    ratios.append((levels[j]-level)/difference)
            multiplier = max([F(1)] + ratios)
        for i in group:
            levels[i], multipliers[i] = level, multiplier
        old.extend(group)
        remaining.difference_update(group)
        groups.append(tuple(group))
    return (tuple(levels[i] for i in range(len(x))),
            tuple(multipliers[i] for i in range(len(x))), tuple(groups))


def certificate(prices, quantities, levels, multipliers):
    p, x, e, *unused = budgets(prices, quantities)
    u, lam = vector(levels, len(x)), vector(multipliers, len(x))
    need(all(t > 0 for t in lam), 'strictly positive multipliers')
    slacks = tuple(tuple(u[t] + lam[t]*(e[t][s]-e[t][t])-u[s]
                        for s in range(len(x))) for t in range(len(x)))
    need(all(v >= 0 for row in slacks for v in row), 'Afriat inequality violated')
    slopes = tuple(tuple(lam[t]*v for v in p[t]) for t in range(len(x)))
    intercepts = tuple(u[t]-lam[t]*e[t][t] for t in range(len(x)))
    return intercepts, slopes, slacks


def planes(cert, point):
    intercepts, slopes, unused = cert
    x = vector(point, len(slopes[0]))
    need(all(t >= 0 for t in x), 'nonnegative evaluation bundle')
    return tuple(c + dot(a, x) for c, a in zip(intercepts, slopes))


def new_budget_bound(cert, income):
    """Solve equal x1/x3 bound slopes and plane intersection, without a grid."""
    income = number(income)
    need(income > 0, 'positive counterfactual income')
    c, a, unused = cert
    need(len(a) == 3 and len(a[0]) == 3, 'three-plane three-good case')
    denominator = (a[0][0]-a[0][2])-(a[1][0]-a[1][2])
    need(denominator != 0, 'nonparallel equality equation')
    weight = (a[1][2]-a[1][0])/denominator
    need(0 < weight < 1, 'positive convex weights')
    slope = tuple(weight*a[0][j] + (1-weight)*a[1][j] for j in range(3))
    intercept = weight*c[0] + (1-weight)*c[1]
    need(slope[0] == slope[2] > slope[1] and slope[0] > 0,
         'global bound and zero-second-good equality condition')
    first = (c[1]-c[0]+(a[1][2]-a[0][2])*income)/denominator
    candidate = (first, F(0), income-first)
    need(all(t >= 0 for t in candidate), 'candidate budget feasibility')
    upper = intercept + slope[0]*income
    values = planes(cert, candidate)
    need(values[0] == values[1] == upper and values[2] >= upper,
         'candidate must attain bound')
    return weight, intercept, slope, candidate, values, upper, denominator


def menu_data(alternatives, reports):
    need(type(alternatives) in (tuple, list) and bool(alternatives), 'alternatives')
    need(all(type(t) is str and bool(t) for t in alternatives), 'alternative IDs')
    need(len(set(alternatives)) == len(alternatives), 'duplicate alternatives')
    need(type(reports) in (tuple, list) and bool(reports), 'nonempty reports')
    ids, menus, out = set(), set(), []
    for row in reports:
        need(type(row) is dict and set(row) == {'id', 'menu', 'choice'},
             'exact menu report fields')
        ident = row['id']
        need(type(ident) is str and bool(ident) and ident not in ids,
             'missing or duplicate report ID')
        ids.add(ident)
        pairs = []
        for field in ('menu', 'choice'):
            seq = row[field]
            need(type(seq) in (tuple, list) and bool(seq), 'nonempty menu/choice')
            need(all(type(t) is str and t in alternatives for t in seq), 'unknown ID')
            need(len(set(seq)) == len(seq), 'duplicate menu/choice member')
            pairs.append(frozenset(seq))
        menu, choice = pairs
        need(choice <= menu, 'choice outside menu')
        need(menu not in menus, 'duplicate menu report')
        menus.add(menu)
        out.append((menu, choice))
    return tuple(out)


def warp(reports):
    return all(x in d for b, c in reports for a, d in reports
               for x in c for y in b if y in d and x in a)


def menu_graph(alternatives, reports):
    n = len(alternatives)
    index = {a: i for i, a in enumerate(alternatives)}
    weak = [[i == j for j in range(n)] for i in range(n)]
    strict_edges = set()
    for b, c in reports:
        for x in c:
            for y in b:
                weak[index[x]][index[y]] = True
                if y not in c:
                    strict_edges.add((index[x], index[y]))
    r = closure(weak)
    valid = all(not r[j][i] for i, j in strict_edges)
    if not valid:
        return False, None
    remaining, ordered = set(range(n)), []
    while remaining:
        first = next(i for i in sorted(remaining)
                     if all(not r[j][i] or r[i][j] for j in remaining))
        group = {j for j in remaining if r[first][j] and r[j][first]}
        ordered.append(group)
        remaining -= group
    rank = {i: len(ordered)-1-k for k, group in enumerate(ordered) for i in group}
    return True, tuple(rank[i] for i in range(n))


def maximum_choices(alternatives, scores, menu):
    values = dict(zip(alternatives, scores))
    high = max(values[x] for x in menu)
    return frozenset(x for x in menu if values[x] == high)


def numeric_display(text):
    """Exact scalar/tuple arithmetic; never eval arbitrary manuscript content."""
    tree = ast.parse(text.replace('−', '-').strip(), mode='eval')
    def visit(node):
        if isinstance(node, ast.Constant):
            return number(node.value)
        if isinstance(node, (ast.Tuple, ast.List)):
            return tuple(visit(t) for t in node.elts)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            value = visit(node.operand)
            need(type(value) is F, 'unary display scalar')
            return -value if isinstance(node.op, ast.USub) else value
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub,
                                                              ast.Mult, ast.Div)):
            a, b = visit(node.left), visit(node.right)
            need(type(a) is F and type(b) is F, 'binary display scalar')
            if isinstance(node.op, ast.Add):
                return a+b
            if isinstance(node.op, ast.Sub):
                return a-b
            if isinstance(node.op, ast.Mult):
                return a*b
            need(b != 0, 'zero display denominator')
            return a/b
        raise ValueError('unsupported numeric display')
    return visit(tree.body)


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.ids, self.prompts, self.answers = [], set(), [], []
        self.cases, self.sources, self.links = [], set(), []
        self.markers, self.active = {}, None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        need(len(a) == len(attrs), 'duplicate HTML attribute')
        ident = a.get('id')
        if ident is not None:
            need(ident.startswith('v13-c01-') and ident not in self.ids,
                 'missing prefix or duplicate HTML ID')
            self.ids.add(ident)
        classes = a.get('class', '').split()
        if 'worked' in classes:
            need(ident is not None, 'worked ID required')
            self.cases.append(ident)
        if tag == 'li' and any('exercises' in c for unused, c in self.stack):
            need(ident is not None, 'exercise ID required')
            self.prompts.append(ident)
        if 'data-solution-for' in a:
            need(tag == 'li' and any('solutions' in c for unused, c in self.stack),
                 'solution must be in disclosure')
            self.answers.append(a['data-solution-for'])
        if 'data-source' in a:
            self.sources.add(a['data-source'])
        if 'href' in a:
            self.links.append(a['href'])
        if 'data-calc' in a:
            key = a['data-calc']
            need(self.active is None and key not in self.markers, 'duplicate/nested marker')
            self.markers[key] = ''
            self.active = (key, len(self.stack))
        if tag not in ('br', 'hr', 'img', 'input', 'meta', 'link'):
            self.stack.append((tag, classes))

    def handle_endtag(self, tag):
        need(self.stack and self.stack[-1][0] == tag, 'unbalanced HTML element')
        self.stack.pop()
        if self.active is not None and len(self.stack) == self.active[1]:
            self.active = None

    def handle_data(self, data):
        if self.active is not None:
            self.markers[self.active[0]] += data

    def finish(self):
        self.close()
        need(not self.stack and self.active is None, 'unclosed HTML element')
        expected = [f'v13-c01-ex{i}' for i in range(1, 13)]
        need(self.prompts == expected, 'exact twelve prompt IDs/order')
        need(self.answers == expected, 'exact twelve solution pairings/order')
        need(self.cases == [f'v13-c01-case{i}' for i in range(1, 7)],
             'six distinct worked cases')
        need(self.sources == SOURCE_IDS, 'scoped source IDs')
        need(all(not x.startswith(('projects/', 'chapters/')) for x in self.links),
             'flat reader links')
        return self


def parse_page(html):
    page = Page()
    page.feed(html)
    return page.finish()


def strict_object(pairs):
    out = {}
    for key, value in pairs:
        need(key not in out, 'duplicate JSON key')
        out[key] = value
    return out


def strict_json(text):
    def reject_constant(value):
        raise ValueError('nonfinite JSON value')
    return json.loads(text, parse_constant=reject_constant, object_pairs_hook=strict_object)


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
        except (ValueError, TypeError, SyntaxError, ZeroDivisionError):
            self.comparisons += 1
            self.rejections += 1
        else:
            raise ValueError('not rejected: '+label)


def check(root=None):
    root = Path(root) if root is not None else Path(__file__).resolve().parents[1]
    payloads = {name: (root/name).read_bytes() for name in FILES}
    html = payloads[FILES[0]].decode('utf-8')
    page = parse_page(html)
    sources = strict_json(payloads[FILES[2]].decode('utf-8'))
    review = strict_json(payloads[FILES[3]].decode('utf-8'))
    audit, expected = Audit(), {}

    # Reconstruct all complete choices, not just a stored list of outputs.
    alternatives = tuple('abcdef')
    values = tuple(F(t) for t in (2, 1, 0, 2, 1, 0))
    squared = tuple(t*t for t in values)
    reports = []
    for k in range(1, 7):
        for menu in combinations(alternatives, k):
            c = maximum_choices(alternatives, values, menu)
            audit.equal(maximum_choices(alternatives, squared, menu), c,
                        'strict ordinal transform on each menu')
            reports.append({'id': 'm'+str(len(reports)), 'menu': menu,
                            'choice': sorted(c)})
    rs = menu_data(alternatives, reports)
    audit.test(warp(rs), 'all 63 complete menus satisfy correspondence WARP')
    valid, scores = menu_graph(alternatives, rs)
    audit.test(valid, 'full menus have no strict cycle')
    for b, c in rs:
        audit.equal(maximum_choices(alternatives, scores, b), c, 'graph recovers all maxima')
    expected.update({'finite-u': values, 'finite-v': squared, 'finite-menu-count': len(rs),
                     'lottery-u': ((values[0]+values[2])/2, values[1]),
                     'lottery-v': ((squared[0]+squared[2])/2, squared[1])})
    merged = tuple(min(t, 1) for t in values)
    audit.equal(maximum_choices(alternatives, merged, ('a', 'b')), frozenset('ab'),
                'nonstrict map merges strict preference')
    incomplete = list(reports)
    full_index = next(i for i, row in enumerate(incomplete) if len(row['menu']) == 6)
    incomplete[full_index] = {**incomplete[full_index], 'choice': ['a']}
    audit.test(not warp(menu_data(alternatives, incomplete)), 'omitted reported tie violates WARP')
    audit.interventions.append('Strict versus nonstrict ordinal relabeling and omitted complete-choice tie')

    diag = lambda x: (sum(x)+abs(x[0]-x[1])/2)/2
    bundles = tuple(tuple(map(F, row)) for row in ((4, 0), (0, 4), (2, 2), (3, 1)))
    expected['diagonal-values'] = tuple(diag(x) for x in bundles)
    audit.equal(expected['diagonal-values'], (3, 3, 2, F(5, 2)), 'nonconvex upper contour')
    for x in bundles:
        audit.equal(diag((diag(x), diag(x))), diag(x), 'diagonal indifferent label')
        for gain in ((F(1, 10), 0), (0, F(1, 10))):
            y = tuple(a+b for a, b in zip(x, gain))
            audit.test(diag(y)-diag(x) >= sum(gain)/4 > 0, 'one-good strict increase')
    audit.interventions.append('One-good perturbations preserve strict monotonicity despite nonconvex contour')

    grid = tuple(product(range(5), repeat=2))
    for x, y in product(grid, repeat=2):
        audit.equal(x >= y, 5*x[0]+x[1] >= 5*y[0]+y[1], 'finite lexicographic comparison')
    expected.update({'lex-grid-size': len(grid), 'lex-grid-max': max(5*i+j for i, j in grid),
                     'lex-grid-comparisons': len(grid)**2})
    for eps in (F(1, 100), F(1), F(3)):
        a = min(eps/2, F(1, 2))
        audit.test((a, 0) > (0, 1) and a < eps, 'small-weight full-domain counterexample')
    audit.interventions.append('Arbitrarily small and large positive weights fail full-domain lexicographic order')

    alt4 = tuple('abcd')
    positive = menu_data(alt4, [
        {'id': 'p1', 'menu': list('abc'), 'choice': list('ab')},
        {'id': 'p2', 'menu': list('bcd'), 'choice': ['b']},
        {'id': 'p3', 'menu': list('ad'), 'choice': ['a']},
    ])
    orders = []
    for rank in product(range(4), repeat=4):
        if set(rank) == set(range(max(rank)+1)) and all(
                maximum_choices(alt4, rank, b) == c for b, c in positive):
            orders.append(rank)
    reported_orders = ((2, 2, 1, 0), (2, 2, 0, 1), (1, 1, 0, 0))
    audit.equal(set(orders), set(reported_orders), 'complete enumeration of normalized weak orders')
    valid, rank = menu_graph(alt4, positive)
    audit.test(valid and rank in orders, 'finite completion construction')
    negative_rows = [
        {'id': 'n1', 'menu': list('ab'), 'choice': ['a']},
        {'id': 'n2', 'menu': list('bc'), 'choice': ['b']},
        {'id': 'n3', 'menu': list('ac'), 'choice': ['c']},
    ]
    negative = menu_data(tuple('abc'), negative_rows)
    audit.test(warp(negative), 'pair-only WARP succeeds')
    audit.test(not menu_graph(tuple('abc'), negative)[0], 'strict cycle prevents weak order')
    failed = 0
    for k in range(1, 4):
        for choice in combinations('abc', k):
            plus = menu_data(tuple('abc'), negative_rows + [
                {'id': 'triple', 'menu': list('abc'), 'choice': choice}])
            audit.test(not warp(plus), 'every nonempty triple extension fails')
            failed += 1
    expected.update({'menu-orders': reported_orders, 'menu-order-count': len(orders),
                     'triple-failures': failed})
    # Adding an informative c>d comparison resolves only this missing ranking.
    refined = positive + ((frozenset('cd'), frozenset('c')),)
    narrowed = [u for u in orders if all(maximum_choices(alt4, u, b) == c for b, c in refined)]
    audit.equal(narrowed, [(2, 2, 1, 0)], 'new observed comparison shrinks completion set')
    audit.interventions.append('Nonempty triple completion and one informative missing comparison')

    x = tuple(tuple(F(i == j) for j in range(3)) for i in range(3))
    badp = ((F(1), F(4, 5), F(6, 5)), (F(6, 5), F(1), F(4, 5)),
            (F(4, 5), F(6, 5), F(1)))
    goodp = badp[:2] + ((F(6, 5), F(6, 5), F(1)),)
    bad = budgets(badp, x)
    good = budgets(goodp, x)
    audit.test(bad[6] and good[6], 'tie-permitting budget pair WARP both datasets')
    audit.equal(bad[4], ((True,)*3,)*3, 'bad transitive closure')
    audit.equal(bad[5], ((0, 2), (1, 0), (2, 1)), 'all strict reverse witnesses')
    audit.equal(paths(bad[3])[0][2], (0, 1, 2), 'explicit length-two path')
    audit.equal(good[4], ((True, True, True), (False, True, True), (False, False, True)),
                'repaired closure')
    audit.equal(good[5], (), 'repaired GARP')
    expected.update({'prices-bad': bad[2], 'prices-good': good[2],
                     'incomes': tuple(good[2][i][i] for i in range(3)),
                     'good-closure': tuple(tuple(int(t) for t in row) for row in good[4]),
                     'flat-bound': F(1)/min(t for row in badp for t in row)})
    audit.test(expected['flat-bound'] < 2, 'every budget is in flat utility region')
    for t in range(3):
        vertices = [(F(0),)*3] + [tuple(F(i == j)/badp[t][i] for j in range(3))
                                     for i in range(3)]
        for vertex in vertices:
            audit.test(dot(badp[t], vertex) <= 1 and sum(vertex) <= F(5, 4),
                       'budget-polytope extreme points verify total-quantity bound')
    for altered, passed in ((F(1), False), (F(101, 100), True)):
        changed = badp[:2] + ((altered, F(6, 5), F(1)),)
        audit.equal(not budgets(changed, x)[5], passed, 'weak/strict boundary of repair')
    audit.interventions.append('Price-repair equality boundary versus strict removal of revealed cycle')

    au, al, groups = construct(goodp, x)
    audit.equal(groups, ((0,), (1,), (2,)), 'revealed-class order')
    audit.equal(au, (1, F(4, 5), F(3, 5)), 'inductively constructed levels')
    audit.equal(al, (1, 1, 2), 'inductively constructed positive multipliers')
    bu, bl = (1, F(7, 10), F(3, 10)), (1, 2, 4)
    ac, bc = certificate(goodp, x, au, al), certificate(goodp, x, bu, bl)
    expected.update({'certificate-a-u': au, 'certificate-a-lambda': al,
                     'certificate-b-u': bu, 'certificate-b-lambda': bl,
                     'certificate-a-slack': ac[2], 'certificate-b-slack': bc[2]})
    for u, cert in ((au, ac), (bu, bc)):
        for t in range(3):
            audit.equal(min(planes(cert, x[t])), u[t], 'observed utility')
            # Own-plane upper bound certifies all budget points; vertices check printed signs.
            audit.equal(cert[0][t]+dot(cert[1][t], x[t]), u[t], 'own plane equality')
    extra = (F(0), F(5, 4), F(0))
    audit.equal(dot(goodp[0], extra), 1, 'extra first-budget maximum spends income')
    expected['extra-max'] = min(planes(ac, extra))
    audit.equal(expected['extra-max'], au[0], 'selected versus unique')
    other_bundles = ((F(5, 4), 0, 0), (1, 0, F(1, 4)))
    expected['rank-a'] = tuple(min(planes(ac, z)) for z in other_bundles)
    expected['rank-b'] = tuple(min(planes(bc, z)) for z in other_bundles)
    audit.test(expected['rank-a'][0] > expected['rank-a'][1] and
               expected['rank-b'][0] < expected['rank-b'][1], 'opposite unobserved ranks')
    for name, cert, target, value in (
            ('a', ac, (F(7, 6), F(0), F(1, 12)), F(19, 15)),
            ('b', bc, (F(4, 5), F(0), F(9, 20)), F(67, 50))):
        w, c, slope, demand, terms, upper, det = new_budget_bound(cert, F(5, 4))
        audit.equal(demand, target, 'analytically derived unique '+name+' demand')
        audit.equal(upper, value, 'global '+name+' upper bound')
        audit.test(det != 0 and slope[0] == slope[2] > slope[1] and
                   0 < w < 1 and sum(demand) == F(5, 4), 'unique equality conditions')
        expected.update({'new-'+name+'-bound': upper, 'new-'+name+'-demand': demand,
                         'new-'+name+'-planes': terms,
                         'new-'+name+'-third-slack': terms[2]-upper})
        # Small true-income transfer changes the uniquely certified demand.
        altered = new_budget_bound(cert, F(63, 50))
        audit.test(altered[3] != demand and altered[5] > upper, 'new income changes optimum')
    audit.interventions.append('Distinct rationalizers reverse ranks and uniquely respond to changed income')

    tx, tp = ((1, 0), (0, 1)), ((1, 1), (1, 1))
    tu, tl, tg = construct(tp, tx)
    audit.equal(tg, ((0, 1),), 'tied mutual-reachability class')
    tc = certificate(tp, tx, tu, tl)
    audit.equal(tc[:2], ((0, 0), ((1, 1), (1, 1))), 'tied envelope equals total quantity')
    expected.update({'tied-u': tu, 'tied-lambda': tl})
    audit.interventions.append('Tied observations share one class and rationalize multiple maxima')

    # Units, utility scales and observed-order changes preserve the modeled experiment.
    row_scale = (F(2), F(3), F(4))
    rp = tuple(tuple(row_scale[i]*t for t in row) for i, row in enumerate(goodp))
    rc = certificate(rp, x, au, tuple(al[i]/row_scale[i] for i in range(3)))
    audit.equal(rc, ac, 'price/income units with inverse multiplier scaling')
    unit_scale = (F(2), F(3), F(5))
    up = tuple(tuple(row[j]/unit_scale[j] for j in range(3)) for row in goodp)
    ux = tuple(tuple(row[j]*unit_scale[j] for j in range(3)) for row in x)
    uc = certificate(up, ux, au, al)
    for z in x + other_bundles:
        audit.equal(planes(uc, tuple(z[j]*unit_scale[j] for j in range(3))),
                    planes(ac, z), 'commodity-unit change preserves utility')
    shifted = certificate(goodp, x, tuple(3*u-2 for u in au), tuple(3*t for t in al))
    for z in other_bundles:
        audit.equal(min(planes(shifted, z)), 3*min(planes(ac, z))-2,
                    'positive affine certificate transformation')
    perm = (2, 0, 1)
    pp, px = tuple(goodp[i] for i in perm), tuple(x[i] for i in perm)
    pu, pl, pg = construct(pp, px)
    audit.equal(tuple(pu[perm.index(i)] for i in range(3)), au, 'observation permutation levels')
    audit.equal(tuple(pl[perm.index(i)] for i in range(3)), al, 'observation permutation multipliers')
    audit.interventions.append('Price units, commodity units, positive affine labels and row permutation')

    # Invalid inputs: executed conditions, never optimization-sensitive asserts.
    for value in (True, False, '1', None, float('nan'), float('inf'), float('-inf')):
        audit.reject(lambda value=value: number(value), 'invalid scalar')
    for value in ([], 'abc', [[1], [1, 2]], [[True]], [[float('inf')]]):
        audit.reject(lambda value=value: matrix(value), 'malformed matrix')
    for price, bundle in (([[0]], [[1]]), ([[-1]], [[1]]), ([[1]], [[-1]]),
                          ([[1, 1]], [[1]]), ([[1], [2]], [[1]])):
        audit.reject(lambda price=price, bundle=bundle: budgets(price, bundle), 'budget domain')
    audit.reject(lambda: construct(badp, x), 'inconsistent GARP construction')
    for invalid in ((0, 1, 2), (-1, 1, 2), (True, 1, 2), (1, 1), (float('nan'), 1, 2)):
        audit.reject(lambda invalid=invalid: certificate(goodp, x, au, invalid), 'multiplier domain')
    audit.reject(lambda: certificate(goodp, x, (1, 1, 1), (1, 1, 1)), 'false certificate')
    audit.reject(lambda: planes(ac, (-1, 0, 0)), 'negative evaluation bundle')
    audit.reject(lambda: new_budget_bound(ac, 0), 'counterfactual income domain')
    valid_row = {'id': 'one', 'menu': ['a', 'b'], 'choice': ['a']}
    invalid_reports = [[], [{**valid_row, 'id': ''}], [valid_row, valid_row],
                       [{**valid_row, 'choice': []}], [{**valid_row, 'choice': ['c']}],
                       [{**valid_row, 'menu': ['a', 'a']}],
                       [{**valid_row, 'choice': ['a', 'a']}],
                       [{**valid_row, 'menu': ['a', True]}],
                       [{'menu': ['a'], 'choice': ['a']}],
                       [valid_row, {**valid_row, 'id': 'two'}]]
    for invalid in invalid_reports:
        audit.reject(lambda invalid=invalid: menu_data(tuple('abc'), invalid), 'menu contract')
    audit.reject(lambda: menu_data(('a', 'a'), [valid_row]), 'duplicate alternative IDs')
    audit.reject(lambda: paths([[True, False]]), 'nonsquare graph')
    audit.reject(lambda: paths([[1]]), 'nonboolean graph')
    for invalid in ('True', 'float("nan")', '1/0', '__import__("os")'):
        audit.reject(lambda invalid=invalid: numeric_display(invalid), 'display grammar')
    for invalid in ('{"x":NaN}', '{"x":1,"x":2}'):
        audit.reject(lambda invalid=invalid: strict_json(invalid), 'strict JSON')
    audit.reject(lambda: parse_page(html.replace('id="v13-c01-ex1"', '', 1)), 'missing prompt ID')
    audit.reject(lambda: parse_page(html.replace('id="v13-c01-ex2"', 'id="v13-c01-ex1"', 1)),
                 'duplicate prompt ID')
    audit.reject(lambda: parse_page(html.replace('data-solution-for="v13-c01-ex1"',
                                                 'data-solution-for="v13-c01-ex2"', 1)),
                 'wrong solution pairing')
    audit.reject(lambda: parse_page(html.replace('class="solutions"', 'class="other"', 1)),
                 'missing solution disclosure')
    audit.interventions.append('Explicit finite/domain/choice/identity rejection under normal and optimized Python')

    audit.equal(set(page.markers), set(expected), 'exact set of printed numerical markers')
    for key, value in expected.items():
        audit.equal(numeric_display(page.markers[key]), value, 'printed '+key)
    audit.equal(sources['chapter'], 'v13-c01', 'source chapter')
    proposals = sources['proposals']
    audit.equal({s['id'] for s in proposals}, SOURCE_IDS, 'source proposal IDs')
    audit.equal(len(proposals), 3, 'no duplicate source proposal')
    audit.equal(sources['attribution']['new_body_count_in_preparation'], 2, 'two actual fresh bodies')
    audit.equal(sources['attribution']['equation_images_inspected_in_preparation'], 9, 'nine actual images')
    for item in proposals:
        audit.test(bool(item['verification']) and item['url'].startswith('https://'), 'source verification scope')
        audit.test('chapter_author_role' in item['inspection'], 'actual reader attribution')
        if item['id'] == 'v05-c01-bergstrom-revealed':
            audit.equal(item['checked'], '2026-10-07', 'prior-only original inspection date')
            audit.equal(item['inspection']['new_images'], [], 'no new prior-source image claim')
        else:
            audit.equal(item['inspection']['actual_primary_inspector'], 'ito_author', 'primary inspector')
    audit.equal(review['chapter'], 'v13-c01', 'author record chapter')
    audit.equal(review['first_gate']['comparisons'], 729, 'actual independent first gate')
    audit.equal(set(review['exercise_audit']), {f'v13-c01-ex{i}' for i in range(1, 13)},
                'every exact prompt has audit')
    audit.test(len(review['proof_audit']) >= 8 and not review['unresolved_findings'],
               'separate full proof audit and issue disposition')
    bindings = review['bindings']
    audit.equal(set(bindings), set(FILES[:3]), 'three nonself exact bindings')
    for name in FILES[:3]:
        audit.equal(bindings[name], {'bytes': len(payloads[name]),
                                    'sha256': sha256(payloads[name]).hexdigest()}, 'binding '+name)
    summary = {'chapter': 'v13-c01', 'status': 'passed',
               'comparisons': audit.comparisons, 'rejections': audit.rejections,
               'intervention_groups': len(audit.interventions),
               'interventions': audit.interventions, 'worked_cases': len(page.cases),
               'solved_exercises': len(page.answers), 'printed_markers': len(expected),
               'complete_menus': len(rs), 'normalized_restricted_orders': len(orders),
               'triple_extensions_rejected': failed, 'lexicographic_comparisons': len(grid)**2,
               'runtime_files': list(FILES),
               'limits': 'Finite exact checks complement written proofs; no empirical fit, statistical confidence, independent human certification or coordinator acceptance.'}
    json.dumps(summary, allow_nan=False)
    return summary


if __name__ == '__main__':
    if len(sys.argv) != 1:
        raise SystemExit('usage: python3 -B check_v13_c01.py')
    check()
