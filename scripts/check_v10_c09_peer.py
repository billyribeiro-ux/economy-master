"""Separate c09 peer audit using Gauss-Legendre payoffs and discounted cash."""
from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
from fractions import Fraction as Q
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
AUTHOR_PATHS = ['content/chapters/v10-c09.html'] + [
    'content/projects/v10-c09-'+s for s in ('inputs.json','analysis.py','output.json','manifest.json','README.txt')
] + ['scripts/check_v10_c09.py','content/reviews/v10-c09-author.json','content/reviews/v10-c09-sources.json']
PEER_PATHS = ['scripts/check_v10_c09_peer.py','content/reviews/v10-c09-peer.json']


def require(ok, label):
    if not ok:
        raise AssertionError(label)


class Audit:
    def __init__(self):
        self.comparisons = 0
        self.rejections = 0
        self.interventions = []
        self.groups = []

    def eq(self, actual, expected, label):
        self.comparisons += 1
        require(actual == expected, label+': '+repr(actual)+' != '+repr(expected))

    def true(self, ok, label):
        self.comparisons += 1
        require(ok, label)

    def near(self, actual, expected, label, atol=3e-9, rtol=3e-11):
        self.comparisons += 1
        require(type(actual) in (float,int) and math.isfinite(actual), label+': finite number')
        require(abs(actual-float(expected)) <= atol+rtol*abs(float(expected)),
                label+': '+repr(actual)+' != '+repr(expected))

    def reject(self, run, data, label):
        before = deepcopy(data)
        try:
            run(data)
        except ValueError:
            self.rejections += 1
        else:
            raise AssertionError(label+': invalid input accepted')
        # NaN cannot be compared by ordinary equality after a deep copy.
        self.eq(repr(data), repr(before), label+': rejected input unchanged')


def gauss_nodes(n):
    """Construct a Gauss-Legendre rule, independently of author Simpson code."""
    pairs = []
    for j in range(1,n+1):
        x = math.cos(math.pi*(j-.25)/(n+.5))
        for _ in range(30):
            p0,p1 = 1.0,x
            for k in range(2,n+1):
                p0,p1 = p1,((2*k-1)*x*p1-(k-1)*p0)/k
            derivative = n*(x*p1-p0)/(x*x-1)
            step = p1/derivative
            x -= step
            if abs(step) < 2e-16:
                break
        p0,p1 = 1.0,x
        for k in range(2,n+1):
            p0,p1 = p1,((2*k-1)*x*p1-(k-1)*p0)/k
        derivative = n*(x*p1-p0)/(x*x-1)
        pairs.append((x,2/((1-x*x)*derivative*derivative)))
    return pairs


RULES = {n: gauss_nodes(n) for n in (12,20)}


def integrate(function, low, high, order=20):
    if high <= low:
        return 0.0
    count = max(1,math.ceil(high-low))
    width = (high-low)/count
    terms = []
    for i in range(count):
        middle = low+(i+.5)*width
        terms.extend(weight*function(middle+x*width/2)*width/2 for x,weight in RULES[order])
    return math.fsum(terms)


def payoff(p, order=20):
    """Discounted lognormal payoffs and pathwise first derivatives; no CDF."""
    s,k,t,r,q,v = (p[key] for key in ('spot','strike','tau','rate','dividend','sigma'))
    a,h = s*math.exp(-q*t),k*math.exp(-r*t)
    if s == 0 or t == 0 or v == 0:
        return {'call':max(a-h,0),'put':max(h-a,0)}
    scale = v*math.sqrt(t)
    drift = (r-q-v*v/2)*t
    trigger = (math.log(k/s)-drift)/scale
    low,high = -12.0,max(12.0,scale+12.0)
    split = min(high,max(low,trigger))
    disc = math.exp(-r*t)
    def density(z):
        return math.exp(-z*z/2)/math.sqrt(2*math.pi)
    def terminal(z):
        return s*math.exp(drift+scale*z)
    return {
        'call':disc*integrate(lambda z:max(terminal(z)-k,0)*density(z),split,high,order),
        'put':disc*integrate(lambda z:max(k-terminal(z),0)*density(z),low,split,order),
        'call_delta':disc*integrate(lambda z:terminal(z)/s*density(z),split,high,order),
        'put_delta':-disc*integrate(lambda z:terminal(z)/s*density(z),low,split,order),
        'vega':disc*integrate(lambda z:terminal(z)*(math.sqrt(t)*z-v*t)*density(z),split,high,order),
    }


def first_difference(function, x, h):
    return (function(x-2*h)-8*function(x-h)+8*function(x+h)-function(x+2*h))/(12*h)


def greeks(p):
    row = payoff(p)
    hs = .0001*p['spot']
    ht = min(.0001,p['tau']/40)
    row['gamma'] = first_difference(lambda s:payoff(dict(p,spot=s))['call_delta'],p['spot'],hs)
    row['call_theta'] = -first_difference(lambda t:payoff(dict(p,tau=t))['call'],p['tau'],ht)
    row['put_theta'] = -first_difference(lambda t:payoff(dict(p,tau=t))['put'],p['tau'],ht)
    return row


def replace(data, path, value):
    out = deepcopy(data)
    obj = out
    for key in path[:-1]:
        obj = obj[key]
    obj[path[-1]] = value
    return out


def audit_ledger(a, data, out, label):
    p,spec = data['base'],data['hedge']
    first = payoff(p)
    initial_cash = first['call']-p['spot']*first['call_delta']
    bank_pv = initial_cash
    fee_pv = 0.0
    # Reinvested shares are constant after multiplication by exp(-q*t).
    shares_without_reinvestment = first['call_delta']
    a.near(out['initial_price'],first['call'],label+' initial premium')
    a.near(out['initial_shares'],shares_without_reinvestment,label+' initial delta integral')
    a.near(out['initial_bank'],initial_cash,label+' initial cash')
    a.eq(len(out['ledger']),len(spec['times'])-1,label+' dated rows')
    for i,row in enumerate(out['ledger'],1):
        t,s = spec['times'][i],spec['spots'][i]
        discount = math.exp(-p['rate']*t)
        h = shares_without_reinvestment*math.exp(p['dividend']*t)
        bank = bank_pv/discount
        wealth = h*s+bank
        mark = payoff(dict(p,spot=s,tau=p['tau']-t))
        for key,value in {'date':t,'spot':s,'incoming_shares_after_dividends':h,
                          'incoming_bank':bank,'wealth_before_trade':wealth,'call_mark':mark['call']}.items():
            a.near(row[key],value,label+' dated cash '+key)
        if i < len(spec['times'])-1:
            target = mark['call_delta']
            trade = (target-h)*s
            fee = abs(trade)*spec['interior_fee']
            bank_pv -= discount*trade
            fee_pv += discount*fee
            shares_without_reinvestment = target*math.exp(-p['dividend']*t)
            wanted = {'target_shares':target,'stock_trade_cash':trade,'fee':fee,
                      'ideal_bank_after_trade':bank_pv/discount,
                      'bank_with_fees_after_trade':(bank_pv-fee_pv)/discount,
                      'self_financing_residual':0,'unhedged_mark_difference':wealth-mark['call']}
        else:
            obligation = max(s-p['strike'],0)
            wanted = {'payoff':obligation,'ideal_terminal_error':wealth-obligation,
                      'funded_fee_terminal_error':wealth-obligation-fee_pv/discount}
        for key,value in wanted.items():
            a.near(row[key],value,label+' discounted cash '+key,atol=2e-8)
    terminal = out['ledger'][-1]
    a.near(terminal['ideal_terminal_error']-terminal['funded_fee_terminal_error'],
           fee_pv*math.exp(p['rate']*p['tau']),label+' independently funded fee total')


def audit_inverse(a, p, row, label):
    lo_price = max(p['spot']*math.exp(-p['dividend']*p['tau'])-p['strike']*math.exp(-p['rate']*p['tau']),0)
    hi_price = p['spot']*math.exp(-p['dividend']*p['tau'])
    a.near(row['lower_price_bound'],lo_price,label+' lower value limit')
    a.near(row['upper_price_bound'],hi_price,label+' upper value limit')
    if row['status'] != 'bracketed':
        return
    lo,hi = row['bracket']
    a.true(0 <= lo <= row['sigma'] <= hi <= row['sigma_cap'],label+' sigma containment')
    a.true(hi-lo <= 1.00001e-10,label+' volatility width')
    left = payoff(dict(p,sigma=lo))['call']
    right = payoff(dict(p,sigma=hi))['call']
    center = payoff(dict(p,sigma=row['sigma']))
    a.near(row['bracket_prices'][0],left,label+' independent left price',atol=1e-10)
    a.near(row['bracket_prices'][1],right,label+' independent right price',atol=1e-10)
    a.true(left-1e-10 <= row['quote'] <= right+1e-10,label+' independent numerical bracket')
    a.near(row['price_residual'],center['call']-row['quote'],label+' independent residual',atol=1e-10)
    a.near(row['vega_at_solution'],center['vega'],label+' pathwise inverse vega')
    if center['vega'] > 1e-12:
        a.near(row['local_sigma_change_per_price_unit'],1/center['vega'],label+' local inverse slope')
    else:
        a.eq(row['local_sigma_change_per_price_unit'],None,label+' no finite reported inverse scale')
    a.true(1 <= row['iterations'] <= 80,label+' bounded iterations')


def audit_smile(a, data, result, label):
    smile = data['smile']
    strikes = list(map(lambda x:Q(str(x)),smile['strikes']))
    prices = list(map(lambda x:Q(str(x)),smile['call_prices']))
    slopes = [(prices[i+1]-prices[i])/(strikes[i+1]-strikes[i]) for i in range(len(prices)-1)]
    costs = []
    for i in range(1,len(prices)-1):
        left = (strikes[i+1]-strikes[i])/(strikes[i+1]-strikes[i-1])
        costs.append(left*prices[i-1]+(1-left)*prices[i+1]-prices[i])
    for got,want in zip(result['adjacent_price_slopes'],slopes):
        a.near(got,want,label+' exact vertical slope')
    for got,want in zip(result['weighted_butterfly_costs'],costs):
        a.near(got,want,label+' exact butterfly cost')
    discount = math.exp(-smile['rate']*smile['tau'])
    a.eq(result['vertical_spread_screen_passes'],all(-discount-1e-12 <= float(x) <= 1e-12 for x in slopes),label+' vertical screen')
    a.eq(result['convexity_screen_passes'],all(float(x) >= -1e-12 for x in costs),label+' convexity screen')
    for k,row in zip(smile['strikes'],result['individual_implied_volatilities']):
        p = {x:smile[x] for x in ('spot','tau','rate','dividend')}
        audit_inverse(a,dict(p,strike=k),row,label+' individual quote')


def audit_variance(a, data, out, label):
    spec = data['variance_account']
    dt,w,v = [list(map(lambda x:Q(str(x)),spec[k])) for k in ('durations','discounted_cash_gammas','actual_sigmas')]
    model = Q(str(spec['model_sigma']))
    contribution = [t*weight*(model-model_actual)*(model+model_actual) for t,weight,model_actual in zip(dt,w,v)]
    for actual,expected in zip(out['contributions'],contribution):
        a.near(actual,expected,label+' difference of squares')
    a.near(out['total_discounted_error'],sum(contribution),label+' exact weighted error')
    a.near(out['time_average_actual_variance'],sum(t*x*x for t,x in zip(dt,v))/sum(dt),label+' time weighted variance')


class Fragment(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack=[];self.ids=[];self.hrefs=[];self.worked=0;self.problems=0;self.answers=0
    def handle_starttag(self, tag, attrs):
        x = dict(attrs)
        require(tag not in ('html','head','body','h1','script'),'static chapter fragment')
        if 'id' in x:self.ids.append(x['id'])
        if 'href' in x:self.hrefs.append(x['href'])
        if 'worked' in x.get('class','').split():self.worked+=1
        if tag=='li' and self.stack and self.stack[-1][0]=='ol':
            if 'exercises' in self.stack[-1][1].get('class','').split():self.problems+=1
            if any(t=='details' and 'solutions' in a.get('class','').split() for t,a in self.stack):self.answers+=1
        if tag not in ('br','hr','img','meta','link','input'):self.stack.append((tag,x))
    def handle_endtag(self, tag):
        require(self.stack and self.stack[-1][0]==tag,'balanced HTML '+tag)
        self.stack.pop()


def check():
    a = Audit()
    raw = json.loads((ASSETS/(PREFIX+'-inputs.json')).read_text())
    initial = deepcopy(raw)
    capture = StringIO()
    with redirect_stdout(capture),redirect_stderr(capture):
        module = runpy.run_path(str(ASSETS/(PREFIX+'-analysis.py')))
        run = module['run']
        result = run(raw)
    a.eq(capture.getvalue(),'','quiet import and API')
    a.eq(raw,initial,'baseline input unchanged')
    a.eq(json.loads(json.dumps(result,allow_nan=False)),result,'strict finite JSON result')
    a.eq(result,json.loads((ASSETS/(PREFIX+'-output.json')).read_text()),'saved output secondary reproducibility check')
    for n in RULES:
        for power in (0,1,2,4,8,16):
            expected = 0 if power%2 else 2/(power+1)
            a.near(math.fsum(w*x**power for x,w in RULES[n]),expected,'Gaussian rule polynomial moment',atol=2e-14,rtol=0)
    p = raw['base']
    cases = [p,dict(spot=85,strike=90,tau=.5,rate=.01,dividend=.02,sigma=.3),
             dict(spot=100,strike=105,tau=.4,rate=-.075,dividend=.04,sigma=.6),
             dict(spot=10000,strike=1,tau=5,rate=.2,dividend=0,sigma=3),
             dict(spot=1,strike=10000,tau=.0001,rate=-.2,dividend=.2,sigma=.0001),
             dict(spot=100,strike=100,tau=.0001,rate=0,dividend=0,sigma=.2),
             dict(spot=100,strike=50,tau=1,rate=0,dividend=.2,sigma=.1),
             dict(spot=150,strike=100,tau=1,rate=-.1,dividend=0,sigma=.1)]
    for i,case in enumerate(cases):
        actual = module['vanilla'](**case)
        want = payoff(case)
        coarse = payoff(case,12)
        for key in want:
            a.near(want[key],coarse[key],'quadrature order refinement '+key,atol=5e-10)
            a.near(actual[key],want[key],'independent payoff/pathwise case '+str(i)+' '+key,atol=5e-9)
        a.near(actual['call']-actual['put'],case['spot']*math.exp(-case['dividend']*case['tau'])-case['strike']*math.exp(-case['rate']*case['tau']),'value parity')
        a.near(actual['call_delta']-actual['put_delta'],math.exp(-case['dividend']*case['tau']),'delta parity')
        a.near(actual['vega'],actual['gamma']*case['spot']**2*case['sigma']*case['tau'],'gamma-vega rank identity')
        a.near(actual['call_theta']+.5*case['sigma']**2*case['spot']**2*actual['gamma']+(case['rate']-case['dividend'])*case['spot']*actual['call_delta']-case['rate']*actual['call'],0,'funded pricing PDE',atol=2e-8)
    for case in cases[:3]:
        actual = module['vanilla'](**case)
        independent = greeks(case)
        for key in ('gamma','call_theta','put_theta'):
            a.near(actual[key],independent[key],'five-point integral Greek '+key,atol=2e-8)
    for field in ('spot','tau','sigma'):
        case = dict(p);case[field]=0
        out = module['vanilla'](**case)
        for side,value in payoff(case).items():a.near(out[side],value,field+' boundary value')
        for key in ('gamma','vega','call_delta','put_delta','call_theta','put_theta'):
            a.eq(out[key],None,field+' boundary not assigned interior Greek')
    a.true(module['vanilla'](**cases[-1])['call_theta']>0,'negative rate can make call theta positive')
    a.true(module['vanilla'](**cases[-2])['call_theta']>0,'yield can make call theta positive')
    a.eq(module['vanilla'](**cases[4])['vega'],0.0,'explicit extreme-tail underflow case')
    near_expiry = module['vanilla'](**cases[5])
    earlier = module['vanilla'](**dict(cases[5],tau=.01))
    a.true(near_expiry['gamma']>9*earlier['gamma'] and near_expiry['vega']<.11*earlier['vega'],'nonuniform expiry sensitivities')
    a.groups.append('Gauss-Legendre terminal payoffs and pathwise delta/vega; rule/refinement checks, independent five-point gamma/theta, parity/PDE and qualified boundary stresses')

    base = greeks(p)
    units = raw['position']['contracts']*raw['position']['multiplier']
    target = {'option_units':units,'call_market_value':units*base['call'],
              'delta_shares':units*base['call_delta']+raw['position']['stock_units'],
              'gamma':units*base['gamma'],'vega_per_unit_sigma':units*base['vega'],
              'vega_per_volatility_point':units*base['vega']/100,
              'calendar_theta_per_year':units*base['call_theta'],
              'stock_trade_to_zero_delta':-units*base['call_delta']-raw['position']['stock_units']}
    for key,value in target.items():a.near(result['portfolio'][key],value,'signed portfolio units '+key,atol=4e-6)
    for path,value,label in [(('position','contracts'),15,'long/short reversal'),(('position','multiplier'),200,'contract multiplier'),(('position','stock_units'),100,'existing stock and incremental trade')]:
        changed = replace(raw,path,value);row = run(changed)['portfolio'];position=changed['position'];n=position['contracts']*position['multiplier']
        a.near(row['delta_shares'],n*base['call_delta']+position['stock_units'],label+' delta')
        a.near(row['stock_trade_to_zero_delta'],-n*base['call_delta']-position['stock_units'],label+' incremental stock')
        a.near(row['gamma'],n*base['gamma'],label+' gamma')
        a.near(row['vega_per_volatility_point'],n*base['vega']/100,label+' vega point')
        a.interventions.append(label)
    gamma_hedge = Q(6)/Q('.02');stock_hedge = -(-100+Q('.6')*gamma_hedge)
    a.eq((gamma_hedge,stock_hedge,-12000+30*gamma_hedge),(300,-80,-3000),'exercise two simultaneous hedge and residual')
    a.eq(Q(-3000)*Q('.01'),-30,'exercise two volatility-point P&L')
    a.eq(Q(-2400)*Q('.02'),-48,'retention two volatility points')
    a.eq(Q(100)**2*Q('.2')*Q('.5')*Q('.03'),30,'retention gamma to vega')
    exercise_one = greeks(cases[1])
    for key,value in {'call':4.949425248,'put':10.346312506,'call_delta':.421612037,'put_delta':-.568437797,'gamma':.021525460,'vega':23.328217770,'call_theta':-6.590600847,'put_theta':-7.378174333}.items():
        a.near(exercise_one[key],value,'exercise one printed '+key,atol=1e-9)

    for ds in (-7,-1,0,1,7):
        changed = deepcopy(raw);changed['shock'].update(spot_change=ds,vol_change=0,elapsed=0)
        row = run(changed)['shock'];true = payoff(dict(p,spot=p['spot']+ds))['call']-base['call']
        a.near(row['spot_only_exact_change'],true,'integral spot repricing')
        a.true(abs(true-row['spot_only_taylor_change'])<=row['spot_only_remainder_bound']+1e-10,'spot-only analytic remainder contains independent difference')
        a.interventions.append('spot-only shock '+str(ds))
    sh = raw['shock'];ds,dv,dt = (sh[k] for k in ('spot_change','vol_change','elapsed'))
    true = payoff(dict(p,spot=p['spot']+ds,sigma=p['sigma']+dv,tau=p['tau']-dt))['call']-base['call']
    terms = {'delta':base['call_delta']*ds,'gamma':base['gamma']*ds*ds/2,'vega':base['vega']*dv,'theta':base['call_theta']*dt}
    for key,value in terms.items():a.near(result['shock']['terms'][key],value,'mixed approximation component '+key)
    a.near(result['shock']['exact_repriced_change'],true,'mixed integral repricing')
    a.near(result['shock']['mixed_shock_residual'],true-sum(terms.values()),'mixed remainder separate from spot theorem')
    a.true(abs(result['shock']['mixed_shock_residual'])>result['shock']['spot_only_remainder_bound'],'worked mixed residual exceeds spot-only bound')
    slope,curvature = -.0015,.00002
    def surface(s):return payoff(dict(p,spot=s,sigma=p['sigma']+slope*(s-p['spot'])+curvature*(s-p['spot'])**2/2))['call']
    h = .015
    response = first_difference(surface,p['spot'],h)
    a.near(response,base['call_delta']+base['vega']*slope,'total versus partial response',atol=2e-8)
    a.near(response,.417831841080851,'worked total delta',atol=2e-8)
    vanna = first_difference(lambda v:payoff(dict(p,sigma=v))['call_delta'],p['sigma'],.0001)
    volga = first_difference(lambda v:payoff(dict(p,sigma=v))['vega'],p['sigma'],.0001)
    direct_gamma = (-surface(p['spot']+2*h)+16*surface(p['spot']+h)-30*surface(p['spot'])+16*surface(p['spot']-h)-surface(p['spot']-2*h))/(12*h*h)
    a.near(direct_gamma,base['gamma']+2*vanna*slope+volga*slope*slope+base['vega']*curvature,'all four total gamma terms',atol=1e-7)
    a.eq(Q('.5')+30*Q('-.002'),Q('.44'),'exercise four total delta')
    step = (3e-6/.003)**(1/3)
    a.near(step,.1,'exercise nine optimal central-difference step')
    a.near(.003*step*step/6+1e-6/step,.000015,'exercise nine worst-case error')
    a.groups.append('all printed Greek/unit anchors, incremental portfolio trades, spot-only and mixed revaluation, calibrated first/second response and deterministic difference-error optimum')

    audit_inverse(a,p,result['implied_volatility'],'baseline IV')
    a.near(result['implied_volatility']['sigma'],.3073774716758635,'worked inverse')
    for sigma in (.08,.35,.9,1.5):
        price = payoff(dict(p,sigma=sigma))['call']
        changed = replace(raw,('iv','call_price'),price);row = run(changed)['implied_volatility']
        a.eq(row['status'],'bracketed','integral-generated quote status')
        a.near(row['sigma'],sigma,'integral-generated inverse',atol=2e-9)
        audit_inverse(a,p,row,'known volatility '+str(sigma));a.interventions.append('known IV '+str(sigma))
    lower,upper = result['implied_volatility']['lower_price_bound'],result['implied_volatility']['upper_price_bound']
    eps = result['implied_volatility']['price_resolution']
    for quote,status in [(lower,'zero_volatility_limit'),(upper,'upper_bound_has_no_finite_implied_volatility'),(lower+eps/2,'unresolved_near_price_boundary'),(upper-eps/2,'unresolved_near_price_boundary')]:
        row = run(replace(raw,('iv','call_price'),quote))['implied_volatility']
        a.eq(row['status'],status,'classified inverse boundary')
        a.eq(row['sigma'],0.0 if quote==lower else None,'boundary no invented finite IV')
        a.interventions.append(status)
    row = run(replace(raw,('iv','sigma_cap'),.1))['implied_volatility']
    a.eq(row['status'],'root_above_declared_sigma_cap','cap is computational scope')
    a.near(row['price_at_cap'],payoff(dict(p,sigma=.1))['call'],'independent capped price')
    a.interventions.append('binding computational sigma cap')
    price = raw['iv']['call_price'];hprice=.001
    sigma_up = run(replace(raw,('iv','call_price'),price+hprice))['implied_volatility']['sigma']
    sigma_down = run(replace(raw,('iv','call_price'),price-hprice))['implied_volatility']['sigma']
    a.near((sigma_up-sigma_down)/(2*hprice),result['implied_volatility']['local_sigma_change_per_price_unit'],'inverse local conditioning',atol=4e-8)
    atm = deepcopy(raw);atm['base'].update(spot=80,strike=80,tau=.25,rate=0,dividend=0,sigma=.4)
    atm['shock'].update(spot_change=0,vol_change=0,elapsed=0);atm['hedge'].update(times=[0,.25],spots=[80,80])
    atm_quote=80*integrate(lambda z:math.exp(-z*z/2)/math.sqrt(2*math.pi),-.1,.1)
    atm['iv']['call_price']=atm_quote
    a.near(atm_quote,6.372453964324638,'exercise five symmetric density integral')
    a.near(run(atm)['implied_volatility']['sigma'],.4,'exercise five known inverse',atol=1e-10)
    a.eq(Q('.05')/2,Q('.025'),'exercise five finite-interval inverse bound')
    a.interventions.extend(['small price perturbation and local inverse scale','closed ATM inversion anchor'])
    a.groups.append('independent IV bracket/residual/vega prices, known generated volatilities, exact/near price endpoints, computational cap and finite-interval versus local conditioning')

    audit_smile(a,raw,result['smile'],'baseline smile')
    changed = replace(raw,('smile','call_prices'),[14,9,5]);row=run(changed)
    audit_smile(a,changed,row['smile'],'repaired middle quote')
    a.eq(row['smile']['convexity_screen_passes'],True,'middle quote repair finite screen')
    a.eq(row['implied_volatility'],result['implied_volatility'],'separate contract unaffected')
    a.interventions.append('same-expiry convexity repair')
    changed = deepcopy(raw);changed['smile'].update(strikes=[90,100,115],call_prices=[17,13,5]);row=run(changed)
    audit_smile(a,changed,row['smile'],'unequal-strike exercise')
    a.near(row['smile']['weighted_butterfly_costs'][0],Q(-4,5),'exercise eight exact negative cost')
    for spot in (0,89,90,95,100,110,115,120,10000):
        payoff_value=Q(3,5)*max(spot-90,0)+Q(2,5)*max(spot-115,0)-max(spot-100,0)
        expected=0 if spot<=90 or spot>=115 else Q(3,5)*(spot-90) if spot<=100 else Q(2,5)*(115-spot)
        a.eq(payoff_value,expected,'exercise eight exact payoff segments');a.true(payoff_value>=0,'nonnegative butterfly')
    a.interventions.append('unequal strike butterfly')
    a.groups.append('rational finite-strike slopes/costs, independently repriced smile inverses and unequal-strike nonnegative payoff proof anchors')

    audit_ledger(a,raw,result['hedge'],'baseline')
    for path,value,label in [(('hedge','spots'),[120,126,113,95],'terminal loss path'),(('hedge','interior_fee'),0,'zero reset costs'),(('hedge','interior_fee'),.004,'doubled reset costs'),(('base','rate'),-.04,'negative financing rate'),(('base','dividend'),0,'no dividend reinvestment'),(('hedge','times'),[0,.1,.6,.75],'uneven trading schedule')]:
        changed=replace(raw,path,value);out=run(changed);audit_ledger(a,changed,out['hedge'],label)
        if label=='terminal loss path':
            a.eq(out['hedge']['ledger'][:-1],result['hedge']['ledger'][:-1],'future spot does not change earlier trades')
            a.near(out['hedge']['ledger'][-1]['ideal_terminal_error'],-.696468323446986,'exercise six ideal loss')
            a.near(out['hedge']['ledger'][-1]['funded_fee_terminal_error'],-.7959345696427071,'exercise six financed loss')
        a.interventions.append(label)
    changed=deepcopy(raw);changed['hedge'].update(times=[0,.75],spots=[120,130]);out=run(changed)
    audit_ledger(a,changed,out['hedge'],'no interior trade')
    a.eq(out['hedge']['ledger'][-1]['ideal_terminal_error'],out['hedge']['ledger'][-1]['funded_fee_terminal_error'],'no trade no charged fee')
    a.interventions.append('no interior delta reset')
    row=result['hedge']['ledger'][0]
    a.near(row['wealth_before_trade']-row['call_mark'],1.6340190117303237,'mark-reset hidden withdrawal')
    audit_variance(a,raw,result['variance_account'],'baseline variance worksheet')
    for path,value,label in [(('variance_account','actual_sigmas'),[.2,.3],'permuted equal-average variances'),(('variance_account','discounted_cash_gammas'),[0,0],'zero cash gamma weights'),(('variance_account','actual_sigmas'),[.25,.25],'matched instantaneous variance'),(('variance_account','durations'),[.2,.8],'unequal time weights')]:
        changed=replace(raw,path,value);out=run(changed);audit_variance(a,changed,out['variance_account'],label)
        if label.startswith('permuted'):
            a.near(out['variance_account']['total_discounted_error'],Q(-35,16),'exercise seven reversed error')
            a.eq(out['variance_account']['time_average_actual_variance'],result['variance_account']['time_average_actual_variance'],'same average does not fix gamma-weighted result')
        a.interventions.append(label)
    a.near(result['variance_account']['total_discounted_error'],Q(25,16),'exercise seven original error')
    a.groups.append('discounted cash and dividend-adjusted share accounts, financed costs, losses, uneven/no trading, hidden withdrawals and exact gamma-weighted variance worksheets')

    invalid=[None,[],{}]
    for path,value in [(('schema',),True),(('provenance',),1),(('base','spot'),True),(('base','spot'),0),(('base','spot'),10001),(('base','strike'),'125'),(('base','sigma'),None),(('base','sigma'),float('nan')),(('base','sigma'),float('inf')),(('base','sigma'),10**400),(('base','sigma'),0),(('base','tau'),0),(('base','tau'),5.1),(('base','rate'),-.20001),(('base','dividend'),-.00001),(('position','contracts'),.5),(('position','contracts'),True),(('position','contracts'),10001),(('position','multiplier'),0),(('position','stock_units'),1e8+1),(('shock','spot_change'),-120),(('shock','vol_change'),-.24),(('shock','elapsed'),.75),(('iv','call_price'),upper+.01),(('iv','call_price'),-1),(('iv','sigma_cap'),4.1),(('smile','strikes'),[90,90,110]),(('smile','strikes'),[110,100,90]),(('smile','call_prices'),[14,11]),(('smile','call_prices'),[1,1,1]),(('smile','spot'),True),(('smile','call_prices'),[14,True,5]),(('hedge','times'),[0,.25,.25,.75]),(('hedge','times'),[0,.25,.5,.8]),(('hedge','times'),[0,.25,.74999,.75]),(('hedge','spots'),[121,126,113,130]),(('hedge','spots'),[120,126]),(('hedge','spots'),[120,126,0,130]),(('hedge','interior_fee'),.051),(('variance_account','durations'),[]),(('variance_account','actual_sigmas'),[.3]),(('variance_account','discounted_cash_gammas'),[50,-1]),(('variance_account','model_sigma'),True),(('variance_account','actual_sigmas'),[.3,3.1])]:
        invalid.append(replace(raw,path,value))
    for section in ('base','position','shock','iv','smile','hedge','variance_account'):
        invalid.append(replace(raw,(section,),[]))
        changed=deepcopy(raw);changed[section]['unexpected']=0;invalid.append(changed)
    changed=deepcopy(raw);changed['unexpected']=0;invalid.append(changed)
    for i,data in enumerate(invalid):a.reject(run,data,'invalid peer case '+str(i))
    a.groups.append('independent strict JSON shape/type/nonfinite/overflow and finite financial-domain rejection, with unchanged rejected inputs')

    with tempfile.TemporaryDirectory(prefix='v10 c09 peer ') as td:
        temp=Path(td);assets=temp/'download';assets.mkdir();cwd=temp/'unrelated';cwd.mkdir()
        for suffix in ('analysis.py','inputs.json'):shutil.copy2(ASSETS/(PREFIX+'-'+suffix),assets)
        script=assets/(PREFIX+'-analysis.py');source=assets/(PREFIX+'-inputs.json')
        for opt in ([],['-O']):
            cmd=[sys.executable]+opt+[str(script),'--input',str(source)]
            process=subprocess.run(cmd,cwd=cwd,capture_output=True,text=True,timeout=30)
            a.eq((process.returncode,process.stderr),(0,''),'isolated normal/-O status')
            a.eq(json.loads(process.stdout),result,'isolated CLI stdout full output')
            dest=temp/'explicit output.json'
            process=subprocess.run(cmd+['--output',str(dest)],cwd=cwd,capture_output=True,text=True,timeout=30)
            a.eq((process.returncode,process.stdout,process.stderr),(0,'',''),'isolated explicit output quiet')
            a.eq(json.loads(dest.read_text()),result,'isolated file full output')
            for text in ('{"schema":1,"schema":1}','{"x":NaN}',json.dumps(invalid[-1]),json.dumps(raw).replace('"sigma": 0.24','"sigma": 1e400')):
                bad=temp/'invalid.json';bad.write_text(text);dest.write_text('preserve existing result')
                proc=subprocess.run([sys.executable]+opt+[str(script),'--input',str(bad),'--output',str(dest)],cwd=cwd,capture_output=True,text=True,timeout=30)
                a.true(proc.returncode!=0,'invalid standalone input rejected');a.eq(proc.stdout,'','invalid CLI no data')
                a.eq(dest.read_text(),'preserve existing result','invalid input did not replace output')
                a.rejections+=1
            probe='import contextlib,io,runpy,json; c=io.StringIO();\nwith contextlib.redirect_stdout(c),contextlib.redirect_stderr(c):\n m=runpy.run_path('+repr(str(script))+'); d=json.loads(open('+repr(str(source))+').read()); m["run"](d)\nif c.getvalue(): raise RuntimeError("API output")\n'
            proc=subprocess.run([sys.executable]+opt+['-c',probe],cwd=cwd,capture_output=True,text=True,timeout=30)
            a.eq((proc.returncode,proc.stdout,proc.stderr),(0,'',''),'isolated normal/-O quiet import/API')
    a.groups.append('two-file isolated normal/-O CLI and quiet API, explicit paths with unrelated cwd, duplicate/nonfinite JSON rejection and preservation of existing output')

    chapter=(ROOT/'content/chapters/v10-c09.html').read_text();fragment=Fragment();fragment.feed(chapter)
    a.eq(fragment.stack,[],'balanced manuscript');a.eq((fragment.worked,fragment.problems,fragment.answers),(5,10,10),'all worked/prompts/answers')
    a.eq(len(fragment.ids),len(set(fragment.ids)),'unique anchors')
    for i in range(1,11):a.true('solution-'+str(i) in fragment.ids,'complete solution anchor')
    for suffix in ('inputs.json','analysis.py','output.json','manifest.json','README.txt'):
        a.true(PREFIX+'-'+suffix in fragment.hrefs,'flat downloadable asset')
    proposals=json.loads((ROOT/'content/reviews/v10-c09-sources.json').read_text())['proposals']
    a.eq({x['id'] for x in proposals},{x.split('#')[1] for x in fragment.hrefs if x.startswith('sources.html#')},'exact scoped source IDs')
    author=json.loads((ROOT/'content/reviews/v10-c09-author.json').read_text())
    a.eq({r['path'] for r in author['reviewed_hashes']},set(AUTHOR_PATHS)-{'content/reviews/v10-c09-author.json'},'author exact eight nonself paths')
    a.eq(len(author['reviewed_hashes']),8,'eight author bindings without duplicates')
    for r in author['reviewed_hashes']:
        blob=(ROOT/r['path']).read_bytes();a.eq((len(blob),sha256(blob).hexdigest()),(r['bytes'],r['sha256']),'author original binding')
    manifest=json.loads((ASSETS/(PREFIX+'-manifest.json')).read_text())
    a.eq({r['file'] for r in manifest['files']},{PREFIX+'-'+s for s in ('inputs.json','analysis.py','output.json','README.txt')},'four payload original manifest')
    for r in manifest['files']:
        blob=(ASSETS/r['file']).read_bytes();a.eq((len(blob),sha256(blob).hexdigest()),(r['bytes'],r['sha256']),'original manifest binding')
    peer=json.loads((ROOT/'content/reviews/v10-c09-peer.json').read_text())
    a.eq({r['path'] for r in peer['reviewed_hashes']},set(AUTHOR_PATHS),'peer exact nine authors');a.eq(len(peer['reviewed_hashes']),9,'nine peer bindings without duplicates')
    for r in peer['reviewed_hashes']:
        blob=(ROOT/r['path']).read_bytes();a.eq((len(blob),sha256(blob).hexdigest()),(r['bytes'],r['sha256']),'peer frozen author binding')
    m=json.loads((ROOT/'content/reviews/v10-c09-peer-manifest.json').read_text())
    a.eq(m['author_files'],peer['reviewed_hashes'],'same nine final author files')
    a.eq({r['path'] for r in m['peer_payloads']},set(PEER_PATHS),'peer manifest record/checker paths')
    for r in m['peer_payloads']:
        blob=(ROOT/r['path']).read_bytes();a.eq((len(blob),sha256(blob).hexdigest()),(r['bytes'],r['sha256']),'peer payload binding')
    a.groups.append('complete fragment, all ten exact solution anchors, scoped sources, flat lab assets and nine author/two peer payload digest bindings')
    return {'chapter':PREFIX,'status':'passed','peer_comparisons':a.comparisons,
            'invalid_inputs_rejected':a.rejections,'financial_interventions':len(a.interventions),
            'interventions':a.interventions,'author_files_bound':9,'worked_examples_reviewed':5,'solved_exercises_reviewed':10,
            'count_definition':'Every executed scalar/vector/object comparison counts once; rejected API/CLI inputs and named economic interventions are counted separately. Proof and prompt/source reading are documented in the review record.',
            'groups':a.groups,'limits':'Separate machine-assisted peer audit, not external human certification or empirical hedge validation. Gaussian quadrature order agreement and finite differences are numerical evidence, not rigorous integration-error intervals or proof of the continuous identities. Author price, inverse and funding helpers are not numerical oracles.'}


if __name__ == '__main__':
    print(json.dumps(check(),indent=2,allow_nan=False))
