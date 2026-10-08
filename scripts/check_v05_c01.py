"""Independent arithmetic and boundary audit of v05-c01 consumer choice.

Uses exact references, separate objective comparisons and revealed-affordability
graphs. Finite checks supplement the manuscript's analytic proofs.
"""
from fractions import Fraction as F
from html.parser import HTMLParser
from itertools import product
from math import isclose, log, sqrt
from pathlib import Path
import json
import re


ROOT = Path(__file__).resolve().parents[1]
CHAPTER = ROOT / "content/chapters/v05-c01.html"
SOURCES = ROOT / "content/reviews/v05-c01-sources.json"


def require(condition, message):
    if not condition:
        raise ValueError(message)


class Structure(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.lists, self.ids, self.sources, self.links = [], [], [], [], []
        self.worked = self.exercises = self.solutions = self.solution_blocks = 0
        self.in_solutions = False
        self.h1 = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag not in ("br", "hr", "img", "meta", "link", "input"):
            self.stack.append(tag)
        self.h1 += tag == "h1"
        if "id" in attrs:
            self.ids.append(attrs["id"])
        if "data-source" in attrs:
            self.sources.append(attrs["data-source"])
        if tag == "a":
            self.links.append(attrs.get("href", ""))
        if tag == "aside" and attrs.get("class") == "worked":
            self.worked += 1
        if tag == "details" and attrs.get("class") == "solutions":
            self.in_solutions = True
            self.solution_blocks += 1
        if tag == "ol":
            self.lists.append(attrs.get("class"))
        if tag == "li" and self.lists:
            if self.lists[-1] == "exercises":
                self.exercises += 1
            elif self.in_solutions:
                self.solutions += 1

    def handle_endtag(self, tag):
        require(bool(self.stack) and self.stack.pop() == tag, "unbalanced HTML at " + tag)
        if tag == "ol":
            self.lists.pop()
        if tag == "details":
            self.in_solutions = False


def prices_income(prices, income):
    require(len(prices) == 2 and all(p > 0 for p in prices), "strictly positive two-good prices")
    require(income >= 0, "nonnegative income")


def spend(prices, bundle):
    return sum(p * x for p, x in zip(prices, bundle))


def cobb_douglas(a, b, prices, income):
    prices_income(prices, income)
    require(a > 0 and b > 0, "positive utility exponents")
    return (F(a, a + b) * income / prices[0],
            F(b, a + b) * income / prices[1])


def shifted_log(a, prices, income, ration=None):
    prices_income(prices, income)
    require(a > 0, "positive log coefficient")
    upper = income / prices[0]
    if ration is not None:
        require(ration >= 0, "nonnegative ration")
        upper = min(upper, ration)
    x = min(upper, max(F(0), a * prices[1] / prices[0] - 1))
    return x, (income - prices[0] * x) / prices[1]


def proportions(a, b, prices, income):
    prices_income(prices, income)
    require(a > 0 and b > 0, "positive recipe amounts")
    t = income / (a * prices[0] + b * prices[1])
    return a * t, b * t


def costs(prices, choices):
    return [[spend(price, bundle) for bundle in choices] for price in prices]


def pair_violations(matrix, choices, unique):
    violations = []
    for t, s in product(range(len(matrix)), repeat=2):
        if t == s or choices[t] == choices[s]:
            continue
        if matrix[t][s] <= matrix[t][t]:
            reverse = matrix[s][t] <= matrix[s][s] if unique else matrix[s][t] < matrix[s][s]
            if reverse:
                violations.append((t, s))
    return violations


def chain_violations(matrix):
    n = len(matrix)
    reachable = [[matrix[t][s] <= matrix[t][t] for s in range(n)] for t in range(n)]
    for middle in range(n):
        for start in range(n):
            for end in range(n):
                reachable[start][end] = reachable[start][end] or (
                    reachable[start][middle] and reachable[middle][end])
    return [(t, s) for t, s in product(range(n), repeat=2)
            if reachable[t][s] and matrix[s][t] < matrix[s][s]]


def check():
    text = CHAPTER.read_text(encoding="utf-8")
    parser = Structure()
    parser.feed(text)
    require(not parser.stack and parser.h1 == 0, "fragment must be balanced without h1")
    require(parser.worked >= 2 and parser.exercises == parser.solutions == 8,
            "worked/example/solution structure")
    require(parser.solution_blocks == 1 and len(parser.ids) == len(set(parser.ids)),
            "solution block or ID duplication")
    for term in ("Capability:", "Prerequisites:", "Teach-back", "Delayed check",
                 "correspondence", "local nonsatiation", "WARP"):
        require(term in text, "instructional requirement: " + term)
    proposals = json.loads(SOURCES.read_text(encoding="utf-8"))
    required_fields = {"id", "title", "url", "use", "checked", "verification"}
    require(all(set(source) == required_fields and source["id"].startswith("v05-c01-")
                and all(type(source[key]) is str and source[key] for key in required_fields)
                for source in proposals), "source proposal schema")
    require(len({source["id"] for source in proposals}) == len(proposals), "source IDs unique")
    require(set(parser.sources) == {source["id"] for source in proposals}, "source use alignment")
    require("foundation-assessment.html" in parser.links and "v05-c02.html" in parser.links,
            "foundation/successor route")
    for link in parser.links:
        if re.fullmatch(r"v\d{2}-c\d{2}\.html", link) and link != "v05-c02.html":
            require((ROOT / "content/chapters" / link).is_file(), "missing prior chapter " + link)
    checks = ["Balanced static fragment with three worked examples, eight matched "
              "exercise/solution items, teaching checks, foundation/successor links and three scoped source proposals."]
    results = {}

    # Ordinal transformations: compare complete finite grids of deterministic
    # bundles, and separately construct an expected-utility reversal.
    bundles = list(product(map(F, range(5)), repeat=2))
    for x, y in product(bundles, repeat=2):
        ux, uy = sum(x), sum(y)
        require((ux >= uy) == (ux ** 3 >= uy ** 3), "ordinal cube order")
    ua, ub = F(3), F(4)
    require(ua < ub and -ua > -ub and (ua - 5) ** 2 > (ub - 5) ** 2,
            "nonmonotone/decreasing transformation counterexamples")
    require(F(6, 5) > F(0 + 2, 2) and F(6, 5) ** 3 < F(0 + 8, 2),
            "Bernoulli transformation reverses expected utility")
    require(F(1) ** 3 < F(0 ** 3 + 2 ** 3, 2), "convex preference representation need not be concave")
    for k in range(1, 21):
        require(F(1, k) > 0, "lexicographic first-coordinate priority")
    results["ordinal"] = {"ranking_pair": ["3", "4"], "squared_shift_pair": ["4", "1"],
                          "original_certain_vs_lottery": ["6/5", "1"],
                          "cubed_certain_vs_lottery": ["216/125", "4"]}
    checks.append("Ordinal rankings checked on625 bundle pairs; concavity and "
                  "expected-utility transformation counterexamples verified separately.")

    # Satiation and budget domains are separate from arithmetic optimality.
    bliss = (F(1), F(2))
    p, income = (F(3), F(2)), F(12)
    require(spend(p, bliss) == 7 and income - spend(p, bliss) == 5, "satiated budget slack")
    for x, y in product(map(F, range(5)), repeat=2):
        utility = -(x - 1) ** 2 - (y - 2) ** 2
        require(utility <= 0 and (utility == 0) == ((x, y) == bliss), "unique bliss value")
    for scale, bundle in product((F(1, 3), F(2), F(7, 2)), bundles):
        require((spend(p, bundle) <= income) ==
                (spend(tuple(scale * value for value in p), bundle) <= scale * income),
                "budget homogeneity")
    require(all((spend(p, bundle) <= 0) == (bundle == (0, 0)) for bundle in bundles),
            "zero income singleton")
    for n in range(1, 20):
        require(spend((F(0), F(2)), (F(n), F(6))) == 12 and n + 1 + 6 > n + 6,
                "free good improvement sequence")
    results["budget"] = {"bliss_demand": ["1", "2"], "expenditure": "7", "slack": "5"}
    checks.append("Budget scaling, zero-income singleton, bliss-point slack and "
                  "unbounded free-good improvement sequence checked independently of tangency.")

    # For x1^2*x2, a polynomial factorization gives an exact global comparison
    # distinct from the manuscript's logarithmic Hessian/KKT proof.
    cd_cases = 0
    for p1, p2, m in product((F(1), F(3), F(4)), (F(1), F(2), F(6)),
                              (F(6), F(18), F(90))):
        optimum = cobb_douglas(2, 1, (p1, p2), m)
        require(spend((p1, p2), optimum) == m, "Cobb-Douglas budget")
        r, second = optimum
        max_u = r ** 2 * second
        for k in range(21):
            x = m / p1 * F(k, 20)
            y = (m - p1 * x) / p2
            gap = max_u - x ** 2 * y
            factorized = (r - x) ** 2 * (p1 * x / p2 + m / (3 * p2))
            require(gap == factorized >= 0, "exact cubic global objective difference")
        cd_cases += 1
    require(cobb_douglas(2, 1, (F(4), F(6)), F(90)) == (15, 5), "worked interior demand")
    require(cobb_douglas(2, 1, (F(5), F(6)), F(90)) == (12, 5), "relative price change")
    require(cobb_douglas(2, 1, (F(8), F(12)), F(180)) == (15, 5), "common nominal scaling")
    for prices, m, expected in [((F(2), F(5)), F(50), (15, 4)),
                                ((F(1), F(5)), F(50), (30, 4)),
                                ((F(4), F(10)), F(100), (15, 4))]:
        optimum = cobb_douglas(3, 2, prices, m)
        require(optimum == expected, "exercise demand transfer")
        best = optimum[0] ** 3 * optimum[1] ** 2
        for k in range(101):
            x = m / prices[0] * F(k, 100)
            y = (m - prices[0] * x) / prices[1]
            require(x ** 3 * y ** 2 <= best, "independent exercise budget-grid comparison")
    require(F(3 * 4, 2 * 15) == F(2, 5), "exercise MRS")
    results["smooth_demand"] = {"worked": ["15", "5"], "exercise": ["15", "4"],
                                "exercise_MRS": "2/5", "exact_global_cases": cd_cases}
    checks.append("Smooth demand:27 exact polynomial global-optimum certificates "
                  "across budget grids, separate exponent-transfer objective checks, prices/income scaling and MRS.")

    # Shifted-log choices checked with a separate derivative-bisection oracle
    # and exact KKT ratios, including all corner and zero-income regimes.
    ql_cases = 0
    for a, p1, p2, m in product((F(1, 2), F(2), F(6), F(9)),
                                (F(1), F(2), F(3), F(7), F(12)),
                                (F(1), F(2)), (F(0), F(1), F(3), F(10), F(18))):
        x, y = shifted_log(a, (p1, p2), m)
        require(x >= 0 and y >= 0 and p1 * x + p2 * y == m, "log choice feasibility")
        derivative = lambda point: float(a) / (1 + point) - float(p1 / p2)
        left, right = 0.0, float(m / p1)
        if derivative(left) <= 0:
            independent_x = left
        elif derivative(right) >= 0:
            independent_x = right
        else:
            for _ in range(70):
                middle = (left + right) / 2
                if derivative(middle) > 0:
                    left = middle
                else:
                    right = middle
            independent_x = (left + right) / 2
        require(isclose(float(x), independent_x, rel_tol=1e-12, abs_tol=1e-12),
                "log derivative-bisection reference")
        if m > 0:
            ratio1, ratio2 = a / (1 + x) / p1, 1 / p2
            multiplier = ratio1 if x > 0 else ratio2
            require((ratio1 == multiplier if x > 0 else ratio1 <= multiplier)
                    and (ratio2 == multiplier if y > 0 else ratio2 <= multiplier),
                    "log exact corner KKT ratios")
        objective = float(a) * log(1 + float(x)) + float(y)
        for k in range(11):
            candidate_x = m / p1 * F(k, 10)
            candidate_y = (m - p1 * candidate_x) / p2
            require(float(a) * log(1 + float(candidate_x)) + float(candidate_y)
                    <= objective + 1e-11, "log direct objective comparison")
        ql_cases += 1
    worked_log = [shifted_log(F(9), tuple(map(F, p)), F(m))
                  for p, m in [((3, 1), 18), ((3, 1), 3), ((12, 1), 18)]]
    require(worked_log == [(2, 12), (1, 0), (0, 18)], "worked log regimes")
    exercise_log = [shifted_log(F(6), tuple(map(F, p)), F(m))
                    for p, m in [((2, 1), 3), ((2, 1), 10), ((7, 1), 10)]]
    require(exercise_log == [(F(3, 2), 0), (2, 6), (0, 10)], "exercise log regimes")
    require(shifted_log(F(6), (F(2), F(1)), F(10), ration=F(1)) == (1, 8), "ration")
    require(F(6, 2) - 2 > 0, "ration has positive budget-line derivative")
    require(shifted_log(F(4), (F(2), F(1)), F(8)) == (1, 6)
            and shifted_log(F(4), (F(2), F(1)), F(1)) == (F(1, 2), 0), "delayed answers")
    results["corners"] = {"worked": [[str(v) for v in pair] for pair in worked_log],
                          "exercise": [[str(v) for v in pair] for pair in exercise_log],
                          "ration": ["1", "8"], "independent_regime_cases": ql_cases}
    checks.append("Shifted-log demand:200 zero-income/interior/corner cases versus "
                  "independent derivative bisection, exact KKT ratios and direct objective comparisons; ration and delayed answers.")

    # Linear utility upper bounds, integer enumeration and fixed recipes test
    # correspondence and kink claims without a differentiable tangency.
    for k in range(25):
        x = F(k, 3)
        y = (24 - 3 * x) / 2
        require(x >= 0 and y >= 0 and 3 * x + 2 * y == 24, "worked substitute segment")
    require(F(3, 4) < F(2, 2) and F(2) * 12 == 24, "substitute price corner")
    integer_bundles = [(x, y) for x in range(10) for y in range(7) if 2 * x + 3 * y <= 18]
    integer_max = max(2 * x + 3 * y for x, y in integer_bundles)
    integer_best = sorted((x, y) for x, y in integer_bundles if 2 * x + 3 * y == integer_max)
    require(integer_best == [(0, 6), (3, 4), (6, 2), (9, 0)], "integer substitute ties")
    require(2 * sqrt(.5) == sqrt(2) and sqrt(2) > 1, "continuous/divisible square-root optimum")
    feasible_integer = [(x, y) for x, y in product(range(2), repeat=2) if x + y <= 1]
    require([point for point in feasible_integer if sum(point) == 1] == [(0, 1), (1, 0)],
            "integer convexity counterexample")
    recipe_cases = [(F(1), F(1, 2), (F(3), F(2)), F(24), (6, 3)),
                    (F(2), F(3), (F(3), F(1)), F(24), (F(16, 3), 8)),
                    (F(2), F(3), (F(6), F(1)), F(24), (F(16, 5), F(24, 5)))]
    for a, b, p, m, expected in recipe_cases:
        chosen = proportions(a, b, p, m)
        require(chosen == expected and spend(p, chosen) == m, "fixed-proportion demands")
        t = min(chosen[0] / a, chosen[1] / b)
        require(t == m / (a * p[0] + b * p[1]), "recipe utility upper bound attained")
        for i, j in product(range(11), repeat=2):
            candidate = (m / p[0] * F(i, 10), m / p[1] * F(j, 10))
            if spend(p, candidate) <= m:
                require(min(candidate[0] / a, candidate[1] / b) <= t, "recipe affordable utility bound")
    require(min(F(2), F(0)) == min(F(3), F(0)) == min(F(5, 2), F(0)),
            "flat contour disproves strict convexity")
    results["ties_and_kinks"] = {"integer_substitute_maximizers": integer_best,
                                 "worked_recipe": ["6", "3"],
                                 "exercise_recipe": ["16/3", "8"],
                                 "changed_price_recipe": ["16/5", "24/5"]}
    checks.append("Substitute demand segment and changed-price corner, all integer "
                  "maximizers, nonconvex integer-feasibility counterexample, and exact recipe utility bounds.")

    choices = [(F(4), F(1)), (F(1), F(4))]
    contradiction = costs([(F(2), F(1)), (F(1), F(2))], choices)
    require(contradiction == [[9, 6], [6, 9]], "pair expenditure matrix")
    require(pair_violations(contradiction, choices, unique=False) == [(0, 1), (1, 0)],
            "tie-permitting WARP detects strict contradiction")
    tied = costs([(F(1), F(1)), (F(1), F(1))], choices)
    require(tied == [[5, 5], [5, 5]], "tied expenditure matrix")
    require(pair_violations(tied, choices, unique=True) == [(0, 1), (1, 0)]
            and not pair_violations(tied, choices, unique=False) and not chain_violations(tied),
            "unique-demand versus tied-selection boundary")
    cycle_choices = [tuple(F(i == j) for j in range(3)) for i in range(3)]
    cycle_prices = [tuple(map(F, row)) for row in [(3, 2, 4), (4, 3, 2), (2, 4, 3)]]
    cycle = costs(cycle_prices, cycle_choices)
    require(cycle == [[3, 2, 4], [4, 3, 2], [2, 4, 3]], "three-good expenditure matrix")
    require(not pair_violations(cycle, cycle_choices, unique=True)
            and not pair_violations(cycle, cycle_choices, unique=False), "pairwise cycle checks")
    require(len(chain_violations(cycle)) == 3, "transitive affordability detects three-cycle")
    # A generated set of exact maximizing demands should pass both versions
    # and all longer-chain necessary restrictions, despite many intersections.
    demands = []
    observed_prices = []
    for p1, p2, m in product((F(1), F(2), F(4)), (F(1), F(3)), (F(12), F(24))):
        observed_prices.append((p1, p2))
        demands.append(cobb_douglas(2, 1, (p1, p2), m))
    generated = costs(observed_prices, demands)
    require(not pair_violations(generated, demands, unique=True)
            and not chain_violations(generated), "optimizing data revealed-consistency")
    results["revealed_preference"] = {"contradiction_matrix": [[int(v) for v in row] for row in contradiction],
                                      "tie_matrix": [[int(v) for v in row] for row in tied],
                                      "cycle_matrix": [[int(v) for v in row] for row in cycle],
                                      "cycle_pair_violations": 0, "cycle_chain_violations": 3,
                                      "generated_optimizing_budgets": len(demands)}
    checks.append("Revealed preference: exact own/cross expenditures distinguish "
                  "strict contradiction, arbitrary tied selections and a pairwise-consistent three-cycle; "
                  "twelve generated optimizing budgets pass pair and chain checks.")
    return {"chapter": "v05-c01", "status": "passed", "checks": checks,
            "results": results, "limitations": [
                "Finite calculations supplement the separately reviewed analytic preference, existence, KKT and revealed-preference arguments; they do not prove a general utility-representation or rationalization theorem.",
                "The numerical cases are synthetic and do not establish actual preferences, causal demand responses or interpersonal welfare comparisons.",
                "Bisection and floating logarithms are checked only as independent numerical references; exact corner inequalities and budget identities retain rational arithmetic.",
                "The checker distinguishes unique full choice from possibly tied observed selections; applying either test to real records requires the corresponding assumptions.",
                "No browser visual/mobile/print QA or learner testing was performed."
            ]}


if __name__ == "__main__":
    try:
        report = check()
    except Exception as error:
        print(json.dumps({"chapter": "v05-c01", "status": "failed", "error": str(error)}, indent=2))
        raise SystemExit(1)
    print(json.dumps(report, indent=2))
