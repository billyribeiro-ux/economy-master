"""Offline original Volume 4 empirical integration benchmark.

Published-rate regression/forecast targets are kept distinct from ratios
reconstructed from rounded levels. See README for retrospective-vintage scope.
"""

from fractions import Fraction as F
import hashlib
import json
from pathlib import Path
import platform
import re
import sys

DATA = "v04-project-data.json"
EXTRACT = "v04-project-source-extract.txt"
MANIFEST = "v04-project-manifest.json"
MONTHS = ["2024-" + str(month).zfill(2) for month in range(2, 8)]
LEVELS = ("population_thousands", "labor_force_thousands", "employed_thousands",
          "unemployed_thousands", "not_in_labor_force_thousands")
RATES = ("published_unemployment_percent", "published_participation_percent",
         "published_employment_population_percent")
FIELDS = ("month", "source_release") + LEVELS + RATES
SOURCES = {
    "2024-07-05": "https://www.bls.gov/news.release/archives/empsit_07052024.htm",
    "2024-08-02": "https://www.bls.gov/news.release/archives/empsit_08022024.htm",
}
PROTOCOL = {
    "target": "published_unemployment_percent",
    "train_months": MONTHS[:3], "validation_month": MONTHS[3], "test_months": MONTHS[4:],
    "selection_loss": "squared error in percentage points squared", "tie_break": "naive",
    "updating": "expanding history; one-step ahead; no test reselection",
    "vintage_scope": "retrospective assembled series",
}


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON field: " + key)
        result[key] = value
    return result


def reject_constant(value):
    raise ValueError("nonfinite JSON constant: " + value)


def decode(raw):
    return json.loads(raw.decode("utf-8"), object_pairs_hook=unique_object,
                      parse_constant=reject_constant)


def validate_data(data):
    expected = {
        "schema_version": 1, "dataset_id": "bls_a1_total_feb_jul_2024_retrospective",
        "geography": "United States: 50 states and District of Columbia",
        "population": "Civilian noninstitutional population age 16 and over",
        "adjustment": "SA", "level_unit": "thousands of persons", "rate_unit": "percent",
    }
    if type(data) is not dict or set(data) != set(expected) | {"rows"}:
        raise ValueError("input fields differ from documented schema")
    for name, value in expected.items():
        if type(data[name]) is not type(value) or data[name] != value:
            raise ValueError("wrong metadata: " + name)
    if type(data["rows"]) is not list or len(data["rows"]) != 6:
        raise ValueError("six consecutive monthly rows required")
    for position, row in enumerate(data["rows"]):
        if type(row) is not dict or set(row) != set(FIELDS):
            raise ValueError("row schema mismatch")
        if row["month"] != MONTHS[position]:
            raise ValueError("months must be unique and ordered February through July 2024")
        release = "2024-07-05" if position == 0 else "2024-08-02"
        if row["source_release"] != release:
            raise ValueError("wrong per-row source release")
        for name in LEVELS:
            if type(row[name]) is not int or not 0 <= row[name] <= 1000000:
                raise ValueError("levels require nonnegative integer thousands within bounds")
        p, labor, employed, unemployed, _ = (row[name] for name in LEVELS)
        if not 0 < labor <= p or max(employed, unemployed) > labor:
            raise ValueError("invalid level denominator or subset count")
        for name in RATES:
            value = row[name]
            if type(value) is not str or not re.fullmatch(r"(?:[0-9]{1,2}|100)\.[0-9]", value) or F(value) > 100:
                raise ValueError("published rates require one-decimal percent strings")


def parse_extract(text):
    if text.count("BEGIN DATA\n") != 1 or text.count("END DATA") != 1:
        raise ValueError("extract data delimiters invalid")
    lines = text.split("BEGIN DATA\n", 1)[1].split("END DATA", 1)[0].strip().splitlines()
    if not lines or lines[0].split("|") != list(FIELDS):
        raise ValueError("extract header invalid")
    rows = []
    for line in lines[1:]:
        pieces = line.split("|")
        if len(pieces) != len(FIELDS):
            raise ValueError("extract field count invalid")
        row = dict(zip(FIELDS, pieces))
        for name in LEVELS:
            if not row[name].isdigit():
                raise ValueError("extract levels must be integer strings")
            row[name] = int(row[name])
        rows.append(row)
    return rows


def load_inputs(directory):
    directory = Path(directory)
    manifest = decode((directory / MANIFEST).read_bytes())
    if type(manifest) is not dict or type(manifest.get("schema_version")) is not int or manifest["schema_version"] != 1:
        raise ValueError("invalid manifest schema")
    if manifest.get("dataset_id") != "bls_a1_total_feb_jul_2024_retrospective":
        raise ValueError("wrong manifest dataset identifier")
    if manifest.get("sources") != SOURCES or manifest.get("protocol") != PROTOCOL:
        raise ValueError("manifest source/protocol differs from fixed project")
    hashes = manifest.get("sha256")
    if type(hashes) is not dict or set(hashes) != {DATA, EXTRACT}:
        raise ValueError("manifest must hash both local inputs")
    contents = {}
    for name in (DATA, EXTRACT):
        expected = hashes[name]
        if type(expected) is not str or not re.fullmatch("[0-9a-f]{64}", expected):
            raise ValueError("invalid SHA-256 field")
        raw = (directory / name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError("frozen input hash mismatch: " + name)
        contents[name] = raw
    data = decode(contents[DATA])
    validate_data(data)
    if parse_extract(contents[EXTRACT].decode("utf-8")) != data["rows"]:
        raise ValueError("structured data differ from source transcription")
    return data, manifest


def number(value):
    value = F(value)
    return {"exact": str(value), "approx": float(value)}


def one_decimal(value):
    value = F(value)
    q, r = divmod(abs(value.numerator) * 10, value.denominator)
    q += 2 * r >= value.denominator
    return ("-" if value < 0 and q else "") + str(q // 10) + "." + str(q % 10)


def ratio_envelope(numerator, denominator):
    """Outer percent bounds under <=0.5-thousand input rounding, not survey CI."""
    return (F(100 * max(0, 2 * numerator - 1), 2 * denominator + 1),
            min(F(100), F(100 * (2 * numerator + 1), 2 * denominator - 1)))


def row_audit(row):
    p, labor, employed, unemployed, outside = (row[name] for name in LEVELS)
    pairs = ((unemployed, labor), (labor, p), (employed, p))
    metrics = {}
    for label, source, (numerator, denominator) in zip(
            ("unemployment", "participation", "employment_population"), RATES, pairs):
        value = F(100 * numerator, denominator)
        low, high = ratio_envelope(numerator, denominator)
        metrics[label] = {
            "reconstructed_percent": number(value), "source_display_percent": row[source],
            "reconstructed_display_percent": one_decimal(value),
            "display_matches": one_decimal(value) == row[source],
            "level_rounding_envelope_percent": [number(low), number(high)],
        }
    return {
        "month": row["month"], "source_release": row["source_release"], "metrics": metrics,
        "labor_force_identity_residual_thousands": labor - employed - unemployed,
        "population_identity_residual_thousands": p - labor - outside,
        "employment_ratio_identity_gap_pp": number(F(100 * (employed - labor + unemployed), p)),
    }


def exact_sequence(values):
    if type(values) is not list or any(type(x) not in (int, str, F) for x in values):
        raise ValueError("provide an exact numeric list, not booleans or binary floats")
    return [F(value) for value in values]


def ols(x, y):
    """Exact descriptive intercept OLS; no sampling or causal model assumed."""
    x, y = exact_sequence(x), exact_sequence(y)
    if len(x) != len(y) or len(x) < 2:
        raise ValueError("OLS needs equal lists with at least two observations")
    n = len(x)
    xbar, ybar = sum(x) / n, sum(y) / n
    sxx = sum((value - xbar)**2 for value in x)
    if not sxx:
        raise ValueError("intercept and time columns are rank deficient")
    sxy = sum((a - xbar) * (b - ybar) for a, b in zip(x, y))
    slope = sxy / sxx
    intercept = ybar - slope * xbar
    fitted = [intercept + slope * value for value in x]
    residuals = [observed - fit for observed, fit in zip(y, fitted)]
    sse = sum(value**2 for value in residuals)
    tss = sum((value - ybar)**2 for value in y)
    ess = sum((value - ybar)**2 for value in fitted)
    if sum(residuals) != 0 or sum(a * e for a, e in zip(x, residuals)) != 0 or tss != ess + sse:
        raise ValueError("OLS projection audit failed")
    return {"intercept_percent": number(intercept), "slope_pp_per_month": number(slope),
            "fitted_percent": [number(v) for v in fitted], "residuals_pp": [number(v) for v in residuals],
            "sse_pp2": number(sse), "tss_pp2": number(tss), "explained_ss_pp2": number(ess),
            "r_squared": number(1 - sse / tss) if tss else None,
            "sum_residuals": str(sum(residuals)), "sum_time_residuals": str(sum(a * e for a, e in zip(x, residuals)))}


def forecast(history, rule):
    history = exact_sequence(history)
    if not history:
        raise ValueError("forecast needs past observations")
    if rule == "naive":
        return history[-1]
    if rule == "drift" and len(history) >= 2:
        return history[-1] + (history[-1] - history[0]) / (len(history) - 1)
    raise ValueError("unsupported rule or inadequate drift history")


def forecast_protocol(y):
    y = exact_sequence(y)
    if len(y) != 6:
        raise ValueError("fixed forecast protocol requires six monthly targets")
    rules = ("naive", "drift")
    validation = []
    validation_losses = {}
    for rule in rules:
        estimate = forecast(y[:3], rule)
        error = y[3] - estimate
        validation_losses[rule] = error**2
        validation.append({"rule": rule, "target_month": MONTHS[3], "history_months": MONTHS[:3],
                           "forecast_percent": number(estimate), "actual_percent": number(y[3]),
                           "error_pp": number(error), "squared_error_pp2": number(error**2)})
    selected = "naive" if validation_losses["naive"] <= validation_losses["drift"] else "drift"
    tests = []
    totals = {rule: F(0) for rule in rules}
    for index in (4, 5):
        for rule in rules:
            estimate = forecast(y[:index], rule)
            error = y[index] - estimate
            totals[rule] += error**2
            tests.append({"rule": rule, "selected_before_test": rule == selected,
                          "target_month": MONTHS[index], "history_months": MONTHS[:index],
                          "forecast_percent": number(estimate), "actual_percent": number(y[index]),
                          "error_pp": number(error), "squared_error_pp2": number(error**2)})
    return {"validation": validation, "selected_rule": selected,
            "tie_occurred": validation_losses["naive"] == validation_losses["drift"],
            "test": tests, "test_mse_pp2": {rule: number(totals[rule] / 2) for rule in rules},
            "selected_rule_test_mse_pp2": number(totals[selected] / 2),
            "scope": "Retrospective one-step updating exercise on known historical values; test outcomes never reselect the rule."}


def analyze(data):
    validate_data(data)
    rows = data["rows"]
    audits = [row_audit(row) for row in rows]
    y = [F(row["published_unemployment_percent"]) for row in rows]
    regression = ols(list(range(1, 7)), y)
    forecasts = forecast_protocol(y)
    low0, high0 = ratio_envelope(rows[0]["unemployed_thousands"], rows[0]["labor_force_thousands"])
    low5, high5 = ratio_envelope(rows[-1]["unemployed_thousands"], rows[-1]["labor_force_thousands"])
    display_match = all(m["display_matches"] for row in audits for m in row["metrics"].values())
    identity_match = all(abs(row[field]) <= 1 for row in audits for field in (
        "labor_force_identity_residual_thousands", "population_identity_residual_thousands"))
    nonzero = [{"month": row["month"], "identity": field, "residual_thousands": row[field]}
               for row in audits for field in ("labor_force_identity_residual_thousands",
                                                "population_identity_residual_thousands") if row[field]]
    ratio_change = F(100 * rows[-1]["unemployed_thousands"], rows[-1]["labor_force_thousands"]) - F(100 * rows[0]["unemployed_thousands"], rows[0]["labor_force_thousands"])
    return {
        "status": "passed" if display_match and identity_match else "numerical-mismatch",
        "protocol": PROTOCOL, "row_audits": audits,
        "all_18_rate_displays_match": display_match, "component_identities_compatible_with_rounding": identity_match,
        "nonzero_component_residuals": nonzero,
        "february_to_july_unemployment_change": {
            "displayed_rate_change_pp": number(y[-1] - y[0]), "reconstructed_ratio_change_pp": number(ratio_change),
            "conditional_rounding_envelope_pp": [number(low5-high0), number(high5-low0)],
            "interpretation": "Conditional input-rounding envelope; no sampling confidence level."},
        "descriptive_ols_on_published_rates": regression,
        "chronological_pedagogical_forecasts": forecasts,
        "chart_values": [{"month": row["month"], "time_index": index+1,
                          "published_unemployment_percent": row["published_unemployment_percent"],
                          "ols_fitted_percent": regression["fitted_percent"][index]} for index, row in enumerate(rows)],
        "limits": ["Historical outcomes were known when this teaching protocol was designed.",
                   "Per-row releases differ and are later than some hypothetical forecast origins; no real-time backtest is reconstructed.",
                   "Survey standard errors, seasonal-adjustment estimation, causal effects and general forecast accuracy are not established."]}


def main(argv=None):
    arguments = sys.argv[1:] if argv is None else argv
    if len(arguments) > 1:
        print("Usage: python3 v04-project-analysis.py [package-directory]", file=sys.stderr)
        return 2
    directory = Path(arguments[0]) if arguments else Path(__file__).resolve().parent
    try:
        data, manifest = load_inputs(directory)
        result = analyze(data)
        result["reproducibility"] = {"python_version": platform.python_version(), "implementation": platform.python_implementation(),
            "input_sha256": manifest["sha256"], "program_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "sources": SOURCES, "network_required": False, "hash_scope": "local files, not official authenticity"}
        print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    except (OSError, UnicodeError, ValueError, TypeError, KeyError, ZeroDivisionError) as error:
        print("Cannot reproduce Volume 4 project: " + str(error), file=sys.stderr)
        return 1
    return 0 if result["status"] == "passed" else 3


if __name__ == "__main__":
    raise SystemExit(main())
