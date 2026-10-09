"""Separate c10 peer audit: adaptive integrals, spectral PDE oracle and stopping policies."""
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
from decimal import Decimal, localcontext
from fractions import Fraction
from hashlib import sha256
from html.parser import HTMLParser
from io import StringIO
import json
import math
from pathlib import Path
import runpy
import shutil
import statistics
import struct
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
ASSETS=ROOT/'content/projects'
AUTHOR_PATHS=['content/chapters/v10-c10.html']+[
    'content/projects/v10-c10'+suffix for suffix in ('-inputs.json','-analysis.py','-output.json','-manifest.json','-README.txt')]+[
    'scripts/check_v10_c10.py','content/reviews/v10-c10-sources.json','content/reviews/v10-c10-author.json']


def require(condition,label):
    if not condition: raise AssertionError(label)


class Audit:
    def __init__(self): self.comparisons=0; self.rejections=0; self.policies=0; self.interventions=[]
    def eq(self,x,y,label):
        self.comparisons+=1
        require(x==y,f'{label}: {x!r} != {y!r}')
    def near(self,x,y,label,atol=2e-9,rtol=2e-10):
        self.comparisons+=1
        require(type(x) in (int,float) and math.isfinite(x),label+': nonfinite')
        require(abs(x-y)<=atol+rtol*abs(y),f'{label}: {x!r} != {y!r}')
    def true(self,test,label):
        self.comparisons+=1; require(test,label)
    def reject(self,fn,label):
        try: fn()
        except ValueError: self.rejections+=1
        else: raise AssertionError(label+': accepted invalid input')


def adapt(f,a,b,tolerance=1e-9):
    """Adaptive Simpson with explicit depth bound; numerical oracle, not interval proof."""
    if a>=b: return 0.0
    def recur(a,b,fa,fb,fm,whole,budget,depth):
        mid=(a+b)/2; l=(a+mid)/2; r=(mid+b)/2
        fl,fr=f(l),f(r)
        left=(mid-a)*(fa+4*fl+fm)/6; right=(b-mid)*(fm+4*fr+fb)/6
        delta=left+right-whole
        if abs(delta)<=15*budget or depth==0: return left+right+delta/15
        return recur(a,mid,fa,fm,fl,left,budget/2,depth-1)+recur(mid,b,fm,fb,fr,right,budget/2,depth-1)
    fa,fb,fm=f(a),f(b),f((a+b)/2)
    return recur(a,b,fa,fb,fm,(b-a)*(fa+4*fm+fb)/6,tolerance,24)


def moments(p,tolerance=1e-9):
    s,k,r,q,v,t=p
    width=v*math.sqrt(t); drift=(r-q-v*v/2)*t; discount=math.exp(-r*t)
    threshold=(math.log(k/s)-drift)/width
    def receipt(z):
        stock=s*math.exp(drift+width*z)
        return discount*max(k-stock,0),discount*stock,discount*max(stock-k,0)
    cuts=sorted({-12.0,12.0,max(-12,min(12,threshold)),max(-12,min(12,-threshold))})
    def expectation(fn):
        return math.fsum(adapt(lambda z:fn(z)*math.exp(-z*z/2)/math.sqrt(2*math.pi),a,b,tolerance/len(cuts)) for a,b in zip(cuts,cuts[1:]))
    ey=expectation(lambda z:receipt(z)[0]); ex=expectation(lambda z:receipt(z)[1])
    call=expectation(lambda z:receipt(z)[2])
    vy=expectation(lambda z:(receipt(z)[0]-ey)**2)
    vx=expectation(lambda z:(receipt(z)[1]-ex)**2)
    covariance=expectation(lambda z:(receipt(z)[0]-ey)*(receipt(z)[1]-ex))
    pair_y=lambda z:(receipt(z)[0]+receipt(-z)[0])/2
    pair_x=lambda z:(receipt(z)[1]+receipt(-z)[1])/2
    pair_var=expectation(lambda z:(pair_y(z)-ey)**2)
    pair_control=expectation(lambda z:(pair_y(z)+.35*(pair_x(z)-ex)-ey)**2)
    return dict(put=ey,call=call,ex=ex,vy=vy,vx=vx,cov=covariance,pair_var=pair_var,pair_control=pair_control)


def decimal_policies(p,n,stride):
    """Every full-history stopping subtree, including different actions after recombination."""
    with localcontext() as context:
        context.prec=48
        s,k,r,q,v,t=map(lambda x:Decimal(str(x)),p)
        dt=t/n; jump=v*dt.sqrt(); up=jump.exp(); down=(-jump).exp()
        probability=((r-q)*dt).exp()-down
        probability/=up-down; discount=(-r*dt).exp()
        def at(i,j):
            payoff=max(k-s*(jump*(2*j-i)).exp(),Decimal(0))
            if i==n: return [payoff]
            left=at(i+1,j); right=at(i+1,j+1)
            continued=[discount*((1-probability)*a+probability*b) for a in left for b in right]
            return ([payoff]+continued) if i%stride==0 else continued
        values=at(0,0)
        return float(max(values)),len(values)


def boundary_put(s,k,r,q,v,t):
    if t==0: return max(k-s,0)
    width=v*math.sqrt(t)
    cutoff=(math.log(k/s)-(r-q-v*v/2)*t)/width
    normal=statistics.NormalDist()
    return k*math.exp(-r*t)*normal.cdf(cutoff)-s*math.exp(-q*t)*normal.cdf(cutoff-width)


def spectral(p,L,M,N,mode):
    """Diagonalize the Dirichlet tridiagonal operator using its sine eigenvectors.

    This computes a modal convolution, not the model's spatial update or the
    author's stopped-walk oracle. Boundaries at previous time enter each update.
    """
    s,k,r,q,v,t=p; h=2*L/M; dt=t/N; a=v*v/2; b=r-q-a
    left=dt*(a/h**2-b/(2*h)); right=dt*(a/h**2+b/(2*h)); center=1-2*a*dt/h**2
    require(left>0 and right>0,'spectral oracle requires strict positive side weights')
    d=math.sqrt(left/right); geometric=[d**j for j in range(M+1)]
    x=[-L+j*h for j in range(M+1)]; growth=a*1.3**2+b*1.3
    initial=[math.exp(1.3*xx) if mode=='manufactured' else max(k-s*math.exp(xx),0) for xx in x]
    def edges(n):
        tau=n*dt
        if mode=='manufactured': return math.exp(-1.3*L+growth*tau),math.exp(1.3*L+growth*tau)
        if mode=='asymptotic': return max(k-s*math.exp(-L+(r-q)*tau),0),0.0
        return tuple(math.exp(r*tau)*boundary_put(s*math.exp(xx),k,r,q,v,tau) for xx in (-L,L))
    boundaries=[edges(n) for n in range(N)]
    modes=[]
    for ell in range(1,M):
        angle=math.pi*ell/M
        eigenvalue=center+2*math.sqrt(left*right)*math.cos(angle)
        coefficient=2/M*math.fsum(initial[j]/geometric[j]*math.sin(angle*j) for j in range(1,M))
        low_weight=2/M*left/geometric[1]*math.sin(angle)
        high_weight=2/M*right/geometric[M-1]*math.sin(angle*(M-1))
        for low,high in boundaries: coefficient=eigenvalue*coefficient+low_weight*low+high_weight*high
        modes.append(coefficient)
    low,high=edges(N)
    return [low]+[geometric[j]*math.fsum(coefficient*math.sin(math.pi*ell*j/M) for ell,coefficient in enumerate(modes,1)) for j in range(1,M)]+[high]


def replay(p,settings):
    s,k,r,q,v,t=p; beta=settings['control_beta']; discount=math.exp(-r*t); ex=s*math.exp(-q*t)
    data={key:[] for key in ('plain','fixed_control','antithetic','antithetic_fixed_control')}
    def obs(z):
        stock=s*math.exp((r-q-v*v/2)*t+v*math.sqrt(t)*z)
        return discount*max(k-stock,0),discount*stock
    for i in range(settings['pairs']):
        raw=sha256(f"v10-c10:{settings['seed']}:{i}".encode('ascii')).digest()
        words=struct.unpack('>QQ',raw[:16])
        u,w=(min((int(word//2048)+.5)/9007199254740992,math.nextafter(1,0)) for word in words)
        radius=(-2*math.log(u))**.5; z=radius*math.cos(2*math.pi*w); second=radius*math.sin(2*math.pi*w)
        for normal in (z,second):
            y,x=obs(normal); data['plain'].append(y); data['fixed_control'].append(y-beta*(x-ex))
        y,x=obs(z); ym,xm=obs(-z)
        data['antithetic'].append((y+ym)/2)
        data['antithetic_fixed_control'].append((y+ym)/2-beta*((x+xm)/2-ex))
    return {name:(len(values),statistics.mean(values),statistics.variance(values)) for name,values in data.items()}


class Fragment(HTMLParser):
    def __init__(self): super().__init__(); self.stack=[]; self.ids=[]; self.links=[]; self.worked=0; self.prompts=0; self.solutions=0
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        require(tag not in ('html','body','head','h1','script'),'static fragment')
        if 'id' in a: self.ids.append(a['id'])
        if 'href' in a: self.links.append(a['href'])
        if tag=='aside' and 'worked' in a.get('class','').split(): self.worked+=1
        if tag=='li' and self.stack and self.stack[-1][0]=='ol':
            if 'exercises' in self.stack[-1][1].get('class','').split(): self.prompts+=1
            if any(t=='details' and 'solutions' in d.get('class','').split() for t,d in self.stack): self.solutions+=1
        if tag not in ('br','hr','img','input','meta','link'): self.stack.append((tag,a))
    def handle_endtag(self,tag):
        require(self.stack and self.stack[-1][0]==tag,'balanced tag '+tag); self.stack.pop()


def check():
    audit=Audit(); data=json.loads((ASSETS/'v10-c10-inputs.json').read_text()); original=deepcopy(data)
    capture=StringIO()
    with redirect_stdout(capture),redirect_stderr(capture):
        code=runpy.run_path(str(ASSETS/'v10-c10-analysis.py')); run=code['run']; result=run(data)
    audit.eq(capture.getvalue(),'','quiet model import/run'); audit.eq(data,original,'nonmutating API')
    audit.eq(result,json.loads((ASSETS/'v10-c10-output.json').read_text()),'saved output is secondary reproducibility check')
    json.dumps(result,allow_nan=False)
    names=('spot','strike','rate','dividend_yield','volatility','maturity')
    p=tuple(data['market'][key] for key in names); s,k,r,q,v,t=p
    calculated=moments(p); tighter=moments(p,1e-10)
    for key in calculated: audit.near(calculated[key],tighter[key],'adaptive tolerance refinement '+key,atol=1e-7)
    for side in ('call','put'): audit.near(result['analytic']['european_'+side],calculated[side],'adaptive independent payoff '+side,atol=2e-8)
    ideal=result['monte_carlo']['ideal_analytic']
    for field,key in [('put_mean','put'),('put_variance','vy'),('discounted_stock_mean','ex'),('discounted_stock_variance','vx'),('put_stock_covariance','cov')]:
        audit.near(ideal[field],calculated[key],'centered moment integral '+field,atol=2e-7)
    audit.near(ideal['optimal_beta'],calculated['cov']/calculated['vx'],'independent covariance optimum')
    beta=data['monte_carlo']['control_beta']
    audit.near(ideal['fixed_control_variance'],calculated['vy']+beta*beta*calculated['vx']-2*beta*calculated['cov'],'raw control variance',atol=2e-7)
    audit.true(calculated['pair_var']<=calculated['vy']/2,'ideal monotone antithetic equal-cost variance improvement')
    audit.true(calculated['pair_control']>calculated['pair_var'],'same raw control worsens actual ideal paired variance')
    for name,(n,mean,variance) in replay(p,data['monte_carlo']).items():
        row=result['monte_carlo'][name]
        audit.eq(row['units'],n,'independent units '+name); audit.near(row['mean'],mean,'independent sample mean '+name)
        audit.near(row['sample_variance'],variance,'exact-float statistics variance '+name)
        se=math.sqrt(variance/n); audit.near(row['standard_error'],se,'sample SE '+name)
        for got,sign in zip(row['clt95_interval'],(-1,1)): audit.near(got,mean+sign*1.959963984540054*se,'CLT endpoints '+name)
        expected=None if 'control' in name else k*math.exp(-r*t)*math.sqrt(math.log(2/data['monte_carlo']['alpha'])/(2*n))
        if expected is None: audit.eq(row['hoeffding_half_width'],None,'unbounded stock control excluded')
        else: audit.near(row['hoeffding_half_width'],expected,'bounded independent-unit guarantee')

    quick=deepcopy(data); quick['tree']={'steps':[4],'exercise_stride':2}
    quick['finite_difference']['grids']=[{'space_steps':40,'time_steps':100}]; quick['monte_carlo']['pairs']=32
    base_quick=run(quick)
    for rate,yield_ in ((.04,.015),(-.03,.07),(0,0)):
        changed=deepcopy(quick); changed['market'].update(rate=rate,dividend_yield=yield_)
        changed_p=tuple(changed['market'][key] for key in names); row=run(changed)['tree'][0]
        for stride,field in ((1,'all_grid_dates_put'),(2,'bermudan_put')):
            expected,count=decimal_policies(changed_p,4,stride); audit.policies+=count
            audit.near(row[field],expected,'48-digit all-history stopping enumeration '+field)
        audit.true(row['european_put']<=row['bermudan_put']+1e-10<=row['all_grid_dates_put']+2e-10,'same-law nested exercise')
        audit.near(row['european_call']-row['european_put'],changed_p[0]*math.exp(-yield_*t)-k*math.exp(-rate*t),'negative/yield tree parity')
    audit.eq(audit.policies,3*(677+17),'all-history stopping policy count')
    stride_values=[]
    for stride in (1,4,24):
        changed=deepcopy(quick); changed['tree']={'steps':[24],'exercise_stride':stride}
        row=run(changed)['tree'][0]; stride_values.append(row['bermudan_put'])
        if stride==24: audit.near(row['bermudan_put'],max(k-s,row['european_put']),'root-and-terminal exercise target')
    audit.true(stride_values==sorted(stride_values,reverse=True),'same-law exercise intervention')
    audit.interventions.append('fixed-law exercise opportunities and negative-rate/dividend policy enumeration')

    for grid in result['finite_difference']:
        M,N=grid['space_steps'],grid['time_steps']; L=data['finite_difference']['log_half_width']
        exact=spectral(p,L,M,N,'exact'); asym=spectral(p,L,M,N,'asymptotic'); smooth=spectral(p,L,M,N,'manufactured')
        audit.near(grid['put_exact_boundary'],math.exp(-r*t)*exact[M//2],'sine spectral Dirichlet price',atol=2e-8)
        audit.near(grid['put_asymptotic_boundary'],math.exp(-r*t)*asym[M//2],'sine spectral asymptotic price',atol=2e-8)
        growth=v*v/2*1.3**2+(r-q-v*v/2)*1.3
        errors=[abs(y-math.exp(1.3*(-L+2*L*j/M)+growth*t)) for j,y in enumerate(smooth)]
        audit.near(grid['manufactured_max_error'],max(errors),'full spectral manufactured error',atol=2e-9)
        a=v*v/2; b=r-q-a; h=2*L/M; dt=t/N; top=math.exp(1.3*L+max(growth*t,0))
        bound=t*top*(dt*growth**2/2+a*h*h*1.3**4/12+abs(b)*h*h*1.3**3/6)
        audit.near(grid['manufactured_global_bound'],bound,'derived closed-rectangle derivative bound')
        audit.true(max(errors)<=bound+1e-10,'conditional smooth global theorem')
        audit.true(abs(grid['boundary_effect'])<=grid['discrete_boundary_effect_bound']+1e-10,'discrete boundary perturbation bound')
    altered=deepcopy(quick); altered['market'].update(volatility=.4,rate=-.03)
    altered['finite_difference']={'log_half_width':.8,'grids':[{'space_steps':80,'time_steps':800}]}
    row=run(altered)['finite_difference'][0]; pp=tuple(altered['market'][key] for key in names)
    for mode,key in (('exact','put_exact_boundary'),('asymptotic','put_asymptotic_boundary')):
        wanted=math.exp(.03*t)*spectral(pp,.8,80,800,mode)[40]
        audit.near(row[key],wanted,'negative-rate finite boundary effect '+mode,atol=2e-8)
    audit.true(row['boundary_effect']<-.001,'finite-boundary approximation error visible')
    audit.true(abs(row['boundary_effect'])<=row['discrete_boundary_effect_bound']+1e-10,'negative-rate discounted maximum principle')
    audit.interventions.append('negative-rate narrow-domain spectral boundary check')

    for label,mutate in [('zero control',lambda d:d['monte_carlo'].update(control_beta=0)),
                         ('wrong-sign control',lambda d:d['monte_carlo'].update(control_beta=1)),
                         ('seed-only change',lambda d:d['monte_carlo'].update(seed=17)),
                         ('concentration confidence change',lambda d:d['monte_carlo'].update(alpha=.1)),
                         ('homogeneous price scale',lambda d:d['market'].update(spot=120,strike=125))]:
        changed=deepcopy(quick); mutate(changed); got=run(changed)
        if label=='zero control':
            for first,second in [('plain','fixed_control'),('antithetic','antithetic_fixed_control')]:
                for key in ('mean','sample_variance','standard_error','units'): audit.eq(got['monte_carlo'][first][key],got['monte_carlo'][second][key],label+' '+key)
        elif label=='wrong-sign control':
            audit.true(got['monte_carlo']['ideal_analytic']['fixed_control_variance']>got['monte_carlo']['ideal_analytic']['put_variance'],label)
        elif label=='seed-only change':
            for key in ('analytic','tree','finite_difference'): audit.eq(got[key],base_quick[key],label+' deterministic '+key)
            audit.true(got['monte_carlo']['plain']['mean']!=base_quick['monte_carlo']['plain']['mean'],'seed changes observations')
        elif label=='concentration confidence change':
            audit.eq(got['monte_carlo']['plain']['clt95_interval'],base_quick['monte_carlo']['plain']['clt95_interval'],'fixed CLT95 unchanged')
            audit.true(got['monte_carlo']['plain']['hoeffding_half_width']<base_quick['monte_carlo']['plain']['hoeffding_half_width'],'higher alpha narrows bounded interval')
        else:
            for side in ('european_call','european_put'): audit.near(got['analytic'][side],1.25*base_quick['analytic'][side],'price homogeneity '+side)
            for field in ('european_call','european_put','bermudan_put','all_grid_dates_put'): audit.near(got['tree'][0][field],1.25*base_quick['tree'][0][field],'tree homogeneity '+field)
            audit.near(got['finite_difference'][0]['put_exact_boundary'],1.25*base_quick['finite_difference'][0]['put_exact_boundary'],'PDE homogeneity')
            for estimator in ('plain','fixed_control','antithetic','antithetic_fixed_control'):
                audit.near(got['monte_carlo'][estimator]['mean'],1.25*base_quick['monte_carlo'][estimator]['mean'],'sample common-random price scaling')
                audit.near(got['monte_carlo'][estimator]['sample_variance'],1.25**2*base_quick['monte_carlo'][estimator]['sample_variance'],'sample variance scaling')
        audit.interventions.append(label)
    for parameter,value,direction in [('volatility',.35,1),('dividend_yield',.06,1),('rate',.10,-1)]:
        changed=deepcopy(quick); changed['market'][parameter]=value; got=run(changed)
        pp=tuple(changed['market'][key] for key in names); wanted=moments(pp,1e-8)
        audit.near(got['analytic']['european_put'],wanted['put'],'financial intervention adaptive oracle '+parameter,atol=1e-7)
        audit.true(direction*(got['analytic']['european_put']-result['analytic']['european_put'])>0,'financial direction '+parameter)
        audit.interventions.append(parameter+' economic direction')

    F=Fraction; probability=F(8,15); discount=F(25,26)
    for strike,european,all_dates in [(84,F(12845,1521),F(15050,1521)),(88,F(16870,1521),F(19180,1521))]:
        terminal=[max(F(strike)-x,0) for x in (F(256,5),F(80),F(125))]
        continuation=[discount*((1-probability)*terminal[j]+probability*terminal[j+1]) for j in (0,1)]
        e=discount*((1-probability)*continuation[0]+probability*continuation[1])
        a=discount*((1-probability)*max(strike-64,continuation[0])+probability*max(strike-100,continuation[1]))
        audit.eq(e,european,'exact exercise tree European'); audit.eq(a,all_dates,'exact exercise tree adapted')
        audit.true(a>max(strike-80,0),'root continue')
    audit.eq(F('.012')/18,F(1,1500),'exercise1 inverse condition')
    audit.eq(4*F('.012')/F('.20')**2,F('1.2'),'exercise1 gamma price-error bound')
    for dt,expected in [(F('.2'),[F('.37'),F('.2'),F('.43')]),(F('.3'),[F('.555'),F('-.2'),F('.645')])]:
        weights=[dt*(F('.02')/F('.1')**2-F('.03')/(2*F('.1'))),1-2*F('.02')*dt/F('.1')**2,dt*(F('.02')/F('.1')**2+F('.03')/(2*F('.1')))]
        audit.eq(weights,expected,'exercise4 signed stencil'); audit.eq(sum(weights),1,'stencil sums to one even when invalid')
    bound=F('.0004')+F('.001')*3/2+F('.02')*F('.02')**2*20/12+F('.01')*F('.02')**2*5/6
    audit.eq(bound,F(23,12000),'exercise5 exact smooth bound'); audit.near(.006*math.exp(.06),.006371019279,'exercise6 negative rate',atol=1e-12)
    audit.eq(math.ceil(5000*math.log(40)),18445,'exercise7 Hoeffding n'); audit.eq(math.ceil((1.959963984540054*16)**2),984,'exercise7 CLT planning')
    audit.eq(F(3)-F(1)**2,2,'exercise8 square-normal variance'); audit.eq(F(2)/2,1,'exercise8 equal-cost iid denominator')
    for beta,wanted in [(F(-8,5),36),(-1,45),(1,205)]: audit.eq(100+25*beta**2+80*beta,wanted,'exercise9 coefficient variance')
    for receipts,wanted in [([5,5,1,1],3),([0,8,0,6],F(7,2)),([5,5,0,6],4),([5,8,1,6],5)]: audit.eq(sum(map(F,receipts))/4,wanted,'exercise11 toy policy value')
    audit.eq(F(1,4)**4,F(1,256),'worked4 all-L high-coin evaluation event')
    audit.eq(F('.1')**2/(2*F('.05')),F('.1'),'retention stable time step'); audit.eq(4*2500,10000,'retention sample scaling')

    invalid=[]
    def bad(path,value):
        changed=deepcopy(quick); branch=changed
        for key in path[:-1]: branch=branch[key]
        branch[path[-1]]=value; invalid.append(changed)
    for field in names:
        for value in (True,None,'1',float('nan'),float('inf'),10**500): bad(('market',field),value)
    for path,value in [(('schema_version',),True),(('schema_version',),1.0),(('market','spot'),19),
                       (('market','volatility'),0),(('market','maturity'),0),(('market','spot'),20),
                       (('tree','steps'),[4,4]),(('tree','steps'),[True]),(('tree','steps'),[4.0]),
                       (('tree','exercise_stride'),3),(('tree','exercise_stride'),33),
                       (('finite_difference','grids'),[{'space_steps':41,'time_steps':100}]),
                       (('finite_difference','grids'),[{'space_steps':40,'time_steps':4}]),
                       (('finite_difference','grids'),[{'space_steps':180,'time_steps':8000},{'space_steps':200,'time_steps':10000}]),
                       (('finite_difference','log_half_width'),.5),(('monte_carlo','pairs'),31),
                       (('monte_carlo','seed'),2**32),(('monte_carlo','control_beta'),2.1),(('monte_carlo','alpha'),0)]: bad(path,value)
    for section in ('market','tree','finite_difference','monte_carlo'): bad((section,),None)
    for change in [dict(spot=50,strike=100),dict(rate=.15,dividend_yield=0,volatility=.1,maturity=2)]:
        x=deepcopy(quick); x['market'].update(change)
        if 'spot' in change: x['finite_difference']['log_half_width']=.6
        else: x['tree']={'steps':[2],'exercise_stride':1}
        invalid.append(x)
    x=deepcopy(quick); x['market'].update(rate=.15,dividend_yield=0,volatility=.1); x['tree']['steps']=[24]
    x['finite_difference']['grids']=[{'space_steps':8,'time_steps':100}]; invalid.append(x)
    for item in invalid: audit.reject(lambda item=item:run(item),'strict bounded numerical domain')
    audit.interventions.append('reject unstable, nonpositive-probability and malformed financial domains')

    with tempfile.TemporaryDirectory(prefix='c10 peer portable ') as temporary:
        directory=Path(temporary)
        for suffix in ('-inputs.json','-analysis.py','-output.json','-manifest.json','-README.txt'):
            shutil.copyfile(ASSETS/('v10-c10'+suffix),directory/('v10-c10'+suffix))
        model=directory/'v10-c10-analysis.py'; source=directory/'v10-c10-inputs.json'; output=directory/'checked result.json'
        for optimized in (False,True):
            executable=[sys.executable]+(['-O'] if optimized else [])
            command=executable+[str(model),'--input',str(source),'--output',str(output)]
            completed=subprocess.run(command,cwd=directory,capture_output=True,text=True,timeout=30)
            audit.eq(completed.returncode,0,'portable CLI success'); audit.eq((completed.stdout,completed.stderr),('',''),'quiet portable CLI')
            audit.eq(json.loads(output.read_text()),result,'portable full numeric result')
            for bad_text in ('{"schema_version":1,"schema_version":1}','{"schema_version":NaN}',json.dumps(invalid[0]),' '*65537):
                bad_path=directory/'bad.json'; bad_path.write_text(bad_text); output.write_text('prior result')
                completed=subprocess.run(executable+[str(model),'--input',str(bad_path),'--output',str(output)],cwd=directory,capture_output=True,text=True,timeout=5)
                audit.true(completed.returncode!=0,'portable bad-input exit'); audit.eq(output.read_text(),'prior result','failure preserves existing output'); audit.rejections+=1
            before=source.read_bytes()
            same=subprocess.run(executable+[str(model),'--input',str(source),'--output',str(source)],cwd=directory,capture_output=True,text=True,timeout=5)
            audit.true(same.returncode!=0,'reject same input/output path'); audit.eq(source.read_bytes(),before,'source not overwritten'); audit.rejections+=1

    manifest=json.loads((ASSETS/'v10-c10-manifest.json').read_text())
    audit.eq(len(manifest['files']),4,'four standalone payloads')
    for row in manifest['files']:
        payload=(ASSETS/row['file']).read_bytes(); audit.eq(sha256(payload).hexdigest(),row['sha256'],'author manifest digest'); audit.eq(len(payload),row['bytes'],'manifest bytes')
    fragment=Fragment(); fragment.feed((ROOT/'content/chapters/v10-c10.html').read_text())
    audit.eq(fragment.stack,[],'balanced complete manuscript'); audit.eq((fragment.worked,fragment.prompts,fragment.solutions),(4,12,12),'four worked and twelve solved prompts')
    for i in range(1,13): audit.true('exercise-'+str(i) in fragment.ids and 'solution-'+str(i) in fragment.ids,'complete exact prompt/solution '+str(i))
    sources=json.loads((ROOT/'content/reviews/v10-c10-sources.json').read_text())['proposals']
    audit.eq({x['id'] for x in sources},{x.split('#',1)[1] for x in fragment.links if x.startswith('sources.html#')},'precise source scope links')
    for source in sources: audit.true(all(source.get(key) for key in ('title','url','use','checked','verification')),'source inspection record present')
    author=json.loads((ROOT/'content/reviews/v10-c10-author.json').read_text())
    audit.eq({x['path'] for x in author['reviewed_hashes']},set(AUTHOR_PATHS)-{'content/reviews/v10-c10-author.json'},'author eight nonself paths')
    for row in author['reviewed_hashes']:
        body=(ROOT/row['path']).read_bytes(); audit.eq(sha256(body).hexdigest(),row['sha256'],'author nonself digest'); audit.eq(len(body),row['bytes'],'author bytes')
    peer=ROOT/'content/reviews/v10-c10-peer.json'; peer_bound=0
    if peer.exists():
        record=json.loads(peer.read_text()); audit.eq({x['path'] for x in record['reviewed_hashes']},set(AUTHOR_PATHS),'peer exact nine paths')
        for row in record['reviewed_hashes']:
            body=(ROOT/row['path']).read_bytes(); audit.eq(sha256(body).hexdigest(),row['sha256'],'peer author digest'); audit.eq(len(body),row['bytes'],'peer author bytes'); peer_bound+=1
    peer_manifest=ROOT/'content/reviews/v10-c10-peer-manifest.json'
    if peer_manifest.exists():
        integrity=json.loads(peer_manifest.read_text())
        audit.eq(integrity['author_files'],record['reviewed_hashes'],'manifest and peer bind identical author payloads')
        audit.eq({x['path'] for x in integrity['peer_payloads']},{'scripts/check_v10_c10_peer.py','content/reviews/v10-c10-peer.json'},'peer two-payload integrity coverage')
        for row in integrity['peer_payloads']:
            body=(ROOT/row['path']).read_bytes(); audit.eq(sha256(body).hexdigest(),row['sha256'],'peer manifest digest'); audit.eq(len(body),row['bytes'],'peer manifest bytes')
    summary={'chapter':'v10-c10','status':'passed','independent_comparisons':audit.comparisons,
             'invalid_inputs_rejected':audit.rejections,'full_history_stopping_policies':audit.policies,
             'economic_interventions':audit.interventions,'worked_examples':4,'solved_exercises':12,
             'author_payload_hashes_verified':peer_bound,
             'groups':['adaptive payoff/centered-moment integrals and ideal paired-control variance',
                       '48-digit full-history finite stopping-policy enumeration',
                       'independent sine spectral Dirichlet solver and manufactured global error',
                       'independent sample reconstruction and correct statistical units',
                       'economic, boundary, scaling and strict-domain interventions',
                       'all determinate exercise arithmetic and separately audited proofs',
                       'portable normal/-O, source scopes and exact author/peer integrity'],
             'limits':'Separate machine-assisted peer review, not human academic certification. Numerical quadrature and spectral comparisons are tolerance-based checks, not proofs of general tree convergence, nonsmooth PDE rates, ideal RNG quality or empirical validation.'}
    json.dumps(summary,allow_nan=False); return summary


if __name__=='__main__': print(json.dumps(check(),indent=2,allow_nan=False))
