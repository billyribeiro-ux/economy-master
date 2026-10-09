"""Quiet independent arithmetic, contract and package checks for v09-c11."""
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
from fractions import Fraction as F
import hashlib
from html.parser import HTMLParser
import io
import json
from pathlib import Path
import re
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "content/projects"


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def load_lab():
    path = PROJECT / "v09-c11-analysis.py"
    module = ModuleType("v09_c11_lab")
    module.__file__ = str(path)
    captured = io.StringIO()
    with redirect_stdout(captured), redirect_stderr(captured):
        exec(compile(path.read_text(), str(path), "exec"), module.__dict__)
    require(not captured.getvalue(), "lab import must be quiet")
    return module


def run(lab, data):
    captured = io.StringIO()
    with redirect_stdout(captured), redirect_stderr(captured):
        result = lab.run(data)
    require(not captured.getvalue(), "run(data) must be quiet")
    json.dumps(result, allow_nan=False)
    return result


def exact(got, expected, label):
    require(F(got) == F(expected), label)


def book_check(lab, data, out):
    b = out["book"]
    require([x["filled"] for x in b["orders"]] == [300, 250, 0], "baseline order completion")
    require([x["cancelled"] for x in b["orders"]] == [0, 50, 300], "IOC/FOK cancellation")
    for order, answer in zip(data["book"]["orders"], b["orders"]):
        # Expand independently into individual available shares, then apply the limit.
        direction = 1 if order["side"] == "buy" else -1
        prices = [F(p) for p, n in data["book"]["asks" if direction == 1 else "bids"] for _ in range(n)]
        if order["limit"] is not None:
            prices = [p for p in prices if direction * (p - F(order["limit"])) <= 0]
        fill = prices[:order["quantity"]]
        if order["instruction"] == "FOK" and len(fill) < order["quantity"]:
            fill = []
        gross, fees = sum(fill, F(0)), len(fill) * F(".01")
        exact(answer["gross"], gross, "independent snapshot cash")
        exact(answer["cash_change"], -direction * gross - fees, "signed snapshot cash")
        if fill:
            mean, mid, future = gross / len(fill), F(100), F("100.15")
            exact(answer["average"], mean, "snapshot average")
            es, rs, mc = [F(answer["spreads"][x]) for x in ("effective", "realized", "midpoint_component")]
            require(es == rs + mc == 2 * direction * (mean - mid), "spread telescope")
            require(rs == 2 * direction * (mean - future), "future mark timing")
            exact(answer["spreads"]["effective_bps"], 10000 * es / mid, "spread bps denominator")
        else:
            require(answer["average"] is None and answer["spreads"] is None, "undefined unfilled average")
    exact(b["orders"][0]["cash_change"], -30063, "market cash anchor")
    exact(b["orders"][1]["cash_change"], -F(50085, 2), "partial limit cash anchor")
    exact(b["quoted_spread_bps"], 20, "quoted spread bps")
    changed = deepcopy(data)
    changed["book"]["orders"] = [
        {"id": "sellmarket", "side": "sell", "quantity": 450, "limit": None, "instruction": "IOC"},
        {"id": "selllimit", "side": "sell", "quantity": 450, "limit": "99.8", "instruction": "IOC"},
        {"id": "sellfok", "side": "sell", "quantity": 450, "limit": "99.8", "instruction": "FOK"}]
    sells = run(lab, changed)["book"]["orders"]
    require([x["filled"] for x in sells] == [450, 400, 0], "exercise2 sell fills")
    require([F(x["gross"]) for x in sells] == [44920, 39940, 0], "exercise2 sell gross")
    require([F(x["cash_change"]) for x in sells] == [F(89831, 2), 39936, 0], "exercise2 net cash")
    require([F(sells[i]["average"]) for i in (0, 1)] == [F(4492, 45), F(1997, 20)], "exercise2 averages")
    # A sell's proceeds can be smaller than its fee. Check the exact cash boundary
    # independently; fees above the execution price remain feasible if prefunded.
    changed = deepcopy(data)
    changed["book"].update(cash="0.1", fee_per_share=100,
                           orders=[{"id": "fee_boundary", "side": "sell", "quantity": 1,
                                    "limit": None, "instruction": "IOC"}])
    boundary = run(lab, changed)["book"]["orders"][0]
    expected_cash = F(1, 10) + F(999, 10) - 100
    require(expected_cash == 0 and boundary["filled"] == 1, "high-fee sell is funded exactly")
    exact(boundary["gross"], F(999, 10), "one-share sell proceeds at best bid")
    exact(boundary["fees"], 100, "high fee is charged once")
    exact(F(changed["book"]["cash"]) + F(boundary["cash_change"]), expected_cash,
          "final snapshot cash includes initial cash, sell proceeds and fees")
    changed["book"].update(cash=0, fee_per_share="99.9")
    covered = run(lab, changed)["book"]["orders"][0]
    exact(covered["cash_change"], 0, "sale proceeds exactly cover fee without initial cash")
    changed = deepcopy(data)
    changed["book"]["orders"][0]["quantity"] = 600
    large = run(lab, changed)["book"]["orders"][0]
    require((large["filled"], large["cancelled"]) == (500, 100), "finite market-order depth")
    exact(large["gross"], 50140, "all visible asks consumed")
    # Exercise1 is independent signed measurement, not the lab's spreads helper.
    es = 2 * (F(50) - F("49.95"))
    rs = 2 * (F("49.8") - F("49.95"))
    mc = 2 * (F(50) - F("49.8"))
    require([es, rs, mc] == [F(1, 10), -F(3, 10), F(2, 5)] and es == rs + mc, "exercise1 sell identity")
    require([10000 * x / 50 for x in (es, rs, mc)] == [20, -60, 80], "exercise1 bps")
    changed = deepcopy(data)
    changed["book"]["future_mid"] = "100.3"
    ret = run(lab, changed)["book"]["orders"][0]["spreads"]
    require([F(ret[x]) for x in ("effective", "realized", "midpoint_component")] == [F(2, 5), -F(1, 5), F(3, 5)], "retention mark change")
    return {"market_cash": 30063, "limit_cash": "50085/2", "sell_gross": [44920, 39940, 0],
            "sell_spreads_bps": [20, -60, 80], "high_fee_sell_boundary_final_cash": "0"}


def dealer_check(lab, data, out):
    results = []
    for theta, delta in [(F(2, 5), F(2)), (F(1, 4), F(4)), (F(0), F(2))]:
        changed = deepcopy(data)
        changed["dealer"]["informed_probability"] = str(theta)
        changed["dealer"]["value_half_range"] = str(delta)
        result = run(lab, changed)["dealer"]
        # Enumerate nature/type/direction paths rather than reuse posterior formulas.
        paths = []
        for value in (100 - delta, 100 + delta):
            informed_side = "buy" if value > 100 else "sell"
            paths.append((value, "informed", informed_side, theta / 2))
            paths.extend((value, "uninformed", s, (1 - theta) / 4) for s in ("buy", "sell"))
        quotes = {}
        for direction in ("buy", "sell"):
            subset = [x for x in paths if x[2] == direction]
            probability = sum(x[3] for x in subset)
            quotes[direction] = sum(x[0] * x[3] for x in subset) / probability
            posterior = sum(x[3] for x in subset if x[0] > 100) / probability
            exact(result["high_given_" + direction], posterior, "enumerated dealer posterior")
        exact(result["ask"], quotes["buy"], "dealer conditional ask")
        exact(result["bid"], quotes["sell"], "dealer conditional bid")
        profits = {"informed": F(0), "uninformed": F(0)}
        for value, kind, direction, probability in paths:
            gain = quotes["buy"] - value if direction == "buy" else value - quotes["sell"]
            profits[kind] += probability * gain
        require(sum(profits.values()) == 0, "zero expected dealer cash profit")
        exact(result["weighted_informed_loss"], profits["informed"], "type-weighted informed loss")
        exact(result["weighted_uninformed_gain"], profits["uninformed"], "type-weighted liquidity gain")
        results.append([str(quotes["sell"]), str(quotes["buy"])])
    require(results == [["496/5", "504/5"], ["99", "101"], ["100", "100"]], "dealer and exercise3 anchors")
    exact(out["dealer"]["spread"], F(8, 5), "baseline information spread")
    return {"bid_ask_cases": results, "exercise3_weighted_profits": ["-3/4", "3/4"]}


def queue_check(lab, data, out):
    results = []
    for ahead in (80, 100):
        changed = deepcopy(data)
        changed["queue"]["ahead"] = ahead
        result = run(lab, changed)["queue"]
        expected_cash = expected_is = expected_cancel = F(0)
        for state, answer in zip(changed["queue"]["states"], result["states"]):
            # Match named queue slots independently, retaining volume-price association.
            our_slots = range(ahead + 1, ahead + 101)
            filled = sum(position <= state["sell_volume"] for position in our_slots)
            remaining = 100 - filled
            passive_cash = filled * F("49.91")
            later_cash = remaining * (F(state["deadline_ask"]) + F(".01"))
            probability, mid = F(state["probability"]), F(state["deadline_mid"])
            paper = 1000 + 100 * mid
            actual = 6000 - passive_cash - later_cash + 100 * mid
            cancelled = 6000 - passive_cash + filled * mid
            require(answer["passive_fill"] == filled and answer["deadline_fill"] == remaining, "independent queue positions")
            exact(answer["complete_wealth"], actual, "completed queue wealth")
            exact(answer["cancel_wealth"], cancelled, "cancelled queue wealth")
            exact(answer["complete_shortfall"], paper - actual, "queue whole-target shortfall")
            expected_cash += probability * (passive_cash + later_cash)
            expected_is += probability * (paper - actual)
            expected_cancel += probability * (paper - cancelled)
        exact(result["expected_complete_cash"], expected_cash, "unconditional cash comparison")
        exact(result["expected_complete_shortfall"], expected_is, "unconditional target comparison")
        exact(result["expected_cancel_shortfall"], expected_cancel, "retained missed quantity")
        results.append(str(expected_is))
    require(results == ["33", "153/5"], "baseline and exercise4 queue shortfall")
    exact(out["queue"]["expected_cancel_shortfall"], F(132, 5), "cancel policy anchor")
    threshold = F(5061 - 5011, 5061 - 4991)
    require(threshold == F(5, 7), "exercise4 probability threshold")
    changed = deepcopy(data)
    changed["queue"]["states"][0]["probability"] = str(threshold)
    changed["queue"]["states"][1]["probability"] = str(1 - threshold)
    exact(run(lab, changed)["queue"]["expected_complete_cash"], 5011, "threshold policy indifference")
    return {"expected_shortfalls": results, "cancel_shortfall": "132/5", "fall_probability_threshold": "5/7"}


def shortfall_check(lab, data, out):
    def wealth(c, answer):
        d = 1 if c["side"] == "buy" else -1
        cash, shares = F(c["initial_cash"]), c["initial_shares"]
        paper_cash = cash - d * c["quantity"] * F(c["decision_price"])
        paper_shares = shares + d * c["quantity"]
        for fill in c["fills"]:
            cash -= d * fill["quantity"] * F(fill["price"]) + fill["quantity"] * F(c["fee_per_share"])
            shares += d * fill["quantity"]
            require(cash >= 0 and shares >= 0, "each dated fill funded")
        paper = paper_cash + paper_shares * F(c["terminal_price"])
        actual = cash + shares * F(c["terminal_price"])
        exact(answer["paper_wealth"], paper, "paper cash-stock ledger")
        exact(answer["actual_wealth"], actual, "actual cash-stock ledger")
        exact(answer["shortfall"], paper - actual, "independent terminal wealth difference")
        require(sum(F(answer[x]) for x in ("delay", "execution", "opportunity", "fees")) == paper - actual, "component telescope")
    wealth(data["shortfall"], out["shortfall"])
    require([F(out["shortfall"][x]) for x in ("delay", "execution", "opportunity", "fees")] == [100, F(65, 2), 45, 7], "baseline components")
    exact(out["shortfall"]["shortfall"], F(369, 2), "baseline full target IS")
    require(F(101500) / 5000 == F(out["shortfall"]["external_vwap"]) == F(203, 10), "exercise6 external sample VWAP")
    exact(out["shortfall"]["filled_vwap_cost"], -F(5, 2), "exercise6 gross VWAP cost")
    exact(out["shortfall"]["filled_vwap_cost_with_fees"], F(9, 2), "exercise6 net VWAP cost")
    changed = deepcopy(data)
    changed["shortfall"].update(side="sell", quantity=400, decision_price=30, arrival_price="29.9", terminal_price="29.7",
                                 initial_cash=0, initial_shares=400, terminal_time=3,
                                 fills=[{"time": 2, "quantity": 250, "price": "29.85"}])
    sell = run(lab, changed)["shortfall"]
    wealth(changed["shortfall"], sell)
    require([F(sell[x]) for x in ("delay", "execution", "opportunity", "fees")] == [40, F(25, 2), 30, 5], "exercise5 sell components")
    exact(sell["shortfall"], F(175, 2), "exercise5 sell shortfall")
    exact(sell["shortfall_bps"], F(875, 12), "exercise5 target basis points")
    changed = deepcopy(data)
    changed["shortfall"]["fills"] = []
    empty = run(lab, changed)["shortfall"]
    require(empty["average_fill_price"] is None and empty["filled"] == 0, "empty fill observation")
    exact(empty["shortfall"], 250, "empty fill preserves paper gain")
    changed = deepcopy(data)
    changed["shortfall"]["fills"].append({"time": 4, "quantity": 150, "price": "20.6"})
    changed["shortfall"]["initial_cash"] = "10202.5"
    complete = run(lab, changed)["shortfall"]
    wealth(changed["shortfall"], complete)
    exact(complete["cash_after_fills"], 0, "retention exact prefunding")
    exact(complete["shortfall"], F(405, 2), "retention full completion cost")
    exact(complete["opportunity"], 0, "completed target has no residual opportunity")
    return {"baseline": "369/2", "sell_exercise": "175/2", "sell_bps": "875/12", "funded_retention": "405/2", "retention_extra_cash": "405/2"}


def independent_schedules(c, quantity):
    """One-share price-path integration and explicit shock enumeration."""
    m, k, e1, e2, h, s, lam = [F(c[x]) for x in ("initial_mid", "persistent_k", "temporary_eta1", "temporary_eta2", "half_spread_and_fee", "shock_magnitude", "lambda")]
    rows = []
    for first in range(c["capacity1"] + 1):
        second = quantity - first
        if not 0 <= second <= c["capacity2"]:
            continue
        costs = []
        for shock in (-s, s):
            # Midpoint-rule integration is exact for the supplied linear persistent path.
            total = sum((m + k * (F(j) + F(1, 2)) + e1 * first + h for j in range(first)), F(0))
            total += sum((m + shock + k * (F(j) + F(1, 2)) + e2 * second + h for j in range(first, quantity)), F(0))
            costs.append(total - quantity * m)
        mean = sum(costs) / 2
        variance = sum((x - mean)**2 for x in costs) / 2
        rows.append({"q1": first, "q2": second, "mean": mean, "variance": variance,
                     "score": mean + lam * variance, "costs": costs})
    return sorted(rows, key=lambda x: (x["score"], x["q1"]))


def impact_check(lab, data, out):
    comparisons = 0
    c, answer = data["impact"], out["impact"]
    independent = independent_schedules(c, 12)
    require([(r["q1"], r["q2"]) for r in independent] == [(5, 7), (4, 8), (3, 9)], "schedule ranking from shock cash")
    for row in answer["candidates"]:
        separate = next(x for x in independent if x["q1"] == row["q1"])
        for output_key, own_key in (("expected_cost", "mean"), ("variance", "variance"), ("objective", "score")):
            exact(row[output_key], separate[own_key], "independent integrated cost and state moments")
            comparisons += 1
        require([F(x) for x in row["state_costs"]] == separate["costs"], "actual two-state ledger")
        require([F(x) - 600 for x in row["state_cash"]] == separate["costs"], "cost versus actual cash")
    selected = answer["selected"]
    require([F(selected[x]) for x in ("expected_cost", "variance", "objective")] == [F(147, 10), F(49, 4), F(98, 5)], "mean-variance convention anchor")
    exact(selected["block1_price"], F(2049, 40), "within-first-block average")
    require([F(x) for x in selected["state_cash"]] == [F(3056, 5), F(3091, 5)], "actual prefunded cash states")
    # Continuous derivative sign and integral terms, independent of returned optimum.
    derivative = lambda x: F(2, 5) * x - F(2, 5) * (12 - x)
    require(derivative(6) == 0 and derivative(5) < 0, "projection onto binding first cap")
    for lam, expected_first in [(F(0), 4), (F(2, 25), 4), (F(81, 1000), 5)]:
        changed = deepcopy(data)
        changed["impact"]["lambda"] = str(lam)
        result = run(lab, changed)["impact"]
        separate = independent_schedules(changed["impact"], 12)
        require(result["selected"]["q1"] == expected_first == separate[0]["q1"], "exercise7 integer risk switch")
    # Cost equality, dominance and continuous cap threshold are different statements.
    tie = F(3, 10) / (16 - F(49, 4))
    require(tie == F(2, 25) and F(3, 10) + F(17, 4) * tie > 0, "integer tie and dominated schedule")
    continuous_threshold = F(6, 35)
    qstar = 12 * (F(1, 10) + continuous_threshold / 4) / (F(3, 10) + continuous_threshold / 4)
    require(qstar == 5 and continuous_threshold > tie, "exercise7 continuous threshold")
    changed = deepcopy(data)
    changed["impact"]["capacity1"] = 6
    relaxed = run(lab, changed)["impact"]["selected"]
    require((relaxed["q1"], relaxed["q2"]) == (6, 6), "relaxed cap schedule")
    exact(relaxed["objective"], F(96, 5), "relaxed cap objective")
    changed = deepcopy(data)
    changed["impact"]["quantity"] = 15
    impossible = run(lab, changed)["impact"]
    require(not impossible["feasible"] and impossible["selected"] is None and impossible["candidates"] == [], "infeasible target preserved")
    changed = deepcopy(data)
    changed["impact"]["shock_magnitude"] = 0
    deterministic = run(lab, changed)["impact"]["selected"]
    require((deterministic["q1"], deterministic["q2"]) == (4, 8), "zero price risk transfer")
    exact(deterministic["variance"], 0, "zero shock variance")
    return {"mean": "147/10", "variance": "49/4", "objective": "98/5", "state_cash": ["3056/5", "3091/5"],
            "integer_lambda_switch": "2/25", "continuous_cap_threshold": "6/35", "moment_comparisons": comparisons}


def capacity_check(lab, data, out):
    anchors = []
    comparisons = 0
    for benefit in (F(3, 2), F(2)):
        changed = deepcopy(data)
        changed["impact"]["gross_benefit_per_share"] = str(benefit)
        result = run(lab, changed)["impact"]
        scores = []
        for row in result["capacity_grid"]:
            q = row["quantity"]
            independent = independent_schedules(changed["impact"], q)
            optimum = independent[0]
            score = benefit * q - optimum["score"]
            scores.append(score)
            exact(row["net_score"], score, "independent authorized-size score")
            require([row["q1"], row["q2"]] == [optimum["q1"], optimum["q2"]], "size-specific schedule")
            ties = [[r["q1"], r["q2"]] for r in independent if r["score"] == optimum["score"]]
            require(row["optimal_schedules"] == ties, "all integer ties reported")
            comparisons += 1
        optimum_q = max(range(15), key=lambda q: (scores[q], -q))
        largest_nonnegative = max(q for q in range(15) if scores[q] >= 0)
        require(result["optimal_quantity"] == optimum_q and result["largest_nonnegative_score_quantity"] == largest_nonnegative, "three different capacity questions")
        anchors.append([optimum_q, largest_nonnegative, result["physical_capacity"]])
    require(anchors == [[6, 11, 14], [8, 14, 14]], "baseline and exercise8 capacity anchors")
    require(out["impact"]["capacity_grid"][0]["optimal_schedules"] == [[0, 0]], "zero-size abstention")
    require([F(r["objective"]) for r in out["impact"]["capacity_grid"]] ==
            [F(x) for x in [0, "13/40", "7/10", "61/40", "12/5", "149/40", "51/10", "277/40", "44/5", "89/8", "27/2", "653/40", "98/5", "933/40", "55/2"]], "entire chapter cost table")
    return {"benefit_1_5": anchors[0], "benefit_2": anchors[1], "size_scenarios_independently_recomputed": comparisons}


def domain_check(lab, data):
    rejected = []
    def reject(label, mutate):
        value = deepcopy(data)
        mutate(value)
        captured = io.StringIO()
        try:
            with redirect_stdout(captured), redirect_stderr(captured):
                lab.run(value)
        except ValueError:
            require(not captured.getvalue(), "rejection must not print")
            rejected.append(label)
        else:
            raise AssertionError("invalid case accepted: " + label)
    reject("changed-priority-contract", lambda x: x["conventions"].update(queue="pro-rata"))
    reject("lambda-half-convention", lambda x: x["conventions"].update(objective="expected cost plus lambda/2 times variance"))
    reject("float-input", lambda x: x["impact"].update(**{"lambda": 0.4}))
    reject("boolean-quantity", lambda x: x["impact"].update(quantity=True))
    reject("nonfinite-price-string", lambda x: x["book"].update(future_mid="NaN"))
    reject("crossed-book", lambda x: x["book"]["bids"][0].__setitem__(0, "100.2"))
    reject("unordered-book", lambda x: x["book"]["asks"].reverse())
    reject("future-mark-before-fill", lambda x: x["book"].update(mark_time=0))
    reject("unsupported-order-type", lambda x: x["book"]["orders"][0].update(instruction="GTC"))
    reject("snapshot-unfunded", lambda x: x["book"].update(cash=30000))
    def snapshot_sell_fee(x):
        x["book"].update(cash=0, fee_per_share=100,
                         orders=[{"id": "unfunded_sell", "side": "sell", "quantity": 1,
                                  "limit": None, "instruction": "IOC"}])
    reject("snapshot-sell-fee-cash-deficit", snapshot_sell_fee)
    reject("dealer-no-participation-rule", lambda x: x["dealer"].update(informed_probability=1))
    reject("nonpositive-low-value", lambda x: x["dealer"].update(value_half_range=100))
    reject("probabilities-do-not-sum", lambda x: x["queue"]["states"][0].update(probability="1/2"))
    reject("deadline-ask-below-mid", lambda x: x["queue"]["states"][0].update(deadline_ask="49.4"))
    reject("deadline-unfunded", lambda x: x["queue"].update(cash=5060))
    reject("prearrival-fill", lambda x: x["shortfall"]["fills"][0].update(time=0))
    reject("postvaluation-fill", lambda x: x["shortfall"]["fills"][-1].update(time=5))
    reject("overfilled-original-target", lambda x: x["shortfall"]["fills"][0].update(quantity=400))
    reject("negative-fee", lambda x: x["shortfall"].update(fee_per_share="-0.01"))
    reject("unowned-sell-target", lambda x: x["shortfall"].update(side="sell", initial_shares=499))
    reject("retention-unfunded-completion", lambda x: x["shortfall"]["fills"].append({"time": 4, "quantity": 150, "price": "20.6"}))
    def intermediate(x):
        x["shortfall"].update(side="sell", quantity=2, initial_shares=2, initial_cash=0, fee_per_share=2,
                              fills=[{"time": 2, "quantity": 1, "price": 1}, {"time": 3, "quantity": 1, "price": 100}])
    reject("intermediate-cash-deficit", intermediate)
    reject("nonpositive-impacted-domain", lambda x: x["impact"].update(shock_magnitude=50))
    reject("nonconvex-temporary-input", lambda x: x["impact"].update(temporary_eta1=0))
    reject("negative-risk-penalty", lambda x: x["impact"].update(**{"lambda": "-1"}))
    reject("fractional-block-capacity", lambda x: x["impact"].update(capacity1="5/2"))
    reject("grid-not-prefunded", lambda x: x["impact"].update(cash=600))
    return rejected


class ChapterParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack = []
        self.ids = set()
        self.links = []
        self.text = []
        self.worked = 0
        self.exercises = 0
        self.solutions = 0
        self.sources = set()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            require(attrs["id"] not in self.ids, "unique chapter IDs")
            self.ids.add(attrs["id"])
        if "data-source" in attrs:
            self.sources.add(attrs["data-source"])
        if tag == "a":
            self.links.append(attrs.get("href", ""))
        if tag == "aside" and "worked" in attrs.get("class", "").split():
            self.worked += 1
        if tag == "li" and self.stack:
            parent = self.stack[-1]
            if parent[0] == "ol" and "exercises" in parent[1].get("class", "").split():
                self.exercises += 1
            if parent[0] == "ol" and any(t == "details" and "solutions" in a.get("class", "").split() for t, a in self.stack):
                self.solutions += 1
        require(tag != "h1", "chapter fragment has no duplicate h1")
        if tag not in ("br", "hr", "img", "meta", "link", "input"):
            self.stack.append((tag, attrs))

    def handle_endtag(self, tag):
        require(bool(self.stack) and self.stack[-1][0] == tag, "balanced HTML: " + tag)
        self.stack.pop()

    def handle_data(self, text):
        self.text.append(text)


def package_check(lab, data, out):
    reference = json.loads((PROJECT / "v09-c11-output.json").read_text())
    require(out == reference, "complete frozen output regression")
    manifest = json.loads((PROJECT / "v09-c11-manifest.json").read_text())
    expected_files = {"v09-c11-inputs.json", "v09-c11-analysis.py", "v09-c11-output.json", "v09-c11-README.txt"}
    require({x["file"] for x in manifest["files"]} == expected_files and len(manifest["files"]) == 4, "exact distributed asset set")
    for item in manifest["files"]:
        payload = (PROJECT / item["file"]).read_bytes()
        require(len(payload) == item["bytes"] and hashlib.sha256(payload).hexdigest() == item["sha256"], "distributed asset integrity")
    chapter = (ROOT / "content/chapters/v09-c11.html").read_text()
    parsed = ChapterParser()
    parsed.feed(chapter)
    parsed.close()
    require(not parsed.stack, "all chapter tags closed")
    require((parsed.worked, parsed.exercises, parsed.solutions) == (4, 8, 8), "complete worked/exercise/solution package")
    require({"objective", "orders", "spreads", "information", "queue", "shortfall", "impact", "evidence", "lab", "teach-back", "scope"} <= parsed.ids, "complete instructional route")
    expected_assets = expected_files | {"v09-c11-manifest.json"}
    require(expected_assets <= set(parsed.links), "all offline asset links")
    require({"curriculum.html#v09-c10", "curriculum.html#v09-c12"} <= set(parsed.links), "precise adjacent specification routes")
    proposals = json.loads((ROOT / "content/reviews/v09-c11-sources.json").read_text())
    ids = {x["id"] for x in proposals}
    require(ids == {"v09-c11-sec-orders", "v09-c11-hasbrouck", "v09-c11-almgren-chriss"} == parsed.sources, "scoped source mapping")
    require({"sources.html#" + x for x in ids} <= set(parsed.links), "source catalogue routes")
    require(all(x["checked"] == "2026-10-09" and x["verification"] and x["use"] for x in proposals), "source inspection scope present")
    for href in parsed.links:
        if href.startswith("#"):
            require(href[1:] in parsed.ids, "local fragment route")
    words = len(re.findall(r"\S+", " ".join(parsed.text)))
    return {"worked": parsed.worked, "exercises": parsed.exercises, "solutions": parsed.solutions,
            "chapter_words": words, "manifest_files": 4, "scoped_sources": len(ids)}


def check():
    """No stdout/stderr or mutations; return strict JSON or raise a concrete failure."""
    lab = load_lab()
    data = lab.load_json(PROJECT / "v09-c11-inputs.json")
    out = run(lab, data)
    anchors = {
        "book": book_check(lab, data, out),
        "dealer": dealer_check(lab, data, out),
        "queue": queue_check(lab, data, out),
        "shortfall": shortfall_check(lab, data, out),
        "impact": impact_check(lab, data, out),
        "capacity": capacity_check(lab, data, out),
    }
    rejected = domain_check(lab, data)
    package = package_check(lab, data, out)
    result = {"chapter": "v09-c11", "status": "passed", "groups": 8,
              "checks": ["Snapshot depth, signed spreads and sell transfers", "Enumerated informed/uninformed conditional cash",
                         "Queue selection and dated deadline cash", "Independent paper/actual wealth and original target",
                         "Per-share impact integration and shock-state objective", "Complete authorized-size grid and integer ties",
                         "Meaningful timing, funding and contract-domain rejection", "Complete frozen output, HTML, sources and four-file hashes"],
              "anchors": anchors, "rejected_inputs": rejected, "package": package}
    json.dumps(result, allow_nan=False)
    return result


if __name__ == "__main__":
    print(json.dumps(check(), indent=2, allow_nan=False))
