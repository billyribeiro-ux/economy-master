"""Exact finite-law and independent quadrature checks for Chapters v03-c05/c06.

General convergence/proof claims receive a separate written audit. Numerical
examples, finite inequalities and Taylor/cutoff calculations are checked here.
"""
from fractions import Fraction as F
from itertools import product
from math import comb, sqrt, erf, pi, exp, cos, isclose
from check_v03_moments import moments, covariance, simpson, near


def phi(t):
    return exp(-t*t/2)/sqrt(2*pi)


def Phi(t):
    return (1+erf(t/sqrt(2)))/2


def double_integral(f, xa, xb, ya, yb):
    return simpson(lambda x: simpson(lambda y:f(x,y),ya(x),yb(x),80),xa,xb,400)


def binomial(n,p):
    weights=[F(comb(n,k))*p**k*(1-p)**(n-k) for k in range(n+1)]
    assert sum(weights)==1
    return weights


def check():
    checks=[]
    cash=[-40,20,80]; low=[F(3,10),F(3,20),F(1,20)]
    high=[F(1,20),F(1,5),F(1,4)]
    marg=[a+b for a,b in zip(low,high)]
    assert sum(low)==sum(high)==F(1,2)
    lm=moments(cash,[2*w for w in low]); hm=moments(cash,[2*w for w in high])
    assert lm==(-10,1720,1620) and hm==(44,3520,1584)
    assert moments(cash,marg)==(17,2620,2331)
    assert moments([-10,44],[F(1,2)]*2)==(17,1018,729)
    assert (lm[2]+hm[2])/2==1602
    direct_loss=lambda a,b:sum(w*(x-a)**2 for x,w in zip(cash,low))+sum(w*(x-b)**2 for x,w in zip(cash,high))
    assert [direct_loss(a,b) for a,b in [(0,0),(17,17),(0,40),(-10,44)]]==[2620,2331,1660,1602]
    for a,b in product((-20,0,17,40,60),repeat=2):
        assert direct_loss(a,b)==1602+F(1,2)*((-10-a)**2+(44-b)**2)
    assert sum(w*(x+10) for x,w in zip(cash,low))==0
    assert sum(w*(x-44) for x,w in zip(cash,high))==0
    checks.append('Exact signal-table marginals, conditional moments, orthogonal residuals and forecast-loss decomposition')

    for density, norm, mean, second, var, within, between, upper in [
        (lambda x,y:2,1,F(1,3),F(1,6),F(1,18),F(1,24),F(1,72),F(1,4)),
        (lambda x,y:3*y,1,F(3,8),F(1,5),F(19,320),F(1,20),F(3,320),F(5,16))]:
        near(double_integral(density,0,1,lambda x:x,lambda x:1),norm)
        near(double_integral(lambda x,y:x*density(x,y),0,1,lambda x:x,lambda x:1),mean)
        near(double_integral(lambda x,y:x*x*density(x,y),0,1,lambda x:x,lambda x:1),second)
        near(double_integral(lambda x,y:(x-float(mean))**2*density(x,y),0,1,lambda x:x,lambda x:1),var)
        near(double_integral(lambda x,y:(x-y/2)**2*density(x,y),0,1,lambda x:x,lambda x:1),within)
        near(double_integral(lambda x,y:(y/2-float(mean))**2*density(x,y),0,1,lambda x:x,lambda x:1),between)
        near(double_integral(density,.5,1,lambda x:x,lambda x:1),upper)
        for y in (.1,.25,.6,.9):
            marginal=simpson(lambda x:density(x,y),0,y,80)
            near(simpson(lambda x:density(x,y)/marginal,0,y,80),1)
            near(simpson(lambda x:x*density(x,y)/marginal,0,y,80),y/2)
            near(simpson(lambda x:(x-y/2)**2*density(x,y)/marginal,0,y,80),y*y/12)
    for a,b in [(F(1,4),F(3,4)),(F(3,4),F(1,4)),(F(1,2),F(1,2))]:
        direct=double_integral(lambda x,y:2,0,min(float(a),float(b)),lambda x:x,lambda x:float(b))
        near(direct,b*b if b<=a else 2*a*b-a*a)
    near(double_integral(lambda x,y:2*x*y,0,1,lambda x:x,lambda x:1),F(1,4))
    near(double_integral(lambda x,y:2*y,0,1,lambda x:x,lambda x:1),F(2,3))
    near(double_integral(lambda x,y:2*y*y,0,1,lambda x:x,lambda x:1),F(1,2))
    checks.append('Independent triangular-domain quadrature for normalization, CDFs, conditional laws, cross-moments and within/between variance')

    x=[0,0,2,2]; y=[-1,1,-1,1]; p=[F(1,10),F(3,10),F(2,5),F(1,5)]
    assert moments(x,p)[0::2]==(F(6,5),F(24,25))
    for sign,expected in [(-1,(F(8,5),F(16,25))),(1,(F(4,5),F(24,25)))]:
        values=[a for a,b in zip(x,y) if b==sign]
        weights=[2*w for b,w in zip(y,p) if b==sign]
        assert moments(values,weights)[0::2]==expected
    assert F(4,5)+F(4,25)==F(24,25)
    near(simpson(lambda u:u*u/2,-1,1),F(1,3))
    near(simpson(lambda u:u**3/2,-1,1),0)
    for threshold in (.0625,.25,.5625):
        near(simpson(lambda u:.5,-sqrt(threshold),sqrt(threshold)),sqrt(threshold))
    bits=list(product((0,1),repeat=2))
    conditional_by_b={b:sum(F(a,2) for a,bb in bits if bb==b) for b in (0,1)}
    for a in (0,1):
        outer=sum(conditional_by_b[b]*F(1,2) for aa,b in bits if aa==a)
        direct=sum(F(aa,2) for aa,b in bits if aa==a)
        assert outer==F(1,2) and direct==a and outer!=direct
    prior=F(1,5); poor=F(7,10); good=F(1,10)
    # Enumerate latent quality and all three flags rather than use odds shortcuts.
    flag_states=[]
    for state,weight,rate in [(1,prior,poor),(0,1-prior,good)]:
        for outcomes in product((0,1),repeat=3):
            w=weight
            for bit in outcomes: w*=rate if bit else 1-rate
            flag_states.append((state,outcomes,w))
    assert sum(w for _,_,w in flag_states)==1
    marginal=sum(w for _,bits,w in flag_states if bits[0])
    both=sum(w for _,bits,w in flag_states if bits[0] and bits[1])
    assert marginal==F(11,50) and both==F(53,500)
    assert both-marginal*marginal==F(36,625)
    assert sum(w for state,bits,w in flag_states if state and bits[0] and bits[1])/both==F(49,53)
    assert sum(w for _,bits,w in flag_states if all(bits))/both==F(347,530)
    # Random count: construct the full finite sum distribution with Xi = 5 or 11.
    sum_values=[]; sum_weights=[]
    for n,pn in [(0,F(1,5)),(2,F(1,2)),(5,F(3,10))]:
        for outcomes in product((5,11),repeat=n):
            sum_values.append(sum(outcomes));sum_weights.append(pn*F(1,2)**n)
    assert moments(sum_values,sum_weights)[0::2]==(20,F(461,2))
    assert moments([0,2,5],[F(1,5),F(1,2),F(3,10)])[0::2]==(F(5,2),F(13,4))
    assert moments([-10,0,10],[F(1,10),F(4,5),F(1,10)])[0::2]==(0,20)
    assert F(1,5)*100==20
    checks.append('Conditional exercise tables, singular-law generating integrals, latent-state enumeration and full random-sum distribution')

    p=F(1,5); n=625; probabilities=binomial(n,p)
    tail=sum(probabilities[:101])+sum(probabilities[150:])
    near(tail,.014206310947840273,1e-12)
    near(2*Phi(-2.45),.014285621470542909,1e-12)
    assert p*(1-p)/(625*F(1,25)**2)==F(4,25)
    assert p*(1-p)/(F(1,20)*F(1,25)**2)==2000
    near((p*p+(1-p)**2)/sqrt(p*(1-p))/sqrt(625),.068)
    assert F(3,10)*F(7,10)/(400*F(1,20)**2)==F(21,100)
    assert F(3,10)*F(7,10)/(F(1,20)*F(1,20)**2)==1680
    assert F(1,4)/(F(1,20)*F(1,20)**2)==2000
    n=100; probabilities=binomial(n,F(1,10))
    near(sum(probabilities[15:]),.07257296526488076,1e-12)
    near(1-Phi(1.5),.06680720126885809,1e-12)
    near(1-Phi(5/3),.047790352272814696,1e-12)
    for n in (5,20,80):
        p=F(2,5); probs=binomial(n,p)
        for eps in (F(1,10),F(1,5),F(2,5)):
            failure=sum(w for k,w in enumerate(probs) if abs(F(k,n)-p)>=eps)
            assert failure <= min(F(1),p*(1-p)/(n*eps*eps))
    checks.append('Exact binomial tails versus corrected/uncorrected Gaussian approximations, Chebyshev bounds and Berry–Esseen inputs')

    # Exhaust shared-shock finite paths, checking covariance and grand-mean scaling.
    for n in (1,2,4,6):
        observations=[]; weights=[]
        for b in (-2,2):
            for errors in product((-1,1),repeat=n):
                observations.append(F(b)+F(sum(errors),n));weights.append(F(1,2)**(n+1))
        assert moments(observations,weights)[0::2]==(0,4+F(1,n))
        assert all(abs(value)>=1 for value in observations)
    assert 4+F(1,25)==F(101,25)
    assert 4+F(1,1000)==F(4001,1000)
    assert F(4,10)+F(1,1000)==F(401,1000)
    for block in range(1,9):
        size=2**block
        for numerator in (0,1,size//2,size-1):
            u=F(2*numerator+1,2*size)
            states=[int(F(k,size)<=u<F(k+1,size)) for k in range(size)]
            assert sum(states)==1 and 0 in states
    checks.append('Exhaustive common-shock averages and deterministic block construction for convergence-mode counterexamples')

    # Check first-crossing events directly in small independent walks.
    for n in (4,8):
        for threshold in (2,3,4):
            first=[0]*n; terminal_second_on_event=[F(0)]*n; crossed_second=[F(0)]*n
            weight=F(1,2)**n
            for outcomes in product((-1,1),repeat=n):
                partial=[]; total=0
                for bit in outcomes: total+=bit;partial.append(total)
                for k,value in enumerate(partial):
                    if abs(value)>=threshold:
                        first[k]+=1
                        terminal_second_on_event[k]+=weight*total**2
                        crossed_second[k]+=weight*value**2
                        break
            probability=sum(first)*weight
            assert probability<=F(n,threshold**2)
            for k in range(n):
                assert terminal_second_on_event[k]>=crossed_second[k]>=threshold**2*first[k]*weight
    assert F(64,16**2)==F(1,4)
    for M in (3,8,12):
        eps=F(1,5)
        finite_sum=sum(F(1,2**m)/eps**2 for m in range(M,M+30))
        remainder=F(1,2**(M+29))/eps**2
        assert finite_sum+remainder==F(2,2**M)/eps**2
    checks.append('Exact first-crossing maximal-inequality terms and dyadic geometric tail certificates')

    # Smooth transition used in the CLT proof: algebra and Taylor remainder.
    def q(t):
        if t<=0:return 1.
        if t>=1:return 0.
        return 1-10*t**3+15*t**4-6*t**5
    def qp(t):return -30*t*t*(1-t)**2 if 0<t<1 else 0.
    def qpp(t):return -60*t*(1-t)*(1-2*t) if 0<t<1 else 0.
    for k in range(101):
        t=k/100
        assert -1e-14 <= q(t) <= 1+1e-14 and qp(t)<=0
        assert abs(qpp(t))<=15
    for s,u in product((-2.,-.1,0.,.1,.5,.9,1.,2.),(-2.,-.2,-.01,.01,.2,2.)):
        remainder=q(s+u)-q(s)-qp(s)*u-.5*qpp(s)*u*u
        assert abs(remainder)<=.5*u*u*min(60*abs(u),30)+1e-13
    for z in (-1.,0.,1.):
        delta=.5
        lower=simpson(lambda t:q((t-z+delta)/delta)*phi(t),-8,8,16000)
        upper=simpson(lambda t:q((t-z)/delta)*phi(t),-8,8,16000)
        assert Phi(z-delta)-1e-10<=lower<=Phi(z)+1e-10
        assert Phi(z)-1e-10<=upper<=Phi(z+delta)+1e-10
    for t in (.5,1.,2.):
        target=simpson(lambda z:cos(t*z)*phi(z),-8,8)
        near(target,exp(-t*t/2),1e-11)
        for n in (8,32):
            probs=binomial(n,F(1,2))
            direct=sum(float(w)*cos(t*(2*k-n)/sqrt(n)) for k,w in enumerate(probs))
            near(direct,cos(t/sqrt(n))**n,1e-11)
        assert abs(cos(t/sqrt(128))**128-target)<abs(cos(t/sqrt(32))**32-target)
    # Pareto alpha 5/2 finite mean/variance, infinite third-moment cutoff.
    near(simpson(lambda v:5*v**4,0,1),1)
    near(simpson(lambda v:5*v*v,0,1),F(5,3))
    near(simpson(lambda v:5,0,1),5)
    for cutoff in (4,9,16):
        near(simpson(lambda x:2.5/sqrt(x),1,cutoff),5*(sqrt(cutoff)-1),1e-9)
    checks.append('Smooth CDF transition/Taylor bounds, normal comparison integrals and finite-second/infinite-third-moment example')
    return {'status':'passed','chapters':['v03-c05','v03-c06'],'checks':checks,
            'limitations':['General tower, LLN and CLT results require the separately recorded written proof audit; finite numerical checks do not establish convergence theorems.']}


if __name__=='__main__':
    import json
    print(json.dumps(check(),indent=2))
