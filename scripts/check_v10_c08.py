"""Independent vanilla payoff integration, funded ledgers and c08 package checks."""
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
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
        require(actual == expected, f'{label}: {actual!r} != {expected!r}')

    def near(self, actual, expected, label, absolute=2e-10, relative=2e-10):
        self.comparisons += 1
        require(type(actual) in (int, float) and math.isfinite(actual), label + ': nonfinite result')
        require(abs(actual-expected) <= absolute+relative*abs(expected),
                f'{label}: {actual!r} != {expected!r}')

    def true(self, condition, label):
        self.comparisons += 1
        require(condition, label)


def normal(x):
    # NormalDist uses a different public interface from the model's erfc helper.
    # The principal price oracle below does not use any normal CDF at all.
    from statistics import NormalDist
    return NormalDist().cdf(x)


def simpson(function, low, high, panels):
    if low >= high:
        return 0.0
    step = (high-low)/panels
    total = function(low)+function(high)
    total += 4*math.fsum(function(low+i*step) for i in range(1,panels,2))
    total += 2*math.fsum(function(low+i*step) for i in range(2,panels,2))
    return total*step/3


def integral_prices(s, k, r, q, sigma, tau, panels=8192):
    """Terminal payoff integrals, not a reimplementation of the normal formula."""
    if tau == 0:
        return max(s-k, 0), max(k-s, 0)
    disc = math.exp(-r*tau)
    if s == 0 or sigma == 0:
        terminal = s*math.exp((r-q)*tau)
        return disc*max(terminal-k,0), disc*max(k-terminal,0)
    width = sigma*math.sqrt(tau)
    logmedian = math.log(s)+(r-q-sigma*sigma/2)*tau
    cutoff = (math.log(k)-logmedian)/width
    def stock(z):
        return math.exp(logmedian+width*z)
    def density(z):
        return math.exp(-z*z/2)/math.sqrt(2*math.pi)
    call = disc*simpson(lambda z:max(stock(z)-k,0)*density(z), max(-12,cutoff),12,panels)
    put = disc*simpson(lambda z:max(k-stock(z),0)*density(z),-12,min(12,cutoff),panels)
    return call, put


def values(case):
    return tuple(float(case[name]) for name in ('spot','strike','rate','dividend_yield','volatility','maturity'))


class Fragment(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack, self.ids, self.hrefs = [], [], []
        self.worked = self.exercises = self.solutions = 0
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        require(tag not in ('html','head','body','h1','script'), 'chapter must be a static fragment')
        if 'id' in attrs:
            self.ids.append(attrs['id'])
        if 'href' in attrs:
            self.hrefs.append(attrs['href'])
        if tag == 'aside' and 'worked' in attrs.get('class','').split():
            self.worked += 1
        if tag == 'li' and self.stack and self.stack[-1][0] == 'ol':
            if 'exercises' in self.stack[-1][1].get('class','').split():
                self.exercises += 1
            if any(t == 'details' and 'solutions' in a.get('class','').split() for t,a in self.stack):
                self.solutions += 1
        if tag not in ('br','hr','img','meta','link','input'):
            self.stack.append((tag,attrs))
    def handle_endtag(self, tag):
        require(self.stack and self.stack[-1][0] == tag, 'unbalanced HTML: '+tag)
        self.stack.pop()


def check():
    audit = Audit()
    raw = json.loads((ASSETS/'v10-c08-inputs.json').read_text(encoding='utf-8'))
    saved = json.loads((ASSETS/'v10-c08-output.json').read_text(encoding='utf-8'))
    before = deepcopy(raw)
    captured = StringIO()
    with redirect_stdout(captured), redirect_stderr(captured):
        model = runpy.run_path(str(ASSETS/'v10-c08-analysis.py'))
        result = model['run'](raw)
    audit.eq(captured.getvalue(), '', 'quiet import and run')
    audit.eq(raw, before, 'nonmutating API')
    audit.eq(result, saved, 'entire regenerated reference output')
    json.dumps(result, allow_nan=False)
    audit.eq(len(result['cases']),8,'eight original/boundary cases')
    audit.groups.append('quiet nonmutating strict API and full reference payload')

    for case in raw['cases']:
        label = case['id']; row = result['cases'][label]
        s,k,r,q,sigma,tau = params = values(case)
        mu = float(case['physical_drift'])
        fine = integral_prices(*params)
        coarse = integral_prices(*params,panels=4096)
        for name,expected,previous in zip(('call','put'),fine,coarse):
            audit.near(expected,previous,label+' quadrature grid '+name,absolute=1e-8,relative=0)
            audit.near(row[name],expected,label+' independent payoff integral '+name,absolute=2e-7,relative=0)
        a,b = s*math.exp(-q*tau), k*math.exp(-r*tau)
        audit.near(row['prepaid_stock'],a,label+' prepaid stock')
        audit.near(row['discounted_strike'],b,label+' strike PV')
        audit.near(row['call']-row['put'],a-b,label+' parity')
        audit.near(row['put_call_parity_residual'],0,label+' parity residual')
        for name,low,high in (('call',max(a-b,0),a),('put',max(b-a,0),b)):
            audit.near(row[name+'_lower_bound'],low,label+' lower bound')
            audit.near(row[name+'_upper_bound'],high,label+' upper bound')
            audit.true(low-1e-9 <= row[name] <= high+1e-9,label+' financial bounds '+name)
        audit.near(row['expected_terminal_stock_P'],s*math.exp(mu*tau),label+' P mean')
        audit.near(row['expected_terminal_stock_Q'],s*math.exp((r-q)*tau),label+' Q mean')
        audit.near(row['expected_discounted_ex_price_Q'],a,label+' discounted ex-price')
        # Integrate the expected dated dividends independently, including q=0.
        dividends = simpson(lambda u:q*s*math.exp(-q*u),0,tau,256)
        audit.near(row['expected_discounted_dividends_Q'],dividends,label+' integrated discounted receipts')
        audit.near(row['expected_discounted_total_gain_Q'],a+dividends,label+' total gains')
        if row['branch'] == 'positive_diffusion':
            width = sigma*math.sqrt(tau)
            logthreshold = (math.log(s/k)+(r-q-sigma*sigma/2)*tau)/width
            audit.near(row['probability_Q_itm'],normal(logthreshold),label+' Q probability')
            audit.near(row['probability_P_itm'],normal((math.log(s/k)+(mu-sigma*sigma/2)*tau)/width),label+' P probability')
            audit.near(row['market_price_of_risk'],(mu+q-r)/sigma,label+' lambda')
            audit.near(row['delta_call']-row['delta_put'],math.exp(-q*tau),label+' delta parity')
            audit.near(row['call_bank']+s*row['delta_call'],row['call'],label+' call funding')
            audit.near(row['put_bank']+s*row['delta_put'],row['put'],label+' put funding')
            audit.near(row['pde_call_residual'],0,label+' call PDE residual',absolute=2e-9)
            audit.near(row['pde_put_residual'],0,label+' put PDE residual',absolute=2e-9)
    audit.groups.append('independent terminal-payoff quadrature, dated dividend integration and model bounds')

    # Derivative oracle: finite differences of directly integrated payoffs.
    # Avoid expiry, deterministic kinks and the bounded input's edges.
    for index in (0,1,5):
        case=raw['cases'][index]; label=case['id']; row=result['cases'][label]
        s,k,r,q,sigma,tau = values(case)
        hs,ht = .01,.0001
        low=integral_prices(s-hs,k,r,q,sigma,tau)
        middle=integral_prices(s,k,r,q,sigma,tau)
        high=integral_prices(s+hs,k,r,q,sigma,tau)
        short=integral_prices(s,k,r,q,sigma,tau-ht)
        long=integral_prices(s,k,r,q,sigma,tau+ht)
        for n,name in enumerate(('call','put')):
            delta=(high[n]-low[n])/(2*hs)
            gamma=(high[n]-2*middle[n]+low[n])/(hs*hs)
            theta=(short[n]-long[n])/(2*ht)
            audit.near(row['delta_'+name],delta,label+' integrated delta '+name,absolute=2e-5,relative=2e-5)
            audit.near(row['gamma'],gamma,label+' integrated gamma '+name,absolute=2e-5,relative=2e-5)
            audit.near(row['theta_'+name],theta,label+' integrated calendar theta '+name,absolute=2e-5,relative=2e-5)
    audit.groups.append('finite differences of independent integrals for both option sensitivities')

    # Analytical worked/solution anchors and boundary semantics.
    base=result['cases']['dividend_call']
    symmetric=result['cases']['symmetric_zero_carry']
    audit.near(symmetric['call'],100*(2*normal(.1)-1),'exercise4 symmetric call')
    audit.near(symmetric['put'],symmetric['call'],'exercise4 symmetric put')
    audit.near(symmetric['delta_call'],normal(.1),'exercise4 delta')
    audit.near(symmetric['probability_Q_itm'],normal(-.1),'exercise4 Q event')
    audit.true(symmetric['delta_call']>symmetric['probability_Q_itm'],'zero-yield delta exceeds event probability')
    for name in ('delta_call','delta_put','gamma','theta_call','theta_put','call_bank','put_bank'):
        audit.eq(result['cases']['deterministic_kink'][name],None,'deterministic kink '+name)
        audit.eq(result['cases']['expiry'][name],None,'expiry no Greek '+name)
    audit.eq(result['cases']['deterministic_kink']['probability_Q_itm'],0,'strict event at deterministic strike')
    audit.near(result['cases']['absorbing']['put'],100*math.exp(.02),'zero-stock negative-rate put')
    audit.true(result['cases']['absorbing']['put']>100,'put can exceed undiscounted strike')
    audit.near(result['cases']['deterministic']['put'],math.exp(.02)*(100-90*math.exp(-.06)),'exercise8 certain put')
    audit.near(90*(math.exp(.04)-math.exp(-.02)),5.455089079706966,'exercise8 zero-volatility arbitrage')
    audit.near(-math.log(.96),.040821994520255166,'exercise10 carry-equivalent yield')
    audit.near(100*math.exp(math.log(.96)),96,'exercise10 prepaid match')
    audit.near(-4+4,0,'exercise10 dividend jump total gain')
    audit.near(50*math.exp(.02),51.01006700133779,'retention zero-stock put')
    audit.near((.08+.02-.04)/.30,.2,'retention tilt')
    audit.groups.append('worked examples, determinate exercises, strict events and degenerate-boundary semantics')

    # Rebuild the density ratio with interval normal densities, not saved logs.
    tilt=result['tilt']; lam=(.09+.015-.04)/.25
    hs=[float(x) for x in raw['tilt']['intervals']]
    xs=[float(x) for x in raw['tilt']['brownian_P_increments']]
    p_density=math.prod(math.exp(-x*x/(2*h))/math.sqrt(2*math.pi*h) for h,x in zip(hs,xs))
    q_density=math.prod(math.exp(-(x+lam*h)**2/(2*h))/math.sqrt(2*math.pi*h) for h,x in zip(hs,xs))
    audit.near(tilt['lambda'],lam,'tilt lambda')
    audit.near(tilt['density_Z'],q_density/p_density,'density product ratio')
    audit.eq(tilt['density_Z_underflow'],False,'ordinary tilt density representable')
    audit.near(tilt['log_density_Z'],math.log(q_density/p_density),'density log ratio')
    audit.near(tilt['log_joint_P_density'],math.log(p_density),'joint P density')
    audit.near(tilt['log_joint_Q_density_of_WP'],math.log(q_density),'joint Q density')
    audit.near(tilt['log_density_factorization_residual'],0,'density factorization')
    for actual,h,x in zip(tilt['Brownian_Q_increments_on_same_path'],hs,xs):
        audit.near(actual,x+lam*h,'same-path shifted increment')
    audit.near(tilt['mean_WP_terminal_under_Q'],-lam*sum(hs),'shifted WP mean')
    audit.near(tilt['variance_WP_terminal_under_Q'],sum(hs),'shifted WP variance')
    # Numerical Gaussian normalization is an illustration anchored by exact MGF.
    t=sum(hs)
    density_expectation=simpson(lambda z:math.exp(-lam*math.sqrt(t)*z-lam*lam*t/2)*math.exp(-z*z/2)/math.sqrt(2*math.pi),-12,12,4096)
    audit.near(tilt['E_P_Z_analytic'],density_expectation,'integrated density normalization')
    audit.near(math.exp(tilt['log_E_P_Z_squared_analytic']),math.exp(lam*lam*t),'exact second density moment')
    audit.groups.append('independent normal-density products and analytical normalization anchors')

    # Reconstruct ledger, including rebalance expenditures and initial borrowing.
    dates=[float(x) for x in raw['hedge']['dates']]
    spots=[float(x) for x in raw['hedge']['prices']]
    stock_count=math.exp(-.015*1.5)*normal((math.log(92/100)+(.04-.015+.25*.25/2)*1.5)/(.25*math.sqrt(1.5)))
    bank=integral_prices(92,100,.04,.015,.25,1.5)[0]-stock_count*92
    ledger=result['hedge']['ledger']
    audit.near(ledger[0]['shares_after'],stock_count,'initial hedge shares')
    audit.near(ledger[0]['bank_after'],bank,'initial hedge debt')
    for j in range(1,len(dates)):
        h=dates[j]-dates[j-1]; remaining=dates[-1]-dates[j]; s=spots[j]
        incoming=stock_count*math.exp(.015*h); grown=bank*math.exp(.04*h)
        wealth=incoming*s+grown
        if remaining:
            d=(math.log(s/100)+(.04-.015+.25*.25/2)*remaining)/(.25*math.sqrt(remaining))
            target=math.exp(-.015*remaining)*normal(d)
        else:
            target=0
        expenditure=(target-incoming)*s
        bank=grown-expenditure; stock_count=target
        call=integral_prices(s,100,.04,.015,.25,remaining)[0]
        expected={'time':dates[j],'spot':s,'incoming_shares':incoming,'bank_before_trade':grown,
                  'rebalance_expenditure':expenditure,'shares_after':target,'bank_after':bank,
                  'wealth':wealth,'call_mark':call,'hedge_error':wealth-call,'external_contribution':0}
        for key,value in expected.items():
            audit.near(ledger[j][key],value,'hedge row '+str(j)+' '+key,absolute=2e-8,relative=0)
        audit.near(ledger[j]['shares_after']*s+ledger[j]['bank_after'],wealth,'funding identity '+str(j),absolute=2e-8,relative=0)
    audit.near(result['hedge']['terminal_error'],bank-max(spots[-1]-100,0),'terminal hedge error',absolute=2e-8,relative=0)
    audit.groups.append('full dividend-reinvestment and signed-bank ledger reconstructed independently')

    def changed(edit):
        data=deepcopy(raw); edit(data)
        quiet=StringIO()
        with redirect_stdout(quiet),redirect_stderr(quiet):
            out=model['run'](data)
        require(quiet.getvalue()=='','intervention API printed')
        return out

    forecast=changed(lambda d:d['cases'][0].__setitem__('physical_drift','0.19'))
    for field in ('call','put','delta_call','delta_put','probability_Q_itm','call_bank','put_bank'):
        audit.eq(forecast['cases']['dividend_call'][field],base[field],'physical drift preserves '+field)
    audit.near(forecast['cases']['dividend_call']['market_price_of_risk'],.66,'exercise5 changed lambda')
    audit.near(forecast['cases']['dividend_call']['probability_P_itm'],normal((math.log(.92)+(.19-.25**2/2)*1.5)/(.25*math.sqrt(1.5))),'exercise5 changed physical probability')
    audit.eq(forecast['hedge'],result['hedge'],'physical drift does not alter executed ledger')
    neutral=changed(lambda d:d['cases'][0].__setitem__('physical_drift','0.025'))
    audit.near(neutral['tilt']['density_Z'],1,'zero-risk-premium density')
    audit.near(neutral['cases']['dividend_call']['probability_P_itm'],base['probability_Q_itm'],'P=Q when total drift equals bank rate')
    audit.eq(neutral['tilt']['Brownian_Q_increments_on_same_path'],xs,'zero tilt leaves increments')
    no_div=changed(lambda d:d['cases'][0].__setitem__('dividend_yield','0'))
    audit.true(no_div['cases']['dividend_call']['call']>base['call'],'lower dividends increase call')
    audit.eq(no_div['cases']['dividend_call']['expected_discounted_dividends_Q'],0,'zero dividend receipts')
    audit.near(no_div['hedge']['ledger'][1]['incoming_shares'],no_div['hedge']['ledger'][0]['shares_after'],'zero dividend share growth')
    higher_vol=changed(lambda d:d['cases'][0].__setitem__('volatility','0.35'))
    audit.true(higher_vol['cases']['dividend_call']['call']>base['call'],'higher sigma raises call')
    audit.true(higher_vol['cases']['dividend_call']['put']>base['put'],'higher sigma raises put')
    lower_rate=changed(lambda d:d['cases'][0].__setitem__('rate','-0.01'))
    audit.true(lower_rate['cases']['dividend_call']['call']<base['call'],'lower rate lowers European call')
    audit.true(lower_rate['cases']['dividend_call']['put']>base['put'],'lower rate raises European put')
    down=changed(lambda d:d['hedge']['prices'].__setitem__(-1,'40'))
    audit.eq(down['hedge']['ledger'][:-1],result['hedge']['ledger'][:-1],'terminal intervention preserves earlier cash')
    terminal40=ledger[2]['shares_after']*math.exp(.0075)*40+ledger[2]['bank_after']*math.exp(.02)
    audit.near(down['hedge']['terminal_error'],terminal40,'exercise11 terminal debt')
    audit.near(terminal40,-7.902181202079438,'exercise11 signed error')
    audit.eq(down['hedge']['ledger'][-1]['call_mark'],0,'exercise11 no exercise payoff')
    itm=changed(lambda d:d['cases'][2].__setitem__('spot','120'))['cases']['deterministic']
    audit.near(itm['call'],120*math.exp(-.04)-100*math.exp(.02),'deterministic ITM call')
    audit.eq(itm['put'],0,'deterministic OTM put')
    audit.near(itm['delta_call'],math.exp(-.04),'deterministic affine delta')
    audit.near(itm['call_bank'],-100*math.exp(.02),'deterministic bank leg')
    expiry=changed(lambda d:d['cases'][4].__setitem__('spot','120'))['cases']['expiry']
    audit.eq(expiry['call'],20,'expiry intrinsic call')
    audit.eq(expiry['probability_Q_itm'],1,'strict event at ITM expiry')
    # A high-yield, deep ITM case refutes a universal delta/probability ordering.
    def high_yield(data):
        data['cases'][7].update(spot='1000',strike='1',rate='0',dividend_yield='0.2',volatility='0.05',maturity='5')
    ordering=changed(high_yield)['cases']['extreme_tail']
    audit.true(ordering['delta_call']<ordering['probability_Q_itm'],'exercise4 no universal delta/event ordering')
    def density_underflow(data):
        data['cases'][0].update(rate='-0.1',dividend_yield='0.2',volatility='0.05',maturity='5',physical_drift='0.4')
        data['tilt'].update(intervals=['0.625']*8,brownian_P_increments=['5']*8)
        data['hedge']['dates']=['0','1','3','5']
    tiny=changed(density_underflow)['tilt']
    audit.near(tiny['log_density_Z'],-1050,'extreme density retains finite log')
    audit.eq(tiny['density_Z'],None,'underflow is unavailable density rather than zero probability')
    audit.eq(tiny['density_Z_underflow'],True,'density underflow flag')
    audit.near(tiny['log_density_factorization_residual'],0,'extreme density factorization',absolute=1e-9)
    for key in ('negative_rate','absorbing','expiry','symmetric_zero_carry','deterministic_kink','extreme_tail'):
        audit.eq(forecast['cases'][key],result['cases'][key],'unrelated case preserved '+key)
    audit.groups.append('economic interventions: drift, dividends, volatility, rates, deterministic/expiry branches and hedge loss')

    stress_cases=[(1,1000,-.1,.2,.05,.02),(1000,1,.3,0,.05,5),
                  (1000,1000,-.1,.2,.8,5),(1,1,.3,0,.8,5),
                  (600,1000,-.1,0,.8,5),(1000,600,.3,.2,.05,5),
                  (99,100,.3,0,.05,.02),(100,99,-.1,.2,.8,.02)]
    for j,params in enumerate(stress_cases):
        def stress(data):
            data['cases'][7].update({name:str(value) for name,value in zip(('spot','strike','rate','dividend_yield','volatility','maturity'),params)})
        actual=changed(stress)['cases']['extreme_tail']
        for name,expected in zip(('call','put'),integral_prices(*params)):
            audit.near(actual[name],expected,'bounded-domain stress '+str(j)+' '+name,absolute=2e-7,relative=0)
        audit.near(actual['put_call_parity_residual'],0,'stress parity '+str(j),absolute=1e-9)
    audit.groups.append('independent quadrature at short/long, high/low-volatility and deep-tail domain stresses')

    invalid=[
        ('unknown top key',lambda d:d.__setitem__('extra',0)),
        ('wrong schema',lambda d:d.__setitem__('schema','bad')),
        ('empty cases',lambda d:d.__setitem__('cases',[])),
        ('too many cases',lambda d:d['cases'].append(deepcopy(d['cases'][0]))),
        ('case wrong keys',lambda d:d['cases'][0].__setitem__('fee',0)),
        ('duplicate id',lambda d:d['cases'][1].__setitem__('id',d['cases'][0]['id'])),
        ('invalid id',lambda d:d['cases'][1].__setitem__('id','../escape')),
        ('bool number',lambda d:d['cases'][0].__setitem__('spot',True)),
        ('NaN string',lambda d:d['cases'][0].__setitem__('spot','NaN')),
        ('infinite float',lambda d:d['cases'][0].__setitem__('spot',float('inf'))),
        ('NaN float',lambda d:d['cases'][0].__setitem__('rate',float('nan'))),
        ('scientific notation',lambda d:d['cases'][0].__setitem__('rate','1e-2')),
        ('decimal precision',lambda d:d['cases'][0].__setitem__('rate','0.123456789')),
        ('leading zero',lambda d:d['cases'][0].__setitem__('spot','092')),
        ('leading plus',lambda d:d['cases'][0].__setitem__('spot','+92')),
        ('numeric whitespace',lambda d:d['cases'][0].__setitem__('spot',' 92')),
        ('huge integer',lambda d:d['cases'][0].__setitem__('spot',10**40)),
        ('numeric null',lambda d:d['cases'][0].__setitem__('spot',None)),
        ('negative spot',lambda d:d['cases'][0].__setitem__('spot','-1')),
        ('too-small spot',lambda d:d['cases'][0].__setitem__('spot','0.5')),
        ('zero strike',lambda d:d['cases'][0].__setitem__('strike','0')),
        ('too-high strike',lambda d:d['cases'][0].__setitem__('strike','1001')),
        ('rate boundary',lambda d:d['cases'][0].__setitem__('rate','-0.10000001')),
        ('negative dividend',lambda d:d['cases'][0].__setitem__('dividend_yield','-0.01')),
        ('too-high dividend',lambda d:d['cases'][0].__setitem__('dividend_yield','0.20000001')),
        ('too-small sigma',lambda d:d['cases'][0].__setitem__('volatility','0.01')),
        ('too-high sigma',lambda d:d['cases'][0].__setitem__('volatility','0.81')),
        ('too-small horizon',lambda d:d['cases'][0].__setitem__('maturity','0.01')),
        ('too-long horizon',lambda d:d['cases'][0].__setitem__('maturity','6')),
        ('physical drift bound',lambda d:d['cases'][0].__setitem__('physical_drift','0.41')),
        ('deterministic arbitrage',lambda d:d['cases'][2].__setitem__('physical_drift','0')),
        ('tilt unknown case',lambda d:d['tilt'].__setitem__('case_id','unknown')),
        ('tilt degenerate case',lambda d:d['tilt'].__setitem__('case_id','absorbing')),
        ('tilt wrong keys',lambda d:d['tilt'].__setitem__('mu',0)),
        ('tilt short list',lambda d:d['tilt'].__setitem__('intervals',['1.5'])),
        ('tilt interval sum',lambda d:d['tilt'].__setitem__('intervals',['0.4','0.5','0.5'])),
        ('tilt length mismatch',lambda d:d['tilt'].__setitem__('brownian_P_increments',['0','0'])),
        ('tilt increment boundary',lambda d:d['tilt']['brownian_P_increments'].__setitem__(0,'5.00000001')),
        ('tilt bool interval',lambda d:d['tilt']['intervals'].__setitem__(0,False)),
        ('hedge unknown case',lambda d:d['hedge'].__setitem__('case_id','unknown')),
        ('hedge degenerate case',lambda d:d['hedge'].__setitem__('case_id','expiry')),
        ('hedge repeated date',lambda d:d['hedge']['dates'].__setitem__(1,'0')),
        ('hedge missing origin',lambda d:d['hedge']['dates'].__setitem__(0,'0.1')),
        ('hedge short interval',lambda d:d['hedge']['dates'].__setitem__(1,'0.01')),
        ('hedge wrong endpoint',lambda d:d['hedge']['dates'].__setitem__(-1,'1.6')),
        ('hedge initial spot mismatch',lambda d:d['hedge']['prices'].__setitem__(0,'93')),
        ('hedge nonpositive price',lambda d:d['hedge']['prices'].__setitem__(-1,'0')),
        ('hedge vector mismatch',lambda d:d['hedge']['prices'].pop()),
        ('hedge nonlist',lambda d:d['hedge'].__setitem__('prices','92,97,88,110')),
    ]
    for label,edit in invalid:
        try:
            changed(edit)
        except ValueError:
            audit.rejections += 1
        else:
            raise AssertionError('invalid input accepted: '+label)
    for bad in (None,[],True):
        try:
            model['run'](bad)
        except ValueError:
            audit.rejections += 1
        else:
            raise AssertionError('invalid top-level type accepted')
    audit.groups.append('malformed JSON-shaped inputs and economic-domain rejection under normal or optimized Python')

    expected_files={'v10-c08-'+end for end in ('inputs.json','analysis.py','output.json','README.txt')}
    manifest=json.loads((ASSETS/'v10-c08-manifest.json').read_text())
    audit.eq(manifest['schema'],'v10-c08-manifest-1','manifest schema')
    audit.eq(len(manifest['files']),4,'exact four manifest payloads')
    audit.eq({entry['file'] for entry in manifest['files']},expected_files,'manifest scope')
    for entry in manifest['files']:
        payload=(ASSETS/entry['file']).read_bytes()
        audit.eq(len(payload),entry['bytes'],'manifest size '+entry['file'])
        audit.eq(sha256(payload).hexdigest(),entry['sha256'],'manifest hash '+entry['file'])
    with tempfile.TemporaryDirectory(prefix='v10-c08-') as temporary:
        temp=Path(temporary); source=temp/'source'; source.mkdir(); cwd=temp/'elsewhere'; cwd.mkdir()
        for name in expected_files:
            shutil.copyfile(ASSETS/name,source/name)
        script=source/'v10-c08-analysis.py'; input_file=source/'v10-c08-inputs.json'
        for flags in ([],['-O']):
            prefix=[sys.executable]+flags+[str(script)]
            command=prefix+['--input',str(input_file)]
            proc=subprocess.run(command,cwd=cwd,capture_output=True,text=True,check=True)
            audit.eq(json.loads(proc.stdout),saved,'portable stdout CLI '+str(flags))
            audit.eq(proc.stderr,'','portable successful stderr')
            out=cwd/('optimized.json' if flags else 'normal.json')
            proc=subprocess.run(command+['--output',str(out)],cwd=cwd,capture_output=True,text=True,check=True)
            audit.eq(proc.stdout,'','output-file CLI quiet')
            audit.eq(proc.stderr,'','output-file CLI stderr quiet')
            audit.eq(json.loads(out.read_text()),saved,'portable output file '+str(flags))
            proc=subprocess.run(prefix,cwd=cwd,capture_output=True,text=True,check=True)
            audit.eq(json.loads(proc.stdout),saved,'default input relative to script '+str(flags))
            invalid_json=['{"schema":"x","schema":"y"}','{"spot":NaN}','{"spot":Infinity}']
            broken=deepcopy(raw); broken['cases'][2]['physical_drift']='0'
            invalid_json.append(json.dumps(broken))
            for j,text in enumerate(invalid_json):
                bad=source/'bad.json'; bad.write_text(text)
                forbidden=cwd/('bad-output-'+str(j)+str(bool(flags))+'.json')
                proc=subprocess.run(prefix+['--input',str(bad),'--output',str(forbidden)],cwd=cwd,capture_output=True,text=True)
                require(proc.returncode!=0 and proc.stderr and not proc.stdout and not forbidden.exists(), 'invalid CLI input must fail before writing')
                audit.rejections += 1
    audit.groups.append('four-payload manifest and isolated normal/-O explicit/default input and output CLIs')

    body=(ROOT/'content/chapters/v10-c08.html').read_text(encoding='utf-8')
    fragment=Fragment();fragment.feed(body);fragment.close()
    require(not fragment.stack,'unclosed HTML tags')
    audit.eq(len(fragment.ids),len(set(fragment.ids)),'unique chapter anchors')
    audit.eq((fragment.worked,fragment.exercises,fragment.solutions),(4,12,12),'complete chapter counts')
    required={'capability','market','pde','measure','martingale','formula','verification','boundaries','lab','exercises','teach-back','sources'}
    audit.true(required <= set(fragment.ids),'substantive chapter sections')
    audit.true('Model answer.' in body and 'Delayed retention' in body and 'Answers.' in body,'answered teaching checks')
    proposed=json.loads((ROOT/'content/reviews/v10-c08-sources.json').read_text())['proposals']
    expected_sources={'v10-c08-haugh-bs','v10-c08-haugh-measure','v10-c08-mit-lecture'}
    audit.eq({p['id'] for p in proposed},expected_sources,'proposed source IDs')
    for source_id in expected_sources:
        audit.true('sources.html#'+source_id in fragment.hrefs,'source linked '+source_id)
    for name in expected_files | {'v10-c08-manifest.json'}:
        audit.true(name in fragment.hrefs,'portable payload linked '+name)
    for n in range(1,13):
        audit.true('exercise-'+str(n) in fragment.ids and 'solution-'+str(n) in fragment.ids,'paired exercise '+str(n))
    # Author record is generated only after the first successful calculation pass.
    # Its own hash cannot be included in itself; all other eight owned files bind.
    bound=0; author=ROOT/'content/reviews/v10-c08-author.json'
    if author.exists():
        entries=json.loads(author.read_text())['reviewed_hashes']
        expected_paths={'content/chapters/v10-c08.html','scripts/check_v10_c08.py','content/reviews/v10-c08-sources.json'}
        expected_paths |= {'content/projects/'+name for name in expected_files | {'v10-c08-manifest.json'}}
        require(len(entries)==8 and {e['path'] for e in entries}==expected_paths,'author must bind exactly eight nonself payloads')
        for entry in entries:
            payload=(ROOT/entry['path']).read_bytes()
            require(len(payload)==entry['bytes'] and sha256(payload).hexdigest()==entry['sha256'],'stale author hash: '+entry['path'])
            bound+=1
    audit.groups.append('balanced static HTML, complete problem/solution anchors, scoped citations and author payload bindings')
    return {'status':'passed','independent_comparisons':audit.comparisons,
            'invalid_inputs_rejected':audit.rejections,'worked_examples':4,'solved_exercises':12,
            'author_payload_hashes_verified':bound,'groups':audit.groups,
            'limits':'Author checks, not separate peer/human certification or empirical validation; no visual UI QA. Quadrature is a numerical oracle with documented absolute tolerances, not a stochastic proof.'}


if __name__ == '__main__':
    print(json.dumps(check(),indent=2,allow_nan=False))
