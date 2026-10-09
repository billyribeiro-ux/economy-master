"""Independent, read-only, exact finite and Decimal Gaussian audit of v12-c06.

The author checker is never imported or called. Runtime uses exactly the four
frozen author payloads and the two peer files. No network or shared code.
"""
from collections import Counter, defaultdict
from decimal import Decimal, localcontext
from fractions import Fraction as F
from html.parser import HTMLParser
from itertools import combinations, product
import hashlib
import json
from math import isfinite, sqrt
from pathlib import Path

AUTHOR = (
    ('content/chapters/v12-c06.html',70286,'e5e0bf5c694c76a1cc3217b624e67be4770d9160719c86eb9041472c74d9fe8d'),
    ('scripts/check_v12_c06.py',43356,'1e785d5e2b5d716d9db3898de7afe5c1ac29e49366db3489029739ea20ac2530'),
    ('content/reviews/v12-c06-sources.json',13255,'198d3ea06a366a1144d98b06cf3529887a2e8e01bb13fac60c52b3a544521f3a'),
    ('content/reviews/v12-c06-author.json',30613,'bf5cac4edb4eabb1ff21b2b097c45473210f8659389f047e21108d6aaca24dbd'),
)
SELF='scripts/check_v12_c06_peer.py'
RECORD='content/reviews/v12-c06-peer.json'


def need(ok,label):
    if not ok:
        raise ValueError('v12-c06 peer: '+label)


def strict(raw):
    def pairs(rows):
        d={}
        for k,v in rows:
            need(k not in d,'duplicate JSON member');d[k]=v
        return d
    def decimal(s):
        x=float(s);need(isfinite(x),'finite JSON decimal');return x
    def bad(s):
        raise ValueError('nonfinite JSON literal '+s)
    return json.loads(raw,object_pairs_hook=pairs,parse_float=decimal,parse_constant=bad)


def exact(x):
    need(type(x) in (int,F),'exact scalar excluding bool and float')
    x=F(x);need(abs(x)<=10**6,'bounded exact scalar');return x


def count(n,lo=1,hi=512):
    need(type(n) is int and lo<=n<=hi,'bounded integer count');return n


def average(xs):
    need(len(xs)>0,'nonempty average');return sum(xs,F(0))/len(xs)


def dispersion(xs,ddof=0):
    need(len(xs)>ddof,'variance sample degrees of freedom')
    m=average(xs);return sum((v-m)**2 for v in xs)/(len(xs)-ddof)


def subsets(n,k):
    count(n,2,10);count(k,1,n-1)
    return [frozenset(s) for s in combinations(range(n),k)]


def contrast(values,treated):
    values=[exact(x) for x in values]
    need(0<len(treated)<len(values) and all(type(i) is int and 0<=i<len(values) for i in treated),'two valid observed arms')
    return average([y for i,y in enumerate(values) if i in treated])-average([y for i,y in enumerate(values) if i not in treated])


def finite(y0,y1,k):
    need(len(y0)==len(y1),'complete potential table')
    y0,y1=[exact(x) for x in y0],[exact(x) for x in y1]
    rows=[]
    for t in subsets(len(y0),k):
        obs=[y1[i] if i in t else y0[i] for i in range(len(y0))]
        arms=[[v for i,v in enumerate(obs) if (i in t)==d] for d in (False,True)]
        # Pair-distance route to each observed arm variance.
        vh=None if min(map(len,arms))<2 else sum(sum((x-y)**2 for x,y in combinations(a,2))/F(len(a)**2*(len(a)-1)) for a in arms)
        rows.append((t,contrast(obs,t),vh))
    return rows


def rank_values(statistics,masses,inclusive=True):
    need(len(statistics)==len(masses)>0,'matching statistic law')
    masses=[exact(x) for x in masses]
    need(min(masses)>0 and sum(masses)==1,'positive normalized assignment masses')
    levels=sorted(set(statistics),reverse=True)
    cumulative=F(0);tail={}
    for level in levels:
        mass=sum(p for s,p in zip(statistics,masses) if s==level)
        tail[level]=cumulative+mass if inclusive else cumulative
        cumulative+=mass
    return [tail[s] for s in statistics]


def subset_histogram(values,labels,k):
    """Coefficients of product(1+t*u**label*v**value), at t**k."""
    need(len(values)==len(labels)<=10,'bounded histogram input')
    states={(0,0,F(0)):1}
    for value,label in zip(values,labels):
        value=exact(value);need(type(label) is int and label in (0,1),'binary histogram label')
        newer=Counter(states)
        for (size,overlap,total),multiplicity in states.items():
            if size<k:newer[size+1,overlap+label,total+value]+=multiplicity
        states=dict(newer)
    return {(overlap,total):m for (size,overlap,total),m in states.items() if size==k}


def fisher(y,treated,candidate=F(0)):
    need(len(y)==6 and len(treated)==3,'bounded three-of-six sharp design')
    candidate=exact(candidate)
    adjusted=[exact(v)-candidate*(i in treated) for i,v in enumerate(y)]
    hist=subset_histogram(adjusted,[0]*6,3)
    observed=abs(3*contrast(adjusted,treated))
    total=sum(adjusted)
    return F(sum(m for (k,s),m in hist.items() if abs(2*s-total)>=observed),sum(hist.values()))


def cdf(x):
    """Integral of the exponential Taylor series, with 50-digit arithmetic.

    |x|<=8. Beyond k=32 the terms decrease; at the declared cutoff the
    alternating remainder is below 1e-43 before conversion to float.
    Cancellation at this boundary uses fewer than 15 decimal places.
    """
    need(type(x) in (int,float) and isfinite(x) and abs(x)<=8,'bounded Gaussian argument')
    with localcontext() as ctx:
        ctx.prec=50
        z=Decimal(str(x));term=z;value=term
        for k in range(300):
            term *= -z*z*Decimal(2*k+1)/(Decimal(2*(k+1))*Decimal(2*k+3))
            value+=term
            if k>32 and abs(term)<Decimal('1e-43'):break
        else:raise ValueError('Gaussian series convergence')
        pi=Decimal('3.1415926535897932384626433832795028841971693993751')
        return float(Decimal('0.5')+value/(2*pi).sqrt())


def critical():
    lo,hi=0.0,3.0
    for i in range(56):
        mid=(lo+hi)/2
        if cdf(mid)<.975:lo=mid
        else:hi=mid
    return (lo+hi)/2


def power(v,effect=1):
    v=exact(v);effect=exact(effect);need(v>0,'positive planning variance')
    z=critical();lam=float(effect)/sqrt(float(v))
    return cdf(lam-z)+cdf(-lam-z)


def allocation(n,v1=9,v0=1):
    count(n,2);v1,v0=exact(v1),exact(v0);need(min(v1,v0)>0,'positive arm variances')
    # Exhaustive finite optimization, independent of the floor/ceiling rule.
    return min((v1/k+v0/(n-k),k,n-k) for k in range(1,n))


def arm_statistics(observed):
    need(observed and sum(observed.values())==1,'observed probability law')
    need(len(observed)<=32 and all(exact(q)>0 and type(z) is int and z in (0,1) and type(d) is int and d in (0,1)
                                  for (z,d,y),q in observed.items()),'bounded positive binary observed law')
    for z,d,y in observed:exact(y)
    p=[sum(q for (z,d,y),q in observed.items() if z==a) for a in (0,1)]
    need(min(p)>0,'nonempty encouragement arms')
    ys=[sum(q*y for (z,d,y),q in observed.items() if z==a) for a in (0,1)]
    ds=[sum(q*d for (z,d,y),q in observed.items() if z==a) for a in (0,1)]
    ym=[ys[a]/p[a] for a in (0,1)];dm=[ds[a]/p[a] for a in (0,1)]
    return p,ys,ds,ym,dm


def ratio(observed):
    p,ys,ds,ym,dm=arm_statistics(observed)
    g=dm[1]-dm[0];need(g!=0,'nonzero observed first stage')
    return (ym[1]-ym[0])/g


def derivative(observed,atom):
    """Differentiate the full rational functional at an observed atom."""
    p,ys,ds,ym,dm=arm_statistics(observed)
    dy=[];dd=[]
    for z in (0,1):
        dp=F(atom[0]==z)-p[z]
        da=(atom[2] if atom[0]==z else F(0))-ys[z]
        db=(atom[1] if atom[0]==z else F(0))-ds[z]
        dy.append((da*p[z]-ys[z]*dp)/p[z]**2)
        dd.append((db*p[z]-ds[z]*dp)/p[z]**2)
    sy,sd=dy[1]-dy[0],dd[1]-dd[0]
    g=dm[1]-dm[0];num=ym[1]-ym[0];need(g!=0,'nonzero derivative denominator')
    return sy,sd,(sy*g-num*sd)/g**2


def compliance(p=F(1,2),direct=F(0)):
    p,direct=exact(p),exact(direct);need(0<p<1,'positive encouragement arms')
    types=[(F(1,2),0,0,1,7),(F(1,8),1,1,2,6),(F(3,8),0,1,3,5)]
    observed=defaultdict(F);treated=F(0);att_numerator=F(0)
    for mass,d0,d1,y0,y1 in types:
        for z,pz in ((0,1-p),(1,p)):
            d=d1 if z else d0;y=(y1 if d else y0)+direct*z
            observed[z,d,F(y)]+=mass*pz
            treated+=mass*pz*d;att_numerator+=mass*pz*d*(y1-y0)
    return dict(observed),treated,att_numerator/treated


def exposures(p=F(1,2),fixed_one=False):
    p=exact(p);need(0<p<1,'positive Bernoulli exposure support')
    law=[]
    for z in product((0,1),repeat=3):
        if fixed_one and sum(z)!=1:continue
        q=F(1,3) if fixed_one else p**sum(z)*(1-p)**(3-sum(z))
        es=[(z[0],z[1]),(z[1],int(z[0] or z[2])),(z[2],z[1])]
        # Six indicator coordinates: unit order, then 00 and 10.
        indicators=[int(e==(d,0)) for e in es for d in (0,1)]
        law.append((z,q,indicators))
    pi=[sum(q*row[j] for z,q,row in law) for j in range(6)]
    need(min(pi)>0,'marginal support for the entire target')
    values=[1,3,2,6,3,9]
    weights=[F((-1 if j%2==0 else 1)*values[j],3)/pi[j] for j in range(6)]
    out=[(z,q,sum(w*d for w,d in zip(weights,row))) for z,q,row in law]
    covariance=[[sum(q*(row[i]-pi[i])*(row[j]-pi[j]) for z,q,row in law) for j in range(6)] for i in range(6)]
    return pi,weights,covariance,out


def endpoint_mapping(remote):
    remote=exact(remote);seen={}
    for z in product((0,1),repeat=3):
        label=(z[0],z[1]);outcome=1+2*z[0]+3*z[1]+remote*z[2]
        need(label not in seen or seen[label]==outcome,'same endpoint exposure must determine one outcome')
        seen[label]=outcome
    return seen


def attrition(coupling,upper):
    coupling=exact(coupling);need(F(3,5)<=coupling<=F(4,5),'admissible joint response coupling')
    need(type(upper) is bool,'endpoint indicator')
    masses=[coupling,F(4,5)-coupling,F(4,5)-coupling,coupling-F(3,5)]
    rows=[]
    for q,(r0,r1) in zip(masses,((1,1),(0,1),(1,0),(0,0))):
        if q:
            rows.append((q,r0,r1,F(6 if r0 else 0 if upper else 10),F(8 if r1 else 10 if upper else 0)))
    return rows


def observed_attrition(rows):
    out=defaultdict(F)
    for q,r0,r1,y0,y1 in rows:
        for z,r,y in ((0,r0,y0),(1,r1,y1)):
            out[z,r,y if r else None]+=q/2
    return dict(out)


def bounds(r,m,lo=0,hi=10):
    r,lo,hi=exact(r),exact(lo),exact(hi)
    need(0<=r<=1 and lo<=hi,'response probability and ordered bounds')
    if r==0:
        need(m is None,'no fabricated mean when response is zero');return lo,hi
    m=exact(m);need(lo<=m<=hi,'observed mean inside support')
    return r*m+(1-r)*lo,r*m+(1-r)*hi


class Reader(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack=[];self.ids=[];self.prompts=[];self.answers={};self.active=None
        self.values={};self.mark=None;self.worked=0;self.sources=[];self.links=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs);need(len(a)==len(attrs),'unique HTML attributes')
        if 'id' in a:self.ids.append(a['id'])
        if tag=='li' and a.get('id','').startswith('v12-c06-e'):self.prompts.append(a['id'])
        if 'data-solution-for' in a:
            need(self.active is None and a['data-solution-for'] not in self.answers,'unique solution')
            self.active=a['data-solution-for'];self.answers[self.active]=''
        if 'data-calc' in a:
            need(self.mark is None and a['data-calc'] not in self.values,'unique visible calculation')
            self.mark=a['data-calc'];self.values[self.mark]=''
        if 'data-source' in a:self.sources.append(a['data-source'])
        if 'href' in a:self.links.append(a['href'])
        self.worked+='worked' in a.get('class','').split()
        if tag not in ('br','hr','img','meta','link','input'):self.stack.append((tag,a))
    def handle_data(self,data):
        if self.mark is not None:self.values[self.mark]+=data
        if self.active is not None:self.answers[self.active]+=data
    def handle_endtag(self,tag):
        need(self.stack and self.stack[-1][0]==tag,'balanced markup')
        t,a=self.stack.pop()
        if 'data-calc' in a:self.mark=None
        if 'data-solution-for' in a:self.active=None


class Audit:
    def __init__(self):self.comparisons=0;self.rejections=[];self.interventions=[]
    def eq(self,x,y,label):
        self.comparisons+=1;need(x==y,label+': '+repr(x)+' != '+repr(y))
    def close(self,x,y,label,tolerance=2e-12):
        self.comparisons+=1;need(isfinite(x) and isfinite(y) and abs(x-y)<=tolerance,label)
    def reject(self,fn,label):
        try:fn()
        except ValueError:self.rejections.append(label)
        else:raise ValueError('missing rejection: '+label)


def calculate(a):
    exact_values={};rounded={}
    y0=list(map(F,range(6)));tau=[F(0),F(2)]*3;y1=[x+t for x,t in zip(y0,tau)]
    law=finite(y0,y1,3);contrasts=[x[1] for x in law];hats=[x[2] for x in law]
    v=dispersion(contrasts);s0,s1,st=[dispersion(x,1) for x in (y0,y1,tau)]
    exact_values.update({'finite-assignments':len(law),'finite-ate':average(contrasts),'finite-s0':s0,'finite-s1':s1,'finite-stau':st,'finite-variance':v,'finite-neyman':average(hats)})
    a.eq((average(contrasts),v,average(hats)),(1,F(44,15),F(47,15)),'all twenty design outcomes and pair-distance variances')
    a.eq(v,s1/3+s0/3-st/6,'finite covariance identity')
    for k in (1,2,3):
        choices=subsets(6,k)
        p=F(k,6)
        for i,j in ((0,0),(0,1),(2,5)):
            joint=average([F(i in t and j in t) for t in choices])
            a.eq(joint,p if i==j else F(k*(k-1),30),'inclusion moments including singleton boundary')
    t,d,vhat=next(row for row in law if row[0]==frozenset((0,2,4)))
    exact_values.update({'finite-realized-estimate':d,'finite-realized-neyman':vhat})
    a.eq(vhat<v,True,'Neyman realization need not dominate')
    C=F(6,20)*(F(49,3)+F(25,3));exact_values['finite-range-bound']=C;rounded['ex2-halfwidth']=sqrt(float(C/F(1,10)))
    coefficients=sorted((a+b)/3 for a,b in zip(y0,y1))
    support=(sum(coefficients[:3])-sum(y0)/3,sum(coefficients[-3:])-sum(y0)/3)
    a.eq((C,min(contrasts),max(contrasts)),(F(37,5),*support),'known-range bound and finite estimate support by order statistics')
    a.eq(sum((d-1)**2>=74 for d in contrasts),0,'actual finite Chebyshev coverage')
    for k in (2,3):
        rows=finite(y0,[x+2 for x in y0],k)
        a.eq(average([r[2] for r in rows]),dispersion([r[1] for r in rows]),'constant effects remove expected excess')
    a.eq({row[1] for row in finite([2]*6,[5]*6,3)},{F(3)},'known zero range')
    a.interventions.append('Singleton inclusion boundary, changed fixed counts and constant effects separate finite covariance and variance-estimation scope.')

    all_t=subsets(6,3)
    for effect in range(5):
        ps=[fisher([v+effect*(i in t) for i,v in enumerate(y0)],t) for t in all_t]
        rejected=sum(p<=F(1,10) for p in ps)
        exact_values['power-t'+str(effect)]=F(rejected,20);exact_values['ex4-count-t'+str(effect)]=rejected
        a.eq(rejected,[2,1,2,4,8][effect],'true-alternative rejection count')
        a.eq(min(ps)>=F(1,10),True,'complement ties rule out five-percent rejection')
    obs=list(map(F,(0,1,2,5,6,7)));treated=frozenset((3,4,5))
    exact_values['fisher-observed-difference']=contrast(obs,treated)
    hist=subset_histogram(obs,[0,0,0,1,1,1],3);roots=set()
    # Histogram gives each statistic 3*T(c) = (2*sum-21)+(3-2*overlap)c.
    # Squared-tail signs can change only at these exact linear-factor roots.
    for (overlap,total),mass in hist.items():
        A=2*total-21;B=3-2*overlap
        for s in (-1,1):
            if B+3*s:roots.add(-(A-15*s)/(B+3*s))
    roots=sorted(roots)
    a.eq(roots,list(map(F,(3,4)))+[F(9,2),F(5),F(11,2)]+list(map(F,(6,7))),'all algebraic tail-comparison breakpoints')
    probes=[roots[0]-1,roots[-1]+1]+roots+[(l+r)/2 for l,r in zip(roots,roots[1:])]
    for c in probes:
        by_polynomial=F(sum(m for (k,s),m in hist.items() if (2*s-21+(3-2*k)*c)**2>=(15-3*c)**2),20)
        a.eq(by_polynomial,fisher(obs,treated,c),'subset polynomial and adjusted-data histogram agree')
        a.eq(by_polynomial>F(1,10),F(3)<=c<=F(7),'whole-real-line root and open-cell certificate')
    exact_values['fisher-endpoint-p']=fisher(obs,treated,3)
    a.eq((fisher(obs,treated,3),fisher(obs,treated,5),fisher(obs,treated,7)),(F(1,5),F(1),F(1,5)),'inversion endpoints and center')
    masses=[F(1,2),F(1,4),F(1,4)];rank=rank_values([2,2,0],masses)
    bad=rank_values([2,2,0],masses,False)
    exact_values.update({'ex3-top-p':rank[0],'ex3-inclusive-size':sum(p for p,v in zip(masses,rank) if v<=F(1,4)),'ex3-strict-size':sum(p for p,v in zip(masses,bad) if v<=F(1,4))})
    a.eq((rank,bad),([F(3,4),F(3,4),F(1)],[F(0),F(0),F(3,4)]),'nonuniform inclusive versus strict tie ranks')
    a.interventions.append('Subset-generating polynomials certify every real Fisher candidate; alternative generation and unequal tied masses check the actual rejection law.')

    # Convolve independent stratum contrast laws, retaining target and pooled weights.
    low=list(map(F,range(4)));high=[x+10 for x in low]
    complete=finite(low+high,[x+2 for x in low+high],4)
    exact_values.update({'strata-complete-count':len(complete),'strata-complete-variance':dispersion([r[1] for r in complete])})
    for kl,kh,prefix in ((2,2,'strata'),(1,3,'ex5')):
        ls=finite(low,[x+2 for x in low],kl);hs=finite(high,[x+2 for x in high],kh)
        weighted=[];pooled=[]
        for l,h in product(ls,hs):
            weighted.append((l[1]+h[1])/2)
            tr=set(l[0])|{i+4 for i in h[0]};base=low+high
            pooled.append(contrast([x+2*(i in tr) for i,x in enumerate(base)],tr))
        if prefix=='strata':
            exact_values.update({'strata-blocked-count':len(weighted),'strata-blocked-variance':dispersion(weighted),'strata-target':average(weighted)})
        else:
            exact_values.update({'ex5-assignments':len(weighted),'ex5-weighted-mean':average(weighted),'ex5-weighted-variance':dispersion(weighted),'ex5-pooled-mean':average(pooled)})
        a.eq((average(weighted),dispersion(weighted)),(2,F(5,6) if kl==2 else F(10,9)),'independent target-weighted stratum convolution')
    a.eq(exact_values['ex5-pooled-mean'],7,'unequal shares select different baseline mixtures')
    a.interventions.append('Changing treatment fractions inside fixed strata preserves the weighted estimand while moving the naive pooled expectation.')

    exact_values.update({'gaussian-fraction':F(3,4),'gaussian-optimal-coefficient':16,'gaussian-balanced-coefficient':20})
    for n in (125,126):
        var,k,j=allocation(n)
        a.eq((k,j),(94,n-94),'full finite allocation optimization')
        exact_values['gaussian-v'+str(n)]=var;rounded['gaussian-p'+str(n)]=power(var)
    rounded['gaussian-p156']=power(F(10,78));rounded['gaussian-p158']=power(F(10,79))
    a.eq(rounded['gaussian-p125']<.8<rounded['gaussian-p126'],True,'optimized minimum boundary')
    a.eq(rounded['gaussian-p156']<.8<rounded['gaussian-p158'],True,'equal allocation minimum boundary')
    a.close(cdf(critical()),.975,'series integral quantile')
    a.close(power(F(191,1504),0),.05,'Gaussian null size')
    a.close(power(F(191,1504),-1),rounded['gaussian-p126'],'effect sign symmetry')
    a.close(power(4*F(191,1504),2),rounded['gaussian-p126'],'outcome unit change')
    a.eq(allocation(126,1,9)[1:],(32,94),'arm permutation')
    J,m=10,10
    common_coeff=[F(1,J)]*J+[-F(1,J)]*J
    error_coeff=[c/m for c in common_coeff for row in range(m)]
    correct=sum(c*c for c in common_coeff)+4*sum(c*c for c in error_coeff)
    wrong=5*sum(c*c for c in error_coeff)
    exact_values.update({'cluster-variance':correct,'cluster-wrong-variance':wrong,'cluster-factor':correct/wrong,'retention-cluster-limit':sum(c*c for c in common_coeff)})
    rounded['ex7-se-factor']=sqrt(float(correct/wrong))
    a.eq((correct,wrong,correct/wrong),(F(7,25),F(1,10),F(14,5)),'independent latent-shock coefficients recover cluster variance')
    a.interventions.append('Decimal exponential integration and quantile bisection verify Gaussian powers; full integer optimization and independent latent-shock coefficients certify allocation and cluster information.')

    observed,treated,att=compliance();p,ys,ds,ym,dm=arm_statistics(observed)
    b=ratio(observed);gamma=dm[1]-dm[0];itt=ym[1]-ym[0]
    influences={atom:derivative(observed,atom) for atom in observed}
    vy,vd,vb=[sum(q*influences[atom][k]**2 for atom,q in observed.items()) for k in range(3)]
    cov=sum(q*influences[atom][0]*influences[atom][1] for atom,q in observed.items())
    for name,value in [('d0',dm[0]),('d1',dm[1]),('y0',ym[0]),('y1',ym[1]),('first-stage',gamma),('itt',itt),('late',b),('ate',F(1,2)*6+F(1,8)*4+F(3,8)*2),('treated',treated),('att',att),('vy',vy),('vd',vd),('cov',cov),('variance',vb)]:exact_values['compliance-'+name]=value
    qlaw=defaultdict(F)
    for (z,d,y),mass in observed.items():qlaw[y-2*d]+=mass
    qm=sum(q*x for x,q in qlaw.items());qv=sum(q*(x-qm)**2 for x,q in qlaw.items())
    exact_values.update({'compliance-qmean':qm,'compliance-qvar':qv,'compliance-wrong-variance':(vy+b*b*vd)/gamma**2})
    a.eq((vy,vd,cov,vb),(F(235,16),F(23,32),F(97,32),F(116,3)),'observed-law directional derivatives retain joint covariance')
    a.eq(vb,4*qv/gamma**2,'independent treatment-residual certificate')
    empirical=Counter()
    for atom,q in observed.items():empirical[atom]+=int(q*16)
    empirical={atom:F(n,16) for atom,n in empirical.items()}
    a.eq(ratio(empirical),2,'actual sixteen-row sample ratio')
    a.eq(sum(q*derivative(empirical,atom)[2]**2 for atom,q in empirical.items())/16,F(29,12),'empirical feasible estimator variance')
    direct,_,_=compliance(direct=F(1,2));stats=arm_statistics(direct)
    exact_values.update({'ex8-direct-itt':stats[3][1]-stats[3][0],'ex8-direct-ratio':ratio(direct)})
    a.eq((exact_values['ex8-direct-itt'],ratio(direct)),(F(5,4),F(10,3)),'direct channel changes ratio interpretation')
    changed,treated2,att2=compliance(F(1,4))
    a.eq((ratio(changed),treated2,att2),(F(2),F(7,32),F(22,7)),'assignment probability changes treated composition')
    a.interventions.append('Observed-law quotient derivatives and actual sample frequencies check covariance-aware Wald inference; direct encouragement and assignment frequency separate ITT, LATE, ATT and precision.')

    for prob in (F(1,2),F(1,3)):
        pi,weights,matrix,law=exposures(prob)
        mu=sum(q*v for z,q,v in law);var=sum(q*(v-mu)**2 for z,q,v in law)
        a.eq(mu,4,'exposure contrast under nonuniform randomization')
        a.eq(sum(weights[i]*matrix[i][j]*weights[j] for i,j in product(range(6),repeat=2)),var,'entire indicator covariance quadratic form')
        a.eq(matrix[1][3],-pi[1]*pi[3],'adjacent treated-unexposed joint support is zero')
        for i in range(3):
            neighbors=2 if i==1 else 1
            a.eq(pi[2*i:2*i+2],[(1-prob)**(neighbors+1),prob*(1-prob)**neighbors],'target marginal exposure probabilities')
        if prob==F(1,2):
            exact_values.update({'interference-target':mu,'interference-edge-prob':pi[0],'interference-center-prob':pi[2],'interference-variance':var,'ex9-second-moment':sum(q*v*v for z,q,v in law)})
            for z,q,value in law:exact_values['ht-'+''.join(map(str,z))]=value
            a.eq([v for z,q,v in law],[F(-32,3),F(32,3),F(16),F(0),F(0),F(16),F(0),F(0)],'all eight exposure outcomes')
    a.eq(endpoint_mapping(0),{(0,0):1,(0,1):4,(1,0):3,(1,1):6},'all endpoint histories agree with the original exposure map')
    witness=((0,0,0),(0,0,1))
    a.eq([z[:2] for z in witness],[(0,0),(0,0)],'observed exposure labels in the remote-spillover witness')
    remote_outcomes=[1+2*z[0]+3*z[1]+2*z[2] for z in witness]
    exact_values['ex10-remote-outcome']=remote_outcomes[1]
    a.eq(remote_outcomes,[1,3],'actual outcomes differ at the same old label')
    a.interventions.append('Six exposure indicators reconstruct the full covariance; nonuniform assignment and absent joint or marginal support distinguish mean, variance and mapping identification.')

    r=F(4,5);treat_bounds=bounds(r,8);control_bounds=bounds(r,6)
    lo,hi=treat_bounds[0]-control_bounds[1],treat_bounds[1]-control_bounds[0]
    exact_values.update({'attrition-y1-low':treat_bounds[0],'attrition-y1-high':treat_bounds[1],'attrition-y0-low':control_bounds[0],'attrition-y0-high':control_bounds[1],'attrition-low':lo,'attrition-high':hi})
    target_observed={(0,1,F(6)):F(2,5),(0,0,None):F(1,10),(1,1,F(8)):F(2,5),(1,0,None):F(1,10)}
    for coupling in (F(3,5),F(16,25),F(4,5)):
        low,high=attrition(coupling,False),attrition(coupling,True)
        for rows,endpoint in ((low,lo),(high,hi)):
            a.eq(sum(q for q,*rest in rows),1,'endpoint potential law normalizes')
            a.eq(observed_attrition(rows),target_observed,'complete observed law preserved across endpoint and response dependence')
            a.eq(sum(q*(y1-y0) for q,r0,r1,y0,y1 in rows),endpoint,'sharp endpoint attained')
        mixture=[(q*F(3,4),r0,r1,y0,y1) for q,r0,r1,y0,y1 in low]+[(q*F(1,4),r0,r1,y0,y1) for q,r0,r1,y0,y1 in high]
        a.eq(observed_attrition(mixture),target_observed,'independent mixture preserves the full observation distribution')
        a.eq(sum(q*(y1-y0) for q,r0,r1,y0,y1 in mixture),F(3,4)*lo+F(1,4)*hi,'interior bound attainment')
    a.eq((bounds(1,8),bounds(1,6)),((F(8),F(8)),(F(6),F(6))),'full response collapses uncertainty')
    a.eq(bounds(0,None),(0,10),'zero response has only known support')
    tmean=r*8+(1-r)*4
    exact_values['retention-attrition-low']=tmean-control_bounds[1];exact_values['retention-attrition-high']=tmean-control_bounds[0]
    a.eq((lo,hi,exact_values['retention-attrition-low'],exact_values['retention-attrition-high']),(F(-2,5),F(18,5),F(2,5),F(12,5)),'identification and actual-follow-up intervals')
    a.interventions.append('Extreme, independent and common potential-response couplings give the same complete observed law and sharp bounds; mixtures and measured follow-up separate identification from sampling precision.')
    return exact_values,rounded,roots,len(probes)


def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    a=Audit()
    for name,size,digest in AUTHOR:
        raw=(root/name).read_bytes();a.eq((len(raw),hashlib.sha256(raw).hexdigest()),(size,digest),'frozen author '+name)
    page=Reader();page.feed((root/AUTHOR[0][0]).read_text());page.close()
    prompt_ids=['v12-c06-e'+str(i).zfill(2) for i in range(1,13)]
    a.eq((page.prompts,list(page.answers)),(prompt_ids,prompt_ids),'every exact prompt and paired solution')
    a.eq((page.worked,len(page.ids),len(set(page.ids)),page.stack),(7,32,32,[]),'actual markup structure')
    values,rounded,roots,cells=calculate(a)
    a.eq(set(page.values),set(values)|set(rounded),'all visible numerical markers independently covered')
    for k,v in values.items():a.eq(F(page.values[k].strip().replace('−','-')),v,'visible exact '+k)
    for k,v in rounded.items():a.close(float(page.values[k]),v,'visible rounded '+k,5e-7)
    sources=strict((root/AUTHOR[2][0]).read_text());author=strict((root/AUTHOR[3][0]).read_text())
    source_ids={s['id'] for s in sources['proposals']+sources['reused']}
    a.eq((len(source_ids),set(page.sources)),(4,source_ids),'four scoped source routes')
    a.eq(set(page.links),{'v12-c01.html','v12-c03.html','v12-c05.html'}|{'sources.html#'+i for i in source_ids},'flat prerequisite and source routes')
    for record,expected in ((author,{row[0] for row in AUTHOR[:3]}),(strict((root/RECORD).read_text()),{row[0] for row in AUTHOR}|{SELF})):
        bindings=record['reviewed_hashes'];a.eq(len(bindings),len(expected),'exact nonself binding count')
        a.eq({r['path'] for r in bindings},expected,'exact bound payload set')
        for row in bindings:
            raw=(root/row['path']).read_bytes();a.eq((len(raw),hashlib.sha256(raw).hexdigest()),(row['bytes'],row['sha256']),'current binding '+row['path'])
    invalid=[
        (lambda:exact(True),'boolean numeric input'),(lambda:exact(float('nan')),'nonfinite numeric input'),
        (lambda:exact(10**7),'out-of-scope magnitude'),(lambda:subsets(11,5),'outside finite assignment bound'),
        (lambda:subsets(6,0),'empty treated arm'),(lambda:subsets(6,6),'empty control arm'),
        (lambda:finite([1,2],[1],1),'incomplete potential table'),
        (lambda:dispersion([F(1)],1),'singleton sample variance'),
        (lambda:rank_values([1,2],[F(1,4),F(1,4)]),'unnormalized rank law'),
        (lambda:rank_values([1,2],[F(-1),F(2)]),'negative assignment mass'),
        (lambda:cdf(9),'unproved Gaussian numerical domain'),(lambda:power(0),'zero planning variance'),
        (lambda:allocation(1),'two-arm allocation impossible'),(lambda:allocation(10,0,1),'zero arm variance'),
        (lambda:compliance(0),'zero encouragement probability'),
        (lambda:ratio({(0,0,F(1)):F(1)}),'empty observed encouragement arm'),
        (lambda:ratio({(0,0,F(1)):F(1,2),(1,0,F(2)):F(1,2)}),'finite zero estimated first stage'),
        (lambda:exposures(fixed_one=True),'fixed-one center target exposure unavailable'),
        (lambda:exposures(1),'degenerate marginal exposure support'),
        (lambda:endpoint_mapping(2),'remote spillover invalidates the exposure map'),
        (lambda:attrition(F(1,2),True),'invalid response coupling'),
        (lambda:bounds(F(6,5),8),'invalid response probability'),
        (lambda:bounds(F(4,5),11),'respondent outcome outside support'),
        (lambda:bounds(0,8),'fabricated respondent mean'),
        (lambda:strict('{"x":1,"x":2}'),'duplicate JSON key'),
        (lambda:strict('NaN'),'nonfinite JSON literal'),(lambda:strict('1e400'),'overflowing JSON decimal')]
    for fn,label in invalid:a.reject(fn,label)
    result={'chapter':'v12-c06','status':'independent peer checks passed','comparisons':a.comparisons,'exact_numeric_anchors':len(values),'rounded_numeric_anchors':len(rounded),'worked_cases':7,'exercises':12,'solutions':12,'domain_rejections':len(a.rejections),'rejection_scopes':a.rejections,'purposeful_interventions':len(a.interventions),'intervention_scopes':a.interventions,'fisher_breakpoints':[str(x) for x in roots],'whole_real_line_cells_and_endpoints':cells,'gaussian_method':'50-digit exponential-series integration and bisection; bounded absolute argument 8','nonself_peer_bindings':5,'author_code_used_as_oracle':False,'limits':'Independent finite evidence plus separate proof reading; no empirical validity, general asymptotic theorem, rendered UI or acceptance claim.'}
    strict(json.dumps(result,allow_nan=False));return result


if __name__=='__main__':
    check()
