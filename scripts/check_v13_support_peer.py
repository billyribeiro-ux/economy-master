"""Independent, quiet V13 support audit; never executes the author checker.

Seven-file runtime. Exact finite calculations corroborate separately read proofs;
finite witnesses are not presented as proofs of the universal results.
"""
from collections import deque
from fractions import Fraction as Q
from hashlib import sha256
from html.parser import HTMLParser
from itertools import combinations, permutations, product
from math import isfinite, isqrt
from pathlib import Path
import json
import sys

AUTHOR = (
    ('content/assessments/parts/v13-support-opening.html', 14063,
     '24fea5e98be7a3ff1c15d896c73ec23714610f380059abd0538d521e23d07c44'),
    ('content/assessments/parts/v13-support-closing.html', 32212,
     '3baf7de9da7a2df1a98f06bc694f9237e9d59deb407959b0fb3ab52d61dd5e99'),
    ('scripts/check_v13_support.py', 14121,
     'eb9acff37190f6265366e24246bbd03dd94132244a7e85cd71293ba29cc6ec25'),
    ('content/reviews/v13-support-sources.json', 2839,
     '737a6cf0a634923f3b9124950ce62a888f896aad503f11821e7392ca6ccc7c99'),
    ('content/reviews/v13-support-author.json', 5940,
     'befdf4b71ec092bfd704e341386272b89586251ebd51cbea8d504b97452be804'),
)
CHECKER = 'scripts/check_v13_support_peer.py'
REVIEW = 'content/reviews/v13-support-peer.json'
FILES = tuple(a[0] for a in AUTHOR)+(CHECKER, REVIEW)


def need(ok, label):
    if not ok:
        raise ValueError(label)


def exact(x):
    need(type(x) in (int, Q), 'exact rational scalar; no bool/float/string')
    return Q(x)


def strict_json(raw):
    def pairs(items):
        result = {}
        for k, v in items:
            need(k not in result, 'duplicate JSON key')
            result[k] = v
        return result
    def finite(s):
        x = float(s)
        need(isfinite(x), 'overflow JSON number')
        return x
    def bad(_):
        raise ValueError('nonfinite JSON token')
    return json.loads(raw, object_pairs_hook=pairs, parse_float=finite, parse_constant=bad)


def rationalizers(choices):
    universe = ('a', 'b', 'c')
    need(type(choices) in (tuple, list) and len(choices) == 3, 'three declared menus')
    for menu, chosen in choices:
        need(len(menu) == 2 and len(set(menu)) == 2 and set(menu) <= set(universe)
             and chosen in menu, 'valid binary choice')
    good = []
    for ranking in permutations(universe):
        if all(min(menu, key=ranking.index) == chosen for menu, chosen in choices):
            good.append(ranking)
    return good


def concave_capacity(slope, bound):
    slope, bound = exact(slope), exact(bound)
    need(bound >= 0, 'nonnegative feasible bound')
    candidates = {Q(0), bound}
    if 0 <= slope <= bound:
        candidates.add(slope)
    values = {x: slope*x-x*x/2 for x in candidates}
    best = max(values.values())
    maximizers = tuple(sorted(x for x, v in values.items() if v == best))
    return maximizers, best


def wealth_lottery(wealth, probabilities):
    need(len(wealth) == len(probabilities) and len(wealth) > 0, 'lottery dimension')
    w = tuple(exact(x) for x in wealth)
    p = tuple(exact(x) for x in probabilities)
    need(min(w) >= 0 and min(p) >= 0 and sum(p) == 1, 'wealth/probability domain')
    roots = []
    for x in w:
        a, b = isqrt(x.numerator), isqrt(x.denominator)
        need(a*a == x.numerator and b*b == x.denominator, 'rational square witness')
        roots.append(Q(a, b))
    ew = sum(a*b for a, b in zip(w, p))
    eu = sum(a*b for a, b in zip(roots, p))
    return ew, eu, eu*eu, ew-eu*eu


def exchange(endowment_x, endowment_y, relative_price):
    e, f, r = map(exact, (endowment_x, endowment_y, relative_price))
    need(min(e, f, r) > 0, 'strictly positive endowments and relative price')
    # Each interior optimum equates its two expenditure components.
    a, b = (e/2, r*e/2), (f/(2*r), f/2)
    excess = (a[0]+b[0]-e, a[1]+b[1]-f)
    return a, b, excess


def minimax(matrix):
    need(type(matrix) in (tuple, list) and len(matrix) == 2 and
         all(type(row) in (tuple, list) and len(row) == 2 for row in matrix), '2x2 matrix')
    a, b, c, d = (exact(v) for row in matrix for v in row)
    # Optimize the lower/upper envelopes at their endpoints and possible kink.
    den = a-b-c+d
    need(den != 0, 'declared nondegenerate envelope witness')
    ps, qs = {Q(0), Q(1)}, {Q(0), Q(1)}
    if 0 < (d-c)/den < 1:
        ps.add((d-c)/den)
    if 0 < (d-b)/den < 1:
        qs.add((d-b)/den)
    security = {p: min(p*a+(1-p)*c, p*b+(1-p)*d) for p in ps}
    exposure = {q: max(q*a+(1-q)*b, q*c+(1-q)*d) for q in qs}
    v, w = max(security.values()), min(exposure.values())
    return tuple(sorted(p for p in ps if security[p] == v)), tuple(sorted(q for q in qs if exposure[q] == w)), v, w


def menu_accounts(low_acceptance=1, buyer_cash=5, seller_cash=2):
    accept, bc, sc = map(exact, (low_acceptance, buyer_cash, seller_cash))
    need(0 <= accept <= 1 and min(bc, sc) >= 0, 'acceptance/cash domain')
    types, quantities, charges = (Q(1), Q(3)), (Q(1), Q(2)), (Q(1), Q(7, 2))
    cost = tuple(q*q/2 for q in quantities)
    need(max(cost) <= sc and max(charges) <= bc, 'menu must be actually prefunded')
    table = tuple(tuple(t*q-p for q, p in zip(quantities, charges)) for t in types)
    profit = tuple(p-k for p, k in zip(charges, cost))
    frequencies = (accept/2, Q(1, 2))
    seller = sum(p*f for p, f in zip(profit, frequencies))
    buyer = sum(table[i][i]*frequencies[i] for i in range(2))
    real = sum((types[i]*quantities[i]-cost[i])*frequencies[i] for i in range(2))
    return table, cost, profit, seller, buyer, real


def affine_certificate(a, b, x):
    a, b, x = map(exact, (a, b, x))
    need(0 <= b < 1 and 0 <= a and a+b <= 1 and 0 <= x <= 1, 'invariant contraction/candidate domain')
    fixed = a/(1-b)
    residual = abs(x-a-b*x)
    return fixed, residual, residual/(1-b)


def wage_vertices():
    # All six halfspaces are a*w0+b*w1 >= c. Cash4 makes the polygon compact.
    rows = ((1,0,0),(0,1,0),(-1,0,-4),(0,-1,-4),
            (-Q(1,2),Q(1,2),1),(Q(1,4),Q(3,4),1))
    feasible = set()
    for (a,b,c),(d,e,f) in combinations(rows,2):
        det = a*e-b*d
        if not det:
            continue
        point = (Q(c*e-b*f,det),Q(a*f-c*d,det))
        if all(x*point[0]+y*point[1] >= z for x,y,z in rows):
            feasible.add(point)
    price = lambda p: (p[0]+3*p[1])/4
    low = min(map(price,feasible))
    return tuple(sorted(feasible)), tuple(p for p in sorted(feasible) if price(p) == low), low


def agent_actions(w0, w1, payroll=4):
    w0, w1, payroll = map(exact, (w0,w1,payroll))
    need(min(w0,w1,payroll) >= 0 and max(w0,w1) <= payroll, 'limited liability and actual payroll')
    return (3*w0+w1)/4, (w0+3*w1)/4-1


def hicks_squares(px, py, target):
    px, py, target = map(exact,(px,py,target))
    need(min(px,py,target) > 0, 'positive Hicksian price/target domain')
    return target*target*py/px, target*target*px/py, 4*target*target*px*py


def grim(delta):
    d = exact(delta)
    need(0 <= d < 1, 'discounted infinite-horizon domain')
    follow = Q(3)/(1-d)
    deviate = 5+d/(1-d)
    return follow, deviate, follow-deviate


def mechanism(theta, report, cash=4):
    t, r, cash = map(exact, (theta,report,cash))
    need(0 <= t <= 4 and 0 <= r <= 4 and cash >= 2, 'declared type/report/full-menu funding')
    probability, fee = r/4, r*r/8
    return probability, fee, t*probability-fee


EDGES = ((0,1),(0,2),(1,2))
GRAPHS = tuple(frozenset(s) for k in range(4) for s in combinations(EDGES,k))


def network(edges, rho=Q(1,2), cost=Q(9,16), transfer=Q(0), cash=Q(2)):
    need(type(edges) in (tuple,list,set,frozenset), 'finite link collection')
    need(all(type(e) is tuple and e in EDGES for e in edges) and len(set(edges)) == len(edges), 'canonical distinct three-node edges')
    rho,cost,transfer,cash = map(exact,(rho,cost,transfer,cash))
    need(0 < rho < 1 and min(cost,transfer,cash) >= 0, 'network parameter domain')
    adjacency = [set() for _ in range(3)]
    for i,j in edges:
        adjacency[i].add(j);adjacency[j].add(i)
    benefits = []
    for start in range(3):
        distance = {start:0}; queue = deque([start])
        while queue:
            i=queue.popleft()
            for j in adjacency[i]:
                if j not in distance:
                    distance[j]=distance[i]+1;queue.append(j)
        benefits.append(sum((rho**d for j,d in distance.items() if j != start), Q(0)))
    maintenance = [cost*len(a) for a in adjacency]
    outgoing,incoming = [Q(0)]*3,[Q(0)]*3
    for leaf in (0,2):
        if 1 in adjacency[leaf]:
            outgoing[leaf] += transfer;incoming[1] += transfer
    due=tuple(maintenance[i]+outgoing[i] for i in range(3))
    need(max(due) <= cash, 'prefunding before benefits or transfer receipts')
    utility=tuple(benefits[i]-maintenance[i]-outgoing[i]+incoming[i] for i in range(3))
    return {'benefits':tuple(benefits),'maintenance':tuple(maintenance),'incoming':tuple(incoming),
            'outgoing':tuple(outgoing),'due':due,'utility':utility,'welfare':sum(utility)}


def link_deviations(edges, rho=Q(1,2), cost=Q(9,16), transfer=Q(0)):
    start=network(edges,rho,cost,transfer)['utility'];result=[]
    for e in EDGES:
        present=e in edges;changed=frozenset(edges ^ {e})
        after=network(changed,rho,cost,transfer)['utility']
        gains=tuple(after[i]-start[i] for i in e)
        profitable=max(gains)>0 if present else min(gains)>=0 and max(gains)>0
        result.append((e,present,gains,profitable))
    return result


def da(proposers, receivers):
    need(len(proposers)==2 and len(receivers)==2, 'two-by-two finite DA witness')
    for ranking in tuple(proposers)+tuple(receivers):
        need(type(ranking) in (tuple,list) and len(set(ranking))==len(ranking)
             and all(type(x) is int and 0<=x<2 for x in ranking), 'strict ordered-subset report')
    next_choice=[0,0];held=[None,None];queue=deque((0,1));proposals=[]
    while queue:
        p=queue.popleft()
        if next_choice[p] == len(proposers[p]):
            continue
        r=proposers[p][next_choice[p]];next_choice[p]+=1;proposals.append((p,r))
        if p not in receivers[r]:
            queue.append(p);continue
        old=held[r]
        if old is None or receivers[r].index(p)<receivers[r].index(old):
            held[r]=p
            if old is not None:queue.append(old)
        else:
            queue.append(p)
    matches=[None,None]
    for r,p in enumerate(held):
        if p is not None:matches[p]=r
    return tuple(matches),tuple(proposals)


class Fragments(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack=[];self.ids=set();self.prompts={};self.answers={};self.marks={}
        self.points={};self.sources={};self.links=set();self.capture=[]

    def handle_starttag(self,tag,attrs):
        a=dict(attrs);need(len(a)==len(attrs),'duplicate attribute')
        need(tag not in ('script','iframe','object'),'static reader content')
        if 'id' in a:
            need(a['id'] not in self.ids,'duplicate support ID');self.ids.add(a['id'])
        depth=len(self.stack)+1
        if 'data-points' in a:
            need(tag=='li' and 'id' in a and a['data-points'].isdigit(),'scored li')
            key=a['id'];need(key not in self.prompts,'duplicate scored prompt')
            self.points[key]=int(a['data-points']);self.prompts[key]=''
            self.capture.append((depth,self.prompts,key))
        if 'data-solution-for' in a:
            key=a['data-solution-for'];need(key not in self.answers,'duplicate answer')
            need(any(t=='details' and 'solutions' in d.get('class','').split() for t,d in self.stack),'answer disclosure')
            self.answers[key]='';self.capture.append((depth,self.answers,key))
        if 'data-check' in a:
            key=a['data-check'];need(key not in self.marks,'duplicate numeric marker')
            self.marks[key]='';self.capture.append((depth,self.marks,key))
        if 'href' in a:self.links.add(a['href'])
        if 'data-source' in a:
            key=a['data-source'];url=a.get('href')
            need(key not in self.sources or self.sources[key]==url,'inconsistent source route')
            self.sources[key]=url
        if tag not in ('br','hr','img','meta','link','input','wbr'):self.stack.append((tag,a))

    def handle_data(self,data):
        for _,dest,key in self.capture:dest[key]+=data

    def handle_endtag(self,tag):
        need(self.stack and self.stack[-1][0]==tag,'unbalanced fragment')
        depth=len(self.stack);self.capture=[c for c in self.capture if c[0]!=depth];self.stack.pop()


def display(x):
    if type(x) in (tuple,list):return '('+','.join(display(y) for y in x)+')'
    return str(x)


def normal(text):
    return ''.join(text.replace('−','-').split())


def check(root=None):
    need(root is None or isinstance(root,(str,Path)),'root path')
    base=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    raw={p:(base/p).read_bytes() for p in FILES}
    comparisons=0;rejections=0
    def eq(a,b,label):
        nonlocal comparisons
        comparisons+=1;need(a==b,label+': '+repr(a)+' != '+repr(b))
    def reject(fn,label):
        nonlocal rejections
        try:fn()
        except ValueError:rejections+=1
        else:raise ValueError('accepted invalid case: '+label)
    for p,size,digest in AUTHOR:
        eq((len(raw[p]),sha256(raw[p]).hexdigest()),(size,digest),'frozen author '+p)
    page=Fragments()
    for p in FILES[:2]:
        page.feed(raw[p].decode());eq((page.stack,page.capture),([],[]),'complete reader fragment')
    page.close()
    points={f'v13-d{i}':5 for i in range(1,9)}
    points.update({f'v13-o{i}':4 for i in range(1,6)})
    points.update({f'v13-r{i}':10 for i in range(1,6)})
    eq(page.points,points,'all exact point allocations')
    eq(set(page.answers),set(points),'all18 paired answers')
    for letter,total in (('d',40),('o',20),('r',50)):
        eq(sum(v for k,v in points.items() if k.startswith('v13-'+letter)),total,'section total')
    eq({'diagnostic','exam-rules','oral-transfer','retention','remediation','notation-index','concept-index',
        'volume-synthesis','assessment-source-scope'} <= page.ids,True,'all required support sections')
    eq('accepts employment when indifferent' in page.prompts['v13-o4'],True,'resolved employment tie in exact prompt')
    eq('conditional on accepting employment' in page.answers['v13-o4'],True,'resolved effort versus participation scope')
    eq('curriculum.html#v14' in page.links,True,'planned macro route')
    eq(len([u for u in page.links if not u.startswith(('http:','https:'))]),73,'local route inventory')
    m={};interventions=[]
    choices=((('a','b'),'a'),(('b','c'),'b'),(('a','c'),'c'))
    eq(rationalizers(choices),[],'no strict transitive rationalizer')
    eq(rationalizers(choices[:2]+((('a','c'),'a'),)),[('a','b','c')],'one-choice repair')
    x,value=concave_capacity(6,4);m.update({'d2-choice':x[0],'d2-value':value,'d2-multiplier':Q(6)-x[0]})
    eq(concave_capacity(6,7),((Q(6),),Q(18)),'loosening capacity eventually makes bound slack')
    eq((Q(6)-Q(4),6*Q(4)-Q(4)**2/2),(Q(2),Q(16)),'local envelope and global square')
    w=wealth_lottery((4,16),(Q(1,2),Q(1,2)))
    m.update(dict(zip(('d3-wealth','d3-utility','d3-ce','d3-premium'),w)))
    eq(wealth_lottery((4,16),(Q(1,4),Q(3,4))),(Q(13),Q(7,2),Q(49,4),Q(3,4)),'probability transfer changes CE nonlinearly')
    for r in (Q(1),Q(2)):
        a,b,z=exchange(2,2,r)
        eq((r*a[0]+a[1],r*b[0]+b[1]),(2*r,2),'both owned budgets')
        eq(r*z[0]+z[1],0,'value balance')
        if r==2:eq(z,(-Q(1,2),Q(1)),'nonclearing zero-value excess')
    m['d4-price']=Q(2,2)
    a,b,z=exchange(4,2,Q(1,2));eq((a,b,z),((2,1),(2,1),(0,0)),'changed endowment changes equilibrium relative price')
    p,q,v,upper=minimax(((2,-1),(-2,1)))
    eq((p,q,v,upper),((Q(1,2),),(Q(1,3),),Q(0),Q(0)),'complete envelope optimum')
    pure=[];matrix=((2,-1),(-2,1))
    for i,j in product(range(2),repeat=2):
        if matrix[i][j]>=matrix[1-i][j] and matrix[i][j]<=matrix[i][1-j]:pure.append((i,j))
    eq(pure,[],'no pure mutual best reply')
    m.update({'d5-row':p[0],'d5-column':q[0],'d5-value':v})
    # Normal-form columns Fight/Accommodate; rows Out/In.
    normal_game=(((0,3),(0,3)),((-1,0),(2,2)))
    ne=[]
    for i,j in product(range(2),repeat=2):
        if normal_game[i][j][0]>=normal_game[1-i][j][0] and normal_game[i][j][1]>=normal_game[i][1-j][1]:ne.append((i,j))
    eq(ne,[(0,0),(1,1)],'all pure normal-form Nash profiles')
    eq([x for x in ne if normal_game[1][x[1]][1]==max(cell[1] for cell in normal_game[1])],[(1,1)],'proper-subgame filter')
    interventions.append('choice-cycle repair, changed capacity/risk/endowment and complete finite strategic supports')
    table,cost,profit,seller,buyer,real=menu_accounts()
    eq(table,((0,-Q(3,2)),(2,Q(5,2))),'all menu/outside comparisons')
    eq(seller+buyer,real,'transfer cancellation')
    for q,fee,c in zip((1,2),(Q(1),Q(7,2)),cost):
        eq((5-fee)+(2-c+fee),7-c,'actual final cash after production and settlement')
    m.update({'d7-profits':profit,'d7-mean-profit':seller,'d7-buyer':buyer,'d7-total':real})
    refusal=menu_accounts(0);eq(refusal[3:],(Q(3,4),Q(5,4),Q(2)),'outside tie changes realized trade and profit')
    fixed,residual,bound=affine_certificate(Q(1,2),Q(1,4),Q(7,10))
    m.update({'d8-fixed':fixed,'d8-residual':residual,'d8-bound':bound})
    eq(bound,abs(Q(7,10)-fixed),'attained affine distance certificate')
    eq(affine_certificate(Q(1,4),Q(1,2),Q(7,10)),(Q(1,2),Q(1,10),Q(1,5)),'changed contraction constant')
    m.update({'o1-before':(3,2),'o1-after':(3,4)})
    eq(3>2 and 3<2*2,True,'positive own rescaling reverses the interpersonal sum')
    for z in (Q(0),Q(2,5),Q(1)):
        profile=(z,1-z)
        eq(tuple(max(Q(0),1-profile[1-i]) for i in range(2)),profile,'continuum witness with unique own replies')
    interventions.append('participation versus effort/report ties, real cash timing and numerical stability constant')
    vertices,optimal,mean=wage_vertices()
    eq(optimal,((Q(0),Q(2)),),'unique global wage-polygon optimum')
    low,high=agent_actions(*optimal[0]);eq((low,high),(Q(1,2),Q(1,2)),'H/L tie distinct from strict participation')
    m.update({'o4-wages':optimal[0],'o4-mean':mean,'o4-rent':high,'o4-high-profit':3-mean,'o4-low-profit':Q(1)})
    low0,high0=agent_actions(0,0);eq((low0,high0),(0,-1),'strict low effort only conditional on zero-utility participation')
    low1,high1=agent_actions(0,Q(21,10));eq(high1-low1,Q(1,20),'strict-IC nearby feasible wage')
    # Report-independent-menu witnesses include every ordered subset, including outside.
    reports=((),(0,),(1,),(0,1),(1,0));truth=((0,1),(0,1));priorities=((1,0),(0,1))
    menus=[];report_checks=0
    for agent in range(2):
        refusing=list(truth);refusing[agent]=()
        _,offers=da(priorities,tuple(refusing))
        menu={institution for institution,recipient in offers if recipient==agent};menus.append(menu)
        for report in reports:
            profile=list(truth);profile[agent]=report
            actual=da(tuple(profile),priorities)[0][agent]
            chosen=next((r for r in report if r in menu),None)
            eq(actual,chosen,'every ordered-subset report selects its reported-best fixed-menu member');report_checks+=1
    eq(menus,[{1},{0,1}],'fixed menus with explicit outside')
    eq(da(((0,),(0,1)),priorities)[0][0],None,'one-name sincere report can be rejected')
    eq(da(((1,),(0,1)),priorities)[0][0],1,'one-name deviation changes unavailable-full-type problem')
    interventions.append('global wage vertices, strict-IC limit and complete finite ordered-subset matching reports')
    m['r1-marshallian']=(Q(12)/(2*2),Q(12)/(2*1))
    eq(hicks_squares(2,1,3),(Q(9,2),Q(18),Q(72)),'exact squared Hicksian bundle and cost')
    eq(hicks_squares(1,4,3),(Q(36),Q(9,4),Q(144)),'changed-price dual witness')
    eq((2*Q(3,2)+3)**2*2,Q(72),'radical spending square')
    # Entire coefficient identity: 16 - ((x-4)^2+(y-4)^2)/2.
    aggregate_coefficients=(Q(0),Q(4),Q(4),-Q(1,2),-Q(1,2))
    completed_coefficients=(Q(16)-Q(16),Q(4),Q(4),-Q(1,2),-Q(1,2))
    eq(aggregate_coefficients,completed_coefficients,'global welfare polynomial identity')
    utility=lambda own,other:2*(exact(own)+exact(other))-exact(own)**2/2
    ne=(Q(2),Q(2));planner=(Q(4),Q(4))
    nu=tuple(utility(ne[i],ne[1-i]) for i in range(2));pu=tuple(utility(planner[i],planner[1-i]) for i in range(2))
    m.update({'r2-nash':ne,'r2-nash-utilities':nu,'r2-nash-welfare':sum(nu),
              'r2-planner':planner,'r2-planner-utilities':pu,'r2-planner-welfare':sum(pu),'r2-deviation':utility(2,Q(4))})
    c,d,gap=grim(Q(3,5));m.update({'r3-threshold':'δ≥1/2','r3-cooperate':c,'r3-deviate':d,'r3-margin':gap})
    for delta,sign in ((Q(0),-1),(Q(1,2),0),(Q(3,5),1)):
        margin=grim(delta)[2]
        eq((margin>0)-(margin<0),sign,'exact patience boundary')
        eq((1-delta)*margin,-2+4*delta,'full linear incentive identity')
    eq(Q(3,5)**2*gap,Q(9,25),'later first-deviation margin discounts the same continuation comparison')
    interventions.append('global primal/dual and welfare certificates, with discounted first-deviation boundaries')
    for theta,report in ((0,4),(2,3),(4,0)):
        truth_u=mechanism(theta,theta)[2];off_u=mechanism(theta,report)[2]
        eq(truth_u-off_u,Q(theta-report)**2/8,'global expected-utility report square')
    revenue=Q(1,4)*Q(1,8)*Q(4)**3/3
    m.update({'r4-max-fee':mechanism(4,4)[1],'r4-revenue':revenue,'r4-posted-revenue':Q(2)*(4-2)/4})
    probability,fee,u=mechanism(2,2);eq((probability,fee,u),(Q(1,2),Q(1,2),Q(1,2)),'interim utility with negative losing realization')
    eq(-fee,-Q(1,2),'ex-post participation counterexample')
    interventions.append('lottery expected truthfulness versus ex-post participation and alternative revenue')
    welfare={g:network(g)['welfare'] for g in GRAPHS}
    stable=[g for g in GRAPHS if not any(a[3] for a in link_deviations(g))]
    eq(stable,[frozenset()],'all eight original stability tests')
    eq({g for g in GRAPHS if welfare[g]==max(welfare.values())},{g for g in GRAPHS if len(g)==2},'all three efficient labeled paths')
    target=frozenset(((0,1),(1,2)));fee=Q(1,8);led=network(target,transfer=fee)
    deviations=link_deviations(target,transfer=fee)
    eq(tuple(a[3] for a in deviations),(False,False,False),'all target edge changes')
    m.update({'r5-welfare':tuple(welfare[g] for g in (frozenset(),frozenset(((0,1),)),target,frozenset(EDGES))),
              'r5-payoffs':led['utility'],'r5-keep':led['utility'][1]-network(frozenset(((1,2),)),transfer=fee)['utility'][1],
              'r5-add':network(frozenset(EDGES),transfer=fee)['utility'][0]-led['utility'][0],
              'r5-leaf-funding':2*Q(9,16)+fee,'r5-center-funding':2*Q(9,16),'r5-first-link':2*(Q(1,2)-Q(9,16))})
    for g in GRAPHS:
        row=network(g,transfer=fee)
        eq(sum(row['incoming']),sum(row['outgoing']),'every-graph balanced transfers')
        eq(row['welfare'],welfare[g],'real resources unaffected by pure transfers')
        eq(max(row['due'])<=2,True,'every graph actually prefunded before receipts')
    for transfer,ok in ((Q(0),False),(Q(1,16),True),(Q(1,8),True),(Q(3,16),True),(Q(1,4),False)):
        eq(not any(a[3] for a in link_deviations(target,transfer=transfer)),ok,'complete weak-boundary transfer interval witness')
    boundary=[g for g in GRAPHS if not any(a[3] for a in link_deviations(g,cost=Q(1,2)))]
    eq(set(boundary),{frozenset()}|{g for g in GRAPHS if len(g)==2},'both-weak-one-strict addition boundary')
    eq(sum(network(frozenset(((0,1),)),transfer=fee)['utility']),-Q(1,8),'balanced payment cannot repair negative first-link surplus')
    interventions.append('complete graph enumeration, shortest-path benefits, real prefunding and weak consent boundaries')
    eq(set(m),set(page.marks),'all47 visible result anchors independently reconstructed')
    for key,value in m.items():eq(normal(page.marks[key]),normal(display(value)),'visible '+key)
    invalid=[
        (lambda:exact(True),'bool scalar'),(lambda:exact(0.5),'float scalar'),(lambda:exact('1/2'),'numeric string'),
        (lambda:exact(float('nan')),'NaN scalar'),(lambda:exact(float('inf')),'infinite scalar'),
        (lambda:rationalizers(((('a','b'),'c'),)*3),'choice outside menu'),
        (lambda:concave_capacity(6,-1),'negative capacity'),
        (lambda:wealth_lottery((-1,4),(Q(1,2),Q(1,2))),'negative wealth'),
        (lambda:wealth_lottery((4,16),(Q(1,2),Q(1,4))),'probability mass'),
        (lambda:exchange(2,2,0),'zero price'),(lambda:exchange(-1,2,1),'negative endowment'),
        (lambda:minimax(((1,1),(1,1))),'degenerate envelope outside helper scope'),
        (lambda:menu_accounts(Q(3,2)),'acceptance above one'),
        (lambda:menu_accounts(buyer_cash=3),'unfunded full menu charge'),
        (lambda:menu_accounts(seller_cash=1),'unfunded prior production'),
        (lambda:affine_certificate(0,1,Q(1,2)),'noncontraction'),
        (lambda:affine_certificate(Q(3,4),Q(1,2),Q(1,2)),'noninvariant map'),
        (lambda:agent_actions(-1,2),'negative wage'),(lambda:agent_actions(0,5),'payroll exceeds endowed cash'),
        (lambda:hicks_squares(0,1,3),'zero Hicksian price'),(lambda:hicks_squares(1,1,0),'target outside positive domain'),
        (lambda:grim(1),'undiscounted infinite sum'),(lambda:grim(-1),'negative discount'),
        (lambda:mechanism(5,1),'type outside support'),(lambda:mechanism(1,-1),'negative report'),
        (lambda:mechanism(1,1,1),'full menu not funded'),
        (lambda:network(((0,0),)),'self link'),(lambda:network(((0,1),(0,1))),'duplicate link'),
        (lambda:network(target,rho=1),'network discount boundary outside stated domain'),
        (lambda:network(target,cost=-1),'negative maintenance'),(lambda:network(target,transfer=-1),'negative stated transfer'),
        (lambda:network(target,transfer=fee,cash=Q(1,2)),'insufficient pre-benefit cash'),
        (lambda:da(((0,0),()),((0,1),(1,0))),'repeated report name'),
        (lambda:strict_json('{"x":1,"x":2}'),'duplicate JSON'),
        (lambda:strict_json('{"x":NaN}'),'JSON NaN'),(lambda:strict_json('{"x":1e9999}'),'JSON overflow'),
    ]
    for fn,label in invalid:reject(fn,label)
    source=strict_json(raw[FILES[3]]);author=strict_json(raw[FILES[4]]);peer=strict_json(raw[REVIEW])
    source_routes={'v05-c02-consumer':'https://ocw.mit.edu/courses/14-121-microeconomic-theory-i-fall-2015/ea9f11b15ace05e7bfd31d58ae48beb9_MIT14_121F15_2S.pdf',
                   'v13-c06-yildiz-games2022':'https://ocw.mit.edu/courses/14.126-game-theory-spring-2024/mit14_126_s24_yildiz-lecture-notes.pdf'}
    eq(page.sources,source_routes,'exact inspected-reuse source identities')
    eq({s['id']:s['url'] for s in source['sources']},source_routes,'source record matches reader')
    eq(set(author['prompt_audit']),set(points),'author audits every exact prompt')
    eq(author['open_findings'],[],'author has no unresolved issue')
    for row in author['bindings']:
        data=raw[row['path']];eq((len(data),sha256(data).hexdigest()),(row['bytes'],row['sha256']),'author nonself binding')
    eq({a['path'] for a in peer['bindings']},set(FILES[:-1]),'peer binds five authors and own checker only')
    for row in peer['bindings']:
        data=raw[row['path']];eq((len(data),sha256(data).hexdigest()),(row['bytes'],row['sha256']),'peer final binding')
    eq(peer['unresolved_findings'],[],'peer has no unresolved finding')
    eq({p:(base/p).read_bytes() for p in FILES},raw,'seven runtime payloads unchanged')
    summary={'volume':'v13','component':'support_peer','status':'passed','comparisons':comparisons,
             'domain_rejections':rejections,'solved_prompts':18,'result_markers':len(m),
             'diagnostic_points':40,'oral_points':20,'retention_points':50,'intervention_groups':len(interventions),
             'interventions':interventions,'graphs_enumerated':len(GRAPHS),'matching_report_witnesses':report_checks,
             'wage_polygon_vertices':len(vertices),'runtime_files':7,'author_checker_executed':False,
             'scope':'Exact primitive reconstructions and focused interventions, together with full separate proof/prompt reading; finite witnesses do not replace universal proofs.'}
    json.dumps(summary,allow_nan=False)
    return summary


if __name__=='__main__':
    need(len(sys.argv)==1,'silent CLI has no arguments')
    check()
