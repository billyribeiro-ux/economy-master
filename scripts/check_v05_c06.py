#!/usr/bin/env python3
"""Exact, bounded and read-only checks for Monopoly, oligopoly and pricing.

Independent global candidate enumeration, active-set/deviation checks and
benefit-minus-cost welfare accounts supplement the written mathematical review.
Standard library only, no network or runtime inputs; quiet import and JSON CLI.
"""
from fractions import Fraction as F
from html.parser import HTMLParser
from itertools import product
import json
from pathlib import Path


BOOK = Path(__file__).resolve().parents[1]
CHAPTER = BOOK / "content/chapters/v05-c06.html"
SOURCES = BOOK / "content/reviews/v05-c06-sources.json"


def require(condition, label):
    if not condition:
        raise AssertionError(label)


def quad(coefficients, value):
    a, b, c = map(F, coefficients)
    value = F(value)
    return a * value * value + b * value + c


def quadratic_maxima(coefficients, lower, upper):
    """Exact global candidates on a closed interval, including convex cases."""
    a, b, _ = map(F, coefficients)
    lower, upper = F(lower), F(upper)
    require(lower <= upper, "ordered interval")
    candidates = {lower, upper}
    if a:
        stationary = -b / (2 * a)
        if lower <= stationary <= upper:
            candidates.add(stationary)
    scored = [(quad(coefficients, value), value) for value in candidates]
    maximum = max(value for value, _ in scored)
    return maximum, sorted(x for value, x in scored if value == maximum)


def benefit(a, b, quantity):
    # Integral of linear inverse demand, calculated as its trapezoid area.
    a, b, quantity = F(a), F(b), F(quantity)
    return (a + (a - b * quantity)) * quantity / 2


def welfare(a, b, quantities, costs):
    quantities, costs = tuple(map(F, quantities)), tuple(map(F, costs))
    q = sum(quantities)
    p = max(F(a) - F(b) * q, F(0))
    gross = benefit(a, b, q)
    production_cost = sum(c * x for c, x in zip(costs, quantities))
    profits = tuple((p - c) * x for c, x in zip(costs, quantities))
    cs = gross - p * q
    require(cs + sum(profits) == gross - production_cost, "welfare identity")
    return {"Q": q, "price": p, "profits": profits,
            "CS": cs, "total_surplus": gross - production_cost}


def uniform_segment_oracle(groups, cost):
    """Enumerate all choke-price intervals and their quadratic extrema.

    Each group is (intercept, inverse slope). Feasible price extends above the
    largest choke price with zero profit; that whole tail is represented by
    its boundary. The chapter's cases have strictly positive maximal profit.
    """
    groups = [(F(a), F(b)) for a, b in groups]
    cost = F(cost)
    boundaries = sorted({F(0), *(a for a, _ in groups)})
    candidates = set(boundaries)
    for lower, upper in zip(boundaries, boundaries[1:]):
        midpoint = (lower + upper) / 2
        active = [(a, b) for a, b in groups if midpoint < a]
        demand_intercept = sum(a / b for a, b in active)
        demand_slope = sum(1 / b for _, b in active)
        coefficients = (-demand_slope,
                        demand_intercept + cost * demand_slope,
                        -cost * demand_intercept)
        _, branch = quadratic_maxima(coefficients, lower, upper)
        candidates.update(branch)
    scored = []
    for price in candidates:
        quantities = tuple(max((a - price) / b, F(0)) for a, b in groups)
        profit = (price - cost) * sum(quantities)
        scored.append((profit, price, quantities))
    best = max(profit for profit, _, _ in scored)
    return sorted((price, quantities, profit) for profit, price, quantities in scored
                  if profit == best)


def segment_stats(groups, prices, quantities, cost):
    profits = tuple((F(p) - cost) * q for p, q in zip(prices, quantities))
    gross = tuple(benefit(a, b, q) for (a, b), q in zip(groups, quantities))
    cs = tuple(value - p * q for value, p, q in zip(gross, prices, quantities))
    total = sum(gross) - cost * sum(quantities)
    require(sum(cs) + sum(profits) == total, "segmented welfare reconciliation")
    return {"quantities": quantities, "prices": prices, "profit": sum(profits),
            "CS_by_group": cs, "CS": sum(cs), "total_surplus": total}


def cournot_profit(a, b, ci, own, rival):
    return (max(F(a) - F(b) * (own + rival), F(0)) - ci) * own


def cournot_response_oracle(a, b, ci, rival):
    """Global branch candidates; all positive output beyond choke loses at ci>0."""
    a, b, ci, rival = map(F, (a, b, ci, rival))
    require(b > 0 and ci > 0 and rival >= 0, "Cournot reference domain")
    boundary = max(a / b - rival, F(0))
    _, choices = quadratic_maxima((-b, a - ci - b * rival, 0), 0, boundary)
    profits = [(cournot_profit(a, b, ci, choice, rival), choice) for choice in choices]
    best = max(profit for profit, _ in profits)
    return tuple(choice for profit, choice in profits if profit == best)


def cournot_equilibria(a, b, c1, c2):
    """Enumerate all two-firm activity patterns; verify each by global responses."""
    a, b, c1, c2 = map(F, (a, b, c1, c2))
    # Solve the two active first-order equations by a determinant calculation.
    d = 4 * b * b - b * b
    both = ((2 * b * (a - c1) - b * (a - c2)) / d,
            (2 * b * (a - c2) - b * (a - c1)) / d)
    candidates = {(F(0), F(0)), both,
                  (max((a - c1) / (2 * b), F(0)), F(0)),
                  (F(0), max((a - c2) / (2 * b), F(0)))}
    valid = []
    for q1, q2 in candidates:
        if q1 < 0 or q2 < 0:
            continue
        if (q1 in cournot_response_oracle(a, b, c1, q2)
                and q2 in cournot_response_oracle(a, b, c2, q1)):
            valid.append((q1, q2))
    return sorted(valid)


def bertrand_profit(a, b, c, own, rival):
    own, rival = F(own), F(rival)
    demand = max((F(a) - own) / b, F(0))
    if own > rival:
        sales = F(0)
    elif own == rival:
        sales = demand / 2
    else:
        sales = demand
    return (own - c) * sales


def json_ready(value):
    if isinstance(value, F):
        return str(value)
    if isinstance(value, dict):
        return {key: json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(item) for item in value]
    return value


class Fragment(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.worked = self.h1 = self.exercises = self.solutions = 0
        self.depth = 0
        self.exercise_depth = self.solution_depth = None
        self.solution_details = False
        self.sources, self.ids, self.links, self.text = [], [], [], []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "h1":
            self.h1 += 1
        if "id" in attrs:
            self.ids.append(attrs["id"])
        if "data-source" in attrs:
            self.sources.extend(attrs["data-source"].split())
        if tag == "a":
            self.links.append(attrs.get("href", ""))
        if tag == "aside" and attrs.get("class") == "worked":
            self.worked += 1
        if tag == "details":
            self.solution_details = attrs.get("class") == "solutions"
        if tag == "ol":
            self.depth += 1
            if attrs.get("class") == "exercises":
                self.exercise_depth = self.depth
            elif self.solution_details:
                self.solution_depth = self.depth
        if tag == "li":
            if self.depth == self.exercise_depth:
                self.exercises += 1
            if self.depth == self.solution_depth:
                self.solutions += 1

    def handle_endtag(self, tag):
        if tag == "ol":
            if self.depth == self.exercise_depth:
                self.exercise_depth = None
            if self.depth == self.solution_depth:
                self.solution_depth = None
            self.depth -= 1
        if tag == "details":
            self.solution_details = False

    def handle_data(self, text):
        self.text.append(text)


def check():
    checks, outputs = [], {}
    # Worked 1: global square/candidate proof and separate integral accounting.
    value, choices = quadratic_maxima((-1, 72, 0), 0, 90)
    require((value, choices) == (1296, [36]), "worked 1 global monopoly")
    stats = welfare(90, 1, (F(36),), (F(18),))
    require(stats == {"Q": 36, "price": 54, "profits": (1296,),
                      "CS": 648, "total_surplus": 1944}, "worked 1 surplus")
    efficient = quadratic_maxima((F(-1, 2), 72, 0), 0, 90)
    require(efficient == (2592, [72]), "worked 1 global efficient choice")
    require(F(54 - 18, 54) == 1 / F(54, 36) == F(2, 3), "worked 1 Lerner")
    require(2592 - stats["total_surplus"] == 648, "worked 1 DWL")
    require(2592 - stats["CS"] == 1944 == 1296 + 648, "transfer versus loss")
    outputs["uniform_monopoly"] = stats
    checks.append("Worked 1: global quadratic candidates, Lerner, exact benefit/cost surplus and buyer-loss transfer reconciliation")

    # Exercise 1 changes marginal cost and imposes a binding capacity.
    require(quadratic_maxima((-3, 60, 0), 0, 35) == (300, [10]),
            "exercise 1 monopoly")
    require(quadratic_maxima((-2, 60, 0), 0, 35) == (450, [15]),
            "exercise 1 efficient choice")
    q, p = F(10), F(50)
    cs = benefit(70, 2, q) - p * q
    actual_cost = 10 * q + q * q
    require(cs == 100 and p * q - actual_cost == 300, "exercise 1 CS/profit")
    require(benefit(70, 2, q) - actual_cost == 400 and 450 - 400 == 50,
            "exercise 1 welfare loss")
    require(F(50 - 30, 50) == 1 / (F(1, 2) * 50 / 10) == F(2, 5),
            "exercise 1 unconstrained Lerner")
    require(quadratic_maxima((-3, 60, 0), 0, 8) == (288, [8]), "exercise 1 capacity monopoly")
    require(quadratic_maxima((-2, 60, 0), 0, 8) == (352, [8]), "exercise 1 feasible welfare")
    require(benefit(70, 2, 8) - 54 * 8 == 64, "exercise 1 capacity CS")
    require((70 - 4 * 8) - (10 + 2 * 8) == 12, "binding capacity derivative")
    require(F(54 - 26, 54) == F(14, 27) and 1 / (F(1, 2) * 54 / 8) == F(8, 27),
            "capacity violates unconstrained markup identity")
    require(450 - 352 == 98, "different feasible benchmarks")
    checks.append("Exercise 1: nonlinear cost global extrema, marginal/average distinctions, elasticity, capacity and like-for-like efficient benchmark")

    # Exercise 2: discontinuous activation cost at zero, not simply a derivative.
    activation = {}
    for fee in (F(1296), F(1300)):
        candidate_profits = {F(0): F(0), F(36): 1296 - fee}
        best = max(candidate_profits.values())
        active = sorted(q for q, profit in candidate_profits.items() if profit == best)
        activation[str(fee)] = active
    require(activation == {"1296": [0, 36], "1300": [0]}, "opening choices including tie")
    require(1296 - 1300 == -4 and -1300 < -4, "committed fee comparison")
    require(2592 - 1300 == 1292, "efficient surplus after avoidable setup")
    checks.append("Exercise 2: exact operating-versus-shutdown fee tie, sunk-cost alternatives and uncollectable gains under uniform pricing")

    # Worked 2 and exercise 4: independent branch partition for common prices.
    segment_cases = [
        {"groups": [(50, 1), (30, 1)], "uniform_price": F(25),
         "uniform_q": (F(25), F(5)), "uniform_profit": F(450),
         "uniform_cs": F(325), "uniform_w": F(775),
         "disc_q": (F(20), F(10)), "disc_prices": (F(30), F(20)),
         "disc_profit": F(500), "disc_cs": F(250), "disc_w": F(750)},
        {"groups": [(80, 1), (20, 1)], "uniform_price": F(45),
         "uniform_q": (F(35), F(0)), "uniform_profit": F(1225),
         "uniform_cs": F(1225, 2), "uniform_w": F(3675, 2),
         "disc_q": (F(35), F(5)), "disc_prices": (F(45), F(15)),
         "disc_profit": F(1250), "disc_cs": F(625), "disc_w": F(1875)},
    ]
    outputs["segmented_cases"] = []
    for case in segment_cases:
        groups = case["groups"]
        optimum = uniform_segment_oracle(groups, 10)
        require(optimum == [(case["uniform_price"], case["uniform_q"], case["uniform_profit"])],
                "global common-price branch optimum")
        uniform = segment_stats(groups, (case["uniform_price"],) * 2,
                                case["uniform_q"], 10)
        require(uniform["CS"] == case["uniform_cs"] and uniform["total_surplus"] == case["uniform_w"],
                "uniform benefit/cost accounting")
        discriminatory_q = []
        for a, b in groups:
            _, choices = quadratic_maxima((-b, a - 10, 0), 0, F(a, b))
            require(len(choices) == 1, "unique segment optimum")
            discriminatory_q.append(choices[0])
        require(tuple(discriminatory_q) == case["disc_q"], "separated global quantities")
        discriminatory = segment_stats(groups, case["disc_prices"], case["disc_q"], 10)
        require(discriminatory["profit"] == case["disc_profit"]
                and discriminatory["CS"] == case["disc_cs"]
                and discriminatory["total_surplus"] == case["disc_w"],
                "separate-price welfare accounting")
        outputs["segmented_cases"].append({"uniform": uniform, "discrimination": discriminatory})
    require(750 - 775 == -25 and F(1875) - F(3675, 2) == F(75, 2),
            "opposite welfare directions")
    require(F(625, 2) + F(25, 2) == 325, "worked 2 group triangles")
    require(benefit(50, 1, 40) == 1200 and benefit(30, 1, 20) == 400,
            "worked 2 first-degree payments")
    require(1200 + 400 - 10 * 60 == 1000 and 1000 - 775 == 225 and 1000 - 750 == 250,
            "worked 2 efficient extraction and two losses")
    checks.append("Worked 2 and exercise 4: every common-price branch, separated global quantities, independent welfare accounts and opposite discrimination effects")

    # Exercise 3: exhaustive consumer subsets for the efficient/perfect benchmark.
    values, cost = (52, 41, 29, 17), 20
    candidates = []
    for price in (0, *values, max(values) + 1):
        buyers = tuple(value for value in values if value >= price)
        candidates.append(((price - cost) * len(buyers), price, buyers))
    best_profit, price, buyers = max(candidates)
    require((best_profit, price, buyers) == (42, 41, (52, 41)), "finite uniform optimum")
    require(price * len(buyers) == 82 and sum(v - price for v in buyers) == 11,
            "finite uniform revenue and CS")
    subsets = [(sum((v - cost) * take for v, take in zip(values, mask)), mask)
               for mask in product((0, 1), repeat=4)]
    require(max(subsets) == (62, (1, 1, 1, 0)), "efficient consumer subset")
    require(sum(values[:3]) == 122 and 122 - 3 * cost == 62 and 62 - (42 + 11) == 9,
            "perfect extraction and finite DWL")
    checks.append("Exercise 3: all relevant uniform-price intervals and all 16 consumer subsets, with exact perfect-discrimination revenue and surplus")

    # Worked 3 and exercise 5: active sets plus whole-domain best-response certificates.
    for a, b, c in ((90, 1, 18), (84, 1, 12), (84, 1, 30), (84, 1, 54), (66, 1, 6)):
        for rival in (F(0), F(7, 3), F(12), F(18), F(24), F(30), F(36), F(54), F(72), F(100)):
            oracle = cournot_response_oracle(a, b, c, rival)
            formula = max(F(a - c) - b * rival, F(0)) / (2 * b)
            require(oracle == (formula,), "global BR versus derived formula")
            optimum_profit = cournot_profit(a, b, c, formula, rival)
            for own in (F(0), formula / 2, formula, formula + F(1, 3), F(a, b) + 1):
                require(cournot_profit(a, b, c, own, rival) <= optimum_profit,
                        "sampled BR deviation including zero-price tail")
    require(cournot_equilibria(90, 1, 18, 18) == [(24, 24)], "worked 3 active set")
    cournot = welfare(90, 1, (F(24), F(24)), (F(18), F(18)))
    require(cournot == {"Q": 48, "price": 42, "profits": (576, 576),
                         "CS": 1152, "total_surplus": 2304}, "worked 3 Cournot account")
    require(2592 - cournot["total_surplus"] == 288, "Cournot loss")
    outputs["cournot"] = cournot
    require(cournot_equilibria(84, 1, 12, 30) == [(30, 12)], "exercise 5 both active")
    asymmetric = welfare(84, 1, (F(30), F(12)), (F(12), F(30)))
    require(asymmetric == {"Q": 42, "price": 42, "profits": (900, 144),
                            "CS": 882, "total_surplus": 1926}, "asymmetric account")
    efficient_asym, efficient_q = quadratic_maxima((F(-1, 2), 72, 0), 0, 84)
    require((efficient_asym, efficient_q) == (2592, [72]), "low-cost allocation benchmark")
    same_q_lowcost = benefit(84, 1, 42) - 12 * 42
    require(same_q_lowcost == 2142 and 2592 - same_q_lowcost == 450,
            "asymmetric output-gap loss")
    require(same_q_lowcost - 1926 == (30 - 12) * 12 == 216,
            "asymmetric production-cost loss")
    require(2592 - 1926 == 666 == 450 + 216, "loss decomposition")
    require(F(84 - 2 * 54 + 12, 3) == -4, "invalid interior candidate")
    require(cournot_equilibria(84, 1, 12, 54) == [(36, 0)], "inactive high-cost firm")
    require(cournot_profit(84, 1, 12, 36, 0) == 1296 and 84 - 54 - 36 == -6,
            "corner equilibrium payoff/entry derivative")
    outputs["asymmetric_cournot"] = asymmetric
    checks.append("Worked 3 and exercise 5: 50 exact global response comparisons, 250 bounded deviations, active-set equilibria, productive versus output losses and rejected negative output")

    # Bertrand baseline: finite checks accompany the manuscript's continuum proof.
    for deviating_price in tuple(F(i, 2) for i in range(0, 201)):
        require(bertrand_profit(90, 1, 18, deviating_price, 18) <= 0,
                "baseline marginal-cost deviation")
    bertrand = welfare(90, 1, (F(36), F(36)), (F(18), F(18)))
    require(bertrand == {"Q": 72, "price": 18, "profits": (0, 0),
                          "CS": 2592, "total_surplus": 2592}, "worked 3 Bertrand account")
    outputs["bertrand"] = bertrand
    checks.append("Worked 3: exact Bertrand welfare and 201 price deviations checked; general uniqueness remains a written case proof")

    # Exercise 6: full best response against cartel action; concrete price/capacity deviations.
    require(cournot_profit(90, 1, 18, 18, 18) == 648, "cartel split payoff")
    require(cournot_response_oracle(90, 1, 18, 18) == (27,), "cartel deviation optimum")
    require(cournot_profit(90, 1, 18, 27, 18) == 729 and 729 - 648 == 81,
            "cartel incentive")
    require(bertrand_profit(90, 1, 18, 30, 30) == 360, "price tie payoff")
    require(bertrand_profit(90, 1, 18, 29, 30) == 671, "price undercut payoff")
    baseline_capacity_sales = min(F(30), F(90 - 18, 2))
    residual = max(F(90 - 19) - 30, F(0))
    deviation_sales = min(F(30), residual)
    require(baseline_capacity_sales == 30 and residual == 41 and deviation_sales == 30,
            "efficient capacity rationing")
    require((19 - 18) * deviation_sales == 30 > 0, "capacity price deviation")
    checks.append("Exercise 6: global cartel deviation, profitable price undercut and capacity/rationing deviation without claiming a new equilibrium")

    # Exercise 7: timing and different cost comparisons.
    require(576 - 700 == -124 and 576 - 500 == 76, "post-entry decisions")
    require(400 + 18 * 60 == 1480 and 800 + 18 * 60 == 1880,
            "plant duplication resource costs")
    require(18 * 60 == 1080 and 1480 - 1080 == 400, "marginal-cost revenue deficit")
    checks.append("Exercise 7: post-entry operating profit, irreversible one-period investment and fixed-cost duplication/financing distinction")

    # Exercise 8: exhaustive finite game, not just selected profitable deviations.
    grid = tuple(range(15))
    equilibria = []
    for p1, p2 in product(grid, repeat=2):
        first = bertrand_profit(14, 1, 2, p1, p2)
        second = bertrand_profit(14, 1, 2, p2, p1)
        first_deviations = [bertrand_profit(14, 1, 2, deviation, p2) for deviation in grid]
        second_deviations = [bertrand_profit(14, 1, 2, deviation, p1) for deviation in grid]
        if max(first_deviations) <= first and max(second_deviations) <= second:
            equilibria.append((p1, p2))
    require(equilibria == [(2, 2), (3, 3)], "complete integer-price game")
    require(bertrand_profit(14, 1, 2, 3, 3) == F(11, 2), "grid equilibrium profit")
    require(bertrand_profit(14, 1, 2, F(29, 10), 3) == F(999, 100),
            "continuous price deviation")
    outputs["integer_price_equilibria"] = equilibria
    checks.append("Exercise 8: all 225 price profiles and all unilateral integer deviations; exact 2.9-dollar deviation yields 9.99 instead of 5.5")

    # Retention uses a fresh intercept and cost, with independent extrema/responses.
    require(quadratic_maxima((-1, 60, 0), 0, 66) == (900, [30]), "delayed monopoly")
    require(quadratic_maxima((F(-1, 2), 60, 0), 0, 66) == (1800, [60]), "delayed efficient")
    require(cournot_equilibria(66, 1, 6, 6) == [(20, 20)], "delayed Cournot")
    delayed = [welfare(66, 1, (F(30),), (F(6),)),
               welfare(66, 1, (F(20), F(20)), (F(6), F(6))),
               welfare(66, 1, (F(30), F(30)), (F(6), F(6)))]
    require([(r["Q"], r["price"], r["CS"], 1800 - r["total_surplus"]) for r in delayed]
            == [(30, 36, 450, 450), (40, 26, 800, 200), (60, 6, 1800, 0)],
            "all delayed values")
    outputs["delayed_models"] = delayed
    checks.append("Delayed check: fresh monopoly/Cournot/Bertrand quantities, prices, profits, consumer surplus and deadweight losses")

    fragment = Fragment()
    html = CHAPTER.read_text(encoding="utf-8")
    fragment.feed(html)
    fragment.close()
    require(fragment.worked == 3 and fragment.exercises == fragment.solutions == 8,
            "complete worked/exercise/solution counts")
    require(fragment.h1 == 0 and fragment.depth == 0, "fragment/list structure")
    require(len(fragment.ids) == len(set(fragment.ids)), "unique IDs")
    text = " ".join(fragment.text)
    for phrase in ("Capability:", "Prerequisite:", "Teach-back:", "Delayed check:",
                   "best response", "Nash equilibrium", "marginal cost", "no discounting"):
        require(phrase in text, "instructional anchor: " + phrase)
    require("v05-c05.html" in fragment.links and "v05-c07.html" in fragment.links,
            "adjacent prerequisite and successor")
    sources = json.loads(SOURCES.read_text(encoding="utf-8"))
    require(isinstance(sources, list) and len(sources) == 4, "four scoped sources")
    source_ids = set()
    for source in sources:
        require(set(source) == {"id", "title", "url", "use", "checked", "verification"},
                "source schema")
        require(source["id"].startswith("v05-c06-") and source["id"] not in source_ids,
                "source prefix and uniqueness")
        require(source["url"].startswith("https://ocw.mit.edu/"), "official source domain")
        source_ids.add(source["id"])
    require(set(fragment.sources) == source_ids, "source/citation equality")
    checks.append("Static fragment: three worked examples, eight paired solutions, answered retention, strategic definitions, source schema and owned citation IDs")
    result = {"chapter": "v05-c06", "status": "passed", "checks": checks,
              "reference_values": json_ready(outputs),
              "limitations": [
                  "Exact case calculations and finite deviation checks supplement the written global, equilibrium and welfare proofs; they do not establish general theorems by enumeration.",
                  "The discrete-price game is exhaustively checked. The continuous-price Bertrand uniqueness result relies on the manuscript's full deviation-case argument and stated assumptions.",
                  "The capacity exercise only rejects a proposed equilibrium; it does not solve an unrestricted capacity-constrained pricing game.",
                  "All examples are synthetic. No empirical conduct, market definition, discrimination legality or current institutional observation is established.",
                  "Source inspection is scoped in the proposal file. No visual, mobile, print or independent-human QA is claimed; root owns shared integration and acceptance.",
              ]}
    json.dumps(result, allow_nan=False)  # Enforce the directly serializable contract.
    return result


if __name__ == "__main__":
    print(json.dumps(check(), indent=2, ensure_ascii=False, allow_nan=False))
