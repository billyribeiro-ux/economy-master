"""Independent exact-state and quadrature audit of v03-c07/c08.

Proofs/assumption claims have a separate editorial review. Finite coverage grids
are diagnostics, not a proof of uniform coverage; the manuscript proves it.
"""
from fractions import Fraction as F
from itertools import combinations, product
from math import sqrt, exp, log, pi, atan, ceil
from statistics import NormalDist
from check_v03_moments import moments, covariance, near, simpson
from check_v03_conditioning_limits import binomial, Phi, phi


def mean(xs):
    return sum(xs, F(0))/len(xs)


def sample_variance(xs):
    mu = mean(xs)
    return sum((x-mu)**2 for x in xs)/(len(xs)-1)


def root(f, target, increasing=True):
    lo, hi = 0., 1.
    for _ in range(70):
        mid = (lo+hi)/2
        if (f(mid) < target) == increasing:
            lo = mid
        else:
            hi = mid
    return (lo+hi)/2


def binomial_float(n, p):
    # Use direct coefficient sums, independently of the exact fraction law.
    from math import comb
    return [comb(n,k)*p**k*(1-p)**(n-k) for k in range(n+1)]


def exact_interval(n, k, alpha=.05):
    lower = root(lambda p:sum(binomial_float(n,p)[k:]),alpha/2) if k else 0.
    upper = root(lambda p:sum(binomial_float(n,p)[:k+1]),alpha/2,False) if k<n else 1.
    return lower,upper


def holm(values, alpha):
    ordered=sorted(enumerate(values),key=lambda item:item[1])
    rejected=[]
    for rank,(index,p) in enumerate(ordered):
        if p>alpha/(len(values)-rank):
            break
        rejected.append(index)
    return rejected


def check():
    checks=[]
    # Exhaustive finite-population sampling: true dispersion and unbiased
    # sample-variance/estimated-mean-variance, including all feasible sizes.
    for population in ([0,2,4,6,8,10],[0,2,6,8]):
        N=len(population); mu=mean(population); S2=sample_variance(population)
        for n in range(2,N+1):
            samples=list(combinations(population,n))
            weights=[F(1,len(samples))]*len(samples)
            sample_means=[mean(s) for s in samples]
            assert moments(sample_means,weights)[0]==mu
            true_var=moments(sample_means,weights)[2]
            assert true_var==(1-F(n,N))*S2/n
            assert mean([sample_variance(s) for s in samples])==S2
            assert mean([(1-F(n,N))*sample_variance(s)/n for s in samples])==true_var
        draws=list(product(range(N),repeat=2))
        draws=[(a,b) for a,b in draws if a!=b]
        cov=covariance([population[a] for a,b in draws],[population[b] for a,b in draws],[F(1,len(draws))]*len(draws))
        assert cov==-S2/N
    assert moments([mean(s) for s in combinations([0,2,4,6,8,10],2)],[F(1,15)]*15)[2]==F(14,3)
    strat=[F(a+b,2) for a,b in product([0,2,4],[6,8,10])]
    assert moments(strat,[F(1,9)]*9)[0::2]==(5,F(4,3))
    assert sample_variance([2,8])==18
    near(sqrt((1-2/6)*18/2),sqrt(6))
    assert [mean(s) for s in combinations([0,2,6,8],2)]==[1,3,4,4,5,7]
    near(sqrt(F(9,2)),3/sqrt(2))
    values=[10,20,30]; inclusion=[F(1,2),F(1,3),F(1,6)]
    totals=[y/p for y,p in zip(values,inclusion)]
    assert totals==[20,60,180]
    assert moments(totals,inclusion)==(60,6800,3200)
    assert moments(values,inclusion)[0]==F(50,3)
    assert moments([v/3 for v in totals],inclusion)[0::2]==(20,F(3200,9))
    # Full covariance expansion using mutually exclusive indicators.
    variance=F(0)
    for i,j in product(range(3),repeat=2):
        joint=inclusion[i] if i==j else 0
        variance+=(joint-inclusion[i]*inclusion[j])*values[i]*values[j]/(inclusion[i]*inclusion[j])
    assert variance==3200
    assert F(4,5)*12+F(1,5)*35==F(83,5)
    assert F(16,25)*F(9,10)*16/8+F(1,25)*F(4,5)*36/4==F(36,25)
    checks.append('Exhaustive finite-population and stratified designs, negative covariance, unbiased variance estimates, unequal-probability totals and joint-inclusion variance')

    for n in (1,2,10,100):
        assert F(9,n)+F(4,n*n)==F(9*n+4,n*n)
    # Exact two-point laws test the shrinkage MSE identity directly.
    for mu,ref,a in product((F(-1),F(3)),(F(0),F(5)),(F(0),F(1,3),F(1))):
        estimates=[a*(mu+noise)+(1-a)*ref for noise in (-3,3)]
        direct=mean([(t-mu)**2 for t in estimates])
        assert direct==a*a*9+(1-a)**2*(ref-mu)**2
    near(sqrt(F(3,20)*F(17,20)/20),.07984359711335656)
    # Numeric likelihood grid does not stand in for the manuscript's global
    # concavity/boundary proof; it independently catches parameter mistakes.
    likelihood=lambda p:p**3*(1-p)**17
    assert max(range(1001),key=lambda j:likelihood(j/1000))==150
    for p in (0,.01,.15,.7,1):
        assert (1-p)**20<=1
    for completed,expected in ((4,F(1,3)),(2,F(1,6))):
        mle=completed/12
        near(mle,expected)
        ell=lambda r:completed*log(r)-12*r
        for r in (.01,.05,.1,.2,.5,1,3):
            assert ell(mle)>=ell(r)-1e-12
    near(simpson(lambda m:m*4*m**3,0,1),F(4,5))
    near(.8**4,.4096)
    for data,expected_mu,empirical,sv,bootvar in [([2,4,4,10],5,9,12,F(9,4)),([0,3,6],3,6,9,2)]:
        n=len(data); index_draws=list(product(range(n),repeat=n))
        means=[mean([data[i] for i in ids]) for ids in index_draws]
        weights=[F(1,n**n)]*len(means)
        assert moments(means,weights)[0::2]==(expected_mu,bootvar)
        assert sample_variance(data)==sv
        assert sum((F(x)-expected_mu)**2 for x in data)/n==empirical
        assert F(n-1,n*n)*sv==bootvar
        assert all(mean([data[i] for i in ids])==expected_mu for ids in combinations(range(n),n))
    index_draws=list(product(range(4),repeat=4))
    max_atom=F(sum(3 in ids for ids in index_draws),len(index_draws))
    assert max_atom==F(175,256)==1-F(3,4)**4
    for n in (10,100,1000):
        true_gap_cdf=1-(1-1/n)**n
        atom=true_gap_cdf
        assert atom>.6  # persistent empirical-bootstrap atom, not Monte Carlo error
    checks.append('Exact estimator MSE/shrinkage comparisons, likelihood grid and censored exposures, uniform-maximum moment, exhaustive empirical resampling and endpoint atom')

    normal=NormalDist(); z=normal.inv_cdf(.975); z1=normal.inv_cdf(.95)
    near(z,1.9599639845400534)
    near(simpson(phi,-z,z),.95)
    near(simpson(phi,-8,z1),.95)
    near(2*(1-Phi(2.4)),.01639507184919231)
    near(1-Phi(-1.6),.945200708300442)
    near(1.2-z*.5,.22001800772997326)
    near(1.2+z*.5,2.1799819922700268)
    near(1.2-z1*.5,.3775731865242643)
    near(2*(1-Phi(1.6)),.10959858339911598)
    near(1-Phi(1.6),.05479929169955799)
    near(.8-z*.5,-.17998199227002665)
    near(.8+z*.5,1.7799819922700268)
    # Explicit orthonormal four-point rotation: first coordinate is the mean
    # direction and the other squared coordinates are exactly residual norm.
    Q=[[F(s,2) for s in row] for row in [[1,1,1,1],[1,1,-1,-1],[1,-1,1,-1],[1,-1,-1,1]]]
    for i,j in product(range(4),repeat=2):
        assert sum(a*b for a,b in zip(Q[i],Q[j]))==int(i==j)
    for data in ([2,4,4,10],[-2,0,1,6],[1,1,1,1]):
        rotated=[sum(a*x for a,x in zip(row,data)) for row in Q]
        assert rotated[0]==2*mean(data)
        assert sum(x*x for x in rotated[1:])==3*sample_variance(data)
    # For t_3 the density is elementary; quadrature independently verifies
    # the supplied quantile. Its CDF also follows by t=sqrt(3)tan(angle).
    density3=lambda t:2/(sqrt(3)*pi)*(1+t*t/3)**-2
    t3=3.182446305284263
    near(simpson(density3,-t3,t3),.95)
    u=t3/sqrt(3)
    near(.5+(atan(u)+u/(1+u*u))/pi,.975)
    near(t3*sqrt(3),5.512158693112197)
    assert 5/sqrt(3)<t3
    checks.append('Independent normal coverage integration, effect/cost test arithmetic, orthonormal residual identity and t3 critical-value quadrature')

    w12=binomial(12,F(1,2)); w10=binomial(10,F(1,2))
    assert sum(w12[10:])==F(79,4096) and sum(w12[9:])==F(299,4096)
    assert sum(binomial(12,F(3,4))[10:])==F(6554439,16777216)
    assert sum(w10[9:])==F(11,1024) and sum(w10[8:])==F(56,1024)
    assert sum(binomial(10,F(4,5))[9:])==F(3670016,9765625)
    near(sum(binomial(10,F(4,5))[9:]),.3758096384)
    # Exhaustive tail calibration for every attainable p-value and many
    # composite-null laws, including a genuinely discrete 5% threshold.
    for n in (10,12,20):
        boundary=binomial(n,F(1,2))
        pvalues=[sum(boundary[k:]) for k in range(n+1)]
        for p in (F(0),F(1,10),F(1,4),F(1,2)):
            weights=binomial(n,p)
            for u in pvalues+[F(1,20),F(1,10)]:
                assert sum(w for w,pv in zip(weights,pvalues) if pv<=u)<=u
    L,U=exact_interval(12,10)
    near(L,.5158622513140327);near(U,.9791374745399075)
    near(root(lambda p:sum(binomial_float(12,p)[10:]),.05),.5618945648846887)
    near(1-.05**(1/20),.13910834066826516)
    near(1-.025**(1/20),.1684334709830853)
    near(z*z/(20+z*z),.16112515805281927)
    for n in (10,12,20):
        intervals=[exact_interval(n,k) for k in range(n+1)]
        for step in range(1001):
            p=step/1000
            weights=binomial_float(n,p)
            coverage=sum(w for w,(lo,hi) in zip(weights,intervals) if lo-1e-14<=p<=hi+1e-14)
            assert coverage>=.95-1e-12
            near(sum(weights),1)
    assert float(binomial(20,F(1,20))[0])>.35  # Wald [0,0] misses true p=.05 on this event
    # Check quadratic inversion numerically over all possible counts.
    for k in range(21):
        phat=k/20; den=1+z*z/20
        center=(phat+z*z/40)/den
        half=z*sqrt(phat*(1-phat)/20+z*z/1600)/den
        lo,hi=center-half,center+half
        assert lo>=-1e-14 and hi<=1+1e-14
        for p in (lo,hi):
            near((phat-p)**2,z*z*p*(1-p)/20)
    checks.append('Exact binomial sizes/powers and superuniform/composite-null tail calibration, root inversion, finite coverage grids and Wilson quadratic endpoints')

    nbound=((z1+normal.inv_cdf(.8))*4)**2
    near(nbound,98.92091571231622); assert ceil(nbound)==99
    assert 1-Phi(z1-sqrt(98)/4)<.8<1-Phi(z1-sqrt(99)/4)
    near(1-Phi(z-2)+Phi(-z-2),.5160052739761751)
    near(simpson(phi,z-2,9)+simpson(phi,-9,-z-2),.5160052739761751)
    family=[F(4,1000),F(11,1000),F(16,1000),F(32,1000),F(1,5)]
    assert [i for i,p in enumerate(family) if p<=F(1,20)]==[0,1,2,3]
    assert [i for i,p in enumerate(family) if p<=F(1,100)]==[0]
    assert holm(family,F(1,20))==[0,1,2]
    near(1-.95**5,.2262190625);near(1-.95**2,.0975)
    # Enumerate independent valid discrete p-values for every arrangement
    # of true/false hypotheses. False-null values need not be calibrated.
    grid=[F(i,12) for i in range(1,13)]; alpha=F(1,4)
    for true_flags in product((False,True),repeat=3):
        choices=[grid if flag else [F(0),F(1,8),F(1)] for flag in true_flags]
        configurations=list(product(*choices))
        errors=sum(any(true_flags[i] for i in holm(vals,alpha)) for vals in configurations)
        assert F(errors,len(configurations))<=alpha
    # Perfectly dependent true p-values: still valid marginally.
    assert F(sum(bool(holm([p,p,p],alpha)) for p in grid),len(grid))<=alpha
    near(1-Phi(3),.0013498980316301035)
    near(Phi(-2),.02275013194817921)
    near(.1-z1*.2,-.2289707253902943)
    near(.1+z1*.2,.42897072539029435)
    near(2*(1-Phi(.5)),.6170750774519738)
    # Exact normal probability of equivalence rejection at the two boundary
    # null means (where a true component limits the size).
    low=-.5+z1*.2; high=.5-z1*.2
    for mu in (-1,-.5,.5,1):
        chance=max(0.,Phi((high-mu)/.2)-Phi((low-mu)/.2))
        assert chance<=.05+1e-12
    assert low<.1<high
    checks.append('Alternative-law power integration and integer sample size, Holm family decisions and exhaustive mixed/dependent-null states, equivalence statistics/interval/boundary size')
    return {'status':'passed','checks':checks,'coverage_grid_points':3003,'limitations':['Finite grids and numeric integrations do not establish asymptotic, general coverage or strong error-control theorems; their manuscript proofs receive separate author review.']}


if __name__=='__main__':
    import json
    print(json.dumps(check(),indent=2))
