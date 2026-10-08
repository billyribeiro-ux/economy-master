"""Exact synthetic accounting diagnosis; no dependencies, files written or network."""
from fractions import Fraction as F
from pathlib import Path
import json
import sys

UNITS = {"money":"kCU", "period":"one year", "packages":"whole installations"}
FIELDS = {
    "opening": "cash receivables inventory ppe payables tax_payable debt equity",
    "operations": "revenue cost_of_sales cash_costs_before_recovery cash_settlement_recovery depreciation interest tax_rate tax_paid severance marketing",
    "closing_reported": "receivables inventory payables",
    "flows": "capex debt_principal_paid dividends",
    "contract": "max_net_debt_to_covenant_ebitda severance_cap min_eligible_cash",
    "corrections": "premature_revenue capitalized_repair",
    "actions": "new_equity extra_debt_payment restricted_cash",
    "growth": "new_packages price unit_cost extra_fixed_cash depreciation interest capex receivables inventory payables",
}


def amount(value):
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ValueError("amounts must be integers or exact strings, not binary floats")
    try:
        x = F(value)
    except (ValueError, ZeroDivisionError) as exc:
        raise ValueError("invalid exact amount") from exc
    if x < 0:
        raise ValueError("negative input outside this teaching contract")
    return x


def read_data(data):
    if not isinstance(data, dict) or data.get("case") != "Atlas Field Systems integration case" or data.get("units") != UNITS:
        raise ValueError("unsupported case or units")
    out = {}
    for name, fields in FIELDS.items():
        if set(data[name]) != set(fields.split()):
            raise ValueError("unexpected fields in " + name)
        out[name] = {k: amount(v) for k, v in data[name].items()}
    o, p, c, f, t, r, a, g = (out[k] for k in FIELDS)
    if sum(o[k] for k in ("cash", "receivables", "inventory", "ppe")) != sum(o[k] for k in ("payables", "tax_payable", "debt", "equity")):
        raise ValueError("opening balance sheet does not balance")
    if p["tax_rate"] > 1 or t["max_net_debt_to_covenant_ebitda"] <= 0:
        raise ValueError("tax rate or covenant limit outside domain")
    if p["severance"] + p["marketing"] > p["cash_costs_before_recovery"]:
        raise ValueError("severance and marketing must be included in cash operating costs")
    if r["premature_revenue"] > min(p["revenue"], c["receivables"]):
        raise ValueError("reversal exceeds recorded revenue or receivable")
    if r["capitalized_repair"] > f["capex"]:
        raise ValueError("repair correction exceeds recorded capital spending")
    if f["debt_principal_paid"] + a["extra_debt_payment"] > o["debt"]:
        raise ValueError("principal payment exceeds debt")
    if g["new_packages"].denominator != 1 or g["new_packages"] > 1000:
        raise ValueError("growth requires bounded whole installations")
    return out


def growth_bridge(g, rate):
    revenue = g["new_packages"] * g["price"]
    cost = g["new_packages"] * g["unit_cost"]
    ebitda = revenue - cost - g["extra_fixed_cash"]
    ebit = ebitda - g["depreciation"]
    pretax = ebit - g["interest"]
    if pretax < 0 or g["depreciation"] > g["capex"]:
        raise ValueError("growth fixture excludes tax losses and depreciation beyond new assets")
    tax = pretax * rate
    net = pretax - tax
    nwc = g["receivables"] + g["inventory"] - g["payables"]
    receipts = revenue - g["receivables"]
    supplier_cash = cost + g["inventory"] - g["payables"]
    if receipts < 0 or supplier_cash < 0:
        raise ValueError("growth cash receipts or supplier payments negative")
    cfo = receipts - supplier_cash - g["extra_fixed_cash"] - g["interest"] - tax
    cash = cfo - g["capex"]
    assets = cash + g["receivables"] + g["inventory"] + g["capex"] - g["depreciation"]
    return dict(revenue=revenue, cost_of_sales=cost, ebitda=ebitda, ebit=ebit,
                pretax=pretax, tax_expense_and_cash=tax, net_income=net,
                net_working_capital=nwc, receipts=receipts, supplier_payments=supplier_cash,
                cfo=cfo, indirect_cfo=net+g["depreciation"]-nwc,
                investing_cash=-g["capex"], cash_change=cash,
                asset_change=assets, liabilities_and_equity_change=g["payables"]+net,
                funding_to_keep_comparator_cash=max(F(0), -cash))


def analyze(data):
    d = read_data(data)
    o, p, c, f, t, r, a, g = (d[k] for k in FIELDS)
    revenue = p["revenue"] - r["premature_revenue"]
    receivables = c["receivables"] - r["premature_revenue"]
    operating_cash_cost = p["cash_costs_before_recovery"] - p["cash_settlement_recovery"] + r["capitalized_repair"]
    ebitda = revenue - p["cost_of_sales"] - operating_cash_cost
    ebit = ebitda - p["depreciation"]
    pretax = ebit - p["interest"]
    if pretax < 0:
        raise ValueError("fixture excludes tax losses and tax-loss relief")
    tax = pretax * p["tax_rate"]
    payable_tax = o["tax_payable"] + tax - p["tax_paid"]
    if payable_tax < 0:
        raise ValueError("fixture excludes current-tax receivables and refunds")
    net = pretax - tax
    capex = f["capex"] - r["capitalized_repair"]
    ppe = o["ppe"] + capex - p["depreciation"]
    if ppe < 0:
        raise ValueError("negative closing PPE")
    changes = dict(receivables=receivables-o["receivables"],
                   inventory=c["inventory"]-o["inventory"],
                   payables=c["payables"]-o["payables"],
                   tax_payable=payable_tax-o["tax_payable"])
    receipts = revenue - changes["receivables"]
    supplier_cash = p["cost_of_sales"] + changes["inventory"] - changes["payables"]
    if receipts < 0 or supplier_cash < 0:
        raise ValueError("negative operating cash receipts or supplier payments")
    cfo = receipts - supplier_cash - operating_cash_cost - p["interest"] - p["tax_paid"]
    indirect = net + p["depreciation"] - changes["receivables"] - changes["inventory"] + changes["payables"] + changes["tax_payable"]
    financing = a["new_equity"] - f["debt_principal_paid"] - a["extra_debt_payment"] - f["dividends"]
    cash = o["cash"] + cfo - capex + financing
    debt = o["debt"] - f["debt_principal_paid"] - a["extra_debt_payment"]
    equity = o["equity"] + net - f["dividends"] + a["new_equity"]
    if cash < 0 or a["restricted_cash"] > cash:
        raise ValueError("unfunded closing cash or restricted cash exceeds cash")
    eligible = cash - a["restricted_cash"]
    net_debt = max(F(0), debt-eligible)
    allowed = min(p["severance"], t["severance_cap"])
    covenant_ebitda = ebitda + allowed
    positive_denominator = covenant_ebitda > 0
    debt_headroom = t["max_net_debt_to_covenant_ebitda"]*covenant_ebitda-net_debt
    cash_headroom = eligible-t["min_eligible_cash"]
    assets = cash+receivables+c["inventory"]+ppe
    liabilities = c["payables"]+payable_tax+debt
    return dict(case=data["case"], units=UNITS, corrections=r, actions=a,
                income=dict(revenue=revenue,cost_of_sales=p["cost_of_sales"],net_cash_operating_expense=operating_cash_cost,
                            ebitda=ebitda,depreciation=p["depreciation"],ebit=ebit,interest=p["interest"],pretax=pretax,tax=tax,net_income=net),
                closing=dict(cash=cash,receivables=receivables,inventory=c["inventory"],ppe=ppe,
                             payables=c["payables"],tax_payable=payable_tax,debt=debt,equity=equity,
                             assets=assets,liabilities=liabilities,liabilities_and_equity=liabilities+equity),
                cash_flow=dict(customer_receipts=receipts,supplier_payments=supplier_cash,operating_cost_net_payment=operating_cash_cost,
                               interest_paid=p["interest"],tax_paid=p["tax_paid"],cfo=cfo,indirect_cfo=indirect,
                               investing=-capex,financing=financing,cash_change=cfo-capex+financing,working_capital_changes=changes),
                covenant=dict(eligible_cash=eligible,net_debt=net_debt,allowed_severance=allowed,ebitda=covenant_ebitda,
                              leverage=net_debt/covenant_ebitda if positive_denominator else None,
                              debt_headroom=debt_headroom,cash_headroom=cash_headroom,
                              passes=positive_denominator and debt_headroom>=0 and cash_headroom>=0),
                normalization=dict(ebitda=ebitda+p["severance"]-p["cash_settlement_recovery"],
                                   assumed_nonrecurring_severance=p["severance"],removed_favorable_recovery=p["cash_settlement_recovery"],
                                   recurring_marketing_retained=p["marketing"]),
                growth=growth_bridge(g,p["tax_rate"]))


def exact_json(value):
    if isinstance(value,F): return str(value)
    if isinstance(value,dict): return {k:exact_json(v) for k,v in value.items()}
    if isinstance(value,list): return [exact_json(v) for v in value]
    return value


def run(data):
    return exact_json(analyze(data))


def main():
    path=Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).with_name("v07-c12-inputs.json")
    try:
        result=run(json.loads(path.read_text()))
    except (ValueError,KeyError,TypeError) as exc:
        raise SystemExit("Invalid teaching-case input: "+str(exc)) from exc
    print(json.dumps(result,indent=2,allow_nan=False))


if __name__ == "__main__":
    main()
