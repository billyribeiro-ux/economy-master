"""Independent Caldera equilibrium/pricing/teaching checks; quiet strict JSON."""
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
        self.worked = self.solution_containers = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.ids.append(attrs["id"])
        if "href" in attrs:
            self.hrefs.append(attrs["href"])
        if "worked" in attrs.get("class", "").split():
            self.worked += 1
        if tag == "details" and "solutions" in attrs.get("class", "").split():
            self.solution_containers += 1


def check():
    comparisons = 0

    def eq(actual, expected, label):
        nonlocal comparisons
        comparisons += 1
        if actual != expected:
            raise AssertionError(f"{label}: {actual!r} != {expected!r}")

    def yes(condition, label):
        eq(bool(condition), True, label)

    def rejected(call, label):
        try:
            call()
        except ValueError:
            return
        raise AssertionError("Expected model-domain rejection: " + label)

    sink = io.StringIO()
    with redirect_stdout(sink), redirect_stderr(sink):
        spec = importlib.util.spec_from_file_location("v09_c04_caldera", PROJECTS / "v09-c04-analysis.py")
        model = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(model)
        data = json.loads((PROJECTS / "v09-c04-inputs.json").read_text())
        result = model.run(data)
    eq(sink.getvalue(), "", "quiet import and run")
    json.dumps(result, allow_nan=False)
    groups = []

    # Independent orthogonal-factor reconstruction of all returns and covariance.
    # The benchmark instead derives covariance directly from the payoff table.
    rf = F(1, 50)
    factors = [[F(-1, 10), F(-1, 10), F(1, 10), F(1, 10)],
               [F(-1, 10), F(1, 10), F(-1, 10), F(1, 10)],
               [F(-1, 10), F(1, 10), F(1, 10), F(-1, 10)]]
    loadings = [[F(3, 2), F(1, 2), F(0)], [F(1), F(0), F(1, 2)], [F(-1, 2), F(-3, 2), F(-1)]]
    means = [F(2, 25), F(3, 50), F(0)]
    returns = [[mean + sum(coef * factor[s] for coef, factor in zip(row, factors)) for s in range(4)]
               for mean, row in zip(means, loadings)]
    covariance = [[sum(x * y for x, y in zip(left, right)) / 100 for right in loadings] for left in loadings]
    expected_covariance = [[F(1, 40), F(3, 200), F(-3, 200)],
                           [F(3, 200), F(1, 80), F(-1, 100)],
                           [F(-3, 200), F(-1, 100), F(7, 200)]]
    eq(covariance, expected_covariance, "factor loadings imply complete covariance matrix")
    for i, left in enumerate(factors):
        eq(sum(left), F(0), "factor mean zero")
        for j, right in enumerate(factors):
            eq(sum(x * y for x, y in zip(left, right)) / 4, F(1, 100) if i == j else F(0), "orthogonal factor covariance")
    for asset, expected in zip("ABC", returns):
        eq(list(map(F, result["state_returns_by_asset"][asset])), expected, "independent state-return reconstruction " + asset)
    candidate = result["candidate_economy"]
    eq([[F(x) for x in row] for row in candidate["covariance"]], covariance, "benchmark covariance")
    eq(list(map(F, candidate["means"])), means, "physical means")
    eq(list(map(F, candidate["leading_principal_minors"])), [F(1, 40), F(7, 80000), F(9, 4000000)], "SPD leading minors")
    market = [F(-1, 25), F(-1, 25), F(4, 25), F(4, 25)]
    w = [F(1, 2), F(1, 3), F(1, 6)]
    for s in range(4):
        eq(sum(weight * column[s] for weight, column in zip(w, returns)), market[s], "market value-weighted state cash")
    eq(F(result["market"]["mean"]), F(3, 50), "market mean")
    eq(F(result["market"]["variance"]), F(1, 100), "market variance")
    groups.append("Independent orthogonal-factor state/mean/covariance and SPD reconstruction")

    # Individual FOC, strict-concavity objective gaps, actual shares and loan cash.
    x_expected = [[F(1), F(2, 3), F(1, 3)], [F(1, 4), F(1, 6), F(1, 12)]]
    cash_expected = [F(-1), F(1, 2)]
    final_expected = [[F(180), F(180), F(260), F(260)], [F(396), F(396), F(436), F(436)]]
    holdings = []
    for index, h in enumerate(candidate["investors"]):
        gamma, wealth = [F(2), F(8)][index], [F(200), F(400)][index]
        x = list(map(F, h["risky_weights"]))
        eq(x, x_expected[index], "investor optimal risky direction/scale")
        eq(F(h["cash_weight"]), cash_expected[index], "funded wealth budget includes borrowing")
        eq(sum(x) + F(h["cash_weight"]), F(1), "full individual investment budget")
        for row, mu in zip(covariance, means):
            eq(gamma * sum(s * y for s, y in zip(row, x)), mu - rf, "individual FOC")
        units = [wealth * weight / 100 for weight in x]
        eq(list(map(F, h["risky_shares"])), units, "actual claim units")
        holdings.append(units)
        for s in range(4):
            risky_payoff = sum(n * F(a["final_payoffs"][s]) for n, a in zip(units, data["assets"]))
            final_cash = risky_payoff + wealth * cash_expected[index] * F(51, 50)
            eq(final_cash, final_expected[index][s], "gross risky payoff plus signed loan/lending cash")
            eq(F(h["final_wealth"][s]), final_cash, "reported final wealth")
        d = [F(1, 10), F(-1, 5), F(1, 20)]
        def objective(z):
            variance = sum(z[i] * covariance[i][j] * z[j] for i in range(3) for j in range(3))
            return rf + sum(y * (mu - rf) for y, mu in zip(z, means)) - gamma * variance / 2
        gap = objective([y + change for y, change in zip(x, d)]) - objective(x)
        expected_gap = -gamma * sum(d[i] * covariance[i][j] * d[j] for i in range(3) for j in range(3)) / 2
        eq(gap, expected_gap, "strict-concavity loss identity")
        yes(gap < 0, "nonzero deviation is worse")
        eq(F(h["objective"]), [F(3, 50), F(3, 100)][index], "objective level")
    eq([sum(row[i] for row in holdings) for i in range(3)], [F(3), F(2), F(1)], "all risky shares clear")
    eq(sum(F(h["cash_amount"]) for h in candidate["investors"]), F(0), "loan and lending cancel in CU")
    eq(F(candidate["aggregate_risk_tolerance"]), F(1, 4), "wealth-weighted risk tolerance")
    eq(F(candidate["lambda_from_preferences"]), F(4), "equilibrium covariance price")
    eq(candidate["market_clearing"], True, "baseline clearing flag")
    eq(list(map(F, candidate["aggregate_risky_weights"])), w, "aggregate risky exposures")
    for s in range(4):
        eq(sum(row[s] for row in final_expected), 600 * (1 + market[s]), "aggregate final wealth equals physical economy cash")
    groups.append("Investor optimality, strict-concavity gaps, actual shares and complete loan/wealth clearing")

    residuals = []
    for asset, beta, residual_var in zip("ABC", [F(3, 2), F(1), F(-1, 2)], [F(1, 400), F(1, 400), F(13, 400)]):
        projection = result["true_market_projections"][asset]
        eq(F(projection["beta"]), beta, "true market beta")
        eq(F(projection["alpha"]), F(0), "CAPM zero alpha")
        eq(F(projection["residual_variance"]), residual_var, "residual variance decomposition")
        eq(F(projection["residual_mean"]), F(0), "projection mean orthogonality")
        eq(F(projection["residual_benchmark_covariance"]), F(0), "projection covariance orthogonality")
        residuals.append(list(map(F, projection["residuals"])))
    for s in range(4):
        eq(sum(weight * residual[s] for weight, residual in zip(w, residuals)), F(0), "market-weighted residuals cancel exactly")
    z = result["supplied_zero_beta_portfolio"]
    eq(list(map(F, z["state_returns"])), [F(39, 200), F(-31, 200), F(9, 200), F(-1, 200)], "zero-beta risky payoff")
    eq((F(z["mean"]), F(z["variance"]), F(z["projection"]["beta"])), (rf, F(1, 64), F(0)), "zero beta is not zero variance")
    for row in result["market_cash_allocations"]:
        y = F(row["market_weight"])
        eq(F(row["mean"]), rf + y / 25, "signed market/cash mean")
        eq(F(row["variance"]), y * y / 100, "absolute-scaling risk squared")
        eq(row["on_positive_premium_cml_ray"], y >= 0, "negative-market exposure is lower ray")
    yes(F(9, 400) < F(1, 40), "same-mean market mix dominates A in mean-variance space")
    groups.append("SML versus upper/lower CML, portfolio beta and exact residual-risk distinctions")

    # Valuation weights are independently supplied and directly price each payoff.
    q = [F(7, 20), F(7, 20), F(3, 20), F(3, 20)]
    pricing = result["pricing_checksum"]
    eq(list(map(F, pricing["candidate_normalized_weights"])), q, "physical and pricing weights differ")
    eq(list(map(F, pricing["candidate_kernel"])), [F(70, 51), F(70, 51), F(10, 17), F(10, 17)], "strictly positive pricing kernel")
    for a in data["assets"]:
        payoff = list(map(F, a["final_payoffs"]))
        eq(sum(prob * cash for prob, cash in zip(q, payoff)), F(102), "direct valuation-weight expected payoff")
        eq(sum(prob * cash for prob, cash in zip(q, payoff)) / F(51, 50), F(a["price"]), "direct price consistency")
        eq(F(pricing["asset_price_residuals"][a["id"]]), F(0), "reported claim-pricing residual")
    eq(pricing["strictly_positive_and_prices_all_claims"], True, "positive checksum prices full opportunity set")
    eq(F(pricing["bond_price_residual"]), F(0), "risk-free claim priced")
    eq([F(pricing["physical_expected_payoffs_discounted_at_rf"][a]) for a in "ABC"], [F(1800, 17), F(5300, 51), F(5000, 51)], "incorrect physical-mean risk-free discounts exposed")
    digital_price = q[0] / F(51, 50)
    digital_returns = [F(1) / digital_price - 1, F(-1), F(-1), F(-1)]
    digital_mu = sum(digital_returns) / 4
    digital_cov = sum((r - digital_mu) * (rm - F(3, 50)) for r, rm in zip(digital_returns, market)) / 4
    eq((digital_price, digital_mu, digital_cov, digital_cov * 100), (F(35, 102), F(-19, 70), F(-51, 700), F(-51, 7)), "exercise4 state-contract price/mean/covariance/beta")
    eq(rf + digital_cov * 100 / 25, digital_mu, "state contract CAPM required return")
    groups.append("Independent positive pricing weights, every payoff identity and physical-probability counterexample")

    for asset, beta, alpha in zip("ABC", [F(6, 5), F(1), F(-4, 5)], [F(3, 250), F(0), F(3, 250)]):
        proxy = result["proxy_projections"][asset]
        eq((F(proxy["beta"]), F(proxy["alpha"])), (beta, alpha), "B-only proxy discrepancy")
    sample = data["sample_state_indices"]
    m = [market[i] for i in sample]
    m_mean = sum(m) / 8
    m_ss = sum((r - m_mean) ** 2 for r in m)
    eq((m_mean, m_ss), (F(17, 200), F(3, 40)), "sample market mean and centered square sum")
    sample_expected = {"A": (F(23, 15), F(-11, 750)), "B": (F(17, 15), F(-13, 1500)), "C": (F(-13, 15), F(23, 375))}
    for asset, column in zip("ABC", returns):
        observed = [column[i] for i in sample]
        y_mean = sum(observed) / 8
        cross_sum = sum((y - y_mean) * (x - m_mean) for y, x in zip(observed, m))
        beta = cross_sum / m_ss
        alpha = y_mean - rf - beta * (m_mean - rf)
        eq((beta, alpha), sample_expected[asset], "independent OLS centered-sum oracle")
        got = result["finite_sample"]["projections"][asset]
        eq((F(got["beta"]), F(got["alpha"])), (beta, alpha), "sample reported coefficients")
        eq((cross_sum / 7) / (m_ss / 7), beta, "common sample covariance divisor cancels")
        if asset == "A":
            eq((y_mean, cross_sum), (F(21, 200), F(23, 200)), "exercise5 sufficient statistics")
    eq(sum(w[i] * sample_expected[a][1] for i, a in enumerate("ABC")), F(0), "finite-sample true-market weighted alphas cancel")
    equal = [sum(column[s] for column in returns) / 3 for s in range(4)]
    equal_mu = sum(equal) / 4
    equal_var = sum((x - equal_mu) ** 2 for x in equal) / 4
    eq((equal_mu, equal_var), (F(7, 150), F(7, 1200)), "exercise6 equal-weighted proxy")
    for column, mu, expected_beta, expected_alpha in zip(returns, means, [F(10, 7), F(1), F(4, 7)], [F(23, 1050), F(1, 75), F(-37, 1050)]):
        cov = sum((x - mu) * (y - equal_mu) for x, y in zip(column, equal)) / 4
        beta = cov / equal_var
        eq((beta, mu - rf - beta * (equal_mu - rf)), (expected_beta, expected_alpha), "equal-weighted proxy beta/alpha transfer")
    changed_proxy = deepcopy(data)
    changed_proxy["proxy_asset_id"] = "A"
    dynamic = model.run(changed_proxy)
    eq(dynamic["proxy_id"], "A", "edited proxy selector is honored")
    eq(F(dynamic["proxy_projections"]["C"]["alpha"]), F(2, 125), "edited proxy changes reported alpha")
    groups.append("Proxy counterexamples, independent finite-sample OLS and dynamic benchmark selection")

    shift = result["fixed_price_mean_shift"]["demand"]
    eq(shift["market_clearing"], False, "changed beliefs at fixed prices do not create an equilibrium")
    eq(list(map(F, shift["risky_excess_demand_weights"])), [F(3, 8), F(-5, 12), F(1, 24)], "exact mean-shift excess demands")
    constrained = result["borrowing_limit_experiment"]["demand"]
    h1 = constrained["investors"][0]
    eq(list(map(F, h1["risky_weights"])), [F(1), F(0), F(0)], "constrained optimum is A-only")
    eq(F(h1["cash_weight"]), F(0), "borrowing constraint binds")
    eq(F(h1["borrowing_multiplier"]), F(1, 100), "nonnegative KKT multiplier")
    eq(list(map(F, h1["gradient"])), [F(1, 100)] * 3, "constrained marginal values match normal vector")
    eq(F(h1["objective"]), F(11, 200), "A-only objective")
    eq(F(3, 50) - F(1, 100), F(1, 20), "scaled-down market has lower objective")
    eq(list(map(F, constrained["aggregate_risky_weights"])), [F(1, 2), F(1, 9), F(1, 18)], "constrained aggregate exposures")
    eq(list(map(F, constrained["risky_excess_demand_weights"])), [F(0), F(-2, 9), F(-1, 9)], "unmet risky supplies")
    eq((F(constrained["aggregate_cash_weight"]), constrained["market_clearing"]), (F(1, 3), False), "zero-net-cash market cannot clear desired lending")
    for z in [[F(1, 3)] * 3, [F(0)] * 3, [F(3, 2), F(-1, 2), F(0)]]:
        delta = [z[0] - 1, z[1], z[2]]
        loss = F(1, 100) * sum(delta) - sum(delta[i] * covariance[i][j] * delta[j] for i in range(3) for j in range(3))
        yes(loss < 0, "feasible constrained competitor strictly worse")
    h2_constraint = deepcopy(data)
    h2_constraint["borrowing_limit_investor_id"] = "H2"
    h2_result = model.run(h2_constraint)["borrowing_limit_experiment"]["demand"]
    eq(h2_result["market_clearing"], True, "nonbinding investor constraint preserves baseline demands")
    changed_payoff = deepcopy(data)
    changed_payoff["assets"][0]["final_payoffs"] = [str(F(x) + 1) for x in changed_payoff["assets"][0]["final_payoffs"]]
    new_candidate = model.run(changed_payoff)
    eq(new_candidate["candidate_economy"]["market_clearing"], False, "edited main candidate truthfully reports nonclearing")
    eq(new_candidate["pricing_checksum"]["strictly_positive_and_prices_all_claims"], False, "candidate kernel not silently advertised as valid after edit")
    yes(F(new_candidate["market"]["expected_excess_return"]) > 0 and all(not row["on_positive_premium_cml_ray"] for row in new_candidate["market_cash_allocations"]),
        "positive-premium market ray is not called efficient when admitted assets have nonzero population alphas")
    groups.append("Mean-shift and borrowing-limit failures, KKT optimality and honest edited-candidate flags")

    # Other exercise anchors are independently reconstructed, not merely located in prose.
    T = F(1, 5) / 2 + F(3, 10) / 3 + F(1, 2) / 5
    lam = 1 / T
    eq((T, lam, F(18, 1000) * lam), (F(3, 10), F(10, 3), F(3, 50)), "exercise1 aggregate preferences/premium")
    eq(F(1, 100) - F(1, 4) * F(3, 50), F(-1, 200), "exercise1 negative-beta return")
    eq(sum(a * (1 - lam / gamma) for a, gamma in zip([F(1, 5), F(3, 10), F(1, 2)], [2, 3, 5])), F(0), "exercise1 aggregate cash")
    d = [4 * a - 6 * rm + 3 * rf for a, rm in zip(returns[0], market)]
    eq(d, [F(-9, 50), F(11, 50), F(-9, 50), F(11, 50)], "exercise2 implemented signed portfolio")
    eq(sum((x - rf) ** 2 for x in d) / 4, F(1, 25), "exercise2 residual risk")
    alpha = F(7, 100) - F(3, 100) - F(1, 2) * F(6, 100)
    eq(alpha, F(1, 100), "exercise3 alpha")
    eq(F(3, 5) * alpha, F(3, 500), "exercise3 portfolio alpha")
    eq(F(3, 100) + F(3, 2) * F(6, 100), F(3, 25), "exercise3 CML expected return")
    halfwidth = F(196, 100) * F(5, 1000)
    eq([F(8, 1000) - halfwidth, F(8, 1000) + halfwidth], [F(-9, 5000), F(89, 5000)], "exercise8 supplied gross reference interval")
    eq([F(5, 1000) - halfwidth, F(5, 1000) + halfwidth], [F(-3, 625), F(37, 2500)], "exercise8 fee-adjusted reference interval")
    groups.append("All eight exercise arithmetic/transfer anchors, with pricing and inference scope separated")

    modifications = [(["regime"], "no_borrowing"), (["physical_probabilities"], ["1/4"] * 3 + ["1/5"]),
                     (["physical_probabilities"], ["0", "1/3", "1/3", "1/3"]),
                     (["investors", 0, "wealth"], "201"), (["investors", 0, "gamma"], "0"),
                     (["assets", 0, "price"], "0"), (["proxy_asset_id"], "missing"),
                     (["sample_state_indices"], [False, 1]),
                     (["zero_beta_portfolio", "cash_weight"], "1")]
    for path, value in modifications:
        bad = deepcopy(data)
        destination = bad
        for key in path[:-1]:
            destination = destination[key]
        destination[path[-1]] = value
        rejected(lambda bad=bad: model.run(bad), str(path))
    singular = deepcopy(data)
    singular["assets"][1]["final_payoffs"] = singular["assets"][0]["final_payoffs"][:]
    rejected(lambda: model.run(singular), "redundant risky claims make covariance singular")
    rejected(lambda: model.projection(returns[0], [rf] * 4, [F(1, 4)] * 4, rf), "constant benchmark beta")
    groups.append("Eleven meaningful regime/probability/wealth/risk/budget/singularity rejection checks")

    preserved = json.loads((PROJECTS / "v09-c04-output.json").read_text())
    eq(result, preserved, "complete preserved reference output")
    manifest = json.loads((PROJECTS / "v09-c04-manifest.json").read_text())
    filenames = {"v09-c04-inputs.json", "v09-c04-analysis.py", "v09-c04-output.json", "v09-c04-README.txt"}
    eq({entry["file"] for entry in manifest["files"]}, filenames, "manifest exact payload set")
    for entry in manifest["files"]:
        payload = (PROJECTS / entry["file"]).read_bytes()
        eq(len(payload), entry["bytes"], "manifest byte size")
        eq(hashlib.sha256(payload).hexdigest(), entry["sha256"], "manifest digest")
    structure = Structure()
    html = (ROOT / "content/chapters/v09-c04.html").read_text()
    structure.feed(html)
    eq(len(structure.ids), len(set(structure.ids)), "unique chapter anchors")
    eq(structure.worked, 4, "four worked examples")
    eq(structure.solution_containers, 1, "complete solution container")
    for number in range(1, 9):
        yes("exercise-" + str(number) in structure.ids and "solution-" + str(number) in structure.ids, "exact exercise/solution pairing")
    for name in filenames | {"v09-c04-manifest.json"}:
        yes(name in structure.hrefs, "flat offline asset link")
    sources = json.loads((ROOT / "content/reviews/v09-c04-sources.json").read_text())
    eq(len(sources), 3, "three scoped primary method sources")
    canonical = {source["id"]: source for source in json.loads((ROOT / "content/sources.json").read_text())}
    eq(sources[0], canonical["v08-c04-mit-capm"], "existing MIT record reused exactly")
    for source in sources:
        yes("sources.html#" + source["id"] in structure.hrefs, "cited source record")
        yes(all(source.get(key) for key in ("title", "url", "use", "checked", "verification")), "complete source scope")
    with tempfile.TemporaryDirectory(prefix="caldera-offline-") as directory:
        folder = Path(directory)
        for filename in ("v09-c04-analysis.py", "v09-c04-inputs.json"):
            shutil.copyfile(PROJECTS / filename, folder / filename)
        for optimized in (False, True):
            command = [sys.executable] + (["-O"] if optimized else []) + [str(folder / "v09-c04-analysis.py")]
            if optimized:
                command.append(str(folder / "v09-c04-inputs.json"))
            finished = subprocess.run(command, cwd=ROOT.parent, text=True, capture_output=True, check=True)
            eq(finished.stderr, "", "isolated execution stderr")
            eq(json.loads(finished.stdout), preserved, "isolated normal/optimized portable result")
    groups.append("Full reference/manifest, worked/exercise/source structure and isolated offline CLI")
    return {"chapter": "v09-c04", "status": "pass", "check_groups": len(groups), "comparisons": comparisons,
            "checks": [{"name": name, "status": "pass"} for name in groups],
            "limits": "Bounded exact synthetic economy, not empirical CAPM validation, investor skill evidence or visual UI certification."}


if __name__ == "__main__":
    print(json.dumps(check(), indent=2, allow_nan=False))
