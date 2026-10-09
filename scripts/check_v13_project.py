"""Quiet, independent nine-file audit of the V13 theory project.

The numerical oracle constructs actual payoff/transition laws, uses the value
difference equation rather than the reader's 2x2 inverse, and uses determinant
expansion/Cramer's rule rather than the reader's row reduction for graph cases.
Universal incentive and singular-family proofs are separately read in full.
"""
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
from fractions import Fraction as Q
from hashlib import sha256
from html.parser import HTMLParser
from io import StringIO
from itertools import permutations, product
import json
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile

HTML = 'content/assessments/parts/v13-project.html'
INPUT = 'content/projects/v13-assessment-inputs.json'
MODEL = 'content/projects/v13-assessment-analysis.py'
OUTPUT = 'content/projects/v13-assessment-output.json'
MANIFEST = 'content/projects/v13-assessment-manifest.json'
README = 'content/projects/v13-assessment-README.txt'
CHECKER = 'scripts/check_v13_project.py'
AUTHOR = 'content/reviews/v13-project-author.json'
SOURCES = 'content/reviews/v13-project-sources.json'
FILES = (HTML, INPUT, MODEL, OUTPUT, MANIFEST, README, CHECKER, AUTHOR, SOURCES)
READER = (INPUT, MODEL, OUTPUT, MANIFEST, README)
SOURCE_URLS = {
    'v13-c06-manea-noncoop2017': 'https://ocw.mit.edu/courses/14-126-game-theory-spring-2016/a4d0a3949ab29c2a2f55442a9723d205_MIT14_126S16_noncoop.pdf',
    'v13-c09-stole-contracts1999': 'https://ocw.mit.edu/courses/14-124-microeconomic-theory-iv-spring-2017/be21e9cc762231c50ab42bbf35ead5db_MIT14_124S17_LecNote1_2.pdf',
    'v13-c11-bkd-networks2014': 'https://sites.duke.edu/rachelkranton/files/2016/09/strategic-interaction-and-networks-aer.pdf',
}


def need(test, reason):
    if not test:
        raise ValueError(reason)


def read_json(text):
    def pairs(items):
        out = {}
        for k, v in items:
            need(k not in out, 'duplicate JSON key'); out[k] = v
        return out
    def bad(_): raise ValueError('noninteger JSON token')
    return json.loads(text, object_pairs_hook=pairs, parse_float=bad, parse_constant=bad)


def encoded(x):
    if isinstance(x, Q): return str(x)
    if type(x) in (tuple, list): return [encoded(v) for v in x]
    if type(x) is dict: return {k: encoded(v) for k, v in x.items()}
    return x


def printed(x):
    if type(x) in (tuple, list): return '('+','.join(printed(v) for v in x)+')'
    return str(x)


def norm(x): return ''.join(x.replace('−', '-').split())


class Reader(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []; self.ids = set(); self.tasks = {}; self.answers = set(); self.domains = {}
        self.inputs = {}; self.results = {}; self.capture = []; self.sources = {}; self.downloads = set()

    def handle_starttag(self, tag, attrs):
        a = dict(attrs); need(len(a) == len(attrs), 'duplicate HTML attribute')
        need(tag not in ('h1', 'script', 'iframe', 'object'), 'unsupported project reader element')
        if 'id' in a:
            need(a['id'] not in self.ids and (a['id'] == 'project' or a['id'].startswith('v13-project-')), 'unique scoped ID')
            self.ids.add(a['id'])
        if 'data-points' in a:
            need(a['data-points'].isdigit(), 'integer points')
            if tag == 'li': self.tasks[a['id']] = int(a['data-points'])
            elif tag == 'tr': self.domains[a['data-domain']] = int(a['data-points'])
            else: raise ValueError('unexpected points element')
        if 'data-solution-for' in a:
            key = a['data-solution-for']
            need(key not in self.answers and any(t == 'details' and 'solutions' in z.get('class', '').split() for t, z in self.stack), 'unique disclosed solution')
            self.answers.add(key)
        for attribute, target in (('data-input', self.inputs), ('data-check', self.results)):
            if attribute in a:
                key = a[attribute]; need(key not in target, 'unique visible marker')
                target[key] = ''; self.capture.append((len(self.stack)+1, target, key))
        if 'data-source' in a: self.sources[a['data-source']] = a['href']
        if 'download' in a: self.downloads.add(a['href'])
        if tag not in ('br', 'hr', 'img', 'meta', 'link', 'input', 'wbr'): self.stack.append((tag, a))

    def handle_data(self, data):
        for _, target, key in self.capture: target[key] += data

    def handle_endtag(self, tag):
        need(self.stack and self.stack[-1][0] == tag, 'balanced HTML')
        depth = len(self.stack); self.capture = [x for x in self.capture if x[0] != depth]; self.stack.pop()


def primitive_case(data, recommendation=(1, 0), restoration=Q(1, 2), eta=Q(0), active=False, changed=False):
    """Independent conditional laws and difference-equation solution."""
    e = data['economy']; delta, benefit, cost, repair_cost = map(Q, (e['discount'], e['benefit'], e['collaboration_effort_cost'], e['review_effort_cost']))
    signal = {k: (1-eta)*Q(v)+eta/2 for k, v in e['good_report_in_G'].items()}
    review = {k: Q(v) for k, v in data['active_repair']['good_report_in_R'].items()} if active else {k: restoration for k in signal}
    if changed:
        review['WN'] = review['NW'] = Q(data['active_repair']['counterfactual_one_worker_good_probability'])
    def reward_probability(state, own):
        other = recommendation[state]; key = ('W' if own else 'N')+('W' if other else 'N')
        if state == 0: return benefit*other-cost*own, signal[key]
        return -repair_cost*own, review[key]
    def solve(own):
        (g, p), (h, q) = (reward_probability(s, own[s]) for s in (0, 1))
        gap = (g-h)/(1-delta*(p-q))
        vr = (h+delta*q*gap)/(1-delta)
        return (vr+gap, vr), (g, h), (p, q)
    value, flow, probabilities = solve(recommendation)
    u = tuple((1-delta)*v for v in value)
    margins = []; residuals = []; failures = []
    for s in (0, 1):
        for action in (0, 1):
            g, p = reward_probability(s, action)
            advantage = value[s]-g-delta*(p*value[0]+(1-p)*value[1])
            residuals.append({'state': ('G', 'R')[s], 'own_action': action, 'recommended': action == recommendation[s], 'margin': advantage})
            if action != recommendation[s]:
                margins.append(advantage)
                if advantage < 0: failures.append({'state': ('G', 'R')[s], 'own_action': action, 'one_action_then_return_gain': -advantage})
    policies = []
    for policy in product((0, 1), repeat=2):
        v, _, _ = solve(policy)
        policies.append({'actions_G_R': list(policy), 'V': v, 'U': tuple((1-delta)*z for z in v)})
    p, q = probabilities
    stationary = q/(q+1-p)
    occupancy = tuple((1-delta)*initial/(1-delta*(p-q))+delta*q/(1-delta*(p-q)) for initial in (1, 0))
    return {'profile_G_R': list(recommendation), 'status': 'certified' if min(margins) >= 0 else 'not_certified',
            'strict_alternative_margins': min(margins) > 0, 'V': value, 'U': u,
            'on_path_good_probabilities': probabilities, 'current_per_agent_flow': flow,
            'alternative_action_margins_G_R': margins, 'state_action_bellman': residuals,
            'profitable_one_action_return_witnesses': failures, 'stationary_own_policies': policies,
            'best_stationary_U_by_start': tuple(max(row['U'][s] for row in policies) for s in (0, 1)),
            'occupancy': {'stationary_G': stationary, 'stationary_per_agent_flow': stationary*flow[0]+(1-stationary)*flow[1],
                          'discounted_G_by_start': occupancy, 'discounted_flow_by_start': tuple(w*flow[0]+(1-w)*flow[1] for w in occupancy)}}


def determinant(matrix):
    n = len(matrix); total = Q(0)
    for order in permutations(range(n)):
        inversions = sum(order[i] > order[j] for i in range(n) for j in range(i+1, n))
        term = Q((-1)**inversions)
        for i, j in enumerate(order): term *= matrix[i][j]
        total += term
    return total


def graph_oracle(gamma, targets):
    # Labeled cycle adjacency constructed directly, independently of reader helpers.
    neighbors = ((1, 3), (0, 2), (1, 3), (0, 2))
    candidates = []; rows = []
    for mask in range(16):
        active = [i for i in range(4) if mask & 2**i]
        m = [[Q(i == j)+gamma*int(j in neighbors[i]) for j in active] for i in active]
        rhs = [targets[i] for i in active]; det = determinant(m)
        if not det:
            need(active == [0, 1, 2, 3] and gamma == Q(1, 2), 'only declared singular system in oracle domain')
            status = 'affine' if targets[0]-targets[1]+targets[2]-targets[3] == 0 else 'inconsistent'
            rows.append({'support': active, 'status': status, 'matrix': m, 'rhs': rhs}); continue
        values = []
        for col in range(len(active)):
            replaced = [list(row) for row in m]
            for i in range(len(active)): replaced[i][col] = rhs[i]
            values.append(determinant(replaced)/det)
        x = [Q(0)]*4
        for i, v in zip(active, values): x[i] = v
        slack = [gamma*sum(x[j] for j in neighbors[i])-targets[i] for i in range(4) if i not in active]
        valid = all(x[i] > 0 for i in active) and all(z >= 0 for z in slack)
        rows.append({'support': active, 'status': 'unique', 'candidate': x, 'slacks': slack, 'valid': valid})
        if valid:
            payoffs = [targets[i]*x[i]-x[i]**2/2-gamma*x[i]*sum(x[j] for j in neighbors[i]) for i in range(4)]
            potential = sum(targets[i]*x[i]-x[i]**2/2 for i in range(4))-gamma*(x[0]*x[1]+x[1]*x[2]+x[2]*x[3]+x[3]*x[0])
            candidates.append({'actions': x, 'utility': payoffs, 'welfare': sum(payoffs), 'potential': potential})
    return rows, candidates


def check(root=None):
    need(root is None or isinstance(root, (str, Path)), 'root path')
    base = Path(root) if root is not None else Path(__file__).resolve().parents[1]
    raw = {p: (base/p).read_bytes() for p in FILES}
    comparisons = rejections = alias_attempts = reader_cli_runs = 0
    def eq(a, b, reason):
        nonlocal comparisons
        comparisons += 1; need(a == b, reason+': '+repr(a)+' != '+repr(b))
    def rejects(fn, reason):
        nonlocal rejections
        try: fn()
        except ValueError: rejections += 1
        else: raise ValueError('invalid domain accepted: '+reason)
    page = Reader(); page.feed(raw[HTML].decode()); page.close()
    eq((page.stack, page.capture), ([], []), 'complete balanced project')
    tasks = {f'v13-project-p{i}': p for i, p in enumerate((10, 10, 20, 10, 10, 20, 20), 1)}
    eq(page.tasks, tasks, 'all seven exact task allocations'); eq(page.answers, set(tasks), 'seven complete paired answers')
    eq(page.domains, {'D'+str(i): 20 for i in range(1, 6)}, 'five twenty-point domains')
    eq(sum(page.tasks.values()), 100, 'project total')
    eq(page.downloads, {Path(p).name for p in READER}, 'five flat reader downloads')
    eq(page.sources, SOURCE_URLS, 'exact primary routes')
    data = read_json(raw[INPUT]); saved = read_json(raw[OUTPUT]); source = read_json(raw[SOURCES]); audit = read_json(raw[AUTHOR]); manifest = read_json(raw[MANIFEST])
    eq({s['id']: s['url'] for s in source['sources']}, SOURCE_URLS, 'source record identity')
    expected_input_routes = {'economy.discount', 'economy.benefit', 'economy.collaboration_effort_cost', 'economy.review_effort_cost',
        'restoration_grid', 'garbling_values', 'active_repair.counterfactual_one_worker_good_probability', 'paper_case.vertices',
        'paper_case.undirected_edges', 'paper_case.regular_interaction', 'paper_case.singular_interaction', 'paper_case.last_target_increase'}
    expected_input_routes |= {'economy.good_report_in_G.'+a for a in ('WW', 'WN', 'NW', 'NN')}
    expected_input_routes |= {'active_repair.good_report_in_R.'+a for a in ('WW', 'WN', 'NW', 'NN')}
    eq(set(page.inputs), expected_input_routes, 'all twenty original visible input routes')
    for path, visible in page.inputs.items():
        value = data
        for key in path.split('.'): value = value[key]
        eq(norm(visible), norm(printed(value)), 'actual printed input '+path)
    capture, errors = StringIO(), StringIO()
    with redirect_stdout(capture), redirect_stderr(errors):
        reader = runpy.run_path(str(base/MODEL))
        original = deepcopy(data); result = reader['run'](data)
    eq((capture.getvalue(), errors.getvalue()), ('', ''), 'quiet import and run')
    eq(data, original, 'caller input unchanged'); eq(result, saved, 'actual saved output equals fresh run')
    json.dumps(result, allow_nan=False)
    groups = []; marks = {}; primitive_rows = []
    def compare_case(actual, expected, name):
        for field, value in expected.items(): eq(actual[field], encoded(value), name+' '+field)
        eq(expected['U'], expected['occupancy']['discounted_flow_by_start'], name+' true-flow reconciliation')
        return expected
    rates = tuple(Q(x) for x in data['restoration_grid'])
    for i, r in enumerate(rates):
        expected = primitive_case(data, restoration=r); primitive_rows.append(expected)
        compare_case(result['baseline']['grid'][i], expected, 'base '+str(r))
        for tag, field in (('V', 'V'), ('U', 'U'), ('margins', 'alternative_action_margins_G_R'), ('best', 'best_stationary_U_by_start')):
            marks[f'grid-{i}-{tag}'] = expected[field]
        for j, row in enumerate(expected['stationary_own_policies']): marks[f'policy-{i}-{j}'] = row['U']
    feasible = [r for r, row in zip(rates, primitive_rows) if row['status'] == 'certified']
    best = max((row['U'][0], r) for r, row in zip(rates, primitive_rows) if row['status'] == 'certified')[1]
    eq(result['baseline']['feasible_restorations'], encoded(feasible), 'complete finite feasible set')
    eq(result['baseline']['best_grid']['restoration'], str(best), 'complete grid optimum')
    marks['feasible-grid'] = feasible; marks['best-grid'] = best
    reference = primitive_case(data); compare_case(result['reference_restoration_half'], reference, 'reference')
    delta = Q(data['economy']['discount']); benefit = Q(data['economy']['benefit']); cost = Q(data['economy']['collaboration_effort_cost']); k = Q(data['economy']['review_effort_cost'])
    alpha = Q(data['economy']['good_report_in_G']['WW']); beta = Q(data['economy']['good_report_in_G']['NW'])
    for key, a, b in (('WW', 1, 1), ('WN', 1, 0), ('NW', 0, 1), ('NN', 0, 0)):
        marks['payoff-G-'+key] = (benefit*b-cost*a, benefit*a-cost*b)
        marks['payoff-R-'+key] = (-k*a, -k*b)
    marks.update({'false-warning': 1-alpha, 'reference-gap': reference['V'][0]-reference['V'][1],
        'reference-V': reference['V'], 'reference-U': reference['U'], 'reference-margins': reference['alternative_action_margins_G_R'],
        'reference-stationary-G': reference['occupancy']['stationary_G'], 'reference-stationary-flow': reference['occupancy']['stationary_per_agent_flow'],
        'reference-discounted-G': reference['occupancy']['discounted_G_by_start'][0],
        'reference-patience': cost/((alpha-beta)*(benefit-cost)+cost*(alpha-Q(1, 2)))})
    def inspect_continuous(d, eta, actual):
        e = d['economy']; discount, b, c = map(Q, (e['discount'], e['benefit'], e['collaboration_effort_cost']))
        a = (1-eta)*Q(e['good_report_in_G']['WW'])+eta/2
        beta_eta = (1-eta)*Q(e['good_report_in_G']['NW'])+eta/2
        ceiling = a+(a-beta_eta)*(b-c)/c-1/discount
        eq(actual['raw_restoration_ceiling'], str(ceiling), 'actual generalized raw ceiling')
        if ceiling < 0:
            eq((actual['weak_interval'], actual['weak_optimum'], actual['strict_interval'], actual['strict_supremum_U']), (None,)*4, 'empty cooperative class')
        else:
            upper = min(Q(1), ceiling)
            eq(actual['weak_interval'], ['0', str(upper)], 'domain intersection [0,1]')
            oracle = primitive_case(d, restoration=upper, eta=eta)
            compare_case(actual['weak_optimum'], oracle, 'continuous')
            eq(oracle['alternative_action_margins_G_R'][0] >= 0, True, 'attained weak boundary is feasible')
            if ceiling == 0:
                eq((actual['strict_interval'], actual['strict_supremum_U']), (None, None), 'weak singleton has empty strict class')
            else:
                eq(actual['strict_interval'], {'lower':'0', 'upper':str(upper), 'lower_included':True, 'upper_included':ceiling>1}, 'strict endpoint rights')
                eq(actual['strict_supremum_U'], encoded(oracle['U']), 'strict supremum values')
        eq(actual['strict_supremum_attained'], ceiling > 1, 'strict attainment boundary')
        return ceiling
    ceiling = inspect_continuous(data, Q(0), result['baseline']['continuous'])
    boundary = primitive_case(data, restoration=ceiling)
    marks.update({'continuous-r': ceiling, 'continuous-V': boundary['V'], 'continuous-U': boundary['U'], 'continuous-margins': boundary['alternative_action_margins_G_R']})
    groups.append('all five controls, every stationary deviation and full weak/strict continuous boundary')
    noise_rows = []
    for eta_text, actual_design in zip(data['garbling_values'], result['garbling']):
        eta = Q(eta_text); local = []
        for r, actual in zip(rates, actual_design['grid']):
            row = primitive_case(data, restoration=r, eta=eta); compare_case(actual, row, 'garbling '+str(eta)); local.append(row)
        possible = [r for r, row in zip(rates, local) if row['status'] == 'certified']
        eq(actual_design['feasible_restorations'], encoded(possible), 'garbled feasible class')
        eq(actual_design['best_grid'] is None, not possible, 'empty best candidate semantics')
        cap = inspect_continuous(data, eta, actual_design['continuous']); noise_rows.append((eta, cap, local))
    quarter, half = noise_rows
    eta, cap, rows = quarter
    a, b = ((1-eta)*x+eta/2 for x in (alpha, beta)); noise_boundary = primitive_case(data, restoration=cap, eta=eta)
    marks.update({'noise-quarter-law': (a, b), 'noise-quarter-ceiling': cap, 'noise-quarter-grid': (Q(0),),
        'noise-quarter-V': rows[0]['V'], 'noise-quarter-U': rows[0]['U'], 'noise-quarter-margins': rows[0]['alternative_action_margins_G_R'],
        'noise-continuous-V': noise_boundary['V'], 'noise-continuous-U': noise_boundary['U'], 'noise-continuous-margins': noise_boundary['alternative_action_margins_G_R'],
        'noise-half-law': tuple((1-half[0])*x+half[0]/2 for x in (alpha, beta)), 'noise-half-ceiling': half[1],
        'noise-half-zero-margin': half[2][0]['alternative_action_margins_G_R'][0]})
    # The ceiling is affine in eta; this solves its exact zero, not a sampled cutoff.
    slope = ((Q(1, 2)-alpha)+(beta-alpha)*(benefit-cost)/cost)
    marks['garbling-cutoff'] = -ceiling/slope
    always = primitive_case(data, recommendation=(0, 0)); compare_case(result['always_N_equilibrium'], always, 'always N')
    eq(always['status'], 'certified', 'lack of cooperative candidates is not lack of equilibrium')
    groups.append('both actual garbling laws, sharp information boundary and alternative equilibrium')
    active = primitive_case(data, (1, 1), active=True); changed = primitive_case(data, (1, 1), active=True, changed=True)
    compare_case(result['active_repair'], active, 'active repair'); compare_case(result['changed_off_path_repair'], changed, 'changed repair')
    gains = tuple(a-b for a, b in zip(active['U'], reference['U']))
    eq(result['repair_gain_over_reference_U'], encoded(gains), 'cost-inclusive conditional gains')
    eq((active['V'], active['on_path_good_probabilities'], active['current_per_agent_flow']),
       (changed['V'], changed['on_path_good_probabilities'], changed['current_per_agent_flow']), 'observationally identical compliant law')
    eq((active['status'], changed['status']), ('certified', 'not_certified'), 'off-path IC is material')
    marks.update({'repair-V': active['V'], 'repair-U': active['U'], 'repair-margins': active['alternative_action_margins_G_R'],
        'repair-gain': gains, 'repair-stationary-G': active['occupancy']['stationary_G'], 'repair-stationary-flow': active['occupancy']['stationary_per_agent_flow'],
        'repair-discounted-G': active['occupancy']['discounted_G_by_start'][0], 'changed-repair-margins': changed['alternative_action_margins_G_R'],
        'changed-repair-best': changed['best_stationary_U_by_start']})
    for j in range(4):
        marks['repair-policy-'+str(j)] = active['stationary_own_policies'][j]['U']
        marks['changed-policy-'+str(j)] = changed['stationary_own_policies'][j]['U']
    groups.append('costly repair in both states and changed off-path law at identical compliant values')
    paper = data['paper_case']; graph_outputs = {}
    for name, gamma, target in (('regular', Q(paper['regular_interaction']), [Q(1)]*4),
                                 ('critical', Q(1, 2), [Q(1)]*4),
                                 ('changed_target', Q(1, 2), [Q(1), Q(1), Q(1), 1+Q(paper['last_target_increase'])])):
        oracle_rows, eqs = graph_oracle(gamma, target); graph_outputs[name] = eqs
        actual = result['paper'][name]
        eq(actual['isolated_or_endpoint_equilibria'], encoded(eqs), name+' independent complete nonsingular support results')
        eq(len(actual['support_audits']), 16, 'all sixteen graph supports')
        for reference_row, row in zip(oracle_rows, actual['support_audits']):
            eq(row['positive_support'], [i+1 for i in reference_row['support']], 'actual active support')
            eq(row['linear_system']['status'], reference_row['status'], 'determinant versus elimination status')
            if reference_row['status'] == 'unique':
                eq((row['candidate'], row['inactive_slacks'], row['is_equilibrium']),
                   (encoded(reference_row['candidate']), encoded(reference_row['slacks']), reference_row['valid']), 'Cramer solution, strict activity and all inactive inequalities')
            elif reference_row['status'] == 'affine':
                part = list(map(Q, row['linear_system']['particular'])); null = row['linear_system']['nullspace']
                eq([sum(a*b for a, b in zip(line, part)) for line in reference_row['matrix']], reference_row['rhs'], 'affine particular solves original system')
                eq(len(null), 1, 'critical nullity')
                eq([sum(a*Q(b) for a, b in zip(line, null[0])) for line in reference_row['matrix']], [Q(0)]*4, 'critical null direction')
        eq(actual['equilibrium_set_kind'], 'continuum' if name == 'critical' else 'finite', 'honest family versus point status')
    family = result['paper']['critical']['complete_family']
    eq((family['actions'], family['interval'], family['welfare_polynomial_coefficients_constant_linear_quadratic']),
       (['a', '1-a', 'a', '1-a'], ['0', '1'], ['1', '-2', '2']), 'entire symbolic family and welfare polynomial')
    # Independent coefficient identity for every a: neighbors sum twice the opposite action.
    eq((Q(1)-2*Q(1, 2), -1+2*Q(1, 2)), (0, 0), 'all-a affine best-reply identity coefficients')
    for a in (Q(0), Q(1, 3), Q(1, 2), Q(1)):
        x = (a, 1-a, a, 1-a)
        utility = [v-v*v/2-Q(1, 2)*v*2*x[(i+1)%4] for i, v in enumerate(x)]
        eq(sum(utility), 1-2*a+2*a*a, 'actual utility on critical family')
        potential = sum(v-v*v/2 for v in x)-Q(1, 2)*4*a*(1-a)
        eq(potential, 1, 'constant potential differs from welfare')
    reg, changed_graph = graph_outputs['regular'][0], graph_outputs['changed_target'][0]
    marks.update({'paper-contraction': 2*Q(paper['regular_interaction']), 'paper-regular-actions': reg['actions'],
        'paper-regular-welfare': reg['welfare'], 'paper-regular-potential': reg['potential'],
        'paper-critical-welfare-range': (Q(1, 2), Q(1)), 'paper-critical-potential': Q(1),
        'paper-changed-actions': changed_graph['actions'], 'paper-changed-welfare': changed_graph['welfare']})
    groups.append('all graph supports by determinant expansion, singular family and actual welfare versus potential')
    eq(set(page.results), set(marks), 'all 101 visible answer markers independently derived')
    for name, value in marks.items(): eq(norm(page.results[name]), norm(printed(value)), 'printed answer '+name)
    # Focused boundary interventions: no undirected parameter grid.
    transfers = (('benefit', '2', 'empty'), ('benefit', '13/6', 'weak singleton'),
                 ('benefit', '11/2', 'ceiling exactly one'), ('benefit', '6', 'ceiling above one'),
                 ('discount', '3/4', 'patience failure'))
    for field, value, label in transfers:
        altered = deepcopy(data); altered['economy'][field] = value
        output = reader['run'](altered)
        inspect_continuous(altered, Q(0), output['baseline']['continuous'])
        compare_case(output['reference_restoration_half'], primitive_case(altered), label)
    altered = deepcopy(data); altered['garbling_values'] = ['11/26', '1']
    out = reader['run'](altered)
    for eta, item in zip((Q(11, 26), Q(1)), out['garbling']): inspect_continuous(altered, eta, item['continuous'])
    altered = deepcopy(data); altered['paper_case']['regular_interaction'] = '2/5'; altered['paper_case']['last_target_increase'] = '1'
    out = reader['run'](altered)
    eq(out['paper']['regular']['isolated_or_endpoint_equilibria'], encoded(graph_oracle(Q(2, 5), [Q(1)]*4)[1]), 'new contraction network')
    eq(out['paper']['changed_target']['isolated_or_endpoint_equilibria'], encoded(graph_oracle(Q(1, 2), [Q(1), Q(1), Q(1), Q(2)])[1]), 'largest declared target perturbation')
    groups.append('empty/singleton/strict-boundary/above-one control domains, patience and targeted graph changes')
    def set_path(path, value):
        changed_input = deepcopy(data); cursor = changed_input
        for key in path[:-1]: cursor = cursor[key]
        cursor[path[-1]] = value
        return changed_input
    bad_values = [
        (('schema_version',), True), (('schema_version',), 2),
        (('economy', 'discount'), True), (('economy', 'discount'), 0.8), (('economy', 'discount'), float('nan')),
        (('economy', 'discount'), float('inf')), (('economy', 'discount'), '0.8'), (('economy', 'discount'), '4/0'),
        (('economy', 'discount'), ' 4/5'), (('economy', 'discount'), '1e0'), (('economy', 'discount'), '0'),
        (('economy', 'discount'), '1'), (('economy', 'discount'), '-1'),
        (('economy', 'benefit'), '1'), (('economy', 'collaboration_effort_cost'), '0'),
        (('economy', 'review_effort_cost'), '0'), (('economy', 'initial_state'), 'R'),
        (('economy', 'good_report_in_G', 'NN'), '0'), (('economy', 'good_report_in_G', 'WW'), '1'),
        (('economy', 'good_report_in_G', 'WN'), '1/2'), (('economy', 'good_report_in_G', 'NN'), '4/5'),
        (('restoration_grid',), []), (('restoration_grid',), ['1/2', '2/4']), (('restoration_grid',), ['3/2']),
        (('garbling_values',), ['-1/2']), (('garbling_values',), ['1', '1']),
        (('active_repair', 'good_report_in_R', 'WN'), '1/2'),
        (('active_repair', 'counterfactual_one_worker_good_probability'), '3/2'),
        (('paper_case', 'vertices'), True), (('paper_case', 'vertices'), 5),
        (('paper_case', 'undirected_edges'), [[1, 2], [2, 3], [3, 4], [1, 2]]),
        (('paper_case', 'undirected_edges'), [[1, 1], [2, 3], [3, 4], [1, 4]]),
        (('paper_case', 'undirected_edges'), [[1, 2], [2, 3], [3, 4], [1, 3]]),
        (('paper_case', 'regular_interaction'), '1/2'), (('paper_case', 'regular_interaction'), '0'),
        (('paper_case', 'singular_interaction'), '2/5'), (('paper_case', 'last_target_increase'), '0'),
        (('paper_case', 'last_target_increase'), '6/5'),
    ]
    for path, value in bad_values: rejects(lambda p=path, v=value: reader['run'](set_path(p, v)), str(path))
    extra = deepcopy(data); extra['invented'] = 1
    missing = deepcopy(data); del missing['economy']['review_effort_cost']
    rejects(lambda: reader['run'](extra), 'unknown object key'); rejects(lambda: reader['run'](missing), 'missing object key')
    rejects(lambda: reader['run']([]), 'object type')
    for raw_bad in ('{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}', '{"x":1e9999}', '{"x":0.8}'):
        rejects(lambda s=raw_bad: reader['strict_loads'](s), 'strict JSON')
    groups.append('actual malformed economic/JSON domains and protected reader execution')
    # Real reader writes/rejections, separately under normal and optimized Python.
    with tempfile.TemporaryDirectory(prefix='v13-project-reader-') as temporary:
        directory = Path(temporary)
        for path in READER: (directory/Path(path).name).write_bytes(raw[path])
        program = directory/Path(MODEL).name
        protected = [directory/Path(p).name for p in (INPUT, MODEL, README, MANIFEST)]
        protected_before = {p: p.read_bytes() for p in protected}
        for mode in ((), ('-O',)):
            command = [sys.executable, '-B', *mode, str(program)]
            process = subprocess.run(command, cwd='/', capture_output=True)
            reader_cli_runs += 1
            eq((process.returncode, process.stdout, process.stderr), (0, b'', b''), 'silent isolated reader default')
            eq((directory/Path(OUTPUT).name).read_bytes(), raw[OUTPUT], 'reader exact output bytes')
            alternate = directory/'explicit-input.json'; alternate.write_bytes(raw[INPUT])
            destination = directory/'explicit-output.json'
            process = subprocess.run(command+['--input', str(alternate), '--output', str(destination)], cwd='/', capture_output=True)
            reader_cli_runs += 1
            eq((process.returncode, process.stdout, process.stderr), (0, b'', b''), 'explicit isolated reader paths')
            eq(destination.read_bytes(), raw[OUTPUT], 'explicit output bytes'); destination.unlink()
            for target in protected+[alternate]:
                for kind in ('direct', 'symlink', 'hardlink'):
                    alias = target if kind == 'direct' else directory/('output-'+kind)
                    if kind == 'symlink': alias.symlink_to(target)
                    if kind == 'hardlink': alias.hardlink_to(target)
                    before = {p: p.read_bytes() for p in protected+[alternate]}
                    process = subprocess.run(command+['--input', str(alternate), '--output', str(alias)], cwd='/', capture_output=True)
                    alias_attempts += 1
                    eq(process.returncode != 0 and process.stdout == b'' and bool(process.stderr), True, 'actual '+kind+' output protection')
                    eq({p: p.read_bytes() for p in protected+[alternate]}, before, 'alias rejection preserved every protected byte')
                    if kind != 'direct': alias.unlink()
            malformed = directory/'malformed.json'; malformed.write_text('{"discount":NaN}')
            sentinel = directory/'sentinel.json'; sentinel.write_bytes(b'unchanged')
            process = subprocess.run(command+['--input', str(malformed), '--output', str(sentinel)], cwd='/', capture_output=True)
            reader_cli_runs += 1
            eq(process.returncode != 0 and process.stdout == b'', True, 'actual malformed CLI rejection')
            eq(sentinel.read_bytes(), b'unchanged', 'invalid input does not replace output')
            malformed.unlink(); sentinel.unlink(); alternate.unlink()
            eq({p: p.read_bytes() for p in protected}, protected_before, 'all original protected reader bytes')
        eq({p.name for p in directory.iterdir()}, {Path(p).name for p in READER}, 'exact five-file reader isolation')
    eq({row['file'] for row in manifest['files']}, {Path(p).name for p in (INPUT, MODEL, OUTPUT, README)}, 'manifest exactly four nonself reader payloads')
    for row in manifest['files']:
        payload = raw['content/projects/'+row['file']]
        eq((row['bytes'], row['sha256']), (len(payload), sha256(payload).hexdigest()), 'reader manifest binding')
    eq({row['path'] for row in audit['bindings']}, set(FILES)-{AUTHOR}, 'author exactly eight nonself bindings')
    for row in audit['bindings']:
        payload = raw[row['path']]
        eq((row['bytes'], row['sha256']), (len(payload), sha256(payload).hexdigest()), 'final author binding')
    eq(set(audit['task_audit']), set(tasks), 'all seven exact task/proof judgments')
    eq(audit['unresolved_findings'], [], 'no unresolved author finding')
    eq({p: (base/p).read_bytes() for p in FILES}, raw, 'all nine runtime payloads unchanged')
    summary = {'volume': 'v13', 'component': 'project', 'status': 'passed', 'comparisons': comparisons,
        'domain_rejections': rejections, 'protected_output_attempts': alias_attempts, 'reader_cli_runs': reader_cli_runs,
        'solved_tasks': len(tasks), 'points': sum(tasks.values()), 'domains': len(page.domains), 'input_markers': len(page.inputs),
        'result_markers': len(marks), 'intervention_groups': len(groups), 'interventions': groups,
        'runtime_files': 9, 'isolated_reader_files': 5,
        'limits': 'Finite exact checks supplement full analytic proof/task review; no empirical validation, learner certification or unrestricted equilibrium-selection claim.'}
    json.dumps(summary, allow_nan=False)
    return summary


if __name__ == '__main__':
    need(len(sys.argv) == 1, 'silent checker CLI takes no arguments')
    check()
