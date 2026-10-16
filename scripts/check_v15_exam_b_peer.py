"""Coordinator reconstruction of V15 Form B; no author-checker imports.

The numerical oracle was persisted before reading the unfinished author checker.
Exact finite games and resource accounts complement the written proof review.
"""
import ast
import json
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from itertools import product
from pathlib import Path

FILES = (
    'content/assessments/parts/v15-exam-b.html',
    'scripts/check_v15_exam_b.py',
    'content/reviews/v15-exam-b-sources.json',
    'content/reviews/v15-exam-b-author.json',
    'scripts/check_v15_exam_b_peer.py',
    'content/reviews/v15-exam-b-peer.json',
)

def require(ok, message):
    if not ok:
        raise ValueError(message)

def literal(text):
    def walk(node):
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            return F(str(node.value))
        if isinstance(node, (ast.Tuple, ast.List)):
            return tuple(walk(x) for x in node.elts)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            return -walk(node.operand)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            return walk(node.left) / walk(node.right)
        raise ValueError('numeric literals only')
    return walk(ast.parse(text.rsplit('=', 1)[-1].strip(), mode='eval').body)

def strict(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    def invalid(value):
        raise ValueError('nonfinite JSON')
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)

class Manuscript(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack = []
        self.ids = set()
        self.inputs, self.results, self.questions, self.answers, self.sources = {}, {}, {}, {}, {}
        self.links = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        require(len(a) == len(attrs), 'duplicate attribute')
        if 'id' in a:
            require(a['id'] not in self.ids, 'duplicate id')
            self.ids.add(a['id'])
        if 'href' in a:
            self.links.append(a['href'])
        if 'data-source' in a:
            require(a['data-source'] not in self.sources, 'duplicate source')
            self.sources[a['data-source']] = a['href']
        if 'data-points' in a:
            self.questions[a['id']] = int(a['data-points'])
        if 'data-solution-for' in a:
            key = a['data-solution-for']
            require(key not in self.answers, 'duplicate answer')
            require(any(t == 'details' and 'solutions' in d.get('class', '').split() for t, d in self.stack), 'answer disclosure')
            self.answers[key] = ''
        for attr, target in [('data-input', self.inputs), ('data-result', self.results)]:
            if attr in a:
                require(a[attr] not in target, 'duplicate numeric marker')
                target[a[attr]] = ''
        if tag not in ('br', 'hr', 'img', 'meta', 'link', 'input'):
            self.stack.append((tag, a))

    def handle_data(self, text):
        for tag, a in self.stack:
            for attr, target in [('data-input', self.inputs), ('data-result', self.results), ('data-solution-for', self.answers)]:
                if attr in a:
                    target[a[attr]] += text

    def handle_endtag(self, tag):
        require(self.stack and self.stack[-1][0] == tag, 'balanced markup')
        self.stack.pop()

def linear(matrix, rhs):
    """Pivoted rational row elimination, independently used for quantities/prices."""
    n = len(rhs)
    require(n and len(matrix) == n and all(len(row) == n for row in matrix), 'square system')
    a = [[F(x) for x in row] + [F(b)] for row, b in zip(matrix, rhs)]
    for j in range(n):
        pivot = next((i for i in range(j, n) if a[i][j]), None)
        require(pivot is not None, 'singular system')
        a[j], a[pivot] = a[pivot], a[j]
        scale = a[j][j]
        a[j] = [v / scale for v in a[j]]
        for i in range(n):
            if i != j:
                scale = a[i][j]
                a[i] = [v - scale * w for v, w in zip(a[i], a[j])]
    return tuple(row[-1] for row in a)

def price_profit(p, rival, intercept, cost):
    require(0 <= p <= intercept and 0 <= rival <= intercept and 0 <= cost < intercept, 'price domain')
    quantity = max(0, intercept - p) * (1 if p < rival else F(1, 2) if p == rival else 0)
    return (p - cost) * quantity

def games(cost, high, low, coverage, indemnity):
    def payoff(own, other, insured):
        return (high if other else low + insured * indemnity) - cost if own else F(0)
    equilibria = []
    for choices in product((0, 1), repeat=2):
        if all(payoff(choices[i], choices[1-i], coverage[i]) >= payoff(1-choices[i], choices[1-i], coverage[i]) for i in (0, 1)):
            equilibria.append(choices)
    return equilibria

def allocation(stock, beta, cost, a0, a1):
    require(stock >= 0 and 0 < beta <= 1 and cost >= 0, 'resource domain')
    net0, net1 = a0 - cost, a1 - cost
    candidates = {(F(0), F(0)), (stock, F(0)), (F(0), stock)}
    candidates.add((min(stock, max(F(0), net0)), F(0)))
    candidates.add((F(0), min(stock, max(F(0), net1))))
    candidates.add((max(F(0), net0), max(F(0), net1)))
    q0 = (net0 - beta * net1 + beta * stock) / (1 + beta)
    candidates.add((q0, stock - q0))
    value = lambda q: net0*q[0] - q[0]**2/2 + beta*(net1*q[1] - q[1]**2/2)
    feasible = [q for q in candidates if min(q) >= 0 and sum(q) <= stock]
    return max(feasible, key=value), value

def reconstruct(inputs):
    """All twenty displayed solution vectors reconstructed from prompt primitives."""
    out = {}
    a, b, tax = inputs['tax']
    q0, q = (a-b)/2, (a-b-tax)/2
    revenue = tax*q
    surplus = lambda z: (a-b)*z-z*z
    out['b1a'] = (a-q0, q0, a-q, b+q, q, revenue, surplus(q0), surplus(q))
    low, high, dl, dh, tuition, cash = inputs['training']
    out['b1b'] = (dl-tuition, dh-tuition, dl, dh)
    market_change = surplus(q)-surplus(q0)
    out['b1c'] = (2*tuition, dl+dh-2*tuition, market_change+dl+dh-2*tuition, tuition, revenue-tuition, dh-tuition, market_change+dh-tuition)
    out['b1d'] = (high+dh-low, dh, (dl+dh)/2, high-low)
    a, c, claimed = inputs['bertrand']
    deviation = claimed-F(1, 10)
    out['b2a'] = (price_profit(claimed, claimed, a, c), deviation, a-deviation, price_profit(deviation, claimed, a, c))
    out['b2b'] = (c, c, a-c, price_profit(c,c,a,c), price_profit(c,c,a,c))
    final, hpf, fph, home, foreign = inputs['network']
    xh, xf = linear(((1, -hpf), (-fph, 1)), (final, 0))
    ph, pf = linear(((1, -fph), (-hpf, 1)), (home, foreign))
    out['b2c'] = (xh, xf, ph, pf, home*xh, foreign*xf, final*ph, ph*xh+pf*xf, pf*fph*xh+ph*hpf*xf)
    ph, pf = linear(((1, -fph), (-hpf, 1)), (home, 2*foreign))
    ih, iff = home*xh, 2*foreign*xf
    out['b2d'] = (ph,pf,ih,iff,ih/ph,iff/ph,pf*fph*xh,ph*hpf*xf+iff)
    initial, cost, high, low, insurance = inputs['coordination']
    out['b3a'] = ((cost-low)/(high-low), 2*(high-cost), 0)
    out['b3b'] = (low-cost+insurance, insurance, 0, 2*(high-cost))
    t, cpath = inputs['history']
    dd = (t[2]-t[1])-(cpath[2]-cpath[1])
    out['b3c'] = (dd,(t[1]-t[0])-(cpath[1]-cpath[0]),t[1]+cpath[2]-cpath[1],dd,t[2],0)
    outcomes = {(u,v): high-cost if u or v else F(0) for u,v in product((0,1),repeat=2)}
    covered = sum(outcomes[1,v] for v in (0,1))/2
    uncovered = sum(outcomes[0,v] for v in (0,1))/2
    full = outcomes[1,1]-outcomes[0,0]
    out['b3d'] = (covered,uncovered,covered-uncovered,full,2*full)
    A,B,C,tax = inputs['voting']
    votes = lambda x,y: sum(a>b for a,b in zip(x,y))
    out['b4a'] = (votes(A,B),votes(B,C),votes(C,A),3*tax)
    prior,l1,l0,prize,d1,d0 = inputs['reporting']
    posterior = prior*l1/(prior*l1+(1-prior)*l0)
    u1,u0 = prize/d1,prize/d0
    report = posterior*u1/(posterior*u1+(1-posterior)*u0)
    out['b4b'] = (posterior,report)
    repaired = prize*d0/d1
    pay = posterior*(1-(posterior-1)**2)*prize+(1-posterior)*(1-posterior**2)*repaired
    out['b4c'] = (repaired,posterior,pay,3*pay,3*max(prize,repaired))
    out['b4d'] = tuple(sum(w*(z-tax) for w,z in zip((2,1,1),proposal)) for proposal in (A,B,C))+(0,)
    stock,beta,cost,a0,a1,harm = inputs['resource']
    before,_ = allocation(stock,beta,cost,a0,a1)
    after,_ = allocation(stock,beta,cost+harm,a0,a1)
    out['b5a'] = (*before,a0-before[0],a1-before[1],*after,a0-after[0],a1-after[1])
    wealth,p0,p1,loss,effort,capital = inputs['health']
    physical = (p0*loss,effort+p1*loss)
    uninsured = min((0,1),key=lambda e:physical[e])
    insured = min((0,1),key=lambda e:e*effort)
    out['b5b'] = (uninsured,insured,(p0,p1)[insured]*loss,physical[uninsured],physical[insured])
    # The spatial primitive is stated in prose, unlike the other numeric spans.
    original=(F(2),F(8));current=(F(8),F(10));rent=F(2)
    out['b5c'] = ((sum(current)-sum(original))/2,0,-rent)
    al,ah,ac,aw,bl,bh,bc,bw,cap,budget,tc,extra = inputs['implementation']
    choices=[]
    for training in (0,1):
        for label,lower,cost,work in [('none',F(0),F(0),F(0)),('A',al,ac,aw),('B',bl,bc,bw)]:
            if cost+training*tc <= budget and work <= cap+training*extra:
                choices.append((lower-training*tc,cost+training*tc,cap+training*extra-work,label,training))
    best=max(choices,key=lambda z:z[0])
    out['b5d']=(best[0],best[1],budget-best[1],best[2])
    return out

def check(root=None):
    base = Path(root) if root is not None else Path(__file__).resolve().parents[1]
    raw = {f:(base/f).read_bytes() for f in FILES}
    doc=Manuscript();doc.feed(raw[FILES[0]].decode());doc.close()
    require(not doc.stack,'complete markup')
    targets=[f'v15-exam-b-{i}{s}' for i in range(1,6) for s in 'abcd']
    require(list(doc.questions)==targets==list(doc.answers),'all twenty exact solutions')
    require(all(v==5 for v in doc.questions.values()),'100 additive points')
    require(all('Rubric:' in v for v in doc.answers.values()),'all rubrics')
    require(all(f'v15-c{i:02}.html' in doc.links for i in range(1,13)),'all chapter routes')
    sources=strict(raw[FILES[2]]);peer=strict(raw[FILES[5]])
    require(doc.sources=={x['id']:x['url'] for x in sources['sources']},'source routes')
    require(set(peer['exact_prompt_review'])==set(targets) and not peer['open_findings'],'full written audit')
    require(set(peer['payload_bindings'])==set(FILES[:-1]),'five nonself bindings')
    for f,b in peer['payload_bindings'].items():
        require(len(raw[f])==b['bytes'] and sha256(raw[f]).hexdigest()==b['sha256'],'peer freeze '+f)
    inputs={k:literal(v) for k,v in doc.inputs.items()}
    computed=reconstruct(inputs)
    require(set(computed)==set(doc.results),'all numeric markers')
    count=0
    def equal(a,b):
        nonlocal count
        if isinstance(a,(tuple,list)):
            require(isinstance(b,(tuple,list)) and len(a)==len(b),'shape')
            for x,y in zip(a,b):equal(x,y)
        else:
            require(a==b,'numeric mismatch '+str((a,b)));count+=1
    for k,value in computed.items():equal(value,literal(doc.results[k]))
    # Exhaustive action profiles, not an assumed high-investment selection.
    _,cost,high,low,indemnity=inputs['coordination']
    equal(games(cost,high,low,(0,0),indemnity),[(0,0),(1,1)])
    for coverage in ((1,0),(0,1),(1,1)):
        equal(games(cost,high,low,coverage,indemnity),[(1,1)])
    equal(games(cost,high,low,(1,1),0),[(0,0),(1,1)])
    # Price candidate against every tenth-unit unilateral deviation.
    a,c,_=inputs['bertrand']
    for i in range(int(10*a)+1):
        require(price_profit(F(i,10),c,a,c)<=0,'profitable cost-price deviation');count+=1
    # All resource faces plus a rational triangular grid, including corner cases.
    for stock,beta,cost,a0,a1 in [(4,F(1,2),2,8,10),(4,F(1,2),3,8,10),(0,F(1,2),2,8,10),(4,F(1,2),20,8,10),(4,1,2,20,3),(4,1,2,3,20)]:
        best,value=allocation(F(stock),F(beta),F(cost),F(a0),F(a1))
        for i in range(2*stock+1):
            for j in range(2*stock+1-i):
                require(value(best)>=value((F(i,2),F(j,2))),'global resource witness');count+=1
    # Scoring-square identities include p=0,1 and state utility differences.
    for p,u1,u0 in product((F(0),F(1,3),F(2,3),F(1)),(F(1),F(2)),(F(1),F(3))):
        weight=p*u1+(1-p)*u0;star=p*u1/weight
        value=lambda q:p*u1*(1-(q-1)**2)+(1-p)*u0*(1-q*q)
        for i in range(11):
            q=F(i,10);equal(value(star)-value(q),weight*(q-star)**2)
    # Funding cancellation is statewise, not only in expectation.
    wealth,p0,p1,loss,effort,capital=inputs['health'];premium=p0*loss
    for illness in (0,1):
        person=wealth-premium-illness*loss+illness*loss
        insurer=capital+premium-illness*loss
        require(min(person,insurer)>=0,'state funding')
        equal(person+insurer,wealth+capital-illness*loss)
    rejections=0
    for operation in [lambda:literal('True'),lambda:literal('2**3'),lambda:literal('1/0'),lambda:strict('{"x":1,"x":2}'),lambda:strict('{"x":NaN}'),lambda:linear(((1,1),(1,1)),(1,2)),lambda:allocation(-1,F(1,2),2,8,10),lambda:allocation(4,0,2,8,10),lambda:price_profit(-1,3,12,3)]:
        try:operation()
        except (ValueError,ZeroDivisionError):rejections+=1
        else:raise ValueError('invalid domain accepted')
    require(raw=={f:(base/f).read_bytes() for f in FILES},'immutable check')
    return dict(volume='v15',component='exam_b_peer',status='passed',questions=20,points=100,numeric_markers=20,comparisons=count,invalid_domain_rejections=rejections,runtime_files=6)

if __name__=='__main__':
    check()
