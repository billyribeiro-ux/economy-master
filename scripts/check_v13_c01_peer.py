"""Separate exact peer oracles for preference/choice theory; six read-only files.

The author checker is read and bound, never imported as an arithmetic oracle.
Analytic proof judgments are in the peer record; finite checks do not prove an
infinite-domain representation theorem. Import, check(), and CLI are quiet.
"""
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from itertools import combinations, product
from pathlib import Path
import ast
import json
import math
import re
import sys

AUTHOR = ('content/chapters/v13-c01.html', 'scripts/check_v13_c01.py',
          'content/reviews/v13-c01-sources.json', 'content/reviews/v13-c01-author.json')
SELF = 'scripts/check_v13_c01_peer.py'
RECORD = 'content/reviews/v13-c01-peer.json'
SOURCES = {'v05-c01-mit-preferences', 'v05-c01-bergstrom-revealed',
           'v13-c01-varian-demand1982'}


def require(ok, label):
    if not ok:
        raise ValueError('C01 peer: ' + label)


class Audit:
    def __init__(self):
        self.comparisons = 0
        self.rejections = 0
        self.interventions = 0

    def equal(self, actual, expected, label):
        require(actual == expected, label + ': ' + repr(actual)[:140])
        self.comparisons += 1

    def reject(self, action, label):
        try:
            action()
        except (ValueError, SyntaxError, ZeroDivisionError):
            self.rejections += 1
        else:
            raise ValueError('C01 peer accepted invalid ' + label)


def strict_json(text):
    def pairs(items):
        out = {}
        for key, value in items:
            require(key not in out, 'duplicate JSON key')
            out[key] = value
        return out
    def fail(value):
        raise ValueError('nonfinite JSON ' + value)
    value = json.loads(text, object_pairs_hook=pairs, parse_constant=fail)
    def scan(item):
        if isinstance(item, float):
            require(math.isfinite(item), 'overflowed JSON number')
        elif isinstance(item, dict):
            for v in item.values(): scan(v)
        elif isinstance(item, list):
            for v in item: scan(v)
    scan(value)
    return value


def scalar(value):
    require(type(value) in (int, F), 'exact scalar excludes booleans/floats/strings')
    value = F(value)
    require(abs(value) <= 10000 and value.denominator <= 1000000, 'bounded scalar')
    return value


def numeric(text):
    """Only integers, signed rationals and tuple/list syntax are accepted."""
    require(type(text) is str and len(text) <= 2000, 'bounded numeric display')
    node = ast.parse(text.replace('−', '-').strip(), mode='eval').body
    def visit(n):
        if isinstance(n, ast.Constant): return scalar(n.value)
        if isinstance(n, (ast.Tuple, ast.List)):
            require(len(n.elts) <= 20, 'bounded displayed tuple')
            return tuple(visit(v) for v in n.elts)
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.UAdd, ast.USub)):
            v = visit(n.operand)
            require(type(v) is F, 'unary scalar')
            return v if isinstance(n.op, ast.UAdd) else -v
        if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Div):
            a, b = visit(n.left), visit(n.right)
            require(type(a) is F and type(b) is F and b != 0, 'rational division')
            return scalar(a/b)
        raise ValueError('numeric display grammar')
    return visit(node)


def dot(a, b):
    require(len(a) == len(b), 'dot dimensions')
    return sum((x*y for x, y in zip(a, b)), F(0))


def subsets(items):
    return tuple(frozenset(s) for k in range(1, len(items)+1) for s in combinations(items, k))


def ordered_partitions(items):
    """Insert each new alternative into a tie block or between ordered blocks."""
    require(type(items) is tuple and 1 <= len(items) <= 6 and len(set(items)) == len(items),
            'bounded distinct alternatives')
    out = [((items[0],),)]
    for new in items[1:]:
        next_ = []
        for blocks in out:
            for k in range(len(blocks)):
                next_.append(blocks[:k] + (blocks[k]+(new,),) + blocks[k+1:])
            for k in range(len(blocks)+1):
                next_.append(blocks[:k] + ((new,),) + blocks[k:])
        out = next_
    return out


def maxima(blocks, menu):
    require(bool(menu), 'nonempty menu')
    for block in reversed(blocks):
        chosen = frozenset(block) & menu
        if chosen: return chosen
    raise ValueError('menu has no known alternative')


def reports_valid(universe, reports):
    require(type(universe) is tuple and 1 <= len(universe) <= 6 and
            all(type(x) is str and x for x in universe) and len(set(universe)) == len(universe),
            'finite named universe')
    require(type(reports) in (list, tuple) and 1 <= len(reports) <= 63, 'bounded reports')
    seen = set()
    for row in reports:
        require(type(row) in (list, tuple) and len(row) == 2, 'report pair')
        menu, choice = row
        require(type(menu) is frozenset and type(choice) is frozenset and bool(choice)
                and choice <= menu <= set(universe), 'complete feasible choice report')
        require(menu not in seen, 'duplicate menu')
        seen.add(menu)
    return reports


def correspondence_warp(reports):
    for menu, chosen in reports:
        for other, later in reports:
            common = menu & other
            if later & common and (chosen & common) - later:
                return False
    return True


def closure(edges):
    require(type(edges) in (tuple, list) and 1 <= len(edges) <= 6, 'bounded graph')
    n = len(edges)
    require(all(type(row) in (tuple, list) and len(row) == n for row in edges), 'square graph')
    require(all(type(v) is bool for row in edges for v in row), 'Boolean graph')
    r = [[v or i == j for j, v in enumerate(row)] for i, row in enumerate(edges)]
    # Relational composition with the admitted intermediate set; no BFS helper.
    for k in range(n):
        for i in range(n):
            for j in range(n): r[i][j] = r[i][j] or (r[i][k] and r[k][j])
    return tuple(tuple(row) for row in r)


def menu_criterion(universe, reports):
    reports_valid(universe, reports)
    index = {x:i for i,x in enumerate(universe)}
    edges = [[i == j for j in range(len(universe))] for i in range(len(universe))]
    strict = []
    for menu, chosen in reports:
        for x in chosen:
            for y in menu:
                edges[index[x]][index[y]] = True
                if y not in chosen: strict.append((index[x],index[y]))
    reach = closure(edges)
    return not any(reach[j][i] for i,j in strict)


def budget_data(prices, quantities):
    require(type(prices) in (tuple,list) and 1 <= len(prices) <= 6, 'bounded observations')
    require(type(quantities) in (tuple,list) and len(prices) == len(quantities), 'observation counts')
    require(type(prices[0]) in (tuple,list) and 1 <= len(prices[0]) <= 4, 'bounded goods')
    dim = len(prices[0])
    def rows(value):
        require(all(type(row) in (tuple,list) and len(row) == dim for row in value), 'commodity dimensions')
        return tuple(tuple(scalar(v) for v in row) for row in value)
    p, x = rows(prices), rows(quantities)
    require(all(v > 0 for row in p for v in row), 'strict price positivity')
    require(all(v >= 0 for row in x for v in row), 'nonnegative consumption')
    cross = tuple(tuple(dot(row, point) for point in x) for row in p)
    difference = tuple(tuple(row[j]-row[i] for j in range(len(row))) for i,row in enumerate(cross))
    direct = tuple(tuple(v <= 0 for v in row) for row in difference)
    reach = closure(direct)
    bad = tuple((i,j) for i in range(len(x)) for j in range(len(x))
                if reach[i][j] and difference[j][i] < 0)
    pair = all(not direct[i][j] or difference[j][i] >= 0
               for i in range(len(x)) for j in range(len(x)))
    return p,x,cross,difference,direct,reach,bad,pair


def afriat(prices, quantities):
    p,x,e,d,edges,r,bad,pair = budget_data(prices, quantities)
    require(not bad, 'GARP required for the positive construction')
    remaining = set(range(len(x)));classes = []
    while remaining:
        i = next(i for i in sorted(remaining)
                 if not any(r[j][i] and not r[i][j] for j in remaining))
        group = tuple(j for j in sorted(remaining) if r[i][j] and r[j][i])
        classes.append(group);remaining.difference_update(group)
    levels = [None]*len(x);lam = [None]*len(x);old = []
    for group in classes:
        if not old: level,mult = F(1),F(1)
        else:
            level = min(v for i in group for j in old
                        for v in (levels[j],levels[j]+lam[j]*d[j][i]))
            require(all(d[i][j] > 0 for i in group for j in old), 'proved denominator positivity')
            mult = max([F(1)]+[(levels[j]-level)/d[i][j] for i in group for j in old])
        for i in group: levels[i],lam[i] = level,mult
        old.extend(group)
    return tuple(levels),tuple(lam),tuple(classes)


def envelope(prices, quantities, levels, multipliers):
    p,x,e,d,*_ = budget_data(prices, quantities)
    require(type(levels) in (list,tuple) and type(multipliers) in (list,tuple)
            and len(levels) == len(x) == len(multipliers), 'certificate dimensions')
    u,lam = tuple(map(scalar,levels)),tuple(map(scalar,multipliers))
    require(all(v > 0 for v in lam), 'strict multiplier positivity')
    slack = tuple(tuple(u[i]+lam[i]*d[i][j]-u[j] for j in range(len(x))) for i in range(len(x)))
    require(all(v >= 0 for row in slack for v in row), 'all certificate inequalities')
    constants = tuple(u[i]-lam[i]*e[i][i] for i in range(len(x)))
    slopes = tuple(tuple(lam[i]*v for v in row) for i,row in enumerate(p))
    return constants,slopes,slack


def plane_values(cert, point):
    c,a,_ = cert
    require(type(point) in (list,tuple) and len(point) == len(a[0]), 'evaluation dimension')
    point = tuple(map(scalar,point));require(all(v >= 0 for v in point), 'evaluation orthant')
    return tuple(v+dot(row,point) for v,row in zip(c,a))


def linear_solve(rows, values):
    n = len(rows)
    require(1 <= n <= 4 and len(values) == n and all(len(row) == n for row in rows), 'small square system')
    a = [[F(v) for v in row]+[F(b)] for row,b in zip(rows,values)]
    for j in range(n):
        k = next((k for k in range(j,n) if a[k][j]),None)
        if k is None: return None
        a[j],a[k] = a[k],a[j]
        pivot = a[j][j];a[j] = [v/pivot for v in a[j]]
        for k in range(n):
            if k != j:
                amount = a[k][j];a[k] = [x-amount*y for x,y in zip(a[k],a[j])]
    return tuple(row[-1] for row in a)


def counterfactual(cert, income):
    income = scalar(income);require(income > 0, 'positive new income')
    c,a,_ = cert
    require(len(c) == 3 and all(len(row) == 3 for row in a), 'three-plane counterfactual')
    # Independent hypograph vertices, not the author's two-plane demand formula.
    constraints = [(tuple(-v for v in row)+(F(1),),b) for row,b in zip(a,c)]
    constraints += [(tuple(-F(i == j) for j in range(3))+(F(0),),F(0)) for i in range(3)]
    constraints += [((F(1),F(1),F(1),F(0)),income)]
    feasible = set()
    for chosen in combinations(range(7),4):
        q = linear_solve([constraints[i][0] for i in chosen],[constraints[i][1] for i in chosen])
        if q is not None and all(dot(row,q) <= b for row,b in constraints): feasible.add(q)
    require(bool(feasible), 'hypograph vertices exist')
    value = max(q[3] for q in feasible)
    optima = tuple(sorted(q[:3] for q in feasible if q[3] == value))
    # The analytic upper bound and its equality conditions independently certify
    # the whole budget; a finite vertex search alone is not the proof in prose.
    dual = linear_solve(((1,1),(a[0][0]-a[0][2],a[1][0]-a[1][2])),(1,0))
    require(dual is not None and all(w > 0 for w in dual), 'positive dual weights')
    slope = tuple(sum(dual[i]*a[i][j] for i in range(2)) for j in range(3))
    intercept = sum(dual[i]*c[i] for i in range(2))
    require(slope[0] == slope[2] > slope[1] and slope[0] > 0, 'global bound strict equality restrictions')
    upper = intercept+slope[0]*income
    require(len(optima) == 1 and value == upper, 'vertex and global upper bound agreement')
    q = optima[0];terms = plane_values(cert,q)
    require(q[1] == 0 and sum(q) == income and terms[0] == terms[1] == value <= terms[2], 'attained bound')
    require(a[0][0]-a[1][0] != a[0][2]-a[1][2], 'unique active-plane intersection')
    return q,value,terms,dual,(intercept,slope),len(feasible)


def printed_plane(text):
    text = text.replace('−','-').replace(' ','').replace('(','').replace(')','')
    for i,ch in enumerate(('₁','₂','₃'),1):text = text.replace('x'+ch,'x'+str(i))
    constant = F(0);slopes = [F(0)]*3
    for term in re.findall(r'[+-]?[^+-]+',text):
        if 'x' not in term:constant += F(term)
        else:
            match = re.fullmatch(r'([+-]?)([0-9]+(?:/[0-9]+)?)?x([123])',term)
            require(match is not None, 'printed affine grammar')
            sign,coefficient,index = match.groups()
            slopes[int(index)-1] += (-1 if sign == '-' else 1)*F(coefficient or '1')
    return constant,tuple(slopes)


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack=[];self.ids=[];self.cases=[];self.exercises=[];self.solutions=[]
        self.markers={};self.active=None;self.sources={};self.links=[];self.tables=[]
        self.table=None;self.caption=False;self.row=None;self.cell=None
    def handle_starttag(self,tag,attrs):
        a=dict(attrs);require(len(a)==len(attrs),'distinct attributes')
        ident=a.get('id');classes=a.get('class','').split()
        if ident:
            require(ident.startswith('v13-c01-') and ident not in self.ids,'unique prefixed ID')
            self.ids.append(ident)
        if 'worked' in classes:self.cases.append(ident)
        if tag=='li' and any('exercises' in c for _,c in self.stack):self.exercises.append(ident)
        if 'data-solution-for' in a:
            require(any('solutions' in c for _,c in self.stack),'disclosed solution')
            self.solutions.append(a['data-solution-for'])
        if 'data-calc' in a:
            require(self.active is None and a['data-calc'] not in self.markers,'distinct marker')
            self.active=a['data-calc'];self.markers[self.active]=''
        if 'href' in a:self.links.append(a['href'])
        if 'data-source' in a:self.sources[a['data-source']]=a.get('href')
        if tag=='table':self.table={'caption':'','rows':[]}
        if tag=='caption':self.caption=True
        if tag=='tr':self.row=[]
        if tag=='td':self.cell=''
        if tag not in ('br','hr','img','meta','input','link'):self.stack.append((tag,classes))
    def handle_data(self,text):
        if self.active:self.markers[self.active]+=text
        if self.caption:self.table['caption']+=text
        if self.cell is not None:self.cell+=text
    def handle_endtag(self,tag):
        require(bool(self.stack) and self.stack.pop()[0]==tag,'balanced HTML')
        if tag=='span':self.active=None
        if tag=='caption':self.caption=False
        if tag=='td':self.row.append(self.cell.strip());self.cell=None
        if tag=='tr' and self.table is not None and self.row:self.table['rows'].append(self.row)
        if tag=='table':self.tables.append(self.table);self.table=None
    def finish(self):
        self.close();require(not self.stack,'closed HTML')
        require(self.cases==['v13-c01-case'+str(i) for i in range(1,7)],'six worked cases')
        required=['v13-c01-ex'+str(i) for i in range(1,13)]
        require(self.exercises==self.solutions==required,'all twelve exact prompt/solution pairs')
        require(set(self.sources)==SOURCES,'three source routes')
        require(not any(h.startswith(('chapters/','projects/')) for h in self.links),'flat reader links')
        return self


def finite_oracles(audit):
    expected={};universe=tuple('abcdef');ranks=(2,1,0,2,1,0)
    blocks=(tuple('cf'),tuple('be'),tuple('ad'))
    reports=[]
    for menu in subsets(universe):
        choice=maxima(blocks,menu)
        def from_score(score):
            high=max(score[universe.index(x)] for x in menu)
            return frozenset(x for x in menu if score[universe.index(x)]==high)
        audit.equal(choice,from_score(ranks),'finite rank representation')
        audit.equal(choice,from_score(tuple(v*v for v in ranks)),'strict increasing range relabeling')
        reports.append((menu,choice))
    audit.equal(correspondence_warp(reports),True,'all full reports WARP')
    audit.equal(menu_criterion(universe,reports),True,'all full reports completion')
    expected.update({'finite-u':ranks,'finite-v':tuple(v*v for v in ranks),'finite-menu-count':len(reports),
                     'lottery-u':(F(ranks[0]+ranks[2],2),ranks[1]),
                     'lottery-v':(F(ranks[0]**2+ranks[2]**2,2),ranks[1]**2)})
    audit.equal(maxima((tuple('cf'),tuple('abde')),frozenset('ab')),frozenset('ab'),'weak map changes strict choice')
    omitted=[(m,frozenset('a') if m==frozenset(universe) else c) for m,c in reports]
    audit.equal(correspondence_warp(omitted),False,'omitting a genuine reported tie')
    audit.interventions+=1

    def diagonal(x):return (x[0]+x[1]+abs(x[0]-x[1])/2)/2
    points=tuple(tuple(F(v) for v in row) for row in ((4,0),(0,4),(2,2),(3,1)))
    labels=tuple(diagonal(x) for x in points);expected['diagonal-values']=labels
    audit.equal(labels[0]==labels[1]>labels[2],True,'nonconvex preference contour')
    for x in points+((F(0),F(0)),):
        audit.equal(diagonal((diagonal(x),diagonal(x))),diagonal(x),'diagonal equivalence including zero')
        for d in ((F(1,7),F(0)),(F(0),F(1,7))):
            audit.equal(diagonal(tuple(v+w for v,w in zip(x,d)))-diagonal(x)>=sum(d)/4,True,'positive one-coordinate lower bound')
    grid=tuple(product(range(5),repeat=2));codes=tuple(5*i+j for i,j in grid)
    expected.update({'lex-grid-size':len(grid),'lex-grid-max':max(codes),'lex-grid-comparisons':len(grid)**2})
    audit.equal(tuple(sorted(zip(codes,grid))),tuple(zip(range(25),sorted(grid))),'all finite lexicographic ranks')
    for epsilon in (F(1,1000),F(1),F(10)):
        gain=min(epsilon/2,F(1,2))
        audit.equal(0<gain<epsilon,True,'every positive weight witness')
    for n in (3,10,100):audit.equal((F(1,2)+F(1,n),0)>(F(1,2),1),True,'closed-graph counterexample sequence')
    audit.interventions+=1

    u3=tuple('abc');partitions3=ordered_partitions(u3);pairs=tuple(combinations(u3,2))
    singletons=[(frozenset((x,)),frozenset((x,))) for x in u3]
    successes=0;tested=0
    for choices in product(*(subsets(pair) for pair in pairs)):
        for full in subsets(u3):
            rs=singletons+[(frozenset(b),c) for b,c in zip(pairs,choices)]+[(frozenset(u3),full)]
            valid=[p for p in partitions3 if all(maxima(p,b)==c for b,c in rs)]
            passed=correspondence_warp(rs)
            audit.equal(passed,bool(valid),'all rich-domain reports: existence')
            if passed:audit.equal(len(valid),1,'pair information identifies unique weak order')
            successes+=passed;tested+=1
    audit.equal((len(partitions3),tested,successes),(13,189,13),'complete rich finite domain inventory')
    u4=tuple('abcd');rs=[(frozenset('abc'),frozenset('ab')),(frozenset('bcd'),frozenset('b')),(frozenset('ad'),frozenset('a'))]
    fits=[p for p in ordered_partitions(u4) if all(maxima(p,b)==c for b,c in rs)]
    vectors=sorted((tuple(next(i for i,block in enumerate(p) if x in block) for x in u4) for p in fits),reverse=True)
    expected['menu-orders']=tuple(vectors);expected['menu-order-count']=len(fits)
    audit.equal(menu_criterion(u4,rs),True,'restricted report completion')
    narrowed=[p for p in fits if maxima(p,frozenset('cd'))==frozenset('c')]
    audit.equal(len(narrowed),1,'one new comparison removes two completions')
    cycle=[(frozenset('ab'),frozenset('a')),(frozenset('bc'),frozenset('b')),(frozenset('ac'),frozenset('c'))]
    audit.equal((correspondence_warp(cycle),menu_criterion(u3,cycle)),(True,False),'restricted WARP misses strict cycle')
    failures=0
    for full in subsets(u3):
        audit.equal(correspondence_warp(cycle+[(frozenset(u3),full)]),False,'every nonempty triple completion')
        failures+=1
    expected['triple-failures']=failures;audit.interventions+=1
    return expected


def budget_oracles(audit,expected):
    x=tuple(tuple(F(i==j) for j in range(3)) for i in range(3))
    bad=((F(1),F(4,5),F(6,5)),(F(6,5),F(1),F(4,5)),(F(4,5),F(6,5),F(1)))
    good=bad[:2]+((F(6,5),F(6,5),F(1)),)
    wrong=budget_data(bad,x);right=budget_data(good,x)
    audit.equal((wrong[7],right[7]),(True,True),'declared tie-permitting pair WARP')
    audit.equal(wrong[5],((True,True,True),)*3,'cyclic closure')
    audit.equal(wrong[6],((0,2),(1,0),(2,1)),'all strict-reverse GARP failures')
    audit.equal(right[6],(),'all repaired paths pass')
    expected.update({'prices-bad':wrong[2],'prices-good':right[2],'incomes':tuple(right[2][i][i] for i in range(3)),
                     'good-closure':tuple(tuple(int(v) for v in row) for row in right[5]),
                     'flat-bound':max(F(1)/p for row in bad for p in row)})
    audit.equal(expected['flat-bound']<2,True,'whole-budget flat-region bound')
    for replacement,valid in ((F(99,100),False),(F(1),False),(F(101,100),True)):
        altered=bad[:2]+((replacement,F(6,5),F(1)),)
        audit.equal(not budget_data(altered,x)[6],valid,'strict versus weak cycle-removal boundary')
    audit.interventions+=1
    au,al,classes=afriat(good,x);bu,bl=(F(1),F(7,10),F(3,10)),(F(1),F(2),F(4))
    ac,bc=envelope(good,x,au,al),envelope(good,x,bu,bl)
    audit.equal(classes,((0,),(1,),(2,)),'induction follows revealed classes')
    expected.update({'certificate-a-u':au,'certificate-a-lambda':al,'certificate-b-u':bu,'certificate-b-lambda':bl,
                     'certificate-a-slack':ac[2],'certificate-b-slack':bc[2]})
    for u,cert in ((au,ac),(bu,bc)):
        for i,point in enumerate(x):audit.equal(min(plane_values(cert,point)),u[i],'observed-point envelope equality')
    extra=(F(0),F(5,4),F(0));expected['extra-max']=min(plane_values(ac,extra))
    audit.equal((dot(good[0],extra),expected['extra-max']),(F(1),au[0]),'unreported extra maximizing point')
    unobserved=((F(5,4),F(0),F(0)),(F(1),F(0),F(1,4)))
    expected['rank-a']=tuple(min(plane_values(ac,z)) for z in unobserved)
    expected['rank-b']=tuple(min(plane_values(bc,z)) for z in unobserved)
    audit.equal(expected['rank-a'][0]>expected['rank-a'][1] and expected['rank-b'][0]<expected['rank-b'][1],True,'different preferences, not just labels')
    for name,cert in (('a',ac),('b',bc)):
        q,value,terms,dual,upper,vertices=counterfactual(cert,F(5,4))
        expected.update({'new-'+name+'-demand':q,'new-'+name+'-bound':value,
                         'new-'+name+'-planes':terms,'new-'+name+'-third-slack':terms[2]-value})
        audit.equal(terms[2]>value,True,'inactive third plane positive slack')
        audit.equal(dot(upper[1],q)+upper[0],value,'global affine bound attainment')
        transfer=counterfactual(cert,F(63,50))
        audit.equal(transfer[0]!=q and transfer[1]>value,True,'income transfer changes unique optimum')
    audit.interventions+=1
    tp,tx=((1,1),(1,1)),((1,0),(0,1))
    tu,tl,tg=afriat(tp,tx);tc=envelope(tp,tx,tu,tl)
    expected.update({'tied-u':tu,'tied-lambda':tl})
    audit.equal((tg,tc[:2]),(((0,1),),((F(0),F(0)),((F(1),F(1)),(F(1),F(1))))),'tied class envelope')
    # Internal weak cycles, tied and singleton classes, and a zero-income boundary.
    situations=[(((1,1,2),(2,1,1),(1,2,1)),x),
                (((1,1),(1,1),(3,1)),((2,0),(0,2),(0,1))),
                (((1,2),),((0,0),))]
    for prices,quantities in situations:
        levels,mults,groups=afriat(prices,quantities);cert=envelope(prices,quantities,levels,mults)
        audit.equal(all(v>0 for v in mults),True,'positive construction in boundary classes')
        audit.equal(tuple(min(plane_values(cert,z)) for z in quantities),levels,'all new/old/internal class inequalities')
    audit.interventions+=1
    perm=(2,0,1);pu,pl,_=afriat(tuple(good[i] for i in perm),tuple(x[i] for i in perm))
    audit.equal((tuple(pu[perm.index(i)] for i in range(3)),tuple(pl[perm.index(i)] for i in range(3))),(au,al),'original observation indices retained')
    currency=(F(2),F(3),F(5));scaled=tuple(tuple(currency[i]*v for v in row) for i,row in enumerate(good))
    audit.equal(envelope(scaled,x,au,tuple(al[i]/currency[i] for i in range(3))),ac,'per-budget currency rescaling')
    shifted=envelope(good,x,tuple(3*u-2 for u in au),tuple(3*v for v in al))
    for z in unobserved:audit.equal(min(plane_values(shifted,z)),3*min(plane_values(ac,z))-2,'positive affine certificate relabeling')
    audit.interventions+=1
    return (bad,good,x,au,al,ac,bc)


def invalid_cases(audit,context,html):
    bad,good,x,au,al,ac,bc=context
    for v in (True,False,None,'1',0.1,float('nan'),float('inf'),10001):audit.reject(lambda v=v:scalar(v),'scalar domain')
    for p,z in (((),()),(((0,),),((1,),)),(((-1,),),((1,),)),(((1,),),((-1,),)),
                (((1,1),),((1,),)),(((1,),),((1,),(2,)))):
        audit.reject(lambda p=p,z=z:budget_data(p,z),'budget domain')
    audit.reject(lambda:afriat(bad,x),'GARP failure')
    for lam in ((0,1,2),(-1,1,2),(True,1,2),(1,1)):
        audit.reject(lambda lam=lam:envelope(good,x,au,lam),'multiplier restriction')
    audit.reject(lambda:envelope(good,x,(1,1,1),(1,1,1)),'false certificate')
    audit.reject(lambda:plane_values(ac,(-1,0,0)),'orthant')
    audit.reject(lambda:counterfactual(ac,0),'new budget')
    for graph in ([[True,False]],[[1]]):audit.reject(lambda graph=graph:closure(graph),'graph type')
    for reports in ([],[(frozenset('ab'),frozenset())],[(frozenset('a'),frozenset('b'))],
                    [(frozenset('a'),frozenset('a'))]*2):
        audit.reject(lambda reports=reports:reports_valid(tuple('ab'),reports),'report contract')
    for text in ('True','1/0','__import__("os")','1+2'):
        audit.reject(lambda text=text:numeric(text),'display grammar')
    for text in ('{"x":NaN}','{"x":1,"x":2}','{"x":1e999}'):
        audit.reject(lambda text=text:strict_json(text),'strict JSON')
    for before,after in [('id="v13-c01-ex1"','id="v13-c01-ex2"'),
                         ('data-solution-for="v13-c01-ex1"','data-solution-for="v13-c01-ex2"'),
                         ('class="solutions"','class="other"')]:
        def parse(before=before,after=after):
            page=Page();page.feed(html.replace(before,after,1));page.finish()
        audit.reject(parse,'reader pairing')
    audit.interventions+=1


def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    paths=AUTHOR+(SELF,RECORD);before={p:(root/p).read_bytes() for p in paths};audit=Audit()
    peer=strict_json(before[RECORD].decode());bindings=peer['payload_bindings']
    audit.equal(len(bindings),5,'five nonself peer bindings')
    audit.equal({r['path'] for r in bindings},set(AUTHOR+(SELF,)),'exact peer binding scope')
    for row in bindings:
        blob=before[row['path']]
        audit.equal((len(blob),sha256(blob).hexdigest()),(row['bytes'],row['sha256']),'bound final payload')
    html=before[AUTHOR[0]].decode();page=Page();page.feed(html);page.finish()
    expected=finite_oracles(audit);context=budget_oracles(audit,expected)
    audit.equal(set(page.markers),set(expected),'complete numerical marker inventory')
    for key,value in expected.items():audit.equal(numeric(page.markers[key]),value,'printed '+key)
    table=next(t for t in page.tables if t['caption']=='Two explicit rationalizers on the full orthant')
    audit.equal(len(table['rows']),3,'all printed envelope planes')
    for i,row in enumerate(table['rows']):
        for j,cert in enumerate(context[-2:],1):
            audit.equal(printed_plane(row[j]),(cert[0][i],cert[1][i]),'printed affine coefficients')
    for phrase in ('strictly positive multipliers','no real-valued representation','local nonsatiation',
                   'no directed cycle containing a strict edge','not a confidence level','positive rescaling'):
        audit.equal(phrase.lower() in html.lower(),True,'proof scope '+phrase)
    invalid_cases(audit,context,html)
    sources=strict_json(before[AUTHOR[2]].decode());proposals=sources['proposals']
    audit.equal({s['id'] for s in proposals},SOURCES,'source scopes')
    audit.equal(len(proposals),3,'source inventory')
    for source in proposals:audit.equal(page.sources[source['id']],source['url'],'actual primary URL')
    audit.equal(sources['attribution']['primary_source_preparation'],'ito_author','actual earlier source inspector')
    author=strict_json(before[AUTHOR[3]].decode())
    audit.equal(set(author['exercise_audit']),{'v13-c01-ex'+str(i) for i in range(1,13)},'every author solution record')
    audit.equal(set(author['bindings']),set(AUTHOR[:3]),'three nonself author bindings')
    for p in AUTHOR[:3]:
        audit.equal(author['bindings'][p],{'bytes':len(before[p]),'sha256':sha256(before[p]).hexdigest()},'author final binding')
    for p,blob in before.items():audit.equal((root/p).read_bytes(),blob,'unchanged input bytes')
    result={'chapter':'v13-c01','status':'separate peer checks passed','comparisons':audit.comparisons,
            'rejections':audit.rejections,'intervention_groups':audit.interventions,
            'worked_cases':6,'solved_exercises':12,'printed_markers':len(expected),
            'complete_menus':63,'rich_three_alternative_reports':189,'rich_rationalizable_reports':13,
            'restricted_normalized_orders':len(expected['menu-orders']),'runtime_payloads':6,
            'author_checker_imported':False,
            'limit':'Finite checks accompany the separate written proof review; no empirical or statistical confidence claim.'}
    strict_json(json.dumps(result,allow_nan=False));return result


if __name__=='__main__':
    require(len(sys.argv)==1,'no CLI arguments')
    check()
