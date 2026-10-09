"""Independent C10 peer: endowed transfers, incentives and dated resolution cash.

Only the author's public run(data) is used. Numerical expectations below come
from the stated contracts and transaction vectors, not from author helpers.
"""
import argparse
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
from fractions import Fraction as F
import hashlib
from html.parser import HTMLParser
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
AUTHOR_PATHS = [
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
PEER_CHECKER = 'scripts/check_v11_c10_peer.py'


class Markup(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids, self.prompts, self.answers, self.links = [], [], [], []
        self.sources = set()
        self.worked = 0
        self.lists = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if 'id' in a:
            self.ids.append(a['id'])
        if 'worked' in a.get('class', '').split():
            self.worked += 1
        if tag == 'ol':
            self.lists.append('exercises' in a.get('class', '').split())
        if tag == 'li' and self.lists and self.lists[-1]:
            self.prompts.append(a.get('id'))
        if 'data-solution-for' in a:
            self.answers.append(a['data-solution-for'])
        if 'href' in a:
            self.links.append(a['href'])
        if 'data-source' in a:
            self.sources.add(a['data-source'])

    def handle_endtag(self, tag):
        if tag == 'ol' and self.lists:
            self.lists.pop()


def check(root=None):
    root = Path(root) if root is not None else Path(__file__).resolve().parents[1]
    project = root / 'content/projects'
    counts = dict(comparisons=0, financial_interventions=0, portfolio_states=0,
                  resolution_rows=0, conduct_joint_tables=0, invalid_api_cases=0,
                  invalid_cli_cases=0, protected_alias_attempts=0,
                  portable_model_runs=0, author_files_bound=0)

    def need(ok, label):
        counts['comparisons'] += 1
        if not ok:
            raise RuntimeError(label)

    def eq(actual, expected, label):
        need(actual == expected, label + ': ' + repr(actual) + ' != ' + repr(expected))

    def num(actual, expected, label):
        eq(F(actual), F(expected), label)

    target = project / 'v11-c10-analysis.py'
    spec = importlib.util.spec_from_file_location('c10_peer_target', target)
    model = importlib.util.module_from_spec(spec)
    capture = io.StringIO()
    with redirect_stdout(capture), redirect_stderr(capture):
        spec.loader.exec_module(model)
    eq(capture.getvalue(), '', 'quiet import')
    data = json.loads((project / 'v11-c10-inputs.json').read_text())

    def run(d):
        before, silent = deepcopy(d), io.StringIO()
        with redirect_stdout(silent), redirect_stderr(silent):
            answer = model.run(d)
        eq(silent.getvalue(), '', 'quiet public API')
        eq(d, before, 'nonmutating public API')
        json.dumps(answer, allow_nan=False)
        return answer

    result = run(data)
    eq(result, json.loads((project / 'v11-c10-output.json').read_text()), 'saved exact output')

    def portfolio(d, output):
        p = d['portfolio']
        a0, capital, reserve = map(F, (p['initial_assets'], p['capital'], p['insurer_reserve']))
        debt = a0-capital
        probabilities = list(map(F, p['probabilities']))
        num(output['initial_deposits'], debt, 'funding replaces deposits')
        eq([x['id'] for x in output['options']], [x['id'] for x in p['options']], 'option inventory')
        profits, welfare = {}, {}
        for contract, row in zip(p['options'], output['options']):
            equity_mean = F(0)
            paid_mean = F(0)
            assets_mean = F(0)
            default_mass = F(0)
            eq(len(row['states']), len(probabilities), 'state inventory')
            for probability, raw_asset, state in zip(probabilities, contract['assets'], row['states']):
                assets = F(raw_asset)
                # Allocate the asset pool to deposits first, then its residual.
                bank_payment = min(debt, assets)
                owner_payment = assets-bank_payment
                insurance = debt-bank_payment
                harm = F(p['harm_if_default']) if insurance > 0 else F(0)
                expected = dict(probability=probability, assets=assets,
                                deposit_from_bank=bank_payment, insurance_payment=insurance,
                                deposit_total=debt, equity_residual=owner_payment,
                                insurer_closing_reserve=reserve-insurance, real_harm=harm)
                for key, value in expected.items():
                    num(state[key], value, 'state ' + key)
                eq(state['default'], insurance > 0, 'strict default boundary')
                need(reserve-insurance >= 0, 'endowed guarantor covers state')
                num(F(state['equity_residual'])-F(state['insurance_payment']), assets-debt, 'signed transfer identity')
                num(F(state['deposit_total'])+F(state['equity_residual'])+F(state['insurer_closing_reserve']),
                    assets+reserve, 'all endowed financial resources conserved')
                equity_mean += probability*owner_payment
                paid_mean += probability*insurance
                assets_mean += probability*assets
                default_mass += probability*(insurance > 0)
                counts['portfolio_states'] += 1
            profit = equity_mean-capital
            surplus = assets_mean-a0-default_mass*F(p['harm_if_default'])
            profits[contract['id']], welfare[contract['id']] = profit, surplus
            expected = dict(expected_assets=assets_mean, asset_gain=assets_mean-a0,
                            private_profit=profit, expected_insurance=paid_mean,
                            default_probability=default_mass,
                            expected_real_harm=default_mass*F(p['harm_if_default']),
                            welfare_before_policy_cost=surplus)
            for key, value in expected.items():
                num(row[key], value, 'expectation ' + key)
            eq(profit-paid_mean, assets_mean-a0, 'profit less transfer equals asset gain')
        eq([x['id'] for x in output['policies']], [x['id'] for x in p['policies']], 'policy inventory')
        scores = {}
        ambiguous = False
        for policy, row in zip(p['policies'], output['policies']):
            eligible = []
            for option in p['options']:
                required = F(policy['ratio'])*F(option[policy['basis']+'_exposure'])
                num(row['required_capital'][option['id']], required, 'screen requirement')
                if required <= capital:
                    eligible.append(option['id'])
            # Pairwise deviations are the definition of a best response.
            choices = [x for x in eligible if all(profits[x] >= profits[y] for y in eligible)]
            eq(row['feasible'], eligible, 'screen feasibility')
            eq(row['best_responses'], choices, 'all private deviations')
            eq(row['status'], 'feasible' if eligible else 'no feasible option', 'empty menu scope')
            eq([x['choice'] for x in row['outcomes']], choices, 'unselected private ties retained')
            policy_scores = []
            for outcome in row['outcomes']:
                choice = outcome['choice']
                net = welfare[choice]-F(policy['resource_cost'])
                score = net+F(p['capture_weight'])*profits[choice]
                num(outcome['private_profit'], profits[choice], 'screen does not change private payoff')
                num(outcome['welfare'], net, 'outside real implementation cost')
                num(outcome['score'], score, 'extra incumbent weight')
                policy_scores.append(score)
            if policy_scores:
                scores[policy['id']] = policy_scores[0]
                ambiguous |= len(set(policy_scores)) > 1
        winners = None if ambiguous else [x for x in scores if all(scores[x] >= scores[y] for y in scores)]
        eq(output['score_maximizers'], winners, 'no hidden policy tie selection')
        eq(output['ranking_status'], 'tie-dependent; inspect all outcomes' if ambiguous else
           'determinate over feasible policies', 'ranking scope')

    def conduct(d, output):
        c = {k: F(v) for k, v in d['conduct'].items()}
        collectible = min(c['fine'], c['pledged_funds'])
        a = c['inspection_probability']
        num(output['collectible_fine'], collectible, 'funded fine cap')
        num(output['deterrence_margin'], a*collectible-c['care_cost'], 'procedural incentive margin')
        seller_means = {}
        eq([x['id'] for x in output['actions']], ['care', 'shortcut'], 'action inventory')
        for row in output['actions']:
            action = row['id']
            prob = c[action+'_harm_probability']
            cost = c['care_cost'] if action == 'care' else F(0)
            # Extremal harm/inspection couplings plus their independent coupling.
            # The result must not accidentally multiply the fine by harm probability.
            for joint in sorted({max(F(0), prob+a-1), prob*a, min(prob, a)}):
                masses = {(1, 1): joint, (1, 0): prob-joint,
                          (0, 1): a-joint, (0, 0): 1-prob-a+joint}
                eq(sum(masses.values()), F(1), 'joint state mass')
                need(min(masses.values()) >= 0, 'joint state nonnegativity')
                seller = buyer = authority = F(0)
                for (harmed, inspected), mass in masses.items():
                    fine = collectible if inspected and action == 'shortcut' else F(0)
                    s = c['fee']-cost-fine
                    b = c['gross_benefit']-c['fee']-harmed*c['harm']
                    au = fine-inspected*c['inspection_cost']
                    eq(s+b+au, c['gross_benefit']-cost-harmed*c['harm']-inspected*c['inspection_cost'],
                       'state fine and fee cancel')
                    seller += mass*s
                    buyer += mass*b
                    authority += mass*au
                for key, value in {'seller_profit': seller, 'buyer_net': buyer, 'authority_net': authority,
                                   'welfare': seller+buyer+authority}.items():
                    num(row[key], value, 'joint expectation ' + key)
                counts['conduct_joint_tables'] += 1
                seller_means[action] = seller
            expected = dict(expected_fine=F(0) if action == 'care' else a*collectible,
                            expected_harm=prob*c['harm'], expected_real_care_cost=cost,
                            expected_inspection_cost=a*c['inspection_cost'])
            for key, value in expected.items():
                num(row[key], value, 'conduct ' + key)
        choices = [x for x in seller_means if all(seller_means[x] >= seller_means[y] for y in seller_means)]
        eq(output['best_responses'], choices, 'weak versus strict deterrence')

    def resolution(d, output):
        r = {k: F(v) for k, v in d['resolution'].items()}
        c, long, dep, sen, jun = [r[k] for k in ('cash', 'long_assets', 'deposits', 'senior', 'junior')]
        initial = c+long-dep-sen-jun
        remaining = c+long-r['asset_loss']
        surviving = remaining-dep
        x = r['conversion']
        gap = max(F(0), r['due_first']-c)
        interest = gap*r['bridge_rate']
        funded = gap <= r['bridge_capacity']
        solvent = x >= interest
        expected = dict(original_equity=initial, remaining_assets=remaining,
                        surviving_senior_before_conversion=surviving, first_cash_gap=gap,
                        minimum_external_advance=gap, unfunded_first_gap=max(F(0), gap-r['bridge_capacity']),
                        bridge_interest_if_funded=interest, capital_after_conversion=x,
                        capital_after_interest_if_funded=x-interest)
        for key, value in expected.items():
            num(output[key], value, 'resolution ' + key)
        eq(output['first_cutoff_funded'], funded, 'cash feasibility')
        eq(output['terminal_claims_funded_if_bridge'], solvent, 'terminal solvency conditional on bridge')
        eq(output['immediate_capital_pass'], x >= r['capital_floor'], 'immediate capital')
        eq(output['continuing_capital_pass'], funded and x-interest >= r['capital_floor'], 'continuing capital')
        absorption = (initial, jun, sen-surviving)
        eq(sum(absorption), r['asset_loss'], 'loss allocated once')
        for key, value in zip(('old_equity', 'junior', 'senior'), absorption):
            num(output['loss_absorption'][key], value, 'loss priority ' + key)

        fields = ('cash', 'long_assets', 'deposits', 'senior', 'junior', 'bridge', 'equity')
        vec = [c, long, dep, sen, jun, F(0), initial]
        expected_rows = [('opening', vec[:])]

        def transact(stage, moves):
            for key, amount in moves.items():
                vec[fields.index(key)] += amount
            expected_rows.append((stage, vec[:]))

        transact('after_asset_loss', dict(long_assets=-r['asset_loss'], equity=-r['asset_loss']))
        transact('after_write_down', dict(senior=surviving-sen, junior=-jun, equity=r['asset_loss']-initial))
        transact('after_conversion', dict(senior=-x, equity=x))
        if funded:
            transact('after_bridge', dict(cash=gap, bridge=gap))
            transact('after_first_payment', dict(cash=-r['due_first'], deposits=-r['due_first']))
            transact('maturity_before_payments', dict(cash=long-r['asset_loss'], long_assets=-(long-r['asset_loss']),
                                                     bridge=interest, equity=-interest))
            if solvent:
                liabilities = sum(vec[2:6])
                transact('after_final_payments', dict(cash=-liabilities, deposits=-vec[2], senior=-vec[3],
                                                      junior=-vec[4], bridge=-vec[5]))
        eq([row['stage'] for row in output['snapshots']], [stage for stage, _ in expected_rows], 'dated stopping rule')
        for actual, (stage, values) in zip(output['snapshots'], expected_rows):
            for key, value in zip(fields, values):
                num(actual[key], value, stage + ' ' + key)
            eq(sum(F(actual[k]) for k in fields[:2]), sum(F(actual[k]) for k in fields[2:]), 'journal balance ' + stage)
            counts['resolution_rows'] += 1
        status = ('first cutoff unfunded; no payment continuation assumed' if not funded else
                  'terminal claims underfunded; no final allocation assumed' if not solvent else 'funded continuation')
        eq(output['status'], status, 'conditional cash continuation')
        if funded and solvent:
            final = output['final']
            exp = dict(cash_and_equity=x-interest, deposit_receipts_total=dep,
                       old_senior_debt_receipts=surviving-x, old_senior_new_equity_value=x-interest,
                       old_senior_total_value=surviving-interest, lender_repayment=gap+interest,
                       lender_net_interest=interest, old_claims_total_value=dep+surviving-interest)
            for key, value in exp.items():
                num(final[key], value, 'terminal allocation ' + key)
            num(F(final['old_claims_total_value'])+F(final['lender_net_interest']), remaining, 'returned principal is not income')
        else:
            eq(output['final'], None, 'unsupported terminal allocation absent')
        # Independently allocate the smaller immediate liquidation pool by priority.
        pool = remaining-r['liquidation_cost']
        num(output['liquidation']['net_assets'], pool, 'real liquidation resource loss')
        for claim, key in ((dep, 'deposit_receipts'), (sen, 'senior_receipts'),
                           (jun, 'junior_receipts'), (initial, 'old_equity_receipts')):
            paid = min(pool, claim)
            num(output['liquidation'][key], paid, 'liquidation priority ' + key)
            pool -= paid
        eq(pool, 0, 'liquidation pool exhausted in restricted loss region')

    portfolio(data, result['portfolio'])
    conduct(data, result['conduct'])
    resolution(data, result['resolution'])

    def intervention(section, changes):
        d = deepcopy(data)
        for key, value in changes.items():
            d[section][key] = deepcopy(value)
        out = run(d)
        {'portfolio': portfolio, 'conduct': conduct, 'resolution': resolution}[section](d, out[section])
        counts['financial_interventions'] += 1
        return out[section]

    # Exercise transfers and exact decision boundaries, with no broad parameter fuzzing.
    for capital, profit, insurance, welfare in [
            ('20', ['8', '35/2', '67/4'], ['0', '15/2', '31/4'], ['8', '5', '4']),
            ('50', ['8', '10', '37/4'], ['0', '0', '1/4'], ['8', '10', '4'])]:
        out = intervention('portfolio', {'capital': capital})
        for key, values in [('private_profit', profit), ('expected_insurance', insurance),
                            ('welfare_before_policy_cost', welfare)]:
            eq([r[key] for r in out['options']], values, 'printed financing transfer ' + key)
        eq([r['best_responses'] for r in out['policies']], [['H']]*3, 'funding and perimeter interaction')
    for harm, winners in [('16', ['none', 'broad']), ('15', ['none'])]:
        eq(intervention('portfolio', {'harm_if_default': harm})['score_maximizers'], winners, 'external-harm threshold')
    for weight, winners in [('4/43', ['none', 'broad']), ('1/10', ['none'])]:
        out = intervention('portfolio', {'capture_weight': weight})
        eq(out['score_maximizers'], winners, 'incumbent-weight threshold')
        if weight == '1/10':
            eq([p['outcomes'][0]['score'] for p in out['policies']], ['55/8', '53/10', '34/5'], 'printed score transfer')
    options = deepcopy(data['portfolio']['options'])
    options[0]['assets'] = ['475/4', '475/4']
    tied = intervention('portfolio', {'options': options})
    eq(tied['policies'][0]['best_responses'], ['C', 'H'], 'private tie exercise')
    eq(tied['score_maximizers'], None, 'honest social tie reporting')
    policies = [{'id': 'blocked', 'basis': 'lookthrough', 'ratio': '1', 'resource_cost': '0'}]
    eq(intervention('portfolio', {'policies': policies})['score_maximizers'], [], 'empty regulatory menu')

    for probability, expected in [('1/10', ['shortcut']), ('2/7', ['care', 'shortcut']), ('1/5', ['shortcut'])]:
        out = intervention('conduct', {'fine': '100', 'pledged_funds': '7', 'inspection_probability': probability})
        eq(out['best_responses'], expected, 'collectibility and inspection boundary')
        if probability == '2/7':
            num(out['actions'][0]['welfare'], F(115, 14), 'printed boundary care surplus')
    no_inspection = intervention('conduct', {'inspection_probability': '0', 'authority_budget': '0'})
    eq(no_inspection['best_responses'], ['shortcut'], 'zero inspection cannot deter positive cost')
    # Explicit counterfactual, not an extra feature of the target's care-never-fined model.
    false_sanction_probability = F(1, 2)
    care_profit = F(6)-2-F(1, 4)*false_sanction_probability*10
    shortcut_profit = F(6)-F(1, 4)*10
    need(shortcut_profit > care_profit, 'false sanctions can reverse baseline deterrence')
    eq(care_profit-shortcut_profit, F(1, 4)*(1-false_sanction_probability)*10-2, 'false sanction incentive difference')

    fixed = intervention('resolution', {'conversion': '26/5'})
    eq(fixed['continuing_capital_pass'], True, 'minimum continuing conversion')
    num(fixed['final']['old_senior_total_value'], F(49, 5), 'conversion preserves senior class value')
    for conversion in ['5', '10']:
        out = intervention('resolution', {'bridge_capacity': '3', 'conversion': conversion})
        num(out['unfunded_first_gap'], 1, 'conversion cannot fill dated cash gap')
        eq(len(out['snapshots']), 4, 'no fictitious partial-funded continuation')
    costly = intervention('resolution', {'bridge_rate': '3/20', 'conversion': '28/5'})
    num(costly['final']['cash_and_equity'], 5, '15 percent bridge capital floor')
    num(costly['final']['old_senior_debt_receipts'], F(22, 5), '15 percent bridge senior debt')
    num(costly['final']['old_senior_total_value'], F(47, 5), '15 percent bridge senior value')
    out = intervention('resolution', {'bridge_rate': '3/20', 'conversion': '1/5'})
    num(out['capital_after_interest_if_funded'], F(-2, 5), 'funded early but insolvent terminal')
    eq(len(out['snapshots']), 7, 'no invented secondary waterfall')
    out = intervention('resolution', {'due_first': '6', 'bridge_capacity': '0', 'lender_cash': '0'})
    num(out['first_cash_gap'], 0, 'cash equality needs no loan')
    eq(out['continuing_capital_pass'], True, 'no bridge interest when no borrowing')
    out = intervention('resolution', {'asset_loss': '40', 'conversion': '0', 'capital_floor': '0', 'bridge_rate': '0'})
    num(out['surviving_senior_before_conversion'], 0, 'loss-region deposit boundary')
    eq(out['continuing_capital_pass'], True, 'zero surplus zero floor boundary')
    # Necessity/sufficiency and minimality on an exact small conversion lattice.
    threshold = F(5)+F(4)*F(3, 20)
    need(threshold <= 10, 'capital repair fits surviving senior claim')
    eq(threshold, F(28, 5), 'closed-form minimum conversion')
    need(threshold-F(1, 100)-F(4)*F(3, 20) < 5, 'one cent less fails capital floor')
    eq(F(60)+F(47, 5)+F(3, 5), F(70), 'all original resources including net lender interest')

    bad = []
    def invalid(path, value):
        d = deepcopy(data)
        obj = d
        for key in path[:-1]:
            obj = obj[key]
        obj[path[-1]] = value
        bad.append(d)

    invalid(['schema'], True)
    invalid(['provenance'], '')
    invalid(['portfolio', 'capital'], 15)
    invalid(['portfolio', 'capital'], '1e1')
    invalid(['portfolio', 'capital'], ' 15')
    invalid(['portfolio', 'capital'], '1/0')
    invalid(['portfolio', 'capital'], '1/1000001')
    invalid(['portfolio', 'capital'], '101')
    invalid(['portfolio', 'probabilities'], ['1/2', '1/3'])
    invalid(['portfolio', 'probabilities'], ['1'])
    invalid(['portfolio', 'options', 0, 'assets'], ['108'])
    invalid(['portfolio', 'options', 1, 'id'], 'C')
    invalid(['portfolio', 'policies', 1, 'basis'], 'economic')
    invalid(['portfolio', 'policies', 1, 'ratio'], '101/100')
    invalid(['portfolio', 'capture_weight'], '11')
    invalid(['portfolio', 'insurer_reserve'], '35')
    zero_mass = deepcopy(data)
    zero_mass['portfolio']['probabilities'] = ['1', '0']
    zero_mass['portfolio']['insurer_reserve'] = '35'
    bad.append(zero_mass)
    invalid(['conduct', 'care_cost'], '7')
    invalid(['conduct', 'care_harm_probability'], '1/2')
    invalid(['conduct', 'inspection_probability'], '101/100')
    invalid(['conduct', 'authority_budget'], '1/4')
    invalid(['resolution', 'deposits'], '101')
    invalid(['resolution', 'asset_loss'], '95')
    invalid(['resolution', 'asset_loss'], '19')
    invalid(['resolution', 'asset_loss'], '41')
    invalid(['resolution', 'conversion'], '11')
    invalid(['resolution', 'due_first'], '61')
    invalid(['resolution', 'lender_cash'], '3')
    invalid(['resolution', 'bridge_rate'], '101/100')
    invalid(['resolution', 'liquidation_cost'], '71')
    extra = deepcopy(data)
    extra['conduct']['care_false_sanction_probability'] = '1/2'
    bad.append(extra)
    for d in bad:
        before, silent, rejected = deepcopy(d), io.StringIO(), False
        with redirect_stdout(silent), redirect_stderr(silent):
            try:
                model.run(d)
            except (ValueError, TypeError):
                rejected = True
        need(rejected, 'invalid public contract rejected')
        eq(d, before, 'invalid input preserved')
        eq(silent.getvalue(), '', 'invalid API quiet')
        counts['invalid_api_cases'] += 1

    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    with tempfile.TemporaryDirectory(prefix='v11-c10-peer-') as directory:
        temp = Path(directory)
        implementation, inputs = temp / target.name, temp / 'v11-c10-inputs.json'
        shutil.copy2(target, implementation)
        shutil.copy2(project / inputs.name, inputs)
        sentinel = b'preserve this existing destination\n'
        for flags in ([], ['-O']):
            prefix = [sys.executable]+flags+[str(implementation)]
            for explicit in (False, True):
                destination = temp / ('explicit.json' if explicit else 'v11-c10-output.json')
                args = ['--input', str(inputs), '--output', str(destination)] if explicit else []
                proc = subprocess.run(prefix+args, cwd=temp.parent, env=env, capture_output=True, timeout=20)
                eq((proc.returncode, proc.stdout, proc.stderr), (0, b'', b''), 'quiet portable CLI')
                eq(json.loads(destination.read_text()), result, 'portable CLI exact result')
                counts['portable_model_runs'] += 1
            malformed = [b'{"schema":1,"schema":1}', b'{"schema":NaN}', b'{"schema":Infinity}',
                         b'\xff', b'{', b' '*262145]
            destination = temp / 'sentinel-output.json'
            for raw in malformed:
                source = temp / 'invalid.json'
                source.write_bytes(raw)
                destination.write_bytes(sentinel)
                proc = subprocess.run(prefix+['--input', str(source), '--output', str(destination)],
                                      cwd=temp.parent, env=env, capture_output=True, timeout=20)
                eq(proc.returncode, 2, 'invalid CLI status')
                eq(proc.stdout, b'', 'invalid CLI no stdout')
                need(proc.stderr.startswith(b'error: '), 'invalid CLI useful diagnostic')
                eq(destination.read_bytes(), sentinel, 'invalid CLI preserves output')
                counts['invalid_cli_cases'] += 1
            for protected in (inputs, implementation):
                original_input, original_model = inputs.read_bytes(), implementation.read_bytes()
                pad = temp / 'subdir'
                pad.mkdir(exist_ok=True)
                symbolic = temp / ('symbolic-'+protected.name)
                hard = temp / ('hard-'+protected.name)
                if symbolic.is_symlink():
                    symbolic.unlink()
                if hard.exists():
                    hard.unlink()
                symbolic.symlink_to(protected)
                os.link(protected, hard)
                for alias in (protected, pad / '..' / protected.name, symbolic, hard):
                    proc = subprocess.run(prefix+['--input', str(inputs), '--output', str(alias)],
                                          cwd=temp.parent, env=env, capture_output=True, timeout=20)
                    eq(proc.returncode, 2, 'protected alias rejection')
                    eq(proc.stdout, b'', 'protected alias quiet stdout')
                    need(b'aliases input or implementation' in proc.stderr, 'specific alias diagnostic')
                    eq(inputs.read_bytes(), original_input, 'input bytes preserved')
                    eq(implementation.read_bytes(), original_model, 'implementation bytes preserved')
                    counts['protected_alias_attempts'] += 1

    markup = Markup()
    manuscript = (root / AUTHOR_PATHS[0]).read_text()
    markup.feed(manuscript)
    eq(len(markup.ids), len(set(markup.ids)), 'unique HTML ids')
    eq(markup.worked, 4, 'four complete worked containers')
    eq(markup.prompts, ['v11-c10-e'+str(i) for i in range(1, 11)], 'all exact exercise prompts')
    eq(markup.answers, markup.prompts, 'all exact solution pairs')
    for name in ('inputs.json', 'analysis.py', 'output.json', 'manifest.json', 'README.txt'):
        need('v11-c10-'+name in markup.links, 'flat reader attachment ' + name)
    eq(markup.sources, {'v11-c10-uk-fsa2012-enacted', 'v11-c10-fsb-resolution2024',
                        'v10-c12-fed-letter', 'v10-c12-fed-guidance', 'v11-c02-bcbs-liquidity2008'}, 'scoped source IDs')
    need('Delayed retention' in manuscript and 'Model answer' in manuscript, 'answered retention and teach-back')

    def bindings(rows, expected, label):
        eq([x['path'] for x in rows], expected, label + ' exact ordered inventory')
        eq(len({x['path'] for x in rows}), len(rows), label + ' unique bindings')
        for item in rows:
            payload = (root / item['path']).read_bytes()
            eq(len(payload), item['bytes'], label + ' size ' + item['path'])
            eq(hashlib.sha256(payload).hexdigest(), item['sha256'], label + ' hash ' + item['path'])

    author = json.loads((root / 'content/reviews/v11-c10-author.json').read_text())
    bindings(author['artifact_bindings'], [p for p in AUTHOR_PATHS if not p.endswith('-author.json')], 'author nonself')
    manifest = json.loads((project / 'v11-c10-manifest.json').read_text())
    files = manifest['files']
    eq([x['file'] for x in files], ['v11-c10-'+suffix for suffix in ('inputs.json', 'analysis.py', 'output.json', 'README.txt')], 'manifest four payloads')
    bindings([dict(path='content/projects/'+r['file'], bytes=r['bytes'], sha256=r['sha256']) for r in files],
             ['content/projects/'+r['file'] for r in files], 'payload manifest')
    peer = json.loads((root / 'content/reviews/v11-c10-peer.json').read_text())
    bindings(peer['artifact_bindings'], AUTHOR_PATHS+[PEER_CHECKER], 'peer frozen package')
    counts['author_files_bound'] = len(AUTHOR_PATHS)
    return dict(chapter='v11-c10', status='passed', **counts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path)
    args = parser.parse_args()
    print(json.dumps(check(args.root), sort_keys=True))


if __name__ == '__main__':
    main()
