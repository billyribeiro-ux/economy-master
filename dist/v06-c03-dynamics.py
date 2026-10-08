"""Exact, offline v06-c03 model calculations. Standard library only.

All inputs are synthetic. This evaluates research candidates, not a grid proof
of a continuous optimum; the chapter supplies that proof. No file is mutated.
"""
from fractions import Fraction as F
from itertools import product
import argparse
import json
from pathlib import Path
import re


DEFAULT = Path(__file__).with_name("v06-c03-models.json")


def rational(value):
    if not isinstance(value, str) or not re.fullmatch(r"-?\d+(?:/[1-9]\d*)?", value):
        raise ValueError("quantities must be integer or rational strings")
    return F(value)


def numbers(case, keys):
    return [rational(case[key]) for key in keys.split()]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def periods(case):
    n = case["periods"]
    require(type(n) is int and 0 <= n <= 100, "periods must be an integer in [0,100]")
    return n


def pack(value):
    if isinstance(value, F):
        return str(value)
    if isinstance(value, list):
        return [pack(x) for x in value]
    if isinstance(value, dict):
        return {key: pack(x) for key, x in value.items()}
    return value


def research(case):
    a, eta, d, theta = numbers(case, "A0 eta d theta")
    require(a > 0 and eta > 0 and 0 < d <= 1 and 0 <= theta <= 1,
            "invalid research domain")
    choices = case["candidates"]
    require(isinstance(choices, list) and len(choices) > 0, "candidate list must be nonempty")
    rs = [rational(x) for x in choices]
    require(all(0 <= r <= 1 for r in rs) and len(set(rs)) == len(rs),
            "research candidates must be distinct shares in [0,1]")
    rows = []
    for r in rs:
        y0 = a*(1-r)
        increment = a*eta*r/(1+r)
        y1 = a+increment
        rows.append({"r": r, "Y0": y0, "Y1": y1, "J": y0+d*y1,
                     "private_incremental_payoff": -a*r+d*theta*increment,
                     "uncaptured_future_increment": (1-theta)*increment})
    social = max(row["J"] for row in rows)
    private = max(row["private_incremental_payoff"] for row in rows)
    return {"id": case["id"], "candidates": rows,
            "best_supplied_social": [x["r"] for x in rows if x["J"] == social],
            "best_supplied_private": [x["r"] for x in rows if x["private_incremental_payoff"] == private]}


def innovation(case):
    a, eta, h, r = numbers(case, "A0 eta h r")
    require(a > 0 and eta > 0 and h >= 0 and 0 <= r <= 1, "invalid innovation domain")
    growth = eta*r*h/(1+r*h)
    path = [a]
    for _ in range(periods(case)):
        a += a*growth
        path.append(a)
    return {"growth": growth, "A": path}


def schooling(case):
    h, delta, chi, e = numbers(case, "h0 delta chi e")
    require(h >= 0 and 0 <= delta <= 1 and chi > 0 and 0 <= e <= 1,
            "invalid schooling domain")
    path = [h]
    for _ in range(periods(case)):
        h = (1-delta)*h+chi*e
        path.append(h)
    return {"id": case["id"], "h": path,
            "unique_fixed_point": chi*e/delta if delta else None,
            "boundary": "positive depreciation" if delta else
                        ("linear growth, no finite fixed point" if e else "every h is fixed")}


def diffusion(case):
    frontier, a, h, kappa, g = numbers(case, "F0 A0 h kappa g")
    require(frontier > 0 and 0 <= a <= frontier and h >= 0 and kappa > 0 and g >= 0,
            "invalid diffusion domain")
    absorption = h/(kappa+h)
    rows = [{"period": 0, "F": frontier, "A": a, "relative_A": a/frontier}]
    for t in range(1, periods(case)+1):
        a += absorption*(frontier-a)  # Uses the old frontier, before its update.
        frontier *= 1+g
        rows.append({"period": t, "F": frontier, "A": a, "relative_A": a/frontier})
    return {"id": case["id"], "lambda": absorption,
            "rho": (1-absorption)/(1+g),
            "unique_relative_fixed_point": absorption/(absorption+g) if absorption+g else None,
            "path": rows}


def identification(case):
    pi, b1, b2, gamma, vcoef = numbers(case, "pi beta1 beta2 gamma v_coefficient")
    rows = []
    for z, v in product((-1, 1), repeat=2):
        r = pi*z+v
        rows.append({"probability": F(1, 4), "Z": z, "V": v, "R": r,
                     "y1": b1*r, "y2": b2*r+gamma*z+vcoef*v,
                     "u2": gamma*z+vcoef*v})
    def mean(key):
        return sum(x["probability"]*x[key] for x in rows)
    def cov(left, right):
        return sum(x["probability"]*(x[left]-mean(left))*(x[right]-mean(right)) for x in rows)
    zr, zy1, zy2 = cov("Z", "R"), cov("Z", "y1"), cov("Z", "y2")
    return {"rows": rows, "cov_Z_R": zr, "cov_Z_y1": zy1, "cov_Z_y2": zy2,
            "cov_Z_u2": cov("Z", "u2"),
            "iv1": zy1/zr if zr else None, "iv2": zy2/zr if zr else None,
            "same_observables": all(row["y1"] == row["y2"] for row in rows),
            "intervention_effect1": b1, "intervention_effect2": b2}


def analyze(data):
    require(isinstance(data, dict) and data.get("schema") == "v06-c03-original-models-v1",
            "unsupported input schema")
    for group in ("research", "schooling", "diffusion"):
        require(isinstance(data[group], list) and data[group], "empty case group")
        labels = [x["id"] for x in data[group]]
        require(all(isinstance(x, str) and x for x in labels) and len(set(labels)) == len(labels),
                "case IDs must be nonempty and unique within group")
    return pack({"scope": "Exact synthetic model calculations; supplied research candidates only",
                 "research": [research(x) for x in data["research"]],
                 "innovation_path": innovation(data["innovation_path"]),
                 "schooling": [schooling(x) for x in data["schooling"]],
                 "diffusion": [diffusion(x) for x in data["diffusion"]],
                 "iv": identification(data["iv"])})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, nargs="?", default=DEFAULT)
    args = parser.parse_args()
    try:
        answer = analyze(json.loads(args.input.read_text(encoding="utf-8")))
    except (OSError, ValueError, TypeError, KeyError, ZeroDivisionError) as exc:
        parser.error(str(exc))
    print(json.dumps(answer, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
