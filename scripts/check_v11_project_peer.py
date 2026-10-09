"""Independent, bounded Portlight peer checks; quiet check() and portable CLI.

The financial oracle uses cumulative creditor-priority tranches and dated
resource identities derived from the assigned contract. It never calls an
author checker or private model helper. All 18 original policies, the selected
69 journal rows, six transfers and focused failure boundaries are checked.
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
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / 'content/projects'
MODEL = PROJECT / 'v11-assessment-analysis.py'
INPUT = PROJECT / 'v11-assessment-inputs.json'
PEER = 'content/reviews/v11-project-peer.json'
SELF = 'scripts/check_v11_project_peer.py'
AUTHOR = (
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
NAMES = ('bank_equity_H', 'prefund_F', 'pension_contribution_H')
CHOICES = ('bank_equity', 'prefund_foreign', 'pension_contribution')
ZERO = F(0)


def require(ok, message):
    if not ok:
        raise ValueError('Portlight peer: ' + message)


def encode(value):
    if isinstance(value, F):
        return str(value)
    if type(value) is dict:
        return {key: encode(v) for key, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [encode(v) for v in value]
    return value


def strict(body):
    def pairs(items):
        out = {}
        for key, value in items:
            require(key not in out, 'duplicate JSON key')
            out[key] = value
        return out
    def bad(value):
        raise ValueError('nonfinite JSON constant ' + value)
    return json.loads(body, object_pairs_hook=pairs, parse_constant=bad)


class Audit:
    def __init__(self):
        self.comparisons = self.policy_states = self.journal_rows = 0
        self.interventions = self.invalid_api = self.invalid_cli = 0
        self.aliases = self.portable_model_runs = 0

    def eq(self, actual, expected, label):
        self.comparisons += 1
        actual, wanted = encode(actual), encode(expected)
        require(type(actual) is type(wanted) and actual == wanted,
                label + ': ' + repr(actual)[:250] + ' != ' + repr(wanted)[:250])

    def yes(self, condition, label):
        self.eq(bool(condition), True, label)

    def run(self, function, data):
        before, stream = deepcopy(data), StringIO()
        with redirect_stdout(stream), redirect_stderr(stream):
            output = function(data)
        self.eq(stream.getvalue(), '', 'quiet public run')
        self.eq(data, before, 'input not mutated')
        self.eq(strict(json.dumps(output, allow_nan=False)), output, 'strict JSON-safe output')
        return output


def amended(base, path, value):
    data = deepcopy(base)
    node = data
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value
    return data


def singleton(base, policy=(F(20), F(10), F(2))):
    data = deepcopy(base)
    data['choices'] = {name: [str(value)] for name, value in zip(CHOICES, policy)}
    return data


def tranches(cash, claims):
    """Priority claimant i receives its interval intersected with [0,cash]."""
    prefix, amounts = ZERO, []
    for claim in claims:
        amounts.append(max(ZERO, min(cash, prefix + claim) - prefix))
        prefix += claim
    return amounts, max(ZERO, cash - prefix)


def oracle(data, policy, s, quote=None):
    """Expected transfers and positions from independent resource envelopes."""
    b, f, z = policy
    B = {k: F(v) for k, v in data['bank'].items()}
    D = {k: F(v) for k, v in data['first_due'].items()}
    end = {k: F(v) for k, v in data['endowments'].items()}
    e0, e = F(data['initial_spot']), F(s['spot'])
    q = (1 + F(s['bond_yield'])) ** -2 if quote is None else quote
    r, floor = F(data['facility']['interest']), F(data['limits']['home_reserve'])
    unit_advance = q * (1 - F(s['haircut']))
    pledgeable = F(data['facility']['eligible_bond_units'])
    p_cash, p_due = F(data['pension']['cash']), F(data['pension']['benefits'])
    recovery = F(s['collateral_gross']) - F(s['collateral_cost']) - F(s['collateral_prior_claim'])
    borrower1, borrower2 = F(s['borrower_cash_first']), F(s['borrower_cash_final']) + recovery
    foreign_receipt = F(s['foreign_recovery'])
    loan_loss = B['domestic_loan_face'] - borrower1 - borrower2
    foreign_loss = B['foreign_claim_face'] - foreign_receipt
    available_H = B['home_cash'] + b - e0 * f
    delivered = f if s['prefund_timely'] else ZERO
    transit = f - delivered
    buy = min(max(ZERO, D['foreign_deposits'] - B['foreign_cash'] - delivered),
              F(s['early_fx_cap']), available_H / e)
    (foreign1,), F1 = tranches(B['foreign_cash'] + delivered + buy, [D['foreign_deposits']])
    H_before_draw = available_H - e * buy + borrower1
    request = max(ZERO, floor + D['households'] + B['pension_deposit'] - H_before_draw)
    capacity = min(end['lender_home_cash'], pledgeable * unit_advance)
    draw = min(request, capacity)
    (household1, pension1), H1 = tranches(H_before_draw + draw, [D['households'], B['pension_deposit']])
    (benefit1,), pension_cash1 = tranches(p_cash + z + pension1, [p_due])
    (foreign2,), F_before_sale = tranches(F1 + transit + foreign_receipt, [B['foreign_deposits'] - foreign1])
    final_claims = [(1 + r) * draw, B['household_deposits'] - household1, B['pension_deposit'] - pension1]
    late_H = H1 + B['bill'] + borrower2
    sell = min(F_before_sale, F(s['late_fx_cap']), max(ZERO, sum(final_claims) + floor - late_H) / e)
    (secured2, household2, pension2), H2 = tranches(late_H + e * sell, final_claims)
    (benefit2,), pension_cash2 = tranches(pension_cash1 + pension2, [p_due - benefit1])
    rem_F = B['foreign_deposits'] - foreign1 - foreign2
    rem_H = B['household_deposits'] - household1 - household2
    rem_P = B['pension_deposit'] - pension1 - pension2
    rem_S = (1 + r) * draw - secured2
    rem_B = p_due - benefit1 - benefit2
    E0 = (B['home_cash'] + B['bill'] + B['long_bond_units'] + B['domestic_loan_face']
          + e0 * (B['foreign_cash'] + B['foreign_claim_face'] - B['foreign_deposits'])
          - B['household_deposits'] - B['pension_deposit'])
    fx_mark = (B['foreign_cash'] + f + B['foreign_claim_face'] - B['foreign_deposits']) * (e - e0)
    E1 = E0 + b + fx_mark + B['long_bond_units'] * (q - 1) - loan_loss - e * foreign_loss
    # This terminal residual uses no capital bridge: every collected asset and
    # actually extinguished claim is removed, and every unpaid claim survives.
    E2 = H2 + e * (F_before_sale - sell) + B['long_bond_units'] * q - rem_H - rem_P - rem_S - e * rem_F
    require(E2 == E1 - r * draw, 'independent residual/bridge disagreement')
    early = dict(foreign_F=D['foreign_deposits'] - foreign1,
                 households_H=D['households'] - household1,
                 pension_bank_claim_H=B['pension_deposit'] - pension1,
                 pension_benefits_H=p_due - benefit1)
    final = dict(foreign_F=rem_F, households_H=rem_H, pension_bank_claim_H=rem_P,
                 pension_benefits_H=rem_B, secured_H=rem_S)
    gates = dict(bank_and_pension_obligations_timely=not any(list(early.values()) + list(final.values())),
                 home_reserve_met=min(H1, H2) >= floor,
                 bank_equity_floor_met=min(E1, E2) >= F(data['limits']['bank_equity']))
    bridge = dict(reference_equity_H=E0, received_equity_H=b, fx_mark_H=fx_mark,
                  bond_mark_H=B['long_bond_units'] * (q - 1), domestic_credit_loss_H=loan_loss,
                  foreign_credit_loss_H=e * foreign_loss, interest_expense_H=r * draw,
                  closing_equity_H=E2, capital_flow_adjusted_loss_H=E0 + b - E2)
    credit = dict(primary_cash_first=borrower1, primary_cash_final=F(s['borrower_cash_final']),
                  collateral_net_to_bank=recovery, actual_final_receipt=borrower2,
                  first_service_ratio=borrower1 / D['borrower_principal'],
                  final_operating_service_ratio=F(s['borrower_cash_final']) / (B['domestic_loan_face'] - D['borrower_principal']),
                  first_nominal_arrears=D['borrower_principal'] - borrower1,
                  terminal_nominal_unpaid=loan_loss, recognized_credit_loss=loan_loss,
                  terminal_carrying_asset=ZERO,
                  collateral_allocation=dict(buyer_cash_before_H=end['collateral_buyer_home_cash'],
                    buyer_paid_H=F(s['collateral_gross']), buyer_cash_after_H=end['collateral_buyer_home_cash'] - F(s['collateral_gross']),
                    liquidation_cost_H=F(s['collateral_cost']), prior_creditor_H=F(s['collateral_prior_claim']), bank_recovery_H=recovery))
    funding = dict(sponsor_cash_committed_H=b + z, sponsor_cash_remaining_H=end['sponsor_home_cash'] - b - z,
                   new_investor_equity_fraction=b / (E0 + b),
                   new_investor_closing_marked_stake_H=b * max(ZERO, E2) / (E0 + b),
                   lender_cash_remaining_H=end['lender_home_cash'] - draw + secured2, lender_claim_H=rem_S,
                   dealer_home_cash=end['dealer_home_cash'] + e0 * f + e * (buy - sell),
                   dealer_foreign_cash=end['dealer_foreign_cash'] - f - buy + sell)
    # Separate contractual event columns, determined above, reconstruct every
    # selected journal and each reported candidate close without its deltas.
    moves = [
        {}, {'home_cash': b}, {},
        {'home_cash': -e0 * f, 'foreign_cash' if s['prefund_timely'] else 'foreign_in_transit': f},
        {'long_bonds': B['long_bond_units'] * (q - 1), 'domestic_loan': -loan_loss, 'foreign_claim': -foreign_loss},
        {'home_cash': -e * buy, 'foreign_cash': buy},
        {'foreign_cash': -foreign1, 'foreign_deposits': -foreign1},
        {'home_cash': borrower1, 'domestic_loan': -borrower1},
        {'home_cash': draw, 'secured_claim': draw},
        {'home_cash': -household1, 'household_deposits': -household1},
        {'home_cash': -pension1, 'pension_deposit': -pension1}, {},
        {'foreign_cash': transit, 'foreign_in_transit': -transit},
        {'foreign_cash': foreign_receipt, 'foreign_claim': -foreign_receipt},
        {'foreign_cash': -foreign2, 'foreign_deposits': -foreign2},
        {'home_cash': B['bill'], 'bill': -B['bill']},
        {'home_cash': borrower2, 'domestic_loan': -borrower2},
        {'secured_claim': r * draw},
        {'home_cash': e * sell, 'foreign_cash': -sell},
        {'home_cash': -secured2, 'secured_claim': -secured2},
        {'home_cash': -household2, 'household_deposits': -household2},
        {'home_cash': -pension2, 'pension_deposit': -pension2}, {},
    ]
    state = dict(home_cash=B['home_cash'], foreign_cash=B['foreign_cash'], foreign_in_transit=ZERO,
                 bill=B['bill'], long_bonds=B['long_bond_units'], domestic_loan=B['domestic_loan_face'],
                 foreign_claim=B['foreign_claim_face'], household_deposits=B['household_deposits'],
                 pension_deposit=B['pension_deposit'], foreign_deposits=B['foreign_deposits'], secured_claim=ZERO)
    clocks = ['opening'] + ['before_early'] * 4 + ['early_09'] * 2 + ['early_10'] * 4 + ['early_1015'] + ['final_17'] * 3 + ['final_18'] * 7 + ['final_1815']
    snapshots = []
    for i, (time, move) in enumerate(zip(clocks, moves)):
        for key, value in move.items():
            state[key] += value
        spot = e0 if i < 4 else e
        assets = (state['home_cash'] + state['bill'] + state['long_bonds'] + state['domestic_loan']
                  + spot * (state['foreign_cash'] + state['foreign_claim'] + state['foreign_in_transit']))
        liabilities = state['household_deposits'] + state['pension_deposit'] + state['secured_claim'] + spot * state['foreign_deposits']
        pc = p_cash + (z if i >= 2 else ZERO) + (pension1 if i >= 10 else ZERO) - (benefit1 if i >= 11 else ZERO) + (pension2 if i >= 21 else ZERO) - (benefit2 if i >= 22 else ZERO)
        pb = p_due - (benefit1 if i >= 11 else ZERO) - (benefit2 if i >= 22 else ZERO)
        snapshots.append(dict(time=time, changes=move, bank=dict(state), valuation_spot=spot,
            balance=dict(assets_H=assets, liabilities_H=liabilities, equity_H=assets - liabilities),
            pledged_units=(draw / unit_advance if i >= 8 and (i < 19 or rem_S > 0) else ZERO),
            pension_cash=pc, pension_benefits_unpaid=pb,
            pension_net_assets_at_bank_claim_face=pc + state['pension_deposit'] - pb,
            sponsor_cash=end['sponsor_home_cash'] - (b if i >= 1 else ZERO) - (z if i >= 2 else ZERO),
            lender_cash=end['lender_home_cash'] - (draw if i >= 8 else ZERO) + (secured2 if i >= 19 else ZERO),
            dealer_home_cash=end['dealer_home_cash'] + (e0 * f if i >= 3 else ZERO) + (e * buy if i >= 5 else ZERO) - (e * sell if i >= 18 else ZERO),
            dealer_foreign_cash=end['dealer_foreign_cash'] - (f if i >= 3 else ZERO) - (buy if i >= 5 else ZERO) + (sell if i >= 18 else ZERO)))
    return dict(scenario=s['id'], bond_price=q, borrower=credit, foreign_issuer_nominal_unpaid_F=foreign_loss,
                early_conversion_F=buy, late_conversion_F=sell, requested_secured_H=request,
                secured_capacity_H=capacity, secured_draw_H=draw, pledged_units_initial=draw / unit_advance,
                secured_interest_H=r * draw, early_shortfalls=early, final_shortfalls=final,
                equity_bridge=bridge, external_funding=funding, gates=gates, feasible=all(gates.values()),
                snapshots=snapshots)


def snapshot_check(a, actual, expected, label):
    a.eq({k: v for k, v in actual.items() if k != 'event'}, expected, label + ' complete financial snapshot')
    a.yes(type(actual.get('event')) is str and bool(actual['event']), label + ' event named')
    a.yes(all(v >= 0 for v in expected['bank'].values()), label + ' no negative executed asset/claim')
    a.yes(min(expected[k] for k in ('pension_cash', 'sponsor_cash', 'lender_cash', 'dealer_home_cash', 'dealer_foreign_cash')) >= 0,
          label + ' funded outside accounts')


def scenario_check(a, data, policy, scenario, actual, journal=False):
    want = oracle(data, policy, scenario)
    for key, value in want.items():
        if key != 'snapshots':
            a.eq(actual[key], value, scenario['id'] + ' ' + key)
    for key, i in [('early_foreign_close', 6), ('early_home_close', 10), ('early_pension_close', 11),
                   ('final_home_close', 21), ('final_network_close', 22)]:
        snapshot_check(a, actual[key], want['snapshots'][i], key)
    if journal:
        a.eq(len(actual['journal']), 23, 'complete selected event journal')
        for row, wanted in zip(actual['journal'], want['snapshots']):
            snapshot_check(a, row, wanted, 'journal ' + wanted['time'])
            a.yes(wanted['pledged_units'] <= F(data['facility']['eligible_bond_units']), 'no collateral reuse')
            a.journal_rows += 1
    a.policy_states += 1
    return want


def all_baseline(a, base, report):
    menu = sorted(product(*(map(F, base['choices'][name]) for name in CHOICES)))
    a.eq(report['candidate_count'], 18, 'original Cartesian policy count')
    a.eq(len(report['candidates']), len(menu), 'all original candidates present')
    passed = []
    for policy, actual in zip(menu, report['candidates']):
        a.eq(actual['policy'], dict(zip(NAMES, policy)), 'canonical candidate identity')
        a.eq(actual['outside_cash_commitment_H'], policy[0] + policy[2], 'received outside cash commitment')
        expected = [scenario_check(a, base, policy, s, row) for s, row in zip(base['scenarios'], actual['scenarios'])]
        a.eq(len(actual['scenarios']), 3, 'every original joint state')
        feasible = all(row['feasible'] for row in expected)
        a.eq(actual['feasible'], feasible, 'unweighted scenario conjunction')
        if feasible:
            passed.append((policy[0] + policy[2], policy[1], policy[0], policy[2]))
    a.eq(report['feasible_count'], len(passed), 'independently feasible count')
    a.eq(passed, [(F(22), F(10), F(20), F(2))], 'unique feasible finite policy')
    selected = report['selected']
    a.eq(selected['policy'], dict(zip(NAMES, (F(20), F(10), F(2)))), 'ranked selected policy')
    selected_rows = [scenario_check(a, base, (F(20), F(10), F(2)), s, row, journal=True)
                     for s, row in zip(base['scenarios'], selected['scenarios'])]
    # Independent necessary conditions for finite selection, plus explicit
    # sufficient dated-state checks above. No optimization library assumed.
    a.eq(F(15) - 6, F(9), 'timely prefunding necessity')
    a.eq(F(15) - 1 - 12, F(2), 'pension grant necessity')
    a.eq(F(24) - 20 * F(4, 9) * F(3, 4), F(52, 3), 'home funding necessity')
    for row, first, last, foreign, equity in zip(selected_rows,
            [F(10), F(2), F(2)], [F(10), F(4), F(2)], [F(11), F(9), F(28, 5)],
            [F(52), F(393, 10), F(1246, 45)]):
        a.eq(encode([row['snapshots'][10]['bank']['home_cash'], row['snapshots'][21]['bank']['home_cash'],
                     row['snapshots'][21]['bank']['foreign_cash'], row['equity_bridge']['closing_equity_H']]),
             [first, last, foreign, equity], 'printed selected close anchors')
    weak = oracle(base, (F(10), F(10), F(2)), base['scenarios'][2])
    a.eq(encode([weak['secured_draw_H'], weak['early_shortfalls']['pension_benefits_H'],
                 weak['late_conversion_F'], weak['equity_bridge']['closing_equity_H']]),
         [F(20, 3), F(16, 3), F(43, 9), F(158, 9)], 'weak policy late cure retains original miss')
    return selected_rows


def risk_check(a, data, rows, report):
    values = [(row['equity_bridge']['capital_flow_adjusted_loss_H'], F(s['probability']))
              for row, s in zip(rows, data['scenarios'])]
    alpha = F(data['risk_alpha'])
    losses = sorted(set(x for x, _ in values))
    var = min(t for t in losses if sum(p for x, p in values if x <= t) >= alpha)
    # Integrate the step quantile over (alpha,1] directly. This handles a
    # boundary atom without adopting the model's reverse tail-filling routine.
    prev, integral = ZERO, ZERO
    for x in losses:
        cumulative = sum(p for y, p in values if y <= x)
        integral += x * max(ZERO, cumulative - max(alpha, prev))
        prev = cumulative
    mean, es = sum(x * p for x, p in values), integral / (1 - alpha)
    a.eq([report['expected_loss_H'], report['var_H'], report['expected_shortfall_H']], [mean, var, es], 'independent step-quantile tail integral')
    a.eq(encode([mean, var, es]), [F(2237, 270), F(127, 10), F(5519, 270)], 'all printed risk results')
    a.eq(report['tail_allocation'], [dict(loss_H=F(1094, 45), probability_used=F(1, 6)),
                                   dict(loss_H=F(127, 10), probability_used=F(1, 12))], 'fractional credit atom')


def reverse_check(a, data, policy, report):
    s = next(s for s in data['scenarios'] if s['id'] == data['reverse_scenario'])
    row = oracle(data, policy, s)
    draw, units = row['requested_secured_H'], F(data['bank']['long_bond_units'])
    q_cash = draw / (F(data['facility']['eligible_bond_units']) * (1 - F(s['haircut']))) if draw else ZERO
    nonbond = row['equity_bridge']['closing_equity_H'] - units * row['bond_price']
    q_equity = max(ZERO, (F(data['limits']['bank_equity']) - nonbond) / units)
    critical = max(q_cash, q_equity)
    a.eq([report['collateral_price_floor'], report['equity_price_floor'], report['binding_price_floor']],
         [q_cash, q_equity, critical], 'intersection of cash and capital inequalities')
    inside = F(1, 25) <= critical <= 1
    a.eq(report['boundary_within_supported_yield_0_to_4'], inside, 'bounded yield domain')
    if inside:
        at = oracle(data, policy, s, critical)
        a.eq(report['equality_feasible'], at['feasible'], 'exact price-boundary execution')
        a.eq(report['boundary_final_equity_H'], at['equity_bridge']['closing_equity_H'], 'equality capital')
        low, high = map(F, report['yield_boundary_bracket'])
        a.yes(0 <= low <= high <= 4 and high - low <= F(1, 10**12), 'bounded exact rational yield enclosure')
        a.yes((1 + low)**2 * critical <= 1 <= (1 + high)**2 * critical, 'enclosure by squared inequality')
    else:
        a.eq([report['equality_feasible'], report['yield_boundary_bracket'], report['boundary_final_equity_H']],
             [None, None, None], 'no invented out-of-domain equality')


def focus(a, run, data, policy=(F(20), F(10), F(2))):
    small = singleton(data, policy)
    report = a.run(run, small)
    a.eq(report['candidate_count'], 1, 'focused fixed-policy contract')
    row = report['candidates'][0]
    expected = [scenario_check(a, small, policy, s, actual) for s, actual in zip(small['scenarios'], row['scenarios'])]
    good = all(r['feasible'] for r in expected)
    a.eq(row['feasible'], good, 'focused changed-contract decision')
    a.eq(report['feasible_count'], int(good), 'focused selection count')
    if good:
        a.eq(report['selected']['policy'], dict(zip(NAMES, policy)), 'fixed selected identity')
        reverse_check(a, small, policy, report['reverse_stress'])
    else:
        a.eq([report['selected'], report['selected_loss_measure'], report['reverse_stress']], [None, None, None], 'no refusal relabeled as an approval')
    return report, expected


def transfers(a, run, base):
    fixed = (F(20), F(10), F(2))
    delayed = amended(base, ('scenarios', 2, 'prefund_timely'), False)
    _, rows = focus(a, run, delayed)
    joint = rows[2]
    a.eq(encode([joint['early_shortfalls']['foreign_F'], joint['equity_bridge']['closing_equity_H']]),
         [F(9), F(1246, 45)], 'transfer 1: same wealth, missed F deadline')
    a.yes(all(F(6) < 15 for _ in base['choices']['prefund_foreign']), 'no delayed original policy can pay early F')
    a.interventions += 1

    cap = amended(base, ('scenarios', 2, 'late_fx_cap'), '1')
    _, rows = focus(a, run, cap)
    a.eq(encode([rows[2]['snapshots'][21]['bank']['home_cash'], rows[2]['equity_bridge']['closing_equity_H']]),
         [F(4, 5), F(1246, 45)], 'transfer 2: reserve, not creditor, misses')
    a.eq(encode(list(rows[2]['final_shortfalls'].values())), [ZERO] * 5, 'all creditors paid with cap1')
    delta = (F(21, 5) - 3) / F(21, 20)
    a.eq(str(delta), F(8, 7), 'minimal continuous late-cap repair')
    exact, rows = focus(a, run, cap, (20 + delta, F(10), F(2)))
    a.eq(encode([rows[2]['secured_draw_H'], rows[2]['late_conversion_F'], rows[2]['equity_bridge']['closing_equity_H']]),
         [F(20, 7), F(1), F(260, 9)], 'late-cap equality ledger')
    below, _ = focus(a, run, cap, (20 + delta - F(1, 100000), F(10), F(2)))
    a.eq(below['selected'], None, 'strictly less extra equity fails')
    expanded = amended(cap, ('choices', 'bank_equity'), ['0', '10', '20', '22'])
    grid = a.run(run, expanded)
    a.eq(grid['selected']['policy'], dict(zip(NAMES, (F(22), F(10), F(2)))), 'expanded grid selects the first adequate bank subscription')
    _, rows = focus(a, run, cap, (F(22), F(10), F(2)))
    a.eq(encode([rows[2]['secured_draw_H'], rows[2]['late_conversion_F'], rows[2]['equity_bridge']['closing_equity_H']]),
         [F(2), F(7, 10), F(2681, 90)], 'added b22 ledger')
    a.interventions += 1

    higher = amended(base, ('pension', 'benefits'), '17')
    _, rows = focus(a, run, higher)
    a.eq(encode([r['early_shortfalls']['pension_benefits_H'] for r in rows]), [F(2)] * 3, 'transfer 3 pension shortage in every state')
    grants = amended(higher, ('choices', 'pension_contribution'), ['0', '2', '4'])
    grid = a.run(run, grants)
    a.eq(grid['selected']['policy'], dict(zip(NAMES, (F(20), F(10), F(4)))), 'funded new benefit promise reselects grant4')
    _, rows = focus(a, run, higher, (F(20), F(10), F(4)))
    a.eq(encode([rows[2]['external_funding']['sponsor_cash_committed_H'], rows[2]['external_funding']['sponsor_cash_remaining_H']]),
         [F(24), F(6)], 'actual sponsor outlay and unspent cash')
    a.interventions += 1

    eligible = amended(base, ('facility', 'eligible_bond_units'), '10')
    _, rows = focus(a, run, eligible)
    a.eq(encode([rows[2]['secured_draw_H'], rows[2]['snapshots'][10]['bank']['home_cash']]),
         [F(10, 3), F(4, 3)], 'transfer 4 restricted collateral keeps mark but reduces cash')
    delta = F(4) - F(10, 3)
    a.eq(str(delta), F(2, 3), 'minimum collateral-access repair')
    _, rows = focus(a, run, eligible, (20 + delta, F(10), F(2)))
    a.eq(encode([rows[2]['secured_draw_H'], rows[2]['late_conversion_F'], rows[2]['equity_bridge']['closing_equity_H']]),
         [F(10, 3), F(7, 6), F(511, 18)], 'collateral repair equality ledger')
    below, _ = focus(a, run, eligible, (20 + delta - F(1, 100000), F(10), F(2)))
    a.eq(below['selected'], None, 'strictly less collateral remedy fails')
    a.interventions += 1

    prior = amended(base, ('scenarios', 2, 'collateral_prior_claim'), '9')
    report, rows = focus(a, run, prior)
    a.eq(encode([rows[2]['borrower']['collateral_net_to_bank'], rows[2]['borrower']['actual_final_receipt'],
                 rows[2]['borrower']['terminal_nominal_unpaid'], rows[2]['late_conversion_F'],
                 rows[2]['equity_bridge']['closing_equity_H']]),
         [F(6), F(34), F(18), F(17, 5), F(976, 45)], 'transfer 5 claim priority changes recovery once')
    a.eq([report['reverse_stress']['collateral_price_floor'], report['reverse_stress']['binding_price_floor']],
         [F(4, 15), F(9, 25)], 'capital replaces collateral as first binding constraint')
    at = amended(prior, ('scenarios', 2, 'bond_yield'), '2/3')
    report, rows = focus(a, run, at)
    a.eq(encode([rows[2]['equity_bridge']['closing_equity_H'], rows[2]['secured_capacity_H']]), [F(20), F(27, 5)], 'exact rational capital equality')
    above = amended(prior, ('scenarios', 2, 'bond_yield'), str(F(2, 3) + F(1, 1000000)))
    report, _ = focus(a, run, above)
    a.eq(report['selected'], None, 'just beyond capital boundary fails')
    a.interventions += 1

    # Transfer 6 deliberately changes creditor rights outside the public model.
    pension_cash = F(1) + 2 + (12 - 10)
    a.eq(str(pension_cash), F(5), 'transfer 6 cash after deposit-to-equity conversion')
    a.eq(str(F(15) - pension_cash), F(10), 'beneficiary cash gap survives bank capital conversion')
    a.eq(str(F(30) - 20 - 2), F(8), 'fixed sponsor has less than the required new grant')
    a.interventions += 1

    # Additional boundaries exercise mechanisms absent from successful paths.
    for yield_text, feasible in [('0.93649167', True), ('0.93649168', False)]:
        data = amended(base, ('scenarios', 2, 'bond_yield'), yield_text)
        report, _ = focus(a, run, data)
        a.eq(report['selected'] is not None, feasible, 'adjacent admitted yields around irrational cash boundary')
    at_price = oracle(base, fixed, base['scenarios'][2], F(4, 15))
    a.eq(str(at_price['equity_bridge']['closing_equity_H']), F(362, 15), 'exact reserve equality equity')
    paid_price = oracle(base, fixed, base['scenarios'][2], F(2, 15))
    a.eq(encode([paid_price['early_shortfalls']['households_H'], paid_price['early_shortfalls']['pension_bank_claim_H'],
                 paid_price['snapshots'][10]['bank']['home_cash']]), [ZERO, ZERO, ZERO], 'creditor payment boundary differs from reserve')
    a.interventions += 1

    for cap_text, feasible in [('4', True), ('3.99999999', False)]:
        data = amended(base, ('endowments', 'lender_home_cash'), cap_text)
        report, _ = focus(a, run, data)
        a.eq(report['selected'] is not None, feasible, 'actual lender cash at/under required draw')
    a.interventions += 1

    data = amended(base, ('scenarios', 2, 'late_fx_cap'), '0')
    _, rows = focus(a, run, data)
    a.eq(str(rows[2]['final_shortfalls']['households_H']), F(11, 5), 'no conversion retains unpaid household claim')
    a.interventions += 1

    data = amended(base, ('facility', 'interest'), '0')
    _, rows = focus(a, run, data)
    a.eq(encode([rows[2]['equity_bridge']['closing_equity_H'], rows[2]['late_conversion_F']]),
         [F(251, 9), F(4, 3)], 'zero interest changes expense and funded FX need')
    a.interventions += 1

    data = amended(base, ('bank', 'bill'), '0')
    data['scenarios'] = [data['scenarios'][2]]
    data['scenarios'][0].update(probability='1', borrower_cash_final='0', collateral_gross='0',
        collateral_cost='0', collateral_prior_claim='0', late_fx_cap='0')
    _, rows = focus(a, run, data)
    a.eq(encode([rows[0]['final_shortfalls']['secured_H'], rows[0]['snapshots'][21]['pledged_units'],
                 rows[0]['external_funding']['new_investor_closing_marked_stake_H']]),
         [F(11, 5), F(12), ZERO], 'unpaid secured debt retains collateral; shareholder downside limited')
    a.interventions += 1

    data = deepcopy(base)
    data['scenarios'] = [data['scenarios'][0]]
    data['scenarios'][0]['probability'] = '1'
    data['reverse_scenario'] = 'normal'
    data['limits']['bank_equity'] = '0'
    report, _ = focus(a, run, data)
    a.eq(report['reverse_stress']['binding_price_floor'], ZERO, 'zero boundary lies outside finite yield range')
    a.interventions += 1


class Markup(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids, self.links, self.sources, self.rubric, self.stack = [], [], set(), [], []
        self.solution_items = self.depth = self.h1 = 0
    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if 'id' in d:
            self.ids.append(d['id'])
        if tag == 'h1':
            self.h1 += 1
        if tag == 'a':
            self.links.append(d.get('href', ''))
            if 'data-source' in d:
                self.sources.add(d['data-source'])
        if tag == 'tr' and 'data-points' in d:
            self.rubric.append((d.get('data-domain'), int(d['data-points'])))
        if tag == 'details' and 'solutions' in d.get('class', '').split():
            self.depth = 1
        elif self.depth and tag == 'details':
            self.depth += 1
        if self.depth and tag == 'li':
            self.solution_items += 1
        if tag not in ('br', 'hr', 'img', 'input', 'meta', 'link', 'wbr', 'source', 'area', 'base', 'col', 'embed', 'param', 'track'):
            self.stack.append(tag)
    def handle_endtag(self, tag):
        require(bool(self.stack) and self.stack.pop() == tag, 'unbalanced explicit HTML markup')
        if tag == 'details' and self.depth:
            self.depth -= 1


def structure_and_hashes(a, bound):
    html = (ROOT / AUTHOR[0]).read_text()
    parser = Markup(); parser.feed(html); parser.close()
    a.eq(parser.stack, [], 'closed fragment markup')
    a.eq(parser.h1, 0, 'no duplicate page h1')
    a.eq(len(parser.ids), len(set(parser.ids)), 'unique project anchors')
    a.yes(all(i == 'project' or i.startswith('v11-project-') for i in parser.ids), 'owned anchor namespace')
    a.eq(parser.solution_items, 6, 'six complete transfer answer items')
    a.eq(parser.rubric, [('D' + str(i), 20) for i in range(1, 6)], 'five essential domains and 100 points')
    for i in range(1, 7):
        a.yes('v11-project-task-' + str(i) in parser.ids, 'required learner deliverable')
        a.yes('v11-project-transfer-' + str(i) in parser.ids, 'required unfamiliar transfer')
    for i in range(1, 13):
        a.yes('v11-c' + str(i).zfill(2) + '.html' in parser.links, 'all twelve chapter method routes')
    for path in AUTHOR[1:6]:
        a.yes(Path(path).name in parser.links, 'flat portable download route')
    sources = strict((ROOT / AUTHOR[8]).read_text())
    a.eq(parser.sources, {row['id'] for row in sources['reuse']}, 'exact inherited source scopes')
    a.eq(sources['proposals'], [], 'no unsupported new primary-source claim')
    for phrase in ('original', '14–20 hours', '85/100', '15/20', 'critical', '1,200 words', 'ten-minute'):
        a.yes(phrase.lower() in html.lower(), 'explicit administration/rubric: ' + phrase)
    manifest = strict((ROOT / AUTHOR[4]).read_text())
    a.eq({r['file'] for r in manifest['files']}, {Path(p).name for p in [AUTHOR[1], AUTHOR[2], AUTHOR[3], AUTHOR[5]]}, 'four exact manifest payloads')
    a.eq(len(manifest['files']), 4, 'four manifest rows')
    for row in manifest['files']:
        body = (PROJECT / row['file']).read_bytes()
        a.eq([len(body), sha256(body).hexdigest()], [row['bytes'], row['sha256']], 'manifest bytes')
    author = strict((ROOT / AUTHOR[7]).read_text())
    hashes = author['reviewed_hashes']
    a.eq(len(hashes), 8, 'eight nonself author bindings')
    a.eq({r['path'] for r in hashes}, set(AUTHOR) - {AUTHOR[7]}, 'exact author binding set')
    for row in hashes:
        body = (ROOT / row['path']).read_bytes()
        a.eq([len(body), sha256(body).hexdigest()], [row['bytes'], row['sha256']], 'author reviewed bytes')
    a.eq(author['unresolved_findings'], [], 'author records no open finding')
    if bound:
        peer = strict((ROOT / PEER).read_text())
        hashes = peer['reviewed_hashes']
        a.eq(len(hashes), 10, 'nine author payloads plus own checker bound')
        a.eq({r['path'] for r in hashes}, set(AUTHOR) | {SELF}, 'peer exact nonself set')
        for row in hashes:
            body = (ROOT / row['path']).read_bytes()
            a.eq([len(body), sha256(body).hexdigest()], [row['bytes'], row['sha256']], 'peer final frozen bytes')


def invalid_inputs(a, run, base):
    mutations = [
        (('schema',), True), (('unexpected',), '1'), (('bank',), []),
        (('initial_spot',), 2), (('initial_spot',), True), (('initial_spot',), 'NaN'),
        (('initial_spot',), '2e0'), (('initial_spot',), '2/0'), (('initial_spot',), '0'),
        (('bank', 'home_cash'), '-1'), (('bank', 'long_bond_units'), '0'),
        (('first_due', 'borrower_principal'), '60'), (('pension', 'benefits'), '0'),
        (('choices', 'bank_equity'), ['0', '0/2']), (('choices', 'bank_equity'), []),
        (('choices', 'prefund_foreign'), ['11']), (('endowments', 'sponsor_home_cash'), '21'),
        (('endowments', 'dealer_foreign_cash'), '29'), (('endowments', 'dealer_home_cash'), '39'),
        (('endowments', 'collateral_buyer_home_cash'), '17'), (('facility', 'eligible_bond_units'), '21'),
        (('facility', 'interest'), '2'), (('risk_alpha',), '1'), (('reverse_scenario',), 'missing'),
        (('scenarios', 2, 'probability'), '1/5'), (('scenarios', 2, 'prefund_timely'), 1),
        (('scenarios', 2, 'haircut'), '1'), (('scenarios', 2, 'bond_yield'), '5'),
        (('scenarios', 2, 'foreign_recovery'), '21'), (('scenarios', 2, 'borrower_cash_first'), '21'),
        (('scenarios', 2, 'collateral_prior_claim'), '16'),
    ]
    for bad in [None] + [amended(base, p, v) for p, v in mutations]:
        before, stream = deepcopy(bad), StringIO()
        try:
            with redirect_stdout(stream), redirect_stderr(stream):
                run(bad)
        except ValueError:
            pass
        else:
            raise ValueError('invalid contract accepted')
        a.eq(bad, before, 'invalid API input preserved')
        a.eq(stream.getvalue(), '', 'invalid API remains quiet')
        a.invalid_api += 1


def cli_checks(a, base, expected):
    def invoke(args):
        return subprocess.run(args, cwd='/', capture_output=True, text=True, timeout=30)
    with tempfile.TemporaryDirectory(prefix='v11-peer-portlight-') as directory:
        root = Path(directory)
        model, source = root / MODEL.name, root / INPUT.name
        model.write_bytes(MODEL.read_bytes()); source.write_bytes(INPUT.read_bytes())
        default, output = root / 'v11-assessment-output.json', root / 'custom.json'
        badfile = root / 'invalid.json'
        invalid = ['{"schema":1,"schema":1}', '{"x":NaN}', '{', '[]', ' ' * 65537,
                   json.dumps(amended(base, ('facility', 'eligible_bond_units'), '21'))]
        (root / 'child').mkdir()
        before = (source.read_bytes(), model.read_bytes())
        for optimize in ([], ['-O']):
            command = [sys.executable, '-I', '-B'] + optimize + [str(model)]
            for args, destination in [([], default), (['--input', str(source), '--output', str(output)], output)]:
                r = invoke(command + args)
                a.eq([r.returncode, r.stdout, r.stderr], [0, '', ''], 'quiet arbitrary-CWD model CLI')
                a.eq(destination.read_bytes(), expected, 'portable canonical bytes')
                a.portable_model_runs += 1
            for text in invalid:
                badfile.write_text(text)
                output.write_text('preserve destination\n')
                r = invoke(command + ['--input', str(badfile), '--output', str(output)])
                a.eq([r.returncode, r.stdout], [2, ''], 'invalid CLI explicit refusal')
                a.yes(bool(r.stderr) and 'Traceback' not in r.stderr, 'concise error')
                a.eq(output.read_text(), 'preserve destination\n', 'invalid input does not open output')
                a.invalid_cli += 1
            for protected in (source, model):
                symlink, hardlink = root / ('sym-' + protected.name), root / ('hard-' + protected.name)
                if symlink.is_symlink():
                    symlink.unlink()
                if hardlink.exists():
                    hardlink.unlink()
                symlink.symlink_to(protected)
                os.link(protected, hardlink)
                for target in (protected, root / 'child' / '..' / protected.name, symlink, hardlink):
                    r = invoke(command + ['--input', str(source), '--output', str(target)])
                    a.eq([r.returncode, r.stdout], [2, ''], 'actual direct/parent/symbolic/hard output alias refused')
                    a.yes(bool(r.stderr) and 'Traceback' not in r.stderr, 'alias error is explicit')
                    a.eq((source.read_bytes(), model.read_bytes()), before, 'protected bytes unchanged')
                    a.aliases += 1
                default.unlink()
                default.symlink_to(protected)
                r = invoke(command)
                a.eq([r.returncode, r.stdout], [2, ''], 'default output alias refused')
                a.eq((source.read_bytes(), model.read_bytes()), before, 'default protected bytes unchanged')
                a.aliases += 1
            default.unlink()


def check(verify_bindings=True):
    a = Audit()
    structure_and_hashes(a, verify_bindings)
    base = strict(INPUT.read_text())
    stream = StringIO()
    with redirect_stdout(stream), redirect_stderr(stream):
        run = runpy.run_path(str(MODEL))['run']
    a.eq(stream.getvalue(), '', 'quiet model import')
    report = a.run(run, base)
    rows = all_baseline(a, base, report)
    risk_check(a, base, rows, report['selected_loss_measure'])
    reverse_check(a, base, (F(20), F(10), F(2)), report['reverse_stress'])
    transfers(a, run, base)
    saved = (PROJECT / 'v11-assessment-output.json').read_bytes()
    a.eq(strict(saved), report, 'all saved output fields equal the freshly audited result')
    a.eq(saved, (json.dumps(report, indent=2, sort_keys=True) + '\n').encode(), 'saved canonical output bytes')
    fresh = a.run(run, base)
    report['selected']['policy']['bank_equity_H'] = 'returned object changed'
    a.eq(a.run(run, base), fresh, 'no shared mutable result state')
    invalid_inputs(a, run, base)
    cli_checks(a, base, saved)
    return dict(component='v11-project-peer', status='passed', comparisons=a.comparisons,
        baseline_policies=18, independently_recomputed_policy_states=a.policy_states,
        selected_journal_rows=a.journal_rows, transfer_answers=6, focused_mechanism_groups=a.interventions,
        essential_domains=5, rubric_points=100, invalid_api_cases=a.invalid_api,
        invalid_cli_cases=a.invalid_cli, protected_alias_attempts=a.aliases,
        portable_model_runs=a.portable_model_runs, author_payloads_bound=9 if verify_bindings else 0,
        own_checker_bound=bool(verify_bindings))


if __name__ == '__main__':
    print(json.dumps(check(), sort_keys=True, allow_nan=False))
