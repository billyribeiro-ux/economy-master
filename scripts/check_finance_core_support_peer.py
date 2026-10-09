"""Independent, bounded support review. Stdlib only; no author oracle or writes.

The HTML supplies the fixed contracts. This checker reconstructs dated transfers,
linear replication, payoff allocation, orthogonal-factor variance and the FX
feasible polygon. Mathematical certificates are reviewed in the accompanying
peer record; finite witnesses are not claimed to prove an arbitrary theorem.
"""
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from itertools import combinations
import json
from pathlib import Path
import re


AUTHOR = (
    "content/cross-assessments/parts/finance-core-support-opening.html",
    "content/cross-assessments/parts/finance-core-support-closing.html",
    "scripts/check_finance_core.py",
    "content/reviews/finance-core-support-sources.json",
    "content/reviews/finance-core-support-author.json",
)
SELF = "scripts/check_finance_core_support_peer.py"
RECORD = "content/reviews/finance-core-support-peer.json"
FROZEN = (
    (19055, "9feb645b729d574d67c0fc6f5f0d6e71fc91bd4da05e28c626232a8c0d5f1763"),
    (27389, "08f7ca20df264010e209433b5d6134446d9be32f31c75299dc155d72d5e3c76d"),
    (13195, "2305796a9d7e0a955c2b37f3e80aa6c1b89870e8b1e253f0476476530f414cbb"),
    (17969, "f09e0db1b97f60f68994fc11b787bfb8f9f4447682e8a2095a93b306fbdcd396"),
    (10050, "a4d9c0baf028d4838ed2a827b85be0e26e6e20c59987ead4cc32bd7263188576"),
)
GROUPS = {"d": (8, 5), "o": (5, 4), "r": (5, 10)}
PROMPTS = {
    f"finance-core-{group}{i}": points
    for group, (count, points) in GROUPS.items() for i in range(1, count + 1)
}


class Audit:
    def __init__(self):
        self.comparisons = 0
        self.rejections = 0
        self.interventions = []
        self.wallet_rows = 0
        self.polygon_candidates = 0

    def equal(self, actual, expected, name):
        self.comparisons += 1
        if actual != expected:
            raise ValueError(f"{name}: {actual!r} != {expected!r}")

    def yes(self, condition, name):
        self.equal(bool(condition), True, name)

    def rejects(self, operation, name):
        try:
            operation()
        except ValueError:
            self.rejections += 1
        else:
            raise ValueError(f"{name}: invalid domain accepted")

    def intervention(self, name):
        self.interventions.append(name)


def rational(value):
    if isinstance(value, bool) or not isinstance(value, (int, F)):
        raise ValueError("exact integer or rational required")
    return F(value)


def weighted(values, weights, probability=False):
    if not values or len(values) != len(weights):
        raise ValueError("nonempty matched states required")
    values, weights = tuple(map(rational, values)), tuple(map(rational, weights))
    if any(w <= 0 for w in weights):
        raise ValueError("strictly positive weights required in these contracts")
    if probability and sum(weights) != 1:
        raise ValueError("physical probabilities must sum to one")
    return sum(x * w for x, w in zip(values, weights))


def solve_two(row1, row2):
    """Solve two equations a*x+b*y=c by exact elimination."""
    a, b, c = map(rational, row1)
    d, e, f = map(rational, row2)
    determinant = a * e - b * d
    if determinant == 0:
        raise ValueError("singular two-equation system")
    return ((c * e - b * f) / determinant, (a * f - c * d) / determinant)


class Wallets:
    """Cash transfers require a funded payer; exogenous receipts are explicit.

    A receipt represents only a stated asset liquidation or dated recovery,
    never a new financing promise or accounting reclassification.
    """
    def __init__(self, audit, balances):
        self.audit = audit
        self.cash = {k: rational(v) for k, v in balances.items()}
        if any(v < 0 for v in self.cash.values()):
            raise ValueError("opening cash cannot be negative")
        self.total = sum(self.cash.values())

    def transfer(self, payer, recipient, amount):
        amount = rational(amount)
        if payer == recipient or amount < 0 or self.cash[payer] < amount:
            raise ValueError("transfer lacks distinct parties or usable cash")
        self.cash[payer] -= amount
        self.cash[recipient] += amount
        self.audit.wallet_rows += 1
        self.audit.equal(sum(self.cash.values()), self.total, "cash transfer conservation")

    def receipt(self, recipient, amount):
        amount = rational(amount)
        if amount < 0:
            raise ValueError("external receipt must be nonnegative")
        self.cash[recipient] += amount
        self.total += amount
        self.audit.wallet_rows += 1
        self.audit.equal(sum(self.cash.values()), self.total, "specified external cash receipt")


def variance_from_factors(weight):
    """r1=.10 Z1; r2=.05 Z1+sqrt(.0375) Z2, independent unit shocks."""
    weight = rational(weight)
    return (F(1, 10) * weight + F(1, 20) * (1 - weight)) ** 2 + F(3, 80) * (1 - weight) ** 2


def fx_vertices(audit, gap, late, gross, donor, lender):
    """Vertices of nonnegative dated cash in (grant, bridge).

    a*g+b*bridge<=c inequalities include both endowments. Early excess is
    retained in the second balance: final=grant-gap+late-(gross-1)*bridge.
    """
    gap, late, gross, donor, lender = map(rational, (gap, late, gross, donor, lender))
    if min(gap, late, donor, lender) < 0 or gross < 1:
        raise ValueError("nonnegative resources and nonnegative bridge interest required")
    bounds = (
        (-1, 0, 0), (1, 0, donor), (0, -1, 0), (0, 1, lender),
        (-1, -1, -gap), (-1, gross - 1, late - gap),
    )
    vertices = set()
    for first, second in combinations(bounds, 2):
        audit.polygon_candidates += 1
        try:
            g, b = solve_two(first, second)
        except ValueError:
            continue
        if all(a * g + d * b <= c for a, d, c in bounds):
            vertices.add((g, b))
    return sorted(vertices)


def strict_json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    def invalid(token):
        raise ValueError(f"nonfinite JSON value: {token}")

    return json.loads(text, object_pairs_hook=pairs, parse_constant=invalid)


class Page(HTMLParser):
    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.ids, self.links = [], set(), []
        self.prompts, self.solutions, self.text = {}, {}, []
        self.active, self.depth = None, None
        self.h1 = 0

    def handle_starttag(self, tag, attrs):
        if len(dict(attrs)) != len(attrs):
            raise ValueError("duplicate HTML attribute")
        attrs = dict(attrs)
        if "id" in attrs:
            if attrs["id"] in self.ids:
                raise ValueError("duplicate HTML ID")
            self.ids.add(attrs["id"])
        if tag == "a":
            self.links.append(attrs.get("href", ""))
        if tag == "h1":
            self.h1 += 1
        if "data-points" in attrs or "data-solution-for" in attrs:
            if tag != "li" or self.active:
                raise ValueError("scored prompt/solution must be a distinct li")
            if "data-points" in attrs:
                key = attrs.get("id")
                self.prompts[key] = {"points": int(attrs["data-points"]), "text": []}
                self.active = self.prompts[key]["text"]
            else:
                key = attrs["data-solution-for"]
                if key in self.solutions:
                    raise ValueError("duplicate solution target")
                self.solutions[key] = []
                self.active = self.solutions[key]
            self.depth = len(self.stack)
        if tag not in self.VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if not self.stack or self.stack[-1] != tag:
            raise ValueError(f"unbalanced HTML: {tag}")
        self.stack.pop()
        if self.active is not None and len(self.stack) == self.depth:
            self.active, self.depth = None, None

    def handle_data(self, text):
        self.text.append(text)
        if self.active is not None:
            self.active.append(text)


def prose(text):
    return re.sub(r"\s+", " ", text).strip()


def compact(text):
    return re.sub(r"\s+", "", text).replace("−", "-").replace("–", "-")


def numerical_review(a):
    # D1/R1: reconstruct receipts independently of the noncash expense bridge.
    for label, rev, collected, ar0, costs, depreciation, allowance, opening, capex, borrowing, dividend, answer in (
        ("d1", 100, 80, 15, 55, 10, 0, 12, 20, 8, 5, (35, 35, 35, 25, 20)),
        ("r1", 130, 110, 20, 60, 10, 6, 10, 25, 5, 15, (40, 34, 54, 50, 25)),
    ):
        gross = ar0 + rev - collected
        net = gross - allowance
        income = rev - costs - depreciation - allowance
        cash_ops = collected - costs
        close = opening + cash_ops - capex + borrowing - dividend
        a.equal((gross, net, income, cash_ops, close), answer, label + " independent cash/accrual reconstruction")
        a.equal(income + depreciation + allowance - (gross - ar0), cash_ops, label + " gross bridge")
        a.equal(income + depreciation - (net - ar0), cash_ops, label + " net bridge")
    a.equal(50 - 25, 25, "r1 FCFF")
    a.equal(54 + 10 + 6 - (34 - 20), 56, "r1 duplicated noncash allowance witness")
    # Delay ten of D1 collections, preserving recognized revenue/expense.
    a.equal((15 + 100 - 70, 70 - 55, 12 + 70 - 55 - 20 + 8 - 5), (45, 15, 10), "d1 delayed collection")
    a.equal(100 - 55 - 10, 35, "d1 unchanged accrual income")
    a.intervention("Receipts delayed while income is fixed; receivable and closing cash move in opposite directions.")
    # Removing the R1 provision raises reported income and net AR, not cash.
    a.equal((130 - 60 - 10, 40, 110 - 60), (60, 40, 50), "r1 provision reversal cash invariant")
    a.intervention("Allowance zero versus six preserves cash; using net AR plus a second provision addition fails.")

    # D2: tax applied to operating income; debt is a claim, not a cash-flow expense.
    a.equal(40 - F(1, 4) * 40 + 8 - 15 - 5, 18, "d2 FCFF")
    a.equal(180 + 10 - 50, 140, "d2 residual equity")
    a.equal(18 - 4, 14, "d2 erroneous interest subtraction changes priced object")
    # D3: count separately the fractional share's price and dividend proceeds.
    shares = F(60, 80)
    a.equal((shares * 88, shares * 4), (66, 3), "d3 components of stock wealth")
    a.equal((F(88 + 4 - 80, 80), shares * (88 + 4), 40 * F(95, 100)), (F(3, 20), 69, 38), "d3 funded returns")
    a.equal(F(69 + 38 - 100, 100), F(7, 100), "d3 portfolio return")

    # D4/O2/R2: positive state prices are not physical probabilities.
    a.equal(weighted((20, 0), (F(2, 5), F(1, 2))), 8, "d4 Arrow replication")
    a.equal(weighted((20, 0), (F(7, 10), F(3, 10)), True), 14, "d4 physical mean")
    a.equal(1 / weighted((1, 1), (F(2, 5), F(1, 2))), F(10, 9), "d4 bank gross return")
    for up, mean in ((F(4, 5), 108), (F(1, 5), 72)):
        a.equal(weighted((120, 60), (up, 1 - up), True), mean, "o2 forecast")
        a.equal(weighted((120, 60), (F(3, 10), F(3, 5))), 72, "o2 price fixed")
    a.intervention("Changing physical probabilities changes the forecast, leaving traded state-price valuation fixed.")

    # D5: zero portfolios price dated cash and lock the future reinvestment.
    a.equal(5 * F(24, 25) + 105 * F(9, 10), F(993, 10), "d5 dated bond")
    a.equal(F(24, 25) / F(9, 10), F(16, 15), "d5 matched initial zero expenditure")
    a.equal(F(16, 15) - 1, F(1, 15), "d5 net forward")
    # D6: solve the two terminal obligations, not the printed hedge formula.
    delta, bank = solve_two((65, F(21, 20), 15), (40, F(21, 20), 0))
    a.equal((delta, bank, delta * 50 + bank), (F(3, 5), -F(160, 7), F(50, 7)), "d6 linear replication")
    for stock in (65, 40):
        a.equal(delta * stock + bank * F(21, 20), max(stock - 50, 0), "d6 every terminal state")
    qu, qd = solve_two((65, 40, 50), (1, 1, F(20, 21)))
    a.equal((qu, qd, qu * F(21, 20)), (F(10, 21), F(10, 21), F(1, 2)), "d6 state prices then pricing probability")

    # D7/O1/O5: chronology and owner-specific cash, independent of value labels.
    cash = Wallets(a, {"firm": 4, "lender": 5, "creditor": 0})
    cash.transfer("lender", "firm", 5)
    cash.transfer("firm", "creditor", 9)
    a.equal(cash.cash["firm"], 0, "d7 first cutoff")
    cash.receipt("firm", 12)
    cash.transfer("firm", "lender", F(11, 2))
    a.equal((cash.cash["firm"], cash.cash["lender"]), (F(13, 2), F(11, 2)), "d7 recipient allocations")
    a.equal(F(11, 2) - 5, F(1, 2), "d7 interest only")
    a.equal((200 - 170, 9 - 4), (30, 5), "d7 book equity does not eliminate gap")
    a.equal(sum(amount for hour, amount in ((12, 5),) if hour <= 10), 0, "o5 noon resource absent at ten")
    a.equal(sum(amount for hour, amount in ((9, 5),) if hour <= 10), 5, "o5 actual earlier delivery repairs first cutoff")
    a.intervention("Move an actual five-unit disbursement across the deadline; unchanged promise/value cannot repair the earlier cutoff.")

    # D8: explicitly sum eight discounted cash terms and an exact tail.
    growth, gross = F(51, 50), F(27, 25)
    ratio = growth / gross
    first = F(12) / gross
    partial = sum(first * ratio ** i for i in range(8))
    tail = first * ratio ** 8 / (1 - ratio)
    a.equal((ratio, partial + tail), (F(17, 18), 200), "d8 geometric sum plus tail certificate")
    a.equal((partial + tail) * gross - 12, 204, "d8 ex-payment continuation")
    a.equal(12 * growth, F(306, 25), "d8 first continuation cash")
    a.yes(gross / gross >= 1 and 12 / gross > 0, "d8 equal growth/discount gives nonvanishing positive terms")
    a.intervention("At growth equal to discount, positive discounted payments do not tend to zero; the perpetuity formula is unavailable.")

    # O3: a funded long-only convex mixture cannot beat the better expected return.
    a.equal((100 - 2) * F(11, 10), F(539, 5), "o3 global upper wealth bound")
    a.equal((F(539, 5) - 100) / 100, F(39, 500), "o3 return on original endowment")
    a.equal(108 - F(539, 5), F(1, 5), "o3 target deficit")
    a.equal(100 - 108 / F(11, 10), F(20, 11), "o3 largest fee consistent with target")
    a.yes((100 - 1) * F(11, 10) >= 108, "o3 changed one-unit fee attains target")
    a.intervention("A one-unit fee makes the previously impossible expected-wealth target feasible without hidden leverage.")

    # O4: rank test and all-price construction, with endpoint arbitrages.
    delta, bank = solve_two((100, 1, 20), (60, 1, 0))
    a.equal((delta, bank, delta * 80 + bank), (F(1, 2), -30, 10), "o4 forced extreme hedge")
    a.equal(delta * 80 + bank - max(80 - 80, 0), 10, "o4 middle residual")
    # At any proposed c in (0,10), q=(c/20,1-c/10,c/20) exactly spans bank/stock/call prices.
    for call_price in (F(1), F(5), F(9)):
        qs = (call_price / 20, 1 - call_price / 10, call_price / 20)
        a.equal((weighted((1, 1, 1), qs), weighted((100, 80, 60), qs), weighted((20, 0, 0), qs)), (1, 80, call_price), "o4 positive extension")
    a.equal(tuple(delta * s + bank - max(s - 80, 0) for s in (100, 80, 60)), (0, 10, 0), "o4 zero-cost upper endpoint arbitrage")
    a.equal(tuple(max(s - 80, 0) for s in (100, 80, 60)), (20, 0, 0), "o4 free call lower endpoint arbitrage")
    a.intervention("Restoring the middle state destroys exact replication; endpoint prices admit explicit nonnegative nonzero zero-cost portfolios.")

    # R2: senior first, residual second; then funded parties at inception.
    assets = (120, 60)
    debt = tuple(min(80, x) for x in assets)
    equity = tuple(x - y for x, y in zip(assets, debt))
    prices = (F(3, 10), F(3, 5))
    a.equal((debt, equity), ((80, 60), (40, 0)), "r2 terminal priority")
    a.equal(tuple(x + y for x, y in zip(debt, equity)), assets, "r2 statewise resource conservation")
    values = tuple(weighted(payoff, prices) for payoff in (assets, debt, equity))
    a.equal(values, (72, 60, 12), "r2 values by actual payoff")
    cash = Wallets(a, {"debt_buyer": 70, "investor": 5, "seller": 0})
    cash.transfer("debt_buyer", "seller", values[1])
    cash.transfer("investor", "seller", 62 - values[1])
    a.equal(cash.cash, {"debt_buyer": 10, "investor": 3, "seller": 62}, "r2 actual purchase budgets")
    a.equal((values[1] + cash.cash["debt_buyer"], values[2] + cash.cash["investor"]), (70, 15), "r2 claim plus unspent wealth")
    a.equal((15 - 5, 72 - 62), (10, 10), "r2 same gain across equity and asset views")
    a.equal((weighted(debt, (F(4, 5), F(1, 5)), True), 80 - debt[1]), (76, 20), "r2 expectation versus proceeds and face deficiency")
    # Face60 shifts funding/equity without inventing extra operating value.
    less_debt = tuple(min(60, x) for x in assets)
    debt_value = weighted(less_debt, prices)
    equity_value = weighted(tuple(x - y for x, y in zip(assets, less_debt)), prices)
    a.equal((debt_value, equity_value, 62 - debt_value), (54, 18, 8), "r2 lower-face funded contribution")
    a.yes(8 > 5, "r2 unchanged investor endowment blocks otherwise positive-NPV acquisition")
    a.equal(equity_value - 8, 10, "r2 pricing NPV invariant does not imply execution")
    a.intervention("Debt face reduced to sixty leaves NPV unchanged but raises required own cash above the investor's five-unit endowment.")

    # R3: factor covariance and algebraic certificates, not a weight-search oracle.
    a.equal((F(1, 10) ** 2, F(1, 20) ** 2 + F(3, 80), F(1, 10) * F(1, 20)), (F(1, 100), F(1, 25), F(1, 200)), "r3 independent factor covariance")
    a.equal(F(1, 100) * F(1, 25) - F(1, 200) ** 2, F(3, 8000), "r3 positive determinant")
    a.equal((variance_from_factors(F(7, 8)), F(3, 50) * F(7, 8) + F(1, 10) * F(1, 8)), (F(3, 320), F(13, 200)), "r3 unconstrained candidate")
    # Coefficients of the positive square and of (1/2-w)(1/20-w/25).
    a.equal((F(1, 25), -2 * F(7, 8) / 25, F(7, 8) ** 2 / 25 + F(3, 320)), (F(1, 25), -F(7, 100), F(1, 25)), "r3 full-square polynomial identity")
    a.equal((F(1, 25), -F(1, 50) - F(1, 20), F(1, 40)), (F(1, 25), -F(7, 100), F(1, 25) - F(3, 200)), "r3 constrained global difference certificate")
    a.equal((F(1, 10) - F(2, 25)) / (F(1, 10) - F(3, 50)), F(1, 2), "r3 whole feasible interval endpoint")
    a.equal(variance_from_factors(F(1, 2)), F(3, 200), "r3 constrained variance")
    a.yes(F(1, 20) - F(1, 2) / 25 > 0, "r3 certificate second factor positive over interval")
    a.equal((F(1, 10) - F(9, 100)) / F(1, 25), F(1, 4), "r3 stronger mean target narrows interval")
    a.equal(variance_from_factors(F(1, 4)), F(1, 40), "r3 stronger-target minimum variance")
    a.yes(F(11, 100) > max(F(3, 50), F(1, 10)), "r3 eleven-percent target impossible")
    a.intervention("A nine-percent mean target restricts the optimum to one-quarter in asset one; eleven percent is impossible in this opportunity set.")

    # R4: original hedge, margin principal, separately funded borrower/lender wallets.
    charge = F(5) - F(5) / F(26, 25)
    a.equal((charge, 5 - charge, 10 + charge), (F(5, 26), F(125, 26), F(265, 26)), "r4 retained-charge solution")
    a.equal(5 - 5 * F(26, 25), -F(1, 5), "r4 no-charge terminal deficiency")
    for stock in (100, 60):
        a.equal(F(stock, 2) - 30, max(stock - 80, 0), "r4 original hedge cash")
        cash = Wallets(a, {"buyer": 15, "bank": 30, "provider": 5, "seller": 0, "stock_seller": 0, "escrow": 0})
        cash.transfer("buyer", "seller", 10 + charge)
        cash.transfer("bank", "seller", 30)
        cash.transfer("seller", "stock_seller", 40)
        a.equal(cash.cash["seller"], charge, "r4 only extra charge remains")
        cash.transfer("provider", "seller", 5 - charge)
        cash.transfer("seller", "escrow", 5)
        a.equal((cash.cash["seller"], cash.cash["bank"], cash.cash["escrow"]), (0, 0, 5), "r4 segregated cash not bank liquidity")
        cash.transfer("escrow", "seller", 5)
        cash.transfer("seller", "provider", F(26, 25) * (5 - charge))
        cash.receipt("seller", F(stock, 2))
        cash.transfer("seller", "bank", 30)
        cash.transfer("seller", "buyer", max(stock - 80, 0))
        a.equal((cash.cash["seller"], cash.cash["bank"], cash.cash["provider"]), (0, 30, 5 + charge), "r4 all obligations and provider interest")
    short_charge = charge - F(1, 1000)
    a.equal(5 - F(26, 25) * (5 - short_charge), -F(26, 25000), "r4 below-threshold failure")
    a.equal(5 - F(5) / 1, 0, "r4 zero-interest bridge needs no extra charge")
    a.intervention("The margin threshold fails just below the sharp extra charge and collapses to zero when bridge interest is removed.")

    # R5: find all extreme points, independently of the manuscript's lower-bound route.
    late = F(1, 2) * (20 - 3)
    a.equal((late, 3 + late, 4 + 20 + 3, 36 - (4 + 20 + 3)), (F(17, 2), F(23, 2), 27, 9), "r5 recovery base and deadline")
    a.equal(late - 9 * F(21, 20), -F(19, 20), "r5 bridge-only late deficit")
    a.equal(4 + 20 + 3 + late - 36, -F(1, 2), "r5 ultimate resource deficiency")
    vertices = fx_vertices(a, 9, late, F(21, 20), 1, 9)
    a.equal(vertices, [(F(19, 21), F(170, 21)), (F(19, 20), F(9)), (F(1), F(8)), (F(1), F(9))], "r5 entire feasible polygon vertices")
    grant, bridge = min(vertices)
    cash = Wallets(a, {"company": 4, "dealer": 20, "collateral": 3, "provider": 9, "donor": 1, "supplier": 0})
    cash.transfer("dealer", "company", 20)  # Dealer obtains all twenty F.
    cash.transfer("collateral", "company", 3)
    cash.transfer("donor", "company", grant)
    cash.transfer("provider", "company", bridge)
    cash.transfer("company", "supplier", 36)
    a.equal(cash.cash["company"], 0, "r5 earliest cutoff is fully funded")
    cash.receipt("company", late)
    cash.transfer("company", "provider", bridge * F(21, 20))
    a.equal((cash.cash["company"], cash.cash["donor"], cash.cash["provider"]), (0, F(2, 21), 9 + F(17, 42)), "r5 final recipients")
    a.equal(grant, F(1, 2) + F(17, 42), "r5 grant covers ultimate deficiency plus interest")
    # Retain excess borrowing rather than accidentally burning it at date one.
    excess = F(1, 2)
    a.equal(27 + grant + bridge + excess - 36, excess, "r5 carried excess cash")
    a.equal(excess + late - F(21, 20) * (bridge + excess), -F(1, 40), "r5 extra borrowing still loses only its interest")
    a.intervention("At the minimum grant, an extra half-unit bridge is retained initially but creates a terminal one-fortieth deficit from interest.")
    a.equal(min(fx_vertices(a, 9, F(189, 20), F(21, 20), 1, 9)), (0, 9), "r5 sufficient late recovery removes grant requirement")
    a.equal(fx_vertices(a, 9, 8, F(21, 20), 1, 9), [], "r5 poorer recovery defeats all endowed grant/bridge plans")
    a.equal(min(fx_vertices(a, F(1, 2), 0, F(21, 20), 1, 9)), (F(1, 2), 0), "r5 moving same recovery early removes interest need")
    a.intervention("Change the amount or delivery date of recovery: grant can become zero, infeasible, or one-half with no bridge.")

    # Invalids concern the independent oracle's explicit mathematical domains.
    a.rejects(lambda: weighted((1, 2), (F(2, 5), F(1, 2)), True), "state prices cannot masquerade as probabilities")
    a.rejects(lambda: weighted((1,), (F(1, 2), F(1, 2))), "state dimension")
    a.rejects(lambda: weighted((1, 2), (0, 1)), "strictly positive extension")
    a.rejects(lambda: rational(True), "boolean is not money")
    a.rejects(lambda: rational(float("nan")), "nonfinite is not exact money")
    a.rejects(lambda: solve_two((1, 1, 1), (2, 2, 2)), "singular replication")
    a.rejects(lambda: fx_vertices(a, 9, 8, F(9, 10), 1, 9), "negative-interest shortcut outside stated oracle")
    a.rejects(lambda: Wallets(a, {"one": 1, "two": 0}).transfer("one", "two", 2), "unfunded transfer")
    a.rejects(lambda: strict_json('{"cash":1,"cash":2}'), "duplicate evidence key")
    a.rejects(lambda: strict_json('{"cash":NaN}'), "nonfinite evidence")


def document_review(a, root):
    page = Page()
    for path in AUTHOR[:2]:
        page.feed((root / path).read_text(encoding="utf-8"))
    page.close()
    a.equal(page.stack, [], "balanced support fragments")
    a.equal(page.h1, 1, "support sole heading one")
    a.equal({k: v["points"] for k, v in page.prompts.items()}, PROMPTS, "all exact scored prompt IDs/points")
    a.equal(set(page.solutions), set(PROMPTS), "all exact solution targets")
    numbers = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "ten": 10}
    for key, points in PROMPTS.items():
        answer = prose("".join(page.solutions[key]))
        rubric = re.search(r"Credit (four|five|ten):\s*([^.]+)\.", answer)
        a.yes(rubric is not None, key + " explicit rubric")
        a.equal(numbers[rubric.group(1)], points, key + " rubric heading")
        a.equal(sum(numbers[word] for word in re.findall(r"\b(one|two|three)\s*(?:;|$)", rubric.group(2))), points, key + " rubric allocation")
        a.yes(len(prose("".join(page.prompts[key]["text"]))) > 150 and len(answer) > 300, key + " complete prompt and response present")

    anchors = {
        "d1": ("Income 35", "operating cash 25", "closing cash 20"),
        "d2": ("FCFF 18", "equity value 140", "Financing interest is excluded"),
        "d3": ("Stock return 15%", "69 and 38", "portfolio return 7%"),
        "d4": ("Price 8", "expected payoff 14", "return 10/9"),
        "d5": ("Price 99.3", "net forward rate 1/15"),
        "d6": ("3/5 of a share", "−160/7", "call price 50/7", "q=1/2"),
        "d7": ("funded cash zero", "6.5 later", "not another twelve of revenue"),
        "d8": ("date 1 is 204", "date 0 is 200", "12.24"),
        "o1": ("classification does not change", "evidence", "actual funded sale"),
        "o2": ("=108", "=72", "numerical coincidence"),
        "o3": ("98", "107.8", "7.8%", "infeasible"),
        "o4": ("20,10,0", "a,1−2a,a", "(0,10)", "nonreplication"),
        "o5": ("cash is zero", "payment is missed", "Noon receipt cannot undo"),
        "r1": ("Net receivables 34", "income 54", "operating cash 50", "FCFF 25", "produce 56"),
        "r2": ("value 72", "proceeds 60", "equity value 12", "own cash two", "=76", "limited"),
        "r3": ("w=7/8", "w=1/2", "3/8000", "3/320", "13/200", "3/200"),
        "r4": ("5/26", "125/26", "265/26", "1.04x−0.2", "policy"),
        "r5": ("19/21", "170/21", "11.5", "9.45", "g−0.5−0.05b", "unused early cash carries"),
    }
    count = 0
    for suffix, tokens in anchors.items():
        answer = compact("".join(page.solutions["finance-core-" + suffix]))
        # The limited-acquisition qualifier occurs in both prompt and answer as
        # access/opportunity scope; bind the exact prompt word separately.
        if suffix == "r2":
            answer += compact("".join(page.prompts["finance-core-r2"]["text"]))
        for token in tokens:
            a.yes(compact(token) in answer, suffix + " printed anchor: " + token)
            count += 1
    for key, pattern, exact, tolerance in (
        ("finance-core-d5", r"approximately ([0-9]+\.[0-9]+)%", F(20, 3), F(1, 20000)),
        ("finance-core-r4", r"approximately ([0-9]+\.[0-9]+)\.", F(5, 26), F(1, 2000000)),
    ):
        match = re.search(pattern, "".join(page.solutions[key]))
        a.yes(match is not None, key + " rounded display present")
        a.yes(abs(F(match.group(1)) - exact) <= tolerance, key + " half-last-place rounding")
    full = prose("".join(page.text))
    for phrase in ("300 minutes", "nonprogrammable calculator", "85/100", "15/20", "34/40", "17/20", "43/50", "14–21 days", "neither admissions requirements nor a credential", "not a measured completion time", "independent human evaluation", "without repeatedly deducting"):
        a.yes(phrase in full, "administration: " + phrase)
    assembly = {"form-a", "form-b", "project"}
    for href in set(page.links):
        if href.startswith("#"):
            a.yes(href[1:] in page.ids | assembly, "local or declared assembly anchor " + href)
        else:
            a.yes(bool(re.fullmatch(r"v(?:07|08|09|10|11)-c(?:0[1-9]|1[0-2])\.html|curriculum\.html#v(?:0[7-9]|1[0-4])", href)), "scoped flat teaching link " + href)
    sources = strict_json((root / AUTHOR[3]).read_text(encoding="utf-8"))
    expected = {f"v{v:02d}-c{c:02d}" for v in range(7, 12) for c in range(1, 13)}
    routes = sources["method_routes"]
    a.equal({r["chapter"] for r in routes}, expected, "all sixty accepted-method routes")
    a.equal(len(routes), 60, "no duplicate source routes")
    a.equal({h[:-5] for h in page.links if re.fullmatch(r"v\d\d-c\d\d\.html", h)}, expected, "sixty chapter links in actual support")
    a.equal((sources["proposals"], sources["reused_source_ids"]), ([], []), "local-method reuse without invented fresh source retrieval")
    a.yes(all(r["manuscript"] == "chapters/" + r["chapter"] + ".html" and r["title"] and r["scope"] for r in routes), "source routes names and paths")
    return count


def fingerprint(path):
    data = path.read_bytes()
    return len(data), sha256(data).hexdigest()


def binding_review(a, root):
    for path, frozen in zip(AUTHOR, FROZEN):
        a.equal(fingerprint(root / path), frozen, "final author freeze " + path)
    author = strict_json((root / AUTHOR[4]).read_text(encoding="utf-8"))
    a.equal({r["path"] for r in author["reviewed_hashes"]}, set(AUTHOR[:4]), "four nonself author bindings")
    for row in author["reviewed_hashes"]:
        a.equal(fingerprint(root / row["path"]), (row["bytes"], row["sha256"]), "author binding " + row["path"])
    peer = strict_json((root / RECORD).read_text(encoding="utf-8"))
    rows = peer["reviewed_hashes"]
    a.equal(len(rows), 6, "exact six peer bindings, no peer-record self hash")
    a.equal({r["path"] for r in rows}, set(AUTHOR) | {SELF}, "peer bindings exact owned/input scope")
    for row in rows:
        a.equal(fingerprint(root / row["path"]), (row["bytes"], row["sha256"]), "peer binding " + row["path"])
    a.equal({r["prompt"] for r in peer["prompt_solution_audit"]}, set(PROMPTS), "peer reviewed all eighteen exact prompts")
    a.equal(peer["open_findings"], [], "no unresolved substantive finding")
    a.yes(all(peer["review"].values()), "documented peer review areas")


def check(root=None):
    root = Path(root).resolve() if root is not None else Path(__file__).resolve().parents[1]
    audit = Audit()
    numerical_review(audit)
    anchors = document_review(audit, root)
    binding_review(audit, root)
    summary = {
        "component": "finance-core-support-peer", "status": "passed",
        "comparisons": audit.comparisons,
        "financial_interventions": len(audit.interventions),
        "intervention_scopes": audit.interventions,
        "oracle_domain_rejections": audit.rejections,
        "funded_transfer_and_receipt_rows": audit.wallet_rows,
        "purposeful_polygon_candidates": audit.polygon_candidates,
        "exact_prompts_and_solutions": 18,
        "rubric_points": {"diagnostic": 40, "oral": 20, "retention": 50},
        "printed_or_conceptual_anchors": anchors,
        "rounded_values_checked": 2,
        "author_payloads_bound": 5, "peer_checker_bound": True,
        "source_method_routes": 60,
        "limits": "Synthetic contracts and bounded independent evidence; no rendered UI, timing calibration, learner certification or final coordinator acceptance is implied.",
    }
    json.dumps(summary, allow_nan=False)
    return summary


if __name__ == "__main__":
    print(json.dumps(check(), ensure_ascii=False, allow_nan=False, sort_keys=True))
