"""Exact assignment enumeration for the original synthetic v05-c12 example.

Run with standard-library Python. The observed-only sharp-null test never
reads the optional synthetic potential-outcome oracle. No network or writes.
"""
import argparse
from collections import Counter
from fractions import Fraction as F
from itertools import combinations
import json
from pathlib import Path


DEFAULT_INPUT = Path(__file__).with_name("v05-c12-experiment.json")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def binary(value, label):
    require(type(value) is int and value in (0, 1), f"{label} must be integer 0 or 1")


def difference(outcomes, treated):
    selected = set(treated)
    n1, n0 = len(selected), len(outcomes)-len(selected)
    require(n1 > 0 and n0 > 0, "both assignment groups must be nonempty")
    return F(sum(y for i, y in enumerate(outcomes) if i in selected), n1) - F(
        sum(y for i, y in enumerate(outcomes) if i not in selected), n0)


def distribution(values):
    counts = Counter(values)
    return [{"difference": str(v), "count": counts[v],
             "probability": str(F(counts[v], len(values)))} for v in sorted(counts)]


def observed_test(rows, n1):
    """Test the individual no-effect null from observed Z,Y only."""
    require(isinstance(rows, list) and 2 <= len(rows) <= 16, "use 2 through 16 observed units")
    require(type(n1) is int and 0 < n1 < len(rows), "invalid fixed treatment count")
    ids = []
    for row in rows:
        require(isinstance(row, dict), "observed row must be an object")
        require(isinstance(row.get("id"), str) and row["id"], "unit ID required")
        ids.append(row["id"])
        binary(row.get("assignment"), "assignment")
        binary(row.get("outcome"), "observed outcome")
    require(len(set(ids)) == len(ids), "unit IDs must be unique")
    selected = tuple(i for i, row in enumerate(rows) if row["assignment"] == 1)
    require(len(selected) == n1, "observed assignment disagrees with fixed treatment count")
    outcomes = [row["outcome"] for row in rows]
    statistic = difference(outcomes, selected)
    null_statistics = [difference(outcomes, subset) for subset in combinations(range(len(rows)), n1)]
    extreme = sum(abs(value) >= abs(statistic) for value in null_statistics)
    positive_tail = sum(value >= statistic for value in null_statistics)
    return {
        "n": len(rows), "n_treated": n1, "n_control": len(rows)-n1,
        "treated_completions": sum(outcomes[i] for i in selected),
        "control_completions": sum(outcomes)-sum(outcomes[i] for i in selected),
        "difference_in_completion_rates": str(statistic),
        "assignment_count": len(null_statistics),
        "sharp_null": "Y_i(1) = Y_i(0) for every unit",
        "two_sided_rule": "inclusive absolute difference at least the observed absolute difference",
        "two_sided_extreme_count": extreme,
        "two_sided_p": str(F(extreme, len(null_statistics))),
        "positive_tail_p_for_predeclared_direction_only": str(F(positive_tail, len(null_statistics))),
        "null_distribution": distribution(null_statistics),
    }


def oracle_audit(rows, potentials, n1):
    """Separate supplied-model truth, never an observed-data causal estimate."""
    require(isinstance(potentials, list), "oracle must be a list")
    observed_ids = {row["id"] for row in rows}
    by_id = {}
    for row in potentials:
        require(isinstance(row, dict) and isinstance(row.get("id"), str), "oracle unit ID required")
        require(row["id"] not in by_id, "duplicate oracle ID")
        binary(row.get("y0"), "oracle y0")
        binary(row.get("y1"), "oracle y1")
        by_id[row["id"]] = row
    require(set(by_id) == observed_ids, "oracle IDs must match observed units")
    y0 = [by_id[row["id"]]["y0"] for row in rows]
    y1 = [by_id[row["id"]]["y1"] for row in rows]
    for i, row in enumerate(rows):
        require(row["outcome"] == (y1[i] if row["assignment"] else y0[i]),
                "oracle conflicts with an observed outcome")
    effects = [b-a for a, b in zip(y0, y1)]
    true_ate = F(sum(effects), len(rows))
    estimates = []
    for subset in combinations(range(len(rows)), n1):
        selected = set(subset)
        # Unlike a sharp-null test, outcomes change under the supplied schedule.
        outcomes = [y1[i] if i in selected else y0[i] for i in range(len(rows))]
        estimates.append(difference(outcomes, subset))
    mean = sum(estimates)/len(estimates)
    variance = sum((value-mean)**2 for value in estimates)/len(estimates)
    return {
        "interpretation": "synthetic potential outcomes supplied by the author, not empirically observed truth",
        "individual_effects": effects,
        "true_finite_population_ate": str(true_ate),
        "assignment_mean_difference": str(mean),
        "assignment_variance_of_difference": str(variance),
        "assignment_distribution_under_oracle": distribution(estimates),
        "compatible_zero_effect_schedule": {
            "rule": "set y0 and y1 both equal to each unit's observed outcome",
            "ate": "0",
        },
    }


def analyze(data):
    require(isinstance(data, dict), "input must be a JSON object")
    require(data.get("synthetic") is True, "input must explicitly identify synthetic data")
    design = data.get("design")
    require(isinstance(design, dict), "design object required")
    require(design.get("assignment_law") == "uniform_complete_randomization", "unsupported assignment law")
    require(design.get("test") == "two_sided_absolute_difference_sharp_null", "unsupported prespecified test")
    observed = observed_test(data.get("observed"), design.get("n_treated"))
    result = {
        "case_id": data.get("case_id"), "synthetic": True,
        "observed_only_analysis": observed,
        "limitations": [
            "The exact p-value tests an individual sharp null, not an arbitrary heterogeneous zero average effect.",
            "The lottery targets these fixed units; it is not random sampling of a wider population.",
            "The measured assignment effect does not identify a psychological mechanism or welfare.",
            "Complete outcomes and the stated assignment law are required; missing outcomes are rejected.",
        ],
    }
    if "synthetic_oracle" in data:
        result["separate_oracle_audit"] = oracle_audit(data["observed"], data["synthetic_oracle"], design["n_treated"])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_INPUT)
    args = parser.parse_args()
    try:
        result = analyze(json.loads(args.data.read_text(encoding="utf-8")))
    except (ValueError, OSError, TypeError, KeyError) as error:
        parser.exit(2, f"Invalid experiment input: {error}\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
