"""Independent exact recurrences and RK4 integrations for v02-c11."""
from fractions import Fraction as F
import math
from check_v02_linear import mm, mv, transpose


def rk4(rhs, initial, end, steps=2000):
    x = list(initial); h = end/steps
    for i in range(steps):
        t = i*h
        k1 = rhs(t, x)
        k2 = rhs(t+h/2, [a+h*b/2 for a,b in zip(x,k1)])
        k3 = rhs(t+h/2, [a+h*b/2 for a,b in zip(x,k2)])
        k4 = rhs(t+h, [a+h*b for a,b in zip(x,k3)])
        x = [a+h*(b+2*c+2*d+e)/6 for a,b,c,d,e in zip(x,k1,k2,k3,k4)]
    return x


def near(a,b):
    assert math.isclose(a,b,rel_tol=1e-9,abs_tol=1e-10), (a,b)


def check():
    stock=F(8)
    for t in range(25):
        assert stock==24-16*F(3,4)**t
        stock=F(3,4)*stock+6
    assert 16*F(3,4)**17>F(1,10)>16*F(3,4)**18
    near(math.log(.1/16)/math.log(.75),17.64160613826393)
    assert 2*F(3,4)**3==F(27,32)
    stock=F(4); debt=F(3200)
    for t in range(30):
        assert stock==8-4*F(-1,4)**t
        assert debt==3000+200*F(21,20)**t
        stock=10-stock/4; debt=F(21,20)*debt-150
    A=[[F(1,2),4],[0,F(1,2)]]; power=[[1,0],[0,1]]
    assert mm(A,transpose(A))!=mm(transpose(A),A)
    for t in range(1,40):
        power=mm(power,A)
        assert power==[[F(1,2)**t,4*t*F(1,2)**(t-1)],[0,F(1,2)**t]]
    jordan=[[1,1],[0,1]]; power=[[1,0],[0,1]]
    for t in range(10):
        assert power==[[1,t],[0,1]]
        power=mm(power,jordan)
    omega=[[0,2],[F(-1,2),0]]
    assert mm(omega,omega)==[[-1,0],[0,-1]]
    for t in (.2,1.,math.pi/2,math.pi):
        result=rk4(lambda _,z:[-z[0]+2*z[1],-.5*z[0]-z[1]], [2,0], t)
        exact=[2*math.exp(-t)*math.cos(t),-math.exp(-t)*math.sin(t)]
        for a,b in zip(result,exact): near(a,b)
        near(result[0]**2+4*result[1]**2,4*math.exp(-2*t))
        forced=rk4(lambda time,x:[6+2*time-2*x[0]],[1],t)[0]
        near(forced,t+2.5-1.5*math.exp(-2*t))
        logistic=rk4(lambda _,x:[.4*x[0]*(1-x[0]/20)],[5],t)[0]
        near(logistic,20/(1+3*math.exp(-.4*t)))
        symmetric=rk4(lambda _,z:[-2*z[0]+z[1],z[0]-2*z[1]],[2,0],t)
        near(symmetric[0],math.exp(-t)+math.exp(-3*t))
        near(symmetric[1],math.exp(-t)-math.exp(-3*t))
    near(2.5*math.log(3),2.7465307216702746)
    near(rk4(lambda _,x:[.4*x[0]*(1-x[0]/20)],[5],2.5*math.log(3))[0],10)
    # Cubic paths, both signs, integrated independently before any blow-up.
    for initial in (-2.,.5,2.):
        for sign in (-1,1):
            end=.03
            result=rk4(lambda _,x:[sign*x[0]**3],[initial],end)[0]
            near(result,initial/math.sqrt(1-2*sign*initial**2*end))
    for h,multiplier in [(F(1,5),F(1,5)),(F(1,2),-1),(F(3,5),F(-7,5))]:
        assert 1-4*h==multiplier
    assert F(1,5)**5==F(1,3125)
    near(math.exp(-4)-.00032,.01799563888873418)
    near((math.exp(-4)-.00032)/math.exp(-4),.9825285919893937)
    return {'scope':'v02-c11','methods':['exact recurrence and matrix-power reconstruction',
        'independent RK4 integration of coupled, forced, logistic and cubic paths',
        'weighted decay identity and Euler boundary checks'],
        'limitation':'Finite calculations check examples; general stability, Picard and series arguments have separate analytic review.'}


if __name__=='__main__':
    import json
    print(json.dumps(check()))
