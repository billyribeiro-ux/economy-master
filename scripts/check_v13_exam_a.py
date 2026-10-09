"""Bounded, quiet four-file Form A audit; standard library only.

check(root=None) reads exactly FILES and returns a strict JSON-safe summary.
No chapter, blueprint, prior record, source artifact or saved answer is imported.
Finite computations corroborate the separately reviewed universal arguments.
"""
from fractions import Fraction as F
from html.parser import HTMLParser
from itertools import combinations, permutations, product
from hashlib import sha256
import ast
import json
import math
from pathlib import Path
import re
import sys

FILES=('content/assessments/parts/v13-exam-a.html','scripts/check_v13_exam_a.py',
       'content/reviews/v13-exam-a-sources.json','content/reviews/v13-exam-a-author.json')
POINTS=((4,6,4,6),(6,5,5,4),(4,4,6,6),(5,6,5,4),(5,5,4,6))
PARTS={f'v13-exam-a-{i}{chr(97+j)}':n for i,row in enumerate(POINTS,1) for j,n in enumerate(row)}
DOMAINS=('choice_duality_information','equilibrium_welfare','strategic_dynamics','incentives_design','networks_research')
URLS={'v05-c01-mit-preferences': 'https://ocw.mit.edu/courses/14-121-microeconomic-theory-i-fall-2015/b89cf6eb8d2118d015d4e41278ede14a_MIT14_121F15_1S.pdf', 'v05-c02-consumer': 'https://ocw.mit.edu/courses/14-121-microeconomic-theory-i-fall-2015/ea9f11b15ace05e7bfd31d58ae48beb9_MIT14_121F15_2S.pdf', 'mit-expected-utility': 'https://ocw.mit.edu/courses/14-123-microeconomic-theory-iii-spring-2015/02f917a9f6cf1d6a3c7397d457b23951_MIT14_123S15_Chap2.pdf', 'v13-c03-borgers-blackwell2023': 'https://websites.umich.edu/~tborgers/BlackwellDominance.pdf', 'v13-c04-condie-existence': 'https://scottcondie.github.io/teaching/580/chapters/ge-existence.html', 'v05-c05-mit-welfare': 'https://ocw.mit.edu/courses/14-04-intermediate-microeconomic-theory-fall-2020/1gcajw7hbthjPcO8f8wCXWoKIBXEYkUEH_transcript.pdf', 'v13-c05-borgers-aggregation2021': 'https://websites.umich.edu/~tborgers/GE.pdf', 'v13-c06-manea-noncoop2017': 'https://ocw.mit.edu/courses/14-126-game-theory-spring-2016/a4d0a3949ab29c2a2f55442a9723d205_MIT14_126S16_noncoop.pdf', 'v13-c06-yildiz-games2022': 'https://ocw.mit.edu/courses/14.126-game-theory-spring-2024/mit14_126_s24_yildiz-lecture-notes.pdf', 'v05-c08-holmstrom-screening': 'https://ocw.mit.edu/courses/14-124-microeconomic-theory-iv-spring-2017/9a5e2a8da8b4e9b22fa39d66f9d98dda_MIT14_124S17_Slide3.pdf', 'v05-c09-mit-contracts': 'https://ocw.mit.edu/courses/14-124-microeconomic-theory-iv-spring-2017/0a3d53590f17f81f1561eb7d7922329d_MIT14_124S17_Slide2.pdf', 'v13-c10-ozdaglar-mechanism2010': 'https://ocw.mit.edu/courses/6-254-game-theory-with-engineering-applications-spring-2010/4bad561319453ce5c37ff094549c5486_MIT6_254S10_lec20.pdf', 'v05-c11-manea-matching': 'https://ocw.mit.edu/courses/14-16-strategy-and-information-spring-2016/53dbe8d681978367f9c04182aa3c9b97_MIT14_16S16_Matching.pdf', 'v13-c11-ght-menu2026': 'https://arxiv.org/pdf/2209.13148v4', 'v13-c12-berk-harvey-hirshleifer-referee2015': 'https://www.aeaweb.org/content/file?id=222.'}


def need(ok,label):
    if not ok:raise ValueError('V13 Form A: '+label)


def num(x):
    need(type(x) in (int,float,F),'numeric type, excluding bool')
    if type(x) is float:
        need(math.isfinite(x),'finite numeric value');x=F(str(x))
    else:x=F(x)
    need(abs(x)<=10**6 and x.denominator<=10**12,'bounded magnitude/reduced denominator')
    return x


def vec(x,n=None,maximum=4):
    need(type(x) in (tuple,list) and 1<=len(x)<=maximum,'bounded vector')
    need(n is None or len(x)==n,'vector dimension')
    return tuple(num(v) for v in x)


def probability(x,n=None):
    x=vec(x,n);need(all(z>=0 for z in x) and sum(x)==1,'probability simplex');return x


def matrix(x,rows=None,cols=None):
    need(type(x) in (tuple,list) and 1<=len(x)<=4,'bounded matrix')
    need(rows is None or len(x)==rows,'matrix row count')
    out=tuple(vec(row,cols) for row in x)
    need(all(len(r)==len(out[0]) for r in out),'rectangular matrix')
    return out


def strict_json(raw):
    def pairs(items):
        out={}
        for k,v in items:
            need(k not in out,'duplicate JSON key');out[k]=v
        return out
    def bad(_):raise ValueError('V13 Form A: nonfinite JSON constant')
    obj=json.loads(raw,object_pairs_hook=pairs,parse_constant=bad)
    def walk(x):
        if type(x) is float:need(math.isfinite(x),'finite JSON number')
        elif type(x) is list:
            for z in x:walk(z)
        elif type(x) is dict:
            for z in x.values():walk(z)
    walk(obj);return obj


def literal(text):
    """Small visible numeric tuples, fractions and the four matching names only."""
    need(type(text) is str and 0<len(text)<=2000,'bounded visible literal')
    try:node=ast.parse(text.strip().replace('−','-'),mode='eval')
    except (SyntaxError,ValueError) as exc:raise ValueError('V13 Form A: literal syntax') from exc
    need(sum(1 for _ in ast.walk(node))<=128,'bounded literal tree')
    def parse(n,depth=0):
        need(depth<=8,'bounded literal depth')
        if isinstance(n,ast.Expression):return parse(n.body,depth+1)
        if isinstance(n,ast.Constant):return num(n.value)
        if isinstance(n,ast.Name):
            need(n.id in ('A','B','X','Y'),'matching name');return n.id
        if isinstance(n,(ast.Tuple,ast.List,ast.Set)):
            need(len(n.elts)<=12,'bounded tuple');return tuple(parse(e,depth+1) for e in n.elts)
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,(ast.USub,ast.UAdd)):
            z=parse(n.operand,depth+1);return num(-z if isinstance(n.op,ast.USub) else z)
        if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Div):
            a,b=parse(n.left,depth+1),parse(n.right,depth+1)
            need(type(a) is F and type(b) is F and b!=0,'finite rational division');return num(a/b)
        raise ValueError('V13 Form A: forbidden literal expression')
    return parse(node)


def sqrt_exact(x):
    x=num(x);need(x>=0,'nonnegative rational square')
    a,b=math.isqrt(x.numerator),math.isqrt(x.denominator)
    need(a*a==x.numerator and b*b==x.denominator,'exact rational-square helper domain')
    return F(a,b)


def consumer(p,m,kind='cd'):
    p=vec(p,2);m=num(m);need(all(z>0 for z in p) and m>=0,'positive prices and nonnegative income')
    need(kind in ('cd','minimum'),'specified consumer index')
    return (m/(2*p[0]),m/(2*p[1])) if kind=='cd' else (m/sum(p),)*2


def decision(prior,E,payoffs):
    prior=probability(prior);E=matrix(E,len(prior));v=matrix(payoffs,len(prior))
    for row in E:probability(row)
    rules=tuple(product(range(len(v[0])),repeat=len(E[0])))
    scores=tuple(sum(prior[s]*E[s][z]*v[s][r[z]] for s in range(len(prior)) for z in range(len(E[0]))) for r in rules)
    best=max(scores);return best,tuple(r for r,z in zip(rules,scores) if z==best)


def multiply(A,B):
    A=matrix(A);B=matrix(B,len(A[0]))
    return tuple(tuple(sum(A[i][k]*B[k][j] for k in range(len(B))) for j in range(len(B[0]))) for i in range(len(A)))


def exchange(endowments,shares,t):
    e=matrix(endowments,2,2);a=vec(shares,2);t=num(t)
    need(all(z>=0 for row in e for z in row) and all(0<z<1 for z in a),'nonnegative endowments/interior Cobb shares')
    need(0<=t<=e[1][1],'owned physical transfer range')
    w=((e[0][0],e[0][1]+t),(e[1][0],e[1][1]-t))
    total=tuple(sum(row[j] for row in w) for j in range(2))
    need(all(z>0 for z in total),'both goods supplied')
    denominator=total[0]-sum(a[i]*w[i][0] for i in range(2))
    numerator=sum(a[i]*w[i][1] for i in range(2))
    need(denominator>0 and numerator>0,'positive relative-price formula')
    r=numerator/denominator;income=tuple(r*row[0]+row[1] for row in w)
    choices=tuple((a[i]*income[i]/r,(1-a[i])*income[i]) for i in range(2))
    return r,income,choices,w


def volunteer(a,b,benefit,cost):
    need(type(a) is int and a in (0,1) and type(b) is int and b in (0,1),'binary volunteer actions')
    benefit,cost=num(benefit),num(cost);need(0<cost<benefit,'volunteer helper parameter domain')
    return (benefit*int(a+b>0)-cost*a,benefit*int(a+b>0)-cost*b)


def plan_payoffs(benefit,cost):
    plans=((1,1),(1,0),(0,1),(0,0))
    return tuple(tuple(volunteer(a,r[0 if a else 1],benefit,cost) for r in plans) for a in (1,0))


def plan_nash(p,d,table):
    p=num(p);need(0<=p<=1,'first-mover probability');d=probability(d,4)
    row=tuple(sum(d[j]*table[i][j][0] for j in range(4)) for i in range(2))
    col=tuple(p*table[0][j][1]+(1-p)*table[1][j][1] for j in range(4))
    return all(row[i]==max(row) for i,weight in enumerate((p,1-p)) if weight) and all(col[j]==max(col) for j,weight in enumerate(d) if weight)


def worker_vertices(p,c,cap,target):
    p=vec(p,2);c=vec(c,2);cap=num(cap)
    need(0<p[1]<p[0]<1 and c[0]>c[1]==0 and cap>0,'two-action worker domain')
    need(type(target) is int and target in (0,1),'worker target')
    other=1-target
    # A wage vector (success,failure) must satisfy each affine row dot w >= b.
    constraints=((F(1),F(0),F(0)),(F(0),F(1),F(0)),(F(-1),F(0),-cap),(F(0),F(-1),-cap),
                 (p[target],1-p[target],c[target]),(p[target]-p[other],p[other]-p[target],c[target]-c[other]))
    vertices=set()
    for x,y in combinations(constraints,2):
        det=x[0]*y[1]-x[1]*y[0]
        if not det:continue
        w=((x[2]*y[1]-x[1]*y[2])/det,(x[0]*y[2]-x[2]*y[0])/det)
        if all(r[0]*w[0]+r[1]*w[1]>=r[2] for r in constraints):vertices.add(w)
    if not vertices:return None,()
    value=min(p[target]*w[0]+(1-p[target])*w[1] for w in vertices)
    return value,tuple(sorted(w for w in vertices if p[target]*w[0]+(1-p[target])*w[1]==value))


def menus(theta,pi,qualities,costs):
    theta=vec(theta,2);pi=num(pi);q=vec(qualities,3);c=vec(costs,3)
    need(0<theta[0]<theta[1] and 0<pi<1,'positive ordered types/full-support prior')
    need(0==q[0]<q[1]<q[2]<=1 and all(z>=0 for z in c) and c[0]==0,'three delivery modes')
    rows=[]
    for low in range(3):
        for high in range(low,3):
            rent=(F(0),(theta[1]-theta[0])*q[low]);price=(theta[0]*q[low],theta[1]*q[high]-rent[1])
            profit=(1-pi)*(price[0]-c[low])+pi*(price[1]-c[high])
            rows.append({'modes':(low,high),'q':(q[low],q[high]),'rent':rent,'price':price,'profit':profit})
    maximum=max(r['profit'] for r in rows)
    return tuple(rows),tuple(r['modes'] for r in rows if r['profit']==maximum)


def preferences(P,R):
    need(type(P) is dict and type(R) is dict and len(P)<=3 and len(R)<=3,'bounded matching sides')
    need(not set(P).intersection(R),'disjoint sides')
    for side,other in ((P,R),(R,P)):
        for name,order in side.items():
            need(type(name) is str and name in ('A','B','C','X','Y','Z'),'matching names')
            need(type(order) in (list,tuple) and all(type(j) is str and j in other for j in order),'ordered known report')
            need(len(order)==len(set(order)),'strict report')
    return P,R


def da(P,R):
    P,R=preferences(P,R);held={h:None for h in R};k={a:0 for a in P}
    while True:
        free=next((a for a in P if a not in held.values() and k[a]<len(P[a])),None)
        if free is None:break
        h=P[free][k[free]];k[free]+=1
        if free in R[h] and (held[h] is None or R[h].index(free)<R[h].index(held[h])):held[h]=free
    return {a:next((h for h in R if held[h]==a),None) for a in P}


def matching_set(P,R):
    P,R=preferences(P,R);feasible=[];stable=[]
    for destinations in product((None,)+tuple(R),repeat=len(P)):
        used=[h for h in destinations if h is not None]
        if len(set(used))!=len(used):continue
        mu=dict(zip(P,destinations))
        if any(h is not None and (h not in P[a] or a not in R[h]) for a,h in mu.items()):continue
        feasible.append(mu);owner={h:a for a,h in mu.items() if h is not None};block=[]
        for a in P:
            for h in P[a]:
                if a not in R[h]:continue
                applicant=mu[a] is None or P[a].index(h)<P[a].index(mu[a])
                recipient=h not in owner or R[h].index(a)<R[h].index(owner[h])
                if applicant and recipient:block.append((a,h))
        if not block:stable.append(mu)
    return tuple(feasible),tuple(stable)


class Audit:
    def __init__(self):self.comparisons=0;self.rejections=0
    def equal(self,a,b,label):self.comparisons+=1;need(a==b,label)
    def reject(self,call,label):
        try:call()
        except (ValueError,TypeError,SyntaxError,json.JSONDecodeError):self.rejections+=1;return
        raise ValueError('V13 Form A: missing rejection: '+label)


class Document(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.stack=[];self.ids=set();self.inputs={};self.calcs={};self.models={};self.questions={};self.answers={};self.rubrics={};self.sources={};self.links=[];self.domains={};self.headings={}
    def handle_starttag(self,tag,pairs):
        attrs=dict(pairs);need(len(attrs)==len(pairs),'duplicate HTML attribute')
        need(tag not in ('script','iframe','object','style','h1'),'static fragment without extra UI')
        if 'id' in attrs:
            i=attrs['id'];need(i not in self.ids and (i in ('form-a','solutions-a') or i.startswith('v13-exam-a-')),'unique namespaced ID');self.ids.add(i)
        if tag=='section':
            need(attrs.get('data-domain') in DOMAINS,'case domain');self.domains[attrs['id']]=attrs['data-domain']
        if tag=='a':
            self.links.append(attrs.get('href',''))
            if 'data-source' in attrs:
                i=attrs['data-source'];need(i in URLS and attrs['href']==URLS[i],'exact source URL');self.sources[i]=attrs['href']
        if any(k in attrs for k in ('data-input','data-calc','data-model')):
            need(not any(any(k in s['attrs'] for k in ('data-input','data-calc','data-model')) for s in self.stack),'no nested visible input/result markers')
        if tag not in ('br','hr','img','meta','link','input','wbr'):self.stack.append({'tag':tag,'attrs':attrs,'text':[]})
    def handle_endtag(self,tag):
        need(self.stack and self.stack[-1]['tag']==tag,'balanced explicit HTML: '+tag)
        node=self.stack.pop();a=node['attrs'];s=''.join(node['text']).strip()
        for attr,where in (('data-input',self.inputs),('data-calc',self.calcs),('data-model',self.models)):
            if attr in a:need(a[attr] not in where,'unique visible marker');where[a[attr]]=s
        if tag=='li' and any(n['tag']=='ol' and 'exercises' in n['attrs'].get('class','').split() for n in self.stack):
            i=a.get('id');need(i in PARTS and i not in self.questions,'exact scored prompt');self.questions[i]=(int(a['data-points']),s)
        if 'data-solution-for' in a:
            i=a['data-solution-for'];need(i not in self.answers and i in PARTS,'unique paired solution')
            need(any(n['tag']=='details' and 'solutions' in n['attrs'].get('class','').split() for n in self.stack),'standard solution disclosure');self.answers[i]=s
        if 'data-rubric-for' in a:
            i=a['data-rubric-for'];need(i not in self.rubrics and i in PARTS,'unique additive rubric');self.rubrics[i]=(int(a['data-points']),s)
        if tag=='h2':self.headings[a.get('id')]=s
    def handle_data(self,text):
        for node in self.stack:node['text'].append(text)


def numerical(A,raw):
    I={k:literal(v) for k,v in raw.items()};C={}
    expected_inputs={'a1-choice6':(3,3),'a1-p0':(1,1),'a1-choice10':(5,5),'a1-prior':(F(1,2),)*2,'a1-safe':(2,2),'a1-risk-low':(0,0),'a1-risk-high':(4,4),'a1-P':((F(3,4),F(1,4)),(F(1,4),F(3,4))),'a1-flip':F(1,4),'a1-incomes':(6,10),'a1-p1':(4,1),'a1-income-new':10,'a1-target':5,'a2-transfer-range':(0,6),'a2-shares':(F(1,3),F(2,3)),'a2-endowments':((6,0),(0,6)),'a2-transfers':(0,3,6),'a3-benefit':3,'a3-cost':2,'a3-recommendation':(F(1,2),F(1,2)),'a4-types':(2,6),'a4-prior':F(1,3),'a4-success':(F(3,4),F(1,4)),'a4-effort-cost':(1,0),'a4-wage-bounds':(0,2),'a4-cash':(6,2,0),'a4-prior-transfers':(F(1,4),F(1,2)),'a5-applicant-values':((3,2,0),(2,3,0)),'a5-institution-values':((1,2),(2,1)),'a5-applicant-lists':(('X','Y'),('Y','X')),'a5-priorities':(('B','A'),('A','B')),'a5-worlds':(0,2)}
    A.equal(I,expected_inputs,'all thirty-two actual visible primitives')
    for m,key in zip(I['a1-incomes'],('a1-choice6','a1-choice10')):
        for kind in ('cd','minimum'):A.equal(consumer(I['a1-p0'],m,kind),I[key],'two complete rationalizers')
    C['a1-new-U']=consumer(I['a1-p1'],I['a1-income-new']);C['a1-new-L']=consumer(I['a1-p1'],I['a1-income-new'],'minimum')
    p=I['a1-p1'];u=I['a1-target'];e=2*u*sqrt_exact(p[0]*p[1]);h=consumer(p,e)
    C['a1-e']=e;C['a1-h']=h
    S=((-e/(4*p[0]**2),e/(4*p[0]*p[1])),(e/(4*p[0]*p[1]),-e/(4*p[1]**2)));C['a1-S']=S
    A.equal(tuple(sum(S[i][j]*p[j] for j in range(2)) for i in range(2)),(0,0),'compensated price null direction')
    A.equal(S[0][1],S[1][0],'compensated symmetry');A.equal(S[0][0]*S[1][1]-S[0][1]**2,F(0),'rank-one Hessian determinant')
    A.equal(S[0][0]<0 and S[1][1]<0,True,'negative semidefinite rank-one Hessian')
    A.equal(h[0]*h[1],u*u,'target actually attained');A.equal(sum(p[i]*h[i] for i in range(2)),e,'compensated budget')
    prizes=(I['a1-safe'],I['a1-risk-low'],I['a1-risk-high']);utility=tuple(sqrt_exact(x*y) for x,y in prizes)
    payoff=((utility[0],utility[1]),(utility[0],utility[2]));P=I['a1-P'];flip=I['a1-flip'];G=((1-flip,flip),(flip,1-flip));Q=multiply(P,G)
    C['a1-Q']=Q
    for E,label in ((P,'P'),(Q,'Q')):
        mass=tuple(sum(I['a1-prior'][s]*E[s][z] for s in range(2)) for z in range(2))
        A.equal(mass,(F(1,2),)*2,'actual signal probabilities')
        C['a1-post-'+label]=tuple(I['a1-prior'][1]*E[1][z]/mass[z] for z in range(2))
        value,rules=decision(I['a1-prior'],E,payoff);C['a1-value-'+label]=value;A.equal(rules,((0,1),),'unique signal-contingent rule')
    no_signal=decision(I['a1-prior'],((1,),(1,)),payoff)
    A.equal(no_signal,(F(2),((0,),(1,))),'complete uninformed pure optima')
    C['a1-lottery-U']=(utility[0],sum(I['a1-prior'][s]*payoff[s][1] for s in range(2)))
    C['a1-lottery-square']=(utility[0]**2,sum(I['a1-prior'][s]*payoff[s][1]**2 for s in range(2)))
    # Verify statewise simulation for every deterministic Q rule, independently of decision maxima.
    for r in product((0,1),repeat=2):
        D=tuple(tuple(F(r[z]==a) for a in (0,1)) for z in range(2))
        A.equal(multiply(P,multiply(G,D)),multiply(Q,D),'statewise garbling simulation')
    ex=[]
    for t in I['a2-transfers']:
        r,m,x,w=exchange(I['a2-endowments'],I['a2-shares'],t);ex.append((r,m,x))
        A.equal(tuple(sum(z[j] for z in x) for j in range(2)),(6,6),'every commodity clears')
        A.equal(tuple(r*z[0]+z[1] for z in x),m,'every owned budget')
        A.equal(r,1-t/12,'full derived price-family anchor')
    C['a2-base-incomes']=ex[0][1];C['a2-transfer-price']=ex[1][0];C['a2-transfer-incomes']=ex[1][1]
    C['a2-transfer-A'],C['a2-transfer-B']=ex[1][2];C['a2-endpoint-price']=ex[2][0];C['a2-endpoint-bundles']=ex[2][2]
    C['a2-cube-A']=(ex[0][2][0][0]*ex[0][2][0][1]**2,ex[1][2][0][0]*ex[1][2][0][1]**2)
    C['a2-cube-B']=(ex[0][2][1][0]**2*ex[0][2][1][1],ex[1][2][1][0]**2*ex[1][2][1][1])
    A.equal((I['a2-shares'][0]-I['a2-shares'][1])/ex[1][0],F(-4,9),'fixed-price income redistribution derivative')
    b,k=I['a3-benefit'],I['a3-cost'];mix=(b-k)/b
    table=tuple(tuple(volunteer(a,z,b,k) for z in (1,0)) for a in (1,0))
    pure=[]
    for i,j in product(range(2),repeat=2):
        if table[i][j][0]>=table[1-i][j][0] and table[i][j][1]>=table[i][1-j][1]:pure.append((i,j))
    A.equal(pure,[(0,1),(1,0)],'complete simultaneous pure equilibria')
    A.equal(b*mix,b-k,'interior indifference from primitive payoffs');A.equal(mix,F(1,3),'interior probability')
    C['a3-independent-provision']=1-(1-mix)**2
    C['a3-independent-payoffs']=tuple(sum((mix if a else 1-mix)*(mix if z else 1-mix)*volunteer(a,z,b,k)[i] for a,z in product((0,1),repeat=2)) for i in range(2))
    recommendation=I['a3-recommendation'];joint={(1,0):recommendation[0],(0,1):recommendation[1]}
    for i,rec in product(range(2),(0,1)):
        margin=F(0)
        for action,mass in joint.items():
            if action[i]!=rec:continue
            dev=list(action);dev[i]=1-rec
            margin+=mass*(volunteer(*action,b,k)[i]-volunteer(*dev,b,k)[i])
        A.equal(margin>0,True,'every CE recommendation is strictly obedient')
    A.equal(tuple(sum(mass*volunteer(*a,b,k)[i] for a,mass in joint.items()) for i in range(2)),(2,2),'CE payoffs')
    A.equal(b/F(2)>b-k,True,'same independent marginals not Nash')
    normal=plan_payoffs(b,k);C['a3-SPE-payoffs']=normal[1][2]
    for q in (F(0),F(1,2),F(1)):
        A.equal(plan_nash(0,(q,0,1-q,0),normal),True,'whole first Nash family endpoints/interior')
    for r in (F(0),mix/2,mix):A.equal(plan_nash(1,(0,0,r,1-r),normal),True,'second Nash family boundary/interior')
    A.equal(plan_nash(1,(0,0,mix+F(1,10),1-mix-F(1,10)),normal),False,'noncredible family threshold violated')
    A.equal(plan_nash(F(1,2),(0,0,1,0),normal),False,'positive first-player mixing cannot be Nash')
    eps=F(1,10);d=(eps,eps,1-3*eps,eps)
    col=tuple(eps*normal[0][j][1]+(1-eps)*normal[1][j][1] for j in range(4))
    A.equal(tuple(j for j,z in enumerate(col) if z==max(col)),(2,),'unique NV best reply to full-support first tremble')
    A.equal(sum(d[j]*normal[1][j][0] for j in range(4)),3-6*eps,'explicit perfection payoff')
    p,c,cap=I['a4-success'],I['a4-effort-cost'],I['a4-wage-bounds'][1]
    H,Hw=worker_vertices(p,c,cap,0);L,Lw=worker_vertices(p,c,cap,1)
    A.equal((Hw,Lw),(((F(2),F(0)),),((F(0),F(0)),)),'complete minimum-wage vertices')
    C['a4-H-wages']=Hw[0];C['a4-H-cost']=H
    A.equal((p[0]-p[1])*cap-(c[0]-c[1]),F(0),'strict H impossible at escrow boundary')
    wages=Hw[0];target=p[0]*wages[0]+(1-p[0])*wages[1]-c[0];deviation=p[1]*wages[0]+(1-p[1])*wages[1]-c[1]
    A.equal((target,deviation),(F(1,2),)*2,'global worker deviation tie and IR')
    qualities=(F(0),p[1],p[0]);costs=(F(0),L,H);rows,optimal=menus(I['a4-types'],I['a4-prior'],qualities,costs)
    A.equal(optimal,((0,2),(1,2)),'all baseline profit maximizers')
    C['a4-baseline-profits']=tuple(r['profit'] for r in rows)
    for r in rows:
        for i,j in product(range(2),repeat=2):A.equal(I['a4-types'][i]*r['q'][i]-r['price'][i]>=I['a4-types'][i]*r['q'][j]-r['price'][j],True,'every global buyer report inequality')
        A.equal(all(0<=z<=I['a4-cash'][0] for z in r['price']),True,'all actual prices funded')
    selected={r['modes']:r for r in rows if r['modes'] in optimal}
    C['a4-price-0H']=(selected[(0,2)]['q'][1],selected[(0,2)]['price'][1]);C['a4-price-LH']=(selected[(1,2)]['q'][1],selected[(1,2)]['price'][1])
    for pi,key,wanted in zip(I['a4-prior-transfers'],('a4-quarter-profit','a4-half-profit'),((1,2),(0,2))):
        changed,winners=menus(I['a4-types'],pi,qualities,costs);A.equal(winners,(wanted,),'changed-prior complete winner')
        C[key]=max(r['profit'] for r in changed)
    def cash(T,w):return (I['a4-cash'][0]-T,I['a4-cash'][1]+T-w,I['a4-cash'][2]+w)
    for modes,label in (((0,2),'0H'),((1,2),'LH')):
        r=selected[modes];pi=I['a4-prior'];buyer=(1-pi)*r['rent'][0]+pi*r['rent'][1];worker=pi*target
        real=(1-pi)*I['a4-types'][0]*r['q'][0]+pi*(I['a4-types'][1]*r['q'][1]-c[0])
        A.equal(r['profit']+buyer+worker,real,'transfers cancel but effort cost remains');C['a4-surplus-'+label]=real
        C['a4-cash-'+label+'-S']=cash(r['price'][1],wages[0]);C['a4-cash-'+label+'-F']=cash(r['price'][1],wages[1])
        for T in r['price']:
            for w in wages:A.equal(sum(cash(T,w)),sum(I['a4-cash']),'every state cash total')
    C['a4-cash-L']=cash(selected[(1,2)]['price'][0],0)
    strict_rows=[r for r in rows if 2 not in r['modes']]
    A.equal(tuple(r['modes'] for r in strict_rows if r['profit']==max(z['profit'] for z in strict_rows)),((0,1),(1,1)),'all strict-effort baseline optima')
    A.equal(max(z['profit'] for z in strict_rows),F(1,2),'strict-effort maximum profit')
    P=dict(zip(('A','B'),I['a5-applicant-lists']));R=dict(zip(('X','Y'),I['a5-priorities']));feasible,stable=matching_set(P,R)
    A.equal(len(feasible),7,'complete individually rational matching set');A.equal({tuple(m.values()) for m in stable},{('X','Y'),('Y','X')},'all stable matchings')
    reports=((),('X',),('Y',),('X','Y'),('Y','X'));outcomes=[]
    for report in reports:
        changed=dict(P);changed['A']=report;outcomes.append(da(changed,R))
    A.equal(tuple(tuple(m.values()) for m in outcomes),((None,'Y'),('X','Y'),('Y','X'),('X','Y'),('Y','X')),'every ordered-subset report')
    av,bv=I['a5-applicant-values'];iv=I['a5-institution-values'];index={'X':0,'Y':1,None:2}
    def benefits(mu,lam):
        lam=num(lam);need(lam>=0,'nonnegative declared externality')
        applicants=(av[index[mu['A']]]+lam*int(mu['B']=='X'),bv[index[mu['B']]])
        recipients=tuple(next((iv[h][j] for j,a in enumerate(('A','B')) if mu[a]==name),F(0)) for h,name in enumerate(('X','Y')))
        return applicants+recipients
    for lam in (F(0),F(1,2),F(1),F(2)):
        values=tuple(benefits(mu,lam)[0] for mu in outcomes)
        A.equal(values,(0,3,2+lam,3,2+lam),'full report payoff externality law')
        A.equal(max(values),max(F(3),F(2)+lam),'actual best response including outside')
    old=outcomes[1];new=outcomes[2];C['a5-old']=benefits(old,I['a5-worlds'][0]);A.equal(C['a5-old'],benefits(old,I['a5-worlds'][1]),'actual administrative observational equivalence')
    C['a5-new-zero']=benefits(new,I['a5-worlds'][0]);C['a5-new-two']=benefits(new,I['a5-worlds'][1]);C['a5-sum-change']=(sum(C['a5-old']),sum(C['a5-new-two']))
    # This single symbolic marker has a coefficient independently checked above for four meaningful lambda values.
    C['a5-utilities']='0,3,2+λ,3,2+λ'
    return C


def invalid_domains(A):
    bad=[lambda:num(True),lambda:num(float('nan')),lambda:num(float('inf')),lambda:num(10**7),lambda:num(F(1,10**13)),lambda:vec([]),lambda:vec([1],2),lambda:matrix(((1,2),(1,))),lambda:probability((F(1,2),F(1,3))),lambda:probability((2,-1)),lambda:literal('__import__(1)'),lambda:literal('True'),lambda:literal('1/0'),lambda:literal('1e999'),lambda:literal('unknown'),lambda:sqrt_exact(-1),lambda:sqrt_exact(2),lambda:consumer((0,1),1),lambda:consumer((1,1),-1),lambda:consumer((1,1),1,'other'),lambda:decision((1,),((F(1,2),),),((1,),)),lambda:exchange(((6,0),(0,6)),(F(1,3),F(2,3)),7),lambda:exchange(((6,0),(0,6)),(0,1),0),lambda:volunteer(True,0,3,2),lambda:volunteer(1,0,2,2),lambda:plan_nash(2,(0,0,1,0),plan_payoffs(3,2)),lambda:worker_vertices((F(1,4),F(3,4)),(1,0),2,0),lambda:worker_vertices((F(3,4),F(1,4)),(1,0),2,True),lambda:menus((2,6),0,(0,F(1,4),F(3,4)),(0,0,F(3,2))),lambda:menus((6,2),F(1,3),(0,F(1,4),F(3,4)),(0,0,F(3,2))),lambda:preferences({'A':('X','X')},{'X':('A',)}),lambda:preferences({'A':('Y',)},{'X':('A',)}),lambda:preferences({'A':{'X'}},{'X':('A',)}),lambda:strict_json('{"x":1,"x":2}'),lambda:strict_json('{"x":NaN}'),lambda:strict_json('{"x":1e999}')]
    for i,call in enumerate(bad):A.reject(call,'domain '+str(i+1))


def compact(s):return re.sub(r'\s+','',s).replace('−','-')


def check(root=None):
    need(root is None or type(root) is str or isinstance(root,Path),'root path type')
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    raw={p:(root/p).read_bytes() for p in FILES};A=Audit();doc=Document();doc.feed(raw[FILES[0]].decode());doc.close()
    A.equal(doc.stack,[],'all tags closed');A.equal(set(doc.headings),{'form-a','solutions-a'},'exact two assembly headings')
    A.equal({k:v[0] for k,v in doc.questions.items()},PARTS,'all twenty point-valued prompts')
    A.equal(set(doc.answers),set(PARTS),'all twenty complete paired answers');A.equal({k:v[0] for k,v in doc.rubrics.items()},PARTS,'all twenty additive rubrics')
    A.equal(sum(v[0] for v in doc.questions.values()),100,'paper points')
    for i in range(1,6):A.equal(sum(v[0] for k,v in doc.questions.items() if k.startswith(f'v13-exam-a-{i}')),20,'essential domain points')
    for i,domain in enumerate(DOMAINS,1):A.equal(doc.domains.get(f'v13-exam-a-case{i}'),domain,'case/domain map')
    A.equal(all(len(t)>450 for t in doc.answers.values()),True,'substantive answer bodies')
    for ident,(_,text) in doc.rubrics.items():A.equal(sum(int(n) for n in re.findall(r'(\d+) for ',text)),PARTS[ident],'actual additive scoring prose')
    models={'choice':'U(x,y)=√(xy); L(x,y)=min(x,y)','exchange':'uA=xA^(1/3)yA^(2/3); uB=xB^(2/3)yB^(1/3)','volunteer':'ui=3·1{a1+a2≥1}−2ai','buyer':'θq−T','externality':'vA(μ(A))+λ·1{μ(B)=X}'}
    A.equal({k:compact(v) for k,v in doc.models.items()},{k:compact(v) for k,v in models.items()},'actual visible functional laws')
    values=numerical(A,doc.inputs);invalid_domains(A);A.equal(set(values),set(doc.calcs),'complete result-marker inventory')
    arrows={'a2-cube-A','a2-cube-B','a5-sum-change'}
    for key,expected in values.items():
        if key=='a5-utilities':actual=compact(doc.calcs[key]);expected=compact(expected)
        elif key in arrows:actual=tuple(literal(v) for v in doc.calcs[key].split('→'))
        else:actual=literal(doc.calcs[key])
        A.equal(actual,expected,'actual visible result '+key)
    A.equal({h for h in doc.links if not h.startswith(('https://','http://'))},{f'v13-c{i:02}.html' for i in range(1,13)},'exact flat chapter routes')
    A.equal(doc.sources,URLS,'all scoped method references')
    source=strict_json(raw[FILES[2]].decode());author=strict_json(raw[FILES[3]].decode())
    A.equal((source['volume'],source['component']),('v13','exam_a'),'source identity')
    A.equal({s['id']:s['url'] for s in source['sources']},URLS,'source record URL identities')
    A.equal(all(s.get('prior_actual_inspector') and s.get('inherited_scope') and s.get('limits') and s['mode']=='reuse_accepted_scoped_evidence' for s in source['sources']),True,'source attribution and limits')
    A.equal((source['new_primary_retrievals'],source['new_primary_image_views']),(0,0),'honest inherited inspection')
    A.equal((author['volume'],author['component']),('v13','exam_a'),'author identity')
    A.equal(author['runtime_payloads'],list(FILES),'exact four runtime files')
    A.equal({x['path'] for x in author['bindings']},set(FILES[:3]),'three nonself payload bindings')
    for x in author['bindings']:
        data=raw[x['path']];A.equal((x['bytes'],x['sha256']),(len(data),sha256(data).hexdigest()),'payload binding '+x['path'])
    A.equal({x['id'] for x in author['prompt_solution_audit']},set(PARTS),'all exact author solution audits')
    A.equal({x['domain'] for x in author['proof_audit']},set(DOMAINS),'all proof domains reviewed')
    A.equal(author['open_findings'],[],'no unresolved author finding')
    result={'volume':'v13','component':'exam_a','status':'passed','comparisons':A.comparisons,'domain_rejections':A.rejections,'visible_inputs':len(doc.inputs),'visible_results':len(doc.calcs),'scored_parts':len(doc.questions),'paired_solutions':len(doc.answers),'points':100,'runtime_files':4,'finite_scope':{'signal_rules_per_two_signal_experiment':4,'service_mode_pairs':6,'applicant_reports':5,'partial_matchings':7},'limits':'Exact finite arithmetic, structure and bindings; universal proof review, independent acceptance and reader rendering are separate.'}
    json.dumps(result,allow_nan=False);return result


if __name__=='__main__':
    need(len(sys.argv)==1,'silent CLI takes no arguments');check()
