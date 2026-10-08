"""Independent arithmetic/optimization checks for the original v05-c03 cases.

Run from any working directory with Python's standard library. No network or
manuscript writes. Enumeration verifies finite test grids; the manuscript's
analytic arguments, not these grids, establish continuous global theorems.
"""

from fractions import Fraction as F
from html.parser import HTMLParser
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHAPTER = ROOT / "content/chapters/v05-c03.html"


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def close(actual, expected, label, tolerance=1e-7):
    require(math.isclose(actual, expected, abs_tol=tolerance, rel_tol=tolerance),
            f"{label}: {actual} != {expected}")


def primal_smooth(q, w, r):
    """Minimize the original binding constraint in log labor, no demand formula.

    The compact search interval contains all declared chapter cases. The
    objective w*exp(t)+r*q^2/(4*exp(t)) is strictly convex in t.
    """
    lo, hi = -16.0, 16.0
    def value(t):
        labor = math.exp(t)
        return w * labor + r * q * q / (4 * labor)
    for _ in range(180):
        a, b = (2 * lo + hi) / 3, (lo + 2 * hi) / 3
        if value(a) <= value(b):
            hi = b
        else:
            lo = a
    labor = math.exp((lo + hi) / 2)
    capital = q * q / (4 * labor)
    return labor, capital, w * labor + r * capital


def maximizers(grid, objective):
    scores = [(q, objective(q)) for q in grid]
    best = max(v for _, v in scores)
    return {q for q, v in scores if v == best}, best


class Structure(HTMLParser):
    def __init__(self):
        super().__init__()
        self.worked = 0
        self.exercises = 0
        self.solutions = 0
        self.in_exercises = False
        self.in_solutions = False
        self.links = []
        self.sources = set()
        self.forbidden = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in {"h1", "html", "body", "script"}:
            self.forbidden.append(tag)
        if tag == "aside" and attrs.get("class") == "worked":
            self.worked += 1
        if tag == "ol" and attrs.get("class") == "exercises":
            self.in_exercises = True
        if tag == "details" and attrs.get("class") == "solutions":
            self.in_solutions = True
        if tag == "li" and self.in_exercises:
            self.exercises += 1
        if tag == "li" and self.in_solutions:
            self.solutions += 1
        if tag == "a":
            self.links.append(attrs.get("href", ""))
        if "data-source" in attrs:
            self.sources.add(attrs["data-source"])

    def handle_endtag(self, tag):
        if tag == "ol":
            self.in_exercises = False
        if tag == "details":
            self.in_solutions = False


def check():
    checks = []
    f = lambda labor, capital: 2 * math.sqrt(labor * capital)
    h = 1e-4
    close(f(4, 9), 12, "baseline output")
    close((f(4+h, 9)-f(4-h, 9))/(2*h), 1.5, "labor marginal product")
    close((f(4, 9+h)-f(4, 9-h))/(2*h), 2/3, "capital marginal product")
    close(f(16, 36), 48, "constant returns")
    g = lambda labor, capital: labor**0.75 * capital**0.75
    close(g(2, 2), 2*math.sqrt(2), "increasing returns")
    close((g(1+h, 1)-2*g(1, 1)+g(1-h, 1))/h**2,
          -3/16, "diminishing own marginal product", 5e-7)
    require(F(3, 2)/F(2, 3) == F(9, 4), "MRTS")
    checks.append("Finite differences and exact ratios verify both marginal products, the isoquant ratio, scale changes and the increasing-returns/diminishing-product counterexample.")

    # Compare closed-form chapter targets with optimization of the original
    # binding production constraint and exact feasible boundary comparisons.
    cases = [(12, 9, 4, F(4), F(9), F(72)),
             (18, 16, 9, F(27, 4), F(12), F(216)),
             (12, 36, 4, F(2), F(18), F(144)),
             (12, 16, 4, F(3), F(12), F(96))]
    for q, w, r, labor, capital, cost in cases:
        got = primal_smooth(q, w, r)
        for actual, target, name in zip(got, (labor, capital, cost), ("L", "K", "C")):
            close(actual, float(target), f"primal q={q},w={w},r={r}: {name}")
        require(4*labor*capital == q*q and w*labor+r*capital == cost,
                "exact primal feasibility/expenditure")
        for i in range(1, 601):
            other_labor = F(i, 4)
            other_capital = F(q*q, 4)/other_labor
            require(w*other_labor+r*other_capital >= cost, "smooth global comparison")
        # Finite differences of the value, independent of envelope substitution.
        value = lambda a, b: q*math.sqrt(a*b)
        close((value(w+h, r)-value(w-h, r))/(2*h), float(labor), "C_w")
        close((value(w, r+h)-value(w, r-h))/(2*h), float(capital), "C_r")
    # Concavity-in-price diagnostics, distinct from convexity-in-output.
    for w1, r1, w2, r2 in [(1, 9, 9, 1), (4, 4, 9, 16), (16, 9, 25, 4)]:
        for theta in (0, F(1, 4), F(1, 2), F(3, 4), 1):
            mix = math.sqrt(float((theta*w1+(1-theta)*w2)*(theta*r1+(1-theta)*r2)))
            bound = float(theta)*math.sqrt(w1*r1)+float(1-theta)*math.sqrt(w2*r2)
            require(mix >= bound-1e-12, "cost price concavity")
    checks.append("Original-constraint minimization and 2,400 exact feasible comparisons independently recover smooth conditional costs/demands; price finite differences verify Shephard values, including the delayed target.")

    grid = [F(i, 4) for i in range(81)]
    for q, w, r, expected_pair, expected_cost in [
            (12, 9, 4, (F(4), F(6)), F(60)),
            (15, 8, 6, (F(5), F(15, 2)), F(85))]:
        feasible = [(l, k) for l in grid for k in grid if min(3*l, 2*k) >= q]
        best = min(w*l+r*k for l, k in feasible)
        winners = {(l, k) for l, k in feasible if w*l+r*k == best}
        require(best == expected_cost and winners == {expected_pair}, "fixed proportions")
    for q, w, r, expected_pair, expected_cost in [
            (12, 9, 4, (F(0), F(6)), F(24)),
            (15, 8, 6, (F(5), F(0)), F(40))]:
        feasible = [(l, k) for l in grid for k in grid if 3*l+2*k >= q]
        best = min(w*l+r*k for l, k in feasible)
        winners = {(l, k) for l, k in feasible if w*l+r*k == best}
        require(best == expected_cost and winners == {expected_pair}, "substitute corner")
    for q, w, r in [(F(12), F(6), F(4)), (F(15), F(8), F(16, 3))]:
        for i in range(61):
            labor = q/3*F(i, 60)
            capital = (q-3*labor)/2
            require(w*labor+r*capital == w*q/3, "whole tie segment")
    checks.append("Direct two-input enumeration checks fixed-proportions and corner optima; 122 exact segment points verify the substitute tie values and full-segment formula.")

    # Direct labor cost at a fixed plant, then global output enumeration.
    output_grid = [F(i, 4) for i in range(241)]
    sr = lambda q: F(36)+9*q*q/F(36)
    for q in output_grid:
        require(sr(q)-6*q == (q-12)**2/4, "short/long-run envelope gap")
    for p, expected_q, expected_profit in [(4, F(8), F(-20)), (5, F(10), F(-11)), (6, F(12), F(0))]:
        winners, profit = maximizers(output_grid, lambda q: p*q-sr(q))
        require(winners == {expected_q} and profit == expected_profit, "short-run supply")
        labor = expected_q**2/36
        require(9*labor == p*p, "variable labor expenditure")
    q = F(10)
    require((q*q/36, 5*q, 9*q*q/36, sr(q), 5*q-sr(q)) ==
            (F(25, 9), F(50), F(25), F(61), F(-11)), "exercise 4 ledger")
    require((q/2, (sr(q)-36)/q, sr(q)/q) == (F(5), F(5, 2), F(61, 10)), "exercise 4 units")
    require(F(36, 12)+F(12, 4) == 6, "minimum average cost")
    for q in output_grid[1:]:
        require(sr(q)/q >= 6, "average cost global bound")
    checks.append("Direct labor expenditures and exact output enumeration confirm short-run choices, negative-profit operation, all exercise-4 amounts and the pointwise long-run cost bound.")

    # Price grid contains shutdown ties exactly; q eighths contain every
    # positive stationary candidate for the quarter-price grid.
    outputs = [F(i, 8) for i in range(161)]
    def operating_profit(q, p, sunk, fee):
        return -sunk if q == 0 else p*q-(2*q+q*q)-sunk-fee
    for p in [F(i, 4) for i in range(49)]:
        expected = {F(0)} if p < 8 else ({F(0), F(3)} if p == 8 else {(p-2)/2})
        for sunk in (0, 30, 300):
            winners, _ = maximizers(outputs, lambda q: operating_profit(q, p, sunk, 9))
            require(winners == expected, "opening-fee supply and sunk-cost invariance")
    for p, quantities, profit in [(7, {F(0)}, F(-30)), (8, {F(0), F(3)}, F(-30)), (10, {F(4)}, F(-23))]:
        require(maximizers(outputs, lambda q: operating_profit(q, p, 30, 9)) == (quantities, profit), "exercise 5 profit")
    require(maximizers(outputs, lambda q: operating_profit(q, 7, 39, 0)) ==
            ({F(5, 2)}, F(-131, 4)), "newly sunk fee")
    require((F(15, 2)-2)**2/4-9 == F(-23, 16), "delayed opening gain")
    for q in outputs[1:]:
        require(2+q+9/q >= 8, "average avoidable cost lower bound")
    require(4*8-sr(F(8))-1000 == -1020 and -36-1000 == -1036,
            "exercise 8 today")
    require(maximizers(output_grid, lambda q: F(0) if q == 0 else 4*q-sr(q))[0] == {F(0)},
            "exercise 8 avoidable renewal")
    checks.append("Exact enumeration across 49 prices and three unavoidable-cost levels verifies the discontinuous supply correspondence, shutdown tie, already-paid fee change and all current/renewal comparisons.")

    # Law-of-supply test includes nonconvex costs and multiple maximizers.
    prices = [F(i, 4) for i in range(49)]
    choices = [maximizers(outputs, lambda q: operating_profit(q, p, 30, 9))[0] for p in prices]
    for i in range(len(prices)-1):
        require(max(choices[i]) <= min(choices[i+1]), "law of supply with ties")
    cap_grid = [F(i, 4) for i in range(81)]
    for p, expected in [(5, {F(0)}), (6, set(cap_grid)), (7, {F(20)})]:
        require(maximizers(cap_grid, lambda q: (p-6)*q)[0] == expected, "capacity/CRS")
    for n in range(1, 41):
        require(F(1, n)*n == 1 and F(1, n+1) < F(1, n), "zero-price cost infimum sequence")
    previous = -1.0
    for q in (0, 1, 2, 4, 8, 12, 20):
        cost = q-1+math.exp(-q)
        profit = q-cost
        require(cost >= 0 and previous < profit < 1, "finite unattained-profit sequence")
        previous = profit
    close(previous, 1, "profit supremum approach", 3e-9)
    checks.append("Exact price comparisons include ties and nonconvex operating costs; capped constant-returns cases and sequences diagnose unbounded profit, finite nonattainment and zero-price cost nonattainment.")

    html = CHAPTER.read_text(encoding="utf-8")
    structure = Structure()
    structure.feed(html)
    require(not structure.forbidden, "fragment contains forbidden wrapper/script")
    require(structure.worked >= 2 and structure.exercises == structure.solutions == 8, "worked/exercise/solution structure")
    require("Teach-back" in html and "Delayed check" in html and "Delayed-check targets" in html, "retention answers")
    proposed = json.loads((ROOT / "content/reviews/v05-c03-sources.json").read_text())
    expected_ids = {item["id"] for item in proposed}
    require(structure.sources == expected_ids and len(expected_ids) == 3, "source inventory")
    for item in proposed:
        require(set(item) == {"id", "title", "url", "use", "checked", "verification"}, "source fields")
        require(item["id"].startswith("v05-c03-") and item["url"].startswith("https://"), "source scope")
    for link in structure.links:
        if link.startswith("v02-") or link.startswith("v05-"):
            require((ROOT / "content/chapters" / link).exists(), f"missing chapter route {link}")
    checks.append("Static fragment has three worked cases, eight matching complete solutions, retention answers, scoped source records and available prerequisite routes.")
    return {"status": "passed", "checks": checks, "limitations": [
        "Finite grids/finite differences are independent diagnostics; written proofs establish continuous optima, global properties and nonattainment.",
        "Hypothetical technologies and contracts are not empirical estimates, legal accounting rules or causal evidence.",
        "Root retains cross-chapter acceptance and integration; no visual/mobile/print QA or external human certification was performed."]}


if __name__ == "__main__":
    print(json.dumps(check(), indent=2))
