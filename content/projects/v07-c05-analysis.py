#!/usr/bin/env python3
"""Bounded annual borrower/lessee model. Exact rational kCU, no network or packages."""
from fractions import Fraction as Q
from pathlib import Path
import json
import re
import sys


def require(condition, message):
    if not condition:
        raise ValueError(message)


def fields(obj, names, label):
    require(type(obj) is dict and set(obj) == set(names), label + ": exact fields required")


def number(value, label, maximum=10**7):
    require(type(value) is str and len(value) <= 40 and re.fullmatch(r"(?:0|[1-9][0-9]*)(?:\.[0-9]{1,12}|/[1-9][0-9]*)?", value) is not None,
            label + ": nonnegative decimal or rational string required")
    n = Q(value)
    require(0 <= n <= maximum, label + ": outside bounded domain")
    return n


def encoded(value):
    if isinstance(value, Q): return str(value)
    if isinstance(value, dict): return {k: encoded(v) for k, v in value.items()}
    if isinstance(value, list): return [encoded(v) for v in value]
    return value


def present_value(payments, rate):
    return sum((payment / (1 + rate)**t for t, payment in enumerate(payments, 1)), Q(0))


def liability_schedule(initial, rate, payments):
    """Amounts/rate already validated by caller. Each payment follows annual accrual."""
    balance, rows = initial, []
    for t, payment in enumerate(payments, 1):
        interest = rate * balance
        closing = balance + interest - payment
        require(closing >= 0, "payment over-settles liability at year " + str(t))
        remaining_pv = present_value(payments[t:], rate)
        require(closing == remaining_pv, "schedule does not equal remaining-payment PV")
        rows.append({"year_number": t, "opening": balance, "effective_interest": interest,
            "payment": payment, "liability_reduction": payment - interest, "closing": closing,
            "remaining_payment_pv": remaining_pv})
        balance = closing
    require(balance == 0, "contract does not fully settle at horizon")
    return rows


def build_report(data):
    fields(data, ("schema", "entity", "currency_unit", "start_year", "equity_cash", "owned_asset_cost", "owned_asset_life_years",
        "note", "lease", "cash_revenues", "cash_operating_expenses", "covenant"), "input")
    require(data["schema"] == "v07-c05-financing-1" and data["currency_unit"] == "kCU", "unsupported schema or units")
    require(type(data["entity"]) is str and 1 <= len(data["entity"].strip()) <= 120, "bounded entity name required")
    year = data["start_year"]
    require(type(year) is int and 1900 <= year <= 2100, "start_year must be an integer from 1900 to 2100")
    fields(data["note"], ("gross_proceeds", "direct_issue_fee", "effective_annual_rate", "annual_coupon", "face_at_maturity"), "note")
    fields(data["lease"], ("annual_rate", "commencement_prepayment", "end_year_payments"), "lease")
    fields(data["covenant"], ("test_year_number", "maximum_carrying_debt_to_book_equity"), "covenant")
    require(type(data["lease"]["end_year_payments"]) is list and 1 <= len(data["lease"]["end_year_payments"]) <= 10, "one to ten end-year payments required")
    n = len(data["lease"]["end_year_payments"])
    for name in ("cash_revenues", "cash_operating_expenses"):
        require(type(data[name]) is list and len(data[name]) == n, name + ": one amount per modeled year required")
    life = data["owned_asset_life_years"]
    require(type(life) is int and n <= life <= 100, "owned asset life must cover the model horizon, at most 100 years")
    test_year = data["covenant"]["test_year_number"]
    require(type(test_year) is int and 1 <= test_year <= n, "covenant test year outside horizon")
    equity0, owned = number(data["equity_cash"], "equity"), number(data["owned_asset_cost"], "owned asset")
    note = {key: number(value, key, 1 if key == "effective_annual_rate" else 10**7) for key, value in data["note"].items()}
    lease_rate = number(data["lease"]["annual_rate"], "lease rate", 1)
    prepaid = number(data["lease"]["commencement_prepayment"], "prepayment")
    lease_payments = [number(p, "lease payment") for p in data["lease"]["end_year_payments"]]
    require(any(p > 0 for p in lease_payments), "lease must have a positive future payment")
    cash_revenues = [number(p, "revenue") for p in data["cash_revenues"]]
    cash_expenses = [number(p, "operating expense") for p in data["cash_operating_expenses"]]
    leverage_max = number(data["covenant"]["maximum_carrying_debt_to_book_equity"], "covenant limit", 100)
    initial_note = note["gross_proceeds"] - note["direct_issue_fee"]
    require(initial_note > 0 and note["face_at_maturity"] > 0, "positive net proceeds and face required")
    note_payments = [note["annual_coupon"]] * n
    note_payments[-1] += note["face_at_maturity"]
    require(present_value(note_payments, note["effective_annual_rate"]) == initial_note, "note net proceeds and supplied effective rate do not match contractual payments")
    initial_lease = present_value(lease_payments, lease_rate)
    initial_rou = initial_lease + prepaid
    note_rows = liability_schedule(initial_note, note["effective_annual_rate"], note_payments)
    lease_rows = liability_schedule(initial_lease, lease_rate, lease_payments)
    require(all(row["liability_reduction"] >= 0 for row in lease_rows), "this cash-classification model requires lease payments to cover each year's interest")
    owned_dep, rou_dep = owned / life, initial_rou / n
    balances = {"cash": Q(0), "owned_asset_cost": Q(0), "owned_accumulated_depreciation": Q(0),
        "rou_asset_cost": Q(0), "rou_accumulated_depreciation": Q(0), "note_liability": Q(0),
        "lease_liability": Q(0), "capital": Q(0), "retained_earnings": Q(0),
        "revenue": Q(0), "operating_expense": Q(0), "depreciation_expense": Q(0), "interest_expense": Q(0)}
    journal, cash_path = [], []
    def post(label, changes):
        require(sum(changes.values()) == 0, "unbalanced journal: " + label)
        for a, amount in changes.items(): balances[a] += amount
        require(sum(balances.values()) == 0, "trial balance failed")
        require(balances["cash"] >= 0, label + ": proposed cash path needs additional financing")
        journal.append({"label": label, "debit_changes": changes})
        cash_path.append({"label": label, "cash": balances["cash"]})
    post("commencement-owner", {"cash": equity0, "capital": -equity0})
    post("commencement-note-proceeds", {"cash": note["gross_proceeds"], "note_liability": -note["gross_proceeds"]})
    post("commencement-eligible-note-fee", {"note_liability": note["direct_issue_fee"], "cash": -note["direct_issue_fee"]})
    post("commencement-owned-equipment", {"owned_asset_cost": owned, "cash": -owned})
    post("commencement-lease", {"rou_asset_cost": initial_rou, "lease_liability": -initial_lease, "cash": -prepaid})
    def position():
        cash = balances["cash"]
        net_owned = balances["owned_asset_cost"] + balances["owned_accumulated_depreciation"]
        net_rou = balances["rou_asset_cost"] + balances["rou_accumulated_depreciation"]
        debt = -balances["note_liability"] - balances["lease_liability"]
        equity = -balances["capital"] - balances["retained_earnings"]
        return {"cash": cash, "owned_carrying": net_owned, "rou_carrying": net_rou,
            "note_liability": -balances["note_liability"], "lease_liability": -balances["lease_liability"],
            "assets": cash + net_owned + net_rou, "liabilities": debt, "equity": equity,
            "retained_earnings": -balances["retained_earnings"], "balance_residual": cash + net_owned + net_rou - debt - equity}
    commencement = position()
    commencement["cash_flows"] = {"owner_financing": equity0, "gross_note_financing": note["gross_proceeds"],
        "issue_fee_financing": -note["direct_issue_fee"], "owned_asset_investing": -owned,
        "lease_prepayment_financing": -prepaid, "noncash_lease_addition": initial_lease}
    reports = []
    previous_cash, previous_equity = commencement["cash"], commencement["equity"]
    for index in range(n):
        nr, lr, revenue, op = note_rows[index], lease_rows[index], cash_revenues[index], cash_expenses[index]
        t = index + 1
        label = "year-" + str(t)
        post(label + "-revenue-collected", {"cash": revenue, "revenue": -revenue})
        post(label + "-operating-expense-paid", {"operating_expense": op, "cash": -op})
        post(label + "-owned-depreciation", {"depreciation_expense": owned_dep, "owned_accumulated_depreciation": -owned_dep})
        post(label + "-rou-depreciation", {"depreciation_expense": rou_dep, "rou_accumulated_depreciation": -rou_dep})
        post(label + "-note-interest", {"interest_expense": nr["effective_interest"], "note_liability": -nr["effective_interest"]})
        post(label + "-note-payment", {"note_liability": nr["payment"], "cash": -nr["payment"]})
        post(label + "-lease-interest", {"interest_expense": lr["effective_interest"], "lease_liability": -lr["effective_interest"]})
        post(label + "-lease-payment", {"lease_liability": lr["payment"], "cash": -lr["payment"]})
        profit = revenue - op - owned_dep - rou_dep - nr["effective_interest"] - lr["effective_interest"]
        for a in ("revenue", "operating_expense", "depreciation_expense", "interest_expense"):
            amount = balances[a]
            post(label + "-close-" + a, {a: -amount, "retained_earnings": amount})
        current = position()
        cfo = revenue - op - note["annual_coupon"] - lr["effective_interest"]
        note_face_paid = note["face_at_maturity"] if t == n else Q(0)
        cff = -note_face_paid - lr["liability_reduction"]
        adjustment = nr["effective_interest"] - note["annual_coupon"]
        indirect = profit + owned_dep + rou_dep + adjustment
        require(cfo == indirect and current["cash"] == previous_cash + cfo + cff, "cash-flow bridge failed")
        require(current["equity"] == previous_equity + profit and current["balance_residual"] == 0, "equity or balance bridge failed")
        debt_service = nr["payment"] + lr["payment"]
        coverage = None if debt_service == 0 else (revenue - op) / debt_service
        covenant = None
        if t == test_year:
            # Positive E is an explicit additional contractual requirement; do not divide by nonpositive equity.
            headroom = leverage_max * current["equity"] - current["liabilities"]
            covenant = {"definition": "carrying note plus lease liabilities; positive book equity required",
                "maximum_ratio": leverage_max, "headroom": headroom,
                "ratio": None if current["equity"] <= 0 else current["liabilities"] / current["equity"],
                "compliant": current["equity"] > 0 and headroom >= 0,
                "consequence": "status only; no automatic acceleration, waiver, refinancing or entry is assumed"}
        reports.append({"date": str(year + index) + "-12-31", "income": {"revenue": revenue, "cash_operating_expense": op,
            "owned_depreciation": owned_dep, "rou_depreciation": rou_dep, "note_effective_interest": nr["effective_interest"],
            "lease_interest": lr["effective_interest"], "profit": profit}, "position": current,
            "cash_flow": {"operating": cfo, "indirect_operating": indirect, "investing": Q(0), "financing": cff,
                "change": cfo + cff, "note_cash_interest": note["annual_coupon"], "lease_cash_interest": lr["effective_interest"],
                "note_face_paid": note_face_paid, "lease_principal_paid": lr["liability_reduction"], "note_non_cash_accretion": adjustment},
            "full_calendar_year_cash_flow": {"opening_cash": Q(0) if index == 0 else previous_cash,
                "operating": cfo, "investing": -owned if index == 0 else Q(0),
                "financing": cff + (equity0 + initial_note - prepaid if index == 0 else Q(0)),
                "closing_cash": current["cash"]},
            "contractual_debt_service": debt_service, "cash_surplus_coverage": coverage, "covenant": covenant})
        previous_cash, previous_equity = current["cash"], current["equity"]
    require(balances["note_liability"] == balances["lease_liability"] == 0, "liabilities not fully settled")
    require(sum(row["effective_interest"] for row in note_rows) == sum(note_payments) - initial_note, "note lifetime interest")
    require(sum(row["effective_interest"] for row in lease_rows) == sum(lease_payments) - initial_lease, "lease lifetime interest")
    return encoded({"entity": data["entity"], "currency_unit": "kCU; exact rational model amounts, no hidden currency rounding",
        "cash_flow_scope": "cash_flow shows movements after commencement; full_calendar_year_cash_flow also includes commencement funding/acquisition in the first year, starting from zero before formation",
        "commencement_date": str(year) + "-01-01", "commencement": commencement, "note_schedule": note_rows,
        "lease_schedule": lease_rows, "annual_reports": reports, "journal": journal, "cash_path": cash_path,
        "postclosing_debit_balances": balances,
        "limits": ["Synthetic amortized-cost and lessee conventions, not universal current GAAP/IFRS advice.",
            "Annual receipts precede operating payments and debt service; finer calendar funding is not tested.",
            "Both liabilities end at this fixed horizon; no floating rates, options, tax, FX, impairment or remeasurement.",
            "Cash interest is operating; note face and lease liability reductions plus specified initial financing fees/prepayment are financing.",
            "A covenant breach is reported without assuming any lender waiver or remedy; no undrawn facility is counted as cash."]})


def unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate input field")
        result[key] = value
    return result


def load_inputs(path):
    path = Path(path)
    require(path.stat().st_size <= 100000, "input exceeds bounded file size")
    def no_constant(value): raise ValueError("nonfinite JSON number: " + value)
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique, parse_constant=no_constant)


def main():
    try:
        require(len(sys.argv) <= 2, "usage: v07-c05-analysis.py [inputs.json]")
        path = Path(sys.argv[1]) if len(sys.argv) == 2 else Path(__file__).with_name("v07-c05-inputs.json")
        report = build_report(load_inputs(path))
    except (ValueError, OSError, UnicodeError) as error:
        print(json.dumps({"status": "invalid_input", "error": str(error)}, allow_nan=False))
        return 2
    print(json.dumps(report, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
