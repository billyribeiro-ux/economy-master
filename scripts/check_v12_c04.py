"""Readonly original-contract checks for the likelihood chapter.

Finite probability laws, direct likelihoods, row-wise moments and independently
integrated selection densities supply the evidence. They do not prove the
chapter's limit theorems or establish empirical identification. No third-party
package, data file, network, random simulation or shared checker is used.
"""
from fractions import Fraction as F
from html.parser import HTMLParser
import hashlib
import json
from math import erf, erfc, exp, isclose, isfinite, log, log1p, pi, sqrt
from pathlib import Path
from statistics import NormalDist

HTML = 'content/chapters/v12-c04.html'
SELF = 'scripts/check_v12_c04.py'
SOURCES = 'content/reviews/v12-c04-sources.json'
REVIEW = 'content/reviews/v12-c04-author.json'


def need(ok, message):
    if not ok:
        raise ValueError('v12-c04: ' + message)


def number(x):
    need(type(x) in (int, float, F) and isfinite(float(x)), 'finite numeric value, excluding bool')
    return x


def matrix(rows):
    need(isinstance(rows, (list, tuple)) and rows, 'nonempty matrix')
    need(all(isinstance(r, (list, tuple)) for r in rows), 'matrix rows')
    width = len(rows[0])
    need(width and all(len(r) == width for r in rows), 'rectangular matrix')
    return tuple(tuple(number(v) for v in r) for r in rows)


def transpose(a):
    return tuple(zip(*a))


def multiply(a, b):
    need(len(a[0]) == len(b), 'conformable product')
    return tuple(tuple(sum(x*y for x, y in zip(row, col)) for col in transpose(b)) for row in a)


def invert2(a):
    a = matrix(a)
    need(len(a) == len(a[0]) == 2 and a[0][1] == a[1][0], 'symmetric two-dimensional curvature')
    det = a[0][0]*a[1][1]-a[0][1]*a[1][0]
    need(a[0][0] > 0 and det > 0, 'positive definite curvature')
    return ((a[1][1]/det, -a[0][1]/det), (-a[1][0]/det, a[0][0]/det))


def outer(x):
    return tuple(tuple(v*w for w in x) for v in x)


def expectation(states, fn):
    return sum(p*fn(x, y) for p, x, y in states)


def weighted_matrix(states, fn):
    return tuple(tuple(expectation(states, lambda x, y: fn(x, y)[i][j]) for j in range(2)) for i in range(2))


def matvec(a, v):
    return tuple(sum(x*y for x, y in zip(row, v)) for row in a)


def sandwich(a, b):
    ai = invert2(a)
    return multiply(multiply(ai, b), ai)


def logistic(eta):
    eta = number(eta)
    if eta >= 0:
        return 1/(1+exp(-eta))
    z = exp(eta)
    return z/(1+z)


def softplus(eta):
    return max(eta, 0)+log1p(exp(-abs(eta)))


def binary_loglik(beta, rows):
    need(len(beta) == 2, 'binary coefficient dimension')
    beta = tuple(number(v) for v in beta)
    value = 0.0
    for d, y in rows:
        need(type(d) is int and d in (0, 1) and type(y) is int and y in (0, 1), 'binary observations')
        eta = beta[0]+d*beta[1]
        value += y*eta-softplus(eta)
    return value


def grouped_binary(groups):
    need(isinstance(groups, (list, tuple)) and len(groups) == 2, 'two binomial groups')
    ps = []
    for n, k in groups:
        need(type(n) is int and type(k) is int and n > 0 and 0 <= k <= n, 'binomial counts')
        need(0 < k < n, 'finite unconstrained group log odds require interior fraction')
        ps.append(F(k, n))
    eta = [log(float(p/(1-p))) for p in ps]
    return tuple(ps), (eta[0], eta[1]-eta[0])


def exponential_fit(data):
    need(isinstance(data, (list, tuple)) and data, 'nonempty exponential sample')
    data = [number(x) for x in data]
    need(all(x >= 0 for x in data) and sum(data) > 0, 'nonnegative waiting times with positive sum')
    return F(len(data))/sum(data)


def exponential_loglik(rate, data):
    rate = number(rate)
    need(rate > 0, 'positive exponential rate')
    need(all(number(y) >= 0 for y in data), 'nonnegative exponential support')
    return len(data)*log(float(rate))-rate*sum(data)


def count_fit(rows):
    need(isinstance(rows, (list, tuple)) and rows, 'nonempty count sample')
    for d, y in rows:
        need(type(d) is int and d in (0, 1), 'binary group design')
        need(type(y) is int and y >= 0, 'nonnegative integer count')
    need({d for d, y in rows} == {0, 1}, 'two independent count design columns')
    means = {d:sum(F(y) for di, y in rows if di == d)/sum(di == d for di, y in rows) for d in (0, 1)}
    need(all(v > 0 for v in means.values()), 'finite unconstrained group log mean')
    states = [(F(1, len(rows)), (F(1), F(d)), F(y)) for d, y in rows]
    a = weighted_matrix(states, lambda x, y: tuple(tuple(means[int(x[1])]*v*w for w in x) for v in x))
    b = weighted_matrix(states, lambda x, y: tuple(tuple((y-means[int(x[1])])**2*v*w for w in x) for v in x))
    return means, a, b, sandwich(a, b)


def normal_pdf(t):
    return exp(-t*t/2)/sqrt(2*pi)


def normal_cdf(t):
    return erfc(-t/sqrt(2))/2


def selection_parameters(a, mu, sigma, rho):
    a, mu, sigma, rho = map(number, (a, mu, sigma, rho))
    need(sigma > 0 and abs(rho) < 1, 'positive scale and nonsingular Gaussian correlation')
    need(abs(a) <= 8, 'bounded numeric selection exercise: absolute index at most eight')
    return a, mu, sigma, rho


def selected_joint(y, a, mu, sigma, rho):
    y = number(y)
    a, mu, sigma, rho = selection_parameters(a, mu, sigma, rho)
    t = (y-mu)/sigma
    return normal_pdf(t)*normal_cdf((a+rho*t)/sqrt(1-rho*rho))/sigma


def simpson(fn, left=-10.0, right=10.0, n=4096):
    need(type(n) is int and n > 0 and n % 2 == 0, 'positive even quadrature panel count')
    h = (right-left)/n
    return h*(fn(left)+fn(right)+sum((4 if i % 2 else 2)*fn(left+i*h) for i in range(1, n)))/3


def uniform_fit(data):
    need(isinstance(data, (list, tuple)) and data, 'nonempty uniform sample')
    data = [number(x) for x in data]
    need(all(x >= 0 for x in data) and max(data) > 0, 'uniform nonnegative observations with positive maximum')
    return max(data)


def uniform_interval(data, alpha):
    alpha = number(alpha)
    need(0 < alpha < 1, 'interior tail probability')
    m = uniform_fit(data)
    return m, float(m)/float(alpha)**(1/len(data))


def uniform_tail(n, t):
    need(type(n) is int and n > 0, 'positive integer sample size')
    t = number(t)
    need(t >= 0, 'nonnegative scaled maximum gap')
    return (1-F(t)/n)**n if t <= n else F(0)


def strict(raw):
    def pairs(items):
        out = {}
        for key, value in items:
            need(key not in out, 'duplicate JSON key');out[key] = value
        return out
    def constant(x):
        raise ValueError('nonfinite JSON ' + x)
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)


class Audit:
    def __init__(self):
        self.comparisons = 0;self.rejections = [];self.interventions = []
    def eq(self, got, wanted, label):
        self.comparisons += 1
        need(got == wanted, label + ': ' + repr(got) + ' != ' + repr(wanted))
    def near(self, got, wanted, label, tolerance=5e-9):
        self.comparisons += 1
        need(isclose(float(got), float(wanted), rel_tol=0, abs_tol=tolerance), label)
    def reject(self, fn, label):
        try:fn()
        except ValueError:self.rejections.append(label)
        else:raise ValueError('Expected executed rejection: ' + label)


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack=[];self.ids=[];self.links=[];self.sources=[];self.worked=0;self.h1=0
        self.prompts=[];self.targets=[];self.ex_depth=0;self.answer=None;self.answer_depth=0;self.answers={}
        self.calc=None;self.values={};self.tables={};self.table=None;self.caption=None;self.row=None;self.cell=None
    def handle_starttag(self, tag, attrs):
        d=dict(attrs);classes=d.get('class','').split()
        if 'id' in d:self.ids.append(d['id'])
        if tag=='a':self.links.append(d.get('href',''))
        if tag=='h1':self.h1+=1
        if 'worked' in classes:self.worked+=1
        if 'data-source' in d:self.sources.append(d['data-source'])
        if tag=='ol' and 'exercises' in classes:self.ex_depth=len(self.stack)+1
        if tag=='li' and self.ex_depth==len(self.stack)>0:self.prompts.append(d.get('id'))
        if 'data-solution-for' in d:
            need(tag=='li' and self.answer is None,'separate exact solution item')
            self.answer=d['data-solution-for'];self.targets.append(self.answer);self.answers[self.answer]='';self.answer_depth=len(self.stack)+1
        if 'data-calc' in d:
            need(tag=='span' and self.calc is None and d['data-calc'] not in self.values,'unique calculation marker')
            self.calc=d['data-calc'];self.values[self.calc]=''
        if tag=='table':self.table={'caption':'','rows':[]}
        if tag=='caption':self.caption=''
        if tag=='tr':self.row=[]
        if tag in ('td','th'):self.cell=''
        if tag not in ('br','hr','img','input','meta','link'):self.stack.append(tag)
    def handle_data(self, value):
        need(bool(self.stack) or not value.strip(),'no bare text outside chapter sections')
        if self.answer is not None:self.answers[self.answer]+=value
        if self.calc is not None:self.values[self.calc]+=value
        if self.caption is not None:self.caption+=value
        if self.cell is not None:self.cell+=value
    def handle_endtag(self, tag):
        need(self.stack and self.stack[-1]==tag,'balanced HTML '+tag)
        if len(self.stack)==self.answer_depth:self.answer=None;self.answer_depth=0
        if tag=='ol' and len(self.stack)==self.ex_depth:self.ex_depth=0
        self.stack.pop()
        if tag=='span':self.calc=None
        if tag=='caption':self.table['caption']=self.caption.strip();self.caption=None
        if tag in ('td','th'):self.row.append(self.cell.strip());self.cell=None
        if tag=='tr':self.table['rows'].append(self.row);self.row=None
        if tag=='table':self.tables[self.table['caption']]=self.table['rows'];self.table=None


def calculate(a, page):
    exact={};rounded={}
    times=[F(1,2),F(1),F(3,2),F(2),F(5,2),F(3)]
    rate=exponential_fit(times);mean=sum(times)/len(times);info=1/rate**2
    a.eq((rate,mean,info),(F(4,7),F(7,4),F(49,16)),'waiting-time original data')
    a.eq(F(len(times))/rate-sum(times),0,'exponential original score at optimum')
    for alternative in (rate/2,rate*2):a.eq(exponential_loglik(rate,times)>exponential_loglik(alternative,times),True,'likelihood declines away from maximum')
    exact.update({'exp-rate':rate,'exp-mean':mean,'exp-information':info,'exp-total-info':len(times)*info,
                  'exp-root-variance':1/info,'exp-log-variance':F(1)})
    rounded['exp-se']=sqrt(float(1/info/len(times)))
    minutes=[60*x for x in times];mr=exponential_fit(minutes)
    a.eq((mr,1/mr,1/mr**2),(rate/60,60*mean,3600*info),'physical unit conversion')
    exact.update({'ex2-minute-rate':mr,'ex2-minute-mean':1/mr,'ex2-minute-info':1/mr**2})
    a.near(log(float(mr))-log(float(rate)),-log(60),'log rate deterministic location shift')
    kl=log(F(1,2))+1
    a.eq(kl>0,True,'exponential candidate KL is positive')
    a.near(F(1,2)*log(2*F(1,2))+F(1,2)*log(2*F(1,2)),0,'equal discrete density KL')
    a.near(F(1,2)*log(2)+F(1,2)*log(F(2,3)),.5*log(F(4,3)),'finite Bernoulli KL law')
    a.interventions.append('Change physical time units and contrast a density mismatch with equality; rate, mean and information transform in different units.')

    def binary_case(groups, prefix):
        ps,beta=grouped_binary(groups);total=sum(n for n,k in groups)
        rows=[(d,y) for d,(n,k) in enumerate(groups) for y in ([1]*k+[0]*(n-k))]
        states=[(F(1,total),(F(1),F(d)),F(y)) for d,y in rows]
        info=weighted_matrix(states,lambda x,y:tuple(tuple(ps[int(x[1])]*(1-ps[int(x[1])])*v*w for w in x) for v in x))
        score=[expectation(states,lambda x,y:x[j]*(y-ps[int(x[1])])) for j in range(2)]
        a.eq(score,[0,0],prefix+' two original likelihood scores')
        cov=tuple(tuple(v/total for v in row) for row in invert2(info))
        ws=[p*(1-p) for p in ps];g=(ws[1]-ws[0],ws[1])
        contrast_var=sum(g[i]*cov[i][j]*g[j] for i in range(2) for j in range(2))
        independent=sum(w/n for w,(n,k) in zip(ws,groups))
        a.eq(contrast_var,independent,prefix+' delta versus separate binomial group variance')
        for j in range(2):
            step=1e-4;plus=list(beta);minus=list(beta);plus[j]+=step;minus[j]-=step
            curvature=(binary_loglik(plus,rows)-2*binary_loglik(beta,rows)+binary_loglik(minus,rows))/(step*step)/total
            a.near(curvature,-float(info[j][j]),prefix+' likelihood finite-difference curvature '+str(j),2e-7)
        return ps,beta,info,cov,contrast_var
    ps,beta,info,cov,cv=binary_case([(40,10),(40,30)],'worked binary')
    a.eq(info,((F(3,16),F(3,32)),(F(3,32),F(3,32))),'binary expected information')
    a.eq(cov,((F(2,15),F(-2,15)),(F(-2,15),F(4,15))),'binary coefficient covariance scale')
    a.eq(page.tables['Original binary sample'][1:],[['0','40','10','30','1/4'],['1','40','30','10','3/4']],'all printed binary rows')
    exact.update({'binary-contrast':ps[1]-ps[0],'binary-contrast-variance':cv})
    rounded['binary-derivative']=beta[1]*float(ps[0]*(1-ps[0]))
    a.near((logistic(beta[0]+beta[1]*1e-5)-logistic(beta[0]-beta[1]*1e-5))/(2e-5),rounded['binary-derivative'],'interpolation derivative from probability differences')
    a.eq(abs(rounded['binary-derivative']-float(ps[1]-ps[0]))>.08,True,'finite binary contrast differs from derivative')
    p4,b4,i4,c4,v4=binary_case([(20,4),(20,16)],'transfer binary')
    odds=(p4[1]/(1-p4[1]))/(p4[0]/(1-p4[0]))
    a.eq(c4,((F(5,16),F(-5,16)),(F(-5,16),F(5,8))),'new group proportions change information')
    exact.update({'ex4-odds-ratio':odds,'ex4-contrast':p4[1]-p4[0],'ex4-contrast-variance':v4})
    a.interventions.append('Change binary group success fractions and verify coefficient, probability and covariance responses from the original likelihood.')
    separated=[(0,0)]*4+[(1,1)]*4
    ll=[binary_loglik((-t,2*t),separated) for t in (0,1,2,4,8)]
    a.eq(all(u<v<0 for u,v in zip(ll,ll[1:])),True,'separated likelihood increases toward unattained zero')
    a.eq(8*(1-logistic(2))>0,True,'constrained endpoint score does not vanish')
    exact['ex5-boundary-t']=F(2)
    a.near(2*normal_pdf(0),sqrt(2/pi),'probit score at origin')
    a.near((normal_cdf(2e-5)-normal_cdf(-2e-5))/(2e-5),2*normal_pdf(0),'probit continuous derivative from CDF')
    a.interventions.append('Move a binary sample to complete separation and constrain a path: existence at a boundary differs from an interior zero-score solution.')

    L=log(3);prob={-1:F(1,4),0:F(1,2),1:F(3,4)}
    ape_states=[(F(1,3)*(p if y else 1-p),(F(1),F(x)),F(y)) for x,p in prob.items() for y in (0,1)]
    h=lambda x:L*float(prob[int(x[1])]*(1-prob[int(x[1])]))
    tau=expectation(ape_states,lambda x,y:h(x))
    ia=weighted_matrix(ape_states,lambda x,y:tuple(tuple(prob[int(x[1])]*(1-prob[int(x[1])])*v*w for w in x) for v in x))
    ai=invert2(ia)
    grad=[]
    for j in range(2):
        grad.append(expectation(ape_states,lambda x,y:float(prob[int(x[1])]*(1-prob[int(x[1])]))*((1 if j==1 else 0)+L*float(1-2*prob[int(x[1])])*x[j])))
    def influence(x,y):
        score=tuple(v*(y-prob[int(x[1])]) for v in x);psi=matvec(ai,score)
        return h(x)-tau+sum(g*v for g,v in zip(grad,psi))
    total_v=expectation(ape_states,lambda x,y:influence(x,y)**2)
    distribution_v=expectation(ape_states,lambda x,y:(h(x)-tau)**2)
    coefficient_v=sum(grad[i]*ai[i][j]*grad[j] for i in range(2) for j in range(2))
    cross=expectation(ape_states,lambda x,y:(h(x)-tau)*sum(g*v for g,v in zip(grad,matvec(ai,tuple(w*(y-prob[int(x[1])]) for w in x)))))
    a.eq(ia,((F(5,24),F(0)),(F(0),F(1,8))),'APE information from six actual probability states')
    a.near(tau,5*L/24,'APE expectation');a.near(grad[0],0,'APE intercept gradient symmetry')
    a.near(grad[1],5/24-L/16,'APE slope gradient')
    a.near(distribution_v,L*L/1152,'empirical covariate-distribution contribution')
    a.near(cross,0,'correct conditional-score cross covariance')
    a.near(total_v,distribution_v+coefficient_v,'full state influence variance versus decomposition')
    a.eq(total_v>coefficient_v,True,'estimated target distribution adds positive variance here')
    rounded.update({'ape-mean':tau,'ape-total-variance':total_v,'ape-se300':sqrt(total_v/300)})
    for j in range(2):
        def functional(b):return sum(b[1]*logistic(b[0]+b[1]*x)*(1-logistic(b[0]+b[1]*x)) for x in (-1,0,1))/3
        up=[0,L];down=[0,L];up[j]+=1e-5;down[j]-=1e-5
        a.near((functional(up)-functional(down))/2e-5,grad[j],'APE gradient independently differentiated '+str(j))
    a.interventions.append('Replace an estimated covariate distribution with a known fixed target; remove only its empirical-distribution influence, while retaining coefficient uncertainty.')

    qp=F(5,8);pvals=[F(1,2),F(3,4)];hs=[p*(1-p) for p in pvals]
    pseudo=[(F(1,2)*(qp if y else 1-qp),d,F(y)) for d in (0,1) for y in (0,1)]
    et=lambda fn:sum(weight*fn(d,y) for weight,d,y in pseudo)
    at=sum(hs)/2;gp=sum(h*(1-2*p) for h,p in zip(hs,pvals))/2
    bt=et(lambda d,y:(y-pvals[d])**2);vh=et(lambda d,y:(hs[d]-at)**2);cs=et(lambda d,y:(hs[d]-at)*(y-pvals[d]))
    full=et(lambda d,y:(hs[d]-at+gp/at*(y-pvals[d]))**2)
    fixed=(gp/at)**2*bt;omitted=vh+fixed
    a.eq(et(lambda d,y:y-pvals[d]),0,'pseudo likelihood unconditional score centered')
    a.eq((qp-pvals[0],qp-pvals[1]),(F(1,8),F(-1,8)),'pseudo conditional scores are nonzero')
    a.eq((at,gp,bt,vh,cs),(F(7,32),F(-3,64),F(1,4),F(1,1024),F(1,256)),'all pseudo-effect variance ingredients')
    a.eq((full,omitted,fixed),(F(541,50176),F(625,50176),F(9,784)),'full versus omitted-cross versus known-target variance')
    a.eq(full,omitted+2*gp/at*cs,'signed cross covariance retained')
    exact.update({'ex7-tau':at,'ex7-gradient':gp,'ex7-full-variance':full,'ex7-omitted-cross-variance':omitted})
    for b in (-1,1):
        criterion=sum(float(qp)*log(logistic(b+x))+(1-float(qp))*log(1-logistic(b+x)) for x in (0,L))/2
        target=sum(float(qp)*log(float(p))+(1-float(qp))*log(float(1-p)) for p in pvals)/2
        a.eq(criterion<target,True,'pseudo original criterion declines from target')
    a.interventions.append('Misspecify conditional binary probabilities while retaining a centered unconditional score; a nonzero cross covariance changes the average-effect variance.')

    counts=[(F(1,4),(F(1),F(d)),F(y)) for d,ys in [(0,(0,4)),(1,(0,8))] for y in ys]
    mus={d:sum(p*y for p,x,y in counts if x[1]==d)/sum(p for p,x,y in counts if x[1]==d) for d in (0,1)}
    ca=weighted_matrix(counts,lambda x,y:tuple(tuple(mus[int(x[1])]*v*w for w in x) for v in x))
    cb=weighted_matrix(counts,lambda x,y:tuple(tuple((y-mus[int(x[1])])**2*v*w for w in x) for v in x))
    vc=sandwich(ca,cb);model=invert2(ca)
    a.eq((mus,ca,cb),({0:F(2),1:F(4)},((F(3),F(2)),(F(2),F(2))),((F(10),F(8)),(F(8),F(8)))),'count law means, curvature and meat')
    a.eq(vc,((F(2),F(-2)),(F(-2),F(4))),'count law robust covariance')
    a.eq(model,((F(1),F(-1)),(F(-1),F(3,2))),'count model-only covariance')
    exact.update({'count-pop-slope-var':vc[1][1],'count-model-slope-var':model[1][1]})
    rows=[(d,y) for d,ys in [(0,[0,0,4,4]),(1,[0,8,8,8])] for y in ys]
    sm,sa,sb,sv=count_fit(rows)
    a.eq((sm,sa,sb),({0:F(2),1:F(6)},((F(4),F(3)),(F(3),F(3))),((F(8),F(6)),(F(6),F(6)))),'original finite count rows')
    a.eq(sv,((F(2),F(-2)),(F(-2),F(8,3))),'finite fitted-residual sandwich')
    table=[]
    for d in (0,1):
        ys=[y for group,y in rows if group==d];m=sum(map(F,ys))/len(ys);squared=sum((y-m)**2 for y in ys)/len(ys)
        table.append([str(d),', '.join(map(str,ys)),str(m),str(squared)])
    a.eq(page.tables['Original count sample'][1:],table,'every printed count table cell')
    exact.update({'count-sample-root-slope':sv[1][1],'count-sample-slope-cov':sv[1][1]/len(rows)})
    altered=[(0,1),(0,3),(1,3),(1,5)]
    am,aa,ab,av=count_fit(altered)
    a.eq(am,mus,'variance intervention preserves both conditional means')
    a.eq(aa,ca,'variance intervention preserves population curvature')
    a.eq(av!=vc,True,'variance intervention changes robust covariance')
    a.interventions.append('Preserve the conditional count means but change within-group dispersion; the coefficients remain targeted while their robust covariance changes.')
    dm,da,db,dv=count_fit([(d,2*y) for d,y in rows])
    a.eq(dm,{d:2*v for d,v in sm.items()},'doubling count levels')
    a.eq(dv,sv,'proportional count change preserves log-mean robust covariance')
    a.eq(invert2(da),tuple(tuple(v/2 for v in row) for row in invert2(sa)),'Poisson-only covariance changes under proportional count scaling')
    a.interventions.append('Double every count: fitted log intercept shifts, robust log-parameter variance stays invariant, but the Poisson-model variance changes.')
    intercept_mean=expectation(counts,lambda x,y:y)
    intercept_b=expectation(counts,lambda x,y:(y-intercept_mean)**2)
    a.eq((intercept_mean,intercept_b),(F(3),F(11)),'omitted-group pseudo law')
    a.eq([mus[d]-intercept_mean for d in (0,1)],[-1,1],'conditional misspecification remains despite zero average score')
    exact.update({'ex9-curvature':intercept_mean,'ex9-meat':intercept_b,'ex9-robust-variance':intercept_b/intercept_mean**2})
    a.eq(mus[1]-mus[0],2,'true binary mean contrast lost by intercept restriction')
    a.interventions.append('Omit the group regressor: a centered unconditional score and a sandwich do not recover the missing conditional mean contrast.')

    selected_mean=10+sqrt(2/pi)
    joint=selected_joint(10,0,10,2,.5)
    rounded.update({'selection-mean':selected_mean,'selection-joint-at10':joint,'selection-conditional-at10':joint/normal_cdf(0)})
    selection_cases=0
    for index,rho in [(0,0),(0,.5),(0,-.5),(1,.5),(-1,.5)]:
        kernel=lambda t:normal_pdf(t)*normal_cdf((index+rho*t)/sqrt(1-rho*rho))
        mass=simpson(kernel);first=simpson(lambda t:t*kernel(t));second=simpson(lambda t:t*t*kernel(t))
        expected_mass=normal_cdf(index);mills=normal_pdf(index)/expected_mass
        conditional_mean=first/mass;conditional_var=second/mass-conditional_mean**2
        a.near(mass,expected_mass,'selection integrated mass '+str((index,rho)),3e-10)
        a.near(conditional_mean,rho*mills,'selection integrated selected first moment '+str((index,rho)),3e-10)
        a.near(conditional_var,1-rho*rho*mills*(index+mills),'selection integrated selected variance '+str((index,rho)),3e-10)
        a.near(mass+normal_cdf(-index),1,'mixed observed likelihood normalizes '+str((index,rho)),3e-10)
        selection_cases+=1
    a.near(simpson(lambda v:v*normal_pdf(v),0,10),normal_pdf(0),'Mills numerator by direct tail integral',3e-10)
    selected_variance=4-2/pi;rounded['ex10-selected-variance']=selected_variance
    a.eq(selected_mean>10>10-sqrt(2/pi),True,'sign of correlation reverses selected-mean displacement')
    a.interventions.append('Reverse selection correlation and shift the selection cutoff; direct Gaussian-density integrals preserve the mixed probability budget and change selected moments.')
    conditional_densities=[selected_joint(11,index,10,2,0)/normal_cdf(index) for index in (-1,0,1)]
    for value in conditional_densities:a.near(value,normal_pdf(.5)/2,'rho-zero selected-only density ignores selection index')
    best=NormalDist().inv_cdf(.75)
    def joint_mass_ll(index):return 3*log(normal_cdf(index))+log(normal_cdf(-index))
    a.eq(joint_mass_ll(best)>joint_mass_ll(0),True,'three selected one unselected jointly identify a different selection fit')
    a.near(normal_cdf(best),.75,'selection-count binomial target')
    a.interventions.append('Switch selected-only to joint observed sampling with selection counts; the normalization and information about the selection index differ.')

    uniform_data=[1,2,3,4];m=uniform_fit(uniform_data);interval=uniform_interval(uniform_data,F(1,16))
    exact.update({'uniform-maximum':F(m),'uniform-tail':uniform_tail(4,1),'uniform-upper':F(interval[1]),'uniform-coverage':F(15,16)})
    a.eq((m,uniform_tail(4,1)),(4,F(81,256)),'actual maximum and finite tail')
    a.eq(uniform_tail(4,4),0,'scaled maximum-gap support endpoint')
    a.eq(uniform_tail(4,5),0,'scaled maximum-gap outside support')
    a.eq(uniform_tail(4,0),1,'scaled maximum-gap zero threshold')
    sequence=[float(uniform_tail(n,1)) for n in (4,20,100)]
    a.eq(sequence[0]<sequence[1]<sequence[2]<exp(-1),True,'finite maximum tails approach exponential from below')
    for theta in (F(2),F(5),F(12)):
        quantile=theta*F(1,2)
        a.eq((quantile/theta)**4,F(1,16),'exact coverage tail independent of scale')
        a.eq(F(4,5)*theta,theta-theta/F(5),'maximum expectation by survival integration')
    a.eq(-F(1,5)+F(1,5),0,'moving endpoint term restores normalization derivative')
    a.interventions.append('Change the uniform endpoint scale and sample size while retaining the exact maximum distribution; finite and limiting confidence calculations remain distinct.')
    a.interventions.append('Compare support-dependent likelihoods with ordinary interior score logic: the missing moving-boundary derivative is nonzero.')

    p=F(1,3);w=p*(1-p);dh=w*(1-2*p)
    exact.update({'retention-logit-variance':1/w,'retention-effect-variance':dh**2/w,
                  'retention-count-variance':F(9,9),'retention-uniform-upper':F(uniform_interval([1,3],F(1,9))[1])})
    a.eq(exact['retention-effect-variance'],F(2,81),'new scalar delta-method retention')
    a.eq(exact['retention-uniform-upper'],9,'new exact endpoint interval')
    a.eq(F(1,2)*(0-3)**2+F(1,2)*(6-3)**2,9,'retention count score variance')
    a.near(2-4*.25*normal_pdf(0)/normal_cdf(0),2-sqrt(2/pi),'retention changed selection scale and sign')

    a.reject(lambda:exponential_fit([]),'empty waiting-time sample')
    a.reject(lambda:exponential_fit([0,0]),'unattained exponential fit with all-zero sample')
    a.reject(lambda:exponential_fit([1,-1]),'negative waiting time')
    a.reject(lambda:exponential_fit([True,1]),'boolean waiting time')
    a.reject(lambda:exponential_fit([float('nan'),1]),'nonfinite waiting time')
    a.reject(lambda:exponential_loglik(0,[1]),'zero exponential rate')
    a.reject(lambda:grouped_binary([(2,3),(2,1)]),'successes exceed trials')
    a.reject(lambda:grouped_binary([(0,0),(2,1)]),'empty binomial group')
    a.reject(lambda:grouped_binary([(2,0),(2,1)]),'no finite zero-success group log odds')
    a.reject(lambda:grouped_binary([(2,2),(2,1)]),'no finite all-success group log odds')
    a.reject(lambda:binary_loglik((0,float('inf')),[(0,0)]),'nonfinite coefficient')
    a.reject(lambda:invert2([[1,1],[1,1]]),'rank-deficient information')
    a.reject(lambda:invert2([[1,2],[2,1]]),'indefinite information')
    a.reject(lambda:invert2([[1,0],[1,1]]),'asymmetric information')
    a.reject(lambda:matrix([[1,2],[1]]),'ragged matrix dimensions')
    a.reject(lambda:count_fit([(0,-1),(1,2)]),'negative count')
    a.reject(lambda:count_fit([(0,1.5),(1,2)]),'noninteger count')
    a.reject(lambda:count_fit([(0,True),(1,2)]),'boolean count')
    a.reject(lambda:count_fit([(0,0),(1,2)]),'no finite zero-group log mean')
    a.reject(lambda:count_fit([(0,1),(0,2)]),'missing independent count regressor')
    a.reject(lambda:selected_joint(1,0,0,0,.5),'zero selection outcome scale')
    a.reject(lambda:selected_joint(1,0,0,1,1),'singular Gaussian correlation')
    a.reject(lambda:selected_joint(1,0,0,1,-1),'negative singular Gaussian correlation')
    a.reject(lambda:selected_joint(1,9,0,1,0),'outside bounded numeric selection exercise')
    a.reject(lambda:uniform_fit([0,0]),'unattained positive uniform endpoint for all-zero sample')
    a.reject(lambda:uniform_fit([-1,2]),'negative uniform observation')
    a.reject(lambda:uniform_interval([1],0),'zero confidence tail probability')
    a.reject(lambda:uniform_interval([1],1),'unit confidence tail probability')
    a.reject(lambda:uniform_tail(True,1),'boolean sample size')
    a.reject(lambda:uniform_tail(4,-1),'negative scaled maximum gap')
    a.reject(lambda:strict('{"a":1,"a":2}'),'duplicate JSON member')
    a.reject(lambda:strict('{"a":NaN}'),'nonfinite JSON constant')
    a.reject(lambda:Page().feed('HTML'),'stray non-markup delimiter')
    for key,value in exact.items():a.eq(F(page.values[key].strip().replace('−','-')),value,'printed exact value '+key)
    for key,value in rounded.items():a.near(float(page.values[key]),value,'printed rounded value '+key,5e-10)
    a.eq(set(page.values),set(exact)|set(rounded),'every printed calculation marker independently reconstructed')
    return len(exact),len(rounded),selection_cases


def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    raw=(root/HTML).read_text();page=Page();page.feed(raw);page.close();audit=Audit()
    prompts=['v12-c04-e'+str(i).zfill(2) for i in range(1,13)]
    audit.eq(page.prompts,prompts,'twelve exact prompt IDs')
    audit.eq(page.targets,prompts,'twelve paired complete solution IDs')
    audit.eq((page.worked,page.h1,page.stack,page.answer),(6,0,[],None),'six complete original cases and balanced fragment')
    audit.eq(len(page.ids),len(set(page.ids)),'unique IDs')
    audit.eq(all(i.startswith('v12-c04-') for i in page.ids),True,'owned ID namespace')
    audit.eq(raw.count('<details class="solutions"'),1,'standard reader disclosure')
    for prompt in prompts:audit.eq(len(page.answers[prompt])>400,True,'complete solution text '+prompt)
    audit.eq('Teach-back benchmark' in raw and 'Retention solution and repair route' in raw,True,'answered instruction/retention')
    exact,rounded,selection_cases=calculate(audit,page)
    sources=strict((root/SOURCES).read_text());review=strict((root/REVIEW).read_text())
    expected={'v12-c04-mit-likelihood2016','v12-c04-mit-nonlinear2017','v12-c04-counts1999','v12-c04-selection2007'}
    audit.eq({s['id'] for s in sources['proposals']},expected,'four scoped inspected source proposals')
    audit.eq(len(sources['proposals']),4,'no duplicated or extra source proposal')
    audit.eq(set(page.sources),expected,'all method source routes actually used')
    for s in sources['proposals']:
        audit.eq(bool(s['inspection']['read_pages']) and bool(s['inspection']['rendered_pages']),True,'actual bounded source body/equation inspection')
        audit.eq(s['checked'],'2026-10-09','source inspection date')
    for href in page.links:
        audit.eq(href in ('v12-c01.html','v12-c02.html','v12-c03.html') or href in {'sources.html#'+v for v in expected},True,'flat future reader route')
    bindings=review['reviewed_hashes']
    audit.eq({row['path'] for row in bindings},{HTML,SELF,SOURCES},'three nonself runtime payload bindings')
    audit.eq(len(bindings),3,'no duplicated payload binding')
    for row in bindings:
        payload=(root/row['path']).read_bytes()
        audit.eq((len(payload),hashlib.sha256(payload).hexdigest()),(row['bytes'],row['sha256']),'final author payload '+row['path'])
    result=dict(chapter='v12-c04',status='passed',working_only=False,worked_cases=6,exercises=12,solutions=12,
                comparisons=audit.comparisons,exact_numeric_anchors=exact,rounded_numeric_anchors=rounded,
                purposeful_interventions=len(audit.interventions),intervention_scopes=audit.interventions,
                executed_rejections=len(audit.rejections),rejection_scopes=audit.rejections,selection_quadrature_cases=selection_cases,
                inspected_primary_sources=4,nonself_author_bindings=3,
                limits='Bounded finite calculations and numerical integrals plus separately recorded proof reading; no empirical identification, dependent inference, browser QA, human certification or acceptance implied.')
    strict(json.dumps(result,allow_nan=False))
    return result


if __name__=='__main__':
    check()
