"""Separate finite-contract review of Finance Core Form A; read-only stdlib.

No author code is imported. Independent witnesses include cash/inventory
recipients, a log-product certificate, bounded clearing iterates and atomic
simultaneous transfers. Quiet check() survives -O and an exact six-file copy.
"""
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from itertools import combinations
import json
from pathlib import Path
import re

FILES = (
    "content/cross-assessments/parts/finance-core-exam-a.html",
    "scripts/check_finance_core_exam_a.py",
    "content/reviews/finance-core-exam-a-author.json",
    "content/reviews/finance-core-exam-a-sources.json",
)
SELF = "scripts/check_finance_core_exam_a_peer.py"
REVIEW = "content/reviews/finance-core-exam-a-peer.json"
FROZEN = (
    (44122, "3b03154d13551f50dd0f9ebe7f3603f1effa0157c087b4216b790d8579a286c2"),
    (22041, "cf5d7065fbc7d95dd14aae18a36f9ab472406876d0fb4ae2ae4d33eef7d1b179"),
    (23086, "437bc867d22eff298bbd7a9d410c426b370c538f8024fbe22d1fe13e89517e83"),
    (17365, "f1b18a6448e394a9f98e4235cb1d2825c59d3333c3f6acdcb5fd059f402b5c5a"),
)
POINTS = ((6, 8, 6), (7, 8, 5), (8, 5, 7), (8, 6, 6), (6, 6, 8))
IDS = {f"finance-core-a-{i}{s}": p for i, row in enumerate(POINTS, 1) for s, p in zip("abc", row)}


class Audit:
    def __init__(self):
        self.comparisons = self.rejections = self.cash_rows = self.clearing_cases = 0
        self.interventions = []

    def eq(self, actual, expected, label):
        self.comparisons += 1
        if actual != expected:
            raise ValueError(f"{label}: {actual!r} != {expected!r}")

    def yes(self, condition, label):
        self.eq(bool(condition), True, label)

    def reject(self, operation, label):
        try:
            operation()
        except ValueError:
            self.rejections += 1
        else:
            raise ValueError(label + ": invalid oracle/evidence domain accepted")


def exact(value):
    if isinstance(value, bool) or not isinstance(value, (int, F)):
        raise ValueError("exact finite integer or rational required")
    return F(value)


def solve(first, second):
    a, b, c = map(exact, first)
    d, e, f = map(exact, second)
    det = a * e - b * d
    if not det:
        raise ValueError("singular payoff system")
    return (c * e - b * f) / det, (a * f - c * d) / det


class Cash:
    def __init__(self, audit, balances):
        self.audit = audit
        self.balances = {k: exact(v) for k, v in balances.items()}
        if any(v < 0 for v in self.balances.values()):
            raise ValueError("negative initial usable cash")
        self.total = sum(self.balances.values())

    def batch(self, transfers):
        # A batch permits incoming money to fund outgoing obligations only
        # when the caller explicitly models simultaneous-clearing rights.
        delta = dict.fromkeys(self.balances, F(0))
        for payer, receiver, amount in transfers:
            amount = exact(amount)
            if amount < 0 or payer == receiver:
                raise ValueError("invalid transfer")
            delta[payer] -= amount
            delta[receiver] += amount
        new = {k: self.balances[k] + v for k, v in delta.items()}
        if any(v < 0 for v in new.values()):
            raise ValueError("cash delivery is unfunded")
        self.balances = new
        self.audit.cash_rows += len(transfers)
        self.audit.eq(sum(new.values()), self.total, "all-recipient cash conserved")

    def pay(self, payer, receiver, amount):
        self.batch([(payer, receiver, amount)])


def clearing_brackets(cash_a, cash_b):
    """Forty exact monotone contractions from bottom and top of the box."""
    cash_a, cash_b = exact(cash_a), exact(cash_b)
    if min(cash_a, cash_b) < 0:
        raise ValueError("external cash cannot be negative")
    def update(p):
        return min(F(12), cash_a + p[1] / 2), min(F(16), cash_b + p[0] / 4)
    lower, upper = (F(0), F(0)), (F(12), F(16))
    for _ in range(40):
        lower, upper = update(lower), update(upper)
    return lower, upper


def check_clearing(audit, cash_a, cash_b, candidate):
    low, high = clearing_brackets(cash_a, cash_b)
    audit.yes(all(l <= p <= u for l, p, u in zip(low, candidate, high)), "exact answer within independent monotone brackets")
    audit.yes(max(u - l for l, u in zip(low, high)) <= F(16, 2 ** 40), "sup-norm contraction error bound")
    audit.eq(candidate, (min(F(12), cash_a + candidate[1] / 2), min(F(16), cash_b + candidate[0] / 4)), "candidate exactly settles original obligations")
    audit.clearing_cases += 1


def geometric_payments(cash_a, cash_b):
    # An A->B->A circulation transmits (1/4)*(1/2)=1/8 of its origin.
    # Eight transmission rounds plus their exact tail give the complete
    # uncapped flow; the caller separately certifies that caps are slack.
    cash_a, cash_b = exact(cash_a), exact(cash_b)
    ratio = F(1, 8)
    propagation = sum(ratio ** n for n in range(8)) + ratio ** 8 / (1 - ratio)
    return (cash_a + cash_b / 2) * propagation, (cash_b + cash_a / 4) * propagation


def one_period_log_slope(weight, probability):
    weight, probability = exact(weight), exact(probability)
    if not 0 <= weight <= 1 or not 0 < probability < 1:
        raise ValueError("long-only weight and interior physical probability required")
    up, down = 1 + F(4, 5) * weight, 1 - F(2, 5) * weight
    return probability * F(4, 5) / up - (1 - probability) * F(2, 5) / down


def accounts(a):
    # Receipt resources represent the stated period payments, not a claim
    # about the customers' full balance sheets.
    cash = Cash(a, {"company": 15, "customers": 162, "suppliers": 0, "employees": 0, "debt_holder": 0, "owners": 0})
    for payer, recipient, amount in (("customers", "company", 150), ("customers", "company", 12), ("company", "suppliers", 95), ("company", "employees", 30), ("company", "debt_holder", 4), ("company", "debt_holder", 5), ("company", "owners", 6)):
        cash.pay(payer, recipient, amount)
    ar, inventory, ap, advances = 20 + 160 - 150, 30 + 100 - 90 - 6, 18 + 100 - 95, 10 + 12 - 8
    income = 160 + 8 - sum((90, 6, 30, 12, 4))
    a.eq((ar, inventory, ap, advances), (30, 34, 23, 14), "1a operating claim roll-forwards")
    a.eq(income, 26, "1b earned revenue and actual expenses")
    a.eq(cash.balances, {"company": 37, "customers": 0, "suppliers": 95, "employees": 30, "debt_holder": 9, "owners": 6}, "1b all stated cash recipients")
    cfo = cash.balances["company"] - 15 + 5 + 6
    a.eq((cfo, 150 + 12 - 95 - 30 - 4), (33, 33), "1b classified and direct operating cash")
    a.eq(income + 12 + 6 - (ar - 20) - (inventory + 6 - 30) + (ap - 18) + (advances - 10), cfo, "1b gross inventory bridge")
    a.eq(income + 12 - (ar - 20) - (inventory - 30) + (ap - 18) + (advances - 10), cfo, "1b net inventory bridge")
    ppe, debt, equity = 80 - 12, 40 - 5, 77 + income - 6
    a.eq((ppe, debt, equity), (68, 35, 97), "1b nonoperating balances")
    a.eq((37 + ar + inventory + ppe, ap + advances + debt, equity), (169, 72, 97), "1b full balance sheet")
    a.eq(169 - 72 - 97, 0, "1b accounting identity")
    a.eq((income + 12 + 6, equity + 12 + 6), (44, 115), "1c misstated profit and equity")
    a.eq((inventory + 6, advances - 12), (40, 2), "1c matching false asset and liability amounts")
    a.eq(37 + ar + 40 + ppe - (ap + 2 + debt), 115, "1c false statements can still balance")
    # Delivery of only four of the existing advance changes income/liability,
    # holding the problem's stated consumed-goods total and all receipts fixed.
    a.eq((160 + 4 - 142, 10 + 12 - 4, cfo), (22, 18, 33), "1 changed earning event without new receipt")
    a.interventions.append("Reduce earned advance release from eight to four while keeping stated goods cost and cash fixed: income falls four and liability rises four.")
    a.eq((income + 6, inventory + 6, cfo, cash.balances["company"]), (32, 40, 33, 37), "1 no write-down changes values but not cash")
    a.interventions.append("Remove the inventory write-down: book inventory/income rise six but neither CFO nor usable cash changes.")


def investment(a):
    tax1, tax2 = F(1, 4) * (100 - 60 - 30), F(1, 4) * (120 - 70 - 30)
    # Direct dated operating payments, separate from the accounting bridge.
    cf1, cf2 = 100 - 60 - tax1 - 5, 120 - 70 - tax2 + 15
    value = F(9, 10) * cf1 + F(4, 5) * cf2
    a.eq((tax1, tax2, cf1, cf2, value, value - 70), (F(5, 2), 5, F(65, 2), 60, F(309, 4), F(29, 4)), "2a dated FCFF and value")
    a.eq(10 + 5 - 15, 0, "2a complete working-capital liquidation")
    a.eq(60 - 30 - 30, 0, "2a no residual equipment value")
    # Distinct investor, company, vendor and supplier wallets, all at date zero.
    cash = Cash(a, {"investor": 60, "company": 20, "vendor": 0, "inventory_supplier": 0})
    cash.pay("investor", "company", 50)
    cash.pay("company", "vendor", 60)
    cash.pay("company", "inventory_supplier", 10)
    a.eq(cash.balances, {"investor": 10, "company": 0, "vendor": 60, "inventory_supplier": 10}, "2b investment recipients")
    rejection, gross_assets = F(100 + 20 - 30), 100 + value
    post = gross_assets - 30
    # Fair subscription price z solves 100*z+50=post. Ownership follows
    # from the actual number bought at z, rather than assuming a fraction.
    price = (post - 50) / 100
    new_shares = 50 / price
    new_fraction = new_shares / (100 + new_shares)
    a.eq((rejection, gross_assets, post, price, new_shares, new_fraction), (90, F(709, 4), F(589, 4), F(389, 400), F(20000, 389), F(200, 589)), "2b fair share-count equation")
    a.eq(((1 - new_fraction) * post, new_fraction * post), (F(389, 4), 50), "2b owner allocations")
    a.eq((1 - new_fraction) * post - rejection, value - 70, "2b value gain counted once")
    a.eq(30 + 50 + F(389, 4), gross_assets, "2b all financial claims exhaust assets")
    stale_count = 50 / F(9, 10)
    stale_fraction = stale_count / (100 + stale_count)
    new_value, old_value = stale_fraction * post, (1 - stale_fraction) * post
    a.eq((stale_count, stale_fraction, new_value, old_value), (F(500, 9), F(5, 14), F(2945, 56), F(5301, 56)), "2c stale share-count allocation")
    a.eq((new_value - 50, old_value - rejection), (F(145, 56), F(261, 56)), "2c recipient gains")
    a.eq((new_value - 50) + (old_value - rejection), value - 70, "2c no second project NPV")
    # A fee paid to an external provider at inception lowers total value to
    # owners. This actual extra cash cannot be silently financed by the same70.
    extra_cost = F(29, 4)
    a.eq(value - 70 - extra_cost, 0, "2 additional funded outlay consumes exactly the NPV")
    a.yes(cash.balances["investor"] >= extra_cost, "2 investor's retained ten can actually fund the changed fee")
    cash.pay("investor", "vendor", extra_cost)
    a.eq(cash.balances["investor"], F(11, 4), "2 fee's cash source identified")
    a.interventions.append("An extra inception outlay of 29/4, explicitly paid from the investor's retained ten, exhausts the project surplus; value and resources change together.")


def allocation(a):
    w = F(5, 8)
    # Equal probabilities make J(w)=log(product)/2. Its polynomial maximum
    # is global since log is strictly increasing and wealth is positive.
    product_coefficients = (F(1), F(2, 5), -F(8, 25))
    square_coefficients = (F(9, 8) - F(8, 25) * w * w, 2 * F(8, 25) * w, -F(8, 25))
    a.eq(product_coefficients, square_coefficients, "3a global product identity 9/8-(8/25)(w-5/8)^2")
    a.eq(1 - F(2, 5), F(3, 5), "3a smallest wealth factor on whole interval")
    a.eq(one_period_log_slope(w, F(1, 2)), 0, "3a independent derivative root")
    a.yes(0 < w < 1, "3a root strictly inside feasible interval")
    a.eq((100 * w, 100 * (1 - w), 10 * w), (F(125, 2), F(75, 2), F(25, 4)), "3a actual money and units")
    terminal = (18 * 10 * w + 100 * (1 - w), 6 * 10 * w + 100 * (1 - w))
    a.eq(terminal, (150, 75), "3a terminal wealth")
    a.eq(sum(terminal) / 2, F(225, 2), "3a physical expected wealth")
    qu, qd = solve((1, 1, 1), (18, 6, 10))
    a.eq((qu, qd, qu * terminal[0] + qd * terminal[1]), (F(1, 3), F(2, 3), 100), "3b independent traded equations")
    a.eq(100 - terminal[1], 25, "3a positive mean is compatible with a loss")
    for p, candidate in ((F(1, 3), F(0)), (F(2, 5), F(1, 4)), (F(3, 5), F(1))):
        a.eq(one_period_log_slope(candidate, p), 0, "3 belief threshold or interior certificate")
        a.eq(18 * qu + 6 * qd, 10, "3 same quoted price across belief changes")
    a.interventions.append("Physical probabilities 1/3, 2/5 and 3/5 move the unique log optimum to zero, one-quarter and one, with traded Arrow prices unchanged.")
    r1, r2 = F(120, 100) - 1, F(180, 120 + 80) - 1
    a.eq((r1, r2, (1 + r1) * (1 + r2) - 1), (F(1, 5), -F(1, 10), F(2, 25)), "3c cash-flow-delimited returns")
    a.eq((20 * 5, 20 * (9 - 5), -20 * 9), (100, 80, -180), "3c exact coefficients of admissible IRR polynomial")
    a.eq(100 + 80 - 180, 0, "3c positive gross root one")
    a.yes(-F(9, 5) < 0, "3c other root outside positive gross domain")
    a.eq(100 * (1 + r1) + 80, 200, "3c funded contribution adds to second-period capital")
    a.eq(F(180, 100) - 1, F(4, 5), "3c misleading raw account growth")
    # Keep the same returns but halve the actual contribution; terminal wealth
    # is recomputed, not held fixed despite the changed funded path.
    revised_terminal = (120 + 40) * F(9, 10)
    a.eq(revised_terminal, 144, "3c changed contribution changes final wealth")
    a.yes(100 + 40 - revised_terminal < 0 and 100 * F(51, 50) ** 2 + 40 * F(51, 50) - revised_terminal > 0, "3c revised IRR lies between zero and two percent")
    a.eq((1 + r1) * F(9, 10) - 1, F(2, 25), "3c same time-weighted return despite changed IRR")
    a.interventions.append("Halve the year-one contribution to forty and recompute final wealth as 144: the time-weighted return stays eight percent while annual IRR becomes positive.")


def hedge_path(a, path, changed=False, lender_endowment=60):
    """Actual cash/inventory path; interest accrual is only an owed amount."""
    gross = F(11, 10)
    du, bu = solve((144, gross, 30), (96, gross, 0))
    vu = 120 * du + bu
    d0, b0 = solve((120, gross, vu), (80, gross, 0))
    premium = 100 * d0 + b0
    cash = Cash(a, {"customer": 20, "lender": lender_endowment, "counterparty": 200, "trust": 0, "investor": 5 if changed else 0})
    inventory = {"counterparty": F(2), "trust": F(0)}
    cash.pay("customer", "trust", premium)
    cash.pay("lender", "trust", -b0)
    cash.pay("trust", "counterparty", 100 * d0)
    inventory["counterparty"] -= d0
    inventory["trust"] += d0
    a.eq(cash.balances["trust"], 0, "4 inception premium/advance fully spent")
    a.yes(-b0 <= F(3, 4) * 100 * d0, "4 inception single-stock collateral")
    grown = -b0 * gross
    if path[0] == "D":
        cash.pay("counterparty", "trust", 80 * d0)
        inventory["counterparty"] += d0
        inventory["trust"] -= d0
        cash.pay("trust", "lender", grown)
        a.eq(cash.balances["trust"], 0, "4 first down node closes hedge")
        a.eq(cash.balances["lender"], lender_endowment + F(450, 121), "4 down-node bank interest actually received")
        payoff, residual = F(0), F(0)
    else:
        debt = F(50) if changed else -bu
        injection = (-bu) - debt
        added_loan = debt - grown
        if changed:
            cash.pay("investor", "trust", injection)
        cash.pay("lender", "trust", added_loan)
        cash.pay("trust", "counterparty", 120 * (du - d0))
        inventory["counterparty"] -= du - d0
        inventory["trust"] += du - d0
        a.eq(inventory["trust"], F(5, 8), "4 up-node titled shares")
        a.eq(cash.balances["trust"], 0, "4 up rebalance funded exactly")
        a.eq(cash.balances["lender"], F(1660, 121) if changed else F(1110, 121), "4 actual lender reserve excludes interest accrual")
        a.yes(debt <= (F(2, 3) if changed else F(3, 4)) * 120 * du, "4 post-rebalance single-stock collateral")
        stock = 144 if path[1] == "U" else 96
        payoff = F(30 if path == "UU" else 0)
        cash.pay("counterparty", "trust", stock * du)
        inventory["counterparty"] += du
        inventory["trust"] -= du
        cash.pay("trust", "lender", debt * gross)
        cash.pay("trust", "customer", payoff)
        residual = cash.balances["trust"]
        if changed:
            cash.pay("trust", "investor", residual)
            a.eq((residual, residual / gross), (5, F(50, 11)), "4 sole new-equity claim and fair value")
        else:
            a.eq(residual, 0, "4 original hedge no unassigned terminal surplus")
    a.eq(inventory, {"counterparty": F(2), "trust": F(0)}, "4 final stock title reconciles")
    a.eq(cash.balances["trust"], 0, "4 all trust cash allocated once")
    a.yes(cash.balances["counterparty"] >= 0, "4 underlying counterparties actually funded")
    return premium, payoff, residual


def derivatives(a):
    gross = F(11, 10)
    # Price Arrow payoffs independently of the portfolio equations.
    state_u, state_d = solve((1, 1, 1 / gross), (120, 80, 100))
    q = gross * state_u
    path_prices = (state_u ** 2, state_u * state_d, state_d * state_u, state_d ** 2)
    a.eq((q, sum(path_prices), 30 * path_prices[0]), (F(3, 4), F(100, 121), F(3375, 242)), "4a positive path-state prices")
    a.yes(min(path_prices) > 0, "4a all priced paths positive")
    du, bu = solve((144, gross, 30), (96, gross, 0))
    dd, bd = solve((96, gross, 0), (64, gross, 0))
    vu, vd = 120 * du + bu, 80 * dd + bd
    d0, b0 = solve((120, gross, vu), (80, gross, vd))
    a.eq((du, bu, vu, dd, bd, vd), (F(5, 8), -F(600, 11), F(225, 11), 0, 0, 0), "4a both date-one portfolios")
    a.eq((d0, b0, 100 * d0 + b0), (F(45, 88), -F(4500, 121), F(3375, 242)), "4a initial portfolio")
    for path, payoff in (("UU", 30), ("UD", 0), ("DU", 0), ("DD", 0)):
        a.eq(hedge_path(a, path), (F(3375, 242), payoff, 0), "4 original funded path " + path)
    added = du - d0
    a.eq((added, 120 * added, -b0 * gross, -bu), (F(5, 44), F(150, 11), F(450, 11), F(600, 11)), "4b up-node increments")
    ratios = (-b0 / (100 * d0), -bu / (120 * du))
    a.eq(ratios, (F(8, 11), F(8, 11)), "4b collateral ratio at each nonzero monitoring date")
    a.eq(1 - max(ratios), F(3, 11), "4b largest allowed haircut")
    a.yes(all(r <= 1 - F(1, 4) for r in ratios), "4b original quarter haircut")
    a.yes(any(r > 1 - (F(3, 11) + F(1, 1000)) for r in ratios), "4b slightly tighter haircut fails")
    a.interventions.append("Increase the monitored haircut just above 3/11: the original hedge's payoff still matches but its original debt/share positions are inadmissible.")
    for path in ("UU", "UD"):
        a.eq(hedge_path(a, path, changed=True)[2], 5, "4c both financed residual states")
    injection = -bu - 50
    a.eq((injection, 50 - (-b0 * gross), gross * 50), (F(50, 11), F(100, 11), 55), "4c equity and bank cash versus later repayment")
    a.yes(-bu - (injection - F(1, 1000)) > 50, "4c smaller cash injection violates cap")
    a.eq(injection + (50 - (-b0 * gross)), 120 * added, "4c exact equity/debt purchase funding")
    a.interventions.append("An up-node one-third haircut requires delivered equity 50/11 with the entire five-unit terminal residual; a smaller or unexecuted contribution leaves the financing gap.")
    a.eq((-b0) + 120 * added, F(6150, 121), "4 minimum lender endowment along an up path")
    a.reject(lambda: hedge_path(a, "UU", lender_endowment=50), "4 reduced lender reserve blocks later advance")
    a.interventions.append("Reduce the lender's separate reserve from sixty to fifty: inception still funds, but the required up-node second advance cannot be executed.")


def network(a):
    original = geometric_payments(F(2), F(3))
    a.eq(original, (4, 4), "5a payment propagation including all internal rounds")
    check_clearing(a, F(2), F(3), original)
    pa, pb = original
    a.eq((pa / 4, 3 * pa / 4, pb / 2, pb / 2), (1, 3, 2, 2), "5a each actual recipient")
    a.eq((12 - pa, 16 - pb, (12 - pa) / 4, 3 * (12 - pa) / 4, (16 - pb) / 2), (8, 12, 2, 6, 6), "5a retained nominal creditor-specific claims")
    a.eq(3 * pa / 4 + pb / 2, 2 + 3, "5a outside receipts cancel internal circulation")
    # The affine grant solution is valid on the whole simplex: the maximum
    # of either linear coordinate is at one of its three vertices.
    vertices = ((F(0), F(0)), (F(6), F(0)), (F(0), F(6)))
    values = [geometric_payments(2 + x, 3 + y) for x, y in vertices]
    a.eq((max(p[0] for p in values), max(p[1] for p in values)), (F(76, 7), F(76, 7)), "5c full-domain coordinate maxima")
    a.yes(F(76, 7) < 12 and F(76, 7) < 16, "5c original grant domain is entirely uncapped")
    for (x, y), payment in zip(vertices, values):
        check_clearing(a, 2 + x, 3 + y, payment)
    # Marginal delivery to T from each grant origin follows its path into A,
    # then exits with fraction 3/4 after any number of 1/8 circulation cycles.
    gain_a = F(3, 4) / (1 - F(1, 8))
    gain_b = F(1, 2) * gain_a
    a.eq((gain_a, gain_b), (F(6, 7), F(3, 7)), "5c recipient delivery per donor unit")
    need = 8 - (2 + 3 * pa / 4)
    a.eq(need / max(gain_a, gain_b), F(7, 2), "5c global donation lower bound by best recipient conversion")
    # Enumerate only intersections defining this two-variable feasible set.
    bounds = ((-1, 0, 0), (0, -1, 0), (1, 1, 6), (-gain_a, -gain_b, -need))
    feasible = set()
    for first, second in combinations(bounds, 2):
        try:
            x, y = solve(first, second)
        except ValueError:
            continue
        if all(c * x + d * y <= e for c, d, e in bounds):
            feasible.add((x, y))
    a.eq(feasible, {(F(7, 2), F(0)), (F(6), F(0)), (F(1), F(5))}, "5c complete feasible grant polygon")
    a.eq(min(feasible, key=lambda xy: sum(xy)), (F(7, 2), F(0)), "5c attained unique upstream optimum")
    # Execute original, upstream and direct policies. Only the four network
    # transfers use simultaneous net funding; donor and deposit payments are
    # actual sequential cash events before/after that explicitly allowed batch.
    outcomes = {}
    for label, x, y, direct in (("none", F(0), F(0), F(0)), ("upstream", F(7, 2), F(0), F(0)), ("direct", F(0), F(0), F(3))):
        cash = Cash(a, {"A": 2, "B": 3, "T": 2, "other_creditors": 0, "depositor": 0, "donor": 6})
        for receiver, grant in (("A", x), ("B", y), ("T", direct)):
            if grant:
                cash.pay("donor", receiver, grant)
        payment_a, payment_b = geometric_payments(2 + x, 3 + y)
        check_clearing(a, 2 + x, 3 + y, (payment_a, payment_b))
        cash.batch([("A", "B", payment_a / 4), ("A", "T", 3 * payment_a / 4), ("B", "A", payment_b / 2), ("B", "other_creditors", payment_b / 2)])
        a.eq((cash.balances["A"], cash.balances["B"]), (0, 0), "5 batch exhausts available debtor resources in uncapped region")
        available = cash.balances["T"]
        paid = min(F(8), available)
        cash.pay("T", "depositor", paid)
        deposits = 20 - paid
        equity = available + 18 - 20
        a.eq(cash.balances["T"] + 18, deposits + equity, "5 post-payment bank identity")
        a.eq(cash.balances["depositor"] + cash.balances["other_creditors"] + cash.balances["donor"] + cash.balances["T"], 13, "5 consolidated recipient budgets including unused donor cash")
        outcomes[label] = (payment_a, payment_b, available, paid, 8 - paid, deposits, equity, 9 - 3 * payment_a / 4)
    a.eq(outcomes["none"], (4, 4, 5, 5, 3, 15, 3, 6), "5b original loss, capital, due payment and surviving face")
    a.eq(outcomes["upstream"], (8, 5, 8, 8, 0, 12, 6, 3), "5c upstream all claim/cash allocations")
    a.eq(outcomes["direct"], (4, 4, 8, 8, 0, 12, 6, 6), "5c direct all claim/cash allocations")
    a.eq(F(7, 2) - 3, F(5, 2) - 2, "5c extra donor cost exactly equals other-creditor gain")
    a.eq(11 - 2 - 6, 3, "5b losses recognized once")
    a.yes(2 + 3 + (3 - F(1, 1000)) < 8, "5c smaller direct grant fails")
    a.yes(2 + 3 + gain_a * (F(7, 2) - F(1, 1000)) < 8, "5c smaller upstream cost cannot attain target")
    a.interventions.append("Compare original, minimum upstream and minimum direct grants, retaining all nominal claims and unused donor cash; the extra upstream half-unit reaches other creditors.")
    shifted = geometric_payments(F(2 + 3), F(3) + F(1, 2))
    check_clearing(a, F(5), F(7, 2), shifted)
    a.yes(2 + 3 * shifted[0] / 4 < 8, "5 same donor outlay redirected partly to B misses T's target")
    a.interventions.append("Redirect half of the minimal upstream outlay from A to B: total donor cash is unchanged but T misses its deadline.")
    # Explicitly enlarge the donor domain only for this counterfactual. Caps
    # now bind and cash can remain with A, unlike the original <=6 proof.
    check_clearing(a, F(10), F(3), (F(12), F(6)))
    a.eq(10 + F(6, 2) - 12, 1, "5 expanded-grant capped case retains debtor cash")
    a.eq(F(3, 4) * 12 + F(1, 2) * 6 + 1, 5 + 8, "5 external budget includes retained cash beyond original domain")
    a.interventions.append("Expand the donor budget and grant eight to A: A hits its face cap and retains one, so the original uncapped formulas cannot be extrapolated.")


def strict(text):
    def pairs(items):
        out = {}
        for key, value in items:
            if key in out:
                raise ValueError("duplicate evidence key")
            out[key] = value
        return out
    def bad(token):
        raise ValueError("nonfinite evidence constant " + token)
    return json.loads(text, object_pairs_hook=pairs, parse_constant=bad)


class Page(HTMLParser):
    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.ids, self.links, self.citations = [], set(), [], set()
        self.prompts, self.answers, self.domains = {}, {}, {}
        self.active, self.depth = None, None
        self.text, self.h1 = [], 0

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if len(attrs) != len(attributes):
            raise ValueError("duplicate attribute")
        if "id" in attrs:
            if attrs["id"] in self.ids:
                raise ValueError("duplicate HTML ID")
            self.ids.add(attrs["id"])
        if tag == "h1":
            self.h1 += 1
        if tag == "a":
            self.links.append(attrs.get("href", ""))
        if "data-source" in attrs:
            self.citations.add(attrs["data-source"])
        if tag == "tr" and "data-domain" in attrs:
            key = attrs["data-domain"]
            if key in self.domains:
                raise ValueError("duplicate domain score")
            self.domains[key] = int(attrs["data-points"])
        if tag == "li" and ("data-points" in attrs or "data-solution-for" in attrs):
            if self.active is not None:
                raise ValueError("nested scored item")
            if "data-points" in attrs:
                key = attrs.get("id")
                if not key or key in self.prompts:
                    raise ValueError("missing or duplicate prompt ID")
                self.prompts[key] = {"points": int(attrs["data-points"]), "text": []}
                self.active = self.prompts[key]["text"]
            else:
                key = attrs["data-solution-for"]
                if key in self.answers:
                    raise ValueError("duplicate answer")
                self.answers[key] = []
                self.active = self.answers[key]
            self.depth = len(self.stack)
        if tag not in self.VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if not self.stack or self.stack.pop() != tag:
            raise ValueError("unbalanced explicit HTML tag " + tag)
        if self.active is not None and len(self.stack) == self.depth:
            self.active, self.depth = None, None

    def handle_data(self, data):
        self.text.append(data)
        if self.active is not None:
            self.active.append(data)


def compact(text):
    return re.sub(r"\s+", "", text).replace("−", "-").replace("–", "-")


def manuscript(a, root):
    p = Page()
    p.feed((root / FILES[0]).read_text(encoding="utf-8"))
    p.close()
    a.eq(p.stack, [], "balanced author fragment")
    a.eq(p.h1, 0, "form does not duplicate assembly heading")
    a.eq({k: v["points"] for k, v in p.prompts.items()}, IDS, "fifteen exact scored prompt IDs")
    a.eq(set(p.answers), set(IDS), "one full solution for each exact prompt")
    a.eq(sum(x["points"] for x in p.prompts.values()), 100, "total points")
    a.eq(p.domains, {"D" + str(i): 20 for i in range(1, 6)}, "five domains")
    a.yes(all(x in {"form-a", "solutions-a"} or x.startswith("finance-core-a-") for x in p.ids), "owned anchor namespace")
    words = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8}
    for key, points in IDS.items():
        answer = re.sub(r"\s+", " ", "".join(p.answers[key]))
        rubric = re.search(r"(Five|Six|Seven|Eight) points:\s*([^.]+)\.", answer)
        a.yes(rubric is not None, key + " explicit rubric")
        a.eq(words[rubric.group(1).lower()], points, key + " rubric heading")
        a.eq(sum(words[x] for x in re.findall(r"\b(one|two|three|four)\s*(?:;|$)", rubric.group(2))), points, key + " rubric allocations sum")
        a.yes(len(answer) > 400 and len("".join(p.prompts[key]["text"])) > 150, key + " complete response and prompt")
    anchors = {
        "1a": ("receivables 30", "inventory 34", "payables 23", "advances 14", "credits the customer contract liability 12"),
        "1b": ("Income 26", "cash 33", "closing cash 37", "PPE is 80−12=68", "debt is 40−5=35", "77+26−6=97", "169=72+97", "omit the extra six add-back"),
        "1c": ("by 18", "44 rather than 26", "115 rather than 97", "CFO remains 33", "delivery/acceptance", "item-level inventory"),
        "2a": ("65/2", "60 at date 2", "309/4", "29/4", "no remaining equipment value"),
        "2b": ("200/589", "389/4", "589/4", "20000/389", "709/4", "investor retains ten"),
        "2c": ("500/9", "5/14", "2945/56", "5301/56", "145/56", "261/56", "389/400"),
        "3a": ("w=5/8", "125/2", "75/2", "25/4", "150 or 75", "225/2", "strict concavity"),
        "3b": ("1/3", "2/3", "price is 100", "112.5", "physical beliefs"),
        "3c": ("8%", "IRR is zero", "100g²+80g−180=0", "20(g−1)(5g+9)", "untouched evaluation period"),
        "4a": ("45/88", "−4500/121", "3375/242", "q=3/4", "5/8", "−600/11", "225/11", "DU and DD"),
        "4b": ("5/44", "150/11", "450/11", "600/11", "1110/121", "8/11", "h≤3/11", "claim, not a receipt"),
        "4c": ("50/11", "100/11", "debt is 50", "date 2 is 55", "five for the new equity investor", "not also an old holder's profit"),
        "5a": ("pA=pB=4", "M≤M/2", "T receives (3/4)4=3", "receive (1/2)4=2", "unpaid face eight", "unpaid face 12"),
        "5b": ("equity three", "20, giving equity three", "deposits still owed are 15", "nominal A claim still unpaid is six", "double count"),
        "5c": ("7/2", "76/7", "2x+y≥7", "17/2", "pA=8", "pB=5", "direct gift of three", "deposits 12 and equity six", "actual authority"),
    }
    anchor_count = 0
    for suffix, texts in anchors.items():
        answer = compact("".join(p.answers["finance-core-a-" + suffix]))
        for token in texts:
            a.yes(compact(token) in answer, suffix + " printed/conceptual anchor " + token)
            anchor_count += 1
    for suffix, exact_value, literal, places in (("2b", F(20000, 389), "51.414", 3), ("2c", F(2945, 56), "52.589286", 6), ("2c", F(5301, 56), "94.660714", 6), ("4a", F(3375, 242), "13.946281", 6)):
        a.yes("approximately " + literal in "".join(p.answers["finance-core-a-" + suffix]), "labeled approximate value")
        a.yes(abs(F(literal) - exact_value) <= F(1, 2 * 10 ** places), "correct half-last-place rounding")
    full = re.sub(r"\s+", " ", "".join(p.text))
    for clause in ("300 minutes", "nonprogrammable calculator", "no notes, code, internet or solutions", "85/100 overall and 15/20", "uncalibrated planning estimate", "each restates its own complete information", "without repeated deductions", "No broader welfare ordering is stipulated"):
        a.yes(clause in full, "administration and independent-case scope: " + clause)
    sources = strict((root / FILES[3]).read_text(encoding="utf-8"))
    a.eq(sources["proposals"], [], "no new source proposal")
    a.eq(p.citations, {x["id"] for x in sources["reuse"]}, "all six source scopes cited")
    a.eq(len(sources["reuse"]), 6, "inherited primary scopes")
    routes = sources["chapter_method_routes"]
    a.eq(len(routes), 25, "twenty-five sampled chapter routes")
    a.eq({r["domain"] for r in routes}, set(p.domains), "methods span all five finance domains")
    for row in routes:
        a.eq((row["status"], row["reader_url"]), ("accepted", row["canonical_chapter_id"] + ".html"), "source route spelling/status")
    allowed = {r["reader_url"] for r in routes} | {"sources.html#" + r["id"] for r in sources["reuse"]}
    a.eq(set(p.links), allowed, "exact flat chapter links and scoped source anchors")
    a.yes(all(r["url"].startswith("https://") and r["scope"] and r["evidence_record"] and "No fresh" in r["retrieval_status"] for r in sources["reuse"]), "honest inherited retrieval scope")
    return anchor_count


def bindings(a, root):
    def fingerprint(path):
        data = (root / path).read_bytes()
        return len(data), sha256(data).hexdigest()
    for path, frozen in zip(FILES, FROZEN):
        a.eq(fingerprint(path), frozen, "frozen author file " + path)
    author = strict((root / FILES[2]).read_text(encoding="utf-8"))
    a.eq({r["path"] for r in author["reviewed_hashes"]}, set(FILES) - {FILES[2]}, "three nonself author bindings")
    for row in author["reviewed_hashes"]:
        a.eq(fingerprint(row["path"]), (row["bytes"], row["sha256"]), "author nonself payload " + row["path"])
    peer = strict((root / REVIEW).read_text(encoding="utf-8"))
    rows = peer["reviewed_hashes"]
    a.eq(len(rows), 5, "five peer bindings without review self hash")
    a.eq({r["path"] for r in rows}, set(FILES) | {SELF}, "exact author-plus-peer-checker scope")
    for row in rows:
        a.eq(fingerprint(row["path"]), (row["bytes"], row["sha256"]), "peer bound payload " + row["path"])
    a.eq({r["prompt"] for r in peer["prompt_solution_audit"]}, set(IDS), "all fifteen exact prompts audited")
    a.eq(peer["open_findings"], [], "no unresolved substantive finding")
    a.yes(all(peer["review"].values()), "separate documented substantive review areas")


def check(root=None):
    root = Path(root).resolve() if root is not None else Path(__file__).resolve().parents[1]
    a = Audit()
    for procedure in (accounts, investment, allocation, derivatives, network):
        procedure(a)
    a.reject(lambda: exact(True), "boolean money")
    a.reject(lambda: exact(float("inf")), "nonfinite money")
    a.reject(lambda: solve((1, 1, 1), (2, 2, 2)), "singular replication")
    a.reject(lambda: one_period_log_slope(F(2), F(1, 2)), "unfunded weight")
    a.reject(lambda: one_period_log_slope(F(1, 2), F(0)), "outside strict two-state probability scope")
    a.reject(lambda: clearing_brackets(-1, 3), "negative external resource")
    a.reject(lambda: Cash(a, {"A": 0, "B": 0}).pay("A", "B", 1), "unfunded payment")
    a.reject(lambda: strict('{"cash":1,"cash":2}'), "duplicate JSON evidence")
    a.reject(lambda: strict('{"cash":NaN}'), "nonfinite JSON evidence")
    anchors = manuscript(a, root)
    bindings(a, root)
    result = {
        "component": "finance-core-exam-a-peer", "status": "passed",
        "comparisons": a.comparisons, "financial_interventions": len(a.interventions),
        "intervention_scopes": a.interventions, "oracle_or_funding_rejections": a.rejections,
        "cash_transfer_rows": a.cash_rows, "clearing_bracket_cases": a.clearing_cases,
        "scored_subparts_and_solutions": 15, "points": 100,
        "domain_points": {"D" + str(i): 20 for i in range(1, 6)},
        "printed_or_conceptual_anchors": anchors, "approximate_values_checked": 4,
        "author_payloads_bound": 4, "peer_checker_bound": True,
        "sampled_chapter_routes": 25, "inherited_source_scopes": 6,
        "limits": "Bounded synthetic-contract evidence and separate proof reading; no current law, rendered QA, calibrated exam equivalence, human certification or coordinator acceptance implied.",
    }
    json.dumps(result, allow_nan=False)
    return result


if __name__ == "__main__":
    print(json.dumps(check(), ensure_ascii=False, allow_nan=False, sort_keys=True))
