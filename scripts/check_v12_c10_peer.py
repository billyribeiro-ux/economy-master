"""Independent, bounded C10 peer oracle; standard library and read-only files.

The numerical reconstruction does not import or call the author checker.  Final
check() reads the canonical four author files and the two peer files only.
Successful import/API/CLI are quiet; proof conclusions remain separately read.
"""
import ast
from fractions import Fraction as Q
from html.parser import HTMLParser
from itertools import product
import hashlib
import json
import math
from pathlib import Path

AUTHOR = ('content/chapters/v12-c10.html', 'scripts/check_v12_c10.py',
          'content/reviews/v12-c10-sources.json', 'content/reviews/v12-c10-author.json')
SELF = 'scripts/check_v12_c10_peer.py'
REVIEW = 'content/reviews/v12-c10-peer.json'
SOURCE_IDS = {'v12-c10-train-simulation2009', 'v12-c10-rust1987',
              'v12-c10-gourieroux-monfort-renault1993'}


def require(condition, message):
    if not condition:
        raise ValueError('C10 peer: ' + message)


def finite(x):
    require(type(x) in (int, float, Q), 'numeric scalar, excluding bool')
    try:
        y = float(x)
    except (OverflowError, ValueError):
        raise ValueError('C10 peer: unrepresentable scalar') from None
    require(math.isfinite(y) and abs(y) <= 10**9, 'bounded finite scalar')
    return Q(str(x)) if type(x) is float else Q(x)


def count(n):
    require(type(n) is int and 1 <= n <= 10000, 'bounded positive integer')
    return n


def strict_json(raw):
    def pairs(items):
        d = {}
        for k, v in items:
            require(k not in d, 'duplicate JSON key')
            d[k] = v
        return d
    def bad(x):
        raise ValueError('C10 peer: nonfinite JSON token ' + x)
    value = json.loads(raw, object_pairs_hook=pairs, parse_constant=bad)
    def scan(x):
        if isinstance(x, float):
            require(math.isfinite(x), 'overflowed JSON number')
        elif isinstance(x, dict):
            for v in x.values():
                scan(v)
        elif isinstance(x, list):
            for v in x:
                scan(v)
    scan(value)
    return value


def average(values):
    require(bool(values), 'nonempty mean')
    return sum(values, Q(0))/len(values)


def covariance(x, y):
    require(len(x) == len(y) and bool(x), 'paired covariance')
    return average([a*b for a, b in zip(x, y)])-average(x)*average(y)


def polynomial_root(fun, left, right):
    left, right = float(finite(left)), float(finite(right))
    require(left < right, 'ordered interval')
    a, b = fun(left), fun(right)
    require(math.isfinite(a) and math.isfinite(b) and a*b <= 0, 'bracketed finite root')
    if a == 0:
        return left
    if b == 0:
        return right
    for _ in range(85):
        mid = left+(right-left)/2
        f = fun(mid)
        require(math.isfinite(f), 'finite root evaluation')
        if f == 0 or mid in (left, right):
            return mid
        if a*f > 0:
            left, a = mid, f
        else:
            right = mid
    return (left+right)/2


def line_projection(moments, weights):
    """Centered weighted regression, rather than a matrix-inverse formula."""
    require(len(moments) == len(weights) == 3, 'three observed design points')
    m, w = [finite(x) for x in moments], [finite(x) for x in weights]
    require(all(x > 0 for x in w), 'positive projection weights')
    mass = sum(w)
    center = sum(w[i]*i for i in range(3))/mass
    response = sum(w[i]*m[i] for i in range(3))/mass
    denominator = sum(w[i]*(i-center)**2 for i in range(3))
    require(denominator > 0, 'nonconstant design')
    slope = sum(w[i]*(i-center)*(m[i]-response) for i in range(3))/denominator
    intercept = response-slope*center
    residual = [m[i]-intercept-slope*i for i in range(3)]
    return intercept, slope, residual, sum(wi*ri**2 for wi, ri in zip(w, residual))


def coefficient_variance(n, r, shared):
    n, r = count(n), count(r)
    require(type(shared) is bool, 'explicit sharing law')
    require(n*r <= 4096, 'bounded independent-coordinate budget')
    # Collect independent standard-normal coefficients by actual shock identity.
    terms = {('data', i): Q(1, n) for i in range(n)}
    for i in range(n):
        for j in range(r):
            key = ('draw', j) if shared else ('draw', i, j)
            terms[key] = terms.get(key, Q(0))-Q(1, n*r)
    return sum(v*v for v in terms.values())


def difference_noise(r, step, same_draws):
    r, step = count(r), finite(step)
    require(step > 0 and type(same_draws) is bool, 'positive step and sharing law')
    coefficients = {}
    for side, sign in [(0, -1), (1, 1)]:
        for j in range(r):
            key = j if same_draws else (side, j)
            coefficients[key] = coefficients.get(key, Q(0))+Q(sign, r)/step
    return sum(x*x for x in coefficients.values())


def simulated_score(parameter, truth):
    p, pi = finite(parameter), finite(truth)
    require(Q(1, 4) <= p <= Q(3, 4) and 0 <= pi <= 1, 'binary compact law')
    first = second = curvature = cross = Q(0)
    criterion = 0.
    for sign in (-1, 1):
        probability = p+Q(sign, 5)
        for y in (0, 1):
            weight = (pi if y else 1-pi)/2
            score = 1/probability if y else -1/(1-probability)
            first += weight*score
            second += weight*score**2
            curvature += weight/(probability if y else 1-probability)**2
            criterion += float(weight)*math.log(float(probability if y else 1-probability))
        cross += (1/probability+1/(1-probability))/2
    return first, curvature, second-first**2, cross, criterion


def simulated_target(truth):
    pi = finite(truth)
    require(0 <= pi <= 1, 'valid truth probability')
    score = lambda p: float(simulated_score(p, pi)[0])
    if score(Q(1, 4)) <= 0:
        return .25
    if score(Q(3, 4)) >= 0:
        return .75
    return polynomial_root(score, .25, .75)


def auxiliary_covariance(h, shared):
    h = count(h)
    require(type(shared) is bool, 'explicit covariate law')
    # Coefficient vectors for root-N means in independent Gaussian coordinates.
    observed = {'X': Q(1), 'epsilon': Q(1)}
    simulated = {'X': Q(1)} if shared else {}
    for j in range(h):
        simulated['u'+str(j)] = Q(1, h)
        if not shared:
            simulated['X'+str(j)] = Q(1, h)
    keys = set(observed)|set(simulated)
    vo = sum(x*x for x in observed.values())
    vs = sum(x*x for x in simulated.values())
    cross = sum(observed.get(k, Q(0))*simulated.get(k, Q(0)) for k in keys)
    difference = sum((observed.get(k, Q(0))-simulated.get(k, Q(0)))**2 for k in keys)
    return vo, vs, cross, difference


def binding_estimate(d):
    d = finite(d)
    return math.sqrt(float(min(Q(9), max(Q(0), d))))


def regular_binding_variance(h, theta, shared):
    theta = finite(theta)
    require(0 < theta < 3, 'regular interior binding parameter')
    return auxiliary_covariance(h, shared)[3]/(4*theta**2)


def dynamic_cubic(k, ell):
    """beta=1/2: t=exp((V1-V0)/2) solves a monotone cubic.

    This oracle and its analytic derivatives use neither value iteration nor
    an inverse Bellman Jacobian.  The root is in [sqrt(ell),1].
    """
    k, ell = float(finite(k)), float(finite(ell))
    require(0 < k <= 4 and 0 < ell <= 1, 'positive bounded exponential costs')
    t = 1. if ell == 1 else polynomial_root(
        lambda x: x**3+k*x*x-ell*x-k, math.sqrt(ell), 1.)
    v0 = 2*math.log(t+k)
    return t, [v0, v0+2*math.log(t)], [k/(t+k), k/(ell*t+k)]


def cubic_sensitivity(t, k, ell):
    t, k, ell = map(finite, (t, k, ell))
    denominator = 3*t*t+2*k*t-ell
    require(denominator > 0 and t > 0 and k > 0 and ell > 0, 'regular cubic')
    tr, tc = k*(t*t-1)/denominator, -ell*t/denominator
    value = [[2*(tr-k)/(t+k), 2*tc/(t+k)],
             [2*(tr-k)/(t+k)+2*tr/t, 2*tc/(t+k)+2*tc/t]]
    probabilities = [k/(t+k), k/(ell*t+k)]
    odds = [[-1-tr/t, -tc/t], [-1-tr/t, 1-tc/t]]
    derivatives = [[p*(1-p)*v for v in row] for p, row in zip(probabilities, odds)]
    return value, odds, derivatives


def inverse_choices(p0, p1, beta):
    p0, p1, beta = map(lambda x: float(finite(x)), (p0, p1, beta))
    require(0 < p0 <= p1 < 1 and 0 <= beta < 1, 'admissible ordered choice rates')
    difference = math.log(p0/p1)
    c = math.log((1-p0)*p1/(p0*(1-p1)))
    r = math.log((1-p0)/p0)-beta*difference
    v0 = (-r-math.log(p0))/(1-beta)
    return r, c, [v0, v0+difference]


def logistic(x):
    return 1/(1+math.exp(-x))


def equilibrium_set(b, h):
    """Solve in the log-odds coordinate, with a proved finite root bound."""
    b, h = float(finite(b)), float(finite(h))
    require(0 <= b <= 8 and abs(h) <= 1, 'bounded interaction and intervention')
    # At a solution x=b*(logistic(x)-1/2)+h, hence |x|<=b/2+|h|.
    bound = b/2+abs(h)+1
    def curve(x):
        if x < 0:
            return -curve(-x)
        return x-b*(logistic(x)-.5)
    cuts = [-bound, bound]
    if b > 4:
        critical = math.acosh(b/2-1)
        cuts = [-bound, -critical, critical, bound]
    roots = []
    for left, right in zip(cuts, cuts[1:]):
        fl, fr = curve(left)-h, curve(right)-h
        if fl == 0 and left not in roots:
            roots.append(left)
        if fl*fr < 0:
            roots.append(polynomial_root(lambda x: curve(x)-h, left, right))
        if fr == 0 and right not in roots:
            roots.append(right)
    require(bool(roots), 'located equilibrium')
    return [logistic(x) for x in sorted(roots)]


def branch_sensitivity(q, b):
    q, b = float(finite(q)), float(finite(b))
    require(0 < q < 1, 'interior adoption fraction')
    denominator = 1-b*q*(1-q)
    require(abs(denominator) > 1e-12, 'regular branch away from a fold')
    return q*(1-q)/denominator


class Evidence:
    def __init__(self):
        self.comparisons = 0
        self.rejections = []

    def same(self, actual, expected, label):
        require(actual == expected, label)
        self.comparisons += 1

    def close(self, actual, expected, label, tolerance=8e-10):
        if isinstance(expected, (list, tuple)):
            require(isinstance(actual, (list, tuple)) and len(actual) == len(expected), label+' shape')
            for a, e in zip(actual, expected):
                self.close(a, e, label, tolerance)
            return
        if type(actual) in (int, Q) and type(expected) in (int, Q):
            self.same(actual, expected, label+' exact')
            return
        a, e = float(actual), float(expected)
        require(math.isfinite(a) and math.isfinite(e), label+' finite')
        require(abs(a-e) <= tolerance*max(1., abs(e)), label)
        self.comparisons += 1

    def reject(self, call, label):
        try:
            call()
        except (ValueError, TypeError, SyntaxError):
            self.rejections.append(label)
            self.comparisons += 1
        else:
            raise ValueError('C10 peer: missing rejection '+label)


def reconstruct():
    e, out = Evidence(), {}
    # Case 1: direct market balance and orthogonal finite sign basis.
    rows = []
    for w, z, u, v in product((-1, 1), repeat=4):
        demand_intercept, supply_intercept = 10+w+u, 1-z+v
        price = Q(demand_intercept-supply_intercept, 3)
        quantity = demand_intercept-2*price
        e.same(quantity, supply_intercept+price, 'market balance in each original atom')
        rows.append((Q(w), Q(z), Q(u), Q(v), price, quantity))
    w, z, u, v, p, q = map(list, zip(*rows))
    out['supply-means'] = [average(p), average(q)]
    out['cost-covs'] = [covariance(z,p), covariance(z,q)]
    out['demand-covs'] = [covariance(w,p), covariance(w,q)]
    for control, name in [(w,'demand-ols'), (z,'supply-ols')]:
        pr = [x-average(p)-covariance(p,control)*c for x,c in zip(p,control)]
        qr = [x-average(q)-covariance(q,control)*c for x,c in zip(q,control)]
        out[name] = covariance(pr,qr)/covariance(pr,pr)
        e.same(covariance(pr,control),0,'projection removes stipulated exogenous sign')
    out['e1-iv'] = [out['cost-covs'][1]/out['cost-covs'][0], out['demand-covs'][1]/out['demand-covs'][0]]
    invalid = [zz+uu for zz,uu in zip(z,u)]
    out['e1-invalid-iv'] = covariance(invalid,q)/covariance(invalid,p)
    e.same(covariance(invalid,u),1,'invalid instrument exclusion failure')
    out['tax-rich'] = [average([x+Q(1,3) for x in p]), average([x-Q(2,3) for x in q])]
    def tax(d):
        d=finite(d); require(d>0,'positive supply slope')
        return [3+d/(2+d),4-2*d/(2+d)]
    for slope in [Q(1,2),Q(1),Q(2)]:
        intercept, shift = 4-3*slope,(2+slope)/3
        for cost in [Q(-1),Q(0),Q(1)]:
            pp=3+cost/3; qq=4-2*cost/3
            e.same(qq,intercept+slope*pp-shift*cost,'same full cost-only mapping')
    out['tax-family1'],out['tax-family2'],out['e2-d2-tax']=tax(1),tax(Q(1,2)),tax(2)
    out['e2-calibrated-d']=3*Q(5,6)-2
    out['e2-calibrated-tax']=tax(out['e2-calibrated-d'])
    # Case 2: centered regression coefficients and basis perturbations.
    a,b,residual,loss=line_projection([1,3,6],[1,2,1])
    out['md-target'],out['md-residual'],out['md-loss']=[a,b],residual,loss
    out['md-normal']=[[sum(Q(w)*i**(j+k) for i,w in enumerate([1,2,1])) for k in (0,1)] for j in (0,1)]
    basis=[line_projection([int(i==j) for i in range(3)],[1,2,1])[:2] for j in range(3)]
    operator=[list(x) for x in zip(*basis)]
    out['md-map']=operator
    variances=[Q(1),Q(1,2),Q(1)]
    vmat=[[sum(operator[i][k]*operator[j][k]*variances[k] for k in range(3)) for j in range(2)] for i in range(2)]
    out['md-covariance']=vmat
    quantity=(5-a)/b
    gradient=[-1/b,-quantity/b]
    sensitivity=[sum(gradient[j]*operator[j][k] for j in range(2)) for k in range(3)]
    out['md-output'],out['md-gradient']=quantity,sensitivity
    out['md-delta-variance']=sum(s*s*v for s,v in zip(sensitivity,variances))
    ap,bp,_,_=line_projection([1,3,Q(61,10)],[1,2,1])
    out['md-perturbed']=(5-ap)/bp
    out['md-exact-change']=out['md-perturbed']-quantity
    out['md-linear-change']=sensitivity[-1]/10
    au,bu,ru,lu=line_projection([1,3,6],[1,1,1])
    out['e3-target'],out['e3-loss'],out['e3-output']=[au,bu],lu,(5-au)/bu
    e.same(sum(w*r for w,r in zip([1,2,1],residual)),0,'projection level orthogonality')
    e.same(sum(i*w*r for i,(w,r) in enumerate(zip([1,2,1],residual))),0,'projection slope orthogonality')
    e.same(au!=a,True,'pseudo-target depends on weights')
    out['extrapolation-outputs']=[Q(6),Q(3)]
    out['e4-policy-derivative']=-Q(3*2*1,2-1+3*(3-1)**2)
    for kappa in [Q(0),Q(1,2),Q(1)]:
        mc=lambda x:1+2*x+float(kappa)*x*(x-1)*(x-2)
        for design in (0,1,2): e.close(mc(design),1+2*design,'same observed marginal costs')
        crossing=polynomial_root(lambda x:mc(x)-13,3,6)
        e.close(mc(crossing),13,'monotone global competitive crossing')
        e.same(2-kappa>=1,True,'global marginal-cost derivative lower bound')
    # Case 3: independent-coordinate maps and exact four-atom score laws.
    out['sim-independent-variance']=coefficient_variance(100,4,False)
    out['sim-shared-variance']=coefficient_variance(100,4,True)
    out['sim-fd-variance']=difference_noise(4,Q(1,100),False)
    out['sim-crn-derivative'],out['sim-crn-variance']=Q(1),difference_noise(4,Q(1,100),True)
    out['e5-variances']=[coefficient_variance(80,5,s) for s in (False,True)]
    out['e5-fd'],out['e5-crn']=difference_noise(5,Q(1,50),False),difference_noise(5,Q(1,50),True)
    truth=Q(9,25); target=Q(2,5)
    score,H,Omega,_,criterion=simulated_score(target,truth)
    e.same(score,0,'four-atom stationary score')
    e.same(simulated_score(Q(1,4),truth)[0]>0>simulated_score(Q(3,4),truth)[0],True,'unique interior criterion target')
    e.close(simulated_target(truth),target,'bracketed target from score, not saved result')
    out.update({'msl-score-truth':simulated_score(truth,truth)[0],'msl-target':target,'mle-target':truth,'msl-bias':target-truth,'msl-H':H,'msl-Omega':Omega,'msl-variance':Omega/H**2,'mle-variance':truth*(1-truth)})
    e.same(criterion>simulated_score(truth,truth)[4],True,'expected simulated objective prefers pseudo-target')
    e.same(criterion<float(truth)*math.log(float(target))+float(1-truth)*math.log(float(1-target)),True,'strict log Jensen bias')
    hs=simulated_score(Q(1,2),Q(1,2))
    out.update({'e6-target':Q(1,2),'e6-H':hs[1],'e6-cross-derivative':hs[3],'e6-target-derivative':hs[3]/hs[1],'e6-variance':hs[2]/hs[1]**2})
    e.same(hs[0],0,'symmetric target score')
    e.same(hs[4]<math.log(.5),True,'criterion bias persists at unbiased target')
    h=1e-5
    e.close((simulated_target(.5+h)-simulated_target(.5-h))/(2*h),hs[3]/hs[1],'target derivative',2e-8)
    e.same([simulated_target(0),simulated_target(1)],[.25,.75],'boundary targets')
    for r in [1,2,4,8]:
        mean_abs=sum(Q(math.comb(r,j),2**r)*abs(Q(2*j-r,r)) for j in range(r+1))
        second=sum(Q(math.comb(r,j),2**r)*Q(2*j-r,r)**2 for j in range(r+1))
        e.same(second,Q(1,r),'binomial simulation-mean variance')
        e.same(mean_abs**2<=second,True,'finite-law Lipschitz expectation bound input')
    # Case 4: actual shared coordinates, rather than adding marginal variances.
    x,y=[-1,0,1,0],[0,2,4,3]
    noise=[-1,0,1,2,-1,0,0,1]
    ybar,ubar=average(list(map(Q,y))),average(list(map(Q,noise)))
    d=ybar-average(list(map(Q,x)))-ubar
    out.update({'ii-ymean':ybar,'ii-umean':ubar,'ii-D':d,'ii-estimate':binding_estimate(d)})
    vo,vs,co,vd=auxiliary_covariance(2,True)
    out.update({'ii-observed-var':vo,'ii-sim-var':vs,'ii-cross':co,'ii-diff-var':vd,'ii-theta-var':regular_binding_variance(2,Q(3,2),True),'ii-wrong-independent':(vo+vs)/9,'ii-wrong-blanket':vo*Q(3,2)/9,'ii-boundary-atom':Q(1,2),'e7-difference-variance':auxiliary_covariance(2,False)[3],'e7-theta-variance':regular_binding_variance(2,Q(3,2),False),'e8-signed-estimates':[-math.sqrt(float(d)),math.sqrt(float(d))]})
    e.same(vo+vs-2*co,vd,'explicit cross-covariance subtraction')
    for z in [-2,0,2]:
        n=10000
        e.close(n**.25*binding_estimate(Q(z,100)),math.sqrt(max(0,z)),'zero-boundary transformed law')
        observed=100*(binding_estimate(9+Q(z,100))-3)
        exact=min(z,0)/(math.sqrt(9+z/100)+3)
        e.close(observed,exact,'upper-boundary transformed law')
    e.same([binding_estimate(-1),binding_estimate(10)],[0.,3.],'both projection boundaries')
    # Case 5: positive-root cubic and polynomial implicit differentiation.
    t,values,probs=dynamic_cubic(Q(1,5),Q(11,20))
    base_values=values[:]
    e.close(t,Q(4,5),'exact cubic root')
    out['dynamic-v0'],out['dynamic-v1']=values
    rational_probs=[Q(1,5),Q(5,16)]
    e.close(probs,rational_probs,'cubic choice rates')
    out['dynamic-probs']=rational_probs
    transition=[[p,1-p] for p in rational_probs]
    out['dynamic-transition']=transition
    # Regenerative flow balance: mass in state 0 times exit probability equals
    # mass in state 1 times entry probability.
    p0,p1=rational_probs
    mass0=p1/(p1+1-p0)
    stationary=[mass0,1-mass0]
    out['dynamic-stationary']=stationary
    out['dynamic-replace-rate']=mass0*p0+(1-mass0)*p1
    e.same(mass0*(1-p0),(1-mass0)*p1,'stationary inter-state flow')
    out['dynamic-ll']=sum(n*math.log(float(p)) for n,p in [(4,p0),(16,1-p0),(5,p1),(11,1-p1)])
    value_deriv,odds_deriv,prob_deriv=cubic_sensitivity(Q(4,5),Q(1,5),Q(11,20))
    out['dynamic-dV'],out['dynamic-dlogit'],out['dynamic-dp']=value_deriv,odds_deriv,prob_deriv
    out['e10-dVc']=[row[1] for row in value_deriv]
    out['e10-dpc']=[row[1] for row in prob_deriv]
    out['dynamic-subsidy']=dynamic_cubic(Q(2,5),Q(11,20))[2]
    out['static-subsidy']=[Q(1,2)/(1+Q(1,2)),Q(1,2)/(Q(11,20)+Q(1,2))]
    for j in (0,1):
        r,c=math.log(5),math.log(20/11); step=1e-5
        upper=[r,c]; lower=[r,c]; upper[j]+=step; lower[j]-=step
        _,vu,pu=dynamic_cubic(math.exp(-upper[0]),math.exp(-upper[1]))
        _,vl,pl=dynamic_cubic(math.exp(-lower[0]),math.exp(-lower[1]))
        e.close([(a-b)/(2*step) for a,b in zip(vu,vl)],[row[j] for row in value_deriv],'polynomial value derivative',2e-8)
        e.close([(a-b)/(2*step) for a,b in zip(pu,pl)],[row[j] for row in prob_deriv],'polynomial probability derivative',2e-8)
    for beta in [0.,.5,.9]:
        r,c,values=inverse_choices(p0,p1,beta)
        for s,p in enumerate(rational_probs):
            keep=math.exp(-c*s+beta*values[1]); replace=math.exp(-r+beta*values[0])
            e.close(math.log(keep+replace),values[s],'discount family fixed-point identity')
            e.close(replace/(keep+replace),p,'discount family identical observation law')
    e.close(dynamic_cubic(Q(1,5),1)[2],[Q(1,6),Q(1,6)],'zero deterioration boundary')
    beta,delta=Q(9,10),Q(1,1000)
    out['e9-value-bound']=delta/(1-beta)
    out['e9-log-bound']=2*beta*delta/(1-beta)
    out['e9-sum-bound']=36*out['e9-log-bound']
    # Check a deliberately inexact value, with the cubic solution as oracle.
    approximate=[base_values[0]+.02,base_values[1]-.01]
    r,c=math.log(5),math.log(20/11)
    operator=lambda v,s: math.log(math.exp(-c*s+.5*v[1])+math.exp(-r+.5*v[0]))
    residual=max(abs(operator(approximate,s)-approximate[s]) for s in (0,1))
    e.same(max(abs(a-v) for a,v in zip(approximate,base_values))<=2*residual+2e-12,
           True,'actual cubic value error below residual certificate')
    for s,p in enumerate(rational_probs):
        logprob=-r+.5*approximate[0]-operator(approximate,s)
        e.same(abs(logprob-math.log(float(p)))<=2*residual+2e-12,
               True,'actual log probability error below certificate')
        shifted=[v+1.4 for v in base_values]
        e.close(.7+operator(shifted,s),shifted[s],'common shock-location fixed point')
    # Case 6: complete monotone branches in the log-odds coordinate.
    b=4*math.log(3); xc=math.acosh(b/2-1)
    critical=[logistic(-xc),logistic(xc)]
    fold=b*(logistic(xc)-.5)-xc
    baseline=equilibrium_set(b,0); small=equilibrium_set(b,.02)
    large=equilibrium_set(b,.1); negative=equilibrium_set(b,-.02)
    out.update({'eq-unique':equilibrium_set(2,0)[0],'eq-unique-modulus':Q(1,2),'eq-unique-derivative':branch_sensitivity(.5,2),'eq-baseline':baseline,'eq-critical':critical,'eq-fold':fold,'eq-derivatives':[branch_sensitivity(q,b) for q in baseline],'eq-slopes':[b*q*(1-q) for q in baseline],'eq-small-policy':small,'eq-large-policy':large[0],'eq-mean-set':[small[0],small[-1]],'e11-negative-roots':negative,'e11-mean-set':[negative[0],negative[-1]]})
    for shift,size in [(0,3),(.02,3),(.1,1),(fold,2),(-fold,2),(fold-1e-6,3),(fold+1e-6,1)]:
        roots=equilibrium_set(b,shift)
        e.same(len(roots),size,'complete fold interval root count')
        for q in roots: e.close(q,logistic(-b/2+shift+b*q),'direct equilibrium equation')
    e.close(baseline,[Q(1,4),Q(1,2),Q(3,4)],'three exact baseline equilibria')
    e.close(negative,[1-q for q in reversed(small)],'policy reflection')
    e.same(len(equilibrium_set(4,0)),1,'unique threshold interaction equilibrium')
    mean=.6; weight=(mean-small[0])/(small[-1]-small[0])
    e.same(0<weight<1,True,'nontrivial feasible selection weights')
    e.close((1-weight)*small[0]+weight*small[-1],mean,'selection mean reconstruction')
    # Deliberate contract failures; no random grid or external estimator API.
    failures=[
        (lambda:finite(True),'boolean numeric input'),(lambda:finite(float('nan')),'NaN scalar'),
        (lambda:finite(float('inf')),'infinite scalar'),(lambda:finite(10**400),'unrepresentable scalar'),
        (lambda:line_projection([1,2],[1,1]),'moment dimensions'),
        (lambda:line_projection([1,3,6],[1,0,1]),'zero criterion weight'),
        (lambda:coefficient_variance(0,2,False),'empty sample'),
        (lambda:coefficient_variance(2,1.5,False),'fractional simulation count'),
        (lambda:coefficient_variance(2,2,1),'implicit coupling flag'),
        (lambda:coefficient_variance(100,100,False),'coordinate budget'),
        (lambda:difference_noise(2,0,False),'zero derivative step'),
        (lambda:simulated_score(Q(1,5),Q(1,2)),'outside positive compact likelihood domain'),
        (lambda:simulated_target(Q(6,5)),'invalid Bernoulli law'),
        (lambda:regular_binding_variance(2,0,True),'zero is nonregular'),
        (lambda:regular_binding_variance(2,3,True),'upper endpoint is nonregular'),
        (lambda:dynamic_cubic(0,Q(1,2)),'zero exponential replacement index'),
        (lambda:dynamic_cubic(1,2),'negative deterioration outside oracle domain'),
        (lambda:inverse_choices(Q(1,5),Q(5,16),1),'undiscounted inverse'),
        (lambda:inverse_choices(Q(1,2),Q(1,5),.5),'choice ordering'),
        (lambda:equilibrium_set(9,0),'unbounded interaction'),
        (lambda:equilibrium_set(b,2),'unbounded policy'),
        (lambda:branch_sensitivity(critical[0],b),'fold derivative'),
        (lambda:polynomial_root(lambda x:x*x+1,-1,1),'unbracketed root')]
    for call,label in failures: e.reject(call,label)
    for raw in ['{"x":1,"x":2}','{"x":NaN}','{"x":Infinity}','{"x":-Infinity}','{"x":1e400}','{"x":[1e400]}']:
        e.reject(lambda raw=raw:strict_json(raw),'strict JSON '+raw)
    return out,e


def expression(raw):
    require(isinstance(raw,str) and len(raw)<300,'bounded visible expression')
    tree=ast.parse(raw.replace('−','-').strip(),mode='eval')
    require(len(list(ast.walk(tree)))<100,'bounded expression tree')
    def parse(n):
        if isinstance(n,ast.Expression): return parse(n.body)
        if isinstance(n,ast.Constant) and type(n.value) in (int,float):
            return finite(n.value) if type(n.value) is int else float(finite(n.value))
        if isinstance(n,ast.Tuple): return [parse(x) for x in n.elts]
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,(ast.USub,ast.UAdd)):
            return -parse(n.operand) if isinstance(n.op,ast.USub) else parse(n.operand)
        if isinstance(n,ast.BinOp) and isinstance(n.op,(ast.Add,ast.Sub,ast.Mult,ast.Div)):
            a,b=parse(n.left),parse(n.right)
            if isinstance(n.op,ast.Add): return a+b
            if isinstance(n.op,ast.Sub): return a-b
            if isinstance(n.op,ast.Mult): return a*b
            require(b!=0,'nonzero expression denominator');return a/b
        if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id in ('log','sqrt'):
            require(len(n.args)==1 and not n.keywords,'unary safe function')
            x=float(parse(n.args[0]));require(x>0 if n.func.id=='log' else x>=0,'safe function domain')
            return math.log(x) if n.func.id=='log' else math.sqrt(x)
        raise ValueError('C10 peer: unsupported visible expression')
    return parse(tree)


class Reader(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack=[];self.ids=[];self.links=[];self.sources=[];self.worked=0
        self.values={};self.prompts={};self.solutions={};self.active=[]

    def handle_starttag(self,tag,attrs):
        a=dict(attrs);classes=a.get('class','').split()
        require(tag not in ('script','iframe','h1'),'static chapter fragment')
        if 'id' in a:self.ids.append(a['id'])
        if 'href' in a:self.links.append(a['href'])
        if 'data-source' in a:self.sources.append(a['data-source'])
        if 'worked' in classes:self.worked+=1
        target=None;store=None
        if tag=='li' and any(t=='ol' and 'exercises' in c for t,c in self.stack):
            store=self.prompts;target=a.get('id')
        elif tag=='li' and any(t=='details' and 'solutions' in c for t,c in self.stack):
            store=self.solutions;target=a.get('data-solution-for')
        if store is not None:
            require(target is not None and target not in store,'unique exact prompt/solution')
            store[target]='';self.active.append((len(self.stack),store,target))
        if 'data-calc' in a:
            key=a['data-calc'];require(key not in self.values,'unique calculation marker')
            self.values[key]='';self.active.append((len(self.stack),self.values,key))
        if tag not in ('br','hr','img','meta','link','input'):
            self.stack.append((tag,classes))

    def handle_endtag(self,tag):
        require(bool(self.stack) and self.stack[-1][0]==tag,'balanced chapter markup')
        self.stack.pop()
        self.active=[x for x in self.active if x[0]<len(self.stack)]

    def handle_data(self,data):
        require(bool(self.stack) or not data.strip(),'no stray reader text')
        for _,store,key in self.active:store[key]+=data


def snapshot(root,paths):
    out=[]
    for rel in paths:
        raw=(root/rel).read_bytes()
        out.append({'path':rel,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
    return out


def check(root=None):
    base=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    outputs,e=reconstruct()
    raw=(base/AUTHOR[0]).read_text();page=Reader();page.feed(raw);page.close()
    expected=['v12-c10-e'+str(i).zfill(2) for i in range(1,13)]
    e.same(list(page.prompts),expected,'all twelve exact questions')
    e.same(list(page.solutions),expected,'all twelve paired full answers')
    e.same(page.worked,6,'six worked cases')
    e.same(page.stack,[],'closed fragment')
    e.same(page.active,[],'closed reader captures')
    e.same(len(page.ids),len(set(page.ids)),'unique reader IDs')
    e.same(set(page.values),set(outputs),'all visible numeric anchors independently derived')
    for key,value in outputs.items():e.close(expression(page.values[key]),value,'visible '+key)
    for i in expected:
        e.same(len(page.prompts[i])>80,True,'nonempty exact prompt '+i)
        e.same(len(page.solutions[i])>300,True,'complete exact answer '+i)
    e.same('Benchmark answer.' in raw and '<strong>Answers.</strong>' in raw,True,'answered teaching and retention')
    allowed={'v12-c09.html','v02-c10.html','v12-c01.html','v12-c03.html','v12-c04.html'}|{'sources.html#'+s for s in SOURCE_IDS}
    e.same(set(page.sources),SOURCE_IDS,'three actual method source links')
    for link in page.links:e.same(link in allowed,True,'flat prerequisite/source link')
    source=strict_json((base/AUTHOR[2]).read_text())
    e.same({x['id'] for x in source['proposals']},SOURCE_IDS,'source proposal identity')
    for proposal in source['proposals']:
        e.same(proposal['inspection']['reader'],'c05_review','actual primary inspector')
        e.same('verification' in proposal,True,'scoped verification field')
    author=strict_json((base/AUTHOR[3]).read_text())
    e.same(author['reviewed_hashes'],snapshot(base,AUTHOR[:3]),'author three nonself bindings')
    peer=strict_json((base/REVIEW).read_text())
    e.same(peer['reviewed_hashes'],snapshot(base,AUTHOR+(SELF,)),'peer four author plus checker bindings')
    e.same(peer['status'],'passed; frozen for coordinator acceptance','completed separate review status')
    e.same(len(peer['prompt_solution_audit']),12,'all exact prompt audit records')
    e.same([row['id'] for row in peer['prompt_solution_audit']],expected,'exact audit coverage and order')
    for row in peer['prompt_solution_audit']:
        text=' '.join(page.prompts[row['id']].split())
        e.same(row['prompt_sha256'],hashlib.sha256(text.encode()).hexdigest(),'exact audited prompt '+row['id'])
    e.same(peer['open_findings'],[],'no unresolved peer findings')
    for candidate in ['__import__("os")','log(0)','1/0']:
        e.reject(lambda candidate=candidate:expression(candidate),'unsupported displayed expression '+candidate)
    result={'chapter':'v12-c10','status':'passed','independent_comparisons':e.comparisons,
            'worked_cases':6,'exercises':12,'solutions':12,'visible_anchors':len(outputs),
            'executed_rejections':len(e.rejections),'author_files_bound':4,'peer_checker_bound':True,
            'oracle_methods':['16-state centered projection and exclusion sums','centered weighted regression and basis perturbations','Gaussian coordinate maps and finite simulated score atoms','shared-coordinate covariance and clipped binding identities','positive cubic and implicit polynomial derivatives','log-odds root intervals and explicit fold/selection checks'],
            'limits':'Finite checks accompany separate proof/solution/source reading; no author helper is an oracle, empirical invariance, generic simulation CLT, rendered UI or chapter acceptance is certified.'}
    strict_json(json.dumps(result,allow_nan=False))
    return result


if __name__=='__main__':
    check()
