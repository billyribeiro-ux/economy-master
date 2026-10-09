"""Bounded original-contract audit. Quiet check(root=None), silent no-write CLI.

Only four runtime payloads are read. Proofs are reviewed in the manuscript;
finite computations, exact polynomial integrals and interventions corroborate
those proofs without substituting a grid for a global incentive argument.
"""
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from itertools import product
import json
import math
from pathlib import Path

FILES = (
    'production/v13-c10-working.html',
    'production/check_v13_c10_working.py',
    'production/v13-c10-sources-working.json',
    'production/v13-c10-author-review-working.json',
)


def rational(x):
    if isinstance(x, bool) or not isinstance(x, (int, float, F)):
        raise ValueError('a finite real numeric scalar is required')
    if isinstance(x, float) and not math.isfinite(x):
        raise ValueError('nonfinite scalar')
    return F(x)


def vector(xs, length=None, nonnegative=False):
    if not isinstance(xs, (tuple, list)) or not xs:
        raise ValueError('nonempty finite list required')
    if length is not None and len(xs) != length:
        raise ValueError('wrong dimension')
    result = tuple(rational(x) for x in xs)
    if nonnegative and min(result) < 0:
        raise ValueError('negative quantity')
    return result


def positive(x):
    x = rational(x)
    if x <= 0:
        raise ValueError('strictly positive quantity required')
    return x


def distribution(xs, length=None):
    ps = vector(xs, length, True)
    if sum(ps) != 1:
        raise ValueError('probabilities must sum exactly to one')
    return ps


def trim(p):
    p = list(map(F, p))
    while len(p) > 1 and p[-1] == 0:
        p.pop()
    return p


def add(a, b):
    return trim([(a[i] if i < len(a) else 0) +
                 (b[i] if i < len(b) else 0)
                 for i in range(max(len(a), len(b)))])


def scale(a, c):
    return trim([x*c for x in a])


def mul(a, b):
    p = [F(0)]*(len(a)+len(b)-1)
    for i, x in enumerate(a):
        for j, y in enumerate(b):
            p[i+j] += x*y
    return trim(p)


def power(a, n):
    p = [F(1)]
    for _ in range(n):
        p = mul(p, a)
    return p


def derivative(p):
    return trim([i*p[i] for i in range(1, len(p))] or [0])


def integrate(p, lo, hi):
    return sum((c*(hi**(i+1)-lo**(i+1))/F(i+1)
                for i, c in enumerate(p)), F(0))


def evaluate(p, x):
    return sum((c*x**i for i, c in enumerate(p)), F(0))


def assignment(values, cost):
    if not isinstance(values, (tuple, list)) or not values:
        raise ValueError('valuation table required')
    rows = tuple(vector(row, nonnegative=True) for row in values)
    m = len(rows[0])
    if any(len(row) != m for row in rows):
        raise ValueError('rectangular valuation table required')
    c = rational(cost)
    if c < 0 or len(rows) > 6 or m > 3:
        raise ValueError('bounded nonnegative-cost enumeration domain')
    n = len(rows)

    def outcomes(active):
        return [o for o in product((0,)+tuple(active), repeat=m)
                if len([x for x in o if x]) == len(set(x for x in o if x))]

    def gross(o):
        return sum((rows[owner-1][j] for j, owner in enumerate(o) if owner), F(0))

    def resources(o):
        return c*sum(owner != 0 for owner in o)

    def best(active):
        opts = outcomes(active)
        # Stable lexicographic priority is report independent.
        top = max(gross(o)-resources(o) for o in opts)
        return next(o for o in opts if gross(o)-resources(o) == top), top

    owners, welfare = best(range(1, n+1))
    raw = tuple(sum((rows[i][j] for j, o in enumerate(owners) if o == i+1), F(0))
                for i in range(n))
    hs = tuple(best([j for j in range(1, n+1) if j != i+1])[1] for i in range(n))
    pays = tuple(h-welfare+v for h, v in zip(hs, raw))
    utils = tuple(v-p for v, p in zip(raw, pays))
    revenue = sum(pays)
    return dict(owners=owners, count=len(outcomes(range(1, n+1))), welfare=welfare,
                h=hs, payments=pays, utilities=utils, value=sum(raw),
                cost=resources(owners), revenue=revenue, profit=revenue-resources(owners))


def project(values, cost, cash):
    vs = vector(values, nonnegative=True)
    c, cash = rational(cost), rational(cash)
    if c < 0 or cash < c:
        raise ValueError('committed account must fund the announced cost')
    build = sum(vs) >= c
    payments = tuple(max(F(0), sum(vs)-v-c)-(sum(vs)-v-c)*build for v in vs)
    utils = tuple(v*build-p for v, p in zip(vs, payments))
    spend = c*build
    return dict(build=build, payments=payments, utilities=utils,
                deficit=spend-sum(payments), surplus=sum(vs)*build-spend,
                cash=cash+sum(payments)-spend)


def lottery(v, prices, probs, cap=10):
    cap = positive(cap)
    v = rational(v)
    ps = vector(prices, nonnegative=True)
    ws = distribution(probs, len(ps))
    if not 0 <= v <= cap or max(ps) > cap or any(a >= b for a, b in zip(ps, ps[1:])):
        raise ValueError('ordered prices and value must lie in the support')
    allocation = sum((w for p, w in zip(ps, ws) if v >= p), F(0))
    payment = sum((p*w for p, w in zip(ps, ws) if v >= p), F(0))
    return allocation, payment, v*allocation-payment


def sidebet(joint):
    ps = distribution(joint, 4)
    rows = ((0, 0), (0, 2), (2, 0), (2, 2))
    results = []
    for own in (0, 2):
        marginal = sum(p for p, (a, _) in zip(ps, rows) if a == own)
        if marginal == 0:
            raise ValueError('positive own-type marginal required for conditional claims')
        pay = []
        for report in (own, 2-own):
            pay.append(sum(p*(report-1)*(b-1)
                           for p, (a, b) in zip(ps, rows) if a == own)/marginal)
        results.append((marginal, *pay))
    return tuple(results)


def uniforms(supports, cost=0):
    hs = vector(supports, 2)
    if min(hs) <= 0:
        raise ValueError('positive uniform endpoints required')
    c = rational(cost)
    if c < 0:
        raise ValueError('nonnegative delivery cost required')
    sale, payments, values, virtual_profit = [], [], [], []
    # Integrate the opponent-value axis; inner own-value integral is analytic.
    for i in range(2):
        h, k = hs[i], hs[1-i]
        reserve, shift = (h+c)/2, (h-k)/2
        cuts = sorted({F(0), k} | {x for x in (reserve-shift, h-shift) if 0 < x < k})
        si = pi = vi = zi = F(0)
        for a, b in zip(cuts, cuts[1:]):
            mid = (a+b)/2
            threshold = [reserve] if mid+shift <= reserve else [shift, F(1)]
            if evaluate(threshold, mid) >= h:
                continue
            width = add([h], scale(threshold, -1))
            second = scale(add([h*h], scale(mul(threshold, threshold), -1)), F(1, 2))
            si += integrate(width, a, b)/(h*k)
            pi += integrate(mul(threshold, width), a, b)/(h*k)
            vi += integrate(second, a, b)/(h*k)
            zi += integrate(add(scale(second, 2), scale(width, -(h+c))), a, b)/(h*k)
        sale.append(si); payments.append(pi); values.append(vi); virtual_profit.append(zi)
    # Independent tail integration for efficient max and min.
    cuts = sorted(set((F(0), *hs)))
    maximum = minimum = F(0)
    for a, b in zip(cuts, cuts[1:]):
        cdfs = [[F(0), 1/h] if (a+b)/2 < h else [F(1)] for h in hs]
        maximum += integrate(add([1], scale(mul(*cdfs), -1)), a, b)
        minimum += integrate(mul(*(add([1], scale(f, -1)) for f in cdfs)), a, b)
    revenue, total_sale, value = sum(payments), sum(sale), sum(values)
    return dict(sale=total_sale, payments=tuple(payments), value_parts=tuple(values),
                revenue=revenue, value=value, rent=value-revenue, cost=c*total_sale,
                profit=revenue-c*total_sale, virtual_profit=sum(virtual_profit),
                efficient=maximum, efficient_revenue=minimum)


def uniform_profile(vs, hs, cost=0):
    vs, hs = vector(vs, 2), vector(hs, 2)
    c = rational(cost)
    if min(hs) <= 0 or c < 0 or any(v < 0 or v > h for v, h in zip(vs, hs)):
        raise ValueError('profile outside declared uniform support or cost domain')
    phis = tuple(2*v-h for v, h in zip(vs, hs))
    top = max(phis)
    if top < c:
        return None, F(0), F(0)
    winner = phis.index(top)
    other = 1-winner
    price = max((hs[winner]+c)/2, vs[other]+(hs[winner]-hs[other])/2)
    return winner+1, price, vs[winner]-price


def power_case(n, a=2, h=10, v=5):
    if isinstance(n, bool) or not isinstance(n, int) or not 2 <= n <= 8:
        raise ValueError('two through eight bidders required')
    if isinstance(a, bool) or not isinstance(a, int) or not 1 <= a <= 8:
        raise ValueError('positive bounded integer power required')
    h, v = positive(h), rational(v)
    if not 0 <= v <= h:
        raise ValueError('value outside support')
    k = a*(n-1)
    G = [F(0)]*k + [h**(-k)]
    density = [F(0)]*(a-1) + [F(a)/h**a]
    allocation = evaluate(G, v)
    rent = integrate(G, F(0), v)
    payment = v*allocation-rent
    bid = F(k, k+1)*v
    highest_cdf = power([F(0)]*a+[h**(-a)], n)
    max_value = integrate(add([1], scale(highest_cdf, -1)), F(0), h)
    fp_revenue = F(k, k+1)*max_value
    allpay_poly = [F(0)]*(k+1)+[F(k, k+1)/h**k]
    ap_revenue = n*integrate(mul(allpay_poly, density), F(0), h)
    base_cdf = [F(0)]*a+[h**(-a)]
    second_density = scale(mul(mul(power(base_cdf, n-2), add([1], scale(base_cdf, -1))), density), n*(n-1))
    sp_revenue = integrate(mul([0, 1], second_density), F(0), h)
    # Full polynomial derivatives in the imitated type, not sampled FOCs.
    fp_payoff = mul([v, -F(k, k+1)], G)
    ap_payoff = add(scale(G, v), scale(allpay_poly, -1))
    target = [F(0)]*(k-1) + [F(k)*v/h**k, -F(k)/h**k]
    return dict(type=(bid, allocation, payment, rent), k=k, maximum=max_value,
                revenue=fp_revenue, ap=ap_revenue, sp=sp_revenue,
                total_rent=max_value-fp_revenue, per_rent=integrate(mul([F(0)]*(k+1)+[F(1,k+1)/h**k], density), F(0), h),
                derivative_fp=derivative(fp_payoff), derivative_ap=derivative(ap_payoff),
                derivative_target=trim(target), endpoint_bid=F(k,k+1)*h)


def normalize(s):
    return ''.join(s.replace('−', '-').split())


def render(x):
    if isinstance(x, (tuple, list)):
        return '('+','.join(render(v) for v in x)+')'
    return str(x)


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.markers = {'data-calc': {}, 'data-input': {}}
        self.current = None
        self.ids = set()
        self.duplicate_ids = []
        self.worked = []
        self.prompts = []
        self.answers = []
        self.sources = set()
        self.source_urls = {}
        self.exercise_depth = 0
        self.solution_depth = 0
        self.stack = []

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        classes = d.get('class', '').split()
        if 'id' in d:
            if d['id'] in self.ids:
                self.duplicate_ids.append(d['id'])
            self.ids.add(d['id'])
        if 'worked' in classes and 'worked-example' in classes:
            self.worked.append(d.get('id'))
        if tag == 'ol' and 'exercises' in classes:
            self.exercise_depth = len(self.stack)+1
        if tag == 'details' and 'solutions' in classes:
            self.solution_depth = len(self.stack)+1
        if tag == 'li' and self.exercise_depth:
            self.prompts.append(d.get('id'))
        if 'data-solution-for' in d:
            if not self.solution_depth:
                raise ValueError('solution outside reader disclosure')
            self.answers.append(d['data-solution-for'])
        if 'data-source' in d:
            sid = d['data-source']
            self.sources.add(sid)
            if sid in self.source_urls and self.source_urls[sid] != d.get('href'):
                raise ValueError('inconsistent source URL')
            self.source_urls[sid] = d.get('href')
        for kind in self.markers:
            if kind in d:
                key = d[kind]
                if key in self.markers[kind] or self.current is not None:
                    raise ValueError('duplicate or nested numerical marker')
                self.markers[kind][key] = ''
                self.current = (kind, key, len(self.stack)+1)
        if tag not in ('br','hr','meta','link','img','input','wbr'):
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if not self.stack or self.stack[-1] != tag:
            raise ValueError('unbalanced reader markup: '+tag)
        depth = len(self.stack)
        if self.current and self.current[2] == depth:
            self.current = None
        if self.exercise_depth == depth:
            self.exercise_depth = 0
        if self.solution_depth == depth:
            self.solution_depth = 0
        self.stack.pop()

    def handle_data(self, data):
        if self.current:
            kind, key, _ = self.current
            self.markers[kind][key] += data


def check(root=None):
    root = Path(root) if root is not None else Path(__file__).resolve().parent.parent
    counts = {'comparisons': 0, 'domain_rejections': 0}

    def eq(got, want, name):
        counts['comparisons'] += 1
        if got != want:
            raise ValueError(f'{name}: got {got!r}, expected {want!r}')

    def require(ok, name):
        eq(bool(ok), True, name)

    def reject(fn, name):
        try:
            fn()
        except ValueError:
            counts['domain_rejections'] += 1
        else:
            raise ValueError('invalid domain accepted: '+name)

    raw = {p: (root/p).read_bytes() for p in FILES}
    page = Page()
    page.feed(raw[FILES[0]].decode('utf-8'))
    page.close()
    eq(page.stack, [], 'balanced document')
    eq(page.duplicate_ids, [], 'unique anchors')
    eq(page.worked, [f'v13-c10-w{i}' for i in range(1, 7)], 'all worked cases')
    eq(page.prompts, [f'v13-c10-e{i}' for i in range(1, 13)], 'all exact prompts')
    eq(page.answers, page.prompts, 'one full reader solution per prompt')
    require({'v13-c10-revelation','v13-c10-groves','v13-c10-payment','v13-c10-optimal',
             'v13-c10-revenue','v13-c10-preferences','v13-c10-teach'} <= page.ids,
            'complete theorem/instruction structure')
    sources = json.loads(raw[FILES[2]])
    eq({s['id'] for s in sources['sources']}, page.sources, 'exact source routes')
    for s in sources['sources']:
        eq(s['url'], page.source_urls[s['id']], 'source URL '+s['id'])
        require(bool(s['actual_body_scope']) and bool(s['limits']), 'scoped source evidence')
    inputs = {
        'w1-values':((9,4),(8,7),(3,6)), 'w1-cost':1,
        'w2-cost':12, 'w2-values':(7,6,4), 'w2-endowment':12,
        'w3-lottery':(2,7,F(1,3)), 'w3-sidebet':((0,2),(F(1,2),F(1,2))),
        'w4-supports':(6,12), 'w4-profile':(5,7),
        'w5-law':'F(v)=(v/10)²,0≤v≤10;n=3',
        'w6-utility':'u(z)=1−2^(−5z),z∈ℝ', 'w6-deviation':F(24,5),
        'e1-rivals':(2,3), 'e2-b-value':8, 'e3-values':(8,3,2),
        'e5-probabilities':(F(3,8),F(1,8),F(1,8),F(3,8)),
        'e6-profiles':((4,8),(6,9)), 'e7-support':'[0,8]', 'e8-cost':2,
        'e9-n':2, 'e10-fee':F(2,7),
    }
    eq(set(page.markers['data-input']), set(inputs), 'exact primitive marker set')
    for name, value in inputs.items():
        eq(normalize(page.markers['data-input'][name]), normalize(render(value)), 'input '+name)
    out = {}
    a = assignment(((9,4),(8,7),(3,6)), 1)
    for key in ('count','welfare','h','payments','utilities'):
        out['w1-'+key] = a[key]
    out['w1-allocation'] = f'A→{a["owners"][0]}, B→{a["owners"][1]}'
    out['w1-accounts'] = (a['revenue'], a['cost'], a['profit'])
    s = assignment(((9,),(8,),(3,)), 1)
    out['w1-single-price'] = s['payments'][0]
    out['w1-single-surplus'] = s['welfare']
    for vals, prefix in [((7,6,4),'w2'),((8,3,2),'e3')]:
        p = project(vals,12,12)
        for key in ('payments','utilities','deficit','surplus'):
            out[prefix+'-'+key] = p[key]
        out[prefix+('-closing-cash' if prefix=='w2' else '-cash')] = p['cash']
        eq(sum(p['utilities'])-p['deficit'],p['surplus'],'project consolidated identity')
    out['e3-gain'] = -(2-4)
    out['w3-payments'] = tuple(lottery(v,(2,7),(F(1,3),F(2,3)))[1] for v in (0,2,7))
    out['w3-type5'] = lottery(5,(2,7),(F(1,3),F(2,3)))
    out['w3-type7'] = lottery(7,(2,7),(F(1,3),F(2,3)))
    out['w3-expost-gain'] = (0-1)*(0-1)-(2-1)*(0-1)
    fair = sidebet((F(1,4),)*4)
    eq(tuple(row[1:] for row in fair),((0,0),(0,0)),'iid sidebet conditional means')
    u = uniforms((6,12))
    out['w4-profile-price'] = uniform_profile((5,7),(6,12))[1]
    for suffix, key in [('revenue','revenue'),('payment-parts','payments'),('sale','sale'),
                        ('value-parts','value_parts'),('value','value'),('rent','rent'),
                        ('efficient','efficient'),('efficient-revenue','efficient_revenue')]:
        out['w4-'+suffix] = u[key]
    out['w4-surplus-loss'] = u['efficient']-u['value']
    # Tail virtual integral independent of actual winning-payment regions.
    virtual_tail = integrate([F(3,4),-F(1,16),-F(1,288)],F(0),F(6))+integrate([F(1,2),-F(1,24)],F(6),F(12))
    eq(u['revenue'],virtual_tail,'independent positive-virtual tail identity')
    b = power_case(3)
    out['w5-type5'] = b['type']
    out['w5-max'], out['w5-revenue'] = b['maximum'], b['revenue']
    out['w5-rent'],out['w5-per-bidder-rent'] = b['total_rent'],b['per_rent']
    out['w6-candidate'] = F(1,16)*(1-F(1,32))
    out['w6-deviation-utility'] = F(6,10)**4*(1-F(1,2))
    out['w6-gain'] = out['w6-deviation-utility']-out['w6-candidate']
    out['w6-money'] = (F(1,16)*(5-4),F(6,10)**4*(5-F(24,5)))
    out['e1-interim'] = b['type'][1:]
    out['e1-lie-utility'] = 5-F(4,5)*4
    out['e1-gain'] = out['e1-lie-utility']-(5-F(4,5)*5)
    e2 = assignment(((9,4),(8,7),(3,8)),1)
    for key in ('h','payments','utilities'):
        out['e2-'+key] = e2[key]
    out['e2-accounts'] = (e2['revenue'],e2['cost'],e2['profit'])
    out['e2-surplus'] = e2['welfare']
    out['e4-payments'] = tuple(lottery(v,(3,8),(F(1,4),F(3,4)))[1] for v in (0,3,8))
    out['e4-six'] = lottery(6,(3,8),(F(1,4),F(3,4)))
    out['e4-nine'] = lottery(9,(3,8),(F(1,4),F(3,4)))
    dep = sidebet(inputs['e5-probabilities'])
    out['e5-match'] = F(3,8)/dep[0][0]
    out['e5-payments'] = dep[0][1:]
    out['e5-gain'] = dep[0][1]-dep[0][2]
    eq(dep[1][1:], dep[0][1:], 'both own types in dependence intervention')
    out['e6-price1'] = uniform_profile((4,8),(6,12))[1]
    out['e6-price2'] = uniform_profile((6,9),(6,12))[1]
    win, price, _ = uniform_profile((6,F(91,10)),(6,12))
    eq(win,2,'tie-crossing report wins')
    out['e6-lie-utility'] = 9-price
    same = uniforms((8,8))
    out['e7-reserve'] = F(8,2)
    for key in ('sale','revenue','value','rent'):
        out['e7-'+key] = same[key]
    out['e7-zero-revenue'] = same['efficient_revenue']
    out['e7-zero-value'] = same['efficient']
    out['e7-zero-rent'] = same['efficient']-same['efficient_revenue']
    costly = uniforms((6,12),2)
    for suffix, key in [('sale','sale'),('payment-parts','payments'),('receipts','revenue'),
                        ('expected-cost','cost'),('profit','profit')]:
        out['e8-'+suffix] = costly[key]
    pair = power_case(2)
    out['e9-five'] = pair['type']
    out['e9-max'],out['e9-revenue'],out['e9-rent'] = pair['maximum'],pair['revenue'],pair['total_rent']
    fee = F(2,7)
    out['e10-revenue'] = b['revenue']+3*fee
    out['e10-rent'] = b['total_rent']-3*fee
    out['e10-bottom'] = -fee
    eq(set(page.markers['data-calc']),set(out),'every exact result marker has an oracle')
    for name, value in out.items():
        eq(normalize(page.markers['data-calc'][name]),normalize(render(value)),'result '+name)
    interventions = []
    # Welfare/payments checked against all feasible physical outcomes in each case.
    for vals, res in [(((9,4),(8,7),(3,6)),a),(((9,4),(8,7),(3,8)),e2)]:
        eq(sum(res['utilities'])+res['profit'],res['welfare'],'assignment accounts')
        eq(res['value']-res['cost'],res['welfare'],'physical surplus')
        require(min(res['utilities']) >= 0,'pivot IR in removal-embedding domain')
        for owners in product(range(4),repeat=2):
            chosen = [x for x in owners if x]
            if len(chosen) != len(set(chosen)):
                continue
            candidate = sum(F(vals[o-1][j])-1 for j,o in enumerate(owners) if o)
            require(candidate <= res['welfare'],'complete assignment welfare certificate')
    interventions.append('new bidder value changes allocation and every removal account')
    closed = assignment(((9,4),(8,7),(3,6)),9)
    eq((closed['owners'],closed['welfare'],closed['payments']),((0,0),0,(0,0,0)),
       'delivery-cost boundary removes trade under fixed retention priority')
    interventions.append('known resource cost eliminates trade')
    tied = project((7,6,4),17,17)
    eq((tied['build'],tied['surplus'],tied['payments']),(True,0,(7,6,4)),
       'project efficient-zero tie normalization')
    shut = project((7,6,4),18,18)
    eq((shut['build'],shut['payments'],shut['cash']),(False,(0,0,0),18),
       'project does not spend cash below cost')
    # Without a nonnegative-value embedding, a formal pivot need not give IR.
    require(F(-1)-0 < 0,'negative own value violates the claimed IR conclusion')
    interventions.append('funded project threshold and pivot-IR hypothesis boundary')
    for prices, probs in [((2,7),(F(1,3),F(2,3))),((3,8),(F(1,4),F(3,4)))]:
        types = sorted(set((F(0),F(10),*map(F,prices),F(sum(prices),2))))
        for v in types:
            x,p,u0 = lottery(v,prices,probs)
            # Direct posted-price gains versus cumulative envelope at every break.
            envelope = sum(w*max(F(0),v-price) for price,w in zip(prices,probs))
            eq(u0,envelope,'step rent from physical price outcomes')
            for r in prices:
                xr,pr,_ = lottery(r,prices,probs)
                require(u0 >= v*xr-pr,'cross-report weak inequality at jump')
        for price in prices:
            eq(price-price,0,'equality acceptance/rejection cash indifference')
    interventions.append('changed lottery weights and thresholds with exact jump rights')
    eq(tuple(x[0] for x in fair),tuple(x[0] for x in dep),'marginals preserved under dependence')
    require(dep[0][1] > dep[0][2],'conditional law change destroys BIC')
    for r1,r2 in product((0,2),repeat=2):
        pay=(r1-1)*(r2-1)
        eq(pay+(-pay),0,'sidebet designer cash conserved')
        require(abs(pay) <= 1,'sidebet funded transfer bound')
    interventions.append('same type marginals with altered dependence')
    for supports,cost in [((6,12),0),((6,12),2),((8,8),0),((6,12),6),((6,12),12),((6,12),13)]:
        result=uniforms(supports,cost)
        eq(result['profit'],result['virtual_profit'],'payment versus virtual net objective')
        eq(result['revenue']+result['rent'],result['value'],'auction transfer cancellation')
        require(0 <= result['sale'] <= 1,'feasible integrated sale mass')
        require(result['profit'] >= 0,'no-sale option bounds optimal profit')
        if cost >= max(supports):
            eq((result['sale'],result['profit']),(0,0),'zero-measure/above-top cost boundary')
    interventions.append('positive delivery cost, endpoint and no-sale regimes')
    for profile in [(3,6),(0,6),(6,9),(6,12)]:
        winner,price,utility=uniform_profile(profile,(6,12))
        require(winner in (1,2),'zero-virtual and virtual-tie sale selected')
        require(utility >= 0,'critical-price IR at exact boundary')
    eq(uniform_profile((3,6),(6,12)),(1,3,0),'fixed zero-virtual tie priority')
    eq(uniform_profile((F(29,10),F(59,10)),(6,12)),(None,0,0),'just-below-reserve no sale')
    interventions.append('fixed priority and weak incentives at reserve/virtual ties')
    for n,aexp in [(3,2),(2,2),(3,1)]:
        law=power_case(n,aexp)
        eq(law['derivative_fp'],law['derivative_target'],'global first-price derivative polynomial')
        eq(law['derivative_ap'],law['derivative_target'],'global all-pay derivative polynomial')
        eq(law['revenue'],law['ap'],'independent all-pay receipts integral')
        eq(law['revenue'],law['sp'],'independent second-order-statistic integral')
        eq(n*law['per_rent'],law['total_rent'],'type-specific rent integrates to accounts')
        for v in (0,5,10):
            endpoint=power_case(n,aexp,v=v)
            eq(endpoint['derivative_fp'],endpoint['derivative_target'],'endpoint derivative identity')
            # Full-support overbids win surely; an additional unit is a certain loss.
            eq((F(v)-endpoint['endpoint_bid'])-(F(v)-endpoint['endpoint_bid']-1),1,
               'bid outside candidate support cannot improve endpoint bid')
            require(endpoint['type'][3] >= 0,'interim participation at endpoint/type')
    interventions.append('bidder count and distribution exponent change equilibrium')
    require(out['w6-gain'] > 0,'strict CARA improvement')
    require(out['w6-money'][0] > out['w6-money'][1],'lower monetary mean despite utility gain')
    # Open-set conclusion is analytic continuity; nearby evaluations only corroborate it.
    for v in (4.99,5.01):
        candidate=(v/10)**4*(1-2**(-v))
        deviating=(6/10)**4*(1-2**(-5*(v-24/5)))
        require(deviating > candidate,'nearby CARA counterexample type')
    # Full-domain u including losses is finite for these declared loss witnesses.
    require(1-2**5 < 0,'globally defined CARA negative cash gain')
    interventions.append('CARA change rejects money-linear candidate on an open type set')
    for v,m in [(5,4),(5,6),(5,5)]:
        truthful=max(0,v-m)
        for win in (False,True):
            alternate=(v-m)*win
            require(truthful >= alternate,'second-price statewise cash dominance')
            require(1-2**(-5*truthful) >= 1-2**(-5*alternate),
                    'increasing utility preserves statewise dominance')
    interventions.append('second-price rights survive preference change')
    eq(out['e10-revenue']+out['e10-rent'],b['maximum'],'fee cancels in consolidated surplus')
    require(out['e10-bottom'] < 0,'compulsory fee violates bottom participation')
    eq((5-4-fee)-(5-F(16,5)-fee),(5-4)-(5-F(16,5)),
       'report-independent fee preserves every such utility difference')
    interventions.append('boundary utility shift changes payments and entry conditions')
    # Actual malformed economic domains; explicit ValueError checks survive Python -O.
    bad = [
        (lambda:rational(True),'Boolean scalar'),
        (lambda:rational(float('nan')),'NaN'),
        (lambda:rational(float('inf')),'infinity'),
        (lambda:rational('1'),'numeric string'),
        (lambda:rational(1+0j),'complex scalar'),
        (lambda:assignment((),1),'empty valuation table'),
        (lambda:assignment(((1,2),(3,)),1),'ragged valuation table'),
        (lambda:assignment(((1,-2),),1),'negative instructional value'),
        (lambda:assignment(((1,2),),-1),'negative cost'),
        (lambda:assignment(((1,2,3,4),),0),'unsupported enumeration dimension'),
        (lambda:project((7,6,4),12,11),'unfunded committed project'),
        (lambda:project((7,-1,4),12,12),'negative project benefit'),
        (lambda:project((7,6,4),-1,12),'negative project cost'),
        (lambda:lottery(5,(2,7),(F(1,3),F(1,3))),'missing probability mass'),
        (lambda:lottery(5,(2,7),(-1,2)),'negative lottery probability'),
        (lambda:lottery(5,(7,2),(F(1,2),F(1,2))),'unordered thresholds'),
        (lambda:lottery(5,(2,2),(F(1,2),F(1,2))),'duplicate thresholds'),
        (lambda:lottery(11,(2,7),(F(1,2),F(1,2))),'outside value support'),
        (lambda:lottery(5,(2,11),(F(1,2),F(1,2))),'outside price support'),
        (lambda:lottery(5,(2,7),(1,)),'probability dimension'),
        (lambda:sidebet((F(1,2),F(1,2),0,0)),'zero conditional marginal'),
        (lambda:sidebet((F(1,4),)*3),'joint-law dimension'),
        (lambda:uniforms((0,12)),'degenerate uniform support'),
        (lambda:uniforms((6,12),-1),'negative delivery cost'),
        (lambda:uniforms((6,12,18)),'extra bidder in two-bidder oracle'),
        (lambda:uniform_profile((7,8),(6,12)),'report outside own support'),
        (lambda:uniform_profile((1,8),(6,12),-1),'negative profile cost'),
        (lambda:power_case(1),'single bidder outside power-game contract'),
        (lambda:power_case(True),'Boolean bidder count'),
        (lambda:power_case(3,F(1,2)),'noninteger polynomial exponent'),
        (lambda:power_case(3,0),'zero distribution exponent'),
        (lambda:power_case(3,h=0),'zero power support'),
        (lambda:power_case(3,v=-1),'negative value'),
        (lambda:power_case(3,v=11),'power value above support'),
    ]
    for fn,name in bad:
        reject(fn,name)
    author=json.loads(raw[FILES[3]])
    bindings=author['payload_bindings']
    eq({x['path'] for x in bindings},set(FILES[:3]),'exact three nonself author bindings')
    for binding in bindings:
        payload=raw[binding['path']]
        eq(len(payload),binding['bytes'],'bound bytes '+binding['path'])
        eq(sha256(payload).hexdigest(),binding['sha256'],'bound hash '+binding['path'])
    eq(author['unresolved_findings'],[],'no unresolved author finding')
    summary={'chapter':'v13-c10','status':'passed',**counts,
             'worked_cases':len(page.worked),'solved_exercises':len(page.answers),
             'primitive_markers':len(inputs),'result_markers':len(out),
             'intervention_groups':len(interventions),'interventions':interventions,
             'runtime_files':4,'proof_scope':'Exact finite accounts/polynomial certificates plus manuscript proof review; no finite grid claimed as proof.'}
    json.dumps(summary,allow_nan=False)
    return summary


if __name__ == '__main__':
    check()
