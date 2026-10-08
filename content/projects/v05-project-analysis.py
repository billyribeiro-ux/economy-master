"""Exact two-firm market intervention benchmark; standard library, offline.

Enumerates lower/interior/upper output states. Every feasible policy interval
has affine outputs and quadratic welfare, so endpoints and stationary points
give a global comparison. No grid approximation is used for optimization.
"""
import argparse
from copy import deepcopy
from fractions import Fraction as F
from itertools import product
import json
from pathlib import Path

DEFAULT_INPUT = Path(__file__).with_name("v05-project-data.json")
REGIMES = ("competition", "cournot")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def number(value, label):
    require(type(value) is int or isinstance(value, str), f"{label}: use an integer or rational string")
    try:
        return F(value)
    except (ValueError, ZeroDivisionError):
        raise ValueError(f"{label}: invalid finite rational") from None


def validate(data):
    require(isinstance(data, dict) and data.get("synthetic") is True, "explicit synthetic object required")
    rows = data.get("scenarios")
    require(isinstance(rows, list) and 1 <= len(rows) <= 20, "one through twenty scenarios required")
    cases = []
    for row in rows:
        require(isinstance(row, dict), "scenario must be an object")
        require(isinstance(row.get("id"), str) and row["id"], "scenario ID required")
        case = {k: number(row.get(k), k) for k in (
            "demand_intercept", "demand_slope", "damage_slope", "tax_ceiling",
            "standard_ceiling", "tax_administration", "standard_administration")}
        case.update(id=row["id"], label=row.get("label", row["id"]))
        require(case["demand_intercept"] > 0 and case["demand_slope"] > 0, "positive demand intercept/slope required")
        require(all(case[k] >= 0 for k in ("damage_slope", "tax_ceiling", "tax_administration", "standard_administration")), "nonnegative damage, tax bound and administration required")
        require(case["standard_ceiling"] > 0, "positive standard bound required")
        firms = row.get("firms")
        require(isinstance(firms, list) and len(firms) == 2, "exactly two firms required")
        case["firms"] = []
        for firm in firms:
            require(isinstance(firm, dict) and isinstance(firm.get("id"), str) and firm["id"], "firm ID required")
            f = {k: number(firm.get(k), k) for k in ("linear_cost", "quadratic_cost", "capacity")}
            f["id"] = firm["id"]
            require(f["linear_cost"] >= 0 and f["quadratic_cost"] > 0 and f["capacity"] > 0, "nonnegative linear cost, strictly convex cost and positive capacity required")
            case["firms"].append(f)
        require(len({f["id"] for f in case["firms"]}) == 2, "unique firm IDs required")
        require(case["demand_slope"]*sum(f["capacity"] for f in case["firms"]) <= case["demand_intercept"], "linear demand must stay nonnegative on the entire feasible output box")
        require(case["standard_ceiling"] >= max(f["capacity"] for f in case["firms"]), "standard bound must include the unconstrained physical box")
        cases.append(case)
    require(len({c["id"] for c in cases}) == len(cases), "unique scenario IDs required")
    require(cases[0]["id"] == "baseline", "first scenario must be baseline")
    uncertainty = data.get("damage_uncertainty")
    require(isinstance(uncertainty, dict) and isinstance(uncertainty.get("states"), list) and uncertainty["states"], "damage uncertainty states required")
    by_id = {c["id"]: c for c in cases}
    states = []
    for state in uncertainty["states"]:
        require(isinstance(state, dict) and state.get("scenario_id") in by_id, "unknown uncertainty state")
        probability = number(state.get("probability"), "probability")
        require(probability > 0, "strictly positive state weights required")
        states.append((by_id[state["scenario_id"]], probability))
    require(sum(p for _, p in states) == 1 and len({c["id"] for c, _ in states}) == len(states), "unique states and unit probability sum required")
    economic_keys = set(cases[0]) - {"id", "label", "damage_slope"}
    require(all(all(c[k] == cases[0][k] for k in economic_keys) for c, _ in states), "uncertainty exercise may vary damage only")
    return cases, states


def add(a, b):
    return (a[0]+b[0], a[1]+b[1])


def scale(a, k):
    return (a[0]*k, a[1]*k)


def at(a, x):
    return a[0]+a[1]*x


def restrict(lo, hi, nonnegative):
    a, b = nonnegative
    if b > 0:
        lo = max(lo, -a/b)
    elif b < 0:
        hi = min(hi, -a/b)
    elif a < 0:
        return None
    return (lo, hi) if lo <= hi else None


def regions(case, regime, tax, caps, lo, hi):
    """Exact affine solution and validity interval for every active output set."""
    require(regime in REGIMES + ("planner",), "unknown regime")
    A, b, h = (case[k] for k in ("demand_intercept", "demand_slope", "damage_slope"))
    cross = b+h if regime == "planner" else b
    strategic = b if regime == "cournot" else F(0)
    fs = case["firms"]
    diagonal = [f["quadratic_cost"]+cross+strategic for f in fs]
    for statuses in product(("lower", "interior", "upper"), repeat=2):
        q = [(F(0), F(0)) if s == "lower" else caps[i] if s == "upper" else None
             for i, s in enumerate(statuses)]
        inside = [i for i, s in enumerate(statuses) if s == "interior"]
        rhs = [add((A-f["linear_cost"], F(0)), scale(tax, -1)) for f in fs]
        if len(inside) == 1:
            i = inside[0]
            q[i] = scale(add(rhs[i], scale(q[1-i], -cross)), 1/diagonal[i])
        elif len(inside) == 2:
            determinant = diagonal[0]*diagonal[1]-cross**2
            q = [scale(add(scale(rhs[i], diagonal[1-i]), scale(rhs[1-i], -cross)), 1/determinant) for i in (0, 1)]
        total = add(q[0], q[1])
        interval = (lo, hi)
        for i, status in enumerate(statuses):
            constraints = [q[i], add(caps[i], scale(q[i], -1))]
            gradient = add(add(rhs[i], scale(total, -cross)), scale(q[i], -(fs[i]["quadratic_cost"]+strategic)))
            if status == "lower":
                constraints.append(scale(gradient, -1))
            elif status == "upper":
                constraints.append(gradient)
            for condition in constraints:
                interval = restrict(*interval, condition)
                if interval is None:
                    break
            if interval is None:
                break
        if interval is not None:
            yield {"lower": interval[0], "upper": interval[1], "q_affine": q, "states": statuses}


def equilibrium(case, regime, kind="none", value=F(0)):
    require(kind in ("none", "tax", "standard"), "unknown policy kind")
    if kind == "tax":
        require(0 <= value <= case["tax_ceiling"], "tax outside permitted interval")
    if kind == "standard":
        require(0 <= value <= case["standard_ceiling"], "standard outside permitted interval")
    require(kind != "none" or value == 0, "no policy has no nonzero parameter")
    caps = [(min(f["capacity"], value) if kind == "standard" else f["capacity"], F(0)) for f in case["firms"]]
    tax = (value if kind == "tax" else F(0), F(0))
    solutions = {tuple(at(x, F(0)) for x in branch["q_affine"])
                 for branch in regions(case, regime, tax, caps, F(0), F(0))}
    require(len(solutions) == 1, "active sets must produce one equilibrium")
    return list(next(iter(solutions)))


def ledger(case, regime, kind="none", value=F(0), quantities=None):
    q = equilibrium(case, regime, kind, value) if quantities is None else quantities
    A, b, h = (case[k] for k in ("demand_intercept", "demand_slope", "damage_slope"))
    Q = sum(q)
    price = A-b*Q
    tax = value if kind == "tax" else F(0)
    administration = F(0) if kind == "none" else case[kind+"_administration"]
    caps = [min(f["capacity"], value) if kind == "standard" else f["capacity"] for f in case["firms"]]
    costs = [f["linear_cost"]*x+f["quadratic_cost"]*x*x/2 for x, f in zip(q, case["firms"])]
    profits = [(price-tax)*x-c for x, c in zip(q, costs)]
    benefit = A*Q-b*Q*Q/2
    cs, revenue, damage = benefit-price*Q, tax*Q, h*Q*Q/2
    government = revenue-administration
    gross = benefit-sum(costs)-damage
    net = gross-administration
    require(net == cs+sum(profits)+government-damage, "transfer/resource ledger does not reconcile")
    return {"regime": regime, "policy": {"kind": kind, "value": value}, "quantities": q, "total_output": Q,
            "effective_output_bounds": caps,
            "active_bounds": ["zero_and_upper" if x == u == 0 else "zero" if x == 0 else "upper" if x == u else "interior" for x, u in zip(q, caps)],
            "buyer_price": price, "retained_price_after_tax": price-tax, "gross_benefit": benefit,
            "private_costs": costs, "consumer_surplus": cs, "firm_profits": profits,
            "tax_receipts": revenue, "real_administration": administration, "government_net_cash": government,
            "external_damage": damage, "gross_welfare_before_administration": gross, "net_welfare": net}


def welfare_coefficients(case, q):
    A, b, h = (case[k] for k in ("demand_intercept", "demand_slope", "damage_slope"))
    a, slope = add(q[0], q[1])
    constant = A*a-(b+h)*a*a/2
    linear = A*slope-(b+h)*a*slope
    quadratic = -(b+h)*slope*slope/2
    for (x, y), f in zip(q, case["firms"]):
        c, k = f["linear_cost"], f["quadratic_cost"]
        constant -= c*x+k*x*x/2
        linear -= c*y+k*x*y
        quadratic -= k*y*y/2
    return constant, linear, quadratic


def policy_regions(case, regime, kind):
    if kind == "tax":
        caps = [(f["capacity"], F(0)) for f in case["firms"]]
        yield from regions(case, regime, (F(0), F(1)), caps, F(0), case["tax_ceiling"])
    else:
        knots = sorted({F(0), case["standard_ceiling"], *(f["capacity"] for f in case["firms"])})
        for lo, hi in zip(knots[:-1], knots[1:]):
            caps = [(F(0), F(1)) if hi <= f["capacity"] else (f["capacity"], F(0)) for f in case["firms"]]
            yield from regions(case, regime, (F(0), F(0)), caps, lo, hi)


def preference(result):
    kind, value = result["policy"]["kind"], result["policy"]["value"]
    return (-result["net_welfare"], {"none": 0, "tax": 1, "standard": 2}[kind], -value if kind == "standard" else value)


def optimize(case, regime, kind):
    branches = list(policy_regions(case, regime, kind))
    candidates = set()
    for branch in branches:
        lo, hi = branch["lower"], branch["upper"]
        candidates.update((lo, hi))
        _, linear, quadratic = welfare_coefficients(case, branch["q_affine"])
        require(quadratic <= 0, "welfare along affine outputs must be concave")
        if quadratic < 0:
            stationary = -linear/(2*quadratic)
            if lo <= stationary <= hi:
                candidates.add(stationary)
    require(candidates, "no policy candidates found")
    results = [ledger(case, regime, kind, value) for value in sorted(candidates)]
    return {"optimum_deployed_instrument": min(results, key=preference),
            "candidate_audit": [{"value": r["policy"]["value"], "quantities": r["quantities"], "net_welfare": r["net_welfare"]} for r in results],
            "affine_regions": branches}


def scenario(case):
    answer = {"id": case["id"], "label": case["label"],
              "efficient_target_without_administration": ledger(case, "planner")}
    for regime in REGIMES:
        none = ledger(case, regime)
        searches = {kind: optimize(case, regime, kind) for kind in ("tax", "standard")}
        recommendation = min([none]+[x["optimum_deployed_instrument"] for x in searches.values()], key=preference)
        answer[regime] = {"no_policy": none, "policy_search": searches, "recommended_feasible_policy": recommendation}
    return answer


def analyze(data):
    cases, states = validate(data)
    reports = [scenario(case) for case in cases]
    baseline = cases[0]
    mean_case = deepcopy(baseline)
    mean_case["damage_slope"] = sum(c["damage_slope"]*p for c, p in states)
    mean_case["id"], mean_case["label"] = "ex_ante_damage", "Fixed policy before the damage state is known"
    uncertain = scenario(mean_case)["cournot"]
    chosen = uncertain["recommended_feasible_policy"]["policy"]
    outcomes = [{"scenario_id": c["id"], "probability": p, "ledger": ledger(c, "cournot", chosen["kind"], chosen["value"])} for c, p in states]
    expected = sum(o["probability"]*o["ledger"]["net_welfare"] for o in outcomes)
    require(expected == uncertain["recommended_feasible_policy"]["net_welfare"], "expected-damage reduction must reconcile")
    baseline_tax = reports[0]["cournot"]["policy_search"]["tax"]["optimum_deployed_instrument"]["policy"]["value"]
    baseline_standard = reports[0]["cournot"]["policy_search"]["standard"]["optimum_deployed_instrument"]["policy"]["value"]
    stress = [{"scenario_id": c["id"], "unchanged_baseline_tax": ledger(c, "cournot", "tax", baseline_tax),
               "unchanged_baseline_standard": ledger(c, "cournot", "standard", baseline_standard)} for c in cases]
    chart = [ledger(baseline, "cournot", "tax", baseline["tax_ceiling"]*F(i, 40)) for i in range(41)]
    protocol = data.get("protocol")
    require(isinstance(protocol, dict) and protocol.get("regimes") == list(REGIMES), "declared comparison regimes must match this benchmark")
    comparison_rates = protocol.get("baseline_report_tax_rates")
    require(isinstance(comparison_rates, list) and comparison_rates, "baseline comparison rates required")
    comparisons = {r: [ledger(baseline, r)]+[
        ledger(baseline, r, "tax", number(t, "comparison tax")) for t in comparison_rates]+[
        ledger(baseline, r, "standard", number(protocol.get("baseline_report_standard"), "comparison standard"))]
        for r in REGIMES}
    return {"project_id": data.get("project_id"), "synthetic": True, "scenarios": reports,
            "baseline_instrument_comparisons": comparisons,
            "fixed_baseline_policy_stress": stress,
            "damage_uncertainty": {"mean_damage_slope": mean_case["damage_slope"], "cournot_fixed_policy_search": uncertain,
                                   "state_results_at_fixed_chosen_policy": outcomes, "expected_net_welfare": expected},
            "chart_values": [{"tax": x["policy"]["value"], "output": x["total_output"], "net_welfare": x["net_welfare"]} for x in chart],
            "chart_no_policy_reference": reports[0]["cournot"]["no_policy"]["net_welfare"],
            "limitations": ["All primitives, probabilities and administration costs are supplied synthetic assumptions, not estimates.",
                            "Two price-taking technologies are a comparison benchmark, not evidence that two firms behave competitively.",
                            "Equal standards are nontradable firm bounds, not a competitive permit market.",
                            "Negative taxes, discriminatory instruments, entry, evasion and endogenous emission intensity are outside the feasible model.",
                            "Efficiency uses quasilinear unweighted surplus; no causal estimate, universal policy ranking or Pareto compensation is established."]}


def serializable(value):
    if isinstance(value, F):
        return str(value)
    if isinstance(value, dict):
        return {k: serializable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [serializable(x) for x in value]
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_INPUT)
    args = parser.parse_args()
    try:
        report = analyze(json.loads(args.data.read_text(encoding="utf-8")))
    except (ValueError, TypeError, KeyError, OSError, ZeroDivisionError) as error:
        parser.exit(2, f"Invalid market input: {error}\n")
    print(json.dumps(serializable(report), indent=2))


if __name__ == "__main__":
    main()
