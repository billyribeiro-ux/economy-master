"""Independent peer reconstructions of the Volume 9 support cases.

This checker never calls the coordinator's support_check() or check(). All
numerical results are reconstructed here from the printed inputs. The root
Structure class is exercised only with a small markup regression fixture.
check() is quiet, standard-library-only, and returns strict JSON. Counts include
structure and text-boundary comparisons, not that many independent derivations.
"""
from collections import Counter
from fractions import Fraction as F
from html.parser import HTMLParser
import json
import math
from pathlib import Path
import re
import runpy


ROOT = Path(__file__).resolve().parents[1]
OPENING = ROOT / "content/assessments/parts/v09-support-opening.html"
CLOSING = ROOT / "content/assessments/parts/v09-support-closing.html"


class Review:
    def __init__(self):
        self.comparisons = 0
        self.log_domain_rejections = 0
        self.parser_rejections = 0
        self.groups = []

    def equal(self, actual, expected, label):
        self.comparisons += 1
        if actual != expected:
            raise AssertionError(f"{label}: {actual!r} != {expected!r}")

    def true(self, value, label):
        self.equal(bool(value), True, label)

    def near(self, actual, expected, label):
        self.true(math.isfinite(actual) and abs(actual - expected) < 1e-12,
                  f"{label}: {actual} versus {expected}")


def dot(x, y):
    return sum((a * b for a, b in zip(x, y)), F(0))


def mean_var(values, weights):
    if len(values) != len(weights) or sum(weights) != 1 or min(weights) <= 0:
        raise ValueError("Positive exhaustive probabilities on matching states required")
    mean = dot(values, weights)
    # Raw second moment differs from the coordinator's centered-sum route.
    return mean, dot([x * x for x in values], weights) - mean * mean


def solve(matrix, rhs):
    n = len(rhs)
    rows = [[F(x) for x in row] + [F(y)] for row, y in zip(matrix, rhs)]
    for j in range(n):
        pivot = next((k for k in range(j, n) if rows[k][j]), None)
        if pivot is None:
            raise ValueError("Singular independent reconstruction")
        rows[j], rows[pivot] = rows[pivot], rows[j]
        scale = rows[j][j]
        rows[j] = [x / scale for x in rows[j]]
        for k in range(n):
            if k != j:
                scale = rows[k][j]
                rows[k] = [x - scale * y for x, y in zip(rows[k], rows[j])]
    return [row[-1] for row in rows]


class Support(HTMLParser):
    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input",
            "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.ids, self.links, self.text = [], [], []
        self.points, self.prompts, self.answers = {}, {}, {}
        self.active_prompt = self.active_answer = None
        self.in_solutions = False
        self.h1 = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "h1":
            self.h1 += 1
        if "id" in attrs:
            self.ids.append(attrs["id"])
        if tag == "a":
            self.links.append(attrs.get("href", ""))
        if tag == "details" and "solutions" in attrs.get("class", "").split():
            self.in_solutions = True
        if "data-points" in attrs:
            key = attrs.get("id")
            if tag != "li" or "ol" not in self.stack or self.in_solutions or key in self.points:
                raise AssertionError("Support prompt must be a unique ordered list item")
            self.points[key] = int(attrs["data-points"])
            self.prompts[key] = []
            self.active_prompt = key
        if "data-solution-for" in attrs:
            key = attrs["data-solution-for"]
            if tag != "li" or "ol" not in self.stack or not self.in_solutions or key in self.answers:
                raise AssertionError("Support solution must be unique and inside solutions")
            self.answers[key] = []
            self.active_answer = key
        if tag not in self.VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if not self.stack or self.stack.pop() != tag:
            raise AssertionError(f"Unbalanced support markup: {tag}")
        if tag == "li":
            self.active_prompt = self.active_answer = None
        if tag == "details":
            self.in_solutions = False

    def handle_data(self, data):
        self.text.append(data)
        if self.active_prompt:
            self.prompts[self.active_prompt].append(data)
        if self.active_answer:
            self.answers[self.active_answer].append(data)


def structure(review):
    doc = Support()
    doc.feed(OPENING.read_text() + "\n" + CLOSING.read_text())
    doc.close()
    expected = ({f"v09-d{i}": 5 for i in range(1, 9)} |
                {f"v09-o{i}": 5 for i in range(1, 5)} |
                {f"v09-r{i}": 10 for i in range(1, 7)})
    review.equal(doc.stack, [], "both support fragments are balanced")
    review.equal(doc.h1, 1, "one assembled assessment title")
    review.equal(len(doc.ids), len(set(doc.ids)), "support anchors unique")
    review.equal(doc.points, expected, "all eighteen prompt IDs and values")
    review.equal(set(doc.answers), set(expected), "all eighteen complete mapped answers")
    for group, total in (("d", 40), ("o", 20), ("r", 60)):
        review.equal(sum(score for key, score in doc.points.items() if key.startswith("v09-" + group)),
                     total, f"{group} total points")
    answer_text = {key: "".join(data) for key, data in doc.answers.items()}
    prompt_text = {key: "".join(data) for key, data in doc.prompts.items()}
    for key, maximum in expected.items():
        review.true(len(answer_text[key].split()) >= 55, f"{key} substantive answer")
        if not key.startswith("v09-o"):
            credit = answer_text[key].split("Credit:")[1].split("Repair")[0].split("Review")[0]
            scores = [int(x) for x in re.findall(r"\b([1-5])(?=[;.])", credit)]
            review.equal(sum(scores), maximum, f"{key} exact analytic credit sum")
    text = " ".join(doc.text)
    for boundary in ("34/40", "items 2, 3, 6 and 7", "240 minutes", "85/100",
                     "15/20", "17/20", "51/60", "at least eight on every item",
                     "two points for correct economic", "one for the relevant constraint",
                     "one for an explicit assumption", "one for a clear answer",
                     "carry-forward", "critical-error", "not been statistically equated"):
        review.true(boundary in text, f"administration boundary: {boundary}")
    review.true("grant payment" in prompt_text["v09-o4"] and
                "grant payment" in prompt_text["v09-r5"], "grant outflows now unambiguous")
    review.true("full two-factor fitted identity" in answer_text["v09-r3"] and
                "omitted exposure with a nonzero sample mean" in answer_text["v09-r3"],
                "descriptive factor identity no longer asserts compensation or future replication")
    review.true("annualizing the TWR" in answer_text["v09-r1"], "annual comparison preserves horizon")
    curriculum = json.loads((ROOT / "content/curriculum.json").read_text())
    chapters = {c["id"]: c for volume in curriculum["volumes"] for c in volume["chapters"]}
    for link in sorted(set(doc.links)):
        if link.startswith("#"):
            review.true(link[1:] in doc.ids, "support internal anchor: " + link)
        elif re.fullmatch(r"v\d\d-c\d\d.html", link):
            key = link[:-5]
            review.equal(chapters[key]["status"], "accepted", "accepted teaching route: " + key)
            review.true((ROOT / "content" / chapters[key]["manuscript"]).is_file(),
                        "manuscript route exists: " + key)
        elif link.startswith("curriculum.html#"):
            review.true(link.split("#")[1] in {v["id"] for v in curriculum["volumes"]},
                        "successor specification route")
        else:
            raise AssertionError("Unexpected support route: " + link)
    review.true(all(f"v09-c{i:02d}.html" in doc.links for i in range(1, 13)),
                "all twelve accepted chapter routes present")
    review.groups.append("support structure, scoring, prerequisites, indices and repaired wording")
    return answer_text


def diagnostics(review):
    after_first = F(200) * F(11, 10)
    before_second = after_first + 50
    final = before_second * F(9, 10)
    review.equal((after_first, before_second, final), (220, 270, 243), "D1 dated wealth")
    review.equal(final - 200 - 50, -7, "D1 investment profit excludes capital supplied")
    review.equal(final / 200 - 1, F(43, 200), "D1 contribution-contaminated raw ratio")
    review.groups.append("D1 contribution versus investment profit")

    p, risky = [F(2, 3), F(1, 3)], [F(1, 5), -F(1, 10)]
    portfolio = [F(2, 5) * r + F(3, 5) * F(1, 20) for r in risky]
    review.equal(mean_var(risky, p), (F(1, 10), F(1, 50)), "D2 raw second-moment risk")
    review.equal(portfolio, [F(11, 100), -F(1, 100)], "D2 portfolio state returns")
    review.equal(mean_var(portfolio, p), (F(7, 100), F(2, 625)), "D2 portfolio moments")
    review.equal(mean_var(portfolio, p)[1], F(2, 5) ** 2 * mean_var(risky, p)[1],
                 "D2 safe variance and covariance vanish")
    review.groups.append("D2 physical probability and decimal variance units")

    holdings = solve([[3, 1], [1, 1]], [2, 0])
    review.equal(holdings, [F(1), -F(1)], "D3 independent payoff-system solution")
    review.equal([dot(row, holdings) for row in [[3, 1], [1, 1]]], [2, 0], "D3 both payoff rows")
    review.equal(dot(holdings, [F(17, 10), F(9, 10)]), F(4, 5), "D3 replicated cost")
    review.groups.append("D3 same dated rights and signed financing")

    # Count a population of 1,000, rather than reusing a probability formula.
    event_positive, non_event_positive = 80, 180
    review.equal(F(event_positive, event_positive + non_event_positive), F(4, 13), "D4 signal posterior")
    review.true(F(4, 13) != F(4, 5), "D4 conditioning events differ")
    changed_prevalence = F(400, 400 + 100)
    review.true(changed_prevalence != F(4, 13), "D4 changed population can change posterior")
    review.groups.append("D4 Bayes denominator and transport boundary")

    a, b, bound = -F(2, 25), F(3, 50), F(1, 4)
    unconstrained = -b / (2 * a)
    derivative_at_bound = b + 2 * a * bound
    review.equal((unconstrained, derivative_at_bound, a * bound ** 2 + b * bound),
                 (F(3, 8), F(1, 50), F(1, 100)), "D5 stationary and constrained values")
    review.true(a < 0 and derivative_at_bound > 0,
                "D5 derivative decreasing but still positive throughout feasible interval")
    review.groups.append("D5 global feasible-direction certificate")

    friday = 18 - 12
    review.equal((friday, max(0, 8 - friday), friday + 7), (6, 2, 13), "D6 dated reserve ledger")
    review.true(18 >= 12 and friday < 8, "D6 payment settlement differs from reserve compliance")
    review.groups.append("D6 future receipt cannot fund Friday")

    final_cohort = F(6, 5) + F(11, 10)
    review.equal((final_cohort, final_cohort / 3 - 1), (F(23, 10), -F(7, 30)), "D7 original cohort")
    review.equal(final_cohort / 2 - 1, F(3, 20), "D7 future-selected survivor population")
    review.groups.append("D7 lost initial capital stays in the cohort")

    low, high = F(4) - F(49, 25) * 3, F(4) + F(49, 25) * 3
    review.equal((low, high), (-F(47, 25), F(247, 25)), "D8 interval in percentage points")
    review.true(low < 0 < high, "D8 nonrejection does not identify an exact zero")
    review.groups.append("D8 stated uncertainty and unadjusted selection boundary")


def oral(review, answers):
    fractions = [F(0), F(1, 10), F(1, 2), F(1)]

    def log_score(surplus):
        if min(surplus) <= 0:
            raise ValueError("Expected log requires strictly positive surplus in every possible state")
        return sum(math.log(float(x)) / 2 for x in surplus)

    for income, optimal, expected_products in ((0, F(1, 10), [F(1), F(32, 25)]),
                                                (1, F(1, 2), [F(4), F(117, 25), F(5)])):
        candidates, products = [], []
        for w in fractions:
            risky_cu, safe_cu = 10 * w, 10 * (1 - w)
            surplus = [safe_cu + risky_cu * g + income - 9 for g in (F(8, 5), F(4, 5))]
            try:
                score = log_score(surplus)
            except ValueError:
                review.log_domain_rejections += 1
                review.true(min(surplus) <= 0, "O1 infeasible log domain rejected before utility")
            else:
                candidates.append((score, w))
                product = surplus[0] * surplus[1]
                products.append(product)
                review.near(score, math.log(float(product)) / 2, "O1 log-sum and product equivalence")
        review.equal(max(candidates)[1], optimal, "O1 actual discrete-menu optimum")
        review.equal(products, expected_products, "O1 complete positive-surplus action menu")
    review.equal(review.log_domain_rejections, 3, "O1 all three inadmissible menu cases accounted for")
    review.groups.append("O1 actual log utilities, strict surplus domain and conditional terminal income")

    physical, sdf = [F(3, 4), F(1, 4)], [F(4, 5), F(7, 5)]
    state_prices = [a * b for a, b in zip(physical, sdf)]
    x, y = [F(1), F(0)], [F(0), F(3)]
    review.equal(dot(physical, x), dot(physical, y), "O2 equal physical expected payoffs")
    review.equal((dot(state_prices, x), dot(state_prices, y)), (F(3, 5), F(21, 20)), "O2 unequal SDF prices")
    review.equal(sum(state_prices), F(19, 20), "O2 bond discount factor")
    normalized = [q / sum(state_prices) for q in state_prices]
    review.equal(normalized, [F(12, 19), F(7, 19)], "O2 normalized pricing probabilities")
    review.true(normalized != physical, "O2 physical probabilities are not pricing probabilities")
    review.groups.append("O2 physical equality does not imply equal contingent value")

    # This is a boundary inventory after independent prose review, not an
    # automated determination of empirical validity or human oral competence.
    for term in ("cutoff", "100-rule search history", "before seeing evaluation",
                 "failed funds", "availability dates", "execution costs",
                 "uncertainty", "dependence", "new experiment", "does not establish causality"):
        review.true(term in answers["v09-o3"], "O3 reviewed evidence boundary: " + term)
    review.groups.append("O3 prospective falsifiable evidence design, reviewed qualitatively")

    required_cash = 18 + 5 + 4
    proceeds = 7 * F(19, 20)
    closing = 20 + proceeds - 18 - 5
    review.equal((required_cash - 20, proceeds, closing, 4 - closing),
                 (F(7), F(133, 20), F(73, 20), F(7, 20)), "O4 capped outgoing grant/call ledger")
    required_units = F(required_cash - 20) / F(19, 20)
    review.equal(required_units, F(140, 19), "O4 unconstrained required sale")
    review.true(required_units > 7, "O4 adequate bonds without authorized capacity are insufficient")
    review.equal(closing + F(7, 20), 4, "O4 timely authorized contribution closes actual reserve")
    review.groups.append("O4 sale cap, date-specific funding and actual authorization")


def retention(review):
    first = F(1000) * F(27, 25)
    second_start = first + 200
    gross_end = second_start * F(19, 20)
    end = gross_end - 16
    twr = first / 1000 * end / second_start - 1
    review.equal((first, second_start, gross_end, end, twr), (1080, 1280, 1216, 1200, F(1, 80)),
                 "R1 dated fee-inclusive account closure")
    annualized = math.sqrt(float(1 + twr)) - 1
    review.true(0 < annualized < float(twr), "R1 annual and two-year horizons differ")
    for gross_root in (F(1), -F(6, 5)):
        review.equal(-1000 * gross_root ** 2 - 200 * gross_root + 1200, 0, "R1 both polynomial roots")
    review.equal(-1000 - 200 + 1200, 0, "R1 zero IRR closes investor cash")
    matrix = [[F(1, 25), F(1, 200)], [F(1, 200), F(1, 100)]]

    def risk(w):
        weights = [w, 1 - w]
        return sum(weights[i] * matrix[i][j] * weights[j] for i in range(2) for j in range(2))

    quad = risk(F(1)) - 2 * risk(F(1, 2)) + risk(F(0))
    # This centered second difference has spacing 1/2, so it equals a/2.
    quad *= 2
    linear = risk(F(1)) - risk(F(0)) - quad
    unconstrained = -linear / (2 * quad)
    constrained = max(F(1, 5), unconstrained)
    review.equal((quad, linear, unconstrained, constrained), (F(1, 25), -F(1, 100), F(1, 8), F(1, 5)),
                 "R1 covariance-matrix reconstruction and constrained choice")
    review.equal((risk(unconstrained), risk(constrained)), (F(3, 320), F(6, 625)), "R1 both estimated variances")
    review.true(quad > 0 and linear + 2 * quad * constrained > 0,
                "R1 global increasing-risk certificate above binding lower bound")
    review.groups.append("R1 timing, annualization, IRR root and constrained covariance optimum")

    # Parameterize by q3=u, independently of the printed q1=t family.
    lo_u, hi_u = F(1, 20), F(1, 2)
    for u in (F(1, 10), F(1, 4), F(2, 5)):
        q = [u - F(1, 20), 1 - 2 * u, u]
        review.true(min(q) > 0, "R2 strict state prices")
        review.equal((sum(q), dot(q, [0, 1, 2])), (F(19, 20), 1), "R2 original claim price equations")
        price_x = dot(q, [1, 0, 1])
        review.equal(price_x, 2 * u - F(1, 20), "R2 independent price parameterization")
        reconstructed = solve([[1, 1, 1], [0, 1, 2], [1, 0, 1]], [F(19, 20), 1, price_x])
        review.equal(reconstructed, q, "R2 full extension reconstructed by elimination")
    review.equal((2 * lo_u - F(1, 20), 2 * hi_u - F(1, 20)), (F(1, 20), F(19, 20)),
                 "R2 strict no-arbitrage interval")
    for u in (lo_u, hi_u):
        review.equal(min([u - F(1, 20), 1 - 2 * u, u]), 0, "R2 endpoints lose strict positivity")
    review.equal(F(1, 20) - 1 + F(19, 20), 0, "R2 endpoint trade budget")
    review.equal([x - a + 1 for x, a in zip([1, 0, 1], [0, 1, 2])], [2, 0, 0],
                 "R2 endpoint arbitrage state payoffs")
    rf = F(20, 19) - 1
    expected_return = dot([F(1, 5), F(1, 2), F(3, 10)], [0, 1, 2]) - 1
    capm = rf + F(7, 5) * F(1, 20)
    review.equal((rf, expected_return, capm, expected_return - capm),
                 (F(1, 19), F(1, 10), F(233, 1900), -F(43, 1900)), "R2 CAPM discrepancy with existing positive pricing law")
    review.groups.append("R2 incomplete pricing, funded endpoint arbitrage and conditional CAPM")

    factor = list(map(F, (-2, -1, 1, 2)))
    second = [F(3, 2), -F(1, 2), -F(1, 2), F(3, 2)]
    y = [F(0), -F(5, 2), F(1, 2), F(6)]
    weights = [F(1, 4)] * 4

    def normal_equations(columns):
        return solve([[dot(a, b) for b in columns] for a in columns], [dot(a, y) for a in columns])

    one = normal_equations([[F(1)] * 4, factor])
    full = normal_equations([[F(1)] * 4, factor, second])
    review.equal(one, [F(1), F(3, 2)], "R3 one-factor least squares from normal equations")
    review.equal(full, [F(0), F(3, 2), F(2)], "R3 full descriptive least squares from normal equations")
    full_residual = [value - full[0] - full[1] * f - full[2] * g for value, f, g in zip(y, factor, second)]
    review.equal(full_residual, [0] * 4, "R3 exact identity only over the supplied four records")
    active = [value - F(3, 2) * f for value, f in zip(y, factor)]
    net = [value - F(2, 5) for value in active]
    review.equal(active, [3, -1, -1, 3], "R3 predeclared benchmark-active observations")
    review.equal(mean_var(active, weights), (F(1), F(4)), "R3 gross population moments in pp")
    review.equal(mean_var(net, weights), (F(3, 5), F(4)), "R3 fee changes mean, not centered risk")
    review.equal((mean_var(active, weights)[0] / 2, mean_var(net, weights)[0] / 2),
                 (F(1, 2), F(3, 10)), "R3 descriptive information ratios")
    review.equal(full[0] - F(2, 5), -F(2, 5), "R3 net full-model intercept in percentage points")
    review.groups.append("R3 omitted exposure, fixed benchmark and population versus inference scope")

    def surplus(x, income):
        return [(10 - x) + x * g + inc - 5 for g, inc in zip([F(7, 5), F(4, 5)], income)]

    def score(x, income):
        mu, var = mean_var(surplus(x, income), [F(1, 2)] * 2)
        return mu - var / 2

    for income, optimum in (([2, 6], F(70, 9)), ([0, 0], F(10, 9))):
        c = score(F(0), income)
        a = (score(F(2), income) - 2 * score(F(1), income) + c) / 2
        b = score(F(1), income) - c - a
        chosen = -b / (2 * a)
        review.equal(chosen, optimum, "R4 optimum derived from full state ledger quadratic")
        review.true(a < 0 and 0 < chosen < 10, "R4 strict concavity and actual initial budget")
        # Polynomial coefficients certify score(chosen)-score(x)=-a(x-chosen)^2 for every x.
        review.equal([score(chosen, income) - c, -b, -a],
                     [-a * chosen ** 2, 2 * a * chosen, -a], "R4 global square-loss identity coefficients")
    actual_surplus = surplus(F(70, 9), [2, 6])
    review.equal(actual_surplus, [F(91, 9), F(85, 9)], "R4 actual state surpluses")
    review.equal(mean_var(actual_surplus, [F(1, 2)] * 2), (F(88, 9), F(1, 9)), "R4 mean and variance units")
    review.true(F(70, 9) > F(10, 9), "R4 countercyclical income permits larger risky demand")
    review.groups.append("R4 nontraded hedge, two exact global certificates and initial budget")

    base_cash = 50 - 30 - 12
    stress_cash = base_cash - 8
    review.equal((base_cash, stress_cash, 10 - base_cash, 10 - stress_cash), (8, 0, 2, 10), "R5 gross cash obligations")
    units = F(10 - stress_cash) / F(49, 50)
    review.equal(units, F(500, 49), "R5 exact divisible minimum stress sale")
    review.true(units <= 12 and units > 10, "R5 authorized capacity intervention changes feasibility")
    review.equal(stress_cash + units * F(49, 50), 10, "R5 repaired stress cash")
    review.equal(10 - (stress_cash + 10 * F(49, 50)), F(1, 5), "R5 reduced capacity gap")
    alpha = F(3, 5)
    latent = (-F(1, 50) - alpha * F(1, 50)) / (1 - alpha)
    review.equal(latent, -F(2, 25), "R5 latent return from dated appraisal inversion")
    ratio = (1 - alpha) ** 2 / (1 - alpha ** 2)
    finite_ma_variance = sum(((1 - alpha) * alpha ** lag) ** 2 for lag in range(12))
    review.equal(finite_ma_variance + alpha ** 24 * ratio, ratio, "R5 moving-average variance plus exact stationary tail")
    review.equal(ratio, F(1, 4), "R5 stationary iid variance ratio")
    review.near(math.sqrt(float(ratio)), 0.5, "R5 volatility ratio differs from variance ratio")
    review.groups.append("R5 cash capacity, appraisal inversion and stationary iid filter boundary")

    initial_paper = 200 * 40
    execution_cash = 120 * F(79, 2) - 6
    residual_mark = 80 * 39
    actual_wealth = execution_cash + residual_mark
    filled, unfilled = 120 * (40 - F(79, 2)) + 6, 80 * (40 - 39)
    review.equal((execution_cash, actual_wealth, initial_paper - actual_wealth, filled, unfilled),
                 (4734, 7854, 146, 66, 80), "R6 full initial target cash and mark ledger")
    half_spread_sell = F(199, 5) - F(79, 2)
    review.equal(2 * half_spread_sell, F(3, 5), "R6 signed effective spread excludes explicit fee")
    each = 39 - F(1, 20)
    required = (5000 - execution_cash) / each
    n = (required.numerator + required.denominator - 1) // required.denominator
    review.equal(n, 7, "R6 exact integer minimum sale")
    review.true(execution_cash + (n - 1) * each < 5000 <= execution_cash + n * each,
                "R6 monotone cash constraint proves global smallest integer")
    review.equal((execution_cash + 6 * each, execution_cash + 7 * each, 80 - n),
                 (F(49677, 10), F(100133, 20), 73), "R6 six versus seven sales and residual target")
    after_wealth = execution_cash + n * each + (80 - n) * 39
    review.equal(after_wealth, actual_wealth - F(n, 20), "R6 repair changes wealth only by additional fees")
    review.true(120 + n < 200, "R6 cash repair does not complete original mandate")
    review.groups.append("R6 signed sell measurement, exact integer repair and historical target")


def coordinator_parser_regression(review):
    # Definitions load only. The coordinator's numerical functions are never called.
    definitions = runpy.run_path(str(ROOT / "scripts/check_v09_assessment.py"),
                                 run_name="_v09_peer_markup_only_")
    parser = definitions["Structure"]()
    parser.feed('<table><tr data-points="25"><td>Rubric row</td></tr></table>'
                '<ol><li id="peer-fixture" data-points="5">Prompt</li></ol>'
                '<ol><li data-solution-for="peer-fixture">Answer</li></ol>')
    review.equal(parser.points, {"peer-fixture": 5}, "root parser excludes scored rubric rows from prompts")
    review.equal(parser.solutions, ["peer-fixture"], "root parser recognizes mapped semantic solution")
    for markup in ('<li data-points="5">Missing anchor</li>',
                   '<li id="dup" data-points="5"></li><li id="dup" data-points="5"></li>'):
        parser = definitions["Structure"]()
        try:
            parser.feed(markup)
        except AssertionError:
            review.parser_rejections += 1
        else:
            raise AssertionError("Coordinator parser accepted malformed scored prompt")
    review.equal(review.parser_rejections, 2, "missing and duplicate prompt anchors rejected")
    review.groups.append("coordinator markup regression only; no numerical oracle called")


def check():
    review = Review()
    answers = structure(review)
    diagnostics(review)
    oral(review, answers)
    retention(review)
    coordinator_parser_regression(review)
    result = {"review": "v09-support-peer", "status": "passed",
              "diagnostic_cases": 8, "oral_cases": 4, "retention_cases": 6,
              "quantitative_cases": 17, "qualitative_oral_design": 1,
              "check_groups": len(review.groups), "groups": review.groups,
              "comparisons": review.comparisons,
              "log_domain_rejections": review.log_domain_rejections,
              "malformed_prompt_rejections": review.parser_rejections,
              "coordinator_numerical_oracle_called": False,
              "limits": "Finite synthetic arithmetic and support structure; open-answer judgment requires editorial review. No human certification, empirical validation or visual UI review."}
    json.dumps(result, allow_nan=False)
    return result


if __name__ == "__main__":
    print(json.dumps(check(), ensure_ascii=False, indent=2, allow_nan=False))
