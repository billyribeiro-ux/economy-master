"""Offline Monte Carlo inventory comparison; standard-library Python only.

Run python3 v04-c06-inventory.py with v04-c06-case.json beside this script.
Synthetic USD cents/day inputs; see v04-c06-readme.txt for the full contract.
"""

from fractions import Fraction
import json
import math
from pathlib import Path
import platform
import random
import statistics
import sys


def integer(value, name, low, high):
    if type(value) is not int:
        raise TypeError(name + " must be an integer (not bool or float)")
    if not low <= value <= high:
        raise ValueError(name + " outside supported bounds")


def validate_case(case):
    fields = {
        "case_id", "provenance", "currency", "period", "demand_units",
        "demand_weights", "stock_a_units", "stock_b_units",
        "price_cents_per_unit", "cost_cents_per_unit",
        "salvage_cents_per_unit", "replications", "seed",
    }
    if type(case) is not dict or set(case) != fields:
        raise ValueError("case must have exactly the documented fields")
    for key in ("case_id", "provenance"):
        if type(case[key]) is not str or not case[key].strip():
            raise ValueError(key + " must be nonblank text")
    if case["currency"] != "USD" or case["period"] != "day":
        raise ValueError("this tool requires USD and day units")
    demands = case["demand_units"]
    weights = case["demand_weights"]
    if type(demands) is not list or type(weights) is not list:
        raise TypeError("demand_units and demand_weights must be lists")
    if not 1 <= len(demands) <= 20 or len(weights) != len(demands):
        raise ValueError("use 1 to 20 matched demand and weight entries")
    for demand in demands:
        integer(demand, "demand", 0, 1000000)
    if any(demands[i] >= demands[i + 1] for i in range(len(demands) - 1)):
        raise ValueError("demand_units must be strictly increasing")
    for weight in weights:
        integer(weight, "weight", 0, 1000000)
    if sum(weights) == 0:
        raise ValueError("at least one demand weight must be positive")
    for key in ("stock_a_units", "stock_b_units"):
        integer(case[key], key, 0, 1000000)
    for key in ("price_cents_per_unit", "cost_cents_per_unit",
                "salvage_cents_per_unit"):
        integer(case[key], key, 0, 1000000)
    if not (case["salvage_cents_per_unit"] <= case["cost_cents_per_unit"]
            <= case["price_cents_per_unit"]):
        raise ValueError("this case requires salvage <= cost <= price")
    integer(case["replications"], "replications", 2, 200000)
    integer(case["seed"], "seed", 0, 2**64 - 1)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON field: " + key)
        result[key] = value
    return result


def reject_constant(value):
    raise ValueError("nonfinite JSON constant: " + value)


def load_case(path):
    with Path(path).open("r", encoding="utf-8") as handle:
        case = json.load(handle, object_pairs_hook=unique_object,
                         parse_constant=reject_constant)
    validate_case(case)
    return case


def profit_cents(demand, stock, case):
    """Pure integer payoff; arguments come from the validated case/support."""
    sold = min(demand, stock)
    leftover = stock - sold
    return (case["price_cents_per_unit"] * sold
            + case["salvage_cents_per_unit"] * leftover
            - case["cost_cents_per_unit"] * stock)


def demand_from_u(u, case):
    """Inverse discrete CDF for validated inputs, with half-open intervals."""
    if type(u) not in (int, float) or not math.isfinite(u) or not 0 <= u < 1:
        raise ValueError("u must be finite and in [0, 1)")
    cumulative = 0
    total = sum(case["demand_weights"])
    for demand, weight in zip(case["demand_units"], case["demand_weights"]):
        cumulative += weight
        if u < cumulative / total:
            return demand
    raise RuntimeError("validated CDF did not reach one")


def exact_reference(case):
    """Enumerate rational population moments; never use simulation output."""
    weights = case["demand_weights"]
    probabilities = [Fraction(w, sum(weights)) for w in weights]
    a = [profit_cents(d, case["stock_a_units"], case)
         for d in case["demand_units"]]
    b = [profit_cents(d, case["stock_b_units"], case)
         for d in case["demand_units"]]
    delta = [right - left for left, right in zip(a, b)]

    def mean(values):
        return sum(p * y for p, y in zip(probabilities, values))

    def variance(values):
        mu = mean(values)
        return sum(p * (y - mu)**2 for p, y in zip(probabilities, values))

    return {
        "mean_a_cents": mean(a),
        "mean_b_cents": mean(b),
        "mean_delta_cents": mean(delta),
        "variance_a_cents2": variance(a),
        "variance_b_cents2": variance(b),
        "variance_paired_delta_cents2": variance(delta),
        "variance_independent_delta_cents2": variance(a) + variance(b),
        "probability_b_worse_same_demand": sum(
            p for p, d in zip(probabilities, delta) if d < 0),
    }


def summarize(values):
    """Summarize at least two finite independent-replication outputs."""
    if len(values) < 2 or not all(math.isfinite(x) for x in values):
        raise ValueError("summary needs at least two finite values")
    mean = statistics.mean(values)
    variance = statistics.variance(values)
    se = math.sqrt(variance / len(values))
    return {
        "mean_delta_cents": mean,
        "sample_variance_delta_cents2": variance,
        "estimated_mc_se_cents": se,
        "approximate_95pct_mc_interval_cents": [mean - 1.96 * se,
                                                mean + 1.96 * se],
    }


def simulate(case):
    """Each replicate consumes three uniforms: shared, independent A, B."""
    validate_case(case)
    rng = random.Random(case["seed"])
    paired = []
    independent = []
    counts = {str(d): 0 for d in case["demand_units"]}
    for _ in range(case["replications"]):
        shared = demand_from_u(rng.random(), case)
        separate_a = demand_from_u(rng.random(), case)
        separate_b = demand_from_u(rng.random(), case)
        counts[str(shared)] += 1
        paired.append(profit_cents(shared, case["stock_b_units"], case)
                      - profit_cents(shared, case["stock_a_units"], case))
        independent.append(profit_cents(separate_b, case["stock_b_units"], case)
                           - profit_cents(separate_a, case["stock_a_units"], case))
    exact = exact_reference(case)
    return {
        "case_id": case["case_id"],
        "provenance": case["provenance"],
        "currency": "USD",
        "period": "day",
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "generator": "random.Random; Mersenne Twister; random()",
        "seed": case["seed"],
        "replications": case["replications"],
        "uniforms_per_replication": 3,
        "draw_order": ["shared_demand", "independent_a", "independent_b"],
        "shared_demand_counts": counts,
        "exact_reference_rational": {k: str(v) for k, v in exact.items()},
        "paired": summarize(paired),
        "independent": summarize(independent),
        "interval_scope": "Approximate sampling error from simulation of the specified model; not model or parameter uncertainty.",
    }


def main():
    path = Path(__file__).resolve().parent / "v04-c06-case.json"
    try:
        report = simulate(load_case(path))
        print(json.dumps(report, indent=2, sort_keys=True, allow_nan=False))
    except (OSError, UnicodeError, ValueError, TypeError) as error:
        print("Cannot simulate: " + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
