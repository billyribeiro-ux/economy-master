"""Independent financial and instructional checks for the Serein return lab."""
from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
from fractions import Fraction as F
from html.parser import HTMLParser
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
        self.examples = self.exercises = self.solution_items = 0
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
        self.examples += "worked" in classes
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
    groups = []

    def same(actual, expected, label):
        nonlocal comparisons
        comparisons += 1
        if actual != expected:
            raise AssertionError(f"{label}: {actual!r} != {expected!r}")

    def near(actual, expected, label):
        nonlocal comparisons
        comparisons += 1
        if not math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12):
            raise AssertionError(f"{label}: {actual!r} != {expected!r}")

    def equivalent(actual, expected, path="output"):
        if isinstance(expected, float):
            near(actual, expected, path)
        elif isinstance(expected, dict):
            same(set(actual), set(expected), path + " fields")
            for key in expected:
                equivalent(actual[key], expected[key], path + "/" + key)
        elif isinstance(expected, list):
            same(len(actual), len(expected), path + " length")
            for i, item in enumerate(expected):
                equivalent(actual[i], item, path + "/" + str(i))
        else:
            same(actual, expected, path)

    def rejects(call, label):
        try:
            call()
        except ValueError:
            return
        raise AssertionError("Missing domain rejection: " + label)

    buffer = io.StringIO()
    with redirect_stdout(buffer), redirect_stderr(buffer):
        spec = importlib.util.spec_from_file_location("serein", ASSETS / "v09-c01-analysis.py")
        model = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(model)
        data = json.loads((ASSETS / "v09-c01-inputs.json").read_text())
        result = model.run(data)
    same(buffer.getvalue(), "", "quiet import and run")
    json.dumps(result, allow_nan=False)

    # Direct share and cash reconstruction, separate from the code's linked factors.
    shares1 = F(1) + F(6, 78)
    terminal_receipt = shares1 * 84 + shares1 * 3
    d = result["dividends"]
    same(shares1, F(d["rows"][0]["reinvested_shares_after_distribution"]), "actual first dividend purchases")
    same(terminal_receipt, F(d["rows"][1]["reinvested_wealth"]), "separate capital and income receipts")
    same(terminal_receipt / 80 - 1, F(89, 520), "direct cumulative wealth anchor")
    same(F(d["reinvested_cumulative_return"]), F(89, 520), "linked wealth matches holdings")
    same((F(84) + 6 + 3) / 80 - 1, F(d["retained_cash_cumulative_return"]), "fixed-share cash strategy")
    same(F(d["price_return"]), F(1, 20), "price-only perimeter")
    near(sum(row["log_total_return"] for row in d["rows"]), math.log(float(F(609, 520))), "additive log path")
    near((1+d["reinvested_annualized_return"])**2, float(F(609, 520)), "annualized rate reproduces wealth")
    same(model.log_return(F(0)), None, "total loss has no finite log")
    same(model.annualized(F(0), 2), -1.0, "zero endpoint equivalent simple return")
    groups.append("Distribution-share reconciliation, cash alternatives and log/annualization domains")

    f = result["cash_flow_account"]
    same(F(f["twr_cumulative"]), F(2, 25), "unitized manager return")
    same(F(f["investor_net_cash_gain"]), F(-10), "investor net receipts")
    same(F(f["modified_dietz_cumulative"]), F(-1, 19), "dated capital approximation")
    annual = f["money_weighted_annual_return"]
    # Independent discounted-cash equation and bisection, not the quadratic code.
    npv = lambda r: -100 - 180/(1+r) + 270/(1+r)**2
    near(npv(annual), 0, "IRR original investor cash equation")
    low, high = -0.5, 0.5
    for _ in range(90):
        mid = (low + high) / 2
        # Equivalent terminal receipts minus required accumulation is decreasing.
        if 270 - 100*(1+mid)**2 - 180*(1+mid) > 0:
            low = mid
        else:
            high = mid
    near(annual, (low+high)/2, "independent bracket root")
    changed = deepcopy(data["account"])
    changed["before_contribution"] = "90"
    alternate = model.flow_account(changed)
    same(alternate["twr_cumulative"], F(-1, 10), "unknown valuation allows another true TWR")
    near(alternate["money_weighted_annual_return"], annual, "fixed investor flows leave IRR unchanged")
    changed["contribution"] = "0"
    zero = model.flow_account(changed)
    near(zero["money_weighted_annual_return"], math.sqrt(2.7)-1, "zero-flow endpoint boundary")
    groups.append("Flow-adjusted unit growth, discounted investor equation, root and identification counterexample")

    # Independent charges entered as cash amounts, not only compounded fee factors.
    balance = F(990)
    anchors = [(F(5544, 5), F(1386, 125), F(137214, 125)),
               (F(1303533, 1250), F(1303533, 125000), F(129049767, 125000))]
    for row, (market, charge, close) in zip(result["fees"]["rows"], anchors):
        same(F(row["opening_invested_assets"]), balance, "fee opening balance")
        same(F(row["before_management_fee"]), market, "gross assets")
        same(F(row["management_fee"]), charge, "actual fee amount")
        same(F(row["closing_assets"]), market-charge, "fee cash reconciles closing assets")
        same(F(row["closing_assets"]), close, "closing balance anchor")
        balance = close
    receipt = balance - balance/200
    same(F(result["fees"]["final_investor_receipt"]), receipt, "final redemption cash")
    same(receipt/1000-1, F(680903633, 25000000000), "all-cost investor return")
    same(F(result["fees"]["after_management_before_loads_cumulative_return"]), F(53533, 1250000), "different fee perimeter")
    # One home unit buys 4/5 foreign units; ending foreign holdings convert at19/16.
    home_cash = F(4, 5) * F(27, 25) * F(19, 16)
    same(home_cash-1, F(result["currency"]["home_nominal_return"]), "actual currency units cancel")
    same(home_cash/F(26, 25)-1, F(-7, 520), "real purchasing-power anchor")
    same(F(result["currency"]["home_real_return"]), F(-7, 520), "model real return")
    near(result["currency"]["home_real_log_return"], math.log(float(F(513, 520))), "log of real wealth")
    groups.append("Independent fee cash ledger and currency/purchasing-power unit conversion")

    o = result["opportunity"]
    # Invest100: selected holdings .6 units of A and .4 units of B priced100.
    payoffs_a, payoffs_b = [80, 110, 130], [112, 104, 96]
    selected = [(F(3, 5)*a + F(2, 5)*b)/100-1 for a,b in zip(payoffs_a,payoffs_b)]
    same(selected, [F(x) for x in o["selected_state_returns"]], "quantity-based state returns")
    same(sum(p*r for p,r in zip([F(1,4),F(1,2),F(1,4)],selected)), F(61,1000), "physical mean")
    same(o["selected_meets_floor"], False, "mean does not erase a state violation")
    same([F(x) for x in o["feasible_weight_a_interval"]], [F(0),F(17,32)], "all original inequalities")
    same([F(x) for x in o["highest_mean_feasible_state_returns"]], [F(-1,20),F(23,320),F(9,64)], "feasible boundary cash")
    same(F(o["highest_mean_feasible_expected_return"]), F(15,256), "boundary mean")
    tightened = deepcopy(data["opportunity"])
    tightened["minimum_state_return"] = "-1/50"
    tighter = model.opportunity(tightened)
    same(tighter["feasible_weight_a_interval"], [F(1,17),F(7,16)], "new floor activates both endpoints")
    same(tighter["highest_mean_feasible_state_returns"], [F(-1,50),F(53,800),F(87,800)], "tightened actual states")
    same(tighter["highest_mean_feasible_expected_return"], F(177,3200), "tightened mean")
    for weight in (F(1,17)-F(1,10000), F(7,16)+F(1,10000)):
        returns = [weight*F(a,100)+(1-weight)*F(b,100)-1 for a,b in zip(payoffs_a,payoffs_b)]
        same(min(returns) < F(-1,50), True, "each side of feasible interval matters")
    groups.append("State payoffs, physical means and two-sided mandate boundaries")

    r = result["rebalancing"]
    same(F(r["buy_and_hold"]["rows"][1]["wealth"]), F(70)*F(3,4)+45*F(6,5), "unchanged quantity strategy")
    same(F(r["constant_weights"]["rows"][1]["wealth"]), F(115,2)*(F(3,4)+F(6,5)), "self-financing target reset")
    same([F(x) for x in r["buy_and_hold"]["rows"][1]["beginning_weights"]], [F(14,23),F(9,23)], "wealth-drift weights")
    same(F(r["buy_and_hold"]["cumulative_return"]), F(13,200), "buy-and-hold cumulative")
    same(F(r["constant_weights"]["cumulative_return"]), F(97,800), "rebalanced cumulative")
    same(math.isclose(math.log(1.15), 0.5*math.log(1.4)+0.5*math.log(0.9)), False, "portfolio logs do not weight linearly")
    groups.append("Beginning-weight budget identity and distinct self-financing strategies")

    # All eight exercise solutions and retention anchors, outside the lab fixture.
    same(F(13,12)*56, F(182,3), "E1 holdings")
    same(F(182,3)/50-1, F(16,75), "E1 wealth return")
    same(F(13,10)*F(7,10), F(91,100), "E2 realized growth")
    same(sum([F(169,100),F(91,100),F(91,100),F(49,100)])/4, F(1), "E2 independent expected wealth")
    same(F(7,10)*(1+F(3,7)), F(1), "E2 loss recovery")
    e3x = (math.sqrt(3265)-15)/40
    near(-120-90/e3x+228/e3x**2, 0, "E3 exact root expression")
    same(F(150,120)*F(228,240), F(19,16), "E3 unitized growth")
    same(F(18,165), F(6,55), "E3 Dietz capital")
    for x in (F(11,10), F(7,5)):
        same(-100+250/x-154/x**2, F(0), "E4 both roots")
    same(-100+250/F(6,5)-154/F(6,5)**2, F(25,18), "E4 NPV uses capital call")
    same(F(23,20)*F(49,50)*F(23,25)/F(103,100)-1, F(171,25750), "E5 fee/FX/inflation")
    same(F(125)*F(4,5)+100*F(11,10), F(210), "E6 hold")
    same(F(225,2)*(F(4,5)+F(11,10)), F(855,4), "E6 rebalance")
    same(F(125)*F(6,5)+100*F(11,10), F(260), "E6 winner continuation hold")
    same(F(225,2)*(F(6,5)+F(11,10)), F(1035,4), "E6 reversed strategy ranking")
    same(112+4-F(4,4)-F(12,5), F(563,5), "E7 tax bases")
    near(math.log(float(F(563,500))), 0.11867152971749854, "E7 log wealth")
    same((F(303)+12)/300-1, F(1,20), "retention total income")
    same(F(210,200)*F(310,310)-1, F(1,20), "retention flow split")
    same(F(106,104)-1, F(1,52), "retention relative wealth")
    groups.append("Every determinate exercise and retention result; E8 independently covered by tightened-state checks")

    edits = [(["account","dates"],[0,0.5,2]), (["account","contribution"],"-180"),
             (["account","terminal_liquidation"],"0"), (["dividends","opening_price"],"0"),
             (["fees","post_return_management_fraction"],"1"), (["foreign","opening_home_per_foreign"],"0"),
             (["foreign","home_inflation"],"-1"), (["opportunity","probabilities"],["1/4","1/4","1/4"]),
             (["opportunity","selected_weight_a"],"11/10"), (["opportunity","minimum_state_return"],"1/5"),
             (["conventions","fees"],"charge on opening assets instead"),
             (["conventions","fx"],"foreign per home"), (["rebalancing","initial_weights"],["1/2","1/4"])]
    for path,value in edits:
        changed = deepcopy(data)
        target = changed
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value
        rejects(lambda changed=changed: model.run(changed), "/".join(path))
    rejects(lambda: model.log_return(F(-1)), "negative wealth log")
    rejects(lambda: model.q(0.1), "binary float input")
    groups.append("Fifteen meaningful timing, capital, mandate, convention and numerical-domain rejections")

    reference = json.loads((ASSETS / "v09-c01-output.json").read_text())
    equivalent(result, reference)
    manifest = json.loads((ASSETS / "v09-c01-manifest.json").read_text())
    expected_files = {f"v09-c01-{suffix}" for suffix in ("inputs.json","analysis.py","output.json","README.txt")}
    same({x["file"] for x in manifest["files"]}, expected_files, "exact manifest asset set")
    for item in manifest["files"]:
        payload = (ASSETS / item["file"]).read_bytes()
        same(len(payload), item["bytes"], "manifest bytes")
        same(hashlib.sha256(payload).hexdigest(), item["sha256"], "manifest hash")
    html = (ROOT / "content/chapters/v09-c01.html").read_text()
    doc = Structure(); doc.feed(html)
    same(doc.stack, [], "balanced full fragment")
    same(len(doc.ids), len(set(doc.ids)), "unique chapter anchors")
    same((doc.examples,doc.exercises,doc.solution_items), (4,8,8), "actual worked and solved packages")
    for name in expected_files | {"v09-c01-manifest.json"}:
        same(name in doc.hrefs, True, "download route " + name)
    for source in json.loads((ROOT / "content/reviews/v09-c01-sources.json").read_text()):
        same("sources.html#"+source["id"] in doc.hrefs, True, "scoped source citation")
    with tempfile.TemporaryDirectory(prefix="serein-offline-") as folder:
        target = Path(folder)
        for name in ("v09-c01-inputs.json","v09-c01-analysis.py"):
            shutil.copyfile(ASSETS/name,target/name)
        for optimized in (False, True):
            command = [sys.executable] + (["-O"] if optimized else []) + [str(target/"v09-c01-analysis.py")]
            if optimized:
                command.append(str(target/"v09-c01-inputs.json"))
            run = subprocess.run(command,cwd=ROOT.parent,capture_output=True,text=True,check=True)
            same(run.stderr,"","portable CLI stderr")
            equivalent(json.loads(run.stdout),reference,"portable CLI")
    groups.append("Complete preserved output, final manifest, chapter structure and isolated normal/optimized offline CLI")
    return {"chapter":"v09-c01","status":"passed","groups":len(groups),"comparisons":comparisons,
            "checks":[{"name":name,"status":"passed"} for name in groups],
            "limitations":"Synthetic economic and numerical review; not authenticated market data, standards compliance, learner mastery or visual UI verification."}


if __name__ == "__main__":
    print(json.dumps(check(),indent=2,allow_nan=False))
