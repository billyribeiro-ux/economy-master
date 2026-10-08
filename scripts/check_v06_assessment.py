"""Independent equation, ledger, transfer and assembly checks for Volume 6.

These checks complement the recorded full prompt/solution and primary-source
reviews. They do not certify behavioral realism, institutional mastery or UI QA.
"""
from contextlib import redirect_stdout
from copy import deepcopy
from fractions import Fraction as F
import importlib.util
import io
import json
import math
from pathlib import Path
import re
import subprocess
import sys
import tempfile

from check_v04_assessment import Sections

ROOT = Path(__file__).resolve().parents[1]


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def solve(matrix, rhs):
    """Small exact Gaussian solve, independently of the benchmark reduction."""
    a = [[F(x) for x in row]+[F(v)] for row, v in zip(matrix, rhs)]
    n = len(a)
    for c in range(n):
        pivot = next((i for i in range(c, n) if a[i][c]), None)
        require(pivot is not None, 'singular reference system')
        a[c], a[pivot] = a[pivot], a[c]
        divisor = a[c][c]
        a[c] = [v/divisor for v in a[c]]
        for i in range(n):
            if i != c:
                factor = a[i][c]
                a[i] = [v-factor*w for v, w in zip(a[i], a[c])]
    return [row[-1] for row in a]


def written_check():
    # Each block reconstructs the result from primitives, rather than asking
    # whether the manuscript contains the same hard-coded answer string.
    checks = []
    require(F(264, 240)/F(126, 120)-1 == F(1, 21), 'diagnostic deflation')
    require(40-3+5 == 42 and 6*2-2**2 == 8 and 6*3-3**2 == 9,
            'diagnostic stock and constrained square')
    require(2+F(2+F(5, 2), 2) == F(17, 4)
            and F(55)/F(11, 10) == 50 and F(20)/F(2, 5) == 50,
            'diagnostic transition, PV and multiplier')
    require((math.log(1)+math.log(9))/2 < math.log(5), 'diagnostic Jensen')
    checks.append('Seven determinate diagnostic calculations; open identification item reviewed separately')

    require(sum((90-10, 140-50)) == 170 == sum((70, 10, 60, 30))
            == 100+40+20+30-20, 'A1 GDP triplet')
    require(170-4+2-100-20-40 == 30-20-4+2 == 8, 'A1 saving/current account')
    require(F(9, 10)*F(36, 100)+F(3, 10)*F(6, 10) == F(63, 125), 'A1 transition')
    for saving, capital, consumption in ((F(3, 10), F(9), F(21, 10)), (F(1, 2), F(25), F(5, 2))):
        output = capital*F(1, 10)/saving
        require(output**2 == capital and (1-saving)*output == consumption,
                'A1 positive steady capital and consumption')
    social = lambda r: 60*(2-r+4*r/(1+r))
    require(social(F(1)) == 180 and social(F(1, 2)) == 170
            and F(9, 16)*4/(1+F(1, 2))**2 == 1, 'A1 research incentives')

    require(30+F(75)/F(5, 4) == 90 and F(90)/F(9, 5) == 50,
            'A2 lifetime resources')
    require((30+4, 75-F(5, 4)*4) == (34, 70)
            and (34+4, 70-F(5, 4)*4) == (38, 65), 'A2 constrained tax timing')
    require(3*F(3, 2)-F(3, 2)**2-F(5, 2) == -F(1, 4), 'A2 entry value')
    flows = ((74, 4, 2), (3, 6, 1), (2, 1, 7))
    require(tuple(map(sum, zip(*flows))) == (79, 11, 10), 'A2 labor column sums')
    u = F(3, 10)
    for _ in range(3):
        u = F(4, 100)*(1-u)+(1-F(16, 100))*u
    require(u == F(157, 625) and 1/F(16, 100) == F(25, 4), 'A2 path/duration')

    require(8+10-15+72+20 == 70+20-15+10+10 == 95, 'A3 bank settlement')
    x, pi = solve([[1, 2], [-F(3, 4), 1]], [3, F(23, 10)])
    require((x, pi) == (-F(16, 25), F(91, 50)), 'A3 pricing joint solve')
    x, pi, j = solve([[1, 0, 1], [-F(1, 2), 1, 0],
                      [-F(1, 2), -F(3, 2), 1]], [-5, 0, 0])
    require((x, j) == (-F(20, 9), -F(25, 9)) and j < -2, 'A3 rejected rule')
    require(-5-(-2) == -3 and F(3, 2)*(-F(3, 2))+F(1, 2)*(-3) < -2,
            'A3 binding floor consistency')
    shocks = [-2, -1, 1, 2]
    xs = [-F(4, 5)*u for u in shocks]; ps = [2+F(2, 5)*u for u in shocks]
    require(sum(a*(b-2) for a, b in zip(xs, ps))/sum(a*a for a in xs) == -F(1, 2),
            'A3 regression covariance')

    debt = 90*F(21, 20)-3+5
    require(debt == F(193, 2) and debt/(150*F(51, 50)) == F(193, 306)
            and 45+F(9, 2)-3+5 == F(103, 2), 'A4 stocks/ratios/issuance')
    request = F(15, 1000)+F(12, 100)*(F(85, 100)-F(75, 100))
    require(request == F(27, 1000) and F(102, 100)*F(85, 100)-F(2, 100) == F(847, 1000),
            'A4 capped debt branch')
    require(65-58 == 7 and 25-5 == 20 and 48-20 == 28 and 48+8-53 == 3,
            'A4 bridge and recovery priority')
    require(55-2-3+8 == 58 and 63-F(11, 10)*58 == -F(4, 5)
            and 55+F(36, 11)-F(3, 11) == 58, 'A4 joint rescue classification')

    require(F(1, 2) < 1 < 3 and 30+30 == 60 and 30*30 > 30*15 > 10*30,
            'A5 Ricardian allocation')
    def surplus(p, tariff):
        demand, supply = 100-2*p, p-10
        return demand, supply, F(50-p)*demand/2, F(p-10)*supply/2, tariff*(demand-supply)
    free, taxed = surplus(F(20), F(0)), surplus(F(26), F(6))
    require(free == (60, 10, 900, 50, 0) and taxed == (48, 16, 576, 128, 192)
            and sum(free[2:])-sum(taxed[2:]) == 54, 'A5 tariff ledger')
    require(-20+(3-9)+4-1 == -23 and (10-15)*F(2, 5) == -2, 'A5 external bridge')
    require(F(6, 5)*F(26, 25) == F(156, 125)
            and F(100)/F(6, 5)*F(63, 50)-104 == 1, 'A5 covered payoff')
    checks.append('All 20 Form A parts: exact accounts, choices, dynamics, regimes, welfare and parity anchors')

    p0, p1, q0, q1 = (2, 4), (3, 3), (10, 5), (12, 4)
    dot = lambda a, b: sum(x*y for x, y in zip(a, b))
    v00, v01, v10, v11 = dot(p0, q0), dot(p0, q1), dot(p1, q0), dot(p1, q1)
    quantity_square = F(v01, v00)*F(v11, v10)
    price_square = F(v10, v00)*F(v11, v01)
    require(quantity_square == F(16, 15) and price_square == F(27, 20)
            and quantity_square*price_square == F(v11, v00)**2, 'B1 Fisher reversal')
    k = 2**1.5
    require(math.isclose(.2*k**(1/3), .1*k) and math.isclose((1/3)*(10/3)**(-1), .1),
            'B1 steady/golden derivative')
    require((F(4, 5)*F(1, 2)+F(1, 5))/F(11, 10) == F(6, 11)
            and F(4, 10)/(F(1, 10)+F(4, 10)) == F(4, 5), 'B1 diffusion normalization')
    require(F(132, 100)**2/F(121, 100)/F(9, 10) == F(8, 5), 'B1 growth residual')

    saving = math.sqrt(17)-3
    require(-2 < saving < 6 and math.isclose(1/(6-saving), (1/(2+saving)+1/(10+saving))/2),
            'B2 precautionary root')
    value = lambda i: F(14, 3)*i-F(7, 12)*i*i
    require(value(2) == 7 and value(3)-value(2) == F(7, 4)
            and F(14, 3)-F(7, 6)*2 == F(7, 3), 'B2 capacity value')
    require(F(1, 10)+F(1, 2)*F(3, 10) < F(3, 10)
            and F(1, 10)+F(3, 4)*F(3, 10) >= F(3, 10), 'B2 invariant branches')
    require(F(1, 10)/(F(1, 10)+F(2, 5)) == F(1, 20)/(F(1, 20)+F(1, 5)) == F(1, 5)
            and F(2, 5)*F(1, 5) == F(2, 25) and F(1, 5)**2 == F(1, 25), 'B2 hazards')

    require(22+42+20 == 85-1 == 84, 'B3 QE and impairment')
    require(F(11, 10)*F(95, 100)/F(1045, 1000) == 1
            and F(106, 100)*(1+1/F(112, 100))/2 == F(2809, 2800), 'B3 exact returns')
    x0, pi0 = -F(4, 9), F(4, 9)
    j0 = max(F(-2), F(3, 2)*pi0+F(1, 2)*x0)
    pi1 = 2*(pi0-F(1, 2)*x0); x1 = x0+j0-pi1
    j1 = max(F(-2), F(3, 2)*pi1+F(1, 2)*x1)
    require((x1, pi1, x1+j1, pi1-F(1, 2)*x1) == (-F(4, 3), F(4, 3), 0, 2),
            'B3 inverse news model')
    require(F(1, 2)**2+1 == F(5, 4) and -3-(-2) == -1, 'B3 feasible optimum')

    require(80*F(1, 20) == 4 and 60*F(1, 20)+20*F(1, 5) == 7, 'B4 coupon cohorts')
    require(F(4)/F(11, 10)+F(4)/F(11, 10)**2+F(44)/F(11, 10)**3 == 40
            and F(4)/F(1, 10) == 40, 'B4 finite/infinite PV')
    sold = 60-20*math.sqrt(7); price = .8-.005*sold
    debt = 18-price*sold; assets = price*(40-sold)
    require(0 < sold < 40 and debt > 0 and math.isclose(assets, 2*debt)
            and math.isclose(debt, 2+4*math.sqrt(7)), 'B4 collateral first root')
    losses = ((1, 8, 20), (5, 7, 10), (3, 6, 14))
    best = tuple(map(min, zip(*losses)))
    regrets = [[v-b for v, b in zip(row, best)] for row in losses]
    expected = [sum(w*v for w, v in zip((F(1, 2), F(1, 3), F(1, 6)), row)) for row in losses]
    require(list(map(max, losses)) == [20, 10, 14] and list(map(max, regrets)) == [10, 4, 4]
            and expected == [F(13, 2), F(13, 2), F(35, 6)], 'B4 criteria')

    wage, rent = solve([[2, 1], [1, 2]], [F(2, 5), 1])
    require((wage, rent) == (-F(1, 15), F(8, 15)), 'B5 rejected full-use price')
    require(2*45+F(45, 2) == F(225, 2) < 120 and 45+2*F(45, 2) == 90
            and 50-35 == 35-20 == 15 and 35**2 > 45*F(45, 2), 'B5 slack-factor allocation')
    require(16*8-8*8-81 == -17 and -17+20 == 3
            and (24*8-F(8*8, 2))-8*8-81 == 15, 'B5 export resource ledger')
    require(F(102, 100)/F(110, 100) == F(51, 55)
            and F(3, 2)*F(108, 100)/F(102, 100) == F(27, 17)
            and F(16, 10)/F(15, 10)*F(102, 100)-F(108, 100) == F(1, 125), 'B5 FX quotes')
    require(7-2-5-(-1) == 1 and -30+(7-2)+9-2 == -18, 'B5 discrepancy/valuation')
    checks.append('All 20 Form B parts: index reversal, global branches, inverse news, cohort interest and boundary trade')

    require(3-1 == 2 and -8+2-4+1 == -9, 'retention NFA')
    require(10+F(22)/F(11, 10) == 30 and F(22)-F(22, 10) == F(99, 5), 'retention liquidity')
    require(F(1, 10)+F(4, 5)**2*F(1, 10) == F(41, 250)
            and 1/F(18, 100) == F(50, 9), 'retention labor')
    require(50-6 == 46-2 and 50-6+10 == 46+10-2, 'retention bank loss')
    require(66-3+2 == 65 and 20+6-3+2 == 25, 'retention debt')
    require((50-15)-(15-10) == 30 and (50-20)-(20-10) == 20
            and F(5, 2)*(5+5) == 25, 'retention tariff')
    require(F(2)-F(23, 2) == -F(19, 2)
            and -F(19, 2)*F(22, 10) == -F(209, 10), 'oral closing FX valuation')
    checks.append('Six retention answers and changed-quote oral transfer recomputed')
    return checks


def project_check():
    program = ROOT/'content/projects/v06-assessment-analysis.py'
    data = json.loads(program.with_name('v06-assessment-data.json').read_text())
    spec = importlib.util.spec_from_file_location('v06_assessment_program', program)
    module = importlib.util.module_from_spec(spec)
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        spec.loader.exec_module(module)
    require(not buffer.getvalue(), 'project import must be quiet')
    result = module.analyze(data)
    p = {k: F(v) for k, v in data['synthetic']['parameters'].items()}
    for s, row in zip(data['synthetic']['scenarios'], result['synthetic']):
        psi, i0, g = (F(s[k]) for k in ('rate_feedback', 'investment_intercept', 'government_consumption'))
        # Unknown order Y,C,I,M,T,r. Six primitive equations, not the reduced formula.
        y, c, inv, imports, taxes, rate = solve([
            [1, -1, -1, 1, 0, 0], [-F(3, 4), 1, 0, 0, F(3, 4), 0],
            [0, 0, 1, 0, 0, 100], [-F(1, 10), 0, 0, 1, 0, 0],
            [-F(1, 5), 0, 0, 0, 1, 0], [-psi, 0, 0, 0, 0, 1]
        ], [g+30, 10, i0+2, 0, 0, F(1, 50)-200*psi])
        require([row[k] for k in ('output', 'consumption', 'investment', 'imports', 'taxes', 'real_rate')]
                == [y, c, inv, imports, taxes, rate], s['id']+' independent goods system')
        public_cash_shortfall = g+4+50-taxes
        require(row['public_issuance'] == public_cash_shortfall
                and row['public_debt'] == 50+public_cash_shortfall
                and row['private_saving']-inv == row['public_debt']-100+row['current_account'],
                s['id']+' primitive public/private financing')
        foreign_uses = imports/2+20+F(5, 2)+2
        foreign_committed = 8+15+10
        loan = max(F(0), foreign_uses-foreign_committed)
        require(row['official_foreign_loan_needed'] == loan
                and row['closing_external_debt'] == 10+loan
                and row['current_account'] == 25-imports
                and row['closing_nfa']+24 == row['current_account'], s['id']+' external cash/stock')
        require(all(v == 0 for v in row['accounting_residuals'].values()), s['id']+' residuals')
        changed = dict(s, government_consumption=str(g+1))
        extra = module.scenario(p, changed)
        require(extra['output']-y == 1/(F(1, 2)+100*psi), 'analytical sensitivity')
    repair = module.scenario(p, {'id':'repair', 'government_consumption':'100/3',
                               'investment_intercept':'20', 'rate_feedback':'0'})
    require([repair[k] for k in ('output','consumption','public_issuance','public_debt_gdp',
                                 'current_account','official_foreign_loan_needed')]
            == [F(560, 3), F(122), F(50), F(15, 28), F(19, 3), F(5, 6)], 're-solved funding repair')
    h = result['historical']
    require(math.isclose((1+h['real_quarter_percent_from_rounded_headline']/100)**4, 1.023)
            and h['implied_deflator_annual_percent_from_rounded_headlines'] == F(200, 93)
            and math.isclose(float(h['constant_monthly_cpi_annual_percent_not_forecast']), 4.907020753480571)
            and h['current_account_q2_revision_billion_usd'] == -F(41, 5)
            and h['current_account_q3_change_using_same_release_billion_usd'] == -F(359, 10),
            'historical transformations')
    require(100*(1-F(5996,10000)/F(625,1000)) == F(508,125), 'rounding compatibility example')

    bad = []
    for key, value in [('e','0'), ('c','1'), ('tax_rate','-1/5'),
                       ('public_maturity','101'), ('external_interest_rate','-1/8')]:
        d = deepcopy(data); d['synthetic']['parameters'][key] = value; bad.append(d)
    d = deepcopy(data); d['observations'][0]['release'] = '2025-01-31'; bad.append(d)
    d = deepcopy(data); d['observations'].append(deepcopy(d['observations'][0])); bad.append(d)
    d = deepcopy(data); d['synthetic']['scenarios'][0]['rate_feedback'] = '-1'; bad.append(d)
    d = deepcopy(data); d['synthetic']['scenarios'][0]['government_consumption'] = '10000'; d['synthetic']['scenarios'][0]['rate_feedback'] = '1'; bad.append(d)
    for d in bad:
        try:
            module.analyze(d)
        except (ValueError, KeyError, TypeError, ZeroDivisionError):
            pass
        else:
            raise AssertionError('invalid source/parameter/domain accepted')
    frozen = json.loads(json.dumps(result, default=module.encode, allow_nan=False))
    with tempfile.TemporaryDirectory(prefix='v06-assessment-') as td:
        for flags in ([], ['-O']):
            run = subprocess.run([sys.executable, *flags, str(program)], cwd=td,
                                 capture_output=True, text=True, check=False)
            require(run.returncode == 0 and not run.stderr and json.loads(run.stdout) == frozen,
                    'portable normal/optimized CLI')
        path = Path(td)/'bad.json'; path.write_text(json.dumps(bad[0]))
        run = subprocess.run([sys.executable, str(program), str(path)], cwd=td,
                             capture_output=True, text=True, check=False)
        require(run.returncode != 0 and not run.stdout and 'Input/model error:' in run.stderr,
                'invalid CLI must fail without a false report')
    return ['Five independent six-equation rational solves; public/private/external cash and stock bridges',
            'Five analytical multiplier perturbations and a separately re-solved public funding repair',
            'Frozen-data annualization/rounding/revisions, nine invalid domain contracts and portable normal/-O CLI']


def check():
    checks = written_check()+project_check()
    text = (ROOT/'content/assessments/v06.html').read_text()
    p = Sections(); p.feed(text)
    require(p.h1 == 1 and len(p.ids) == len(set(p.ids)) and p.depth == 0,
            'unique title/anchors and closed list structure')
    require(p.counts.get(('diagnostic', False)) == 8 and p.counts.get(('diagnostic', True)) == 8
            and p.counts.get(('retention', False)) == 6 and p.counts.get(('retention', True)) == 6,
            'diagnostic/retention answer pairing')
    for form in ('a','b'):
        require(p.counts.get(('form-'+form, False)) == 5
                and p.counts.get(('form-'+form+'-solutions', True)) == 5, 'five solved domains')
        for q in range(1,6):
            for part in 'abcd':
                require(f'id="v06-{form}-q{q}{part}" data-points="5"' in text,
                        'all examination parts individually scored')
    require(len(re.findall(r'data-points="5"', text)) == 40, 'two 100-point forms')
    require({'project','project-guide','project-rubric','oral-transfer','remediation',
             'notation-index','concept-index','volume-synthesis'} <= set(p.ids), 'full package components')
    require({f'v06-c{i:02d}.html' for i in range(1,13)} <= set(p.links), 'twelve chapter routes')
    require('PENDING' not in text and '85/100' in text and '15/20' in text
            and '51/60' in text and '7.5/10' in text, 'finished package and criteria')
    for filename in ('v06-assessment-data.json','v06-assessment-analysis.py'):
        require(filename in p.links and (ROOT/'content/projects'/filename).is_file(), 'offline project assets')
    checks.append('Two 100-point forms, eight diagnostic/six retention solution pairs, project/rubrics and all twelve routes')
    return {'status':'passed', 'checks':checks, 'written_parts':40, 'project_scenarios':5,
            'limits':'Numerical/structural regression checks; full prose/assumption/source peer reviews recorded separately; UI QA pending.'}


if __name__ == '__main__':
    print(json.dumps(check(), indent=2, allow_nan=False))
