#!/usr/bin/env python3
"""Independent exact checks for Volume 5 assessment Form B.

Quiet check() returns directly JSON-serializable data. Standard library only;
reads its own HTML fragment relative to this script, with no runtime writes or
network access. Global candidates, finite allocations, LP vertices, matching
enumeration and all permitted lottery assignments check the supplied cases.
"""
from fractions import Fraction as F
from html.parser import HTMLParser
from itertools import combinations, permutations, product
import json
from pathlib import Path
import re

BOOK = Path(__file__).resolve().parents[1]
FRAGMENT = BOOK / "content/assessment-parts/v05-form-b.html"


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def quadratic(coefficients, x):
    a, b, c = map(F, coefficients)
    x = F(x)
    return a*x*x+b*x+c


def global_quadratic(coefficients, lower, upper):
    a, b, _ = map(F, coefficients)
    lower, upper = F(lower), F(upper)
    points = {lower, upper}
    if a:
        stationary = -b/(2*a)
        if lower <= stationary <= upper:
            points.add(stationary)
    values = [(quadratic(coefficients, x), x) for x in points]
    best = max(v for v, _ in values)
    return best, sorted(x for v, x in values if v == best)


def benefit(intercept, slope, quantity):
    intercept, slope, quantity = map(F, (intercept, slope, quantity))
    return quantity*(intercept+intercept-slope*quantity)/2


class ExamParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack = []
        self.ids = []
        self.h1_count = 0
        self.headings = []
        self.links = []
        self.tables = {}
        self.table = None
        self.row = None
        self.cell = None
        self.parts = []
        self.question_count = 0
        self.solution_count = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = set(attrs.get("class", "").split())
        if tag == "h1":
            self.h1_count += 1
        if tag in {"h1", "h2", "h3"}:
            self.headings.append((tag, attrs.get("id")))
        if "id" in attrs:
            self.ids.append(attrs["id"])
        if tag == "a":
            self.links.append(attrs.get("href", ""))
        if tag == "table":
            self.table = attrs.get("id")
            self.tables[self.table] = []
        if tag == "tr" and self.table:
            self.row = []
        if tag == "td" and self.table:
            self.cell = []
        if tag == "ol" and "exam-parts" in classes:
            self.parts.append(0)
        if tag == "li":
            parent = self.stack[-1] if self.stack else (None, set())
            if parent[0] == "ol":
                if "exam-questions" in parent[1]:
                    self.question_count += 1
                if "exam-parts" in parent[1]:
                    self.parts[-1] += 1
                if "exam-solutions" in parent[1]:
                    self.solution_count += 1
        if tag not in {"br", "hr", "img", "input", "meta", "link", "wbr", "col"}:
            self.stack.append((tag, classes))

    def handle_endtag(self, tag):
        if tag == "td" and self.cell is not None:
            self.row.append("".join(self.cell).strip())
            self.cell = None
        if tag == "tr" and self.table and self.row:
            self.tables[self.table].append(self.row)
            self.row = None
        if tag == "table":
            self.table = None
        require(self.stack and self.stack[-1][0] == tag, "balanced fragment: "+tag)
        self.stack.pop()

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)


def common_price(groups, marginal_cost):
    """Enumerate active-demand price intervals and all quadratic extrema."""
    groups = [(F(a), F(b)) for a, b in groups]
    marginal_cost = F(marginal_cost)
    knots = sorted({F(0), *(a for a, _ in groups)})
    candidates = set(knots)
    for lower, upper in zip(knots, knots[1:]):
        midpoint = (lower+upper)/2
        active = [(a, b) for a, b in groups if midpoint < a]
        demand_intercept = sum(a/b for a, b in active)
        demand_slope = sum(1/b for _, b in active)
        if demand_slope:
            stationary = (demand_intercept+marginal_cost*demand_slope)/(2*demand_slope)
            if lower <= stationary <= upper:
                candidates.add(stationary)
    records = []
    for price in sorted(candidates):
        quantities = [max(F(0), (a-price)/b) for a, b in groups]
        profit = (price-marginal_cost)*sum(quantities)
        records.append((profit, price, quantities))
    optimum = max(row[0] for row in records)
    best = [row for row in records if row[0] == optimum]
    return best, records


def lp_vertices(constraints):
    """Vertices of a 2D polyhedron a*x+b*y >= c using exact intersections."""
    constraints = [tuple(map(F, row)) for row in constraints]
    candidates = set()
    for first, second in combinations(constraints, 2):
        a, b, c = first
        d, e, f = second
        determinant = a*e-b*d
        if not determinant:
            continue
        x, y = (c*e-b*f)/determinant, (a*f-c*d)/determinant
        if all(r*x+s*y >= t for r, s, t in constraints):
            candidates.add((x, y))
    return sorted(candidates)


def wage_minimum(p_high, p_low, high_cost, reservation, target):
    p_high, p_low, high_cost, reservation = map(F, (p_high, p_low, high_cost, reservation))
    constraints = [(1, 0, 0), (0, 1, 0)]
    if target == "H":
        probability, cost = p_high, high_cost
        constraints.append((p_low-p_high, p_high-p_low, high_cost))
    else:
        probability, cost = p_low, F(0)
        constraints.append((p_high-p_low, p_low-p_high, -high_cost))
    constraints.append((1-probability, probability, reservation+cost))
    vertices = lp_vertices(constraints)
    require(vertices, "wage feasible vertices exist")
    expected = lambda wages: (1-probability)*wages[0]+probability*wages[1]
    best = min(expected(wages) for wages in vertices)
    return {"expected_wage": best, "minimizing_vertices": [w for w in vertices if expected(w) == best],
            "vertices_checked": len(vertices), "constraints": constraints}


def feasible(wages, constraints):
    return all(F(a)*wages[0]+F(b)*wages[1] >= F(c) for a, b, c in constraints)


def deferred_acceptance(applicant_preferences, institution_preferences):
    next_choice = {a: 0 for a in applicant_preferences}
    free = list(applicant_preferences)
    held = {}
    rejected = []
    while free:
        applicant = free.pop(0)
        require(next_choice[applicant] < len(applicant_preferences[applicant]), "acceptable place remains")
        institution = applicant_preferences[applicant][next_choice[applicant]]
        next_choice[applicant] += 1
        if institution not in held:
            held[institution] = applicant
            continue
        previous = held[institution]
        rankings = institution_preferences[institution]
        if rankings.index(applicant) < rankings.index(previous):
            held[institution] = applicant
            free.append(previous)
            rejected.append((institution, previous))
        else:
            free.append(applicant)
            rejected.append((institution, applicant))
    return {a: institution for institution, a in held.items()}, rejected


def blocking_pairs(matching, applicants, institutions):
    inverse = {institution: applicant for applicant, institution in matching.items()}
    return [(a, i) for a in applicants for i in institutions
            if applicants[a].index(i) < applicants[a].index(matching[a])
            and institutions[i].index(a) < institutions[i].index(inverse[i])]


def ready(value):
    if isinstance(value, F):
        return value.numerator if value.denominator == 1 else str(value)
    if isinstance(value, dict):
        return {str(k): ready(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [ready(v) for v in value]
    return value


def check():
    manuscript = FRAGMENT.read_text(encoding="utf-8")
    parser = ExamParser()
    parser.feed(manuscript)
    require(not parser.stack, "closed fragment")
    checks, reference = [], {}

    # D1(a): the linear objective is globally maximized at a budget-simplex vertex.
    consumer = []
    for px, py in [(2, 1), (4, 1)]:
        vertices = [(F(0), F(0)), (F(12, px), F(0)), (F(0), F(12, py))]
        values = [3*x+y for x, y in vertices]
        optimum = max(values)
        chosen = [bundle for bundle, value in zip(vertices, values) if value == optimum]
        consumer.append({"bundle": chosen[0], "utility": optimum})
    require(consumer == [{"bundle": (6, 0), "utility": 18}, {"bundle": (0, 12), "utility": 12}], "D1a corners")
    require(4*consumer[0]["bundle"][0] == 24 > 12, "D1a changed budget")
    reference["D1a"] = consumer
    checks.append("D1(a): all budget-simplex vertices, utility targets and old-bundle infeasibility")

    expenditure = lambda px, py, u: min(F(px, 3)*u, F(py)*u)
    cv, ev = expenditure(4, 1, 18)-12, 12-expenditure(2, 1, 12)
    require((cv, ev) == (6, 4), "D1b variations")
    for x in [F(0), F(1), F(2), F(4)]:
        y = 12-3*x
        require(y >= 0 and 3*x+y == expenditure(3, 1, 12), "D1b tie budget identity")
    require(4*0+18 == expenditure(4, 1, 18) and 2*4 == expenditure(2, 1, 12), "D1b Hicksian targets")
    reference["D1b"] = {"CV": cv, "EV": ev, "target_bundles": [(0, 18), (4, 0)]}
    checks.append("D1(b): dual target expenditures, corner Hicksian bundles and tie-line identity")

    initial, tie = [], []
    for labor in [F(i, 2) for i in range(11)]:
        capital = 10-2*labor
        initial.append((6*labor+4*capital, labor, capital))
        tie.append(8*labor+4*capital)
    require(min(initial) == (30, 5, 0) and set(tie) == {F(40)}, "D1c factor cases")
    # Linear coefficients certify the complete interval, not just listed points.
    require(4-6/F(2) == 1 and 4-8/F(2) == 0, "D1c nonnegative slack coefficients")
    reference["D1c"] = {"initial_pair": [5, 0], "initial_cost": 30, "tie_cost": 40}
    checks.append("D1(c): input requirement boundary, global cost inequality and whole minimizing tie segment")

    operating = {}
    for price in [F(4), F(5), F(21, 5)]:
        candidates = [(F(-7), F(0)), ((price-3)*10-19, F(10))]
        best = max(profit for profit, _ in candidates)
        outputs = sorted(q for profit, q in candidates if profit == best)
        require(price > 3, "D1d positive operating profit slope")
        operating[str(price)] = {"outputs": outputs, "profit": best}
    require(operating == {"4": {"outputs": [0], "profit": -7}, "5": {"outputs": [10], "profit": 1},
                          "21/5": {"outputs": [0, 10], "profit": -7}}, "D1d global shutdown choices")
    reference["D1d"] = operating
    checks.append("D1(d): capacity endpoint versus shutdown and exact disconnected supply tie")

    rows = parser.tables["v05-b-unit-market"]
    values = [F(row[1]) for row in rows]
    costs = [F(row[3]) for row in rows]
    require(values == [18, 14, 10, 6] and costs == [2, 5, 9, 13], "D2 table input contract")
    price = F(19, 2)
    buyers = [i for i, value in enumerate(values) if value > price]
    sellers = [i for i, cost in enumerate(costs) if cost < price]
    cs = sum(values[i]-price for i in buyers)
    ps = sum(price-costs[i] for i in sellers)
    # Exhaust every chosen buyer/seller subset at every possible volume.
    allocation_best = {}
    for volume in range(5):
        alternatives = [sum(values[i] for i in bs)-sum(costs[i] for i in ss)
                        for bs in combinations(range(4), volume) for ss in combinations(range(4), volume)]
        allocation_best[volume] = max(alternatives)
    require(buyers == sellers == [0, 1, 2] and (cs, ps) == (F(27, 2), F(25, 2)), "D2a market ledger")
    require(allocation_best == {0: 0, 1: 16, 2: 25, 3: 26, 4: 19}, "D2a global allocation enumeration")
    reference["D2a"] = {"Q": 3, "CS": cs, "PS": ps, "surplus": cs+ps, "best_surplus_by_Q": allocation_best}
    checks.append("D2(a): parsed market inputs, participation/clearing and all 70 buyer/seller subset allocations")

    ceiling = F(7)
    supplied = [i for i, cost in enumerate(costs) if cost < ceiling]
    served = [1, 2]
    cs2 = sum(values[i]-ceiling for i in served)
    ps2 = sum(ceiling-costs[i] for i in supplied)
    require(len(supplied) == len(served) == 2 and (cs2, ps2) == (10, 7), "D2b rationing ledger")
    best_given_supply = max(sum(values[i] for i in bs)-sum(costs[i] for i in supplied)
                            for bs in combinations([0, 1, 2], 2))
    require(best_given_supply == 25 and (26-25, 25-cs2-ps2) == (1, 8), "D2b loss decomposition")
    reference["D2b"] = {"CS": cs2, "PS": ps2, "surplus": cs2+ps2,
                        "best_same_supply": best_given_supply, "restricted_trade_loss": 1, "misallocation_loss": 8}
    checks.append("D2(b): actual rationing, every eligible two-buyer allocation and trade versus misallocation loss")

    # Exact market polynomial p²+p−12 = (p−3)(p+4) plus strict concavity.
    p = F(3)
    output = p
    profit = p*output-output*output/2
    income = 20+profit
    z = income-p*output
    require((output, profit, income, z) == (3, F(9, 2), F(49, 2), F(31, 2)), "D2c values")
    require(12/(1+output) == p and z > 0 and z+output*output/2 == 20, "D2c optimality and markets")
    require(global_quadratic((F(-1, 2), p, 0), 0, 20) == (profit, [output]), "D2c independent firm global choice")
    reference["D2c"] = {"price": p, "output": output, "profit": profit, "income": income, "z": z}
    checks.append("D2(c): firm global candidates, exact market polynomial, household first-order condition and both resource ledgers")

    omitted_z = 20-p*output
    missing = 20-omitted_z-output*output/2
    require((omitted_z, missing) == (11, F(9, 2)), "D2d missing ownership")
    require(output*output < 40 and -output+12/(1+output) == 0, "D2d feasible stationary point")
    # Derivative sign numerator 12−q−q² = (3−q)(q+4) changes only at q=3 for q>=0.
    require((F(-1), F(-1), F(12)) == (F(-1), F(3-4), F(3*4)), "D2d global derivative factorization")
    reference["D2d"] = {"incorrect_z": omitted_z, "missing_numeraire": missing, "efficient_output": output}
    checks.append("D2(d): missing profit closure and global utility derivative sign on the resource-feasible interval")

    groups = [(64, 2), (28, 1)]
    best, candidates = common_price(groups, 4)
    require(best == [(F(486), F(22), [F(21), F(6)])], "D3a common optimum")
    require((F(450), F(34), [F(15), F(0)]) in candidates, "D3a excluded-group alternative")
    reference["D3a"] = {"price": 22, "quantities": [21, 6], "profit": 486,
                        "branch_candidates": candidates}
    checks.append("D3(a): all common-price choke intervals, stationary prices, boundaries and no-sales branch")

    separate = [global_quadratic((-b, a-4, 0), 0, F(a, b)) for a, b in groups]
    quantities = [case[1][0] for case in separate]
    gross_profit = sum(case[0] for case in separate)
    prices = [F(a)-F(b)*q for (a, b), q in zip(groups, quantities)]
    gross_benefit = sum(benefit(a, b, q) for (a, b), q in zip(groups, quantities))
    total_sep = gross_benefit-4*sum(quantities)-80
    common_q = best[0][2]
    total_common = sum(benefit(a, b, q) for (a, b), q in zip(groups, common_q))-4*sum(common_q)
    require((quantities, prices, gross_profit-80, total_common, total_sep) == ([15, 12], [34, 16], 514, 945, 811),
            "D3b private and real-resource comparison")
    require(sum(quantities) == sum(common_q) == 27 and total_common-total_sep == 134, "D3b allocation/resource loss")
    reference["D3b"] = {"quantities": quantities, "prices": prices, "net_profit": gross_profit-80,
                        "common_surplus": total_common, "separate_surplus": total_sep, "loss": total_common-total_sep}
    checks.append("D3(b): separate global group choices and independently integrated welfare including real verification")

    parsed_game = [[tuple(F(x) for x in re.findall(r"-?\d+", cell)) for cell in row[1:]]
                   for row in parser.tables["v05-b-game"]]
    require(parsed_game == [[(4, 1), (0, 3)], [(0, 3), (2, 0)], [(1, 2), (1, 2)]], "D3 game input contract")
    row_mix, col_mix = [F(3, 5), F(2, 5), F(0)], [F(1, 3), F(2, 3)]
    row_payoffs = [sum(col_mix[j]*parsed_game[i][j][0] for j in range(2)) for i in range(3)]
    col_payoffs = [sum(row_mix[i]*parsed_game[i][j][1] for i in range(3)) for j in range(2)]
    require(row_payoffs == [F(4, 3), F(4, 3), F(1)] and col_payoffs == [F(9, 5), F(9, 5)], "D3c every pure deviation")
    reference["D3c"] = {"row_mix": row_mix, "column_mix": col_mix, "row_action_payoffs": row_payoffs, "column_action_payoffs": col_payoffs}
    checks.append("D3(c): parsed game, both indifference equations and every supported/off-support pure deviation")

    threshold = row_payoffs[0]
    require(threshold == F(4, 3) and F(2)-threshold == F(2, 3), "D3d threshold and deviation gain")
    for k in [F(-5), F(1), F(4, 3), F(2)]:
        actual_best = max(row_payoffs[:2]+[k])
        require((actual_best == threshold) == (k <= threshold), "D3d support condition including tie")
    reference["D3d"] = {"valid_k_upper_bound": threshold, "deviation_gain_at_2": F(2, 3)}
    checks.append("D3(d): off-support parameter inequality, equality without mandatory support and explicit profitable deviation")

    costs_signal = {"H": F(2), "L": F(7)}
    sep_payoffs = {kind: [F(4), F(10)-cost] for kind, cost in costs_signal.items()}
    require(sep_payoffs == {"H": [4, 8], "L": [4, 3]}, "D4a complete finite deviations")
    require(sep_payoffs["H"][1] > 0 and sep_payoffs["L"][0] > 0, "D4a participation")
    reference["D4a"] = {"beliefs_at_0_1": [0, 1], "wages_at_0_1": [4, 10], "type_signal_payoffs": sep_payoffs}
    checks.append("D4(a): both on-path posteriors, both finite signal choices and positive participation")

    pooling_wage = F(10+4, 2)
    high_bound = (pooling_wage+costs_signal["H"]-4)/6
    low_bound = (pooling_wage+costs_signal["L"]-4)/6
    require((high_bound, low_bound) == (F(5, 6), F(5, 3)), "D4b both belief constraints")
    total_sep_signal = pooling_wage-costs_signal["H"]/2
    require(total_sep_signal == 6 and pooling_wage == 7, "D4b real credential cost")
    reference["D4b"] = {"pooling_wage": pooling_wage, "belief_interval": [0, high_bound],
                        "pooling_joint_value": pooling_wage, "separating_joint_value": total_sep_signal}
    checks.append("D4(b): intersected high/low signal IC and probability bounds; pooling versus separating resource value")

    unaudited_high = wage_minimum(F(3, 4), F(1, 4), 8, 2, "H")
    unaudited_low = wage_minimum(F(3, 4), F(1, 4), 8, 2, "L")
    require(unaudited_high["expected_wage"] == 12 and unaudited_low["expected_wage"] == 2, "D4c global wage LP values")
    require(feasible((F(0), F(16)), unaudited_high["constraints"]) and feasible((F(2), F(2)), unaudited_low["constraints"]), "D4c stated schedules")
    require((48-12, 16-2) == (36, 14), "D4c principal alternatives")
    reference["D4c"] = {"high_wages": [0, 16], "high_expected_wage": 12, "high_profit": 36,
                        "low_profit": 14, "worker_H_utility": 4,
                        "H_vertices_checked": unaudited_high["vertices_checked"], "L_vertices_checked": unaudited_low["vertices_checked"]}
    checks.append("D4(c): every feasible wage-polyhedron vertex, IC/IR/limited liability and both efforts versus no hiring")

    audited_high = wage_minimum(1, F(1, 4), 8, 2, "H")
    audited_low = wage_minimum(1, F(1, 4), 8, 2, "L")
    wage = audited_high["expected_wage"]
    require(wage == F(32, 3) and audited_low["expected_wage"] == 2, "D4d audited LP values")
    require(feasible((F(0), F(32, 3)), audited_high["constraints"]), "D4d actual audited schedule")
    profit_audit, worker_audit = 48-wage-1, wage-8
    require((profit_audit, worker_audit, profit_audit+worker_audit) == (F(109, 3), F(8, 3), 39), "D4d real-cost ledger")
    require(profit_audit > 36 and 16-audited_low["expected_wage"]-1 == 13, "D4d private adoption comparison")
    require(profit_audit+worker_audit < 36+4, "D4d private/joint reversal")
    reference["D4d"] = {"wages": [0, wage], "profit": profit_audit, "worker_utility": worker_audit,
                        "joint_surplus": profit_audit+worker_audit, "audited_low_profit": 13,
                        "H_vertices_checked": audited_high["vertices_checked"], "L_vertices_checked": audited_low["vertices_checked"]}
    checks.append("D4(d): audited global wage LP, weak IC, all private alternatives and rent reduction versus real audit cost")

    efficient, quantities = global_quadratic((-1, 8, 0), 0, 5)
    require(efficient == 16 and quantities == [4], "D5a public-good global optimum")
    gross_public = [benefit(a, 1, 4) for a in [9, 5]]
    fees = [F(16), F(8)]
    nets = [value-fee for value, fee in zip(gross_public, fees)]
    require(gross_public == [28, 12] and sum(fees) == 24 and nets == [12, 4], "D5a financing and strict participation")
    require((9-4)+(5-4) == 6, "D5a Samuelson sum")
    reference["D5a"] = {"G": 4, "surplus": efficient, "fees": fees, "net_benefits": nets,
                        "strict_fee_1_interval": "(12,24]"}
    checks.append("D5(a): global public provision, endpoint comparison, summed margins and budget-balanced strict participation")

    preferences = parser.tables["v05-b-matching"]
    applicants = {row[0]: [x.strip() for x in row[1].split(",")] for row in preferences}
    institutions = {row[2]: [x.strip() for x in row[3].split(",")] for row in preferences}
    matching, rejections = deferred_acceptance(applicants, institutions)
    require(matching == {"M": "T", "N": "S", "O": "R"}, "D5b DA allocation")
    require(rejections == [("R", "N"), ("S", "O"), ("R", "M"), ("S", "M")], "D5b rejection chain")
    require(not blocking_pairs(matching, applicants, institutions), "D5b all blocking-pair checks")
    stable = []
    for allocation in permutations(institutions):
        candidate = dict(zip(applicants, allocation))
        if not blocking_pairs(candidate, applicants, institutions):
            stable.append(candidate)
    require(stable == [matching], "D5b all six complete matchings checked")
    reference["D5b"] = {"matching": matching, "rejections": rejections, "stable_matchings": stable}
    checks.append("D5(b): parsed preferences, executed rejection chain, all pairs and all six complete matchings")

    pilot = parser.tables["v05-b-pilot"]
    assignment = [int(row[1]) for row in pilot]
    outcomes = [int(row[2]) for row in pilot]
    require(assignment == outcomes == [1, 1, 1, 0, 0, 0, 0], "D5c supplied realization")
    observed = sum(F(y) for y, z in zip(outcomes, assignment) if z)/3-sum(F(y) for y, z in zip(outcomes, assignment) if not z)/4
    counts = {k: 0 for k in range(4)}
    statistics = []
    for treated in combinations(range(7), 3):
        k = sum(outcomes[i] for i in treated)
        counts[k] += 1
        statistic = F(k, 3)-F(sum(outcomes)-k, 4)
        statistics.append(statistic)
    require(list(counts.values()) == [4, 18, 12, 1], "D5c independent combinatorial counts")
    require(parser.tables["v05-b-randomization"] == [["Assignments", "4", "18", "12", "1"]], "D5c table matches enumeration")
    tail = sum(abs(t) >= abs(observed) for t in statistics)
    p_value = F(tail, len(statistics))
    require(observed == 1 and p_value == F(1, 35) < F(1, 20), "D5c exact inclusive test")
    require(sorted(set(statistics)) == [F(-3, 4), F(-1, 6), F(5, 12), F(1)] and sum(statistics) == 0,
            "D5c asymmetric support and exact null expectation")
    require(2*p_value > F(1, 20), "D5c doubling would change the decision")
    reference["D5c"] = {"observed_contrast": observed, "counts": counts,
                        "null_statistics": sorted(set(statistics)), "p_value": p_value, "assignments": len(statistics)}
    checks.append("D5(c): all 35 permitted assignments, asymmetric null distribution, inclusive exact tail and 5% decision")

    plug_in = (F(7)-9)*observed-F(1, 2)
    require(plug_in == F(-5, 2), "D5d conditional welfare calculation")
    # Compatible missing potential outcomes demonstrate that the one observed
    # contrast need not equal its finite-population effect, even with a valid lottery.
    compatible_effects = []
    for missing in product([0, 1], repeat=7):
        y0 = [missing[i] if assignment[i] else outcomes[i] for i in range(7)]
        y1 = [outcomes[i] if assignment[i] else missing[i] for i in range(7)]
        compatible_effects.append(sum(F(a-b) for a, b in zip(y1, y0))/7)
    require(min(compatible_effects) == 0 and max(compatible_effects) == 1, "D5d compatible zero and positive effects")
    reference["D5d"] = {"plug_in_welfare_USD_per_person": plug_in,
                        "compatible_sample_effect_extrema": [min(compatible_effects), max(compatible_effects)]}
    checks.append("D5(d): conditional resource criterion and all 128 missing-binary-outcome schedules illustrating effect uncertainty")

    require(parser.h1_count == 0 and parser.headings == [("h2", "form-b")], "required fragment heading")
    require(parser.question_count == parser.solution_count == 5 and parser.parts == [4]*5, "five complete four-part domains")
    require(manuscript.count("<strong>(5)</strong>") == 20 and manuscript.count("Scoring:") == 20, "twenty five-point parts and rubrics")
    require(len(set(parser.ids)) == len(parser.ids), "unique IDs")
    require(all(identifier == "form-b" or identifier.startswith("v05-b-") for identifier in parser.ids), "owned ID prefix")
    require(set(parser.links) == {f"v05-c{i:02d}.html" for i in range(1, 13)}, "all twelve taught-method routes")
    for phrase in ["180 minutes", "closed notes", "basic nonprogrammable calculator", "critical conceptual error", "finite set {0,1}", "report-only"]:
        require(phrase in manuscript, "administration/assumption contract: "+phrase)
    checks.append("Structure: five domains, twenty scored parts and rubrics, exact owned IDs, administration and all twelve prerequisite routes")

    result = ready({"status": "passed", "checks": checks, "reference_values": reference,
                    "limitations": [
                        "Checks audit the supplied synthetic exam, not arbitrary economies or the actual knowledge of a learner.",
                        "Exact numeric candidates and finite enumeration supplement the written global arguments, assumptions, mechanism critiques and scoring review.",
                        "The contract LP audit covers the expressly permitted output-only and report-only classes; it makes no claim about richer joint-signal contracts.",
                        "The behavioral sharp-null test and welfare plug-in calculation have different premises and targets; neither identifies a unique psychological mechanism or universal population effect.",
                        "No new external empirical or legal claims require retrieval; stable methods route through the twelve chapter manuscripts and their inspected primary sources.",
                        "No visual, mobile or print UI QA performed. Root alone integrates, accepts and publishes the complete volume package."]})
    json.dumps(result, allow_nan=False)
    return result


if __name__ == "__main__":
    print(json.dumps(check(), ensure_ascii=False, indent=2, allow_nan=False))
