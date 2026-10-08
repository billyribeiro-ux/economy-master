#!/usr/bin/env python3
"""Exact, bounded synthetic crisis accounts. Standard library; no network."""
from fractions import Fraction as F
from pathlib import Path
import json
import re
import sys

DECIMAL = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]{1,9})?\Z")


def number(value, name):
    if type(value) is int:
        result = F(value)
    elif type(value) is str and len(value) <= 32 and DECIMAL.fullmatch(value):
        result = F(value)
    else:
        raise ValueError(name + ': use an integer or finite decimal string (at most 9 decimal places)')
    if abs(result) > 1_000_000:
        raise ValueError(name + ': absolute value must be at most 1000000')
    return result


def fields(obj, names, name):
    if type(obj) is not dict or set(obj) != set(names):
        raise ValueError(name + ': unexpected or missing fields')
    return {key: number(obj[key], name + '.' + key) for key in names}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate(raw):
    require(type(raw) is dict and set(raw) == {'schema_version', 'bank', 'collateral', 'fx', 'fiscal'},
            'root: exact schema fields required')
    require(type(raw['schema_version']) is int and raw['schema_version'] == 1, 'schema_version must be integer 1')
    bank = fields(raw['bank'], ('cash', 'loan_face', 'deposits', 'withdrawal', 'sale_price', 'bad_recovery', 'injection'), 'bank')
    c, k, d, w, q, v, j = (bank[key] for key in ('cash', 'loan_face', 'deposits', 'withdrawal', 'sale_price', 'bad_recovery', 'injection'))
    require(0 <= c < w <= d and k > 0 and c + k >= d, 'bank: require 0 <= cash < withdrawal <= deposits and nonnegative opening book equity')
    require(0 < q <= 1 and (w-c)/q <= k, 'bank: positive price at most 1 and sufficient pool for sale required')
    require(0 <= v <= k and c+v <= d and j >= 0, 'bank: recovery in [0,face], bad-state equity at most zero, nonnegative injection required')
    items = raw['collateral']
    require(type(items) is list and 1 <= len(items) <= 20, 'collateral: list of 1 to 20 cases required')
    cases = []
    ids = set()
    for item in items:
        require(type(item) is dict and set(item) == {'id','units','debt','ltv','price_intercept','price_impact'}, 'collateral: exact case fields required')
        label = item['id']
        require(type(label) is str and re.fullmatch(r'[a-z][a-z0-9_-]{0,39}', label) is not None and label not in ids, 'collateral: unique simple case id required')
        ids.add(label)
        case = fields({k:v for k,v in item.items() if k != 'id'}, ('units','debt','ltv','price_intercept','price_impact'), 'collateral.' + label)
        k,b,t,p,a = (case[key] for key in ('units','debt','ltv','price_intercept','price_impact'))
        require(k > 0 and b >= 0 and 0 < t < 1 and a >= 0 and p > a*k, 'collateral: positive units/prices, nonnegative debt/impact, 0 < ltv < 1 required')
        cases.append((label, case))
    fx = fields(raw['fx'], ('reserves','exports','imports','old_debt','interest','private_new','reserve_floor','old_quote','new_quote'), 'fx')
    require(all(v >= 0 for v in fx.values()) and fx['old_quote'] > 0 and fx['new_quote'] > 0, 'fx: nonnegative amounts/rate and positive quotes required')
    fiscal = fields(raw['fiscal'], ('old_debt','gross_rate','cash','primary_1','primary_2','private_cap'), 'fiscal')
    require(all(fiscal[key] >= 0 for key in ('old_debt','cash','private_cap')) and fiscal['gross_rate'] >= 1, 'fiscal: nonnegative stocks/cap and gross rate at least one required')
    base_issue = fiscal['gross_rate']*fiscal['old_debt']-fiscal['primary_1']-fiscal['cash']
    require(base_issue >= 0, 'fiscal: this borrowing-only lab requires nonnegative baseline issuance')
    return bank, cases, fx, fiscal


def bank_case(b):
    c,k,d,w,q,v,j = (b[key] for key in ('cash','loan_face','deposits','withdrawal','sale_price','bad_recovery','injection'))
    bridge = w-c
    sale = bridge/q
    liability = d-w+bridge
    residual = v+j-liability
    return {
        'opening': {'assets':c+k, 'deposits':d, 'equity':c+k-d},
        'cash_gap':bridge,
        'sale_full_repayment': {'face_sold':sale, 'receipts':q*sale, 'remaining_assets':k-sale, 'deposits':d-w, 'equity':k-sale-d+w, 'buyer_discount_gain':(1-q)*sale},
        'bridge_full_repayment': {'remaining_assets':k, 'deposits':d-w, 'bridge':bridge, 'equity':k-liability},
        'bridge_bad': {'assets':v, 'total_liabilities':liability, 'economic_equity':v-liability, 'senior_payment':min(v,bridge), 'late_deposit_payment':min(d-w,max(F(0),v-bridge)), 'creditor_shortfall':max(F(0),liability-v)},
        'public_support_bad': {'cash':j, 'loans':v, 'total_liabilities':liability, 'residual_after_full_payment':residual, 'public_recovery':max(F(0),residual), 'creditor_shortfall':max(F(0),-residual)}
    }


def collateral_case(c):
    k,b,t,p,a = (c[key] for key in ('units','debt','ltv','price_intercept','price_impact'))
    linear = p*(1-t)-a*t*k
    quadratic = a*(1-t)
    h = lambda x: (p-a*x)*(t*k+(1-t)*x)
    if a == 0:
        vertex = k
    else:
        vertex = min(k,max(F(0),linear/(2*quadratic)))
    maximum = h(vertex)
    result = {'maximizer':vertex, 'maximum_supported_debt':maximum, 'initial_supported_debt':h(0), 'sale_only_feasible':b <= maximum}
    if b > maximum:
        result['minimum_sale'] = None
        return result
    if b <= h(0):
        low = high = F(0)
    elif a == 0:
        low = high = (b-h(0))/linear
    elif b == maximum:
        low = high = vertex
    else:
        low, high = F(0), vertex
        # On this interval H is increasing. Preserve H(low)<b<=H(high).
        for _ in range(80):
            mid = (low+high)/2
            if h(mid) == b:
                low = high = mid
                break
            if h(mid) < b:
                low = mid
            else:
                high = mid
        # Some arbitrarily larger sales can overpay debt. The bracket describes
        # the mathematical first crossing; do not label its upper endpoint as
        # a feasible transaction without separately reporting the debt check.
    price = p-a*high
    receipts = price*high
    debt = b-receipts
    assets = price*(k-high)
    result['minimum_sale'] = {
        'lower':low, 'upper':high, 'width':high-low, 'exact':low == high,
        'upper_price':price, 'upper_receipts':receipts, 'upper_remaining_debt':debt,
        'upper_remaining_assets':assets, 'upper_equity':assets-debt,
        'upper_ltv_slack':t*assets-debt, 'upper_nonnegative_debt':debt >= 0
    }
    return result


def fx_case(c):
    r0,x,m,d,i,n,floor,e0,e1 = (c[key] for key in ('reserves','exports','imports','old_debt','interest','private_new','reserve_floor','old_quote','new_quote'))
    interest = i*d
    official = max(F(0),floor+m+d+interest-r0-x-n)
    r1 = r0+x+n+official-m-d-interest
    d1 = n+official
    ca = (x-m-interest)*e1
    fa = ((r1-r0)-(d1-d))*e1
    value = (r0-d)*(e1-e0)
    start = (r0-d)*e0
    end = (r1-d1)*e1
    return {'interest_F':interest, 'official_required_F':official, 'unsupported_max_imports_F':r0+x+n-d-interest-floor,
            'closing_reserves_F':r1, 'closing_debt_F':d1, 'CA_H':ca, 'FA_H':fa, 'valuation_H':value,
            'opening_NFA_H':start, 'closing_NFA_H':end, 'stock_flow_residual_H':end-start-fa-value,
            'official_availability_assumed_for_supported_case':True}


def fiscal_case(c, injection, recovery):
    b,r,cash,s1,s2,cap = (c[key] for key in ('old_debt','gross_rate','cash','primary_1','primary_2','private_cap'))
    issue = r*b-s1-cash+injection
    terminal = s2+recovery-r*issue
    asset = recovery/r
    transfer = injection-asset
    primary = s1-transfer
    adjustment = asset-cash
    return {'cash_payment':injection, 'terminal_claim_recovery':recovery, 'gross_issuance':issue, 'debt_stock_change':issue-b,
            'immediate_gap':max(F(0),issue-cap), 'terminal_resources':s2+recovery, 'terminal_debt_service':r*issue,
            'terminal_cash':terminal, 'terminal_shortfall':max(F(0),-terminal), 'terminal_feasible':terminal >= 0,
            'minimum_terminal_primary':r*issue-recovery, 'claim_value_at_date_1':asset,
            'transfer_component':transfer, 'post_support_primary_1':primary, 'stock_flow_adjustment_1':adjustment,
            'debt_identity_residual':issue-(r*b-primary+adjustment),
            'present_value_margin':(s1+cash-injection)/r+(s2+recovery)/(r*r)-b}


def encode(value):
    if isinstance(value,F):
        return str(value)
    if isinstance(value,dict):
        return {k:encode(v) for k,v in value.items()}
    if isinstance(value,list):
        return [encode(v) for v in value]
    return value


def run(raw):
    bank, collateral, fx, fiscal = validate(raw)
    bank_result = bank_case(bank)
    rescue = bank_result['public_support_bad']
    return encode({'status':'computed', 'bank':bank_result,
        'collateral':{label:collateral_case(case) for label,case in collateral},
        'fx':fx_case(fx), 'fiscal':{'baseline':fiscal_case(fiscal,F(0),F(0)),
        'linked_bank_support':fiscal_case(fiscal,bank['injection'],rescue['public_recovery']),
        'supported_bank_pays_creditors_in_full':rescue['creditor_shortfall'] == 0}})


def pairs_unique(items):
    result = {}
    for key,value in items:
        if key in result:
            raise ValueError('duplicate JSON key: '+key)
        result[key] = value
    return result


def reject_constant(value):
    raise ValueError('nonfinite JSON constant: '+value)


def load(path):
    require(path.stat().st_size <= 100_000, 'input file exceeds 100000 bytes')
    return json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=pairs_unique, parse_constant=reject_constant)


def main():
    try:
        require(len(sys.argv) <= 2, 'usage: python3 v06-c12-analysis.py [input.json]')
        path = Path(sys.argv[1]) if len(sys.argv) == 2 else Path(__file__).with_name('v06-c12-inputs.json')
        result = run(load(path))
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({'status':'error','message':str(exc)},sort_keys=True,allow_nan=False))
        return 2
    print(json.dumps(result,sort_keys=True,indent=2,allow_nan=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
