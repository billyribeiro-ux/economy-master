"""Quiet bounded verification for the four-file V13-C03 canonical author package.

Only standard-library code and adjacent runtime payloads are used. check(root=None)
returns strict JSON data; successful import and CLI are silent and write nothing.
Finite numeric witnesses support the manuscript's separately audited proofs.
"""
from __future__ import annotations

from collections import Counter
from decimal import Decimal, localcontext
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from itertools import product
import json
import math
from pathlib import Path
import sys

FILES = (
    'content/chapters/v13-c03.html',
    'scripts/check_v13_c03.py',
    'content/reviews/v13-c03-sources.json',
    'content/reviews/v13-c03-author.json',
)
SOURCE_IDS = {
    'mit-expected-utility', 'mit-risk-attitudes',
    'v13-c03-mit-dominance2015', 'v13-c03-borgers-blackwell2023',
}
READER_ROUTES = {
    'v13-c01.html', 'v13-c02.html', 'v03-c01.html',
    'v03-c10.html', 'v02-c10.html', 'v13-c04.html',
}


def need(ok, message):
    if not ok:
        raise ValueError(message)


def number(x):
    need(type(x) in (int, float, F), 'number must exclude bool/string/complex')
    if type(x) is float:
        need(math.isfinite(x), 'finite number required')
        x = F(str(x))
    else:
        x = F(x)
    need(abs(x) <= 10**6 and x.denominator <= 10**9, 'bounded rational domain')
    return x


def vector(xs, n=None, limit=4):
    need(type(xs) in (list, tuple) and 1 <= len(xs) <= limit, 'bounded vector')
    need(n is None or len(xs) == n, 'vector dimension')
    return tuple(number(x) for x in xs)


def probabilities(xs, n=None, limit=4):
    xs = vector(xs, n, limit)
    need(all(x >= 0 for x in xs) and sum(xs) == 1, 'probability simplex')
    return xs


def matrix(rows, n=None, m=None, stochastic=False):
    need(type(rows) in (list, tuple) and 1 <= len(rows) <= 4, 'bounded matrix')
    need(n is None or len(rows) == n, 'matrix row dimension')
    first = vector(rows[0], m)
    result = (first,) + tuple(vector(row, len(first)) for row in rows[1:])
    if stochastic:
        need(all(all(x >= 0 for x in row) and sum(row) == 1 for row in result),
             'row-stochastic matrix required')
    return result


def finite_lottery(support, probs):
    xs = vector(support, limit=8)
    ps = probabilities(probs, len(xs), limit=8)
    need(all(a < b for a, b in zip(xs, xs[1:])), 'strictly ordered support')
    return xs, ps


def expectation(law, fun):
    xs, ps = law
    return sum((p * fun(x) for x, p in zip(xs, ps)), F(0))


def cdf(law, t):
    return expectation(law, lambda x: F(x <= t))


def lower(law, t):
    return expectation(law, lambda x: max(F(0), t-x))


def decision(prior, experiment, payoffs):
    """Column-wise exact maximization; zero-probability posteriors are None."""
    pi = probabilities(prior)
    p = matrix(experiment, len(pi), stochastic=True)
    u = matrix(payoffs, len(pi))
    q, posterior, values, actions = [], [], [], []
    for s in range(len(p[0])):
        joint = tuple(pi[i]*p[i][s] for i in range(len(pi)))
        mass = sum(joint)
        q.append(mass)
        posterior.append(tuple(x/mass for x in joint) if mass else None)
        av = tuple(sum(joint[i]*u[i][a] for i in range(len(pi)))
                   for a in range(len(u[0])))
        best = max(av)
        values.append(best)
        actions.append(tuple(a for a, value in enumerate(av) if value == best))
    prior_value = max(sum(pi[i]*u[i][a] for i in range(len(pi)))
                      for a in range(len(u[0])))
    perfect = sum(pi[i]*max(u[i]) for i in range(len(pi)))
    return {'signal': tuple(q), 'posterior': tuple(posterior),
            'actions': tuple(actions), 'value': sum(values),
            'prior': prior_value, 'perfect': perfect}


def enumerated_rules(pi, p, u):
    """Independent route: enumerate whole deterministic policies, then total states."""
    result = []
    for rule in product(range(len(u[0])), repeat=len(p[0])):
        total = F(0)
        for i, prob in enumerate(pi):
            conditional = F(0)
            for s, signal_prob in enumerate(p[i]):
                conditional += signal_prob*u[i][rule[s]]
            total += prob*conditional
        result.append((rule, total))
    return result


def garble(experiment, kernel):
    p = matrix(experiment, stochastic=True)
    g = matrix(kernel, len(p[0]), stochastic=True)
    return tuple(tuple(sum(p[i][s]*g[s][t] for s in range(len(g)))
                       for t in range(len(g[0]))) for i in range(len(p)))


def reject_constants(text):
    raise ValueError('nonstandard JSON constant: '+text)


def unique_pairs(items):
    out = {}
    for key, value in items:
        need(key not in out, 'duplicate JSON key')
        out[key] = value
    return out


def read_json(path):
    return json.loads(path.read_text(), parse_constant=reject_constants,
                      object_pairs_hook=unique_pairs)


class Reader(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids, self.sources, self.links = [], [], []
        self.worked, self.prompts, self.solutions = [], [], []
        self.anchors = {}
        self.capture = None
        self.stack = []
        self.exercise_depth = None
        self.solution_depth = None
        self.have_solution_disclosure = False

    def handle_starttag(self, tag, attrs):
        data = dict(attrs)
        if 'id' in data:
            self.ids.append(data['id'])
        if 'data-source' in data:
            self.sources.append(data['data-source'])
        if 'href' in data:
            self.links.append(data['href'])
        classes = data.get('class', '').split()
        if tag == 'article' and 'worked' in classes:
            self.worked.append(data.get('id'))
        if tag == 'ol' and 'exercises' in classes:
            self.exercise_depth = len(self.stack)
        if tag == 'details' and 'solutions' in classes:
            self.solution_depth = len(self.stack)
            self.have_solution_disclosure = True
        if tag == 'li' and self.exercise_depth is not None:
            self.prompts.append(data.get('id'))
        if 'data-solution-for' in data:
            need(self.solution_depth is not None, 'answer outside standard disclosure')
            self.solutions.append(data['data-solution-for'])
        if 'data-calc' in data:
            key = data['data-calc']
            need(key not in self.anchors and self.capture is None, 'duplicate/nested anchor')
            self.capture = key
            self.anchors[key] = ''
        if tag not in {'br', 'hr', 'img', 'meta', 'link', 'input'}:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if tag == 'span' and self.capture is not None:
            self.capture = None
        need(bool(self.stack) and self.stack[-1] == tag, 'unbalanced HTML '+tag)
        self.stack.pop()
        if tag == 'ol' and self.exercise_depth == len(self.stack):
            self.exercise_depth = None
        if tag == 'details' and self.solution_depth == len(self.stack):
            self.solution_depth = None

    def handle_data(self, data):
        if self.capture is not None:
            self.anchors[self.capture] += data


def fmt(xs):
    return '('+','.join(str(x) for x in xs)+')'


def digest(path):
    payload = path.read_bytes()
    return {'path': str(path), 'bytes': len(payload), 'sha256': sha256(payload).hexdigest()}


def check(root=None):
    root = Path(root).resolve() if root is not None else Path(__file__).resolve().parent.parent
    paths = tuple(root/name for name in FILES)
    before = tuple(p.read_bytes() for p in paths)
    counts = {'comparisons': 0, 'rejections': 0, 'enumerated_rules': 0}

    def eq(actual, expected, label):
        counts['comparisons'] += 1
        need(actual == expected, label+': '+repr(actual)+' != '+repr(expected))

    def yes(ok, label):
        counts['comparisons'] += 1
        need(ok, label)

    def rejects(call, label):
        try:
            call()
        except (ValueError, TypeError):
            counts['rejections'] += 1
        else:
            raise ValueError('accepted invalid domain: '+label)

    reader = Reader()
    reader.feed(before[0].decode('utf-8'))
    reader.close()
    yes(not reader.stack, 'balanced reader fragment')
    eq(len(reader.ids), len(set(reader.ids)), 'unique IDs')
    eq(reader.worked, ['v13-c03-case'+str(i) for i in range(1, 7)], 'six worked cases')
    prompts = ['v13-c03-ex'+str(i) for i in range(1, 13)]
    eq(reader.prompts, prompts, 'twelve exact prompts')
    eq(reader.solutions, prompts, 'twelve paired answers')
    yes(reader.have_solution_disclosure, 'standard grouped solutions')
    eq(set(reader.sources), SOURCE_IDS, 'reader source scopes')
    eq({x for x in reader.links if not x.startswith('https://')}, READER_ROUTES,
       'exact flat prerequisite/successor links, no runtime chapter dependencies')
    sources, author = (read_json(paths[2]), read_json(paths[3]))
    eq({x['id'] for x in sources['proposals']}, SOURCE_IDS, 'four source proposals')
    for source in sources['proposals']:
        eq(source['inspection']['actual_inspector'], 'ito_author', 'actual source inspector')
        yes(bool(source['limits']), 'source limitations retained')
    borgers = next(x for x in sources['proposals'] if 'borgers' in x['id'])
    eq(borgers['inspection']['actual_image_physical_pages'], [], 'no false image claim')
    yes('retained_pdf' not in borgers, 'no unavailable PDF binding')
    bindings = {x['path']: x for x in author['bindings']}
    eq(set(bindings), set(FILES[:3]), 'three nonself author bindings')
    for name, path in zip(FILES[:3], paths[:3]):
        info = digest(path)
        eq((bindings[name]['bytes'], bindings[name]['sha256']),
           (info['bytes'], info['sha256']), 'author payload binding '+name)
    eq([x['id'] for x in author['exercise_audit']], prompts, 'all solution audits')
    eq(len(author['proof_audit']), 6, 'six substantive proof audits')
    eq(author['open_findings'], [], 'author open findings')

    anchors = {}
    # Case 1: direct expectations and independent polynomial expansion.
    u = (F(0), F(3, 10), F(1))
    lot = ((F(1, 5), F(1, 2), F(3, 10)), (F(0), F(3, 4), F(1, 4)))
    ev = tuple(sum(p*v for p, v in zip(row, u)) for row in lot)
    nonlinear = tuple(sum(p*v*v for p, v in zip(row, u)) for row in lot)
    affine = tuple(sum(p*(2*v+5) for p, v in zip(row, u)) for row in lot)
    eq(ev, (F(9,20), F(19,40)), 'normalized lottery values')
    eq(affine, tuple(2*x+5 for x in ev), 'affine commutes with expectation')
    yes(ev[0] < ev[1] and nonlinear[0] > nonlinear[1], 'nonlinear reversal')
    anchors.update({'eu-values': fmt(ev), 'affine-values': fmt(affine),
                    'nonlinear-values': fmt(nonlinear)})
    money = (F(0), F(2), F(4), F(10))
    laws = ((0,1,0,0), (F(2,5),0,F(3,5),0),
            (0,F(1,2),0,F(1,2)), (F(1,5),0,F(3,10),F(1,2)))
    means, variances, second, scores = [], [], [], []
    for ps in laws:
        law = finite_lottery(money, ps)
        mean = expectation(law, lambda x: x)
        moment = expectation(law, lambda x: x*x)
        variance = expectation(law, lambda x: (x-mean)**2)
        eq(variance, moment-mean*mean, 'centered versus raw variance')
        means.append(mean); second.append(moment); variances.append(variance)
        scores.append(mean-variance/4)
    eq(tuple(means), (2,F(12,5),6,F(31,5)), 'all four means')
    eq(tuple(variances), (0,F(96,25),16,F(409,25)), 'all four variances')
    eq(second[1], F(48,5), 'Q second moment')
    eq(second[3], F(274,5), 'mixed Q second moment')
    eq(tuple(scores), (2,F(36,25),2,F(211,100)), 'independence witness')
    anchors['independence-values'] = fmt(scores)
    # Case 2: high-precision transcendental route versus algebraic CE identity.
    with localcontext() as ctx:
        ctx.prec = 50
        ce = ((Decimal(7).ln()+Decimal(13).ln())/2).exp()
        yes(abs(ce*ce-91) < Decimal('1e-45'), 'log CE independent exponential route')
        premium = Decimal(10)-ce
        anchors['log-premium'] = format(premium, '.6f')
        eq(F(1)/(F(1,7)/2+F(1,13)/2), F(91,10), 'harmonic certainty equivalent')
        eq(10-F(91,10), F(9,10), 'reciprocal premium')
        yes(Decimal(91)/10 < ce < 10, 'strict global CE ordering')
        for epsilon in (F(1), F(1,2)):
            eps = Decimal(epsilon.numerator)/epsilon.denominator
            s = (100-9*eps*eps).sqrt()
            err = 10-s-Decimal(9)*eps*eps/20
            rationalized = 81*eps**4/(20*(10+s)**2)
            yes(abs(err-rationalized) < Decimal('1e-45'), 'exact log remainder identity')
            yes(err > 0, 'quadratic premium underestimates')
        anchors['half-local'] = str(F(9,20)*F(1,2)**2)
        anchors['half-error-bound'] = str(F(81,320*19**2))
        anchors['half-error'] = format(err, '.6f')
        yes(err < Decimal(81)/115520 < Decimal(1)/1000, 'half-risk analytic bound')
    # Case 3: atom-aware distribution tests and utility generators.
    A = finite_lottery((2,5), (F(1,2),F(1,2)))
    B = finite_lottery((1,4), (F(1,2),F(1,2)))
    C = finite_lottery((3,), (1,))
    spread = finite_lottery((1,5), (F(1,2),F(1,2)))
    X = finite_lottery((0,3), (F(1,3),F(2,3)))
    Y = finite_lottery((1,5), (F(3,4),F(1,4)))
    for first, second_law, label in ((A,B,'shift'),(C,spread,'spread'),(X,Y,'incomparable')):
        knots = sorted(set(first[0]+second_law[0]))
        fd = tuple(cdf(first,t)-cdf(second_law,t) for t in knots)
        ld = tuple(lower(first,t)-lower(second_law,t) for t in knots)
        for t in knots:
            # Integral of the right-continuous step CDF, independent of put-payoff sum.
            for law in (first,second_law):
                grid = sorted(set([min(knots),t]+[x for x in law[0] if x <= t]))
                integral = sum(cdf(law,a)*(b-a) for a,b in zip(grid,grid[1:]))
                eq(integral, lower(law,t), 'CDF integral with endpoint atoms')
        for increments in product((0,1,2), repeat=len(knots)-1):
            utility = [F(0)]
            for inc in increments:
                utility.append(utility[-1]+inc)
            scores_at = dict(zip(knots,utility))
            diff = expectation(first, scores_at.__getitem__)-expectation(second_law, scores_at.__getitem__)
            telescoped = sum(increments[k]*(-fd[k]) for k in range(len(increments)))
            eq(diff,telescoped,'finite FSD summation identity')
        if label == 'shift':
            eq(fd,(F(-1,2),0,F(-1,2),0),'shift CDF')
            yes(all(v<=0 for v in fd),'shift FSD')
            eq((expectation(first,lambda x:x),expectation(second_law,lambda x:x)),
               (F(7,2),F(5,2)),'unequal shift means')
            anchors['shift-cdf']=fmt(fd)
        elif label == 'spread':
            yes(min(fd)<0<max(fd),'spread not FSD')
            yes(all(v<=0 for v in ld),'spread SSD')
            eq(expectation(spread,lambda x:x),3,'coupling conditional mean')
            eq((expectation(first,lambda x:min(x,3)),expectation(second_law,lambda x:min(x,3))),
               (3,2),'spread capped utility')
        else:
            yes(min(fd)<0<max(fd) and min(ld)<0<max(ld),'both incomparabilities')
            eq(tuple(expectation(law,lambda x:x) for law in (X,Y)),(2,2),'equal means')
            var=tuple(expectation(law,lambda x:(x-2)**2) for law in (X,Y))
            eq(var,(2,3),'variance trap')
            anchors['incomparable-variances']=fmt(var)
            anchors['incomparable-cdf']=fmt(fd)
            anchors['incomparable-lower']=fmt(ld)
            for cap,key,values in ((1,'cap-one',(F(2,3),1)),(3,'cap-three',(2,F(3,2)))):
                val=tuple(expectation(law,lambda x:min(x,cap)) for law in (X,Y))
                eq(val,values,'opposite concave witness')
                raised=tuple(expectation(law,lambda x:min(x,cap)+F(1,7)*x) for law in (X,Y))
                eq(raised[0]-raised[1],val[0]-val[1],'strictly increasing witness unchanged')
                anchors[key]=fmt(val)
        # Hinge representation checked on all support points for two concave slope patterns.
        if len(knots)>1:
            for slopes in (tuple(F(1) for _ in knots[:-1]),
                           tuple(F(len(knots)-j) for j in range(1,len(knots)))):
                values=[F(0)]
                for j,slope in enumerate(slopes):
                    values.append(values[-1]+slope*(knots[j+1]-knots[j]))
                for x,value in zip(knots,values):
                    via_hinges=values[-1]+slopes[-1]*(x-knots[-1])
                    via_hinges-=sum((slopes[j-1]-slopes[j])*max(F(0),knots[j]-x)
                                    for j in range(1,len(knots)-1))
                    eq(via_hinges,value,'finite concave hinge decomposition')
    # Cases 4–6: complete policy enumeration versus column-wise maximization.
    pi=(F(1,3),F(2,3)); P=((F(3,4),F(1,4)),(F(1,4),F(3,4)))
    U=((6,0),(-3,0)); G=((F(2,3),F(1,3)),(F(1,3),F(2,3)))
    Q=garble(P,G)
    eq(Q,((F(7,12),F(5,12)),(F(5,12),F(7,12))),'garbling product')
    jobs=[]
    def task(pi,p,u,label):
        result=decision(pi,p,u)
        enumerated=enumerated_rules(pi,p,u)
        counts['enumerated_rules']+=len(enumerated)
        eq(result['value'],max(v for _,v in enumerated),'whole-policy oracle '+label)
        yes(result['prior']<=result['value']<=result['perfect'],'information bounds '+label)
        for i in range(len(pi)):
            eq(sum(q*post[i] for q,post in zip(result['signal'],result['posterior']) if q),
               pi[i],'Bayes plausibility '+label)
        common=set(range(len(u[0])))
        for q,chosen in zip(result['signal'],result['actions']):
            if q: common.intersection_update(chosen)
        eq(bool(common),result['value']==result['prior'],'zero-value criterion '+label)
        jobs.append(result)
        return result
    pval=task(pi,P,U,'investment P');qval=task(pi,Q,U,'investment Q')
    eq((pval['prior'],pval['value'],pval['perfect']),(0,1,2),'original value anchors')
    eq(qval['value'],F(1,3),'garbled value')
    eq(pval['actions'],((0,),(1,)),'investment optimal actions')
    anchors['bayes-signal']=fmt(pval['signal'])
    anchors['bayes-high']=fmt(row[0] for row in pval['posterior'])
    invest=tuple(sum(post[i]*U[i][0] for i in range(2)) for post in pval['posterior'])
    eq(invest,(F(12,5),F(-12,7)),'posterior investment means')
    anchors['bayes-invest']=fmt(invest)
    zero=task(pi,P,((6,0),(0,0)),'informative but zero value')
    eq((zero['prior'],zero['value']),(2,2),'common-action no gain')
    anchors['garbled-matrix']='Q=('+','.join(fmt(row) for row in Q)+')'
    anchors['garbled-signal']=fmt(qval['signal'])
    anchors['garbled-high']=fmt(row[0] for row in qval['posterior'])
    eq(tuple(sum(post[i]*U[i][0] for i in range(2)) for post in qval['posterior']),
       (F(12,17),F(-12,19)),'garbled conditional payoffs')
    simulated=sum(pi[i]*sum(P[i][s]*G[s][0]*U[i][0] for s in range(2)) for i in range(2))
    eq(simulated,qval['value'],'simulated Q policy')
    det=Q[0][0]*Q[1][1]-Q[0][1]*Q[1][0]
    eq(det,F(1,6),'reverse determinant')
    inv=((Q[1][1]/det,-Q[0][1]/det),(-Q[1][0]/det,Q[0][0]/det))
    K=tuple(tuple(sum(inv[i][s]*P[s][j] for s in range(2)) for j in range(2)) for i in range(2))
    eq(K,((2,-1),(-1,2)),'unique reverse solution')
    rejects(lambda:garble(Q,K),'negative reverse kernel')
    anchors['reverse-kernel']='Q⁻¹P=('+','.join(fmt(row) for row in K)+')'
    anchors['cost-net']=str(pval['value']-F(3,4))
    eq(pval['value']-qval['value'],F(2,3),'extra-fee boundary')
    for fee,sign in ((F(0),1),(F(2,3),0),(F(3,4),-1)):
        gap=pval['value']-fee-qval['value']
        eq((gap>0)-(gap<0),sign,'acquisition boundary')
    pi3=(F(1,3),)*3
    E=((1,0),(0,1),(0,1));H=((0,1),(1,0),(0,1))
    U1=((1,0),(0,1),(0,1));U2=((0,1),(1,0),(0,1))
    pair=[]
    for payoff,label in ((U1,'state 1'),(U2,'state 2')):
        pair.append(tuple(task(pi3,p,payoff,label)['value'] for p in (E,H)))
    eq(tuple(pair),((1,F(2,3)),(F(2,3),1)),'opposite information witnesses')
    anchors['partition-values']='('+','.join(fmt(row) for row in pair)+')'
    classification=tuple(task(pi3,p,((1,0,0),(0,1,0),(0,0,1)),'classification')['value'] for p in (E,H))
    eq(classification,(F(2,3),F(2,3)),'equal classification insufficient')
    anchors['classification-values']=fmt(classification)
    energies=[]
    for p in (E,H):
        r=decision(pi3,p,U1)
        energy=sum(q*sum((post[i]-pi3[i])**2 for i in range(3))
                   for q,post in zip(r['signal'],r['posterior']))
        energies.append(energy)
    eq(tuple(energies),(F(1,3),F(1,3)),'posterior energy insufficiency')
    anchors['posterior-energy']=str(energies[0])
    yes(E[1]==E[2] and H[1]!=H[2] and H[0]==H[2] and E[0]!=E[2],
        'repeated rows obstruct both garblings')
    # A complete explicit separating witness; no numerical optimizer is invoked.
    trivial=((1,),(1,)); perfect=((1,0),(0,1))
    midpoint=((F(1,2),F(1,2)),)*2
    separator=tuple(tuple(perfect[i][j]-midpoint[i][j] for j in range(2)) for i in range(2))
    separator_pay=tuple(tuple(2*x for x in row) for row in separator)
    sepP=task((F(1,2),)*2,trivial,separator_pay,'separator constant')
    sepQ=task((F(1,2),)*2,perfect,separator_pay,'separator revealing')
    eq((sepP['value'],sepQ['value']),(0,1),'separation becomes payoff')
    for prob in (F(0),F(1,3),F(1)):
        z=garble(trivial,((prob,1-prob),))
        eq(sum(separator[i][j]*z[i][j] for i in range(2) for j in range(2)),0,
           'separator constant on whole row-equal affine family')
    for payoff in (((1,0),(0,1)),((2,-5),(-3,7))):
        left=task((1,0),trivial,payoff,'zero prior constant')
        right=task((1,0),perfect,payoff,'zero prior reveal')
        eq(left['value'],right['value'],'zero-prior equality cannot recover rows')
        eq(right['posterior'][1],None,'zero signal posterior undefined')
    # Explicit supported-domain failures; no stochastic fuzzing.
    bad_numbers=(True,'1',complex(1,0),float('nan'),float('inf'),10**7,F(1,10**10))
    for bad in bad_numbers:
        rejects(lambda bad=bad:number(bad),'bad numeric scalar')
    for bad in ([],[0,0],[-1,2],[F(1,3),F(1,3)],[1,0,0,0,0]):
        rejects(lambda bad=bad:probabilities(bad),'bad probability vector')
    for bad in ([],[[1],[]],[[1,0],[1]],[[1,-1]],[[1,1]],[[True,0]]):
        rejects(lambda bad=bad:matrix(bad,stochastic=True),'bad experiment')
    for args in (((1,0),((1,),),((1,),(1,))),
                 ((1,),((1,),),((1,),(2,))),
                 ((1,),((1,),),((1,2,3,4,5),))):
        rejects(lambda args=args:decision(*args),'decision dimension')
    rejects(lambda:finite_lottery((1,1),(F(1,2),F(1,2))),'duplicate support')
    rejects(lambda:finite_lottery((2,1),(F(1,2),F(1,2))),'unsorted support')
    rejects(lambda:finite_lottery((1,2),(1,)),'lottery dimensions')
    rejects(lambda:garble(P,((1,),)),'garbling dimensions')
    for invalid in ('{"x":NaN}','{"x":Infinity}','{"x":1,"x":2}'):
        rejects(lambda invalid=invalid:json.loads(invalid,parse_constant=reject_constants,
                                                   object_pairs_hook=unique_pairs),'strict JSON')
    eq(reader.anchors,anchors,'every printed calculation anchor')
    eq(tuple(p.read_bytes() for p in paths),before,'four payloads unchanged')
    result={'chapter':'v13-c03','status':'passed','worked_cases':6,'solved_exercises':12,
            'numeric_anchors':len(anchors),**counts,
            'scope':'Finite original arithmetic/policy witnesses and bindings; universal proofs audited separately.',
            'runtime_payloads':list(FILES),'writes':0}
    json.dumps(result,allow_nan=False)
    return result


if __name__ == '__main__':
    need(len(sys.argv)==1,'CLI takes no arguments and writes nothing')
    check()
