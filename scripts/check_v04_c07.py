#!/usr/bin/env python3
"""Independent rational, boundary, exercise and package checks for v04-c07."""
import contextlib
import copy
from fractions import Fraction as F
from html.parser import HTMLParser
import io
import itertools
import json
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PROGRAM = ROOT / "content/projects/v04-c07-regression.py"
CASES = ROOT / "content/projects/v04-c07-cases.json"
CHAPTER = ROOT / "content/chapters/v04-c07.html"
SOURCES = ROOT / "content/reviews/v04-c07-sources.json"


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def error_from(function, *args):
    try:
        function(*args)
    except (ValueError, TypeError):
        return
    raise AssertionError("expected invalid-input or deficient-rank error")


def inner(a, b):
    return sum((F(x) * F(y) for x, y in zip(a, b)), F(0))


def projection(design, y):
    """Independent exact Gram-Schmidt, dropping dependent directions.

    No normal equations, square-system solver, inverse or downloaded fit code.
    Unnormalized orthogonal directions avoid irrational square roots.
    """
    basis = []
    for column in zip(*design):
        residual = [F(v) for v in column]
        for direction in basis:
            scale = inner(direction, residual) / inner(direction, direction)
            residual = [r - scale * q for r, q in zip(residual, direction)]
        if inner(residual, residual):
            basis.append(residual)
    n = len(y)
    h = [[sum((q[i] * q[j] / inner(q, q) for q in basis), F(0))
          for j in range(n)] for i in range(n)]
    predicted = [inner(row, y) for row in h]
    return predicted, h, len(basis)


def centered_line(x, y):
    mean_x = sum(map(F, x)) / len(x)
    mean_y = sum(map(F, y)) / len(y)
    sxx = sum((F(v) - mean_x)**2 for v in x)
    slope = sum((F(a) - mean_x) * (F(b) - mean_y) for a, b in zip(x, y)) / sxx
    return mean_y - slope * mean_x, slope


def matrix_vector(matrix, vector):
    return [inner(row, vector) for row in matrix]


def product(a, b):
    return [[inner(row, col) for col in zip(*b)] for row in a]


class Manuscript(HTMLParser):
    def __init__(self):
        super().__init__()
        self.worked = 0
        self.exercises = 0
        self.answers = 0
        self.exercise_depth = 0
        self.solution = False
        self.pre = False
        self.buffer = []
        self.snippets = []
        self.sources = set()
        self.links = []
        self.forbidden = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in {"html", "body", "h1"}:
            self.forbidden.append(tag)
        if attrs.get("data-source"):
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
            self.solution = True
        if tag == "li" and self.exercise_depth == 1:
            self.exercises += 1
        if tag == "li" and self.solution:
            self.answers += 1
        if tag == "pre":
            self.pre = True
            self.buffer = []

    def handle_endtag(self, tag):
        if tag == "ol" and self.exercise_depth:
            self.exercise_depth -= 1
        if tag == "details":
            self.solution = False
        if tag == "pre":
            self.pre = False
            self.snippets.append("".join(self.buffer))

    def handle_data(self, data):
        if self.pre:
            self.buffer.append(data)


def check():
    checks = []
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        mod = runpy.run_path(str(PROGRAM), run_name="v04_c07_check")
    require(not output.getvalue(), "import should not print or fit")
    fit, report = mod["fit"], mod["make_report"]
    original = CASES.read_bytes()
    cases = mod["load_cases"](CASES)
    before = copy.deepcopy(cases)
    reports = [report(case) for case in cases]
    require(cases == before, "fit/report must not mutate inputs")
    targets = [([F(7,10), F(6,5)], F(9,5), F(9), F(4,5)),
               ([F(10), F(2), F(4)], F(12), F(82), F(35,41)),
               ([F(1), F(17,6), F(-5,2), F(2,3)], F(0), F(9), F(1))]
    for case, target in zip(cases, targets):
        result = fit(case["design"], case["outcomes"])
        require((result["coefficients"], result["sse"], result["sst"], result["r_squared"]) == target,
                "worked example coefficients and loss targets")
        pred, h, rank = projection(case["design"], case["outcomes"])
        require(result["fitted"] == pred, "independent projection disagrees")
        require(h == [list(col) for col in zip(*h)] and product(h, h) == h,
                "projection symmetry/idempotence")
        require(matrix_vector(h, result["residuals"]) == [0] * len(pred), "residual projection")
        require(result["leverage"] == [h[i][i] for i in range(len(h))], "leverage exact agreement")
        require(sum(result["leverage"]) == rank and all(0 <= value <= 1 for value in result["leverage"]),
                "leverage bounds/trace")
        require(result["ssr"] + result["sse"] == result["sst"], "centered Pythagoras")
        require(all(v == 0 for v in result["normal_equation_residual"]), "normal equations")
        for perturbation in itertools.product([-2, 0, 3], repeat=len(target[0])):
            shifted = [a + F(d) for a, d in zip(target[0], perturbation)]
            alternative = [F(y) - inner(row, shifted) for row, y in zip(case["design"], case["outcomes"])]
            deltafit = matrix_vector(case["design"], perturbation)
            require(inner(alternative, alternative) == result["sse"] + inner(deltafit, deltafit),
                    "global-minimum orthogonal decomposition")
    checks.append("Three exact coefficient/loss references independently agree with rational Gram-Schmidt projections, hat matrices and 117 global-loss perturbations")

    a, b = centered_line([0,1,2,3], [1,2,2,5])
    require((a,b) == (F(7,10),F(6,5)), "simple-regression independent formula")
    rx = [-1,0,1,-1,0,1]
    ry = [-1,-2,3,-3,2,1]
    require(inner(rx, ry) / inner(rx, rx) == 2, "within-group partialling")
    require(centered_line([0,1,2,1,2,3], [11,10,15,15,20,19]) == (F(114,11), F(34,11)),
            "aggregate-versus-adjusted slope")
    require(reports[0]["evaluation_predictions"] == ["11/2", "67/10"] and
            reports[0]["evaluation_mse"] == "17/100", "line evaluation")
    require(reports[2]["evaluation_predictions"] == ["15", "36"] and
            reports[2]["evaluation_mse"] == "461" and reports[2]["predictions"] == ["72"],
            "cubic evaluation and extrapolation")
    altered = copy.deepcopy(cases[0])
    altered["evaluation_outcomes"] = [100,-200]
    altered_report = report(altered)
    for key in ["coefficients","fitted","residuals","sse","sst","leverage","r_squared"]:
        require(altered_report[key] == reports[0][key], "evaluation leaked into training")
    checks.append("Centered-sum and within-group slope derivations; cubic interpolation and fixed evaluation; no evaluation-to-training leakage")

    # Independent projection across many data shapes, including an ill-scaled exact case.
    verified = 0
    for n in range(3, 9):
        x = list(range(n))
        for slope in [-3, 0, 2]:
            for degree in [1,2]:
                design = [[1] + [v**j for j in range(1,degree+1)] for v in x]
                y = [7 + slope*v + ((v*v+3*v+1) % 5) for v in x]
                result = fit(design,y)
                predicted,_,rank = projection(design,y)
                require(result["fitted"] == predicted and rank == degree+1, "grid exact projection")
                verified += 1
    nearly = [[1, 999999, 999998], [1, 1000000, 999999], [1, 999999, 999999], [1, 999998, 999997]]
    near_y = [3,4,7,2]
    require(fit(nearly, near_y)["fitted"] == projection(nearly, near_y)[0], "ill-scaled exact input")
    checks.append(str(verified) + " full-rank polynomial/design grid comparisons plus a large nearly dependent exact design")

    # Exercises 2,3,4: data, transformations, null-space prediction distinction.
    ex2 = fit([[1,0],[1,2],[1,4]], [2,3,7])
    require(ex2["coefficients"] == [F(3,2),F(5,4)] and ex2["residuals"] == [F(1,2),-1,F(1,2)]
            and ex2["sse"] == F(3,2) and ex2["sst"] == 14 and ex2["r_squared"] == F(25,28), "exercise 2")
    units = fit([[1,0],[1,100],[1,200],[1,300]], [1000,2000,2000,5000])
    require(units["coefficients"] == [700,12] and units["sse"] == 1800000 and units["r_squared"] == F(4,5), "units")
    centered = fit([[1,-2],[1,-1],[1,0],[1,1]], [1,2,2,5])
    require(centered["coefficients"] == [F(31,10),F(6,5)], "centered coding")
    redundant = [[1,x,2*x] for x in range(4)]
    error_from(fit, redundant, [1,2,2,5])
    redundant_fit, redundant_h, rank = projection(redundant,[1,2,2,5])
    require(rank == 2 and redundant_fit == [F(7,10),F(19,10),F(31,10),F(43,10)], "rank-deficient fitted uniqueness")
    for t in [F(-9),F(0),F(2,3),F(8)]:
        beta = [F(7,10),F(6,5)-2*t,t]
        require(matrix_vector(redundant,beta) == redundant_fit, "coefficient family")
        require(inner([1,4,8], beta) == F(11,2) and inner([1,4,9],beta) == F(11,2)+t, "off-support nonuniqueness")
    checks.append("Exercises 2–4 exact fits, outcome/predictor rescaling, centering, null-space family and off-support prediction nonuniqueness")

    # Exercises 5,6 and boundaries.
    shifted_y = [11,10,15,18,23,22]
    shifted = fit(cases[1]["design"],shifted_y)
    require(shifted["coefficients"] == [10,2,7] and shifted["residuals"] == [1,-2,1,-1,2,-1]
            and shifted["sse"] == 12, "exercise 5 included-design shift")
    require(centered_line([0,1,2,1,2,3],shifted_y)[1] == F(43,11), "exercise 5 aggregate slope")
    no_intercept, _, _ = projection([[1],[0]],[1,2])
    require(no_intercept == [1,0], "no-intercept projection")
    sse = sum((F(y)-pred)**2 for y,pred in zip([1,2],no_intercept))
    require(1-sse/F(1,2) == -7 and 1-sse/5 == F(1,5), "negative centered/uncentered R2")
    const = fit([[1,0],[1,1],[1,2]], [8,8,8])
    require(const["r_squared"] is None and const["sse"] == 0 and const["sst"] == 0, "constant outcome boundary")
    require(fit([[1]], [8])["leverage"] == [1], "one-row intercept boundary")
    error_from(fit, [[1,3],[1,3]], [8,10])
    for yy in ([1,4,2,7],[4,4,4,4],[-3,0,8,1]):
        losses=[fit([[1]+[x**j for j in range(1,d+1)] for x in range(4)],list(yy))["sse"] for d in range(4)]
        require(all(losses[i+1] <= losses[i] for i in range(3)), "nested SSE monotonicity")
    checks.append("Exercises 5–6 group shifts, no-intercept negative R², constant outcomes, one-row/saturated fits and nested-loss boundaries")

    # Exercise 7, residual curvature and delayed check.
    changed = fit(cases[0]["design"], [1,2,2,6])
    require(changed["coefficients"] == [F(1,2),F(3,2)] and changed["residuals"] == [F(1,2),0,F(-3,2),1]
            and changed["sse"] == F(7,2), "exercise 7 updated fit")
    weights=[F(1,4)+F(9,2)*F(2*x-3,2)/5 for x in range(4)]
    require(weights == [F(-11,10),F(-1,5),F(7,10),F(8,5)] and sum(weights) == 1 and inner(weights,weights) == F(43,10),
            "prediction sensitivity weights")
    require(inner([1,6],changed["coefficients"]) - F(79,10) == weights[-1], "last outcome prediction sensitivity")
    curve=fit([[1,-1],[1,0],[1,1]],[1,0,1])
    require(curve["residuals"] == [F(1,3),F(-2,3),F(1,3)], "curvature despite orthogonality")
    delayed=fit([[1,0],[1,1],[1,2]],[1,3,2])
    require(delayed["coefficients"] == [F(3,2),F(1,2)] and delayed["r_squared"] == F(1,4)
            and delayed["residuals"] == [F(-1,2),1,F(-1,2)], "delayed check")
    checks.append("Exercise 7 and delayed check; leverage response, extrapolation weights/norm and residual curvature counterexample")

    malformed=[]
    base=json.loads(CASES.read_text())
    for field, value in [("design",[]),("design",[[1,0],[1]]),("outcomes",[1]),
                         ("outcomes",[True,2,2,5]),("outcomes",[1.0,2,2,5]),
                         ("outcomes",[1000001,2,2,5]),("outcomes",[None,2,2,5]),
                         ("predictor_names",["intercept","intercept"]),
                         ("predictor_units",["1"]),("evaluation_outcomes",[]),
                         ("prediction_design",[[0,6]]),("design",[[1,1]]*4)]:
        data=copy.deepcopy(base)
        data["cases"][0][field]=value
        malformed.append(json.dumps(data))
    data=copy.deepcopy(base);data["schema_version"]=True;malformed.append(json.dumps(data))
    data=copy.deepcopy(base);data["cases"][0]["extra"]=1;malformed.append(json.dumps(data))
    data=copy.deepcopy(base);data["cases"][1]["id"]="cost_line";malformed.append(json.dumps(data))
    data=copy.deepcopy(base);data["provenance"]["kind"]="observed";malformed.append(json.dumps(data))
    malformed.extend(['{"schema_version":1,"schema_version":1}', '{"x":NaN}', '{broken'])
    with tempfile.TemporaryDirectory(prefix="v04-c07-") as temp:
        folder=Path(temp)
        valid=subprocess.run([sys.executable,str(PROGRAM)],cwd=folder,capture_output=True,text=True)
        require(valid.returncode == 0 and not valid.stderr and json.loads(valid.stdout)["cases"] == reports, "CLI / independent cwd")
        for optimized in [False,True]:
            prefix=[sys.executable]+(["-O"] if optimized else [])+[str(PROGRAM)]
            for index, document in enumerate(malformed):
                path=folder/(str(index)+".json");path.write_text(document)
                result=subprocess.run(prefix+[str(path)],capture_output=True,text=True)
                require(result.returncode != 0 and not result.stdout and "regression input error" in result.stderr,
                        "invalid input must fail without numeric report")
        bad=folder/"invalid-utf8.json";bad.write_bytes(b'\xff')
        for path in [bad,folder/"absent.json"]:
            result=subprocess.run([sys.executable,str(PROGRAM),str(path)],capture_output=True,text=True)
            require(result.returncode != 0 and not result.stdout, "file/encoding diagnostic")
    require(CASES.read_bytes() == original, "input was modified")
    checks.append(str(len(malformed)) + " malformed/type/schema/rank cases rejected under ordinary and optimized Python; successful read-only CLI from another directory, missing-file and encoding failures")

    parser=Manuscript(); text=CHAPTER.read_text();parser.feed(text)
    require(not parser.forbidden and parser.worked == 2 and parser.exercises == 8 and parser.answers == 8,
            "chapter structure and exercise/solution count")
    sources=json.loads(SOURCES.read_text())
    require(parser.sources == {s["id"] for s in sources}, "source records and manuscript IDs")
    for link in parser.links:
        if link.startswith("v04-c07-"):
            require((ROOT/"content/projects"/link).is_file(), "flat download target missing")
    require(len(parser.snippets) == 1, "expected one executable snippet")
    output=io.StringIO()
    with contextlib.redirect_stdout(output):
        exec(compile(parser.snippets[0],"v04-c07 snippet","exec"),{})
    require(output.getvalue() == "7/10 6/5\n", "instructional snippet output")
    require(all(label in text for label in ["Capability:","Prerequisite:","Teach-back", "Delayed check", "v04-c08.html"]), "instructional gates")
    checks.append("Two worked examples, eight matched exercises/solutions, executable exact-arithmetic snippet, flat downloads, source IDs and retention/successor gates")
    return {"chapter":"v04-c07","status":"passed","checks":checks,
            "limitations":["Proof, interpretation and open-ended criteria also require author/root reading; finite computational checks are not an external academic review.",
                           "Data and evaluation outcomes are synthetic; no real forecasting or causal performance is established.",
                           "Exact arithmetic avoids rounding but does not remove sensitivity; benchmark is intentionally bounded and not a general floating-data regression library.",
                           "Whole-library acceptance/citation integration belongs to root; visual/mobile/print UI QA remains pending after prior browser-policy rejection."]}


if __name__ == "__main__":
    print(json.dumps(check(), indent=2))
