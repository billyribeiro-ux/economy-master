"""Original Volume 5 support arithmetic, exact transfer audits and assembly."""
from fractions import Fraction as F
from itertools import combinations, product
import json
from pathlib import Path
import re

from check_v04_assessment import Sections

ROOT = Path(__file__).resolve().parents[1]
PARTS = ROOT / 'content/assessment-parts'


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def lottery_distribution(outcomes, treated_count):
    result = {}
    for treated in combinations(range(len(outcomes)), treated_count):
        a = sum(outcomes[i] for i in treated)
        b = sum(outcomes)-a
        contrast = F(a, treated_count)-F(b, len(outcomes)-treated_count)
        result[contrast] = result.get(contrast, 0)+1
    return result


def contract_vertices(probabilities, costs, outside, action):
    """Enumerate intersections of all half-planes in (failure, success) wages."""
    p, c = probabilities[action], costs[action]
    constraints = [(F(-1), F(0), F(0)), (F(0), F(-1), F(0)),
                   (-(1-p), -p, -outside-c)]
    for j, pj in enumerate(probabilities):
        if j != action:
            constraints.append((p-pj, pj-p, costs[j]-c))
    candidates = []
    for (a, b, rhs), (d, e, other) in combinations(constraints, 2):
        determinant = a*e-b*d
        if not determinant:
            continue
        w0, w1 = (rhs*e-b*other)/determinant, (a*other-rhs*d)/determinant
        if all(x*w0+y*w1 <= z for x, y, z in constraints):
            candidates.append(((1-p)*w0+p*w1, w0, w1))
    require(bool(candidates), 'contract feasible vertex missing')
    return min(candidates)


def support_check():
    checks = []
    require(F(10-8, 8) == F(1, 4) and F(50-40, 40) == F(1, 4)
            and F(50-40, 100) == F(1, 10), 'diagnostic rates')
    for k in range(301):
        q = F(k, 100)
        require(21-(10*q-q*q) == (3-q)*(7-q) >= 0,
                'bounded quadratic global certificate')
    require(F(6+2)*2/2 == 6*2-2**2 == 8, 'integral/trapezoid units')
    require(4+2*3 == 10 and 3*4+3 == 15 and 4 > 3, 'linear feasible set')
    states = {(1, 1): F(1, 4), (1, 0): F(1, 12),
              (0, 1): F(1, 6), (0, 0): F(1, 2)}
    positive = sum(v for (_, signal), v in states.items() if signal)
    require(sum(states.values()) == 1 and positive == F(5, 12)
            and states[1, 1]/positive == F(3, 5), 'Bayes joint-state reconstruction')
    require(F(1, 4)*8 == 2 < 3 and F(121)/F(11, 10)**2 == 100
            and F(12)/F(11, 10) == F(120, 11) > 10,
            'expected monetary losses and dated discounting')
    diagnostic_law = lottery_distribution((1, 1, 0, 0), 2)
    require(diagnostic_law == {F(1): 1, F(0): 4, F(-1): 1},
            'diagnostic assignment enumeration')
    require(F(sum(n for t, n in diagnostic_law.items() if abs(t) >= 1), 6)
            == F(1, 3), 'diagnostic absolute-tail probability')
    checks.append('All eight diagnostic results; independent joint-state, assignment and quadratic-factor checks')

    # Leontief dual certificates: every feasible utility-u bundle must have x>=u,y>=u/2.
    for px, u, expected in ((1, F(9), F(18)), (2, F(6), F(18)),
                            (2, F(9), F(27)), (1, F(6), F(12))):
        expenditure = px*u+2*(u/2)
        require(expenditure == expected, 'complementary expenditure target')
        for dx, dy in product((F(0), F(1, 4), F(2)), repeat=2):
            x, y = u+dx, u/2+dy
            require(min(x, 2*y) >= u and px*x+2*y-expenditure == px*dx+2*dy >= 0,
                    'global expenditure bound and attaining bundle')
    require(27-18 == 9 and 18-12 == 6, 'CV/EV utility targets')
    checks.append('Complementary Marshallian bundles and expenditure certificates at both welfare targets')

    # Integrate primitive benefit/cost/damage rather than summing the supplied surplus answers.
    def resource_welfare(q):
        return 40*q-q*q/2-(4*q+q*q/2)-2*q
    for q, expected in ((F(18), 288), (F(15), 285), (F(17), 289)):
        require(resource_welfare(q) == expected, 'resource welfare integral')
    q = F(15); buyer, seller = 40-q, 4+q
    cs, ps, receipts, damage = (40-buyer)*q/2, (seller-4)*q/2, (buyer-seller)*q, 2*q
    require((cs, ps, receipts, damage) == (F(225, 2), F(225, 2), 90, 30)
            and cs+ps+receipts-damage == resource_welfare(q), 'tax incidence ledger')
    for k in range(161):
        x = F(k, 4)
        require(289-resource_welfare(x) == (x-17)**2, 'global social output certificate')
    checks.append('Tax prices/surpluses independently reconciled to primitive resource integrals and global efficient-output certificate')

    deviation_checks = 0
    for costs, quantities, target_profits in (((8, 20), (16, 4), (256, 16)),
                                              ((8, 28), (18, 0), (324, 0))):
        for i in range(2):
            qi, rival, cost = F(quantities[i]), F(quantities[1-i]), F(costs[i])
            optimum = max(F(44-cost-rival, 2), F(0))
            require(qi == optimum, 'Cournot active best response')
            profit = lambda x: (max(44-x-rival, 0)-cost)*x
            require(profit(qi) == target_profits[i], 'Cournot profit')
            for k in range(321):
                x = F(k, 4)
                require(profit(qi) >= profit(x), 'finite Cournot deviation countercheck')
                if 44-x-rival >= 0:
                    require(profit(qi)-profit(x) == (qi-x)*(44-cost-rival-qi-x),
                            'positive-price quadratic gap')
                else:
                    require(profit(x) <= 0 <= profit(qi), 'zero-price global branch')
                deviation_checks += 1
    require(F(44-56+8, 3) == F(-4, 3), 'rejected interior rival')
    checks.append(f'Cournot active/inactive solutions and {deviation_checks} deviation counterchecks, with branch-specific gap identities')

    probs, costs = (F(2, 5), F(7, 10), F(4, 5)), (F(0), F(2), F(6))
    require(tuple(p*20-c for p, c in zip(probs, costs)) == (8, 12, 10),
            'omitted action is profitable')
    minima = [contract_vertices(probs, costs, F(1), i) for i in range(3)]
    require([v[0] for v in minima] == [F(1), F(14, 3), F(32)],
            'all action contract LP minima')
    profits = [60*p-v[0] for p, v in zip(probs, minima)]
    require(profits == [F(23), F(112, 3), F(16)] and profits.index(max(profits)) == 1,
            'global principal action comparison')
    for i, (_, w0, w1) in enumerate(minima):
        utilities = [(1-p)*w0+p*w1-c for p, c in zip(probs, costs)]
        require(utilities[i] >= 1 and utilities[i] == max(utilities),
                'every vertex contract all-action participation audit')
    checks.append('Independent half-plane vertex enumeration for all three action contracts and principal comparison')

    auction_cases = 0
    for value, opponent_max, bid in product(range(41), range(41), range(41)):
        threshold = max(25, opponent_max)
        for wins_tie in (False, True):
            def payoff(b):
                wins = b >= 25 and (b > opponent_max or (b == opponent_max and wins_tie))
                return value-threshold if wins else 0
            require(payoff(value) >= payoff(bid), 'reserve-auction truthful deviation check')
            auction_cases += 1
    require(30-max(25, 20) == 5, 'reserve auction outcome')
    applicant = {'A': ['X', 'Y'], 'B': ['X', 'Y']}
    institution = {'X': ['B', 'A'], 'Y': ['A', 'B']}
    assigned = {'A': 'Y', 'B': 'X'}
    holder = {school: student for student, school in assigned.items()}
    for a, s in product(applicant, institution):
        if assigned[a] != s:
            blocks = applicant[a].index(s) < applicant[a].index(assigned[a]) and institution[s].index(a) < institution[s].index(holder[s])
            require(not blocks, 'matching unmatched-pair audit')
    checks.append(f'Reserve-auction {auction_cases} finite deviation/tie checks and exhaustive unmatched-pair stability audit')

    law = lottery_distribution((1, 1, 0, 0, 0), 2)
    require(law == {F(-2, 3): 3, F(1, 6): 6, F(1): 1}
            and F(sum(n for t, n in law.items() if abs(t) >= 1), sum(law.values())) == F(1, 10),
            'five-person exact randomization law')
    ates = []
    for missing in product((0, 1), repeat=5):
        y1 = (1, 1)+missing[2:]
        y0 = missing[:2]+(0, 0, 0)
        ates.append(F(sum(y1)-sum(y0), 5))
    require(min(ates) == 0 and max(ates) == 1 and len(ates) == 32,
            'all compatible missing-outcome schedules and sharp logical ATE bounds')
    checks.append('All ten treatment assignments and32 compatible binary potential-outcome schedules; sharp-null tail separated from logical ATE bounds')

    support = (PARTS/'v05-support.html').read_text()
    parsed = Sections(); parsed.feed(support)
    require(parsed.h1 == 1 and len(parsed.ids) == len(set(parsed.ids)), 'support title/anchors')
    for section, count in (('diagnostic', 8), ('retention', 6), ('oral-transfer', 3)):
        require(parsed.counts.get((section, False)) == count and parsed.counts.get((section, True)) == count,
                f'{section}: matched prompt and answer counts')
    require(set(f'v05-c{i:02d}.html' for i in range(1, 13)) <= set(parsed.links), 'twelve chapter routes')
    require({'diagnostic', 'exam-rules', 'oral-transfer', 'retention', 'remediation',
             'notation-index', 'concept-index', 'volume-synthesis'} <= set(parsed.ids), 'support components')
    require(all(s in support for s in ('85/100', '15/20', '180 minutes', '51/60', '7.5/10')),
            'stated criterion scores')
    checks.append('Eight diagnostic, six retention and three oral prompt/answer groups; rubric, remediation and all12 chapter routes')
    return {'status': 'passed', 'checks': checks}


def assemble():
    return (PARTS/'v05-support.html').read_text().replace(
        '<!-- ASSESSMENT_FORMS -->', (PARTS/'v05-form-a.html').read_text()+'\n'+(PARTS/'v05-form-b.html').read_text()).replace(
        '<!-- INTEGRATIVE_PROJECT -->', (PARTS/'v05-project.html').read_text())


def check():
    from check_v05_exam_a import check as exam_a
    from check_v05_exam_b import check as exam_b
    from check_v05_project import check as project
    support = support_check()
    manuscript = (ROOT/'content/assessments/v05.html').read_text()
    require(manuscript == assemble(), 'canonical package equals all owned fragments')
    parsed = Sections(); parsed.feed(manuscript)
    require(parsed.h1 == 1 and len(parsed.ids) == len(set(parsed.ids)), 'canonical title/unique anchors')
    require({'form-a', 'form-b', 'project'} <= set(parsed.ids), 'all assessment fragments present')
    for form in ('form-a', 'form-b'):
        require(parsed.counts.get((form, False)) == 5 and parsed.counts.get((form, True)) == 5,
                f'{form}: five domain question/answer groups')
    require('<!-- ASSESSMENT_' not in manuscript and '<!-- INTEGRATIVE_' not in manuscript,
            'no unfilled assembly markers')
    sources = {s['id'] for s in json.loads((ROOT/'content/sources.json').read_text())}
    require(set(re.findall(r'data-source="([^"]+)"', manuscript)) <= sources, 'registered assessment sources')
    return {'status': 'passed', 'support': support, 'form_a': exam_a(), 'form_b': exam_b(), 'project': project(),
            'limitations': ['Numerical checks supplement the separate full written review, not replace it.',
                            'Finite checks do not prove general theorems or externally assess learner competence; visual/mobile/print QA remains separate.']}


if __name__ == '__main__':
    import sys
    print(json.dumps(support_check() if '--support-only' in sys.argv else check(), indent=2))
