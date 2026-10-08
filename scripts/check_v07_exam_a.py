"""Exact independent numerical and structure checks for Volume 7 Form A.

Run from any directory. Import is quiet; check() returns strict-JSON-compatible
data without writing files. The checker reconstructs journal, present-value,
resource-choice and cash models from the exam's original inputs. Source scope,
recognition facts, open evidence answers and teaching adequacy need the recorded
manuscript review; arithmetic cannot authenticate them.
"""
from collections import Counter, defaultdict
from copy import deepcopy
from fractions import Fraction as F
from html.parser import HTMLParser
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
MANUSCRIPT = ROOT / 'content/assessments/parts/v07-exam-a.html'


def require(condition, message):
    if not condition:
        raise AssertionError(message)


class Ledger:
    """Positive debit balances; negative credit balances, including income."""
    def __init__(self, balances=None):
        self.balance = defaultdict(F)
        self.entries = 0
        if balances:
            self.post(balances)

    def post(self, entry):
        require(sum(map(F, entry.values())) == 0, 'unbalanced journal entry')
        for account, amount in entry.items():
            self.balance[account] += F(amount)
        self.entries += 1
        require(sum(self.balance.values()) == 0, 'trial balance does not close')

    def __getitem__(self, account):
        return self.balance[account]

    def income(self, expenses):
        return -self['revenue'] - sum(self[a] for a in expenses)

    def close(self, expenses):
        income = self.income(expenses)
        entry = {'revenue': -self['revenue'], 'retained': -income}
        entry.update({a: -self[a] for a in expenses})
        self.post(entry)
        return income


class Form(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids = []
        self.parts = {}
        self.solutions = []
        self.h2 = []
        self.hrefs = []
        self.forbidden = []
        self.details = 0
        self.summary_count = 0
        self.text = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if 'id' in a:
            self.ids.append(a['id'])
        if 'data-points' in a:
            require(tag == 'li' and 'id' in a, 'point tag must be identified li')
            self.parts[a['id']] = int(a['data-points'])
        if 'data-solution-for' in a:
            require(tag == 'li', 'solution mapping must be li')
            self.solutions.append(a['data-solution-for'])
        if tag == 'h2':
            self.h2.append(a.get('id'))
        if tag == 'a':
            self.hrefs.append(a.get('href', ''))
        if tag in ('h1', 'html', 'head', 'body', 'script'):
            self.forbidden.append(tag)
        if tag == 'details':
            self.details += 1
        if tag == 'summary':
            self.summary_count += 1

    def handle_data(self, text):
        self.text.append(text)


def cedar_check():
    opening = {'cash': 40, 'receivables': 60, 'inventory': 90, 'ppe': 120,
               'payables': -50, 'debt': -100, 'capital': -100, 'retained': -60}
    ledger = Ledger(opening)
    transactions = (
        {'cash': 60, 'revenue': -60},
        {'receivables': 300, 'revenue': -300},
        {'cash': 280, 'receivables': -280},
        {'inventory': 260, 'payables': -260},
        {'cost': 240, 'inventory': -240},
        {'payables': 240, 'cash': -240},
        {'wages': 50, 'cash': -50},
        {'depreciation': 12, 'ppe': -12},
    )
    for entry in transactions:
        ledger.post(entry)
    genuine = deepcopy(ledger.balance)
    ledger.post({'receivables': 50, 'revenue': -50})
    ledger.post({'cost': 30, 'inventory': -30})
    expenses = ('cost', 'wages', 'depreciation')
    draft_income = ledger.income(expenses)
    draft_cfo = (draft_income + ledger['depreciation']
                 - (ledger['receivables'] - 60)
                 - (ledger['inventory'] - 90)
                 + (-ledger['payables'] - 50))
    require((draft_income, ledger['receivables'], ledger['inventory']) ==
            (78, 130, 80), 'Q1 draft reconstruction')
    ledger.post({'revenue': 50, 'receivables': -50})
    ledger.post({'inventory': 30, 'cost': -30})
    require(dict(ledger.balance) == dict(genuine), 'Q1 correction not full reversal')
    ni = ledger.close(expenses)
    balances = tuple(ledger[a] for a in ('cash', 'receivables', 'inventory', 'ppe'))
    require(balances == (90, 80, 110, 108), 'Q1 closing assets')
    require(ni == 58 and -ledger['retained'] == 118 and
            sum(balances) == 388 == -sum(ledger[a] for a in
                ('payables', 'debt', 'capital', 'retained')), 'Q1 equation/equity')
    receipts, supplier, wage = 60 + 280, 240, 50
    direct_cfo = receipts - supplier - wage
    indirect_cfo = ni + 12 - (80-60) - (110-90) + (70-50)
    require(direct_cfo == indirect_cfo == draft_cfo == 50 and
            ledger['cash'] == opening['cash'] + direct_cfo, 'Q1 cash invariance')
    dso = F(360) * F(60+80, 2) / 300
    dio = F(360) * F(90+110, 2) / 240
    dpo = F(360) * F(50+70, 2) / 260
    require((dso, dio, dpo, dso+dio-dpo) ==
            (84, 150, F(1080, 13), F(1962, 13)), 'Q1 matched-flow days')
    require(dso != F(360)*70/360 and dpo != F(360)*60/240,
            'Q1 silent denominator changes must matter')
    return {'NI': 58, 'CFO': 50, 'assets': 388,
            'CCC_days': str(dso+dio-dpo), 'balanced_journal_prefixes': ledger.entries}


def asset_finance_check():
    # Monthly allocations provide a separate check of fractional-year charges.
    cost = sum((96, 4, 8))
    month_charge = F(cost-8, 5*12)
    half_year = sum(month_charge for _ in range(6))
    require((cost, half_year, cost-half_year, 6+3+half_year) ==
            (108, 10, 98, 19), 'Q2 capitalizable versus consumed costs')
    require(6+3+cost == 117 and cost-half_year + 19 == 117,
            'Q2 all consumed/current resource cost closes')
    tool_dep = sum(F(12, 12) for _ in range(6))
    accumulated = 60 + tool_dep
    carrying = 90 - accumulated
    loss = carrying - 22
    tool = Ledger({'ppe_cost': 90, 'accumulated': -60, 'equity': -30})
    tool.post({'depreciation': tool_dep, 'accumulated': -tool_dep})
    tool.post({'cash': 22, 'accumulated': accumulated, 'loss': loss, 'ppe_cost': -90})
    require((tool_dep, accumulated, carrying, loss) == (6, 66, 24, 2),
            'Q2 disposal at current carrying amount')
    require(tool['ppe_cost'] == tool['accumulated'] == 0 and
            -tool_dep-loss+tool_dep+loss == 0 and tool['cash'] == 22,
            'Q2 complete derecognition and CFO/CFI separation')

    r = F(1, 10)
    require(F(121)/(1+r)**2 == 100, 'Q2 zero-coupon PV')
    balance, interests, ends = F(100), [], []
    for payment in (0, 121):
        interest = balance*r
        interests.append(interest)
        balance += interest
        ends.append(balance)
        balance -= payment
    require(interests == [10, 11] and ends == [110, 121] and balance == 0,
            'Q2 note schedule/settlement')
    require(sum(interests) == 121-100 == 21, 'Q2 note lifetime expense')

    payment = F(121, 2)
    initial = sum(payment/(1+r)**t for t in (1, 2))
    liability, rou = initial, initial
    depreciation = initial/2
    rows = []
    for _ in range(2):
        interest = liability*r
        principal = payment-interest
        liability -= principal
        rou -= depreciation
        rows.append((interest, principal, liability, rou, depreciation+interest))
    require(initial == 105 and rows[0] ==
            (F(21, 2), 50, 55, F(105, 2), 63), 'Q2 first lease year')
    require(rows[1] == (F(11, 2), 55, 0, 0, 58), 'Q2 lease terminal closure')
    require(sum(row[4] for row in rows) == 2*payment == 121 and
            sum(row[1] for row in rows) == initial, 'Q2 lifetime lease cash/expense')
    return {'machine_cost': 108, 'machine_close': 98, 'disposal_loss': 2,
            'note_interest': [10, 11], 'lease_initial': 105,
            'lease_year_1_liability': 55, 'lease_year_1_ROU': '105/2'}


def ownership_tax_check():
    issue_cash, par = 20*8, 20*1
    issuer = Ledger({'assets': 450, 'capital': -100, 'premium': -200,
                     'retained': -150})
    issuer.post({'cash': issue_cash, 'capital': -par,
                 'premium': -(issue_cash-par)})
    issuer.post({'net_resources_from_income': 30, 'retained': -30})
    issuer.post({'retained': 12, 'cash': -12})
    equity = -sum(issuer[a] for a in ('capital', 'premium', 'retained'))
    require(equity == 628 and -issuer['retained'] == 168 and
            F(25, 100+20) == F(5, 24), 'Q3 owner issue/retention/dilution')

    # Combine separate trial balances, then use acquisition eliminations.
    group = Ledger({'cash': 80+40, 'ppe': 260+200, 'investment': 225,
                    'inventory': 160, 'liabilities': -165-160,
                    'parent_equity': -400, 'subsidiary_equity': -240})
    goodwill = 225 - F(3, 4)*(400-160)
    nci = F(1, 4)*(400-160)
    group.post({'subsidiary_equity': 240, 'goodwill': goodwill,
                'investment': -225, 'nci': -nci})
    assets = sum(group[a] for a in ('cash', 'ppe', 'investment', 'inventory', 'goodwill'))
    require((nci, goodwill, assets) == (60, 45, 785), 'Q3 purchase/NCI/goodwill')
    require(group['investment'] == group['subsidiary_equity'] == 0 and
            assets == -sum(group[a] for a in ('liabilities', 'parent_equity', 'nci')),
            'Q3 consolidated equation/elimination')

    fraction_unsold = F(2, 5)
    unsold_buyer_cost = 60*fraction_unsold
    unsold_group_cost = 48*fraction_unsold
    unrealized = unsold_buyer_cost-unsold_group_cost
    # The full transfer elimination changes gross flows equally; only the
    # retained markup changes group profit. The parent is the seller, so this
    # is a downstream inventory sale and does not alter S's own profit.
    elimination = Ledger()
    elimination.post({'revenue': 60, 'cost': -60})
    elimination.post({'cost': unrealized, 'inventory': -unrealized})
    ni_change = -elimination['revenue']-elimination['cost']
    group_income = 80+40+ni_change
    outside_income = F(1, 4)*40
    parent_income = (80-unrealized)+F(3, 4)*40
    require((unrealized, group_income, outside_income, parent_income) ==
            (F(24, 5), F(576, 5), 10, F(526, 5)), 'Q3 downstream attribution')
    require(parent_income+outside_income == group_income and
            F(1, 4)*(40-unrealized) != outside_income,
            'Q3 downstream cannot reduce subsidiary NCI income')

    taxpayer = Ledger()
    taxpayer.post({'cash': 170, 'revenue': -170})
    taxpayer.post({'ordinary_expense': 70, 'cash': -70})
    taxpayer.post({'warranty_expense': 20, 'provision': -20})
    rate = F(1, 4)
    book_profit = taxpayer.income(('ordinary_expense', 'warranty_expense'))
    taxable_profit = 170-70
    current_tax = taxable_profit*rate
    tax_base = 20-20
    dta = (20-tax_base)*rate
    taxpayer.post({'current_tax_expense': current_tax, 'cash': -current_tax})
    taxpayer.post({'DTA': dta, 'deferred_tax_expense': -dta})
    ni = taxpayer.close(('ordinary_expense', 'warranty_expense',
                         'current_tax_expense', 'deferred_tax_expense'))
    require((book_profit, taxable_profit, current_tax, tax_base, dta, ni) ==
            (80, 100, 25, 0, 5, 60), 'Q3 current/deferred tax and recognized income')
    require(taxpayer['cash'] == 75 == ni+20-dta and
            taxpayer['cash']+taxpayer['DTA'] == -taxpayer['provision']-taxpayer['retained'],
            'Q3 DTA is noncash; signed balance closure')
    return {'issuer_equity': int(equity), 'acquisition_assets': int(assets),
            'downstream_group_NI': str(group_income), 'NCI_income': 10,
            'DTA': 5, 'taxpayer_NI': 60, 'taxpayer_CFO': 75}


def cost_ratio_check():
    v = F(3500-2600, 700-400)
    fixed = F(2600)-v*400
    require(v == 3 and fixed == 1400 and fixed+700*v == 3500,
            'Q4 cost line from observations')
    variable_a, variable_b = 13+v, 22+2*v
    margin_a, margin_b = 30-variable_a, 50-variable_b
    committed = fixed+600
    bundle_margin = 2*margin_a+margin_b
    bundle_results = [(z, z*bundle_margin-committed) for z in range(51)]
    nonloss = next(z for z, profit in bundle_results if profit >= 0)
    require((variable_a, variable_b, margin_a, margin_b, bundle_margin) ==
            (16, 28, 14, 22, 50), 'Q4 support counted once in variable costs')
    require(nonloss == 40 and 4*nonloss == 160 and
            max(profit for _, profit in bundle_results) == 500 and
            (committed+600)/bundle_margin*4 == 208, 'Q4 integer mix and target capacity')

    # Enumerate complete feasible regular choices; no greedy ranking assumed.
    def best_regular(hours):
        candidates = [(a*margin_a+b*margin_b, a, b)
                      for a in range(81) for b in range(41) if a+2*b <= hours]
        value = max(x[0] for x in candidates)
        choices = [(a, b) for contribution, a, b in candidates if contribution == value]
        return value, choices

    baseline_contribution, baseline_choices = best_regular(200)
    reserved_contribution, reserved_choices = best_regular(200-30*2)
    lost = baseline_contribution-reserved_contribution
    incremental = 30*(40-variable_b)-30-lost
    threshold = variable_b+(30+lost)/30
    require(baseline_choices == [(80, 40)] and reserved_choices == [(80, 30)] and
            (lost, incremental, threshold) == (220, 110, F(109, 3)),
            'Q4 complete all-or-nothing order comparison')
    alternate_profit = 80*30+30*50+30*40-(80*16+30*28+30*28)-committed-30
    require(alternate_profit == incremental == 110 and
            30*(threshold-variable_b)-30-lost == 0,
            'Q4 full-scenario versus incremental profit and threshold')
    opening_current = F(10+40+50, 30+20)
    closing_current = F(5+65+90, 55+25)
    opening_quick = F(10+40, 30+20)
    closing_quick = F(5+65, 55+25)
    require((opening_current, closing_current, opening_quick, closing_quick, F(30, 5)) ==
            (2, 2, 1, F(7, 8), 6), 'Q4 liquidity components and positive interest divisor')
    return {'variable_support_per_hour': '3', 'support_fixed': '1400',
            'first_nonloss_bundles': 40, 'maximum_fixed_mix_profit': 500,
            'special_order_profit': '110', 'special_quote_threshold': str(threshold),
            'closing_quick_ratio': str(closing_quick)}


def forecast_ledger(receivables, dividend, borrowing, new_equity):
    ledger = Ledger({'cash': 20, 'receivables': 30, 'inventory': 40, 'ppe': 100,
                     'payables': -25, 'debt': -75, 'retained': -90})
    # Equity is aggregated in retained for the forecast only; no par allocation
    # is asserted. All cash legs follow from customer/supplier stock ledgers.
    ledger.post({'receivables': 240, 'revenue': -240})
    ledger.post({'cash': 30+240-receivables, 'receivables': -(30+240-receivables)})
    ledger.post({'inventory': 154, 'payables': -154})
    ledger.post({'cost': 144, 'inventory': -144})
    ledger.post({'payables': 25+154-30, 'cash': -(25+154-30)})
    ledger.post({'operating_expense': 36, 'cash': -36})
    ledger.post({'interest': 6, 'cash': -6})
    ledger.post({'depreciation': 10, 'ppe': -10})
    tax = F(240-144-36-6-10, 4)
    ledger.post({'tax': tax, 'cash': -tax})
    cfo = ledger['cash']-20
    ledger.post({'ppe': 30, 'cash': -30})
    ledger.post({'debt': 15, 'cash': -15})
    ledger.post({'retained': dividend, 'cash': -dividend})
    ledger.post({'cash': borrowing, 'debt': -borrowing})
    ledger.post({'cash': new_equity, 'retained': -new_equity})
    ni = ledger.close(('cost', 'operating_expense', 'interest', 'depreciation', 'tax'))
    return ledger, ni, cfo


def forecast_comparison_check():
    unfunded, ni, cfo = forecast_ledger(48, 12, 0, 0)
    needed = 10-unfunded['cash']
    require((ni, cfo, needed) == (33, 20, 27), 'Q5 unconstrained annual funding need')
    base, ni, cfo = forecast_ledger(48, 12, needed, 0)
    require(tuple(base[a] for a in ('cash', 'receivables', 'inventory', 'ppe',
                                   'payables', 'debt', 'retained')) ==
            (10, 48, 50, 120, -30, -87, -111), 'Q5 base all-statement closure')
    require(sum(base[a] for a in ('cash', 'receivables', 'inventory', 'ppe')) == 228,
            'Q5 base asset total')
    stressed, stress_ni, stress_cfo = forecast_ledger(70, 12, 0, 0)
    require(stress_ni == ni == 33 and stress_cfo == -2 and
            10-stressed['cash'] == 49, 'Q5 collection delay is not profit loss')
    cap_only, _, _ = forecast_ledger(70, 12, 35, 0)
    cancelled, _, _ = forecast_ledger(70, 0, 35, 0)
    new_equity = 10-cancelled['cash']
    require((cap_only['cash'], cancelled['cash'], new_equity) == (-4, 8, 2),
            'Q5 binding line and payout repair')
    repaired, _, _ = forecast_ledger(70, 0, 35, new_equity)
    require(tuple(repaired[a] for a in ('cash', 'receivables', 'inventory', 'ppe',
                                       'payables', 'debt', 'retained')) ==
            (10, 70, 50, 120, -30, -95, -125), 'Q5 repaired complete balance sheet')
    require(sum(repaired[a] for a in ('cash', 'receivables', 'inventory', 'ppe')) == 250,
            'Q5 repaired asset total')
    # Small transfers verify the cash rule while holding recognized profit fixed.
    for ar_change in (-5, 0, 9):
        alternative, other_ni, other_cfo = forecast_ledger(48+ar_change, 12, 0, 0)
        require(other_ni == 33 and other_cfo == 20-ar_change and
                10-alternative['cash'] == 27+ar_change, 'Q5 funding/receivable sensitivity')

    fifo_open, fifo_close = 45+12, 65+8
    inventory_adjustment_change = (fifo_close-fifo_open)-(65-45)
    # Same purchases: ending inventory difference determines current COGS.
    arbitrary_common_purchases = 140
    lifo_cost = 45+arbitrary_common_purchases-65
    fifo_cost = fifo_open+arbitrary_common_purchases-fifo_close
    profit_change = lifo_cost-fifo_cost
    fifo_profit = 40+profit_change
    fifo_cfo = 30+profit_change-inventory_adjustment_change
    require((fifo_open, fifo_close, profit_change, fifo_profit, fifo_cfo) ==
            (57, 73, -4, 36, 30), 'Q5 FIFO reserve stock/flow/cash consistency')
    require(fifo_profit != 40+8, 'Q5 ending reserve cannot replace its change')
    management = 70+12+5
    recurring = 70+12-10
    historical_cfo = 40+10-35-8+5
    require((management, recurring, management-recurring, historical_cfo) ==
            (87, 72, 15, 12), 'Q5 symmetric normalization and unchanged bank history')
    return {'base_NI': 33, 'base_CFO': 20, 'base_draw': 27, 'stress_draw': 49,
            'stress_equity_cure': 2, 'repaired_assets': 250,
            'FIFO_profit': 36, 'FIFO_CFO': 30, 'recurring_EBITDA': 72}


def structure_check():
    content = MANUSCRIPT.read_text(encoding='utf-8')
    form = Form()
    form.feed(content)
    expected = {f'v07-a-q{q}{part}' for q in range(1, 6) for part in 'abcd'}
    require(set(form.parts) == expected and set(form.parts.values()) == {5} and
            sum(form.parts.values()) == 100, 'Form A exact part IDs and 100 points')
    require(Counter(form.solutions) == Counter({key: 1 for key in expected}),
            'Form A one solution per question part')
    require(len(form.ids) == len(set(form.ids)), 'duplicate HTML IDs')
    require(form.h2 == ['form-a', 'solutions-a'] and not form.forbidden,
            'Form A fragment headings and no page wrapper')
    require(form.details == form.summary_count == 5 and content.count('<strong>Scoring:</strong>') == 20,
            'Form A labeled full solutions and point rubrics')
    chapters = {f'v07-c{c:02d}.html' for c in range(1, 13)}
    require(chapters <= set(form.hrefs), 'all twelve taught chapter routes required')
    require('180 minutes' in content and 'closed notes' in content and
            'calculator permitted' in content, 'exam conditions')
    require('data-solution-for="v07-a-q5d"' in content and
            'Maple Works' in content and 'Rowan' not in content,
            'assembly mapping and separate project entity')
    # Scoring prose is intentionally explicit; each rubric's terminal integers
    # sum to five, including the 2+2+1 high-low cost rubric.
    rubrics = re.findall(r'<strong>Scoring:</strong>(.*?)</p>', content, re.S)
    for index, rubric in enumerate(rubrics):
        points = [int(x) for x in re.findall(r'\b([1-5])(?=\s*[;.])', rubric)]
        require(sum(points) == 5, f'Form A rubric {index+1} does not sum to five')
    return {'parts': len(form.parts), 'solutions': len(form.solutions), 'points': 100,
            'question_domains': 5, 'chapter_routes': 12,
            'words': len(re.findall(r'\b[\w’−]+\b', ' '.join(form.text)))}


def check():
    result = {
        'status': 'passed',
        'groups': [
            'Q1 signed journal prefixes, cutoff cancellation, three statements and matched days',
            'Q2 monthly consumption, complete disposal and independent note/lease PV/lifetime checks',
            'Q3 owner and consolidation eliminations, downstream attribution and noncash tax asset',
            'Q4 cost fit, bounded whole-bundle enumeration and complete special-order optimization',
            'Q5 independent forecast cash ledger, constrained repair, inventory basis and evidence arithmetic',
            'Twenty matched parts/solutions, five-point rubrics, fragment structure and twelve chapter routes',
        ],
        'numerical_anchors': {
            'D1': cedar_check(),
            'D2': asset_finance_check(),
            'D3': ownership_tax_check(),
            'D4': cost_ratio_check(),
            'D5': forecast_comparison_check(),
        },
        'structure': structure_check(),
        'limits': 'Conditional numerical and source-fragment checks; no UI, human grading, calibration or real evidence authentication.',
    }
    json.dumps(result, allow_nan=False)
    return result


if __name__ == '__main__':
    print(json.dumps(check(), indent=2, allow_nan=False))
