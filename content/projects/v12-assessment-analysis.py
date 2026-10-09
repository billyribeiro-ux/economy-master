"""Harbor Skills: a bounded original complete-randomization laboratory.

Observed estimators use observed rows only. Potential records are used separately
for consistency validation and labelled teaching randomization calculations.
Standard library only; run(data) is quiet, deterministic and does not mutate data.
"""
from fractions import Fraction as F
from itertools import combinations
import argparse
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
PREFIX = "v12-assessment-"
ASSIGNMENTS = tuple(combinations(range(1, 7), 3))
COLUMNS = ["centre", "worker", "Z", "D", "B", "Y", "W"]
POPULATION = (
    (1, -2, ("C", "C"), (2, 4), (40, 42)),
    (2, 1, ("C", "N"), (6, 1), (44, 46)),
    (3, 3, ("A", "C"), (3, 2), (48, 50)),
    (4, -1, ("N", "N"), (8, 0), (52, 54)),
    (5, 2, ("A", "N"), (5, 1), (56, 58)),
    (6, 0, ("C", "C"), (4, 6), (60, 62)),
)


def require(ok, message):
    if not ok:
        raise ValueError("Harbor Skills: " + message)


def object_keys(value, expected, label):
    require(type(value) is dict and set(value) == set(expected), label + " keys")


def integer(value, lower, upper, label):
    require(type(value) is int and lower <= value <= upper, label + " integer domain")
    return value


def rational(value, label):
    require(type(value) in (int, str), label + " must be integer or canonical rational string")
    if type(value) is str:
        require(len(value) <= 40 and re.fullmatch(r"-?(0|[1-9][0-9]*)(/[1-9][0-9]*)?", value) is not None,
                label + " rational syntax")
        result = F(value)
        require(str(result) == value, label + " must be reduced canonical rational")
    else:
        require(abs(value) <= 1000, label + " integer bound")
        result = F(value)
    require(abs(result) <= 1000 and result.denominator <= 10**6, label + " rational bounds")
    return result


def strict_load(text):
    def unique(pairs):
        out = {}
        for key, value in pairs:
            require(key not in out, "duplicate JSON key " + key)
            out[key] = value
        return out
    def nonfinite(value):
        raise ValueError("Harbor Skills: nonfinite JSON " + value)
    return json.loads(text, object_pairs_hook=unique, parse_constant=nonfinite)


def encode(value):
    if isinstance(value, F):
        return str(value)
    if type(value) is dict:
        return {k: encode(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [encode(v) for v in value]
    return value


def mean(values):
    return sum(values, F(0)) / len(values)


def sample_variance(values):
    centre = mean(values)
    return sum((v - centre)**2 for v in values) / (len(values) - 1)


def centre_means(rows, column):
    return [mean([F(r[column]) for r in rows if r[0] == j]) for j in range(1, 7)]


def contrast(values, assignment):
    return mean([v for j, v in enumerate(values, 1) if j in assignment]) - mean(
        [v for j, v in enumerate(values, 1) if j not in assignment])


def neyman(values, assignment):
    return sample_variance([v for j, v in enumerate(values, 1) if j in assignment]) / 3 + (
        sample_variance([v for j, v in enumerate(values, 1) if j not in assignment]) / 3)


def solve(matrix, rhs):
    """Exact elimination; a rank failure is explicit, never a pseudoinverse."""
    n = len(rhs)
    a = [[F(v) for v in row] + [F(y)] for row, y in zip(matrix, rhs)]
    for j in range(n):
        pivots = [i for i in range(j, n) if a[i][j]]
        require(bool(pivots), "singular ANCOVA design")
        k = pivots[0]
        a[j], a[k] = a[k], a[j]
        pivot = a[j][j]
        a[j] = [v / pivot for v in a[j]]
        for i in range(n):
            if i != j:
                factor = a[i][j]
                a[i] = [u - factor * v for u, v in zip(a[i], a[j])]
    return [row[-1] for row in a]


def ancova(values, baselines, assignment):
    centred = [v - mean(baselines) for v in baselines]
    x = [[F(1), F(j in assignment), centred[j-1]] for j in range(1, 7)]
    matrix = [[sum(row[i] * row[j] for row in x) for j in range(3)] for i in range(3)]
    rhs = [sum(row[i] * y for row, y in zip(x, values)) for i in range(3)]
    return solve(matrix, rhs)


def interval(lower, upper, left_closed=False, right_closed=False):
    return {"lower": lower, "upper": upper, "lower_unbounded": lower is None,
            "upper_unbounded": upper is None,
            "lower_closed": left_closed, "upper_closed": right_closed}


def invert(lines, actual_line, alpha):
    """Partition the entire real line into exact rational crossing cells."""
    a0, b0 = actual_line
    roots = set()
    for a, b in lines:
        if (a == a0 and b == b0) or (a == -a0 and b == -b0):
            continue  # Identically tied comparison; no isolated polynomial root.
        for sign in (-1, 1):
            denominator = b - sign * b0
            if denominator:
                roots.add((a - sign * a0) / denominator)
    cuts = sorted(roots)
    def p_value(tau):
        observed = abs(a0 - b0 * tau)
        return F(sum(abs(a - b * tau) >= observed for a, b in lines), len(lines))
    accepted = []
    bounds = [None] + cuts + [None]
    for left, right in zip(bounds, bounds[1:]):
        test = ((left + right) / 2 if left is not None and right is not None
                else right - 1 if right is not None
                else left + 1 if left is not None else F(0))
        if p_value(test) > alpha:
            accepted.append(interval(left, right))
        if right is not None and p_value(right) > alpha:
            accepted.append(interval(right, right, True, True))
    merged = []
    for piece in accepted:
        if (merged and merged[-1]["upper"] is not None
                and merged[-1]["upper"] == piece["lower"]
                and (merged[-1]["upper_closed"] or piece["lower_closed"])):
            merged[-1]["upper"] = piece["upper"]
            merged[-1]["upper_unbounded"] = piece["upper_unbounded"]
            merged[-1]["upper_closed"] = piece["upper_closed"]
        else:
            merged.append(dict(piece))
    return {"alpha": alpha, "reject_if": "p <= alpha", "null": "sharp_adjusted_outcome_invariance",
            "intervals": merged, "breakpoints": cuts,
            "probe_p": {str(x): p_value(F(x)) for x in (0, 1, 4, 7, 8, 9, 10)},
            "scope": "Coverage applies when the common sharp invariance null is true; not a generic heterogeneous CACE interval."}


def analyse_observed(rows, assignment, alpha):
    """No types, receipt effects or unobserved potential outcomes enter here."""
    w, d, b, y = [centre_means(rows, c) for c in (6, 3, 4, 5)]
    itt, first = contrast(w, assignment), contrast(d, assignment)
    ac = ancova(w, b, assignment)
    lines = [(contrast(w, s), contrast(d, s)) for s in ASSIGNMENTS]
    p = F(sum(abs(a) >= abs(itt) for a, _ in lines), 20)
    pa = F(sum(abs(ancova(w, b, s)[1]) >= abs(ac[1]) for s in ASSIGNMENTS), 20)
    recipients = [F(r[6]) for r in rows if r[3] == 1]
    others = [F(r[6]) for r in rows if r[3] == 0]
    receipt_slope = mean(recipients) - mean(others) if recipients and others else None
    individuals1 = [F(r[6]) for r in rows if r[2] == 1]
    individuals0 = [F(r[6]) for r in rows if r[2] == 0]
    return {
        "assignment": list(assignment), "centre_baseline": b, "centre_change": w, "centre_receipt": d,
        "change_ITT": itt, "post_only_ITT": contrast(y, assignment),
        "baseline_difference": contrast(b, assignment), "first_stage": first,
        "Wald": itt / first if first else None,
        "Wald_status": "defined" if first else "undefined_zero_first_stage",
        "receipt_OLS": receipt_slope,
        "receipt_OLS_status": "descriptive" if receipt_slope is not None else "undefined_no_receipt_variation",
        "ANCOVA_coefficients": ac, "ANCOVA_regressors": ["intercept", "Z", "centre_B-mean_B"],
        "cluster_Neyman": neyman(w, assignment),
        "incorrect_individual_iid_variance": sample_variance(individuals1)/6 + sample_variance(individuals0)/6,
        "sharp_outcome_null_p_change": p, "sharp_outcome_null_p_ANCOVA": pa,
        "sharp_adjusted_outcome_inversion": invert(lines, (itt, first), alpha),
    }


def records(population, assignment, weak=False):
    rows = []
    for c in population:
        for r in range(2):
            kind = "N" if weak and (c["id"], r) == (2, 0) else c["types"][r]
            z = int(c["id"] in assignment)
            d = int(kind == "A" or (kind == "C" and z))
            w = c["g"] + (-1 if r == 0 else 1) + c["tau"][r] * d
            baseline = c["B"][r]
            rows.append([c["id"], r+1, z, d, baseline, baseline+w, w])
    return rows


def teaching_law(population, weak=False):
    """True alternative-law moments; never used as a sharp-null reference."""
    zero = records(population, (), weak)
    one = records(population, tuple(range(1, 7)), weak)
    w0, w1 = centre_means(zero, 6), centre_means(one, 6)
    d0, d1 = centre_means(zero, 3), centre_means(one, 3)
    effects = [v-u for u, v in zip(w0, w1)]
    first_truth = mean([v-u for u, v in zip(d0, d1)])
    itts, firsts, ratios, acs, variances, post = [], [], [], [], [], []
    for s in ASSIGNMENTS:
        rows = records(population, s, weak)
        w, d, b, y = [centre_means(rows, c) for c in (6, 3, 4, 5)]
        a, f = contrast(w, s), contrast(d, s)
        itts.append(a); firsts.append(f)
        ratios.append(a/f if f else None)
        acs.append(ancova(w, b, s)[1]); variances.append(neyman(w, s))
        post.append(contrast(y, s))
    undefined = sum(v is None for v in ratios)
    true_variance = mean([(v-mean(itts))**2 for v in itts])
    effect_variance = sample_variance(effects)
    formula = sample_variance(w1)/3 + sample_variance(w0)/3 - effect_variance/6
    return {
        "assignment_count": 20, "centre_change_z0": w0, "centre_change_z1": w1,
        "centre_encouragement_effects": effects,
        "encouragement_ATE": mean(effects), "first_stage": first_truth,
        "complier_receipt_ATE_under_exclusion": mean(effects)/first_truth if first_truth else None,
        "expected_change_ITT": mean(itts), "expected_post_only_ITT": mean(post),
        "expected_first_stage": mean(firsts), "expected_ANCOVA": mean(acs),
        "expected_Wald": mean(ratios) if not undefined else None,
        "expected_Wald_status": "unconditional_defined" if not undefined else "undefined_on_assignment_support",
        "zero_first_stage_assignments": undefined,
        "first_stage_range": [min(firsts), max(firsts)],
        "true_ITT_variance": true_variance, "variance_formula": formula,
        "expected_Neyman": mean(variances), "centre_effect_sample_variance": effect_variance,
        "Neyman_expectation_gap": mean(variances)-true_variance,
    }


def validate(data):
    object_keys(data, ("schema", "project", "provenance", "design", "observed_columns",
                       "observed_rows", "teaching_oracle"), "input")
    require(type(data["schema"]) is int and data["schema"] == 1, "schema")
    require(data["project"] == "v12-project" and type(data["project"]) is str, "project")
    require(type(data["provenance"]) is str and data["provenance"] == "Original fictional Harbor Skills Outreach population; no external data or real participants.",
            "provenance")
    design = data["design"]
    object_keys(design, ("centres", "workers_per_centre", "encouraged_count",
                        "actual_encouraged_centres", "alpha", "direct_effect_delta"), "design")
    for key, expected in (("centres", 6), ("workers_per_centre", 2), ("encouraged_count", 3)):
        integer(design[key], expected, expected, key)
    assignment = design["actual_encouraged_centres"]
    require(type(assignment) is list and len(assignment) == 3, "three encouraged centres")
    for j in assignment:
        integer(j, 1, 6, "centre ID")
    require(assignment == sorted(set(assignment)), "sorted distinct assignment IDs")
    alpha = rational(design["alpha"], "alpha")
    require(alpha in (F(1, 5), F(1, 20)), "supported alpha")
    delta = rational(design["direct_effect_delta"], "delta")
    require(-1 <= delta <= 1, "delta in [-1,1]")
    require(type(data["observed_columns"]) is list and data["observed_columns"] == COLUMNS, "observed columns")
    oracle = data["teaching_oracle"]
    object_keys(oracle, ("worker_offsets", "centres", "weak_override"), "teaching oracle")
    offsets = oracle["worker_offsets"]
    require(type(offsets) is list and len(offsets) == 2, "worker offsets")
    for actual, expected in zip(offsets, (-1, 1)):
        integer(actual, expected, expected, "fixed worker offset")
    population = oracle["centres"]
    require(type(population) is list and len(population) == 6, "six oracle centres")
    for c, expected in zip(population, POPULATION):
        object_keys(c, ("id", "g", "types", "tau", "B"), "centre")
        integer(c["id"], expected[0], expected[0], "ordered original centre")
        integer(c["g"], expected[1], expected[1], "original centre trend")
        for key, wanted in (("types", expected[2]), ("tau", expected[3]), ("B", expected[4])):
            require(type(c[key]) is list and len(c[key]) == 2, key + " pair")
            for actual, value in zip(c[key], wanted):
                require(type(actual) is type(value) and actual == value, "unsupported population " + key)
    override = oracle["weak_override"]
    object_keys(override, ("centre", "worker", "from", "to", "actual_encouraged_centres"), "weak override")
    integer(override["centre"], 2, 2, "weak centre")
    integer(override["worker"], 1, 1, "weak worker")
    require(type(override["from"]) is str and type(override["to"]) is str
            and override["from"] == "C" and override["to"] == "N", "supported type change")
    weak_s = override["actual_encouraged_centres"]
    require(type(weak_s) is list and len(weak_s) == 3, "weak assignment")
    for actual, expected in zip(weak_s, (1, 2, 4)):
        integer(actual, expected, expected, "fixed weak assignment")
    rows = data["observed_rows"]
    require(type(rows) is list and len(rows) == 12, "twelve observed rows")
    for row in rows:
        require(type(row) is list and len(row) == 7, "observed row shape")
        for value in row:
            integer(value, -1000, 1000, "observed value")
    expected_rows = records(population, tuple(assignment))
    require(rows == expected_rows, "observed rows disagree with ordered keys, assignment or fixed teaching population")
    return population, tuple(assignment), alpha, delta


def run(data):
    population, assignment, alpha, delta = validate(data)
    baseline = analyse_observed(data["observed_rows"], assignment, alpha)
    weak_rows = records(population, (1, 2, 4), True)
    weak = analyse_observed(weak_rows, (1, 2, 4), alpha)
    complier_effects = [F(c["tau"][r])-delta for c in population
                        for r in range(2) if c["types"][r] == "C"]
    same = True
    for c in population:
        for r in range(2):
            for z in (0, 1):
                kind = c["types"][r]
                d = int(kind == "A" or (kind == "C" and z))
                v = F(c["g"] + (-1 if r == 0 else 1))
                baseline_w = v + c["tau"][r]*d
                changed_w = v + (F(c["tau"][r])-delta)*d + delta*z if kind == "C" else baseline_w
                same = same and baseline_w == changed_w
    return encode({
        "project": "v12-project", "arithmetic": "exact rational strings",
        "interpretation": "Original synthetic fixed population; no empirical replication or superpopulation claim.",
        "observed_analysis": baseline,
        "teaching_oracle": teaching_law(population),
        "weak_extension": {"information": "Separate prospective C-to-N world and newly assigned trial; not an edit to observed baseline evidence.",
                           "observed_rows": weak_rows, "observed_analysis": weak,
                           "teaching_oracle": teaching_law(population, True)},
        "direct_effect_extension": {
            "delta": delta, "class": "Common direct encouragement effect for compliers only; receipt coefficient reduced by delta.",
            "all_worker_assignment_observables_unchanged": same,
            "complier_receipt_ATE_at_fixed_assignment": mean(complier_effects),
            "sharp_receipt_effect_bounds": [F(3), F(5)],
            "assignment_ATE": F(2), "first_stage": F(1, 2), "ratio_of_assignment_effects": F(4),
            "scope": "Bounds apply only to the declared delta in [-1,1] class; randomization does not prove exclusion."},
    })


def protect_output(destination, input_path):
    protected = [Path(__file__), input_path, HERE/(PREFIX+"inputs.json"),
                 HERE/(PREFIX+"README.txt"), HERE/(PREFIX+"manifest.json")]
    for source in protected:
        if destination.resolve() == source.resolve():
            raise ValueError("Harbor Skills: output aliases protected file")
        if destination.exists() and source.exists() and destination.samefile(source):
            raise ValueError("Harbor Skills: output aliases protected file")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=HERE/(PREFIX+"inputs.json"))
    parser.add_argument("--output", type=Path, default=HERE/(PREFIX+"output.json"))
    args = parser.parse_args()
    try:
        protect_output(args.output, args.input)
        require(args.input.stat().st_size <= 65536, "input exceeds 65536-byte limit")
        data = strict_load(args.input.read_text(encoding="utf-8"))
        result = run(data)
        rendered = json.dumps(result, indent=2, allow_nan=False) + "\n"
        args.output.write_text(rendered, encoding="utf-8")
    except (ValueError, OSError, TypeError) as error:
        parser.exit(2, str(error) + "\n")


if __name__ == "__main__":
    main()

