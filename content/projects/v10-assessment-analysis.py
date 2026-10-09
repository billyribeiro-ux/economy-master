"""Original Alder pricing/risk toolkit. Python 3.9+, standard library only."""
import argparse
from fractions import Fraction
from hashlib import sha256
import json
import math
from pathlib import Path
import re

SCHEMA = 'v10-assessment-alder-1'
PROVENANCE = 'Original synthetic Alder desk case; no market observations or real trading permission.'
NUMBER = re.compile(r'-?(?:0|[1-9][0-9]{0,7})(?:\.[0-9]{1,8}|/[1-9][0-9]{0,7})?\Z|-?\.[0-9]{1,8}\Z')
IDENTIFIER = re.compile(r'[a-z][a-z0-9_]{0,39}\Z')


def need(condition, message):
    if not condition:
        raise ValueError(message)


def obj(value, keys, name):
    need(type(value) is dict and set(value) == set(keys.split()), name + ': exact object keys required')


def vector(value, lower, upper, name):
    need(type(value) is list and lower <= len(value) <= upper, name + ': list length outside domain')
    return value


def number(value, low, high, name):
    need(type(value) is str and len(value) <= 24 and NUMBER.fullmatch(value) is not None,
         name + ': bounded exact financial string required')
    result = Fraction(value)
    need(low <= result <= high, name + ': value outside domain')
    return result


def integer(value, low, high, name):
    need(type(value) is int and low <= value <= high, name + ': integer outside domain')
    return value


def name(value):
    need(type(value) is str and IDENTIFIER.fullmatch(value) is not None, 'invalid identifier')
    return value


def unique(rows):
    ids = [name(row['id']) for row in rows]
    need(len(ids) == len(set(ids)), 'identifiers must be distinct within their list')


def validate(data):
    obj(data, 'schema provenance curve liability option hedge credit_reserve decision', 'input')
    need(data['schema'] == SCHEMA and data['provenance'] == PROVENANCE, 'schema/provenance mismatch')
    c = data['curve']; obj(c, 'times instruments shocks', 'curve')
    times = [number(x, Fraction(1,4), 3, 'curve time') for x in vector(c['times'], 3, 3, 'curve times')]
    need(times[0] <= 1 and all(b-a >= Fraction(1,4) for a,b in zip(times,times[1:])), 'ordered separated curve times required')
    rows = vector(c['instruments'], 3, 3, 'instruments'); discounts = []
    for i,row in enumerate(rows):
        obj(row, 'id cash price', 'instrument')
        cash = [number(x, 0, 100000, 'instrument cash') for x in vector(row['cash'],3,3,'instrument cash')]
        price = number(row['price'], Fraction(1,100), 200000, 'instrument price')
        need(cash[i] >= 1 and all(x == 0 for x in cash[i+1:]), 'positive triangular diagonal and zero later payments required')
        disc = (price-sum(cash[j]*discounts[j] for j in range(i)))/cash[i]
        need(Fraction(1,4) <= disc <= Fraction(3,2), 'bootstrapped discount outside [.25,1.5]')
        discounts.append(disc)
    unique(rows)
    shocks = vector(c['shocks'], 1, 6, 'shocks')
    for row in shocks:
        obj(row, 'id zero_shifts', 'shock')
        for x in vector(row['zero_shifts'],3,3,'shock shifts'): number(x,Fraction(-1,20),Fraction(1,20),'zero shift')
    unique(shocks)
    l = data['liability']; obj(l, 'face coupons', 'liability')
    number(l['face'],1,100000,'face')
    for x in vector(l['coupons'],3,3,'coupons'):number(x,0,10000,'coupon')
    o = data['option']; obj(o, 'spot strike sigma tree_steps bermudan_fractions mc_pairs seed control_beta quadrature_steps', 'option')
    spot = number(o['spot'],50,200,'spot')
    number(o['strike'],spot*Fraction(3,4),spot*Fraction(5,4),'strike')
    sigma = float(number(o['sigma'],Fraction(1,10),Fraction(3,5),'sigma'))
    rate = -math.log(float(discounts[0]))/float(times[0])
    need(abs(rate) <= .2, 'option first-segment rate exceeds absolute .2')
    steps = vector(o['tree_steps'],2,6,'tree steps')
    for n in steps: need(type(n) is int and n in (4,8,16,32,64,128), 'tree steps must be a permitted power of two')
    need(all(a<b for a,b in zip(steps,steps[1:])), 'tree steps must increase')
    fractions = [number(x,0,Fraction(3,4),'exercise fraction') for x in vector(o['bermudan_fractions'],1,4,'exercise fractions')]
    need(all(a<b for a,b in zip(fractions,fractions[1:])), 'exercise fractions must increase without duplicates')
    need(all((f*n).denominator == 1 for f in fractions for n in steps), 'exercise dates must lie on every tree grid')
    for n in steps:
        dt = float(times[0])/n
        need(-sigma*math.sqrt(dt) < rate*dt < sigma*math.sqrt(dt), 'tree violates strict no-arbitrage')
    integer(o['mc_pairs'],64,4096,'MC pairs'); integer(o['seed'],0,2**32-1,'seed')
    number(o['control_beta'],-2,2,'fixed control coefficient')
    qn = integer(o['quadrature_steps'],32,1024,'quadrature steps'); need(qn % 2 == 0,'quadrature steps must be even')
    h = data['hedge']; obj(h, 'times cost_rate paths', 'hedge')
    ht = [number(x,0,times[0],'hedge time') for x in vector(h['times'],2,9,'hedge times')]
    need(ht[0] == 0 and ht[-1] == times[0] and all(b-a >= times[0]/16 for a,b in zip(ht,ht[1:])), 'hedge dates must span option life with bounded positive gaps')
    number(h['cost_rate'],0,Fraction(1,100),'cost rate')
    paths = vector(h['paths'],1,8,'hedge paths')
    for row in paths:
        obj(row, 'id spots', 'hedge path')
        levels = [number(x,spot/2,spot*Fraction(3,2),'path spot') for x in vector(row['spots'],len(ht),len(ht),'path levels')]
        need(levels[0] == spot, 'each path must start at option spot')
    unique(paths)
    cr = data['credit_reserve']; obj(cr, 'pricing_default_probability default_index settlement_index recovery_fraction', 'credit reserve')
    number(cr['pricing_default_probability'],Fraction(1,1000),Fraction(999,1000),'pricing default probability')
    di = integer(cr['default_index'],0,2,'default index')
    si = integer(cr['settlement_index'],0,2,'settlement index'); need(si>=di,'recovery cannot precede default')
    number(cr['recovery_fraction'],0,1,'recovery fraction')
    d = data['decision']; obj(d, 'requested_exercise requested_reserve requested_quote max_tested_terminal_loss max_mc_standard_error max_tree_abs_error', 'decision')
    need(d['requested_exercise'] in ('european','bermudan','american'),'unknown requested exercise rights')
    need(d['requested_reserve'] in ('matched_zeros','risky_bond'),'unknown requested reserve')
    number(d['requested_quote'],0,500000,'requested quote')
    number(d['max_tested_terminal_loss'],0,1000,'tested loss budget')
    number(d['max_mc_standard_error'],Fraction(1,10000),10,'MC SE budget')
    number(d['max_tree_abs_error'],Fraction(1,1000000),10,'tree difference budget')
    return times, discounts


def cdf(x):
    return .5*math.erfc(-x/math.sqrt(2))


def vanilla(spot, strike, rate, sigma, tau):
    # Used at strictly positive remaining lives; maturity payoff is separate.
    root = sigma*math.sqrt(tau)
    d1 = (math.log(spot/strike)+(rate+.5*sigma*sigma)*tau)/root
    d2 = d1-root
    discount = math.exp(-rate*tau)
    put = max(0.0,strike*discount*cdf(-d2)-spot*cdf(-d1))
    call = max(0.0,spot*cdf(d1)-strike*discount*cdf(d2))
    return {'put':put,'call':call,'put_delta':cdf(d1)-1,
            'gamma':math.exp(-d1*d1/2)/(math.sqrt(2*math.pi)*spot*root),
            'vega':spot*math.exp(-d1*d1/2)*math.sqrt(tau)/math.sqrt(2*math.pi),
            'd1':d1,'d2':d2}


def tree(spot,strike,rate,sigma,tau,n,early,details=False):
    dt = tau/n; up = math.exp(sigma*math.sqrt(dt)); down = 1/up
    growth = math.exp(rate*dt); p = (growth-down)/(up-down)
    value = [max(strike-spot*up**j*down**(n-j),0.0) for j in range(n+1)]
    exercised = []; count = 0; continuation_hedge = None; root_exercise = False
    for i in range(n-1,-1,-1):
        if i == 0:
            delta = (value[1]-value[0])/(spot*(up-down))
            cash = (up*value[0]-down*value[1])/((up-down)*growth)
            continuation_hedge = {'stock_units':delta,'initial_bank':cash,
                                  'down_value':value[0],'up_value':value[1]}
        new = []
        for j in range(i+1):
            s = spot*up**j*down**(i-j)
            continuation = (p*value[j+1]+(1-p)*value[j])/growth
            immediate = max(strike-s,0.0)
            stop = i in early and immediate>continuation
            new.append(immediate if stop else continuation)
            if stop:
                count += 1
                if details:exercised.append({'step':i,'up_moves':j,'time':i*dt,'spot':s,'exercise':immediate,'continuation':continuation})
            if i == 0:root_exercise = stop
        value = new
    return {'steps':n,'up':up,'down':down,'probability_up':p,'price':value[0],
            'exercise_steps':sorted(early),'exercise_node_count':count,
            'exercise_nodes':exercised,'exercise_nodes_complete':details,'root_exercise':root_exercise,
            'root_continuation_hedge':continuation_hedge}


def normals(seed,index):
    raw = sha256(('alder-project-v1|'+str(seed)+'|'+str(index)).encode('ascii')).digest()
    # Open midpoints of 52-bit cells; all endpoints are exactly interior in binary64.
    u = ((int.from_bytes(raw[:8],'big')>>12)+.5)/2**52
    v = ((int.from_bytes(raw[8:16],'big')>>12)+.5)/2**52
    radius = math.sqrt(-2*math.log(u)); angle = 2*math.pi*v
    return radius*math.cos(angle),radius*math.sin(angle)


def moments(values,bound=None):
    n = len(values); mean = math.fsum(values)/n
    variance = math.fsum((x-mean)**2 for x in values)/(n-1)
    se = math.sqrt(variance/n)
    result = {'units':n,'mean':mean,'sample_variance':variance,'estimated_se':se,
              'approximate_95_interval':[mean-1.96*se,mean+1.96*se]}
    if bound is not None:
        half = bound*math.sqrt(math.log(40)/(2*n))
        result['ideal_iid_hoeffding_95_halfwidth'] = half
    return result


def monte_carlo(spot,strike,rate,sigma,tau,pairs,seed,beta,anchor):
    discount = math.exp(-rate*tau); scale = sigma*math.sqrt(tau)
    drift = (rate-.5*sigma*sigma)*tau
    def observation(z):
        terminal = spot*math.exp(drift+scale*z)
        return discount*max(strike-terminal,0.0),discount*terminal
    plain = []; controlled = []; antithetic = []; controls = []
    for i in range(pairs):
        z,w = normals(seed,i)
        yz,xz = observation(z)
        for value in (z,w):
            y,x = observation(value); plain.append(y); controls.append(x)
            controlled.append(y-beta*(x-spot))
        opposite,_ = observation(-z)
        antithetic.append((yz+opposite)/2)
    result = {'generator':'SHA256 52-bit open midpoint Box-Muller; deterministic pseudo experiment',
              'seed':seed,'base_pairs':pairs,'fixed_beta':beta,
              'plain':moments(plain,discount*strike),
              'antithetic':moments(antithetic,discount*strike),
              'controlled':moments(controlled),
              'discounted_stock':moments(controls)}
    for key in ('plain','antithetic','controlled'):
        result[key]['estimate_minus_analytic'] = result[key]['mean']-anchor
    result['discounted_stock']['ideal_mean'] = spot
    result['controlled_to_plain_variance_ratio'] = result['controlled']['sample_variance']/result['plain']['sample_variance'] if result['plain']['sample_variance']>0 else None
    result['antithetic_to_plain_estimated_mean_variance_ratio'] = result['antithetic']['estimated_se']**2/result['plain']['estimated_se']**2 if result['plain']['estimated_se']>0 else None
    return result


def quadrature(spot,strike,rate,sigma,tau,n):
    drift = (rate-.5*sigma*sigma)*tau; scale = sigma*math.sqrt(tau)
    boundary = (math.log(strike/spot)-drift)/scale
    right = min(10.0,boundary); left = -10.0; discount = math.exp(-rate*tau)
    def integrand(z):
        return discount*max(strike-spot*math.exp(drift+scale*z),0)*math.exp(-z*z/2)/math.sqrt(2*math.pi)
    def integrate(count):
        if right<=left:return 0.0
        h = (right-left)/count
        return h/3*(integrand(left)+integrand(right)+4*math.fsum(integrand(left+i*h) for i in range(1,count,2))+2*math.fsum(integrand(left+i*h) for i in range(2,count,2)))
    coarse,fine = integrate(n),integrate(2*n)
    return {'steps':n,'coarse':coarse,'fine':fine,'fine_minus_coarse':fine-coarse,
            'normal_cutoff':10,'omitted_tail_upper_bound':2*discount*strike*cdf(-10),
            'scope':'Tail bound is valid under ideal normal law; refinement difference is diagnostic, not a certified quadrature error bound.'}


def hedge_path(times,spots,strike,rate,sigma,premium,cost_rate):
    maturity = times[-1]; delta = vanilla(spots[0],strike,rate,sigma,maturity)['put_delta']
    entry_cost = cost_rate*abs(delta)*spots[0]
    bank = premium-delta*spots[0]-entry_cost
    costs = [(times[0],entry_cost)]; ledger = [{'time':0.0,'spot':spots[0],'stock_before':0.0,
        'stock_after':delta,'bank_before_trade':premium,'stock_trade_cash':delta*spots[0],
        'transaction_cost':entry_cost,'bank_after_trade':bank,'account_after_trade':delta*spots[0]+bank}]
    for i in range(1,len(times)):
        bank *= math.exp(rate*(times[i]-times[i-1])); before = bank; old_delta = delta
        if i<len(times)-1:
            delta = vanilla(spots[i],strike,rate,sigma,maturity-times[i])['put_delta']
        else:delta = 0.0
        trade = (delta-old_delta)*spots[i]; cost = cost_rate*abs(delta-old_delta)*spots[i]
        bank -= trade+cost; costs.append((times[i],cost))
        ledger.append({'time':times[i],'spot':spots[i],'stock_before':old_delta,'stock_after':delta,
                       'bank_before_trade':before,'stock_trade_cash':trade,'transaction_cost':cost,
                       'bank_after_trade':bank,'account_after_trade':bank+delta*spots[i]})
    payoff = max(strike-spots[-1],0.0)
    terminal_cost = math.fsum(cost*math.exp(rate*(maturity-date)) for date,cost in costs)
    return {'ledger':ledger,'payoff':payoff,'account_before_payoff':bank,'terminal_error':bank-payoff,
            'terminalized_transaction_costs':terminal_cost,'present_transaction_costs':terminal_cost*math.exp(-rate*maturity)}


def run(data):
    times,discounts = validate(data)
    def f(value):return Fraction(value)
    l = data['liability']; cash = list(map(f,l['coupons'])); cash[-1] += f(l['face'])
    pv_parts = [c*d for c,d in zip(cash,discounts)]
    pv = sum(pv_parts); exposure = [t*x for t,x in zip(times,pv_parts)]
    parallel = sum(exposure); second = sum(t*t*x for t,x in zip(times,pv_parts))
    short_pv = (times[-1]*pv-parallel)/(times[-1]-times[0]); long_pv = pv-short_pv
    barbell = [short_pv/discounts[0],Fraction(0),long_pv/discounts[-1]]
    gap_exposure = [t*d*(a-c) for t,d,a,c in zip(times,discounts,barbell,cash)]
    calibration = []
    for row in data['curve']['instruments']:
        fitted = sum(f(c)*d for c,d in zip(row['cash'],discounts))
        calibration.append({'id':row['id'],'reprice':str(fitted),'residual':str(fitted-f(row['price']))})
    previous_t = Fraction(0); previous_d = Fraction(1); forwards = []
    for t,d in zip(times,discounts):
        forwards.append(str((previous_d/d-1)/(t-previous_t))); previous_t,previous_d=t,d
    shocks = []
    for row in data['curve']['shocks']:
        dz = list(map(f,row['zero_shifts']))
        ds = [float(d)*math.exp(-float(t*z)) for d,t,z in zip(discounts,times,dz)]
        lp = math.fsum(float(c)*d for c,d in zip(cash,ds)); bp = math.fsum(float(a)*d for a,d in zip(barbell,ds))
        shocks.append({'id':row['id'],'liability_pv':lp,'barbell_pv':bp,'barbell_minus_liability':bp-lp,
                       'first_order_residual':float(-sum(g*z for g,z in zip(gap_exposure,dz))),
                       'second_order_residual':float(sum(-g*z+Fraction(1,2)*t*g*z*z for g,t,z in zip(gap_exposure,times,dz)))})
    bond = {'cash':list(map(str,cash)),'discounts':list(map(str,discounts)),
            'spot_continuous_rates':[-math.log(float(d))/float(t) for t,d in zip(times,discounts)],
            'simple_forward_rates':forwards,'calibration':calibration,'pv_parts':list(map(str,pv_parts)),
            'pv':str(pv),'key_rate_dollar_exposures':list(map(str,exposure)),
            'parallel_dollar_duration':str(parallel),'parallel_second_derivative':str(second),
            'parallel_duration_years':str(parallel/pv),'barbell_zero_quantities':list(map(str,barbell)),
            'barbell_gap_key_exposures':list(map(str,gap_exposure)),
            'cash_matched_zero_quantities':list(map(str,cash)),'shocks':shocks}
    o = data['option']; spot,strike,sigma = [float(f(o[k])) for k in ('spot','strike','sigma')]
    tau = float(times[0]); rate = -math.log(float(discounts[0]))/tau
    analytic = vanilla(spot,strike,rate,sigma,tau)
    benchmark = quadrature(spot,strike,rate,sigma,tau,o['quadrature_steps'])
    benchmark['fine_minus_analytic'] = benchmark['fine']-analytic['put']
    grids = []
    for n in o['tree_steps']:
        early = {int(f(x)*n) for x in o['bermudan_fractions']}
        eu = tree(spot,strike,rate,sigma,tau,n,set(),n==o['tree_steps'][0])
        be = tree(spot,strike,rate,sigma,tau,n,early,n==o['tree_steps'][0])
        am = tree(spot,strike,rate,sigma,tau,n,set(range(n)),n==o['tree_steps'][0])
        grids.append({'steps':n,'european':eu,'bermudan':be,'american':am,
                      'european_minus_analytic':eu['price']-analytic['put'],
                      'american_minus_european':am['price']-eu['price']})
    mc = monte_carlo(spot,strike,rate,sigma,tau,o['mc_pairs'],o['seed'],float(f(o['control_beta'])),analytic['put'])
    h = data['hedge']; ht = list(map(lambda x:float(f(x)),h['times'])); cost = float(f(h['cost_rate']))
    hedges = []
    for row in h['paths']:
        levels = list(map(lambda x:float(f(x)),row['spots']))
        zero = hedge_path(ht,levels,strike,rate,sigma,analytic['put'],0.0)
        paid = hedge_path(ht,levels,strike,rate,sigma,analytic['put'],cost)
        hedges.append({'id':row['id'],'frictionless':zero,'with_costs':paid,
                       'cost_attribution_residual':zero['terminal_error']-paid['terminal_error']-paid['terminalized_transaction_costs']})
    cr = data['credit_reserve']; q = f(cr['pricing_default_probability'])
    default_cash = [cash[i] if i<cr['default_index'] else Fraction(0) for i in range(3)]
    default_cash[cr['settlement_index']] += f(l['face'])*f(cr['recovery_fraction'])
    default_pv = sum(c*d for c,d in zip(default_cash,discounts))
    risky_pv = (1-q)*pv+q*default_pv
    bank = Fraction(0); prior = Fraction(1); funding = []
    for t,d,owed,received in zip(times,discounts,cash,default_cash):
        before = bank*prior/d; bank = before+received-owed
        funding.append({'time':str(t),'liability_cash':str(owed),'reserve_cash':str(received),
                        'bank_before_payment':str(before),'bank_after_payment':str(bank)})
        prior = d
    credit = {'survival_pv':str(pv),'default_cash':list(map(str,default_cash)),
              'default_pv':str(default_pv),'risky_reserve_pv':str(risky_pv),
              'apparent_initial_saving':str(pv-risky_pv),'default_initial_gap':str(pv-default_pv),
              'default_funding_ledger':funding,'default_terminal_bank':str(bank),
              'funds_all_declared_dates_without_injection':all(f(row['bank_after_payment'])>=0 for row in funding),
              'scope':'Exogenous pricing probability and specified recovery timing; this is not an estimated physical default probability.'}
    d = data['decision']; worst = min(row['with_costs']['terminal_error'] for row in hedges)
    buffer = max(0.0,-worst-float(f(d['max_tested_terminal_loss'])))*float(discounts[0])
    selected_reserve_pv = pv if d['requested_reserve']=='matched_zeros' else risky_pv
    reserve_budget_pv = max(pv,selected_reserve_pv)
    model_quote = float(pv)+analytic['put']
    required_quote = float(reserve_budget_pv)+analytic['put']+buffer
    gates = {'exercise_matches_european_reference':d['requested_exercise']=='european',
             'reserve_funds_all_declared_dates':d['requested_reserve']=='matched_zeros' or credit['funds_all_declared_dates_without_injection'],
             'quote_covers_tested_loss_budget':float(f(d['requested_quote']))+1e-10>=required_quote,
             'controlled_mc_se_within_budget':mc['controlled']['estimated_se']<=float(f(d['max_mc_standard_error'])),
             'finest_european_tree_difference_within_budget':abs(grids[-1]['european_minus_analytic'])<=float(f(d['max_tree_abs_error']))}
    failures = [key for key,value in gates.items() if not value]
    decision = {'frictionless_model_quote':model_quote,
                'selected_reserve_pv':str(selected_reserve_pv),'reserve_budget_pv':str(reserve_budget_pv),
                'reserve_budget_rule':'max(riskless fixed-liability PV, selected reserve purchase PV)',
                'worst_tested_terminal_hedge_error':worst,
                'additional_initial_cash_for_tested_loss_budget':buffer,'quote_with_tested_buffer':required_quote,
                'requested_quote':float(f(d['requested_quote'])),'gates':gates,'failed_gates':failures,
                'recommendation':'revise_before_demo' if failures else 'eligible_for_limited_demonstration',
                'scope':'Fictional classroom controls only; tested paths are not all possible paths, sample SE is not a deterministic error bound, and no real trade is authorized.'}
    result = {'schema':SCHEMA+'-output','provenance':PROVENANCE,'bond':bond,
              'option':{'maturity':tau,'first_segment_rate':rate,'analytic':analytic,'quadrature':benchmark,'trees':grids,'monte_carlo':mc},
              'hedge':{'paths':hedges,'cost_rate':cost,'path_scope':'Unweighted specified scenarios, not an iid profit sample or an exhaustive stress set.'},
              'credit_reserve':credit,'decision':decision}
    # Keep this check active under -O; all returned values must be strict-JSON safe.
    json.dumps(result,allow_nan=False)
    return result


def strict_pairs(pairs):
    result = {}
    for key,value in pairs:
        need(key not in result,'duplicate JSON key: '+key); result[key]=value
    return result


def reject_constant(value):
    raise ValueError('nonfinite JSON constant: '+value)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,default=Path(__file__).with_name('v10-assessment-inputs.json'))
    parser.add_argument('--output',type=Path)
    args = parser.parse_args()
    need(args.input.stat().st_size<=1000000,'input file exceeds one megabyte')
    data = json.loads(args.input.read_text(encoding='utf-8'),object_pairs_hook=strict_pairs,parse_constant=reject_constant)
    result = run(data); payload = json.dumps(result,indent=2,allow_nan=False)+'\n'
    if args.output is None:print(payload,end='')
    else:
        need(args.output.resolve() not in (args.input.resolve(),Path(__file__).resolve()),'output must not overwrite input or implementation')
        args.output.write_text(payload,encoding='utf-8')


if __name__ == '__main__':
    main()
