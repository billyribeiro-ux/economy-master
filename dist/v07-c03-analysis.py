#!/usr/bin/env python3
"""Exact synthetic operating ledger; standard library, offline, no imports with output."""
from datetime import date
from fractions import Fraction
from pathlib import Path
import json
import re
import sys

SCALE = 100000
LIMIT = 10**12  # minor units per input amount: at most 10 million kCU
OPEN = ("cash", "gross_receivables", "allowance", "inventory", "payables", "advances", "capital", "retained_earnings")
FLOWS = ("cash_sales", "credit_sales", "ordinary_collections", "advances_received", "advances_earned",
         "cash_purchases", "credit_purchases", "cost_of_sales", "payables_paid", "other_expense_paid", "writeoffs", "recoveries")
TEMP = ("revenue", "cost_of_sales", "other_expense", "credit_loss_expense")
CREDIT_NORMAL = {"allowance", "payables", "advances", "capital", "retained_earnings", "revenue"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def keys(obj, expected, label):
    require(type(obj) is dict and set(obj) == set(expected), label + ": exact object fields required")


def money(value, label, signed=False):
    require(type(value) is str and len(value) <= 24 and
            re.fullmatch(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]{1,5})?", value) is not None,
            label + ": use an exact decimal string with at most five fractional kCU digits")
    amount = Fraction(value) * SCALE
    require(amount.denominator == 1 and abs(amount) <= LIMIT, label + ": amount outside bounded minor-unit domain")
    require(signed or amount >= 0, label + ": nonnegative amount required")
    return int(amount)


def rate(value):
    require(type(value) is str and len(value) <= 32 and re.fullmatch(r"(?:0|[1-9][0-9]*)(?:\.[0-9]{1,12}|/[1-9][0-9]*)?", value) is not None,
            "loss_fraction: bounded nonnegative decimal or rational string required")
    result = Fraction(value)
    require(0 <= result <= 1, "loss_fraction must be between zero and one")
    return result


def money_text(amount):
    require(type(amount) is int, "internal monetary amount must be integer")
    whole, fraction = divmod(abs(amount), SCALE)
    suffix = ("." + str(fraction).zfill(5).rstrip("0")) if fraction else ""
    return ("-" if amount < 0 else "") + str(whole) + suffix


def monetary_dict(values):
    return {key: money_text(value) for key, value in values.items()}


def parse_date(value, label):
    require(type(value) is str and re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value) is not None, label + ": ISO date required")
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise ValueError(label + ": invalid date") from error


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate JSON field: " + key)
        result[key] = value
    return result


def load_inputs(path):
    path = Path(path)
    require(path.stat().st_size <= 200000, "input file exceeds 200000 bytes")
    def invalid_constant(value):
        raise ValueError("nonfinite JSON number: " + value)
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_object, parse_constant=invalid_constant)


def build_report(data):
    keys(data, ("schema", "entity", "unit", "start", "end", "days", "opening_kcu", "flows_kcu", "aging", "alternative_calendar"), "input")
    require(data["schema"] == "v07-c03-operating-ledger-1", "unsupported schema")
    require(type(data["entity"]) is str and 1 <= len(data["entity"].strip()) <= 120, "bounded entity name required")
    require(data["unit"] == "kCU; 1 CU = 100 minor units", "unsupported units")
    start, end = parse_date(data["start"], "start"), parse_date(data["end"], "end")
    days = data["days"]
    require(type(days) is int and 1 <= days <= 366 and (end - start).days + 1 == days, "days must match inclusive bounded interval")
    keys(data["opening_kcu"], OPEN, "opening")
    keys(data["flows_kcu"], FLOWS, "flows")
    opening = {a: money(data["opening_kcu"][a], a, a == "retained_earnings") for a in OPEN}
    f = {a: money(data["flows_kcu"][a], a) for a in FLOWS}
    require(opening["allowance"] <= opening["gross_receivables"], "opening allowance exceeds gross claims")
    balances = {a: (-n if a in CREDIT_NORMAL else n) for a, n in opening.items()}
    balances.update({a: 0 for a in TEMP})
    require(sum(balances.values()) == 0, "opening accounting equation does not balance")
    require(f["recoveries"] <= f["writeoffs"], "this bounded model recovers only claims written off in this period")
    journal, cash_path = [], [{"event": "opening", "cash_kcu": money_text(balances["cash"])}]

    def post(identifier, changes):
        require(sum(changes.values()) == 0, "unbalanced generated entry: " + identifier)
        for account, change in changes.items():
            balances[account] += change
        # Intermediate allowance may be debit before the documented final adjustment.
        for account in ("cash", "gross_receivables", "inventory"):
            require(balances[account] >= 0, identifier + ": unfunded cash or unavailable asset: " + account)
        for account in ("payables", "advances"):
            require(balances[account] <= 0, identifier + ": payment/performance exceeds recorded liability: " + account)
        require(sum(balances.values()) == 0, "generated trial balance mismatch")
        journal.append({"id": identifier, "debit_changes_kcu": monetary_dict(changes)})
        cash_path.append({"event": identifier, "cash_kcu": money_text(balances["cash"])})

    post("cash-sales", {"cash": f["cash_sales"], "revenue": -f["cash_sales"]})
    post("credit-sales", {"gross_receivables": f["credit_sales"], "revenue": -f["credit_sales"]})
    post("ordinary-collections", {"cash": f["ordinary_collections"], "gross_receivables": -f["ordinary_collections"]})
    post("new-advances", {"cash": f["advances_received"], "advances": -f["advances_received"]})
    post("earn-advances", {"advances": f["advances_earned"], "revenue": -f["advances_earned"]})
    purchases = f["cash_purchases"] + f["credit_purchases"]
    post("inventory-purchases", {"inventory": purchases, "cash": -f["cash_purchases"], "payables": -f["credit_purchases"]})
    post("cost-of-sales", {"cost_of_sales": f["cost_of_sales"], "inventory": -f["cost_of_sales"]})
    post("supplier-settlement", {"payables": f["payables_paid"], "cash": -f["payables_paid"]})
    post("other-expense-paid", {"other_expense": f["other_expense_paid"], "cash": -f["other_expense_paid"]})
    post("writeoff", {"allowance": f["writeoffs"], "gross_receivables": -f["writeoffs"]})
    post("reinstate-recovery", {"gross_receivables": f["recoveries"], "allowance": -f["recoveries"]})
    post("collect-recovery", {"cash": f["recoveries"], "gross_receivables": -f["recoveries"]})

    aging = data["aging"]
    require(type(aging) is list and 1 <= len(aging) <= 100, "aging requires 1 to 100 supplied groups")
    aging_report, aging_total, target = [], 0, 0
    labels = set()
    for row in aging:
        keys(row, ("label", "gross_kcu", "loss_fraction"), "aging group")
        label = row["label"]
        require(type(label) is str and 1 <= len(label.strip()) <= 120 and label not in labels, "unique bounded aging label required")
        labels.add(label)
        amount, fraction = money(row["gross_kcu"], "aging gross"), rate(row["loss_fraction"])
        loss = amount * fraction
        require(loss.denominator == 1, "each aging loss must be an exact minor-unit amount; no hidden rounding")
        aging_total += amount
        target += int(loss)
        aging_report.append({"label": label, "gross_kcu": money_text(amount), "loss_fraction": str(fraction), "target_kcu": money_text(int(loss))})
    require(aging_total == balances["gross_receivables"], "aging groups must cover every closing gross claim exactly")
    pre_allowance = -balances["allowance"]
    expense = target - pre_allowance
    post("allowance-adjustment", {"credit_loss_expense": expense, "allowance": -expense})
    adjusted = dict(balances)
    revenue = -balances["revenue"]
    profit = -sum(balances[a] for a in TEMP)
    closing_entries = []
    for account in TEMP:
        n = balances[account]
        balances[account] = 0
        balances["retained_earnings"] += n
        closing_entries.append({"account": account, "temporary_debit_change_kcu": money_text(-n), "retained_earnings_debit_change_kcu": money_text(n)})
    closing = {a: (-balances[a] if a in CREDIT_NORMAL else balances[a]) for a in OPEN}
    closing["net_receivables"] = closing["gross_receivables"] - closing["allowance"]
    closing["assets"] = closing["cash"] + closing["net_receivables"] + closing["inventory"]
    closing["liabilities"] = closing["payables"] + closing["advances"]
    closing["equity"] = closing["capital"] + closing["retained_earnings"]
    receipts = f["cash_sales"] + f["ordinary_collections"] + f["advances_received"] + f["recoveries"]
    suppliers = f["cash_purchases"] + f["payables_paid"]
    cfo = receipts - suppliers - f["other_expense_paid"]
    def nwc(stock, net):
        return stock["gross_receivables"] - (stock["allowance"] if net else 0) + stock["inventory"] - stock["payables"] - stock["advances"]
    gross0, gross1 = nwc(opening, False), nwc(closing, False)
    net0, net1 = nwc(opening, True), nwc(closing, True)
    delta = {a: closing[a] - opening[a] for a in OPEN}
    gross_bridge = profit + expense - (gross1 - gross0) - f["writeoffs"] + f["recoveries"]
    net_bridge = profit - (net1 - net0)
    residuals = {
        "adjusted_trial_balance": sum(adjusted.values()), "closed_trial_balance": sum(balances.values()),
        "balance_sheet": closing["assets"] - closing["liabilities"] - closing["equity"],
        "cash": closing["cash"] - opening["cash"] - cfo,
        "retained_earnings": closing["retained_earnings"] - opening["retained_earnings"] - profit,
        "gross_receivables": delta["gross_receivables"] - f["credit_sales"] + f["ordinary_collections"] + f["writeoffs"],
        "allowance": delta["allowance"] - expense + f["writeoffs"] - f["recoveries"],
        "inventory": delta["inventory"] - purchases + f["cost_of_sales"],
        "payables": delta["payables"] - f["credit_purchases"] + f["payables_paid"],
        "advances": delta["advances"] - f["advances_received"] + f["advances_earned"],
        "customer_cash": receipts - (revenue - delta["gross_receivables"] + delta["advances"] - f["writeoffs"] + f["recoveries"]),
        "supplier_cash": suppliers - (f["cost_of_sales"] + delta["inventory"] - delta["payables"]),
        "gross_cfo_bridge": cfo - gross_bridge, "net_cfo_bridge": cfo - net_bridge,
    }
    require(all(n == 0 for n in residuals.values()), "operating reconciliation failed")

    def day_ratio(open_amount, close_amount, flow):
        return None if flow == 0 else Fraction(days * (open_amount + close_amount), 2 * flow)
    dso = day_ratio(opening["gross_receivables"], closing["gross_receivables"], f["credit_sales"])
    dio = day_ratio(opening["inventory"], closing["inventory"], f["cost_of_sales"])
    dpo = day_ratio(opening["payables"], closing["payables"], f["credit_purchases"])
    dpo_total = day_ratio(opening["payables"], closing["payables"], purchases)
    dpo_cogs = day_ratio(opening["payables"], closing["payables"], f["cost_of_sales"])
    def cycle(payable_days):
        return None if any(x is None for x in (dso, dio, payable_days)) else dso + dio - payable_days
    ratios = {"dso_gross_credit": dso, "dio": dio, "dpo_credit_purchases": dpo,
              "ccc_credit_purchases": cycle(dpo), "dpo_total_purchases": dpo_total,
              "ccc_total_purchases": cycle(dpo_total), "dpo_cost_of_sales": dpo_cogs,
              "ccc_cost_of_sales": cycle(dpo_cogs),
              "dso_total_revenue": day_ratio(opening["gross_receivables"], closing["gross_receivables"], revenue),
              "dso_net_credit": day_ratio(opening["gross_receivables"] - opening["allowance"], closing["net_receivables"], f["credit_sales"])}

    calendar = data["alternative_calendar"]
    require(type(calendar) is list and 1 <= len(calendar) <= days, "bounded nonempty alternative calendar required")
    raw, funded, debt, low = opening["cash"], opening["cash"], 0, opening["cash"]
    totals = [0, 0, 0]
    previous_date = None
    calendar_report = []
    for row in calendar:
        keys(row, ("date", "receipts_kcu", "suppliers_kcu", "other_kcu"), "calendar row")
        when = parse_date(row["date"], "calendar date")
        require(start <= when <= end and (previous_date is None or when > previous_date), "calendar dates must be distinct, increasing and in period")
        previous_date = when
        r, s, o = [money(row[key], key) for key in ("receipts_kcu", "suppliers_kcu", "other_kcu")]
        for index, amount in enumerate((r, s, o)): totals[index] += amount
        draw = 0
        # Receipts first, then suppliers, then other payments within each bucket.
        for change in (r, -s, -o):
            raw += change
            low = min(low, raw)
            if funded + change < 0:
                new_draw = -(funded + change)
                draw += new_draw
                debt += new_draw
                funded += new_draw
            funded += change
        calendar_report.append({"date": row["date"], "unfinanced_cash_kcu": money_text(raw),
                                "conditional_draw_kcu": money_text(draw), "conditional_cash_kcu": money_text(funded),
                                "conditional_debt_kcu": money_text(debt)})
    require(totals == [receipts, suppliers, f["other_expense_paid"]], "calendar cash totals must match ledger operating cash")
    require(raw == closing["cash"] and funded >= debt and debt == max(0, -low), "calendar funding reconciliation failed")
    repay = debt
    return {
        "entity": data["entity"], "period": {"start": data["start"], "end": data["end"], "days": days},
        "unit": data["unit"], "journal": journal, "cash_path": cash_path,
        "adjusted_debit_balances_kcu": monetary_dict(adjusted), "closing_entries": closing_entries,
        "postclosing_debit_balances_kcu": monetary_dict(balances), "aging": aging_report,
        "income_kcu": monetary_dict({"revenue": revenue, "cost_of_sales": f["cost_of_sales"],
            "other_expense": f["other_expense_paid"], "credit_loss_expense": expense, "profit": profit}),
        "balance_sheet_kcu": monetary_dict(closing),
        "cash_flow_kcu": monetary_dict({"customer_receipts": receipts, "supplier_payments": suppliers,
            "other_payments": f["other_expense_paid"], "operating": cfo, "gross_indirect": gross_bridge,
            "net_indirect": net_bridge, "investing": 0, "financing": 0}),
        "working_capital_kcu": monetary_dict({"gross_opening": gross0, "gross_closing": gross1,
            "gross_change": gross1 - gross0, "net_opening": net0, "net_closing": net1,
            "net_change": net1 - net0, "pre_adjustment_allowance": pre_allowance}),
        "days_ratios": {key: None if value is None else str(value) for key, value in ratios.items()},
        "alternative_calendar": {"status": "conditional_zero_cost_funding_plan" if debt else "no_funding_needed_at_stated_timing",
            "rows": calendar_report, "minimum_facility_kcu": money_text(debt), "gross_draws_kcu": money_text(debt),
            "final_repayment_kcu": money_text(repay), "cash_after_repayment_kcu": money_text(funded - repay),
            "closing_bridge_debt_kcu": "0", "net_financing_kcu": "0"},
        "zero_residuals_kcu": monetary_dict(residuals),
        "limits": ["Supplied synthetic recognition, loss and cash conventions; no documentary or standards-compliance audit.",
            "Journal order groups receipts before payments; alternative calendar is a separate conditional proposal.",
            "Calendar rows receive cash before supplier and other payments; finer timing can require more credit.",
            "Facility assumes certain availability, zero fees/interest and final repayment; it is not an actual commitment.",
            "Endpoint ratios with mixed cash/credit flows are approximations, not individual physical cycle durations.",
            "Zero-flow ratios and dependent CCC are null (undefined), not zero; supported loss estimates remain external inputs."]
    }


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    try:
        require(len(args) <= 1, "usage: v07-c03-analysis.py [inputs.json]")
        path = Path(args[0]) if args else Path(__file__).with_name("v07-c03-inputs.json")
        result = build_report(load_inputs(path))
    except (ValueError, OSError, UnicodeError) as error:
        print(json.dumps({"status": "invalid_input", "error": str(error)}, allow_nan=False))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
