"""Independent arithmetic and structure checks for the original v10 Form A."""
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from itertools import product, combinations
import json
import math
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT/'content/assessments/parts/v10-exam-a.html'
SOURCE = ROOT/'content/reviews/v10-exam-a-sources.json'
AUTHOR = ROOT/'content/reviews/v10-exam-a-author.json'
OWNED = ['content/assessments/parts/v10-exam-a.html','scripts/check_v10_exam_a.py',
         'content/reviews/v10-exam-a-author.json','content/reviews/v10-exam-a-sources.json']


def require(ok, label):
    if not ok:
        raise AssertionError(label)


class Audit:
    def __init__(self):
        self.comparisons=0;self.groups=[];self.interventions=[]
    def eq(self, actual, expected, label):
        self.comparisons+=1
        require(actual==expected,label+': '+repr(actual)+' != '+repr(expected))
    def true(self, ok, label):
        self.comparisons+=1;require(ok,label)
    def near(self, actual, expected, label, tolerance=2e-10):
        self.comparisons+=1
        require(math.isfinite(float(actual)) and abs(float(actual)-float(expected))<=tolerance,label+': '+repr(actual)+' != '+repr(expected))


class Fragment(HTMLParser):
    def __init__(self):
        super().__init__();self.stack=[];self.ids=[];self.parts={};self.solutions=[];self.hrefs=[];self.text=[]
    def handle_starttag(self, tag, attrs):
        x=dict(attrs)
        require(tag not in ('html','head','body','h1','script'),'assessment fragment only')
        if 'id'in x:self.ids.append(x['id'])
        if 'href'in x:self.hrefs.append(x['href'])
        if 'data-points'in x:
            require(tag=='li' and x.get('id') and x.get('data-domain'),'scored li with ID/domain')
            require(x['id'] not in self.parts,'unique scored ID')
            self.parts[x['id']]=(int(x['data-points']),x['data-domain'])
        if 'data-solution-for'in x:
            require(tag=='li','solution li convention');self.solutions.append(x['data-solution-for'])
        if tag not in ('br','hr','img','meta','link','input'):self.stack.append(tag)
    def handle_endtag(self, tag):
        require(self.stack and self.stack[-1]==tag,'balanced HTML '+tag);self.stack.pop()
    def handle_data(self, data):self.text.append(data)


def solve(matrix, rhs):
    """Exact pivoted elimination, independent of hand solution substitutions."""
    rows=[[F(x) for x in row]+[F(y)] for row,y in zip(matrix,rhs)]
    size=len(rows)
    for column in range(size):
        pivot=next((j for j in range(column,size) if rows[j][column]),None)
        require(pivot is not None,'nonsingular independently solved system')
        rows[pivot],rows[column]=rows[column],rows[pivot]
        factor=rows[column][column];rows[column]=[x/factor for x in rows[column]]
        for j in range(size):
            if j!=column:
                factor=rows[j][column]
                rows[j]=[x-factor*y for x,y in zip(rows[j],rows[column])]
    return [row[-1] for row in rows]


def simpson(function, start, stop, n=2048):
    h=(stop-start)/n
    return h/3*(function(start)+function(stop)
                +4*math.fsum(function(start+i*h) for i in range(1,n,2))
                +2*math.fsum(function(start+i*h) for i in range(2,n,2)))


def check():
    a=Audit();html=HTML.read_text();f=Fragment();f.feed(html);plain=''.join(f.text)
    a.eq(f.stack,[],'balanced standalone fragment')
    a.eq(len(f.ids),len(set(f.ids)),'unique fragment IDs')
    a.true(all(x in ('form-a','solutions-a') or x.startswith('v10-a-') for x in f.ids),'exact A namespace')
    allocations=[[5,5,5,5],[6,3,6,5],[6,6,8],[6,4,6,4],[5,6,3,6]]
    expected={f'v10-a-q{q}{chr(97+i)}':(points,f'D{q}') for q,parts in enumerate(allocations,1) for i,points in enumerate(parts)}
    a.eq(f.parts,expected,'19 exact scored prompts and individual allocations')
    a.eq(set(f.solutions),set(expected),'every prompt has a full solution link')
    a.eq(len(f.solutions),19,'19 solutions without duplicates')
    for domain in ('D1','D2','D3','D4','D5'):
        a.eq(sum(points for points,d in f.parts.values() if d==domain),20,'essential domain total')
    a.eq(sum(p for p,d in f.parts.values()),100,'complete examination total')
    a.eq(sum((45,45,55,50,45)),240,'suggested minutes')
    for i in range(1,13):a.true(f'v10-c{i:02d}.html' in f.hrefs,'accepted chapter method route')
    for literal in ('240 minutes','85/100','15/20','nonprogrammable','No normal-CDF lookup','not a calibrated','Scoring, 8','Scoring, 6'):
        a.true(literal in plain,'assessment contract '+literal)
    sources=json.loads(SOURCE.read_text())
    a.eq(sources['proposals'],[],'no new source proposed')
    source_ids={x['id'] for x in sources['reused_sources']}
    a.eq(source_ids,{x.split('#')[1] for x in f.hrefs if x.startswith('sources.html#')},'exact scoped source reuse')
    a.eq(len(source_ids),12,'twelve reused method scopes')
    for row in sources['reused_sources']:
        a.true(all(row.get(k) for k in ('id','url','title','use','checked','verification','reused_body_scope')),'complete source provenance scope')
    a.groups.append('complete 100-point/19-subpart structure, five essential domains, all12 chapter routes and scoped source reuse')

    # D1: solve the whole coupon system, then a distinct exposure system.
    discounts=solve([[100,0,0],[4,104,0],[5,5,105]],[98,F('100.744'),F('101.955')])
    a.eq(discounts,[F('.98'),F('.931'),F('.88')],'full cash matrix inversion')
    a.eq(sum(c*d for c,d in zip((5,5,105),discounts)),F('101.955'),'third dirty price reconstructed')
    accrued=F(5)*F(1,2);clean=F('101.955')-accrued
    a.eq((accrued,clean),(F('2.5'),F('99.455')),'elapsed coupon and clean convention')
    times=[F(1,2),F(3,2),F(5,2)];liability=100*discounts[1]
    quantities=solve([[discounts[0],discounts[2]],[times[0]*discounts[0],times[2]*discounts[2]]],[liability,times[1]*liability])
    a.eq(quantities,[F(95,2),F(4655,88)],'barbell matching by exact elimination')
    cash=[quantities[0],F(-100),quantities[1]]
    a.eq(sum(c*d for c,d in zip(cash,discounts)),0,'initial surplus')
    a.eq(sum(-t*c*d for t,c,d in zip(times,cash,discounts)),0,'parallel first derivative')
    key=[-t*c*d for t,c,d in zip(times,cash,discounts)]
    a.eq(key,[F('-23.275'),F('139.65'),F('-116.375')],'full key-rate vector remains nonzero')
    bump=F('.01');linear=key[1]*bump
    bumped=[float(discounts[0]),float(discounts[1])*math.exp(-float(times[1]*bump)),float(discounts[2])]
    surplus=math.fsum(float(c)*d for c,d in zip(cash,bumped))
    a.eq(linear,F('1.3965'),'first-order twist')
    a.near(surplus,1.3860784229548675,'direct bumped dated surplus')
    for shift in (-.02,.02):
        changed=math.fsum(float(c*d)*math.exp(-float(t)*shift) for c,d,t in zip(cash,discounts,times))
        a.true(changed>0,'barbell convexity under pure parallel shift differs from twist')
        a.interventions.append('parallel shift '+str(shift))
    d=[F('.99'),F('.91')];q=[F(1,2)]*2;p=[F(3,4),F(1,4)]
    rates=[1/x-1 for x in d];dq=sum(w*x for w,x in zip(q,d));eq=sum(w*x for w,x in zip(q,rates));ep=sum(w*x for w,x in zip(p,rates));forward=discounts[0]/discounts[1]-1
    a.eq(discounts[0]*dq,discounts[1],'calibrated two-step cash discount')
    a.eq((forward,eq,ep),(F(1,19),F(491,9009),F(97,3003)),'pricing and physical rate means')
    a.eq(forward-ep,(forward-eq)+(eq-ep),'forecast gap decomposition')
    a.true(forward<eq and forward>ep,'distinct nonlinear/measure directions')
    a.near(forward-eq,-.00186947555368608,'nonlinear averaging amount')
    a.near(eq-ep,.0222000222000222,'measure component amount')
    a.eq(sum(w*x for w,x in zip(list(reversed(p)),d)),F('.93'),'physical probability change does not calibrate a new Q')
    a.interventions.append('physical branch reversal with fixed pricing curve')
    a.groups.append('D1 exact cash-matrix bootstrap, accrued/clean cash, exposure-system barbell, nonparallel repricing and independent P/Q rate means')

    # D2: integrate the default density instead of reusing the closed price.
    density=lambda t:.06*math.exp(-.06*t)
    survivor=100*math.exp(-.04*2)*math.exp(-.06*2)
    immediate=survivor+simpson(lambda t:50*math.exp(-.04*t)*density(t),0,2)
    maturity=survivor+math.exp(-.08)*simpson(lambda t:50*density(t),0,2)
    a.near(immediate,87.31115271545872,'independent immediate recovery integration')
    a.near(maturity,87.09235497323088,'independent maturity recovery integration')
    a.near(immediate-maturity,.2187977422278351,'recovery timing value')
    a.near(simpson(density,0,2),1-math.exp(-.12),'first-default probability integral')
    a.near(1-math.exp(-.12),.11307956328284252,'pricing cumulative default probability')
    a.true(immediate>maturity,'earlier recovery greater at positive rate')
    no_discount=100*math.exp(-.12)+simpson(lambda t:50*density(t),0,2)
    a.near(no_discount,100*math.exp(-.12)+50*(1-math.exp(-.12)),'zero-rate recovery timing equality')
    a.interventions.append('zero-rate recovery timing')
    ds=[F(1),F('.96'),F('.90')];fw=[ds[i-1]/ds[i]-1 for i in (1,2)]
    nets=[100*(x-F('.05')) for x in fw]
    pvs=[nets[i]*ds[i+1] for i in range(2)]
    a.eq(fw,[F(1,24),F(1,15)],'deposit forward coupons')
    a.eq(nets,[F(-5,6),F(5,3)],'dated swap net payments')
    a.eq(pvs,[F(-4,5),F(3,2)],'discounted swap net payments')
    a.eq(sum(pvs),F(7,10),'payer-fixed reference value')
    floating=sum(100*fw[i]*ds[i+1] for i in range(2));annuity=sum(ds[1:]);par=floating/(100*annuity)
    a.eq((floating,annuity,par),(10,F('1.86'),F(5,93)),'rolling-deposit leg and par coupon')
    a.eq(sum(100*F('.05')*x for x in ds[1:]),F('9.3'),'different constant projected index need not telescope')
    a.interventions.append('different floating projection')
    loan0=F(12);bank_factor=F('1.06');collateral_factor=F('1.01')
    collateral1=loan0*collateral_factor;debt1=loan0*bank_factor;release=collateral1-8;retained_debt=debt1-release
    collateral2=8*collateral_factor;debt2=retained_debt*bank_factor;net=collateral2-debt2
    a.eq((collateral1,debt1,release,retained_debt,collateral2,debt2,net),tuple(map(F,('12.12','12.72','4.12','8.60','8.08','9.116','-1.036'))),'full dated segregated margin ledger')
    a.eq(release*bank_factor+collateral2-loan0*bank_factor**2,net,'independent terminal accumulation of all cash')
    same_rate=F('1.01');same_release=12*same_rate-8
    a.eq(same_release*same_rate+8*same_rate-12*same_rate**2,0,'matched funding/remuneration zero cost')
    a.interventions.append('matched collateral and borrowing returns')
    a.groups.append('D2 independent default-density integration, recovery delay/zero-rate comparison, swap dated coupons and two-date segregated-principal funding')

    # D3: enumerate every adapted deterministic exercise policy on this tree.
    R=F(21,20);q=F(5,8);S=F(100);u=F(6,5);d=F(4,5);K=F(110)
    a.eq((R-d)/(u-d),q,'stock-implied pricing probability')
    paths=list(product((True,False),repeat=2));path_cash=[]
    for first,second in paths:
        s1=S*(u if first else d);s2=s1*(u if second else d)
        probability=(q if first else 1-q)*(q if second else 1-q)
        path_cash.append((first,probability,max(K-s1,0),max(K-s2,0)))
    a.eq([v for first,payprob,early,v in path_cash],[0,14,14,46],'all terminal path payoffs')
    policies={}
    for stop_up,stop_down in product((False,True),repeat=2):
        value=sum(prob*(early/R if (stop_up if first else stop_down) else late/R**2) for first,prob,early,late in path_cash)
        policies[(stop_up,stop_down)]=value
    american=max(max(K-S,0),max(policies.values()));european=policies[(False,False)]
    a.eq(max(policies,key=policies.get),(False,True),'exhaustively optimal adapted policy')
    a.eq((american,european,american-european),(F(575,42),F(3475,294),F(275,147)),'American/European/premium independent enumeration')
    continuation_up=(q*0+(1-q)*14)/R;continuation_down=(q*14+(1-q)*46)/R
    a.eq((continuation_up,continuation_down),(F(5),F(520,21)),'conditional continuation values')
    delta0,bank0=solve([[120,R],[80,R]],[5,30])
    delta1,bank1=solve([[144,R],[96,R]],[0,14])
    a.eq((delta0,bank0,delta1,bank1),(F(-5,8),F(1600,21),F(-7,24),F(40)),'separate payoff-matching solves')
    a.eq(delta0*100+bank0,american,'root hedge cost')
    a.eq(bank0*R,80,'date-one bank amount')
    purchase=(delta1-delta0)*120
    a.eq((purchase,bank0*R-purchase),(40,bank1),'actual up-node share rebalance cash')
    for s1 in (144,96):a.eq(delta1*s1+bank1*R,max(K-s1,0),'up branch terminal hedge receipt')
    a.eq(bank0*R-(-delta0)*80,30,'down branch share closure and exercise payment')
    hindsight=sum(prob*max(early/R,late/R**2) for first,prob,early,late in path_cash)
    a.true(hindsight>american,'future branch exercise has a different information set')
    a.interventions.append('inadmissible hindsight exercise as a diagnostic')
    # The PDE proof is inspected directly, not certified by a finite sample.
    for literal in ('d[S]=σ²S²dt','Δ(dS+qSdt)','d(H−v)=r(H−v)dt','at most linear growth','kink','predictable'):
        a.true(literal in plain,'explicit continuous proof premise '+literal)
    a.groups.append('D3 exact exhaustive finite stopping, independent hedge systems and actual branch cash; local Ito/PDE assumptions separately reviewed in author record')

    # D4: inconsistent columns, exact full-rank replacement, stable recurrence.
    A=[F('.03'),F(30)];B=[F('.02'),F(20)];C=[F('.025'),F(50)]
    a.eq(A[0]*B[1]-B[0]*A[1],0,'same-maturity Greek matrix singular')
    a.true(A[0]*5000-4*A[1]!=0,'target outside single exposure direction')
    x,y=solve([[A[0],C[0]],[A[1],C[1]]],[4,5000])
    a.eq((x,y),(100,40),'cross-maturity complete exposure solve')
    residual=-70+F('.5')*x+F('.4')*y+10
    a.eq((residual,-residual),(6,-6),'incremental delta trade includes existing shares')
    a.eq(F(100)**2*F('.2')*F('.5'),1000,'shorter gamma-to-vega coefficient')
    a.eq(F(100)**2*F('.2'),2000,'longer gamma-to-vega coefficient')
    a.eq(F(-1000)*F('.01'),-10,'remaining same-maturity vega in point units')
    ratios=[]
    for epsilon in (.1,.01,.001):
        ratios.append(epsilon**2/(math.sqrt(2)*epsilon)**3)
    a.near(ratios[1]/ratios[0],10,'quadratic omitted error is not uniformly cubic')
    a.near(ratios[2]/ratios[1],10,'joint-shock order persists')
    minus,center,plus=F('.20'),F('.65'),F('.10');factor=minus+center+plus
    a.eq(factor,F('.95'),'stencil interior contraction factor')
    bound=F('.04');b0=bound;rho=F('.001');boundary=F('.01')
    errors=[boundary]+[F('.04'),F('-.03'),F('.02'),F('-.04'),F('.01')]+[boundary]
    for step in range(1,21):
        errors=[boundary]+[minus*errors[j-1]+center*errors[j]+plus*errors[j+1]+rho for j in range(1,len(errors)-1)]+[boundary]
        bound=max(boundary,factor*bound+rho)
        closed=rho/(1-factor)+(b0-rho/(1-factor))*factor**step
        a.eq(bound,closed,'exact contraction recurrence step '+str(step))
        a.true(max(map(abs,errors))<=bound,'bounded signed grid error step '+str(step))
    a.near(bound,.027169718448,tolerance=6e-13,label='printed twenty-step bound')
    ak=(minus+plus)/2;bk=(plus-minus)/2;rk=1-factor
    refined=(4*ak-2*bk,1-8*ak-rk,4*ak+2*bk)
    a.eq(refined,(F('.70'),F('-.25'),F('.50')),'hold-time-step spatial refinement')
    a.eq(sum(refined),factor,'weight sum alone is insufficient')
    a.eq(sum(w*x for w,x in zip(refined,(0,1,0))),F('-.25'),'positive input becomes negative')
    a.eq(sum(w*x for w,x in zip(refined,(1,-1,1))),F('1.45'),'refined max norm can amplify')
    a.interventions.append('spatial refinement at fixed time step')
    # Construct independent primitive shocks realizing the stated moments.
    obs=[(7+2*u+math.sqrt(12)*v,10+3*u) for u,v in product((-1,1),repeat=2)]
    means=[sum(row[i] for row in obs)/4 for i in (0,1)]
    var_y=sum((y-means[0])**2 for y,x in obs)/4;var_x=sum((x-means[1])**2 for y,x in obs)/4
    cov=sum((y-means[0])*(x-means[1]) for y,x in obs)/4
    a.near(var_y,16,'independent finite-law Y variance');a.near(var_x,9,'finite-law control variance');a.near(cov,6,'finite-law covariance')
    beta=cov/var_x;controlled=[y-beta*(x-10) for y,x in obs];mean_z=sum(controlled)/4
    var_z=sum((z-mean_z)**2 for z in controlled)/4
    a.near(beta,F(2,3),'control optimizer');a.near(mean_z,7,'fixed-control unchanged mean');a.near(var_z,12,'realized finite-law controlled variance')
    a.near(math.sqrt(var_z/400),.17320508075688773,'independent path-level standard error')
    a.near(1.96*math.sqrt(var_z/400),.3394819582834999,'approximate normal half-width')
    a.near(math.sqrt(var_y/400),.2,'raw observation comparison')
    a.near(1.96*math.sqrt(var_y/400),.392,'raw interval half-width')
    bad_beta=[y-(x-10)*(x-10) for y,x in obs]
    a.near(sum(bad_beta)/4,7-9,'same-evaluation random coefficient need not preserve mean')
    a.interventions.append('data-dependent control coefficient counterexample')
    a.groups.append('D4 exposure rank and signed trade, joint Taylor order, exact error recurrence/refinement failure, and independent finite-law control moments')

    # D5: solve contact-line envelopes instead of assuming the claimed hedges.
    stock=[F(70),F(100),F(160)];claim=[F(0),F(10),F(10)];D=F('.95');S0=F(95)
    lower=[];upper=[]
    for i,j in combinations(range(3),2):
        slope,intercept=solve([[stock[i],1],[stock[j],1]],[claim[i],claim[j]])
        payouts=[slope*s+intercept for s in stock];cost=slope*S0+intercept*D
        if all(x<=y for x,y in zip(payouts,claim)):lower.append(cost)
        if all(x>=y for x,y in zip(payouts,claim)):upper.append(cost)
    a.eq((max(lower),min(upper)),(F(19,6),F(19,2)),'independent two-contact hedge envelopes')
    for parameter in (F(1,10),F(1,3),F(9,19),F(1,2),F(3,5)):
        weights=[parameter,1-F(3,2)*parameter,parameter/2]
        a.true(all(p>0 for p in weights),'strictly positive calibration')
        a.eq(sum(weights),1,'probability normalization')
        a.eq(D*sum(p*s for p,s in zip(weights,stock)),S0,'same traded stock value')
        value=D*sum(p*g for p,g in zip(weights,claim))
        a.eq(value,F(19,2)*(1-parameter),'capped value along positive family')
        a.true(F(19,6)<value<F(19,2),'strict claim interval')
    a.eq(D*sum(stock)/3,F('104.5'),'equal physical weights do not fit traded stock')
    sub=[(s-70)/9 for s in stock];superpay=[F(10)]*3
    a.eq(sub,[0,F(10,3),10],'explicit subhedge payouts')
    a.eq([g-v for g,v in zip(claim,sub)],[0,F(20,3),0],'lower quote endpoint residual')
    a.eq([v-g for g,v in zip(claim,superpay)],[10,0,0],'upper quote endpoint residual')
    a.eq(S0/9-F(70,9)*D,F(19,6),'subhedge funded cost')
    a.eq(10*D,F(19,2),'superhedge funded cost')
    a.eq((F(160)**2-F(100)**2)/100,156,'finite nonlinear jump')
    a.eq(F(2)*(160-100),120,'prejump delta gain')
    a.eq(F(120)-156,-36,'hedge-minus-mark jump error')
    candidate=F('5.006');benchmark=F(5);tolerance=F('.010')
    a.true(abs(candidate-benchmark)<=tolerance,'conditional implementation passes')
    unit_sup=F(19,2)-benchmark
    a.eq(unit_sup*20,90,'upward liability valuation supremum')
    limit=F(60);size=int(limit/unit_sup)
    a.eq((size,size*unit_sup,(size+1)*unit_sup),(13,F('58.5'),63),'maximum whole-unit controlled use')
    a.true(20<=30 and 20*unit_sup>limit,'size exception leaves uncertainty failure')
    for quantity,want in ((13,True),(14,False),(20,False)):
        a.eq(quantity*unit_sup<=limit,want,'quantity uncertainty gate '+str(quantity))
        a.interventions.append('short quantity '+str(quantity))
    a.groups.append('D5 exact contact envelopes, positive calibrated families, endpoint arbitrages, finite jump residual and separate conditional-error/model-risk gates')

    # Bind the numerical audit to the printed answers, not just a side calculation.
    for token in ('0.931','0.88','99.455','4655/88','1.3965','1.386078423','491/9009','97/3003',
                  '87.311152715','87.092354973','0.218797742','0.113079563','5/93','+0.70','−1.036',
                  '575/42','3475/294','275/147','1600/21','−7/24','sell 6 shares','0.027169718448',
                  '(0.70,−0.25,0.50)','0.173205081','0.339481958','19/6','19/2','20/3','−36','58.5'):
        a.true(token in plain,'printed answer binding '+token)
    for exponent,printed in ((-.015,.9851119396),(-.08,.9231163464),(-.12,.8869204367),(-.20,.8187307531)):
        a.near(math.exp(exponent),printed,'supplied calculator constant',tolerance=5.1e-11)
    bound=0
    require(AUTHOR.exists(),'frozen author record must exist')
    if AUTHOR.exists():
        record=json.loads(AUTHOR.read_text())
        a.eq({x['path'] for x in record['reviewed_hashes']},set(OWNED)-{'content/reviews/v10-exam-a-author.json'},'author exact three nonself bindings')
        a.eq(len(record['reviewed_hashes']),3,'no duplicate author bindings')
        for row in record['reviewed_hashes']:
            body=(ROOT/row['path']).read_bytes();a.eq((len(body),sha256(body).hexdigest()),(row['bytes'],row['sha256']),'frozen author payload '+row['path']);bound+=1
    return {'component':'v10-exam-a','status':'passed','comparisons':a.comparisons,
            'scored_subparts':19,'points':100,'domain_points':{f'D{i}':20 for i in range(1,6)},
            'financial_interventions':len(a.interventions),'interventions':a.interventions,
            'author_nonself_hashes_verified':bound,'groups':a.groups,
            'count_definition':'Each executed comparison is counted once; named financial interventions have a separate count. Full proof/solution/source inspection is recorded independently in the author audit.',
            'limits':'Machine-assisted author verification, not a substitute for separate peer/coordinator review, empirical validation, tested timing or external certification. Numerical checks do not prove stochastic-calculus hypotheses, PDE uniqueness or sampling coverage.'}


if __name__=='__main__':
    print(json.dumps(check(),indent=2,allow_nan=False))
