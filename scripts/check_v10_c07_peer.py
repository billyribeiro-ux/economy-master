"""Separate-agent c07 audit: quadratic forms, compressed cubature and L2 errors."""
from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
from decimal import Decimal, localcontext
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from io import StringIO
import json
import math
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
ASSETS=ROOT/'content/projects'
AUTHOR_PATHS=['content/chapters/v10-c07.html']+['content/projects/v10-c07-'+s for s in ('inputs.json','analysis.py','output.json','manifest.json','README.txt')]+['scripts/check_v10_c07.py','content/reviews/v10-c07-author.json','content/reviews/v10-c07-sources.json']


def require(ok,label):
    if not ok:
        raise AssertionError(label)


class Audit:
    def __init__(self):
        self.comparisons=0; self.rejections=0; self.groups=[]
    def eq(self,a,b,label):
        self.comparisons+=1
        if isinstance(b,F): a=F(a)
        require(a==b,f'{label}: {a!r} != {b!r}')
    def near(self,a,b,label,tol=2e-10):
        self.comparisons+=1
        require(type(a) in (int,float) and math.isfinite(a) and abs(a-b)<=tol*max(1,abs(b)),f'{label}: {a!r} != {b!r}')
    def true(self,ok,label):
        self.comparisons+=1;require(ok,label)


def simpson(fn,n=8192):
    lo,hi=-12,12; step=(hi-lo)/n
    total=fn(lo)+fn(hi)
    total+=4*math.fsum(fn(lo+i*step) for i in range(1,n,2))
    total+=2*math.fsum(fn(lo+i*step) for i in range(2,n,2))
    return total*step/3


def gaussian_integral(fn):
    return simpson(lambda z:fn(z)*math.exp(-z*z/2)/math.sqrt(2*math.pi))


def check_path(a,data,out):
    original=list(map(F,data['grid']['increments'])); T=F(data['grid']['horizon'])
    for block,group in zip(data['grid']['blocks'],out['finite_grids']):
        dx=[sum(original[i:i+block],F(0)) for i in range(0,len(original),block)]
        row=group['ledger']; n=len(dx); end=sum(dx,F(0));q=sum((x*x for x in dx),F(0))
        # Off-diagonal quadratic form x'Ax, Aij=1/2 for i!=j.
        left=sum((dx[i]*dx[j] for i in range(n) for j in range(i)),F(0))
        expected={'steps':n,'step':T/n,'terminal_W':end,'squared_increment_sum':q,
                  'absolute_increment_sum':sum(map(abs,dx),F(0)), 'left_sum':left,
                  'right_sum':left+q,'symmetric_sum':end*end/2,
                  'brownian_endpoint_formula':(end*end-T)/2,'left_minus_brownian_endpoint_formula':(T-q)/2}
        a.eq(group['block'],block,'aggregation block')
        for key,value in expected.items(): a.eq(row[key],value,'quadratic-form path '+key)
        for i,step in enumerate(row['rows']):
            w=sum(dx[:i],F(0)); next_w=w+dx[i]
            exact={'time':str((i+1)*T/n),'increment':str(dx[i]),'W_before':str(w),'W_after':str(next_w),
                   'left_gain':str(w*dx[i]),'right_gain':str(next_w*dx[i])}
            a.eq(step,exact,'dated row from prefix dot products')
    q=sum((x*x for x in original),F(0)); end=sum(original,F(0))
    for row in out['polygon_refinements']:
        a.eq(row['quadratic_sum'],sum((x*x/F(row['subdivisions']) for x in original),F(0)),'polygon variation')
        a.eq(row['ordinary_integral_W_dW'],end*end/2,'ordinary polygon integral')


def quadratic_moments(h):
    # For independent centered normals, E[x'Ax]=tr(A Sigma),
    # Var(x'Ax)=2 sum_ij Aij^2 h_i h_j. Apply to I, off-diagonal/2,
    # and I+off-diagonal/2 without assuming equally spaced observations.
    diagonal=sum((x*x for x in h),F(0))
    off=sum((h[i]*h[j] for i in range(len(h)) for j in range(i)),F(0))
    return {'quadratic_sum_mean':sum(h,F(0)),'quadratic_sum_variance':2*diagonal,
            'left_sum_mean':F(0),'left_sum_variance':off,
            'right_sum_mean':sum(h,F(0)),'right_sum_variance':2*diagonal+off,
            'left_integral_mse':diagonal/2,'ito_W_integral_variance':sum(h,F(0))**2/2}


def compressed_cubature(T,n):
    # Combine paths sharing (sum z,sum z^2), instead of the model's 3^n enumeration.
    law={(0,0):F(1)}
    for _ in range(n):
        updated={}
        for (s,q),weight in law.items():
            for z,p in ((-1,F(1,6)),(0,F(2,3)),(1,F(1,6))):
                key=(s+z,q+z*z); updated[key]=updated.get(key,F(0))+weight*p
        law=updated
    sums={key:F(0) for key in ('mass','Q','Q2','L','L2','R','R2','error2','WT2','WT4')}
    for (s,q),p in law.items():
        wt2=3*T*s*s/n; Q=3*T*q/n; L=(wt2-Q)/2;R=(wt2+Q)/2
        vals={'mass':1,'Q':Q,'Q2':Q*Q,'L':L,'L2':L*L,'R':R,'R2':R*R,
              'error2':(Q-T)**2/4,'WT2':wt2,'WT4':wt2*wt2}
        for key,value in vals.items():sums[key]+=p*value
    return {'states':3**n,'probability_sum':sums['mass'],'quadratic_sum_mean':sums['Q'],
            'quadratic_sum_variance':sums['Q2']-sums['Q']**2,'left_sum_mean':sums['L'],
            'left_sum_variance':sums['L2']-sums['L']**2,'right_sum_mean':sums['R'],
            'right_sum_variance':sums['R2']-sums['R']**2,'left_to_endpoint_mse':sums['error2'],
            'terminal_second_moment':sums['WT2'],'terminal_fourth_moment':sums['WT4']}


def dfrac(value):
    value=F(value);return Decimal(value.numerator)/Decimal(value.denominator)


def check_distribution(a,data,out):
    T=F(data['grid']['horizon']); t=float(T)
    for row in out['brownian_grid_theory']:
        for key,value in quadratic_moments([T/row['steps']]*row['steps']).items():
            a.eq(row[key],value,'Gaussian quadratic-form trace '+key)
    for key,value in compressed_cubature(T,data['grid']['cubature_steps']).items():
        a.eq(out['finite_moment_cubature'][key],value,'compressed cubature '+key)
    # Three-point Gaussian quadrature is exact for the two-stage polynomial's
    # degree <=4 in each independent variable; this is not a Gaussian-tail model.
    first,feedback=[float(F(data['adapted_integrand'][k])) for k in ('first_holding','feedback')]
    node=math.sqrt(3*t/2); nodes=[(-node,1/6),(0,2/3),(node,1/6)]
    m={p:math.fsum(pu*pv*(u*(first+feedback*v))**p for u,pu in nodes for v,pv in nodes) for p in (1,2,4)}
    for key,value in [('mean',m[1]),('variance',m[2]-m[1]**2),('fourth_moment',m[4]),('gaussian_fourth_if_same_variance',3*m[2]**2)]:
        a.near(float(F(out['adapted_two_step_integral'][key])),value,'tensor quadrature '+key)
    a.eq(out['adapted_two_step_integral']['switch_time'],T/2,'adapted half-horizon')
    # Integrate the affine endpoint law and use numerical derivatives of f.
    c={k:float(F(v)) for k,v in data['chain_product'].items()}; W=float(sum(map(F,data['grid']['increments']),F(0)))
    x=c['x0']+c['x_drift']*t+c['x_diffusion']*W
    y=c['y0']+c['y_drift']*t+c['y_diffusion']*W
    report=out['chain_and_product']; f=lambda time,state:math.exp(-c['decay']*time)*state*state
    hs,ht=.001,.00001
    fx=(f(t,x+hs)-f(t,x-hs))/(2*hs)
    fxx=(f(t,x+hs)-2*f(t,x)+f(t,x-hs))/(hs*hs)
    ft=(f(t+ht,x)-f(t-ht,x))/(2*ht)
    a.near(report['discounted_square_approx'],f(t,x),'discounted state')
    a.near(report['discounted_square_drift_approx'],ft+c['x_drift']*fx+.5*c['x_diffusion']**2*fxx,'numerical generator drift',tol=2e-6)
    a.near(report['discounted_square_diffusion_approx'],c['x_diffusion']*fx,'numerical Ito diffusion',tol=2e-7)
    xs=lambda z:c['x0']+c['x_drift']*t+c['x_diffusion']*math.sqrt(t)*z
    ys=lambda z:c['y0']+c['y_drift']*t+c['y_diffusion']*math.sqrt(t)*z
    a.near(report['discounted_square_expectation_approx'],gaussian_integral(lambda z:f(t,xs(z))),'integrated transformed expectation')
    a.near(float(F(report['product_expectation'])),gaussian_integral(lambda z:xs(z)*ys(z)),'integrated product expectation')
    a.near(float(F(report['product_drift_at_endpoint'])),c['x_drift']*y+c['y_drift']*x+c['x_diffusion']*c['y_diffusion'],'product generator')
    a.near(float(F(report['product_diffusion_at_endpoint'])),c['x_diffusion']*y+c['y_diffusion']*x,'product diffusion')
    for key,value in [('terminal_X',x),('terminal_Y',y),('cross_variation',c['x_diffusion']*c['y_diffusion']*t),('X_quadratic_variation',c['x_diffusion']**2*t),('Y_quadratic_variation',c['y_diffusion']**2*t)]:
        a.near(float(F(report[key])),value,'affine '+key)


def check_gbm(a,data,out):
    spec=data['gbm'];T=F(data['grid']['horizon']);s,mu,vol=[F(spec[k]) for k in ('initial_price','drift','diffusion')]
    report=out['gbm']; npath=len(data['grid']['increments']);h=T/npath
    w=F(0);factors=[];exact=float(s)
    for i,dx in enumerate(map(F,data['grid']['increments'])):
        w+=dx;factors.append(1+mu*h+vol*dx);exact*=math.exp(float((mu-vol**2/2)*h+vol*dx))
        row=report['rows'][i]
        a.eq(row['euler_price'],s*math.prod(factors),'Euler prefix product')
        a.eq(row['euler_positive'],math.prod(factors)>0,'Euler exact sign')
        a.near(row['exact_price_approx'],exact,'exact path as composed transitions')
        a.eq(row['time'],(i+1)*h,'GBM path time');a.eq(row['W'],w,'GBM path Brownian level')
    # Quadrature integrates the genuinely Gaussian terminal law, independently
    # of the finite authored path and three-point moment cubature.
    stock=lambda z:float(s)*math.exp(float((mu-vol**2/2)*T)+float(vol)*math.sqrt(float(T))*z)
    mean=gaussian_integral(stock);second=gaussian_integral(lambda z:stock(z)**2)
    a.near(report['mean_price_approx'],mean,'normal terminal quadrature mean')
    a.near(report['price_variance_approx'],second-mean*mean,'normal terminal quadrature variance',tol=2e-9)
    a.eq(report['log_return_mean'],(mu-vol**2/2)*T,'GBM log drift')
    a.eq(report['log_return_variance'],vol**2*T,'GBM log variance')
    a.near(report['median_price_approx'],stock(0),'median normal quantile')
    with localcontext() as ctx:
        ctx.prec=105
        S,m,v,t=map(dfrac,(s,mu,vol,T))
        for row in report['euler_analytical_error']:
            n=row['steps'];dt=t/n
            # Per-step Gaussian MGF anchors; total MSE uses a distinct
            # nonnegative norm/correlation decomposition instead of A+B-2C.
            E=(1+m*dt);A=(E*E+v*v*dt)**n;B=(((2*m+v*v)*dt).exp())**n
            C=(((m*dt).exp())*(E+v*v*dt))**n
            rootA=A.sqrt();rootB=B.sqrt()
            mse=S*S*((rootA-rootB)**2+2*(rootA*rootB-C))
            mEuler=S*E**n;mExact=S*(m*t).exp()
            anchors={'exact_mean_approx':mExact,'euler_mean_approx':mEuler,'weak_mean_bias_approx':mEuler-mExact,
                     'exact_second_moment_approx':S*S*B,'euler_second_moment_approx':S*S*A,
                     'coupled_cross_moment_approx':S*S*C,'coupled_strong_mse_approx':mse}
            for key,value in anchors.items():a.near(row[key],float(value),'norm/correlation GBM '+key)
    dt,dw=F(spec['probe_time']),F(spec['probe_increment']);p=report['positivity_probe'];factor=1+mu*dt+vol*dw
    a.eq(p['euler_factor'],factor,'probe signed factor');a.eq(p['euler_price'],s*factor,'probe signed price')
    a.eq(p['euler_nonpositive'],factor<=0,'probe zero/negative flag')
    a.near(p['exact_price_approx'],float(s)*math.exp(float((mu-vol**2/2)*dt+vol*dw)),'probe exact positivity')


class Fragment(HTMLParser):
    def __init__(self):
        super().__init__();self.stack=[];self.ids=[];self.links=[];self.worked=self.exercises=self.solutions=0
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        require(tag not in ('html','head','body','h1','script'),'static fragment')
        if 'id' in attrs:self.ids.append(attrs['id'])
        if 'href' in attrs:self.links.append(attrs['href'])
        if tag=='aside' and 'worked' in attrs.get('class','').split():self.worked+=1
        if tag=='li' and self.stack and self.stack[-1][0]=='ol':
            if 'exercises' in self.stack[-1][1].get('class','').split():self.exercises+=1
            if any(t=='details' and 'solutions' in at.get('class','').split() for t,at in self.stack):self.solutions+=1
        if tag not in ('br','hr','img','meta','link','input'):self.stack.append((tag,attrs))
    def handle_endtag(self,tag):
        require(self.stack and self.stack[-1][0]==tag,'balanced tag '+tag);self.stack.pop()


def check():
    a=Audit();data=json.loads((ASSETS/'v10-c07-inputs.json').read_text());saved=json.loads((ASSETS/'v10-c07-output.json').read_text())
    snapshot=deepcopy(data);capture=StringIO()
    with redirect_stdout(capture),redirect_stderr(capture):
        module=runpy.run_path(str(ASSETS/'v10-c07-analysis.py'));out=module['run'](data)
    a.eq(capture.getvalue(),'','quiet import/run');a.eq(data,snapshot,'input nonmutation');a.eq(out,saved,'full reference consistency')
    json.dumps(out,allow_nan=False)
    check_path(a,data,out);check_distribution(a,data,out);check_gbm(a,data,out)
    a.groups.append('independent quadratic-form path/moment calculations, compressed cubature, Gaussian quadrature, generator finite differences and norm/correlation MSE')

    # Exact exercise anchors, separate from the baseline fixture.
    irregular=quadratic_moments([F(1,8),F(3,8),F(1,2)])
    a.eq(irregular['quadratic_sum_variance'],F(13,16),'exercise2 irregular variance')
    a.eq(irregular['left_integral_mse'],F(13,64),'exercise2 irregular MSE')
    a.eq(F(1)+F(1)+F(1,3),F(7,3),'exercise3 deterministic integral')
    a.near(gaussian_integral(lambda z:z**4-z*z),2,'exercise4 anticipative weight nonzero mean')
    a.eq(F(2)**3/3,F(8,3),'exercise5 variance T2');a.eq(F(2)**2/2,F(2),'exercise5 covariance T2')
    a.near(gaussian_integral(lambda z:math.exp(-4)*(.5+.5*math.sqrt(2)*z)**2),.75*math.exp(-4),'exercise6 discounted square')
    a.near(gaussian_integral(lambda z:(.5+.5*math.sqrt(2)*z)*(4+.25*math.sqrt(2)*z)),2.25,'exercise6 product')
    a.near(gaussian_integral(lambda z:math.exp(-(-.12+.4*math.sqrt(2)*z))/50),math.exp(.28)/50,'exercise7 inverse price expectation')
    a.near(50*math.exp(-.12),44.346021835857876,'exercise7 median');a.near(50*math.exp(.04),52.04053870961941,'exercise7 mean')
    a.true(.02-.4**2/2<0,'exercise10 mean/median growth counterexample')
    a.eq(F(1,3)*27,F(9),'cubature sixth moment');a.near(gaussian_integral(lambda z:z**6),15,'Gaussian sixth moment')
    a.eq(quadratic_moments([F(1,4)]*8)['quadratic_sum_variance'],F(1),'retention Q variance')
    a.eq(quadratic_moments([F(1,4)]*8)['left_integral_mse'],F(1,4),'retention approximation MSE')
    a.groups.append('all determinate exercise and retention arithmetic; ten proof/open solutions separately reviewed')

    def changed(edit):
        variant=deepcopy(data);edit(variant);before=deepcopy(variant);quiet=StringIO()
        with redirect_stdout(quiet),redirect_stderr(quiet): result=module['run'](variant)
        require(not quiet.getvalue() and before==variant,'quiet nonmutating intervention')
        json.dumps(result,allow_nan=False);return variant,result
    # Reversal changes the observed endpoint, not quadratic forms or P-law moments.
    reverse,rev=changed(lambda d:d['grid'].__setitem__('increments',[str(-F(x)) for x in d['grid']['increments']]))
    check_path(a,reverse,rev)
    for old,new in zip(out['finite_grids'],rev['finite_grids']):
        for key in ('squared_increment_sum','left_sum','right_sum','absolute_increment_sum'):
            a.eq(new['ledger'][key],old['ledger'][key],'reverse-increment invariant '+key)
    a.eq(rev['brownian_grid_theory'],out['brownian_grid_theory'],'authored path does not change Gaussian law')
    a.eq(rev['finite_moment_cubature'],out['finite_moment_cubature'],'authored path does not change cubature')
    # Signed exposures, nonunit horizon, zero decay and smaller power-of-two record.
    def alternate(d):
        d['grid'].update(horizon='3/2',increments=['1/2','-1/4','1/8','-3/8'],blocks=[1,2,4],theory_steps=[3,7],cubature_steps=7)
        d['adapted_integrand'].update(first_holding='-3/2',feedback='-2')
        d['chain_product'].update(x0='1',x_drift='-1/4',x_diffusion='1/2',y0='2',y_drift='1',y_diffusion='-1/4',decay='0')
        d['gbm'].update(initial_price='50',drift='-1/5',diffusion='2/5',euler_steps=[1,3,9])
    variant,alt=changed(alternate);check_path(a,variant,alt);check_distribution(a,variant,alt);check_gbm(a,variant,alt)
    a.true(F(alt['chain_and_product']['cross_variation'])<0,'negative common-shock covariance')
    for mu,sigma in [('0','0'),('-1/2','0'),('1/1000000','1/1000000'),('-1/2','1')]:
        def boundary(d):
            d['gbm'].update(drift=mu,diffusion=sigma,euler_steps=[1,4096],probe_time='2',probe_increment='-4')
            d['grid'].update(horizon='2',increments=['0','0'],blocks=[1,2],theory_steps=[1],cubature_steps=1)
        variant,bound=changed(boundary);check_gbm(a,variant,bound)
        if sigma=='0':
            for row in bound['gbm']['euler_analytical_error']:
                a.near(row['coupled_strong_mse_approx'],row['weak_mean_bias_approx']**2,'deterministic MSE is squared bias')
        if mu=='0':
            for row in bound['gbm']['euler_analytical_error']:
                a.eq(row['weak_mean_bias_approx'],0.0,'zero-motion bias');a.eq(row['coupled_strong_mse_approx'],0.0,'zero-motion MSE')
        if mu=='-1/2' and sigma=='0':a.eq(bound['gbm']['positivity_probe']['euler_factor'],F(0),'zero Euler factor accepted as scheme defect')
    a.groups.append('path-sign, law invariance, maximum cubature, signed feedback/covariance, zero diffusion, tiny coefficients and n4096 interventions')

    bads=[(['grid','horizon'],True),(['grid','horizon'],1.0),(['grid','horizon'],float('nan')),(['grid','horizon'],float('inf')),
          (['grid','horizon'],'1e0'),(['grid','horizon'],'1/0'),(['grid','horizon'],'01'),(['grid','horizon'],'1/1000001'),
          (['grid','horizon'],'1/32'),(['grid','horizon'],'3'),(['grid','increments'],['0']*3),(['grid','increments'],['0']*128),
          (['grid','increments'],['4.000001','0']),(['grid','blocks'],[1,1]),(['grid','blocks'],[3]),(['grid','theory_steps'],[4097]),
          (['grid','polygon_subdivisions'],[True]),(['grid','cubature_steps'],8),(['adapted_integrand','feedback'],'10.01'),
          (['chain_product','decay'],'-1'),(['gbm','initial_price'],'0'),(['gbm','diffusion'],'-0.1'),(['gbm','drift'],'0.6'),
          (['gbm','euler_steps'],[0]),(['gbm','probe_increment'],'5'),(['contract','law'],'empirical fact'),(['provenance'],'observed data'),
          (['schema'],'other'),(['grid','unexpected'],0),(['gbm'],None)]
    for keys,value in bads:
        bad=deepcopy(data);dest=bad
        for key in keys[:-1]:dest=dest[key]
        dest[keys[-1]]=value
        try:module['run'](bad)
        except ValueError:a.rejections+=1
        else:raise AssertionError('accepted invalid '+str(keys))
    for bad in (None,[],True):
        try:module['run'](bad)
        except ValueError:a.rejections+=1
        else:raise AssertionError('invalid top-level type accepted')
    a.groups.append('independent malformed/domain/provenance rejection probes')

    manifest=json.loads((ASSETS/'v10-c07-manifest.json').read_text())
    expected={'v10-c07-'+s for s in ('inputs.json','analysis.py','output.json','README.txt')}
    a.eq({r['file'] for r in manifest['files']},expected,'four-file manifest scope')
    for entry in manifest['files']:
        b=(ASSETS/entry['file']).read_bytes();a.eq(sha256(b).hexdigest(),entry['sha256'],'manifest hash');a.eq(len(b),entry['bytes'],'manifest bytes')
    with tempfile.TemporaryDirectory(prefix='c07-peer-') as path:
        path=Path(path);source=path/'source';source.mkdir();cwd=path/'unrelated';cwd.mkdir()
        for name in expected:shutil.copyfile(ASSETS/name,source/name)
        script=source/'v10-c07-analysis.py';input_path=source/'v10-c07-inputs.json'
        for flags in ([],['-O']):
            base=[sys.executable]+flags+[str(script)]
            for args in ([],['--input',str(input_path)]):
                proc=subprocess.run(base+args,cwd=cwd,capture_output=True,text=True,timeout=30)
                a.eq(proc.returncode,0,'portable exit');a.eq(proc.stderr,'','portable stderr');a.eq(json.loads(proc.stdout),saved,'portable default/explicit stdout')
            target=cwd/('out-O.json' if flags else 'out.json')
            proc=subprocess.run(base+['--input',str(input_path),'--output',str(target)],cwd=cwd,capture_output=True,text=True,timeout=30)
            a.eq(proc.returncode,0,'portable output exit');a.eq(proc.stdout,'','portable file quiet');a.eq(proc.stderr,'','portable file stderr');a.eq(json.loads(target.read_text()),saved,'portable output result')
            for i,text in enumerate(('{"a":1,"a":2}','{"a":NaN}','{"a":Infinity}','{"a":-Infinity}')):
                bad=source/'bad.json';bad.write_text(text);dest=cwd/('reject'+str(i)+str(bool(flags)))
                proc=subprocess.run(base+['--input',str(bad),'--output',str(dest)],cwd=cwd,capture_output=True,text=True,timeout=30)
                require(proc.returncode and proc.stderr and not proc.stdout and not dest.exists(),'strict invalid JSON wrote output');a.rejections+=1
    a.groups.append('manifest and portable explicit/default normal/-O CLI with strict JSON and no rejected output')

    body=(ROOT/'content/chapters/v10-c07.html').read_text();parser=Fragment();parser.feed(body)
    a.true(not parser.stack,'complete HTML');a.eq(len(parser.ids),len(set(parser.ids)),'unique section IDs')
    a.eq((parser.worked,parser.exercises,parser.solutions),(4,10,10),'four examples and ten solved exercises')
    for name in expected|{'v10-c07-manifest.json'}:a.true(name in parser.links,'flat reader download '+name)
    a.true(not any(h.startswith('projects/') for h in parser.links),'resolved flat-download links')
    source_ids={s['id'] for s in json.loads((ROOT/'content/reviews/v10-c07-sources.json').read_text())['proposals']}
    a.eq({h.split('#',1)[1] for h in parser.links if h.startswith('sources.html#')},source_ids,'scoped source links')
    author=json.loads((ROOT/'content/reviews/v10-c07-author.json').read_text())
    a.eq({e['path'] for e in author['reviewed_hashes']},set(AUTHOR_PATHS)-{'content/reviews/v10-c07-author.json'},'author nonself scope')
    for entry in author['reviewed_hashes']:
        b=(ROOT/entry['path']).read_bytes();a.eq(sha256(b).hexdigest(),entry['sha256'],'author payload hash');a.eq(len(b),entry['bytes'],'author payload bytes')
    for name in ('content/reviews/v10-c07-peer.json','production/v10-c07-peer-evidence.json'):
        path=ROOT/name
        if path.exists():
            record=json.loads(path.read_text());entries=record['reviewed_hashes']
            require(len(entries)==9 and {e['path'] for e in entries}==set(AUTHOR_PATHS),'peer must bind nine author payloads')
            for entry in entries:
                b=(ROOT/entry['path']).read_bytes();require(sha256(b).hexdigest()==entry['sha256'] and len(b)==entry['bytes'],'stale peer hash '+entry['path'])
    a.groups.append('static package, corrected flat downloads, author and peer nine-file bindings')
    return {'status':'passed','independent_comparisons':a.comparisons,'invalid_inputs_rejected':a.rejections,'worked_examples':4,'solved_exercises':10,
            'groups':a.groups,'limits':'Separate-agent numerical/editorial review, not formal proof verification, external human certification, empirical validation or visual UI QA.'}


if __name__=='__main__':
    print(json.dumps(check(),indent=2,allow_nan=False))
