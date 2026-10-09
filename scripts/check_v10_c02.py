"""Independent fixed-income arithmetic, boundary and artifact checks; quiet check()."""
from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
from fractions import Fraction as F
from html.parser import HTMLParser
from math import exp, isclose, isfinite, log
from pathlib import Path
from types import SimpleNamespace
import hashlib
import io
import json
import runpy
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "content/projects"
CHAPTER = ROOT / "content/chapters/v10-c02.html"


class Structure(HTMLParser):
    """The fragment intentionally uses explicit closing tags, even where optional."""
    VOID = {"br", "hr", "img", "input", "meta", "link", "wbr", "source"}

    def __init__(self):
        super().__init__()
        self.stack = []
        self.ids, self.hrefs, self.text = [], [], []
        self.worked = self.exercises = self.answers = self.details = 0
        self.main_solution_depth = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "h1":
            raise ValueError("Chapter fragments must not duplicate the generated h1")
        if tag == "p" and any(t == "p" for t, _ in self.stack):
            raise ValueError("Nested paragraphs")
        if "id" in a:
            self.ids.append(a["id"])
        if "href" in a:
            self.hrefs.append(a["href"])
        if tag == "aside" and "worked" in a.get("class", "").split():
            self.worked += 1
        if tag == "details" and "solutions" in a.get("class", "").split():
            self.details += 1
            if self.details == 1:
                self.main_solution_depth = len(self.stack)
        if tag == "li" and self.stack and self.stack[-1][0] == "ol":
            if "exercises" in self.stack[-1][1].get("class", "").split():
                self.exercises += 1
            if self.main_solution_depth is not None:
                self.answers += 1
        if tag not in self.VOID:
            self.stack.append((tag, a))

    def handle_endtag(self, tag):
        if not self.stack or self.stack[-1][0] != tag:
            raise ValueError("Unbalanced tag: " + tag)
        self.stack.pop()
        if tag == "details" and len(self.stack) == self.main_solution_depth:
            self.main_solution_depth = None

    def handle_data(self, value):
        self.text.append(value)


def check():
    comparisons = rejections = 0
    groups = []

    def same(actual, expected, label):
        nonlocal comparisons
        comparisons += 1
        if actual != expected:
            raise AssertionError(f"{label}: {actual!r} != {expected!r}")

    def near(actual, expected, label, rel=2e-12, absolute=2e-11):
        nonlocal comparisons
        comparisons += 1
        if not isclose(float(actual), float(expected), rel_tol=rel, abs_tol=absolute):
            raise AssertionError(f"{label}: {actual!r} != {float(expected)!r}")

    def require(value, label):
        same(bool(value), True, label)

    def tree(actual, expected, label):
        if isinstance(expected, dict):
            same(set(actual), set(expected), label + " fields")
            for key in expected:
                tree(actual[key], expected[key], label + "." + key)
        elif isinstance(expected, list):
            same(len(actual), len(expected), label + " length")
            for i, (a, b) in enumerate(zip(actual, expected)):
                tree(a, b, f"{label}[{i}]")
        elif isinstance(expected, (int, float, F)) and not isinstance(expected, bool):
            require(isfinite(float(actual)), label + " finite")
            near(actual, expected, label)
        else:
            same(actual, expected, label)

    def rejects(call, label):
        nonlocal rejections
        try:
            call()
        except ValueError:
            rejections += 1
            return
        raise AssertionError("Expected documented rejection: " + label)

    quiet = io.StringIO()
    data = json.loads((PROJECT / "v10-c02-inputs.json").read_text())
    with redirect_stdout(quiet), redirect_stderr(quiet):
        model = SimpleNamespace(**runpy.run_path(str(PROJECT / "v10-c02-analysis.py")))
        out = model.run(data)
    same(quiet.getvalue(), "", "quiet import and run")
    json.dumps(out, allow_nan=False)
    tree(out, json.loads((PROJECT / "v10-c02-output.json").read_text()), "complete preserved output")
    groups.append("quiet strict JSON and every preserved field")

    # Independent baseline: differentiate the polynomial in d=1/(1+y), then
    # use d'=-d^2 and d''=2d^3. No analysis pricing/derivative helper is called.
    d = F(20, 21)
    p = 4*d + 4*d**2 + 4*d**3 + 104*d**4
    pd = 4 + 8*d + 12*d**2 + 416*d**3
    pdd = 8 + 24*d + 1248*d**2
    k, g = d*d*pd, 2*d**3*pd + d**4*pdd
    mac = k/p/d
    note = out["note"]
    expected_metrics = {
        "price": p, "cash_flow_pvs": [4*d, 4*d*d, 4*d**3, 104*d**4],
        "macaulay_years": mac, "modified_duration": k/p,
        "convexity": g/p, "dollar_duration": k, "dollar_convexity": g,
        "dv01_positive_loss_for_upward_bp": k/10000}
    tree(note["dirty"], expected_metrics, "discount-polynomial derivative")
    near(note["clean_price"], p, "coupon-date clean price")
    near(note["clean_fractional_sensitivity"], k/p, "clean fractional exposure")
    for j, h in enumerate((F(-1, 100), F(1, 100), F(1, 10))):
        dz = 1 / (F(21, 20) + h)
        actual = 4*dz + 4*dz**2 + 4*dz**3 + 104*dz**4
        linear, quadratic = p-k*h, p-k*h+g*h*h/2
        low_d = max(d, dz)
        third = 24*low_d**4 + 96*low_d**5 + 240*low_d**6 + 12480*low_d**7
        bound = third*abs(h)**3/6
        tree(note["scenarios"][j], {
            "yield_shift": h, "exact_dirty_price": actual,
            "linear_dirty_price": linear, "quadratic_dirty_price": quadratic,
            "linear_error_estimate_minus_exact": linear-actual,
            "quadratic_error_estimate_minus_exact": quadratic-actual,
            "absolute_quadratic_remainder_bound": bound}, "exact yield shock")
        require(linear <= actual, "convex tangent lower bound")
        require(abs(quadratic-actual) <= bound, "Taylor remainder certificate")
        require((quadratic-actual)*h > 0, "quadratic error direction")
    near(note["finite_difference"]["duration"], k/p, "FD first derivative", absolute=2e-7)
    near(note["finite_difference"]["convexity"], g/p, "FD second derivative", absolute=1e-6)
    smaller = deepcopy(data)
    smaller["note"]["finite_difference_step"] = 0.00005
    smaller_fd = model.run(smaller)["note"]["finite_difference"]
    require(abs(smaller_fd["duration"]-float(k/p)) <
            abs(note["finite_difference"]["duration"]-float(k/p)), "first derivative convergence")
    near(smaller_fd["convexity"], g/p, "smaller-step second derivative", absolute=1e-6)
    pv_shares = [v/p for v in expected_metrics["cash_flow_pvs"]]
    timing_var = sum(w*(t-mac)**2 for t, w in enumerate(pv_shares, 1))
    near(g/p, (timing_var+mac*mac+mac)*d*d, "PV variance convexity identity")
    require(1 < mac < 4, "positive-payment maturity bounds")
    groups.append("exact note polynomial, Taylor bounds, units and finite differences")

    # Solve actual initial market-value equations, then close dated receipts.
    v = 125*d**3
    f1, f5 = v/(2*d), v/(2*d**5)
    hedge = out["immunization"]
    near(hedge["initial_budget"], v, "funded initial liability PV")
    tree(hedge["asset_pv_weights"], [F(1, 2), F(1, 2)], "two equations give equal PV weights")
    tree(hedge["asset_market_values"], [v/2, v/2], "asset market values")
    tree(hedge["asset_zero_faces"], [f1, f5], "actual purchased faces")
    am, lm = hedge["asset_metrics"], hedge["liability_metrics"]
    for metric, expected_a, expected_l in (
            ("price", v, v), ("macaulay_years", 3, 3),
            ("modified_duration", 3*d, 3*d), ("convexity", 16*d*d, 12*d*d),
            ("dollar_duration", 3*v*d, 3*v*d),
            ("dollar_convexity", 16*v*d*d, 12*v*d*d),
            ("dv01_positive_loss_for_upward_bp", 3*v*d/10000, 3*v*d/10000)):
        near(am[metric], expected_a, "asset " + metric)
        near(lm[metric], expected_l, "liability " + metric)
    tree(am["cash_flow_pvs"], [v/2, v/2], "asset cash PVs")
    tree(lm["cash_flow_pvs"], [v], "liability cash PV")
    near(hedge["initial_surplus"], 0, "PV match")
    near(hedge["surplus_first_yield_derivative"], 0, "dollar duration match")
    near(hedge["surplus_second_yield_derivative"], 4*v*d*d, "strict surplus curvature")
    for j, h in enumerate((F(-1, 100), F(1, 100), F(1, 10))):
        q = 1/d+h
        early, late = f1*q*q, f5/(q*q)
        wealth = early+late
        x = (q*d)**2
        near(wealth-125, F(125, 2)*(x-1)**2/x, "global special-case squared identity")
        tree(hedge["single_shift_then_constant_rate_scenarios"][j], {
            "annual_yield_shift": h, "asset_pv": f1/q+f5/q**5,
            "liability_pv": 125/q**3, "valuation_surplus": (wealth-125)/q**3,
            "early_cash_reinvested_to_horizon": early, "long_zero_sold_at_horizon": late,
            "horizon_wealth": wealth, "horizon_surplus": wealth-125}, "dated constant-rate ledger")
    later = f1 + f5/F(11, 10)**2
    tree(hedge["later_path_intervention"], {
        "early_reinvestment_yield": 0, "long_sale_yield": F(1, 10),
        "early_cash_at_horizon": f1, "long_sale_receipt": f5/F(11, 10)**2,
        "horizon_wealth": later, "horizon_surplus": later-125}, "later uncontracted cash quotes")
    fee, scale = F(1, 500), F(500, 501)
    tree(hedge["entry_fee_intervention"], {
        "fee_rate": fee, "extra_initial_cash_for_original_holdings": fee*v,
        "holdings_scale_on_unchanged_budget": scale, "post_trade_security_value": scale*v,
        "cash_fee_paid": fee*scale*v, "base_horizon_wealth": 125*scale,
        "base_horizon_funding_gap": 125*(1-scale)}, "entry cash budget")
    near(scale*v + fee*scale*v, v, "security cost plus fee equals available cash")
    tree(hedge["changed_cash_flow_intervention"], {
        "long_payoff_fraction": F(9, 10), "base_horizon_wealth": F(475, 4),
        "base_horizon_surplus": F(-25, 4)}, "independent changed claim")
    groups.append("funded hedge and constant-rate, later-path, fee and claim ledgers")

    curve = out["key_rate_curve"]
    tree(curve["baseline_continuous_zeros"], [log(F(21, 20))]*3, "annual to continuous zero")
    # Hand-specified basis rows and matrix entries for the original contract.
    b = [[1, 0, 0], [F(1, 2), F(1, 2), 0], [0, 1, 0], [0, F(1, 2), F(1, 2)]]
    t1, t2, t3, t4 = expected_metrics["cash_flow_pvs"]
    kn = [t1+t2, t2+3*t3+2*t4, 2*t4]
    hn = [[t1+t2, t2, 0], [t2, t2+9*t3+4*t4, 4*t4], [0, 4*t4, 4*t4]]
    ka, kl = [v/2, 0, 5*v/2], [0, 3*v, 0]
    ha = [[v/2, 0, 0], [0, 0, 0], [0, 0, 25*v/2]]
    hl = [[0, 0, 0], [0, 9*v, 0], [0, 0, 0]]
    ks, hs = [v/2, -3*v, 5*v/2], [[v/2, 0, 0], [0, -9*v, 0], [0, 0, 25*v/2]]
    for name, price, rows, pvs, key, hessian in (
            ("note", p, b, [t1, t2, t3, t4], kn, hn),
            ("assets", v, [[1, 0, 0], [0, 0, 1]], [v/2, v/2], ka, ha),
            ("liability", v, [[0, 1, 0]], [v], kl, hl)):
        tree(curve[name], {"price": price, "basis_rows": rows, "cash_flow_pvs": pvs,
                          "dollar_key_durations": key, "key_durations": [x/price for x in key],
                          "dollar_hessian": hessian,
                          "continuous_parallel_dollar_duration": sum(key),
                          "continuous_parallel_dollar_convexity": sum(map(sum, hessian))}, "manual curve " + name)
    tree(curve["surplus_dollar_key_durations"], ks, "surplus key vector")
    tree(curve["surplus_dollar_hessian"], hs, "surplus Hessian")
    near(sum(kn)*d, k, "first annual/continuous chain rule")
    near((sum(map(sum, hn))+sum(kn))*d*d, g, "second annual/continuous chain rule")
    same(sum(ks), 0, "parallel neutrality")
    require(hs[1][1] < 0, "surplus Hessian is not PSD")
    for scenario, bump in zip(curve["scenarios"], ((.01, .01, .01), (-.01, 0, .01), (0, .01, 0))):
        u, w, z = bump
        pa = float(v)/2*(exp(-u)+exp(-5*z))
        pl = float(v)*exp(-3*w)
        pn = (float(t1)*exp(-u) + float(t2)*exp(-(u+w)) +
              float(t3)*exp(-3*w) + float(t4)*exp(-2*(w+z)))
        linear = -float(v)*(u/2-3*w+5*z/2)
        quadratic = linear + float(v)/2*(u*u/2-9*w*w+25*z*z/2)
        near(scenario["asset_price"], pa, "exact key asset reprice")
        near(scenario["liability_price"], pl, "exact key liability reprice")
        near(scenario["exact_note_price"], pn, "off-key note exponential reprice")
        near(scenario["exact_surplus"], pa-pl, "exact key surplus")
        near(scenario["linear_surplus"], linear, "key linear estimate")
        near(scenario["quadratic_surplus"], quadratic, "key quadratic estimate")
    # Separate mixed derivative finite difference of the coupon-note polynomial.
    step = 0.0001
    def manual_curve(u, w):
        return float(t1)*exp(-u)+float(t2)*exp(-(u+w))+float(t3)*exp(-3*w)+float(t4)*exp(-2*w)
    cross = (manual_curve(step, step)-manual_curve(step, -step)-
             manual_curve(-step, step)+manual_curve(-step, -step))/(4*step*step)
    near(cross, hn[0][1], "mixed derivative from prices", absolute=1e-6)
    groups.append("explicit key basis, Hessian, chain rule and exact twists")

    counter = out["local_counterexample"]
    cd = F(5, 4)
    tree(counter, {"asset_times": [1, 3], "asset_cash": [120, 320],
                   "liability_times": [2, 4], "liability_cash": [340, 100],
                   "initial_asset_pv": 440, "initial_liability_pv": 440,
                   "initial_surplus_first_derivative": 0, "initial_surplus_second_derivative": 40,
                   "stress_yield": F(-1, 5), "stress_discount_factor": cd,
                   "stress_asset_pv": 120*cd+320*cd**3,
                   "stress_liability_pv": 340*cd**2+100*cd**4,
                   "stress_surplus_direct": F(-25, 64), "stress_surplus_factored": F(-25, 64),
                   "negative_surplus_region": {"annual_yield_lower_exclusive": -1,
                                               "annual_yield_upper_exclusive": F(-1, 6)}}, "local-only polynomial")
    # Verify polynomial identity at distinct rational arguments, with its sign
    # implication supplied by the factor proof rather than inferred from tests.
    for cd in (F(9, 10), F(1), F(11, 10), F(6, 5), F(5, 4)):
        same(120*cd-340*cd**2+320*cd**3-100*cd**4,
             100*cd*(cd-1)**2*(F(6, 5)-cd), "counterexample factorization")
    groups.append("strict local theorem counterexample and exact failure boundary")

    # Every determinate exercise/retention anchor is independently recomputed;
    # proof and research-answer sufficiency also receives manuscript review.
    html = CHAPTER.read_text()
    parsed = Structure()
    parsed.feed(html)
    parsed.close()
    same(parsed.stack, [], "balanced fragment")
    text = " ".join("".join(parsed.text).split())
    q2 = F(103, 100)
    e1p = 100/q2**6
    for printed, exact in (("83.74842567", e1p), ("2.91262136", 3/q2),
                           ("9.89725705", F(21, 2)/q2**2), ("243.92745340", 3*e1p/q2),
                           ("0.02439275", 3*e1p/q2/10000), ("2.82778773", 3/q2**2)):
        require(printed in text, "E1 printed anchor " + printed)
        near(float(printed), exact, "E1 rounded anchor", absolute=5.01e-9)
    near(q2*q2-1, F(609, 10000), "E1 annual effective yield")
    near(3/q2, q2*(3/q2**2), "E1 coordinate derivative")
    near(F(103)*4, 412, "E3 dollar exposure")
    near(F(412, 100), F(103, 25), "E3 clean normalization")
    near(F(412, 400)-1, F(3, 100), "E3 loss understatement")
    e4exact = 100/F(6, 5)**10
    near(100-1000*F(1, 5), -100, "E4 linear price")
    near(-100+F(11000, 2)*F(1, 5)**2, 120, "E4 quadratic price")
    near(e4exact, 16.15055829, "E4 rounded exact price", absolute=5.01e-9)
    same(F(132000)*F(1, 5)**3/6, F(176), "E4 remainder bound")
    require(120-e4exact < 176, "E4 bound covers exact error")
    near(F(600, 240), F(5, 2), "E5 normalized duration")
    same(120*2+120*20-150*20, -360, "E5 surplus convexity")
    same(F(-360)*F(1, 100)**2/2, F(-18, 1000), "E5 surplus change")
    e6p = 100*exp(-.06)
    near(e6p, 94.17645336, "E6 printed price", absolute=5.01e-9)
    near(100*exp(-2*((.02+.01)/2+(.04-.01)/2)), e6p, "E6 exact offsetting bump")
    require(e6p > 0, "E6 rank-one PSD Hessian factor")
    same((-1)+2, 1, "E7 formal funding weights")
    same(2*(-1)+5*2, 8, "E7 formal duration")
    require(-1 < 0 and 5 < 8, "E7 long-only infeasibility witness")
    same(300*2+100*4, 100*1+300*3, "E8 first derivative match")
    same(300*6+100*20, 100*2+300*12, "E8 second derivative match")
    for cd in (F(10, 11), F(10, 9)):
        same(300*cd**2+100*cd**4-100*cd-300*cd**3,
             100*cd*(cd-1)**3, "E8 cubic factor")
    require(100*F(10, 11)*(F(10, 11)-1)**3 < 0, "E8 failure on upward yield side")
    near(F(12500, 101), 123.76237624, "E9 fee horizon wealth", absolute=5.01e-9)
    near(F(125, 101), 1.23762376, "E9 fee gap", absolute=5.01e-9)
    near(v/100, 1.07979700, "E9 contribution", absolute=5.01e-9)
    same(F(125, 2)*(1+F(4, 5)), F(225, 2), "E9 changed-claim wealth")
    near(2/F(26, 25), F(25, 13), "retention duration")
    near(6/F(26, 25)**2, F(3750, 676), "retention convexity")
    same(F(80*3, 100), F(12, 5), "retention funding-weighted duration")
    same(-(20*F(1, 100)+30*F(-1, 100)), F(1, 10), "retention signed twist")
    for required in ("continuity of S″", "strictly positive S″", "Full credit requires",
                     "predeclared information boundary", "not a rate forecast",
                     "No stochastic calculus is assumed", "liquidity"):
        require(required.lower() in text.lower(), "proof/interpretation clause: " + required)
    groups.append("ten exercise solutions and answered retention, with proof-scope clauses")

    # Economically different valid interventions; expected numbers come from
    # cash contracts, not the reference output used as an oracle.
    changed = deepcopy(data)
    changed["immunization"]["liability_amount"] = 250
    doubled = model.run(changed)
    tree(doubled["immunization"]["asset_zero_faces"], [2*f1, 2*f5], "double obligation faces")
    near(doubled["immunization"]["later_path_intervention"]["horizon_surplus"],
         2*(later-125), "double obligation funding gap")
    near(doubled["key_rate_curve"]["scenarios"][1]["exact_surplus"],
         float(v)*(exp(.01)+exp(-.05)-2), "double obligation twist")
    changed = deepcopy(data)
    changed["immunization"].update(entry_fee_rate=0, changed_long_payoff_fraction=1)
    restored = model.run(changed)["immunization"]
    near(restored["entry_fee_intervention"]["base_horizon_funding_gap"], 0, "zero fee restores budget")
    near(restored["changed_cash_flow_intervention"]["base_horizon_surplus"], 0, "full claim restores payoff")
    changed = deepcopy(data)
    changed["key_rate_curve"]["scenarios"][1]["bumps"] = [.01, 0, -.01]
    near(model.run(changed)["key_rate_curve"]["scenarios"][1]["exact_surplus"],
         float(v)*(exp(-.01)/2+exp(.05)/2-1), "reverse twist exact convex repricing")
    changed = deepcopy(data)
    changed["note"].update(times_years=[3], cash_flows=[100], frequency=2,
                           nominal_annual_yield=.06, accrued_interest=2)
    semi = model.run(changed)["note"]
    near(semi["dirty"]["price"], e1p, "actual semiannual edited lab")
    near(semi["dirty"]["convexity"], F(21, 2)/q2**2, "semiannual convexity")
    near(semi["clean_fractional_sensitivity"], 3*e1p/q2/(e1p-2), "edited accrual normalization")
    changed = deepcopy(data)
    changed["note"]["nominal_annual_yield"] = -.05
    negative = model.run(changed)["note"]["dirty"]
    dd = F(20, 19)
    near(negative["price"], 4*dd+4*dd**2+4*dd**3+104*dd**4, "negative admitted yield price")
    require(negative["dollar_convexity"] > 0, "positive convexity under negative yield")
    groups.append("bounded scale, funding, payoff, reverse-twist and quote interventions")

    invalids = [
        (("note", "frequency"), True, "bool frequency"),
        (("note", "cash_flows"), [-1, 4, 4, 104], "negative claim"),
        (("note", "cash_flows"), [0, 0, 0, 0], "zero price claim"),
        (("note", "cash_flows"), [4], "misaligned dates"),
        (("note", "times_years"), [1, 3, 2, 4], "unordered payments"),
        (("note", "times_years"), [1, 2.1, 3, 4], "off-period date"),
        (("note", "nominal_annual_yield"), -1, "zero base gross factor"),
        (("note", "nominal_annual_yield"), float("nan"), "nonfinite quote"),
        (("note", "yield_shifts"), [-1.05], "zero shocked gross factor"),
        (("note", "finite_difference_step"), 1.1, "FD crosses gross-factor boundary"),
        (("note", "accrued_interest"), 1000, "nonpositive clean price"),
        (("immunization", "liability_time"), 5, "unbracketed liability"),
        (("immunization", "later_long_sale_yield"), -1, "invalid later cash quote"),
        (("immunization", "entry_fee_rate"), -0.01, "negative fee"),
        (("immunization", "changed_long_payoff_fraction"), 1.1, "unsupported claim fraction"),
        (("key_rate_curve", "key_times"), [1, 3, 3], "duplicate curve nodes"),
        (("key_rate_curve", "key_times"), [2, 3, 5], "no extrapolation"),
        (("key_rate_curve", "convention"), "linear discounts", "changed coordinate"),
        (("local_counterexample", "discount_cutoff"), 1, "non-strict local curvature"),
        (("local_counterexample", "stress_yield"), -1, "counterexample gross factor"),
        (("contract",), "random cash flows", "changed financial contract"),
        (("schema_version",), True, "bool schema"),
    ]
    for path, value, label in invalids:
        bad = deepcopy(data)
        target = bad
        for part in path[:-1]:
            target = target[part]
        target[path[-1]] = value
        rejects(lambda b=bad: model.run(b), label)
    bad = deepcopy(data)
    bad["note"]["unmodeled_option"] = True
    rejects(lambda: model.run(bad), "unknown option field")
    bad = deepcopy(data)
    bad["key_rate_curve"]["scenarios"][1]["name"] = bad["key_rate_curve"]["scenarios"][0]["name"]
    rejects(lambda: model.run(bad), "duplicate scenario")
    bad = deepcopy(data)
    bad["key_rate_curve"]["scenarios"][1]["bumps"] = [.01]
    rejects(lambda: model.run(bad), "incomplete bump vector")
    rejects(lambda: json.loads('{"x":1,"x":2}', object_pairs_hook=model.unique_object), "duplicate JSON key")
    rejects(lambda: json.loads('{"x":NaN}', parse_constant=model.bad_constant), "nonfinite JSON token")
    groups.append("financial domain and exact schema rejection")

    same(parsed.worked, 4, "worked cases")
    same(parsed.exercises, 10, "graduate exercises")
    same(parsed.answers, 10, "full main solutions")
    same(parsed.details, 3, "solutions plus answered teaching and retention")
    same(len(parsed.ids), len(set(parsed.ids)), "unique chapter anchors")
    for i in range(1, 11):
        require("e"+str(i) in parsed.ids, "original exercise anchor")
    records = json.loads((ROOT / "content/reviews/v10-c02-sources.json").read_text())
    same([r["id"] for r in records], ["v10-c01-mit-fixed-income", "v10-c02-redington", "v10-c02-cfa-keyrates"], "scoped method sources")
    root_sources = json.loads((ROOT / "content/reviews/v10-c01-sources.json").read_text())
    same(records[0], root_sources[0], "exact shared MIT source reuse")
    for record in records:
        same(set(record), {"id", "title", "url", "use", "checked", "verification"}, "source metadata")
        require(record["url"].startswith("https://"), "primary source URL")
        require(record["verification"].startswith("Actual"), "actual-body inspection recorded")
    catalog_ids = {r["id"] for r in records}
    for href in parsed.hrefs:
        page, _, anchor = href.partition("#")
        require("/" not in page and not page.startswith("http"), "flat internal chapter link")
        if page == "sources.html":
            require(anchor in catalog_ids, "proposed source anchor resolves")
        elif page == "curriculum.html":
            same(anchor, "v10-c03", "successor curriculum route")
        elif page.endswith(".html"):
            require((ROOT / "content/chapters" / page).is_file(), "prerequisite manuscript exists")
        else:
            require((PROJECT / page).is_file(), "offline lab link exists")
    manifest = json.loads((PROJECT / "v10-c02-manifest.json").read_text())
    same({r["file"] for r in manifest["files"]},
         {"v10-c02-"+suffix for suffix in ("inputs.json", "analysis.py", "output.json", "README.txt")}, "four-file manifest scope")
    for record in manifest["files"]:
        payload = (PROJECT / record["file"]).read_bytes()
        same(len(payload), record["bytes"], "manifest bytes")
        same(hashlib.sha256(payload).hexdigest(), record["sha256"], "manifest hash")
    groups.append("balanced HTML, full solutions, flat links, sources and manifest")

    # Execute copied artifacts from an unrelated directory without repository
    # imports. No assertions in the model carry domain enforcement under -O.
    with tempfile.TemporaryDirectory(prefix="v10-c02-check-") as tmp:
        here = Path(tmp)
        files = here / "files"
        files.mkdir()
        for name in ("v10-c02-analysis.py", "v10-c02-inputs.json"):
            shutil.copy2(PROJECT / name, files / name)
        for flag in ([], ["-O"]):
            normal = subprocess.run([sys.executable, *flag, str(files / "v10-c02-analysis.py")],
                                    cwd=here, capture_output=True, text=True, check=False)
            same(normal.returncode, 0, "isolated CLI exit")
            same(normal.stderr, "", "isolated CLI stderr")
            tree(json.loads(normal.stdout), out, "isolated CLI complete output")
            (here / "edited.json").write_text(json.dumps(changed, allow_nan=False))
            output = here / "result.json"
            edited = subprocess.run([sys.executable, *flag, str(files / "v10-c02-analysis.py"),
                                     "--input", str(here / "edited.json"), "--output", str(output)],
                                    cwd=here, capture_output=True, text=True, check=False)
            same(edited.returncode, 0, "explicit CLI exit")
            same(edited.stdout, "", "output-file CLI quiet")
            same(edited.stderr, "", "output-file CLI stderr")
            tree(json.loads(output.read_text()), model.run(changed), "explicit edited CLI complete output")
            (here / "invalid.json").write_text('{"contract":0,"contract":1}')
            invalid = subprocess.run([sys.executable, *flag, str(files / "v10-c02-analysis.py"),
                                      "--input", str(here / "invalid.json")], cwd=here,
                                     capture_output=True, text=True, check=False)
            require(invalid.returncode != 0 and "Duplicate JSON key" in invalid.stderr,
                    "isolated strict JSON rejection also under optimization")
    groups.append("isolated normal and optimized default/edited CLI")
    result = {"chapter": "v10-c02", "passed": True, "groups": groups,
              "group_count": len(groups), "comparisons": comparisons, "rejections": rejections,
              "worked_examples": 4, "exercises": 10,
              "limits": "Comparisons include structural checks and complete repeated-output fields, not that many independent derivations. Proofs and open-answer adequacy also require manuscript review; no UI or real-market validation is claimed."}
    json.dumps(result, allow_nan=False)
    return result


if __name__ == "__main__":
    print(json.dumps(check(), ensure_ascii=False, indent=2, allow_nan=False))
