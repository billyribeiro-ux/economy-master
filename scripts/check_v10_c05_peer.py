"""Separate c05 peer audit: cash reconstruction, interventions, and portable CLI.

The author model is the system under test. Its saved output and author checker
are not numerical oracles. Proof/source-scope findings are in the peer record.
"""
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
from decimal import Decimal, localcontext
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from io import StringIO
from math import prod
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
    "content/chapters/v10-c05.html",
    "content/projects/v10-c05-inputs.json",
    "content/projects/v10-c05-analysis.py",
    "content/projects/v10-c05-output.json",
    "content/projects/v10-c05-manifest.json",
    "content/projects/v10-c05-README.txt",
    "scripts/check_v10_c05.py",
    "content/reviews/v10-c05-sources.json",
    "content/reviews/v10-c05-author.json",
)


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def exact(value):
    if isinstance(value, F):
        return str(value)
    if isinstance(value, dict):
        return {k: exact(v) for k, v in value.items()}
    if isinstance(value, list):
        return [exact(v) for v in value]
    return value


def oracle(data):
    """Independent dated cash construction, with closed-form debt accumulation."""
    c = data["carry"]
    strips = [(F(e["time"]), F(e["income"])-F(e["cost"]), F(e["discount"]))
              for e in c["events"]]
    initial_strip = sum((cash*df for _, cash, df in strips), F(0))
    delivered_asset_pv = F(c["spot"])-initial_strip
    terminal_debt = delivered_asset_pv/F(c["discount"])
    carry = {
        "prepaid_delivery": delivered_asset_pv,
        "fair_forward": terminal_debt,
        "long_value": (terminal_debt-F(c["delivery_price"]))*F(c["discount"]),
        "terminal_excess_of_quoted_delivery": F(c["delivery_price"])-terminal_debt,
        "replication": [{"time": t, "asset_net_receipt": cash,
                         "strip_borrowing_at_zero": cash*df,
                         "strip_repayment": cash, "interim_net_cash": cash-cash}
                        for t, cash, df in strips],
        "maturity_borrowing_at_zero": terminal_debt*F(c["discount"]),
        "maturity_repayment": terminal_debt,
        "initial_cash_residual": delivered_asset_pv+initial_strip-F(c["spot"]),
    }

    x = data["fx"]
    notional, spot = F(x["foreign_notional"]), F(x["spot_domestic_per_foreign"])
    foreign_deposit = notional*F(x["foreign_discount"])
    domestic_debt = foreign_deposit*spot/F(x["domestic_discount"])
    contracted_delivery = notional*F(x["delivery_price"])
    fx = {
        "fair_domestic_per_foreign": domestic_debt/notional,
        "domestic_prepaid_per_foreign": domestic_debt*F(x["domestic_discount"])/notional,
        "foreign_deposit_today": foreign_deposit,
        "domestic_funding_today": foreign_deposit*spot,
        "domestic_funding_repayment": domestic_debt,
        "long_value_domestic": (domestic_debt-contracted_delivery)*F(x["domestic_discount"]),
        "short_terminal_surplus_domestic": contracted_delivery-domestic_debt,
    }

    t = data["tree"]
    p, spots, rates = [list(map(F, t[k])) for k in ("probabilities", "terminal_spot", "second_gross")]
    first = F(t["first_gross"])
    # Price every Arrow claim first. The fair strike clears the separately
    # priced terminal cash portfolio; the first settlement clears at date 1.
    arrows = [probability/first/rate for probability, rate in zip(p, rates)]
    bond = sum(arrows, F(0))
    stock = sum((state_price*cash for state_price, cash in zip(arrows, spots)), F(0))
    strike = stock/bond
    first_date_prices = [probability/first for probability in p]
    quote = sum((price*cash for price, cash in zip(first_date_prices, spots)), F(0))/sum(first_date_prices)
    changes = [cash-quote for cash in spots]
    funded = [change*rate for change, rate in zip(changes, rates)]
    forwards = [cash-strike for cash in spots]
    discounts = [state_price/probability for state_price, probability in zip(arrows, p)]
    mean_discount = sum((probability*discount for probability, discount in zip(p, discounts)), F(0))
    covariance = sum((probability*(cash-quote)*(discount-mean_discount)
                      for probability, cash, discount in zip(p, spots, discounts)), F(0))
    tree = {
        "bond_price": bond, "spot_price": stock,
        "node_spot": [cash/rate for cash, rate in zip(spots, rates)],
        "path_discounts": discounts, "forward_quote": strike,
        "futures_quote": quote, "futures_minus_forward": quote-strike,
        "covariance_spot_discount": covariance, "date_one_variation": changes,
        "funded_terminal_futures": funded, "forward_terminal": forwards,
        "futures_discounted_value": sum((price*cash for price, cash in zip(arrows, funded)), F(0)),
        "forward_discounted_value": sum((price*cash for price, cash in zip(arrows, forwards)), F(0)),
    }

    m = data["margin"]
    prices, funding = list(map(F, m["quotes"])), list(map(F, m["funding_gross"]))
    initial, maintenance = F(m["initial"]), F(m["maintenance"])
    signed_size = F(m["contracts"])*F(m["multiplier"])
    deposits = [initial]
    ledger = []
    # Compute balances from cumulative quotation changes and all external
    # deposits. Compute each debt from a sum of separately accumulated deposits,
    # rather than reproducing the author's rolling account/debt recurrences.
    for date in range(1, len(prices)):
        before = sum(deposits)+signed_size*(prices[date]-prices[0])
        if date == len(prices)-1:
            deposit = -before if before < 0 else F(0)
        else:
            deposit = initial-before if before < maintenance else F(0)
        deposits.append(deposit)
        debt = sum((cash*prod(funding[j:date]) for j, cash in enumerate(deposits)), F(0))
        ledger.append({"date": date, "variation": signed_size*(prices[date]-prices[date-1]),
                       "balance_before_call": before, "call": deposit,
                       "balance_after_call": before+deposit, "funding_debt": debt})
    variation = signed_size*(prices[-1]-prices[0])
    principal = sum(deposits)
    release = principal+variation
    debt = sum((cash*prod(funding[j:]) for j, cash in enumerate(deposits)), F(0))
    margin = {
        "ledger": ledger, "total_variation": variation, "total_posted": principal,
        "terminal_release": release, "terminal_funding_debt": debt,
        "funding_cost": debt-principal, "net_after_funding": release-debt,
        "cash_identity_residual": release-principal-variation,
    }

    w = data["swap"]
    n, fixed_rate = F(w["notional"]), F(w["fixed_rate"])
    accrual, discount, projected = [list(map(F, w[k])) for k in ("accruals", "discounts", "projected_rates")]
    floating_cash = [n*years*rate for years, rate in zip(accrual, projected)]
    fixed_cash = [n*years*fixed_rate for years in accrual]
    float_pv = sum((cash*df for cash, df in zip(floating_cash, discount)), F(0))
    fixed_pv = sum((cash*df for cash, df in zip(fixed_cash, discount)), F(0))
    annuity = sum((years*df for years, df in zip(accrual, discount)), F(0))
    rate_differences = [((F(1) if j == 0 else discount[j-1])-df)/(years*df)
                        for j, (years, df) in enumerate(zip(accrual, discount))]
    single_float = sum((n*years*rate*df for years, rate, df in zip(accrual, rate_differences, discount)), F(0))
    swap = {
        "annuity": annuity, "floating_pv": float_pv, "fixed_pv": fixed_pv,
        "payer_fixed_value": float_pv-fixed_pv, "par_fixed": float_pv/(n*annuity),
        "single_curve_rates": rate_differences, "single_curve_floating_pv": single_float,
        "single_curve_par": single_float/(n*annuity),
        "pv_change_per_fixed_rate_unit": -n*annuity,
        "projected_coupon_amounts": floating_cash,
    }

    k = data["collateral"]
    principal, years = F(k["segregated_initial"]), F(k["year_fraction"])
    repaid = principal+principal*F(k["funding_rate"])*years
    returned = principal+principal*F(k["remuneration_rate"])*years
    collateral = {
        "fully_reusable_claim_value": F(k["receipt"])/F(k["collateral_gross"]),
        "segregated_funding_repayment": repaid,
        "segregated_margin_return": returned,
        "segregated_net_cost": repaid-returned,
    }

    b = data["basis"]
    units, contracts, multiplier = F(b["units"]), F(b["contracts"]), F(b["multiplier"])
    short_size = contracts*multiplier
    local_basis = F(b["terminal_local_spot"])-F(b["terminal_futures"])
    physical = units*(local_basis+F(b["terminal_futures"]))
    short_receipt = short_size*F(b["initial_futures"])-short_size*F(b["terminal_futures"])
    basis = {
        "sale_receipt": physical, "nominal_futures_receipt": short_receipt,
        "terminal_local_basis": local_basis, "cash_before_funding": physical+short_receipt,
        "cash_after_funding": physical+short_receipt-F(b["funding_cost"]),
        "matched_quantity": short_size == units,
    }
    return exact({"schema": data["schema"], "carry": carry, "fx": fx, "tree": tree,
                  "margin": margin, "swap": swap, "collateral": collateral, "basis": basis})


class Fragment(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack, self.ids, self.sources = [], [], []
        self.worked = self.exercises = self.solutions = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        require(tag not in {"h1", "html", "body"}, "chapter must remain a fragment")
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
        require(bool(self.stack) and self.stack[-1][0] == tag, "unbalanced HTML "+tag)
        self.stack.pop()


def check():
    comparisons = 0
    rejected = 0
    intervention_names = []
    groups = []

    def equal(actual, expected, label):
        nonlocal comparisons
        comparisons += 1
        require(actual == expected, f"{label}: {actual!r} != {expected!r}")

    def rational(actual, expected, label):
        equal(F(actual), F(expected), label)

    def whole(actual, expected, label):
        # Count actual scalar checks; dictionary/list structure is also checked.
        if isinstance(expected, dict):
            require(type(actual) is dict and set(actual) == set(expected), label+" keys")
            for key in expected:
                whole(actual[key], expected[key], label+"."+key)
        elif isinstance(expected, list):
            require(type(actual) is list and len(actual) == len(expected), label+" length")
            for i, value in enumerate(expected):
                whole(actual[i], value, label+"["+str(i)+"]")
        else:
            require(type(actual) is type(expected), label+" output type")
            equal(actual, expected, label)

    raw = json.loads((ASSETS/"v10-c05-inputs.json").read_text())
    original = deepcopy(raw)
    capture = StringIO()
    with redirect_stdout(capture), redirect_stderr(capture):
        model = runpy.run_path(str(ASSETS/"v10-c05-analysis.py"))
        base = model["run"](raw)
    equal(capture.getvalue(), "", "quiet module and API")
    equal(raw, original, "unmutated baseline input")
    whole(base, oracle(raw), "independent baseline")
    equal(base, json.loads((ASSETS/"v10-c05-output.json").read_text()), "saved output secondary comparison")
    json.dumps(base, allow_nan=False)
    groups.append("all baseline output fields versus independent dated cash and Arrow-price constructions")

    def intervene(name, section, replacement):
        data = deepcopy(raw)
        if callable(replacement):
            replacement(data)
        else:
            data[section].update(replacement)
        before = deepcopy(data)
        with redirect_stdout(capture), redirect_stderr(capture):
            actual = model["run"](data)
        equal(data, before, name+" input preserved")
        whole(actual[section], oracle(data)[section], name)
        for unchanged in set(base)-{section}:
            equal(actual[unchanged], base[unchanged], name+" unaffected "+unchanged)
        intervention_names.append(name)
        return actual[section]

    changed = intervene("carry net cost requires a dated deposit", "carry", {
        "events": [{"time": ".25", "discount": ".99", "income": 0, "cost": 7},
                   {"time": ".75", "discount": "1.01", "income": 3, "cost": 1}]})
    rational(changed["replication"][0]["strip_borrowing_at_zero"], "-6.93", "negative borrowing is funded deposit")
    intervene("carry zero income and negative yield", "carry", {"events": [], "discount": "1.05"})
    changed = intervene("old forward strike changes without replacing contract", "carry", {"delivery_price": 111})
    rational(F(changed["long_value"])-F(base["carry"]["long_value"]), "-9.5", "old strike derivative")
    changed = intervene("FX reciprocal quotation and swapped funding curves", "fx", {
        "spot_domestic_per_foreign": "5/6", "domestic_discount": ".99", "foreign_discount": ".96", "delivery_price": ".8"})
    rational(F(changed["fair_domestic_per_foreign"])*F(base["fx"]["fair_domestic_per_foreign"]), 1, "reciprocal forward units")
    changed = intervene("FX notional scaling", "fx", {"foreign_notional": 6000000})
    rational(changed["long_value_domestic"], -72000, "threefold FX exposure")

    changed = intervene("tree reverse rate and spot association", "tree", {"second_gross": [1, "1.2"]})
    rational(changed["futures_minus_forward"], "-20/11", "covariance gap reverses")
    changed = intervene("tree deterministic discount path", "tree", {"second_gross": ["1.1", "1.1"]})
    equal(changed["forward_quote"], changed["futures_quote"], "deterministic forward futures equality")
    changed = intervene("tree initial gross scales prices but not quotations", "tree", {"first_gross": "1.5"})
    equal(changed["forward_quote"], base["tree"]["forward_quote"], "unchanged forward quotient")
    equal(changed["futures_quote"], base["tree"]["futures_quote"], "unchanged first settlement mean")
    rational(changed["spot_price"], 60, "scaled initial spot")
    intervene("tree split identical states without changing aggregate prices", "tree", {
        "probabilities": [".2", ".3", ".5"], "second_gross": ["1.2", "1.2", 1], "terminal_spot": [120, 120, 80]})
    changed = intervene("tree single known state boundary", "tree", {
        "probabilities": [1], "second_gross": [".1"], "terminal_spot": [7], "first_gross": 3})
    rational(changed["futures_minus_forward"], 0, "no random cash quotation gap")
    changed = intervene("tree constant terminal price with random rates", "tree", {"terminal_spot": [80, 80]})
    rational(changed["futures_minus_forward"], 0, "zero covariance with stochastic rates")

    changed = intervene("margin equality at maintenance prevents a call", "margin", {"maintenance": 200})
    rational(changed["net_after_funding"], "25.5576", "reduced funded collateral cost")
    equal(changed["total_variation"], base["margin"]["total_variation"], "margin rules preserve trading variation")
    changed = intervene("margin no interest reconciles trading cash", "margin", {"funding_gross": [1, 1, 1]})
    equal(changed["net_after_funding"], changed["total_variation"], "zero rate net cash")
    changed = intervene("margin negative funding rate is permitted", "margin", {"funding_gross": [".99", ".98", ".97"]})
    require(F(changed["funding_cost"]) < 0, "negative funding cost")
    changed = intervene("margin mirrored short exposure and negative quotes", "margin", {"contracts": -1, "quotes": [-100, -96, -102, -101]})
    equal(changed, base["margin"], "two sign reversals preserve full cash ledger")
    changed = intervene("margin terminal deficit settled without restoring initial", "margin", {"quotes": [100, 100, 100, -20]})
    rational(changed["ledger"][-1]["call"], 5600, "terminal shortfall payment")
    rational(changed["terminal_release"], 0, "zero post-close balance")
    changed = intervene("margin 24-quote accumulation boundary", "margin", {
        "quotes": [100+(j % 3-1)*5 for j in range(24)], "funding_gross": ["1.001"]*23})
    rational(changed["cash_identity_residual"], 0, "longest dated cash identity")

    changed = intervene("swap contractual coupon basis point", "swap", {"fixed_rate": ".0451"})
    rational(F(changed["payer_fixed_value"])-F(base["swap"]["payer_fixed_value"]), -190, "contract coupon derivative")
    equal(changed["floating_pv"], base["swap"]["floating_pv"], "coupon leaves floating projection unchanged")
    changed = intervene("swap discount-ratio projection restores telescoping", "swap", {"projected_rates": base["swap"]["single_curve_rates"]})
    equal(changed["floating_pv"], changed["single_curve_floating_pv"], "matched projection telescopes")
    intervene("swap negative coupons and discounts above one", "swap", {
        "projected_rates": ["-.01", "-.02", "-.03"], "discounts": ["1.005", "1.02", "1.04"], "fixed_rate": "-.02"})
    changed = intervene("collateral equal financing and remuneration", "collateral", {"funding_rate": ".02"})
    rational(changed["segregated_net_cost"], 0, "matched simple rates return principal")
    changed = intervene("collateral zero separate margin", "collateral", {"segregated_initial": 0})
    equal(changed["fully_reusable_claim_value"], base["collateral"]["fully_reusable_claim_value"], "independent collateral arrangements")
    changed = intervene("collateral remuneration exceeds financing", "collateral", {"funding_rate": "-.01", "remuneration_rate": ".03"})
    rational(changed["segregated_net_cost"], -100, "negative net deposit cost")
    changed = intervene("basis partial hedge leaves quantity exposure", "basis", {"contracts": 1})
    equal(changed["matched_quantity"], False, "unmatched hedge flag")
    rational(changed["cash_after_funding"], 9550, "partial hedge terminal cash")
    changed = intervene("basis no contracts and measured funding credit", "basis", {"contracts": 0, "funding_cost": -25})
    rational(changed["cash_after_funding"], 9425, "no derivative still allows signed cash adjustment")
    groups.append("financial interventions with invariant neighboring cases and explicit boundary behavior")

    # Every determinate prompt is reconstructed separately from the solutions.
    e1 = intervene("exercise 1 multi-date carry", "carry", {
        "spot": 72, "discount": ".92", "delivery_price": 76,
        "events": [{"time": ".25", "discount": ".99", "income": "1.5", "cost": ".4"},
                   {"time": ".75", "discount": ".96", "income": 2, "cost": ".6"}]})
    rational(e1["prepaid_delivery"], "69.567", "E1 manuscript prepaid")
    rational(e1["fair_forward"], "69567/920", "E1 manuscript forward")
    rational(e1["terminal_excess_of_quoted_delivery"], "353/920", "E1 manuscript funded surplus")
    rational(e1["long_value"], "-.353", "E1 manuscript old value")
    # These are sign sanity checks; the full proof is an identity of tradable
    # cash portfolios and is audited in the written review, not proved by cases.
    for price1, price2 in ((79, 100), (100, 79)):
        rational(F("1.05")*((140-price1)-(140-price2)), F("1.05")*(price2-price1), "E2 exact cancellation sign")
    e3 = intervene("exercise 3 benchmark currency value", "fx", {
        "spot_domestic_per_foreign": ".8", "domestic_discount": ".97", "foreign_discount": ".95",
        "delivery_price": ".79", "foreign_notional": 500000})
    rational(e3["fair_domestic_per_foreign"], "76/97", "E3 manuscript fair quote")
    rational(e3["long_value_domestic"], -3150, "E3 manuscript value")
    sell_cost, buy_proceeds = F(".801")/F("1.04")*F("1.06"), F(".799")/F("1.07")*F("1.02")
    rational(sell_cost, "42453/52000", "E3 actual sell financing")
    rational(buy_proceeds, "40749/53500", "E3 actual reverse financing")
    require(F(".790") < sell_cost and F(".792") > buy_proceeds, "E3 neither trade profitable")
    with localcontext() as ctx:
        ctx.prec = 70
        shares = Decimal("-.08").exp()
        forward = Decimal(120)*shares/Decimal("-.02").exp()
        value = Decimal(120)*shares-Decimal(115)*Decimal("-.02").exp()
        require(abs(forward-Decimal("113.011744030")) < Decimal(".0000000005"), "E4 rounded quote")
        require(abs(value-Decimal("-1.948885864")) < Decimal(".0000000005"), "E4 rounded value")
        require(abs(shares*Decimal(".08").exp()-1) < Decimal("1e-65"), "E4 ODE accumulation")
    e5 = intervene("exercise 5 stochastic rate transfer", "tree", {
        "first_gross": "1.02", "probabilities": [".4", ".6"], "second_gross": ["1.25", ".95"], "terminal_spot": [160, 70]})
    for key, value in {"spot_price": "90640/969", "bond_price": "904/969", "forward_quote": "11330/113",
                       "futures_quote": 106, "futures_minus_forward": "648/113", "covariance_spot_discount": "-5184/969"}.items():
        rational(e5[key], value, "E5 manuscript "+key)
    equal(e5["funded_terminal_futures"], ["135/2", "-171/5"], "E5 funded terminal cash")
    e6 = intervene("exercise 6 short side funded calls", "margin", {
        "contracts": -2, "multiplier": 25, "quotes": [80, 84, 79, 83], "initial": 300,
        "maintenance": 200, "funding_gross": ["1.005", "1.01", "1.02"]})
    for key, value in {"total_variation": -150, "total_posted": 500, "terminal_release": 350,
                       "terminal_funding_debt": "516.6453", "funding_cost": "16.6453", "net_after_funding": "-166.6453"}.items():
        rational(e6[key], value, "E6 manuscript "+key)
    rational(450-300-F(e6["ledger"][0]["call"]), -50, "E6 first-call reserve shortfall")
    e7 = intervene("exercise 7 projected swap", "swap", {
        "notional": 2000000, "accruals": [".5", ".5"], "discounts": [".98", ".94"],
        "projected_rates": [".06", ".07"], "fixed_rate": ".065"})
    for key, value in {"annuity": ".96", "floating_pv": 124600, "fixed_pv": 124800,
                       "payer_fixed_value": -200, "par_fixed": "623/9600"}.items():
        rational(e7[key], value, "E7 manuscript "+key)
    rational(F(e7["single_curve_floating_pv"])-F(e7["fixed_pv"]), -4800, "E7 incorrect substituted projection")
    fixing_change = 2000000*F(".5")*F(".98")*(F(".08")-F(".06"))
    rational(F(e7["floating_pv"])+fixing_change, 144200, "E7 known first fixing PV")
    rational(F(e7["payer_fixed_value"])+fixing_change, 19400, "E7 known first fixing net")
    e8 = intervene("exercise 8 collateral and independent margin", "collateral", {
        "receipt": 103, "collateral_gross": "1.02", "segregated_initial": 20000,
        "funding_rate": ".05", "remuneration_rate": ".01", "year_fraction": ".5"})
    for key, value in {"fully_reusable_claim_value": "5150/51", "segregated_funding_repayment": 20500,
                       "segregated_margin_return": 20100, "segregated_net_cost": 400}.items():
        rational(e8[key], value, "E8 manuscript "+key)
    rational(F(e8["fully_reusable_claim_value"])*F("1.02"), 103, "E8 collateral repayment matches claim")
    for key, value in {"sale_receipt": 9400, "nominal_futures_receipt": 600, "terminal_local_basis": -2,
                       "cash_after_funding": 9850}.items():
        rational(base["basis"][key], value, "E9 cash "+key)
    optimum_units = F(200)*6/16
    rational(optimum_units/100, "3/4", "E9 optimal short contracts")
    for units, target in ((0, 360000), (75, 270000), (100, 280000), (200, 520000)):
        # Completed square exposes global nonnegative excess variance.
        rational(270000+16*(F(units)-optimum_units)**2, target, "E9 completed-square variance")
    rational(F(60)/F(".96"), "62.5", "retention forward")
    rational(60-61*F(".96"), "1.44", "retention old value")
    equal([-3*20, 5*20], [-60, 100], "retention dated variation")
    rational(F(".12")/F("2.4"), ".05", "retention swap par")
    rational(100000*(F(".12")-F(".045")*F("2.4")), 1200, "retention swap value")
    groups.append("all determinate exercise and retention values; 70-digit proportional-payout calculation; proof and critique separately reviewed")

    def reject(name, edit):
        nonlocal rejected
        data = deepcopy(raw)
        edit(data)
        try:
            model["run"](data)
        except ValueError:
            rejected += 1
        else:
            raise AssertionError("accepted invalid input: "+name)

    for section, field in (("carry", "spot"), ("fx", "foreign_notional"), ("tree", "first_gross"),
                           ("margin", "multiplier"), ("swap", "notional"), ("collateral", "receipt"), ("basis", "units")):
        for bad in (True, False, 1.0, float("nan"), float("inf"), "NaN", "Infinity", "1/0", "1/1000000000001", "1"*65):
            reject(section+" numeric contract", lambda d, s=section, f=field, b=bad: d[s].__setitem__(f, b))
    invalid = [
        ("unknown schema", lambda d: d.__setitem__("schema", "v10-c05-2")),
        ("nontext provenance", lambda d: d.__setitem__("provenance", False)),
        ("extra root", lambda d: d.__setitem__("unpriced", 1)),
        ("missing case", lambda d: d.pop("fx")),
        ("extra carry field", lambda d: d["carry"].__setitem__("fee", 1)),
        ("numerator precision", lambda d: d["carry"].__setitem__("spot", 10**25)),
        ("zero discount", lambda d: d["carry"].__setitem__("discount", 0)),
        ("discount above bound", lambda d: d["carry"].__setitem__("discount", "3.0001")),
        ("nonpositive prepaid", lambda d: d["carry"]["events"][0].__setitem__("income", 1000)),
        ("event at maturity", lambda d: d["carry"]["events"][0].__setitem__("time", 1)),
        ("duplicate event date", lambda d: d["carry"]["events"].append(deepcopy(d["carry"]["events"][0]))),
        ("too many events", lambda d: d["carry"].__setitem__("events", [d["carry"]["events"][0]]*25)),
        ("negative FX spot", lambda d: d["fx"].__setitem__("spot_domestic_per_foreign", -1)),
        ("negative FX delivery", lambda d: d["fx"].__setitem__("delivery_price", -1)),
        ("tree zero probability", lambda d: d["tree"].__setitem__("probabilities", [0, 1])),
        ("tree probability sum", lambda d: d["tree"].__setitem__("probabilities", [".5", ".49"])),
        ("tree empty vector", lambda d: d["tree"].__setitem__("probabilities", [])),
        ("tree oversized vector", lambda d: d["tree"].__setitem__("probabilities", ["1/25"]*25)),
        ("tree mismatch", lambda d: d["tree"].__setitem__("second_gross", [1])),
        ("tree gross below bound", lambda d: d["tree"].__setitem__("first_gross", ".099")),
        ("tree nonpositive spot", lambda d: d["tree"].__setitem__("terminal_spot", [0, 80])),
        ("margin noninteger contracts", lambda d: d["margin"].__setitem__("contracts", "1/2")),
        ("margin no position", lambda d: d["margin"].__setitem__("contracts", 0)),
        ("margin no interval", lambda d: d["margin"].__setitem__("quotes", [100])),
        ("margin funding mismatch", lambda d: d["margin"].__setitem__("funding_gross", [1])),
        ("margin zero maintenance", lambda d: d["margin"].__setitem__("maintenance", 0)),
        ("margin maintenance over initial", lambda d: d["margin"].__setitem__("maintenance", 401)),
        ("margin initial zero", lambda d: d["margin"].__setitem__("initial", 0)),
        ("swap zero accrual", lambda d: d["swap"].__setitem__("accruals", [0, ".5", 1])),
        ("swap nonpositive projected accumulation", lambda d: d["swap"].__setitem__("projected_rates", [-2, 0, 0])),
        ("swap dimension mismatch", lambda d: d["swap"].__setitem__("discounts", [1])),
        ("collateral gross outside bound", lambda d: d["collateral"].__setitem__("collateral_gross", 0)),
        ("collateral funding accumulation zero", lambda d: d["collateral"].update({"funding_rate": -1, "year_fraction": 1})),
        ("collateral remuneration accumulation negative", lambda d: d["collateral"].update({"remuneration_rate": -1, "year_fraction": 2})),
        ("collateral negative separate margin", lambda d: d["collateral"].__setitem__("segregated_initial", -1)),
        ("basis negative short count", lambda d: d["basis"].__setitem__("contracts", -1)),
        ("basis fractional short count", lambda d: d["basis"].__setitem__("contracts", "1/2")),
        ("basis no physical quantity", lambda d: d["basis"].__setitem__("units", 0)),
    ]
    for name, edit in invalid:
        reject(name, edit)
    groups.append("explicit malformed, precision, dimensional, signed-position, probability, and positive-accumulation domain rejections")

    manifest = json.loads((ASSETS/"v10-c05-manifest.json").read_text())
    files = {"v10-c05-"+suffix for suffix in ("inputs.json", "analysis.py", "output.json", "README.txt")}
    equal({entry["file"] for entry in manifest["files"]}, files, "four payload manifest scope")
    for entry in manifest["files"]:
        payload = (ASSETS/entry["file"]).read_bytes()
        equal(len(payload), entry["bytes"], "manifest size "+entry["file"])
        equal(sha256(payload).hexdigest(), entry["sha256"], "manifest hash "+entry["file"])
    with tempfile.TemporaryDirectory(prefix="v10-c05-peer-") as temporary:
        temp = Path(temporary)
        source, unrelated = temp/"source", temp/"unrelated"
        source.mkdir()
        unrelated.mkdir()
        for name in files | {"v10-c05-manifest.json"}:
            shutil.copyfile(ASSETS/name, source/name)
        alternate = deepcopy(raw)
        alternate["tree"].update({"second_gross": [1, "1.2"]})
        alternate["margin"].update({"contracts": -1, "quotes": [-100, -96, -102, -101]})
        (source/"altered.json").write_text(json.dumps(alternate))
        for flags in ([], ["-O"]):
            script = [sys.executable]+flags+[str(source/"v10-c05-analysis.py")]
            for filename, input_data in (("v10-c05-inputs.json", raw), ("altered.json", alternate)):
                command = script+["--input", str(source/filename)]
                proc = subprocess.run(command, cwd=unrelated, capture_output=True, text=True, check=True)
                equal(proc.stderr, "", "portable successful stderr")
                equal(json.loads(proc.stdout), oracle(input_data), "portable stdout independent result "+str(flags)+filename)
                destination = unrelated/"result.json"
                proc = subprocess.run(command+["--output", str(destination)], cwd=unrelated, capture_output=True, text=True, check=True)
                equal((proc.stdout, proc.stderr), ("", ""), "portable explicit output silence")
                equal(json.loads(destination.read_text()), oracle(input_data), "portable file independent result "+str(flags)+filename)
            for malformed in ('{"schema":"x","schema":"y"}', '{"x":NaN}', '{"x":Infinity}', '{"x":-Infinity}', '{'):
                invalid_path = source/"invalid.json"
                invalid_path.write_text(malformed)
                protected = unrelated/"protected.json"
                protected.write_text("retain existing destination")
                proc = subprocess.run(script+["--input", str(invalid_path), "--output", str(protected)],
                                      cwd=unrelated, capture_output=True, text=True)
                require(proc.returncode != 0 and proc.stderr, "malformed CLI must fail "+str(flags))
                equal(proc.stdout, "", "invalid CLI stdout")
                equal(protected.read_text(), "retain existing destination", "invalid input must not replace destination")
                rejected += 1
    groups.append("isolated five-file normal and optimized CLI with baseline and changed contracts; strict JSON failures preserve destinations")

    fragment = Fragment()
    body = (ROOT/AUTHOR_PATHS[0]).read_text()
    fragment.feed(body)
    fragment.close()
    require(not fragment.stack, "closed chapter fragment")
    equal(len(fragment.ids), len(set(fragment.ids)), "unique chapter anchors")
    equal((fragment.worked, fragment.exercises, fragment.solutions), (5, 10, 10), "graduate chapter package")
    require("teach-back" in fragment.ids and "Delayed retention" in body and "Model answer" in body, "answered teaching/retention")
    proposals = json.loads((ROOT/"content/reviews/v10-c05-sources.json").read_text())["proposals"]
    canonical = {entry["id"]: entry for entry in json.loads((ROOT/"content/sources.json").read_text())}
    equal(set(fragment.sources), {entry["id"] for entry in proposals}, "citation scope exactly three registered readings")
    for entry in proposals:
        equal(entry, canonical[entry["id"]], "registered source record "+entry["id"])
    author = json.loads((ROOT/AUTHOR_PATHS[-1]).read_text())
    equal({entry["path"] for entry in author["reviewed_hashes"]}, set(AUTHOR_PATHS[:-1]), "author eight nonself payloads")
    for entry in author["reviewed_hashes"]:
        payload = (ROOT/entry["path"]).read_bytes()
        equal((len(payload), sha256(payload).hexdigest()), (entry["bytes"], entry["sha256"]), "author frozen payload "+entry["path"])
    peer_path = ROOT/"content/reviews/v10-c05-peer.json"
    if peer_path.exists():
        peer = json.loads(peer_path.read_text())
        equal({entry["path"] for entry in peer["reviewed_hashes"]}, set(AUTHOR_PATHS), "peer all nine author payloads")
        for entry in peer["reviewed_hashes"]:
            payload = (ROOT/entry["path"]).read_bytes()
            equal((len(payload), sha256(payload).hexdigest()), (entry["bytes"], entry["sha256"]), "peer frozen payload "+entry["path"])
    equal(capture.getvalue(), "", "all successful API interventions remain quiet")
    groups.append("HTML package, source-record scope, four-file integrity, eight author hashes, and nine peer review bindings")
    result = {
        "chapter": "v10-c05", "status": "passed", "comparisons": comparisons,
        "count_definition": "Actual equality checks: independently reconstructed output fields, unchanged cases, exercise values, API/CLI results, and structure/integrity records. Unchanged-case and record comparisons count once each; require-style qualitative gates are not included.",
        "invalid_inputs_rejected": rejected, "financial_intervention_runs": len(intervention_names),
        "interventions": intervention_names, "worked_examples_reviewed": 5, "exercise_solutions_reviewed": 10,
        "groups": groups,
        "limits": "Separate machine-assisted peer review; numerical tests support implementation checks, not proofs or market authentication. Existing dated source body-verification records reused; no independent human certification or visual UI QA.",
    }
    json.dumps(result, allow_nan=False)
    return result


if __name__ == "__main__":
    print(json.dumps(check(), indent=2, allow_nan=False))
