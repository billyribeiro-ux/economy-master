"""Independent finite calculations for v02-c10; proofs reviewed separately."""
from fractions import Fraction as F
import math
from check_v02_linear import inverse, mv, mm


def bisect(f,lo,hi):
    assert f(lo)*f(hi)<0
    for _ in range(70):
        mid=(lo+hi)/2
        if f(mid)==0: return mid
        if f(lo)*f(mid)>0: lo=mid
        else: hi=mid
    return (lo+hi)/2


def check():
    # Uniform geometric approximation: exact endpoint errors, threshold and integral.
    for n in (0,1,20,24,25,26,27):
        maxerror=3*F(2,3)**(n+1)
        integral=sum((F(2)**(t+1)/(F(3)**t*(t+1)) for t in range(n+1)),F(0))
        for x in (F(0),F(1,3),F(1),F(3,2),F(2)):
            partial=sum(((x/3)**t for t in range(n+1)),F(0))
            limit=1/(1-x/3)
            assert limit-partial==(x/3)**(n+1)/(1-x/3)<=maxerror
        assert 0<3*math.log(3)-float(integral)<=2*float(maxerror)+1e-14
    tolerance=F(1,10000)
    assert 3*F(2,3)**25>tolerance>3*F(2,3)**26
    assert 6*F(2,3)**27>tolerance>6*F(2,3)**28
    assert math.isclose(3*math.log(3),3.295836866004329)
    # Independent Simpson quadrature of the limiting function.
    count=2000; step=2/count
    function=lambda x:1/(1-x/3)
    quadrature=step/3*(function(0)+function(2)+sum((4 if i%2 else 2)*function(i*step) for i in range(1,count)))
    assert abs(quadrature-3*math.log(3))<1e-10

    # Nonlinear fixed point checked by exact iterates against an independent bracket.
    root=bisect(lambda q:q-1-.4*q/(1+q),1,1.4)
    closed=(.4+math.sqrt(4.16))/2
    assert math.isclose(root,closed,abs_tol=1e-14)
    mapping=lambda q:1+F(2,5)*q/(1+q)
    assert mapping(F(1))==F(6,5) and mapping(F(7,5))==F(37,30)
    q=F(1); previous=q
    for n in range(1,7):
        previous=q; q=mapping(q)
        apriori=F(2,9)*F(1,10)**n
        aposteriori=abs(q-previous)/9
        residual=abs(q-mapping(q))/F(9,10)
        error=abs(float(q)-root)
        assert error<=float(apriori)+1e-14
        assert error<=float(aposteriori)+1e-14
        assert error<=float(residual)+1e-14
    assert math.isclose(float(q),1.2198038322261926,abs_tol=1e-14)
    assert F(2,9)*F(1,10)**5>F(1,10**6)>F(2,9)*F(1,10)**6
    perturbed=bisect(lambda q:q-1.001-.4*q/(1+q),1,1.4)
    assert 0<perturbed-root<=.001/.9

    # Rational-domain approximations and harmonic non-Cauchy witness.
    root2=math.sqrt(2)
    decimals=[F(math.floor(10**n*root2),10**n) for n in range(1,7)]
    for n,value in enumerate(decimals,1): assert 0<=root2-float(value)<10**(-n)
    for n in (1,2,10,100):
        assert sum((F(1,j) for j in range(n+1,2*n+1)),F(0))>=F(1,2)
    for n in (1,2,10,100):
        x=.5**(1/n)
        assert math.isclose(x**n,.5,rel_tol=1e-13)

    # Triangular spike: original-function endpoint integration on its actual support.
    for n in (2,3,10,100):
        spike=lambda x:F(n)*max(1-abs(n*x-1),F(0))
        grid=(F(0),F(1,n),F(2,n))
        heights=[spike(x) for x in grid]
        assert heights==[0,n,0]
        area=sum((grid[i+1]-grid[i])*(heights[i+1]+heights[i])/2 for i in range(2))
        assert area==1

    # Affine iteration exercise: exact error and minimum certified step count.
    q=F(2); fixed=F(8,3)
    for n in range(8):
        assert abs(q-fixed)==F(2,3)*F(1,4)**n
        q=2+q/4
    assert F(2,3)*F(1,4)**6>tolerance>F(2,3)*F(1,4)**7

    # Spectral exercise: exact eigenvectors and orthogonal projector reconstruction.
    matrix=[[3,1,0],[1,3,0],[0,0,2]]
    vectors=[[1,1,0],[1,-1,0],[0,0,1]]
    for vector,eigenvalue in zip(vectors,[4,2,2]):
        assert mv(matrix,vector)==[eigenvalue*x for x in vector]
    projectors=[]
    for v in vectors:
        norm2=sum(x*x for x in v)
        projectors.append([[F(x*y,norm2) for y in v] for x in v])
    reconstructed=[[sum(lam*p[i][j] for lam,p in zip([4,2,2],projectors)) for j in range(3)] for i in range(3)]
    assert reconstructed==matrix
    assert mm(projectors[0],projectors[1])==[[0]*3 for _ in range(3)]

    # Implicit system solved by bisection on the nearby branch rather than root formula.
    jac=[[1,1],[2,1]]; inv=inverse(jac)
    assert inv==[[F(-1),F(1)],[F(2),F(-1)]]
    assert mv(inv,[1,0])==[-1,2]
    for a in (2.,2.1):
        y1=bisect(lambda y:y*y-y+a-2,.6,1.3); y2=a-y1
        assert abs(y1*y1+y2-2)<1e-14
        assert abs(y1-(1+math.sqrt(9-4*a))/2)<1e-14
    assert math.isclose(y1,.8872983346207417,abs_tol=1e-14)
    assert math.isclose(y2,1.2127016653792584,abs_tol=1e-14)
    h=1e-5
    upper=bisect(lambda y:y*y-y+(2+h)-2,.6,1.3)
    lower=bisect(lambda y:y*y-y+(2-h)-2,.6,1.3)
    derivative=(upper-lower)/(2*h)
    assert math.isclose(derivative,-1,rel_tol=1e-8)
    assert math.isclose(1-derivative,2,rel_tol=1e-8)
    assert F(1,2)+F(7,4)==F(9,4) and F(1,2)**2+F(7,4)==2
    assert 1-2*F(1,2)==0
    # Explicit small-ball constants make the general proof's inequalities checkable.
    assert 2*math.sqrt(2)*.1<.5
    assert math.sqrt(5)*.01<(1-.5)*.1/2
    return {'scope':'v02-c10','methods':['exact uniform geometric tails and tolerance thresholds',
        'exact polynomial integrals and independent Simpson quadrature',
        'nonlinear rational iterates, independent bisection, step/residual and perturbation bounds',
        'harmonic and spike counterexample calculations','exact affine error sequence',
        'eigenvector and projector reconstruction','implicit roots, Jacobian response and small-ball constants'],
        'limitation':'These finite calculations check original examples; completeness, compactness, spectral and implicit-function theorems require the separate analytic proof review.'}


if __name__=='__main__':
    import json
    print(json.dumps(check()))
