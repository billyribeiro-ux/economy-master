"""Independent exact fiscal identities, model solutions and portable-lab checks."""
from fractions import Fraction as F
from pathlib import Path
import contextlib
import copy
import importlib.util
import io
import json
import subprocess
import sys
import tempfile

from check_v06_c01 import Chapter

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT/'content/projects'


def need(ok, message):
    if not ok:
        raise ValueError(message)


def demand(c0, c, tau, tax, investment, spending, feedback=F(0), reference=F(0)):
    y = (c0-c*tax+investment+spending+feedback*reference)/(1-c*(1-tau)+feedback)
    n = tax+tau*y
    consumption = c0+c*(y-n)
    inv = investment-feedback*(y-reference)
    need(y == consumption+inv+spending, 'goods market')
    return y, n, consumption, inv, n-spending


def check():
    text = (ROOT/'content/chapters/v06-c09.html').read_text()
    doc = Chapter(); doc.feed(text)
    need(not doc.stack and len(doc.ids) == len(set(doc.ids)), 'chapter structure')
    need((doc.worked, doc.exercises, doc.solutions) == (4, 8, 8), 'chapter package')
    proposals = json.loads((ROOT/'content/reviews/v06-c09-sources.json').read_text())
    need(set(doc.sources) == {x['id'] for x in proposals}, 'source coverage')
    need(all(x['verification'] for x in proposals), 'scoped source inspections')

    # Nominal ledger first; independently dividing by GDP checks the ratio law.
    count = 0
    for debt in (F(40), F(120), F(200)):
        for i in (F(0), F(1,25), F(1,10)):
            for pi in (F(-1,50), F(0), F(1,10)):
                for growth in (F(-1,20), F(0), F(1,25)):
                    z0, p, a = F(200), F(1,50), F(1,100)
                    z = z0*(1+pi)*(1+growth)
                    bill, surplus, adjustment = i*debt, p*z, a*z
                    end = debt+bill-surplus+adjustment
                    need(end/z == (1+i)/((1+pi)*(1+growth))*(debt/z0)-p+a, 'ratio identity')
                    issuance = debt/2+bill-surplus+adjustment
                    need(end == debt-debt/2+issuance, 'maturity reconciliation')
                    count += 1
    need(F(120)*F('1.04')-F('4.2')+6 == F('126.6'), 'worked asset stock')
    need((F('126.6')-6)/210 == F(201,350), 'net debt')
    need(60+F('4.8')-F('4.2')+6 == F('66.6'), 'worked issuance')
    z = 250*F('1.04')*F('.98')
    need(z == F('254.8') and F(161)/z == F(805,1274) and F(154)/z == F(385,637), 'exercise1 ratios')
    need(30+9+5-3 == 41 and 150-30+41 == 161, 'exercise1 cash')
    change = (F('1.08')/(F('1.1')*F('.95'))-1)*F('.75')-F('.024')
    need(change == F(117,104500), 'exercise2 exact')
    need((F('.08')-F('.1')+F('.05'))*F('.75')-F('.024') == F('-.0015'), 'exercise2 approximation')
    real = F('1.08')/F('1.1')-1
    need(real == F(-1,55) and (real+F('.05'))/F('.95') == F(7,209), 'exact real rate')

    alpha, target = F(21,20), F(4,5)
    for phi in (F(0), F(1,4), F(1,20), F(41,20), F(21,10)):
        d = F(9,10)
        for t in range(1,9):
            p = (alpha-1)*target+phi*(d-target)
            d = alpha*d-p
            need(d == target+(alpha-phi)**t*F(1,10), 'feedback closed form')
    need(target+alpha**3*F(1,10) == F('.9157625'), 'unstable example')
    need(target+F(4,5)**3*F(1,10) == F('.8512'), 'stable example')
    need(alpha*F('.9')-F('.05') == F('.895'), 'capped first step')
    need(F('.05')/(alpha-1) == 1 and F('.8')-40*F('.02') == 0, 'fiscal domain boundaries')
    need(F(20)/F('1.1')+F(99)/F('1.21') == 100, 'two-date repayment')
    need(F(20)/F('1.1')+F(88)/F('1.21')+F(11)/F('1.21') == 100, 'terminal term')
    need(F(34,35)*F(4,5)+F(4,175) == F(4,5) and F(35,34)>1, 'bounded-ratio counterexample')

    need(demand(F(10),F(3,4),F(1,5),F(0),F(30),F(40)) == (200,40,130,30,0), 'worked baseline')
    need(demand(F(10),F(3,4),F(1,5),F(0),F(22),F(40)) == (180,36,118,22,-4), 'worked shock')
    need(demand(F(10),F(3,4),F(0),F(40),F(22),F(40)) == (168,40,106,22,0), 'no stabilizer')
    need(demand(F(10),F(3,4),F(1,5),F(0),F(30),F(36)) == (190,38,124,30,2), 'consolidation')
    need(F(158,190) == F(79,95), 'denominator effect')
    need(demand(F(10),F(3,4),F(1,5),F(0),F(30),F(52),F(1,5),F(200)) == (220,44,142,26,-8), 'rate response')
    need(demand(F(10),F(4,5),F(1,4),F(0),F(20),F(30)) == (150,F('37.5'),100,20,F('7.5')), 'exercise5 baseline')
    need(demand(F(10),F(4,5),F(1,4),F(0),F(14),F(30)) == (135,F('33.75'),91,14,F('3.75')), 'exercise5 shock')
    need(demand(F(10),F(4,5),F(0),F('37.5'),F(14),F(30)) == (120,F('37.5'),76,14,F('7.5')), 'exercise5 comparison')
    need(demand(F(10),F(4,5),F(1,4),F(4),F(20),F(34)) == (152,42,98,20,8), 'exercise6 joint instruments')
    need(demand(F(10),F(4,5),F(1,4),F(0),F(20),F(36),F(1,5),F(150)) == (160,40,106,18,4), 'exercise6 rate')
    need(demand(F(10),F(4,5),F(1,4),F(0),F(20),F(26)) == (140,35,94,20,9), 'exercise6 cut')
    need(F('118.5')/140 == F(237,280), 'exercise6 debt ratio')
    # Strict concavity plus these derivative signs certify each constrained optimum.
    for first, total in ((20,80),(30,80),(24,96),(36,96)):
        need(F(1,first)-F(1,total-first)>0, 'credit bound derivative')
        need(total/2 > first, 'unconstrained borrowing')
    need(1-F(3,5)*F(3,4)+F(1,20) == F(3,5), 'retention denominator')

    spec = importlib.util.spec_from_file_location('fiscal_lab', PROJECT/'v06-c09-fiscal.py')
    lab = importlib.util.module_from_spec(spec)
    capture = io.StringIO()
    with contextlib.redirect_stdout(capture), contextlib.redirect_stderr(capture):
        spec.loader.exec_module(lab)
    need(not capture.getvalue(), 'quiet import')
    data = json.loads((PROJECT/'v06-c09-fiscal-inputs.json').read_text())
    result = lab.solve(data)
    need(lab.encoded(result) == json.loads((PROJECT/'v06-c09-fiscal-benchmark.json').read_text()), 'benchmark')
    # Accumulate discounted net cash independently with a direct path convolution.
    for case, out in zip(data['cases'], result['cases']):
        r = 1+F(case['interest']); gamma = (1+F(case['inflation']))*(1+F(case['growth']))
        b0, z0 = F(case['initial_debt']), F(case['initial_gdp'])
        flows = []
        for t, row in enumerate(out['rows'],1):
            need(row['gdp'] == z0*gamma**t, 'independent GDP path')
            flows.append(row['surplus']-row['adjustment'])
            end = b0*r**t-sum(flow*r**(t-j) for j, flow in enumerate(flows,1))
            need(end == row['debt'], 'convolution debt path')
            need(row['debt'] == row['opening_debt']-row['maturing']+row['issuance'], 'funding ledger')
        need(out['discounted_terminal_debt'] == out['rows'][-1]['debt']/r**len(flows), 'discounted endpoint')
    byname = {r['name']:r for r in result['cases']}
    need(byname['path_a']['rows'][-1]['debt'] == F('105.865555'), 'exercise8 A')
    need(byname['path_b']['rows'][-1]['debt'] == F('140.3831'), 'exercise8 B')
    need(byname['feedback']['rows'][-1]['ratio'] == F('.8512'), 'lab feedback')
    need(byname['capped_feedback']['rows'][0]['cap_limited'], 'lab cap flag')
    need(byname['asset_acquisition']['rows'][0]['issuance'] == F('66.6'), 'lab acquisition')

    invalids = []
    for key, value in (('interest', '-1'),('initial_gdp', '0'),('periods', True),
                       ('inflation', 'nan'),('growth', 'inf'),('surplus_cap', '-1'),
                       ('maturity_fraction', '1.1'),('feedback',True),
                       ('adjustment_ratios', []),('primary_base','1')):
        x = copy.deepcopy(data); x['cases'][0][key]=value; invalids.append(x)
    x=copy.deepcopy(data); x['cases'].append(x['cases'][0]); invalids.append(x)
    x=copy.deepcopy(data); x['cases'][0]['unexpected']=1; invalids.append(x)
    for x in invalids:
        try:
            lab.solve(x)
        except ValueError:
            pass
        else:
            raise ValueError('invalid lab input accepted')
    with tempfile.TemporaryDirectory() as directory:
        for flag in ([], ['-O']):
            proc = subprocess.run([sys.executable,*flag,str(PROJECT/'v06-c09-fiscal.py')],cwd=directory,capture_output=True,text=True)
            need(proc.returncode == 0 and not proc.stderr, 'portable lab execution')
            need(json.loads(proc.stdout) == lab.encoded(result), 'portable result')
    return dict(status='passed',worked_examples=4,solved_exercises=8,
                exact_ledger_cases=count,lab_cases=len(result['cases']),invalid_cases=len(invalids),
                checks=['nominal/ratio/cash identities','stability and caps','terminal values',
                        'multipliers and distribution','all exercise anchors','benchmark and portable CLI'])


if __name__ == '__main__':
    print(json.dumps(check(), indent=2))
