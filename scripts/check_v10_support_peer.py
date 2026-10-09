"""Separate support peer: original arithmetic, probability and cash reconstruction.
Never imports or invokes the root assessment aggregator.
"""
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from itertools import combinations, product
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
AUTHOR_PATHS=(
    'content/assessments/parts/v10-support-opening.html',
    'content/assessments/parts/v10-support-closing.html',
    'scripts/check_v10_assessment.py',
    'content/reviews/v10-support-author.json',
    'content/reviews/v10-support-sources.json',
)


def require(test,label):
    if not test:raise AssertionError(label)


class Audit:
    def __init__(self):self.count=0
    def eq(self,a,b,label):self.count+=1;require(a==b,label+': '+repr(a)+' != '+repr(b))
    def near(self,a,b,label,tolerance=2e-9):
        self.count+=1;require(math.isfinite(float(a)) and abs(float(a)-float(b))<=tolerance,label)
    def true(self,test,label):self.count+=1;require(test,label)


def solve(matrix,rhs):
    rows=[[F(x) for x in row]+[F(y)] for row,y in zip(matrix,rhs)]
    for col in range(len(rhs)):
        pivot=next(i for i in range(col,len(rhs)) if rows[i][col])
        rows[col],rows[pivot]=rows[pivot],rows[col]
        scale=rows[col][col];rows[col]=[x/scale for x in rows[col]]
        for i in range(len(rhs)):
            if i!=col:
                scale=rows[i][col];rows[i]=[x-scale*y for x,y in zip(rows[i],rows[col])]
    return [row[-1] for row in rows]


def simpson(f,a,b,n=4096):
    h=(b-a)/n
    return h/3*(f(a)+f(b)+4*math.fsum(f(a+i*h) for i in range(1,n,2))+2*math.fsum(f(a+i*h) for i in range(2,n,2)))


class Fragment(HTMLParser):
    def __init__(self):
        super().__init__();self.stack=[];self.ids=[];self.links=[];self.points={};self.solutions=[];self.headings=0
    def handle_starttag(self,tag,attrs):
        d=dict(attrs)
        if 'id' in d:self.ids.append(d['id'])
        if tag=='h1':self.headings+=1
        if tag=='a':self.links.append(d.get('href',''))
        if 'data-points' in d:
            require(tag=='li' and 'id' in d,'scored support prompt must be a labeled list item')
            require(d['id'] not in self.points,'duplicate scored prompt')
            self.points[d['id']]=int(d['data-points'])
        if 'data-solution-for' in d:self.solutions.append(d['data-solution-for'])
        if tag not in ('br','hr','img','link','meta','input'):self.stack.append(tag)
    def handle_endtag(self,tag):
        require(self.stack and self.stack[-1]==tag,'unbalanced support tag '+tag);self.stack.pop()


def check():
    a=Audit()
    # Diagnostic1/2: cash-vector distinction and a separately differenced price.
    dated=sum(c*d for c,d in zip((12,112),(F(97,100),F(23,25))))
    moved=sum((12,112))*F(23,25)
    a.eq((dated,moved,dated-moved),(F(2867,25),F(2852,25),F(3,5)),'D1 independent dated strips')
    price=lambda y:100*math.exp(-2*y)
    bump=1e-4
    a.near((price(bump)-price(-bump))/(2*bump),-200,'D2 central derivative',2e-6)
    a.near((price(bump)-2*price(0)+price(-bump))/bump**2,400,'D2 central curvature',4e-6)
    a.near(price(.01)-price(0),-1.98013266932447,'D2 finite change')
    a.eq(F(-200)*F(1,100),F(-2),'D2 first order')
    a.eq(F(400,2)*F(1,100)**2,F(1,50),'D2 positive second-order term')
    a.eq(F(1,100)*10000,100,'D2 basis points')
    # D3: independent finite laws realize both specified covariance structures.
    states=list(product((-1,1),repeat=2))
    for weights,expected_cov,expected_var in (([F(1,4)]*4,F(0),F(18,25)),([F(3,8),F(1,8),F(1,8),F(3,8)],F(3,100),F(9,25))):
        values=[(F(x,5),F(3*y,10)) for x,y in states]
        a.eq(sum(p*x*y for p,(x,y) in zip(weights,values)),expected_cov,'D3 feasible joint covariance')
        a.eq(sum(p*(3*x-2*y) for p,(x,y) in zip(weights,values)),0,'D3 transformed mean')
        a.eq(sum(p*(3*x-2*y)**2 for p,(x,y) in zip(weights,values)),expected_var,'D3 directly enumerated variance')
    holdings=solve([[60,1],[120,1]],[0,30])
    states_prices=solve([[1,1],[60,120]],[F(19,20),90])
    a.eq(holdings,[F(1,2),F(-30)],'D4 linear-system holdings')
    a.eq(states_prices,[F(2,5),F(11,20)],'D4 independently solved state prices')
    a.eq(90*holdings[0]+F(19,20)*holdings[1],30*states_prices[1],'D4 dual price agreement')
    a.eq(30*states_prices[1],F(33,2),'D4 cost')
    a.true(min(states_prices)>0,'D4 strict state positivity')
    se=F(2,10);half=F(49,25)*se
    a.eq((F(-1,10)-half,F(-1,10)+half),(F(-123,250),F(73,250)),'D5 fixed-rule interval')
    delta,gamma=F(40,50),F(2,50)
    a.eq((delta,gamma,F(23*23-20*20,50)),(F(4,5),F(1,25),F(129,50)),'D6 derivatives and exact quadratic change')
    a.eq(F(129,50)-delta*3-gamma*9/2,0,'D6 zero quadratic remainder')
    incoming=3*35-F(100)*F(51,50)
    bank=-F(100)*F(51,50)+35
    a.eq((incoming,bank,2*35+bank,5-incoming),(F(3),F(-67),F(3),F(2)),'D7 wealth and funding conservation')

    # Oral1/2: a curvature difference and ordered cash availability.
    a.eq(F(300-500,2)*F(1,100)**2,F(-1,100),'O1 signed surplus')
    a.eq(F(300-500,2)*F(-1,100)**2,F(-1,100),'O1 reverse move has same quadratic sign')
    balance=5;sequence=[]
    for cash in (-3,-4,6):balance+=cash;sequence.append(balance)
    a.eq(sequence,[2,-2,4],'O2 future cash cannot cure earlier shortfall')
    a.eq(5-3+2-4,0,'O2 timely facility cures immediate gap before its costs')
    # O3: direct Gaussian integration of the discounted squared terminal stock.
    normal=lambda z:math.exp(-z*z/2)/math.sqrt(2*math.pi)
    squared=lambda z:math.exp(-.02)*100*math.exp(2*((.02-.3**2/2)+.3*z))
    expectation=simpson(lambda z:squared(z)*normal(z),-12,12)
    a.near(expectation,100*math.exp(.11),'O3 independently integrated GBM second moment',2e-8)
    a.near(expectation,111.62780704588713,'O3 numerical teaching anchor',2e-8)
    a.eq(2*F(1,50)+F(3,10)**2,F(13,100),'O3 Ito drift coefficient')
    a.eq(F(13,100)-F(1,50),F(11,100),'O3 discounted drift coefficient')
    a.eq(2*F(3,10),F(3,5),'O3 diffusion coefficient')
    wing=[F(1,2),F(-1),F(1,2)]
    for middle,cost in ((9,F(1,2)),(10,F(-1,2))):
        a.eq(sum(w*c for w,c in zip(wing,(14,middle,5))),cost,'O4 normalized butterfly price')
    for stock in (0,80,90,95,100,105,110,120,200):
        payoff=sum(w*max(stock-strike,0) for w,strike in zip(wing,(90,100,110)))
        a.true(payoff>=0,'O4 nonnegative piecewise-linear payoff')
    for strike,quote in ((90,14),(100,9),(100,10),(110,5)):
        a.true(max(100-strike,0)<quote<100,'O4 individual inversion interior does not test convexity')
    family=lambda t,c:100-t+c*t*(t-1)
    endpoints=[family(2,F(x,4)) for x in (-1,1)]
    a.eq(endpoints,[F(195,2),F(197,2)],'O5 imposed identification range')
    a.eq(endpoints[1]-endpoints[0],1,'O5 width fails quarter-CU bound')
    a.eq([family(1,F(x,4)) for x in (-1,1)],[F(99),F(99)],'O5 restricted calibrated target')

    # Retention1/2: solve the quote system and date every carry/credit cash.
    discounts=solve([[100,0],[5,105]],[97,F(1987,20)])
    a.eq(discounts,[F(97,100),F(9,10)],'R1 simultaneous curve calibration')
    a.eq(discounts[0]/discounts[1]-1,F(7,90),'R1 effective one-year forward')
    value=150*discounts[1]
    a.eq(value,F(135),'R1 dated liability')
    a.eq(-2*value*F(1,500),F(-27,50),'R1 named-coordinate first derivative')
    a.near(float(value)*math.exp(-2*.002)-float(value),-.53892143856115,'R1 independent exact perturbation')
    dividend=2*F(99,100);prepaid=48-dividend;forward=prepaid/F(47,50)
    a.eq((prepaid,forward,prepaid-F(49)*F(47,50)),(F(2301,50),F(2301,47),F(-1,25)),'R2 carry and existing signed value')
    probabilities=[F(23,25),F(2,25)];payments=[100,35]
    receipt=sum(p*x for p,x in zip(probabilities,payments));note=F(47,50)*receipt
    a.eq((receipt,note,94-note),(F(474,5),F(11139,125),F(611,125)),'R2 state-weighted terminal cash and discounted loss')
    premium_annuity=F(47,50)*probabilities[0]*100
    protection=F(47,50)*probabilities[1]*65
    spread=protection/premium_annuity
    a.eq(spread,F(13,230),'R2 zero-upfront survival-only premium')
    a.eq(spread*premium_annuity-protection,F(0),'R2 exactly balanced dated legs')
    a.near(float(spread)*10000,565.2173913043478,'R2 basis-point rate')
    # R3: independent state matching and direct tilted-density moments.
    holdings=solve([[40,1],[70,1]],[0,18])
    stateprices=solve([[1,1],[40,70]],[F(20,21),50])
    a.eq(holdings,[F(3,5),F(-24)],'R3 exact replica')
    a.eq(holdings[0]*50+holdings[1]*F(20,21),F(50,7),'R3 financed call')
    a.eq(stateprices[1]/sum(stateprices),F(5,12),'R3 pricing probability via state-price system')
    mu,sigma,q,r=F(2,25),F(1,5),F(1,100),F(3,100)
    lam=(mu-(r-q))/sigma
    a.eq((mu-sigma*sigma/2,r-q,lam,mu-sigma*lam-sigma*sigma/2),(F(3,50),F(1,50),F(3,10),F(0)),'R3 physical/pricing log drift and tilt')
    for time in (.25,1.0,3.0):
        root=math.sqrt(time)
        density=lambda z:normal(z)*math.exp(-float(lam)*root*z-.5*float(lam)**2*time)
        mass=simpson(density,-12,12)
        first=simpson(lambda z:root*z*density(z),-12,12)
        second=simpson(lambda z:time*z*z*density(z),-12,12)
        a.near(mass,1,'R3 independent density normalization')
        a.near(first,-float(lam)*time,'R3 tilted Brownian coordinate mean')
        a.near(second-first*first,time,'R3 tilted Brownian coordinate variance',2e-8)
    # R4 uses exact signed cash-scaled mark components, separate from financing.
    terms=[F(9,20)*2,F(1,50)*4/2,30*F(1,100),F(-5,250)]
    a.eq(terms,[F(9,10),F(1,25),F(3,10),F(-1,50)],'R4 separate Greek units')
    a.eq(sum(terms),F(61,50),'R4 unit mark')
    shares=200*F(9,20);a.eq(shares,90,'R4 signed delta neutralization')
    a.eq(-200*sum(terms)+shares*2,F(-64),'R4 option-plus-fixed-stock mark')
    vraw,vpair=F(36,400),F(9,200)
    a.eq((vraw,vpair,vpair/vraw),(F(9,100),F(9,200),F(1,2)),'R4 equal evaluation budget mean variances')
    a.near(math.sqrt(float(vraw)),.3,'R4 raw SE')
    a.near(math.sqrt(float(vpair)),.212132034355964,'R4 pair SE')
    a.near(1.96*math.sqrt(float(vraw)),.588,'R4 raw interval half-width')
    a.near(1.96*math.sqrt(float(vpair)),.41577878733769,'R4 pair interval half-width')

    # R5: enumerate feasible basic state-price laws, then certify both hedge bounds.
    stock=[20,50,80];payoff=[0,0,30];disc=F(19,20);forward=F(50)/disc
    vertices=[]
    for left,right in combinations(range(3),2):
        weights=solve([[1,1],[stock[left],stock[right]]],[1,forward])
        if min(weights)>=0:
            law=[F(0)]*3;law[left],law[right]=weights;vertices.append(law)
    prices=[disc*sum(p*h for p,h in zip(v,payoff)) for v in vertices]
    a.eq((min(prices),max(prices)),(F(5,2),F(31,2)),'R5 independently optimized finite bounds')
    a.eq(vertices,[[F(26,57),F(0),F(31,57)],[F(0),F(52,57),F(5,57)]],'R5 exact extremal laws')
    for coefficient in (F(1,57),F(5,19),F(25,57)):
        law=[coefficient,F(52,57)-2*coefficient,coefficient+F(5,57)]
        a.true(min(law)>0,'R5 strictly positive interior')
        a.eq(sum(law),1,'R5 normalization')
        a.eq(disc*sum(p*s for p,s in zip(law,stock)),50,'R5 calibrated interior stock')
    lower=[s-50 for s in stock];upper=[F(s,2)-10 for s in stock]
    a.eq([h-v for h,v in zip(payoff,lower)],[F(30),F(0),F(0)],'R5 lower-endpoint arbitrage certificate')
    a.eq([v-h for h,v in zip(payoff,upper)],[F(0),F(15),F(0)],'R5 upper-endpoint arbitrage certificate')
    a.eq((50-50*disc,25-10*disc),(min(prices),max(prices)),'R5 portfolio funding at exact endpoints')
    a.true(F(1,50)<=F(3,100),'R5 unit error within tolerance')
    a.eq((600*F(1,50),400*F(1,50)),(F(12),F(8)),'R5 signed book discrepancy and inclusive boundary')

    # Complete prompt structure, source scope and real chapter routes.
    parser=Fragment()
    for path in AUTHOR_PATHS[:2]:
        parser.feed((ROOT/path).read_text());a.eq(parser.stack,[],'balanced independent support fragment')
    a.eq(parser.headings,1,'exactly one assessment main heading')
    a.eq(len(parser.ids),len(set(parser.ids)),'unique support anchors')
    for prefix,n,points in (('v10-d',8,5),('v10-o',5,4),('v10-r',5,20)):
        actual={k:v for k,v in parser.points.items() if k.startswith(prefix)}
        a.eq(actual,{prefix+str(i):points for i in range(1,n+1)},'complete point schedule '+prefix)
    a.eq(set(parser.solutions),set(parser.points),'all eighteen exact prompts answered')
    a.eq(len(parser.solutions),18,'no duplicated or missing support solutions')
    for link in sorted(set(parser.links)):
        if link.startswith('v') and link.endswith('.html'):
            a.true((ROOT/'content/chapters'/link).is_file(),'authored prerequisite/remediation route '+link)
    a.true('curriculum.html#v11' in parser.links,'planned successor routes to canonical curriculum')
    sources=json.loads((ROOT/AUTHOR_PATHS[4]).read_text())
    a.eq(sources['proposals'],[],'source reuse adds no unsupported external proposal')
    a.eq(sources['chapter_routes'],['v10-c%02d'%i for i in range(1,13)],'all twelve source/remediation routes')
    author=json.loads((ROOT/AUTHOR_PATHS[3]).read_text())
    a.eq({row['path'] for row in author['reviewed_hashes']},set(AUTHOR_PATHS)-{AUTHOR_PATHS[3]},'four nonself author files')
    for row in author['reviewed_hashes']:
        payload=(ROOT/row['path']).read_bytes()
        a.eq((len(payload),sha256(payload).hexdigest()),(row['bytes'],row['sha256']),'author content hash binding')
    peer=json.loads((ROOT/'content/reviews/v10-support-peer.json').read_text())
    a.eq({row['path'] for row in peer['reviewed_hashes']},set(AUTHOR_PATHS),'peer binds all five final author files')
    a.eq(len(peer['reviewed_hashes']),5,'no duplicated peer payload')
    for row in peer['reviewed_hashes']:
        payload=(ROOT/row['path']).read_bytes()
        a.eq((len(payload),sha256(payload).hexdigest()),(row['bytes'],row['sha256']),'peer final author binding')
    for row in peer['reviewer_artifacts']:
        payload=(ROOT/row['path']).read_bytes()
        a.eq((len(payload),sha256(payload).hexdigest()),(row['bytes'],row['sha256']),'peer checker binding')
    result={'component':'v10-assessment-support','status':'passed','peer_comparisons':a.count,
            'diagnostic_prompts_reviewed':8,'oral_transfers_reviewed':5,'retention_prompts_reviewed':5,
            'author_files_bound':5,'root_aggregator_invoked':False,
            'limits':'Separate machine-assisted peer audit. Thresholds/timings are authored designs; calculations do not certify learner competence, empirical model adequacy or visual UI QA.'}
    json.dumps(result,allow_nan=False)
    return result


if __name__=='__main__':print(json.dumps(check(),indent=2,allow_nan=False))
