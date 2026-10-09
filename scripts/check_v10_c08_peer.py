"""Independent peer audit: Decimal Gaussian integrals, quadrature and cash ledgers."""
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
from decimal import Decimal as D, localcontext
from fractions import Fraction
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

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'content/projects'
AUTHOR_PATHS = ['content/chapters/v10-c08.html'] + [
    'content/projects/v10-c08' + suffix for suffix in
    ('-inputs.json', '-analysis.py', '-output.json', '-manifest.json', '-README.txt')
] + ['scripts/check_v10_c08.py', 'content/reviews/v10-c08-author.json',
     'content/reviews/v10-c08-sources.json']
PI = D('3.141592653589793238462643383279502884197169399375105820974944592307816406286208998628034825342117')


def require(ok, label):
    if not ok:
        raise AssertionError(label)


class Audit:
    def __init__(self):
        self.comparisons = 0
        self.rejections = 0
        self.groups = []
        self.max_price_error = 0.0
        self.max_quadrature_gap = 0.0

    def eq(self, value, expected, label):
        self.comparisons += 1
        require(value == expected, label + ': ' + repr(value) + ' != ' + repr(expected))

    def near(self, value, expected, label, absolute=1e-9, relative=1e-10):
        self.comparisons += 1
        expected = float(expected)
        require(type(value) in (float, int) and math.isfinite(value), label + ': finite numeric value')
        require(abs(value - expected) <= absolute + relative * abs(expected),
                label + ': ' + repr(value) + ' != ' + repr(expected))

    def true(self, condition, label):
        self.comparisons += 1
        require(condition, label)


def phi_integral(x):
    """Gaussian power-series integral in 110-digit Decimal arithmetic; no erf/erfc call.

    For |x|>14 the discarded Gaussian tail is <8e-45. Our maximum discounted
    input amounts then bound its price impact far below the float tolerance.
    """
    if x > 14:
        return D(1)
    if x < -14:
        return D(0)
    term = total = x
    for n in range(2000):
        term *= -x * x * D(2 * n + 1) / (D(2) * D(n + 1) * D(2 * n + 3))
        total += term
        if abs(term) < D('1e-90'):
            return D('0.5') + total / (2 * PI).sqrt()
    raise ArithmeticError('Gaussian series did not converge')


def parameters(case):
    return tuple(D(str(case[k])) for k in
                 ('spot', 'strike', 'rate', 'dividend_yield', 'volatility', 'maturity'))


def oracle_prices(params):
    s, k, r, q, sigma, tau = params
    with localcontext() as ctx:
        ctx.prec = 110
        prepaid, strike = s * (-q * tau).exp(), k * (-r * tau).exp()
        if tau == 0 or s == 0 or sigma == 0:
            return max(prepaid - strike, D(0)), max(strike - prepaid, D(0))
        width = sigma * tau.sqrt()
        logratio = (prepaid / strike).ln()
        zlo, zhi = logratio / width - width / 2, logratio / width + width / 2
        call = prepaid * phi_integral(zhi) - strike * phi_integral(zlo)
        put = strike * phi_integral(-zlo) - prepaid * phi_integral(-zhi)
        return call, put


def legendre_rule(n=24):
    """Newton construction of an independent Gauss-Legendre integration rule."""
    result = []
    for i in range(1, n + 1):
        x = math.cos(math.pi * (i - .25) / (n + .5))
        for _ in range(20):
            previous, current = 1.0, x
            for k in range(2, n + 1):
                previous, current = current, ((2*k-1)*x*current-(k-1)*previous)/k
            derivative = n * (x * current - previous) / (x*x - 1)
            change = current / derivative
            x -= change
            if abs(change) < 2e-16:
                break
        weight = 2 / ((1 - x*x) * derivative * derivative)
        result.append((x, weight))
    return result


def integrate(function, low, high, rule, panels=8):
    if low >= high:
        return 0.0
    step = (high - low) / panels
    total = []
    for i in range(panels):
        middle, half = low + (i + .5)*step, step/2
        total.append(half * math.fsum(w * function(middle + half*x) for x, w in rule))
    return math.fsum(total)


def payoff_quadrature(params, rule, panels=8):
    s, k, r, q, sigma, tau = map(float, params)
    if not s or not sigma or not tau:
        terminal = s * math.exp((r - q) * tau)
        return tuple(math.exp(-r*tau)*v for v in (max(terminal-k,0),max(k-terminal,0)))
    width = sigma * math.sqrt(tau)
    median = math.log(s) + (r - q - .5*sigma*sigma)*tau
    cutoff = (math.log(k) - median) / width
    density = lambda z: math.exp(-z*z/2) / math.sqrt(2*math.pi)
    terminal = lambda z: math.exp(median + width*z)
    call = integrate(lambda z: (terminal(z)-k)*density(z), max(-12,cutoff), 12, rule, panels)
    put = integrate(lambda z: (k-terminal(z))*density(z), -12, min(12,cutoff), rule, panels)
    return math.exp(-r*tau)*call, math.exp(-r*tau)*put


def greeks(params):
    """Five-point sensitivities of high-precision prices, not copied derivatives."""
    with localcontext() as ctx:
        ctx.prec = 100
        hs, ht = D('0.0001'), D('0.00001')
        spots, times = [], []
        for j in (-2, -1, 0, 1, 2):
            changed = list(params)
            changed[0] += j * hs
            spots.append(oracle_prices(tuple(changed)))
            changed = list(params)
            changed[5] += j * ht
            times.append(oracle_prices(tuple(changed)))
        out = {}
        for index, name in enumerate(('call', 'put')):
            a,b,c,d,e = [x[index] for x in spots]
            ta,tb,tc,td,te = [x[index] for x in times]
            out['delta_'+name] = (a-8*b+8*d-e)/(12*hs)
            out['gamma_'+name] = (-a+16*b-30*c+16*d-e)/(12*hs*hs)
            out['theta_'+name] = -(ta-8*tb+8*td-te)/(12*ht)
        return out


def audit_case(a, case, actual, rule, sensitivities=True):
    params = parameters(case)
    s,k,r,q,sigma,tau = map(float, params)
    high = oracle_prices(params)
    quad = payoff_quadrature(params, rule, 8)
    finer = payoff_quadrature(params, rule, 16)
    for i, name in enumerate(('call','put')):
        a.max_price_error = max(a.max_price_error, abs(actual[name] - float(high[i])))
        a.max_quadrature_gap = max(a.max_quadrature_gap, abs(quad[i] - finer[i]))
        a.near(actual[name], high[i], case['id']+' Decimal integral '+name, absolute=2e-9)
        a.near(actual[name], finer[i], case['id']+' payoff Gauss quadrature '+name, absolute=2e-8)
        a.near(quad[i], finer[i], case['id']+' quadrature refinement '+name, absolute=1e-9)
    stock_pv = s * math.exp(-q*tau)
    strike_pv = k * math.exp(-r*tau)
    a.near(actual['call']-actual['put'], stock_pv-strike_pv, 'independent parity')
    a.near(actual['prepaid_stock'], stock_pv, 'prepaid stock')
    a.near(actual['discounted_strike'], strike_pv, 'discounted strike')
    dividend = integrate(lambda u: q*s*math.exp(-q*u), 0, tau, rule)
    a.near(actual['expected_discounted_dividends_Q'], dividend, 'dated dividend receipts')
    a.near(actual['expected_discounted_total_gain_Q'], stock_pv+dividend, 'total gain reconciliation')
    mu = float(case['physical_drift'])
    a.near(actual['expected_terminal_stock_P'], s*math.exp(mu*tau), 'P mean')
    a.near(actual['expected_terminal_stock_Q'], s*math.exp((r-q)*tau), 'Q mean')
    for name, lo, hi in (('call', max(stock_pv-strike_pv,0),stock_pv),
                         ('put', max(strike_pv-stock_pv,0),strike_pv)):
        a.true(lo-1e-9 <= actual[name] <= hi+1e-9, name+' financial bounds')
    if s and sigma and tau:
        with localcontext() as ctx:
            ctx.prec = 110
            ds,dk,dr,dq,dv,dt = params
            pz = ((ds/dk).ln()+(D(str(case['physical_drift']))-dv*dv/2)*dt)/(dv*dt.sqrt())
            qz = ((ds/dk).ln()+(dr-dq-dv*dv/2)*dt)/(dv*dt.sqrt())
            a.near(actual['probability_P_itm'], phi_integral(pz), 'P normal series probability')
            a.near(actual['probability_Q_itm'], phi_integral(qz), 'Q normal series probability')
        a.near(actual['market_price_of_risk'], (mu+q-r)/sigma, 'market risk premium')
        a.near(actual['call_bank']+s*actual['delta_call'], actual['call'], 'call value funding')
        a.near(actual['put_bank']+s*actual['delta_put'], actual['put'], 'put value funding')
        if sensitivities and abs(float(actual['d1'])) < 12:
            derivatives = greeks(params)
            for name in ('call','put'):
                delta, gamma, theta = [float(derivatives[p+'_'+name]) for p in ('delta','gamma','theta')]
                a.near(actual['delta_'+name], delta, name+' independent delta', absolute=2e-8)
                a.near(actual['gamma'], gamma, name+' independent gamma', absolute=2e-8)
                a.near(actual['theta_'+name], theta, name+' independent calendar theta', absolute=2e-7)
                residual = theta+(r-q)*s*delta+.5*sigma*sigma*s*s*gamma-r*float(high[0 if name=='call' else 1])
                a.near(residual, 0, name+' PDE using independently differentiated prices', absolute=3e-7)


def audit_tilt(a, raw, actual, rule):
    spec = raw['tilt']
    case = next(c for c in raw['cases'] if c['id']==spec['case_id'])
    lam = float((Fraction(str(case['physical_drift']))+Fraction(str(case['dividend_yield']))-Fraction(str(case['rate'])))/Fraction(str(case['volatility'])))
    T = float(case['maturity'])
    hs, ws = list(map(float,spec['intervals'])), list(map(float,spec['brownian_P_increments']))
    log_ratios = [(-2*lam*w-lam*lam*h)/2 for h,w in zip(hs,ws)]
    a.near(actual['lambda'],lam,'tilt lambda')
    a.near(actual['log_density_Z'],math.fsum(log_ratios),'sum interval density ratios',absolute=2e-10)
    a.near(actual['log_joint_Q_density_of_WP']-actual['log_joint_P_density'],math.fsum(log_ratios),'joint normal density factorization',absolute=3e-10)
    for shifted,x,h in zip(actual['Brownian_Q_increments_on_same_path'],ws,hs):
        a.near(shifted-x,lam*h,'same path change of Brownian coordinate')
    a.near(actual['mean_WP_terminal_under_Q'],-lam*T,'tilted mean')
    a.near(actual['variance_WP_terminal_under_Q'],T,'unchanged variance')
    a.near(actual['E_P_Z_analytic'],1,'normalization anchor')
    a.near(actual['log_E_P_Z_squared_analytic'],lam*lam*T,'second density moment anchor')
    if abs(lam)*math.sqrt(T) < 4:
        # Integrate actual tilted density, x and x², independently of stored anchors.
        h = hs[0]
        density = lambda z: math.exp(-z*z/2-lam*math.sqrt(h)*z-.5*lam*lam*h)/math.sqrt(2*math.pi)
        mass = integrate(density,-12,12,rule)
        first = integrate(lambda z:math.sqrt(h)*z*density(z),-12,12,rule)
        second = integrate(lambda z:h*z*z*density(z),-12,12,rule)
        a.near(mass,1,'integrated tilted density mass')
        a.near(first,-lam*h,'integrated shifted first moment')
        a.near(second-first*first,h,'integrated shifted variance')
    if actual['log_density_Z'] < -746:
        a.eq(actual['density_Z'],None,'underflow is explicitly unavailable')
        a.eq(actual['density_Z_underflow'],True,'underflow flagged')
    else:
        a.near(actual['density_Z'],math.exp(math.fsum(log_ratios)),'representable positive density',absolute=1e-12)
        a.eq(actual['density_Z_underflow'],False,'representable density flag')


def audit_ledger(a, raw, actual):
    spec = raw['hedge']
    case = next(c for c in raw['cases'] if c['id']==spec['case_id'])
    s,k,r,q,sigma,tau = parameters(case)
    derivatives = greeks((s,k,r,q,sigma,tau))
    with localcontext() as ctx:
        ctx.prec = 80
        shares = derivatives['delta_call']
        bank = oracle_prices((s,k,r,q,sigma,tau))[0]-shares*s
        dates,spots = list(map(D,spec['dates'])),list(map(D,spec['prices']))
        a.near(actual['ledger'][0]['shares_after'],shares,'initial independently differentiated delta')
        a.near(actual['ledger'][0]['bank_after'],bank,'initial bank from independent premium')
        for i in range(1,len(dates)):
            dt = dates[i]-dates[i-1]
            incoming = shares*(q*dt).exp()
            accrued = bank*(r*dt).exp()
            marked = incoming*spots[i]+accrued
            remaining = tau-dates[i]
            params = spots[i],k,r,q,sigma,remaining
            premium = oracle_prices(params)[0]
            target = D(0) if remaining==0 else greeks(params)['delta_call']
            cash = (target-incoming)*spots[i]
            bank = accrued-cash
            shares = target
            row = actual['ledger'][i]
            for key,expected in {'time':dates[i],'spot':spots[i],'incoming_shares':incoming,
                                 'bank_before_trade':accrued,'rebalance_expenditure':cash,
                                 'shares_after':shares,'bank_after':bank,'wealth':marked,
                                 'call_mark':premium,'hedge_error':marked-premium}.items():
                a.near(row[key],expected,'independent dated hedge '+key,absolute=4e-8)
            a.eq(row['external_contribution'],0.0,'zero external funding')
            a.near(row['shares_after']*row['spot']+row['bank_after'],row['wealth'],'trade preserves marked wealth')
        a.near(actual['terminal_error'],bank-oracle_prices((spots[-1],k,r,q,sigma,D(0)))[0], 'terminal liquidation error',absolute=4e-8)


class Chapter(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids=[]
        self.links=[]
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if 'id' in attrs:self.ids.append(attrs['id'])
        if 'href' in attrs:self.links.append(attrs['href'])


def check():
    a=Audit()
    raw=json.loads((ASSETS/'v10-c08-inputs.json').read_text())
    saved=json.loads((ASSETS/'v10-c08-output.json').read_text())
    before=deepcopy(raw)
    captured=StringIO()
    with redirect_stdout(captured),redirect_stderr(captured):
        model=runpy.run_path(str(ASSETS/'v10-c08-analysis.py'))
        result=model['run'](raw)
    a.eq(captured.getvalue(),'','quiet independent import/API')
    a.eq(raw,before,'inputs unchanged')
    a.eq(result,saved,'reference reproducibility, supplemental to independent oracles')
    json.dumps(result,allow_nan=False)
    rule=legendre_rule()
    a.near(math.fsum(w for x,w in rule),2,'quadrature integrates constant',absolute=2e-14,relative=0)
    a.near(math.fsum(w*x*x for x,w in rule),2/3,'quadrature integrates square',absolute=2e-14,relative=0)
    for case in raw['cases']:
        audit_case(a,case,result['cases'][case['id']],rule)
    audit_tilt(a,raw,result['tilt'],rule)
    audit_ledger(a,raw,result['hedge'])
    a.groups.append('independent 110-digit normal integral and Gauss-Legendre payoff integration, Greeks, density moments and complete funded ledger')

    forecast=deepcopy(raw);forecast['cases'][0]['physical_drift']='0.19'
    changed=model['run'](forecast)
    base=result['cases']['dividend_call'];other=changed['cases']['dividend_call']
    for key in ('call','put','delta_call','delta_put','gamma','theta_call','theta_put','call_bank','put_bank','probability_Q_itm'):
        a.eq(other[key],base[key],'physical drift leaves '+key+' unchanged')
    a.eq(changed['hedge'],result['hedge'],'physical forecast does not alter the funded hedge')
    a.near(other['market_price_of_risk'],.66,'exercise5 risk premium')
    a.near(other['probability_P_itm'],.6933574586056107,'exercise5 physical event probability',absolute=1e-9)
    audit_tilt(a,forecast,changed['tilt'],rule)

    for field,value in [('dividend_yield','0'),('rate','-0.06'),('volatility','0.5')]:
        intervention=deepcopy(raw);intervention['cases'][0][field]=value
        changed=model['run'](intervention)
        audit_case(a,intervention['cases'][0],changed['cases']['dividend_call'],rule)
        if field=='dividend_yield':
            a.near(changed['cases']['dividend_call']['expected_discounted_dividends_Q'],0,'zero dividend cash')
            a.true(changed['cases']['dividend_call']['call']>base['call'],'removing yield raises call')
        elif field=='rate':
            a.true(changed['cases']['dividend_call']['call']<base['call'],'lower funding rate lowers call')
            a.true(changed['cases']['dividend_call']['put']>base['put'],'lower funding rate raises put')
        else:
            a.true(changed['cases']['dividend_call']['call']>base['call'],'higher diffusion raises call')
            a.true(changed['cases']['dividend_call']['put']>base['put'],'higher diffusion raises put')

    negative=deepcopy(raw);negative['hedge']['prices'][-1]='40'
    loss=model['run'](negative)
    a.eq(loss['hedge']['ledger'][:-1],result['hedge']['ledger'][:-1],'final stress preserves every earlier cash row')
    audit_ledger(a,negative,loss['hedge'])
    a.near(loss['hedge']['terminal_error'],-7.902181201720436,'exercise11 explicit loss',absolute=2e-8)
    a.true(result['hedge']['terminal_error']>0 and loss['hedge']['terminal_error']<0,'both signs of finite-grid error')

    neutral=deepcopy(raw);neutral['cases'][0]['physical_drift']='0.025'
    same=model['run'](neutral)
    a.eq(same['tilt']['density_Z'],1.0,'zero premium density is one')
    a.eq(same['tilt']['Brownian_Q_increments_on_same_path'],list(map(float,raw['tilt']['brownian_P_increments'])),'zero premium changes no Brownian coordinate')

    for s,k,r,q,v,t in [('1000','1','0.3','0','0.8','5'),('1','1000','-0.1','0.2','0.8','5'),
                       ('100','100','0.3','0.2','0.05','0.02')]:
        stress=deepcopy(raw)
        stress['cases'][-1].update(spot=s,strike=k,rate=r,dividend_yield=q,volatility=v,maturity=t)
        stressed=model['run'](stress)
        audit_case(a,stress['cases'][-1],stressed['cases']['extreme_tail'],rule)
    a.groups.append('financial interventions: P-only forecast, dividend cash, funding rate, volatility, zero risk premium, signed hedge loss and bounded-domain extremes')

    for underflow in (True,False):
        stress=deepcopy(raw)
        stress['cases'][0].update(rate='-0.1',dividend_yield='0.2',volatility='0.05',physical_drift='0.4',maturity='5' if underflow else '0.16')
        stress['tilt'].update(intervals=['0.625' if underflow else '0.02']*8,brownian_P_increments=['5' if underflow else '-5']*8)
        stress['hedge']['dates']=['0','0.5','1','5'] if underflow else ['0','0.04','0.08','0.16']
        stressed=model['run'](stress)
        audit_tilt(a,stress,stressed['tilt'],rule)
        a.near(stressed['tilt']['log_density_Z'],-1050 if underflow else 544.32,'extreme log density remains finite')
        json.dumps(stressed,allow_nan=False)
    a.eq(result['cases']['deterministic_kink']['delta_call'],None,'deterministic spot kink unavailable')
    a.eq(result['cases']['expiry']['delta_call'],None,'expiry Greek unavailable')
    a.eq(result['cases']['absorbing']['call'],0.0,'absorbing call')
    a.near(result['cases']['absorbing']['put'],100*math.exp(.02),'absorbing negative-rate put')
    a.near(result['cases']['deterministic']['put'],100*math.exp(.02)-90*math.exp(-.04),'exercise8 deterministic PV')
    a.near(90*(math.exp(.04)-math.exp(-.02)),5.45508907979223,'exercise8 deterministic arbitrage',absolute=2e-8)
    a.near(-math.log(.96),.040821994520255166,'exercise10 carry-equivalent yield')
    a.near(50*math.exp(.02),51.01006700133779,'retention zero-stock put')
    a.near((.08+.02-.04)/.30,.20,'retention measure shift')
    a.groups.append('underflow and maximal representable tilt, deterministic/absorbing/expiry semantics and remaining exercise/retention anchors')

    def reject(path,value):
        changed=deepcopy(raw);target=changed
        for part in path[:-1]:target=target[part]
        target[path[-1]]=value
        try:model['run'](changed)
        except ValueError:a.rejections+=1
        else:raise AssertionError('accepted invalid peer input '+repr(path)+' '+repr(value))
    invalid=[(['cases',0,'spot'],True),(['cases',0,'spot'],'NaN'),(['cases',0,'spot'],float('nan')),
             (['cases',0,'spot'],float('inf')),(['cases',0,'spot'],'1e2'),(['cases',0,'spot'],'+92'),
             (['cases',0,'spot'],'092'),(['cases',0,'spot'],'92/1'),(['cases',0,'spot'],'0.5'),
             (['cases',0,'strike'],'0'),(['cases',0,'rate'],'0.31'),(['cases',0,'dividend_yield'],'-0.01'),
             (['cases',0,'volatility'],'0.04'),(['cases',0,'maturity'],'0.01'),(['cases',0,'physical_drift'],'0.41'),
             (['cases',2,'physical_drift'],'0'),(['cases',0,'extra'],1),(['cases',0,'id'],'UPPER'),
             (['cases',1,'id'],'dividend_call'),(['tilt','intervals'],['0.5','0.5']),
             (['tilt','intervals'],['0.5','0.5','0.4']),(['tilt','brownian_P_increments'],['6','0','0']),
             (['tilt','case_id'],'deterministic'),(['hedge','case_id'],'absorbing'),
             (['hedge','dates'],['0','0.5','0.5','1.5']),(['hedge','dates'],['0','0.01','1','1.5']),
             (['hedge','prices'],['91','97','88','110']),(['hedge','prices'],['92','0','88','110']),
             (['hedge','dates'],['0','0.5','1','1.4']),(['schema'],'other'),(['cases'],[]),(['extra'],True)]
    for path,value in invalid:reject(path,value)
    a.groups.append('independent malformed, financial-invariant and bounded-domain rejection cases')

    with tempfile.TemporaryDirectory(prefix='c08-peer-') as folder:
        temp=Path(folder);source=temp/'source';source.mkdir();cwd=temp/'cwd';cwd.mkdir()
        for suffix in ('-inputs.json','-analysis.py','-output.json','-README.txt'):
            shutil.copyfile(ASSETS/('v10-c08'+suffix),source/('v10-c08'+suffix))
        for optimized in (False,True):
            base_command=[sys.executable]+(['-O'] if optimized else [])
            code="import contextlib,io,json,runpy; b=io.StringIO();\nwith contextlib.redirect_stdout(b),contextlib.redirect_stderr(b):\n m=runpy.run_path("+repr(str(source/'v10-c08-analysis.py'))+"); d=json.loads(open("+repr(str(source/'v10-c08-inputs.json'))+").read()); r=m['run'](d)\nif b.getvalue(): raise RuntimeError('noisy API')\nprint(json.dumps(r,allow_nan=False))"
            api=subprocess.run(base_command+['-c',code],cwd=cwd,capture_output=True,text=True,timeout=30)
            a.eq(api.returncode,0,'isolated quiet API return')
            a.eq(api.stderr,'','isolated quiet API stderr')
            a.eq(json.loads(api.stdout),saved,'isolated API output')
            output=temp/('result-O.json' if optimized else 'result.json')
            command=base_command+[str(source/'v10-c08-analysis.py'),'--input',str(source/'v10-c08-inputs.json'),'--output',str(output)]
            process=subprocess.run(command,cwd=cwd,capture_output=True,text=True,timeout=30)
            a.eq(process.returncode,0,'portable CLI return')
            a.eq(process.stdout,'','portable CLI stdout')
            a.eq(process.stderr,'','portable CLI stderr')
            a.eq(json.loads(output.read_text()),saved,'portable explicit output')
            for text in ('{"schema":"x","schema":"y"}','{"x":NaN}','{"x":Infinity}'):
                bad=temp/'bad.json';bad.write_text(text);unwritten=temp/'unwritten.json'
                fail=subprocess.run(base_command+[str(source/'v10-c08-analysis.py'),'--input',str(bad),'--output',str(unwritten)],cwd=cwd,capture_output=True,text=True,timeout=30)
                a.true(fail.returncode!=0 and not unwritten.exists(),'strict CLI rejects before output creation')
                a.eq(fail.stdout,'','invalid CLI no result')
                a.rejections+=1
    a.groups.append('portable isolated normal/optimized quiet API and explicit CLI; strict duplicate/nonfinite JSON')

    peer=json.loads((ROOT/'content/reviews/v10-c08-peer.json').read_text())
    a.eq({x['path'] for x in peer['reviewed_hashes']},set(AUTHOR_PATHS),'peer binds exact nine author files')
    a.eq(len(peer['reviewed_hashes']),9,'no duplicate author binding')
    for record in peer['reviewed_hashes']:
        blob=(ROOT/record['path']).read_bytes()
        a.eq(record['bytes'],len(blob),'peer byte count')
        a.eq(record['sha256'],sha256(blob).hexdigest(),'peer author hash')
    manifest=json.loads((ASSETS/'v10-c08-manifest.json').read_text())
    a.eq(len(manifest['files']),4,'four-file manifest')
    for record in manifest['files']:
        blob=(ASSETS/record['file']).read_bytes()
        a.eq(record['bytes'],len(blob),'manifest bytes')
        a.eq(record['sha256'],sha256(blob).hexdigest(),'manifest hash')
    author=json.loads((ROOT/'content/reviews/v10-c08-author.json').read_text())
    a.eq(len(author['reviewed_hashes']),8,'author binds eight nonself files')
    for record in author['reviewed_hashes']:
        a.eq(sha256((ROOT/record['path']).read_bytes()).hexdigest(),record['sha256'],'author binding rechecked')
    chapter=Chapter();chapter.feed((ROOT/'content/chapters/v10-c08.html').read_text())
    for number in range(1,13):
        a.true('exercise-'+str(number) in chapter.ids and 'solution-'+str(number) in chapter.ids,'complete prompt/solution '+str(number))
    for suffix in ('-inputs.json','-analysis.py','-output.json','-README.txt','-manifest.json'):
        a.true('v10-c08'+suffix in chapter.links,'flat project download link')
    a.groups.append('exact frozen author payloads, manifest/author bindings and twelve complete prompt/solution entries')
    return {'chapter':'v10-c08','status':'passed','peer_comparisons':a.comparisons,
            'invalid_inputs_rejected':a.rejections,'author_files_bound':9,'solved_exercises_reviewed':12,
            'max_price_difference_from_decimal_oracle':a.max_price_error,
            'max_payoff_quadrature_refinement_difference':a.max_quadrature_gap,
            'groups':a.groups,'limits':'Independent machine-assisted peer review, not external human certification. Numerical checks do not prove stochastic theorems or empirical model adequacy.'}


if __name__=='__main__':
    print(json.dumps(check(),indent=2,allow_nan=False))
