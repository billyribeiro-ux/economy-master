"""Exact original-contract arithmetic and structure for Volume 11 Form A."""
import argparse
from fractions import Fraction as F
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
PAYLOADS = ['content/assessments/parts/v11-exam-a.html',
            'scripts/check_v11_exam_a.py', 'content/reviews/v11-exam-a-sources.json']


class Exam(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack, self.ids, self.targets = [], [], []
        self.points, self.questions, self.answers = {}, {}, {}
        self.active = None
        self.tables = []
        self.table = self.row = self.cell = None
        self.in_caption = False
        self.h1 = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if 'id' in a:
            self.ids.append(a['id'])
        if tag == 'h1':
            self.h1 += 1
        if tag == 'li' and 'data-points' in a:
            if a['id'] in self.points:
                raise RuntimeError('duplicate scored prompt')
            self.points[a['id']] = int(a['data-points'])
            self.questions[a['id']] = ''
            self.active = (self.questions, a['id'])
        if 'data-solution-for' in a:
            ident = a['data-solution-for']
            self.targets.append(ident)
            self.answers[ident] = ''
            self.active = (self.answers, ident)
        if tag == 'table':
            self.table = dict(caption='', rows=[])
            self.tables.append(self.table)
        if tag == 'caption':
            self.in_caption = True
        if tag == 'tr':
            self.row = []
            self.table['rows'].append(self.row)
        if tag in ('th', 'td'):
            self.cell = ''
        if tag not in ('br', 'hr', 'img', 'input', 'link', 'meta'):
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if not self.stack or self.stack.pop() != tag:
            raise RuntimeError('unbalanced exam HTML: '+tag)
        if tag == 'li':
            self.active = None
        if tag in ('th', 'td'):
            self.row.append(self.cell.strip())
            self.cell = None
        if tag == 'caption':
            self.in_caption = False
        if tag == 'table':
            self.table = None

    def handle_data(self, text):
        if self.active is not None:
            mapping, ident = self.active
            mapping[ident] += text
        if self.in_caption:
            self.table['caption'] += text
        if self.cell is not None:
            self.cell += text


def check(root=None):
    root = Path(root) if root is not None else Path(__file__).resolve().parents[1]
    counts = dict(comparisons=0, cases=5, scored_subparts=18, points=100,
                  financial_boundaries=0, funded_state_allocations=0,
                  author_payload_hashes_verified=0)

    def need(ok, label):
        counts['comparisons'] += 1
        if not ok:
            raise RuntimeError(label)

    def eq(actual, expected, label):
        need(actual == expected, label+': '+repr(actual)+' != '+repr(expected))

    raw = (root/PAYLOADS[0]).read_text()
    page = Exam()
    page.feed(raw)

    def printed(part, *tokens):
        for token in tokens:
            need(token in page.answers['v11-a-q'+part], part+' printed solution '+token)

    def balance(values, label):
        eq(sum(values[:3]), sum(values[3:]), label+' accounting identity')

    # Q1: integrate all applicant states; a test is purchased in every state.
    prior = {'G': F(2, 3), 'B': F(1, 3)}
    pass_given = {'G': F(3, 4), 'B': F(1, 4)}
    receipts = {'G': F(24), 'B': F(8)}
    principal, fee = F(20), F(2, 5)
    states = [(kind, passed, prior[kind]*(pass_given[kind] if passed else 1-pass_given[kind]))
              for kind in prior for passed in (True, False)]
    eq(sum(p for _, _, p in states), 1, 'Q1 applicant state mass')
    prob_pass = sum(p for _, passed, p in states if passed)
    passed_good = sum(p for kind, passed, p in states if kind == 'G' and passed)
    accepted_receipt = sum(p*receipts[kind] for kind, passed, p in states if passed)/prob_pass
    gain = sum(p*((receipts[kind]-principal if passed else 0)-fee) for kind, passed, p in states)
    unscreened = sum(prior[k]*(receipts[k]-principal) for k in prior)
    eq((prob_pass, passed_good/prob_pass, accepted_receipt, gain, unscreened),
       (F(7, 12), F(6, 7), F(152, 7), F(3, 5), F(-4, 3)), 'Q1 original screening contract')
    eq(round(float(accepted_receipt), 6), 21.714286, 'Q1 rounded conditional receipt')
    eq(accepted_receipt-principal, F(12, 7), 'Q1 conditional loan margin')
    eq(prob_pass*(accepted_receipt-principal), 1, 'Q1 gross applicant margin')
    need(gain > 0 > unscreened, 'Q1 rejection comparison')
    # Break-even testing fee is one, holding only the screening policy fixed.
    eq(gain+fee-1, 0, 'Q1 break-even test cost')
    need(gain+fee-F(11, 10) < 0, 'Q1 cost increase can reverse screen value')
    counts['financial_boundaries'] += 2
    printed('1a', '7/12', '6/7', '152/7≈21.714286 CU', '3/5 CU', '−4/3', 'failed as well as passed')

    # Transaction vectors are independent of the printed ledger, which is then compared.
    row = list(map(F, [6, 54, 20, 60, 10, 10]))
    advance = F(12)-(row[0]-fee)
    eq(advance, F(32, 5), 'Q1 minimum actually funded advance')
    need(advance <= 7, 'Q1 external provider capacity')
    eq(7-advance, F(3, 5), 'Q1 provider remaining cash')
    events = [(-fee, 0, 0, 0, 0, -fee), (0, 20, 0, 20, 0, 0),
              (advance, 0, 0, 0, advance, 0), (-12, 0, 0, -12, 0, 0)]
    ledger = []
    for event in events:
        row = [value+delta for value, delta in zip(row, event)]
        balance(row, 'Q1 event')
        ledger.append(row[:])
    eq(row, [0, 74, 20, 68, F(82, 5), F(48, 5)], 'Q1 closing inventory')
    eq((sum(row[:3]), sum(row[3:5])), (94, F(422, 5)), 'Q1 closing totals')
    table = next(t for t in page.tables if t['caption'] == 'One passed applicant: complete bank ledger')
    eq([[F(value) for value in line[1:]] for line in table['rows'][1:]], ledger, 'Q1 printed full ledger')
    eq(20-12, 8, 'Q1 retained deposit before internal input purchase')
    need('changes deposit ownership but neither aggregate bank deposits nor cash' in page.questions['v11-a-q1c'],
         'Q1 residual deposit is accounted for before the external service receipt')
    need('service cash now arrives from outside this bank' in page.questions['v11-a-q1c'], 'Q1 actual repayment route')
    printed('1b', '32/5=6.4', '94', '422/5=84.4', '48/5=9.6', 'due at date 3')
    contractual_gap = 24-receipts['B']
    write_down = principal-receipts['B']
    equity = row[5]-write_down
    eq((receipts['B']/24, contractual_gap, write_down, equity),
       (F(1, 3), 16, 12, F(-12, 5)), 'Q1 debt service versus principal impairment')
    eq(contractual_gap-write_down, 4, 'Q1 unrecognized promised interest')
    balance([0, F(74)-write_down, 20, 68, F(82, 5), equity], 'Q1 loss recognition')
    balance([8, F(74)-20, 20, 68, F(82, 5), equity], 'Q1 external recovery replaces the written asset')
    printed('1c', '1/3', 'sixteen', 'twelve', '−12/5=−2.4', 'remains a legal claim', 'not a second')

    # Q2: integrate the quantile over exactly the upper quarter.
    law = [(0, F(11, 20)), (4, F(3, 10)), (24, F(3, 20))]
    cumulative, integral, tail_mass, quantile = F(0), F(0), F(0), None
    pieces = []
    alpha = F(3, 4)
    for loss, probability in law:
        lower, upper = cumulative, cumulative+probability
        if quantile is None and upper >= alpha:
            quantile = loss
        mass = max(F(0), upper-max(lower, alpha))
        pieces.append(mass)
        tail_mass += mass
        integral += loss*mass
        cumulative = upper
    eq((quantile, pieces, tail_mass, integral/tail_mass),
       (4, [0, F(1, 10), F(3, 20)], F(1, 4), 16), 'Q2 partial-atom ES')
    all_boundary_mean = sum(l*p for l, p in law if l >= 4)/sum(p for l, p in law if l >= 4)
    eq(all_boundary_mean, F(32, 3), 'Q2 full-atom conditional mean')
    printed('2a', '=4', '=16', 'ten of the thirty percentage points', 'one third', '32/3')
    eligible, price, haircut, lender_cash = 12-4, F(9, 10), F(1, 4), F(6)
    cap = min(eligible*price*(1-haircut), lender_cash)
    eq(cap, F(27, 5), 'Q2 eligible inventory and actual lender cash')

    def cash(contribution, draw):
        first = 5+contribution+draw+2-13
        second = first+10-6-F(11, 10)*draw
        return first, second

    b_star, x_star = F(40, 11), F(26, 11)
    eq(cash(x_star, b_star), (0, 0), 'Q2 both cash constraints bind')
    need(b_star <= cap, 'Q2 optimal draw inside real capacity')
    eq(F(11, 10)*b_star, 4, 'Q2 complete later principal and interest')
    # A positive combination of the two inequalities certifies a global lower bound.
    first_weight, second_weight = F(1, 11), F(10, 11)
    eq(first_weight+second_weight, 1, 'Q2 dual contribution coefficient')
    eq(first_weight-second_weight/F(10), 0, 'Q2 dual borrowing cancellation')
    eq(first_weight*6+second_weight*2, x_star, 'Q2 global contribution certificate')
    eq(cash(F(3, 5), cap), (0, F(-97, 50)), 'Q2 maximum draw with early-only topup fails later')
    eq(F(2)+cap/10, F(127, 50), 'Q2 maximum-draw feasible contribution')
    need(F(127, 50) > x_star, 'Q2 maximum borrowing costs more outside capital')
    eq(round(float(x_star), 6), 2.363636, 'Q2 printed contribution precision')
    for maximum, expected in [(F(0), F(6)), (F(3), F(3)), (b_star, x_star), (cap, x_star)]:
        candidates = [F(0), maximum]
        if b_star <= maximum:
            candidates.append(b_star)
        best = min(max(6-b, 2+b/10) for b in candidates)
        eq(best, expected, 'Q2 capacity-boundary vertex oracle')
        counts['financial_boundaries'] += 1
    need(cash(x_star-F(1, 100), b_star)[0] < 0 and cash(x_star-F(1, 100), b_star)[1] < 0,
         'Q2 one cent less cannot fund this intersection')
    counts['financial_boundaries'] += 1
    printed('2b', '27/5=5.4', 'x+b−6', 'x−2−b/10', 'Principal received earlier must be returned')
    printed('2c', '40/11', '26/11≈2.363636', '−97/50=−1.94', '127/50', 'global minimality')
    eq((5+2+6-13, 5+2+6-13+10-6), (0, 4), 'Q2 delayed facility feasible zero-draw policy')
    need(5+2+F(599, 100)-13 < 0, 'Q2 less early capital fails with delayed facility')
    counts['financial_boundaries'] += 1
    printed('2d', 'x≥6', 'zero, then four', 'none is required')

    # Q3: settle each instruction against the named outstanding obligation.
    owing = {'r': F(7), 's': F(5), 't': F(8)}
    instructions = [('r', F(7)), ('r', F(5)), ('t', F(8))]
    sent, valid, excess = F(0), F(0), F(0)
    for ident, amount in instructions:
        discharge = min(owing[ident], amount)
        owing[ident] -= discharge
        sent += amount
        valid += discharge
        excess += amount-discharge
    recovery = F(3)
    cash_left = 22-sent
    liabilities = 90-valid
    assets = cash_left+80+recovery
    eq((sent, valid, excess, owing), (20, 15, 5, {'r': 0, 's': 5, 't': 0}), 'Q3 identity-aware discharge')
    eq((cash_left, assets, liabilities, assets-liabilities, excess-recovery, owing['s']-cash_left),
       (2, 85, 75, 10, 2, 3), 'Q3 loss, retained claims and deadline')
    need(cash_left < owing['s'] and cash_left+recovery == owing['s'], 'Q3 eventual resources do not imply timely access')
    printed('3a', 'twenty', 'fifteen', '85', '75', 'three', 'Deleting s would overstate equity by five')
    state_losses = [(0, 1, 0), (7, 2, 2), (2, 8, 0)]
    stress_table = next(t for t in page.tables if t['caption'] == 'Three complete supported stress states')
    eq([tuple(int(x) for x in line[1:]) for line in stress_table['rows'][1:]], state_losses, 'Q3 printed original state inventory')
    eq(list(map(sum, state_losses)), [1, 11, 10], 'Q3 sum within states')
    eq(12-max(map(sum, state_losses)), 1, 'Q3 worst-state marked equity')
    eq(sum(max(row[j] for row in state_losses) for j in range(3)), 17, 'Q3 impossible component-max combination')
    incorrect = (7+2)+2+5
    eq((incorrect, incorrect-sum(state_losses[1])), (16, 5), 'Q3 gross/net repeated attribution')
    eq((assets-7-2)-liabilities, 1, 'Q3 incident book reconciles with stress loss')
    printed('3b', 'one, eleven and ten', 'seventeen', 'sixteen', 'overstatement of five', 'not another asset loss')
    printed('3c', 'immutable obligation register', 'shared identity/authorization service', 'three achievements', 'trigger')

    # Q4: square-root certainty equivalents are exact here, avoiding numerical ties.
    wealth, loss, premium, capital = F(100), F(36), F(10), F(26)
    risks = [F(1, 10), F(2, 5)]
    thresholds, participation = [], []
    for risk in risks:
        utility = (1-risk)*10+risk*8
        certainty_equivalent = utility**2
        limit = wealth-certainty_equivalent
        thresholds.append(limit)
        participation.append(wealth-premium > certainty_equivalent)
    eq((thresholds, participation), ([F(99, 25), F(384, 25)], [False, True]), 'Q4 private type participation')
    selected_profit = premium-risks[1]*loss
    pooled_profit = premium-F(sum(risks), 2)*loss
    eq((selected_profit, pooled_profit), (F(-22, 5), 1), 'Q4 selected versus original population')
    insurer_profit_states = []
    for claim in (F(0), loss):
        closing = capital+premium-claim
        need(closing >= 0, 'Q4 fully endowed policy state')
        eq(closing+claim, capital+premium, 'Q4 policy cash conservation')
        insurer_profit_states.append(closing-capital)
        counts['funded_state_allocations'] += 1
    eq(insurer_profit_states, [10, -26], 'Q4 owner profit relative to initial capital')
    eq((1-risks[1])*insurer_profit_states[0]+risks[1]*insurer_profit_states[1], selected_profit,
       'Q4 expected unprofitability with full claim performance')
    printed('4a', '40p−4p²', '99/25=3.96', '384/25=15.36', 'only the high type buys', 'entry equilibrium')
    printed('4b', '−22/5=−4.4', 'profit one', '36 cash', '−26 or ten')
    for spot, expected in [(F(2), (16, 12, 4, 4, 16, 8, 28)), (F(3), (24, 12, 12, 4, 16, 8, 40))]:
        converted_f = min(F(12), F(8))
        converted_h = spot*converted_f
        transferred = min(F(12), converted_h)
        onshore_h, onshore_f = converted_h-transferred, 12-converted_f
        offshore = 4+transferred
        total = offshore+onshore_h+spot*onshore_f
        eq((converted_h, transferred, onshore_h, onshore_f, offshore, 24-offshore, total), expected, 'Q4 H/F location ledger')
        eq(total, 12*spot+4, 'Q4 currency conversion conserves translated resources')
        need(total > 24 and offshore < 24, 'Q4 positive translated net worth fails payment access')
        counts['funded_state_allocations'] += 1
    printed('4c', 'four H plus four F', 'sixteen H', 'eight H', '28 H', 'No partial payment')
    printed('4d', 'twelve H plus four F', 'forty H', 'gap is still eight H', 'binding outward-transfer cap')

    # Q5: optimize the private menu before analyzing a stipulated realized stress.
    routes = {'direct': {'profit': 4, 'reported': 8, 'lookthrough': 8},
              'routed': {'profit': 5, 'reported': 4, 'lookthrough': 18}}
    for field, expected in [('reported', 'routed'), ('lookthrough', 'direct')]:
        eligible_routes = [k for k, r in routes.items() if r[field] <= 10]
        best_routes = [k for k in eligible_routes if all(routes[k]['profit'] >= routes[j]['profit'] for j in eligible_routes)]
        eq(best_routes, [expected], 'Q5 perimeter changes private feasible choice')
    printed('5a', 'routed funding', 'direct funding', 'social welfare', 'anticipated continuing rescue')
    need('smallest quantity that covers' in raw and 'minimum is unique' in page.questions['v11-a-q5b'], 'Q5 explicit minimum-sale policy')
    revenue = lambda q: q*(1-q/16)
    for q in [F(0), F(399, 100), F(4), F(5), F(8)]:
        eq(4-revenue(q), (q-8)**2/16, 'Q5 exact revenue-maximum certificate')
        eq(revenue(q)-3, -(q-4)*(q-12)/16, 'Q5 assisted revenue factorization')
        need(revenue(q) <= 4, 'Q5 external buyer can finance the announced quantity')
    need(revenue(F(399, 100)) < 3 < revenue(F(5)), 'Q5 minimum differs from full feasible interval')
    counts['financial_boundaries'] += 2
    for advance, q, expected_price, margin, gap in [(F(0), F(8), F(1, 2), F(2), F(1)),
                                                  (F(1), F(4), F(3, 4), F(0), F(0))]:
        price = 1-q/16
        sales = revenue(q)
        eq(price, expected_price, 'Q5 uniform auction price')
        eq(2+advance+sales, 6, 'Q5 funded original creditor payment')
        need(advance <= 1 and sales <= 4, 'Q5 separate provider and buyer cash')
        required_margin = max(F(0), 6-8*price)
        eq((required_margin, max(F(0), required_margin-1)), (margin, gap), 'Q5 downstream collateral call')
        eq((8-q)+q, 8, 'Q5 sold and retained collateral inventories')
        counts['funded_state_allocations'] += 1
    # For the intervention, total external cash is conserved across A, buyer,
    # provider and the original creditor before any terminal collateral payoff.
    eq(2+4+1, 0+1+0+6, 'Q5 first-cutoff aggregate cash conservation')
    eq(F(4)-F(4)**2/32-revenue(F(4)), F(1, 2), 'Q5 integrating the schedule would invent proceeds')
    printed('5b', 'q=8', 'p=1/2', 'q=4', '3/4', 'payment-feasible set is [4,8]', 'four securities', 'uncovered need is one')

    face, principal = F(5, 4), F(1)
    expected_states = [(F(1), F(5, 4), F(1, 4), F(11, 4), F(0)),
                       (F(1, 5), F(4, 5), F(-1, 5), F(0), F(9, 20))]
    for unit, received, net, owner, shortfall in expected_states:
        available = 4*unit
        actual = min(available, face)
        eq((actual, actual-principal, available-actual, face-actual),
           (received, net, owner, shortfall), 'Q5 limited-recourse terminal allocation')
        eq(actual+owner, available, 'Q5 terminal security cash conservation')
        counts['funded_state_allocations'] += 1
    eq(F(9, 20), F(1, 5)+F(1, 4), 'Q5 principal loss versus contractual interest shortfall')
    printed('5c', '5/4', '11/4=2.75', '4/5', '1/5', '9/20=0.45', 'deficiency is discharged')

    limit = F(3, 20)
    minimum_escrow = 1-F(4, 5)-limit
    eq(minimum_escrow, F(1, 20), 'Q5 minimum external first-loss cash')
    for escrow in [F(0), F(49, 1000), F(1, 20), F(1, 10)]:
        worst_loss = F(0)
        for unit in (F(1), F(1, 5)):
            collateral = 4*unit
            base_receipt = min(face, collateral)
            support = min(escrow, face-base_receipt)
            final_receipt = base_receipt+support
            refund = escrow-support
            owner = collateral-base_receipt
            eq(final_receipt+refund+owner, collateral+escrow, 'Q5 separate escrow owner conservation')
            worst_loss = max(worst_loss, principal-final_receipt)
        eq(worst_loss <= limit, escrow >= minimum_escrow, 'Q5 hard loss-limit boundary')
        counts['financial_boundaries'] += 1
    eq(F(4, 5)+minimum_escrow, F(17, 20), 'Q5 supported bad-state receipt')
    need(F(1, 5) > limit, 'Q5 unsigned promise fails existing hard limit')
    printed('5d', 'δ*=1/20=0.05 CU', '17/20=0.85', 'Do not execute', 'Without actual escrow', 'revision')

    # Exact prompt, answer, point and source inventories; no future package files.
    expected_points = {'1a': 6, '1b': 8, '1c': 6, '2a': 5, '2b': 4, '2c': 7, '2d': 4,
                       '3a': 8, '3b': 6, '3c': 6, '4a': 6, '4b': 4, '4c': 6, '4d': 4,
                       '5a': 4, '5b': 7, '5c': 4, '5d': 5}
    wanted = {'v11-a-q'+part: points for part, points in expected_points.items()}
    eq(page.points, wanted, 'eighteen original scored subparts')
    eq(sum(page.points.values()), 100, 'total examination points')
    for question in range(1, 6):
        eq(sum(points for part, points in expected_points.items() if part.startswith(str(question))), 20, 'twenty-point domain')
    eq(set(page.targets), set(wanted), 'every exact prompt solved')
    eq(len(page.targets), len(wanted), 'no duplicated solution')
    eq(len(page.ids), len(set(page.ids)), 'unique fragment IDs')
    eq(page.stack, [], 'fully closed HTML fragment')
    eq(page.h1, 0, 'no extra volume-level h1')
    need({'form-a', 'solutions-a'} <= set(page.ids), 'required form and solution anchors')
    need(all(i in ('form-a', 'solutions-a') or i.startswith('v11-a-') for i in page.ids), 'owned anchor prefix')
    # Score details are independently summed, and their advertised totals are linked.
    rubrics = {'1a': [1, 1, 1, 2, 1], '1b': [4, 2, 1, 1], '1c': [2, 2, 2],
               '2a': [1, 2, 1, 1], '2b': [2, 2], '2c': [1, 2, 2, 1, 1], '2d': [1, 2, 1],
               '3a': [2, 2, 2, 2], '3b': [2, 2, 2], '3c': [2, 2, 2],
               '4a': [2, 2, 1, 1], '4b': [1, 1, 1, 1], '4c': [1, 1, 2, 2], '4d': [2, 1, 1],
               '5a': [2, 1, 1], '5b': [2, 2, 1, 2], '5c': [1, 1, 1, 1], '5d': [2, 1, 1, 1]}
    for part, values in rubrics.items():
        eq(sum(values), expected_points[part], 'subpart rubric sum '+part)
        printed(part, 'Credit '+str(expected_points[part])+':')
    sources = json.loads((root/PAYLOADS[2]).read_text())
    eq((sources['proposals'], sources['reused_source_ids']), ([], []), 'original synthetic source scope')
    eq([x['chapter'] for x in sources['method_routes']], ['v11-c'+str(i).zfill(2) for i in range(1, 13)], 'all twelve method routes')
    author = json.loads((root/'content/reviews/v11-exam-a-author.json').read_text())
    records = author['artifact_bindings']
    eq([x['path'] for x in records], PAYLOADS, 'exact three nonself payloads')
    eq(len({x['path'] for x in records}), 3, 'unique nonself bindings')
    for item in records:
        payload = (root/item['path']).read_bytes()
        eq((len(payload), hashlib.sha256(payload).hexdigest()), (item['bytes'], item['sha256']), 'author binding '+item['path'])
        counts['author_payload_hashes_verified'] += 1
    return dict(component='v11-exam-a', status='passed', **counts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path)
    args = parser.parse_args()
    print(json.dumps(check(args.root), sort_keys=True))


if __name__ == '__main__':
    main()
