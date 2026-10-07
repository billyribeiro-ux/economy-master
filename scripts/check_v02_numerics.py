"""Exact-fraction checks independent of the downloadable float benchmark."""
from fractions import Fraction as F
from pathlib import Path
import importlib.util
import math


def rejects(kind, function):
    try: function()
    except kind: return
    raise AssertionError('Expected failure was not raised')


def check():
    root_function=lambda q:q**3+q-5
    lo,hi=F(1),F(2)
    for _ in range(80):
        mid=(lo+hi)/2
        if root_function(mid)<0: lo=mid
        else: hi=mid
    root=float((lo+hi)/2)
    assert root_function(lo)<0<root_function(hi)
    residual=root_function(F(379,250))
    assert residual==F(19512,125000000) and residual/4==F(2439,62500000)
    assert F(1,2)**16>F(1,100000)>F(1,2)**17
    assert F(1,2)**20<F(1,1000000)
    q=F(3,2)
    expected=[1.5161290322580645,1.5159802404475657,1.5159802276928207]
    for target in expected:
        q=q-root_function(q)/(3*q*q+1)
        assert math.isclose(float(q),target,abs_tol=1e-14)
    assert math.isclose(1/(3*root*root+1),.12667,abs_tol=5e-6)
    q=F(1)
    for target in (F(2),F(7,4),F(97,56)):
        q=(q+3/q)/2; assert q==target
    q=F(0)
    for target in (1,0,1,0):
        q=q-(q**3-2*q+2)/(3*q*q-2); assert q==target
    assert F(1,2)/F(1,10000)==5000
    prediction=(1+math.exp(-.5))/2; error=prediction-math.exp(-.25)
    assert 0<error<1/32
    assert math.isclose(error,.024464546784911834,abs_tol=1e-14)
    # Integrate x^4 and the quadrature kernels exactly, not by implementation calls.
    trapezoid=F(1,2)*(F(1,16)+F(1,2)); simpson=F(1,6)*(F(4,16)+1)
    assert trapezoid==F(9,32) and trapezoid-F(1,5)==F(13,160)
    assert simpson==F(5,24) and simpson-F(1,5)==F(1,120)
    # Kernel derivation at h=1 from integrated truncated power and node evaluations.
    for t in (F(-1),F(-3,4),F(-1,3),F(0),F(1,4),F(3,4),F(1)):
        direct=(1-t)**4/24-(4*max(-t,F(0))**3+(1-t)**3)/18
        closed=-(1-abs(t))**3*(1+3*abs(t))/72
        assert direct==closed
    # (1-u)^3(1+3u) = 1-6u^2+8u^3-3u^4.
    integral=1-F(6,3)+F(8,4)-F(3,5)
    assert integral==F(2,5) and 2*integral/72==F(1,90)
    for n in (10,20):
        approximation=F(n-1,n)**n
        exact=math.exp(-1); error=exact-float(approximation)
        assert 0<error<(math.e-1)/(2*n)
    # Exact Bellman iteration and independent stationary-policy enumeration.
    beta=F(4,5); optimal=(F(80,9),F(55,9)); never=(F(8),F(5))
    operator=lambda v:(4+beta*v[1],max(1+beta*v[1],-1+beta*v[0]))
    assert operator(optimal)==optimal
    assert optimal[0]>never[0] and optimal[1]>never[1]
    # Service forever cycles G->W->G; geometric reward sum is (4-beta)/(1-beta^2).
    assert (4-beta)/(1-beta**2)==optimal[0]
    v=(F(0),F(0))
    starts=[(4,1),(F(24,5),F(11,5)),(F(144,25),F(71,25)),(F(784,125),F(451,125))]
    for target in starts:
        v=operator(v); assert v==target
    for _ in range(26): v=operator(v)
    residual=max(abs(a-b) for a,b in zip(operator(v),v))
    bound=residual/(1-beta)
    actual=max(abs(a-b) for a,b in zip(v,optimal))
    assert actual<=bound<F(1,100)
    assert math.isclose(float(residual),.0018569100589280704,rel_tol=1e-10)
    gap=(-1+beta*v[0])-(1+beta*v[1])
    assert gap>2*beta*bound
    approximate=(F(222,25),F(61,10))
    residual=max(abs(a-b) for a,b in zip(operator(approximate),approximate))
    assert residual==F(1,250) and residual/(1-beta)==F(1,50)
    assert optimal[0]-approximate[0]==F(2,225)
    assert optimal[1]-approximate[1]==F(1,90)
    for c in (F(0),F(1),F(7,5),F(2)):
        service=((4-beta*c)/(1-beta**2),(4*beta-c)/(1-beta**2))
        candidate=service if c<=F(7,5) else never
        T=lambda v:(4+beta*v[1],max(1+beta*v[1],-c+beta*v[0]))
        assert T(candidate)==candidate
        if c==F(7,5): assert service==never
    # Cross-check float download against rational brackets, exact polynomial integrals
    # and exact dynamic optimum; exercise advertised input/termination safeguards.
    path=Path(__file__).resolve().parents[1]/'content/projects/v02-numerics.py'
    spec=importlib.util.spec_from_file_location('benchmark_v02',path)
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    result=module.bisection(root_function,1,2)
    assert result['halvings']==19
    assert abs(result['answer']-root)<=result['error_bound']
    assert result['bracket'][0]<=root<=result['bracket'][1]
    assert module.bisection(lambda x:x,0,1)['answer']==0
    assert math.isclose(module.quadrature(lambda x:x**4,0,1,2),float(trapezoid))
    assert math.isclose(module.quadrature(lambda x:x**4,0,1,2,'simpson'),float(simpson))
    model={'G':{'operate':(4,'W')},'W':{'operate':(1,'W'),'service':(-1,'G')}}
    result=module.value_iteration(model,.8)
    assert result['updates']==30 and result['policy']['W']=='service'
    assert max(abs(result['values'][s]-float(target)) for s,target in zip(('G','W'),optimal))<=result['error_bound']
    rejects(ValueError,lambda:module.bisection(lambda x:x*x+1,-1,1))
    rejects(ValueError,lambda:module.bisection(lambda x:float('nan'),0,1))
    rejects(RuntimeError,lambda:module.bisection(root_function,1,2,1e-12,1))
    adjacent=math.nextafter(1.,2.)
    rejects(RuntimeError,lambda:module.bisection(lambda x:-1 if x==1 else 1,1,adjacent,1e-30))
    rejects(ValueError,lambda:module.quadrature(lambda x:x,0,1,3,'simpson'))
    rejects(ValueError,lambda:module.value_iteration(model,1))
    rejects(RuntimeError,lambda:module.value_iteration(model,.8,1e-12,1))
    zero_discount=module.value_iteration(model,0)
    assert zero_discount['values']=={'G':4.,'W':1.}
    return {'scope':'v02-c12','methods':['80-step rational root bracket and exact Newton iterates',
        'exact quadrature errors and Simpson kernel identities',
        'Euler global-error comparisons','exact Bellman residuals and all stationary policies',
        'downloadable float benchmark cross-checks and termination safeguards'],
        'limitation':'Analytic hypotheses and quantified error proofs are reviewed separately; float outputs are not outward-rounded interval certificates.'}


if __name__=='__main__':
    import json
    print(json.dumps(check()))
