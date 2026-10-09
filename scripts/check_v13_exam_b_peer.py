"""Independent exact peer recomputation; reads only the frozen six-file capsule.

No author checker import or invocation. Universal proofs are audited in the peer
record; the finite computations below corroborate, rather than prove, them.
"""
from fractions import Fraction as Q
from hashlib import sha256
from html.parser import HTMLParser
from itertools import product
import json
from math import isqrt
from pathlib import Path
import re
import sys

PAGE = 'content/assessments/parts/v13-exam-b.html'
AUTHOR = 'scripts/check_v13_exam_b.py'
SOURCES = 'content/reviews/v13-exam-b-sources.json'
AUTHOR_REVIEW = 'content/reviews/v13-exam-b-author.json'
SELF = 'scripts/check_v13_exam_b_peer.py'
PEER = 'content/reviews/v13-exam-b-peer.json'
FILES = (PAGE, AUTHOR, SOURCES, AUTHOR_REVIEW, SELF, PEER)
POINTS = ((5,7,4,4),(7,3,6,4),(5,6,5,4),(8,4,3,5),(5,5,5,5))


def require(ok, message):
    if not ok:
        raise ValueError(message)


def clean(s):
    return ''.join(s.replace('−', '-').split())


def parse(s):
    """Small recursive fraction/tuple reader; no eval or execution grammar."""
    require(isinstance(s, str) and len(s) <= 1500, 'literal size/type')
    s = clean(s)
    def read(t, depth=0):
        require(depth <= 5 and t, 'literal nesting/empty')
        if t.startswith('('):
            require(t.endswith(')'), 'tuple closing delimiter')
            parts, level, start = [], 0, 1
            for i in range(1, len(t)-1):
                level += (t[i] == '(') - (t[i] == ')')
                require(level >= 0, 'tuple nesting')
                if t[i] == ',' and level == 0:
                    parts.append(read(t[start:i], depth+1)); start = i+1
            require(level == 0, 'tuple nesting')
            parts.append(read(t[start:-1], depth+1))
            require(len(parts) <= 20, 'tuple length')
            return tuple(parts)
        require(re.fullmatch(r'-?\d+(?:/[1-9]\d*)?', t) is not None, 'fraction syntax')
        value = Q(t)
        require(abs(value) <= 10**6 and value.denominator <= 10**12, 'fraction bound')
        return value
    return read(s)


def sqrtq(x):
    require(type(x) in (int, Q) and x >= 0, 'rational square-root domain')
    x = Q(x); a, b = isqrt(x.numerator), isqrt(x.denominator)
    require(a*a == x.numerator and b*b == x.denominator, 'irrational square root')
    return Q(a,b)


def read_json(raw):
    def pairs(items):
        out = {}
        for k,v in items:
            require(k not in out, 'duplicate JSON key'); out[k] = v
        return out
    def bad(value):
        raise ValueError('nonfinite JSON '+value)
    result = json.loads(raw, object_pairs_hook=pairs, parse_constant=bad)
    json.dumps(result, allow_nan=False)
    return result


class Reader(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.ids = [], set()
        self.markers = {'data-input':{}, 'data-calc':{}, 'data-model':{}}
        self.prompts, self.answers, self.rubrics, self.links = {}, {}, {}, {}
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        require(len(a) == len(attrs), 'duplicate attribute')
        if 'id' in a:
            require(a['id'] not in self.ids, 'duplicate ID'); self.ids.add(a['id'])
        for kind, values in self.markers.items():
            if kind in a:
                require(a[kind] not in values, 'duplicate marker'); values[a[kind]] = ''
        if tag == 'li' and 'data-points' in a:
            self.prompts[a['id']] = int(a['data-points'])
        for attr, target in (('data-solution-for', self.answers), ('data-rubric-for', self.rubrics)):
            if attr in a:
                require(a[attr] not in target, 'duplicate answer/rubric')
                target[a[attr]] = ''
        if 'data-source' in a:
            require(a['data-source'] not in self.links, 'duplicate citation')
            self.links[a['data-source']] = a['href']
        if tag not in ('br','hr','img','input','meta','link','wbr'):
            self.stack.append((tag,a))
    def handle_data(self, data):
        for _,a in self.stack:
            for kind,values in self.markers.items():
                if kind in a: values[a[kind]] += data
            for attr,target in (('data-solution-for',self.answers),('data-rubric-for',self.rubrics)):
                if attr in a: target[a[attr]] += data
    def handle_endtag(self, tag):
        require(self.stack and self.stack[-1][0] == tag, 'unbalanced HTML')
        self.stack.pop()


def inner(x,y):
    require(len(x) == len(y), 'inner product dimension')
    return sum((a*b for a,b in zip(x,y)), Q(0))


def consumer(p, wealth):
    px,py = p
    require(px > 0 and py > 0 and wealth >= 0, 'consumer domain')
    # Compare the vertex with the resource endpoint in square-root coordinates.
    endpoint = wealth/px
    x = min(endpoint, (py/px)**2/4)
    y = (wealth-px*x)/py
    return (x,y), sqrtq(x)+y


def dual(p, u):
    px,py = p
    require(px > 0 and py > 0 and u >= 0, 'dual domain')
    s = min(u,py/(2*px)); h = (s*s,u-s)
    return h, inner(p,h)


def integrate(poly, low):
    """Polynomial integral to sqrt(3) in basis (1,sqrt(3))."""
    a,b = Q(0),Q(0)
    for k,c in enumerate(poly):
        n = k+1
        a -= c*low**n/n
        if n%2: b += c*3**((n-1)//2)/n
        else: a += c*3**(n//2)/n
    return a,b


def add(x,y): return tuple(a+b for a,b in zip(x,y))
def scale(x,k): return tuple(a*k for a in x)


def radical(s):
    m = re.fullmatch(r'(\d*)sqrt\(3\)(?:/(\d+))?([+-]\d+(?:/\d+)?)?', clean(s))
    require(m is not None, 'radical display grammar')
    return Q(m[3] or '0'), Q(int(m[1] or '1'),int(m[2] or '1'))


def check(root=None):
    root = Path(root) if root is not None else Path(__file__).resolve().parents[1]
    before = {p:(root/p).read_bytes() for p in FILES}
    count, rejections = 0,0
    def eq(a,b,label):
        nonlocal count
        count += 1
        require(a == b, label+': '+repr(a)+' != '+repr(b))
    page = Reader(); page.feed(before[PAGE].decode()); page.close()
    eq(page.stack,[], 'balanced full fragment')
    scores = {f'v13-exam-b-{i}{letter}':n for i,row in enumerate(POINTS,1) for letter,n in zip('abcd',row)}
    eq(page.prompts,scores,'all twenty prompt scores')
    eq(set(page.answers),set(scores),'complete paired solutions')
    eq(set(page.rubrics),set(scores),'complete paired rubrics')
    for key,n in scores.items():
        eq(sum(map(int,re.findall(r'\b(\d+) for\b',page.rubrics[key]))),n,'rubric '+key)
    q = {k:parse(v) for k,v in page.markers['data-input'].items() if k != 'b4-value-support'}
    out = {}
    # Afriat: compute all affine evaluations before subtracting levels.
    prices = [q[f'b1-p{i}'] for i in range(1,4)]
    bundles = [q[f'b1-x{i}'] for i in range(1,4)]
    U,L = q['b1-levels'],q['b1-multipliers']
    planes = lambda z: tuple(U[t]+L[t]*(inner(prices[t],z)-inner(prices[t],bundles[t])) for t in range(3))
    out['b1-slacks'] = tuple(tuple(planes(bundles[s])[t]-U[s] for s in range(3)) for t in range(3))
    eq(all(x >= 0 for row in out['b1-slacks'] for x in row),True,'every Afriat inequality')
    out['b1-tie-planes'] = planes(q['b1-tie'])
    eq((inner(prices[0],q['b1-tie']),min(out['b1-tie-planes'])),(Q(1),U[0]),'genuine tie')
    for i in range(3):
        m=q[f'b1-wealth{i+1}']; x,v=consumer(prices[i],m)
        eq(x,bundles[i],'observed selected demand')
        eq(dual(prices[i],v),(x,m),'observed duality')
    for p in ((Q(1),Q(4)),(Q(4),Q(4)),(Q(3),Q(2))):
        threshold=p[1]/(2*p[0])
        for u in (Q(0),threshold/2,threshold,threshold*2):
            h,cost=dual(p,u); eq(consumer(p,cost),(h,u),'zero/corner/join/interior duality')
    for name in ('low','high'):
        wealth=q[f'b1-{name}-wealth']; ev=inner(q['b1-probabilities'],tuple(consumer(prices[0],w)[1] for w in wealth))
        ce=dual(prices[0],ev)[1]; mean=inner(q['b1-probabilities'],wealth)
        for key,v in (('EU',ev),('CE',ce),('mean',mean),('premium',mean-ce)): out[f'b1-{name}-{key}']=v
    eq((sqrtq(4),Q(1)+Q(4)/4),(Q(2),Q(2)),'wealth value joins')
    eq(Q(1)/(2*sqrtq(4)),Q(1,4),'wealth slope joins')
    # Production: solve raw resources after eliminating intermediate clearing.
    raw_total=sum(q['b2-endowments']); z=raw_total/5; pm=2*sqrtq(z); final=2*sqrtq(sqrtq(z)); pf=pm*sqrtq(sqrtq(z))
    intermediate=sqrtq(z); profits=(pm*intermediate-z,pf*final-pm*intermediate)
    out['b2-prices']=(Q(1),pm,pf); out['b2-profits']=profits
    for prefix,div in (('baseline',profits),('swapped',profits[::-1])):
        incomes=tuple(a+b for a,b in zip(q['b2-endowments'],div)); choices=tuple((w/2,w/(2*pf)) for w in incomes)
        out[f'b2-{prefix}-incomes']=incomes
        for j,label in enumerate(('A','B')): out[f'b2-'+('baseline' if prefix=='baseline' else 'target')+'-'+label]=choices[j]
        eq((sum(c[0] for c in choices)+z,sum(c[1] for c in choices)),(raw_total,final),'physical resources')
        eq(tuple(inner((Q(1),pf),c) for c in choices),incomes,'household budgets')
    targets=(q['b2-target-A'],q['b2-target-B'])
    eq(tuple(tuple(w/x for x in c) for w,c in zip(q['b2-weights'],targets)),((Q(1,4),Q(1,2)),)*2,'common weighted gradient')
    eq(tuple(inner((Q(1),pf),c)-div for c,div in zip(targets,profits)),(Q(5),Q(0)),'owned balanced transfer')
    gross=raw_total+pm*intermediate+pf*final
    out['b2-wrong-demand']=(gross/2,gross/(2*pf))
    eq(gross-(raw_total+sum(profits)),Q(3),'input double count')
    eq((Q(3,2)+profits[0]-Q(5,2),profits[1]-Q(1,2)-Q(3,2)),(0,0),'settlement counterparties')
    # Bayesian boundaries solved by payoff signs; finite points test the classification.
    prior,costs,payment,benefits=(q[k] for k in ('b3-prior','b3-costs','b3-payment','b3-benefits'))
    cutoff=costs[0]/payment; posterior=(payment-benefits[1])/(benefits[0]-benefits[1])
    out['b3-trading-strategy']=(1,0,1); out['b3-posterior-cutoff']=posterior
    out['b3-exante-payoffs']=(prior[0]*(payment-costs[0]),prior[0]*(benefits[0]-payment))
    out['b3-real-surplus']=sum(out['b3-exante-payoffs'])
    def optimal(prob,gain): return (prob==0 or gain>=0) and (prob==1 or gain<=0)
    nodes=(Q(0),Q(1,3),cutoff,Q(2,3),Q(1))
    for g,b,r in product(nodes,repeat=3):
        found=optimal(g,payment*r-costs[0]) and optimal(b,payment*r-costs[1]) and optimal(r,prior[0]*g*(benefits[0]-payment)+prior[1]*b*(benefits[1]-payment))
        eq(found,(g,b,r)==(1,0,1) or (g==b==0 and r<=cutoff),'simultaneous family sample')
    for mu in (Q(0),Q(1,5),posterior,Q(1,2),Q(1)):
        for r in nodes:
            eq(optimal(r,mu*(benefits[0]-payment)+(1-mu)*(benefits[1]-payment)) and optimal(0,payment*r-costs[0]),(mu<posterior and r==0) or (mu==posterior and r<=cutoff),'off-path family sample')
    for mu in (Q(1,5),posterior):
        for eps in (Q(1,10),Q(1,100)):
            g,b=2*mu*eps,(1-mu)*eps
            eq(prior[0]*g/(prior[0]*g+prior[1]*b),mu,'consistent interior posterior')
    eq(payment-costs[1]<0<payment-costs[0],True,'exact dominated type')
    # Auction: integrate the direct payment distribution, independently of virtual values.
    # Exactly one above reserve contributes 4/9; both above pay their minimum.
    out['b4-sale']=1-Q(1,3)**2
    revenue=add((Q(4,9),Q(0)),integrate((Q(0),Q(0),Q(4,3),Q(0),Q(-4,9)),Q(1)))
    value=integrate((Q(0),)*4+(Q(4,9),),Q(1))
    out['b4-revenue']=revenue; out['b4-allocated-value']=value; out['b4-buyer-rent']=add(value,scale(revenue,-1))
    virtual=integrate((Q(0),Q(0),Q(-2,3),Q(0),Q(2,3)),Q(1))
    eq(virtual,revenue,'virtual and direct receipts')
    for label,lower in (('reserve',Q(1)),('zero',Q(0))):
        out[f'b4-correlated-{label}-revenue']=integrate((Q(0),Q(0),Q(2,3)),lower)
    eq(add(out['b4-correlated-zero-revenue'],scale(out['b4-correlated-reserve-revenue'],-1)),(Q(2,9),Q(0)),'correlated improvement')
    eq(q['b4-buyer-cash']**2>3,True,'auction cash ceiling')
    # Payroll: action-by-action expectations from the full probability table.
    wages=q['b4-wages']; utility=tuple(sqrtq(w) for w in wages); costs=q['b4-costs']
    initial=tuple((s/2,s/2,(1-s)/2,(1-s)/2) for s in q['b4-success'])
    changed=(q['b4-changed-H'],q['b4-changed-L'])
    for changed_flag,laws in ((False,initial),(True,changed)):
        means=tuple(inner(laws[0][j:j+2],utility[j:j+2])/sum(laws[0][j:j+2]) for j in (0,2))
        new_u=(means[0],means[0],means[1],means[1]); new_w=tuple(u*u for u in new_u)
        old_net=tuple(inner(l,u)-c for l,u,c in zip(laws,(utility,utility),costs))
        net=tuple(inner(l,new_u)-c for l,c in zip(laws,costs))
        old_cost,new_cost=inner(laws[0],wages),inner(laws[0],new_w)
        if changed_flag:
            for key,v in (('means',means),('compressed-wages',new_w),('L-utility',net[1]),('gap',net[0]-net[1]),('old-cost',old_cost),('new-cost',new_cost)): out['b4-changed-'+key]=v
            eq(old_net,(Q(7,6),Q(11,12)),'changed original utilities')
            eq(net[0],old_net[0],'target only utility preserved')
            eq(net[0]<net[1],True,'replacement fails H-IC')
        else:
            for key,v in (('compressed-wages',new_w),('old-H-cost',old_cost),('new-H-cost',new_cost),('cost-saving',old_cost-new_cost),('H-utility',net[0]),('L-utility',net[1]),('incentive-gap',net[0]-net[1])): out['b4-'+key]=v
            eq(old_net,net,'all action utilities preserved')
        eq(tuple((sum(l),sum(l[:2]),l[1]+l[3]) for l in laws),((1,Q(2,3),Q(1,2)),(1,Q(1,3),Q(1,2))),'joint-law marginals')
        eq(all(0<=w<=q['b4-payroll-cash'] for w in new_w),True,'common wage restrictions')
        for w in new_w:
            eq((16-w+Q(3,2))+w+(4-Q(3,2)),Q(20),'owned cash conservation')
    # Network: total-sum reduction, distinct from author active-face enumeration.
    a,gamma=q['b5-a'],q['b5-interaction']; total=sum(a)/(1-2*gamma)
    x=tuple((ai+gamma*total)/(1+gamma) for ai in a)
    def br(y,t=(0,0,0)):
        return tuple(max(Q(0),min(Q(1),a[i]+t[i]+gamma*(sum(y)-y[i]))) for i in range(3))
    def utility(y): return tuple(a[i]*y[i]-y[i]**2/2+gamma*y[i]*(sum(y)-y[i]) for i in range(3))
    out['b5-Nash']=x; out['b5-Nash-utilities']=utility(x); out['b5-Nash-welfare']=sum(utility(x))
    eq(br(x),x,'full cube fixed point')
    target=q['b5-target']; wt=sum(utility(target)); out['b5-welfare-gap']=wt-sum(utility(x))
    deviation=(br(target)[0],Q(1),Q(1)); out['b5-deviator-utility']=utility(deviation)[0]; out['b5-deviation-gain']=utility(deviation)[0]-utility(target)[0]
    rates=tuple(max(Q(0),1-a[i]-gamma*2) for i in range(3)); out['b5-rates']=rates; out['b5-budget']=sum(rates)
    eq(br(target,rates),target,'minimal rate implementation')
    eq(tuple(u+t for u,t in zip(utility(target),rates)),(Q(1,2),)*3,'funded agent utilities')
    eq(sum(utility(target))+sum(rates)-sum(rates),Q(1),'sponsor consolidation')
    # Polynomial coefficient identity, not just pointwise sampling.
    # W(1)-W(1-d) has linear a_i and quadratic diagonal 1/2, off diagonal -1/2.
    eq(tuple(ai-Q(1)+4*gamma for ai in a),a,'welfare certificate linear coefficients')
    eq((Q(1,2),-2*gamma),(2*Q(1,4),-2*Q(1,4)),'welfare certificate all quadratic coefficients')
    candidate=q['b5-candidate']; response=br(candidate); residual=max(abs(v-w) for v,w in zip(candidate,response))
    out['b5-response']=response; out['b5-residual']=residual; out['b5-distance-bound']=residual/(1-2*gamma)
    out['b5-objective-bound']=2*q['b5-objective-error']+q['b5-global-gap']
    eq(max(abs(v-w) for v,w in zip(candidate,x)),Q(1,20),'actual distance')
    eq(out['b5-welfare-gap']>out['b5-objective-bound'],True,'incompatible welfare premises')
    eq(set(out),set(page.markers['data-calc']),'every displayed answer covered')
    radical_keys={'b4-revenue','b4-allocated-value','b4-buyer-rent','b4-correlated-reserve-revenue','b4-correlated-zero-revenue'}
    for key,value in out.items(): eq((radical if key in radical_keys else parse)(page.markers['data-calc'][key]),value,'visible result '+key)
    sources,author,peer=(read_json(before[p]) for p in (SOURCES,AUTHOR_REVIEW,PEER))
    eq(page.links,{s['id']:s['url'] for s in sources['sources']},'sixteen source identities/routes')
    eq(len(page.links),16,'source count')
    eq((sources['new_primary_retrievals'],sources['new_primary_image_views']),(0,0),'accurate reused-source scope')
    eq(peer['status'],'passed','peer decision')
    eq(peer['open_findings'],[],'no open material findings')
    eq({r['id']:r['points'] for r in peer['prompt_solution_review']},scores,'all written proof reviews')
    eq({b['path'] for b in peer['bindings']},set(FILES)-{PEER},'five nonself bindings')
    for record in (author,peer):
        for binding in record['bindings']:
            raw=before[binding['path']]
            eq((len(raw),sha256(raw).hexdigest()),(binding['bytes'],binding['sha256']),'payload binding')
    for fn in (lambda:parse('1/0'),lambda:parse('True'),lambda:parse('0.5'),lambda:parse('x()'),lambda:parse('1+2'),lambda:parse('(1,,2)'),lambda:parse('1'*1501),lambda:sqrtq(-1),lambda:sqrtq(2),lambda:consumer((0,1),1),lambda:consumer((1,1),-1),lambda:dual((1,1),-1),lambda:read_json('{"a":1,"a":2}'),lambda:read_json('{"a":NaN}'),lambda:read_json('{"a":1e9999}')):
        try: fn()
        except (ValueError,TypeError): rejections+=1
        else: raise ValueError('invalid domain accepted')
    eq({p:(root/p).read_bytes() for p in FILES},before,'all six bytes unchanged')
    return {'volume':'v13','component':'exam_b_peer','status':'passed','comparisons':count,'domain_rejections':rejections,'visible_results':len(out),'scored_parts':20,'points':100,'source_routes':16,'runtime_files':6,'author_code_executed':False,'limits':'Exact recomputation and separately recorded universal-proof audit; no human validation or empirical timing claim.'}


if __name__ == '__main__':
    require(len(sys.argv)==1,'silent checker takes no arguments')
    check()
