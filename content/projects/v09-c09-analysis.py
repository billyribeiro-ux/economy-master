#!/usr/bin/env python3
"""Cedar allocation council: independent synthetic decision panels, stdlib only."""
import argparse
from fractions import Fraction as F
import itertools
import json
import math
from pathlib import Path

CONVENTIONS = {
    'liability': 'Four equally likely independent-sign states; fixed mean-variance preference over terminal CU surplus; long-only and a beginning cash reserve.',
    'lifecycle': 'One-period terminal log utility; safe gross return one; nontradable endowment H0+h*(G-1); no borrowing or shorting.',
    'dynamic': 'Two-period terminal utility -1/W; safe gross return one at every node; exogenous observed tree; long-only fractions in [0,1]; no flows or costs.',
    'rebalancing': 'One risky asset and cash marked before trading; proportional fee on absolute risky CU traded, paid from cash immediately; target is a post-fee wealth fraction.',
    'bands': 'One-period CU mean-variance preference, zero liability covariance, safe gross return one; cash-paid proportional fee, long-only and no borrowing.',
    'uncertainty': 'Only the risky mean varies over a fixed closed interval; variance and risk coefficient are known model inputs; no confidence interpretation.'
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def keys(value, expected, label):
    require(isinstance(value, dict) and set(value) == set(expected.split()), label + ': exact keys required')


def number(x):
    require(type(x) in (int, str), 'Use integer or exact rational/decimal string, not bool or binary float')
    try:
        v = F(x)
    except (ValueError, ZeroDivisionError):
        raise ValueError('Invalid exact number') from None
    require(abs(v) <= 10**9 and v.denominator <= 10**9, 'Number outside documented finite fixture range')
    return v


def unpack(value, expected, label):
    keys(value, expected, label)
    return {k: number(v) for k, v in value.items()}


def clip(x, lo, hi):
    return max(lo, min(hi, x))


def liability_case(d):
    q = unpack(d, 'wealth safe_gross reserve excess_mean excess_sign_loading gamma liability_mean liability_u liability_v income_mean income_u income_v', 'liability')
    w, rf, reserve, mu, loading, gamma = (q[k] for k in ['wealth', 'safe_gross', 'reserve', 'excess_mean', 'excess_sign_loading', 'gamma'])
    require(w > 0 and 0 <= reserve <= w and 0 < rf <= 10 and gamma > 0 and loading > 0, 'Invalid liability wealth/reserve/risk domain')
    require(rf + mu - loading > 0 and abs(mu) < loading, 'Risky gross returns must be positive and straddle the safe return')
    for stem in ['liability', 'income']:
        require(q[stem + '_mean'] >= abs(q[stem + '_u']) + abs(q[stem + '_v']), 'Underlying income and liability must be nonnegative in every state')
    n0 = q['liability_mean'] - q['income_mean']
    nu = q['liability_u'] - q['income_u']
    nv = q['liability_v'] - q['income_v']
    variance, covariance = loading**2, loading * nu
    speculative, hedge = mu / (gamma * variance), covariance / variance
    raw = speculative + hedge
    x = clip(raw, F(0), w - reserve)
    rows = []
    for u, v in itertools.product([1, -1], repeat=2):
        z = mu + loading * u
        income = q['income_mean'] + q['income_u'] * u + q['income_v'] * v
        obligation = q['liability_mean'] + q['liability_u'] * u + q['liability_v'] * v
        assets = (w - x) * rf + x * (rf + z)
        rows.append({'u': u, 'v': v, 'probability': F(1, 4), 'asset_wealth': assets, 'income': income, 'liability': obligation, 'surplus': assets + income - obligation})
    mean = sum(r['surplus'] for r in rows) / 4
    var = sum((r['surplus'] - mean)**2 for r in rows) / 4
    return {'speculative_demand': speculative, 'liability_hedge_demand': hedge, 'unconstrained_demand': raw, 'risky_cu': x, 'safe_cu': w-x, 'risky_financial_fraction': x/w, 'excess_variance': variance, 'excess_net_obligation_covariance': covariance, 'mean_surplus': mean, 'surplus_variance': var, 'mean_variance_criterion': mean-gamma*var/2, 'constraint_derivative': mu-gamma*(variance*x-covariance), 'states': rows}


def binary(d, label):
    q = unpack(d, 'up_probability up_gross down_gross', label)
    p, gu, gd = (q[k] for k in ['up_probability', 'up_gross', 'down_gross'])
    require(F(1, 1000) <= p <= F(999, 1000) and 1 < gu <= 10 and F(1, 1000) <= gd < 1, 'Binary probabilities/positive gross returns outside supported straddling domain')
    return p, gu, gd


def lifecycle_case(d):
    keys(d, 'up_probability up_gross down_gross households', 'lifecycle')
    p, gu, gd = binary({k: d[k] for k in ['up_probability', 'up_gross', 'down_gross']}, 'lifecycle law')
    require(isinstance(d['households'], list) and 1 <= len(d['households']) <= 20, 'Supply 1–20 household cases')
    require(all(isinstance(h, dict) and isinstance(h.get('name'), str) and h['name'] for h in d['households']), 'Named household cases required')
    require(len({h['name'] for h in d['households']}) == len(d['households']), 'Household names must be unique')
    a, b = gu-1, gd-1
    rows = []
    for h in d['households']:
        keys(h, 'name wealth income_intercept income_exposure', 'household')
        w, h0, hx = (number(h[k]) for k in ['wealth', 'income_intercept', 'income_exposure'])
        require(w > 0 and h0 >= 0 and min(h0+hx*a, h0+hx*b) >= 0, 'Positive wealth and nonnegative endowment required')
        base = w+h0
        require(min(base+z*(x+hx) for z in [a,b] for x in [F(0),w]) > 0, 'Log terminal wealth must be positive over the full feasible interval')
        combined = -base*(p*a+(1-p)*b)/(a*b)
        raw = combined-hx
        x = clip(raw, F(0), w)
        terminal = [base+(x+hx)*a, base+(x+hx)*b]
        derivative = p*a/terminal[0] + (1-p)*b/terminal[1]
        rows.append({'name': h['name'], 'wealth': w, 'income_intercept': h0, 'income_exposure': hx, 'unconstrained_combined_exposure': combined, 'unconstrained_financial_exposure': raw, 'risky_cu': x, 'cash_cu': w-x, 'financial_fraction': x/w, 'terminal_wealth': terminal, 'objective_derivative': derivative, 'expected_log_approx': float(p)*math.log(float(terminal[0]))+float(1-p)*math.log(float(terminal[1]))})
    return rows


def crra2_node(d, coefficients=(1.0, 1.0)):
    p0, gu0, gd0 = binary(d, 'dynamic node')
    p, a, b = float(p0), float(gu0-1), float(gd0-1)
    cu, cd = coefficients
    k = math.sqrt(p*cu*a/((1-p)*cd*(-b)))
    raw = (k-1)/(a-k*b)
    alpha = clip(raw, 0.0, 1.0)
    gains = [1+alpha*a, 1+alpha*b]
    coefficient = p*cu/gains[0]+(1-p)*cd/gains[1]
    derivative = p*cu*a/gains[0]**2+(1-p)*cd*b/gains[1]**2
    return {'risky_fraction_approx': alpha, 'unconstrained_fraction_approx': raw, 'continuation_coefficient_approx': coefficient, 'marginal_criterion_approx': derivative, 'gross_wealth_factors_approx': gains}


def dynamic_case(d):
    keys(d, 'wealth initial after_up after_down', 'dynamic')
    w = number(d['wealth'])
    require(w > 0, 'Dynamic wealth must be positive')
    up, down = crra2_node(d['after_up']), crra2_node(d['after_down'])
    cu, cd = up['continuation_coefficient_approx'], down['continuation_coefficient_approx']
    first = crra2_node(d['initial'], (cu, cd))
    myopic = crra2_node(d['initial'])
    p, gu, gd = binary(d['initial'], 'initial')
    rows = []
    for label, prob, factor, node, spec in [('up',p,first['gross_wealth_factors_approx'][0],up,d['after_up']), ('down',1-p,first['gross_wealth_factors_approx'][1],down,d['after_down'])]:
        p2, _, _ = binary(spec, 'continuation')
        wealth1 = float(w)*factor
        for j, prob2 in enumerate([p2,1-p2]):
            rows.append({'path': label+'/'+['up','down'][j], 'probability': prob*prob2, 'wealth_after_period1_approx': wealth1, 'risky_cu_at_period1_approx': wealth1*node['risky_fraction_approx'], 'cash_cu_at_period1_approx': wealth1*(1-node['risky_fraction_approx']), 'terminal_wealth_approx': wealth1*node['gross_wealth_factors_approx'][j]})
    eu = sum(float(r['probability'])*(-1/r['terminal_wealth_approx']) for r in rows)
    am = myopic['risky_fraction_approx']
    myopic_coefficient = float(p)*cu/(1+am*float(gu-1))+float(1-p)*cd/(1+am*float(gd-1))
    return {'after_up': up, 'after_down': down, 'initial_optimum': first, 'initial_myopic': myopic, 'optimal_expected_utility_approx': eu, 'certainty_equivalent_terminal_cu_approx': -1/eu, 'myopic_first_optimal_continuation_eu_approx': -myopic_coefficient/float(w), 'myopic_first_certainty_equivalent_cu_approx': float(w)/myopic_coefficient, 'paths': rows}


def rebalance_case(d):
    keys(d, 'risky_before cash_before target fee_rate next_risky_gross', 'rebalancing')
    old, cash, target, fee = (number(d[k]) for k in ['risky_before','cash_before','target','fee_rate'])
    require(old >= 0 and cash >= 0 and old+cash > 0 and 0 <= target <= 1 and 0 <= fee < 1, 'Invalid rebalancing holdings/target/fee')
    require(isinstance(d['next_risky_gross'],list) and 1 <= len(d['next_risky_gross']) <= 20, 'Supply future gross scenarios')
    gross = [number(v) for v in d['next_risky_gross']]
    require(all(0 < v <= 10 for v in gross), 'Positive finite future gross returns required')
    wealth = old+cash
    gap = target*wealth-old
    trade = gap/(1+target*fee) if gap >= 0 else gap/(1-target*fee)
    paid = fee*abs(trade)
    new = old+trade
    safe = cash-trade-paid
    require(new >= 0 and safe >= 0 and wealth-paid > 0, 'Rebalancing must remain funded')
    return {'wealth_before':wealth,'fraction_before':old/wealth,'signed_risky_trade':trade,'fee_paid':paid,'risky_after':new,'cash_after':safe,'wealth_after':wealth-paid,'fraction_after':new/(wealth-paid),'next_period_scenarios':[{'risky_gross':g,'unchanged_holdings_wealth':old*g+cash,'rebalanced_wealth':new*g+safe,'difference':new*g+safe-old*g-cash} for g in gross]}


def band_decision(w, old, mu, variance, gamma, fee):
    require(w > 0 and 0 <= old <= w and variance > 0 and gamma > 0 and 0 <= fee < 1, 'Invalid funded mean-variance trade inputs')
    require(mu > -1, 'Mean gross return must be positive')
    curvature = gamma*variance
    marginal = mu-curvature*old
    if marginal > fee:
        candidate = (mu-fee)/curvature
    elif marginal < -fee:
        candidate = (mu+fee)/curvature
    else:
        candidate = old
    upper = (w+fee*old)/(1+fee)
    x = clip(candidate,F(0),upper)
    cost = fee*abs(x-old)
    def score(y): return mu*y-curvature*y*y/2-fee*abs(y-old)
    return {'risky_before':old,'mean_used':mu,'frictionless_target':mu/curvature,'no_trade_interval_unconstrained':[(mu-fee)/curvature,(mu+fee)/curvature],'maximum_funded_risky_cu':upper,'risky_after':x,'cash_after':w-cost-x,'fee_paid':cost,'variable_criterion':score(x),'hold_variable_criterion':score(old),'criterion_gain':score(x)-score(old),'marginal_before_cost':mu-curvature*x}


def band_case(d):
    keys(d,'wealth mean_excess variance gamma fee_rate risky_before','bands')
    w, mu, var, gamma, fee = (number(d[k]) for k in ['wealth','mean_excess','variance','gamma','fee_rate'])
    require(isinstance(d['risky_before'],list) and 1 <= len(d['risky_before']) <= 20, 'Supply old positions')
    return [band_decision(w,number(old),mu,var,gamma,fee) for old in d['risky_before']]


def uncertainty_case(d):
    q=unpack(d,'wealth risky_before estimated_mean half_width variance gamma fee_rate','uncertainty')
    w,old,mu,width,var,gamma,fee=(q[k] for k in ['wealth','risky_before','estimated_mean','half_width','variance','gamma','fee_rate'])
    require(width >= 0,'Mean interval half-width must be nonnegative')
    nominal=band_decision(w,old,mu,var,gamma,fee)
    robust=band_decision(w,old,mu-width,var,gamma,fee)
    a=gamma*var
    def worst(x):return (mu-width)*x-a*x*x/2-fee*abs(x-old)
    return {'mean_interval':[mu-width,mu+width],'nominal':nominal,'robust':robust,'worst_case_variable_criteria':{'hold':worst(old),'nominal':worst(nominal['risky_after']),'robust':worst(robust['risky_after'])}}


def horizon_case(d):
    keys(d,'mean_log sd_log periods','horizon')
    mu,sd=number(d['mean_log']),number(d['sd_log'])
    require(sd >= 0 and isinstance(d['periods'],list) and 1 <= len(d['periods']) <= 20,'Invalid horizon inputs')
    require(all(type(n) is int and 1 <= n <= 100 for n in d['periods']),'Periods must be integers in [1,100]')
    return [{'periods':n,'expected_cumulative_log':n*mu,'cumulative_log_variance':n*sd**2,'average_log_variance':sd**2/n} for n in d['periods']]


def withdrawal_case(d):
    keys(d,'wealth payment gross_returns','withdrawals')
    w,payment=number(d['wealth']),number(d['payment'])
    require(w > 0 and payment >= 0 and isinstance(d['gross_returns'],list) and len(d['gross_returns'])==2,'Invalid withdrawal contract')
    gs=[number(g) for g in d['gross_returns']]
    require(all(0 < g <= 10 for g in gs),'Positive finite gross returns required')
    rows=[]
    for name,returns in [('listed',gs),('reversed',list(reversed(gs)))]:
        wealth=w; ledger=[]
        for i,g in enumerate(returns,1):
            before=wealth;earned=before*g
            require(earned >= payment,'Payment cannot be funded in every required path')
            wealth=earned-payment
            ledger.append({'period':i,'start':before,'gross_return':g,'before_payment':earned,'payment':payment,'end':wealth})
        rows.append({'order':name,'terminal_wealth':wealth,'ledger':ledger})
    return {'no_payment_terminal':w*gs[0]*gs[1],'paths':rows,'listed_minus_reversed':rows[0]['terminal_wealth']-rows[1]['terminal_wealth']}


def serial(value):
    if isinstance(value,F):return value.numerator if value.denominator==1 else str(value)
    if isinstance(value,float):require(math.isfinite(value),'Nonfinite numerical result');return value
    if isinstance(value,dict):return {k:serial(v) for k,v in value.items()}
    if isinstance(value,list):return [serial(v) for v in value]
    return value


def run(data):
    keys(data,'case provenance units conventions liability lifecycle dynamic rebalancing bands uncertainty horizon withdrawals','root')
    require(data['case']=='Cedar allocation council — authored teaching cases','Wrong fixture identity')
    require(data['provenance']=='Synthetic parameters created for this chapter; no observed or forecast market data.','Synthetic provenance must remain explicit')
    require(data['units']=='CU and one-period gross returns; each panel is a separate stated model.','Wrong units')
    require(data['conventions']==CONVENTIONS,'Contradictory or incomplete model convention')
    return serial({'case':data['case'],'liability':liability_case(data['liability']),'lifecycle':lifecycle_case(data['lifecycle']),'dynamic':dynamic_case(data['dynamic']),'rebalancing':rebalance_case(data['rebalancing']),'bands':band_case(data['bands']),'uncertainty':uncertainty_case(data['uncertainty']),'horizon':horizon_case(data['horizon']),'withdrawals':withdrawal_case(data['withdrawals']),'limits':'Independent authored panels; conditional optima do not validate preference, probability, liquidity or forecast assumptions.'})


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,default=Path(__file__).with_name('v09-c09-inputs.json'))
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    result=run(json.loads(args.input.read_text()))
    rendered=json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
    if args.output:args.output.write_text(rendered)
    else:print(rendered,end='')


if __name__=='__main__':main()
