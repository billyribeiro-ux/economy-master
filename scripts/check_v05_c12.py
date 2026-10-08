"""Independent exact checks for the v05-c12 models and synthetic experiment.

Standard library only. Hypergeometric counts and bit masks provide reference
paths distinct from the downloadable program's combinations enumeration.
check() is quiet, returns JSON-serializable evidence and writes no book files.
"""
from collections import Counter
from contextlib import redirect_stdout
from copy import deepcopy
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
import importlib.util
import io
import json
from math import comb
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "content/projects"
INPUT = PROJECT / "v05-c12-experiment.json"
PROGRAM = PROJECT / "v05-c12-randomization.py"


def require(condition, label):
    if not condition:
        raise AssertionError(label)


def choose(n, k):
    return comb(n, k) if 0 <= k <= n else 0


def null_counts(n, treated, successes):
    """Count treated successes, without constructing assignment subsets."""
    return Counter({F(k, treated)-F(successes-k, n-treated):
                    choose(successes, k)*choose(n-successes, treated-k)
                    for k in range(treated+1)
                    if choose(successes, k)*choose(n-successes, treated-k)})


def tail(counts, value):
    return F(sum(number for x, number in counts.items() if abs(x) >= abs(value)),
             sum(counts.values()))


def sample_variance(xs):
    mean = F(sum(xs), len(xs))
    return sum((x-mean)**2 for x in xs)/(len(xs)-1)


def utility(q, money, reference, gain_value, loss_multiplier):
    change = q-reference
    return money+gain_value*change*(1 if change >= 0 else loss_multiplier)


def stream_value(flows, today, beta, delta):
    return flows[today] + sum(beta*delta**(s-today)*flows[s]
                              for s in range(today+1, len(flows)))


class Structure(HTMLParser):
    def __init__(self):
        super().__init__()
        self.worked = self.exercises = self.solutions = 0
        self.in_exercises = self.in_solutions = False
        self.links, self.downloads, self.forbidden = [], [], []
        self.sources = set()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in {"h1", "html", "body", "script"}:
            self.forbidden.append(tag)
        if tag == "aside" and attrs.get("class") == "worked":
            self.worked += 1
        if tag == "ol" and attrs.get("class") == "exercises":
            self.in_exercises = True
        if tag == "details" and attrs.get("class") == "solutions":
            self.in_solutions = True
        if tag == "li":
            self.exercises += self.in_exercises
            self.solutions += self.in_solutions
        if tag == "a":
            self.links.append(attrs.get("href", ""))
            if "download" in attrs:
                self.downloads.append(attrs["href"])
        if "data-source" in attrs:
            self.sources.add(attrs["data-source"])

    def handle_endtag(self, tag):
        if tag == "ol":
            self.in_exercises = False
        if tag == "details":
            self.in_solutions = False


def check():
    checks = []
    # Check thresholds by utility differences on both sides and exactly at ties.
    for a, loss, expected_wta in [(F(6), F(2), F(12)),
                                  (F(8), F(3, 2), F(12)),
                                  (F(10), F(3, 2), F(15)),
                                  (F(8), F(1), F(8))]:
        for step in (F(-1, 2), F(0), F(1, 2)):
            buy_price, sell_price = a+step, expected_wta+step
            buy_gain = utility(1, 100-buy_price, 0, a, loss)-utility(0, 100, 0, a, loss)
            sell_gain = utility(0, 100+sell_price, 1, a, loss)-utility(1, 100, 1, a, loss)
            require(buy_gain == -step and sell_gain == step, "reservation thresholds and ties")
    for a, price, loss in [(F(6), F(8), F(2)), (F(8), F(10), F(3, 2))]:
        require(utility(0, price, 0, a, loss) > utility(1, 0, 0, a, loss), "nonowner reference choice")
        require(utility(1, 0, 1, a, loss) > utility(0, price, 1, a, loss), "owner reference choice")
    value = lambda x: x if x >= 0 else 2*x
    require((value(F(2))+value(F(-2)))/2 == -1, "crossing-reference lottery")
    require((value(F(2))+value(F(6)))/2 == value(F(4)) == 4, "all-gain lottery")
    checks.append("Reference model: four parameter cases, thresholds from direct bundle utility, strict-side/tie checks, fixed-bundle reversals and both lottery solutions")

    for cost, benefit, beta, delta, plan, later in [
        (6, 10, F(1, 2), F(1), F(2), F(-1)),
        (7, 12, F(1, 2), F(9, 10), F(171, 100), F(-8, 5)),
        (7, 12, F(1), F(9, 10), F(171, 50), F(19, 5)),
        (5, 9, F(1, 2), F(1), F(2), F(-1, 2)),
    ]:
        flows = (F(0), F(-cost), F(benefit))
        require(stream_value(flows, 0, beta, delta) == plan, "date-0 stream weights")
        require(stream_value(flows, 1, beta, delta) == later, "date-1 stream weights")
        require((plan > 0 and later < 0) == (beta*delta*benefit < cost < delta*benefit), "strict reversal inequality")
        if later < 0:
            require(stream_value((-plan, -cost, benefit), 0, beta, delta) == 0, "commitment fee threshold tie")
            require(stream_value((-F(1), -cost, benefit), 0, beta, delta) > 0, "sophisticated fee-1 purchase")
            require(stream_value(flows, 1, F(1), delta) > 0, "fully naive predicts action")
            require(stream_value((-F(1), -cost, benefit), 0, beta, delta) < plan, "naive rejects fee relative to perceived action")
    for c in (F(5), F(10)):
        values = [stream_value((0, -c, 10), t, F(1, 2), F(1)) for t in (0, 1)]
        require(0 in values and not (values[0] > 0 and values[1] < 0), "reversal boundaries are not strict")
    for fee, expected in [(1, (F(1), F(3))), (3, (F(-1), F(1)))]:
        flows = (-F(fee), F(-6), F(10))
        require((stream_value(flows, 0, F(1, 2), F(1)), sum(flows)) == expected, "welfare criterion disagreement")
        require(stream_value(flows, 1, F(1, 2), F(1)) == -1, "sunk fee absent from continuation")
    require(sum((-1-6+b) for b in (10, 4))/2 == 0, "heterogeneous mandatory welfare")
    require(stream_value((-1, -6, 4), 0, F(1, 2), F(1)) == -2, "low-benefit voluntary refusal")
    require(F(4, 5)-F(2, 5) == F(2, 5), "attention contrast")
    checks.append("Time and welfare: direct date-weighted stream sums for worked, exercise and delayed cases; naive beliefs, sophisticated continuation, threshold ties, beta=1 and heterogeneous welfare")

    spec = importlib.util.spec_from_file_location("v05_c12_lab", PROGRAM)
    lab = importlib.util.module_from_spec(spec)
    captured = io.StringIO()
    with redirect_stdout(captured):
        spec.loader.exec_module(lab)
    require(captured.getvalue() == "", "import must be quiet")
    before = sha256(INPUT.read_bytes()).hexdigest()
    data = json.loads(INPUT.read_text(encoding="utf-8"))
    result = lab.analyze(data)
    observed = result["observed_only_analysis"]
    expected = null_counts(8, 4, 5)
    require(expected == {F(-3, 4): 5, F(-1, 4): 30, F(1, 4): 30, F(3, 4): 5}, "closed-form null counts")
    actual = {F(row["difference"]): row["count"] for row in observed["null_distribution"]}
    require(actual == expected, "enumerator versus hypergeometric count")
    require(observed["difference_in_completion_rates"] == "3/4", "observed completion contrast")
    require(observed["two_sided_p"] == str(tail(expected, F(3, 4))) == "1/7", "inclusive two-sided tail")
    require(observed["positive_tail_p_for_predeclared_direction_only"] == "1/14", "predeclared positive tail")
    require(observed["assignment_count"] == comb(8, 4) == 70 and observed["two_sided_extreme_count"] == 10, "lottery count")
    require(F(3, 4)/F(1, 4) == 3, "75 points versus 300 percent")
    # All binary sharp-null populations of size eight reduce by exchangeability
    # to these nine success totals. Audit rejection probability at every cutoff.
    tested_cutoffs = 0
    for m in range(9):
        counts = null_counts(8, 4, m)
        require(sum(counts.values()) == 70, "all-null-population assignment total")
        for cutoff in (F(j, 70) for j in range(71)):
            size = F(sum(n for t, n in counts.items() if tail(counts, t) <= cutoff), 70)
            require(size <= cutoff, "inclusive discrete p-value size control")
            tested_cutoffs += 1
    require(tail(null_counts(6, 3, 3), F(1)) == F(1, 10), "delayed test")
    checks.append(f"Randomization: closed-form hypergeometric oracle, 70 assignments, p=1/7 and positive p=1/14; {tested_cutoffs} exact size cutoffs spanning every binary null population; six-person retention p=1/10")

    y0 = [r["y0"] for r in data["synthetic_oracle"]]
    y1 = [r["y1"] for r in data["synthetic_oracle"]]
    effects = [b-a for a, b in zip(y0, y1)]
    require(effects == [1, 1, 0, 0, 0, 1, 1, 0], "individual effect vector")
    truth = Counter()
    for mask in range(1 << 8):
        if mask.bit_count() == 4:
            treated_total = sum(y1[i] for i in range(8) if mask & (1 << i))
            control_total = sum(y0[i] for i in range(8) if not mask & (1 << i))
            truth[F(treated_total-control_total, 4)] += 1
    require(truth == {F(0): 4, F(1, 4): 19, F(1, 2): 24, F(3, 4): 19, F(1): 4}, "bit-mask true assignment distribution")
    mean = sum(t*n for t, n in truth.items())/70
    variance = sum((t-mean)**2*n for t, n in truth.items())/70
    variance_identity = sample_variance(y1)/4 + sample_variance(y0)/4 - sample_variance(effects)/8
    require(mean == F(sum(effects), 8) == F(1, 2) and variance == variance_identity == F(1, 16), "unbiasedness and finite-population variance identity")
    oracle = result["separate_oracle_audit"]
    require(oracle["individual_effects"] == effects and oracle["true_finite_population_ate"] == "1/2", "reported synthetic truth")
    require(oracle["assignment_mean_difference"] == "1/2" and oracle["assignment_variance_of_difference"] == "1/16", "reported oracle moments")
    require({F(r["difference"]): r["count"] for r in oracle["assignment_distribution_under_oracle"]} == truth, "oracle implementation compared with bit masks")
    compatible = []
    for mask in range(1 << 8):
        total = 0
        for i, row in enumerate(data["observed"]):
            missing = int(bool(mask & (1 << i)))
            total += row["outcome"]-missing if row["assignment"] else missing-row["outcome"]
        compatible.append(F(total, 8))
    require((min(compatible), max(compatible)) == (F(-1, 8), F(7, 8)), "logical ATE compatibility endpoints")
    require(F(0) in compatible and F(1, 2) in compatible, "distinct compatible truths")
    missing_contrasts = [F(2+a+b, 4)-F(1, 4) for a in (0, 1) for b in (0, 1)]
    require((min(missing_contrasts), max(missing_contrasts)) == (F(1, 4), F(3, 4)), "attrition bounds")
    require(F(2, 2)-F(1, 4) == F(3, 4), "selected complete-case contrast")
    checks.append("Synthetic truth: independent bit masks and Neyman variance identity give mean 1/2 and variance 1/16; all 256 missing-counterfactual schedules give [-1/8,7/8]; four attrition completions give [1/4,3/4]")

    no_oracle = deepcopy(data)
    no_oracle.pop("synthetic_oracle")
    require(lab.analyze(no_oracle)["observed_only_analysis"] == observed, "oracle removal cannot change test")
    zero = deepcopy(data)
    zero["synthetic_oracle"] = [{"id": r["id"], "y0": r["outcome"], "y1": r["outcome"]} for r in data["observed"]]
    zero_result = lab.analyze(zero)
    require(zero_result["observed_only_analysis"] == observed and zero_result["separate_oracle_audit"]["true_finite_population_ate"] == "0", "same observed test, different synthetic effect")
    reverse = deepcopy(data)
    reverse["observed"].reverse()
    reverse["synthetic_oracle"].reverse()
    require(lab.analyze(reverse)["observed_only_analysis"] == observed, "row-label permutation invariance")
    changed = deepcopy(no_oracle)
    changed["observed"][0]["outcome"] = 0
    changed_test = lab.analyze(changed)["observed_only_analysis"]
    require(changed_test["difference_in_completion_rates"] == "1/2", "outcome mutation changes estimate")
    require(F(changed_test["two_sided_p"]) == tail(null_counts(8, 4, 4), F(1, 2)), "outcome mutation changes exact p")
    checks.append("Separation tests: remove oracle, substitute compatible zero effects, permute labels and change an actual outcome; observed inference uses observed information only")

    invalid = []
    def change(label, path, value):
        variant = deepcopy(data)
        target = variant
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value
        invalid.append((label, variant))
    for value in (None, True, 1.0, 2):
        change(f"invalid observed binary {value!r}", ["observed", 0, "outcome"], value)
    change("duplicate observed ID", ["observed", 1, "id"], "P01")
    change("boolean assignment", ["observed", 0, "assignment"], True)
    change("wrong arm count", ["design", "n_treated"], 3)
    change("empty arm", ["design", "n_treated"], 0)
    change("boolean arm count", ["design", "n_treated"], True)
    change("unsupported assignment", ["design", "assignment_law"], "independent_bernoulli")
    change("posthoc test", ["design", "test"], "positive_after_observation")
    change("unmarked synthetic data", ["synthetic"], False)
    change("inconsistent oracle", ["synthetic_oracle", 0, "y1"], 0)
    change("duplicate oracle ID", ["synthetic_oracle", 1, "id"], "P01")
    change("unmatched oracle ID", ["synthetic_oracle", 0, "id"], "P99")
    change("invalid oracle binary", ["synthetic_oracle", 0, "y0"], False)
    change("invalid row", ["observed", 0], None)
    for label, variant in invalid:
        try:
            lab.analyze(variant)
        except ValueError:
            pass
        else:
            raise AssertionError(f"failed to reject {label}")
    with tempfile.TemporaryDirectory(prefix="v05-c12-check-") as folder:
        run = subprocess.run([sys.executable, str(PROGRAM)], cwd=folder, capture_output=True, text=True, timeout=10)
        require(run.returncode == 0 and not run.stderr and json.loads(run.stdout) == result, "baseline CLI from another directory")
        require(result == json.loads((PROJECT / "v05-c12-output.json").read_text()), "preserved output reproduces exactly")
        bad_input = Path(folder)/"invalid.json"
        for label, variant in invalid:
            bad_input.write_text(json.dumps(variant))
            run = subprocess.run([sys.executable, str(PROGRAM), "--data", str(bad_input)], cwd=folder, capture_output=True, text=True, timeout=10)
            require(run.returncode == 2 and not run.stdout and "Invalid experiment input:" in run.stderr and "Traceback" not in run.stderr, f"CLI failure detection: {label}")
    require(sha256(INPUT.read_bytes()).hexdigest() == before, "benchmark leaves frozen input unchanged")
    checks.append(f"Executable: quiet import, reproducible preserved JSON, default input from unrelated working directory, unchanged input hash, and {len(invalid)} direct plus CLI invalid-input rejections")

    require(1-F(19, 20)**5 == F("0.2262190625"), "five independent tests family error")
    ps = list(map(F, ("0.008", "0.02", "0.04", "0.30", "0.70")))
    require(sum(p <= F(1, 20) for p in ps) == 3 and sum(p <= F(1, 100) for p in ps) == 1, "Bonferroni decisions")
    require(round(float(F(11, 18)*100), 1) == 61.1, "bounded historical ratio display")
    checks.append("Multiplicity: exact 0.2262190625 family rejection probability, three individual versus one Bonferroni rejection; historical ratio arithmetic only")

    html = (ROOT / "content/chapters/v05-c12.html").read_text(encoding="utf-8")
    parsed = Structure()
    parsed.feed(html)
    require(not parsed.forbidden and parsed.worked == 3 and parsed.exercises == parsed.solutions == 8, "complete static chapter inventory")
    require(all(term in html for term in ("Teach-back", "Delayed check", "Delayed-check answers", "not a 95% confidence interval")), "retention and interpretation statements")
    require("v05-c11.html" in parsed.links and (ROOT / "content/chapters/v05-c11.html").is_file(), "prerequisite manuscript route")
    require(len(parsed.downloads) == 4 and all("/" not in name and (PROJECT/name).is_file() for name in parsed.downloads), "four flat offline downloads")
    sources = json.loads((ROOT / "content/reviews/v05-c12-sources.json").read_text(encoding="utf-8"))
    require(len(sources) == 5 and {s["id"] for s in sources} == parsed.sources, "source IDs exactly match")
    for source in sources:
        require(set(("id", "title", "url", "use", "checked", "verification")) <= set(source), "source schema")
        require(source["id"].startswith("v05-c12-") and source["url"] in parsed.links and source["checked"] == "2026-10-08", "source route and actual inspection date")
    checks.append("Structure: three original worked cases, eight matched full solutions, answered retention, prerequisite route, four existing flat downloads and five scoped primary-source records")
    report = {"status": "passed", "checks": checks, "limitations": [
        "Numerical checks verify these original finite models and experiment; they do not establish prevalence, a real psychological mechanism, transportability or welfare of an actual intervention.",
        "The experiment program requires the specified complete lottery and complete binary outcomes. Sharp-null inference is not a heterogeneous-average-effect confidence procedure.",
        "Synthetic oracle outcomes are known only by construction. Logical missing-counterfactual bounds are not confidence intervals.",
        "Source inspections are scoped in the source proposals; the replication paper is cited from its actual author-deposited abstract and metadata, without reanalysis or a full methods audit.",
        "Analytic proofs and open-ended exercise evaluation also require editorial reading; a checker cannot certify all prose. Root retains acceptance, integrated verification and publication.",
        "Visual/mobile/print UI QA and external expert validation were not performed."
    ]}
    json.dumps(report)
    return report


if __name__ == "__main__":
    print(json.dumps(check(), indent=2))
