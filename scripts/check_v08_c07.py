"""Independent exact audit of the original relative-valuation teaching package.

Quiet check() returns strict JSON-compatible evidence; no file writes/network.
Numerical checks cannot authenticate the supplied peer/normalization judgments.
"""
from contextlib import redirect_stdout
from copy import deepcopy
from fractions import Fraction as F
from html.parser import HTMLParser
import importlib.util
import io
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT/'content/projects'


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def module_load():
    spec = importlib.util.spec_from_file_location('v08_c07_benchmark', LAB/'v08-c07-analysis.py')
    module = importlib.util.module_from_spec(spec)
    capture = io.StringIO()
    with redirect_stdout(capture):
        spec.loader.exec_module(module)
    require(capture.getvalue() == '', 'Benchmark import must be quiet')
    return module


class Document(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.worked = self.exercises = self.solutions = 0
        self.ol = self.details = self.exercise_depth = self.solution_depth = 0
        self.ids, self.links, self.text = [], [], []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if 'id' in a:
            self.ids.append(a['id'])
        if tag == 'a':
            self.links.append(a.get('href', ''))
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
        if tag == 'li' and self.exercise_depth and self.exercise_depth == self.ol:
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

    def handle_data(self, value):
        self.text.append(value)


def problem_audit():
    # Worked 1 reconstructs both matched lease conventions and omitted claims.
    assets = 240+80+40+20
    operating = assets-15-5
    require((operating, F(operating,60), F(operating-40,50), F(348,60)) ==
            (360, 6, F('6.4'), F('5.8')), 'Worked 1 claim/lease bridge')
    require(F(320,60) == F(16,3) and F(360,50) == F('7.2') and
            F(300,60) == 5, 'Worked 1 mixed conventions are distinct')

    # Independent capital plus perpetual economic-profit valuation of Worked 2.
    K, R, r, g = F(200), F('.15'), F('.09'), F('.03')
    ep1 = (R-r)*K
    value = K+ep1/(r-g)
    require(value == 400 and F(50-10)*F('.75') == 30 and
            R*(K+6) == F('30.9'), 'Worked 2 productive capital and economic profit')
    require((value/50, value/40, value/250, value-85, (value-85)/10) ==
            (8, 10, F('1.6'), 315, F('31.5')), 'Worked 2 justified multiples and units')
    require(g+24/F(350) == F(69,700) and g+24/F(385) == F(711,7700),
            'Conditional implied rates hold cash and growth fixed')

    # Exercise 1 independent asset/claim conservation.
    claims = 50+20+10+15
    excluded = 12+8
    require(180+claims == 255+excluded and F(255,40) == F('6.375') and
            7*40-claims+excluded == 205, 'Exercise 1 preference/NCI/lease claims')
    recurring = F(42)+6+5-3
    forward = recurring-8+6
    require((recurring, forward, forward-8, 288/forward, 6*(forward+4+2)-288) ==
            (50, 48, 40, 6, 36), 'Exercise 2 recurring exclusions and normalization')

    steady = []
    for rho, growth, target in ((F('.16'),F('.04'),600), (F('.16'),F('.06'),750),
                               (F('.08'),F('.04'),400), (F('.08'),F('.06'),300)):
        nopat = F(60)*F('.8')
        opening = nopat/rho
        investment = opening*growth
        cash = nopat-investment
        # Economic-profit value is independent of the numerator formula.
        capital_value = opening+(rho-F('.1'))*opening/(F('.1')-growth)
        require(capital_value == cash/(F('.1')-growth) == target and
                rho*(opening+investment) == nopat*(1+growth), 'Exercise 3 funded growth')
        steady.append([str(investment), str(cash), str(capital_value)])
    require(steady == [['12','36','600'],['18','30','750'],['24','24','400'],['36','12','300']],
            'Exercise 3 every comparison')
    require((F(600,80), F(600,60), F(600,400), F(750,80), F(400,80), F(300,80)) ==
            (F('7.5'),10,F('1.5'),F('9.375'),5,F('3.75')), 'Exercise 3 displayed multiples')

    multiple = [F(120,20), F(400,50), F(990,90)]
    weights = [F(20,160), F(50,160), F(90,160)]
    pooled = sum(m*w for m,w in zip(multiple,weights))
    require(multiple == [6,8,11] and sum(multiple)/3 == F(25,3) and pooled == F(151,16),
            'Exercise 4 pooled weighted comparison')
    require(8*30-40 == 200 and F(200,12) == F(50,3) and
            pooled*30-40 == F(1945,8) and (pooled*30-40)/12 == F(1945,96),
            'Exercise 4 target equity and per-share units')
    margins = [F(10,100),F(40,200),F(40,400)]
    require(sum(margins)/3 == F(2,15) and sum(margins)/3*450 == 60 and
            F(90,3) == 30 and F(90,700)*450 == F(405,7), 'Exercise 5 scale and cycle weights')
    require(sorted([6,8,6,9,4])[2] == sorted([6,8,6])[1] == 6 and F(90,-5) == -18,
            'Exercise 6 altered selection and nonrankable loss ratio')
    cap, income = F(18)*12, F(24)
    require((cap,cap/income,F(18)/(income/10),F(30)/12,F(18)/(F(30)/12)) ==
            (216,9,F('7.5'),F('2.5'),F('7.2')), 'Exercise 7 share bases and forward EPS')
    require(F(9)/F('1.2') == F('7.5') and 9*24 == cap, 'Exercise 7 split invariance')
    revised = 400-12/F('1.09')
    terminal1 = F('24.72')/F('.06')
    require(terminal1 == 412 and (12+terminal1)/F('1.09') == revised == F(42400,109)
            and 480-90+20 == 410, 'Exercise 8 transition and stipulated transaction decomposition')

    require((F(200,50), F(200,25)) == (4,8), 'Retention 1 cycle denominator')
    require((280-60-15-5+10)/F(7) == 30, 'Retention 2 equity/share bridge')
    n = F(40)*F('.75')*F('.8')
    require(n*(1-F('.03')/F('.12')) == 18 and F(18)/F('.06')/40 == F('7.5'),
            'Retention 3 justified multiple')
    require(sorted([5,5,20])[1] == 5 and F(5+5+20,3) == 10, 'Retention 4 outlier aggregates')
    return {'worked_examples':3, 'exercise_solutions':8, 'answered_retention_items':4,
            'open_reasoning_reviewed':'Peer selection, recovery timing, share definitions, transaction allocation and evidence criteria'}


def check():
    data = json.loads((LAB/'v08-c07-inputs.json').read_text())
    saved = json.loads((LAB/'v08-c07-output.json').read_text())
    module = module_load()
    capture = io.StringIO()
    with redirect_stdout(capture):
        result = module.benchmark(data)
    require(capture.getvalue() == '' and result == saved, 'Quiet API and preserved result equality')
    json.dumps(result, allow_nan=False)
    expected_ev = [360,480,300,720,400,90,385]
    expected_recurring = [60,90,40,70,100,-5,70]
    expected_forward = [60,60,50,80,100,-5,50]
    source_rows = data['peers']+[data['target']]
    outputs = result['candidates']+[result['target']]
    for source, out, ev, recurring, forward in zip(source_rows, outputs, expected_ev,
                                                expected_recurring, expected_forward):
        # Independently balance all capital providers against operating and excluded assets.
        claims = sum(F(source[k]) for k in ('common_equity','financial_debt','lease_claim','noncontrolling_claim'))
        nonoperating = F(source['excess_cash'])+F(source['excluded_holdings'])
        require(claims == ev+nonoperating and F(out['operating_EV']) == ev, 'Every claim/asset row closes')
        adjustments = [F(source['lease_expense_in_subtotal']),F(source['settled_transitory_cost']),
                       -F(source['transitory_gain']),F(source['cycle_adjustment']),F(source['forward_capacity_adjustment'])]
        require(F(source['reported_subtotal']) == F(forward)-sum(adjustments), 'Normalization ledger reverses to source subtotal')
        require(F(out['recurring_common_basis_Y0']) == recurring and
                F(out['normalized_forward_EBITDA_Y1']) == forward and
                F(out['normalized_forward_EBIT_Y1']) == forward-F(source['forward_depreciation']),
                'Every reported, recurring, forward and depreciation boundary')
        require(F(source['common_equity']) == ev-F(out['net_excluded_claims']), 'Reverse bridge returns quoted equity')
    require(result['selection'] == ['P1','P2','P3','P4'] and
            result['candidates'][4]['exclusion_reasons'] == ['different operating/capital model'] and
            result['candidates'][5]['EV_to_normalized_forward_EBITDA'] is None and
            len(result['candidates']) == 6, 'Full candidate register and documented exclusions')
    summary = result['summary']
    require((F(summary['median']),F(summary['arithmetic_mean']),F(summary['pooled_EV_over_EBITDA']),F(summary['EBIT_median'])) ==
            (7,F(29,4),F(186,25),F(39,4)), 'Four different aggregates')
    weights = [F(x,250) for x in (60,60,50,80)]
    require(sum(w*m for w,m in zip(weights,(6,8,6,9))) == F(summary['pooled_EV_over_EBITDA']),
            'Pooled ratio equals explicit denominator-weighted mean')
    require([F(x['median']) for x in summary['leave_one_out_medians']] == [8,6,8,6], 'All leave-one-out medians')
    for name, value in (('median',350),('arithmetic_mean',F(725,2)),('pooled',372),('minimum',300),('maximum',450),('EBIT_median',390)):
        row = result['relative_estimates'][name]
        require((F(row['operating_value']),F(row['common_equity_value']),F(row['CU_per_share'])) ==
                (value,value-85,(F(value)-85)/10), 'Every target estimate/claim/share bridge')
    require(F(result['target']['raw_EV_to_reported_subtotal']) == F(77,16) and
            F(result['target']['EV_to_normalized_forward_EBITDA']) == F(77,10) and
            F(result['incorrect_reported_denominator_application']['operating_value_overstatement']) == 210,
            'Peak earnings apparent cheapness and 210 denominator mismatch')
    dcf = result['conditional_DCF']
    require((F(dcf['NOPAT1']),F(dcf['net_reinvestment1']),F(dcf['FCFF1']),F(dcf['operating_value']),F(dcf['common_equity_value'])) ==
            (30,6,24,400,315), 'DCF cash and value anchors')
    require(F(dcf['operating_value']) == 200+(F('.15')-F('.09'))*200/(F('.09')-F('.03')),
            'DCF matches independently derived capital plus future economic profit')

    permuted = deepcopy(data)
    permuted['peers'].reverse()
    ordered = module.benchmark(permuted)
    require(ordered['relative_estimates'] == result['relative_estimates'] and
            ordered['conditional_DCF'] == dcf, 'Peer permutation cannot change estimates')
    rebased = deepcopy(data)
    rebased['peers'][0].update(reported_subtotal='55',reported_basis='before_lease_payments',lease_expense_in_subtotal='0')
    rebased_result = module.benchmark(rebased)
    require(rebased_result['relative_estimates'] == result['relative_estimates'] and
            rebased_result['summary'] == summary, 'Consistent lease reporting change leaves pricing unchanged')
    extra_cash = deepcopy(data)
    extra_cash['peers'][0].update(common_equity='257',excess_cash='32')
    require(module.benchmark(extra_cash)['relative_estimates'] == result['relative_estimates'],
            'An equal addition to equity and excluded cash does not alter operating value')
    scaled = deepcopy(data)
    money = ('common_equity','financial_debt','lease_claim','noncontrolling_claim','excess_cash','excluded_holdings',
             'reported_subtotal','lease_expense_in_subtotal','settled_transitory_cost','transitory_gain',
             'cycle_adjustment','forward_capacity_adjustment','forward_depreciation')
    for row in scaled['peers']+[scaled['target']]:
        for key in money:
            row[key] = str(3*F(row[key]))
    scaled['target']['ordinary_shares_thousands'] = '30'
    scaled['target_dcf']['forward_sales'] = '750'
    three = module.benchmark(scaled)
    require(three['summary'] == summary and
            F(three['conditional_DCF']['operating_value']) == 1200 and
            three['conditional_DCF']['CU_per_share'] == dcf['CU_per_share'], 'Currency/size/share scaling')

    invalid = []
    def fails(label, change):
        candidate = deepcopy(data)
        change(candidate)
        try:
            module.benchmark(candidate)
        except ValueError:
            invalid.append(label)
        else:
            raise AssertionError('Invalid comparison accepted: '+label)
    fails('mixed price dates',lambda d:d['peers'][0].update(price_date='T1'))
    fails('mixed forecast periods',lambda d:d['peers'][0].update(forecast_period='Y2'))
    fails('duplicate ID',lambda d:d['peers'][1].update(id='P1'))
    fails('double lease addback',lambda d:d['peers'][0].update(reported_basis='before_lease_payments'))
    fails('Boolean money',lambda d:d['target'].update(common_equity=True))
    fails('float input',lambda d:d['target_dcf'].update(stable_growth=0.03))
    fails('g equals r',lambda d:d['target_dcf'].update(stable_growth='9/100'))
    fails('zero continuing distribution',lambda d:d['target_dcf'].update(stable_growth='3/20',operating_discount_rate='1/5'))
    fails('zero shares',lambda d:d['target'].update(ordinary_shares_thousands='0'))
    fails('negative target equity estimate',lambda d:d['target'].update(financial_debt='1000'))
    fails('unsubstantiated target normalization',lambda d:d['target'].update(normalization_supported=False))
    fails('no eligible peers',lambda d:[row.update(normalization_supported=False) for row in d['peers']])

    problems = problem_audit()
    html = (ROOT/'content/chapters/v08-c07.html').read_text()
    document = Document()
    document.feed(html)
    require((document.worked,document.exercises,document.solutions) == (3,8,8), 'Three worked cases and eight full pairs')
    require(len(document.ids) == len(set(document.ids)) and document.ol == document.details == 0,
            'Unique anchors and balanced exercise containers')
    require('Teach-back' in html and 'Delayed check' in html, 'Answered teaching and retention sections')
    require({f'v08-c07-{s}' for s in ('inputs.json','analysis.py','output.json','README.txt')} <= set(document.links),
            'Four flat offline lab links')
    sources = json.loads((ROOT/'content/reviews/v08-c07-sources.json').read_text())
    require(len(sources) == 5 and all({'id','title','url','use','checked','verification'} <= set(s) for s in sources),
            'Five scoped source proposals')
    require({f'sources.html#{s["id"]}' for s in sources} <= set(document.links), 'Every proposed source is cited')
    report = {'status':'passed','groups':[
        'Quiet exact benchmark and preserved strict JSON',
        'Independent seven-row claims and adjustment ledger; complete six-candidate selection',
        'Median, mean, denominator-weighted pool, EBIT comparison and leave-one-out results',
        'Independent economic-profit DCF, implied rates, equity units and mismatch detection',
        'Peer permutation, consistent lease reporting, excluded-cash and size/share invariance',
        'Twelve meaningful invalid comparison contracts rejected',
        'All three worked examples, eight solutions and four retention answers checked',
        'Source-fragment structure, four offline assets and five scoped primary sources'],
        'anchors':{'peer_median':'7','pooled_multiple':'186/25','target_relative_equity':'265','DCF_equity':'315'},
        'problems':problems,'invalid_contracts':invalid,
        'words':len(re.findall(r'\b[\w’−]+\b',' '.join(document.text))),
        'limitations':'Fictional conditional inputs and source-fragment review; no empirical peer or forecast authentication, human certification or browser/print QA.'}
    json.dumps(report,allow_nan=False)
    return report


if __name__ == '__main__':
    print(json.dumps(check(),indent=2,allow_nan=False))
