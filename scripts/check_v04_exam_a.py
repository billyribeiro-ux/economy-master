"""Independent arithmetic, behavioral and fragment checks for Volume 4 Form A.

All cases are synthetic. This checker does not certify causal assumptions,
source authenticity, examination difficulty, or visual/print presentation.
Run from any directory with the Python standard library only.
"""
from calendar import monthrange
from copy import deepcopy
from datetime import date, datetime
from fractions import Fraction as F
from html.parser import HTMLParser
from itertools import product
from math import fsum, isclose, sqrt
from pathlib import Path
import json
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
MANUSCRIPT = ROOT / "content/assessment-parts/v04-form-a.html"


def require(condition, message):
    if not condition:
        raise ValueError(message)


class Fragment(HTMLParser):
    """Read actual tables, IDs, scoring attributes and the supplied code."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids = []
        self.parts = []
        self.rubrics = []
        self.headings = []
        self.tables = {}
        self.table_id = None
        self.row = None
        self.cell = None
        self.validator = ""
        self.in_validator = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.ids.append(attrs["id"])
        if tag in ("h1", "h2", "h3"):
            self.headings.append((tag, attrs.get("id")))
        if tag == "li" and "data-points" in attrs:
            self.parts.append((attrs.get("id"), int(attrs["data-points"])))
        if tag == "p" and attrs.get("class") == "rubric":
            self.rubrics.append(int(attrs["data-points"]))
        if tag == "table":
            self.table_id = attrs.get("id")
            self.tables[self.table_id] = []
        if tag == "tr" and self.table_id:
            self.row = []
        if tag in ("th", "td") and self.row is not None:
            self.cell = []
        if tag == "pre" and attrs.get("id") == "v04-a-validator":
            self.in_validator = True

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)
        if self.in_validator:
            self.validator += data

    def handle_endtag(self, tag):
        if tag in ("th", "td") and self.cell is not None:
            self.row.append("".join(self.cell).strip())
            self.cell = None
        if tag == "tr" and self.row is not None:
            self.tables[self.table_id].append(self.row)
            self.row = None
        if tag == "table":
            self.table_id = None
        if tag == "pre":
            self.in_validator = False


def mean(values):
    return sum(values, F(0)) / len(values)


def population_variance(values):
    # Pairwise identity supplies a path independent of centered-squares prose.
    n = len(values)
    return sum((values[i] - values[j]) ** 2
               for i in range(n) for j in range(i + 1, n)) / (n * n)


def check():
    source = MANUSCRIPT.read_text(encoding="utf-8")
    fragment = Fragment()
    fragment.feed(source)
    require(len(fragment.ids) == len(set(fragment.ids)), "duplicate HTML IDs")
    require(fragment.headings[0] == ("h2", "form-a"), "fragment heading")
    require(not any(tag == "h1" for tag, _ in fragment.headings), "unexpected h1")
    require(all(value == "form-a" or value.startswith("v04-a-")
                for value in fragment.ids), "unprefixed ID")
    expected_parts = [(f"v04-a-q{q}{letter}", 5)
                      for q in range(1, 6) for letter in "abcd"]
    require(fragment.parts == expected_parts, "five domains/four five-point parts")
    require(fragment.rubrics == [5] * 20, "twenty explicit five-point rubrics")
    for q in range(1, 6):
        require(f"v04-a-q{q}" in fragment.ids and f"v04-a-s{q}" in fragment.ids,
                f"domain {q} question/solution group missing")
        for letter in "abcd":
            require(f"v04-a-s{q}{letter}" in fragment.ids, "missing part solution")
    require(sum(points for _, points in fragment.parts) == 100, "total points")
    require("180 minutes" in source and "basic nonprogrammable calculator" in source,
            "exam conditions missing")
    for chapter in range(1, 13):
        require(f'href="v04-c{chapter:02}.html"' in source, "method link missing")
        require((ROOT / f"content/chapters/v04-c{chapter:02}.html").is_file(),
                "linked chapter absent")
    checks = ["Fragment has five domains, twenty matched five-point parts/solutions, "
              "100 total points, twenty rubrics and uniquely prefixed IDs."]
    results = {}

    # D1: read the actual prompt table, then compare period-by-period deflation
    # and the separate terminal-value approach to discounted cash flow.
    sales = {row[0]: row[1:] for row in fragment.tables["v04-a-sales"][1:]}
    require(sales == {"R": ["220", "242"], "S": ["110", "unreported"],
                      "T": ["330", "—"], "U": ["—", "363"]},
            "sales fixture changed without an answer audit")
    jan = sum(F(row[0]) for row in sales.values() if row[0].isdigit())
    feb = sum(F(row[1]) * F(100, 110)
              for row in sales.values() if row[1].isdigit())
    threshold = (jan - feb) * F(110, 100)
    require((jan, feb, threshold) == (660, 550, 121), "roster/deflation results")
    for missing in (0, 60, 121, 242, 1000):
        real_change = sum([F(242), F(missing), F(363)]) / F(11, 10) - jan
        require(real_change == F(10, 11) * (missing - 121),
                "missing-value sensitivity identity")
    require(F(242) / F(11, 10) == 220, "R real growth")
    rate = F(1, 10)
    flows = [-500, 220, 342]
    pv_terms = [F(cash) / (1 + rate) ** t for t, cash in enumerate(flows)]
    npv = sum(pv_terms)
    terminal_value = -500 * F(121, 100) + 220 * F(11, 10) + 342
    require(npv == terminal_value / F(121, 100) == F(-2100, 121), "NPV")
    wc = -100 + F(100) / (1 + rate) ** 2
    netted = -400 + F(220) / (1 + rate) + F(242) / (1 + rate) ** 2
    require(netted == 0 and wc == npv, "working-capital timing reconciliation")
    require("=B5/(1+$B$2)^C5" in source and "=SUM(D5:D7)" in source,
            "spreadsheet solution changed")
    results["D1"] = {"january_real": str(jan), "february_observed_real": str(feb),
                     "missing_sales_zero_change": str(threshold), "npv_usd": str(npv)}
    checks.append("D1: actual sales table, missing-amount sign boundary, per-month "
                  "deflation, independent terminal-value NPV and working-capital timing.")

    # D2: execute the solution's own validator in both supported launch modes.
    # The harness uses explicit exceptions, so its checks also survive -O.
    require("assert " not in fragment.validator, "validator relies on assert")
    compile(fragment.validator, "Form-A-validator", "exec")
    harness = '''
import json
from copy import deepcopy
def ensure(condition, message):
    if not condition:
        raise ValueError(message)
B = 2**53
base = {"unit": "USD cents", "opening_cents": B,
        "closing_cents": B+3, "fee_cents": 2}
valid = [base, {**base, "opening_cents": B+10,
               "closing_cents": B+18, "fee_cents": 7},
         {"unit": "USD cents", "opening_cents": 0,
          "closing_cents": 0, "fee_cents": 0},
         {"unit": "USD cents", "opening_cents": 10**18,
          "closing_cents": 0, "fee_cents": 10**18}]
for record in valid:
    before = deepcopy(record)
    validate(record)
    ensure(record == before, "valid input mutated")
nets = [r["closing_cents"]-r["opening_cents"]-r["fee_cents"] for r in valid]
ensure(nets == [1, 1, 0, -2*10**18], "valid nets")
invalid = [None, [], (), "record", {**base, "extra": 0}]
for field in base:
    invalid.append({k:v for k,v in base.items() if k != field})
for unit in (None, 1, True, "USD", "USD dollars", "EUR cents", "usd cents"):
    invalid.append({**base, "unit": unit})
for field in ("opening_cents", "closing_cents", "fee_cents"):
    for value in (True, False, 1.0, 2.5, "2", None, [], {}, -1, 10**18+1):
        invalid.append({**base, field: value})
for record in invalid:
    before = deepcopy(record)
    try:
        validate(record)
    except (TypeError, ValueError):
        pass
    else:
        raise ValueError("invalid record accepted")
    ensure(record == before, "invalid input mutated")
print(json.dumps({"valid": len(valid), "invalid": len(invalid), "nets": nets}))
'''
    mode_results = []
    for flags in ([], ["-O"]):
        completed = subprocess.run([sys.executable, *flags, "-c",
                                    fragment.validator + "\n" + harness],
                                   text=True, capture_output=True, check=False)
        require(completed.returncode == 0, "validator mode failure: " + completed.stderr)
        mode_results.append(json.loads(completed.stdout))
    require(mode_results[0] == mode_results[1], "optimized validation differs")
    require(sys.float_info.mant_dig == 53 and sys.float_info.max_exp == 1024,
            "numerical stress check requires the stated binary64 environment")
    b = 2 ** 53
    exact = (b + 3) - b - 2
    represented = F.from_float(float(b + 3)) - F.from_float(float(b)) - 2
    floating = float(b + 3) - float(b) - 2
    require(exact == 1 and represented == floating == 2, "floating stress result")
    require(represented - exact == 1 and F.from_float(floating) - represented == 0,
            "representation/accumulation separation")
    require(fsum([float(b + 3), -float(b), -2.0]) == 2,
            "accurate summation cannot restore discarded level")
    for shift, extra_fee in product((0, 1, 10, 1000), (0, 1, 5, 50)):
        require((b + 3 + shift + extra_fee) - (b + shift) - (2 + extra_fee) == 1,
                "exact net transformation")
    require(not exact >= 2 and floating >= 2, "decision reversal")
    require(abs(F.from_float(floating) - exact) > F(1, 4), "absolute-budget failure")
    tolerance = 1e-12 * max(float(b + 3), float(b + 2))
    require(9007 < tolerance < 9008 and
            isclose(float(b + 3), float(b + 2), rel_tol=1e-12, abs_tol=0),
            "level-scaled tolerance example")
    results["D2"] = {"exact_net_cents": exact, "floating_net_cents": floating,
                     "representation_error_cents": str(represented - exact),
                     "subtraction_error_cents": str(F.from_float(floating) - represented),
                     "validator_modes": mode_results[0]}
    checks.append("D2: manuscript validator passed four valid and 46 invalid cases "
                  "with nonmutation in normal and -O modes; exact transformations, "
                  "binary64 representation loss, fsum boundary and approval/tolerance reversal.")

    # D3: determinant solution of normal equations differs from the prose's
    # centered-sum solution; objective expansions checked on a rational grid.
    xy = [(F(row[1]), F(row[2]))
          for row in fragment.tables["v04-a-regression"][1:]]
    x, y = zip(*xy)
    n = len(x)
    sx, sy = sum(x), sum(y)
    sxx, sxy = sum(v * v for v in x), sum(u * v for u, v in xy)
    det = n * sxx - sx * sx
    intercept = (sy * sxx - sx * sxy) / det
    slope = (n * sxy - sx * sy) / det
    require((intercept, slope) == (10, 2) and det > 0, "OLS determinant solution")
    fitted = [intercept + slope * value for value in x]
    residual = [value - fit for value, fit in zip(y, fitted)]
    require(fitted == [10, 12, 14, 16] and residual == [0, 1, -2, 1],
            "OLS predictions/residuals")
    require(sum(residual) == sum(value * err for value, err in zip(x, residual)) == 0,
            "normal equations")
    sse = sum(err ** 2 for err in residual)
    sst = population_variance(list(y)) * n
    ssr = sum((fit - mean(y)) ** 2 for fit in fitted)
    require((sse, sst, ssr, 1 - sse / sst) == (6, 26, 20, F(10, 13)),
            "projection decomposition")
    for da, db in product((F(-2), F(-1, 3), F(0), F(1, 2), F(3)), repeat=2):
        alternative = sum((value - (intercept + da) - (slope + db) * xx) ** 2
                          for xx, value in xy)
        increment = sum((da + db * xx) ** 2 for xx in x)
        require(alternative == sse + increment and increment >= 0,
                "global squared-error decomposition")
    chart = []
    for width, height, low_y, high_y in [(300, 180, 0, 18), (150, 180, 9, 18)]:
        transform = lambda xx, yy: (F(width) * xx / 3,
                                    F(height) * (yy - low_y) / (high_y - low_y))
        left, right = transform(0, intercept), transform(3, intercept + 3 * slope)
        pixel_slope = (right[1] - left[1]) / (right[0] - left[0])
        chart.append((pixel_slope, transform(2, 12)))
    require(chart == [(F(1, 5), (F(200), F(120))),
                      (F(4, 5), (F(100), F(60)))], "chart coordinate arithmetic")
    require(slope / 60 == F(1, 30) and intercept + 8 * slope == 26,
            "rescaling/extrapolation arithmetic")
    results["D3"] = {"intercept": str(intercept), "slope": str(slope),
                     "SSE": str(sse), "SST": str(sst), "R_squared": str(1 - sse / sst),
                     "chart_slopes": [str(entry[0]) for entry in chart],
                     "eight_hour_prediction": "26"}
    checks.append("D3: independent normal-equation determinants, exact residual "
                  "orthogonality, pairwise SST, 25 objective decompositions, pixel "
                  "coordinates/angles and unit rescaling.")

    # D4: enumerate all nine independent pairs and all nine two-replication
    # paired means, independently checking both dependence and sample averaging.
    policy_a = list(map(F, [20, 50, 80]))
    policy_b = list(map(F, [30, 45, 90]))
    differences = [bb - aa for aa, bb in zip(policy_a, policy_b)]
    independent_differences = [bb - aa for aa, bb in product(policy_a, policy_b)]
    va, vb = population_variance(policy_a), population_variance(policy_b)
    cov = mean([aa * bb for aa, bb in zip(policy_a, policy_b)]) - mean(policy_a) * mean(policy_b)
    vd, vi = population_variance(differences), population_variance(independent_differences)
    require((mean(differences), va, vb, cov, vd, vi) == (5, 600, 650, 600, 50, 1250),
            "simulation moments")
    require(vd == va + vb - 2 * cov, "covariance variance identity")
    paired_two_means = [(a + b) / 2 for a, b in product(differences, repeat=2)]
    require(population_variance(paired_two_means) == vd / 2,
            "independent replication variance enumeration")
    require(vd / 400 == F(1, 8) and vi / (vd / 400) == 10000,
            "MCSE and budget matching")
    groups = [list(map(int, row[1:]))
              for row in fragment.tables["v04-a-causal"][1:]]
    count_a = sum(row[0] for row in groups)
    count_b = sum(row[2] for row in groups)
    raw_a = F(sum(row[0] * row[1] for row in groups), count_a)
    raw_b = F(sum(row[2] * row[3] for row in groups), count_b)
    total = count_a + count_b
    weights = [F(row[0] + row[2], total) for row in groups]
    standardized_a = sum(weight * row[1] for weight, row in zip(weights, groups))
    standardized_b = sum(weight * row[3] for weight, row in zip(weights, groups))
    require((raw_a, raw_b, raw_b - raw_a) == (F(160, 7), F(140, 3), F(500, 21)),
            "crude register contrast")
    require(weights == [F(3, 4), F(1, 4)] and
            standardized_b - standardized_a == F(5, 2), "target standardization")
    require(F(400, 40000) == F(1, 100), "replication growth variance ratio")
    results["D4"] = {"paired_mean_usd": "5", "paired_variance_usd_squared": str(vd),
                     "covariance_usd_squared": str(cov),
                     "paired_MCSE_usd": sqrt(vd / 400),
                     "independent_MCSE_usd": sqrt(vi / 400),
                     "independent_matching_count": 10000,
                     "crude_contrast_usd_per_day": str(raw_b - raw_a),
                     "standardized_contrast_usd_per_day": str(standardized_b - standardized_a)}
    checks.append("D4: nine-state independent comparison and two-replication "
                  "enumerations, pairwise variances/covariance, 400-pair MCSE, "
                  "10,000-comparison budget, and separately weighted target potential-mean formula.")

    # D5: derive the maturity/release dates independently from the month index.
    rows = fragment.tables["v04-a-timing"][1:]
    forecast_rows = []
    for cohort, role, end, release, outcome, pred_a, pred_b in rows:
        start = datetime.strptime(cohort, "%B %Y").date()
        maturity = datetime.strptime(end + " 2024", "%d %B %Y").date()
        available = datetime.strptime(release + " 2024", "%d %B %Y").date()
        maturity_month, release_month = start.month + 1, start.month + 2
        require(maturity == date(2024, maturity_month, monthrange(2024, maturity_month)[1]),
                "two-month outcome window")
        require(available == date(2024, release_month, monthrange(2024, release_month)[1]),
                "label release schedule")
        forecast_rows.append({"start": start, "role": role, "maturity": maturity,
                              "release": available, "y": F(outcome),
                              "A": F(pred_a), "B": F(pred_b)})
    selection = date(2024, 5, 1)
    validation = [row for row in forecast_rows if row["role"] == "validation"]
    eligible = [row for row in validation if row["release"] < selection]
    require([row["start"].month for row in eligible] == [1, 2], "availability cutoff")
    require(validation[2]["maturity"] < selection < validation[2]["release"],
            "mature but unavailable validation label")
    losses = lambda records, name: mean([(row["y"] - row[name]) ** 2 for row in records])
    eligible_losses = [losses(eligible, name) for name in "AB"]
    leaked_losses = [losses(validation, name) for name in "AB"]
    require(eligible_losses == [1, 0] and leaked_losses == [1, F(100, 3)],
            "validation leakage choice reversal")
    final_rows = [row for row in forecast_rows if row["role"] == "final test"]
    require([losses(final_rows, name) for name in "AB"] == [1, 4], "final scores")
    require(max(row["release"] for row in final_rows) == date(2024, 8, 31),
            "full final score release")
    counts = re.findall(r"E = (\d+), (?:unemployed )?U = (\d+) and (?:working-age population )?P = (\d+)", source)
    require(counts == [("240", "60", "400"), ("255", "45", "400")],
            "replication prompt counts changed")
    correct_rates = [100 * F(int(u), int(e) + int(u)) for e, u, _ in counts]
    old_wrong_rate = 100 * F(int(counts[0][1]), int(counts[0][2]))
    require(correct_rates == [20, 15] and old_wrong_rate == correct_rates[1],
            "vintage/denominator coincidence")
    results["D5"] = {"eligible_validation_months": [1, 2],
                     "eligible_MSE_A_B": [str(v) for v in eligible_losses],
                     "leaked_MSE_A_B": [str(v) for v in leaked_losses],
                     "selected_final_MSE": "4", "other_final_MSE": "1",
                     "full_score_after_release": "2024-08-31",
                     "vintage_rates_percent": [str(v) for v in correct_rates],
                     "old_wrong_denominator_percent": str(old_wrong_rate)}
    checks.append("D5: calendar-derived two-month maturity and release dates, "
                  "available-label selection, leakage reversal, separate final scores, "
                  "and original-versus-revised denominator reconstruction.")
    return {"status": "passed", "checks": checks, "results": results,
            "limitations": [
                "Numerical and snippet checks supplement the separate written solution/rubric review; they do not prove all prose claims.",
                "Synthetic data and mock releases are instructional; no actual empirical policy effect or official series is claimed.",
                "Causal exchangeability, ledger completeness, source authenticity and real forecasting performance are not established by these checks.",
                "Spreadsheet formulas are checked algebraically; no spreadsheet application, visual/mobile/print inspection or learner timing study was performed.",
                "The floating stress case assumes the stated binary64 environment; measured runtime behavior is not a guarantee for other numeric formats."
            ]}


if __name__ == "__main__":
    try:
        report = check()
    except Exception as error:
        print(json.dumps({"status": "failed", "error": str(error)}, indent=2))
        raise SystemExit(1)
    print(json.dumps(report, indent=2))
