"""Independent payoff integrals, funded cash sums and bounded c09 package checks."""
from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
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
ASSETS = ROOT/'content/projects'
PREFIX = 'v10-c09'


def require(condition, label):
    if not condition:
        raise AssertionError(label)


class Audit:
    def __init__(self):
        self.comparisons = 0
        self.rejections = 0
        self.interventions = []
        self.groups = []

    def eq(self, actual, expected, label):
        self.comparisons += 1
        require(actual == expected, f'{label}: {actual!r} != {expected!r}')

    def near(self, actual, expected, label, atol=2e-9, rtol=2e-10):
        self.comparisons += 1
        require(type(actual) in (int, float) and math.isfinite(actual), label+': not finite')
        require(abs(actual-expected) <= atol+rtol*abs(expected),
                f'{label}: {actual!r} != {expected!r}')

    def true(self, condition, label):
        self.comparisons += 1
        require(condition, label)

    def reject(self, function, label):
        try:
            function()
        except ValueError:
            self.rejections += 1
        else:
            raise AssertionError(label+': failed to reject')


def simpson(function, low, high, panels=4096):
    if low >= high:
        return 0.0
    h = (high-low)/panels
    return h/3*(function(low)+function(high)
                +4*math.fsum(function(low+i*h) for i in range(1,panels,2))
                +2*math.fsum(function(low+i*h) for i in range(2,panels,2)))


def integral(p, panels=4096):
    """Independent terminal-payoff and pathwise-delta quadrature, no normal CDF."""
    s,k,t,r,q,v = (p[key] for key in ('spot','strike','tau','rate','dividend','sigma'))
    if not t or not v or not s:
        a, h = s*math.exp(-q*t), k*math.exp(-r*t)
        return {'call': max(a-h,0), 'put': max(h-a,0)}
    scale = v*math.sqrt(t)
    drift = (r-q-v*v/2)*t
    threshold = (math.log(k/s)-drift)/scale
    low, high = -12.0, max(12.0, scale+12)
    split = min(high,max(low,threshold))
    def factor(z):
        return math.exp(drift+scale*z)
    def density(z):
        return math.exp(-z*z/2)/math.sqrt(2*math.pi)
    discount = math.exp(-r*t)
    return {
        'call': discount*simpson(lambda z:max(s*factor(z)-k,0)*density(z),split,high,panels),
        'put': discount*simpson(lambda z:max(k-s*factor(z),0)*density(z),low,split,panels),
        'call_delta': discount*simpson(lambda z:factor(z)*density(z),split,high,panels),
        'put_delta': -discount*simpson(lambda z:factor(z)*density(z),low,split,panels),
    }


def fd_greeks(p):
    center = integral(p,8192)
    h = 0.03
    up = integral(dict(p,spot=p['spot']+h),8192)
    down = integral(dict(p,spot=p['spot']-h),8192)
    v = 0.0001
    vup = integral(dict(p,sigma=p['sigma']+v),8192)
    vdown = integral(dict(p,sigma=p['sigma']-v),8192)
    dt = 0.00001
    older = integral(dict(p,tau=p['tau']-dt),8192)
    younger = integral(dict(p,tau=p['tau']+dt),8192)
    return {'call_delta': (up['call']-down['call'])/(2*h),
            'put_delta': (up['put']-down['put'])/(2*h),
            'gamma': (up['call']-2*center['call']+down['call'])/(h*h),
            'vega': (vup['call']-vdown['call'])/(2*v),
            'call_theta': (older['call']-younger['call'])/(2*dt),
            'put_theta': (older['put']-younger['put'])/(2*dt)}


def ledger_oracle(p, spec):
    """Expand every dated stock trade/fee back to the initial cash balance."""
    start = integral(p,8192)
    cash0 = start['call']-start['call_delta']*p['spot']
    shares = start['call_delta']
    trades, fees, rows = [], [], []
    for i,(date,spot) in enumerate(zip(spec['times'][1:],spec['spots'][1:]),1):
        previous = spec['times'][i-1]
        incoming = shares*math.exp(p['dividend']*(date-previous))
        bank = cash0*math.exp(p['rate']*date)-math.fsum(c*math.exp(p['rate']*(date-t)) for t,c in trades)
        wealth = incoming*spot+bank
        row = {'incoming_shares_after_dividends': incoming,'incoming_bank':bank,'wealth_before_trade':wealth}
        if i < len(spec['times'])-1:
            mark = integral(dict(p,spot=spot,tau=p['tau']-date),8192)
            shares = mark['call_delta']
            trade = (shares-incoming)*spot
            fee = abs(trade)*spec['interior_fee']
            trades.append((date,trade)); fees.append((date,fee))
            row.update(target_shares=shares,stock_trade_cash=trade,fee=fee,
                       ideal_bank_after_trade=bank-trade,call_mark=mark['call'],
                       bank_with_fees_after_trade=bank-trade-math.fsum(c*math.exp(p['rate']*(date-t)) for t,c in fees))
        else:
            payoff = max(spot-p['strike'],0)
            fee_cost = math.fsum(c*math.exp(p['rate']*(date-t)) for t,c in fees)
            row.update(payoff=payoff,ideal_terminal_error=wealth-payoff,
                       funded_fee_terminal_error=wealth-payoff-fee_cost)
        rows.append(row)
    return rows


class Fragment(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack=[]; self.ids=[]; self.links=[]
        self.worked=0; self.exercises=0; self.solutions=0

    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        require(tag not in ('html','head','body','h1','script'),'static fragment only')
        if 'id' in attrs: self.ids.append(attrs['id'])
        if 'href' in attrs: self.links.append(attrs['href'])
        if tag=='aside' and 'worked' in attrs.get('class','').split(): self.worked+=1
        if tag=='li' and self.stack and self.stack[-1][0]=='ol':
            if 'exercises' in self.stack[-1][1].get('class','').split(): self.exercises+=1
            if any(t=='details' and 'solutions' in a.get('class','').split() for t,a in self.stack): self.solutions+=1
        if tag not in ('br','hr','img','meta','link','input'): self.stack.append((tag,attrs))

    def handle_endtag(self,tag):
        require(self.stack and self.stack[-1][0]==tag,'balanced fragment: '+tag)
        self.stack.pop()


def check():
    audit=Audit()
    raw=json.loads((ASSETS/(PREFIX+'-inputs.json')).read_text())
    saved=json.loads((ASSETS/(PREFIX+'-output.json')).read_text())
    original=deepcopy(raw); capture=StringIO()
    with redirect_stdout(capture),redirect_stderr(capture):
        model=runpy.run_path(str(ASSETS/(PREFIX+'-analysis.py')))
        run=model['run']; vanilla=model['vanilla']; inverse=model['implied_call']
        result=run(raw)
    audit.eq(capture.getvalue(),'','quiet import and public API')
    audit.eq(raw,original,'input not mutated')
    audit.eq(result,saved,'saved payload additional reproducibility check')
    json.dumps(result,allow_nan=False)
    audit.groups.append('quiet strict JSON API and nonmutation; saved output secondary check')
    base=raw['base']; values=result['base']
    cases=[base,dict(spot=85,strike=90,tau=.5,rate=.01,dividend=.02,sigma=.3),
           dict(spot=150,strike=100,tau=1,rate=-.1,dividend=0,sigma=.1),
           dict(spot=100,strike=50,tau=1,rate=0,dividend=.2,sigma=.1),
           dict(spot=100,strike=100,tau=.0001,rate=0,dividend=0,sigma=.2),
           dict(spot=1,strike=10000,tau=.0001,rate=-.2,dividend=.2,sigma=.0001),
           dict(spot=10000,strike=1,tau=5,rate=.2,dividend=.2,sigma=3),
           dict(spot=80,strike=120,tau=5,rate=-.2,dividend=.2,sigma=3)]
    for i,p in enumerate(cases):
        actual=vanilla(**p); expected=integral(p,8192); coarse=integral(p,4096)
        a=p['spot']*math.exp(-p['dividend']*p['tau']); h=p['strike']*math.exp(-p['rate']*p['tau'])
        for key in ('call','put','call_delta','put_delta'):
            audit.near(expected[key],coarse[key],f'case{i} integral refinement {key}',atol=2e-6)
            audit.near(actual[key],expected[key],f'case{i} independent integral {key}',atol=2e-6)
        audit.near(actual['call']-actual['put'],a-h,f'case{i} parity')
        audit.near(actual['call_delta']-actual['put_delta'],math.exp(-p['dividend']*p['tau']),f'case{i} delta parity')
        audit.near(actual['vega'],p['spot']**2*p['sigma']*p['tau']*actual['gamma'],f'case{i} vega gamma')
        audit.near(actual['call_theta']+.5*p['sigma']**2*p['spot']**2*actual['gamma']
                   +(p['rate']-p['dividend'])*p['spot']*actual['call_delta']-p['rate']*actual['call'],0,f'case{i} funded PDE',atol=1e-8)
        audit.true(max(a-h,0)-1e-8 <= actual['call'] <= a+1e-8,f'case{i} call bounds')
        audit.true(max(h-a,0)-1e-8 <= actual['put'] <= h+1e-8,f'case{i} put bounds')
    for p in (cases[0],cases[1],dict(base,rate=-.04,dividend=.08)):
        actual=vanilla(**p)
        for key,expected in fd_greeks(p).items():
            audit.near(actual[key],expected,'independent payoff finite difference '+key,atol=2e-5 if 'theta' in key or key=='vega' else 8e-7)
    audit.true(vanilla(**cases[2])['call_theta']>0,'negative funding rate allows positive long-call theta')
    audit.true(vanilla(**cases[3])['call_theta']>0,'yield carry allows positive long-call theta')
    audit.eq(vanilla(**cases[5])['vega'],0.0,'extreme-tail float underflow acknowledged')
    tiny=vanilla(**cases[4]); larger=vanilla(**dict(cases[4],tau=.01))
    audit.true(tiny['gamma']>9*larger['gamma'] and tiny['vega']<.11*larger['vega'],'near-expiry gamma/vega opposite scaling')
    for field in ('spot','tau','sigma'):
        p=dict(base); p[field]=0
        boundary=vanilla(**p); expected=integral(p)
        for side in ('call','put'): audit.near(boundary[side],expected[side],field+' boundary price '+side)
        for key in ('call_delta','put_delta','gamma','vega','call_theta','put_theta'):
            audit.eq(boundary[key],None,field+' boundary no interior '+key)
    audit.groups.append('payoff quadrature with grid refinement, independent finite differences, PDE/parity and interior/boundary stresses')

    # Numerical statements in the five worked cases and exact problem worksheets.
    for key,expected in {'call':8.288309863733858,'put':11.849649159552925,
                         'call_delta':.4792798674509495,'gamma':.015804533531403948,
                         'vega':40.96535091339903,'call_theta':-7.168510611643539}.items():
        audit.near(values[key],expected,'worked1 '+key)
    units=Fraction(-15*100)
    for key,expected in {'option_units':float(units),'call_market_value':float(units)*values['call'],
                         'delta_shares':float(units)*values['call_delta'],
                         'gamma':float(units)*values['gamma'],
                         'vega_per_unit_sigma':float(units)*values['vega'],
                         'vega_per_volatility_point':float(units)*values['vega']/100,
                         'calendar_theta_per_year':float(units)*values['call_theta']}.items():
        audit.near(result['portfolio'][key],expected,'portfolio signed units '+key)
    for label,mutator in (
        ('reverse option position',lambda d:d['position'].update(contracts=15)),
        ('add delta-neutralizing stock',lambda d:d['position'].update(stock_units=result['portfolio']['stock_trade_to_zero_delta'])),
        ('double contract multiplier',lambda d:d['position'].update(multiplier=200))):
        changed=deepcopy(raw); mutator(changed); row=run(changed)
        if label.startswith('reverse'):
            for key,value in result['portfolio'].items(): audit.near(row['portfolio'][key],-value,label+' '+key)
        elif label.startswith('add'):
            audit.near(row['portfolio']['delta_shares'],0,label)
            for key in ('gamma','vega_per_unit_sigma','calendar_theta_per_year'): audit.eq(row['portfolio'][key],result['portfolio'][key],label+' unchanged '+key)
        else:
            for key,value in result['portfolio'].items(): audit.near(row['portfolio'][key],2*value,label+' '+key)
        audit.eq(row['hedge'],result['hedge'],label+' independently one-call ledger unchanged')
        audit.interventions.append(label)
    spot_move=integral(dict(base,spot=123),8192)['call']-integral(base,8192)['call']
    mixed=integral(dict(base,spot=123,sigma=.255,tau=.75-1/252),8192)['call']-integral(base,8192)['call']
    audit.near(result['shock']['spot_only_exact_change'],spot_move,'spot repricing independent integral',atol=1e-7)
    audit.near(result['shock']['exact_repriced_change'],mixed,'mixed repricing independent integral',atol=1e-7)
    for ds in (-9,-3,-.3,0,.3,3,9):
        changed=deepcopy(raw); changed['shock'].update(spot_change=ds,vol_change=0,elapsed=0)
        row=run(changed)['shock']
        audit.true(abs(row['spot_only_exact_change']-row['spot_only_taylor_change'])<=row['spot_only_remainder_bound']+1e-11,'analytic Taylor bound '+str(ds))
    audit.true(abs(result['shock']['mixed_shock_residual'])>result['shock']['spot_only_remainder_bound'],'spot-only bound does not cover mixed shock')
    audit.interventions.append('signed spot perturbations and separate mixed-shock error')
    slope=-.0015; hs=.01
    total_fd=(integral(dict(base,spot=120+hs,sigma=.24+slope*hs),8192)['call']-
              integral(dict(base,spot=120-hs,sigma=.24-slope*hs),8192)['call'])/(2*hs)
    audit.near(total_fd,values['call_delta']+values['vega']*slope,'total calibrated-response delta',atol=2e-7)
    audit.near(values['call_delta']+values['vega']*slope,.417831841080851,'worked response slope')
    hedge_units=Fraction(6)/Fraction('0.02'); stock=-(Fraction(-100)+Fraction('.6')*hedge_units)
    residual=Fraction(-12000)+hedge_units*30
    audit.eq(hedge_units,300,'exercise2 gamma hedge'); audit.eq(stock,-80,'exercise2 stock hedge')
    audit.eq(residual,-3000,'exercise2 residual vega'); audit.eq(residual/100,-30,'exercise2 volatility point')
    audit.eq(Fraction('0.5')+30*Fraction('-.002'),Fraction('.44'),'exercise4 total delta')
    h=(3e-6/.003)**(1/3)
    audit.near(h,.1,'exercise9 optimal difference step')
    audit.near(.003*h*h/6+1e-6/h,.000015,'exercise9 minimum bound')
    audit.eq(Fraction(-2400)*Fraction('.02'),-48,'retention vega units')
    audit.eq(10000*Fraction('.2')*Fraction('.5')*Fraction('.03'),30,'retention gamma/vega')
    audit.groups.append('worked examples, portfolio scaling, controlled Taylor shocks, total response and rational problem anchors')

    iv=result['implied_volatility']; lo,hi=iv['bracket']
    audit.true(hi-lo<=1e-10 and lo<=iv['sigma']<=hi,'bounded volatility width')
    audit.true(iv['bracket_prices'][0]<=11.05<=iv['bracket_prices'][1],'computed price bracket')
    audit.near(integral(dict(base,sigma=iv['sigma']),8192)['call'],11.05,'IV independent repricing',atol=1e-8)
    audit.near(iv['sigma'],.3073774716758635,'worked3 inversion')
    atm=dict(spot=80,strike=80,tau=.25,rate=0,dividend=0,sigma=.4)
    # Integral of the density over [-.1,.1] is an independent closed-form ATM anchor.
    atm_quote=80*simpson(lambda x:math.exp(-x*x/2)/math.sqrt(2*math.pi),-.1,.1,1024)
    atm_iv=inverse(atm,atm_quote,2)
    audit.near(atm_quote,6.372453964324638,'exercise5 ATM price')
    audit.near(atm_iv['sigma'],.4,'exercise5 ATM inverse',atol=1e-10)
    audit.eq(Fraction('.05')/2,Fraction('.025'),'exercise5 finite lower-vega error bound')
    for sigma in (.1,.2,.5,1.2):
        price=integral(dict(base,sigma=sigma),8192)['call']
        got=inverse(base,price,2)
        audit.eq(got['status'],'bracketed','independent generated quote bracketed')
        audit.near(got['sigma'],sigma,'inverse of independent integral quote',atol=2e-8)
    a=values['prepaid_stock']; lower=max(a-values['discounted_strike'],0)
    boundary_cases=[(lower,'zero_volatility_limit'),(a,'upper_bound_has_no_finite_implied_volatility'),
                    (lower+iv['price_resolution']/2,'unresolved_near_price_boundary'),
                    (a-iv['price_resolution']/2,'unresolved_near_price_boundary')]
    for quote,status in boundary_cases:
        changed=deepcopy(raw); changed['iv']['call_price']=quote
        audit.eq(run(changed)['implied_volatility']['status'],status,'inverse quote boundary '+status)
    changed=deepcopy(raw); changed['iv']['sigma_cap']=.2; narrow=run(changed)
    audit.eq(narrow['implied_volatility']['status'],'root_above_declared_sigma_cap','cap is a scope boundary')
    audit.eq(narrow['smile']['weighted_butterfly_costs'],result['smile']['weighted_butterfly_costs'],'cap does not alter quote arbitrage arithmetic')
    audit.interventions.extend(['inverse exact and near-boundary statuses','lower inversion cap'])
    plus=inverse(base,11.06,2)['sigma']; minus=inverse(base,11.04,2)['sigma']
    audit.near((plus-minus)/.02,1/iv['vega_at_solution'],'local inverse conditioning',atol=2e-8)
    audit.interventions.append('price perturbation and inverse conditioning')
    for quote in (lower-.01,a+.01): audit.reject(lambda quote=quote:inverse(base,quote,2),'impossible quote')
    audit.groups.append('independent implied-volatility anchors, endpoint/cap classifications and local conditioning')

    smile=result['smile']
    audit.eq(smile['vertical_spread_screen_passes'],True,'worked4 vertical spreads')
    audit.eq(smile['convexity_screen_passes'],False,'worked4 convexity violation')
    audit.near(smile['weighted_butterfly_costs'][0],-1.5,'worked4 normalized butterfly')
    for strike,price,row in zip(raw['smile']['strikes'],raw['smile']['call_prices'],smile['individual_implied_volatilities']):
        audit.near(integral(dict(spot=100,strike=strike,tau=1,rate=0,dividend=0,sigma=row['sigma']),8192)['call'],price,'smile independent inverse',atol=1e-8)
    changed=deepcopy(raw); changed['smile']['call_prices'][1]=9; fixed=run(changed)
    audit.eq(fixed['smile']['convexity_screen_passes'],True,'repair finite convexity screen')
    audit.eq(fixed['implied_volatility'],iv,'other contract inverse unchanged')
    audit.interventions.append('middle smile quote correction')
    cost=Fraction(3,5)*17+Fraction(2,5)*5-13
    audit.eq(cost,Fraction(-4,5),'exercise8 uneven weighted cost')
    for s in (0,80,90,95,100,105,115,130,1000):
        payoff=Fraction(3,5)*max(s-90,0)+Fraction(2,5)*max(s-115,0)-max(s-100,0)
        expected=0 if s<=90 or s>=115 else Fraction(3,5)*(s-90) if s<=100 else Fraction(2,5)*(115-s)
        audit.eq(payoff,expected,'exercise8 exact piecewise payoff '+str(s))
        audit.true(payoff>=0,'exercise8 nonnegative payoff '+str(s))
    audit.groups.append('finite strike inequalities, independent smile inversions and exact uneven butterfly payoff')

    for label,mutate in (
        ('base funded ledger',lambda d:None),
        ('final stock loss',lambda d:d['hedge']['spots'].__setitem__(-1,95)),
        ('zero fees',lambda d:d['hedge'].update(interior_fee=0)),
        ('double fees',lambda d:d['hedge'].update(interior_fee=.004)),
        ('zero dividend reinvestment',lambda d:d['base'].update(dividend=0)),
        ('negative financing',lambda d:d['base'].update(rate=-.04))):
        changed=deepcopy(raw); mutate(changed); rows=run(changed)['hedge']['ledger']
        expected=ledger_oracle(changed['base'],changed['hedge'])
        for i,(actual,wanted) in enumerate(zip(rows,expected)):
            for key,value in wanted.items(): audit.near(actual[key],value,label+f' row{i} '+key,atol=2e-7)
            if 'self_financing_residual' in actual: audit.near(actual['self_financing_residual'],0,label+' self financing')
        if label=='final stock loss':
            audit.eq(rows[:-1],result['hedge']['ledger'][:-1],'later shock does not fund earlier trades')
            audit.near(rows[-1]['ideal_terminal_error'],-.696468323446986,'exercise6 terminal loss')
            audit.near(rows[-1]['funded_fee_terminal_error'],-.7959345696427071,'exercise6 fee-funded loss')
        if label=='zero fees': audit.near(rows[-1]['ideal_terminal_error'],rows[-1]['funded_fee_terminal_error'],'zero-fee identity')
        if label=='double fees':
            old=result['hedge']['ledger'][-1]
            audit.near(rows[-1]['ideal_terminal_error']-rows[-1]['funded_fee_terminal_error'],
                       2*(old['ideal_terminal_error']-old['funded_fee_terminal_error']),'linearity of funded fees')
        if label!='base funded ledger': audit.interventions.append(label)
    rows=result['hedge']['ledger']
    fees=math.fsum(row['fee']*math.exp(base['rate']*(base['tau']-row['date'])) for row in rows[:-1])
    audit.near(fees,.09946624619572315,'worked5 independently dated fee cost')
    audit.near(rows[-1]['ideal_terminal_error']-rows[-1]['funded_fee_terminal_error'],fees,'funded fee reconciliation')
    audit.near(rows[0]['wealth_before_trade']-rows[0]['call_mark'],1.6340190117303237,'exercise6 hidden withdrawal')
    weights=[Fraction(50),Fraction(200)]; actual=[Fraction('.3'),Fraction('.2')]
    expected=sum(Fraction('.5')*w*(Fraction('.25')**2-v*v) for w,v in zip(weights,actual))
    audit.eq(expected,Fraction('1.5625'),'exercise7 exact original weighted variance')
    audit.near(result['variance_account']['total_discounted_error'],float(expected),'variance worksheet original')
    changed=deepcopy(raw); changed['variance_account']['actual_sigmas'].reverse(); reverse=run(changed)['variance_account']
    expected=sum(Fraction('.5')*w*(Fraction('.25')**2-v*v) for w,v in zip(weights,reversed(actual)))
    audit.eq(expected,Fraction('-2.1875'),'exercise7 reversed weighted variance')
    audit.near(reverse['total_discounted_error'],float(expected),'variance worksheet reversed')
    audit.eq(reverse['time_average_actual_variance'],result['variance_account']['time_average_actual_variance'],'same unweighted average')
    audit.interventions.append('reverse actual variance order')
    audit.groups.append('expanded dated cash/trade/fee funding, loss paths, negative rate/yield interventions and rational variance weights')

    invalid=[]
    for key in base:
        for value in (True,'0.1',None,float('nan'),float('inf'),10**400):
            data=deepcopy(raw); data['base'][key]=value; invalid.append((data,'nonfinite/type '+key))
    for field,value in [('spot',0),('strike',0),('tau',0),('tau',5.1),('rate',-.21),('dividend',-.01),('sigma',0),('sigma',3.1)]:
        data=deepcopy(raw); data['base'][field]=value; invalid.append((data,'bounded base '+field))
    mutations=[lambda d:d.update(schema=True),lambda d:d.update(provenance=7),lambda d:d.update(extra=1),
               lambda d:d['position'].update(contracts=1.5),lambda d:d['position'].update(contracts=True),
               lambda d:d['position'].update(multiplier=0),lambda d:d['shock'].update(spot_change=-120),
               lambda d:d['shock'].update(vol_change=-.24),lambda d:d['shock'].update(elapsed=.75),
               lambda d:d['iv'].update(call_price=-1),lambda d:d['iv'].update(call_price=119),
               lambda d:d['iv'].update(sigma_cap=0),lambda d:d['smile'].update(strikes=[90,90,110]),
               lambda d:d['smile'].update(call_prices=[1,1,1]),lambda d:d['smile'].update(call_prices=[14,11]),
               lambda d:d['smile'].update(strikes='90,100,110'),lambda d:d['hedge'].update(interior_fee=-.01),
               lambda d:d['hedge'].update(times=[0,.25,.25,.75]),lambda d:d['hedge'].update(times=[0,.25,.5,.8]),
               lambda d:d['hedge'].update(spots=[120,126]),lambda d:d['hedge'].update(spots=[121,126,113,130]),
               lambda d:d['hedge'].update(times=[0,.25,.74999,.75]),
               lambda d:d['variance_account'].update(durations=[]),lambda d:d['variance_account'].update(actual_sigmas=[.3]),
               lambda d:d['variance_account'].update(discounted_cash_gammas=[50,-1]),
               lambda d:d['variance_account'].update(model_sigma=float('inf'))]
    for i,mutate in enumerate(mutations):
        data=deepcopy(raw); mutate(data); invalid.append((data,'financial malformed intervention '+str(i)))
    for section in ('base','position','shock','iv','smile','hedge','variance_account'):
        data=deepcopy(raw); data[section]=None; invalid.append((data,'wrong object '+section))
    for data,label in invalid: audit.reject(lambda data=data:run(data),label)
    audit.groups.append('strict finite bounded domain, bool/type/overflow/shape and financially infeasible input rejection')

    manifest=json.loads((ASSETS/(PREFIX+'-manifest.json')).read_text())
    expected_files={PREFIX+suffix for suffix in ('-inputs.json','-analysis.py','-output.json','-README.txt')}
    audit.eq({row['file'] for row in manifest['files']},expected_files,'four payload manifest coverage')
    for row in manifest['files']:
        body=(ASSETS/row['file']).read_bytes()
        audit.eq(len(body),row['bytes'],'manifest byte count '+row['file'])
        audit.eq(sha256(body).hexdigest(),row['sha256'],'manifest digest '+row['file'])
    with tempfile.TemporaryDirectory(prefix='c09 portable ') as temporary:
        directory=Path(temporary)
        for name in expected_files|{PREFIX+'-manifest.json'}: shutil.copyfile(ASSETS/name,directory/name)
        script=directory/(PREFIX+'-analysis.py'); source=directory/(PREFIX+'-inputs.json')
        for optimized in (False,True):
            command=[sys.executable]+(['-O'] if optimized else [])+[str(script),'--input',str(source)]
            cli=subprocess.run(command,cwd=directory,capture_output=True,text=True,timeout=30)
            audit.eq(cli.returncode,0,'portable normal/optimized success')
            audit.eq(cli.stderr,'','portable no diagnostics'); audit.eq(json.loads(cli.stdout),saved,'portable stdout full output')
            output=directory/'explicit result.json'
            cli=subprocess.run(command+['--output',str(output)],cwd=directory,capture_output=True,text=True,timeout=30)
            audit.eq(cli.returncode,0,'portable explicit output success'); audit.eq(cli.stdout,'','portable file output quiet')
            audit.eq(json.loads(output.read_text()),saved,'portable explicit file output')
            malformed=[json.dumps(invalid[0][0]),'{"schema":1,"schema":1}', '{"x":NaN}', json.dumps(raw).replace('"sigma": 0.24','"sigma": 1e400')]
            for text in malformed:
                bad=directory/'bad input.json'; bad.write_text(text); output.write_text('preserve prior result')
                cli=subprocess.run([sys.executable]+(['-O'] if optimized else [])+[str(script),'--input',str(bad),'--output',str(output)],cwd=directory,capture_output=True,text=True,timeout=30)
                audit.true(cli.returncode!=0,'portable bad data rejected'); audit.eq(cli.stdout,'','bad CLI no result');
                audit.eq(output.read_text(),'preserve prior result','invalid input preserves destination')
                audit.rejections+=1
    audit.groups.append('four-payload manifest and isolated five-file normal/-O stdout/file CLI with rejection preserving output')

    text=(ROOT/'content/chapters/v10-c09.html').read_text()
    fragment=Fragment(); fragment.feed(text)
    audit.eq(fragment.stack,[],'balanced static manuscript'); audit.eq(len(fragment.ids),len(set(fragment.ids)),'unique anchors')
    audit.eq(fragment.worked,5,'five worked examples'); audit.eq(fragment.exercises,10,'ten exact exercises'); audit.eq(fragment.solutions,10,'ten complete solutions')
    for i in range(1,11): audit.true('solution-'+str(i) in fragment.ids,'solution anchor '+str(i))
    for anchor in ('teach-back','sources','variance-mismatch','implied-volatility','funded-hedge'):
        audit.true(anchor in fragment.ids,'required teaching anchor '+anchor)
    sources=json.loads((ROOT/'content/reviews/v10-c09-sources.json').read_text())
    proposals={p['id'] for p in sources['proposals']}
    used={link.split('#')[1] for link in fragment.links if link.startswith('sources.html#')}
    audit.eq(used,proposals,'exact scoped source references')
    for name in expected_files|{PREFIX+'-manifest.json'}: audit.true(name in fragment.links,'download link '+name)
    for source in sources['proposals']:
        audit.true(all(source.get(k) for k in ('id','title','url','use','checked','verification')),'source scope complete')
    audit.groups.append('balanced original chapter, all problem/solution anchors, answered teaching and exact source/download references')
    author=ROOT/'content/reviews/v10-c09-author.json'
    bindings=0
    if author.exists():
        review=json.loads(author.read_text())
        paths={row['path'] for row in review['reviewed_hashes']}
        expected={'content/chapters/v10-c09.html','scripts/check_v10_c09.py','content/reviews/v10-c09-sources.json'}
        expected.update('content/projects/'+name for name in expected_files|{PREFIX+'-manifest.json'})
        audit.eq(paths,expected,'author exact eight nonself paths')
        for row in review['reviewed_hashes']:
            body=(ROOT/row['path']).read_bytes()
            audit.eq(len(body),row['bytes'],'author binding byte count '+row['path'])
            audit.eq(sha256(body).hexdigest(),row['sha256'],'author binding hash '+row['path'])
            bindings+=1
    summary={'chapter':PREFIX,'status':'passed','comparisons':audit.comparisons,
             'invalid_inputs_rejected':audit.rejections,'economic_interventions':audit.interventions,
             'worked_examples':5,'solved_exercises':10,'author_payload_hashes_verified':bindings,
             'groups':audit.groups,
             'limits':'Machine-assisted author verification, not peer/human certification or empirical hedge evidence. Quadrature and finite differences are numerical checks; mathematical proofs and assumptions are reviewed separately.'}
    json.dumps(summary,allow_nan=False)
    return summary


if __name__=='__main__':
    print(json.dumps(check(),indent=2,allow_nan=False))
