"""Independent exact arithmetic, original exam forms and allocation project."""
from fractions import Fraction as F
from pathlib import Path
import importlib.util
import json
import math
from check_v02_linear import inverse, mv, mm, transpose
from check_v02_dynamics import rk4


def near(a,b,tolerance=1e-8):
    assert math.isclose(float(a),float(b),rel_tol=tolerance,abs_tol=tolerance),(a,b)


def check():
    # Diagnostic.
    assert F(3,4)+F(2,3)==F(17,12)
    assert 3*6-7==11 and (-3)**2==3**2==9
    assert F(100,80)-1==F(1,4) and F(80,100)-1==F(-1,5)
    for r in (F(-1,2),F(0),F(1,3),F(1),F(2)):
        assert (1-r)*sum((r**j for j in range(4)),F(0))==1-r**4
    # Form A: independently reconstruct residual bounds and local derivatives.
    G=lambda x:1+x/3
    assert G(F(3,2))==F(3,2)
    assert abs(G(F(149,100))-F(149,100))/F(2,3)==F(1,100)
    assert sum((F(c,k+1)*3**(k+1) for k,c in enumerate((15,-12,3))),F(0))==18
    gradient=[4,5]; direction=[2,-1]; H=[[2,1],[1,2]]
    assert sum(a*b for a,b in zip(gradient,direction))==3
    assert sum(a*b for a,b in zip(direction,mv(H,direction)))/2==3
    assert 2**2+1*2==6 and -F(2,2*2+1)==F(-2,5)
    assert mv([[3,1],[1,2]],[2,1])==[7,4]
    A=[[F(3,5),F(1,5)],[F(1,5),F(3,5)]]; z=[F(2),F(0)]
    for t in range(20):
        assert z==[F(4,5)**t+F(2,5)**t,F(4,5)**t-F(2,5)**t]
        z=mv(A,z)
    assert 1-3*F(4,5)==F(-7,5)
    for t in (.2,1.,2.):
        near(rk4(lambda _,x:[-3*x[0]+6],[1],t)[0],2-math.exp(-3*t))
    x,y,lam=F(3),F(2),F(2)
    objective=lambda x,y:8*x+6*y-x*x-y*y
    dual=lambda lam,B:lam*B+max(8-lam,0)**2/4+max(6-lam,0)**2/4
    assert objective(x,y)==dual(lam,5)==23
    assert 8-2*x-lam==6-2*y-lam==0
    B=F(51,10); lam=7-B; x=(8-lam)/2; y=(6-lam)/2
    assert x+y==B and objective(x,y)-23==F(39,200)
    assert F(1,2)**9>F(1,1000)>F(1,2)**10
    residual=F(707,500)**2-2
    assert residual==F(-151,250000) and abs(residual)/2==F(151,500000)
    trapezoid=F(1,2)*(F(1,4)+F(1,2))
    simpson=F(1,6)*(4*F(1,4)+1)
    assert trapezoid==F(3,8) and trapezoid-F(1,3)==F(1,24)
    assert simpson==F(1,3)
    assert abs(2+F(1,2)*F(39,10)-F(39,10))/F(1,2)==F(1,10)
    # Form B: implicit responses, projection and continuous trajectories.
    H=[[4,1],[1,6]]; gradient=[3,-5]; direction=[1,2]
    assert sum(a*b for a,b in zip(gradient,direction))==-7
    assert sum(a*b for a,b in zip(direction,mv(H,direction)))/2==16
    assert 4*6-1==23 and 2**3+2**2==12
    assert mv(inverse([[1,1],[2,1]]),[1,0])==[-1,2]
    assert F(1,2)+F(7,4)==F(9,4) and F(1,2)**2+F(7,4)==2
    Hmap=lambda x:F(1,2)+x/4
    assert Hmap(F(2,3))==F(2,3)
    assert abs(Hmap(F(33,50))-F(33,50))/F(3,4)==F(1,150)
    A=[[1,0],[1,1],[1,2]]; b=[1,2,2]
    normal=mm(transpose(A),A); rhs=mv(transpose(A),b)
    theta=mv(inverse(normal),rhs)
    assert normal==[[3,3],[3,5]] and rhs==[5,6] and theta==[F(7,6),F(1,2)]
    residual=[a-c for a,c in zip(b,mv(A,theta))]
    assert residual==[F(-1,6),F(1,3),F(-1,6)]
    assert mv(transpose(A),residual)==[0,0] and sum(r*r for r in residual)==F(1,6)
    for t in (.2,1.,2.):
        result=rk4(lambda _,z:[-2*z[0]+3*z[1],-z[1]],[0,1],t)
        near(result[0],3*(math.exp(-t)-math.exp(-2*t)))
        near(result[1],math.exp(-t))
    f=lambda x,y:(x-3)**2+(y-1)**2
    assert f(2,0)==2 and 2*(2-3)+2==2*(0-1)+2==0
    assert f(F(41,20),F(1,20))==F(361,200)
    assert F(361,200)-2==F(-39,200)
    assert F(1,2)**13>F(1,10000)>F(1,2)**14
    assert 1-F(-2,3)==F(5,3)
    values=[F(j,4)**4 for j in range(5)]
    simpson=F(1,12)*(values[0]+4*values[1]+2*values[2]+4*values[3]+values[4])
    assert simpson==F(77,384) and simpson-F(1,5)==F(1,1920)
    assert 24*F(1,4)**4/180==F(1,1920)
    value=F(399,50); beta=F(3,4); Tv=2+beta*value
    assert Tv==F(1597,200) and abs(Tv-value)/(1-beta)==F(1,50)
    # Delayed check.
    assert mv([[4,0],[0,2]],[-1,2])==[-4,4]
    assert F(1,2)*((-1)*(-4)+2*4)==6
    assert 4/(1-F(2,3))==12
    assert 6*2+4*1-2**2-1**2==11
    assert 3*2+(6-2)**2/4+(4-2)**2/4==11
    assert (3+F(4,5)*F(149,10)-F(149,10))/F(1,5)==F(1,10)

    # Project: exact active-set solutions for all stated capacity regimes.
    root=Path(__file__).resolve().parents[1]
    fixture=json.loads((root/'content/projects/v02-allocation-case.json').read_text())
    path=root/'content/projects/v02-allocation-solution.py'
    spec=importlib.util.spec_from_file_location('allocation_benchmark',path)
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    exact_rows=[]
    for capacity in fixture['capacity_grid']:
        B=F(str(capacity))
        if B<=F(7,2): x,y,lam=B,F(0),12-2*B
        elif B<=16: x,y,lam=(14+B)/5,(2*B-7)/5,(32-2*B)/5
        else: x,y,lam=F(6),F(5),F(0)
        f=12*x+10*y-x*x-y*y
        D=lam*B+max(12-lam,0)**2/4+max(10-2*lam,0)**2/4
        assert x>=0 and y>=0 and lam>=0 and x+2*y<=B
        assert lam*(B-x-2*y)==0 and f==D
        assert (12-2*x-lam<=0 if x==0 else 12-2*x-lam==0)
        assert (10-2*y-2*lam<=0 if y==0 else 10-2*y-2*lam==0)
        result=module.solve(dict(fixture['baseline'],B=capacity))
        for key,exact in zip(('x','y','multiplier','objective'),(x,y,lam,f)):
            near(result[key],exact)
        assert result['resource']<=float(B)+1e-10
        assert result['computed_duality_gap']>=-1e-12
        distance=math.hypot(result['x']-float(x),result['y']-float(y))
        assert distance<=result['distance_bound_if_arithmetic_reliable']+1e-8
        exact_rows.append((B,x,y,lam,f))
    assert [row[4] for row in exact_rows]==[0,20,F(119,4),41,F(269,5),F(304,5),61,61]
    package=module.package(fixture)
    near(package['capacity_value_change'],F(119,500))
    near(package['payoff_value_change'],F(56,5))
    assert F(269,5)+F(119,500)==F(27019,500)
    # Exact envelope integral, split at active-set transitions.
    area=F(7,2)*(12+5)/2+F(25,2)*(5+0)/2
    assert area==61
    # Coarse versus fine multiplier tolerance: independently bound objective error.
    for tolerance in (1e-3,1e-10):
        r=module.solve(fixture['baseline'],tolerance)
        actual_gap=float(F(269,5))-r['objective']
        assert actual_gap>=-1e-12
        assert actual_gap<=r['computed_duality_gap']+1e-12
    # Off-baseline inputs exercise generic curvature, resource weight and corners.
    for case in [dict(a=8,b=6,p=2,q=2,w=1,B=5),
                 dict(a=-1,b=-2,p=2,q=3,w=2,B=10),
                 dict(a=6,b=12,p=2,q=3,w=1,B=0),
                 dict(a=4,b=20,p=3,q=2,w=2,B=2)]:
        r=module.solve(case); x,y,lam=r['x'],r['y'],r['multiplier']
        assert x>=0 and y>=0 and x+case['w']*y<=case['B']+1e-9
        assert r['computed_duality_gap']>=-1e-10
        # Compare against a dense feasible triangular lattice, separate algorithm.
        if case['B']>0:
            best=-math.inf
            for i in range(101):
                xx=case['B']*i/100
                for j in range(101-i):
                    yy=case['B']*j/(100*case['w'])
                    val=case['a']*xx+case['b']*yy-(case['p']*xx*xx+case['q']*yy*yy)/2
                    best=max(best,val)
            assert r['objective']>=best-1e-8
    return {'scope':'Volume 2 diagnostic, Form A, Form B, delayed check and project',
        'methods':['exact fractional exam residuals and quadrature',
                   'normal-equation reconstruction and independent RK4 solutions',
                   'exact project active-set/KKT/dual matching across all supplied capacities',
                   'benchmark cross-check, sensitivity and envelope integral',
                   'off-baseline dense feasible-search comparisons'],
        'limitation':'Numerical recomputation complements separate proof/rubric review; it is not independent assessment of a learner.'}


if __name__=='__main__':
    print(json.dumps(check()))
