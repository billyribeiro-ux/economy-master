"""Exact auction ledgers and finite matching audits, independent of HTML.

Finite incentive enumeration illustrates but does not prove general DA
strategy-proofness. Written arguments establish the continuous bid result.
"""
from fractions import Fraction as F
from itertools import permutations, product
import json


def integral(coefficients, lo, hi):
    return sum(F(c, j+1)*(hi**(j+1)-lo**(j+1))
               for j, c in enumerate(coefficients))


def second_price(values, bids, reserve=0):
    eligible = [i for i, b in enumerate(bids) if b >= reserve]
    if not eligible:
        return None, F(0), [F(0)]*len(values)
    winner = max(eligible, key=lambda i: (bids[i], -i))
    payment = max([reserve]+[b for i, b in enumerate(bids) if i != winner])
    utilities = [F(0)]*len(values)
    utilities[winner] = values[winner]-payment
    return winner, payment, utilities


def da(proposers, receivers):
    """Lists contain acceptable partners only; dict insertion fixes queue order."""
    positions = {a: 0 for a in proposers}
    held = {}
    queue = list(proposers)
    while queue:
        a = queue.pop(0)
        if positions[a] == len(proposers[a]):
            continue
        x = proposers[a][positions[a]]
        positions[a] += 1
        if a not in receivers[x]:
            queue.append(a)
        elif x not in held:
            held[x] = a
        elif receivers[x].index(a) < receivers[x].index(held[x]):
            queue.append(held[x])
            held[x] = a
        else:
            queue.append(a)
    return {a: x for x, a in held.items()}


def blocking(proposers, receivers, allocation):
    reverse = {x: a for a, x in allocation.items()}
    def prefers(ranking, new, old):
        return new in ranking and (old not in ranking or ranking.index(new) < ranking.index(old))
    return [(a, x) for a in proposers for x in receivers
            if prefers(proposers[a], x, allocation.get(a))
            and prefers(receivers[x], a, reverse.get(x))]


def check():
    values = (96, 75, 43)
    assert second_price(values, values) == (0, 75, [21, 0, 0])
    assert second_price(values, values, 80) == (0, 80, [16, 0, 0])
    assert second_price(values, values, 100) == (None, 0, [0, 0, 0])
    assert second_price(values, (74, 75, 43))[2][0] == 0
    assert second_price(values, (110, 75, 43))[2][0] == 21
    assert second_price(values, (96, 100, 43))[2][1] == -21
    # Include ties, ineligible bids and reserve equalities for both priorities.
    for v, other, reserve, deviation, i in product(range(5), range(5), range(5), range(7), range(2)):
        vals = (v, v)
        truth = [other, other]
        truth[i] = v
        lie = list(truth)
        lie[i] = deviation
        assert second_price(vals, truth, reserve)[2][i] >= second_price(vals, lie, reserve)[2][i]

    A, n, v = F(120), 3, F(96)
    def first_utility(value, bid, upper, bidders):
        k = F(bidders-1, bidders)
        win = min(F(1), (bid/(k*upper))**(bidders-1))
        return (value-bid)*win
    assert first_utility(v, 64, A, n) == F(512, 25)
    assert first_utility(v, 60, A, n) == F(81, 4)
    assert first_utility(v, 80, A, n) == 16
    assert 64*F(16, 25) == F(1024, 25)
    assert 60*F(9, 16) == F(135, 4)
    for value, imitation in product((F(0), F(1, 3), F(60), F(96), A),
                                    (F(0), F(1, 7), F(30), F(60), F(96), A)):
        best = value**3/(3*A*A)
        candidate = (value-F(2, 3)*imitation)*(imitation/A)**2
        certificate = (imitation-value)**2*(2*imitation+value)/(3*A*A)
        assert best-candidate == certificate >= 0
    for bidders, upper in ((2, F(90)), (3, A), (4, F(100))):
        k = F(bidders-1, bidders)
        max_coeff = [F(0)]*bidders+[F(bidders)/upper**bidders]
        total_value = integral(max_coeff, 0, upper)
        revenue = k*total_value
        utility_coeff = [F(0)]*bidders+[F(1)/(bidders*upper**bidders)]
        individual_surplus = integral(utility_coeff, 0, upper)
        assert revenue+bidders*individual_surplus == total_value
        assert total_value == F(bidders, bidders+1)*upper
        assert revenue == F(bidders-1, bidders+1)*upper
        for value in (F(0), upper/10, upper*F(4, 5), upper):
            best = first_utility(value, k*value, upper, bidders)
            for bid in (F(0), upper/10, upper/2, k*upper, upper, 2*upper):
                assert best >= first_utility(value, bid, upper, bidders)
    second_coeff = [0, 0, F(6, A*A), F(-6, A**3)]
    assert integral(second_coeff, 0, A) == 60
    assert integral([0, 0, 0, F(3, A**3)], 0, A) == 90
    assert first_utility(F(80), 60, F(100), 4) == F(256, 25)
    assert 60*F(64, 125) == F(768, 25)
    assert first_utility(F(60), 30, F(90), 2) == 20
    # Reserve revenue from a direct integral over the ordered pair, not RET.
    r = F(60)
    exactly_one = 2*(r/A)*(1-r/A)
    both = (1-r/A)**2
    min_conditional = r+integral([F(A*A, (A-r)**2), F(-2*A, (A-r)**2), F(1, (A-r)**2)], r, A)
    reserve_revenue = exactly_one*r+both*min_conditional
    reserve_value = integral([0, 0, F(2, A*A)], r, A)
    assert (exactly_one, both, min_conditional) == (F(1, 2), F(1, 4), 80)
    assert (reserve_revenue, reserve_value, reserve_value-reserve_revenue) == (50, 70, 20)
    assert integral([1, F(-2, A), F(1, A*A)], 0, A) == 40
    high_joint, low_joint = F(1, 2)*F(3, 4), F(1, 2)*F(1, 4)
    assert high_joint/(high_joint+low_joint) == F(3, 4)
    high_hl, low_hl = high_joint*F(1, 4), low_joint*F(3, 4)
    assert 100*high_hl/(high_hl+low_hl)-70 == -20
    assert (60+3*2, 90-60-3*2, -2) == (66, 24, -2)

    applicants = {'A': 'XYZ', 'B': 'YXZ', 'C': 'XZY'}
    institutions = {'X': 'BAC', 'Y': 'ABC', 'Z': 'CAB'}
    app_result = da(applicants, institutions)
    inst_result = {a: x for x, a in da(institutions, applicants).items()}
    assert app_result == dict(zip('ABC', 'XYZ'))
    assert inst_result == dict(zip('ABC', 'YXZ'))
    stable = [dict(zip('ABC', p)) for p in permutations('XYZ')
              if not blocking(applicants, institutions, dict(zip('ABC', p)))]
    assert len(stable) == 2 and app_result in stable and inst_result in stable
    false_institutions = dict(institutions, X='BCA')
    manipulated = da(applicants, false_institutions)
    assert manipulated == inst_result
    assert institutions['X'].index('B') < institutions['X'].index('A')
    for a in applicants:
        for lie in permutations('XYZ'):
            result = da(dict(applicants, **{a: lie}), institutions)
            assert applicants[a].index(app_result[a]) <= applicants[a].index(result[a])
    serial = {}
    available = set('XYZ')
    for a in 'CAB':
        serial[a] = next(x for x in applicants[a] if x in available)
        available.remove(serial[a])
    assert serial == {'C': 'X', 'A': 'Y', 'B': 'Z'}
    assert blocking(applicants, institutions, serial) == [('A', 'X'), ('B', 'X')]
    for p in permutations('XYZ'):
        alternative = dict(zip('ABC', p))
        if all(applicants[a].index(alternative[a]) <= applicants[a].index(serial[a]) for a in applicants):
            assert alternative == serial
    # Exhaust all two-by-two profiles, including unacceptable partners, and
    # every unilateral report on that same finite domain.
    app_lists = [()] + [p for k in (1, 2) for p in permutations('XY', k)]
    inst_lists = [()] + [p for k in (1, 2) for p in permutations('AB', k)]
    profiles = 0
    for la, lb, lx, ly in product(app_lists, app_lists, inst_lists, inst_lists):
        ap, ins = {'A': la, 'B': lb}, {'X': lx, 'Y': ly}
        out = da(ap, ins)
        assert not blocking(ap, ins, out)
        assert all(x in ap[a] and a in ins[x] for a, x in out.items())
        for a in ap:
            def rank(partner):
                return ap[a].index(partner) if partner in ap[a] else len(ap[a])
            for lie in app_lists:
                deviation = da(dict(ap, **{a: lie}), ins)
                assert rank(out.get(a)) <= rank(deviation.get(a))
        profiles += 1
    assert profiles == 625
    assert da({'A': 'XY', 'B': 'XY'}, {'X': 'BA', 'Y': 'AB'}) == {'B': 'X', 'A': 'Y'}
    return {
        'status': 'passed',
        'checks': ['Second-price deviations, reserves and both tie priorities',
                   'First-price global gap certificate, endpoint deviations and exact order-statistic integrals',
                   'Reserve and compulsory-fee surplus ledgers; common-value Bayes posterior',
                   'Both DA directions, all six complete matchings and receiver manipulation',
                   'Serial allocation, all blocking pairs and one-sided Pareto comparison',
                   '625 complete/incomplete two-by-two profiles and all unilateral proposer reports',
                   'All eight exercise targets and delayed transfer'],
        'limitations': ['Finite matching enumeration is not a general theorem proof.',
                        'No empirical validation, general DA truthfulness proof or UI QA.']}


if __name__ == '__main__':
    print(json.dumps(check(), indent=2))
