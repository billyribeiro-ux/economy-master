"""Independent exact calculations and information-boundary audit for c09."""
import contextlib
import copy
from fractions import Fraction as F
from html.parser import HTMLParser
import io
from itertools import product
import json
import math
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "content/projects"
PROGRAM = PROJECT / "v04-c09-validation.py"
INPUT = PROJECT / "v04-c09-case.json"


def require(value, message):
    if not value:
        raise AssertionError(message)


def reject(function, *args):
    try:
        function(*args)
    except (TypeError, ValueError):
        return
    raise AssertionError("invalid case was accepted")


def independently_score(case, targets, fixed=None):
    """Read each permitted row separately; weighted formula, not endpoint code."""
    answer = {m: [] for m in ("naive", "mean", "drift")}
    rows = {r["period"]: r for r in case["records"]}
    for target in targets:
        origin = target - 1 if fixed is None else fixed
        eligible = [t for t in sorted(rows) if t <= origin and rows[t]["released"] <= origin]
        first, last = eligible[0], eligible[-1]
        weights = F(target - first, last - first)
        values = {"naive": F(rows[last]["value"]),
                  "mean": F(sum(rows[t]["value"] for t in eligible), len(eligible)),
                  "drift": weights * rows[last]["value"] + (1 - weights) * rows[first]["value"]}
        for name, predicted in values.items():
            answer[name].append((predicted, F(rows[target]["value"]) - predicted, eligible))
    return answer


def check():
    checks = []
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        mod = runpy.run_path(str(PROGRAM))
    require(not output.getvalue(), "import must be quiet")
    data = mod["load_case"](INPUT)
    untouched = copy.deepcopy(data)
    report = mod["build_report"](data)
    require(data == untouched, "case mutated")
    require(report["selected_method"] == "drift", "validation winner")
    expected_mse = {
        "validation": {"naive": F(43, 4), "mean": F(35109, 400), "drift": F(5641, 3600)},
        "test_updating": {"naive": F(7, 4), "mean": F(147373547, 1960200),
                          "drift": F(147393481, 25401600)},
        "test_fixed_origin": {"naive": F(3, 2), "drift": F(5133, 98)},
    }
    for part, targets, fixed in [("validation", range(5, 9), None),
                                  ("test_updating", range(9, 13), None),
                                  ("test_fixed_origin", range(9, 13), 8)]:
        oracle = independently_score(data, targets, fixed)
        for name, values in oracle.items():
            actual = report[part][name]
            require([r["prediction"] for r in actual["forecasts"]] == [v[0] for v in values], "independent forecast values")
            require([r["error"] for r in actual["forecasts"]] == [v[1] for v in values], "independent forecast errors")
            require([r["training_periods"] for r in actual["forecasts"]] == [v[2] for v in values], "exact eligible period sets")
            require(actual["mse"] == sum(v[1]**2 for v in values)/len(values), "independent loss")
            require(actual["mae"] == sum(abs(v[1]) for v in values)/len(values), "absolute loss")
            if name in expected_mse[part]:
                require(actual["mse"] == expected_mse[part][name], "published exact MSE")
    require(report["test_updating"]["drift"]["mse"] - F(7,4) == F(102940681,25401600), "exercise4 loss difference")
    checks.append("Every rolling and fixed-origin forecast, eligible row set and loss independently reconstructed with exact rational weights; all reported worked-example tables/MSEs")

    # Future labels must not affect any forecast already issued, or selection.
    changed = copy.deepcopy(data); changed["records"][-1]["value"] += 100
    later = mod["build_report"](changed)
    require(later["validation"] == report["validation"] and later["selected_method"] == report["selected_method"], "last test label entered development")
    for part in ["test_updating", "test_fixed_origin"]:
        for method in data["methods"]:
            require([r["prediction"] for r in later[part][method]["forecasts"]] == [r["prediction"] for r in report[part][method]["forecasts"]], "target label entered own/earlier forecast")
            require(later[part][method]["mse"] != report[part][method]["mse"], "scoring ignored changed actual")
    changed = copy.deepcopy(data); changed["records"][8]["value"] += 20
    later = mod["build_report"](changed)
    require(later["validation"] == report["validation"] and later["selected_method"] == "drift", "test-first label changed selected candidate")
    for method in data["methods"]:
        require(later["test_updating"][method]["forecasts"][0]["prediction"] == report["test_updating"][method]["forecasts"][0]["prediction"], "own label entered target9 forecast")
        require(later["test_updating"][method]["forecasts"][1]["prediction"] != report["test_updating"][method]["forecasts"][1]["prediction"], "prespecified refit ignored newly available label")
        require([r["prediction"] for r in later["test_fixed_origin"][method]["forecasts"]] == [r["prediction"] for r in report["test_fixed_origin"][method]["forecasts"]], "fixed origin learned future test data")
    # A delay affects use by origin, not reference-period labels alone.
    changed = copy.deepcopy(data); changed["records"][8]["released"] = 10
    delayed = mod["build_report"](changed)
    for method in data["methods"]:
        rows = delayed["test_updating"][method]["forecasts"]
        require(9 not in rows[1]["training_periods"] and 9 in rows[2]["training_periods"], "release availability ignored")
    require(delayed["test_updating"]["drift"]["forecasts"][1]["prediction"] == F(862,7), "elapsed-calendar delayed drift")
    changed = copy.deepcopy(data); changed["records"][7]["released"] = 9
    reject(mod["build_report"], changed)
    changed = copy.deepcopy(data); changed["records"].reverse()
    require(mod["build_report"](changed) == report, "raw order dependence")
    checks.append("Future-label mutation cannot alter earlier predictions or validation choice; allowed later updates do change; fixed forecasts stay frozen; late labels excluded or premature selection rejected; input-order invariance")

    cases = 0
    for offset, slope in product((0, 17, 100), (0, 2, 11)):
        d = copy.deepcopy(data)
        for row in d["records"]:
            row["value"] = offset + slope * row["period"]
        r = mod["build_report"](d)
        for part in ["validation", "test_updating", "test_fixed_origin"]:
            require(r[part]["drift"]["mse"] == 0, "linear path not extrapolated exactly")
        require(r["selected_method"] == ("naive" if slope == 0 else "drift"), "zero-loss tie order")
        cases += 1
    # All three rules are affine in observed values: add constant, predictions shift;
    # multiply values, squared errors multiply by the square (within input bounds).
    for factor, shift in [(1,100),(3,0),(2,50)]:
        d = copy.deepcopy(data)
        for row in d["records"]:row["value"] = factor * row["value"] + shift
        r = mod["build_report"](d)
        require(r["selected_method"] == report["selected_method"], "affine units changed winner")
        for part in ["validation","test_updating","test_fixed_origin"]:
            for m in data["methods"]:
                require(r[part][m]["mse"] == factor**2 * report[part][m]["mse"], "loss units")
                require(r[part][m]["mae"] == factor * report[part][m]["mae"], "absolute units")
                for a,b in zip(r[part][m]["forecasts"],report[part][m]["forecasts"]):
                    require(a["prediction"] == factor*b["prediction"]+shift, "affine prediction")
    checks.append(f"{cases} exact constant/linear paths, prespecified tie resolution and affine-unit/invariant checks across all forecast protocols")

    # Independent exercise and proof diagnostics, not substitutes for proof review.
    errors_a = [0,0,0,8]; errors_b = [3,3,3,3]
    require(sum(map(abs,errors_a))/4 == 2 and sum(v*v for v in errors_a)/4 == 16, "lossA")
    require(sum(map(abs,errors_b))/4 == 3 and sum(v*v for v in errors_b)/4 == 9, "lossB")
    require(sum((F(y)-F(9,10))**2 for y in [1,0,1,0])/4 == F(41,100), "Brier score")
    def cost(a):
        return sum(p*(9*max(y-a,0)+max(a-y,0)) for y,p in [(10,F(4,5)),(20,F(1,5))])
    require([cost(a) for a in [10,12,20]] == [18,16,8], "asymmetric action costs")
    require(min(range(0,31),key=cost) == 20, "cost minimizing action")
    require(sum(min(pair) for pair in product([8,12],repeat=2))/4 == 9, "selection optimism")
    require(F(2*1+8*9,10) == F(37,5), "fold weighting")
    difference = [F(a*a-b*b) for a,b in zip(errors_a,errors_b)]
    average = sum(difference)/4
    variance = sum((d-average)**2 for d in difference)/3
    require(average == 7 and variance == 1024 and math.sqrt(variance/4) == 16, "paired loss precision")
    require(10+2*F(2+4,2) == 16 and 10+2*F(2+4+100,3) == F(242,3), "imputation example")
    # Enumerated train randomness and independent outcome noise: mean forecast2,
    # true mean3, forecast variance1, outcome variance4 => risk6.
    risk = sum(F((y-f)**2,4) for y,f in product([1,5],[1,3]))
    require(risk == 4+1+1 == 6, "bias variance identity numerical illustration")
    checks.append("All determinate exercises: loss rankings/Brier score, asymmetric quantile decision, exact selection optimism, leakage imputation, unequal-fold weights and paired loss variance; enumerated bias-variance identity")

    invalid = []
    for value in [True, "100", 1.5, -1, 1000001, None]:
        d=copy.deepcopy(data);d["records"][0]["value"]=value;invalid.append(d)
    for key,value in [("schema_version",True),("unit","USD"),("selection_loss","mae"),
                      ("initial_training_end",1),("validation_end",12),
                      ("methods",["drift","mean","naive"]),("provenance","")]:
        d=copy.deepcopy(data);d[key]=value;invalid.append(d)
    d=copy.deepcopy(data);d["records"][1]["period"]=1;invalid.append(d)
    d=copy.deepcopy(data);d["records"][0]["released"]=0;invalid.append(d)
    d=copy.deepcopy(data);d["records"][0]["extra"]=0;invalid.append(d)
    d=copy.deepcopy(data);d["records"]=d["records"][:3];invalid.append(d)
    for d in invalid:reject(mod["build_report"],d)
    no_history=copy.deepcopy(data)
    for row in no_history["records"][:4]:row["released"]=8
    reject(mod["build_report"],no_history)
    documents = [json.dumps(d) for d in invalid] + ['{"a":1,"a":2}','{"a":NaN}','{bad']
    with tempfile.TemporaryDirectory(prefix="v04-c09-") as directory:
        temp=Path(directory)
        # Copied package truly runs without repository-only supporting files.
        copied=temp/PROGRAM.name;copied.write_bytes(PROGRAM.read_bytes())
        (temp/INPUT.name).write_bytes(INPUT.read_bytes())
        expected=json.loads(json.dumps(report,default=mod["encode"]))
        for flags in [[],["-O"]]:
            run=subprocess.run([sys.executable,*flags,str(copied)],cwd="/private/tmp",capture_output=True,text=True)
            require(run.returncode==0 and not run.stderr and json.loads(run.stdout)==expected,"copied offline CLI")
            for index,document in enumerate(documents):
                path=temp/f"bad-{index}.json";path.write_text(document)
                run=subprocess.run([sys.executable,*flags,str(copied),str(path)],capture_output=True,text=True)
                require(run.returncode!=0 and not run.stdout and "Cannot evaluate forecast case" in run.stderr,"invalid file did not fail cleanly")
        missing=subprocess.run([sys.executable,str(copied),str(temp/"absent.json")],capture_output=True,text=True)
        require(missing.returncode!=0 and not missing.stdout,"missing-file error")
    checks.append(f"{len(invalid)} invalid input contracts plus unavailable training history; {len(documents)} bad JSON/schema cases rejected normally and with assertions removed; copied read-only package works from unrelated directory")

    # The shared verifier handles chapter counts/links/source IDs after integration.
    chapter=(ROOT/"content/chapters/v04-c09.html").read_text()
    require(all(term in chapter for term in ["Capability:","Prerequisite:","Teach-back","Delayed check","v04-c10.html"]),"instructional structure")
    return {"chapter":"v04-c09","status":"passed","checks":checks,
            "limitations":["Proof assumptions, qualitative solutions and economic interpretations additionally require root/peer reading.",
                           "Synthetic paths establish no empirical forecast performance or future risk guarantee.",
                           "Fixed-program checks do not replace visual/mobile/print UI QA, which remains pending."]}


if __name__ == "__main__":
    print(json.dumps(check(),indent=2))
