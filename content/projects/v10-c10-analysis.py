"""Original bounded numerical-pricing lab; all cash values are per option in CU.

Import and run(data) are quiet. Ideal iid-normal statements are mathematical
benchmarks, not properties proved for the deterministic SHA256 test stream.
"""
import argparse
from hashlib import sha256
import json
import math
from pathlib import Path


def _keys(value, expected, label):
    if type(value) is not dict or set(value) != set(expected):
        raise ValueError(label + ': incorrect object keys')


def _number(value, low, high, label):
    if type(value) not in (int, float) or not low <= value <= high or not math.isfinite(value):
        raise ValueError(label + ': expected a finite number in [' + str(low) + ', ' + str(high) + ']')
    return float(value)


def _integer(value, low, high, label):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(label + ': expected bounded integer')
    return value


def validate(data):
    _keys(data, ('schema_version', 'market', 'tree', 'finite_difference', 'monte_carlo'), 'input')
    if type(data['schema_version']) is not int or data['schema_version'] != 1:
        raise ValueError('schema_version must be integer 1')
    market = data['market']
    names = ('spot', 'strike', 'rate', 'dividend_yield', 'volatility', 'maturity')
    _keys(market, names, 'market')
    bounds = ((20, 200), (20, 200), (-.05, .15), (0, .12), (.1, .6), (.25, 2))
    s, strike, r, q, sigma, t = [_number(market[n], *b, n) for n, b in zip(names, bounds)]
    if not .5 <= s / strike <= 2:
        raise ValueError('spot/strike must lie in [0.5, 2]')
    tree = data['tree']
    _keys(tree, ('steps', 'exercise_stride'), 'tree')
    stride = _integer(tree['exercise_stride'], 1, 32, 'exercise_stride')
    if type(tree['steps']) is not list or not 1 <= len(tree['steps']) <= 6:
        raise ValueError('tree.steps must contain 1 to 6 grids')
    last = 0
    for n in tree['steps']:
        _integer(n, 2, 256, 'tree steps')
        if n <= last or n % stride:
            raise ValueError('tree steps must increase strictly and be divisible by exercise_stride')
        last = n
        dt = t / n
        if not -sigma * math.sqrt(dt) < (r-q)*dt < sigma * math.sqrt(dt):
            raise ValueError('CRR pricing weights must be strictly interior; increase steps')
    fd = data['finite_difference']
    _keys(fd, ('log_half_width', 'grids'), 'finite_difference')
    width = _number(fd['log_half_width'], .6, 2.4, 'log_half_width')
    if abs(math.log(strike / s)) >= width:
        raise ValueError('payoff kink must be strictly inside log domain')
    if type(fd['grids']) is not list or not 1 <= len(fd['grids']) <= 4:
        raise ValueError('finite_difference.grids must contain 1 to 4 grids')
    cost = 0
    previous = (0, 0)
    a, b = sigma*sigma/2, r-q-sigma*sigma/2
    for grid in fd['grids']:
        _keys(grid, ('space_steps', 'time_steps'), 'grid')
        m = _integer(grid['space_steps'], 8, 200, 'space_steps')
        n = _integer(grid['time_steps'], 4, 10000, 'time_steps')
        if m % 2 or m <= previous[0] or n <= previous[1]:
            raise ValueError('space steps must be even; both grid counts must increase')
        previous = (m, n)
        h, dt = 2*width/m, t/n
        if a/h**2 - abs(b)/(2*h) < 0 or 1-2*a*dt/h**2 < 0:
            raise ValueError('finite-difference positivity/CFL condition fails')
        cost += m*n
    if cost > 2000000:
        raise ValueError('finite-difference total work exceeds 2000000 node updates per sweep')
    mc = data['monte_carlo']
    _keys(mc, ('seed', 'pairs', 'control_beta', 'alpha'), 'monte_carlo')
    _integer(mc['seed'], 0, 2**32-1, 'seed')
    _integer(mc['pairs'], 32, 16384, 'pairs')
    _number(mc['control_beta'], -2, 2, 'control_beta')
    _number(mc['alpha'], .001, .2, 'alpha')
    return s, strike, r, q, sigma, t


def _phi(x):
    return .5*math.erfc(-x/math.sqrt(2))


def vanilla(s, strike, r, q, sigma, t):
    if t == 0:
        return max(s-strike, 0.0), max(strike-s, 0.0)
    w = sigma*math.sqrt(t)
    d1 = (math.log(s/strike)+(r-q+sigma*sigma/2)*t)/w
    d2 = d1-w
    prepaid, bond = s*math.exp(-q*t), strike*math.exp(-r*t)
    return prepaid*_phi(d1)-bond*_phi(d2), bond*_phi(-d2)-prepaid*_phi(-d1)


def crr(market, steps, stride):
    s, strike, r, q, sigma, t = market
    dt = t/steps
    jump = sigma*math.sqrt(dt)
    down, up = math.exp(-jump), math.exp(jump)
    prob = math.expm1((r-q)*dt+jump)/math.expm1(2*jump)
    discount = math.exp(-r*dt)
    stocks = [s*math.exp((2*j-steps)*jump) for j in range(steps+1)]
    call = [max(stock-strike, 0.0) for stock in stocks]
    put = [max(strike-stock, 0.0) for stock in stocks]
    american, bermudan = put[:], put[:]
    exercised = 0
    for i in range(steps-1, -1, -1):
        call = [discount*((1-prob)*call[j]+prob*call[j+1]) for j in range(i+1)]
        put = [discount*((1-prob)*put[j]+prob*put[j+1]) for j in range(i+1)]
        new_a, new_b = [], []
        for j in range(i+1):
            intrinsic = max(strike-s*math.exp((2*j-i)*jump), 0.0)
            ca = discount*((1-prob)*american[j]+prob*american[j+1])
            cb = discount*((1-prob)*bermudan[j]+prob*bermudan[j+1])
            exercised += int(intrinsic > ca)
            new_a.append(max(intrinsic, ca))
            new_b.append(max(intrinsic, cb) if i % stride == 0 else cb)
        american, bermudan = new_a, new_b
    return {'steps': steps, 'up': up, 'down': down, 'probability_up': prob,
            'european_call': call[0], 'european_put': put[0],
            'bermudan_put': bermudan[0], 'all_grid_dates_put': american[0],
            'strict_exercise_nodes': exercised,
            'parity_residual': call[0]-put[0]-(s*math.exp(-q*t)-strike*math.exp(-r*t))}


def _evolve(initial, time_steps, weights, boundary):
    values = initial[:]
    left, middle, right = weights
    for n in range(1, time_steps+1):
        lo, hi = boundary(n)
        values = [lo] + [left*values[j-1]+middle*values[j]+right*values[j+1]
                         for j in range(1, len(values)-1)] + [hi]
    return values


def finite_difference(market, half_width, space_steps, time_steps):
    s, strike, r, q, sigma, t = market
    h, dt = 2*half_width/space_steps, t/time_steps
    a, b = sigma*sigma/2, r-q-sigma*sigma/2
    weights = (dt*(a/h**2-b/(2*h)), 1-2*a*dt/h**2, dt*(a/h**2+b/(2*h)))
    x = [-half_width+j*h for j in range(space_steps+1)]
    stocks = [s*math.exp(v) for v in x]
    initial = [max(strike-stock, 0.0) for stock in stocks]
    exact_edges, asym_edges = [], []
    for n in range(time_steps+1):
        tau = n*dt
        exact_edges.append(tuple(math.exp(r*tau)*vanilla(stock, strike, r, q, sigma, tau)[1]
                                 for stock in (stocks[0], stocks[-1])))
        asym_edges.append((max(strike-stocks[0]*math.exp((r-q)*tau), 0.0), 0.0))
    # The strict kink-inside condition makes both boundary definitions agree at tau=0.
    exact = _evolve(initial, time_steps, weights, lambda n: exact_edges[n])
    asym = _evolve(initial, time_steps, weights, lambda n: asym_edges[n])
    envelope = max(abs(u-v) for xe, xa in zip(exact_edges, asym_edges) for u, v in zip(xe, xa))
    discount = math.exp(-r*t)
    middle = space_steps//2
    kappa = 1.3
    growth = a*kappa*kappa+b*kappa
    manufactured_initial = [math.exp(kappa*xx) for xx in x]
    manufactured = _evolve(manufactured_initial, time_steps, weights,
                           lambda n: (math.exp(-kappa*half_width+growth*n*dt),
                                      math.exp(kappa*half_width+growth*n*dt)))
    truth = [math.exp(kappa*xx+growth*t) for xx in x]
    maximum = math.exp(kappa*half_width+max(growth*t, 0.0))
    consistency_bound = t*maximum*(dt*growth**2/2+h*h*(a*kappa**4/12+abs(b)*kappa**3/6))
    return {'space_steps': space_steps, 'time_steps': time_steps, 'dx': h, 'dt': dt,
            'weights': list(weights), 'spot_low': stocks[0], 'spot_high': stocks[-1],
            'put_exact_boundary': discount*exact[middle],
            'put_asymptotic_boundary': discount*asym[middle],
            'boundary_effect': discount*(asym[middle]-exact[middle]),
            'discrete_boundary_effect_bound': discount*envelope,
            'manufactured_max_error': max(abs(u-v) for u, v in zip(manufactured, truth)),
            'manufactured_global_bound': consistency_bound}


def normal_pairs(seed, count):
    """SHA256 counter stream + Box–Muller. The exact byte protocol is documented."""
    for i in range(count):
        digest = sha256(('v10-c10:' + str(seed) + ':' + str(i)).encode('ascii')).digest()
        u = ((int.from_bytes(digest[:8], 'big') >> 11)+.5)/2**53
        v = ((int.from_bytes(digest[8:16], 'big') >> 11)+.5)/2**53
        # Midpoints at the very top can round to 1.0 in binary64; cap explicitly.
        u, v = min(u, math.nextafter(1.0, 0.0)), min(v, math.nextafter(1.0, 0.0))
        radius, angle = math.sqrt(-2*math.log(u)), 2*math.pi*v
        yield radius*math.cos(angle), radius*math.sin(angle)


def _sample(values, bound, alpha):
    n = len(values)
    mean = math.fsum(values)/n
    variance = math.fsum((x-mean)**2 for x in values)/(n-1)
    se = math.sqrt(variance/n)
    # Fixed 95% CLT diagnostic; alpha controls the separate finite-sample bound.
    z = 1.959963984540054
    return {'units': n, 'mean': mean, 'sample_variance': variance, 'standard_error': se,
            'clt95_interval': [mean-z*se, mean+z*se],
            'hoeffding_half_width': None if bound is None else bound*math.sqrt(math.log(2/alpha)/(2*n))}


def monte_carlo(market, settings):
    s, strike, r, q, sigma, t = market
    discount, width = math.exp(-r*t), sigma*math.sqrt(t)
    median_log, ex = math.log(s)+(r-q-sigma*sigma/2)*t, s*math.exp(-q*t)
    beta = settings['control_beta']
    raw, controlled, anti, anti_controlled, z_values, x_values = [], [], [], [], [], []
    first = []
    def receipt(z):
        stock = math.exp(median_log+width*z)
        return discount*max(strike-stock, 0.0), discount*stock
    for index, (z1, z2) in enumerate(normal_pairs(settings['seed'], settings['pairs'])):
        if index < 3:
            first.append([z1, z2])
        for z in (z1, z2):
            y, x = receipt(z)
            raw.append(y)
            controlled.append(y-beta*(x-ex))
            z_values.append(z)
            x_values.append(x)
        y1, x1 = receipt(z1)
        y2, x2 = receipt(-z1)
        ya, xa = (y1+y2)/2, (x1+x2)/2
        anti.append(ya)
        anti_controlled.append(ya-beta*(xa-ex))
    truncated = []
    for j in range(3):
        scale = s**j*math.exp(j*(r-q)*t+j*(j-1)*sigma*sigma*t/2)
        threshold = (math.log(strike/s)-(r-q+(j-.5)*sigma*sigma)*t)/width
        truncated.append(scale*_phi(threshold))
    m0, m1, m2 = truncated
    ey = discount*(strike*m0-m1)
    ey2 = discount**2*(strike*strike*m0-2*strike*m1+m2)
    var_y = max(ey2-ey*ey, 0.0)
    var_x = ex*ex*math.expm1(sigma*sigma*t)
    cov = discount**2*(strike*m1-m2)-ey*ex
    var_control = max(var_y+beta*beta*var_x-2*beta*cov, 0.0)
    cap = discount*strike
    return {'generator': 'SHA256 ASCII v10-c10:seed:index; two 53-bit midpoint uniforms; Box-Muller',
            'seed': settings['seed'], 'pairs': settings['pairs'], 'payoff_evaluations_per_method': 2*settings['pairs'],
            'first_three_normal_pairs': first, 'fixed_beta': beta, 'hoeffding_alpha': settings['alpha'],
            'normal_sample_mean': math.fsum(z_values)/len(z_values),
            'normal_sample_second_moment': math.fsum(z*z for z in z_values)/len(z_values),
            'discounted_stock_sample_mean': math.fsum(x_values)/len(x_values),
            'ideal_analytic': {'put_mean': ey, 'put_variance': var_y, 'discounted_stock_mean': ex,
                               'discounted_stock_variance': var_x, 'put_stock_covariance': cov,
                               'optimal_beta': cov/var_x, 'fixed_control_variance': var_control},
            'plain': _sample(raw, cap, settings['alpha']),
            'fixed_control': _sample(controlled, None, settings['alpha']),
            'antithetic': _sample(anti, cap, settings['alpha']),
            'antithetic_fixed_control': _sample(anti_controlled, None, settings['alpha'])}


def run(data):
    market = validate(data)
    call, put = vanilla(*market)
    fd = data['finite_difference']
    trees = [crr(market, n, data['tree']['exercise_stride']) for n in data['tree']['steps']]
    grids = [finite_difference(market, fd['log_half_width'], g['space_steps'], g['time_steps'])
             for g in fd['grids']]
    for row in trees:
        row['european_put_error'] = row['european_put']-put
    for row in grids:
        row['exact_boundary_put_error'] = row['put_exact_boundary']-put
    result = {'schema_version': 1, 'chapter': 'v10-c10', 'units': 'CU per one option; times in years',
              'analytic': {'european_call': call, 'european_put': put},
              'tree': trees, 'finite_difference': grids,
              'monte_carlo': monte_carlo(market, data['monte_carlo']),
              'limits': ['All inputs are original synthetic teaching parameters, not market observations.',
                         'All-grid-date tree put is finite-model optimal stopping, not a continuous American price.',
                         'Exact PDE boundary is a vanilla verification device; asymptotic boundary introduces error.',
                         'Manufactured smooth-solution error bound does not certify the kinked option payoff rate.',
                         'Intervals require ideal independent random draws; deterministic test-stream quality is not proved.',
                         'Sampling intervals exclude model, monitoring, PDE, policy and floating-point errors.']}
    # Also detects any accidental nonfinite result before a caller serializes it.
    json.dumps(result, allow_nan=False)
    return result


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key: '+key)
        result[key] = value
    return result


def _constant(token):
    raise ValueError('nonfinite JSON token: '+token)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if args.input.resolve() == args.output.resolve():
        parser.error('input and output paths must differ')
    try:
        if args.input.stat().st_size > 65536:
            raise ValueError('input JSON exceeds 65536 bytes')
        data = json.loads(args.input.read_text(encoding='utf-8'), object_pairs_hook=_unique, parse_constant=_constant)
        result = run(data)
    except (OSError, ValueError, TypeError, OverflowError, RecursionError) as exc:
        parser.error(str(exc))
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False)+'\n', encoding='utf-8')


if __name__ == '__main__':
    main()
