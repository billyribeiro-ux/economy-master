"""Exact, scoped cash-flow and discounting lab. Python standard library only."""
from fractions import Fraction as F
import json
from pathlib import Path
import sys


def need(condition, message):
    if not condition:
        raise ValueError(message)


def number(value):
    need(type(value) in (int, str), "use integers or exact decimal/fraction strings")
    try:
        return F(value)
    except (ValueError, ZeroDivisionError) as exc:
        raise ValueError("invalid finite rational input") from exc


def nonnegative(value):
    x = number(value)
    need(x >= 0, "nonnegative money or rate required by this runoff contract")
    return x


def encode(value):
    if isinstance(value, F):
        return str(value)
    if isinstance(value, dict):
        return {k: encode(v) for k, v in value.items()}
    if isinstance(value, list):
        return [encode(v) for v in value]
    return value


def pv(cash, rate):
    need(rate > -1, "discount rate must exceed -100%")
    return sum((c / (1 + rate) ** t for t, c in enumerate(cash, 1)), F(0))


def continuation(explicit, rate, next_cash, growth):
    need(explicit and rate > -1 and growth > -1 and growth < rate, "positive finite perpetuity needs -1 < growth < rate")
    need(next_cash > 0, "positive next-period continuation cash required")
    horizon = len(explicit)
    terminal = next_cash / (rate - growth)
    return {"horizon": horizon, "next_cash": next_cash, "terminal_at_horizon": terminal,
            "explicit_pv": pv(explicit, rate), "terminal_pv": terminal / (1 + rate) ** horizon,
            "value": pv(explicit, rate) + terminal / (1 + rate) ** horizon}


def runoff(data):
    tax, rate = nonnegative(data["tax_rate"]), nonnegative(data["certain_rate"])
    need(tax < 1, "tax must be below 100%")
    opening = {k: number(v) for k, v in data["opening"].items()}
    need(set(opening) == {"cash", "receivables", "ppe", "debt", "book_equity"}, "opening account contract")
    need(opening["cash"] == 0 and all(opening[k] >= 0 for k in ("receivables", "ppe", "debt")), "zero cash and nonnegative operating/debt stocks required")
    need(opening["receivables"] + opening["ppe"] == opening["debt"] + opening["book_equity"], "opening accounts do not balance")
    need(len(data["periods"]) == 2, "two annual runoff periods required")
    rows = []; start = dict(opening)
    for t, raw in enumerate(data["periods"], 1):
        p = {k: nonnegative(v) for k, v in raw.items()}
        need(set(p) == {"sales", "cash_operating_costs", "depreciation", "capex", "closing_receivables", "closing_debt"}, "period input contract")
        need(p["depreciation"] <= start["ppe"], "year-end capex cannot be depreciated before service")
        interest = rate * start["debt"]
        ebit = p["sales"] - p["cash_operating_costs"] - p["depreciation"]
        need(ebit >= interest, "loss/delayed-shield regime outside this lab")
        tax_unlevered = tax * ebit; tax_levered = tax * (ebit - interest)
        ni = ebit - interest - tax_levered
        delta_wc = p["closing_receivables"] - start["receivables"]
        borrowing = p["closing_debt"] - start["debt"]
        receipts = p["sales"] - delta_wc
        need(receipts >= 0, "negative collections outside contract")
        reinvestment = p["capex"] - p["depreciation"] + delta_wc
        fcff = ebit - tax_unlevered - reinvestment
        fcfe = ni + p["depreciation"] - p["capex"] - delta_wc + borrowing
        need(fcfe >= 0, "negative equity cash requires a funding contract outside this payout-only lab")
        cfo = receipts - p["cash_operating_costs"] - interest - tax_levered
        closing = {"cash": F(0), "receivables": p["closing_receivables"],
                   "ppe": start["ppe"] + p["capex"] - p["depreciation"], "debt": p["closing_debt"],
                   "book_equity": start["book_equity"] + ni - fcfe}
        need(closing["ppe"] >= 0, "PPE overdepreciated")
        need(closing["ppe"] + closing["receivables"] == closing["debt"] + closing["book_equity"], "closing accounts do not balance")
        rows.append({"date": data["dates"][t], "opening": start, "closing": closing,
                     "sales": p["sales"], "cash_operating_costs": p["cash_operating_costs"],
                     "ebit": ebit, "depreciation": p["depreciation"], "capex": p["capex"],
                     "delta_wc": delta_wc, "net_reinvestment": reinvestment,
                     "nopat": ebit - tax_unlevered, "interest": interest,
                     "unlevered_cash_tax": tax_unlevered, "levered_cash_tax": tax_levered,
                     "tax_shield": tax_unlevered - tax_levered, "net_income": ni,
                     "receipts": receipts, "cfo": cfo, "indirect_cfo": ni + p["depreciation"] - delta_wc,
                     "cfi": -p["capex"], "cff": borrowing - fcfe, "net_borrowing": borrowing,
                     "fcff": fcff, "fcfe": fcfe, "debt_cash": interest - borrowing,
                     "all_investor_cash": fcfe + interest - borrowing})
        start = closing
    need(all(start[k] == 0 for k in start), "finite runoff must end with zero balances")
    firm_values = [F(0)] * 3
    for i in (1, 0):
        firm_values[i] = (rows[i]["all_investor_cash"] + firm_values[i + 1]) / (1 + rate)
    debts = [opening["debt"]] + [row["closing"]["debt"] for row in rows]
    equity_values = [v - d for v, d in zip(firm_values, debts)]
    need(all(e >= 0 for e in equity_values) and all(v > 0 for v in firm_values[:2]), "claims not covered by certain remaining cash")
    waccs = []
    for i, row in enumerate(rows):
        wacc = rate * (equity_values[i] + (1 - tax) * debts[i]) / firm_values[i]
        waccs.append(wacc)
        row.update({"opening_operating_value": firm_values[i], "closing_operating_value": firm_values[i + 1],
                    "opening_equity_value": equity_values[i], "closing_equity_value": equity_values[i + 1],
                    "opening_debt_weight": debts[i] / firm_values[i], "wacc": wacc})
    discount = F(1); fcff_value = F(0)
    for row, wacc in zip(rows, waccs):
        discount *= 1 + wacc
        fcff_value += row["fcff"] / discount
    return {"periods": rows, "operating_values": firm_values, "debt_values": debts, "equity_values": equity_values,
            "fcff_value": fcff_value, "fcfe_value": pv([r["fcfe"] for r in rows], rate),
            "debt_cash_value": pv([r["debt_cash"] for r in rows], rate),
            "unlevered_value": pv([r["fcff"] for r in rows], rate),
            "shield_value": pv([r["tax_shield"] for r in rows], rate), "waccs": waccs}


def run(data):
    need(data["case"] == "Cedar Service Runoff: original free-cash-flow case", "fixed case label required")
    need(data["units"] == "kCU; annual end-date cash; effective annual rates", "units contract")
    need(data["dates"] == ["2026-12-31", "2027-12-31", "2028-12-31"], "fixed annual timeline")
    real = data["real_nominal"]
    real_cash = [nonnegative(v) for v in real["real_cash"]]
    real_rate, inflation = number(real["real_rate"]), number(real["inflation"])
    need(real_cash and real_rate > -1 and inflation > -1 and number(real["price_index_at_zero"]) == 1, "real/nominal contract")
    nominal_rate = (1 + real_rate) * (1 + inflation) - 1
    nominal_cash = [c * (1 + inflation) ** t for t, c in enumerate(real_cash, 1)]
    cur = data["currency"]
    foreign_cash = [nonnegative(v) for v in cur["foreign_cash"]]
    foreign_rate, home_rate = number(cur["foreign_rate"]), number(cur["home_rate"])
    spot = nonnegative(cur["spot_home_per_foreign"])
    path = [nonnegative(v) for v in cur["future_home_per_foreign"]]
    need(spot > 0 and foreign_rate > -1 and home_rate > -1 and foreign_cash and len(path) == len(foreign_cash), "currency contract")
    need(path == [spot * ((1 + home_rate) / (1 + foreign_rate)) ** t for t in range(1, len(path) + 1)], "supplied certain conversion path conflicts with rates")
    home_cash = [c * x for c, x in zip(foreign_cash, path)]
    terminal = data["continuation"]
    continued = continuation([nonnegative(v) for v in terminal["explicit_cash"]], number(terminal["rate"]), nonnegative(terminal["next_cash"]), number(terminal["growth"]))
    return encode({"case": data["case"], "runoff": runoff(data),
                   "real_nominal": {"real_cash": real_cash, "nominal_cash": nominal_cash, "nominal_rate": nominal_rate,
                                    "real_pv": pv(real_cash, real_rate), "nominal_pv": pv(nominal_cash, nominal_rate)},
                   "currency": {"home_per_foreign_path": path, "home_cash": home_cash,
                                "foreign_pv": pv(foreign_cash, foreign_rate), "home_pv": pv(home_cash, home_rate),
                                "spot_converted_foreign_pv": spot * pv(foreign_cash, foreign_rate)},
                   "continuation": continued,
                   "limitation": "Exact original conditional examples; certainty/rates/tax usage are supplied, not estimated. No general risky-valuation, foreign-exchange forecasting, legal payout or tax-loss engine."})


if __name__ == "__main__":
    try:
        need(len(sys.argv) <= 2, "usage: python3 v08-c02-analysis.py [inputs.json]")
        source = Path(sys.argv[1]) if len(sys.argv) == 2 else Path(__file__).with_name("v08-c02-inputs.json")
        print(json.dumps(run(json.loads(source.read_text(encoding="utf-8"))), indent=2, allow_nan=False))
    except (ValueError, KeyError, TypeError, OSError) as exc:
        print("Invalid free-cash-flow contract: " + str(exc), file=sys.stderr)
        sys.exit(2)
