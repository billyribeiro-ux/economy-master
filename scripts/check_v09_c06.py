"""Independent, quiet checks for the original Ilex factor package."""
from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
from fractions import Fraction as F
from html.parser import HTMLParser
from itertools import product
import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "content/projects"


class Structure(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack, self.ids, self.hrefs = [], [], []
        self.worked = self.exercises = self.solution_items = 0
        self.in_exercises = self.in_solutions = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag not in {"br", "hr", "img", "input", "meta", "link"}:
            self.stack.append(tag)
        if "id" in attrs:
            self.ids.append(attrs["id"])
        if "href" in attrs:
            self.hrefs.append(attrs["href"])
        classes = attrs.get("class", "").split()
        self.worked += "worked" in classes
        if tag == "ol" and "exercises" in classes:
            self.in_exercises = True
        if tag == "details" and "solutions" in classes:
            self.in_solutions = True
        if tag == "li":
            self.exercises += self.in_exercises
            self.solution_items += self.in_solutions

    def handle_endtag(self, tag):
        if not self.stack or self.stack.pop() != tag:
            raise AssertionError("Invalid fragment nesting: " + tag)
        if tag == "ol":
            self.in_exercises = False
        if tag == "details":
            self.in_solutions = False


def check():
    comparisons = 0
    rejections = 0
    groups = []

    def same(actual, expected, label):
        nonlocal comparisons
        comparisons += 1
        if actual != expected:
            raise AssertionError(f"{label}: {actual!r} != {expected!r}")

    def near(actual, expected, label):
        nonlocal comparisons
        comparisons += 1
        if not math.isclose(actual, expected, abs_tol=1e-12, rel_tol=1e-12):
            raise AssertionError(f"{label}: {actual!r} != {expected!r}")

    def rejects(call, label):
        nonlocal rejections
        try:
            call()
        except ValueError:
            rejections += 1
            return
        raise AssertionError("Missing domain rejection: " + label)

    def equivalent(actual, expected, path="output"):
        if isinstance(expected, float):
            near(actual, expected, path)
        elif isinstance(expected, dict):
            same(set(actual), set(expected), path + " fields")
            for key in expected:
                equivalent(actual[key], expected[key], path + "/" + key)
        elif isinstance(expected, list):
            same(len(actual), len(expected), path + " length")
            for i, value in enumerate(expected):
                equivalent(actual[i], value, path + "/" + str(i))
        else:
            same(actual, expected, path)

    quiet = io.StringIO()
    with redirect_stdout(quiet), redirect_stderr(quiet):
        spec = importlib.util.spec_from_file_location("ilex", ASSETS / "v09-c06-analysis.py")
        model = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(model)
        data = json.loads((ASSETS / "v09-c06-inputs.json").read_text())
        result = model.run(data)
    same(quiet.getvalue(), "", "quiet import and run")
    json.dumps(result, allow_nan=False)

    # Reconstruct the complete finite economy by signed asset quantities.
    state_rows = result["pricing"]["states"]
    sdf, evalues, factor1, factor2, claim_a, claim_b = [], [], [], [], [], []
    rf = F(51, 50)
    for row, (u, v, e) in zip(state_rows, product((-1, 1), repeat=3)):
        m = (F(1)-F(u, 4)-F(v, 5)-F(e, 10))/rf
        f1, f2 = F(3, 100)+F(3*u, 25), F(1, 50)+F(v, 10)
        g1, g2 = rf+f1, rf+f2
        xa = F(3, 2)*g1-F(1, 4)*g2-F(1, 4)*rf
        xb = xa+F(1, 250)+F(e, 25)
        same(F(row["sdf"]), m, "state kernel")
        same(F(row["replicated_gross_payoff"]), xa, "safe-closed replica payoff")
        same(F(row["priced_residual_gross_payoff"]), xb, "full residual claim payoff")
        same(xa-F(3, 2)*g1+F(1, 4)*g2+F(27, 100)*rf, F(51, 2500), "same-payoff clone hedge")
        same(F(row["clone_arbitrage_payoff"]), F(51, 2500), "reported statewise sure gain")
        sdf.append(m); evalues.append(F(e, 25)); factor1.append(f1); factor2.append(f2)
        claim_a.append(xa); claim_b.append(xb)
    same(len(state_rows), 8, "full sign-state set")
    same(min(sdf), F(15, 34), "strict kernel positivity")
    same(sum(sdf)/8, 1/rf, "safe price")
    for payoffs in (factor1, factor2):
        same(sum(m*x for m, x in zip(sdf, payoffs))/8, F(0), "traded factor zero price")
    for payoffs in (claim_a, claim_b):
        same(sum(m*x for m, x in zip(sdf, payoffs))/8, F(1), "gross claim price")
    same(F(49, 50)-F(3, 2)+F(1, 4)+F(27, 100), F(0), "clone initial budget")
    same(sum(evalues), F(0), "residual mean")
    for factors in (factor1, factor2):
        same(sum(f*e for f, e in zip(factors, evalues)), F(0), "factor residual orthogonality")
    covariance = sum(m*e for m, e in zip(sdf, evalues))/8
    same(-rf*covariance, F(1, 250), "residual price supports positive alpha")
    same(F(result["pricing"]["priced_residual_alpha"]), F(1, 250), "reported priced alpha")
    same(min(F(1, 250)+e for e in evalues), F(-9, 250), "alpha hedge retains a loss")
    near(result["pricing"]["residual_alpha_bound"], math.sqrt(9/80)/25, "SDF Cauchy bound")
    groups.append("Exact state prices, full replication budgets, clone arbitrage and priced factor-orthogonal residual")

    # Enumerate16 outcomes rather than the implementation's binomial formulas.
    n4 = next(row for row in result["diversification"]["rows"] if row["assets"] == 4)
    kernels, payoffs, individual = [], [], [[], [], [], []]
    for signs in product((-1, 1), repeat=4):
        kernel = F(1)/rf
        for e in signs:
            kernel *= 1-F(e, 10)
        zs = [F(1, 50)+F(e, 5) for e in signs]
        kernels.append(kernel); payoffs.append(sum(zs)/4)
        for j, z in enumerate(zs):
            individual[j].append(z)
    same(sum(kernels)/16, 1/rf, "product-kernel safe normalization")
    for zs in individual:
        same(sum(m*z for m, z in zip(kernels, zs))/16, F(0), "product-kernel claim price")
    mean = sum(payoffs)/16
    same(mean, F(n4["average_expected_payoff"]), "diversified physical mean")
    same(sum((x-mean)**2 for x in payoffs)/16, F(n4["average_residual_variance"]), "enumerated residual variance")
    same(F(sum(x < 0 for x in payoffs), 16), F(5, 16), "finite loss probability")
    same(F(n4["physical_probability_of_loss"]), F(5, 16), "binomial agrees with enumerated losses")
    cv2 = (sum(m*m for m in kernels)/16)/(sum(kernels)/16)**2-1
    same(cv2, F(n4["product_sdf_cv_squared"]), "kernel variation formula")
    same(min(kernels), F(n4["product_sdf_minimum"]), "positive product kernel")
    n100 = next(row for row in result["diversification"]["rows"] if row["assets"] == 100)
    near(n100["hypothetical_uniform_bound_on_mean"], 0.01, "separately hypothetical uniform bound")
    same(F(n100["product_sdf_cv_squared"]) > F(1, 4), True, "actual family violates proposed uniform bound")
    groups.append("Independent finite product-kernel enumeration, residual variance, loss states and uniform-bound distinction")

    # Recover two slopes with explicit centered two-by-two equations.
    obs = data["empirical"]["observations"]
    a = [F(row["factor_1"]) for row in obs]
    b = [F(row["factor_2"]) for row in obs]
    y = [F(row["asset_excess"]) for row in obs]
    am, bm, ym = sum(a)/8, sum(b)/8, sum(y)/8
    ac, bc, yc = [[v-m for v in col] for col, m in ((a, am), (b, bm), (y, ym))]
    aa, bb, ab = sum(x*x for x in ac), sum(x*x for x in bc), sum(x*z for x, z in zip(ac, bc))
    ay, by = sum(x*z for x, z in zip(ac, yc)), sum(x*z for x, z in zip(bc, yc))
    determinant = aa*bb-ab*ab
    beta1, beta2 = (ay*bb-by*ab)/determinant, (by*aa-ay*ab)/determinant
    full = result["empirical"]["two_factor_ols"]
    short = result["empirical"]["one_factor_ols"]
    same([ym-beta1*am-beta2*bm, beta1, beta2], [F(x) for x in full["coefficients"]], "centered independent full OLS")
    residual = [v-(F(1, 500)+F(5, 4)*x-F(1, 2)*z) for v, x, z in zip(y, a, b)]
    same(residual, [F(x) for x in full["residuals"]], "independent full residual vector")
    same(sum(r*r for r in residual), F(1, 5000), "full residual sum of squares")
    same(F(full["centered_sst"]), F(21, 5000), "response total variation")
    same(F(full["r_squared_with_intercept"]), F(20, 21), "descriptive fit")
    same(F(full["residual_mean_square_df"]), F(1, 25000), "five residual degrees of freedom")
    same([ym-ay/aa*am, ay/aa], [F(x) for x in short["coefficients"]], "direct one-factor slope and intercept")
    same(F(short["sse"]), F(1, 1000), "omitted-factor residual risk")
    same(F(short["r_squared_with_intercept"]), F(16, 21), "omitted-factor fit")
    same(ab/aa, F(1, 2), "omitted-variable coefficient channel")
    groups.append("Independent centered-moment OLS, residuals, omitted-factor slope/alpha and descriptive fit")

    betas = [[F(x) for x in row] for row in data["empirical"]["cross_section_betas"]]
    means = [F(x) for x in data["empirical"]["cross_section_mean_excess"]]
    bty = [sum(row[j]*v for row, v in zip(betas, means)) for j in range(2)]
    lambdas = [(3*bty[0]+bty[1])/17, (bty[0]+6*bty[1])/17]
    residuals = [v-row[0]*lambdas[0]-row[1]*lambdas[1] for row, v in zip(betas, means)]
    cross = result["empirical"]["cross_section_no_free_intercept"]
    same(lambdas, [F(x) for x in cross["coefficients"]], "closed two-pass inverse")
    same(residuals, [F(1, 500), F(1, 500), F(-1, 500), F(0)], "cross-sectional pricing residuals")
    same([F(x) for x in cross["residuals"]], residuals, "reported second-pass residuals")
    same(cross["r_squared_with_intercept"], None, "no misleading centered intercept R-squared")
    same(lambdas == [am, bm], False, "estimated risk prices differ from sample means")
    groups.append("Separate cross-sectional normal equations, estimated premiums and normalization limits")

    # Independent signed DOLLAR holdings ledger, not the code's share bookkeeping.
    target_rows = [[50,50,-50,-50],[-50,50,50,-50],[-50,-50,50,50],[50,-50,-50,50]]
    preceding = [F(0)]*4
    equity = F(100)
    trading_total = F(0)
    factor_payoffs = []
    account_growth = F(1)
    for i, (target_raw, source_row, actual) in enumerate(zip(target_rows, data["construction"]["observations"], result["construction"]["periods"])):
        target = [F(x) for x in target_raw]
        rs = [F(x) for x in source_row["simple_returns"]]
        traded = sum(abs(t-p) for t, p in zip(target, preceding))
        gross = sum(t*r for t, r in zip(target, rs))
        end_values = [t*(1+r) for t, r in zip(target, rs)]
        close_volume = sum(abs(x) for x in end_values) if i == 3 else F(0)
        charge = (traded+close_volume)/1000
        opening = equity
        equity += gross-charge-F(1, 10)
        same(F(actual["rebalance_dollar_volume"]), traded, "drift-aware traded volume")
        same(F(actual["liquidation_dollar_volume"]), close_volume, "terminal closure volume")
        same(F(actual["trading_cost"]), charge, "one-way cash costs")
        same(F(actual["ending_equity"]), equity, "dollar-holdings wealth")
        same(F(actual["account_simple_return"]), equity/opening-1, "account denominator")
        account_growth *= 1+F(actual["account_simple_return"])
        factor_payoffs.append(gross/100); trading_total += charge; preceding = end_values
    same(factor_payoffs, [F(7,200),F(7,200),F(1,25),F(0)], "lagged gross factors")
    same(trading_total, F(101,100), "all trading cost")
    same(equity, F(10959,100), "fully liquidated cash")
    same(F(result["construction"]["final_cash"]), equity, "reported investor receipt")
    same(result["construction"]["final_positions"], ["0"]*4, "nothing left open")
    same(account_growth, F(10959,10000), "account compounding reconciles")
    same(F(result["construction"]["mean_unavailable_hindsight_gross_factor"]), F(7,200), "hindsight comparison explicitly unavailable")
    same(F(result["construction"]["mean_gross_factor_per_notional"]), F(11,400), "actual lagged factor average")
    groups.append("Independent drifted-dollar cash ledger, complete liquidation and factor-versus-account measurement")

    # Exercises are independently reconstructed from their separate prompts.
    same(F(5,4)+F(1,2)-F(3,4), F(1), "E1 replica price")
    same(F(5,4)*F(1,25)+F(1,2)*F(1,40)+F(1,25), F(41,400), "E1 fair expected return")
    same(F(3,100)*F(26,25), F(39,1250), "E1 same-payoff arbitrage")
    same(F(441,400)/F(103,100)-1, F(29,412), "E1 changed price changes return")
    emz = eme = F(0)
    for u,v in product((-1,1),repeat=2):
        m = (1-F(u,5)+F(v,10))/F(21,20)
        emz += m*(2*u)/4; eme += m*F(v,50)/4
    same(-F(21,20)*emz, F(2,5), "E2 nontraded covariance risk price")
    same(F(3,100)*(-F(21,20)*emz)-F(21,20)*eme, F(1,100), "E2 priced residual contribution")
    same(F(3,1000)*4, F(3,100)*F(2,5), "E2 scale invariance")
    same(F(3,20)**2/100, F(9,40000), "E3 residual variance")
    near(0.2*math.sqrt(9/40000), 0.003, "E3 uniform bound")
    near(0.2*math.sqrt(9/8000), 0.00670820393249937, "E3 common residual bound")
    same(F(1,200)-F(3,20), F(-29,200), "E3 finite loss state")
    ystar = [v+F(3,500)+F(3,4)*z for v,z in zip(y,b)]
    residual_star = [v-(F(1,125)+F(5,4)*x+F(1,4)*z) for v,x,z in zip(ystar,a,b)]
    same(residual_star,residual,"E4 transformed full residuals")
    sststar = sum((v-sum(ystar)/8)**2 for v in ystar)
    same(sststar,F(129,20000),"E4 changed total variation")
    same(1-F(1,5000)/sststar,F(125,129),"E4 R-squared")
    same(F(5,4)+F(1,4)*ab/aa,F(11,8),"E4 short slope")
    same(F(1,125)+F(1,4)*(bm-F(1,2)*am),F(21,2000),"E4 short intercept")
    for intercept,slope,third in [(F(-3,1000),F(1),F(0)),(F(7,1000),F(-1,2),F(1,2))]:
        fit_values = [intercept+slope*x+third*(3*x-F(1,50)) for x in a]
        same(sum((v-p)**2 for v,p in zip(y,fit_values)),F(1,1000),"E5 alternative unidentified triple")
    new_lambdas = [F(27,2125),F(31,1700)]
    new_means = [F(9,500),F(1,50),F(7,250),F(3,500)]
    new_residuals = [v-row[0]*new_lambdas[0]-row[1]*new_lambdas[1] for row,v in zip(betas,new_means)]
    same([x-y for x,y in zip(new_lambdas,lambdas)],[F(3,4250),F(1,4250)],"E6 sensitivity coefficients")
    same(new_residuals,[F(9,1700),F(3,1700),F(-1,340),F(-1,850)],"E6 pricing residuals")
    same([sum(row[j]*e for row,e in zip(betas,new_residuals)) for j in range(2)],[F(0),F(0)],"E6 normal equations")
    e7vol = abs(F(-100)-110)+abs(F(100)+105)
    same(e7vol,F(415),"E7 actual reversal volume")
    same(200*F(1,500)+e7vol*F(1,500)+198*F(1,500),F(813,500),"E7 total transaction cash")
    same(100+5+6-F(813,500)-F(1,5),F(54587,500),"E7 final liquidation cash")
    same(2*F(1,50)-F(3,100),F(1,100),"retention exact premium")
    same(F(3,2)-F(2,5)*F(1,2),F(13,10),"retention omitted slope")
    same(F(1,4)*F(3,50)/6,F(1,400),"retention uniform bound")
    groups.append("All seven determinate exercise reconstructions and numerical retention; open E8 evaluated by explicit prose rubric")

    edits = [(["pricing","kernel_sign_coefficients"],["1/2","1/2","0"]),
             (["pricing","factor_shock_scales"],["0","1/10"]),
             (["pricing","clone_quote"],"103/100"),
             (["pricing","priced_residual_scale"],"-1/25"),
             (["diversification","pricing_tilt"],"1"),
             (["diversification","asset_counts"],[0]),
             (["diversification","asset_counts"],[4,4]),
             (["empirical","observations",1,"period"],1),
             (["construction","observations",0,"signal_available"],1),
             (["construction","observations",0,"signals"],["1","1","2","3"]),
             (["construction","observations",0,"simple_returns"],["-1","0","0","0"]),
             (["construction","one_way_trading_cost"],"-1/1000"),
             (["construction","initial_collateral"],"1/1000"),
             (["conventions","trading"],"omit final liquidation"),
             (["conventions","factor_units"],"return on zero initial equity"),
             (["pricing","safe_gross"],1.02)]
    for path,value in edits:
        changed=deepcopy(data);target=changed
        for key in path[:-1]:
            target=target[key]
        target[path[-1]]=value
        rejects(lambda changed=changed:model.run(changed),str(path))
    changed=deepcopy(data)
    for row in changed["empirical"]["observations"]:
        row["factor_2"]=str(3*F(row["factor_1"])-F(1,50))
    rejects(lambda:model.run(changed),"collinear factor rank")
    changed=deepcopy(data);changed["empirical"]["cross_section_betas"]=[["1","1"]]*4
    rejects(lambda:model.run(changed),"cross-sectional rank")
    # A meaningful allowed cost edit changes final cash by exact traded volume.
    changed=deepcopy(data);changed["construction"]["one_way_trading_cost"]="1/500"
    dearer=model.run(changed)
    same(F(dearer["construction"]["final_cash"]),F(5429,50),"doubling proportional cost preserves targets and removes another1.01")
    changed=deepcopy(data);changed["pricing"]["priced_residual_scale"]="0"
    exact=model.run(changed)
    same(exact["pricing"]["priced_residual_alpha"],"0","zero residual exact-spanning boundary")
    groups.append("Eighteen meaningful domain rejections, rank failures and targeted allowed numerical edits")

    reference=json.loads((ASSETS/"v09-c06-output.json").read_text())
    equivalent(result,reference)
    manifest=json.loads((ASSETS/"v09-c06-manifest.json").read_text())
    expected_assets={"v09-c06-"+suffix for suffix in ("inputs.json","analysis.py","output.json","README.txt")}
    same({x["file"] for x in manifest["files"]},expected_assets,"exact manifest asset set")
    for item in manifest["files"]:
        payload=(ASSETS/item["file"]).read_bytes()
        same(len(payload),item["bytes"],"manifest bytes")
        same(hashlib.sha256(payload).hexdigest(),item["sha256"],"manifest hash")
    html=(ROOT/"content/chapters/v09-c06.html").read_text()
    doc=Structure();doc.feed(html)
    same(doc.stack,[],"balanced manuscript fragment")
    same(len(doc.ids),len(set(doc.ids)),"unique chapter anchors")
    same((doc.worked,doc.exercises,doc.solution_items),(4,8,8),"actual worked and solved package")
    for name in expected_assets|{"v09-c06-manifest.json"}:
        same(name in doc.hrefs,True,"flat offline route "+name)
    sources=json.loads((ROOT/"content/reviews/v09-c06-sources.json").read_text())
    canonical={x["id"]:x for x in json.loads((ROOT/"content/sources.json").read_text())}
    for source in sources:
        same("sources.html#"+source["id"] in doc.hrefs,True,"scoped source linked")
        if source["id"] in {"mit-linear-projection","v09-c04-fama-french-tests"}:
            same(source,canonical[source["id"]],"exact accepted-source reuse")
    groups.append("Complete preserved output, actual chapter structure, scoped source reuse and final asset integrity")

    with tempfile.TemporaryDirectory(prefix="ilex-offline-") as folder:
        target=Path(folder)
        for name in ("v09-c06-inputs.json","v09-c06-analysis.py"):
            shutil.copyfile(ASSETS/name,target/name)
        for optimized in (False,True):
            command=[sys.executable]+(["-O"] if optimized else [])+[str(target/"v09-c06-analysis.py")]
            if optimized:
                command.append(str(target/"v09-c06-inputs.json"))
            run=subprocess.run(command,cwd=ROOT.parent,capture_output=True,text=True,check=True)
            same(run.stderr,"","isolated CLI stderr")
            equivalent(json.loads(run.stdout),reference,"portable CLI")
    groups.append("Isolated standard-library offline execution under normal and optimized Python")
    return {"chapter":"v09-c06","status":"passed","groups":len(groups),"comparisons":comparisons,
            "domain_rejections":rejections,"checks":[{"name":name,"status":"passed"} for name in groups],
            "limitations":"Includes numerical, reference, structural and portable-execution comparisons; not separate proofs for every count. Synthetic cases do not establish empirical premiums, investor skill or visual/print quality."}


if __name__=="__main__":
    print(json.dumps(check(),indent=2,allow_nan=False))
