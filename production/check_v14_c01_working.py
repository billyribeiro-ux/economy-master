"""Quiet, read-only four-file audit of original finite dynamic-programming cases.

Exact finite algebra and numerical witnesses corroborate the printed proofs.
They do not prove general measurable selection or unbounded-value contraction.
"""
import ast
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from itertools import product
import json
from math import isfinite, log, sqrt
from pathlib import Path

FILES = ('production/v14-c01-working.html',
         'production/check_v14_c01_working.py',
         'production/v14-c01-sources-working.json',
         'production/v14-c01-author-review-working.json')


def number(x):
    if isinstance(x, bool) or not isinstance(x, (int, float, F)):
        raise ValueError('finite real scalar required')
    if isinstance(x, float) and not isfinite(x):
        raise ValueError('finite real scalar required')
    return F(x)


def vector(x, size=None):
    if not isinstance(x, (tuple, list)) or not x or (size is not None and len(x) != size):
        raise ValueError('nonempty vector with matching dimension required')
    return tuple(number(y) for y in x)


def discount(beta):
    beta = number(beta)
    if not 0 < beta < 1:
        raise ValueError('strict discounted domain')
    return beta


def parse_number(text):
    """Restricted visible rational/tuple parser; never eval arbitrary manuscript."""
    if '=' in text:
        text = text.split('=', 1)[1]
    node = ast.parse(text.replace('−', '-').strip(), mode='eval').body
    def read(n):
        if isinstance(n, ast.Constant):
            return number(n.value)
        if isinstance(n, (ast.Tuple, ast.List)):
            return tuple(read(x) for x in n.elts)
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.USub, ast.UAdd)):
            return -read(n.operand) if isinstance(n.op, ast.USub) else read(n.operand)
        if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Div):
            return read(n.left) / read(n.right)
        raise ValueError('only visible rational constants and tuples are supported')
    return read(node)


class Document(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.ids = []
        self.exercises = []
        self.solutions = []
        self.worked = []
        self.sources = []
        self.links = []
        self.markers = {'data-input': {}, 'data-calc': {}, 'data-formula': {}}
        self.text = []

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if 'id' in d:
            self.ids.append(d['id'])
        if 'worked' in d.get('class', '').split():
            self.worked.append(d.get('id'))
        if tag == 'li' and any(t == 'ol' and 'exercises' in a.get('class', '').split() for t,a in self.stack):
            self.exercises.append(d.get('id'))
        if 'data-solution-for' in d:
            if not any(t == 'details' and 'solutions' in a.get('class', '').split() for t,a in self.stack):
                raise ValueError('solution outside disclosure')
            self.solutions.append(d['data-solution-for'])
        if 'data-source' in d:
            self.sources.append((d['data-source'], d.get('href')))
        if 'href' in d:
            self.links.append(d['href'])
        for marker in self.markers:
            if marker in d:
                key = d[marker]
                if key in self.markers[marker]:
                    raise ValueError('duplicate numerical marker')
                self.markers[marker][key] = ''
        if tag not in ('br', 'hr', 'img', 'meta', 'link', 'input'):
            self.stack.append((tag, d))

    def handle_endtag(self, tag):
        if not self.stack or self.stack[-1][0] != tag:
            raise ValueError('unbalanced HTML tag: '+tag)
        self.stack.pop()

    def handle_data(self, data):
        self.text.append(data)
        for _, attrs in self.stack:
            for marker in self.markers:
                if marker in attrs:
                    self.markers[marker][attrs[marker]] += data


def model(rewards, transitions, beta):
    beta = discount(beta)
    if not isinstance(rewards, (tuple, list)) or not rewards or len(rewards) != len(transitions):
        raise ValueError('matching nonempty state sets required')
    n = len(rewards)
    r = tuple(vector(row) for row in rewards)
    p = []
    for row, reward in zip(transitions, r):
        if len(row) != len(reward):
            raise ValueError('action dimensions disagree')
        rows = tuple(vector(t, n) for t in row)
        if any(min(t) < 0 or sum(t) != 1 for t in rows):
            raise ValueError('transition row must be a probability law')
        p.append(rows)
    return r, tuple(p), beta


def action_values(m, v):
    r,p,b = m
    v = vector(v, len(r))
    return tuple(tuple(reward+b*sum(q*x for q,x in zip(row,v))
                       for reward,row in zip(rs,ps)) for rs,ps in zip(r,p))


def bellman(m, v):
    return tuple(max(row) for row in action_values(m,v))


def norm(v):
    return max(abs(x) for x in v)


def difference(v, w):
    if len(v) != len(w):
        raise ValueError('difference dimensions')
    return tuple(x-y for x,y in zip(v,w))


def policy(m, sigma):
    r,p,b = m
    if not isinstance(sigma, (tuple, list)) or len(sigma) != len(r):
        raise ValueError('policy state dimension')
    if any(isinstance(a,bool) or not isinstance(a,int) or not 0 <= a < len(r[s]) for s,a in enumerate(sigma)):
        raise ValueError('policy action unavailable')
    return tuple(r[s][a] for s,a in enumerate(sigma)), tuple(p[s][a] for s,a in enumerate(sigma)), b


def solve(matrix, rhs):
    n = len(rhs)
    if len(matrix) != n or not n:
        raise ValueError('square nonempty linear system required')
    a = [list(vector(row,n))+[number(y)] for row,y in zip(matrix,rhs)]
    for j in range(n):
        pivot = next((i for i in range(j,n) if a[i][j]), None)
        if pivot is None:
            raise ValueError('singular linear system')
        a[j],a[pivot] = a[pivot],a[j]
        d = a[j][j]
        a[j] = [x/d for x in a[j]]
        for i in range(n):
            if i != j:
                q = a[i][j]
                a[i] = [x-q*y for x,y in zip(a[i],a[j])]
    return tuple(row[-1] for row in a)


def evaluate(m, sigma):
    r,p,b = policy(m,sigma)
    return solve(tuple(tuple(F(i==j)-b*q for j,q in enumerate(row)) for i,row in enumerate(p)),r)


def policy_step(m, v, incumbent):
    policy(m,incumbent)
    q = action_values(m,v)
    return tuple(old if row[old] == max(row) else row.index(max(row)) for row,old in zip(q,incumbent))


def policy_iteration(m, initial):
    current = tuple(initial)
    seen = []
    while current not in seen:
        seen.append(current)
        v = evaluate(m,current)
        next_policy = policy_step(m,v,current)
        if current == next_policy:
            return current,v,tuple(seen)
        current = next_policy
    raise ValueError('exact policy improvement unexpectedly cycled')


def value_iteration(m, initial, tolerance, cap):
    tolerance = number(tolerance)
    if tolerance < 0 or isinstance(cap,bool) or not isinstance(cap,int) or cap < 1:
        raise ValueError('nonnegative tolerance and positive integer cap required')
    v = vector(initial,len(m[0]))
    for n in range(cap):
        w = bellman(m,v)
        bound = norm(difference(w,v))/(1-m[2])
        if bound <= tolerance:
            return {'value':v,'bound':bound,'index':n,'calls':n+1}
        v = w
    return None


def readiness(amounts, probability):
    cash,receipt,cold,warm = vector(amounts,4)
    probability = number(probability)
    if min(cash,receipt,cold,warm) < 0 or not 0 <= probability <= 1:
        raise ValueError('nonnegative funded amounts and probability required')
    optimal = tuple(max([cash]+([cash-cost+receipt] if cost <= cash else [])) for cost in (cold,warm))
    blind = max([cash]+([cash-max(cold,warm)+receipt] if max(cold,warm) <= cash else []))
    # The baseline blind set contains idle only; in general evaluate its expected payoff.
    if max(cold,warm) <= cash:
        blind = max(cash,cash-((1-probability)*cold+probability*warm)+receipt)
    return optimal, (1-probability)*optimal[0]+probability*optimal[1], blind


def growth(A, alpha, beta, k):
    A,alpha,k = number(A),number(alpha),number(k)
    beta = discount(beta)
    if A <= 0 or k <= 0 or not 0 < alpha < 1:
        raise ValueError('positive technology/capital and Cobb exponent in (0,1)')
    s = alpha*beta
    b = alpha/(1-s)
    a = (log(float((1-s)*A))+float(beta*b)*log(float(s*A)))/float(1-beta)
    resources = float(A)*float(k)**float(alpha)
    return {'share':s,'b':b,'a':a,'next':float(s)*resources,
            'consumption':float(1-s)*resources,'value':a+float(b)*log(float(k))}


def saving_domain(m,beta,R,incomes,probabilities):
    m,R = number(m),number(R)
    beta = discount(beta)
    y = vector(incomes)
    p = vector(probabilities,len(y))
    if m <= 0 or R <= 0 or min(y) <= 0 or min(p) < 0 or sum(p) != 1:
        raise ValueError('positive wealth/return/income and probability law required')
    return m,beta,R,y,p


def saving_derivative(a,m,beta,R,incomes,probabilities):
    m,beta,R,y,p = saving_domain(m,beta,R,incomes,probabilities)
    a = number(a)
    if not 0 <= a < m:
        raise ValueError('saving outside borrowing/positive-consumption domain')
    return -1/(m-a)+beta*R*sum(q/(R*a+z) for q,z in zip(p,y))


def saving_optimum(m,beta,R,incomes,probabilities):
    m,beta,R,y,p = saving_domain(m,beta,R,incomes,probabilities)
    if saving_derivative(0,m,beta,R,y,p) <= 0:
        return 0.0
    lo,hi = F(0),m
    for _ in range(90):
        mid = (lo+hi)/2
        if saving_derivative(mid,m,beta,R,y,p) > 0:
            lo = mid
        else:
            hi = mid
    return float((lo+hi)/2)


def salvage(M,beta):
    M,beta = number(M),discount(beta)
    if M <= 0:
        raise ValueError('positive terminal resources required')
    x = max(F(0),(beta*M-1)/(1+beta))
    return x,M-x


def linear_path(C, initial=2, dates=5):
    C,initial = number(C),number(initial)
    if initial <= 0 or C <= 0 or C > initial or isinstance(dates,bool) or not isinstance(dates,int) or dates < 1:
        raise ValueError('infinite feasible constant-consumption domain')
    path = [initial]
    for _ in range(dates):
        path.append(2*path[-1]-C)
    return tuple(path)


def check(root=None):
    base = Path(root) if root is not None else Path(__file__).resolve().parents[1]
    raw = {name:(base/name).read_bytes() for name in FILES}
    counts = {'comparisons':0,'domain_rejections':0}
    def require(test,label):
        counts['comparisons'] += 1
        if not test:
            raise ValueError(label)
    def equal(actual,expected,label):
        require(actual == expected,label+': '+repr(actual)+' != '+repr(expected))
    def close(actual,expected,label,tol=2e-12):
        require(isfinite(float(actual)) and isfinite(float(expected)) and abs(float(actual)-float(expected)) <= tol*max(1,abs(float(expected))),label)
    def reject(fn,label):
        try:
            fn()
        except (ValueError,ZeroDivisionError):
            counts['domain_rejections'] += 1
        else:
            raise ValueError('accepted invalid domain: '+label)

    doc = Document()
    doc.feed(raw[FILES[0]].decode())
    require(not doc.stack,'all manuscript tags close')
    equal(len(set(doc.ids)),len(doc.ids),'unique IDs')
    require(all(x.startswith('v14-c01-') for x in doc.ids),'chapter-prefixed IDs')
    expected_exercises = ['v14-c01-e'+str(i) for i in range(1,13)]
    equal(doc.exercises,expected_exercises,'exact exercise order')
    equal(doc.solutions,expected_exercises,'exact disclosed solution pairing')
    equal(doc.worked,['v14-c01-w'+str(i) for i in range(1,7)],'six worked cases')
    require(all(h.startswith('https://') or ('/' not in h and h.endswith('.html')) for h in doc.links),'flat local/source routes')
    for phrase in ('Teach-back benchmark','Retention answers','Ten-point rubric','PolicyIteration','uncertified: iteration cap reached'):
        require(phrase in ''.join(doc.text),'instruction/algorithm present: '+phrase)
    sources = json.loads(raw[FILES[2]])
    equal({x['id']:x['url'] for x in sources['proposals']},dict(doc.sources),'exact source IDs and URLs')
    require(len(doc.sources)==4,'exact four scoped sources')
    require('currently absent' in sources['resumption_evidence'],'historical source availability distinguished')
    ins = {k:parse_number(v) for k,v in doc.markers['data-input'].items()}
    out = {k:parse_number(v) for k,v in doc.markers['data-calc'].items()}
    formulas = doc.markers['data-formula']
    checked = set()
    def visible(key,value,approx=False):
        checked.add(key)
        (close if approx else equal)(out[key],value,'visible '+key)

    pair,observed,blind = readiness(ins['readiness-amounts'],ins['readiness-probability'])
    for key,value in zip(('readiness-cold','readiness-warm','readiness-observed','readiness-blind'),(*pair,observed,blind)):
        visible(key,value)
    r = ins['device-rewards']
    nexts = ins['device-next']
    require(all(q.denominator == 1 and 0 <= q < len(r) for row in nexts for q in row),'valid visible next-state indices')
    p = tuple(tuple(tuple(F(j==target) for j in range(len(r))) for target in row) for row in nexts)
    m = model(r,p,ins['device-beta'])
    b = m[2]
    allpol = tuple(product(*(range(len(row)) for row in r)))
    vals = {sig:evaluate(m,sig) for sig in allpol}
    for sig,value in vals.items():
        visible('device-policy'+''.join(map(str,sig)),value)
        rr,pp,bb = policy(m,sig)
        equal(tuple(rr[s]+bb*sum(q*x for q,x in zip(pp[s],value)) for s in range(len(r))),value,'policy linear equation')
    optimal,vstar,trace = policy_iteration(m,(0,0))
    equal((optimal,trace),((1,1),((0,0),(1,1))),'exact tie-preserving PI trace')
    equal(bellman(m,vstar),vstar,'optimal fixed point')
    v = (F(0),F(0))
    iterates = [v]
    for n in range(1,16):
        v = bellman(m,v)
        iterates.append(v)
        if n <= 3:
            visible('device-v'+str(n),v)
        if n >= 2:
            equal(v,tuple(x-3*b**(n-2) for x in vstar),'full printed VI recurrence')
            equal(norm(difference(bellman(m,v),v))/(1-b),norm(difference(vstar,v)),'attained residual certificate')
    visible('device-residual2',norm(difference(iterates[3],iterates[2])))
    visible('device-error2',norm(difference(vstar,iterates[2])))
    switch = F(2,3)
    visible('device-beta-switch',switch)
    tied = model(r,p,switch)
    visible('device-tie-value',evaluate(tied,(0,0)))
    equal(formulas['device-vi'],'v_n=(5,8)−3(3/4)^(n−2)(1,1).','visible full VI formula')
    # Every stationary policy, both optimal action gaps, and exact equality.
    for beta in (F(1,4),F(1,2),switch,F(3,4),F(9,10)):
        mm = model(r,p,beta)
        candidates = {sig:evaluate(mm,sig) for sig in allpol}
        vmax = tuple(max(v[s] for v in candidates.values()) for s in range(2))
        winners = {sig for sig,v in candidates.items() if v == vmax}
        expected = set(allpol) if beta == switch else {(0,0) if beta < switch else (1,1)}
        equal(winners,expected,'complete discount-dependent policy set')
        q = action_values(mm,vmax)
        gap = abs(2-3*beta)
        for row in q:
            equal(max(row)-min(row),gap,'both state action gaps')
        for sig in winners:
            equal(policy_step(mm,vmax,sig),sig,'tie retention preserves any optimal incumbent')
    success = ins['e3-repair-success']
    def repair_model(prob):
        prob = number(prob)
        if not 0 <= prob <= 1:
            raise ValueError('repair success probability domain')
        pp = ((p[0][0],(1-prob,prob)),p[1])
        return model(r,pp,b)
    risky = repair_model(success)
    rp,rv,_ = policy_iteration(risky,(0,0))
    visible('e3-value',rv)
    q = action_values(risky,rv)
    visible('e3-gaps',tuple(row[1]-row[0] for row in q))
    equal(rp,(1,1),'risky optimum')
    for prob in (F(0),F(1,2),switch,success,F(1)):
        mm = repair_model(prob)
        candidates = {sig:evaluate(mm,sig) for sig in allpol}
        vmax = tuple(max(v[s] for v in candidates.values()) for s in range(2))
        expected = {(0,1)} if prob < switch else ({(0,1),(1,1)} if prob == switch else {(1,1)})
        equal({sig for sig,v in candidates.items() if v == vmax},expected,'risky threshold complete policies')
        if prob >= switch:
            equal(vmax,((24*prob-4)/(1+3*prob),F(8)),'risky value formula')
    cert = value_iteration(m,(0,0),ins['e5-tolerance'],15)
    require(cert is not None,'VI valid cap certifies')
    visible('e5-first-index',cert['index'])
    equal(cert['calls'],15,'VI returns residual origin after fifteen Bellman calls')
    require(value_iteration(m,(0,0),ins['e5-tolerance'],14) is None,'iteration cap cannot masquerade as convergence')
    for n in (13,14):
        visible('e5-error'+str(n),norm(difference(vstar,iterates[n])))
    require(norm(difference(vstar,iterates[13])) > ins['e5-tolerance'] >= cert['bound'],'first certified index')
    # Verify nontrivial approximate-greedy and policy-evaluation bounds.
    for v in ((F(0),F(0)),(F(2),F(5)),(F(100),F(-20))):
        delta = norm(difference(bellman(m,v),v))
        require(norm(difference(vstar,v)) <= delta/(1-b),'true value residual certificate')
        for sig in allpol:
            q = action_values(m,v)
            ts = tuple(row[a] for row,a in zip(q,sig))
            eta = max(max(row)-row[a] for row,a in zip(q,sig))
            own_resid = norm(difference(ts,v))
            require(norm(difference(v,vals[sig])) <= own_resid/(1-b),'fixed-policy evaluation certificate')
            require(norm(difference(vstar,vals[sig])) <= (2*delta+eta)/(1-b),'eta-greedy policy certificate')
    offset = ins['operator-offset']
    vf = tuple(x+offset/(1-b) for x in vstar)
    visible('offset-fixed',vf)
    equal(tuple(x+offset for x in bellman(m,vf)),vf,'approximate operator fixed point')
    visible('offset-residual',norm(difference(bellman(m,vf),vf)))
    visible('offset-error',norm(difference(vstar,vf)))
    equal(policy_step(m,vf,(0,0)),optimal,'common offset leaves action rankings')
    omitted = model((ins['omitted-rewards'],),(((1,),(1,)),),b)
    visible('omitted-true-value',evaluate(omitted,(1,))[0])
    visible('omitted-true-residual',bellman(omitted,(0,))[0])
    equal(evaluate(omitted,(0,)),(F(0),),'omitted policy evaluation')

    A,alpha,beta,k0 = ins['growth-parameters']
    g = growth(A,alpha,beta,k0)
    visible('growth-share',g['share'])
    visible('growth-b',g['b'])
    first = out['growth-first']
    checked.add('growth-first')
    close(first[0],g['next'],'growth first next capital')
    close(first[1],g['consumption'],'growth first consumption')
    ks = float(g['share']*A)**(1/float(1-alpha))
    steady = growth(A,alpha,beta,ks)
    checked.add('growth-steady')
    close(out['growth-steady'][0],ks,'steady capital')
    close(out['growth-steady'][1],steady['consumption'],'steady consumption')
    visible('growth-value16',g['value'],True)
    nxt = growth(A,alpha,beta,g['next'])
    close(nxt['next'],3*sqrt(3)/4,'second next capital')
    close(nxt['consumption'],5*sqrt(3)/4,'second consumption')
    equal(g['b'],alpha*(1+beta*g['b']),'value coefficient identity')
    k = float(k0)
    util = 0.0
    for t in range(150):
        gt = growth(A,alpha,beta,k)
        gn = growth(A,alpha,beta,gt['next'])
        close(gt['consumption']+gt['next'],float(A)*k**float(alpha),'growth resource identity')
        close(1/gt['consumption'],float(beta*A*alpha)*gt['next']**float(alpha-1)/gn['consumption'],'growth Euler equality')
        close(float(beta)**t*gt['next']/gt['consumption'],float(beta)**t*float(g['share']/(1-g['share'])),'explicit shadow tail')
        close(gt['value'],log(gt['consumption'])+float(beta)*gn['value'],'constructed Bellman identity')
        util += float(beta)**t*log(gt['consumption'])
        k = gt['next']
    close(util,g['value'],'attained discounted candidate value')
    # Distinct technology/exponent/discount/capital cases check implemented domains,
    # not a grid offered as proof of the universal concavity/tail argument.
    for args in ((F(1,2),F(1,3),F(2,3),F(1,8)),(3,F(3,4),F(4,5),20)):
        ga = growth(*args)
        gn = growth(*args[:3],ga['next'])
        close(ga['value'],log(ga['consumption'])+float(args[2])*gn['value'],'changed growth Bellman identity')
        close(1/ga['consumption'],float(args[2]*args[0]*args[1])*ga['next']**float(args[1]-1)/gn['consumption'],'changed growth Euler')

    sb,sR,sy,sp = (ins[k] for k in ('saving-beta','saving-return','saving-incomes','saving-probabilities'))
    wealths = ins['saving-wealths']
    sides = (1/wealths[0],sb*sR*sum(q/y for q,y in zip(sp,sy)))
    visible('saving-corner-sides',sides)
    visible('saving-corner',F(saving_optimum(wealths[0],sb,sR,sy,sp)))
    threshold = 1/(sb*sR*sum(q/y for q,y in zip(sp,sy)))
    visible('saving-threshold',threshold)
    ar = saving_optimum(wealths[1],sb,sR,sy,sp)
    visible('saving-root-decimal',ar,True)
    equal(formulas['saving-root'],'(sqrt(385)−17)/12','visible radical formula')
    close(ar,(sqrt(385)-17)/12,'independent bisection matches radical')
    equal(formulas['e9-general-root'],'a*(m)=[2m−25+sqrt(4m²+20m+241)]/12.','visible general root')
    # Cleared derivative polynomial from the declared two-state law, ascending powers.
    for wealth in (F(1),F(2),threshold,F(4),F(10)):
        y1,y2 = sy
        p1,p2 = sp
        coefs = (sb*sR*wealth*(p1*y2+p2*y1)-y1*y2,
                 sb*sR*(wealth*sR-p1*y2-p2*y1)-sR*(y1+y2),
                 -sb*sR*sR-sR*sR)
        equal(tuple(-4*x for x in coefs),(16-5*wealth,25-2*wealth,F(6)),'cleared polynomial from economic primitives')
        opt = saving_optimum(wealth,sb,sR,sy,sp)
        if wealth <= threshold:
            equal(opt,0.0,'corner including derivative equality')
        else:
            formula = (2*float(wealth)-25+sqrt(float(4*wealth**2+20*wealth+241)))/12
            close(opt,formula,'general positive root')
            close(saving_derivative(opt,wealth,sb,sR,sy,sp),0,'interior saving derivative')
    mean = sum(y*q for y,q in zip(sy,sp))
    visible('e9-mean-threshold',mean/(sb*sR))
    equal(saving_optimum(wealths[1],sb,sR,(mean,),(1,)),0.0,'mean-income corner')
    for aa in (F(0),F(1,3),F(2)):
        require(sum(q/(sR*aa+y) for q,y in zip(sp,sy)) > 1/(sR*aa+mean),'strict marginal-utility Jensen witness')
    terminal = salvage(ins['e8-terminal-resources'],sb)
    visible('e8-terminal-choice',terminal)
    visible('e8-terminal-marginal',1/terminal[1])
    equal(1/terminal[1],sb/(1+terminal[0]),'terminal salvage marginal balance')
    for resources in (F(1),F(2),F(5),F(20)):
        x,c = salvage(resources,sb)
        d = -1/c+sb/(1+x)
        require((x==0 and d<=0) or (x>0 and d==0),'terminal endpoint/interior KKT')

    lb,lr,lk = ins['linear-parameters']
    equal(lb*lr,1,'linear log Euler constant-consumption restriction')
    visible('linear-bad-value',F(0))
    visible('linear-bad-tail',2*(lk-1))
    equal(formulas['linear-good-value'],'2log(2)','visible good value expression')
    for C in (F(1,2),F(1),F(2)):
        path = linear_path(C,lk,20)
        pv = F(0)
        for t,k in enumerate(path[:-1]):
            equal(path[t+1]+C,lr*k,'linear budget')
            equal(k,C+(lk-C)*2**t,'complete constant path formula')
            pv += C/lr**(t+1)
            equal(pv+path[t+1]/lr**(t+1),lk,'finite telescoping PV budget')
            equal(lb**t*path[t+1]/C,lb**t+2*(lk-C)/C,'exact tail decomposition')
    require(log(2)/(1-float(lb)) > log(1)/(1-float(lb)),'Euler counterexample utility ranking')
    # Contraction without attainment: exact epsilon policy values and first loss.
    for eps in (F(1,100),F(1),F(10)):
        d = min(F(1,2),eps*(1-b))
        a = 1-d
        require(0 <= a < 1,'epsilon policy feasible in open action domain')
        require(0 < (1-a)/(1-b) <= eps,'epsilon value guarantee')
    equal(1/(1-b),4,'open-domain fixed-point supremum')
    # Optimal stationarity at beta=2/3 need not imply physical convergence.
    cycling = [0]
    for _ in range(6):
        cycling.append(int(nexts[cycling[-1]][(1,0)[cycling[-1]]]))
    equal(cycling,[0,1,0,1,0,1,0],'optimal stationary cycling witness')

    bad = [
        (lambda:number(True),'Boolean'),(lambda:number(float('nan')),'NaN'),
        (lambda:number(float('inf')),'infinity'),(lambda:number('1'),'numeric string'),
        (lambda:discount(1),'undiscounted'),(lambda:discount(0),'excluded zero discount'),
        (lambda:discount(-1),'negative discount'),(lambda:vector((),0),'empty state vector'),
        (lambda:model(((1,),),(((F(1,2),),),),b),'missing probability mass'),
        (lambda:model(((1,),),(((-1,),),),b),'negative probability'),
        (lambda:model(((1,2),),(((1,),),),b),'action dimensions'),
        (lambda:model((),(),b),'empty model'),(lambda:bellman(m,(1,)),'value dimension'),
        (lambda:evaluate(m,(True,0)),'Boolean action'),(lambda:evaluate(m,(2,0)),'unavailable action'),
        (lambda:evaluate(m,(1,)),'policy dimension'),(lambda:solve(((0,),),(1,)),'singular system'),
        (lambda:solve(((1,),(2,)),(1,)),'excess linear-system row'),
        (lambda:value_iteration(m,(0,0),-1,15),'negative tolerance'),
        (lambda:value_iteration(m,(0,0),1,True),'Boolean cap'),
        (lambda:value_iteration(m,(0,0),1,0),'zero cap'),
        (lambda:readiness((-1,3,3,1),F(1,2)),'negative funded cash'),
        (lambda:readiness((2,3,3,1),2),'readiness probability'),
        (lambda:repair_model(-F(1,10)),'negative repair probability'),
        (lambda:repair_model(F(11,10)),'repair probability exceeds one'),
        (lambda:growth(0,F(1,2),b,1),'zero technology'),
        (lambda:growth(2,1,b,1),'outside Cobb exponent'),
        (lambda:growth(2,0,b,1),'zero Cobb exponent'),
        (lambda:growth(2,F(1,2),b,0),'zero log capital'),
        (lambda:saving_domain(0,sb,sR,sy,sp),'zero wealth'),
        (lambda:saving_domain(2,sb,0,sy,sp),'zero saving return'),
        (lambda:saving_domain(2,sb,sR,(0,4),sp),'zero income outside positive domain'),
        (lambda:saving_domain(2,sb,sR,sy,(1,1)),'unnormalized income probabilities'),
        (lambda:saving_domain(2,sb,sR,sy,(-1,2)),'negative income probability'),
        (lambda:saving_derivative(-1,2,sb,sR,sy,sp),'borrowing violation'),
        (lambda:saving_derivative(2,2,sb,sR,sy,sp),'zero consumption'),
        (lambda:salvage(0,sb),'zero terminal resources'),
        (lambda:linear_path(3),'eventually negative capital'),
        (lambda:linear_path(0),'zero log consumption'),
        (lambda:parse_number('__import__("os")'),'unsafe visible expression'),
    ]
    for fn,label in bad:
        reject(fn,label)
    equal(checked,set(out),'every visible result reconstructed')
    equal(len(ins),17,'all visible primitive markers inventoried')
    equal(len(formulas),4,'all visible formulas inventoried')
    author = json.loads(raw[FILES[3]])
    equal({a['path'] for a in author['payload_bindings']},set(FILES[:3]),'exact three nonself payload bindings')
    for binding in author['payload_bindings']:
        payload = raw[binding['path']]
        equal(len(payload),binding['bytes'],'bound bytes '+binding['path'])
        equal(sha256(payload).hexdigest(),binding['sha256'],'bound hash '+binding['path'])
    equal(set(author['exact_prompt_solution_audit']),set(expected_exercises),'author reviewed every exact prompt')
    equal(author['unresolved_findings'],[],'no unresolved author finding')
    summary = {'chapter':'v14-c01','status':'passed',**counts,
               'worked_cases':len(doc.worked),'solved_exercises':len(doc.exercises),
               'primitive_markers':len(ins),'result_markers':len(out),'formula_markers':len(formulas),
               'runtime_files':4,'policy_count':len(allpol),'first_certified_VI_index':cert['index'],
               'sensitivity_groups':9,
               'scope':'Exact finite policy/iteration/certificate/constraint algebra and independent numerical growth/saving witnesses; universal all-history, concavity and tail arguments require the recorded manuscript proof review.'}
    json.dumps(summary,allow_nan=False)
    return summary


if __name__ == '__main__':
    check()
