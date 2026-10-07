"""Original Volume 2 numerical examples; Python standard library only.

Run: python3 v02-numerics.py
Bounds assume reliable floating-point evaluations, not interval arithmetic.
"""
import json
import math


def finite(value):
    value = float(value)
    if not math.isfinite(value):
        raise ValueError('Expected a finite number')
    return value


def positive_integer(value):
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError('Expected a positive integer')
    return value


def bisection(function, lo, hi, tolerance=1e-6, max_iterations=1000):
    """Return midpoint, bracket, half-width bound and completed halvings.

    Caller supplies a continuous function and trustworthy signs on the bracket.
    Endpoint roots and exactly evaluated midpoint roots return zero-width brackets.
    """
    lo, hi, tolerance = finite(lo), finite(hi), finite(tolerance)
    positive_integer(max_iterations)
    if not lo < hi or tolerance <= 0:
        raise ValueError('Require lo < hi and tolerance > 0')
    # Reject ranges whose width cannot be represented by this implementation.
    finite(hi-lo)
    flo, fhi = finite(function(lo)), finite(function(hi))
    if flo == 0 or fhi == 0:
        root = lo if flo == 0 else hi
        return dict(answer=root, bracket=[root, root], error_bound=0., halvings=0)
    if (flo < 0) == (fhi < 0):
        raise ValueError('Endpoints must have opposing signs')
    count = 0
    while (hi-lo)/2 > tolerance:
        if count >= max_iterations:
            raise RuntimeError('Iteration limit; tolerance not achieved')
        mid = lo+(hi-lo)/2
        if mid == lo or mid == hi:
            raise RuntimeError('Floating-point bracket stagnation')
        fm = finite(function(mid))
        count += 1
        if fm == 0:
            return dict(answer=mid, bracket=[mid, mid], error_bound=0., halvings=count)
        if (fm < 0) == (flo < 0):
            lo, flo = mid, fm
        else:
            hi, fhi = mid, fm
    mid = lo+(hi-lo)/2
    return dict(answer=mid, bracket=[lo, hi], error_bound=(hi-lo)/2, halvings=count)


def quadrature(function, lo, hi, cells, method='trapezoid'):
    """Composite trapezoid, midpoint or even-cell Simpson rule.

    This returns an approximation; supply smoothness bounds separately.
    """
    lo, hi = finite(lo), finite(hi)
    positive_integer(cells)
    if not lo < hi:
        raise ValueError('Require lo < hi')
    if method not in ('trapezoid', 'midpoint', 'simpson'):
        raise ValueError('Unknown quadrature method')
    if method == 'simpson' and cells % 2:
        raise ValueError('Simpson requires an even cell count')
    h = finite(hi-lo)/cells
    if h == 0:
        raise ValueError('Grid step underflows')
    if method == 'midpoint':
        return finite(h*math.fsum(finite(function(lo+(j+.5)*h)) for j in range(cells)))
    values = [finite(function(lo+j*h)) for j in range(cells+1)]
    if method == 'trapezoid':
        return finite(h*(values[0]/2+math.fsum(values[1:-1])+values[-1]/2))
    return finite(h/3*(values[0]+values[-1]+math.fsum(
        (4 if j % 2 else 2)*values[j] for j in range(1, cells))))


def value_iteration(model, beta, tolerance=.01, max_iterations=10000):
    """model[state][action] = (net_reward, next_state).

    Return current values, greedy policy, residual, certified value-error bound
    and number of completed Bellman updates. Finite deterministic states only.
    """
    beta, tolerance = finite(beta), finite(tolerance)
    positive_integer(max_iterations)
    if not 0 <= beta < 1 or tolerance <= 0 or not model:
        raise ValueError('Require finite nonempty model, 0 <= beta < 1, tolerance > 0')
    clean = {}
    for state, actions in model.items():
        if not actions:
            raise ValueError('Every state needs a feasible action')
        clean[state] = {}
        for action, (reward, successor) in actions.items():
            if successor not in model:
                raise ValueError('Unknown successor state')
            clean[state][action] = (finite(reward), successor)
    values = {state: 0. for state in clean}
    for count in range(max_iterations+1):
        next_values, policy = {}, {}
        for state, actions in clean.items():
            scores = {action: finite(reward+beta*values[successor])
                      for action, (reward, successor) in actions.items()}
            policy[state] = max(scores, key=scores.get)
            next_values[state] = scores[policy[state]]
        residual = max(abs(next_values[s]-values[s]) for s in clean)
        bound = residual/(1-beta)
        if bound <= tolerance:
            return dict(values=values, policy=policy, residual=residual,
                        error_bound=bound, updates=count)
        values = next_values
    raise RuntimeError('Iteration limit; value error not certified')


def example():
    machine = {'G': {'operate': (4, 'W')},
               'W': {'operate': (1, 'W'), 'service': (-1, 'G')}}
    return {'root': bisection(lambda q: q**3+q-5, 1, 2),
            'integral_x4': {method: quadrature(lambda x: x**4, 0, 1, 2, method)
                            for method in ('trapezoid', 'midpoint', 'simpson')},
            'machine': value_iteration(machine, .8)}


if __name__ == '__main__':
    print(json.dumps(example(), indent=2))
