#!/usr/bin/env python3
"""Exact finite term-structure teaching model; no network or third-party package."""
import argparse
from fractions import Fraction as F
from itertools import product
import json
from pathlib import Path
import re

SCHEMA = "v10-c03-finite-tree-v1"
CONTRACT = {
    "dates_years": [0, 1, 2, 3],
    "currency": "CU",
    "payment_timing": "end-period",
    "trading": "frictionless signed positions; equal node borrowing and lending rates",
    "outside_storage": "no external costless cash storage",
}


def keys(obj, expected, label):
    if not isinstance(obj, dict) or set(obj) != set(expected):
        raise ValueError(label + ": exact fields required")


def rational(x, label):
    if type(x) is int:
        value = F(x)
    elif isinstance(x, str) and len(x) <= 80 and re.fullmatch(r"-?(?:0|[1-9][0-9]*)(?:/[1-9][0-9]*|\.[0-9]+)?", x):
        value = F(x)
    else:
        raise ValueError(label + ": use an integer or exact rational/decimal string")
    if abs(value) > 10**6 or value.denominator > 10**12:
        raise ValueError(label + ": input magnitude or denominator exceeds the teaching bound")
    return value


def curve(values, label):
    if not isinstance(values, list) or len(values) != 4:
        raise ValueError(label + ": four discount points required")
    ds = [rational(x, label) for x in values]
    if ds[0] != 1 or any(x <= 0 for x in ds):
        raise ValueError(label + ": D0=1 and all discounts positive required")
    return ds


def probabilities(rows, label):
    if not isinstance(rows, list) or len(rows) != 3:
        raise ValueError(label + ": three triangular rows required")
    result = []
    for t, row in enumerate(rows):
        if not isinstance(row, list) or len(row) != t + 1:
            raise ValueError(label + ": row t must have t+1 entries")
        values = [rational(x, label) for x in row]
        if any(not 0 < x < 1 for x in values):
            raise ValueError(label + ": strict full-support probabilities required")
        result.append(values)
    return result


def name(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-z][a-zA-Z0-9_]{0,31}", value):
        raise ValueError("short unique scenario names required")
    return value


def parse(data):
    keys(data, {"schema", "contract", "discount_curve", "pricing_up", "physical_up", "models", "cashflows", "claim", "curve_scenarios", "mean_reversion"}, "input")
    if data["schema"] != SCHEMA or data["contract"] != CONTRACT:
        raise ValueError("fixed annual timing, units and trading contract required")
    if any(type(t) is not int for t in data["contract"]["dates_years"]):
        raise ValueError("dates must be integers")
    ds = curve(data["discount_curve"], "discount_curve")
    q = probabilities(data["pricing_up"], "pricing_up")
    p = probabilities(data["physical_up"], "physical_up")
    if not isinstance(data["models"], list) or not 1 <= len(data["models"]) <= 8:
        raise ValueError("one through eight model specifications required")
    models = []
    for item in data["models"]:
        keys(item, {"name", "dispersion"}, "model")
        s = rational(item["dispersion"], "dispersion")
        if not 0 <= s < F(1, 2):
            raise ValueError("0 <= dispersion < 1/2 keeps all finite shapes positive")
        models.append((name(item["name"]), s))
    if models[0][0] != "base" or len(set(n for n, _ in models)) != len(models):
        raise ValueError("first model must be base; model names must be unique")
    if not isinstance(data["cashflows"], list) or len(data["cashflows"]) != 3:
        raise ValueError("cashflows: three dated payments required")
    cashflows = [rational(x, "cashflow") for x in data["cashflows"]]
    if any(x < 0 for x in cashflows) or not any(cashflows):
        raise ValueError("nonnegative cashflows, at least one positive, required")
    claim = data["claim"]
    keys(claim, {"payment_time", "bond_maturity", "face", "strike"}, "claim")
    if type(claim["payment_time"]) is not int or type(claim["bond_maturity"]) is not int or claim["payment_time"] != 1 or claim["bond_maturity"] != 2:
        raise ValueError("this claim pays at date1 on the date2 zero; dates are fixed")
    face, strike = [rational(claim[k], k) for k in ("face", "strike")]
    if face <= 0 or strike < 0:
        raise ValueError("claim face must be positive and strike nonnegative")
    if not isinstance(data["curve_scenarios"], list) or len(data["curve_scenarios"]) > 8:
        raise ValueError("at most eight curve scenarios allowed")
    scenarios = []
    for item in data["curve_scenarios"]:
        keys(item, {"name", "discount_curve"}, "curve scenario")
        scenarios.append((name(item["name"]), curve(item["discount_curve"], "scenario curve")))
    if len(set(n for n, _ in scenarios)) != len(scenarios):
        raise ValueError("curve scenario names must be unique")
    ar = data["mean_reversion"]
    keys(ar, {"initial", "level", "phi", "innovation", "steps"}, "mean_reversion")
    ar = {k: (v if k == "steps" else rational(v, "mean_reversion " + k)) for k, v in ar.items()}
    if type(ar["steps"]) is not int or not 1 <= ar["steps"] <= 6:
        raise ValueError("mean-reversion horizon must be an integer from1 through6")
    if not 0 <= ar["phi"] < 1 or ar["innovation"] < 0 or ar["initial"] <= -1:
        raise ValueError("mean reversion requires 0<=phi<1, sigma>=0 and initial gross rate>0")
    return ds, q, p, models, cashflows, face, strike, scenarios, ar


def calibrate(ds, s, q):
    """Forward Arrow weights; each level is uniquely fitted given shape and Q."""
    arrows, discounts, levels = [[F(1)]], [], []
    for t in range(3):
        shape = [1 + s * (t - 2 * j) for j in range(t + 1)]
        level = ds[t + 1] / sum(a * h for a, h in zip(arrows[t], shape))
        d = [level * h for h in shape]
        nxt = [F(0)] * (t + 2)
        for j, (a, node_d, up) in enumerate(zip(arrows[t], d, q[t])):
            nxt[j] += a * node_d * (1 - up)
            nxt[j + 1] += a * node_d * up
        levels.append(level)
        discounts.append(d)
        arrows.append(nxt)
    return levels, discounts, arrows


def backward(discounts, q, maturity, terminal):
    values = [None] * (maturity + 1)
    values[maturity] = list(terminal)
    for t in reversed(range(maturity)):
        values[t] = [discounts[t][j] * ((1 - q[t][j]) * values[t + 1][j] + q[t][j] * values[t + 1][j + 1]) for j in range(t + 1)]
    return values


def node_probabilities(rows):
    mass = [[F(1)]]
    for t in range(3):
        nxt = [F(0)] * (t + 2)
        for j, prob in enumerate(mass[t]):
            nxt[j] += prob * (1 - rows[t][j])
            nxt[j + 1] += prob * rows[t][j]
        mass.append(nxt)
    return mass


def path_records(discounts, q, p):
    rows = []
    for bits in product((0, 1), repeat=3):
        j, qp, pp, df = 0, F(1), F(1), F(1)
        bank_history = [F(1)]
        for t, bit in enumerate(bits):
            qp *= q[t][j] if bit else 1 - q[t][j]
            pp *= p[t][j] if bit else 1 - p[t][j]
            df *= discounts[t][j]
            bank_history.append(1 / df)
            j += bit
        arrow = qp * df
        rows.append({"path": "".join("H" if b else "L" for b in bits), "terminal_node": j,
                     "Q_probability": qp, "P_probability": pp, "discount_product": df,
                     "bank_history": bank_history, "state_price": arrow, "P_sdf": arrow / pp})
    return rows


def model(ds, s, q, p, cashflows, face, strike):
    levels, discounts, arrows = calibrate(ds, s, q)
    zeros = {str(T): backward(discounts, q, T, [F(1)] * (T + 1)) for T in range(1, 4)}
    coupon = [[F(0)] * (t + 1) for t in range(4)]
    for t in reversed(range(3)):
        coupon[t] = [discounts[t][j] * (cashflows[t] + (1 - q[t][j]) * coupon[t + 1][j] + q[t][j] * coupon[t + 1][j + 1]) for j in range(t + 1)]
    successor = zeros["2"][1]
    pay = [max(face * value - strike, F(0)) for value in successor]
    claim_value = discounts[0][0] * ((1 - q[0][0]) * pay[0] + q[0][0] * pay[1])
    if successor[0] == successor[1]:
        if pay[0] != pay[1]:
            raise ValueError("degenerate bond cannot replicate differing branch claims")
        beta, cash = F(0), claim_value
        rank = "redundant bond; bank-only replica chosen"
    else:
        beta = (pay[0] - pay[1]) / (successor[0] - successor[1])
        cash = discounts[0][0] * (pay[0] - beta * successor[0])
        rank = "two distinct successor bond values"
    replica = [beta * price + cash / discounts[0][0] for price in successor]
    premiums = []
    for t in range(2):
        T = t + 2
        for j in range(t + 1):
            price = zeros[str(T)][t][j]
            gross = [zeros[str(T)][t + 1][j + b] / price for b in (0, 1)]
            up = p[t][j]
            expected = (1 - up) * gross[0] + up * gross[1]
            d = discounts[t][j]
            local_m = [d * (1 - q[t][j]) / (1 - up), d * q[t][j] / up]
            covariance = (1 - up) * local_m[0] * gross[0] + up * local_m[1] * gross[1] - d * expected
            premiums.append({"time": t, "node": j, "bond_maturity": T, "bond_price": price,
                             "branch_gross_returns": gross, "physical_expected_simple_return": expected - 1,
                             "risk_free_simple_rate": 1 / d - 1, "expected_excess_return": expected - 1 / d,
                             "local_P_sdf": local_m, "sdf_return_covariance": covariance})
    future_r = [1 / x - 1 for x in discounts[1]]
    expected_q = (1 - q[0][0]) * future_r[0] + q[0][0] * future_r[1]
    expected_p = (1 - p[0][0]) * future_r[0] + p[0][0] * future_r[1]
    forward = ds[1] / ds[2] - 1
    return {"dispersion": s, "levels": levels, "node_discounts": discounts,
            "short_rates": [[1 / x - 1 for x in row] for row in discounts],
            "arrow_weights": arrows, "discount_sums": [sum(row) for row in arrows],
            "Q_node_probabilities": node_probabilities(q), "P_node_probabilities": node_probabilities(p),
            "zero_prices": zeros, "coupon_ex_payment_values": coupon,
            "coupon_curve_price": sum(c * d for c, d in zip(cashflows, ds[1:])),
            "claim": {"branch_payoffs": pay, "price": claim_value, "hedge_units_face1_zero2": beta,
                      "hedge_cash_at0": cash, "hedge_initial_cost": beta * ds[2] + cash,
                      "hedge_branch_payoffs": replica, "hedge_rank": rank},
            "forward_vs_expectations": {"forward_1_2": forward, "Q_expected_short1": expected_q,
                                        "P_expected_short1": expected_p, "forward_minus_Q": forward - expected_q,
                                        "Q_minus_P": expected_q - expected_p, "forward_minus_P": forward - expected_p},
            "holding_premiums": premiums, "terminal_paths": path_records(discounts, q, p)}


def mean_reversion(ar):
    rows = []
    for bits in product((-1, 1), repeat=ar["steps"]):
        value = ar["initial"]
        history = [value]
        for shock in bits:
            value = ar["level"] + ar["phi"] * (value - ar["level"]) + ar["innovation"] * shock
            if value <= -1:
                raise ValueError("a mean-reversion support path has nonpositive gross rate")
            history.append(value)
        rows.append({"shocks": list(bits), "rates": history})
    mean = sum(row["rates"][-1] for row in rows) / len(rows)
    variance = sum((row["rates"][-1] - mean) ** 2 for row in rows) / len(rows)
    analytic_mean = ar["level"] + ar["phi"] ** ar["steps"] * (ar["initial"] - ar["level"])
    analytic_variance = ar["innovation"] ** 2 * sum(ar["phi"] ** (2 * k) for k in range(ar["steps"]))
    return {"contract": "separate physical model; independent equiprobable +/- innovations; not curve calibrated",
            "terminal_mean": mean, "terminal_variance": variance,
            "analytic_mean": analytic_mean, "analytic_variance": analytic_variance, "paths": rows}


def encode(value):
    if isinstance(value, F):
        return str(value)
    if isinstance(value, dict):
        return {k: encode(v) for k, v in value.items()}
    if isinstance(value, list):
        return [encode(v) for v in value]
    return value


def run(data):
    """Validate one small contract, return a fresh strict-JSON object, print nothing."""
    ds, q, p, specs, cf, face, strike, scenarios, ar = parse(data)
    models = {n: model(ds, s, q, p, cf, face, strike) for n, s in specs}
    base = models["base"]
    h = base["claim"]
    risk = {}
    for n, other in models.items():
        values = [h["hedge_units_face1_zero2"] * d + h["hedge_cash_at0"] / other["node_discounts"][0][0] for d in other["zero_prices"]["2"][1]]
        errors = [value - pay for value, pay in zip(values, other["claim"]["branch_payoffs"])]
        risk[n] = {"frozen_base_hedge_payoffs": values, "claim_payoffs": other["claim"]["branch_payoffs"],
                   "branch_errors": errors, "priced_error": ds[1] * ((1 - q[0][0]) * errors[0] + q[0][0] * errors[1]),
                   "base_price_minus_model_price": h["price"] - other["claim"]["price"]}
    bumps = {}
    for n, altered in scenarios:
        m = model(altered, specs[0][1], q, p, cf, face, strike)
        bumps[n] = {"discount_curve": altered, "node_discounts": m["node_discounts"],
                    "discount_sums": m["discount_sums"], "coupon_price": m["coupon_curve_price"],
                    "coupon_change": m["coupon_curve_price"] - base["coupon_curve_price"],
                    "claim_price": m["claim"]["price"], "claim_change": m["claim"]["price"] - h["price"]}
    return encode({"schema": SCHEMA, "contract": CONTRACT, "models": models,
                   "frozen_base_hedge_model_risk": risk, "curve_scenarios": bumps,
                   "mean_reversion": mean_reversion(ar)})


def load_json(path):
    def pairs(items):
        obj = {}
        for k, v in items:
            if k in obj:
                raise ValueError("duplicate JSON field: " + k)
            obj[k] = v
        return obj
    def nonfinite(value):
        raise ValueError("nonfinite JSON token: " + value)
    return json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=pairs, parse_constant=nonfinite)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path(__file__).with_name("v10-c03-inputs.json"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        output = json.dumps(run(load_json(args.input)), indent=2, allow_nan=False) + "\n"
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    if args.output:
        args.output.write_text(output, encoding="utf-8")
    else:
        print(output, end="")


if __name__ == "__main__":
    main()
