#!/usr/bin/env python3
"""Independent C11 peer: finite stable sets, price bounds and graph deviations.

Read-only six-file runtime; author code and blueprint numerical results are
never imported or executed. Universal claims have a separate full proof audit.
"""
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from itertools import permutations, product
import json
from pathlib import Path
import re
import sys


AUTHORS = ('content/chapters/v13-c11.html', 'scripts/check_v13_c11.py',
           'content/reviews/v13-c11-sources.json', 'content/reviews/v13-c11-author.json')
SELF, RECORD = 'scripts/check_v13_c11_peer.py', 'content/reviews/v13-c11-peer.json'
SOURCES = {
    'v05-c11-manea-matching': 'https://ocw.mit.edu/courses/14-16-strategy-and-information-spring-2016/53dbe8d681978367f9c04182aa3c9b97_MIT14_16S16_Matching.pdf',
    'v13-c11-ght-menu2026': 'https://arxiv.org/pdf/2209.13148v4',
    'v13-c11-pass-assignment': 'https://www.cs.cornell.edu/~rafael/networks-html/chapter8.html',
    'v13-c11-bkd-networks2014': 'https://sites.duke.edu/rachelkranton/files/2016/09/strategic-interaction-and-networks-aer.pdf',
    'v13-c11-jackson-network-formation': 'https://web.stanford.edu/~jacksonm/netsurv.pdf',
}


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
            need(all(type(x) is str and x in other for x in acceptable), 'existing named partners')
            need(len(acceptable) == len(set(acceptable)),
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
    need(all(h is None or type(h) is str for h in match.values()), 'named matching partners or outside')
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
    need(type(names) in (tuple, list) and len(names) <= 4, 'bounded report universe')
    need(all(type(x) is str and 1 <= len(x) <= 16 for x in names) and len(set(names)) == len(names),
         'distinct report labels')
    return tuple(report for size in range(len(names)+1) for report in permutations(names, size))


def value_assignments(values, forbidden=()):
    need(type(values) is dict and 1 <= len(values) <= 4, 'finite valued buyers')
    need(all(type(i) is str and type(row) is dict for i, row in values.items()), 'named buyer value rows')
    buyers = tuple(sorted(values)); goods = tuple(values[buyers[0]])
    need(1 <= len(goods) <= 3 and all(type(j) is str for j in goods)
         and all(set(values[i]) == set(goods) for i in buyers),
         'rectangular object values')
    goods = tuple(sorted(goods))
    amounts = {(i, j): q(values[i][j]) for i in buyers for j in goods}
    need(min(amounts.values()) >= 0 and type(forbidden) in (tuple, list, set), 'nonnegative assignment values')
    need(all(type(edge) is tuple and len(edge) == 2 and all(type(x) is str for x in edge)
             for edge in forbidden), 'named forbidden pairs')
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
    need(type(utility) is dict and type(prices) is dict, 'price and utility dictionaries')
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
    need(type(actions) in (tuple, list), 'funded effort vector')
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
    def __init__(self): self.comparisons = 0; self.rejections = 0
    def eq(self, x, y, why):
        self.comparisons += 1; need(x == y, why+': '+repr(x)+' != '+repr(y))
    def yes(self, x, why): self.eq(bool(x), True, why)
    def reject(self, fn, *args):
        try: fn(*args)
        except ValueError: self.rejections += 1
        else: raise ValueError('invalid domain accepted by '+fn.__name__)


def derive(audit):
    """Finite evidence from primitive preferences, values, payoffs and rights."""
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
    audit.eq(menu(small_a, small_h, 'A')[2], {'X': None, 'Y': 'B', 'Z': 'C'},
             'removing A leaves B at its preferred Y and X unmatched')
    priorities = {h: tuple(i for i in order if i != 'C') for h, order in small_h.items()}
    audit.eq(deferred(without_c, priorities)[0]['D'], 'Z', 'removing a competitor changes the environment')
    changed_h = dict(small_h); changed_h['Z'] = ('D', 'C')
    audit.eq((deferred(small_a, changed_h)[0]['C'], deferred(small_a, changed_h)[0]['D']),
             (None, 'Z'), 'changing a priority changes the menu')
    lie_h = dict(large_h); lie_h['X'] = ('C', 'D', 'A', 'B')
    manipulated = deferred(large_a, lie_h)[0]
    audit.yes(manipulated in matching['complete']['stable'], 'recipient manipulation selects a different true-stable outcome')
    audit.yes(manipulated != matching['complete']['applicant'], 'recipient lie changes its true partner')
    for partners, pair in ((('X', 'Z', 'Y'), ('C', 'X')), (('Y', 'X', 'Z'), ('B', 'Z')),
                           (('Z', 'X', 'Y'), ('A', 'X')), (('Z', 'Y', 'X'), ('A', 'Y'))):
        candidate = dict(zip(('A', 'B', 'C'), partners)); candidate['D'] = 'W'
        audit.yes(pair in blocking(large_a, large_h, candidate), 'stated blocking witness excludes this permutation')
    caps = {k: deferred({i: order[:k] for i, order in large_a.items()}, large_h)[0] for k in (1, 2)}
    one = {i: order[:1] for i, order in large_a.items()}; one['D'] = ('W',)
    audit.eq((caps[1]['D'], deferred(one, large_h)[0]['D']), (None, 'W'), 'sincere top-one report is not protected full truth')
    audit.eq(caps[2], matching['complete']['applicant'], 'two-name cap preserves this baseline outcome')
    audit.eq(deferred({}, {})[0], {}, 'empty market boundary')
    audit.eq(deferred({'A': ()}, {'X': ('A',)})[0], {'A': None}, 'outside outranks every falsely acceptable institution')
    audit.eq(deferred({'A': ('X',)}, {'X': ('A',)})[0], {'A': 'X'}, 'false acceptability can produce a truly worse match')

    vals = {'A': {'X': 12, 'Y': 8, 'Z': 2}, 'B': {'X': 10, 'Y': 6, 'Z': 5}, 'C': {'X': 4, 'Y': 9, 'Z': 7}}
    # Solve displayed certificate from its independent tight constraints and pZ=0.
    baseline_p = {'Z': F(0), 'X': F(vals['B']['X']-vals['B']['Z']), 'Y': F(vals['C']['Y']-vals['C']['Z'])}
    baseline_u = {'A': vals['A']['X']-baseline_p['X'], 'B': F(vals['B']['Z']), 'C': F(vals['C']['Z'])}
    bx = price_certificate(vals, baseline_u, baseline_p)
    audit.eq(bx[0], bx[3], 'assignment attains the all-partial-allocation certificate')
    audit.eq(len(bx[2]), 34, 'all partial assignments, not only bijections')
    audit.eq(tuple(sum(vals[i][j] for i, j in zip(('A', 'B', 'C'), order))
                   for order in permutations(('X', 'Y', 'Z'))),
             (25, 26, 25, 17, 21, 12), 'all six full assignment totals')
    audit.eq(tuple(baseline_u[i]+baseline_p[j]-vals[i][j] for i in ('A', 'B', 'C') for j in ('X', 'Y', 'Z')),
             (0, 1, 5, 0, 1, 0, 8, 0, 0), 'every baseline dual slack')
    changed_p = {'Z': F(0), 'Y': baseline_p['Y']}
    changed_u = {'C': F(vals['C']['Z']), 'B': vals['B']['Y']-changed_p['Y']}
    changed_p['X'] = vals['B']['X']-changed_u['B']; changed_u['A'] = vals['A']['X']-changed_p['X']
    rx = price_certificate(vals, changed_u, changed_p, (('B', 'Z'),))
    audit.eq(rx[0], rx[3], 'forbidden-edge certificate attains both complete assignments')
    audit.eq(len(rx[2]), 27, 'all allowed partial assignments after one edge removal')
    audit.eq(len(rx[1]), 2, 'complete restricted optimizer set')
    audit.yes(changed_u['B']+changed_p['Z'] < vals['B']['Z'], 'removed inequality really differs from unrestricted problem')
    cash = (20-baseline_p['X'], F(20), 20-baseline_p['Y'])
    audit.eq(sum(cash)+sum(baseline_p.values()), 60, 'owned-object cash transfers conserve the actual endowment')
    audit.eq(sum(baseline_u.values())+sum(baseline_p.values()), bx[0], 'buyer and owner increments include every transfer once')

    b = F(1, 4); equilibrium = complementary_path(b); utilities = path_payoffs(equilibrium, b)
    audit.eq(path_best(equilibrium, b), equilibrium, 'interior complementary fixed point is feasible')
    efficient = (F(3), F(4), F(3)); planner_u = path_payoffs(efficient, b)
    audit.eq(tuple(1+x for x in (b*8, b*12, b*8)), efficient, 'planner derivative uses twice the network externality')
    audit.eq((1, 1, 1, -4*b, -4*b, 0),
             (1, F(1, 4)+F(1, 4)+F(1, 2), 1, -1, -1, 0),
             'all six quadratic coefficients equal the positive sum-of-squares certificate')
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
        audit.eq(-1+(1-2*g), -2*g, 'substitute planner square identity has the correct cross coefficient')
        substitution[str(g)] = [(x, sum(substitute_payoffs(x, g))) for x in witnesses]

    rho = F(3, 5); network = {}
    for cost in (F(0), rho-rho*rho, F(1, 2), rho, F(7, 10), rho+rho*rho/2, F(1)):
        utility = {mask: graph_payoffs(mask, rho, cost)[0] for mask in range(8)}
        stable = tuple(mask for mask in range(8) if graph_incentives(mask, rho, cost)[0])
        best = max(sum(u) for u in utility.values())
        efficient_graphs = tuple(mask for mask, u in utility.items() if sum(u) == best)
        audit.eq(sum(utility[7])-sum(utility[5]), 2*(rho-rho*rho-cost), 'triangle-versus-path efficiency threshold')
        audit.eq(sum(utility[5]), 4*(rho+rho*rho/2-cost), 'path-versus-empty efficiency threshold')
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
    audit.eq(tuple(mask for mask in range(8) if graph_incentives(mask, rho, F(7, 10), True)[0]),
             (0, path_mask), 'all contract graphs and every permitted link move give the complete stable set')
    audit.yes(2*rho-2*F(7, 10) < 0, 'no balanced bilateral transfer finances a Pareto-improving first edge')
    cash_before_benefits = tuple(2-F(7, 10)*degree+t for degree, t in zip((1, 2, 1), contracted[1]))
    audit.eq(cash_before_benefits, (F(23, 20), F(9, 10), F(23, 20)), 'actual maintenance and transfer settlement precedes benefits')
    audit.eq(sum(cash_before_benefits), 6-4*F(7, 10), 'only maintenance reduces total cash')
    return {'comparisons': audit.comparisons, 'reports_checked': reports_checked,
            'matching': matching, 'recipient_manipulation': manipulated, 'caps': caps,
            'assignment': (bx[0], bx[1], baseline_p, baseline_u),
            'restricted_assignment': (rx[0], rx[1], changed_p, changed_u),
            'complements': (equilibrium, utilities, sum(utilities)),
            'planner': (efficient, planner_u, sum(planner_u)),
            'funded': (charges, receipts, transfer, balances, tuple(u+t for u, t in zip(planner_u, transfer))),
            'high_beta': high, 'substitutes': substitution, 'graphs': network,
            'contracted_path': (contracted, graph_incentives(path_mask, rho, F(7, 10), True)[1]),
            'contract_cash': cash_before_benefits}


def result_markers(result):
    small, large = (result['matching'][key] for key in ('incomplete', 'complete'))
    rho, cost = F(3, 5), F(7, 10)
    formal_beta = F(3, 4)
    denominator = 1-2*formal_beta**2
    formal = ((1+formal_beta)/denominator, (1+2*formal_beta)/denominator, (1+formal_beta)/denominator)
    contract, moves = result['contracted_path']
    return {
        'w1-stable': len(small['stable']), 'w1-ir': small['feasible_count'],
        'w1-reports': 4*len(report_family(('X', 'Y', 'Z'))),
        'w2-ir': large['feasible_count'], 'w2-reports': 4*len(report_family(('X', 'Y', 'Z', 'W'))),
        'assignment-value': result['assignment'][0], 'assignment-cash': 3*20,
        'assignment-restricted': result['restricted_assignment'][0],
        'complement-ne': result['complements'][0], 'complement-welfare': result['complements'][2],
        'planner-actions': result['planner'][0], 'planner-welfare': result['planner'][2],
        'funded-charges': result['funded'][0], 'funded-cash': result['funded'][3],
        'funded-utilities': result['funded'][4], 'beta-three-fifths': result['high_beta'],
        'beta-three-quarters-formal': formal, 'cap-two': path_best((2, 2, 2), formal_beta, cap=2),
        'substitute-small': result['substitutes']['1/2'][0][0],
        'substitute-interior-welfare': result['substitutes']['2'][0][1],
        'substitute-planner': sum(substitute_payoffs((1, 0), F(1, 2))),
        'network-baseline-welfare': sum(graph_payoffs(5, rho, F(1, 2))[0]),
        'network-changed-welfare': sum(graph_payoffs(5, rho, cost)[0]),
        'network-thresholds': (rho-rho*rho, rho, rho+rho*rho/2),
        'network-funded-payoffs': contract[0], 'network-center-margin': -moves[0][2][1],
        'network-leaf-addition': moves[1][2][0],
        'network-first-link': sum(graph_payoffs(1, rho, cost)[0]),
    }


def pairs(items):
    result = {}
    for key, value in items:
        need(key not in result, 'duplicate JSON key'); result[key] = value
    return result


def nonfinite(value):
    raise ValueError('nonfinite JSON constant '+value)


def finite_float(text):
    value = float(text); need(-float('inf') < value < float('inf'), 'finite JSON number')
    return value


def read_json(raw):
    need(type(raw) is bytes, 'JSON bytes')
    return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
                      parse_constant=nonfinite, parse_float=finite_float)


def display(value):
    if type(value) is str: return value
    if type(value) in (tuple, list): return '('+','.join(display(x) for x in value)+')'
    return str(F(value))


def compact(text):
    return re.sub(r'\s+', '', text).replace('−', '-')


class Fragment(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.ids, self.worked, self.prompts, self.answers = [], [], [], [], []
        self.sources, self.links, self.markers = {}, set(), {}
        self.tables, self.row, self.cell, self.capture = [], None, None, None
        self.exercise_depth = self.solution_depth = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs); classes = attrs.get('class', '').split()
        if 'id' in attrs: self.ids.append(attrs['id'])
        if 'worked' in classes: self.worked.append(attrs.get('id'))
        if tag == 'ol' and 'exercises' in classes: self.exercise_depth = len(self.stack)
        if tag == 'details' and 'solutions' in classes: self.solution_depth = len(self.stack)
        if tag == 'li' and self.exercise_depth is not None: self.prompts.append(attrs.get('id'))
        if 'data-solution-for' in attrs:
            need(self.solution_depth is not None, 'paired solution inside full solutions disclosure')
            self.answers.append(attrs['data-solution-for'])
        if 'href' in attrs: self.links.add(attrs['href'])
        if 'data-source' in attrs:
            key, url = attrs['data-source'], attrs.get('href')
            need(key in SOURCES and url == SOURCES[key], 'exact source identity and URL')
            self.sources[key] = url
        if 'data-calc' in attrs:
            key = attrs['data-calc']
            need(tag == 'span' and key not in self.markers and self.capture is None, 'unique result marker')
            self.markers[key] = ''; self.capture = key
        if tag == 'table': self.tables.append([])
        if tag == 'tr': self.row = []
        if tag in ('th', 'td'): self.cell = ''
        if tag not in {'br', 'hr', 'img', 'meta', 'link', 'input'}: self.stack.append(tag)

    def handle_data(self, text):
        if self.capture is not None: self.markers[self.capture] += text
        if self.cell is not None: self.cell += text

    def handle_endtag(self, tag):
        need(bool(self.stack) and self.stack[-1] == tag, 'balanced complete manuscript')
        self.stack.pop()
        if tag == 'span': self.capture = None
        if tag in ('th', 'td'):
            self.row.append(self.cell); self.cell = None
        if tag == 'tr': self.tables[-1].append(tuple(self.row)); self.row = None
        if tag == 'ol' and self.exercise_depth == len(self.stack): self.exercise_depth = None
        if tag == 'details' and self.solution_depth == len(self.stack): self.solution_depth = None


def inspect_manuscript(manuscript, audit, result):
    fragment = Fragment(); fragment.feed(manuscript); fragment.close()
    audit.yes(not fragment.stack and fragment.capture is None, 'balanced final fragment')
    audit.eq(len(fragment.ids), len(set(fragment.ids)), 'unique fragment IDs')
    audit.yes(all(name.startswith('v13-c11-') for name in fragment.ids), 'chapter ID namespace')
    audit.eq(fragment.worked, ['v13-c11-case'+str(i) for i in range(1, 7)], 'six actual shared worked tokens')
    exercises = ['v13-c11-ex'+str(i) for i in range(1, 13)]
    audit.eq(fragment.prompts, exercises, 'all twelve original exact prompts')
    audit.eq(fragment.answers, exercises, 'all twelve paired complete solutions')
    audit.eq(fragment.sources, SOURCES, 'five scoped primary routes')
    audit.eq({link for link in fragment.links if not link.startswith('https://')},
             {'v05-c11.html', 'v13-c06.html', 'v13-c10.html', 'v13-c12.html'}, 'flat prerequisite and successor links')
    expected_tables = (
        (('A', 'X, Y', 'X', 'B, A'), ('B', 'Y, X', 'Y', 'A, B'), ('C', 'Z', 'Z', 'C, D'), ('D', 'Z', '—', '—')),
        (('A', 'X, Y, Z, W', 'X', 'C, A, D, B'), ('B', 'Y, Z, X, W', 'Y', 'A, B, C, D'),
         ('C', 'Z, X, Y, W', 'Z', 'B, C, A, D'), ('D', 'X, W, Y, Z', 'W', 'D, A, B, C')),
        (('A', '12', '8', '2'), ('B', '10', '6', '5'), ('C', '4', '9', '7')))
    audit.eq(len(fragment.tables), 5, 'complete five-table inventory')
    for actual, expected in zip(fragment.tables[:3], expected_tables):
        audit.eq(tuple(tuple(compact(cell) for cell in row) for row in actual[1:]),
                 tuple(tuple(compact(cell) for cell in row) for row in expected), 'independent original primitive table')
    markers = result_markers(result)
    audit.eq(set(fragment.markers), set(markers), 'complete independent result-marker inventory')
    for key, value in markers.items():
        audit.eq(compact(fragment.markers[key]), compact(display(value)), 'independent printed result '+key)
    for phrase in ('first rejected achievable pair', 'strictly-above truncation',
                   'Once it accepts an acceptable offer', 'main-text menu proof assumes',
                   'B prefers Y to X', 'X empty, Y–B and Z–C',
                   'X ranks B above A, and Y ranks B above outside',
                   'not a voluntary Pareto improvement', 'not additional cash invoices',
                   'both would be indifferent', 'balanced transfer', 'Teach-back and delayed retention'):
        audit.yes(phrase in manuscript, 'reviewed proof or repair boundary '+phrase)
    return len(markers)


def bindings(rows):
    need(type(rows) is list, 'binding list')
    result = {}
    for row in rows:
        need(type(row) is dict and set(row) == {'path', 'bytes', 'sha256'}, 'binding fields')
        name = row['path']; need(type(name) is str and name not in result, 'unique bound path')
        need(type(row['bytes']) is int and row['bytes'] > 0, 'positive exact size')
        need(type(row['sha256']) is str and re.fullmatch('[0-9a-f]{64}', row['sha256']) is not None, 'SHA256 format')
        result[name] = row
    return result


def invalid_domains(a):
    for value in (True, False, 0.5, '1/2', None, complex(1, 0), float('nan'), float('inf'),
                  10**7, F(1, 10**10)): a.reject(q, value)
    a.reject(preferences, [], {})
    a.reject(preferences, {str(i): () for i in range(5)}, {})
    a.reject(preferences, {'A': ()}, {'A': ()})
    a.reject(preferences, {'A': ('X', 'X')}, {'X': ('A',)})
    a.reject(preferences, {'A': ('Y',)}, {'X': ('A',)})
    a.reject(preferences, {'A': ([],)}, {'X': ('A',)})
    a.reject(preferences, {1: ()}, {})
    a.reject(deferred, {}, {}, 1)
    a.reject(deferred, {}, {}, False, 'absent')
    a.reject(blocking, {'A': ('X',)}, {'X': ('A',)}, {'A': 'Y'})
    a.reject(blocking, {'A': ('X',), 'B': ('X',)}, {'X': ('A', 'B')}, {'A': 'X', 'B': 'X'})
    a.reject(menu, {'A': ()}, {}, 'B')
    a.reject(report_family, ('A', 'A'))
    a.reject(report_family, ('A', 'B', 'C', 'D', 'E'))
    a.reject(value_assignments, {})
    a.reject(value_assignments, {'A': {'X': 1}, 'B': {'Y': 1}})
    a.reject(value_assignments, {'A': {'X': -1}})
    a.reject(value_assignments, {'A': {'X': 1}}, (('A', 'Y'),))
    a.reject(price_certificate, {'A': {'X': 2}}, {'A': 0}, {'X': 1})
    a.reject(price_certificate, {'A': {'X': 2}}, {'A': -1}, {'X': 3})
    a.reject(path_payoffs, (1, 2), F(1, 4))
    a.reject(path_payoffs, (1, -1, 1), F(1, 4))
    a.reject(complementary_path, -1)
    a.reject(path_best, (1, 2, 1), F(1, 4), (0, 0, 0), 1)
    a.reject(path_best, (0, 0, 0), F(1, 4), (0, 0, 0), 0)
    a.reject(funded_effort, (4, 5, 4))
    a.reject(substitute_best, (1, 1), -1)
    for mask in (-1, 8, True): a.reject(graph_payoffs, mask, F(3, 5), F(1, 2))
    for rho in (0, 1, F(3, 2)): a.reject(graph_payoffs, 0, rho, F(1, 2))
    a.reject(graph_payoffs, 0, F(3, 5), -1)
    a.reject(graph_payoffs, 0, F(3, 5), F(1, 2), 1)
    for raw in (b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":Infinity}', b'{"x":1e9999}'):
        a.reject(read_json, raw)
    a.reject(check, True)


def check(root=None):
    need(root is None or type(root) is str or isinstance(root, Path), 'root path type')
    root = Path(root).resolve() if root is not None else Path(__file__).resolve().parent.parent
    paths = AUTHORS+(SELF, RECORD)
    raw = {name: (root/name).read_bytes() for name in paths}
    audit = Audit(); result = derive(audit)
    count = inspect_manuscript(raw[AUTHORS[0]].decode('utf-8'), audit, result)
    source, author, peer = (read_json(raw[name]) for name in (AUTHORS[2], AUTHORS[3], RECORD))
    audit.eq({row['id']: row['url'] for row in source['proposals']}, SOURCES, 'final five-source provenance record')
    for row in source['proposals']:
        audit.yes(bool(row['limits']) and row['inspection']['actual_inspector'] == 'ito_author',
                  'source scope and actual primary inspector')
    own_bindings = bindings(author['bindings']); reviewed = bindings(peer['bindings'])
    audit.eq(set(own_bindings), set(AUTHORS[:3]), 'author binds three nonself payloads')
    audit.eq(set(reviewed), set(AUTHORS+(SELF,)), 'peer binds four author files and own checker')
    for group in (own_bindings, reviewed):
        for name, row in group.items():
            audit.eq((len(raw[name]), sha256(raw[name]).hexdigest()),
                     (row['bytes'], row['sha256']), 'exact reviewed payload '+name)
    exercises = {'v13-c11-ex'+str(i) for i in range(1, 13)}
    audit.eq({row['id'] for row in author['exercise_audit']}, exercises, 'author exact twelve-exercise audit')
    audit.eq(set(peer['exercise_audit']), exercises, 'peer exact twelve-exercise audit')
    audit.eq(set(peer['proof_audit']), {'v13-c11-'+name for name in
             ('matching', 'menu-proof', 'design-constraints', 'assignment', 'network-games', 'substitutes', 'formation', 'evidence')},
             'all independent proof-domain judgments')
    audit.eq((author['open_findings'], peer['open_findings']), ([], []), 'no unresolved material finding claimed')
    audit.yes(any(row['id'] == 'removed-a-ipda-trace' for row in peer['resolved_findings']),
              'resolved explanatory finding retained honestly')
    invalid_domains(audit)
    audit.eq({name: (root/name).read_bytes() for name in paths}, raw, 'six runtime payloads unchanged')
    summary = {'chapter': 'v13-c11', 'status': 'passed', 'comparisons': audit.comparisons,
               'domain_rejections': audit.rejections, 'unilateral_reports': result['reports_checked'],
               'worked_cases': 6, 'solved_exercises': 12, 'primitive_tables': 3, 'result_markers': count,
               'runtime_payloads': list(paths), 'writes': 0,
               'scope': 'Independent finite stable sets, partial assignments, funded actions and all graph deviations; universal proofs separately reviewed.'}
    json.dumps(summary, allow_nan=False)
    return summary


if __name__ == '__main__':
    need(len(sys.argv) == 1, 'silent CLI accepts no arguments')
    check()
