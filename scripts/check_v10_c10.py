"""Independent bounded numerical-pricing audit. check() is quiet and JSON-safe."""
from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
from fractions import Fraction
from hashlib import sha256
from html.parser import HTMLParser
from io import StringIO
import cmath
import itertools
import json
import math
from pathlib import Path
import runpy
import shutil
from statistics import NormalDist
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT/'content/projects'


def require(condition, message):
    if not condition:
        raise AssertionError(message)


class Audit:
    def __init__(self):
        self.comparisons = 0
        self.rejections = 0
        self.groups = []

    def eq(self, actual, expected, label):
        self.comparisons += 1
        require(actual == expected, label+': '+repr(actual)+' != '+repr(expected))

    def near(self, actual, expected, label, absolute=3e-10, relative=2e-11):
        self.comparisons += 1
        require(type(actual) in (int, float) and math.isfinite(actual), label+': nonfinite result')
        require(abs(actual-expected) <= absolute+relative*abs(expected),
                label+': '+repr(actual)+' != '+repr(expected))

    def true(self, condition, label):
        self.comparisons += 1
        require(condition, label)


def simpson(f, low, high, panels):
    if low >= high:
        return 0.0
    h = (high-low)/panels
    return h/3*(f(low)+f(high)+4*math.fsum(f(low+j*h) for j in range(1, panels, 2))
                +2*math.fsum(f(low+j*h) for j in range(2, panels, 2)))


def payoff_integrals(market, panels=8192):
    """Direct positive payoff integrals and raw cross moments, without a normal CDF."""
    s, k, r, q, sig, t = market
    d, w = math.exp(-r*t), sig*math.sqrt(t)
    m = math.log(s)+(r-q-sig*sig/2)*t
    cutoff = min(12.0, max(-12.0, (math.log(k)-m)/w))
    def density(z):
        return math.exp(-z*z/2)/math.sqrt(2*math.pi)
    def stock(z):
        return math.exp(m+w*z)
    put = simpson(lambda z:d*(k-stock(z))*density(z), -12, cutoff, panels)
    call = simpson(lambda z:d*(stock(z)-k)*density(z), cutoff, 12, panels)
    ey2 = simpson(lambda z:d*d*(k-stock(z))**2*density(z), -12, cutoff, panels)
    eyx = simpson(lambda z:d*d*(k-stock(z))*stock(z)*density(z), -12, cutoff, panels)
    ex = simpson(lambda z:d*stock(z)*density(z), -12, 12, panels)
    ex2 = simpson(lambda z:d*d*stock(z)**2*density(z), -12, 12, panels)
    return {'call': call, 'put': put, 'var_y': ey2-put*put, 'var_x': ex2-ex*ex,
            'cov_yx': eyx-put*ex, 'ex': ex}


def normal_put(s, k, r, q, sig, t):
    if t == 0:
        return max(k-s, 0)
    w = sig*math.sqrt(t)
    z = (math.log(k/s)-(r-q-sig*sig/2)*t)/w
    n = NormalDist()
    return k*math.exp(-r*t)*n.cdf(z)-s*math.exp(-q*t)*n.cdf(z-w)


def terminal_sum(market, n):
    s, k, r, q, sig, t = market
    u = math.exp(sig*math.sqrt(t/n))
    p = (math.exp((r-q)*t/n)-1/u)/(u-1/u)
    rows = [(math.comb(n,j)*p**j*(1-p)**(n-j), s*u**(2*j-n)) for j in range(n+1)]
    d = math.exp(-r*t)
    return (d*math.fsum(prob*max(k-stock,0) for prob,stock in rows),
            d*math.fsum(prob*max(stock-k,0) for prob,stock in rows),
            math.fsum(prob*stock for prob,stock in rows), p)


def enumerate_policies(market, n, stride):
    """Enumerate all Markov exercise maps on a small recombining tree, then paths."""
    s, k, r, q, sig, t = market
    u = math.exp(sig*math.sqrt(t/n))
    p = (math.exp((r-q)*t/n)-1/u)/(u-1/u)
    decision_nodes = [(i,j) for i in range(n) if i % stride == 0 for j in range(i+1)]
    all_paths = list(itertools.product((0,1), repeat=n))
    best = -math.inf
    for mask in range(1 << len(decision_nodes)):
        exercise = {node for b,node in enumerate(decision_nodes) if mask & (1 << b)}
        value = 0.0
        for path in all_paths:
            probability = p**sum(path)*(1-p)**(n-sum(path))
            ups = 0
            for i in range(n+1):
                if i == n or (i,ups) in exercise:
                    receipt = math.exp(-r*t*i/n)*max(k-s*u**(2*ups-i),0)
                    break
                ups += path[i]
            value += probability*receipt
        best = max(best, value)
    return best, 1 << len(decision_nodes)


def walk_oracle(market, half_width, m, n, mode, start=None):
    """Forward propagation of a killed Markov walk, not backward price-array updating."""
    s, k, r, q, sig, t = market
    h, dt = 2*half_width/m, t/n
    a, b = sig*sig/2, r-q-sig*sig/2
    moves = ((-1,dt*(a/h**2-b/(2*h))), (0,1-2*a*dt/h**2), (1,dt*(a/h**2+b/(2*h))))
    def value(j, remaining):
        x, tau = -half_width+j*h, remaining*dt
        if mode == 'manufactured':
            return math.exp(1.3*x+(a*1.3**2+b*1.3)*tau)
        stock = s*math.exp(x)
        if mode == 'asymptotic' and remaining:
            return max(k-stock*math.exp((r-q)*tau),0) if j == 0 else 0.0
        return math.exp(r*tau)*normal_put(stock,k,r,q,sig,tau)
    start = m//2 if start is None else start
    if start in (0,m):
        return value(start,n)
    mass, paid = {start:1.0}, 0.0
    for remaining in range(n-1, -1, -1):
        following = {}
        for j,prob in mass.items():
            for step,weight in moves:
                dest = j+step
                flow = prob*weight
                if dest in (0,m):
                    paid += flow*value(dest,remaining)
                else:
                    following[dest] = following.get(dest,0.0)+flow
        mass = following
    return paid+math.fsum(prob*value(j,0) for j,prob in mass.items())


def independent_samples(market, settings):
    s, k, r, q, sig, t = market
    d, ex = math.exp(-r*t), s*math.exp(-q*t)
    beta = settings['control_beta']
    samples = {name:[] for name in ('plain','fixed_control','antithetic','antithetic_fixed_control')}
    normal, stocks, first = [], [], []
    def observation(z):
        terminal = s*math.exp((r-q-sig*sig/2)*t+sig*math.sqrt(t)*z)
        return d*max(k-terminal,0), d*terminal
    for i in range(settings['pairs']):
        encoded = f"v10-c10:{settings['seed']}:{i}".encode('ascii')
        hexed = sha256(encoded).hexdigest()
        uniform = [min(((int(hexed[j:j+16],16)//2048)+.5)/9007199254740992,
                       math.nextafter(1.0,0)) for j in (0,16)]
        normal_complex = cmath.rect(math.sqrt(-2*math.log(uniform[0])), math.tau*uniform[1])
        z1,z2 = normal_complex.real,normal_complex.imag
        if i < 3:
            first.append([z1,z2])
        normal.extend((z1,z2))
        for z in (z1,z2):
            y,x = observation(z)
            stocks.append(x)
            samples['plain'].append(y)
            samples['fixed_control'].append(y-beta*(x-ex))
        ya,xa = observation(z1)
        yb,xb = observation(-z1)
        samples['antithetic'].append((ya+yb)/2)
        samples['antithetic_fixed_control'].append((ya+yb-beta*(xa+xb-2*ex))/2)
    summaries = {}
    for name,series in samples.items():
        # Online Welford recurrence, independent of the model's two-pass fsum.
        mean,m2 = 0.0,0.0
        for count,x in enumerate(series,1):
            difference = x-mean
            mean += difference/count
            m2 += difference*(x-mean)
        summaries[name] = (len(series),mean,m2/(len(series)-1))
    return summaries, first, normal, stocks


class Fragment(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack,self.ids,self.hrefs = [],[],[]
        self.worked = self.exercises = self.solutions = 0
    def handle_starttag(self,tag,attrs):
        a = dict(attrs)
        require(tag not in ('html','head','body','h1','script'), 'static chapter fragment required')
        if 'id' in a:
            self.ids.append(a['id'])
        if 'href' in a:
            self.hrefs.append(a['href'])
        if tag == 'aside' and 'worked' in a.get('class','').split():
            self.worked += 1
        if tag == 'li' and self.stack and self.stack[-1][0] == 'ol':
            if 'exercises' in self.stack[-1][1].get('class','').split():
                self.exercises += 1
            if any(t == 'details' and 'solutions' in at.get('class','').split() for t,at in self.stack):
                self.solutions += 1
        if tag not in ('br','hr','img','meta','link','input'):
            self.stack.append((tag,a))
    def handle_endtag(self,tag):
        require(self.stack and self.stack[-1][0] == tag, 'unbalanced HTML: '+tag)
        self.stack.pop()


def check():
    audit = Audit()
    data = json.loads((ASSETS/'v10-c10-inputs.json').read_text())
    saved = json.loads((ASSETS/'v10-c10-output.json').read_text())
    original = deepcopy(data)
    buffer = StringIO()
    with redirect_stdout(buffer),redirect_stderr(buffer):
        module = runpy.run_path(str(ASSETS/'v10-c10-analysis.py'))
        result = module['run'](data)
    audit.eq(buffer.getvalue(), '', 'quiet import and run')
    audit.eq(data, original, 'nonmutating input')
    audit.eq(result, saved, 'entire reference output')
    json.dumps(result,allow_nan=False)
    market = tuple(data['market'][x] for x in ('spot','strike','rate','dividend_yield','volatility','maturity'))
    s,k,r,q,sig,t = market
    fine,coarse = payoff_integrals(market),payoff_integrals(market,4096)
    for name in fine:
        audit.near(fine[name],coarse[name],'quadrature refinement '+name,absolute=2e-7,relative=0)
    for name in ('call','put'):
        audit.near(result['analytic']['european_'+name],fine[name],'independent direct payoff '+name,absolute=2e-8)
    ideals = result['monte_carlo']['ideal_analytic']
    mapping = {'put_mean':'put','put_variance':'var_y','discounted_stock_variance':'var_x',
               'put_stock_covariance':'cov_yx','discounted_stock_mean':'ex'}
    for key,oracle in mapping.items():
        audit.near(ideals[key],fine[oracle],'direct moment integral '+key,absolute=3e-7)
    beta = data['monte_carlo']['control_beta']
    audit.near(ideals['optimal_beta'],fine['cov_yx']/fine['var_x'],'optimal raw coefficient',absolute=1e-9)
    audit.near(ideals['fixed_control_variance'],fine['var_y']+beta*beta*fine['var_x']-2*beta*fine['cov_yx'],
               'controlled variance from independent moments',absolute=6e-7)
    audit.groups.append('direct lognormal payoff and moment quadrature with refinement, analytic control variance')

    for row in result['tree']:
        ep,ec,mean,p = terminal_sum(market,row['steps'])
        audit.near(row['european_put'],ep,'binomial terminal sum put')
        audit.near(row['european_call'],ec,'binomial terminal sum call')
        audit.near(mean,s*math.exp((r-q)*t),'tree exact terminal mean')
        audit.near(row['probability_up'],p,'pricing probability')
        audit.near(row['up']*row['down'],1,'recombination')
        audit.near(row['parity_residual'],0,'European parity')
        audit.near(row['european_put_error'],ep-fine['put'],'tree oracle error',absolute=2e-8)
        audit.true(ep-1e-10 <= row['bermudan_put'] <= row['all_grid_dates_put']+1e-10,'same-law exercise inclusion')
    quick = deepcopy(data)
    quick['tree']={'steps':[4], 'exercise_stride':2}
    quick['finite_difference']['grids']=[{'space_steps':40,'time_steps':100}]
    quick['monte_carlo']['pairs']=64
    small = module['run'](quick)['tree'][0]
    american,policy_count = enumerate_policies(market,4,1)
    bermudan,coarse_policy_count = enumerate_policies(market,4,2)
    audit.eq(policy_count,1024,'all small-tree Markov exercise maps')
    audit.eq(coarse_policy_count,16,'coarse-date exercise maps')
    audit.near(small['all_grid_dates_put'],american,'exhaustive policy American oracle')
    audit.near(small['bermudan_put'],bermudan,'exhaustive policy Bermudan oracle')
    values=[]
    for stride in (1,4,24):
        altered=deepcopy(quick)
        altered['tree']={'steps':[24],'exercise_stride':stride}
        row=module['run'](altered)['tree'][0]
        values.append(row['bermudan_put'])
        if stride == 1:
            audit.near(row['bermudan_put'],row['all_grid_dates_put'],'full exercise stride')
        if stride == 24:
            audit.near(row['bermudan_put'],max(k-s,row['european_put']),'root and terminal only')
    audit.true(values[0] >= values[1] >= values[2],'fixed law exercise-stride intervention')
    audit.groups.append('independent binomial expectations and exhaustive finite adapted exercise-policy enumeration')

    width=data['finite_difference']['log_half_width']
    for row in result['finite_difference']:
        m,n=row['space_steps'],row['time_steps']
        h,dt=2*width/m,t/n
        a,b=sig*sig/2,r-q-sig*sig/2
        weights=(dt*(a/h**2-b/(2*h)),1-2*a*dt/h**2,dt*(a/h**2+b/(2*h)))
        for actual,expected in zip(row['weights'],weights):
            audit.near(actual,expected,'stencil coefficient')
        audit.true(min(row['weights']) >= 0,'stencil positivity')
        audit.near(sum(row['weights']),1,'stencil mass')
        for mode,key in (('exact','put_exact_boundary'),('asymptotic','put_asymptotic_boundary')):
            oracle=math.exp(-r*t)*walk_oracle(market,width,m,n,mode)
            audit.near(row[key],oracle,'killed random-walk '+key,absolute=2e-9)
        audit.near(row['exact_boundary_put_error'],row['put_exact_boundary']-fine['put'],'FD oracle error',absolute=2e-8)
        audit.true(abs(row['boundary_effect']) <= row['discrete_boundary_effect_bound']+2e-11,'boundary perturbation theorem')
        kap=1.3;theta=a*kap*kap+b*kap
        maximum=math.exp(kap*width+max(theta*t,0))
        bound=t*maximum*(dt*theta*theta/2+h*h*(a*kap**4/12+abs(b)*kap**3/6))
        audit.near(row['manufactured_global_bound'],bound,'smooth residual theorem constants')
        audit.true(0 < row['manufactured_max_error'] <= bound+1e-11,'manufactured solution global error bound')
    row=result['finite_difference'][0];m,n=row['space_steps'],row['time_steps']
    theta=sig*sig/2*1.3**2+(r-q-sig*sig/2)*1.3
    independent_max=max(abs(walk_oracle(market,width,m,n,'manufactured',j)-math.exp(1.3*(-width+2*width*j/m)+theta*t))
                        for j in range(m+1))
    audit.near(row['manufactured_max_error'],independent_max,'full coarse manufactured error from stopped walks',absolute=2e-11)
    narrow=deepcopy(quick)
    narrow['market']['volatility']=.4
    narrow['finite_difference']={'log_half_width':.8,'grids':[{'space_steps':80,'time_steps':800}]}
    narrow_result=module['run'](narrow);nr=narrow_result['finite_difference'][0]
    narrow_market=list(market);narrow_market[4]=.4
    for mode,key in (('exact','put_exact_boundary'),('asymptotic','put_asymptotic_boundary')):
        audit.near(nr[key],math.exp(-r*t)*walk_oracle(narrow_market,.8,80,800,mode),'narrow-boundary independent walk',absolute=2e-9)
    audit.true(nr['boundary_effect'] < -.01,'finite boundary error exposed')
    audit.true(abs(nr['boundary_effect']) <= nr['discrete_boundary_effect_bound'],'narrow-domain difference bounded')
    audit.groups.append('killed random-walk PDE oracle, full manufactured maximum error, stability and boundary interventions')

    samples,first,zs,xs=independent_samples(market,data['monte_carlo'])
    mc=result['monte_carlo']
    for pair_a,pair_b in zip(mc['first_three_normal_pairs'],first):
        for za,zb in zip(pair_a,pair_b):
            audit.near(za,zb,'independent digest/complex-polar stream reconstruction')
    audit.near(mc['normal_sample_mean'],math.fsum(zs)/len(zs),'normal mean diagnostic')
    audit.near(mc['normal_sample_second_moment'],math.fsum(z*z for z in zs)/len(zs),'normal second moment diagnostic')
    audit.near(mc['discounted_stock_sample_mean'],math.fsum(xs)/len(xs),'sample control mean')
    for name,(count,mean,var) in samples.items():
        actual=mc[name]
        audit.eq(actual['units'],count,'independent estimator units '+name)
        audit.near(actual['mean'],mean,'independent Welford mean '+name)
        audit.near(actual['sample_variance'],var,'independent Welford variance '+name)
        se=math.sqrt(var/count)
        audit.near(actual['standard_error'],se,'correct unit standard error '+name)
        for actual_edge,sign in zip(actual['clt95_interval'],(-1,1)):
            audit.near(actual_edge,mean+sign*1.959963984540054*se,'CLT interval '+name)
        if 'control' in name:
            audit.eq(actual['hoeffding_half_width'],None,'unbounded control has no put Hoeffding claim')
        else:
            radius=k*math.exp(-r*t)*math.sqrt(math.log(2/data['monte_carlo']['alpha'])/(2*count))
            audit.near(actual['hoeffding_half_width'],radius,'bounded independent-unit concentration')
    audit.true(mc['antithetic_fixed_control']['standard_error'] > mc['antithetic']['standard_error'],
               'combined raw control does not improve this pair estimator')
    reference_quick=module['run'](quick)
    for new_beta in (0,1):
        altered=deepcopy(quick);altered['monte_carlo']['control_beta']=new_beta
        out=module['run'](altered)['monte_carlo']
        if new_beta == 0:
            for a1,a2 in (('fixed_control','plain'),('antithetic_fixed_control','antithetic')):
                for key in ('mean','sample_variance','standard_error','units','clt95_interval'):
                    audit.eq(out[a1][key],out[a2][key],'zero coefficient identity '+key)
        else:
            audit.true(out['ideal_analytic']['fixed_control_variance'] > out['ideal_analytic']['put_variance'],
                       'wrong-sign control worsens raw variance')
    altered=deepcopy(quick);altered['monte_carlo']['seed']=0
    shifted=module['run'](altered)
    for key in ('analytic','tree','finite_difference'):
        audit.eq(shifted[key],reference_quick[key],'seed cannot affect deterministic target '+key)
    audit.true(shifted['monte_carlo']['plain']['mean'] != reference_quick['monte_carlo']['plain']['mean'], 'seed actually changes sample')
    altered=deepcopy(quick);altered['monte_carlo']['alpha']=.1
    change_alpha=module['run'](altered)['monte_carlo']
    audit.eq(change_alpha['plain']['clt95_interval'],reference_quick['monte_carlo']['plain']['clt95_interval'],'CLT always 95 percent')
    audit.true(change_alpha['plain']['hoeffding_half_width'] < reference_quick['monte_carlo']['plain']['hoeffding_half_width'],'alpha changes bounded guarantee')
    for parameter,value,direction in (('dividend_yield',.05,1),('volatility',.35,1),('rate',.08,-1)):
        altered=deepcopy(quick);altered['market'][parameter]=value
        changed=module['run'](altered)
        pvec=tuple(altered['market'][x] for x in ('spot','strike','rate','dividend_yield','volatility','maturity'))
        oracle=payoff_integrals(pvec,4096)
        audit.near(changed['analytic']['european_put'],oracle['put'],'financial perturbation direct integral '+parameter,absolute=1e-7)
        audit.true(direction*(changed['analytic']['european_put']-result['analytic']['european_put']) > 0,'economic direction '+parameter)
    for new_market,grid in ((dict(spot=20,strike=40,rate=-.05,dividend_yield=.12,volatility=.6,maturity=2),
                             {'space_steps':40,'time_steps':200}),
                            (dict(spot=200,strike=100,rate=.15,dividend_yield=0,volatility=.1,maturity=.25),
                             {'space_steps':80,'time_steps':100})):
        edge=deepcopy(quick);edge['market']=new_market
        edge['tree']={'steps':[24],'exercise_stride':4}
        edge['finite_difference']['grids']=[grid]
        edge['monte_carlo'].update(seed=2**32-1,pairs=32,control_beta=2,alpha=.001)
        er=module['run'](edge)
        pvec=tuple(new_market[x] for x in ('spot','strike','rate','dividend_yield','volatility','maturity'))
        oracle=payoff_integrals(pvec)
        for option in ('call','put'):
            audit.near(er['analytic']['european_'+option],oracle[option],'bounded-domain edge payoff '+option,absolute=2e-8)
        audit.true(er['analytic']['european_put'] >= 0,'nonnegative edge put')
        audit.true(er['finite_difference'][0]['manufactured_max_error'] <= er['finite_difference'][0]['manufactured_global_bound']+1e-11,
                   'domain-edge smooth error theorem')
        audit.eq(er['monte_carlo']['plain']['units'],64,'minimum bounded sample at maximal seed')
        json.dumps(er,allow_nan=False)
    audit.groups.append('independent seed/sample reconstruction, estimator units, financial and variance-reduction interventions')

    # Exact authored exercise arithmetic, independent of the pricing implementation.
    F=Fraction;p=F(8,15);account=F(26,25)
    for strike,expected_e,expected_a in ((84,F(12845,1521),F(15050,1521)),(88,F(16870,1521),F(19180,1521))):
        terminal=[max(F(strike)-v,0) for v in (F(256,5),F(80),F(125))]
        continuation=[((1-p)*terminal[j]+p*terminal[j+1])/account for j in range(2)]
        exercise=[max(F(strike)-stock,v) for stock,v in zip((F(64),F(100)),continuation)]
        audit.eq(((1-p)*continuation[0]+p*continuation[1])/account,expected_e,'exact tree exercise European')
        audit.eq(((1-p)*exercise[0]+p*exercise[1])/account,expected_a,'exact tree exercise stopping')
    audit.eq(F(12,1000)/18,F(1,1500),'implied volatility sensitivity bound')
    audit.eq(4*F(12,1000)/F(1,5)**2,F(6,5),'gamma oracle-error amplification')
    for step,expected in ((F(1,5),F(1,5)),(F(3,10),F(-1,5))):
        audit.eq(1-2*F(2,100)*step/F(1,10)**2,expected,'stencil counterexample')
    residual=F(1,1000)*3/2+F(2,100)*F(2,100)**2*20/12+F(1,100)*F(2,100)**2*5/6
    audit.eq(F(4,10000)+residual,F(23,12000),'smooth theorem exercise bound')
    audit.near(.006*math.exp(.06),.006371019279,'negative-rate boundary conversion',absolute=1e-12)
    audit.eq(math.ceil(5000*math.log(40)),18445,'Hoeffding planning size')
    audit.eq(math.ceil((1.959963984540054*16)**2),984,'CLT planning size')
    for coefficient,expected in ((F(-8,5),36),(-1,45),(1,205)):
        audit.eq(100+coefficient**2*25+80*coefficient,expected,'control exercise variance')
    audit.eq(sum(F(x,4) for x in (5,5,0,6)),4,'optimal feasible toy policy')
    audit.eq(sum(F(x,4) for x in (0,8,0,6)),F(7,2),'waiting policy')
    audit.eq(sum(F(x,4) for x in (5,8,1,6)),5,'hindsight upper bound')
    audit.eq(F(1,4)**4,F(1,256),'no pathwise lower bound event')
    audit.eq(F(1,100)/(2*F(5,100)),F(1,10),'retention CFL')
    audit.eq(4*2500,10000,'retention square-root scaling')
    audit.groups.append('exact worked/solved arithmetic, error and confidence bounds, policy and counterexample checks')

    failures=[]
    def bad(path,value):
        x=deepcopy(quick);node=x
        for key in path[:-1]:
            node=node[key]
        node[path[-1]]=value;failures.append(x)
    for value in (True,1.0,2):
        bad(('schema_version',),value)
    for value in (True,float('nan'),float('inf'),-float('inf'),10**1000,'96',None):
        bad(('market','spot'),value)
    for key,value in (('spot',0),('strike',201),('rate',.151),('dividend_yield',-.001),('volatility',0),('maturity',0)):
        bad(('market',key),value)
    bad(('market','spot'),20)
    for value in ([],[4,4],[4,2],[3],[True],[4.0],[258],[2,4,6,8,10,12,14]):
        bad(('tree','steps'),value)
    for value in (0,True,33,3):
        bad(('tree','exercise_stride'),value)
    bad(('finite_difference','log_half_width'),.59)
    bad(('finite_difference','grids'),[])
    for grid in ({'space_steps':41,'time_steps':100},{'space_steps':40,'time_steps':4},
                 {'space_steps':202,'time_steps':100},{'space_steps':40,'time_steps':10001},
                 {'space_steps':True,'time_steps':100},{'space_steps':40,'time_steps':100,'extra':0}):
        bad(('finite_difference','grids'),[grid])
    bad(('finite_difference','grids'),[{'space_steps':180,'time_steps':8000},{'space_steps':200,'time_steps':10000}])
    for key,value in (('seed',-1),('seed',2**32),('seed',True),('pairs',31),('pairs',16385),('pairs',64.0),
                      ('control_beta',2.01),('alpha',0),('alpha',.201)):
        bad(('monte_carlo',key),value)
    x=deepcopy(quick);x['market'].update(rate=.15,dividend_yield=0,volatility=.1,maturity=2)
    x['tree']={'steps':[2],'exercise_stride':1};failures.append(x)
    x=deepcopy(quick);x['market'].update(rate=.15,dividend_yield=0,volatility=.1)
    x['tree']={'steps':[24],'exercise_stride':4};x['finite_difference']['grids']=[{'space_steps':8,'time_steps':100}];failures.append(x)
    x=deepcopy(quick);x['market'].update(spot=50,strike=100);x['finite_difference']['log_half_width']=.6;failures.append(x)
    x=deepcopy(quick);x['market']['extra']=0;failures.append(x)
    x=deepcopy(quick);del x['tree'];failures.append(x)
    failures.extend(([],None,True))
    for index,x in enumerate(failures):
        try:
            module['run'](x)
        except ValueError:
            audit.rejections += 1
        else:
            raise AssertionError('accepted invalid input '+str(index))
    audit.groups.append('strict nested, Boolean/nonfinite, financial-invariant, mesh stability and work-budget rejections')

    with tempfile.TemporaryDirectory(prefix='v10-c10-check-') as directory:
        dest=Path(directory)
        shutil.copy2(ASSETS/'v10-c10-analysis.py',dest/'model.py')
        shutil.copy2(ASSETS/'v10-c10-inputs.json',dest/'inputs.json')
        for optimized in (False,True):
            prefix=[sys.executable]+(['-O'] if optimized else [])
            output=dest/('optimized.json' if optimized else 'normal.json')
            proc=subprocess.run(prefix+[str(dest/'model.py'),'--input',str(dest/'inputs.json'),'--output',str(output)],
                                cwd=dest,capture_output=True,text=True,timeout=30)
            audit.eq(proc.returncode,0,'portable CLI status')
            audit.eq((proc.stdout,proc.stderr),('',''),'quiet portable CLI')
            audit.eq(json.loads(output.read_text()),result,'portable CLI numerical payload')
            code="import contextlib,io,json,runpy; b=io.StringIO();\nwith contextlib.redirect_stdout(b),contextlib.redirect_stderr(b):\n m=runpy.run_path('model.py'); d=json.load(open('inputs.json')); before=json.dumps(d,sort_keys=True); r=m['run'](d)\nif b.getvalue() or before!=json.dumps(d,sort_keys=True): raise RuntimeError('API noise/mutation')\nprint(json.dumps(r,allow_nan=False))"
            api=subprocess.run(prefix+['-c',code],cwd=dest,capture_output=True,text=True,timeout=30)
            audit.eq(api.returncode,0,'portable API status')
            audit.eq(api.stderr,'','portable API stderr')
            audit.eq(json.loads(api.stdout),result,'portable API result')
            for text_input in ('{"schema_version":1,"schema_version":1}',
                               '{"schema_version":NaN}', '{"schema_version":Infinity}',
                               '{"schema_version":-Infinity}', '{', ' '*65537):
                (dest/'bad.json').write_text(text_input)
                invalid=subprocess.run(prefix+[str(dest/'model.py'),'--input',str(dest/'bad.json'),'--output',str(dest/'never.json')],
                                       cwd=dest,capture_output=True,text=True,timeout=5)
                require(invalid.returncode != 0 and not (dest/'never.json').exists(),'invalid CLI must not write a result')
                audit.rejections += 1
    audit.groups.append('isolated normal/optimized explicit CLI and quiet API, strict JSON token/duplicate rejection')

    text=(ROOT/'content/chapters/v10-c10.html').read_text()
    fragment=Fragment();fragment.feed(text);fragment.close()
    audit.eq(fragment.stack,[],'balanced static fragment')
    audit.eq((fragment.worked,fragment.exercises,fragment.solutions),(4,12,12),'complete instructional counts')
    audit.eq(len(fragment.ids),len(set(fragment.ids)),'unique anchors')
    for n in range(1,13):
        audit.true('exercise-'+str(n) in fragment.ids and 'solution-'+str(n) in fragment.ids,'prompt/solution anchors')
    proposals=json.loads((ROOT/'content/reviews/v10-c10-sources.json').read_text())['proposals']
    audit.eq({h.split('#',1)[1] for h in fragment.hrefs if h.startswith('sources.html#')},
             {x['id'] for x in proposals},'scoped source links')
    names={'v10-c10-inputs.json','v10-c10-analysis.py','v10-c10-output.json','v10-c10-README.txt'}
    for name in names|{'v10-c10-manifest.json'}:
        audit.true(name in fragment.hrefs,'flat standalone link '+name)
    manifest=json.loads((ASSETS/'v10-c10-manifest.json').read_text())
    audit.eq({x['file'] for x in manifest['files']},names,'four manifest payloads')
    for entry in manifest['files']:
        payload=(ASSETS/entry['file']).read_bytes()
        audit.eq(len(payload),entry['bytes'],'manifest size')
        audit.eq(sha256(payload).hexdigest(),entry['sha256'],'manifest integrity')
    author=ROOT/'content/reviews/v10-c10-author.json'
    bound=0
    if author.exists():
        entries=json.loads(author.read_text())['reviewed_hashes']
        expected={'content/chapters/v10-c10.html','scripts/check_v10_c10.py','content/reviews/v10-c10-sources.json'}
        expected|={'content/projects/'+name for name in names|{'v10-c10-manifest.json'}}
        require(len(entries)==8 and {x['path'] for x in entries} == expected,'author must bind eight nonself payloads')
        for entry in entries:
            payload=(ROOT/entry['path']).read_bytes()
            require(len(payload)==entry['bytes'] and sha256(payload).hexdigest()==entry['sha256'],'stale author binding '+entry['path'])
            bound += 1
    audit.groups.append('complete HTML/prompts/solutions, source scope, flat links and frozen payload integrity')
    return {'chapter':'v10-c10','status':'passed','independent_comparisons':audit.comparisons,
            'invalid_inputs_rejected':audit.rejections,'worked_examples':4,'solved_exercises':12,
            'enumerated_small_tree_policies':policy_count+coarse_policy_count,
            'author_payload_hashes_verified':bound,'groups':audit.groups,
            'limits':'Author checks, not independent peer/human certification or empirical model validation. Numerical tests do not prove tree/LSM convergence, nonsmooth PDE rates, random-stream independence or interval coverage.'}


if __name__ == '__main__':
    print(json.dumps(check(),indent=2,allow_nan=False))
