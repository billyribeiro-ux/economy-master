"""Independent accounting, optimization certificates and boundary checks for c05.

Exact rational arithmetic checks the original synthetic economies. Finite checks
supplement the separately reviewed analytic proofs, not a general GE solver.
"""
from fractions import Fraction as F
from html.parser import HTMLParser
from itertools import product
from math import isclose, log
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[1]
CHAPTER = ROOT / 'content/chapters/v05-c05.html'
SOURCES = ROOT / 'content/reviews/v05-c05-sources.json'


def require(condition, message):
    if not condition:
        raise ValueError(message)


class Structure(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.lists, self.sources, self.links, self.ids = [], [], [], [], []
        self.worked = self.exercises = self.solutions = self.solution_blocks = self.h1 = 0
        self.in_solutions = False
        self.rows, self.row, self.cell = [], None, None

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
        if tag == 'aside' and attrs.get('class') == 'worked':
            self.worked += 1
        if tag == 'details' and attrs.get('class') == 'solutions':
            self.in_solutions = True
            self.solution_blocks += 1
        if tag == 'ol':
            self.lists.append(attrs.get('class'))
        if tag == 'li' and self.lists:
            if self.lists[-1] == 'exercises':
                self.exercises += 1
            elif self.in_solutions:
                self.solutions += 1
        if tag == 'tr':
            self.row = []
        if tag in ('td', 'th'):
            self.cell = ''

    def handle_data(self, data):
        if self.cell is not None:
            self.cell += data

    def handle_endtag(self, tag):
        require(bool(self.stack) and self.stack.pop() == tag, 'unbalanced HTML: ' + tag)
        if tag == 'ol':
            self.lists.pop()
        if tag == 'details':
            self.in_solutions = False
        if tag in ('td', 'th'):
            self.row.append(self.cell.strip())
            self.cell = None
        if tag == 'tr':
            self.rows.append(self.row)
            self.row = None


def dot(a, b):
    require(len(a) == len(b), 'dot-product dimensions')
    return sum((x*y for x, y in zip(a, b)), F(0))


def plus(a, b):
    return tuple(x+y for x, y in zip(a, b))


def minus(a, b):
    return tuple(x-y for x, y in zip(a, b))


def share_demand(share, prices, wealth):
    require(F(0) < share < 1 and all(p > 0 for p in prices) and wealth >= 0,
            'share-demand domain')
    return share*wealth/prices[0], (1-share)*wealth/prices[1]


def exchange(endowments, prices, transfers=(F(0), F(0))):
    wealth = [dot(prices, w)+t for w, t in zip(endowments, transfers)]
    demands = [share_demand(a, prices, m) for a, m in zip((F(1, 3), F(2, 3)), wealth)]
    excess = minus(plus(*demands), plus(*endowments))
    return wealth, demands, excess


def objective_certificate(prices, wealth, share):
    """Factorized cubic objective differences, not the text's log-FOC proof."""
    p1, p2 = prices
    optimum = share_demand(share, prices, wealth)
    for k in range(25):
        expenditure = wealth*F(k, 24)
        bundle = expenditure/p1, (wealth-expenditure)/p2
        if share == F(1, 3):
            best = optimum[0]*optimum[1]**2
            other = bundle[0]*bundle[1]**2
            gap = (expenditure-wealth/3)**2*(4*wealth/3-expenditure)/(p1*p2**2)
        else:
            best = optimum[0]**2*optimum[1]
            other = bundle[0]**2*bundle[1]
            gap = (expenditure-2*wealth/3)**2*(expenditure+wealth/3)/(p1**2*p2)
        require(best-other == gap >= 0, 'exact global exchange objective difference')


def log_demand(coefficient, price, wealth):
    require(coefficient > 0 and price > 0 and wealth >= 0, 'log-demand domain')
    good2 = min(wealth/price, max(F(0), coefficient/price-1))
    return wealth-price*good2, good2


def production(coefficients, ownership, price):
    q, profit = 2*price, price**2
    wealth = [endow+share*profit for endow, share in zip((F(12), F(8)), ownership)]
    demands = [log_demand(a, price, m) for a, m in zip(coefficients, wealth)]
    return q, profit, wealth, demands


def bisect_positive_root(function, left, right):
    require(function(left) > 0 > function(right), 'root bracket')
    for _ in range(75):
        middle = (left+right)/2
        if function(middle) > 0:
            left = middle
        else:
            right = middle
    return (left+right)/2


def exact_strings(values):
    return [str(v) for v in values]


def check():
    text = CHAPTER.read_text(encoding='utf-8')
    parser = Structure()
    parser.feed(text)
    require(not parser.stack and not parser.h1, 'balanced static fragment, no h1')
    require(parser.worked == 3 and parser.exercises == parser.solutions == 8,
            'three worked cases and eight matched solutions')
    require(parser.solution_blocks == 1 and len(parser.ids) == len(set(parser.ids)), 'unique structure')
    for term in ('Capability:', 'Prerequisite:', 'Teach-back', 'Delayed check',
                 'quasiequilibrium', 'Walras law', 'Pareto efficient'):
        require(term in text, 'instructional term: ' + term)
    proposals = json.loads(SOURCES.read_text(encoding='utf-8'))
    fields = {'id', 'title', 'url', 'use', 'checked', 'verification'}
    require(len(proposals) == 3 and all(set(s) == fields and s['id'].startswith('v05-c05-')
            and all(type(s[k]) is str and s[k] for k in fields) for s in proposals), 'source schema')
    require(set(parser.sources) == {s['id'] for s in proposals}, 'source proposal/citation match')
    require('v05-c04.html' in parser.links and 'v05-c06.html' in parser.links, 'chapter handoff')
    for link in parser.links:
        if re.fullmatch(r'v\d{2}-c\d{2}\.html', link) and link != 'v05-c06.html':
            require((ROOT/'content/chapters'/link).is_file(), 'prior route: ' + link)
    expected_pairs = [((0, 0), (12, 12)), ((12, 12), (0, 0)),
                      ((9, 3), (3, 9)), ((4, 8), (8, 4)),
                      ((2, F(16, 3)), (10, F(20, 3)))]
    for row, (a, b) in zip(parser.rows[1:], expected_pairs):
        parse_pair = lambda value: tuple(F(v) for v in value.strip('()').split(','))
        require(parse_pair(row[1]) == a and parse_pair(row[2]) == b and plus(a, b) == (12, 12),
                'actual coordinate-table quantities')
    require(len(parser.rows) == 6, 'complete coordinate table')
    checks = ['Balanced chapter, three worked cases, eight matched solutions, answered retention check, '
              'prior/successor links, three scoped source records and all five coordinate-table rows.']
    results = {}

    endowments = [(F(9), F(3)), (F(3), F(9))]
    wealth, demands, excess = exchange(endowments, (F(1), F(1)))
    require(wealth == [12, 12] and demands == [(4, 8), (8, 4)] and excess == (0, 0),
            'worked exchange equilibrium')
    require([demands[0][0]*demands[0][1]**2, demands[1][0]**2*demands[1][1]] == [256, 256],
            'equilibrium within-person utility values')
    require(9*3**2 == 3**2*9 == 81, 'endowment within-person utility values')
    require(minus(demands[0], endowments[0]) == (-5, 5), 'net trade')
    w2, d2, z2 = exchange(endowments, (F(2), F(1)))
    require(w2 == [21, 15] and d2 == [(F(7, 2), 14), (5, 5)] and z2 == (F(-7, 2), 7),
            'exercise off-equilibrium accounts')
    require(dot((F(2), F(1)), z2) == 0 and z2 != (0, 0), 'Walras law versus clearing')
    ws, ds, zs = exchange(endowments, (F(2, 3), F(1, 3)))
    require(ws == [7, 5] and ds == d2 and zs == z2, 'normalization')
    require(dot((F(1), F(0)), (F(0), F(2))) == 0, 'zero-price omitted market')
    altered = [(F(6), F(2)), (F(6), F(10))]
    wa, da, za = exchange(altered, (F(11, 9), F(1)))
    require(wa == [F(28, 3), F(52, 3)] and za == (0, 0)
            and da == [(F(28, 11), F(56, 9)), (F(104, 11), F(52, 9))], 'exercise changed endowments')
    equilibrium_cases = 0
    for a1, a2, b1, b2 in product(map(F, (1, 3, 9)), repeat=4):
        stocks = [(a1, a2), (b1, b2)]
        # Value of demand for good 1 equals its endowment value:
        # (a1*r+a2)/3 + 2*(b1*r+b2)/3 = (a1+b1)*r.
        ratio = (a2+2*b2)/(2*a1+b1)
        p = (ratio, F(1))
        w, d, z = exchange(stocks, p)
        require(z == (0, 0) and all(dot(p, x) == m for x, m in zip(d, w)), 'grid clearing/budgets')
        for share, m in zip((F(1, 3), F(2, 3)), w):
            objective_certificate(p, m, share)
        for multiplier in (F(1, 2), F(2)):
            p_off = (ratio*multiplier, F(1))
            _, _, z_off = exchange(stocks, p_off)
            require(dot(p_off, z_off) == 0 and z_off != (0, 0), 'off-equilibrium value identity')
        equilibrium_cases += 1
    results['exchange'] = {'worked_price': ['1', '1'], 'worked_bundles': [['4', '8'], ['8', '4']],
                           'altered_price': '11/9', 'altered_bundles': [exact_strings(d) for d in da],
                           'off_equilibrium_excess': exact_strings(z2), 'parameter_cases': equilibrium_cases}
    checks.append('Exact exchange budgets, both markets, endogenous wealth, nominal normalization and '
                  'net trades; 81 distinct endowment economies, each with independent cubic global-choice '
                  'certificates and two nonclearing price checks.')

    transfer_cases = []
    for s in [F(k, 4) for k in range(1, 48)]:
        t = 16*s/(4+s)
        target = [(s, t), (12-s, 12-t)]
        ratio = t/(2*s)
        require(ratio == 2*(12-t)/(12-s), 'contract-curve common MRS')
        p = (ratio, F(1))
        transfers = [dot(p, minus(x, e)) for x, e in zip(target, endowments)]
        w, d, z = exchange(endowments, p, transfers)
        require(sum(transfers) == 0 and d == target and z == (0, 0), 'decentralized support')
        for share, m in zip((F(1, 3), F(2, 3)), w):
            objective_certificate(p, m, share)
        if s in (2, 6):
            transfer_cases.append((s, p, w, target, transfers))
    require(transfer_cases[0] == (F(2), (F(4, 3), F(1)), [F(8), F(20)],
            [(F(2), F(16, 3)), (F(10), F(20, 3))], [F(-7), F(7)]), 'worked supporting transfers')
    require(transfer_cases[1] == (F(6), (F(4, 5), F(1)), [F(72, 5), F(36, 5)],
            [(F(6), F(48, 5)), (F(6), F(12, 5))], [F(21, 5), F(-21, 5)]), 'exercise support')
    require(F(2)*F(16, 3)**2 == F(512, 9) < 256 and F(10)**2*F(20, 3) == F(2000, 3) > 256,
            'worked redistribution is not Pareto improvement')
    require(F(6)*F(48, 5)**2 == F(13824, 25) > 256 and F(6)**2*F(12, 5) == F(432, 5) < 256,
            'exercise redistribution is not Pareto improvement')
    results['support'] = {'worked_price': '4/3', 'worked_transfers': ['-7', '7'],
                          'exercise_price': '4/5', 'exercise_transfers': ['21/5', '-21/5'],
                          'interior_curve_points_checked': 47}
    checks.append('47 contract-curve targets have equal MRS, budget-balanced transfers, individually '
                  'globally optimal demands and both markets clearing; both redistribution cases have a loser.')

    # Satiation and quasiequilibrium counterexamples are evaluated separately.
    require(sum((1, 1)) == sum((0, 2)) == 2 and 0 == 0 and 2 > 1, 'satiation Pareto improvement')
    for x1, x2 in product(map(F, range(5)), repeat=2):
        require(dot((F(1), F(0)), (x1, x2)) >= 0, 'weak quasi support cost inequality')
        if x1+x2 <= 1:
            require(x1+x2 <= sum((0, 1)), 'alternative full-support utility bound')
    require(dot((F(1), F(0)), (F(0), F(2))) == 0 and sum((0, 2)) > sum((0, 1)),
            'strictly preferred same-cost bundle')
    for k in range(1, 21):
        epsilon = F(1, k+1)
        require(dot((F(1), F(1)), (F(1)-epsilon, F(0))) < 1, 'cheaper mixture cost identity')
    checks.append('Satiation example is feasible and Pareto improving despite equilibrium choice; '
                  'zero-wealth/zero-price quasiequilibrium has better affordable bundles, while '
                  'alternative support prices make the target a consumer optimum.')

    production_results = []
    for coeffs, ownership, r, wanted_wealth, wanted_numeraire in [
            ((F(8), F(4)), (F(3, 4), F(1, 4)), F(2), [F(15), F(9)], [F(9), F(7)]),
            ((F(8), F(4)), (F(0), F(1)), F(2), [F(12), F(12)], [F(6), F(10)]),
            ((F(12), F(12)), (F(3, 4), F(1, 4)), F(3), [F(75, 4), F(41, 4)], [F(39, 4), F(5, 4)]),
            ((F(12), F(12)), (F(0), F(1)), F(3), [F(12), F(17)], [F(3), F(8)])]:
        q, pi, w, d = production(coeffs, ownership, r)
        input_use = q*q/4
        require(w == wanted_wealth and [x[0] for x in d] == wanted_numeraire
                and all(x[0] > 0 for x in d), 'production income/regime')
        require(sum(x[1] for x in d) == q and sum(x[0] for x in d)+input_use == 20,
                'production both physical markets')
        require(sum(w) == 20+pi and all(dot((F(1), r), x) == m for x, m in zip(d, w)),
                'production budgets and profit ownership')
        for candidate in [F(k, 4) for k in range(49)]:
            candidate_profit = r*candidate-candidate**2/4
            require(pi-candidate_profit == (candidate-q)**2/4 >= 0, 'firm global profit certificate')
        for a, m, x in zip(coeffs, w, d):
            require(a/(1+x[1]) == r, 'consumer marginal condition with positive numeraire')
            objective = float(x[0])+float(a)*log(1+float(x[1]))
            for k in range(31):
                alternative_q = (m/r)*F(k, 30)
                alternative_value = float(m-r*alternative_q)+float(a)*log(1+float(alternative_q))
                require(alternative_value <= objective+1e-11, 'direct consumer objective comparison')
        # This oracle retains the wealth cap, independently of the interior
        # aggregate polynomial used in the manuscript.
        def excess_at(candidate_price):
            candidate_profit = candidate_price**2
            income = [float(e)+float(t)*candidate_profit for e, t in zip((12, 8), ownership)]
            demand = [min(m/candidate_price, max(0, float(a)/candidate_price-1))
                      for a, m in zip(coeffs, income)]
            return sum(demand)-2*candidate_price
        independent_price = bisect_positive_root(excess_at, .1, 10.0)
        require(isclose(independent_price, float(r), abs_tol=1e-12, rel_tol=1e-12), 'capped-demand equilibrium oracle')
        production_results.append({'price': str(r), 'output': str(q), 'input': str(input_use),
                                   'profit': str(pi), 'wealth': exact_strings(w),
                                   'consumption': [exact_strings(x) for x in d]})
    require(log_demand(F(12), F(3), F(0)) == (0, 0) and F(12)/3-1 > 0, 'zero-wealth cap')
    results['production'] = production_results
    checks.append('Four production/ownership scenarios reconcile every profit, budget and resource; '
                  'global profit-square certificates, independent capped-demand bisection and direct '
                  'consumer utility comparisons verify the equilibrium branches and the zero-wealth boundary.')

    # Unpriced pollution: exact feasible quantities and an independent sign
    # factorization certify the aggregate derivative's optimum.
    qstar = F(3)
    astar, bstar = F(7, 3), F(2, 3)
    require(astar+bstar == qstar and 8/(1+astar) == 4/(1+bstar) == F(12, 5), 'pollution allocation')
    require(F(10)+F(31, 4)+qstar*qstar/4 == 20, 'pollution resource accounting')
    for q in [F(k, 10) for k in range(10, 90)]:
        derivative = 12/(q+2)-q/2-F(9, 10)
        require(derivative == -(q-3)*(5*q+34)/(10*(q+2)), 'independent derivative factorization')
        require((derivative > 0) == (q < 3) and (derivative < 0) == (q > 3), 'global interior sign')
    for q in [F(k, 20) for k in range(21)]:
        require(8/(1+q)-q/2-F(9, 10) >= F(13, 5) > 0, 'low-output corner branch improves')
    best_sum = float(20-qstar*qstar/4)+8*log(1+float(astar))+4*log(1+float(bstar))-float(F(9, 10)*qstar)
    for q, fraction_a in product([F(k, 10) for k in range(90)], [F(k, 20) for k in range(21)]):
        require(q*q/4 <= 20, 'planner grid physical input')
        qa, qb = q*fraction_a, q*(1-fraction_a)
        candidate_sum = float(20-q*q/4)+8*log(1+float(qa))+4*log(1+float(qb))-float(F(9, 10)*q)
        require(candidate_sum <= best_sum+1e-11, 'independent planner objective grid')
    # Alternating series supplies exact independent bounds on log(6/5).
    log_lower = sum(((-1)**(k+1)*F(1, 5)**k/k for k in range(1, 21)), F(0))
    log_upper = log_lower+F(1, 5)**21/21
    require(0 < log_lower < log_upper < F(1, 5), 'log bound')
    gain_a = F(8, 5)-8*log_upper
    gain_b = F(21, 20)-4*log_upper
    require(gain_a > 0 and gain_b > 0, 'strict individual welfare gains')
    require(isclose(float(F(8, 5))-8*log(6/5), .141427545648363, abs_tol=1e-12), 'pollution gain A')
    require(isclose(float(F(21, 20))-4*log(6/5), .320713772824182, abs_tol=1e-12), 'pollution gain B')
    results['missing_pollution_price'] = {'private_output': '4', 'efficient_output': '3',
                                          'new_bundles': [['10', '7/3'], ['31/4', '2/3']],
                                          'individual_gain_lower_bounds': [float(gain_a), float(gain_b)],
                                          'global_objective_grid': 90*21}
    checks.append('Pollution case: exact derivative factorization, low-output boundary, 1,890 feasible '
                  'quantity/allocation comparisons and rational logarithm bounds verify both strictly '
                  'positive individual gains and all resource balances.')

    # Nonconvex technology: global planner value is bounded without evaluating
    # irrational square roots; q=(c*z)^2 with c in [0,1].
    for z, c in product([F(k, 8) for k in range(17)], [F(k, 8) for k in range(9)]):
        numeraire, root_output = 4-z, c*z
        require(numeraire+root_output <= 4, 'nonconvex economy global utility bound')
    require(F(1)**2 < 2, 'infeasible production midpoint')
    price_pairs = 0
    for a, b in product([F(k, 4) for k in range(17)], repeat=2):
        if a == b == 0:
            continue
        candidate_profit = b-a
        require(max(F(0), 4*b-2*a) > candidate_profit, 'unsupported production plan endpoint deviation')
        price_pairs += 1
    results['nonconvexity'] = {'efficient_utility': '4', 'infeasible_midpoint': ['-1', '2'],
                              'price_pairs_with_profitable_deviation': price_pairs}
    checks.append('Nonconvex production: exact global utility bound over frontier/disposal cases and '
                  '288 nonzero nonnegative price pairs exhibit a profitable endpoint deviation; '
                  'the universal no-support inequality is proved in the manuscript.')

    state_endowments = [(F(9), F(1)), (F(1), F(9))]
    state_prices = (F(1), F(1))
    state_demands = [share_demand(F(1, 2), state_prices, dot(state_prices, w)) for w in state_endowments]
    require(state_demands == [(5, 5), (5, 5)] and plus(*state_demands) == (10, 10), 'complete-market insurance')
    for e, x in zip(state_endowments, state_demands):
        require(e[0]*e[1] == 9 < x[0]*x[1] == 25 and dot(state_prices, minus(x, e)) == 0,
                'insurance utility/product and net expenditure')
    for k in range(41):
        a = F(k, 4)
        require(25-a*(10-a) == (a-5)**2 >= 0, 'independent log-demand product certificate')
    require(isclose(log(5)-log(3), log(5/3), abs_tol=1e-14), 'ex ante utility gain')
    delayed_prices = (F(2, 3), F(1))
    delayed_endowments = [(F(6), F(0)), (F(0), F(4))]
    delayed = [share_demand(F(1, 2), delayed_prices, dot(delayed_prices, w)) for w in delayed_endowments]
    require(delayed == [(3, 2), (3, 2)] and plus(*delayed) == (6, 4)
            and all(dot(delayed_prices, x) == 4 for x in delayed), 'delayed equilibrium')
    results['insurance_and_retention'] = {'state_price': ['1', '1'], 'insured_bundles': [['5', '5'], ['5', '5']],
                                          'ex_ante_utility_gain': log(5/3), 'delayed_price': '2/3',
                                          'delayed_bundles': [['3', '2'], ['3', '2']]}
    checks.append('Missing insurance and complete contingent-market comparison checked through exact '
                  'state resources, wealth, net claims and a separate global product certificate; '
                  'delayed exchange example reconciles both markets and budgets.')

    report = {'chapter': 'v05-c05', 'status': 'passed', 'checks': checks, 'results': results,
              'limitations': [
                  'Finite checks supplement the separately reviewed analytic welfare/support arguments; no general equilibrium existence, uniqueness or dynamic stability theorem is established.',
                  'All economies and welfare changes are synthetic; no empirical preference, technology, causal policy impact or administrative feasibility is identified.',
                  'The general convex separation result is stated with scoped conditions and source; the chapter proves only the restricted constructive support result and cheaper-bundle upgrade.',
                  'Floating bisection and logarithmic objective grids are independent numerical references; the accounting, optimality-gap and individual-gain certificates retain exact rational checks.',
                  'Source retrieval verifies only recorded method passages. Browser visual/mobile/print QA and learner testing were not performed.'
              ]}
    json.dumps(report)  # Enforce the integration contract without a fallback serializer.
    return report


if __name__ == '__main__':
    try:
        answer = check()
    except Exception as error:
        print(json.dumps({'chapter': 'v05-c05', 'status': 'failed', 'error': str(error)}, indent=2))
        raise SystemExit(1)
    print(json.dumps(answer, indent=2))
