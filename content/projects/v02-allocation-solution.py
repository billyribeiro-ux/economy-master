"""Original constrained-allocation benchmark; no external dependencies.

Place alongside v02-allocation-case.json and run python3 v02-allocation-solution.py.
The objective is strictly concave: maximize a*x+b*y-(p*x^2+q*y^2)/2.
Nonnegative activities use x+w*y<=B. p,q,w are strictly positive.
"""
from pathlib import Path
import json
import math


def solve(case, tolerance=1e-10):
    inputs={k:float(case[k]) for k in ('a','b','p','q','w','B')}
    if not all(math.isfinite(v) for v in inputs.values()) or not math.isfinite(tolerance):
        raise ValueError('Inputs and tolerance must be finite')
    a,b,p,q,w,B=(inputs[k] for k in ('a','b','p','q','w','B'))
    if min(p,q,w,tolerance)<=0 or B<0:
        raise ValueError('Require positive p,q,w,tolerance and nonnegative capacity')
    def activities(multiplier):
        return max((a-multiplier)/p,0.),max((b-w*multiplier)/q,0.)
    x,y=activities(0.)
    if x+w*y<=B:
        multiplier=0.; iterations=0
    elif B==0:
        multiplier=max(a,b/w,0.); x=y=0.; iterations=0
    else:
        lo=0.; hi=max(a,b/w,0.); iterations=0
        while hi-lo>tolerance:
            if iterations>=1000:
                raise RuntimeError('Multiplier iteration limit')
            mid=lo+(hi-lo)/2
            if mid==lo or mid==hi:
                raise RuntimeError('Multiplier bracket stagnation')
            mx,my=activities(mid)
            if mx+w*my>B: lo=mid
            else: hi=mid
            iterations+=1
        # Upper multiplier endpoint has feasible resource demand.
        multiplier=hi; x,y=activities(multiplier)
    objective=a*x+b*y-(p*x*x+q*y*y)/2
    dual=multiplier*B+max(a-multiplier,0.)**2/(2*p)+max(b-w*multiplier,0.)**2/(2*q)
    gap=dual-objective
    return dict(x=x,y=y,multiplier=multiplier,resource=x+w*y,
                slack=B-x-w*y,objective=objective,dual_upper=dual,
                computed_duality_gap=gap,
                distance_bound_if_arithmetic_reliable=math.sqrt(2*max(gap,0.)/min(p,q)),
                iterations=iterations)


def package(data):
    baseline=data['baseline']; tolerance=data['multiplier_tolerance']
    base=solve(baseline,tolerance)
    grid=[dict(B=B,**solve(dict(baseline,B=B),tolerance)) for B in data['capacity_grid']]
    capacity=solve(dict(baseline,B=baseline['B']+data['local_capacity_increment']),tolerance)
    payoff=solve(dict(baseline,**data['marginal_payoff_shock']),tolerance)
    return dict(provenance=data['provenance'],baseline=base,capacity_grid=grid,
                capacity_increment_result=capacity,payoff_shock_result=payoff,
                capacity_value_change=capacity['objective']-base['objective'],
                payoff_value_change=payoff['objective']-base['objective'],
                certificate_scope=data['numerical_certificate_scope'])


if __name__=='__main__':
    fixture=Path(__file__).with_name('v02-allocation-case.json')
    print(json.dumps(package(json.loads(fixture.read_text())),indent=2))
