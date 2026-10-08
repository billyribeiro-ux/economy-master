"""Independent exact audit of v08-c09 acquisition teaching cases.

check() is quiet, JSON-compatible and performs no writes or network operations.
The reconstruction tests dated cash, claims, incentives and counterexamples;
it cannot authenticate the fictional case assumptions or real transaction law.
"""
from contextlib import redirect_stdout
from copy import deepcopy
from fractions import Fraction as F
from html.parser import HTMLParser
import importlib.util
import io
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT / 'content/projects'


def require(condition, message):
    if not condition:
        raise AssertionError(message)


class Document(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids, self.links, self.sources, self.text = [], [], [], []
        self.worked = self.exercises = self.solutions = 0
        self.ol = self.details = self.exercise_depth = self.solution_depth = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if 'id' in a:
            self.ids.append(a['id'])
        if tag == 'a':
            self.links.append(a.get('href', ''))
        if 'data-source' in a:
            self.sources.append(a['data-source'])
        if 'worked' in a.get('class', '').split():
            self.worked += 1
        if tag == 'ol':
            self.ol += 1
            if 'exercises' in a.get('class', '').split():
                self.exercise_depth = self.ol
        if tag == 'details':
            self.details += 1
            if 'solutions' in a.get('class', '').split():
                self.solution_depth = self.details
        if tag == 'li' and self.exercise_depth == self.ol and self.exercise_depth:
            self.exercises += 1
        if tag == 'li' and self.solution_depth:
            self.solutions += 1

    def handle_endtag(self, tag):
        if tag == 'ol':
            if self.exercise_depth == self.ol:
                self.exercise_depth = 0
            self.ol -= 1
        if tag == 'details':
            if self.solution_depth == self.details:
                self.solution_depth = 0
            self.details -= 1

    def handle_data(self, text):
        self.text.append(text)


def load_lab():
    spec = importlib.util.spec_from_file_location('v08_c09_benchmark', LAB / 'v08-c09-analysis.py')
    module = importlib.util.module_from_spec(spec)
    capture = io.StringIO()
    with redirect_stdout(capture):
        spec.loader.exec_module(module)
    require(not capture.getvalue(), 'Lab import must be quiet')
    return module


def problem_audit():
    # All eight exact exercise prompts are independently solved here. Conceptual
    # explanations and source scope also receive manual author/root review.
    equity = 360+25+15-90-20
    tx_ev = 330+90+20-25-15
    require((equity, F(equity,15), tx_ev, 330-equity, F(330-equity,equity)) ==
            (290, F(58,3), 400, 40, F(4,29)), 'Exercise 1 ownership and offer boundary')

    pv75 = F('22.5') + F(3,4)*90 - 30 - 16 - F('6.5')
    delayed = F(90)/F('1.1') - 30
    require((pv75, 190+pv75-230, F(70,90), delayed, delayed-40) ==
            (F('37.5'), F('-2.5'), F(7,9), F(570,11), F(130,11)),
            'Exercise 2 scaling, break-even and dated delay')

    qfund = 90+240-F('108.5')
    require((F('248.5')-240, qfund, qfund-190, 250-qfund) ==
            (F('8.5'), F('221.5'), F('31.5'), F('28.5')),
            'Exercise 3 financing shortfall and repaired price')

    p13 = F(850,43)
    require((p13*30, p13*13, p13*30-600, p13*13-190) ==
            (F(25500,43), F(11050,43), F(-300,43), F(2880,43)),
            'Exercise 4 endogenous thirteen-share wealth')
    require(F(30*250,600) == F('12.5') and p13*43-790 == 60,
            'Exercise 4 buyer participation ceiling and total gain')

    xeq = F(30*230,850-230)
    peq = F(850)/(30+xeq)
    pwrong = F(850)/(30+F(230,20))
    require((xeq, peq, xeq*peq, 30*peq, F(230,20)*pwrong) ==
            (F(345,31), F(62,3), 230, 620, F(19550,83)),
            'Exercise 5 fixed-value equation and old-price error')

    p7, eps7 = F(500,27), F(30,27)
    require((eps7, eps7-1, p7*20, p7*20-400, p7*7-100) ==
            (F(10,9), F(1,9), F(10000,27), F(-800,27), F(800,27)),
            'Exercise 6 EPS-positive, wealth-negative case')
    require(F(20*10,20) == 10 and F(20*100,400) == 5,
            'Exercise 6 distinct earnings and value ceilings')

    require((145-110, 145-125, 125+12-145) == (35,20,-8),
            'Exercise 7 goodwill, seller gain and buyer loss are different')

    b = (F(1,4)*20-F(3,4)*4)/F('1.05')-3
    t = (F(1,4)*40-F(3,4)*2)/F('1.05')
    require((b,t,b+t) == (F(-23,21),F(170,21),7),
            'Exercise 8 negative buyer signing decision, positive total')


def check():
    module = load_lab()
    data = json.loads((LAB / 'v08-c09-inputs.json').read_text())
    capture = io.StringIO()
    with redirect_stdout(capture):
        result = module.analyze(data)
    require(not capture.getvalue(), 'analyze() must be quiet')
    json.dumps(result, allow_nan=False)
    snapshot = json.loads((LAB / 'v08-c09-output.json').read_text())
    require(result == snapshot, 'Supplied exact output must reproduce')

    # A backward cash recursion independently prices the finite receipts. This
    # also avoids accepting a helper's dates just because the output is stable.
    control = combination = future_integration = F(0)
    for row in reversed(data['incremental']['annual']):
        control = (control + F(row['control_gross'])-F(row['control_tax']))/F('1.1')
        combination = (combination + F(row['cost_saving']) + F(row['customer_contribution'])
                       - F(row['combination_tax']))/F('1.1')
        future_integration = (future_integration+F(row['integration']))/F('1.1')
    require((control,combination,future_integration) == (F('22.5'),90,4),
            'Backward dated cash valuation')
    net = control+combination-30-12-future_integration-F('6.5')
    require(net == 60 and F(result['baseline']['net_surplus']) == net,
            'One occurrence of every investment, integration and fee payment')
    require([F(row['control_pv']) for row in result['benefit_ledger']] == [F('7.5')]*3 and
            [F(row['combination_pv']) for row in result['benefit_ledger']] == [F(30)]*3,
            'Each payment correctly assigned to T1/T2/T3')

    # Full signed closing ledger, then independently reconcile surviving assets
    # against all common and non-common claims, not just an NPV shortcut.
    require(70+20+F('248.5')-230-60-30-12-F('6.5') == 0, 'Cash sources equal uses')
    funded_ops = F(630+240)+control+combination-future_integration
    cash_equity = funded_ops-100-F('248.5')-10
    require((funded_ops,cash_equity) == (F('978.5'),620), 'Postfunding claim conservation')
    cash = result['baseline']['cash']
    require((F(cash['new_debt']),F(cash['buyer_wealth']),F(cash['buyer_gain']),F(cash['target_gain'])) ==
            (F('248.5'),620,20,40), 'Cash old-buyer and seller wealth')
    require(620+230+100+60+10-(600+190+100+60+10) == net,
            'All old investor classes reconcile; new fair lender contributes no surplus')
    require(cash_equity-60 != 620 and cash_equity-30 != 620,
            'Double retirement or capital deduction would fail the wealth anchor')
    require(result['boundaries']['cash_operating_transaction_value'] == '280' and
            result['boundaries']['financeable_cash_ceiling'] == '463/2' and
            F(cash['funding_slack']) == F('1.5'), 'Offer perimeter and funding limit')

    require(70+20+F('18.5')-60-30-12-F('6.5') == 0, 'Stock deal still has cash uses')
    total = funded_ops-100-F('18.5')-10
    seller_fraction = F(12,42)
    buyer_stock, target_stock = (1-seller_fraction)*total, seller_fraction*total
    require((total,buyer_stock,target_stock) == (850,F(4250,7),F(1700,7)),
            'Stock wealth from ownership and operating claims')
    stock = result['baseline']['stock']
    require((F(stock['post_price']),F(stock['buyer_gain']),F(stock['target_gain'])) ==
            (F(425,21),F(50,7),F(370,7)), 'Fixed-ratio endogenous price')
    require(target_stock-12*20 == F(20,7), 'Old-price headline is not closing consideration')
    xmin, xmax = F(95,11), F(25,2)
    require(xmin*850/(30+xmin) == 190 and 30*850/(30+xmax) == 600,
            'Participation endpoints solve actual wealth equations')
    require(F(result['boundaries']['stock_x_minimum']) == xmin and
            F(result['boundaries']['stock_x_maximum']) == xmax and
            F(result['equivalent_fixed_value_stock']['new_shares']) == F(345,31),
            'Lab participation and fixed-value solution')

    expected_rows = [(60,20,40,F(50,7),F(370,7)),
                     (F('37.5'),F('-2.5'),40,F(-125,14),F(325,7)),
                     (15,-25,40,-25,40)]
    for row, expected in zip(result['realization_sensitivity'], expected_rows):
        values = tuple(F(v) for v in [row['net_surplus'], row['cash']['buyer_gain'],
                        row['cash']['target_gain'], row['stock']['buyer_gain'], row['stock']['target_gain']])
        require(values == expected, 'Realization sensitivity differs from independent anchors')
        require(values[1]+values[2] == values[0] == values[3]+values[4],
                'Both offers must conserve the changed surplus')
    require(len(result['realization_sensitivity']) == 3, 'Complete sensitivity grid')
    require(F(result['one_year_combination_delay']['net_surplus']) == F(570,11),
            'Delay discounts receipts again without moving fixed costs')
    require(90*F(7,9)-70 == 0 and (760+90*F(8,9))*F(5,7)-600 == 0,
            'Cash and stock realization break-even differ')

    eps = result['eps_case']
    require((F(eps['eps_after']),F(eps['buyer_gain']),F(eps['target_gain']),F(eps['combined_pe'])) ==
            (F(15,13),F(-200,13),F(200,13),F(50,3)), 'EPS counterexample reconciles zero created value')
    signing = result['signing_case']
    require((F(signing['buyer_value']),F(signing['target_value']),F(signing['combined_value'])) ==
            (F(31,3),F(590,21),F(269,7)), 'Signing outcomes retain distinct decision date')
    require(F(signing['buyer_break_even_probability']) == F(143,480), 'Signing participation threshold')
    problem_audit()

    # Consequential variants: infeasible financing is reported; zero/negative S
    # does not get relabeled positive; endpoint probabilities are legitimate.
    variant = deepcopy(data)
    variant['consideration']['new_debt_commitment'] = '240'
    answer = module.analyze(variant)
    require(not answer['baseline']['cash']['feasible_under_commitment'] and
            F(answer['baseline']['cash']['funding_gap']) == F('8.5'), 'Real financing gap survives output')
    for fee, surplus in [('66.5',0),('76.5',-10)]:
        variant = deepcopy(data)
        variant['incremental']['fee_at_close'] = fee
        answer = module.analyze(variant)
        require(F(answer['baseline']['net_surplus']) == surplus, 'No artificial positivity restriction on S')
        require(answer['boundaries']['mutually_acceptable_stock_interval_exists'] == (surplus >= 0),
                'Negative surplus has no mutual participation interval')
    variant = deepcopy(data)
    variant['realization_fractions'] = ['0']
    require(module.analyze(variant)['realization_sensitivity'][0]['net_surplus'] == '-30',
            'Zero benefit realization does not erase committed costs')
    for p, combined_signing in [('0',F(-61,7)),('1',F(379,7))]:
        variant = deepcopy(data)
        variant['signing_case']['success_probability'] = p
        require(F(module.analyze(variant)['signing_case']['combined_value']) == combined_signing,
                'Valid signing probability endpoint')

    invalid = []
    for group,key,value in [('incremental','discount_rate','-1'),
                            ('buyer','shares',True), ('buyer','excess_cash','200'),
                            ('consideration','cash_offer','850'),
                            ('signing_case','success_probability','1.1'),
                            ('target','debt','NaN')]:
        variant = deepcopy(data)
        variant[group][key] = value
        invalid.append(variant)
    variant = deepcopy(data)
    variant['incremental']['annual'][1]['year'] = 1
    invalid.append(variant)
    variant = deepcopy(data)
    variant['incremental']['annual'][0]['combination_tax'] = '100'
    invalid.append(variant)
    variant = deepcopy(data)
    variant['realization_fractions'] = ['1.01']
    invalid.append(variant)
    for variant in invalid:
        try:
            module.analyze(variant)
        except ValueError:
            continue
        raise AssertionError('Invalid documented model input was accepted')

    doc = Document()
    doc.feed((ROOT / 'content/chapters/v08-c09.html').read_text())
    require((doc.worked,doc.exercises,doc.solutions) == (4,8,8), 'Complete worked/problem/solution package')
    require(len(doc.ids) == len(set(doc.ids)), 'Unique chapter anchors')
    require('Teach-back' in ''.join(doc.text) and 'Delayed check' in ''.join(doc.text),
            'Teaching and retention sections exist')
    local_assets = {link for link in doc.links if link.startswith('v08-c09-')}
    require(local_assets == {'v08-c09-inputs.json','v08-c09-analysis.py','v08-c09-output.json','v08-c09-README.txt'},
            'Complete flat offline lab routes')
    for asset in local_assets:
        require((LAB / asset).is_file(), 'Missing offline payload: '+asset)
    sources = json.loads((ROOT / 'content/reviews/v08-c09-sources.json').read_text())
    require(set(doc.sources) <= {item['id'] for item in sources}, 'Scoped source proposals cover cited IDs')

    return {'status': 'passed', 'chapter': 'v08-c09', 'groups': 8,
            'checks': ['finite cash recursion and net benefits', 'full cash closing and all claim classes',
                       'endogenous stock price and participation', 'realization and delay sensitivity',
                       'EPS and signing counterexamples', 'all eight determinate exercise solutions',
                       'consequential variants and nine invalid domains', 'quiet exact output and package structure'],
            'limits': ['Original assumptions are supplied, not empirical forecasts',
                       'No real legal/tax transaction review or external academic certification',
                       'Structural checks do not validate visual/mobile/print layout']}


if __name__ == '__main__':
    print(json.dumps(check(), indent=2, ensure_ascii=False, allow_nan=False))
