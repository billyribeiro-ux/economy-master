"""Independent peer reconstruction of the original Tern project, standard library only."""
from contextlib import redirect_stdout
from copy import deepcopy
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from io import StringIO
from itertools import product
import json
from math import isclose, sqrt
from pathlib import Path
import runpy
import re

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "content/projects/v09-assessment-inputs.json"
MODEL = ROOT / "content/projects/v09-assessment-analysis.py"
OUTPUT = ROOT / "content/projects/v09-assessment-output.json"
REVIEWED = [
    "content/assessments/parts/v09-project.html",
    "content/projects/v09-assessment-inputs.json",
    "content/projects/v09-assessment-analysis.py",
    "content/projects/v09-assessment-output.json",
    "content/projects/v09-assessment-manifest.json",
    "content/projects/v09-assessment-README.txt",
    "scripts/check_v09_project.py",
    "content/reviews/v09-project-author.json",
    "content/reviews/v09-project-sources.json",
]


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def serial(value):
    if isinstance(value, F):
        return str(value)
    if isinstance(value, dict):
        return {k: serial(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [serial(v) for v in value]
    return value


class Audit:
    def __init__(self):
        self.comparisons = 0

    def equal(self, actual, expected, label):
        self.comparisons += 1
        require(serial(actual) == serial(expected), label)


def average(x):
    return sum(x, F(0)) / len(x)


def covariance(x, y):
    # Pairwise difference identity avoids reusing the author's centered-products route.
    n = len(x)
    return sum((x[i] - x[j]) * (y[i] - y[j])
               for i in range(n) for j in range(n)) / (2 * n * (n - 1))


def growth(x):
    out = F(1)
    for r in x:
        out *= 1 + r
    return out


def series(data, asset, periods, cutoff):
    values = {}
    rows = sorted(data["research"]["series_records"], key=lambda r: (r["released_on"], r["version"]))
    for row in rows:
        if row["asset"] == asset and row["released_on"] <= cutoff:
            values[row["period"]] = F(row["gross_return"]) - F(row["fee_on_beginning_nav"])
    closure = data["research"]["closures"].get(asset)
    if closure and closure["announced_on"] <= cutoff:
        values.update({t: F(0) for t in periods if t > closure["last_period"]})
    return [values[t] for t in periods]


def research_check(data, output, audit):
    r = data["research"]
    train, hold = r["training_periods"], r["holdout_periods"]
    cutoff, end = r["decision_cutoff"], r["evaluation_cutoff"]
    e, b = [series(data, a, train, cutoff) for a in ("E", "B")]
    bench = [(2 * x + 3 * y) / 5 for x, y in zip(e, b)]
    cohort = {a: series(data, a, train, cutoff) for a in r["initial_cohort"]}
    eligible = [a for a in r["manager_ids"] if r["admitted_on"][a] <= cutoff and
                not (a in r["closures"] and r["closures"][a]["announced_on"] <= cutoff)]
    means = {a: average([x - y for x, y in zip(cohort[a], bench)]) for a in eligible}
    selected = min(eligible, key=lambda a: (-means[a], a))
    actual = output["research"]
    audit.equal(actual["selected_manager"], selected, "point-in-time selected manager")
    audit.equal(actual["training_manager_benchmark"], bench, "rebalanced manager benchmark")
    for a in eligible:
        row = next(v for v in actual["eligible_ranked"] if v["asset"] == a)["statistics"]
        active = [x - y for x, y in zip(cohort[a], bench)]
        audit.equal(row["net_returns"], cohort[a], a + " available net returns")
        audit.equal(row["mean_net_active"], means[a], a + " active mean")
        audit.equal(row["sample_active_variance"], covariance(active, active), a + " tracking variance")
        slope = covariance(cohort[a], bench) / covariance(bench, bench)
        intercept = average(cohort[a]) - slope * average(bench)
        audit.equal(row["benchmark_slope"], slope, a + " sample slope")
        audit.equal(row["sample_intercept"], intercept, a + " sample intercept")
        audit.equal(row["sample_residual_squared_sum"], sum((x-intercept-slope*y)**2 for x, y in zip(cohort[a], bench)), a + " sample residual sum")
        if covariance(active, active) > 0:
            require(isclose(row["sample_information_ratio_approx"], float(means[a])/sqrt(float(covariance(active, active))), rel_tol=1e-12), a + " sample information ratio")
    audit.equal(next(v for v in actual["eligible_ranked"] if v["asset"] == "K")["statistics"]["sample_information_ratio_approx"], None, "zero tracking error has undefined IR")
    audit.equal(actual["training_full_cohort_return"], average([growth(v) for v in cohort.values()]) - 1, "full initial cohort")
    survivors = [a for a in cohort if a not in r["closures"]]
    audit.equal(actual["training_survivor_only_return"], average([growth(cohort[a]) for a in survivors]) - 1, "survivor exclusion")
    latest = {a: series(data, a, train, end) for a in r["manager_ids"] if a not in r["closures"]}
    revised = min(eligible, key=lambda a: (-average(latest[a]), a))
    backfilled = min(latest, key=lambda a: (-average(latest[a]), a))
    audit.equal(actual["retrospective_same_eligible_ranked"][0]["asset"], revised, "late revision changes retrospective rank")
    audit.equal(actual["late_backfilled_ranked"][0]["asset"], backfilled, "inadmissible backfill changes naive rank")
    metrics = {}
    for a in eligible:
        active = [x-y for x, y in zip(cohort[a], bench)]
        variance = covariance(active, active)
        metrics[a] = [means[a], growth(cohort[a])/growth(bench)-1, active[-1],
                      None if variance == 0 else float(means[a])/sqrt(float(variance))]
    winners = []
    for i in range(4):
        admissible = [a for a in eligible if metrics[a][i] is not None]
        winners.append(min(admissible, key=lambda a: (-metrics[a][i], a)) if admissible else None)
    audit.equal([row["winner"] for row in actual["search_log_results"]], winners, "all four disclosed dependent training trials")
    full = {a: growth(series(data, a, train + hold, end)) for a in cohort}
    audit.equal(actual["final_restated_cohort_growth_factors"], full, "restated entire cohort wealth")
    audit.equal(actual["final_restated_full_cohort_return"], average(list(full.values())) - 1, "restated full-cohort return")
    audit.equal(actual["final_restated_survivor_only_return"], average([full[a] for a in survivors]) - 1, "restated survivor-only return")
    eh, bh = [series(data, a, hold, end) for a in ("E", "B")]
    hb = [(2*x + 3*y)/5 for x, y in zip(eh, bh)]
    for a in eligible:
        values = series(data, a, hold, end)
        active = [x-y for x, y in zip(values, hb)]
        row = actual["holdout_statistics"][a]
        audit.equal(row["mean_net_active"], average(active), a + " held-out mean")
        audit.equal(row["sample_active_variance"], covariance(active, active), a + " held-out tracking variance")
        audit.equal(row["net_growth_factor"], growth(values), a + " held-out wealth")
        audit.equal(row["terminal_factor_difference"], growth(values)-growth(hb), a + " held-out matched wealth gap")
        slope = covariance(values, hb)/covariance(hb, hb)
        intercept = average(values)-slope*average(hb)
        audit.equal(row["benchmark_slope"], slope, a + " held-out descriptive slope")
        audit.equal(row["sample_intercept"], intercept, a + " held-out descriptive intercept")
        audit.equal(row["sample_residual_squared_sum"], sum((x-intercept-slope*y)**2 for x, y in zip(values, hb)), a + " held-out residual sum")
        require(isclose(row["sample_information_ratio_approx"], float(average(active))/sqrt(float(covariance(active, active))), rel_tol=1e-12), a + " held-out information ratio")
    return {"selected": selected, "training_active_means": means, "late_revision_winner": revised,
            "backfill_winner": backfilled, "training_E": e, "training_B": b,
            "holdout_factors": {"E": growth(eh), "B": growth(bh), "manager": growth(series(data, selected, hold, end))}}


def joint_covariance(data, research, output, audit):
    f = data["portfolio"]["forecast"]
    inputs = [research["training_E"], research["training_B"]]
    sample = [[covariance(x, y) for y in inputs] for x in inputs]
    sigma = [[2*sample[i][j] + F(f["prior_covariance"][i][j])/2 for j in range(2)] for i in range(2)]
    audit.equal(output["risk_model"]["quarterly_sample"], sample, "pairwise-difference sample covariance")
    audit.equal(output["risk_model"]["planning_factor_covariance"], sigma, "planning covariance blend")
    determinant = sigma[0][0]*sigma[1][1]-sigma[0][1]*sigma[1][0]
    audit.equal(output["risk_model"]["planning_determinant"], determinant, "positive factor determinant")
    require(sigma[0][0] > 0 and determinant > 0, "factor covariance is SPD")
    # Full E, B, manager, private-payoff covariance, retaining every cross term.
    load = [[F(1), F(0)], [F(0), F(1)], [F(2, 5), F(3, 5)],
            [F(f["private_equity_loading"]), F(f["private_bond_loading"])]]
    joint = [[sum(load[i][a]*sigma[a][b]*load[j][b] for a in range(2) for b in range(2))
              for j in range(4)] for i in range(4)]
    joint[2][2] += F(f["manager_residual_variance"])
    joint[3][3] += F(f["private_residual_variance"])
    # Enumerated bounded-law witness is separate from the rational quadratic calculation.
    root = sqrt(float(sigma[0][0])); cross = float(sigma[0][1])/root
    other = sqrt(float(sigma[1][1])-cross*cross)
    witness = []
    for u, v, m, p in product((-1, 1), repeat=4):
        fe, fb = root*u, cross*u+other*v
        witness.append([fe, fb, .4*fe+.6*fb+sqrt(float(F(f["manager_residual_variance"])))*m,
                        float(load[3][0])*fe+float(load[3][1])*fb+sqrt(float(F(f["private_residual_variance"])))*p])
    for i in range(4):
        for j in range(4):
            require(isclose(sum(row[i]*row[j] for row in witness)/16, float(joint[i][j]), rel_tol=1e-12, abs_tol=1e-10), "enumerated joint covariance witness")
    means = [1+float(F(f["equity_mean"])), 1+float(F(f["bond_mean"])),
             1+.4*float(F(f["equity_mean"]))+.6*float(F(f["bond_mean"]))-float(F(f["manager_annual_fee"]))+float(F(f["manager_overlay_lower"])),
             float(F(f["private_distribution_mean"]))]
    require(all(means[i]+row[i] > 0 for row in witness for i in range(4)), "all sixteen joint states have positive gross payoffs")
    return sigma, joint


def quadratic(x, cov):
    return sum(x[i]*cov[i][j]*x[j] for i in range(len(x)) for j in range(len(x)))


def liquid_holding(data, position):
    p = data["portfolio"]
    labels = ("E", "B", "manager")
    fee = sum(abs(position[i]-F(p["initial_liquid"][k]))*F(p["entry_cost_rates"][k]) for i, k in enumerate(labels))
    cash = F(p["initial_wealth"])-F(p["private_initial_value"])-sum(position)-fee
    return {**dict(zip(labels, position)), "fee": fee, "cash": cash}


def dated_ledger(data, h, scenario, sale=F(0), sale_price=F(0)):
    p = data["portfolio"]; g = F(p["cash_half_year_factor"])
    first = g*h["cash"] + sale*sale_price-F(scenario["call_t1"])-F(scenario["grant_t1"])
    if first < 0:
        return {"cash_after_t1": None, "terminal_reserve": None, "payments_funded": False}
    before_final = first*g + h["E"]*(1+F(scenario["equity_return"])) + (h["B"]-sale)*(1+F(scenario["bond_return"])) + h["manager"]*(1+F(scenario["manager_return"])) + F(scenario["private_distribution"])
    reserve = before_final-F(scenario["grant_t2"])
    return {"cash_after_t1": first, "terminal_reserve": reserve if reserve >= 0 else None,
            "payments_funded": reserve >= 0}


def portfolio_check(data, output, joint, audit):
    p = data["portfolio"]; f = p["forecast"]; policy = p["policy"]
    g = F(p["cash_half_year_factor"])
    labels = ("E", "B", "manager")
    bm = [F(p["benchmark"][k]) for k in labels]
    mean = [F(f["equity_mean"]), F(f["bond_mean"])]
    mean.append((2*mean[0]+3*mean[1])/5-F(f["manager_annual_fee"]))
    def assess(position):
        h = liquid_holding(data, position)
        variance = quadratic(list(position)+[F(1)], joint)
        active = quadratic([position[i]-bm[i] for i in range(3)]+[F(0)], joint)
        scenario = {**p["planning_flows"], "equity_return": mean[0], "bond_return": mean[1],
                    "manager_return": mean[2]+F(f["manager_overlay_lower"]), "private_distribution": f["private_distribution_mean"]}
        lower = dated_ledger(data, h, scenario)["terminal_reserve"]
        if lower is None:
            # Unfunded candidates are inadmissible; no hypothetical continuation is scored.
            return None
        upper = lower+h["manager"]*(F(f["manager_overlay_upper"])-F(f["manager_overlay_lower"]))
        penalty = F(policy["gamma"])*variance/(2*F(p["initial_wealth"]))
        margin = min([g*h["cash"]-F(p["planning_flows"]["call_t1"])-F(p["planning_flows"]["grant_t1"])] +
                     [g*h["cash"]-F(s["call_t1"])-F(s["grant_t1"]) for s in p["design_stresses"]])-F(policy["cash_buffer"])
        design = [dated_ledger(data, h, s) for s in p["design_stresses"]]
        valid = h["cash"] >= 0 and variance <= F(policy["total_variance_limit"]) and active <= F(policy["active_variance_limit"]) and margin >= 0 and all(row["terminal_reserve"] is not None and row["terminal_reserve"] >= F(policy["terminal_floor"]) for row in design)
        return {**h, "variance": variance, "active_variance": active, "lower_mean_reserve": lower,
                "upper_mean_reserve": upper, "robust_score": lower-penalty, "nominal_score": upper-penalty,
                "feasible": valid, "date1_cash_margin": margin, "stresses": design}
    axes = [range(0, int(F(p["caps"][k]))+1, int(F(p["lot"]))) for k in labels]
    candidates = [tuple(map(F, row)) for row in product(*axes)]
    feasible = [row for pos in candidates if (row := assess(pos)) is not None and row["feasible"]]
    def key(row, score="robust_score"):
        return (-row[score], row["variance"], row["fee"], row["E"], row["B"], row["manager"])
    ranked = sorted(feasible, key=key)
    nominal = min(feasible, key=lambda row: key(row, "nominal_score"))
    audit.equal(output["optimization"]["candidate_count"], len(candidates), "full original grid count")
    audit.equal(output["optimization"]["feasible_count"], len(feasible), "independent complete feasibility count")
    fields = list(output["optimization"]["robust_ranked"][0])
    audit.equal(output["optimization"]["robust_ranked"], [{k: row[k] for k in fields} for row in ranked], "every ranked feasible portfolio and score")
    benchmark = assess(tuple(bm))
    require(benchmark is not None and benchmark["feasible"], "independent benchmark feasibility")
    for label, row in (("robust", ranked[0]), ("nominal", nominal), ("benchmark", benchmark)):
        target = output["benchmark"] if label == "benchmark" else output["optimization"][label]
        for k in fields+["date1_cash_margin"]:
            audit.equal(target[k], row[k], label+" "+k)
        for scenario, ledger in zip(p["design_stresses"], row["stresses"]):
            for k, value in ledger.items():
                audit.equal(target["stresses"][scenario["name"]][k], value, label+" design ledger "+k)
    return ranked[0], nominal, benchmark, feasible, assess


def guide_interventions(data, output, feasible, research, audit):
    # The guide's objective edits do not change feasibility, so rerank independently.
    W = F(data["portfolio"]["initial_wealth"])
    def rank(gamma, upper):
        mean_key = "upper_mean_reserve" if upper else "lower_mean_reserve"
        return min(feasible, key=lambda h: (-(h[mean_key]-F(gamma)*h["variance"]/(2*W)),
                                           h["variance"], h["fee"], h["E"], h["B"], h["manager"]))
    gamma6 = {"robust": rank(6, False), "nominal": rank(6, True)}
    audit.equal([gamma6["robust"][k] for k in ("E", "B", "manager")], [F(250), F(325), F(0)], "guide higher-risk-aversion robust policy")
    audit.equal([gamma6["nominal"][k] for k in ("E", "B", "manager")], [F(250), F(300), F(25)], "guide higher-risk-aversion nominal policy")
    singleton = rank(4, False)
    audit.equal([singleton[k] for k in ("E", "B", "manager")], [F(325), F(250), F(0)], "guide singleton-overlay objectives agree")
    # The two guide research edits alter only the selected manager's realized leg.
    nominal = output["optimization"]["nominal"]
    initial = F(output["realized_report"]["cash_ledgers"]["nominal_counterfactual"]["terminal_reserve"])
    end = data["research"]["evaluation_cutoff"]
    gm = growth(series(data, "M", [5, 6, 7, 8], end))
    earlier_revision = initial+F(nominal["manager"])*(gm-research["holdout_factors"]["manager"])
    audit.equal(earlier_revision, F(7543884431, 8000000), "guide early-M-revision nominal report")
    k = series(data, "K", [5, 6, 7, 8], end)
    k[0] += F(1, 10)
    heldout = initial+F(nominal["manager"])*(growth(k)-research["holdout_factors"]["manager"])
    audit.equal(heldout, F(7545697583, 8000000), "guide held-out-period-five nominal report")
    return {"gamma6": {name: [h[k] for k in ("E", "B", "manager")] for name, h in gamma6.items()},
            "early_revision_nominal_reserve": earlier_revision, "heldout_intervention_nominal_reserve": heldout}


def execution_and_stress(data, output, research, robust, nominal, benchmark, feasible, assess, audit):
    p = data["portfolio"]; old = p["initial_liquid"]
    intended_sale = F(old["B"])-robust["B"]
    sold = min(intended_sale, F(p["execution"]["available_bond_sale_units"]))
    bond = F(old["B"])-sold
    continuations = [h for h in feasible if h["B"] == bond and h["manager"] == robust["manager"] and F(old["E"]) <= h["E"] <= robust["E"]]
    actual = min(continuations, key=lambda h: (-h["robust_score"], h["variance"], h["fee"], h["E"]))
    naive = assess((robust["E"], bond, robust["manager"]))
    audit.equal(output["implementation"]["bond_sale_executed"], sold, "actual bond sale")
    audit.equal(output["implementation"]["unfilled_equity_buy"], robust["E"]-actual["E"], "canceled equity purchase")
    for k in ("E", "B", "manager", "fee", "cash", "variance", "active_variance", "date1_cash_margin"):
        audit.equal(output["implementation"]["authorized_fallback"][k], actual[k], "authorized actual "+k)
        audit.equal(output["implementation"]["naive_complete_equity_order"][k], naive[k], "naive order "+k)
    realized = {**p["realized_private"], **{k+"_return": v-1 for k, v in research["holdout_factors"].items()}}
    realized["equity_return"] = realized.pop("E_return")
    realized["bond_return"] = realized.pop("B_return")
    reserves = {}
    for name, h in (("target", robust), ("actual", actual), ("benchmark", benchmark), ("nominal_counterfactual", nominal)):
        ledger = dated_ledger(data, h, realized)
        reserves[name] = ledger["terminal_reserve"]
        for k, value in ledger.items():
            audit.equal(output["realized_report"]["cash_ledgers"][name][k], value, name+" realized "+k)
    decomposition = output["realized_report"]["reserve_gap_decomposition"]
    audit.equal(decomposition["policy_selection"], reserves["target"]-reserves["benchmark"], "policy selection wealth")
    audit.equal(decomposition["implementation"], reserves["actual"]-reserves["target"], "implementation wealth")
    audit.equal(decomposition["total"], reserves["actual"]-reserves["benchmark"], "total matched wealth")
    actual_minus_target = sum((actual[k]-robust[k])*research["holdout_factors"][k] for k in ("E", "B", "manager")) + (actual["cash"]-robust["cash"])*F(p["cash_half_year_factor"])**2
    audit.equal(actual_minus_target, reserves["actual"]-reserves["target"], "direct liquid holdings explain implementation")
    audit.equal(F(decomposition["target_minus_actual_opportunity_component"])+F(decomposition["fee_difference_at_terminal"])+F(decomposition["cash_principal_timing_adjustment"]), -actual_minus_target, "reported components conserve terminal wealth")
    s = p["outside_stress"]; price = F(s["bond_t1_mark"])-F(s["bond_spread_per_original_unit"])-F(s["bond_fee_per_original_unit"])
    g = F(p["cash_half_year_factor"])
    required = max(F(0), (F(s["call_t1"])+F(s["grant_t1"])+F(p["policy"]["cash_buffer"])-robust["cash"]*g)/price)
    sold = min(required, robust["B"], F(s["bond_sale_capacity"]))
    outside = dated_ledger(data, robust, s, sold, price)
    audit.equal(output["outside_design"]["required_original_units_for_buffer"], required, "emergency gross original units")
    for k, value in outside.items():
        audit.equal(output["outside_design"]["ledger"][k], value, "outside-design "+k)
    audit.equal(output["outside_design"]["external_funding_at_terminal_to_restore_floor"], F(p["policy"]["terminal_floor"])-outside["terminal_reserve"], "remaining external resource gap")
    audit.equal(F(output["outside_design"]["gross_marked_value_removed"]), sum(F(output["outside_design"][k]) for k in ("spread_cost", "fee_cost", "net_cash_raised")), "sale marked value conservation")
    return {"actual": {k: actual[k] for k in ("E", "B", "manager", "fee", "cash")},
            "realized_reserves": reserves, "outside_required_sale": required, "outside_terminal": outside["terminal_reserve"]}


def intervention_check(data, output, model, robust, research, required_sale, audit):
    rejected, valid = [], []
    def reject(name, changed):
        try:
            model["validate"](changed)
        except ValueError:
            rejected.append(name)
        else:
            raise AssertionError("invalid intervention accepted: "+name)
    for period, changed_date in ((8, "2026-01-02"), (6, "2025-07-02")):
        changed = deepcopy(data)
        for row in changed["research"]["series_records"]:
            if row["period"] == period:
                row["observation_end"] = changed_date
        reject("uniform-period-"+str(period)+"-boundary-shift", changed)
    changed = deepcopy(data)
    changed["portfolio"]["outside_stress"]["bond_fee_per_original_unit"] = ".98"
    reject("nonpositive-net-contingency-sale-price", changed)
    changed = deepcopy(data)
    changed["portfolio"]["forecast"]["prior_covariance"] = [[".01", ".01"], [".01", ".01"]]
    reject("singular-prior-covariance", changed)
    changed = deepcopy(data)
    changed["research"]["series_records"][0]["released_on"] = "2024-03-30"
    reject("release-before-observation-end", changed)
    changed = deepcopy(data)
    changed["portfolio"]["initial_wealth"] = True
    reject("boolean-financial-amount", changed)
    changed = deepcopy(data)
    for row in changed["research"]["series_records"]:
        if row["asset"] == "M" and row["version"] == 2:
            row["released_on"] = "2025-01-02"
    model["validate"](changed)
    audit.equal(model["research_audit"](changed)["selected_manager"], "M", "eligible earlier revision changes selection")
    valid.append("earlier-revision-information-set")
    changed = deepcopy(data)
    for row in changed["research"]["series_records"]:
        if row["asset"] == "K" and row["period"] == 8:
            row["gross_return"] = str(F(row["gross_return"])+F(1, 100))
    changed_result = model["run"](changed)
    for key in ("optimization", "risk_model", "benchmark", "implementation"):
        audit.equal(changed_result[key], output[key], "holdout edit cannot change "+key)
    audit.equal(changed_result["research"]["selected_manager"], research["selected"], "holdout cannot retune selection")
    audit.equal(changed_result["research"]["holdout_statistics"]["K"]["net_growth_factor"], growth(series(changed, "K", [5, 6, 7, 8], changed["research"]["evaluation_cutoff"])), "holdout evaluation responds")
    valid.append("held-out-return-isolation")
    changed = deepcopy(data)
    changed["portfolio"]["execution"]["available_bond_sale_units"] = "100"
    complete = model["run"](changed)
    audit.equal(complete["implementation"]["authorized_fallback"]["E"], robust["E"], "complete bond execution permits target E")
    audit.equal(complete["realized_report"]["reserve_gap_decomposition"]["implementation"], F(0), "complete target has zero implementation difference")
    valid.append("full-entry-fill")
    for name, cap in (("exact-buffer-sale-capacity", required_sale), ("capacity-just-below-buffer", required_sale-F(1, 10000)), ("twenty-unit-capacity", F(20)), ("zero-unit-capacity", F(0))):
        changed = deepcopy(data)
        changed["portfolio"]["outside_stress"]["bond_sale_capacity"] = str(cap)
        model["validate"](changed)
        answer = model["forced_sale"](changed, robust)
        ledger = answer["ledger"]
        if name == "exact-buffer-sale-capacity":
            audit.equal(ledger["cash_after_t1"], F(20), "exact cash-buffer boundary")
        elif cap == 0:
            require(not ledger["payments_funded"] and ledger["cash_after_t1"] is None and ledger["terminal_reserve"] is None, "unfunded call has no invented continuation")
        else:
            require(ledger["payments_funded"] and ledger["buffer_gap_t1"] > 0 and not ledger["cash_and_floor_pass"], "funded payment can still fail cash policy")
        valid.append(name)
    return {"rejected": rejected, "valid": valid}


def numerical_review():
    """Can be run before the author freezes the guide; never issues final acceptance."""
    data = json.loads(INPUT.read_text())
    reference = json.loads(OUTPUT.read_text())
    original = deepcopy(data)
    captured = StringIO()
    with redirect_stdout(captured):
        model = runpy.run_path(str(MODEL))
        generated = model["run"](data)
    require(not captured.getvalue(), "model import and run must remain quiet")
    audit = Audit()
    audit.equal(data, original, "run preserves caller input")
    audit.equal(generated, reference, "entire canonical reference output")
    research = research_check(data, reference, audit)
    sigma, joint = joint_covariance(data, research, reference, audit)
    robust, nominal, benchmark, feasible, assess = portfolio_check(data, reference, joint, audit)
    guide = guide_interventions(data, reference, feasible, research, audit)
    implementation = execution_and_stress(data, reference, research, robust, nominal, benchmark, feasible, assess, audit)
    interventions = intervention_check(data, reference, model, robust, research, implementation["outside_required_sale"], audit)
    return serial({"status": "passed", "comparisons": audit.comparisons,
                   "candidate_count": reference["optimization"]["candidate_count"], "feasible_count": len(feasible),
                   "research": {k: research[k] for k in ("selected", "training_active_means", "late_revision_winner", "backfill_winner")},
                   "factor_covariance": sigma, "joint_claim_covariance": joint,
                   "robust": {k: robust[k] for k in ("E", "B", "manager", "fee", "cash", "variance", "active_variance", "robust_score")},
                   "nominal": {k: nominal[k] for k in ("E", "B", "manager", "nominal_score")},
                   "implementation": implementation, "interventions": interventions, "guide_interventions": guide})


class ProjectStructure(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack, self.ids, self.links, self.words = [], set(), [], []
        self.scores, self.guide_items, self.deliverables = [], 0, 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "id" in a:
            require(a["id"] not in self.ids, "unique project anchors")
            self.ids.add(a["id"])
        require(tag != "h1", "fragment does not duplicate title")
        if "data-points" in a:
            self.scores.append(int(a["data-points"]))
        if tag == "li" and self.stack and self.stack[-1][0] == "ol":
            if any(t == "details" and "solutions" in attributes.get("class", "").split() for t, attributes in self.stack):
                self.guide_items += 1
            elif "project-deliverables" in self.stack[-1][1].get("class", "").split():
                self.deliverables += 1
        if tag == "a":
            self.links.append(a.get("href", ""))
        if tag not in ("br", "hr", "img", "input", "meta", "link"):
            self.stack.append((tag, a))

    def handle_endtag(self, tag):
        require(self.stack and self.stack[-1][0] == tag, "balanced project HTML: "+tag)
        self.stack.pop()

    def handle_data(self, value):
        self.words.append(value)


def artifact_review():
    for relative in REVIEWED:
        require((ROOT/relative).is_file(), "final author payload missing: "+relative)
    path = ROOT/REVIEWED[0]
    text = path.read_text()
    parser = ProjectStructure()
    parser.feed(text); parser.close()
    require(not parser.stack and parser.deliverables == 6 and parser.guide_items == 8, "complete six-deliverable/eight-guide structure")
    require(parser.scores == [20, 20, 20, 20, 10, 10], "complete hundred-point analytic rubric")
    require(all(token in text for token in ("85/100", "15/20", "7.5/10", "Critical errors", "Carry forward")), "domain floors and critical/error-carry-forward policy")
    sources = json.loads((ROOT/"content/reviews/v09-project-sources.json").read_text())
    catalog = {row["id"]: row for row in json.loads((ROOT/"content/sources.json").read_text())}
    require(len(sources) == 5 and all(row == catalog.get(row["id"]) for row in sources), "exact accepted source scopes")
    require(all("sources.html#"+row["id"] in parser.links for row in sources), "every method source is actually linked")
    for name in ("inputs.json", "analysis.py", "output.json", "manifest.json", "README.txt"):
        require("v09-assessment-"+name in parser.links, "flat published project asset route")
    manifest = json.loads((ROOT/"content/projects/v09-assessment-manifest.json").read_text())
    require([r["file"] for r in manifest["files"]] == ["v09-assessment-"+name for name in ("inputs.json", "analysis.py", "output.json", "README.txt")], "four-file distributed manifest perimeter")
    for row in manifest["files"]:
        raw = (ROOT/"content/projects"/row["file"]).read_bytes()
        require(row["bytes"] == len(raw) and row["sha256"] == sha256(raw).hexdigest(), "exact final manifest payload")
    author = json.loads((ROOT/"content/reviews/v09-project-author.json").read_text())
    expected = set(REVIEWED)-{"content/reviews/v09-project-author.json"}
    require({row["path"] for row in author["reviewed_hashes"]} == expected, "author hashes all eight non-self payloads")
    for row in author["reviewed_hashes"]:
        raw = (ROOT/row["path"]).read_bytes()
        require(row["bytes"] == len(raw) and row["sha256"] == sha256(raw).hexdigest(), "author record matches final payload")
    require(author["open_findings"] == [], "author has no open material finding")
    return {"deliverables": parser.deliverables, "instructor_items": parser.guide_items,
            "rubric_points": sum(parser.scores), "source_records": len(sources),
            "words_including_guide": len(re.findall(r"\S+", " ".join(parser.words)))}


def check():
    result = numerical_review()
    result["structure"] = artifact_review()
    result["task"] = "v09-project-peer"
    result["reviewed_payloads"] = {relative: {"sha256": sha256((ROOT/relative).read_bytes()).hexdigest(),
                                            "bytes": (ROOT/relative).stat().st_size} for relative in REVIEWED}
    result["limits"] = "Independent conditional numerical/domain review; the accompanying peer record documents full prose, source-scope and author-checker reading. No human certification or UI QA."
    json.dumps(result, allow_nan=False)
    return result


if __name__ == "__main__":
    print(json.dumps(check(), indent=2, allow_nan=False))
