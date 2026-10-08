#!/usr/bin/env python3
"""Harbor three-statement laboratory; stdlib, exact CU minor units internally."""
from __future__ import annotations

import argparse
from datetime import date, timedelta
import json
from pathlib import Path
import re
import sys

SCALE = 100_000  # CU minor units per kCU; one CU contains 100 minor units.
ASSETS = ("cash", "receivables", "inventory", "prepaid_insurance", "equipment")
LIABILITIES = ("trade_payables", "wages_payable", "interest_payable", "customer_advances", "borrowings")
EQUITY = ("share_capital", "retained_earnings")
PERMANENT = ASSETS + ("accumulated_depreciation",) + LIABILITIES + EQUITY
EXPENSES = ("cost_of_goods_sold", "wage_expense", "insurance_expense", "rent_expense", "interest_expense", "depreciation_expense")
INCOME = ("revenue", "disposal_gain") + EXPENSES
CHART = PERMANENT + INCOME + ("dividends",)
CREDIT_NORMAL = {"accumulated_depreciation", *LIABILITIES, *EQUITY, "revenue", "disposal_gain"}
CF_LINES = {
    "customer_receipts": ("operating", 1), "supplier_payments": ("operating", -1),
    "wage_payments": ("operating", -1), "insurance_payments": ("operating", -1),
    "rent_payments": ("operating", -1), "interest_payments": ("operating", -1),
    "equipment_sale": ("investing", 1), "equipment_purchase": ("investing", -1),
    "share_issue": ("financing", 1), "borrowing": ("financing", 1),
    "principal_repayment": ("financing", -1), "dividends": ("financing", -1),
}
DECIMAL = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]{1,5})?\Z")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def fields(value, keys, label):
    require(type(value) is dict and set(value) == set(keys), f"{label}: incorrect fields")


def amount(value):
    """Parse an exact decimal string in kCU; reject floats, bools and nonfinite data."""
    require(type(value) is str and len(value) <= 24 and DECIMAL.fullmatch(value) is not None,
            "amount must be a decimal string with at most five places")
    negative = value.startswith("-")
    whole, _, fraction = value.lstrip("-").partition(".")
    result = int(whole) * SCALE + int(fraction.ljust(5, "0") or "0")
    require(result <= 1_000_000 * SCALE, "amount exceeds laboratory limit of 1,000,000 kCU")
    return -result if negative else result


def display(value):
    sign = "-" if value < 0 else ""
    whole, minor = divmod(abs(value), SCALE)
    return sign + str(whole) + (("." + f"{minor:05d}".rstrip("0")) if minor else "")


def money_map(values):
    return {key: display(value) for key, value in values.items()}


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, f"duplicate JSON field: {key}")
        result[key] = value
    return result


def load_inputs(path):
    raw = Path(path).read_bytes()
    require(len(raw) <= 200_000, "input exceeds 200,000-byte limit")
    return json.loads(raw.decode("utf-8"), object_pairs_hook=unique_object,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError("nonfinite JSON constant")))


def normal(ledger, account):
    return -ledger[account] if account in CREDIT_NORMAL else ledger[account]


def nwc(ledger):
    return sum(normal(ledger, a) for a in ("receivables", "inventory", "prepaid_insurance")) - sum(
        normal(ledger, a) for a in ("trade_payables", "wages_payable", "interest_payable", "customer_advances"))


def build_report(data):
    """Post the supplied adjusted journal; reject failures of this bounded case contract."""
    fields(data, ("schema", "entity", "unit", "opening_date", "period_start", "period_end",
                  "opening_debit_balances_kcu", "current_borrowings_kcu", "events"), "input")
    require(data["schema"] == "v07-c02-1" and data["unit"] == "kCU", "unsupported schema or unit")
    require(type(data["entity"]) is str and 0 < len(data["entity"]) <= 100, "entity must be nonempty text")
    dates = []
    for key in ("opening_date", "period_start", "period_end"):
        require(type(data[key]) is str, f"{key}: expected ISO date")
        parsed = date.fromisoformat(data[key])
        require(parsed.isoformat() == data[key], f"{key}: expected YYYY-MM-DD")
        dates.append(parsed)
    require(dates[1] == dates[0] + timedelta(days=1) and dates[2] >= dates[1], "inconsistent reporting dates")
    fields(data["opening_debit_balances_kcu"], PERMANENT, "opening balances")
    opening = {a: amount(data["opening_debit_balances_kcu"][a]) if a in PERMANENT else 0 for a in CHART}
    require(sum(opening.values()) == 0, "opening trial balance does not balance")
    for a in PERMANENT:
        if a != "retained_earnings":
            require(normal(opening, a) >= 0, f"opening {a}: wrong normal balance")
    require(-opening["accumulated_depreciation"] <= opening["equipment"], "opening depreciation exceeds cost")
    events = data["events"]
    require(type(events) is list and 1 <= len(events) <= 200, "events must be a list of 1 to 200 entries")
    ledger = dict(opening)
    lines = dict.fromkeys(CF_LINES, 0)
    cash_path = [{"event": "opening", "cash_kcu": display(ledger["cash"])}]
    seen = set()
    debit_equipment = credit_equipment = credit_accumulated = debit_accumulated = noncash_note = 0
    for event in events:
        fields(event, ("id", "description", "cash_line", "postings"), "event")
        event_id = event["id"]
        require(type(event_id) is str and 0 < len(event_id) <= 40 and event_id not in seen, "invalid/duplicate event id")
        seen.add(event_id)
        require(type(event["description"]) is str and 0 < len(event["description"]) <= 300, "invalid event description")
        postings = event["postings"]
        require(type(postings) is list and 2 <= len(postings) <= 20, "event needs 2 to 20 postings")
        change = dict.fromkeys(CHART, 0)
        posted_accounts = set()
        for posting in postings:
            fields(posting, ("account", "side", "amount_kcu"), "posting")
            a, side = posting["account"], posting["side"]
            require(type(a) is str and a in CHART and a not in posted_accounts, "unknown/duplicate account in event")
            require(side in ("Dr", "Cr"), "posting side must be Dr or Cr")
            posted_accounts.add(a)
            n = amount(posting["amount_kcu"])
            require(n > 0, "posting amount must be positive")
            change[a] = n if side == "Dr" else -n
        require(sum(change.values()) == 0, f"{event_id}: journal does not balance")
        # The limited chart allows owner capital changes and dividends only for cash.
        require(change["share_capital"] == 0 or
                (posted_accounts == {"cash", "share_capital"} and change["cash"] > 0),
                "share issue must be for cash in this laboratory")
        require(change["retained_earnings"] == 0, "direct retained-earnings adjustment is outside this laboratory")
        require(change["dividends"] == 0 or
                (posted_accounts == {"cash", "dividends"} and change["dividends"] > 0),
                "dividend must be declared and paid together")
        cf_line = event["cash_line"]
        cash = change["cash"]
        if cash:
            require(type(cf_line) is str and cf_line in CF_LINES, f"{event_id}: missing cash classification")
            require(cash * CF_LINES[cf_line][1] > 0, f"{event_id}: cash-line direction is wrong")
            lines[cf_line] += cash
        else:
            require(cf_line is None, f"{event_id}: noncash event cannot have a cash-flow line")
        if change["equipment"] > 0 and not cash:
            require(posted_accounts == {"equipment", "borrowings"}, "only seller-note noncash equipment addition is supported")
            noncash_note += change["equipment"]
        debit_equipment += max(change["equipment"], 0)
        credit_equipment += max(-change["equipment"], 0)
        credit_accumulated += max(-change["accumulated_depreciation"], 0)
        debit_accumulated += max(change["accumulated_depreciation"], 0)
        for a in CHART:
            ledger[a] += change[a]
        require(ledger["cash"] >= 0, f"{event_id}: unfinanced negative cash path")
        cash_path.append({"event": event_id, "cash_kcu": display(ledger["cash"])})
    for a in CHART:
        if a not in ("retained_earnings", "disposal_gain"):
            require(normal(ledger, a) >= 0, f"closing {a}: wrong normal balance")
    require(-ledger["accumulated_depreciation"] <= ledger["equipment"], "closing depreciation exceeds cost")
    income = {a: normal(ledger, a) for a in INCOME}
    profit = -sum(ledger[a] for a in INCOME)
    dividends = ledger["dividends"]
    closed = dict(ledger)
    closing_entries = []
    for a in INCOME + ("dividends",):
        if closed[a]:
            value = closed[a]
            closing_entries.append({"temporary_account": a,
                                    "temporary_debit_change_kcu": display(-value),
                                    "retained_earnings_debit_change_kcu": display(value)})
            closed["retained_earnings"] += value
            closed[a] = 0
    current_debt = amount(data["current_borrowings_kcu"])
    debt = normal(closed, "borrowings")
    require(0 <= current_debt <= debt, "current borrowings outside total debt")
    asset_total = sum(closed[a] for a in ASSETS) + closed["accumulated_depreciation"]
    liability_total = sum(normal(closed, a) for a in LIABILITIES)
    equity_total = sum(normal(closed, a) for a in EQUITY)
    cfo = sum(lines[k] for k, (activity, _) in CF_LINES.items() if activity == "operating")
    cfi = sum(lines[k] for k, (activity, _) in CF_LINES.items() if activity == "investing")
    cff = sum(lines[k] for k, (activity, _) in CF_LINES.items() if activity == "financing")
    bridge = {"profit": profit, "depreciation_addback": income["depreciation_expense"],
              "disposal_gain_removal": -income["disposal_gain"]}
    for a in ("receivables", "inventory", "prepaid_insurance"):
        bridge["minus_change_" + a] = -(normal(closed, a) - normal(opening, a))
    for a in ("trade_payables", "wages_payable", "interest_payable", "customer_advances"):
        bridge["plus_change_" + a] = normal(closed, a) - normal(opening, a)
    indirect = sum(bridge.values())
    opening_equity = sum(normal(opening, a) for a in EQUITY)
    assets_open = sum(opening[a] for a in ASSETS) + opening["accumulated_depreciation"]
    gross_additions_expected = -lines["equipment_purchase"] + noncash_note
    debt_expected = normal(opening, "borrowings") + lines["borrowing"] + noncash_note + lines["principal_repayment"]
    residuals = {
        "adjusted_trial_balance": sum(ledger.values()), "postclosing_trial_balance": sum(closed.values()),
        "accounting_equation": asset_total - liability_total - equity_total,
        "direct_minus_indirect_cfo": cfo - indirect,
        "cash_bridge": closed["cash"] - opening["cash"] - cfo - cfi - cff,
        "equity_bridge": equity_total - opening_equity - lines["share_issue"] - profit + dividends,
        "dividend_cash": dividends + lines["dividends"],
        "debt_rollforward": debt - debt_expected,
        "equipment_additions": debit_equipment - gross_additions_expected,
        "depreciation_schedule": credit_accumulated - income["depreciation_expense"],
        "disposal_proceeds": lines["equipment_sale"] - (credit_equipment - debit_accumulated) - income["disposal_gain"],
    }
    delta = {a: normal(closed, a) - normal(opening, a) for a in PERMANENT}
    expected_operating_lines = {
        "customer_receipts": income["revenue"] - delta["receivables"] + delta["customer_advances"],
        "supplier_payments": -(income["cost_of_goods_sold"] + delta["inventory"] - delta["trade_payables"]),
        "wage_payments": -(income["wage_expense"] - delta["wages_payable"]),
        "insurance_payments": -(income["insurance_expense"] + delta["prepaid_insurance"]),
        "rent_payments": -income["rent_expense"],
        "interest_payments": -(income["interest_expense"] - delta["interest_payable"]),
    }
    residuals.update({"direct_line_" + key: lines[key] - value for key, value in expected_operating_lines.items()})
    for name, residual in residuals.items():
        require(residual == 0, f"{name}: reconciliation failed")
    return {
        "status": "passed", "schema": "v07-c02-report-1", "entity": data["entity"], "unit": "kCU",
        "period": {k: data[k] for k in ("opening_date", "period_start", "period_end")},
        "classification": "Cash interest operating; cash dividends financing; noncash seller note excluded from cash flows.",
        "opening_debit_balances_kcu": money_map(opening), "adjusted_trial_balance_kcu": money_map(ledger),
        "postclosing_trial_balance_kcu": money_map(closed), "closing_entries": closing_entries,
        "income_statement_kcu": money_map({**income, "gross_profit": income["revenue"] - income["cost_of_goods_sold"],
            "trading_result_before_disposal_and_interest": profit - income["disposal_gain"] + income["interest_expense"],
            "tax_expense_stipulated_zero": 0, "profit": profit}),
        "balance_sheet_kcu": money_map({**{a: normal(closed, a) for a in PERMANENT},
            "net_equipment": closed["equipment"] + closed["accumulated_depreciation"],
            "current_assets": sum(closed[a] for a in ASSETS if a != "equipment"),
            "current_borrowings": current_debt, "noncurrent_borrowings": debt - current_debt,
            "current_liabilities": liability_total - debt + current_debt,
            "assets": asset_total, "liabilities": liability_total, "equity": equity_total}),
        "equity_bridge_kcu": money_map({"opening_equity": opening_equity, "cash_share_contribution": lines["share_issue"],
            "profit": profit, "dividends": dividends, "closing_equity": equity_total}),
        "cash_flow_kcu": {"direct_lines": money_map(lines), "indirect_adjustments": money_map(bridge),
            **money_map({"operating": cfo, "indirect_operating": indirect, "investing": cfi, "financing": cff,
                "change": cfo + cfi + cff, "opening_cash": opening["cash"], "closing_cash": closed["cash"]})},
        "rollforwards_kcu": money_map({"opening_assets": assets_open, "opening_operating_nwc": nwc(opening),
            "closing_operating_nwc": nwc(closed), "change_operating_nwc": nwc(closed) - nwc(opening),
            "opening_gross_equipment": opening["equipment"], "equipment_additions": debit_equipment,
            "equipment_cost_disposed": credit_equipment, "depreciation_added": credit_accumulated,
            "accumulated_depreciation_removed": debit_accumulated,
            "disposed_carrying_amount": credit_equipment - debit_accumulated, "opening_borrowings": normal(opening, "borrowings"),
            "cash_borrowing": lines["borrowing"], "cash_principal_repaid": -lines["principal_repayment"],
            "closing_borrowings": debt}),
        "noncash_disclosure_kcu": {"equipment_acquired_for_seller_note": display(noncash_note)},
        "cash_path": cash_path, "zero_residuals_kcu": money_map(residuals),
        "limitations": ["Balanced journals and statement bridges do not establish documentary recognition or completeness.",
                        "Fixed chart, ordinary balances and supplied maturity schedule; no tax, FX, OCI, impairment or overdraft.",
                        "Ordered postings are the supplied model's payment order, not evidence of actual dated bank movements."]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", nargs="?", type=Path,
                        default=Path(__file__).resolve().with_name("v07-c02-inputs.json"))
    args = parser.parse_args(argv)
    try:
        result = build_report(load_inputs(args.input))
    except (ValueError, OSError, UnicodeError, OverflowError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, allow_nan=False))
        return 2
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
