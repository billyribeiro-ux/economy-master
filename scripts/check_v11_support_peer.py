"""Separate finite-contract review of the Volume 11 support component only."""
import argparse
from contextlib import redirect_stderr, redirect_stdout
from fractions import Fraction as F
import hashlib
from html.parser import HTMLParser
import importlib.util
import io
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
AUTHOR_PATHS = [
    'content/assessments/parts/v11-support-opening.html',
    'content/assessments/parts/v11-support-closing.html',
    'scripts/check_v11_assessment.py',
    'content/reviews/v11-support-sources.json',
    'content/reviews/v11-support-author.json',
]
CHECKER = 'scripts/check_v11_support_peer.py'


class Support(HTMLParser):
    """Collect scored prompts and answers independently of the author parser."""
    def __init__(self):
        super().__init__()
        self.elements = []
        self.ids, self.hrefs, self.targets = [], [], []
        self.points, self.questions, self.answers = {}, {}, {}
        self.active = None
        self.text = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if 'id' in a:
            self.ids.append(a['id'])
        if 'href' in a:
            self.hrefs.append(a['href'])
        if tag == 'li' and 'data-points' in a:
            ident = a['id']
            if ident in self.points:
                raise RuntimeError('duplicate scored prompt')
            self.points[ident] = int(a['data-points'])
            self.questions[ident] = ''
            self.active = (self.questions, ident)
        if 'data-solution-for' in a:
            ident = a['data-solution-for']
            self.targets.append(ident)
            self.answers[ident] = ''
            self.active = (self.answers, ident)
        if tag not in ('br', 'hr', 'img', 'input', 'meta', 'link'):
            self.elements.append(tag)

    def handle_endtag(self, tag):
        if not self.elements or self.elements.pop() != tag:
            raise RuntimeError('unbalanced support markup: '+tag)
        if tag == 'li':
            self.active = None

    def handle_data(self, text):
        self.text.append(text)
        if self.active is not None:
            mapping, ident = self.active
            mapping[ident] += text


def check(root=None):
    root = Path(root) if root is not None else Path(__file__).resolve().parents[1]
    n = dict(comparisons=0, diagnostic_items=8, oral_items=5, retention_items=5,
             proof_boundary_cases=0, author_files_bound=0)

    def require(ok, label):
        n['comparisons'] += 1
        if not ok:
            raise RuntimeError(label)

    def eq(actual, expected, label):
        require(actual == expected, label+': '+repr(actual)+' != '+repr(expected))

    page = Support()
    for rel in AUTHOR_PATHS[:2]:
        page.feed((root/rel).read_text())
        eq(page.elements, [], 'complete support fragment')
    text = ' '.join(page.text)

    def printed(ident, *tokens):
        answer = page.answers['v11-'+ident]
        for token in tokens:
            require(token in answer, ident+' printed answer: '+token)

    def balanced(assets, liabilities, equity, label):
        eq(sum(assets), sum(liabilities)+equity, label+' stock conservation')

    # Diagnostic 1: reconstruct creditor claims and asset holdings separately.
    deposits = 70-8
    debt = 20+5
    cash = 12-8+5
    eq((cash, deposits, debt), (9, 62, 25), 'D1 closing claims')
    balanced([cash, 58, 30], [deposits, debt], 10, 'D1 closing')
    balanced([4, 58, 30], [62, 20], 10, 'D1 withdrawal stage')
    eq((cash+58+30, deposits+debt), (97, 87), 'D1 aggregate values')
    eq(((-8)-(-8), 5-5), (0, 0), 'D1 net worth change from principal transactions')
    printed('d1', 'cash is four', 'cash to nine', '97', '87', 'equity remains ten', 'neither creates income')

    # Diagnostic 2: use all four type/signal states with test cost in every state.
    applicants = [('G', True, F(3, 5), 112), ('G', False, F(3, 20), 112),
                  ('B', True, F(1, 20), 52), ('B', False, F(1, 5), 52)]
    eq(sum(p for _, _, p, _ in applicants), 1, 'D2 joint applicant law')
    accepted = sum(p for _, passed, p, _ in applicants if passed)
    good_accepted = sum(p for kind, passed, p, _ in applicants if kind == 'G' and passed)
    expected_accepted_receipt = sum(p*receipt for _, passed, p, receipt in applicants if passed)
    margin = sum(p*((receipt-100) if passed else 0) for _, passed, p, receipt in applicants)
    expense = sum(p*2 for _, _, p, _ in applicants)
    eq((accepted, good_accepted/accepted, expected_accepted_receipt/accepted),
       (F(13, 20), F(12, 13), F(1396, 13)), 'D2 signal and conditional loan')
    eq((margin, expense, margin-expense), (F(24, 5), 2, F(14, 5)), 'D2 cost per tested applicant')
    eq(F(3, 4)*(112-100)+F(1, 4)*(52-100), -3, 'D2 unscreened comparison')
    require(margin-expense > 0 > -3, 'D2 choice versus reject and unscreened')
    eq(round(float(expected_accepted_receipt/accepted), 6), 107.384615, 'D2 displayed rounding')
    eq(margin/accepted, F(96, 13), 'D2 conditional margin not applicant gain')
    # Exact break-even test cost and a failure of charging only accepted applicants.
    eq(margin-F(24, 5), 0, 'D2 break-even test cost')
    require(margin-accepted*2 != margin-2, 'D2 rejected applicants are still tested')
    n['proof_boundary_cases'] += 2
    printed('d2', '13/20', '12/13', '1396/13', '107.384615', '14/5=2.8 CU', '96/13', 'net gain is −3')

    # Diagnostic 3: compare two cash-flow vectors against the same dated prices.
    prices = [F(19, 20), F(9, 10)]
    original, delayed = [10, 110], [0, 120]
    value = lambda flows: sum(a*b for a, b in zip(flows, prices))
    eq((value(original), value(delayed), value(original)-value(delayed)),
       (F(217, 2), 108, F(1, 2)), 'D3 exact dated claims')
    printed('d3', '108.5 CU', '108 CU', 'loss of 0.5', 'executable terms')

    # Diagnostic 4: verify the quantile's defining inequalities at the atom.
    loss_law = {0: F(4, 5), 10: F(3, 20), 50: F(1, 20)}
    eq(sum(l*p for l, p in loss_law.items()), 4, 'D4 mean')
    eq(sum(p for l, p in loss_law.items() if l > 10), F(1, 20), 'D4 strict tail')
    require(sum(p for l, p in loss_law.items() if l < 10) < F(19, 20), 'D4 below quantile')
    eq(sum(p for l, p in loss_law.items() if l <= 10), F(19, 20), 'D4 quantile mass inclusive')
    require(loss_law[50] > 0, 'D4 loss beyond quantile possible')
    printed('d4', 'four CU', '0.05', 'ten CU', 'fifty-CU loss remains possible')

    def cash_plan(opening, receipts, payments, contributions):
        balance = F(opening)
        balances = []
        for receipt, payment, contribution in zip(receipts, payments, contributions):
            balance += receipt+contribution-payment
            balances.append(balance)
        return balances

    # Diagnostic 5: necessity from each date, sufficiency on the fixed plan.
    eq(cash_plan(5, [4, 8], [10, 6], [1, 0]), [0, 2], 'D5 actual timely balances')
    eq(cash_plan(5, [4, 8], [10, 6], [0, 0]), [-1, 1], 'D5 unfunded projections')
    require(cash_plan(5, [4, 8], [10, 6], [F(99, 100), 0])[0] < 0, 'D5 less than minimum fails')
    eq(cash_plan(5, [4, 8], [10, 6], [0, 1])[0], -1, 'D5 delayed money cannot repair first date')
    n['proof_boundary_cases'] += 2
    printed('d5', 'one CU', 'zero at cutoff 1 and two at cutoff 2', 'cannot meet the earlier obligation')

    eq(F(3, 4)*4+F(1, 4)*0, 3, 'D6 physical expectation')
    eq(F(1, 4)*4+F(3, 4)*0, 1, 'D6 state-price value')
    eq(F(1, 4)+F(3, 4), 1, 'D6 unit terminal discount factor')
    printed('d6', 'three CU', 'one CU', 'specified population, data, estimation method')

    # Diagnostic 7: conversion does not relax the distinct outward-transfer cap.
    translated = 20*F(3, 2)
    offshore, onshore = 3+12, translated-12
    eq((translated+3, offshore, onshore, 20-offshore), (33, 15, 18, 5), 'D7 H-denominated location map')
    eq(offshore+onshore, translated+3, 'D7 transfer conservation')
    eq(offshore+onshore-20, 13, 'D7 positive economic net worth while illiquid')
    printed('d7', '33 H', '18 H onshore', '15 H', 'five H', 'Positive translated net worth of thirteen H')

    # Diagnostic 8: all action deviations, including strict dominance.
    payoffs = {('S', 'S'): (4, 4), ('S', 'R'): (1, 6), ('R', 'S'): (6, 1), ('R', 'R'): (2, 2)}
    best = {}
    for player in (0, 1):
        for other in ('S', 'R'):
            values = {a: payoffs[(a, other) if player == 0 else (other, a)][player] for a in ('S', 'R')}
            require(values['R'] > values['S'], 'D8 strict dominance for each opponent action')
            best[player, other] = 'R'
    eq([a+b for a, b in payoffs if a == best[0, b] and b == best[1, a]], ['RR'], 'D8 equilibrium set')
    eq((sum(payoffs['S', 'S']), sum(payoffs['R', 'R'])), (8, 4), 'D8 social payoff comparison')
    printed('d8', 'RR is the unique Nash equilibrium', 'eight at SS and four at RR', 'Actual use requires evidence')

    # Oral transfers: the open rubric requires a coherent route, not one policy.
    printed('o1', "lender's own settlement cash and funding", "change the borrower's feasible payoffs")
    eq((5+10-8, 8-5), (7, 3), 'O2 early versus late identical receipt')
    eq((5+10-8, 5+3+10-8-3), (7, 7), 'O2 zero-interest bridge preserves terminal resources')
    printed('o2', 'payment leaves seven', 'gap of three', 'explicitly stipulated', 'repayment and interest')
    printed('o3', 'same identity service', 'duplicated', 'obligation IDs', 'deadline')
    printed('o4', 'forty-F pension benefit', 'sixty-F-equivalent assets', 'cutoff 2', 'who retains any unpaid obligation')
    printed('o5', 'separately available budget', 'downside', 'false sanction', 'execution proof')

    # Retention 1: derive equity from conserved assets and creditor claims.
    loan_balances = [61+10, 61+10, 61+10-4]
    cash_balances = [9, 9-7, 9-7]
    deposit_balances = [80+10, 80+10-7, 80+10-7]
    expected = [(110, 100, 10), (103, 93, 10), (99, 93, 6)]
    for loans, cash, deposits, expected_row in zip(loan_balances, cash_balances, deposit_balances, expected):
        assets, liabilities = cash+loans+30, deposits+10
        eq((assets, liabilities, assets-liabilities), expected_row, 'R1 stage resource totals')
        balanced([cash, loans, 30], [deposits, 10], expected_row[2], 'R1 stage')
    eq((cash_balances[-1], 6-5), (2, 1), 'R1 bank cash versus borrower service gap')
    printed('r1', 'loans to 71', 'cash to two', 'deposits to 83', 'net loans to 67', 'equity to six', '99', 'one-CU service gap')

    # Retention 2: quantile integral on [0.8,1], independently of a tail-sort routine.
    intervals = [(F(0), F(7, 10), 0), (F(7, 10), F(9, 10), 8), (F(9, 10), F(1), 40)]
    alpha = F(4, 5)
    pieces = [(max(F(0), hi-max(lo, alpha)), loss) for lo, hi, loss in intervals]
    eq(pieces, [(0, 0), (F(1, 10), 8), (F(1, 10), 40)], 'R2 exact partial atom')
    eq(sum(mass for mass, _ in pieces), 1-alpha, 'R2 exactly required tail mass')
    es = sum(mass*loss for mass, loss in pieces)/(1-alpha)
    eq(es, 24, 'R2 integrated quantile ES')
    require(F(7, 10) < alpha <= F(9, 10), 'R2 VaR is eight')
    wrong_tail_mean = (F(1, 5)*8+F(1, 10)*40)/F(3, 10)
    eq(wrong_tail_mean, F(56, 3), 'R2 full boundary atom answers different question')
    require(wrong_tail_mean != es, 'R2 boundary atom cannot be included in full')
    eq(cash_plan(6, [3, 9], [12, 4], [3, 0]), [0, 5], 'R2 early contribution suffices')
    require(cash_plan(6, [3, 9], [12, 4], [F(299, 100), 0])[0] < 0, 'R2 less than three fails')
    capacity = F(10)*F(4, 5)*F(3, 4)
    eq(capacity, 6, 'R2 haircut capacity')
    eq(cash_plan(6, [3, 9], [12, 4], [0, capacity])[0], -3, 'R2 late facility fails first deadline')
    n['proof_boundary_cases'] += 3
    printed('r2', '=8', '=24', 'three', 'zero and five', 'six CU', 'too late')

    # Retention 3: condition on the common regime; covariance is its mean variance.
    regimes = [(F(1, 10), F(1)), (F(9, 10), F(1, 5))]
    marginal = sum(weight*conditional for weight, conditional in regimes)
    joint = sum(weight*conditional**2 for weight, conditional in regimes)
    covariance = sum(weight*(conditional-marginal)**2 for weight, conditional in regimes)
    eq((marginal, joint, marginal*marginal, covariance),
       (F(7, 25), F(17, 125), F(49, 625), F(36, 625)), 'R3 common-regime moments')
    eq(joint-marginal*marginal, covariance, 'R3 exact covariance gap')
    eq((float(joint), float(marginal*marginal), float(covariance)), (0.136, 0.0784, 0.0576), 'R3 exact decimal presentation')
    joint_states = [(8, 2, 0), (1, 7, 4)]
    eq([sum(s) for s in joint_states], [10, 12], 'R3 supported totals')
    eq(sum(max(x, y) for x, y in zip(*joint_states)), 19, 'R3 incompatible component maxima')
    obligations, reported = ['a', 'b'], ['a', 'a']
    eq([o for o in obligations if o not in reported], ['b'], 'R3 unpaid unique obligation')
    eq(len(reported), len(obligations), 'R3 total count conceals identity failure')
    printed('r3', '0.136', '0.0784', '0.0576', 'twelve', 'nineteen', 'b unpaid', 'separate recoverable claim')

    # Retention 4: allocate each pension asset pool, then draw from a separate reserve.
    guarantee, unpaid, residual, remaining_reserve = [], [], [], []
    for assets in (20, 60):
        primary = min(assets, 40)
        draw = min(40-primary, 12)
        receipts = primary+draw
        sponsor = assets-primary
        unused = 12-draw
        eq(receipts+sponsor+unused, assets+12, 'R4 complete state resources')
        guarantee.append(draw); unpaid.append(40-receipts)
        residual.append(sponsor); remaining_reserve.append(unused)
    eq((guarantee, unpaid, residual, remaining_reserve), ([12, 0], [8, 0], [0, 20], [0, 12]), 'R4 full state allocations')
    eq(tuple(F(sum(values), 2) for values in (guarantee, unpaid, residual)), (6, 4, 10), 'R4 expected allocations')
    eq(F(20+60, 2)/40, 1, 'R4 ratio of mean assets to fixed benefit')
    h_after_local = 66-16
    purchase = min(F(h_after_local, 2), 15)
    h_before_foreign, f_before_foreign = h_after_local-2*purchase, 8+purchase
    eq((h_before_foreign, f_before_foreign, 30-f_before_foreign), (20, 23, 7), 'R4 explicit pre-foreign-service balances')
    eq(h_before_foreign+2*f_before_foreign, 66+2*8-16, 'R4 translated conversion conservation')
    eq(f_before_foreign+7-30, 0, 'R4 timely grant or funded loan closes current gap')
    require('before foreign service' in page.questions['v11-r4'], 'R4 repaired measurement time')
    printed('r4', 'ratio is one', 'eight unpaid benefits', 'Expected guarantee payment is six',
            'expected unpaid benefits four', 'expected sponsor residual ten', '32 and 72',
            'twenty H', '23 usable F', 'seven F', 'eight-F later service')

    # Retention 5: use final external claims to solve for required conversion.
    assets_after_loss, deposits, senior_after_loss = 4+76-20, 50, 20-10
    write_down = (50+20)-assets_after_loss
    advance, repayment = 9-4, F(11, 2)
    interest = repayment-advance
    floor = F(4)
    conversion = floor+interest
    remaining_senior = senior_after_loss-conversion
    terminal_cash = (76-20)-repayment-(deposits-9)-remaining_senior
    eq((write_down, advance, interest, conversion, remaining_senior, terminal_cash),
       (10, 5, F(1, 2), F(9, 2), F(11, 2), 4), 'R5 cash-funded capital repair')
    balanced([4, 56], [50, 10], 0, 'R5 write-down')
    balanced([4, 56], [50, remaining_senior], conversion, 'R5 conversion')
    balanced([0, 56], [41, remaining_senior, advance], conversion, 'R5 first payment')
    balanced([56], [41, remaining_senior, repayment], floor, 'R5 interest accrual')
    senior_value = remaining_senior+terminal_cash
    eq(senior_value, F(19, 2), 'R5 old senior debt plus new equity')
    eq(deposits+senior_value+interest, assets_after_loss, 'R5 old claims plus net lender income')
    require(conversion-F(1, 100)-interest < floor, 'R5 less conversion fails terminal floor')
    eq(8-0, 8, 'R5 downstream due amount has no available receipt')
    # State-payoff expectation keeps the lost bonus and the paid fine distinct.
    for conditional, probability, expected in [(F(1, 2), F(3, 8), F(0)), (F(3, 5), F(9, 20), F(-3, 5))]:
        detected = F(3, 4)*conditional
        concealment = (1-detected)*3+detected*(-5)
        eq((detected, concealment), (probability, expected), 'R5 incentive outcome')
        eq(concealment, 3-(3+5)*detected, 'R5 reduced incentive equation')
    eq(F(3, 8)/F(3, 4), F(1, 2), 'R5 exact conditional detection tie boundary')
    n['proof_boundary_cases'] += 3
    printed('r5', 'ten', 'five', '4.5', '9.5', 'eight-CU customer obligation', '3/8',
            'zero', 'tying truthful reporting', '0.45', '−0.6', 'strict truthful preference')

    # Point totals and advancement rules are authored criteria, not test validation.
    expected_points = {**{'v11-d'+str(i): 5 for i in range(1, 9)},
                       **{'v11-o'+str(i): 4 for i in range(1, 6)},
                       **{'v11-r'+str(i): 10 for i in range(1, 6)}}
    eq(page.points, expected_points, 'all exact scored prompts')
    eq(len(page.targets), len(expected_points), 'one answer for each prompt')
    eq(set(page.targets), set(expected_points), 'complete exact answer mapping')
    eq(len(page.ids), len(set(page.ids)), 'unique fragment IDs')
    for prefix, total in [('v11-d', 40), ('v11-o', 20), ('v11-r', 50)]:
        eq(sum(v for k, v in page.points.items() if k.startswith(prefix)), total, 'component point sum')
    diagnostic_rubrics = [[1, 1, 1, 1, 1], [1, 1, 1, 1, 1], [1, 1, 1, 1, 1],
                          [1, 1, 2, 1], [2, 1, 1, 1], [1, 1, 2, 1], [1, 1, 1, 1, 1], [2, 1, 1, 1]]
    retention_rubrics = [[6, 1, 1, 2], [2, 3, 3, 2], [4, 3, 3], [4, 2, 2, 2], [3, 2, 1, 3, 1]]
    for weights in diagnostic_rubrics:
        eq(sum(weights), 5, 'diagnostic suballocation')
    for weights in retention_rubrics:
        eq(sum(weights), 10, 'retention suballocation')
    eq(sum([1, 1, 1, 1]), 4, 'common oral rubric')
    for marker in ('34/40', 'questions 1, 5 and 7', '85/100 and 15/20', '17/20 and three points',
                   '43/50 and eight points', 'not been statistically equated', 'Critical errors require remediation'):
        require(marker in text, 'administration '+marker)
    require(F(43, 50) >= F(85, 100) and F(42, 50) < F(85, 100), 'rounded overall retention threshold')
    require(F(8, 10) >= F(75, 100) and F(7, 10) < F(75, 100), 'rounded domain retention threshold')

    # Exact portable link inventory was additionally resolved against the real
    # chapter/build outputs at review time. Those shared files are not dependencies.
    expected_links = {
        'v07-c01.html', 'v07-c02.html', 'v03-c02.html', 'v03-c09.html', 'v08-c01.html',
        'v09-c05.html', 'v03-c03.html', 'v03-c04.html', 'v08-c06.html', 'v10-c05.html',
        'v10-c06.html', 'v06-c11.html', 'v05-c07.html', 'v11-c01.html',
        'v11-c02.html#transactions', 'v11-c03.html#repayment', 'v11-c04.html#es',
        'v11-c05.html#minimum-proof', 'v11-c06.html#dependence', 'v11-c07.html',
        'v11-c08.html#guarantees', 'v11-c09.html#claim-map', 'v11-c10.html#resolution',
        'v11-c11.html#lender', 'v11-c12.html#evidence', 'v11-c02.html#balance-sheet',
        'v11-c03.html#cash', 'v11-c04.html#var', 'v11-c05.html#dated-resources',
        'v11-c06.html#reconciliation', 'v11-c08.html#survival', 'v11-c09.html#covered-proof',
        'v11-c10.html#portfolio', 'v11-c11.html#sale', 'v11-c12.html#appetite',
        'assessments.html#finance-core', 'curriculum.html#v12',
    }
    eq(set(page.hrefs), expected_links, 'audited chapter and successor links')
    eq({link[:7] for link in page.hrefs if link.startswith('v11-c')},
       {'v11-c'+str(i).zfill(2) for i in range(1, 13)}, 'all twelve chapter routes')
    sources = json.loads((root/AUTHOR_PATHS[3]).read_text())
    eq((sources['proposals'], sources['reused_source_ids']), ([], []), 'no new primary-source claim')

    def bindings(rows, expected, label):
        eq([x['path'] for x in rows], expected, label+' exact binding inventory')
        eq(len({x['path'] for x in rows}), len(rows), label+' unique bindings')
        for item in rows:
            payload = (root/item['path']).read_bytes()
            eq((len(payload), hashlib.sha256(payload).hexdigest()),
               (item['bytes'], item['sha256']), label+' '+item['path'])

    author = json.loads((root/AUTHOR_PATHS[-1]).read_text())
    bindings(author['reviewed_hashes'], AUTHOR_PATHS[:-1], 'author nonself')
    peer = json.loads((root/'content/reviews/v11-support-peer.json').read_text())
    bindings(peer['artifact_bindings'], AUTHOR_PATHS+[CHECKER], 'final peer')
    n['author_files_bound'] = len(AUTHOR_PATHS)

    # Test the author's public support-only boundary after the independent oracle.
    # Do not call its future whole-volume check() or use its numbers as expected data.
    spec = importlib.util.spec_from_file_location('v11_support_author_target', root/AUTHOR_PATHS[2])
    module = importlib.util.module_from_spec(spec)
    silent = io.StringIO()
    with redirect_stdout(silent), redirect_stderr(silent):
        spec.loader.exec_module(module)
        author_result = module.support_check()
    eq(silent.getvalue(), '', 'quiet author support-only API')
    eq(author_result['status'], 'passed', 'author support contract after independent oracle')
    eq(author_result['author_payload_hashes_verified'], 4, 'author verifies its four nonself files')
    return dict(component='v11-assessment-support', status='passed', **n)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path)
    args = parser.parse_args()
    print(json.dumps(check(args.root), sort_keys=True))


if __name__ == '__main__':
    main()
