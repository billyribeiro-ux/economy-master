"""Independent finite-contract peer checks; no author-checker imports or oracles."""
import contextlib
import copy
from fractions import Fraction as F
import hashlib
from html.parser import HTMLParser
import importlib.util
import io
import itertools
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
AUTHORS = (
    'content/cross-assessments/parts/finance-core-project.html',
    'content/projects/finance-core-inputs.json',
    'content/projects/finance-core-analysis.py',
    'content/projects/finance-core-output.json',
    'content/projects/finance-core-manifest.json',
    'content/projects/finance-core-README.txt',
    'scripts/check_finance_core_project.py',
    'content/reviews/finance-core-project-author.json',
    'content/reviews/finance-core-project-sources.json')
SELF = 'scripts/check_finance_core_project_peer.py'
REVIEW = 'content/reviews/finance-core-project-peer.json'
FILES = AUTHORS + (SELF, REVIEW)
PI = (F(1, 5), F(3, 10), F(2, 5))
D = F(9, 10)
BASE_ID = '1/2-escrow-1/4'


def require(ok, message):
    if not ok:
        raise ValueError('finance-core project peer: ' + message)


class Audit:
    def __init__(self):
        self.n = self.policies = self.events = self.api_rejections = 0
        self.cli_rejections = self.aliases = self.portable = self.anchors = 0

    def eq(self, actual, expected, label):
        self.n += 1
        if isinstance(expected, F):
            if isinstance(actual, F):
                require(actual == expected, label + ': exact rational mismatch')
            else:
                require(type(actual) in (int, float) and math.isfinite(actual)
                        and math.isclose(actual, float(expected), rel_tol=2e-13, abs_tol=2e-13),
                        label + ': ' + repr(actual) + ' != ' + str(expected))
        elif isinstance(expected, dict):
            require(type(actual) is dict and set(actual) == set(expected), label + ': keys')
            for key, value in expected.items():
                self.eq(actual[key], value, label + '.' + key)
        elif isinstance(expected, (list, tuple)):
            require(isinstance(actual, (list, tuple)) and len(actual) == len(expected), label + ': length')
            for i, value in enumerate(expected):
                self.eq(actual[i], value, label + '[' + str(i) + ']')
        else:
            require(actual == expected and (type(expected) is not bool or type(actual) is bool),
                    label + ': ' + repr(actual) + ' != ' + repr(expected))

    def fields(self, actual, expected, label):
        for key, value in expected.items():
            self.eq(actual[key], value, label + '.' + key)


def reject_constant(value):
    raise ValueError('nonfinite JSON: ' + value)


def no_duplicates(pairs):
    out = {}
    for key, value in pairs:
        require(key not in out, 'duplicate key in evidence')
        out[key] = value
    return out


def read_json(path):
    return json.loads(path.read_text(), parse_constant=reject_constant, object_pairs_hook=no_duplicates)


def digest(path):
    raw = path.read_bytes()
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def load_model(path):
    old = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    out, err = io.StringIO(), io.StringIO()
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            spec = importlib.util.spec_from_file_location('finance_peer_subject', path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = old
    require(not out.getvalue() and not err.getvalue(), 'model import is quiet')
    return module


def call(a, module, data):
    original, cwd = copy.deepcopy(data), Path.cwd()
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        result = module.run(data)
    a.eq(out.getvalue() + err.getvalue(), '', 'quiet run')
    a.eq(data == original, True, 'input not mutated')
    a.eq(Path.cwd(), cwd, 'cwd not changed')
    a.eq(json.loads(json.dumps(result, allow_nan=False), parse_constant=reject_constant) == result,
         True, 'strict JSON result')
    return result


def dot(x, y):
    return sum((a*b for a, b in zip(x, y)), F(0))


def tail_vertices(losses, probabilities):
    """Maximize loss over all vertices of the three-atom 0.1-tail mass polytope."""
    tail = F(1, 10)
    values = []
    for free in range(3):
        other = [i for i in range(3) if i != free]
        for extremes in itertools.product((0, 1), repeat=2):
            mass = [F(0)]*3
            for i, upper in zip(other, extremes):
                mass[i] = probabilities[i] if upper else F(0)
            mass[free] = tail - sum(mass)
            if 0 <= mass[free] <= probabilities[free]:
                values.append(dot(mass, losses)/tail)
    require(bool(values), 'tail polytope has vertices')
    quantile = min(z for z in set(losses)
                   if sum(p for p, loss in zip(probabilities, losses) if loss <= z) >= 1-tail)
    return {'mean_loss': dot(probabilities, losses), 'var': quantile,
            'es': max(values), 'loss_by_state': losses}


def financial_matrix(experiment):
    """Independent security-price/payoff matrix and cumulative resources by cutoff."""
    delta, senior = (F(str(experiment[k])) for k in ('down_revenue_loss', 'escrow_senior_claim'))
    pre = experiment['information'] == 'before_trade'
    p = tuple(F(str(x)) for x in experiment['physical_probabilities'])
    estate = (30-delta, F(60), F(90))
    note = tuple(min(F(50), x) for x in estate)
    equity = tuple(max(F(0), x-50) for x in estate)
    note_price = dot(PI, note) if pre else F(41)
    # Columns: unit terminal bill, note, escrow claim, credit-exposed claim.
    payoffs = [(F(1), n, 20-senior if i == 0 else F(0), F(12) if i == 0 else F(0))
               for i, n in enumerate(note)]
    costs = (D, note_price+F(1, 10), F(22, 5), F(12, 5))
    rows = []
    for x in (F(1, 2), F(3, 4), F(1)):
        for kind, h in [('none', F(0)), ('credit', x/2), ('credit', x), ('escrow', x/2), ('escrow', x)]:
            holdings = [F(0), x, h if kind == 'escrow' else F(0), h if kind == 'credit' else F(0)]
            holdings[0] = (64-dot(costs, holdings))/D
            require(holdings[0] >= 20, 'supported menu meets first cutoff')
            capital = [dot(holdings, payoff)-64 for payoff in payoffs]
            noon = [holdings[0]+x*note[i]-64+
                    (holdings[2]*payoffs[i][2] if experiment['escrow_settlement'] == '12:00' else 0)
                    for i in range(3)]
            misses = [max(F(0), -z) for z in noon]
            unpaid = [max(F(0), -z) for z in capital]
            cash = [max(F(0), z) for z in capital]
            cure = [miss-arrear for miss, arrear in zip(misses, unpaid)]
            require(min(cure) >= 0, 'later inflows cannot increase arrears')
            eligible = min(noon) >= 0 and min(capital) >= 2
            row = {'id': str(x)+'-'+kind+'-'+str(h), 'note_fraction': x, 'kind': kind,
                   'hedge_fraction': h, 'entry_fees': x/10+F(2, 5)*holdings[2],
                   'bill_purchase': D*holdings[0], 'cash_after09': holdings[0]-20,
                   'net_capital_by_state': capital, 'missed_at_deadline_by_state': misses,
                   'client_unpaid_by_state': unpaid, 'physical_mean_capital': dot(p, capital),
                   'timely': min(noon) >= 0, 'capital_floor_met': min(capital) >= 2,
                   'eligible': eligible, 'risk': tail_vertices([F(64, 9)-z for z in capital], p)}
            rows.append({'output': row, 'holdings': holdings, 'noon': noon, 'cash': cash, 'cure': cure})
    ranked = sorted((x for x in rows if x['output']['eligible']),
                    key=lambda x: (-x['output']['physical_mean_capital'], x['holdings'][1],
                                   x['output']['hedge_fraction'], x['output']['kind']))
    fixed = next(x for x in rows if x['output']['id'] == BASE_ID)
    after = not pre and (delta > 0 or senior > 0 or experiment['escrow_settlement'] == '16:00')
    return {'rows': rows, 'ranked': ranked, 'shown': ranked[0] if ranked else fixed, 'fixed': fixed,
            'delta': delta, 'senior': senior, 'estate': estate, 'note': note, 'equity': equity,
            'note_price': note_price, 'new_cash': 50-note_price, 'pre': pre, 'after': after,
            'p': p, 'payoffs': payoffs}


def accounts(a, result, collections):
    # Signed transaction vectors against the opening balance sheet, with equity
    # as the temporary income account. Supplier settlement is a second cash date.
    ledger = dict(cash=F(10), receivables=F(20), inventory=F(30), ppe=F(60),
                  payables=F(20), debt=F(40), equity=F(60))
    events = [dict(receivables=100, equity=100), dict(inventory=50, payables=50),
              dict(inventory=-60, equity=-60), dict(cash=collections, receivables=-collections),
              dict(cash=-55, payables=-55), dict(cash=-20, equity=-20), dict(ppe=-10, equity=-10)]
    for event in events:
        for account, change in event.items():
            ledger[account] += change
        a.eq(sum(ledger[k] for k in ('cash', 'receivables', 'inventory', 'ppe')),
             sum(ledger[k] for k in ('payables', 'debt', 'equity')), 'journal A=L+E')
    income = ledger['equity']-60
    cfo = ledger['cash']-10
    indirect = income+10-(ledger['receivables']-20)-(ledger['inventory']-30)+(ledger['payables']-20)
    a.eq(cfo, indirect, 'indirect independently agrees with journal cash')
    a.eq(result['closing'], ledger, 'all historical balances')
    a.fields(result, {'income': income, 'direct_cfo': cfo, 'indirect_cfo': indirect,
                     'assets': F(125), 'liabilities_and_equity': F(125),
                     'cash_after_paying_all_ap': ledger['cash']-ledger['payables'],
                     'operating_reserve_gap': 90-collections, 'parent_gate': collections == 90}, 'parent')


def audit_case(a, data, result):
    e = data['experiment']; calc = financial_matrix(e)
    collections = F(str(e['historical_collections']))
    accounts(a, result['parent'], collections)
    delta, q = calc['delta'], calc['note_price']
    a.fields(result['project_claims'], {
        'sales_cash': [50-delta, F(80), F(110)], 'operating_income': [-20-delta, F(10), F(40)],
        'estate': calc['estate'], 'note_paid': calc['note'], 'equity_paid': calc['equity'],
        'note_unpaid_nominal': [50-n for n in calc['note']],
        'current_asset_pv': dot(PI, calc['estate']), 'current_note_pv': dot(PI, calc['note']),
        'equity_pv': F(19), 'current_unfunded_opportunity_npv': dot(PI, calc['estate'])-50,
        'entry_note_proceeds': q, 'new_equity_cash': 50-q, 'new_equity_share': (50-q)/19,
        'parent_equity_share': 1-(50-q)/19, 'entry_note_discount': 50-q,
        'pre_resolution_book_equity': [v-50 for v in calc['estate']],
        'protection_current_pvs': {'escrow': (20-calc['senior'])/5, 'credit': F(12, 5)}}, 'claims')
    a.eq(len(result['policies']), 15, 'complete allowed menu')
    for observed, expected in zip(result['policies'], calc['rows']):
        a.eq(observed, expected['output'], 'independent payoff matrix policy')
        a.policies += 1
    winner = calc['ranked'][0]['output'] if calc['ranked'] else None
    actual_ok = calc['fixed']['output']['eligible'] if calc['after'] else winner is not None
    a.fields(result, {
        'physical_probabilities': calc['p'], 'state_prices': PI, 'opening_reserve_cash': F(64),
        'client_full_performance_pv': F(288, 5), 'cash_only_terminal_benchmark': F(64, 9),
        'selected_policy': winner['id'] if winner else None,
        'eligible_policy_ids': [x['output']['id'] for x in calc['ranked']],
        'menu_has_feasible_policy': winner is not None,
        'comparison_scope': 'historical_entry_counterfactuals' if calc['after'] else 'prospective_entry',
        'prospective_entry_approval': None if calc['after'] else collections == 90 and winner is not None,
        'institution_approval': collections == 90 and actual_ok,
        'shown_policy': calc['shown']['output']['id']}, 'decision')
    fixed = calc['fixed']['output']
    expected_actual = {'id': BASE_ID, 'eligible': fixed['eligible'],
                       'net_capital_by_state': fixed['net_capital_by_state'],
                       'missed_at_deadline_by_state': fixed['missed_at_deadline_by_state']} if calc['after'] else None
    a.eq(result['actual_after_trade_position'], expected_actual, 'actual holdings never silently switch')
    shown = calc['shown']['output']
    pv = dot(PI, shown['net_capital_by_state'])
    a.eq(result['exact'], {'selected_mean': str(winner['physical_mean_capital']) if winner else None,
                          'shown_net_capital': list(map(str, shown['net_capital_by_state'])),
                          'shown_terminal_net_pv': str(pv), 'shown_es90': str(shown['risk']['es'])}, 'exact results')
    a.eq(result['shown_terminal_net_pv'], pv, 'residual price')
    certificate = result['fixed_position_reverse_certificate']
    if calc['senior'] or e['escrow_settlement'] == '16:00':
        a.eq(certificate, None, 'single-shock certificate absent for compound contract')
    else:
        a.fields(certificate, {'position': BASE_ID, 'capital_floor_boundary': '19/7' if calc['pre'] else '19/9',
                              'bad_capital_shock_slope': '-7/18' if calc['pre'] else '-1/2',
                              'boundary_is_inclusive': True}, 'reverse')
    audit_owners_and_execution(a, e, result, calc)
    return calc


def audit_owners_and_execution(a, experiment, result, calc):
    row = calc['shown']['output']; holdings = calc['shown']['holdings']
    x, he, hc = holdings[1:]; q, nc = calc['note_price'], calc['new_cash']
    premium = 4*he+F(12, 5)*hc
    purchases = [('client_payer', 'reserve', F(288, 5)), ('sponsor', 'reserve', F(32, 5)),
                 ('reserve', 'spv', x*q), ('note_underwriter', 'spv', (1-x)*q),
                 ('equity_subscriber', 'spv', nc), ('spv', 'equipment_seller', F(30)),
                 ('spv', 'inventory_supplier', F(20)), ('reserve', 'dealer', premium),
                 ('reserve', 'fee_provider', row['entry_fees']), ('reserve', 'bill_issuer', row['bill_purchase'])]
    balances = {k: F(v) for k, v in dict(reserve=0, client_payer=60, sponsor=10, note_underwriter=50,
                equity_subscriber=20, dealer=0, fee_provider=0, bill_issuer=100, spv=0,
                equipment_seller=0, inventory_supplier=0, escrow_pool=20, credit_pool=12).items()}
    a.eq(len(result['entry']['transfers']), len(purchases), 'all entry recipients')
    for actual, (payer, recipient, amount) in zip(result['entry']['transfers'], purchases):
        a.fields(actual, {'payer': payer, 'recipient': recipient, 'cash': amount}, 'entry transfer')
        balances[payer] -= amount; balances[recipient] += amount
        a.eq(balances[payer] >= 0, True, 'each payer funds its payment prefix')
    a.fields(result['entry'], {'remaining_cash': balances, 'cash_sum_before': F(272), 'cash_sum_after': F(272),
             'dealer_escrow_units_retained': 1-he, 'dealer_credit_units_retained': 1-hc,
             'dealer_original_reference_claim_value': F(32, 5),
             'dealer_after_sale_cash_plus_reference_claim_value': premium+4*(1-he)+F(12, 5)*(1-hc)}, 'endowments')
    for i, state in enumerate(('down', 'normal', 'up')):
        es = calc['payoffs'][i][2]*he; cr = calc['payoffs'][i][3]*hc
        now = es if experiment['escrow_settlement'] == '12:00' else F(0)
        later = es+cr-now
        missed = row['missed_at_deadline_by_state'][i]
        payments = [F(20), 44-missed, calc['shown']['cure'][i]]
        details = result['shown_reserve_states'][i]
        a.fields(details, {'state': state, 'paid09': payments[0], 'paid12': payments[1],
                'missed_at_deadline': missed, 'late_cure': payments[2],
                'terminal_cash': calc['shown']['cash'][i],
                'client_unpaid_nominal': row['client_unpaid_by_state'][i],
                'terminal_net_capital': row['net_capital_by_state'][i]}, 'executed summary')
        # Verify semantic event vector, then reconstruct all prefixes independently.
        events = [('09:00', 'bill_redemption', holdings[0], F(0), F(0)),
                  ('09:00', 'first_client_payment', F(0), payments[0], F(20)),
                  ('12:00', 'project_note_receipt', x*calc['note'][i], F(0), F(0))]
        if row['kind'] == 'escrow' and experiment['escrow_settlement'] == '12:00':
            events.append(('12:00', 'escrow_receipt', now, F(0), F(0)))
        events.append(('12:00', 'second_client_payment', F(0), payments[1], F(44)))
        if row['kind'] != 'none':
            events.append(('16:00', 'late_protection_receipt', later, F(0), F(0)))
        events.append(('16:00', 'late_client_cure', F(0), payments[2], F(0)))
        a.eq(len(details['journal']), len(events), 'full event count')
        cash = arrears = F(0)
        for got, (time, event, received, paid, due) in zip(details['journal'], events):
            cash += received-paid; arrears += due-paid
            a.eq(got, dict(time=time, event=event, receipt=received, payment=paid, new_client_due=due,
                           cash=cash, client_arrears=arrears), 'dated executed event')
            a.events += 1
        owners = result['shown_terminal_allocations'][i]
        n, eq = calc['note'][i], calc['equity'][i]
        a.eq(owners['spv_cash'], dict(customer_receipt=calc['estate'][i]+20, equipment_buyer_receipt=F(10),
             operating_payee=F(30), cedar_note=x*n, underwriter_note=(1-x)*n,
             new_equity_holder=nc*eq/19, parent_shareholder=(1-nc/19)*eq, ending_cash=F(0),
             cedar_note_unpaid_nominal=x*(50-n), underwriter_note_unpaid_nominal=(1-x)*(50-n)), 'SPV all rights')
        a.eq(n+eq, calc['estate'][i], 'all estate cash allocated exactly once')
        for kind, endowed, fraction, priority, cutoff in (
                ('escrow', F(20), he, calc['senior'], experiment['escrow_settlement']),
                ('credit', F(12), hc, F(0), '16:00')):
            payoff = endowed-priority if i == 0 else F(0)
            expected = dict(settlement=cutoff, cedar_paid=fraction*payoff, dealer_paid=(1-fraction)*payoff,
                            writer_cash_return=endowed-priority-payoff,
                            cedar_unpaid_nominal=fraction*(20-payoff) if i == 0 else F(0),
                            dealer_unpaid_nominal=(1-fraction)*(20-payoff) if i == 0 else F(0))
            if kind == 'escrow': expected['senior_paid'] = priority
            a.eq(owners[kind+'_pool'], expected, 'separate pool rights')
            a.eq(expected['cedar_paid']+expected['dealer_paid']+expected['writer_cash_return']+priority,
                 endowed, 'pool cannot reuse collateral')
        a.eq(owners['bill_issuer_after_redemption'], 100+row['bill_purchase']-holdings[0], 'bill issuer funded')


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids, self.points, self.solutions, self.sources, self.links = [], {}, {}, {}, []
        self.tables, self.table, self.row, self.cell, self.active = {}, None, None, None, None
        self.stack = []; self.h1 = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'id' in attrs: self.ids.append(attrs['id'])
        if tag == 'h1': self.h1 += 1
        if tag == 'li' and 'data-points' in attrs: self.points[attrs['id']] = int(attrs['data-points'])
        if tag == 'a':
            self.links.append(attrs.get('href', ''))
            if 'data-source' in attrs: self.sources[attrs['data-source']] = attrs['href']
        if tag == 'details' and 'data-solution-for' in attrs:
            self.active = attrs['data-solution-for']
            require(self.active not in self.solutions, 'duplicate solution')
            self.solutions[self.active] = ''
        if tag == 'table' and 'id' in attrs:
            self.table = attrs['id']; self.tables[self.table] = []
        if self.table and tag == 'tr': self.row = []
        if self.table and tag in ('td', 'th'): self.cell = ''
        if tag not in ('br', 'hr', 'img', 'input', 'meta', 'link'): self.stack.append(tag)

    def handle_endtag(self, tag):
        require(self.stack and self.stack.pop() == tag, 'HTML nesting')
        if tag in ('td', 'th') and self.cell is not None:
            self.row.append(self.cell.strip()); self.cell = None
        if tag == 'tr' and self.table:
            self.tables[self.table].append(self.row); self.row = None
        if tag == 'table': self.table = None
        if tag == 'details': self.active = None

    def handle_data(self, text):
        if self.active: self.solutions[self.active] += text
        if self.cell is not None: self.cell += text


def determinant(rows):
    n = len(rows)
    if n == 1: return rows[0][0]
    return sum(((-1)**j)*rows[0][j]*determinant([row[:j]+row[j+1:] for row in rows[1:]]) for j in range(n))


def proofs_and_print(a, data, cases):
    page = Page(); page.feed((ROOT/AUTHORS[0]).read_text()); page.close()
    a.eq(page.stack, [], 'balanced fragment'); a.eq(page.h1, 0, 'no duplicate root heading')
    a.eq(len(page.ids), len(set(page.ids)), 'unique anchors')
    ids = ['finance-core-project-d'+str(i) for i in range(1, 6)] + ['finance-core-project-t'+str(i) for i in range(1, 7)]
    a.eq(set(page.solutions), set(ids), 'eleven exact tasks solved')
    a.eq(page.points, {i: 20 for i in ids[:5]}, '100 points across five domains')
    a.eq(all(i in page.ids for i in ids), True, 'every answer targets a prompt')
    a.eq(all(i == 'project' or i.startswith('finance-core-project-') for i in page.ids), True, 'owned ID namespace')
    source = read_json(ROOT/AUTHORS[8])
    a.eq(source['proposals'], [], 'no new source claims')
    a.eq(page.sources, {r['id']: r['url'] for r in source['reuse']}, 'eight exact scoped citations')
    a.eq(len(page.sources), 8, 'source count')
    for ending in ('inputs.json', 'analysis.py', 'output.json', 'manifest.json', 'README.txt'):
        a.eq('finance-core-'+ending in page.links, True, 'flat attachment href')
    base = cases['baseline']; winner = base['shown']['output']
    for cells, row in zip(page.tables['finance-core-project-policy-table'][1:], base['rows']):
        r = row['output']
        expected = [str(r['note_fraction']), r['kind'], str(r['hedge_fraction']), str(r['bill_purchase']),
                    str(r['net_capital_by_state'][0]), str(r['net_capital_by_state'][1]),
                    str(r['physical_mean_capital']), 'Yes' if r['eligible'] else 'No']
        a.eq([s.replace('−', '-') for s in cells], expected, 'all printed policy cells'); a.anchors += 8
    a.eq(len(page.tables['finance-core-project-policy-table']), 16, 'all 15 rows printed')
    money = base['shown']['holdings'][0]
    bad = [money, money-20, money-5, money, money-44, money-44]
    good = [money, money-20, money+5, money+5, money-39, money-39]
    for cells, bad_value, good_value in zip(page.tables['finance-core-project-cash-table'][1:], bad, good):
        a.eq(cells[1:], [str(bad_value), str(good_value)], 'printed cash prefixes'); a.anchors += 2
    # Whole-menu inequalities are checked algebraically, then at all allowed x.
    for row in base['rows']:
        r = row['output']; x, h, k = r['note_fraction'], r['hedge_fraction'], r['kind']
        if k == 'none': a.eq(row['noon'][0], (64-141*x)/9, 'unhedged global formula')
        if k == 'credit': a.eq(row['noon'][0] < (64-141*x)/9 < 0, True, 'late credit cannot fix noon')
        if k == 'escrow':
            expression = (64-73*x)/9 if h == x/2 else (64-5*x)/9
            a.eq(r['net_capital_by_state'][0], expression, 'escrow feasibility formula')
    a.eq((64-18)/F(73), F(46, 73), 'half hedge feasible fraction threshold')
    a.eq(winner['physical_mean_capital']-F(41, 6), F(35, 36), 'strict finite optimum margin')
    a.eq(dot(PI, winner['net_capital_by_state']), F(32, 5)-winner['entry_fees'], 'sponsor value less real fees')
    a.eq(winner['risk']['es'], F(14, 9), 'tail-polytope ES anchor')
    # Fixed-position slopes from separate price and payoff changes.
    after_slope = -F(1, 2); before_slope = after_slope+F(1, 10)/D
    after_boundary = (2-F(55, 18))/after_slope
    before_boundary = (2-F(55, 18))/before_slope
    a.eq((after_boundary, before_boundary), (F(19, 9), F(19, 7)), 'different information boundaries')
    a.eq(F(55, 18)+after_slope*F(55, 9), F(0), 'deadline boundary differs from capital')
    switch = (F(145, 18)-F(41, 6))/5
    a.eq(switch, F(11, 45), 'physical preference switch')
    a.eq(F(145, 18)-5*switch, F(41, 6), 'exact preference tie')
    bridge = 44-(money-20+15)
    a.eq((bridge, 2-bridge, 5-bridge), (F(35, 18), F(1, 18), F(55, 18)), 'new funded bridge and repayment')
    a.eq(50*D-41, F(4), 'reference escrow price')
    basis = [[F(1), n, e] for n, e in zip(base['note'], base['equity'])]
    a.eq(determinant(basis), F(600), 'three-state completeness')
    # Cofactor null vector supplies the complete one-dimensional four-state family.
    pay = [[F(1)]*4, list(map(F, (10, 30, 50, 50))), list(map(F, (0, 0, 10, 40)))]
    cofactors = [(-1)**j*determinant([row[:j]+row[j+1:] for row in pay]) for j in range(4)]
    direction = [v/cofactors[0] for v in cofactors]
    origin = [F(0), *PI]
    a.eq(direction, [F(1), F(-2), F(4, 3), F(-1, 3)], 'pricing null direction')
    a.eq([dot(r, direction) for r in pay], [F(0)]*3, 'all traded prices unchanged along family')
    upper = min(-v/s for v, s in zip(origin, direction) if s < 0)
    a.eq(upper, F(1, 10), 'strict positivity upper bound')
    sample = [b+F(1, 20)*s for b, s in zip(origin, direction)]
    a.eq([dot(r, sample) for r in pay], [D, F(41), F(19)], 'interior positive state prices')
    a.eq(dot([20, 20, 0, 0], sample), F(3), 'interior extension price')
    lower_pay = [25-n/2 for n in pay[1]]; upper_pay = [50-n for n in pay[1]]
    a.eq([h-z for h, z in zip((20, 20, 0, 0), lower_pay)], [0, 10, 0, 0], 'lower endpoint arbitrage')
    a.eq([z-h for z, h in zip(upper_pay, (20, 20, 0, 0))], [20, 0, 0, 0], 'upper endpoint arbitrage')
    a.eq((25*D-F(41, 2), 50*D-41), (F(2), F(4)), 'sharp hedge prices')
    anchors = {
        'd2': [F(9, 19), F(10, 19), F(90, 19), F(360, 19), F(100, 19), F(400, 19)],
        'd3': [F(46, 73), F(281, 36), F(35, 36), F(3, 20), F(25, 4), F(14, 9), F(-25, 36)],
        'd4': [F(19, 9), F(55, 9), F(71, 18), F(37, 18)],
        't2': [cases['after']['fixed']['output']['net_capital_by_state'][0],
               cases['after']['shown']['output']['physical_mean_capital'], before_boundary,
               cases['before']['note_price'], cases['before']['new_cash'],
               cases['before']['shown']['output']['bill_purchase'],
               cases['before']['shown']['output']['physical_mean_capital']],
        't3': [switch, F(59, 9), F(41, 6)],
        't4': [bridge, 2-bridge, 5-bridge],
        't5': [cases['senior']['fixed']['output']['physical_mean_capital'],
               cases['senior']['shown']['output']['physical_mean_capital'], F(15, 4), F(45, 4), F(15, 2)],
        't6': [F(1, 10), F(1, 20), F(11, 30), F(23, 60)]}
    for task, values in anchors.items():
        for value in values:
            a.eq(str(value).replace('-', '−') in page.solutions['finance-core-project-'+task], True,
                 'independently derived visible answer '+task)
            a.anchors += 1


def boundary_checks(a, module, data):
    for info, numerator, denominator in [('after_trade', 19, 9), ('before_trade', 19, 7),
                                         ('after_trade', 55, 9)]:
        scaled = numerator*10**12//denominator
        for units, below in ((scaled, True), (scaled+1, False)):
            changed = copy.deepcopy(data)
            changed['experiment'].update(information=info, down_revenue_loss=float(F(units, 10**12)))
            output = call(a, module, changed)
            target = next(r for r in output['policies'] if r['id'] == BASE_ID)
            a.eq(target['timely'] if numerator == 55 else target['capital_floor_met'], below, 'adjacent permitted boundary')
    for probability, normal, winner in [(.244444444444, .355555555556, BASE_ID),
                                        (.244444444445, .355555555555, '1/2-escrow-1/2')]:
        changed = copy.deepcopy(data); changed['experiment']['physical_probabilities'] = [probability, normal, .4]
        a.eq(call(a, module, changed)['selected_policy'], winner, 'physical switch adjacent decimals')
    for probability, up in [(.1, .4), (.100000000001, .399999999999)]:
        changed = copy.deepcopy(data); changed['experiment']['physical_probabilities'] = [probability, .5, up]
        result = call(a, module, changed)
        row = next(x for x in result['policies'] if x['id'] == BASE_ID)
        a.eq(row['risk'], tail_vertices([F(73, 18), F(-17, 18), F(-17, 18)],
                                        list(map(lambda x: F(str(x)), [probability, .5, up]))), 'VaR atom boundary and ES')
    changed = copy.deepcopy(data); changed['experiment']['down_revenue_loss'] = .0001220703125
    a.eq(call(a, module, changed)['actual_after_trade_position']['net_capital_by_state'][0],
         F(55, 18)-F(1, 16384), 'reduced denominator valid despite 13 decimal digits')


def invalid_api(a, module, data):
    invalid = [None, [], True]
    changes = [(('schema',), True), (('contract', 'project', 'note_face'), 51),
               (('contract', 'providers', 'escrow_pool_cash'), True),
               (('experiment', 'historical_collections'), 79), (('experiment', 'historical_collections'), 91),
               (('experiment', 'down_revenue_loss'), -1), (('experiment', 'down_revenue_loss'), 11),
               (('experiment', 'down_revenue_loss'), '2.5'), (('experiment', 'down_revenue_loss'), float('nan')),
               (('experiment', 'down_revenue_loss'), float('inf')), (('experiment', 'down_revenue_loss'), 1e-13),
               (('experiment', 'physical_probabilities'), [.1, .2, .6]),
               (('experiment', 'physical_probabilities'), [0, .6, .4]),
               (('experiment', 'physical_probabilities'), [.05, .55, .3, .1]),
               (('experiment', 'escrow_senior_claim'), 6), (('experiment', 'escrow_settlement'), '11:00')]
    for path, value in changes:
        changed = copy.deepcopy(data); target = changed
        for key in path[:-1]: target = target[key]
        target[path[-1]] = value; invalid.append(changed)
    for field, value in [('escrow_senior_claim', 1), ('escrow_settlement', '16:00')]:
        changed = copy.deepcopy(data); changed['experiment'].update(information='before_trade')
        changed['experiment'][field] = value; invalid.append(changed)
    for remove in (True, False):
        changed = copy.deepcopy(data)
        if remove: del changed['experiment']['information']
        else: changed['experiment']['undeclared'] = 1
        invalid.append(changed)
    for changed in invalid:
        before = repr(changed); out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try: module.run(changed)
            except ValueError: a.api_rejections += 1
            else: raise ValueError('unsupported API contract accepted')
        a.eq(out.getvalue()+err.getvalue(), '', 'invalid API quiet')
        a.eq(repr(changed), before, 'invalid API nonmutation')


def bindings(a, verify_peer):
    manifest = read_json(ROOT/AUTHORS[4])
    expected = {Path(AUTHORS[i]).name for i in (1, 2, 3, 5)}
    a.eq({r['file'] for r in manifest['files']}, expected, 'four manifested payloads')
    for r in manifest['files']:
        a.eq(digest(ROOT/'content/projects'/r['file']), {k: r[k] for k in ('bytes', 'sha256')}, 'manifest identity')
    author = read_json(ROOT/AUTHORS[7]); rows = author['reviewed_hashes']
    a.eq({r['path'] for r in rows}, set(AUTHORS)-{AUTHORS[7]}, 'eight author nonself payloads')
    for r in rows:
        a.eq(digest(ROOT/r['path']), {k: r[k] for k in ('bytes', 'sha256')}, 'author identity')
    if verify_peer:
        rows = read_json(ROOT/REVIEW)['reviewed_hashes']
        a.eq(len(rows), 10, 'nine author plus own checker')
        a.eq({r['path'] for r in rows}, set(AUTHORS+(SELF,)), 'exact peer binding set')
        for r in rows:
            a.eq(digest(ROOT/r['path']), {k: r[k] for k in ('bytes', 'sha256')}, 'peer identity')


def portable_and_aliases(a, baseline):
    with tempfile.TemporaryDirectory(prefix='finance-core-peer-') as raw:
        temp = Path(raw); package = temp/'book'; work = temp/'unrelated'; work.mkdir()
        for relative in FILES:
            target = package/relative; target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT/relative, target)
        a.eq(sorted(str(p.relative_to(package)) for p in package.rglob('*') if p.is_file()), sorted(FILES), 'exact eleven-file copy')
        model, input_path = package/AUTHORS[2], package/AUTHORS[1]
        def execute(args, optimized=False):
            return subprocess.run([sys.executable, '-I', '-B']+(['-O'] if optimized else [])+[str(model)]+args,
                                  cwd=work, capture_output=True, text=True, timeout=20)
        for optimized in (False, True):
            for explicit in (False, True):
                output = work/'result.json' if explicit else package/AUTHORS[3]
                args = ['--input', str(input_path), '--output', str(output)] if explicit else []
                run = execute(args, optimized)
                a.eq((run.returncode, run.stdout, run.stderr), (0, '', ''), 'portable quiet model CLI')
                a.eq(read_json(output) == baseline, True, 'portable output equals independently audited baseline')
                a.portable += 1
        protected = [package/rel for rel in AUTHORS if rel != AUTHORS[3]]
        custom = work/'custom-input.json'; shutil.copyfile(input_path, custom); protected.append(custom)
        preserved = {p: p.read_bytes() for p in protected}
        attempts = []
        for i, target in enumerate(protected):
            attempts.append((target, custom if target == custom else input_path))
            for mode in ('symlink', 'hardlink'):
                alias = work/(mode+'-'+str(i))
                if mode == 'symlink': alias.symlink_to(target)
                else: os.link(target, alias)
                attempts.append((alias, custom if target == custom else input_path))
        attempts.append((input_path.parent/'..'/'projects'/input_path.name, input_path))
        for i, (target, source) in enumerate(attempts):
            run = execute(['--input', str(source), '--output', str(target)], bool(i % 2))
            a.eq((run.returncode, run.stdout), (2, ''), 'real protected-alias refusal')
            a.eq('aliases protected payload' in run.stderr, True, 'alias reason identifies protection')
            a.aliases += 1
        for path, raw_bytes in preserved.items(): a.eq(path.read_bytes(), raw_bytes, 'protected bytes unchanged')
        raw_good = input_path.read_bytes()
        invalid = [b'{"schema":1,"schema":1}', raw_good+b'{}', b'\xff', b' '*32769,
                   raw_good.replace(b'"down_revenue_loss": 0', b'"down_revenue_loss": NaN'),
                   raw_good.replace(b'"down_revenue_loss": 0', b'"down_revenue_loss": 1e400'),
                   raw_good.replace(b'"escrow_senior_claim": 0', b'"escrow_senior_claim": 6'), b'[]']
        bad = work/'bad.json'; sentinel = work/'sentinel.txt'
        for i, payload in enumerate(invalid):
            bad.write_bytes(payload); sentinel.write_bytes(b'preserved\n')
            run = execute(['--input', str(bad), '--output', str(sentinel)], bool(i % 2))
            a.eq((run.returncode, run.stdout), (2, ''), 'malformed CLI input rejected')
            a.eq(bool(run.stderr), True, 'malformed input explains rejection')
            a.eq(sentinel.read_bytes(), b'preserved\n', 'rejection leaves existing output untouched')
            a.cli_rejections += 1


def check(verify_peer_bindings=True):
    a = Audit(); before = {p: digest(ROOT/p) for p in FILES}
    bindings(a, verify_peer_bindings)
    data = read_json(ROOT/AUTHORS[1]); module = load_model(ROOT/AUTHORS[2])
    contracts = [('baseline', {}), ('collections', {'historical_collections': 80}),
                 ('after', {'down_revenue_loss': 2.5}),
                 ('before', {'down_revenue_loss': 2.5, 'information': 'before_trade'}),
                 ('physical', {'physical_probabilities': [.3, .3, .4]}),
                 ('delay', {'escrow_settlement': '16:00'}), ('senior', {'escrow_senior_claim': 5}),
                 ('combined', {'historical_collections': 80, 'down_revenue_loss': 10,
                               'escrow_senior_claim': 5, 'escrow_settlement': '16:00'})]
    cases = {}; baseline = None
    for label, updates in contracts:
        changed = copy.deepcopy(data); changed['experiment'].update(updates)
        result = call(a, module, changed)
        cases[label] = audit_case(a, changed, result)
        if label == 'baseline': baseline = result
    a.eq(read_json(ROOT/AUTHORS[3]) == baseline, True, 'saved output is reproduction, not oracle')
    a.eq(call(a, module, data) == baseline, True, 'repeated API is deterministic')
    proofs_and_print(a, data, cases)
    boundary_checks(a, module, data)
    invalid_api(a, module, data)
    portable_and_aliases(a, baseline)
    a.eq({p: digest(ROOT/p) for p in FILES}, before, 'no persistent payload changed by check')
    summary = dict(component='finance-core-project-peer', status='passed', comparisons=a.n,
                   full_financial_contracts=len(contracts), policy_rows=a.policies, executed_journal_rows=a.events,
                   boundary_or_atom_cases=11, solved_transfers=6, visible_exact_cells_and_anchors=a.anchors,
                   api_rejections=a.api_rejections, cli_rejections=a.cli_rejections,
                   actual_protected_alias_refusals=a.aliases, portable_model_cli_runs=a.portable,
                   peer_payload_bindings=10 if verify_peer_bindings else 0)
    json.dumps(summary, allow_nan=False)
    return summary


if __name__ == '__main__':
    print(json.dumps(check(), sort_keys=True, allow_nan=False))
