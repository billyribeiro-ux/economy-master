"""Original synthetic Solow ledger; standard library, fixed teaching technology.

Timing: beginning K_t produces Y_t; gross I_t is usable at t+1.
Units: physical goods, workers and normalized efficiency, per teaching period.
This fixed fixture uses alpha=1/2, delta=1/25, n=g=1/10.
"""
import json
import math

DELTA = 1 / 25
N = 1 / 10
G = 1 / 10
GAMMA = (1 + N) * (1 + G)
MAINTENANCE = GAMMA - 1 + DELTA


def simulate(initial_k, saving, periods=40):
    """Vary only initial effective-worker capital, saving and horizon.

    Returns `periods` dated transition rows and a terminal state at that date.
    Fixed A_0=1 and L_0=100 fix the aggregate normalization. A changing period
    length, depreciation or efficiency convention requires a new fixture.
    """
    for value, name in ((initial_k, 'initial_k'), (saving, 'saving')):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(name + ' must be a real number, not a boolean')
        if not math.isfinite(value):
            raise ValueError(name + ' must be finite')
    if initial_k < 0 or not 0 <= saving <= 1:
        raise ValueError('require initial_k >= 0 and saving in [0,1]')
    if isinstance(periods, bool) or not isinstance(periods, int) or not 1 <= periods <= 200:
        raise ValueError('periods must be an integer between 1 and 200')
    A, L, K = 1.0, 100.0, initial_k * 100.0
    rows = []
    for t in range(periods):
        effective = A * L
        k = K / effective
        Y = math.sqrt(K) * math.sqrt(effective)
        investment = saving * Y
        consumption = Y - investment
        depreciation = DELTA * K
        next_K = K - depreciation + investment
        next_A, next_L = A * (1 + G), L * (1 + N)
        next_k = next_K / (next_A * next_L)
        normalized_prediction = ((1 - DELTA) * k + saving * math.sqrt(k)) / GAMMA
        quantities = (A, L, K, Y, investment, consumption, next_K, next_k)
        if not all(math.isfinite(value) for value in quantities):
            raise ValueError('scenario exceeds finite numerical range')
        rows.append({
            't': t, 'A': A, 'L': L, 'K': K, 'Y': Y,
            'I': investment, 'C': consumption, 'depreciation': depreciation,
            'net_investment': investment - depreciation, 'k': k,
            'c': consumption / effective, 'next_K': next_K,
            'next_A': next_A, 'next_L': next_L, 'next_k': next_k,
            'normalized_discrepancy': next_k - normalized_prediction,
        })
        A, L, K = next_A, next_L, next_K
    terminal_k = K / (A * L)
    return {
        'initial_k': initial_k, 'saving': saving, 'periods': periods,
        'rows': rows,
        'terminal': {'t': periods, 'K': K, 'A': A, 'L': L, 'k': terminal_k,
                     'y': math.sqrt(terminal_k),
                     'c': (1 - saving) * math.sqrt(terminal_k)},
        'positive_steady': None if saving == 0 else {
            'k': (saving / MAINTENANCE) ** 2,
            'y': saving / MAINTENANCE,
            'c': (1 - saving) * saving / MAINTENANCE,
        },
        'zero_capital_boundary': initial_k == 0,
    }


def benchmark():
    return {
        'provenance': 'Original synthetic teaching cases; not observed data or forecasts.',
        'units': {'K': 'physical goods, beginning stock',
                  'Y_I_C': 'physical goods during the teaching period',
                  'L': 'workers with fixed labor per period',
                  'A': 'normalized efficiency index',
                  'k': 'goods per effective worker',
                  'c_y': 'goods per effective worker during the teaching period'},
        'fixed_parameters': {'alpha': '1/2', 'delta': '1/25', 'n': '1/10',
                             'g': '1/10', 'Gamma': '121/100', 'd': '1/4'},
        'scenarios': {
            'accumulation': simulate(1 / 4, 1 / 4),
            'saving_increase': simulate(1, 1 / 2),
            'saving_reduction': simulate(9, 1 / 2),
        },
        'limitations': [
            'Square-root physical production, constant rates and fixed period convention only.',
            'Floating-point transition paths; exact first-step and limit references are in the chapter.',
            'A finite simulated horizon is not a proof of convergence or the limiting state.',
            'Exogenous saving and productivity; no estimated parameters or causal policy effects.',
        ],
    }


if __name__ == '__main__':
    print(json.dumps(benchmark(), indent=2, allow_nan=False))
