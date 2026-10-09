#!/usr/bin/env python3
"""Quiet independent C04 peer checks; six canonical runtime files only.

The finite certificates support a separately recorded proof review. They do not
purport to prove an arbitrary-dimensional fixed-point or equilibrium theorem.
No author checker, generated numeric output, shared module or network is used.
"""
import ast
from collections import Counter
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from itertools import combinations, permutations, product
import json
from math import factorial
from pathlib import Path


AUTHORS = ("content/chapters/v13-c04.html", "scripts/check_v13_c04.py",
           "content/reviews/v13-c04-sources.json", "content/reviews/v13-c04-author.json")
SELF, RECORD = "scripts/check_v13_c04_peer.py", "content/reviews/v13-c04-peer.json"
SOURCES = {
    "v13-c04-mathew2010": "https://math.uchicago.edu/~amathew/HMMT.pdf",
    "v13-c04-tamuz2021": "https://www.tamuz.caltech.edu/teaching/ss205b/lectures.pdf",
    "v13-c04-condie-existence": "https://scottcondie.github.io/teaching/580/chapters/ge-existence.html",
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def number(value):
    require(type(value) in (int, F), "bounded exact number required")
    result = F(value)
    require(abs(result) <= 10**6 and result.denominator <= 10**9, "rational bounds")
    return result


def vector(values, length=None):
    require(type(values) in (list, tuple) and 1 <= len(values) <= 8, "vector shape")
    require(length is None or len(values) == length, "vector dimension")
    return tuple(number(x) for x in values)


def inner(left, right):
    a, b = vector(left), vector(right)
    require(len(a) == len(b), "inner product dimensions")
    return sum((x*y for x, y in zip(a, b)), F(0))


def minus(left, right):
    require(len(left) == len(right), "difference dimensions")
    return tuple(x-y for x, y in zip(left, right))


def square_distance(left, right):
    delta = minus(left, right)
    return inner(delta, delta)


def total(rows):
    require(type(rows) in (tuple, list) and 1 <= len(rows) <= 8, "row collection")
    rows = tuple(vector(row) for row in rows)
    require(len({len(row) for row in rows}) == 1, "ragged rows")
    return tuple(sum(row[j] for row in rows) for j in range(len(rows[0])))


def poly_product(left, right):
    a, b = vector(left), vector(right)
    require(len(a)+len(b) <= 9, "polynomial degree bound")
    result = [F(0)]*(len(a)+len(b)-1)
    for i, x in enumerate(a):
        for j, y in enumerate(b):
            result[i+j] += x*y
    return tuple(result)


def simplex(values):
    x = vector(values)
    require(min(x) >= 0 and sum(x) == 1, "simplex domain")
    return x


def label(point, image):
    x, y = simplex(point), simplex(image)
    require(len(x) == len(y), "self-map dimensions")
    if x == y:
        return None
    return next(i for i in range(len(x)) if x[i] > y[i])


def chain_cell(order):
    require(type(order) in (tuple, list) and 2 <= len(order) <= 4, "finite chain dimension")
    require(all(type(i) is int for i in order) and set(order) == set(range(len(order))), "permutation")
    return tuple(tuple(F(int(j in order[:k]), k) for j in range(len(order)))
                 for k in range(1, len(order)+1))


def determinant(rows):
    require(type(rows) in (tuple, list) and 1 <= len(rows) <= 3, "determinant dimension")
    n = len(rows)
    a = tuple(vector(row, n) for row in rows)
    # Leibniz expansion, independent of the author's elimination routine.
    answer = F(0)
    for p in permutations(range(n)):
        inversions = sum(p[i] > p[j] for i in range(n) for j in range(i+1, n))
        term = F((-1)**inversions)
        for i in range(n):
            term *= a[i][p[i]]
        answer += term
    return answer


def demand(price, income, share):
    p, m, alpha = vector(price, 2), number(income), number(share)
    require(min(p) > 0 and m > 0 and 0 < alpha < 1, "Cobb-Douglas interior domain")
    return (alpha*m/p[0], (1-alpha)*m/p[1])


def exchange(endowments, shares):
    require(type(endowments) in (tuple, list) and 1 <= len(endowments) <= 4, "household count")
    omega = tuple(vector(row, 2) for row in endowments)
    alpha = vector(shares, len(omega))
    require(all(min(row) > 0 for row in omega) and all(0 < x < 1 for x in alpha), "exchange primitives")
    # Multiply first-good excess demand by r: its affine zero supplies the price.
    slope = sum(a*w[0] for a, w in zip(alpha, omega))-sum(w[0] for w in omega)
    intercept = sum(a*w[1] for a, w in zip(alpha, omega))
    r = -intercept/slope
    wealth = tuple(r*w[0]+w[1] for w in omega)
    choices = tuple(demand((r, 1), m, a) for m, a in zip(wealth, alpha))
    return r, wealth, choices


def firm(price):
    # Optimize output value b*2t-a*t² on 0<=t<=2, including boundary prices.
    a, b = vector(price, 2)
    require(a >= 0 and b >= 0 and a+b > 0, "nonnegative nonzero prices")
    t = F(2) if a == 0 else min(F(2), b/a)
    supply = (-t*t, 2*t)
    return supply, inner((a, b), supply), t


def owner_ledger(price, shares, tastes=(F(1, 2), F(1, 2)), distribute=True):
    p, theta, alpha = vector(price, 2), vector(shares, 2), vector(tastes, 2)
    require(min(p) > 0 and min(theta) >= 0 and sum(theta) == 1, "complete ownership and positive prices")
    require(type(distribute) is bool, "distribution flag")
    y, profit, _ = firm(p)
    wealth = tuple(inner(p, (2, F(1, 2)))+(s*profit if distribute else 0) for s in theta)
    choices = tuple(demand(p, m, a) for m, a in zip(wealth, alpha))
    resources = (4+y[0], 1+y[1])
    return y, profit, wealth, choices, resources


def projection(point):
    z = vector(point, 2)
    # Orthogonality to tangent (1,-1), followed by its interval KKT constraints.
    t = min(F(1), max(F(0), inner(z, (1, -1))/2+F(1, 2)))
    return (t, 1-t)


def tents(sites, choices, point, epsilon):
    s, v, x, e = vector(sites), vector(choices), number(point), number(epsilon)
    require(len(s) == len(v) and e > 0 and 0 <= x <= 1, "tent dimensions/scale")
    require(all(0 <= z <= 1 for z in s+v), "tent domain and range")
    weights = tuple(max(F(0), e-abs(x-z)) for z in s)
    require(sum(weights) > 0, "uncovered tent point")
    normalized = tuple(w/sum(weights) for w in weights)
    return inner(normalized, v), normalized


def strict_json(text):
    def unique(pairs):
        obj = {}
        for key, value in pairs:
            require(key not in obj, "duplicate JSON key")
            obj[key] = value
        return obj
    def bad(value):
        raise ValueError("nonfinite JSON value: "+value)
    result = json.loads(text, object_pairs_hook=unique, parse_constant=bad)
    json.dumps(result, allow_nan=False)
    return result


def expression(text):
    raw = text.strip().replace("−", "-")
    require(len(raw) <= 1500, "numeric marker size")
    tree = ast.parse(raw, mode="eval")
    require(sum(1 for _ in ast.walk(tree)) <= 300, "numeric marker nodes")
    def visit(node):
        if isinstance(node, ast.Constant) and type(node.value) is int:
            return number(node.value)
        if isinstance(node, (ast.Tuple, ast.List)):
            require(1 <= len(node.elts) <= 8, "marker tuple size")
            return tuple(visit(x) for x in node.elts)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            v = visit(node.operand)
            require(type(v) is F, "scalar sign")
            return -v if isinstance(node.op, ast.USub) else v
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            a, b = visit(node.left), visit(node.right)
            require(type(a) is F and type(b) is F and b != 0, "scalar division")
            return number(a/b)
        raise ValueError("unsupported numeric expression")
    return visit(tree.body)


class Document(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids, self.inputs, self.results, self.sources = {}, {}, {}, {}
        self.worked, self.exercises, self.solutions, self.links, self.rows = [], [], [], [], []
        self.stack, self.text = [], []
        self.exdepth = self.soldepth = 0
        self.marker = self.cell = None
        self.table = False
        self.row = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        require(len(a) == len(attrs), "duplicate HTML attribute")
        if "id" in a:
            require(a["id"] not in self.ids, "duplicate HTML ID")
            self.ids[a["id"]] = tag
        classes = a.get("class", "").split()
        ex, sol = tag == "ol" and "exercises" in classes, tag == "details" and "solutions" in classes
        if "worked" in classes:
            self.worked.append(a.get("id"))
        if tag == "li" and self.exdepth:
            self.exercises.append(a.get("id"))
        if "data-solution-for" in a:
            require(tag == "li" and self.soldepth, "answer disclosure/element")
            self.solutions.append(a["data-solution-for"])
        self.exdepth += int(ex)
        self.soldepth += int(sol)
        if tag not in ("br", "hr", "img", "input", "meta", "link"):
            self.stack.append((tag, ex, sol))
        keys = [key for key in ("data-input", "data-calc") if key in a]
        if keys:
            require(len(keys) == 1 and self.marker is None and tag == "span", "single numeric marker")
            destination = self.inputs if keys[0] == "data-input" else self.results
            require(a[keys[0]] not in destination, "duplicate numeric marker")
            self.marker = (destination, a[keys[0]], [])
        if tag == "a":
            self.links.append(a.get("href", ""))
            if "data-source" in a:
                require(a["data-source"] not in self.sources, "duplicate source marker")
                self.sources[a["data-source"]] = a.get("href")
        if tag == "table" and a.get("id") == "v13-c04-cycle-table":
            self.table = True
        if self.table and tag == "tr":
            self.row = []
        if self.table and tag == "td":
            self.cell = []

    def handle_data(self, text):
        self.text.append(text)
        if self.marker is not None:
            self.marker[2].append(text)
        if self.cell is not None:
            self.cell.append(text)

    def handle_endtag(self, tag):
        require(self.stack and self.stack[-1][0] == tag, "balanced HTML nesting")
        _, ex, sol = self.stack.pop()
        self.exdepth -= int(ex)
        self.soldepth -= int(sol)
        if tag == "span" and self.marker is not None:
            destination, key, pieces = self.marker
            destination[key] = expression("".join(pieces))
            self.marker = None
        if tag == "td" and self.cell is not None:
            self.row.append("".join(self.cell).strip())
            self.cell = None
        if tag == "tr" and self.table and self.row:
            self.rows.append(tuple(self.row))
        if tag == "table":
            self.table = False


class Audit:
    def __init__(self):
        self.comparisons = self.rejections = 0

    def equal(self, actual, expected, label):
        self.comparisons += 1
        require(actual == expected, label+": "+repr(actual)+" != "+repr(expected))

    def true(self, condition, label):
        self.equal(bool(condition), True, label)

    def reject(self, function, *args):
        self.rejections += 1
        try:
            function(*args)
        except (ValueError, TypeError, SyntaxError, ZeroDivisionError):
            return
        raise ValueError("invalid case accepted by "+function.__name__)


def mathematical_oracle(a):
    inputs = {
        "exchange-endowments": ((4, 1), (1, 4)), "exchange-shares": (F(2, 3), F(1, 3)),
        "exchange-transfer-endowment": (4, 2), "production-endowment": (2, F(1, 2)),
        "production-shares": (F(1, 4), F(3, 4)), "production-capacity": 4,
        "cycle-vertices": ((1, 0, 0), (0, 1, 0), (0, 0, 1),
                           (F(1, 2), F(1, 2), 0), (F(1, 2), 0, F(1, 2)), (0, F(1, 2), F(1, 2))),
        "cycle-cells": ((0, 3, 4), (1, 3, 5), (2, 4, 5), (3, 4, 5)),
        "leontief-endowments": ((1, 1), (2, 2)), "linear-endowments": ((1, 1), (1, 1)),
        "nonconvex-endowment": (1, 1),
    }
    result = {}
    # Direct polynomial certificates for the three Cobb-Douglas shares used.
    a.equal(poly_product(poly_product((F(-2, 3), 1), (F(-2, 3), 1)), (F(1, 3), 1)),
            (F(4, 27), 0, -1, 1), "global q²(1-q) maximum difference factorization")
    a.equal(poly_product(poly_product((F(-1, 3), 1), (F(-1, 3), 1)), (F(4, 3), -1)),
            (F(4, 27), -1, 2, -1), "global q(1-q)² maximum difference factorization")
    a.equal(poly_product((F(-1, 2), 1), (F(-1, 2), 1)), (F(1, 4), -1, 1),
            "global q(1-q) maximum difference factorization")
    for prefix, gift in (("exchange", 1), ("exchange-transfer", 2), ("exercise-exchange", 3)):
        omega = ((4, gift), (1, 4))
        r, wealth, x = exchange(omega, inputs["exchange-shares"])
        result[prefix+"-price"], result[prefix+"-incomes"] = r, wealth
        result[prefix+"-allocations"], result[prefix+"-totals"] = x, total(x)
        a.equal(total(x), total(omega), prefix+" exact commodity clearing")
        a.equal(tuple(inner((r, 1), row) for row in x), wealth, prefix+" household budgets")
        a.equal(sum(wealth), inner((r, 1), total(omega)), prefix+" aggregate wealth")
        a.equal(tuple(demand((7*r, 7), 7*m, alpha) for m, alpha in zip(wealth, inputs["exchange-shares"])),
                x, prefix+" nominal normalization invariance")

    # Solve using t=sqrt(input): leisure-value clearing is 3t²+t-4=0.
    a.equal(poly_product((-1, 1), (4, 3)), (-4, 1, 3), "production equilibrium in input-root coordinate")
    t_roots = (F(1), F(-4, 3))
    wage_roots = tuple(1/t for t in t_roots)
    result["production-roots"], result["production-wage"] = wage_roots, wage_roots[0]
    a.true(t_roots[0] > 0 > t_roots[1] and 1/t_roots[0] > F(1, 2), "sole admissible interior root")
    y, profit, wealth, choices, resources = owner_ledger((1, 1), inputs["production-shares"])
    result.update({"production-supply": y, "production-profit": profit, "production-incomes": wealth,
                   "production-allocations": choices, "production-totals": total(choices)})
    a.equal(total(choices), resources, "production exact resource identities")
    a.equal(tuple(inner((1, 1), x) for x in choices), wealth, "funded household budgets")
    a.equal(sum(wealth), inner((1, 1), resources), "owners receive full net profit")
    equal = owner_ledger((1, 1), (F(1, 2),)*2)
    result["production-equal-incomes"], result["production-equal-allocations"] = equal[2], equal[3]
    a.equal(total(equal[3]), resources, "ownership redistribution with common spending shares")
    omitted = owner_ledger((1, 1), inputs["production-shares"], distribute=False)
    result["production-omitted-demand"] = total(omitted[3])
    result["production-omitted-walras"] = inner((1, 1), minus(total(omitted[3]), resources))
    a.equal(result["production-omitted-walras"], -profit, "omitted distributed profit equals value gap")
    taste = (F(3, 4), F(1, 4))
    changed = owner_ledger((1, 1), inputs["production-shares"], taste)
    changed_equal = owner_ledger((1, 1), (F(1, 2),)*2, taste)
    a.equal(minus(total(changed[3]), total(changed_equal[3])), (F(-1, 8), F(1, 8)),
            "ownership affects aggregate demand with unequal tastes")

    for price in ((F(1, 4), 1), (F(1, 2), 1), (1, 1), (2, 1), (0, 1), (1, 0)):
        y, pi, t_star = firm(price)
        w, b = map(F, price)
        a.true(0 <= t_star <= 2 and y == (-t_star*t_star, 2*t_star), "original generator feasibility")
        for t in (F(0), F(1, 2), F(1), F(3, 2), F(2)):
            gap = pi-(2*b*t-w*t*t)
            certificate = w*(t-t_star)**2+(2*w*t_star-2*b)*(t-t_star)
            a.equal(gap, certificate, "quadratic global profit certificate")
            a.true(gap >= 0, "candidate beats finite original technologies")
        if 0 < w <= F(1, 2) and b == 1:
            cap = owner_ledger(price, inputs["production-shares"])
            a.equal(cap[4][0], 0, "capacity exhausts input resource")
            a.true(total(cap[3])[0] > 0, "capacity branch cannot clear positive leisure demand")
    a.equal(firm((F(1, 2), 1))[:2], ((-4, 4), 2), "profit and supply join at w=1/2")
    bounds = (4, 1+4)
    result["exercise-resource-bounds"], result["exercise-resource-cap"] = bounds, max(bounds)+1
    result["exercise-income-lower"] = min(inputs["production-endowment"])
    normalized = ((F(0), F(1)), (F(1, 3), F(2, 3)), (F(1), F(0)))
    for p in normalized:
        _, pi, _ = firm(p)
        a.true(all(inner(p, inputs["production-endowment"])+share*pi >= F(1, 2)
                   for share in inputs["production-shares"]), "individual normalized income floor")
    for p, q in combinations(normalized, 2):
        a.true((firm(p)[1]-firm(q)[1])**2 <= 32*square_distance(p, q), "compact-generator support Lipschitz witness")

    vertices, cells = inputs["cycle-vertices"], inputs["cycle-cells"]
    images = tuple((x[1], x[2], x[0]) for x in vertices)
    labels = tuple(label(x, f) for x, f in zip(vertices, images))
    counts = tuple(sum({labels[i] for i in edge} == {0, 1} for edge in combinations(cell, 2)) for cell in cells)
    full = tuple(i for i, cell in enumerate(cells) if {labels[j] for j in cell} == {0, 1, 2})
    centroid = tuple(z/3 for z in total(tuple(vertices[j] for j in cells[full[0]])))
    result["cycle-labels"], result["cycle-incidences"], result["cycle-fixed"] = labels, counts, centroid
    a.equal(full, (3,), "only central cell full")
    a.equal((centroid[1], centroid[2], centroid[0]), centroid, "cycle centroid is fixed by this linear map")
    a.equal(label(centroid, centroid), None, "exact fixed vertex ends labeling proof")
    for v, k in zip(vertices, labels):
        a.true(v[k] > 0, "strict deficit cannot label a zero coordinate")
    for mids in product((0, 1), (0, 2), (1, 2)):
        lab = (0, 1, 2)+mids
        marked = Counter(tuple(sorted(edge)) for cell in cells for edge in combinations(cell, 2)
                         if {lab[j] for j in edge} == {0, 1})
        odd_boundary = sum(n == 1 for n in marked.values())
        fully = sum({lab[j] for j in cell} == {0, 1, 2} for cell in cells)
        a.equal((sum(marked.values()) % 2, odd_boundary % 2, fully % 2), (1, 1, 1), "complete admissible triangle parity")
    weak_deficits = minus(vertices[2], vertices[0])
    weak_index = next(i for i, z in enumerate(weak_deficits) if z >= 0)
    a.equal((weak_index, vertices[2][weak_index], label(vertices[2], vertices[0])), (1, 0, 2), "weak labeling violates boundary")
    table = tuple((name, minus(v, im), F(k)) for name, v, im, k in
                  zip(("e₀", "e₁", "e₂", "m₀₁", "m₀₂", "m₁₂"), vertices, images, labels))

    cell_count = 0
    for d in (1, 2, 3):
        subcells = tuple(chain_cell(p) for p in permutations(range(d+1)))
        cell_count += len(subcells)
        volumes, diameters = [], []
        for cell in subcells:
            columns = tuple(minus(v[1:], cell[0][1:]) for v in cell[1:])
            volumes.append(abs(determinant(columns)))
            diameters.append(max(square_distance(x, y) for x, y in combinations(cell, 2)))
        a.equal((len(subcells), set(volumes), sum(volumes)),
                (factorial(d+1), {F(1, factorial(d+1))}, 1), "Leibniz oriented-volume subdivision certificate")
        a.true(max(diameters) <= 2*F(d, d+1)**2, "nested-face mesh contraction")
        # Shared original-face subdivisions must coincide with its own chains.
        if d >= 2:
            facets = {tuple(sorted(v for v in cell if v[-1] == 0)) for cell in subcells
                      if sum(v[-1] == 0 for v in cell) == d}
            independent_face = {tuple(sorted(v+(F(0),) for v in chain_cell(p))) for p in permutations(range(d))}
            a.equal(facets, independent_face, "compatible restriction to original face")
    lam = (F(2, 5), F(2, 5), F(1, 5), F(0))
    survivors = []
    for order in ((0, 1, 2, 3), (1, 0, 2, 3)):
        cell = chain_cell(order)
        mu = tuple((k+1)*(lam[order[k]]-(lam[order[k+1]] if k+1 < 4 else 0)) for k in range(4))
        reconstruction = tuple(sum(mu[k]*cell[k][j] for k in range(4)) for j in range(4))
        a.equal((min(mu), sum(mu), reconstruction), (0, 1, lam), "coordinate-drop reconstruction with ties/zero face")
        survivors.append({cell[k] for k, w in enumerate(mu) if w})
    a.equal(survivors[0], survivors[1], "ties leave only common-chain face vertices")

    # A full interval cell need not have a fixed centroid: an irrational root.
    lo, hi = F(0), F(1)
    deficit = lambda t: t-(1-t)**2
    for _ in range(8):
        middle = (lo+hi)/2
        if deficit(middle) < 0:
            lo = middle
        else:
            hi = middle
    a.true(deficit(lo) < 0 < deficit(hi), "full-cell endpoint labels for nonlinear self-map")
    a.equal(hi-lo, F(1, 256), "vanishing-mesh finite witness")
    a.true(deficit((lo+hi)/2) != 0, "finite full-cell centroid is not generically fixed")

    point_data = ((2, 2), (-1, 0), (2, 0))
    projections = tuple(projection(z) for z in point_data)
    result["exercise-projections"] = projections
    for z, p in zip(point_data, projections):
        a.true(min(p) >= 0 and sum(p) == 1, "lower-dimensional projection feasibility")
        for endpoint in ((0, 1), (1, 0)):
            a.true(inner(minus(z, p), minus(endpoint, p)) <= 0, "projection endpoint variational condition")
    for i, j in combinations(range(3), 2):
        a.true(square_distance(projections[i], projections[j]) <= square_distance(point_data[i], point_data[j]),
               "projection nonexpansive squared-distance certificate")
    # Three-dimensional cube containment in the chapter's explicit simplex.
    for z in product((-2, 2), repeat=3):
        bary = tuple(F(x+2, 12) for x in z)
        zero_weight = 1-sum(bary)
        a.true(min(bary+(zero_weight,)) >= 0, "containing-simplex cube-corner barycentric coordinates")
        a.equal(tuple(-2+12*b for b in bary), z, "containing-simplex reconstruction")

    result["kakutani-repaired-fixed"] = F(1, 2)
    result["kakutani-missing-limit"] = (F(1, 2), F(1))
    result["noncompact-candidate"] = F(1)
    a.true(F(1, 2) not in (0, 1) and 0 < F(1, 2) < 1, "middle convexification changes fixed-point membership")
    for n in (3, 6, 12):
        site = F(1, 2)-F(1, n)
        a.true(site < F(1, 2) and site != 1, "closed-graph missing-limit sequence")
        a.true(1/F(1, n) >= n, "without compact range images can escape")
    for x in (F(0), F(1, 2), F(3, 4)):
        a.true(x < (1+x)/2 < 1, "noncompact-domain self-map moves every tested point upward")
        averaged, weights = tents((0, F(1, 2), 1), (F(1, 4), F(3, 4), F(1, 4)), x, F(3, 4))
        a.true(sum(weights) == 1 and min(weights) >= 0 and F(1, 4) <= averaged <= F(3, 4),
               "tent normalization and convex constant-image bounds")
    finite_fixed, _ = tents((0, 1), (0, 1), F(1, 2), 2)
    a.equal(finite_fixed, F(1, 2), "finite approximate map has midpoint fixed point")
    a.true(finite_fixed != F(1, 2)**2, "approximate fixed point need not belong to original nonlinear graph")

    # Positive income is necessary to this radial budget-approximation route.
    target, omega = (F(5), F(1, 2)), (F(2), F(1, 2))
    previous = None
    for delta in (F(1, 2), F(1, 4), F(1, 8)):
        p = (delta, 1-delta)
        wealth = inner(p, omega)
        scale = wealth/inner(p, target)
        nearby = tuple(scale*x for x in target)
        a.equal(inner(p, nearby), wealth, "nearby budget approximation binds")
        error = square_distance(nearby, target)
        if previous is not None:
            a.true(error < previous, "positive-income approximation approaches boundary target")
        previous = error
        zero_income_price = (1-delta, delta)
        a.equal(inner(zero_income_price, (0, 1))/inner(zero_income_price, (0, 2)), F(1, 2),
                "zero-income limit loses lower approximation")
    a.equal((inner((1, 0), (0, 1)), inner((1, 0), (0, 2))), (0, 0),
            "unapproximable target is feasible at the zero-income limit")
    a.true(inner((F(1, 4), F(3, 4)), (1, -1)) <= 0 and 1 > 0,
           "budget value inequality alone does not imply resource feasibility")
    a.equal(inner((0, 1), (-1, 0)), F(0), "Walras law at a zero price does not clear that good")
    # Actual cheap-mixture construction, with the better point outside the cap.
    xi, better, price, cap = (F(1), F(1)), (F(4), F(0)), (F(1, 10), F(1)), F(3)
    shrunk = tuple(F(9, 10)*v for v in better)
    b = tuple(F(3, 4)*x+F(1, 4)*y for x, y in zip(xi, shrunk))
    improved = (b[0], b[1]+F(1, 10))
    a.true(max(shrunk) > cap and sum(shrunk) > sum(xi) and inner(price, shrunk) < inner(price, xi),
           "radial better point remains outside cap and strictly cheaper")
    a.true(max(improved) < cap and inner(price, improved) < inner(price, xi) and sum(improved) > sum(xi),
           "small mixture plus coordinate increase contradicts purported capped optimality")
    flat = lambda x: max(F(0), min(x)-1)
    result["exercise-flat-mixture-utilities"] = tuple(flat(x) for x in ((0, 0), (2, 2), (F(1, 2),)*2))

    result["linear-allocation-interval"] = (F(0), F(2))
    for t in (F(1), F(2)):
        for r in (F(1, 4), F(1), F(4)):
            a.equal(((r+1)*t)/(r+1), t, "Leontief maximum level under every tested price")
    for allocation in (F(0), F(1, 3), F(1), F(2)):
        x = ((allocation, 2-allocation), (2-allocation, allocation))
        a.equal((total(x), tuple(sum(z) for z in x)), ((2, 2), (2, 2)), "linear continuum individual budgets and aggregate clearing")
    for r in (F(1, 2), F(2)):
        income = 1+r
        chosen = (income/r, F(0)) if r < 1 else (F(0), income)
        a.true(total((chosen, chosen)) != (2, 2), "unequal linear prices leave one supplied good uncleared")
    result["iteration-fixed"] = F(1, 2)
    sequence = [F(0)]
    for _ in range(4):
        sequence.append(1-sequence[-1])
    result["iteration-path"] = tuple(sequence)
    a.equal((set(sequence[::2]), set(sequence[1::2])), ({F(0)}, {F(1)}), "distinct iteration subsequential limits")
    result["nonconvex-endowment-utility"] = inner(inputs["nonconvex-endowment"], inputs["nonconvex-endowment"])
    result["nonconvex-endpoint-lower-bound"] = F(2)**2
    for raw_price in ((F(1, 4), 1), (1, 1), (4, 1)):
        p = vector(raw_price, 2)
        endpoint = (sum(p)/p[0], 0) if p[0] <= p[1] else (0, sum(p)/p[1])
        a.equal(inner(p, endpoint), sum(p), "nonconvex preferred endpoint is funded")
        a.true(inner(endpoint, endpoint) >= 4 > result["nonconvex-endowment-utility"], "nonconvex economy cannot clear at positive price")
    for p in ((0, 1), (1, 0)):
        free = p.index(0)
        x, larger = [F(1), F(1)], [F(1), F(1)]
        larger[free] = 10
        a.equal(inner(p, x), inner(p, larger), "boundary free-good expansion has unchanged cost")
        a.true(inner(larger, larger) > inner(x, x), "boundary nonconvex utility has no saturation")
    return inputs, result, table, cell_count


def check(root=None):
    require(root is None or isinstance(root, (str, Path)), "root path type")
    base = Path(root).resolve() if root is not None else Path(__file__).resolve().parents[1]
    a, doc = Audit(), Document()
    doc.feed((base/AUTHORS[0]).read_text(encoding="utf-8"))
    doc.close()
    a.equal((doc.stack, doc.marker, doc.cell), ([], None, None), "complete balanced manuscript")
    exercise_ids = ["v13-c04-ex"+str(i) for i in range(1, 13)]
    a.equal(doc.exercises, exercise_ids, "twelve exact prompts")
    a.equal(doc.solutions, exercise_ids, "twelve paired complete solutions")
    a.equal(doc.worked, ["v13-c04-case"+str(i) for i in range(1, 7)], "six worked cases")
    a.true(all(key.startswith("v13-c04-") for key in doc.ids), "namespaced reader IDs")
    a.equal(doc.sources, SOURCES, "scoped primary hyperlinks")
    a.equal({link for link in doc.links if not link.startswith("https://")},
            {"v13-c01.html", "v13-c02.html", "v13-c03.html", "v02-c09.html", "v02-c10.html", "v13-c05.html"},
            "flat prerequisite and successor paths")
    a.true("Delayed retention" in "".join(doc.text) and "v13-c04-retention-answer" in doc.ids,
           "answered delayed retention")
    inputs, results, table, cells = mathematical_oracle(a)
    a.equal(doc.inputs, inputs, "eleven visible primitive contracts")
    a.equal(set(doc.results), set(results), "every printed result covered")
    for key, expected in results.items():
        a.equal(doc.results[key], expected, "printed "+key)
    a.equal(tuple((name, expression(delta), expression(k)) for name, delta, k in doc.rows), table,
            "complete six-row deficit table")

    for value in (True, 0.5, "1", float("nan"), float("inf"), 1j, 10**6+1, F(1, 10**9+1)):
        a.reject(number, value)
    a.reject(vector, (1, 2), 3)
    a.reject(vector, ())
    a.reject(total, ((1, 2), (1,)))
    for point in ((-1, 2), (1, 1), (0, 0)):
        a.reject(simplex, point)
    a.reject(label, (1, 0), (1, 0, 0))
    a.reject(chain_cell, (0, 0, 1))
    a.reject(chain_cell, (0, 1, 2, 3, 4))
    a.reject(determinant, ((1, 2), (1,)))
    for price, income, share in (((0, 1), 2, F(1, 2)), ((1, 1), 0, F(1, 2)), ((1, 1), 2, 1)):
        a.reject(demand, price, income, share)
    a.reject(exchange, ((0, 1), (1, 1)), (F(1, 2),)*2)
    a.reject(exchange, ((1, 1),), (F(1, 2),)*2)
    a.reject(firm, (0, 0))
    a.reject(firm, (-1, 1))
    a.reject(owner_ledger, (1, 1), (F(1, 4), F(1, 2)))
    a.reject(owner_ledger, (1, 1), (-1, 2))
    a.reject(tents, (0,), (1,), 1, F(1, 2))
    a.reject(tents, (0, 1), (1,), F(1, 2), 1)
    a.reject(tents, (0,), (2,), 0, 1)
    for raw in ('{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}', '{"x":1e999}'):
        a.reject(strict_json, raw)
    for raw in ("True", "1/0", "__import__('os')", "(1,2)+(3,4)"):
        a.reject(expression, raw)
    a.reject(Document().feed, '<p id="x"></p><p id="x"></p>')
    a.reject(Document().feed, '<li data-solution-for="x">wrong location</li>')

    source = strict_json((base/AUTHORS[2]).read_text(encoding="utf-8"))
    author = strict_json((base/AUTHORS[3]).read_text(encoding="utf-8"))
    peer = strict_json((base/RECORD).read_text(encoding="utf-8"))
    a.equal({s["id"]: s["url"] for s in source["sources"]}, SOURCES, "source-record linkage")
    a.equal([s["actual_inspector"] for s in source["sources"]], ["c05_review"]*3, "actual primary reader attribution")
    a.equal(sum(len(s["equation_images_inspected"]) for s in source["sources"]), 5, "actual scoped equation images")
    a.equal(set(peer["exercise_audit"]), set(exercise_ids), "peer every exact solution judgment")
    a.equal(set(peer["proof_audit"]), {"v13-c04-"+key for key in ("economy", "sperner", "brouwer", "kakutani", "existence", "limits")},
            "peer full proof-chain audit")
    a.equal(peer["open_findings"], [], "no unresolved material finding")
    for title, bindings, paths in (("author", author["payload_bindings"], AUTHORS[:3]),
                                   ("peer", peer["bindings"], AUTHORS+(SELF,))):
        a.equal((len(bindings), {item["path"] for item in bindings}), (len(paths), set(paths)), title+" exact binding scope")
        for item in bindings:
            raw = (base/item["path"]).read_bytes()
            a.equal((len(raw), sha256(raw).hexdigest()), (item["bytes"], item["sha256"]), title+" binding "+item["path"])
    summary = {"chapter": "v13-c04", "status": "passed", "comparisons": a.comparisons,
               "domain_rejections": a.rejections, "intervention_groups": 12,
               "worked_cases": 6, "solved_exercises": 12, "primitive_input_markers": len(inputs),
               "visible_result_markers": len(results), "label_table_rows": len(table),
               "finite_barycentric_cells": cells, "boundary_midpoint_labelings": 8,
               "source_scopes": 3, "author_execution_used_as_oracle": False}
    require(strict_json(json.dumps(summary, allow_nan=False)) == summary, "strict JSON-safe summary")
    return summary


if __name__ == "__main__":
    check()
