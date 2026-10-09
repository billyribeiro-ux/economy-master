"""Quiet, exact and portable checks for the original screening/signaling chapter.

Contiguous-face quadratic optimization, polynomial integration and a full
piecewise-linear signal-space audit independently reconstruct the contracts.
The finite computations supplement, rather than certify, the general proofs.
"""
from fractions import Fraction as F
from html.parser import HTMLParser
from itertools import product
from pathlib import Path
import hashlib
import json
import re

HTML = 'production/v13-c08-working.html'
SELF = 'production/check_v13_c08_working.py'
SOURCES = 'production/v13-c08-sources-working.json'
REVIEW = 'production/v13-c08-author-review-working.json'


def require(ok, message):
    if not ok:
        raise ValueError(message)


class Audit:
    def __init__(self):
        self.comparisons = 0
        self.rejections = 0
        self.interventions = 0

    def equal(self, got, want, name):
        require(got == want, name + ': ' + repr(got) + ' != ' + repr(want))
        self.comparisons += 1

    def true(self, got, name):
        self.equal(bool(got), True, name)

    def reject(self, call, name):
        try:
            call()
        except ValueError:
            self.rejections += 1
        else:
            raise ValueError('malformed domain accepted: ' + name)


def exact(x):
    require(type(x) in (int, F), 'bounded exact integer/Fraction, not bool or float')
    require(abs(x) <= 1000000, 'bounded witness arithmetic')
    return F(x)


def vector(xs, n=None):
    require(type(xs) in (tuple, list) and 1 <= len(xs) <= 8, 'bounded nonempty vector')
    require(n is None or len(xs) == n, 'vector length')
    return tuple(exact(x) for x in xs)


def law(xs, n=None, positive=False):
    xs = vector(xs, n)
    require(sum(xs) == 1 and min(xs) >= 0, 'probability mass')
    require(not positive or min(xs) > 0, 'strictly positive type probabilities')
    return xs


def finite_model(theta, f, cap=5, curvature=1):
    theta = vector(theta)
    require(len(theta) <= 6 and all(theta[i] < theta[i+1] for i in range(len(theta)-1)),
            'at most six strictly ordered finite witness types')
    f = law(f, len(theta), True)
    cap, curvature = exact(cap), exact(curvature)
    require(cap > 0 and curvature > 0, 'positive quality cap and quadratic curvature')
    return theta, f, cap, curvature


def virtual(m):
    th, f, _, _ = m
    return tuple(th[i]-(th[i+1]-th[i])*sum(f[i+1:])/f[i]
                 if i+1 < len(th) else th[i] for i in range(len(th)))


def finite_accounts(m, q, u=None):
    th, f, cap, curvature = m
    q = vector(q, len(th))
    require(0 <= min(q) and max(q) <= cap, 'quality bounds')
    require(all(q[i] <= q[i+1] for i in range(len(q)-1)), 'IC monotonicity')
    minimal = [F(0)]
    for i in range(1, len(q)):
        minimal.append(minimal[-1]+(th[i]-th[i-1])*q[i-1])
    u = tuple(minimal) if u is None else vector(u, len(q))
    t = tuple(th[i]*q[i]-u[i] for i in range(len(q)))
    gaps = tuple(tuple(u[i]-th[i]*q[j]+t[j] for j in range(len(q))) for i in range(len(q)))
    require(min(u) >= 0 and min(x for row in gaps for x in row) >= 0, 'all IC/IR')
    payment = sum(p*x for p, x in zip(f, t))
    cost = sum(p*curvature*x*x/2 for p, x in zip(f, q))
    rent = sum(p*x for p, x in zip(f, u))
    welfare = sum(p*(th[i]*q[i]-curvature*q[i]*q[i]/2) for i, p in enumerate(f))
    phi = virtual(m)
    d = tuple(u[i]-u[0]-minimal[i] for i in range(len(q)))
    virtual_profit = sum(f[i]*(phi[i]*q[i]-curvature*q[i]*q[i]/2) for i in range(len(q)))
    corrected = virtual_profit-u[0]-sum(f[i]*d[i] for i in range(len(q)))
    fbq = tuple(min(cap, max(F(0), x/curvature)) for x in th)
    first_best = sum(f[i]*(th[i]*fbq[i]-curvature*fbq[i]*fbq[i]/2) for i in range(len(q)))
    return {'q':q, 'u':u, 't':t, 'gaps':gaps, 'phi':phi,
            'payment':payment, 'cost':cost, 'profit':payment-cost,
            'rent':rent, 'welfare':welfare, 'first_best':first_best,
            'loss':first_best-welfare, 'corrected_virtual':corrected,
            'gradient':tuple(f[i]*(phi[i]-curvature*q[i]) for i in range(len(q))),
            'extra_rents':d}


def face_optimum(m):
    """Enumerate all contiguous equality blocks, not candidate quality grids.

    At an optimum each maximal constant block's common value is its weighted
    virtual-value average divided by curvature, clipped to the common bounds.
    Otherwise a small common movement of that block improves the objective.
    Thus one enumerated partition contains the unique optimum. The manuscript
    supplies the separate exact tangent certificate for its nonregular cases.
    """
    th, f, cap, curvature = m
    phi = virtual(m)
    candidates = {}
    for cuts in product((False, True), repeat=len(th)-1):
        ends = [0]+[i+1 for i, cut in enumerate(cuts) if cut]+[len(th)]
        q = []
        for lo, hi in zip(ends, ends[1:]):
            average = sum(f[i]*phi[i] for i in range(lo, hi))/(curvature*sum(f[lo:hi]))
            q.extend([min(cap, max(F(0), average))]*(hi-lo))
        if any(q[i] > q[i+1] for i in range(len(q)-1)):
            continue
        q = tuple(q)
        candidates[q] = sum(f[i]*(phi[i]*q[i]-curvature*q[i]*q[i]/2) for i in range(len(q)))
    require(bool(candidates), 'nonempty face candidates')
    value = max(candidates.values())
    winners = [q for q, v in candidates.items() if v == value]
    require(len(winners) == 1, 'strictly concave finite optimum')
    return winners[0], value, len(candidates)


def add(p, q):
    return tuple((p[i] if i < len(p) else F(0))+(q[i] if i < len(q) else F(0))
                 for i in range(max(len(p), len(q))))


def scale(p, a):
    return tuple(a*x for x in p)


def multiply(p, q):
    out = [F(0)]*(len(p)+len(q)-1)
    for i, a in enumerate(p):
        for j, b in enumerate(q):
            out[i+j] += a*b
    return tuple(out)


def integral(p, lo, hi):
    return sum(c*(hi**(i+1)-lo**(i+1))/F(i+1) for i, c in enumerate(p))


def at(p, x):
    return sum(c*x**i for i, c in enumerate(p))


def uniform_contract(a, b, cap=5, curvature=1):
    a, b, cap, curvature = map(exact, (a, b, cap, curvature))
    require(a < b and cap > 0 and curvature > 0, 'uniform interval/cap/curvature')
    points = sorted({a, b}|{z for z in (b/2, (b+curvature*cap)/2) if a < z < b})
    rows, carry = [], F(0)
    totals = {'payment':F(0), 'cost':F(0), 'rent':F(0)}
    for lo, hi in zip(points, points[1:]):
        phi_mid = lo+hi-b
        q = (F(0),) if phi_mid <= 0 else ((cap,) if phi_mid >= curvature*cap else (-b/curvature, 2/curvature))
        primitive = (F(0),)+tuple(c/F(i+1) for i, c in enumerate(q))
        u = add(primitive, (carry-at(primitive, lo),))
        t = add((F(0),)+q, scale(u, -1))
        c = scale(multiply(q, q), curvature/2)
        for name, poly in [('payment',t), ('cost',c), ('rent',u)]:
            totals[name] += integral(poly, lo, hi)/(b-a)
        carry = at(u, hi)
        rows.append((lo, hi, q, u, t))
    fbpoints = sorted({a, b}|{z for z in (F(0), curvature*cap) if a < z < b})
    first_best = F(0)
    for lo, hi in zip(fbpoints, fbpoints[1:]):
        mid = (lo+hi)/2
        q = (F(0),) if mid <= 0 else ((cap,) if mid >= curvature*cap else (F(0),1/curvature))
        surplus = add((F(0),)+q, scale(multiply(q,q),-curvature/2))
        first_best += integral(surplus,lo,hi)/(b-a)
    totals.update(profit=totals['payment']-totals['cost'], first_best=first_best)
    totals['welfare'] = totals['profit']+totals['rent']
    totals['loss'] = first_best-totals['welfare']
    totals['rows'] = tuple(rows)
    totals['bounds'] = (a,b)
    totals['curvature'] = curvature
    return totals


def uniform_at(c, theta):
    theta = exact(theta)
    a,b = c['bounds']
    require(a <= theta <= b, 'reported type in uniform support')
    for lo,hi,q,u,t in c['rows']:
        if lo <= theta <= hi:
            return at(q,theta), at(u,theta), at(t,theta)
    raise ValueError('missing segment')


def step_at(theta, pivot):
    theta, pivot = exact(theta), exact(pivot)
    require(1 <= theta <= 3 and 0 <= pivot <= 2, 'step support and jump selection')
    q = F(0) if theta < 2 else (F(2) if theta > 2 else pivot)
    u = 2*max(F(0),theta-2)
    return q,u,theta*q-u


def lottery(theta, q, probabilities, payment, cap=5, rejection=False):
    theta, q = vector(theta), vector(q)
    p = law(probabilities, len(q))
    payment, cap = exact(payment), exact(cap)
    require(cap > 0 and min(q) >= 0 and max(q) <= cap, 'lottery quality domain')
    require(type(rejection) is bool, 'rejection switch must be boolean')
    out = []
    for th in theta:
        # Weak acceptance at a zero payoff is an explicitly selected action.
        accepted = tuple(not rejection or th*x-payment >= 0 for x in q)
        receipts = sum(prob*payment*int(yes) for prob,yes in zip(p,accepted))
        cost = sum(prob*x*x/2*int(yes) for prob,x,yes in zip(p,q,accepted))
        u = sum(prob*(th*x-payment)*int(yes) for prob,x,yes in zip(p,q,accepted))
        out.append({'accept':accepted,'payment':receipts,'cost':cost,'profit':receipts-cost,'u':u})
    return tuple(out)


def symmetric_transfer_bound(exponent):
    """Uniform[1,3], q=0, symmetric +/-|theta-2|^-exponent transfers.

    The zero-probability center is set to zero. Integrating over the two sides
    with density 1/2 gives E|t|=integral_0^1 d^-exponent dd. Every report
    separately is integrable for every exponent, but the aggregate is finite
    only below one in this nonnegative-exponent family.
    """
    exponent=exact(exponent)
    require(0 <= exponent < 1, 'finite aggregate absolute transfer in this family')
    return 1/(1-exponent)


def signal_model(prior=F(1,3), kappa=0):
    prior, kappa = exact(prior), exact(kappa)
    require(0 < prior < 1 and kappa >= 0, 'positive type marginals and nonnegative productive parameter')
    return prior,kappa


def signal_payoff(m, s, mu, type_index):
    s, mu = exact(s), exact(mu)
    require(s >= 0 and 0 <= mu <= 1 and type(type_index) is int and type_index in (0,1), 'signal/posterior/type domain')
    return 2+3*mu+m[1]*s-(F(1) if type_index == 0 else F(1,3))*s


def signal_audit(m, kind, education, scheme='low'):
    """Check the entire half-line by affine intervals, singleton roots and tails.

    All roots where equilibrium dominance changes are added to the partition.
    No education grid is used. The assumed price function is built from the
    original output and private costs, not from the manuscript's intervals.
    """
    education = exact(education)
    require(kind in ('pool','separate') and scheme in ('low','boundary'), 'pure outcome/belief scheme')
    require(education >= 0 and (kind != 'separate' or education > 0), 'pure signal domain')
    require(scheme != 'boundary' or m[1] == F(1,3), 'boundary beliefs require zero high net cost')
    prior,kappa = m
    on = {education:prior} if kind == 'pool' else {F(0):F(0),education:F(1)}
    chosen = (education,education) if kind == 'pool' else (F(0),education)
    threshold = F(9,2)
    def posterior(s):
        return on[s] if s in on else (F(1) if scheme == 'boundary' and s > threshold else F(0))
    current = tuple(signal_payoff(m,chosen[i],posterior(chosen[i]),i) for i in (0,1))
    costs = (F(1),F(1,3))
    breaks = {F(0),education}
    if scheme == 'boundary':
        breaks.add(threshold)
    for i,cost in enumerate(costs):
        if cost != kappa:
            root = (5-current[i])/(cost-kappa)
            if root >= 0:
                breaks.add(root)
    breaks = sorted(breaks)
    pbe, refined, unbounded = True, True, False
    regions = []
    def dominated(s):
        return tuple(current[i] > signal_payoff(m,s,F(1),i) for i in (0,1))
    def restrictions(s,mu):
        d = dominated(s)
        return (mu == 1 if d == (True,False) else (mu == 0 if d == (False,True) else True))
    for s in breaks:
        mu = posterior(s)
        for i in (0,1):
            pbe = pbe and signal_payoff(m,s,mu,i) <= current[i]
        if s not in on:
            refined = refined and restrictions(s,mu)
        regions.append(('point',str(s),dominated(s)))
    for j,lo in enumerate(breaks):
        hi = breaks[j+1] if j+1 < len(breaks) else None
        mid = (lo+hi)/2 if hi is not None else lo+1
        # Midpoints are merely labels for affine regions whose supremum is exact.
        mu = posterior(mid)
        refined = refined and restrictions(mid,mu)
        for i,cost in enumerate(costs):
            slope = kappa-cost
            if hi is None and slope > 0:
                unbounded = True
                pbe = False
            else:
                end = hi if hi is not None and slope > 0 else lo
                supremum = signal_payoff(m,end,mu,i)
                pbe = pbe and supremum <= current[i]
        regions.append(('interval',str(lo),None if hi is None else str(hi),dominated(mid)))
    return {'pbe':pbe,'refined':pbe and refined,'belief_restrictions':refined,
            'u':current,'unbounded':unbounded,'regions':tuple(regions)}


def signal_accounts(prior, kappa, h):
    m = signal_model(prior,kappa)
    h = exact(h)
    require(h >= 0, 'nonnegative education')
    output = (1-prior)*2+prior*(5+kappa*h)
    cost = prior*h/3
    return {'wage':5+kappa*h,'net':signal_payoff(m,h,F(1),1),
            'output':output,'cost':cost,'welfare':output-cost}


def flat(x):
    if isinstance(x,(tuple,list)):
        return tuple(z for y in x for z in flat(y))
    return (F(x),)


class Page(HTMLParser):
    VOID = {'br','hr','img','meta','link','input','source','wbr'}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack=[]
        self.ids=set()
        self.prompts=[]
        self.solutions=[]
        self.worked=[]
        self.inputs={}
        self.calcs={}
        self.capture=[]
        self.citations=set()
        self.local_links=[]

    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        require(len(a)==len(attrs),'duplicate HTML attribute')
        classes=set(a.get('class','').split())
        ident=a.get('id')
        if ident:
            require(ident.startswith('v13-c08-') and ident not in self.ids,'unique namespaced id')
            self.ids.add(ident)
        if tag=='article' and 'worked' in classes:
            require(ident is not None,'worked id')
            self.worked.append(ident)
        if tag=='li' and any(t=='ol' and 'exercises' in cls for t,cls in self.stack):
            require(ident is not None,'scored exercise id')
            self.prompts.append(ident)
        if 'data-solution-for' in a:
            require(tag=='li' and any(t=='details' and 'solutions' in cls for t,cls in self.stack), 'standard solution disclosure')
            self.solutions.append(a['data-solution-for'])
        if 'data-source' in a:
            require(tag=='a' and a.get('href','').startswith('https://'),'source link')
            self.citations.add(a['data-source'])
        if tag=='a' and 'href' in a and not a['href'].startswith(('https://','#')):
            self.local_links.append(a['href'])
            require('/' not in a['href'] and a['href'].endswith('.html'),'flat chapter link')
        for attr,dest in [('data-input',self.inputs),('data-calc',self.calcs)]:
            if attr in a:
                key=a[attr]
                require(key not in dest,'unique numeric marker')
                dest[key]=''
                self.capture.append((len(self.stack),key,dest))
        if tag not in self.VOID:
            self.stack.append((tag,classes))

    def handle_endtag(self,tag):
        require(bool(self.stack) and self.stack[-1][0]==tag,'balanced HTML '+tag)
        self.stack.pop()
        self.capture=[x for x in self.capture if x[0] < len(self.stack)]

    def handle_data(self,data):
        for _,key,dest in self.capture:
            dest[key]+=data

    def finish(self):
        self.close()
        require(not self.stack and not self.capture,'complete HTML fragment')


def numbers(s):
    return tuple(F(x) for x in re.findall(r'[-+]?\d+(?:/\d+)?',s.replace('−','-')))


def strict_json(path):
    def pairs(items):
        result={}
        for k,v in items:
            require(k not in result,'duplicate JSON key')
            result[k]=v
        return result
    def invalid(x):
        raise ValueError('nonfinite JSON '+x)
    return json.loads(path.read_text(encoding='utf-8'),object_pairs_hook=pairs,parse_constant=invalid)


def binding(path):
    data=path.read_bytes()
    return {'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}


def computations(a):
    expected={}
    inputs={}
    def mark(name,value):
        require(name not in expected,'unique computed marker '+name)
        expected[name]=flat(value)
    def finite_run(prefix,m):
        q,value,count=face_optimum(m)
        z=finite_accounts(m,q)
        a.equal(z['profit'],value,prefix+' primitive profit versus virtual optimum')
        a.equal(z['corrected_virtual'],z['profit'],prefix+' complete rent identity')
        a.equal(z['profit']+z['rent'],z['welfare'],prefix+' welfare conservation')
        for i,row in enumerate(z['gaps']):
            for j,gap in enumerate(row):
                a.true(gap>=0,prefix+' exact IC '+str((i,j)))
        for i,u in enumerate(z['u']):
            a.true(u>=0,prefix+' IR '+str(i))
        # Order-polytope vertices are leading zeros followed by the cap.
        # Every ordered q is their convex combination with quality-increment weights.
        cap=m[2]
        tangent=max(sum(g*(v-x) for g,v,x in zip(z['gradient'],(F(0),)*k+(cap,)*(len(q)-k),q))
                    for k in range(len(q)+1))
        a.equal(tangent,F(0),prefix+' full-polytope tangent certificate')
        return z,count
    m1=finite_model((1,2,3),(F(1,2),F(1,4),F(1,4)))
    m2=finite_model((2,3,4),(F(1,2),F(1,10),F(2,5)))
    z1,n1=finite_run('finite1',m1)
    z2,n2=finite_run('finite2',m2)
    for prefix,z,names in [('finite1',z1,('phi','q','u','t','gaps','profit','rent','welfare','first_best','loss')),
                           ('finite2',z2,('phi','q','gradient','u','t','gaps','profit'))]:
        for name in names:
            mark(prefix+'-'+('fb' if name=='first_best' else name),z[name])
    inputs['finite1']=flat((m1[0],m1[1],m1[2]))
    inputs['finite2']=flat((m2[0],m2[1],m2[2]))
    e1m=finite_model((1,2,3),(F(1,4),F(1,4),F(1,2)))
    e1,n3=finite_run('prior transfer',e1m)
    for name in ('phi','q','u','t','profit','first_best','loss'):
        mark('e1-'+('fb' if name=='first_best' else name),e1[name])
    inputs['exercise1']=e1m[1]
    a.true(e1['q'][1]<z1['q'][1],'prior change increases exclusion')
    a.interventions+=1
    e2m=finite_model(m2[0],m2[1],1)
    e2,n4=finite_run('cap transfer',e2m)
    for name in ('q','t','profit','gradient'):
        mark('e2-'+name,e2[name])
    inputs['exercise2']=(F(1),)
    a.true(e2['profit']<z2['profit'],'binding cap reduces optimal profit')
    a.interventions+=1
    e3=finite_accounts(m1,z1['q'],(0,F(1,2),F(5,2)))
    off=tuple(e3['gaps'][i][j] for i in range(3) for j in range(3) if i!=j)
    a.true(min(off)>0,'strict reporting')
    a.equal(min(e3['u']),F(0),'participation remains weak')
    a.equal(e3['corrected_virtual'],e3['profit'],'nonminimal finite rents identity')
    mark('e3-t',e3['t']);mark('e3-gaps',off);mark('e3-profit',e3['profit'])
    mark('e3-loss',z1['profit']-e3['profit'])
    inputs['exercise3']=e3['u']
    shifted=finite_accounts(m1,z1['q'],tuple(x+F(1,4) for x in e3['u']))
    a.equal(shifted['gaps'],e3['gaps'],'common transfer preserves all report gaps')
    a.equal(shifted['profit'],e3['profit']-F(1,4),'funded utility transfer reduces profit equally')
    a.true(min(shifted['u'])>0,'common transfer gives strict IR')
    a.interventions+=1
    scaled_m=finite_model(m2[0],m2[1],5,2)
    scaled_q,scaled_value,_=face_optimum(scaled_m)
    a.equal(scaled_q,tuple(x/2 for x in z2['q']),'higher cost rescales bunched qualities')
    a.equal(scaled_value,z2['profit']/2,'higher cost rescales maximal value')
    a.interventions+=1

    c=uniform_contract(1,3)
    inputs['continuum']=(F(1),F(3),F(5))
    mark('continuum-at2',uniform_at(c,2));mark('continuum-at3',uniform_at(c,3))
    for name in ('payment','cost','profit','rent','welfare','first_best','loss'):
        mark('continuum-'+('fb' if name=='first_best' else name),c[name])
    def check_integrals(z,label):
        width=z['bounds'][1]-z['bounds'][0]
        direct=F(0)
        previous=F(0)
        for lo,hi,q,u,t in z['rows']:
            a.equal(at(u,lo),previous,label+' rent continuity')
            a.equal(at(u,hi)-at(u,lo),integral(q,lo,hi),label+' integrated allocation')
            a.equal(add((F(0),)+q,scale(u,-1)),t,label+' payment identity')
            previous=at(u,hi)
            direct+=integral(add((F(0),)+q,scale(multiply(q,q),-z['curvature']/2)),lo,hi)/width
        a.equal(direct,z['welfare'],label+' primitive social surplus')
    check_integrals(c,'continuum baseline')
    points=(F(1),F(3,2),F(2),F(3))
    for th in points:
        qi,ui,ti=uniform_at(c,th)
        for report in points:
            qj,uj,tj=uniform_at(c,report)
            a.true(ui>=th*qj-tj,'continuum boundary IC witness')
    # A null endpoint variation remains globally compatible with all interior types:
    # increasing top quality while fixing U(top) makes it less attractive below top.
    topq=F(5);topu=uniform_at(c,3)[1];topt=3*topq-topu
    a.equal(topu,F(9,4),'top rent retained')
    for th in points[:-1]:
        q,u,t=uniform_at(c,th)
        a.true(u>=th*topq-topt,'null endpoint does not attract lower witnesses')
        a.true(topu>=3*q-t,'top endpoint still chooses own report')
    a.interventions+=1
    inputs['exercise4']=flat((0,2,2,2,2,0,2))
    for pivot in (F(0),F(1),F(2)):
        points=(F(1),F(3,2),F(2),F(5,2),F(3))
        for th in points:
            _,u,_=step_at(th,pivot)
            for report in points:
                qj,_,tj=step_at(report,pivot)
                a.true(u>=th*qj-tj,'jump/all selected point IC witnesses')
        a.equal(step_at(2,pivot)[2],2*pivot,'jump-point payment')
    eps=F(1,10)
    left=(step_at(2,1)[1]-step_at(2-eps,1)[1])/eps
    right=(step_at(2+eps,1)[1]-step_at(2,1)[1])/eps
    a.equal((left,right),(F(0),F(2)),'distinct one-sided derivatives')
    # Integrate the two constant contracts; the singleton has zero mass.
    steppay=integral((F(4),),F(2),F(3))/2
    stepcost=integral((F(2),),F(2),F(3))/2
    mark('e4-at2',(2,2));mark('e4-payment',steppay);mark('e4-cost',stepcost);mark('e4-profit',steppay-stepcost)
    a.interventions+=1
    c5=uniform_contract(1,4)
    inputs['exercise5']=(F(1),F(4),F(5))
    mark('e5-threshold',F(4,2))
    mark('e5-accounts',tuple(c5[x] for x in ('payment','cost','profit','rent')))
    mark('e5-welfare',c5['welfare']);mark('e5-fb',c5['first_best']);mark('e5-loss',c5['loss'])
    check_integrals(c5,'continuum wider support')
    a.interventions+=1
    capped=uniform_contract(1,3,1)
    check_integrals(capped,'continuum quality cap')
    a.equal(capped['profit'],F(19,24),'new capped continuum profit')
    a.equal(uniform_at(capped,3)[0],F(1),'new capped continuum top')
    a.true(capped['profit']<c['profit'],'cap contracts continuum opportunity set')
    a.interventions+=1
    delta=F(1,4)
    mark('e12-profit',c['profit']-delta)
    inputs['exercise12']=(F(1),)
    for th in (F(1),F(3,2),F(5,2),F(3)):
        q,u,t=uniform_at(c,th)
        a.equal(th*q-(t-delta),u+delta,'continuum common transfer identity')
    a.interventions+=1

    lot=lottery((2,4),(0,4),(F(1,2),F(1,2)),3)
    det=lottery((2,4),(2,),(1,),3)
    inputs['lottery']=flat(((2,4),(0,4),(F(1,2),F(1,2)),3))
    mark('lottery-utilities',tuple(x['u'] for x in lot))
    a.equal(tuple(x['u'] for x in lot),tuple(x['u'] for x in det),'all interim utilities preserved')
    mark('lottery-quadratic',(det[0]['profit'],lot[0]['profit']))
    a.true(det[0]['profit']>lot[0]['profit'],'strict convex production cost')
    # Square-root costs are exact at lottery qualities 0 and 4. sqrt(2)>1
    # is certified by positivity and 2>1^2, without a rounded decimal oracle.
    sqr_lottery_cost=F(1,2)*0+F(1,2)*2
    mark('lottery-sqrt',F(3)-sqr_lottery_cost)
    a.true(F(2)>sqr_lottery_cost**2,'nonconvex fixed-contract comparison')
    mark('lottery-realized',F(2)*0-3)
    e6=lottery((2,4),(0,3),(F(1,3),F(2,3)),3)
    e6post=lottery((2,4),(0,3),(F(1,3),F(2,3)),3,rejection=True)
    inputs['exercise6']=flat((0,F(1,3),3,F(2,3),3))
    mark('e6-committed-u',tuple(x['u'] for x in e6));mark('e6-committed-profit',e6[0]['profit'])
    mark('e6-option-u',tuple(x['u'] for x in e6post))
    mark('e6-option-accounts',tuple(e6post[0][x] for x in ('payment','cost','profit')))
    a.equal(tuple(x['accept'] for x in e6post),((False,True),(False,True)),'actual post-realization acceptances')
    a.equal(e6post[0]['profit'],e6[0]['profit']-1,'rejection removes actual cash receipt')
    a.interventions+=1

    a.equal(symmetric_transfer_bound(0),F(1),'bounded continuum transfer')
    a.equal(symmetric_transfer_bound(F(1,2)),F(2),'integrable unbounded transfer family')
    # For exponent one, every right-side dyadic annulus contributes at least
    # 1/8 to the unconditional positive part: density 1/2, positive lottery
    # probability 1/2, width 2^(-k-1), and amount at least 2^k.
    for k in range(4):
        a.equal(F(1,2)*F(1,2)*F(1,2**(k+1))*2**k,F(1,8),
                'nonvanishing dyadic contribution to divergent positive tail')
    a.interventions+=1

    sbase=signal_model()
    inputs['signal-base']=(F(2),F(5),F(1,3))
    mark('signal-separation',(0,3,9));mark('signal-pooling',(0,1))
    # Endpoint constants below are reconstructed from actual two cross-action payoffs.
    low_threshold=(F(5)-2)/F(1); high_threshold=(F(5)-2)/F(1,3)
    a.equal((low_threshold,high_threshold),(F(3),F(9)),'primitive separating thresholds')
    region_count=0
    def sig(m,kind,h,scheme,pbe,refined,label):
        nonlocal region_count
        z=signal_audit(m,kind,h,scheme)
        a.equal((z['pbe'],z['refined']),(pbe,refined),label)
        region_count+=len(z['regions'])
        return z
    for h in (F(3),F(6),F(9)):
        sig(sbase,'separate',h,'low',True,h==3,'baseline full half-line separation')
    for h in (F(5,2),F(10)):
        sig(sbase,'separate',h,'low',False,False,'outside separating interval')
    for p in (F(0),F(1,2),F(1)):
        sig(sbase,'pool',p,'low',True,False,'pooling and refinement')
    sig(sbase,'pool',F(5,4),'low',False,False,'outside pooling interval')
    selected=signal_audit(sbase,'separate',3)
    mark('signal-net',selected['u'])
    baseaccount=signal_accounts(F(1,3),F(0),F(3))
    mark('signal-welfare',baseaccount['welfare'])
    a.equal(baseaccount['welfare'],F(2,3)*selected['u'][0]+F(1,3)*selected['u'][1],'wage/output/cost conservation')
    # Original general witness intervals are verified at a strict interior point;
    # the manuscript proves their nonempty open-interval scope for all outcomes.
    for p in (F(0),F(1)):
        current=signal_audit(sbase,'pool',p)['u']
        witness=p+4
        a.true(current[0]>signal_payoff(sbase,witness,1,0),'pool witness low dominated')
        a.true(current[1]<signal_payoff(sbase,witness,1,1),'pool witness high profitable')
    sprod=signal_model(kappa=F(1,6))
    aL,aH=1-sprod[1],F(1,3)-sprod[1]
    lower,upper=3/aL,3/aH
    inputs['productive']=(F(1,6),)
    mark('productive-separation',(lower,upper));mark('productive-pooling',(0,1/aL))
    for h in (lower,F(6),upper):
        sig(sprod,'separate',h,'low',True,h==lower,'productive full half-line')
    sig(sprod,'pool',1/aL,'low',True,False,'productive pooling endpoint')
    productive=signal_accounts(F(1,3),F(1,6),lower)
    for name in ('wage','net','output','cost','welfare'):
        mark('productive-'+name,productive[name])
    a.interventions+=1
    sbound=signal_model(kappa=F(1,3))
    mark('boundary-separation',F(3)/(1-F(1,3)))
    for h in (F(9,2),F(6),F(10)):
        sig(sbound,'separate',h,'low',True,False,'low beliefs violate boundary refinement')
        z=sig(sbound,'separate',h,'boundary',True,True,'H beliefs preserve boundary refined equilibrium')
        a.equal(z['u'],(F(2),F(5)),'boundary high is indifferent')
    sig(sbound,'separate',F(4),'boundary',False,False,'below boundary separating threshold')
    sig(sbound,'pool',F(3,2),'low',True,False,'boundary pooling endpoint eliminated')
    too_productive=signal_audit(signal_model(kappa=F(1,2)),'separate',6)
    a.true(too_productive['unbounded'] and not too_productive['pbe'],'unbounded high payoff tail')
    a.interventions+=1
    e7m=signal_model(prior=F(1,2))
    poolwage=2+3*e7m[0]
    inputs['exercise7']=(F(1,2),)
    mark('e7-wage',poolwage);mark('e7-pooling',(0,poolwage-2));mark('e7-separation',(low_threshold,high_threshold))
    sig(e7m,'pool',poolwage-2,'low',True,False,'new prior pooling endpoint')
    sig(e7m,'separate',low_threshold,'low',True,True,'new prior same least separation')
    mark('e7-welfare',signal_accounts(F(1,2),F(0),low_threshold)['welfare'])
    a.interventions+=1
    inputs['exercise8']=(F(4),)
    best4=tuple(signal_payoff(sbase,4,1,i) for i in (0,1))
    poolu=signal_audit(sbase,'pool',1)['u']
    excessu=signal_audit(sbase,'separate',6)['u']
    mark('e8-max',best4);mark('e8-pool-u',poolu);mark('e8-excess-u',excessu);mark('e8-gain',best4[1]-excessu[1])
    for current,want in [(poolu,(True,False)),(excessu,(True,False)),(selected['u'],(True,True))]:
        a.equal(tuple(current[i]>best4[i] for i in (0,1)),want,'proper versus all-dominated set')
    a.interventions+=1
    e9m=signal_model(kappa=F(1,4))
    e9net=(1-e9m[1],F(1,3)-e9m[1])
    e9lo,e9hi=tuple(3/x for x in e9net)
    inputs['exercise9']=(F(1,4),)
    mark('e9-netcosts',e9net);mark('e9-separation',(e9lo,e9hi));mark('e9-pooling',(0,1/e9net[0]))
    for h in (e9lo,e9hi):
        sig(e9m,'separate',h,'low',True,h==e9lo,'new productivity endpoints')
    e9account=signal_accounts(F(1,3),F(1,4),e9lo)
    for name in ('wage','net','output','cost','welfare'):
        mark('e9-'+name,e9account[name])
    a.interventions+=1
    inputs['exercise10']=(F(1,3),F(6))
    mark('e10-max5',tuple(signal_payoff(sbound,5,1,i) for i in (0,1)))
    mark('e10-wage5',F(5)+F(1,3)*5)
    mark('e10-max4',tuple(signal_payoff(sbound,4,1,i) for i in (0,1)))
    a.equal(signal_payoff(sbound,5,1,1),F(5),'strict dominance excludes equality')
    a.equal(signal_payoff(sbound,4,0,0),F(-2,3),'permitted boundary low posterior deters')

    # Actual malformed domain calls, each must raise ValueError under normal and -O.
    bad=[
        ('boolean type',lambda:finite_model((True,2),(F(1,2),F(1,2)))),
        ('floating type',lambda:finite_model((1.0,2),(F(1,2),F(1,2)))),
        ('nonfinite type',lambda:finite_model((float('nan'),2),(F(1,2),F(1,2)))),
        ('unordered types',lambda:finite_model((2,1),(F(1,2),F(1,2)))),
        ('duplicate types',lambda:finite_model((1,1),(F(1,2),F(1,2)))),
        ('missing probabilities',lambda:finite_model((1,2),(1,))),
        ('zero type mass',lambda:finite_model((1,2),(1,0))),
        ('negative type mass',lambda:finite_model((1,2),(2,-1))),
        ('wrong total mass',lambda:finite_model((1,2),(F(1,3),F(1,3)))),
        ('zero cap',lambda:finite_model((1,2),(F(1,2),F(1,2)),0)),
        ('zero curvature',lambda:finite_model((1,2),(F(1,2),F(1,2)),5,0)),
        ('negative quality',lambda:finite_accounts(m1,(-1,1,3))),
        ('over cap',lambda:finite_accounts(m1,(0,1,6))),
        ('nonmonotone quality',lambda:finite_accounts(m2,(1,0,4))),
        ('IR failure',lambda:finite_accounts(m1,(0,1,3),(-1,0,1))),
        ('IC failure',lambda:finite_accounts(m1,(0,1,3),(0,0,5))),
        ('reversed uniform',lambda:uniform_contract(3,1)),
        ('zero width',lambda:uniform_contract(1,1)),
        ('negative continuum cap',lambda:uniform_contract(1,3,-1)),
        ('outside continuum report',lambda:uniform_at(c,4)),
        ('invalid jump selection',lambda:step_at(2,3)),
        ('outside step type',lambda:step_at(0,1)),
        ('lottery mass error',lambda:lottery((2,4),(0,4),(F(1,3),F(1,3)),3)),
        ('lottery negative mass',lambda:lottery((2,4),(0,4),(-1,2),3)),
        ('lottery over cap',lambda:lottery((2,4),(0,6),(F(1,2),F(1,2)),3)),
        ('lottery date switch type',lambda:lottery((2,4),(0,4),(F(1,2),F(1,2)),3,rejection=1)),
        ('nonintegrable continuum payment',lambda:symmetric_transfer_bound(1)),
        ('stronger continuum payment singularity',lambda:symmetric_transfer_bound(F(3,2))),
        ('zero high prior',lambda:signal_model(prior=0)),
        ('zero low prior',lambda:signal_model(prior=1)),
        ('negative productivity scope',lambda:signal_model(kappa=-1)),
        ('negative signal',lambda:signal_payoff(sbase,-1,0,0)),
        ('invalid posterior',lambda:signal_payoff(sbase,1,2,0)),
        ('boolean type index',lambda:signal_payoff(sbase,1,0,True)),
        ('false separation at zero',lambda:signal_audit(sbase,'separate',0)),
        ('undefined mixed scope',lambda:signal_audit(sbase,'mixed',1)),
        ('wrong boundary regime',lambda:signal_audit(sbase,'separate',3,'boundary')),
    ]
    for name,call in bad:
        a.reject(call,name)
    return expected,inputs,{'finite_face_candidates':n1+n2+n3+n4,'signal_regions':region_count}


def check(root=None):
    root=Path(root).resolve() if root is not None else Path(__file__).resolve().parents[1]
    audit=Audit()
    paths=(HTML,SELF,SOURCES,REVIEW)
    before={p:binding(root/p) for p in paths}
    text=(root/HTML).read_text(encoding='utf-8')
    page=Page();page.feed(text);page.finish()
    audit.equal(page.worked,['v13-c08-case'+str(i) for i in range(1,7)],'all six substantial cases')
    audit.equal(page.prompts,['v13-c08-e'+str(i) for i in range(1,13)],'twelve exact prompts')
    audit.equal(page.solutions,page.prompts,'one ordered solution per prompt')
    for ident in ('finite','continuum','lotteries','signaling','productive','workflow','exercises','teach'):
        audit.true('v13-c08-'+ident in page.ids,'proof/teaching section '+ident)
    audit.true('v13-c09.html' in page.local_links,'correct hidden-action successor')
    expected,inputs,counts=computations(audit)
    audit.equal(set(page.calcs),set(expected),'complete computed marker set')
    audit.equal(set(page.inputs),set(inputs),'complete original input marker set')
    for key,value in expected.items():
        audit.equal(numbers(page.calcs[key]),value,'printed value '+key)
    for key,value in inputs.items():
        audit.equal(numbers(page.inputs[key]),value,'printed primitive '+key)
    sources=strict_json(root/SOURCES)
    audit.equal(sources['chapter'],'v13-c08','source chapter')
    ids={s['id'] for s in sources['sources']}
    audit.equal(ids,{'v13-c06-manea-noncoop2017','v13-c08-holmstrom-screening2016'},'narrow primary source identities')
    audit.equal(page.citations,ids,'all cited source scopes recorded')
    for s in sources['sources']:
        audit.true(bool(s['actual_body_scope']) and bool(s['limits']) and bool(s['images_inspected']),'honest source inspection record')
        b=s['primary_body_binding']
        audit.true(type(b['bytes']) is int and b['bytes']>0 and re.fullmatch('[0-9a-f]{64}',b['sha256']) is not None,'provenance binding format only')
    review=strict_json(root/REVIEW)
    audit.equal(review['chapter'],'v13-c08','author review chapter')
    declared=review['payload_bindings']
    audit.equal(len(declared),3,'three nonself binding records')
    binds={item['path']:{'bytes':item['bytes'],'sha256':item['sha256']} for item in declared}
    audit.equal(set(binds),{HTML,SELF,SOURCES},'three distinct nonself author paths')
    for p in (HTML,SELF,SOURCES):
        audit.equal(binds[p],before[p],'exact author payload '+p)
    audit.equal({p:binding(root/p) for p in paths},before,'no runtime file mutation')
    result={'chapter':'v13-c08','status':'passed','comparisons':audit.comparisons,
            'actual_domain_rejections':audit.rejections,'interventions':audit.interventions,
            'worked_cases':len(page.worked),'solved_exercises':len(page.solutions),
            'numeric_markers':len(page.calcs),'input_markers':len(page.inputs),
            **counts,
            'scope':'Exact original finite, polynomial and full affine-region witnesses; general proofs separately read. No all-mixed signaling or universal implementation claim.'}
    json.dumps(result,allow_nan=False,sort_keys=True)
    return result


if __name__=='__main__':
    check()
