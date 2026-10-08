"""Independent arithmetic, information-time and behavior audit of the practical."""

from copy import deepcopy
from fractions import Fraction as F
from html.parser import HTMLParser
import contextlib
import hashlib
import io
import json
import math
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
PROJECTS=ROOT/"content/projects"
PROGRAM=PROJECTS/"foundation-practical-analysis.py"
DATA="foundation-practical-data.json"
SOURCE="foundation-practical-source.txt"
MANIFEST="foundation-practical-manifest.json"


def require(condition,message):
    if not condition: raise AssertionError(message)


def q(value): return F(value["exact"])


def reject(call):
    try: call()
    except (ValueError,TypeError,KeyError,ZeroDivisionError): return
    raise AssertionError("invalid input unexpectedly accepted")


class Fragment(HTMLParser):
    def __init__(self):
        super().__init__();self.ids=[];self.links=[];self.items=0;self.project=False
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        require(tag not in {"html","body","h1","script"},"plain fragment")
        if "id" in attrs:self.ids.append(attrs["id"])
        if tag=="a":self.links.append(attrs.get("href",""))
        if tag=="li":self.items+=1
        if tag=="h2" and attrs.get("id")=="practical":self.project=True


def check():
    checks=[];capture=io.StringIO()
    with contextlib.redirect_stdout(capture),contextlib.redirect_stderr(capture):
        m=runpy.run_path(str(PROGRAM),run_name="foundation_practical_reference_audit")
    require(not capture.getvalue(),"quiet import")
    data,manifest=m["load"](PROJECTS);before=deepcopy(data);r=m["analyze"](data)
    require(data==before and r["status"]=="passed","read-only baseline")
    accounts=r["ledger"]
    # Independent signed-flow/stock calculations, not the program transaction loop.
    cash=200000+20000+60000-40000-10000+50000-5000-12000
    profit=90000-40000-15000
    closing={"cash":cash,"receivables":30000+90000-20000-60000,"equipment":100000,
             "payables":20000+15000-10000,"loan":60000+50000-5000,"equity":250000+profit-12000}
    require(accounts["closing_balances_cents"]==closing,"closing stocks")
    require(cash==263000 and profit==35000,"cash/profit")
    operating=profit-(closing["receivables"]-30000)+(closing["payables"]-20000)
    require(operating==30000==accounts["operating_cash_flow_cents"],"profit-cash independent bridge")
    require(accounts["financing_cash_flow_cents"]==33000 and accounts["cash_change_cents"]==63000,"funding flow")
    require(closing["cash"]+closing["receivables"]+closing["equipment"]==403000
            ==closing["payables"]+closing["loan"]+closing["equity"],"closing identity")
    checks.append("Independently reconciled all opening/closing stocks, profit350 USD, operating300/financing330 cash flows and the separate2630-USD bank balance.")

    operations=r["operations"];fit=operations["frozen_origin_ols"]
    x=list(map(F,[0,1,2,3]));y=list(map(F,[0,4,4,10]))
    # Solve normal equations by determinant; program uses centered sums.
    determinant=4*sum(t*t for t in x)-sum(x)**2
    b=(4*sum(t*v for t,v in zip(x,y))-sum(x)*sum(y))/determinant
    a=(sum(y)-b*sum(x))/4
    require(a==q(fit["intercept_usd"])==0 and b==q(fit["slope_usd_per_job"])==3,"OLS")
    residual=[v-a-b*t for t,v in zip(x,y)]
    require(list(map(q,fit["residuals_usd"]))==residual==[0,1,-2,1],"residuals")
    require(sum(residual)==sum(t*e for t,e in zip(x,residual))==0,"normal equations")
    require(q(fit["sse_usd2"])==6 and q(fit["tss_usd2"])==51 and q(fit["r_squared"])==F(15,17),"fit totals")
    require([v["version"] for v in operations["training_versions"]]==[1]*4,"origin versions")
    require([v["cost_cents"] for v in operations["training_versions"]]==[0,400,400,1000],"zero retained/future revision excluded")
    targets=operations["forecasts"]
    require([q(v["forecast_usd"]) for v in targets]==[12,15],"frozen target forecasts")
    require(q(targets[0]["error_usd"])==3 and q(targets[0]["squared_error_usd2"])==9,"D5 score")
    require(all(targets[1][key] is None for key in ("first_release_actual_usd","outcome_release_at","error_usd","squared_error_usd2")),"missing remains null")
    require(operations["scored_count"]==1 and operations["unscored_count"]==1 and q(operations["available_outcome_mse_usd2"])==9,"score denominator")
    revised=operations["latest_snapshot_training_refit_for_diagnostic_only"]
    require(q(revised["intercept_usd"])==F(2,5) and q(revised["slope_usd_per_job"])==F(17,5),"revision diagnostic")
    require(q(revised["intercept_usd"])+4*q(revised["slope_usd_per_job"])==14,"leaky retrospective prediction")
    changed=deepcopy(data);changed["operations"][2]["cost_releases"][1]["cost_cents"]=1800
    altered=m["analyze"](changed)["operations"]
    require(altered["frozen_origin_ols"]==fit and altered["forecasts"]==targets,"late revision cannot change origin")
    require(altered["latest_snapshot_training_refit_for_diagnostic_only"]!=revised,"later diagnostic does change")
    changed=deepcopy(data);changed["operations"][4]["cost_releases"][0]["cost_cents"]=2500
    altered=m["analyze"](changed)["operations"]
    require(altered["frozen_origin_ols"]==fit and [q(t["forecast_usd"]) for t in altered["forecasts"]]==[12,15],"test label cannot alter forecasts")
    changed=deepcopy(data);changed["operations"][5]["cost_releases"]=[{"version":1,"released_at":"2025-04-12T09:00:00Z","cost_cents":1800}];changed["operations"][5]["missing_reason"]=None
    transfer=m["analyze"](changed)
    require(transfer["operations"]["scored_count"]==2 and transfer["operations"]["unscored_count"]==0
            and q(transfer["operations"]["available_outcome_mse_usd2"])==9,"hypothetical new release")
    require(transfer["operations"]["frozen_origin_ols"]==fit and transfer["capital"]==r["capital"],"unrelated targets remain fixed")
    require((F(9)+15**2)/2==117,"false zero-imputation counterexample")
    checks.append("All OLS/projection/score targets, revised-fit diagnostic, observed zero, missing outcome and future-label/revision isolation checked; hypothetical D6 release increases coverage without changing MSE.")

    capital=r["capital"];discount=[F(4,5),F(16,25)]
    # Evaluate state cash flows year by year, separately from annuity implementation.
    payoffs=[-500+sum(F(flow)*factor for factor in discount) for flow in (400,200)]
    p=[F(4,5),F(1,5)];mean=sum(prob*value for prob,value in zip(p,payoffs))
    second=sum(prob*value*value for prob,value in zip(p,payoffs));variance=second-mean*mean
    require(payoffs==[76,-212] and mean==F(92,5) and variance==F(331776,25),"state moments")
    require(q(capital["expected_npv_usd"])==mean and q(capital["payoff_variance_usd2"])==variance,"model output")
    losses={"buy":[0,212],"defer":[76,0]}
    for action,values in losses.items():
        require(q(capital["expected_regret_usd"][action])==sum(prob*loss for prob,loss in zip(p,values)),"regret losses")
    require(q(capital["break_even_price_usd"])==F(2592,5) and q(capital["cash_price_ceiling_usd"])==630,"price constraints")
    require(q(capital["break_even_high_probability"])==F(53,72),"probability threshold")
    require((400*F(5,4)+400-500*F(25,16))*F(16,25)==76,"independent terminal-value check")
    for price,expected,choice in [(50000,F(92,5),"buy"),(52000,F(-8,5),"defer"),(51840,F(0),"defer")]:
        changed=deepcopy(data);changed["investment"]["price_cents"]=price
        result=m["analyze"](changed)["capital"]
        require(q(result["expected_npv_usd"])==expected and result["decision_from_exact_model"]==choice,"price transfer/tie")
    changed=deepcopy(data);changed["investment"]["minimum_cash_reserve_cents"]=220000
    result=m["analyze"](changed)["capital"]
    require(not result["immediate_reserve_feasible"] and result["decision_from_exact_model"]=="defer"
            and q(result["expected_npv_usd"])>0 and "Unconstrained" in result["regret_scope"],"feasibility separately binds")
    simulation=capital["simulation"];n=simulation["replications"];h=simulation["state_counts"]["high"];l=simulation["state_counts"]["low"]
    require(h+l==n==400,"simulation count")
    simulated_mean=F(76*h-212*l,n)
    # Independent count-weighted raw second moment for sample variance.
    sample_variance=(F(h*76**2+l*212**2)-n*simulated_mean**2)/(n-1)
    require(q(simulation["mean_npv_usd"])==simulated_mean and q(simulation["error_against_exact_mean_usd"])==simulated_mean-mean,"simulated moments")
    require(math.isclose(simulation["estimated_mcse_usd"],math.sqrt(float(sample_variance/n)),rel_tol=1e-14),"estimated MCSE")
    require(math.isclose(simulation["theoretical_mcse_usd"],5.76,rel_tol=1e-14),"true MCSE")
    require(math.sqrt(float(variance))==115.2 and math.sqrt(float(variance/1600))==2.88,"risk and run-size scaling")
    require(capital["decision_from_exact_model"]=="buy" and capital["immediate_reserve_feasible"],"exact feasible action")
    checks.append("Independent state-by-year NPVs, raw-moment variance, regret tables, probability/price thresholds, terminal-value check,520-price transfer, exact tie, binding reserve and count-weighted MCSE verified.")

    invalid=[]
    def add(change):
        item=deepcopy(data);change(item);invalid.append(item)
    add(lambda d:d.update(money_unit="dollar"))
    add(lambda d:d.update(schema_version=True))
    add(lambda d:d["opening_balances_cents"].update(cash=True))
    add(lambda d:d["ledger"][0].update(amount_cents=20000.0))
    add(lambda d:d["operations"][1].update(record_id="D1"))
    add(lambda d:d["operations"][1].update(period="2025-04-01"))
    add(lambda d:d["operations"][2]["cost_releases"][1].update(version=1))
    add(lambda d:d["operations"][0]["cost_releases"][0].update(cost_cents=True))
    add(lambda d:d["operations"][0]["cost_releases"][0].update(released_at="2025-03-31T09:00:00Z"))
    add(lambda d:d["operations"][4].update(feature_available_at="2025-04-08T13:00:00Z"))
    add(lambda d:d["operations"][5].update(active=False))
    add(lambda d:d["operations"][5].update(missing_reason=None))
    add(lambda d:d["investment"].update(annual_effective_nominal_rate="-1"))
    add(lambda d:d["investment"]["states"][0].update(probability="0"))
    add(lambda d:d["investment"]["states"][1].update(probability="1/2"))
    add(lambda d:d["simulation"].update(replications=1))
    add(lambda d:d["forecast_protocol"].update(forecast_mode="refit after outcomes"))
    add(lambda d:d["operations"][0]["cost_releases"][0].update(released_at="2025-04-31T09:00:00Z"))
    for item in invalid:reject(lambda item=item:m["validate"](item))
    for raw in (b'{"a":1,"a":2}',b'{"a":NaN}',b'{"a":Infinity}'):
        reject(lambda raw=raw:m["decode"](raw))
    broken=deepcopy(data);broken["ledger"][6]["amount_cents"]+=1000
    discrepancy=m["analyze"](broken)
    require(discrepancy["status"]=="cash-reconciliation-failed" and discrepancy["ledger"]["closing_balances_cents"]["cash"]==264000
            and discrepancy["ledger"]["balance_sheet_residual_cents"]==0,"cash failure despite algebraic balance")
    originals={filename:(PROJECTS/filename).read_bytes() for filename in (DATA,SOURCE,MANIFEST)}
    with tempfile.TemporaryDirectory(prefix="foundation-practical-check-") as name:
        temp=Path(name)
        def reset():
            for filename,raw in originals.items():(temp/filename).write_bytes(raw)
        def rehash():
            updated=json.loads((temp/MANIFEST).read_text());updated["sha256"]={f:hashlib.sha256((temp/f).read_bytes()).hexdigest() for f in (DATA,SOURCE)}
            (temp/MANIFEST).write_text(json.dumps(updated))
        def invoke(optimized=False,extra=()):
            return subprocess.run([sys.executable]+(["-O"] if optimized else [])+[str(PROGRAM),str(temp)]+list(extra),cwd=temp,capture_output=True,text=True,check=False)
        for optimized in (False,True):
            reset();run=invoke(optimized);require(run.returncode==0 and not run.stderr,"portable baseline CLI")
            output=json.loads(run.stdout);meta=output.pop("reproducibility");require(output==r,"normal/optimized numeric parity")
            require(meta["input_sha256"]==manifest["sha256"],"reported input hashes")
            for item in invalid:
                reset();(temp/DATA).write_text(json.dumps(item));rehash();run=invoke(optimized)
                require(run.returncode==1 and not run.stdout and run.stderr.startswith("Cannot complete foundation practical:"),"required validation survives optimization")
        reset();(temp/DATA).write_bytes(originals[DATA]+b"\n");run=invoke()
        require(run.returncode==1 and "hash mismatch" in run.stderr,"byte drift")
        reset();(temp/DATA).write_text(json.dumps(broken));rehash();run=invoke()
        require(run.returncode==3 and json.loads(run.stdout)["status"]=="cash-reconciliation-failed","reconciliation exit3")
        reset();require(invoke(extra=("extra",)).returncode==2,"usage status")
        (temp/MANIFEST).unlink();require(invoke().returncode==1,"missing input")
        run=subprocess.run([sys.executable,str(PROGRAM)],cwd=temp,capture_output=True,text=True,check=False)
        require(run.returncode==0 and not run.stderr,"default path independent of cwd")
    require(all((PROJECTS/f).read_bytes()==raw for f,raw in originals.items()),"input nonmutation")
    benchmark=json.loads((PROJECTS/"foundation-practical-benchmark.json").read_text());meta=benchmark.pop("reproducibility")
    # randrange streams are runtime-specific: require exact record equality on
    # the recorded runtime; elsewhere preserve deterministic fields and audit
    # simulation from that run's own reported counts.
    same_runtime=meta["python_version"]==sys.version.split()[0]
    if same_runtime:require(benchmark==r,"preserved output on recorded runtime")
    else:
        benchmark["capital"].pop("simulation");candidate=deepcopy(r);candidate["capital"].pop("simulation")
        require(benchmark==candidate,"deterministic fields across runtime")
    require(meta["program_sha256"]==hashlib.sha256(PROGRAM.read_bytes()).hexdigest(),"current program fingerprint")
    checks.append("18 invalid schema/unit/key/time/version/probability cases rejected in normal and -O CLI; duplicate/nonfinite JSON, hash drift, independent cash failure exit3, portability and unchanged inputs checked.")

    html=(ROOT/"content/assessment-parts/foundation-practical.html").read_text();parser=Fragment();parser.feed(html)
    require(parser.project and len(parser.ids)==len(set(parser.ids)) and all(i=="practical" or i.startswith("foundation-practical-") for i in parser.ids),"owned heading/IDs")
    require(parser.items==40,"twenty five-point tasks and twenty answers")
    downloads=[v for v in parser.links if v.startswith("foundation-practical-")]
    require(len(downloads)==6 and all("/" not in v and (PROJECTS/v).is_file() for v in downloads),"six flat files")
    for link in parser.links:
        if link.startswith("v") and link.endswith(".html"):require((ROOT/"content/chapters"/link).is_file(),"accepted chapter route")
    for word in ("85/100","19/25","3–5 hours","synthetic","Complete instructor answers","unreported","USD²"):
        require(word in html,"assessment scope: "+word)
    checks.append("Four25-point domains,20 complete five-point parts/answers, six downloads, owned IDs, accepted-method routes, mastery gates and missingness/synthetic disclosures checked.")
    return {"status":"passed","checks":checks,"limitations":[
        "Synthetic records and finite-state probabilities are assumptions, not empirical validation or causal evidence.",
        "One available forecast score cannot identify the missing target loss or generalize to population performance.",
        "Seeded high-level random streams may vary by Python version; exact model quantities and count-based simulation reconciliation are the comparison targets.",
        "Root owns integration/acceptance; visual/mobile/print QA and external learner calibration were not performed."
    ]}


if __name__=="__main__":print(json.dumps(check(),indent=2))
