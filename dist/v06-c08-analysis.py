#!/usr/bin/env python3
"""Exact, bounded finite New Keynesian lab; standard library, no network.

All shocks are known at date 0. Fractions preserve the supplied JSON decimal
values exactly. This solves a maintained model, not estimated economic data.
"""
from fractions import Fraction as Q
import json
import math
from pathlib import Path
import sys


def number(value, name, low=-100, high=100):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(name + " must be a JSON number, not a boolean")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(name + " must be finite")
    if not low <= value <= high:
        raise ValueError(name + " outside bounded lab domain")
    return Q(str(value))


def keys(obj, expected, name):
    if not isinstance(obj, dict) or set(obj) != set(expected):
        raise ValueError(name + " has missing or unexpected fields")


def validate(data):
    keys(data, ("description", "parameters", "cases"), "input")
    if not isinstance(data["description"], str):
        raise ValueError("description must be text")
    p = data["parameters"]
    keys(p, ("sigma", "beta", "kappa", "phi_pi", "phi_x"), "parameters")
    par = {k: number(v, k, 0, 10) for k, v in p.items()}
    if par["sigma"] <= 0 or par["kappa"] <= 0 or par["beta"] > 1:
        raise ValueError("require sigma,kappa > 0 and beta in [0,1]")
    cases = data["cases"]
    if not isinstance(cases, list) or not 1 <= len(cases) <= 20:
        raise ValueError("require 1 to 20 cases")
    checked, seen = [], set()
    for case in cases:
        keys(case, ("name", "n", "u", "v", "terminal_x", "terminal_pi"), "case")
        name = case["name"]
        if not isinstance(name, str) or not name or len(name) > 80 or name in seen:
            raise ValueError("case names must be unique nonempty text of at most 80 characters")
        seen.add(name)
        paths = {}
        for field in ("n", "u", "v"):
            path = case[field]
            if not isinstance(path, list) or not 1 <= len(path) <= 6:
                raise ValueError("each shock path must contain 1 to 6 dates")
            paths[field] = [number(v, field, -20, 20) for v in path]
        if len({len(path) for path in paths.values()}) != 1:
            raise ValueError("shock paths must have the same length")
        checked.append(dict(name=name, **paths,
                            terminal_x=number(case["terminal_x"], "terminal_x", -20, 20),
                            terminal_pi=number(case["terminal_pi"], "terminal_pi", -20, 20)))
    return par, checked


def solve_case(par, case):
    """Validated inputs, exact backward solution; equality uses the free branch."""
    sigma, beta, kappa = par["sigma"], par["beta"], par["kappa"]
    phi, psi = par["phi_pi"], par["phi_x"]
    floor = Q(-2)
    next_x, next_pi = case["terminal_x"], case["terminal_pi"]
    denominator = 1 + sigma*(phi*kappa + psi)
    rows = []
    for t in reversed(range(len(case["n"]))):
        n, u, v = case["n"][t], case["u"][t], case["v"][t]
        intercept = beta*next_pi + u
        x = (next_x + sigma*(next_pi+n-v-phi*intercept))/denominator
        pi = intercept + kappa*x
        requested = phi*pi + psi*x + v
        j = requested
        limited = requested < floor
        if limited:
            j = floor
            x = next_x + sigma*(next_pi+n-j)
            pi = intercept + kappa*x
            requested = phi*pi + psi*x + v
        residuals = {"demand": x-next_x+sigma*(j-next_pi-n),
                     "inflation": pi-beta*next_pi-kappa*x-u,
                     "policy": j-max(floor, requested)}
        if any(residuals.values()):
            raise ArithmeticError("equilibrium equations did not reconcile")
        if j < floor or (limited and requested > floor):
            raise ArithmeticError("inconsistent floor branch")
        rows.append({"date": t, "x": str(x), "pi": str(pi), "j": str(j),
                     "nominal_log_rate": str(2+j), "requested_j": str(requested),
                     "strictly_floor_limited": limited,
                     "residuals": {k: str(v) for k, v in residuals.items()}})
        next_x, next_pi = x, pi
    return {"name": case["name"], "rows": list(reversed(rows))}


def analyze(data):
    parameters, cases = validate(data)
    return {"model": "finite announced-path NK; zero log-inflation target; nominal baseline 2",
            "units": "x, pi and rates in log points; exact fractions encoded as strings",
            "boundary": "supplied terminal forecasts; nominal rate floor 0, j floor -2",
            "cases": [solve_case(parameters, case) for case in cases]}


def main():
    if len(sys.argv) > 2:
        raise ValueError("usage: python3 v06-c08-analysis.py [inputs.json]")
    path = Path(sys.argv[1]) if len(sys.argv) == 2 else Path(__file__).with_name("v06-c08-inputs.json")
    with path.open(encoding="utf-8") as handle:
        result = analyze(json.load(handle))
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, ArithmeticError) as error:
        print(json.dumps({"status": "error", "message": str(error)}, allow_nan=False), file=sys.stderr)
        sys.exit(1)
