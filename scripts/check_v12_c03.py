"""Readonly, bounded evidence for the original graduate IV/GMM chapter.

Finite state sums, projection algebra and candidate-set inequalities independently
reconstruct the manuscript. They do not substitute for its probability proofs or
empirical exclusion evidence. Quiet check() needs only the four canonical files.
"""
from fractions import Fraction as F
from html.parser import HTMLParser
from itertools import product
import hashlib
import json
from math import exp, isclose, isqrt, sqrt
from pathlib import Path
from statistics import NormalDist

HTML = 'content/chapters/v12-c03.html'
SELF = 'scripts/check_v12_c03.py'
SOURCES = 'content/reviews/v12-c03-sources.json'
REVIEW = 'content/reviews/v12-c03-author.json'


def require(ok, label):
    if not ok:
        raise ValueError('v12-c03: ' + label)


def rational(x):
    require(type(x) in (int, F), 'finite exact rational, not bool or float')
    return F(x)


def matrix(a):
    require(isinstance(a, (list, tuple)) and len(a) > 0, 'nonempty matrix')
    require(all(isinstance(r, (list, tuple)) for r in a), 'matrix rows')
    width = len(a[0])
    require(width > 0 and all(len(r) == width for r in a), 'rectangular matrix')
    return tuple(tuple(rational(x) for x in r) for r in a)


def tr(a):
    return tuple(zip(*a))


def mm(a, b):
    require(len(a[0]) == len(b), 'conformable product')
    return tuple(tuple(sum(x*y for x, y in zip(r, c)) for c in tr(b)) for r in a)


def add(a, b, sign=1):
    require(len(a) == len(b) and len(a[0]) == len(b[0]), 'conformable sum')
    return tuple(tuple(x+sign*y for x, y in zip(r, s)) for r, s in zip(a, b))


def scale(a, c):
    return tuple(tuple(c*x for x in r) for r in a)


def eye(n):
    return tuple(tuple(F(i == j) for j in range(n)) for i in range(n))


def col(v):
    return matrix([[x] for x in v])


def solve(a, b):
    a, b = matrix(a), matrix(b)
    n = len(a)
    require(len(a[0]) == n and len(b) == n, 'square solve dimensions')
    aug = [list(a[i])+list(b[i]) for i in range(n)]
    for j in range(n):
        pivot = next((i for i in range(j, n) if aug[i][j]), None)
        require(pivot is not None, 'singular matrix')
        aug[j], aug[pivot] = aug[pivot], aug[j]
        v = aug[j][j]
        aug[j] = [x/v for x in aug[j]]
        for i in range(n):
            if i != j:
                v = aug[i][j]
                aug[i] = [x-v*y for x, y in zip(aug[i], aug[j])]
    return tuple(tuple(r[n:]) for r in aug)


def inverse(a):
    return solve(a, eye(len(a)))


def positive(a):
    a = matrix(a)
    require(len(a) == len(a[0]) and a == tr(a), 'symmetric square weight/covariance')
    b = [list(r) for r in a]
    for j in range(len(b)):
        require(b[j][j] > 0, 'positive definite weight/covariance')
        for i in range(j+1, len(b)):
            for k in range(j+1, len(b)):
                b[i][k] -= b[i][j]*b[j][k]/b[j][j]
    return a


def gmm(b, a, w):
    b, a, w = matrix(b), matrix(a), positive(w)
    require(len(b) == len(a) == len(w) and len(a[0]) == 1, 'moment dimensions')
    k = solve(mm(mm(tr(b), w), b), mm(tr(b), w))
    return mm(k, a), k


def quadratic(v, w):
    return mm(mm(tr(v), w), v)[0][0]


def projection(z):
    z = matrix(z)
    gram = positive(mm(tr(z), z))
    return mm(mm(z, inverse(gram)), tr(z))


def average_moments(rows):
    n = len(rows)
    z = matrix([r[0] for r in rows]);x = col([r[1] for r in rows]);y = col([r[2] for r in rows])
    return scale(mm(tr(z), x), F(1, n)), scale(mm(tr(z), y), F(1, n)), scale(mm(tr(z), z), F(1, n))


def meat(rows, beta):
    z = matrix([r[0] for r in rows])
    scores = tuple(tuple(v*(y-x*beta) for v in zi) for zi, x, y in rows)
    return scale(mm(tr(scores), scores), F(1, len(z)))


def candidate_set(a, b, c, variance, cutoff):
    a, b, c, variance, cutoff = map(rational, (a, b, c, variance, cutoff))
    require(a >= 0 and c >= 0 and b*b <= a*c, 'projection Gram inequality')
    require(variance > 0 and cutoff >= 0, 'positive known variance and nonnegative cutoff')
    if a == 0:
        return {'kind': 'all' if c <= variance*cutoff else 'empty'}
    center = b/a
    radius2 = (variance*cutoff-c+b*b/a)/a
    if radius2 < 0:
        return {'kind': 'empty'}
    return {'kind': 'singleton' if radius2 == 0 else 'interval', 'center': center, 'radius2': radius2}


def projected_coefficients(z, x, y):
    p = projection(z);x = col(x);y = col(y)
    return quadratic(x, p), mm(mm(tr(x), p), y)[0][0], quadratic(y, p), p


def weak_error(u, v, strength):
    u, v, strength = map(rational, (u, v, strength))
    require(strength+v != 0, 'zero IV denominator')
    return u/(strength+v)


def compliance(table, assignment, direct=F(0)):
    assignment, direct = rational(assignment), rational(direct)
    require(0 < assignment < 1, 'assignment positivity')
    table = [tuple(rational(v) for v in row) for row in table]
    require(all(len(row) == 5 and row[0] >= 0 and row[1] in (0, 1) and row[2] in (0, 1) for row in table), 'compliance domain')
    require(sum(row[0] for row in table) == 1, 'type probability total')
    means_d = [];means_y = [];law = {};treated = F(0);effect_treated = F(0)
    for z, pz in [(0, 1-assignment), (1, assignment)]:
        dbar = F(0);ybar = F(0)
        for p, d0, d1, y0, y1 in table:
            d = d1 if z else d0;y = y1 if d else y0
            y += direct*z
            dbar += p*d;ybar += p*y
            key = (z, d, y);law[key] = law.get(key, F(0))+pz*p
            treated += pz*p*d;effect_treated += pz*p*d*(y1-y0)
        means_d.append(dbar);means_y.append(ybar)
    require(means_d[1] != means_d[0], 'zero compliance first stage')
    require(treated > 0, 'treated mean defined')
    return dict(d=means_d, y=means_y, wald=(means_y[1]-means_y[0])/(means_d[1]-means_d[0]),
                ate=sum(p*(y1-y0) for p, d0, d1, y0, y1 in table), treated=treated,
                att=effect_treated/treated, law=law)


class Audit:
    def __init__(self):
        self.comparisons = 0;self.rejections = 0;self.interventions = []
    def eq(self, actual, expected, label):
        self.comparisons += 1
        require(actual == expected, label+': '+repr(actual)+' != '+repr(expected))
    def near(self, actual, expected, tolerance, label):
        self.comparisons += 1
        require(isclose(float(actual), float(expected), rel_tol=0, abs_tol=tolerance), label)
    def reject(self, fn, label):
        try:
            fn()
        except ValueError:
            self.rejections += 1
        else:
            raise ValueError('Missing domain rejection: '+label)


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack=[];self.ids=[];self.links=[];self.sources=[];self.h1=0;self.worked=0
        self.exercise_depth=0;self.answer_depth=0;self.exercises=[];self.targets=[]
        self.answers={};self.active=None;self.anchors={};self.anchor=None
        self.tables={};self.table=None;self.caption=None;self.row=None;self.cell=None
    def handle_starttag(self, tag, attrs):
        d=dict(attrs);classes=d.get('class','').split()
        if 'id' in d:self.ids.append(d['id'])
        if tag=='h1':self.h1+=1
        if tag=='a':self.links.append(d.get('href',''))
        if 'data-source' in d:self.sources.append(d['data-source'])
        if 'worked' in classes:self.worked+=1
        if tag=='ol' and 'exercises' in classes:self.exercise_depth=len(self.stack)+1
        if tag=='li' and self.exercise_depth==len(self.stack)>0:self.exercises.append(d.get('id'))
        if 'data-solution-for' in d:
            require(self.active is None and tag=='li','separate solution list item')
            self.active=d['data-solution-for'];self.targets.append(self.active)
            self.answers[self.active]='';self.answer_depth=len(self.stack)+1
        if 'data-calc' in d:
            require(tag=='span' and self.anchor is None and d['data-calc'] not in self.anchors,'unique numerical anchor')
            self.anchor=d['data-calc'];self.anchors[self.anchor]=''
        if tag=='table':self.table={'caption':'','rows':[]}
        if tag=='caption':self.caption=''
        if tag=='tr':self.row=[]
        if tag in ('td','th'):self.cell=''
        if tag not in ('br','hr','img','input','meta','link'):self.stack.append(tag)
    def handle_data(self, value):
        require(bool(self.stack) or not value.strip(), 'text outside the chapter fragment sections')
        if self.active is not None:self.answers[self.active]+=value
        if self.anchor is not None:self.anchors[self.anchor]+=value
        if self.caption is not None:self.caption+=value
        if self.cell is not None:self.cell+=value
    def handle_endtag(self, tag):
        require(self.stack and self.stack[-1]==tag,'balanced HTML '+tag)
        if len(self.stack)==self.answer_depth:self.active=None;self.answer_depth=0
        if tag=='ol' and len(self.stack)==self.exercise_depth:self.exercise_depth=0
        self.stack.pop()
        if tag=='span':self.anchor=None
        if tag=='caption':self.table['caption']=self.caption.strip();self.caption=None
        if tag in ('td','th'):self.row.append(self.cell.strip());self.cell=None
        if tag=='tr':self.table['rows'].append(self.row);self.row=None
        if tag=='table':self.tables[self.table['caption']]=self.table['rows'];self.table=None


def strict(raw):
    def pairs(rows):
        out={}
        for k,v in rows:
            require(k not in out,'duplicate JSON key');out[k]=v
        return out
    def bad(value):
        raise ValueError('nonfinite JSON '+value)
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=bad)


def calculations(a, page):
    values={};decimals={}
    rows=[]
    for z,v,w in product((-1,1), repeat=3):
        x=F(z+v);y=2*x+v+w
        rows.append(([F(z)],x,y))
    b, outcome, s=average_moments(rows)
    beta,k=gmm(b,outcome,inverse(s))
    ols=sum(x*y for z,x,y in rows)/sum(x*x for z,x,y in rows)
    omega=meat(rows,F(2))
    z=matrix([r[0] for r in rows]);x=col([r[1] for r in rows]);y=col([r[2] for r in rows])
    p=projection(z);xhat=mm(p,x)
    stage2=solve(mm(tr(xhat),xhat),mm(tr(xhat),y))
    bad_residual=add(y,scale(xhat,F(2)),sign=-1)
    wrong=sum(z[i][0]**2*bad_residual[i][0]**2 for i in range(8))/8
    a.eq(b,col([1]),'original first stage')
    a.eq(outcome,col([2]),'original reduced form')
    a.eq(beta,stage2,'actual projected least squares coefficient')
    a.eq(mm(p,p),p,'instrument projection idempotence')
    a.eq(mm(tr(z),add(x,xhat,sign=-1)),col([0]),'first-stage projection orthogonality')
    a.eq((ols,beta[0][0],omega[0][0],wrong),(F(5,2),F(2),F(2),F(10)),'finite original law')
    values.update({'case1-iv':beta[0][0],'case1-ols':ols,'case1-meat':omega[0][0],'case1-wrong-meat':wrong})
    invalid=[(zi,xi,yi+F(2,5)*zi[0]) for zi,xi,yi in rows]
    ib,ia,iz=average_moments(invalid);iv,_=gmm(ib,ia,inverse(iz))
    a.eq(ib,b,'direct effect preserves relevance');a.eq(iv[0][0]-2,F(2,5),'exclusion shift reaches ratio')
    values['case1-invalid-iv']=iv[0][0]
    a.interventions.append('A direct outcome channel changes IV without changing the first stage.')
    changed=[];invalid_t=[]
    for z,v,w in product((-1,1),repeat=3):
        x=F(2*z+v);y=2*x+v+w
        changed.append(([F(z)],x,y));invalid_t.append(([F(z+v)],x,y))
    xb,xa,xs=average_moments(changed);tb,ta,ts=average_moments(invalid_t)
    xv,_=gmm(xb,xa,inverse(xs));tv,_=gmm(tb,ta,inverse(ts))
    values['ex1-ols']=sum(x*y for z,x,y in changed)/sum(x*x for z,x,y in changed)
    values['ex1-invalid']=tv[0][0]
    a.eq((xb[0][0],xv[0][0],tb[0][0],values['ex1-ols'],tv[0][0]),(F(2),F(2),F(3),F(11,5),F(7,3)),'altered relevance and invalid instrument')
    a.interventions.append('A more predictive instrument containing the latent disturbance remains invalid.')

    sample=[];table=[]
    for j,sign,shock in product((1,2),(-1,1),(-1,1)):
        zi=[F(0),F(0)];zi[j-1]=F(sign)
        xi=F(sign);yi=sign*(F(2*j+1,2)+j*shock)
        table.append([str(j),str(sign),str(shock),str(xi),str(yi)])
        sample.extend([(zi,xi,yi)]*5)
    printed=[[v.replace('−','-') for v in row] for row in page.tables['Eight row types, each with frequency five'][1:]]
    a.eq(printed,table,'every printed sample row')
    b,outcome,s=average_moments(sample);prelim,_=gmm(b,outcome,inverse(s))
    a.eq((b,outcome,s),(col([F(1,2),F(1,2)]),col([F(3,4),F(5,4)]),scale(eye(2),F(1,2))),'sample moments')
    a.eq(prelim,col([2]),'sample 2SLS')
    omega_hat=meat(sample,prelim[0][0]);a.eq(omega_hat,matrix([[F(5,8),0],[0,F(17,8)]]),'preliminary structural meat')
    beta,k=gmm(b,outcome,inverse(omega_hat));residual=add(outcome,mm(b,beta),sign=-1)
    j=len(sample)*quadratic(residual,inverse(omega_hat))
    plug=mm(mm(k,omega_hat),tr(k))[0][0]
    a.eq((beta[0][0],residual,j,plug),(F(19,11),col([F(-5,44),F(17,44)]),F(40,11),F(85,44)),'two-step exact contracts')
    a.eq(plug,inverse(mm(mm(tr(b),inverse(omega_hat)),b))[0][0],'sandwich versus inverse efficient curvature')
    values.update({'case2-feasible-beta':beta[0][0],'case2-g1':residual[0][0],'case2-g2':residual[1][0],
                   'case2-feasible-j':j,'case2-plugin-v':plug})
    decimals['case2-se']=sqrt(float(plug/len(sample)))
    fresh=meat(sample,beta[0][0]);a.eq(fresh,matrix([[F(509,968),0],[0,F(2225,968)]]),'post-step meat separately reconstructed')
    a.eq(fresh!=omega_hat,True,'finite recomputation is a distinct procedure')
    a.interventions.append('Recompute structural residual meat at the finite two-step estimate; it differs from the stipulated preliminary meat.')
    true_omega=matrix([[0,0],[0,0]])
    for group,sign in product((0,1),(-1,1)):
        zi=col([F(sign) if j==group else F(0) for j in range(2)])
        true_omega=add(true_omega,scale(mm(zi,tr(zi)),F((group+1)**2,4)))
    a.eq(true_omega,matrix([[F(1,2),0],[0,2]]),'separate null-population covariance')
    _,k2=gmm(b,outcome,inverse(s));oracle,ko=gmm(b,outcome,inverse(true_omega))
    v2=mm(mm(k2,true_omega),tr(k2))[0][0];ve=mm(mm(ko,true_omega),tr(ko))[0][0]
    oracle_j=len(sample)*quadratic(add(outcome,mm(b,oracle),sign=-1),inverse(true_omega))
    a.eq((v2,ve,v2-ve,oracle[0][0],oracle_j),(F(5,2),F(8,5),F(9,10),F(17,10),F(4)),'population efficiency and oracle sample')
    values.update({'case2-pop-2sls-v':v2,'case2-pop-efficient-v':ve,'case2-efficiency-gap':v2-ve,'case2-oracle-beta':oracle[0][0],'case2-oracle-j':oracle_j})
    critical=NormalDist().inv_cdf(.975)**2
    a.near(critical,3.841459,5e-7,'supplied chi-square1 cutoff rounding')
    a.eq(float(j)<critical<float(oracle_j),True,'finite decisions differ around specified asymptotic cutoff')
    a.interventions.append('Known population versus feasible preliminary weighting changes a finite J decision, without changing the asymptotic theorem.')
    transform=matrix([[2,1],[0,3]])
    bt=mm(transform,b);at=mm(transform,outcome)
    wt=mm(mm(tr(inverse(transform)),inverse(omega_hat)),inverse(transform))
    transformed,_=gmm(bt,at,wt);naive,_=gmm(bt,at,eye(2))
    a.eq(transformed,beta,'proper moment-unit transformation preserves estimate')
    a.eq(naive!=beta,True,'unchanged identity weight changes transformed criterion')
    a.interventions.append('Change instrument units and mix instruments: transformed inverse weight preserves the result while a naive fixed weight does not.')

    deficient=matrix([[1,2],[2,4],[-1,-2]]);target=col([3,6,-3])
    for t in (F(-1),F(0),F(3,2)):
        a.eq(mm(deficient,col([3-2*t,t])),target,'original entire affine identified-set formula')
    full=matrix(list(deficient)+[(0,1)]);full_target=col([3,6,-3,1])
    restored,_=gmm(full,full_target,eye(4));a.eq(restored,col([1,1]),'new independent moment restores target')
    values['ex3-beta1']=restored[0][0]
    a.interventions.append('Add one genuinely independent valid moment to a rank-deficient system; redundant row count alone fails.')
    b6=col([1,2]);o6=matrix([[2,1],[1,3]]);a6=col([3,7])
    _,ki=gmm(b6,a6,eye(2));_,ks=gmm(b6,a6,inverse(o6));_,kd=gmm(b6,a6,matrix([[F(1,2),0],[0,F(1,3)]]))
    vi=quadratic(tr(ki),o6);vs=quadratic(tr(ks),o6);vd=quadratic(tr(kd),o6)
    a.eq((ki,ks,vi,vs,vi-vs,vd),(matrix([[F(1,5),F(2,5)]]),matrix([[F(1,7),F(3,7)]]),F(18,25),F(5,7),F(1,175),F(90,121)),'correlated-score weights')
    d=add(ki,ks,sign=-1)
    a.eq(quadratic(tr(d),o6),vi-vs,'independent scalar covariance-difference certificate')
    a.eq(vd>vi>vs,True,'discarding covariance can worsen variance')
    values.update({'ex6-identity-v':vi,'ex6-efficient-v':vs,'ex6-gap':vi-vs,'ex6-diagonal-v':vd})
    a.interventions.append('Retain versus discard off-diagonal score covariance; inverse marginal variances are not efficient weights.')
    bm=matrix([[1,0],[0,1],[1,1]]);om=matrix([[2,1,0],[1,3,1],[0,1,2]]);am=col([2,3,6])
    _,kw=gmm(bm,am,eye(3));_,ke=gmm(bm,am,inverse(positive(om)));dm=add(kw,ke,sign=-1)
    a.eq(mm(dm,bm),matrix([[0,0],[0,0]]),'two-coefficient difference annihilates derivative span')
    a.eq(mm(mm(ke,om),tr(dm)),matrix([[0,0],[0,0]]),'efficiency cross covariance vanishes')
    diff=add(mm(mm(kw,om),tr(kw)),mm(mm(ke,om),tr(ke)),sign=-1)
    a.eq(diff,mm(mm(dm,om),tr(dm)),'full matrix covariance-difference identity')
    for c in ([1,0],[0,1],[1,-2]):a.eq(quadratic(col(c),diff)>=0,True,'purposeful contrast variance cannot improve on efficient weighting')
    a.interventions.append('A two-coefficient three-moment correlated system checks the matrix, not only scalar, efficiency identity.')
    one=col([1,1,1]);r=add(eye(3),scale(mm(one,tr(one)),F(1,3)),sign=-1)
    a.eq(mm(r,r),r,'J residual projection idempotence');a.eq(tr(r),r,'J residual projection symmetry')
    a.eq(mm(r,one),col([0,0,0]),'J removes one fitted direction')
    a.eq(sum(r[i][i] for i in range(3)),2,'J residual degrees of freedom')
    v=col([1,-1,2]);rv=mm(r,v)
    a.eq(rv,col([F(1,3),F(-5,3),F(4,3)]),'normalized moment residual')
    values['ex7-j']=quadratic(rv,eye(3));a.eq(values['ex7-j'],F(14,3),'J norm')
    shifted=mm(one,col([F(5,2)]));wrong_beta,_=gmm(one,shifted,eye(3))
    a.eq(wrong_beta,col([F(5,2)]),'aligned invalidity fits pseudo-target')
    a.eq(add(shifted,mm(one,wrong_beta),sign=-1),col([0,0,0]),'aligned invalidity is invisible to residual moments')
    a.interventions.append('Moment violations parallel to the regressor span shift the fitted target without creating a J residual.')

    mean=F(441,100);theta=F(21,10);linear=F(2)+(mean-4)/4
    a.eq(theta*theta,mean,'nonlinear exact interior solution')
    a.eq(theta-linear,-(theta-2)**2/4,'independent nonlinear remainder identity')
    values.update({'case3-v':F(16,16),'case3-estimate':theta,'case3-linearized':linear,
                   'case3-remainder':theta-linear,'case3-plugin-se':F(4)/(2*theta*10)})
    for observed,wanted in [(F(0),F(1)),(F(1),F(1)),(F(9),F(3)),(F(16),F(3))]:
        clipped=max(F(1),min(F(9),observed))
        fitted=F(isqrt(clipped.numerator),isqrt(clipped.denominator))
        a.eq(fitted,wanted,'square-root parameter-boundary response')
        for trial in (F(1),F(2),F(3)):
            a.eq((observed-fitted**2)**2 <= (observed-trial**2)**2,True,'declared boundary minimizes original squared criterion')
    a.eq(4-F(-2)**2,0,'second nonlinear root');a.eq(-2*F(-2),4,'second root remains locally full rank')
    for m in (2,3):
        for normalized in (-1,1):
            th=F(normalized,m);bar_y=F(normalized,m**3)
            a.eq(th**3,bar_y,'real cubic sample root')
            a.eq(m*th,normalized,'n^(1/6) normalization at n=m^6')
    a.interventions.append('Move a nonlinear sample moment to a parameter boundary and enlarge a signed domain; global and local conditions change separately.')
    a.eq(F(1)-F(1,2)**2,F(3,4),'nonsingular endogenous Gaussian covariance')
    values['ex9-error100']=weak_error(F(3,5),F(-1,5),F(isqrt(100),2))
    values['ex9-error400']=weak_error(F(3,5),F(-1,5),F(isqrt(400),2))
    values['ex9-weak-error']=weak_error(F(3,5),F(-1,5),F(1,2))
    a.eq(tuple(values[k] for k in ('ex9-error100','ex9-error400','ex9-weak-error')),(F(1,8),F(3,49),F(2)),'fixed versus drifting first-stage examples')
    a.interventions.append('Scale first-stage relevance with sample size; standardized-score algebra distinguishes shrinking and nonshrinking errors.')

    z4=matrix([[1,0],[-1,0],[0,1],[0,-1]])
    aa,bb,cc,p4=projected_coefficients(z4,[1,-1,1,-1],[2,-2,0,0])
    a.eq((aa,bb,cc),(F(4),F(4),F(8)),'worked projection quadratic')
    a.eq(mm(p4,p4),p4,'worked known-variance test projection')
    accepted=candidate_set(aa,bb,cc,1,8)
    a.eq(accepted,{'kind':'interval','center':F(1),'radius2':F(1)},'full original confidence set')
    values.update({'case4-left':accepted['center']-1,'case4-right':accepted['center']+1})
    for bval,inside in [(F(-1,10),False),(F(0),True),(F(1),True),(F(2),True),(F(21,10),False)]:
        a.eq(aa*bval*bval-2*bb*bval+cc<=8,inside,'original endpoints and external points')
    a.eq(candidate_set(aa,bb,cc,1,4)['kind'],'singleton','critical equality')
    a.eq(candidate_set(aa,bb,cc,1,3)['kind'],'empty','below irreducible mismatch')
    for yy,name,wanted in [([1,-1,0,0],'case4-constant-small','all'),([3,-3,0,0],'case4-constant-large','empty')]:
        aq,bq,cq,_=projected_coefficients(z4,[1,1,-1,-1],yy)
        a.eq((aq,bq),(F(0),F(0)),'zero instrument projection of regressor')
        values[name]=cq;a.eq(candidate_set(aq,bq,cq,1,8)['kind'],wanted,'zero relevance set classification')
    a.near(1-exp(-4),.981684,5e-7,'supplied chi-square2 confidence coefficient rounding')
    z10=matrix([[1,0],[0,1],[0,0]])
    ax,bx,cx,_=projected_coefficients(z10,[1,1,1],[2,4,0])
    a.eq((ax,bx,cx),(F(2),F(6),F(20)),'transfer candidate quadratic')
    cset=candidate_set(ax,bx,cx,1,8)
    a.eq(cset,{'kind':'interval','center':F(3),'radius2':F(3)},'transfer full acceptance set')
    decimals['ex10-left']=float(cset['center'])-sqrt(float(cset['radius2']))
    decimals['ex10-right']=float(cset['center'])+sqrt(float(cset['radius2']))
    a.eq(candidate_set(ax,bx,cx,1,2)['kind'],'singleton','transfer equality')
    a.eq(candidate_set(ax,bx,cx,1,1)['kind'],'empty','transfer empty')
    for yy,kind in [([2,4,0],'empty'),([1,1,0],'all')]:
        ax,bx,cx,_=projected_coefficients(z10,[0,0,1],yy)
        a.eq(candidate_set(ax,bx,cx,1,8)['kind'],kind,'transfer constant test')
    a.interventions.append('Reduce a critical value through the quadratic minimum, and remove projected relevance: interval, singleton, empty and all-real sets are explicitly distinguished.')

    types=[(F(1,4),0,0,2,10),(F(1,4),1,1,1,3),(F(1,2),0,1,4,8)]
    base=compliance(types,F(1,2))
    a.eq((base['d'],base['y'],base['wald'],base['ate'],base['att']),([F(1,4),F(3,4)],[F(13,4),F(21,4)],F(4),F(9,2),F(3)),'full compliance law')
    a.eq(sum(base['law'].values()),1,'observable joint law total')
    values.update({'case5-y0':base['y'][0],'case5-y1':base['y'][1],'case5-late':base['wald'],'case5-ate':base['ate'],'case5-att':base['att']})
    expected=[]
    for label,row in zip(('Never treated','Always treated','Complier'),types):
        prob,d0,d1,y0,y1=row;expected.append([label,str(prob),str(d0),str(d1),str(y0),str(y1),str(y1-y0)])
    a.eq(page.tables['Original compliance population'][1:],expected,'every printed compliance cell')
    defiers=[(F(1,8),0,0,2,10),types[1],types[2],(F(1,8),1,0,0,12)]
    altered=compliance(defiers,F(1,2));direct=compliance(types,F(1,2),F(1,2))
    a.eq((altered['d'][1]-altered['d'][0],altered['y'][1]-altered['y'][0]),(F(3,8),F(1,2)),'defier signed decomposition')
    a.eq(altered['wald']<min(row[4]-row[3] for row in defiers),True,'negative weighting leaves effect range')
    a.eq(direct['d'],base['d'],'direct channel preserves compliance relevance')
    a.eq(direct['ate'],base['ate'],'treatment effect holding encouragement fixed is unchanged')
    values['case5-defier-wald']=altered['wald'];values['case5-direct-wald']=direct['wald']
    a.interventions.append('Introduce defiers and, separately, a direct encouragement effect; the Wald numerator changes through different causal assumptions.')
    rare=compliance(types,F(1,4));counterfactual=[(F(1,4),0,0,2,6),types[1],types[2]]
    alt=compliance(counterfactual,F(1,4))
    a.eq(rare['law'],alt['law'],'entire observed law unchanged by missing never-treated counterfactual')
    a.eq((rare['wald'],rare['treated'],rare['att'],alt['ate']),(F(4),F(3,8),F(8,3),F(7,2)),'assignment mixture and ATE identification')
    values.update({'ex11-treated':rare['treated'],'ex11-att':rare['att'],'ex11-alternative-ate':alt['ate']})
    a.interventions.append('Change encouragement frequency, then an unobserved never-treated potential outcome: ATT mixture and ATE identification differ from LATE.')
    rb=col([1,1]);ra=col([1,3]);ro=matrix([[1,0],[0,9]])
    retained,rk=gmm(rb,ra,inverse(ro));rg=add(ra,mm(rb,retained),sign=-1)
    rv=quadratic(tr(rk),ro);rj=10*quadratic(rg,inverse(ro))
    values.update({'retention-beta':retained[0][0],'retention-v':rv,'retention-j':rj})
    a.eq((retained[0][0],rv,rj),(F(6,5),F(9,10),F(4)),'new retention quantities')
    a.eq(candidate_set(0,0,3,1,2)['kind'],'empty','retention constant test')

    a.reject(lambda:gmm(deficient,target,eye(3)),'unidentified linear coefficient')
    a.reject(lambda:projection([[1,2],[2,4]]),'dependent instrument columns')
    a.reject(lambda:gmm([[1]],[[2]],[[0]]),'zero moment weight')
    a.reject(lambda:positive([[1,2],[2,1]]),'indefinite covariance')
    a.reject(lambda:positive([[1,1],[0,1]]),'asymmetric covariance')
    a.reject(lambda:matrix([[1],[True]]),'boolean numeric value')
    a.reject(lambda:matrix([[1],[float('nan')]]),'nonfinite numeric value')
    a.reject(lambda:matrix([[1],[2,3]]),'ragged dimensions')
    a.reject(lambda:weak_error(F(3,5),F(-1,5),F(1,5)),'zero first-stage sample denominator')
    a.reject(lambda:candidate_set(1,0,1,0,8),'zero known error variance')
    a.reject(lambda:candidate_set(1,0,1,1,-1),'negative cutoff')
    a.reject(lambda:candidate_set(0,1,1,1,8),'impossible zero-curvature cross term')
    a.reject(lambda:candidate_set(1,2,1,1,8),'impossible projection Gram')
    a.reject(lambda:compliance(types,F(0)),'absent encouragement support')
    a.reject(lambda:compliance(types+[(F(1,8),0,0,1,2)],F(1,2)),'probabilities exceed one')
    a.reject(lambda:compliance([(F(3,4),0,0,2,10),(F(1,4),1,1,1,3)],F(1,2)),'zero complier first stage')
    for key,value in values.items():
        a.eq(F(page.anchors[key].strip().replace('−','-')),value,'printed exact anchor '+key)
    for key,value in decimals.items():
        a.near(float(page.anchors[key]),value,5e-10,'printed rounded anchor '+key)
    a.eq(set(page.anchors),set(values)|set(decimals),'all numeric anchors reconstructed')
    return len(values),len(decimals)


def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    audit=Audit();page=Page();raw=(root/HTML).read_text();page.feed(raw);page.close()
    prompts=['v12-c03-e'+str(i).zfill(2) for i in range(1,13)]
    audit.eq(page.exercises,prompts,'twelve exact exercise markers')
    audit.eq(page.targets,prompts,'all exact solutions and order')
    audit.eq((page.worked,page.h1,page.stack,page.active),(5,0,[],None),'complete original chapter fragment')
    audit.eq(len(page.ids),len(set(page.ids)),'unique IDs')
    audit.eq(all(x.startswith('v12-c03-') for x in page.ids),True,'owned IDs')
    for key in prompts:audit.eq(len(page.answers[key])>180,True,'substantive answer '+key)
    audit.eq(raw.count('<details class="solutions"'),1,'standard reader disclosure marker')
    audit.eq('Teach-back benchmark' in raw and 'Retention solution and repair route' in raw,True,'answered teaching and retention')
    exact,rounded=calculations(audit,page)
    sources=strict((root/SOURCES).read_text());review=strict((root/REVIEW).read_text())
    expected={'v12-c03-mit-iv2017','v12-c03-mit-gmm2017','v12-c03-mit-nonlinear2017','v12-c03-imbens-angrist1994'}
    audit.eq({s['id'] for s in sources['proposals']},expected,'four inspected primary source proposals')
    audit.eq(len(sources['proposals']),4,'bounded source count')
    audit.eq(set(page.sources),expected,'every proposed source has actual manuscript scope')
    for s in sources['proposals']:
        audit.eq(s['inspection']['date_checked'],'2026-10-09','dated actual inspection')
        audit.eq(bool(s['inspection']['body_scope_read']) and bool(s['inspection']['sha256']),True,'scoped body evidence')
    for link in page.links:
        audit.eq(link in ('v12-c01.html','v12-c02.html') or link in {'sources.html#'+x for x in expected},True,'flat future reader/source route')
    rows=review['reviewed_hashes']
    audit.eq({x['path'] for x in rows},{HTML,SELF,SOURCES},'three nonself author bindings')
    audit.eq(len(rows),3,'no duplicate payload binding')
    for row in rows:
        content=(root/row['path']).read_bytes()
        audit.eq((len(content),hashlib.sha256(content).hexdigest()),(row['bytes'],row['sha256']),'exact author payload '+row['path'])
    summary=dict(chapter='v12-c03',status='passed',working_only=False,worked_cases=5,exercises=12,solutions=12,
                 exact_numeric_anchors=exact,rounded_numeric_anchors=rounded,comparisons=audit.comparisons,
                 purposeful_interventions=len(audit.interventions),intervention_scopes=audit.interventions,
                 executed_domain_rejections=audit.rejections,source_documents=4,nonself_author_bindings=3,
                 limits='Finite original evidence and scoped source/proof reading; no empirical validity, general dependent or uniform-weak theorem, rendered QA, human certification or acceptance implied.')
    strict(json.dumps(summary,allow_nan=False))
    return summary


if __name__=='__main__':
    print(json.dumps(check(),ensure_ascii=False,allow_nan=False,indent=2))
