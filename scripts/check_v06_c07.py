"""Independent exact audit for v06-c07; quiet JSON-compatible check().

Uses pricing matrix equations, direct price-index checks, geometric closed-form
forecast paths and finite covariance sums rather than trusting preserved output.
"""
from contextlib import redirect_stdout
from copy import deepcopy
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
import importlib.util
import io
import json
from math import exp, isclose, log
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "content/projects"
INPUT = PROJECT / "v06-c07-models.json"
PROGRAM = PROJECT / "v06-c07-inflation.py"


def require(condition, label):
    if not condition:
        raise AssertionError(label)


def matrix_reference(case):
    s, a, b, target, e, d, z = (F(case[k]) for k in ("s", "a", "b", "anchor", "e", "d", "z"))
    # Matrix [s, -(1-s)a; b, 1] times [Pi,x] equals RHS.
    left, right = s*e+(1-s)*z, d+b*target
    determinant = s+(1-s)*a*b
    return (left+(1-s)*a*right)/determinant, (s*right-b*left)/determinant


class Structure(HTMLParser):
    def __init__(self):
        super().__init__()
        self.worked = self.exercises = self.solutions = 0
        self.in_exercises = self.in_solutions = False
        self.downloads, self.sources, self.bad = [], set(), []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in {"html", "body", "h1", "script"}:
            self.bad.append(tag)
        if tag == "aside" and attrs.get("class") == "worked":
            self.worked += 1
        if tag == "ol" and attrs.get("class") == "exercises":
            self.in_exercises = True
        if tag == "details" and attrs.get("class") == "solutions":
            self.in_solutions = True
        if tag == "li":
            self.exercises += self.in_exercises
            self.solutions += self.in_solutions
        if tag == "a" and "download" in attrs:
            self.downloads.append(attrs["href"])
        if attrs.get("data-source"):
            self.sources.add(attrs["data-source"])

    def handle_endtag(self, tag):
        if tag == "ol":
            self.in_exercises = False
        if tag == "details":
            self.in_solutions = False


def check():
    checks = []
    require(F(110, 100)-1 == F(1, 10) and F(231, 2)/110-1 == F(1, 20), "quarterly inflation")
    require(F(231, 200)-1 == F(31, 200) and F(21, 20)**4-1 == F(34481, 160000),
            "cumulative and annualized growth")
    require(F(108)*2/F(204) == F(18, 17) and F(108)*F(17, 9)/204 == 1, "two velocities")
    require(F(27, 25)/F(18, 17)-1 == F(1, 50), "exact worked real return")
    require(F(11, 10)*F(49, 50)/F(26, 25)-1 == F(19, 520), "quantity exercise exact growth")
    require((F(11, 10)+F(11, 12))/2 == F(121, 120), "expected reciprocal return")
    require(F(21, 20)/F(51, 50)-1 == F(1, 34), "delayed real net")
    for ordinary in (F(-1, 2), F(0), F(1, 17), F(1, 10)):
        log_points = 100*log(1+float(ordinary))
        require(isclose(exp(log_points/100)-1, float(ordinary), abs_tol=1e-14), "log conversion round trip")
    require(isclose(100*(exp(.03)-1), 3.045453395351694, rel_tol=1e-12), "3 log points are not 3 percent")
    checks.append("Rates: exact quarterly/cumulative/annualized compounding, both quantity scenarios, finite-growth correction, ordinary versus log conversion and realized/expected real returns")

    data = json.loads(INPUT.read_text())
    input_hash = sha256(INPUT.read_bytes()).hexdigest()
    spec = importlib.util.spec_from_file_location("v06_c07_model", PROGRAM)
    model = importlib.util.module_from_spec(spec)
    captured = io.StringIO()
    with redirect_stdout(captured):
        spec.loader.exec_module(model)
        output = model.analyze(data)
    require(not captured.getvalue(), "quiet benchmark import/API")
    require(output == json.loads((PROJECT / "v06-c07-output.json").read_text()), "preserved output reproduction")
    require(output["quantity"]["next"][0]["ordinary_inflation"] == "1/17" and
            output["quantity"]["next"][0]["loan_real_net"] == "1/50" and
            output["quantity"]["next"][1]["ordinary_inflation"] == "0", "quantity benchmark values")
    require(output["uncertain_return"]["expected_real_gross"] == "121/120" and
            output["uncertain_return"]["gross_using_mean_inflation"] == "1", "uncertainty benchmark")
    cases = {row["id"]: row for row in output["pricing_cases"]}
    targets = {"baseline": (F(2), F(0)), "demand_positive": (F(3), F(2)),
               "demand_negative": (F(1), F(-2)), "pricing_positive": (F(4), F(-2)),
               "pricing_negative": (F(0), F(2)), "same_inflation": (F(3), F(-1)),
               "same_pair_other_expectation": (F(3), F(2)), "exercise_four": (F(7, 2), F(1)),
               "all_preset": (F(2), F(3)), "all_reset": (F(5), F(0)),
               "all_reset_cost": (F(8), F(-6))}
    for source in data["pricing_cases"]:
        row = cases[source["id"]]
        pi, x = F(row["Pi"]), F(row["x"])
        require((pi, x) == matrix_reference(source) == targets[source["id"]], "pricing exact target and matrix")
        s, a, z, e = (F(source[k]) for k in ("s", "a", "z", "e"))
        require(s*e+(1-s)*(pi+a*x+z) == pi, "aggregate geometric-index log fixed point")
        # A common log-price shift changes individual/aggregate levels equally.
        previous = F(117, 2)
        require(s*(previous+e)+(1-s)*(previous+pi+a*x+z) == previous+pi,
                "nominal normalization invariance")
    # Independent exercise3 is not an executable canned scenario.
    s, a, z, e, x = F(3, 4), F(3, 2), F(2), F(1), F(2)
    pi = e+(1-s)*(a*x+z)/s
    require(pi == F(8, 3) and pi+a*x+z == F(23, 3) and
            s*e+(1-s)*(pi+a*x+z) == pi, "exercise3 individual-price aggregation")
    for deviation in (F(-10), F(-1), F(0), F(1, 3), F(12)):
        require(deviation**2/2 >= 0 and (deviation**2/2 == 0) == (deviation == 0),
                "quadratic target unique global minimum")
    # Changed parameters, including endpoints, test beyond printed canned cases.
    tested = 0
    for s in (F(0), F(1, 4), F(2, 3), F(1)):
        for a in (F(1, 2), F(2)):
            for b in (F(1, 3), F(1), F(3)):
                for d, z in ((F(-2), F(1)), (F(3), F(-1))):
                    case = {"s": str(s), "a": str(a), "b": str(b), "e": "7/3", "anchor": "2", "d": str(d), "z": str(z)}
                    row = model.pricing(case)
                    require((row["Pi"], row["x"]) == matrix_reference(case), "parameter-grid matrix oracle")
                    tested += 1
    checks.append(f"Pricing: 11 named cases, separate exercise aggregation/global quadratic target, nominal normalization and {tested} changed-parameter cases including both preset-share endpoints")

    # Finite changes equal derivatives here because the solved system is affine.
    base = deepcopy(data["pricing_cases"][0])
    baseline = model.pricing(base)
    demand = {**base, "d": "1"}
    price = {**base, "z": "2"}  # u=1 at this s.
    drow, urow = model.pricing(demand), model.pricing(price)
    require(drow["Pi"]-baseline["Pi"] == F(1, 3) and drow["x"] == F(2, 3), "demand derivatives")
    require(urow["Pi"]-baseline["Pi"] == F(2, 3) and urow["x"] == F(-2, 3), "pricing derivatives")
    inflation_target = model.pricing({**base, "d": "-6", "z": "6"})
    output_target = model.pricing({**base, "d": "3", "z": "6"})
    require((inflation_target["Pi"], inflation_target["x"]) == (2, -6) and
            (output_target["Pi"], output_target["x"]) == (5, 0), "incompatible short-run targets")
    checks.append("Demand/cost comparative statics, expectation observational ambiguity and exact intercepts required by conflicting inflation/output targets")

    for source, result in zip(data["adaptive"], output["adaptive"]):
        s, a, b, anchor, initial, d, z, learning = (F(source[k]) for k in
                                                    ("s", "a", "b", "anchor", "e", "d", "z", "learning"))
        kappa, u = (1-s)*a/s, (1-s)*z/s
        rho = 1-learning*kappa*b/(1+kappa*b)
        fixed = anchor+(kappa*d+u)/(kappa*b)
        require(F(result["rho"]) == rho and 0 < rho <= 1, "adaptive contraction/boundary")
        price_sum = F(0)
        for t, row in enumerate(result["path"]):
            e_t = fixed+rho**t*(initial-fixed) if learning else initial
            pi_t = (e_t+kappa*d+kappa*b*anchor+u)/(1+kappa*b)
            x_t = d-b*(pi_t-anchor)
            price_sum += pi_t
            require((F(row["e"]), F(row["Pi"]), F(row["x"])) == (e_t, pi_t, x_t),
                    "adaptive loop against forced closed form")
            require(F(row["log_price_from_initial"]) == price_sum, "inflation accumulates into price level")
        require(result["unique_forecast_fixed_point"] == (str(fixed) if learning else None),
                "fixed forecast uniqueness")
        if not d and not u and learning:
            infinite_gap = -(initial-anchor)/(learning*kappa)
            finite_gap = infinite_gap*(1-rho**source["periods"])
            require(F(result["finite_log_gap_sum"]) == finite_gap, "finite versus infinite cumulative gap")
            require(infinite_gap == {"worked": -8, "exercise": -6, "retention": -4}[source["id"]],
                    "worked/exercise/delayed cumulative units")
    require(output["adaptive"][0]["path"][0]["Pi"] == "10/3" and
            output["adaptive"][0]["path"][1]["Pi"] == "28/9" and
            output["adaptive"][1]["path"][0]["Pi"] == "4", "explicit adaptive anchors")
    for s, rho in (("1", F(1)), ("0", F(1, 2))):
        changed = {**data["adaptive"][0], "s": s}
        result = model.adaptive(changed)
        require(result["rho"] == rho, "endpoint forecast update")
    # At b=0 the separate undivided demand law supplies no target feedback.
    require(F(4)+F(1, 2)*(F(4)-F(4)) == 4, "zero-demand-feedback boundary no automatic convergence")
    checks.append("Five adaptive paths checked with forced/unforced closed forms, λ=0 and s endpoints, finite/infinite gap sums, price-level accumulation and separate b=0 scope")

    surprise, known = output["consistent_forecasts"]
    require(surprise["e"] == surprise["expected_Pi"] == "2" and
            [(row["Pi"], row["x"]) for row in surprise["states"]] == [("1", "-2"), ("3", "2")],
            "finite model-consistent surprise law")
    require(known["e"] == known["expected_Pi"] == "5" and known["states"][0]["x"] == "0",
            "known intercept differs from surprise")
    expected_ordinary = (exp(.01)+exp(.03))/2-1
    require(expected_ordinary > exp(.02)-1, "expectation does not commute with inflation conversion")
    require(output["descriptive_slopes"] == {"demand_pair": "1/2", "pricing_pair": "-1", "equal_four_state_mixture": "-1/4"},
            "descriptive slope outputs")
    x = [F(-2), F(2), F(2), F(-2)]
    pi = [F(1), F(3), F(0), F(4)]
    require(sum(a*(b-2) for a, b in zip(x, pi))/4 == -1 and sum(a*a for a in x)/4 == 4,
            "independent four-state moments")
    changed = deepcopy(data)
    changed["pricing_cases"][3]["z"] = "0"
    require(model.analyze(changed)["pricing_cases"][3]["Pi"] == "2", "actual shock mutation changes outcome")
    changed = deepcopy(data)
    changed["consistent_forecasts"][0]["states"][1]["d"] = "5"
    require(model.analyze(changed)["consistent_forecasts"][0]["e"] == "3", "conditional mean mutation changes forecast")
    checks.append("Model-consistent means and realized errors, announced versus surprise timing, log/ordinary expectation difference and independent synthetic OLS covariance sums")

    invalid = []
    for group, key, value in [("pricing_cases", "s", "-1/4"), ("pricing_cases", "s", "5/4"),
                              ("pricing_cases", "a", "0"), ("pricing_cases", "b", "0"),
                              ("pricing_cases", "e", True), ("pricing_cases", "e", 2.0),
                              ("pricing_cases", "e", "1/0"), ("adaptive", "periods", True),
                              ("adaptive", "periods", 0), ("adaptive", "periods", 101),
                              ("adaptive", "learning", "-1/2"), ("adaptive", "learning", "2"),
                              ("consistent_forecasts", "s", "1")]:
        mutant = deepcopy(data)
        mutant[group][0][key] = value
        invalid.append(mutant)
    for key in ("M", "V", "Y"):
        mutant = deepcopy(data)
        mutant["quantity"]["initial"][key] = "0"
        invalid.append(mutant)
    mutant = deepcopy(data)
    mutant["uncertain_return"]["states"][0]["ordinary_inflation"] = "-1"
    invalid.append(mutant)
    mutant = deepcopy(data)
    mutant["consistent_forecasts"][0]["states"][0]["probability"] = "1/3"
    invalid.append(mutant)
    mutant = deepcopy(data)
    mutant["schema"] = "unknown"
    invalid.append(mutant)
    with tempfile.TemporaryDirectory() as directory:
        run = subprocess.run([sys.executable, str(PROGRAM)], cwd=directory, capture_output=True, text=True)
        require(run.returncode == 0 and not run.stderr and json.loads(run.stdout) == output,
                "standalone default independent of working directory")
        for index, mutant in enumerate(invalid):
            try:
                model.analyze(mutant)
            except (ValueError, KeyError, TypeError, ZeroDivisionError):
                pass
            else:
                raise AssertionError(f"invalid input accepted: {index}")
            file = Path(directory) / f"invalid-{index}.json"
            file.write_text(json.dumps(mutant))
            run = subprocess.run([sys.executable, str(PROGRAM), str(file)], capture_output=True, text=True)
            require(run.returncode != 0 and not run.stdout and "error:" in run.stderr,
                    "invalid CLI fails without result")
    require(sha256(INPUT.read_bytes()).hexdigest() == input_hash, "input unmodified")
    checks.append(f"Executable: quiet callable, preserved output, arbitrary-CWD default, meaningful shock/expectation mutations and {len(invalid)} invalid inputs rejected by API and CLI")

    html = (ROOT / "content/chapters/v06-c07.html").read_text()
    parser = Structure()
    parser.feed(html)
    require(parser.worked >= 2 and parser.exercises == parser.solutions == 8 and not parser.bad,
            "complete HTML fragment structure")
    require("Teach-back" in html and "Delayed-check answers" in html and "v06-c06.html" in html,
            "instruction and prerequisite")
    require(len(parser.downloads) == 4 and all(name.startswith("v06-c07-") and "/" not in name and
            (PROJECT/name).is_file() for name in parser.downloads), "flat existing downloads")
    sources = json.loads((ROOT / "content/reviews/v06-c07-sources.json").read_text())
    require({source["id"] for source in sources} == parser.sources and len(sources) == 3, "source coverage")
    for source in sources:
        require(all(source.get(k) for k in ("id", "title", "url", "use", "checked", "verification")), "scoped source record")
    checks.append("Structure: three worked examples, eight aligned full solutions, answered delayed check, four flat downloads and three actually inspected primary-method records")
    report = {"status": "passed", "checks": checks, "invalid_cases": len(invalid), "changed_parameter_cases": tested,
              "input_sha256": input_hash, "limitations": [
                  "Checks verify maintained synthetic equations, units and implementation; they estimate no empirical slope or identified policy effect.",
                  "Exact rational calculations are separate from tolerance-checked exponential/log conversions.",
                  "Analytic stability, pricing and identification scope also require editorial reading; executable checks do not prove the economic assumptions.",
                  "Full RBC/NK equilibrium comparison and graduate microfoundations are outside this chapter.",
                  "Root owns dependency acceptance and integration. No visual/mobile/print QA or external human validation is claimed."
              ]}
    json.dumps(report)
    return report


if __name__ == "__main__":
    print(json.dumps(check(), indent=2, ensure_ascii=False))
