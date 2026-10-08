"""Independent Nacre case checks. Quiet check() returns strict JSON.

The operating cash reconstruction, dated debt ledger and terminal series below
are independent oracles, not copies of the benchmark's control-flow algorithm.
"""
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
from fractions import Fraction as F
import hashlib
from html.parser import HTMLParser
import importlib.util
import io
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "content/projects"


class Structure(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids, self.hrefs, self.points = [], [], []
        self.solutions = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.ids.append(attrs["id"])
        if "href" in attrs:
            self.hrefs.append(attrs["href"])
        if "data-points" in attrs:
            self.points.append(int(attrs["data-points"]))
        if tag == "details" and "solutions" in attrs.get("class", "").split():
            self.solutions += 1


def check():
    comparisons = 0

    def same(actual, expected, label):
        nonlocal comparisons
        comparisons += 1
        if actual != expected:
            raise AssertionError(f"{label}: {actual!r} != {expected!r}")

    def require(condition, label):
        same(bool(condition), True, label)

    def rejects(call, label):
        try:
            call()
        except ValueError:
            return
        raise AssertionError("Expected bounded-domain rejection: " + label)

    captured = io.StringIO()
    with redirect_stdout(captured), redirect_stderr(captured):
        spec = importlib.util.spec_from_file_location("v08_nacre_benchmark", ASSETS / "v08-assessment-analysis.py")
        model = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(model)
    same(captured.getvalue(), "", "quiet module import")
    data = json.loads((ASSETS / "v08-assessment-inputs.json").read_text())
    with redirect_stdout(captured), redirect_stderr(captured):
        result = model.run(data)
    same(captured.getvalue(), "", "quiet benchmark run")
    json.dumps(result, allow_nan=False)
    groups = []

    # Independent invoice/cost/tax cash reconstruction, not NOPAT + D&A code.
    raw = {
        "base": {"sales": [600, 660, 720], "variable": [360, 396, 432],
                 "nwc": [90, 99, 108], "nopat": [F(135, 2), F(333, 4), F(99)],
                 "fcff": [F(65, 2), F(189, 4), F(405, 4)]},
        "downside": {"sales": [540, 600, 660], "variable": [F(1674, 5), 372, F(2046, 5)],
                     "nwc": [108, 108, 99], "nopat": [F(207, 5), F(225, 4), F(711, 10)],
                     "fcff": [F(-58, 5), F(117, 4), F(1827, 20)]},
    }
    capitals = {}
    for scenario, oracle in raw.items():
        rows = model.forecast(data, scenario)
        nwc, ppe, capital = F(75), F(425), F(500)
        for i, row in enumerate(rows):
            sales, variable = F(oracle["sales"][i]), F(oracle["variable"][i])
            dep, capex = [30, 33, 36][i], [F(50), F(60), F(99, 4)][i]
            tax = (sales - variable - 120 - dep) / 4
            operating_receipts_less_costs = sales - variable - 120 - (F(oracle["nwc"][i]) - nwc)
            cash_after_tax_investment = operating_receipts_less_costs - tax - capex
            new_ppe = ppe + capex - dep
            new_capital = new_ppe + F(oracle["nwc"][i])
            expected = {"revenue": sales, "variable_cost": variable, "fixed_cash_cost": F(120),
                        "ebitda": sales - variable - 120, "ebit": sales - variable - 120 - dep,
                        "operating_tax": tax, "nopat": oracle["nopat"][i],
                        "fcff": cash_after_tax_investment, "closing_ppe": new_ppe,
                        "closing_nwc": F(oracle["nwc"][i]), "closing_capital": new_capital,
                        "net_reinvestment": new_capital - capital}
            for field, expected_value in expected.items():
                same(row[field], expected_value, f"{scenario} year{i+1} {field}")
            same(cash_after_tax_investment, oracle["fcff"][i], "independent signed operating cash anchor")
            same(cash_after_tax_investment + new_capital - capital, oracle["nopat"][i], "capital return identity")
            nwc, ppe, capital = F(oracle["nwc"][i]), new_ppe, new_capital
        capitals[scenario] = capital
    groups.append("Independent operating receipts/cost/tax cash and six capital roll-forwards")

    # Continuing cash is an explicit growing series with an independently dated tail.
    ev_anchors = {"base": F(1806975, 2662), "downside": F(147123, 242)}
    terminal_anchors = {"base": {"revenue": F(700), "ebitda": F(126), "depreciation": F(35),
                                 "nopat": F(273, 4), "capex": F(395, 8), "delta_nwc": F(-3),
                                 "closing_ppe": F(3801, 8), "terminal_value": F(11375, 16)},
                        "downside": {"revenue": F(8956, 13), "ebitda": F(40302, 325), "depreciation": F(2239, 65),
                                     "nopat": F(6717, 100), "capex": F(107387, 2600), "delta_nwc": F(282, 65),
                                     "closing_ppe": F(1215777, 2600), "terminal_value": F(11195, 16)}}
    r, g, R = F(1, 10), F(1, 50), F(3, 25)
    for scenario in raw:
        value = model.valuation(data, scenario)
        tail, K = value["terminal"], capitals[scenario]
        for field, expected in terminal_anchors[scenario].items():
            same(tail[field], expected, scenario + " terminal " + field)
        same(tail["reinvestment_fraction"], F(1, 6), "growth funding fraction")
        same(tail["closing_ppe"] + tail["closing_nwc"], K * F(51, 50), "terminal asset stocks")
        same(tail["capex"] - tail["depreciation"] + tail["delta_nwc"], K / 50, "terminal cash investment")
        first_cash = R * K - K / 50
        five_year_pv = sum(first_cash * (1 + g) ** n / (1 + r) ** (n + 1) for n in range(5))
        remaining_pv = first_cash * (1 + g) ** 5 / (r - g) / (1 + r) ** 5
        same(five_year_pv + remaining_pv, tail["terminal_value"], "five actual continuing payments plus residual at date8")
        direct_pv = sum(c / F(11, 10) ** (i + 1) for i, c in enumerate(raw[scenario]["fcff"]))
        direct_pv += (five_year_pv + remaining_pv) / F(11, 10) ** 3
        same(value["operating_enterprise_value"], direct_pv, "independently dated total DCF")
        same(direct_pv, ev_anchors[scenario], "exact operating DCF anchor")
        same(value["pre_action_equity_value"], direct_pv - 160, "old claims bridge")
        same(value["buyer_npv"], direct_pv - 668, "buyer cost versus company value")
        same(value["maximum_seller_price_after_fee"], direct_pv - 168, "maximum seller price")
        for J, Q in [(F(70), F(0)), (F(3195, 52), F(0)), (F(70), F(445, 52)), (F(70), F(20))]:
            company_equity = direct_pv + 60 + 30 + J - Q - 250
            owner_outlay = 500 + 8 + J - Q
            same(company_equity - owner_outlay, value["buyer_npv"], "equal owner/corporate cash transfer cancels")
        bad_tv = tail["nopat"] / (r - g)
        omission = (bad_tv - tail["terminal_value"]) / (1 + r) ** 3
        same(omission, value["value_overstatement_if_reinvestment_omitted"], "funding-free growth error quantified")
        require(omission > abs(value["buyer_npv"]), "omitted investment is economically material")
        misdated = sum(c / (1 + r) ** (i + 1) for i, c in enumerate(raw[scenario]["fcff"])) + tail["terminal_value"] / (1 + r) ** 4
        require(misdated != direct_pv, "wrong terminal discount date detected")
    same(model.terminal(data, model.forecast(data, "base"), required_return=R)["terminal_value"], capitals["base"], "growth-neutral capital value when R equals r")
    groups.append("Dated continuing series, year4 asset/cash closure, owner bridges and value-error detectors")

    peers = model.peer_comparison(data)
    for row, ev, earnings, multiple in zip(peers["candidates"], [550, 720, 975, 400, 270], [100, 120, 150, 100, -5], [F(11, 2), F(6), F(13, 2), F(4), None]):
        same(row["operating_ev"], F(ev), "peer claim reconciliation " + row["id"])
        same(row["normalized_ebitda"], F(earnings), "peer earnings normalization " + row["id"])
        same(row["positive_profit_multiple"], multiple, "usable peer quotient " + row["id"])
    same(peers["qualified_ids"], ["P1", "P2", "P3"], "full universe eligibility")
    same(peers["low_median_high_multiples"], [F(11, 2), F(6), F(13, 2)], "median/range")
    same(peers["aggregate_ev_over_aggregate_ebitda"], F(449, 74), "aggregate ratio is EBITDA weighted")
    same(peers["targets"]["base"]["pre_action_equity_low_median_high"], list(map(F, [434, 488, 542])), "base matched peer bridge")
    same(peers["targets"]["downside"]["pre_action_equity_low_median_high"], [F(1873, 5), F(2116, 5), F(2359, 5)], "downside matched peer bridge")
    require(F(930, 150) != peers["candidates"][2]["positive_profit_multiple"], "omitted NCI changes the multiple")
    same(peers["targets"]["base"]["normalized_forward_year1_ebitda"], F(108), "peer denominator is not terminal EBITDA126")
    groups.append("All five peer claims, symmetric normalization, eligibility and matched forward denominators")

    # Independent gross receipts/payments ledger with fixed contractual principal.
    debt_oracles = {
        "base": {"cash": [F(160), F(339, 10), F(30), F(1893659, 25000)],
                 "line": [F(0), F(0), F(1747, 500), F(0)], "note": [F(0), F(0), F(0)]},
        "downside": {"cash": [F(160), F(30), F(30), F(30)],
                     "line": [F(0), F(201, 5), F(34081, 500), F(0)], "note": [F(0), F(0), F(817543, 25000)]}}
    for scenario, oracle in debt_oracles.items():
        plan = model.treasury(data, scenario)
        same(plan["funded"], True, "benchmark funded flag")
        for i, row in enumerate(plan["rows"]):
            term_open, term_close = [250, 100, 50][i], [100, 50, 0][i]
            debt_interest = F(term_open, 1) * F(3, 50) + oracle["line"][i] * F(3, 50)
            gross_receipts = oracle["cash"][i] + oracle["cash"][i] / 25 + raw[scenario]["fcff"][i] + oracle["note"][i]
            gross_payments = debt_interest + (term_open - term_close)
            if i < 2:
                gross_receipts += max(F(0), oracle["line"][i + 1] - oracle["line"][i])
                gross_payments += max(F(0), oracle["line"][i] - oracle["line"][i + 1])
            else:
                gross_payments += oracle["line"][i]  # All old revolving principal paid exactly once.
            same(gross_receipts - gross_payments, oracle["cash"][i + 1], "independent gross cash ledger")
            for key, expected in {"opening_cash": oracle["cash"][i], "closing_cash": oracle["cash"][i + 1],
                                  "closing_term": F(term_close), "closing_revolver": oracle["line"][i + 1],
                                  "new_note_proceeds": oracle["note"][i], "cash_interest": oracle["cash"][i] / 25}.items():
                same(row[key], expected, scenario + " treasury " + key)
            same(row["term_interest"] + row["revolver_interest"], debt_interest, "opening-principal interest")
            require(row["closing_cash"] >= 30, "cash minimum at actual date")
            if i < 2:
                cap = min(F(120), row["ebitda"] * F(7, 4) - term_close)
                same(row["revolver_limit"], cap, "effective commitment")
                require(oracle["line"][i + 1] <= cap, "actual debt within effective commitment")
        same(plan["rows"][-1]["revolver_maturity_repayment"], oracle["line"][2], "full contractual revolver maturity")
        same(plan["continuing_annual_coupon"], oracle["note"][2] * F(3, 50), "new note coupon remains visible")
        continuing_cash = capitals[scenario] / 10 + F(6, 5) - oracle["note"][2] * F(3, 50)
        same(plan["year4_cash_available_after_coupon"], continuing_cash, "first continuing owner cash")
        require(continuing_cash > 0, "coupon sustainable in monotone growing tail")
    same(model.treasury(data, "downside")["rows"][2]["cash_after_old_debt_maturity"], F(-67543, 25000), "negative post-maturity cash precedes note")
    low_note_cap = deepcopy(data)
    low_note_cap["finance"]["replacement_note_cap"] = "30"
    failed = model.treasury(low_note_cap, "downside")
    same((failed["funded"], failed["failure_year"], failed["cash_gap"]), (False, 3, F(67543, 25000)), "explicit takeout limit binds without invented refinancing")
    groups.append("Independent gross cash/debt ledgers, old-claim extinguishment and continuing-note coverage")

    boundaries = model.thresholds(data)
    expected = {"downside_date1_line_limit": F(491, 10), "minimum_equity_with_asset_sale": F(3195, 52),
                "minimum_equity_without_asset_sale": F(4755, 52), "maximum_initial_payout_with_equity70_and_sale": F(445, 52),
                "maximum_extra_downside_nwc_year1": F(89, 10), "maximum_downside_nwc_year1": F(1169, 10),
                "maximum_downside_nwc_sales_ratio_year1": F(1169, 5400), "price_cap_nonnegative_in_both_forecasts": F(106467, 242)}
    for key, value in expected.items():
        same(boundaries[key], value, "analytic boundary " + key)
    # Derive from the dated cash inequality, independently of the model solver.
    same(F(26, 25) * (90 + F(3195, 52)) - F(58, 5) - 15 - 150 + F(491, 10), F(30), "minimum subscription equality")
    for scenario in raw:
        subscription = model.treasury(data, scenario, new_equity=F(3195, 52))
        payout = model.treasury(data, scenario, initial_payout=F(445, 52))
        same(subscription["rows"], payout["rows"], "same company cash yields same later path")
        require(subscription["funded"], "minimum subscription passes every later date")
    delay = model.treasury(data, "downside", extra_nwc_year1=F(89, 10))
    same(delay["rows"][1]["closing_revolver"], F(8587, 125), "temporary collection boundary year2 debt")
    same(delay["continuing_note_face"], F(415847, 12500), "temporary collection boundary takeout")
    for args, gap in [({"new_equity": F(3195, 52) - F(1, 100)}, F(13, 1250)),
                      ({"initial_payout": F(445, 52) + F(1, 100)}, F(13, 1250)),
                      ({"extra_nwc_year1": F(891, 100)}, F(1, 100))]:
        fail = model.treasury(data, "downside", **args)
        same((fail["funded"], fail["failure_year"], fail["cash_gap"]), (False, 1, gap), "small step beyond exact boundary")
        same(len(fail["rows"]), 1, "unfunded path stops without fictional future rows")
        require("closing_cash" not in fail["rows"][-1], "unfunded row has no asserted feasible closing cash")
    for key, gap in {"no_sale_no_subscription": F(951, 10), "sale_only": F(639, 10),
                     "equity70_without_asset_sale": F(223, 10), "proposed_initial_payout20": F(119, 10),
                     "collection_delay10": F(11, 10)}.items():
        branch = result["rejected_policies"][key]
        same((branch["funded"], branch["failure_year"], F(branch["cash_gap"])), (False, 1, gap), "named rejected branch " + key)
    same(F(11, 10) / F(26, 25), F(55, 52), "intervention repair requires additional unauthorized equity")
    groups.append("Equity/payout/collection boundaries, all later dates, beyond-boundary and rejected-plan checks")

    roic_anchors = {"base": F(1677491, 14218750), "downside": F(1839113, 13993750)}
    for scenario in raw:
        K = capitals[scenario]
        for cell in result["r_g_sensitivity"][scenario]:
            rr, gg = F(cell["r"]), F(cell["g"])
            direct = sum(c / (1 + rr) ** (i + 1) for i, c in enumerate(raw[scenario]["fcff"]))
            direct += ((R * K - gg * K) / (rr - gg)) / (1 + rr) ** 3
            same(F(cell["buyer_npv"]), direct - 668, "grid recomputes investment and opportunity cost")
        threshold = model.valuation(data, scenario)["break_even_terminal_roic"]
        same(threshold, roic_anchors[scenario], "reverse terminal ROIC anchor")
        same(model.valuation(data, scenario, roic=threshold)["buyer_npv"], F(0), "reverse value equality")
        require(model.valuation(data, scenario, roic=threshold - F(1, 100000))["buyer_npv"] < 0, "below terminal return boundary rejects price")
    intervention = {"base": F(-169339, 10648), "downside": F(-919327, 10648)}
    for scenario, expected in intervention.items():
        value = model.valuation(data, scenario, roic=F(23, 200))
        same(value["buyer_npv"], expected, "terminal economics intervention")
        same(value["terminal"]["normalized_ebitda_margin"], F(419, 2400), "margin consistent with changed ROIC")
        require(value["terminal"]["ebitda"] * F(7, 4) > 80, "effective note cap unchanged by margin intervention")
    delay_value_loss = F(10) / F(11, 10) - F(10) / F(11, 10) ** 2
    same(delay_value_loss, F(100, 121), "collection timing also has a conditional operating value cost")
    same(intervention["downside"] - delay_value_loss, F(-928127, 10648), "combined conditional value does not establish funding")
    groups.append("Eighteen coherent r/g cells, reverse-value thresholds and both transfer interventions")

    # Narrow model guards, including canonical fields that must not be ignored.
    for field, edit in [("sell_nonoperating_asset", False), ("initial_payout", "20"), ("new_equity", "66")]:
        changed = deepcopy(data)
        changed["benchmark_policy"][field] = edit
        rejects(lambda changed=changed: model.run(changed), "contradictory fixed policy " + field)
    modifications = [(["operations", "interest_deductible"], True), (["operations", "tax_rate"], "1"),
                     (["offer", "management_initial_payout"], "15"),
                     (["sensitivities", "intervention_extra_downside_nwc_year1"], "8"),
                     (["finance", "term_repayments"], ["100", "50", "50"]),
                     (["terminal", "nominal_growth"], "1/10"),
                     (["scenarios", "base", "quantity"], ["0", "66", "72"])]
    for path, edit in modifications:
        changed = deepcopy(data)
        destination = changed
        for key in path[:-1]:
            destination = destination[key]
        destination[path[-1]] = edit
        rejects(lambda changed=changed: model.run(changed), "/".join(path))
    rejects(lambda: model.treasury(data, "downside", new_equity=F(7001, 100)), "no unapproved extra equity")
    rejects(lambda: model.forecast(data, "base", extra_nwc_year1=-1), "negative delay outside parameter meaning")
    rejects(lambda: model.terminal(data, model.forecast(data, "base"), growth=F(1, 10)), "nonconvergent terminal growth")
    groups.append("Thirteen meaningful bounded-domain and named-policy rejection checks")

    preserved = json.loads((ASSETS / "v08-assessment-output.json").read_text())
    same(result, preserved, "full preserved output matches benchmark")
    manifest = json.loads((ASSETS / "v08-assessment-manifest.json").read_text())
    expected_files = {"v08-assessment-inputs.json", "v08-assessment-analysis.py", "v08-assessment-output.json", "v08-assessment-README.txt"}
    same({entry["file"] for entry in manifest["files"]}, expected_files, "manifest exact asset set")
    for entry in manifest["files"]:
        payload = (ASSETS / entry["file"]).read_bytes()
        same(entry["bytes"], len(payload), "manifest byte size")
        same(entry["sha256"], hashlib.sha256(payload).hexdigest(), "manifest digest")
    html = (ROOT / "content/assessments/parts/v08-project.html").read_text()
    structure = Structure()
    structure.feed(html)
    same(len(structure.ids), len(set(structure.ids)), "unique project anchors")
    same(structure.solutions, 1, "one complete instructor solution container")
    same(structure.points, [20, 20, 15, 25, 10, 10], "rubric domains")
    same(sum(structure.points), 100, "rubric sums to100")
    for anchor in ("project", "v08-project-contract", "v08-project-tail-solution", "v08-project-funding-solution", "v08-project-boundaries-solution", "v08-project-intervention"):
        require(anchor in structure.ids, "complete project component " + anchor)
    for asset in expected_files | {"v08-assessment-manifest.json"}:
        require(asset in structure.hrefs, "flat downloadable asset link")
    require(not any(h.startswith("projects/") for h in structure.hrefs), "public links have no unpublished directory")
    sources = json.loads((ROOT / "content/reviews/v08-project-sources.json").read_text())
    canonical = {item["id"]: item for item in json.loads((ROOT / "content/sources.json").read_text())}
    for source in sources:
        same(source, canonical[source["id"]], "exact reused source scope " + source["id"])
        require("sources.html#" + source["id"] in structure.hrefs, "source actually supports a cited method")
    with tempfile.TemporaryDirectory(prefix="nacre-offline-") as folder:
        target = Path(folder)
        for filename in ("v08-assessment-analysis.py", "v08-assessment-inputs.json"):
            shutil.copyfile(ASSETS / filename, target / filename)
        for optimize in (False, True):
            command = [sys.executable] + (["-O"] if optimize else []) + [str(target / "v08-assessment-analysis.py")]
            if optimize:
                command.append(str(target / "v08-assessment-inputs.json"))
            run = subprocess.run(command, cwd=ROOT.parent, capture_output=True, text=True, check=True)
            same(run.stderr, "", "portable execution stderr")
            same(json.loads(run.stdout), preserved, "isolated offline CLI with optimization=" + str(optimize))
    groups.append("Full artifact/rubric/source/manifest audit and isolated normal/optimized offline execution")
    return {"project": "v08", "case": "Nacre Process Controls", "status": "pass",
            "check_groups": len(groups), "independent_comparisons": comparisons,
            "checks": [{"name": name, "status": "pass"} for name in groups],
            "limits": "Original bounded case and exact model checks; no current-law, empirical pricing, human certification or visual UI claim."}


if __name__ == "__main__":
    print(json.dumps(check(), indent=2, allow_nan=False))
