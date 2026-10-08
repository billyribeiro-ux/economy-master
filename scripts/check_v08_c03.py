"""Independent exact checks of Chapter 8.3's original capital/valuation package.

Quiet check() returns strict JSON-compatible evidence. These checks complement
the full prompt/solution and source review. They do not authenticate business
assumptions, estimate a discount rate, or perform browser/print QA.
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
CHAPTER = ROOT/'content/chapters/v08-c03.html'


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def load_module():
    spec = importlib.util.spec_from_file_location('v08_c03_benchmark', LAB/'v08-c03-analysis.py')
    module = importlib.util.module_from_spec(spec)
    output = io.StringIO()
    with redirect_stdout(output):
        spec.loader.exec_module(module)
    require(output.getvalue() == '', 'Benchmark import must be quiet')
    return module


def reference(data, r=None, g=None):
    """Independent cohort sum and economic-profit oracle; no benchmark helper.

    Track the initial capital and each addition as separate productive cohorts.
    All cohorts face the stated period's return. Value follows the capital plus
    economic-profit identity, not the benchmark's cash-plus-terminal sum.
    """
    p = {key: F(value) for key, value in data['parameters'].items()}
    r = p['operating_discount_rate'] if r is None else r
    g = p['stable_growth'] if g is None else g
    rho_s = p['stable_roic']
    cohorts = [p['initial_operating_capital']]
    book_components = []
    ep_pv = F(0)
    for stage in data['stages']:
        year = stage['year']
        rho = F(stage['roic'])
        capital = sum(cohorts)
        nopat = sum(cohort*rho for cohort in cohorts)
        b = g/rho_s if stage['reinvestment_rate'] == 'terminal' else F(stage['reinvestment_rate'])
        investment = nopat*b
        ep_pv += sum(cohort*(rho-r) for cohort in cohorts)/(1+r)**year
        book_components.append((capital, nopat, investment, nopat-investment))
        cohorts.append(investment)
    capital_h = sum(cohorts)
    h = len(data['stages'])
    remaining_excess_value = (rho_s-r)*capital_h/(r-g)
    value = p['initial_operating_capital']+ep_pv+remaining_excess_value/(1+r)**h
    terminal = capital_h+remaining_excess_value
    equity = value+p['excess_cash_value']+p['nonoperating_asset_value']-p['debt_market_value']
    return {'value': value, 'terminal': terminal, 'capital_h': capital_h,
            'rows': book_components, 'equity': equity,
            'terminal_share': terminal/(1+r)**h/value if value else None}


class Structure(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.worked = 0
        self.exercises = 0
        self.solutions = 0
        self.ol = 0
        self.exercise_depth = 0
        self.detail = 0
        self.solution_depth = 0
        self.ids = []
        self.links = []
        self.text = []

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
            self.detail += 1
            if 'solutions' in a.get('class', '').split():
                self.solution_depth = self.detail
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
            if self.solution_depth == self.detail:
                self.solution_depth = 0
            self.detail -= 1

    def handle_data(self, text):
        self.text.append(text)


def problem_check():
    # Worked 1: explicit cash plus tail, independently checked at horizon 1.
    r, g = F(3, 25), F(1, 25)
    terminal = F('33.28')/(r-g)
    value = F(24)/(1+r)+(32+terminal)/(1+r)**2
    require(terminal == 416 and value == F(2650, 7) and
            terminal/(1+r)**2/value == F(325, 371), 'Worked 1 boundary and share')
    require((24+(32+terminal)/(1+r))/(1+r) == value, 'Worked 1 backward valuation')

    # Steady-return economics: growth alters reinvestment with N1 fixed.
    steady_values = []
    for rho, target in ((F(1, 25), 800), (F(2, 25), 1200), (F(4, 25), 1400)):
        n1, r, g = F(96), F(2, 25), F(1, 50)
        capital = n1/rho
        first_investment = n1*g/rho
        first_cash = n1-first_investment
        # Value capital plus discounted future economic-profit stream.
        ep_value = capital+(rho-r)*capital/(r-g)
        require(ep_value == first_cash/(r-g) == target,
                'Worked 2 growth value and capital/EP cross-check')
        require(rho*(capital+first_investment) == n1*(1+g), 'Worked 2 funded growth')
        steady_values.append(int(ep_value))
    require(F(96)/F(2, 25) == 1200, 'Worked 2 no-growth comparator')
    require(60+F(2, 25)*30 == F('62.4') and
            (60-6+F(2, 25)*30)/60-1 == F(-3, 50), 'Old/new capital mini example')

    # Exercise 1 deliberately has a transition jump different from stable g.
    tv2 = F(42)/F(3, 50)
    ex1 = F(30)/F('1.08')+(40+tv2)/F('1.08')**2
    error = (42-40)/F('.06')/F('1.08')**2
    require(tv2 == 700 and ex1 == F(482750, 729) and error == F(62500, 2187),
            'Exercise 1 next-cash timing and PV error')
    require(F(42, 40)-1 == F(1, 20) != F(1, 50), 'Exercise 1 boundary growth distinction')
    ex2_new = F(1, 8)*32
    require(ex2_new == 4 and 80-F('6.4')+ex2_new == F('77.6') and
            (-F('6.4')+ex2_new)/80 == F(-3, 100), 'Exercise 2 marginal and old earnings')
    ex3 = []
    for gg in (F(0), F(3, 100), F(3, 50)):
        reinvest = F(72)*gg/F(9, 50)
        cash = 72-reinvest
        ex3.append((reinvest, cash, cash/(F(3, 25)-gg)))
    require(ex3 == [(0, 72, 600), (12, 60, F(2000, 3)), (24, 48, 800)],
            'Exercise 3 full stable-growth alternatives')
    require(1-F(3, 25)/F(9, 50) > 0, 'Exercise 3 derivative sign')

    k0, rho, b = F(300), F(3, 20), F(2, 5)
    n, inv = k0*rho, k0*rho*b
    dep, capex, nwc_change = F(240, 20), F(240, 20)+F(4, 5)*inv, F(1, 5)*inv
    require((n, inv, dep, capex, nwc_change, 240+capex-dep, 60+nwc_change, n-inv) ==
            (45, 18, 12, F('26.4'), F('3.6'), F('254.4'), F('63.6'), 27),
            'Exercise 4 independent asset bridge')
    n2 = F(3, 25)*(300+inv)
    require(n2 == F('38.16') and n2/n-1 == F(-19, 125) and
            (F(3, 25)-rho)*k0+F(3, 25)*inv == n2-n,
            'Exercise 4 return fade decomposition')

    k4 = F('606.8348')
    k5, k6 = k4*F('1.03'), k4*F('1.03')**2
    f5, f6 = F('.07')*k4, F('.07')*k5
    require((f5, f6, k6) == (F('42.478436'), F('43.75278908'), F('643.79103932')),
            'Exercise 5 continued capital and cash')
    require(f5/F('1.1')+(f6+k6)/F('1.1')**2 == k4,
            'Exercise 5 horizon extension leaves continuation unchanged')
    extended_share = k6/F('1.1')**6/F(70340, 121)
    require(abs(float(extended_share)-0.6251321329244005) < 1e-14,
            'Exercise 5 terminal-share change')
    ex6 = []
    for gg in (F(0), F('.03'), F('.06')):
        investment = F('589.16')*gg
        cash, close = F('58.916')-investment, F('589.16')+investment
        tv = close*F('.1')*(1-gg/F('.1'))/(F('.1')-gg)
        require(cash+tv == F('648.076') and tv == close, 'Exercise 6 boundary neutrality')
        ex6.append((investment, cash, close))
    require(ex6 == [(0, F('58.916'), F('589.16')),
                    (F('17.6748'), F('41.2412'), F('606.8348')),
                    (F('35.3496'), F('23.5664'), F('624.5096'))],
            'Exercise 6 complete three-policy table')
    require(F('1.08')/F('1.07') > 1 and F('.03')/F('.02') == F(3, 2),
            'Exercise 7 divergence and external funding requirement')
    b8 = F('.04')/F('.2')
    ev8 = 50*(1-b8)/(F('.08')-F('.04'))
    require((b8, ev8, ev8+12+3-100, (ev8+12+3-100)/10) ==
            (F(1, 5), 1000, 915, F('91.5')) and
            F(50)/F('.04') == 1250, 'Exercise 8 omitted investment and claim bridge')
    require(F(24)/F('.06')/F('1.09')**3 == F(400000000, 1295029), 'Retention 1')
    require(80-4+20*F('.15') == 79 and F(-1, 80) == F('-.0125'), 'Retention 2')
    require(F(40)/F('.1') == 40*(1-F('.04')/F('.1'))/(F('.1')-F('.04')) == 400,
            'Retention 3 supported growth neutrality')
    return {'worked_examples': 3, 'exercise_solutions': 8,
            'determinate_retention_items': 3, 'open_retention_items_reviewed': 1,
            'steady_values': steady_values, 'exercise_1_value': str(ex1)}


def check():
    data = json.loads((LAB/'v08-c03-inputs.json').read_text())
    preserved = json.loads((LAB/'v08-c03-output.json').read_text())
    module = load_module()
    capture = io.StringIO()
    with redirect_stdout(capture):
        result = module.benchmark(data)
    require(capture.getvalue() == '', 'Benchmark API must be quiet')
    require(result == preserved, 'Preserved output differs from benchmark')
    json.dumps(result, allow_nan=False)
    base = result['base']
    oracle = reference(data)
    require(F(base['operating_value']) == oracle['value'] == F(70340, 121) and
            F(base['terminal_value']) == oracle['terminal'] == F('606.8348') and
            F(base['equity_value']) == oracle['equity'] == F(51585, 121),
            'Independent cohort/EP valuation and claim bridge')
    require(F(base['value_per_ordinary_share_CU']) == F(10317, 484) and
            F(base['terminal_share_of_operating_value']) == F(137917, 193435),
            'Base units and terminal share')
    anchors = [(500, 100, 50, 50, 550, 20, 60, 10),
               (550, 88, 22, 66, 572, 22, F('39.6'), F('4.4')),
               (572, F('68.64'), F('17.16'), F('51.48'), F('589.16'),
                F('22.88'), F('36.608'), F('3.432')),
               (F('589.16'), F('58.916'), F('17.6748'), F('41.2412'), F('606.8348'),
                F('23.5664'), F('37.70624'), F('3.53496'))]
    keys = ('opening_capital', 'NOPAT', 'net_reinvestment', 'FCFF', 'closing_capital',
            'depreciation', 'capex', 'change_operating_nwc')
    for index, row in enumerate(base['explicit_years']):
        values = {key: F(value) for key, value in row.items() if key != 'year'}
        require(tuple(values[key] for key in keys) == anchors[index], 'Displayed capital/cash table')
        require(tuple(values[key] for key in keys[:4]) == oracle['rows'][index],
                'Every period matches independent productive-cohort sums')
        require(values['sales']-values['cash_operating_cost']-values['operating_tax_paid']
                -values['capex']-values['change_operating_nwc'] == values['FCFF'],
                'Direct operating cash independent of NOPAT-minus-investment form')
        require(values['closing_ppe']+values['closing_operating_nwc'] == values['closing_capital']
                and values['closing_ppe']-values['opening_ppe'] == values['capex']-values['depreciation'],
                'Separate PPE/NWC stocks close')
        require(values['economic_profit'] == values['NOPAT']-F('.1')*values['opening_capital'],
                'Economic profit uses beginning capital')
    require([F(row['next_NOPAT_growth']) for row in base['explicit_years']] ==
            [F('-.12'), F('-.22'), F(-17, 120), F('.03')], 'Finite fade versus naive g=ROIC*b')
    next_year = base['first_continuation_year']
    require(F(next_year['NOPAT']) == F('60.68348') and
            F(next_year['net_reinvestment']) == F('18.205044') and
            F(next_year['FCFF']) == F('42.478436'), 'First continuation capital and cash')

    for cell in result['sensitivity']:
        r, g = F(cell['discount_rate']), F(cell['stable_growth'])
        independent = reference(data, r, g)
        require(F(cell['operating_value']) == independent['value'] and
                F(cell['terminal_value']) == independent['terminal'] and
                F(cell['equity_value']) == independent['equity'] and
                F(cell['terminal_share_of_operating_value']) == independent['terminal_share'],
                'Every sensitivity cell uses independent economic-profit continuation')
    for r, direction in ((F('.08'), 1), (F('.1'), 0), (F('.12'), -1)):
        vals = [F(c['operating_value']) for c in result['sensitivity'] if F(c['discount_rate']) == r]
        if direction == 0:
            require(vals == [F(70340, 121)]*3, 'Growth-neutral row must be exactly flat')
        else:
            require(all(direction*(b-a) > 0 for a, b in zip(vals, vals[1:])),
                    'Growth sensitivity follows the marginal return spread')
    growth6 = next(c for c in result['sensitivity']
                   if F(c['discount_rate']) == F('.1') and F(c['stable_growth']) == F('.06'))
    bad_frozen_boundary = F(base['explicit_present_value'])+F(growth6['terminal_value'])/F('1.1')**4
    require(bad_frozen_boundary-F(70340, 121) == F('17.6748')/F('1.1')**4,
            'Detect omitted boundary-reinvestment change')

    extended = deepcopy(data)
    extended['stages'][-1]['reinvestment_rate'] = '3/10'
    extended['stages'] += [{'year': 5, 'roic': '1/10', 'reinvestment_rate': '3/10'},
                            {'year': 6, 'roic': '1/10', 'reinvestment_rate': 'terminal'}]
    ext = module.benchmark(extended)['base']
    require(F(ext['operating_value']) == F(base['operating_value']) and
            F(ext['terminal_share_of_operating_value']) < F(base['terminal_share_of_operating_value']),
            'Horizon extension is representation invariant at unchanged policy')
    scaled = deepcopy(data)
    for key in ('initial_operating_capital', 'excess_cash_value', 'nonoperating_asset_value',
                'debt_market_value', 'ordinary_shares_thousands'):
        scaled['parameters'][key] = str(2*F(scaled['parameters'][key]))
    doubled = module.benchmark(scaled)['base']
    require(F(doubled['operating_value']) == 2*F(base['operating_value']) and
            F(doubled['equity_value']) == 2*F(base['equity_value']) and
            doubled['value_per_ordinary_share_CU'] == base['value_per_ordinary_share_CU'],
            'Capital/claim/share scaling preserves per-share units')
    zero_cash = deepcopy(data)
    zero_cash['parameters'].update({'stable_roic': '1/20', 'stable_growth': '1/20',
        'excess_cash_value': '0', 'nonoperating_asset_value': '0', 'debt_market_value': '0'})
    zero_cash['stages'] = [{'year': 1, 'roic': '1/20', 'reinvestment_rate': 'terminal'}]
    zero_cash['sensitivity'] = {'discount_rates': ['1/10'], 'stable_growth_rates': ['1/20']}
    zero = module.benchmark(zero_cash)['base']
    require(F(zero['operating_value']) == 0 and zero['terminal_share_of_operating_value'] is None,
            'Zero-distribution boundary has undefined share, not invented percent')

    invalid = []
    def fail(label, modify):
        candidate = deepcopy(data)
        modify(candidate)
        try:
            module.benchmark(candidate)
        except ValueError:
            invalid.append(label)
        else:
            raise AssertionError(f'Invalid model accepted: {label}')
    fail('g equals r', lambda d: d['parameters'].update(stable_growth='1/10'))
    fail('reinvestment above NOPAT', lambda d: d['parameters'].update(stable_growth='11/100', operating_discount_rate='1/5'))
    fail('terminal return jump', lambda d: d['parameters'].update(stable_roic='3/25'))
    fail('terminal policy frozen', lambda d: d['stages'][-1].update(reinvestment_rate='3/10'))
    fail('negative cash operating cost', lambda d: d['stages'][0].update(roic='1'))
    fail('negative residual equity', lambda d: d['parameters'].update(debt_market_value='10000'))
    fail('float input', lambda d: d['parameters'].update(stable_growth=0.03))
    fail('Boolean input', lambda d: d['parameters'].update(initial_operating_capital=True))
    fail('nonconsecutive years', lambda d: d['stages'][1].update(year=3))
    fail('zero first capital', lambda d: d['parameters'].update(initial_operating_capital='0'))

    problems = problem_check()
    html = CHAPTER.read_text()
    document = Structure()
    document.feed(html)
    require((document.worked, document.exercises, document.solutions) == (3, 8, 8),
            'Chapter has three worked cases and eight full prompt/solution pairs')
    require(len(document.ids) == len(set(document.ids)) and document.ol == document.detail == 0,
            'Unique anchors and balanced assessment containers')
    require('Teach-back' in html and 'Delayed check' in html and 'Kestrel' not in html,
            'Teaching/retention and independent named case')
    downloads = {f'v08-c03-{suffix}' for suffix in ('inputs.json', 'analysis.py', 'output.json', 'README.txt')}
    require(downloads <= set(document.links), 'Four flat offline asset links')
    sources = json.loads((ROOT/'content/reviews/v08-c03-sources.json').read_text())
    require(len(sources) == 4 and all({'id','title','url','use','checked','verification'} <= set(s) for s in sources),
            'Four scoped primary-source proposals')
    require({f'sources.html#{s["id"]}' for s in sources} <= set(document.links), 'All source proposals cited')
    result = {'status': 'passed', 'groups': [
        'Quiet benchmark, preserved exact output and strict JSON',
        'Independent productive-cohort and economic-profit valuation; PPE/NWC/cash closure and return fade',
        'Nine coherent sensitivity cells and three return-spread signs; frozen-boundary error detected',
        'Unchanged-policy horizon extension, capital/claim/share scaling and zero-cash boundary',
        'Ten meaningful invalid model contracts rejected',
        'All worked examples, eight solutions and four retention answers independently checked',
        'Chapter structure, four offline assets and four scoped primary sources'
    ], 'anchors': {'operating_value': base['operating_value'], 'equity_value': base['equity_value'],
                   'terminal_value': base['terminal_value'],
                   'terminal_share': base['terminal_share_of_operating_value']},
        'problems': problems, 'invalid_contracts': invalid,
        'words': len(re.findall(r'\b[\w’−]+\b', ' '.join(document.text))),
        'limitations': 'Conditional numerical/source-fragment review; source and economic evidence, timing calibration and UI require separate judgment.'}
    json.dumps(result, allow_nan=False)
    return result


if __name__ == '__main__':
    print(json.dumps(check(), indent=2, allow_nan=False))
