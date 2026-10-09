"""Independent, quiet eleven-file review of the V13 theory project.

Values come from discounted state-occupation measures solved by elimination;
network supports use an LDL factorization and the cycle's exact null vector.
Neither the author checker nor its answers are imported or executed.
"""
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from io import StringIO
from itertools import product
import json
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile

PAGE = 'content/assessments/parts/v13-project.html'
INPUT = 'content/projects/v13-assessment-inputs.json'
MODEL = 'content/projects/v13-assessment-analysis.py'
OUTPUT = 'content/projects/v13-assessment-output.json'
MANIFEST = 'content/projects/v13-assessment-manifest.json'
README = 'content/projects/v13-assessment-README.txt'
AUTHOR_CHECKER = 'scripts/check_v13_project.py'
AUTHOR = 'content/reviews/v13-project-author.json'
SOURCES = 'content/reviews/v13-project-sources.json'
SELF = 'scripts/check_v13_project_peer.py'
REVIEW = 'content/reviews/v13-project-peer.json'
AUTHOR_FILES = (PAGE, INPUT, MODEL, OUTPUT, MANIFEST, README, AUTHOR_CHECKER, AUTHOR, SOURCES)
FILES = AUTHOR_FILES + (SELF, REVIEW)
READER_FILES = (INPUT, MODEL, OUTPUT, MANIFEST, README)
SOURCE_ROUTES = {
    'v13-c06-manea-noncoop2017': 'https://ocw.mit.edu/courses/14-126-game-theory-spring-2016/a4d0a3949ab29c2a2f55442a9723d205_MIT14_126S16_noncoop.pdf',
    'v13-c09-stole-contracts1999': 'https://ocw.mit.edu/courses/14-124-microeconomic-theory-iv-spring-2017/be21e9cc762231c50ab42bbf35ead5db_MIT14_124S17_LecNote1_2.pdf',
    'v13-c11-bkd-networks2014': 'https://sites.duke.edu/rachelkranton/files/2016/09/strategic-interaction-and-networks-aer.pdf',
}


def require(test, message):
    if not test:
        raise ValueError(message)


def strict_json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    def bad(_):
        raise ValueError('unsupported JSON number')
    return json.loads(text, object_pairs_hook=pairs, parse_float=bad, parse_constant=bad)


def serial(value):
    if isinstance(value, F): return str(value)
    if isinstance(value, (tuple, list)): return [serial(x) for x in value]
    if isinstance(value, dict): return {k: serial(v) for k, v in value.items()}
    return value


def visible(value):
    return '('+','.join(visible(x) for x in value)+')' if isinstance(value, (tuple, list)) else str(value)


def compact(text):
    return ''.join(text.replace('\u2212', '-').split())


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.open = []; self.ids = set(); self.inputs = {}; self.results = {}
        self.prompts = {}; self.solutions = set(); self.domains = {}; self.sources = {}; self.downloads = set()
        self.collect = []

    def handle_starttag(self, tag, pairs):
        a = dict(pairs); require(len(a) == len(pairs), 'duplicate HTML attribute')
        require(tag not in ('h1', 'script', 'iframe', 'object'), 'unexpected reader element')
        if 'id' in a:
            key = a['id']; require(key not in self.ids and (key == 'project' or key.startswith('v13-project-')), 'reader ID')
            self.ids.add(key)
        if 'data-points' in a:
            require(a['data-points'].isdigit(), 'integer rubric points')
            if tag == 'li': self.prompts[a['id']] = int(a['data-points'])
            elif tag == 'tr': self.domains[a['data-domain']] = int(a['data-points'])
            else: raise ValueError('unexpected rubric element')
        if 'data-solution-for' in a:
            key = a['data-solution-for']
            require(key not in self.solutions and any(t == 'details' and 'solutions' in d.get('class', '').split() for t, d in self.open), 'paired disclosed solution')
            self.solutions.add(key)
        for name, destination in (('data-input', self.inputs), ('data-check', self.results)):
            if name in a:
                key = a[name]; require(key not in destination, 'duplicate visible marker')
                destination[key] = ''; self.collect.append((len(self.open), destination, key))
        if 'data-source' in a: self.sources[a['data-source']] = a['href']
        if 'download' in a: self.downloads.add(a['href'])
        if tag not in ('br', 'hr', 'img', 'input', 'meta', 'link', 'wbr'): self.open.append((tag, a))

    def handle_data(self, text):
        for _, destination, key in self.collect: destination[key] += text

    def handle_endtag(self, tag):
        require(self.open and self.open[-1][0] == tag, 'unbalanced reader HTML')
        self.open.pop(); self.collect = [r for r in self.collect if r[0] < len(self.open)]


def solve(a, b):
    """Forward elimination and back substitution; no inverse or gap formula."""
    n = len(b); rows = [list(map(F, row))+[F(v)] for row, v in zip(a, b)]
    for col in range(n):
        pivot = next((r for r in range(col, n) if rows[r][col]), None)
        require(pivot is not None, 'oracle system singular')
        rows[col], rows[pivot] = rows[pivot], rows[col]
        for r in range(col+1, n):
            scale = rows[r][col]/rows[col][col]
            for j in range(col, n+1): rows[r][j] -= scale*rows[col][j]
    x = [F(0)]*n
    for r in reversed(range(n)):
        x[r] = (rows[r][-1]-sum(rows[r][j]*x[j] for j in range(r+1, n)))/rows[r][r]
    return x


def occupation_value(p, reward, discount):
    trans = [[p[0], 1-p[0]], [p[1], 1-p[1]]]
    matrix = [[F(i == j)-discount*trans[j][i] for j in range(2)] for i in range(2)]
    weights = [solve(matrix, [(1-discount)*int(i == start) for i in range(2)]) for start in range(2)]
    u = [sum(w[i]*reward[i] for i in range(2)) for w in weights]
    return [x/(1-discount) for x in u], u, weights


def game(data, recommendation=(1, 0), restoration=F(1, 2), noise=F(0), repair=False, changed=False):
    e = data['economy']; d, b, c, k = [F(e[x]) for x in ('discount', 'benefit', 'collaboration_effort_cost', 'review_effort_cost')]
    signal = {s: (1-noise)*F(v)+noise/2 for s, v in e['good_report_in_G'].items()}
    rlaw = {s: F(v) for s, v in data['active_repair']['good_report_in_R'].items()} if repair else {s: restoration for s in signal}
    if changed: rlaw['WN'] = rlaw['NW'] = F(data['active_repair']['counterfactual_one_worker_good_probability'])
    def law(state, action):
        opponent = recommendation[state]
        key = ('W' if action else 'N')+('W' if opponent else 'N')
        return ((b*opponent-c*action) if state == 0 else -k*action), (signal if state == 0 else rlaw)[key]
    def policy(actions):
        pairs = [law(s, a) for s, a in enumerate(actions)]
        rewards = [v[0] for v in pairs]; probabilities = [v[1] for v in pairs]
        v, u, weights = occupation_value(probabilities, rewards, d)
        return v, u, weights, rewards, probabilities
    v, u, weights, rewards, p = policy(recommendation)
    rows = []; margins = []; profitable = []
    for state in range(2):
        for action in range(2):
            immediate, good = law(state, action)
            m = v[state]-immediate-d*(good*v[0]+(1-good)*v[1])
            rows.append({'state': ('G', 'R')[state], 'own_action': action, 'recommended': action == recommendation[state], 'margin': m})
            if action != recommendation[state]:
                margins.append(m)
                if m < 0: profitable.append({'state': ('G', 'R')[state], 'own_action': action, 'one_action_then_return_gain': -m})
    policies = []
    for actions in product(range(2), repeat=2):
        pv, pu, _, _, _ = policy(actions)
        policies.append({'actions_G_R': list(actions), 'V': pv, 'U': pu})
    stationary = solve([[1-p[0], -p[1]], [1, 1]], [0, 1])
    return {
        'profile_G_R': list(recommendation), 'status': 'certified' if all(m >= 0 for m in margins) else 'not_certified',
        'strict_alternative_margins': all(m > 0 for m in margins), 'V': v, 'U': u,
        'current_per_agent_flow': rewards, 'on_path_good_probabilities': p,
        'alternative_action_margins_G_R': margins, 'state_action_bellman': rows,
        'profitable_one_action_return_witnesses': profitable, 'stationary_own_policies': policies,
        'best_stationary_U_by_start': [max(r['U'][s] for r in policies) for s in range(2)],
        'occupancy': {'stationary_G': stationary[0], 'stationary_per_agent_flow': sum(x*y for x, y in zip(stationary, rewards)),
                      'discounted_G_by_start': [w[0] for w in weights], 'discounted_flow_by_start': u}}


def ldl_solution(a, b):
    """Independent symmetric positive-definite principal-support factorization."""
    n = len(b); lower = [[F(i == j) for j in range(n)] for i in range(n)]; diagonal = []
    for j in range(n):
        value = a[j][j]-sum(lower[j][k]**2*diagonal[k] for k in range(j))
        require(value > 0, 'positive principal support pivot')
        diagonal.append(value)
        for i in range(j+1, n): lower[i][j] = (a[i][j]-sum(lower[i][k]*lower[j][k]*diagonal[k] for k in range(j)))/value
    y = []
    for i in range(n): y.append(b[i]-sum(lower[i][j]*y[j] for j in range(i)))
    z = [v/d for v, d in zip(y, diagonal)]; x = [F(0)]*n
    for i in reversed(range(n)): x[i] = z[i]-sum(lower[j][i]*x[j] for j in range(i+1, n))
    return x


def network(gamma, targets):
    adjacent = lambda i, j: (i-j) % 4 in (1, 3)
    supports = []; equilibria = []
    for mask in range(16):
        active = [i for i in range(4) if mask & (1 << i)]
        matrix = [[F(i == j)+gamma*adjacent(i, j) for j in active] for i in active]
        if len(active) == 4 and gamma == F(1, 2):
            status = 'affine' if targets[0]-targets[1]+targets[2]-targets[3] == 0 else 'inconsistent'
            supports.append((active, status, matrix, None, None)); continue
        values = ldl_solution(matrix, [targets[i] for i in active]); x = [F(0)]*4
        for i, v in zip(active, values): x[i] = v
        slacks = [gamma*sum(x[j] for j in range(4) if adjacent(i, j))-targets[i] for i in range(4) if i not in active]
        valid = all(x[i] > 0 for i in active) and all(v >= 0 for v in slacks)
        supports.append((active, 'unique', matrix, x, slacks))
        if valid:
            utility = [targets[i]*x[i]-x[i]**2/2-gamma*x[i]*sum(x[j] for j in range(4) if adjacent(i, j)) for i in range(4)]
            potential = sum(targets[i]*x[i]-x[i]**2/2 for i in range(4))-gamma*sum(x[i]*x[(i+1) % 4] for i in range(4))
            equilibria.append({'actions': x, 'utility': utility, 'welfare': sum(utility), 'potential': potential})
    return supports, equilibria


def check(root=None):
    require(root is None or isinstance(root, (str, Path)), 'root must be a path')
    root = Path(root) if root is not None else Path(__file__).resolve().parents[1]
    original = {p: (root/p).read_bytes() for p in FILES}
    comparisons = rejects = cli_runs = alias_rejections = 0
    def equal(a, b, label):
        nonlocal comparisons
        comparisons += 1
        require(a == b, label+': '+repr(a)[:160]+' != '+repr(b)[:160])
    def reject(fn, label):
        nonlocal rejects
        try: fn()
        except ValueError: rejects += 1
        else: raise ValueError('accepted invalid '+label)
    data = strict_json(original[INPUT]); saved = strict_json(original[OUTPUT]); review = strict_json(original[REVIEW])
    author = strict_json(original[AUTHOR]); sources = strict_json(original[SOURCES]); manifest = strict_json(original[MANIFEST])
    page = Page(); page.feed(original[PAGE].decode()); page.close()
    equal((page.open, page.collect), ([], []), 'complete reader structure')
    points = {f'v13-project-p{i}': v for i, v in enumerate((10, 10, 20, 10, 10, 20, 20), 1)}
    equal(page.prompts, points, 'seven exact prompt allocations'); equal(page.solutions, set(points), 'all paired solutions')
    equal(page.domains, {f'D{i}': 20 for i in range(1, 6)}, 'five essential domains')
    equal(sum(points.values()), 100, 'point total')
    equal(page.downloads, {Path(p).name for p in READER_FILES}, 'flat reader assets')
    equal(page.sources, SOURCE_ROUTES, 'reader primary identities')
    equal({s['id']: s['url'] for s in sources['sources']}, SOURCE_ROUTES, 'source record identities')
    equal(set(review['prompt_solution_audit']), set(points), 'seven peer task audits')
    equal(review['unresolved_findings'], [], 'peer has no unresolved finding')
    for record, expected, label in ((author, set(AUTHOR_FILES)-{AUTHOR}, 'author'), (review, set(FILES)-{REVIEW}, 'peer')):
        equal({b['path'] for b in record['bindings']}, expected, label+' nonself binding set')
        for b in record['bindings']:
            raw = original[b['path']]
            equal((b['bytes'], b['sha256']), (len(raw), sha256(raw).hexdigest()), label+' binding '+b['path'])
    equal({r['file'] for r in manifest['files']}, {Path(p).name for p in (INPUT, MODEL, OUTPUT, README)}, 'four manifest payloads')
    for row in manifest['files']:
        payload = original['content/projects/'+row['file']]
        equal((row['bytes'], row['sha256']), (len(payload), sha256(payload).hexdigest()), 'manifest hash')
    expected_inputs = {'economy.'+x for x in ('discount', 'benefit', 'collaboration_effort_cost', 'review_effort_cost')}
    expected_inputs |= {'economy.good_report_in_G.'+k for k in ('WW', 'WN', 'NW', 'NN')}
    expected_inputs |= {'active_repair.good_report_in_R.'+k for k in ('WW', 'WN', 'NW', 'NN')}
    expected_inputs |= {'restoration_grid', 'garbling_values', 'active_repair.counterfactual_one_worker_good_probability'}
    expected_inputs |= {'paper_case.'+k for k in ('vertices', 'undirected_edges', 'regular_interaction', 'singular_interaction', 'last_target_increase')}
    equal(set(page.inputs), expected_inputs, 'twenty original visible inputs')
    for path, text in page.inputs.items():
        value = data
        for key in path.split('.'): value = value[key]
        equal(compact(text), compact(visible(value)), 'printed input '+path)
    stdout, stderr = StringIO(), StringIO(); before = deepcopy(data)
    with redirect_stdout(stdout), redirect_stderr(stderr):
        api = runpy.run_path(str(root/MODEL)); result = api['run'](data)
    equal((stdout.getvalue(), stderr.getvalue()), ('', ''), 'quiet reader import/API')
    equal(data, before, 'reader pure input'); equal(result, saved, 'fresh versus archived reader output')
    json.dumps(result, allow_nan=False)
    def compare(actual, oracle, label):
        for key, value in oracle.items(): equal(actual[key], serial(value), label+' '+key)
        return oracle
    d, b, c, k = [F(data['economy'][x]) for x in ('discount', 'benefit', 'collaboration_effort_cost', 'review_effort_cost')]
    alpha = F(data['economy']['good_report_in_G']['WW']); beta = F(data['economy']['good_report_in_G']['NW'])
    markers = {}
    def certify_design(changed_data, actual, eta):
        e = changed_data['economy']; discount, benefit, cost = [F(e[x]) for x in ('discount', 'benefit', 'collaboration_effort_cost')]
        a, z = [(1-eta)*F(e['good_report_in_G'][x])+eta/2 for x in ('WW', 'NW')]
        equal(actual['G_law_after_garbling'], {name: str((1-eta)*F(v)+eta/2) for name, v in e['good_report_in_G'].items()}, 'entire garbled law')
        rates = sorted(F(v) for v in changed_data['restoration_grid']); rows = []
        equal(len(actual['grid']), len(rates), 'whole finite menu length')
        for rate, row in zip(rates, actual['grid']):
            equal(row['restoration'], str(rate), 'sorted rate identity')
            rows.append(compare(row, game(changed_data, restoration=rate, noise=eta), 'finite control '+str(rate)))
        feasible = [rate for rate, row in zip(rates, rows) if row['status'] == 'certified']
        equal(actual['feasible_restorations'], serial(feasible), 'complete feasible menu')
        if feasible:
            best = max((row['U'][0], rate) for rate, row in zip(rates, rows) if row['status'] == 'certified')[1]
            equal(actual['best_grid']['restoration'], str(best), 'menu optimum')
        else: equal(actual['best_grid'], None, 'empty menu has no optimum')
        # Multiply the collaboration constraint by its strictly positive denominator.
        ceiling = (discount*(a-z)*(benefit-cost)-cost*(1-discount*a))/(cost*discount)
        cont = actual['continuous']; equal(cont['raw_restoration_ceiling'], str(ceiling), 'linearized global constraint')
        equal(cont['strict_supremum_attained'], ceiling > 1, 'strict attainment')
        boundary = None
        if ceiling < 0:
            equal([cont[x] for x in ('weak_interval', 'weak_optimum', 'strict_interval', 'strict_supremum_U')], [None]*4, 'empty continuous class')
        else:
            top = min(F(1), ceiling); equal(cont['weak_interval'], ['0', str(top)], 'closed clipped weak class')
            boundary = compare(cont['weak_optimum'], game(changed_data, restoration=top, noise=eta), 'weak continuous optimum')
            if ceiling == 0: equal((cont['strict_interval'], cont['strict_supremum_U']), (None, None), 'singleton boundary excludes strict IC')
            else:
                equal(cont['strict_interval'], {'lower': '0', 'upper': str(top), 'lower_included': True, 'upper_included': ceiling > 1}, 'strict endpoint semantics')
                equal(cont['strict_supremum_U'], serial(boundary['U']), 'strict supremum')
        return rows, feasible, ceiling, boundary
    base_rows, feasible, ceiling, boundary = certify_design(data, result['baseline'], F(0))
    for i, row in enumerate(base_rows):
        for tag, field in (('V', 'V'), ('U', 'U'), ('margins', 'alternative_action_margins_G_R'), ('best', 'best_stationary_U_by_start')): markers[f'grid-{i}-{tag}'] = row[field]
        for j, policy in enumerate(row['stationary_own_policies']): markers[f'policy-{i}-{j}'] = policy['U']
    reference = compare(result['reference_restoration_half'], game(data), 'reference')
    for key, actions in zip(('WW', 'WN', 'NW', 'NN'), ((1, 1), (1, 0), (0, 1), (0, 0))):
        x, y = actions; markers['payoff-G-'+key] = (b*y-c*x, b*x-c*y); markers['payoff-R-'+key] = (-k*x, -k*y)
    markers.update({'false-warning': 1-alpha, 'reference-gap': reference['V'][0]-reference['V'][1], 'reference-V': reference['V'],
        'reference-U': reference['U'], 'reference-margins': reference['alternative_action_margins_G_R'],
        'reference-stationary-G': reference['occupancy']['stationary_G'], 'reference-stationary-flow': reference['occupancy']['stationary_per_agent_flow'],
        'reference-discounted-G': reference['occupancy']['discounted_G_by_start'][0], 'reference-patience': c/((alpha-beta)*(b-c)+c*(alpha-F(1, 2))),
        'feasible-grid': feasible, 'best-grid': max(feasible), 'continuous-r': ceiling, 'continuous-V': boundary['V'],
        'continuous-U': boundary['U'], 'continuous-margins': boundary['alternative_action_margins_G_R']})
    noises = []
    for eta, actual in zip(sorted(F(x) for x in data['garbling_values']), result['garbling']): noises.append(certify_design(data, actual, eta))
    equal(len(result['garbling']), len(data['garbling_values']), 'all garbling designs')
    quarter, half = [F(x) for x in data['garbling_values']]
    rows, possible, cap, edge = noises[0]
    markers.update({'noise-quarter-law': [(1-quarter)*p+quarter/2 for p in (alpha, beta)], 'noise-quarter-ceiling': cap, 'noise-quarter-grid': possible,
        'noise-quarter-V': rows[0]['V'], 'noise-quarter-U': rows[0]['U'], 'noise-quarter-margins': rows[0]['alternative_action_margins_G_R'],
        'noise-continuous-V': edge['V'], 'noise-continuous-U': edge['U'], 'noise-continuous-margins': edge['alternative_action_margins_G_R'],
        'noise-half-law': [(1-half)*p+half/2 for p in (alpha, beta)], 'noise-half-ceiling': noises[1][2],
        'noise-half-zero-margin': noises[1][0][0]['alternative_action_margins_G_R'][0],
        'garbling-cutoff': ceiling/(alpha-F(1, 2)+(alpha-beta)*(b-c)/c)})
    active = compare(result['active_repair'], game(data, (1, 1), repair=True), 'active repair')
    changed = compare(result['changed_off_path_repair'], game(data, (1, 1), repair=True, changed=True), 'changed off-path repair')
    gains = [x-y for x, y in zip(active['U'], reference['U'])]; equal(result['repair_gain_over_reference_U'], serial(gains), 'cost-inclusive repair gains')
    equal((active['V'], active['on_path_good_probabilities'], active['current_per_agent_flow']), (changed['V'], changed['on_path_good_probabilities'], changed['current_per_agent_flow']), 'same compliant observations')
    for tag, row in (('repair', active), ('changed', changed)):
        for j, policy in enumerate(row['stationary_own_policies']): markers[f'{tag}-policy-{j}'] = policy['U']
    markers.update({'repair-V': active['V'], 'repair-U': active['U'], 'repair-margins': active['alternative_action_margins_G_R'], 'repair-gain': gains,
        'repair-stationary-G': active['occupancy']['stationary_G'], 'repair-stationary-flow': active['occupancy']['stationary_per_agent_flow'],
        'repair-discounted-G': active['occupancy']['discounted_G_by_start'][0], 'changed-repair-margins': changed['alternative_action_margins_G_R'],
        'changed-repair-best': changed['best_stationary_U_by_start']})
    compare(result['always_N_equilibrium'], game(data, (0, 0)), 'always N equilibrium')
    def compare_graph(actual, gamma, target):
        supports, equilibria = network(gamma, target)
        equal(actual['isolated_or_endpoint_equilibria'], serial(equilibria), 'all isolated/endpoint network equilibria')
        equal(len(actual['support_audits']), 16, 'complete support set')
        for row, (support, status, matrix, x, slack) in zip(actual['support_audits'], supports):
            equal(row['positive_support'], [i+1 for i in support], 'support label')
            equal(row['linear_system']['status'], status, 'LDL/null-vector status')
            if x is not None:
                equal(row['candidate'], serial(x), 'independent principal-system solution')
                equal(row['inactive_slacks'], serial(slack), 'all excluded-agent inequalities')
                equal(row['is_equilibrium'], all(x[i] > 0 for i in support) and all(s >= 0 for s in slack), 'strict active support')
            elif status == 'affine':
                system = row['linear_system']; particular = [F(x) for x in system['particular']]
                equal([sum(a*b for a, b in zip(r, particular)) for r in matrix], target, 'affine particular compatibility')
                equal(len(system['nullspace']), 1, 'critical nullity')
                equal([sum(a*F(b) for a, b in zip(r, system['nullspace'][0])) for r in matrix], [F(0)]*4, 'actual reported null vector')
        return equilibria
    gamma = F(data['paper_case']['regular_interaction']); epsilon = F(data['paper_case']['last_target_increase'])
    regular = compare_graph(result['paper']['regular'], gamma, [F(1)]*4)[0]
    compare_graph(result['paper']['critical'], F(1, 2), [F(1)]*4)
    shifted = compare_graph(result['paper']['changed_target'], F(1, 2), [F(1)]*3+[1+epsilon])[0]
    family = result['paper']['critical']['complete_family']
    equal((family['actions'], family['interval'], family['welfare_polynomial_coefficients_constant_linear_quadratic']),
          (['a', '1-a', 'a', '1-a'], ['0', '1'], ['1', '-2', '2']), 'closed all-a family and polynomial')
    equal((family['parameter'], family['welfare_range'], family['potential']), ('a', ['1/2', '1'], '1'), 'actual family range and potential')
    equal((result['paper']['regular']['complete_family'], result['paper']['changed_target']['complete_family']), (None, None), 'unique cases have no affine family')
    for name in ('regular', 'critical', 'changed_target'):
        equal(result['paper'][name]['equilibrium_set_kind'], 'continuum' if name == 'critical' else 'finite', 'singularity not silently discarded')
    # Exact eigenvectors certify rank three at the critical interaction.
    for vector, eigen in (((1, 1, 1, 1), 2), ((1, 0, -1, 0), 1), ((0, 1, 0, -1), 1), ((1, -1, 1, -1), 0)):
        equal([F(vector[i])+F(1, 2)*(vector[(i-1) % 4]+vector[(i+1) % 4]) for i in range(4)], [F(eigen*v) for v in vector], 'cycle spectral rank certificate')
    # Polynomial coefficients establish the universal identity; sample values alone would not.
    equal([1-2*F(1, 2), -1+2*F(1, 2)], [0, 0], 'family best-reply coefficient identity')
    markers.update({'paper-contraction': 2*gamma, 'paper-regular-actions': regular['actions'], 'paper-regular-welfare': regular['welfare'],
        'paper-regular-potential': regular['potential'], 'paper-critical-welfare-range': (F(1, 2), F(1)), 'paper-critical-potential': F(1),
        'paper-changed-actions': shifted['actions'], 'paper-changed-welfare': shifted['welfare']})
    equal(set(page.results), set(markers), 'all 101 visible result identities')
    for label, value in markers.items(): equal(compact(page.results[label]), compact(visible(value)), 'printed result '+label)
    interventions = []
    for desired in (F(-1, 20), F(0), F(1), F(5, 4)):
        change = deepcopy(data); change['economy']['benefit'] = str(c+c*(desired-alpha+1/d)/(alpha-beta))
        out = api['run'](change); certify_design(change, out['baseline'], F(0)); interventions.append('ceiling '+str(desired))
    change = deepcopy(data); cutoff = markers['garbling-cutoff']; change['garbling_values'] = [str(x) for x in (0, cutoff-F(1, 1000), cutoff, cutoff+F(1, 1000), 1)]
    out = api['run'](change)
    for eta, row in zip(map(F, change['garbling_values']), out['garbling']): certify_design(change, row, eta)
    interventions.append('both sides and exact garbling cutoff, identity and complete garbling')
    for patience in (markers['reference-patience']-F(1, 1000), markers['reference-patience'], markers['reference-patience']+F(1, 1000)):
        change = deepcopy(data); change['economy']['discount'] = str(patience)
        out = api['run'](change); compare(out['reference_restoration_half'], game(change), 'patience boundary')
    interventions.append('weak patience equality and neighboring incentive signs')
    threshold = F(data['active_repair']['good_report_in_R']['WW'])-k/(d*(active['V'][0]-active['V'][1]))
    for sigma in (threshold, threshold+F(1, 1000)):
        change = deepcopy(data); change['active_repair']['counterfactual_one_worker_good_probability'] = str(sigma)
        out = api['run'](change); compare(out['changed_off_path_repair'], game(change, (1, 1), repair=True, changed=True), 'exact repair deviation boundary')
    interventions.append('same-observation repair equality and violation')
    change = deepcopy(data); change['paper_case']['regular_interaction'] = '1/3'; change['paper_case']['last_target_increase'] = '1'
    change['paper_case']['undirected_edges'] = [[4, 1], [4, 3], [3, 2], [2, 1]]
    out = api['run'](change); compare_graph(out['paper']['regular'], F(1, 3), [F(1)]*4); compare_graph(out['paper']['changed_target'], F(1, 2), [F(1)]*3+[F(2)])
    interventions.append('relabeled edge order, altered regular interaction and endpoint target')
    def altered(path, value):
        copy = deepcopy(data); cursor = copy
        for name in path[:-1]: cursor = cursor[name]
        cursor[path[-1]] = value
        return copy
    invalid = [(('schema_version',), True), (('economy', 'discount'), 0.8), (('economy', 'discount'), '0.8'),
        (('economy', 'discount'), '1/0'), (('economy', 'discount'), '+4/5'), (('economy', 'discount'), ' 4/5'),
        (('economy', 'discount'), '0'), (('economy', 'discount'), '1'), (('economy', 'benefit'), '1'),
        (('economy', 'collaboration_effort_cost'), '0'), (('economy', 'review_effort_cost'), '0'), (('economy', 'initial_state'), 'R'),
        (('economy', 'good_report_in_G', 'WW'), '1'), (('economy', 'good_report_in_G', 'NN'), '0'),
        (('economy', 'good_report_in_G', 'NW'), '1/2'), (('restoration_grid',), []), (('restoration_grid',), ['1/2', '2/4']),
        (('garbling_values',), ['-1']), (('active_repair', 'good_report_in_R', 'NW'), '1/3'),
        (('active_repair', 'counterfactual_one_worker_good_probability'), '3/2'), (('paper_case', 'vertices'), True),
        (('paper_case', 'undirected_edges'), [[1, 1], [1, 2], [2, 3], [3, 4]]),
        (('paper_case', 'regular_interaction'), '1/2'), (('paper_case', 'singular_interaction'), '1/3'),
        (('paper_case', 'last_target_increase'), '0'), (('paper_case', 'last_target_increase'), '2')]
    for path, value in invalid: reject(lambda p=path, v=value: api['run'](altered(p, v)), str(path))
    extra = deepcopy(data); extra['unknown'] = 1
    missing = deepcopy(data); del missing['economy']['benefit']
    for bad in ([], extra, missing): reject(lambda x=bad: api['run'](x), 'schema')
    for text in ('{"a":1,"a":2}', '{"a":NaN}', '{"a":Infinity}', '{"a":1e999}', '{"a":0.8}'):
        reject(lambda t=text: api['strict_loads'](t), 'JSON syntax/number')
    # Bounded actual external executions; never touch the delivered reader files.
    with tempfile.TemporaryDirectory(prefix='v13-peer-reader-') as folder:
        temporary = Path(folder)
        for path in READER_FILES: (temporary/Path(path).name).write_bytes(original[path])
        protected = [temporary/Path(p).name for p in (INPUT, MODEL, README, MANIFEST)]
        protected_bytes = {p: p.read_bytes() for p in protected}
        for flags in ([], ['-O']):
            command = [sys.executable, '-B', *flags, str(temporary/Path(MODEL).name)]
            proc = subprocess.run(command, cwd='/', capture_output=True); cli_runs += 1
            equal((proc.returncode, proc.stdout, proc.stderr), (0, b'', b''), 'actual quiet reader default')
            equal(strict_json((temporary/Path(OUTPUT).name).read_bytes()), result, 'actual reader output')
            for kind, target in (('direct', protected[2]), ('symlink', protected[0]), ('hardlink', protected[1])):
                destination = target if kind == 'direct' else temporary/('alias-'+kind)
                if kind == 'symlink': destination.symlink_to(target)
                if kind == 'hardlink': destination.hardlink_to(target)
                proc = subprocess.run(command+['--output', str(destination)], cwd='/', capture_output=True); alias_rejections += 1
                equal(proc.returncode != 0 and proc.stdout == b'' and bool(proc.stderr), True, 'actual '+kind+' rejection')
                equal({p: p.read_bytes() for p in protected}, protected_bytes, 'protected bytes after '+kind)
                if kind != 'direct': destination.unlink()
            alternate = temporary/'alternate.json'; alternate.write_bytes(original[INPUT]); destination = temporary/'answer.json'
            proc = subprocess.run(command+['--input', str(alternate), '--output', str(destination)], cwd='/', capture_output=True); cli_runs += 1
            equal((proc.returncode, proc.stdout, proc.stderr), (0, b'', b''), 'explicit reader paths')
            equal(strict_json(destination.read_bytes()), result, 'explicit computed result')
            alternate.write_text('{"schema_version":1,"schema_version":1}'); destination.write_bytes(b'keep')
            proc = subprocess.run(command+['--input', str(alternate), '--output', str(destination)], cwd='/', capture_output=True); cli_runs += 1
            equal(proc.returncode != 0 and proc.stdout == b'' and bool(proc.stderr), True, 'actual malformed CLI rejection')
            equal(destination.read_bytes(), b'keep', 'malformed input preserves existing output')
            alternate.unlink(); destination.unlink()
        equal({p.name for p in temporary.iterdir()}, {Path(p).name for p in READER_FILES}, 'exact reader membership')
        equal({p: p.read_bytes() for p in protected}, protected_bytes, 'all protected bytes preserved')
    equal({p: (root/p).read_bytes() for p in FILES}, original, 'eleven delivered payloads unchanged')
    summary = {'volume': 'v13', 'component': 'project', 'peer': 'ito_author', 'status': 'passed', 'comparisons': comparisons,
        'domain_rejections': rejects, 'reader_cli_runs': cli_runs, 'protected_output_rejections': alias_rejections,
        'solved_tasks': 7, 'points': 100, 'essential_domains': 5, 'visible_inputs': len(page.inputs), 'visible_results': len(markers),
        'runtime_files': 11, 'independent_interventions': interventions,
        'limits': 'Exact finite evidence plus separate complete proof review; no empirical validation, unrestricted equilibrium selection, rendered UI or learner certification.'}
    json.dumps(summary, allow_nan=False)
    return summary


if __name__ == '__main__':
    require(len(sys.argv) == 1, 'quiet peer CLI takes no arguments')
    check()
