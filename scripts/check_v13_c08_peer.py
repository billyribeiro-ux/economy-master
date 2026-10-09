#!/usr/bin/env python3
"""Independent exact C08 oracle; quiet six-file runtime, no author imports.

Weighted pool-adjacent-violators with a global multiplier certificate, exact
quadratic quadrature, actual lottery choices, and affine signaling inequalities
supplement the separately read general proofs. No blueprint output is an oracle.
"""
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys


AUTHORS = ('content/chapters/v13-c08.html', 'scripts/check_v13_c08.py',
           'content/reviews/v13-c08-sources.json', 'content/reviews/v13-c08-author.json')
SELF, RECORD = 'scripts/check_v13_c08_peer.py', 'content/reviews/v13-c08-peer.json'
SOURCES = {
    'v13-c06-manea-noncoop2017': 'https://ocw.mit.edu/courses/14-126-game-theory-spring-2016/a4d0a3949ab29c2a2f55442a9723d205_MIT14_126S16_noncoop.pdf',
    'v05-c08-holmstrom-screening': 'https://ocw.mit.edu/courses/14-124-microeconomic-theory-iv-spring-2017/9a5e2a8da8b4e9b22fa39d66f9d98dda_MIT14_124S17_Slide3.pdf',
}


def require(ok, why):
    if not ok:
        raise ValueError(why)


def scalar(x):
    require(type(x) in (int, F), 'exact scalar type')
    x = F(x)
    require(abs(x) <= 10**6 and x.denominator <= 10**9, 'bounded exact scalar')
    return x


def vector(x, n=None):
    require(type(x) in (tuple, list) and 1 <= len(x) <= 8, 'finite vector')
    require(n is None or len(x) == n, 'vector dimension')
    return tuple(scalar(v) for v in x)


def law(p, n=None):
    p = vector(p, n)
    require(min(p) >= 0 and sum(p) == 1, 'probability law')
    return p


def weighted(p, x):
    p, x = law(p), vector(x)
    require(len(p) == len(x), 'weighted dimension')
    return sum((a*b for a, b in zip(p, x)), F(0))


def market(theta, p, cap=5):
    theta = vector(theta)
    require(len(theta) <= 6 and all(x < y for x, y in zip(theta, theta[1:])), 'ordered type support')
    p, cap = law(p, len(theta)), scalar(cap)
    require(min(p) > 0 and cap > 0, 'positive masses and quality cap')
    return theta, p, cap


def revenue_weights(m):
    theta, p, _ = m
    # Each lower quality adds its type gap to the utility of every higher type.
    rent_cost = tuple((theta[i+1]-theta[i])*sum(p[i+1:]) if i+1 < len(p) else F(0)
                      for i in range(len(p)))
    return tuple(p[i]*theta[i]-rent_cost[i] for i in range(len(p)))


def isotonic(m):
    """Pool descending weighted means; certify the result independently below."""
    _, p, cap = m
    blocks = []
    for i, r in enumerate(revenue_weights(m)):
        blocks.append(([i], p[i], r))
        while len(blocks) >= 2 and blocks[-2][2]/blocks[-2][1] > blocks[-1][2]/blocks[-1][1]:
            right, left = blocks.pop(), blocks.pop()
            blocks.append((left[0]+right[0], left[1]+right[1], left[2]+right[2]))
    q = [F(0)]*len(p)
    for indices, mass, revenue in blocks:
        for i in indices:
            q[i] = min(cap, max(F(0), revenue/mass))
    return tuple(q)


def menu(m, q, rents=None):
    theta, p, cap = m
    q = vector(q, len(theta))
    require(0 <= min(q) and max(q) <= cap and all(x <= y for x, y in zip(q, q[1:])), 'feasible quality order')
    minimal = tuple(sum((theta[j+1]-theta[j])*q[j] for j in range(i)) for i in range(len(q)))
    u = minimal if rents is None else vector(rents, len(q))
    t = tuple(th*x-v for th, x, v in zip(theta, q, u))
    gaps = tuple(tuple(u[i]-(theta[i]*q[j]-t[j]) for j in range(len(q))) for i in range(len(q)))
    require(min(u) >= 0 and min(x for row in gaps for x in row) >= 0, 'all-pair IC and IR')
    costs = tuple(x*x/2 for x in q)
    payment, cost, rent = weighted(p, t), weighted(p, costs), weighted(p, u)
    social = weighted(p, tuple(th*x-c for th, x, c in zip(theta, q, costs)))
    fbq = tuple(min(cap, max(F(0), th)) for th in theta)
    fb = weighted(p, tuple(th*x-x*x/2 for th, x in zip(theta, fbq)))
    return {'q': q, 'u': u, 't': t, 'gaps': gaps, 'payment': payment, 'cost': cost,
            'rent': rent, 'profit': payment-cost, 'welfare': social, 'fb': fb,
            'loss': fb-social, 'minimal': minimal}


def certificate(m, q):
    """Nonnegative multipliers prove a global tangent bound for every feasible q'."""
    _, p, cap = m
    q = vector(q, len(p))
    gradient = tuple(r-w*x for r, w, x in zip(revenue_weights(m), p, q))
    lower = -sum(g for g, x in zip(gradient, q) if x == 0)
    upper = sum(gradient)+lower
    adjacent = tuple(lower+sum(gradient[:i+1]) for i in range(len(q)-1))
    require(min((lower, upper)+adjacent) >= 0, 'nonnegative global multipliers')
    require(lower*q[0] == upper*(cap-q[-1]) == 0, 'bound complementarity')
    require(all(v*(q[i+1]-q[i]) == 0 for i, v in enumerate(adjacent)), 'order complementarity')
    reconstructed = tuple((adjacent[i] if i+1 < len(q) else upper)
                          -(adjacent[i-1] if i else lower) for i in range(len(q)))
    require(reconstructed == gradient, 'gradient multiplier identity')
    # Thus g.(q'-q) <= 0 for the entire feasible polytope; the exact remaining
    # objective difference is -sum p_i (q'_i-q_i)^2/2, strictly negative off q.
    return gradient, (lower, adjacent, upper)


def virtual_objective(m, q):
    _, p, _ = m
    return sum(r*x-w*x*x/2 for r, w, x in zip(revenue_weights(m), p, q))


def simpson_quadratic(f, lo, hi):
    # Used only for explicitly quadratic-or-lower polynomials on each segment.
    return (hi-lo)*(f(lo)+4*f((lo+hi)/2)+f(hi))/6


def continuous_point(b, theta, delta=0, top=None):
    b, theta, delta = scalar(b), scalar(theta), scalar(delta)
    require(2 <= b <= 5 and 1 <= theta <= b, 'uniform witness interval')
    q = max(F(0), 2*theta-b)
    u = max(F(0), theta-b/2)**2+delta
    if top is not None:
        top = scalar(top)
        require(theta == b and b <= top <= 5, 'null-set top allocation domain')
        q = top
    return q, u, theta*q-u


def continuous_accounts(b):
    b = scalar(b)
    require(2 <= b <= 5, 'bounded uniform upper support')
    pivot = b/2
    payment = simpson_quadratic(lambda x: x*x-pivot*pivot, pivot, b)/(b-1)
    cost = simpson_quadratic(lambda x: (2*x-b)**2/2, pivot, b)/(b-1)
    rent = simpson_quadratic(lambda x: (x-pivot)**2, pivot, b)/(b-1)
    fb = simpson_quadratic(lambda x: x*x/2, F(1), b)/(b-1)
    return {'payment': payment, 'cost': cost, 'profit': payment-cost, 'rent': rent,
            'welfare': payment-cost+rent, 'fb': fb, 'loss': fb-(payment-cost+rent)}


def jump(theta, selected):
    theta, selected = scalar(theta), scalar(selected)
    require(1 <= theta <= 3 and 0 <= selected <= 2, 'jump domain')
    q = F(0) if theta < 2 else F(2) if theta > 2 else selected
    u = 2*max(F(0), theta-2)
    return q, u, theta*q-u


def lottery_choices(types, qualities, probabilities, payment, late=False):
    types, qualities = vector(types), vector(qualities)
    p, payment = law(probabilities, len(qualities)), scalar(payment)
    require(min(qualities) >= 0 and max(qualities) <= 5 and type(late) is bool, 'lottery witness domain')
    rows = []
    for theta in types:
        take = tuple(not late or theta*q-payment >= 0 for q in qualities)
        receipts = weighted(p, tuple(payment*int(v) for v in take))
        costs = weighted(p, tuple(q*q*int(v)/2 for q, v in zip(qualities, take)))
        utility = weighted(p, tuple((theta*q-payment)*int(v) for q, v in zip(qualities, take)))
        rows.append((utility, receipts, costs, receipts-costs, take))
    return tuple(rows)


def tail_shell(k):
    require(type(k) is int and 0 <= k <= 12, 'bounded dyadic shell index')
    # Uniform [1,3], transfers +/-1/|theta-2| with equal signs. Two annuli,
    # each length 2^(-k-1), density 1/2, positive-sign probability 1/2,
    # and payment at least 2^k. Each disjoint shell contributes >= 1/4
    # to EACH tail. This identity for arbitrary k proves both tails diverge.
    return 2*F(1, 2**(k+1))*F(1, 2)*F(1, 2)*2**k


def linear_interval(conditions):
    require(type(conditions) in (tuple, list) and 1 <= len(conditions) <= 4, 'finite affine conditions')
    lo, hi = F(0), None
    for condition in conditions:
        a, b = vector(condition, 2)
        if b == 0:
            if a < 0: return None
        elif b > 0:
            lo = max(lo, -a/b)
        else:
            hi = min(hi, -a/b) if hi is not None else -a/b
    return None if hi is not None and lo > hi else (lo, hi)


def signaling_ranges(prior, kappa):
    prior, kappa = scalar(prior), scalar(kappa)
    require(0 < prior < 1 and 0 <= kappa <= F(1, 3), 'two positive type marginals and nonnegative net high cost')
    low, high = 1-kappa, F(1, 3)-kappa
    return (linear_interval(((-3, low), (3, -high))),
            linear_interval(((3*prior, -low), (3*prior, -high))))


def payoffs(kappa, s, mu):
    kappa, s, mu = scalar(kappa), scalar(s), scalar(mu)
    require(kappa >= 0 and s >= 0 and 0 <= mu <= 1, 'signal and posterior domain')
    wage = 2+3*mu+kappa*s
    return wage-s, wage-s/3


def dominance(current, kappa, s):
    current = vector(current, 2)
    return tuple(u > v for u, v in zip(current, payoffs(kappa, s, 1)))


def signal_welfare(prior, kappa, h):
    prior, kappa, h = scalar(prior), scalar(kappa), scalar(h)
    require(0 < prior < 1 and kappa >= 0 and h >= 0, 'separating accounts domain')
    outputs, education_costs = (F(2), 5+kappa*h), (F(0), h/3)
    p = (1-prior, prior)
    return {'wage': outputs[1], 'net': outputs[1]-education_costs[1],
            'output': weighted(p, outputs), 'cost': weighted(p, education_costs),
            'welfare': weighted(p, tuple(x-c for x, c in zip(outputs, education_costs)))}


def escape(kappa, utility):
    kappa, utility = scalar(kappa), scalar(utility)
    require(kappa > F(1, 3), 'strictly positive productive high return')
    return max(F(0), (utility-2)/(kappa-F(1, 3)))+1


def flatten(values):
    if isinstance(values, (list, tuple)):
        return tuple(v for row in values for v in flatten(row))
    return (scalar(values),)


def marker_numbers(text):
    require(type(text) is str and len(text) <= 2000, 'bounded numeric marker')
    # The reader's markers include labels, inequalities and interval notation.
    parts = re.findall(r'[-+]?\d+(?:/\d+)?', text.replace('−', '-'))
    require(1 <= len(parts) <= 60, 'nonempty bounded marker values')
    return tuple(scalar(F(x)) for x in parts)


def strict_json(text):
    def pairs(rows):
        out = {}
        for k, v in rows:
            require(k not in out, 'duplicate JSON key'); out[k] = v
        return out
    def bad(x):
        raise ValueError('nonfinite JSON '+x)
    result = json.loads(text, object_pairs_hook=pairs, parse_constant=bad)
    json.dumps(result, allow_nan=False)
    return result


class Document(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.capture, self.text = [], [], []
        self.inputs, self.results, self.ids, self.sources = {}, {}, {}, {}
        self.worked, self.prompts, self.solutions, self.links = [], [], [], []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs); require(len(a) == len(attrs), 'unique HTML attributes')
        cls = a.get('class', '').split()
        if 'id' in a:
            require(a['id'] not in self.ids, 'unique HTML IDs'); self.ids[a['id']] = tag
        if 'worked' in cls: self.worked.append(a.get('id'))
        if tag == 'li' and any(t == 'ol' and 'exercises' in c for t, c in self.stack):
            self.prompts.append(a.get('id'))
        if 'data-solution-for' in a:
            require(tag == 'li' and any(t == 'details' and 'solutions' in c for t, c in self.stack), 'standard solution disclosure')
            self.solutions.append(a['data-solution-for'])
        for key, dest in (('data-input', self.inputs), ('data-calc', self.results)):
            if key in a:
                require(a[key] not in dest, 'unique numeric marker')
                dest[a[key]] = ''; self.capture.append((len(self.stack), a[key], dest))
        if tag == 'a':
            self.links.append(a.get('href', ''))
            if 'data-source' in a:
                key = a['data-source']
                require(key not in self.sources or self.sources[key] == a.get('href'), 'same reused source URL')
                self.sources[key] = a.get('href')
        if tag not in ('br', 'hr', 'img', 'link', 'meta', 'input', 'wbr'):
            self.stack.append((tag, cls))

    def handle_data(self, text):
        self.text.append(text)
        for _, key, dest in self.capture: dest[key] += text

    def handle_endtag(self, tag):
        require(self.stack and self.stack[-1][0] == tag, 'balanced HTML')
        self.stack.pop(); self.capture = [v for v in self.capture if v[0] < len(self.stack)]


class Audit:
    def __init__(self): self.comparisons = self.rejections = 0
    def equal(self, actual, expected, name):
        self.comparisons += 1
        require(actual == expected, name+': '+repr(actual)+' != '+repr(expected))
    def true(self, ok, name): self.equal(bool(ok), True, name)
    def reject(self, call, *args):
        self.rejections += 1
        try: call(*args)
        except (ValueError, TypeError, ZeroDivisionError): return
        raise ValueError('invalid domain accepted by '+call.__name__)


def derive(a):
    results = {}
    first = market((1, 2, 3), (F(1, 2), F(1, 4), F(1, 4)))
    second = market((2, 3, 4), (F(1, 2), F(1, 10), F(2, 5)))
    changed = market((1, 2, 3), (F(1, 4), F(1, 4), F(1, 2)))
    capped = market(second[0], second[1], 1)
    cases = {}
    for prefix, m in (('finite1', first), ('finite2', second), ('e1', changed), ('e2', capped)):
        q = isotonic(m); row = menu(m, q); cases[prefix] = row
        gradient, multipliers = certificate(m, q)
        phi = tuple(r/p for r, p in zip(revenue_weights(m), m[1]))
        a.equal(row['profit'], virtual_objective(m, q), 'direct payments versus minimal-rent revenue weights '+prefix)
        a.equal(row['profit']+row['rent'], row['welfare'], 'transfer cancellation '+prefix)
        a.true(all(x >= 0 for g in row['gaps'] for x in g), 'all-pair IC '+prefix)
        a.equal(row['loss'], row['fb']-row['welfare'], 'first-best welfare loss '+prefix)
        a.true(all(w > 0 for w in m[1]), 'strict quadratic global remainder '+prefix)
        # Check the coefficient identity behind the global certificate on an
        # economically distinct feasible allocation, rather than an optimum grid.
        witness = tuple(F(i+1)*m[2]/(len(q)+1) for i in range(len(q)))
        exact_change = sum(g*(v-x)-p*(v-x)**2/2 for g, v, x, p in zip(gradient, witness, q, m[1]))
        a.equal(virtual_objective(m, witness)-row['profit'], exact_change, 'global tangent quadratic identity '+prefix)
        a.true(exact_change <= 0, 'certificate witness '+prefix)
        if prefix == 'finite1':
            for key in ('q', 'u', 't', 'gaps', 'profit', 'rent', 'welfare', 'fb', 'loss'): results[prefix+'-'+key] = row[key]
            results[prefix+'-phi'] = phi
        elif prefix == 'finite2':
            for key in ('q', 'u', 't', 'gaps', 'profit'): results[prefix+'-'+key] = row[key]
            results[prefix+'-phi'], results[prefix+'-gradient'] = phi, gradient
            a.equal(multipliers, (0, (F(1, 6), 0), 0), 'exact bunching multiplier')
        elif prefix == 'e1':
            for key in ('q', 'u', 't', 'profit', 'fb', 'loss'): results[prefix+'-'+key] = row[key]
            results[prefix+'-phi'] = phi
            a.equal(multipliers, (F(1, 2), (0, 0), 0), 'additional exclusion multiplier')
        else:
            for key in ('q', 't', 'profit'): results[prefix+'-'+key] = row[key]
            results[prefix+'-gradient'] = gradient
            a.equal(multipliers, (0, (F(1, 6), 0), F(6, 5)), 'cap plus bunching multipliers')

    high_rent = menu(first, cases['finite1']['q'], (0, F(1, 2), F(5, 2)))
    off = tuple(g for i, row in enumerate(high_rent['gaps']) for j, g in enumerate(row) if i != j)
    a.true(min(off) > 0 and min(high_rent['u']) == 0, 'strict report choice need not mean strict participation')
    extra = tuple(u-z for u, z in zip(high_rent['u'], high_rent['minimal']))
    a.equal(high_rent['profit'], virtual_objective(first, high_rent['q'])-weighted(first[1], extra), 'arbitrary feasible extra-rent correction')
    shifted = menu(first, high_rent['q'], tuple(u+F(1, 4) for u in high_rent['u']))
    a.equal((shifted['gaps'], shifted['profit']), (high_rent['gaps'], high_rent['profit']-F(1, 4)), 'common utility shift preserves all IC and costs its full amount')
    a.true(min(shifted['u']) > 0 and shifted['t'][0] < 0, 'strict IR and allowed rebate')
    results.update({'e3-t': high_rent['t'], 'e3-gaps': off, 'e3-profit': high_rent['profit'],
                    'e3-loss': cases['finite1']['profit']-high_rent['profit']})

    for b, prefix in ((3, 'continuum'), (4, 'e5')):
        totals = continuous_accounts(b)
        a.equal(totals['payment']-totals['cost']+totals['rent'], totals['welfare'], 'continuum transfer identity')
        # Simpson integrates these quadratics exactly; the active rent has a
        # separate cubic antiderivative value as an independent account check.
        a.equal(totals['rent'], (F(b)-F(b, 2))**3/(3*(b-1)), 'integrated envelope rent')
        if prefix == 'continuum':
            results.update({prefix+'-'+k: v for k, v in totals.items()})
            results['continuum-at2'], results['continuum-at3'] = continuous_point(b, 2), continuous_point(b, 3)
        else:
            results['e5-threshold'] = F(b, 2)
            results['e5-accounts'] = tuple(totals[k] for k in ('payment', 'cost', 'profit', 'rent'))
            for k in ('welfare', 'fb', 'loss'): results[prefix+'-'+k] = totals[k]
    # Endpoint quality is intentionally changed with its IC-compatible payment.
    types = (F(1), F(3, 2), F(2), F(5, 2), F(3))
    endpoint_rows = tuple(continuous_point(3, th, top=5 if th == 3 else None) for th in types)
    a.true(all(row[1] >= th*other[0]-other[2] for th, row in zip(types, endpoint_rows) for other in endpoint_rows), 'null-mass endpoint change preserves global-pair witness IC')
    a.equal(endpoint_rows[-1], (5, F(9, 4), F(51, 4)), 'top payment adjusts to preserve endpoint utility')
    for selected in (0, 1, 2):
        rows = tuple(jump(th, selected) for th in types)
        a.true(all(row[1] >= th*other[0]-other[2] for th, row in zip(types, rows) for other in rows), 'all jump-point choices satisfy every witness IC pair')
        a.equal(jump(2, selected), (selected, 0, 2*selected), 'jump type indifferent across contract qualities')
    a.equal(((jump(2, 1)[1]-jump(F(3, 2), 1)[1])/F(1, 2),
             (jump(F(5, 2), 1)[1]-jump(2, 1)[1])/F(1, 2)), (0, 2), 'unequal one-sided utility derivatives')
    payment, cost = F(1, 2)*4, F(1, 2)*F(2)**2/2
    results.update({'e4-at2': (2, 2), 'e4-payment': payment, 'e4-cost': cost, 'e4-profit': payment-cost,
                    'e12-profit': continuous_accounts(3)['profit']-F(1, 4)})
    for th in types:
        base, shifted = continuous_point(3, th), continuous_point(3, th, F(1, 4))
        a.equal((shifted[0], shifted[1]-base[1], shifted[2]-base[2]), (base[0], F(1, 4), -F(1, 4)), 'fixed continuous quality allows only the common envelope constant')
    a.true(continuous_point(3, 1, -F(1, 4))[1] < 0, 'negative constant violates lowest-type IR')

    committed = lottery_choices((2, 4), (0, 4), (F(1, 2), F(1, 2)), 3)
    mean = lottery_choices((2, 4), (2,), (1,), 3)
    a.equal(tuple(r[0] for r in committed), tuple(r[0] for r in mean), 'mean replacement preserves each interim utility')
    variance = weighted((F(1, 2), F(1, 2)), (4, 4))
    a.equal(committed[0][2]-mean[0][2], variance/2, 'quadratic Jensen gap is half quality variance')
    results.update({'lottery-utilities': tuple(r[0] for r in mean),
                    'lottery-quadratic': (mean[0][3], committed[0][3]),
                    'lottery-sqrt': 3-weighted((F(1, 2), F(1, 2)), (0, 2)), 'lottery-realized': 2*0-3})
    a.true(F(1) < F(2) < F(9, 4), 'exact squared bounds imply 1 < sqrt(2) < 3/2')
    a.true(committed[0][0] > 0 and results['lottery-realized'] < 0, 'interim IR does not imply ex-post IR')
    before = lottery_choices((2, 4), (0, 3), (F(1, 3), F(2, 3)), 3)
    after = lottery_choices((2, 4), (0, 3), (F(1, 3), F(2, 3)), 3, True)
    a.equal(tuple(r[4] for r in after), ((False, True), (False, True)), 'actual later choices at each realization')
    a.equal(tuple(v[0]-u[0] for u, v in zip(before, after)), (1, 1), 'rejection right removes each buyer bad-state payment')
    a.equal(after[0][3]-before[0][3], -1, 'seller actually loses rejected-state receipt')
    results.update({'e6-committed-u': tuple(r[0] for r in before), 'e6-committed-profit': before[0][3],
                    'e6-option-u': tuple(r[0] for r in after), 'e6-option-accounts': after[0][1:4]})
    for k in (0, 1, 4, 8): a.equal(tail_shell(k), F(1, 4), 'nonintegrable population example has a constant lower tail contribution per dyadic shell')
    a.equal(sum(tail_shell(k) for k in range(6)), F(3, 2), 'disjoint-shell lower bounds accumulate, despite every report mean being zero')
    a.equal(weighted((F(1, 2), F(1, 2)), (4, -4)), 0, 'fixed-report signed payment has finite absolute moment and zero mean')

    for prior, kappa, prefix in ((F(1, 3), F(0), 'signal'), (F(1, 2), F(0), 'e7'),
                                 (F(1, 3), F(1, 6), 'productive'), (F(1, 3), F(1, 4), 'e9')):
        sep, pool = signaling_ranges(prior, kappa)
        low, high = 1-kappa, F(1, 3)-kappa
        a.true(low > high > 0, 'positive ordered net costs')
        h0, hmax = sep; current = (F(2), payoffs(kappa, h0, 1)[1])
        a.equal((5-current[0])/low, (5-current[1])/high, 'both dominance boundaries coincide at least-cost separation')
        a.true(min(current) >= 2 and low > 0 and high > 0, 'low posterior off-path payoff bounded globally by equilibrium values')
        for h in (h0, hmax):
            a.true(2 >= payoffs(kappa, h, 1)[0] and payoffs(kappa, h, 1)[1] >= 2, 'separating endpoints include all cross-signal IC inequalities')
        for sp in pool:
            equilibrium = payoffs(kappa, sp, prior)
            a.true(min(equilibrium) >= 2, 'pooling endpoints deter every low-priced off-path signal')
            lo, hi = (5-equilibrium[0])/low, (5-equilibrium[1])/high
            witness = (lo+hi)/2
            a.equal(hi-lo, 3*(1-prior)*(1/high-1/low), 'strict pooling-elimination interval has positive width independent of pool signal')
            a.true(witness > sp and dominance(equilibrium, kappa, witness) == (True, False)
                   and payoffs(kappa, witness, 1)[1] > equilibrium[1], 'forced H posterior gives a strict off-path pooling deviation')
        excess = (h0+hmax)/2; equilibrium = (F(2), payoffs(kappa, excess, 1)[1]); witness = (h0+excess)/2
        a.true(dominance(equilibrium, kappa, witness) == (True, False)
               and payoffs(kappa, witness, 1)[1] > equilibrium[1], 'every positive excess permits an interior profitable H-only deviation')
        a.equal(dominance(current, kappa, h0/2), (False, False), 'below least-cost signal no type is dominated')
        a.equal(dominance(current, kappa, h0+1), (True, True), 'above least-cost signal all types are dominated; no extra posterior restriction')
        accounts = signal_welfare(prior, kappa, h0)
        a.equal(accounts['welfare'], (1-prior)*current[0]+prior*current[1], 'posterior wages give aggregate zero employer profit')
        if prefix == 'signal':
            results.update({'signal-separation': (0,)+sep, 'signal-pooling': pool,
                            'signal-net': current, 'signal-welfare': accounts['welfare']})
        elif prefix == 'e7':
            results.update({'e7-wage': 2+3*prior, 'e7-pooling': pool, 'e7-separation': sep,
                            'e7-welfare': accounts['welfare']})
        else:
            results[prefix+'-separation'], results[prefix+'-pooling'] = sep, pool
            results.update({prefix+'-'+key: v for key, v in accounts.items()})
            if prefix == 'e9': results['e9-netcosts'] = (low, high)
    maximum = payoffs(0, 4, 1)
    pooled = payoffs(0, 1, F(1, 3)); excess = (F(2), payoffs(0, 6, 1)[1])
    a.equal((dominance(pooled, 0, 4), dominance(excess, 0, 4), dominance((2, 4), 0, 4)),
            ((True, False), (True, False), (True, True)), 'same off-path signal has different type-specific dominance sets')
    results.update({'e8-max': maximum, 'e8-pool-u': pooled, 'e8-excess-u': excess,
                    'e8-gain': maximum[1]-excess[1]})
    boundary, pool = signaling_ranges(F(1, 3), F(1, 3))
    a.equal((boundary, pool), ((F(9, 2), None), (0, F(3, 2))), 'complete zero-high-net-cost pure outcome intervals')
    results['boundary-separation'] = boundary[0]
    for h in (F(9, 2), F(6)):
        current = (F(2), F(5)); kappa = F(1, 3)
        a.equal(payoffs(kappa, h, 1)[1], current[1], 'all finite separating high signals give identical utility')
        a.true(payoffs(kappa, h, 1)[0] <= current[0], 'low cross-signal boundary constraint')
        a.equal((payoffs(kappa, boundary[0], 1)[0], kappa-F(1, 3)), (2, 0), 'H-priced tail has nonincreasing low utility and constant high utility')
        a.equal(payoffs(kappa, 0, 0), (2, 2), 'low-priced lower region begins below both equilibrium values')
        a.equal(dominance(current, kappa, 5), (True, False), 'strict test excludes only low at equality boundary')
        a.equal(dominance(current, kappa, 4), (False, False), 'low beliefs allowed below boundary threshold')
        a.equal(signal_welfare(F(1, 3), kappa, h)['welfare'], 3, 'productive gain exactly offsets education cost throughout surviving half-line')
    current = payoffs(F(1, 3), F(3, 2), F(1, 3)); signal = F(11, 2)
    a.true(dominance(current, F(1, 3), signal) == (True, False) and payoffs(F(1, 3), signal, 1)[1] > current[1], 'boundary pooling still eliminated with a strict high gain')
    results.update({'e10-max5': payoffs(F(1, 3), 5, 1), 'e10-wage5': 5+F(5, 3),
                    'e10-max4': payoffs(F(1, 3), 4, 1)})
    for utility in (0, 5, 10):
        signal = escape(F(1, 2), utility)
        a.true(payoffs(F(1, 2), signal, 0)[1] > utility, 'belief-independent improving signal above zero-net-cost boundary')
    return results


def check(root=None):
    require(root is None or isinstance(root, (str, Path)), 'root path type')
    base = Path(root).resolve() if root is not None else Path(__file__).resolve().parents[1]
    paths = AUTHORS+(SELF, RECORD)
    def bindings():
        return {p: (len((base/p).read_bytes()), sha256((base/p).read_bytes()).hexdigest()) for p in paths}
    before = bindings()
    a, page = Audit(), Document()
    page.feed((base/AUTHORS[0]).read_text(encoding='utf-8')); page.close()
    prompts = ['v13-c08-e'+str(i) for i in range(1, 13)]
    a.equal((page.stack, page.capture), ([], []), 'complete balanced fragment')
    a.equal((page.prompts, page.solutions), (prompts, prompts), 'all exact exercise/solution pairs')
    a.equal(page.worked, ['v13-c08-case'+str(i) for i in range(1, 7)], 'six original worked cases')
    a.true(all(key.startswith('v13-c08-') for key in page.ids), 'unique namespaced IDs')
    a.equal(page.sources, SOURCES, 'exact scoped source URLs')
    a.equal({p for p in page.links if not p.startswith('https://')},
            {'v13-c0'+str(i)+'.html' for i in (3, 6, 7, 9)}, 'flat prerequisite and successor links')
    prose = ''.join(page.text)
    a.true(all(s in prose for s in ('Teach-back.', 'Delayed retention, without the formulas.',
                                  'Answer key.', 'Evaluation rubric.')), 'answered teaching and open rubric')
    a.true('jointly measurable quality and payment' in prose
           and 'aggregate payments absolutely integrable' in prose
           and 'Per-report integrability alone does not ensure that ex ante receipts exist.' in prose,
           'resolved continuum aggregate-integrability qualification retained')
    results = derive(a)
    inputs = {
        'finite1': (1, 2, 3, F(1, 2), F(1, 4), F(1, 4), 5),
        'finite2': (2, 3, 4, F(1, 2), F(1, 10), F(2, 5), 5),
        'continuum': (1, 3, 5),
        'lottery': (2, 4, 0, 4, F(1, 2), F(1, 2), 3),
        'signal-base': (2, 5, F(1, 3)), 'productive': (F(1, 6),),
        'exercise1': (F(1, 4), F(1, 4), F(1, 2)), 'exercise2': (1,),
        'exercise3': (0, F(1, 2), F(5, 2)), 'exercise4': (0, 2, 2, 2, 2, 0, 2),
        'exercise5': (1, 4, 5), 'exercise6': (0, F(1, 3), 3, F(2, 3), 3),
        'exercise7': (F(1, 2),), 'exercise8': (4,), 'exercise9': (F(1, 4),),
        'exercise10': (F(1, 3), 6), 'exercise12': (1,),
    }
    a.equal(set(page.inputs), set(inputs), 'every original primitive marker covered')
    a.equal(set(page.results), set(results), 'every printed result marker covered')
    for key, value in inputs.items(): a.equal(marker_numbers(page.inputs[key]), flatten(value), 'primitive '+key)
    for key, value in results.items(): a.equal(marker_numbers(page.results[key]), flatten(value), 'printed result '+key)

    for x in (True, 0.5, '1', 1j, float('nan'), float('inf'), 10**6+1, F(1, 10**9+1)):
        a.reject(scalar, x)
    for x in ((), tuple(range(9))): a.reject(vector, x)
    a.reject(vector, (1, 2), 3)
    for p in ((0, 0), (2, -1)): a.reject(law, p)
    for theta, p, cap in (((2, 1), (F(1, 2), F(1, 2)), 5),
                          ((1, 1), (F(1, 2), F(1, 2)), 5),
                          ((1, 2), (1, 0), 5), ((1, 2), (1,), 5),
                          ((1, 2), (F(1, 2), F(1, 2)), 0)):
        a.reject(market, theta, p, cap)
    m = market((1, 2, 3), (F(1, 2), F(1, 4), F(1, 4)))
    for q in ((-1, 1, 3), (0, 1, 6), (1, 0, 3)): a.reject(menu, m, q)
    for u in ((-1, 0, 1), (0, 0, 5)): a.reject(menu, m, (0, 1, 3), u)
    a.reject(certificate, m, (0, 0, 0))
    for b in (1, 6): a.reject(continuous_accounts, b)
    a.reject(continuous_point, 3, 4)
    a.reject(continuous_point, 3, 2, 0, 5)
    a.reject(continuous_point, 3, 3, 0, 2)
    a.reject(jump, 0, 1); a.reject(jump, 2, 3)
    a.reject(lottery_choices, (2, 4), (0, 6), (F(1, 2), F(1, 2)), 3)
    a.reject(lottery_choices, (2, 4), (0, 4), (F(1, 3), F(1, 3)), 3)
    a.reject(lottery_choices, (2, 4), (0, 4), (F(1, 2), F(1, 2)), 3, 1)
    for k in (-1, 13, True): a.reject(tail_shell, k)
    a.reject(linear_interval, ()); a.reject(linear_interval, ((1, 2, 3),))
    for p, k in ((0, 0), (1, 0), (F(1, 3), -1), (F(1, 3), F(1, 2))): a.reject(signaling_ranges, p, k)
    a.reject(payoffs, 0, -1, 0); a.reject(payoffs, 0, 1, 2)
    a.reject(dominance, (1,), 0, 1); a.reject(escape, F(1, 3), 5)
    for text in ('', '1/0', 'x'*2001): a.reject(marker_numbers, text)
    for text in ('{"x":1,"x":2}', '{"x":NaN}'): a.reject(strict_json, text)
    a.reject(Document().feed, '<p id="x"></p><p id="x"></p>')
    a.reject(Document().feed, '<li data-solution-for="x">outside</li>')

    source = strict_json((base/AUTHORS[2]).read_text(encoding='utf-8'))
    author = strict_json((base/AUTHORS[3]).read_text(encoding='utf-8'))
    peer = strict_json((base/RECORD).read_text(encoding='utf-8'))
    a.equal({v['id']: v['url'] for v in source['sources']}, SOURCES, 'final source record identities')
    a.equal({v['actual_inspector'] for v in source['sources']}, {'c05_review'}, 'actual primary inspector attribution')
    a.equal(sum(len(v['images_inspected']) for v in source['sources']), 6, 'six actual scoped page images')
    a.equal(set(peer['exercise_audit']), set(prompts), 'peer every exact solution judgment')
    a.equal(set(peer['proof_audit']), {'v13-c08-'+v for v in ('finite', 'continuum', 'lotteries', 'signaling', 'productive')}, 'peer complete general proof judgments')
    a.equal(peer['open_findings'], [], 'no unresolved material findings')
    a.true(any(v['id'] == 'continuum-lottery-integrability' and v['status'] == 'resolved'
               for v in peer['resolved_findings']), 'precise discovered issue and repair retained')
    for label, declared, expected in (('author', author['payload_bindings'], AUTHORS[:3]),
                                      ('peer', peer['bindings'], AUTHORS+(SELF,))):
        a.equal((len(declared), {v['path'] for v in declared}), (len(expected), set(expected)), label+' exact nonself binding set')
        for v in declared:
            a.equal(before[v['path']], (v['bytes'], v['sha256']), label+' payload '+v['path'])
    a.equal(bindings(), before, 'all six runtime files remain unchanged')
    summary = {'chapter': 'v13-c08', 'status': 'passed', 'comparisons': a.comparisons,
               'domain_rejections': a.rejections, 'intervention_groups': 12,
               'worked_cases': 6, 'solved_exercises': 12, 'input_markers': len(inputs),
               'numeric_markers': len(results), 'global_finite_certificates': 4,
               'source_scopes': 2, 'author_execution_used_as_oracle': False}
    require(strict_json(json.dumps(summary, allow_nan=False)) == summary, 'strict JSON-safe result')
    return summary


if __name__ == '__main__':
    require(len(sys.argv) == 1, 'silent CLI accepts no arguments')
    check()

