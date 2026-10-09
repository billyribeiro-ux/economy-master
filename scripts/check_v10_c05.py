"""Independent dated-cash reconstructions and portable artifact checks for c05."""
from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from io import StringIO
import json
import math
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT/'content/projects'


def require(condition, label):
    if not condition:
        raise AssertionError(label)


class Audit:
    def __init__(self):
        self.comparisons = 0
        self.rejections = 0
        self.groups = []

    def eq(self, actual, expected, label):
        self.comparisons += 1
        if isinstance(expected, F):
            actual = F(actual)
        require(actual == expected, f'{label}: {actual!r} != {expected!r}')

    def near(self, actual, expected, label):
        self.comparisons += 1
        require(math.isfinite(actual) and abs(actual-expected) <= 1e-10*max(1,abs(expected)), label)


class Fragment(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack, self.ids = [], []
        self.worked = self.exercises = self.solutions = 0
    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        require(tag != 'h1', 'fragment must not duplicate generated title')
        if 'id' in d:
            self.ids.append(d['id'])
        if tag == 'aside' and 'worked' in d.get('class','').split():
            self.worked += 1
        if tag == 'li' and self.stack and self.stack[-1][0] == 'ol':
            if 'exercises' in self.stack[-1][1].get('class','').split():
                self.exercises += 1
            if any(t == 'details' and 'solutions' in at.get('class','').split() for t,at in self.stack):
                self.solutions += 1
        if tag not in ('br','hr','img','meta','link','input'):
            self.stack.append((tag,d))
    def handle_endtag(self, tag):
        require(self.stack and self.stack[-1][0] == tag, 'unbalanced HTML: '+tag)
        self.stack.pop()


def check():
    a = Audit()
    raw = json.loads((ASSETS/'v10-c05-inputs.json').read_text())
    saved = json.loads((ASSETS/'v10-c05-output.json').read_text())
    original = deepcopy(raw)
    capture = StringIO()
    with redirect_stdout(capture), redirect_stderr(capture):
        model = runpy.run_path(str(ASSETS/'v10-c05-analysis.py'))
        result = model['run'](raw)
    a.eq(capture.getvalue(), '', 'quiet import and API')
    a.eq(raw, original, 'API preserves inputs')
    a.eq(result, saved, 'whole reference payload')
    json.dumps(result, allow_nan=False)
    a.groups.append('quiet nonmutating exact API and complete reference output')

    # Borrowing strips are reconstructed as complete date-zero and repayment cash.
    c = result['carry']
    for key,value in {'prepaid_delivery':F('98.04'), 'fair_forward':F('103.2'),
                      'long_value':F('2.09'), 'maturity_borrowing_at_zero':F('98.04'),
                      'maturity_repayment':F('103.2'), 'initial_cash_residual':F(0),
                      'terminal_excess_of_quoted_delivery':-F('2.2')}.items():
        a.eq(c[key], value, 'carry '+key)
    row = c['replication'][0]
    a.eq(row, {'time':'1/2','asset_net_receipt':'2','strip_borrowing_at_zero':'49/25',
               'strip_repayment':'2','interim_net_cash':'0'}, 'complete interim carry record')
    a.eq(F('1.96')+F('98.04')-100, F(0), 'initial funding')
    a.eq(F(3)-1-2, F(0), 'interim funded balance')
    a.eq(F(106)-F('103.2'), F('2.8'), 'quoted106 terminal surplus')
    a.eq(F('2.8')*F('.95'), F('2.66'), 'quoted106 present surplus')
    a.eq(F(108)-101*F('.98'), F('9.02'), 'old long after payout')
    a.near(108/.98,110.20408163265306,'new quote after payout')
    x = result['fx']
    for key,value in {'fair_domestic_per_foreign':F('1.2375'), 'domestic_prepaid_per_foreign':F('1.188'),
                      'foreign_deposit_today':F(1980000), 'domestic_funding_today':F(2376000),
                      'domestic_funding_repayment':F(2475000), 'long_value_domestic':F(-24000),
                      'short_terminal_surplus_domestic':F(25000)}.items():
        a.eq(x[key],value,'FX '+key)
    a.eq(F(2376000)*F('1.08'),F(2566080),'actual domestic repayment')
    a.eq(2500000-F(2566080),F(-66080),'actual funding destroys apparent surplus')
    a.eq(F(2566080)/2000000,F('1.28304'),'funded FX threshold')
    a.groups.append('worked carry date-ledgers and foreign/domestic deposit funding')

    t = result['tree']
    for key,value in {'spot_price':F(90), 'bond_price':F(11,12), 'forward_quote':F(1080,11),
                      'futures_quote':F(100), 'futures_minus_forward':F(20,11),
                      'covariance_spot_discount':-F(5,3),
                      'futures_discounted_value':F(0), 'forward_discounted_value':F(0)}.items():
        a.eq(t[key],value,'tree '+key)
    a.eq(t['node_spot'],['100','80'],'tree traded spot nodes')
    a.eq(t['path_discounts'],['5/6','1'],'tree state discounts')
    a.eq(t['date_one_variation'],['20','-20'],'tree settlement cash')
    a.eq(t['funded_terminal_futures'],['24','-20'],'tree funded cash')
    a.eq(t['forward_terminal'],['240/11','-200/11'],'tree forward cash')
    # Independent state-price portfolios: Arrow prices solve bond and asset costs.
    qa,qb = F(5,12),F(1,2)
    a.eq(120*qa+80*qb,F(90),'state-price spot closure')
    a.eq(qa+qb,F(11,12),'state-price bond closure')
    a.eq(qa*24-qb*20,F(0),'funded futures no initial value')
    a.eq(qa*F(240,11)-qb*F(200,11),F(0),'forward no initial value')
    a.groups.append('stochastic-rate worked example reconstructed with dated Arrow prices')

    m = result['margin']
    expected_rows = [(1,-200,200,200,400,F(604)),
                     (2,300,700,0,700,F('616.08')),
                     (3,-50,650,0,650,F('634.5624'))]
    for row,expected in zip(m['ledger'],expected_rows):
        for key,value in zip(('date','variation','balance_before_call','call','balance_after_call','funding_debt'),expected):
            a.eq(row[key],F(value) if key!='date' else value,'margin row '+str(row['date'])+' '+key)
    for key,value in {'total_variation':F(50), 'total_posted':F(600), 'terminal_release':F(650),
                      'terminal_funding_debt':F('634.5624'), 'funding_cost':F('34.5624'),
                      'net_after_funding':F('15.4376'), 'cash_identity_residual':F(0)}.items():
        a.eq(m[key],value,'margin '+key)
    a.eq(F(400)*F('1.01')*F('1.02')*F('1.03')+200*F('1.02')*F('1.03'),F('634.5624'),'separately accumulated contributions')
    a.groups.append('complete worked variation/margin/debt ledger and terminal reconciliation')

    w = result['swap']
    for key,value in {'annuity':F('1.9'), 'floating_pv':F(94400), 'fixed_pv':F(85500),
                      'payer_fixed_value':F(8900), 'par_fixed':F(118,2375),
                      'single_curve_floating_pv':F(75000), 'single_curve_par':F(3,76),
                      'pv_change_per_fixed_rate_unit':F(-1900000)}.items():
        a.eq(w[key],value,'swap '+key)
    a.eq(w['projected_coupon_amounts'],['15000','25000','60000'],'swap projected coupons')
    for actual,expected in zip(w['single_curve_rates'],[F(6,197),F(8,193),F(8,185)]):
        a.eq(actual,expected,'independent adjacent discount rate')
    a.eq(F(94400)-75000,F(19400),'projection model-value difference')
    a.eq(-F(w['pv_change_per_fixed_rate_unit'])*F('.0001'),F(190),'contract coupon basis-point sensitivity')
    a.eq(result['collateral'],{'fully_reusable_claim_value':'100', 'segregated_funding_repayment':'10150',
                             'segregated_margin_return':'10050','segregated_net_cost':'100'},'collateral principal and cost')
    a.eq(result['basis'],{'sale_receipt':'9400','nominal_futures_receipt':'600','terminal_local_basis':'-2',
                        'cash_before_funding':'10000','cash_after_funding':'9850','matched_quantity':True},'local basis example')
    a.groups.append('separate swap projection/discounting, collateral and basis cash')

    # Prompt-by-prompt numerical oracles, with inputs copied from the questions.
    e1_pv=F(72)-F('1.1')*F('.99')-F('1.4')*F('.96')
    a.eq(e1_pv,F('69.567'),'E1 cash-strip value')
    a.eq(e1_pv/F('.92'),F(69567,920),'E1 quote')
    a.eq(e1_pv-76*F('.92'),-F(353,1000),'E1 old value')
    a.eq(76-e1_pv/F('.92'),F(353,920),'E1 funded surplus')
    # E2 proves equality generally; these values check the stated sign convention.
    for k1,k2 in [(F(90),F(100)),(F(105),F(95))]:
        a.eq((F(100)-k1*F('.9'))-(F(100)-k2*F('.9')),F('.9')*(k2-k1),'E2 sign boundary')
    a.eq(F('.8')*F('.95')/F('.97'),F(76,97),'E3 benchmark quote')
    a.eq(500000*(F('.8')*F('.95')-F('.79')*F('.97')),F(-3150),'E3 long old value')
    upper=F('.801')*F('1.06')/F('1.04');lower=F('.799')*F('1.02')/F('1.07')
    a.eq(upper,F(42453,52000),'E3 executable upper')
    a.eq(lower,F(40749,53500),'E3 executable lower')
    require(lower<F('.792') and F('.790')<upper,'E3 no demonstrated covered arbitrage')
    a.near(120*math.exp(-.06),113.01174403010985,'E4 forward')
    a.near(120*math.exp(-.08)-115*math.exp(-.02),-1.9488858638805624,'E4 old value')
    a.near(math.exp(-.08)*math.exp(.04*2),1,'E4 share accumulation')
    # Independently value Arrow claims first, then both contracts.
    prices=[F(2,5)/F('1.02')/F('1.25'), F(3,5)/F('1.02')/F('.95')]
    d=sum(prices);s=160*prices[0]+70*prices[1]
    a.eq(d,F(904,969),'E5 bond');a.eq(s,F(90640,969),'E5 spot')
    a.eq(s/d,F(11330,113),'E5 forward');a.eq(F(106)-s/d,F(648,113),'E5 gap')
    a.eq(s-106*d,-F(5184,969),'E5 covariance')
    a.eq(prices[0]*F('67.5')-prices[1]*F('34.2'),F(0),'E5 futures price closure')
    # Closed-form accumulation is independent of the model's rolling debt loop.
    e6_debt=300*F('1.005')*F('1.01')*F('1.02')+200*F('1.01')*F('1.02')
    a.eq(e6_debt,F('516.6453'),'E6 borrowed contributions')
    a.eq(F(350)-e6_debt,-F('166.6453'),'E6 net cash')
    a.eq(e6_debt-500,F('16.6453'),'E6 interest')
    a.eq(-50*(83-80),F(-150),'E6 telescoped variation')
    ann=F('0.5')*(F('.98')+F('.94'))
    floating=2000000*(F('.98')*F('.03')+F('.94')*F('.035'))
    fixed=2000000*F('.065')*ann
    a.eq(ann,F('.96'),'E7 annuity');a.eq(floating,F(124600),'E7 floating')
    a.eq(fixed,F(124800),'E7 fixed');a.eq(floating-fixed,F(-200),'E7 value')
    a.eq(floating/2000000/ann,F(623,9600),'E7 par')
    a.eq(2000000*(1-F('.94'))-fixed,F(-4800),'E7 inappropriate single curve')
    a.eq(floating+2000000*F('.5')*F('.98')*F('.02'),F(144200),'E7 known fixing')
    a.eq(F(144200)-fixed,F(19400),'E7 revised net')
    a.eq(103/F('1.02'),F(5150,51),'E8 full reusable collateral')
    a.eq(20000*(1+F('.05')*F('.5')),F(20500),'E8 financing repayment')
    a.eq(20000*(1+F('.01')*F('.5')),F(20100),'E8 collateral return')
    a.eq(20000*(F('.05')-F('.01'))*F('.5'),F(400),'E8 net cost')
    a.eq(F(200)*6/16/100,F(3,4),'E9 contract optimum')
    for h,variance in [(0,360000),(75,270000),(100,280000),(200,520000)]:
        a.eq(F(200**2*9+h*h*16-2*200*h*6),F(variance),'E9 variance at '+str(h))
    for value,expected in [(F(60)/F('.96'),F('62.5')),(F(60)-61*F('.96'),F('1.44')),
                           (F('.12')/F('2.4'),F('.05')),(100000*(F('.12')-F('.045')*F('2.4')),F(1200))]:
        a.eq(value,expected,'delayed retention')
    a.groups.append('all determinate exercise calculations and retention; proof/critique reviewed separately')

    def changed(edit):
        data=deepcopy(raw);edit(data);return model['run'](data)
    swap_rates=changed(lambda d:d['tree'].__setitem__('second_gross',['1','1.2']))
    a.eq(swap_rates['tree']['futures_quote'],F(100),'rate association leaves futures mean')
    a.eq(swap_rates['tree']['forward_quote'],F(1120,11),'rate association changes forward')
    constant=changed(lambda d:d['tree'].__setitem__('second_gross',['1.1','1.1']))
    a.eq(constant['tree']['futures_quote'],constant['tree']['forward_quote'],'deterministic rates quotation equality')
    a.eq(constant['tree']['spot_price'],F(1000,11),'coherent constant-rate spot')
    low_margin=changed(lambda d:d['margin'].__setitem__('maintenance',200))
    a.eq(low_margin['margin']['ledger'][0]['call'],F(0),'equality at maintenance is not breach')
    a.eq(low_margin['margin']['net_after_funding'],F('25.5576'),'maintenance affects funding')
    a.eq(low_margin['margin']['total_variation'],m['total_variation'],'collateral rule does not change variation')
    rate_change=changed(lambda d:d['swap'].__setitem__('fixed_rate','.055'))
    a.eq(rate_change['swap']['payer_fixed_value'],F(-10100),'contract coupon intervention')
    a.eq(rate_change['swap']['floating_pv'],w['floating_pv'],'coupon intervention preserves floating leg')
    no_funding=changed(lambda d:d['margin'].__setitem__('funding_gross',[1,1,1]))
    a.eq(no_funding['margin']['net_after_funding'],F(50),'zero-interest complete cash equality')
    no_carry=changed(lambda d:d['carry']['events'][0].__setitem__('income',1))
    a.eq(no_carry['carry']['prepaid_delivery'],F(100),'zero net carry')
    negative=changed(lambda d:d['carry'].__setitem__('discount','1.05'))
    a.eq(negative['carry']['fair_forward'],F('98.04')/F('1.05'),'negative yield permitted')
    def exercise_six(d):
        d['margin']={'contracts':-2,'multiplier':25,'quotes':[80,84,79,83],
                     'initial':300,'maintenance':200,'funding_gross':['1.005','1.01','1.02']}
    e6=changed(exercise_six)['margin']
    a.eq(e6['terminal_funding_debt'],e6_debt,'short-side portable engine')
    a.eq(e6['total_posted'],F(500),'short-side call principal')
    # Extreme final move forces final cash settlement, not a redundant margin reset.
    deficit=changed(lambda d:d['margin'].__setitem__('quotes',[100,100,100,0]))['margin']
    a.eq(deficit['ledger'][-1]['call'],F(4600),'final negative balance settled exactly')
    a.eq(deficit['terminal_release'],F(0),'no remaining final collateral')
    a.eq(deficit['cash_identity_residual'],F(0),'terminal deficit cash conservation')
    for key in ('carry','fx','tree','swap','collateral','basis'):
        a.eq(no_funding[key],result[key],'independent case unaffected '+key)
    a.groups.append('economic interventions, signed positions, negative yield and terminal shortfall')

    invalid=[
        ('bool spot',lambda d:d['carry'].__setitem__('spot',True)),
        ('float spot',lambda d:d['carry'].__setitem__('spot',100.0)),
        ('nan',lambda d:d['carry'].__setitem__('spot','NaN')),
        ('infinity',lambda d:d['carry'].__setitem__('spot','Infinity')),
        ('zero divisor',lambda d:d['carry'].__setitem__('spot','1/0')),
        ('overprecision',lambda d:d['carry'].__setitem__('spot','1/1000000000001')),
        ('huge integer',lambda d:d['carry'].__setitem__('spot',10**25)),
        ('zero discount',lambda d:d['carry'].__setitem__('discount',0)),
        ('too-late event',lambda d:d['carry']['events'][0].__setitem__('time',1)),
        ('negative prepaid',lambda d:d['carry']['events'][0].__setitem__('income',1000)),
        ('wrong fields',lambda d:d['fx'].__setitem__('unmodeled_fee',1)),
        ('bad sum',lambda d:d['tree'].__setitem__('probabilities',['.4','.4'])),
        ('zero probability',lambda d:d['tree'].__setitem__('probabilities',[0,1])),
        ('negative gross',lambda d:d['tree'].__setitem__('first_gross',-1)),
        ('tree lengths',lambda d:d['tree'].__setitem__('terminal_spot',[100])),
        ('fractional contracts',lambda d:d['margin'].__setitem__('contracts','1/2')),
        ('zero contracts',lambda d:d['margin'].__setitem__('contracts',0)),
        ('maintenance too high',lambda d:d['margin'].__setitem__('maintenance',401)),
        ('funding lengths',lambda d:d['margin'].__setitem__('funding_gross',[1])),
        ('swap gross zero',lambda d:d['swap'].__setitem__('projected_rates',[-2,0,0])),
        ('no accrual',lambda d:d['swap'].__setitem__('accruals',[0,'.5',1])),
        ('invalid simple accumulation',lambda d:d['collateral'].update({'funding_rate':-1,'year_fraction':1})),
        ('basis contracts fractional',lambda d:d['basis'].__setitem__('contracts','1/2')),
    ]
    for label,edit in invalid:
        try:
            changed(edit)
        except ValueError:
            a.rejections += 1
        else:
            raise AssertionError('accepted invalid input: '+label)
    a.groups.append('explicit malformed and financial-domain rejection cases')

    manifest=json.loads((ASSETS/'v10-c05-manifest.json').read_text())
    expected_files={'v10-c05-'+end for end in ('inputs.json','analysis.py','output.json','README.txt')}
    a.eq({entry['file'] for entry in manifest['files']},expected_files,'manifest scope')
    for entry in manifest['files']:
        payload=(ASSETS/entry['file']).read_bytes()
        a.eq(len(payload),entry['bytes'],'manifest length '+entry['file'])
        a.eq(sha256(payload).hexdigest(),entry['sha256'],'manifest digest '+entry['file'])
    with tempfile.TemporaryDirectory(prefix='v10-c05-') as temporary:
        temp=Path(temporary);source=temp/'source';source.mkdir();cwd=temp/'unrelated';cwd.mkdir()
        for name in expected_files:
            shutil.copyfile(ASSETS/name,source/name)
        for flags in ([],['-O']):
            command=[sys.executable]+flags+[str(source/'v10-c05-analysis.py'),'--input',str(source/'v10-c05-inputs.json')]
            proc=subprocess.run(command,cwd=cwd,capture_output=True,text=True,check=True)
            a.eq(json.loads(proc.stdout),saved,'standalone stdout CLI '+str(flags))
            a.eq(proc.stderr,'','quiet successful CLI')
            output=cwd/('optimized.json' if flags else 'normal.json')
            proc=subprocess.run(command+['--output',str(output)],cwd=cwd,capture_output=True,text=True,check=True)
            a.eq(proc.stdout,'','output-file CLI is quiet')
            a.eq(json.loads(output.read_text()),saved,'portable explicit output '+str(flags))
        for text in ('{"schema":"x","schema":"y"}', '{"spot":NaN}'):
            bad=source/'bad.json';bad.write_text(text)
            proc=subprocess.run([sys.executable,'-O',str(source/'v10-c05-analysis.py'),'--input',str(bad)],cwd=cwd,capture_output=True,text=True)
            require(proc.returncode!=0 and proc.stderr,'invalid strict JSON must fail CLI')
            a.rejections += 1
    body=(ROOT/'content/chapters/v10-c05.html').read_text();parser=Fragment();parser.feed(body)
    require(not parser.stack,'unfinished HTML tags')
    a.eq(len(parser.ids),len(set(parser.ids)),'unique anchors')
    a.eq((parser.worked,parser.exercises,parser.solutions),(5,10,10),'chapter package counts')
    require('teach-back' in body.lower() and 'delayed retention' in body.lower(),'teaching gates')
    sources=json.loads((ROOT/'content/sources.json').read_text())
    a.eq({s['id'] for s in sources if s['id'].startswith('v10-c05-')},
         {'v10-c05-haugh-carry','v10-c05-cme-variation','v10-c05-bis-basis'},'registered source routes')
    # Once review records exist, keep their claimed payloads attached to this exact edition.
    for suffix in ('author','accepted'):
        path=ROOT/'content/reviews'/('v10-c05-author.json' if suffix=='author' else 'v10-c05.json')
        if path.exists():
            for entry in json.loads(path.read_text()).get('reviewed_hashes',[]):
                payload=(ROOT/entry['path']).read_bytes()
                a.eq(sha256(payload).hexdigest(),entry['sha256'],'review binding '+entry['path'])
    a.groups.append('manifest, isolated normal/optimized CLI, HTML package and review hashes')
    return {'status':'passed','independent_comparisons':a.comparisons,'invalid_inputs_rejected':a.rejections,
            'worked_examples':5,'solved_exercises':10,'groups':a.groups,
            'limits':'Author recomputation and editorial review; no separate-agent or human certification, market authentication, or visual UI QA.'}


if __name__ == '__main__':
    print(json.dumps(check(),indent=2))
