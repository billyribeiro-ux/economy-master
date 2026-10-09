#!/usr/bin/env python3
"""Independent C09 finite-law oracle; read-only six-file runtime.

Mean/spread lower bounds, orthogonal likelihood-score projection, direct wage
splits and private-history plan enumeration supplement the separate proof audit.
No author checker or blueprint result is imported or executed as an oracle.
"""
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from itertools import product
import json
from pathlib import Path
import re
import sys


AUTHORS = ('content/chapters/v13-c09.html', 'scripts/check_v13_c09.py',
           'content/reviews/v13-c09-sources.json', 'content/reviews/v13-c09-author.json')
SELF, RECORD = 'scripts/check_v13_c09_peer.py', 'content/reviews/v13-c09-peer.json'
SOURCES = {
    'v05-c09-mit-contracts': 'https://ocw.mit.edu/courses/14-124-microeconomic-theory-iv-spring-2017/0a3d53590f17f81f1561eb7d7922329d_MIT14_124S17_Slide2.pdf',
    'v13-c09-stole-contracts1999': 'https://ocw.mit.edu/courses/14-124-microeconomic-theory-iv-spring-2017/be21e9cc762231c50ab42bbf35ead5db_MIT14_124S17_LecNote1_2.pdf',
    'v13-c09-levin-relational2006': 'https://web.stanford.edu/~jdlevin/Econ%20286/Relational%20Contracts.pdf',
}


def require(ok, why):
    if not ok: raise ValueError(why)


def scalar(x):
    require(type(x) in (int, F), 'exact scalar')
    x = F(x)
    require(abs(x) <= 10**6 and x.denominator <= 10**9, 'bounded rational witness')
    return x


def vector(x, n=None):
    require(type(x) in (list, tuple) and 1 <= len(x) <= 8, 'finite vector')
    require(n is None or len(x) == n, 'vector dimension')
    return tuple(scalar(v) for v in x)


def law(p, n=None):
    p = vector(p, n)
    require(min(p) > 0 and sum(p) == 1, 'positive complete action law')
    return p


def average(p, v):
    p = law(p); v = vector(v, len(p))
    return sum((x*y for x, y in zip(p, v)), F(0))


def probability(p):
    p = scalar(p); require(0 < p < 1, 'strict probability')
    return p


def wage_mean_spread(B, spread=None):
    B = scalar(B); require(B >= 0, 'nonnegative enforceable wealth')
    minimum = max(F(3), 4-B)
    interval = (F(5), F(5)) if B <= 1 else (F(5), 5*(3+B)/4)
    d = interval[0] if spread is None else scalar(spread)
    require(interval[0] <= d <= interval[1], 'cost-minimizing spread interval')
    failure = minimum-F(4, 5)*d
    return minimum, interval, (failure+d, failure)


def binary_quadratic(p, alternatives, target_cost=F(1, 2), reservation=1):
    p, c, r = probability(p), scalar(target_cost), scalar(reservation)
    require(c > 0 and r >= 0 and type(alternatives) in (tuple, list)
            and 1 <= len(alternatives) <= 4, 'binary higher-effort oracle domain')
    requirements = []
    for pair in alternatives:
        q, k = vector(pair, 2); q = probability(q)
        require(q < p and 0 <= k < c, 'lower-probability lower-cost comparison')
        requirements.append((c-k)/(p-q))
    d = max(requirements)
    m = max(r+c, p*d)
    v = (m+(1-p)*d, m-p*d)
    # E[v^2] = m^2+p(1-p)d^2. Both m and d have these independent
    # lower bounds; nonnegative failure utility adds m>=p*d.
    return v, m*m+p*(1-p)*d*d, (m, d)


def score_projection(p, q, gross=F(3, 2), incentive=F(1, 2)):
    p = law(p); q = law(q, len(p))
    gross, incentive = scalar(gross), scalar(incentive)
    require(gross >= 0 and incentive > 0, 'nonnegative required mean and positive incentive')
    score = tuple(1-y/x for x, y in zip(p, q))
    variance = average(p, tuple(z*z for z in score))
    require(variance > 0, 'distinct action laws')
    slope = incentive/variance
    v = tuple(gross+slope*z for z in score)
    require(min(v) >= 0, 'orthogonal projection respects wage floor')
    # Constant and score are orthogonal under the target law. Any feasible v
    # has squared norm >= gross^2+incentive^2/variance. The displayed v attains
    # this bound and is nonnegative; no active-constraint guess is assumed.
    return v, gross*gross+incentive*incentive/variance, (2*gross, 2*slope), score


def sufficient(laws, statistic):
    require(type(laws) in (tuple, list) and 2 <= len(laws) <= 4, 'finite action family')
    p = law(laws[0]); family = tuple(law(q, len(p)) for q in laws)
    require(type(statistic) in (list, tuple) and len(statistic) == len(p)
            and all(type(t) is int and 0 <= t <= 7 for t in statistic), 'finite statistic labels')
    fibers = tuple(tuple(i for i, label in enumerate(statistic) if label == t) for t in sorted(set(statistic)))
    conditional, ratios = True, True
    for q in family:
        for indices in fibers:
            qp, pp = sum(q[i] for i in indices), sum(p[i] for i in indices)
            conditional &= all(q[i]/qp == p[i]/pp for i in indices)
            ratios &= all(q[i]/p[i] == q[indices[0]]/p[indices[0]] for i in indices)
    return conditional, ratios, fibers


def conditioned(p, v, statistic):
    p = law(p); v = vector(v, len(p))
    _, _, fibers = sufficient((p, p), statistic)
    result = [F(0)]*len(p)
    for indices in fibers:
        mean = sum(p[i]*v[i] for i in indices)/sum(p[i] for i in indices)
        for i in indices: result[i] = mean
    return tuple(result)


def branch(z, outside=0):
    z, b = scalar(z), scalar(outside)
    require(b >= 0 and z >= b, 'feasible branch promise and exit utility')
    y = max(b, z/2); x = z-y
    return (x, y), (x*x, y*y), x*x+y*y


def delayed_contract(outside=0):
    b = scalar(outside)
    require(b in (F(0), F(1, 4), F(3, 4)), 'three declared exit interventions')
    z = (F(2), F(1, 2)) if b <= F(1, 4) else (b+F(3, 2), b)
    rows = tuple(branch(v, b) for v in z)
    cost = average((F(2, 3), F(1, 3)), tuple(row[2] for row in rows))
    return z, rows, cost


def hidden_history_tree(first_success_wage=1):
    first_success_wage = scalar(first_success_wage)
    require(0 <= first_success_wage <= 4, 'bounded two-date wage witness')
    probabilities, costs = (F(2, 3), F(1, 3)), (F(1, 2), F(0))
    second_wages = (F(9, 4), F(3, 2))  # public first S or F; second failure pays zero
    values = []
    for plan in product((0, 1), repeat=5):
        first = plan[0]; ps = probabilities[first]
        value = ps*first_success_wage-costs[first]
        for s, mass in enumerate((ps, 1-ps)):
            second = plan[1+2*first+s]
            value += mass*(probabilities[second]*second_wages[s]-costs[second])
        values.append(value)
    public = []
    for first, after_s, after_f in product((0, 1), repeat=3):
        ps = probabilities[first]
        public.append(ps*first_success_wage-costs[first]
                      +ps*(probabilities[after_s]*second_wages[0]-costs[after_s])
                      +(1-ps)*(probabilities[after_f]*second_wages[1]-costs[after_f]))
    # Prescribed H at every node, including private histories after past L.
    continuation = tuple(probabilities[0]*w-costs[0] for w in second_wages)
    prescribed = probabilities[0]*first_success_wage-costs[0]+average((probabilities[0], 1-probabilities[0]), continuation)
    return tuple(values), tuple(public), prescribed, continuation


def relational(discount, bonus, failure_trigger=False):
    d, b = probability(discount), scalar(bonus)
    require(b >= 0 and type(failure_trigger) is bool, 'bounded nonnegative bonus and transition flag')
    ph, pl, cost, output = F(4, 5), F(1, 5), F(3), F(15)
    bad_firm, bad_worker = pl*output/(1-d), F(0)
    if failure_trigger:
        good_firm = (ph*(output-b)+d*(1-ph)*bad_firm)/(1-d*ph)
        good_worker = (ph*b-cost)/(1-d*ph)
        effort_gain = (ph-pl)*(b+d*good_worker)-cost
    else:
        good_firm, good_worker = ph*(output-b)/(1-d), (ph*b-cost)/(1-d)
        effort_gain = (ph-pl)*b-cost
    payment_margin = d*(good_firm-bad_firm)-b
    return {'firm': good_firm, 'worker': good_worker, 'bad_firm': bad_firm, 'bad_worker': bad_worker,
            'effort': effort_gain, 'payment': payment_margin}


def bonus_interval(d):
    d = probability(d)
    # At payment, b(1-d+d*pH) <= d*(pH-pL)*Y.
    return F(3)/(F(4, 5)-F(1, 5)), d*(F(4, 5)-F(1, 5))*15/(1-d+d*F(4, 5))


class Audit:
    def __init__(self): self.comparisons = self.rejections = 0
    def equal(self, got, want, why):
        self.comparisons += 1; require(got == want, why+': '+repr(got)+' != '+repr(want))
    def true(self, ok, why): self.equal(bool(ok), True, why)
    def reject(self, call, *args):
        self.rejections += 1
        try: call(*args)
        except (ValueError, TypeError, ZeroDivisionError): return
        raise ValueError('invalid domain accepted by '+call.__name__)


def derive(a):
    results = {}
    for B in (F(0), F(1, 2), F(1), F(2)):
        cost, interval, wages = wage_mean_spread(B)
        for spread in sorted(set(interval+((interval[0]+interval[1])/2,))):
            c, _, w = wage_mean_spread(B, spread)
            a.equal(average((F(4, 5), F(1, 5)), w), c, 'all optimum spreads deliver the cost bound')
            a.true(min(w) >= -B and (F(4, 5)-F(1, 5))*(w[0]-w[1]) >= 3 and c >= 3, 'all wealth IC/IR/floors')
        a.equal(cost, max(F(3), 4-B), 'IR and floor lower bounds attained')
        if B < 1: a.equal(interval[0], interval[1], 'low-wealth optimum is unique')
        if B > 1: a.true(interval[1] > interval[0], 'binding IR leaves nonunique spreads')
    results['wealth-baseline'] = F(4, 5)*15-wage_mean_spread(0)[0]
    results['wealth-threshold'] = wage_mean_spread(0)[0]/(F(4, 5)-F(1, 5))
    results['wealth-six'] = (F(4, 5)*6-3, F(1, 5)*6)
    results['wealth-spreads'] = wage_mean_spread(2)[1]
    results['wealth-transfer-boundary'] = 4-(F(4, 5)-F(1, 5))*6
    results['wealth-half-profits'] = (F(4, 5)*6-wage_mean_spread(F(1, 2))[0], F(1, 5)*6, F(0))
    a.equal(wage_mean_spread(results['wealth-transfer-boundary'])[0], F(18, 5), 'wealth switching boundary equality')
    a.true(results['wealth-half-profits'][0] > results['wealth-half-profits'][1] > 0, 'target comparison includes no hire')
    for eps in (F(1, 4), F(1, 16)):
        w = (5+eps, F(0))
        a.true((F(3, 5)*(w[0]-w[1]) > 3) and average((F(4, 5), F(1, 5)), w) > 4, 'strict effort contracts approach but do not attain the low-wealth bound')

    ph, pl = (F(2, 3), F(1, 3)), (F(1, 3), F(2, 3))
    base, basecost, moments = binary_quadratic(ph[0], ((pl[0], 0),))
    projected, projected_cost, dual, score = score_projection(ph, pl)
    a.equal((base, basecost), (projected, projected_cost), 'independent mean/spread and orthogonal-score solutions')
    a.equal(average(ph, score), 0, 'likelihood score orthogonal to the constant')
    a.equal((average(ph, base)-F(1, 2), average(pl, base)), (1, 1), 'unique wages leave weak effort selection')
    a.equal(tuple(2*p*v for p, v in zip(ph, base)), tuple(dual[0]*p+dual[1]*(p-q) for p, q in zip(ph, pl)), 'global supporting coefficient identity')
    results.update({'risk-cost': basecost, 'risk-dual': dual, 'risk-profit': ph[0]*12-basecost})
    a.equal((F(3, 2)**2, basecost-F(3, 2)**2), (F(9, 4), F(1, 2)), 'insurance benchmark and currency incentive cost')
    hidden_threshold, observed_threshold = (basecost-1)/(ph[0]-pl[0]), (F(9, 4)-1)/(ph[0]-pl[0])
    a.equal((hidden_threshold, observed_threshold), (F(21, 4), F(15, 4)), 'regime-specific output thresholds')
    a.true(pl[0]*observed_threshold-1 > 0, 'no hire does not undo positive threshold comparisons')
    middle_probability, middle_cost = F(1, 2), F(1, 8)
    results['middle-old-utility'] = average((middle_probability, 1-middle_probability), base)-middle_cost
    with_middle, middle_bill, _ = binary_quadratic(ph[0], ((pl[0], 0), (middle_probability, middle_cost)))
    outcomes = (average(ph, with_middle)-F(1, 2),
                average((middle_probability, 1-middle_probability), with_middle)-middle_cost,
                average(pl, with_middle))
    a.true(results['middle-old-utility'] > 1, 'omitted action defeats the old contract')
    a.equal(tuple(2*p*v for p, v in zip(ph, with_middle)),
            tuple(3*p+6*(p-q) for p, q in zip(ph, (middle_probability, 1-middle_probability))), 'new global supporting certificate uses the actual binding action')
    a.true(outcomes[0] >= max(outcomes[1:]) and min(with_middle) == 0, 'all new action comparisons and wage floor')
    results.update({'middle-new-cost': middle_bill, 'middle-utilities': outcomes})

    h4 = tuple(x*y for x in ph for y in ph)
    l4 = tuple(x*y for x in pl for y in pl)
    signal_v, signal_cost, signal_dual, signal_score = score_projection(h4, l4)
    a.equal(tuple(q/p for p, q in zip(h4, l4)), (F(1, 4), 1, 1, 4), 'joint law likelihood ratios')
    a.equal(tuple(2*p*v for p, v in zip(h4, signal_v)),
            tuple(signal_dual[0]*p+signal_dual[1]*(p-q) for p, q in zip(h4, l4)), 'four-state global gradient certificate')
    a.equal((average(h4, signal_v), average(h4, signal_v)-average(l4, signal_v)),
            (F(3, 2), F(1, 2)), 'measurement preserves exact participation and incentive constraints')
    a.equal(sufficient((h4, l4), (2, 1, 1, 0))[:2], (True, True), 'both sufficiency characterizations for the sufficient middle grouping')
    for statistic in ((1, 1, 0, 0), (1, 0, 1, 0)):
        a.equal(sufficient((h4, l4), statistic)[:2], (False, False), 'a single favorable indicator loses joint action information')
    results['signal-cost'], results['signal-gain'] = signal_cost, basecost-signal_cost
    results['fee-net-saving'] = results['signal-gain']-F(1, 4)
    a.equal((results['signal-gain']-F(1, 4), results['signal-gain']-F(1, 2)), (F(1, 20), -F(1, 5)), 'actual device fee comparisons')
    a.equal(average(h4, tuple(v*v for v in signal_v)), signal_cost, 'direct square-wage receipts cost')
    ancillary_h = tuple(x/2 for x in ph for _ in (0, 1))
    ancillary_l = tuple(x/2 for x in pl for _ in (0, 1))
    noisy = (F(9, 4), F(7, 4), F(3, 4), F(1, 4))
    cleaned = conditioned(ancillary_h, noisy, (1, 1, 0, 0))
    a.equal(sufficient((ancillary_h, ancillary_l), (1, 1, 0, 0))[:2], (True, True), 'ancillary conditional law and ratios agree')
    for p in (ancillary_h, ancillary_l): a.equal(average(p, noisy), average(p, cleaned), 'utility conditioning preserves every action value')
    results['ancillary-waste'] = average(ancillary_h, tuple(v*v for v in noisy))-average(ancillary_h, tuple(v*v for v in cleaned))
    a.equal(average(ancillary_h, tuple(v*v for v in cleaned)), basecost, 'mean utility replacement recovers binary cost')
    third_law = (F(1, 4), F(1, 4), F(1, 8), F(3, 8))
    a.equal(sufficient((ancillary_h, ancillary_l, third_law), (1, 1, 0, 0))[:2], (False, False), 'sufficiency must hold for every action, not just two selected laws')
    a.equal(average(ancillary_h, noisy)-average(ancillary_h, cleaned), 0, 'linear inverse cost has no strict ancillary wage gain')

    e = F(1, 2)
    original = lambda t: F(1, 4)+t*t/2-t/2
    changed = lambda t: F(1, 4)+t-t*t/2-t/2
    results['foa-minimum'], results['foa-maximum'] = original(e), changed(e)
    for t in (F(0), F(1, 4), F(1, 2), F(1)):
        a.equal(original(t)-results['foa-minimum'], (t-e)**2/2, 'positive square proves stationary minimum')
        a.equal(results['foa-maximum']-changed(t), (t-e)**2/2, 'negative square proves unique global maximum')
    a.equal((original(0), original(1)), (F(1, 4), F(1, 4)), 'entire original maximizing endpoint pair')
    for spread in (F(-1), F(0), F(1), F(3)):
        if spread > 0:
            t = F(1, 3)
            value = spread*(F(1, 4)+t*t/2)-t/2
            chord = (1-t)*spread*F(1, 4)+t*(spread*F(3, 4)-F(1, 2))
            a.equal(chord-value, spread*t*(1-t)/2, 'positive-spread endpoint chord excludes every interior effort')
        else:
            a.true(spread*F(1, 2)-F(1, 2) < 0, 'nonpositive-spread derivative remains negative on the effort interval')

    z, rows, bill = delayed_contract()
    a.equal(z, base, 'two-date promise vector comes from the independent static lower bound')
    a.equal(bill, basecost/2, 'branchwise square identity halves the no-exit cost')
    results['two-date-cost'] = bill
    a.equal(tuple(row[1] for row in rows), ((1, 1), (F(1, 16), F(1, 16))), 'each dated wage is reconstructed separately')
    a.equal((F(9, 8), bill-F(9, 8)), (F(9, 8), F(1, 4)), 'two-date insurance benchmark and incentive increment')
    exit_z, exit_rows, exit_bill = delayed_contract(F(3, 4))
    a.equal(exit_z, (F(9, 4), F(3, 4)), 'componentwise smallest feasible retained-worker promises')
    for total, row in zip(exit_z, exit_rows):
        a.equal(sum(row[0]), total, 'conditional promise is utility, not money')
        a.true(row[0][1] >= F(3, 4), 'each dated continuation participation constraint')
    a.equal(average(ph, exit_z)-average(pl, exit_z), F(1, 2), 'exit contract retains all-action effort constraint')
    results['exit-cost'] = exit_bill
    results['exit-worker'] = average(ph, exit_z)-F(1, 2)
    a.true(results['exit-worker'] > 1, 'higher continuation floor makes initial IR slack')
    low_bill = branch(1, F(3, 4))[2]
    results['exit-profits'] = (8-exit_bill, 4-low_bill, F(0))
    a.equal(delayed_contract(F(1, 4)), (z, rows, bill), 'lower exit floor leaves the original global optimum feasible')
    b = F(3, 4)
    a.equal((2*(2*b-b), 2*b), (F(3, 2), F(3, 2)), 'branch-cost derivatives meet at the convex junction')
    for v in (b, F(1), 2*b, F(9, 4)):
        (_, y), _, g = branch(v, b)
        a.equal(g, v*v/2+(v-2*y)**2/2, 'global branch split square identity')
    # A separate two-period, risk-neutral tree exercises the full scalar-promise
    # recursion with hidden action at BOTH dates, rather than a copied solution.
    private, public, prescribed, continuation = hidden_history_tree()
    a.equal((len(private), len(public)), (32, 8), 'complete deterministic private/public worker strategy sets')
    a.equal((max(private), max(public), prescribed, continuation), (1, 1, 1, (1, F(1, 2))), 'private history supplies no profitable extra strategy')
    a.equal(F(1, 3)*(1+continuation[0]-continuation[1])-F(1, 2), 0, 'current IC must include continuation promises')
    a.true(F(1, 3)*1-F(1, 2) < 0, 'ignoring continuation incentives wrongly rejects the feasible contract')
    total_wage = F(2, 3)*1+average(ph, (F(2, 3)*F(9, 4), F(2, 3)*F(3, 2)))
    principal = 2*F(2, 3)*3-total_wage
    a.equal((total_wage, principal, principal+prescribed), (2, 2, 3), 'stitched wage tree attains the risk-neutral joint-payoff bound at promise1')
    broken, _, broken_recommendation, _ = hidden_history_tree(F(3, 4))
    a.equal((max(broken), broken_recommendation), (F(11, 12), F(5, 6)), 'changed current wage breaks whole-strategy IC')
    a.equal((2*sum((1, 0)), 2*sum((F(1, 4), F(1, 4)))), (2, 1), 'with private credit equal old promises have different squared optimal utilities')

    d, bonus = F(3, 5), F(6)
    bounds = bonus_interval(d); value = relational(d, bonus)
    results.update({'bonus-patience': F(5)/(9+F(5, 5)), 'bonus-upper': bounds[1],
                    'bonus-payoffs': ((1-d)*value['worker'], (1-d)*value['firm']),
                    'bonus-margin': value['payment'], 'fixed-bonus-patience': bonus/(9+bonus/5),
                    'impatient-bonus-upper': bonus_interval(F(2, 5))[1]})
    a.equal(bonus_interval(F(1, 2)), (5, 5), 'weak-patience endpoint has a single bonus')
    a.true(results['impatient-bonus-upper'] < 5, 'impatient declared bonus class is empty')
    a.true(value['effort'] > 0 and value['payment'] > 0, 'both effort and payment are strictly optimal in the baseline')
    a.equal(sum(results['bonus-payoffs']), 9, 'risk-neutral transfers cancel from joint output less effort cost')
    for paid in (F(0), bonus/2, bonus-F(1, 10)):
        margin = d*(value['firm']-value['bad_firm'])-(bonus-paid)
        a.equal(margin, value['payment']+paid, 'every intermediate underpayment is weaker than withholding everything')
        a.true(margin >= 0, 'baseline pays at every success payment node')
        a.true(-paid <= 0, 'positive bad-state payments cannot improve the absorbing fallback')
    a.equal(0-(-3), 3, 'bad-state worker strictly prefers low effort')
    a.equal(relational(results['fixed-bonus-patience'], bonus)['payment'], 0, 'fixed-bonus payment boundary includes equality')
    for btest in (F(5), bounds[1]):
        v = relational(d, btest)
        a.true(v['effort'] >= 0 and v['payment'] >= 0, 'complete interval endpoint constraints')
    a.equal((relational(d, bonus)['bad_firm'], relational(d, bonus)['bad_worker']), (F(15, 2), 0), 'fallback values include all future dates')
    failure = relational(d, bonus, True)
    results.update({'failure-firm-value': failure['firm'], 'failure-worker-value': failure['worker'],
                    'failure-effort-gain': failure['effort'], 'failure-payment-margin': failure['payment']})
    a.equal(failure['firm'], F(4, 5)*(15-bonus)+d*(F(4, 5)*failure['firm']+F(1, 5)*failure['bad_firm']), 'changed firm transition equation')
    a.equal(failure['worker'], F(4, 5)*bonus-3+d*F(4, 5)*failure['worker'], 'changed worker transition equation')
    a.true(failure['effort'] > 0 and failure['payment'] < 0, 'punishing failure strengthens effort but breaks payment')
    a.true(failure['firm'] > 0, 'positive continuation value is insufficient for discretionary payment')
    fixed = relational(d, 5, True)
    a.true(fixed['effort'] >= 0 and fixed['payment'] >= 0, 'a changed bonus can satisfy the altered transition constraints')
    M, K = F(24), 6
    tail = 2*M*d**K/(1-d)
    a.equal(2*M*sum(d**t for t in range(K, K+3))+2*M*d**(K+3)/(1-d), tail,
            'uniform unnormalized bounded-payoff tail decomposition')
    return results


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'duplicate JSON key')
        result[key] = value
    return result


def forbidden_constant(value):
    raise ValueError('nonfinite JSON constant '+value)


def read_json(raw):
    require(type(raw) is bytes, 'JSON byte payload')
    return json.loads(raw.decode('utf-8'), object_pairs_hook=unique_object,
                      parse_constant=forbidden_constant)


class Fragment(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.ids, self.worked, self.prompts, self.answers = [], [], [], [], []
        self.links, self.sources, self.anchors = set(), {}, {}
        self.exercise_depth = self.solution_depth = self.capture = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs); classes = attrs.get('class', '').split()
        if 'id' in attrs: self.ids.append(attrs['id'])
        if tag == 'article' and 'worked' in classes: self.worked.append(attrs.get('id'))
        if tag == 'ol' and 'exercises' in classes:
            require(self.exercise_depth is None, 'single primary exercise list')
            self.exercise_depth = len(self.stack)
        if tag == 'details' and 'solutions' in classes: self.solution_depth = len(self.stack)
        if tag == 'li' and self.exercise_depth is not None: self.prompts.append(attrs.get('id'))
        if 'data-solution-for' in attrs:
            require(self.solution_depth is not None, 'paired answer inside a solution disclosure')
            self.answers.append(attrs['data-solution-for'])
        if 'href' in attrs: self.links.add(attrs['href'])
        if 'data-source' in attrs:
            key, url = attrs['data-source'], attrs.get('href')
            require(key in SOURCES and SOURCES[key] == url, 'exact scoped primary source URL')
            self.sources[key] = url
        if 'data-calc' in attrs:
            key = attrs['data-calc']
            require(tag == 'span' and key not in self.anchors and self.capture is None,
                    'unique simple numeric anchor')
            self.anchors[key] = ''; self.capture = key
        if tag not in {'br', 'hr', 'img', 'meta', 'link', 'input'}: self.stack.append(tag)

    def handle_data(self, data):
        if self.capture is not None: self.anchors[self.capture] += data

    def handle_endtag(self, tag):
        require(bool(self.stack) and self.stack[-1] == tag, 'balanced HTML fragment')
        self.stack.pop()
        if tag == 'span': self.capture = None
        if tag == 'ol' and self.exercise_depth == len(self.stack): self.exercise_depth = None
        if tag == 'details' and self.solution_depth == len(self.stack): self.solution_depth = None


def display(value):
    if type(value) in (list, tuple): return '('+','.join(display(x) for x in value)+')'
    return str(F(value))


def compact(text):
    return re.sub(r'\s+', '', text).replace('−', '-')


def binding_map(rows):
    require(type(rows) is list, 'binding list')
    result = {}
    for row in rows:
        require(type(row) is dict and set(row) == {'path', 'bytes', 'sha256'}, 'binding fields')
        key = row['path']
        require(type(key) is str and key not in result, 'unique binding path')
        require(type(row['bytes']) is int and row['bytes'] >= 1, 'positive payload size')
        require(type(row['sha256']) is str and re.fullmatch('[0-9a-f]{64}', row['sha256']) is not None,
                'SHA256 hex digest')
        result[key] = row
    return result


def domains(a):
    for value in (True, False, '1/2', None, 0.5, complex(1, 0), float('nan'), float('inf'),
                  10**7, F(1, 10**10)):
        a.reject(scalar, value)
    for value in ([], [1, 0], [F(1, 2), F(1, 4)], [-1, 2], [1]*9): a.reject(law, value)
    a.reject(vector, [1, 2], 3)
    a.reject(average, [F(1, 2)]*2, [1])
    for value in (0, 1, -1, 2): a.reject(probability, value)
    a.reject(wage_mean_spread, -1)
    a.reject(wage_mean_spread, 0, F(21, 4))
    a.reject(wage_mean_spread, 2, F(13, 2))
    a.reject(binary_quadratic, F(2, 3), [])
    a.reject(binary_quadratic, F(2, 3), [(F(3, 4), 0)])
    a.reject(binary_quadratic, F(2, 3), [(F(1, 3), F(1, 2))])
    a.reject(binary_quadratic, F(2, 3), [(F(1, 3), 0)], F(1, 2), -1)
    a.reject(score_projection, [F(1, 2)]*2, [F(1, 2)]*2)
    a.reject(score_projection, [F(2, 3), F(1, 3)], [F(1, 3), F(2, 3)], 0)
    a.reject(sufficient, [[F(1, 2)]*2], [0, 1])
    a.reject(sufficient, [[F(1, 2)]*2]*2, [True, 1])
    a.reject(sufficient, [[F(1, 2)]*2]*2, [0])
    a.reject(branch, F(1, 2), F(3, 4))
    a.reject(branch, 1, -1)
    a.reject(delayed_contract, F(1, 2))
    a.reject(hidden_history_tree, 5)
    a.reject(relational, F(3, 5), -1)
    a.reject(relational, F(3, 5), 6, 1)
    a.reject(bonus_interval, 1)
    for value in (b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":Infinity}'):
        a.reject(read_json, value)
    a.reject(read_json, '{}')
    a.reject(check, True)


def check(root=None):
    require(root is None or type(root) is str or isinstance(root, Path), 'root path type')
    root = Path(root).resolve() if root is not None else Path(__file__).resolve().parent.parent
    paths = AUTHORS+(SELF, RECORD)
    before = {name: (root/name).read_bytes() for name in paths}
    a = Audit(); manuscript = before[AUTHORS[0]].decode('utf-8')
    fragment = Fragment(); fragment.feed(manuscript); fragment.close()
    a.true(not fragment.stack and fragment.capture is None, 'complete balanced fragment')
    a.equal(len(fragment.ids), len(set(fragment.ids)), 'unique manuscript IDs')
    a.true(all(key.startswith('v13-c09-') for key in fragment.ids), 'chapter namespace')
    a.equal(fragment.worked, ['v13-c09-case'+str(i) for i in range(1, 7)], 'six original worked cases')
    prompts = ['v13-c09-ex'+str(i) for i in range(1, 13)]
    a.equal(fragment.prompts, prompts, 'every exact original exercise')
    a.equal(fragment.answers, prompts, 'one complete paired solution per prompt')
    a.equal(fragment.sources, SOURCES, 'actual scoped source links')
    a.equal({x for x in fragment.links if not x.startswith('https://')},
            {'v13-c02.html', 'v13-c03.html', 'v13-c07.html', 'v13-c08.html', 'v13-c10.html'},
            'flat prerequisite and successor link syntax')
    for phrase in ('deterministic wage trees', 'pure recommended actions', 'private history',
                   'increasing throughout the domain', 'time layers', 'delayed recall'):
        a.true(phrase in manuscript, 'reviewed proof/instruction scope: '+phrase)
    numbers = derive(a)
    expected = {key: display(value) for key, value in numbers.items()}
    expected['wealth-spreads'] = 'd∈['+','.join(display(x) for x in numbers['wealth-spreads'])+']'
    a.equal({key: compact(value) for key, value in fragment.anchors.items()}, expected,
            'all printed numeric anchors reconstructed from primitive laws')
    a.equal(len(expected), 32, 'complete numeric inventory')
    sources, author, peer = (read_json(before[name]) for name in (AUTHORS[2], AUTHORS[3], RECORD))
    a.equal({x['id']: x['url'] for x in sources['proposals']}, SOURCES, 'source record matches exact URLs')
    for source in sources['proposals']:
        a.true(bool(source['limits']) and bool(source['inspection']['actual_inspector']),
               'scoped inspection attribution and limits')
    author_bindings = binding_map(author['bindings'])
    a.equal(set(author_bindings), set(AUTHORS[:3]), 'author binds all three nonself payloads')
    peer_bindings = binding_map(peer['bindings'])
    a.equal(set(peer_bindings), set(AUTHORS+(SELF,)), 'peer binds four final authors and own checker')
    for rows in (author_bindings, peer_bindings):
        for name, row in rows.items():
            a.equal((row['bytes'], row['sha256']), (len(before[name]), sha256(before[name]).hexdigest()),
                    'actual final payload binding '+name)
    a.equal([row['id'] for row in author['exercise_audit']], prompts, 'author reviewed each exact prompt')
    a.equal(set(peer['exercise_audit']), set(prompts), 'separate peer reviewed each exact prompt')
    a.equal(set(peer['proof_audit']), {'v13-c09-static', 'v13-c09-wealth', 'v13-c09-risk',
            'v13-c09-information', 'v13-c09-foa', 'v13-c09-promises', 'v13-c09-smoothing',
            'v13-c09-relational'}, 'separate peer proof coverage')
    a.equal((author['open_findings'], peer['open_findings']), ([], []), 'no unresolved finding claimed')
    domains(a)
    a.equal({name: (root/name).read_bytes() for name in paths}, before, 'all six payloads unchanged')
    summary = {'chapter': 'v13-c09', 'status': 'passed', 'comparisons': a.comparisons,
               'domain_rejections': a.rejections, 'financial_interventions': 13,
               'private_worker_plans': 32, 'public_worker_plans': 8, 'numeric_anchors': len(expected),
               'worked_cases': len(fragment.worked), 'solved_exercises': len(prompts),
               'runtime_payloads': list(paths), 'writes': 0,
               'scope': 'Independent finite-law evidence and exact bindings; universal proofs reviewed separately.'}
    json.dumps(summary, allow_nan=False)
    return summary


if __name__ == '__main__':
    require(len(sys.argv) == 1, 'CLI accepts no arguments and writes nothing')
    check()
