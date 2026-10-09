"""Independent C12 peer: funded transactions, draw intervals and finite decisions.

Only the author's public run(data) and CLI are executed. The author checker and
private projection/execution helpers never provide expected values. This oracle
posts original asset/debt transactions, derives equity as their residual, and
intersects affine cash/equity constraints in the secured draw. check() is quiet.
All tests are bounded, deterministic and standard-library only.
"""
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
PROJECT = ROOT / 'content/projects'
MODEL = PROJECT / 'v11-c12-analysis.py'
INPUT = PROJECT / 'v11-c12-inputs.json'
PEER = ROOT / 'content/reviews/v11-c12-peer.json'
AUTHOR_FILES = (
    'content/chapters/v11-c12.html',
    'content/projects/v11-c12-inputs.json',
    'content/projects/v11-c12-analysis.py',
    'content/projects/v11-c12-output.json',
    'content/projects/v11-c12-manifest.json',
    'content/projects/v11-c12-README.txt',
    'scripts/check_v11_c12.py',
    'content/reviews/v11-c12-author.json',
    'content/reviews/v11-c12-sources.json',
)
CHECKER = 'scripts/check_v11_c12_peer.py'


def require(ok, label):
    if not ok:
        raise ValueError('C12 separate peer: ' + label)


def strict(text):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    def constant(value):
        raise ValueError('nonfinite JSON constant: ' + value)
    return json.loads(text, object_pairs_hook=unique, parse_constant=constant)


class Audit:
    def __init__(self):
        self.comparisons = 0
        self.financial_cases = 0
        self.candidate_policies = 0
        self.draw_intervals = 0
        self.journal_rows = 0
        self.printed_anchors = 0
        self.incentive_cases = 0
        self.invalid_api = 0
        self.invalid_cli = 0
        self.aliases = 0
        self.portable_runs = 0

    def eq(self, actual, expected, label):
        self.comparisons += 1
        require(type(actual) is type(expected) and actual == expected,
                label + ': ' + repr(actual) + ' != ' + repr(expected))

    def truth(self, condition, label):
        self.eq(bool(condition), True, label)

    def tree(self, actual, expected, label):
        if isinstance(expected, F):
            self.eq(actual, str(expected), label)
        elif type(expected) is dict:
            self.truth(type(actual) is dict, label + ' is an object')
            self.eq(set(actual), set(expected), label + ' keys')
            for key in expected:
                self.tree(actual[key], expected[key], label + '.' + key)
        elif type(expected) is list:
            self.truth(type(actual) is list, label + ' is a list')
            self.eq(len(actual), len(expected), label + ' length')
            for j, value in enumerate(expected):
                self.tree(actual[j], value, label + '[' + str(j) + ']')
        else:
            self.eq(actual, expected, label)

    def call(self, run, data):
        original = deepcopy(data)
        stream = StringIO()
        with redirect_stdout(stream), redirect_stderr(stream):
            result = run(data)
        self.eq(stream.getvalue(), '', 'run(data) is quiet')
        self.eq(data, original, 'run(data) preserves its input')
        self.eq(strict(json.dumps(result, allow_nan=False)), result, 'strict JSON output')
        return result

    def anchor(self, computed, printed, label):
        self.eq(F(computed), F(printed), 'printed anchor: ' + label)
        self.printed_anchors += 1


def changed(data, path, value):
    result = deepcopy(data)
    target = result
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    return result


def independent_journal(data, policy, scenario, draw):
    """Original transaction quantities; no author output is used as input.

    Signed cash is allowed here for counterfactual projections. Whether it is
    physically executable is separately tested only for a selected feasible row.
    Equity is recalculated from asset and liability positions after every event.
    """
    book = {k: F(v) for k, v in data['institution'].items()}
    terms = {k: F(v) for k, v in data['terms'].items()}
    x, b, t = policy
    assets = ('cash', 'securities', 'loans')
    debts = ('deposits', 'old_short', 'rolled', 'secured', 'term')
    state = dict(cash=book['cash'], securities=book['security_units'],
                 loans=book['loans'], deposits=book['deposits'],
                 old_short=book['short_debt'], rolled=F(0), secured=F(0), term=F(0))
    def residual():
        return sum(state[k] for k in assets) - sum(state[k] for k in debts)
    state['equity'] = residual()
    rows, closes = [], []
    pledged = F(0)

    def post(date, event, changes, affects_equity=False):
        before_equity = state['equity']
        entries = dict(changes)
        for key, amount in entries.items():
            state[key] += amount
        state['equity'] = residual()
        if affects_equity:
            entries['equity'] = state['equity'] - before_equity
        else:
            require(state['equity'] == before_equity, 'principal transaction changes equity')
        rows.append(dict(date=date, event=event, changes=entries,
                         accounts=dict(state), pledged_units=pledged))

    post(0, 'initial inventory', {})
    post(0, 'received cash equity', {'cash': b}, True)
    post(0, 'received growth deposits', {'cash': x, 'deposits': x})
    post(0, 'funded new loans', {'cash': -x, 'loans': x})
    post(0, 'received term funding', {'cash': t, 'term': t})
    post(0, 'repaid replaced old principal', {'cash': -t, 'old_short': -t})
    post(0, 'paid term origination fee', {'cash': -terms['term_fee'] * t}, True)
    mark = book['security_units'] * (F(scenario['security_price']) - 1)
    loss = F(scenario['loan_loss_fixed']) + F(scenario['loan_loss_per_new']) * x
    post(1, 'joint marks and credit writeoff', {'securities': mark, 'loans': -loss}, True)
    post(1, 'paid operating incident', {'cash': -F(scenario['operating_loss'])}, True)
    old = book['short_debt'] - t
    roll = old * F(scenario['rollover'])
    for j in range(3):
        date = j + 1
        received = F(scenario['principal_receipts'][j])
        post(date, 'collected loan principal', {'cash': received, 'loans': -received})
        post(date, 'collected interest', {'cash': F(scenario['interest_receipts'][j])}, True)
        if date == 1:
            post(date, 'received contracted rollover', {'cash': roll, 'rolled': roll})
            pledged = draw / (F(scenario['security_price']) * (1 - F(scenario['haircut'])))
            post(date, 'received secured cash against separate eligible pool',
                 {'cash': draw, 'secured': draw})
            post(date, 'repaid remaining old principal', {'cash': -old, 'old_short': -old})
        elif date == 2:
            post(date, 'repaid rollover with interest',
                 {'cash': -roll * (1 + terms['roll_interest']), 'rolled': -roll}, True)
            pledged = F(0)
            post(date, 'repaid secured debt with interest and released pledge',
                 {'cash': -draw * (1 + terms['secured_interest']), 'secured': -draw}, True)
        else:
            post(date, 'repaid term principal', {'cash': -t, 'term': -t})
        post(date, 'paid term coupon', {'cash': -terms['term_coupon'] * t}, True)
        w = F(scenario['withdrawal_fixed'][j]) + x * F(scenario['withdrawal_per_new'][j])
        post(date, 'paid deposit withdrawals', {'cash': -w, 'deposits': -w})
        closes.append(dict(state))
    return rows, closes


def draw_oracle(data, policy, scenario):
    """Intersect six affine closing inequalities with 0 <= g <= capacity.

    Unit-draw differences come from two independently posted transaction books,
    so this also checks the author's minimum-draw proof without importing it.
    """
    _, zero = independent_journal(data, policy, scenario, F(0))
    _, one = independent_journal(data, policy, scenario, F(1))
    collateral = (F(data['institution']['eligible_units']) * F(scenario['security_price'])
                  * (1 - F(scenario['haircut'])))
    cap = min(collateral, F(scenario['facility_ceiling'])) if scenario['facility_open'] else F(0)
    lower, upper = F(0), cap
    possible = True
    for base, moved in zip(zero, one):
        for account, floor_key in (('cash', 'cash_floor'), ('equity', 'equity_floor')):
            floor = F(data['limits'][floor_key])
            slope = moved[account] - base[account]
            if slope > 0:
                lower = max(lower, (floor - base[account]) / slope)
            elif slope < 0:
                upper = min(upper, (floor - base[account]) / slope)
            elif base[account] < floor:
                possible = False
    requested = max(F(0), F(data['limits']['cash_floor']) - zero[0]['cash'])
    draw = min(requested, cap)
    return zero, one, cap, requested, draw, possible and lower <= upper


def financial_oracle(audit, data, actual):
    names = ('lending', 'cash_equity', 'term_replacement')
    policies = sorted(product(*(map(F, data['choices'][name]) for name in names)))
    audit.eq(actual['candidate_count'], len(policies), 'number of policies')
    audit.eq(len(actual['candidates']), len(policies), 'complete candidate rows')
    acceptable = []
    expected_by_policy = {}
    for policy, candidate in zip(policies, actual['candidates']):
        x, b, t = policy
        concentration = ((F(data['institution']['cluster_loans']) + x)
                         / (F(data['institution']['loans']) + x))
        cost = (F(data['terms']['equity_charge']) * b
                + (F(data['terms']['term_fee']) + 3 * F(data['terms']['term_coupon'])) * t)
        reasons = []
        if concentration > F(data['limits']['concentration']):
            reasons.append('concentration')
        paths, journals = [], []
        for scenario in data['scenarios']:
            zero, one, cap, requested, draw, interval_feasible = draw_oracle(data, policy, scenario)
            rows, closes = independent_journal(data, policy, scenario, draw)
            rate = F(data['terms']['secured_interest'])
            audit.eq([one[j]['cash'] - zero[j]['cash'] for j in range(3)],
                     [F(1), -rate, -rate], 'cash marginal effect of a secured unit')
            audit.eq([one[j]['equity'] - zero[j]['equity'] for j in range(3)],
                     [F(0), -rate, -rate], 'equity marginal effect of a secured unit')
            cash_ok = all(r['cash'] >= F(data['limits']['cash_floor']) for r in closes)
            equity_ok = all(r['equity'] >= F(data['limits']['equity_floor']) for r in closes)
            audit.eq(cash_ok and equity_ok, interval_feasible, 'full draw interval versus minimum policy')
            audit.draw_intervals += 1
            snapshots = []
            for j, r in enumerate(closes):
                snapshots.append(dict(
                    cutoff=j + 1, cash_after_full_planned_payments=r['cash'], equity=r['equity'],
                    loans=r['loans'], deposits=r['deposits'], rolled_debt=r['rolled'],
                    secured_debt=r['secured'], term_debt=r['term'],
                    assets=sum(r[k] for k in ('cash', 'securities', 'loans')),
                    liabilities=sum(r[k] for k in ('deposits', 'old_short', 'rolled', 'secured', 'term')),
                    cash_short_of_floor=max(F(0), F(data['limits']['cash_floor']) - r['cash']),
                    unfinanced_payment_shortfall=max(F(0), -r['cash'])))
            paths.append(dict(scenario=scenario['id'], cash_before_secured_draw=zero[0]['cash'],
                              collateral_capacity=cap, requested_minimum_draw=requested, secured_draw=draw,
                              pledged_units=draw / (F(scenario['security_price']) * (1 - F(scenario['haircut']))),
                              cutoffs=snapshots, cash_limits_met=cash_ok, equity_limits_met=equity_ok))
            journals.append(dict(scenario=scenario['id'], rows=rows,
                                 remaining_deposits=closes[-1]['deposits'], remaining_loans=closes[-1]['loans'],
                                 remaining_securities=closes[-1]['securities']))
            if not cash_ok:
                reasons.append(scenario['id'] + ':cash')
            if not equity_ok:
                reasons.append(scenario['id'] + ':equity')
        expected = dict(policy=dict(zip(names, policy)), concentration=concentration,
                        ranking_cost=cost, feasible=not reasons, failed_gates=reasons,
                        scenario_projections=paths)
        audit.tree(candidate, expected, 'candidate ' + str(policy))
        expected_by_policy[policy] = (expected, journals)
        if not reasons:
            acceptable.append(((-x, cost, b, t), policy))
        audit.candidate_policies += 1
    acceptable.sort()
    audit.eq(actual['feasible_count'], len(acceptable), 'feasible count')
    if acceptable:
        expected, journals = expected_by_policy[acceptable[0][1]]
        audit.tree(actual['selected_policy'], expected['policy'], 'lexicographic selected policy')
        audit.tree(actual['selected_ranking_cost'], expected['ranking_cost'], 'commitment score')
        audit.tree(actual['selected_execution'], journals, 'complete selected event journals')
        for journal in journals:
            for row in journal['rows']:
                audit.truth(all(v >= 0 for k, v in row['accounts'].items() if k != 'equity'),
                            'selected execution has nonnegative asset/debt accounts')
                audit.truth(0 <= row['pledged_units'] <= F(data['institution']['eligible_units']),
                            'no double use or overpledge')
                audit.journal_rows += 1
    else:
        audit.eq(actual['selected_policy'], None, 'infeasible menu has null choice')
        audit.eq(actual['selected_ranking_cost'], None, 'infeasible menu has null score')
        audit.eq(actual['selected_execution'], [], 'no fictional execution of rejected plans')
    audit.financial_cases += 1
    return expected_by_policy


def incentive_oracle(audit, data, result):
    ins = {k: F(v) for k, v in data['incentives'].items()}
    g, f = ins['concealment_bonus'], ins['funded_penalty']
    z, d, alpha = (ins[k] for k in ('common_audit_failure', 'conditional_detection', 'false_positive'))
    # Three disjoint concealment outcomes: unavailable audit, available miss,
    # available detection. Honest false sanctions have their own two outcomes.
    events = [(z, g), ((1 - z) * (1 - d), g), ((1 - z) * d, -f)]
    audit.eq(sum(p for p, _ in events), F(1), 'audit outcome probabilities sum to one')
    conceal = sum(p * payoff for p, payoff in events)
    honest = alpha * (-f) + (1 - alpha) * 0
    expected = dict(effective_detection=events[-1][0], truthful_expected_payoff=honest,
                    conceal_expected_payoff=conceal, truthful_advantage=honest - conceal,
                    weak_truthful_threshold=(g + alpha * f) / (g + f),
                    truthful_weakly_preferred=honest >= conceal,
                    truthful_strictly_preferred=honest > conceal)
    audit.tree(result['incentive'], expected, 'independent audit outcome tree')
    audit.incentive_cases += 1


def transfer_cases(data):
    cases = [('baseline', deepcopy(data))]
    cases.append(('concentration_04', changed(data, ('limits', 'concentration'), '0.4')))
    cases.append(('equity_30', changed(data, ('choices', 'cash_equity'), ['0', '10', '20', '30'])))
    late = changed(data, ('scenarios', 2, 'facility_open'), False)
    cases.append(('late', late))
    cases.append(('late_equity_30', changed(late, ('choices', 'cash_equity'), ['0', '10', '20', '30'])))
    early = changed(data, ('scenarios', 2, 'withdrawal_fixed'), ['45', '15', '10'])
    cases.append(('earlier_withdrawal', early))
    injected = changed(early, ('choices',), dict(lending=['20'], cash_equity=['24.1'], term_replacement=['20']))
    cases.append(('earlier_exact_injection', injected))
    cases.append(('interest_04', changed(data, ('terms', 'secured_interest'), '0.4')))
    capital = changed(data, ('choices',), dict(lending=['20'], cash_equity=['21.4'], term_replacement=['20']))
    cases.append(('all_event_equity', capital))
    cases.append(('eligible_20', changed(data, ('institution', 'eligible_units'), '20')))
    cases.append(('zero_secured_interest', changed(data, ('terms', 'secured_interest'), '0')))
    tie = deepcopy(data)
    tie['scenarios'] = [tie['scenarios'][0]]
    tie['limits'].update(cash_floor='0', equity_floor='0')
    tie['terms'].update(term_fee='0', term_coupon='0', equity_charge='0')
    cases.append(('exact_score_tie', tie))
    ceiling = changed(data, ('scenarios', 2, 'facility_ceiling'), '12.6')
    cases.append(('exact_facility_boundary', ceiling))
    cases.append(('below_facility_boundary', changed(ceiling, ('scenarios', 2, 'facility_ceiling'), '12.59999999')))
    return cases


def printed_results(audit, data, oracles, outputs, html):
    def record(case, policy=(20, 20, 20), scenario=2):
        candidate, journals = oracles[case][tuple(map(F, policy))]
        return candidate, candidate['scenario_projections'][scenario], journals[scenario]
    c, p, j = record('baseline')
    initial = j['rows'][0]['accounts']
    audit.anchor(sum(initial[k] for k in ('cash', 'securities', 'loans')), '200', 'opening assets')
    audit.anchor(sum(initial[k] for k in ('deposits', 'old_short')), '170', 'opening liabilities')
    audit.anchor(initial['equity'], '30', 'opening equity')
    by_event = {r['event']: r for r in j['rows'] if r['date'] == 0}
    opening = by_event['paid term origination fee']['accounts']
    for k, v in dict(cash='43.6', securities='60', loans='136', deposits='160',
                     old_short='10', term='20', equity='49.6').items():
        audit.anchor(opening[k], v, 'date0 ' + k)
    audit.anchor(sum(opening[k] for k in ('cash', 'securities', 'loans')), '239.6', 'date0 assets')
    audit.anchor(sum(opening[k] for k in ('deposits', 'old_short', 'term')), '190', 'date0 debt')
    for k, v in dict(cash_before_secured_draw='-38/5', collateral_capacity='27/2',
                     secured_draw='63/5', pledged_units='28').items():
        audit.anchor(p[k], v, 'joint ' + k)
    marks = next(r for r in j['rows'] if r['event'] == 'joint marks and credit writeoff')
    audit.anchor(marks['changes']['securities'], '-15', 'security write-down')
    audit.anchor(marks['changes']['loans'], '-14', 'loan write-down')
    for field, value in dict(assets='167', liabilities='146.6', loans='117', deposits='114').items():
        audit.anchor(p['cutoffs'][0][field], value, 'first balance sheet ' + field)
    audit.anchor(F(data['institution']['eligible_units']) - p['pledged_units'], '2', 'unpledged eligible remainder')
    repayment = next(r for r in j['rows'] if r['event'] == 'repaid secured debt with interest and released pledge')
    audit.anchor(-repayment['changes']['cash'], '12.978', 'secured principal and interest cash')
    for r, cash, equity in zip(p['cutoffs'], ['5', '8911/500', '4311/500'],
                               ['102/5', '11411/500', '12311/500']):
        audit.anchor(r['cash_after_full_planned_payments'], cash, 'joint closing cash')
        audit.anchor(r['equity'], equity, 'joint closing equity')
    for key, v in dict(assets='105.622', liabilities='81', deposits='81', loans='52').items():
        audit.anchor(p['cutoffs'][-1][key], v, 'joint residual ' + key)
    audit.anchor(min(r['accounts']['equity'] for r in j['rows']), '18.6', 'intraday minimum')
    audit.anchor(c['concentration'], '7/17', 'gross concentration')
    audit.anchor(c['ranking_cost'], '13/5', 'score')
    audit.eq(outputs['baseline']['feasible_count'], 3, 'exactly three baseline policies')
    for scenario, cash, equity in (
        (0, ['36.4', '72', '62.8'], ['51.4', '54', '55.8']),
        (1, ['15.4', '46.1', '36.9'], ['37.4', '40.1', '41.9'])):
        path = c['scenario_projections'][scenario]
        for r, cv, ev in zip(path['cutoffs'], cash, equity):
            audit.anchor(r['cash_after_full_planned_payments'], cv, 'other stress cash')
            audit.anchor(r['equity'], ev, 'other stress equity')
    _, rejected, _ = record('baseline', (20, 20, 10))
    for actual, expected, label in (
        (rejected['cash_before_secured_draw'], '-17.3', 'rejected pre-draw'),
        (rejected['cutoffs'][0]['equity'], '20.7', 'rejected positive equity'),
        (rejected['cutoffs'][0]['cash_after_full_planned_payments'], '-3.8', 'rejected signed cash'),
        (rejected['cutoffs'][0]['unfinanced_payment_shortfall'], '3.8', 'missing payment funds'),
        (rejected['cutoffs'][0]['cash_short_of_floor'], '8.8', 'missing floor funds')):
        audit.anchor(actual, expected, label)
    # Recover affine policy bounds by finite unit differences of original ledgers.
    s = data['scenarios'][2]
    def first(x, b, t):
        return independent_journal(data, tuple(map(F, (x, b, t))), s, F(0))[1][0]
    base = first(0, 0, 0)
    audit.anchor(base['cash'], '-41', 'joint first cash constant')
    audit.anchor(first(1, 0, 0)['cash'] - base['cash'], '-0.30', 'lending cash coefficient')
    audit.anchor(first(0, 1, 0)['cash'] - base['cash'], '1', 'equity cash coefficient')
    audit.anchor(first(0, 0, 1)['cash'] - base['cash'], '0.97', 'term cash coefficient')
    audit.anchor(F(5) - F('13.5') - base['cash'], '32.5', 'first reserve bound')
    audit.anchor(F(10) + F('.97') * 20, '29.4', 'b <= 10 impossibility bound')
    audit.anchor(F(20) + F('.97') * 10, '29.7', 't <= 10 impossibility bound')
    audit.anchor((F(20) + F('.97') * 20 - F('32.5')) / F('.3'), '23', 'continuous cash x bound')
    audit.anchor((first(0, 20, 20)['equity'] - 20) / F('.2'), '22', 'continuous equity x bound')
    audit.anchor(base['equity'], '5', 'first equity constant')
    audit.anchor(first(1, 0, 0)['equity'] - base['equity'], '-.2', 'equity lending coefficient')
    audit.anchor(first(0, 0, 1)['equity'] - base['equity'], '-.03', 'equity term coefficient')
    _, at_zero, _ = record('baseline', (0, 20, 20))
    _, at_ten, _ = record('baseline', (10, 20, 20))
    audit.anchor(at_zero['secured_draw'], '6.6', 'draw intercept')
    audit.anchor((at_ten['secured_draw'] - at_zero['secured_draw']) / 10, '.3', 'draw slope')
    for index, field, intercept, slope in (
        (1, 'cash_after_full_planned_payments', '26.002', '-.409'),
        (2, 'cash_after_full_planned_payments', '17.802', '-.459'),
        (1, 'equity', '27.002', '-.209'), (2, 'equity', '28.802', '-.209')):
        audit.anchor(at_zero['cutoffs'][index][field], intercept, 'later affine intercept')
        audit.anchor((at_ten['cutoffs'][index][field] - at_zero['cutoffs'][index][field]) / 10,
                     slope, 'later affine slope')
    audit.anchor((F(116) * F('.4') - 36) / (1 - F('.4')), '52/3', 'concentration bound')
    audit.anchor(F(36, 116), '9/29', 'no-growth concentration boundary')
    audit.anchor(F(116) - 36, '80', 'positive derivative numerator')
    _, tight, _ = record('concentration_04', (10, 20, 20))
    audit.eq(outputs['concentration_04']['feasible_count'], 2, 'two concentration-feasible choices')
    for value, expected in zip([tight['secured_draw']] + [r['cash_after_full_planned_payments'] for r in tight['cutoffs']]
                               + [tight['cutoffs'][0]['equity']], ['9.6', '5', '21.912', '13.212', '22.4']):
        audit.anchor(value, expected, 'tight concentration transfer')
    extra, path, _ = record('equity_30', (30, 30, 20))
    for value, expected in zip([path['cash_before_secured_draw'], path['secured_draw']]
                               + [r['cash_after_full_planned_payments'] for r in path['cutoffs']]
                               + [path['cutoffs'][0]['equity'], extra['ranking_cost']],
                               ['-.6', '28/5', '5', '3004/125', '3583/250', '28.4', '3.4']):
        audit.anchor(value, expected, 'extra equity timely transfer')
    audit.eq(outputs['late']['selected_policy'], None, 'late original menu empty')
    audit.anchor(first(0, 20, 20)['cash'], '-1.6', 'best unfinanced late first cash')
    _, late, _ = record('late_equity_30', (10, 30, 20))
    for value, expected in zip([r['cash_after_full_planned_payments'] for r in late['cutoffs']]
                               + [late['cutoffs'][0]['equity'], late['secured_draw']],
                               ['5.4', '32.2', '23.5', '32.4', '0']):
        audit.anchor(value, expected, 'funded late-facility response')
    audit.anchor((F(30) + F('.97') * 20 - 41 - 5) / F('.3'), '34/3', 'late x bound')
    _, early, _ = record('earlier_withdrawal')
    audit.anchor(early['cash_before_secured_draw'], '-12.6', 'early fixed-plan funding projection')
    audit.anchor(early['cutoffs'][0]['cash_after_full_planned_payments'], '.9', 'early fixed-plan signed cash')
    audit.anchor(early['cutoffs'][0]['cash_short_of_floor'], '4.1', 'minimum timely injection')
    _, early_zero, _ = record('earlier_withdrawal', (0, 20, 20))
    audit.anchor(early_zero['secured_draw'], '11.6', 'earlier selected draw')
    audit.anchor((F('6.9') - 5) / F('.3'), '19/3', 'earlier continuous bound')
    _, rate, _ = record('interest_04')
    audit.anchor(F('.37') * p['secured_draw'], '4.662', 'extra interest')
    audit.anchor(rate['cutoffs'][2]['cash_after_full_planned_payments'], '3.96', 'old-plan higher-interest cash')
    audit.anchor(rate['cutoffs'][1]['equity'], '18.16', 'old-plan higher-interest equity')
    _, rate_ten, _ = record('interest_04', (10, 20, 20))
    audit.anchor(rate_ten['secured_draw'], '9.6', 'new higher-interest draw')
    audit.anchor(rate_ten['cutoffs'][2]['cash_after_full_planned_payments'], '9.66', 'new higher-interest cash')
    audit.anchor(rate_ten['cutoffs'][1]['equity'], '21.36', 'new higher-interest equity')
    _, capital, capital_journal = record('all_event_equity', (20, F('21.4'), 20))
    audit.anchor(20 - min(r['accounts']['equity'] for r in j['rows']), '1.4', 'all-events minimum extra capital')
    audit.anchor(capital['secured_draw'], '11.2', 'all-events reduced draw')
    audit.anchor(min(r['accounts']['equity'] for r in capital_journal['rows']), '20', 'all-events restored minimum')
    _, collateral, _ = record('eligible_20')
    audit.anchor(collateral['collateral_capacity'], '9', 'retention collateral capacity')
    audit.anchor(collateral['cutoffs'][0]['cash_after_full_planned_payments'], '1.4', 'retention projected cash')
    audit.anchor(collateral['cutoffs'][0]['cash_short_of_floor'], '3.6', 'retention reserve deficit')
    audit.anchor(F('32.5') + F('.3') * 10, '35.5', 'retention x10 inequality')
    for calc, expected, label in (
        (F('.8') * F('.5'), '.4', 'baseline effective detection'),
        (F(4, 10), '.4', 'baseline truthful threshold'),
        (F('.8') * F('.75'), '.6', 'improved effective detection'),
        (F('.4') * 4 - F('.6') * 6, '-2', 'improved concealment payoff'),
        ((F(4) + F('.05') * 6) / 10, '.43', 'false-sanction threshold'),
        (((F(4) + F('.05') * 6) / 10) / F('.8'), '43/80', 'conditional detection bound'),
        (F(4) / (4 + 3), '4/7', 'collectible f3 effective bound'),
        (F(4, 7) / F('.8'), '5/7', 'collectible f3 conditional bound'),
        (F('.3') * 10 - F('4.3'), '-1.3', 'worst uncertain truthful advantage'),
        (F('.6') * 10 - F('4.3'), '1.7', 'best uncertain truthful advantage'),
        (F('.45') * 10 - F('4.3'), '.2', 'midpoint conditional advantage'),
        (F('.45') * 10 - 4, '.5', 'retention truthful advantage')):
        audit.anchor(calc, expected, label)
    # Bind the printed exact fractions themselves, not only model decimals.
    for decimal, fraction in [('17.822', '8911/500'), ('22.822', '11411/500'),
                              ('8.622', '4311/500'), ('24.622', '12311/500'),
                              ('5.6', '28/5'), ('24.032', '3004/125'),
                              ('14.332', '3583/250'), ('0.5375', '43/80')]:
        audit.truth(decimal in html and fraction in html, 'printed fraction and decimal both present')
        audit.anchor(F(decimal), fraction, 'printed exact equality')


class Reader(HTMLParser):
    def __init__(self):
        super().__init__()
        self.worked = self.exercises = self.solutions = 0
        self.depth = 0
        self.exercise_depth = self.solution_depth = None
        self.group = False
        self.ids, self.links, self.sources = [], [], set()

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        classes = a.get('class', '').split()
        if 'id' in a:
            self.ids.append(a['id'])
        if tag == 'aside' and 'worked' in classes:
            self.worked += 1
        if tag == 'a':
            self.links.append(a.get('href', ''))
            if 'data-source' in a:
                self.sources.add(a['data-source'])
        if tag == 'details' and 'solutions' in classes:
            self.group = True
        if tag == 'ol':
            self.depth += 1
            if 'exercises' in classes:
                self.exercise_depth = self.depth
            if self.group and self.solution_depth is None:
                self.solution_depth = self.depth
        if tag == 'li':
            if self.depth == self.exercise_depth:
                self.exercises += 1
            if self.depth == self.solution_depth:
                self.solutions += 1

    def handle_endtag(self, tag):
        if tag == 'ol':
            if self.depth == self.exercise_depth:
                self.exercise_depth = None
            if self.depth == self.solution_depth:
                self.solution_depth = None
            self.depth -= 1
        if tag == 'details':
            self.group = False


def bindings_and_reader(audit, bind_peer):
    def bindings(rows, expected, label):
        audit.eq(len(rows), len(expected), label + ' binding count')
        audit.eq({r['path'] for r in rows}, set(expected), label + ' exact membership')
        for r in rows:
            body = (ROOT / r['path']).read_bytes()
            audit.eq(len(body), r['bytes'], label + ' bytes ' + r['path'])
            audit.eq(sha256(body).hexdigest(), r['sha256'], label + ' SHA256 ' + r['path'])
    author = strict((ROOT / 'content/reviews/v11-c12-author.json').read_text())
    bindings(author['reviewed_hashes'], set(AUTHOR_FILES) - {'content/reviews/v11-c12-author.json'}, 'author nonself')
    manifest = strict((PROJECT / 'v11-c12-manifest.json').read_text())
    files = manifest['files']
    names = {'v11-c12-' + suffix for suffix in ('inputs.json', 'analysis.py', 'output.json', 'README.txt')}
    audit.eq(len(files), 4, 'manifest exact count')
    audit.eq({r['file'] for r in files}, names, 'manifest exact payload set')
    for r in files:
        body = (PROJECT / r['file']).read_bytes()
        audit.eq(len(body), r['bytes'], 'manifest bytes')
        audit.eq(sha256(body).hexdigest(), r['sha256'], 'manifest SHA256')
    if bind_peer:
        peer = strict(PEER.read_text())
        bindings(peer['reviewed_hashes'], set(AUTHOR_FILES) | {CHECKER}, 'peer nine plus checker')
    html = (ROOT / AUTHOR_FILES[0]).read_text()
    parser = Reader()
    parser.feed(html)
    parser.close()
    audit.eq((parser.worked, parser.exercises, parser.solutions), (4, 10, 10), 'reader counted content')
    audit.eq(len(parser.ids), len(set(parser.ids)), 'unique reader IDs')
    audit.eq(parser.sources, {'v11-c12-bcbs-governance2015', 'v08-c11-oecd-board', 'v08-c11-oecd-scope'}, 'scoped sources')
    assets = {'v11-c12-' + suffix for suffix in ('inputs.json', 'analysis.py', 'output.json', 'manifest.json', 'README.txt')}
    audit.truth(assets <= set(parser.links), 'five flat portable asset links')
    for name in assets:
        audit.truth((PROJECT / name).is_file(), 'linked asset exists')
    source = strict((ROOT / 'content/reviews/v11-c12-sources.json').read_text())
    audit.eq({r['id'] for r in source['proposals']} | {r['id'] for r in source['reuse']}, parser.sources,
             'source proposal/reuse membership')
    return html


def invalid_api(audit, run, base):
    mutations = [
        (('schema',), True), (('schema',), 2), (('units',), ''), (('extra',), 1),
        (('institution', 'cash'), 24.0), (('institution', 'cash'), True),
        (('institution', 'cash'), 'NaN'), (('institution', 'cash'), '2.4e1'),
        (('institution', 'cash'), '24/1'), (('institution', 'cash'), '-1'),
        (('institution', 'cash'), '0.000000001'), (('institution', 'cash'), '10001'),
        (('institution', 'loans'), '0'), (('institution', 'eligible_units'), '61'),
        (('institution', 'cluster_loans'), '117'), (('institution', 'deposits'), '300'),
        (('choices', 'lending'), ['0', '0.0']), (('choices', 'lending'), []),
        (('choices', 'lending'), ['0', '1', '2', '3', '4', '5']),
        (('choices', 'term_replacement'), ['31']),
        (('terms', 'secured_interest'), '-0.1'), (('terms', 'secured_interest'), '1.00000001'),
        (('limits', 'concentration'), '1.01'), (('scenarios',), []),
        (('scenarios', 0, 'facility_open'), 1), (('scenarios', 0, 'security_price'), '0'),
        (('scenarios', 0, 'haircut'), '1'), (('scenarios', 0, 'id'), 'Bad ID'),
        (('scenarios', 1, 'id'), 'calm'), (('scenarios', 0, 'principal_receipts'), ['1', '2']),
        (('scenarios', 0, 'principal_receipts'), ['117', '0', '0']),
        (('scenarios', 0, 'withdrawal_fixed'), ['141', '0', '0']),
        (('scenarios', 0, 'withdrawal_per_new'), ['1.1', '0', '0']),
        (('scenarios', 0, 'operating_loss'), '24'),
        (('incentives', 'concealment_bonus'), '0'), (('incentives', 'false_positive'), '1.01'),
    ]
    bad = [changed(base, path, value) for path, value in mutations]
    bad += [None, [], changed(base, ('institution',), [])]
    for data in bad:
        original = deepcopy(data)
        stream = StringIO()
        try:
            with redirect_stdout(stream), redirect_stderr(stream):
                run(data)
        except ValueError:
            pass
        else:
            raise ValueError('C12 separate peer: invalid API input was accepted')
        audit.eq(data, original, 'rejected input unmodified')
        audit.eq(stream.getvalue(), '', 'rejected API quiet')
        audit.invalid_api += 1


def command(args, cwd):
    return subprocess.run(args, cwd=cwd, text=True, capture_output=True, timeout=35)


def cli_checks(audit, base, expected_bytes):
    with tempfile.TemporaryDirectory(prefix='v11-c12-peer-cli-') as tmp:
        folder = Path(tmp)
        model = folder / MODEL.name
        source = folder / INPUT.name
        model.write_bytes(MODEL.read_bytes())
        source.write_bytes(INPUT.read_bytes())
        destination = folder / 'destination.json'
        guard = b'preserved existing destination\n'
        bad_documents = [
            '{"schema":1,"schema":1}', '{"schema":NaN}', '{"schema":Infinity}',
            '{"schema":-Infinity}', '{', '[]',
            json.dumps(changed(base, ('limits', 'concentration'), True)), ' ' * 65537,
        ]
        for flag in ([], ['-O']):
            prefix = [sys.executable] + flag + [str(model)]
            # Both documented paths work from a foreign cwd and produce no stdout/stderr.
            for argv, out in (([], model.with_name('v11-c12-output.json')),
                              (['--input', str(source), '--output', str(destination)], destination)):
                response = command(prefix + argv, '/')
                audit.eq((response.returncode, response.stdout, response.stderr), (0, '', ''), 'quiet portable model CLI')
                audit.eq(out.read_bytes(), expected_bytes, 'canonical portable output bytes')
                audit.portable_runs += 1
            for text in bad_documents:
                bad = folder / 'invalid.json'
                bad.write_text(text)
                destination.write_bytes(guard)
                response = command(prefix + ['--input', str(bad), '--output', str(destination)], '/')
                audit.eq(response.returncode, 2, 'invalid CLI explicit exit')
                audit.eq(response.stdout, '', 'invalid CLI stdout empty')
                audit.truth(bool(response.stderr) and 'Traceback' not in response.stderr, 'invalid CLI concise stderr')
                audit.eq(destination.read_bytes(), guard, 'invalid CLI preserves destination')
                audit.invalid_cli += 1
            (folder / 'nested').mkdir(exist_ok=True)
            aliases = []
            for protected in (source, model):
                aliases.append(protected)
                aliases.append(folder / 'nested' / '..' / protected.name)
                symbolic = folder / ('symbolic-' + protected.name)
                hard = folder / ('hard-' + protected.name)
                if symbolic.is_symlink():
                    symbolic.unlink()
                if hard.exists():
                    hard.unlink()
                symbolic.symlink_to(protected)
                os.link(protected, hard)
                aliases.extend((symbolic, hard))
            original_source, original_model = source.read_bytes(), model.read_bytes()
            for target in aliases:
                response = command(prefix + ['--input', str(source), '--output', str(target)], '/')
                audit.eq(response.returncode, 2, 'protected direct/resolved/symlink/hardlink rejected')
                audit.eq(response.stdout, '', 'alias rejection quiet stdout')
                audit.truth(bool(response.stderr) and 'Traceback' not in response.stderr, 'alias rejection is explicit')
                audit.eq((source.read_bytes(), model.read_bytes()), (original_source, original_model), 'protected bytes unchanged')
                audit.aliases += 1
            default = model.with_name('v11-c12-output.json')
            for protected in (source, model):
                default.unlink()
                default.symlink_to(protected)
                response = command(prefix, '/')
                audit.eq(response.returncode, 2, 'default output alias guard active')
                audit.eq(response.stdout, '', 'default guard quiet stdout')
                audit.eq((source.read_bytes(), model.read_bytes()), (original_source, original_model), 'default alias preserves bytes')
                audit.aliases += 1
            default.unlink()


def isolated_checks(audit):
    with tempfile.TemporaryDirectory(prefix='v11-c12-peer-isolated-') as tmp:
        root = Path(tmp)
        paths = list(AUTHOR_FILES) + [CHECKER, 'content/reviews/v11-c12-peer.json']
        for relative in paths:
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, target)
        audit.eq(sum(1 for p in root.rglob('*') if p.is_file()), 11, 'isolated package has exactly eleven files')
        program = ("import contextlib,io,json,runpy; s=io.StringIO(); "
                   "m=runpy.run_path(" + repr(str(root / CHECKER)) + "); "
                   "\nwith contextlib.redirect_stdout(s),contextlib.redirect_stderr(s): r=m['check'](portable=False)"
                   "\nif s.getvalue(): raise ValueError('nonquiet check API')"
                   "\nprint(json.dumps(r,sort_keys=True,allow_nan=False))")
        results = []
        for flag in ([], ['-O']):
            response = command([sys.executable] + flag + ['-c', program], '/')
            audit.eq(response.returncode, 0, 'isolated independent checker exit')
            audit.eq(response.stderr, '', 'isolated checker stderr')
            result = strict(response.stdout)
            audit.eq(result['status'], 'passed', 'isolated peer check status')
            results.append(result)
            audit.portable_runs += 1
        audit.eq(results[0], results[1], 'isolated normal/optimized summaries identical')


def check(portable=True, bind_peer=True):
    audit = Audit()
    html = bindings_and_reader(audit, bind_peer)
    base = strict(INPUT.read_text())
    stream = StringIO()
    with redirect_stdout(stream), redirect_stderr(stream):
        run = runpy.run_path(str(MODEL))['run']
    audit.eq(stream.getvalue(), '', 'quiet model import')
    outputs, oracles = {}, {}
    for name, data in transfer_cases(base):
        output = audit.call(run, data)
        outputs[name] = output
        oracles[name] = financial_oracle(audit, data, output)
        incentive_oracle(audit, data, output)
    expected_policies = {
        'baseline': ('20', '20', '20'), 'concentration_04': ('10', '20', '20'),
        'equity_30': ('30', '30', '20'), 'late_equity_30': ('10', '30', '20'),
        'earlier_withdrawal': ('0', '20', '20'), 'earlier_exact_injection': ('20', '241/10', '20'),
        'interest_04': ('10', '20', '20'), 'all_event_equity': ('20', '107/5', '20'),
        'exact_score_tie': ('30', '0', '0'), 'exact_facility_boundary': ('20', '20', '20'),
        'below_facility_boundary': ('10', '20', '20'),
    }
    for name, policy in expected_policies.items():
        audit.eq(outputs[name]['selected_policy'], dict(zip(('lending', 'cash_equity', 'term_replacement'), policy)),
                 'explicit economic transfer: ' + name)
    saved = strict((PROJECT / 'v11-c12-output.json').read_text())
    audit.eq(outputs['baseline'], saved, 'entire saved output matches audited fresh baseline')
    canonical = (json.dumps(outputs['baseline'], indent=2, sort_keys=True) + '\n').encode()
    audit.eq((PROJECT / 'v11-c12-output.json').read_bytes(), canonical, 'canonical output encoding')
    printed_results(audit, base, oracles, outputs, html)
    # Incentive cases use a one-policy, one-scenario input to avoid repeating a
    # financial enumeration when only the two-action payoff contract changes.
    incentive_base = deepcopy(base)
    incentive_base['choices'] = dict(lending=['20'], cash_equity=['20'], term_replacement=['20'])
    incentive_base['scenarios'] = [incentive_base['scenarios'][0]]
    for changes in [
        {'conditional_detection': '0.75'}, {'false_positive': '0.05'},
        {'false_positive': '0.05', 'conditional_detection': '0.75'},
        {'funded_penalty': '3', 'common_audit_failure': '0.5', 'conditional_detection': '1'},
        {'funded_penalty': '0', 'common_audit_failure': '0', 'conditional_detection': '1'},
        {'false_positive': '1', 'common_audit_failure': '0', 'conditional_detection': '1'},
        *[{'false_positive': '0.05', 'common_audit_failure': '0', 'conditional_detection': p}
          for p in ('0.3', '0.43', '0.45', '0.6')],
    ]:
        data = deepcopy(incentive_base)
        data['incentives'].update(changes)
        result = audit.call(run, data)
        incentive_oracle(audit, data, result)
    # Returned objects are independent of subsequent runs and retained inputs.
    first = audit.call(run, incentive_base)
    baseline_copy = deepcopy(first)
    first['selected_policy']['lending'] = 'mutated result'
    audit.eq(audit.call(run, incentive_base), baseline_copy, 'fresh output isolation')
    invalid_api(audit, run, base)
    cli_checks(audit, base, canonical)
    if portable:
        require(bind_peer, 'portable package requires final peer bindings')
        isolated_checks(audit)
    return dict(chapter='v11-c12', status='passed', comparisons=audit.comparisons,
                financial_cases=audit.financial_cases, candidate_policies=audit.candidate_policies,
                independent_draw_intervals=audit.draw_intervals, actual_journal_rows=audit.journal_rows,
                printed_exact_anchors=audit.printed_anchors, incentive_outcome_cases=audit.incentive_cases,
                invalid_api_cases=audit.invalid_api, invalid_cli_cases=audit.invalid_cli,
                protected_alias_attempts=audit.aliases, portable_runs=audit.portable_runs,
                author_payloads_bound=9 if bind_peer else 0, own_checker_bound=bind_peer,
                worked_examples=4, solved_exercises=10,
                limits='Finite synthetic contracts; no empirical calibration, national legal authority, full runoff, external human certification or visual QA.')


if __name__ == '__main__':
    print(json.dumps(check(), sort_keys=True, allow_nan=False))
