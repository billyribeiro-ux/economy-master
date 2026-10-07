"""Independent rational arithmetic and behavior checks for v04-c06.

No third-party dependencies. check() returns status/checks/limitations.
Author checks complement, rather than replace, root's mathematical review.
"""

import contextlib
import copy
from fractions import Fraction as F
from html.parser import HTMLParser
import io
import itertools
import json
import math
from pathlib import Path
import random
import runpy
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
PROGRAM = ROOT / "content/projects/v04-c06-inventory.py"
CASE = ROOT / "content/projects/v04-c06-case.json"
CHAPTER = ROOT / "content/chapters/v04-c06.html"


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def close(actual, expected, message, tol=1e-8):
    require(math.isclose(actual, float(expected), rel_tol=1e-12, abs_tol=tol),
            message + ": " + str(actual) + " != " + str(expected))


def rejected(function, value):
    try:
        function(value)
    except (TypeError, ValueError):
        return
    raise AssertionError("invalid case was accepted")


class Manuscript(HTMLParser):
    def __init__(self):
        super().__init__()
        self.worked = 0
        self.exercise_count = 0
        self.solution_count = 0
        self.exercise_depth = 0
        self.solutions = False
        self.pre = False
        self.blocks = []
        self.buffer = []
        self.sources = set()
        self.links = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        require(tag not in {"html", "head", "body", "h1"}, "fragment wrapper")
        if tag == "aside" and attrs.get("class") == "worked":
            self.worked += 1
        if tag == "ol" and attrs.get("class") == "exercises":
            self.exercise_depth = 1
        elif tag == "ol" and self.exercise_depth:
            self.exercise_depth += 1
        if tag == "details" and attrs.get("class") == "solutions":
            self.solutions = True
        if tag == "li" and self.exercise_depth == 1:
            self.exercise_count += 1
        if tag == "li" and self.solutions:
            self.solution_count += 1
        if tag == "pre":
            self.pre = True
            self.buffer = []
        if "data-source" in attrs:
            self.sources.add(attrs["data-source"])
        if tag == "a":
            self.links.append(attrs.get("href", ""))

    def handle_endtag(self, tag):
        if tag == "ol" and self.exercise_depth:
            self.exercise_depth -= 1
        if tag == "details":
            self.solutions = False
        if tag == "pre":
            self.blocks.append("".join(self.buffer))
            self.pre = False

    def handle_data(self, text):
        if self.pre:
            self.buffer.append(text)


def check():
    checks = []
    output = io.StringIO()
    with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
        module = runpy.run_path(str(PROGRAM), run_name="v04_c06_checks")
    require(not output.getvalue(), "import has side effects")
    original = CASE.read_bytes()
    case = module["load_case"](CASE)
    saved = copy.deepcopy(case)
    report = module["simulate"](case)
    require(case == saved and CASE.read_bytes() == original, "mutated inputs")
    require(report == module["simulate"](case), "seed replay")
    require(report["draw_order"] == ["shared_demand", "independent_a", "independent_b"],
            "draw order metadata")
    require(report["shared_demand_counts"] == {"60": 2423, "90": 5029, "120": 2548},
            "baseline replay counts")
    checks.append("Quiet import, nonmutation, local seed replay and baseline draw-order/count contract")

    # Alternate deterministic payoff form; expand integer tickets to get an
    # exact uniform state space, independent of the program's weighted moments.
    tickets = [60, 90, 90, 120]

    def alternate_profit(demand, stock, c=case):
        return ((c["price_cents_per_unit"] - c["salvage_cents_per_unit"])
                * min(demand, stock)
                + (c["salvage_cents_per_unit"] - c["cost_cents_per_unit"]) * stock)

    a = [alternate_profit(d, 80) for d in tickets]
    b = [alternate_profit(d, 100) for d in tickets]
    paired = [y - x for x, y in zip(a, b)]
    independent = [y - x for x in a for y in b]

    def mean(xs):
        return sum(F(x) for x in xs) / len(xs)

    def variance(xs):
        return mean([F(x)**2 for x in xs]) - mean(xs)**2

    exact = module["exact_reference"](case)
    references = {
        "mean_a_cents": mean(a), "mean_b_cents": mean(b),
        "mean_delta_cents": mean(paired),
        "variance_a_cents2": variance(a), "variance_b_cents2": variance(b),
        "variance_paired_delta_cents2": variance(paired),
        "variance_independent_delta_cents2": variance(independent),
        "probability_b_worse_same_demand": F(sum(d < 0 for d in paired), 4),
    }
    require(exact == references, "exact moments versus expanded-ticket enumeration")
    require(mean(paired) == 2000 and variance(paired) == 50000000, "baseline targets")
    covariance = mean([x * y for x, y in zip(a, b)]) - mean(a) * mean(b)
    require(covariance == 125000000 and variance(independent) == 6 * variance(paired),
            "covariance and variance reduction")
    # Enumerate all 64 n=3 iid paired samples to verify expectation, variance
    # of the mean, and unbiased sample variance using exact arithmetic.
    sample_means = []
    sample_variances = []
    for sample in itertools.product(paired, repeat=3):
        mu = mean(sample)
        sample_means.append(mu)
        sample_variances.append(sum((F(x) - mu)**2 for x in sample) / 2)
    require(mean(sample_means) == mean(paired), "unbiased mean by sample enumeration")
    require(variance(sample_means) == variance(paired) / 3, "MC variance by enumeration")
    require(mean(sample_variances) == variance(paired), "n-1 correction by enumeration")
    checks.append("Exact four-ticket/16-state enumeration, alternate payoff algebra, covariance and 64 complete iid sample experiments")

    # Match the seeded transcript with a manual threshold/state lookup,
    # then use exact raw sums for both sample summaries.
    rng = random.Random(20261006)
    a_lookup = {60: 28000, 90: 48000, 120: 48000}
    b_lookup = {60: 20000, 90: 50000, 120: 60000}
    pair_values, ind_values = [], []
    def lookup(u):
        return (60, 90, 120)[int(u >= .25) + int(u >= .75)]
    for _ in range(10000):
        d1, d2, d3 = [lookup(rng.random()) for _ in range(3)]
        pair_values.append(b_lookup[d1] - a_lookup[d1])
        ind_values.append(b_lookup[d3] - a_lookup[d2])
    for key, values, expected_mean in (("paired", pair_values, 2125),
                                        ("independent", ind_values, 2112)):
        n = len(values)
        mu = mean(values)
        s2 = (sum(F(x)**2 for x in values) - n * mu**2) / (n - 1)
        se = math.sqrt(s2 / n)
        require(mu == expected_mean, key + " transcript mean")
        close(report[key]["mean_delta_cents"], mu, key + " mean")
        close(report[key]["sample_variance_delta_cents2"], s2, key + " sample variance")
        close(report[key]["estimated_mc_se_cents"], se, key + " SE")
        for actual, target in zip(report[key]["approximate_95pct_mc_interval_cents"],
                                  [float(mu) - 1.96 * se, float(mu) + 1.96 * se]):
            close(actual, target, key + " interval")
    require(abs(report["paired"]["mean_delta_cents"] - 2000)
            > abs(report["independent"]["mean_delta_cents"] - 2000),
            "realized accuracy is not guaranteed by variance reduction")
    checks.append("Seeded transcript reconstructed with alternate thresholds/payoff lookup and exact raw-moment sample summaries")

    # Supported economic cases: deterministic support, equal policies,
    # all-zero stock, arbitrary weights and the stated sensitivity.
    deterministic = copy.deepcopy(case)
    deterministic.update(demand_weights=[0, 1, 0], replications=20)
    deterministic_report = module["simulate"](deterministic)
    for method in ("paired", "independent"):
        require(deterministic_report[method]["mean_delta_cents"] == 2000,
                "deterministic payoff")
        require(deterministic_report[method]["estimated_mc_se_cents"] == 0,
                "deterministic variance")
    equal = copy.deepcopy(case)
    equal.update(stock_a_units=100, replications=100)
    equal_report = module["simulate"](equal)
    require(equal_report["paired"]["mean_delta_cents"] == 0
            and equal_report["paired"]["estimated_mc_se_cents"] == 0,
            "identical policies paired identity")
    require(equal_report["independent"]["sample_variance_delta_cents2"] > 0,
            "independent worlds need not have identical profits")
    for stocks in [(0, 0), (0, 100), (100, 80), (1000000, 1000000)]:
        scenario = copy.deepcopy(case)
        scenario.update(stock_a_units=stocks[0], stock_b_units=stocks[1], replications=10)
        scenario["demand_weights"] = [3, 0, 2]
        ref = module["exact_reference"](scenario)
        ticket_differences = [alternate_profit(d, stocks[1]) - alternate_profit(d, stocks[0])
                              for d in [60, 60, 60, 120, 120]]
        require(ref["mean_delta_cents"] == mean(ticket_differences), "stock boundary mean")
        require(ref["variance_paired_delta_cents2"] == variance(ticket_differences),
                "stock boundary variance")
        module["simulate"](scenario)
    sensitivity = copy.deepcopy(case)
    sensitivity["demand_weights"] = [2, 1, 1]
    sensitivity_ref = module["exact_reference"](sensitivity)
    require(sensitivity_ref["mean_delta_cents"] == -500
            and sensitivity_ref["variance_paired_delta_cents2"] == 68750000,
            "sensitivity ranking reversal")
    for u, target in [(0, 60), (.249999, 60), (.25, 90), (.749999, 90),
                       (.75, 120), (math.nextafter(1.0, 0), 120)]:
        require(module["demand_from_u"](u, case) == target, "half-open CDF boundary")
    for u in [True, "0.5", -0.1, 1, float("nan"), float("inf")]:
        rejected(lambda value: module["demand_from_u"](value, case), u)
    checks.append("Deterministic support, equal policies, stock bounds, reversed policies, zero-weight support, CDF thresholds and sensitivity reversal")

    # Chapter exercises; exact arithmetic first, approximate displays second.
    first = [10] * 45 + [30] * 55
    revised = [10] * 40 + [30] * 60
    require(mean(first) == 21 and sum((F(x) - 21)**2 for x in first) == 9900,
            "worked example 1 moments")
    require(mean(revised) == 22 and sum((F(x) - 22)**2 for x in revised) == 9600,
            "exercise 3 moments")
    revised_se = math.sqrt(F(9600, 9900))
    close(revised_se, .9847319278, "exercise 3 SE", tol=1e-9)
    close(22 - 1.96 * revised_se, 20.0699254215, "exercise 3 lower", tol=1e-9)
    close(2 / revised_se, 2.0310096012, "exercise 3 standardized error", tol=1e-9)
    require(math.ceil((1.96 * 10 / .5)**2) == 1537
            and math.ceil((1.96 * 30)**2) == 3458, "sample-size plans")
    close(72 - 1.96 * 1.5, 69.06, "exercise 2 interval")
    for n in [1000, 2000]:
        # expm1 avoids cancellation; power formula checks the derived endpoint.
        bound = -math.expm1(math.log(.05) / n)
        close((1 - bound)**n, .05, "rare-event bound inversion", tol=1e-12)
    close(.999**2000, .1351999254, "zero-count probability", tol=1e-9)
    require(variance([d - 2500 for d in paired]) == variance(paired)
            and mean([d - 2500 for d in paired]) == -500, "fee shift")
    require(variance(paired) / 2500 == 20000
            and variance(independent) / 15000 == 20000, "equal target precision")
    # Antithetic indicator is exactly 1/2 on two fifths of the unit interval.
    z = [F(1, 2), 0, 0, 0, F(1, 2)]
    require(mean(z) == F(1, 5) and variance(z) == F(3, 50), "antithetic indicator")
    require(F(4, 25) / 2 == F(2, 25), "independent antithetic benchmark")
    for u in [F(0), F(1, 5), F(1, 2), F(4, 5), F(1)]:
        require(((100 + 40 * u) + (100 + 40 * (1-u))) / 2 == 120,
                "linear antithetic cancellation")
        require((u-F(1,2))**2 == ((1-u)-F(1,2))**2, "nonmonotone reflection")
    checks.append("Both worked examples and every numerical exercise: precision plans, rare-event inversion, fee shift and antithetic finite-state identities")

    invalid = []
    for key, value in [
        ("replications", True), ("replications", 1), ("replications", 200001),
        ("replications", "100"), ("replications", 2.0),
        ("seed", -1), ("seed", 2**64), ("currency", "EUR"), ("period", "month"),
        ("demand_units", [90, 60]), ("demand_units", [60, 60, 120]),
        ("demand_units", [60, 90, 1000001]), ("demand_weights", [0, 0, 0]),
        ("demand_weights", [1, -1, 1]), ("demand_weights", [1, 1]),
        ("demand_weights", [True, 2, 1]), ("price_cents_per_unit", float("inf")),
        ("cost_cents_per_unit", float("nan")), ("stock_a_units", -1),
        ("salvage_cents_per_unit", 601), ("price_cents_per_unit", 599),
        ("case_id", ""), ("provenance", 4),
    ]:
        c = copy.deepcopy(case)
        c[key] = value
        invalid.append(c)
    missing = copy.deepcopy(case)
    del missing["seed"]
    extra = copy.deepcopy(case)
    extra["unknown"] = 7
    invalid += [missing, extra, [], None]
    for c in invalid:
        rejected(module["validate_case"], c)

    with tempfile.TemporaryDirectory(prefix="v04-c06-") as temporary:
        task_dir = Path(temporary)
        source_dir = task_dir / "program"
        source_dir.mkdir()
        other_dir = task_dir / "other"
        other_dir.mkdir()
        script = source_dir / PROGRAM.name
        data = source_dir / CASE.name
        shutil.copyfile(PROGRAM, script)
        data.write_bytes(original)
        result = subprocess.run([sys.executable, str(script)], cwd=other_dir,
                                capture_output=True, text=True, check=False)
        require(result.returncode == 0 and not result.stderr, "portable CLI")
        require(json.loads(result.stdout) == report, "portable report parity")
        require(data.read_bytes() == original, "portable input unchanged")
        documents = [json.dumps(c) for c in invalid]
        documents += [original.decode().replace('"seed": 20261006',
                       '"seed": 1, "seed": 20261006'), "{", '{"seed": NaN}',
                      original.decode().replace('"seed": 20261006', '"seed": 1e10000')]
        for document in documents:
            data.write_text(document, encoding="utf-8")
            for optimized in [False, True]:
                command = [sys.executable] + (["-O"] if optimized else []) + [str(script)]
                result = subprocess.run(command, cwd=other_dir, capture_output=True,
                                        text=True, check=False)
                require(result.returncode == 1 and not result.stdout
                        and result.stderr.startswith("Cannot simulate:"), "explicit invalid CLI failure")
        data.write_bytes(b"\xff")
        result = subprocess.run([sys.executable, str(script)], cwd=other_dir,
                                capture_output=True, text=True, check=False)
        require(result.returncode == 1 and not result.stdout, "invalid encoding failure")
        data.unlink()
        result = subprocess.run([sys.executable, str(script)], cwd=other_dir,
                                capture_output=True, text=True, check=False)
        require(result.returncode == 1 and not result.stdout, "missing file failure")
    checks.append(str(len(invalid)) + " direct invalid contracts and " + str(len(documents))
                  + " malformed/invalid CLI documents rejected normally and under -O; missing/encoding failure and cross-directory run")

    manuscript = Manuscript()
    source = CHAPTER.read_text(encoding="utf-8")
    manuscript.feed(source)
    require(manuscript.worked >= 2 and manuscript.exercise_count == 8
            and manuscript.solution_count == 8, "required package structure")
    sources = json.loads((ROOT / "content/reviews/v04-c06-sources.json").read_text())
    require(manuscript.sources == {item["id"] for item in sources}, "source coverage")
    for link in manuscript.links:
        if link.startswith("v04-c06-"):
            require("/" not in link and (ROOT / "content/projects" / link).is_file(),
                    "flat download path")
    require("Teach-back:" in source and "Delayed check:" in source, "retention structure")
    require(len(manuscript.blocks) == 4, "instructional blocks")
    scope = {}
    exec(compile(manuscript.blocks[0], "chapter-sampler", "exec"), scope)
    first_five = scope["demands"]
    check_rng = random.Random(20261006)
    require(first_five == [lookup(check_rng.random()) for _ in range(5)], "sampler snippet")
    require(manuscript.blocks[1].strip() == "python3 v04-c06-inventory.py", "CLI block")
    scope.update(paired=[], shared=60, case=case, profit_cents=module["profit_cents"])
    exec(compile(manuscript.blocks[2], "chapter-paired-core", "exec"), scope)
    require(scope["paired"] == [-8000], "paired core snippet")
    exec(compile(manuscript.blocks[3], "chapter-solution", "exec"), scope)
    require(scope["five_demands"] == first_five, "seed exercise snippet")
    checks.append("Two worked examples, eight complete solution entries, source/download alignment and all three Python snippets executed; shell command checked")

    return {
        "status": "passed",
        "checks": checks,
        "limitations": [
            "Finite executable tests do not prove model validity, every modified case or exact normal-interval coverage.",
            "PRNG independence is an idealized sampling model; the seeded transcript is a reproducibility check.",
            "Specialist author review is not independent human assessment; root integration and dependency acceptance remain separate.",
            "Browser visual/mobile/print QA remains pending after the recorded policy rejection; no workaround attempted.",
        ],
    }


if __name__ == "__main__":
    print(json.dumps(check(), indent=2))
