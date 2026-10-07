"""Independent exact-state and quadrature checks for probability Chapters 3–4.

Numerical checks complement the written proof audit; finite truncations do not
prove moment existence, convergence, independence or general theorem claims.
"""
from fractions import Fraction as F
from itertools import combinations, product, permutations
from collections import Counter
from math import exp, erf, sqrt, pi, log, comb, isclose


def near(a, b, tol=1e-10):
    assert isclose(float(a), float(b), rel_tol=tol, abs_tol=tol), (a, b)


def simpson(f, a, b, n=12000):
    assert n > 0 and n % 2 == 0
    h = (b-a)/n
    return h/3*(f(a)+f(b)+sum((4 if k % 2 else 2)*f(a+k*h)
                              for k in range(1, n)))


def moments(values, weights):
    assert len(values) == len(weights) and all(w >= 0 for w in weights)
    assert sum(weights) == 1
    mean = sum(w*x for x, w in zip(values, weights))
    second = sum(w*x*x for x, w in zip(values, weights))
    centered = sum(w*(x-mean)**2 for x, w in zip(values, weights))
    assert centered == second-mean**2
    return mean, second, centered


def covariance(x, y, weights):
    mx = moments(x, weights)[0]; my = moments(y, weights)[0]
    direct = sum(w*(a-mx)*(b-my) for a, b, w in zip(x, y, weights))
    assert direct == sum(w*a*b for a, b, w in zip(x, y, weights))-mx*my
    return direct


def check():
    checks = []
    # Enumerate labeled mechanisms, rather than use the manuscript's PMF formula.
    files = [1]*3+[0]*5
    counts = Counter(sum(pair) for pair in combinations(files, 2))
    assert counts == {0: 10, 1: 15, 2: 3}
    assert sum(counts.values()) == 28
    assert F(counts[1]+counts[2], 28) == F(9, 14)
    replacement = Counter(a+b for a, b in product(files, repeat=2))
    assert replacement == {0: 25, 1: 30, 2: 9}
    for n in range(7):
        for p in (F(0), F(3, 25), F(3, 8), F(1)):
            count_weights = [F(0)]*(n+1)
            for bits in product((0, 1), repeat=n):
                weight = F(1)
                for bit in bits: weight *= p if bit else 1-p
                count_weights[sum(bits)] += weight
            assert sum(count_weights) == 1
            for k in range(n+1):
                assert count_weights[k] == comb(n, k)*p**k*(1-p)**(n-k)
            if n == 4 and p == F(3, 25):
                assert count_weights[1] == F(127776, 390625)
                assert 1-count_weights[0] == F(156369, 390625)
    checks.append('Exhaustive labeled without/with-replacement and independent Bernoulli count laws')

    # CDF jumps and endpoint conventions in exercise 1.
    x = [-1, 0, 2]; p = [F(1, 5), F(1, 2), F(3, 10)]
    cdf = lambda t: sum(w for value, w in zip(x, p) if value <= t)
    assert [cdf(t) for t in (-2, -1, F(-1, 2), 0, 1, 2, 3)] == [0,F(1,5),F(1,5),F(7,10),F(7,10),1,1]
    assert sum(w for value, w in zip(x, p) if -1 < value <= 2) == F(4,5)
    assert sum(w for value, w in zip(x, p) if value < 0) == F(1,5)
    assert cdf(0)-cdf(F(-1,100)) == F(1,2)

    # Poisson normalization: a finite sum with a positive omitted-tail bound.
    lam = 1.5; mass = [exp(-lam)]
    for k in range(50): mass.append(mass[-1]*lam/(k+1))
    first_omitted = mass[-1]*lam/51
    tail_bound = first_omitted/(1-lam/52)  # later consecutive ratios <= lam/52
    assert tail_bound < 1e-55
    near(sum(mass), 1, 1e-14)
    near(mass[0], .22313016014842982)
    near(mass[2], .25102143016698353)
    near(sum(mass[2:]), .44217459962892547)
    near(sum(k*q for k,q in enumerate(mass)), lam)
    near(sum((k-lam)**2*q for k,q in enumerate(mass)), lam)
    for k in range(5):
        errors = []
        for n in (100, 1000, 10000):
            prob = comb(n,k)*(lam/n)**k*(1-lam/n)**(n-k)
            errors.append(abs(prob-mass[k]))
        assert errors[2] < errors[1] < errors[0]
    checks.append('Discrete CDF endpoints and Poisson sums, moments, tail certificate and rare-event comparison')

    # PDF integrals checked through quadrature, not only CDF substitution.
    near(simpson(lambda t: t/2,0,2),1)
    near(simpson(lambda t: t/2,.5,1.5),.5)
    near(simpson(lambda t: t/2,0,sqrt(2)),.5)
    for r in (.25, .4):
        pdf = lambda t: r*exp(-r*t)
        near(simpson(pdf,0,160),1,1e-9)
        near(simpson(lambda t: t*pdf(t),0,160),1/r,1e-8)
        near(simpson(lambda t: t*t*pdf(t),0,160),2/r**2,1e-8)
    near(simpson(lambda t: .25*exp(-.25*t),0,4),.6321205588285577)
    near(simpson(lambda t: .25*exp(-.25*t),2,6),.38340049956420363)
    near(exp(-.25*10)/exp(-.25*6),.36787944117144233)
    near(4*log(2),2.772588722239781)
    near(1-exp(-.25*(4*log(2))),.5)
    near(exp(-.4*3),.3011942119122021)
    near(exp(-.4*5)/exp(-.4*2),exp(-1.2))
    near(log(10)/.4,5.756462732485114)
    near(1-exp(-.4*(log(10)/.4)),.9)
    assert F(7,10) != F(5,8)

    phi = lambda z: exp(-z*z/2)/sqrt(2*pi)
    # Standard Gaussian tails beyond 8 have probability <= 2 phi(8)/8.
    assert 2*phi(8)/8 < 1.3e-15
    near(simpson(phi,-8,8),1,1e-12)
    near(simpson(lambda z: z*phi(z),-8,8),0,1e-12)
    near(simpson(lambda z: z*z*phi(z),-8,8),1,1e-11)
    assert 2*(8+1/8)*phi(8) < 9e-14  # second-moment omitted-tail bound
    near(simpson(phi,-1,1),.6826894921370859)
    near(simpson(phi,2,8),.02275013194817921)
    for z in (-2,-1,0,1,2):
        near(simpson(phi,-8,z),(1+erf(z/sqrt(2)))/2)
    for radius in (1,2,3,4):
        j = simpson(lambda z: exp(-z*z/2),-radius,radius)
        assert 2*pi*(1-exp(-radius**2/2)) <= j*j <= 2*pi*(1-exp(-radius**2))
    checks.append('Independent quadrature for density normalization, exponential probabilities/moments and Gaussian intervals/moments')

    mixed_cdf = lambda t: F(0) if t < 0 else (F(1,5) if t < 1 else (F(1,5)+F(4,5)*(t-1) if t <= 2 else F(1)))
    assert mixed_cdf(F(3,2))-mixed_cdf(1) == F(2,5)
    assert mixed_cdf(0) == mixed_cdf(1) == F(1,5)
    assert 1-mixed_cdf(F(99,100)) == F(4,5)
    assert mixed_cdf(0)-mixed_cdf(F(-1,100)) == F(1,5)
    near(simpson(lambda t: 1/t**2,1,10),.9,1e-9)
    near(simpson(lambda t: 1/t,1,10),log(10),1e-9)
    assert 1-1/100 == .99
    # Integrate Pareto moments using u = 1/x to compare distinct integrands.
    # For alpha=3/2, norm and mean become 1.5 sqrt(u) and 1.5/sqrt(u).
    # A further u=v^2 substitution removes the endpoint singularity.
    near(simpson(lambda v: 3*v*v,0,1),1)
    near(simpson(lambda v: 3,0,1),3)
    # Truncated alpha=3/2 second moment is 3(sqrt(R)-1), unbounded analytically.
    for cutoff in (4,9,16):
        near(simpson(lambda t: 1.5/sqrt(t),1,cutoff),3*(sqrt(cutoff)-1),1e-9)
    near(simpson(lambda u: 3*u*u,0,1),1)
    near(simpson(lambda u: 3*u,0,1),1.5)
    near(simpson(lambda u: 3,0,1),3)
    # Cauchy first positive part: verify logarithmic finite-cutoff integral.
    for cutoff in (2,5,10):
        near(simpson(lambda t: t/(pi*(1+t*t)),0,cutoff),log(1+cutoff**2)/(2*pi))
    checks.append('Mixed-law atoms, quantiles and transformed heavy-tail/Cauchy finite-cutoff integrals; divergence reviewed analytically')

    p = [F(1,5),F(1,2),F(3,10)]; x = [-100,40,160]
    assert moments(x,p) == (48,10480,8176)
    assert moments([2*t-30 for t in x],p) == (66,37060,32704)
    assert sum(w*(t-50)**2 for t,w in zip(x,p)) == 8180
    near(sqrt(8176),90.42123644365851)
    p = [F(1,4)]*4; a = [-20,0,20,40]; b = [40,20,0,20]
    assert moments(a,p) == (10,600,500)
    assert moments(b,p) == (20,600,200)
    assert covariance(a,b,p) == -200
    near(-200/sqrt(500*200),-2/sqrt(10))
    half = [F(1,2)*(x+y) for x,y in zip(a,b)]
    assert moments(half,p) == (15,300,75)
    optimum = [F(4,11)*x+F(7,11)*y for x,y in zip(a,b)]
    assert moments(optimum,p)[0] == F(180,11)
    assert moments(optimum,p)[2] == F(600,11)
    for numerator in range(-25,76):
        w = F(numerator,50)
        v = moments([w*x+(1-w)*y for x,y in zip(a,b)],p)[2]
        assert v == 1100*w*w-800*w+200
        assert v-F(600,11) == 1100*(w-F(4,11))**2
    checks.append('Exact centered versus raw payoff moments, affine exposures, squared loss and global portfolio variance certificate')

    assert moments([-2,1,4],[F(1,4),F(1,2),F(1,4)]) == (1,F(11,2),F(9,2))
    assert moments([-1,8,17],[F(1,4),F(1,2),F(1,4)]) == (8,F(209,2),F(81,2))
    near(simpson(lambda t: t*t/2,0,2),F(4,3))
    near(simpson(lambda t: t**3/2,0,2),2)
    near(simpson(lambda t: (t-F(4,3))**2*t/2,0,2),F(2,9))
    near(simpson(lambda t: (2*t-1)*t/2,0,2),F(5,3))
    near(simpson(lambda t: (2*t-1-F(5,3))**2*t/2,0,2),F(8,9))
    files = [1]*5+[0]*15
    count = [sum(c) for c in combinations(files,4)]
    assert len(count) == 4845
    weights = [F(1,len(count))]*len(count)
    assert moments(count,weights)[0::2] == (1,F(12,19))
    ordered = list(permutations(range(20),2))
    joint_flags = F(sum(files[i]*files[j] for i,j in ordered),len(ordered))
    assert joint_flags-F(1,4)**2 == F(-3,304)
    checks.append('Continuous polynomial moments and exhaustive 4,845 finite-population samples with position covariance')

    x=[0,0,1,1]; y=[0,2,0,2]; p=[F(2,5),F(1,10),F(1,5),F(3,10)]
    assert moments(x,p) == (F(1,2),F(1,2),F(1,4))
    assert moments(y,p) == (F(4,5),F(8,5),F(24,25))
    assert covariance(x,y,p) == F(1,5)
    assert sum(w*a*b for a,b,w in zip(x,y,p)) == F(3,5)
    near(F(1,5)/sqrt(F(1,4)*F(24,25)),1/sqrt(6))
    assert moments([a+b for a,b in zip(x,y)],p) == (F(13,10),F(33,10),F(161,100))
    x=[-1,0,1]; y=[1,0,1]; p=[F(1,3)]*3
    assert moments(x,p)[0::2] == (0,F(2,3))
    assert moments(y,p)[0::2] == (F(2,3),F(2,9))
    assert covariance(x,y,p) == 0 and F(1,3) != F(1,3)**2
    x=[-70,-30,15,35]; p=[F(1,10),F(1,10),F(2,5),F(2,5)]
    assert moments(x,p)[0::2] == (10,1060)
    assert moments(x[:2],[F(1,2)]*2)[0::2] == (-50,400)
    assert moments(x[2:],[F(1,2)]*2)[0::2] == (25,100)
    assert F(1,5)*400+F(4,5)*100 == 160
    assert F(1,5)*(-50-10)**2+F(4,5)*(25-10)**2 == 900
    checks.append('Exact joint marginal/cross-moments, dependent-uncorrelated counterexample and partition variance decomposition')

    assert 9+2*1*(-2)*8+(-2)**2*4 == -7
    assert 8**2 > 9*4 and 9*4-3**2 == 27
    w = F(1,7)
    variance = lambda w: 9*w*w+4*(1-w)**2+6*w*(1-w)
    assert variance(w) == F(27,7) and variance(F(1,2)) == F(19,4)
    for k in range(101):
        candidate=F(k,100)
        assert variance(candidate)-variance(w) == 7*(candidate-w)**2
    checks.append('Inconsistent covariance rejection and repaired constrained minimum-variance certificate')
    return {'status':'passed','chapters':['v03-c03','v03-c04'], 'checks':checks,
            'limitations':['Finite numerical checks do not prove the stated general identities or infinite-tail divergence; written derivations reviewed separately.']}


if __name__ == '__main__':
    import json
    print(json.dumps(check(),indent=2))
