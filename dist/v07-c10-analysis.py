"""Original conditional forecast: exact arithmetic, Python standard library only."""
from fractions import Fraction as Q
from pathlib import Path
import json
import sys

UNITS = 'kCU; quantity in thousands; price and unit cost in CU; annual fractions'


def need(condition, message):
    if not condition:
        raise ValueError(message)


def amount(value):
    need(type(value) in (int, str), 'exact integer or rational/decimal string required')
    try:
        result = Q(value)
    except (ValueError, ZeroDivisionError) as exc:
        raise ValueError('invalid exact number') from exc
    need(result >= 0, 'negative input outside the supplied contract')
    return result


def encode(value):
    if isinstance(value, Q):
        return str(value)
    if isinstance(value, dict):
        return {k: encode(v) for k, v in value.items()}
    if isinstance(value, list):
        return [encode(v) for v in value]
    return value


def forecast(data):
    need(data['case'] == 'Lumen Instrument Supply two-year forecast' and data['units'] == UNITS,
         'fixed teaching case and units required')
    need(type(data['years']) is list and len(data['years']) == 2, 'exactly two annual periods required')
    state = {k: amount(v) for k, v in data['opening'].items()}
    p = {k: amount(v) for k, v in data['policy'].items()}
    need(0 <= p['tax_rate'] < 1 and p['interest_rate'] <= 1, 'rate domain')
    need(p['new_asset_life'] >= 2, 'new assets must remain in service through this horizon')
    need(state['cash'] >= p['minimum_cash'] and state['revolver'] <= p['revolver_limit'], 'opening funding policy')
    assets = sum(state[k] for k in ('cash', 'receivables', 'inventory', 'ppe'))
    claims = sum(state[k] for k in ('payables', 'term_debt', 'revolver', 'equity'))
    need(assets == claims, 'opening balance sheet does not reconcile')
    old_remaining = state['ppe']
    prior_capex = Q(0)
    rows = []
    for index, values in enumerate(data['years'], 1):
        y = {k: amount(v) for k, v in values.items()}
        need(all(y[k] <= 1 for k in ('receivables_sales', 'inventory_cogs', 'payables_purchases')), 'target fractions outside [0,1]')
        revenue, cogs = y['quantity'] * y['price'], y['quantity'] * y['unit_cost']
        ar, inventory = y['receivables_sales'] * revenue, y['inventory_cogs'] * cogs
        purchases = cogs + inventory - state['inventory']
        need(purchases >= 0, 'excess opening inventory needs a different purchasing rule')
        ap = y['payables_purchases'] * purchases
        receipts, supplier_cash = revenue + state['receivables'] - ar, purchases + state['payables'] - ap
        need(receipts >= 0 and supplier_cash >= 0, 'collection or supplier refund outside contract')
        old_remaining -= y['old_asset_depreciation']
        need(old_remaining >= 0, 'existing assets cannot be depreciated below zero')
        depreciation = y['old_asset_depreciation'] + prior_capex / p['new_asset_life']
        ebit = revenue - cogs - y['cash_opex'] - depreciation
        # All debt changes occur after this year's interest is paid.
        interest = p['interest_rate'] * (state['term_debt'] + state['revolver'])
        pbt = ebit - interest
        need(pbt >= 0, 'tax-loss benefits require additional rules; no automatic refund assumed')
        tax, ni = p['tax_rate'] * pbt, (1-p['tax_rate']) * pbt
        nwc_change = ar-state['receivables'] + inventory-state['inventory'] - ap+state['payables']
        cfo = receipts - supplier_cash - y['cash_opex'] - interest - tax
        cash_before_financing = state['cash'] + cfo - y['capex'] - y['dividend']
        delta_debt = max(p['minimum_cash']-cash_before_financing, -state['revolver'])
        required_debt = state['revolver'] + delta_debt
        if required_debt > p['revolver_limit']:
            maximum_draw = p['revolver_limit'] - state['revolver']
            return encode(dict(status='funding-shortfall', rows=rows,
                               failure=dict(year=index, net_income=ni, cfo=cfo,
                                            cash_before_financing=cash_before_financing,
                                            required_revolver=required_debt,
                                            available_limit=p['revolver_limit'],
                                            gap_to_minimum=required_debt-p['revolver_limit'],
                                            cash_after_maximum_draw=cash_before_financing+maximum_draw),
                               limitation='No feasible closing balance sheet or subsequent forecast is asserted for the failed period.'))
        closing = dict(cash=cash_before_financing+delta_debt, receivables=ar, inventory=inventory,
                       ppe=state['ppe']+y['capex']-depreciation, payables=ap,
                       term_debt=state['term_debt'], revolver=required_debt,
                       equity=state['equity']+ni-y['dividend'])
        cfi, cff = -y['capex'], delta_debt-y['dividend']
        residuals = dict(balance_sheet=sum(closing[k] for k in ('cash','receivables','inventory','ppe'))
                         - sum(closing[k] for k in ('payables','term_debt','revolver','equity')),
                         direct_indirect_cash=cfo-(ni+depreciation-nwc_change),
                         cash_rollforward=closing['cash']-state['cash']-cfo-cfi-cff)
        need(all(v == 0 for v in residuals.values()), 'forecast reconciliation failed')
        need(closing['cash'] >= p['minimum_cash'] and closing['ppe'] >= 0, 'invalid closing assets')
        rows.append(dict(year=index, opening=state, revenue=revenue, cogs=cogs,
                         purchases=purchases, cash_receipts=receipts, supplier_cash=supplier_cash,
                         cash_opex=y['cash_opex'], depreciation=depreciation, ebit=ebit,
                         interest=interest, tax=tax, net_income=ni, nwc_change=nwc_change,
                         cfo=cfo, cfi=cfi, cff=cff, debt_change=delta_debt,
                         cash_before_financing=cash_before_financing,
                         closing=closing, zero_residuals=residuals))
        state = closing
        prior_capex += y['capex']
    return encode(dict(status='feasible-at-annual-dates', rows=rows,
                       limitation='Conditional annual balances; no probability, intrayear liquidity, real borrowing access or reporting compliance is certified.'))


def average_debt_closure(cash_before_revolver, opening_debt, minimum_cash, rate, tax_rate, limit):
    """Separate example with current tax relief and average-balance interest.

    Inputs are Fractions, including possibly negative cash_before_revolver.
    Sufficient taxable profit and an available stated credit limit are assumptions.
    """
    need(all(isinstance(x, Q) for x in (cash_before_revolver, opening_debt, minimum_cash, rate, tax_rate, limit)), 'Fraction inputs required')
    need(min(opening_debt, minimum_cash, rate, tax_rate, limit) >= 0 and tax_rate < 1, 'closure domain')
    k = (1-tax_rate)*rate/2
    need(k < 1 and opening_debt <= limit, 'finite positive funding effect and valid opening debt required')
    required = max(Q(0), (minimum_cash-cash_before_revolver+(1+k)*opening_debt)/(1-k))
    interest = rate*(opening_debt+required)/2
    cash = cash_before_revolver-(1-tax_rate)*interest+required-opening_debt
    return encode(dict(required_debt=required, interest=interest, cash=cash,
                       feasible=required <= limit,
                       gap_at_limit=max(Q(0), (required-limit)*(1-k))))


if __name__ == '__main__':
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name('v07-c10-inputs.json')
    try:
        result = forecast(json.loads(path.read_text()))
    except (ValueError, KeyError, TypeError) as exc:
        raise SystemExit('Invalid forecast contract: '+str(exc)) from exc
    print(json.dumps(result, indent=2, allow_nan=False))
