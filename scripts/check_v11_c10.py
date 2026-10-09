"""Bounded independent author checks for V11-C10; quiet check(), no model oracle.

Separate stakeholder flows, Frechet endpoint inspection/harm laws and additive
journal vectors certify the finite cases. This is machine-assisted author review,
not independent peer acceptance or an empirical/legal certification.
"""
import contextlib
import copy
from fractions import Fraction as F
import hashlib
from html.parser import HTMLParser
import io
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PREFIX = 'v11-c10'
PROJECT = ROOT/'content/projects'
MODEL = PROJECT/(PREFIX+'-analysis.py')
INPUT = PROJECT/(PREFIX+'-inputs.json')
OWNED = [
    'content/chapters/v11-c10.html',
    'content/projects/v11-c10-inputs.json',
    'content/projects/v11-c10-analysis.py',
    'content/projects/v11-c10-output.json',
    'content/projects/v11-c10-manifest.json',
    'content/projects/v11-c10-README.txt',
    'scripts/check_v11_c10.py',
    'content/reviews/v11-c10-author.json',
    'content/reviews/v11-c10-sources.json',
]
COUNTS = {}


def need(ok, label):
    COUNTS['comparisons'] += 1
    if not ok:
        raise ValueError(PREFIX+' check: '+label)


def eq(actual, wanted, label):
    need(actual == wanted, label+'; got '+repr(actual)+' expected '+repr(wanted))


def strict(text):
    def unique(pairs):
        out = {}
        for k, v in pairs:
            if k in out:
                raise ValueError('duplicate JSON key')
            out[k] = v
        return out
    def bad(value):
        raise ValueError('nonfinite JSON constant '+value)
    return json.loads(text, object_pairs_hook=unique, parse_constant=bad)


def packed(x):
    if isinstance(x, F):
        return str(x)
    if isinstance(x, list):
        return [packed(v) for v in x]
    if isinstance(x, dict):
        return {k: packed(v) for k, v in x.items()}
    return x


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def set_at(data, path, value):
    out = copy.deepcopy(data)
    dest = out
    for key in path[:-1]:
        dest = dest[key]
    dest[path[-1]] = value
    return out


def portfolio_oracle(raw):
    a0, capital = F(raw['initial_assets']), F(raw['capital'])
    deposits, reserve = a0-capital, F(raw['insurer_reserve'])
    harm, weight = F(raw['harm_if_default']), F(raw['capture_weight'])
    prob = list(map(F, raw['probabilities']))
    eq(sum(prob), 1, 'physical law normalization')
    options = []
    for source in raw['options']:
        states, owner_net, insurer_net, asset_net, outside_loss, default_weight = [], F(0), F(0), F(0), F(0), F(0)
        for p, value in zip(prob, map(F, source['assets'])):
            # Give bank assets to the contractual deposit claim, then to owners.
            remaining = value
            to_deposits = min(remaining, deposits)
            remaining -= to_deposits
            external_payment = deposits-to_deposits
            insurer_final = reserve-external_payment
            personal_owner_gain = remaining-capital
            personal_insurer_gain = insurer_final-reserve
            disrupted = to_deposits < deposits
            loss = harm*int(disrupted)
            eq(to_deposits+external_payment, deposits, 'guaranteed depositor receipt')
            eq(remaining+to_deposits, value, 'bank priority resource identity')
            eq(personal_owner_gain+personal_insurer_gain, value-a0, 'stakeholder net changes equal asset gain')
            need(insurer_final >= 0, 'every listed guarantee state is funded')
            owner_net += p*personal_owner_gain
            insurer_net += p*personal_insurer_gain
            asset_net += p*(value-a0)
            outside_loss += p*loss
            default_weight += p*int(disrupted)
            states.append({'probability': p, 'assets': value, 'deposit_from_bank': to_deposits,
                           'insurance_payment': external_payment, 'deposit_total': deposits,
                           'equity_residual': remaining, 'insurer_closing_reserve': insurer_final,
                           'real_harm': loss, 'default': disrupted})
        eq(owner_net+insurer_net, asset_net, 'expected transfer cancellation')
        options.append({'id': source['id'], 'states': states, 'expected_assets': a0+asset_net,
                        'asset_gain': asset_net, 'private_profit': owner_net,
                        'expected_insurance': -insurer_net, 'default_probability': default_weight,
                        'expected_real_harm': outside_loss, 'welfare_before_policy_cost': owner_net+insurer_net-outside_loss})
    policies = []
    for policy in raw['policies']:
        requirements = {s['id']: F(policy['ratio'])*F(s[policy['basis']+'_exposure']) for s in raw['options']}
        allowed = [row for row in options if capital-requirements[row['id']] >= 0]
        # Pairwise dominance, rather than the model's max helper, retains every tie.
        winners = [row for row in allowed if all(row['private_profit'] >= other['private_profit'] for other in allowed)]
        outcomes = []
        for row in winners:
            welfare = row['private_profit']-row['expected_insurance']-row['expected_real_harm']-F(policy['resource_cost'])
            outcomes.append({'choice': row['id'], 'private_profit': row['private_profit'],
                             'welfare': welfare, 'score': welfare+weight*row['private_profit']})
        policies.append({'id': policy['id'], 'required_capital': requirements,
                         'feasible': [row['id'] for row in allowed],
                         'best_responses': [row['id'] for row in winners],
                         'status': 'feasible' if allowed else 'no feasible option', 'outcomes': outcomes})
    active = [p for p in policies if p['outcomes']]
    tie_dependent = any(any(y['score'] != p['outcomes'][0]['score'] for y in p['outcomes']) for p in active)
    maximizers = None if tie_dependent else [p['id'] for p in active
        if all(p['outcomes'][0]['score'] >= q['outcomes'][0]['score'] for q in active)]
    return packed({'initial_deposits': deposits, 'options': options, 'policies': policies,
                   'score_maximizers': maximizers,
                   'ranking_status': 'tie-dependent; inspect all outcomes' if tie_dependent else 'determinate over feasible policies'})


def conduct_oracle(raw):
    x = {k: F(v) for k, v in raw.items()}
    a = x['inspection_probability']
    # The promised and pledged amounts independently limit actual collection.
    collectible = x['fine'] if x['fine'] <= x['pledged_funds'] else x['pledged_funds']
    rows = []
    for ident in ('care', 'shortcut'):
        p = x[ident+'_harm_probability']
        cost = x['care_cost'] if ident == 'care' else F(0)
        endpoint_results = []
        # Both Frechet endpoint couplings preserve marginal inspection and harm.
        # Equal expectations show no unneeded independence assumption is used.
        for joint in (max(F(0), a+p-1), min(a, p)):
            states = [(True, True, joint), (True, False, a-joint),
                      (False, True, p-joint), (False, False, 1-a-p+joint)]
            eq(sum(w for _, _, w in states), 1, 'inspection/harm law total')
            eq(sum(w for inspected, _, w in states if inspected), a, 'inspection law marginal')
            eq(sum(w for _, harmed, w in states if harmed), p, 'harm law marginal')
            totals = [F(0)]*7
            for inspected, harmed, w in states:
                need(w >= 0, 'Frechet weights nonnegative')
                fine = collectible if inspected and ident == 'shortcut' else F(0)
                seller = x['fee']-cost-fine
                buyer = x['gross_benefit']-x['fee']-int(harmed)*x['harm']
                inspection_cost = int(inspected)*x['inspection_cost']
                authority = fine-inspection_cost
                eq(buyer+seller+authority, x['gross_benefit']-cost-int(harmed)*x['harm']-inspection_cost,
                   'state fee/fine transfers cancel')
                values = [seller, buyer, authority, fine, int(harmed)*x['harm'], cost, inspection_cost]
                totals = [u+w*v for u, v in zip(totals, values)]
            endpoint_results.append(totals)
        eq(endpoint_results[0], endpoint_results[1], 'additive expectation invariant to inspection/harm coupling')
        t = endpoint_results[0]
        rows.append({'id': ident, 'seller_profit': t[0], 'buyer_net': t[1], 'authority_net': t[2],
                     'expected_fine': t[3], 'expected_harm': t[4], 'expected_real_care_cost': t[5],
                     'expected_inspection_cost': t[6], 'welfare': sum(t[:3])})
    choices = [r['id'] for r in rows if all(r['seller_profit'] >= q['seller_profit'] for q in rows)]
    return packed({'collectible_fine': collectible, 'deterrence_margin': rows[0]['seller_profit']-rows[1]['seller_profit'],
                   'best_responses': choices, 'actions': rows})


def resolution_oracle(raw):
    x = {k: F(v) for k, v in raw.items()}
    initial_assets = x['cash']+x['long_assets']
    eq0 = initial_assets-x['deposits']-x['senior']-x['junior']
    residual_loss = x['asset_loss']
    absorption = []
    for available in (eq0, x['junior'], x['senior']):
        charge = min(available, residual_loss)
        absorption.append(charge)
        residual_loss -= charge
    eq(residual_loss, 0, 'ordered loss absorption exhausts loss')
    eq(absorption[:2], [eq0, x['junior']], 'supported loss region')
    senior_left = x['senior']-absorption[2]
    # Vector order cash, long, deposits, senior, junior, bridge, equity.
    ledger = [x['cash'], x['long_assets'], x['deposits'], x['senior'], x['junior'], F(0), eq0]
    stages = []
    keys = ['cash', 'long_assets', 'deposits', 'senior', 'junior', 'bridge', 'equity']
    def post(label, changes=None):
        if changes is not None:
            for n, change in enumerate(changes):
                ledger[n] += change
        eq(ledger[0]+ledger[1], sum(ledger[2:]), 'balanced journal '+label)
        stages.append(dict(stage=label, **dict(zip(keys, ledger))))
    z, loss, cv = F(0), x['asset_loss'], x['conversion']
    post('opening')
    post('after_asset_loss', [z, -loss, z, z, z, z, -loss])
    post('after_write_down', [z, z, z, -absorption[2], -absorption[1], z, absorption[1]+absorption[2]])
    post('after_conversion', [z, z, z, -cv, z, z, cv])
    need_early = x['due_first']-ledger[0]
    advance = need_early if need_early > 0 else z
    interest = advance*x['bridge_rate']
    funded = advance <= x['bridge_capacity']
    solvent = cv >= interest
    final = None
    if funded:
        post('after_bridge', [advance, z, z, z, z, advance, z])
        due = x['due_first']
        post('after_first_payment', [-due, z, -due, z, z, z, z])
        realization = ledger[1]
        post('maturity_before_payments', [realization, -realization, z, z, z, interest, -interest])
        if solvent:
            payable = ledger[2:6]
            final_cash = ledger[0]-sum(payable)
            post('after_final_payments', [-sum(payable), z, -payable[0], -payable[1], -payable[2], -payable[3], z])
            eq(ledger[0], ledger[-1], 'terminal cash equals equity after debt payment')
            senior_debt = senior_left-cv
            eq(x['deposits']+senior_debt+final_cash+interest, initial_assets-loss,
               'old claim values plus lender net income equal surviving assets')
            final = {'cash_and_equity': final_cash, 'deposit_receipts_total': x['deposits'],
                     'old_senior_debt_receipts': senior_debt, 'old_senior_new_equity_value': final_cash,
                     'old_senior_total_value': senior_debt+final_cash,
                     'lender_repayment': advance+interest, 'lender_net_interest': interest,
                     'old_claims_total_value': x['deposits']+senior_debt+final_cash}
    proceeds = initial_assets-loss-x['liquidation_cost']
    left, receipts = proceeds, []
    for claim in (x['deposits'], x['senior'], x['junior'], eq0):
        payment = min(claim, left)
        left -= payment
        receipts.append(payment)
    eq(left, 0, 'liquidation priority exhausts proceeds')
    return packed({'original_equity': eq0, 'remaining_assets': initial_assets-loss,
                   'loss_absorption': dict(zip(('old_equity', 'junior', 'senior'), absorption)),
                   'surviving_senior_before_conversion': senior_left,
                   'first_cash_gap': advance, 'minimum_external_advance': advance,
                   'unfunded_first_gap': advance-x['bridge_capacity'] if not funded else z,
                   'bridge_interest_if_funded': interest, 'first_cutoff_funded': funded,
                   'terminal_claims_funded_if_bridge': solvent, 'capital_after_conversion': cv,
                   'capital_after_interest_if_funded': cv-interest,
                   'immediate_capital_pass': cv >= x['capital_floor'],
                   'continuing_capital_pass': funded and cv-interest >= x['capital_floor'],
                   'status': ('first cutoff unfunded; no payment continuation assumed' if not funded else
                              'terminal claims underfunded; no final allocation assumed' if not solvent else 'funded continuation'),
                   'snapshots': stages, 'final': final,
                   'liquidation': dict(zip(('net_assets', 'deposit_receipts', 'senior_receipts', 'junior_receipts', 'old_equity_receipts'), [proceeds]+receipts))})


ORACLES = {'portfolio': portfolio_oracle, 'conduct': conduct_oracle, 'resolution': resolution_oracle}


def case(run, data, label, baseline=None, changed=None):
    COUNTS['cases'] += 1
    before = copy.deepcopy(data)
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
        result = run(data)
    eq(buffer.getvalue(), '', 'quiet API '+label)
    eq(data, before, 'nonmutating API '+label)
    eq(set(result), {'schema', 'chapter', 'portfolio', 'conduct', 'resolution'}, 'result shape '+label)
    eq((result['schema'], result['chapter']), (1, PREFIX), 'result provenance '+label)
    json.dumps(result, allow_nan=False)
    for section, oracle in ORACLES.items():
        expected = oracle(data[section]) if baseline is None or section == changed else baseline[section]
        eq(result[section], expected, 'independent '+section+' '+label)
    return result


def option(out, ident):
    return next(r for r in out['portfolio']['options'] if r['id'] == ident)


def policy(out, ident):
    return next(r for r in out['portfolio']['policies'] if r['id'] == ident)


def interventions(run, base, original):
    results = {}
    def change(label, section, updates):
        candidate = copy.deepcopy(base)
        for path, value in updates:
            dest = candidate[section]
            for key in path[:-1]:
                dest = dest[key]
            dest[path[-1]] = value
        COUNTS['financial_interventions'] += 1
        results[label] = case(run, candidate, label, original, section)
        return results[label]
    def one(label, section, field, value):
        return change(label, section, [([field], value)])

    # Different sides AND exact equality of the derived welfare/score boundaries.
    for harm in ('15', '16', '21'):
        r = one('harm_'+harm, 'portfolio', 'harm_if_default', harm)
        eq(r['portfolio']['score_maximizers'], ['none'] if harm == '15' else ['none', 'broad'] if harm == '16' else ['broad'], 'harm boundary maximizers')
    for label, weight, winners in [('below', '1/20', ['broad']), ('tie', '4/43', ['none', 'broad']), ('above', '1/10', ['none'])]:
        r = one('capture_'+label, 'portfolio', 'capture_weight', weight)
        eq(r['portfolio']['score_maximizers'], winners, 'capture threshold '+label)
    for capital, profits, insurance, surplus, policy_values in [
        ('20', ['8', '35/2', '67/4'], ['0', '15/2', '31/4'], ['8', '5', '4'], ['5', '9/2', '3']),
        ('50', ['8', '10', '37/4'], ['0', '0', '1/4'], ['8', '10', '4'], ['10', '19/2', '8'])]:
        r = one('capital_'+capital, 'portfolio', 'capital', capital)
        eq([o['private_profit'] for o in r['portfolio']['options']], profits, 'financing profits')
        eq([o['expected_insurance'] for o in r['portfolio']['options']], insurance, 'financing insurance')
        eq([o['welfare_before_policy_cost'] for o in r['portfolio']['options']], surplus, 'financing surplus')
        eq([p['best_responses'] for p in r['portfolio']['policies']], [['H']]*3, 'screen equality permits H')
        eq([p['outcomes'][0]['welfare'] for p in r['portfolio']['policies']], policy_values, 'financing after-cost welfare')
    r = change('private_tie', 'portfolio', [(['options', 0, 'assets'], ['475/4', '475/4'])])
    eq(policy(r, 'none')['best_responses'], ['C', 'H'], 'retain private ties')
    eq([o['welfare'] for o in policy(r, 'none')['outcomes']], ['75/4', '5'], 'tied action welfare interval')
    eq(policy(r, 'broad')['outcomes'][0]['welfare'], '67/4', 'broad tied-case welfare')
    eq(r['portfolio']['score_maximizers'], None, 'no unstated tie convention')
    r = change('empty_screens', 'portfolio', [(['capital'], '0'), (['insurer_reserve'], '100')])
    eq([p['status'] for p in r['portfolio']['policies']], ['feasible', 'no feasible option', 'no feasible option'], 'infeasible menus reported')
    r = change('all_screens_empty', 'portfolio', [(['capital'], '0'), (['insurer_reserve'], '100'), (['policies', 0, 'ratio'], '1')])
    eq(r['portfolio']['score_maximizers'], [], 'no invented option when all policies infeasible')
    r = one('zero_probability', 'portfolio', 'probabilities', ['1', '0'])
    eq(option(r, 'H')['expected_insurance'], '0', 'zero-probability expectation')

    r = one('conduct_tie', 'conduct', 'fine', '8')
    eq(r['conduct']['best_responses'], ['care', 'shortcut'], 'conduct equality preserved')
    r = change('no_inspection', 'conduct', [(['inspection_probability'], '0'), (['authority_budget'], '0')])
    eq(r['conduct']['best_responses'], ['shortcut'], 'zero detection cannot deter')
    eq(r['conduct']['actions'][1]['welfare'], '3', 'no-inspection shortcut welfare')
    limited = [(['fine'], '100'), (['pledged_funds'], '7')]
    r = change('collection_limited', 'conduct', limited+[(['inspection_probability'], '1/10')])
    eq([a['seller_profit'] for a in r['conduct']['actions']], ['4', '53/10'], 'paper versus collectible fine')
    r = change('collection_boundary', 'conduct', limited+[(['inspection_probability'], '2/7')])
    eq(r['conduct']['best_responses'], ['care', 'shortcut'], 'inspection collection exact boundary')
    eq(r['conduct']['actions'][0]['welfare'], '115/14', 'care welfare at boundary')
    r = change('inspection_capacity', 'conduct', limited+[(['inspection_probability'], '1/5')])
    eq(r['conduct']['deterrence_margin'], '-3/5', 'capacity prevents deterrence')

    r = one('continuing_capital', 'resolution', 'conversion', '26/5')
    eq((r['resolution']['continuing_capital_pass'], r['resolution']['final']['cash_and_equity']), (True, '5'), 'interest-aware conversion')
    eq(r['resolution']['final']['old_senior_total_value'], '49/5', 'conversion preserves class value')
    r = one('bridge_shortfall', 'resolution', 'bridge_capacity', '3')
    eq((r['resolution']['unfunded_first_gap'], r['resolution']['final'], len(r['resolution']['snapshots'])), ('1', None, 4), 'no invented unfunded continuation')
    r = change('conversion_cannot_fund', 'resolution', [(['bridge_capacity'], '3'), (['conversion'], '10')])
    eq((r['resolution']['unfunded_first_gap'], r['resolution']['continuing_capital_pass']), ('1', False), 'capital cannot close cash gap')
    r = change('dearer_bridge', 'resolution', [(['bridge_rate'], '3/20'), (['conversion'], '28/5')])
    eq((r['resolution']['final']['old_senior_debt_receipts'], r['resolution']['final']['cash_and_equity'], r['resolution']['final']['old_senior_total_value']), ('22/5', '5', '47/5'), 'expensive funded bridge ledger')
    r = change('terminal_shortfall', 'resolution', [(['bridge_rate'], '3/20'), (['conversion'], '1/5')])
    eq((r['resolution']['first_cutoff_funded'], r['resolution']['terminal_claims_funded_if_bridge'], r['resolution']['final']), (True, False, None), 'no invented second default allocation')
    eq(r['resolution']['snapshots'][-1]['equity'], '-2/5', 'maturity insolvency retained')
    r = change('cash_already_available', 'resolution', [(['due_first'], '6'), (['bridge_capacity'], '0'), (['lender_cash'], '0')])
    eq((r['resolution']['first_cash_gap'], r['resolution']['final']['cash_and_equity']), ('0', '5'), 'no borrowing when cash sufficient')
    r = change('zero_rate_zero_conversion', 'resolution', [(['bridge_rate'], '0'), (['conversion'], '0'), (['capital_floor'], '0')])
    eq((r['resolution']['final']['cash_and_equity'], r['resolution']['continuing_capital_pass']), ('0', True), 'zero rate equality case')
    r = one('senior_loss_boundary', 'resolution', 'asset_loss', '20')
    eq(r['resolution']['loss_absorption']['senior'], '0', 'senior write-down lower boundary')
    r = change('deposit_coverage_boundary', 'resolution', [(['asset_loss'], '40'), (['conversion'], '0'), (['capital_floor'], '0'), (['bridge_rate'], '0')])
    eq((r['resolution']['surviving_senior_before_conversion'], r['resolution']['final']['cash_and_equity']), ('0', '0'), 'protected deposits exact coverage boundary')
    return results


def numeric_manuscript(original, results):
    # Hard-coded displayed answers are checked against independently certified runs.
    eq([o['private_profit'] for o in original['portfolio']['options']], ['8', '75/4', '18'], 'worked1 owner profits')
    eq([o['expected_insurance'] for o in original['portfolio']['options']], ['0', '35/4', '9'], 'worked1 insurer transfer')
    eq([o['expected_assets'] for o in original['portfolio']['options']], ['108', '110', '109'], 'worked1 total asset values')
    eq([o['welfare_before_policy_cost'] for o in original['portfolio']['options']], ['8', '5', '4'], 'worked1 resource welfare')
    eq([o['default_probability'] for o in original['portfolio']['options']], ['0', '1/4', '1/4'], 'worked1 strict default boundary')
    eq(option(original, 'routed_H')['states'][1]['insurer_closing_reserve'], '4', 'worst guarantee closing reserve')
    eq([p['required_capital'] for p in original['portfolio']['policies']],
       [{'C':'0','H':'0','routed_H':'0'}, {'C':'10','H':'20','routed_H':'8'}, {'C':'10','H':'20','routed_H':'20'}], 'worked2 screen table')
    eq([p['outcomes'][0]['welfare'] for p in original['portfolio']['policies']], ['5','7/2','6'], 'worked2 induced surplus')
    eq([p['outcomes'][0]['score'] for p in results['capture_above']['portfolio']['policies']], ['55/8','53/10','34/5'], 'exercise4 decimal scores')
    eq(F('6.875')-F('6.8'), F('0.075'), 'exercise4 margin')
    eq(F(4,43), F(1)/F('10.75'), 'capture threshold derivation')
    need(abs(float(F(4,43))-0.0930233)<0.00000005, 'capture threshold rounding')
    need(abs(float(F(115,14))-8.214286)<0.0000005, 'conduct boundary rounding')
    eq(F('1.5')+F('0.75')*F(1,10), F('1.575'), 'strict narrow dominance at positive weight')
    eq([a['seller_profit'] for a in original['conduct']['actions']], ['4','7/2'], 'worked3 seller table')
    eq([a['buyer_net'] for a in original['conduct']['actions']], ['9/2','-3'], 'worked3 buyer table')
    eq([a['authority_net'] for a in original['conduct']['actions']], ['-1/4','9/4'], 'worked3 authority table')
    eq([a['welfare'] for a in original['conduct']['actions']], ['33/4','11/4'], 'worked3 welfare table')
    eq(original['conduct']['deterrence_margin'], '1/2', 'worked3 strict incentive margin')
    resolution = original['resolution']
    matrix = [[row[k] for k in ('cash','long_assets','deposits','senior','junior','bridge','equity')] for row in resolution['snapshots']]
    eq(matrix, [['6','94','60','20','10','0','10'], ['6','64','60','20','10','0','-20'],
                ['6','64','60','10','0','0','0'], ['6','64','60','5','0','0','5'],
                ['10','64','60','5','0','4','5'], ['0','64','50','5','0','4','5'],
                ['64','0','50','5','0','21/5','24/5'], ['24/5','0','0','0','0','0','24/5']], 'worked4 and exercise7 every printed journal row')
    eq(resolution['loss_absorption'], {'old_equity':'10','junior':'10','senior':'10'}, 'worked4 ordered loss values')
    eq(resolution['liquidation'], {'net_assets':'62','deposit_receipts':'60','senior_receipts':'2','junior_receipts':'0','old_equity_receipts':'0'}, 'liquidation comparator')
    eq(F(resolution['final']['old_claims_total_value'])-F('62'), F('7.8'), 'old creditor gain versus real avoided cost')
    eq(F(resolution['final']['old_senior_total_value'])+F('60')+F('0.2'), F('70'), 'baseline aggregate receipt identity')
    eq(F(results['dearer_bridge']['resolution']['final']['old_senior_total_value'])+F('60')+F('0.6'), F('70'), 'dearer bridge aggregate identity')
    # The general capital certificate: interval endpoints give necessity/sufficiency.
    for surviving, gap, rate, target in [(F(10),F(4),F(1,20),F(5)), (F(10),F(4),F(3,20),F(5)), (F(1),F(4),F(1,2),F(0))]:
        lower = target+gap*rate
        feasible = lower <= surviving
        if feasible:
            need(0 <= lower <= surviving and lower-gap*rate >= target, 'construct minimal feasible conversion')
        else:
            need(surviving-gap*rate < target, 'even largest conversion cannot meet target')


def invalid_api(run, base):
    invalid = [
        (['schema'], True), (['provenance'], ''), (['portfolio','initial_assets'], '0'),
        (['portfolio','capital'], '101'), (['portfolio','capital'], '-1'),
        (['portfolio','capital'], True), (['portfolio','capital'], 15.0),
        (['portfolio','capital'], 'NaN'), (['portfolio','capital'], '1e1'),
        (['portfolio','capital'], ' 15'), (['portfolio','capital'], '1/0'),
        (['portfolio','capital'], '1/1000001'), (['portfolio','capital'], '0'*41),
        (['portfolio','probabilities'], ['1/2','1/3']), (['portfolio','probabilities'], ['1']),
        (['portfolio','probabilities'], ['-1','2']), (['portfolio','probabilities'], ['1/2']*7),
        (['portfolio','options',0,'assets'], ['108']), (['portfolio','options',0,'assets'], ['-1','108']),
        (['portfolio','options',0,'id'], 'bad id'), (['portfolio','options',1,'id'], 'C'),
        (['portfolio','options'], []), (['portfolio','options',0,'reported_exposure'], '1000001'),
        (['portfolio','policies',0,'basis'], 'domestic_law'), (['portfolio','policies',0,'ratio'], '2'),
        (['portfolio','policies',0,'resource_cost'], '-1'), (['portfolio','policies',1,'id'], 'none'),
        (['portfolio','capture_weight'], '11'), (['portfolio','insurer_reserve'], '35'),
        (['conduct','care_cost'], '7'), (['conduct','care_harm_probability'], '1/2'),
        (['conduct','inspection_probability'], '2'), (['conduct','authority_budget'], '0'),
        (['conduct','pledged_funds'], '-1'), (['resolution','asset_loss'], '95'),
        (['resolution','asset_loss'], '19'), (['resolution','asset_loss'], '41'),
        (['resolution','cash'], '0'), (['resolution','conversion'], '11'),
        (['resolution','due_first'], '61'), (['resolution','lender_cash'], '3'),
        (['resolution','bridge_rate'], '2'), (['resolution','liquidation_cost'], '71')]
    for path, value in invalid:
        candidate = set_at(base, path, value)
        original = copy.deepcopy(candidate)
        try:
            run(candidate)
        except ValueError:
            pass
        else:
            raise ValueError('invalid API contract accepted: '+repr(path))
        COUNTS['invalid_data_rejections'] += 1
        eq(candidate, original, 'invalid API does not mutate '+repr(path))
    for candidate in (None, [], dict(base, extra='unknown'), {k:v for k,v in base.items() if k!='conduct'},
                      set_at(base, ['resolution'], dict(base['resolution'], unknown='1'))):
        try:
            run(candidate)
        except ValueError:
            pass
        else:
            raise ValueError('shape rejection missing')
        COUNTS['invalid_data_rejections'] += 1
        need(True, 'explicit object/domain rejection')
    # A zero-probability state still belongs to the declared guarantee support.
    candidate = set_at(base, ['portfolio','probabilities'], ['1','0'])
    candidate['portfolio']['insurer_reserve'] = '35'
    try:
        run(candidate)
    except ValueError:
        COUNTS['invalid_data_rejections'] += 1
        need(True, 'unfunded zero-probability supported state rejected')
    else:
        raise ValueError('guarantee support accidentally pruned')


class Manuscript(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids, self.sources, self.links, self.prompts, self.solutions = [], [], [], [], []
        self.worked = 0
        self.exercise = False
        self.headings, self.heading = [], None
        self.text = []
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if 'id' in a:
            self.ids.append(a['id'])
        if 'data-source' in a:
            self.sources.append(a['data-source'])
        if 'href' in a:
            self.links.append(a['href'])
        if 'worked' in a.get('class','').split():
            self.worked += 1
        if tag == 'ol' and 'exercises' in a.get('class','').split():
            self.exercise = True
        if tag == 'li' and self.exercise:
            self.prompts.append(a.get('id'))
        if 'data-solution-for' in a:
            self.solutions.append(a['data-solution-for'])
        if tag in ('h2','h3'):
            self.heading = []
    def handle_endtag(self, tag):
        if tag == 'ol':
            self.exercise = False
        if tag in ('h2','h3') and self.heading is not None:
            self.headings.append(''.join(self.heading)); self.heading = None
    def handle_data(self, data):
        self.text.append(data)
        if self.heading is not None:
            self.heading.append(data)


def bindings_and_structure():
    path = ROOT/'content/chapters/v11-c10.html'
    doc = Manuscript(); doc.feed(path.read_text())
    eq(doc.worked, 4, 'four complete worked containers')
    eq(doc.prompts, [PREFIX+'-e'+str(i) for i in range(1,11)], 'ten original prompt IDs')
    eq(doc.solutions, doc.prompts, 'every exact prompt has one paired solution')
    eq(len(doc.ids), len(set(doc.ids)), 'no duplicate manuscript IDs')
    need(any('Teach-back' in h for h in doc.headings), 'answered teaching heading')
    need(any('Delayed retention' in h for h in doc.headings), 'answered delayed check heading')
    sources = strict((ROOT/'content/reviews/v11-c10-sources.json').read_text())
    eq({p['id'] for p in sources['proposals']}, {'v11-c10-uk-fsa2012-enacted','v11-c10-fsb-resolution2024'}, 'two inspected new source routes')
    available = {p['id'] for p in sources['proposals']} | set(sources['reused_source_ids'])
    eq(set(doc.sources), available, 'every used source is scoped or proposed')
    for item in sources['proposals']:
        need(item['url'].startswith('https://') and bool(item['verification']) and bool(item['limits']), 'honest scoped source record')
    portable = [PREFIX+suffix for suffix in ('-inputs.json','-analysis.py','-output.json','-manifest.json','-README.txt')]
    eq(sorted(h for h in doc.links if h in portable), sorted(portable), 'five flat reader attachment links')
    need(not any(h.startswith('projects/') for h in doc.links), 'no nonexistent projects link directory')
    text = ' '.join(''.join(doc.text).split())
    for marker in ('118.75', '115/14≈8.214286', '4/43≈.0930233', '6.875,5.3,6.8', '5.2', '7.8', '19 December 2012', '25 April 2024', '17 April 2026', 'not inspected those commencement orders'):
        need(marker in text, 'printed answer/date/scope retained '+marker)
    manifest = strict((PROJECT/(PREFIX+'-manifest.json')).read_text())
    expected = set(portable)-{PREFIX+'-manifest.json'}
    eq({row['file'] for row in manifest['files']}, expected, 'manifest binds exact four payloads')
    eq(len(manifest['files']), 4, 'manifest no duplicate rows')
    for row in manifest['files']:
        p = PROJECT/row['file']
        eq((p.stat().st_size,digest(p)), (row['bytes'],row['sha256']), 'manifest bytes '+row['file'])
    author = strict((ROOT/'content/reviews/v11-c10-author.json').read_text())
    expected = set(OWNED)-{'content/reviews/v11-c10-author.json'}
    eq({r['path'] for r in author['artifact_bindings']}, expected, 'author binds all eight nonself paths')
    eq(len(author['artifact_bindings']), 8, 'author no duplicate binding rows')
    for row in author['artifact_bindings']:
        p = ROOT/row['path']
        eq((p.stat().st_size,digest(p)), (row['bytes'],row['sha256']), 'author bytes '+row['path'])
    eq((len(author['worked_audit']),len(author['exercise_audit'])), (4,10), 'complete author manual worked/prompt audits')
    eq(author['review'], dict.fromkeys(('arithmetic','reasoning','solutions','sources','instruction','structure'), True), 'author review fields complete')
    need('pending' in author['status'], 'separate review remains explicit')


def portable_cli(base, expected):
    with tempfile.TemporaryDirectory(prefix='v11-c10-cli-') as temporary:
        folder = Path(temporary)
        model, source = folder/MODEL.name, folder/INPUT.name
        shutil.copy2(MODEL, model); shutil.copy2(INPUT, source)
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
        for optimized in (False, True):
            command = [sys.executable]+(['-O'] if optimized else [])+[str(model)]
            def execute(args):
                return subprocess.run(command+args, cwd='/', env=env, text=True, capture_output=True, timeout=15)
            result = execute([])
            eq((result.returncode,result.stdout,result.stderr), (0,'',''), 'portable quiet default CLI mode '+str(optimized))
            eq(strict((folder/(PREFIX+'-output.json')).read_text()), expected, 'portable sibling input/output independent of cwd')
            output = folder/'result.json'
            result = execute(['--input',str(source),'--output',str(output)])
            eq((result.returncode,result.stdout,result.stderr), (0,'',''), 'output-file success is quiet')
            eq(strict(output.read_text()), expected, 'CLI full baseline')
            nested = folder/'nested'; nested.mkdir(exist_ok=True)
            for protected in (source,model):
                for kind in ('direct','resolved','symbolic','hard'):
                    candidate = protected if kind == 'direct' else nested/'..'/protected.name if kind == 'resolved' else folder/(protected.name+'.'+kind)
                    if kind in ('symbolic','hard'):
                        if candidate.exists() or candidate.is_symlink(): candidate.unlink()
                        if kind == 'symbolic': candidate.symlink_to(protected)
                        else: os.link(protected,candidate)
                    before = source.read_bytes(), model.read_bytes()
                    result = execute(['--input',str(source),'--output',str(candidate)])
                    need(result.returncode != 0 and result.stdout == '' and result.stderr.startswith('error:'), 'reject protected output '+kind)
                    eq((source.read_bytes(),model.read_bytes()), before, 'alias rejection preserves protected bytes')
                    COUNTS['protected_output_rejections'] += 1
                    if kind in ('symbolic','hard'): candidate.unlink()
            bad_payloads = [b'{"schema":1,"schema":2}',
                            source.read_bytes().replace(b'"capital": "15"',b'"capital": NaN'),
                            json.dumps(set_at(base,['schema'],True)).encode(),
                            b' ' * 262145, b'\xff']
            for payload in bad_payloads:
                invalid = folder/'invalid.json'; invalid.write_bytes(payload)
                output.write_text('PRESERVE\n')
                result = execute(['--input',str(invalid),'--output',str(output)])
                need(result.returncode != 0 and result.stdout == '' and result.stderr.startswith('error:'), 'invalid CLI data rejected')
                eq(output.read_text(),'PRESERVE\n','invalid input preserves prior output')
                COUNTS['invalid_data_rejections'] += 1
    return {'normal_and_optimized_cli': True, 'independent_working_directory': True,
            'output_guards': 'direct, resolved, symbolic and hard aliases of input and implementation in both modes'}


def check():
    global COUNTS
    COUNTS = {'comparisons':0,'cases':0,'financial_interventions':0,'invalid_data_rejections':0,'protected_output_rejections':0}
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
        namespace = runpy.run_path(str(MODEL))
    eq(buffer.getvalue(),'','quiet model import')
    base = strict(INPUT.read_text())
    original = case(namespace['run'],base,'baseline')
    eq(original,strict((PROJECT/(PREFIX+'-output.json')).read_text()),'saved output after independent full baseline audit')
    results = interventions(namespace['run'],base,original)
    numeric_manuscript(original,results)
    invalid_api(namespace['run'],base)
    portable = portable_cli(base,original)
    bindings_and_structure()
    summary = {'chapter':PREFIX,'status':'passed',**COUNTS,'worked_examples':4,'solved_exercises':10,
               'independent_methods':['statewise priority and stakeholder resource identities',
                   'pairwise feasible choice comparisons preserving all ties',
                   'Frechet endpoint inspection/harm joint laws',
                   'ordered loss absorption and additive dated journal vectors',
                   'capital interval feasibility certificates and printed numeric boundaries'],
               'portable':portable,
               'limits':'Original bounded author validation; no empirical policy/capture conclusion, current national-law finding, human academic certification or coordinator acceptance.'}
    json.dumps(summary,allow_nan=False)
    return summary


if __name__ == '__main__':
    print(json.dumps(check(),indent=2,allow_nan=False))
