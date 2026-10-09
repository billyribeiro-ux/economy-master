"""Portlight author checks from independent original-contract cash formulas.

Only public run(data) and the model CLI are executed. Expected payments are
calculated by two-date resource formulas; an independent transaction table then
reconstructs every reported close and selected journal. Exact tail evidence uses
threshold minimization, not the model's tail-filling implementation. No asserts,
outside dependencies, stochastic fuzzing or shared-library files are required.
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
MODEL = PROJECT / 'v11-assessment-analysis.py'
INPUT = PROJECT / 'v11-assessment-inputs.json'
OWNED = (
    'content/assessments/parts/v11-project.html',
    'content/projects/v11-assessment-inputs.json',
    'content/projects/v11-assessment-analysis.py',
    'content/projects/v11-assessment-output.json',
    'content/projects/v11-assessment-manifest.json',
    'content/projects/v11-assessment-README.txt',
    'scripts/check_v11_project.py',
    'content/reviews/v11-project-author.json',
    'content/reviews/v11-project-sources.json',
)


def require(ok, message):
    if not ok:
        raise ValueError('Portlight independent check: ' + message)


def strict(text):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    def nonfinite(value):
        raise ValueError('nonfinite JSON constant: ' + value)
    return json.loads(text, object_pairs_hook=unique, parse_constant=nonfinite)


def encode(value):
    if isinstance(value, F): return str(value)
    if type(value) is dict: return {k: encode(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)): return [encode(v) for v in value]
    return value


class Audit:
    def __init__(self):
        self.comparisons = self.policies = self.scenarios = self.journal_rows = 0
        self.cases = self.anchors = self.invalid_api = self.invalid_cli = self.aliases = self.portable = 0

    def eq(self, actual, expected, label):
        self.comparisons += 1
        require(type(actual) is type(expected) and actual == expected,
                label + ': ' + repr(actual)[:250] + ' != ' + repr(expected)[:250])

    def yes(self, condition, label):
        self.eq(bool(condition), True, label)

    def tree(self, actual, expected, label):
        if isinstance(expected, F):
            self.eq(actual, str(expected), label)
        elif type(expected) is dict:
            self.yes(type(actual) is dict, label + ' object')
            self.eq(set(actual), set(expected), label + ' keys')
            for key in expected: self.tree(actual[key], expected[key], label + '.' + key)
        elif type(expected) is list:
            self.yes(type(actual) is list, label + ' list')
            self.eq(len(actual), len(expected), label + ' length')
            for j, v in enumerate(expected): self.tree(actual[j], v, label + '[' + str(j) + ']')
        else:
            self.eq(actual, expected, label)

    def call(self, run, data):
        copy = deepcopy(data)
        stream = StringIO()
        with redirect_stdout(stream), redirect_stderr(stream): result = run(data)
        self.eq(stream.getvalue(), '', 'quiet run(data)')
        self.eq(data, copy, 'input preserved')
        self.eq(strict(json.dumps(result, allow_nan=False)), result, 'strict JSON result')
        return result

    def anchor(self, actual, printed, label):
        self.eq(F(actual), F(printed), 'printed exact anchor: ' + label)
        self.anchors += 1


def change(data, path, value):
    out = deepcopy(data)
    ref = out
    for key in path[:-1]: ref = ref[key]
    ref[path[-1]] = value
    return out


def oracle(data, policy, s, price=None):
    """Closed-form resource envelopes first; independent posting table second."""
    b, f, z = policy
    B = {k: F(v) for k, v in data['bank'].items()}
    D = {k: F(v) for k, v in data['first_due'].items()}
    C = {k: F(v) for k, v in data['endowments'].items()}
    e0, e = F(data['initial_spot']), F(s['spot'])
    q = F(1) / (1 + F(s['bond_yield'])) ** 2 if price is None else price
    h, rate = F(s['haircut']), F(data['facility']['interest'])
    reserve, minimum_equity = F(data['limits']['home_reserve']), F(data['limits']['bank_equity'])
    collateral = F(s['collateral_gross']) - F(s['collateral_cost']) - F(s['collateral_prior_claim'])
    r1, r2 = F(s['borrower_cash_first']), F(s['borrower_cash_final']) + collateral
    rf = F(s['foreign_recovery'])
    lossH, lossF = B['domestic_loan_face'] - r1 - r2, B['foreign_claim_face'] - rf
    H0 = B['home_cash'] + b - e0 * f
    F0 = B['foreign_cash'] + (f if s['prefund_timely'] else 0)
    transit = F(0) if s['prefund_timely'] else f
    bought = min(max(F(0), D['foreign_deposits'] - F0), F(s['early_fx_cap']), H0 / e)
    paidF1 = min(D['foreign_deposits'], F0 + bought)
    F1 = F0 + bought - paidF1
    foreign_remaining = B['foreign_deposits'] - paidF1
    H_before_loan = H0 - e * bought + r1
    request = max(F(0), reserve + D['households'] + B['pension_deposit'] - H_before_loan)
    capacity = min(C['lender_home_cash'], F(data['facility']['eligible_bond_units']) * q * (1 - h))
    g = min(capacity, request)
    available1 = H_before_loan + g
    hh1 = min(D['households'], available1)
    pp1 = min(B['pension_deposit'], available1 - hh1)
    H1 = available1 - hh1 - pp1
    hh_remaining, pp_remaining = B['household_deposits'] - hh1, B['pension_deposit'] - pp1
    benefit1 = min(F(data['pension']['benefits']), F(data['pension']['cash']) + z + pp1)
    pension1 = F(data['pension']['cash']) + z + pp1 - benefit1
    benefits_remaining = F(data['pension']['benefits']) - benefit1
    foreign_available = F1 + transit + rf
    paidF2 = min(foreign_available, foreign_remaining)
    foreign_before_sale = foreign_available - paidF2
    H_before_sale = H1 + B['bill'] + r2
    loan_due = (1 + rate) * g
    H_needed = max(F(0), reserve + loan_due + hh_remaining + pp_remaining - H_before_sale)
    sold = min(foreign_before_sale, F(s['late_fx_cap']), H_needed / e)
    available2 = H_before_sale + e * sold
    lender_paid = min(available2, loan_due)
    hh2 = min(available2 - lender_paid, hh_remaining)
    pp2 = min(available2 - lender_paid - hh2, pp_remaining)
    H2 = available2 - lender_paid - hh2 - pp2
    F2 = foreign_before_sale - sold
    benefit2 = min(pension1 + pp2, benefits_remaining)
    pension2 = pension1 + pp2 - benefit2
    initial_equity = (B['home_cash'] + B['bill'] + B['long_bond_units'] + B['domestic_loan_face']
                      + e0 * (B['foreign_cash'] + B['foreign_claim_face'] - B['foreign_deposits'])
                      - B['household_deposits'] - B['pension_deposit'])
    final_equity = (H2 + e * F2 + B['long_bond_units'] * q
                    - (hh_remaining - hh2) - (pp_remaining - pp2)
                    - e * (foreign_remaining - paidF2) - (loan_due - lender_paid))
    # Expected bank transfers use the closed-form paid quantities above, never
    # amounts or changes supplied by the implementation under test.
    rowspec = [
        ('opening', 'reference inventory and separate endowed cash', {}),
        ('before_early', 'received funded equity subscription', {'home_cash': b}),
        ('before_early', 'sponsor paid separate pension contribution', {}),
        ('before_early', 'paid for prefunding; record actual foreign delivery status', {'home_cash': -e0 * f, 'foreign_cash' if s['prefund_timely'] else 'foreign_in_transit': f}),
        ('before_early', 'recognize FX, long-bond and loan impairment once', {'long_bonds': B['long_bond_units'] * (q - 1), 'domestic_loan': -lossH, 'foreign_claim': -lossF}),
        ('early_09', 'delivered limited early H-to-F conversion', {'home_cash': -e * bought, 'foreign_cash': bought}),
        ('early_09', 'paid early foreign deposit claim from foreign cash', {'foreign_cash': -paidF1, 'foreign_deposits': -paidF1}),
        ('early_10', 'received borrower first principal cash', {'home_cash': r1, 'domestic_loan': -r1}),
        ('early_10', 'received funded secured advance against separate long bonds', {'home_cash': g, 'secured_claim': g}),
        ('early_10', 'paid priority household withdrawals', {'home_cash': -hh1, 'household_deposits': -hh1}),
        ('early_10', 'paid pension withdrawal with remaining actual home cash', {'home_cash': -pp1, 'pension_deposit': -pp1}),
        ('early_1015', 'pension paid due benefits; retain any missed claim', {}),
        ('final_17', 'received previously paid in-transit prefunding', {'foreign_cash': transit, 'foreign_in_transit': -transit}),
        ('final_17', 'received actual foreign claim recovery', {'foreign_cash': rf, 'foreign_claim': -rf}),
        ('final_17', 'paid remaining foreign deposits including any early arrears', {'foreign_cash': -paidF2, 'foreign_deposits': -paidF2}),
        ('final_18', 'maturing bill paid from its separately funded promise', {'home_cash': B['bill'], 'bill': -B['bill']}),
        ('final_18', 'received borrower final operating and net collateral cash', {'home_cash': r2, 'domestic_loan': -r2}),
        ('final_18', 'accrued secured interest as an expense and payable claim', {'secured_claim': rate * g}),
        ('final_18', 'received limited late F-to-H conversion before home payments', {'foreign_cash': -sold, 'home_cash': e * sold}),
        ('final_18', 'paid senior secured claim; release collateral only if fully repaid', {'home_cash': -lender_paid, 'secured_claim': -lender_paid}),
        ('final_18', 'paid remaining household claims before pension arrears', {'home_cash': -hh2, 'household_deposits': -hh2}),
        ('final_18', 'paid remaining pension bank claim', {'home_cash': -pp2, 'pension_deposit': -pp2}),
        ('final_1815', 'pension paid retained benefit arrears when cash actually arrived', {}),
    ]
    opening = dict(home_cash=B['home_cash'], foreign_cash=B['foreign_cash'], foreign_in_transit=F(0),
                   bill=B['bill'], long_bonds=B['long_bond_units'], domestic_loan=B['domestic_loan_face'],
                   foreign_claim=B['foreign_claim_face'], household_deposits=B['household_deposits'],
                   pension_deposit=B['pension_deposit'], foreign_deposits=B['foreign_deposits'], secured_claim=F(0))
    rows = []
    # Cumulative columns provide a second reconciliation of all event positions.
    for j, (time, event, changes) in enumerate(rowspec):
        state = {key: amount + sum(spec[2].get(key, F(0)) for spec in rowspec[:j + 1])
                 for key, amount in opening.items()}
        spot = e0 if j < 4 else e
        assets = state['home_cash'] + state['bill'] + state['long_bonds'] + state['domestic_loan'] + spot * (state['foreign_cash'] + state['foreign_in_transit'] + state['foreign_claim'])
        liabilities = state['household_deposits'] + state['pension_deposit'] + state['secured_claim'] + spot * state['foreign_deposits']
        p_cash = F(data['pension']['cash']) + (z if j >= 2 else 0) + (pp1 if j >= 10 else 0) - (benefit1 if j >= 11 else 0) + (pp2 if j >= 21 else 0) - (benefit2 if j >= 22 else 0)
        p_owed = F(data['pension']['benefits']) - (benefit1 if j >= 11 else 0) - (benefit2 if j >= 22 else 0)
        pledge = g / (q * (1 - h)) if j >= 8 and not (j >= 19 and lender_paid == loan_due) else F(0)
        rows.append(dict(time=time, event=event, changes=changes, bank=state, valuation_spot=spot,
                         balance=dict(assets_H=assets, liabilities_H=liabilities, equity_H=assets - liabilities),
                         pledged_units=pledge, pension_cash=p_cash, pension_benefits_unpaid=p_owed,
                         pension_net_assets_at_bank_claim_face=p_cash + state['pension_deposit'] - p_owed,
                         sponsor_cash=C['sponsor_home_cash'] - (b if j >= 1 else 0) - (z if j >= 2 else 0),
                         lender_cash=C['lender_home_cash'] - (g if j >= 8 else 0) + (lender_paid if j >= 19 else 0),
                         dealer_home_cash=C['dealer_home_cash'] + (e0 * f if j >= 3 else 0) + (e * bought if j >= 5 else 0) - (e * sold if j >= 18 else 0),
                         dealer_foreign_cash=C['dealer_foreign_cash'] - (f if j >= 3 else 0) - (bought if j >= 5 else 0) + (sold if j >= 18 else 0)))
    early_misses = dict(foreign_F=D['foreign_deposits'] - paidF1, households_H=D['households'] - hh1,
                        pension_bank_claim_H=B['pension_deposit'] - pp1, pension_benefits_H=benefits_remaining)
    final_misses = dict(foreign_F=foreign_remaining - paidF2, households_H=hh_remaining - hh2,
                        pension_bank_claim_H=pp_remaining - pp2, pension_benefits_H=benefits_remaining - benefit2,
                        secured_H=loan_due - lender_paid)
    good_time = all(v == 0 for v in list(early_misses.values()) + list(final_misses.values()))
    good_cash = H1 >= reserve and H2 >= reserve
    good_equity = rows[10]['balance']['equity_H'] >= minimum_equity and final_equity >= minimum_equity
    result = dict(scenario=s['id'], bond_price=q,
                  borrower=dict(primary_cash_first=r1, primary_cash_final=F(s['borrower_cash_final']),
                                collateral_net_to_bank=collateral, actual_final_receipt=r2,
                                collateral_allocation=dict(buyer_cash_before_H=C['collateral_buyer_home_cash'], buyer_paid_H=F(s['collateral_gross']),
                                                           buyer_cash_after_H=C['collateral_buyer_home_cash'] - F(s['collateral_gross']),
                                                           liquidation_cost_H=F(s['collateral_cost']), prior_creditor_H=F(s['collateral_prior_claim']), bank_recovery_H=collateral),
                                first_service_ratio=r1 / D['borrower_principal'],
                                final_operating_service_ratio=F(s['borrower_cash_final']) / (B['domestic_loan_face'] - D['borrower_principal']),
                                first_nominal_arrears=D['borrower_principal'] - r1, terminal_nominal_unpaid=lossH,
                                recognized_credit_loss=lossH, terminal_carrying_asset=F(0)),
                  foreign_issuer_nominal_unpaid_F=lossF, early_conversion_F=bought, late_conversion_F=sold,
                  requested_secured_H=request, secured_capacity_H=capacity, secured_draw_H=g,
                  pledged_units_initial=g / (q * (1 - h)), secured_interest_H=rate * g,
                  early_shortfalls=early_misses, final_shortfalls=final_misses,
                  early_foreign_close=rows[6], early_home_close=rows[10], early_pension_close=rows[11],
                  final_home_close=rows[21], final_network_close=rows[22],
                  equity_bridge=dict(reference_equity_H=initial_equity, received_equity_H=b,
                                     fx_mark_H=(B['foreign_cash'] + f + B['foreign_claim_face'] - B['foreign_deposits']) * (e - e0),
                                     bond_mark_H=B['long_bond_units'] * (q - 1), domestic_credit_loss_H=lossH,
                                     foreign_credit_loss_H=e * lossF, interest_expense_H=rate * g,
                                     closing_equity_H=final_equity, capital_flow_adjusted_loss_H=initial_equity + b - final_equity),
                  external_funding=dict(sponsor_cash_committed_H=b + z, sponsor_cash_remaining_H=C['sponsor_home_cash'] - b - z,
                                        new_investor_equity_fraction=b / (initial_equity + b),
                                        new_investor_closing_marked_stake_H=b * max(F(0), final_equity) / (initial_equity + b),
                                        lender_cash_remaining_H=C['lender_home_cash'] - g + lender_paid, lender_claim_H=loan_due - lender_paid,
                                        dealer_home_cash=C['dealer_home_cash'] + e0 * f + e * bought - e * sold,
                                        dealer_foreign_cash=C['dealer_foreign_cash'] - f - bought + sold),
                  gates=dict(bank_and_pension_obligations_timely=good_time, home_reserve_met=good_cash, bank_equity_floor_met=good_equity),
                  feasible=good_time and good_cash and good_equity)
    require(rows[21]['bank']['home_cash'] == H2 and rows[21]['bank']['foreign_cash'] == F2
            and rows[21]['balance']['equity_H'] == final_equity and rows[22]['pension_cash'] == pension2,
            'independent cumulative and resource formulas disagree')
    return result, rows


def verify_financial(a, data, result):
    names = ('bank_equity_H', 'prefund_F', 'pension_contribution_H')
    choices = sorted(product(*(map(F, data['choices'][k]) for k in ('bank_equity', 'prefund_foreign', 'pension_contribution'))))
    a.eq(result['candidate_count'], len(choices), 'complete policy count')
    a.eq(len(result['candidates']), len(choices), 'complete candidate rows')
    accepted, oracle_rows = [], {}
    for policy, actual in zip(choices, result['candidates']):
        b, f, z = policy
        expected = [oracle(data, policy, s)[0] for s in data['scenarios']]
        valid = all(row['feasible'] for row in expected)
        a.tree(actual, dict(policy=dict(zip(names, policy)), outside_cash_commitment_H=b + z,
                            feasible=valid, scenarios=expected), 'candidate ' + str(policy))
        oracle_rows[policy] = expected
        if valid: accepted.append(((b + z, f, b, z), policy))
        a.policies += 1
        a.scenarios += len(expected)
    accepted.sort()
    a.eq(result['feasible_count'], len(accepted), 'independently feasible policies')
    if accepted:
        policy = accepted[0][1]
        expected = []
        for s in data['scenarios']:
            row, journal = oracle(data, policy, s)
            row['journal'] = journal
            for event in journal:
                a.yes(all(v >= 0 for v in event['bank'].values()), 'no negative executed position')
                a.yes(all(event[k] >= 0 for k in ('pension_cash', 'sponsor_cash', 'lender_cash', 'dealer_home_cash', 'dealer_foreign_cash')), 'funded counterparty cash')
                a.yes(0 <= event['pledged_units'] <= F(data['facility']['eligible_bond_units']), 'distinct eligible collateral')
                a.journal_rows += 1
            expected.append(row)
        a.tree(result['selected'], dict(policy=dict(zip(names, policy)), outside_cash_commitment_H=policy[0] + policy[2], scenarios=expected), 'selected policy and all actual journals')
        verify_risk(a, data, expected, result['selected_loss_measure'])
        verify_reverse(a, data, policy, result['reverse_stress'])
    else:
        for field in ('selected', 'selected_loss_measure', 'reverse_stress'):
            a.eq(result[field], None, 'no feasible plan: ' + field)
    a.cases += 1
    return oracle_rows


def verify_risk(a, data, rows, report):
    losses = [(row['equity_bridge']['capital_flow_adjusted_loss_H'], F(s['probability']))
              for row, s in zip(rows, data['scenarios'])]
    alpha = F(data['risk_alpha'])
    thresholds = sorted(set(loss for loss, _ in losses))
    # A finite convex piecewise-linear objective attains its minimum at a knot.
    es = min(t + sum(p * max(F(0), loss - t) for loss, p in losses) / (1 - alpha) for t in thresholds)
    quantile = next(t for t in thresholds if sum(p for loss, p in losses if loss <= t) >= alpha)
    a.tree(report['alpha'], alpha, 'tail alpha')
    a.tree(report['expected_loss_H'], sum(loss * p for loss, p in losses), 'weighted physical mean')
    a.tree(report['var_H'], quantile, 'lower quantile through CDF')
    a.tree(report['expected_shortfall_H'], es, 'ES via independent threshold minimization')
    allocation = report['tail_allocation']
    a.eq(sum(F(r['probability_used']) for r in allocation), 1 - alpha, 'exact tail mass')
    a.eq(sum(F(r['probability_used']) * F(r['loss_H']) for r in allocation) / (1 - alpha), es, 'tail dual value')
    for t in thresholds:
        used = sum(F(r['probability_used']) for r in allocation if F(r['loss_H']) == t)
        a.yes(0 <= used <= sum(p for loss, p in losses if loss == t), 'valid fractional tail atom')


def verify_reverse(a, data, policy, report):
    s = next(s for s in data['scenarios'] if s['id'] == data['reverse_scenario'])
    reference, _ = oracle(data, policy, s)
    g = reference['requested_secured_H']
    units = F(data['bank']['long_bond_units'])
    capacity_coefficient = F(data['facility']['eligible_bond_units']) * (1 - F(s['haircut']))
    c_floor = g / capacity_coefficient if g else F(0)
    # On the feasible-draw region, taking the original q mark out of E_final
    # leaves its non-bond component; collect the required residual equity.
    no_bond = reference['equity_bridge']['closing_equity_H'] - units * reference['bond_price']
    e_floor = max(F(0), (F(data['limits']['bank_equity']) - no_bond) / units)
    critical = max(c_floor, e_floor)
    a.tree(report['collateral_price_floor'], c_floor, 'reverse collateral inequality')
    a.tree(report['equity_price_floor'], e_floor, 'reverse equity inequality')
    a.tree(report['binding_price_floor'], critical, 'reverse intersection')
    inside = F(1, 25) <= critical <= 1
    a.eq(report['boundary_within_supported_yield_0_to_4'], inside, 'reverse supported domain')
    if inside:
        boundary, _ = oracle(data, policy, s, critical)
        a.eq(report['equality_feasible'], boundary['feasible'], 'actual equality case')
        a.tree(report['boundary_final_equity_H'], boundary['equity_bridge']['closing_equity_H'], 'boundary account identity')
        low, high = map(F, report['yield_boundary_bracket'])
        a.yes(0 <= low <= high <= 4 and high - low <= F(1, 10**12), 'bounded rational root bracket')
        a.yes(1 / (1 + low)**2 >= critical >= 1 / (1 + high)**2, 'root bracket justified by monotonicity')
        if critical > F(1, 25):
            below, _ = oracle(data, policy, s, critical - min(F(1, 10**6), (critical - F(1, 25)) / 2))
            a.eq(below['feasible'], False, 'strictly beyond first boundary fails')
    else:
        a.eq(report['yield_boundary_bracket'], None, 'no unsupported yield bracket')
        a.eq(report['equality_feasible'], None, 'no unsupported equality claim')


def cases(base):
    items = [('baseline', deepcopy(base))]
    items.append(('delayed', change(base, ('scenarios', 2, 'prefund_timely'), False)))
    late = change(base, ('scenarios', 2, 'late_fx_cap'), '1')
    items.append(('late_cap1', late))
    items.append(('late_cap1_grid22', change(late, ('choices', 'bank_equity'), ['0', '10', '20', '22'])))
    items.append(('late_cap1_exact', change(late, ('choices',), dict(bank_equity=['148/7'], prefund_foreign=['10'], pension_contribution=['2']))))
    benefit = change(base, ('pension', 'benefits'), '17')
    items.append(('benefits17', benefit))
    items.append(('benefits17_grant4', change(benefit, ('choices', 'pension_contribution'), ['0', '2', '4'])))
    eligible = change(base, ('facility', 'eligible_bond_units'), '10')
    items.append(('eligible10', eligible))
    items.append(('eligible10_exact', change(eligible, ('choices',), dict(bank_equity=['62/3'], prefund_foreign=['10'], pension_contribution=['2']))))
    items.append(('prior9', change(base, ('scenarios', 2, 'collateral_prior_claim'), '9')))
    items.append(('late_cap0', change(base, ('scenarios', 2, 'late_fx_cap'), '0')))
    items.append(('zero_interest', change(base, ('facility', 'interest'), '0')))
    flat = deepcopy(base)
    flat['scenarios'] = [flat['scenarios'][0]]
    flat['scenarios'][0]['probability'] = '1'
    flat['reverse_scenario'] = 'normal'
    flat['limits']['bank_equity'] = '0'
    flat['choices'] = dict(bank_equity=['20'], prefund_foreign=['10'], pension_contribution=['2'])
    items.append(('no_positive_reverse_boundary', flat))
    unpaid = deepcopy(base)
    unpaid['bank']['bill'] = '0'
    unpaid['choices'] = dict(bank_equity=['20'], prefund_foreign=['10'], pension_contribution=['2'])
    unpaid['scenarios'] = [unpaid['scenarios'][2]]
    unpaid['scenarios'][0].update(probability='1', borrower_cash_final='0', collateral_gross='0', collateral_cost='0', collateral_prior_claim='0', late_fx_cap='0')
    items.append(('unpaid_secured_claim', unpaid))
    return items


def printed_anchors(a, base, reports, expected, html):
    fixed = (F(20), F(10), F(2))
    baseline = expected['baseline'][fixed]
    normal, credit, joint = baseline
    initial, events = oracle(base, fixed, base['scenarios'][2])
    for actual, printed, label in (
        (events[0]['balance']['assets_H'], '172', 'opening assets'),
        (events[0]['balance']['liabilities_H'], '140', 'opening deposits'),
        (events[0]['balance']['equity_H'], '32', 'opening equity'),
        (events[0]['pension_net_assets_at_bank_claim_face'], '-2', 'pension funding deficit'),
        (events[3]['bank']['home_cash'], '20', 'funded initial H'),
        (events[3]['bank']['foreign_cash'], '16', 'delivered initial F'),
        (events[3]['sponsor_cash'], '8', 'remaining sponsor cash'),
        (events[3]['pension_cash'], '3', 'funded pension cash'),
        (joint['external_funding']['new_investor_equity_fraction'], '5/13', 'new investor fraction'),
        (1 - joint['external_funding']['new_investor_equity_fraction'], '8/13', 'old investor fraction'),
        (joint['external_funding']['new_investor_closing_marked_stake_H'], '1246/117', 'new investor joint stake'),
        (joint['secured_draw_H'], '4', 'joint actual loan'),
        (joint['secured_capacity_H'], '20/3', 'joint loan capacity'),
        (joint['pledged_units_initial'], '12', 'joint distinct pledge'),
        (joint['early_foreign_close']['bank']['foreign_cash'], '1', 'F after early payment'),
        (joint['early_home_close']['bank']['home_cash'], '2', 'first home cash'),
        (joint['early_home_close']['balance']['equity_H'], '251/9', 'first home equity'),
        (events[14]['bank']['foreign_cash'], '7', 'F before repatriation'),
        (events[17]['bank']['home_cash'], '62', 'H before final conversion'),
        (events[17]['bank']['secured_claim'], '4.2', 'accrued secured claim'),
        (joint['late_conversion_F'], '7/5', 'required final conversion'),
        (joint['final_home_close']['bank']['foreign_cash'], '28/5', 'final foreign cash'),
        (joint['final_home_close']['bank']['home_cash'], '2', 'final home cash'),
        (joint['final_home_close']['bank']['long_bonds'], '80/9', 'retained bond mark'),
        (joint['equity_bridge']['closing_equity_H'], '1246/45', 'final equity'),
        (joint['secured_interest_H'], '1/5', 'interest only once'),
        (F(15) - 6, '9', 'required original F prefunding'),
        (F(15) - 1 - 12, '2', 'required pension contribution'),
        (F(24) - F(20, 3), '52/3', 'first home capital-cash necessity'),
        (F(20) + 2, '22', 'outside commitment'),
    ):
        a.anchor(actual, printed, label)
    for row, service1, service2, net, final_receipt, first_arrears, last_arrears, fx_arrears in zip(
        baseline, ['1', '3/5', '2/5'], ['1', '4/5', '7/10'], ['0', '10', '12'],
        ['40', '42', '40'], ['0', '8', '12'], ['0', '6', '12'], ['0', '2', '4']):
        borrower = row['borrower']
        for field, printed in [('first_service_ratio', service1), ('final_operating_service_ratio', service2),
                               ('collateral_net_to_bank', net), ('actual_final_receipt', final_receipt),
                               ('first_nominal_arrears', first_arrears), ('terminal_nominal_unpaid', last_arrears)]:
            a.anchor(borrower[field], printed, row['scenario'] + ' ' + field)
        a.anchor(row['foreign_issuer_nominal_unpaid_F'], fx_arrears, 'offshore unpaid face')
        alloc = borrower['collateral_allocation']
        a.eq(alloc['buyer_paid_H'], alloc['liquidation_cost_H'] + alloc['prior_creditor_H'] + alloc['bank_recovery_H'], 'collateral allocation conserves actual proceeds')
    for row, c1, c2, foreign, e1, e2, loss in zip(
        baseline, ['10', '2', '2'], ['10', '4', '2'], ['11', '9', '28/5'],
        ['52', '393/10', '251/9'], ['52', '393/10', '1246/45'], ['0', '127/10', '1094/45']):
        for actual, printed, label in (
            (row['early_home_close']['bank']['home_cash'], c1, 'early cash'),
            (row['final_home_close']['bank']['home_cash'], c2, 'late cash'),
            (row['final_home_close']['bank']['foreign_cash'], foreign, 'late F'),
            (row['early_home_close']['balance']['equity_H'], e1, 'early equity'),
            (row['equity_bridge']['closing_equity_H'], e2, 'final equity'),
            (row['equity_bridge']['capital_flow_adjusted_loss_H'], loss, 'capital-adjusted loss')):
            a.anchor(actual, printed, row['scenario'] + ' ' + label)
    poor = expected['baseline'][(F(10), F(10), F(2))][2]
    for actual, printed, label in (
        (poor['early_home_close']['pension_cash'] - 3, '20/3', 'weak policy pension receipt'),
        (poor['early_pension_close']['pension_benefits_unpaid'], '16/3', 'weak policy on-time benefit gap'),
        (poor['early_home_close']['bank']['home_cash'], '0', 'no protected reserve in failed execution'),
        (poor['late_conversion_F'], '43/9', 'late cure conversion'),
        (poor['equity_bridge']['closing_equity_H'], '158/9', 'weak policy final capital')):
        a.anchor(actual, printed, label)
    a.eq(poor['final_shortfalls'], dict(foreign_F=F(0), households_H=F(0), pension_bank_claim_H=F(0), pension_benefits_H=F(0), secured_H=F(0)), 'late cure does not erase original miss')
    risk = reports['baseline']['selected_loss_measure']
    for field, printed in [('expected_loss_H', '2237/270'), ('var_H', '127/10'), ('expected_shortfall_H', '5519/270')]:
        a.anchor(risk[field], printed, 'physical ' + field)
    a.anchor(F('1/4') - F('1/6'), '1/12', 'fraction of the credit atom')
    reverse = reports['baseline']['reverse_stress']
    for field, printed in [('collateral_price_floor', '4/15'), ('equity_price_floor', '3/50'), ('boundary_final_equity_H', '362/15')]:
        a.anchor(reverse[field], printed, 'reverse ' + field)
    a.anchor((F(30) - 28) / 15, '2/15', 'creditor-payment boundary differs from reserve')
    # All six transfer prompts, including the explicit off-model change in rights.
    def row(case, policy=fixed): return expected[case][policy][2]
    delayed = row('delayed')
    a.anchor(delayed['early_shortfalls']['foreign_F'], '9', 'delayed prefund early F gap')
    a.anchor(delayed['equity_bridge']['closing_equity_H'], '1246/45', 'delayed delivery terminal wealth')
    cap = row('late_cap1')
    a.anchor(cap['final_home_close']['bank']['home_cash'], '4/5', 'late cap1 reserve cash')
    a.anchor(2 - cap['final_home_close']['bank']['home_cash'], '6/5', 'late cap1 reserve deficit')
    a.anchor(F('6/5') / (1 + F('1/20')), '8/7', 'least extra funded equity for late cap')
    exact = row('late_cap1_exact', (F(148, 7), F(10), F(2)))
    for value, printed in [(exact['secured_draw_H'], '20/7'), (exact['late_conversion_F'], '1'), (exact['equity_bridge']['closing_equity_H'], '260/9')]:
        a.anchor(value, printed, 'exact late-cap remedy')
    grid = row('late_cap1_grid22', (F(22), F(10), F(2)))
    for value, printed in [(grid['secured_draw_H'], '2'), (grid['late_conversion_F'], '7/10'), (grid['equity_bridge']['closing_equity_H'], '2681/90')]:
        a.anchor(value, printed, 'finite late-cap remedy')
    a.anchor(row('benefits17')['early_shortfalls']['pension_benefits_H'], '2', 'new pension deficit')
    benefits = row('benefits17_grant4', (F(20), F(10), F(4)))
    a.anchor(benefits['external_funding']['sponsor_cash_committed_H'], '24', 'new funded benefit promise')
    a.anchor(benefits['external_funding']['sponsor_cash_remaining_H'], '6', 'sponsor remaining after grant4')
    eligible = row('eligible10')
    a.anchor(eligible['secured_capacity_H'], '10/3', 'changed collateral capacity')
    a.anchor(eligible['early_home_close']['bank']['home_cash'], '4/3', 'collateral change first cash')
    a.anchor(2 - eligible['early_home_close']['bank']['home_cash'], '2/3', 'least added equity for collateral')
    repaired = row('eligible10_exact', (F(62, 3), F(10), F(2)))
    for value, printed in [(repaired['secured_draw_H'], '10/3'), (repaired['late_conversion_F'], '7/6'), (repaired['equity_bridge']['closing_equity_H'], '511/18')]:
        a.anchor(value, printed, 'exact collateral remedy')
    prior = row('prior9')
    for value, printed in [(prior['borrower']['collateral_net_to_bank'], '6'), (prior['borrower']['actual_final_receipt'], '34'),
                           (prior['borrower']['terminal_nominal_unpaid'], '18'), (prior['late_conversion_F'], '17/5'),
                           (prior['final_home_close']['bank']['foreign_cash'], '18/5'), (prior['equity_bridge']['closing_equity_H'], '976/45')]:
        a.anchor(value, printed, 'changed senior recovery')
    a.anchor(reports['prior9']['reverse_stress']['binding_price_floor'], '9/25', 'capital now first')
    a.anchor(1 / (1 + F(2, 3))**2, '9/25', 'new exact yield boundary')
    a.anchor(15 * F(9, 25), '27/5', 'excess collateral at capital boundary')
    a.anchor(F(1) + 2 + (12 - 10), '5', 'conversion does not create benefit cash')
    a.anchor(F(15) - 5, '10', 'converted-deposit benefit gap')
    a.anchor(F(30) - 20 - 2, '8', 'insufficient unused sponsor cash for fixed plan')
    a.eq(reports['baseline']['feasible_count'], 1, 'unique original policy')
    for case in ('delayed', 'late_cap1', 'benefits17', 'eligible10', 'late_cap0', 'unpaid_secured_claim'):
        a.eq(reports[case]['selected'], None, 'explicit original-menu refusal ' + case)
    unpaid = expected['unpaid_secured_claim'][fixed][0]
    a.anchor(unpaid['final_shortfalls']['secured_H'], '11/5', 'retained accrued secured claim')
    a.anchor(unpaid['final_home_close']['pledged_units'], '12', 'no release before full secured repayment')
    a.anchor(unpaid['external_funding']['new_investor_closing_marked_stake_H'], '0', 'limited-liability investor stake floor')
    for literal in ('1246/45', '251/9', '5519/270', '2237/270', '1094/45', '362/15', '43/9', '158/9',
                    '148/7', '20/7', '260/9', '2681/90', '62/3', '511/18', '976/45', '1246/117'):
        a.yes(literal in html, 'instructor exact fraction is present: ' + literal)


class ProjectHTML(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids, self.hrefs, self.sources, self.rubric = [], [], set(), []
        self.h1 = 0
    def handle_starttag(self, tag, attrs):
        attr = dict(attrs)
        if 'id' in attr: self.ids.append(attr['id'])
        if tag == 'h1': self.h1 += 1
        if tag == 'a':
            self.hrefs.append(attr.get('href', ''))
            if 'data-source' in attr: self.sources.add(attr['data-source'])
        if tag == 'tr' and 'data-points' in attr:
            self.rubric.append((attr.get('data-domain'), int(attr['data-points'])))


def structure_and_bindings(a, verify_bindings):
    html = (ROOT / OWNED[0]).read_text()
    parser = ProjectHTML(); parser.feed(html); parser.close()
    a.eq(parser.h1, 0, 'fragment has no extra h1')
    a.eq(len(parser.ids), len(set(parser.ids)), 'all project IDs unique')
    a.yes('project' in parser.ids and 'v11-project-guide' in parser.ids, 'project and complete guide anchors')
    a.yes(all(x == 'project' or x.startswith('v11-project-') for x in parser.ids), 'owned ID namespace')
    for j in range(1, 7):
        a.yes('v11-project-task-' + str(j) in parser.ids, 'complete deliverable prompt')
        a.yes('v11-project-transfer-' + str(j) in parser.ids, 'complete unfamiliar transfer')
    a.eq(parser.rubric, [('D' + str(j), 20) for j in range(1, 6)], 'five essential domains totaling 100')
    for j in range(1, 13): a.yes('v11-c' + str(j).zfill(2) + '.html' in parser.hrefs, 'all twelve chapter outcomes linked')
    for suffix in ('inputs.json', 'analysis.py', 'output.json', 'manifest.json', 'README.txt'):
        a.yes('v11-assessment-' + suffix in parser.hrefs, 'flat downloadable project asset')
    sources = strict((ROOT / OWNED[8]).read_text())
    a.eq(parser.sources, {row['id'] for row in sources['reuse']}, 'exact scoped reused source set')
    a.eq(sources['proposals'], [], 'no unsupported new source proposal')
    if verify_bindings:
        manifest = strict((PROJECT / 'v11-assessment-manifest.json').read_text())
        paths = {'v11-assessment-' + s for s in ('inputs.json', 'analysis.py', 'output.json', 'README.txt')}
        a.eq(len(manifest['files']), 4, 'four manifest payloads')
        a.eq({row['file'] for row in manifest['files']}, paths, 'exact manifest membership')
        for row in manifest['files']:
            body = (PROJECT / row['file']).read_bytes()
            a.eq((len(body), sha256(body).hexdigest()), (row['bytes'], row['sha256']), 'manifest bytes and SHA256')
        author = strict((ROOT / 'content/reviews/v11-project-author.json').read_text())
        hashes = author['reviewed_hashes']
        a.eq(len(hashes), 8, 'author eight nonself payloads')
        a.eq({row['path'] for row in hashes}, set(OWNED) - {'content/reviews/v11-project-author.json'}, 'exact nonself set')
        for row in hashes:
            body = (ROOT / row['path']).read_bytes()
            a.eq((len(body), sha256(body).hexdigest()), (row['bytes'], row['sha256']), 'author bound bytes and SHA256')
    return html


def reject_inputs(a, run, base):
    mutations = [
        (('schema',), True), (('schema',), 2), (('extra',), 0), (('provenance',), ''),
        (('initial_spot',), 2.0), (('initial_spot',), True), (('initial_spot',), 'NaN'),
        (('initial_spot',), '2e0'), (('initial_spot',), '2/0'), (('initial_spot',), '0'),
        (('bank', 'long_bond_units'), '0'), (('bank', 'domestic_loan_face'), '0'),
        (('bank', 'household_deposits'), '1000'), (('bank', 'home_cash'), '-1'),
        (('first_due', 'households'), '79'), (('first_due', 'borrower_principal'), '0'),
        (('choices', 'bank_equity'), ['0', '0/2']), (('choices', 'bank_equity'), []),
        (('choices', 'bank_equity'), ['0', '1', '2', '3', '4']),
        (('choices', 'prefund_foreign'), ['11']), (('endowments', 'sponsor_home_cash'), '21'),
        (('endowments', 'dealer_foreign_cash'), '29'), (('endowments', 'dealer_home_cash'), '39'),
        (('endowments', 'collateral_buyer_home_cash'), '17'),
        (('facility', 'eligible_bond_units'), '21'), (('facility', 'interest'), '-1/20'),
        (('facility', 'interest'), '2'), (('risk_alpha',), '0'), (('risk_alpha',), '1'),
        (('reverse_scenario',), 'missing'), (('scenarios',), []), (('scenarios', 1, 'id'), 'normal'),
        (('scenarios', 2, 'probability'), '1/5'), (('scenarios', 2, 'prefund_timely'), 1),
        (('scenarios', 2, 'haircut'), '1'), (('scenarios', 2, 'bond_yield'), '5'),
        (('scenarios', 2, 'foreign_recovery'), '21'), (('scenarios', 2, 'borrower_cash_first'), '21'),
        (('scenarios', 2, 'borrower_cash_final'), '61'), (('scenarios', 2, 'collateral_prior_claim'), '16'),
    ]
    bad = [change(base, path, value) for path, value in mutations] + [None, [], change(base, ('bank',), [])]
    for data in bad:
        copy, stream = deepcopy(data), StringIO()
        try:
            with redirect_stdout(stream), redirect_stderr(stream): run(data)
        except ValueError:
            pass
        else:
            raise ValueError('invalid API contract accepted')
        a.eq(data, copy, 'invalid input unmodified')
        a.eq(stream.getvalue(), '', 'invalid API quiet')
        a.invalid_api += 1


def invoke(args):
    return subprocess.run(args, cwd='/', capture_output=True, text=True, timeout=55)


def cli_checks(a, base, expected):
    with tempfile.TemporaryDirectory(prefix='v11-project-cli-') as tmp:
        folder = Path(tmp)
        model, source = folder / MODEL.name, folder / INPUT.name
        model.write_bytes(MODEL.read_bytes()); source.write_bytes(INPUT.read_bytes())
        output = folder / 'result.json'
        default = folder / 'v11-assessment-output.json'
        invalid = ['{"schema":1,"schema":1}', '{"x":NaN}', '{"x":Infinity}', '{"x":-Infinity}', '{', '[]',
                   json.dumps(change(base, ('scenarios', 2, 'prefund_timely'), 1)), ' ' * 65537]
        for option in ([], ['-O']):
            command = [sys.executable] + option + [str(model)]
            for extra, destination in (([], default), (['--input', str(source), '--output', str(output)], output)):
                result = invoke(command + extra)
                a.eq((result.returncode, result.stdout, result.stderr), (0, '', ''), 'quiet portable default/explicit model')
                a.eq(destination.read_bytes(), expected, 'canonical portable output')
                a.portable += 1
            for text in invalid:
                bad = folder / 'invalid.json'; bad.write_text(text)
                output.write_text('preserve existing output\n')
                result = invoke(command + ['--input', str(bad), '--output', str(output)])
                a.eq(result.returncode, 2, 'invalid CLI explicit failure')
                a.eq(result.stdout, '', 'invalid CLI no stdout')
                a.yes(bool(result.stderr) and 'Traceback' not in result.stderr, 'invalid CLI concise error')
                a.eq(output.read_text(), 'preserve existing output\n', 'invalid input preserves existing destination')
                a.invalid_cli += 1
            (folder / 'nested').mkdir(exist_ok=True)
            aliases = []
            for protected in (source, model):
                aliases += [protected, folder / 'nested' / '..' / protected.name]
                sym, hard = folder / ('sym-' + protected.name), folder / ('hard-' + protected.name)
                if sym.is_symlink(): sym.unlink()
                if hard.exists(): hard.unlink()
                sym.symlink_to(protected); os.link(protected, hard)
                aliases += [sym, hard]
            before = (source.read_bytes(), model.read_bytes())
            for destination in aliases:
                result = invoke(command + ['--input', str(source), '--output', str(destination)])
                a.eq(result.returncode, 2, 'direct/resolved/symlink/hardlink protected')
                a.eq(result.stdout, '', 'protected alias no stdout')
                a.yes(bool(result.stderr) and 'Traceback' not in result.stderr, 'explicit alias failure')
                a.eq((source.read_bytes(), model.read_bytes()), before, 'protected original bytes unchanged')
                a.aliases += 1
            for protected in (source, model):
                default.unlink(); default.symlink_to(protected)
                result = invoke(command)
                a.eq(result.returncode, 2, 'default alias protected')
                a.eq(result.stdout, '', 'default alias no stdout')
                a.eq((source.read_bytes(), model.read_bytes()), before, 'default protected bytes unchanged')
                a.aliases += 1
            default.unlink()


def isolated(a):
    with tempfile.TemporaryDirectory(prefix='v11-project-isolated-') as tmp:
        root = Path(tmp)
        for relative in OWNED:
            destination = root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, destination)
        a.eq(sum(1 for p in root.rglob('*') if p.is_file()), 9, 'isolated nine-file package')
        program = ("import contextlib,io,json,runpy; s=io.StringIO(); "
                   "m=runpy.run_path(" + repr(str(root / 'scripts/check_v11_project.py')) + "); "
                   "\nwith contextlib.redirect_stdout(s),contextlib.redirect_stderr(s): r=m['check'](portable=False)"
                   "\nif s.getvalue(): raise ValueError('nonquiet check API')"
                   "\nprint(json.dumps(r,sort_keys=True,allow_nan=False))")
        results = []
        for option in ([], ['-O']):
            response = invoke([sys.executable] + option + ['-c', program])
            a.eq(response.returncode, 0, 'isolated checker normal/optimized exit')
            a.eq(response.stderr, '', 'isolated checker stderr')
            result = strict(response.stdout)
            a.eq(result['status'], 'passed', 'isolated package passes')
            results.append(result); a.portable += 1
        a.eq(results[0], results[1], 'isolated normal/optimized equal evidence')


def check(portable=True, verify_bindings=True):
    a = Audit()
    html = structure_and_bindings(a, verify_bindings)
    base = strict(INPUT.read_text())
    stream = StringIO()
    with redirect_stdout(stream), redirect_stderr(stream): run = runpy.run_path(str(MODEL))['run']
    a.eq(stream.getvalue(), '', 'quiet import')
    reports, expected = {}, {}
    for name, data in cases(base):
        report = a.call(run, data)
        reports[name] = report
        expected[name] = verify_financial(a, data, report)
    printed_anchors(a, base, reports, expected, html)
    saved = strict((PROJECT / 'v11-assessment-output.json').read_text())
    a.eq(saved, reports['baseline'], 'saved baseline equals independently audited fresh output')
    body = (json.dumps(reports['baseline'], indent=2, sort_keys=True) + '\n').encode()
    a.eq((PROJECT / 'v11-assessment-output.json').read_bytes(), body, 'canonical output bytes')
    original = a.call(run, base)
    unchanged = deepcopy(original)
    original['selected']['policy']['bank_equity_H'] = 'changed returned object'
    a.eq(a.call(run, base), unchanged, 'no shared output state')
    reject_inputs(a, run, base)
    cli_checks(a, base, body)
    if portable:
        require(verify_bindings, 'portable evidence requires final author bindings')
        isolated(a)
    return dict(project='v11-project', status='passed', comparisons=a.comparisons,
                financial_cases=a.cases, candidate_policies=a.policies, scenario_cases=a.scenarios,
                selected_journal_rows=a.journal_rows, exact_printed_anchors=a.anchors,
                transfer_tasks=6, essential_domains=5, rubric_points=100,
                invalid_api_cases=a.invalid_api, invalid_cli_cases=a.invalid_cli,
                protected_alias_attempts=a.aliases, portable_runs=a.portable,
                author_nonself_bindings=8 if verify_bindings else 0,
                limits='Original finite contract and scoped numerical evidence; separate peer/coordinator acceptance, actual external funding/authority and visual QA remain distinct.')


if __name__ == '__main__':
    print(json.dumps(check(), sort_keys=True, allow_nan=False))
