"""Quiet, no-write C12 audit from original primitives; four runtime files only.

Exact finite accounts and polynomial identities corroborate the printed proofs.
No finite grid is presented as a proof of a continuum or an equilibrium theorem.
"""
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from itertools import product
from math import isfinite, isqrt
import json
from pathlib import Path

FILES = ('content/chapters/v13-c12.html',
         'scripts/check_v13_c12.py',
         'content/reviews/v13-c12-sources.json',
         'content/reviews/v13-c12-author.json')


def number(x):
    if isinstance(x, bool) or not isinstance(x, (int, float, F)):
        raise ValueError('finite real numeric scalar required')
    if isinstance(x, float) and not isfinite(x):
        raise ValueError('nonfinite scalar')
    return F(x)


def vec(xs, n=None):
    if not isinstance(xs, (tuple, list)) or not xs or (n is not None and len(xs) != n):
        raise ValueError('nonempty list of the required dimension')
    return tuple(number(x) for x in xs)


def weights(total, lam):
    total, lam = number(total), number(lam)
    if total < 0 or not 0 <= lam <= 1:
        raise ValueError('resource and normalized weight domain')
    x = min(total, max(F(0), (total+2)*lam-1))
    return x, total-x


def poly(p, x):
    return sum((F(a)*x**i for i, a in enumerate(p)), F(0))


def derivative(p):
    return tuple(i*p[i] for i in range(1, len(p)))


def multiply(a, b):
    out = [F(0)]*(len(a)+len(b)-1)
    for i, x in enumerate(a):
        for j, y in enumerate(b):
            out[i+j] += x*y
    return tuple(out)


COEF = (F(0), F(96), F(-84), F(28), F(-3))


def capacity(cap):
    cap = number(cap)
    if not 0 < cap <= 5:
        raise ValueError('capacity must be in the declared positive range')
    candidates = sorted(set((F(0), cap)) | {F(x) for x in (1,2,4) if 0 < x < cap})
    values = tuple(poly(COEF, x) for x in candidates)
    high = max(values)
    return tuple(candidates), values, tuple(x for x,v in zip(candidates,values) if v == high), high


def approximation(f, computed, chosen, eta):
    f, g = vec(f), vec(computed)
    eta = number(eta)
    if len(f) != len(g) or isinstance(chosen, bool) or not isinstance(chosen, int) or not 0 <= chosen < len(f) or eta < 0:
        raise ValueError('finite approximation dimensions/index/tolerance')
    gap = max(g)-g[chosen]
    if gap > eta:
        raise ValueError('claimed global approximate-solver gap is false')
    error = max(abs(a-b) for a,b in zip(f,g))
    return error, gap, 2*error+eta, max(f)-f[chosen]


def game(b, costs, grants, cash):
    b = number(b); c = vec(costs, 2); s = vec(grants, 2); cash = number(cash)
    if b <= 0 or any(not 0 < x < b for x in c) or min(s) < 0 or cash < sum(s):
        raise ValueError('positive costs below benefit, nonnegative funded grants required')
    return b,c,s,cash


def equilibria(b, costs, grants, cash):
    b,c,s,_ = game(b,costs,grants,cash)
    t1,t2 = ((c[i]-s[i])/b for i in range(2))
    if min(t1,t2) < 0:
        return {'points':((F(1),F(1)),), 'segments':()}
    if t1 > 0 and t2 > 0:
        return {'points':((F(0),F(0)),(F(1),F(1)),(t2,t1)), 'segments':()}
    if t1 == t2 == 0:
        return {'points':((F(0),F(0)),(F(1),F(1))), 'segments':()}
    # (varying coordinate, fixed-other value, closed lower/upper ends).
    segment = (0,F(0),F(0),t2) if t1 == 0 else (1,F(0),F(0),t1)
    return {'points':((F(1),F(1)),), 'segments':(segment,)}


def gain(b, costs, grants, p):
    p = vec(p,2)
    if min(p) < 0 or max(p) > 1:
        raise ValueError('adoption probabilities must lie in the unit interval')
    return tuple(number(b)*p[1-i]-number(costs[i])+number(grants[i]) for i in range(2))


def nash_witness(b,c,s,p):
    ds = gain(b,c,s,p)
    return all((pi == 0 and di <= 0) or (pi == 1 and di >= 0) or
               (0 < pi < 1 and di == 0) for pi,di in zip(p,ds))


def joint_accounts(b, costs, grants, cash, law):
    b,c,s,cash = game(b,costs,grants,cash)
    law = vec(law,4)
    if min(law) < 0 or sum(law) != 1:
        raise ValueError('joint probability mass must be nonnegative and sum to one')
    states = tuple(product((0,1), repeat=2))
    utilities = [F(0),F(0)]; spending = welfare = F(0)
    obedience = []
    for mass,a in zip(law,states):
        spending += mass*sum(s[i]*a[i] for i in range(2))
        welfare += mass*(2*b*a[0]*a[1]-sum(c[i]*a[i] for i in range(2)))
        for i in range(2):
            utilities[i] += mass*a[i]*(b*a[1-i]-c[i]+s[i])
    for i,rec in product(range(2),(0,1)):
        # Unnormalized inequalities remain meaningful at unused recommendations.
        delta = sum(mass*(2*rec-1)*(b*a[1-i]-c[i]+s[i])
                    for mass,a in zip(law,states) if a[i] == rec)
        obedience.append(delta)
    return {'utilities':tuple(utilities),'spending':spending,'welfare':welfare,
            'cash':cash-spending,'obedience':tuple(obedience)}


def independent_law(p):
    p = vec(p,2)
    if min(p) < 0 or max(p) > 1:
        raise ValueError('independent probabilities outside unit interval')
    return tuple((p[0] if a else 1-p[0])*(p[1] if b else 1-p[1])
                 for a,b in product((0,1),repeat=2))


def transition(theta,x):
    theta,x = number(theta),number(x)
    if not 0 <= theta <= 3 or not 0 <= x <= 1:
        raise ValueError('parameter or activity outside invariant domain')
    return (theta+x*x)/4


def exact_roots(theta):
    theta = number(theta)
    transition(theta,F(0))
    d = 4-theta
    a,b = isqrt(d.numerator),isqrt(d.denominator)
    if a*a != d.numerator or b*b != d.denominator:
        raise ValueError('this exact-rational output helper requires a square discriminant')
    r = F(a,b)
    return 2-r,2+r


def error_certificate(theta,x,epsilon,eta):
    epsilon,eta = number(epsilon),number(eta)
    if min(epsilon,eta) < 0:
        raise ValueError('nonnegative error bounds required')
    residual = abs(number(x)-transition(theta,x))
    if residual > epsilon+eta:
        raise ValueError('claimed computed residual and map error cannot both hold')
    return 2*(epsilon+eta)


def budget_responses(model,z,ps,tax,buyer_cash=20,producer_cash=10):
    """Actual off-equilibrium demand and supply squared, without irrational rounding."""
    if model not in ('A','B'):
        raise ValueError('declared structural model A or B required')
    z,ps,tax,buyer_cash,producer_cash = map(number,(z,ps,tax,buyer_cash,producer_cash))
    if z not in (-1,1) or ps < 0 or not 0 <= tax <= 1 or min(buyer_cash,producer_cash) < 0:
        raise ValueError('state, price, tax or initial-resource domain')
    slope = F(2) if model == 'A' else F(4)
    intercept = (1/slope+F(1,2))*(4+2*z)
    pb = ps+tax
    unconstrained = max(F(0),slope*(intercept-pb))
    demand = unconstrained if pb == 0 else min(unconstrained,buyer_cash/pb)
    return demand,min((2*ps)**2,4*producer_cash)


def market(model,z,tax,buyer_cash=20,producer_cash=10):
    if model not in ('A','B'):
        raise ValueError('declared structural model A or B required')
    z,tax,buyer_cash,producer_cash = map(number,(z,tax,buyer_cash,producer_cash))
    if z not in (-1,1) or not 0 <= tax <= 1 or min(buyer_cash,producer_cash) < 0:
        raise ValueError('state, tax or initial-resource domain')
    slope = F(2) if model == 'A' else F(4)
    q0 = 4+2*z
    intercept = (1/slope+F(1,2))*q0
    # Solve demand q=slope*(intercept-p_b), supply q=2*p_s.
    ps = (slope*intercept-slope*tax)/(slope+2)
    q = 2*ps; pb = ps+tax
    benefit = intercept*q-q*q/(2*slope)
    cost = q*q/4
    payment = pb*q
    if min(q,ps,pb) <= 0 or cost > producer_cash or payment > buyer_cash:
        raise ValueError('unconstrained choice is not funded in this case')
    welfare = benefit-cost
    welfare0 = intercept*q0-q0*q0/(2*slope)-q0*q0/4
    return {'q':q,'ps':ps,'pb':pb,'tax':tax*q,'cost':cost,'payment':payment,
            'loss':welfare0-welfare,'welfare0':welfare0,'welfare':welfare,
            'buyer_u':benefit-payment,'producer_profit':ps*q-cost,
            'buyer_cash':buyer_cash-payment,'producer_cash':producer_cash-cost+ps*q}


def market_means(model,tax):
    rows=[market(model,z,tax) for z in (-1,1)]
    return tuple(sum(row[k] for row in rows)/2 for k in ('q','ps','pb','tax','loss'))


def prediction_intervals(epsilon):
    epsilon = number(epsilon)
    if epsilon < 0:
        raise ValueError('negative measurement-error bound')
    return ((3-epsilon,3+epsilon),(F(8,3)-epsilon,F(8,3)+epsilon))


def matching(scale=1):
    scale = number(scale)
    if scale <= 0:
        raise ValueError('strictly positive preference-preserving utility scale')
    left_orders = ((0,1),(1,0)); right_orders = ((1,0),(0,1))
    left_values = ((5,4),(4,5)); right_values = ((1,100),(100,1))
    feasible=[]; stable=[]; sums=[]
    for partners in product((None,0,1),repeat=2):
        picked=[x for x in partners if x is not None]
        if len(set(picked)) != len(picked):
            continue
        feasible.append(partners)
        inverse={r:l for l,r in enumerate(partners) if r is not None}
        blockers=[]
        for l,r in product(range(2),repeat=2):
            if partners[l] == r:
                continue
            left_wants = partners[l] is None or left_orders[l].index(r) < left_orders[l].index(partners[l])
            right_wants = r not in inverse or right_orders[r].index(l) < right_orders[r].index(inverse[r])
            if left_wants and right_wants:
                blockers.append((l,r))
        if not blockers:
            stable.append(partners)
            sums.append(sum(scale*left_values[l][r]+right_values[r][l]
                            for l,r in enumerate(partners) if r is not None))
    return tuple(feasible),tuple(stable),tuple(sums)


def fmt(x):
    if isinstance(x,(list,tuple)):
        return '('+','.join(fmt(y) for y in x)+')'
    return str(x)


def norm(x):
    return ''.join(x.replace('−','-').split())


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack=[]; self.current=None; self.ids=set(); self.duplicates=[]
        self.markers={'data-input':{},'data-calc':{}}
        self.examples=[]; self.prompts=[]; self.answers=[]; self.sources={}
        self.exdepth=0; self.soldepth=0

    def handle_starttag(self,tag,attrs):
        a=dict(attrs); classes=a.get('class','').split()
        if 'id' in a:
            if a['id'] in self.ids:self.duplicates.append(a['id'])
            self.ids.add(a['id'])
        if 'worked' in classes and 'worked-example' in classes:self.examples.append(a.get('id'))
        if tag=='ol' and 'exercises' in classes:self.exdepth=len(self.stack)+1
        if tag=='details' and 'solutions' in classes:self.soldepth=len(self.stack)+1
        if tag=='li' and self.exdepth:self.prompts.append(a.get('id'))
        if 'data-solution-for' in a:
            if not self.soldepth:raise ValueError('answer outside reader disclosure')
            self.answers.append(a['data-solution-for'])
        if 'data-source' in a:
            sid=a['data-source'];url=a.get('href')
            if sid in self.sources and self.sources[sid]!=url:raise ValueError('source URL mismatch')
            self.sources[sid]=url
        for kind in self.markers:
            if kind in a:
                if self.current or a[kind] in self.markers[kind]:raise ValueError('nested or duplicate marker')
                self.current=(kind,a[kind],len(self.stack)+1);self.markers[kind][a[kind]]=''
        if tag not in ('br','hr','img','input','meta','link','wbr'):self.stack.append(tag)

    def handle_endtag(self,tag):
        if not self.stack or self.stack[-1]!=tag:raise ValueError('unbalanced tag '+tag)
        depth=len(self.stack)
        if self.current and self.current[2]==depth:self.current=None
        if self.exdepth==depth:self.exdepth=0
        if self.soldepth==depth:self.soldepth=0
        self.stack.pop()

    def handle_data(self,data):
        if self.current:
            kind,name,_=self.current;self.markers[kind][name]+=data


def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parent.parent
    counts={'comparisons':0,'domain_rejections':0}
    def eq(got,want,name):
        counts['comparisons']+=1
        if got!=want:raise ValueError(f'{name}: {got!r} != {want!r}')
    def req(ok,name):eq(bool(ok),True,name)
    def reject(fn,name):
        try:fn()
        except ValueError:counts['domain_rejections']+=1
        else:raise ValueError('invalid case accepted: '+name)
    raw={name:(root/name).read_bytes() for name in FILES}
    page=Page();page.feed(raw[FILES[0]].decode());page.close()
    eq(page.stack,[],'balanced HTML');eq(page.duplicates,[],'unique reader IDs')
    eq(page.examples,[f'v13-c12-w{i}' for i in range(1,7)],'six shared-reader worked articles')
    eq(page.prompts,[f'v13-c12-e{i}' for i in range(1,13)],'all exact prompts')
    eq(page.answers,page.prompts,'all exact paired solutions')
    req({'v13-c12-claims','v13-c12-welfare','v13-c12-global','v13-c12-selection',
         'v13-c12-approximation','v13-c12-identification','v13-c12-referee','v13-c12-teach'}<=page.ids,
        'proof and instruction sections')
    sources=json.loads(raw[FILES[2]])
    eq({s['id']:s['url'] for s in sources['sources']},page.sources,'source identities/URLs')
    for s in sources['sources']:
        req(bool(s.get('actual_reading',s.get('inherited_used_scope'))) and bool(s['limits']),
            'honest scoped source route')
    inputs={'w1-resource':12,'w1-scale':4,'w2-coefficients':(96,-84,28,-3),
            'w2-concave-candidate':F(23,6),'w3-benefit-cost':(3,1),'w3-subsidy':F(1,2),
            'w4-theta':F(7,4),'w4-candidate':F(3,5),'w4-new-theta':F(51,25),'w4-claimed-error':F(1,100),
            'w5-slopes':(2,4),'w5-funds':(20,10),'w5-tax':1,
            'w6-benefit-costs':'(b,c₁,c₂)=(3,1,2)','w6-policy':'(K,s₁,s₂)=(1,1/2,1/2)',
            'w6-robust-grant':(F(11,8),0),'e1-weights':(F(1,4),F(3,4),F(1,14),F(13,14)),
            'e2-scale':100,'e3-cap':'[0,3]','e4-errors':'(ε,η)=(3/4,1/2)',
            'e5-cost':F(3,2),'e6-probability':F(1,4),'e7-theta':F(15,16),
            'e9-tax':F(1,2),'e10-error':F(1,6),'e11-budget':F(3,2)}
    eq(set(inputs),set(page.markers['data-input']),'all primitive markers')
    for key,value in inputs.items():eq(norm(page.markers['data-input'][key]),norm(fmt(value)),'primitive '+key)
    out={}
    out['w1-equal']=weights(12,F(1,2));out['w1-scaled']=weights(12,F(4,5))
    out['w1-weight-boundaries']=(F(1,14),F(13,14));out['w1-sensitivity']=14
    c5=capacity(5);c3=capacity(3)
    out['w2-critical']=(1,2,4)
    out['w2-curvatures']=tuple(poly(derivative(derivative(COEF)),F(x)) for x in (1,2,4))
    out['w2-values']=c5[1];out['w2-regret']=c5[3]-poly(COEF,F(1))
    out['w2-concave-loss']=3*(F(23,6)-4)**2
    half=(F(1,2),F(1,2));zeros=(F(0),F(0));ones=(F(1),F(1))
    h0=equilibria(3,(1,1),zeros,0);h=equilibria(3,(1,1),half,1)
    p0=h0['points'][-1];p=h['points'][-1]
    mixed=joint_accounts(3,(1,1),half,1,independent_law(p))
    full=joint_accounts(3,(1,1),half,1,independent_law(ones))
    out['w3-mix-zero']=p0;out['w3-mix-half']=p
    out['w3-mixed-welfare']=mixed['welfare'];out['w3-mixed-spending']=mixed['spending']
    out['w3-full-accounts']=(sum(full['utilities']),full['spending'],full['welfare'])
    theta=F(7,4);candidate=F(3,5);roots=exact_roots(theta);r=abs(candidate-transition(theta,candidate))
    out['w4-roots']=roots;out['w4-iterates']=(transition(theta,0),transition(theta,transition(theta,0)))
    out['w4-error']=(r,2*r,abs(candidate-roots[0]))
    newtheta=F(51,25);newfixed=exact_roots(newtheta)[0]
    out['w4-new-fixed']=newfixed;out['w4-sensitivity']=(newtheta-theta,(newfixed-roots[0])/(newtheta-theta))
    out['w4-local-derivative']=1/(4-2*roots[0]);out['w4-false-distance-bound']=4*F(1,100)
    out['w4-minimum-numerical-residual']=r-F(1,100)
    out['w5-baseline-states']=tuple((z,market('A',z,0)['ps'],market('A',z,0)['q']) for z in (-1,1))
    base=[market(m,z,0) for m,z in product(('A','B'),(-1,1))]
    out['w5-resource-bounds']=(max(row['payment'] for row in base),max(row['cost'] for row in base))
    means=[market_means(m,1) for m in ('A','B')]
    for i,key in enumerate(('quantities','seller-prices','buyer-prices','revenue')):
        out['w5-mean-'+key]=tuple(row[i] for row in means)
    out['w5-real-losses']=tuple(row[4] for row in means)
    out['w5-baseline-welfare']=tuple(sum(market(m,z,0)['welfare0'] for z in (-1,1))/2 for m in ('A','B'))
    f=equilibria(3,(1,2),half,1);f0=equilibria(3,(1,2),zeros,0)
    fm=joint_accounts(3,(1,2),half,1,independent_law(f['points'][-1]));ff=joint_accounts(3,(1,2),half,1,independent_law(ones))
    out['w6-fair-mix']=f['points'][-1];out['w6-zero-mix']=f0['points'][-1]
    out['w6-full-utilities']=ff['utilities'];out['w6-full-surplus']=ff['welfare']
    out['w6-mixed-accounts']=(fm['spending'],fm['welfare']);out['w6-budget-condition']='K>'+str(min(1,2))
    boundary=equilibria(3,(1,2),(1,0),1)
    out['w6-boundary-limit']=boundary['segments'][0][-1]
    cost_lo=(F(3,4),F(7,4));cost_hi=(F(5,4),F(9,4))
    out['w6-robust-infimum']=min(cost_hi)
    out['w6-robust-welfare']='['+str(6-sum(cost_hi))+','+str(6-sum(cost_lo))+']'
    out['e1-allocations']=tuple(weights(12,w) for w in inputs['e1-weights'])
    match=matching();match_scaled=matching(100)
    out['e2-feasible-count']=len(match[0]);out['e2-original-totals']=match[2];out['e2-scaled-totals']=match_scaled[2]
    out['e3-values']=c3[1];out['e3-regret']=c3[3]-poly(COEF,F(1));out['e3-endpoint-derivative']=poly(derivative(COEF),F(3))
    sharp=approximation((0,2),(F(3,4),F(5,4)),0,F(1,2));out['e4-sharp-regret']=sharp[3]
    newcosts=(F(3,2),F(3,2));e5=equilibria(3,newcosts,half,1);e50=equilibria(3,newcosts,zeros,0)
    e5m=joint_accounts(3,newcosts,half,1,independent_law(e5['points'][-1]));e5f=joint_accounts(3,newcosts,half,1,independent_law(ones))
    out['e5-mixed']=e5['points'][-1];out['e5-zero-mixed']=e50['points'][-1]
    out['e5-full-welfare']=e5f['welfare'];out['e5-mixed-welfare']=e5m['welfare']
    ce=joint_accounts(3,(1,1),half,1,(F(3,4),0,0,F(1,4)))
    out['e6-accounts']=(sum(ce['utilities']),ce['spending'],ce['welfare'])
    out['e6-independent-gain']=gain(3,(1,1),half,(F(1,4),F(1,4)))[0]
    e7roots=exact_roots(F(15,16));e7r=F(1,3)-transition(F(15,16),F(1,3))
    out['e7-roots']=e7roots;out['e7-residual']=e7r;out['e7-bound']=2*e7r
    out['e7-distance']=F(1,3)-e7roots[0];out['e7-derivative']=1/(4-2*e7roots[0])
    out['e8-minimum-residual']=r-F(1,100);out['e8-map-error']=(newtheta-theta)/4;out['e8-bound']=2*out['e8-map-error']
    out['e9-A']=market_means('A',F(1,2));out['e9-B']=market_means('B',F(1,2))
    critical=(3-F(8,3))/2;out['e10-critical-error']='ε<'+str(critical);out['e10-touch']=3-critical
    targeted=joint_accounts(3,(1,2),(F(5,4),0),F(3,2),independent_law(ones))
    out['e11-target-accounts']=(targeted['utilities'],targeted['spending'],targeted['welfare'])
    out['e11-equal-infimum']=2*min(1,2)
    equal=equilibria(3,(1,2),(F(3,4),F(3,4)),F(3,2));out['e11-equal-mix']=equal['points'][-1]
    out['e11-mixed-welfare']=joint_accounts(3,(1,2),(F(3,4),F(3,4)),F(3,2),independent_law(equal['points'][-1]))['welfare']
    fresh_c=(F(3,2),F(5,2));fresh_s=(F(3,4),F(3,4));fresh=equilibria(4,fresh_c,fresh_s,F(3,2))
    fresh_m=joint_accounts(4,fresh_c,fresh_s,F(3,2),independent_law(fresh['points'][-1]));fresh_f=joint_accounts(4,fresh_c,fresh_s,F(3,2),independent_law(ones))
    out['e12-mix']=fresh['points'][-1];out['e12-sponsor-loss']=fresh_m['spending'];out['e12-mixed-welfare']=fresh_m['welfare']
    out['e12-full-utilities']=fresh_f['utilities'];out['e12-full-welfare']=fresh_f['welfare'];out['e12-infimum']=min(fresh_c)
    eq(set(out),set(page.markers['data-calc']),'every printed result marker derived')
    for key,value in out.items():eq(norm(page.markers['data-calc'][key]),norm(fmt(value)),'result '+key)
    interventions=[]
    # Full derivative identities reduce the continuum comparison to root intervals.
    factored=tuple(-12*x for x in multiply(multiply((-1,1),(-2,1)),(-4,1)))
    eq(derivative(COEF),factored,'entire quartic derivative factorization')
    eq(c5[2],(F(4),),'unique full-domain optimum')
    eq(c3[2],(F(3),),'changed-capacity unique boundary optimum')
    eq(capacity(2)[2],(F(1),),'tighter capacity changes global maximizer')
    req(poly(derivative(COEF),F(1))==0 and out['w2-regret']>0,'stationarity is not global accuracy')
    eq(sharp[:3],(F(3,4),F(1,2),F(2)),'sharp objective-error certificate')
    eq(sharp[2],sharp[3],'bound attained by two-point example')
    interventions.append('global optimum versus local curvature, changed feasible cap and sharp error certificate')
    # Endpoint derivative numerator signs prove the clipped regimes; inspect all breakpoints.
    for lam in (F(0),F(1,14),F(1,4),F(1,2),F(4,5),F(13,14),F(1)):
        x,y=weights(12,lam);numerator=14*lam-1-x
        eq(x+y,12,'full resource allocation')
        req((x==0 and numerator<=0) or (x==12 and numerator>=0) or (0<x<12 and numerator==0),
            'exact global weight-sign condition')
    eq(match[1],((0,1),(1,0)),'all and only stable matchings')
    eq(match_scaled[1],match[1],'positive scaling preserves every blocker comparison')
    req(match[2][0]<match[2][1] and match_scaled[2][0]>match_scaled[2][1],
        'ordinally identical matchings reverse cardinal welfare ranking')
    interventions.append('welfare-weight boundaries and representation-preserving matching reversal')
    # Actual equilibrium witnesses for each changed mechanism; all support regimes are explicit.
    game_cases=[(3,(1,1),zeros,0),(3,(1,1),half,1),(3,(1,1),(1,1),2),
                (3,(1,1),(F(9,8),F(9,8)),F(9,4)),
                (3,(1,2),half,1),(3,(1,2),(1,0),1),(3,(1,2),(0,2),2),
                (3,(1,2),(F(9,8),0),F(9,8)),
                (3,newcosts,half,1),(4,fresh_c,fresh_s,F(3,2))]
    segments_checked=0
    for b,c,s,cash in game_cases:
        sol=equilibria(b,c,s,cash)
        strict=any(F(si)>F(ci) for si,ci in zip(s,c))
        eq(sol=={'points':((F(1),F(1)),),'segments':()},strict,'strict grant iff unique full adoption')
        for profile in sol['points']:
            req(nash_witness(b,c,s,profile),'pure/interior support best replies')
            ledger=joint_accounts(b,c,s,cash,independent_law(profile))
            eq(sum(ledger['utilities'])-ledger['spending'],ledger['welfare'],'sponsor-inclusive transfer cancellation')
            req(ledger['cash']>=0,'funded expected sponsor account')
        for varying,fixed,lo,hi in sol['segments']:
            segments_checked+=1
            for point in (lo,hi):
                profile=[fixed,fixed];profile[varying]=point
                req(nash_witness(b,c,s,profile),'closed segment endpoint best replies')
            # Best-response gains are affine; their endpoint signs certify whole segment.
            endpoint=[fixed,fixed];endpoint[varying]=hi
            delta=gain(b,c,s,endpoint)
            eq(delta[1-varying],0,'other player indifferent at segment upper endpoint')
            outside=list(endpoint);outside[varying]=(hi+1)/2
            req(not nash_witness(b,c,s,outside),'above-segment point has a profitable deviation')
    eq(equilibria(3,(1,1),(1,1),2)['points'],((0,0),(1,1)),'homogeneous weak equality has two pure equilibria')
    eq(segments_checked,2,'both asymmetric equality orientations audited')
    interventions.append('all mixed support regimes, subsidy equality, asymmetric continuum and strict targeted grants')
    # CE uses a joint law; independent marginals do not preserve conditional gains.
    req(min(ce['obedience'])>=0,'all CE recommendation inequalities')
    indep=joint_accounts(3,(1,1),half,1,independent_law((F(1,4),F(1,4))))
    req(min(indep['obedience'])<0,'same marginals fail obedience under independent play')
    for degenerate in ((1,0,0,0),(0,0,0,1)):
        req(min(joint_accounts(3,(1,1),half,1,degenerate)['obedience'])>=0,
            'zero-probability recommendations use unnormalized inequalities')
    interventions.append('correlated recommendations versus equal independent marginals and unused messages')
    # Robust cost rectangle: worst-corner necessity plus strict own-cost margin.
    robust_grants=(F(11,8),F(0))
    for c in product((F(3,4),F(5,4)),(F(7,4),F(9,4))):
        eq(equilibria(3,c,robust_grants,F(3,2)),{'points':((F(1),F(1)),),'segments':()},
           'robust targeted grant at every rectangle corner')
        welfare=joint_accounts(3,c,robust_grants,F(3,2),independent_law(ones))['welfare']
        req(F(5,2)<=welfare<=F(7,2),'robust real-welfare range')
    eq(robust_grants[0]-max(cost_lo[0],cost_hi[0]),F(1,8),'uniform positive standalone incentive margin')
    req(bool(equilibria(3,cost_hi,(F(5,4),0),F(5,4))['segments']),
        'robust budget infimum is not attained at worst corner')
    interventions.append('robust cost rectangle, strict margin and unattained funding infimum')
    # Monotone-domain and contraction identity, plus rational fixed points/changed maps.
    eq(multiply((0,1),(0,1)),(0,0,1),'quadratic map primitive')
    for th in (F(0),F(15,16),theta,newtheta,F(3)):
        lo,hi=transition(th,0),transition(th,1)
        req(0<=lo<=hi<=1,'entire invariant interval from monotone endpoints')
        fixed=exact_roots(th)[0]
        eq(transition(th,fixed),fixed,'exact stationary solution')
        req(0<=fixed<=1,'stationary domain')
    for x,y in ((F(0),F(1)),(F(1,4),F(3,4)),(F(1),F(1))):
        eq(abs(transition(theta,x)-transition(theta,y)),abs(x-y)*(x+y)/4,'full difference factorization witness')
        req(abs(x-y)*(x+y)/4<=abs(x-y)/2,'declared contraction bound')
    eq(transition(newtheta,candidate),candidate,'valid changed-map fixed point')
    shifted=lambda x:transition(theta,x)+F(1,100)
    eq((shifted(0),shifted(1),abs(candidate-shifted(candidate))),
       (F(179,400),F(279,400),F(1,16)),
       'attainment of minimum computed residual by a valid uniformly shifted map')
    eq(error_certificate(theta,candidate,r,0),2*r,'valid combined error certificate')
    req(abs(newfixed-roots[0])<=abs(newtheta-theta)/2,'uniform parameter sensitivity')
    req(out['w4-local-derivative']<F(1,2),'local slope distinguished from uniform constant')
    interventions.append('invariant-map endpoints, true residual, changed model and incompatible error claims')
    # Statewise funded trade and welfare are reconstructed without using loss formulas.
    for m,z,tax in product(('A','B'),(-1,1),(F(0),F(1,2),F(1))):
        row=market(m,z,tax)
        eq(budget_responses(m,z,row['ps'],tax),(row['q'],row['q']**2),
           'actual cash-limited responses clear at computed equilibrium')
        eq(row['buyer_u']+row['producer_profit']+row['tax'],row['welfare'],'tax transfer cancels from real welfare')
        eq(row['buyer_cash']+row['producer_cash']+row['tax'],30-row['cost'],'cash consumed only in production')
        req(row['buyer_cash']>0 and 10-row['cost']>0,'strict ex-ante liquidity slack')
        eq(row['loss'],(F(1,2) if m=='A' else F(2,3))*tax*tax,'completed-square welfare loss')
        if tax==0:
            eq((row['ps'],row['q']),(2+z,4+2*z),'complete observable baseline law')
    eq(budget_responses('B',1,F(9,4),0),(F(80,9),F(81,4)),
       'off-equilibrium buyer cap binds before unconstrained spending of 81/4')
    eq(budget_responses('A',1,4,0)[1],40,
       'off-equilibrium producer cap excludes unfunded quantity eight and cost sixteen')
    for m,z,tax in product(('A','B'),(-1,1),(F(0),F(1))):
        demand,supply_squared=budget_responses(m,z,0,tax)
        req(demand>0 and supply_squared==0,'positive excess demand at zero seller price')
    intervals=prediction_intervals(F(1,6));eq(intervals[0][0],intervals[1][1],'prediction intervals touch')
    tight=prediction_intervals(F(1,7));req(tight[1][1]<tight[0][0],'smaller error separates model predictions')
    wide=prediction_intervals(F(1,5));req(wide[1][1]>wide[0][0],'larger error gives overlapping predictions')
    interventions.append('observational equivalence, funded tax intervention and identification-error boundary')
    # Real invalid inputs and false certificates, executed under both Python modes.
    bad=[
        (lambda:number(True),'Boolean'),(lambda:number('1'),'numeric string'),
        (lambda:number(float('nan')),'NaN'),(lambda:number(float('inf')),'infinity'),
        (lambda:number(1+0j),'complex'),(lambda:weights(-1,F(1,2)),'negative resource'),
        (lambda:weights(12,-F(1,10)),'negative welfare weight'),(lambda:weights(12,F(11,10)),'weight above one'),
        (lambda:capacity(0),'empty positive-capacity domain'),(lambda:capacity(6),'outside quartic case domain'),
        (lambda:approximation((0,2),(0,),0,0),'unequal objective dimensions'),
        (lambda:approximation((),(),0,0),'empty objective domain'),
        (lambda:approximation((0,2),(0,2),True,0),'Boolean chosen index'),
        (lambda:approximation((0,2),(0,2),2,0),'outside chosen index'),
        (lambda:approximation((0,2),(0,2),0,-1),'negative solver tolerance'),
        (lambda:approximation(c5[1],c5[1],1,0),'local point falsely certified global'),
        (lambda:game(3,(0,1),zeros,0),'zero cost outside sharp theorem'),
        (lambda:game(3,(1,3),zeros,0),'cost reaches coordination benefit'),
        (lambda:game(3,(1,),zeros,0),'cost dimensions'),
        (lambda:game(3,(1,2),(-1,0),0),'negative grant'),
        (lambda:game(3,(1,2),half,F(9,10)),'unfunded grant promise'),
        (lambda:independent_law((F(3,2),0)),'invalid mixed probability'),
        (lambda:joint_accounts(3,(1,1),half,1,(F(1,2),0,0,0)),'missing joint probability mass'),
        (lambda:joint_accounts(3,(1,1),half,1,(-1,1,1,0)),'negative joint mass'),
        (lambda:joint_accounts(3,(1,1),half,1,(1,0,0)),'joint state dimension'),
        (lambda:transition(-1,F(1,2)),'negative model parameter'),
        (lambda:transition(4,F(1,2)),'non-invariant parameter'),
        (lambda:transition(theta,F(11,10)),'activity above one'),
        (lambda:transition(theta,-F(1,10)),'negative activity'),
        (lambda:error_certificate(theta,candidate,F(1,100),F(1,100)),'incompatible numerical/model bounds'),
        (lambda:error_certificate(theta,candidate,-1,1),'negative error tolerance'),
        (lambda:market('C',1,1),'unspecified structural law'),
        (lambda:market('A',0,1),'unmodeled state'),
        (lambda:market('A',1,F(3,2)),'tax outside proved range'),
        (lambda:market('A',1,-1),'negative tax outside policy class'),
        (lambda:market('A',1,0,buyer_cash=17),'unfunded buyer expenditure'),
        (lambda:market('A',1,0,producer_cash=8),'unfunded production'),
        (lambda:budget_responses('A',1,-1,0),'negative seller price outside funded market'),
        (lambda:prediction_intervals(-1),'negative measurement error'),
        (lambda:matching(0),'zero utility scale destroys strict preferences'),
        (lambda:matching(-1),'negative scale reverses rankings'),
    ]
    for fn,name in bad:reject(fn,name)
    author=json.loads(raw[FILES[3]])
    eq({a['path'] for a in author['payload_bindings']},set(FILES[:3]),'exact three nonself bindings')
    for a in author['payload_bindings']:
        payload=raw[a['path']]
        eq(len(payload),a['bytes'],'bound bytes '+a['path'])
        eq(sha256(payload).hexdigest(),a['sha256'],'bound hash '+a['path'])
    eq(author['unresolved_findings'],[],'no open author issue')
    summary={'chapter':'v13-c12','status':'passed',**counts,'worked_cases':6,'solved_exercises':12,
             'primitive_markers':len(inputs),'result_markers':len(out),'intervention_groups':len(interventions),
             'interventions':interventions,'feasible_matchings':len(match[0]),'stable_matchings':len(match[1]),
             'asymmetric_boundary_segments':segments_checked,'runtime_files':4,
             'proof_scope':'Exact cases, global polynomial identities, finite support/account checks and manuscript proof review; no grid or fitted model is treated as a universal proof.'}
    json.dumps(summary,allow_nan=False)
    return summary


if __name__=='__main__':
    check()
