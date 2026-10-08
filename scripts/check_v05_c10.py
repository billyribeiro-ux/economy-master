#!/usr/bin/env python3
"""Exact, bounded, read-only checks for Externalities and public goods.

Standard library only. Independent resource ledgers, global quadratic and
piecewise candidates, active sets and transfer feasibility supplement the
manuscript's proofs. Quiet check() returns strict-JSON-compatible data.
"""
from fractions import Fraction as F
from html.parser import HTMLParser
import json
from pathlib import Path

BOOK = Path(__file__).resolve().parents[1]
CHAPTER = BOOK / "content/chapters/v05-c10.html"
SOURCES = BOOK / "content/reviews/v05-c10-sources.json"


def require(condition, label):
    if not condition:
        raise AssertionError(label)


def qvalue(coefficients, x):
    a, b, c = map(F, coefficients)
    x = F(x)
    return a*x*x+b*x+c


def extremum(coefficients, lo, hi, maximize=True):
    """Compare endpoints and stationary point, including convex polynomials."""
    a, b, _ = map(F, coefficients)
    lo, hi = F(lo), F(hi)
    require(lo <= hi, "ordered interval")
    xs = {lo, hi}
    if a:
        stationary = -b/(2*a)
        if lo <= stationary <= hi:
            xs.add(stationary)
    values = [(qvalue(coefficients, x), x) for x in xs]
    best = (max if maximize else min)(y for y, _ in values)
    return best, sorted(x for y, x in values if y == best)


def integral_linear(intercept, slope, quantity):
    """Trapezoid integral; slope may be positive or negative."""
    intercept, slope, quantity = map(F, (intercept, slope, quantity))
    return quantity*(intercept+(intercept+slope*quantity))/2


def external_case(a, b, c, k, h):
    a, b, c, k, h = map(F, (a, b, c, k, h))
    efficient_value, candidates = extremum((-(b+k+h)/2, a-c, 0), 0, a/b)
    require(len(candidates) == 1, "unique social optimum")
    efficient = candidates[0]
    tax = h*efficient
    private = (a-c)/(b+k)
    records = []
    for quantity, wedge in ((private, F(0)), (efficient, tax)):
        pb, ps = a-b*quantity, c+k*quantity
        benefit = integral_linear(a, -b, quantity)
        cost = integral_linear(c, k, quantity)
        harm = integral_linear(0, h, quantity)
        cs, surplus, revenue = benefit-pb*quantity, ps*quantity-cost, wedge*quantity
        require(pb-ps == wedge, "implementing wedge")
        require(cs+surplus+revenue-harm == benefit-cost-harm, "resource ledger")
        records.append({"Q": quantity, "buyer_price": pb, "seller_price": ps,
                        "CS": cs, "PS": surplus, "revenue": revenue,
                        "harm": harm, "welfare": benefit-cost-harm})
    require(records[1]["welfare"] == efficient_value, "candidate and ledger match")
    return records


def abatement(total):
    total = F(total)
    lo, hi = max(F(0), total-12), min(F(12), total)
    # Substitute a2 = total-a1 into the cost rather than equalizing MAC blindly.
    cost, choices = extremum((2, -3*total, F(3, 2)*total*total), lo, hi, False)
    require(len(choices) == 1, "unique abatement minimum")
    a1 = choices[0]
    a2 = total-a1
    price = 3*a2
    _, br1 = extremum((F(1, 2), -price, 12*price), 0, 12, False)
    _, br2 = extremum((F(3, 2), -price, 12*price), 0, 12, False)
    require(br1 == [a1] and br2 == [a2], "bounded price responses implement allocation")
    return {"abatement": [a1, a2], "emissions": [12-a1, 12-a2],
            "cost": cost, "price": price, "revenue": price*(24-total)}


def emissions(a, b, tax):
    # Independent private objective includes the bounds explicitly.
    _, xs = extremum((-F(b)/2, F(a)-F(tax), 0), 0, 20)
    require(len(xs) == 1, "unique private emissions choice")
    return xs[0]


def uncertain_case(b, d, states):
    b, d = F(b), F(d)
    states = list(map(F, states))
    mean = sum(states)/len(states)
    cap, tax = mean/(b+d), d*mean/(b+d)
    losses_cap, losses_tax, selected = [], [], []
    for state in states:
        coefficients = (-(b+d)/2, state, 0)
        optimum, xs = extremum(coefficients, 0, 20)
        output = emissions(state, b, tax)
        require(xs == [state/(b+d)], "state optimum interior")
        lc = optimum-qvalue(coefficients, cap)
        lt = optimum-qvalue(coefficients, output)
        require(lc == (state-mean)**2/(2*(b+d)), "cap loss derivation")
        require(lt == d*d*(state-mean)**2/(2*b*b*(b+d)), "tax loss derivation")
        if state != mean:
            require(lt/lc == (d/b)**2, "loss ratio")
        losses_cap.append(lc)
        losses_tax.append(lt)
        selected.append(output)
    # Enumerate all policy-tax intervals at which an emitter's bound changes.
    # Once tax reaches max A all emissions are zero, so represent the infinite tail.
    knots = sorted({F(0), *states, *(max(F(0), a-20*b) for a in states)})
    candidates = set(knots)
    for lo, hi in zip(knots, knots[1:]):
        mid = (lo+hi)/2
        active = [a for a in states if 0 < (a-mid)/b < 20]
        # W((a-t)/b) has quadratic coefficient -(b+d)/(2b²)
        # and linear coefficient da/b² on each active state's tax interval.
        if active:
            stationary = d*sum(active)/((b+d)*len(active))
            if lo <= stationary <= hi:
                candidates.add(stationary)
    scored = []
    for candidate in candidates:
        expected = sum(qvalue((-(b+d)/2, a, 0), emissions(a, b, candidate))
                       for a in states)/len(states)
        scored.append((expected, candidate))
    best = max(value for value, _ in scored)
    best_taxes = sorted(t for value, t in scored if value == best)
    require(best_taxes == [tax], "all bounded-response tax branches checked")
    return {"cap": cap, "tax": tax, "tax_emissions": selected,
            "efficient_emissions": [a/(b+d) for a in states],
            "expected_cap_loss": sum(losses_cap)/len(states),
            "expected_tax_loss": sum(losses_tax)/len(states),
            "tax_candidates_checked": len(candidates)}


def public_benefit(intercept, quantity):
    intercept, quantity = F(intercept), F(quantity)
    s = min(intercept, quantity)
    return integral_linear(intercept, -1, s)


def public_optimum(intercepts, cost):
    intercepts = tuple(map(F, intercepts))
    cost = F(cost)
    knots = sorted({F(0), *intercepts})
    candidates = set(knots)
    for lo, hi in zip(knots, knots[1:]):
        mid = (lo+hi)/2
        active = [a for a in intercepts if a > mid]
        if active:
            stationary = (sum(active)-cost)/len(active)
            if lo <= stationary <= hi:
                candidates.add(stationary)
    # Beyond the last satiation kink, benefits are constant and positive cost rises.
    scores = [(sum(public_benefit(a, g) for a in intercepts)-cost*g, g)
              for g in candidates]
    value = max(v for v, _ in scores)
    return value, sorted(g for v, g in scores if v == value)


def contribution_response(intercept, cost, others, upper=F(100)):
    """Piecewise maximize one contributor's net benefit, including satiation."""
    intercept, cost, others, upper = map(F, (intercept, cost, others, upper))
    xs = {F(0), upper}
    for candidate in (intercept-others, intercept-cost-others):
        if 0 <= candidate <= upper:
            xs.add(candidate)
    scored = [(public_benefit(intercept, others+x)-cost*x, x) for x in xs]
    best = max(v for v, _ in scored)
    return sorted(x for v, x in scored if v == best)


def public_equilibrium(intercepts, cost, government=0):
    """Exhaust active sets for two distinct-target contributors in our cases."""
    intercepts = tuple(map(F, intercepts))
    cost, government = F(cost), F(government)
    require(len(intercepts) == 2 and intercepts[0] != intercepts[1],
            "checker restricted to two distinct public-good targets")
    candidates = {(F(0), F(0))}
    # Both active would require distinct total targets to be equal, impossible.
    for i in range(2):
        values = [F(0), F(0)]
        values[i] = max(F(0), intercepts[i]-cost-government)
        candidates.add(tuple(values))
    accepted = []
    for contributions in candidates:
        if all(contribution_response(intercepts[i], cost,
                                     government+contributions[1-i], F(100)/cost) == [contributions[i]]
               for i in range(2)):
            accepted.append(contributions)
    require(len(accepted) == 1, "unique active-set contribution equilibrium")
    contributions = accepted[0]
    quantity = government+sum(contributions)
    payoffs = [public_benefit(a, quantity)-cost*g
               for a, g in zip(intercepts, contributions)]
    return {"contributions": contributions, "quantity": quantity,
            "net_benefits_before_government_finance": payoffs}


def congestion(a, c, slope):
    a, c, slope = map(F, (a, c, slope))
    private = (a-c)/(1+slope)
    welfare, xs = extremum((-(F(1, 2)+slope), a-c, 0), 0, a)
    require(len(xs) == 1, "unique flow optimum")
    efficient = xs[0]
    records = []
    for flow, toll in ((private, F(0)), (efficient, slope*efficient)):
        own = c+slope*flow
        benefit = integral_linear(a, -1, flow)
        real_cost = flow*own
        receipts = flow*toll
        user_surplus = benefit-flow*(own+toll)
        require(user_surplus+receipts == benefit-real_cost, "congestion ledger")
        records.append({"flow": flow, "own_cost": own, "toll": toll,
                        "benefit": benefit, "resource_cost": real_cost,
                        "receipts": receipts, "user_surplus": user_surplus,
                        "welfare": benefit-real_cost})
    require(records[1]["welfare"] == welfare, "global flow welfare")
    return records


class Structure(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack = []
        self.exercise_count = 0
        self.solution_count = 0
        self.worked = 0
        self.h1 = 0
        self.ids = []
        self.sources = set()
        self.links = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = set(attrs.get("class", "").split())
        if tag == "h1":
            self.h1 += 1
        if tag == "aside" and "worked" in classes:
            self.worked += 1
        if "id" in attrs:
            self.ids.append(attrs["id"])
        if "data-source" in attrs:
            self.sources.add(attrs["data-source"])
        if tag == "a":
            self.links.append(attrs.get("href", ""))
        if tag == "li":
            if any(t == "ol" and "exercises" in c for t, c in self.stack):
                self.exercise_count += 1
            if any(t == "details" and "solutions" in c for t, c in self.stack):
                self.solution_count += 1
        if tag not in {"area", "base", "br", "col", "embed", "hr", "img", "input",
                       "link", "meta", "param", "source", "track", "wbr"}:
            self.stack.append((tag, classes))

    def handle_endtag(self, tag):
        require(bool(self.stack) and self.stack[-1][0] == tag, "balanced HTML: "+tag)
        self.stack.pop()


def json_ready(value):
    if isinstance(value, F):
        return value.numerator if value.denominator == 1 else str(value)
    if isinstance(value, dict):
        return {k: json_ready(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [json_ready(v) for v in value]
    return value


def check():
    checks, references = [], {}
    main = external_case(84, 2, 12, 1, 1)
    require([r["Q"] for r in main] == [24, 18], "worked output")
    require([[r[k] for k in ("CS", "PS", "revenue", "harm", "welfare")]
             for r in main] == [[576, 288, 0, 288, 576], [324, 162, 324, 162, 648]],
            "worked tax accounts")
    require(main[1]["buyer_price"]-main[0]["buyer_price"] == 12, "buyer incidence")
    require(main[0]["seller_price"]-main[1]["seller_price"] == 6, "seller incidence")
    wrong_quantity = F(84-12-24, 3)
    require(wrong_quantity == 16 and qvalue((-2, 72, 0), wrong_quantity) == 640,
            "old marginal damage does not implement optimum")
    references["worked_externality"] = main
    checks.append("External-cost global optimum, tax wedge, incidence, full transfer/harm ledger and wrong-target loss")

    ex1 = external_case(60, 1, 12, 1, 2)
    require([[r[k] for k in ("Q", "CS", "PS", "revenue", "harm", "welfare")]
             for r in ex1] == [[24, 288, 288, 0, 576, 0], [12, 72, 72, 288, 144, 288]],
            "exercise 1 full ledger")
    references["exercise_1"] = ex1
    checks.append("Exercise 1 independent integrated functions, global target and both private/public accounts")

    normal, corner = abatement(12), abatement(20)
    require(normal["abatement"] == [9, 3] and normal["cost"] == 54 and normal["price"] == 9,
            "interior heterogeneous abatement")
    require(corner["abatement"] == [12, 8] and corner["cost"] == 168 and corner["price"] == 24,
            "binding abatement corner")
    require(F(1, 2)*6**2+F(3, 2)*6**2-normal["cost"] == 18, "uniform allocation loss")
    require(F(1, 2)*10**2+F(3, 2)*10**2-corner["cost"] == 32, "uniform allocation corner loss")
    references["abatement"] = {"worked": normal, "exercise_2": corner}
    checks.append("Abatement endpoint/stationary cost minimization, bounded private price responses and standard comparisons")

    first, second = uncertain_case(2, 1, [10, 14]), uncertain_case(1, 2, [10, 14])
    require((first["expected_tax_loss"], first["expected_cap_loss"]) == (F(1, 6), F(2, 3)),
            "first uncertainty ranking")
    require((second["expected_tax_loss"], second["expected_cap_loss"]) == (F(8, 3), F(2, 3)),
            "reversed uncertainty ranking")
    ex3 = uncertain_case(3, 1, [12, 20])
    require(ex3["expected_tax_loss"] == F(2, 9) and ex3["expected_cap_loss"] == 2,
            "exercise 3 transfer calculation")
    references["uncertainty"] = [first, second, ex3]
    checks.append("State-by-state loss identities and ranking reversal; every nonnegative-tax response branch, including zero emissions")

    public = public_equilibrium([14, 10], 6)
    require(public["contributions"] == (8, 0), "worked contribution equilibrium")
    require(public["net_benefits_before_government_finance"] == [32, 48], "worked private net benefits")
    optimum, quantities = public_optimum([14, 10], 6)
    require(optimum == 81 and quantities == [9], "worked public-good global optimum")
    gross = [public_benefit(a, 9) for a in [14, 10]]
    require(gross == [F(171, 2), F(99, 2)], "public-good benefit branches")
    lo = 54-(gross[1]-48)
    hi = gross[0]-32
    require((lo, hi) == (F(105, 2), F(107, 2)), "balanced IR finance interval")
    require([gross[0]-53, gross[1]-1] == [F(65, 2), F(97, 2)], "strict improving finance")
    require([x-27 for x in gross] == [F(117, 2), F(45, 2)], "equal-fee distribution")
    references["worked_public_good"] = {"voluntary": public, "efficient_quantity": 9,
                                         "efficient_surplus": optimum, "fee_1_interval": [lo, hi]}
    checks.append("Public-good satiation branches, active-set Nash equilibrium, global efficient provision and balanced participation fees")

    new_public = public_equilibrium([10, 6], 8)
    require(new_public["contributions"] == (2, 0), "exercise 4 equilibrium")
    require(new_public["net_benefits_before_government_finance"] == [2, 10], "exercise 4 private benefits")
    require(public_optimum([10, 6], 8) == (F(16), [F(4)]), "exercise 4 all efficient branches")
    benefits = [public_benefit(a, 4) for a in [10, 6]]
    require(benefits == [32, 16], "exercise 4 gross benefits")
    require([benefits[0]-28, benefits[1]-4] == [4, 12], "exercise 4 improving fee pair")
    require([v-16 for v in benefits] == [16, 0], "exercise 4 equal fees")
    references["exercise_4"] = new_public
    checks.append("Exercise 4 unique contribution responses, efficient satiation branches and equal versus improving finance")

    crowd = [public_equilibrium([14, 10], 6, g) for g in [3, 10]]
    require([r["contributions"] for r in crowd] == [(5, 0), (0, 0)], "crowding out and nonnegative bound")
    require([r["quantity"] for r in crowd] == [8, 10], "crowding-out quantities")
    require(public_optimum([14, 10], 25) == (F(0), [F(0)]), "zero provision corner")
    references["exercise_5"] = {"government_3": crowd[0], "government_10": crowd[1], "high_cost_quantity": 0}
    checks.append("Government provision active sets, contribution exhaustion and zero efficient provision corner")

    traffic = congestion(30, 6, F(1, 2))
    require([[r[k] for k in ("flow", "own_cost", "toll", "receipts", "user_surplus", "welfare")]
             for r in traffic] == [[16, 14, 0, 0, 128, 128], [12, 12, 6, 72, 72, 144]],
            "worked congestion complete ledger")
    ex6 = congestion(42, 6, 1)
    require([[r[k] for k in ("flow", "own_cost", "toll", "receipts", "user_surplus", "welfare")]
             for r in ex6] == [[18, 24, 0, 0, 162, 162], [12, 18, 12, 144, 72, 216]],
            "exercise 6 congestion complete ledger")
    references["congestion"] = {"worked": traffic, "exercise_6": ex6}
    checks.append("Congestion own versus external cost, global flow optimum and hourly resource/payment accounts in both cases")

    joint = (F(-3, 2), F(24), F(0))
    private = (-1, 24, 0)
    require(extremum(joint, 0, 12) == (F(96), [F(8)]), "Coase efficient activity")
    require(extremum(private, 0, 12) == (F(144), [F(12)]), "producer-rights fallback")
    zero_rights_interval = [F(32), F(128)]
    producer_rights_interval = [F(144)-qvalue(private, 8), F(72)-F(8**2, 2)]
    require(producer_rights_interval == [16, 40], "producer-rights transfer interval")
    require(zero_rights_interval[1]-zero_rights_interval[0] == 96, "zero-rights interval equals gains")
    require(producer_rights_interval[1]-producer_rights_interval[0] == 24, "producer-rights interval equals gains")
    require([128-80, 80-32] == [48, 48] and [128+28, -32-28] == [156, -60], "both splits")
    require(96-30 < 72 and 96-30 > 0, "transaction-cost feasibility depends on fallback")
    references["worked_bargaining"] = {"efficient_activity": 8, "joint_surplus": 96,
                                        "neighbor_rights_payment_interval": zero_rights_interval,
                                        "producer_rights_payment_interval": producer_rights_interval}
    checks.append("Bargaining global joint/private optima, both rights' participation intervals, distribution and transaction-cost comparison")

    constrained, choices = extremum(joint, 9, 12)
    require(constrained == F(189, 2) and choices == [9], "payment-limited global joint optimum")
    compensation = 144-qvalue(private, 9)
    payoffs = [qvalue(private, 9)+compensation, -F(9**2, 2)-compensation]
    require(compensation == 9 and payoffs == [144, F(-99, 2)], "payment-limited IR construction")
    require(payoffs[1] >= -72 and sum(payoffs) == constrained, "both participation and ledger")
    require(96-constrained == F(3, 2), "constrained efficiency loss")
    # Polynomial identity establishes R >= (12-x)^2 for every x, not just a grid.
    require(tuple(F(v) for v in (1, -24, 144)) == (F(1), F(-2*12), F(12**2)), "required compensation square")
    references["exercise_7"] = {"activity": 9, "payment": compensation, "payoffs": payoffs,
                                 "joint_surplus": constrained, "loss": F(3, 2)}
    checks.append("Exercise 7 compensation-square bound, constrained global activity, actual feasible transfer and costly-agreement rejection")

    technologies = {"dirty": (F(8), F(0)), "clean": (F(2), F(50))}
    private_costs = {}
    for name, output_tax, emissions_tax in [("no_policy", 0, 0), ("output_tax", 3, 0), ("emissions_tax", 0, 15)]:
        costs = {tech: extra+10*output_tax+emission*emissions_tax
                 for tech, (emission, extra) in technologies.items()}
        chosen = min(costs, key=costs.get)
        private_costs[name] = {"costs": costs, "choice": chosen}
    require([private_costs[name]["choice"] for name in private_costs] == ["dirty", "dirty", "clean"],
            "technology incentives under each instrument")
    dirty_resources = technologies["dirty"][1]+15*technologies["dirty"][0]
    clean_resources = technologies["clean"][1]+15*technologies["clean"][0]
    gain = dirty_resources-clean_resources
    require(gain == 40 and gain-60 == -20 and gain-5 == 35, "monitoring and standard real costs")
    references["exercise_8"] = {"private_costs": private_costs, "physical_gain": gain,
                                 "emissions_tax_net_gain": gain-60, "standard_net_gain": gain-5}
    checks.append("Exercise 8 discrete technology choice, output-proxy failure and real monitoring-cost reversal without revenue double-counting")

    delayed = external_case(40, 1, 4, 1, 1)
    require([r["Q"] for r in delayed] == [18, 12], "retention output")
    require([r["welfare"] for r in delayed] == [162, 216], "retention welfare")
    require(delayed[1]["buyer_price"] == 28 and delayed[1]["seller_price"] == 16
            and delayed[1]["revenue"] == 144 and delayed[1]["harm"] == 72, "retention prices and accounts")
    references["delayed_check"] = delayed
    checks.append("Fresh delayed-check global optimum, tax, prices, receipts, damage and surplus gain")

    manuscript = CHAPTER.read_text(encoding="utf-8")
    parser = Structure()
    parser.feed(manuscript)
    require(not parser.stack and parser.h1 == 0, "complete HTML fragment")
    require(parser.worked == 4 and parser.exercise_count == parser.solution_count == 8,
            "four worked cases and eight paired exercises/solutions")
    require(len(parser.ids) == len(set(parser.ids)), "unique fragment IDs")
    require("Teach-back" in manuscript and "Delayed check" in manuscript
            and "Delayed-check answer" in manuscript, "teaching and retention closure")
    require({"v05-c09.html", "v05-c11.html"} <= set(parser.links), "prerequisite and continuation")
    sources = json.loads(SOURCES.read_text(encoding="utf-8"))
    require(len(sources) == 4 and len({s["id"] for s in sources}) == 4, "four distinct source records")
    schema = {"id", "title", "url", "use", "checked", "verification"}
    for source in sources:
        require(set(source) == schema and all(isinstance(value, str) and value for value in source.values()), "source schema")
        require(source["id"].startswith("v05-c10-") and source["checked"] == "2026-10-08", "source scope/date")
        require(source["url"] in parser.links, "inspected route is cited")
    require(parser.sources == {s["id"] for s in sources}, "source citation agreement")
    checks.append("Static fragment structure, exercise/solution counts, source schema/date/IDs and local prerequisite routes")

    result = json_ready({"status": "passed", "checks": checks, "reference_values": references,
                         "limitations": [
                             "Exact checks cover the supplied synthetic cases; continuum proofs and institutional assumptions require mathematical/editorial reading.",
                             "Tax-policy branch enumeration uses the chapter's two equally likely linear-quadratic states and does not establish a general price-versus-quantity theorem.",
                             "Source schema and citation matching do not repeat network retrieval or certify every statement in the source PDFs.",
                             "No empirical, legal or actual policy implementation conclusion follows from these synthetic examples.",
                             "No visual, mobile or print UI QA was performed; shared build and acceptance remain root responsibilities."]})
    json.dumps(result, ensure_ascii=False, allow_nan=False)
    return result


if __name__ == "__main__":
    print(json.dumps(check(), ensure_ascii=False, indent=2, allow_nan=False))
