"""Offline reconstruction of a bounded historical BLS descriptive result.

Uses frozen published aggregates, not microdata. Original implementation;
no network, external packages, source rewriting or inferred missing values.
"""

from fractions import Fraction as F
import hashlib
import json
from pathlib import Path
import platform
import re
import sys


DATA = "v04-c12-data.json"
EXTRACT = "v04-c12-source-extract.txt"
MANIFEST = "v04-c12-manifest.json"
LEVELS = ("population_thousands", "labor_force_thousands", "employed_thousands",
          "unemployed_thousands", "not_in_labor_force_thousands")
FIELDS = ("period", "adjustment") + LEVELS + ("published_rate_percent",)
KEYS = {(period, adjustment) for period in ("2023-07", "2024-06", "2024-07")
        for adjustment in ("SA", "NSA")}


def unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON field: " + key)
        value[key] = item
    return value


def invalid_constant(value):
    raise ValueError("nonfinite JSON value: " + value)


def decode_json(raw):
    return json.loads(raw.decode("utf-8"), object_pairs_hook=unique_object,
                      parse_constant=invalid_constant)


def validate_data(data):
    metadata = {
        "schema_version": 1, "source_release": "2024-08-02", "table": "A-1 TOTAL",
        "geography": "United States: 50 states and District of Columbia",
        "population": "Civilian noninstitutional population age 16 and over",
        "level_unit": "thousands of persons", "rate_unit": "percent",
    }
    if type(data) is not dict or set(data) != set(metadata) | {"rows"}:
        raise ValueError("data must have exactly the documented fields")
    for key, value in metadata.items():
        if type(data[key]) is not type(value) or data[key] != value:
            raise ValueError("unsupported metadata: " + key)
    if type(data["rows"]) is not list or len(data["rows"]) != 6:
        raise ValueError("six frozen period/adjustment rows are required")
    seen = set()
    for row in data["rows"]:
        if type(row) is not dict or set(row) != set(FIELDS):
            raise ValueError("row fields differ from documented schema")
        if type(row["period"]) is not str or type(row["adjustment"]) is not str:
            raise TypeError("period and adjustment must be text")
        key = (row["period"], row["adjustment"])
        if key not in KEYS or key in seen:
            raise ValueError("unexpected or duplicate period/adjustment key")
        seen.add(key)
        for field in LEVELS:
            if type(row[field]) is not int or not 0 <= row[field] <= 1000000:
                raise ValueError("levels must be bounded nonnegative integer thousands: " + field)
        if not 0 < row["labor_force_thousands"] <= row["population_thousands"]:
            raise ValueError("positive labor force must not exceed population")
        if max(row["employed_thousands"], row["unemployed_thousands"]) > row["labor_force_thousands"]:
            raise ValueError("employment or unemployment exceeds labor force")
        rate = row["published_rate_percent"]
        if type(rate) is not str or not re.fullmatch(r"(?:[0-9]{1,2}|100)\.[0-9]", rate) or F(rate) > 100:
            raise ValueError("published rate must be one-decimal text from 0.0 to 100.0")


def parse_extract(text):
    if text.count("BEGIN DATA\n") != 1 or text.count("END DATA") != 1:
        raise ValueError("source extract requires one delimited data block")
    block = text.split("BEGIN DATA\n", 1)[1].split("END DATA", 1)[0].strip().splitlines()
    if not block or block[0].split("|") != list(FIELDS):
        raise ValueError("source extract header mismatch")
    rows = []
    for line in block[1:]:
        parts = line.split("|")
        if len(parts) != len(FIELDS):
            raise ValueError("source extract row has wrong field count")
        row = dict(zip(FIELDS, parts))
        for field in LEVELS:
            if not row[field].isdigit():
                raise ValueError("source extract level is not a nonnegative integer")
            row[field] = int(row[field])
        rows.append(row)
    return rows


def load_inputs(directory):
    directory = Path(directory)
    manifest = decode_json((directory / MANIFEST).read_bytes())
    if type(manifest) is not dict or type(manifest.get("schema_version")) is not int or manifest["schema_version"] != 1:
        raise ValueError("invalid manifest")
    if manifest.get("source_url") != "https://www.bls.gov/news.release/archives/empsit_08022024.htm":
        raise ValueError("unexpected source URL")
    hashes = manifest.get("sha256")
    if type(hashes) is not dict or set(hashes) != {DATA, EXTRACT}:
        raise ValueError("manifest must hash exactly the data and source extract")
    contents = {}
    for name in (DATA, EXTRACT):
        expected = hashes[name]
        if type(expected) is not str or not re.fullmatch("[0-9a-f]{64}", expected):
            raise ValueError("invalid SHA-256 field")
        raw = (directory / name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError("frozen input hash mismatch: " + name)
        contents[name] = raw
    data = decode_json(contents[DATA])
    validate_data(data)
    extracted = parse_extract(contents[EXTRACT].decode("utf-8"))
    sort_key = lambda row: (row["period"], row["adjustment"])
    if sorted(data["rows"], key=sort_key) != sorted(extracted, key=sort_key):
        raise ValueError("analysis data differ from the documented source extract")
    return data, manifest


def display_one_decimal(value):
    """Exact nearest-tenth display, ties away from zero; no binary rounding."""
    value = F(value)
    numerator = abs(value.numerator) * 10
    quotient, remainder = divmod(numerator, value.denominator)
    if 2 * remainder >= value.denominator:
        quotient += 1
    sign = "-" if value < 0 and quotient else ""
    return sign + str(quotient // 10) + "." + str(quotient % 10)


def rate(row):
    return F(100 * row["unemployed_thousands"], row["labor_force_thousands"])


def rounding_envelope(row):
    """Conservative envelope if each displayed level differs by <=0.5 thousand.

    This covers independent input-rounding bounds, not sampling uncertainty.
    The numerator and denominator are related, so some corners need not be
    attainable jointly; using the rectangle still supplies an outer bound.
    """
    u, labor = row["unemployed_thousands"], row["labor_force_thousands"]
    return (F(100 * max(0, 2 * u - 1), 2 * labor + 1),
            min(F(100), F(100 * (2 * u + 1), 2 * labor - 1)))


def calculate(data):
    validate_data(data)
    rows = {(row["period"], row["adjustment"]): row for row in data["rows"]}
    audits = []
    for key in sorted(rows):
        row = rows[key]
        reconstructed = rate(row)
        low, high = rounding_envelope(row)
        audits.append({
            "period": key[0], "adjustment": key[1], "ratio_percent_exact": str(reconstructed),
            "ratio_percent_approx": float(reconstructed),
            "ratio_display_percent": display_one_decimal(reconstructed),
            "published_rate_percent": row["published_rate_percent"],
            "display_matches": display_one_decimal(reconstructed) == row["published_rate_percent"],
            "published_minus_ratio_pp": float(F(row["published_rate_percent"]) - reconstructed),
            "level_rounding_envelope_percent": [float(low), float(high)],
            "labor_force_identity_residual_thousands": row["labor_force_thousands"] - row["employed_thousands"] - row["unemployed_thousands"],
            "population_identity_residual_thousands": row["population_thousands"] - row["labor_force_thousands"] - row["not_in_labor_force_thousands"],
        })
    comparisons = []
    for adjustment in ("SA", "NSA"):
        new = rows[("2024-07", adjustment)]
        for period, label in (("2024-06", "month"), ("2023-07", "year")):
            old = rows[(period, adjustment)]
            delta = rate(new) - rate(old)
            display_delta = F(new["published_rate_percent"]) - F(old["published_rate_percent"])
            comparisons.append({"adjustment": adjustment, "comparison": label,
                                "earlier_period": period, "later_period": "2024-07",
                                "ratio_difference_pp_exact": str(delta),
                                "ratio_difference_pp_approx": float(delta),
                                "round_after_subtraction_pp": display_one_decimal(delta),
                                "subtract_published_rates_pp": display_one_decimal(display_delta),
                                "unemployed_level_change_thousands": new["unemployed_thousands"] - old["unemployed_thousands"]})
    june = rows[("2024-06", "SA")]
    july = rows[("2024-07", "SA")]
    july_rate = rate(july)
    primary = {
        "target": "July 2024 U.S. household-survey total unemployment release statistics, 2024-08-02 vintage, SA",
        "rate_percent": {"original": "4.3", "reconstructed": display_one_decimal(july_rate)},
        "month_change_pp": {"original": "0.2", "reconstructed": display_one_decimal(july_rate - rate(june))},
        "unemployed_change_thousands": {"original": 352, "reconstructed": july["unemployed_thousands"] - june["unemployed_thousands"]},
    }
    primary["all_match"] = all(primary[name]["original"] == primary[name]["reconstructed"]
                               for name in ("rate_percent", "month_change_pp", "unemployed_change_thousands"))
    identities_compatible = all(abs(row[field]) <= 1 for row in audits for field in (
        "labor_force_identity_residual_thousands", "population_identity_residual_thousands"))
    displays_match = all(row["display_matches"] for row in audits)
    annual = comparisons[1]
    residuals = [{"period": row["period"], "adjustment": row["adjustment"],
                  "identity": field, "residual_thousands": row[field]}
                 for row in audits for field in ("labor_force_identity_residual_thousands",
                                                  "population_identity_residual_thousands") if row[field]]
    return {
        "primary_replication": primary, "row_audits": audits, "comparison_grid": comparisons,
        "all_six_rate_displays_match": displays_match,
        "identities_compatible_with_component_rounding": identities_compatible,
        "diagnostics": {
            "july_sa_unemployed_over_population_percent": float(F(100 * july["unemployed_thousands"], july["population_thousands"])),
            "july_sa_unemployed_over_employed_percent": float(F(100 * july["unemployed_thousands"], july["employed_thousands"])),
            "july_sa_unemployed_millions_display": display_one_decimal(F(july["unemployed_thousands"], 1000)),
        },
        "discrepancy_log": [
            {"id": "D01", "status": "display-agreement" if displays_match else "unresolved-display-mismatch", "issue": "Unrounded level ratios and printed rates use different precision.",
             "resolution": "Compare nearest-tenth displays and preserve both ratios and source rates; investigate any mismatch."},
            {"id": "D02", "status": "rounding-order-comparison", "issue": "Annual SA change: published rates subtract to " + annual["subtract_published_rates_pp"] + ", while subtraction before rounding gives " + annual["round_after_subtraction_pp"] + " percentage point.",
             "resolution": "Different display operations; report both with their definitions. This is a secondary comparison, not failure of the primary monthly target."},
            {"id": "D03", "status": "compatible-with-rounding" if identities_compatible else "unresolved-identity-residual", "issue": "Check component identities without altering published levels.", "nonzero_residuals": residuals,
             "resolution": "Retain all published values. Three separately rounded levels can have an integer residual of magnitude one; exact undisplayed levels are unavailable."},
            {"id": "D04", "status": "scope-limit", "issue": "Original survey weighting, seasonal-adjustment estimation and sampling uncertainty are not reconstructed.",
             "resolution": "Limit success claim to the stated published-aggregate descriptive calculation."},
        ],
    }


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if len(args) > 1:
        print("Usage: python3 v04-c12-replication.py [package-directory]", file=sys.stderr)
        return 2
    directory = Path(args[0]) if args else Path(__file__).resolve().parent
    try:
        data, manifest = load_inputs(directory)
        result = calculate(data)
        result["reproducibility"] = {
            "python_version": platform.python_version(), "implementation": platform.python_implementation(),
            "source_release": data["source_release"], "source_url": manifest["source_url"],
            "input_sha256": manifest["sha256"], "hash_scope": "local transcription bytes, not the original website",
            "network_required": False,
        }
        print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    except (OSError, UnicodeError, ValueError, TypeError, KeyError) as error:
        print("Cannot reproduce frozen case: " + str(error), file=sys.stderr)
        return 1
    return 0 if (result["primary_replication"]["all_match"] and result["all_six_rate_displays_match"]
                 and result["identities_compatible_with_component_rounding"]) else 3


if __name__ == "__main__":
    raise SystemExit(main())
