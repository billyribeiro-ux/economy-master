"""Independent c01 peer certificates; author helpers/checker are never oracles."""
from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from io import StringIO
from itertools import product
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'content/projects'
REVIEW = ROOT / 'content/reviews/v11-c01-peer.json'
MODEL = ASSETS / 'v11-c01-analysis.py'


def need(condition, message):
    if not condition:
        raise ValueError('c01 peer: ' + message)


def wire(value):
    if isinstance(value, F):
        return str(value)
    if isinstance(value, dict):
        return {k: wire(v) for k, v in value.items()}
    if isinstance(value, list):
        return [wire(v) for v in value]
    if isinstance(value, tuple):
        return tuple(wire(v) for v in value)
    return value


class Audit:
    def __init__(self):
        self.comparisons = 0
        self.interventions = 0
        self.rejections = 0
        self.policies = 0
        self.game_profiles = 0
        self.queue_rows = 0

    def eq(self, actual, expected, label):
        self.comparisons += 1
        need(wire(actual) == wire(expected), label + ': ' + repr(actual) + ' != ' + repr(wire(expected)))


def screening(a, x, got):
    """Enumerate all four signal-contingent lending policies over latent outcomes."""
    x = {k: F(v) for k, v in x.items()}
    states = []
    for kind, mass, success, positive in (
        ('good', x['good_prior'], x['good_success'], x['good_pass']),
        ('bad', 1-x['good_prior'], x['bad_success'], x['bad_pass'])):
        for signal, ps in (('pass', positive), ('fail', 1-positive)):
            for paid, po in ((True, success), (False, 1-success)):
                receipt = x['success_repayment'] if paid else x['failure_recovery']
                states.append((kind, signal, paid, mass*ps*po, receipt))
    a.eq(sum(s[3] for s in states), F(1), 'joint probability normalization')
    choices = list(product((False, True), repeat=2))
    policy_values = []
    for lend_pass, lend_fail in choices:
        policy_values.append(sum((p*(receipt-x['principal'])
                                 for _, signal, _, p, receipt in states
                                 if (lend_pass if signal == 'pass' else lend_fail)), F(0)))
        a.policies += 1
    gross = max(policy_values)
    pooled = sum(p*receipt for _, _, _, p, receipt in states)
    untested = max(policy_values[0], policy_values[-1])
    branches = []
    for signal in ('pass', 'fail'):
        selected = [s for s in states if s[1] == signal]
        mass = sum(s[3] for s in selected)
        if mass:
            receipt = sum(s[3]*s[4] for s in selected)/mass
            branches.append(dict(signal=signal, mass=mass,
                good_posterior=sum(s[3] for s in selected if s[0] == 'good')/mass,
                success_probability=sum(s[3] for s in selected if s[2])/mass,
                expected_receipt=receipt, loan_margin=receipt-x['principal'],
                fund=receipt > x['principal']))
        else:
            branches.append(dict(signal=signal, mass=F(0), good_posterior=None,
                success_probability=None, expected_receipt=None, loan_margin=None, fund=False))
    a.eq(got, dict(funding_threshold_probability=(x['principal']-x['failure_recovery'])/
                  (x['success_repayment']-x['failure_recovery']),
        pooled_success=sum(s[3] for s in states if s[2]), pooled_receipt=pooled,
        pooled_loan_margin=pooled-x['principal'], branches=branches,
        funded_mass_if_tested=sum((b['mass'] for b in branches if b['fund']), F(0)),
        gross_test_policy_value=gross, no_test_policy_value=untested,
        gross_information_value=gross-untested, net_test_policy_value=gross-x['test_cost'],
        optimal_value=max(untested, gross-x['test_cost']),
        choose_test=gross-x['test_cost'] > untested,
        maximum_test_cost_against_no_test=gross-untested), 'all screening policy outputs')
    a.eq(gross >= untested, True, 'constant policies included among contingent policies')


def monitoring(a, raw, got, enumerate_game=False):
    x = {k: F(v) for k, v in raw.items() if k != 'claimants'}
    n = raw['claimants']
    residual = x['success_cash']-x['debt']
    # Rank feasible borrower actions, with prudence first for the specified tie.
    actions = [('prudent', x['prudent_success']*residual),
               ('divert', x['divert_success']*residual+x['private_benefit'])]
    action = max(actions, key=lambda item: item[1])[0]
    old = x[action+'_success']*x['debt']
    new = x['prudent_success']*x['debt']

    def payoff(profile, j):
        return (new if any(profile) else old)/n - x['audit_cost']*profile[j]

    none = (False,)*n
    deviation = (True,)+(False,)*(n-1)
    not_worse = payoff(none, 0) >= payoff(deviation, 0)
    strictly_better = payoff(none, 0) > payoff(deviation, 0)
    a.eq(got, dict(borrower_prudent_payoff=actions[0][1],
        borrower_divert_payoff=actions[1][1], unmonitored_action=action,
        borrower_divert_payoff_after_enforcement=x['divert_success']*residual,
        unmonitored_receipt=old, monitored_receipt=new, aggregate_audit_gain=new-old,
        one_claimant_audit_gain=new/n-old/n, no_audit_is_nash_given_loan=not_worse,
        no_audit_is_strict_given_loan=strictly_better,
        pooled_initial_funding=x['principal']+x['audit_cost']+x['delegation_cost'],
        pooled_expected_surplus=new-x['principal']-x['audit_cost']-x['delegation_cost'],
        pooled_funding_is_profitable=new > x['principal']+x['audit_cost']+x['delegation_cost'],
        unmonitored_expected_surplus=old-x['principal'],
        all_duplicate_expected_surplus=new-x['principal']-n*x['audit_cost'],
        largest_delegation_cost_for_nonnegative_surplus=new-x['principal']-x['audit_cost'],
        private_benefit_indifference=actions[0][1]-x['divert_success']*residual),
        'borrower and lender action payoffs')
    if enumerate_game:
        equilibria = []
        for profile in product((False, True), repeat=n):
            best = True
            for j in range(n):
                changed = profile[:j]+(not profile[j],)+profile[j+1:]
                if payoff(changed, j) > payoff(profile, j):
                    best = False
            if best:
                equilibria.append(profile)
            a.game_profiles += 1
        a.eq(sorted(sum(p) for p in equilibria), [1]*6,
             'six players: precisely six single-enforcer pure equilibria')


def bank(a, raw, got):
    x = {k: F(v) for k, v in raw.items()}
    # Post each transaction to independent asset, liability and capital accounts.
    accounts = [x['a_reserves'], x['a_loans'], x['a_deposits'],
                x['a_reserves']+x['a_loans']-x['a_deposits'],
                x['b_reserves'], x['b_loans'], x['b_deposits'],
                x['b_reserves']+x['b_loans']-x['b_deposits']]
    L, P = x['new_loan'], x['external_payment']
    changes = [(0,)*8, (0,L,L,0,0,0,0,0), (-P,0,-P,0,P,0,P,0)]
    names = ['initial', 'loan_credits_A_deposit', 'external_settlement_to_B']

    def snapshot(v):
        cash, loans, deposits, capital = v
        a.eq(cash+loans, deposits+capital, 'double-entry accounting identity')
        assets = cash+loans
        return dict(reserves=cash, loans=loans, assets=assets, deposits=deposits,
                    equity=capital, equity_assets=capital/assets if assets > 0 else None)

    expected = []
    for name, delta in zip(names, changes):
        accounts = [old+change for old, change in zip(accounts, delta)]
        expected.append(dict(event=name, A=snapshot(accounts[:4]), B=snapshot(accounts[4:]),
            consolidated=snapshot([accounts[j]+accounts[j+4] for j in range(4)])))
    a.eq(got['two_bank_ledger'], expected, 'all two-bank dated journal accounts')
    opening = accounts[:4]
    probe = x['immediate_withdrawal_probe']
    a.eq(got['immediate_probe_before_income'], dict(requested=probe, cash_available=opening[0],
        cash_gap=max(F(0), probe-opening[0]), executable=probe <= opening[0],
        book_equity=opening[3]), 'earlier probe, before all later receipts')
    I, fee, J, O, loss = (x[k] for k in ('interest_received', 'fees_received', 'interest_paid',
                                          'operating_cash_cost', 'direct_unprovided_loss'))
    events = [('opening_after_settlement', (0,0,0,0)),
              ('external_loan_interest', (I,0,0,I)), ('external_fee_receipt', (fee,0,0,fee)),
              ('external_interest_payment', (-J,0,0,-J)),
              ('external_operating_payment', (-O,0,0,-O)),
              ('confirmed_loss_without_prior_allowance', (0,-loss,0,-loss))]
    current = opening[:]
    income = []
    for event, delta in events:
        current = [v+d for v, d in zip(current, delta)]
        income.append(dict(event=event, **snapshot(current)))
    a.eq(got['A_later_income_ledger'], income, 'all later income journals and direct loss')
    avgloan = (opening[1]+current[1])/2
    avgasset = (sum(opening[:2])+sum(current[:2]))/2
    avgcapital = (opening[3]+current[3])/2
    profit = current[3]-opening[3]
    ratio = lambda numerator, denominator: numerator/denominator if denominator > 0 else None
    expect = dict(net_interest_income=I-J, net_external_cash_receipts=current[0]-opening[0],
        direct_loss_without_prior_allowance=loss, profit=profit, average_earning_loans=avgloan,
        average_assets=avgasset, average_equity=avgcapital, net_interest_margin=ratio(I-J, avgloan),
        return_on_assets=ratio(profit, avgasset), return_on_equity=ratio(profit, avgcapital),
        gross_loan_yield=ratio(I, avgloan), deposit_funding_rate=ratio(J, opening[2]),
        closing_book_insolvent=current[3] < 0)
    a.eq({k: got[k] for k in expect}, expect, 'income and denominator conventions')


def liquidity(a, raw, got):
    M, lam, ell, R, c, shift = (F(raw[k]) for k in ('initial_fund', 'early_fraction',
        'liquidation_return', 'maturity_return', 'early_claim', 'utility_shift'))
    utility = lambda consumption: -1/(consumption+shift)

    def queue(w):
        # Normalize uniform queue rank to [0,1]. Integrate its two constant payoffs.
        served_interval = min(F(1), ell/(w*c))
        lottery = [(served_interval, c), (1-served_interval, F(0))]
        mean = sum(p*cash for p, cash in lottery)
        eu = sum(p*utility(cash) for p, cash in lottery)
        paid = M*w*mean
        retained = M-paid/ell
        waiter_count = M*(1-w)
        waiting = R*retained/waiter_count if waiter_count else None
        a.eq(eu <= utility(mean), True, 'concavity under queue lottery')
        a.queue_rows += 1
        return dict(withdrawal_fraction=w, claimant_mass=M*w,
            served_mass=M*w*served_interval, served_probability=served_interval,
            date1_cash_paid=paid, long_asset_liquidated=paid/ell, long_asset_held=retained,
            date2_cash_available=R*retained, waiter_mass=waiter_count, cash_per_waiter=waiting,
            expected_cash_per_withdrawer=mean, expected_utility_per_withdrawer=eu)

    normal, run = queue(lam), queue(F(1))
    # Residual late resources minus promised c per late unit is affine in w.
    intercept, slope = R-c, c-R*c/ell
    threshold = -intercept/slope
    candidate_eu = lam*normal['expected_utility_per_withdrawer']+(1-lam)*utility(normal['cash_per_waiter'])
    autarky = lam*utility(ell)+(1-lam)*utility(R)
    a.eq(got, dict(candidate_no_run=normal, full_run=run,
        scenarios=[queue(F(w)) for w in raw['withdrawal_fractions']],
        withdrawal_capacity_fraction=ell/c, late_indifference_withdrawal_fraction=threshold,
        candidate_no_run_fully_pays_early=normal['served_probability'] == 1,
        candidate_no_run_incentive_compatible=normal['served_probability'] == 1 and
            normal['cash_per_waiter'] >= c, candidate_no_run_expected_utility=candidate_eu,
        direct_all_long_expected_utility=autarky, candidate_utility_gain_over_all_long=candidate_eu-autarky,
        full_run_wait_deviation_consumption=F(0), full_run_wait_deviation_utility=utility(F(0)),
        full_run_withdrawal_is_strict_best_reply=run['expected_utility_per_withdrawer'] > utility(F(0))),
        'queue integration, asset resources and private-type expected utilities')
    a.eq((threshold > 0, threshold < ell/c, ell/c < 1), (True,True,True),
         'strict threshold ordering')
    a.eq(intercept+slope*threshold, F(0), 'late resource surplus zero at threshold')
    # Verify the quotient derivative by its exact finite-difference identity.
    low, high = threshold/2, (threshold+ell/c)/2
    payoff = lambda w: R*(1-w*c/ell)/(1-w)
    secant = (payoff(high)-payoff(low))/(high-low)
    a.eq(secant, R*(1-c/ell)/((1-low)*(1-high)), 'exact declining-payoff secant')
    a.eq(secant < 0, True, 'waiting resources fall strictly before exhaustion')


class Chapter(HTMLParser):
    def __init__(self):
        super().__init__()
        self.worked = 0
        self.exercise = False
        self.solution = False
        self.prompts = 0
        self.solutions = 0
        self.ids = []
        self.sources = set()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'id' in attrs:
            self.ids.append(attrs['id'])
        classes = attrs.get('class', '').split()
        if tag == 'aside' and 'worked' in classes:
            self.worked += 1
        if tag == 'ol' and 'exercises' in classes:
            self.exercise = True
        if tag == 'details' and 'solutions' in classes:
            self.solution = True
        if tag == 'li':
            self.prompts += self.exercise
            self.solutions += self.solution
        if 'data-source' in attrs:
            self.sources.add(attrs['data-source'])

    def handle_endtag(self, tag):
        if tag == 'ol':
            self.exercise = False
        if tag == 'details':
            self.solution = False


def check():
    a = Audit()
    saved_bytecode = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        capture = StringIO()
        with redirect_stdout(capture), redirect_stderr(capture):
            candidate = runpy.run_path(str(MODEL))['run']
        a.eq(capture.getvalue(), '', 'quiet candidate import')
        baseline = json.loads((ASSETS/'v11-c01-inputs.json').read_text())

        def evaluate(data):
            before = deepcopy(data)
            quiet = StringIO()
            with redirect_stdout(quiet), redirect_stderr(quiet):
                got = candidate(data)
            a.eq(quiet.getvalue(), '', 'quiet public run(data)')
            a.eq(data, before, 'run does not mutate input')
            json.dumps(got, allow_nan=False)
            return got

        result = evaluate(baseline)
        a.eq(result, json.loads((ASSETS/'v11-c01-output.json').read_text()), 'saved full baseline')
        for name, oracle in (('screening',screening), ('monitoring',monitoring), ('bank',bank), ('liquidity',liquidity)):
            oracle(a, baseline[name], result[name])

        def change(section, updates, oracle):
            varied = deepcopy(baseline)
            varied[section].update(updates)
            got = evaluate(varied)
            oracle(a, varied[section], got[section])
            a.interventions += 1
            return got[section]

        changed = change('screening', {'good_prior':'1/2'}, screening)
        a.eq((changed['net_test_policy_value'], changed['maximum_test_cost_against_no_test']),
             ('-1/2','5/2'), 'exercise 1 changed population')
        for updates in ({'test_cost':'22/5'}, {'test_cost':'440000001/100000000'},
                        {'good_pass':'1/2','bad_pass':'1/2'},
                        {'good_pass':'1/5','bad_pass':'4/5'},
                        {'good_pass':'1','bad_pass':'1'},
                        {'good_prior':'0','bad_pass':'0'},
                        {'principal':'10'}, {'principal':'1000'},
                        {'principal':'755/7'}):
            change('screening', updates, screening)
        a.eq(F(14,25)*F(75,14), F(3), 'exercise 2 test costs across all applicants')
        a.eq(F(14,25)*(F(55,7)-F(75,14)), F(7,5), 'exercise 2 funded cost allocation')
        for updates in ({'claimants':6}, {'claimants':8}, {'audit_cost':'3'},
                        {'private_benefit':'6'}, {'delegation_cost':'3'}, {'debt':'0'}):
            fn = (lambda audit,x,g: monitoring(audit,x,g,True)) if updates == {'claimants':6} else monitoring
            change('monitoring', updates, fn)
        a.eq(F(108,6)-5-F(72,6), F(1), 'exercise 3 enforcer benefits by staying')
        a.eq(F(108,6)-5-F(108,6), F(-5), 'exercise 3 duplicate enforcer loses cost')
        for updates in ({'new_loan':'18','external_payment':'18'},
                        {'new_loan':'18','external_payment':'0'},
                        {'direct_unprovided_loss':'22'}, {'direct_unprovided_loss':'25'},
                        {'direct_unprovided_loss':'26'}, {'direct_unprovided_loss':'43'},
                        {'a_reserves':'200','a_loans':'0','new_loan':'0','external_payment':'0',
                         'interest_received':'0','direct_unprovided_loss':'0'}):
            change('bank', updates, bank)
        # Exercise 5 independently posts financing before the withdrawal.
        for cash, loans, deposits, otherdebt, capital in (
            (5,162,144,0,23), (0,162,139,0,23),
            (5,162,144,5,18), (0,162,139,5,18), (0,162,139,0,23)):
            a.eq(cash+loans, deposits+otherdebt+capital, 'exercise 5 financing transaction identity')
        for updates in (
            {'early_fraction':'8/11','withdrawal_fractions':['8/11','10/11','1']},
            {'early_fraction':'4/5','withdrawal_fractions':['4/5','10/11','1']},
            {'early_fraction':'19/20','withdrawal_fractions':['19/20','1']},
            {'withdrawal_fractions':['1/4','799/1100','8/11','801/1100','999/1100','10/11','1001/1100','1']},
            {'liquidation_return':'4/5'}, {'initial_fund':'7/2'}, {'utility_shift':'1'}):
            change('liquidity', updates, liquidity)
        a.eq(-F(515,744)+F(245,352), F(125,32736), 'exercise 7 insurance utility gain')
        a.eq(F(10,11)*(-F(5,6))+F(1,11)*(-10), -F(5,3), 'exercise 7 full-run lottery')
        a.eq(-F(5,3) < -F(10,11), True, 'expected utility strictly below utility of mean cash')

        def reject(data, label):
            before = deepcopy(data)
            quiet = StringIO()
            try:
                with redirect_stdout(quiet), redirect_stderr(quiet):
                    candidate(data)
            except ValueError:
                a.rejections += 1
            else:
                raise ValueError('c01 peer: invalid input accepted: '+label)
            a.eq(data, before, 'rejection preserves input')
            a.eq(quiet.getvalue(), '', 'API rejection is quiet')

        for value in (None, [], True, {}, dict(baseline, surprise='0')):
            reject(value, 'root exact object')
        for value in (True, 100, 100.0, None, '1e2', '01', '+1', ' 1', '1/0', '1/-2',
                      'NaN', '1/1000000001', '1'*33, '-1'):
            bad = deepcopy(baseline); bad['screening']['principal'] = value
            reject(bad, 'bounded rational syntax')
        for section, updates in (
            ('screening', {'good_prior':'101/100'}), ('screening', {'principal':'0'}),
            ('screening', {'failure_recovery':'120'}), ('screening', {'test_cost':'1001'}),
            ('monitoring', {'claimants':True}), ('monitoring', {'claimants':1001}),
            ('monitoring', {'claimants':0}), ('monitoring', {'debt':'140'}),
            ('monitoring', {'prudent_success':'3/5'}),
            ('bank', {'a_deposits':'150'}), ('bank', {'external_payment':'25'}),
            ('bank', {'new_loan':'23'}), ('bank', {'immediate_withdrawal_probe':'145'}),
            ('bank', {'direct_unprovided_loss':'163'}), ('bank', {'operating_cash_cost':'20'}),
            ('liquidity', {'initial_fund':'0'}), ('liquidity', {'early_fraction':'1'}),
            ('liquidity', {'liquidation_return':'1/20'}), ('liquidity', {'maturity_return':'1'}),
            ('liquidity', {'early_claim':'1'}), ('liquidity', {'utility_shift':'0'}),
            ('liquidity', {'withdrawal_fractions':[]}),
            ('liquidity', {'withdrawal_fractions':['1/4']*17}),
            ('liquidity', {'withdrawal_fractions':['1/4','1/4']}),
            ('liquidity', {'withdrawal_fractions':['1/5']}),
            ('liquidity', {'withdrawal_fractions':['1','1/2']})):
            bad = deepcopy(baseline); bad[section].update(updates); reject(bad, section)
        for section in ('screening','monitoring','bank','liquidity'):
            bad = deepcopy(baseline); bad[section]['unexpected'] = '0'; reject(bad, 'extra key')
            bad = deepcopy(baseline); del bad[section][next(iter(bad[section]))]; reject(bad, 'missing key')
        bad = deepcopy(baseline); bad['schema'] = 'future'; reject(bad, 'schema')

        portable_runs, cli_rejections = portable(a, baseline, result)
        chapter = Chapter()
        chapter.feed((ROOT/'content/chapters/v11-c01.html').read_text())
        a.eq((chapter.worked,chapter.prompts,chapter.solutions), (4,8,8), 'four worked and eight complete solutions')
        a.eq(len(chapter.ids), len(set(chapter.ids)), 'unique section IDs')
        a.eq(chapter.sources, {'v06-c06-boe-creation','v11-c01-diamond-monitoring','v11-c01-diamond-dybvig'},
             'exact scoped citations')
        bound = bindings(a)
        return dict(chapter='v11-c01', status='passed', comparisons=a.comparisons,
            economic_interventions=a.interventions, rejected_api_inputs=a.rejections,
            screening_policies=a.policies, monitoring_action_profiles=a.game_profiles,
            integrated_queue_rows=a.queue_rows, portable_runs=portable_runs,
            cli_rejections=cli_rejections, bound_author_files=bound, bound_peer_checker=True)
    finally:
        sys.dont_write_bytecode = saved_bytecode


def portable(a, baseline, expected):
    runs = 0
    rejections = 0
    with tempfile.TemporaryDirectory(prefix='c01-peer-') as temporary:
        directory = Path(temporary)
        lab = directory/'lab'; lab.mkdir()
        source = lab/MODEL.name
        inputfile = lab/'v11-c01-inputs.json'
        for name in ('analysis.py','inputs.json','output.json','README.txt','manifest.json'):
            shutil.copyfile(ASSETS/('v11-c01-'+name), lab/('v11-c01-'+name))
        api_code = """import contextlib,copy,io,json,runpy,sys
sys.dont_write_bytecode=True
capture=io.StringIO()
with contextlib.redirect_stdout(capture),contextlib.redirect_stderr(capture):
    ns=runpy.run_path(sys.argv[1]);data=json.load(open(sys.argv[2]));before=copy.deepcopy(data)
    result=ns['run'](data)
if capture.getvalue() or data!=before:raise RuntimeError('quiet/nonmutating contract')
print(json.dumps(result,sort_keys=True,allow_nan=False))
"""
        aliases = [inputfile,source]
        for protected in (inputfile,source):
            for kind in ('symbolic','hard'):
                alias = directory/(kind+'-'+protected.name)
                if kind == 'symbolic': alias.symlink_to(protected)
                else: os.link(protected,alias)
                aliases.append(alias)
        for optimized in (False,True):
            python = [sys.executable]+(['-O'] if optimized else [])
            proc = subprocess.run(python+['-c',api_code,str(source),str(inputfile)], cwd=directory,
                                  capture_output=True, timeout=15)
            a.eq((proc.returncode,proc.stderr), (0,b''), 'isolated public API execution')
            a.eq(json.loads(proc.stdout), expected, 'portable API exact result')
            runs += 1
            for default in (False,True):
                output = lab/'v11-c01-output.json' if default else directory/'explicit.json'
                args = [] if default else ['--input',str(inputfile),'--output',str(output)]
                proc = subprocess.run(python+[str(source)]+args, cwd=directory,
                                      capture_output=True, timeout=15)
                a.eq((proc.returncode,proc.stdout,proc.stderr), (0,b'',b''), 'quiet isolated CLI')
                a.eq(output.read_bytes(), (ASSETS/'v11-c01-output.json').read_bytes(), 'portable CLI exact bytes')
                runs += 1
            original = inputfile.read_text()
            malformed = [original.replace('"schema":','"schema":"duplicate","schema":',1),
                         original.replace('"good_prior": "3/5"','"good_prior": NaN'),
                         original.replace('"principal": "100"','"principal": true',1),
                         ' '*65537]
            for raw in malformed:
                invalid = directory/'bad.json'; invalid.write_text(raw)
                target = directory/'keep.json'; target.write_bytes(b'preserve\n')
                proc = subprocess.run(python+[str(source),'--input',str(invalid),'--output',str(target)],
                                      cwd=directory,capture_output=True,timeout=15)
                a.eq((proc.returncode,proc.stdout,bool(proc.stderr)), (2,b'',True), 'strict JSON CLI rejection')
                a.eq(target.read_bytes(), b'preserve\n', 'rejected CLI preserves prior output')
                rejections += 1
            for alias in aliases:
                originals = (inputfile.read_bytes(),source.read_bytes())
                proc = subprocess.run(python+[str(source),'--input',str(inputfile),'--output',str(alias)],
                                      cwd=directory,capture_output=True,timeout=15)
                a.eq((proc.returncode,proc.stdout,bool(proc.stderr)), (2,b'',True), 'input/model alias cannot be output')
                a.eq((inputfile.read_bytes(),source.read_bytes()), originals, 'protected file bytes unchanged')
                rejections += 1
    return runs,rejections


def bindings(a):
    record = json.loads(REVIEW.read_text())
    payloads = ['content/chapters/v11-c01.html']+['content/projects/v11-c01-'+end for end in
        ('inputs.json','analysis.py','output.json','manifest.json','README.txt')]+[
        'scripts/check_v11_c01.py','content/reviews/v11-c01-author.json','content/reviews/v11-c01-sources.json']
    rows = record['reviewed_hashes']
    a.eq([row['path'] for row in rows], payloads, 'exact nine final author bindings')
    for row in rows+[record['checker_binding']]:
        raw = (ROOT/row['path']).read_bytes()
        a.eq((len(raw),sha256(raw).hexdigest()), (row['bytes'],row['sha256']), 'hash binding '+row['path'])
    a.eq(record['checker_binding']['path'], str(Path(__file__).resolve().relative_to(ROOT)), 'own checker binding')
    manifest = json.loads((ASSETS/'v11-c01-manifest.json').read_text())
    a.eq(sorted(row['file'] for row in manifest['files']), sorted('v11-c01-'+s for s in
        ('inputs.json','analysis.py','output.json','README.txt')), 'four-payload manifest membership')
    for row in manifest['files']:
        raw = (ASSETS/row['file']).read_bytes()
        a.eq((len(raw),sha256(raw).hexdigest()), (row['bytes'],row['sha256']), 'lab manifest '+row['file'])
    author = json.loads((ROOT/'content/reviews/v11-c01-author.json').read_text())
    a.eq({row['path'] for row in author['reviewed_hashes']}, set(payloads)-{'content/reviews/v11-c01-author.json'},
         'author binds eight nonself payloads')
    for row in author['reviewed_hashes']:
        raw = (ROOT/row['path']).read_bytes()
        a.eq((len(raw),sha256(raw).hexdigest()), (row['bytes'],row['sha256']), 'author binding '+row['path'])
    a.eq(record['open_findings'], [], 'no unresolved peer finding')
    return len(rows)


if __name__ == '__main__':
    print(json.dumps(check(),sort_keys=True,allow_nan=False))
