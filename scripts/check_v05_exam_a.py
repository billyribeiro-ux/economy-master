"""Independent exact checks for Volume 5 Form A. Standard library only.

Quiet check() API, directly JSON serializable. Numerical enumerations complement
the manuscript's analytic global proofs and the separate author/root review.
"""
from fractions import Fraction as F
from html.parser import HTMLParser
from itertools import combinations, product
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[1]
MANUSCRIPT = ROOT / 'content/assessment-parts/v05-form-a.html'


def require(condition, message):
    if not condition:
        raise ValueError(message)


class Manuscript(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.lists, self.ids, self.links = [], [], [], []
        self.parts, self.answers, self.rubrics = {}, set(), []
        self.domains = self.h1 = self.solution_blocks = 0
        self.rubric, self.table, self.row, self.cell = None, None, None, None
        self.tables = {}

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag not in ('br', 'hr', 'img', 'input', 'meta', 'link'):
            self.stack.append(tag)
        self.h1 += tag == 'h1'
        if 'id' in a:
            self.ids.append(a['id'])
        if tag == 'a':
            self.links.append(a.get('href', ''))
        if tag == 'ol':
            self.lists.append(a.get('class', ''))
        if tag == 'li':
            self.domains += bool(self.lists) and self.lists[-1] == 'exam-questions'
            if 'data-points' in a:
                self.parts[a['id']] = int(a['data-points'])
            if re.fullmatch(r'v05-a-s[1-5][a-d]', a.get('id', '')):
                self.answers.add(a['id'])
        if tag == 'details' and a.get('class') == 'solutions':
            self.solution_blocks += 1
        if tag == 'p' and a.get('class') == 'rubric':
            self.rubric = [int(a['data-points']), '']
        if tag == 'table':
            self.table = a['id']
            self.tables[self.table] = []
        if tag == 'tr':
            self.row = []
        if tag in ('th', 'td'):
            self.cell = ''

    def handle_data(self, data):
        if self.rubric is not None:
            self.rubric[1] += data
        if self.cell is not None:
            self.cell += data

    def handle_endtag(self, tag):
        require(bool(self.stack) and self.stack.pop() == tag, 'HTML balance: '+tag)
        if tag == 'ol':
            self.lists.pop()
        if tag == 'p' and self.rubric is not None:
            self.rubrics.append(self.rubric)
            self.rubric = None
        if tag in ('th', 'td'):
            self.row.append(self.cell.strip())
            self.cell = None
        if tag == 'tr':
            self.tables[self.table].append(self.row)
            self.row = None
        if tag == 'table':
            self.table = None


def dot(a, b):
    return sum((x*y for x, y in zip(a, b)), F(0))


def wage_vertices(probabilities, costs, target, outside):
    """Enumerate two-dimensional wage LP vertices, independently of cost formula."""
    p = probabilities[target]
    rows = [(F(1), F(0), F(0)), (F(0), F(1), F(0)),
            (1-p, p, F(outside)+costs[target])]
    for j, pj in enumerate(probabilities):
        if j != target:
            rows.append((pj-p, p-pj, costs[target]-costs[j]))
    feasible = []
    for (a, b, c), (d, e, f) in combinations(rows, 2):
        determinant = a*e-b*d
        if determinant:
            wf, ws = (c*e-b*f)/determinant, (a*f-c*d)/determinant
            if all(r*wf+s*ws >= rhs for r, s, rhs in rows):
                feasible.append(((1-p)*wf+p*ws, (wf, ws)))
    require(feasible, 'nonempty contract polyhedron')
    value = min(v for v, _ in feasible)
    return value, sorted(set(w for v, w in feasible if v == value))


def cournot(a, costs):
    """Enumerate active sets rather than assume both firms produce."""
    candidates = [(F(0), F(0)), (max(F(0), (a-costs[0])/2), F(0)),
                  (F(0), max(F(0), (a-costs[1])/2)),
                  ((a-2*costs[0]+costs[1])/3, (a-2*costs[1]+costs[0])/3)]
    equilibria = []
    for q in candidates:
        if min(q) < 0:
            continue
        if all(q[i] == max(F(0), (a-costs[i]-q[1-i])/2) for i in range(2)):
            if q not in equilibria:
                equilibria.append(q)
    return equilibria


def present_value(flows, date, beta, delta):
    return flows[date]+beta*sum((delta**(s-date)*flows[s] for s in range(date+1, len(flows))), F(0))


def check():
    html = MANUSCRIPT.read_text(encoding='utf-8')
    m = Manuscript()
    m.feed(html)
    require(not m.stack and not m.lists and not m.h1 and m.solution_blocks == 1, 'complete exam fragment')
    expected_parts = {f'v05-a-q{i}{part}' for i in range(1, 6) for part in 'abcd'}
    require(set(m.parts) == expected_parts and set(m.parts.values()) == {5}, 'twenty five-point parts')
    require(m.answers == {x.replace('-q', '-s') for x in expected_parts}, 'twenty exact answer matches')
    require(m.domains == 5 and sum(m.parts.values()) == 100, 'domain and total points')
    require(len(m.rubrics) == 20, 'one rubric per part')
    for points, rubric in m.rubrics:
        require(points == 5 and sum(int(x) for x in re.findall(r'\b([1-5])(?=[;.])', rubric)) == 5,
                'rubric components total five: '+rubric)
    require(len(m.ids) == len(set(m.ids)) and 'form-a' in m.ids
            and all(x == 'form-a' or x.startswith('v05-a-') for x in m.ids), 'unique/prefixed IDs')
    require({f'v05-c{i:02d}.html' for i in range(1, 13)} <= set(m.links), 'twelve chapter routes')
    require('180 minutes' in html and 'closed notes' in html and 'basic nonprogrammable calculator' in html,
            'exam administration')
    require('Scoring and critical errors' in html and 'transfer check' in html, 'critical error protocol')
    checks = ['HTML/question/answer/rubric correspondence, 100 points and all twelve method routes']
    results = {'format': {'domains': 5, 'parts': 20, 'points': 100, 'minutes': 180,
                          'words': len(re.sub(r'<[^>]+>', ' ', html).split())}}

    # D1: a factorized cubic certificate checks the product-utility optimizer.
    consumer_cases = []
    for px, py in ((F(1), F(1)), (F(8), F(1))):
        income = F(18)
        x, y = 2*income/(3*px), income/(3*py)
        value = x*x*y
        require(px*x+py*y == income, 'consumer budget')
        for numerator in range(61):
            t = F(numerator, 60)
            alternative = (income*t/px, income*(1-t)/py)
            gap = income**3/(px*px*py)*(t-F(2, 3))**2*(t+F(1, 3))
            require(value-alternative[0]**2*alternative[1] == gap >= 0, 'global cubic choice certificate')
        consumer_cases.append((x, y, value))
    require(consumer_cases == [(12, 6, 864), (F(3, 2), 6, F(27, 2))], 'consumer independent references')
    hicks = F(6), F(24)
    require(hicks[0]**2*hicks[1] == 864 and 8*hicks[0]+hicks[1] == 72, 'compensated target/cost')
    for numerator in range(1, 97):
        ratio = F(numerator, 24)
        candidate_x = 6*ratio
        candidate_cost = 8*candidate_x+F(864)/(candidate_x*candidate_x)
        gap = 24*(ratio-1)**2*(2*ratio+1)/(ratio*ratio)
        require(candidate_cost-72 == gap >= 0, 'global expenditure factorization')
    require(72-18 == 54 and 8*12+6-18 == 84 and 102-72 == 30, 'compensation/old-basket ledger')
    for numerator in range(41):
        q = F(numerator, 4)
        minimum_cost = 2*q*q+3*q
        for extra_labor in (F(0), F(1, 3), F(5)):
            labor_cost = 2*(q*q+extra_labor)+3*q
            require(labor_cost-minimum_cost == 2*extra_labor >= 0, 'conditional input global minimum')
        profit = 11*q-minimum_cost
        require(8-profit == 2*(q-2)**2 >= 0, 'global profit square')
        for price in (F(0), F(1), F(3)):
            require(price*q-minimum_cost <= 0, 'zero-output boundary')
    results['D1'] = {'demand_old': ['12', '6'], 'demand_new': ['3/2', '6'],
                     'hicksian_new': ['6', '24'], 'expenditure': '72', 'compensation': '54',
                     'old_basket_addition': '84', 'output': '2', 'labor': '4', 'profit': '8'}
    checks.append('D1 cubic/global cost certificates, compensation versus repricing and production boundaries')

    # D2: integrate benefit and cost independently of triangle/ledger arithmetic.
    tax_ledgers = []
    for tax in (F(0), F(9)):
        q = (45-tax)/3
        buyer, seller = 50-2*q, 5+q
        benefit, cost = 50*q-q*q, 5*q+q*q/2
        cs, ps, revenue = benefit-buyer*q, seller*q-cost, tax*q
        require(cs+ps+revenue == benefit-cost, 'competitive transfer cancellation')
        tax_ledgers.append((q, buyer, seller, cs, ps, revenue, benefit-cost))
    require(tax_ledgers == [(15, 20, 20, 225, F(225, 2), 0, F(675, 2)),
                           (12, 26, 17, 144, 72, 108, 324)], 'tax numerical references')
    require(tax_ledgers[0][-1]-tax_ledgers[1][-1] == F(27, 2), 'tax deadweight area')
    # Solve y clearing first, independently of the manuscript's x equation.
    eq_price = F(6-2, 3)
    exchange = []
    for p in (F(1, 2), F(1), eq_price, F(2), F(4)):
        wealth = 6*p, F(6)
        a, b = (F(3), 3*p), (4/p, F(2))
        z = a[0]+b[0]-6, a[1]+b[1]-6
        require(p*z[0]+z[1] == 0, 'Walras value identity at trial prices')
        require(p*a[0]+a[1] == wealth[0] and p*b[0]+b[1] == wealth[1], 'endowment wealth/budgets')
        if p == eq_price:
            require(a == (3, 4) and b == (3, 2) and z == (0, 0), 'exchange equilibrium')
        if p == 2:
            require(z == (-1, 2), 'nonclearing Walras case')
        exchange.append({'p': str(p), 'wealth': list(map(str, wealth)), 'excess': list(map(str, z))})
    pareto_checks = 0
    for x, y in product((F(i, 4) for i in range(25)), repeat=2):
        ua, ub = x*y, (6-x)**2*(6-y)
        require(not (ua >= 12 and ub >= 18 and (ua > 12 or ub > 18)), 'feasible Pareto grid supplement')
        pareto_checks += 1
    results['D2'] = {'untaxed': list(map(str, tax_ledgers[0])), 'taxed': list(map(str, tax_ledgers[1])),
                     'DWL': '27/2', 'exchange_price': str(eq_price), 'exchange_cases': exchange,
                     'feasible_Pareto_comparisons': pareto_checks}
    checks.append('D2 integrated surplus/transfer identity, endowment budgets, both markets and Walras counterexample')

    # D3: active-set/deviation checks and the actual manuscript's entry table.
    quantity_cases = []
    for costs, target in (((F(8), F(20)), (F(22), F(10))),
                          ((F(8), F(40)), (F(27), F(0)))):
        eqs = cournot(F(62), costs)
        require(eqs == [target], 'unique Cournot active set')
        price = max(F(62)-sum(target), F(0))
        profit = tuple((price-costs[i])*target[i] for i in range(2))
        for i in range(2):
            for numerator in range(201):
                deviation = F(numerator, 2)
                other_price = max(F(62)-deviation-target[1-i], F(0))
                payoff = (other_price-costs[i])*deviation
                require(payoff <= profit[i], 'Cournot global deviation incl zero price')
        quantity_cases.append({'costs': list(map(str, costs)), 'q': list(map(str, target)),
                               'price': str(price), 'profit': list(map(str, profit))})
    require(quantity_cases[0]['profit'] == ['484', '100'] and quantity_cases[1]['profit'] == ['729', '0'],
            'Cournot profit references')
    require(cournot(F(62), (F(8), F(40))) != [(F(86, 3), F(-10, 3))], 'negative output excluded')
    table = m.tables['v05-a-entry']
    require(len(table) == 6 and all(len(row) == 4 for row in table), 'entry table shape')
    outcomes = {}
    for mode, response, e, incumbent in table[1:]:
        outcomes[(mode, response)] = F(e.replace('−', '-')), F(incumbent.replace('−', '-'))
    require(outcomes == {('Out', 'Game ends'): (0, 14), ('Standard', 'Accommodate'): (5, 7),
                         ('Standard', 'Fight'): (-4, 3), ('Specialized', 'Accommodate'): (2, 6),
                         ('Specialized', 'Fight'): (-1, 9)}, 'actual entry data')
    modes = ('Out', 'Standard', 'Specialized')
    plans = list(product(('Accommodate', 'Fight'), repeat=2))
    def entry_payoff(mode, plan):
        return outcomes[(mode, 'Game ends' if mode == 'Out' else plan[modes.index(mode)-1])]
    nash, spne = [], []
    for mode, plan in product(modes, plans):
        payoff = entry_payoff(mode, plan)
        if all(entry_payoff(other, plan)[0] <= payoff[0] for other in modes) and all(
                entry_payoff(mode, alternative)[1] <= payoff[1] for alternative in plans):
            profile = (mode, plan)
            nash.append(profile)
            if all(outcomes[(entry_mode, plan[j])][1] >= outcomes[(entry_mode, alternate)][1]
                   for j, entry_mode in enumerate(modes[1:]) for alternate in ('Accommodate', 'Fight')):
                spne.append(profile)
    require(set(nash) == {('Out', ('Fight', 'Fight')), ('Standard', ('Accommodate', 'Accommodate')),
                         ('Standard', ('Accommodate', 'Fight'))}, 'complete pure Nash set')
    require(spne == [('Standard', ('Accommodate', 'Fight'))], 'complete SPNE plan')
    results['D3'] = {'quantity_cases': quantity_cases,
                     'pure_Nash': [[mode, list(plan)] for mode, plan in nash],
                     'SPNE': [[mode, list(plan)] for mode, plan in spne]}
    checks.append('D3 independent active-set and global output checks; all 12 normal-form profiles and proper subgames')

    # D4: enumerate bidder price deviations and solve wage LPs independently.
    reservations, values = (F(5), F(13)), (F(9), F(21))
    lemons = []
    for high_share, existing in ((F(1, 4), F(9)), (F(1, 2), F(15))):
        masses = 1-high_share, high_share
        actual = sum((mass*(value-reservation) for mass, value, reservation in zip(masses, values, reservations)
                      if existing >= reservation), F(0))
        complete = sum((mass*(value-reservation) for mass, value, reservation in zip(masses, values, reservations)), F(0))
        for numerator in range(121):
            offer = F(numerator, 4)
            if offer > existing:
                gain = sum((mass*(value-offer) for mass, value, reservation in zip(masses, values, reservations)
                            if offer >= reservation), F(0))
                require(gain <= 0, 'no profitable higher offer')
        lemons.append({'high_share': str(high_share), 'price': str(existing),
                        'actual_gains': str(actual), 'verifiable_gains': str(complete)})
    require([r['actual_gains'] for r in lemons] == ['3', '6'], 'lemons actual gains')
    require([r['verifiable_gains'] for r in lemons] == ['5', '6'], 'lemons full gains')
    require(F(1, 2)*(9-14)+F(1, 2)*(21-14) == 1, 'profitable pooling deviation')
    probabilities, costs = (F(1, 3), F(2, 3)), (F(0), F(8))
    h_cost, h_wages = wage_vertices(probabilities, costs, 1, F(3))
    l_cost, _ = wage_vertices(probabilities, costs, 0, F(3))
    require(h_cost == 16 and h_wages == [(F(0), F(24))] and l_cost == 3, 'contract LP minima')
    utilities = tuple((1-p)*h_wages[0][0]+p*h_wages[0][1]-cost for p, cost in zip(probabilities, costs))
    require(utilities == (8, 8) and utilities[1]-3 == 5, 'contract tie and rent')
    profits = []
    for success in (F(54), F(48)):
        returns = tuple((1-p)*12+p*success for p in probabilities)
        candidate_profits = returns[0]-l_cost, returns[1]-h_cost, F(0)
        profits.append(tuple(candidate_profits))
    require(profits == [(23, 24, 0), (21, 20, 0)], 'action-choice reversal')
    require(40-(3+8) == 29 and 29-24 == 5, 'observable effort/rent benchmark')
    results['D4'] = {'lemons': lemons, 'H_wages': ['0', '24'], 'H_mean_wage': '16',
                     'agent_utilities_L_H': ['8', '8'], 'rent': '5',
                     'profits_L_H_nohire': [list(map(str, p)) for p in profits], 'observable_H_profit': '29'}
    checks.append('D4 selection/deviation/surplus comparisons, exact contract LP and all hiring alternatives')

    # D5: resource ledgers, arbitrary-threshold auction incentives and dated selves.
    def benefit(q):
        return 30*q-q*q/2
    def cost(q):
        return 6*q+q*q/2
    def damage(q):
        return q*q/2
    def welfare(q):
        return benefit(q)-cost(q)-damage(q)
    require(welfare(F(12)) == 72 and welfare(F(8)) == 96, 'externality targets')
    for numerator in range(121):
        q = F(numerator, 4)
        require(96-welfare(q) == F(3, 2)*(q-8)**2 >= 0, 'externality global certificate')
    q, pb, ps, wedge = F(8), F(22), F(14), F(8)
    cs, psurplus, receipt, harm = benefit(q)-pb*q, ps*q-cost(q), wedge*q, damage(q)
    require((cs, psurplus, receipt, harm) == (32, 32, 64, 32), 'corrective fiscal ledger')
    require(cs+psurplus+receipt-harm == welfare(q), 'fiscal transfer cancellation')
    require(welfare(q)-10 == 86 and welfare(q)-4 == 92 and receipt-10 == 54, 'net instruments and finance')
    values = (47, 34, 19)
    def auction(bids):
        winner = max(range(3), key=lambda i: (bids[i], -i))
        payment = max(bids[j] for j in range(3) if j != winner)
        utilities = tuple(F(values[i]-payment) if i == winner else F(0) for i in range(3))
        return winner, payment, utilities
    require(auction(values) == (0, 34, (13, 0, 0)), 'auction allocation ledger')
    require(auction((40, 34, 19)) == auction(values), 'nonunique best reply')
    require(auction((47, 50, 19)) == (1, 47, (0, -13, 0)), 'costly overbid')
    auction_comparisons = 0
    # Value/threshold tests allow either side to win ties, independently of the fixture.
    for value, rival, priority in product((F(0), F(19), F(34), F(47), F(60)),
                                         (F(0), F(19), F(34), F(47), F(60)), (False, True)):
        def payoff(bid):
            wins = bid > rival or (bid == rival and priority)
            return value-rival if wins else F(0)
        for numerator in range(141):
            require(payoff(value) >= payoff(F(numerator, 2)), 'truthful weak dominance by threshold')
            auction_comparisons += 1
    beta, delta = F(1, 2), F(4, 5)
    cash, wait, locked = (F(0), F(10), F(0)), (F(0), F(0), F(18)), (F(-1), F(0), F(18))
    pv = lambda flows, t: present_value(flows, t, beta, delta)
    require(pv(cash, 0) == 4 and pv(wait, 0) == F(144, 25), 'date0 intended ranking')
    require(pv(cash, 1) == 10 and pv(wait, 1) == F(36, 5), 'actual date1 reversal')
    require(pv(locked, 0) == F(119, 25) and pv(locked, 0)-pv(cash, 0) == F(19, 25), 'sophisticated actual benchmark')
    require(present_value(wait, 1, F(1), delta) == F(72, 5) > 10, 'naive forecast')
    require(pv(wait, 0) > pv(locked, 0) and sum(locked)-sum(cash) == 7, 'naive purchase and specified flow welfare')
    require(pv(wait, 0)-pv(cash, 0) == F(44, 25), 'maximum sophisticated lock fee')
    results['D5'] = {'unregulated_Q_W': ['12', '72'], 'target_Q_W': ['8', '96'],
                     'tax_cap_net_surplus': ['86', '92'], 'tax_net_funds': '54', 'cap_funding': '4',
                     'truthful_auction_winner_payment': [1, 34], 'threshold_comparisons': auction_comparisons,
                     'date0_cash_wait_lock': ['4', '144/25', '119/25'], 'date1_cash_wait': ['10', '36/5'],
                     'sophisticated_gain': '19/25', 'maximum_lock_fee': '44/25', 'flow_welfare_gain': '7'}
    checks.append('D5 global externality and fiscal accounts, auction threshold deviations, and dated actual/forecast welfare')
    report = {'assessment': 'v05-form-a', 'status': 'passed', 'checks': checks, 'results': results,
              'limitations': [
                  'Finite numerical checks supplement the separate full prompt/solution/global-proof audit.',
                  'Grids are not proofs of all possible deviations; the manuscript supplies analytic global arguments.',
                  'All models are synthetic and establish no real intervention effect or universal welfare ranking.',
                  'This internal review does not certify learner timing/difficulty or replace external academic assessment.',
                  'No browser visual/mobile/print QA; root owns integration, cross-form review and acceptance.'
              ]}
    json.dumps(report)
    return report


if __name__ == '__main__':
    print(json.dumps(check(), indent=2))
