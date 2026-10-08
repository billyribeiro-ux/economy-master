"""Exact small forecasting laboratory. Standard library; no network or writes.

Period t labels are released at the end of 'released'. A forecast made just
after origin t may use only records whose period and release are <= t.
The final test is a prespecified updating procedure, not a frozen fitted vector.
"""
from fractions import Fraction as F
import json
from pathlib import Path
import sys


METHODS = ("naive", "mean", "drift")


def keys(obj, fields, name):
    if type(obj) is not dict or set(obj) != set(fields):
        raise ValueError(name + " must have exactly the documented fields")


def integer(value, low, high, name):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(name + " must be a bounded integer, not a boolean")


def validate(case):
    keys(case, ("schema_version", "provenance", "unit", "initial_training_end",
                "validation_end", "methods", "selection_loss", "records"), "case")
    integer(case["schema_version"], 1, 1, "schema_version")
    if type(case["provenance"]) is not str or not case["provenance"].strip():
        raise ValueError("provenance must be nonblank text")
    if case["unit"] != "units per month" or case["selection_loss"] != "mse":
        raise ValueError("this laboratory requires monthly demand units and MSE selection")
    if case["methods"] != list(METHODS):
        raise ValueError("methods must preserve the documented candidates and tie order")
    rows = case["records"]
    if type(rows) is not list or not 4 <= len(rows) <= 120:
        raise ValueError("supply 4 through 120 consecutive monthly observations")
    n = len(rows)
    integer(case["initial_training_end"], 2, n - 2, "initial training end")
    integer(case["validation_end"], case["initial_training_end"] + 1, n - 1, "validation end")
    seen = set()
    for row in rows:
        keys(row, ("period", "released", "value"), "record")
        integer(row["period"], 1, n, "period")
        integer(row["released"], row["period"], n + 12, "release period")
        integer(row["value"], 0, 1000000, "demand")
        if row["period"] in seen:
            raise ValueError("duplicate period")
        seen.add(row["period"])
    if seen != set(range(1, n + 1)):
        raise ValueError("calendar periods must be consecutive")
    return case


def history_as_of(rows, origin):
    return sorted((row["period"], row["value"]) for row in rows
                  if row["period"] <= origin and row["released"] <= origin)


def forecast(history, target, method):
    """Pure formula for a sorted, unique, valid history; no target outcome read."""
    if method not in METHODS or len(history) < 2:
        raise ValueError("forecast needs a supported method and two released records")
    first_t, first_y = history[0]
    last_t, last_y = history[-1]
    if target <= last_t or last_t <= first_t:
        raise ValueError("forecast target must follow the observed time span")
    if method == "mean":
        return F(sum(y for _, y in history), len(history))
    if method == "naive":
        return F(last_y)
    # If the latest label is delayed, target-last_t exceeds the nominal horizon.
    return F(last_y) + F(target - last_t) * F(last_y - first_y, last_t - first_t)


def summary(errors):
    if not errors:
        raise ValueError("loss needs at least one scored forecast")
    return {"n": len(errors), "mae": sum(abs(e) for e in errors) / len(errors),
            "mse": sum(e * e for e in errors) / len(errors),
            "mean_error": sum(errors) / len(errors)}


def evaluate(case, targets, scored_as_of, fixed_origin=None):
    rows = case["records"]
    lookup = {row["period"]: row for row in rows}
    reports = {m: {"forecasts": []} for m in METHODS}
    for target in targets:
        row = lookup[target]
        if row["released"] > scored_as_of:
            raise ValueError("a scoring/selection label was not released by the declared score date")
        origin = target - 1 if fixed_origin is None else fixed_origin
        if target <= origin:
            raise ValueError("target must follow the forecast origin")
        history = history_as_of(rows, origin)
        for method in METHODS:
            prediction = forecast(history, target, method)
            reports[method]["forecasts"].append({
                "origin": origin, "target": target,
                "training_periods": [t for t, _ in history],
                "prediction": prediction, "actual": F(row["value"]),
                "error": F(row["value"]) - prediction,
            })
    for report in reports.values():
        report.update(summary([row["error"] for row in report["forecasts"]]))
    return reports


def build_report(case):
    validate(case)
    boundary = case["validation_end"]
    validation_targets = range(case["initial_training_end"] + 1, boundary + 1)
    validation = evaluate(case, validation_targets, boundary)
    # Candidate order resolves ties before any final-test loss is computed.
    selected = min(METHODS, key=lambda m: validation[m]["mse"])
    final_as_of = max(row["released"] for row in case["records"])
    targets = range(boundary + 1, len(case["records"]) + 1)
    test = evaluate(case, targets, final_as_of)
    fixed = evaluate(case, targets, final_as_of, fixed_origin=boundary)
    return {"unit": case["unit"], "provenance": case["provenance"],
            "validation_scored_as_of": boundary, "test_scored_as_of": final_as_of,
            "selection_rule": "minimum validation MSE; tie order naive, mean, drift",
            "selected_method": selected, "validation": validation,
            "test_updating": test, "test_fixed_origin": fixed,
            "test_role": "Prespecified final comparison; no test-based method reselection."}


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON field: " + key)
        result[key] = value
    return result


def reject_constant(value):
    raise ValueError("nonfinite JSON value: " + value)


def load_case(path):
    with Path(path).open(encoding="utf-8") as handle:
        case = json.load(handle, object_pairs_hook=unique_object, parse_constant=reject_constant)
    return validate(case)


def encode(value):
    if isinstance(value, F):
        return {"exact": str(value), "decimal": float(value)}
    raise TypeError("unsupported output type")


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if len(args) > 1:
        print("Usage: python3 v04-c09-validation.py [case.json]", file=sys.stderr)
        return 2
    path = Path(args[0]) if args else Path(__file__).resolve().with_name("v04-c09-case.json")
    try:
        report = build_report(load_case(path))
    except (ValueError, TypeError, OSError, UnicodeError) as exc:
        print("Cannot evaluate forecast case: " + str(exc), file=sys.stderr)
        return 2
    print(json.dumps(report, default=encode, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
