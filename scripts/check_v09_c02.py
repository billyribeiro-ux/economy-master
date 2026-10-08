"""Quiet independent checks for portfolio mathematics and the bounded Oriel lab."""
from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
from fractions import Fraction as F
from html.parser import HTMLParser
from itertools import product
from math import isclose, sqrt
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
ASSETS = ROOT / "content/projects"


class Structure(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids, self.hrefs, self.exercises, self.solutions = [], [], [], []
        self.worked, self.solution_containers = 0, 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "id" in a:
            self.ids.append(a["id"])
            if a["id"].startswith("v09-c02-e") and tag == "li":
                self.exercises.append(a["id"])
        if "href" in a:
            self.hrefs.append(a["href"])
        if "data-solution-for" in a:
            self.solutions.append(a["data-solution-for"])
        if tag == "aside" and "worked" in a.get("class", "").split():
            self.worked += 1
        if tag == "details" and "solutions" in a.get("class", "").split():
            self.solution_containers += 1


def check():
    comparisons, rejections = 0, 0

    def same(actual, expected, label):
        nonlocal comparisons
        comparisons += 1
        if actual != expected:
            raise AssertionError(f"{label}: {actual!r} != {expected!r}")

    def near(actual, expected, label):
        nonlocal comparisons
        comparisons += 1
        if not isclose(float(actual), float(expected), rel_tol=1e-12, abs_tol=1e-12):
            raise AssertionError(label)

    def require(condition, label):
        same(bool(condition), True, label)

    def rejects(call, label):
        nonlocal rejections
        try:
            call()
        except ValueError:
            rejections += 1
            return
        raise AssertionError("Expected documented-domain rejection: " + label)

    quiet = io.StringIO()
    with redirect_stdout(quiet), redirect_stderr(quiet):
        model = SimpleNamespace(**runpy.run_path(str(ASSETS / "v09-c02-analysis.py")))
        data = json.loads((ASSETS / "v09-c02-inputs.json").read_text())
        result = model.run(data)
    same(quiet.getvalue(), "", "quiet import and full run")
    json.dumps(result, allow_nan=False)
    rows = [[F(x) for x in row] for row in data["population"]["returns"]]
    p = [F(x) for x in data["population"]["probabilities"]]
    stats = model.population_moments(rows, p)
    groups = []

    # Independent construction from factor loadings, rather than centered state sums.
    means = [F(2, 25), F(3, 50), F(7, 100)]
    loads = [[F(3, 25), F(1, 25)], [F(1, 25), F(-2, 25)], [F(2, 25), F(-1, 50)]]
    signs = [(1, 1), (1, -1), (-1, 1), (-1, -1)]
    reconstructed = [[means[i] + loads[i][0] * f + loads[i][1] * e for i in range(3)] for f, e in signs]
    same(rows, reconstructed, "complete original factor-built state law")
    cov = [[sum(loads[i][k] * loads[j][k] for k in range(2)) for j in range(3)] for i in range(3)]
    same(stats["mean"], means, "population means")
    same(stats["covariance"], cov, "loading product independently reconstructs covariance")
    # A second mean-free identity uses every pair of possible states.
    for i in range(3):
        for j in range(3):
            pair = sum(p[s] * p[t] * (rows[s][i] - rows[t][i]) * (rows[s][j] - rows[t][j])
                       for s in range(4) for t in range(4)) / 2
            same(cov[i][j], pair, "pairwise state-difference covariance identity")
    null = [F(1), F(1), F(-2)]
    same([sum(row[i] * null[i] for i in range(3)) for row in rows], [F(0)] * 4, "redundant fund zero payoff")
    same([sum(cov[i][j] * null[j] for j in range(3)) for i in range(3)], [F(0)] * 3, "exact covariance null vector")
    same(stats["centered_rank"], 2, "two independent factor directions")
    # All two-asset minors nonnegative; full determinant is zero for the replicated claim.
    for i, j in [(0, 1), (0, 2), (1, 2)]:
        require(cov[i][i] * cov[j][j] - cov[i][j] ** 2 > 0, "distinct two-asset directions are nondegenerate")
    det = (cov[0][0] * (cov[1][1] * cov[2][2] - cov[1][2] ** 2)
           - cov[0][1] * (cov[0][1] * cov[2][2] - cov[1][2] * cov[0][2])
           + cov[0][2] * (cov[0][1] * cov[1][2] - cov[1][1] * cov[0][2]))
    same(det, F(0), "legitimate singular covariance")
    near(stats["correlation"][0][1], sqrt(2) / 10, "population correlation")
    constant = model.population_moments([[F(1, 25)], [F(1, 25)]], [F(1, 2), F(1, 2)])
    same(constant["covariance"], [[F(0)]], "constant cash has zero variance")
    same(constant["correlation"], [[None]], "constant cash correlation is undefined")
    groups.append("Factor-built and pairwise state covariance, replication, rank and zero-variance boundaries")

    anchor_returns = {
        "P1": [F(3, 40), F(7, 40), F(-9, 200), F(11, 200)],
        "P2": [F(13, 100), F(17, 100), F(-3, 100), F(1, 100)]}
    for label in ("P3", "P4"):
        anchor_returns[label] = anchor_returns["P2"]
    for plan in data["population"]["portfolios"]:
        got = result["portfolios"][plan["id"]]
        returns = anchor_returns[plan["id"]]
        mu = sum(returns) / 4
        var = sum(x * x for x in returns) / 4 - mu * mu
        same(list(map(F, got["state_returns"])), returns, "direct allocation state returns")
        same(F(got["mean"]), mu, "return expectation")
        same(F(got["variance"]), var, "raw second moment minus squared mean")
        near(got["standard_deviation"], sqrt(float(var)), "portfolio standard deviation")
        same(F(got["negative_return_probability"]), F(1, 4), "state loss probability is separately calculated")
    same(F(result["portfolios"]["P1"]["variance"]), F(61, 10000), "tilted portfolio variance")
    same(F(result["portfolios"]["P2"]["variance"]), F(17, 2500), "replicated C variance")
    groups.append("All four allocations, direct state dispersion, loss probability and duplicate-name counterexample")

    # Enumerate common/idiosyncratic signs; do not use the benchmark's H formula as the oracle.
    common = result["common_risk"]
    for w, key in [([F(1, 4)] * 4, "equal"), ([F(7, 10), F(1, 10), F(1, 10), F(1, 10)], "concentrated")]:
        draws = []
        for shocks in product((-1, 1), repeat=5):
            assets = [F(3, 50) + F(shocks[0], 10) + F(shocks[i + 1], 5) for i in range(4)]
            draws.append(sum(wi * ri for wi, ri in zip(w, assets)))
        mu = sum(draws) / len(draws)
        variance = sum(x * x for x in draws) / len(draws) - mu * mu
        expected = F(common["equal_weight"][1]["variance"]) if key == "equal" else F(common["concentrated"]["variance"])
        same(variance, expected, "enumerated common and residual shocks")
        same(mu, F(3, 50), "common-risk family mean")
    same([F(x["variance"]) for x in common["equal_weight"]], [F(1, 20), F(1, 50), F(29, 2500), F(13, 1250)], "four stated diversification sizes")
    same(F(common["concentrated"]["H"]), F(13, 25), "concentration")
    same(F(common["concentrated"]["effective_names_for_residual_component"]), F(25, 13), "conditional effective-name interpretation")
    for n, expected in [(5, F(0)), (6, F(-1, 24))]:
        rho = F(-1, 4)
        full_sum = sum(F(1) if i == j else rho for i in range(n) for j in range(n)) / (n * n)
        same(full_sum, expected, "negative equicorrelation feasible size boundary")
    groups.append("Enumerated diversification versus concentration and the finite equicorrelation boundary")

    # Gross cash obligations independently recover returns, including fee and debt principal.
    financing = result["financing"]
    for label in ("scaled_underlying", "long_short"):
        actual = financing[label]
        wealths = []
        for A, B, C in rows:
            W1 = 150 * (1 + C) - 53 if label == "scaled_underlying" else 120 * (1 + A) - 40 * (1 + B) + 20 * F(103, 100) - F(4, 5)
            wealths.append(W1)
        returns = [w / 100 - 1 for w in wealths]
        mu = sum(returns) / 4
        variance = sum((w - sum(wealths) / 4) ** 2 for w in wealths) / (4 * 100 ** 2)
        same(list(map(F, actual["terminal_wealth"])), wealths, "gross financed wealth ledger")
        same(list(map(F, actual["state_returns"])), returns, "net return from actual terminal wealth")
        same(F(actual["mean"]), mu, "financed expected net return")
        same(F(actual["variance"]), variance, "variance of dollar wealth divided by initial wealth squared")
    same(F(financing["scaled_underlying"]["mean"]), F(3, 40), "borrowing cost is six percent")
    same(F(financing["scaled_underlying"]["variance"]), F(153, 10000), "scaled risk")
    same(F(financing["long_short"]["mean"]), F(7, 100), "stock borrow fee included")
    same(F(financing["long_short"]["variance"]), F(356, 15625), "signed cross term included")
    stress_rows = [[F(0), F(0), F(-4, 5)]]
    stress_moments = model.population_moments(stress_rows, [F(1)])
    stress = model.financed_plan(stress_rows, [F(1)], stress_moments, [0, 0, F(3, 2)], F(-1, 2), data["finance"])
    same(stress["terminal_wealth"], [F(-23)], "full-recourse stress is not a zero-floor payoff")
    same(stress["negative_equity_state_indices"], [0], "recourse deficit explicitly reported")
    groups.append("Direct loan and short cash ledgers, deterministic costs, signed variance and recourse stress")

    # Sample covariance through pairwise time differences, independently of sample centering.
    sample_rows = [[F(x) for x in row] for row in data["sample"]["returns"]]
    n = len(sample_rows)
    sample = model.sample_report(data["sample"])
    S = [[sum((sample_rows[t][i] - sample_rows[u][i]) * (sample_rows[t][j] - sample_rows[u][j])
              for t in range(n) for u in range(t + 1, n)) / (n * (n - 1))
          for j in range(2)] for i in range(2)]
    same(sample["sample_covariance"], S, "sample pairwise-difference identity")
    same(S, [[F(13, 5000), F(3, 2500)], [F(3, 2500), F(1, 1000)]], "sample covariance anchors")
    series = [F(2, 5) * row[0] + F(3, 5) * row[1] for row in sample_rows]
    sample_mean = sum(series) / n
    sample_var = (sum(x * x for x in series) - n * sample_mean * sample_mean) / (n - 1)
    same(sample["fixed_weight_portfolio"]["sample_mean"], F(1, 50), "fixed-weight sample mean")
    same(sample["fixed_weight_portfolio"]["sample_variance"], sample_var, "direct scalar sample variance")
    same(sample_var, F(169, 125000), "sample risk")
    same(sample["fixed_weight_portfolio"]["iid_mean_variance_estimate"], F(169, 625000), "iid estimator variance differs from return variance")
    same(sample["fixed_weight_portfolio"]["empirical_equal_probability_variance"], F(169, 156250), "empirical law has denominator n")
    near(sample["fixed_weight_portfolio"]["iid_mean_standard_error_estimate"], sqrt(float(F(169, 625000))), "mean standard error")
    # Small exhaustive repeated-sampling audit: all 4^3 iid samples.
    samples, average_S = [], [[F(0), F(0)], [F(0), F(0)]]
    for index in product(range(4), repeat=3):
        draw = [rows[t][:2] for t in index]
        got = model.sample_moments(draw, 2)
        samples.append(got["sample_mean"])
        for i in range(2):
            for j in range(2):
                average_S[i][j] += got["sample_covariance"][i][j] / 64
    same(average_S, [row[:2] for row in cov[:2]], "exhaustive finite iid covariance unbiasedness")
    for i in range(2):
        for j in range(2):
            covariance_of_means = sum(v[i] * v[j] for v in samples) / 64 - means[i] * means[j]
            same(covariance_of_means, cov[i][j] / 3, "exhaustive variance of sample means")
    small = model.sample_moments([[0, 0, 0], ["1/10", "1/5", "3/10"]], 3)
    same(small["centered_rank"], 1, "n-1 rank bound with more assets than dates")
    groups.append("Pairwise sample reconstruction, mean uncertainty, empirical law and exact repeated-sampling experiment")

    missing = result["missing_pair_counterexample"]
    raw_missing = data["missing_data"]["returns"]
    matrix = [[F(1) if i == j else F(0) for j in range(3)] for i in range(3)]
    for i in range(3):
        for j in range(i + 1, 3):
            pair = [[F(row[i]), F(row[j])] for row in raw_missing if row[i] is not None and row[j] is not None]
            # With two varying observations, Pearson correlation is the sign of the product of differences.
            sign = F(1) if (pair[1][0] - pair[0][0]) * (pair[1][1] - pair[0][1]) > 0 else F(-1)
            matrix[i][j] = matrix[j][i] = sign
    same([[F(x) for x in row] for row in missing["assembled_correlation"]], matrix, "independent pairwise direction reconstruction")
    witness = [F(-1), F(1), F(1)]
    impossible = sum(witness[i] * matrix[i][j] * witness[j] for i in range(3) for j in range(3))
    same(impossible, F(-3), "negative full-investment variance witness")
    same(F(missing["impossible_unit_volatility_variance"]), impossible, "diagnostic reports contradiction")
    same(missing["complete_rows"], 0, "no complete-case estimate invented")
    groups.append("Missing-pair correlations, absent complete rows and explicit non-PSD certificate")

    # Independent solutions to every determinate exercise; proofs reviewed separately.
    e1_mean = F(3, 10) * F(1, 10) + F(1, 2) * F(1, 25) + F(1, 5) * F(1, 50)
    e1_var = F(3, 10) ** 2 * F(1, 25) + F(1, 2) ** 2 * F(1, 100) + 2 * F(3, 10) * F(1, 2) * F(-1, 200)
    same((e1_mean, 200 * (1 + e1_mean), e1_var), (F(27, 500), F(1054, 5), F(23, 5000)), "exercise1 full account")
    e2_matrix = [[F(1), F(4, 5), F(4, 5)], [F(4, 5), F(1), F(-4, 5)], [F(4, 5), F(-4, 5), F(1)]]
    same(sum(witness[i] * e2_matrix[i][j] * witness[j] for i in range(3) for j in range(3)) / 100, F(-9, 500), "exercise2 global inconsistency")
    e3 = [(F(5, 8) * F(3, 20)) ** 2 + (F(3, 8) * F(1, 4)) ** 2
          + 2 * F(5, 8) * F(3, 8) * rho * F(3, 20) * F(1, 4) for rho in [-1, 0, 1]]
    same(e3, [F(0), F(9, 512), F(9, 256)], "exercise3 correlation endpoints")
    same(2 * F(3, 2) * F(-1, 2) * F(3, 20) * F(1, 4), F(-9, 160), "exercise3 derivative changes sign")
    same([abs(F(3, 2) * F(3, 20) + rho * F(-1, 2) * F(1, 4)) for rho in [-1, 1]], [F(7, 20), F(1, 10)], "exercise3 signed endpoint volatility")
    loading = F(1, 2) + F(3, 10) * 2
    residual = F(1, 2) ** 2 / 100 + F(3, 10) ** 2 / 25 + F(1, 5) ** 2 * F(9, 100)
    original = loading ** 2 / 400 + residual
    new = original - F(1, 2) ** 2 / 100 + 4 * F(1, 8) ** 2 / 100
    same((original, new), (F(509, 40000), F(217, 20000)), "exercise4 preserves common loading")
    wealth = [180 * F(6, 5) - 84, 180 * F(3, 5) - 84]
    ret = [(x - 100) / 100 for x in wealth]
    mu = F(3, 5) * ret[0] + F(2, 5) * ret[1]
    variance = F(3, 5) * ret[0] ** 2 + F(2, 5) * ret[1] ** 2 - mu * mu
    same((wealth, mu, variance), ([F(132), F(24)], F(-14, 125), F(4374, 15625)), "exercise5 independent payoff moments")
    same((180 * F(2, 5) - 84, F(84, 180) - 1), (F(-12), F(-8, 15)), "exercise5 recourse stress and zero equity")
    x, y = [F(1, 100), F(3, 100), F(-1, 100)], [F(1, 50), F(0), F(1, 25)]
    e6_S = [[(sum(a * b for a, b in zip(u, v)) - 3 * (sum(u) / 3) * (sum(v) / 3)) / 2 for v in (x, y)] for u in (x, y)]
    same(e6_S, [[F(1, 2500), F(-1, 2500)], [F(-1, 2500), F(1, 2500)]], "exercise6 raw-product sample moments")
    same([(a + b) / 2 for a, b in zip(x, y)], [F(3, 200)] * 3, "exercise6 observed cancellation")
    e7 = sum(F(1, 2500) if t == u else F(1, 10000) if abs(t - u) == 1 else F(0)
             for t in range(4) for u in range(4)) / 16
    same(e7, F(11, 80000), "exercise7 full serial covariance sum")
    same(e7 / F(1, 10000), F(11, 8), "exercise7 independence understatement")
    for returns, probs, loss, tail in [([F(-1, 10), F(1, 10)], [F(1, 2), F(1, 2)], F(1, 2), F(0)),
                                       ([F(-3, 10), F(1, 30)], [F(1, 10), F(9, 10)], F(1, 10), F(1, 10))]:
        mu = sum(r * p for r, p in zip(returns, probs))
        variance = sum(r * r * p for r, p in zip(returns, probs)) - mu * mu
        same((mu, variance), (F(0), F(1, 100)), "exercise8 equal first two moments")
        same(sum(p for r, p in zip(returns, probs) if r < 0), loss, "exercise8 loss probability")
        same(sum(p for r, p in zip(returns, probs) if r < F(-1, 5)), tail, "exercise8 extreme loss probability")
    groups.append("All eight exercise numerical and counterexample anchors, with complete proof review separate")

    # Selected economic and representation failures; no broad parameter sweep.
    rejects(lambda: model.population_moments(rows, ["0", "1/3", "1/3", "1/3"]), "strictly positive state probabilities")
    rejects(lambda: model.population_moments(rows, ["1/4"] * 3 + ["1/5"]), "probability mass")
    rejects(lambda: model.portfolio(rows, p, stats, ["1/4", "1/4", "0"]), "missing financing in portfolio budget")
    rejects(lambda: model.matrix_rows([["-101/100"]], 1), "unlevered asset return below total loss")
    rejects(lambda: model.matrix_rows([[0.1]], 1), "floating input not exact")
    rejects(lambda: model.matrix_rows([[True]], 1), "boolean is not a return")
    rejects(lambda: model.sample_moments([[0, 0]], 2), "sample covariance needs at least two dates")
    rejects(lambda: model.sample_moments([[0, None], [1, 0]], 2), "missing value not zero")
    changes = [
        (["sample", "period_ends"], ["2027-01-31"] * 5),
        (["common_risk", "factor_variance"], "-1/100"),
        (["common_risk", "equal_weight_counts"], [4.5]),
        (["finance", "short_proceeds_reusable"], False),
        (["finance", "interim_margin_calls"], True),
        (["finance", "full_recourse"], False),
        (["finance", "short_cash_weight"], "0"),
        (["finance", "borrowing_rate"], "1/100"),
        (["finance", "initial_wealth"], "0"),
        (["missing_data", "witness_weights"], ["1", "0", "0"]),
    ]
    for path, replacement in changes:
        modified = deepcopy(data)
        destination = modified
        for key in path[:-1]:
            destination = destination[key]
        destination[path[-1]] = replacement
        rejects(lambda modified=modified: model.run(modified), "/".join(path))
    missing_change = deepcopy(data)
    missing_change["missing_data"]["returns"][0][0] = "-9/100"
    rejects(lambda: model.run(missing_change), "named perfect-pair demonstration has explicit scope")
    groups.append("Nineteen meaningful budget, sampling, payoff-contract and bounded-counterexample rejections")

    same(result, json.loads((ASSETS / "v09-c02-output.json").read_text()), "complete reference output")
    manifest = json.loads((ASSETS / "v09-c02-manifest.json").read_text())
    expected_files = {"v09-c02-inputs.json", "v09-c02-analysis.py", "v09-c02-output.json", "v09-c02-README.txt"}
    same({item["file"] for item in manifest["files"]}, expected_files, "manifest exact four-file perimeter")
    for item in manifest["files"]:
        payload = (ASSETS / item["file"]).read_bytes()
        same(len(payload), item["bytes"], "manifest byte size")
        same(hashlib.sha256(payload).hexdigest(), item["sha256"], "manifest digest")
    html = (ROOT / "content/chapters/v09-c02.html").read_text()
    structure = Structure()
    structure.feed(html)
    same(len(structure.ids), len(set(structure.ids)), "unique chapter anchors")
    same(structure.worked, 4, "four complete worked examples")
    expected_ids = [f"v09-c02-e{i}" for i in range(1, 9)]
    same(structure.exercises, expected_ids, "eight original exercise prompts")
    same(structure.solutions, expected_ids, "eight matched complete solutions")
    same(structure.solution_containers, 1, "solution container")
    for filename in expected_files | {"v09-c02-manifest.json"}:
        require(filename in structure.hrefs, "flat downloadable link")
    require(not any(h.startswith("projects/") for h in structure.hrefs), "no unpublished asset directory")
    sources = json.loads((ROOT / "content/reviews/v09-c02-sources.json").read_text())
    same({s["id"] for s in sources}, {"v09-c02-mit-portfolio", "mit-probability-covariance", "v09-c02-r-covariance"}, "three scoped methodological sources")
    canonical = {s["id"]: s for s in json.loads((ROOT / "content/sources.json").read_text())}
    for source in sources:
        require("sources.html#" + source["id"] in structure.hrefs, "source is actually linked")
        if source["id"] in canonical:
            same(source, canonical[source["id"]], "exact reused or integrated source record")
    with tempfile.TemporaryDirectory(prefix="oriel-offline-") as folder:
        target = Path(folder)
        for name in ["v09-c02-analysis.py", "v09-c02-inputs.json"]:
            shutil.copyfile(ASSETS / name, target / name)
        for optimized in [False, True]:
            command = [sys.executable] + (["-O"] if optimized else []) + [str(target / "v09-c02-analysis.py")]
            if optimized:
                command.append(str(target / "v09-c02-inputs.json"))
            run = subprocess.run(command, cwd=ROOT.parent, capture_output=True, text=True, check=True)
            same(run.stderr, "", "portable standalone execution stderr")
            same(json.loads(run.stdout), result, "normal/optimized standalone result")
    groups.append("Reference, manifest, exercises, source scope and portable normal/optimized offline execution")
    return {"chapter": "v09-c02", "status": "pass", "check_groups": len(groups),
            "comparisons": comparisons, "domain_rejections": rejections,
            "checks": [{"name": name, "status": "pass"} for name in groups],
            "limits": "Original synthetic case, exact algebra and bounded code checks; no market-risk guarantee, learner validation, external human certification or visual UI claim."}


if __name__ == "__main__":
    print(json.dumps(check(), indent=2, allow_nan=False))

