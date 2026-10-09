#!/usr/bin/env python3
"""Quiet independent checks for the original v10-c03 finite-rate chapter."""
import contextlib
import copy
from fractions import Fraction as F
import hashlib
from html.parser import HTMLParser
import importlib.util
import io
from itertools import product
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

BOOK = Path(__file__).resolve().parents[1]
PROJECT = BOOK / "content/projects"
PREFIX = "v10-c03"


def encode(value):
    if isinstance(value, F):
        return str(value)
    if isinstance(value, list):
        return [encode(x) for x in value]
    if isinstance(value, dict):
        return {k: encode(v) for k, v in value.items()}
    return value


class Audit:
    def __init__(self):
        self.count = 0
        self.groups = []
        self.start = 0

    def eq(self, actual, expected, label):
        if isinstance(expected, dict):
            if type(actual) is not dict or set(actual) != set(expected):
                raise ValueError(label + ": object keys differ")
            for key in expected:
                self.eq(actual[key], expected[key], label + "." + str(key))
        elif isinstance(expected, list):
            if type(actual) is not list or len(actual) != len(expected):
                raise ValueError(label + ": list shape differs")
            for i, value in enumerate(expected):
                self.eq(actual[i], value, label + "." + str(i))
        else:
            self.count += 1
            if type(actual) is not type(expected) or actual != expected:
                raise ValueError(f"{label}: got {actual!r}; expected {expected!r}")

    def require(self, condition, label):
        self.count += 1
        if not condition:
            raise ValueError(label)

    def group(self, title):
        self.groups.append({"name": title, "status": "passed", "comparisons": self.count - self.start})
        self.start = self.count


def oracle(data):
    """Use full path sums, not the author's Arrow or backward recursions."""
    D = list(map(F, data["discount_curve"]))
    q = [list(map(F, row)) for row in data["pricing_up"]]
    p = [list(map(F, row)) for row in data["physical_up"]]
    cf = list(map(F, data["cashflows"]))
    face, strike = F(data["claim"]["face"]), F(data["claim"]["strike"])

    def probability(bits, measure, start=0, node=0):
        result = F(1)
        j = node
        for t, b in enumerate(bits, start):
            result *= measure[t][j] if b else 1 - measure[t][j]
            j += b
        return result

    def discounted_path(bits, discounts, start=0, node=0):
        result = F(1)
        j = node
        for t, b in enumerate(bits, start):
            result *= discounts[t][j]
            j += b
        return result

    def tree(curve, s):
        discounts, levels = [], []
        for t in range(3):
            denominator = F(0)
            for bits in product((0, 1), repeat=t):
                weight = probability(bits, q) * discounted_path(bits, discounts)
                denominator += weight * (1 + s * (t - 2 * sum(bits)))
            level = curve[t + 1] / denominator
            levels.append(level)
            discounts.append([level * (1 + s * (t - 2 * j)) for j in range(t + 1)])

        def z(t, j, T):
            return sum((probability(bits, q, t, j) * discounted_path(bits, discounts, t, j)
                        for bits in product((0, 1), repeat=T - t)), F(0))

        def node_rows(kind):
            rows = []
            for t in range(4):
                row = []
                for j in range(t + 1):
                    total = F(0)
                    for bits in product((0, 1), repeat=t):
                        if sum(bits) == j:
                            total += probability(bits, p if kind == "P" else q) * (discounted_path(bits, discounts) if kind == "Arrow" else 1)
                    row.append(total)
                rows.append(row)
            return rows

        zeros = {str(T): [[z(t, j, T) for j in range(t + 1)] for t in range(T + 1)] for T in range(1, 4)}
        coupon = [[sum((cf[T - 1] * z(t, j, T) for T in range(t + 1, 4)), F(0)) for j in range(t + 1)] for t in range(4)]
        B = [z(1, j, 2) for j in range(2)]
        payments = [max(face * b - strike, F(0)) for b in B]
        price = sum((probability((j,), q) * discounted_path((j,), discounts) * payments[j] for j in (0, 1)), F(0))
        beta = (payments[0] - payments[1]) / (B[0] - B[1]) if B[0] != B[1] else F(0)
        cash = price - beta * curve[2]
        replica = [beta * b + cash / curve[1] for b in B]
        arrows = node_rows("Arrow")
        premiums = []
        for t in range(2):
            for j in range(t + 1):
                buy = z(t, j, t + 2)
                gross = [z(t + 1, j + b, t + 2) / buy for b in (0, 1)]
                pb = [1 - p[t][j], p[t][j]]
                qb = [1 - q[t][j], q[t][j]]
                d = discounts[t][j]
                m = [d * qb[b] / pb[b] for b in (0, 1)]
                mean = sum(pb[b] * gross[b] for b in (0, 1))
                mean_m = sum(pb[b] * m[b] for b in (0, 1))
                cov = sum(pb[b] * (m[b] - mean_m) * (gross[b] - mean) for b in (0, 1))
                premiums.append({"time": t, "node": j, "bond_maturity": t + 2, "bond_price": buy,
                                 "branch_gross_returns": gross, "physical_expected_simple_return": mean - 1,
                                 "risk_free_simple_rate": 1 / d - 1, "expected_excess_return": mean - 1 / d,
                                 "local_P_sdf": m, "sdf_return_covariance": cov})
        paths = []
        for bits in product((0, 1), repeat=3):
            qp, pp = probability(bits, q), probability(bits, p)
            df = discounted_path(bits, discounts)
            paths.append({"path": "".join("H" if b else "L" for b in bits), "terminal_node": sum(bits),
                          "Q_probability": qp, "P_probability": pp, "discount_product": df,
                          "bank_history": [1 / discounted_path(bits[:t], discounts) for t in range(4)],
                          "state_price": qp * df, "P_sdf": qp * df / pp})
        rates = [1 / discounts[1][j] - 1 for j in range(2)]
        eq = (1 - q[0][0]) * rates[0] + q[0][0] * rates[1]
        ep = (1 - p[0][0]) * rates[0] + p[0][0] * rates[1]
        forward = curve[1] / curve[2] - 1
        return {"dispersion": s, "levels": levels, "node_discounts": discounts,
                "short_rates": [[1 / d - 1 for d in row] for row in discounts], "arrow_weights": arrows,
                "discount_sums": [sum(row) for row in arrows], "Q_node_probabilities": node_rows("Q"),
                "P_node_probabilities": node_rows("P"), "zero_prices": zeros,
                "coupon_ex_payment_values": coupon, "coupon_curve_price": sum(cf[i] * curve[i + 1] for i in range(3)),
                "claim": {"branch_payoffs": payments, "price": price, "hedge_units_face1_zero2": beta,
                          "hedge_cash_at0": cash, "hedge_initial_cost": beta * curve[2] + cash,
                          "hedge_branch_payoffs": replica,
                          "hedge_rank": "two distinct successor bond values" if B[0] != B[1] else "redundant bond; bank-only replica chosen"},
                "forward_vs_expectations": {"forward_1_2": forward, "Q_expected_short1": eq, "P_expected_short1": ep,
                                            "forward_minus_Q": forward - eq, "Q_minus_P": eq - ep, "forward_minus_P": forward - ep},
                "holding_premiums": premiums, "terminal_paths": paths}

    models = {spec["name"]: tree(D, F(spec["dispersion"])) for spec in data["models"]}
    base = models["base"]
    h = base["claim"]
    errors = {}
    for key, m in models.items():
        cash = [h["hedge_units_face1_zero2"] * b + h["hedge_cash_at0"] / D[1] for b in m["zero_prices"]["2"][1]]
        err = [a - b for a, b in zip(cash, m["claim"]["branch_payoffs"])]
        errors[key] = {"frozen_base_hedge_payoffs": cash, "claim_payoffs": m["claim"]["branch_payoffs"],
                       "branch_errors": err, "priced_error": D[1] * ((1 - q[0][0]) * err[0] + q[0][0] * err[1]),
                       "base_price_minus_model_price": h["price"] - m["claim"]["price"]}
    scenarios = {}
    for spec in data["curve_scenarios"]:
        ds = list(map(F, spec["discount_curve"]))
        m = tree(ds, F(data["models"][0]["dispersion"]))
        scenarios[spec["name"]] = {"discount_curve": ds, "node_discounts": m["node_discounts"],
                                   "discount_sums": m["discount_sums"], "coupon_price": m["coupon_curve_price"],
                                   "coupon_change": m["coupon_curve_price"] - base["coupon_curve_price"],
                                   "claim_price": m["claim"]["price"], "claim_change": m["claim"]["price"] - h["price"]}
    ar = data["mean_reversion"]
    r0, theta, phi, sigma = [F(ar[k]) for k in ("initial", "level", "phi", "innovation")]
    n = ar["steps"]
    paths = []
    for signs in product((-1, 1), repeat=n):
        rates = [theta + phi**t * (r0 - theta) + sigma * sum((phi**(t - 1 - k) * signs[k] for k in range(t)), F(0)) for t in range(n + 1)]
        paths.append({"shocks": list(signs), "rates": rates})
    mean = sum(x["rates"][-1] for x in paths) / len(paths)
    var = sum((x["rates"][-1] - mean)**2 for x in paths) / len(paths)
    return encode({"schema": data["schema"], "contract": data["contract"], "models": models,
                   "frozen_base_hedge_model_risk": errors, "curve_scenarios": scenarios,
                   "mean_reversion": {"contract": "separate physical model; independent equiprobable +/- innovations; not curve calibrated",
                                      "terminal_mean": mean, "terminal_variance": var,
                                      "analytic_mean": theta + phi**n * (r0 - theta),
                                      "analytic_variance": sigma**2 * (1 - phi**(2*n)) / (1 - phi**2), "paths": paths}})


class Fragment(HTMLParser):
    def __init__(self):
        super().__init__()
        self.worked = self.exercises = self.solutions = self.h1 = 0
        self.solution_depth = 0
        self.lists = []
        self.ids, self.sources, self.hrefs = [], set(), set()

    def handle_starttag(self, tag, pairs):
        attrs = dict(pairs)
        classes = attrs.get("class", "").split()
        if "id" in attrs:
            self.ids.append(attrs["id"])
        if "data-source" in attrs:
            self.sources.add(attrs["data-source"])
        if "href" in attrs:
            self.hrefs.add(attrs["href"])
        if tag == "h1":
            self.h1 += 1
        if tag == "aside" and "worked" in classes:
            self.worked += 1
        if tag == "details" and "solutions" in classes:
            self.solution_depth += 1
        if tag == "ol":
            self.lists.append("exercises" if "exercises" in classes else "solutions" if self.solution_depth else "other")
        if tag == "li" and self.lists:
            if self.lists[-1] == "exercises":
                self.exercises += 1
            elif self.lists[-1] == "solutions":
                self.solutions += 1

    def handle_endtag(self, tag):
        if tag == "ol" and self.lists:
            self.lists.pop()
        if tag == "details" and self.solution_depth:
            self.solution_depth -= 1


def check():
    audit = Audit()
    data = json.loads((PROJECT / (PREFIX + "-inputs.json")).read_text())
    saved = json.loads((PROJECT / (PREFIX + "-output.json")).read_text())
    before = copy.deepcopy(data)
    capture_out, capture_err = io.StringIO(), io.StringIO()
    sys.dont_write_bytecode = True
    with contextlib.redirect_stdout(capture_out), contextlib.redirect_stderr(capture_err):
        spec = importlib.util.spec_from_file_location("v10_c03_reviewed_analysis", PROJECT / (PREFIX + "-analysis.py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        actual = module.run(data)
    audit.eq(capture_out.getvalue(), "", "quiet stdout")
    audit.eq(capture_err.getvalue(), "", "quiet stderr")
    audit.eq(data, before, "input preserved")
    json.dumps(actual, allow_nan=False)
    audit.eq(actual, saved, "complete preserved reference")
    audit.eq(actual, oracle(data), "independent full path oracle")
    audit.group("Quiet API, complete saved output and independent path enumeration")

    base = actual["models"]["base"]
    audit.eq(base["levels"], ["49/50", "95/98", "45500/47519"], "worked1 levels")
    audit.eq(base["arrow_weights"][2], ["969/4000", "19/40", "931/4000"], "worked1 Arrow row")
    audit.eq(sum(F(a) * h for a, h in zip(base["arrow_weights"][2], [F(26,25),F(1),F(24,25)])), F(47519,50000), "exercise1 denominator")
    audit.eq(3*F(49,50)+3*F(19,20)+103*F(91,100), F(2488,25), "exercise1 alternate bond")
    paths = {x["path"]: x for x in base["terminal_paths"]}
    audit.eq(paths["LHL"]["bank_history"][2], "1000/969", "exercise2 LH bank")
    audit.eq(paths["HLL"]["bank_history"][2], "1000/931", "exercise2 HL bank")
    audit.eq(F(969,4000)/(F(969,4000)+F(931,4000)), F(51,100), "exercise2 middle price weight")
    audit.eq(F(969,4000)/F(19,20), F(51,200), "exercise2 normalized Arrow")
    audit.eq(base["Q_node_probabilities"][2], ["1/4", "1/2", "1/4"], "exercise2 Q weights")
    audit.eq(base["forward_vs_expectations"], {"forward_1_2":"3/95","Q_expected_short1":"31/969","P_expected_short1":"13/323","forward_minus_Q":"-2/4845","Q_minus_P":"-8/969","forward_minus_P":"-14/1615"}, "worked2 means and decomposition")
    audit.eq([x["expected_excess_return"] for x in base["holding_premiums"]], ["-2/245", "196/49419", "-12/931"], "worked2 dated premiums")
    audit.eq(base["holding_premiums"][0]["sdf_return_covariance"], "1/125", "worked2 covariance")
    for m in actual["models"].values():
        for row in m["holding_premiums"]:
            d = F(m["node_discounts"][row["time"]][row["node"]])
            audit.eq(F(row["expected_excess_return"]), -F(row["sdf_return_covariance"])/d, "local covariance identity")
        audit.eq(m["discount_sums"], data["discount_curve"], "all model fits")
        for row in m["terminal_paths"]:
            audit.require(F(row["Q_probability"]) > 0 and F(row["P_probability"]) > 0 and F(row["state_price"]) > 0, "proof4 support")
            audit.eq(F(row["state_price"]), F(row["Q_probability"])/F(row["bank_history"][-1]), "proof4 numeraire path")
            audit.eq(F(row["state_price"]), F(row["P_probability"])*F(row["P_sdf"]), "proof4 P representation")
        audit.eq(sum(F(row["state_price"]) for row in m["terminal_paths"]), F(91,100), "proof4 path price of unit")
    audit.eq([actual["models"][k]["claim"]["price"] for k in ("base","deterministic","wide")], ["141/100","23/25","59/25"], "exercise6 constructive identification counterexample")
    audit.eq(actual["frozen_base_hedge_model_risk"]["wide"]["branch_errors"], ["-1/2","-141/98"], "worked3 model error")
    audit.eq(actual["frozen_base_hedge_model_risk"]["wide"]["priced_error"], "-19/20", "worked3 error funding")
    audit.eq(actual["curve_scenarios"]["lower_D2"]["claim_price"], "9/10", "worked4 D2 claim")
    audit.eq(actual["curve_scenarios"]["lower_D3"]["coupon_price"], "4187/40", "worked4 D3 coupon")
    audit.eq(F(96)*F(49,50)/(100*F(51,50)), F(392,425), "exercise7 low boundary")
    audit.eq(F(96)*F(49,50)/(100*F(49,50)), F(24,25), "exercise7 high boundary")
    audit.eq(F(141,100)+51*(F(23,25)-F(19,20)), -F(3,25), "exercise7 invalid linear extrapolation")
    audit.eq(actual["mean_reversion"]["terminal_mean"], "7/200", "exercise8 mean")
    audit.eq(actual["mean_reversion"]["terminal_variance"], "1/8000", "exercise8 variance")
    audit.eq([r["rates"][-1] for r in actual["mean_reversion"]["paths"]], ["1/50","1/25","3/100","1/20"], "exercise8 support")
    audit.eq(1/F(247,245)-1, -F(2,247), "exercise9 negative rate")
    audit.eq(F(1)-F(245,247), F(2,247), "exercise9 storage arbitrage")
    drift = F(25,10000)+F(1,5)*(F(3,100)-F(25,10000))
    shock = F(3,10)*F(1,20)
    audit.eq([drift-shock, drift+shock], [-F(7,1000),F(23,1000)], "exercise9 square root step")
    audit.eq((drift+shock)/2-drift, F(7,2000), "exercise9 clamp changes mean")
    audit.group("All determinate worked/exercise anchors, path pricing identities and proof assumptions")

    variants = []
    def variation(title, fields):
        x = copy.deepcopy(data)
        for path, value in fields:
            here = x
            for key in path[:-1]:
                here = here[key]
            here[path[-1]] = value
        with contextlib.redirect_stdout(capture_out), contextlib.redirect_stderr(capture_err):
            result = module.run(x)
        audit.eq(result, oracle(x), "variant " + title)
        variants.append(title)
        return x, result

    _, physical = variation("physical law only", [(["physical_up",0,0], "3/10")])
    for key in ("levels","node_discounts","arrow_weights","zero_prices","coupon_ex_payment_values","claim"):
        audit.eq(physical["models"]["base"][key], base[key], "P-only price invariance " + key)
    audit.eq(physical["models"]["base"]["forward_vs_expectations"]["P_expected_short1"], "23/969", "exercise3 changed forecast")
    audit.eq(physical["models"]["base"]["holding_premiums"][0]["physical_expected_simple_return"], "1/35", "exercise3 expected return")
    audit.eq(physical["models"]["base"]["holding_premiums"][0]["expected_excess_return"], "2/245", "exercise3 risk premium")
    _, equal = variation("root P equals Q", [(["physical_up",0,0], "1/2")])
    audit.eq(equal["models"]["base"]["holding_premiums"][0]["expected_excess_return"], "0", "retention pure return premium")
    audit.eq(equal["models"]["base"]["forward_vs_expectations"]["forward_minus_P"], "-2/4845", "retention nonlinear averaging remains")
    variation("changed conditional Q with refit", [(["pricing_up"], [["3/5"],["3/10","7/10"],["1/4","1/2","3/4"]])])
    strike_data, strike = variation("strike97 replication", [(["claim","strike"], "97")])
    audit.eq(strike["models"]["base"]["claim"]["branch_payoffs"], ["92/49","0"], "exercise5 payoff")
    audit.eq(strike["models"]["base"]["claim"]["hedge_units_face1_zero2"], "920/19", "exercise5 units")
    audit.eq(strike["models"]["base"]["claim"]["hedge_cash_at0"], "-1127/25", "exercise5 borrowing")
    _, all_positive = variation("both branches pay", [(["claim","strike"], "0")])
    audit.eq(all_positive["models"]["base"]["claim"]["hedge_units_face1_zero2"], "100", "zero-strike full bond hedge")
    _, no_pay = variation("no branch pays", [(["claim","strike"], "150")])
    audit.eq(no_pay["models"]["base"]["claim"]["price"], "0", "zero claim price")
    _, kink = variation("large D2 move crosses kink", [(["discount_curve",2], "23/25")])
    audit.eq(kink["models"]["base"]["claim"]["price"], "0", "exercise7 exact max price")
    audit.eq(kink["models"]["base"]["coupon_curve_price"], "2101/20", "exercise7 bond price")
    _, increasing = variation("increasing discount curve", [(["discount_curve"], ["1","101/100","103/100","26/25"])])
    audit.require(all(F(x)<0 for row in increasing["models"]["deterministic"]["short_rates"] for x in row), "positive-rate restriction is not imposed")
    _, no_ar_noise = variation("physical zero-persistence zero-noise boundary", [(["mean_reversion","phi"], "0"),(["mean_reversion","innovation"], "0")])
    audit.eq(no_ar_noise["mean_reversion"]["terminal_variance"], "0", "degenerate physical variance")
    _, retained = variation("date3 retention bump", [(["discount_curve",3], "9/10")])
    audit.eq(retained["models"]["base"]["coupon_curve_price"], "2083/20", "retention fixed bond104.15")
    audit.eq(retained["models"]["base"]["claim"]["price"], "141/100", "retention unchanged date1 claim")
    audit.eq(capture_out.getvalue(), "", "all intervention calls quiet stdout")
    audit.eq(capture_err.getvalue(), "", "all intervention calls quiet stderr")
    audit.group("Ten meaningful probability, payoff, curve and physical-dynamics interventions")

    bad = [
        ("unknown schema", ["schema"], "unsupported"),
        ("changed date", ["contract","dates_years"], [0,1,2,4]),
        ("boolean date", ["contract","dates_years"], [False,1,2,3]),
        ("outside storage", ["contract","outside_storage"], "free storage"),
        ("zero discount", ["discount_curve",2], "0"),
        ("wrong D0", ["discount_curve",0], "99/100"),
        ("boolean number", ["discount_curve",1], True),
        ("bare float", ["discount_curve",1], 0.98),
        ("NaN API value", ["discount_curve",1], float("nan")),
        ("zero denominator", ["discount_curve",1], "1/0"),
        ("too large denominator", ["discount_curve",1], "1/1000000000001"),
        ("zero Q support", ["pricing_up",0,0], "0"),
        ("unit Q support", ["pricing_up",1,0], "1"),
        ("zero P support", ["physical_up",2,2], "0"),
        ("ragged probabilities", ["physical_up",1], ["1/2"]),
        ("negative dispersion", ["models",0,"dispersion"], "-1/100"),
        ("zero shape", ["models",0,"dispersion"], "1/2"),
        ("missing base", ["models",0,"name"], "renamed"),
        ("duplicate model", ["models",1,"name"], "base"),
        ("empty models", ["models"], []),
        ("negative coupon", ["cashflows",0], "-1"),
        ("no cashflow", ["cashflows"], ["0","0","0"]),
        ("zero face", ["claim","face"], "0"),
        ("negative strike", ["claim","strike"], "-1"),
        ("changed claim date", ["claim","payment_time"], 2),
        ("boolean claim date", ["claim","payment_time"], True),
        ("invalid scenario curve", ["curve_scenarios",0,"discount_curve",3], "0"),
        ("duplicate curve scenario", ["curve_scenarios",1,"name"], "lower_D2"),
        ("non-reverting phi", ["mean_reversion","phi"], "1"),
        ("negative innovation", ["mean_reversion","innovation"], "-1/100"),
        ("nonpositive initial gross", ["mean_reversion","initial"], "-1"),
        ("invalid future gross", ["mean_reversion","level"], "-3"),
        ("float steps", ["mean_reversion","steps"], 2.0),
        ("zero steps", ["mean_reversion","steps"], 0),
    ]
    for title, path, value in bad:
        x = copy.deepcopy(data)
        node = x
        for key in path[:-1]:
            node = node[key]
        node[path[-1]] = value
        try:
            module.run(x)
        except ValueError:
            audit.require(True, title)
        else:
            raise ValueError("invalid contract accepted: " + title)
    for title, mutation in (("unknown field", lambda x: x.update({"unmodeled_fee":"1"})),
                            ("missing field", lambda x: x.pop("physical_up"))):
        x = copy.deepcopy(data)
        mutation(x)
        try:
            module.run(x)
        except ValueError:
            audit.require(True, title)
        else:
            raise ValueError("invalid contract accepted: " + title)
    audit.group("36 actual time, probability, numerical and economic domain rejections")

    fragment = (BOOK / "content/chapters/v10-c03.html").read_text()
    parsed = Fragment()
    parsed.feed(fragment)
    audit.eq([parsed.worked,parsed.exercises,parsed.solutions,parsed.h1], [4,10,10,0], "graduate package structure")
    audit.eq(len(set(parsed.ids)), len(parsed.ids), "unique fragment anchors")
    for anchor in ("objective","calibration","physical-risk","families","model-risk","exercises","teach-back","scope"):
        audit.require(anchor in parsed.ids, "required teaching component " + anchor)
    sources = json.loads((BOOK / "content/reviews/v10-c03-sources.json").read_text())
    ids = {s["id"] for s in sources}
    audit.eq(ids, {"v09-c05-princeton-pricing","v10-c03-haugh-lattice","v10-c03-fed-premium"}, "scoped source IDs")
    audit.require(parsed.sources <= ids, "all paragraph citations have proposed/accepted records")
    canonical = json.loads((BOOK / "content/sources.json").read_text())
    reuse = next(x for x in canonical if x["id"] == "v09-c05-princeton-pricing")
    audit.eq(next(x for x in sources if x["id"] == reuse["id"]), reuse, "stable source record reused exactly")
    for source in sources:
        audit.require(set(source) == {"id","title","url","use","checked","verification"} and bool(source["verification"]), "complete source proposal " + source["id"])
    for suffix in ("inputs.json","analysis.py","output.json","manifest.json","README.txt"):
        audit.require(PREFIX + "-" + suffix in parsed.hrefs, "download route " + suffix)
    for href in ("v10-c01.html","v10-c02.html","curriculum.html#v10-c04","curriculum.html#v10-c06","curriculum.html#v10-c07","v09-c05.html"):
        audit.require(href in parsed.hrefs, "prerequisite/extension route " + href)
    manifest = json.loads((PROJECT / (PREFIX + "-manifest.json")).read_text())
    audit.eq(manifest["case_id"], "v10-c03-finite-tree-v1", "manifest case")
    names = [PREFIX+"-"+s for s in ("inputs.json","analysis.py","output.json","README.txt")]
    audit.eq([x["file"] for x in manifest["files"]], names, "four-file payload manifest")
    for entry in manifest["files"]:
        payload = (PROJECT / entry["file"]).read_bytes()
        audit.eq(entry["bytes"], len(payload), "manifest bytes " + entry["file"])
        audit.eq(entry["sha256"], hashlib.sha256(payload).hexdigest(), "manifest hash " + entry["file"])
    audit.group("Chapter structure, scoped source records, exact routes and payload integrity")

    with tempfile.TemporaryDirectory(prefix="v10-c03-check-") as temp:
        folder = Path(temp)
        isolated, cwd = folder/"isolated", folder/"other-working-directory"
        isolated.mkdir(); cwd.mkdir()
        script = isolated / (PREFIX + "-analysis.py")
        for file in names:
            (isolated/file).write_bytes((PROJECT/file).read_bytes())
        env = dict(os.environ)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        def cli(args):
            return subprocess.run([sys.executable,"-I","-B"]+args, cwd=cwd, env=env, capture_output=True, text=True, timeout=20)
        normal = cli([str(script)])
        audit.eq(normal.returncode, 0, "isolated default-input CLI success")
        audit.eq(normal.stderr, "", "isolated CLI stderr")
        audit.eq(json.loads(normal.stdout), saved, "isolated complete output")
        changed = cwd/"changed-input.json"
        changed.write_text(json.dumps(strike_data))
        output = cwd/"result.json"
        optimized = cli(["-O",str(script),"--input",str(changed),"--output",str(output)])
        audit.eq(optimized.returncode, 0, "optimized explicit-input/output CLI success")
        audit.eq(optimized.stdout, "", "optimized output mode stdout")
        audit.eq(optimized.stderr, "", "optimized output mode stderr")
        audit.eq(json.loads(output.read_text()), strike, "optimized modified case output")
        for label, content in (("duplicate fields",'{"schema":"x","schema":"y"}'),("nonfinite token",'{"value":NaN}')):
            wrong = cwd/"wrong.json"
            wrong.write_text(content)
            result = cli(["-O",str(script),"--input",str(wrong)])
            audit.require(result.returncode != 0 and result.stdout == "", "CLI rejects " + label)
    audit.group("Isolated default and optimized explicit CLI; strict JSON parser")
    return {"chapter":"v10-c03","status":"passed","groups":audit.groups,
            "comparisons":audit.count,"valid_interventions":len(variants),"domain_rejections":len(bad)+4,
            "worked_examples":4,"solved_exercises":10,
            "limits":"Finite arithmetic/domain/structure checks plus recorded editorial proof review; not empirical calibration validation or external certification."}


if __name__ == "__main__":
    print(json.dumps(check(), indent=2, allow_nan=False))
