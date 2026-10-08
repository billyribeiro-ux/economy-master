"""Independent exact reference calculations and executable contracts for v05 project.

The reference equilibrium solves a scalar aggregate-output equation rather than
the benchmark's two-firm active-set matrices. Policy branch certificates are
verified against primitive incentives; quadratic maxima are reconstructed from
three direct resource-welfare evaluations, not benchmark coefficient helpers.
"""
from contextlib import redirect_stdout
from copy import deepcopy
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "content/projects"
DATA = DIR / "v05-project-data.json"
PROGRAM = DIR / "v05-project-analysis.py"


def require(condition, label):
    if not condition:
        raise AssertionError(label)


def primitives(row):
    return {"A": F(row["demand_intercept"]), "b": F(row["demand_slope"]), "h": F(row["damage_slope"]),
            "c": [F(f["linear_cost"]) for f in row["firms"]], "k": [F(f["quadratic_cost"]) for f in row["firms"]],
            "u": [F(f["capacity"]) for f in row["firms"]],
            "tax": F(row["tax_ceiling"]), "standard": F(row["standard_ceiling"]),
            "tax_cost": F(row["tax_administration"]), "standard_cost": F(row["standard_administration"])}


def clip(x, hi):
    return max(F(0), min(hi, x))


def capacities(p, kind, value):
    return [min(u, value) for u in p["u"]] if kind == "standard" else p["u"]


def scalar_equilibrium(p, regime, kind="none", value=F(0)):
    """Q = sum_i clip((A-c_i-t-cross*Q)/d_i,0,cap_i)."""
    caps = capacities(p, kind, value)
    t = value if kind == "tax" else F(0)
    cross = p["b"]+p["h"] if regime == "planner" else p["b"]
    ds = [k+(p["b"] if regime == "cournot" else 0) for k in p["k"]]
    intercepts = [p["A"]-c-t for c in p["c"]]
    bound = sum(caps)
    knots = {F(0), bound}
    for a, d, cap in zip(intercepts, ds, caps):
        knots.update((clip(a/cross, bound), clip((a-d*cap)/cross, bound)))
    knots = sorted(knots)
    def amounts(Q):
        return [clip((a-cross*Q)/d, cap) for a, d, cap in zip(intercepts, ds, caps)]
    roots = {tuple(amounts(Q)) for Q in knots if sum(amounts(Q)) == Q}
    for lo, hi in zip(knots[:-1], knots[1:]):
        mid = (lo+hi)/2
        numerator, denominator = F(0), F(1)
        for a, d, cap in zip(intercepts, ds, caps):
            tentative = (a-cross*mid)/d
            if tentative >= cap:
                numerator += cap
            elif tentative > 0:
                numerator += a/d
                denominator += cross/d
        Q = numerator/denominator
        if lo <= Q <= hi and sum(amounts(Q)) == Q:
            roots.add(tuple(amounts(Q)))
    require(len(roots) == 1, "independent scalar equation unique root")
    return list(next(iter(roots)))


def resource_welfare(p, q, kind="none"):
    Q = sum(q)
    benefit = p["A"]*Q-p["b"]*Q*Q/2
    costs = sum(c*x+k*x*x/2 for c, k, x in zip(p["c"], p["k"], q))
    administration = p[kind+"_cost"] if kind != "none" else F(0)
    return benefit-costs-p["h"]*Q*Q/2-administration


def gradients(p, q, regime, tax):
    Q = sum(q)
    price = p["A"]-p["b"]*Q
    return [price-c-k*x-tax-(p["b"]*x if regime == "cournot" else p["h"]*Q if regime == "planner" else 0)
            for c, k, x in zip(p["c"], p["k"], q)]


def verify_ledger(p, result, expected_regime=None):
    regime = result["regime"]
    require(expected_regime is None or expected_regime == regime, "ledger regime")
    kind, value = result["policy"]["kind"], result["policy"]["value"]
    q = scalar_equilibrium(p, regime, kind, value)
    require(result["quantities"] == q, "ledger quantities versus independent scalar oracle")
    Q = sum(q)
    price = p["A"]-p["b"]*Q
    tax = value if kind == "tax" else F(0)
    cost = [c*x+k*x*x/2 for c, k, x in zip(p["c"], p["k"], q)]
    profits = [(price-tax)*x-c for x, c in zip(q, cost)]
    administration = p[kind+"_cost"] if kind != "none" else F(0)
    require(result["total_output"] == Q and result["buyer_price"] == price, "output and price")
    require(result["retained_price_after_tax"] == price-tax and result["private_costs"] == cost, "retained price and private resource costs")
    require(result["firm_profits"] == profits, "firm profits")
    require(result["consumer_surplus"] == p["b"]*Q*Q/2, "consumer surplus area")
    require(result["external_damage"] == p["h"]*Q*Q/2, "damage")
    require(result["tax_receipts"] == tax*Q and result["government_net_cash"] == tax*Q-administration, "government cash")
    require(result["real_administration"] == administration, "deployed versus no-policy administration")
    W = resource_welfare(p, q, kind)
    require(result["net_welfare"] == W and result["gross_welfare_before_administration"] == W+administration, "direct resource objective")
    require(W == result["consumer_surplus"]+sum(profits)+result["government_net_cash"]-result["external_damage"], "transfer cancellation")
    return W


def preference(kind, value, welfare):
    return (-welfare, {"none": 0, "tax": 1, "standard": 2}[kind], -value if kind == "standard" else value)


def certify_search(p, regime, kind, search):
    branches = search["affine_regions"]
    require(branches, "nonempty branch certificate")
    intervals, candidates = [], set()
    for branch in branches:
        lo, hi = branch["lower"], branch["upper"]
        require(0 <= lo <= hi <= p[kind], "reported feasible interval")
        intervals.append((lo, hi))
        def q_at(x):
            return [a+b*x for a, b in branch["q_affine"]]
        if kind == "standard":
            require(not any(lo < u < hi for u in p["u"]), "physical-cap kinks must split intervals")
        # For a fixed state and cap segment all equations/inequalities are affine.
        # Their validity at both endpoints therefore certifies the whole interval.
        for x in (lo, hi):
            q = q_at(x)
            caps = capacities(p, kind, x)
            gs = gradients(p, q, regime, x if kind == "tax" else F(0))
            for amount, cap, g, status in zip(q, caps, gs, branch["states"]):
                require(0 <= amount <= cap, "certificate quantities feasible")
                if status == "lower":
                    require(amount == 0 and g <= 0, "zero-output optimality certificate")
                elif status == "upper":
                    require(amount == cap and g >= 0, "upper-output optimality certificate")
                else:
                    require(status == "interior" and g == 0, "interior optimality certificate")
            require(q == scalar_equilibrium(p, regime, kind, x), "branch endpoint reference equilibrium")
        candidates.update((lo, hi))
        if hi > lo:
            length = hi-lo
            y0 = resource_welfare(p, q_at(lo), kind)
            ym = resource_welfare(p, q_at((lo+hi)/2), kind)
            y1 = resource_welfare(p, q_at(hi), kind)
            quadratic = 2*(y1-2*ym+y0)/(length*length)
            linear = (y1-y0)/length-quadratic*length
            require(quadratic <= 0, "independent welfare curvature")
            if quadratic < 0:
                vertex = lo-linear/(2*quadratic)
                if lo <= vertex <= hi:
                    candidates.add(vertex)
    covered = F(0)
    for lo, hi in sorted(intervals):
        require(lo <= covered, "policy interval coverage has no gaps")
        covered = max(covered, hi)
    require(covered == p[kind], "coverage includes policy upper boundary")
    expected = [(x, resource_welfare(p, scalar_equilibrium(p, regime, kind, x), kind)) for x in candidates]
    expected.sort(key=lambda item: preference(kind, item[0], item[1]))
    best = search["optimum_deployed_instrument"]
    require((best["policy"]["value"], verify_ledger(p, best, regime)) == expected[0], "global policy optimum from independently certified branches")
    require({r["value"] for r in search["candidate_audit"]} == candidates, "all endpoints and stationary candidates preserved")
    for row in search["candidate_audit"]:
        q = scalar_equilibrium(p, regime, kind, row["value"])
        require(row["quantities"] == q and row["net_welfare"] == resource_welfare(p, q, kind), "candidate audit values")
    return len(branches), len(candidates)


class Structure(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids, self.downloads, self.sources, self.forbidden = [], [], set(), []
        self.project_heading = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("h1", "html", "body", "script"):
            self.forbidden.append(tag)
        if "id" in a:
            self.ids.append(a["id"])
        if tag == "h2" and a.get("id") == "project":
            self.project_heading = True
        if tag == "a" and "download" in a:
            self.downloads.append(a["href"])
        if "data-source" in a:
            self.sources.add(a["data-source"])


def check():
    checks = []
    spec = importlib.util.spec_from_file_location("v05_project_benchmark", PROGRAM)
    lab = importlib.util.module_from_spec(spec)
    quiet = io.StringIO()
    with redirect_stdout(quiet):
        spec.loader.exec_module(lab)
        data = json.loads(DATA.read_text())
        result = lab.analyze(data)
    require(not quiet.getvalue(), "benchmark import and analyze must be quiet")
    rows = {r["id"]: r for r in data["scenarios"]}
    reports = {r["id"]: r for r in result["scenarios"]}
    require(set(rows) == set(reports) and len(rows) == 7, "seven complete scenarios")
    branch_count = candidate_count = 0
    for name, row in rows.items():
        p = primitives(row)
        report = reports[name]
        verify_ledger(p, report["efficient_target_without_administration"], "planner")
        for regime in ("competition", "cournot"):
            r = report[regime]
            verify_ledger(p, r["no_policy"], regime)
            for kind in ("tax", "standard"):
                branches, candidates = certify_search(p, regime, kind, r["policy_search"][kind])
                branch_count += branches
                candidate_count += candidates
            alternatives = [r["no_policy"]]+[s["optimum_deployed_instrument"] for s in r["policy_search"].values()]
            expected = min(alternatives, key=lambda z: preference(z["policy"]["kind"], z["policy"]["value"], z["net_welfare"]))
            require(r["recommended_feasible_policy"] == expected, "no-policy and fixed-administration global comparison")
    checks.append(f"Independent scalar output oracle and primitive ledger checks for seven scenarios/two regimes/planner; {branch_count} active intervals certify full policy domains and {candidate_count} endpoint/stationary candidates")

    expected = {
        "baseline": (("tax", "32", "1260"), ("tax", "16", "1260")),
        "low_damage": (("tax", "80/7", "12660/7"), ("none", "0", "1800")),
        "high_damage": (("standard", "80/11", "6015/11"), ("standard", "80/11", "6015/11")),
        "tight_capacity": (("none", "0", "1200"), ("none", "0", "1200")),
        "costly_administration": (("tax", "32", "1180"), ("none", "0", "1200")),
        "asymmetric_cost": (("tax", "136/5", "5244/5"), ("tax", "68/5", "5064/5")),
        "inactive_firm": (("tax", "80/3", "3140/3"), ("none", "0", "3200/3")),
    }
    for name, targets in expected.items():
        for regime, (kind, value, W) in zip(("competition", "cournot"), targets):
            r = reports[name][regime]["recommended_feasible_policy"]
            require(r["policy"] == {"kind": kind, "value": F(value)} and r["net_welfare"] == F(W), "instructor recommendation target")
    p = primitives(rows["baseline"])
    for regime, entries in result["baseline_instrument_comparisons"].items():
        require(len(entries) == 6, "baseline no-policy/four tax/standard comparisons")
        for entry in entries:
            verify_ledger(p, entry, regime)
    require(scalar_equilibrium(p, "planner") == [F(16), F(16)], "baseline target")
    require(scalar_equilibrium(p, "cournot", "tax", F(32)) == [F(12), F(12)], "mechanical marginal-damage tax contracts excessively")
    require(resource_welfare(p, [F(12), F(12)], "tax") == 1180, "mechanical tax net welfare")
    require(clip(F(80-16, 3), F(40)) == F(64, 3) > 16, "cap must bind against unrestricted best response")
    require(F(68)-F(60) == 8 and F(60)-(F(68)-16) == 8, "Cournot incidence")
    require(F(68)-F(140, 3) == F(64, 3) and F(140, 3)-36 == F(32, 3), "competitive incidence")
    a = primitives(rows["asymmetric_cost"])
    target = scalar_equilibrium(a, "planner")
    feasible_tax_q = scalar_equilibrium(a, "cournot", "tax", F(68, 5))
    require(target == [F(128, 5), F(8, 5)] and feasible_tax_q == [F(98, 5), F(38, 5)], "asymmetric vectors")
    require(sum(target) == sum(feasible_tax_q) and resource_welfare(a, target)-resource_welfare(a, feasible_tax_q) == 36, "same total with productive-allocation loss")
    require([a["h"]*sum(target)-a["b"]*x for x in target] == [F(8, 5), F(128, 5)], "excluded discriminatory-tax diagnostic")
    standard = reports["asymmetric_cost"]["cournot"]["policy_search"]["standard"]["optimum_deployed_instrument"]
    require(standard["policy"]["value"] == F(64, 3) and standard["net_welfare"] == F(8485, 9), "asymmetric standard global optimum")
    for s in (F(0), F(7), F(14), F(64, 3), F(23), F(40)):
        expected_q = [s, s] if s <= 14 else [s, (56-s)/3] if s <= 23 else [F(23), F(11)]
        require(scalar_equilibrium(a, "cournot", "standard", s) == expected_q, "asymmetric standard three branches")
    require(reports["inactive_firm"]["cournot"]["no_policy"]["quantities"] == [F(80, 3), F(0)], "inactive firm lower bound")
    require(reports["tight_capacity"]["cournot"]["no_policy"]["quantities"] == [F(12), F(12)], "both physical upper bounds")
    checks.append("All 14 instructor policy/welfare targets, baseline tax/cap implementation and incidence, asymmetric three-branch standard and exact 36 allocation loss, zero-output and capacity corners")

    for stress in result["fixed_baseline_policy_stress"]:
        p = primitives(rows[stress["scenario_id"]])
        for key, kind in (("unchanged_baseline_tax", "tax"), ("unchanged_baseline_standard", "standard")):
            require(stress[key]["policy"] == {"kind": kind, "value": F(16)}, "stress policy held fixed")
            verify_ledger(p, stress[key], "cournot")
    u = result["damage_uncertainty"]
    mean_h = sum(F(s["probability"])*F(rows[s["scenario_id"]]["damage_slope"]) for s in data["damage_uncertainty"]["states"])
    require(mean_h == u["mean_damage_slope"] == F(25, 16), "probability weighted damage slope")
    mean_p = primitives(rows["baseline"])
    mean_p["h"] = mean_h
    ur = u["cournot_fixed_policy_search"]
    for kind in ("tax", "standard"):
        certify_search(mean_p, "cournot", kind, ur["policy_search"][kind])
    choice = ur["recommended_feasible_policy"]
    require(choice["policy"] == {"kind": "tax", "value": F(1360, 49)}, "fixed ex ante optimum")
    require(choice["total_output"] == F(1280, 49) and u["expected_net_welfare"] == F(50220, 49), "ex ante output and net welfare")
    require(ur["policy_search"]["standard"]["optimum_deployed_instrument"]["net_welfare"] == F(49485, 49), "ex ante standard")
    expected_W = F(0)
    retained_tax = retained_standard = retained_none = F(0)
    for state in u["state_results_at_fixed_chosen_policy"]:
        p = primitives(rows[state["scenario_id"]])
        require(state["ledger"]["policy"] == choice["policy"], "same chosen policy in every realized state")
        expected_W += state["probability"]*verify_ledger(p, state["ledger"], "cournot")
        retained_tax += state["probability"]*resource_welfare(p, [F(16), F(16)], "tax")
        retained_standard += state["probability"]*resource_welfare(p, [F(16), F(16)], "standard")
        retained_none += state["probability"]*resource_welfare(p, [F(20), F(20)])
    require(expected_W == F(50220, 49) and (retained_tax, retained_standard, retained_none) == (972, 957, 750), "weighted state outcomes and original fixed policies")
    require(len(result["chart_values"]) == 41 and result["chart_no_policy_reference"] == 1200, "chart inventory/reference")
    for i, row in enumerate(result["chart_values"]):
        require(row["tax"] == i and row["net_welfare"] == 1180+10*i-F(5, 16)*i*i, "chart quadratic, not optimization grid")
    checks.append("Fixed-policy stress preserves tax/standard 16; ex ante weights give h=25/16, tax=1360/49 and welfare=50220/49; original policies yield 972/957 versus no-policy 750; all 41 chart points verified")

    # Input changes must propagate rather than merely replay saved target values.
    reverse = deepcopy(data)
    for row in reverse["scenarios"]:
        row["firms"].reverse()
    changed = lab.analyze(reverse)
    for before, after in zip(result["scenarios"], changed["scenarios"]):
        for regime in ("competition", "cournot"):
            b, a = before[regime]["recommended_feasible_policy"], after[regime]["recommended_feasible_policy"]
            require(a["policy"] == b["policy"] and a["net_welfare"] == b["net_welfare"] and a["quantities"] == b["quantities"][::-1], "firm relabeling equivariance")
    altered = deepcopy(data)
    altered["scenarios"][5]["damage_slope"] = "2"
    altered_result = lab.analyze(altered)["scenarios"][5]
    altered_p = primitives(altered["scenarios"][5])
    for regime in ("competition", "cournot"):
        for kind in ("tax", "standard"):
            certify_search(altered_p, regime, kind, altered_result[regime]["policy_search"][kind])
    require(altered_result["cournot"]["recommended_feasible_policy"]["net_welfare"] != reports["asymmetric_cost"]["cournot"]["recommended_feasible_policy"]["net_welfare"], "changed damage changes optimization")
    checks.append("Mutation audit: reversing all firm records reverses quantities without changing policy/welfare; altered asymmetric damage reoptimizes and passes independent global certificates")

    invalid = []
    def mutation(label, path, value):
        d = deepcopy(data)
        target = d
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value
        invalid.append((label, d))
    for value in (True, 1.0, None, "1/0"):
        mutation(f"bad rational {value!r}", ["scenarios", 0, "demand_slope"], value)
    mutation("negative damage", ["scenarios", 0, "damage_slope"], "-1")
    mutation("nonconvex cost", ["scenarios", 0, "firms", 0, "quadratic_cost"], "0")
    mutation("negative capacity", ["scenarios", 0, "firms", 0, "capacity"], "-1")
    mutation("negative price domain", ["scenarios", 0, "firms", 0, "capacity"], "90")
    mutation("duplicate firm", ["scenarios", 0, "firms", 1, "id"], "F1")
    mutation("duplicate scenario", ["scenarios", 1, "id"], "baseline")
    mutation("wrong dimensions", ["scenarios", 0, "firms"], [])
    mutation("negative administration", ["scenarios", 0, "tax_administration"], "-1")
    mutation("invalid probability sum", ["damage_uncertainty", "states", 0, "probability"], "1/2")
    mutation("unknown uncertainty state", ["damage_uncertainty", "states", 0, "scenario_id"], "missing")
    mutation("state changes private costs", ["scenarios", 1, "firms", 0, "linear_cost"], "21")
    mutation("wrong regime protocol", ["protocol", "regimes"], ["monopoly"])
    mutation("comparison tax infeasible", ["protocol", "baseline_report_tax_rates"], ["41"])
    mutation("comparison standard infeasible", ["protocol", "baseline_report_standard"], "-1")
    mutation("not marked synthetic", ["synthetic"], False)
    for label, variant in invalid:
        try:
            lab.analyze(variant)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid input accepted: "+label)
    original_hash = sha256(DATA.read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory(prefix="v05-project-check-") as folder:
        preserved = json.loads((DIR/"v05-project-output.json").read_text())
        require(lab.serializable(result) == preserved, "preserved exact output")
        for options in ([], ["-O"]):
            run = subprocess.run([sys.executable]+options+[str(PROGRAM)], cwd=folder, capture_output=True, text=True, timeout=15)
            require(run.returncode == 0 and not run.stderr and json.loads(run.stdout) == preserved, "default input from unrelated directory, including optimized Python")
        path = Path(folder)/"bad.json"
        for label, variant in invalid:
            path.write_text(json.dumps(variant))
            run = subprocess.run([sys.executable, "-O", str(PROGRAM), "--data", str(path)], cwd=folder, capture_output=True, text=True, timeout=15)
            require(run.returncode == 2 and not run.stdout and "Invalid market input:" in run.stderr and "Traceback" not in run.stderr, "CLI rejection: "+label)
    require(sha256(DATA.read_bytes()).hexdigest() == original_hash, "benchmark does not mutate frozen input")
    manifest = json.loads((DIR/"v05-project-manifest.json").read_text())
    require(len(manifest["files"]) == 3 and manifest["synthetic"] is True, "manifest scope")
    for entry in manifest["files"]:
        require("/" not in entry["name"] and entry["name"].startswith("v05-project-"), "flat manifest file")
        require(sha256((DIR/entry["name"]).read_bytes()).hexdigest() == entry["sha256"], "preserved input/program/output hash")
    checks.append(f"Executable contracts: quiet import, exact preserved output, three file hashes, unchanged input, unrelated working directory and -O; {len(invalid)} direct and optimized-CLI invalid cases rejected")

    html = (ROOT/"content/assessment-parts/v05-project.html").read_text()
    parsed = Structure()
    parsed.feed(html)
    require(parsed.project_heading and not parsed.forbidden, "project fragment heading/format")
    require(len(parsed.ids) == len(set(parsed.ids)) and all(x == "project" or x.startswith("v05-project-") for x in parsed.ids), "namespaced unique IDs")
    require(len(parsed.downloads) == 5 and all("/" not in x and (DIR/x).is_file() for x in parsed.downloads), "five existing flat downloads")
    require(all(x in html for x in ("100-point rubric", "15/20", "Complete instructor guide", "B−ΣC−tQ", "Critical errors", "1360/49", "8485/9")), "rubric, corrected objective and instructor scope")
    sources = json.loads((ROOT/"content/reviews/v05-project-sources.json").read_text())
    require(len(sources) == 3 and {s["id"] for s in sources} == parsed.sources, "three reused scoped source records")
    for source in sources:
        require(all(k in source for k in ("id", "title", "url", "use", "checked", "verification", "project_reuse")), "source reuse provenance")
    checks.append("Manuscript contracts: project anchor, unique prefixed IDs, five flat downloads, complete instructor/rubric/critical-error sections and three explicitly reused chapter method sources")
    report = {"status": "passed", "checks": checks, "limitations": [
        "Independent scalar roots and affine incentive certificates verify the supplied two-firm convex model and feasible instruments; they do not validate real conduct, demand, cost, damage or enforcement assumptions.",
        "Unweighted quasilinear welfare and lump-sum finance are stipulated criteria/assumptions. Neither a welfare increase nor this checker establishes Pareto compensation or ethical agreement.",
        "The uncertainty exercise permits damage changes only, with supplied weights and a single ex ante instrument. It is not estimation, a confidence interval or an adaptive policy experiment.",
        "Source records reuse accepted chapter primary inspections; project parameters, examples and proofs are original. No empirical dataset or current legal assertion is embedded.",
        "Human-readable proof, prompt/answer and policy interpretation still require editorial review. Root retains volume acceptance, integration and publication; no visual/mobile/print UI QA or external human certification is claimed."
    ]}
    json.dumps(report)
    return report


if __name__ == "__main__":
    print(json.dumps(check(), indent=2))
