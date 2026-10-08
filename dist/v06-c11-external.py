"""Exact synthetic external accounts and parity lab. Standard library; no network.

The routines return Fractions internally; run() packs them as exact strings.
Invalid input is distinct from a well-defined but infeasible regime candidate.
"""
import argparse
from fractions import Fraction as F
import json
from pathlib import Path
import re

DEFAULT = Path(__file__).with_name('v06-c11-cases.json')


def require(test, message):
    if not test:
        raise ValueError(message)


def number(x):
    require(isinstance(x, str) and re.fullmatch(r'-?\d+(?:/[1-9]\d*)?', x),
            'numeric inputs must be integer/rational strings')
    return F(x)


def nums(row, keys):
    return [number(row[key]) for key in keys.split()]


def pack(x):
    if isinstance(x, F):
        return str(x)
    if isinstance(x, dict):
        return {k: pack(v) for k, v in x.items()}
    if isinstance(x, (tuple, list)):
        return [pack(v) for v in x]
    return x


def names(rows):
    require(isinstance(rows, list) and rows, 'nonempty case list required')
    ids = [r['id'] for r in rows]
    require(all(isinstance(k, str) and k for k in ids), 'nonempty string ids')
    require(len(set(ids)) == len(ids), 'duplicate ids')


def ledger(case):
    rows = case['rows']
    names(rows)
    keys = 'CA KA private_assets reserves liabilities'.split()
    totals = dict.fromkeys(keys, F(0))
    for row in rows:
        ca, ka, private, reserve, liab = nums(row, ' '.join(keys))
        require(ca+ka == private+reserve-liab, 'unbalanced transaction '+row['id'])
        for key in keys:
            totals[key] += number(row[key])
    a0,l0,av,lv,ao,lo = nums(case, 'opening_assets opening_liabilities asset_valuation liability_valuation asset_other_volume liability_other_volume')
    at = totals['private_assets']+totals['reserves']
    lt = totals['liabilities']
    a1,l1 = a0+at+av+ao, l0+lt+lv+lo
    require(min(a0,l0,a1,l1) >= 0, 'gross positions cannot be negative')
    y,c,g,inv,nx,ei,ti = nums(case, 'GDP C G_consumption I_all net_exports net_earned_income net_transfer_income')
    require(min(y,c,g,inv) >= 0, 'nonnegative aggregate levels')
    require(y == c+g+inv+nx, 'GDP expenditure reconciliation')
    require(totals['CA'] == nx+ei+ti, 'current account income bridge')
    saving = y+ei+ti-c-g
    fa = at-lt
    return dict(totals=totals, asset_transactions=at, FA=fa,
                statistical_discrepancy=fa-totals['CA']-totals['KA'],
                assets_close=a1, liabilities_close=l1, NFA_open=a0-l0,
                NFA_close=a1-l1, net_valuation=av-lv, net_other_volume=ao-lo,
                GNDI=y+ei+ti, saving=saving, saving_minus_investment=saving-inv)


def currency(case):
    e0,e1,a,l,ai,li = nums(case,'e0 e1 asset_F liability_F asset_interest_F liability_interest_F')
    require(min(e0,e1)>0 and min(a,l)>=0, 'positive quotes and nonnegative principal')
    require(a+ai>=0 and l+li>=0, 'nonnegative closing foreign positions')
    # Interest may be negative; it accrues after the principal is revalued.
    return dict(assets_open=e0*a, liabilities_open=e0*l,
                assets_close=e1*(a+ai), liabilities_close=e1*(l+li),
                asset_transactions=e1*ai, liability_transactions=e1*li,
                CA=e1*(ai-li), FA=e1*(ai-li),
                net_valuation=(e1-e0)*(a-l), NFA_open=e0*(a-l),
                NFA_close=e1*(a+ai-l-li))


def ppp(case):
    e0,e1,p0,p1,pf0,pf1 = nums(case,'e0 e1 P0 P1 PF0 PF1')
    require(min(e0,e1,p0,p1,pf0,pf1)>0, 'strictly positive prices and quotes')
    q0,q1 = e0*pf0/p0,e1*pf1/p1
    parity_e = e0*(p1/p0)/(pf1/pf0)
    return dict(q0=q0,q1=q1,real_depreciation=q1/q0-1,
                nominal_depreciation=e1/e0-1,inverse_quote_change=e0/e1-1,
                relative_PPP_quote=parity_e,relative_PPP_depreciation=parity_e/e0-1,
                inflation_difference=p1/p0-pf1/pf0)


def parity(case):
    e,rh,rf,fw,hp,fp = nums(case,'e RH RF forward home_principal foreign_principal')
    require(min(e,rh,rf,fw,hp,fp)>0, 'positive quotes/gross returns/principals')
    foreign_maturity=hp*rf/e
    home_maturity=fp*e*rh
    return dict(parity_forward=e*rh/rf,
                borrow_H_foreign_maturity=foreign_maturity,
                borrow_H_forward_receipt=foreign_maturity*fw,
                borrow_H_repayment=hp*rh,
                borrow_H_profit=foreign_maturity*fw-hp*rh,
                borrow_F_home_maturity=home_maturity,
                borrow_F_foreign_repayment=fp*rf,
                borrow_F_forward_cost=fp*rf*fw,
                borrow_F_profit=home_maturity-fp*rf*fw)


def uncovered(case):
    e,rh,rf=nums(case,'e RH RF')
    require(min(e,rh,rf)>0,'positive spot and gross returns')
    states=case['states']
    require(isinstance(states,list) and states,'nonempty states')
    ps=[number(r['probability']) for r in states]
    quotes=[number(r['e_next']) for r in states]
    require(all(p>0 for p in ps) and sum(ps)==1,'positive probabilities sum to one')
    require(min(quotes)>0,'positive future quotes')
    mean=sum(p*q for p,q in zip(ps,quotes))
    returns=[rf*q/e for q in quotes]
    return dict(mean_spot=mean,expected_depreciation=mean/e-1,
                UIP_depreciation=rh/rf-1,parity_forward=e*rh/rf,
                state_gross_home_returns=returns,
                expected_gross_home_return=sum(p*r for p,r in zip(ps,returns)),
                expected_excess_foreign_return=rf*mean/e-rh,
                expected_reciprocal=sum(p/q for p,q in zip(ps,quotes)),
                reciprocal_expectation=1/mean)


def bid_ask(case):
    eb,ea,fb,fa,rhl,rhb,rfl,rfb=nums(case,'spot_bid spot_ask forward_bid forward_ask RH_lend RH_borrow RF_lend RF_borrow')
    require(min(eb,ea,fb,fa,rhl,rhb,rfl,rfb)>0,'positive executable quotes/returns')
    require(eb<=ea and fb<=fa and rhl<=rhb and rfl<=rfb,'ordered bid/ask and funding rates')
    first=fb*rfl/ea-rhb
    second=eb*rhl-fa*rfb
    return dict(profit_per_H_borrowed=first,profit_per_F_borrowed_in_H=second,
                no_arbitrage_in_these_two_strategies=(first<=0 and second<=0))


def regime(primitives,case):
    p,a,chi,e0,r0,k0,m=nums(primitives,'P a chi e_initial reserve_initial equity_initial future_spot_mean')
    d,rf=nums(case,'D RF')
    require(min(p,a,chi,e0,m)>0 and min(r0,d)>=0 and rf>=1,
            'regime domain: positive prices/scales, nonnegative holdings and foreign rate')
    require(case['regime'] in ('peg','float'),'unknown regime')
    if case['regime']=='peg':
        interest=rf-1
        h=p*(a-chi*interest)
        reserves=(h+k0-d)/e0
        quote, equity=e0,k0
        reason='nonpositive money demand' if h<=0 else ('negative required reserves' if reserves<0 else None)
    else:
        reserves=r0
        h=d+e0*r0-k0
        interest=(a-h/p)/chi
        if h<=0 or interest<0:
            return dict(feasible=False,reason='money/currency-rate domain',H=h,i_H=interest,
                        R=reserves,e=None,K=None)
        quote=m*rf/(1+interest)
        equity=k0+(quote-e0)*r0
        reason=None
    return dict(feasible=reason is None,reason=reason,H=h,i_H=interest,R=reserves,e=quote,K=equity)


def run(data):
    require(data['schema']=='v06-c11-external-v1' and data['synthetic'] is True,
            'recognized explicitly synthetic input required')
    out={'schema':data['schema'],'synthetic':True,'numeric_encoding':'exact rational strings',
         'ledger':ledger(data['ledger'])}
    for key,fn in [('currency_cases',currency),('ppp_cases',ppp),('parity_cases',parity)]:
        names(data[key]);out[key]={r['id']:fn(r) for r in data[key]}
    out['uncovered']=uncovered(data['uncovered'])
    out['bid_ask']=bid_ask(data['bid_ask'])
    names(data['regime_cases'])
    out['regime_cases']={r['id']:regime(data['regime_primitives'],r) for r in data['regime_cases']}
    return pack(out)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input',nargs='?',type=Path,default=DEFAULT)
    args=parser.parse_args()
    try:
        result=run(json.loads(args.input.read_text()))
    except (ValueError,KeyError,TypeError,OSError) as exc:
        parser.exit(2,'input error: '+str(exc)+'\n')
    print(json.dumps(result,indent=2,allow_nan=False))


if __name__=='__main__':
    main()
