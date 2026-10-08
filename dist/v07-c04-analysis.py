"""Original Alder Instruments asset lifecycle; exact, offline, standard library only.

This is a fixed dated teaching case, not a general accounting-rules engine.
Amounts are kCU. Numeric JSON inputs are integers or decimal/fraction strings.
"""
from fractions import Fraction as F
from pathlib import Path
import json
import sys


def amount(value):
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ValueError("use exact integer or string amounts")
    try:
        result = F(value)
    except (ValueError, ZeroDivisionError) as exc:
        raise ValueError("invalid exact amount") from exc
    if result < 0:
        raise ValueError("this case accepts nonnegative inputs")
    return result


def straight_line(carrying, residual, remaining_months, elapsed_months):
    b, r, n, e = map(amount, (carrying, residual, remaining_months, elapsed_months))
    if n <= 0 or n.denominator != 1 or e.denominator != 1 or e > n:
        raise ValueError("whole months required: 0 <= elapsed <= remaining, remaining > 0")
    return max(b - r, F(0)) * e / n


def impairment(carrying, fair_less_costs, value_in_use):
    b, f, v = map(amount, (carrying, fair_less_costs, value_in_use))
    return max(b - max(f, v), F(0))


def reversal(carrying, no_impairment_carrying, recoverable, changed_estimate):
    b, ceiling, ra = map(amount, (carrying, no_impairment_carrying, recoverable))
    if not isinstance(changed_estimate, bool) or ceiling < b:
        raise ValueError("invalid reversal evidence or no-impairment ceiling")
    return max(min(ceiling, ra) - b, F(0)) if changed_estimate else F(0)


def usage(cost, residual, expected_units, actual_units):
    c, r, n = map(amount, (cost, residual, expected_units))
    used = [amount(x) for x in actual_units]
    if n <= 0 or r > c or sum(used) > n:
        raise ValueError("review useful-output estimates before usage exceeds the supplied total")
    return [(c - r) * u / n for u in used]


def exact_json(value):
    if isinstance(value, F):
        return str(value)
    if isinstance(value, dict):
        return {k: exact_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [exact_json(v) for v in value]
    return value


def run(data):
    if data.get("case") != "Alder Instruments fixed 2025-2027 lifecycle":
        raise ValueError("unsupported case/date convention")
    if data.get("units") != "kCU; 1 kCU = 1000 CU":
        raise ValueError("unsupported unit contract")
    a = data["acquisition"]
    cash = amount(data["opening_cash_and_equity"])
    equity = cash
    cost = (amount(a["invoice"]) - amount(a["discount"]) +
            sum(amount(a[k]) for k in ("freight", "installation", "testing")))
    initial_r = amount(a["residual"])
    if cost < initial_r:
        raise ValueError("initial residual exceeds acquisition cost")
    expense = sum(amount(a[k]) for k in ("training", "launch", "general_admin", "maintenance"))
    rows = []
    dep = straight_line(str(cost), str(initial_r), 72, 9)
    ad = dep
    carrying = cost - ad
    cfo = amount(data["operations"]["2025"]["receipts"]) - amount(data["operations"]["2025"]["cash_costs"]) - expense
    ni = cfo - dep
    cash += cfo - cost
    equity += ni
    rows.append(dict(period="2025", gross=cost, accumulated_depreciation=ad,
                     accumulated_impairment=F(0), carrying=carrying, depreciation=dep,
                     impairment_loss=F(0), disposal_gain=F(0), cfo=cfo, cfi=-cost,
                     profit=ni, cash=cash, equity=equity))
    r = amount(data["revision_2026"]["residual"])
    remaining = amount(data["revision_2026"]["remaining_months"])
    if remaining.denominator != 1 or remaining < 18:
        raise ValueError("case requires at least 18 remaining whole months at 1 January 2026")
    dep = straight_line(str(carrying), str(r), str(remaining), 12)
    ad += dep
    pre_impairment = cost - ad
    loss = impairment(str(pre_impairment), data["impairment_2026"]["fair_less_costs"], data["impairment_2026"]["value_in_use"])
    carrying = pre_impairment - loss
    cfo = amount(data["operations"]["2026"]["receipts"]) - amount(data["operations"]["2026"]["cash_costs"])
    ni = cfo - dep - loss
    cash += cfo
    equity += ni
    rows.append(dict(period="2026", gross=cost, accumulated_depreciation=ad,
                     accumulated_impairment=loss, carrying=carrying, depreciation=dep,
                     impairment_loss=loss, disposal_gain=F(0), cfo=cfo, cfi=F(0),
                     profit=ni, cash=cash, equity=equity))
    dep = straight_line(str(carrying), str(r), str(remaining - 12), 6)
    ad += dep
    sold_carrying = cost - ad - loss
    sale = amount(data["sale_2027"]["gross_receipt"])
    fee = amount(data["sale_2027"]["cash_disposal_cost"])
    net = sale - fee
    gain = net - sold_carrying
    cfo = amount(data["operations"]["2027-H1"]["receipts"]) - amount(data["operations"]["2027-H1"]["cash_costs"])
    ni = cfo - dep + gain
    cash += cfo + net
    equity += ni
    rows.append(dict(period="2027-H1", gross=F(0), accumulated_depreciation=F(0),
                     accumulated_impairment=F(0), carrying=F(0), depreciation=dep,
                     impairment_loss=F(0), disposal_gain=gain, cfo=cfo, cfi=net,
                     profit=ni, cash=cash, equity=equity))
    for row in rows:
        if row["cash"] < 0:
            raise ValueError("case has no overdraft: supply sufficient cash funding")
        if row["cash"] + row["carrying"] != row["equity"]:
            raise ArithmeticError("balance-sheet reconciliation failed")
    return exact_json(dict(case=data["case"], units=data["units"], rows=rows,
                           disposal=dict(gross_removed=cost, depreciation_removed=ad,
                                         impairment_removed=loss, carrying_removed=sold_carrying,
                                         gross_cash=sale, cash_cost=fee, net_cash=net, gain=gain),
                           cumulative_profit=sum(x["profit"] for x in rows),
                           cash_change=cash-amount(data["opening_cash_and_equity"])))


def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("v07-c04-inputs.json")
    try:
        result = run(json.loads(path.read_text()))
    except (ValueError, KeyError, TypeError) as exc:
        raise SystemExit(f"Invalid fixed-case input: {exc}") from exc
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
