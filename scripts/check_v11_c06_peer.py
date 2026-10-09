"""Separate bounded C06 peer checks. Only public run(data) and CLI are executed.

No author checker or candidate helper supplies an oracle. Small feasible-subset
sets, Boolean latent states and instruction-level journals certify the claims.
check() is quiet, strict-JSON-safe and independent of Python assert statements.
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
MODEL = PROJECT / 'v11-c06-analysis.py'
INPUT = PROJECT / 'v11-c06-inputs.json'
REVIEW = ROOT / 'content/reviews/v11-c06-peer.json'
AUTHOR_FILES = (
    'content/chapters/v11-c06.html',
    'content/projects/v11-c06-inputs.json',
    'content/projects/v11-c06-analysis.py',
    'content/projects/v11-c06-output.json',
    'content/projects/v11-c06-manifest.json',
    'content/projects/v11-c06-README.txt',
    'scripts/check_v11_c06.py',
    'content/reviews/v11-c06-author.json',
    'content/reviews/v11-c06-sources.json',
)


def require(condition, label):
    if not condition:
        raise ValueError('C06 separate peer: ' + label)


def strict(text):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    def constant(value):
        raise ValueError('nonfinite constant ' + value)
    return json.loads(text, object_pairs_hook=unique, parse_constant=constant)


class Audit:
    def __init__(self):
        self.comparisons = 0
        self.cases = 0
        self.api_rejections = 0
        self.cli_rejections = 0
        self.alias_rejections = 0
        self.portable_successes = 0
        self.small_schedule_cases = 0
        self.journal_rows = 0

    def eq(self, actual, expected, label):
        self.comparisons += 1
        require(actual == expected, label + ': ' + repr(actual) + ' != ' + repr(expected))

    def truth(self, condition, label):
        self.eq(bool(condition), True, label)

    def call(self, run, data):
        before = deepcopy(data)
        stream = StringIO()
        with redirect_stdout(stream), redirect_stderr(stream):
            result = run(data)
        self.eq(stream.getvalue(), '', 'public API is quiet')
        self.eq(data, before, 'public API preserves its argument')
        self.eq(strict(json.dumps(result, allow_nan=False)), result, 'strict JSON result')
        self.cases += 1
        return result


def changed(base, path, value):
    data = deepcopy(base)
    target = data
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    return data


def queue_certificate(a, data, out, capacities):
    """Certify the reported schedule without using a model scheduling helper."""
    inventory = {p['id']: p for p in data['payments']}
    completed = {}
    unit, cash = F(data['unit_amount']), F(data['opening_cash'])
    priority = lambda key: (inventory[key]['deadline'], inventory[key]['release'], key)
    a.eq(len(out['rows']), data['horizon'], 'one reported row per cutoff')
    for t, row in enumerate(out['rows'], 1):
        pending = {key for key, p in inventory.items() if p['release'] <= t} - completed.keys()
        served = row['completed_ids']
        a.truth(len(set(served)) == len(served) and set(served) <= pending,
                'each completion is unique, released and outstanding')
        cap = capacities[t-1]
        a.eq(len(served), min(cap, len(pending)), 'all useful slots are used')
        left = pending - set(served)
        a.eq(served, sorted(served, key=priority), 'order within serviced batch')
        a.truth(not served or not left or max(map(priority, served)) <= min(map(priority, left)),
                'no available earlier priority job displaced')
        completed.update({key: t for key in served})
        a.eq((row['cutoff'], row['arrivals'], row['available_before_service'], row['capacity'],
              row['unused_slots'], row['backlog_after'], row['due_and_unfinished_ids']),
             (t, [p['id'] for p in data['payments'] if p['release'] == t], len(pending), cap,
              cap-len(served), len(left), sorted((key for key in left if inventory[key]['deadline'] <= t), key=priority)),
             'reported dated work stocks and overdue obligations')
        a.eq((F(row['planned_cash_after']), F(row['planned_payment_liability_after'])),
             (cash-unit*len(completed), unit*(len(inventory)-len(completed))),
             'a planned correct payment reduces cash and liability equally')
    misses = [key for key, p in inventory.items() if completed.get(key, data['horizon']+1) > p['deadline']]
    late = [key for key, p in inventory.items() if key in completed and completed[key] > p['deadline']]
    unfinished = [key for key in inventory if key not in completed]
    a.eq((out['completion_cutoffs'], out['deadline_missed_ids'], out['completed_late_ids'],
          out['unfinished_ids'], out['on_time_count'], out['all_deadlines_met']),
         (completed, misses, late, unfinished, len(inventory)-len(misses), not misses),
         'completion is distinct from timely completion')


def timely_subset_oracle(payments, capacities):
    """All reachable timely completion subsets for at most six jobs.

    At each date, choose any subset of currently eligible uncompleted jobs,
    including deliberate idling. Expired jobs are never selected. This computes
    maximum timely cardinality, a stronger objective than the candidate claims.
    It uses no greedy priority, augmenting paths or candidate completion map.
    """
    require(len(payments) <= 6, 'small independent schedule oracle stays bounded')
    reachable = {0}
    for t, capacity in enumerate(capacities, 1):
        eligible = sum(1 << i for i, p in enumerate(payments) if p['release'] <= t <= p['deadline'])
        future = set()
        for done in reachable:
            available = eligible & ~done
            subset = available
            while True:
                if subset.bit_count() <= capacity:
                    future.add(done | subset)
                if subset == 0:
                    break
                subset = (subset-1) & available
        reachable = future
    return max(mask.bit_count() for mask in reachable)


def ledger(a, data, out):
    """Post each debit against an independently scanned obligation ticket."""
    rows = data['observed_settlements']
    tickets = {}
    for p in data['payments']:
        valid = [(i, row['cutoff']) for i, row in enumerate(rows)
                 if row['id'] == p['id'] and row['cutoff'] >= p['release']]
        tickets[p['id']] = (p, valid[0] if valid else None)
    expected_rows = []
    cash, liability, equity = map(F, (data['opening_cash'], data['opening_payment_liability'], data['opening_equity']))
    unit = F(data['unit_amount'])
    for i, row in enumerate(rows):
        ticket = tickets.get(row['id'])
        if ticket is None:
            kind = 'unknown_instruction'
        elif row['cutoff'] < ticket[0]['release']:
            kind = 'before_authorization'
        elif ticket[1][0] != i:
            kind = 'duplicate_settlement'
        else:
            kind = 'authorized_on_time' if row['cutoff'] <= ticket[0]['deadline'] else 'authorized_late'
        cash -= unit
        if kind.startswith('authorized_'):
            liability -= unit
        else:
            equity -= unit
        a.eq(cash-liability-equity, 0, 'identity after each observed journal entry')
        a.journal_rows += 1
        expected_rows.append(dict(row, classification=kind))
    report = out['observed_reconciliation']
    a.eq(report['rows'], expected_rows, 'all exact observed classifications')
    late = [row['id'] for row in expected_rows if row['classification'] == 'authorized_late']
    missing = [key for key, (_, paid) in tickets.items() if paid is None]
    anomalies = [dict(id=row['id'], cutoff=row['cutoff'], reason=row['classification'])
                 for row in expected_rows if not row['classification'].startswith('authorized_')]
    counts = [sum(row['cutoff'] == t for row in rows) for t in range(1, data['horizon']+1)]
    a.eq((report['authorized_late_ids'], report['missing_instruction_ids'], report['anomalies'],
          report['on_time_count'], report['acknowledgment_count'], report['unique_authorized_settlements'], report['slot_counts']),
         (late, missing, anomalies, len(tickets)-len(missing)-len(late), len(rows), len(tickets)-len(missing), counts),
         'ID, count and date statuses')
    a.eq(tuple(F(report[k]) for k in ('cash_debits', 'authorized_liability_discharged', 'bank_borne_exception_loss',
                                     'closing_cash', 'closing_payment_liability', 'closing_equity', 'identity_residual')),
         (F(data['opening_cash'])-cash, F(data['opening_payment_liability'])-liability,
          F(data['opening_equity'])-equity, cash, liability, equity, F(0)), 'full journal balances')
    a.eq(report['within_stipulated_capacity'], all(n <= c for n, c in zip(counts, out['capacity']['constrained'])),
         'observations that contradict stipulated capacity remain visible')


def latent_risk(risk):
    """Enumerate 32 latent states, including irrelevant misses on common failure.

    Independent Bernoulli latent draws reproduce the specified conditional law;
    common failure forces both effective misses regardless of the latent misses.
    No independence across different requests is needed or added.
    """
    probabilities = [F(risk[k]) for k in ('unauthorized_attempt_probability', 'common_failure_probability',
                      'first_miss_given_no_common', 'second_miss_given_no_common', 'second_control_coverage')]
    mass = m1 = m2 = joint = escaped = F(0)
    conditional = F(0)
    for bits in product((0, 1), repeat=5):
        weight = F(1)
        for bit, probability in zip(bits, probabilities):
            weight *= probability if bit else 1-probability
        attempt, common, first, second, applied = bits
        fail1, fail2 = bool(common or first), bool(common or second)
        mass += weight
        m1 += weight*fail1
        m2 += weight*fail2
        joint += weight*(fail1 and fail2)
        failure = fail1 and (not applied or fail2)
        conditional += weight*failure
        escaped += weight*(attempt and failure)
    require(mass == 1, 'latent probability law normalizes')
    return (m1, m2, joint, m1*m2, conditional, escaped,
            escaped*risk['requests'], escaped*risk['requests']*F(risk['loss_per_escape']))


def certify(a, data, out, queues=False, journals=False):
    x = [r['staff'] for r in data['training']]
    y = [r['throughput'] for r in data['training']]
    rate = F(sum(s*t for s, t in zip(x, y)), sum(s*s for s in x))
    errors = [rate*s-t for s, t in zip(x, y)]
    cal = out['calibration']
    a.eq((F(cal['rate_per_staff_cutoff']), list(map(F, cal['training_errors'])),
          F(cal['sum_squared_error']), F(cal['max_absolute_error'])),
         (rate, errors, sum(e*e for e in errors), max(map(abs, errors))), 'independent least-squares arithmetic')
    a.eq(sum(s*e for s, e in zip(x, errors)), 0, 'least-squares residual orthogonality')
    staffing = [int(rate*s) for s in data['operation']['staff']]
    capacities = [min(s, g) for s, g in zip(staffing, data['operation']['gateway_capacity'])]
    deployed = staffing if data['operation']['deployed_rule'] == 'staff_only' else capacities
    a.eq(out['capacity'], dict(staff_only=staffing, constrained=capacities, deployed=deployed), 'fit versus process capacity')
    if queues:
        queue_certificate(a, data, out['constrained_plan'], capacities)
        queue_certificate(a, data, out['deployed_forecast'], deployed)
    if journals:
        ledger(a, data, out)
    risk = latent_risk(data['control_risk'])
    a.eq(tuple(F(out['separate_control_experiment'][k]) for k in (
        'first_control_marginal_miss', 'second_control_marginal_miss', 'joint_miss_when_both_applied',
        'incorrect_product_of_marginal_misses', 'escape_given_unauthorized_attempt', 'escape_per_request',
        'expected_escapes', 'expected_loss')), risk, '32-state truth table probabilities and loss')
    c, q1, q2 = (F(data['control_risk'][k]) for k in ('common_failure_probability', 'first_miss_given_no_common', 'second_miss_given_no_common'))
    a.eq(risk[2]-risk[3], c*(1-c)*(1-q1)*(1-q2), 'covariance factorization')
    policy = data['closure']; obs = out['observed_reconciliation']
    gates = {
        'training_error_within_stated_tolerance': max(map(abs, errors)) <= F(policy['maximum_fit_error']),
        'runtime_bottleneck_included': data['operation']['deployed_rule'] == 'bottleneck',
        'constrained_plan_meets_all_deadlines': out['constrained_plan']['all_deadlines_met'],
        'observed_instruction_identity_complete': not obs['anomalies'] and not obs['missing_instruction_ids'],
        'observed_all_authorized_payments_on_time': obs['on_time_count'] == len(data['payments']),
        'observed_records_within_stated_capacity': obs['within_stipulated_capacity'],
        'distinct_preparer_and_approver_declared': policy['preparer'] != policy['approver'],
        'independent_model_challenger_declared': policy['developer'] != policy['reviewer'],
        'reviewed_version_matches_deployment': policy['reviewed_version'] == policy['deployed_version'],
        'expected_loss_within_fictional_bound': risk[-1] <= F(policy['maximum_expected_loss']),
        'legal_basis_evidence_declared': policy['legal_basis_verified'],
        'restore_replay_external_evidence_declared': all(policy[k] for k in (
            'restore_evidence_verified', 'replay_evidence_verified', 'external_confirmation_verified')),
    }
    a.eq(out['closure_gates'], gates, 'twelve distinct closure tests')
    a.eq(out['failed_closure_gates'], [k for k, v in gates.items() if not v], 'complete failed-gate list')
    a.eq(out['disposition'], 'eligible_for_independent_closure_review' if all(gates.values()) else
         'keep_incident_open_or_restrict_use', 'all gates required, review eligibility only')


def financial_cases(a, run, base, initial):
    def test(data, queues=False, journals=False):
        result = a.call(run, data)
        certify(a, data, result, queues, journals)
        return result
    a.eq([r['backlog_after'] for r in initial['constrained_plan']['rows']], [2, 5, 4, 0], 'worked 1 and exercise 1 backlogs')
    a.eq(initial['constrained_plan']['deadline_missed_ids'], ['B05', 'C01', 'C02', 'C03'], 'four particular missed obligations')
    a.eq(sum(p['deadline'] <= 3 for p in base['payments']) - sum([2, 2, 4]), 4, 'cutoff 3 deficit is an independent lower bound')
    honest = changed(base, ['operation', 'deployed_rule'], 'bottleneck')
    out = test(honest, queues=True)
    a.eq(out['deployed_forecast']['on_time_count'], 10, 'mapping repair does not add resources')
    retimed = changed(honest, ['operation', 'gateway_capacity'], [2, 2, 8, 2])
    out = test(retimed, queues=True)
    a.eq((out['constrained_plan']['on_time_count'], out['observed_reconciliation']['within_stipulated_capacity']),
         (14, False), 'new reservation cannot retroactively fit old six-debit window 4')
    rehearsal = deepcopy(retimed)
    rehearsal['run_label'] = 'peer_new_rehearsal'
    groups = [(1, ['A01', 'A02']), (2, ['A03', 'A04']),
              (3, ['B01', 'B02', 'B03', 'B04', 'B05', 'C01', 'C02', 'C03']), (4, ['D01', 'D02'])]
    rehearsal['observed_settlements'] = [{'id': key, 'cutoff': t} for t, ids in groups for key in ids]
    rehearsal['control_risk'].update(common_failure_probability='0', second_control_coverage='1')
    rehearsal['closure'].update(legal_basis_verified=True, restore_evidence_verified=True,
                                replay_evidence_verified=True, external_confirmation_verified=True,
                                reviewed_version='capacity_v2', deployed_version='capacity_v2')
    good = test(rehearsal, queues=True, journals=True)
    a.eq(good['failed_closure_gates'], [], 'all-green declared rehearsal exists')
    for field, value, gate in (
        ('approver', rehearsal['closure']['preparer'], 'distinct_preparer_and_approver_declared'),
        ('reviewer', rehearsal['closure']['developer'], 'independent_model_challenger_declared'),
        ('deployed_version', 'unreviewed_v3', 'reviewed_version_matches_deployment'),
        ('legal_basis_verified', False, 'legal_basis_evidence_declared'),
        ('external_confirmation_verified', False, 'restore_replay_external_evidence_declared')):
        out = test(changed(rehearsal, ['closure', field], value))
        a.eq(out['failed_closure_gates'], [gate], 'one missing evidence item cannot be overridden')
    remove = deepcopy(base); del remove['observed_settlements'][11]
    replace = changed(base, ['observed_settlements', 11, 'id'], 'C03')
    for data, expected, counts in ((remove, (130, 130, 0, 70, 10, 60), (10, 3, ['C03'])),
                                   (replace, (140, 140, 0, 60, 0, 60), (10, 4, []))):
        out = test(data, journals=True)['observed_reconciliation']
        a.eq(tuple(F(out[k]) for k in ('cash_debits', 'authorized_liability_discharged', 'bank_borne_exception_loss',
                                      'closing_cash', 'closing_payment_liability', 'closing_equity')), expected, 'exercise 2 exact accounts')
        a.eq((out['on_time_count'], len(out['authorized_late_ids']), out['missing_instruction_ids']), counts, 'exercise 2 residual failures')
    anomaly = changed(base, ['observed_settlements', 1, 'id'], 'C03')
    anomaly['observed_settlements'][11]['id'] = 'C03'
    anomaly['observed_settlements'].append({'id': 'X99', 'cutoff': 4})
    out = test(anomaly, journals=True)['observed_reconciliation']
    a.eq((out['rows'][1]['classification'], out['rows'][11]['classification'], out['rows'][-1]['classification']),
         ('before_authorization', 'authorized_late', 'unknown_instruction'), 'premature does not discharge; later authorized does')
    a.eq(tuple(F(out[k]) for k in ('closing_cash', 'closing_payment_liability', 'closing_equity')), (50, 10, 40), 'premature and unknown debits consume equity')
    fractional = deepcopy(base)
    fractional.update(unit_amount='1/3', opening_cash='20/3', opening_payment_liability='14/3', opening_equity='2')
    out = test(fractional, journals=True)['observed_reconciliation']
    a.eq(tuple(F(out[k]) for k in ('closing_cash', 'closing_payment_liability', 'closing_equity')), (F(2), F(1, 3), F(5, 3)), 'exact currency scale transfer')
    recovery = deepcopy(rehearsal)
    recovery.update(horizon=2, opening_cash='40', opening_payment_liability='30', opening_equity='10',
                    payments=[{'id': 'E0'+str(i), 'release': 1, 'deadline': 2} for i in (1, 2, 3)])
    recovery['operation'] = dict(staff=[2, 2], gateway_capacity=[4, 4], deployed_rule='bottleneck')
    recovery['observed_settlements'] = [{'id': key, 'cutoff': t} for t, key in ((1, 'E01'), (1, 'E02'), (2, 'E02'), (2, 'E03'))]
    blind = test(recovery, journals=True)['observed_reconciliation']
    del recovery['observed_settlements'][2]
    safe = test(recovery, journals=True)['observed_reconciliation']
    a.eq(tuple(F(blind[k]) for k in ('closing_cash', 'closing_payment_liability', 'closing_equity')), (0, 0, 0), 'exercise 6 blind replay')
    a.eq(tuple(F(safe[k]) for k in ('closing_cash', 'closing_payment_liability', 'closing_equity')), (10, 0, 10), 'exercise 6 externally reconciled replay')
    noisy = changed(rehearsal, ['training', 1, 'throughput'], 5)
    out = test(noisy)
    a.eq((F(out['calibration']['rate_per_staff_cutoff']), F(out['calibration']['sum_squared_error'])), (F(44, 21), F(17, 21)), 'nonzero-fit transfer')
    a.eq(out['failed_closure_gates'], ['training_error_within_stated_tolerance'], 'zero tolerance is meaningful')
    out = test(changed(noisy, ['closure', 'maximum_fit_error'], '17/21'))
    a.eq(out['closure_gates']['training_error_within_stated_tolerance'], True, 'fit bound equality included')
    risk_cases = [
        ({'second_control_coverage': '1'}, F('34.5'), False),
        ({'second_control_coverage': '1', 'common_failure_probability': '1/49'}, F(20), True),
        ({'second_control_coverage': '1', 'common_failure_probability': '0.02040817'}, F('20.0000033'), False),
        ({'common_failure_probability': '0', 'second_control_coverage': '0.75'}, F(20), True),
        ({'common_failure_probability': '0', 'second_control_coverage': '0.74999999'}, F('20.0000004'), False),
        ({'common_failure_probability': '1', 'first_miss_given_no_common': '0', 'second_miss_given_no_common': '0'}, F(500), False),
        ({'common_failure_probability': '0', 'first_miss_given_no_common': '0'}, F(0), True),
        ({'common_failure_probability': '0', 'second_control_coverage': '1'}, F(10), True),
        ({'loss_per_escape': '0', 'requests': 1000000}, F(0), True),
    ]
    for change, expected, gate in risk_cases:
        data = deepcopy(base); data['control_risk'].update(change)
        out = test(data)
        a.eq((F(out['separate_control_experiment']['expected_loss']), out['closure_gates']['expected_loss_within_fictional_bound']),
             (expected, gate), 'risk floor, exact boundary or endpoint')
    a.eq(F(initial['separate_control_experiment']['expected_loss'])-F(good['separate_control_experiment']['expected_loss'])-12,
         F('20.1'), 'same-population redesign expected net benefit')


def small_schedules(a, run, base):
    cases = [
        ([(2, 2)], [1, 0], 0), ([(2, 2)], [0, 1], 1),
        ([(1, 1), (1, 2)], [0, 2], 1), ([(1, 2), (1, 2)], [1, 1], 2),
        ([(1, 1), (2, 2), (2, 2)], [0, 2], 2),
        ([(2, 3), (1, 3), (1, 3)], [1, 1, 1], 3),
        ([(1, 2), (1, 2)], [0, 0], 0),
        ([(1, 1)]*3 + [(2, 2)]*2, [2, 3], 4),
    ]
    for i, (dates, capacities, optimum) in enumerate(cases):
        data = deepcopy(base)
        n = len(dates)
        data.update(horizon=len(capacities), payments=[{'id': 'J'+str(j), 'release': r, 'deadline': d} for j, (r, d) in enumerate(dates)],
                    opening_cash=str(n*10), opening_payment_liability=str(n*10), opening_equity='0', observed_settlements=[])
        data['operation'] = dict(staff=[3]*len(capacities), gateway_capacity=capacities, deployed_rule='bottleneck')
        out = a.call(run, data); certify(a, data, out, queues=True, journals=True)
        maximum = timely_subset_oracle(data['payments'], capacities)
        a.eq(maximum, optimum, 'independent timely subset optimum')
        a.eq(out['constrained_plan']['all_deadlines_met'], maximum == n, 'EDF feasibility against all timely subsets')
        a.truth(out['constrained_plan']['on_time_count'] <= maximum, 'timely reported set is feasible')
        if i == 4:
            a.eq(out['constrained_plan']['on_time_count'], 1, 'retaining overdue work need not maximize timely count')
        if i == 7:
            a.eq([r['backlog_after'] for r in out['constrained_plan']['rows']], [1, 0], 'retention backlog answer')
        a.small_schedule_cases += 1
    a.eq(latent_risk(dict(base['control_risk'], common_failure_probability='0.1', first_miss_given_no_common='0.1',
                         second_miss_given_no_common='0.1'))[2:4], (F('0.109'), F('0.0361')), 'retention dependence answer')


def invalid_data(a, run, base):
    changes = [
        (['schema'], 'other'), (['run_label'], 'contains space'), (['horizon'], True), (['horizon'], 13),
        (['unit_amount'], 10), (['unit_amount'], '0'), (['unit_amount'], '1e1'), (['unit_amount'], '01'),
        (['unit_amount'], '1/0'), (['unit_amount'], '1/-2'), (['unit_amount'], '0.000000001'),
        (['opening_cash'], '199'), (['opening_payment_liability'], '130'),
        (['payments'], []), (['payments', 1, 'id'], 'A01'), (['payments', 0, 'release'], 3),
        (['payments', 0, 'deadline'], False), (['training'], [{'staff': 0, 'throughput': 1}]*2),
        (['training', 0, 'throughput'], 501), (['operation', 'staff'], [1]),
        (['operation', 'gateway_capacity', 0], -1), (['operation', 'deployed_rule'], 'other'),
        (['operation', 'staff', 0], 1.0), (['observed_settlements', 0, 'cutoff'], 4),
        (['control_risk', 'requests'], True), (['control_risk', 'requests'], 1000001),
        (['control_risk', 'common_failure_probability'], '1.00000001'),
        (['control_risk', 'loss_per_escape'], '-1'), (['closure', 'legal_basis_verified'], 1),
        (['closure', 'maximum_fit_error'], 'NaN'),
    ]
    cases = [changed(base, path, value) for path, value in changes]
    extra = deepcopy(base); extra['extra'] = 1; cases.append(extra)
    missing = deepcopy(base); del missing['closure']; cases.append(missing)
    extra = deepcopy(base); extra['payments'][0]['amount'] = '10'; cases.append(extra)
    debt = deepcopy(base); debt.update(opening_cash='130', opening_equity='-10'); cases.append(debt)
    overdraw = deepcopy(base); overdraw['observed_settlements'] += [{'id': 'X99', 'cutoff': 4}]*7; cases.append(overdraw)
    for data in cases:
        before = deepcopy(data); stream = StringIO()
        with redirect_stdout(stream), redirect_stderr(stream):
            try:
                run(data)
            except ValueError:
                a.api_rejections += 1
            else:
                raise ValueError('invalid API contract accepted')
        a.eq(stream.getvalue(), '', 'invalid API is quiet')
        a.eq(data, before, 'invalid API preserves input')


class Chapter(HTMLParser):
    def __init__(self):
        super().__init__(); self.stack=[]; self.ids=[]; self.hrefs=[]; self.sources=[]
        self.worked=0; self.prompts=[]; self.answers=[]; self.capture=None; self.depth=0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs); classes=attrs.get('class', '').split()
        if 'id' in attrs: self.ids.append(attrs['id'])
        if 'href' in attrs: self.hrefs.append(attrs['href'])
        if 'data-source' in attrs: self.sources.append(attrs['data-source'])
        if tag == 'aside' and 'worked' in classes: self.worked += 1
        if tag == 'li' and self.capture is None:
            if any(t == 'ol' and 'exercises' in c for t, c in self.stack):
                self.capture = ('prompt', []); self.depth = len(self.stack)
            elif any(t == 'details' and 'solutions' in c for t, c in self.stack):
                self.capture = ('answer', []); self.depth = len(self.stack)
        if tag not in ('area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'):
            self.stack.append((tag, classes))

    def handle_data(self, data):
        if self.capture is not None: self.capture[1].append(data)

    def handle_endtag(self, tag):
        require(bool(self.stack) and self.stack[-1][0] == tag, 'balanced chapter markup')
        self.stack.pop()
        if tag == 'li' and self.capture is not None and len(self.stack) == self.depth:
            kind, chunks = self.capture
            (self.prompts if kind == 'prompt' else self.answers).append(' '.join(''.join(chunks).split()))
            self.capture = None


def binding_and_structure(a):
    review = strict(REVIEW.read_text())
    expected = set(AUTHOR_FILES) | {'scripts/check_v11_c06_peer.py'}
    a.eq({r['path'] for r in review['reviewed_hashes']}, expected, 'exact nine author files plus peer checker')
    a.eq(len(review['reviewed_hashes']), 10, 'no duplicate binding')
    for record in review['reviewed_hashes']:
        payload = (ROOT / record['path']).read_bytes()
        a.eq((len(payload), sha256(payload).hexdigest()), (record['bytes'], record['sha256']), 'bound bytes ' + record['path'])
    author = strict((ROOT / 'content/reviews/v11-c06-author.json').read_text())
    a.eq({r['path'] for r in author['reviewed_hashes']}, set(AUTHOR_FILES)-{'content/reviews/v11-c06-author.json'}, 'author eight nonself bindings')
    a.eq(len(author['reviewed_hashes']), 8, 'no duplicate author binding')
    for record in author['reviewed_hashes']:
        payload = (ROOT / record['path']).read_bytes()
        a.eq((len(payload), sha256(payload).hexdigest()), (record['bytes'], record['sha256']), 'author binding agrees with frozen bytes')
    manifest = strict((PROJECT / 'v11-c06-manifest.json').read_text())
    wanted = {'v11-c06'+s for s in ('-inputs.json', '-analysis.py', '-output.json', '-README.txt')}
    a.eq({r['file'] for r in manifest['files']}, wanted, 'exact four portable manifest members')
    a.eq(len(manifest['files']), 4, 'manifest uniqueness')
    for record in manifest['files']:
        payload = (PROJECT / record['file']).read_bytes()
        a.eq((len(payload), sha256(payload).hexdigest()), (record['bytes'], record['sha256']), 'manifest byte integrity')
    chapter = Chapter(); chapter.feed((ROOT / AUTHOR_FILES[0]).read_text()); chapter.close()
    a.eq(chapter.stack, [], 'closed chapter fragment')
    a.eq(len(chapter.ids), len(set(chapter.ids)), 'unique reader IDs')
    a.eq((chapter.worked, len(chapter.prompts), len(chapter.answers)), (4, 8, 8), 'four worked and eight matched ordered solutions')
    a.eq({s for s in chapter.sources}, {'v11-c06-bcbs-resilience2021', 'v10-c12-fed-letter', 'v10-c12-fed-guidance'}, 'scoped citation IDs')
    a.eq({h for h in chapter.hrefs if h.startswith('v11-c06-')}, wanted | {'v11-c06-manifest.json'}, 'flat reader attachment links')
    a.truth(not any(h.startswith('projects/') for h in chapter.hrefs), 'no nonexistent reader projects directory')
    a.eq(len(review['exact_prompt_solution_audit']), 8, 'all exact prompts independently reviewed')
    for item, prompt, answer in zip(review['exact_prompt_solution_audit'], chapter.prompts, chapter.answers):
        a.eq((item['prompt_sha256'], item['solution_sha256']),
             (sha256(prompt.encode()).hexdigest(), sha256(answer.encode()).hexdigest()), 'bound prompt and full solution text')


def portable(a, base, expected):
    with tempfile.TemporaryDirectory(prefix='c06-separate-peer-') as folder:
        folder = Path(folder); model = folder / MODEL.name; source = folder / INPUT.name
        shutil.copy2(MODEL, model); shutil.copy2(INPUT, source)
        original = (model.read_bytes(), source.read_bytes())
        for optimized in (False, True):
            python = [sys.executable, '-I'] + (['-O'] if optimized else [])
            def invoke(args):
                return subprocess.run(python+[str(model)]+args, cwd='/', capture_output=True, text=True, timeout=20)
            result = invoke([])
            a.eq((result.returncode, result.stderr), (0, ''), 'isolated portable default CLI')
            a.eq(strict(result.stdout), expected, 'default sibling input from unrelated cwd'); a.portable_successes += 1
            target = folder / 'result.json'
            result = invoke(['--input', str(source), '--output', str(target)])
            a.eq((result.returncode, result.stdout, result.stderr), (0, '', ''), 'explicit input/output success is quiet')
            a.eq(strict(target.read_text()), expected, 'portable full saved result'); a.portable_successes += 1
            api = ('import contextlib,io,json,runpy,sys; b=io.StringIO(); '
                   '\nwith contextlib.redirect_stdout(b),contextlib.redirect_stderr(b):\n'
                   ' m=runpy.run_path(sys.argv[1]); d=json.load(open(sys.argv[2])); before=json.dumps(d,sort_keys=True); r=m["run"](d)\n'
                   'if b.getvalue() or json.dumps(d,sort_keys=True)!=before: raise ValueError("API contract")\n'
                   'print(json.dumps(r,allow_nan=False))')
            result = subprocess.run(python+['-c', api, str(model), str(source)], cwd='/', capture_output=True, text=True, timeout=20)
            a.eq((result.returncode, result.stderr), (0, ''), 'isolated API import and call quiet in both modes')
            a.eq(strict(result.stdout), expected, 'isolated API same full output'); a.portable_successes += 1
            for protected in (source, model):
                for kind in ('direct', 'symlink', 'hardlink'):
                    alias = protected if kind == 'direct' else folder / ('alias-'+protected.name)
                    if kind == 'symlink': alias.symlink_to(protected)
                    if kind == 'hardlink': os.link(protected, alias)
                    result = invoke(['--input', str(source), '--output', str(alias)])
                    a.truth(result.returncode != 0 and result.stdout == '' and result.stderr.startswith('error:'), 'protected alias rejected '+kind)
                    a.eq((model.read_bytes(), source.read_bytes()), original, 'protected bytes preserved')
                    a.alias_rejections += 1
                    if kind != 'direct': alias.unlink()
            malformed = ['{"schema":1,"schema":2}', json.dumps(base).replace('"opening_cash": "200"', '"opening_cash": NaN'),
                         json.dumps(changed(base, ['horizon'], True)), ' '*1000001]
            for text in malformed:
                bad = folder / 'bad.json'; bad.write_text(text)
                target.write_text('DO NOT REPLACE\n')
                result = invoke(['--input', str(bad), '--output', str(target)])
                a.truth(result.returncode != 0 and result.stdout == '' and result.stderr.startswith('error:'), 'strict/domain CLI rejects before output')
                a.eq(target.read_text(), 'DO NOT REPLACE\n', 'rejected input preserves existing output')
                a.cli_rejections += 1


def check():
    a = Audit(); stream = StringIO()
    with redirect_stdout(stream), redirect_stderr(stream):
        namespace = runpy.run_path(str(MODEL))
    a.eq(stream.getvalue(), '', 'quiet candidate import')
    base = strict(INPUT.read_text()); run = namespace['run']
    initial = a.call(run, base); certify(a, base, initial, queues=True, journals=True)
    a.eq(initial, strict((PROJECT / 'v11-c06-output.json').read_text()), 'reproduction after independent checks')
    financial_cases(a, run, base, initial)
    small_schedules(a, run, base)
    invalid_data(a, run, base)
    portable(a, base, initial)
    binding_and_structure(a)
    summary = dict(chapter='v11-c06', status='peer-check-passed', **vars(a), worked_examples=4, solved_exercises=8,
                   methods=['feasible timely subsets for eight small dated schedules', '32-state control-risk truth table',
                            'instruction-level journal and release/deadline certificates', 'exact least-squares and boundary arithmetic'],
                   limits='Synthetic bounded machine-assisted peer audit, not real control effectiveness, legal advice, actual closure or human certification.')
    json.dumps(summary, allow_nan=False)
    return summary


if __name__ == '__main__':
    print(json.dumps(check(), indent=2, allow_nan=False))
