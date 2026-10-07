"""Offline benchmark for the synthetic v04-c02 model; Python standard library only.

Run: python3 v04-c02-benchmark.py [v04-c02-inputs.json]
The JSON result is printed to stdout; inputs are never modified.
No workbook engine is used. The chapter teaches the corresponding cell formulas.
"""
import json
import math
from pathlib import Path
import sys


def number(value, label, minimum=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric, not text, null or a boolean")
    if not math.isfinite(value):
        raise ValueError(f"{label} must be finite")
    if minimum is not None and value < minimum:
        raise ValueError(f"{label} must be at least {minimum}")
    return float(value)


def rate(value):
    result = number(value, "discount rate")
    if result <= -1:
        raise ValueError("discount rate must exceed -1")
    return result


def project(inputs, discount_rate=None, quantity_multiplier=None):
    """Compute exactly three end-of-year periods, keeping t=0 undiscounted."""
    r = rate(inputs["discount_rate"] if discount_rate is None else discount_rate)
    multiplier = number(inputs["quantity_multiplier"] if quantity_multiplier is None
                        else quantity_multiplier, "quantity multiplier", 0)
    price = number(inputs["price_per_unit"], "unit price", 0)
    variable = number(inputs["variable_cost_per_unit"], "unit variable cost", 0)
    fixed = number(inputs["fixed_cash_cost_per_year"], "annual fixed cost", 0)
    equipment = number(inputs["initial_equipment_outlay"], "equipment outlay", 0)
    working = number(inputs["initial_working_capital"], "working capital", 0)
    disposal = number(inputs["terminal_equipment_receipt"], "equipment receipt", 0)
    recovery = number(inputs["terminal_working_capital_recovery"], "working-capital recovery", 0)
    if not isinstance(inputs["base_annual_units"], list) or len(inputs["base_annual_units"]) != 3:
        raise ValueError("the teaching model requires three annual unit counts")
    base_units = [number(q, f"year {t} units", 0)
                  for t, q in enumerate(inputs["base_annual_units"], 1)]
    timeline = [{"year": 0, "cash_flow": -equipment-working,
                 "discount_factor": 1.0, "present_value": -equipment-working}]
    discount_factor = 1.0
    for year, base in enumerate(base_units, 1):
        units = base*multiplier
        revenue = units*price
        variable_payment = units*variable
        operating_cash = revenue-variable_payment-fixed
        final_recovery = recovery if year == 3 else 0.0
        final_disposal = disposal if year == 3 else 0.0
        cash_flow = operating_cash+final_recovery+final_disposal
        discount_factor /= 1+r
        timeline.append({"year": year, "units": units, "revenue": revenue,
                         "variable_cash_payment": variable_payment,
                         "fixed_cash_payment": fixed, "operating_cash": operating_cash,
                         "working_capital_recovery": final_recovery,
                         "equipment_receipt": final_disposal, "cash_flow": cash_flow,
                         "discount_factor": discount_factor,
                         "present_value": cash_flow*discount_factor})
    result = {"discount_rate": r, "quantity_multiplier": multiplier,
              "timeline": timeline,
              "npv": math.fsum(row["present_value"] for row in timeline),
              "working_capital_net_cash": recovery-working}
    if not all(math.isfinite(row["present_value"]) for row in timeline):
        raise ValueError("inputs exceed the numerical range of this teaching model")
    return result


def reconcile(inputs):
    p = {key: number(value, key, 0) for key, value in inputs.items()}
    recorded_payments = (p["recorded_supplier_payments"] + p["wage_payments"]
                         + p["equipment_payments"])
    predicted = p["opening_cash"]+p["customer_receipts"]-recorded_payments
    corrected = predicted-p["confirmed_omitted_supplier_payment"]
    return {"recorded_total_payments": recorded_payments,
            "predicted_closing_cash": predicted,
            "residual_before": p["independent_bank_closing_cash"]-predicted,
            "corrected_closing_cash": corrected,
            "residual_after": p["independent_bank_closing_cash"]-corrected}


def run(inputs):
    p = inputs["project"]
    grid = [{"quantity_multiplier": m,
             "cases": [{"discount_rate": r, "npv": project(p, r, m)["npv"]}
                       for r in inputs["sensitivity"]["discount_rates"]]}
            for m in inputs["sensitivity"]["quantity_multipliers"]]
    return {"provenance": inputs["provenance"], "base_case": project(p),
            "sensitivity": grid, "bank_reconciliation": reconcile(inputs["bank_reconciliation"]),
            "limitations": ["Synthetic assumptions, not a valuation recommendation.",
                            "Floating-point implementation; amounts displayed to cents only after calculation.",
                            "No spreadsheet application or formula-recalculation engine is invoked.",
                            "A matching benchmark checks implementation conditional on shared assumptions."]}


if __name__ == "__main__":
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("v04-c02-inputs.json")
    try:
        print(json.dumps(run(json.loads(path.read_text(encoding="utf-8"))), indent=2, allow_nan=False))
    except (OSError, ValueError, KeyError, TypeError, OverflowError) as exc:
        print(json.dumps({"status": "error", "message": str(exc)}))
        raise SystemExit(1)
