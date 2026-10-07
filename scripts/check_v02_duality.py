"""Independent numerical checks for original v02-c09 examples and exercises.

Finite samples check printed calculations and identities; general theorems
require the separate author reasoning review.
"""
from fractions import Fraction as F
import math


def check():
    # Complete-square identity and feasible/dual bounds across capacity regimes.
    for b in (F(-2),F(1),F(5,2),F(3),F(7,2),F(5)):
        xstar=min(F(3),b); p=(xstar-3)**2
        lamstar=2*max(3-b,F(0))
        d=lambda lam:lam*(3-b)-lam*lam/4
        assert d(lamstar)==p and lamstar*(xstar-b)==0
        assert 2*(xstar-3)+lamstar==0
        for lam in (F(0),F(1),F(3),F(4),F(12)):
            xmin=3-lam/2
            assert (xmin-3)**2+lam*(xmin-b)==d(lam)
            assert d(lam)<=p
            for x in (b,b-1,b-F(1,5)):
                assert (x-3)**2+lam*(x-b)==(x-3+lam/2)**2+d(lam)
                assert d(lam)<=(x-3)**2
    assert (F(4,5)-3)**2==F(121,25)
    assert 3*2-F(9,4)==F(15,4)
    assert F(121,25)-F(15,4)==F(109,100)
    assert F(121,25)-4==F(21,25)
    assert (F(6,5)-3)**2==F(81,25) and 4-4*F(1,5)==F(16,5)
    assert (F(5,2)-3)**2==F(1,4) and (3-3)**2==0
    assert F(1,4)-1==F(-3,4)

    # Hyperbolic-region counterexample and exact disk separation.
    p1=(F(1),F(1)); p2=(F(3),F(1,3))
    mid=tuple((a+b)/2 for a,b in zip(p1,p2))
    assert p1[0]*p1[1]==p2[0]*p2[1]==1 and mid[0]*mid[1]==F(4,3)
    nearest=(F(6,5),F(8,5)); z=(F(3),F(4))
    assert sum(t*t for t in nearest)==4
    assert sum((a-b)**2 for a,b in zip(z,nearest))==9
    assert 3*nearest[0]+4*nearest[1]==10 and 3*z[0]+4*z[1]==25

    # Changed target exercise, no use of the worked-case target.
    d=lambda lam:3*lam-lam*lam/4
    assert d(F(6))==9 and d(F(5))==F(35,4)
    assert (F(3,2)-5)**2==F(49,4)
    assert F(49,4)-d(F(5))==F(7,2)
    assert F(49,4)-9==F(13,4)

    # Equality dual checked via both residuals and original objective.
    for m in (F(-3),F(0),F(6),F(9)):
        x=2*m/3; y=m/3; nu=-4*m/3
        assert x+y==m and 2*x+nu==4*y+nu==0
        value=x*x+2*y*y
        assert value==2*m*m/3==-3*nu*nu/8-nu*m
    assert 4**2+2*2**2==24
    h=1e-5
    assert math.isclose(((2*(6+h)**2/3)-(2*(6-h)**2/3))/(2*h),8,rel_tol=1e-9)

    # Kink: dual finite only when the two multipliers sum to one.
    for u in (F(-2),F(0),F(2)):
        x=max(F(0),-u); p=x
        for lam2 in (F(0),F(1,4),F(1,2),F(1)):
            lam1=1-lam2
            assert 1-lam1-lam2==0 and -lam2*u<=p
        lam2star=F(1) if u<0 else F(0)
        assert -lam2star*u==p
        assert (1-lam2star)*x==lam2star*(-x-u)==0
    for slope in (F(-1),F(-3,4),F(-1,2),F(0)):
        for u in (F(-8),F(-1,10),F(0),F(1,10),F(8)):
            assert max(F(0),-u)>=slope*u
    # Failed Slater example: exact L minimizers and monotone nonattained bounds.
    previous=None
    for lam in (F(1),F(10),F(100),F(1000)):
        x=-1/(2*lam); d=x+lam*x*x
        assert 1+2*lam*x==0 and d==-1/(4*lam)<0
        if previous is not None: assert d>previous
        previous=d
    # Discrete-domain dual gap: evaluate retained-domain infima explicitly.
    assert min(x for x in (F(0),F(1)) if F(1,2)-x<=0)==1
    for lam in (F(0),F(1,2),F(1),F(3,2),F(2),F(4)):
        dual=min(x+lam*(F(1,2)-x) for x in (F(0),F(1)))
        assert dual==min(lam/2,1-lam/2)<=F(1,2)
    assert min(F(1,2),1-F(1,2))==F(1,2)

    # Independently reconstruct payoff choices, KKT and global comparison identity.
    def solve(theta,k):
        q=min(k,max(F(0),theta/2))
        alpha=max(-theta,F(0)); beta=max(theta-2*k,F(0))
        return q,theta*q-q*q,alpha,beta
    for k in (F(2),F(3)):
        previous=None
        for theta in (F(-1),F(0),F(1),F(3),F(4),F(6),F(8),F(9)):
            q,value,alpha,beta=solve(theta,k)
            assert 0<=q<=k and alpha>=0 and beta>=0
            assert theta-2*q+alpha-beta==0 and alpha*q==beta*(k-q)==0
            for alternative in (F(0),k/2,k):
                assert theta*alternative-alternative**2<=value
            if previous is not None: assert q>=previous
            previous=q
    assert solve(F(-1),F(2))==(0,0,1,0)
    assert solve(F(3),F(2))==(F(3,2),F(9,4),0,0)
    assert solve(F(6),F(2))==(2,8,0,2)
    assert solve(F(8),F(3))==(3,15,0,2) and solve(F(9),F(3))==(3,18,0,3)
    assert solve(F(8),F(16,5))[:2]==(F(16,5),F(384,25))
    assert F(384,25)-15==F(9,25)
    assert solve(F(8),F(5))[:2]==(4,16)
    # Distance certificate and the actual squared displacement.
    assert (F(4,5)-1)**2==F(1,25)<=F(109,100)
    assert math.isclose(math.sqrt(1.09),1.044030650891055)
    return {'scope':'v02-c09','methods':['exact completing-square dual identities',
        'primal/dual residuals and bounds across regimes','separation coordinates',
        'equality value and finite-difference sensitivity','kink subgradients and nonattained dual sequence',
        'payoff/capacity KKT, global comparisons and quantity monotonicity',
        'strong-curvature distance certificate'],
        'limitation':'Finite recomputations do not prove general convex-analysis theorems.'}


if __name__=='__main__':
    import json
    print(json.dumps(check()))
