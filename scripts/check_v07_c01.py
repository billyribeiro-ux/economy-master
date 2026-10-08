"""Independent integer ledger audit. Quiet, JSON-serializable check()."""
from contextlib import redirect_stdout
from copy import deepcopy
from fractions import Fraction as F
import hashlib
from html.parser import HTMLParser
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / 'content/projects'
INPUT = PROJECT / 'v07-c01-transactions.json'
PROGRAM = PROJECT / 'v07-c01-ledger.py'


def need(test, message):
    if not test:
        raise ValueError(message)


class Chapter(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack, self.sources, self.ids = [], [], []
        self.worked = self.exercises = self.solutions = 0
        self.words = []

    def handle_starttag(self, tag, attrs):
        row = dict(attrs)
        if 'id' in row:
            self.ids.append(row['id'])
        if 'data-source' in row:
            self.sources.extend(row['data-source'].split())
        classes = row.get('class', '').split()
        if tag == 'aside' and 'worked' in classes:
            self.worked += 1
        if tag == 'li' and self.stack and self.stack[-1] == ('ol', 'exercises'):
            self.exercises += 1
        if tag == 'li' and len(self.stack) >= 2 and self.stack[-2:] == [('details', 'solutions'), ('ol', '')]:
            self.solutions += 1
        need(tag not in {'h1', 'script', 'iframe'}, 'static fragment scope')
        if tag not in {'br', 'hr', 'img', 'input', 'meta', 'link', 'wbr'}:
            self.stack.append((tag, row.get('class', '')))

    def handle_endtag(self, tag):
        need(self.stack and self.stack[-1][0] == tag, 'HTML nesting: ' + tag)
        self.stack.pop()

    def handle_data(self, data):
        self.words.extend(data.split())


def load_lab():
    spec = importlib.util.spec_from_file_location('v07_c01_lab', PROGRAM)
    lab = importlib.util.module_from_spec(spec)
    prior = sys.dont_write_bytecode
    try:
        sys.dont_write_bytecode = True
        spec.loader.exec_module(lab)
    finally:
        sys.dont_write_bytecode = prior
    return lab


# Independent expected dollar balances, derived from event amounts, not lab output.
ADJUSTED_USD = dict(cash=5300, receivables=1500, supplies=300,
    prepaid_insurance=1000, equipment=3600, accumulated_depreciation=-100,
    payables=-400, customer_advances=-750, wages_payable=-250,
    interest_payable=-24, loan=-2400, contributed_capital=-6000,
    retained_earnings=0, service_revenue=-4450, wages_expense=1350,
    supplies_expense=600, insurance_expense=200, depreciation_expense=100,
    interest_expense=24, dividends=400)
TEMP = ['service_revenue', 'wages_expense', 'supplies_expense',
        'insurance_expense', 'depreciation_expense', 'interest_expense', 'dividends']


def baseline_oracle(result):
    expected = {a: v * 100 for a, v in ADJUSTED_USD.items()}
    need(result['adjusted']['debit_balances_cents'] == expected, 'full adjusted ledger')
    unadjusted = dict(expected)
    unadjusted.update(supplies=90000, prepaid_insurance=120000,
        accumulated_depreciation=0, customer_advances=-100000, wages_payable=0,
        interest_payable=0, service_revenue=-420000, wages_expense=110000,
        supplies_expense=0, insurance_expense=0, depreciation_expense=0, interest_expense=0)
    need(result['unadjusted']['debit_balances_cents'] == unadjusted, 'full unadjusted ledger')
    closed = dict(expected)
    closed.update({a: 0 for a in TEMP})
    closed['retained_earnings'] = -177600
    need(result['post_closing']['debit_balances_cents'] == closed, 'full closed ledger')
    targets = [
        ('unadjusted', 14000, 12500, 3800, 8700, 3100, 0),
        ('adjusted', 14374, 11600, 3824, 7776, 2176, 0),
        ('post_closing', 11700, 11600, 3824, 7776, 0, 1776)]
    for stage, tb, assets, liabilities, equity, profit, retained in targets:
        snap = result[stage]
        actual = [snap[k] for k in ('trial_debit_cents', 'trial_credit_cents',
            'assets_cents', 'liabilities_cents', 'equity_cents',
            'open_profit_cents', 'retained_account_cents')]
        need(actual == [100*x for x in (tb, tb, assets, liabilities, equity, profit, retained)], stage + ' totals')
        need(snap['equation_residual_cents'] == 0 and not snap['opposite_normal_balance_flags'], stage + ' residual/flags')
        for account, balance in snap['debit_balances_cents'].items():
            pair = snap['trial_balance'][account]
            need(pair['debit_cents'] == max(balance, 0) and pair['credit_cents'] == max(-balance, 0), stage + ' trial display')
    follow = result['wage_followup']
    closed.update(cash=470000, wages_payable=0, wages_expense=35000)
    need(follow['ending_debit_balances_cents'] == closed, 'full followup ledger')
    need(follow['next_period_wage_expense_cents'] == 35000 and follow['cash_payment_cents'] == 60000, 'followup amounts')
    need(follow['reversal_entries'][0]['effective_date'] == '2025-02-01'
         and follow['reversal_entries'][0]['recorded_date'] == '2025-02-02', 'reversal knowledge date')


def check():
    manuscript = (ROOT / 'content/chapters/v07-c01.html').read_text()
    doc = Chapter(); doc.feed(manuscript)
    need(not doc.stack and len(doc.ids) == len(set(doc.ids)), 'complete fragment/unique IDs')
    need((doc.worked, doc.exercises, doc.solutions) == (3, 8, 8), 'instruction package')
    sources = json.loads((ROOT / 'content/reviews/v07-c01-sources.json').read_text())
    need(set(doc.sources) == {s['id'] for s in sources}, 'scoped citation coverage')
    for source in sources:
        need(set(source) >= {'id', 'title', 'url', 'use', 'checked', 'verification'}, 'source record')
        need(source['id'].startswith('v07-c01-'), 'source namespace')
    for suffix in ('transactions.json', 'ledger.py', 'output.json', 'README.txt'):
        need('href="v07-c01-' + suffix + '"' in manuscript, 'flat download ' + suffix)
        need((PROJECT / ('v07-c01-' + suffix)).is_file(), 'download exists')
    for phrase in ('v01-c04.html', 'v07-c02.html', 'Teach-back checklist',
                   'Delayed-check answer', 'not itself an IFRS Standard',
                   'recorded dates distinct', 'no-overdraft', 'integer USD cents'):
        need(phrase in manuscript, 'scope/route ' + phrase)
    curriculum = json.loads((ROOT / 'content/curriculum.json').read_text())
    def objects(value):
        if isinstance(value, dict):
            yield value
            for sub in value.values(): yield from objects(sub)
        elif isinstance(value, list):
            for sub in value: yield from objects(sub)
    foundation = [row for row in objects(curriculum) if str(row.get('id', '')).startswith('v01-c')]
    need(len(foundation) == 12 and all(row['status'] == 'accepted' for row in foundation), 'canonical v01 prerequisites')

    data = json.loads(INPUT.read_text())
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        lab = load_lab()
        result = lab.run(data)
    need(not buffer.getvalue(), 'quiet import/API')
    json.dumps(result, allow_nan=False)
    need(result == json.loads((PROJECT / 'v07-c01-output.json').read_text()), 'preserved output')
    baseline_oracle(result)

    # Independent per-account column aggregation, not the program's posting loop.
    entries = data['transactions'] + data['adjustments'] + result['closing_entries']
    need([len(data['transactions']), len(data['adjustments']), len(result['closing_entries'])] == [11, 6, 3], 'entry counts')
    for index, history in enumerate(result['posting_history'], start=1):
        expected = {a: data['opening_debit_balances'][a] + sum(
            line['cents'] * (2*(line['side'] == 'Dr')-1)
            for entry in entries[:index] for line in entry['lines'] if line['account'] == a)
            for a in data['accounts']}
        need(history['balances'] == expected and sum(expected.values()) == 0, 'independent prefix ' + str(index))
        need(history['entry_id'] == entries[index-1]['id'], 'history event order')
    need(len(result['posting_history']) == 20, 'all posting prefixes')
    for entry in result['closing_entries']:
        need(entry['effective_date'] == '2025-01-31' and entry['recorded_date'] == '2025-02-02', 'closing dates')
    need(6000+2400+1800+1000+900-(3600+1200+500+1100+400) == 5300, 'cash independent sources/uses')
    need(900-300+1200//6+3600//36+250+24-250 == 924, 'adjustment profit change')

    # All exercise numerical anchors, calculated separately from the worked input.
    ex1_cash = 1000+600-400+300-80
    need((ex1_cash, 750-300, ex1_cash+450+400, 1000+750-80) == (1420, 450, 2270, 1670), 'exercise 1')
    need(1420+450+400+80 == 600+1000+750 == 2350, 'exercise 1 trial')
    ex2_revenue = 900//3+220
    ex2_expense = (480-125)+600//3+140+90+1200//100
    ex2_assets = -(480-125)-600//3+220-90
    ex2_liabilities = -900//3+140+1200//100
    need((ex2_revenue, ex2_expense, ex2_assets, ex2_liabilities) == (520, 797, -425, -148), 'exercise 2 entries')
    need(ex2_assets == ex2_liabilities+ex2_revenue-ex2_expense, 'exercise 2 change identity')
    ex3_revenue = 1320+480+900+260+40-(310+700+1500)
    need((ex3_revenue, ex3_revenue-260, ex3_revenue-260-40) == (490, 230, 190), 'exercise 3')
    need(1320+480+900 == 310+700+1500+190 == 2700, 'exercise 3 closure')
    ex4_prepaid = F(240)*5/6
    need((180-250, ex4_prepaid, 180-250+ex4_prepaid) == (-70, 200, 130), 'exercise 4 corrections')
    need(500-180 == 320 and -180+320 == 140 and -180+180+180 == 180, 'exercise 5 reversal/mixed route')
    dep36 = F(2400-240, 36); dep24 = F(2400-240, 24)
    need((dep36, dep36*3, 2400-dep36*3, dep24*3, 2400-dep24*3) == (60, 180, 2220, 270, 2130), 'exercise 6 allocation')
    need(2400-min(40,36)*dep36 == 240, 'exercise 6 residual bound')
    ex7_cash = 40+200+100-300-150-40
    ex7_receivable = 600+800-100
    need((ex7_cash, ex7_receivable, 800-150) == (-150, 1300, 650), 'exercise 7 stocks/profit')
    need(ex7_cash+ex7_receivable+300 == 200+640+650-40 == 1450, 'exercise 7 algebraic identity')
    need(40+200+100-300 == 40 and -ex7_cash == 150, 'exercise 7 funding timing')
    need(1300+300 == 200+150+1250 == 1600, 'exercise 7 funded identity')
    need(600 == (600-2*200+90)+(2*200-90) and 2*200-90 == 310, 'answered retention')

    # Invariance and substantive errors: balanced classifications are not audited facts.
    changed = deepcopy(data)
    changed['transactions'][0]['lines'][1]['account'] = 'service_revenue'
    wrong = lab.run(changed)
    need(wrong['adjusted']['open_profit_cents'] == 817600
         and wrong['adjusted']['contributed_capital_cents'] == 0
         and wrong['adjusted']['equity_cents'] == result['adjusted']['equity_cents'], 'balanced wrong classification')
    changed = deepcopy(data); changed['transactions'].pop()
    omitted = lab.run(changed)
    need(omitted['adjusted']['debit_balances_cents']['cash'] == 570000
         and omitted['adjusted']['equity_cents'] == 817600, 'balanced omission not detected as evidence failure')
    changed = deepcopy(data)
    changed['transactions'][7]['lines'][1]['account'] = 'service_revenue'
    correction = {'id': 'COR-01', 'effective_date': '2025-01-30', 'recorded_date': '2025-01-30',
        'source': 'Synthetic remittance review', 'explanation': 'Correct wrong credit without changing cash',
        'lines': [{'account': 'service_revenue', 'side': 'Dr', 'cents': 90000},
                  {'account': 'receivables', 'side': 'Cr', 'cents': 90000}]}
    changed['transactions'].append(correction)
    repaired = lab.run(changed)
    need(repaired['adjusted'] == result['adjusted'] and repaired['post_closing'] == result['post_closing'], 'correction restores full snapshots')
    for extra, cash, profit, flags in [(500000, 30000, -282400, []), (600000, -70000, -382400, ['cash'])]:
        changed = deepcopy(data)
        for line in changed['transactions'][9]['lines']: line['cents'] += extra
        loss = lab.run(changed)
        need(loss['adjusted']['open_profit_cents'] == profit, 'loss case profit')
        need(loss['adjusted']['debit_balances_cents']['cash'] == cash, 'cash shortfall case')
        need(loss['post_closing']['retained_account_cents'] == 177600-extra, 'debit retained deficit allowed')
        need(loss['post_closing']['opposite_normal_balance_flags'] == flags, 'retained versus cash flags')
    wage_cases = 0
    for payment in range(25000, 100001, 2500):
        changed = deepcopy(data); changed['wage_followup']['payment_cents'] = payment
        follow = lab.run(changed)['wage_followup']
        wanted = dict(result['post_closing']['debit_balances_cents'])
        wanted.update(cash=530000-payment, wages_payable=0, wages_expense=payment-25000)
        need(follow['ending_debit_balances_cents'] == wanted, 'settlement independent ledger')
        for route in ('direct_entries', 'reversal_entries'):
            for account in wanted:
                delta = sum(l['cents'] if l['side']=='Dr' else -l['cents'] for e in follow[route] for l in e['lines'] if l['account']==account)
                need(result['post_closing']['debit_balances_cents'][account]+delta == wanted[account], 'route independent aggregation')
        wage_cases += 1
    for scale in range(2, 10):
        changed = deepcopy(data)
        for entry in changed['transactions']+changed['adjustments']:
            for line in entry['lines']: line['cents'] *= scale
        changed['wage_followup']['payment_cents'] *= scale
        scaled = lab.run(changed)
        for stage in ('unadjusted', 'adjusted', 'post_closing'):
            need(scaled[stage]['debit_balances_cents'] == {a:scale*v for a,v in result[stage]['debit_balances_cents'].items()}, 'homogeneous monetary scaling')

    # Oracle itself must reject plausible wrong reports, even balanced ones.
    corruptions = []
    bad_report = deepcopy(result); bad_report['adjusted']['open_profit_cents'] += 100; corruptions.append(bad_report)
    bad_report = deepcopy(result); bad_report['post_closing']['debit_balances_cents']['dividends'] = 40000; corruptions.append(bad_report)
    bad_report = deepcopy(result); bad_report['wage_followup']['next_period_wage_expense_cents'] = 60000; corruptions.append(bad_report)
    corruptions.append(wrong)
    for corrupted in corruptions:
        try: baseline_oracle(corrupted)
        except ValueError: pass
        else: raise ValueError('independent oracle missed report mutation')

    bad = []
    changes = [
        (('schema',), 'other'), (('synthetic',), False),
        (('metadata','currency'), 'EUR'), (('metadata','amount_unit'), 'dollar'),
        (('metadata','period_start'), '2025-02-01'),
        (('transactions',0,'lines',0,'cents'), 600001),
        (('transactions',0,'lines',0,'cents'), True),
        (('transactions',0,'lines',0,'cents'), 600000.0),
        (('transactions',0,'lines',0,'cents'), 0),
        (('transactions',0,'lines',0,'cents'), -600000),
        (('transactions',0,'lines',0,'cents'), 10**12+1),
        (('transactions',0,'lines',0,'account'), 'unknown'),
        (('transactions',0,'lines',1,'account'), 'cash'),
        (('transactions',0,'lines',0,'side'), 'debit'),
        (('transactions',1,'id'), 'J01'), (('adjustments',0,'id'), 'J01'),
        (('transactions',0,'source'), ''), (('transactions',0,'explanation'), ''),
        (('transactions',0,'effective_date'), '2024-12-31'),
        (('transactions',0,'recorded_date'), '2024-12-31'),
        (('transactions',7,'effective_date'), '2025-01-16'),
        (('transactions',0,'effective_date'), '2025-02-30'),
        (('adjustments',0,'effective_date'), '2025-01-30'),
        (('opening_debit_balances','cash'), 1),
        (('accounts','retained_earnings','type'), 'capital'),
        (('accounts','cash','type'), 'unknown'),
        (('wage_followup','payment_cents'), 24999),
        (('wage_followup','reversal_date'), '2025-01-31'),
        (('wage_followup','payment_date'), '2025-01-31'),
        (('wage_followup','cash_account'), 'loan')]
    for path, value in changes:
        altered = deepcopy(data); cursor = altered
        for key in path[:-1]: cursor = cursor[key]
        cursor[path[-1]] = value; bad.append(altered)
    altered = deepcopy(data); del altered['opening_debit_balances']['loan']; bad.append(altered)
    altered = deepcopy(data); altered['opening_debit_balances'].update(cash=100, service_revenue=-100); bad.append(altered)
    altered = deepcopy(data); altered['transactions'][0]['lines'][0]['memo']='not a posting field'; bad.append(altered)
    for altered in bad:
        try: lab.run(altered)
        except (ValueError, KeyError, TypeError): pass
        else: raise ValueError('invalid API input accepted')
    with tempfile.TemporaryDirectory(prefix='v07-c01-check-') as temporary:
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
        for flags in ([], ['-O']):
            proc = subprocess.run([sys.executable]+flags+[str(PROGRAM)], cwd=temporary, env=env, capture_output=True, text=True)
            need(proc.returncode == 0 and not proc.stderr and json.loads(proc.stdout)==result, 'portable CLI normal/optimized')
        target = Path(temporary)/'bad.json'
        texts = [json.dumps(x) for x in bad]+['{"schema":1,"schema":2}', '{"x":NaN}', '{']
        for raw in texts:
            target.write_text(raw)
            proc = subprocess.run([sys.executable, str(PROGRAM), str(target)], cwd=temporary, env=env, capture_output=True, text=True)
            error = json.loads(proc.stdout)
            need(proc.returncode == 2 and not proc.stderr and error['status']=='error', 'invalid CLI contract')

    return {'chapter': 'v07-c01', 'status': 'passed', 'checks': [
        'Three worked examples, eight complete solutions, answered teach-back/retention, three scoped sources and four flat downloads',
        'All 20 posting prefixes independently recomputed; full unadjusted, adjusted, post-closing and wage-followup vectors checked',
        'Trial balance, total assets, liabilities, profit, closing equity and contra-asset totals independently reconciled',
        'All numerical exercise/retention anchors, cash funding timing and depreciation residual bound recalculated',
        'Balanced classification/omission limits, correcting entry, loss/deficit and infeasible cash-plan demonstrations',
        'Independent wage-route aggregation, monetary-scale cases and deliberately wrong report detection',
        'Quiet strict-JSON API, exact preserved output, portable normal/optimized CLI and malformed-input rejection'],
        'posting_prefixes': 20, 'wage_settlement_cases': wage_cases, 'monetary_scale_cases': 8,
        'invalid_api_cases': len(bad), 'invalid_cli_cases': len(texts), 'rejected_report_mutations': len(corruptions),
        'parsed_words': len(doc.words), 'input_sha256': hashlib.sha256(INPUT.read_bytes()).hexdigest(),
        'limitations': ['Synthetic arithmetic under supplied historical-cost/accrual conventions; no empirical, tax or jurisdictional reporting conclusion.',
                       'Balance checks cannot establish recognition, completeness, authorization, current value or actual funding; prose/evidence judgments require editorial review.',
                       'No visual/mobile/print QA, external human certification, shared acceptance or publication is claimed.']}


if __name__ == '__main__':
    print(json.dumps(check(), indent=2, allow_nan=False))
