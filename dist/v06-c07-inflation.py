"""Exact original inflation-model lab; standard library, no network or mutation.

All logarithmic quantities are log points. No empirical parameter is estimated.
The undivided pricing fixed point also handles fully preset/reset endpoints.
"""
import argparse
from fractions import Fraction as F
import json
from pathlib import Path
import re

DEFAULT = Path(__file__).with_name("v06-c07-models.json")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def number(value):
    require(isinstance(value, str) and re.fullmatch(r"-?\d+(?:/[1-9]\d*)?", value),
            "quantities must be integer/rational strings")
    return F(value)


def values(case, keys):
    return [number(case[key]) for key in keys.split()]


def pack(value):
    if isinstance(value, F):
        return str(value)
    if isinstance(value, dict):
        return {k: pack(v) for k, v in value.items()}
    if isinstance(value, list):
        return [pack(x) for x in value]
    return value


def probabilities(states):
    require(isinstance(states, list) and states, "states must be nonempty")
    ps = [number(row["probability"]) for row in states]
    require(all(p > 0 for p in ps) and sum(ps) == 1, "positive probabilities must sum to one")
    return ps


def pricing(case):
    s, a, b, target, e, d, z = values(case, "s a b anchor e d z")
    require(0 <= s <= 1 and a > 0 and b > 0, "pricing requires s in [0,1], a,b>0")
    denominator = s+(1-s)*a*b
    inflation = (s*e+(1-s)*(a*d+a*b*target+z))/denominator
    x = d-b*(inflation-target)
    # Prices relative to p_previous=0; common nominal shift leaves result unchanged.
    return {"Pi": inflation, "x": x, "preset_log_price": e,
            "reset_log_price": inflation+a*x+z,
            "kappa": (1-s)*a/s if s else None,
            "u": (1-s)*z/s if s else None}


def quantity(case):
    initial = case["initial"]
    m0, v0, y0 = values(initial, "M V Y")
    require(min(m0, v0, y0) > 0, "positive initial stocks/flows")
    p0 = m0*v0/y0
    nominal_net = number(case["loan_nominal_net"])
    require(nominal_net > -1, "positive nominal gross payoff")
    rows = []
    for row in case["next"]:
        m, v, y = values(row, "M V Y")
        require(min(m, v, y) > 0, "positive next stocks/flows")
        p = m*v/y
        inflation = p/p0-1
        rows.append({"id": row["id"], "P": p, "ordinary_inflation": inflation,
                     "approximate_inflation": (m/m0-1)+(v/v0-1)-(y/y0-1),
                     "loan_real_net": (1+nominal_net)/(1+inflation)-1})
    return {"P0": p0, "next": rows}


def uncertain_return(case):
    nominal = number(case["nominal_net"])
    require(nominal > -1, "positive nominal gross payoff")
    ps = probabilities(case["states"])
    rates = [number(row["ordinary_inflation"]) for row in case["states"]]
    require(all(rate > -1 for rate in rates), "positive price growth factors")
    mean = sum(p*rate for p, rate in zip(ps, rates))
    exact = sum(p*(1+nominal)/(1+rate) for p, rate in zip(ps, rates))
    return {"mean_ordinary_inflation": mean, "expected_real_gross": exact,
            "gross_using_mean_inflation": (1+nominal)/(1+mean)}


def adaptive(case):
    n = case["periods"]
    require(type(n) is int and 1 <= n <= 100, "periods must be integer in [1,100]")
    learning = number(case["learning"])
    require(0 <= learning <= 1, "learning must lie in [0,1]")
    current = dict(case)
    forecast = number(case["e"])
    path, log_price = [], F(0)
    for t in range(n):
        current["e"] = str(forecast)
        solved = pricing(current)
        log_price += solved["Pi"]
        path.append({"t": t, "e": forecast, "Pi": solved["Pi"], "x": solved["x"],
                     "log_price_from_initial": log_price})
        forecast += learning*(solved["Pi"]-forecast)
    s, a, b, target, d, z = values(case, "s a b anchor d z")
    rho = 1-learning*(1-s)*a*b/(s+(1-s)*a*b)
    # A unique adaptive forecast fixed point needs learning and nonpreset firms.
    fixed_e = target+d/b+z/(a*b) if learning and s < 1 else None
    return {"id": case["id"], "rho": rho, "unique_forecast_fixed_point": fixed_e,
            "path": path, "next_forecast": forecast,
            "finite_log_gap_sum": sum(row["x"] for row in path)}


def consistent(case):
    s, a, b, target = values(case, "s a b anchor")
    require(0 < s < 1 and a > 0 and b > 0, "forecast derivation requires interior s and a,b>0")
    ps = probabilities(case["states"])
    demand_mean = sum(p*number(row["d"]) for p, row in zip(ps, case["states"]))
    cost_mean = sum(p*number(row["z"]) for p, row in zip(ps, case["states"]))
    e = target+demand_mean/b+cost_mean/(a*b)
    rows = []
    for probability, state in zip(ps, case["states"]):
        full = {**case, **state, "e": str(e)}
        answer = pricing(full)
        rows.append({"probability": probability, "d": number(state["d"]),
                     "z": number(state["z"]), "Pi": answer["Pi"], "x": answer["x"],
                     "forecast_error": answer["Pi"]-e})
    return {"id": case["id"], "e": e, "states": rows,
            "expected_Pi": sum(x["probability"]*x["Pi"] for x in rows)}


def descriptive_slope(rows):
    mean_x = sum(x["x"] for x in rows)/len(rows)
    mean_pi = sum(x["Pi"] for x in rows)/len(rows)
    denominator = sum((x["x"]-mean_x)**2 for x in rows)
    return (sum((x["x"]-mean_x)*(x["Pi"]-mean_pi) for x in rows)/denominator
            if denominator else None)


def analyze(data):
    require(isinstance(data, dict) and data.get("schema") == "v06-c07-synthetic-v1", "unsupported schema")
    results = {}
    for group, method in (("pricing_cases", pricing), ("adaptive", adaptive), ("consistent_forecasts", consistent)):
        cases = data[group]
        require(isinstance(cases, list) and cases, "case group must be nonempty")
        labels = [x["id"] for x in cases]
        require(all(isinstance(x, str) and x for x in labels) and len(set(labels)) == len(labels),
                "nonempty unique case IDs required")
        results[group] = [{"id": case["id"], **method(case)} for case in cases]
    lookup = {row["id"]: row for row in results["pricing_cases"]}
    demand = [lookup[x] for x in ("demand_negative", "demand_positive")]
    supply = [lookup[x] for x in ("pricing_negative", "pricing_positive")]
    results.update(scope="Synthetic conditional calculations, not empirical estimates",
                   quantity=quantity(data["quantity"]), uncertain_return=uncertain_return(data["uncertain_return"]),
                   descriptive_slopes={"demand_pair": descriptive_slope(demand),
                                       "pricing_pair": descriptive_slope(supply),
                                       "equal_four_state_mixture": descriptive_slope(demand+supply)})
    return pack(results)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", nargs="?", type=Path, default=DEFAULT)
    args = parser.parse_args()
    try:
        result = analyze(json.loads(args.input.read_text(encoding="utf-8")))
    except (OSError, ValueError, TypeError, KeyError, ZeroDivisionError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
