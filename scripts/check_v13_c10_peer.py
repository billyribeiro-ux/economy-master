#!/usr/bin/env python3
"""Independent C10 peer oracle: exact finite choices and polygon moments.

Read-only six-file runtime. The author's checker and blueprint answers are never
imported or executed. Universal proof claims have a separate manuscript audit.
"""
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from itertools import product
import json
from pathlib import Path
import re
import sys


AUTHORS = ('content/chapters/v13-c10.html', 'scripts/check_v13_c10.py',
           'content/reviews/v13-c10-sources.json', 'content/reviews/v13-c10-author.json')
SELF, RECORD = 'scripts/check_v13_c10_peer.py', 'content/reviews/v13-c10-peer.json'
SOURCES = {
    'v05-c11-levin-auctions': 'https://web.stanford.edu/~jdlevin/Econ%20286/Auctions.pdf',
    'v13-c10-ozdaglar-mechanism2010': 'https://ocw.mit.edu/courses/6-254-game-theory-with-engineering-applications-spring-2010/4bad561319453ce5c37ff094549c5486_MIT6_254S10_lec20.pdf',
    'v13-c10-roughgarden-revenue2013': 'https://www.timroughgarden.org/f13/l/l5.pdf',
}


def need(ok, reason):
    if not ok: raise ValueError(reason)


def q(x):
    need(type(x) in (int, F), 'exact rational input')
    x = F(x)
    need(abs(x) <= 10**6 and x.denominator <= 10**9, 'bounded rational witness')
    return x


def row(x, n=None):
    need(type(x) in (tuple, list) and 1 <= len(x) <= 8, 'bounded vector')
    need(n is None or len(x) == n, 'vector dimension')
    return tuple(q(v) for v in x)


def law(x, n=None):
    x = row(x, n); need(min(x) > 0 and sum(x) == 1, 'positive normalized finite law')
    return x


def assignment(values, cost=1):
    need(type(values) in (tuple, list) and 1 <= len(values) <= 4, 'one to four buyers')
    first = row(values[0]); need(len(first) <= 3, 'one to three goods')
    values = tuple(row(v, len(first)) for v in values)
    cost = q(cost); need(cost >= 0 and min(v for r in values for v in r) >= 0, 'nonnegative assignment primitives')
    n, goods = len(values), len(first)
    plans = tuple(plan for plan in product(range(-1, goods), repeat=n)
                  if len([g for g in plan if g >= 0]) == len(set(g for g in plan if g >= 0)))
    def score(plan):
        return sum((values[i][g]-cost for i, g in enumerate(plan) if g >= 0), F(0))
    # Fixed lexicographic priority is independent of reports.
    best = max(plans, key=score); welfare = score(best)
    received = tuple(values[i][g] if g >= 0 else F(0) for i, g in enumerate(best))
    resources = cost*sum(g >= 0 for g in best)
    without = tuple(max(score(plan) for plan in plans if plan[i] == -1) for i in range(n))
    payments = tuple(without[i]-(welfare-received[i]) for i in range(n))
    utility = tuple(received[i]-payments[i] for i in range(n))
    receipts = sum(payments)
    return {'plan': best, 'count': len(plans), 'welfare': welfare, 'h': without,
            'payments': payments, 'utility': utility, 'receipts': receipts,
            'cost': resources, 'net': receipts-resources}


def project(values, cost, opening):
    values = row(values); cost, opening = q(cost), q(opening)
    need(min(values) >= 0 and cost >= 0 and opening >= cost, 'nonnegative benefits and endowed full-cost financing')
    build = sum(values) >= cost
    payments = tuple(max(F(0), sum(values)-v-cost)-(sum(values)-v-cost)*build for v in values)
    utility = tuple(v*build-p for v, p in zip(values, payments))
    spent, receipts = cost*build, sum(payments)
    return {'build': build, 'payments': payments, 'utility': utility, 'receipts': receipts,
            'deficit': spent-receipts, 'surplus': sum(values)*build-spent,
            'cash': opening+receipts-spent, 'change': receipts-spent}


def price_lottery(prices, masses, value, report=None):
    prices, masses = row(prices), law(masses)
    need(len(prices) == len(masses) and 0 <= prices[0] and
         all(x < y for x, y in zip(prices, prices[1:])) and prices[-1] <= 10, 'ordered prices on declared support')
    value = q(value); report = value if report is None else q(report)
    need(0 <= value <= 10 and 0 <= report <= 10, 'type and report support')
    x = sum((p for t, p in zip(prices, masses) if report >= t), F(0))
    payment = sum((t*p for t, p in zip(prices, masses) if report >= t), F(0))
    return x, payment, value*x-payment


def sidebet(joint, own, report):
    joint = law(joint, 4)
    need(type(own) is int and type(report) is int and own in (0, 2) and report in (0, 2), 'binary own type/report')
    cells = tuple(product((0, 2), repeat=2))
    mass = sum(p for p, (x, _) in zip(joint, cells) if x == own)
    pay = sum(p*(report-1)*(y-1) for p, (x, y) in zip(joint, cells) if x == own)/mass
    match = sum(p for p, (x, y) in zip(joint, cells) if x == own and y == own)/mass
    return pay, F(own, 2)-pay, match


def clip(poly, normal, threshold):
    need(type(poly) in (tuple, list) and len(poly) <= 12, 'bounded convex polygon')
    poly = tuple(row(point, 2) for point in poly)
    a, b = row(normal, 2); threshold = q(threshold)
    need(a != 0 or b != 0, 'nonzero halfspace normal')
    if not poly: return ()
    out = []
    for start, end in zip(poly, poly[1:]+poly[:1]):
        ds = a*start[0]+b*start[1]-threshold
        de = a*end[0]+b*end[1]-threshold
        if ds >= 0: out.append(start)
        if (ds < 0 <= de) or (de < 0 <= ds):
            weight = ds/(ds-de)
            out.append(tuple(start[j]+weight*(end[j]-start[j]) for j in (0, 1)))
    clean = []
    for point in out:
        if not clean or point != clean[-1]: clean.append(point)
    if len(clean) > 1 and clean[0] == clean[-1]: clean.pop()
    return tuple(clean)


def moments(poly):
    """Area and first moments by triangulating a counterclockwise polygon."""
    if len(poly) < 3: return F(0), F(0), F(0)
    area = mx = my = F(0)
    a = poly[0]
    for b, c in zip(poly[1:-1], poly[2:]):
        part = ((b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]))/2
        need(part >= 0, 'counterclockwise convex triangulation')
        area += part; mx += part*(a[0]+b[0]+c[0])/3; my += part*(a[1]+b[1]+c[1])/3
    return area, mx, my


def uniform_regions(supports, cost=0):
    a, b = row(supports, 2); c = q(cost)
    need(a > 0 and b > 0 and c >= 0, 'positive uniform supports and nonnegative delivery cost')
    rectangle = ((F(0), F(0)), (a, F(0)), (a, b), (F(0), b))
    t1, t2, shift = (a+c)/2, (b+c)/2, (a-b)/2
    first = clip(clip(rectangle, (1, 0), t1), (1, -1), shift)
    second = clip(clip(rectangle, (0, 1), t2), (-1, 1), -shift)
    # Critical payment is constant while the rival virtual value is below c;
    # otherwise it is affine in the rival value. Exact triangles integrate each.
    low1, high1 = clip(first, (0, -1), -t2), clip(first, (0, 1), t2)
    low2, high2 = clip(second, (-1, 0), -t1), clip(second, (1, 0), t1)
    m1, m2 = moments(first), moments(second)
    ml1, mh1, ml2, mh2 = (moments(p) for p in (low1, high1, low2, high2))
    payments = ((t1*ml1[0]+mh1[2]+shift*mh1[0])/(a*b),
                (t2*ml2[0]+mh2[1]-shift*mh2[0])/(a*b))
    values = (m1[1]/(a*b), m2[2]/(a*b))
    sale = (m1[0]+m2[0])/(a*b)
    virtual_profit = (2*m1[1]-(a+c)*m1[0]+2*m2[2]-(b+c)*m2[0])/(a*b)
    efficient = (moments(clip(rectangle, (1, -1), 0))[1]
                 +moments(clip(rectangle, (-1, 1), 0))[2])/(a*b)
    return {'payments': payments, 'sale': sale, 'values': values, 'value': sum(values),
            'receipts': sum(payments), 'cost': c*sale, 'profit': sum(payments)-c*sale,
            'virtual_profit': virtual_profit, 'rent': sum(values)-sum(payments),
            'efficient': efficient, 'efficient_receipts': (a+b)/2-efficient}


def uniform_profile(supports, values, cost=0):
    a, b = row(supports, 2); x, y = row(values, 2); c = q(cost)
    need(a > 0 and b > 0 and 0 <= x <= a and 0 <= y <= b and c >= 0, 'uniform profile domain')
    virtuals = 2*x-a, 2*y-b
    if max(virtuals) < c: return None, F(0), F(0)
    if virtuals[0] >= virtuals[1]:
        payment = max((a+c)/2, y+(a-b)/2); return 0, payment, x-payment
    payment = max((b+c)/2, x+(b-a)/2); return 1, payment, y-payment


def power(n, value=5, support=10, alpha=2):
    need(type(n) is int and 2 <= n <= 4 and type(alpha) is int and 1 <= alpha <= 3, 'finite power auction scope')
    value, h = q(value), q(support); need(0 < h <= 100 and 0 <= value <= h, 'power type support')
    k = alpha*(n-1); slope = F(k, k+1)
    allocation = (value/h)**k; fp = slope*value; payment = fp*allocation
    utility = value*allocation-payment
    max_value = h*F(alpha*n, alpha*n+1)
    fp_receipts = slope*max_value
    # Integrate all bids against each own-type density, independently of the
    # winner. The second-price integral uses the second-order-statistic density.
    ap_receipts = n*slope*F(alpha, alpha+k+1)*h
    sp_receipts = n*(n-1)*alpha*h*(F(1, k+1)-F(1, alpha*n+1))
    return {'k': k, 'slope': slope, 'fp': fp, 'x': allocation, 'p': payment, 'u': utility,
            'max': max_value, 'revenue': fp_receipts, 'allpay_revenue': ap_receipts,
            'second_revenue': sp_receipts, 'rent': max_value-fp_receipts}


def imitated_payoff(value, imitation, n=3, allpay=False):
    value, z = q(value), q(imitation)
    need(type(allpay) is bool and 0 <= z <= 10, 'declared report and format')
    a = power(n, value); winning = (z/10)**a['k']
    bid = a['slope']*z*winning if allpay else a['slope']*z
    return value*winning-bid if allpay else (value-bid)*winning


def cara(gain):
    gain = q(gain); exponent = -5*gain
    need(exponent.denominator == 1 and abs(exponent) <= 64, 'exact dyadic CARA witness')
    return 1-F(2)**int(exponent)


class Audit:
    def __init__(self): self.comparisons = self.rejections = 0
    def eq(self, x, y, why):
        self.comparisons += 1; need(x == y, why+': '+repr(x)+' != '+repr(y))
    def yes(self, x, why): self.eq(bool(x), True, why)
    def reject(self, call, *args):
        try: call(*args)
        except (ValueError, TypeError): self.rejections += 1; return
        raise ValueError('invalid domain accepted: '+call.__name__)


def derive(audit):
    inputs = {'w1-values': ((9, 4), (8, 7), (3, 6)), 'w1-cost': 1,
              'w2-cost': 12, 'w2-values': (7, 6, 4), 'w2-endowment': 12,
              'w3-lottery': (2, 7, F(1, 3)), 'w3-sidebet': ((0, 2), (F(1, 2), F(1, 2))),
              'w4-supports': (6, 12), 'w4-profile': (5, 7),
              'w5-law': 'F(v)=(v/10)², 0≤v≤10; n=3',
              'w6-utility': 'u(z)=1−2^(−5z), z∈ℝ', 'w6-deviation': F(24, 5),
              'e1-rivals': (2, 3), 'e2-b-value': 8, 'e3-values': (8, 3, 2),
              'e5-probabilities': (F(3, 8), F(1, 8), F(1, 8), F(3, 8)),
              'e6-profiles': ((4, 8), (6, 9)), 'e7-support': '[0,8]',
              'e8-cost': 2, 'e9-n': 2, 'e10-fee': F(2, 7)}
    out = {}
    w1 = assignment(inputs['w1-values'], inputs['w1-cost'])
    audit.eq(w1['plan'], (0, 1, -1), 'direct full assignment from buyer choices')
    out.update({'w1-count': w1['count'], 'w1-allocation': 'A→1, B→2', 'w1-welfare': w1['welfare'],
                'w1-h': w1['h'], 'w1-payments': w1['payments'], 'w1-utilities': w1['utility'],
                'w1-accounts': (w1['receipts'], w1['cost'], w1['net'])})
    changed = assignment(((9, 4), (8, 7), (3, inputs['e2-b-value'])))
    audit.eq(changed['plan'], (0, -1, 1), 'changed multidimensional value changes recipient')
    out.update({'e2-h': changed['h'], 'e2-payments': changed['payments'], 'e2-utilities': changed['utility'],
                'e2-accounts': (changed['receipts'], changed['cost'], changed['net']), 'e2-surplus': changed['welfare']})
    for result in (w1, changed):
        audit.eq(sum(result['utility'])+result['net'], result['welfare'], 'payments cancel and resource cost occurs once')
        audit.yes(min(result['utility']) >= 0, 'qualified pivot participation')
    single = assignment(tuple((v[0],) for v in inputs['w1-values']))
    out['w1-single-price'], out['w1-single-surplus'] = single['payments'][0], single['welfare']
    reports = ((0, 0), (20, 0), (0, 20))
    for buyer in range(3):
        for report in reports:
            announced = list(inputs['w1-values']); announced[buyer] = report
            result = assignment(announced); good = result['plan'][buyer]
            true_value = inputs['w1-values'][buyer][good] if good >= 0 else 0
            audit.yes(true_value-result['payments'][buyer] <= w1['utility'][buyer], 'finite changed-report Groves witness')

    for prefix, vals in (('w2', inputs['w2-values']), ('e3', inputs['e3-values'])):
        p = project(vals, inputs['w2-cost'], inputs['w2-endowment'])
        out.update({prefix+'-payments': p['payments'], prefix+'-utilities': p['utility'],
                    prefix+'-deficit': p['deficit'], prefix+'-surplus': p['surplus'],
                    prefix+('-closing-cash' if prefix == 'w2' else '-cash'): p['cash']})
        audit.eq(sum(p['utility'])+p['change'], p['surplus'], 'endowed public-project consolidated account')
        audit.eq(p['cash']-inputs['w2-endowment'], p['change'], 'closing balance versus wealth change')
    out['e3-gain'] = 0-(inputs['e3-values'][2]-4)
    audit.yes(sum(inputs['e3-values'][:2]) < 12 <= sum(inputs['e3-values']), 'equal-fee deviation actually cancels construction')
    audit.eq(project((4, 4, 4), 12, 12)['build'], True, 'fixed build-at-equality priority')

    for prefix, prices, masses, probes in (
            ('w3', (2, 7), (F(1, 3), F(2, 3)), (5, 7)),
            ('e4', (3, 8), (F(1, 4), F(3, 4)), (6, 9))):
        out[prefix+'-payments'] = tuple(price_lottery(prices, masses, v)[1] for v in (0, prices[0], prices[1]))
        keys = ('w3-type5', 'w3-type7') if prefix == 'w3' else ('e4-six', 'e4-nine')
        for key, v in zip(keys, probes): out[key] = price_lottery(prices, masses, v)
        witnesses = (F(0), F(prices[0]), (F(prices[0])+prices[1])/2, F(prices[1]), F(10))
        for v in witnesses:
            truthful = price_lottery(prices, masses, v)
            rent_integral = sum(m*max(F(0), v-t) for t, m in zip(prices, masses))
            audit.eq(truthful[2], rent_integral, 'step allocation rent integral includes both jumps')
            for report in witnesses:
                audit.yes(price_lottery(prices, masses, v, report)[2] <= truthful[2], 'all ordered finite report witnesses')
    out['w3-expost-gain'] = (0-(-1))-(0-1)
    independent = (F(1, 4),)*4
    correlated = inputs['e5-probabilities']
    for own in (0, 2):
        for report in (0, 2): audit.eq(sidebet(independent, own, report)[0], 0, 'independent side-bet interim payments')
        actual, opposite = sidebet(correlated, own, own), sidebet(correlated, own, 2-own)
        audit.eq((actual[0], opposite[0]), (F(1, 2), -F(1, 2)), 'false report keeps the true conditional law')
        out['e5-match'], out['e5-payments'], out['e5-gain'] = actual[2], (actual[0], opposite[0]), opposite[1]-actual[1]
    audit.eq((sum(correlated[:2]), sum(correlated[2:]), correlated[0]+correlated[2]),
             (F(1, 2),)*3, 'dependence changes while both fair marginals remain fixed')

    base = uniform_regions(inputs['w4-supports'])
    out.update({'w4-revenue': base['receipts'], 'w4-payment-parts': base['payments'], 'w4-sale': base['sale'],
                'w4-value-parts': base['values'], 'w4-value': base['value'], 'w4-rent': base['rent'],
                'w4-efficient': base['efficient'], 'w4-efficient-revenue': base['efficient_receipts'],
                'w4-surplus-loss': base['efficient']-base['value']})
    out['w4-profile-price'] = uniform_profile(inputs['w4-supports'], inputs['w4-profile'])[1]
    profiles = [uniform_profile(inputs['w4-supports'], v) for v in inputs['e6-profiles']]
    out['e6-price1'], out['e6-price2'] = profiles[0][1], profiles[1][1]
    audit.eq(tuple(x[0] for x in profiles), (1, 0), 'strict virtual rank and tie priority are distinct')
    liar = uniform_profile(inputs['w4-supports'], (6, F(91, 10)))
    out['e6-lie-utility'] = F(9)-liar[1]
    audit.eq(liar[0], 1, 'higher equality report changes the winner')
    audit.eq(uniform_profile((6, 12), (3, 6)), (0, F(3), F(0)), 'zero virtual tie sells with fixed priority')
    audit.eq(uniform_profile((6, 12), (0, 0)), (None, F(0), F(0)), 'no-sale lower endpoints')
    equal = uniform_regions((8, 8))
    out.update({'e7-reserve': F(8, 2), 'e7-sale': equal['sale'], 'e7-revenue': equal['receipts'],
                'e7-value': equal['value'], 'e7-rent': equal['rent'], 'e7-zero-revenue': equal['efficient_receipts'],
                'e7-zero-value': equal['efficient'], 'e7-zero-rent': equal['efficient']-equal['efficient_receipts']})
    costly = uniform_regions(inputs['w4-supports'], inputs['e8-cost'])
    out.update({'e8-sale': costly['sale'], 'e8-payment-parts': costly['payments'], 'e8-receipts': costly['receipts'],
                'e8-expected-cost': costly['cost'], 'e8-profit': costly['profit']})
    for result in (base, equal, costly):
        audit.eq(result['profit'], result['virtual_profit'], 'actual critical-price receipts less delivery cost match virtual-profit integral')
        audit.eq(result['rent']+result['profit'], result['value']-result['cost'], 'auction resource identity')
        audit.yes(result['sale'] <= 1 and min(result['payments']) >= 0, 'nonnegative receipts and feasible sale mass')
    audit.eq(uniform_regions((6, 12), 13)['sale'], 0, 'valid high cost eliminates every sale')
    # A regular, strictly increasing virtual function need not attain zero.
    audit.eq(F(1, 4)*1+F(3, 2)*F(1, 2), 1, 'piecewise density on [0,3/2] integrates to one')
    audit.eq((2*F(1)-4, 2*F(1)-F(3, 2)), (-2, F(1, 2)), 'regular virtual value jumps across zero at1')
    audit.yes(F(2) >= 1 and F(3, 4) < 1, 'both formal zero roots lie outside their density branches')
    audit.eq(F(0)**2, 0, 'power density endpoint requires integral payments, not a density ratio')

    for n, prefix in ((3, 'w5'), (inputs['e9-n'], 'e9')):
        result = power(n)
        out[prefix+('-type5' if n == 3 else '-five')] = (result['fp'], result['x'], result['p'], result['u'])
        out[prefix+'-max'], out[prefix+'-revenue'], out[prefix+'-rent'] = result['max'], result['revenue'], result['rent']
        audit.eq((result['allpay_revenue'], result['second_revenue']), (result['revenue'],)*2, 'three separately integrated receipt accounts')
        k, slope = result['k'], result['slope']
        audit.eq((k+1)*slope, k, 'exact derivative coefficients factor as k z^(k-1)(v-z)')
        for v in (0, 5, 10):
            optimum = imitated_payoff(v, v, n)
            for z in (0, F(5, 2), 5, 10):
                fp, ap = imitated_payoff(v, z, n), imitated_payoff(v, z, n, True)
                audit.eq(fp, ap, 'same imitated-type risk-neutral objective under different payment timing')
                audit.yes(fp <= optimum, 'global-boundary payoff witnesses')
            above = slope*10+1
            audit.yes(v-above < v-slope*10 <= optimum, 'over-support bids lose against the already-tested endpoint')
        audit.eq((power(n, 0)['p'], power(n, 0)['u']), (0, 0), 'payment and utility at zero need no density division')
    original = power(3)
    out['w5-per-bidder-rent'] = original['rent']/3
    out['e1-interim'] = (original['x'], original['p'], original['u'])
    rival_bid = original['slope']*max(inputs['e1-rivals'])
    audit.yes(original['slope']*4 > rival_bid, 'misreport still wins against the exact rival reports')
    out['e1-lie-utility'] = 5-original['slope']*4
    out['e1-gain'] = out['e1-lie-utility']-(5-original['fp'])
    fee = inputs['e10-fee']
    out['e10-revenue'], out['e10-rent'], out['e10-bottom'] = original['revenue']+3*fee, original['rent']-3*fee, -fee
    audit.eq(out['e10-revenue']+out['e10-rent'], original['max'], 'compulsory fee changes receipts and boundary rent without creating value')
    audit.yes(out['e10-bottom'] < 0, 'compulsory game no longer satisfies interim IR')
    dev = inputs['w6-deviation']; z = dev/original['slope']
    probability = (z/10)**original['k']; gain = 5-dev
    out['w6-candidate'] = original['x']*cara(5-original['fp'])
    out['w6-deviation-utility'] = probability*cara(gain)
    out['w6-gain'] = out['w6-deviation-utility']-out['w6-candidate']
    out['w6-money'] = (original['u'], probability*gain)
    audit.yes(out['w6-gain'] > 0 and out['w6-money'][1] < out['w6-money'][0], 'strict CARA deviation differs from money ranking')
    audit.yes(cara(1)-F(5, 32) > 0, 'ln2<1 gives a strict positive lower bound on the tangent bracket atv5')
    audit.yes(cara(-1) < cara(0) < cara(1), 'CARA includes losses without an overbid-domain gap')
    for rival in (4, 5, 6):
        truth = max(F(0), 5-rival)
        for win in (False, True):
            gain = F(5-rival)*win
            audit.yes(cara(truth) >= cara(gain), 'second-price statewise dominance survives the utility change')
    audit.eq((5-original['fp']-fee)-(out['e1-lie-utility']-fee),
             (5-original['fp'])-out['e1-lie-utility'], 'compulsory fee cancels in each report comparison')
    return inputs, out


def pairs(items):
    obj = {}
    for key, value in items:
        need(key not in obj, 'duplicate JSON key'); obj[key] = value
    return obj


def nonfinite(value):
    raise ValueError('nonfinite JSON constant '+value)


def finite_float(text):
    value = float(text)
    need(-float('inf') < value < float('inf'), 'finite JSON number')
    return value


def read_json(raw):
    need(type(raw) is bytes, 'JSON bytes')
    return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
                      parse_constant=nonfinite, parse_float=finite_float)


class Fragment(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.ids, self.worked, self.prompts, self.answers = [], [], [], [], []
        self.sources, self.links, self.markers = {}, set(), {'data-input': {}, 'data-calc': {}}
        self.exercise_depth = self.solution_depth = self.capture = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs); classes = attrs.get('class', '').split()
        if 'id' in attrs: self.ids.append(attrs['id'])
        if 'worked' in classes: self.worked.append(attrs.get('id'))
        if tag == 'ol' and 'exercises' in classes: self.exercise_depth = len(self.stack)
        if tag == 'details' and 'solutions' in classes: self.solution_depth = len(self.stack)
        if tag == 'li' and self.exercise_depth is not None: self.prompts.append(attrs.get('id'))
        if 'data-solution-for' in attrs:
            need(self.solution_depth is not None, 'paired solution inside disclosure')
            self.answers.append(attrs['data-solution-for'])
        if 'href' in attrs: self.links.add(attrs['href'])
        if 'data-source' in attrs:
            key, url = attrs['data-source'], attrs.get('href')
            need(key in SOURCES and url == SOURCES[key], 'exact source identity and URL')
            self.sources[key] = url
        for kind in self.markers:
            if kind in attrs:
                key = attrs[kind]
                need(tag == 'span' and key not in self.markers[kind] and self.capture is None,
                     'unique numerical marker')
                self.markers[kind][key] = ''; self.capture = (kind, key)
        if tag not in {'br', 'hr', 'img', 'meta', 'link', 'input'}: self.stack.append(tag)

    def handle_data(self, text):
        if self.capture is not None:
            kind, key = self.capture; self.markers[kind][key] += text

    def handle_endtag(self, tag):
        need(bool(self.stack) and self.stack[-1] == tag, 'balanced HTML fragment')
        self.stack.pop()
        if tag == 'span': self.capture = None
        if tag == 'ol' and self.exercise_depth == len(self.stack): self.exercise_depth = None
        if tag == 'details' and self.solution_depth == len(self.stack): self.solution_depth = None


def display(value):
    if type(value) is str: return value
    if type(value) in (tuple, list): return '('+','.join(display(x) for x in value)+')'
    return str(F(value))


def compact(value):
    return re.sub(r'\s+', '', value).replace('−', '-')


def bindings(rows):
    need(type(rows) is list, 'payload binding list')
    result = {}
    for item in rows:
        need(type(item) is dict and set(item) == {'path', 'bytes', 'sha256'}, 'binding fields')
        path = item['path']
        need(type(path) is str and path not in result, 'unique bound path')
        need(type(item['bytes']) is int and item['bytes'] > 0, 'positive payload size')
        need(type(item['sha256']) is str and re.fullmatch('[0-9a-f]{64}', item['sha256']) is not None, 'SHA256 format')
        result[path] = item
    return result


def invalid_domains(a):
    for x in (True, False, 0.5, '1/2', None, complex(1, 0), float('nan'), float('inf'),
              10**7, F(1, 10**10)): a.reject(q, x)
    a.reject(assignment, [])
    a.reject(assignment, [(1, 2), (3,)])
    a.reject(assignment, [(1, -1)])
    a.reject(assignment, [(1, 2, 3, 4)])
    a.reject(assignment, [(1,)], -1)
    a.reject(project, (7, 6, 4), 12, 11)
    a.reject(project, (7, -1, 4), 12, 12)
    for masses in ((F(1, 3), F(1, 3)), (-1, 2), (0, 1)):
        a.reject(price_lottery, (2, 7), masses, 5)
    a.reject(price_lottery, (7, 2), (F(1, 2),)*2, 5)
    a.reject(price_lottery, (2, 2), (F(1, 2),)*2, 5)
    a.reject(price_lottery, (2, 7), (F(1, 2),)*2, 11)
    a.reject(price_lottery, (2, 7), (F(1, 2),)*2, 5, -1)
    a.reject(sidebet, (F(1, 4),)*3, 0, 0)
    a.reject(sidebet, (F(1, 4),)*4, True, 0)
    a.reject(sidebet, (F(1, 4),)*4, 0, 1)
    a.reject(clip, ((0, 0), (1, 0), (1, 1)), (0, 0), 0)
    a.reject(clip, ((0, 0, 0),), (1, 0), 0)
    a.reject(uniform_regions, (0, 12))
    a.reject(uniform_regions, (6, 12), -1)
    a.reject(uniform_profile, (6, 12), (7, 8))
    a.reject(uniform_profile, (6, 12), (1, 8), -1)
    for n in (True, 1, 5): a.reject(power, n)
    a.reject(power, 3, -1)
    a.reject(power, 3, 11)
    a.reject(power, 3, 5, 10, F(1, 2))
    a.reject(imitated_payoff, 5, 11)
    a.reject(imitated_payoff, 5, 6, 3, 1)
    a.reject(cara, F(1, 3))
    a.reject(cara, 20)
    for text in (b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":Infinity}', b'{"x":1e9999}'):
        a.reject(read_json, text)
    a.reject(check, True)


def check(root=None):
    need(root is None or type(root) is str or isinstance(root, Path), 'root path type')
    root = Path(root).resolve() if root is not None else Path(__file__).resolve().parent.parent
    paths = AUTHORS+(SELF, RECORD)
    raw = {name: (root/name).read_bytes() for name in paths}
    a = Audit(); manuscript = raw[AUTHORS[0]].decode('utf-8')
    fragment = Fragment(); fragment.feed(manuscript); fragment.close()
    a.yes(not fragment.stack and fragment.capture is None, 'complete balanced manuscript')
    a.eq(len(fragment.ids), len(set(fragment.ids)), 'unique fragment IDs')
    a.yes(all(key.startswith('v13-c10-') for key in fragment.ids), 'chapter-specific ID namespace')
    a.eq(fragment.worked, ['v13-c10-w'+str(i) for i in range(1, 7)], 'actual shared worked token counts all six cases')
    prompts = ['v13-c10-e'+str(i) for i in range(1, 13)]
    a.eq(fragment.prompts, prompts, 'all twelve exact exercises')
    a.eq(fragment.answers, prompts, 'one paired full solution per exact exercise')
    a.eq(fragment.sources, SOURCES, 'complete scoped source routes')
    a.eq({link for link in fragment.links if not link.startswith('https://')},
         {'v05-c10.html', 'v05-c11.html', 'v13-c06.html', 'v13-c08.html', 'v13-c09.html', 'v13-c11.html'},
         'flat prerequisite and successor links')
    for phrase in ('independent private seeds', 'selected-equilibrium implementation',
                   'per-report integrability alone', 'Endpoint extensions are used only for allocation ranking',
                   'finite defined interior virtual values, hence almost surely', 'reserve threshold',
                   'a jump across zero', 'Teach-back and delayed retention'):
        a.yes(phrase in manuscript, 'reviewed proof boundary '+phrase)
    primitive, result = derive(a)
    for kind, expected in (('data-input', primitive), ('data-calc', result)):
        a.eq(set(fragment.markers[kind]), set(expected), 'complete '+kind+' inventory')
        for key, value in expected.items():
            a.eq(compact(fragment.markers[kind][key]), compact(display(value)), 'independent '+kind+' '+key)
    a.eq((len(primitive), len(result)), (21, 80), 'all primitive and result markers')
    sources, author, peer = (read_json(raw[name]) for name in (AUTHORS[2], AUTHORS[3], RECORD))
    a.eq({s['id']: s['url'] for s in sources['sources']}, SOURCES, 'final source record scope')
    for source in sources['sources']:
        a.yes(bool(source['actual_body_scope']) and bool(source['limits']) and source['actual_inspector'] == 'c05_review',
              'actual primary inspector and exclusions')
    bound_author, bound_peer = bindings(author['payload_bindings']), bindings(peer['bindings'])
    a.eq(set(bound_author), set(AUTHORS[:3]), 'author three nonself bindings')
    a.eq(set(bound_peer), set(AUTHORS+(SELF,)), 'peer four author files and own checker')
    for group in (bound_author, bound_peer):
        for name, item in group.items():
            a.eq((len(raw[name]), sha256(raw[name]).hexdigest()), (item['bytes'], item['sha256']), 'bound actual bytes '+name)
    a.eq(set(author['exercise_audit']), {'e'+str(i) for i in range(1, 13)}, 'author exact exercise coverage')
    a.eq(set(peer['exercise_audit']), set(prompts), 'peer exact exercise coverage')
    a.eq(set(peer['proof_audit']), {'v13-c10-'+x for x in ('revelation', 'groves', 'payment', 'optimal', 'revenue', 'preferences')},
         'peer complete proof domains')
    a.eq((author['unresolved_findings'], peer['open_findings']), ([], []), 'no unresolved finding claimed')
    invalid_domains(a)
    a.eq({name: (root/name).read_bytes() for name in paths}, raw, 'six runtime payloads unchanged')
    summary = {'chapter': 'v13-c10', 'status': 'passed', 'comparisons': a.comparisons,
               'domain_rejections': a.rejections, 'financial_interventions': 13,
               'worked_cases': 6, 'solved_exercises': 12, 'primitive_markers': len(primitive),
               'result_markers': len(result), 'runtime_payloads': list(paths), 'writes': 0,
               'scope': 'Independent finite-choice and polygon-moment evidence plus separate universal proof review.'}
    json.dumps(summary, allow_nan=False)
    return summary


if __name__ == '__main__':
    need(len(sys.argv) == 1, 'silent CLI accepts no arguments')
    check()
