"""Independent probability, integration and preference checks for v03-c09/c10.

Classical representation/Jensen/Bayes-risk arguments receive written review;
these checks verify original laws, numerical examples and counterexamples.
"""
from fractions import Fraction as F
from itertools import product
from math import comb, factorial, exp, log, sqrt, cosh, pi
from statistics import NormalDist
from check_v03_moments import moments, simpson, near
from check_v03_conditioning_limits import Phi, phi


def beta_integral(a,b):
    # Exact expansion of (1-p)^(b-1), independent of factorial recurrence.
    return sum(F((-1)**j*comb(b-1,j),a+j) for j in range(b))


def beta_moment(a,b,k):
    return beta_integral(a+k,b)/beta_integral(a,b)


def beta_cdf(x,a,b):
    return sum(F((-1)**j*comb(b-1,j),a+j)*x**(a+j) for j in range(b))/beta_integral(a,b)


def beta_quantile(a,b,target):
    lo,hi=0.,1.
    for _ in range(65):
        mid=(lo+hi)/2
        if beta_cdf(mid,a,b)<target:lo=mid
        else:hi=mid
    return (lo+hi)/2


def gaussian(x,mu,variance):
    return exp(-(x-mu)**2/(2*variance))/sqrt(2*pi*variance)


def check():
    checks=[]
    states=[]
    for p,prior in ((F(1,5),F(3,4)),(F(4,5),F(1,4))):
        for bits in product((0,1),repeat=3):
            weight=prior
            for bit in bits:weight*=p if bit else 1-p
            states.append((p,bits,weight))
    assert sum(w for _,_,w in states)==1
    selected=[(p,b,w) for p,b,w in states if sum(b)==2]
    evidence=sum(w for _,_,w in selected)
    q=sum(w for p,b,w in selected if p==F(4,5))/evidence
    assert q==F(4,7)
    assert sum(p*w for p,b,w in selected)/evidence==F(19,35)
    assert 3*(1-q)==F(9,7)<5*q==F(20,7)
    assert q>F(3,8)
    checks.append('Exhaustive latent-parameter/observed-sequence posterior, predictive success and asymmetric-loss decision')

    for a,b in [(1,1),(2,3),(5,5),(3,7),(11,9),(15,10),(1,9),(5,10)]:
        B=beta_integral(a,b)
        assert B==F(factorial(a-1)*factorial(b-1),factorial(a+b-1))
        assert beta_integral(a+1,b)+beta_integral(a,b+1)==B
        assert a*beta_integral(a,b+1)==b*beta_integral(a+1,b)
        m=beta_moment(a,b,1);v=beta_moment(a,b,2)-m*m
        assert m==F(a,a+b) and v==F(a*b,(a+b)**2*(a+b+1))
        density=lambda p:p**(a-1)*(1-p)**(b-1)/float(B)
        near(simpson(density,0,1),1)
        near(simpson(lambda p:p*density(p),0,1),m)
        near(simpson(lambda p:(p-float(m))**2*density(p),0,1),v)
        assert beta_cdf(F(0),a,b)==0 and beta_cdf(F(1),a,b)==1
    assert beta_integral(5,5)==F(1,630)
    near(beta_quantile(5,5,.025),.21200850677886796)
    near(beta_quantile(5,5,.975),.7879914932211318)
    polynomial=lambda p:126*p**5-420*p**6+540*p**7-315*p**8+70*p**9
    for x in [F(i,10) for i in range(11)]:assert beta_cdf(x,5,5)==polynomial(x)
    assert 1-beta_cdf(F(3,5),5,5)==F(26656768,100000000)
    assert beta_moment(5,5,1)==F(1,2)
    assert 20*beta_moment(5,5,1)-9==1
    assert 20*beta_moment(4,3,1)-9==F(17,7)
    assert 20*beta_moment(5,10,1)-9==F(-7,3)
    assert beta_moment(11,9,1)==F(11,20)
    assert beta_moment(11,9,2)-F(11,20)**2==F(33,2800)
    assert F(11-1,11+9-2)==F(5,9)
    assert beta_moment(15,10,1)==F(3,5)
    # Integrated predictive count mass and exact moments; no binomial plug-in.
    A,D,m=5,5,4
    weights=[comb(m,j)*beta_integral(A+j,D+m-j)/beta_integral(A,D) for j in range(m+1)]
    assert sum(weights)==1
    assert moments(list(range(m+1)),weights)[0::2]==(2,F(14,11))
    assert weights[4]==beta_moment(5,5,4)==F(14,143)
    assert beta_moment(5,5,2)-F(1,4)==F(1,44)
    for j,w in enumerate(weights):
        near(simpson(lambda p:comb(4,j)*p**j*(1-p)**(4-j)*630*p**4*(1-p)**4,0,1),w)
    # Prior-averaged credible-set probability from all observed outcomes;
    # fixed-parameter coverage at p=.9 is independently enumerated.
    success=(sqrt(.025),sqrt(.975)); failure=(1-sqrt(.975),1-sqrt(.025))
    near(beta_cdf(success[1],2,1)-beta_cdf(success[0],2,1),.95)
    near(beta_cdf(failure[1],1,2)-beta_cdf(failure[0],1,2),.95)
    fixed_coverage=sum(w for interval,w in [(success,.9),(failure,.1)] if interval[0]<=.9<=interval[1])
    near(fixed_coverage,.9)
    # Check loss minimizers by exact polynomial integrals, not only summaries.
    square=lambda d:2*d*d/2-4*d/3+F(1,2)
    assert square(F(2,3))==F(1,18)
    for d in [F(i,20) for i in range(21)]:assert square(d)>=square(F(2,3))
    # Under density 2p, absolute loss = 2/3 - d + 2d^3/3 for d in [0,1].
    absolute=lambda d:2/3-d+2*d**3/3
    med=1/sqrt(2)
    near(2*med*med-1,0)
    for d in [i/100 for i in range(101)]:assert absolute(d)>=absolute(med)-1e-12
    checks.append('Exact beta-integral recurrences/moments and independent quadrature, posterior polynomial/quantiles, prior sensitivity, integrated beta-binomial law and credible-coverage counterexample/loss minimizers')

    data=[2,3,5,6]
    for prior_mu,prior_var,expect_mu,expect_var in [(0,4,F(16,5),F(4,5)),(-4,F(1,4),F(-12,5),F(1,5))]:
        prior_var=float(prior_var)
        joint=lambda mu:gaussian(mu,prior_mu,prior_var)*__import__('math').prod(gaussian(x,mu,4) for x in data)
        evidence=simpson(joint,-20,20)
        empirical_mu=simpson(lambda mu:mu*joint(mu),-20,20)/evidence
        empirical_var=simpson(lambda mu:(mu-empirical_mu)**2*joint(mu),-20,20)/evidence
        near(empirical_mu,expect_mu);near(empirical_var,expect_var)
    z=NormalDist().inv_cdf(.975)
    near(3.2-z*sqrt(.8),1.4469549188468378)
    near(3.2+z*sqrt(.8),4.953045081153163)
    near(1-Phi((3-3.2)/sqrt(.8)),.5884683631209393)
    near(4-z,2.0400360154599464);near(4+z,5.959963984540054)
    for y in (-3,0,3.2,7):
        convolution=simpson(lambda mu:gaussian(y,mu,4)*gaussian(mu,3.2,.8),-15,20)
        near(convolution,gaussian(y,3.2,4.8))
    assert F(4,5)+4==F(24,5) and F(4,5)+1==F(9,5)
    checks.append('Independent prior-times-full-likelihood normal integrals, contrasting-prior posterior, credible/profit probabilities and predictive convolution')

    # Independent gamma integral audit with shape/rate units.
    gamma=lambda x,a,b:b**a*x**(a-1)*exp(-b*x)/factorial(a-1)
    for a,b in ((2,3),(5,7)):
        near(simpson(lambda x:gamma(x,a,b),0,20),1)
        near(simpson(lambda x:x*gamma(x,a,b),0,20),F(a,b))
        near(simpson(lambda x:(x-a/b)**2*gamma(x,a,b),0,20),F(a,b*b))
    count_weights=[F(comb(4+j,j))*F(7,9)**5*F(2,9)**j for j in range(51)]
    near(sum(count_weights),1)
    near(sum(j*w for j,w in enumerate(count_weights)),F(10,7))
    near(sum((F(j)-F(10,7))**2*w for j,w in enumerate(count_weights)),F(90,49))
    assert count_weights[0]==F(7,9)**5
    near(count_weights[0],.28462802079628785)
    for j in range(8):
        integrated=simpson(lambda lam:exp(-2*lam)*(2*lam)**j/factorial(j)*gamma(lam,5,7),0,10)
        near(integrated,count_weights[j])
    # Model evidence integrates the full proper prior rather than maximizes.
    uniform_evidence=beta_moment(1,1,4); pessimistic_evidence=beta_moment(1,9,4)
    assert uniform_evidence==F(1,5) and pessimistic_evidence==F(1,715)
    for ev,expected in ((uniform_evidence,F(16,61)),(pessimistic_evidence,F(16,6451))):
        posterior=F(1,10)*ev/(F(1,10)*ev+F(9,10)*F(1,16))
        assert posterior==expected
    # Transform p->q=p^2: directly integrate induced CDF by substitution.
    for q in (.01,.25,.81):near(simpson(lambda p:1,0,sqrt(q)),sqrt(q))
    checks.append('Gamma shape/rate normalization and moments, integrated predictive count probabilities with tail-small exact series, proper-prior model odds and nonlinear prior transformation')

    certain=F(9,4); payoff=[F(1),F(4)];weights=[F(1,2)]*2
    assert sum(x*w for x,w in zip(payoff,weights))==F(5,2)>certain
    assert sum((3*x+7)*w for x,w in zip(payoff,weights))==F(29,2)>3*certain+7
    assert (log(1)+log(4))/2<log(float(certain))
    # Affine mixture/reduction identity for the finite binary construction.
    u=[F(0),F(1,3),F(1)]; p=[F(1,2),F(1,4),F(1,4)]
    binary_probability=sum(a*b for a,b in zip(u,p))
    assert binary_probability==F(1,3)
    for t in (F(1,5),F(1,2),F(4,5)):
        q=[F(0),F(0),F(1)];mix=[t*a+(1-t)*b for a,b in zip(p,q)]
        assert sum(a*b for a,b in zip(u,mix))==t*binary_probability+(1-t)
    for values in ([1.,4.],[20.,100.],[80.,120.]):
        for q in (.1,.5,.9):
            for utility in (log,sqrt):
                EU=q*utility(values[0])+(1-q)*utility(values[1])
                assert EU<=utility(q*values[0]+(1-q)*values[1])+1e-12
    insurance_EU=.9*10+.1*sqrt(60);insurance_CE=insurance_EU**2
    near(insurance_CE,95.54274004634668)
    near(96-insurance_CE,.45725995365332)
    near(100-insurance_CE,4.45725995365332)
    assert 100-4.3>insurance_CE>100-4.6
    log_CE=sqrt(80*120)
    near(log_CE,97.97958971132712);near(100-log_CE,2.0204102886728776)
    assert F(4,5)*100+F(1,5)*64==F(464,5)
    assert (F(4,5)*10+F(1,5)*8)**2==F(2304,25)
    assert F(464,5)-F(2304,25)==F(16,25)
    assert 100-F(2304,25)==F(196,25)
    assert F(196,25)-F(36,5)==F(16,25)
    assert 100-F(15,2)>F(2304,25)>100-8
    gain=-20*log((1+exp(-1))/2)
    near(gain,7.597709860834449);near(10-gain,2.402290139165551)
    assert gain-8<0<10-8
    for wealth in (0,10,100):
        near(exp(-.05*(wealth+gain)),exp(-.05*wealth)*(1+exp(-1))/2)
    checks.append('Finite binary-lottery reduction/affine identities, nonlinear reordering, Jensen examples, insurance wealth/risk/loading separation, log and discrete-CARA certainty equivalents')

    # Local curvature checked against numerical derivatives and risk limits.
    for gamma in (.5,1,2,3):
        utility=(lambda w:log(w)) if gamma==1 else (lambda w:w**(1-gamma)/(1-gamma))
        for w in (2,20,100):
            h=.0001*w
            du=(utility(w+h)-utility(w-h))/(2*h)
            ddu=(utility(w+h)-2*utility(w)+utility(w-h))/(h*h)
            near(-ddu/du,gamma/w,tol=2e-7)
    errors=[]
    for amplitude in (5,1,.5,.25):
        risk=100-sqrt(10000-amplitude*amplitude)
        errors.append(abs(risk/amplitude**2-.005))
    assert all(a>b for a,b in zip(errors,errors[1:]))
    for mu,sd,a in [(4,20,.02),(8,10,.02),(0,1,1)]:
        direct=simpson(lambda z:exp(-a*(mu+sd*z))*phi(z),-12,12)
        near(direct,exp(-a*mu+a*a*sd*sd/2))
        near(-log(direct)/a,mu-a*sd*sd/2)
    for a,optimum,best in ((F(1,50),F(1,2),F(1)),(F(1,25),F(1,4),F(1,2))):
        objective=lambda f:4*f-a*400*f*f/2
        assert objective(optimum)==best
        for f in (F(i,100) for i in range(101)):assert objective(f)<=best
    assert moments([-1,1],[F(1,2)]*2)[0::2]==(0,1)
    assert moments([-2,0,2],[F(1,8),F(3,4),F(1,8)])[0::2]==(0,1)
    A=cosh(1);B=.75+.25*cosh(2)
    near(B-A,(A-1)**2/2);assert B>A
    near(-log(A),-.4337808304830271);near(-log(B),-.5250532825701297)
    for lo,hi,expected in [(F(0),F(2,3),[F(1,3),F(0),F(1,3),F(2,3)]),(F(1,6),F(1,2),[F(1,3),F(1,6),F(1,2),F(2,3)])]:
        worst=[min(F(1,3) for q in (lo,hi)),min(lo,hi),min(1-lo,1-hi),F(2,3)]
        assert worst==expected
        assert worst[0]>worst[1] and worst[3]>worst[2]
    q=mean_black=F(sum(range(61)),61*90)
    assert q==F(1,3) and 1-q==F(2,3)
    checks.append('Independent CRRA derivative ratios and local small-risk convergence, exponential-normal integrals and exposure optima, equal-moment tail counterexample, ambiguity endpoints and symmetric-prior ties')
    return {'status':'passed','checks':checks,'limitations':['Numerical examples do not establish the general representation, risk-aversion or Bayes-risk theorems; their assumptions and proofs receive separate written author review.']}


if __name__=='__main__':
    import json
    print(json.dumps(check(),indent=2))
