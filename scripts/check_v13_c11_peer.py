#!/usr/bin/env python3
"""C11 independent finite primitives; peer review remains in preparation.

The final check() and exact canonical bindings will be added only after the
complete manuscript and canonical author quartet have been independently read.
"""
from fractions import Fraction as F
from itertools import permutations, product


def need(ok, why):
    if not ok: raise ValueError(why)


def q(value):
    need(type(value) in (int, F), 'exact rational witness')
    value = F(value)
    need(abs(value) <= 10**6 and value.denominator <= 10**9, 'bounded rational witness')
    return value


def preferences(left, right):
    need(type(left) is dict and type(right) is dict and len(left) <= 4 and len(right) <= 4,
         'finite two-sided preference dictionaries')
    need(not set(left) & set(right), 'disjoint participant labels')
    for own, other in ((left, right), (right, left)):
        for person, acceptable in own.items():
            need(type(person) is str and 1 <= len(person) <= 16, 'participant label')
            need(type(acceptable) in (tuple, list), 'ordered acceptable list')
            need(len(acceptable) == len(set(acceptable)) and all(x in other for x in acceptable),
                 'strict list of existing opposite-side partners')
    return {i: tuple(left[i]) for i in sorted(left)}, {i: tuple(right[i]) for i in sorted(right)}


def deferred(left, right, reverse=False, reject=None):
    left, right = preferences(left, right)
    need(type(reverse) is bool and (reject is None or reject in right), 'schedule and rejecting receiver')
    held = {i: None for i in right}; partners = {i: None for i in left}
    next_name = {i: 0 for i in left}; trace = []
    while True:
        free = [i for i in left if partners[i] is None and next_name[i] < len(left[i])]
        if not free: break
        i = sorted(free, reverse=reverse)[0]
        j = left[i][next_name[i]]; next_name[i] += 1
        old = held[j]
        accept = j != reject and i in right[j] and (old is None or right[j].index(i) < right[j].index(old))
        trace.append((i, j, old, accept))
        if accept:
            if old is not None: partners[old] = None
            held[j], partners[i] = i, j
    need(len(trace) <= len(left)*len(right), 'finite pair proposal bound')
    return partners, held, tuple(trace)


def blocking(applicants, institutions, match):
    applicants, institutions = preferences(applicants, institutions)
    need(type(match) is dict and set(match) == set(applicants), 'complete applicant matching map')
    used = [h for h in match.values() if h is not None]
    need(len(used) == len(set(used)), 'one applicant per institution')
    inverse = {h: a for a, h in match.items() if h is not None}
    for a, h in match.items():
        need(h is None or (h in applicants[a] and a in institutions.get(h, ())), 'mutual acceptability')
    result = []
    for a, acceptable in applicants.items():
        for h in acceptable:
            if a not in institutions[h] or match[a] == h: continue
            improve_a = match[a] is None or acceptable.index(h) < acceptable.index(match[a])
            incumbent = inverse.get(h)
            improve_h = incumbent is None or institutions[h].index(a) < institutions[h].index(incumbent)
            if improve_a and improve_h: result.append((a, h))
    return tuple(result)


def stable_matchings(applicants, institutions):
    applicants, institutions = preferences(applicants, institutions)
    people = tuple(applicants); candidates = (None,)+tuple(institutions)
    stable, feasible = [], 0
    for partners in product(candidates, repeat=len(people)):
        used = [h for h in partners if h is not None]
        if len(used) != len(set(used)): continue
        match = dict(zip(people, partners))
        if any(h is not None and (h not in applicants[a] or a not in institutions[h]) for a, h in match.items()): continue
        feasible += 1
        if not blocking(applicants, institutions, match): stable.append(match)
    return tuple(stable), feasible


def menu(applicants, institutions, person):
    applicants, institutions = preferences(applicants, institutions)
    need(person in applicants, 'menu applicant')
    _, _, trace = deferred(institutions, applicants, reject=person)
    offers = {None} | {h for h, recipient, _, _ in trace if recipient == person}
    without = {i: lst for i, lst in applicants.items() if i != person}
    priorities = {h: tuple(i for i in lst if i != person) for h, lst in institutions.items()}
    removed, _, _ = deferred(priorities, without)
    comparative = {None}
    for h, ranking in institutions.items():
        if person in ranking and (removed[h] is None or ranking.index(person) < ranking.index(removed[h])):
            comparative.add(h)
    return offers, comparative, removed


def top(ordered, options):
    return next(x for x in tuple(ordered)+(None,) if x in options)


def report_family(names):
    need(type(names) in (tuple, list) and len(names) <= 4 and len(set(names)) == len(names), 'bounded report universe')
    return tuple(report for size in range(len(names)+1) for report in permutations(names, size))


def value_assignments(values, forbidden=()):
    need(type(values) is dict and 1 <= len(values) <= 4, 'finite valued buyers')
    buyers = tuple(sorted(values)); goods = tuple(sorted(values[buyers[0]]))
    need(1 <= len(goods) <= 3 and all(type(values[i]) is dict and set(values[i]) == set(goods) for i in buyers),
         'rectangular object values')
    amounts = {(i, j): q(values[i][j]) for i in buyers for j in goods}
    need(min(amounts.values()) >= 0 and type(forbidden) in (tuple, list, set), 'nonnegative assignment values')
    banned = set(forbidden); need(banned <= set(amounts), 'forbidden edges belong to the model')
    all_plans = []
    for selected in product((None,)+goods, repeat=len(buyers)):
        sold = [j for j in selected if j is not None]
        if len(sold) != len(set(sold)): continue
        if any((i, j) in banned for i, j in zip(buyers, selected)): continue
        score = sum((amounts[i, j] for i, j in zip(buyers, selected) if j is not None), F(0))
        all_plans.append((score, tuple(zip(buyers, selected))))
    maximum = max(score for score, _ in all_plans)
    return maximum, tuple(plan for score, plan in all_plans if score == maximum), tuple(all_plans)


def price_certificate(values, utility, prices, forbidden=()):
    maximum, attaining, plans = value_assignments(values, forbidden)
    need(set(utility) == set(values) and set(prices) == set(next(iter(values.values()))), 'certificate dimensions')
    utility = {i: q(v) for i, v in utility.items()}; prices = {j: q(v) for j, v in prices.items()}
    need(min(utility.values()) >= 0 and min(prices.values()) >= 0, 'nonnegative certificate')
    gaps = {(i, j): utility[i]+prices[j]-q(value) for i in values for j, value in values[i].items()
            if (i, j) not in forbidden}
    need(min(gaps.values()) >= 0, 'every allowed value has a dual upper bound')
    upper = sum(utility.values())+sum(prices.values())
    return maximum, attaining, plans, upper, gaps


def path_payoffs(actions, beta):
    need(type(actions) in (tuple, list) and len(actions) == 3, 'three path efforts')
    x = tuple(q(v) for v in actions); b = q(beta)
    need(min(x) >= 0 and b >= 0, 'nonnegative effort and complementarity')
    neighbors = (x[1], x[0]+x[2], x[1])
    return tuple(v-v*v/2+b*v*z for v, z in zip(x, neighbors))


def path_best(actions, beta, subsidy=(0, 0, 0), cap=None):
    path_payoffs(actions, beta)
    need(type(subsidy) in (tuple, list) and len(subsidy) == 3, 'three action subsidy rates')
    x = tuple(q(v) for v in actions); b = q(beta); s = tuple(q(v) for v in subsidy)
    if cap is not None:
        cap = q(cap); need(cap > 0 and max(x) <= cap, 'positive effort cap')
    reply = tuple(max(F(0), 1+t+b*z) for t, z in zip(s, (x[1], x[0]+x[2], x[1])))
    return tuple(min(cap, v) for v in reply) if cap is not None else reply


def complementary_path(beta):
    b = q(beta); need(b >= 0, 'nonnegative complementarity')
    denominator = 1-2*b*b
    if denominator <= 0: return None
    # Add the two leaf equations and use the center's first-order condition.
    center = (1+2*b)/denominator
    leaf = 1+b*center
    return leaf, center, leaf


def funded_effort(actions):
    actions = tuple(q(x) for x in actions)
    need(len(actions) == 3 and min(actions) >= 0 and max(actions) <= 4, 'declared funded effort box')
    rates = (F(1), F(3, 2), F(1)); received = tuple(s*x for s, x in zip(rates, actions))
    charges = tuple((sum(received)-received[i])/2 for i in range(3))
    transfer = tuple(a-b for a, b in zip(received, charges))
    cash = tuple(10+t for t in transfer)
    return charges, received, transfer, cash


def substitute_best(actions, gamma):
    need(type(actions) in (tuple, list) and len(actions) == 2, 'two substitute efforts')
    x, y = map(q, actions); g = q(gamma)
    need(min(x, y, g) >= 0, 'nonnegative substitute primitives')
    return max(F(0), 1-g*y), max(F(0), 1-g*x)


def substitute_payoffs(actions, gamma):
    substitute_best(actions, gamma)
    x, y = map(q, actions); g = q(gamma)
    return x-x*x/2-g*x*y, y-y*y/2-g*x*y


EDGES = ((0, 1), (0, 2), (1, 2))


def graph_payoffs(mask, rho, cost, transfers=False):
    need(type(mask) is int and 0 <= mask < 8 and type(transfers) is bool, 'three-node graph and transfer switch')
    r, c = q(rho), q(cost); need(0 < r < 1 and c >= 0, 'discount and maintenance cost')
    neighbors = [set() for _ in range(3)]
    for bit, (i, j) in enumerate(EDGES):
        if mask & (1 << bit): neighbors[i].add(j); neighbors[j].add(i)
    benefits = []
    for i in range(3):
        benefit = F(0)
        for j in range(3):
            if j == i: continue
            if j in neighbors[i]: benefit += r
            elif neighbors[i] & neighbors[j]: benefit += r*r
        benefits.append(benefit)
    charges = tuple(c*len(ns) for ns in neighbors)
    net = [F(0)]*3; outgoing = [F(0)]*3
    if transfers:
        # Node2 is index1. Each designated leaf link pays it3/20.
        for leaf in (0, 2):
            if 1 in neighbors[leaf]:
                net[leaf] -= F(3, 20); net[1] += F(3, 20); outgoing[leaf] += F(3, 20)
    payoff = tuple(benefits[i]-charges[i]+net[i] for i in range(3))
    funded_due = tuple(charges[i]+outgoing[i] for i in range(3))
    return payoff, tuple(net), funded_due


def graph_incentives(mask, rho, cost, transfers=False):
    original = graph_payoffs(mask, rho, cost, transfers)[0]
    gains, stable = [], True
    for bit, ends in enumerate(EDGES):
        changed = graph_payoffs(mask ^ (1 << bit), rho, cost, transfers)[0]
        delta = tuple(changed[i]-original[i] for i in ends)
        present = bool(mask & (1 << bit))
        blocked = any(x > 0 for x in delta) if present else min(delta) >= 0 and max(delta) > 0
        if blocked: stable = False
        gains.append((EDGES[bit], present, delta, blocked))
    return stable, tuple(gains)


class Audit:
    def __init__(self): self.comparisons = 0
    def eq(self, x, y, why):
        self.comparisons += 1; need(x == y, why+': '+repr(x)+' != '+repr(y))
    def yes(self, x, why): self.eq(bool(x), True, why)


def preliminary():
    """Read-only provisional derivation, independent of all author output files."""
    audit = Audit()
    small_a = {'A': ('X', 'Y'), 'B': ('Y', 'X'), 'C': ('Z',), 'D': ('Z',)}
    small_h = {'X': ('B', 'A'), 'Y': ('A', 'B'), 'Z': ('C', 'D')}
    large_a = {'A': ('X', 'Y', 'Z', 'W'), 'B': ('Y', 'Z', 'X', 'W'),
               'C': ('Z', 'X', 'Y', 'W'), 'D': ('X', 'W', 'Y', 'Z')}
    large_h = {'X': ('C', 'A', 'D', 'B'), 'Y': ('A', 'B', 'C', 'D'),
               'Z': ('B', 'C', 'A', 'D'), 'W': ('D', 'A', 'B', 'C')}
    matching = {}; reports_checked = 0
    for name, ap, hp in (('incomplete', small_a, small_h), ('complete', large_a, large_h)):
        stable, feasible = stable_matchings(ap, hp)
        applicant, _, _ = deferred(ap, hp); _, institution, _ = deferred(hp, ap)
        audit.eq(deferred(ap, hp, True)[0], applicant, 'opposite legal schedules agree')
        audit.yes(applicant in stable and institution in stable, 'both side-optimal outcomes pass every blocking-pair test')
        for result in stable:
            audit.eq({i for i, partner in result.items() if partner is None},
                     {i for i, partner in applicant.items() if partner is None}, 'identical unmatched applicant sets')
            audit.eq(set(hp)-set(result.values()), set(hp)-set(applicant.values()), 'identical unmatched institutions')
        menus = {}
        for person in ap:
            offers, comparisons, _ = menu(ap, hp, person)
            audit.eq(offers, comparisons, 'reject-all trace and removed-market priority menu agree')
            menus[person] = tuple(sorted(x for x in offers if x is not None))
            audit.eq(applicant[person], top(ap[person], offers), 'truth chooses the best fixed menu member')
            for report in report_family(tuple(hp)):
                changed = dict(ap); changed[person] = report
                result = deferred(changed, hp)[0][person]
                audit.eq(result, top(report, offers), 'every ordered-subset report chooses its own best fixed-menu element')
                audit.yes(result is None or result in offers, 'every report outcome belongs to the report-independent menu')
                reports_checked += 1
        matching[name] = {'stable': stable, 'feasible_count': feasible, 'applicant': applicant,
                          'institution': institution, 'menus': menus}
    without_c = {i: v for i, v in small_a.items() if i != 'C'}
    priorities = {h: tuple(i for i in order if i != 'C') for h, order in small_h.items()}
    audit.eq(deferred(without_c, priorities)[0]['D'], 'Z', 'removing a competitor changes the environment')
    changed_h = dict(small_h); changed_h['Z'] = ('D', 'C')
    audit.eq((deferred(small_a, changed_h)[0]['C'], deferred(small_a, changed_h)[0]['D']),
             (None, 'Z'), 'changing a priority changes the menu')
    lie_h = dict(large_h); lie_h['X'] = ('C', 'D', 'A', 'B')
    manipulated = deferred(large_a, lie_h)[0]
    audit.yes(manipulated in matching['complete']['stable'], 'recipient manipulation selects a different true-stable outcome')
    caps = {k: deferred({i: order[:k] for i, order in large_a.items()}, large_h)[0] for k in (1, 2)}
    one = {i: order[:1] for i, order in large_a.items()}; one['D'] = ('W',)
    audit.eq((caps[1]['D'], deferred(one, large_h)[0]['D']), (None, 'W'), 'sincere top-one report is not protected full truth')
    audit.eq(caps[2], matching['complete']['applicant'], 'two-name cap preserves this baseline outcome')
    audit.eq(deferred({}, {})[0], {}, 'empty market boundary')
    audit.eq(deferred({'A': ()}, {'X': ('A',)})[0], {'A': None}, 'outside outranks every falsely acceptable institution')

    vals = {'A': {'X': 12, 'Y': 8, 'Z': 2}, 'B': {'X': 10, 'Y': 6, 'Z': 5}, 'C': {'X': 4, 'Y': 9, 'Z': 7}}
    # Solve displayed certificate from its independent tight constraints and pZ=0.
    baseline_p = {'Z': F(0), 'X': F(vals['B']['X']-vals['B']['Z']), 'Y': F(vals['C']['Y']-vals['C']['Z'])}
    baseline_u = {'A': vals['A']['X']-baseline_p['X'], 'B': F(vals['B']['Z']), 'C': F(vals['C']['Z'])}
    bx = price_certificate(vals, baseline_u, baseline_p)
    audit.eq(bx[0], bx[3], 'assignment attains the all-partial-allocation certificate')
    changed_p = {'Z': F(0), 'Y': baseline_p['Y']}
    changed_u = {'C': F(vals['C']['Z']), 'B': vals['B']['Y']-changed_p['Y']}
    changed_p['X'] = vals['B']['X']-changed_u['B']; changed_u['A'] = vals['A']['X']-changed_p['X']
    rx = price_certificate(vals, changed_u, changed_p, (('B', 'Z'),))
    audit.eq(rx[0], rx[3], 'forbidden-edge certificate attains both complete assignments')
    audit.yes(changed_u['B']+changed_p['Z'] < vals['B']['Z'], 'removed inequality really differs from unrestricted problem')
    cash = (20-baseline_p['X'], F(20), 20-baseline_p['Y'])
    audit.eq(sum(cash)+sum(baseline_p.values()), 60, 'owned-object cash transfers conserve the actual endowment')

    b = F(1, 4); equilibrium = complementary_path(b); utilities = path_payoffs(equilibrium, b)
    audit.eq(path_best(equilibrium, b), equilibrium, 'interior complementary fixed point is feasible')
    efficient = (F(3), F(4), F(3)); planner_u = path_payoffs(efficient, b)
    audit.eq(tuple(1+x for x in (b*8, b*12, b*8)), efficient, 'planner derivative uses twice the network externality')
    audit.eq(sum(planner_u), 5, 'planner physical welfare')
    charges, receipts, transfer, balances = funded_effort(efficient)
    audit.eq(sum(charges), sum(receipts), 'fee pool finances every subsidy')
    audit.eq(sum(balances), 30, 'closed implementation cash account')
    audit.eq(path_best(efficient, b, (1, F(3, 2), 1), 4), efficient, 'funded capped best responses implement the planner')
    for corner in product((0, 4), repeat=3):
        fees, subsidies, _, closing = funded_effort(corner)
        audit.eq(sum(fees), sum(subsidies), 'linear funding equality at every box corner')
        audit.yes(max(fees) <= 10 and min(closing) >= 0, 'pre-collected charges are funded before subsidies')
    high = complementary_path(F(3, 5)); audit.eq(path_best(high, F(3, 5)), high, 'failed sufficient contraction test need not eliminate equilibrium')
    audit.eq(complementary_path(F(3, 4)), None, 'positive best replies exclude infeasible inverse solution')
    audit.eq(path_best((2, 2, 2), F(3, 4), cap=2), (2, 2, 2), 'changed capped action domain has the stated fixed point')
    substitution = {}
    for g in (F(1, 2), F(1), F(2)):
        sym = (1/(1+g),)*2
        witnesses = ((F(0), F(1)), (F(1, 4), F(3, 4)), (F(1, 2), F(1, 2)), (F(1), F(0))) if g == 1 else (sym,)
        if g > 1: witnesses += ((F(1), F(0)), (F(0), F(1)))
        for x in witnesses: audit.eq(substitute_best(x, g), x, 'every reported active pattern is a feasible equilibrium')
        substitution[str(g)] = [(x, sum(substitute_payoffs(x, g))) for x in witnesses]

    rho = F(3, 5); network = {}
    for cost in (F(0), rho-rho*rho, F(1, 2), rho, F(7, 10), rho+rho*rho/2, F(1)):
        utility = {mask: graph_payoffs(mask, rho, cost)[0] for mask in range(8)}
        stable = tuple(mask for mask in range(8) if graph_incentives(mask, rho, cost)[0])
        best = max(sum(u) for u in utility.values())
        efficient_graphs = tuple(mask for mask, u in utility.items() if sum(u) == best)
        for mask in range(8):
            edges = mask.bit_count()
            predicted = (cost >= rho if edges == 0 else False if edges == 1 else
                         rho-rho*rho <= cost <= rho if edges == 2 else cost <= rho-rho*rho)
            audit.eq(mask in stable, predicted, 'every graph and strict/weak consent boundary')
        network[str(cost)] = {'stable': stable, 'efficient': efficient_graphs, 'welfare': best}
    path_mask = 5  # {12,23}; center is index1.
    contracted = graph_payoffs(path_mask, rho, F(7, 10), True)
    for mask in range(8):
        u, transfers, due = graph_payoffs(mask, rho, F(7, 10), True)
        audit.eq(sum(transfers), 0, 'link-contingent transfers are balanced at every graph')
        audit.yes(max(due) < 2, 'all maintenance and leaf payments precede benefits and are endowed')
        audit.eq(sum(u), sum(graph_payoffs(mask, rho, F(7, 10))[0]), 'balanced transfers preserve graph welfare')
    audit.yes(graph_incentives(path_mask, rho, F(7, 10), True)[0], 'contracted path survives every link comparison')
    audit.yes(graph_incentives(0, rho, F(7, 10), True)[0], 'empty also survives every bilateral link comparison')
    audit.yes(2*rho-2*F(7, 10) < 0, 'no balanced bilateral transfer finances a Pareto-improving first edge')
    return {'comparisons': audit.comparisons, 'reports_checked': reports_checked,
            'matching': matching, 'recipient_manipulation': manipulated, 'caps': caps,
            'assignment': (bx[0], bx[1], baseline_p, baseline_u),
            'restricted_assignment': (rx[0], rx[1], changed_p, changed_u),
            'complements': (equilibrium, utilities, sum(utilities)),
            'planner': (efficient, planner_u, sum(planner_u)),
            'funded': (charges, receipts, transfer, balances, tuple(u+t for u, t in zip(planner_u, transfer))),
            'high_beta': high, 'substitutes': substitution, 'graphs': network,
            'contracted_path': (contracted, graph_incentives(path_mask, rho, F(7, 10), True)[1])}
