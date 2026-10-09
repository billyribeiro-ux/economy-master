"""Independent exact moments, numerical interventions and artifact checks for c07."""
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
from decimal import Decimal, localcontext
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from io import StringIO
import json
import math
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'content/projects'
PREFIX = 'v10-c07'


def require(condition, message):
    if not condition:
        raise AssertionError(message)


class Audit:
    def __init__(self):
        self.comparisons = 0
        self.rejections = 0
        self.groups = []

    def eq(self, actual, expected, label):
        self.comparisons += 1
        if isinstance(expected, F):
            actual = F(actual)
        require(actual == expected, f'{label}: {actual!r} != {expected!r}')

    def near(self, actual, expected, label, tolerance=2e-10):
        self.comparisons += 1
        require(type(actual) in (float, int) and math.isfinite(actual), label + ': nonfinite/type')
        require(abs(actual - expected) <= tolerance * max(1, abs(expected)), label)


def add(p, q):
    result = p.copy()
    for powers, value in q.items():
        result[powers] = result.get(powers, F(0)) + value
    return {powers: value for powers, value in result.items() if value}


def scale(p, value):
    return {powers: value * coefficient for powers, coefficient in p.items()}


def multiply(p, q):
    result = {}
    for x, a in p.items():
        for y, b in q.items():
            powers = tuple(i + j for i, j in zip(x, y))
            result[powers] = result.get(powers, F(0)) + a * b
    return result


def gaussian_moment(p, variances):
    """Integrate a polynomial via independent centered Gaussian moments."""
    answer = F(0)
    for powers, coefficient in p.items():
        value = coefficient
        for power, variance in zip(powers, variances):
            if power % 2:
                value = F(0)
                break
            value *= variance ** (power // 2)
            for factor in range(1, power, 2):
                value *= factor
        answer += value
    return answer


def check_grid_moments(a, reported, T, n, cubature=False):
    # Construct actual left and right gain polynomials in independent increments.
    # This is distinct from both the model's closed forms and its finite cubature.
    variables = []
    for i in range(n):
        exponents = tuple(1 if j == i else 0 for j in range(n))
        variables.append({exponents: F(1)})
    W, Q, left, right = {}, {}, {}, {}
    for dw in variables:
        left = add(left, multiply(W, dw))
        W = add(W, dw)
        right = add(right, multiply(W, dw))
        Q = add(Q, multiply(dw, dw))
    moments = {}
    for name, polynomial in [('quadratic_sum', Q), ('left_sum', left), ('right_sum', right)]:
        mean = gaussian_moment(polynomial, [T / n] * n)
        second = gaussian_moment(multiply(polynomial, polynomial), [T / n] * n)
        moments[name + '_mean'] = mean
        moments[name + '_variance'] = second - mean * mean
    for name, expected in moments.items():
        a.eq(reported[name], expected, 'independent Gaussian polynomial ' + name)
    centered_Q = add(Q, {(0,) * n: -T})
    mse = gaussian_moment(multiply(centered_Q, centered_Q), [T / n] * n) / 4
    a.eq(reported['left_to_endpoint_mse' if cubature else 'left_integral_mse'], mse, 'polynomial left MSE')
    if cubature:
        a.eq(reported['probability_sum'], F(1), 'cubature mass')
        a.eq(reported['states'], 3 ** n, 'cubature enumerated state count')
        a.eq(reported['terminal_second_moment'], gaussian_moment(multiply(W, W), [T / n] * n), 'terminal second')
        square = multiply(W, W)
        a.eq(reported['terminal_fourth_moment'], gaussian_moment(multiply(square, square), [T / n] * n), 'terminal fourth')


def check_paths(a, output, data):
    T = F(data['grid']['horizon'])
    increments = list(map(F, data['grid']['increments']))
    for group in output['finite_grids']:
        block = group['block']
        dws = [sum(increments[start:start + block], F(0)) for start in range(0, len(increments), block)]
        w = [F(0)]
        for dw in dws:
            w.append(w[-1] + dw)
        report = group['ledger']
        q = sum((v * v for v in dws), F(0))
        left = sum((w[i] * dws[i] for i in range(len(dws))), F(0))
        right = sum((w[i + 1] * dws[i] for i in range(len(dws))), F(0))
        a.eq(report['steps'], len(dws), 'coarse length')
        a.eq(report['step'], T / len(dws), 'coarse time step')
        a.eq(report['terminal_W'], w[-1], 'coarse endpoint')
        a.eq(report['squared_increment_sum'], q, 'exact coarse squares')
        a.eq(report['absolute_increment_sum'], sum(map(abs, dws), F(0)), 'finite total absolute change')
        a.eq(report['left_sum'], left, 'left gain')
        a.eq(report['right_sum'], right, 'right gain')
        a.eq(F(report['right_sum']) - F(report['left_sum']), q, 'pathwise right-left identity')
        a.eq(F(report['right_sum']) + F(report['left_sum']), w[-1] ** 2, 'pathwise telescoping identity')
        a.eq(report['symmetric_sum'], w[-1] ** 2 / 2, 'ordinary polygon integral')
        a.eq(report['brownian_endpoint_formula'], (w[-1] ** 2 - T) / 2, 'Brownian endpoint expression')
        a.eq(report['left_minus_brownian_endpoint_formula'], (T - q) / 2, 'exact discretization discrepancy')
        for i, row in enumerate(report['rows']):
            expected = {'time': str((i + 1) * T / len(dws)), 'increment': str(dws[i]),
                        'W_before': str(w[i]), 'W_after': str(w[i + 1]),
                        'left_gain': str(w[i] * dws[i]), 'right_gain': str(w[i + 1] * dws[i])}
            a.eq(row, expected, 'whole dated path row')
    qfine = sum((x * x for x in increments), F(0))
    endpoint = sum(increments, F(0))
    for row in output['polygon_refinements']:
        pieces = row['subdivisions']
        refined = [x / pieces for x in increments for _ in range(pieces)]
        a.eq(row['quadratic_sum'], sum((x * x for x in refined), F(0)), 'actual polygon subdivision squares')
        a.eq(row['ordinary_integral_W_dW'], endpoint ** 2 / 2, 'polygon endpoint integral')
    a.eq(output['polygon_refinements'][0]['quadratic_sum'], qfine / data['grid']['polygon_subdivisions'][0], 'first polygon')


def check_adapted(a, report, data):
    h = F(data['grid']['horizon']) / 2
    first = F(data['adapted_integrand']['first_holding'])
    feedback = F(data['adapted_integrand']['feedback'])
    polynomial = {(1, 0): first, (1, 1): feedback}
    squared = multiply(polynomial, polynomial)
    variance = gaussian_moment(squared, [h, h])
    fourth = gaussian_moment(multiply(squared, squared), [h, h])
    a.eq(report['switch_time'], h, 'adapted switch')
    a.eq(report['mean'], gaussian_moment(polynomial, [h, h]), 'adapted polynomial mean')
    a.eq(report['variance'], variance, 'adapted polynomial variance')
    a.eq(report['fourth_moment'], fourth, 'adapted polynomial fourth')
    a.eq(report['gaussian_fourth_if_same_variance'], 3 * variance ** 2, 'normal comparison')


def check_chain(a, output, data):
    T = F(data['grid']['horizon'])
    W = sum(map(F, data['grid']['increments']), F(0))
    spec = {key: F(value) for key, value in data['chain_product'].items()}
    xmean = spec['x0'] + spec['x_drift'] * T
    ymean = spec['y0'] + spec['y_drift'] * T
    b, d = spec['x_diffusion'], spec['y_diffusion']
    x, y = xmean + b * W, ymean + d * W
    report = output['chain_and_product']
    a.eq(report['terminal_X'], x, 'affine X')
    a.eq(report['terminal_Y'], y, 'affine Y')
    a.eq(report['cross_variation'], b * d * T, 'shared shock cross variation')
    a.eq(report['X_quadratic_variation'], b ** 2 * T, 'X variation')
    a.eq(report['Y_quadratic_variation'], d ** 2 * T, 'Y variation')
    a.eq(report['product_expectation'], gaussian_moment(multiply({(0,): xmean, (1,): b}, {(0,): ymean, (1,): d}), [T]), 'Gaussian polynomial product')
    a.eq(report['product_drift_at_endpoint'], spec['x_drift'] * y + spec['y_drift'] * x + b * d, 'product drift')
    a.eq(report['product_diffusion_at_endpoint'], b * y + d * x, 'product diffusion')
    discount = math.exp(-float(spec['decay'] * T))
    a.near(report['discounted_square_approx'], discount * float(x ** 2), 'discounted state')
    a.near(report['discounted_square_drift_approx'], discount * float(-spec['decay'] * x ** 2 + 2 * spec['x_drift'] * x + b ** 2), 'discounted Ito drift')
    a.near(report['discounted_square_diffusion_approx'], discount * float(2 * b * x), 'discounted Ito diffusion')
    a.near(report['discounted_square_expectation_approx'], discount * float(gaussian_moment(multiply({(0,): xmean, (1,): b}, {(0,): xmean, (1,): b}), [T])), 'discounted square moment')


def decimal_fraction(value):
    ratio = F(value)
    return Decimal(ratio.numerator) / Decimal(ratio.denominator)


def check_gbm(a, output, data):
    T = F(data['grid']['horizon'])
    spec = data['gbm']
    S0, mu, sigma = [F(spec[key]) for key in ('initial_price', 'drift', 'diffusion')]
    report = output['gbm']
    a.eq(report['log_return_mean'], (mu - sigma ** 2 / 2) * T, 'log drift correction')
    a.eq(report['log_return_variance'], sigma ** 2 * T, 'log variance')
    mean = float(S0) * math.exp(float(mu * T))
    a.near(report['mean_price_approx'], mean, 'normal MGF first moment')
    a.near(report['median_price_approx'], float(S0) * math.exp(float((mu - sigma ** 2 / 2) * T)), 'median')
    a.near(report['price_variance_approx'], mean ** 2 * math.expm1(float(sigma ** 2 * T)), 'MGF price variance')
    w, euler = F(0), S0
    h = T / len(data['grid']['increments'])
    for i, dw in enumerate(map(F, data['grid']['increments'])):
        w += dw
        euler *= 1 + mu * h + sigma * dw
        row = report['rows'][i]
        a.eq(row['time'], (i + 1) * h, 'GBM path time')
        a.eq(row['W'], w, 'GBM path noise')
        a.eq(row['euler_price'], euler, 'exact Euler finite product')
        a.eq(row['euler_positive'], euler > 0, 'Euler sign')
        a.near(row['exact_price_approx'], float(S0) * math.exp(float((mu - sigma ** 2 / 2) * (i + 1) * h + sigma * w)), 'GBM path exponential')
    # Independent one-step moment recurrences, not the implementation's powers.
    with localcontext() as ctx:
        ctx.prec = 110
        initial, drift, vol, horizon = map(decimal_fraction, (S0, mu, sigma, T))
        for row in report['euler_analytical_error']:
            n = row['steps']
            dt = horizon / n
            exact_first = (drift * dt).exp()
            exact_second = ((2 * drift + vol * vol) * dt).exp()
            euler_first = 1 + drift * dt
            euler_second = euler_first * euler_first + vol * vol * dt
            # Gaussian expectation of exp(sigma*dW)*(1+mu*dt+sigma*dW).
            shared = exact_first * (euler_first + vol * vol * dt)
            mS = mE = initial
            mS2 = mE2 = mSE = initial * initial
            for _ in range(n):
                mS *= exact_first
                mE *= euler_first
                mS2 *= exact_second
                mE2 *= euler_second
                mSE *= shared
            anchors = {'exact_mean_approx': mS, 'euler_mean_approx': mE,
                       'weak_mean_bias_approx': mE - mS, 'exact_second_moment_approx': mS2,
                       'euler_second_moment_approx': mE2, 'coupled_cross_moment_approx': mSE,
                       'coupled_strong_mse_approx': mS2 + mE2 - 2 * mSE}
            for key, value in anchors.items():
                a.near(row[key], float(value), 'one-step recurrence ' + key)
            require(row['coupled_strong_mse_approx'] >= 0, 'nonnegative MSE')
    probe = report['positivity_probe']
    dt, dw = F(spec['probe_time']), F(spec['probe_increment'])
    factor = 1 + mu * dt + sigma * dw
    a.eq(probe['euler_factor'], factor, 'probe factor')
    a.eq(probe['euler_price'], S0 * factor, 'probe signed price')
    a.eq(probe['euler_nonpositive'], factor <= 0, 'probe failure flag')
    a.near(probe['exact_price_approx'], float(S0) * math.exp(float((mu - sigma ** 2 / 2) * dt + sigma * dw)), 'positive exact stress')
    require(probe['exact_price_approx'] > 0, 'strictly positive exact stress')


class Fragment(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack = []
        self.ids = []
        self.sources = set()
        self.links = []
        self.worked = self.exercises = self.solutions = 0

    def handle_starttag(self, tag, attrs):
        at = dict(attrs)
        require(tag not in ('html', 'body', 'h1', 'script'), 'static chapter fragment')
        if 'id' in at:
            self.ids.append(at['id'])
        if 'data-source' in at:
            self.sources.add(at['data-source'])
        if 'href' in at:
            self.links.append(at['href'])
        if tag == 'aside' and 'worked' in at.get('class', '').split():
            self.worked += 1
        if tag == 'li' and self.stack and self.stack[-1][0] == 'ol':
            if 'exercises' in self.stack[-1][1].get('class', '').split():
                self.exercises += 1
            if any(t == 'details' and 'solutions' in d.get('class', '').split() for t, d in self.stack):
                self.solutions += 1
        if tag not in ('br', 'hr', 'img', 'input', 'meta', 'link'):
            self.stack.append((tag, at))

    def handle_endtag(self, tag):
        require(self.stack and self.stack[-1][0] == tag, 'unbalanced HTML ' + tag)
        self.stack.pop()


def check():
    a = Audit()
    raw = json.loads((ASSETS / (PREFIX + '-inputs.json')).read_text())
    saved = json.loads((ASSETS / (PREFIX + '-output.json')).read_text())
    original = deepcopy(raw)
    capture = StringIO()
    with redirect_stdout(capture), redirect_stderr(capture):
        model = runpy.run_path(str(ASSETS / (PREFIX + '-analysis.py')))
        actual = model['run'](raw)
    a.eq(capture.getvalue(), '', 'quiet import and API')
    a.eq(raw, original, 'unmodified input')
    a.eq(actual, saved, 'whole reference payload')
    json.dumps(actual, allow_nan=False)
    a.groups.append('quiet nonmutating strict-JSON API and complete saved reference')

    check_paths(a, actual, raw)
    fine = actual['finite_grids'][0]['ledger']
    for key, value in {'terminal_W': F(1, 4), 'squared_increment_sum': F(23, 32),
                       'absolute_increment_sum': F(3), 'left_sum': -F(21, 64),
                       'right_sum': F(25, 64), 'left_minus_brownian_endpoint_formula': F(9, 64)}.items():
        a.eq(fine[key], value, 'worked finite-record anchor ' + key)
    for row in actual['brownian_grid_theory']:
        T, n = F(raw['grid']['horizon']), row['steps']
        h = T / n
        # Summing dated conditional variances is independent of the model's form.
        left_variance = sum((F(i) * h * h for i in range(n)), F(0))
        a.eq(row['quadratic_sum_mean'], T, 'sum Gaussian second moments')
        a.eq(row['quadratic_sum_variance'], sum([2 * h * h] * n, F(0)), 'sum independent square variances')
        a.eq(row['left_sum_mean'], F(0), 'left conditional gain mean')
        a.eq(row['left_sum_variance'], left_variance, 'dated left variances')
        a.eq(row['right_sum_mean'], T, 'right hindsight mean')
        a.eq(row['right_sum_variance'], left_variance + 2 * n * h * h, 'right variance')
        a.eq(row['ito_W_integral_variance'], T * T / 2, 'isometry W integral')
        a.eq(row['left_integral_mse'], sum([h * h / 2] * n, F(0)), 'integrated left-step error')
    check_grid_moments(a, actual['brownian_grid_theory'][0], F(1), 4)
    check_grid_moments(a, actual['finite_moment_cubature'], F(1), 4, True)
    a.eq(2 * F(1, 6) * 3 ** 3, F(9), 'cubature sixth moment is not Gaussian 15')
    a.groups.append('exact path ledgers, polygon counterexample and independent Gaussian polynomial moments')

    check_adapted(a, actual['adapted_two_step_integral'], raw)
    check_chain(a, actual, raw)
    check_gbm(a, actual, raw)
    a.groups.append('adapted nonnormal fourth moment, Ito/product coefficients and coupled GBM/Euler recurrences')

    # Exercise anchors beyond the supplied primary fixture.
    unequal = [F(1, 8), F(3, 8), F(1, 2)]
    a.eq(2 * sum((x * x for x in unequal), F(0)), F(13, 16), 'exercise 2 unequal Q variance')
    a.eq(sum((x * x / 2 for x in unequal), F(0)), F(13, 64), 'exercise 2 unequal MSE')
    a.eq(F(1) + F(1) + F(1, 3), F(7, 3), 'exercise 3 deterministic-integral variance')
    a.eq(gaussian_moment({(4,): F(1), (2,): -F(1, 4)}, [F(1, 4)]), F(1, 8), 'exercise 4 anticipative weight mean')
    a.eq(F(2) ** 3 / 3, F(8, 3), 'exercise 5 T=2 variance')
    a.eq(F(2) ** 2 / 2, F(2), 'exercise 5 T=2 covariance')
    a.near(F(3, 4) * math.exp(-4), 0.013736729166550634, 'exercise 6 discounted expectation')
    a.eq(gaussian_moment(multiply({(0,): F(1, 2), (1,): F(1, 2)}, {(0,): F(4), (1,): F(1, 4)}), [F(2)]), F(9, 4), 'exercise 6 product expectation')
    a.eq(F(1, 2) * F(1, 4) * 2, F(1, 4), 'exercise 6 cross variation')
    a.near(50 * math.exp(-0.12), 44.346021835857876, 'exercise 7 median')
    a.near(50 * math.exp(0.04), 52.04053870961941, 'exercise 7 mean')
    a.near(math.exp(0.28) / 50, 0.02646259624674874, 'exercise 7 inverse expectation')
    a.eq(2 * F(2) ** 2 / 8, F(1), 'retention Q variance')
    a.eq(F(2) ** 2 / (2 * 8), F(1, 4), 'retention left MSE')
    a.eq(F('0.04') - F('0.4') ** 2 / 2, -F('0.04'), 'retention log drift')
    a.groups.append('worked anchors and all determinate exercise/retention arithmetic; proof prompts reviewed editorially')

    # Meaningful interventions preserve the fixed provenance/information contract.
    variant = deepcopy(raw)
    variant['grid'].update(horizon='2', increments=['1/2', '-1/4', '0', '1/4'], blocks=[1, 2, 4],
                           theory_steps=[1, 3, 8], cubature_steps=3)
    variant['adapted_integrand'].update(first_holding='-1', feedback='2')
    variant['chain_product'].update(x_drift='-1/4', x_diffusion='1/2', y_diffusion='-1/4', decay='0')
    variant['gbm'].update(initial_price='50', drift='-1/5', diffusion='1/2', euler_steps=[1, 3, 12])
    changed = model['run'](variant)
    check_paths(a, changed, variant)
    check_grid_moments(a, changed['finite_moment_cubature'], F(2), 3, True)
    check_adapted(a, changed['adapted_two_step_integral'], variant)
    check_chain(a, changed, variant)
    check_gbm(a, changed, variant)
    require(F(changed['chain_and_product']['cross_variation']) < 0, 'negative shared exposure allowed')
    a.near(changed['chain_and_product']['discounted_square_approx'], float(F(changed['chain_and_product']['terminal_X']) ** 2), 'zero discount reduces to square')

    deterministic = deepcopy(raw)
    deterministic['gbm'].update(diffusion='0', drift='-1/2', euler_steps=[1, 4, 64])
    deterministic['grid']['horizon'] = '2'
    deterministic_result = model['run'](deterministic)
    check_gbm(a, deterministic_result, deterministic)
    a.near(deterministic_result['gbm']['price_variance_approx'], 0.0, 'zero diffusion is deterministic')
    for row in deterministic_result['gbm']['euler_analytical_error']:
        a.near(row['coupled_strong_mse_approx'], row['weak_mean_bias_approx'] ** 2, 'deterministic strong error is squared bias')

    zero = deepcopy(raw)
    zero['grid'].update(increments=['0', '0'], blocks=[1, 2], cubature_steps=1)
    zero['gbm'].update(drift='0', diffusion='0', euler_steps=[1, 4096])
    zero['adapted_integrand'].update(first_holding='0', feedback='0')
    no_change = model['run'](zero)
    check_paths(a, no_change, zero)
    check_adapted(a, no_change['adapted_two_step_integral'], zero)
    check_gbm(a, no_change, zero)
    for row in no_change['gbm']['euler_analytical_error']:
        a.eq(row['weak_mean_bias_approx'], 0.0, 'zero-coefficient exact bias')
        a.eq(row['coupled_strong_mse_approx'], 0.0, 'zero-coefficient exact MSE')
    a.groups.append('horizon, feedback, negative shared exposure/drift, zero diffusion/decay and zero-motion interventions')

    def reject(path, value):
        bad = deepcopy(raw)
        destination = bad
        for key in path[:-1]:
            destination = destination[key]
        destination[path[-1]] = value
        try:
            model['run'](bad)
        except ValueError:
            a.rejections += 1
        else:
            raise AssertionError('accepted invalid input ' + repr(path) + ': ' + repr(value))

    invalid = [
        (['grid', 'horizon'], True), (['grid', 'horizon'], 1.0),
        (['grid', 'horizon'], float('nan')), (['grid', 'horizon'], float('inf')),
        (['grid', 'horizon'], 'NaN'), (['grid', 'horizon'], '1e0'),
        (['grid', 'horizon'], '01'), (['grid', 'horizon'], '1/0'),
        (['grid', 'horizon'], '1/1000001'), (['grid', 'horizon'], '1000001'),
        (['grid', 'horizon'], '1/32'), (['grid', 'horizon'], '3'),
        (['grid', 'increments'], ['0']), (['grid', 'increments'], ['0', '0', '0']),
        (['grid', 'increments'], ['5', '0']), (['grid', 'increments'], [False, '0']),
        (['grid', 'blocks'], [3]), (['grid', 'blocks'], [1, 1]),
        (['grid', 'blocks'], [True]), (['grid', 'polygon_subdivisions'], [65]),
        (['grid', 'theory_steps'], [4097]), (['grid', 'theory_steps'], []),
        (['grid', 'cubature_steps'], 8), (['grid', 'cubature_steps'], False),
        (['adapted_integrand', 'feedback'], '11'), (['chain_product', 'decay'], '-1'),
        (['chain_product', 'x0'], '11'), (['gbm', 'initial_price'], '0'),
        (['gbm', 'initial_price'], '-1'), (['gbm', 'diffusion'], '-1/10'),
        (['gbm', 'diffusion'], '2'), (['gbm', 'drift'], '3/4'),
        (['gbm', 'euler_steps'], [1.0]), (['gbm', 'euler_steps'], [4097]),
        (['gbm', 'probe_time'], '0'), (['gbm', 'probe_increment'], '5'),
        (['contract', 'law'], 'risk-neutral by assumption-free calculus'),
        (['provenance'], 'actual price observations'), (['schema'], 'different'),
        (['grid'], []), (['gbm'], None), (['extra'], 1),
    ]
    for path, value in invalid:
        reject(path, value)
    for missing in ('grid', 'gbm', 'contract'):
        bad = deepcopy(raw)
        del bad[missing]
        try:
            model['run'](bad)
        except ValueError:
            a.rejections += 1
        else:
            raise AssertionError('accepted missing ' + missing)
    a.groups.append('bounded runtime/numeric domain, information/provenance and malformed-input rejections')

    manifest = json.loads((ASSETS / (PREFIX + '-manifest.json')).read_text())
    filenames = {PREFIX + suffix for suffix in ('-inputs.json', '-analysis.py', '-output.json', '-README.txt')}
    a.eq({item['file'] for item in manifest['files']}, filenames, 'exact four manifest payloads')
    a.eq(len(manifest['files']), 4, 'no duplicate manifest entry')
    for item in manifest['files']:
        payload = (ASSETS / item['file']).read_bytes()
        a.eq(item['bytes'], len(payload), 'manifest byte count')
        a.eq(item['sha256'], sha256(payload).hexdigest(), 'manifest checksum')
    with tempfile.TemporaryDirectory(prefix='v10-c07-check-') as temp:
        folder = Path(temp)
        for name in filenames:
            shutil.copyfile(ASSETS / name, folder / name)
        for optimized in (False, True):
            destination = folder / ('ordinary.json' if not optimized else 'optimized.json')
            command = [sys.executable] + (['-O'] if optimized else [])
            command += [str(folder / (PREFIX + '-analysis.py')), '--input', str(folder / (PREFIX + '-inputs.json')), '--output', str(destination)]
            process = subprocess.run(command, cwd=folder, capture_output=True, text=True, timeout=30)
            a.eq(process.returncode, 0, 'portable CLI exit')
            a.eq(process.stdout, '', 'portable CLI quiet stdout')
            a.eq(process.stderr, '', 'portable CLI quiet stderr')
            a.eq(json.loads(destination.read_text()), saved, 'portable CLI full output')
        for invalid_text in ('{"schema":"a","schema":"b"}', '{"x":NaN}', '{"x":Infinity}', '{"x":-Infinity}'):
            bad_path = folder / 'invalid.json'
            bad_path.write_text(invalid_text)
            try:
                model['load_json'](bad_path)
            except ValueError:
                a.rejections += 1
            else:
                raise AssertionError('strict parser accepted ' + invalid_text)
        bad_path.write_text('{"schema":"a","schema":"b"}')
        for optimized in (False, True):
            command = [sys.executable] + (['-O'] if optimized else [])
            command += [str(folder / (PREFIX + '-analysis.py')), '--input', str(bad_path), '--output', str(folder / 'must-not-exist.json')]
            process = subprocess.run(command, cwd=folder, capture_output=True, text=True, timeout=30)
            require(process.returncode != 0 and 'duplicate JSON key' in process.stderr, 'invalid portable CLI diagnostic')
            a.eq(process.stdout, '', 'invalid CLI emits no result')
            require(not (folder / 'must-not-exist.json').exists(), 'invalid CLI wrote output')
            a.rejections += 1
    a.groups.append('four-file manifest and isolated explicit normal/optimized CLI including strict duplicate/nonfinite JSON')

    fragment = Fragment()
    fragment.feed((ROOT / 'content/chapters/v10-c07.html').read_text())
    require(not fragment.stack, 'unclosed manuscript tag')
    a.eq(len(set(fragment.ids)), len(fragment.ids), 'unique manuscript anchors')
    a.eq(fragment.worked, 4, 'four worked examples')
    a.eq(fragment.exercises, 10, 'ten exercises')
    a.eq(fragment.solutions, 10, 'ten solutions')
    sources = json.loads((ROOT / 'content/reviews/v10-c07-sources.json').read_text())
    a.eq(fragment.sources, {item['id'] for item in sources['proposals']}, 'exact scoped source coverage')
    for href in fragment.links:
        if href.startswith('projects/'):
            require((ROOT / 'content' / href).is_file(), 'missing project link ' + href)
    review = json.loads((ROOT / 'content/reviews/v10-c07-author.json').read_text())
    owned = {'content/chapters/v10-c07.html', 'scripts/check_v10_c07.py', 'content/reviews/v10-c07-sources.json'}
    owned |= {'content/projects/' + PREFIX + suffix for suffix in ('-inputs.json', '-analysis.py', '-output.json', '-manifest.json', '-README.txt')}
    a.eq({item['path'] for item in review['reviewed_hashes']}, owned, 'author binds all eight nonself payloads')
    a.eq(len(review['reviewed_hashes']), 8, 'no duplicate author payload')
    for item in review['reviewed_hashes']:
        payload = (ROOT / item['path']).read_bytes()
        a.eq(item['bytes'], len(payload), 'review byte count')
        a.eq(item['sha256'], sha256(payload).hexdigest(), 'review hash')
    a.groups.append('balanced original chapter, complete solved prompts, scoped sources and author payload binding')
    return {'status': 'passed', 'independent_comparisons': a.comparisons,
            'invalid_inputs_rejected': a.rejections, 'worked_examples': fragment.worked,
            'solved_exercises': fragment.solutions, 'groups': a.groups,
            'limits': 'Numerical/structural author audit; proofs reviewed editorially, not mechanically certified. Separate coordinator review and whole-edition visual QA remain distinct.'}


if __name__ == '__main__':
    print(json.dumps(check(), indent=2, allow_nan=False))
