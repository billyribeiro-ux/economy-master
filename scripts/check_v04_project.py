"""Independent reference, numerical and workflow audit of the Volume 4 project."""

from copy import deepcopy
from decimal import Decimal, localcontext, ROUND_HALF_UP
from fractions import Fraction as F
from html.parser import HTMLParser
import contextlib
import hashlib
import io
import json
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PROJECTS = ROOT / "content/projects"
PROGRAM = PROJECTS / "v04-project-analysis.py"
DATA = "v04-project-data.json"
EXTRACT = "v04-project-source-extract.txt"
MANIFEST = "v04-project-manifest.json"
FIELDS = ("population_thousands", "labor_force_thousands", "employed_thousands",
          "unemployed_thousands", "not_in_labor_force_thousands")
RATES = ("published_unemployment_percent", "published_participation_percent",
         "published_employment_population_percent")
REFERENCE = [
    ("2024-02", "2024-07-05", 267711, 167426, 160968, 6458, 100285, "3.9", "62.5", "60.1"),
    ("2024-03", "2024-08-02", 267884, 167895, 161466, 6429, 99989, "3.8", "62.7", "60.3"),
    ("2024-04", "2024-08-02", 268066, 167982, 161491, 6492, 100083, "3.9", "62.7", "60.2"),
    ("2024-05", "2024-08-02", 268248, 167732, 161083, 6649, 100516, "4.0", "62.5", "60.1"),
    ("2024-06", "2024-08-02", 268438, 168009, 161199, 6811, 100429, "4.1", "62.6", "60.1"),
    ("2024-07", "2024-08-02", 268644, 168429, 161266, 7163, 100215, "4.3", "62.7", "60.0"),
]


def require(condition, label):
    if not condition:
        raise AssertionError(label)


def near(actual, reference, tolerance=1e-12):
    require(abs(actual-float(reference)) <= tolerance, (actual, str(reference)))


def reject(call):
    try:
        call()
    except (ValueError, TypeError, KeyError, ZeroDivisionError):
        return
    raise AssertionError("invalid input accepted")


def q(field):
    return F(field["exact"])


class Fragment(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.links = []
        self.sources = set()
        self.heading = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        require(tag not in {"html", "body", "h1", "script"}, "fragment format")
        if "id" in attrs:
            self.ids.append(attrs["id"])
        if tag == "h2" and attrs.get("id") == "project":
            self.heading = "project"
        if tag == "a":
            self.links.append(attrs.get("href", ""))
        if "data-source" in attrs:
            self.sources.add(attrs["data-source"])


def check():
    checks = []
    output = io.StringIO()
    with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
        m = runpy.run_path(str(PROGRAM), run_name="v04_project_independent_check")
    require(output.getvalue() == "", "quiet import")
    data, manifest = m["load_inputs"](PROJECTS)
    before = deepcopy(data)
    report = m["analyze"](data)
    require(data == before and report["status"] == "passed", "baseline/nonmutation")
    fields = ("month", "source_release") + FIELDS + RATES
    require([tuple(row[key] for key in fields) for row in data["rows"]] == REFERENCE, "separate archived reference")
    checks.append("Six full source records, two per-row release vintages and all 48 numerical fields match a separately recorded full-header BLS reference.")

    with localcontext() as context:
        context.prec = 70
        rounding_pairs = []
        for row, audit in zip(REFERENCE, report["row_audits"]):
            month, release, p, labor, employed, unemployed, outside, *published = row
            require(audit["month"] == month and audit["source_release"] == release, "row audit identity")
            pairs = ((unemployed, labor), (labor, p), (employed, p))
            for label, (a,b), display in zip(("unemployment", "participation", "employment_population"), pairs, published):
                actual = audit["metrics"][label]
                ratio = Decimal(100) * a / b
                low = Decimal(100) * (Decimal(a)-Decimal("0.5")) / (Decimal(b)+Decimal("0.5"))
                high = Decimal(100) * (Decimal(a)+Decimal("0.5")) / (Decimal(b)-Decimal("0.5"))
                require(str(ratio.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)) == display, "decimal rate display")
                require(q(actual["reconstructed_percent"]) == F(100*a,b) and actual["display_matches"], "exact rate")
                near(actual["reconstructed_percent"]["approx"],ratio)
                near(actual["level_rounding_envelope_percent"][0]["approx"],low)
                near(actual["level_rounding_envelope_percent"][1]["approx"],high)
                if label == "unemployment":
                    rounding_pairs.append((low,high))
                for da in (Decimal("-0.5"),Decimal(0),Decimal("0.5")):
                    for db in (Decimal("-0.5"),Decimal(0),Decimal("0.5")):
                        require(low <= 100*(a+da)/(b+db) <= high, "rounding corners")
            require(audit["labor_force_identity_residual_thousands"] == labor-employed-unemployed, "L-E-U")
            require(audit["population_identity_residual_thousands"] == p-labor-outside, "P-L-N")
            u, participation, e = F(100*unemployed,labor),F(100*labor,p),F(100*employed,p)
            require(q(audit["employment_ratio_identity_gap_pp"]) == e-participation*(1-u/100), "ratio identity")
        change=report["february_to_july_unemployment_change"]
        near(change["conditional_rounding_envelope_pp"][0]["approx"],rounding_pairs[-1][0]-rounding_pairs[0][1])
        near(change["conditional_rounding_envelope_pp"][1]["approx"],rounding_pairs[-1][1]-rounding_pairs[0][0])
        require(q(change["displayed_rate_change_pp"]) == F(2,5), "displayed change")
        require(q(change["reconstructed_ratio_change_pp"]) == F(716300,168429)-F(645800,167426), "ratio change")
    require([(v["month"],v["identity"],v["residual_thousands"]) for v in report["nonzero_component_residuals"]] == [
        ("2024-04","labor_force_identity_residual_thousands",-1),
        ("2024-04","population_identity_residual_thousands",1),
        ("2024-06","labor_force_identity_residual_thousands",-1)], "three residuals retained")
    checks.append("Independent 70-digit Decimal reconstruction of 18 rates, 162 bounded rounding perturbations, all count/rate identities and the endpoint-change envelope agree.")

    # Independent 2x2 normal-equation elimination (program uses centering).
    x = list(map(F,range(1,7)))
    y = list(map(F,[row[-3] for row in REFERENCE]))
    n=F(len(x)); sx=sum(x); sy=sum(y); sxx=sum(t*t for t in x); sxy=sum(t*v for t,v in zip(x,y))
    determinant=n*sxx-sx*sx
    a=(sy*sxx-sx*sxy)/determinant
    b=(n*sxy-sx*sy)/determinant
    result=report["descriptive_ols_on_published_rates"]
    require(a==F(37,10) and b==F(3,35) and q(result["intercept_percent"])==a and q(result["slope_pp_per_month"])==b, "OLS coefficients")
    fitted=[a+b*t for t in x]; residual=[v-f for v,f in zip(y,fitted)]
    sse=sum(e*e for e in residual); tss=sum(v*v for v in y)-sy*sy/n
    require(list(map(q,result["fitted_percent"]))==fitted and list(map(q,result["residuals_pp"]))==residual, "fits/residuals")
    require(sum(residual)==sum(t*e for t,e in zip(x,residual))==0, "normal equations")
    require(q(result["sse_pp2"])==sse==F(11,350) and q(result["tss_pp2"])==tss==F(4,25), "SS")
    require(q(result["explained_ss_pp2"])==F(9,70) and q(result["r_squared"])==F(45,56), "R2")
    perfect=m["ols"]([1,2,3],[5,8,11])
    require(q(perfect["intercept_percent"])==2 and q(perfect["slope_pp_per_month"])==3 and q(perfect["sse_pp2"])==0, "perfect linear boundary")
    constant=m["ols"]([1,2,3],[7,7,7])
    require(constant["r_squared"] is None and q(constant["slope_pp_per_month"])==0, "constant R2 undefined")
    reject(lambda:m["ols"]([1,1],[2,3]))
    reject(lambda:m["ols"]([1,2],[3]))
    checks.append("Independent normal-equation elimination, exact fitted/residual/SS/R2 checks and perfect-fit, constant-outcome and rank-deficient boundaries.")

    # Forecast oracle uses average successive increments, rather than endpoints.
    forecast=report["chronological_pedagogical_forecasts"]
    require(forecast["selected_rule"]=="naive" and forecast["tie_occurred"], "fixed tie")
    for item in forecast["validation"]+forecast["test"]:
        index=[row[0] for row in REFERENCE].index(item["target_month"])
        history=y[:index]
        prediction=history[-1]
        if item["rule"]=="drift":
            prediction+=sum(history[i]-history[i-1] for i in range(1,len(history)))/(len(history)-1)
        require(item["history_months"]==[row[0] for row in REFERENCE[:index]], "prefix chronology")
        require(q(item["forecast_percent"])==prediction and q(item["error_pp"])==y[index]-prediction, "forecasts/errors")
        require(q(item["squared_error_pp2"])==(y[index]-prediction)**2, "loss")
    require(q(forecast["test_mse_pp2"]["naive"])==F(1,40), "naive MSE")
    require(q(forecast["test_mse_pp2"]["drift"])==F(97,7200), "drift MSE")
    require(q(forecast["selected_rule_test_mse_pp2"])==F(1,40), "no test reselection")
    for last in (F(0),F(2),F(8),F(100)):
        changed=y[:-1]+[last]
        modified=m["forecast_protocol"](changed)
        require(modified["validation"]==forecast["validation"] and modified["selected_rule"]=="naive", "test outcome cannot alter selection")
        for old,new in zip(forecast["test"],modified["test"]):
            require(old["forecast_percent"]==new["forecast_percent"], "July outcome cannot alter any forecast")
        require(modified["test"][:2]==forecast["test"][:2], "future outcome cannot alter June")
    changed=y.copy(); changed[4]=F(8)
    modified=m["forecast_protocol"](changed)
    require(modified["selected_rule"]=="naive" and modified["test"][0]["forecast_percent"]==forecast["test"][0]["forecast_percent"], "June target cannot alter June forecast")
    require(q(modified["test"][2]["forecast_percent"])==8, "June revealed for July updating")
    require(m["forecast_protocol"]([1,2,3,4,5,6])["selected_rule"]=="drift", "non-tie selection")
    reject(lambda:m["forecast"]([],"naive"))
    reject(lambda:m["forecast"]([1],"drift"))
    reject(lambda:m["forecast_protocol"]([1,2,3]))
    # Deliberately leaking target-as-forecast would produce zero validation
    # error, unlike the independently fixed 0.01; it fails the fixture.
    require((y[3]-y[3])**2 != q(forecast["validation"][0]["squared_error_pp2"]), "target-leak fixture detects fault")
    checks.append("All six forecast rows and both exact MSEs independently checked; tie rule, future-target isolation, allowed updating, non-tie selection and a target-leak fixture verified.")

    corrupted=deepcopy(data); corrupted["rows"][4]["labor_force_thousands"]=168109
    damaged=m["analyze"](corrupted)
    require(damaged["status"]=="numerical-mismatch" and not damaged["component_identities_compatible_with_rounding"], "corrupted denominator detected")
    require(damaged["row_audits"][4]["metrics"]["unemployment"]["display_matches"], "headline-only false assurance")
    require(damaged["row_audits"][4]["labor_force_identity_residual_thousands"]==99 and damaged["row_audits"][4]["population_identity_residual_thousands"]==-100, "invented residuals")
    invalid=[]
    for key,value in [("month","2024-03"),("source_release","2024-08-02"),("labor_force_thousands",0),
                      ("population_thousands",True),("unemployed_thousands",6458.0),("employed_thousands",-1),
                      ("not_in_labor_force_thousands",1000001),("published_unemployment_percent",3.9),
                      ("published_participation_percent","62.50"),("published_employment_population_percent","NaN")]:
        item=deepcopy(data);item["rows"][0][key]=value;invalid.append(item)
    for key,value in [("adjustment","NSA"),("level_unit","persons"),("schema_version",True)]:
        item=deepcopy(data);item[key]=value;invalid.append(item)
    item=deepcopy(data);item["rows"][3]=deepcopy(item["rows"][2]);invalid.append(item)
    item=deepcopy(data);item["rows"].reverse();invalid.append(item)
    item=deepcopy(data);item["rows"].pop();invalid.append(item)
    item=deepcopy(data);del item["rows"][0]["unemployed_thousands"];invalid.append(item)
    item=deepcopy(data);item["extra"]=True;invalid.append(item)
    for item in invalid:
        reject(lambda item=item:m["validate_data"](item))
    for raw in (b'{"x":1,"x":2}',b'{"x":NaN}',b'{"x":Infinity}'):
        reject(lambda raw=raw:m["decode"](raw))
    original={name:(PROJECTS/name).read_bytes() for name in (DATA,EXTRACT,MANIFEST)}
    with tempfile.TemporaryDirectory(prefix="v04-project-check-") as name:
        temp=Path(name)
        def reset():
            for filename,raw in original.items(): (temp/filename).write_bytes(raw)
        def rehash():
            current=json.loads((temp/MANIFEST).read_text())
            current["sha256"]={filename:hashlib.sha256((temp/filename).read_bytes()).hexdigest() for filename in (DATA,EXTRACT)}
            (temp/MANIFEST).write_text(json.dumps(current))
        def invoke(optimized=False,extra=()):
            return subprocess.run([sys.executable]+(["-O"] if optimized else [])+[str(PROGRAM),str(temp)]+list(extra),cwd=temp,capture_output=True,text=True,check=False)
        for optimized in (False,True):
            reset();run=invoke(optimized)
            require(run.returncode==0 and not run.stderr, "baseline CLI")
            output=json.loads(run.stdout);meta=output.pop("reproducibility")
            require(output==report and meta["program_sha256"]==hashlib.sha256(PROGRAM.read_bytes()).hexdigest(), "CLI report/hash")
            for item in invalid:
                reset();(temp/DATA).write_text(json.dumps(item));rehash();run=invoke(optimized)
                require(run.returncode==1 and not run.stdout and run.stderr.startswith("Cannot reproduce Volume 4 project:"), "explicit optimized validation")
        reset();(temp/DATA).write_bytes(original[DATA]+b"\n");run=invoke()
        require(run.returncode==1 and "hash mismatch" in run.stderr, "byte hash drift")
        reset();(temp/DATA).write_text(json.dumps(corrupted));rehash();run=invoke()
        require(run.returncode==1 and "differ" in run.stderr, "text/JSON disagreement")
        (temp/EXTRACT).write_text((temp/EXTRACT).read_text().replace("2024-06|2024-08-02|268438|168009|","2024-06|2024-08-02|268438|168109|"));rehash();run=invoke()
        require(run.returncode==3 and json.loads(run.stdout)["status"]=="numerical-mismatch", "numerical failure exit")
        for key,value in [("tie_break","drift"),("train_months",["2024-02","2024-03","2024-04","2024-05"])]:
            reset();bad=deepcopy(manifest);bad["protocol"][key]=value;(temp/MANIFEST).write_text(json.dumps(bad));run=invoke()
            require(run.returncode==1 and "protocol" in run.stderr, "protocol drift rejection")
        reset();require(invoke(extra=("extra",)).returncode==2,"usage exit")
        (temp/MANIFEST).unlink();require(invoke().returncode==1,"missing manifest")
        run=subprocess.run([sys.executable,str(PROGRAM)],cwd=temp,capture_output=True,text=True,check=False)
        require(run.returncode==0 and not run.stderr,"independent cwd")
    require(all((PROJECTS/name).read_bytes()==raw for name,raw in original.items()),"frozen inputs unchanged")
    preserved=json.loads((PROJECTS/"v04-project-benchmark.json").read_text());meta=preserved.pop("reproducibility")
    require(preserved==report and meta["input_sha256"]==manifest["sha256"] and meta["program_sha256"]==hashlib.sha256(PROGRAM.read_bytes()).hexdigest(), "preserved benchmark current")
    checks.append("18 invalid contracts rejected normally and with -O, duplicate/nonfinite JSON rejection, byte/source/protocol corruption, numerical exit3 and portable read-only CLI behavior verified.")

    text=(ROOT/"content/assessment-parts/v04-project.html").read_text();parser=Fragment();parser.feed(text)
    require(parser.heading=="project" and len(parser.ids)==len(set(parser.ids)) and all(x=="project" or x.startswith("v04-project-") for x in parser.ids),"project ID ownership")
    downloads=[link for link in parser.links if link.startswith("v04-project-")]
    require(len(downloads)==6 and all("/" not in link and (PROJECTS/link).is_file() for link in downloads),"six flat downloads")
    sources=json.loads((ROOT/"content/reviews/v04-project-sources.json").read_text())
    require(parser.sources=={s["id"] for s in sources}|{"v04-c12-cps-definitions","v04-c12-public-use"},"source alignment")
    for source in sources:
        require(set(source)=={"id","title","url","use","checked","verification"},"source record fields")
    for word in ("100 points","D1","D2","D3","D4","D5","Instructor benchmark","exact tie selects naive","retrospectively assembled"):
        require(word in text,"instructional contract: "+word)
    checks.append("Project fragment IDs, six flat downloads, new/reused source IDs, five-domain 100-point rubric, full instructor guide and fixed-protocol wording checked.")
    return {"status":"passed","checks":checks,"limitations":[
        "Local references verify manually inspected archived aggregates and exact consequences, not BLS source authenticity, survey weighting or sampling uncertainty.",
        "Fixed period-index forecasts are a retrospective teaching exercise; neither contemporaneous vintage availability nor general predictive validity is established.",
        "Deterministic rounding envelopes and descriptive OLS are not causal effects or survey confidence intervals.",
        "Root owns integration/acceptance; visual, mobile and print QA were not performed."
    ]}


if __name__=="__main__":
    print(json.dumps(check(),indent=2))
