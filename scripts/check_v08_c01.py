"""Independent focused checks for the original v08-c01 capital-budgeting package."""
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
from fractions import Fraction as F
from html.parser import HTMLParser
import importlib.util
import io
import json
from math import sqrt
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

BOOK = Path(__file__).resolve().parents[1]
ASSETS = BOOK / 'content/projects'
SCRIPT = ASSETS / 'v08-c01-analysis.py'
INPUT = ASSETS / 'v08-c01-inputs.json'


def need(condition, message):
    if not condition:
        raise AssertionError(message)


def exact(item):
    return F(item['exact'])


def present(cash, rate=F(1, 10)):
    # Independent backward valuation recurrence, not the benchmark discount sum.
    value = F(cash[-1])
    for receipt in reversed(cash[:-1]):
        value = F(receipt) + value/(1+rate)
    return value


class Fragment(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack = []; self.ids = []; self.sources = []; self.worked = 0
        self.exercise_depth = 0; self.solution_depth = 0
        self.exercises = 0; self.solutions = 0; self.ol_depth = 0
        self.links = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        need(tag not in {'html', 'body', 'h1'}, 'chapter must be an unwrapped fragment')
        if 'id' in a: self.ids.append(a['id'])
        if 'data-source' in a: self.sources.append(a['data-source'])
        if tag == 'a': self.links.append(a['href'])
        if 'worked' in a.get('class', '').split(): self.worked += 1
        if tag == 'ol':
            self.ol_depth += 1
            if 'exercises' in a.get('class', '').split(): self.exercise_depth = self.ol_depth
        if tag == 'details' and 'solutions' in a.get('class', '').split(): self.solution_depth = 1
        if tag == 'li' and self.exercise_depth == self.ol_depth: self.exercises += 1
        if tag == 'li' and self.solution_depth: self.solutions += 1
        if tag not in {'br', 'hr', 'img', 'meta', 'link', 'input'}: self.stack.append(tag)

    def handle_endtag(self, tag):
        need(self.stack and self.stack[-1] == tag, 'chapter HTML nesting')
        self.stack.pop()
        if tag == 'ol':
            if self.exercise_depth == self.ol_depth: self.exercise_depth = 0
            self.ol_depth -= 1
        if tag == 'details': self.solution_depth = 0


def check():
    groups = []
    captured, errors = io.StringIO(), io.StringIO()
    with redirect_stdout(captured), redirect_stderr(errors):
        spec = importlib.util.spec_from_file_location('v08_c01_benchmark', SCRIPT)
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        data = module.read_inputs(INPUT)
        report = module.run(data)
    need(not captured.getvalue() and not errors.getvalue(), 'quiet import and run API')
    json.dumps(report, allow_nan=False)
    main = report['main']

    # Independently compare whole-company with/without operating cash and tax.
    # Baseline existing contribution is 20, plus rent 5. New line displaces
    # only the explicitly listed contribution; book/tax depreciation match.
    flows = [F(-105)]; profits = []
    wc = [15, 20, 18, 0]
    for year, (sales, costs, lost) in enumerate(zip([150,170,150], [90,102,90], [6,8,6])):
        before_margin = F(20+5)
        after_margin = F(20-lost+sales-costs-12)
        without_tax = before_margin/4
        with_tax = (after_margin-30)/4
        increment = (after_margin-with_tax)-(before_margin-without_tax)
        ni = (after_margin-30-with_tax)-(before_margin-without_tax)
        terminal = F('13.5') if year == 2 else F(0)
        cash = increment-(wc[year+1]-wc[year])+terminal
        flows.append(cash); profits.append(ni+terminal)
        row = main['rows'][year]
        need(exact(row['operating_cash_before_working_capital']) == increment,
             'whole-firm counterfactual operating cash')
        need(exact(row['after_tax_operating_profit']) == ni,
             'whole-firm incremental profit')
    need(flows == [F(-105),F('30.25'),F('41.75'),F('66.75')], 'main dated cash')
    need([exact(v) for v in main['cash_flows']] == flows, 'benchmark matches independent cash')
    # Signed incremental journal closes each period without inventing funding.
    ledger = {'cash_change': F(-105), 'wc_change': F(15), 'ppe_change': F(90), 'equity_change': F(0)}
    for i in range(3):
        ledger['cash_change'] += flows[i+1]
        ledger['wc_change'] = F(wc[i+1])
        ledger['ppe_change'] -= 30
        ledger['equity_change'] += profits[i]
        need(ledger['cash_change']+ledger['wc_change']+ledger['ppe_change'] == ledger['equity_change'],
             'incremental stock/flow equation each year')
    need(ledger['cash_change'] == ledger['equity_change'] == F('33.75'), 'lifetime operating/disposal closure')
    need(exact(main['npv']) == present(flows) == F(19045,2662), 'backward NPV oracle')
    need(exact(main['sale_tax_cash']) == F('4.5') and exact(main['terminal_tax_basis']) == 0,
         'terminal tax separate from working capital')
    need(exact(main['unfunded_at_time_0']) == 25 and exact(main['time_0_cash_required']) == 105,
         'positive value and separate funding gap')
    groups.append({'name':'Whole-firm counterfactual tax/cash, all-period incremental ledger, backward NPV and dated funding gap','status':'pass'})

    # Economically consequential edits, not a large redundant input matrix.
    sunk = deepcopy(data); sunk['main']['sunk_study'] = 999
    sunk['main']['unchanged_allocated_cost'] = [777]*3
    altered = module.run(sunk)
    need(altered['main']['cash_flows'] == main['cash_flows'] and altered['main']['npv'] == main['npv'], 'sunk and allocated invariance')
    no_rent = deepcopy(data); no_rent['main']['foregone_rent'] = [0]*3
    changed = module.run(no_rent)
    need(exact(changed['main']['npv'])-exact(main['npv']) == present([0,F('3.75'),F('3.75'),F('3.75')]), 'after-tax opportunity-cost transfer')
    slower = deepcopy(data); slower['main']['working_capital_balances'] = [15,24,22,0]
    changed = module.run(slower)
    need([exact(v) for v in changed['main']['cash_flows']] == [F(-105),F('26.25'),F('41.75'),F('70.75')]
         and exact(changed['main']['npv']) == F(17365,2662), 'working-capital deferral and recovery')
    funding = deepcopy(data); funding['main']['committed_time_0_funding'] = 60
    changed = module.run(funding)
    need(exact(changed['main']['unfunded_at_time_0']) == 45 and changed['main']['npv'] == main['npv'], 'funding is not operating value')
    untaxed = deepcopy(data); untaxed['main']['tax_rate'] = 0
    need([exact(v) for v in module.run(untaxed)['main']['cash_flows']] == list(map(F,[-105,32,45,73])), 'zero-tax bridge and gross disposal')
    zero = deepcopy(data); zero['discount_rate'] = 0
    need(exact(module.run(zero)['main']['npv']) == sum(flows), 'zero-rate undiscounted boundary')
    groups.append({'name':'Six economic interventions: sunk/allocation, rent, collection timing, financing, tax and zero-rate limits','status':'pass'})

    # Root brackets are independently evaluated; do not merely compare a copied IRR.
    for c in [flows, [F(-100),F(60),F(72)], [F(-100),F(90)], [F(-100),F(100)]]:
        answer = module.conventional_irr(c); lo, hi = F(answer['lower']), F(answer['upper'])
        need(lo > -1 and hi-lo < F(1,10**20), 'narrow admissible IRR bracket')
        need(present(c, lo) >= 0 and present(c, hi) <= 0, 'root bracket verified by backward recurrence')
    need(abs(main['irr']['estimate']-0.13357868379383475) < 1e-12, 'Kestrel IRR target')
    need(abs(module.conventional_irr([-100,90])['estimate']+0.1) < 1e-12, 'negative conventional root')
    roots = module.two_period_roots([-100,240,-143])
    need([exact(v) for v in roots['roots']] == [F(1,10),F(3,10)], 'all original multiple IRRs')
    need(all(present([-100,240,-143],r) == 0 for r in [F(1,10),F(3,10)]), 'root substitution')
    need(module.two_period_roots([-100,180,-90])['roots'] == [], 'negative discriminant no-root case')
    need(present([-100,240,-143],F(1,5)) == F(25,36), 'positive NPV between roots')
    need(present([80,-96]) == F(-80,11), 'borrowing cash orientation')
    for c in [[-100,240,-143], [80,-96], [-100,0,0]]:
        try: module.conventional_irr(c)
        except ValueError: pass
        else: raise AssertionError('nonconventional or empty-return stream accepted by conventional solver')
    groups.append({'name':'Positive/negative/zero conventional roots, admissible brackets, exact multiple/no-root proofs and borrowing reversal','status':'pass'})

    # Every worked selection example and finite service cash schedule.
    small, large = [-40,56], [-100,130]
    need(present(small)==F(120,11) and present(large)==F(200,11)
         and present([-60,74])==present(large)-present(small)==F(80,11), 'scale and value additivity')
    early, late = [-100,130,0], [-100,0,150]
    need(present(late)>present(early) and present(late,F(1,5))<present(early,F(1,5)), 'timing ranking reversal')
    need(present(late,F(2,13))==present(early,F(2,13)), 'timing crossover')
    costs = report['equal_service']
    need([exact(x) for x in costs[0]['cash_costs']] == [24,30,6]
         and [exact(x) for x in costs[1]['cash_costs']] == [42,5,5], 'replacement dates and equal service')
    need(exact(costs[0]['present_cost'])==present([24,30,6])
         and exact(costs[1]['present_cost'])==present([42,5,5]), 'full service present costs')
    factor = present([0,1,1])
    need(exact(costs[0]['equivalent_annual_cost'])==F('32.4')
         and exact(costs[1]['equivalent_annual_cost'])==F('29.2')
         and F('32.4')*factor==present([24,30,6])
         and F('29.2')*factor==present([42,5,5]), 'annual equivalent with finite matched horizon')
    need(report['capital_budget']=={'feasible_subsets':5,'maximum_npv':{'exact':'38','decimal':38.0},'optimal_sets':[['B','C']]}, 'complete feasible budget selection')
    groups.append({'name':'Exclusive scale/timing, incremental crossover, complete replacement schedule and constrained project set','status':'pass'})

    # Solve every exercise and delayed check independently from its prompt.
    e1_margin=60-35-(5-2)-3; e1_tax=F(e1_margin-10,5)
    need(e1_margin==19 and e1_tax==F('1.8') and e1_margin-e1_tax-(9-6)==F('14.2'), 'E1 counterfactual bridge')
    need(present([0,-4,0,4])==F(-840,1331), 'E2 timing-only NPV change')
    e3_sale=F(20)-F(20-30,4); terminal=e3_sale+8-6*F(3,4)
    need(e3_sale==F('22.5') and terminal==26 and present([0,0,terminal])==F(2600,121), 'E3 terminal tax/cleanup')
    need(present([0,0,F('23.5'),F('2.5')])==F(28350,1331)
         and present([0,0,26])-present([0,0,F('23.5'),F('2.5')])==F(250,1331), 'E3 delayed loss use')
    need(present([-100,60,72])==F(1700,121) and present([-100,60,72],F(1,5))==0, 'E4 conventional equation')
    need([exact(v) for v in module.two_period_roots([-200,500,-312])['roots']]==[F(1,5),F(3,10)]
         and present([-200,500,-312],F(1,4))==F('0.32'), 'E5 multiple roots and rate-specific decision')
    need(80**2-4*50*40==-1600 and module.two_period_roots([-50,80,-40])['roots']==[], 'E5 no-root proof')
    need(present([-80,104,0])==F(160,11) and present([-80,0,128])==F(3120,121)
         and present([-80,104,0],F(1,4))==F('3.2')
         and present([-80,0,128],F(1,4))==F('1.92')
         and present([0,-104,128],F(3,13))==0, 'E6 full timing comparison')
    need(present([-60,F('92.4')])==24 and present([-50,F('75.9')])==19
         and F(84,60)>F(69,50) and 19+19>24 and 60+50>100, 'E7 greedy failure')
    short, long = [36,5,41,5,5],[64,4,4,4,4]
    need(present(short)==F(1194726,14641) and present(long)==F(1122664,14641)
         and present(short)-present(long)==F(72062,14641), 'E8 full horizon')
    need(abs(float(present([36,5,5])/present([0,1,1]))-25.742857142857144)<1e-12
         and abs(float(present(long)/present([0,1,1,1,1]))-24.19013143719026)<1e-12, 'E8 annual equivalents')
    need(present([-70,40,50])==F(930,121) and 70-64==6
         and abs((40+sqrt(15600))/140-1-0.17785685691405684)<1e-12, 'delayed check and funding distinction')
    groups.append({'name':'All eight determinate exercise solutions, counterfactual/tax-timing extensions and delayed retention solved','status':'pass'})

    invalids = []
    def bad(label, modify):
        copy=deepcopy(data);modify(copy)
        try: module.run(copy)
        except (ValueError,KeyError,TypeError): invalids.append(label)
        else: raise AssertionError('invalid domain accepted: '+label)
    bad('units',lambda d:d.update(units='CU'))
    bad('rate at -1',lambda d:d.update(discount_rate='-1'))
    bad('cash timing',lambda d:d.update(timing='midyear'))
    bad('unusable tax convention',lambda d:d.update(tax_convention='carry_forward'))
    bad('tax rate',lambda d:d['main'].update(tax_rate='1.2'))
    bad('excess tax depreciation',lambda d:d['main'].update(tax_depreciation=[40]*3))
    bad('missing final liquidation',lambda d:d['main'].update(working_capital_balances=[15,20,18,4]))
    bad('operating horizon',lambda d:d['main'].update(revenue=[150,170]))
    bad('unsupported replacement',lambda d:d['equal_service'].update(identical_replacement_available=False))
    need(len(invalids)==9, 'domain check coverage')
    # Wrong variants differ by a consequential amount rather than passing balance by coincidence.
    need(present([flows[0]]+[v+30 for v in flows[1:]]) != present(flows), 'detect double depreciation add-back')
    need(present(flows[:-1]+[flows[-1]+F('4.5')])-present(flows)==present([0,0,0,F('4.5')]), 'detect omitted disposal tax')
    need(present([flows[0]+80]+flows[1:])-present(flows)==80, 'detect borrowing treated as project value')
    groups.append({'name':'Nine relevant domain failures and three consequential cash-flow error detectors','status':'pass'})

    html=(BOOK/'content/chapters/v08-c01.html').read_text();parser=Fragment();parser.feed(html);parser.close()
    need(not parser.stack and len(parser.ids)==len(set(parser.ids)), 'balanced fragment and unique IDs')
    need(parser.worked==4 and parser.exercises==8 and parser.solutions==8, 'full pedagogical package counts')
    need(all(f'v08-c01-e{i}' in parser.ids for i in range(1,9)), 'stable exercise anchors')
    proposals=json.loads((BOOK/'content/reviews/v08-c01-sources.json').read_text())
    need(len(proposals)==3 and set(parser.sources)=={p['id'] for p in proposals}, 'scoped source proposals used')
    need(all(set(('id','title','url','use','checked','verification'))<=set(p) for p in proposals), 'source fields')
    need('Teach-back' in html and 'Delayed check' in html and 'Benchmark.' in html and 'Answer.' in html, 'answered teaching and retention')
    for asset in ['v08-c01-inputs.json','v08-c01-analysis.py','v08-c01-results.json','v08-c01-README.txt']:
        need(asset in parser.links and (ASSETS/asset).is_file(), 'offline asset '+asset)
    preserved=json.loads((ASSETS/'v08-c01-results.json').read_text())
    need(preserved==report, 'preserved result matches exact final inputs/benchmark')
    with tempfile.TemporaryDirectory(prefix='v08-c01-check-') as directory:
        target=Path(directory)
        shutil.copy2(SCRIPT,target/SCRIPT.name);shutil.copy2(INPUT,target/INPUT.name)
        command=[sys.executable,str(target/SCRIPT.name)]
        result=subprocess.run(command,cwd=target,text=True,capture_output=True,check=False)
        need(result.returncode==0 and not result.stderr and json.loads(result.stdout)==report, 'portable standard CLI and strict output')
        wrong=deepcopy(data);wrong['units']='CU';(target/'invalid.json').write_text(json.dumps(wrong))
        result=subprocess.run(command+['invalid.json'],cwd=target,text=True,capture_output=True,check=False)
        need(result.returncode!=0 and not result.stdout and 'Input error:' in result.stderr, 'invalid CLI fails without result')
    groups.append({'name':'Four worked cases/eight solution pairs, three scoped sources, offline assets, preserved output and quiet portable CLI','status':'pass'})
    result={'chapter':'v08-c01','status':'pass','checks':groups,'worked_examples':4,'exercises':8,
            'main_npv_exact':str(present(flows)),'main_cash_flows':[str(v) for v in flows],
            'limits':['Original stipulated cases; no current tax/rate/financing evidence.',
                      'Arithmetic does not replace full prose, source-scope and teaching review.',
                      'No browser/mobile/print visual QA or institutional certification.']}
    json.dumps(result,allow_nan=False)
    return result


if __name__=='__main__':
    print(json.dumps(check(),indent=2,allow_nan=False))
