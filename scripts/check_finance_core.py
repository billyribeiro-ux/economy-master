"""Exact finance-core support contracts and final component integration."""
from fractions import Fraction as F
from html.parser import HTMLParser
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
PARTS = ('finance-core-support-opening.html', 'finance-core-exam-a.html',
         'finance-core-exam-b.html', 'finance-core-project.html',
         'finance-core-support-closing.html')
SUPPORT = ('content/cross-assessments/parts/'+PARTS[0],
           'content/cross-assessments/parts/'+PARTS[-1],
           'scripts/check_finance_core.py', 'content/reviews/finance-core-support-sources.json')


def require(condition, label):
    if not condition:
        raise ValueError('Finance core: '+label)


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []; self.ids = []; self.points = {}; self.answers = {}
        self.targets = []; self.links = []; self.h1 = 0; self.active = None
        self.answer_depth = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if 'id' in a:
            self.ids.append(a['id'])
        if tag == 'h1':
            self.h1 += 1
        if tag == 'a':
            self.links.append(a.get('href', ''))
        if tag == 'li' and 'data-points' in a:
            require(a.get('id') and a['id'] not in self.points, 'unique scored prompt')
            self.points[a['id']] = int(a['data-points'])
        if 'data-solution-for' in a:
            require(self.active is None, 'non-nested answer')
            self.active = a['data-solution-for']; self.targets.append(self.active)
            self.answers[self.active] = ''
            self.answer_depth = len(self.stack) + 1
        if tag not in ('br', 'hr', 'img', 'input', 'meta', 'link'):
            self.stack.append(tag)

    def handle_endtag(self, tag):
        require(self.stack and self.stack[-1] == tag, 'balanced HTML '+tag)
        if len(self.stack) == self.answer_depth:
            self.active = None
            self.answer_depth = 0
        self.stack.pop()

    def handle_data(self, value):
        if self.active is not None:
            self.answers[self.active] += value


def support_check():
    comparisons = 0
    def eq(actual, expected, label):
        nonlocal comparisons
        comparisons += 1
        require(actual == expected, label+': '+repr(actual)+' != '+repr(expected))
    p = Page()
    for name in (PARTS[0], PARTS[-1]):
        p.feed((ROOT/'content/cross-assessments/parts'/name).read_text())
        require(not p.stack, 'complete support fragment')
    def printed(key, *values):
        for value in values:
            eq(value in p.answers['finance-core-'+key], True, 'printed '+key+' '+value)

    # Independent cash identities reconcile the accrual routes to actual receipts.
    eq(15+100-80, 35, 'D1 gross AR bridge')
    eq((100-55-10, 80-55, 12+80-55-20+8-5), (35, 25, 20), 'D1 income and cash')
    eq(35+10-(35-15), 80-55, 'D1 indirect/direct equality')
    printed('d1', 'Income 35', 'operating cash 25', 'closing cash 20')
    eq(40*F(3, 4)+8-15-5, 18, 'D2 unlevered FCFF')
    eq(180+10-50, 140, 'D2 exact claim bridge')
    printed('d2', 'FCFF 18', 'equity value 140', 'single observed 18')
    r = F(88+4, 80)-1
    eq((r, 60*(1+r), 40*F(19, 20)), (F(3, 20), 69, 38), 'D3 funded returns')
    eq((69+38-100)/F(100), F(7, 100), 'D3 no doubled dividend')
    printed('d3', '15%', '69 and 38', '7%')
    eq((20*F(2, 5), 20*F(7, 10), 1/(F(2, 5)+F(1, 2))),
       (8, 14, F(10, 9)), 'D4 state prices and frequencies')
    printed('d4', 'Price 8', 'payoff 14', '10/9')
    eq((5*F(24, 25)+105*F(9, 10), F(24, 25)/F(9, 10)-1),
       (F(993, 10), F(1, 15)), 'D5 dated prices and reinvestment')
    printed('d5', '99.3', '1/15', '16/15')
    delta = F(15, 65-40); bank = -40*delta/F(21, 20)
    eq((delta, bank, 50*delta+bank), (F(3, 5), -F(160, 7), F(50, 7)), 'D6 complete initial hedge')
    for stock in (65, 40):
        eq(delta*stock+bank*F(21, 20), max(stock-50, 0), 'D6 actual state cash')
    eq((50*F(21, 20)-40)/25, F(1, 2), 'D6 implied pricing weight')
    printed('d6', '3/5', '−160/7', '50/7', 'q=1/2')
    eq((9-4, 4+5-9, 12-F(11, 2)), (5, 0, F(13, 2)), 'D7 each actual deadline')
    printed('d7', 'gap five', '6.5', 'not another twelve of revenue')
    continuation = 12*F(51, 50)/(F(2, 25)-F(1, 50))
    eq((continuation, (12+continuation)/F(27, 25)), (204, 200), 'D8 after-payment continuation')
    eq(F(51, 54)<1, True, 'D8 convergent geometric ratio')
    printed('d8', '204', '200', '12.24', 'included once')

    # Oral transfer: new information, actual implementation and a full positive
    # pricing family, not tests of memorizing the earlier diagnostic answers.
    means = [p*120+(1-p)*60 for p in (F(4, 5), F(1, 5))]
    eq(means, [108, 72], 'O2 changed physical means')
    eq(F(3, 10)*120+F(3, 5)*60, 72, 'O2 unchanged traded prices')
    printed('o2', '108', '72', 'numerical coincidence')
    eq(98*F(11, 10), F(539, 5), 'O3 maximum net funded wealth')
    eq((98*F(11, 10)-100)/100, F(39, 500), 'O3 expected return on original resources')
    printed('o3', '107.8', '7.8%', 'infeasible')
    for a in (F(1, 10), F(1, 4), F(2, 5)):
        pi = (a, 1-2*a, a)
        eq(sum(pi), 1, 'O4 bank quote')
        eq(sum(x*y for x, y in zip(pi, (100, 80, 60))), 80, 'O4 stock quote')
        eq(min(pi)>0, True, 'O4 strictly positive extension')
        eq(sum(x*y for x, y in zip(pi, (20, 0, 0))), 20*a, 'O4 nonunique call price')
    eq(F(1, 2)*80-30, 10, 'O4 unhedged middle state')
    printed('o4', '20,10,0', '20,0,0', '(0,10)', 'nonreplication')
    printed('o1', 'does not change its collection date', 'new cost, recourse and rights')
    printed('o5', 'payment is missed', 'Noon receipt cannot undo')

    income = 130-60-10-6
    direct = 110-60
    eq((40-6, income, direct), (34, 54, 50), 'R1 net AR, income, direct cash')
    eq(income+10+6-(40-20), direct, 'R1 gross-AR bridge')
    eq(income+10-(34-20), direct, 'R1 net-AR bridge')
    eq((direct-25, 10+direct-25+5-15), (25, 25), 'R1 FCFF and closing cash')
    eq(income+10+6-(34-20), 56, 'R1 actual double-counting counterexample')
    printed('r1', 'income 54', 'operating cash 50', 'FCFF 25', 'incorrectly produce 56')
    prices = (F(3, 10), F(3, 5)); assets = (120, 60)
    debts = [min(80, x) for x in assets]; equities = [max(0, x-80) for x in assets]
    for asset, debt, equity in zip(assets, debts, equities):
        eq(debt+equity, asset, 'R2 statewise full claim allocation')
    price = lambda values: sum(p*x for p, x in zip(prices, values))
    eq((price(assets), price(debts), price(equities)), (72, 60, 12), 'R2 values of different claims')
    eq((62-price(debts), price(equities)-(62-price(debts))), (2, 10), 'R2 own funded contribution and NPV')
    eq((70-price(debts), 5-(62-price(debts))), (10, 3), 'R2 outside providers retain unspent endowments')
    eq(5-(62-price(debts))+price(equities)-5, 10, 'R2 investor total wealth gain')
    eq(F(4, 5)*80+F(1, 5)*60, 76, 'R2 physical debt payment differs from proceeds')
    printed('r2', 'debt proceeds 60', 'equity value 12', 'NPV ten', 'available acquisition')
    variance = lambda w: F(1, 100)*w*w+F(1, 25)*(1-w)**2+F(1, 100)*w*(1-w)
    eq(F(1, 100)*F(1, 25)-F(1, 200)**2, F(3, 8000), 'R3 positive covariance determinant')
    for w in (F(0), F(1, 2), F(7, 8), F(1)):
        eq(variance(w), F(1, 25)*(w-F(7, 8))**2+F(3, 320), 'R3 completed-square identity')
    eq((variance(F(7, 8)), F(1, 10)-F(1, 25)*F(7, 8)), (F(3, 320), F(13, 200)), 'R3 unconstrained optimum')
    eq((variance(F(1, 2)), F(1, 10)-F(1, 25)*F(1, 2)), (F(3, 200), F(2, 25)), 'R3 constrained optimum')
    eq(F(2, 25)*F(1, 2)-F(7, 100)<0, True, 'R3 derivative negative throughout target interval')
    printed('r3', 'w=7/8', '[0,1/2]', 'w=1/2', '3/200', '3/8000')
    for stock in (100, 60):
        eq(F(1, 2)*stock-30-max(stock-80, 0), 0, 'R4 original stock/debt/option net cash')
    terminal = lambda x: 5-F(26, 25)*(5-x)
    threshold = F(5, 26)
    eq(terminal(0), -F(1, 5), 'R4 no-charge funding loss')
    eq((terminal(threshold), 5-threshold, 10+threshold), (0, F(125, 26), F(265, 26)), 'R4 exact funded equality')
    eq(terminal(threshold-F(1, 1000))<0, True, 'R4 smaller retained charge fails')
    eq(0<5-threshold<=5 and 10+threshold<=15, True, 'R4 distinct provider and buyer endowments')
    printed('r4', '5/26', '125/26', '265/26', 'private break-even')
    recover = F(1, 2)*(20-3)
    gap = 36-(4+20+3)
    eq((3+recover, 4+20+3+recover, gap, gap*F(21, 20)-recover),
       (F(23, 2), F(71, 2), 9, F(19, 20)), 'R5 recovery, timing and late deficit')
    grant = F(19, 21); bridge = 9-grant
    eq((bridge, bridge*F(21, 20)), (F(170, 21), recover), 'R5 equality allocation')
    eq(0<=grant<=1 and 0<=bridge<=9, True, 'R5 actual endowed menus')
    for g, extra in ((grant, F(0)), (grant-F(1, 1000), F(0)), (F(1), F(1, 2))):
        debt = 9-g+extra
        first = 27+g+debt-36
        last = first+recover-F(21, 20)*debt
        eq(last, F(21, 20)*g-F(19, 20)-extra/F(20), 'R5 retaining extra debt never improves final feasibility')
    printed('r5', '19/21', '170/21', '0.95', 'below the donor’s one-H capacity')

    eq(len(p.ids), len(set(p.ids)), 'unique support anchors')
    eq(p.h1, 1, 'sole cumulative heading')
    for prefix, n, points in [('finance-core-d', 8, 5), ('finance-core-o', 5, 4), ('finance-core-r', 5, 10)]:
        eq({k: v for k, v in p.points.items() if k.startswith(prefix)},
           {prefix+str(i): points for i in range(1, n+1)}, 'scored '+prefix)
    eq(sorted(p.targets), sorted(p.points), 'every exact prompt solved once')
    for key in ('administration', 'coverage', 'diagnostic', 'oral-transfer', 'retention',
                'notation-index', 'concept-index', 'finance-core-synthesis'):
        eq(key in p.ids, True, 'required anchor '+key)
    source = json.loads((ROOT/SUPPORT[-1]).read_text())
    eq((source['proposals'], source['reused_source_ids']), ([], []), 'no new external claim')
    expected = {f'v{v:02}-c{c:02}' for v in range(7, 12) for c in range(1, 13)}
    eq({x['chapter'] for x in source['method_routes']}, expected, 'sixty accepted method routes')
    eq(len(source['method_routes']), 60, 'no duplicate method route')
    for row in source['method_routes']:
        eq(row['manuscript'], 'chapters/'+row['chapter']+'.html', 'canonical route spelling')
    bindings = 0
    audit = ROOT/'content/reviews/finance-core-support-author.json'
    if audit.exists():
        rows = json.loads(audit.read_text())['reviewed_hashes']
        eq({x['path'] for x in rows}, set(SUPPORT), 'four nonself author bindings')
        eq(len(rows), 4, 'no duplicate binding')
        for row in rows:
            raw = (ROOT/row['path']).read_bytes()
            eq((len(raw), hashlib.sha256(raw).hexdigest()), (row['bytes'], row['sha256']), 'frozen '+row['path'])
            bindings += 1
    result = dict(status='passed', component='finance-core-support', comparisons=comparisons,
                  diagnostic_items=8, diagnostic_points=40, oral_transfers=5, oral_points=20,
                  retention_items=5, retention_points=50, method_routes=60, author_nonself_bindings=bindings,
                  limits='Original conditional contracts; proof/prompt review separate. No calibrated timing, current legal authority, learner achievement, human certification or rendered QA.')
    json.dumps(result, allow_nan=False)
    return result


def check():
    result = support_check()
    require(result['author_nonself_bindings'] == 4, 'complete support record')
    bodies = [(ROOT/'content/cross-assessments/parts'/p).read_text().strip() for p in PARTS]
    actual = (ROOT/'content/cross-assessments/finance-core.html').read_text()
    require(actual == '\n\n'.join(bodies)+'\n', 'exact five-part final assembly')
    page = Page(); page.feed(actual)
    require(not page.stack and page.h1 == 1 and len(page.ids) == len(set(page.ids)), 'whole-page structure')
    transfers = {'finance-core-project-t'+str(i) for i in range(1, 7)}
    require(page.active is None and len(page.points) == 55 and set(page.answers) == set(page.points) | transfers,
            'complete cumulative prompt and answer pairing')
    from check_finance_core_exam_a import check as a
    from check_finance_core_exam_b import check as b
    from check_finance_core_project import check as project
    from check_finance_core_exam_a_peer import check as peer_a
    from check_finance_core_exam_b_peer import check as peer_b
    from check_finance_core_project_peer import check as peer_project
    from check_finance_core_support_peer import check as peer_support
    result['component_checks'] = {name: f() for name, f in [('exam_a_author', a), ('exam_b_author', b),
        ('project_author', project), ('exam_a_peer', peer_a), ('exam_b_peer', peer_b),
        ('project_peer', peer_project), ('support_peer', peer_support)]}
    result['assembly_parts'] = list(PARTS)
    return result


if __name__ == '__main__':
    print(json.dumps(support_check() if '--support-only' in sys.argv else check(), indent=2, allow_nan=False))
