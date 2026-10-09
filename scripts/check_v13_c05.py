"""Quiet, bounded standard-library audit of the four-file V13-C05 package.

check(root=None) returns strict JSON data. Import and successful CLI write nothing.
Exact arithmetic and finite construction checks accompany separately audited proofs;
no finite enumeration is represented as a proof over unrestricted economies.
"""
from __future__ import annotations

from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from itertools import combinations, product
import json
import math
from pathlib import Path
import sys

FILES = (
    'content/chapters/v13-c05.html',
    'scripts/check_v13_c05.py',
    'content/reviews/v13-c05-sources.json',
    'content/reviews/v13-c05-author.json',
)
SOURCE_IDS = {'v05-c05-mit-welfare', 'v13-c05-border-welfare2016',
              'v13-c05-mit-socialchoice2010', 'v13-c05-borgers-aggregation2021'}
ROUTES = {'v13-c0'+str(i)+'.html' for i in (1, 2, 3, 4, 6)}


def need(condition, message):
    if not condition:
        raise ValueError(message)


def number(value):
    need(type(value) in (int, float, F), 'rational scalar excludes bool/string/complex')
    if type(value) is float:
        need(math.isfinite(value), 'finite scalar')
        value = F(str(value))
    else:
        value = F(value)
    need(abs(value) <= 10**6 and value.denominator <= 10**9, 'bounded rational domain')
    return value


def vector(values, n=None, limit=8):
    need(type(values) in (tuple, list) and 1 <= len(values) <= limit, 'bounded vector')
    need(n is None or len(values) == n, 'vector dimension')
    return tuple(number(x) for x in values)


def prices(values, positive=True):
    p = vector(values, 2)
    need(all(x > 0 for x in p) if positive else all(x >= 0 for x in p) and sum(p) > 0,
         'admissible price vector')
    return p


def dot(x, y):
    a = vector(x)
    b = vector(y, len(a))
    return sum((u*v for u, v in zip(a, b)), F(0))


def cd_demand(p, income, alpha):
    p = prices(p)
    m, a = number(income), number(alpha)
    need(m >= 0 and 0 < a < 1, 'nonnegative income and interior shares')
    return a*m/p[0], (1-a)*m/p[1]


def subsistence_demand(p, income, subsistence):
    p = prices(p)
    s = vector(subsistence, 2)
    need(all(x >= 0 for x in s), 'nonnegative subsistence')
    residual = number(income)-dot(p, s)
    need(residual >= 0, 'subsistence must be affordable')
    # The endpoint is returned explicitly; the differentiable theorem uses >0.
    return tuple(s[j]+residual/(2*p[j]) for j in range(2))


def ownership_ledger(p, endowments, shares, profit, target):
    p = prices(p, positive=False)
    need(type(endowments) in (tuple, list) and len(endowments) == 2, 'two owners')
    omega = tuple(vector(w, 2) for w in endowments)
    need(all(x >= 0 for w in omega for x in w), 'nonnegative endowments')
    theta = vector(shares, 2)
    need(all(x >= 0 for x in theta) and sum(theta) == 1, 'complete nonnegative ownership')
    pi = number(profit)
    need(type(target) in (tuple, list) and len(target) == 2, 'two target bundles')
    x = tuple(vector(row, 2) for row in target)
    need(all(t >= 0 for row in x for t in row), 'nonnegative target')
    base = tuple(dot(p, w)+share*pi for w, share in zip(omega, theta))
    wealth = tuple(dot(p, row) for row in x)
    return base, wealth, tuple(w-b for w, b in zip(wealth, base))


def ballots(rows, alternatives):
    need(type(alternatives) is str and 2 <= len(alternatives) <= 7 and
         len(set(alternatives)) == len(alternatives), 'distinct alternative labels')
    need(type(rows) in (tuple, list) and 1 <= len(rows) <= 9, 'bounded nonempty electorate')
    need(all(type(row) is str and len(row) == len(alternatives) and
             set(row) == set(alternatives) for row in rows), 'strict complete ballots')
    return tuple(rows)


def majority_counts(rows, alternatives):
    rows = ballots(rows, alternatives)
    return tuple(sum(row.index(a) < row.index(b) for row in rows)
                 for a, b in combinations(alternatives, 2))


def borda(rows, alternatives):
    rows = ballots(rows, alternatives)
    return tuple(sum(len(alternatives)-1-row.index(a) for row in rows) for a in alternatives)


def weak_order(ranks, n=3):
    need(type(ranks) in (list, tuple) and len(ranks) == n and 2 <= n <= 7,
         'weak-order dimension')
    need(all(type(r) is int and 0 <= r < n for r in ranks), 'finite integer rank labels')
    need(set(ranks) == set(range(max(ranks)+1)), 'consecutive rank levels')
    return tuple(ranks)


def relation(ranks, a, b):
    return (ranks[b] > ranks[a])-(ranks[b] < ranks[a])


def median_contests(policies, peaks):
    xs = vector(policies, limit=9)
    ts = vector(peaks, limit=9)
    need(all(a < b for a, b in zip(xs, xs[1:])), 'strict policy order')
    need(len(ts) % 2 == 1 and all(t in xs for t in ts), 'odd electorate with feasible peaks')
    median = sorted(ts)[len(ts)//2]
    contests = []
    for opponent in xs:
        if opponent == median:
            continue
        signs = tuple((abs(opponent-t) > abs(median-t))-
                      (abs(opponent-t) < abs(median-t)) for t in ts)
        contests.append((signs.count(1), signs.count(-1), signs.count(0)))
    return median, tuple(contests)


def weighted_resource(resource, coefficients):
    resource = number(resource)
    c = vector(coefficients, 2)
    need(resource > 0 and all(x > 0 for x in c), 'positive resource and coefficients')
    norm2 = sum(x*x for x in c)
    return tuple(resource*x*x/norm2 for x in c), resource*norm2


def unique_pairs(pairs):
    out = {}
    for key, value in pairs:
        need(key not in out, 'duplicate JSON key')
        out[key] = value
    return out


def reject_constants(value):
    raise ValueError('nonfinite JSON constant: '+value)


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=unique_pairs,
                      parse_constant=reject_constants)


def fmt(x):
    if isinstance(x, (tuple, list)):
        return '('+','.join(fmt(v) for v in x)+')'
    return str(x)


class Reader(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids, self.links, self.sources = [], [], []
        self.worked, self.prompts, self.solutions = [], [], []
        self.stack, self.anchors = [], {}
        self.exercise_depth = self.solution_depth = self.capture = None

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if 'id' in d:
            self.ids.append(d['id'])
        if 'href' in d:
            self.links.append(d['href'])
        if 'data-source' in d:
            self.sources.append(d['data-source'])
        classes = d.get('class', '').split()
        if tag == 'article' and 'worked' in classes:
            self.worked.append(d.get('id'))
        if tag == 'ol' and 'exercises' in classes:
            self.exercise_depth = len(self.stack)
        if tag == 'details' and 'solutions' in classes:
            self.solution_depth = len(self.stack)
        if tag == 'li' and self.exercise_depth is not None:
            self.prompts.append(d.get('id'))
        if 'data-solution-for' in d:
            need(self.solution_depth is not None, 'solution outside standard disclosure')
            self.solutions.append(d['data-solution-for'])
        if 'data-calc' in d:
            need(self.capture is None and d['data-calc'] not in self.anchors, 'unique numeric anchor')
            self.capture = d['data-calc']
            self.anchors[self.capture] = ''
        if tag not in {'br', 'hr', 'img', 'meta', 'link', 'input'}:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if tag == 'span' and self.capture is not None:
            self.capture = None
        need(bool(self.stack) and self.stack[-1] == tag, 'balanced HTML: '+tag)
        self.stack.pop()
        if tag == 'ol' and self.exercise_depth == len(self.stack):
            self.exercise_depth = None
        if tag == 'details' and self.solution_depth == len(self.stack):
            self.solution_depth = None

    def handle_data(self, data):
        if self.capture is not None:
            self.anchors[self.capture] += data


def check(root=None):
    root = Path(root).resolve() if root is not None else Path(__file__).resolve().parent.parent
    paths = tuple(root/name for name in FILES)
    before = tuple(p.read_bytes() for p in paths)
    counts = {'comparisons': 0, 'rejections': 0, 'arrow_auxiliary_profiles': 0,
              'arrow_partition_profiles': 0}

    def eq(actual, expected, label):
        counts['comparisons'] += 1
        need(actual == expected, label+': '+repr(actual)+' != '+repr(expected))

    def yes(condition, label):
        counts['comparisons'] += 1
        need(condition, label)

    def rejects(call, label):
        try:
            call()
        except (ValueError, TypeError):
            counts['rejections'] += 1
        else:
            raise ValueError('invalid domain accepted: '+label)

    reader = Reader()
    reader.feed(before[0].decode('utf-8'))
    reader.close()
    yes(not reader.stack, 'balanced fragment')
    eq(len(reader.ids), len(set(reader.ids)), 'unique namespace IDs')
    eq(reader.worked, ['v13-c05-case'+str(i) for i in range(1, 7)], 'six worked cases')
    prompts = ['v13-c05-ex'+str(i) for i in range(1, 13)]
    eq(reader.prompts, prompts, 'twelve exact prompts')
    eq(reader.solutions, prompts, 'twelve paired answers')
    eq(set(reader.sources), SOURCE_IDS, 'four reader source scopes')
    eq({x for x in reader.links if not x.startswith('https://')}, ROUTES,
       'flat prerequisites/successor, not runtime dependencies')
    sources, author = read_json(paths[2]), read_json(paths[3])
    eq({s['id'] for s in sources['proposals']}, SOURCE_IDS, 'source proposal IDs')
    for source in sources['proposals']:
        yes(bool(source['limits']), 'honest source limitations')
        if source['id'] != 'v05-c05-mit-welfare':
            eq(source['inspection']['actual_inspector'], 'ito_author', 'new source inspector')
    text_only = next(s for s in sources['proposals'] if 'borgers' in s['id'])
    eq(text_only['inspection']['actual_image_physical_pages'], [], 'no unavailable image claim')
    yes('retained_pdf' not in text_only, 'no unavailable PDF binding')
    reuse = next(s for s in sources['proposals'] if s['id'] == 'v05-c05-mit-welfare')
    eq(reuse['inspection']['mode'], 'prior_scope_reuse', 'prior inspection not claimed anew')
    eq(reuse['checked'], '2026-10-07', 'prior inspection date retained')
    binding = {x['path']: x for x in author['bindings']}
    eq(set(binding), set(FILES[:3]), 'three nonself runtime bindings')
    for name, raw in zip(FILES[:3], before[:3]):
        eq((binding[name]['bytes'], binding[name]['sha256']),
           (len(raw), sha256(raw).hexdigest()), 'exact author binding '+name)
    eq([x['id'] for x in author['exercise_audit']], prompts, 'all exact prompts audited')
    eq(author['open_findings'], [], 'no unresolved author finding')
    anchors = {}

    # 1. Demand shares, independent budget/FOC ratios, and the financed externality.
    p = (1, 1)
    endowments = ((5, 1), (1, 5))
    incomes = tuple(dot(p, w) for w in endowments)
    demands = tuple(cd_demand(p, m, a) for m, a in zip(incomes, (F(1,3), F(2,3))))
    eq(incomes, (6, 6), 'endowment values')
    eq(demands, ((2, 4), (4, 2)), 'exchange demands')
    eq(tuple(sum(row[j] for row in demands) for j in range(2)), (6, 6), 'physical exchange')
    for i, a in enumerate((F(1,3), F(2,3))):
        x = demands[i]
        eq(dot(p, x), incomes[i], 'exhausted private budget')
        eq(a/x[0], (1-a)/x[1], 'log marginal expenditure equality')
    eq((demands[0][0]*demands[0][1]**2, demands[1][0]**2*demands[1][1]),
       (32, 32), 'utility cubes')
    anchors['exchange-wealth'], anchors['exchange-allocation'] = fmt(incomes), fmt(demands)
    old = ((0, 3), (6, 0)); new = ((2, 2), (4, 0))
    def external_utility(x):
        return x[0][0]+2*x[0][1], x[1][0]-3*x[0][1]
    uold, unew = external_utility(old), external_utility(new)
    eq((uold, unew), ((6, -3), (6, -2)), 'omitted harm improvement')
    eq(tuple(new[i][0]-old[i][0] for i in range(2)), (2, -2), 'balanced compensation')
    eq((sum(row[0] for row in new), sum(row[1] for row in new)), (6, 2), 'available resources')
    yes(unew[0] == uold[0] and unew[1] > uold[1], 'Pareto improvement')
    anchors['external-before'], anchors['external-after'] = fmt(uold), fmt(unew)

    # 2. Global quadratic certificate and independently reconciled ownership books.
    p = (2, 1); omega = ((3, 1), (2, 2)); target = ((F(10,3), F(10,3)), (F(2,3), F(8,3)))
    for n in (F(0), F(1,2), F(1), F(3,2), F(2)):
        q = 4*n-n*n
        eq(q-2*n, 1-(n-1)**2, 'completed-square identity witness')
        yes(q-2*n <= 1, 'global certificate evaluated')
    net = (-1, 3); profit = dot(p, net)
    eq(profit, 1, 'firm profit')
    resources = tuple(sum(w[j] for w in omega)+net[j] for j in range(2))
    eq(resources, tuple(sum(x[j] for x in target) for j in range(2)), 'production resources')
    base, wealth, transfers = ownership_ledger(p, omega, (F(1,4), F(3,4)), profit, target)
    eq((base, wealth, transfers), ((F(29,4), F(27,4)), (10, 4), (F(11,4), F(-11,4))),
       'original profit ownership and transfers')
    eq(sum(transfers), 0, 'balanced transfer authority contract')
    eq(tuple(cd_demand(p, m, a) for m, a in zip(wealth, (F(2,3), F(1,3)))), target,
       'target is actual global demand')
    eq(sum(wealth), dot(p, resources), 'aggregate value conservation')
    anchors.update({'production-target': fmt(target), 'target-wealth': fmt(wealth),
                    'owner-income': fmt(base), 'target-transfers': fmt(transfers)})
    base2, wealth2, transfer2 = ownership_ledger(p, omega, (F(3,4), F(1,4)), profit, target)
    eq((base2, transfer2), ((F(31,4), F(25,4)), (F(9,4), F(-9,4))), 'changed ownership')
    eq((sum(transfer2), wealth2), (0, wealth), 'changed shares preserve funded target')
    anchors.update({'changed-owner-income': fmt(base2), 'changed-transfers': fmt(transfer2)})
    unfunded = tuple(w-dot(p, endow) for w, endow in zip(wealth, omega))
    eq(sum(unfunded), profit, 'omitted owner profit is false funding')
    anchors['ignored-profit-transfers'] = fmt(unfunded)
    scaled = ownership_ledger((6, 3), omega, (F(1,4), F(3,4)), 3*profit, target)
    eq(scaled, tuple(tuple(3*x for x in row) for row in (base, wealth, transfers)),
       'price normalization scales all money accounts')

    # 3. Boundary support and three complete nonconvex disposal branches.
    boundary_target = ((0, 0), (1, 1))
    zero_price_wealth = tuple(dot((1, 0), x) for x in boundary_target)
    anchors['boundary-wealth'] = fmt(zero_price_wealth)
    eq(zero_price_wealth, (0, 1), 'quasiequilibrium budgets')
    for t in (1, 2):
        eq(dot((1, 0), (0, t)), 0, 'free preferred bundle at zero wealth')
        yes(t > boundary_target[0][1], 'strict preference despite supporting cost equality')
    eq(tuple(dot((1, 1), x) for x in boundary_target), (0, 2), 'working alternative prices')
    plans = ((0, 0), (-1, 1), (-2, 3))
    consumption = tuple((2+y[0], y[1]) for y in plans)
    values = tuple(min(x) for x in consumption)
    eq(values, (0, 1, 0), 'all discrete branch maxima')
    # Normalize pr+pc=1: middle >= inactive needs pc>=1/2;
    # middle >= full needs pc<=1/3. This is a global infeasibility certificate.
    lower_pc, upper_pc = F(1,2), F(1,3)
    yes(lower_pc > upper_pc, 'nonnegative normalized supporting prices impossible')
    weight = F(2, 2+3)
    hull_net = tuple(weight*x for x in plans[2])
    hull_consumption = (2+hull_net[0], hull_net[1])
    eq(hull_consumption, (F(6,5), F(6,5)), 'explicit convexified resources')
    yes(all(not all(hull_net[j] <= plan[j] for j in range(2)) for plan in plans),
        'convexified plan unavailable on every original branch')
    yes(min(hull_consumption) > max(values), 'changed technology improves welfare')
    anchors.update({'discrete-plans': fmt(plans), 'discrete-utilities': fmt(values),
                    'convexified-weight': fmt(weight), 'convexified-bundle': fmt(hull_consumption)})

    # 4. Recompute all individual demand functions before totals or income slices.
    alphas = (F(1,4), F(3,4)); p = (2, 1)
    totals = []
    for incomes in ((8, 12), (12, 8)):
        ds = tuple(cd_demand(p, m, a) for m, a in zip(incomes, alphas))
        total = tuple(sum(row[j] for row in ds) for j in range(2))
        eq(dot(p, total), sum(incomes), 'redistribution retains total budget')
        totals.append(total)
    eq(tuple(totals), ((F(11,2), 9), (F(9,2), 11)), 'heterogeneous Engel response')
    eq(tuple(totals[1][j]-totals[0][j] for j in range(2)), (-1, 2), 'balanced transfer demand effect')
    slopes = tuple(cd_demand(p, 1, a) for a in alphas)
    eq(slopes, ((F(1,8), F(3,4)), (F(3,8), F(1,4))), 'different income slopes')
    anchors['aggregate-before'], anchors['aggregate-after'] = (fmt(x) for x in totals)
    s = ((1, 0), (0, 1)); common = (F(1,4), F(1,2))
    intercepts = tuple(tuple(row[j]-common[j]*dot(p, row) for j in range(2)) for row in s)
    eq(dot(p, common), 1, 'common Engel slope budget')
    eq(tuple(dot(p, row) for row in intercepts), (0, 0), 'affine intercept budgets')
    anchors['common-slope'], anchors['common-intercepts'] = fmt(common), fmt(intercepts)
    aggregates = []
    for incomes, key in (((8, 12), 'subsistence-before'), ((12, 8), 'subsistence-after')):
        ds = tuple(subsistence_demand(p, m, row) for m, row in zip(incomes, s))
        for i, (m, row) in enumerate(zip(incomes, ds)):
            eq(dot(p, row), m, 'subsistence expenditure')
            eq(p[0]*(row[0]-s[i][0]), p[1]*(row[1]-s[i][1]), 'equal surplus expenditure')
        aggregate = tuple(sum(row[j] for row in ds) for j in range(2))
        eq(aggregate, subsistence_demand(p, sum(incomes), (1, 1)), 'family representative demand')
        aggregates.append(aggregate); anchors[key] = fmt(ds)
    eq(aggregates[0], aggregates[1], 'distribution independence')
    anchors['subsistence-total'] = fmt(aggregates[0])
    for p2, incomes in (((1, 3), (7, 10)), ((3, 2), (8, 11))):
        ds = tuple(subsistence_demand(p2, m, row) for m, row in zip(incomes, s))
        eq(tuple(sum(row[j] for row in ds) for j in range(2)),
           subsistence_demand(p2, sum(incomes), (1, 1)), 'changed-price family, recomputed budgets')
    for row in s:
        threshold = dot(p, row)
        eq(subsistence_demand(p, threshold, row), row, 'exact subsistence endpoint')
        rejects(lambda row=row, threshold=threshold:subsistence_demand(p, threshold-F(1,10), row),
                'unaffordable subsistence')
    for m in (F(9,20), F(1,2), F(11,20)):
        n = 1-m
        d11, d21 = m*m/4, (1-(1-n)**2)/4
        eq((d11+d21, (m-d11)+(n-d21)), (F(1,4), F(3,4)), 'single-slice invariant')
        yes(d11 > 0 and m-d11 > 0 and d21 > 0 and n-d21 > 0, 'positive sliced paths')
    yes(F(9,20)/2 != F(11,20)/2, 'slice derivatives not constant on product')
    # A local negative slope can still satisfy positivity and budget exhaustion.
    for m in (F(9,10), F(11,10)):
        d = (1-m/2, 3*m/2-1)
        yes(all(x > 0 for x in d), 'local inferior-good quantities positive')
        eq(sum(d), m, 'local inferior-good budget')

    # 5. Full reported profiles; finite checks of the actual Arrow constructions.
    ranks4 = ('ABCD', 'ABDC', 'BCAD', 'BCDA', 'CABD')
    mc = majority_counts(ranks4, 'ABCD')
    eq(mc, (3, 2, 4, 4, 5, 4), 'six original pairwise counts')
    yes(mc[0] > 2 and mc[3] > 2 and 5-mc[1] > 2, 'strict majority cycle')
    anchors['majority-counts'] = fmt(mc)
    first = ('ABC',)*3+('BCA',)*2; second = ('ACB',)*3+('BAC',)*2
    b1, b2 = borda(first, 'ABC'), borda(second, 'ABC')
    eq((b1, b2), ((6, 7, 2), (8, 4, 3)), 'Borda totals')
    eq(tuple(row.index('A') < row.index('B') for row in first),
       tuple(row.index('A') < row.index('B') for row in second), 'identical pair information')
    yes(b1[0] < b1[1] and b2[0] > b2[1], 'IIA reversal on same alternative set')
    # Independent accumulation by ballot positions rather than index lookup.
    for rows, score in ((first, b1), (second, b2)):
        table = dict.fromkeys('ABC', 0)
        for row in rows:
            for label, points in zip(row, (2, 1, 0)):
                table[label] += points
        eq(tuple(table[x] for x in 'ABC'), score, 'independent position-score accumulation')
    anchors['borda-before'], anchors['borda-after'] = fmt(b1), fmt(b2)
    orders = tuple(row for row in product(range(3), repeat=3)
                   if set(row) == set(range(max(row)+1)))
    eq(len(orders), 13, 'all weak orders on three labels')
    # Almost (a,b) -> strong (a,c) and strong (c,b), including every outsider tie.
    for members in product((False, True), repeat=3):
        if not any(members):
            continue
        outside = [i for i, member in enumerate(members) if not member]
        for comparisons in product((-1, 0, 1), repeat=len(outside)):
            prescribed = dict(zip(outside, comparisons))
            auxiliary1, auxiliary2 = [], []
            for i, member in enumerate(members):
                if member:
                    auxiliary1.append((0, 1, 2))
                    auxiliary2.append((1, 2, 0))
                else:
                    r = prescribed[i]
                    auxiliary1.append({1:(1,0,2), 0:(1,0,1), -1:(2,0,1)}[r])
                    auxiliary2.append({1:(2,1,0), 0:(1,0,0), -1:(2,0,1)}[r])
            for aux, unanimous, preserved in ((auxiliary1,(1,2),(0,2)),
                                             (auxiliary2,(2,0),(2,1))):
                counts['arrow_auxiliary_profiles'] += 1
                yes(all(weak_order(row) in orders for row in aux), 'valid auxiliary weak orders')
                eq(tuple(relation(row,0,1) == 1 for row in aux), members, 'exact almost-decisive split')
                yes(all(relation(row,*unanimous) == 1 for row in aux), 'Pareto comparison in propagation')
                eq(tuple(relation(aux[i],*preserved) for i in outside), comparisons,
                   'outsider comparison including indifference preserved')
    for initial in ((a,b) for a in range(3) for b in range(3) if a != b):
        reached = {initial}
        for _ in range(3):
            reached |= {(a,c) for a,b in tuple(reached) for c in range(3) if c not in (a,b)}
            reached |= {(c,b) for a,b in tuple(reached) for c in range(3) if c not in (a,b)}
        eq(len(reached), 6, 'all ordered directions reached with only three alternatives')
    # U, V, outside labels. All nonempty U/V partitions of a three-voter set.
    for groups in product(range(3), repeat=3):
        if 0 not in groups or 1 not in groups:
            continue
        counts['arrow_partition_profiles'] += 1
        aux = tuple(((0,1,2),(1,2,0),(2,0,1))[g] for g in groups)
        eq(tuple(relation(row,0,1) == 1 for row in aux), tuple(g != 2 for g in groups), 'S supports a/b')
        eq(tuple(relation(row,2,1) == 1 for row in aux), tuple(g == 1 for g in groups), 'V supports c/b')
        eq(tuple(relation(row,0,2) == 1 for row in aux), tuple(g == 0 for g in groups), 'U supports a/c')
    tied_branch = False
    for social in orders:
        if relation(social,0,1) == 1 and relation(social,2,1) != 1:
            yes(relation(social,1,2) >= 0 and relation(social,0,2) == 1,
                'weak reverse branch entails a strictly above c')
            tied_branch |= relation(social,1,2) == 0
    yes(tied_branch, 'social equality branch actually exercised')
    policies = tuple(range(7)); peaks = (0,2,3,5,6)
    median, contests = median_contests(policies, peaks)
    eq((median, contests), (3,((4,1,0),(3,1,1),(3,2,0),(3,2,0),(3,2,0),(3,2,0))),
       'every median contest including tie')
    anchors['median-votes'] = fmt(contests)
    for changed in ((0,3,3,5,6), (2,2,2), (0,0,0,1,6)):
        median, contests = median_contests(policies, changed)
        yes(all(favor > len(changed)//2 for favor, _, _ in contests), 'repeated peaks strict majority')
        yes(sum(t >= median for t in changed) > len(changed)//2 and
            sum(t <= median for t in changed) > len(changed)//2, 'median-equal voters counted')

    # 6. Global Cauchy-Schwarz equality and the max-min feasibility certificate.
    choices = []
    for c in ((1,2), (2,2), (4,2)):
        x, bound2 = weighted_resource(12, c)
        eq(sum(x), 12, 'full normative resource use')
        eq(x[0]*c[1]**2, x[1]*c[0]**2, 'Cauchy-Schwarz equality ratio')
        # At the equality ratio, the cross term is rational without rounded roots.
        objective2 = c[0]**2*x[0]+c[1]**2*x[1]+2*c[0]**2*x[1]
        eq(objective2, bound2, 'attained squared global bound')
        choices.append(x)
    eq(tuple(choices), ((F(12,5),F(48,5)), (6,6), (F(48,5),F(12,5))),
       'normative choices and individual scale change')
    t2 = F(12)/(1+F(1,4))
    maxmin = (t2, t2/4)
    eq(sum(maxmin), 12, 'max-min global resource lower bound attained')
    eq(maxmin[0], 4*maxmin[1], 'equal declared utility levels')
    anchors['utilitarian-allocation'], anchors['weighted-allocation'] = fmt(choices[0]), fmt(choices[1])
    anchors['maxmin-allocation'] = fmt(maxmin)
    menu = ((1,4), (2,2))
    minima = tuple(min(row) for row in menu)
    shifted = tuple(min(row[0]+3,row[1]) for row in menu)
    eq((minima, shifted), ((1,2),(4,2)), 'max-min origin reversal')
    eq(tuple(row[0]+3-(menu[0][0]+3) for row in menu),
       tuple(row[0]-menu[0][0] for row in menu), 'personal difference preserved by origin shift')
    eq(tuple(min(row) for row in ((1,2),(1,3))), (1,1), 'max-min alone allows dominated tie')
    anchors['origin-before'], anchors['origin-after'] = fmt(minima), fmt(shifted)

    # Purposeful supported-domain and strict-JSON rejection; no random grid.
    for bad in (True, '1', complex(1,0), float('nan'), float('inf'), 10**7, F(1,10**10)):
        rejects(lambda bad=bad:number(bad), 'bad scalar')
    for bad in ([], [1], [1,0], [-1,2], [1,2,3], [True,1]):
        rejects(lambda bad=bad:prices(bad), 'bad positive price pair')
    rejects(lambda:prices((0,0),False), 'zero support normal')
    for m, a in ((-1,F(1,2)), (1,0), (1,1), (1,2)):
        rejects(lambda m=m,a=a:cd_demand((1,1),m,a), 'demand domain')
    for shares in ((F(1,4),F(1,4)), (-1,2), (1,), (True,0)):
        rejects(lambda shares=shares:ownership_ledger((2,1),omega,shares,1,target), 'ownership domain')
    rejects(lambda:ownership_ledger((2,1),((-1,0),(1,1)),(F(1,2),)*2,1,target), 'negative endowment')
    for rows, labels in (([], 'ABC'), (['AAB'],'ABC'), (['AB'],'ABC'), (['ABC'],'AAB'),
                         (['ABC']*10,'ABC'), ([1],'ABC')):
        rejects(lambda rows=rows,labels=labels:majority_counts(rows,labels), 'strict ballot domain')
    for ranks in ((0,2,2), (True,1,2), (0,1), (-1,0,1), (0,1,3)):
        rejects(lambda ranks=ranks:weak_order(ranks), 'weak order domain')
    for xs, ts in (((0,1,1),(0,)), ((1,0),(0,)), ((0,1),(0,1)), ((0,1),(2,))):
        rejects(lambda xs=xs,ts=ts:median_contests(xs,ts), 'median domain')
    for resource, c in ((0,(1,2)), (-1,(1,2)), (12,(0,2)), (12,(1,)), (12,(1,-2))):
        rejects(lambda resource=resource,c=c:weighted_resource(resource,c), 'normative domain')
    for invalid in ('{"x":NaN}', '{"x":Infinity}', '{"x":1,"x":2}'):
        rejects(lambda invalid=invalid:json.loads(invalid,object_pairs_hook=unique_pairs,
                                                  parse_constant=reject_constants), 'strict JSON')
    eq(reader.anchors, anchors, 'all independently reconstructed printed exact anchors')
    eq(tuple(p.read_bytes() for p in paths), before, 'four runtime payloads unchanged')
    result = {'chapter':'v13-c05','status':'passed','worked_cases':6,'solved_exercises':12,
              'numeric_anchors':len(anchors), **counts,
              'scope':'Exact economic witnesses and finite proof constructions; universal proofs audited separately.',
              'runtime_payloads':list(FILES),'writes':0}
    json.dumps(result,allow_nan=False)
    return result


if __name__ == '__main__':
    need(len(sys.argv) == 1, 'CLI takes no arguments and writes nothing')
    check()
