"""Independent exact arithmetic and bounded path checks for v06-c02.

Rational aggregate ledgers, perfect-power roots, polynomial certificates and
stock/service observational equivalence are checked separately from the lab.
Finite path/grid checks supplement, and never establish, global convergence.
check() is quiet and directly JSON serializable; standard library only.
"""
from contextlib import redirect_stdout
from fractions import Fraction as F
from html.parser import HTMLParser
from io import StringIO
from itertools import product
from pathlib import Path
import ast
import runpy
from types import SimpleNamespace
import json
import math

ROOT = Path(__file__).resolve().parents[1]
CHAPTER = ROOT / 'content/chapters/v06-c02.html'
SOURCES = ROOT / 'content/reviews/v06-c02-sources.json'
LAB = ROOT / 'content/projects/v06-c02-solow.py'
README = ROOT / 'content/projects/v06-c02-README.txt'


def require(condition, message):
    if not condition:
        raise ValueError(message)


class Structure(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.lists, self.ids, self.sources, self.links = [], [], [], [], []
        self.worked = self.exercises = self.solutions = self.blocks = self.h1 = 0
        self.in_solutions = False
        self.words = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag not in ('br', 'hr', 'img', 'input', 'meta', 'link'):
            self.stack.append(tag)
        self.h1 += tag == 'h1'
        if 'id' in attrs:
            self.ids.append(attrs['id'])
        if 'data-source' in attrs:
            self.sources.append(attrs['data-source'])
        if tag == 'a':
            self.links.append(attrs.get('href', ''))
        self.worked += tag == 'aside' and attrs.get('class') == 'worked'
        if tag == 'details' and attrs.get('class') == 'solutions':
            self.in_solutions = True
            self.blocks += 1
        if tag == 'ol':
            self.lists.append(attrs.get('class'))
        if tag == 'li' and self.lists:
            self.exercises += self.lists[-1] == 'exercises'
            self.solutions += self.in_solutions

    def handle_endtag(self, tag):
        require(self.stack and self.stack.pop() == tag, 'unbalanced HTML: ' + tag)
        if tag == 'ol':
            self.lists.pop()
        if tag == 'details':
            self.in_solutions = False

    def handle_data(self, data):
        self.words.extend(data.split())


def integer_root(value, degree):
    """Integer bisection, accepting only exact nonnegative perfect powers."""
    require(isinstance(value, int) and value >= 0 and degree >= 2, 'root domain')
    lo, hi = 0, max(1, value)
    while lo <= hi:
        mid = (lo + hi) // 2
        power = mid ** degree
        if power == value:
            return mid
        if power < value:
            lo = mid + 1
        else:
            hi = mid - 1
    raise ValueError('not a perfect power')


def root(value, degree=2):
    value = F(value)
    return F(integer_root(value.numerator, degree), integer_root(value.denominator, degree))


def effective_factors(delta, n, g):
    gamma = (1 + n) * (1 + g)
    return gamma, gamma - 1 + delta


def aggregate_ledger(K, A, L, s, delta, n, g):
    """Independent exact square-root production from the dated aggregate stock."""
    Y = root(K * A * L)
    I, C, depreciation = s * Y, (1 - s) * Y, delta * K
    next_K, next_A, next_L = K + I - depreciation, A * (1 + g), L * (1 + n)
    return {'Y': Y, 'I': I, 'C': C, 'depreciation': depreciation,
            'net_investment': I - depreciation, 'next_K': next_K,
            'next_A': next_A, 'next_L': next_L,
            'next_k': next_K / (next_A * next_L),
            'next_worker_k': next_K / next_L}


def transition(k, s, delta, n, g, degree=2):
    gamma, _ = effective_factors(delta, n, g)
    return ((1 - delta) * k + s * root(k, degree)) / gamma


def strings(record):
    return {key: str(value) for key, value in record.items()}


def near(actual, expected, message, rel=2e-12, absolute=2e-12):
    require(math.isclose(actual, float(expected), rel_tol=rel, abs_tol=absolute), message)


def check():
    checks, results = [], {}
    manuscript = CHAPTER.read_text(encoding='utf-8')
    parser = Structure()
    parser.feed(manuscript)
    require(not parser.stack, 'HTML remains open')
    require(parser.h1 == 0 and parser.worked == 3, 'fragment/three worked cases')
    require(parser.exercises == parser.solutions == 8 and parser.blocks == 1, 'eight aligned solution slots')
    require(len(parser.ids) == len(set(parser.ids)) and
            all(i.startswith('v06-c02-') for i in parser.ids), 'unique prefixed IDs')
    require('Teach-back' in manuscript and 'Delayed check' in manuscript and
            'Delayed-check answer' in manuscript, 'teaching gates')
    require({'v06-c01.html', 'v06-c03.html'}.issubset(parser.links), 'adjacent routes')
    proposals = json.loads(SOURCES.read_text(encoding='utf-8'))
    ids = [s['id'] for s in proposals]
    require(len(ids) == len(set(ids)) == 3 and set(ids) == set(parser.sources), 'source alignment')
    fields = {'id', 'title', 'url', 'use', 'checked', 'verification'}
    require(all(set(s) == fields and s['id'].startswith('v06-c02-') and
                s['checked'] == '2026-10-08' and s['url'] in parser.links for s in proposals),
            'source schema and actual citation links')
    for asset in (LAB, README):
        require(asset.name in parser.links and 'projects/' + asset.name not in parser.links,
                'flat asset route: ' + asset.name)
        require(asset.is_file(), 'asset exists')
    ast.parse(LAB.read_text(encoding='utf-8'))
    require('40 transition rows' in README.read_text(encoding='utf-8'), 'documented horizon')
    results['structure'] = {'worked': parser.worked, 'exercises': parser.exercises,
                            'solutions': parser.solutions, 'text_words': len(parser.words),
                            'source_ids': ids, 'download_files': [LAB.name, README.name]}
    checks.append('balanced fragment, unique IDs, 3 worked/8 solved exercises, retention, source alignment and flat assets')

    alpha, s, delta, n, g = F(1, 2), F(1, 4), F(1, 25), F(1, 10), F(1, 10)
    gamma, d = effective_factors(delta, n, g)
    require((gamma, d) == (F(121, 100), F(1, 4)), 'exact cross term')
    first = aggregate_ledger(F(25), F(1), F(100), s, delta, n, g)
    expected_first = {'Y': F(50), 'I': F(25, 2), 'C': F(75, 2), 'depreciation': F(1),
                      'net_investment': F(23, 2), 'next_K': F(73, 2),
                      'next_A': F(11, 10), 'next_L': F(110),
                      'next_k': F(73, 242), 'next_worker_k': F(73, 220)}
    require(first == expected_first, 'worked 1 aggregate exact references')
    initial_k = F(1, 4)
    normalized_change = (s * root(initial_k) - d * initial_k) / gamma
    require(normalized_change == F(25, 484) and initial_k + normalized_change == first['next_k'],
            'worked 1 independent normalized change')
    require(transition(F(1), s, delta, n, g) == 1, 'worked 1 fixed point')
    require((s / (delta + n + g)) ** 2 == F(625, 576), 'approximate maintenance misspecification')
    require(gamma - 1 == F(21, 100) and gamma / (1 + n) - 1 == g, 'aggregate versus worker growth')
    results['worked_1'] = strings(first) | {'Gamma': str(gamma), 'd': str(d),
                                            'delta_k': str(normalized_change),
                                            'approximate_k_star': '625/576'}
    checks.append('dated physical stock/flow ledger and exact future-worker denominator, cross-term approximation error')

    up = aggregate_ledger(F(100), F(1), F(100), F(1, 2), delta, n, g)
    down = aggregate_ledger(F(900), F(1), F(100), F(1, 2), delta, n, g)
    require(up['next_k'] == F(146, 121) and up['C'] / 100 == F(1, 2), 'saving increase impact')
    require(down['next_k'] == F(1014, 121) and down['C'] / 100 == F(3, 2), 'saving reduction impact')
    require(F(1) < up['next_k'] < 4 < down['next_k'] < 9, 'saving transition first-step bounds')
    for saving, k_star, c_star in ((F(1, 4), F(1), F(3, 4)),
                                  (F(1, 2), F(4), F(1)),
                                  (F(3, 4), F(9), F(3, 4))):
        require(saving * root(k_star) == d * k_star, 'steady resource condition')
        require((1 - saving) * root(k_star) == c_star, 'steady consumption')
    require(alpha / root(F(4)) == d and F(1, 2) == d * 4 / root(F(4)), 'golden FOC/feasible saving')
    results['worked_2'] = {'saving_increase_next_k': str(up['next_k']),
                            'saving_reduction_next_k': str(down['next_k']),
                            'golden_k': '4', 'golden_c': '1',
                            'above_golden_consumption_floor': '1', 'old_high_saving_c': '3/4'}
    checks.append('saving-change aggregate ledgers, golden-rule resource/first-order conditions and transition bounds')

    # Independent exact one-step sign/no-overshoot checks: not a global proof.
    case_count = comparison_count = 0
    for saving, depreciation, labor_growth, efficiency_growth in product(
            (F(1, 10), F(1, 4), F(1, 2), F(1)),
            (F(0), F(1, 25), F(1)), (F(0), F(1, 10)), (F(0), F(1, 10), F(1, 5))):
        gross, maintenance = effective_factors(depreciation, labor_growth, efficiency_growth)
        if maintenance == 0:
            continue
        destination = (saving / maintenance) ** 2
        rho = ((1 - depreciation) + alpha * maintenance) / gross
        require(rho == 1 - (1 - alpha) * maintenance / gross and alpha <= rho < 1,
                'local multiplier identity and bound')
        points = sorted({F(i, 8) ** 2 for i in range(1, 33)} | {destination})
        previous_next = None
        for current in points:
            following = transition(current, saving, depreciation, labor_growth, efficiency_growth)
            difference = (saving * root(current) - maintenance * current) / gross
            require(following - current == difference, 'exact normalized change identity')
            if current < destination:
                require(current < following < destination, 'below fixed point no overshoot')
            elif current > destination:
                require(destination < following < current, 'above fixed point no overshoot')
            else:
                require(following == current, 'positive fixed point')
            if previous_next is not None:
                require(previous_next < following, 'strict monotonicity on distinct grid inputs')
            previous_next = following
            comparison_count += 1
        case_count += 1
    require(1 - (1 - alpha) * d / gamma == F(217, 242), 'worked local multiplier')
    results['stability_checks'] = {'parameter_cases': case_count,
                                   'exact_one_step_comparisons': comparison_count,
                                   'worked_local_multiplier': '217/242',
                                   'scope': 'Finite checks supplement the separately reviewed monotone bounded-sequence proof.'}
    checks.append('exact change identities, no-overshoot signs and local multiplier bounds across positive-state cases')

    golden_checks = 0
    for maintenance in (F(1, 10), F(1, 4), F(3, 5), F(2)):
        x_gr = 1 / (2 * maintenance)  # x = sqrt(k)
        c_gr = 1 / (4 * maintenance)
        # Coefficients certify c(x)-c_GR = -d*(x-x_GR)^2 for every real x.
        require((-maintenance, F(1), -c_gr) ==
                (-maintenance, 2 * maintenance * x_gr, -maintenance * x_gr ** 2),
                'global polynomial consumption certificate')
        for i in range(101):
            saving = F(i, 100)
            x = saving / maintenance
            consumption = x - maintenance * x * x
            require(consumption == (1 - saving) * x, 'consumption resource identity')
            require(c_gr - consumption == maintenance * (x - x_gr) ** 2 >= 0,
                    'global consumption gap')
            golden_checks += 1
    results['golden_certificates'] = {'maintenance_cases': 4, 'exact_feasible_points': golden_checks,
                                      'identity': 'c_GR-c(x)=d*(x-1/(2d))^2, x=sqrt(k), alpha=1/2'}
    checks.append('independent completed-square global golden-rule certificate, endpoints and feasible saving grid')

    # Worked residual: exact gross factors and an independently reconstructed alternative technology.
    K0, K1, L0, L1, Y0, Y1 = map(F, (100, 121, 100, 100, 100, 121))
    z_factor = (Y1 / Y0) / (root(K1 / K0) * root(L1 / L0))
    require(z_factor == F(11, 10) and z_factor ** 2 == F(121, 100), 'worked Z versus A factors')
    ordinary_residual = (Y1 / Y0 - 1) - alpha * (K1 / K0 - 1)
    require(ordinary_residual == F(21, 200) != z_factor - 1, 'ordinary-percent approximation gap')
    true_A, u0, u1 = F(5, 4), F(4, 5), F(121, 125)
    require(0 < u0 <= 1 and 0 < u1 <= 1, 'utilization bounds')
    require(root(u0 * K0 * true_A * L0) == Y0 and
            root(u1 * K1 * true_A * L1) == Y1, 'identical observables with constant true A')
    near(math.log(float(Y1 / Y0)), alpha * math.log(float(K1 / K0)) + math.log(float(z_factor)),
         'exact log accounting identity within floating evaluation')
    results['worked_3'] = {'Z_factor': str(z_factor), 'maintained_A_factor': str(z_factor ** 2),
                            'naive_percentage_residual': str(ordinary_residual),
                            'constant_alternative_A': str(true_A), 'u0': str(u0), 'u1': str(u1),
                            'reproduced_Y': ['100', '121']}
    checks.append('exact growth-factor accounting, log identity, A/Z distinction and utilization observational equivalence')

    exercise = aggregate_ledger(F(36), F(2), F(50), F(3, 10), F(1, 10), F(1, 5), F(1, 4))
    require(exercise == {'Y': F(60), 'I': F(18), 'C': F(42), 'depreciation': F(18, 5),
                         'net_investment': F(72, 5), 'next_K': F(252, 5),
                         'next_A': F(5, 2), 'next_L': F(60), 'next_k': F(42, 125),
                         'next_worker_k': F(21, 25)}, 'exercise 1 complete ledger')
    require(exercise['next_K'] / 36 == F(7, 5) and
            exercise['next_k'] - F(9, 25) == -F(3, 125), 'aggregate up normalized down')
    require(transition(F(1, 4), F(3, 10), F(1, 10), F(1, 5), F(1, 4)) == F(1, 4), 'exercise 1 destination')
    require(transition(F(8), F(2, 5), F(1, 10), F(0), F(0), degree=3) == 8, 'exercise 2 cube-root destination')
    require((1 - F(2, 5)) * root(F(8), 3) == F(6, 5), 'exercise 2 consumption')
    require(1 < transition(F(1), F(2, 5), F(1, 10), F(0), F(0), degree=3) < 8 and
            8 < transition(F(27), F(2, 5), F(1, 10), F(0), F(0), degree=3) < 27,
            'exercise 2 opposite initial sides')
    require(1 - (1 - F(1, 3)) * F(1, 10) == F(14, 15), 'exercise 2 local multiplier')
    new_gamma, new_d = effective_factors(delta, n, F(1, 5))
    new_k, new_y = (s / new_d) ** 2, s / new_d
    require((new_gamma, new_d, new_k, new_y, (1 - s) * new_y) ==
            (F(33, 25), F(9, 25), F(625, 1296), F(25, 36), F(25, 48)), 'exercise 3 faster g')
    require(transition(new_k, s, delta, n, F(1, 5)) == new_k, 'exercise 3 actual fixed point')
    require(new_gamma / (1 + n) == F(6, 5), 'exercise 3 asymptotic worker factor')
    # Doubling A at fixed K,L doubles Y squared, then leaves the normalized destination unchanged.
    require((F(100) * F(2) * F(100)) / (F(100) * F(1) * F(100)) == 2,
            'exercise 3 impact output factor squared')
    require((F(2) * root(F(1))) / (F(1) * root(F(1))) == 2, 'exercise 3 eventual level factor')
    target_tests = 0
    for i in range(101):
        saving = F(i, 100)
        consumption = 4 * saving * (1 - saving)
        require(consumption == 1 - 4 * (saving - F(1, 2)) ** 2, 'exercise 4 inverse-target square identity')
        require((consumption >= F(24, 25)) == (F(2, 5) <= saving <= F(3, 5)),
                'exercise 4 saving interval')
        target_tests += 1
    require((F(3, 5) / d) ** 2 == F(144, 25), 'exercise 4 initial stock')
    require(root(F(144, 25)) / 2 == F(6, 5) and F(1) > F(24, 25), 'exercise 4 consumption dominance floor')
    results['exercises_1_to_4'] = {'exercise_1': strings(exercise),
                                   'exercise_2': {'k': '8', 'c': '6/5', 'rho': '14/15'},
                                   'exercise_3': {'Gamma': str(new_gamma), 'd': str(new_d),
                                                  'k': str(new_k), 'y': str(new_y), 'c': '25/48'},
                                   'exercise_4': {'saving_interval': ['2/5', '3/5'],
                                                  'impact_c': '6/5', 'target_tests': target_tests}}
    checks.append('exercises 1–4: complete ledger, cube-root steady state, changed growth versus level, inverse target and transition dominance')

    require(transition(F(0), s, delta, n, g) == 0, 'zero capital absorbing boundary')
    no_save_factor = (1 - delta) / gamma
    require(0 < no_save_factor < 1 and no_save_factor == F(96, 121), 'zero saving geometric decay')
    require(transition(F(1), F(0), F(1), F(0), F(0)) == 0, 'no saving/full depreciation one-step exhaustion')
    require(transition(F(16), F(1), delta, n, g) == 16 and (1 - F(1)) * root(F(16)) == 0,
            'full saving zero consumption')
    require(effective_factors(F(0), F(0), F(0)) == (1, 0), 'zero maintenance case')
    for k in (F(1), F(4), F(16), F(100), F(10000)):
        following = transition(k, s, F(0), F(0), F(0))
        require(following - k == s * root(k) > 0, 'zero maintenance positive increments')
        require(following / k - 1 == s / root(k), 'zero maintenance declining proportional growth formula')
    require(transition(F(1), s, F(1), F(0), F(0)) == F(1, 4), 'full replacement first step')
    require(transition(F(1, 16), s, F(1), F(0), F(0)) == F(1, 16), 'full replacement destination')
    require(1 - F(1, 10) + F(1, 5) == F(11, 10), 'changed linear technology growth')
    for t in range(12):
        A_P, A_Q = 4 * (1 + g) ** t, (1 + g) ** t
        require(A_P * root(F(1)) / (A_Q * root(F(4))) == 2, 'exercise 6 constant income ratio')
    results['exercises_5_and_6'] = {'no_saving_factor': str(no_save_factor),
                                    'full_replacement_next_k': '1/4', 'full_replacement_k_star': '1/16',
                                    'altered_linear_technology_factor': '11/10',
                                    'P_Q_worker_output_ratio': '2'}
    checks.append('zero capital/saving, full saving/replacement, zero maintenance and changed-return boundaries; conditional-convergence counterexample')

    K_factor, L_factor, Y_factor = F(36, 25), F(121, 100), F(363, 250)
    factor_capital, factor_labor = root(K_factor), root(L_factor)
    residual = Y_factor / (factor_capital * factor_labor)
    naive = (Y_factor - 1) - alpha * (K_factor - 1) - (1 - alpha) * (L_factor - 1)
    require((factor_capital, factor_labor, residual, residual ** 2, Y_factor / L_factor, naive) ==
            (F(6, 5), F(11, 10), F(11, 10), F(121, 100), F(6, 5), F(127, 1000)),
            'exercise 7 all exact growth quantities')
    near(math.log(float(Y_factor)), math.log(float(factor_capital)) +
         math.log(float(factor_labor)) + math.log(float(residual)), 'exercise 7 logarithms')
    require(transition(F(1), F(2, 5), F(1, 5), F(0), F(0)) == F(6, 5), 'delayed first step')
    require(transition(F(4), F(2, 5), F(1, 5), F(0), F(0)) == F(4), 'delayed fixed point')
    require((1 - F(2, 5)) * root(F(4)) == F(6, 5), 'delayed consumption')
    require(alpha / root(F(25, 4)) == F(1, 5) and (1 - alpha) * root(F(25, 4)) == F(5, 4),
            'delayed golden benchmark')
    results['exercise_7_and_retention'] = {'Z_factor': str(residual), 'A_factor': str(residual ** 2),
                                          'worker_output_factor': str(Y_factor / L_factor),
                                          'incorrect_arithmetic_residual': str(naive),
                                          'delayed_next_k': '6/5', 'delayed_k_star': '4',
                                          'delayed_c_star': '6/5', 'delayed_golden_k': '25/4',
                                          'delayed_golden_c': '5/4'}
    checks.append('exercise 7 finite-factor/log accounting and complete delayed numerical answer; exercise 8 assessed by separate prose review')

    buffer = StringIO()
    with redirect_stdout(buffer):
        module = SimpleNamespace(**runpy.run_path(str(LAB)))
        benchmark = module.benchmark()
    require(buffer.getvalue() == '', 'lab import and API are quiet')
    require(benchmark['fixed_parameters'] == {'alpha': '1/2', 'delta': '1/25', 'n': '1/10',
                                               'g': '1/10', 'Gamma': '121/100', 'd': '1/4'},
            'fixed fixture parameter labels')
    references = {'accumulation': (F(1, 4), F(1, 4), first, F(1)),
                   'saving_increase': (F(1), F(1, 2), up, F(4)),
                   'saving_reduction': (F(9), F(1, 2), down, F(4))}
    terminal = {}
    row_count = 0
    for name, (start_k, saving, first_ref, destination) in references.items():
        scenario = benchmark['scenarios'][name]
        rows = scenario['rows']
        require(len(rows) == 40 and scenario['terminal']['t'] == 40, 'documented transition count')
        for key in ('Y', 'I', 'C', 'depreciation', 'net_investment', 'next_K', 'next_A', 'next_L', 'next_k'):
            near(rows[0][key], first_ref[key], 'lab exact first-step reference: ' + name + '/' + key)
        k = float(start_k)
        for t, row in enumerate(rows):
            require(row['t'] == t, 'dated row sequence')
            # Separate normalized recurrence, using exact factors converted once.
            next_k = (float(1 - delta) * k + float(saving) * math.sqrt(k)) / float(gamma)
            near(row['k'], k, 'independent recurrence state')
            near(row['next_k'], next_k, 'independent recurrence update')
            near(row['Y'], row['I'] + row['C'], 'aggregate resource identity')
            near(row['next_K'] - row['K'], row['net_investment'], 'stock/flow identity')
            near(row['next_k'], row['next_K'] / (row['next_A'] * row['next_L']), 'future denominator')
            near(row['normalized_discrepancy'], 0, 'aggregate/normalized numerical reconciliation')
            if start_k < destination:
                require(k < next_k < float(destination), 'finite upward path')
            else:
                require(float(destination) < next_k < k, 'finite downward path')
            if name == 'saving_reduction':
                require(row['c'] >= 1 > F(3, 4), 'finite consumption dominance')
            k = next_k
            row_count += 1
        near(scenario['terminal']['k'], k, 'terminal state horizon')
        near(scenario['positive_steady']['k'], destination, 'theoretical lab destination')
        require(abs(k - float(destination)) < abs(float(start_k - destination)), 'finite gap shrinks')
        terminal[name] = scenario['terminal']['k']
    zero = module.simulate(0, 0.5, 5)
    require(zero['zero_capital_boundary'] and all(row['K'] == row['Y'] == row['next_k'] == 0
                                                for row in zero['rows']), 'lab zero absorbing state')
    no_save = module.simulate(1, 0, 5)
    require(no_save['positive_steady'] is None, 'lab absent positive steady with zero saving')
    near(no_save['terminal']['k'], no_save_factor ** 5, 'lab no-save terminal exact reference')
    all_save = module.simulate(1, 1, 5)
    require(all(row['C'] == 0 for row in all_save['rows']), 'lab full-save zero consumption')
    invalid = [(-1, 0.5, 40), (1, -0.1, 40), (1, 1.1, 40), (True, 0.5, 40),
               (1, False, 40), (float('nan'), 0.5, 40), (1, float('inf'), 40),
               (1, 0.5, True), (1, 0.5, 0), (1, 0.5, 201), (1, 0.5, 4.5), ('1', 0.5, 40)]
    for args in invalid:
        try:
            module.simulate(*args)
        except ValueError:
            pass
        else:
            raise ValueError('invalid lab input accepted: ' + repr(args))
    json.dumps(benchmark, allow_nan=False)
    results['lab'] = {'transition_rows': row_count, 'horizon': 40, 'terminal_k': terminal,
                      'invalid_inputs_rejected': len(invalid), 'boundary_runs': 3,
                      'json_serializable': True}
    checks.append('three independent 40-period ledger/normalized paths, exact first steps, boundary runs, input rejection and quiet JSON lab')

    report = {'chapter': 'v06-c02', 'status': 'passed', 'checks': checks, 'results': results,
              'limitations': [
                  'Exact arithmetic, polynomial certificates and finite grids supplement the separate full proof/prose review.',
                  'Finite trajectories do not prove global convergence, a limiting growth rate or causal identification.',
                  'The author/root review separately assesses exercise 8 and the qualitative answers; parser counts cannot establish their correctness.',
                  'Floating-point paths are checked against independent recurrence and exact first steps; no real economy is calibrated.',
                  'The lab fixes alpha, rates, physical units and the teaching-period convention; it is not a general estimation API.',
                  'Source structure/alignment is checked here; actual primary passage inspection is recorded in the source proposals.',
                  'No browser visual/mobile/print QA; root retains integration and dependency-ordered acceptance.'
              ]}
    json.dumps(report, allow_nan=False)
    return report


if __name__ == '__main__':
    print(json.dumps(check(), indent=2, allow_nan=False))
