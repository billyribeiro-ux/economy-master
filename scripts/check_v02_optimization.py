"""Numerical checks for v02-c07/c08, separate from proof/regularity review."""
from fractions import Fraction as F
import math
from check_v02_linear import dot, mv, inverse


def close(a,b,tolerance=1e-9):
    assert math.isclose(a,b,rel_tol=tolerance,abs_tol=tolerance),(a,b)


def partial(f,point,i,h=1e-5):
    hi=list(point); lo=list(point); hi[i]+=h; lo[i]-=h
    return (f(*hi)-f(*lo))/(2*h)


def positive_root(f,lo,hi):
    assert f(lo)*f(hi)<0
    for _ in range(70):
        mid=(lo+hi)/2
        if f(mid)==0: return mid
        if f(mid)*f(lo)>0: lo=mid
        else: hi=mid
    return (lo+hi)/2


def benefit(x,y):
    return 8*x+6*y-x*x-y*y


def allocation(m):
    assert m>0
    if m<=1: return m,F(0),8-2*m,F(0),2-2*m
    if m<7: return (m+1)/2,(m-1)/2,7-m,F(0),F(0)
    return F(4),F(3),F(0),F(0),F(0)


def check():
    # c07: independent exact increments and finite-difference responses.
    cost=lambda q,k:10+4*q*q+q*k+2*k*k
    assert cost(3,2)==60
    assert cost(F(31,10),F(9,5))-60==F(1,2)
    h=[F(1,10),F(-1,5)]; grad=[26,11]; hc=[[8,1],[1,4]]
    assert dot(grad,h)==F(2,5) and dot(h,mv(hc,h))/2==F(1,10)
    close(partial(cost,[3,2],0),26,1e-8)
    close(partial(cost,[3,2],1),11,1e-8)
    for lam in (6+math.sqrt(5),6-math.sqrt(5)):
        close((8-lam)*(4-lam)-1,0)
        assert lam>0
    assert dot([26,11],[11,-26])==0 and dot([26,11],[26,11])==797
    quadratic=lambda x,y:3*x*x+2*x*y+4*y*y-5*x
    assert quadratic(1,2)==18
    assert quadratic(F(11,10),F(19,10))==F(67,4)
    he=[F(1,10),F(-1,10)]; ge=[5,18]; Hessian=[[6,2],[2,8]]
    assert dot(ge,he)==F(-13,10) and dot(he,mv(Hessian,he))/2==F(1,20)
    assert dot(ge,[F(3,5),F(4,5)])==F(87,5)
    close(partial(quadratic,[1,2],0),5,1e-8)
    close(partial(quadratic,[1,2],1),18,1e-8)
    for t in (F(1,10),F(1,100),F(1,1000)):
        assert t*t/(t*t+t*t)==F(1,2)
        assert (t**3/(t*t+t*t))/t==F(1,2)
    production=lambda k,l:2*math.sqrt(k*l)
    close(production(4,9),12)
    close(partial(production,[4,9],0),1.5,1e-8)
    close(partial(production,[4,9],1),2/3,1e-8)
    close(1.5*.2+(2/3)*(-.3),.1)
    close(production(4.2,8.7),12.08966500776593)
    jacobian=[[1,2],[4,2]]
    assert inverse(jacobian)==[[F(-1,3),F(1,3)],[F(2,3),F(-1,6)]]
    dx=mv(inverse(jacobian),[F(3,100),0])
    assert dx==[F(-1,100),F(1,50)]
    x=F(2)+dx[0]; y=F(1)+dx[1]
    assert [x*y-2,x*x+y*y-5]==[F(149,5000),F(1,2000)]
    path=lambda t:(1+t)**2*t*t+math.exp(t*t)
    close((path(1+1e-5)-path(1-1e-5))/2e-5,12+2*math.e,1e-8)
    # Solve each market independently by bisection, not its printed closed form.
    for a in (1.,1.1):
        p=positive_root(lambda p:p*p+2*p+a-25,0,5)
        close(p,-1+math.sqrt(26-a))
        close(25-p*p,2*p+a)
    close(-1+math.sqrt(24.9),3.989989979949859)
    close(2*(-1+math.sqrt(24.9))+1.1,9.079979959899718)
    assert mv(inverse([[8,1],[-2,1]]),[0,1])==[F(-1,10),F(4,5)]
    a0=1; da=1e-5
    p_hi=positive_root(lambda p:p*p+2*p+(a0+da)-25,0,5)
    p_lo=positive_root(lambda p:p*p+2*p+(a0-da)-25,0,5)
    close((p_hi-p_lo)/(2*da),-.1,1e-8)
    assert mv(inverse([[6,1],[-1,1]]),[0,1])==[F(-1,7),F(6,7)]
    close(positive_root(lambda p:p*p+p+4-16,0,4),3)
    assert F(1,200)*100==F(1,2)
    close((math.sqrt(4+1e-5)-math.sqrt(4-1e-5))/2e-5,.25,1e-8)

    # c08: log optimum, equality sensitivity and exact KKT certificates.
    m=F(12); x=m/6; y=2*m/3; lam=3/m
    assert (x,y,lam)==(2,8,F(1,4))
    assert 2*x+y==m and 1/x==2*lam and 2/y==lam
    close(math.log(x)+2*math.log(y),math.log(128))
    close(math.log(128),4.852030263919617)
    close(3*math.log(1.05),.14637049250829615)
    close(float(lam)*.6,.15)
    # Recompute value and all complementarity/stationarity residuals in each regime.
    for m in (F(1,2),F(9,10),F(1),F(11,10),F(2),F(4),F(7),F(8)):
        x,y,lam,mux,muy=allocation(m)
        assert x>=0 and y>=0 and x+y<=m
        assert lam>=0 and mux>=0 and muy>=0
        assert lam*(m-x-y)==mux*x==muy*y==0
        assert 8-2*x-lam+mux==0 and 6-2*y-lam+muy==0
        expected=8*m-m*m if m<=1 else (7*m-m*m/2+F(1,2) if m<7 else F(25))
        assert benefit(x,y)==expected
        # The exact quadratic difference certificate holds for feasible alternatives:
        # B(z)-B(x*) = gradient(x*) dot (z-x*) - squared displacement.
        for zx,zy in ((F(0),F(0)),(m,F(0)),(F(0),m),(m/3,m/3)):
            d=[zx-x,zy-y]; gradient=[8-2*x,6-2*y]
            assert benefit(zx,zy)-benefit(x,y)==dot(gradient,d)-dot(d,d)
            assert benefit(zx,zy)<=benefit(x,y)
    assert benefit(F(1,2),0)==F(15,4)
    assert benefit(F(5,2),F(3,2))==F(41,2) and benefit(4,3)==25
    v09=benefit(*allocation(F(9,10))[:2]); v11=benefit(*allocation(F(11,10))[:2])
    assert v09==F(639,100) and v11==F(1519,200)
    assert v11-v09==F(241,200)
    assert F(31,5)*F(1,5)==F(31,25)
    assert F(31,25)-F(241,200)==F(7,200)
    # Changed-benefit exercise, checked without importing its worked-case parameters.
    for m,x,y,lam,mux,muy,expected in (
        (2,2,0,6,0,2,16),(5,4,1,2,0,0,27)):
        assert x+y==m and min(x,y,lam,mux,muy)>=0
        assert 10-2*x-lam+mux==0 and 4-2*y-lam+muy==0
        assert mux*x==muy*y==0 and 10*x+4*y-x*x-y*y==expected
    assert 6+2==8 and 6**2+3*2**2==48
    assert 2*6-12==6*2-12==0 and F(3,2)*8==12
    assert 6+3*2==12 and F(1,6)*3==F(1,2)
    close(math.log(6)+math.log(2),math.log(12))
    assert 2*(1-2)+2==0 and (1-2)**2==1
    for x,nu in ((-1,F(1,2)),(1,F(-1,2))):
        assert x*x==1 and 1+2*nu*x==0
        assert 2*nu==(-x)
    assert 1+2*F(100)*0==1  # No finite multiplier repairs the failed CQ example.
    return {'scope':'v02-c07 and v02-c08',
            'methods':['exact quadratic increments and Jacobian inverse products',
                       'finite-difference partial/chain response checks',
                       'independent nonlinear root finding for equilibrium branches',
                       'primal/dual feasibility, complementarity and stationarity residuals',
                       'exact quadratic global-comparison identities',
                       'value, transition and envelope recomputation'],
            'limitation':'Numerical checks do not prove general differentiability/optimization theorems or establish empirical model validity.'}


if __name__=='__main__':
    import json
    print(json.dumps(check()))
