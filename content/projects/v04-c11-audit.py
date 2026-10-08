"""Original offline numerical audit lab; standard library only.

Run python3 v04-c11-audit.py with v04-c11-case.json beside this file.
Read v04-c11-README.txt for units, contracts, exact checks and limitations.
Deliberately faulty functions are named broken_* and never provide the
authoritative ledger or variance reference.
"""

from fractions import Fraction as F
import hashlib
import json
import math
from pathlib import Path
import platform
import sys


def require(condition, message):
    """An audit gate that remains active under Python -O."""
    if not condition:
        raise ValueError("audit failed: " + message)


def validate_vector(values, name, magnitude):
    if type(values) is not list or not 1 <= len(values) <= 200:
        raise ValueError(name + " must be a list with 1 to 200 entries")
    for x in values:
        if type(x) is not int:
            raise TypeError(name + " requires integer cents, not bool/float/text")
        if abs(x) > magnitude:
            raise ValueError(name + " exceeds its declared magnitude bound")


def validate_case(case):
    fields = {"case_id", "provenance", "currency", "money_unit", "period",
              "ledger_transactions_cents", "conversion_probe_cents",
              "margin_observations_cents"}
    if type(case) is not dict or set(case) != fields:
        raise ValueError("case has missing, unexpected or invalid fields")
    for key in ("case_id", "provenance"):
        if type(case[key]) is not str or not case[key].strip():
            raise ValueError(key + " must be nonblank text")
    if case["currency"] != "USD" or case["money_unit"] != "cent" or case["period"] != "day":
        raise ValueError("use USD integer cents for a day")
    for key in ("ledger_transactions_cents", "conversion_probe_cents"):
        validate_vector(case[key], key, 10**18)
    validate_vector(case["margin_observations_cents"], "margin_observations_cents", 10**12)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON field: " + key)
        result[key] = value
    return result


def reject_constant(value):
    raise ValueError("nonfinite JSON constant: " + value)


def decode_case(data):
    case = json.loads(data.decode("utf-8"), object_pairs_hook=unique_object,
                      parse_constant=reject_constant)
    validate_case(case)
    return case


def load_case(path):
    return decode_case(Path(path).read_bytes())


def require_binary64():
    info = sys.float_info
    if not (info.radix == 2 and info.mant_dig == 53 and info.max_exp == 1024
            and info.rounds == 1):
        raise ValueError("this roundoff lab requires binary64 round-to-nearest floats")


def exact_total(values):
    """Validated integer-cent inputs; integer addition is exact."""
    return sum(values)


def broken_left_sum(values):
    """Deliberately unsuitable replacement for an exact integer-cent ledger."""
    total = float(values[0])
    for value in values[1:]:
        total = total + float(value)
    return total


def broken_convert_then_fsum(values):
    """Accurate addition cannot recover cents lost in earlier conversion."""
    return math.fsum(float(value) for value in values)


def sum_audit(values):
    original = F(exact_total(values))
    converted = [float(value) for value in values]
    represented = [F.from_float(value) for value in converted]
    represented_sum = sum(represented, F(0))
    sequential = broken_left_sum(values)
    accurate = math.fsum(converted)
    u = F(1, 2**53)
    k = len(values) - 1
    gamma = k * u / (1 - k * u)
    bound = gamma * sum(abs(value) for value in represented)
    accumulation_error = abs(F.from_float(sequential) - represented_sum)
    conversion_error = abs(represented_sum - original)
    total_error = abs(F.from_float(sequential) - original)
    require(accumulation_error <= bound, "sequential summation roundoff bound")
    require(total_error <= conversion_error + bound, "conversion plus arithmetic bound")
    return {
        "exact_net_cents": str(original),
        "represented_input_sum_cents": str(represented_sum),
        "conversion_error_cents": str(conversion_error),
        "left_sum_cents": sequential,
        "fsum_of_converted_cents": accurate,
        "left_accumulation_error_cents": str(accumulation_error),
        "left_total_error_cents": str(total_error),
        "roundoff_bound_cents_exact": str(bound),
        "roundoff_bound_cents_approx": float(bound),
        "relative_condition_number": (str(F(sum(abs(x) for x in values), abs(original)))
                                      if original else None),
    }


def reference_moments(values):
    """Exact independent pairwise variance identity; no floating moments."""
    n = len(values)
    pair_squares = 0
    for i in range(n):
        for j in range(i + 1, n):
            pair_squares += (values[i] - values[j])**2
    return F(sum(values), n), F(pair_squares, n * n)


def centered_moments(values):
    """Population moments, with integer centering before float arithmetic."""
    anchor = values[0]
    offsets = [value - anchor for value in values]
    mean_offset = math.fsum(offsets) / len(offsets)
    variance = math.fsum((delta - mean_offset)**2 for delta in offsets) / len(offsets)
    # The bounded integer total is exactly representable before one division.
    # Reconstructing a large anchor plus an approximate offset is unnecessary.
    return sum(values) / len(values), variance


def broken_raw_variance(values):
    numbers = [float(value) for value in values]
    mean = math.fsum(numbers) / len(numbers)
    return math.fsum(value * value for value in numbers) / len(numbers) - mean * mean


def broken_sample_denominator(values):
    mean = F(sum(values), len(values))
    return sum((value - mean)**2 for value in values) / (len(values) - 1)


def broken_variance_dollar_conversion(variance_cents2):
    return variance_cents2 / 100


def broken_mutating_total(values):
    values.reverse()
    return sum(values)


def within_variance_budget(actual, exact):
    if not math.isfinite(actual):
        return False
    # A declared engineering comparison budget, not a derived bound on every
    # possible centered algorithm execution or on economic measurement error.
    tolerance = max(F(1, 10**9), abs(exact) * F(1, 10**12))
    return abs(F.from_float(actual) - exact) <= tolerance


def detect_broken_variants():
    """Fixed adversarial fixtures remain separate from user-modified cases."""
    tests = []
    fixture = [10**16, 1, -10**16]
    actual = broken_left_sum(fixture)
    tests.append({"variant": "left_float_ledger", "detected": F.from_float(actual) != sum(fixture),
                  "test": "exact integer reference", "actual": str(actual), "expected": "1"})
    fixture = [2**53 + 1, -(2**53)]
    actual = broken_convert_then_fsum(fixture)
    tests.append({"variant": "early_float_conversion", "detected": F.from_float(actual) != sum(fixture),
                  "test": "exact cents before conversion", "actual": str(actual), "expected": "1"})
    fixture = [100000001, 100000002, 100000003]
    exact = reference_moments(fixture)[1]
    actual = broken_raw_variance(fixture)
    tests.append({"variant": "raw_second_moment_variance", "detected": not within_variance_budget(actual, exact),
                  "test": "pairwise exact variance and translation", "actual": str(actual), "expected": str(exact)})
    fixture = [1, 2, 3]
    actual = broken_sample_denominator(fixture)
    exact = reference_moments(fixture)[1]
    tests.append({"variant": "sample_denominator_for_population_target", "detected": actual != exact,
                  "test": "three-entry population reference", "actual": str(actual), "expected": str(exact)})
    exact = F(8, 3) / 10000
    actual = broken_variance_dollar_conversion(F(8, 3))
    tests.append({"variant": "linear_conversion_of_squared_units", "detected": actual != exact,
                  "test": "variance scales with square of unit conversion", "actual": str(actual), "expected": str(exact)})
    fixture = [3, -1, 2]
    original = fixture.copy()
    actual = broken_mutating_total(fixture)
    tests.append({"variant": "input_mutation", "detected": fixture != original,
                  "test": "nonmutation contract even when scalar sum matches", "actual": str(fixture), "expected": str(original)})
    require(all(test["detected"] for test in tests), "a deliberately faulty variant escaped its fixture")
    return tests


def build_report(case):
    validate_case(case)
    require_binary64()
    values = case["margin_observations_cents"]
    exact_mean, exact_var = reference_moments(values)
    approximate_mean, approximate_var = centered_moments(values)
    mean_error = abs(F.from_float(approximate_mean) - exact_mean)
    require(mean_error <= abs(exact_mean) * F(1, 2**53), "mean division roundoff bound")
    require(within_variance_budget(approximate_var, exact_var), "centered variance versus exact reference")
    # Transformations are mathematical properties of the population target.
    shifted = [value + 12345 for value in values]
    scaled = [-3 * value for value in values]
    shift_mean, shift_var = reference_moments(shifted)
    scale_mean, scale_var = reference_moments(scaled)
    require(shift_mean == exact_mean + 12345 and shift_var == exact_var, "translation identity")
    require(scale_mean == -3 * exact_mean and scale_var == 9 * exact_var, "scaling identity")
    require(within_variance_budget(centered_moments(shifted)[1], exact_var), "centered translation test")
    require(within_variance_budget(centered_moments(scaled)[1], 9 * exact_var), "centered scaling test")
    require(reference_moments(list(reversed(values))) == (exact_mean, exact_var), "permutation identity")
    require(within_variance_budget(centered_moments(list(reversed(values)))[1], exact_var), "centered permutation test")
    return {
        "audit_status": "passed",
        "case_id": case["case_id"], "provenance": case["provenance"],
        "currency": case["currency"], "money_unit": case["money_unit"], "period": case["period"],
        "python_version": platform.python_version(), "python_implementation": platform.python_implementation(),
        "float_model": "binary64, round to nearest; u=2^-53; finite integer-valued sum terms",
        "assert_statements_enabled": __debug__,
        "ledger": sum_audit(case["ledger_transactions_cents"]),
        "conversion_probe": sum_audit(case["conversion_probe_cents"]),
        "margins": {
            "n": len(values), "target": "population variance of supplied observations, divisor n",
            "exact_mean_cents": str(exact_mean), "exact_variance_cents2": str(exact_var),
            "exact_variance_dollars2": str(exact_var / 10000),
            "centered_mean_cents_approx": approximate_mean,
            "mean_error_cents_exact": str(mean_error),
            "centered_variance_cents2_approx": approximate_var,
            "centered_variance_error_cents2_exact": str(abs(F.from_float(approximate_var) - exact_var)),
            "raw_variance_cents2_approx": broken_raw_variance(values),
            "comparison_budget": "max(1e-9 cents^2, 1e-12 times exact variance)",
        },
        "invariants_checked": ["translation", "scaling", "permutation"],
        "deliberately_broken_variants": detect_broken_variants(),
        "scope": "Checks the specified computations and fixtures, not source completeness, measurement validity or every possible program change.",
    }


def main():
    script = Path(__file__).resolve()
    path = script.with_name("v04-c11-case.json")
    try:
        raw = path.read_bytes()
        report = build_report(decode_case(raw))
        report["input_sha256"] = hashlib.sha256(raw).hexdigest()
        report["program_sha256"] = hashlib.sha256(script.read_bytes()).hexdigest()
        print(json.dumps(report, indent=2, sort_keys=True, allow_nan=False))
    except (OSError, UnicodeError, ValueError, TypeError) as error:
        print("Cannot complete numerical audit: " + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
