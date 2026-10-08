"""Exact original two-period teaching model. No jurisdiction's tax law is inferred."""
from fractions import Fraction as Q
from pathlib import Path
import json
import sys

CONVENTIONS = 'Asset purchased at date0; no residual; all repair claims settle in year2; repair deductions arise only on payment; complete deferred-tax recognition; year2 rate enacted at year1 close; all tax effects in profit; no other transactions.'


def need(condition, message):
    if not condition:
        raise ValueError(message)


def number(value):
    need(type(value) in (int, str), "exact integer or fraction/decimal string required")
    try:
        result = Q(value)
    except (ValueError, ZeroDivisionError) as exc:
        raise ValueError("invalid exact number") from exc
    need(result >= 0, "inputs must be nonnegative")
    return result


def pair(value):
    need(type(value) is list and len(value) == 2, "exactly two periods required")
    return [number(v) for v in value]


def exact(value):
    if isinstance(value, Q):
        return str(value)
    if isinstance(value, list):
        return [exact(v) for v in value]
    if isinstance(value, dict):
        return {k: exact(v) for k, v in value.items()}
    return value


def analyze(data):
    need(data['case'] == 'Northstar Calibration two-period tax and provision case', 'fixed case required')
    need(data['units'] == 'kCU; rates are fractions; periods are fictional years', 'unit mismatch')
    need(data['conventions'] == CONVENTIONS, 'fixed recognition/timing conventions required')
    capital = number(data['opening_equity_cash'])
    cost = number(data['equipment_cost'])
    bookdep = pair(data['book_depreciation'])
    taxdep = pair(data['tax_depreciation'])
    revenue = pair(data['cash_revenue'])
    operating = pair(data['ordinary_cash_expense'])
    fines = pair(data['permanently_nondeductible_cash_fine'])
    rates = pair(data['current_tax_rates'])
    estimate = number(data['year1_repair_estimate'])
    settlement = number(data['year2_repair_settlement'])
    first_paid = number(data['year1_tax_cash_paid'])
    need(cost > 0 and sum(bookdep) == sum(taxdep) == cost, 'both schedules must fully allocate positive cost')
    need(taxdep[0] >= bookdep[0], 'this example requires accelerated or equal first-year tax deduction')
    need(all(r <= 1 for r in rates), 'rates must lie in [0,1]')
    need(capital >= cost, 'date0 purchase requires available equity cash')
    # Supplied future taxable resources are adequate for the estimated and realized
    # deduction. This is a model assumption, not an evidence-based recognition test.
    future_before_repair = revenue[1] - operating[1] - taxdep[1]
    need(future_before_repair >= max(estimate, settlement), 'full deferred-tax recognition needs supported future deduction capacity')
    cash, equity, carrying, taxbase = capital - cost, capital, cost, cost
    provision = dta = dtl = current_payable = Q(0)
    rows = []
    for t in range(2):
        before = dict(cash=cash, equity=equity, provision=provision,
                      dta=dta, dtl=dtl, current_payable=current_payable)
        repair_cash = Q(0) if t == 0 else settlement
        repair_expense = estimate if t == 0 else settlement - estimate
        provision += repair_expense - repair_cash
        carrying -= bookdep[t]
        taxbase -= taxdep[t]
        profit_before_tax = revenue[t] - operating[t] - fines[t] - bookdep[t] - repair_expense
        taxable_profit = revenue[t] - operating[t] - taxdep[t] - repair_cash
        need(taxable_profit >= 0, 'tax-loss rules are outside this fixed case')
        current_tax = rates[t] * taxable_profit
        # The year2 rate is already enacted at the year1 reporting date.
        dtl = rates[1] * (carrying - taxbase)
        dta = rates[1] * provision
        deferred_tax_expense = (dtl - before['dtl']) - (dta - before['dta'])
        tax_expense = current_tax + deferred_tax_expense
        net_income = profit_before_tax - tax_expense
        tax_cash = first_paid if t == 0 else before['current_payable'] + current_tax
        need(tax_cash <= before['current_payable'] + current_tax, 'tax prepayments are outside this fixed case')
        current_payable += current_tax - tax_cash
        cfo = revenue[t] - operating[t] - fines[t] - repair_cash - tax_cash
        indirect_cfo = (net_income + bookdep[t] + repair_expense - repair_cash
                        + deferred_tax_expense + current_payable - before['current_payable'])
        cash += cfo
        equity += net_income
        assets = cash + carrying + dta
        liabilities = provision + current_payable + dtl
        need(cash >= 0, 'negative period-end cash requires an explicit financing extension')
        residuals = {
            'balance_sheet': assets - liabilities - equity,
            'cash_bridge': cfo - indirect_cfo,
            'taxable_profit_bridge': taxable_profit - (profit_before_tax + fines[t] + bookdep[t] - taxdep[t] + repair_expense - repair_cash),
            'tax_payable': current_payable - before['current_payable'] - current_tax + tax_cash,
            'provision': provision - before['provision'] - repair_expense + repair_cash,
        }
        need(all(v == 0 for v in residuals.values()), 'accounting reconciliation failed')
        rows.append(dict(year=t+1, revenue=revenue[t], ordinary_expense=operating[t], fine=fines[t],
                         book_depreciation=bookdep[t], tax_depreciation=taxdep[t],
                         repair_expense=repair_expense, repair_cash=repair_cash, provision=provision,
                         profit_before_tax=profit_before_tax, taxable_profit=taxable_profit,
                         current_tax=current_tax, tax_cash=tax_cash, current_tax_payable=current_payable,
                         asset_carrying=carrying, asset_tax_base=taxbase, repair_liability_tax_base=Q(0),
                         deferred_tax_asset=dta, deferred_tax_liability=dtl,
                         deferred_tax_expense=deferred_tax_expense, total_tax_expense=tax_expense,
                         net_income=net_income, cfo=cfo, indirect_cfo=indirect_cfo,
                         cash=cash, assets=assets, liabilities=liabilities, equity=equity,
                         zero_residuals=residuals))
    totals = {key: sum(row[key] for row in rows) for key in
              ('profit_before_tax', 'current_tax', 'tax_cash', 'deferred_tax_expense', 'total_tax_expense', 'net_income', 'cfo')}
    need(totals['net_income'] == cash - capital == totals['cfo'] - cost, 'terminal wealth reconciliation')
    need(totals['deferred_tax_expense'] == 0 and current_payable == provision == dta == dtl == 0, 'terminal claims must settle')
    return exact(dict(case=data['case'], units=data['units'],
                      date0=dict(equity_financing=capital, equipment_investing=-cost, cash=capital-cost),
                      rows=rows, totals=totals,
                      limitations=['Synthetic tax law and supplied recoverability; not a tax-return calculator.',
                                   'Checks period-end cash only; intra-year receipt/payment dates are not supplied.',
                                   'Gross deferred assets/liabilities shown; real offset eligibility is not assessed.']))


def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name('v07-c07-inputs.json')
    try:
        result = analyze(json.loads(path.read_text()))
    except (KeyError, TypeError, ValueError) as exc:
        raise SystemExit('Invalid teaching input: ' + str(exc)) from exc
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
