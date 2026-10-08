"""Rowan's complete original project benchmark: fractions, no network or writes."""
from fractions import Fraction as F
from pathlib import Path
import json
import sys

UNITS = "money=kCU; quantity=thousand units; unit prices=CU; shares=thousand ordinary shares"


def need(condition, message):
    if not condition:
        raise ValueError(message)


def num(value):
    need(type(value) in (int, str), "financial inputs require integers or exact rational strings")
    try:
        out = F(value)
    except (ValueError, ZeroDivisionError):
        raise ValueError("invalid finite rational") from None
    need(out >= 0, "negative financial input outside project contract")
    return out


def numeric(row):
    return {key: num(value) for key, value in row.items()}


def encode(value):
    if isinstance(value, F):
        return str(value)
    if isinstance(value, dict):
        return {key: encode(item) for key, item in value.items()}
    if isinstance(value, list):
        return [encode(item) for item in value]
    return value


def quotient(n, d):
    return n / d if d > 0 else None


def balance(row):
    b = dict(row)
    b["debt"] = b["term_debt"] + b["revolver"]
    b["equity"] = b["share_capital"] + b["retained_earnings"]
    b["current_assets"] = b["cash"] + b["receivables"] + b["inventory"]
    b["current_liabilities"] = b["payables"] + b["tax_payable"] + b["current_term"] + b["revolver"]
    b["assets"] = b["current_assets"] + b["ppe"]
    b["liabilities"] = b["payables"] + b["tax_payable"] + b["dtl"] + b["debt"]
    b["invested_capital"] = b["receivables"] + b["inventory"] + b["ppe"] - b["payables"] - b["tax_payable"] - b["dtl"]
    need(0 <= b["current_term"] <= b["term_debt"], "current term debt outside total")
    need(b["cash"] >= 0 and b["ppe"] >= 0 and b["tax_payable"] >= 0, "unsupported negative closing cash, asset or tax balance")
    need(b["assets"] == b["liabilities"] + b["equity"], "balance sheet fails")
    need(b["invested_capital"] == b["debt"] + b["equity"] - b["cash"], "capital classifications fail")
    return b


def diagnostics(opening, closing, income, cash, rate, days):
    avg_assets = (opening["assets"] + closing["assets"]) / 2
    avg_equity = (opening["equity"] + closing["equity"]) / 2
    avg_ic = (opening["invested_capital"] + closing["invested_capital"]) / 2
    mean_ar = (opening["receivables"] + closing["receivables"]) / 2
    return {
        "gross_margin": quotient(income["sales"] - income["cogs"], income["sales"]),
        "operating_margin": quotient(income["ebit"], income["sales"]),
        "net_margin": quotient(income["net_income"], income["sales"]),
        "current_ratio": quotient(closing["current_assets"], closing["current_liabilities"]),
        "quick_ratio": quotient(closing["cash"] + closing["receivables"], closing["current_liabilities"]),
        "interest_coverage": quotient(income["ebit"], income["interest"]),
        "debt_equity": quotient(closing["debt"], closing["equity"]),
        "cfo_to_income": quotient(cash["cfo"], income["net_income"]),
        "dso": quotient(days * mean_ar, income["sales"]),
        "average_assets": avg_assets, "average_equity": avg_equity, "average_capital": avg_ic,
        "asset_turnover": quotient(income["sales"], avg_assets),
        "equity_multiplier": quotient(avg_assets, avg_equity),
        "roe": quotient(income["net_income"], avg_equity),
        "nopat": income["ebit"] * (1 - rate),
        "roic": quotient(income["ebit"] * (1 - rate), avg_ic)
    }


def historical(opening, h, rate, days, corrected):
    sales, cogs = h["quantity"] * h["price"], h["quantity"] * h["unit_cost"]
    maint = h["maintenance_paid"]
    expensed = maint if corrected else F(0)
    capitalized = maint - expensed
    ebit = sales - cogs - h["ordinary_cash_opex"] - expensed - h["old_asset_depreciation"]
    pbt = ebit - h["interest_paid"]
    # Tax recognition of routine maintenance is correct in both presentations.
    taxable = sales - cogs - h["ordinary_cash_opex"] - maint - h["old_asset_depreciation"] - h["interest_paid"]
    need(taxable >= 0 and pbt >= 0, "tax-loss rules not supplied")
    current_tax = taxable * rate
    dtl = capitalized * rate
    deferred = dtl - opening["dtl"]
    ni = pbt - current_tax - deferred
    ar = opening["receivables"] + sales - h["customer_receipts"]
    inv = opening["inventory"] + h["credit_purchases"] - cogs
    ap = opening["payables"] + h["credit_purchases"] - h["supplier_payments"]
    need(min(ar, inv, ap) >= 0, "historical working-capital balances must be nonnegative")
    cfo = h["customer_receipts"] - h["supplier_payments"] - h["ordinary_cash_opex"] - expensed - h["interest_paid"] - h["current_tax_paid"]
    cfi = -h["genuine_capex"] - capitalized
    cff = h["revolver_draw"] - h["term_repayment"] - h["dividend"]
    end = balance({
        "cash": opening["cash"] + cfo + cfi + cff,
        "receivables": ar, "inventory": inv,
        "ppe": opening["ppe"] + h["genuine_capex"] + capitalized - h["old_asset_depreciation"],
        "payables": ap, "tax_payable": opening["tax_payable"] + current_tax - h["current_tax_paid"], "dtl": dtl,
        "term_debt": opening["term_debt"] - h["term_repayment"], "current_term": h["current_term_at_close"],
        "revolver": opening["revolver"] + h["revolver_draw"], "share_capital": opening["share_capital"],
        "retained_earnings": opening["retained_earnings"] + ni - h["dividend"], "shares": opening["shares"]
    })
    delta_wc = ar - opening["receivables"] + inv - opening["inventory"] - ap + opening["payables"]
    indirect = ni + h["old_asset_depreciation"] + deferred - delta_wc + end["tax_payable"] - opening["tax_payable"]
    need(indirect == cfo, "historical CFO routes disagree")
    income = {"sales": sales, "cogs": cogs, "ordinary_opex": h["ordinary_cash_opex"], "maintenance_expense": expensed,
              "depreciation": h["old_asset_depreciation"], "ebit": ebit, "ebitda": ebit + h["old_asset_depreciation"],
              "interest": h["interest_paid"], "pbt": pbt, "taxable_profit": taxable, "current_tax": current_tax,
              "deferred_tax_expense": deferred, "total_tax": current_tax + deferred, "net_income": ni}
    cash = {"receipts": h["customer_receipts"], "purchases": h["credit_purchases"], "supplier_payments": h["supplier_payments"],
            "ordinary_opex_paid": h["ordinary_cash_opex"], "operating_maintenance_paid": expensed, "interest_paid": h["interest_paid"],
            "tax_paid": h["current_tax_paid"], "cfo": cfo, "indirect_cfo": indirect, "nwc_increase": delta_wc,
            "genuine_capex": h["genuine_capex"], "invalid_capitalized_payment": capitalized, "cfi": cfi,
            "revolver_change": h["revolver_draw"], "term_repayment": h["term_repayment"], "dividend": h["dividend"],
            "equity_issue": F(0), "cff": cff, "cash_change": cfo + cfi + cff}
    return {"status": "corrected" if corrected else "uncorrected-draft", "opening": opening, "income": income,
            "cash_flow": cash, "closing": end, "ratios": diagnostics(opening, end, income, cash, rate, days)}


def forecast(start, s, policy, h, rate, days, capex, dividend, new_equity):
    need(policy["minimum_capex"] <= capex <= policy["planned_capex"], "capex outside supplied feasible range")
    need(0 <= dividend <= policy["planned_dividend"], "dividend outside permitted range")
    need(0 <= new_equity <= policy["subscription_capacity"], "equity exceeds supplied subscription capacity")
    sales, cogs = s["quantity"] * s["price"], s["quantity"] * s["unit_cost"]
    ar, inv = sales * s["receivables_sales"], cogs * s["inventory_cogs"]
    purchases = cogs + inv - start["inventory"]
    ap = purchases * s["payables_purchases"]
    receipts, suppliers = sales + start["receivables"] - ar, purchases + start["payables"] - ap
    need(min(purchases, receipts, suppliers) >= 0, "negative forecast purchase/payment requires new rules")
    dep = policy["old_asset_depreciation"] + h["genuine_capex"] / policy["new_asset_life"]
    interest = policy["interest_rate"] * start["debt"]
    opex = policy["ordinary_cash_opex"] + policy["maintenance_paid"]
    ebit = sales - cogs - opex - dep
    pbt = ebit - interest
    need(pbt >= 0, "forecast tax losses not supplied")
    tax, ni = pbt * rate, pbt * (1 - rate)
    tax_paid = start["tax_payable"] + tax
    cfo = receipts - suppliers - opex - interest - tax_paid
    nwc_increase = ar - start["receivables"] + inv - start["inventory"] - ap + start["payables"]
    indirect = ni + dep - nwc_increase - start["tax_payable"]
    need(cfo == indirect, "forecast CFO routes disagree")
    # Debt adjustments and subscription settle on the final date; no current interest.
    before_revolver = start["cash"] + cfo - capex - dividend - policy["term_repayment"] + new_equity
    change = max(policy["minimum_cash"] - before_revolver, -start["revolver"])
    required = start["revolver"] + change
    gap = max(F(0), required - policy["revolver_limit"])
    max_draw_cash = before_revolver + policy["revolver_limit"] - start["revolver"]
    income = {"sales": sales, "cogs": cogs, "ordinary_opex": policy["ordinary_cash_opex"],
              "maintenance_expense": policy["maintenance_paid"], "depreciation": dep, "ebit": ebit,
              "ebitda": ebit + dep, "interest": interest, "pbt": pbt, "taxable_profit": pbt,
              "current_tax": tax, "deferred_tax_expense": F(0), "total_tax": tax, "net_income": ni}
    cash = {"receipts": receipts, "purchases": purchases, "supplier_payments": suppliers,
            "ordinary_opex_paid": policy["ordinary_cash_opex"], "operating_maintenance_paid": policy["maintenance_paid"],
            "interest_paid": interest, "tax_paid": tax_paid, "cfo": cfo, "indirect_cfo": indirect,
            "nwc_increase": nwc_increase, "genuine_capex": capex, "invalid_capitalized_payment": F(0), "cfi": -capex,
            "term_repayment": policy["term_repayment"], "dividend": dividend, "equity_issue": new_equity}
    funding = {"minimum_cash": policy["minimum_cash"], "cash_before_revolver": before_revolver,
               "required_revolver": required, "revolver_limit": policy["revolver_limit"], "gap_to_minimum": gap,
               "cash_after_maximum_draw": max_draw_cash, "subscription_used": new_equity}
    if gap > 0:
        return {"status": "unfunded", "opening": start, "income": income, "cash_flow": cash, "funding": funding,
                "closing": None, "ratios": None,
                "limitation": "No feasible closing balance sheet or financing cash flow asserted for the rejected plan."}
    cash.update({"revolver_change": change, "cff": change - policy["term_repayment"] - dividend + new_equity})
    cash["cash_change"] = cfo + cash["cfi"] + cash["cff"]
    end = balance({
        "cash": start["cash"] + cash["cash_change"], "receivables": ar, "inventory": inv,
        "ppe": start["ppe"] + capex - dep, "payables": ap, "tax_payable": F(0), "dtl": F(0),
        "term_debt": start["term_debt"] - policy["term_repayment"], "current_term": policy["current_term_at_close"],
        "revolver": required, "share_capital": start["share_capital"] + new_equity,
        "retained_earnings": start["retained_earnings"] + ni - dividend,
        "shares": start["shares"] + new_equity / policy["subscription_price"]
    })
    need(end["cash"] >= policy["minimum_cash"], "minimum cash failed")
    return {"status": "funded-at-annual-close", "opening": start, "income": income, "cash_flow": cash,
            "funding": funding, "closing": end, "ratios": diagnostics(start, end, income, cash, rate, days)}


def run(data):
    need(data["case"] == "Rowan Industrial Supply: original integrated accounting project", "fixed project case required")
    need(data["units"] == UNITS, "project units mismatch")
    need([data[k] for k in ("opening_date", "historical_close", "forecast_close")] == ["2024-12-31", "2025-12-31", "2026-12-31"], "fixed annual timeline required")
    rate, days = num(data["tax_rate"]), num(data["days_per_year"])
    need(rate < 1 and days == 365, "tax rate or year length outside contract")
    o, h, p = numeric(data["opening"]), numeric(data["historical"]), numeric(data["forecast_policy"])
    need(o["tax_payable"] == o["dtl"] == o["revolver"] == 0, "fixed zero opening tax and revolver balances required")
    need(h["term_repayment"] <= o["term_debt"], "historical repayment exceeds debt")
    need(h["old_asset_depreciation"] + p["old_asset_depreciation"] <= o["ppe"], "original assets overdepreciated")
    need(p["new_asset_life"] >= 2 and p["subscription_price"] > 0 and p["interest_rate"] <= 1, "asset life, subscription price or interest domain")
    need(p["minimum_capex"] <= p["planned_capex"], "capex minimum exceeds plan")
    need(h["interest_paid"] == p["interest_rate"] * o["term_debt"], "historical interest inconsistent with opening debt contract")
    opening = balance(o)
    draft = historical(opening, h, rate, days, False)
    corrected = historical(opening, h, rate, days, True)
    start = corrected["closing"]
    need(start["revolver"] <= p["revolver_limit"] and p["term_repayment"] <= start["term_debt"], "forecast opening debt contract")
    scenarios = {name: numeric(data["scenarios"][name]) for name in ("base", "adverse")}
    for s in scenarios.values():
        need(all(s[k] <= 1 for k in ("receivables_sales", "inventory_cogs", "payables_purchases")), "working-capital fractions must be in [0,1]")
    make = lambda name, capex, dividend, eq: forecast(start, scenarios[name], p, h, rate, days, capex, dividend, eq)
    base = make("base", p["planned_capex"], p["planned_dividend"], F(0))
    adverse = make("adverse", p["planned_capex"], p["planned_dividend"], F(0))
    dividend_cut = make("adverse", p["planned_capex"], F(0), F(0))
    max_deferral = make("adverse", p["minimum_capex"], F(0), F(0))
    required_equity = max_deferral["funding"]["gap_to_minimum"]
    if required_equity <= p["subscription_capacity"]:
        repaired = make("adverse", p["minimum_capex"], F(0), required_equity)
    else:
        repaired = None
    full_subscription = make("adverse", p["minimum_capex"], F(0), p["subscription_capacity"])
    ownership = None if repaired is None else {
        "required_subscription": required_equity, "available_subscription": p["subscription_capacity"],
        "new_shares": required_equity / p["subscription_price"], "total_shares": repaired["closing"]["shares"],
        "new_investor_fraction": (required_equity / p["subscription_price"]) / repaired["closing"]["shares"]
    }
    correction = {"journal": [
        {"debit": "maintenance expense", "credit": "PPE", "amount": h["maintenance_paid"]},
        {"debit": "DTL", "credit": "deferred tax benefit", "amount": h["maintenance_paid"] * rate}
    ], "net_income_change": corrected["income"]["net_income"] - draft["income"]["net_income"],
       "cfo_change": corrected["cash_flow"]["cfo"] - draft["cash_flow"]["cfo"],
       "cfi_change": corrected["cash_flow"]["cfi"] - draft["cash_flow"]["cfi"],
       "cash_change": corrected["closing"]["cash"] - draft["closing"]["cash"]}
    need(correction["cash_change"] == 0, "correction invented historical cash")
    return encode({"case": data["case"], "units": UNITS, "opening": opening,
                   "historical_draft": draft, "historical_corrected": corrected, "correction": correction,
                   "base": base, "adverse": adverse, "adverse_dividend_cut": dividend_cut,
                   "adverse_max_deferral": max_deferral, "adverse_funded_repair": repaired,
                   "adverse_full_subscription": full_subscription, "subscription": ownership,
                   "limitation": "Exact original conditional case; no real evidence, tax law, within-year liquidity or financing approval is certified."})


if __name__ == "__main__":
    try:
        need(len(sys.argv) <= 2, "usage: python3 v07-assessment-analysis.py [inputs.json]")
        path = Path(sys.argv[1]) if len(sys.argv) == 2 else Path(__file__).with_name("v07-assessment-inputs.json")
        print(json.dumps(run(json.loads(path.read_text(encoding="utf-8"))), indent=2, allow_nan=False))
    except (ValueError, KeyError, TypeError, OSError) as exc:
        print("Invalid project contract: " + str(exc), file=sys.stderr)
        sys.exit(2)
