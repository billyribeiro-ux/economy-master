"""Independent arithmetic, instructional-code and behavior checks for v04-c03.

No third-party packages. check() returns an integration-friendly dictionary.
Assertions in learner snippets are exercised normally; this checker's own
require() gates remain active even if someone launches this checker with -O.
"""

import contextlib
from fractions import Fraction as F
from html.parser import HTMLParser
import io
import json
import math
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
PROGRAM = ROOT / "content/projects/v04-c03-cashflow.py"
CASE = ROOT / "content/projects/v04-c03-case.json"
CHAPTER = ROOT / "content/chapters/v04-c03.html"


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def expect_error(function, args, error_type):
    try:
        function(*args)
    except error_type:
        return
    raise AssertionError("expected " + error_type.__name__)


def rational_value(flows, bps):
    """Independent backwards Horner recurrence, using exact fractions."""
    growth = F(10000 + bps, 10000)
    value = F(0)
    for cash in reversed(flows):
        value = value / growth + cash
    return value


class Manuscript(HTMLParser):
    def __init__(self):
        super().__init__()
        self.pre = False
        self.buffer = []
        self.blocks = []
        self.worked = 0
        self.exercise_depth = 0
        self.solution_depth = 0
        self.exercise_count = 0
        self.solution_count = 0
        self.sources = set()
        self.links = []
        self.forbidden = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in {"html", "body", "h1"}:
            self.forbidden.append(tag)
        if "data-source" in attrs:
            self.sources.add(attrs["data-source"])
        if tag == "a":
            self.links.append(attrs.get("href", ""))
        if tag == "aside" and attrs.get("class") == "worked":
            self.worked += 1
        if tag == "ol" and attrs.get("class") == "exercises":
            self.exercise_depth = 1
        elif tag == "ol" and self.exercise_depth:
            self.exercise_depth += 1
        if tag == "details" and attrs.get("class") == "solutions":
            self.solution_depth = 1
        if tag == "li" and self.exercise_depth == 1:
            self.exercise_count += 1
        if tag == "li" and self.solution_depth:
            self.solution_count += 1
        if tag == "pre":
            self.pre = True
            self.buffer = []

    def handle_endtag(self, tag):
        if tag == "ol" and self.exercise_depth:
            self.exercise_depth -= 1
        if tag == "details":
            self.solution_depth = 0
        if tag == "pre":
            self.blocks.append("".join(self.buffer))
            self.pre = False

    def handle_data(self, data):
        if self.pre:
            self.buffer.append(data)


def check():
    checks = []
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        namespace = runpy.run_path(str(PROGRAM), run_name="v04_c03_checks")
    require(not stdout.getvalue() and not stderr.getvalue(),
            "importing the program must have no output")
    npv = namespace["npv_cents"]
    loader = namespace["load_case"]
    case_bytes = CASE.read_bytes()
    case = loader(CASE)
    report = namespace["make_report"](case)
    baseline = F(430000, 121)
    require(rational_value(case["cash_flows_cents"], 1000) == baseline,
            "exact baseline recurrence")
    require(math.isclose(report["npv_cents_approx"], float(baseline),
                         rel_tol=0, abs_tol=1e-8), "baseline NPV")
    require(report["undiscounted_net_cents"] == 30000 and
            report["npv_dollars_display"] == "35.54" and
            report["last_period"] == 3, "baseline report")
    checks.append("Import without file/output side effects; exact rational baseline 430000/121 cents, 30000-cent undiscounted net, 35.54 USD display and three-year horizon")

    # The independent reference uses a backwards recurrence, not the
    # program's forward powers, and retains exact rational inputs.
    reference_cases = 0
    for bps in [-5000, -1000, 0, 1, 500, 1000, 10000]:
        for flows in [[0], [12345], [-10000, 12100],
                      [-60000, 25000, 25000, 25000],
                      [-10000, 5500, 6050],
                      [10**12] * 101,
                      [(-1)**i * 10**12 for i in range(101)]]:
            snapshot = flows.copy()
            exact = rational_value(flows, bps)
            actual = npv(flows, bps)
            # Scale-aware check includes cancellation; it is a numerical
            # diagnostic, not a universal forward-error proof.
            scale = sum(F(abs(c)) / F(10000 + bps, 10000)**i
                        for i, c in enumerate(flows))
            bound = max(1e-8, 2e-12 * float(scale))
            require(math.isfinite(actual) and abs(actual - float(exact)) <= bound,
                    "rational grid mismatch")
            require(flows == snapshot, "NPV mutated its input")
            reference_cases += 1
    require(rational_value([-60000, 25000, 25000, 25000], 500) ==
            F(74840000, 9261), "exercise 6 exact NPV")
    require(f"{npv([-60000, 25000, 25000, 25000], 500)/100:.2f}" == "80.81",
            "exercise 6 display")
    require(rational_value([-10000, 5500, 6050], 1000) == 0 and
            rational_value([-10000, 9000], -1000) == 0,
            "cancellation and negative-rate retention cases")
    require(rational_value([-10000, 12100], 1000) == 1000,
            "independent one-period case")
    checks.append(f"{reference_cases} independent exact-rational/backwards-recurrence comparisons, including rate/horizon/magnitude boundaries, cancellation, negative rates and unmodified inputs")

    invalid_args = [
        ((None, 1000), TypeError), (((1, 2), 1000), TypeError),
        (([], 1000), ValueError), (([0] * 102, 1000), ValueError),
        (([True], 1000), TypeError), (([False], 1000), TypeError),
        (([1.0], 1000), TypeError), ((["100"], 1000), TypeError),
        (([None], 1000), TypeError), (([float("nan")], 1000), TypeError),
        (([float("inf")], 1000), TypeError),
        (([10**12 + 1], 1000), ValueError),
        (([-10**12 - 1], 1000), ValueError),
        (([100], True), TypeError), (([100], 1000.0), TypeError),
        (([100], "1000"), TypeError), (([100], float("nan")), TypeError),
        (([100], -5001), ValueError), (([100], 10001), ValueError),
        (([100], -10000), ValueError),
    ]
    for args, error_type in invalid_args:
        expect_error(npv, args, error_type)
    checks.append(f"{len(invalid_args)} direct function failures: wrong collection, empty/excessive horizon, booleans, strings, fractional/null/nonfinite numbers, excessive cents and unsupported rates")

    # Execute the actual supplied CLI from a different directory. The temp
    # source copy allows destructive input experiments without touching data.
    with tempfile.TemporaryDirectory(prefix="v04-c03-") as directory:
        temporary = Path(directory)
        program_dir = temporary / "download"
        program_dir.mkdir()
        copied = program_dir / PROGRAM.name
        shutil.copyfile(PROGRAM, copied)
        input_path = program_dir / CASE.name
        input_path.write_bytes(case_bytes)
        for optimization in [[], ["-O"]]:
            process = subprocess.run([sys.executable] + optimization + [str(copied)],
                                     cwd=temporary, capture_output=True, text=True,
                                     check=False, timeout=15)
            require(process.returncode == 0 and not process.stderr,
                    "valid CLI failed")
            require(json.loads(process.stdout) == report,
                    "CLI report differs from reference")
        invalid_documents = ["{", "[]", "null", "{}"]
        for key, bad in [
            ("discount_rate_bps", "1000"), ("discount_rate_bps", True),
            ("discount_rate_bps", 10001), ("cash_flows_cents", []),
            ("cash_flows_cents", [True]), ("cash_flows_cents", [1.25]),
            ("cash_flows_cents", [None]), ("cash_flows_cents", [float("nan")]),
            ("cash_flows_cents", [float("inf")]),
            ("period", "month"), ("currency", "EUR"), ("currency", 1),
            ("timing", "year_start"), ("case_id", "  "),
            ("provenance", None),
        ]:
            altered = case.copy()
            altered[key] = bad
            invalid_documents.append(json.dumps(altered))
        missing = case.copy()
        del missing["cash_flows_cents"]
        invalid_documents.append(json.dumps(missing))
        extra = case.copy()
        extra["discount_rate_percent"] = 10
        invalid_documents.append(json.dumps(extra))
        invalid_documents.append(case_bytes.decode().replace(
            '"discount_rate_bps": 1000',
            '"discount_rate_bps": 500, "discount_rate_bps": 1000'))
        for document in invalid_documents:
            input_path.write_text(document, encoding="utf-8")
            # The same invalid external input must fail with asserts removed.
            for optimization in [[], ["-O"]]:
                process = subprocess.run(
                    [sys.executable] + optimization + [str(copied)],
                    cwd=temporary, capture_output=True, text=True,
                    check=False, timeout=15)
                require(process.returncode == 1 and not process.stdout and
                        process.stderr.startswith("Input error: "),
                        "invalid CLI input was not explicitly rejected")
        input_path.write_bytes(b"\xff")
        bad_encoding = subprocess.run([sys.executable, str(copied)], cwd=temporary,
                                      capture_output=True, text=True, timeout=15)
        require(bad_encoding.returncode == 1 and not bad_encoding.stdout and
                "Input error: " in bad_encoding.stderr, "UTF-8 validation")
        input_path.unlink()
        missing_file = subprocess.run([sys.executable, str(copied)], cwd=temporary,
                                      capture_output=True, text=True, timeout=15)
        require(missing_file.returncode == 1 and not missing_file.stdout and
                "Input error: " in missing_file.stderr, "missing-file handling")
    require(CASE.read_bytes() == case_bytes, "original data changed")
    checks.append(f"CLI from an unrelated working directory, with and without -O; {len(invalid_documents)} malformed/schema/unit/type/duplicate cases rejected in both modes; invalid UTF-8 and missing file fail explicitly; original input unchanged")

    # Independent integer reconciliation and the requested sensitivity.
    quantities = [3, 5, 2]
    prices = [1250, 800, 1500]
    unit_costs = [600, 300, 700]
    sales = sum(q * p for q, p in zip(quantities, prices))
    variable = sum(q * c for q, c in zip(quantities, unit_costs))
    margins = sum(q * (p - c) for q, p, c in zip(quantities, prices, unit_costs))
    require((sales, variable, margins, margins - 2500) ==
            (10750, 4700, 6050, 3550), "worked order reconciliation")
    require((sales + 4 * 900, variable + 4 * 500,
             margins + 4 * 400, margins + 4 * 400 - 2500,
             margins + 4 * 400 - 3500) ==
            (14350, 6700, 7650, 5150, 4150), "order sensitivity")
    require([7/2, 7//2, 7%2, "7"*2, int("7")+2] == [3.5, 3, 1, "77", 9],
            "types exercise")
    growth = F(11, 10)
    flows = [120, -30, 10]
    shifted = sum(F(c) / growth**(t + 1) for t, c in enumerate(flows))
    require(shifted == rational_value(flows, 1000) / growth,
            "one-period timing error")
    checks.append("Independent order-by-order integer reconciliation, new-order/fixed-cost sensitivity, type expressions and exact shifted-timeline factor")

    manuscript = Manuscript()
    manuscript.feed(CHAPTER.read_text(encoding="utf-8"))
    require(manuscript.worked == 2 and manuscript.exercise_count == 8 and
            manuscript.solution_count == 8 and not manuscript.forbidden,
            "chapter fragment structure")
    proposed = json.loads((ROOT / "content/reviews/v04-c03-sources.json").read_text())
    require(manuscript.sources == {entry["id"] for entry in proposed},
            "source IDs differ from proposed catalogue")
    for link in manuscript.links:
        if link.startswith("v04-c03-"):
            require((ROOT / "content/projects" / link).is_file(),
                    "download target missing: " + link)
    # Execute instructional blocks in their presented order. We supply the
    # downloaded validator before its abbreviated pedagogical NPV definition.
    lesson = {"__file__": str(PROGRAM), "__name__": "lesson_checks",
              "validate_values": namespace["validate_values"]}
    executed = 0
    for block in manuscript.blocks:
        if block.strip().startswith("python3 "):
            continue
        with contextlib.redirect_stdout(io.StringIO()):
            exec(compile(block, str(CHAPTER), "exec"), lesson)
        executed += 1
    require(lesson["margin_cents"](100, 250) == -150 and
            lesson["margin_cents"](0, 0) == 0, "signed margin boundary")
    for amount, error in [(True, TypeError), ("100", TypeError), (-1, ValueError)]:
        expect_error(lesson["margin_cents"], (amount, 0), error)
    flows = [100, -20, 5]
    capture = io.StringIO()
    with contextlib.redirect_stdout(capture):
        answer = lesson["broken_total"](flows)
    require(answer is None and flows == [100, -20, 5, 5] and
            capture.getvalue().strip() == "5", "broken function critique")
    fresh = [100, -20, 5]
    require(lesson["total_cents"](fresh) == 85 and fresh == [100, -20, 5],
            "corrected function purity")
    require(lesson["profit_cents"] == 3550, "worked order code output")
    checks.append(f"Executed all {executed} Python instructional/solution blocks in order; checked intended broken behavior, pure repair, signed/invalid margin boundaries, two worked examples, eight exercises/eight solutions, source IDs and download targets")
    return {
        "status": "passed",
        "checks": checks,
        "limitations": [
            "Numerical grids and CLI tests are finite behavioral evidence, not a proof for every input or economic assumption.",
            "The program deliberately uses approximate floats for discounted values and bounded synthetic USD annual inputs; it is not a settlement engine or hostile-input service.",
            "Author review only; root integration/dependency acceptance and independent human evaluation remain separate.",
            "Visual/mobile/print QA was not attempted after the existing browser-policy rejection.",
        ],
    }


if __name__ == "__main__":
    print(json.dumps(check(), indent=2))
