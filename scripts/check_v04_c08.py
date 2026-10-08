"""Independent exact arithmetic, enumeration and manuscript checks for v04-c08."""

import contextlib
import copy
from fractions import Fraction as F
from html.parser import HTMLParser
import io
import json
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
PROGRAM = ROOT / "content/projects/v04-c08-identification.py"
CASE = ROOT / "content/projects/v04-c08-cases.json"
CHAPTER = ROOT / "content/chapters/v04-c08.html"


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def expect_invalid(function, value):
    try:
        function(value)
    except (TypeError, ValueError):
        return
    raise AssertionError("invalid case was accepted")


class Structure(HTMLParser):
    def __init__(self):
        super().__init__()
        self.worked = 0
        self.exercise_depth = 0
        self.solution_depth = 0
        self.exercises = 0
        self.solutions = 0
        self.sources = set()
        self.links = []
        self.forbidden = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ("html", "body", "h1", "script"):
            self.forbidden.append(tag)
        if tag == "aside" and attrs.get("class") == "worked":
            self.worked += 1
        if tag == "ol" and attrs.get("class") == "exercises":
            self.exercise_depth = 1
        elif tag == "ol" and self.exercise_depth:
            self.exercise_depth += 1
        if tag == "details" and attrs.get("class") == "solutions":
            self.solution_depth = 1
        if tag == "li" and self.exercise_depth == 1:
            self.exercises += 1
        if tag == "li" and self.solution_depth:
            self.solutions += 1
        if "data-source" in attrs:
            self.sources.add(attrs["data-source"])
        if tag == "a":
            self.links.append(attrs.get("href", ""))

    def handle_endtag(self, tag):
        if tag == "ol" and self.exercise_depth:
            self.exercise_depth -= 1
        if tag == "details":
            self.solution_depth = 0


def weighted_training(groups):
    """Direct grouped identities independent of the program's expansion."""
    n = sum(g["n"] for g in groups)
    nt = sum(g["treated"] for g in groups)
    nc = n - nt
    ate = sum(F(g["n"], n) * (g["y1"] - g["y0"]) for g in groups)
    att = sum(F(g["treated"], nt) * (g["y1"] - g["y0"]) for g in groups) if nt else None
    mt = F(sum(g["treated"] * g["y1"] for g in groups), nt) if nt else None
    mc = F(sum((g["n"] - g["treated"]) * g["y0"] for g in groups), nc) if nc else None
    baseline = F(sum(g["treated"] * g["y0"] for g in groups), nt) - mc if nt and nc else None
    return ate, att, mt - mc if nt and nc else None, baseline


def bitmask_lottery(workers, n1):
    """Enumerate masks, not itertools.combinations; independently form contrast."""
    n = len(workers)
    contrasts = []
    for mask in range(1 << n):
        chosen = [(mask >> i) & 1 for i in range(n)]
        if sum(chosen) != n1:
            continue
        value = sum(F(chosen[i] * workers[i]["y1"], n1)
                    - F((1 - chosen[i]) * workers[i]["y0"], n - n1) for i in range(n))
        contrasts.append(value)
    return contrasts


def check():
    captured = io.StringIO()
    with contextlib.redirect_stdout(captured), contextlib.redirect_stderr(captured):
        module = runpy.run_path(str(PROGRAM))
    require(captured.getvalue() == "", "import should perform no output")
    original_bytes = CASE.read_bytes()
    case = module["load_case"](CASE)
    before = copy.deepcopy(case)
    report = module["build_report"](case)
    require(case == before, "analysis mutated case")

    training = report["training"]
    require((training["synthetic_ate"], training["synthetic_att"], training["observable_gap"],
             training["synthetic_selection_term"]) == (F(4), F(26, 5), F(-34, 5), F(-12)),
            "baseline training values")
    require(training["standardized_all"]["value"] == 4 and training["standardized_treated"]["value"] == F(26, 5),
            "target-specific standardization")
    grid = 0
    for n0 in (2, 3, 5):
        for n1 in (2, 4):
            for t0 in range(n0 + 1):
                for t1 in range(n1 + 1):
                    groups = [{"x": 0, "n": n0, "treated": t0, "y0": -3, "y1": 2},
                              {"x": 1, "n": n1, "treated": t1, "y0": 7, "y1": 4}]
                    actual = module["training_report"](groups)
                    expected = weighted_training(groups)
                    require(tuple(actual[k] for k in ("synthetic_ate", "synthetic_att", "observable_gap",
                                                       "synthetic_selection_term")) == expected, "grouped training grid")
                    if expected[2] is not None:
                        require(expected[1] + expected[3] == expected[2], "selection identity")
                    supported = 0 < t0 < n0 and 0 < t1 < n1
                    require(actual["standardized_all"]["value"] == (expected[0] if supported else None),
                            "full target missing support")
                    treated_supported = (t0 + t1 > 0 and t0 < n0 and t1 < n1)
                    require(actual["standardized_treated"]["value"] == (expected[1] if treated_supported else None),
                            "treated target support differs from ATE")
                    grid += 1
    exercise_groups = copy.deepcopy(case["training_groups"])
    exercise_groups[0]["treated"], exercise_groups[1]["treated"] = 30, 20
    require(weighted_training(exercise_groups) == (F(4), F(22, 5), F(2, 5), F(-4)), "exercise 2")
    require(F(30 * 26 + 20 * 42, 50) == F(162, 5) and F(20 * 20 + 30 * 40, 50) == 32,
            "exercise 2 observed levels")
    require(F(1, 4) * 8 + F(3, 4) * 4 == 5 and F(1, 2) * (8 + 4) == 6, "exercise 3 targets")
    require(F(18 + 3 * 28, 4) == F(51, 2) and F(10 + 3 * 24, 4) == F(41, 2),
            "exercise 3 standardized levels")

    lottery = report["lottery"]
    require([r["difference"] for r in lottery["assignments"]] == [-17, -6, 5, 5, 16, 27], "lottery table")
    require(lottery["assignment_mean"] == 5 and lottery["assignment_variance"] == F(605, 3), "lottery moments")
    require([r["baseline_difference"] for r in lottery["assignments"]] == [-20, -10, 0, 0, 10, 20], "baseline balance")
    lottery_cases = 0
    for n in range(2, 8):
        workers = [{"id": str(i), "y0": i * i - 3, "y1": 4 - 2 * i} for i in range(n)]
        truth = F(sum(w["y1"] - w["y0"] for w in workers), n)
        for n1 in range(1, n):
            current = module["lottery_report"]({"workers": workers, "treated_count": n1})
            contrasts = bitmask_lottery(workers, n1)
            require(sorted(r["difference"] for r in current["assignments"]) == sorted(contrasts), "mask enumeration")
            require(current["assignment_mean"] == truth, "finite lottery unbiasedness")
            require(current["assignment_variance"] == sum((v - truth) ** 2 for v in contrasts) / len(contrasts),
                    "lottery exact variance")
            lottery_cases += 1

    mediation = report["mediation"]
    require(mediation["synthetic_total_effect"] == 11 and mediation["randomized_observed_gap"] == 11,
            "baseline mediated total")
    require(mediation["synthetic_controlled_direct_effect"] == 3 and mediation["observed_gap_at_controlled_m"] == 3,
            "baseline controlled direct and observed overlap")
    require(all(r["y"] == 10 + 3 * r["d"] + 4 * r["m"] for r in mediation["rows"]),
            "exact mediator regression zero residuals")
    # The three design rows (1,0,0), (1,0,1), (1,1,2) have determinant -1;
    # the exact-fit coefficients are therefore unique.
    require(all(any((r["d"], r["m"]) == pair for r in mediation["rows"]) for pair in [(0, 0), (0, 1), (1, 2)]),
            "mediator regression contains full-rank design subset")
    modified = {"u_values": [0, 1, 2, 3, 4], "intercept": 5, "d_to_m": 3, "direct": 2,
                "m_to_y": 2, "controlled_m": 3}
    exercise = module["mediation_report"](modified)
    require(exercise["synthetic_total_effect"] == 8 and exercise["observed_gap_at_controlled_m"] == 2, "exercise 6")
    require(F(sum(r["y"] for r in exercise["rows"] if r["d"] == 0), 5) == 9, "exercise 6 control mean")
    require(F(sum(r["y"] for r in exercise["rows"] if r["d"] == 1), 5) == 17, "exercise 6 treated mean")
    modified["controlled_m"] = 100
    unsupported = module["mediation_report"](modified)
    require(unsupported["synthetic_controlled_direct_effect"] == 2 and unsupported["observed_gap_at_controlled_m"] is None,
            "structural direct effect distinguished from observed support")

    collider = report["collider"]
    require([(r["n"], r["mean_y"]) for r in collider["cells"]] == [(3, F(34, 3)), (1, F(10)),
              (1, F(14)), (3, F(38, 3))], "collider exact cells")
    require(collider["synthetic_ate"] == collider["observable_gap"] == 0, "collider raw versus truth")
    require(collider["standardized_on_c"]["value"] == F(-4, 3), "collider adjusted bias")
    selected = [(r["a"], r["b"], r["e"]) for r in collider["rows"] if r["x"] == 1]
    require(selected == [(0, 1, 1), (1, 0, 1), (1, 1, 0), (1, 1, 1)], "exercise 7 selected triples")
    # Independent conditional distribution: P(B=1|D=1,C=1)=2/3;
    # P(B=1|D=0,C=1)=1. Both treatment states exist.
    require(4 * (F(2, 3) - 1) == F(-4, 3), "collider probability derivation")
    no_y_effect = module["collider_report"]({"threshold": 2, "intercept": 10, "b_to_y": 0})
    require(no_y_effect["standardized_on_c"]["value"] == 0, "degenerate harmless collider case")
    for threshold in (1, 3):
        missing = module["collider_report"]({"threshold": threshold, "intercept": 10, "b_to_y": 4})
        require(missing["standardized_on_c"]["value"] is None, "collider support boundary")

    worlds = report["observational_equivalence"]
    require(worlds["same_observed_distribution"], "worlds not observationally equivalent")
    require([w["synthetic_ate"] for w in worlds["worlds"]] == [10, 0, -10], "world causal effects")
    require(all(w["observed"] == [{"d": 0, "y": 20}, {"d": 1, "y": 30}] for w in worlds["worlds"]),
            "world observations")
    altered = copy.deepcopy(case["equivalent_worlds"])
    altered[-1]["effect"] = -9
    require(not module["worlds_report"](altered)["same_observed_distribution"], "equivalence not hardcoded")

    invalid = []
    def bad(path, value):
        item = copy.deepcopy(case)
        place = item
        for key in path[:-1]:
            place = place[key]
        place[path[-1]] = value
        invalid.append(item)
    bad(["schema_version"], True)
    bad(["outcome_unit"], "USD per month")
    bad(["training_groups", 0, "treated"], True)
    bad(["training_groups", 0, "treated"], 51)
    bad(["training_groups", 0, "n"], 0)
    bad(["training_groups", 1, "x"], 0)
    bad(["training_groups", 0, "y0"], 20.0)
    bad(["lottery", "treated_count"], 0)
    bad(["lottery", "treated_count"], 4)
    bad(["lottery", "workers", 1, "id"], "A")
    bad(["mediation", "u_values"], [0, 0])
    bad(["mediation", "direct"], "3")
    bad(["collider", "threshold"], 4)
    bad(["equivalent_worlds", 1, "name"], "A")
    for item in invalid:
        expect_invalid(module["validate_case"], item)
    with tempfile.TemporaryDirectory(prefix="v04-c08-") as directory:
        for optimized in (False, True):
            command = [sys.executable] + (["-O"] if optimized else []) + [str(PROGRAM)]
            result = subprocess.run(command, cwd=directory, text=True, capture_output=True, check=False)
            require(result.returncode == 0 and not result.stderr, "default CLI from unrelated directory")
            require(json.loads(result.stdout)["training"]["observable_gap"] == "-34/5", "CLI exact fraction")
            for index, document in enumerate([json.dumps(x) for x in invalid] + [
                    '{"schema_version":1,"schema_version":1}', '{"value":NaN}', '{']):
                path = Path(directory) / (str(index) + ".json")
                path.write_text(document, encoding="utf-8")
                failed = subprocess.run(command + [str(path)], cwd=directory, text=True, capture_output=True, check=False)
                require(failed.returncode != 0 and not failed.stdout and "Cannot compute synthetic case" in failed.stderr,
                        "invalid CLI document must fail without numeric output")
            missing = subprocess.run(command + [str(Path(directory) / "absent.json")], text=True, capture_output=True, check=False)
            require(missing.returncode != 0 and not missing.stdout, "missing file diagnostic")
    require(CASE.read_bytes() == original_bytes, "input file changed")

    parser = Structure()
    manuscript = CHAPTER.read_text(encoding="utf-8")
    parser.feed(manuscript)
    require(parser.worked >= 2 and parser.exercises == 8 and parser.solutions == 8, "required manuscript package")
    require(not parser.forbidden, "chapter must be a static fragment")
    sources = json.loads((ROOT / "content/reviews/v04-c08-sources.json").read_text(encoding="utf-8"))
    require(parser.sources == {source["id"] for source in sources}, "citation source inventory")
    for href in parser.links:
        if href.startswith("v04-c08-"):
            require("/" not in href and (ROOT / "content/projects" / href).is_file(), "flat download target")
    require("Teach-back:" in manuscript and "Delayed check:" in manuscript, "retention prompts")
    require("v04-c07.html" in parser.links and "v04-c09.html" in parser.links, "dependency and available successor")
    return {
        "status": "passed",
        "checks": [
            "Independent grouped-versus-expanded training identities and target weights: " + str(grid) + " cases, including no-overlap/empty-treated boundaries",
            "Independent bitmask-versus-combination lottery enumeration: " + str(lottery_cases) + " designs; exact unbiasedness and variance",
            "Three worked tables and all determinate exercise arithmetic; total/direct mediation, observed support and collider conditional probabilities",
            "Same observed distribution under three distinct effects and deliberate broken-equivalence detection",
            "14 invalid schema/type/unit cases and 17 bad-file CLI cases in both ordinary and optimized execution",
            "Import without output, input nonmutation and CLI execution from an unrelated working directory",
            "Three worked examples, eight exercises/eight complete solutions, three source IDs, flat download links and retention prompts"
        ],
        "limitations": [
            "Synthetic exact implications do not verify real exchangeability, external validity, no interference or treatment definitions.",
            "Author solution/proof review is separate from external expert certification; finite checks do not prove every possible implementation correct.",
            "Whole-library citation/navigation integration and dependency-order acceptance remain with root.",
            "Visual/mobile/print QA remains pending after previously recorded browser-policy rejection; no workaround attempted."
        ]
    }


if __name__ == "__main__":
    print(json.dumps(check(), indent=2))
