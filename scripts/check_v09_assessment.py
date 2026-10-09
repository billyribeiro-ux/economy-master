"""Exact support calculations and assembly gates for the Volume 9 assessment.

Fraction arithmetic reconstructs the finite cases without importing any supplied
project model. Economic assumptions and open answers require editorial review.
This checker does not certify human competence, market forecasts or browser QA.
"""
from fractions import Fraction as F
from html.parser import HTMLParser
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARTS = ('v09-support-opening.html', 'v09-exam-a.html', 'v09-exam-b.html',
         'v09-project.html', 'v09-support-closing.html')


def require(condition, message):
    if not condition:
        raise AssertionError(message)


class Structure(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.points = {}
        self.solutions = []
        self.links = []

    def handle_starttag(self, tag, attributes):
        a = dict(attributes)
        if 'id' in a:
            self.ids.append(a['id'])
        # Project rubric rows have their own score gate; this map is for prompts.
        if 'data-points' in a and tag == 'li':
            key = a.get('id')
            require(key is not None, 'Scored prompt requires an anchor')
            require(key not in self.points, 'Duplicate point record: '+str(key))
            self.points[key] = int(a['data-points'])
        if 'data-solution-for' in a:
            require(tag == 'li', 'Matched answers must be semantic list items')
            self.solutions.append(a['data-solution-for'])
        if tag == 'a':
            self.links.append(a.get('href', ''))


def support_check():
    counts = {'comparisons': 0, 'groups': 0}

    def check(condition, message):
        counts['comparisons'] += 1
        require(condition, message)

    def moments(values, probabilities):
        check(sum(probabilities) == 1 and all(p > 0 for p in probabilities),
              'Positive exhaustive physical states')
        mean = sum(v*p for v, p in zip(values, probabilities))
        return mean, sum(p*(v-mean)**2 for v, p in zip(values, probabilities))

    # Diagnostic: reconstruct terminal cash rather than using return shortcuts.
    year1 = 200*F(11, 10)
    end = (year1+50)*F(9, 10)
    check((year1, end, end-250, end/200-1) ==
          (220, 243, -7, F(43, 200)), 'D1 funded calendar')
    p = (F(2, 3), F(1, 3))
    r = (F(1, 5), F(-1, 10))
    portfolio = tuple(F(2, 5)*x+F(3, 5)*F(1, 20) for x in r)
    check(moments(r, p) == (F(1, 10), F(1, 50)) and
          moments(portfolio, p) == (F(7, 100), F(2, 625)),
          'D2 weighted-state moments')
    a = F(2, 3-1); b = -a
    check(tuple(a*x+b for x in (3, 1)) == (2, 0) and
          a*F(17, 10)+b*F(9, 10) == F(4, 5), 'D3 replicated rights/cost')
    mass_event, mass_other = F(1, 10)*F(4, 5), F(9, 10)*F(1, 5)
    check(mass_event/(mass_event+mass_other) == F(4, 13), 'D4 conditioning')
    f = lambda w: F(3, 50)*w-F(2, 25)*w*w
    check(F(3, 50)/(2*F(2, 25)) == F(3, 8) and f(F(1, 4)) == F(1, 100),
          'D5 stationary point and feasible value')
    for i in range(101):
        check(f(F(i, 400)) <= f(F(1, 4)), 'D5 independent feasible grid')
    check((18-12, 8-(18-12), 18-12+7) == (6, 2, 13), 'D6 dated reserve')
    wealth = sum(1+x for x in (F(1, 5), F(1, 10), F(-1)))
    check((wealth, wealth/3-1, (F(1, 5)+F(1, 10))/2) ==
          (F(23, 10), F(-7, 30), F(3, 20)), 'D7 original and survivor cohorts')
    check((4-F(49, 25)*3, 4+F(49, 25)*3) ==
          (F(-47, 25), F(247, 25)), 'D8 confidence interval in pp')
    counts['groups'] += 8

    # Oral: log maximization is equivalent to product order only on its domain.
    menu = tuple(map(F, (0, '0.1', '0.5', 1)))
    best = []
    for income in (0, 1):
        candidates = []
        for w in menu:
            terminal = tuple(10*((1-w)+w*g)+income-9
                             for g in (F(8, 5), F(4, 5)))
            if min(terminal) > 0:
                candidates.append((terminal[0]*terminal[1], w))
        best.append(max(candidates))
    check(best == [(F(32, 25), F(1, 10)), (5, F(1, 2))],
          'O1 enumerate admissible contingent-node actions')
    probabilities = (F(3, 4), F(1, 4))
    m = (F(4, 5), F(7, 5))
    q = tuple(a*b for a, b in zip(probabilities, m))
    price = lambda claim: sum(a*b for a, b in zip(q, claim))
    check(q == (F(3, 5), F(7, 20)) and price((1, 0)) == F(3, 5)
          and price((0, 3)) == F(21, 20) and sum(q) == F(19, 20),
          'O2 physical means differ from state pricing')
    check(sum(p*x for p, x in zip(probabilities, (1, 0))) ==
          sum(p*x for p, x in zip(probabilities, (0, 3))) == F(3, 4)
          and tuple(x/sum(q) for x in q) == (F(12, 19), F(7, 19)),
          'O2 expectation equality and normalized pricing probabilities')
    cash = 20+7*F(19, 20)-18-5
    check((cash, 4-cash, F(7)/F(19, 20)) ==
          (F(73, 20), F(7, 20), F(140, 19)), 'O4 binding authorized capacity')
    counts['groups'] += 3

    # Retention1: annual IRR polynomial and a covariance minimum certificate.
    preflow = 1000*F(27, 25)
    before_fee = (preflow+200)*F(19, 20)
    end = before_fee-16
    linked = preflow/1000*end/(preflow+200)-1
    check((preflow, before_fee, end, linked) ==
          (1080, 1216, 1200, F(1, 80)), 'R1 valuation chain and net TWR')
    roots = (F(1), F(-6, 5))
    check(all(1000*g*g+200*g-1200 == 0 for g in roots)
          and [g-1 for g in roots if g > 0] == [0], 'R1 unique admissible annual IRR')
    variance = lambda w: F(1, 25)*w*w+F(1, 100)*(1-w)**2+F(1, 100)*w*(1-w)
    check((variance(F(1, 8)), variance(F(1, 5))) ==
          (F(3, 320), F(6, 625)), 'R1 unconstrained and constrained variance')
    for i in range(201):
        w = F(1, 5)+F(i, 250)
        check(variance(w)-variance(F(1, 5)) ==
              (w-F(1, 5))*(F(1, 25)*(w+F(1, 5))-F(1, 100)) >= 0,
              'R1 exact global constrained certificate')
    counts['groups'] += 1

    # Retention2: all grid prices obey both rights and positivity; endpoints fail.
    for i in range(1, 90):
        t = F(i, 200)
        state_prices = (t, F(9, 10)-2*t, F(1, 20)+t)
        check(min(state_prices) > 0 and sum(state_prices) == F(19, 20)
              and state_prices[1]+2*state_prices[2] == 1,
              'R2 admissible pricing family')
        check(F(1, 20) < state_prices[0]+state_prices[2] < F(19, 20),
              'R2 open contingent-price interval')
    payoff = tuple(x-a+1 for x, a in zip((1, 0, 1), (0, 1, 2)))
    rf = 1/F(19, 20)-1
    physical = F(1, 2)+F(3, 10)*2-1
    capm = rf+F(7, 5)*F(1, 20)
    check(F(1, 20)-1+F(19, 20) == 0 and payoff == (2, 0, 0),
          'R2 zero-cost lower-endpoint arbitrage')
    check((rf, physical, capm, physical-capm) ==
          (F(1, 19), F(1, 10), F(233, 1900), F(-43, 1900)),
          'R2 conditional CAPM discrepancy is not replication')
    counts['groups'] += 1

    # Retention3: compute projections directly from the supplied observations.
    factor = tuple(map(F, (-2, -1, 1, 2)))
    second = (F(3, 2), F(-1, 2), F(-1, 2), F(3, 2))
    returns = (F(0), F(-5, 2), F(1, 2), F(6))
    weights = (F(1, 4),)*4
    ef, vf = moments(factor, weights)
    eg, vg = moments(second, weights)
    ey, _ = moments(returns, weights)
    cov = sum((x-ef)*(y-ey) for x, y in zip(factor, returns))/4
    beta = cov/vf; alpha = ey-beta*ef
    residual = tuple(y-alpha-beta*f for y, f in zip(returns, factor))
    active = tuple(y-F(3, 2)*f for y, f in zip(returns, factor))
    net = tuple(x-F(2, 5) for x in active)
    check((ef, vf, eg, vg, beta, alpha) == (0, F(5, 2), F(1, 2), 1, F(3, 2), 1)
          and residual == (2, -2, -2, 2), 'R3 descriptive one-factor projection')
    check(all(y == F(3, 2)*f+2*g for y, f, g in zip(returns, factor, second))
          and sum((f-ef)*(g-eg) for f, g in zip(factor, second)) == 0,
          'R3 exact full exposure and orthogonality')
    check(moments(active, weights) == (1, 4)
          and moments(net, weights) == (F(3, 5), 4)
          and sum(net)/4/2 == F(3, 10), 'R3 constant fee and population IR')
    counts['groups'] += 1

    # Retention4: exact square-loss certificates, including state-surplus units.
    def surplus_objective(x, income):
        states = tuple(10+x*(g-1)+y-5 for g, y in
                       zip((F(7, 5), F(4, 5)), income))
        mean, var = moments(states, (F(1, 2), F(1, 2)))
        return states, mean, var, mean-var/2

    chosen = F(70, 9)
    states, mean, var, score = surplus_objective(chosen, (2, 6))
    check((states, mean, var, score) ==
          ((F(91, 9), F(85, 9)), F(88, 9), F(1, 9), F(175, 18)),
          'R4 liability/endowment optimum')
    no_income = surplus_objective(F(10, 9), (0, 0))
    for i in range(101):
        x = F(i, 10)
        score_x = surplus_objective(x, (2, 6))[-1]
        no_x = surplus_objective(x, (0, 0))[-1]
        check(score-score_x == F(9, 200)*(x-chosen)**2 >= 0
              and no_income[-1]-no_x == F(9, 200)*(x-F(10, 9))**2 >= 0,
              'R4 global choices on initial cash budget')
    counts['groups'] += 1

    # Retention5: nested cash calendar and stationary filter, not NAV funding.
    base = 50-30-12; stress = base-8
    sale = (10-stress)/F(49, 50)
    check((base, stress, 10-base, 10-stress, sale) ==
          (8, 0, 2, 10, F(500, 49))
          and sale <= 12 and stress+sale*F(49, 50) == 10,
          'R5 gross payments and executable remedy')
    check(10-(stress+10*F(49, 50)) == F(1, 5), 'R5 reduced capacity infeasible')
    smoothing = F(3, 5)
    latent = (F(-1, 50)-smoothing*F(1, 50))/(1-smoothing)
    filter_ratio = (1-smoothing)**2/(1-smoothing**2)
    check((latent, filter_ratio) == (F(-2, 25), F(1, 4)),
          'R5 return inversion and stationary iid variance')
    counts['groups'] += 1

    # Retention6: reconstruct wealth, signed cost, integer feasibility boundary.
    cash = 120*F(79, 2)-6
    mark = 80*39
    filled = 120*(40-F(79, 2))+6
    opportunity = 80*(40-39)
    check(200*40-cash-mark == filled+opportunity == 146
          and (filled, opportunity) == (66, 80), 'R6 entire target shortfall')
    check(2*(-1)*(F(79, 2)-F(199, 5)) == F(3, 5), 'R6 signed sell spread')
    sale_net = 39-F(1, 20)
    feasible = [n for n in range(81) if cash+n*sale_net >= 5000]
    n = min(feasible)
    check(n == 7 and cash+6*sale_net == F(49677, 10)
          and cash+n*sale_net == F(100133, 20) and 80-n == 73,
          'R6 smallest whole-share funding repair')
    check(cash+n*sale_net+(80-n)*39 == cash+mark-F(7, 20),
          'R6 mark-to-cash conservation and additional fee')
    counts['groups'] += 1
    return {'status': 'passed', **counts,
            'scope': 'Eight diagnostic cases, three quantitative oral cases, six delayed reconstructions, exact global/capacity certificates. Oral evidence design and all interpretation require editorial review.'}


def check():
    from check_v09_exam_a import check as check_a
    from check_v09_exam_b import check as check_b
    from check_v09_project import check as check_project
    assembled = (ROOT/'content/assessments/v09.html').read_text()
    expected = '\n\n'.join((ROOT/'content/assessments/parts'/name).read_text().strip()
                           for name in PARTS)+'\n'
    require(assembled == expected, 'Volume 9 assembly differs from reviewed parts')
    doc = Structure(); doc.feed(assembled)
    require(len(doc.ids) == len(set(doc.ids)), 'Duplicate assessment anchors')
    for component in ('diagnostic', 'exam-rules', 'form-a', 'solutions-a', 'form-b',
                      'solutions-b', 'project', 'oral-transfer', 'retention',
                      'notation-index', 'concept-index', 'volume-synthesis'):
        require(component in doc.ids, 'Missing component: '+component)
    groups = [(tuple(f'v09-d{i}' for i in range(1, 9)), 5, 40),
              (tuple(f'v09-o{i}' for i in range(1, 5)), 5, 20),
              (tuple(f'v09-r{i}' for i in range(1, 7)), 10, 60)]
    groups += [(tuple(f'v09-{form}-q{n}{part}' for n in range(1, 6) for part in 'abcd'), 5, 100)
               for form in ('a', 'b')]
    for questions, points, total in groups:
        require(all(doc.points.get(k) == points for k in questions),
                'Missing questions or point values: '+questions[0])
        require(sum(doc.points[k] for k in questions) == total, 'Assessment point total')
        require(all(doc.solutions.count(k) == 1 for k in questions),
                'Missing or repeated matched worked solution: '+questions[0])
    require(all(f'v09-c{i:02}.html' in doc.links for i in range(1, 13)),
            'Incomplete chapter routes')
    return {'status': 'passed',
            'assembly': 'Exact five-part assembly; 40 exam, eight diagnostic, four oral and six retention prompts with point values and uniquely matched list-item solutions; twelve chapter routes.',
            'support': support_check(), 'form_a': check_a(), 'form_b': check_b(),
            'project': check_project()}


if __name__ == '__main__':
    print(json.dumps(check(), indent=2, allow_nan=False))
