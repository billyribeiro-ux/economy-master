"""Independent finite-state pricing, cash-flow and package checks for v09-c05."""
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
from fractions import Fraction as F
import hashlib
from html.parser import HTMLParser
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PROJECTS = ROOT / "content/projects"


class Structure(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids, self.hrefs = [], []
        self.worked = self.solutions = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "id" in a:
            self.ids.append(a["id"])
        if "href" in a:
            self.hrefs.append(a["href"])
        self.worked += "worked" in a.get("class", "").split()
        self.solutions += tag == "details" and "solutions" in a.get("class", "").split()


def check():
    comparisons = 0
    rejections = 0
    groups = []

    def eq(actual, expected, label):
        nonlocal comparisons
        comparisons += 1
        if actual != expected:
            raise AssertionError(f"{label}: {actual!r} != {expected!r}")

    def yes(value, label):
        eq(bool(value), True, label)

    def vec(v):
        return [F(x) for x in v]

    def dot(x, y):
        return sum((a*b for a, b in zip(x, y)), F(0))

    def mean(p, x):
        return dot(p, x)

    def cov(p, x, y):
        return mean(p, [a*b for a, b in zip(x, y)])-mean(p, x)*mean(p, y)

    sink = io.StringIO()
    with redirect_stdout(sink), redirect_stderr(sink):
        spec = importlib.util.spec_from_file_location("v09_c05_aster", PROJECTS / "v09-c05-analysis.py")
        model = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(model)
        data = json.loads((PROJECTS / "v09-c05-inputs.json").read_text())
        result = model.run(data)
    eq(sink.getvalue(), "", "quiet module and run")
    json.dumps(result, allow_nan=False)

    # Independent interpolation formulas and exact dated portfolio reconciliation.
    def audit(d, r):
        stock, claim = vec(d["stock_payoffs"]), vec(d["claim_payoffs"])
        b, ps, pc = [F(d[k]) for k in ("bond_price", "stock_price", "call_price")]
        gap = stock[1]-stock[0]
        prices = [b, ps, pc]
        x = [[F(1), s, max(s-stock[1], F(0))] for s in stock]
        complete = r["complete_market"]
        q = vec(complete["state_prices"])
        for j in range(3):
            eq(dot(q, [row[j] for row in x]), prices[j], "state prices reconcile quote")
        yes(min(q) > 0, "strict positive base state prices")
        eq(F(complete["payoff_determinant"]), gap*gap, "determinant by row subtraction")
        stock_units = (claim[1]-claim[0])/gap
        bond_units = claim[0]-stock[0]*stock_units
        call_units = (claim[2]-2*claim[1]+claim[0])/gap
        h = [bond_units, stock_units, call_units]
        eq(vec(complete["claim_replication_asset_units"]), h, "independent interpolation")
        eq([dot(row, h) for row in x], claim, "replica every state")
        fair = dot(prices, h)
        eq(F(complete["claim_price"]), fair, "replica price")
        eq(dot(q, claim), fair, "dual price")
        for j, arrow in enumerate(complete["arrow_replication_asset_units"]):
            ah = vec(arrow)
            eq([dot(row, ah) for row in x], [F(i == j) for i in range(3)], "Arrow replication")
            eq(dot(prices, ah), q[j], "Arrow price")
        trade = complete["quote_experiment"]
        rh, unit = vec(trade["replica_asset_units"]), F(trade["quoted_claim_units"])
        rh[0] += F(trade["additional_bond_units"])
        eq(dot(prices, rh)+unit*F(d["claim_quote"]), F(0), "claim trade initial budget")
        terminal = [dot(row, rh)+unit*z for row, z in zip(x, claim)]
        eq(terminal, vec(trade["terminal_payoffs"]), "claim trade dated payoffs")
        eq(trade["arbitrage"], F(d["claim_quote"]) != fair, "quote discrepancy sign")
        yes(min(terminal) >= 0, "claim trade nonnegative outcomes")
        for diag in complete["call_quote_diagnostics"]:
            dq = vec(diag["state_prices"])
            dp = [b, ps, F(diag["call_quote"])]
            eq([dot(dq, [row[j] for row in x]) for j in range(3)], dp, "diagnostic prices")
            eq(diag["no_arbitrage"], min(dq) > 0, "complete unique sign test")
            if diag["certificate"]:
                cert = diag["certificate"]
                ch = vec(cert["asset_units_after_banking"])
                eq(dot(dp, ch), F(0), "diagnostic initial budget")
                pay = [dot(row, ch) for row in x]
                eq(pay, vec(cert["terminal_payoffs"]), "diagnostic cash flows")
                yes(min(pay) >= 0 and max(pay) > 0, "diagnostic arbitrage")
        inc = r["incomplete_bond_stock_market"]
        sub, sup = vec(inc["subhedge_bond_stock_units"]), vec(inc["superhedge_bond_stock_units"])
        hp = [F(0), F(0), F(1)]
        subp, supp = [[h[0]+h[1]*s for s in stock] for h in (sub, sup)]
        yes(all(l <= z <= u for l, z, u in zip(subp, hp, supp)), "hedge inequalities")
        lower, upper = F(inc["digital_price_lower_strict"]), F(inc["digital_price_upper_strict"])
        eq(dot([b, ps], sub), lower, "subhedge budget")
        eq(dot([b, ps], sup), upper, "superhedge budget")
        for ex in inc["listed_digital_experiments"]:
            price, sq = F(ex["digital_quote"]), vec(ex["state_prices_after_listing"])
            eq(sum(sq), b, "incomplete extension bond")
            eq(dot(sq, stock), ps, "incomplete extension stock")
            eq(sq[2], price, "incomplete extension digital")
            eq(ex["no_arbitrage"], min(sq) > 0, "listed digital positive extension")
            if ex["certificate"]:
                ch = vec(ex["certificate"]["bond_stock_units"])
                unit = F(ex["certificate"]["digital_units"])
                eq(dot([b, ps], ch)+unit*price, F(0), "digital initial budget")
                pay = [ch[0]+ch[1]*s+unit*z for s, z in zip(stock, hp)]
                eq(pay, vec(ex["certificate"]["terminal_payoffs"]), "digital terminal cash flows")
                yes(min(pay) >= 0 and max(pay) > 0, "digital arbitrage certificate")
        for key, pkey in (("physical_pricing", "physical_probabilities"),
                          ("alternative_physical_pricing", "alternative_probabilities")):
            p, s = vec(d[pkey]), r[key]
            m, g = vec(s["discount_factor"]), [v/ps for v in stock]
            eq([p[i]*m[i] for i in range(3)], q, "density reconstructs state prices")
            em, eg = mean(p, m), mean(p, g)
            vm, vg, cv = cov(p, m, m), cov(p, g, g), cov(p, m, g)
            for field, value in {
                "mean_discount_factor": em, "variance_discount_factor": vm,
                "stock_expected_payoff": mean(p, stock), "stock_expected_gross_return": eg,
                "stock_expected_simple_return": eg-1, "stock_expected_excess_return": eg-1/b,
                "stock_return_variance": vg, "discount_return_covariance": cv,
                "stock_sharpe_squared": (eg-1/b)**2/vg,
                "sdf_bound_squared": vm/em**2, "cauchy_gap": vm*vg-cv*cv,
            }.items():
                eq(F(s[field]), value, field)
            eq(eg-1/b, -cv/em, "pricing premium identity")
            yes(vm*vg-cv*cv >= 0, "Cauchy bound")
            eq(vec(s["risk_neutral_probabilities"]), [v/b for v in q], "normalized pricing probability")
            eq(vec(s["fundamental_prices"]), prices, "all fundamental prices")
            frontier, fh = vec(s["bound_attaining_payoff"]), vec(s["bound_attaining_asset_units"])
            eq([dot(row, fh) for row in x], frontier, "bound payoff actual replica")
            eq(dot(prices, fh), F(1), "bound payoff cost")
            eq(dot(q, frontier), F(1), "bound payoff pricing equation")
            eq(mean(p, frontier)-1/b, vm/em, "bound payoff premium")
            eq(cov(p, frontier, frontier), vm, "bound payoff variance")
        u = r["log_utility_euler"]
        cf = vec(u["future_consumption"])
        mrs = [F(d["utility_discount"])*F(d["current_consumption"])/c for c in cf]
        eq(mrs, vec(r["physical_pricing"]["discount_factor"]), "constructed log Euler kernel")
        eq(F(u["claim_price"]), fair, "Euler claim price")
        eq(F(u["claim_quote_utility_derivative_at_zero_trade"]), (fair-F(d["claim_quote"]))/F(d["current_consumption"]), "Euler quote derivative")

    audit(data, result)
    groups.append("Independent interpolation, state-price duality and every dated arbitrage certificate")
    p = result["physical_pricing"]
    eq(vec(result["complete_market"]["state_prices"]), [F(6,25), F(12,25), F(6,25)], "original Aster state prices")
    eq(F(p["stock_return_variance"]), F(49,576), "stock variance anchor")
    eq(F(p["variance_discount_factor"]), F(12,625), "SDF variance anchor")
    eq(F(p["stock_sharpe_squared"]), F(1,49), "stock squared Sharpe anchor")
    eq(F(p["sdf_bound_squared"]), F(1,48), "SDF squared bound anchor")
    eq(vec(p["bound_attaining_payoff"]), [F(493,600), F(637,600), F(733,600)], "bound attaining states")
    groups.append("Physical-law changes, covariance premium, normalized Q and attainable-bound distinction")

    # Exercise transfers are recomputed, not copied from the preserved output.
    exercise = deepcopy(data)
    exercise.update(claim_payoffs=["8", "20", "52"], claim_quote="23")
    er = model.run(exercise)
    audit(exercise, er)
    eq(vec(er["complete_market"]["claim_replication_asset_units"]), [F(-10), F(3,10), F(1,2)], "exercise 1 replica")
    eq(F(er["complete_market"]["claim_price"]), F(24), "exercise 1 price")
    eq(vec(er["complete_market"]["quote_experiment"]["terminal_payoffs"]), [F(25,24)]*3, "exercise 1 sure payoff")
    eq([3-0, 3-2], [3,1], "exercise 3 zero-budget positive payoff")
    eq(3*F(1)-F(3), F(0), "exercise 3 initial cost")
    eq(dot([F(6,25),F(12,25),F(6,25)], [F(20),F(40),F(60)]), F(192,5), "exercise 4 affine price")
    eq(F(24,25)*F(104), F(2496,25), "exercise 5 wrong physical discount")
    eq(F(p["bound_attaining_mean_excess"]), F(1,50), "exercise 6 tight-bound mean")
    eq(vec(result["log_utility_euler"]["future_consumption"]), [F(4,5),F(1),F(6,5)], "exercise 7 consumption")
    badq = [F(3,5),F(-6,25),F(3,5)]
    eq(sum(badq), F(24,25), "exercise 8 negative extension bond")
    eq(dot(badq, [F(60),F(100),F(140)]), F(96), "exercise 8 negative extension stock")
    groups.append("New-claim exercise, linear-versus-positive pricing, Euler boundary and unidentified digital")

    mutations = []
    equal = deepcopy(data); equal["claim_quote"] = "168/5"; mutations.append(equal)
    probability = deepcopy(data); probability["physical_probabilities"] = ["1/4","1/2","1/4"]; mutations.append(probability)
    asymmetric = deepcopy(data)
    asymmetric.update(stock_price="112", call_price="20", incomplete_digital_quotes=["3/10","2/5","1/2","17/25","7/10"])
    mutations.append(asymmetric)
    grid = deepcopy(data)
    grid.update(stock_payoffs=["50","80","110"], stock_price="384/5", call_price="36/5", diagnostic_call_quotes=["-1","0","36/5","20"])
    mutations.append(grid)
    for d in mutations:
        audit(d, model.run(d))
    eq(model.run(equal)["complete_market"]["quote_experiment"]["arbitrage"], False, "fair quote no artificial trade")
    eq(F(model.run(probability)["physical_pricing"]["variance_discount_factor"]), F(0), "constant SDF boundary")
    ar = model.run(asymmetric)["incomplete_bond_stock_market"]
    eq([F(ar[k]) for k in ("digital_price_lower_strict","digital_price_upper_strict")], [F(2,5),F(17,25)], "changed stock price changes both bounds")
    groups.append("Meaningful price, grid and belief edits; lower-subhedge branch and constant-SDF boundary")

    invalid = []
    for key, value in [
        ("bond_price", "0"), ("stock_price", "0"), ("call_price", "0"),
        ("stock_price", "144"), ("stock_price", "57.6"),
        ("physical_probabilities", ["0","1/2","1/2"]),
        ("alternative_probabilities", ["1/2","1/2","1/2"]),
        ("stock_payoffs", ["60","100","150"]),
        ("states", ["low","low","high"]), ("claim_payoffs", ["10","30"]),
        ("bond_price", True), ("bond_price", 0.96), ("bond_price", "NaN"),
        ("bond_price", "1/0"), ("diagnostic_call_quotes", []),
        ("incomplete_digital_quotes", ["1"]*21), ("utility_discount", "0"),
        ("current_consumption", "-1"), ("policy", "shorting forbidden"),
    ]:
        d = deepcopy(data); d[key] = value; invalid.append(d)
    missing = deepcopy(data); missing.pop("stock_price"); invalid.append(missing)
    extra = deepcopy(data); extra["unused_rate"] = "1/10"; invalid.append(extra)
    for d in invalid:
        try:
            model.run(d)
        except ValueError:
            rejections += 1
        else:
            raise AssertionError("Expected rejection of invalid model domain")
    groups.append("Strict finite-state, rational-number, probability, provenance and policy domain")

    eq(result, json.loads((PROJECTS / "v09-c05-output.json").read_text()), "full preserved output")
    manifest = json.loads((PROJECTS / "v09-c05-manifest.json").read_text())
    expected = {f"v09-c05-{suffix}" for suffix in ("inputs.json","analysis.py","output.json","README.txt")}
    eq({r["file"] for r in manifest["files"]}, expected, "manifest exact distributed set")
    for row in manifest["files"]:
        payload = (PROJECTS / row["file"]).read_bytes()
        eq(len(payload), row["bytes"], "manifest bytes")
        eq(hashlib.sha256(payload).hexdigest(), row["sha256"], "manifest hash")
    with tempfile.TemporaryDirectory(prefix="aster-v09-c05-") as folder:
        dest = Path(folder)
        for name in expected:
            shutil.copyfile(PROJECTS / name, dest / name)
        cli = subprocess.run([sys.executable, str(dest / "v09-c05-analysis.py")], cwd=dest.parent, capture_output=True, text=True, check=True)
        eq(cli.stderr, "", "portable CLI stderr")
        eq(json.loads(cli.stdout), result, "portable complete stdout")
        cli = subprocess.run([sys.executable, str(dest / "v09-c05-analysis.py"), "--input", str(dest / "v09-c05-inputs.json"), "--output", str(dest / "actual.json")], cwd=dest.parent, capture_output=True, text=True, check=True)
        eq(cli.stdout+cli.stderr, "", "explicit-output quiet CLI")
        eq(json.loads((dest / "actual.json").read_text()), result, "explicit-output complete result")
    groups.append("Complete JSON regression, four-file hashes and portable standalone execution")

    chapter = (ROOT / "content/chapters/v09-c05.html").read_text()
    structure = Structure(); structure.feed(chapter)
    eq(len(structure.ids), len(set(structure.ids)), "unique chapter anchors")
    eq(structure.worked, 4, "four fully worked examples")
    eq(structure.solutions, 1, "complete solutions container")
    for n in range(1,9):
        yes(f"exercise-{n}" in structure.ids and f"solution-{n}" in structure.ids, "matched exercise/solution anchors")
    for name in expected | {"v09-c05-manifest.json"}:
        yes(name in structure.hrefs, "offline asset linked")
    yes("Teach-back" in chapter and "Delayed check" in chapter, "retention teaching")
    groups.append("Instructional anchors, four worked cases, eight solved transfers and offline links")
    return {"status":"pass", "groups":len(groups), "comparisons":comparisons,
            "meaningful_domain_rejections":rejections, "coverage":groups}


if __name__ == "__main__":
    print(json.dumps(check(), indent=2, allow_nan=False))
