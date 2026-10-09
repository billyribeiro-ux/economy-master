"""Independent exact reconstructions of the original Volume 9 Form B.

No author model supplies these answers. This file reconstructs dated cash,
sample moments, finite-state payoffs and every allowed integer repair from
the question inputs. check() is quiet and returns strict JSON. Structural
comparisons count alongside arithmetic; they are not separate derivations.
Run from any directory with Python 3; only the standard library is used.
"""
from collections import Counter
from fractions import Fraction as F
from html.parser import HTMLParser
import json
import math
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
PARTS = [f"v09-b-q{q}{part}" for q in range(1, 6) for part in "abcd"]
SOURCE_IDS = [
    "v09-c01-gips-methods", "v09-c02-mit-portfolio", "v09-c03-shrinkage",
    "v09-c05-princeton-pricing", "v09-c04-fama-french-tests",
    "v09-c06-french-construction", "v09-c08-sharpe-ratio",
    "v09-c08-carhart-persistence", "v09-c10-cme-mtm",
    "v09-c11-hasbrouck", "v09-c12-cfa-ips",
]


class Verify:
    def __init__(self):
        self.comparisons = 0
        self.domain_rejections = 0
        self.groups = []

    def equal(self, actual, expected, label):
        self.comparisons += 1
        if actual != expected:
            raise AssertionError(f"{label}: {actual!r} != {expected!r}")

    def true(self, condition, label):
        self.equal(bool(condition), True, label)

    def near(self, actual, expected, label, tolerance=1e-12):
        self.true(math.isfinite(actual) and abs(actual - expected) <= tolerance,
                  f"{label}: {actual!r} versus {expected!r}")

    def rejects(self, operation, label):
        try:
            operation()
        except ValueError:
            self.domain_rejections += 1
            self.true(True, label)
        else:
            raise AssertionError(f"Expected economic-domain rejection: {label}")


def dot(x, y):
    return sum((a * b for a, b in zip(x, y)), F(0))


def mean(x, probabilities):
    return dot(x, probabilities)


def cov(x, y, probabilities):
    mx, my = mean(x, probabilities), mean(y, probabilities)
    return sum(p * (a - mx) * (b - my)
               for a, b, p in zip(x, y, probabilities))


def solve(matrix, rhs):
    """Exact elimination, used to reconstruct prices and regression slopes."""
    n = len(rhs)
    if len(matrix) != n or any(len(row) != n for row in matrix):
        raise ValueError("Square system required")
    a = [[F(x) for x in row] + [F(y)] for row, y in zip(matrix, rhs)]
    for j in range(n):
        pivot = next((i for i in range(j, n) if a[i][j]), None)
        if pivot is None:
            raise ValueError("Singular system")
        a[j], a[pivot] = a[pivot], a[j]
        scale = a[j][j]
        a[j] = [x / scale for x in a[j]]
        for i in range(n):
            if i != j:
                scale = a[i][j]
                a[i] = [x - scale * y for x, y in zip(a[i], a[j])]
    return [row[-1] for row in a]


def sample_covariance(rows):
    if len(rows) < 2 or not rows[0] or any(len(r) != len(rows[0]) for r in rows):
        raise ValueError("At least two complete common-date rows are required")
    n, k = len(rows), len(rows[0])
    means = [sum(row[j] for row in rows) / n for j in range(k)]
    # Raw cross products provide an independent path from the printed centered sums.
    matrix = [[(sum(row[i] * row[j] for row in rows) - n * means[i] * means[j])
               / (n - 1) for j in range(k)] for i in range(k)]
    return means, matrix


def portfolio_variance(matrix, w):
    weights = [w, 1 - w]
    return sum(weights[i] * matrix[i][j] * weights[j]
               for i in range(2) for j in range(2))


def capped_gmv(matrix, cap):
    a, c = matrix[0]
    d, b = matrix[1]
    if c != d or a <= 0 or a * b - c * c <= 0 or not 0 <= cap <= 1:
        raise ValueError("This bounded two-fund problem requires SPD S and 0<=cap<=1")
    raw = (b - c) / (a + b - 2 * c)
    choice = min(cap, max(F(0), raw))
    return raw, choice, portfolio_variance(matrix, choice)


def price(q, payoff):
    if len(q) != len(payoff) or not all(x > 0 for x in q):
        raise ValueError("Strictly positive prices in every possible state required")
    return dot(q, payoff)


class Exam(HTMLParser):
    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input",
            "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.ids = []
        self.parts = {}
        self.answers = {}
        self.answer = None
        self.in_solutions = False
        self.solution_sections = 0
        self.links = []
        self.text = []
        self.headings = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "h1":
            raise AssertionError("Assessment fragment must not duplicate h1")
        if "id" in attrs:
            self.ids.append(attrs["id"])
        if tag in ("h2", "h3"):
            self.headings.append((tag, attrs.get("id")))
        if tag == "details" and "solutions" in attrs.get("class", "").split():
            self.in_solutions = True
            self.solution_sections += 1
        if "data-points" in attrs:
            key = attrs.get("id")
            if tag != "li" or self.in_solutions or key in self.parts or "ol" not in self.stack:
                raise AssertionError("Scored prompts must be unique ordered items before solutions")
            self.parts[key] = int(attrs["data-points"])
        if "data-solution-for" in attrs:
            key = attrs["data-solution-for"]
            if tag != "li" or not self.in_solutions or key in self.answers or "ol" not in self.stack:
                raise AssertionError("Mapped solutions must be unique ordered items inside solutions")
            self.answer = key
            self.answers[key] = []
        if tag == "a":
            self.links.append(attrs.get("href", ""))
        if tag == "th" and attrs.get("scope") not in ("row", "col"):
            raise AssertionError("Table headers require scope")
        if tag not in self.VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if not self.stack or self.stack.pop() != tag:
            raise AssertionError(f"Unbalanced HTML closing tag: {tag}")
        if tag == "li":
            self.answer = None
        if tag == "details":
            self.in_solutions = False

    def handle_data(self, data):
        self.text.append(data)
        if self.answer is not None:
            self.answers[self.answer].append(data)


def structure(v):
    html = (ROOT / "content/assessments/parts/v09-exam-b.html").read_text()
    exam = Exam()
    exam.feed(html)
    exam.close()
    v.equal(exam.stack, [], "balanced fragment")
    v.equal(len(exam.ids), len(set(exam.ids)), "unique anchors")
    v.equal(list(exam.parts), PARTS, "twenty ordered scored prompts")
    v.equal(list(exam.answers), PARTS, "twenty uniquely mapped solutions")
    v.equal(exam.solution_sections, 1, "one semantic solution section")
    v.true(("h2", "form-b") in exam.headings, "form heading")
    v.true(("h2", "solutions-b") in exam.headings, "solution heading")
    for q in range(1, 6):
        v.true(f"v09-b-case{q}" in exam.ids, f"case {q} anchor")
        v.equal(sum(exam.parts[f"v09-b-q{q}{part}"] for part in "abcd"), 20,
                f"domain {q} points")
    for key in PARTS:
        v.equal(exam.parts[key], 5, f"{key} maximum")
        answer = "".join(exam.answers[key])
        v.equal(answer.count("Credit:"), 1, f"{key} explicit credit paragraph")
        credit = answer.split("Credit:")[1]
        scores = [int(x) for x in re.findall(r"\b([1-5]) points?\b", credit)]
        v.equal(sum(scores), 5, f"{key} rubric closes")
        v.true(len(answer.split()) >= 65, f"{key} substantive complete solution")
    text = " ".join(exam.text)
    for boundary in ("240 minutes", "nonprogrammable", "85/100", "15/20",
                     "critical", "Carry forward", "transfer", "teach-back"):
        v.true(boundary in text, f"administration: {boundary}")
    v.equal({link for link in exam.links if re.fullmatch(r"v09-c\d\d.html", link)},
            {f"v09-c{i:02d}.html" for i in range(1, 13)}, "all twelve method routes")
    v.equal(Counter(link.split("#", 1)[1] for link in exam.links
                    if link.startswith("sources.html#")), Counter(SOURCE_IDS),
            "eleven exact scoped source links")
    v.groups.append("structure, twenty five-point rubrics and complete coverage")
    return len(re.findall(r"\b[\w’'-]+\b", text))


def returns_and_sample(v):
    r1, r2 = F(240, 200) - 1, F(110, 120) - 1
    v.equal((r1, r2), (F(1, 5), -F(1, 12)), "flow-correct period returns")
    gross = (1 + r1) * (1 + r2)
    v.equal(gross - 1, F(1, 10), "two-year TWR")
    v.near(math.sqrt(float(gross)) - 1, 0.04880884817015163, "annualized TWR")
    for x in (F(11, 10), -F(1, 2)):
        v.equal(200 * x * x - 120 * x - 110, 0, "both algebraic IRR roots")
    v.true(F(11, 10) > 0 and -F(1, 2) <= 0, "only positive gross root admissible")
    v.equal(-200 + F(120) / F(11, 10) + F(110) / F(11, 10) ** 2, 0,
            "dated investor NPV at annual IRR")
    v.equal((200 * F(11, 10) - 120) * F(11, 10) - 110, 0,
            "investor IRR forward cash closure")
    rows = [[F(a, 100), F(b, 100)] for a, b in [(-2, -1), (2, 7), (4, 1), (8, 9)]]
    means, matrix = sample_covariance(rows)
    v.equal(means, [F(3, 100), F(4, 100)], "sample means")
    v.equal(matrix, [[F(13, 7500), F(11, 7500)], [F(11, 7500), F(17, 7500)]],
            "raw-product covariance")
    for i in range(2):
        for j in range(2):
            centered = sum((row[i] - means[i]) * (row[j] - means[j]) for row in rows) / 3
            v.equal(matrix[i][j], centered, f"centered covariance {i},{j}")
    det = matrix[0][0] * matrix[1][1] - matrix[0][1] ** 2
    v.equal(det, F(100, 7500 ** 2), "positive-definiteness determinant")
    v.true(matrix[0][0] > 0 and det > 0, "strictly positive definite fixture")
    for z in ([F(1), F(-2)], [F(-3, 2), F(1)], [F(0), F(0)]):
        quadratic = sum(z[i] * matrix[i][j] * z[j] for i in range(2) for j in range(2))
        gram = sum(dot(z, [row[j] - means[j] for j in range(2)]) ** 2 for row in rows) / 3
        v.equal(quadratic, gram, "sample Gram identity witness")
        v.true(gram >= 0, "nonnegative sample quadratic form")
    v.rejects(lambda: sample_covariance(rows[:1]), "n-1 covariance needs n>=2")
    v.rejects(lambda: sample_covariance([rows[0], rows[1][:1]]), "common-observation domain")
    v.groups.append("dated investor cash, horizon and independent sample moments")
    return matrix


def allocation(v, matrix):
    cap = F(2, 3)
    raw, w, risk = capped_gmv(matrix, cap)
    v.equal((raw, w, 1 - w, risk), (F(3, 4), cap, F(1, 3), F(113, 67500)),
            "capped raw GMV")
    for z in (F(0), cap, F(3, 4), F(1)):
        v.equal(portfolio_variance(matrix, z), (8 * z * z - 12 * z + 17) / 7500,
                "matrix versus raw variance polynomial")
    v.true((16 * cap - 12) / 7500 < 0 and F(16, 7500) > 0,
           "raw boundary derivative and convexity")
    shrunk = [[matrix[i][j] * (1 if i == j else F(1, 2)) for j in range(2)] for i in range(2)]
    raw2, w2, risk2 = capped_gmv(shrunk, cap)
    v.equal((raw2, w2, 1 - w2, risk2),
            (F(23, 38), F(23, 38), F(15, 38), F(763, 570000)), "shrunk interior GMV")
    v.true(0 < w2 < cap, "shrunk cap slack")
    for z in (F(0), w2, cap, F(1)):
        v.equal(portfolio_variance(shrunk, z), (19 * z * z - 23 * z + 17) / 7500,
                "matrix versus shrunk variance polynomial")
    v.true(portfolio_variance(matrix, w2) > portfolio_variance(matrix, w),
           "under a common raw law the raw constrained optimum has lower risk")
    v.true(portfolio_variance(shrunk, w2) < portfolio_variance(shrunk, w),
           "under the shrunk law its own optimum has lower risk")
    v.rejects(lambda: capped_gmv([[F(1), F(2)], [F(2), F(1)]], cap),
              "indefinite covariance cannot support the claimed convex minimization")
    v.rejects(lambda: capped_gmv(matrix, F(-1, 10)), "empty nonnegative capped-weight domain")
    v.groups.append("two covariance laws, constrained minima and estimation-sensitive ranking")


def pricing_and_capm(v):
    bond, stock, insurance = [F(1)] * 3, list(map(F, (1, 2, 4))), list(map(F, (2, 0, 3)))
    p_b, p_s = F(19, 20), F(41, 20)
    lower_t, upper_t = F(3, 40), F(11, 30)
    for t in (F(1, 10), F(1, 5), F(1, 3)):
        q = [2 * t - F(3, 20), F(11, 10) - 3 * t, t]
        p_x = price(q, insurance)
        v.equal((price(q, bond), price(q, stock)), (p_b, p_s), "two original price equations")
        v.equal(p_x, 7 * t - F(3, 10), "insurance price along positive family")
        v.equal(solve([bond, stock, insurance], [p_b, p_s, p_x]), q,
                "independent complete extension solves the family")
        v.true(lower_t < t < upper_t, "interior family parameter")
        v.equal(sum(q), p_b, "state prices sum to discount factor, not one")
    lo, hi = 7 * lower_t - F(3, 10), 7 * upper_t - F(3, 10)
    v.equal((lo, hi), (F(9, 40), F(34, 15)), "strict insurance endpoints")
    for p_x in (lo, hi, F(12, 5)):
        q = solve([bond, stock, insurance], [p_b, p_s, p_x])
        v.rejects(lambda q=q: price(q, bond), "endpoint or over-upper quote lacks positive extension")
    low_hedge = [F(3, 2) * x - 3 for x in stock]
    high_hedge = [x / 3 + F(5, 3) for x in stock]
    v.equal(low_hedge, [-F(3, 2), F(0), F(3)], "subhedge state payoffs")
    v.equal(high_hedge, [F(2), F(7, 3), F(3)], "superhedge state payoffs")
    v.equal(F(3, 2) * p_s - 3 * p_b, lo, "subhedge price")
    v.equal(p_s / 3 + F(5, 3) * p_b, hi, "superhedge price")
    v.equal([x - l for x, l in zip(insurance, low_hedge)], [F(7, 2), F(0), F(0)],
            "lower endpoint free payoff")
    v.equal([u - x for u, x in zip(high_hedge, insurance)], [F(0), F(7, 3), F(0)],
            "upper endpoint free payoff")
    surplus = F(12, 5) - hi
    extra_bonds = surplus / p_b
    total_bonds = F(5, 3) + extra_bonds
    v.equal((surplus, extra_bonds, total_bonds), (F(2, 15), F(8, 57), F(103, 57)),
            "arbitrage surplus reinvestment")
    v.equal(-F(12, 5) + p_s / 3 + total_bonds * p_b, 0, "zero funded initial budget")
    payoff = [-x + s / 3 + total_bonds for x, s in zip(insurance, stock)]
    v.equal(payoff, [F(8, 57), F(47, 19), F(8, 57)], "three strictly positive arbitrage receipts")
    v.true(all(x > 0 for x in payoff), "funded statewise, not merely expected, dominance")
    beta = F(6, 100) / F(4, 100)
    alpha = F(9, 100) - F(2, 100) - beta * (F(6, 100) - F(2, 100))
    v.equal((beta, alpha), (F(3, 2), F(1, 100)), "proxy beta and intercept")
    # An independent exact moment witness verifies the market-clearing multiplication.
    sigma = [[F(4, 100), F(1, 100)], [F(1, 100), F(9, 100)]]
    market_w, lam = [F(2, 5), F(3, 5)], F(3)
    covariance_with_market = [dot(row, market_w) for row in sigma]
    premia = [lam * c for c in covariance_with_market]
    market_premium = dot(market_w, premia)
    market_variance = dot(market_w, covariance_with_market)
    v.equal(market_premium, lam * market_variance, "aggregate CAPM implication")
    for premium, covariance in zip(premia, covariance_with_market):
        v.equal(premium, covariance / market_variance * market_premium, "true-market beta line")
    v.groups.append("incomplete-market interval, endpoint arbitrage and CAPM proxy discipline")


def factors_fees_evidence(v):
    # An original finite population realizes every supplied moment exactly.
    rows = []
    for sign_m in (-1, 1):
        for residual_z, p_z in ((-F(3, 100), F(3, 8)), (F(0), F(1, 4)), (F(3, 100), F(3, 8))):
            for sign_e in (-1, 1):
                m = F(4, 1000) + F(2, 100) * sign_m
                z = F(6, 1000) + F(15, 1000) * sign_m + residual_z
                e = F(1, 100) * sign_e
                y = F(1, 1000) + F(3, 5) * m + F(2, 5) * z + e
                rows.append((p_z / 4, m, z, e, y))
    p, m, z, e, y = map(list, zip(*rows))
    v.equal(sum(p), 1, "synthetic factor population probabilities")
    v.equal((mean(m, p), mean(z, p), mean(e, p)), (F(4, 1000), F(6, 1000), F(0)),
            "factor and residual means")
    v.equal((cov(m, m, p), cov(z, z, p), cov(m, z, p)),
            (F(4, 10000), F(9, 10000), F(3, 10000)), "factor covariance from states")
    v.equal((cov(e, e, p), cov(e, m, p), cov(e, z, p)), (F(1, 10000), F(0), F(0)),
            "orthogonal nonzero residual")
    beta = cov(y, m, p) / cov(m, m, p)
    intercept = mean(y, p) - beta * mean(m, p)
    full = solve([[cov(m, m, p), cov(m, z, p)], [cov(m, z, p), cov(z, z, p)]],
                 [cov(m, y, p), cov(z, y, p)])
    full_alpha = mean(y, p) - full[0] * mean(m, p) - full[1] * mean(z, p)
    v.equal((beta, mean(y, p), intercept), (F(9, 10), F(58, 10000), F(22, 10000)),
            "one-factor population projection")
    v.equal((full, full_alpha), ([F(3, 5), F(2, 5)], F(1, 1000)),
            "two-factor regression reconstructed from normal equations")
    fee = F(2, 1000)
    net = [x - fee for x in y]
    benchmark = [F(3, 5) * a + F(2, 5) * b for a, b in zip(m, z)]
    active = [a - b for a, b in zip(net, benchmark)]
    v.equal((full_alpha - fee, intercept - fee), (-F(1, 1000), F(2, 10000)), "net intercepts")
    v.equal((mean(active, p), cov(active, active, p)), (-F(1, 1000), F(1, 10000)),
            "benchmark-active moments from individual state returns")
    v.near(math.sqrt(float(cov(active, active, p))), 0.01, "monthly tracking error")
    v.equal(mean(active, p) / F(1, 100), -F(1, 10), "monthly information ratio")
    v.equal(cov(net, m, p), cov(y, m, p), "fixed fee changes no covariance slope")
    v.true((1, 2) < (3, 20), "January trade precedes March information release")
    # A split of the disclosed 0.4% spread closes both actual security legs.
    proceeds_long, cover_short = F(100) * F(1012, 1000), F(100) * F(1008, 1000)
    gross_profit = proceeds_long - cover_short
    returned_collateral = 20 + proceeds_long - cover_short - F(15, 100) - F(35, 100)
    v.equal(gross_profit, F(2, 5), "long and short closure gross cash")
    v.equal((returned_collateral - 20, returned_collateral, returned_collateral / 20 - 1),
            (-F(1, 10), F(199, 10), -F(1, 200)), "funded collateral loss and return")
    end = list(map(F, (110, 105, 0)))
    cohort = sum(end) / 300 - 1
    survivor = sum(end[:2]) / 200 - 1
    v.equal((sum(end), cohort, survivor), (F(215), -F(17, 60), F(3, 40)),
            "full and future-selected cohort returns")
    v.equal(sum((x / 100 - 1) / 3 for x in end), cohort, "equal-initial-capital cohort return")
    v.true(end[0] > end[1] > end[2], "choosing U after outcomes is an outcome-based selection")
    v.groups.append("finite factor population, omitted risk, net benchmark and evaluation cash")


def endowment_and_liquidity(v):
    p, z, h = [F(1, 2)] * 2, [F(3, 10), -F(1, 10)], list(map(F, (34, 26)))
    v.equal((mean(z, p), cov(z, z, p), mean(h, p), cov(h, h, p), cov(z, h, p)),
            (F(1, 10), F(1, 25), F(30), F(16), F(4, 5)), "endowment joint moments")

    def terminal(x, fee_rate=F(0)):
        fee = fee_rate * abs(x - 45)
        cash = 60 - x - fee
        return [cash - 22 + x * (1 + a) + b for a, b in zip(z, h)]

    def score(x, fee_rate=F(0)):
        t = terminal(x, fee_rate)
        return mean(t, p) - F(1, 40) * cov(t, t, p)

    for x in (F(0), F(30), F(40), F(45), F(60)):
        t = terminal(x)
        v.equal(mean(t, p), 68 + x / 10, "state ledger mean versus formula")
        v.equal(cov(t, t, p), x * x / 25 + F(8, 5) * x + 16, "state ledger total variance")
        v.equal(score(x), F(338, 5) + F(3, 50) * x - x * x / 1000, "state objective polynomial")
    # Recover the concave quadratic from state-accounting values at 0,1,2.
    constant = score(F(0))
    quad = (score(F(2)) - 2 * score(F(1)) + constant) / 2
    linear = score(F(1)) - constant - quad
    v.equal((quad, linear, -linear / (2 * quad)), (-F(1, 1000), F(3, 50), F(30)),
            "frictionless unique optimum from independently derived quadratic")
    v.equal(mean(z, p) / (F(1, 20) * cov(z, z, p)), 50, "ignoring endowment hedge changes demand")
    cost = F(1, 50)
    sale_optimum = -(linear + cost) / (2 * quad)
    v.equal(sale_optimum, 40, "piecewise cost-aware optimum")
    v.true(linear + 2 * quad * 45 - cost < 0, "buy-region objective decreases from kink")
    max_cash_feasible = F(609, 10) / F(102, 100)
    v.equal(max_cash_feasible, F(1015, 17), "nonnegative-cash upper trading boundary")
    for x in (F(0), F(30), F(45), max_cash_feasible):
        v.true(score(F(40), cost) >= score(x, cost), "piecewise candidate global comparison")
    fee = cost * abs(40 - 45)
    cash = 60 - 40 - fee
    v.equal((fee, cash, score(F(40), cost), score(F(30), cost)),
            (F(1, 10), F(199, 10), F(683, 10), F(341, 5)), "fee and relaxed objective closure")
    v.equal(22 - cash, F(21, 10), "relaxed call shortfall")
    upper = (60 - cost * 45 - 22) / (1 - cost)
    sale = 45 - upper
    fee = cost * sale
    cash = 60 - upper - fee
    v.equal((upper, sale, fee, cash), (F(265, 7), F(50, 7), F(1, 7), F(22)),
            "funded boundary with fee paid in cash")
    v.equal(upper + fee + cash, 60, "initial resource balance")
    v.equal(cash - 22, 0, "interim call cash closure")
    v.true(linear + cost + 2 * quad * upper > 0, "funded score increasing at upper boundary")
    v.true(60 - (upper + F(1, 100)) - cost * abs(upper + F(1, 100) - 45) < 22,
           "even small upward perturbation fails actual funding")
    v.equal(terminal(upper, cost), [F(1165, 14), F(841, 14)], "funded terminal receipts by state")
    variation = 2 * (40 - 50)
    after_variation = 22 + variation
    required = 22 + 5
    gap = required - after_variation
    v.equal((variation, after_variation, required, gap), (-20, 2, 27, 25), "joint variation/call/margin stress")
    v.equal(after_variation + gap - 22, 5, "hypothetical funded reserve closes once, not twice")
    v.true(after_variation < 22 and after_variation - 22 < 5, "unfunded proposal fails both deadlines")
    v.groups.append("state-dependent endowment, proportional fee and binding dated cash")


def execution_and_policy(v):
    states = [(F(1, 2), 20, F(22)), (F(1, 2), 80, F(18))]
    pfill = sum(p * F(q, 100) for p, q, _ in states)
    up_given_fill = states[0][0] * F(states[0][1], 100) / pfill
    conditional_price = sum(p * F(q, 100) * mark for p, q, mark in states) / pfill
    conditional_profit = conditional_price - F(199, 10) - F(1, 50)
    v.equal((pfill, up_given_fill, conditional_price, conditional_profit),
            (F(1, 2), F(1, 5), F(94, 5), -F(28, 25)), "selected passive fill distribution")
    results = []
    for p, q, mark in states:
        actual_cash = 3000 - q * (F(199, 10) + F(1, 50))
        wealth = actual_cash + q * mark
        paper = 3000 - 100 * 20 + 100 * mark
        shortfall = paper - wealth
        components = q * (F(199, 10) - 20) + (100 - q) * (mark - 20) + q * F(1, 50)
        v.equal(shortfall, components, "whole original target versus signed cost components")
        results.append((actual_cash, wealth, paper, shortfall))
    v.equal(results[0], (F(13008, 5), F(15208, 5), F(3200), F(792, 5)), "Up ledger")
    v.equal(results[1], (F(7032, 5), F(14232, 5), F(2800), -F(232, 5)), "Down ledger")
    expected_is = sum(state[0] * result[3] for state, result in zip(states, results))
    v.equal(expected_is, 56, "expected whole-target shortfall")
    v.equal(sum(p * q for p, q, _ in states) * conditional_profit, -expected_is,
            "conditional fills reconcile to unconditional marked portfolio gain")
    starting_cash, starting_wealth = results[1][:2]
    candidates = []
    for n in range(81):
        cash = starting_cash + n * (18 - F(1, 50))
        shares = 80 - n
        active_sd = F(1, 10) * 18 * abs(shares - 100)
        wealth = cash + 18 * shares
        v.equal(wealth, starting_wealth - F(n, 50), "each allowed sale loses exactly its fee")
        candidates.append({"n": n, "cash": cash, "shares": shares, "sd": active_sd})
    cash_feasible = [r for r in candidates if r["cash"] >= 1450]
    risk_feasible = [r for r in candidates if r["sd"] <= 40]
    joint = [r for r in candidates if r["cash"] >= 1450 and r["sd"] <= 40]
    v.equal(cash_feasible[0]["n"], 3, "smallest cash-funding integer sale")
    v.equal([r["n"] for r in risk_feasible], [0, 1, 2], "full risk-feasible integer set")
    v.equal(joint, [], "no allowed integer sale meets both constraints")
    r = cash_feasible[0]
    v.equal((r["cash"], r["shares"], r["sd"]), (F(73017, 50), 77, F(207, 5)),
            "cash remedy breaches active-risk cap")
    contribution, n = min((max(F(0), 1450 - r["cash"]), r["n"]) for r in risk_feasible)
    r = candidates[n]
    v.equal((contribution, n, r["shares"], r["sd"]), (F(191, 25), 2, 78, F(198, 5)),
            "minimum authorized sponsor remedy")
    v.equal(r["cash"] + contribution, 1450, "sponsor cash deadline closes")
    v.equal(1450 + 18 * r["shares"], starting_wealth + contribution - F(n, 50),
            "external flow and selling fee wealth reconciliation")
    v.equal(1450 + 18 * r["shares"], 2854, "funded total marked wealth")
    waiver, n = min((r["sd"], r["n"]) for r in cash_feasible)
    v.equal((waiver, n), (F(207, 5), 3), "minimum no-contribution prospective waiver")
    v.true(candidates[2]["cash"] < 1450 and candidates[3]["sd"] > 40,
           "two distinct constraints explain infeasibility")
    v.groups.append("conditional fills, whole-target wealth and exhaustive integer policy repair")


def sources(v):
    proposals = json.loads((ROOT / "content/reviews/v09-exam-b-sources.json").read_text())
    accepted = {s["id"]: s for s in json.loads((ROOT / "content/sources.json").read_text())}
    v.equal([s["id"] for s in proposals], SOURCE_IDS, "exact intended source reuse")
    for source in proposals:
        v.equal(source, accepted[source["id"]], f"unchanged scoped source record: {source['id']}")
    curriculum = json.loads((ROOT / "content/curriculum.json").read_text())
    volume = next(item for item in curriculum["volumes"] if item["id"] == "v09")
    v.equal([c["id"] for c in volume["chapters"]], [f"v09-c{i:02d}" for i in range(1, 13)],
            "all canonical prerequisite chapters present")
    for chapter in volume["chapters"]:
        v.equal(chapter["status"], "accepted", f"taught prerequisite: {chapter['id']}")
    v.groups.append("exact scoped source reuse and accepted prerequisite routes")


def check():
    v = Verify()
    words = structure(v)
    matrix = returns_and_sample(v)
    allocation(v, matrix)
    pricing_and_capm(v)
    factors_fees_evidence(v)
    endowment_and_liquidity(v)
    execution_and_policy(v)
    sources(v)
    result = {"assessment": "v09-exam-b", "status": "passed", "points": 100,
              "parts": 20, "scored_solutions": 20, "domains": 5,
              "chapter_outcomes": 12, "visible_words": words,
              "check_groups": len(v.groups), "groups": v.groups,
              "comparisons": v.comparisons, "domain_rejections": v.domain_rejections,
              "limits": "Original finite cases and prose/structure audit; no empirical validation, human certification or visual UI review."}
    json.dumps(result, allow_nan=False)
    return result


if __name__ == "__main__":
    print(json.dumps(check(), ensure_ascii=False, indent=2, allow_nan=False))
