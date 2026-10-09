"""Aster: a bounded, offline bond cash-flow and quotation laboratory.

All inputs and case contracts are synthetic. No network, trading or calendar
database is used. Fractions are serialized as exact strings; roots/logs are
finite floats. See the adjacent README for the deliberately limited contract.
"""
import argparse
from datetime import date
from fractions import Fraction as F
import json
import math
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
NUMBER = re.compile(r'-?\d{1,9}(?:\.\d{1,9}|/[1-9]\d{0,8})?\Z')


def require(value, message):
    if not value:
        raise ValueError(message)


def number(value):
    require(isinstance(value, str) and NUMBER.fullmatch(value), 'Use bounded decimal or rational strings')
    return F(value)


def keys(value, expected):
    require(isinstance(value, dict) and set(value) == set(expected.split()), 'Unexpected or missing contract field')


def sequence(value, length):
    require(isinstance(value, list) and len(value) == length, 'Wrong number of dated entries')
    return [number(x) for x in value]


def bootstrap(prices, cashflows):
    discounts = []
    for i, (price, row) in enumerate(zip(prices, cashflows)):
        require(len(row) == i+1 and row[-1] > 0 and min(row) >= 0, 'Positive triangular cash-flow system required')
        residual = price-sum(c*d for c, d in zip(row[:-1], discounts))
        discount = residual/row[-1]
        require(0 < discount <= 10, 'Implied discount outside positive bounded laboratory domain')
        discounts.append(discount)
    return discounts


def validate(data):
    keys(data, 'schema provenance settlement bootstrap yield_case forward bill')
    require(type(data['schema']) is int and data['schema'] == 1, 'Unknown schema')
    require(data['provenance'] == 'Original synthetic Aster bond laboratory; no market observations.', 'Synthetic provenance must be preserved')
    s = data['settlement']
    keys(s, 'previous_coupon settlement next_coupon maturity face annual_coupon invoice_face discounts')
    require([s[k] for k in ('previous_coupon','next_coupon','maturity')] == ['2025-01-15','2025-07-15','2026-01-15'], 'This fixture has an exact regular semiannual schedule')
    require(all(isinstance(s[k],str) for k in ('previous_coupon','settlement','next_coupon','maturity')), 'ISO calendar strings required')
    dates = [date.fromisoformat(s[k]) for k in ('previous_coupon','settlement','next_coupon','maturity')]
    require(dates[0] <= dates[1] < dates[2] < dates[3], 'Settlement must be in the supplied cum-coupon interval')
    require(0 < number(s['face']) <= 1000000 and 0 < number(s['invoice_face']) <= 100000000, 'Positive bounded faces required')
    require(0 <= number(s['annual_coupon']) <= F(1,2), 'Coupon outside fixture domain')
    require(all(0 < d <= 10 for d in sequence(s['discounts'],2)), 'Positive bounded settlement discount factors required')
    b = data['bootstrap']
    keys(b, 'prices cashflows target_cashflows target_quote')
    p = sequence(b['prices'],3)
    require(min(p)>0 and max(p)<=1000, 'Positive bounded observed prices required')
    require(b['cashflows'] == [['100'],['4','104'],['6','6','106']], 'The three observed instrument contracts are fixed')
    bootstrap(p, [[number(x) for x in row] for row in b['cashflows']])
    target = sequence(b['target_cashflows'],3)
    require(min(target)>=0 and 0 < sum(target)<=10000, 'Nonnegative target cash flows required')
    require(0 < number(b['target_quote']) <= 10000, 'Positive target quote required')
    y = data['yield_case']
    keys(y, 'face annual_coupon reinvestment_rate sale_yield_at_year_one')
    require(0 < number(y['face']) <= 1000000, 'Positive bounded yield-case face required')
    require(0 <= number(y['annual_coupon']) <= F(1,2), 'Yield-case coupon outside domain')
    require(-1 < number(y['reinvestment_rate']) <= 2 and -1 < number(y['sale_yield_at_year_one']) <= 2, 'Positive annual growth factors required')
    f = data['forward']
    keys(f, 'start_year end_year principal offered_effective_annual_rate')
    require(type(f['start_year']) is int and type(f['end_year']) is int and 1 <= f['start_year'] < f['end_year'] <= 3, 'Forward dates must be observed curve years')
    require(0 < number(f['principal']) <= 1000000, 'Positive bounded forward principal required')
    require(-1 < number(f['offered_effective_annual_rate']) <= 2, 'Offered forward gross rate must be positive')
    q = data['bill']
    keys(q, 'face discount_rate days quote_basis')
    require(type(q['days']) is int and 1 <= q['days'] <= 365, 'Bill days must be a positive bounded integer')
    require(type(q['quote_basis']) is int and q['quote_basis'] == 360, 'This bill has the explicitly supplied 360-day quote basis')
    require(0 < number(q['face']) <= 1000000 and -F(1,2) <= number(q['discount_rate']) < 1, 'Bill quote outside bounded domain')
    require(1-number(q['discount_rate'])*F(q['days'],q['quote_basis'])>0, 'Bill price must be positive')


def yield_root(cashflows, price):
    """Monotone bisection in log annual gross yield, including negative yields."""
    require(price>0 and 1<=len(cashflows)<=3 and min(cashflows)>=0 and sum(cashflows)>0, 'Positive price and one to three future nonnegative cash flows required')
    def value(log_gross):
        return sum(float(c)*math.exp(-(i+1)*log_gross) for i,c in enumerate(cashflows))
    lower,upper = -100.0,100.0
    require(value(lower)>float(price)>value(upper), 'Root outside supported numerical bracket')
    for _ in range(100):
        middle=(lower+upper)/2
        if value(middle)>float(price):lower=middle
        else:upper=middle
    return math.expm1((lower+upper)/2)


def serial(value):
    if isinstance(value,F):return str(value)
    if isinstance(value,dict):return {k:serial(v) for k,v in value.items()}
    if isinstance(value,list):return [serial(v) for v in value]
    if isinstance(value,float):require(math.isfinite(value),'Nonfinite output')
    return value


def run(data):
    validate(data)
    s=data['settlement'];previous,settle,next_date,final=[date.fromisoformat(s[k]) for k in ('previous_coupon','settlement','next_coupon','maturity')]
    face=number(s['face']);coupon=face*number(s['annual_coupon'])/2
    elapsed=(settle-previous).days;period=(next_date-previous).days
    remaining=(next_date-settle).days;discounts=sequence(s['discounts'],2)
    cash=[coupon,coupon+face];dirty=sum(c*d for c,d in zip(cash,discounts));accrued=coupon*F(elapsed,period)
    scale=number(s['invoice_face'])/face
    settlement={'elapsed_days':elapsed,'coupon_period_days':period,'days_to_next_coupon':remaining,'days_to_maturity':(final-settle).days,'coupon':coupon,'cashflows':cash,'dirty':dirty,'accrued':accrued,'clean':dirty-accrued,'invoice_dirty':dirty*scale,'invoice_accrued':accrued*scale,'invoice_clean':(dirty-accrued)*scale}
    b=data['bootstrap'];prices=sequence(b['prices'],3);rows=[[number(x) for x in row] for row in b['cashflows']];d=bootstrap(prices,rows)
    target=sequence(b['target_cashflows'],3);holdings=[F(0)]*3
    for i in range(2,-1,-1):holdings[i]=(target[i]-sum(holdings[j]*rows[j][i] for j in range(i+1,3)))/rows[i][i]
    fair=sum(x*y for x,y in zip(target,d));quote=number(b['target_quote'])
    curve={'discounts':d,'repriced_instruments':[sum(cf*df for cf,df in zip(row,d)) for row in rows],'annual_spots':[float(df)**(-1/(i+1))-1 for i,df in enumerate(d)],'continuous_spots':[-math.log(float(df))/(i+1) for i,df in enumerate(d)],'one_year_forward_gross':[d[i]/d[i+1] for i in range(2)],'target_fair_price':fair,'replicating_holdings':holdings,'replica_cost':sum(h*p for h,p in zip(holdings,prices)),'quoted_target_minus_fair':quote-fair,'replica_cashflows':[sum(holdings[j]*rows[j][i] for j in range(i,3)) for i in range(3)]}
    y=data['yield_case'];yf=number(y['face']);yc=yf*number(y['annual_coupon']);cf=[yc,yc+yf];yp=sum(c*z for c,z in zip(cf,d));root=yield_root(cf,yp)
    terminal=cf[1]+cf[0]*(1+number(y['reinvestment_rate']));sale=cf[1]/(1+number(y['sale_yield_at_year_one']))
    yields={'cashflows':cf,'price':yp,'annual_ytm':root,'root_repricing':sum(float(c)/(1+root)**(i+1) for i,c in enumerate(cf)),'terminal_wealth_actual_reinvestment':terminal,'annualized_terminal_growth':math.sqrt(float(terminal/yp))-1,'terminal_wealth_at_ytm_reinvestment':float(cf[1])+float(cf[0])*(1+root),'sale_price_at_year_one':sale,'one_year_holding_return':(cf[0]+sale)/yp-1,'two_year_zero_spot':float(d[1])**(-.5)-1}
    f=data['forward'];start,end=f['start_year'],f['end_year'];principal=number(f['principal']);ds,dt=d[start-1],d[end-1];gross=ds/dt;payoff=principal*gross;offered=principal*(1+number(f['offered_effective_annual_rate']))**(end-start)
    forward={'start_year':start,'end_year':end,'gross_locked':gross,'effective_annual_locked':float(gross)**(1/(end-start))-1,'continuous_annual_locked':math.log(float(gross))/(end-start),'lend_at_start':principal,'receive_at_end':payoff,'initial_cost':payoff*dt-principal*ds,'offered_end_receipt':offered,'offered_lender_contract_value':offered*dt-principal*ds,'offered_minus_locked_terminal':offered-payoff}
    mid_discount=math.sqrt(float(d[0]*d[1]));bumped=mid_discount*math.exp(.005)
    interpolation={'year':1.5,'linear_discount':(d[0]+d[1])/2,'log_linear_discount':mid_discount,'positive_log_perturbation_discount':bumped,'perturbation_coefficient':.02,'price_per_100_linear':50*(d[0]+d[1]),'price_per_100_log_linear':100*mid_discount,'price_per_100_perturbed':100*bumped,'observed_endpoints_unchanged':True}
    q=data['bill'];bf=number(q['face']);bd=number(q['discount_rate']);tau=F(q['days'],q['quote_basis']);bp=bf*(1-bd*tau);gain=bf/bp-1
    bill={'quote_year_fraction':tau,'price':bp,'holding_gain':gain,'investment_simple_360':gain/tau,'investment_simple_365':gain/F(q['days'],365),'effective_annual_360':float(bf/bp)**(1/float(tau))-1,'continuous_annual_360':math.log(float(bf/bp))/float(tau),'incorrect_simple_yield_price':bf/(1+bd*tau)}
    result=serial({'case':'Aster bond laboratory','settlement':settlement,'curve':curve,'yield_case':yields,'forward':forward,'interpolation':interpolation,'bill':bill})
    json.dumps(result,allow_nan=False)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,default=HERE/'v10-c01-inputs.json')
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    data=json.loads(args.input.read_text(),parse_constant=lambda s: (_ for _ in ()).throw(ValueError('Nonfinite JSON '+s)))
    text=json.dumps(run(data),indent=2,allow_nan=False)+'\n'
    if args.output:args.output.write_text(text)
    else:print(text,end='')


if __name__=='__main__':main()
