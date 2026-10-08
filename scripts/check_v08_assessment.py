"""Independent support arithmetic and exact assembly of the Volume 8 package.

Full prompt/solution, source-scope and teaching audits are recorded separately.
These finite checks do not establish real market values or browser visual QA.
"""
from fractions import Fraction as F
from html.parser import HTMLParser
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARTS = ('v08-support-opening.html', 'v08-exam-a.html', 'v08-exam-b.html',
         'v08-project.html', 'v08-support-closing.html')


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
        if 'data-points' in a:
            self.points[a.get('id')] = int(a['data-points'])
        if 'data-solution-for' in a:
            self.solutions.append(a['data-solution-for'])
        if tag == 'a':
            self.links.append(a.get('href', ''))


def support_check():
    profit = 250-200
    margin = F(profit, 250)
    require((profit, margin, F(profit, 25), F(1, 4)-margin,
             F(1, 4)/margin-1) == (50, F(1, 5), 2, F(1, 20), F(1, 4)),
            'D1 units/margin/share scaling')
    pv2, pv1 = F(121)/F(11, 10)**2, F(105)/F(11, 10)
    require((pv2, pv1, pv2-pv1) == (100, F(1050, 11), F(50, 11)),
            'D2 dated values')
    ar, ap = 20+160-140, 10+80-75
    income = 160-80-30-10
    direct = 140-75-30
    indirect = income+10-(ar-20)+(ap-10)
    require((income, ar, ap, direct, indirect) == (40, 40, 15, 35, 35),
            'D3 receivable/payable cash reconciliation')
    require((120+30, 70+30, 120-70) == (150, 100, 50)
            and (150-2)-100 == 48, 'D4 borrowing and expensed fee')
    debt = [min(x, 100) for x in (70, 130)]
    equity = [max(x-100, 0) for x in (70, 130)]
    require(debt == [70, 100] and equity == [0, 30]
            and F(sum(debt), 2) == 85 and F(sum(equity), 2) == 15
            and all(d+e == x for d, e, x in zip(debt, equity, (70, 130))),
            'D5 terminal claims and conservation')
    observations = [(F(-1), F(0)), (F(1), F(4))]
    ex, ey = [sum(p[j] for p in observations)/2 for j in range(2)]
    var = sum((x-ex)**2 for x, _ in observations)/2
    cov = sum((x-ex)*(y-ey) for x, y in observations)/2
    require((ex, ey, var, cov, cov/var) == (0, 2, 1, 2, 2),
            'D6 covariance and projection')
    draw = max(0, 5-(14-20))
    monday = 14+min(draw, 8)-20
    require((draw, monday, 5-monday, monday+16) == (11, 2, 3, 18),
            'D7 dated reserve rather than an unlimited financing plug')

    # Oral transfer: keep physical capital growth fixed, not reinvestment ratio.
    oral = []
    for tax in (F(1, 4), F(1, 5)):
        nopat = 32*(1-tax)
        reinvestment = F(3, 100)*200
        roic = nopat/200
        fcff = nopat-reinvestment
        value = fcff/(F(9, 100)-F(3, 100))
        oral.append((nopat, roic, reinvestment/nopat, fcff, value))
    require(oral == [(24, F(3, 25), F(1, 4), 18, 300),
                     (F(128, 5), F(16, 125), F(15, 64), F(98, 5), F(980, 3))],
            'O1 coupled tax/ROIC/reinvestment change')
    require(24-7-1-10 == 6 and 24-7-1-4-10 == 2
            and 440+180+30 == (440+30-(220-180))+220 == 650
            and 180+30 == 210, 'O2/O3 liquidity and premium allocation')

    # R1 start from taxable operating profit, then recover the actual NWC.
    cash = (36-20)*(1-F(1, 4))+20
    initial = 40+6+4
    value = cash/F(6, 5)+(cash+6)/F(6, 5)**2-initial
    require((cash, initial, cash+6, value) == (32, 50, 38, F(55, 18))
            and value < 5, 'R1 complete project and exclusive choice')
    # R2 reconstruct required capital growth and bridge all separate claims.
    terminal = []
    for roic in (F(3, 25), F(3, 50)):
        reinvestment = 24*F(3, 100)/roic
        fcff = 24-reinvestment
        operating = fcff/(F(9, 100)-F(3, 100))
        common = operating+12+8-80-10
        terminal.append((reinvestment, fcff, operating, common, common/10))
    require(terminal == [(6, 18, 300, 230, 23), (12, 12, 200, 130, 13)],
            'R2 terminal capital and common-equity bridge')
    interest = 60*F(1, 20)
    shield = sum(interest*F(1, 4)/F(21, 20)**t for t in (1, 2))
    funded_cash = 24-7-1
    payout = funded_cash-10
    equity_before = 160+shield+funded_cash-60
    equity_after = 160+shield+10-60
    require((shield, payout, equity_before, equity_after) ==
            (F(205, 147), 6, F(17257, 147), F(16375, 147))
            and equity_after+payout == equity_before,
            'R3 shield, immediate outlays and payout wealth')
    state_prices = (F(3, 5), F(3, 10))
    gross_assets = (130, 50)
    forced = [x-80 for x in gross_assets]
    selected = [max(x, 0) for x in forced]
    option = sum(q*c for q, c in zip(state_prices, selected))
    commitment = sum(q*c for q, c in zip(state_prices, forced))
    discount = sum(state_prices)
    shortcut = discount*(F(1, 5)*selected[0]+F(4, 5)*selected[1])
    require((option, commitment, option-commitment, discount, shortcut) ==
            (30, 21, 9, F(9, 10), 9)
            and tuple(q/discount for q in state_prices) == (F(2, 3), F(1, 3)),
            'R4 explicit state prices and choice menu')
    combined = 360+120+40
    price = F(combined, 18+6)
    max_issue = F(18*combined, 360)-18
    require((price, 18*price-360, 6*price-120, max_issue) ==
            (F(65, 3), 30, 10, 8), 'R5 stock consideration and participation')
    venture = []
    for cash_exit in (1000, 3000):
        preferred = max(min(500, cash_exit), F(500, 2500)*cash_exit)
        venture.append((preferred, cash_exit-preferred))
    require(venture == [(500, 500), (600, 2400)], 'R5 preferred election')
    deficiency = 70-50
    recovery = F(40, deficiency+60)
    liquidation = (50+deficiency*recovery, 60*recovery)
    available_old = 110-F(21, 2)
    proposed = (F(70), available_old-70)
    proposed_pv = tuple(c/F(21, 20) for c in proposed)
    lower = liquidation[0]*F(21, 20)
    upper = available_old-liquidation[1]*F(21, 20)
    repaired = (F(68), available_old-68)
    repaired_pv = tuple(c/F(21, 20) for c in repaired)
    require(liquidation == (60, 30)
            and proposed_pv == (F(200, 3), F(590, 21))
            and sum(proposed_pv)-sum(liquidation) == F(100, 21)
            and (lower, upper) == (63, 68)
            and repaired_pv == (F(1360, 21), 30)
            and sum(repaired)+F(21, 2) == 110
            and all(n >= old for n, old in zip(repaired_pv, liquidation)),
            'R6 complete waterfall and nonempty participation interval')
    return {'status': 'passed', 'groups': 16,
            'scope': 'Seven diagnostic numerical items, oral financial transfers, six delayed reconstructions; evidence and instructional reasoning require separate editorial review.'}


def check():
    from check_v08_exam_a import check as check_a
    from check_v08_exam_b import check as check_b
    from check_v08_project import check as check_project
    assembled = (ROOT/'content/assessments/v08.html').read_text()
    expected = '\n\n'.join((ROOT/'content/assessments/parts'/name).read_text().strip()
                           for name in PARTS)+'\n'
    require(assembled == expected, 'Volume 8 assembly differs from reviewed parts')
    doc = Structure(); doc.feed(assembled)
    require(len(doc.ids) == len(set(doc.ids)), 'Duplicate assessment anchors')
    for component in ('diagnostic', 'exam-rules', 'form-a', 'solutions-a', 'form-b',
                      'solutions-b', 'project', 'oral-transfer', 'retention',
                      'notation-index', 'concept-index', 'volume-synthesis'):
        require(component in doc.ids, 'Missing component: '+component)
    require(all(f'v08-d{i}' in doc.ids for i in range(1, 9)), 'Diagnostic incomplete')
    require(all(f'v08-r{i}' in doc.ids for i in range(1, 7)), 'Retention incomplete')
    for form in ('a', 'b'):
        questions = {f'v08-{form}-q{n}{part}' for n in range(1, 6) for part in 'abcd'}
        require(all(doc.points.get(k) == 5 for k in questions), 'Exam points incomplete')
        require(sum(doc.points[k] for k in questions) == 100, 'Exam total')
        require(all(doc.solutions.count(k) == 1 for k in questions),
                'Missing or repeated matched worked solution')
    require(all(f'v08-c{i:02}.html' in doc.links for i in range(1, 13)),
            'Incomplete chapter routes')
    return {'status': 'passed',
            'assembly': 'Exact five-part assembly, 40 matched five-point subparts, 12 chapter routes',
            'support': support_check(), 'form_a': check_a(), 'form_b': check_b(),
            'project': check_project()}


if __name__ == '__main__':
    print(json.dumps(check(), indent=2, allow_nan=False))
