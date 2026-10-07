"""Exact, finite identification demonstrations using only Python's standard library.

All inputs are synthetic mechanisms, not observed economic data. Potential
outcomes are used for separately labeled truth checks, never for adjustment.
"""

from fractions import Fraction
from itertools import combinations, product
import json
from pathlib import Path
import sys


UNIT = "thousand USD over twelve months at a fixed price basis"
DEFAULT_CASE = Path(__file__).resolve().with_name("v04-c08-cases.json")


def exact_mean(values):
    values = list(values)
    if not values:
        raise ValueError("a mean requires at least one value")
    return sum(values, Fraction(0)) / len(values)


def integer(value, name, low=-1000000, high=1000000):
    if type(value) is not int:
        raise TypeError(name + " must be an integer (not a boolean)")
    if not low <= value <= high:
        raise ValueError(name + " is outside the declared finite-case bounds")


def keys(value, expected, name):
    if type(value) is not dict or set(value) != set(expected):
        raise ValueError(name + " has missing, extra or invalid fields")


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON field: " + key)
        result[key] = value
    return result


def reject_constant(text):
    raise ValueError("nonfinite JSON constant is not supported: " + text)


def validate_case(case):
    keys(case, ("schema_version", "provenance", "outcome_unit", "training_groups",
                "lottery", "mediation", "collider", "equivalent_worlds"), "case")
    integer(case["schema_version"], "schema_version", 1, 1)
    if case["outcome_unit"] != UNIT:
        raise ValueError("unsupported outcome unit")
    keys(case["provenance"], ("kind", "created", "edition_boundary", "observations"), "provenance")
    for value in case["provenance"].values():
        if type(value) is not str or not value.strip():
            raise ValueError("provenance fields must be nonblank text")
    if case["provenance"]["kind"] != "original synthetic teaching cases":
        raise ValueError("this benchmark accepts synthetic teaching cases only")
    groups = case["training_groups"]
    if type(groups) is not list or not 1 <= len(groups) <= 20:
        raise ValueError("supply 1 to 20 training groups")
    seen = set()
    for group in groups:
        keys(group, ("x", "n", "treated", "y0", "y1"), "training group")
        integer(group["x"], "x")
        if group["x"] in seen:
            raise ValueError("training group x values must be unique")
        seen.add(group["x"])
        integer(group["n"], "n", 1, 10000)
        integer(group["treated"], "treated", 0, group["n"])
        integer(group["y0"], "y0")
        integer(group["y1"], "y1")
    if sum(group["n"] for group in groups) > 10000:
        raise ValueError("training population is limited to 10000 workers")
    keys(case["lottery"], ("treated_count", "workers"), "lottery")
    workers = case["lottery"]["workers"]
    if type(workers) is not list or not 2 <= len(workers) <= 12:
        raise ValueError("lottery requires 2 to 12 workers")
    integer(case["lottery"]["treated_count"], "treated_count", 1, len(workers) - 1)
    seen = set()
    for worker in workers:
        keys(worker, ("id", "y0", "y1"), "lottery worker")
        name = worker["id"]
        if type(name) is not str or not name.strip() or name in seen:
            raise ValueError("lottery worker IDs must be unique nonblank text")
        seen.add(name)
        integer(worker["y0"], "y0")
        integer(worker["y1"], "y1")
    mediation = case["mediation"]
    keys(mediation, ("u_values", "intercept", "d_to_m", "direct", "m_to_y", "controlled_m"), "mediation")
    values = mediation["u_values"]
    if type(values) is not list or not 1 <= len(values) <= 20:
        raise ValueError("u_values requires 1 to 20 distinct integers")
    for value in values:
        integer(value, "U")
    if len(values) != len(set(values)):
        raise ValueError("u_values must be distinct")
    for key in ("intercept", "d_to_m", "direct", "m_to_y", "controlled_m"):
        integer(mediation[key], "mediation " + key)
    keys(case["collider"], ("threshold", "intercept", "b_to_y"), "collider")
    integer(case["collider"]["threshold"], "threshold", 1, 3)
    integer(case["collider"]["intercept"], "intercept")
    integer(case["collider"]["b_to_y"], "b_to_y")
    worlds = case["equivalent_worlds"]
    if type(worlds) is not list or not 2 <= len(worlds) <= 10:
        raise ValueError("supply 2 to 10 candidate worlds")
    seen = set()
    for world in worlds:
        keys(world, ("name", "y0_intercept", "y0_u", "effect"), "world")
        name = world["name"]
        if type(name) is not str or not name.strip() or name in seen:
            raise ValueError("world names must be unique nonblank text")
        seen.add(name)
        for key in ("y0_intercept", "y0_u", "effect"):
            integer(world[key], "world " + key)


def load_case(path=DEFAULT_CASE):
    with Path(path).open("r", encoding="utf-8") as handle:
        case = json.load(handle, object_pairs_hook=unique_object,
                         parse_constant=reject_constant)
    validate_case(case)
    return case


def observed_gap(rows):
    treated = [row["y"] for row in rows if row["d"] == 1]
    untreated = [row["y"] for row in rows if row["d"] == 0]
    if not treated or not untreated:
        return None
    return exact_mean(treated) - exact_mean(untreated)


def standardize(rows, target="all"):
    """Rows contain only x, d, y; target selects observed X weights.

    Arithmetic is not a check of causal exchangeability. Missing cells raise
    ValueError, rather than using any synthetic hidden potential outcome.
    """
    if target not in ("all", "treated"):
        raise ValueError("target must be all or treated")
    target_rows = rows if target == "all" else [row for row in rows if row["d"] == 1]
    if not target_rows:
        raise ValueError("target population is empty")
    result = Fraction(0)
    for x in sorted({row["x"] for row in target_rows}):
        y1 = [row["y"] for row in rows if row["x"] == x and row["d"] == 1]
        y0 = [row["y"] for row in rows if row["x"] == x and row["d"] == 0]
        if not y1 or not y0:
            raise ValueError("missing observed treatment comparison at x=" + str(x))
        weight = Fraction(sum(row["x"] == x for row in target_rows), len(target_rows))
        result += weight * (exact_mean(y1) - exact_mean(y0))
    return result


def available_standardization(rows, target):
    try:
        return {"value": standardize(rows, target), "note": "arithmetic only; causal assumptions must be justified"}
    except ValueError as error:
        return {"value": None, "note": str(error)}


def training_report(groups):
    population = []
    for group in groups:
        for index in range(group["n"]):
            population.append({"x": group["x"], "d": int(index < group["treated"]),
                               "y0": group["y0"], "y1": group["y1"]})
    rows = [{"x": row["x"], "d": row["d"],
             "y": row["y1"] if row["d"] else row["y0"]} for row in population]
    treated = [row for row in population if row["d"]]
    untreated = [row for row in population if not row["d"]]
    return {
        "population_n": len(population),
        "synthetic_ate": exact_mean(row["y1"] - row["y0"] for row in population),
        "synthetic_att": exact_mean(row["y1"] - row["y0"] for row in treated) if treated else None,
        "observable_gap": observed_gap(rows),
        "synthetic_selection_term": (exact_mean(row["y0"] for row in treated)
                                     - exact_mean(row["y0"] for row in untreated)) if treated and untreated else None,
        "standardized_all": available_standardization(rows, "all"),
        "standardized_treated": available_standardization(rows, "treated"),
    }


def lottery_report(lottery):
    workers = lottery["workers"]
    assignments = []
    for selected in combinations(range(len(workers)), lottery["treated_count"]):
        treated = [worker for index, worker in enumerate(workers) if index in selected]
        untreated = [worker for index, worker in enumerate(workers) if index not in selected]
        treated_mean = exact_mean(worker["y1"] for worker in treated)
        untreated_mean = exact_mean(worker["y0"] for worker in untreated)
        assignments.append({"treated_ids": [worker["id"] for worker in treated],
                            "treated_mean": treated_mean, "untreated_mean": untreated_mean,
                            "difference": treated_mean - untreated_mean,
                            "baseline_difference": exact_mean(worker["y0"] for worker in treated)
                            - exact_mean(worker["y0"] for worker in untreated)})
    mean = exact_mean(row["difference"] for row in assignments)
    return {"assignments": assignments, "assignment_mean": mean,
            "assignment_variance": exact_mean((row["difference"] - mean) ** 2 for row in assignments),
            "synthetic_ate": exact_mean(worker["y1"] - worker["y0"] for worker in workers)}


def mediation_report(model):
    rows = []
    effects = []
    for u in model["u_values"]:
        potential = []
        for d in (0, 1):
            m = model["d_to_m"] * d + u
            y = model["intercept"] + model["direct"] * d + model["m_to_y"] * m
            rows.append({"u": u, "d": d, "m": m, "y": y})
            potential.append(y)
        effects.append(potential[1] - potential[0])
    m = model["controlled_m"]
    at_m = [row for row in rows if row["m"] == m]
    # The structural joint intervention sets M even outside observed support.
    y_at_m0 = model["intercept"] + model["m_to_y"] * m
    y_at_m1 = model["intercept"] + model["direct"] + model["m_to_y"] * m
    return {"rows": rows, "synthetic_total_effect": exact_mean(effects),
            "randomized_observed_gap": observed_gap(rows),
            "controlled_m": m, "synthetic_controlled_direct_effect": Fraction(y_at_m1 - y_at_m0),
            "observed_gap_at_controlled_m": observed_gap(at_m),
            "joint_observed_support_at_m": {str(d): sum(row["d"] == d for row in at_m) for d in (0, 1)}}


def collider_report(model):
    rows = []
    for a, b, e in product((0, 1), repeat=3):
        c = int(a + b + e >= model["threshold"])
        rows.append({"a": a, "b": b, "e": e, "x": c, "d": a,
                     "y": model["intercept"] + model["b_to_y"] * b})
    cells = []
    for c, d in product((0, 1), repeat=2):
        cell = [row["y"] for row in rows if row["x"] == c and row["d"] == d]
        cells.append({"c": c, "d": d, "n": len(cell), "mean_y": exact_mean(cell) if cell else None})
    observed = [{"x": row["x"], "d": row["d"], "y": row["y"]} for row in rows]
    return {"rows": rows, "cells": cells, "synthetic_ate": Fraction(0),
            "observable_gap": observed_gap(observed),
            "standardized_on_c": available_standardization(observed, "all")}


def worlds_report(worlds):
    results = []
    for world in worlds:
        observed = []
        effects = []
        for u in (0, 1):
            d = u
            y0 = world["y0_intercept"] + world["y0_u"] * u
            y1 = y0 + world["effect"]
            observed.append({"d": d, "y": y1 if d else y0})
            effects.append(y1 - y0)
        results.append({"name": world["name"], "observed": observed,
                        "synthetic_ate": exact_mean(effects), "observable_gap": observed_gap(observed)})
    return {"worlds": results,
            "same_observed_distribution": all(row["observed"] == results[0]["observed"] for row in results)}


def build_report(case):
    validate_case(case)
    return {"provenance": case["provenance"], "outcome_unit": case["outcome_unit"],
            "training": training_report(case["training_groups"]),
            "lottery": lottery_report(case["lottery"]),
            "mediation": mediation_report(case["mediation"]),
            "collider": collider_report(case["collider"]),
            "observational_equivalence": worlds_report(case["equivalent_worlds"])}


def json_value(value):
    if isinstance(value, Fraction):
        return str(value)
    raise TypeError("unsupported report value")


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if len(args) > 1:
        print("Usage: python3 v04-c08-identification.py [case.json]", file=sys.stderr)
        return 2
    try:
        case = load_case(Path(args[0]) if args else DEFAULT_CASE)
        report = build_report(case)
    except (OSError, UnicodeError, ValueError, TypeError) as error:
        print("Cannot compute synthetic case: " + str(error), file=sys.stderr)
        return 1
    print(json.dumps(report, default=json_value, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
