"""Independent specialist audit for Aster; no call to the author's checker."""
from calendar import monthrange
from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
from decimal import Decimal, localcontext
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from io import StringIO
from math import exp, isclose, isfinite, log, sqrt
from pathlib import Path
import json
import runpy
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "content/projects"


def determinant(a):
    return (a[0][0]*(a[1][1]*a[2][2]-a[1][2]*a[2][1]) -
            a[0][1]*(a[1][0]*a[2][2]-a[1][2]*a[2][0]) +
            a[0][2]*(a[1][0]*a[2][1]-a[1][1]*a[2][0]))


def cramer(a, b):
    """Exact determinant-ratio solution, distinct from the lab's bootstrap."""
    denominator = determinant(a)
    answer = []
    for column in range(3):
        modified = [row[:] for row in a]
        for i in range(3):
            modified[i][column] = F(b[i])
        answer.append(determinant(modified)/denominator)
    return answer


def year_day(year, month, day):
    """Count calendar days by actual month lengths, without datetime subtraction."""
    return sum(monthrange(year, m)[1] for m in range(1, month)) + day


class Fragment(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack, self.ids, self.links, self.text = [], [], [], []
        self.worked = self.exercises = self.solutions = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "h1":
            raise ValueError("Duplicate generated h1")
        if tag == "p" and any(t == "p" for t, _ in self.stack):
            raise ValueError("Nested paragraphs")
        if "id" in a:
            self.ids.append(a["id"])
        if "href" in a:
            self.links.append(a["href"])
        if tag == "aside" and "worked" in a.get("class", "").split():
            self.worked += 1
        if tag == "li" and self.stack and self.stack[-1][0] == "ol":
            if "exercises" in self.stack[-1][1].get("class", "").split():
                self.exercises += 1
            elif any(t == "details" and "solutions" in at.get("class", "").split() for t, at in self.stack):
                self.solutions += 1
        if tag not in {"br", "hr", "img", "meta", "link", "input"}:
            self.stack.append((tag, a))

    def handle_endtag(self, tag):
        if not self.stack or self.stack[-1][0] != tag:
            raise ValueError("Unbalanced " + tag)
        self.stack.pop()

    def handle_data(self, value):
        self.text.append(value)


def check():
    comparisons = rejected = 0
    groups = []

    def eq(actual, expected, label):
        nonlocal comparisons
        comparisons += 1
        if isinstance(expected, F):
            actual = F(actual)
        if actual != expected:
            raise AssertionError(f"{label}: {actual!r} != {expected!r}")

    def near(actual, expected, label, tolerance=2e-12):
        nonlocal comparisons
        comparisons += 1
        if not isfinite(float(actual)) or not isclose(float(actual), float(expected), rel_tol=tolerance, abs_tol=tolerance):
            raise AssertionError(f"{label}: {actual!r} != {expected!r}")

    def require(value, label):
        eq(bool(value), True, label)

    def rejects(edit, label):
        nonlocal rejected
        candidate = deepcopy(data)
        edit(candidate)
        try:
            model["run"](candidate)
        except ValueError:
            rejected += 1
            return
        raise AssertionError("Invalid contract accepted: " + label)

    data = json.loads((ASSETS / "v10-c01-inputs.json").read_text())
    untouched = deepcopy(data)
    stream = StringIO()
    with redirect_stdout(stream), redirect_stderr(stream):
        model = runpy.run_path(str(ASSETS / "v10-c01-analysis.py"))
        result = model["run"](data)
    eq(stream.getvalue(), "", "quiet model import and run")
    eq(data, untouched, "input not mutated")
    eq(result, json.loads((ASSETS / "v10-c01-output.json").read_text()), "every preserved field")
    json.dumps(result, allow_nan=False)
    groups.append("quiet nonmutating model and complete reference JSON")

    settled = year_day(2025, 4, 16)
    previous = year_day(2025, 1, 15)
    following = year_day(2025, 7, 15)
    elapsed, period = settled-previous, following-previous
    year_length = sum(monthrange(2025, m)[1] for m in range(1, 13))
    maturity_gap = year_length-settled+15
    s = result["settlement"]
    eq((s["elapsed_days"], s["coupon_period_days"], s["days_to_next_coupon"], s["days_to_maturity"]),
       (elapsed, period, period-elapsed, maturity_gap), "actual calendar spans")
    eq((elapsed, period, maturity_gap), (91, 181, 274), "calendar worked anchors")
    dirty = F(2494, 25)
    accrued = F(3*elapsed, period)
    for key, expected in {"coupon": F(3), "dirty": dirty, "accrued": accrued,
                          "clean": dirty-accrued, "invoice_dirty": 2500*dirty,
                          "invoice_accrued": 2500*accrued,
                          "invoice_clean": 2500*(dirty-accrued)}.items():
        eq(s[key], expected, "dated settlement " + key)
    eq([F(x) for x in s["cashflows"]], [F(3), F(103)], "remaining entitled payments")
    eq(F(s["invoice_clean"])+F(s["invoice_accrued"]), F(249400), "full invoice closure")
    eq(F(s["invoice_dirty"])-248000, F(1400), "cash shortfall")
    groups.append("month-length date reconstruction and actual settlement funding")

    matrix = [[F(x) for x in row] for row in ((100, 0, 0), (4, 104, 0), (6, 6, 106))]
    prices = [F(96), F(2436, 25), F(501, 5)]
    d = cramer(matrix, prices)
    eq(d, [F(24, 25), F(9, 10), F(21, 25)], "full determinant solution")
    curve = result["curve"]
    eq([F(x) for x in curve["discounts"]], d, "all lab discounts")
    target = [F(5), F(5), F(105)]
    transposed = [list(row) for row in zip(*matrix)]
    holdings = cramer(transposed, target)
    eq([F(x) for x in curve["replicating_holdings"]], holdings, "actual bond-quantity system")
    eq(holdings, [F(-25, 2756), F(-25, 2756), F(105, 106)], "replica fractions")
    fair = sum(c*p for c, p in zip(target, d))
    eq(fair, F(195, 2), "target independent valuation")
    for key in ("target_fair_price", "replica_cost"):
        eq(curve[key], fair, key)
    eq(curve["quoted_target_minus_fair"], F(1, 2), "initial arbitrage cash")
    eq([F(x) for x in curve["replica_cashflows"]], target, "all replica dated output")
    for i in range(3):
        eq(sum(holdings[j]*matrix[j][i] for j in range(3)), target[i], "cash cancellation at date")
        eq(sum(matrix[i][j]*d[j] for j in range(3)), prices[i], "original market price")
        eq(curve["repriced_instruments"][i], prices[i], "repriced output")
        near(log(1+curve["annual_spots"][i]), -log(float(d[i]))/(i+1), "annual spot log identity")
        near(curve["continuous_spots"][i], -log(float(d[i]))/(i+1), "continuous spot")
    eq([F(x) for x in curve["one_year_forward_gross"]], [F(16, 15), F(15, 14)], "annual forward factors")
    groups.append("independent determinant systems, every claim date and spot conversions")

    # High precision closed solution; the model's log bisection is not used.
    with localcontext() as context:
        context.prec = 70
        price_decimal = Decimal("104.88")
        gross = (Decimal(8)+(64+4*price_decimal*108).sqrt())/(2*price_decimal)
        growth = (Decimal(116)/price_decimal).sqrt()-1
        terminal_at_root = Decimal(108)+8*gross
    y = result["yield_case"]
    eq([F(x) for x in y["cashflows"]], [F(8), F(108)], "yield payments")
    eq(y["price"], F(2622, 25), "yield initial dated price")
    near(y["annual_ytm"], gross-1, "independent 70-digit quadratic")
    near(y["root_repricing"], price_decimal, "root reprice")
    eq(y["terminal_wealth_actual_reinvestment"], F(116), "cash accumulation")
    near(y["annualized_terminal_growth"], growth, "terminal cash CAGR")
    near(y["terminal_wealth_at_ytm_reinvestment"], terminal_at_root, "conditional YTM accumulation")
    near(y["two_year_zero_spot"], sqrt(F(10, 9))-1, "zero versus coupon yield")
    eq(y["sale_price_at_year_one"], F(1080, 11), "actual early sale price")
    eq(y["one_year_holding_return"], F(179, 14421), "coupon plus early sale")
    require(float(growth) < y["annual_ytm"] < y["two_year_zero_spot"], "three performance measures differ")
    near((1+.08/2)**2-1, .0816, "nominal versus effective quotation")
    near(exp(2*log(1.04)), 1.0816, "continuous quotation same gross growth")
    groups.append("high-precision root, coupon strategy and early-sale ledger")

    forward = result["forward"]
    for key, expected in {"gross_locked": F(16, 15), "lend_at_start": F(60),
                          "receive_at_end": F(64), "initial_cost": F(0),
                          "offered_end_receipt": F(321, 5),
                          "offered_lender_contract_value": F(9, 50),
                          "offered_minus_locked_terminal": F(1, 5)}.items():
        eq(forward[key], expected, "forward " + key)
    eq(60*d[0]-64*d[1], F(0), "offsetting initial funding")
    eq(F(321, 5)-64, F(1, 5), "final offered-forward arbitrage")
    eq(F(1, 5)*d[1], F(9, 50), "dated gain versus present value")
    near(forward["effective_annual_locked"], F(1, 15), "forward effective quote")
    near(forward["continuous_annual_locked"], log(F(16, 15)), "forward continuous quote")
    interp = result["interpolation"]
    geometric = exp((log(.96)+log(.90))/2)
    eq(interp["linear_discount"], F(93, 100), "linear midpoint")
    near(interp["log_linear_discount"], geometric, "geometric midpoint")
    near(interp["positive_log_perturbation_discount"], geometric*exp(.005), "positive perturbation")
    for key, expected in {"price_per_100_linear": F(93),
                          "price_per_100_log_linear": 100*geometric,
                          "price_per_100_perturbed": 100*geometric*exp(.005)}.items():
        if isinstance(expected, F):
            eq(interp[key], expected, key)
        else:
            near(interp[key], expected, key)
    for u in (1, 2):
        perturbed = exp((2-u)*log(.96)+(u-1)*log(.90)+.02*(u-1)*(2-u))
        near(perturbed, d[u-1], "preserved endpoint")
    require(log(F(16, 15))-.02 > 0, "minimum instantaneous forward is positive")
    near(log(F(16, 15))+.02, .08453852113757116, "maximum instantaneous forward")
    groups.append("forward funding and endpoint-preserving curve alternatives")

    # Exercises 1–9 solved explicitly. E5/E7 include analytic arguments in the
    # editorial record; E10's data/design adequacy is not reduced to arithmetic.
    outstanding, amortized = F(400), []
    for redemption in (100, 150, 150):
        amortized.append(outstanding/20+redemption)
        outstanding -= redemption
    eq(amortized, [F(120), F(165), F(315, 2)], "E1 actual principal clock")
    correct = sum(c*z for c, z in zip(amortized, d))
    wrong = sum(c*z for c, z in zip([120, 170, 170], d))
    eq((correct, correct+2, wrong, wrong-correct), (396, 398, 411, 15), "E1 price fee and error")
    leap_elapsed = year_day(2024, 5, 15)-year_day(2024, 2, 15)
    leap_period = year_day(2024, 8, 15)-year_day(2024, 2, 15)
    eq((leap_elapsed, leap_period), (90, 182), "E2 leap-year periods")
    ai = F(5, 2)*F(leap_elapsed, leap_period)
    eq(ai, F(225, 182), "E2 accrued")
    eq((F(496, 5)+ai)*1000, F(9139700, 91), "E2 invoice")
    eq(ai-5*F(90, 365), F(45, 13286), "E2 clock mismatch")
    d_changed = cramer(matrix, [96, 97, F(501, 5)])
    eq(d_changed, [F(24, 25), F(2329, 2600), F(23157, 27560)], "E3 changed full system")
    eq(sum(c*z for c, z in zip(target, d_changed)), F(268721, 2756), "E3 changed target")
    derivatives = cramer(matrix, [0, 1, 0])
    eq(derivatives, [F(0), F(1, 104), F(-6, 106*104)], "E3 quote Jacobian column")
    d_invalid = cramer(matrix, [96, F(2436, 25), 10])
    eq(d_invalid[2], F(-29, 2650), "E4 inconsistency")
    arb = [F(-3, 52), F(-3, 52), F(1)]
    eq([sum(arb[j]*matrix[j][i] for j in range(3)) for i in range(3)], [0, 0, 106], "E4 all future dates")
    eq(sum(h*p for h, p in zip(arb, [96, F(2436, 25), 10])), F(-29, 25), "E4 initial receipt")
    # Bounds follow from termwise comparison at extrema, not regression or fit.
    minimum, maximum = min(curve["annual_spots"][:2]), max(curve["annual_spots"][:2])
    require(8/(1+minimum)+108/(1+minimum)**2 >= 104.88, "E5 lower spot prices high")
    require(8/(1+maximum)+108/(1+maximum)**2 <= 104.88, "E5 upper spot prices low")
    fair_end, borrowed_end = F(80), 70*F(21, 20)**2
    eq(70*d[0]-fair_end*d[2], F(0), "E6 zero-portfolio budget")
    eq(fair_end-borrowed_end, F(113, 40), "E6 terminal profit")
    eq((fair_end-borrowed_end)*d[2], F(2373, 1000), "E6 present profit")
    near(sqrt(F(8, 7))-1, .06904496764969759, "E6 annualized two-year forward")
    bill = result["bill"]
    price = 100*(1-F(3, 50)*F(180, 360))
    gain = (100-price)/price
    for key, expected in {"quote_year_fraction": F(1, 2), "price": price,
                          "holding_gain": gain, "investment_simple_360": gain*2,
                          "investment_simple_365": gain*F(365, 180),
                          "incorrect_simple_yield_price": F(10000, 103)}.items():
        eq(bill[key], expected, "E8 " + key)
    near(bill["effective_annual_360"], F(591, 9409), "E8 annual gross return")
    near(bill["continuous_annual_360"], log(F(10000, 9409)), "E8 continuous return")
    eq((8+F(1080, 11))/F(2622, 25)-1, F(179, 14421), "E9 net one-year holding return")
    eq(3*F(99, 100)+103*F(95, 100), F(5041, 50), "retention dirty")
    eq(F(5041, 50)-F(6, 5), F(4981, 50), "retention clean")
    eq(95*F(99, 100), 99*F(95, 100), "retention forward funding")
    eq(F(100, 101)-1, F(-1, 101), "retention negative-rate claim")
    groups.append("all determinate exercise solutions and three delayed cases")

    def intervention(edit):
        candidate = deepcopy(data)
        edit(candidate)
        return model["run"](candidate)
    at_start = intervention(lambda x: x["settlement"].update(settlement="2025-01-15"))
    eq(at_start["settlement"]["accrued"], F(0), "valid coupon-date accrual boundary")
    eq(at_start["settlement"]["dirty"], dirty, "same supplied discounts at hypothetical other date")
    before_coupon = intervention(lambda x: x["settlement"].update(settlement="2025-07-14"))
    eq(before_coupon["settlement"]["accrued"], F(540, 181), "last admitted entitlement day")
    scaled = intervention(lambda x: x["settlement"].update(face="200"))
    eq(scaled["settlement"]["dirty"], 2*dirty, "face changes underlying amount")
    eq(scaled["settlement"]["invoice_dirty"], F(249400), "same acquired total face keeps invoice")
    multi = intervention(lambda x: x["forward"].update(end_year=3, principal="70", offered_effective_annual_rate="0.05"))
    eq(multi["forward"]["receive_at_end"], fair_end, "edited two-year forward")
    eq(multi["forward"]["offered_lender_contract_value"], F(-2373, 1000), "borrower-versus-lender sign")
    eq(multi["forward"]["offered_minus_locked_terminal"], F(-113, 40), "edited effective exponent")
    quoted = intervention(lambda x: x["bootstrap"]["prices"].__setitem__(1, "97"))
    eq([F(x) for x in quoted["curve"]["discounts"]], d_changed, "edited full-system comparison")
    negative = intervention(lambda x: x["bootstrap"].update(prices=["101", "110.12", "128.78"]))
    eq([F(x) for x in negative["curve"]["discounts"]], [F(101, 100), F(51, 50), F(11, 10)], "above-one positive discounts")
    require(negative["yield_case"]["annual_ytm"] < 0, "negative YTM admitted")
    zero_coupon = intervention(lambda x: x["yield_case"].update(annual_coupon="0", reinvestment_rate="0.2"))
    near(zero_coupon["yield_case"]["annual_ytm"], sqrt(F(10, 9))-1, "zero coupon exact yield boundary")
    eq(zero_coupon["yield_case"]["terminal_wealth_actual_reinvestment"], F(100), "no coupon means no reinvestment cash")
    groups.append("independent date, face, multi-year, price and zero-coupon interventions")

    rejects(lambda x: x["settlement"].update(settlement="2025-07-15"), "next coupon excluded")
    rejects(lambda x: x["settlement"].update(settlement="2025-01-14"), "pre-period date")
    rejects(lambda x: x["settlement"].update(face=True), "bool financial amount")
    rejects(lambda x: x["settlement"].update(maturity="2026-01-16"), "changed fixed schedule")
    rejects(lambda x: x["bootstrap"]["prices"].__setitem__(2, "10"), "negative discount")
    rejects(lambda x: x["bootstrap"]["prices"].__setitem__(2, "11.16"), "zero discount")
    rejects(lambda x: x["bootstrap"]["cashflows"][1].__setitem__(1, "105"), "contradictory observed row")
    rejects(lambda x: x["yield_case"].update(sale_yield_at_year_one="-1"), "nonpositive sale factor")
    rejects(lambda x: x["forward"].update(start_year=True), "bool forward date")
    rejects(lambda x: x["forward"].update(end_year=4), "unobserved forward date")
    rejects(lambda x: x["bill"].update(days=365, discount_rate="0.999"), "nonpositive bill value")
    rejects(lambda x: x["bill"].update(discount_rate=float("nan")), "nonfinite input")
    rejects(lambda x: x["bill"].update(quote_basis=365), "changed quotation contract")
    rejects(lambda x: x.update(unpriced_call_option=True), "unknown economic field")
    groups.append("14 financial, calendar and contract-domain rejections")

    doc = Fragment()
    doc.feed((ROOT / "content/chapters/v10-c01.html").read_text())
    doc.close()
    eq(doc.stack, [], "balanced complete HTML")
    eq((doc.worked, doc.exercises, doc.solutions), (4, 10, 10), "complete worked/exercise structure")
    eq(len(doc.ids), len(set(doc.ids)), "unique anchors")
    prose = " ".join("".join(doc.text).split())
    require("continuously differentiable" in prose and "D(0)=1" in prose, "repaired integral regularity")
    for clause in ("cash-flow", "shorting", "full next-coupon entitlement", "physical expectation",
                   "strictly after settlement", "underidentified", "out-of-sample", "Retention answers"):
        require(clause in prose, "proof/teaching constraint " + clause)
    sources = json.loads((ROOT / "content/reviews/v10-c01-sources.json").read_text())
    eq({r["id"] for r in sources}, {"v10-c01-mit-fixed-income", "v10-c01-treasury-accrual", "v10-c01-boe-curve-estimation"}, "scoped source identifiers")
    for source in sources:
        require("sources.html#"+source["id"] in doc.links, "source linked")
    for suffix in ("inputs.json", "analysis.py", "output.json", "manifest.json", "README.txt"):
        require("v10-c01-"+suffix in doc.links, "offline artifact link")
    for href in doc.links:
        require("/" not in href.split("#")[0], "flat internal link")
    assignment = json.loads((ROOT / "production/v10-opening-c01-peer-assignment.json").read_text())
    eq(len(assignment["frozen_payloads"]), 9, "complete reviewed file assignment")
    for record in assignment["frozen_payloads"]:
        b = (ROOT / record["path"]).read_bytes()
        eq(len(b), record["bytes"], "reviewed bytes")
        eq(sha256(b).hexdigest(), record["sha256"], "reviewed hash")
    manifest = json.loads((ASSETS / "v10-c01-manifest.json").read_text())
    eq(len(manifest["files"]), 4, "four-file lab manifest")
    for record in manifest["files"]:
        b = (ASSETS / record["file"]).read_bytes()
        eq((len(b), sha256(b).hexdigest()), (record["bytes"], record["sha256"]), "lab manifest")
    author = json.loads((ROOT / "content/reviews/v10-c01-author.json").read_text())
    eq(len(author["reviewed_hashes"]), 8, "author nonself payload scope")
    for record in author["reviewed_hashes"]:
        b = (ROOT / record["path"]).read_bytes()
        eq((len(b), sha256(b).hexdigest()), (record["bytes"], record["sha256"]), "author exact reviewed bytes")
    groups.append("final repaired proof clause, HTML, sources and exact nine reviewed payloads")

    with tempfile.TemporaryDirectory(prefix="v10-c01-peer-") as folder:
        parent = Path(folder)
        bundle = parent / "bundle"
        bundle.mkdir()
        for suffix in ("inputs.json", "analysis.py"):
            shutil.copy2(ASSETS / ("v10-c01-"+suffix), bundle / ("v10-c01-"+suffix))
        for flags in ([], ["-O"]):
            command = [sys.executable, "-I", "-B", *flags, str(bundle / "v10-c01-analysis.py")]
            cli = subprocess.run(command, cwd=parent, capture_output=True, text=True, timeout=20)
            eq(cli.returncode, 0, "isolated CLI exit")
            eq(cli.stderr, "", "isolated CLI stderr")
            eq(json.loads(cli.stdout), result, "isolated complete normal/optimized result")
    groups.append("isolated normal and optimized model execution")
    summary = {"chapter": "v10-c01", "reviewer": "cost_peer", "passed": True,
               "group_count": len(groups), "groups": groups, "comparisons": comparisons,
               "domain_rejections": rejected, "worked_cases": 4, "exercises": 10,
               "oracle_independence": "Never calls the author checker; determinant ratios, actual month lengths, 70-digit algebraic root and separate dated ledgers reconstruct the model.",
               "limits": "Proofs, source scopes and open-answer adequacy also reviewed editorially. No real-market authentication, browser UI checks or independent human certification."}
    json.dumps(summary, allow_nan=False)
    return summary


if __name__ == "__main__":
    print(json.dumps(check(), ensure_ascii=False, indent=2, allow_nan=False))
