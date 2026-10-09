"""Independent c06 audit with enumerated stopping rules and funded path ledgers.

The author model is the system under test. Neither its saved output nor its
author checker supplies any pricing or hedge oracle in this file.
"""
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
from fractions import Fraction as F
from functools import lru_cache
from hashlib import sha256
from html.parser import HTMLParser
from io import StringIO
from itertools import product
from math import comb
from pathlib import Path
import json
import runpy
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "content/projects"
AUTHOR_PATHS = (
    "content/chapters/v10-c06.html", "content/projects/v10-c06-inputs.json",
    "content/projects/v10-c06-analysis.py", "content/projects/v10-c06-output.json",
    "content/projects/v10-c06-manifest.json", "content/projects/v10-c06-README.txt",
    "scripts/check_v10_c06.py", "content/reviews/v10-c06-sources.json",
    "content/reviews/v10-c06-author.json",
)


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def cash(spot, strike, kind):
    difference = spot-strike if kind == "call" else strike-spot
    return difference if difference > 0 else F(0)


def european(s, k, u, d, r, remaining, kind):
    """Direct terminal binomial sum, independent of the author's induction."""
    q = (r-d)/(u-d)
    return sum((F(comb(remaining, ups))*q**ups*(1-q)**(remaining-ups)
                *cash(s*u**ups*d**(remaining-ups), k, kind)
                for ups in range(remaining+1)), F(0))/r**remaining


@lru_cache(maxsize=None)
def policies(remaining):
    """All full-history adapted stopping trees; after stopping no choices remain."""
    if remaining == 0:
        return (("stop",),)
    children = policies(remaining-1)
    return (("stop",),)+tuple(("wait", down, up) for down in children for up in children)


def rule_value(rule, s, k, u, d, r, q, kind):
    if rule[0] == "stop":
        return cash(s, k, kind)
    return ((1-q)*rule_value(rule[1], s*d, k, u, d, r, q, kind)
            +q*rule_value(rule[2], s*u, k, u, d, r, q, kind))/r


@lru_cache(maxsize=None)
def enumerated_american(s, k, u, d, r, remaining, kind):
    require(remaining <= 4, "full policy enumeration intentionally limited to four periods")
    q = (r-d)/(u-d)
    return max(rule_value(rule, s, k, u, d, r, q, kind) for rule in policies(remaining))


def cramer(stock_down, stock_up, gross, payoff_down, payoff_up):
    """Exact two-equation determinant ratios, returning shares and current cash."""
    determinant = gross*(stock_up-stock_down)
    delta = gross*(payoff_up-payoff_down)/determinant
    bank = (stock_up*payoff_down-stock_down*payoff_up)/determinant
    return delta, bank


def parsed(data):
    return tuple(F(data[key]) for key in ("spot", "strike", "up", "down", "gross_rate"))


class Fragment(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack, self.ids, self.sources = [], [], []
        self.worked = self.exercises = self.solutions = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        require(tag not in {"html", "body", "h1"}, "HTML must remain a chapter fragment")
        if "id" in attrs:
            self.ids.append(attrs["id"])
        if attrs.get("href", "").startswith("sources.html#"):
            self.sources.append(attrs["href"].split("#", 1)[1])
        if tag == "aside" and "worked" in attrs.get("class", "").split():
            self.worked += 1
        if tag == "li" and self.stack and self.stack[-1][0] == "ol":
            if "exercises" in self.stack[-1][1].get("class", "").split():
                self.exercises += 1
            if any(t == "details" and "solutions" in a.get("class", "").split() for t, a in self.stack):
                self.solutions += 1
        if tag not in {"br", "hr", "img", "input", "link", "meta"}:
            self.stack.append((tag, attrs))

    def handle_endtag(self, tag):
        require(self.stack and self.stack[-1][0] == tag, "unbalanced HTML "+tag)
        self.stack.pop()


def check():
    comparisons = rejections = 0
    scenarios = []
    groups = []

    def equal(actual, expected, label):
        nonlocal comparisons
        comparisons += 1
        require(actual == expected, f"{label}: {actual!r} != {expected!r}")

    def rational(actual, expected, label):
        equal(F(actual), F(expected), label)

    def node_oracle(kind, style, s, k, u, d, r, remaining):
        if style == "european":
            return european(s, k, u, d, r, remaining, kind)
        return enumerated_american(s, k, u, d, r, remaining, kind)

    def tree_audit(tree, parameters, steps, label):
        s, k, u, d, r = parameters
        q = (r-d)/(u-d)
        rational(tree["q_up"], q, label+" pricing law")
        expected_stock = [[str(s*u**j*d**(t-j)) for j in range(t+1)] for t in range(steps+1)]
        equal(tree["stock"], expected_stock, label+" full stock lattice")
        for kind in ("call", "put"):
            for style in ("european", "american_grid"):
                rows = tree["contracts"][kind+"_"+style]
                equal(len(rows), steps+1, label+" time count")
                for t, row in enumerate(rows):
                    equal(len(row), t+1, label+" node count")
                    for j, node in enumerate(row):
                        stock = s*u**j*d**(t-j)
                        intrinsic = cash(stock, k, kind)
                        prefix = f"{label} {kind} {style} ({t},{j})"
                        rational(node["stock"], stock, prefix+" stock")
                        rational(node["intrinsic"], intrinsic, prefix+" immediate payoff")
                        if style == "european" or steps-t <= 4:
                            rational(node["value"], node_oracle(kind, style, stock, k, u, d, r, steps-t), prefix+" independent price")
                        if t == steps:
                            equal(node["action"], "settle", prefix+" final action")
                            continue
                        down, up = F(rows[t+1][j]["value"]), F(rows[t+1][j+1]["value"])
                        delta, bank = cramer(stock*d, stock*u, r, down, up)
                        continuation = ((1-q)*down+q*up)/r
                        value = F(node["value"])
                        rational(node["continuation_delta"], delta, prefix+" determinant shares")
                        rational(node["continuation_bank"], bank, prefix+" determinant cash")
                        rational(node["continuation"], continuation, prefix+" continuation Arrow prices")
                        rational(node["exercise_value_less_continuation"], intrinsic-continuation, prefix+" exercise comparison")
                        rational(node["cash_above_continuation_cost"], value-continuation, prefix+" writer surplus")
                        rational(node["down_replication_residual"], 0, prefix+" reported down residual")
                        rational(node["up_replication_residual"], 0, prefix+" reported up residual")
                        rational(F(node["continuation_delta"])*stock*d+r*F(node["continuation_bank"]), down, prefix+" actual down replication")
                        rational(F(node["continuation_delta"])*stock*u+r*F(node["continuation_bank"]), up, prefix+" actual up replication")
                        if style == "american_grid":
                            # This is an upper certificate for any adapted policy.
                            # The lower certificate is its feasible policy expectation,
                            # independently accumulated over all complete paths below.
                            require(value >= intrinsic and value >= continuation, prefix+" dominating supermartingale")
                            action = "exercise" if intrinsic > continuation else "continue"
                            equal(node["action"], action, prefix+" feasible optimizing action")
                            rational(value, intrinsic if action == "exercise" else continuation, prefix+" active bound")
                        else:
                            equal(node["action"], "continue", prefix+" European cannot stop")
                            rational(value, continuation, prefix+" European martingale")
                if style == "american_grid":
                    present_receipts = F(0)
                    for bits in product((0, 1), repeat=steps):
                        probability = q**sum(bits)*(1-q)**(steps-sum(bits))
                        j = 0
                        for t in range(steps+1):
                            node = rows[t][j]
                            if t == steps or node["action"] == "exercise":
                                present_receipts += probability*cash(s*u**j*d**(t-j), k, kind)/r**t
                                break
                            j += bits[t]
                    rational(rows[0][0]["value"], present_receipts, label+" feasible policy attains supermartingale bound "+kind)
        call, put = [F(tree["contracts"][kind+"_european"][0][0]["value"]) for kind in ("call", "put")]
        rational(tree["european_parity_lhs"], call-put, label+" parity left")
        rational(tree["european_parity_rhs"], s-k/r**steps, label+" parity right")
        rational(call-put, s-k/r**steps, label+" independent parity")
        require(max(F(0), s-k/r**steps) <= call <= s, label+" call bounds")
        require(max(F(0), k/r**steps-s) <= put <= k/r**steps, label+" put bounds")
        american_call = F(tree["contracts"]["call_american_grid"][0][0]["value"])
        american_put = F(tree["contracts"]["put_american_grid"][0][0]["value"])
        rational(tree["american_put_premium"], american_put-put, label+" early premium")
        require(american_call >= call and american_put >= put, label+" extra exercise rights")
        if r >= 1:
            rational(american_call, call, label+" nondividend nonnegative-rate call theorem")

    def paths_audit(report, tree, data, label):
        s, k, u, d, r = parsed(data)
        steps = data["steps"]
        p, fee = F(data["physical_up"]), F(data["interior_rebalance_fee"])
        q = (r-d)/(u-d)
        expected_words = ["".join("U" if b else "D" for b in bits) for bits in product((0, 1), repeat=steps)]
        equal([row["path"] for row in report["paths"]], expected_words, label+" exhaustive paths")
        stop_pv = {"call": F(0), "put": F(0)}
        physical_payoff = F(0)
        common_history_decisions = {}
        for path in report["paths"]:
            word = path["path"]
            ups = word.count("U")
            qweight, pweight = q**ups*(1-q)**(steps-ups), p**ups*(1-p)**(steps-ups)
            rational(path["pricing_probability"], qweight, label+" path Q probability")
            rational(path["physical_probability"], pweight, label+" path physical probability")
            stock = s
            down_value = european(s*d, k, u, d, r, steps-1, "call")
            up_value = european(s*u, k, u, d, r, steps-1, "call")
            delta, bank = cramer(s*d, s*u, r, down_value, up_value)
            fees = []
            equal(len(path["european_call_ledger"]), steps, label+" complete hedge ledger")
            for t, (direction, row) in enumerate(zip(word, path["european_call_ledger"]), 1):
                stock *= u if direction == "U" else d
                wealth = delta*stock+r*bank
                equal(row["date"], t, label+" ledger date")
                for key, value in {"stock": stock, "inherited_delta": delta, "inherited_bank_after_interest": r*bank,
                                   "pre_trade_wealth": wealth, "call_value": european(stock, k, u, d, r, steps-t, "call")}.items():
                    rational(row[key], value, label+" ledger "+key)
                if t < steps:
                    next_down = european(stock*d, k, u, d, r, steps-t-1, "call")
                    next_up = european(stock*u, k, u, d, r, steps-t-1, "call")
                    new_delta, new_bank = cramer(stock*d, stock*u, r, next_down, next_up)
                    trade = (new_delta-delta)*stock
                    fee_cash = abs(trade)*fee
                    fees.append((t, fee_cash))
                    for key, value in {"new_delta": new_delta, "new_bank": new_bank, "stock_trade_cash": trade,
                                       "bank_change": new_bank-r*bank, "external_cash_required": F(0), "intervention_fee": fee_cash}.items():
                        rational(row[key], value, label+" rebalance "+key)
                    rational(trade+new_bank-r*bank, 0, label+" independent rebalance financing")
                    delta, bank = new_delta, new_bank
                else:
                    terminal = cash(stock, k, "call")
                    error = -sum((amount*r**(steps-date) for date, amount in fees), F(0))
                    rational(row["payoff"], terminal, label+" payoff")
                    rational(row["exact_hedge_error"], 0, label+" frictionless error")
                    rational(row["fee_intervention_hedge_error"], error, label+" separately accumulated fee debt")
                    rational(wealth, terminal, label+" independent terminal cash")
                    physical_payoff += pweight*terminal
            for kind in ("call", "put"):
                rows = tree["contracts"][kind+"_american_grid"]
                j = 0
                for t in range(steps+1):
                    node = rows[t][j]
                    stopping = t == steps or node["action"] == "exercise"
                    history = (kind, word[:t])
                    if history in common_history_decisions:
                        equal(stopping, common_history_decisions[history], label+" identical information decision")
                    common_history_decisions[history] = stopping
                    if stopping:
                        receipt = cash(s*u**j*d**(t-j), k, kind)
                        expected = {"date": t, "stock": str(s*u**j*d**(t-j)), "receipt": str(receipt), "discounted_receipt": str(receipt/r**t)}
                        equal(path["american_grid_optimal_stopping"][kind], expected, label+" stopped cash and date")
                        stop_pv[kind] += qweight*receipt/r**t
                        break
                    j += word[t] == "U"
        rational(sum(F(row["pricing_probability"]) for row in report["paths"]), 1, label+" Q mass")
        rational(sum(F(row["physical_probability"]) for row in report["paths"]), 1, label+" physical mass")
        rational(report["european_call_physical_expected_payoff"], physical_payoff, label+" physical mean terminal payoff")
        for kind, value in stop_pv.items():
            rational(report["optimal_stopping_discounted_pricing_expectations"][kind], value, label+" stopping sum "+kind)
            rational(tree["contracts"][kind+"_american_grid"][0][0]["value"], value, label+" stopping and root value "+kind)

    def dividend_audit(actual, data, label):
        s, k, up, down, dividend, r = [F(data[key]) for key in ("spot", "strike", "ex_up", "ex_down", "cash_dividend", "gross_rate")]
        q = (r*s-(down+dividend))/(up-down)
        rational(actual["q_up_total_gain"], q, label+" total-gain pricing weight")
        rational(actual["dividend_pv"], dividend/r, label+" cash strip")
        rational(actual["prepaid_terminal_stock"], s-dividend/r, label+" prepaid stock")
        values = {}
        for kind in ("call", "put"):
            hu, hd = cash(up, k, kind), cash(down, k, kind)
            delta, bank = cramer(down+dividend, up+dividend, r, hd, hu)
            value = ((1-q)*hd+q*hu)/r
            immediate = cash(s, k, kind)
            node = actual["contracts"][kind]
            expected = {"down_payoff": hd, "up_payoff": hu, "delta": delta, "bank": bank,
                        "european_value": value, "immediate_exercise": immediate,
                        "american_grid_value": max(value, immediate),
                        "down_hedge_residual": F(0), "up_hedge_residual": F(0)}
            for key, target in expected.items():
                rational(node[key], target, label+" "+kind+" "+key)
            equal(node["action"], "exercise" if immediate > value else "continue", label+" dividend exercise")
            rational(delta*(down+dividend)+r*bank, hd, label+" actual dividend down cash")
            rational(delta*(up+dividend)+r*bank, hu, label+" actual dividend up cash")
            values[kind] = value
        rational(actual["european_parity_lhs"], values["call"]-values["put"], label+" dividend parity left")
        rational(actual["european_parity_rhs"], s-(dividend+k)/r, label+" dividend parity right")
        rational(values["call"]-values["put"], s-(dividend+k)/r, label+" independent dividend parity")

    raw = json.loads((ASSETS/"v10-c06-inputs.json").read_text())
    unchanged = deepcopy(raw)
    capture = StringIO()
    with redirect_stdout(capture), redirect_stderr(capture):
        model = runpy.run_path(str(ASSETS/"v10-c06-analysis.py"))
        base = model["run"](raw)
    equal(capture.getvalue(), "", "quiet import and API")
    equal(raw, unchanged, "API preserves inputs")
    tree_audit(base["single_step"], parsed(raw["tree"]), 1, "worked one period")
    tree_audit(base["tree"], parsed(raw["tree"]), raw["tree"]["steps"], "worked two periods")
    paths_audit(base["path_reports"], base["tree"], raw["tree"], "worked funded hedge")
    tree_audit(base["negative_rate_case"], parsed(raw["negative_rate_call"]), 1, "worked negative rate")
    dividend_audit(base["dividend_case"], raw["dividend_call"], "worked dividend")
    equal(base, json.loads((ASSETS/"v10-c06-output.json").read_text()), "saved output secondary full comparison")
    json.dumps(base, allow_nan=False)
    groups.append("all baseline nodes and hedges: direct binomial terminal sums, determinant replicas, independently enumerated adapted policies, and complete funded path ledgers")

    def scenario(name, section, updates):
        data = deepcopy(raw)
        data[section].update(updates)
        snapshot = deepcopy(data)
        with redirect_stdout(capture), redirect_stderr(capture):
            actual = model["run"](data)
        equal(data, snapshot, name+" unchanged inputs")
        if section == "tree":
            tree_audit(actual["single_step"], parsed(data["tree"]), 1, name+" one step")
            tree_audit(actual["tree"], parsed(data["tree"]), data["tree"]["steps"], name)
            paths_audit(actual["path_reports"], actual["tree"], data["tree"], name)
            equal(actual["negative_rate_case"], base["negative_rate_case"], name+" independent negative case")
            equal(actual["dividend_case"], base["dividend_case"], name+" independent dividend case")
        elif section == "dividend_call":
            dividend_audit(actual["dividend_case"], data["dividend_call"], name)
            for key in ("single_step", "tree", "path_reports", "negative_rate_case"):
                equal(actual[key], base[key], name+" unaffected "+key)
        else:
            tree_audit(actual["negative_rate_case"], parsed(data[section]), 1, name)
            for key in ("single_step", "tree", "path_reports", "dividend_case"):
                equal(actual[key], base[key], name+" unaffected "+key)
        scenarios.append(name)
        return actual

    physical = scenario("physical probability changes frequencies only", "tree", {"physical_up": "1/4"})
    equal(physical["tree"], base["tree"], "physical input cannot change replication prices")
    rational(F(physical["path_reports"]["european_call_physical_expected_payoff"])/F("21/20")**2, "1075/441", "exercise 6 physical discount mean")
    zero_fee = scenario("zero fee eliminates all intervention shortfalls", "tree", {"interior_rebalance_fee": "0"})
    equal(zero_fee["tree"], base["tree"], "fee intervention cannot reprice ideal tree")
    for path in zero_fee["path_reports"]["paths"]:
        rational(path["european_call_ledger"][-1]["fee_intervention_hedge_error"], 0, "zero fee terminal hedge")
    scenario("one period has no interior stock-trade fee", "tree", {"steps": 1, "interior_rebalance_fee": "1/10"})
    transfer = scenario("exercise 5 strike 88 changes adapted put policy value", "tree", {"strike": "88"})
    rational(transfer["tree"]["contracts"]["put_american_grid"][0][0]["value"], "1984/147", "exercise 5 grid value")
    rational(transfer["tree"]["contracts"]["put_european"][0][0]["value"], "5248/441", "exercise 5 European value")
    rational(transfer["tree"]["american_put_premium"], "704/441", "exercise 5 premium")
    new_hedge = scenario("exercise 4 fresh two-period zero-rate market", "tree", {
        "spot": "60", "strike": "61", "up": "4/3", "down": "2/3", "gross_rate": "1"})
    rational(new_hedge["tree"]["contracts"]["call_european"][0][0]["value"], "137/12", "exercise 4 call")
    rational(new_hedge["tree"]["contracts"]["put_european"][0][0]["value"], "149/12", "exercise 4 put")
    scenario("zero strike exposes exercise ties", "tree", {"strike": "0"})
    scenario("negative-rate multi-period call exercise", "tree", {
        "spot": "100", "strike": "80", "up": "11/10", "down": "9/10", "gross_rate": "49/50", "steps": 3})
    scenario("four-period full-history stopping policy enumeration", "tree", {"steps": 4})
    scenario("six-period domain and supermartingale policy certificate", "tree", {"steps": 6})
    scaled = scenario("uniform threefold monetary scale", "tree", {"spot": "240", "strike": "246"})
    for contract in base["tree"]["contracts"]:
        rational(scaled["tree"]["contracts"][contract][0][0]["value"], 3*F(base["tree"]["contracts"][contract][0][0]["value"]), "scale price "+contract)
    no_dividend = scenario("remove payout while retaining stock total gains", "dividend_call", {"cash_dividend": "0", "ex_up": "112", "ex_down": "82"})
    equal(no_dividend["dividend_case"]["q_up_total_gain"], base["dividend_case"]["q_up_total_gain"], "same total gains same pricing law")
    equal(no_dividend["dividend_case"]["contracts"]["call"]["action"], "continue", "nondividend call need not exercise")
    scenario("larger known payout shifts total-gain probability", "dividend_call", {"cash_dividend": "15"})
    groups.append("financial interventions: physical versus pricing law, fee timing, strike, scale, rate/dividend boundaries, exhaustive policies and six-period certificates")

    # Independent manuscript numerical checks, including transactions not in the lab.
    s, su, sd, r, k = F(62), F(80), F(50), F("1.04"), F(64)
    q = (r*s-sd)/(su-sd)
    rational(q, "181/375", "exercise 1 q")
    for kind, values in {"call": ("8/15", "-1000/39", "1448/195"), "put": ("-7/15", "1400/39", "1358/195")}.items():
        delta, bank = cramer(sd, su, r, cash(sd, k, kind), cash(su, k, kind))
        rational(delta, values[0], "exercise 1 shares "+kind)
        rational(bank, values[1], "exercise 1 cash "+kind)
        rational(delta*s+bank, values[2], "exercise 1 price "+kind)
    premium_debt = F("1448/195")*r
    rational(16-premium_debt, "3104/375", "exercise 1 funded up profit")
    rational(-premium_debt, "-2896/375", "exercise 1 funded down loss")
    for gross, targets in ((F(".98"), (F("15.4"), F("1.4"))), (F(1), (F(14), F(0)))):
        equal((F(84)-70*gross, F(70)-70*gross), targets, "exercise 2 boundary arbitrage")
    rational(4+52*F(".96")-5-50+2*F(".99"), ".9", "exercise 3 initial parity receipt")
    rational(F(2)-2, 0, "exercise 3 dividend repayment")
    for spot in (F(0), F(50), F(52), F(80)):
        rational(spot+cash(spot, F(52), "put")-cash(spot, F(52), "call")-52, 0, "exercise 3 terminal parity cash")
    original = parsed(raw["tree"])
    hindsight = F(0)
    for bits in product((0, 1), repeat=2):
        stock = original[0]
        receipts = [cash(stock, original[1], "put")]
        for t, bit in enumerate(bits, 1):
            stock *= original[2] if bit else original[3]
            receipts.append(cash(stock, original[1], "put")/original[4]**t)
        hindsight += F("3/5")**sum(bits)*F("2/5")**(2-sum(bits))*max(receipts)
    rational(hindsight, "139378/11025", "worked hindsight information value")
    require(hindsight > F("208/21"), "hindsight differs from adapted optimum")
    equal([len(policies(n)) for n in range(5)], [1, 2, 5, 26, 677], "complete full-history stopping policy counts")
    # General proofs are audited in writing; these are independent sign/shape cases.
    rational(F(100)-80/F(".98"), "900/49", "exercise 7 failed positive-rate comparison")
    rational(F(18)-2*14+8, -2, "exercise 8 butterfly initial receipt")
    for spot, target in ((F(0), 0), (F(70), 0), (F(75), 5), (F(80), 10), (F(85), 5), (F(90), 0), (F(120), 0)):
        rational(cash(spot, F(70), "call")-2*cash(spot, F(80), "call")+cash(spot, F(90), "call"), target, "exercise 8 payoff intervals")
    up_trade = (F("43/50")-F("43/70"))*100
    down_trade = F("43/70")*60
    rational(up_trade, "172/7", "exercise 9 up purchase")
    rational(down_trade, "258/7", "exercise 9 down liquidation")
    up_shortfall, down_shortfall = [amount*F(".01")*F("1.05") for amount in (up_trade, down_trade)]
    rational(up_shortfall, "129/500", "exercise 9 funded up fee")
    rational(down_shortfall, "387/1000", "exercise 9 funded down fee")
    reserve = max(up_shortfall, down_shortfall)/F("1.05")**2
    rational(reserve, "86/245", "exercise 9 minimum deterministic fixed-strategy reserve")
    rational(reserve*F("1.05")**2-up_shortfall, ".129", "exercise 9 up residual")
    rational(reserve*F("1.05")**2-down_shortfall, 0, "exercise 9 down residual")
    retention_delta, retention_bank = cramer(F(40), F(60), F(1), F(0), F(8))
    rational(retention_delta, ".4", "retention shares")
    rational(retention_bank, -16, "retention bank")
    rational(retention_delta*50+retention_bank, 4, "retention premium")
    rational(F(12)-F("10.5"), "1.5", "retention writer surplus")
    groups.append("all determinate manuscript problems, funded parity trade, hindsight counterexample, butterfly cash, fixed-strategy reserve and retention; general proofs/open critique reviewed analytically")

    def reject(label, edit):
        nonlocal rejections
        data = deepcopy(raw)
        edit(data)
        try:
            model["run"](data)
        except ValueError:
            rejections += 1
        else:
            raise AssertionError("accepted invalid input: "+label)

    for section, field in (("tree", "spot"), ("negative_rate_call", "spot"), ("dividend_call", "spot")):
        for invalid in (True, 100, 100.0, None, float("inf"), "NaN", "Infinity", "1/0", "1e2", ".5", "+1", "123456789", "1.123456789", "1/123456789", "-1"):
            reject("bounded exact string "+section, lambda data, s=section, f=field, v=invalid: data[s].__setitem__(f, v))
    invalid_cases = [
        ("bool schema", lambda d: d.__setitem__("schema", True)),
        ("wrong schema", lambda d: d.__setitem__("schema", 2)),
        ("market rights changed", lambda d: d.__setitem__("contract", "unsigned only")),
        ("unknown field", lambda d: d["tree"].__setitem__("dividend", "1")),
        ("missing field", lambda d: d["tree"].pop("strike")),
        ("bool steps", lambda d: d["tree"].__setitem__("steps", True)),
        ("zero periods", lambda d: d["tree"].__setitem__("steps", 0)),
        ("seven periods", lambda d: d["tree"].__setitem__("steps", 7)),
        ("float steps", lambda d: d["tree"].__setitem__("steps", 2.0)),
        ("stock zero", lambda d: d["tree"].__setitem__("spot", "0")),
        ("stock bound", lambda d: d["tree"].__setitem__("spot", "10001")),
        ("negative strike", lambda d: d["tree"].__setitem__("strike", "-1")),
        ("strike bound", lambda d: d["tree"].__setitem__("strike", "10001")),
        ("lower rate endpoint", lambda d: d["tree"].__setitem__("gross_rate", "3/4")),
        ("upper rate endpoint", lambda d: d["tree"].__setitem__("gross_rate", "5/4")),
        ("rank one", lambda d: d["tree"].update({"down": "1", "up": "1", "gross_rate": "1"})),
        ("branch reversed", lambda d: d["tree"].__setitem__("up", "1/2")),
        ("down outside bound", lambda d: d["tree"].__setitem__("down", "9/100")),
        ("up outside bound", lambda d: d["tree"].__setitem__("up", "31/10")),
        ("physical zero support", lambda d: d["tree"].__setitem__("physical_up", "0")),
        ("physical unit support", lambda d: d["tree"].__setitem__("physical_up", "1")),
        ("negative fee", lambda d: d["tree"].__setitem__("interior_rebalance_fee", "-1/100")),
        ("fee outside domain", lambda d: d["tree"].__setitem__("interior_rebalance_fee", "11/100")),
        ("named rate case nonnegative", lambda d: d["negative_rate_call"].__setitem__("gross_rate", "1")),
        ("dividend clock changed", lambda d: d["dividend_call"].__setitem__("contract", "exercise anytime")),
        ("dividend omitted from total gain", lambda d: d["dividend_call"].__setitem__("cash_dividend", "0")),
        ("dividend negative", lambda d: d["dividend_call"].__setitem__("cash_dividend", "-1")),
        ("dividend q upper endpoint", lambda d: d["dividend_call"].__setitem__("cash_dividend", "2")),
        ("dividend q lower endpoint", lambda d: d["dividend_call"].__setitem__("cash_dividend", "32")),
        ("dividend rank one", lambda d: d["dividend_call"].__setitem__("ex_down", "100")),
        ("dividend zero asset", lambda d: d["dividend_call"].__setitem__("ex_down", "0")),
        ("dividend gross bound", lambda d: d["dividend_call"].__setitem__("gross_rate", "0")),
    ]
    for label, edit in invalid_cases:
        reject(label, edit)
    equal(capture.getvalue(), "", "all successful API runs remain quiet")
    groups.append("numeric grammar, bounded domain, strictly positive physical/pricing support, singular replicas, fees and dividend-right rejection cases")

    # All author files are now frozen; missing supporting material must fail.
    package_ready = all((ROOT/path).is_file() for path in AUTHOR_PATHS)
    require(package_ready, "all nine final author files are required")
    if package_ready:
        manifest = json.loads((ASSETS/"v10-c06-manifest.json").read_text())
        expected_files = {"v10-c06-"+suffix for suffix in ("inputs.json", "analysis.py", "output.json", "README.txt")}
        equal({entry["file"] for entry in manifest["files"]}, expected_files, "four-file manifest scope")
        for entry in manifest["files"]:
            payload = (ASSETS/entry["file"]).read_bytes()
            equal((len(payload), sha256(payload).hexdigest()), (entry["bytes"], entry["sha256"]), "manifest "+entry["file"])
        author = json.loads((ROOT/AUTHOR_PATHS[-1]).read_text())
        equal({entry["path"] for entry in author["reviewed_hashes"]}, set(AUTHOR_PATHS[:-1]), "author eight payload scope")
        for entry in author["reviewed_hashes"]:
            payload = (ROOT/entry["path"]).read_bytes()
            equal((len(payload), sha256(payload).hexdigest()), (entry["bytes"], entry["sha256"]), "author hash "+entry["path"])
        peer_path = ROOT/"content/reviews/v10-c06-peer.json"
        require(peer_path.is_file(), "the peer record with all nine final hashes is required")
        if peer_path.exists():
            peer = json.loads(peer_path.read_text())
            equal({entry["path"] for entry in peer["reviewed_hashes"]}, set(AUTHOR_PATHS), "peer nine author payload scope")
            for entry in peer["reviewed_hashes"]:
                payload = (ROOT/entry["path"]).read_bytes()
                equal((len(payload), sha256(payload).hexdigest()), (entry["bytes"], entry["sha256"]), "peer hash "+entry["path"])

    copy_names = ["v10-c06-"+suffix for suffix in ("inputs.json", "analysis.py", "output.json")]
    if package_ready:
        copy_names += ["v10-c06-README.txt", "v10-c06-manifest.json"]
    with tempfile.TemporaryDirectory(prefix="v10-c06-peer-") as temporary:
        temp = Path(temporary)
        source, unrelated = temp/"source", temp/"unrelated"
        source.mkdir()
        unrelated.mkdir()
        for name in copy_names:
            shutil.copyfile(ASSETS/name, source/name)
        changed = deepcopy(raw)
        changed["tree"]["strike"] = "88"
        (source/"changed.json").write_text(json.dumps(changed))
        for flags in ([], ["-O"]):
            command = [sys.executable]+flags+[str(source/"v10-c06-analysis.py")]
            for filename, expected in (("v10-c06-inputs.json", base), ("changed.json", transfer)):
                args = command+["--input", str(source/filename)]
                proc = subprocess.run(args, cwd=unrelated, capture_output=True, text=True, check=True)
                equal(proc.stderr, "", "portable stdout stderr")
                equal(json.loads(proc.stdout), expected, "portable API-verified contract "+str(flags)+filename)
                destination = unrelated/"output.json"
                proc = subprocess.run(args+["--output", str(destination)], cwd=unrelated, capture_output=True, text=True, check=True)
                equal((proc.stdout, proc.stderr), ("", ""), "portable file-output silence")
                equal(json.loads(destination.read_text()), expected, "portable explicit destination "+str(flags)+filename)
            for malformed in ('{"schema":1,"schema":1}', '{"schema":NaN}', '{"schema":Infinity}', '{"schema":-Infinity}', '{'):
                invalid_path = source/"invalid.json"
                invalid_path.write_text(malformed)
                destination = unrelated/"protected.txt"
                destination.write_text("retain old destination")
                proc = subprocess.run(command+["--input", str(invalid_path), "--output", str(destination)], cwd=unrelated, capture_output=True, text=True)
                require(proc.returncode != 0 and proc.stderr, "strict JSON must fail")
                equal(proc.stdout, "", "failed CLI no result")
                equal(destination.read_text(), "retain old destination", "failure preserves existing destination")
                rejections += 1
    groups.append("normal and optimized standalone CLI from unrelated directories; baseline/changed contracts, both output routes and strict-JSON destination preservation")

    fragment = Fragment()
    body = (ROOT/AUTHOR_PATHS[0]).read_text()
    fragment.feed(body)
    fragment.close()
    require(not fragment.stack, "closed fragment")
    equal(len(fragment.ids), len(set(fragment.ids)), "unique chapter anchors")
    equal((fragment.worked, fragment.exercises, fragment.solutions), (5, 10, 10), "graduate chapter package")
    require("teach-back" in fragment.ids and "Delayed retention" in body and "Model answer" in body, "answered teaching and retention")
    if package_ready:
        proposals = json.loads((ROOT/"content/reviews/v10-c06-sources.json").read_text())["proposals"]
        equal(set(fragment.sources), {source["id"] for source in proposals}, "exact source proposal and citation scope")
        canonical = {entry["id"]: entry for entry in json.loads((ROOT/"content/sources.json").read_text())}
        for source in proposals:
            if source["id"] in canonical:
                equal(source, canonical[source["id"]], "already integrated source record "+source["id"])
    groups.append("HTML exercise/solution structure and, after author freeze, source scope, manifest and eight/nine-payload review hashes")
    result = {
        "chapter": "v10-c06", "status": "passed", "author_package_ready": package_ready,
        "comparisons": comparisons,
        "count_definition": "Actual equality-check calls across independent prices/hedges, full paths, exercise numbers, invariant records, CLI, structure and integrity; require-style qualitative gates are additional and are not counted.",
        "invalid_inputs_rejected": rejections, "financial_intervention_runs": len(scenarios), "interventions": scenarios,
        "full_history_stopping_policy_counts_by_horizon": {str(n): len(policies(n)) for n in range(5)},
        "six_period_certificate": "All node values dominate exercise and discounted continuation; the reported adapted policy attains root value by an independent sum over all 64 paths.",
        "worked_examples_reviewed": 5, "exercise_solutions_reviewed": 10, "groups": groups,
        "limitations": "Separate machine-assisted peer audit. General proofs are reviewed analytically, not proved by finite test cases. No human certification, empirical contract authentication or visual UI QA.",
    }
    json.dumps(result, allow_nan=False)
    return result


if __name__ == "__main__":
    print(json.dumps(check(), indent=2, allow_nan=False))
