"""Exact original Aster statements and ratios; standard library, no network.

Run beside v07-c09-inputs.json, or pass a JSON input path. Import/run is quiet.
Fraction strings are exact values; ratio null means denominator is nonpositive.
The README and chapter define the deliberately narrow accounting contract.
"""
from fractions import Fraction as F
import json
from pathlib import Path
import sys


def require(condition, message):
    if not condition:
        raise ValueError(message)


def number(value, label):
    require(type(value) in (int, str), label + " must be an integer or exact rational string")
    try:
        result = F(value)
    except (ValueError, ZeroDivisionError):
        raise ValueError(label + " must be finite and rational") from None
    return result


def ratio(numerator, denominator):
    """Suppress misleading nonpositive denominators; retain signed numerators."""
    return numerator / denominator if denominator > 0 else None


def product(values):
    if any(x is None for x in values):
        return None
    out = F(1)
    for value in values:
        out *= value
    return out


def serial(value):
    if isinstance(value, F):
        return str(value)
    if isinstance(value, dict):
        return {key: serial(item) for key, item in value.items()}
    if isinstance(value, list):
        return [serial(item) for item in value]
    return value


def finish_balance(balance, rate):
    b = dict(balance)
    net_dta = rate * (b["tax_base_ppe"] - b["ppe"])
    b["dta"] = max(net_dta, F(0))
    b["dtl"] = max(-net_dta, F(0))
    b["current_assets"] = b["cash"] + b["receivables"] + b["inventory"]
    b["current_liabilities"] = b["payables"] + b["current_debt"]
    b["long_debt"] = b["debt"] - b["current_debt"]
    b["assets"] = b["current_assets"] + b["ppe"] + b["dta"]
    b["liabilities"] = b["payables"] + b["debt"] + b["dtl"]
    b["invested_capital"] = b["receivables"] + b["inventory"] + b["ppe"] + b["dta"] - b["payables"] - b["dtl"]
    require(b["assets"] == b["liabilities"] + b["equity"], "balance sheet does not reconcile")
    require(b["invested_capital"] == b["debt"] + b["equity"] - b["cash"], "operating/financing capital mismatch")
    require(b["cash"] >= 0, "negative cash requires an explicit funding plan")
    require(0 <= b["current_debt"] <= b["debt"], "current debt must be within total debt")
    require(b["ppe"] >= 0 and b["tax_base_ppe"] >= 0, "depreciation exceeds available carrying amount or tax base")
    return b


def diagnostics(start, end, income, cash, days, rate):
    avg = {k: (start[k] + end[k]) / 2 for k in ("assets", "equity", "invested_capital", "receivables", "inventory", "payables")}
    sales = income["sales"]
    nopat = income["ebit"] * (1 - rate)
    factors3 = [ratio(income["net_income"], sales), ratio(sales, avg["assets"]), ratio(avg["assets"], avg["equity"])]
    factors5 = [ratio(income["net_income"], income["pbt"]), ratio(income["pbt"], income["ebit"]), ratio(income["ebit"], sales), factors3[1], factors3[2]]
    dso = ratio(days * avg["receivables"], sales)
    dio = ratio(days * avg["inventory"], income["cogs"])
    dpo = ratio(days * avg["payables"], cash["credit_purchases"])
    return {
        "averages": avg,
        "current_ratio": ratio(end["current_assets"], end["current_liabilities"]),
        "quick_ratio": ratio(end["cash"] + end["receivables"], end["current_liabilities"]),
        "cash_ratio": ratio(end["cash"], end["current_liabilities"]),
        "debt_equity": ratio(end["debt"], end["equity"]),
        "debt_capital": ratio(end["debt"], end["debt"] + end["equity"]),
        "net_debt": end["debt"] - end["cash"],
        "interest_coverage": ratio(income["ebit"], income["interest"]),
        "debt_ebitda": ratio(end["debt"], income["ebitda"]),
        "gross_margin": ratio(sales - income["cogs"], sales),
        "operating_margin": ratio(income["ebit"], sales),
        "net_margin": factors3[0],
        "asset_turnover": factors3[1],
        "equity_multiplier": factors3[2],
        "roe": ratio(income["net_income"], avg["equity"]),
        "dupont_three_factors": factors3,
        "dupont_three_product": product(factors3),
        "dupont_five_factors": factors5,
        "dupont_five_product": product(factors5),
        "nopat": nopat,
        "roic": ratio(nopat, avg["invested_capital"]),
        "nopat_margin": ratio(nopat, sales),
        "capital_turnover": ratio(sales, avg["invested_capital"]),
        "dso": dso, "dio": dio, "dpo": dpo,
        "cash_cycle": None if None in (dso, dio, dpo) else dso + dio - dpo,
        "cfo_net_income": ratio(cash["cfo"], income["net_income"]),
        "cfo_capex": ratio(cash["cfo"], cash["capex"]),
        "nonpositive_equity_endpoint": min(start["equity"], end["equity"]) <= 0
    }


def simulate(opening, periods, days, rate, book_depreciation):
    balance = finish_balance(opening, rate)
    balances = [balance]
    rows = []
    for index, p in enumerate(periods):
        dep = book_depreciation[index]
        ebitda = p["sales"] - p["cogs"] - p["other_opex"]
        ebit = ebitda - dep
        pbt = ebit - p["interest"]
        taxable = ebitda - p["tax_depreciation"] - p["interest"]
        require(pbt >= 0 and taxable >= 0, "lab requires nonnegative book and taxable profit; loss rules are not implemented")
        current_tax = rate * taxable
        delta_ar = p["receivables"] - balance["receivables"]
        delta_inv = p["inventory"] - balance["inventory"]
        delta_ap = p["payables"] - balance["payables"]
        collections = p["sales"] - delta_ar
        purchases = p["cogs"] + delta_inv
        supplier_cash = purchases - delta_ap
        require(min(collections, purchases, supplier_cash) >= 0, "collections, purchases and supplier payments must be nonnegative")
        ppe = balance["ppe"] + p["capex"] - dep
        tax_base = balance["tax_base_ppe"] + p["capex"] - p["tax_depreciation"]
        net_dta = rate * (tax_base - ppe)
        deferred_expense = (balance["dta"] - balance["dtl"]) - net_dta
        tax_expense = current_tax + deferred_expense
        ni = pbt - tax_expense
        cfo = collections - supplier_cash - p["other_opex"] - p["interest"] - current_tax
        indirect = ni + dep + deferred_expense - delta_ar - delta_inv + delta_ap
        require(cfo == indirect, "direct/indirect CFO mismatch")
        financing = p["borrowing"] - p["debt_repayment"] - p["dividends"]
        end = finish_balance({
            "cash": balance["cash"] + cfo - p["capex"] + financing,
            "receivables": p["receivables"], "inventory": p["inventory"], "ppe": ppe,
            "tax_base_ppe": tax_base, "payables": p["payables"],
            "debt": balance["debt"] + p["borrowing"] - p["debt_repayment"],
            "current_debt": p["current_debt"], "equity": balance["equity"] + ni - p["dividends"]
        }, rate)
        income = {"sales": p["sales"], "cogs": p["cogs"], "other_opex": p["other_opex"],
                  "depreciation": dep, "ebitda": ebitda, "ebit": ebit, "interest": p["interest"],
                  "pbt": pbt, "taxable_profit": taxable, "current_tax": current_tax,
                  "deferred_tax_expense": deferred_expense, "tax_expense": tax_expense, "net_income": ni}
        cash = {"collections": collections, "credit_purchases": purchases, "supplier_payments": supplier_cash,
                "other_opex_paid": p["other_opex"], "interest_paid": p["interest"], "tax_paid": current_tax,
                "delta_receivables": delta_ar, "delta_inventory": delta_inv, "delta_payables": delta_ap,
                "cfo": cfo, "indirect_cfo": indirect, "capex": p["capex"], "cfi": -p["capex"],
                "borrowing": p["borrowing"], "debt_repayment": p["debt_repayment"], "dividends": p["dividends"],
                "cff": financing, "cash_change": end["cash"] - balance["cash"]}
        rows.append({"income": income, "cash_flow": cash, "ratios": diagnostics(balance, end, income, cash, days, rate)})
        balances.append(end)
        balance = end
    return {"balances": balances, "periods": rows}


def run(data):
    require(isinstance(data, dict), "input must be an object")
    require(data.get("units") == "kCU", "units must be kCU")
    require(data.get("full_deferred_tax_recognition_supported") is True, "supplied deferred-tax support is required")
    require(data.get("cash_excluded_from_operating_capital") is True, "lab uses the declared all-cash-excluded definition")
    days = number(data["days_per_period"], "days")
    rate = number(data["tax_rate"], "tax rate")
    require(days > 0 and days.denominator == 1, "days must be a positive integer")
    require(0 <= rate < 1, "tax rate must be between zero inclusive and one exclusive")
    opening_keys = {"cash", "receivables", "inventory", "ppe", "tax_base_ppe", "payables", "debt", "current_debt", "equity"}
    period_keys = {"sales", "cogs", "other_opex", "depreciation", "tax_depreciation", "interest", "receivables", "inventory", "payables", "capex", "borrowing", "debt_repayment", "current_debt", "dividends"}
    require(isinstance(data["opening"], dict) and set(data["opening"]) == opening_keys, "opening fields do not match contract")
    opening = {k: number(v, "opening " + k) for k, v in data["opening"].items()}
    require(all(v >= 0 for k, v in opening.items() if k != "equity"), "opening amounts except equity must be nonnegative")
    require(isinstance(data["periods"], list) and len(data["periods"]) == 2, "exactly two periods required")
    periods = []
    for p in data["periods"]:
        require(isinstance(p, dict) and set(p) == period_keys, "period fields do not match contract")
        q = {k: number(v, k) for k, v in p.items()}
        require(all(v >= 0 for v in q.values()), "period amounts must be nonnegative")
        periods.append(q)
    comparison = data["comparison_book_depreciation"]
    require(isinstance(comparison, list) and len(comparison) == 2, "comparison needs two depreciation amounts")
    comparison = [number(v, "comparison depreciation") for v in comparison]
    base_dep = [p["depreciation"] for p in periods]
    require(min(comparison) >= 0, "comparison depreciation must be nonnegative")
    require(sum(comparison) == sum(base_dep), "comparison must preserve two-period depreciation")
    baseline = simulate(opening, periods, days, rate, base_dep)
    alternative = simulate(opening, periods, days, rate, comparison)
    for i in range(2):
        require(baseline["periods"][i]["cash_flow"] == alternative["periods"][i]["cash_flow"], "book allocation changed cash")
    require(baseline["balances"][-1] == alternative["balances"][-1], "comparison terminal statements differ")
    return serial({"units": "kCU", "days_per_period": days, "tax_rate": rate,
                   "baseline": baseline, "alternative_depreciation": alternative})


if __name__ == "__main__":
    try:
        require(len(sys.argv) <= 2, "usage: python3 v07-c09-analysis.py [inputs.json]")
        location = Path(sys.argv[1]) if len(sys.argv) == 2 else Path(__file__).with_name("v07-c09-inputs.json")
        result = run(json.loads(location.read_text(encoding="utf-8")))
        print(json.dumps(result, indent=2, allow_nan=False))
    except (ValueError, KeyError, TypeError, OSError) as exc:
        print("Input error: " + str(exc), file=sys.stderr)
        sys.exit(2)
