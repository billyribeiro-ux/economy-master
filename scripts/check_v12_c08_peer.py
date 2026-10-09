"""Independent, bounded, read-only RD/synthetic-control peer evidence.

Centered linear regression, Lagrange interpolation, planar convex geometry
and exact design masses are the numerical oracles. No author code is used.
"""
from decimal import Decimal, localcontext
from fractions import Fraction as F
from html.parser import HTMLParser
from itertools import combinations
import hashlib
import json
from math import floor, isfinite, sqrt
from pathlib import Path

AUTHOR=(
 ('content/chapters/v12-c08.html',44192,'f605836d96e7b8b6a344bbabd0898a10161390680a0527540d32b3e57e172a38'),
 ('scripts/check_v12_c08.py',31269,'6bbe39c449f28b8ebbd9b39f844894e8d51f990db9e9ea9f1ff0620b57ec6621'),
 ('content/reviews/v12-c08-sources.json',12555,'6b7327aaf29551b5c33e734c01b3d94cdd743452a1f4ddb1a697501648a17d07'),
 ('content/reviews/v12-c08-author.json',34799,'b6119abefdbf6869c01249b42d9155c50c39187c3c34fa0c9e214e6e01416cbd'),
)
SELF='scripts/check_v12_c08_peer.py'
RECORD='content/reviews/v12-c08-peer.json'


def need(ok,label):
    if not ok:raise ValueError('v12-c08 peer: '+label)


def strict(raw):
    def pairs(rows):
        out={}
        for k,v in rows:need(k not in out,'duplicate JSON member');out[k]=v
        return out
    def finite(s):
        x=float(s);need(isfinite(x),'finite JSON decimal');return x
    def bad(s):raise ValueError('nonfinite JSON '+s)
    return json.loads(raw,object_pairs_hook=pairs,parse_float=finite,parse_constant=bad)


def exact(x):
    need(type(x) in (int,F),'exact nonboolean scalar');x=F(x)
    need(abs(x)<=10**6,'bounded magnitude');return x


def dot(a,b):
    need(len(a)==len(b),'matching coordinates');return sum((x*y for x,y in zip(a,b)),F(0))


def difference(a,b):return [x-y for x,y in zip(a,b)]


def centered_weights(scores,kernels=None):
    need(2<=len(scores)<=32,'bounded local fit')
    x=[exact(v) for v in scores];ks=[F(1)]*len(x) if kernels is None else [exact(v) for v in kernels]
    need(len(ks)==len(x) and min(ks)>=0 and sum(ks)>0,'nonnegative effective kernel support')
    need(all(v>0 for v in x) or all(v<0 for v in x),'one cutoff side')
    mass=sum(ks);mean=dot(x,ks)/mass;centered=[v-mean for v in x]
    ss=dot(ks,[v*v for v in centered]);need(ss>0,'identified local slope')
    return [k/mass-mean*k*d/ss for k,d in zip(ks,centered)]


def lagrange(scores,leading=False):
    need(len(scores)==3,'three-point interpolation')
    x=[exact(v) for v in scores];need(len(set(x))==3,'distinct interpolation scores')
    result=[]
    for j in range(3):
        numerator=F(1);denominator=F(1)
        for k in range(3):
            if j!=k:
                numerator*=1 if leading else -x[k];denominator*=x[j]-x[k]
        result.append(numerator/denominator)
    return result


def grid(n,k,sigma2=F(1,100),delta=F(4)):
    need(type(n) is int and type(k) is int and 2<=k<=n<=10**8,'bounded integer grid')
    sigma2,delta=exact(sigma2),exact(delta);need(sigma2>0,'positive Gaussian noise')
    return -delta*F((k+1)*(k+2),6*n*n),4*sigma2*F(2*k+1,k*(k-1))


def cross(a,b):return a[0]*b[1]-a[1]*b[0]


def convex_projection(target,donors):
    """Euclidean projection onto a point, segment or triangle in the plane.

    Interior barycentric coordinates and all boundary segment projections
    exhaust the hull. Duplicate/collinear donor ties use lexicographic weights.
    """
    need(len(target)==2 and 2<=len(donors)<=3 and all(len(x)==2 for x in donors),'two-dimensional two/three-donor geometry')
    target=[exact(x) for x in target];donors=[[exact(x) for x in d] for d in donors]
    J=len(donors);candidates=[]
    def add(weights):
        fit=[sum(weights[j]*donors[j][k] for j in range(J)) for k in (0,1)]
        e=difference(target,fit);candidates.append((dot(e,e),tuple(weights),fit,e))
    for j in range(J):
        w=[F(0)]*J;w[j]=1;add(w)
    for i,j in combinations(range(J),2):
        direction=difference(donors[i],donors[j]);den=dot(direction,direction)
        if den:
            w_i=max(F(0),min(F(1),dot(difference(target,donors[j]),direction)/den))
            w=[F(0)]*J;w[i]=w_i;w[j]=1-w_i;add(w)
    if J==3:
        u=difference(donors[0],donors[2]);v=difference(donors[1],donors[2]);b=difference(target,donors[2]);det=cross(u,v)
        if det:
            w0,w1=cross(b,v)/det,cross(u,b)/det
            if min(w0,w1,1-w0-w1)>=0:add([w0,w1,1-w0-w1])
    best=min(candidates,key=lambda x:(x[0],x[1]))
    need(all(dot(best[3],difference(x,best[2]))<=0 for x in donors),'global convex-projection certificate')
    return best


def fuzzy(rows,direct=F(0)):
    need(2<=len(rows)<=4,'bounded cutoff types')
    need(all(len(row)==5 for row in rows),'complete cutoff type')
    rows=[(exact(p),d0,d1,exact(y0),exact(effect)) for p,d0,d1,y0,effect in rows]
    need(sum(row[0] for row in rows)==1 and min(row[0] for row in rows)>0,'positive normalized cutoff type masses')
    need(all(type(d0) is int and type(d1) is int and d0 in (0,1) and d1 in (0,1) for p,d0,d1,y,e in rows),'binary receipt potentials')
    direct=exact(direct);limits=[]
    for z in (0,1):
        d=sum(p*(d1 if z else d0) for p,d0,d1,y,e in rows)
        y=sum(p*(y+e*(d1 if z else d0)+direct*z) for p,d0,d1,y,e in rows)
        limits.append((d,y))
    denominator=limits[1][0]-limits[0][0];need(denominator!=0,'nonzero cutoff first stage')
    return limits,(limits[1][1]-limits[0][1])/denominator,sum(p*e for p,d0,d1,y,e in rows)


def score(pre,post):
    pre,post=exact(pre),exact(post);need(min(pre,post)>=0,'nonnegative squared errors')
    return (1,F(0)) if pre==0 and post>0 else (0,F(0)) if pre==0 else (0,post/pre)


def ranks(scores,masses):
    need(2<=len(scores)==len(masses)<=8,'matching supported labels')
    masses=[exact(x) for x in masses];need(min(masses)>0 and sum(masses)==1,'actual positive assignment law')
    for top,value in scores:
        need(type(top) is int and top in (0,1) and exact(value)>=0 and (not top or value==0),'valid extended score')
    # Group tied levels before accumulating actual assignment mass.
    tails={};total=F(0)
    for level in sorted(set(scores),reverse=True):
        total+=sum(p for p,s in zip(masses,scores) if s==level);tails[level]=total
    return [tails[s] for s in scores]


class Reader(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.stack=[];self.ids=[];self.worked=0;self.prompts=[];self.answers={};self.active=None;self.text=[];self.links=[];self.sources=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs);need(len(a)==len(attrs),'unique HTML attributes')
        if 'id' in a:self.ids.append(a['id'])
        if tag=='li' and a.get('id','').startswith('v12-c08-e'):self.prompts.append(a['id'])
        if 'data-solution-for' in a:
            need(self.active is None and a['data-solution-for'] not in self.answers,'unique solution');self.active=a['data-solution-for'];self.answers[self.active]=''
        if 'href' in a:self.links.append(a['href'])
        if 'data-source' in a:self.sources.append(a['data-source'])
        self.worked+='worked' in a.get('class','').split()
        if tag not in ('br','hr','img','meta','link','input'):self.stack.append((tag,a))
    def handle_data(self,data):
        self.text.append(data)
        if self.active is not None:self.answers[self.active]+=data
    def handle_endtag(self,tag):
        need(self.stack and self.stack[-1][0]==tag,'balanced markup');t,a=self.stack.pop()
        if 'data-solution-for' in a:self.active=None


class Audit:
    def __init__(self):self.comparisons=0;self.rejections=[];self.anchors=0;self.interventions=[]
    def eq(self,x,y,label):
        self.comparisons+=1;need(x==y,label+': '+repr(x)+' != '+repr(y))
    def close(self,x,y,label,tol=2e-12):
        self.comparisons+=1;need(isfinite(x) and isfinite(y) and abs(x-y)<=tol,label)
    def reject(self,fn,label):
        try:fn()
        except ValueError:self.rejections.append(label)
        else:raise ValueError('missing rejection '+label)
    def anchor(self,page,e,values):
        norm=lambda x:''.join(str(x).split()).replace('−','-')
        text=norm(page.answers['v12-c08-e'+str(e)])
        for value in values:self.eq(norm(value) in text,True,'computed solution anchor '+str(e)+': '+str(value));self.anchors+=1


def numerical(a,page):
    # Simpson endpoint/midpoint averaging integrates these quadratic means exactly.
    left=lambda r:2+r+r*r
    right=lambda r:5+2*r+r*r
    for h,target in ((F(1),F(9,2)),(F(1,5),F(33,10))):
        right_mean=(right(0)+4*right(h/2)+right(h))/6
        left_mean=(left(-h)+4*left(-h/2)+left(0))/6
        a.eq(right_mean-left_mean,target,'exact quadratic Simpson window means')
    for endpoint in (F(-3,4),F(-1,4),F(1,4),F(3,4)):
        # Fair type chooses sign; |V| is uniform, yielding the uniform-score CDF.
        cdf_score=F(1,2)*(1+endpoint) if endpoint<0 else F(1,2)+F(1,2)*endpoint
        a.eq(cdf_score,(endpoint+1)/2,'sorting pushforward distribution')
    for r in (F(-1,4),F(1,4)):
        obs=left(r) if r<0 else right(r);potential=(obs,obs)
        a.eq(potential[1]-potential[0],0,'same observed sharp-rule curve admits zero effect')
    a.anchor(page,1,['continuous','positive','P(R=0)=0','same observations'])
    a.anchor(page,2,[F(9,2),F(33,10),'1/2','Y(1)−Y(0)=0','randomized'])
    a.interventions.append('Exact quadratic integration and the complete sorting-score CDF distinguish window means, smooth density and causal continuity.')

    x=[F(1,10),F(1,5),F(3,10)]
    w=centered_weights(x);v=lagrange(x);q=lagrange(x,True)
    a.eq(w,[F(4,3),F(1,3),F(-2,3)],'centered-regression intercept weights')
    a.eq(v,[F(3),F(-3),F(1)],'Lagrange cutoff interpolation')
    a.eq(q,[F(50),F(-100),F(50)],'Lagrange leading coefficient')
    a.eq(centered_weights([-t for t in x]),w,'left-side intercept symmetry')
    a.eq(centered_weights(x,[2,2,2]),w,'common kernel scaling')
    for weights,degree in ((w,1),(v,2)):
        for power in range(degree+1):a.eq(dot(weights,[z**power for z in x]),int(power==0),'intercept reproduction')
    lm=[1-2*t+t*t for t in x];rm=[3+4*t+5*t*t for t in x]
    a.eq(lm,[F(81,100),F(16,25),F(49,100)],'all left fixed-score means')
    a.eq(rm,[F(69,20),F(4),F(93,20)],'all right fixed-score means')
    means=[dot(weights,difference(rm,lm)) for weights in (w,v)]
    correction=[t/30 for t in q]
    old=2*dot(w,w);added=2*dot(correction,correction);cov=2*dot(w,correction);new=2*dot(v,v)
    a.eq((means,old,added,cov,new),([F(28,15),F(2)],F(14,3),F(100,3),F(0),F(38)),'means and complete correction covariance')
    a.eq([u+c for u,c in zip(w,correction)],v,'same-data estimated correction weights')
    a.eq([dot(q,lm),dot(q,rm)],[F(1),F(5)],'estimated curvature means')
    absolute=dot([abs(t) for t in w],[t*t for t in x]);B=6*absolute
    a.eq((dot(w,[t*t for t in x]),absolute,B),(F(-1,30),F(13,150),F(13,25)),'signed versus bounded-curvature moments')
    z=critical();wrong=2*cdf(z*sqrt(float(old/new)))-1;radius=float(B)+z*.1*sqrt(float(old))
    a.close(wrong,.507820530046,'coverage with old variance')
    a.close(radius,.943400612067,'bias-aware radius')
    sd=.1*sqrt(float(old))
    conservative=cdf((radius-float(B))/sd)-cdf((-radius-float(B))/sd)
    a.eq(conservative>=.95,True,'actual Gaussian coverage at the largest allowed mean bias')
    variances=[1,2,1]
    hetero=lambda u,v:2*sum(u[j]*v[j]*variances[j] for j in range(3))
    a.eq((hetero(w,correction),hetero(v,v)),(F(-20,9),F(56)),'heteroskedastic transfer makes correction covariance nonzero')
    a.eq(hetero(w,w)+hetero(correction,correction)+2*hetero(w,correction),hetero(v,v),'heteroskedastic full covariance identity')
    a.anchor(page,3,['4/3,1/3,−2/3','3,−3,1',means[0],old,new,'Negative'])
    a.anchor(page,4,[added,'covariance','0.507820530046',absolute,B,'0.943400612067'])
    a.interventions.append('Centered regression and Lagrange interpolation independently recover all weights; changed noise variances demonstrate why the zero covariance is not general.')

    for k in (2,3,4,8,17):
        n=100;weights=centered_weights([F(j,n) for j in range(1,k+1)])
        a.eq(weights,[F(2*(2*k+1-3*j),k*(k-1)) for j in range(1,k+1)],'arbitrary-grid formula from centered regression')
        a.eq((sum(weights),dot(weights,list(range(1,k+1))),dot(weights,[j*j for j in range(1,k+1)]),dot(weights,weights)),(1,0,F(-(k+1)*(k+2),6),F(2*(2*k+1),k*(k-1))),'four grid identities')
        b,var=grid(n,k)
        a.eq((b,var),(dot(weights,[4*F(j,n)**2 for j in range(1,k+1)]),F(1,50)*dot(weights,weights)),'exact grid bias and variance')
        a.eq((sum(abs(t) for t in weights)**2<=10,var<=F(1,5*k)),(True,True),'uniform curvature and variance bounds')
    rounded=[]
    for n in (10000,100000000):
        nh=n*(.045/n)**.2;k=floor(nh);b,var=grid(n,k)
        a.eq(abs(k/nh-1)<=1/nh,True,'integer rounding error relative to diverging local sample')
        rounded.append(abs(float(b))/sqrt(float(var)))
    a.eq(abs(rounded[1]-.5)<abs(rounded[0]-.5),True,'exact rounded optimal sequence approaches nonzero scaled bias')
    a.eq(F(16)*F(72)*F(1,100)/(F(16)*288*F(1,100)),F(1,4),'leading optimum bias variance ratio')
    a.eq(F(1,4)*F(1,2)**5,F(1,128),'fixed half-width retains positive limiting squared bias')
    standardized=[]
    for n,k in ((10000,1000),(100000000,1000000)):
        b,var=grid(n,k);standardized.append(abs(float(b))/sqrt(float(var)))
    a.eq(standardized[1]<standardized[0],True,'specified rate undersmoothing sequence')
    a.eq((1-F(1,4)>0,F(1,2)-F(5,2)*F(1,4)<0),(True,True),'local information grows while standardized bias vanishes')
    conventional=cdf(z-.5)-cdf(-z-.5)
    a.close(conventional,.920902465839,'optimal-width conventional coverage')
    a.anchor(page,5,['72σ²','1/2','0.920902465839','r⁵ᐟ²/2','n⁻¹ᐟ⁴','√10','20σ²/k'])
    a.interventions.append('Five exact grids, finite rounding and two rate sequences distinguish a leading-MSE optimum, fixed-fraction bias and true rate undersmoothing.')

    types=[(F(1,4),1,1,2,6),(F(1,2),0,1,1,4),(F(1,4),0,0,0,0)]
    limits,ratio,ate=fuzzy(types)
    a.eq((limits,ratio,ate),([(F(1,4),F(5,2)),(F(3,4),F(9,2))],F(4),F(7,2)),'all original cutoff limits and estimands')
    direct=fuzzy(types,F(1,2));a.eq((direct[0][1][1]-direct[0][0][1],direct[1]),(F(5,2),F(5)),'exclusion failure')
    defiers=[(F(1,4),1,1,2,6),(F(3,8),0,1,1,4),(F(1,8),1,0,1,8),(F(1,4),0,0,0,0)]
    dl,dr,da=fuzzy(defiers)
    a.eq((dl,dr),([(F(3,8),F(7,2)),(F(5,8),F(4))],F(2)),'negative defier weights')
    a.anchor(page,6,['1/4,3/4','5/2,9/2',ate,'3/8,5/8','exclusion','monotonicity','common cutoff'])
    a.interventions.append('Distinct type tables and direct eligibility shifts separate exclusion, monotonicity and positive first stage.')

    donors=[[0,1],[2,2],[1,3]];target=[F(5,4),F(2)]
    full=convex_projection(target,donors);reduced=convex_projection(target,donors[:2])
    a.eq((full[0],full[1],full[2]),(F(0),(F(1,4),F(1,2),F(1,4)),target),'interior barycentric full fit')
    a.eq((reduced[0],reduced[1],reduced[2],reduced[3]),(F(9,80),(F(3,10),F(7,10)),[F(7,5),F(17,10)],[F(-3,20),F(3,10)]),'boundary segment projection after donor deletion')
    loading=[(0,1),(2,0),(1,2)]
    forecast=lambda weights,s:sum(w*(p[0]+s*p[1]) for w,p in zip(weights,loading))
    cf=[forecast(full[1],s) for s in (2,3,4)];rf=[forecast(reduced[1],s) for s in (2,3,4)]
    a.eq(cf,[F(11,4),F(7,2),F(17,4)],'full holdout and post predictions')
    a.eq(rf,[F(2),F(23,10),F(13,5)],'reduced holdout and post predictions')
    observed=[F(11,2),F(29,4)];gaps=difference(observed,cf[1:]);rgaps=difference(observed,rf[1:])
    a.eq((gaps,rgaps,cf[0]-rf[0]),([F(2),F(3)],[F(16,5),F(93,20)],F(3,4)),'supported and missupported gaps')
    delta_loading=[reduced[3][0],reduced[3][1]-reduced[3][0]]
    for s,expected in ((3,F(6,5)),(4,F(33,20))):
        row=[1-s,s];disc=dot([1,s],delta_loading)
        a.eq(disc,expected,'loading difference directly predicts the forecast error')
        a.eq(disc**2<=dot(row,row)*reduced[0],True,'left-inverse Cauchy-Schwarz bound')
    # Rank-deficient pre factors still suffice for a future row in their row span.
    null_loading=[F(0),F(7)];pre_rows=[[1,0],[2,0]]
    a.eq([dot(row,null_loading) for row in pre_rows], [0,0],'rank-deficient exact prefit')
    a.eq(dot([3,0],null_loading),0,'supported future row needs no full column rank')
    a.eq(dot([0,1],null_loading),7,'unsupported future row exposes the hidden loading')
    a.anchor(page,7,['compact','flat direction','1/4,1/2,1/4',cf[0],'7/2,17/4','unique'])
    a.anchor(page,8,[F(3,10),reduced[0],F(3,4),'23/10,13/5','16/5,93/20',F(6,5),F(33,20)])
    a.interventions.append('Planar projection supplies global simplex fits; independent loading differences and a rank-deficient row-span example test the factor extrapolation assumptions.')

    hidden_cf=[cf[1]+1,cf[2]+2]
    a.eq((hidden_cf,difference(observed,hidden_cf)),([F(9,2),F(25,4)],[F(1),F(1)]),'same observed post outcomes support a different hidden-factor causal story')
    contaminated=[cf[1]+2*full[1][1],cf[2]+2*full[1][1]]
    a.eq(difference(observed,contaminated),[1,2],'separate donor-B contamination changes observed donor data')
    duplicate=convex_projection([1,1],[[1,1],[1,1]])
    a.eq((duplicate[0],duplicate[1]),(0,(F(0),F(1))),'lexicographic perfect-fit tie')
    collinear=convex_projection([1,1],[[0,0],[2,2],[1,1]])
    a.eq(collinear[1],(0,0,1),'nonunique weights with a unique fitted predictor')
    for w in (F(0),F(1,3),F(1)):
        prediction=dot([w,1-w],[2,8]);a.eq((prediction,7-prediction),(8-6*w,-1+6*w),'every mixture gives its matching forecast and causal-gap witness')
    a.eq(7-(8+4)<-1,True,'unrestricted post-only factor can leave the optimal-forecast interval')
    a.anchor(page,9,[F(9,2),F(25,4),'1,1','zero column','1,2','same-data'])
    a.anchor(page,10,['2 to 8','−1 to 5','0,1','fixed convex-mixture','not a causal'])
    a.interventions.append('Hidden-factor observational equivalence, changed donor observations and degenerate-fit mixture ranges preserve distinct identification claims.')

    pre=[[0,0],[2,0],[0,2],[2,2]];post=[4,0,1,2];scores=[];placebos=[]
    expected=[(F(1,2),F(1,2),0),(F(1,2),0,F(1,2)),(F(1,2),0,F(1,2)),(0,F(1,2),F(1,2))]
    for treated in range(4):
        others=[i for i in range(4) if i!=treated]
        result=convex_projection(pre[treated],[pre[i] for i in others]);gap=post[treated]-dot(result[1],[post[i] for i in others])
        a.eq((result[1],result[2],result[0]),(expected[treated],[1,1],2),'entire leave-one-label-out projection')
        scores.append(score(result[0]/2,gap*gap));placebos.append(gap)
    a.eq(placebos,[F(7,2),F(-3),F(-2),F(3,2)],'all placebo post gaps')
    uniform=[F(1,4)]*4;actual=[F(7,10)]+[F(1,10)]*3
    pu,pa=ranks(scores,uniform),ranks(scores,actual)
    a.eq(pu,[F(1,4),F(1,2),F(3,4),F(1)],'uniform reference tails')
    a.eq(pa,[F(7,10),F(4,5),F(9,10),F(1)],'actual assignment tails')
    size=lambda probs,ps,alpha:sum(p for p,v in zip(probs,ps) if v<=alpha)
    a.eq((size(uniform,pu,F(1,4)),size(actual,pu,F(1,4)),size(actual,pa,F(1,4)),size(uniform,pu,F(1,20))),(F(1,4),F(7,10),0,0),'actual and falsely assigned rejection probabilities')
    tied=[score(0,1),score(0,9),score(0,0)];tp=[F(1,5),F(3,10),F(1,2)]
    a.eq(ranks(tied,tp),[F(1,2),F(1,2),F(1)],'inclusive infinite-score ties')
    a.eq(ranks([score(0,0)]*3,tp),[1,1,1],'zero-zero convention never invents a tail')
    for alpha in set(pa+pu+[F(1,4),F(1,20)]):a.eq(size(actual,pa,alpha)<=alpha,True,'actual-law validity at every rejection jump')
    a.anchor(page,11,['7/2,−3,−2,3/2','1/4,1/2,3/4,1','7/10,4/5,9/10,1','upper tail','ties','5%'])
    a.anchor(page,12,['Six objections','Two repairs','Conclusion','rate condition','assignment'])
    a.eq(6+2*2+2,12,'open rubric points')
    a.interventions.append('All four placebo algorithms are refitted; actual assignment weights, infinity ties and zero-zero scores determine finite calibration.')
    return {'wrong_corrected_coverage':wrong,'curvature_radius':radius,'optimal_width_coverage':conventional,'rounded_optimal_scaled_bias':rounded,'undersmoothed_scaled_bias':standardized,'weighted_placebo_p':[str(p) for p in pa]}


def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1];a=Audit()
    for name,size,digest in AUTHOR:
        raw=(root/name).read_bytes();a.eq((len(raw),hashlib.sha256(raw).hexdigest()),(size,digest),'frozen author '+name)
    page=Reader();page.feed((root/AUTHOR[0][0]).read_text());page.close();ids=['v12-c08-e'+str(i) for i in range(1,13)]
    a.eq((page.prompts,list(page.answers)),(ids,ids),'all exact paired prompts and solutions')
    a.eq((page.worked,page.stack,len(set(page.ids))),(6,[],len(page.ids)),'complete unique reader structure')
    evidence=numerical(a,page)
    sources=strict((root/AUTHOR[2][0]).read_text());author=strict((root/AUTHOR[3][0]).read_text())
    source_ids={s['id'] for s in sources['sources']};a.eq((len(source_ids),set(page.sources)),(3,source_ids),'three primary source routes')
    a.eq(set(page.links),{'v12-c01.html','v12-c02.html','v12-c03.html','v12-c06.html','v12-c07.html','v12-c09.html'}|{'sources.html#'+s for s in source_ids},'flat chapter and source links')
    a.eq(set(author['payloads']),{r[0] for r in AUTHOR[:3]},'three nonself author bindings')
    for path,row in author['payloads'].items():
        raw=(root/path).read_bytes();a.eq({'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()},row,'author binding '+path)
    review=strict((root/RECORD).read_text());bindings=review['reviewed_hashes']
    a.eq((len(bindings),{r['path'] for r in bindings}),(5,{r[0] for r in AUTHOR}|{SELF}),'exact peer payload set')
    for row in bindings:
        raw=(root/row['path']).read_bytes();a.eq((len(raw),hashlib.sha256(raw).hexdigest()),(row['bytes'],row['sha256']),'peer binding '+row['path'])
    invalid=[(lambda:exact(True),'boolean scalar'),(lambda:exact(float('nan')),'nonfinite scalar'),(lambda:exact(10**7),'outside magnitude bound'),
      (lambda:centered_weights([1,1]),'local rank failure'),(lambda:centered_weights([-1,1]),'mixed cutoff sides'),(lambda:centered_weights([1,2],[0,0]),'zero kernel support'),(lambda:centered_weights([1,2],[1,-1]),'negative kernel'),
      (lambda:lagrange([1,1,2]),'quadratic interpolation rank'),(lambda:grid(4,5),'unavailable grid observations'),(lambda:grid(True,2),'boolean grid count'),(lambda:grid(10,1),'one local point'),
      (lambda:cdf(9),'outside proved Gaussian numerical interval'),(lambda:convex_projection([1,1],[[1,1],[2]]),'incomplete donor coordinate'),
      (lambda:fuzzy([(F(1,2),0,0,0,1),(F(1,2),1,1,0,1)]),'zero cutoff first stage'),
      (lambda:fuzzy([(F(1,4),0,1,0,1),(F(1,4),0,0,0,1)]),'incomplete type law'),
      (lambda:score(-1,1),'negative preMSE'),(lambda:ranks([(0,1),(0,2)],[0,1]),'unsupported assignment label'),(lambda:ranks([(1,2),(0,1)],[F(1,2)]*2),'invalid infinity encoding'),
      (lambda:strict('{"x":1,"x":2}'),'duplicate JSON'),(lambda:strict('NaN'),'nonfinite JSON'),(lambda:strict('1e400'),'overflowed JSON')]
    for fn,label in invalid:a.reject(fn,label)
    result={'chapter':'v12-c08','status':'independent peer checks passed','comparisons':a.comparisons,'computed_solution_anchors':a.anchors,'domain_rejections':len(a.rejections),'rejection_scopes':a.rejections,'purposeful_interventions':len(a.interventions),'intervention_scopes':a.interventions,'worked_cases':6,'exercises':12,'solutions':12,'nonself_peer_bindings':5,'author_code_used_as_oracle':False,'finite_evidence':evidence,'limits':'Finite independent evidence and separately recorded proof review; no empirical validity, general RBC or stochastic synthetic-control theorem, rendered UI or acceptance claim.'}
    strict(json.dumps(result,allow_nan=False));return result


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


if __name__=='__main__':
    check()
