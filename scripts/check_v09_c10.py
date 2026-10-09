"""Quiet independent reconstruction of Rowan alternatives and their boundaries."""
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
        self.worked = self.exercises = self.solutions = self.h1 = 0
        self.exercise_mode = self.solution_mode = False

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
        self.h1 += tag == "h1"
        if tag == "ol" and "exercises" in classes:
            self.exercise_mode = True
        if tag == "details" and "solutions" in classes:
            self.solution_mode = True
        if tag == "li":
            self.exercises += self.exercise_mode
            self.solutions += self.solution_mode

    def handle_endtag(self, tag):
        if not self.stack or self.stack.pop() != tag:
            raise AssertionError("invalid HTML fragment nesting: " + tag)
        if tag == "ol":
            self.exercise_mode = False
        if tag == "details":
            self.solution_mode = False


def check():
    comparisons = rejections = 0
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

    def rejects(call, label):
        nonlocal rejections
        try:
            call()
        except ValueError:
            rejections += 1
            return
        raise AssertionError("missing domain rejection: " + label)

    def equivalent(actual, expected, path="output"):
        if isinstance(expected, float):
            near(actual, expected, path)
        elif isinstance(expected, dict):
            same(set(actual), set(expected), path + " keys")
            for key in expected:
                equivalent(actual[key], expected[key], path + "/" + key)
        elif isinstance(expected, list):
            same(len(actual), len(expected), path + " length")
            for i, value in enumerate(expected):
                equivalent(actual[i], value, path + "/" + str(i))
        else:
            same(actual, expected, path)

    def qvec(values):
        return [F(v) for v in values]

    def zero_npv(cash, rate, label):
        near(sum(float(c)/(1+rate)**t for t, c in enumerate(cash)), 0, label)

    # Independent Newton solution in discount-factor coordinates, not the
    # analysis module's bracketing of a terminal-value polynomial in gross rate.
    def discount_root(cash):
        d = 0.9
        for _ in range(30):
            value = sum(float(c)*d**t for t, c in enumerate(cash))
            derivative = sum(t*float(c)*d**(t-1) for t, c in enumerate(cash) if t)
            updated = d-value/derivative
            if abs(updated-d) < 1e-15:
                d = updated
                break
            d = updated
        if d <= 0:
            raise AssertionError("unexpected exercise root domain")
        return 1/d-1

    quiet = io.StringIO()
    bytecode = sys.dont_write_bytecode
    try:
        sys.dont_write_bytecode = True
        with redirect_stdout(quiet), redirect_stderr(quiet):
            spec = importlib.util.spec_from_file_location("rowan_alternatives", ASSETS / "v09-c10-analysis.py")
            model = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(model)
            data = model.load(ASSETS / "v09-c10-inputs.json")
            untouched = deepcopy(data)
            result = model.run(data)
    finally:
        sys.dont_write_bytecode = bytecode
    same(quiet.getvalue(), "", "quiet import and run")
    same(data, untouched, "run does not mutate inputs")
    json.dumps(result, allow_nan=False)

    # Property: dated cash is reconstructed from initial financing and cumulative
    # principal, then discounted separately from the model's forward recurrence.
    prop = result["property"]
    principal = [F(20), F(20), F(560)]
    lender = [F(-600)]
    for t, row in enumerate(prop["operations"]):
        opening = 600-sum(principal[:t])
        interest = opening*F(3, 50)
        same(F(row["opening_debt"]), opening, "property opening debt")
        same(F(row["interest"]), interest, "property interest")
        same(F(row["principal"]), principal[t], "property principal")
        same(F(row["closing_debt"]), 600-sum(principal[:t+1]), "property closing debt")
        same(F(row["operating_cash"]), [78,84,90][t], "NOI less capex")
        lender.append(interest+principal[t])
    same(qvec(prop["lender_cash"]), lender, "whole lender cash")
    same(sum(v/F(53,50)**t for t,v in enumerate(lender)), F(0), "par financing at its contract rate")
    for key, forward, cap, equity_last, npv in [
        ("base", F(105), F(7,100), F(4757,5), F(374160,1331)),
        ("stress", F(84), F(1,10), F(1556,5), F(-266040,1331))]:
        out = prop[key]
        sale = forward/cap
        net = sale*F(97,100)
        asset = [F(-1020),F(78),F(84),90+net]
        equity = [a-d for a,d in zip(asset,lender)]
        same(F(out["gross_sale"]), sale, key+" gross sale")
        same(F(out["net_sale"]), net, key+" net sale")
        same(qvec(out["asset_cash"]), asset, key+" asset cash")
        same(qvec(out["equity_cash"]), equity, key+" residual equity cash")
        same(equity[-1], equity_last, key+" independent exit anchor")
        same(sum(v/F(11,10)**t for t,v in enumerate(asset)), npv, key+" independent NPV")
        same(F(out["asset_npv_at_supplied_rate"]), npv, key+" reported NPV")
        for i in range(4):
            same(asset[i], lender[i]+equity[i], key+" dated claim conservation")
        near(out["asset_irr"], discount_root(asset), key+" independent asset IRR")
        near(out["equity_irr"], discount_root(equity), key+" independent equity IRR")
        zero_npv(asset,out["asset_irr"],key+" asset zero NPV")
        zero_npv(equity,out["equity_irr"],key+" equity zero NPV")
    near(prop["lender_irr"], .06, "fully paid debt IRR")
    groups.append("Property financing, dated claim conservation, direct discounting and independent IRR roots")

    # Smoothing: dot products of filter weights plus an exact geometric tail,
    # and a full covariance matrix for the return sum, independently of the
    # analysis's scalar closed form. Finite path uses direct convolution.
    s = result["smoothing"]["population"]
    theta, latent_variance = F(3,5), F(1,25)
    weights = [(1-theta)*theta**j for j in range(40)]
    variance = latent_variance*(sum(w*w for w in weights)+(1-theta)**2*theta**80/(1-theta**2))
    same(variance,F(1,100),"infinite-filter variance anchor")
    same(F(s["reported_variance"]),variance,"reported filter variance")
    covariance = weights[0]*F(3,200)
    same(F(s["reported_market_covariance"]),covariance,"current market covariance weight")
    same(F(s["latent_market_covariance"]),F(3,200),"latent market covariance")
    same(F(s["latent_beta"]),F(2,3),"latent beta")
    same(F(s["reported_beta"]),F(4,15),"reported beta")
    same(F(s["lag_one_correlation"]),theta,"stationary lag-one correlation")
    near(s["reported_market_correlation"],.4,"reported correlation")
    near(s["reported_sigma"],.1,"reported standard deviation")
    same(F(s["latent_sharpe"]),F(3,10),"latent same-horizon Sharpe")
    near(s["reported_sharpe"],.6,"reported same-horizon Sharpe")
    sum_variance = sum(variance*theta**abs(i-j) for i in range(4) for j in range(4))
    same(sum_variance,F(296,3125),"full four-by-four covariance sum")
    same(F(s["variance_of_sum"]),sum_variance,"reported return-sum variance")
    same(variance*(1+2*theta/(1-theta)),latent_variance,"long-run covariance sum")
    path = result["smoothing"]["finite_path"]
    true = [F(-1,5),F(1,5),F(-1,10),F(3,10)]
    reports = []
    latent_wealth = report_wealth = F(1)
    for t in range(1,5):
        report = theta**t*F(2,25)+(1-theta)*sum(theta**(t-j)*true[j-1] for j in range(1,t+1))
        reports.append(report)
        latent_wealth *= 1+true[t-1]
        report_wealth *= 1+report
        same(F(path["wealth_indices"][t-1]["latent_index"]),latent_wealth,"finite latent wealth")
        same(F(path["wealth_indices"][t-1]["appraisal_index"]),report_wealth,"finite reported wealth")
    same(qvec(path["reported_returns"]),reports,"independent direct filter convolution")
    same(qvec(path["unsmoothed_returns"]),true,"inverse recovers all latent observations")
    same(latent_wealth,F(702,625),"compound latent endpoint")
    same(report_wealth,F(4363508509074,3814697265625),"compound reported endpoint")
    groups.append("Filter-weight variance/covariance, additive horizon risk, direct convolution and wealth compounding")

    private = result["private"]
    calls, distributions = [F(40),F(32),F(22),F(2)], [F(0),F(8),F(12),F(110)]
    net = [d-c for d,c in zip(distributions,calls)]
    same(qvec(private["lp_contributions"]),calls,"all-purpose LP paid-in cash")
    same(qvec(private["lp_net_distributions"]),distributions,"LP distribution perimeter")
    same(qvec(private["lp_net_cash"]),net,"actual net investor cash")
    same(F(private["carry_paid_at_3"]),F(10),"terminal gross-base carry")
    same(F(private["gp_management_plus_carry"]),F(16),"all GP cash")
    same(sum(calls)-6,F(90),"contributions allocated to fees and investments")
    same(sum(distributions)+10,F(140),"realizations allocated to LP and carry")
    same(F(private["gross_investment_multiple"]),F(14,9),"gross investment multiple")
    same(F(private["lp_net_tvpi"]),F(65,48),"actual LP TVPI")
    same(F(private["lp_net_dpi"])+F(private["lp_rvpi"]),F(65,48),"DPI plus RVPI")
    same(F(private["unused_commitment_released_at_3"]),F(10),"no unreported continuing commitment")
    near(private["lp_net_irr"],discount_root(net),"private independent discount-factor IRR")
    zero_npv(net,private["lp_net_irr"],"private zero NPV")
    # Forward each leg's running benchmark account instead of terminal weights.
    call_account, distribution_account = calls[0], distributions[0]
    for gross,c,d in zip([F(11,10),F(21,20),F(19,20)],calls[1:],distributions[1:]):
        call_account=call_account*gross+c
        distribution_account=distribution_account*gross+d
    bench=private["benchmark"]
    same(call_account,F(9871,100),"forward benchmark contribution account")
    same(distribution_account,F(6469,50),"forward benchmark distribution account")
    same(F(bench["fv_contributions"]),call_account,"reported benchmark contributions")
    same(F(bench["fv_net_distributions"]),distribution_account,"reported benchmark distributions")
    same(F(bench["cash_flow_matched_ratio"]),F(12938,9871),"dated cash relative ratio")
    same(F(bench["terminal_relative_excess"]),F(3067,100),"dated benchmark surplus")
    groups.append("Fund-versus-investor fee waterfall, multiples, independent net IRR and forward benchmark cash legs")

    # Reconstruct all deadline balances by cumulative dated events, rather than
    # carrying the model's previous closing-balance state through its recursion.
    def audit_liquidity(out, initial, dist, spending):
        for t,row in enumerate(out["ledger"]):
            before=initial+5*t-sum(spending[:t])-sum(calls[:t+1])+sum(dist[:t])
            same(F(row["before_distribution"]),before,"cumulative cash at call deadline")
            same(F(row["after_distribution"]),before+dist[t],"cash after delayed distribution")
        minimum=min(F(row["before_distribution"]) for row in out["ledger"])
        same(F(out["minimum_cash"]),minimum,"worst actual payment deadline")
        same(F(out["additional_initial_reserve_needed"]),max(F(0),-minimum),"prefix-deficit reserve requirement")
    audit_liquidity(private["liquidity_base"],F(90),distributions,[F(6)]*3)
    delayed=[F(0),F(0),F(12),F(118)]
    audit_liquidity(private["liquidity_delayed"],F(90),delayed,[F(6)]*3)
    repair=private["repair_by_reducing_initial_gated_allocation"]
    audit_liquidity(repair["ledger"],F(96),delayed,[F(6)]*3)
    same(private["liquidity_base"]["feasible"],True,"baseline funded")
    same(private["liquidity_delayed"]["feasible"],False,"delay fails before receipt")
    same(private["liquidity_delayed"]["terminal_cash"],None,"unfunded path has no implemented terminal cash")
    same(F(private["liquidity_delayed"]["unfunded_diagnostic_terminal_balance"]),F(121),"counterfactual diagnostic is labeled")
    same(F(repair["gated_allocation_after"]),F(19),"repair is financed by initial allocation reduction")
    same(F(repair["ledger"]["terminal_cash"]),F(127),"funded repair endpoint")
    same(F(repair["ledger"]["initial_cash"])+F(repair["gated_allocation_after"]),F(115),"initial total budget conserved")
    near(private["delayed_lp_irr_if_funded"],discount_root([-40,-32,-10,116]),"timing lowers conditional investor IRR")
    groups.append("Independent cumulative deadline test, unfunded status and fully financed reserve repair")

    futures=result["futures"]
    expected=[(1000,10,-20,10,980,0,980,1000),(980,F(49,5),-10,F(49,5),970,0,970,1000),(970,F(97,10),80,F(97,10),1050,10,1040,1040)]
    names=["opening_cash","interest","variation_cash","management_fee","pre_performance_cash","performance_fee","ending_cash","ending_high_water"]
    for row,values in zip(futures["ledger"],expected):
        for name,value in zip(names,values):
            same(F(row[name]),F(value),"independent futures cash anchor "+name)
        same(F(row["opening_cash"])+F(row["interest"])+F(row["variation_cash"])-F(row["management_fee"])-F(row["performance_fee"]),F(row["ending_cash"]),"fund cash ownership")
        same(F(row["free_cash_above_margin"]),F(row["ending_cash"])-200,"margin is a cash subset")
    # Full-maturity payoff accounting: near closing P&L plus deferred closing P&L.
    same(F(futures["total_variation_cash_through_observed_rows"]),10*((98-100)+(112-105)),"contract-by-contract full payoff")
    same(F(futures["new_contract_initial_cash_price"]),F(0),"no notional purchase payment")
    same(F(futures["new_contract_notional_at_roll"]),F(1050),"new notional exposure")
    same(F(futures["net_total_return"]),F(1,25),"net fund total return")
    same(F(futures["spot_total_return"]),F(3,25),"separate spot price return")
    same(F(futures["stress_first_period"]["ending_cash"]),F(150),"positive NAV stress")
    same(F(futures["stress_first_period"]["margin_shortfall"]),F(50),"positive NAV still fails margin")
    same(futures["stress_first_period"]["feasible"],False,"no implicit margin loan")
    groups.append("Independent contract payoffs, full fee/NAV closure, roll accounting and margin constraint")

    # Every determinate exercise, including transfers not embedded in the model.
    edited=deepcopy(data);edited["property"]["exit_cap_rate"]="0.084"
    e1=model.run(edited)["property"]["base"]
    same(F(e1["gross_sale"]),F(1250),"E1 gross exit")
    same(F(e1["net_sale"]),F(2425,2),"E1 net exit")
    same(F(e1["asset_cash"][-1]),F(2605,2),"E1 terminal asset")
    same(F(e1["equity_cash"][-1]),F(7089,10),"E1 terminal equity")
    same(F(e1["asset_npv_at_supplied_rate"]),F(131660,1331),"E1 NPV")
    near(e1["equity_irr"],discount_root([-420,22,F(146,5),F(7089,10)]),"E1 independent IRR")
    observed_var=F(12,100)**2
    true_var=observed_var*3
    same(true_var,F(27,625),"E2 corrected variance")
    near(math.sqrt(float(true_var)),.12*math.sqrt(3),"E2 latent volatility")
    same(F(2,5)/F(1,2),F(4,5),"E2 corrected beta")
    same(2*observed_var+2*F(1,2)*observed_var,F(27,625),"E2 dependent sum variance")
    same(2*observed_var,F(18,625),"E2 naive sum variance")
    observed=[F(4,100),F(1,100),F(5,100),F(-2,100)]
    recovered=[2*observed[t]-observed[t-1] for t in range(1,4)]
    same(recovered,[F(-2,100),F(9,100),F(-9,100)],"E3 latent returns")
    same(math.prod(1+x for x in recovered),F(486031,500000),"E3 latent compound wealth")
    same(math.prod(1+x for x in observed[1:]),F(103929,100000),"E3 reported compound wealth")
    edited=deepcopy(data);edited["private"]["gross_distributions"][-1]="100"
    e4=model.run(edited)["private"]
    for key,value in [("carry_paid_at_3",6),("gross_investment_multiple",F(4,3)),("lp_net_tvpi",F(19,16))]:
        same(F(e4[key]),F(value),"E4 "+key)
    same(qvec(e4["lp_net_cash"]),qvec([-40,-24,-10,92]),"E4 net cash")
    near(e4["lp_net_irr"],discount_root([-40,-24,-10,92]),"E4 net IRR")
    same(F(e4["benchmark"]["cash_flow_matched_ratio"]),F(11338,9871),"E4 benchmark ratio")
    same(F(e4["benchmark"]["terminal_relative_excess"]),F(1467,100),"E4 benchmark surplus")
    edited=deepcopy(data);edited["liquidity"]["spending"][0]="8"
    e5=model.run(edited)["private"]
    same(F(e5["liquidity_delayed"]["minimum_cash"]),F(-8),"E5 failed deadline")
    r5=e5["repair_by_reducing_initial_gated_allocation"]
    same(F(r5["gated_allocation_after"]),F(17),"E5 funded initial reduction")
    same(F(r5["ledger"]["initial_cash"]),F(98),"E5 minimum reserve")
    same([F(x["before_distribution"]) for x in r5["ledger"]["ledger"]],qvec([58,23,0,9]),"E5 all repaired deadlines")
    same(F(r5["ledger"]["terminal_cash"]),F(127),"E5 final cash")
    probabilities=[F(9,10),F(1,10)];asset=[F(150),F(60)]
    debt=[min(F(108),x) for x in asset];equity=[max(F(0),x-108) for x in asset]
    same(debt,qvec([108,60]),"E6 senior state cash")
    same(equity,qvec([42,0]),"E6 residual state cash")
    expected_debt=sum(p*x for p,x in zip(probabilities,debt))
    expected_equity=sum(p*x for p,x in zip(probabilities,equity))
    same(expected_debt/100-1,F(4,125),"E6 expected debt return")
    same(expected_equity/40-1,F(-11,200),"E6 expected equity return")
    same(expected_debt+expected_equity,F(141),"E6 total expected cash")
    same((expected_debt+expected_equity)/140-1,F(1,140),"E6 firm expected return")
    for x,d,e in zip(asset,debt,equity):
        same(x,d+e,"E6 state-by-state priority conservation")
    edited=deepcopy(data)
    edited["futures"].update(initial_cash="500",units="5",near_entry="50",near_settlement="46",deferred_entry="48",deferred_marks=["50","58"],management_rate="0.02",margin_reserve="100")
    e7=model.run(edited)["futures"]
    transfer=[(F(5),F(-20),F(10),F(0),F(475)),(F(19,4),F(10),F(19,2),F(0),F(1921,4)),(F(1921,400),F(40),F(1921,200),F(6179,2000),F(256179,500))]
    for row,values in zip(e7["ledger"],transfer):
        for key,value in zip(["interest","variation_cash","management_fee","performance_fee","ending_cash"],values):
            same(F(row[key]),value,"E7 unequal rate transfer "+key)
    same(F(e7["net_total_return"]),F(6179,250000),"E7 actual net total return")
    same(e7["feasible"],True,"E7 all margins funded")
    same(F(1500)-F(1250),F(250),"retention exact property change")
    same(F(250,1500),F(1,6),"retention exact percent decrease")
    groups.append("All seven determinate exercises and numerical retention; E8 reviewed by explicit reasoning rubric")

    # Economically meaningful permitted interventions and constraint boundaries.
    edited=deepcopy(data);edited["smoothing"]["theta"]="0"
    no_smoothing=model.run(edited)["smoothing"]
    same(no_smoothing["finite_path"]["reported_returns"],no_smoothing["finite_path"]["latent_returns"],"theta zero identity")
    same(no_smoothing["population"]["reported_variance"],"1/25","theta zero variance")
    edited=deepcopy(data);edited["private"]["delay_first_distribution"]="0"
    no_delay=model.run(edited)["private"]
    equivalent(no_delay["liquidity_delayed"],no_delay["liquidity_base"],"zero-delay identity")
    edited=deepcopy(data);edited["liquidity"]["gated_nav"]="5"
    insufficient=model.run(edited)["private"]["repair_by_reducing_initial_gated_allocation"]
    same(insufficient["feasible"],False,"reserve repair cannot exceed available initial allocation")
    same(insufficient["ledger"],None,"no invented funding after failed repair")
    edited=deepcopy(data);edited["futures"]["near_settlement"]="15"
    stopped=model.run(edited)["futures"]
    same(stopped["feasible"],False,"main strategy stops on margin breach")
    same(stopped["terminal_cash"],None,"no terminal wealth after unfunded margin breach")
    same(stopped["completed_periods"],0,"breach at first margin test")
    same(len(stopped["ledger"]),1,"no future strategy execution after first breach")
    edited=deepcopy(data);edited["futures"]["margin_reserve"]="970"
    boundary=model.run(edited)["futures"]
    same(boundary["feasible"],True,"exact margin equality feasible")
    same(boundary["ledger"][1]["free_cash_above_margin"],"0","binding margin boundary")
    edited["futures"]["margin_reserve"]="971"
    above=model.run(edited)["futures"]
    same(above["completed_periods"],1,"one extra margin CU stops second period")
    same(above["ledger"][-1]["margin_shortfall"],"1","margin deficit exact")
    edited=deepcopy(data);edited["futures"]["deferred_marks"]=["105","107"]
    at_high_water=model.run(edited)["futures"]
    same(at_high_water["terminal_cash"],"1000","cash exactly recovers old high water")
    same(at_high_water["total_performance_through_observed_rows"],"0","no performance fee at old high water equality")
    edited=deepcopy(data);edited["futures"]["management_rate"]="0.02"
    dearer=model.run(edited)["futures"]
    cash,peak=F(1000),F(1000)
    for pnl in [-20,-10,80]:
        before=cash*F(99,100)+pnl
        fee=max(F(0),before-peak)/5
        cash=before-fee;peak=max(peak,cash)
    same(F(dearer["terminal_cash"]),cash,"management fee is not assumed to cancel yield")
    edited=deepcopy(data);edited["property"].update(loan="0",principal_payments=["0","0","0"])
    unlevered=model.run(edited)["property"]
    same(unlevered["lender_irr"],None,"zero debt has no IRR")
    same(unlevered["base"]["asset_cash"],unlevered["base"]["equity_cash"],"zero debt aligns asset and equity")
    edits=[
        (["conventions","liquidity"],"distributions before calls"),
        (["property","exit_cap_rate"],"0"),
        (["property","principal_payments"],["20","20","550"]),
        (["property","loan"],"1020"),
        (["property","noi",0],"40"),
        (["property","stress_forward_noi"],"1"),
        (["smoothing","theta"],"1"),
        (["smoothing","latent_sigma"],"0"),
        (["smoothing","latent_market_correlation"],"1.1"),
        (["smoothing","latent_path",0],"-1"),
        (["smoothing","sum_horizon"],True),
        (["private","investment_calls"],["40","50","20","0"]),
        (["private","investment_calls",3],"1"),
        (["private","benchmark_gross_returns",1],"0"),
        (["private","delay_first_distribution"],"9"),
        (["private","gross_distributions",1],"40"),
        (["private","annual_fee_rate"],True),
        (["futures","margin_reserve"],"1001"),
        (["futures","performance_rate"],"1"),
        (["futures","deferred_marks"],["104"]),
        (["futures","near_entry"],"NaN"),
        (["liquidity","initial_cash"],float("inf")),
        (["property","entry_cost"],"1000000001")]
    for path,value in edits:
        edited=deepcopy(data);target=edited
        for key in path[:-1]:
            target=target[key]
        target[path[-1]]=value
        rejects(lambda edited=edited:model.run(edited),str(path))
    edited=deepcopy(data);edited["private"].update(carry_rate="0.9",gross_distributions=["0","80","80","1"])
    rejects(lambda:model.run(edited),"terminal carry cannot be funded by earlier distributions")
    edited=deepcopy(data);edited["futures"]["unknown_borrowing"]=True
    rejects(lambda:model.run(edited),"unknown financing field")
    rejects(lambda:model.irr(qvec([-100,230,-132,1])),"multiple cash sign changes")
    groups.append("Allowed financial interventions, exact funding boundaries and contradictory/domain input rejections")

    reference=model.load(ASSETS/"v09-c10-output.json")
    equivalent(result,reference)
    manifest=model.load(ASSETS/"v09-c10-manifest.json")
    payload_names={"v09-c10-"+suffix for suffix in ("inputs.json","analysis.py","output.json","README.txt")}
    same({x["file"] for x in manifest["files"]},payload_names,"exact distributed payload set")
    same(len(manifest["files"]),4,"no duplicate manifest entry")
    for item in manifest["files"]:
        payload=(ASSETS/item["file"]).read_bytes()
        same(len(payload),item["bytes"],"manifest bytes")
        same(hashlib.sha256(payload).hexdigest(),item["sha256"],"manifest SHA256")
    html=(ROOT/"content/chapters/v09-c10.html").read_text()
    doc=Structure();doc.feed(html);doc.close()
    same(doc.stack,[],"balanced manuscript fragment")
    same(doc.h1,0,"no duplicated generated title")
    same((doc.worked,doc.exercises,doc.solutions),(4,8,8),"four cases and eight complete solution items")
    same(len(doc.ids),len(set(doc.ids)),"unique chapter anchors")
    for name in payload_names|{"v09-c10-manifest.json"}:
        same(name in doc.hrefs,True,"flat offline route "+name)
    sources=model.load(ROOT/"content/reviews/v09-c10-sources.json")
    canonical={s["id"]:s for s in model.load(ROOT/"content/sources.json")}
    same(len({s["id"] for s in sources}),len(sources),"unique scoped source IDs")
    for source in sources:
        same("sources.html#"+source["id"] in doc.hrefs,True,"source actually linked")
        for key in ["id","title","url","use","checked","verification"]:
            same(bool(source[key]),True,"source required field "+key)
        if source["id"] in {"v08-c10-kaplan-stromberg","v08-c10-ilpa-performance"}:
            same(source,canonical[source["id"]],"exact accepted fund-source reuse")
    groups.append("Complete output regression, manuscript structure, scoped source records and distributed payload integrity")

    with tempfile.TemporaryDirectory(prefix="rowan-offline-") as folder:
        target=Path(folder)
        for name in payload_names|{"v09-c10-manifest.json"}:
            shutil.copyfile(ASSETS/name,target/name)
        script=target/"v09-c10-analysis.py";inputs=target/"v09-c10-inputs.json"
        normal=subprocess.run([sys.executable,"-B",str(script)],cwd=target.parent,capture_output=True,text=True,check=True)
        same(normal.stderr,"","portable default CLI quiet stderr")
        equivalent(json.loads(normal.stdout),reference,"portable normal CLI")
        destination=target/"new-output.json"
        optimized=subprocess.run([sys.executable,"-B","-O",str(script),"--input",str(inputs),"--output",str(destination)],cwd=target.parent,capture_output=True,text=True,check=True)
        same((optimized.stdout,optimized.stderr),("",""),"portable optimized output-file CLI quiet")
        equivalent(model.load(destination),reference,"portable optimized CLI")
        for output in [inputs,target/"v09-c10-output.json",destination]:
            before=output.read_bytes()
            collision=subprocess.run([sys.executable,"-B",str(script),"--input",str(inputs),"--output",str(output)],cwd=target.parent,capture_output=True,text=True)
            same(collision.returncode,2,"output collision rejected")
            same(collision.stdout,"","failed CLI has no false output")
            same(output.read_bytes(),before,"existing input/reference/output preserved")
        invalid=target/"invalid.json"
        invalid.write_text('{"case":"a","case":"b"}')
        rejects(lambda:model.load(invalid),"duplicate JSON keys")
        invalid.write_text('{"x":NaN}')
        rejects(lambda:model.load(invalid),"nonfinite JSON constant")
        failed=subprocess.run([sys.executable,"-B","-O",str(script),"--input",str(invalid)],capture_output=True,text=True)
        same(failed.returncode,2,"optimized CLI preserves invalid-input guard")
        same(failed.stdout,"","invalid optimized CLI has no result")
    groups.append("Copied offline normal/optimized CLI, strict JSON and no-clobber output behavior")
    return {"chapter":"v09-c10","status":"passed","groups":len(groups),"comparisons":comparisons,"domain_rejections":rejections,
            "checks":[{"name":name,"status":"passed"} for name in groups],
            "limitations":"Comparison count includes economic anchors, full reference fields, source/structure/integrity and portable output checks, not that many separate derivations. Conditional synthetic cases do not estimate premiums, validate real appraisals or certify visual/print quality."}


if __name__ == "__main__":
    print(json.dumps(check(),indent=2,allow_nan=False))
