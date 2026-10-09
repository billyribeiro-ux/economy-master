"""Independent numerical and structural audit of Volume 10 Form B.

Reconstructs the question's dated cash, finite-state prices and funded ledger.
Uses exact fractions, exhaustive histories, direct normal-density integration,
symbolic power coefficients and independent payoff envelopes. No chapter model
or saved numerical output supplies an oracle. check() is quiet, JSON-safe and
independent of the caller's directory. Only the four frozen assessment files
are needed in a copied tree. Counts are executed checks, not proof counts.
"""
from fractions import Fraction as F
from html.parser import HTMLParser
from itertools import combinations, product
import hashlib
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = "content/assessments/parts/v10-exam-b.html"
SOURCES = "content/reviews/v10-exam-b-sources.json"
AUTHOR = "content/reviews/v10-exam-b-author.json"
CHECKER = "scripts/check_v10_exam_b.py"
POINTS = {f"v10-b-q{q}{part}": points
          for q, scores in enumerate(((6, 8, 6), (8, 8, 4), (6, 6, 8),
                                      (8, 8, 4), (5, 7, 3, 5)), 1)
          for part, points in zip("abcd", scores)}
SOURCE_IDS = {
    "v10-c03-haugh-lattice", "v10-c04-recovery-par", "v10-c05-cme-variation",
    "v10-c07-haugh-diffusions", "v10-c09-haugh-greeks",
    "v10-c10-haugh-output", "v10-c11-haugh-discrete",
}


def need(condition, label):
    if not condition:
        raise ValueError(label)


class Audit:
    def __init__(self):
        self.comparisons = 0
        self.rejections = 0
        self.interventions = []

    def eq(self, actual, expected, label):
        self.comparisons += 1
        if actual != expected:
            raise RuntimeError(f"{label}: {actual!r} != {expected!r}")

    def ok(self, condition, label):
        self.eq(bool(condition), True, label)

    def near(self, actual, expected, label, tol=1e-10):
        self.ok(math.isfinite(actual) and math.isfinite(expected)
                and abs(actual - expected) <= tol,
                f"{label}: {actual!r} versus {expected!r}")

    def rejects(self, function, label):
        try:
            function()
        except ValueError:
            self.rejections += 1
        else:
            raise RuntimeError("Expected domain rejection: " + label)


def dot(a, b):
    need(len(a) == len(b), "Equal-length vectors required")
    return sum((x * y for x, y in zip(a, b)), F(0))


def solve(matrix, rhs):
    """Exact Gaussian elimination; no external linear algebra library."""
    n = len(rhs)
    need(n > 0 and len(matrix) == n and all(len(r) == n for r in matrix),
         "Nonempty square system required")
    a = [[F(x) for x in row] + [F(y)] for row, y in zip(matrix, rhs)]
    for j in range(n):
        k = next((i for i in range(j, n) if a[i][j]), None)
        need(k is not None, "Singular system")
        a[j], a[k] = a[k], a[j]
        divisor = a[j][j]
        a[j] = [v / divisor for v in a[j]]
        for i in range(n):
            if i != j:
                multiplier = a[i][j]
                a[i] = [v - multiplier * w for v, w in zip(a[i], a[j])]
    return tuple(row[-1] for row in a)


def transition_paths(matrix, initial, periods):
    n = len(matrix)
    need(n > 0 and all(len(row) == n and all(p >= 0 for p in row)
                      and sum(row) == 1 for row in matrix),
         "Stochastic transition matrix required")
    need(isinstance(initial, int) and 0 <= initial < n
         and isinstance(periods, int) and 0 <= periods <= 4,
         "Valid initial state and bounded horizon required")
    paths = []
    for following in product(range(n), repeat=periods):
        history = (initial,) + following
        mass = math.prod(matrix[history[i]][history[i + 1]]
                         for i in range(periods))
        paths.append((history, mass))
    return paths


def credit_value(matrix, discounts, recovery=F(40), delay=1):
    need(len(discounts) == 3 and all(d > 0 for d in discounts)
         and 0 <= recovery <= 100 and delay in (0, 1),
         "Positive dated prices, bounded recovery and specified settlement delay required")
    # Enumerate full rating histories, then locate first default once.
    cash = [F(0)] * 3
    first = [F(0)] * 2
    survival = F(0)
    for history, mass in transition_paths(matrix, 1, 2):
        default = next((t for t in (1, 2) if history[t] == 2), None)
        if default is None:
            survival += mass
            cash[1] += 100 * mass
        else:
            first[default - 1] += mass
            cash[default + delay - 1] += recovery * mass
    return tuple(first), survival, tuple(cash), dot(discounts, cash)


def margin_ledger(quotes, signed_multiplier, initial=F(100), maintenance=F(75),
                  factors=(F("1.005"), F("1.01"), F("1.015"))):
    need(len(quotes) == 4 and len(factors) == 3 and all(x > 0 for x in factors)
         and initial > 0 and 0 <= maintenance <= initial,
         "Three dated intervals and valid margin convention required")
    balance, debt = initial, initial
    contributions = [initial]
    before, after, variation = [], [], []
    for t in range(1, 4):
        debt *= factors[t - 1]
        change = signed_multiplier * (quotes[t] - quotes[t - 1])
        variation.append(change)
        balance += change
        before.append(balance)
        topup = initial - balance if t < 3 and balance < maintenance else F(0)
        contributions.append(topup)
        debt += topup
        balance += topup
        after.append(balance)
    return {"variation": tuple(variation), "before": tuple(before),
            "after": tuple(after), "contributions": tuple(contributions),
            "release": balance, "debt": debt,
            "funded": balance - debt}


def replication(s0, sd, su, gross, xd, xu):
    need(0 < sd < su and s0 > 0 and gross > 0 and sd < gross * s0 < su,
         "Strict two-state no-arbitrage domain required")
    delta, terminal_bank = solve(((sd, 1), (su, 1)), (xd, xu))
    p = (gross * s0 - sd) / (su - sd)
    return delta, terminal_bank / gross, delta * s0 + terminal_bank / gross, p


def integrate(function, a, b, n=4096):
    need(n > 0 and n % 2 == 0 and a < b, "Even positive Simpson grid required")
    h = (b - a) / n
    return h / 3 * (function(a) + function(b)
                    + 4 * math.fsum(function(a + i * h) for i in range(1, n, 2))
                    + 2 * math.fsum(function(a + i * h) for i in range(2, n, 2)))


def density(z):
    return math.exp(-z * z / 2) / math.sqrt(2 * math.pi)


def normal_power_moment(s, drift, sigma, tau, exponent):
    need(s > 0 and tau >= 0 and sigma >= 0
         and all(math.isfinite(x) for x in (s, drift, sigma, tau, exponent)),
         "Finite positive-stock GBM domain required")
    return s ** exponent * math.exp(exponent * drift * tau
                                    + exponent * (exponent - 1) * sigma**2 * tau / 2)


def inverse_price(t, s, r=.03, q=.01, sigma=.2, maturity=1.0):
    need(0 <= t <= maturity and s > 0 and sigma >= 0
         and all(math.isfinite(x) for x in (t, s, r, q, sigma, maturity)),
         "Valid inverse-claim stock/time domain required")
    return 10000 / s * math.exp((q + sigma * sigma - 2 * r) * (maturity - t))


def put_by_integral(s, k, tau, r, q, sigma):
    """Discount payoff and pathwise delta against a Gaussian density.

    This does not use the Black-Scholes CDF price/delta formulas. The kink is
    the integration endpoint, and two nested grids check quadrature error.
    All audit parameter sets put that endpoint strictly inside [-10, 10].
    """
    need(min(s, k, tau, sigma) > 0, "Positive option interior required")
    v = sigma * math.sqrt(tau)
    mu = (r - q - sigma * sigma / 2) * tau
    cutoff = (math.log(k / s) - mu) / v
    need(-10 < cutoff < 10, "Audit quadrature range exceeded")
    def terminal(z):
        return s * math.exp(mu + v * z)
    values = []
    for n in (2048, 4096):
        pv = math.exp(-r * tau) * integrate(
            lambda z: (k - terminal(z)) * density(z), -10, cutoff, n)
        delta = -math.exp(-r * tau) * integrate(
            lambda z: terminal(z) / s * density(z), -10, cutoff, n)
        values.append((pv, delta))
    return values


def hedge_ledger(rate=F(".001"), bank_factor=F("1.010050167084"),
                 dividend_factor=F("1.005012520859")):
    need(rate >= 0 and bank_factor > 0 and dividend_factor > 0,
         "Nonnegative fee and positive accumulation required")
    premium, d0, d1 = F("7.364289723"), F("-.436000430455"), F("-.216606525638")
    initial_bank = premium - d0 * 100
    shares = d0 * dividend_factor
    cash = initial_bank * bank_factor
    wealth = 110 * shares + cash
    stock_trade = (d1 - shares) * 110
    fee = rate * abs(stock_trade)
    new_bank = cash - stock_trade - fee
    final_shares = d1 * dividend_factor
    final_bank = new_bank * bank_factor
    return {"initial_bank": initial_bank, "incoming_shares": shares,
            "incoming_bank": cash, "wealth": wealth, "trade": stock_trade,
            "fee": fee, "new_bank": new_bank, "final_shares": final_shares,
            "final_bank": final_bank, "error": 90 * final_shares + final_bank - 10,
            "external_transfer": F("2.067544281") - wealth}


def inverse_interval(estimate, pair_sd, pairs, bias, quote, candidate,
                     vega_lower, bracket):
    values = (estimate, pair_sd, bias, quote, candidate, vega_lower, *bracket)
    need(all(isinstance(x, (int, float)) and not isinstance(x, bool)
             and math.isfinite(x) for x in values), "Finite numerical evidence required")
    need(isinstance(pairs, int) and not isinstance(pairs, bool) and pairs >= 2
         and pair_sd >= 0 and bias >= 0 and vega_lower > 0
         and len(bracket) == 2 and bracket[0] <= candidate <= bracket[1]
         and bracket[0] < bracket[1], "Fixed independent units and whole-bracket positive vega required")
    se = pair_sd / math.sqrt(pairs)
    raw = (estimate - 1.96 * se, estimate + 1.96 * se)
    padded = (raw[0] - bias, raw[1] + bias)
    lo = max(bracket[0], candidate + min(0.0, quote - padded[1]) / vega_lower)
    hi = min(bracket[1], candidate + max(0.0, quote - padded[0]) / vega_lower)
    return se, raw, padded, (lo, hi)


def asian_payoffs(histories):
    need(histories and all(len(h) == 2 and all(s > 0 for s in h) for h in histories),
         "Both positive contractual fixings required")
    return tuple(max(F(sum(h), 2) - 100, 0) for h in histories)


def state_prices(b, call_quote=F(2)):
    tail = call_quote / 20
    pi = (tail, b, 1 - 2 * tail - b, tail)
    need(all(x > 0 for x in pi), "Strict positive prices in all possible histories required")
    return pi


class Exam(HTMLParser):
    VOID = {"br", "hr", "img", "input", "meta", "link", "wbr", "col"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.ids, self.links, self.text = [], [], [], []
        self.points, self.solutions = {}, {}
        self.current_solution = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        need(tag != "h1", "Fragment must not add h1")
        if "id" in attrs:
            self.ids.append(attrs["id"])
        if "data-points" in attrs:
            need(tag == "li" and attrs.get("id") not in self.points,
                 "Scored prompt must be a unique semantic list item")
            self.points[attrs["id"]] = int(attrs["data-points"])
        if "data-solution-for" in attrs:
            key = attrs["data-solution-for"]
            need(tag == "li" and key not in self.solutions, "One solution per prompt required")
            self.current_solution = key
            self.solutions[key] = []
        if tag == "a":
            self.links.append(attrs.get("href", ""))
        if tag not in self.VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        need(self.stack and self.stack[-1] == tag, "Unbalanced HTML element " + tag)
        self.stack.pop()
        if tag == "li":
            self.current_solution = None

    def handle_data(self, data):
        self.text.append(data)
        if self.current_solution:
            self.solutions[self.current_solution].append(data)


def check():
    a = Audit()
    # Q1: reconstruct discounts and both independent cash exposures exactly.
    d1, d2 = solve(((100, 0), (50, 52)), (F(99), F("102.0096")))
    a.eq((d1, d2), (F(".99"), F("1.0098")), "Q1 bootstrap")
    a.eq(d1 / d2 - 1, F(-1, 51), "Q1 negative effective forward")
    a.eq(d1 - d2 * F(50, 51), 0, "Q1 zero-price dated forward exchange")
    liability = (F(40), F(60))
    exposures = (liability[0] * d1, 2 * liability[1] * d2)
    a.eq(exposures, (F("39.6"), F("121.176")), "Q1 key-date exposures")
    holdings = solve(((50 * d1, 100 * d1), (104 * d2, 0)), exposures)
    a.eq(holdings, (F(15, 13), F(-23, 130)), "Q1 signed matching holdings")
    x, y = holdings
    a.eq((50 * x + 100 * y, 52 * x), liability, "Q1 exact dated cash")
    a.eq(dot(liability, (d1, d2)), F("100.188"), "Q1 liability price")
    a.eq(x * F("102.0096") + y * 99, F("100.188"), "Q1 portfolio cost")
    for replacement in product((F(".7"), F(1), F("1.3")), repeat=2):
        a.eq(x * dot((50, 52), replacement) + y * 100 * replacement[0],
             dot(liability, replacement), "Q1 nonparallel replacement cash replication")
    for spread in (F(0), F(".01"), F(".02"), F(".04"), F(".2")):
        future = (F("1.02") + spread, F("1.02") - spread)
        a.eq(d1 * sum(future) / 2, d2, "Q1 unchanged initial curve under changed dispersion")
    u = d1 * (max(F("1.06") - 1, 0) + max(F(".98") - 1, 0)) / 2
    c = d1 * (F("1.02") - 1)
    a.eq((u, c, u - c), (F(".0297"), F(".0198"), F(".0099")), "Q1 convex rate claim")
    a.eq(d1 * dot((F("1.06"), F(".98")), (F(3, 4), F(1, 4))),
         F("1.0296"), "Q1 physical forecast is not calibrated pricing law")
    a.ok(y < 0, "Q1 exact hedge actually requires shorting rights")
    a.eq(1 - d1 / d2, F(1, 51), "Q1 added free storage changes no-arbitrage rights")
    a.interventions += ["Q1 independent zero-rate coordinates and replacement curves",
                        "Q1 fixed initial curve with changed future-rate dispersion/trading rights"]

    # Q2: exhaustive rating histories, single default event and actual payment dates.
    matrix = ((F(".8"), F(".15"), F(".05")),
              (F(".1"), F(".7"), F(".2")), (F(0), F(0), F(1)))
    discounts = (F(".96"), F(".92"), F(".88"))
    first, survival, cash, value = credit_value(matrix, discounts)
    a.eq(first, (F(".2"), F(".145")), "Q2 first defaults")
    a.eq(survival, F(".655"), "Q2 final survival")
    a.eq(sum(first) + survival, 1, "Q2 exhaustive default/survival partition")
    a.eq(cash, (0, F("73.5"), F("5.8")), "Q2 delayed recovery cash by date")
    a.eq(value, F("72.724"), "Q2 delayed recovery value")
    a.eq(credit_value(matrix, discounts, delay=0)[3], F("73.276"), "Q2 immediate recovery counterfactual")
    a.eq(credit_value(matrix, discounts, delay=0)[3] - value, F(".552"), "Q2 recovery delay cost")
    for recovery in (F(0), F(40), F(100)):
        delayed = credit_value(matrix, discounts, recovery)[3]
        immediate = credit_value(matrix, discounts, recovery, 0)[3]
        a.eq(immediate - delayed, recovery * dot(first, (discounts[0] - discounts[1],
                                                         discounts[1] - discounts[2])),
             "Q2 recovery cash relocation identity")
    a.eq(credit_value(matrix, (F(1), F(1), F(1)))[3],
         credit_value(matrix, (F(1), F(1), F(1)), delay=0)[3], "Q2 delay disappears at flat unit discount")
    changed = (matrix[0], (F(".1"), F(".6"), F(".3")), matrix[2])
    a.ok(credit_value(changed, discounts)[3] < value, "Q2 worsened migration lowers this recovery claim")
    a.ok(F(".345") > first[1], "Q2 cumulative absorption cannot be a repeated new default")
    ledger = margin_ledger(tuple(map(F, (50, 56, 47, 52))), F(-10))
    for key, expected in {"variation": (-60, 90, -50), "before": (40, 190, 140),
                          "after": (100, 190, 140), "contributions": (100, 60, 0, 0),
                          "release": 140, "debt": F("164.536575"),
                          "funded": F("-24.536575")}.items():
        a.eq(ledger[key], expected, "Q2 funded margin " + key)
    a.eq(ledger["release"] - sum(ledger["contributions"]), sum(ledger["variation"]),
         "Q2 returned principal versus nominal trading profit")
    a.eq(ledger["debt"] - sum(ledger["contributions"]), F("4.536575"), "Q2 funding interest")
    a.eq(ledger["contributions"][1] - 55, 5, "Q2 due-date liquidity gap")
    a.ok(ledger["contributions"][1] <= 60, "Q2 available cash intervention removes gap exactly")
    debt_by_cohort = sum(ledger["contributions"][t] * math.prod(
        (F("1.005"), F("1.01"), F("1.015"))[t:]) for t in range(4))
    a.eq(ledger["debt"], debt_by_cohort, "Q2 recursive debt equals separate borrowing cohorts")
    zero_funding = margin_ledger((50, 56, 47, 52), F(-10), factors=(F(1),) * 3)
    a.eq(zero_funding["funded"], -20, "Q2 remove dated borrowing cost")
    altered = margin_ledger((50, 47, 56, 52), F(-10))
    a.eq(sum(altered["variation"]), -20, "Q2 same endpoints preserve nominal variation")
    a.ok(altered["funded"] != ledger["funded"], "Q2 reordered fixings change dated funding")
    a.eq(margin_ledger((50, 56, 47, 52), F(-10), maintenance=F(40))["contributions"],
         (100, 0, 0, 0), "Q2 equality at maintenance does not trigger below-threshold call")
    a.interventions += ["Q2 first-default enumeration with delayed/immediate/zero recovery",
                        "Q2 migration deterioration and zero-rate delay boundary",
                        "Q2 reordered same-terminal futures path, threshold and funding interventions"]

    # Q3: independent finite payoff solving and negative lognormal moments.
    delta, bank, price, p = replication(F(80), F(64), F(96), F("1.02"), F(0), F(10))
    a.eq((delta, bank, price, p), (F(5, 16), F(-1000, 51), F(275, 51), F(".55")), "Q3 digital replication")
    for stock, payoff in ((64, 0), (96, 10)):
        a.eq(delta * stock + bank * F("1.02"), payoff, "Q3 exact state cash")
    a.eq(10 * p / F("1.02"), price, "Q3 state-price and replication agreement")
    for physical in (F(".1"), F(".9")):
        a.ok(10 * physical / F("1.02") != price, "Q3 physical frequencies do not replace state cash")
    a.eq(-F(".06") + F(".2") ** 2, F("-.02"), "Q3 inverse Ito physical drift")
    a.eq(-2 * (F(".03") - F(".01")) + 3 * F(".2") ** 2, F(".08"), "Q3 negative second moment exponent")
    initial = inverse_price(0, 100)
    a.near(initial, 99.0049833749168, "Q3 inverse claim initial price")
    a.near(-initial / 100, -.990049833749168, "Q3 initial signed delta")
    a.near(2 * initial, 198.0099667498336, "Q3 initial funded bank")
    # Integrate against the actual terminal density instead of reusing its moment formula.
    for exponent in (-2, -1, 1, 2):
        computed = integrate(lambda z: (100 * math.exp(.2 * z)) ** exponent * density(z), -10, 10)
        predicted = normal_power_moment(100, .02, .2, 1, exponent)
        a.near(computed, predicted, "Q3 independently integrated GBM moment", 2e-9)
    for r, q, sigma in ((.03, .01, .2), (-.02, .04, .3), (.01, -.01, .1)):
        k = q + sigma * sigma - 2 * r
        for t, s in ((0, 70), (.4, 100), (.9, 150)):
            v = inverse_price(t, s, r, q, sigma)
            vt, vs, vss = -k * v, -v / s, 2 * v / s**2
            a.near(vt + (r - q) * s * vs + sigma**2 * s*s * vss / 2 - r * v,
                   0, "Q3 PDE coefficient cancellation under rate/dividend interventions")
            for mu in (-.1, .06, .2):
                ito_drift = vt + mu * s * vs + sigma*sigma * s*s * vss / 2
                funded_drift = vs * (mu + q) * s + r * (v - vs * s)
                a.near(ito_drift, funded_drift, "Q3 self-financing independent of physical drift")
            step = s * 1e-4
            center = (inverse_price(t, s + step, r, q, sigma)
                      - inverse_price(t, s - step, r, q, sigma)) / (2 * step)
            second = (inverse_price(t, s + step, r, q, sigma) - 2*v
                      + inverse_price(t, s - step, r, q, sigma)) / step**2
            a.near(center, vs, "Q3 delta by centered perturbation", 3e-8)
            a.near(second, vss, "Q3 gamma by centered perturbation", 3e-8)
            a.near(inverse_price(1, s, r, q, sigma), 10000 / s, "Q3 terminal cash boundary")
    l2_integral = integrate(lambda t: .04 * math.exp(-.06*t)
                             * 1e8 * math.exp(-.02*(1-t))
                             * normal_power_moment(100, .02, .2, t, -2), 0, 1)
    a.near(l2_integral, 400 * math.exp(-.02) * math.expm1(.04) / .04,
           "Q3 finite discounted stochastic-integrand square norm", 2e-10)
    a.ok(l2_integral > 0 and math.isfinite(l2_integral), "Q3 L2 martingale admissibility evidence")
    a.ok(inverse_price(0, .0001) / (1 + .0001) > 1e7,
         "Q3 small-stock intervention exposes failed uniform linear-growth premise")
    a.interventions += ["Q3 physical-frequency changes versus finite replication",
                        "Q3 density-integrated negative moments and localized derivative/PDE checks",
                        "Q3 negative rates, dividends, physical drifts and small-stock growth boundary"]

    # Q4: supplied marks independently anchored through payoff/delta quadrature.
    for s, tau, mark, greek in ((100, 1, 7.364289723, -.436000430455),
                                (110, .5, 2.067544281, -.216606525638)):
        coarse, fine = put_by_integral(s, 100, tau, .02, .01, .2)
        a.near(coarse[0], fine[0], "Q4 payoff quadrature refinement", 4e-9)
        a.near(coarse[1], fine[1], "Q4 delta quadrature refinement", 1e-10)
        a.near(fine[0], mark, "Q4 supplied model mark", 7e-10)
        a.near(fine[1], greek, "Q4 supplied model delta", 2e-12)
    a.near(math.exp(.02*.5), 1.010050167084, "Q4 bank factor precision", 5e-13)
    a.near(math.exp(.01*.5), 1.005012520859, "Q4 dividend factor precision", 5e-13)
    funded, ideal = hedge_ledger(), hedge_ledger(F(0))
    anchors = {"initial_bank": 50.9643327685, "incoming_shares": -.438185891707,
               "incoming_bank": 51.476532828, "wealth": 3.276084740,
               "trade": 24.373730268, "fee": .024373730268,
               "new_bank": 27.078428830, "final_shares": -.217692270366,
               "final_bank": 27.350571564, "error": -2.241732769,
               "external_transfer": -1.208540459}
    for key, expected in anchors.items():
        a.near(float(funded[key]), expected, "Q4 funded ledger " + key, 2e-8)
    a.near(float(ideal["new_bank"]), 27.102802560, "Q4 costless reset bank", 2e-8)
    a.near(float(ideal["final_bank"]), 27.375190255, "Q4 costless final bank", 2e-8)
    a.near(float(ideal["error"]), -2.217114078, "Q4 costless terminal error", 2e-8)
    a.eq(ideal["error"] - funded["error"], funded["fee"] * F("1.010050167084"),
         "Q4 exact fee financing difference")
    a.eq(funded["wealth"] - funded["fee"], F("-.216606525638") * 110 + funded["new_bank"],
         "Q4 wealth conservation across actual reset")
    double_fee = hedge_ledger(F(".002"))
    a.eq(ideal["error"] - double_fee["error"], 2 * (ideal["error"] - funded["error"]),
         "Q4 proportional fee intervention")
    no_dividend = hedge_ledger(dividend_factor=F(1))
    a.ok(no_dividend["error"] != funded["error"], "Q4 negative shares still owe dividend compensation")
    a.ok(funded["external_transfer"] < 0, "Q4 hidden mark reset is external withdrawal")
    se, raw, padded, iv = inverse_interval(8.1, 4., 400, .008, 8., .3, 20., (.25, .35))
    for actual, expected in zip((se, *raw, *padded, *iv), (.2, 7.708, 8.492, 7.7, 8.5, .275, .315)):
        a.near(actual, expected, "Q4 sampling-bias-inversion arithmetic", 2e-14)
    a.near(4 / math.sqrt(800), .1414213562373095, "Q4 incorrect independence denominator")
    a.ok(4 / math.sqrt(800) < se, "Q4 treating pair means as members understates SE")
    # Whole-bracket vega lower bound is stress-tested on nonlinear monotone price maps.
    # For each true candidate price on the coverage event and curvature, construct an
    # exact root by independent bisection. Numerical bias sign is not presumed.
    roots = 0
    for value_at_candidate in (7.7, 7.9, 8., 8.1, 8.5):
        for slope in (20., 35., 70.):
            for curvature in (0., 80., 200.):
                def price_curve(s):
                    # Derivative slope + curvature*(s-.25) >=20 on [.25,.35].
                    return value_at_candidate + slope*(s-.3) + curvature/2*((s-.25)**2 - .05**2)
                low, high = .25, .35
                a.ok(price_curve(low) <= 8 <= price_curve(high), "Q4 root lies in supplied full bracket")
                for _ in range(60):
                    mid = (low + high) / 2
                    if price_curve(mid) < 8:
                        low = mid
                    else:
                        high = mid
                root = (low + high) / 2
                a.ok(iv[0] - 1e-14 <= root <= iv[1] + 1e-14, "Q4 asymmetric inverse set covers monotone root")
                roots += 1
    zero_bias = inverse_interval(8.1, 4., 400, 0., 8., .3, 20., (.25, .35))[-1]
    a.ok(zero_bias[0] > iv[0] and zero_bias[1] < iv[1], "Q4 deterministic allowance widens inverse interval")
    for mu, actual_var, pricing_var in product((F("-.1"), F(".06")),
                                              (F(".01"), F(".09")), (F(".04"),)):
        r, q, s, delta, gamma, mark, wealth = map(F, (".02", ".01", "100", "-.4", ".03", "7", "8"))
        pt = r*mark - (r-q)*s*delta - pricing_var*s*s*gamma/2
        actual_mark_drift = pt + mu*s*delta + actual_var*s*s*gamma/2
        funded_drift = delta*(mu+q)*s + r*(wealth-delta*s)
        discounted_error_drift = funded_drift - actual_mark_drift - r*(wealth-mark)
        a.eq(discounted_error_drift, gamma*s*s*(pricing_var-actual_var)/2,
             "Q4 exact funded volatility-mismatch cancellation")
    a.ok(dot((F(1), F(10)), (F(".03"), F("-.02"))) < 0
         and F(".03") - F(".02") > 0, "Q4 cash-gamma weights reverse positive unweighted average")
    a.interventions += ["Q4 direct Gaussian put/delta integration independent of chapter formula",
                        "Q4 fee scaling, signed dividend compensation and retained-cash conservation",
                        "Q4 finite-vega inverse sets under nonlinear monotone prices and numerical allowance",
                        "Q4 exact continuous funded mismatch and changing cash-gamma weights"]

    # Q5: exact state constraints and independent finite payoff-envelope vertices.
    histories = ((80, 80), (80, 100), (120, 100), (120, 120))
    asian = asian_payoffs(histories)
    call = tuple(max(h[1] - 100, 0) for h in histories)
    stock = tuple(h[1] for h in histories)
    bank_payoff = (1, 1, 1, 1)
    a.eq((asian, call), ((0, 0, 10, 20), (0, 0, 0, 20)), "Q5 distinct contractual payoffs")
    for b in (F(".001"), F(".2"), F(".4"), F(".799")):
        pi = state_prices(b)
        a.eq((dot(pi, bank_payoff), dot(pi, stock), dot(pi, call)), (1, 100, 2), "Q5 every calibrated state-price vector")
        a.eq(dot(pi, asian), 10 - 10*b, "Q5 complete Asian price family")
    payoff_rows = tuple(zip(bank_payoff, stock, call))
    # Enumerate all three-state active payoff constraints, reject singular history twins,
    # and retain the resulting statewise feasible sub/superhedges.
    sub_costs, super_costs = [], []
    for active in combinations(range(4), 3):
        try:
            holdings = solve(tuple(payoff_rows[i] for i in active), tuple(asian[i] for i in active))
        except ValueError:
            continue
        values = tuple(dot(row, holdings) for row in payoff_rows)
        cost = dot((1, 100, 2), holdings)
        if all(v <= x for v, x in zip(values, asian)):
            sub_costs.append(cost)
        if all(v >= x for v, x in zip(values, asian)):
            super_costs.append(cost)
    a.eq((max(sub_costs), min(super_costs)), (2, 10), "Q5 independent payoff-envelope vertex costs")
    lower, upper = (F(0), F(0), F(1)), (F(-40), F(1, 2), F(0))
    lower_payoff = tuple(dot(row, lower) for row in payoff_rows)
    upper_payoff = tuple(dot(row, upper) for row in payoff_rows)
    a.eq(lower_payoff, (0, 0, 0, 20), "Q5 attained subhedge payoffs")
    a.eq(upper_payoff, (0, 10, 10, 20), "Q5 attained superhedge payoffs")
    a.eq(tuple(x-y for x, y in zip(asian, lower_payoff)), (0, 0, 10, 0), "Q5 lower endpoint arbitrage cash")
    a.eq(tuple(x-y for x, y in zip(upper_payoff, asian)), (0, 10, 0, 0), "Q5 upper endpoint arbitrage cash")
    for interior in (F("2.001"), F(4), F(6), F("9.999")):
        b = (10-interior)/10
        a.eq(dot(state_prices(b), asian), interior, "Q5 every interior price has positive extension")
    for quote in (F(1), F(2), F(4)):
        tail = quote / 20
        midmass = 1 - 2*tail
        for fraction in (F(1, 4), F(3, 4)):
            pi = state_prices(midmass*fraction, quote)
            a.eq(dot(pi, call), quote, "Q5 extra vanilla quote fixes tail mass")
            a.eq(dot(pi, stock), 100, "Q5 call-quote intervention retains stock price")
            a.ok(quote < dot(pi, asian) < 10, "Q5 extra vanilla does not resolve missing fixing")
    at_mid = state_prices(F(".4"))
    a.eq((dot(at_mid, asian), dot(at_mid, call)), (6, 2), "Q5 Asian versus implemented price")
    a.eq(dot(at_mid, call) - dot(at_mid, asian), -4, "Q5 signed implementation error")
    a.eq(10 - 2, 8, "Q5 admissible range width")
    a.eq((all(x == y for x, y in zip(asian, call)), 8 <= 1), (False, False), "Q5 both release gates fail")
    a.eq((all(x == y for x, y in zip(asian, asian)), 8 <= 1), (True, False), "Q5 code repair alone does not identify price")
    a.interventions += ["Q5 extra vanilla quotes and history-twin null direction",
                        "Q5 exact hedge-envelope vertices, endpoint arbitrages and interior extensions",
                        "Q5 corrected contract code with unresolved model-range release gate"]

    # Rejection checks exercise domains used by the economic reconstructions.
    for operation, label in (
        (lambda: solve(((1, 1), (2, 2)), (1, 2)), "singular cash spanning"),
        (lambda: dot((1,), (1, 2)), "cash-date mismatch"),
        (lambda: transition_paths(((F(1), F(1)), (F(0), F(1))), 0, 2), "transition mass"),
        (lambda: transition_paths(matrix, 1, 10), "unbounded history enumeration"),
        (lambda: credit_value(matrix, (F(0), F(1), F(1))), "zero discount"),
        (lambda: credit_value(matrix, discounts, F(-1)), "negative recovery"),
        (lambda: credit_value(matrix, discounts, delay=2), "unspecified settlement date"),
        (lambda: margin_ledger((50, 52), -10), "missing variation dates"),
        (lambda: margin_ledger((50, 56, 47, 52), -10, maintenance=F(101)), "maintenance exceeds restoration"),
        (lambda: margin_ledger((50, 56, 47, 52), -10, factors=(F(1), F(0), F(1))), "nonpositive debt factor"),
        (lambda: replication(F(80), F(64), F(96), F("1.2"), F(0), F(10)), "zero state price endpoint"),
        (lambda: replication(F(80), F(64), F(64), F(1), F(0), F(10)), "collapsed finite states"),
        (lambda: inverse_price(0, 0), "inverse payoff at zero stock"),
        (lambda: inverse_price(1.1, 100), "past terminal claim time"),
        (lambda: normal_power_moment(100, .02, .2, 1, float("nan")), "nonfinite exponent"),
        (lambda: put_by_integral(100, 100, 0, .02, .01, .2), "terminal derivative interior formula"),
        (lambda: hedge_ledger(F("-.01")), "negative transaction fee"),
        (lambda: inverse_interval(8.1, 4., 1, .008, 8., .3, 20., (.25, .35)), "sample variance needs two pairs"),
        (lambda: inverse_interval(8.1, 4., 400, .008, 8., .3, 0., (.25, .35)), "zero inverse vega bound"),
        (lambda: inverse_interval(8.1, 4., 400, -.008, 8., .3, 20., (.25, .35)), "negative bias allowance"),
        (lambda: inverse_interval(8.1, 4., 400, .008, 8., .4, 20., (.25, .35)), "candidate outside derivative bracket"),
        (lambda: inverse_interval(8.1, float("inf"), 400, .008, 8., .3, 20., (.25, .35)), "nonfinite sampling evidence"),
        (lambda: asian_payoffs(((100,),)), "missing contractual fixing"),
        (lambda: state_prices(F(0)), "lower positive-state domain endpoint"),
        (lambda: state_prices(F(".8")), "upper positive-state domain endpoint"),
    ):
        a.rejects(operation, label)

    # Readable structure, exact scoring, scope records and three nonself hashes.
    parser = Exam()
    parser.feed((ROOT / HTML).read_text())
    parser.close()
    a.eq(parser.stack, [], "balanced complete HTML")
    a.eq(len(parser.ids), len(set(parser.ids)), "unique assessment IDs")
    a.eq(parser.points, POINTS, "all sixteen exact prompt scores")
    a.eq(set(parser.solutions), set(POINTS), "one complete solution per scored prompt")
    a.eq(sum(parser.points.values()), 100, "total score")
    for q in range(1, 6):
        a.eq(sum(v for k, v in parser.points.items() if k.startswith(f"v10-b-q{q}")),
             20, f"D{q} essential-domain points")
    for prompt, fragments in parser.solutions.items():
        solution = "".join(fragments)
        a.ok(len(solution.split()) >= 40, "complete worked solution " + prompt)
        a.ok(f"{POINTS[prompt]} points:" in solution, "explicit subpart scoring " + prompt)
    a.ok(all(i in ("form-b", "solutions-b") or i.startswith("v10-b-") for i in parser.ids),
         "integration-safe assessment identifiers")
    for chapter in range(1, 13):
        a.ok(f"v10-c{chapter:02}.html" in parser.links, "taught outcome route " + str(chapter))
    cited = {href.split("#", 1)[1] for href in parser.links if href.startswith("sources.html#")}
    a.eq(cited, SOURCE_IDS, "exact cited primary-method routes")
    source_record = json.loads((ROOT / SOURCES).read_text())
    a.eq(source_record["proposals"], [], "no new unreviewed source proposals")
    a.eq({s["id"] for s in source_record["reused_sources"]}, SOURCE_IDS, "source reuse scope")
    for source in source_record["reused_sources"]:
        a.ok(source["url"].startswith("https://") and source["reused_body_scope"]
             and source["checked"] == "2026-10-09", "dated source provenance " + source["id"])
    review = json.loads((ROOT / AUTHOR).read_text())
    a.eq(set(review["payload_sha256"]), {HTML, SOURCES, CHECKER}, "three nonself author payload bindings")
    for path, digest in review["payload_sha256"].items():
        a.eq(hashlib.sha256((ROOT / path).read_bytes()).hexdigest(), digest, "frozen author payload " + path)
    a.eq(set(review["chapter_coverage"]), {f"v10-c{c:02}" for c in range(1, 13)}, "all twelve assessed outcomes")
    for chapter, prompts in review["chapter_coverage"].items():
        a.ok(prompts and all(p in POINTS for p in prompts), "scored evidence mapping " + chapter)
    a.eq({r["part"] for r in review["part_review"]}, set(POINTS), "exact-prompt author audit coverage")
    for part in review["part_review"]:
        a.eq(sum(part["credit_allocation"]), POINTS[part["part"]], "subpart rubric allocation " + part["part"])
    summary = {"assessment": "v10-exam-b", "status": "pass", "comparisons": a.comparisons,
               "domain_rejections": a.rejections, "scored_prompts": len(POINTS), "points": 100,
               "domains": {f"D{i}": 20 for i in range(1, 6)},
               "independent_rating_histories": 9, "nonlinear_inverse_cases": roots,
               "interventions": a.interventions, "author_payload_hashes_checked": 3,
               "limits": "Machine-assisted author audit, not peer acceptance or human academic certification; approximate CLT coverage is not established by deterministic checks."}
    json.dumps(summary, allow_nan=False)
    return summary


if __name__ == "__main__":
    print(json.dumps(check(), indent=2, allow_nan=False))
