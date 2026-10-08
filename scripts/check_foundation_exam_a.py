"""Independent, standard-library audit of foundation written Form A.

Exact rational arithmetic, separate algebraic routes and behavioral mutations
supplement the written proof/solution review. No external data or packages.
"""
from calendar import monthrange
from copy import deepcopy
from datetime import date
from fractions import Fraction as F
from html.parser import HTMLParser
from itertools import permutations, product
from math import exp, pi, sqrt
from pathlib import Path
from statistics import NormalDist
import json
import re


ROOT = Path(__file__).resolve().parents[1]
MANUSCRIPT = ROOT / "content/assessment-parts/foundation-form-a.html"


def require(condition, message):
    if not condition:
        raise ValueError(message)


class Fragment(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids, self.parts, self.rubrics, self.headings, self.links = [], [], [], [], []
        self.stack = []
        self.tables = {}
        self.table_id = None
        self.row = None
        self.cell = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag not in ("br", "hr", "img", "meta", "input", "link"):
            self.stack.append(tag)
        if "id" in attrs:
            self.ids.append(attrs["id"])
        if tag in ("h1", "h2", "h3"):
            self.headings.append((tag, attrs.get("id")))
        if tag == "li" and "data-points" in attrs:
            self.parts.append((attrs.get("id"), int(attrs["data-points"])))
        if tag == "p" and attrs.get("class") == "rubric":
            self.rubrics.append(int(attrs["data-points"]))
        if tag == "a":
            self.links.append(attrs.get("href", ""))
        if tag == "table":
            self.table_id = attrs.get("id")
            self.tables[self.table_id] = []
        if tag == "tr" and self.table_id:
            self.row = []
        if tag in ("th", "td") and self.row is not None:
            self.cell = []

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        require(bool(self.stack) and self.stack.pop() == tag, "unbalanced HTML at " + tag)
        if tag in ("th", "td") and self.cell is not None:
            self.row.append("".join(self.cell).strip())
            self.cell = None
        if tag == "tr" and self.row is not None:
            self.tables[self.table_id].append(self.row)
            self.row = None
        if tag == "table":
            self.table_id = None


def average(values):
    return sum(values, F(0)) / len(values)


def fit_line(observations):
    """Eliminate the intercept from the normal equations by determinants."""
    n = len(observations)
    sx = sum(x for x, y in observations)
    sy = sum(y for x, y in observations)
    xx = sum(x * x for x, y in observations)
    xy = sum(x * y for x, y in observations)
    determinant = n * xx - sx * sx
    require(determinant > 0, "line requires varying x")
    intercept = (sy * xx - sx * xy) / determinant
    slope = (n * xy - sx * sy) / determinant
    residual = [y - intercept - slope * x for x, y in observations]
    return intercept, slope, residual


def freeze(rows, cutoff, expected_keys):
    """Independent bounded panel selector with persistent audit exceptions."""
    seen, selected = set(), {}
    doses = {"A": F(0), "B": F(1), "C": F(2)}
    for row in rows:
        require(set(row) == {"firm", "month", "release", "x", "y"}, "row fields")
        firm, month, release = row["firm"], row["month"], row["release"]
        require(firm in doses and row["x"] == doses[firm], "firm/dose contract")
        require(re.fullmatch(r"\d{4}-\d{2}", month) is not None, "month format")
        year, number = map(int, month.split("-"))
        period_end = date(year, number, monthrange(year, number)[1])
        released = date.fromisoformat(release)
        require(released >= period_end, "completed-month value released too early")
        require(type(row["y"]) is F and row["y"] >= 0, "nonnegative rational output")
        key = (firm, month, release)
        require(key not in seen, "duplicate release-history key")
        seen.add(key)
        selected_key = (firm, month)
        if released <= cutoff:
            previous = selected.get(selected_key)
            if previous is None or release > previous["release"]:
                selected[selected_key] = dict(row)
    require(set(selected) == expected_keys, "incomplete or unexpected active panel coverage")
    return [selected[key] for key in sorted(expected_keys, key=lambda key: (key[1], key[0]))]


def check():
    text = MANUSCRIPT.read_text(encoding="utf-8")
    fragment = Fragment()
    fragment.feed(text)
    require(not fragment.stack, "unclosed HTML")
    require(fragment.headings[0] == ("h2", "form-a"), "required fragment heading")
    require(not any(tag == "h1" for tag, _ in fragment.headings), "unexpected h1")
    require(len(fragment.ids) == len(set(fragment.ids)), "duplicate IDs")
    require(all(item == "form-a" or item.startswith("foundation-a-")
                for item in fragment.ids), "unprefixed internal ID")
    expected_parts = [(f"foundation-a-q{q}{part}", 5)
                      for q in range(1, 5) for part in "abcde"]
    require(fragment.parts == expected_parts, "four domains/five five-point parts")
    require(fragment.rubrics == [5] * 20, "twenty five-point solution rubrics")
    for q in range(1, 5):
        require(f"foundation-a-q{q}" in fragment.ids and f"foundation-a-s{q}" in fragment.ids,
                "question/solution domain group")
        for part in "abcde":
            require(f"foundation-a-s{q}{part}" in fragment.ids, "missing matched solution")
    require(sum(score for _, score in fragment.parts) == 100, "exam score")
    require("180 minutes" in text and "basic nonprogrammable calculator" in text,
            "examination conditions")
    curriculum = json.loads((ROOT / "content/curriculum.json").read_text())
    accepted = {chapter["id"] for volume in curriculum["volumes"]
                for chapter in volume["chapters"] if chapter["status"] == "accepted"}
    for link in fragment.links:
        require(re.fullmatch(r"v\d{2}-c\d{2}\.html", link) is not None, "unexpected method link")
        require(link.removesuffix(".html") in accepted and
                (ROOT / "content/chapters" / link).is_file(), "unaccepted or missing method link")
    require({link[:3] for link in fragment.links} == {"v01", "v02", "v03", "v04"},
            "cross-volume method coverage")
    checks = ["Balanced HTML; four25-point domains; twenty matched five-point parts, "
              "solutions and rubrics; unique prefixed IDs; all method routes accepted across four volumes."]
    results = {}

    # D1: calculate alternative-level present values before taking their
    # difference, and independently accumulate the difference to year two.
    inflation, nominal = F(27, 25), F(567, 500)
    real = nominal / inflation
    project_receipts = [F(324), F("349.92") + F("116.64")]
    rental_receipts = [F(54), F("58.32")]
    incremental = [F(-500)] + [a - b for a, b in zip(project_receipts, rental_receipts)]
    project_pv = -500 + sum(value / nominal ** t
                            for t, value in enumerate(project_receipts, start=1))
    rent_pv = sum(value / nominal ** t
                  for t, value in enumerate(rental_receipts, start=1))
    nominal_npv = project_pv - rent_pv
    real_flows = [value / inflation ** t for t, value in enumerate(incremental)]
    real_npv = sum(value / real ** t for t, value in enumerate(real_flows))
    terminal_net = -500 * nominal ** 2 + incremental[1] * nominal + incremental[2]
    require(incremental == [-500, 270, F("408.24")], "incremental cash-flow classification")
    require(real - 1 == F(1, 20) and real_flows == [-500, 250, 350], "real transformation")
    require(nominal_npv == real_npv == terminal_net / nominal ** 2 == F(500, 9),
            "three independent valuation routes")
    funding = [F(300), F(-30), F(-330)]
    funded = [a + b for a, b in zip(incremental, funding)]
    require(funded == [-200, 240, F("78.24")], "financing separation")
    # Event ledger: both events must preserve assets - liabilities = equity.
    cash, room, machine, debt, equity = map(F, (1000, 300, 0, 400, 900))
    require(cash + room + machine == debt + equity, "opening balance")
    cash += 300
    debt += 300
    require(cash + room + machine == debt + equity, "loan balance")
    cash -= 500
    machine += 500
    require((cash, room, machine, debt, equity) == (800, 300, 500, 700, 900),
            "closing balance entries")
    require(cash + room + machine == debt + equity == 1600, "closing identity")
    require(850 - cash == 50 and cash < 850, "liquidity policy")
    results["D1"] = {"incremental_nominal_flows": [str(v) for v in incremental],
                     "real_rate": str(real - 1), "real_flows": [str(v) for v in real_flows],
                     "NPV_usd": str(real_npv), "funded_flows": [str(v) for v in funded],
                     "closing_assets_debt_equity": ["1600", "700", "900"],
                     "cash_usd": "800", "liquidity_shortfall_usd": "50"}
    checks.append("D1: separate project/rental PVs, real transformation, independent "
                  "terminal-value identity, financing sequence, event-by-event balance sheets and liquidity.")

    # D2: exact interval bracket is independent of the quadratic radical and
    # provides a reference for iteration-error claims without float cancellation.
    mapping = lambda u: (1 + u * u) / 4
    q = F(1, 2)
    grid = [F(k, 8) for k in range(9)]
    for u, v in product(grid, repeat=2):
        require(F(1, 4) <= mapping(u) <= F(1, 2), "interval self-map grid")
        require(abs(mapping(u) - mapping(v)) == abs(u - v) * (u + v) / 4
                <= q * abs(u - v), "exact Lipschitz factorization")
    low, high = F(0), F(1)
    polynomial = lambda u: u * u - 4 * u + 1
    for _ in range(80):
        middle = (low + high) / 2
        if polynomial(middle) > 0:
            low = middle
        else:
            high = middle
    require(polynomial(low) >= 0 >= polynomial(high), "root bracket")
    root_float = 2 - sqrt(3)
    require(abs(root_float - float((low + high) / 2)) < 1e-15, "independent radical reference")
    iterates = [F(0)]
    for _ in range(9):
        iterates.append(mapping(iterates[-1]))
    require(iterates[1:4] == [F(1, 4), F(17, 64), F(4385, 16384)], "three iterates")
    step_bound = q / (1 - q) * abs(iterates[3] - iterates[2])
    require(step_bound == F(33, 16384) and step_bound > F(1, 1000), "latest-step certificate")
    require(0 < low - iterates[3] <= high - iterates[3] < step_bound,
            "bracket confirms actual error bounded")
    require(high - iterates[3] < F(1, 1000), "conservative bound versus actual error")
    first = next(n for n in range(20)
                 if q ** n * abs(iterates[1] - iterates[0]) / (1 - q) < F(1, 1000))
    require(first == 9, "smallest index for specified a priori bound")
    for n in range(1, 10):
        a_priori = q ** n * abs(iterates[1] - iterates[0]) / (1 - q)
        latest = q / (1 - q) * abs(iterates[n] - iterates[n - 1])
        require(high - iterates[n] <= a_priori and high - iterates[n] <= latest,
                "exact contraction error checks")

    def objective(x, y, u):
        return (4 + u) * x + (2 + u) * y - (x * x + y * y) / 2

    capacity_cases = 0
    for u, capacity in product([F(1, 4), iterates[3], F(1, 2)],
                               [F(k, 4) for k in range(17)]):
        # Independently enumerate optima of all three triangle edges.
        edge_y = min(capacity, 2 + u)
        edge_x = min(capacity, 4 + u)
        diagonal_x = min(capacity, max(F(0), (capacity + 2) / 2))
        candidates = [(F(0), F(0)), (edge_x, F(0)), (F(0), edge_y),
                      (diagonal_x, capacity - diagonal_x)]
        best_value = max(objective(x, y, u) for x, y in candidates)
        if capacity <= 2:
            xstar, ystar = capacity, F(0)
            closed_value = (4 + u) * capacity - capacity ** 2 / 2
            multiplier = 4 + u - capacity
        else:
            xstar, ystar = (capacity + 2) / 2, (capacity - 2) / 2
            closed_value = 1 + (3 + u) * capacity - capacity ** 2 / 4
            multiplier = 3 + u - capacity / 2
        # A separate quadratic upper bound verifies no omitted interior point
        # beats the edge maximum: subtract lambda(x+y-c), maximize coordinates.
        upper = multiplier * capacity + (max(F(0), 4 + u - multiplier) ** 2
                                         + max(F(0), 2 + u - multiplier) ** 2) / 2
        require(best_value == objective(xstar, ystar, u) == closed_value == upper,
                "allocation value and independent quadratic upper bound")
        require(xstar >= 0 and ystar >= 0 and xstar + ystar == capacity,
                "allocation feasibility")
        capacity_cases += 1
    u = iterates[3]
    require((4 + u) * 2 - F(4, 2) == 1 + (3 + u) * 2 - F(4, 4) == 6 + 2 * u,
            "value transition equality")
    require(4 + u - 2 == 3 + u - F(2, 2), "derivative transition equality")
    approximate_value = objective(F(3), F(1), u)
    propagated = 4 * step_bound
    require(approximate_value == F(41249, 4096) and propagated == F(33, 4096),
            "approximate value/error propagation")
    require(0 < 9 + 4 * low - approximate_value <= 9 + 4 * high - approximate_value < propagated,
            "value error against independent root bracket")
    # Direct finite differences agree with the one-sided derivative plus its
    # exact quadratic remainder, not an assumed exact linear response.
    for delta in (F(-1, 10), F(-1, 100), F(-1, 1000)):
        value_changed = 1 + (3 + u) * (4 + delta) - (4 + delta) ** 2 / 4
        require(value_changed - approximate_value == (1 + u) * delta - delta ** 2 / 4,
                "capacity marginal-value remainder")
    results["D2"] = {"fixed_point": "2-sqrt(3)", "fixed_point_approx": root_float,
                     "iterates_1_to_3": [str(v) for v in iterates[1:4]],
                     "latest_step_error_bound": str(step_bound),
                     "a_priori_first_certified_index": first,
                     "allocation_capacity_1": ["1", "0"],
                     "allocation_capacity_4": ["3", "1"],
                     "capacity_transition": "2", "left_marginal_at_4": "3-sqrt(3)",
                     "value_at_4": "17-4*sqrt(3)",
                     "approximate_value_hundreds_usd_per_day": str(approximate_value),
                     "value_error_bound_hundreds_usd_per_day": str(propagated),
                     "value_error_bound_usd_per_day": str(100 * propagated)}
    checks.append(f"D2: exact contraction factorization and80-step rational root bracket; "
                  f"iteration and conservative-tail bounds; {capacity_cases} allocation regimes "
                  "checked by boundary candidates and an independent quadratic upper bound; "
                  "value/derivative transition, local remainder and propagated dollar error.")

    # D3: enumerate all deterministic report-contingent action policies.
    prior = {"H": F(1, 5), "L": F(4, 5)}
    positive = {"H": F(3, 4), "L": F(1, 4)}
    joint = {(state, report): probability *
             (positive[state] if report == "+" else 1 - positive[state])
             for state, probability in prior.items() for report in ("+", "-")}
    require(joint == {("H", "+"): F(3, 20), ("H", "-"): F(1, 20),
                      ("L", "+"): F(1, 5), ("L", "-"): F(3, 5)}, "signal joint law")
    reports = {report: sum(joint[state, report] for state in prior) for report in ("+", "-")}
    posterior = {report: joint["H", report] / reports[report] for report in reports}
    require(posterior == {"+": F(3, 7), "-": F(1, 13)}, "Bayesian posteriors")
    loss = lambda action, state: F(40) if action == "service" else F(160 if state == "H" else 0)
    actions = ("leave", "service")
    prior_losses = {action: sum(prior[state] * loss(action, state) for state in prior)
                    for action in actions}
    require(prior_losses == {"leave": 32, "service": 40}, "prior policy")
    policies = {}
    for on_positive, on_negative in product(actions, repeat=2):
        policy = {"+": on_positive, "-": on_negative}
        policies[(on_positive, on_negative)] = sum(
            probability * loss(policy[report], state)
            for (state, report), probability in joint.items())
    best = min(policies, key=policies.get)
    best_loss = policies[best]
    perfect_loss = sum(prior[state] * min(loss(action, state) for action in actions)
                       for state in prior)
    require(best == ("service", "leave") and best_loss == 22 and perfect_loss == 8,
            "exhaustive action-policy minima")
    require(min(prior_losses.values()) - best_loss == 10 and
            min(prior_losses.values()) - perfect_loss == 24, "information values")
    expected_invoice = reports["+"] * 28
    indifferent_invoice = (min(prior_losses.values()) - best_loss) / reports["+"]
    require(expected_invoice == F(49, 5) and best_loss + expected_invoice == F(159, 5) < 32,
            "contingent invoice decision")
    require(indifferent_invoice == F(200, 7), "contingent invoice boundary")
    for fee in (F(0), F(28), indifferent_invoice, F(40)):
        with_fee = {policy: value + reports["+"] * fee for policy, value in policies.items()}
        require(min(with_fee, key=with_fee.get) == best, "action-independent invoice policy invariance")
    for p in (F(0), F(1, 5), F(1, 4), F(3, 7), F(1)):
        require((40 < 160 * p) == (p > F(1, 4)), "loss threshold")
    se, quantile = F(2), F(49, 25)
    lower, upper = 5 - quantile * se, 5 + quantile * se
    require((lower, upper) == (F(27, 25), F(223, 25)) and lower < 4 < upper,
            "normal interval/cost threshold")
    normal_coverage = NormalDist().cdf(float(quantile)) - NormalDist().cdf(-float(quantile))
    # Independent finite quadrature of the standard-normal pivot density.
    slices = 2000
    left, right = -float(quantile), float(quantile)
    h = (right - left) / slices
    density = lambda z: exp(-z * z / 2) / sqrt(2 * pi)
    integral = h / 3 * (density(left) + density(right) + sum(
        (4 if j % 2 else 2) * density(left + j * h) for j in range(1, slices)))
    require(abs(integral - normal_coverage) < 1e-11 and abs(normal_coverage - .95) < .00001,
            "rounded-normal-quantile coverage")
    results["D3"] = {"positive_probability": str(reports["+"]),
                     "posterior_fault_positive_negative": [str(posterior[r]) for r in ("+", "-")],
                     "service_threshold": "1/4", "no_report_loss_usd": "32",
                     "free_report_loss_usd": str(best_loss), "EVSI_usd": "10", "EVPI_usd": "24",
                     "expected_invoice_usd": str(expected_invoice),
                     "paid_report_loss_usd": str(best_loss + expected_invoice),
                     "positive_only_indifference_fee_usd": str(indifferent_invoice),
                     "confidence_interval_usd": [str(lower), str(upper)],
                     "rounded_quantile_coverage": normal_coverage}
    checks.append("D3: exact joint-state enumeration, all four report policies, "
                  "perfect-information comparison, contingent-invoice acquisition and action boundaries; "
                  "normal interval and independently integrated rounded-quantile coverage.")

    # D4: read actual manuscript tables, verify source selection is independent
    # of row order, and intentionally reject malformed/source-incomplete data.
    records = [{"firm": firm, "month": month, "release": release, "x": F(x), "y": F(y)}
               for firm, month, release, x, y in fragment.tables["foundation-a-panel"][1:]]
    expected_keys = {(firm, month) for firm in "ABC" for month in ("2024-01", "2024-02")}
    cutoff = date(2024, 3, 15)
    saved = deepcopy(records)
    selected = freeze(records, cutoff, expected_keys)
    require(records == saved, "panel selector mutated input")
    observed = [(row["x"], row["y"]) for row in selected]
    require([row["y"] for row in selected] == list(map(F, (2, 4, 5, 3, 4, 6))),
            "historical selected y")
    for order in permutations(records):
        require(freeze(order, cutoff, expected_keys) == selected, "selection order dependence")
    require(selected[3]["y"] - selected[0]["y"] == 1, "calendar change under vintage")
    malformed = []
    malformed.append(records + [deepcopy(records[0])])
    malformed.append([row for row in records if (row["firm"], row["month"]) != ("B", "2024-01")])
    premature = deepcopy(records)
    premature[0]["release"] = "2024-01-15"
    malformed.append(premature)
    altered_dose = deepcopy(records)
    altered_dose[1]["x"] = F(2)
    malformed.append(altered_dose)
    negative = deepcopy(records)
    negative[0]["y"] = F(-1)
    malformed.append(negative)
    for bad_rows in malformed:
        try:
            freeze(bad_rows, cutoff, expected_keys)
        except (ValueError, TypeError):
            pass
        else:
            raise ValueError("malformed panel accepted")
    intercept, slope, residual = fit_line(observed)
    require((intercept, slope) == (F(5, 2), F(3, 2)), "OLS coefficients")
    require(residual == [F(-1, 2), F(0), F(-1, 2), F(1, 2), F(0), F(1, 2)],
            "OLS residuals")
    require(sum(residual) == sum(x * e for (x, y), e in zip(observed, residual)) == 0,
            "OLS normal equations")
    sse = sum(e * e for e in residual)
    require(sse == 1 and sse * 100 ** 2 == 10000, "SSE squared units")
    for da, db in product((F(-2), F(-1, 2), F(0), F(1, 3), F(2)), repeat=2):
        candidate_sse = sum((y - intercept - da - (slope + db) * x) ** 2 for x, y in observed)
        require(candidate_sse == sse + sum((da + db * x) ** 2 for x, y in observed),
                "projection minimization identity")
    mean_forecast = average([y for x, y in observed])
    holdout = []
    for month, role, release, *ys in fragment.tables["foundation-a-holdout"][1:]:
        values = list(map(F, ys))
        line_mse = average([(y - intercept - slope * x) ** 2 for x, y in zip(map(F, range(3)), values)])
        constant_mse = average([(y - mean_forecast) ** 2 for y in values])
        holdout.append({"month": month, "role": role, "release": date.fromisoformat(release),
                        "line_mse": line_mse, "constant_mse": constant_mse})
    require((holdout[0]["line_mse"], holdout[0]["constant_mse"]) == (F(7, 6), F(11, 3)),
            "validation losses")
    require((holdout[1]["line_mse"], holdout[1]["constant_mse"]) == (F(3, 2), F(0)),
            "final losses")
    require(cutoff < date(2024, 4, 1) and holdout[0]["release"] < date(2024, 5, 11)
            < date(2024, 6, 1) < holdout[1]["release"] == date(2024, 7, 10),
            "forecast/selection/label chronology")
    revised = freeze(records, date(2024, 5, 11), expected_keys)
    new_a, new_b, _ = fit_line([(row["x"], row["y"]) for row in revised])
    require((new_a, new_b) == (F(10, 3), F(1)), "later-vintage line differs")
    require(revised[0]["release"] == "2024-03-20" and revised[0]["y"] == 4,
            "revision eligibility at later origin")
    wrong_historical_val_mse = average([(F(y) - new_a - new_b * x) ** 2
                                       for x, y in zip(map(F, range(3)), (3, 5, 7))])
    require(wrong_historical_val_mse == F(10, 9) != holdout[0]["line_mse"],
            "future revision changes falsely labeled historical score")
    sizes = {"A": "small", "B": "large", "C": "large"}
    large_zero = [row for row in selected if sizes[row["firm"]] == "large" and row["x"] == 0]
    require(not large_zero, "missing large-zero support cell")
    results["D4"] = {"selected_y": [str(row["y"]) for row in selected],
                     "A_month_change": "1", "intercept": str(intercept), "slope": str(slope),
                     "SSE_squared_hundreds": str(sse),
                     "validation_line_constant_MSE": [str(holdout[0][name]) for name in ("line_mse", "constant_mse")],
                     "final_line_constant_MSE": [str(holdout[1][name]) for name in ("line_mse", "constant_mse")],
                     "final_full_score_after_release": "2024-07-10",
                     "revision_fit_intercept_slope": [str(new_a), str(new_b)],
                     "revision_based_April_MSE": str(wrong_historical_val_mse),
                     "row_permutations_checked": 5040, "invalid_panels_rejected": len(malformed)}
    checks.append("D4: actual manuscript tables,5040 release-history row permutations, "
                  "nonmutation and five meaningful failure cases; independent normal-equation "
                  "elimination and25 projection identities; holdout scores/release chronology, "
                  "later-revision score change and explicit missing causal-support cell.")
    return {"status": "passed", "assessment": "foundation-form-a", "checks": checks,
            "results": results, "limitations": [
                "Finite numerical checks supplement separately reviewed proofs, interpretations and rubrics; they do not validate every possible input or economic model.",
                "All quantities and release histories are synthetic; no empirical investment return, causal effect, population law or real predictive accuracy is established.",
                "Confidence coverage uses the supplied iid known-variance normal model and rounded1.96 quantile; no posterior for the mean was specified.",
                "Causal support, source credibility and financial feasibility remain substantive conditions rather than consequences of algebraic agreement.",
                "No visual/mobile/print inspection or empirical learner difficulty/timing study was performed."
            ]}


if __name__ == "__main__":
    try:
        result = check()
    except Exception as error:
        print(json.dumps({"status": "failed", "error": str(error)}, indent=2))
        raise SystemExit(1)
    print(json.dumps(result, indent=2))
