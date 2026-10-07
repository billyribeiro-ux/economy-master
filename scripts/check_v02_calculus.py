"""Independent numerical checks for Volume 2 Chapters 1–4.

These calculations check the printed determinate results and sample derivative/
integral implementations. Quantified proofs and theorem hypotheses require the
separate editorial record; finite numerical checks are not proofs.
"""
from fractions import Fraction as F
import math


def close(a, b, tolerance=1e-9):
    assert math.isclose(a, b, rel_tol=tolerance, abs_tol=tolerance), (a, b)


def derivative(f, x, h=1e-5):
    # A finite-difference calculation independent of symbolic differentiation.
    return (f(x+h)-f(x-h))/(2*h)


def simpson(f, a, b, n=2000):
    assert n > 0 and n % 2 == 0
    h=(b-a)/n
    return h/3*(f(a)+f(b)+4*sum(f(a+i*h) for i in range(1,n,2))
                +2*sum(f(a+i*h) for i in range(2,n,2)))


def check():
    # c01: finite set results, witnesses, recurrence and exceptional factor.
    universe={1,2,3,4,5,6}; a={1,2,4}; b={2,3,4}
    assert a|b == {1,2,3,4} and a&b == {2,4}
    assert a-b == {1} and universe-(a|b)=={5,6}
    assert abs(0-1)<=1 and abs(1-2)<=1 and not abs(0-2)<=1
    assert (2-3)**2 == (4-3)**2 == 1
    balance=F(100)
    for n, expected in enumerate([F(130),F(163),F(1993,10)],1):
        balance=F(11,10)*balance+20
        closed=F(11,10)**n*100+20*(F(11,10)**n-1)/F(1,10)
        assert balance==closed==expected
    assert [100+20*n for n in range(4)] == [100,120,140,160]
    loan=F(200)
    for n in range(1,11):
        loan=F(21,20)*loan-30
        assert loan==600-400*F(21,20)**n
        if n<=2: assert loan==[180,159][n-1]
    assert (1-4)**3 == -27 < 1+3*(-4)
    assert 3**2==(-3)**2==9

    # c02: printed tolerances, roots, retained brackets and discounted tails.
    assert F(3,301)<F(1,100) and F(3,300)==F(1,100)
    z=lambda p: 40/(1+p)-(4+2*p)
    close(z(3),0)
    lo,hi=0.,10.; brackets=[]
    for _ in range(5):
        mid=(lo+hi)/2
        if z(mid)>0: lo=mid
        else: hi=mid
        brackets.append((lo,hi))
    assert brackets==[(0,5),(2.5,5),(2.5,3.75),(2.5,3.125),(2.8125,3.125)]
    close((lo+hi)/2,2.96875)
    close((hi-lo)/2,.15625)
    close(abs((lo+hi)/2-3),.03125)
    root=(-1+math.sqrt(41))/2
    close(30/(1+root),3*root)
    assert round(root,6)==2.701562
    assert 10/2**(9+1)<=.01 < 10/2**(8+1)
    for n in (1,5,22,23):
        partial=sum(F(12)*F(5,6)**t for t in range(1,n+1))
        assert partial==60*(1-F(5,6)**n)
    assert 60*F(5,6)**23<1<60*F(5,6)**22
    close(60*(5/6)**22,1.0868355543578687)
    close(60*(5/6)**23,.905696295298224)

    # c03: exact changes, symbolic responses cross-checked by differences.
    cost=lambda q: 40+6*q+q*q
    assert cost(4)==80 and 6+2*4==14
    close(cost(4.1)-cost(4),1.41)
    close(14*.1,1.4); close(40/4+6+4,20)
    close(-40/4**2+1,-1.5); close(14*4/80,.7)
    close(derivative(cost,4),14,1e-8)
    close(derivative(lambda q: cost(q)/q,4),-1.5,1e-8)
    close(derivative(lambda x:(x*x+1)*math.exp(-x),.7),
          math.exp(-.7)*(1.4-(.7**2+1)),1e-8)
    close(derivative(lambda x:math.log(2*x+3),.7),2/(2*.7+3),1e-8)
    close(derivative(lambda x:(3*x+1)/(x-2),.7),-7/(.7-2)**2,1e-8)
    assert 3*2**2+2*2-7==9
    close((3*2.05**2+2*2.05-7)-9,.7075)
    assert 25+4*5+2*5**2==95 and 4+4*5==24
    close(95/5,19); close(24*5/95,24/19)
    close(-25/5**2+2,1)
    close(1.1**-1.5,.8667841720414474)
    # Independently evaluate the two implicit branches from the quadratic.
    branch=lambda x,sign:(-x+sign*math.sqrt(28-3*x*x))/2
    close(branch(1,1),2); close(branch(1,-1),-3)
    close(derivative(lambda x:branch(x,1),1),-.8,1e-8)
    close(derivative(lambda x:branch(x,-1),1),-.2,1e-8)
    close(derivative(lambda x:math.sqrt(25-x*x),3),-.75,1e-8)
    price=lambda r:121/(1+r)**2
    slope=-242/1.1**3; curvature=726/1.1**4
    close(price(.1),100)
    close(derivative(price,.1),slope,1e-8)
    close(slope,-181.8181818181818)
    close(curvature,495.8677685950413)
    linear=100+slope*.01; quadratic=linear+curvature*.01**2/2
    close(linear,98.18181818181819)
    close(quadratic,98.20661157024794)
    close(price(.11),98.20631442253062)
    bound=2904/1.1**5*.01**3/6
    assert abs(quadratic-price(.11))<bound
    assert round(bound,6)==.000301
    close(math.log(1.1),.09531017980432493)
    exponential_approx=1+.2+.2**2/2
    assert 0<math.exp(.2)-exponential_approx<1.222*.2**3/6
    close(math.exp(.2),1.2214027581601699)
    price1=lambda r:110/(1+r)
    slope1=-110/1.1**2; curvature1=220/1.1**3
    linear1=100+slope1*.02; quadratic1=linear1+curvature1*.02**2/2
    close(price1(.1),100); close(price1(.12),98.21428571428571)
    close(linear1,98.18181818181819); close(quadratic1,98.21487603305785)
    assert abs(quadratic1-price1(.12))<abs(linear1-price1(.12))

    # c04: direct rectangle sums and independent quadrature of smooth examples.
    for n in (4,100):
        h=F(4,n)
        left=sum((6+2*i*h)*h for i in range(n))
        right=sum((6+2*i*h)*h for i in range(1,n+1))
        midpoint=sum((6+2*(F(i)+F(1,2))*h)*h for i in range(n))
        assert left==40-F(16,n) and right==40+F(16,n) and midpoint==40
    close(simpson(lambda q:6+2*q,0,4),40)
    close(simpson(lambda x:2*x/(1+x*x),0,2),math.log(5))
    close(simpson(lambda t:t*math.exp(-.05*t),0,5),
          (1-(1+.05*5)*math.exp(-.05*5))/.05**2)
    pv5=simpson(lambda t:120*math.exp(-.03*t),0,5)
    close(pv5,557.1680942997688)
    close(pv5+4000*math.exp(-.15),4000)
    assert 15+4*2+2**3==31 and 31-(15+4+1)==11
    close(simpson(lambda x:x,-2,2),0)
    close(simpson(abs,-2,2),4)
    close(simpson(lambda x:3*x*x*math.exp(x**3),0,1),math.e-1)
    close(simpson(math.log,1,math.e),1)
    close(simpson(lambda x:x*math.exp(x),0,1),1)
    # Endpoint limit formulas rather than quadrature at singular endpoints.
    for epsilon in (1e-2,1e-4,1e-6):
        assert 0<2*(1-math.sqrt(epsilon))<2
    assert -math.log(1e-6)>-math.log(1e-4)>-math.log(1e-2)
    pv10=simpson(lambda t:80*math.exp(-.04*t),0,10)
    close(pv10,659.3599079287213)
    close(pv10+2000*math.exp(-.4),2000)
    horizon=math.log(20)/.04
    close(horizon,74.89330683884977); close(2000*math.exp(-.04*horizon),100)
    assert 20-2*6==8 and 8*6==48
    close(simpson(lambda q:20-2*q,0,6),84)
    close(simpson(lambda q:12-2*q,0,6),36)
    assert 30+5*4==50
    for n in (4,100):
        h=F(2,n)
        assert sum((6+2*i*h)*h for i in range(n))==16-F(4,n)
        assert sum((6+2*i*h)*h for i in range(1,n+1))==16+F(4,n)
    return {'scope':'v02-c01 through v02-c04',
            'methods':['exact rational recurrence and rectangle sums',
                       'root/bracket and tail recomputation',
                       'finite-difference derivative cross-checks',
                       'independent Simpson quadrature',
                       'Taylor remainder bounds and endpoint calculations'],
            'limitation':'Numerical checks do not prove quantified theorems.'}


if __name__=='__main__':
    import json
    print(json.dumps(check()))
