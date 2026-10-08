#!/usr/bin/env python3
"""Independent finite arithmetic and instructional checks for Volume 4 Form B.

Reads the HTML fragment and executes only its two short guard definitions in
memory. No network, files written, third-party packages or manuscript edits.
"""
from fractions import Fraction as F
from html.parser import HTMLParser
from itertools import product
import json
import math
from pathlib import Path
import re
import sqlite3


BOOK = Path(__file__).resolve().parents[1]
FRAGMENT = BOOK / "content/assessment-parts/v04-form-b.html"


def require(condition, label):
    if not condition:
        raise AssertionError(label)


class ExamParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids = []
        self.headings = []
        self.links = []
        self.tables = {}
        self.table = None
        self.row = None
        self.cell = None
        self.codes = {}
        self.code = None
        self.code_text = []
        self.text = []
        self.part_counts = []
        self.part_level = None
        self.ol_depth = 0
        self.solution_items = 0
        self.solution_level = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.ids.append(attrs["id"])
        if tag in ("h1", "h2", "h3"):
            self.headings.append((tag, attrs.get("id")))
        if tag == "a":
            self.links.append(attrs.get("href", ""))
        if tag == "table":
            self.table = attrs.get("id")
            self.tables[self.table] = []
        elif tag == "tr" and self.table:
            self.row = []
        elif tag == "td" and self.table:
            self.cell = []
        if tag == "code" and attrs.get("id"):
            self.code = attrs["id"]
            self.code_text = []
        if tag == "ol":
            self.ol_depth += 1
            if attrs.get("class") == "exam-parts":
                self.part_level = self.ol_depth
                self.part_counts.append(0)
            elif attrs.get("class") == "exam-solutions":
                self.solution_level = self.ol_depth
        if tag == "li":
            if self.part_level == self.ol_depth:
                self.part_counts[-1] += 1
            if self.solution_level == self.ol_depth:
                self.solution_items += 1

    def handle_endtag(self, tag):
        if tag == "td" and self.cell is not None:
            self.row.append("".join(self.cell).strip())
            self.cell = None
        elif tag == "tr" and self.row is not None:
            if self.row:
                self.tables[self.table].append(self.row)
            self.row = None
        elif tag == "table":
            self.table = None
        if tag == "code" and self.code:
            self.codes[self.code] = "".join(self.code_text)
            self.code = None
        if tag == "ol":
            if self.part_level == self.ol_depth:
                self.part_level = None
            if self.solution_level == self.ol_depth:
                self.solution_level = None
            self.ol_depth -= 1

    def handle_data(self, data):
        self.text.append(data)
        if self.cell is not None:
            self.cell.append(data)
        if self.code:
            self.code_text.append(data)


def population_variance(xs):
    mean = sum(map(F, xs)) / len(xs)
    return sum((F(x) - mean) ** 2 for x in xs) / len(xs)


def pairwise_variance(xs):
    return sum((F(a) - F(b)) ** 2
               for i, a in enumerate(xs) for b in xs[i + 1:]) / len(xs) ** 2


def dot(a, b):
    return sum((F(x) * F(y) for x, y in zip(a, b)), F(0))


def display_tenth(x):
    """Nearest tenth for nonnegative exact inputs, upward at a half tie."""
    scaled = F(x) * 10 + F(1, 2)
    return F(scaled.numerator // scaled.denominator, 10)


def check():
    html = FRAGMENT.read_text(encoding="utf-8")
    doc = ExamParser()
    doc.feed(html)
    text = "".join(doc.text)
    require(doc.headings == [("h2", "form-b")], "one form-b h2, no h1")
    require(len(doc.ids) == len(set(doc.ids)), "unique fragment IDs")
    require(all(x == "form-b" or x.startswith("v04-b-") for x in doc.ids), "namespaced IDs")
    require(all("v04-b-q" + str(i) in doc.ids for i in range(1, 6)), "five named domains")
    require(doc.part_counts == [4] * 5 and doc.solution_items == 5, "five matched four-part questions")
    require(html.count("<strong>(5)</strong>") == 20, "twenty five-point parts")
    require(text.count("Scoring:") == 20, "explicit allocation for every part")
    require("180 minutes" in text and "closed notes" in text and "nonprogrammable" in text,
            "exam conditions")
    require("synthetic" in text and "not empirical observations" in text, "original synthetic scope")
    require(len(doc.links) == 12 and all((BOOK / "content/chapters" / x).is_file()
                                      for x in doc.links), "twelve taught-method chapter routes")

    # D1: use the supplied table cells and an independent SQL join.
    facts = [(row[0], int(row[1]), int(row[2])) for row in doc.tables["v04-b-facts"]]
    roles = [tuple(row) for row in doc.tables["v04-b-roles"]]
    with sqlite3.connect(":memory:") as db:
        db.execute("CREATE TABLE fact(depot TEXT PRIMARY KEY, delivered INT, late INT)")
        db.execute("CREATE TABLE role(depot TEXT, role TEXT, PRIMARY KEY(depot,role))")
        db.executemany("INSERT INTO fact VALUES(?,?,?)", facts)
        db.executemany("INSERT INTO role VALUES(?,?)", roles)
        joined = db.execute("SELECT COUNT(*),SUM(delivered),SUM(late) FROM fact JOIN role USING(depot)").fetchone()
        reconciled = db.execute("SELECT COUNT(*),SUM(delivered),SUM(late) FROM fact WHERE EXISTS(SELECT 1 FROM role WHERE role.depot=fact.depot)").fetchone()
    require(joined == (3, 60, 10), "join multiplies N only")
    require(reconciled == (2, 50, 9), "existence preserves facts")
    require(F(joined[2], joined[1]) == F(1, 6), "joined late rate")
    weighted = F(sum(r[2] for r in facts), sum(r[1] for r in facts))
    unweighted = sum(F(r[2], r[1]) for r in facts) / len(facts)
    require((weighted, unweighted) == (F(9, 50), F(3, 20)), "exposure versus depot weights")
    require({r[0] for r in roles} - {r[0] for r in facts} == {"E"}, "active reporting gap")
    # Two possible unreported E records demonstrate lack of all-depot identification.
    require(F(9 + 0, 50 + 50) != F(9 + 50, 50 + 50), "missing denominator/outcome changes target")
    quarterly = [F(880, 4), F(968, 4)]
    discounted = [cash / F(11, 10) ** t for t, cash in enumerate(quarterly, 1)]
    require(quarterly == [220, 242] and discounted == [200, 200], "period and discount units")
    require(-400 + sum(discounted) == 0, "NPV independently sums dated flows")
    require("=C6/(1+$B$2)^A6" in html and "=B6/4" in html and "=C5" in html,
            "spreadsheet references and immediate flow")

    # D2: actual displayed guards under normal and optimized compilation.
    invalid = [None, (), [], [1] * 9, [True], [False], [1.0], [float("nan")],
               [float("inf")], [-1], [1000000001], ["1"], [[1]]]
    for optimization in (0, 1):
        namespace = {}
        exec(compile(doc.codes["v04-b-good-guard"], "form-b-good-guard", "exec",
                     optimize=optimization), namespace)
        validate = namespace["validate_margins"]
        for xs in ([0], [1000000000], [1] * 8, [100000001, 100000004, 100000010]):
            require(validate(xs) is xs, "valid list preserved")
        for xs in invalid:
            try:
                validate(xs)
            except ValueError:
                pass
            else:
                raise AssertionError("guard accepted invalid input " + repr(xs))
    old = {}
    exec(compile(doc.codes["v04-b-broken-guard"], "form-b-old-guard", "exec", optimize=0), old)
    require(old["old_guard"]([True]) == [True], "old bool failure reproduced")
    try:
        old["old_guard"]([])
    except AssertionError:
        pass
    else:
        raise AssertionError("ordinary old guard did not assert")
    exec(compile(doc.codes["v04-b-broken-guard"], "form-b-old-guard", "exec", optimize=1), old)
    require(old["old_guard"]([]) == [], "old assertions removed under optimization")
    margins = [int(x) for x in re.search(r"margin list is \[(\d+), (\d+), (\d+)\]", text).groups()]
    require(sum(margins) / 3 == 100000005, "margin mean")
    require(population_variance(margins) == pairwise_variance(margins) == 14, "two exact variance routes")
    require(population_variance([F(x, 100) for x in margins]) == F(7, 5000), "variance currency conversion")
    require(F(126, 3 * 2) == 21 and F(14, 100) == F(7, 50), "two deliberate wrong variants")
    variance_cases = 0
    for n, base, scale in product(range(1, 9), [0, 100000000], [0, 1, 7]):
        xs = [base + scale * ((j*j + 3*j) % 17) for j in range(n)]
        v = population_variance(xs)
        require(v == pairwise_variance(xs) == population_variance(xs[::-1]), "independent variance/permutation")
        require(population_variance([x + 100 for x in xs]) == v, "translation invariant")
        require(population_variance([3*x for x in xs]) == 9*v, "squared scale invariant")
        variance_cases += 1
    perturbation_bound = math.sqrt(14) + 0.25
    for delta in product([F(-1, 2), F(0), F(1, 2)], repeat=3):
        perturbed = [F(x) + d for x, d in zip(margins, delta)]
        require(abs(float(population_variance(perturbed) - 14)) <= perturbation_bound,
                "rounding perturbation envelope")

    # D3: compute reduced normal equations, then test deficient-family invariance.
    rows = [[F(x) for x in row] for row in doc.tables["v04-b-regression"]]
    xs, zs, ys = [list(values) for values in zip(*rows)]
    n = len(rows)
    gram = [[F(n), sum(xs)], [sum(xs), dot(xs, xs)]]
    rhs = [sum(ys), dot(xs, ys)]
    determinant = gram[0][0]*gram[1][1] - gram[0][1]*gram[1][0]
    intercept = (rhs[0]*gram[1][1] - gram[0][1]*rhs[1]) / determinant
    slope = (gram[0][0]*rhs[1] - rhs[0]*gram[1][0]) / determinant
    fitted = [intercept+slope*x for x in xs]
    residuals = [y-yhat for y,yhat in zip(ys,fitted)]
    require((intercept,slope) == (F(2,3),2), "reduced normal system")
    require(fitted == [F(2,3),F(8,3),F(14,3)], "fitted vector")
    require(residuals == [F(1,3),F(-2,3),F(1,3)], "residual vector")
    require(sum(residuals) == dot(xs,residuals) == dot(zs,residuals) == 0,
            "all original normal equations")
    require(dot(residuals,residuals) == F(2,3), "SSE")
    for t in [F(-7),F(-1,2),F(0),F(1),F(5,3),F(9)]:
        require([intercept+(2-2*t)*x+t*z for x,z in zip(xs,zs)] == fitted,
                "rank-deficient coefficient family")
    for a,b,c in product([-1,0,1], repeat=3):
        alternate = [a+b*x+c*z for x,z in zip(xs,zs)]
        alt_residual = [y-f for y,f in zip(ys,alternate)]
        distance = [f-g for f,g in zip(fitted,alternate)]
        require(dot(alt_residual,alt_residual) == F(2,3)+dot(distance,distance), "projection loss identity")
    require((intercept+2*3,intercept+5) == (F(20,3),F(17,3)), "off-support predictions")
    fees = [0,0,1,2,4,4,4,8]
    counts = [sum(lo<=x<hi or (last and x==hi) for x in fees)
              for lo,hi,last in [(0,2,False),(2,4,False),(4,9,True)]]
    densities = [F(count,8*width) for count,width in zip(counts,[2,2,5])]
    areas = [height*width for height,width in zip(densities,[2,2,5])]
    require(counts == [3,1,4] and densities == [F(3,16),F(1,16),F(1,10)], "unequal-width density")
    require(areas == [F(3,8),F(1,8),F(1,2)] and sum(areas) == 1, "histogram area")
    ecdf = lambda u: F(sum(x<=u for x in fees),len(fees))
    require((ecdf(2),ecdf(4),F(fees.count(4),8),1-ecdf(4)) == (F(1,2),F(7,8),F(3,8),F(1,8)), "ECDF and strict inequality")

    # D4: exact probability equation and an adjacent-integer budget test.
    upper = -math.expm1(math.log(0.05)/500)
    require(math.isclose((1-upper)**500,0.05,rel_tol=1e-12), "zero-count inversion")
    require(math.isclose(upper,0.005973551516349559,abs_tol=1e-15), "rare-event numerical upper bound")
    planned_n = math.ceil(math.log(0.05)/math.log(0.998))
    require(planned_n == 1497, "minimum zero-count budget")
    require(-math.expm1(math.log(.05)/1497) <= .002 < -math.expm1(math.log(.05)/1496), "adjacent n minimality")
    states = [(a,b,a,20+8*b) for a,b in product([0,1],repeat=2)]
    selected = [row for row in states if row[0]==row[1]]
    means = [sum(F(row[3]) for row in selected if row[2]==d)/sum(row[2]==d for row in selected)
             for d in [0,1]]
    require([(r[0],r[1]) for r in selected] == [(0,0),(1,1)] and means == [20,28], "collider enumeration")
    require(means[1]-means[0] == 8 and all((20+8*b)-(20+8*b)==0 for a,b in product([0,1],repeat=2)), "selected contrast versus ATE")
    for d in [0,1]:
        require(sum(F(row[3]) for row in states if row[2]==d)/2 == 24, "unselected mean equality")
    mediator = [(d,u,d+u,30+2*d+5*(d+u)) for d,u in product([0,1],range(3))]
    require(all((30+2+5*(1+u))-(30+5*u)==7 for u in range(3)), "total mediator effect")
    at_one = [row for row in mediator if row[2]==1]
    require(at_one == [(0,1,1,35),(1,0,1,37)] and at_one[1][3]-at_one[0][3] == 2,
            "controlled intervention and observed support")

    # D5: forecast origins are different; selection scores are pooled by cases.
    demand = [F(x) for x in [30,34,38,36,40]]
    def drift(origin,horizon):
        available = demand[:origin]
        return available[-1] + horizon*(available[-1]-available[0])/(len(available)-1)
    fixed = [drift(3,1),drift(3,2)]
    updating = [drift(3,1),drift(4,1)]
    mse = lambda predictions: sum((a-p)**2 for a,p in zip(demand[3:],predictions))/2
    require(fixed == [42,46] and updating == [42,38], "fixed versus new origins")
    require((mse(fixed),mse(updating)) == (36,20), "task-specific MSE")
    blocks = [[int(x) for x in row] for row in doc.tables["v04-b-nested"]]
    choices = [min(range(2),key=lambda j:row[2+j]) for row in blocks]
    correct = F(sum(row[1]*row[4+j] for row,j in zip(blocks,choices)),sum(row[1] for row in blocks))
    invalid_score = F(sum(row[1]*min(row[4:]) for row in blocks),sum(row[1] for row in blocks))
    require(choices == [0,1] and correct == F(22,3) and invalid_score == F(5,3), "nested selection and unequal counts")
    levels = [[F(row[1]),F(row[2])] for row in doc.tables["v04-b-rates"]]
    rates = [100*n/d for n,d in levels]
    require(rates == [F(73,50),F(77,50)], "published-level rate reconstruction")
    require([display_tenth(x) for x in rates] == [F(3,2),F(3,2)], "source displays")
    difference = rates[1]-rates[0]
    require(difference == F(2,25) and display_tenth(difference) == F(1,10), "round-last differs from display difference")
    lower = 100*(levels[1][0]-F(1,2))/(levels[1][1]+F(1,2))
    upper_rate = 100*(levels[1][0]+F(1,2))/(levels[1][1]-F(1,2))
    require((lower,upper_rate) == (F(30700,20001),F(30900,19999)), "monotone level-rounding envelope")
    for numerator_error,denominator_error in product([F(-1,2),F(-1,4),F(0),F(1,4),F(1,2)],repeat=2):
        value = 100*(154+numerator_error)/(10000+denominator_error)
        require(lower <= value <= upper_rate and display_tenth(value) == F(3,2), "entire rounding rectangle agrees")

    # Anchor the computed answers to the manuscript's actual solution values.
    required_answers = ["1/6", "9/50 = 18%", "3/20 = 15%", "100000005 cents",
                        "14 cents²", "0.0014 USD²", "21 cents²", "0.14 USD²",
                        "3.991657 cents²", "(2/3,8/3,14/3) USD", "2/3 USD²",
                        "20/3 USD", "17/3 USD", "(3/16,1/16,1/10) per USD",
                        "0.005973552=0.5973552%", "1497", "36 units²", "20 units²",
                        "22/3", "5/3", "1.534923254%", "1.545077254%"]
    require(all(answer in text for answer in required_answers), "all checked numeric answers present")
    return {
        "assessment": "v04-form-b",
        "status": "passed",
        "checks": [
            "Five 20-point domains, twenty 5-point parts and scoring allocations; matching solutions, namespaced IDs, exam conditions and twelve existing chapter method links",
            "HTML-input SQL join multiplicity/existence reconciliation, correct exposure weights, two missing-depot completions and exact dated spreadsheet cash-flow NPV",
            "Both displayed Python guards executed; bool and optimized-assert failures reproduced; 13 invalid contracts rejected by explicit validation under normal and optimized compilation",
            f"Exact pairwise/centered variance, units and wrong-denominator variants; {variance_cases} independent permutation/translation/scale cases and 27 bounded input perturbations",
            "Reduced normal-system solution, all original residual equations, six rank-deficient coefficient representations, 27 projection-loss identities and off-support predictions",
            "Unequal-width histogram areas/densities, ECDF endpoints and point mass; iid zero-event bound inversion and adjacent-integer simulation-budget minimality",
            "All four baseline collider states, selected and unselected contrasts, six mediator states, total/direct effects and joint-support check",
            "Distinct fixed/updating forecast origins, exact MSEs, inner-selected outer scores with unequal case weights, rounding-order difference and 25-point rounding-envelope grid"
        ],
        "limitations": [
            "Numerical checks accompany manual review of derivations, assumptions and scoring; they do not establish every possible altered program or answer correct.",
            "All exam data and mechanisms are synthetic; no external empirical result, policy effect, future forecast performance or survey sampling interval is asserted.",
            "Methods and source scope are reused from accepted Volume 4 chapters; no new external source inspection was needed for this assessment.",
            "Root retains final assessment integration and acceptance. No visual, mobile or print UI QA was performed."
        ]
    }


if __name__ == "__main__":
    print(json.dumps(check(), indent=2, ensure_ascii=False))
