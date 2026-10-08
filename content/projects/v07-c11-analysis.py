#!/usr/bin/env python3
"""Original exact accounting-comparability lab; standard library, no network."""
import argparse
from fractions import Fraction as F
import json
from pathlib import Path


def rational(value):
    if not isinstance(value, str):
        raise ValueError('money, quantity and price inputs must be rational strings')
    try:
        result = F(value)
    except (ValueError, ZeroDivisionError) as exc:
        raise ValueError('invalid rational string') from exc
    if result < 0:
        raise ValueError('this model requires nonnegative primitive inputs')
    return result


def years(value):
    if type(value) is not int or value <= 0:
        raise ValueError('life and elapsed-year inputs must be positive integers')
    return value


def layers(rows):
    result = []
    for row in rows:
        q, c = rational(row['quantity']), rational(row['unit_cost'])
        if q <= 0:
            raise ValueError('cost layers require positive quantities')
        result.append([q, c])
    return result


def cost(rows):
    return sum((q*c for q,c in rows), F(0))


def consume(rows, sold, method):
    if sold > sum((q for q,c in rows), F(0)):
        raise ValueError('cannot sell more physical inventory than available')
    remaining, cogs = sold, F(0)
    while remaining:
        index = 0 if method == 'FIFO' else -1
        q, c = rows[index]
        taken = min(q, remaining)
        cogs += taken*c
        remaining -= taken
        if taken == q:
            rows.pop(index)
        else:
            rows[index][0] -= taken
    return cogs


def inventory(case):
    opening = layers(case['opening_layers'])
    cash0, debt, capital, re0 = (rational(case[k]) for k in ('opening_cash','liabilities','share_capital','opening_retained'))
    inv0 = cost(opening)
    if cash0+inv0 != debt+capital+re0:
        raise ValueError('opening balance sheet does not reconcile')
    if not case['periods']:
        raise ValueError('at least one period is required')
    names = [p['period'] for p in case['periods']]
    if any(not isinstance(n,str) or not n for n in names) or len(set(names)) != len(names):
        raise ValueError('period labels must be nonempty and unique; array order gives chronology')
    bases = {}
    for method in ('FIFO','LIFO'):
        stock = [r[:] for r in opening]
        cash, retained = cash0, re0
        history = []
        for period in case['periods']:
            opening_inventory, opening_cash = cost(stock), cash
            purchase_layers = layers(period['purchases'])
            purchases = cost(purchase_layers)
            sold, sale_price, operating = (rational(period[k]) for k in ('sold','sale_price','operating_cash'))
            cash -= purchases
            purchase_cash = cash
            if cash < 0:
                raise ValueError('cash purchases cannot be funded at the supplied date')
            stock.extend(purchase_layers)
            cogs = consume(stock, sold, method)
            revenue = sold*sale_price
            cash += revenue
            sale_cash = cash
            cash -= operating
            if cash < 0:
                raise ValueError('operating payment cannot be funded at the supplied date')
            ending_inventory = cost(stock)
            profit = revenue-cogs-operating
            retained += profit
            cfo = revenue-purchases-operating
            equity = capital+retained
            history.append({
                'period':period['period'], 'opening_inventory':opening_inventory,
                'purchases':purchases, 'revenue':revenue, 'cogs':cogs,
                'operating_expense':operating, 'profit':profit,
                'closing_layers':[{'quantity':q,'unit_cost':c} for q,c in stock],
                'closing_quantity':sum((q for q,c in stock),F(0)),
                'closing_inventory':ending_inventory, 'inventory_change':ending_inventory-opening_inventory,
                'cash_after_purchase':purchase_cash, 'cash_after_sale':sale_cash, 'closing_cash':cash,
                'cfo':cfo, 'assets':cash+ending_inventory, 'liabilities':debt,
                'share_capital':capital, 'retained':retained, 'equity':equity,
                'residuals':{'inventory':opening_inventory+purchases-cogs-ending_inventory,
                             'balance_sheet':cash+ending_inventory-debt-equity,
                             'indirect_cfo':profit-(ending_inventory-opening_inventory)-cfo,
                             'cash_bridge':opening_cash+cfo-cash}})
        bases[method] = history
    reserve, bridge = F(0), []
    for f,l in zip(bases['FIFO'],bases['LIFO']):
        current = f['closing_inventory']-l['closing_inventory']
        change = current-reserve
        bridge.append({'period':f['period'],'opening_reserve':reserve,'closing_reserve':current,
                       'reserve_change':change,'cogs_adjustment':-change,'profit_adjustment':change,
                       'equity_adjustment':current,'cash_adjustment':f['closing_cash']-l['closing_cash'],
                       'residuals':{'profit':f['profit']-l['profit']-change,
                                    'equity':f['equity']-l['equity']-current,
                                    'cash':f['closing_cash']-l['closing_cash']}})
        reserve = current
    return {'bases':bases,'common_FIFO_bridge':bridge}


def asset(case):
    amount, residual, operating = (rational(case[k]) for k in ('cost','residual','cash_profit_before_depreciation'))
    old, elapsed, remaining, correct = (years(case[k]) for k in ('original_life','elapsed_years','revised_remaining_life','correct_original_life'))
    if amount <= residual or elapsed >= min(old,correct):
        raise ValueError('asset must retain depreciable value at the stated revision/correction date')
    original_depreciation = (amount-residual)/old
    correct_depreciation = (amount-residual)/correct
    carry = amount-elapsed*original_depreciation
    corrected_carry = amount-elapsed*correct_depreciation
    revised_depreciation = (carry-residual)/remaining
    horizon = max(old,elapsed+remaining,correct)
    schedules = {}
    for name in ('original','new_estimate','corrected_history'):
        carrying = amount
        rows = []
        for year in range(1,horizon+1):
            if name=='original':
                dep = original_depreciation if year<=old else F(0)
            elif name=='new_estimate':
                dep = original_depreciation if year<=elapsed else (revised_depreciation if year<=elapsed+remaining else F(0))
            else:
                dep = correct_depreciation if year<=correct else F(0)
            opening = carrying
            carrying -= dep
            rows.append({'period':f'X{year}','opening_asset':opening,'depreciation':dep,
                         'closing_asset':carrying,'profit':operating-dep,'cfo':operating,
                         'asset_residual':opening-dep-carrying,'cash_reconciliation_residual':operating-dep+dep-operating})
        schedules[name] = rows
    per_year_error = original_depreciation-correct_depreciation
    return {'original_start_revision_asset':carry,'revised_annual_depreciation':revised_depreciation,
            'corrected_start_revision_asset':corrected_carry,
            'corrected_annual_depreciation':correct_depreciation,
            'earliest_comparative_opening_equity_correction':(elapsed-1)*per_year_error,
            'last_comparative_profit_correction':per_year_error,
            'cumulative_prior_asset_equity_correction':elapsed*per_year_error,
            'prior_correction_cash':F(0),'prior_correction_in_discovery_profit':F(0),
            'schedules':schedules}


def segments(case):
    rows = []
    seen = set()
    for item in case['items']:
        name = item['name']
        if not isinstance(name,str) or not name or name in seen:
            raise ValueError('segment names must be nonempty and unique')
        seen.add(name)
        external, internal, other, assets = (rational(item[k]) for k in ('external_revenue','internal_revenue','other_segment_expenses','assets'))
        significant = {k:rational(v) for k,v in item['significant_expenses'].items()}
        revenue = external+internal
        included = sum(significant.values(),F(0))+other
        rows.append({'name':name,'external_revenue':external,'internal_revenue':internal,
                     'revenue':revenue,'significant_expenses':significant,
                     'other_segment_expenses':other,'included_expenses':included,
                     'profit':revenue-included,'assets':assets})
    if not rows:
        raise ValueError('at least one stipulated segment required')
    n = {k:rational(case[k]) for k in ('internal_expense_included','corporate_operating','share_compensation','interest','tax_expense','corporate_assets','internal_receivables')}
    total = lambda key:sum((r[key] for r in rows),F(0))
    internal = total('internal_revenue')
    if internal!=n['internal_expense_included'] or internal>total('included_expenses'):
        raise ValueError('fully consumed transfers require matching included internal revenue/expense')
    if n['internal_receivables']>total('assets'):
        raise ValueError('internal receivable cannot exceed included segment assets')
    revenue = total('revenue')-internal
    operating = total('profit')-n['corporate_operating']-n['share_compensation']
    expenses = total('included_expenses')-internal+n['corporate_operating']+n['share_compensation']
    pretax = operating-n['interest']
    return {'segments':rows,'segment_revenue_sum':total('revenue'),'segment_profit_sum':total('profit'),
            'internal_revenue_eliminated':internal,'internal_expense_eliminated':internal,
            'external_revenue':revenue,'operating_expenses':expenses,'operating_profit':operating,
            'profit_before_tax':pretax,'net_income':pretax-n['tax_expense'],
            'assets':total('assets')+n['corporate_assets']-n['internal_receivables'],
            'cfo':None,
            'residuals':{'external_revenue':revenue-total('external_revenue'),
                         'operating_profit':revenue-expenses-operating}}


def encode(value):
    if isinstance(value,F):return str(value)
    if isinstance(value,dict):return {k:encode(v) for k,v in value.items()}
    if isinstance(value,list):return [encode(v) for v in value]
    return value


def analyze(data):
    if data['schema']!='v07-c11-original-comparison-v1':
        raise ValueError('unsupported teaching schema')
    return encode({'units':data['units'],'inventory':inventory(data['inventory']),
                   'asset':asset(data['asset']),'segments':segments(data['segments'])})


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input',nargs='?',type=Path,default=Path(__file__).with_name('v07-c11-inputs.json'))
    args=parser.parse_args()
    try:
        report=analyze(json.loads(args.input.read_text()))
    except (ValueError,KeyError,TypeError,OSError) as exc:
        parser.exit(2,f'Invalid teaching case: {exc}\n')
    print(json.dumps(report,indent=2,allow_nan=False))


if __name__=='__main__':
    main()
