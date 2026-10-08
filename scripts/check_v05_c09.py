"""Exact independent finite-model checks for Contracts and organizations.

Uses constraint-intersection enumeration rather than the manuscript's formula
to solve wage linear programs. Grids supplement algebraic certificates, never
substitute for the separate manuscript/proof review. Standard library only.
"""
from fractions import Fraction as F
from html.parser import HTMLParser
from itertools import combinations, product
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[1]
CHAPTER = ROOT / 'content/chapters/v05-c09.html'
SOURCES = ROOT / 'content/reviews/v05-c09-sources.json'


def require(condition, message):
    if not condition:
        raise ValueError(message)


class Structure(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.lists, self.ids, self.sources, self.links = [], [], [], [], []
        self.worked = self.exercises = self.solutions = self.blocks = self.h1 = 0
        self.in_solutions = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag not in ('br', 'hr', 'img', 'input', 'meta', 'link'):
            self.stack.append(tag)
        self.h1 += tag == 'h1'
        if 'id' in attrs:
            self.ids.append(attrs['id'])
        if 'data-source' in attrs:
            self.sources.append(attrs['data-source'])
        if tag == 'a':
            self.links.append(attrs.get('href', ''))
        self.worked += tag == 'aside' and attrs.get('class') == 'worked'
        if tag == 'details' and attrs.get('class') == 'solutions':
            self.in_solutions = True
            self.blocks += 1
        if tag == 'ol':
            self.lists.append(attrs.get('class'))
        if tag == 'li' and self.lists:
            self.exercises += self.lists[-1] == 'exercises'
            self.solutions += self.in_solutions

    def handle_endtag(self, tag):
        require(bool(self.stack) and self.stack.pop() == tag, 'HTML balance: ' + tag)
        if tag == 'ol':
            self.lists.pop()
        if tag == 'details':
            self.in_solutions = False


def dot(a, b):
    require(len(a) == len(b), 'dot dimensions')
    return sum((x*y for x, y in zip(a, b)), F(0))


def solve(matrix, rhs):
    """Small exact Gaussian elimination; singular systems return None."""
    n = len(rhs)
    require(len(matrix) == n and all(len(row) == n for row in matrix), 'square system')
    rows = [[F(v) for v in row] + [F(b)] for row, b in zip(matrix, rhs)]
    for col in range(n):
        pivot = next((r for r in range(col, n) if rows[r][col]), None)
        if pivot is None:
            return None
        rows[col], rows[pivot] = rows[pivot], rows[col]
        divisor = rows[col][col]
        rows[col] = [v/divisor for v in rows[col]]
        for r in range(n):
            if r != col:
                scale = rows[r][col]
                rows[r] = [x-scale*y for x, y in zip(rows[r], rows[col])]
    return tuple(row[-1] for row in rows)


def wage_lp(distributions, costs, target, outside, cap=None):
    """Minimize target expected wage subject to IR/all IC and 0<=w<=cap.

    Nonnegative orthant constraints make this polyhedron pointed. In these
    finite feasible cases a bounded-below linear objective attains at a vertex.
    The analytic lower-bound proofs remain in the manuscript.
    """
    n = len(distributions[target])
    require(all(len(p) == n and sum(p) == 1 and all(x >= 0 for x in p)
                for p in distributions), 'probability vectors')
    constraints = []
    for j in range(n):
        row = tuple(F(int(k == j)) for k in range(n))
        constraints.append((row, F(0)))
        if cap is not None:
            constraints.append((tuple(-x for x in row), -F(cap)))
    constraints.append((distributions[target], F(outside)+costs[target]))
    for other in range(len(costs)):
        if other != target:
            row = tuple(x-y for x, y in zip(distributions[target], distributions[other]))
            constraints.append((row, costs[target]-costs[other]))
    vertices = set()
    for active in combinations(constraints, n):
        wage = solve([row for row, _ in active], [b for _, b in active])
        if wage is not None and all(dot(row, wage) >= b for row, b in constraints):
            vertices.add(wage)
    if not vertices:
        return None, []
    value = min(dot(distributions[target], w) for w in vertices)
    return value, sorted(w for w in vertices if dot(distributions[target], w) == value)


def utility(probabilities, wages, costs):
    return tuple(dot(p, wages)-c for p, c in zip(probabilities, costs))


def owner_payoffs(mode, investments, cost_a=F(9)):
    a, b = investments
    value = F(20+16*a+10*b)
    if mode == 'separate':
        outside = F(0), F(0)
    elif mode == 'a_owns':
        outside = F(10*a+6*b), F(0)
    elif mode == 'b_owns':
        outside = F(0), F(8*a+6*b)
    else:
        raise ValueError('unknown ownership')
    require(value > sum(outside), 'positive bargaining gains in every state')
    split = (value-sum(outside))/2
    payoff = outside[0]+split-cost_a*a, outside[1]+split-4*b
    require(sum(payoff) == value-cost_a*a-4*b, 'investment/resource accounting')
    return payoff


def check():
    checks, results = [], {}
    html = CHAPTER.read_text(encoding='utf-8')
    parser = Structure()
    parser.feed(html)
    require(not parser.stack and not parser.lists and parser.h1 == 0, 'HTML fragment')
    require(parser.worked == 4 and parser.exercises == parser.solutions == 8
            and parser.blocks == 1, 'worked/exercise/solution counts')
    require(len(parser.ids) == len(set(parser.ids))
            and all(x.startswith('v05-c09-') for x in parser.ids), 'unique namespaced anchors')
    require('Teach-back' in html and 'Delayed check answer' in html, 'teaching and retention')
    require({'v05-c08.html', 'v05-c10.html'} <= set(parser.links), 'adjacent chapter routes')
    records = json.loads(SOURCES.read_text(encoding='utf-8'))
    keys = {'id', 'title', 'url', 'use', 'checked', 'verification'}
    require(len(records) == 2 and all(set(r) == keys for r in records), 'source schema')
    ids = [r['id'] for r in records]
    require(len(set(ids)) == len(ids) and all(x.startswith('v05-c09-') for x in ids), 'source IDs')
    require(set(parser.sources) == set(ids), 'aligned source proposals')
    require(all(r['url'] in parser.links and r['verification'] and r['checked'] == '2026-10-08'
                for r in records), 'inspected source routes/dates')
    plain = re.sub(r'<[^>]+>', ' ', html)
    results['structure'] = {'words': len(plain.split()), 'worked': parser.worked,
                            'exercise_solution_pairs': 8, 'source_proposals': len(records)}
    checks.append('balanced manuscript, four worked cases, eight matched answers, source alignment')

    probs = [(F(3, 4), F(1, 4)), (F(1, 4), F(3, 4))]
    costs = (F(0), F(12))
    revenue = (F(20), F(100))
    require([dot(p, revenue) for p in probs] == [40, 80], 'expected revenue')
    require(wage_lp(probs, costs, 1, 4) == (F(18), [(F(0), F(24))]), 'main wage optimum')
    require(wage_lp(probs, costs, 0, 4)[0] == 4, 'low effort wage bound')
    require(utility(probs, (F(0), F(24)), costs) == (6, 6), 'main effort tie')
    require(utility(probs, (F(-2), F(22)), costs) == (4, 4), 'excluded negative wage')
    require(80-18 == 62 and 40-4 == 36 and 80-16 == 64, 'main profit alternatives')
    require(62+6 == 64+4 == 80-12 == 68, 'main transfer accounting')
    outside_cost, vertices = wage_lp(probs, costs, 1, 10)
    require(outside_cost == 22 and (F(4), F(28)) in vertices
            and (F(0), F(88, 3)) in vertices, 'two different higher-reservation optima')
    require(utility(probs, (F(0), F(88, 3)), costs) == (F(22, 3), F(10)), 'strict alternative')
    for epsilon in (F(1, 100), F(1, 3), F(2)):
        wages = F(0), F(24)+epsilon
        utilities = utility(probs, wages, costs)
        require(utilities[1]-utilities[0] == epsilon/2 > 0, 'strict effort perturbation')
        require(80-dot(probs[1], wages) == 62-F(3, 4)*epsilon, 'strict profit loss')
    require(wage_lp(probs, costs, 1, 4, 20) == (None, []), 'cap infeasibility')
    require(wage_lp(probs, costs, 1, 4, 24) == (F(18), [(F(0), F(24))]), 'cap weak boundary')
    require(wage_lp([probs[0], probs[0]], costs, 1, 4) == (None, []), 'uninformative effort')
    family = 0
    for pl, ph, c, outside in product((F(1, 5), F(1, 4), F(1, 3)),
                                     (F(1, 2), F(3, 4), F(4, 5)),
                                     (F(3), F(6), F(12)), (F(0), F(4), F(10))):
        ps = [(1-pl, pl), (1-ph, ph)]
        value, ws = wage_lp(ps, (F(0), c), 1, outside)
        predicted = max(outside+c, ph*c/(ph-pl))
        require(value == predicted and ws, 'independent wage LP across branches')
        require(value-c-outside == max(F(0), pl*c/(ph-pl)-outside), 'rent identity')
        require(wage_lp(ps, (F(0), c), 0, outside)[0] == outside, 'low effort family')
        family += 1
    results['risk_neutral'] = {'main_wages': ['0', '24'], 'main_profit': '62',
                               'outside_10_optimal_vertices': [[str(x) for x in w] for w in vertices],
                               'parameter_cases': family, 'cap_20': 'infeasible', 'cap_24': 'weak only'}
    checks.append('exact LP vertices, IR/IC/floors/caps, alternate optima, strict ties and 81 parameter cases')

    risk_cases = []
    risk_comparisons = 0
    for outside, roots, target in ((F(3), (F(5, 2), F(9, 2)), F(67, 4)),
                                    (F(2), (F(3, 2), F(7, 2)), F(39, 4))):
        mu = dot(probs[1], roots)
        wages = tuple(v*v for v in roots)
        require(dot(probs[1], wages) == target, 'risk wage total')
        require(utility(probs, roots, (F(0), F(1))) == (outside, outside), 'risk IC/IR')
        require(target-mu*mu == F(3, 4), 'risk premium')
        for vf, vs in product((F(i, 4) for i in range(41)), repeat=2):
            mean = F(1, 4)*vf+F(3, 4)*vs
            money = F(1, 4)*vf*vf+F(3, 4)*vs*vs
            require(money == mean*mean+F(3, 16)*(vs-vf)**2, 'global square identity')
            if F(1, 2)*(vs-vf) >= 1 and mean-1 >= outside:
                require(money >= target, 'risk feasible alternative bound')
                risk_comparisons += 1
        risk_cases.append({'outside_utility': str(outside), 'wages': [str(x) for x in wages],
                           'expected_wage': str(target), 'certainty_equivalent': str(mu*mu),
                           'risk_premium_dollars': '3/4', 'utility_rent': '0', 'profit': str(80-target)})
    results['risk_aversion'] = {'cases': risk_cases, 'feasible_grid_comparisons': risk_comparisons}
    checks.append('square-root global square certificate, feasible alternatives and distinct risk/rent units')

    # States: failure/fail, failure/pass, success/fail, success/pass.
    audit_probs = [(F(9, 16), F(3, 16), F(3, 16), F(1, 16)),
                   (F(0), F(1, 4), F(0), F(3, 4))]
    report_wages = F(0), F(16), F(0), F(16)
    joint_wages = F(0), F(0), F(0), F(64, 3)
    require(wage_lp(audit_probs, costs, 1, 4)[0] == 16, 'all joint audit wage contracts')
    require(utility(audit_probs, report_wages, costs) == (4, 4), 'audit report-only tie')
    require(utility(audit_probs, joint_wages, costs) == (F(4, 3), F(4)), 'audit joint strict effort')
    require(dot(audit_probs[1], joint_wages) == 16, 'audit strict action at cost bound')
    choices = [max(F(62), F(64)-k) for k in (1, 2, 3)]
    require(choices == [63, 62, 62], 'audit choice costs')
    require([64-k+4 for k in (1, 2, 3)] == [67, 66, 65], 'audit resource totals')
    z_probability = F(1, 3), F(2, 5)
    noise_wages = ((F(0), F(15)), (F(12), F(30)))
    means = tuple((1-z)*w[0]+z*w[1] for z, w in zip(z_probability, noise_wages))
    for p in probs:
        joint_cost = sum((p[r]*((1-z_probability[r])*noise_wages[r][0]
                              + z_probability[r]*noise_wages[r][1]) for r in range(2)), F(0))
        require(joint_cost == dot(p, means), 'conditional redundant report averaging')
    results['monitoring'] = {'joint_LP_minimum_wage': '16', 'best_profits_k_1_2_3': list(map(str, choices)),
                             'strict_joint_utilities_L_H': ['4/3', '4'],
                             'redundant_report_conditional_wages': list(map(str, means))}
    checks.append('four-state audit LP, strict joint incentives, private/resource costs and redundant report identity')

    task_records = []
    task_comparisons = 0
    for quality_value, max_profit, opt_bonus in ((F(4), F(11), F(4)), (F(10), F(25), F(0))):
        best = None
        snapshots = []
        for numerator in range(49):
            bonus = F(numerator, 4)
            m = min(F(6), 3+bonus/2)
            h = 6-m
            cost = (m*m+h*h)/2
            base = max(F(0), 20+cost-bonus*(m+1))
            wages = base+bonus*m, base+bonus*(m+2)
            expected_wage = sum(wages)/2
            agent_value = expected_wage-cost
            require(min(wages) >= 0 and agent_value >= 20, 'task LL/IR')
            for j in range(49):
                other = F(j, 8)
                other_cost = (other**2+(6-other)**2)/2
                other_value = base+bonus*(other+1)-other_cost
                gap = (m-other)**2 if bonus <= 6 else (bonus-6)*(6-other)+(6-other)**2
                require(agent_value-other_value == gap >= 0, 'global task effort certificate')
                task_comparisons += 1
            value = 8*m+quality_value*h
            profit = value-expected_wage
            bound = value-20-cost
            target_bound = 11-(m-5)**2 if quality_value == 4 else 26-(m-2)**2
            require(profit <= bound == target_bound <= max_profit, 'global task profit bound')
            if best is None or profit > best[0]:
                best = profit, bonus
            if bonus in (0, 4, 6):
                snapshots.append({'b': str(bonus), 'a': str(base), 'm': str(m), 'h': str(h),
                                  'cost': str(cost), 'mean_proxy': str(m+1),
                                  'wages': list(map(str, wages)), 'profit': str(profit)})
        require(best == (max_profit, opt_bonus), 'task best bonus attained')
        task_records.append({'maintenance_value': str(quality_value), 'snapshots': snapshots})
    require([s['profit'] for s in task_records[0]['snapshots']] == ['7', '11', '6'], 'main task table')
    require([s['profit'] for s in task_records[1]['snapshots']] == ['25', '17', '6'], 'exercise task table')
    results['multitask'] = {'cases': task_records, 'exact_effort_comparisons': task_comparisons}
    checks.append('global task response/participation certificates, noise wages, bonus corner and changed objective')

    ownership = []
    expected = {
        9: [('separate', (0, 1), (15, 11)), ('a_owns', (1, 0), (14, 13)), ('b_owns', (0, 1), (12, 14))],
        7: [('separate', (1, 1), (16, 19)), ('a_owns', (1, 0), (16, 13)), ('b_owns', (0, 1), (12, 14))]
    }
    for cost_a, scenarios in expected.items():
        for mode, expected_actions, expected_payoff in scenarios:
            matrix = {actions: owner_payoffs(mode, actions, F(cost_a)) for actions in product((0, 1), repeat=2)}
            equilibria = []
            for actions, payoff in matrix.items():
                deviations = [matrix[(1-actions[0], actions[1])][0],
                              matrix[(actions[0], 1-actions[1])][1]]
                if all(payoff[j] >= deviations[j] for j in range(2)):
                    equilibria.append(actions)
                    require(all(payoff[j] > deviations[j] for j in range(2)), 'strict investment equilibrium')
            require(equilibria == [expected_actions], 'all investment equilibria enumerated')
            require(matrix[expected_actions] == expected_payoff, 'ownership payoff reference')
            ownership.append({'cost_a': cost_a, 'mode': mode, 'investment': list(expected_actions),
                              'payoff': list(map(str, matrix[expected_actions])),
                              'total': str(sum(matrix[expected_actions]))})
        first_best = max((F(20+16*a+10*b)-cost_a*a-4*b, (a, b)) for a, b in product((0, 1), repeat=2))
        require(first_best == ((F(33) if cost_a == 9 else F(35)), (1, 1)), 'first-best investments')
    compensation_tests = 0
    for setup, transfer in product((F(i, 4) for i in range(13)), (F(i, 4) for i in range(17))):
        new_payoff = 14-setup+transfer, 13-transfer
        weak = new_payoff[0] >= 15 and new_payoff[1] >= 11
        strict = new_payoff[0] > 15 and new_payoff[1] > 11
        require(weak == (setup <= 1 and 1+setup <= transfer <= 2), 'weak compensation region')
        require(strict == (setup < 1 and 1+setup < transfer < 2), 'strict compensation region')
        require(sum(new_payoff) == 27-setup, 'setup versus transfer accounting')
        compensation_tests += 1
    require((14-F(1, 2)+F(7, 4), 13-F(7, 4)) == (F(61, 4), F(45, 4)), 'setup exercise point')
    results['ownership'] = {'equilibria': ownership, 'compensation_pairs': compensation_tests}
    checks.append('all investment states/deviations in six ownership economies, first best and compensation region')

    three_probs = [probs[0], (F(1, 2), F(1, 2)), probs[1]]
    three_costs = F(0), F(3), F(12)
    require(utility(three_probs, (F(0), F(24)), three_costs) == (6, 9, 6), 'omitted profitable action')
    require(wage_lp(three_probs, three_costs, 2, 4) == (F(27), [(F(0), F(36))]), 'three-action H LP')
    m_value, m_vertices = wage_lp(three_probs, three_costs, 1, 4)
    require(m_value == 7 and (F(1), F(13)) in m_vertices, 'three-action M LP')
    require(utility(three_probs, (F(1), F(13)), three_costs) == (4, 4, -2), 'M all deviations')
    require(utility(three_probs, (F(0), F(36)), three_costs) == (9, 15, 15), 'H all deviations')
    require(wage_lp(three_probs, three_costs, 0, 4)[0] == 4, 'three-action low implementation')
    require([dot(p, revenue)-c for p, c in zip(three_probs, (F(4), F(7), F(27)))] == [36, 53, 53], 'global action choice')
    delayed_probs = [(F(4, 5), F(1, 5)), (F(1, 5), F(4, 5))]
    require(wage_lp(delayed_probs, (F(0), F(6)), 1, 1) == (F(8), [(F(0), F(10))]), 'delayed contract')
    require(utility(delayed_probs, (F(0), F(10)), (F(0), F(6))) == (2, 2), 'delayed tie/rent')
    require([dot(p, (F(10), F(50)))-c for p, c in zip(delayed_probs, (F(1), F(8)))] == [17, 34], 'delayed action choice')
    results['additional_actions_and_retention'] = {'H_wages': ['0', '36'], 'M_wages': ['1', '13'],
                                                  'H_and_M_profit': '53', 'delayed_H_profit': '34'}
    checks.append('new third action, all IC/IR constraints, target/action global comparisons and delayed answer')
    report = {'chapter': 'v05-c09', 'status': 'passed', 'checks': checks, 'results': results,
              'limitations': [
                  'Exact finite-model arithmetic and certificates supplement a separate full prose/proof review.',
                  'Finite grids alone do not prove global optimality; the analytic bounds are stated and checked independently.',
                  'Synthetic parameters establish no empirical effect, legal conclusion or universal organizational ranking.',
                  'Source checks verify proposal structure and alignment; the scoped primary inspection is recorded separately.',
                  'No browser visual/mobile/print QA was performed; root retains integration and acceptance.'
              ]}
    json.dumps(report)
    return report


if __name__ == '__main__':
    print(json.dumps(check(), indent=2))
