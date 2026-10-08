#!/usr/bin/env python3
"""Bounded, independent mathematical and fragment checks for v05-c02.

Standard library only; quiet import; no network or file writes. Exact rational
certificates check the original cases, while quadrature and finite differences
cross-check separately computed welfare and derivative results. Finite numerical
checks supplement, rather than prove, the manuscript's general arguments.
"""
from fractions import Fraction as F
from html.parser import HTMLParser
from itertools import product
import json
import math
from pathlib import Path


BOOK = Path(__file__).resolve().parents[1]
CHAPTER = BOOK / "content/chapters/v05-c02.html"
SOURCES = BOOK / "content/reviews/v05-c02-sources.json"


def require(condition, label):
    if not condition:
        raise AssertionError(label)


def close(actual, expected, label, tolerance=1e-9):
    require(math.isfinite(actual) and math.isfinite(expected), label + ": finite")
    require(math.isclose(actual, expected, rel_tol=tolerance, abs_tol=tolerance),
            f"{label}: {actual!r} != {expected!r}")


def rational_sqrt(value):
    value = F(value)
    a, b = math.isqrt(value.numerator), math.isqrt(value.denominator)
    require(a * a == value.numerator and b * b == value.denominator,
            "case requires a rational square root")
    return F(a, b)


def dot(a, b):
    return sum((x * y for x, y in zip(a, b)), F(0))


def mv(matrix, vector):
    return tuple(dot(row, vector) for row in matrix)


def cd_budget(p, m):
    """Exact equal-spending optimizer and utility for rational-square cases."""
    p, m = tuple(map(F, p)), F(m)
    x = tuple(m / (2 * price) for price in p)
    require(dot(p, x) == m, "CD budget exhausted")
    require(p[0] * x[0] == p[1] * x[1], "CD AM-GM equality")
    return x, rational_sqrt(x[0] * x[1])


def cd_target(p, u):
    """Solve utility/product and equal-cost equations, certify global minimum."""
    p, u = tuple(map(F, p)), F(u)
    x1 = rational_sqrt(u * u * p[1] / p[0])
    x2 = u * u / x1 if x1 else F(0)
    x = (x1, x2)
    cost = dot(p, x)
    require(x1 * x2 == u * u, "CD target attained")
    require(p[0] * x1 == p[1] * x2, "CD equal-cost certificate")
    require(cost * cost == 4 * p[0] * p[1] * u * u,
            "CD cost reaches squared AM-GM lower bound")
    return x, cost


def cd_derivatives(p, m):
    """Compare expenditure Hessian to Marshallian chain-rule expression."""
    p, m = tuple(map(F, p)), F(m)
    x, u = cd_budget(p, m)
    dx = ((-m / (2 * p[0] ** 2), F(0)),
          (F(0), -m / (2 * p[1] ** 2)))
    dm = tuple(1 / (2 * value) for value in p)
    slutsky = tuple(tuple(dx[i][j] + dm[i] * x[j] for j in range(2))
                    for i in range(2))
    e = dot(p, x)
    hessian = ((-e / (4 * p[0] ** 2), e / (4 * p[0] * p[1])),
               (e / (4 * p[0] * p[1]), -e / (4 * p[1] ** 2)))
    require(slutsky == hessian, "Slutsky from two analytic routes")
    require(slutsky[0][1] == slutsky[1][0], "symmetry")
    require(mv(slutsky, p) == (0, 0), "price null vector")
    for d in product(range(-3, 4), repeat=2):
        quadratic = dot(d, mv(slutsky, d))
        square = -e / 4 * (F(d[0]) / p[0] - F(d[1]) / p[1]) ** 2
        require(quadratic == square and quadratic <= 0,
                "exact negative-square identity")
    vm = 1 / (2 * rational_sqrt(p[0] * p[1]))
    vp = tuple(-m * vm / (2 * value) for value in p)
    require(tuple(-value / vm for value in vp) == x, "Roy ratio")
    return x, u, dx, dm, slutsky, vp, vm


def simpson(function, lower, upper, steps=2048):
    step = (upper - lower) / steps
    total = function(lower) + function(upper)
    total += 4 * math.fsum(function(lower + i * step)
                          for i in range(1, steps, 2))
    total += 2 * math.fsum(function(lower + i * step)
                          for i in range(2, steps, 2))
    return total * step / 3


def ql_target_reference(p, u):
    """Independent finite candidates in s=sqrt(q), with feasible z restored.

    On 0 <= s <= u/2, cost is a quadratic with possible stationary s=1/p;
    on s >= u/2, p*s*s increases. Endpoints plus that stationary point suffice.
    """
    p, u = F(p), F(u)
    candidates = {F(0), u / 2}
    if 0 <= 1 / p <= u / 2:
        candidates.add(1 / p)
    choices = []
    for s in candidates:
        q, z = s * s, max(u - 2 * s, F(0))
        choices.append((p * q + z, q, z, s))
    cost, q, z, s = min(choices)
    require(2 * s + z == u, "quasilinear exact target")
    return cost, q, z


def ql_piecewise(p, u):
    p, u = F(p), F(u)
    if u <= 2 / p:
        return p * u * u / 4, u * u / 4, F(0)
    return u - 1 / p, 1 / (p * p), u - 2 / p


def ql_budget_reference(p, m):
    """Completed-square objective in s, independently clamped to feasibility."""
    p, m = F(p), F(m)
    upper = rational_sqrt(m / p)
    s = min(1 / p, upper)
    q, z = s * s, m - p * s * s
    value = 2 * s + z
    require(value == m + 1 / p - p * (s - 1 / p) ** 2,
            "quasilinear completed-square budget certificate")
    require(z >= 0, "quasilinear numeraire feasible")
    return q, z, value


class Fragment(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.worked = 0
        self.h1 = 0
        self.exercises = 0
        self.solutions = 0
        self.depth = 0
        self.exercise_depth = None
        self.solution_depth = None
        self.details_solution = False
        self.sources = []
        self.ids = []
        self.links = []
        self.text = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "h1":
            self.h1 += 1
        if "id" in attrs:
            self.ids.append(attrs["id"])
        if "data-source" in attrs:
            self.sources.extend(attrs["data-source"].split())
        if tag == "a":
            self.links.append(attrs.get("href", ""))
        if tag == "aside" and attrs.get("class") == "worked":
            self.worked += 1
        if tag == "details":
            self.details_solution = attrs.get("class") == "solutions"
        if tag == "ol":
            self.depth += 1
            if attrs.get("class") == "exercises":
                self.exercise_depth = self.depth
            elif self.details_solution:
                self.solution_depth = self.depth
        if tag == "li":
            if self.depth == self.exercise_depth:
                self.exercises += 1
            if self.depth == self.solution_depth:
                self.solutions += 1

    def handle_endtag(self, tag):
        if tag == "ol":
            if self.depth == self.exercise_depth:
                self.exercise_depth = None
            if self.depth == self.solution_depth:
                self.solution_depth = None
            self.depth -= 1
        if tag == "details":
            self.details_solution = False

    def handle_data(self, text):
        self.text.append(text)


def check():
    checks = []
    # Worked example 1 and exercise 3: independent exact certificates.
    w1 = cd_derivatives((2, 8), 96)
    require(w1[:2] == ((24, 6), 12), "worked 1 demand/utility")
    require(w1[2] == ((-12, 0), (0, F(-3, 4))), "worked 1 demand Jacobian")
    require(w1[3] == (F(1, 4), F(1, 16)), "worked 1 income response")
    require(w1[4] == ((-6, F(3, 2)), (F(3, 2), F(-3, 8))),
            "worked 1 Slutsky matrix")
    require(w1[5][0] == -3 and w1[6] == F(1, 8), "worked 1 Roy inputs")
    ex3 = cd_derivatives((4, 1), 40)
    require(ex3[:2] == ((5, 20), 10), "exercise 3 demand/utility")
    require(ex3[2] == ((F(-5, 4), 0), (0, -20)), "exercise 3 Jacobian")
    require(ex3[3] == (F(1, 8), F(1, 2)), "exercise 3 income response")
    require(ex3[4] == ((F(-5, 8), F(5, 2)), (F(5, 2), -10)),
            "exercise 3 Slutsky matrix")
    require(ex3[5] == (F(-5, 4), -5) and ex3[6] == F(1, 4),
            "exercise 3 Roy inputs")
    checks.append("Worked 1 and exercise 3: exact global AM-GM certificates, both Slutsky routes, Roy, symmetry, homogeneity and 98 negative-square evaluations")

    # Differentiated targets compared with numerical perturbations at five prices.
    for a, b, income in ((2, 8, 96), (4, 1, 40), (3, 12, 72),
                         (9, 1, 60), (4, 9, 24)):
        u = income / (2 * math.sqrt(a * b))
        h = lambda p1, p2: (u * math.sqrt(p2 / p1),
                            u * math.sqrt(p1 / p2))
        expected = ((-income / (4 * a * a), income / (4 * a * b)),
                    (income / (4 * a * b), -income / (4 * b * b)))
        for j in range(2):
            step = (a, b)[j] * 1e-5
            left, right = [float(a), float(b)], [float(a), float(b)]
            left[j] -= step
            right[j] += step
            hl, hr = h(*left), h(*right)
            for i in range(2):
                close((hr[i] - hl[i]) / (2 * step), expected[i][j],
                      "compensated finite difference", 2e-9)
    checks.append("Twenty central-difference responses cross-check compensated Hessian entries at five distinct price/income cases")

    # Exercise 1 and the ordinal transformation caveat.
    require(cd_budget((3, 12), 72) == ((12, 3), 6), "exercise 1 budget")
    require(cd_target((3, 12), 9) == ((18, F(9, 2)), 108), "exercise 1 target")
    require(cd_budget((3, 12), 108) == ((18, F(9, 2)), 9), "exercise 1 duality")
    require(cd_target((6, 24), 9) == ((18, F(9, 2)), 216), "exercise 1 homogeneity")
    require((9 - 6) ** 3 == 27 and 3 * (6 - 6) ** 2 == 0,
            "exercise 1 transformed target and zero derivative")
    # Exercise 2: actual sets on the one-good budget, including slack maximizers.
    for x in (F(2), F(5, 2), F(3), F(4)):
        require(3 * x <= 12 and min(x, 2) == 2, "satiation set membership")
    require(3 * F(2) == 6 < 12 and 1 + F(0) == 1 > 0,
            "two different failed duality assumptions")
    checks.append("Exercises 1–2: exact matched targets, nominal scaling, ordinal zero-derivative Roy caveat and separate satiation/below-origin-target counterexamples")

    # Exercise 4: rational signs and a direction violating matrix concavity.
    require(F(-8, 5) - 8 * F(-3, 10) == F(4, 5), "Giffen response")
    require(F(-8, 5) - 8 * F(-1, 10) == F(-4, 5), "inferior non-Giffen response")
    require(F(-8, 5) / 8 == F(-1, 5), "Giffen income threshold")
    bad = ((-1, 2), (2, -1))
    require(dot((1, 1), mv(bad, (1, 1))) == 2, "bad curvature direction")
    checks.append("Exercise 4: Giffen threshold and a matrix with negative diagonals but positive quadratic form")

    # Exercise 5: exact kink and supporting inequality for distinct selected minima.
    linear_e = lambda p: 12 * min(F(p[0], 2), F(p[1]))
    for eps in (F(1, 10), F(1, 1000), F(1, 100000)):
        require((linear_e((6, 3)) - linear_e((6 - eps, 3))) / eps == 6,
                "left kink slope")
        require((linear_e((6 + eps, 3)) - linear_e((6, 3))) / eps == 0,
                "right kink slope")
    b, c = (3, 6), (0, 12)
    for x1 in (F(0), F(1, 3), F(3), F(17, 3), F(6)):
        x2 = 12 - 2 * x1
        require(x1 >= 0 and x2 >= 0 and 6 * x1 + 3 * x2 == 36,
                "tie segment feasibility and equal cost")
    require(dot((2, 0), tuple(c[i] - b[i] for i in range(2))) == -6,
            "finite compensated law")
    for r in product((F(1, 2), F(2), F(3), F(6), F(8)), repeat=2):
        require(linear_e(r) <= 36 + dot(tuple(r[i] - (6, 3)[i] for i in range(2)), b),
                "selected minimizer supporting inequality")
    checks.append("Exercise 5: exact one-sided kink slopes, five points on the minimizing segment, compensated-law sign and 25 support checks")

    # Worked 2, exercise 6, and retention: value differences versus independent areas.
    welfare = []
    for p0, p1, m, expected_cv, expected_ev in (
            ((2, 8), (8, 8), 96, 96, 48),
            ((9, 1), (4, 1), 60, -20, -30),
            ((1, 4), (4, 4), 24, 24, 12)):
        x0, u0 = cd_budget(p0, m)
        x1, u1 = cd_budget(p1, m)
        _, restoration = cd_target(p1, u0)
        _, equivalent = cd_target(p0, u1)
        cv, ev = restoration - m, m - equivalent
        require((cv, ev) == (expected_cv, expected_ev), "welfare exact amounts")
        require(cd_budget(p1, m + cv)[1] == u0, "CV indifference")
        require(cd_budget(p0, m - ev)[1] == u1, "EV indifference")
        cs = m / 2 * math.log(p1[0] / p0[0])
        cs_quad = simpson(lambda price: m / (2 * price), p0[0], p1[0])
        cv_quad = simpson(lambda price: float(u0) * math.sqrt(p0[1] / price),
                          p0[0], p1[0])
        ev_quad = simpson(lambda price: float(u1) * math.sqrt(p0[1] / price),
                          p0[0], p1[0])
        close(cs_quad, cs, "CS independent quadrature")
        close(cv_quad, float(cv), "CV independent quadrature")
        close(ev_quad, float(ev), "EV independent quadrature")
        basket = dot(p1, x0) - m
        require(cv <= basket, "old-basket upper bound, including gain")
        welfare.append({"p0": p0, "p1": p1, "income": m,
                        "CV": str(cv), "EV": str(ev),
                        "CS_loss": cs, "old_basket_change": str(basket),
                        "initial_bundle": list(map(str, x0)),
                        "final_bundle": list(map(str, x1))})
    require(welfare[0]["old_basket_change"] == "144", "worked 2 basket amount")
    require(welfare[1]["old_basket_change"] == "-50/3", "exercise 6 basket amount")
    checks.append("Worked 2, exercise 6 and delayed check: exact utility targets, signed CV/EV, both indifference equations, old-basket bounds and nine independent quadratures")

    # Worked 3 and exercise 7: constrained expenditure, including the zero target.
    grid_cases = 0
    for p in (F(1, 4), F(1, 2), F(1), F(8, 5), F(2), F(4), F(8)):
        for u in (F(0), F(1, 4), F(1, 2), F(1), F(5, 4), F(2), F(3), F(6)):
            require(ql_target_reference(p, u) == ql_piecewise(p, u),
                    "quasilinear independent candidate minimization")
            grid_cases += 1
        join_u = 2 / p
        require(p * join_u ** 2 / 4 == join_u - 1 / p,
                "quasilinear branch values meet")
        require(join_u ** 2 / 4 == 1 / p ** 2 and join_u - 2 / p == 0,
                "quasilinear branch gradients/bundles meet")
    # Budget optima with rational-square bounds allow exact global certificates.
    require(ql_budget_reference(1, 1) == (1, 0, 2), "exercise 7 initial")
    require(ql_budget_reference(4, 1) == (F(1, 16), F(3, 4), F(5, 4)),
            "exercise 7 final")
    # Worked 3 rational q, z checked without taking the irrational feasible endpoint.
    for p, m, q, z, u in ((1, 5, 1, 4, 6),
                         (2, 5, F(1, 4), F(9, 2), F(11, 2))):
        require(p * q + z == m and z > 0, "worked 3 budget/interior")
        require(2 * rational_sqrt(q) + z == u, "worked 3 utility")
        require(rational_sqrt(q) == F(1, p), "worked 3 stationary maximum")
    w3_cv = ql_target_reference(2, 6)[0] - 5
    w3_ev = 5 - ql_target_reference(1, F(11, 2))[0]
    require(w3_cv == w3_ev == F(1, 2), "worked 3 welfare")
    close(simpson(lambda p: 1 / p ** 2, 1, 2), .5, "worked 3 area")
    ex7_cv = ql_target_reference(4, 2)[0] - 1
    ex7_ev = 1 - ql_target_reference(1, F(5, 4))[0]
    require((ex7_cv, ex7_ev) == (F(3, 4), F(39, 64)), "exercise 7 welfare")
    require(F(2) / F(5, 4) == F(8, 5), "exercise 7 branch crossing")
    require(F(25, 64) * F(3, 5) + F(5, 8) - F(1, 4) == ex7_ev,
            "exercise 7 exact piecewise Hicksian integral")
    ev_quad = simpson(lambda p: 25 / 64, 1, 8 / 5)
    ev_quad += simpson(lambda p: 1 / p ** 2, 8 / 5, 4)
    close(ev_quad, float(ex7_ev), "exercise 7 numerical Hicksian integral")
    close(simpson(lambda p: 1 / p ** 2, 1, 4), .75, "exercise 7 CS integral")
    checks.append(f"Worked 3 and exercise 7: {grid_cases} exact expenditure candidate checks, boundary continuity, certified budget optima, corner crossing and exact/numerical area comparison")

    # Exercise 8: recipient-level restoration, independently computed actual utilities.
    individual = []
    for income in (40, 120):
        _, old_u = cd_budget((1, 4), income)
        _, restoration = cd_target((4, 4), old_u)
        _, actual_u = cd_budget((4, 4), income + 90)
        individual.append((income, restoration - income, old_u, actual_u))
    require(individual == [(40, 40, 10, F(65, 4)), (120, 120, 30, F(105, 4))],
            "exercise 8 unequal compensation despite equal transfers")
    require(180 > sum(row[1] for row in individual), "aggregate grant exceeds CV")
    require(cd_budget((4, 4), 40 + 40)[1] == 10, "alternative grant first household")
    require(cd_budget((4, 4), 120 + 140)[1] == F(65, 2), "alternative grant second household")
    checks.append("Exercise 8: total versus individual compensation and feasible alternative grant allocation")

    fragment = Fragment()
    html = CHAPTER.read_text(encoding="utf-8")
    fragment.feed(html)
    fragment.close()
    require(fragment.worked == 3 and fragment.exercises == fragment.solutions == 8,
            "three worked examples and eight matching exercises/solutions")
    require(fragment.h1 == 0 and fragment.depth == 0, "fragment heading/list structure")
    require(len(fragment.ids) == len(set(fragment.ids)), "unique fragment IDs")
    text = " ".join(fragment.text)
    for required in ("Capability:", "Prerequisite:", "Teach-back:", "Delayed check:",
                     "positive-loss convention", "locally nonsatiated",
                     "negative semidefinite", "v05-c03.html"):
        require(required in (html if required.endswith(".html") else text),
                "instructional anchor " + required)
    require("v05-c01.html" in fragment.links and "v05-c03.html" in fragment.links,
            "adjacent chapter routes")
    proposals = json.loads(SOURCES.read_text(encoding="utf-8"))
    require(isinstance(proposals, list) and len(proposals) == 2, "two scoped primary sources")
    ids = set()
    for source in proposals:
        require(set(source) == {"id", "title", "url", "use", "checked", "verification"},
                "source schema")
        require(source["id"].startswith("v05-c02-") and source["id"] not in ids,
                "source ID prefix/uniqueness")
        require(source["url"].startswith("https://ocw.mit.edu/"), "official source domain")
        ids.add(source["id"])
    require(set(fragment.sources) == ids, "source proposal/citation match")
    checks.append("Static fragment: three worked examples, eight complete matched solution items, retention closure, source schema and citations, unique anchors and adjacent routes")

    return {
        "chapter": "v05-c02",
        "status": "passed",
        "checks": checks,
        "reference_values": {
            "cobb_douglas_welfare_cases": welfare,
            "quasilinear_interior_CV_EV_CS": "1/2",
            "quasilinear_boundary_CV_CS": "3/4",
            "quasilinear_boundary_EV": "39/64",
            "quasilinear_boundary_crossing_price": "8/5",
            "grant_initial_utilities": ["10", "30"],
            "grant_actual_utilities": ["65/4", "105/4"],
        },
        "limitations": [
            "General existence, duality, envelope and curvature claims require mathematical review; finite arithmetic checks do not prove the theorems.",
            "Quadrature and finite differences are bounded cross-checks with stated tolerances, independent of the exact rational case certificates.",
            "Examples are synthetic consumer models, not empirical demand estimates or current observations.",
            "Source inspection is recorded separately; this checker neither retrieves sources nor certifies whole documents.",
            "No visual, mobile, print, external-human or whole-library integration review is claimed; root owns acceptance and shared integration.",
        ],
    }


if __name__ == "__main__":
    print(json.dumps(check(), indent=2, ensure_ascii=False))
