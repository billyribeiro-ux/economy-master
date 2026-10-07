#!/usr/bin/env python3
"""Small exact-rational OLS teaching benchmark; standard library only.

Input coefficients are integers; the leading column must be an intercept.
Exact elimination is appropriate for these tiny examples, not large datasets.
All reads and terminal output occur in main(); importing has no side effects.
"""
from fractions import Fraction as F
import json
from pathlib import Path
import sys


def dot(a, b):
    if len(a) != len(b):
        raise ValueError("dot-product dimensions disagree")
    return sum((u * v for u, v in zip(a, b)), F(0))


def solve(matrix, rhs):
    """Solve a square exact system without constructing an inverse.

    A nonzero largest-magnitude pivot is selected, rows below are eliminated,
    and back substitution solves the triangular result. Inputs are copied.
    """
    size = len(matrix)
    if not size or len(rhs) != size or any(len(row) != size for row in matrix):
        raise ValueError("a nonempty square system is required")
    a = [[F(v) for v in row] + [F(rhs[i])] for i, row in enumerate(matrix)]
    for k in range(size):
        pivot = max(range(k, size), key=lambda i: abs(a[i][k]))
        if a[pivot][k] == 0:
            raise ValueError("rank-deficient design: coefficients are not unique")
        a[k], a[pivot] = a[pivot], a[k]
        for i in range(k + 1, size):
            factor = a[i][k] / a[k][k]
            for j in range(k, size + 1):
                a[i][j] -= factor * a[k][j]
    answer = [F(0)] * size
    for i in range(size - 1, -1, -1):
        answer[i] = (a[i][-1] - dot(a[i][i + 1:size], answer[i + 1:])) / a[i][i]
    return answer


def integer(value):
    return type(value) is int and abs(value) <= 1000000


def require_keys(obj, keys, label):
    if type(obj) is not dict or set(obj) != set(keys):
        raise ValueError(label + " has missing or unknown fields")


def validate_case(case):
    require_keys(case, ["id", "predictor_names", "predictor_units", "outcome_name",
                        "outcome_unit", "design", "outcomes", "evaluation_design",
                        "evaluation_outcomes", "prediction_design"], "case")
    for name in ["id", "outcome_name", "outcome_unit"]:
        if type(case[name]) is not str or not case[name].strip():
            raise ValueError(name + " must be nonempty text")
    names = case["predictor_names"]
    units = case["predictor_units"]
    if type(names) is not list or not 1 <= len(names) <= 8:
        raise ValueError("require 1 through 8 named predictors")
    if any(type(v) is not str or not v.strip() for v in names) or len(set(names)) != len(names):
        raise ValueError("predictor names must be distinct nonempty text")
    if names[0] != "intercept":
        raise ValueError("the leading predictor must be named intercept")
    if type(units) is not list or len(units) != len(names) or any(
            type(v) is not str or not v.strip() for v in units) or units[0] != "1":
        raise ValueError("predictor units must match, with intercept unit 1")
    for field in ["design", "evaluation_design", "prediction_design"]:
        rows = case[field]
        minimum = 1 if field == "design" else 0
        if type(rows) is not list or not minimum <= len(rows) <= 32:
            raise ValueError(field + " has an unsupported row count")
        for row in rows:
            if type(row) is not list or len(row) != len(names) or any(not integer(v) for v in row):
                raise ValueError(field + " requires complete bounded integer rows")
            if row[0] != 1:
                raise ValueError("the leading column must contain ones")
    for field, design in [("outcomes", "design"), ("evaluation_outcomes", "evaluation_design")]:
        vals = case[field]
        if type(vals) is not list or len(vals) != len(case[design]) or any(not integer(v) for v in vals):
            raise ValueError(field + " requires one bounded integer per row")
    if len(case["design"]) < len(names):
        raise ValueError("fewer training rows than coefficients cannot have full column rank")
    return case


def fit(design, outcomes):
    """Return exact diagnostics for a full-column-rank design with intercept."""
    if (type(design) is not list or not 1 <= len(design) <= 32
            or type(outcomes) is not list or len(outcomes) != len(design)
            or any(not integer(v) for v in outcomes)):
        raise ValueError("invalid bounded integer training data")
    p = len(design[0]) if type(design[0]) is list else 0
    if not 1 <= p <= 8 or p > len(design):
        raise ValueError("unsupported design dimensions")
    if any(type(row) is not list or len(row) != p or row[0] != 1
           or any(not integer(v) for v in row) for row in design):
        raise ValueError("require rectangular integer rows with a leading intercept")
    x = [[F(v) for v in row] for row in design]
    y = [F(v) for v in outcomes]
    cols = [list(col) for col in zip(*x)]
    gram = [[dot(a, b) for b in cols] for a in cols]
    rhs = [dot(col, y) for col in cols]
    beta = solve(gram, rhs)
    fitted = [dot(row, beta) for row in x]
    residuals = [actual - pred for actual, pred in zip(y, fitted)]
    mean = sum(y) / len(y)
    sse = dot(residuals, residuals)
    sst = sum((value - mean) ** 2 for value in y)
    ssr = sum((value - mean) ** 2 for value in fitted)
    leverage = [dot(row, solve(gram, row)) for row in x]
    return {"coefficients": beta, "fitted": fitted, "residuals": residuals,
            "sse": sse, "sst": sst, "ssr": ssr,
            "r_squared": None if sst == 0 else 1 - sse / sst,
            "training_mse": sse / len(y), "leverage": leverage,
            "normal_equation_residual": [dot(col, residuals) for col in cols]}


def encode(value):
    if isinstance(value, F):
        return str(value)
    if isinstance(value, list):
        return [encode(item) for item in value]
    if isinstance(value, dict):
        return {key: encode(item) for key, item in value.items()}
    return value


def make_report(case):
    validate_case(case)
    result = fit(case["design"], case["outcomes"])
    beta = result["coefficients"]
    evaluation = [dot(row, beta) for row in case["evaluation_design"]]
    errors = [F(actual) - predicted for actual, predicted in zip(case["evaluation_outcomes"], evaluation)]
    result.update({"case_id": case["id"], "predictor_names": case["predictor_names"],
                   "predictor_units": case["predictor_units"], "outcome_unit": case["outcome_unit"],
                   "evaluation_predictions": evaluation, "evaluation_errors": errors,
                   "evaluation_mse": dot(errors, errors) / len(errors) if errors else None,
                   "predictions": [dot(row, beta) for row in case["prediction_design"]]})
    return encode(result)


def unique_fields(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON field: " + key)
        result[key] = value
    return result


def reject_constant(value):
    raise ValueError("nonfinite JSON constant: " + value)


def load_cases(path):
    with Path(path).open(encoding="utf-8") as handle:
        data = json.load(handle, object_pairs_hook=unique_fields, parse_constant=reject_constant)
    require_keys(data, ["schema_version", "provenance", "cases"], "document")
    if type(data["schema_version"]) is not int or data["schema_version"] != 1:
        raise ValueError("schema_version must be integer 1")
    require_keys(data["provenance"], ["kind", "created", "edition_boundary", "description"], "provenance")
    if data["provenance"]["kind"] != "synthetic":
        raise ValueError("this laboratory accepts explicitly synthetic teaching inputs")
    for value in data["provenance"].values():
        if type(value) is not str or not value.strip():
            raise ValueError("provenance fields must be nonempty text")
    cases = data["cases"]
    if type(cases) is not list or not 1 <= len(cases) <= 8:
        raise ValueError("require 1 through 8 cases")
    for case in cases:
        validate_case(case)
    if len({case["id"] for case in cases}) != len(cases):
        raise ValueError("case IDs must be unique")
    return cases


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if len(args) > 1:
        print("usage: python3 v04-c07-regression.py [case-file.json]", file=sys.stderr)
        return 2
    path = Path(args[0]) if args else Path(__file__).resolve().with_name("v04-c07-cases.json")
    try:
        reports = [make_report(case) for case in load_cases(path)]
    except (ValueError, OSError) as error:
        print("regression input error: " + str(error), file=sys.stderr)
        return 2
    print(json.dumps({"arithmetic": "exact rational", "data_kind": "synthetic", "cases": reports}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
