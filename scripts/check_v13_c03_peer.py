#!/usr/bin/env python3
"""Independent, quiet, standard-library peer checks for V13 C03.

Run directly from any directory, or call check(root=None). The exact runtime
contains the four canonical author files and the two peer files. This checker
does not import or execute the author's checker. Finite witnesses corroborate
the separately recorded proof review; they do not replace universal proofs.
"""

import ast
from decimal import Decimal, localcontext
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from itertools import combinations, product
import json
from pathlib import Path


AUTHORS = (
    "content/chapters/v13-c03.html",
    "scripts/check_v13_c03.py",
    "content/reviews/v13-c03-sources.json",
    "content/reviews/v13-c03-author.json",
)
SELF = "scripts/check_v13_c03_peer.py"
RECORD = "content/reviews/v13-c03-peer.json"
SOURCE_URLS = {
    "mit-expected-utility": "https://ocw.mit.edu/courses/14-123-microeconomic-theory-iii-spring-2015/02f917a9f6cf1d6a3c7397d457b23951_MIT14_123S15_Chap2.pdf",
    "mit-risk-attitudes": "https://ocw.mit.edu/courses/14-123-microeconomic-theory-iii-spring-2015/f7d39636011bcb5ab9e0ef9dca295ccf_MIT14_123S15_Chap3.pdf",
    "v13-c03-mit-dominance2015": "https://ocw.mit.edu/courses/14-123-microeconomic-theory-iii-spring-2015/875150f8deb05a910756a02a4f9f78a5_MIT14_123S15_Chap4.pdf",
    "v13-c03-borgers-blackwell2023": "https://websites.umich.edu/~tborgers/BlackwellDominance.pdf",
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def rational(value):
    require(type(value) is int or isinstance(value, F), "exact rational required")
    value = F(value)
    require(abs(value) <= 10**6 and value.denominator <= 10**9, "rational bound")
    return value


def vector(values, limit=8):
    require(type(values) in (tuple, list) and 1 <= len(values) <= limit, "vector shape")
    return tuple(rational(x) for x in values)


def probabilities(values, limit=8):
    result = vector(values, limit)
    require(all(x >= 0 for x in result) and sum(result) == 1, "probability simplex")
    return result


def law(points, masses):
    x, p = vector(points), probabilities(masses)
    require(len(x) == len(p) and all(a < b for a, b in zip(x, x[1:])), "ordered support")
    return x, p


def expected(distribution, utility=lambda x: x):
    x, p = distribution
    return sum((w * utility(z) for z, w in zip(x, p)), F(0))


def variance(distribution):
    # Two independent copies give Var(X) = E[(X-X')^2]/2.
    x, p = distribution
    return sum((p[i] * p[j] * (x[i] - x[j])**2
                for i in range(len(x)) for j in range(len(x))), F(0)) / 2


def mix(left, right, weight):
    a = rational(weight)
    require(0 <= a <= 1, "mixture weight")
    support = tuple(sorted(set(left[0]) | set(right[0])))
    lp, rp = dict(zip(*left)), dict(zip(*right))
    return law(support, tuple(a * lp.get(x, 0) + (1 - a) * rp.get(x, 0) for x in support))


def cdf(distribution, threshold):
    t = rational(threshold)
    return expected(distribution, lambda x: F(x <= t))


def lower(distribution, threshold):
    t = rational(threshold)
    return expected(distribution, lambda x: max(t - x, F(0)))


def matrix(rows):
    require(type(rows) in (tuple, list) and 1 <= len(rows) <= 4, "matrix rows")
    result = tuple(vector(row, 4) for row in rows)
    require(len({len(row) for row in result}) == 1, "ragged matrix")
    return result


def experiment(rows):
    result = matrix(rows)
    for row in result:
        probabilities(row, 4)
    return result


def multiply(left, right):
    a, b = matrix(left), matrix(right)
    require(len(a[0]) == len(b), "matrix dimensions")
    return tuple(tuple(sum((a[i][k] * b[k][j] for k in range(len(b))), F(0))
                       for j in range(len(b[0]))) for i in range(len(a)))


def decision_inputs(channel, prior, payoffs):
    p, pi, u = experiment(channel), probabilities(prior, 4), matrix(payoffs)
    require(len(p) == len(pi) == len(u), "decision dimensions")
    return p, pi, u


def policy_values(channel, prior, payoffs):
    p, pi, u = decision_inputs(channel, prior, payoffs)
    # Whole contingent plans are enumerated before any posterior maximization.
    return tuple((rule, sum((pi[i] * p[i][s] * u[i][rule[s]]
                             for i in range(len(p)) for s in range(len(p[0]))), F(0)))
                 for rule in product(range(len(u[0])), repeat=len(p[0])))


def posterior_table(channel, prior):
    p, pi = experiment(channel), probabilities(prior, 4)
    require(len(p) == len(pi), "posterior dimensions")
    columns = tuple(tuple(pi[i] * p[i][s] for i in range(len(p)))
                    for s in range(len(p[0])))
    mass = tuple(sum(col) for col in columns)
    posterior = tuple(tuple(x / q for x in col) if q else None for col, q in zip(columns, mass))
    return mass, posterior


def upper_envelope(support, heights, point):
    y, h, x = vector(support, 4), vector(heights, 4), rational(point)
    require(len(y) == len(h) and all(a < b for a, b in zip(y, y[1:])), "hull data")
    require(y[0] <= x <= y[-1], "hull point outside support")
    candidates = [h[i] for i in range(len(y)) if y[i] == x]
    for i, j in combinations(range(len(y)), 2):
        if y[i] <= x <= y[j]:
            a = (y[j] - x) / (y[j] - y[i])
            candidates.append(a * h[i] + (1 - a) * h[j])
    return max(candidates)


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "duplicate JSON key")
            result[key] = value
        return result

    def bad_constant(value):
        raise ValueError("nonfinite JSON constant: " + value)

    def finite_float(value):
        x = Decimal(value)
        require(x.is_finite() and abs(x) <= Decimal("1e100"), "JSON numeric bound")
        return float(x)

    return json.loads(raw, object_pairs_hook=pairs, parse_constant=bad_constant,
                      parse_float=finite_float)


def displayed_number(text):
    # Read only integer/fraction tuples; never eval manuscript content.
    raw = text.split("=", 1)[-1].strip()
    require(len(raw) <= 1000, "display size")
    tree = ast.parse(raw, mode="eval")

    def visit(node, depth=0):
        require(depth <= 8, "display depth")
        if isinstance(node, ast.Constant) and type(node.value) is int:
            return rational(node.value)
        if isinstance(node, (ast.Tuple, ast.List)):
            require(1 <= len(node.elts) <= 8, "display shape")
            return tuple(visit(x, depth + 1) for x in node.elts)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            value = visit(node.operand, depth + 1)
            require(isinstance(value, F), "display scalar sign")
            return -value if isinstance(node.op, ast.USub) else value
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            a, b = visit(node.left, depth + 1), visit(node.right, depth + 1)
            require(isinstance(a, F) and isinstance(b, F) and b != 0, "display division")
            return rational(a / b)
        raise ValueError("unsupported display expression")

    return visit(tree.body)


class Document(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids, self.markers, self.sources = {}, {}, {}
        self.exercises, self.solutions, self.worked, self.hrefs = [], [], [], []
        self.exercise_depth, self.solution_depth = 0, 0
        self.stack, self.active, self.text = [], None, []

    def handle_starttag(self, tag, attrs):
        data = dict(attrs)
        require(len(data) == len(attrs), "duplicate HTML attribute")
        if "id" in data:
            require(data["id"] not in self.ids, "duplicate HTML id")
            self.ids[data["id"]] = tag
        classes = data.get("class", "").split()
        if "worked" in classes:
            self.worked.append(data.get("id"))
        is_exercises = tag == "ol" and "exercises" in classes
        is_solutions = tag == "details" and "solutions" in classes
        if tag == "li" and self.exercise_depth:
            self.exercises.append(data.get("id"))
        if tag == "li" and "data-solution-for" in data:
            require(self.solution_depth > 0, "answer outside grouped solutions")
            self.solutions.append(data["data-solution-for"])
        self.exercise_depth += int(is_exercises)
        self.solution_depth += int(is_solutions)
        if tag not in ("br", "hr", "img", "meta", "link", "input"):
            self.stack.append((tag, is_exercises, is_solutions))
        if "data-calc" in data:
            key = data["data-calc"]
            require(tag == "span" and self.active is None and key not in self.markers, "numeric marker")
            self.markers[key] = ""
            self.active = key
        if tag == "a":
            self.hrefs.append(data.get("href", ""))
            if "data-source" in data:
                require(data["data-source"] not in self.sources, "duplicate source marker")
                self.sources[data["data-source"]] = data.get("href")

    def handle_endtag(self, tag):
        if tag == "span" and self.active is not None:
            self.active = None
        require(self.stack and self.stack[-1][0] == tag, "HTML nesting")
        _, ex, sol = self.stack.pop()
        self.exercise_depth -= int(ex)
        self.solution_depth -= int(sol)

    def handle_data(self, text):
        self.text.append(text)
        if self.active is not None:
            self.markers[self.active] += text


class Audit:
    def __init__(self):
        self.comparisons = self.rejections = self.rules = self.tables = 0

    def eq(self, actual, expected, label):
        self.comparisons += 1
        require(actual == expected, label + ": " + repr(actual) + " != " + repr(expected))

    def yes(self, condition, label):
        self.eq(bool(condition), True, label)

    def rejects(self, function, *args):
        self.rejections += 1
        try:
            function(*args)
        except (ValueError, TypeError, SyntaxError, ZeroDivisionError):
            return
        raise ValueError("invalid-domain case accepted: " + function.__name__)

    def value(self, channel, prior, payoffs):
        plans = policy_values(channel, prior, payoffs)
        self.rules += len(plans)
        self.tables += 1
        value = max(total for _, total in plans)
        q, beta = posterior_table(channel, prior)
        u = matrix(payoffs)
        columns = tuple(tuple(sum(b[i] * u[i][a] for i in range(len(u)))
                              for a in range(len(u[0]))) if b is not None else None for b in beta)
        self.eq(value, sum((w * max(col) for w, col in zip(q, columns) if w), F(0)),
                "whole plans versus posterior action maxima")
        no_signal = max(sum(F(prior[i]) * u[i][a] for i in range(len(u))) for a in range(len(u[0])))
        perfect = sum(F(prior[i]) * max(u[i]) for i in range(len(u)))
        self.yes(no_signal <= value <= perfect, "ignore/full-revelation bounds")
        common = set(range(len(u[0])))
        for col in columns:
            if col is not None:
                common &= {a for a, v in enumerate(col) if v == max(col)}
        self.eq(value == no_signal, bool(common), "common posterior optimum iff zero value")
        for i in range(len(u)):
            self.eq(sum((w * b[i] for w, b in zip(q, beta) if w), F(0)), F(prior[i]), "Bayes plausibility")
        return value


def independent_cases(audit):
    a, markers = audit, {}
    u = (F(0), F(3, 10), F(1))
    ap, bp = (F(1, 5), F(1, 2), F(3, 10)), (F(0), F(3, 4), F(1, 4))
    lottery_pair = (law(u, ap), law(u, bp))
    markers["eu-values"] = tuple(expected(x) for x in lottery_pair)
    markers["affine-values"] = tuple(expected(x, lambda z: 2 * z + 5) for x in lottery_pair)
    markers["nonlinear-values"] = tuple(expected(x, lambda z: z*z) for x in lottery_pair)
    a.yes(markers["eu-values"][1] > markers["eu-values"][0], "EU ranking")
    a.eq(markers["affine-values"], tuple(2*x+5 for x in markers["eu-values"]), "affine expectation")
    a.yes(markers["nonlinear-values"][0] > markers["nonlinear-values"][1], "ordinal prize map fails")
    p, q, r = law((2,), (1,)), law((0, 4), (F(2, 5), F(3, 5))), law((10,), (1,))
    four = (p, q, mix(p, r, F(1, 2)), mix(q, r, F(1, 2)))
    means, variances = tuple(map(expected, four)), tuple(map(variance, four))
    a.eq(means, (F(2), F(12, 5), F(6), F(31, 5)), "all counterexample means")
    a.eq(variances, (F(0), F(96, 25), F(16), F(409, 25)), "pairwise-difference variances")
    markers["independence-values"] = tuple(m-v/4 for m, v in zip(means, variances))
    v = markers["independence-values"]
    a.yes(v[0] > v[1] and v[2] < v[3], "common-lottery independence reversal")
    a.eq(mix(p, q, 0), law((0, 2, 4), (F(2, 5), 0, F(3, 5))), "mixture endpoint permits zero masses")
    a.eq(mix(p, q, 1), law((0, 2, 4), (0, 1, 0)), "other mixture endpoint")

    wealth = law((7, 13), (F(1, 2), F(1, 2)))
    reciprocal_ce = -1 / expected(wealth, lambda x: -1/x)
    a.eq(reciprocal_ce, F(91, 10), "harmonic CE")
    a.eq(expected(wealth) - reciprocal_ce, F(9, 10), "reciprocal premium")
    with localcontext() as ctx:
        ctx.prec = 50
        ce = Decimal(91).sqrt()
        markers["log-premium"] = format(Decimal(10) - ce, ".6f")
        a.yes(Decimal(reciprocal_ce.numerator)/Decimal(reciprocal_ce.denominator) < ce < 10,
              "global comparative CE and strict Jensen")
        for e in (F(-1), F(0), F(1, 2), F(1)):
            eps = Decimal(e.numerator) / Decimal(e.denominator)
            s = (100 - 9*eps*eps).sqrt()
            quadratic = 9*eps*eps/20
            difference = 10-s-quadratic
            rationalized = 81*eps**4/(20*(10+s)**2)
            a.yes(abs(difference-rationalized) < Decimal("1e-47"), "exact symmetric log error")
            a.yes(difference >= 0, "local log approximation below true premium")
            if e == F(1, 2):
                markers["half-local"] = F(quadratic)
                markers["half-error-bound"] = F(81, 20*16*19**2)
                markers["half-error"] = format(difference, ".6f")
                bound = Decimal(81)/Decimal(20*16*19**2)
                a.yes(0 < difference < bound < Decimal(".001"), "proved half-risk error bound")
    for x in (F(1, 2), F(7), F(13)):
        up, upp, vp, vpp = 1/x, -1/x**2, 1/x**2, -2/x**3
        au, av = -upp/up, -vpp/vp
        a.eq((au, av), (1/x, 2/x), "absolute risk-aversion derivatives")
        a.eq(vp/(up*up)*(au-av), -1/x, "phi second derivative at log(x)")

    shift_x, shift_y = law((2, 5), (F(1, 2),)*2), law((1, 4), (F(1, 2),)*2)
    knots = (1, 2, 4, 5)
    markers["shift-cdf"] = tuple(cdf(shift_x, t)-cdf(shift_y, t) for t in knots)
    a.eq((expected(shift_x), expected(shift_y)), (F(7, 2), F(5, 2)), "unequal means preclude spread")
    for values in ((0, 0, 0, 0), (0, 1, 2, 3), (0, 0, 0, 1), (0, 1, 1, 1)):
        utility = dict(zip(knots, values))
        direct = expected(shift_x, utility.__getitem__) - expected(shift_y, utility.__getitem__)
        increments = sum((values[k+1]-values[k])*(cdf(shift_y, knots[k])-cdf(shift_x, knots[k]))
                         for k in range(len(knots)-1))
        a.eq(direct, increments, "FSD summation including zero support masses")
        a.yes(direct >= 0, "FSD monotone utility witness")
    spread_x, spread_y = law((3,), (1,)), law((1, 5), (F(1, 2),)*2)
    a.eq(expected(spread_y), expected(spread_x), "conditional mean for sure-3 spread")
    a.eq((expected(spread_x, lambda x: min(x, 3)), expected(spread_y, lambda x: min(x, 3))),
         (F(3), F(2)), "spread capped utility")
    a.yes(cdf(spread_x, 1) < cdf(spread_y, 1) and cdf(spread_x, 3) > cdf(spread_y, 3),
          "spread does not imply FSD")
    x = law((0, 3), (F(1, 3), F(2, 3)))
    y = law((1, 5), (F(3, 4), F(1, 4)))
    knots = tuple(sorted(set(x[0]) | set(y[0])))
    markers["incomparable-variances"] = (variance(x), variance(y))
    markers["incomparable-cdf"] = tuple(cdf(x, t)-cdf(y, t) for t in knots)
    markers["incomparable-lower"] = tuple(lower(x, t)-lower(y, t) for t in knots)
    a.eq((expected(x), expected(y)), (F(2), F(2)), "variance trap equal means")
    a.eq((lower(x, -2), lower(y, -2), lower(x, 9), lower(y, 9)), (0, 0, 7, 7), "all-real tails")
    for key, cap in (("cap-one", 1), ("cap-three", 3)):
        markers[key] = (expected(x, lambda z: min(z, cap)), expected(y, lambda z: min(z, cap)))
        for slope in (F(1, 10), F(3)):
            gap = expected(x, lambda z: min(z, cap)+slope*z)-expected(y, lambda z: min(z, cap)+slope*z)
            a.eq(gap, markers[key][0]-markers[key][1], "strictly increasing cap transfer")
    # The lower-partial-moment difference is affine between every union knot.
    for left, right in zip(knots, knots[1:]):
        midpoint = F(left+right, 2)
        a.eq(lower(x, midpoint)-lower(y, midpoint),
             (lower(x, left)-lower(y, left)+lower(x, right)-lower(y, right))/2, "SSD between knots")
    for slopes in ((F(4), F(2), F(1)), (F(3), F(3), F(0))):
        vals = [F(0)]
        for k, d in enumerate(slopes):
            vals.append(vals[-1]+d*(knots[k+1]-knots[k]))
        for z, val in zip(knots, vals):
            hinge = vals[-1]+slopes[-1]*(z-knots[-1])-sum(
                (slopes[j-1]-slopes[j])*max(F(knots[j]-z), F(0)) for j in range(1, len(knots)-1))
            a.eq(hinge, val, "finite concave-utility hinge identity")

    # New two-row coupling, beyond the chapter's constant-X example.
    gamma = ((F(1, 3), F(1, 6)), (F(1, 6), F(1, 3)))
    cx, cy = (F(1), F(2)), (F(0), F(3))
    for i, row in enumerate(gamma):
        a.eq(sum(row), F(1, 2), "coupling X marginal")
        a.eq(sum(row[j]*cy[j] for j in range(2))/sum(row), cx[i], "coupling conditional mean")
    for j in range(2):
        a.eq(sum(row[j] for row in gamma), F(1, 2), "coupling Y marginal")
    hx, hy = law(cx, (F(1, 2),)*2), law(cy, (F(1, 2),)*2)
    for t in (-1, 0, 1, 2, 3, 4):
        a.yes(lower(hx, t) <= lower(hy, t), "new finite mean-preserving spread")
    a.yes(x[0][0] < y[0][0], "variance-trap support defeats mean-preserving coupling")
    hull_knots = (F(0), F(1, 2), F(1), F(2), F(3))
    envelope = tuple(upper_envelope((0, 1, 3), (0, 2, 1), z) for z in hull_knots)
    a.eq(envelope, (0, 1, 2, F(3, 2), 1), "two-point upper-hull maximizers")
    slopes = tuple((envelope[j+1]-envelope[j])/(hull_knots[j+1]-hull_knots[j]) for j in range(4))
    a.eq(slopes, (2, 2, F(-1, 2), F(-1, 2)), "bounded decreasing envelope slopes")
    a.yes(all(d+F(1, 2) >= 0 for d in slopes), "finite affine monotonicity correction")

    prior = (F(1, 3), F(2, 3))
    p = ((F(3, 4), F(1, 4)), (F(1, 4), F(3, 4)))
    u = ((6, 0), (-3, 0))
    qmass, beta = posterior_table(p, prior)
    markers["bayes-signal"], markers["bayes-high"] = qmass, tuple(b[0] for b in beta)
    markers["bayes-invest"] = tuple(sum(b[i]*u[i][0] for i in range(2)) for b in beta)
    vp = a.value(p, prior, u)
    a.eq(vp, F(1), "case-4 whole-plan value")
    a.eq(a.value(p, prior, ((6, 0), (0, 0))), F(2), "information with no strict value")
    a.eq(a.value(((F(3, 4), F(1, 4), 0), (F(1, 4), F(3, 4), 0)), prior, u), vp,
         "impossible added signal changes no decision")
    _, absent = posterior_table(((1, 0), (1, 0)), prior)
    a.eq(absent[1], None, "zero signal posterior undefined")
    g = ((F(2, 3), F(1, 3)), (F(1, 3), F(2, 3)))
    q = multiply(p, g)
    markers["garbled-matrix"] = q
    qmass, beta = posterior_table(q, prior)
    markers["garbled-signal"], markers["garbled-high"] = qmass, tuple(b[0] for b in beta)
    vq = a.value(q, prior, u)
    a.eq(vq, F(1, 3), "garbled optimal value")
    a.eq(tuple(sum(b[i]*u[i][0] for i in range(2)) for b in beta), (F(12, 17), F(-12, 19)),
         "garbled conditional investment returns")
    simulate = sum(prior[i]*p[i][s]*g[s][0]*u[i][0] for i in range(2) for s in range(2))
    a.eq(simulate, vq, "randomized P rule reproduces Q rule")
    determinant = q[0][0]*q[1][1]-q[0][1]*q[1][0]
    reverse = tuple(tuple((q[1][1]*p[0][j]-q[0][1]*p[1][j])/determinant if i == 0
                          else (q[0][0]*p[1][j]-q[1][0]*p[0][j])/determinant
                          for j in range(2)) for i in range(2))
    markers["reverse-kernel"] = reverse
    a.eq(multiply(q, reverse), p, "unique reverse linear solution")
    a.yes(any(z < 0 for row in reverse for z in row), "reverse solution is not stochastic")
    markers["cost-net"] = vp-F(3, 4)
    a.yes(markers["cost-net"] < vq, "acquisition reverses free-information choice")
    extra = vp-vq
    a.eq(extra, F(2, 3), "exact extra-fee boundary")
    for fee, relation in ((extra-F(1, 100), 1), (extra, 0), (extra+F(1, 100), -1)):
        gap = vp-fee-vq
        a.eq((gap > 0)-(gap < 0), relation, "two sides and equality of fee boundary")

    e = ((1, 0), (0, 1), (0, 1))
    h = ((0, 1), (1, 0), (0, 1))
    uniform = (F(1, 3),)*3
    job1, job2 = e, h
    markers["partition-values"] = tuple(tuple(a.value(channel, uniform, job) for channel in (e, h))
                                         for job in (job1, job2))
    classification = tuple(tuple(F(i == j) for j in range(3)) for i in range(3))
    markers["classification-values"] = tuple(a.value(channel, uniform, classification) for channel in (e, h))
    energies = []
    for channel in (e, h):
        masses, posterior = posterior_table(channel, uniform)
        energies.append(sum(w*sum((b[i]-uniform[i])**2 for i in range(3)) for w, b in zip(masses, posterior)))
    a.eq(energies[0], energies[1], "same posterior energy without experiment equivalence")
    markers["posterior-energy"] = energies[0]
    a.yes(e[1] == e[2] and h[1] != h[2] and h[0] == h[2] and e[0] != e[2], "both repeated-row obstructions")

    # Independent closest-point witness: E's attainable rows 2 and 3 coincide.
    projection = ((F(0), F(1)), (F(1, 2), F(1, 2)), (F(1, 2), F(1, 2)))
    residual = tuple(tuple(F(h[i][j])-projection[i][j] for j in range(2)) for i in range(3))
    inner = lambda left, right: sum(x*y for row, col in zip(left, right) for x, y in zip(row, col))
    a.eq(inner(residual, residual), F(1), "positive separator squared distance")
    a.eq(inner(residual, h)-inner(residual, projection), inner(residual, residual), "strict separator identity")
    for rule in product(range(2), repeat=2):
        kernel = tuple(tuple(F(j == rule[i]) for j in range(2)) for i in range(2))
        a.eq(inner(residual, multiply(e, kernel)), F(0), "all extreme garblings below separator")
    for pi in (uniform, (F(1, 2), F(1, 3), F(1, 6))):
        payoff = tuple(tuple(z/pi[i] for z in row) for i, row in enumerate(residual))
        a.eq((a.value(e, pi, payoff), a.value(h, pi, payoff)), (F(0), F(1)), "separator-to-payoff full-support witness")
    for payoffs in (((2, -1), (-5, 8)), ((-4, 7), (9, -3))):
        a.eq(a.value(((1,), (1,)), (1, 0), payoffs), a.value(((1, 0), (0, 1)), (1, 0), payoffs),
             "zero-prior all-state distinction invisible to decisions")
    return markers


def check(root=None):
    require(root is None or isinstance(root, (str, Path)), "root must be a path")
    base = Path(__file__).resolve().parents[1] if root is None else Path(root).resolve()
    a = Audit()
    html = (base / AUTHORS[0]).read_text(encoding="utf-8")
    doc = Document()
    doc.feed(html)
    doc.close()
    a.eq((doc.stack, doc.active), ([], None), "closed manuscript markup")
    ids = ["v13-c03-ex"+str(i) for i in range(1, 13)]
    a.eq(doc.exercises, ids, "twelve exact exercise IDs")
    a.eq(doc.solutions, ids, "twelve exact paired answers")
    a.eq(doc.worked, ["v13-c03-case"+str(i) for i in range(1, 7)], "six worked cases")
    a.yes(all(key.startswith("v13-c03-") for key in doc.ids), "namespaced IDs")
    a.eq(doc.sources, SOURCE_URLS, "scoped primary source links")
    a.eq({href for href in doc.hrefs if not href.startswith("https://")},
         {"v13-c01.html", "v13-c02.html", "v03-c01.html", "v03-c10.html", "v02-c10.html", "v13-c04.html"},
         "flat prerequisite and successor routes")
    a.yes("Delayed retention" in "".join(doc.text), "answered delayed retention present")
    markers = independent_cases(a)
    a.eq(set(doc.markers), set(markers), "all printed numeric anchors covered")
    for key, value in markers.items():
        printed = doc.markers[key].strip()
        a.eq(printed if isinstance(value, str) else displayed_number(printed), value, "printed "+key)

    for value in (True, "1", 0.5, float("nan"), float("inf"), 1j, 10**6+1, F(1, 10**9+1)):
        a.rejects(rational, value)
    for values in ((), [1]*9, [F(1, 2)], [-1, 2], [0, 0], [True]):
        a.rejects(probabilities, values)
    for points, weights in (((2, 1), (F(1, 2),)*2), ((1, 1), (F(1, 2),)*2), ((1, 2), (1,))):
        a.rejects(law, points, weights)
    a.rejects(mix, law((0,), (1,)), law((1,), (1,)), F(3, 2))
    for rows in ((((1, 0), (1,)), ((F(1, 2), F(1, 4)), (0, 1)), ((1, 0),)*5)):
        a.rejects(experiment, rows)
    a.rejects(multiply, ((1, 0),), ((1, 0),))
    a.rejects(policy_values, ((1,), (1,)), (1,), ((1,), (2,)))
    a.rejects(policy_values, ((1,), (1,)), (F(1, 2),)*2, ((1,),))
    a.rejects(posterior_table, ((1,), (1,)), (1,))
    a.rejects(upper_envelope, (0, 1, 3), (0, 2, 1), 4)
    for text in ('{"a":1,"a":2}', '{"a":NaN}', '{"a":Infinity}', '{"a":1e999}'):
        a.rejects(strict_json, text)
    for text in ("True", "1/0", "1.2", "__import__('os')", "[1]*4"):
        a.rejects(displayed_number, text)
    a.rejects(Document().feed, '<p id="v13-c03-x"></p><p id="v13-c03-x"></p>')
    a.rejects(Document().feed, '<span data-calc="x">1</span><span data-calc="x">2</span>')
    a.rejects(Document().feed, '<li data-solution-for="v13-c03-ex1">outside</li>')

    sources = strict_json((base / AUTHORS[2]).read_text(encoding="utf-8"))
    author = strict_json((base / AUTHORS[3]).read_text(encoding="utf-8"))
    peer = strict_json((base / RECORD).read_text(encoding="utf-8"))
    a.eq({p["id"]: p["url"] for p in sources["proposals"]}, SOURCE_URLS, "source record scopes")
    a.eq([p["inspection"]["actual_inspector"] for p in sources["proposals"]], ["ito_author"]*4, "actual source reader attribution")
    a.eq(sum(len(p["inspection"]["actual_image_physical_pages"]) for p in sources["proposals"]), 8, "documented eight images")
    blackwell = next(p for p in sources["proposals"] if p["id"] == "v13-c03-borgers-blackwell2023")
    a.eq(blackwell["inspection"]["physical_text_pages"], list(range(1, 8)), "Blackwell text scope only")
    a.eq(blackwell["inspection"]["actual_image_physical_pages"], [], "no unsupported Blackwell image claim")
    a.yes("retained_pdf" not in blackwell and "403" in " ".join(blackwell["limits"]), "inaccessible direct PDF documented")
    a.eq({item["id"] for item in peer["exercise_audit"]}, set(ids), "peer exact-prompt judgments")
    a.eq({item["id"] for item in peer["proof_audit"]},
         {"v13-c03-eu", "v13-c03-risk", "v13-c03-dominance", "v13-c03-separation", "v13-c03-bayes", "v13-c03-blackwell"},
         "peer complete proof judgments")
    a.eq(peer["open_findings"], [], "no unresolved peer finding")
    for label, record, paths in (("author", author, AUTHORS[:3]), ("peer", peer, AUTHORS+(SELF,))):
        bindings = record["bindings"]
        a.eq(len(bindings), len(paths), label+" binding count")
        a.eq({item["path"] for item in bindings}, set(paths), label+" exact nonself binding set")
        for item in bindings:
            raw = (base / item["path"]).read_bytes()
            a.eq(len(raw), item["bytes"], label+" bytes "+item["path"])
            a.eq(sha256(raw).hexdigest(), item["sha256"], label+" hash "+item["path"])
    summary = {
        "chapter": "v13-c03", "status": "passed", "comparisons": a.comparisons,
        "rejections": a.rejections, "mathematical_interventions": 11,
        "policy_tables": a.tables, "enumerated_rules": a.rules,
        "numeric_anchors": len(markers), "worked_cases": 6, "solved_exercises": 12,
        "source_scopes": 4, "author_execution_used_as_oracle": False,
    }
    a_safe = strict_json(json.dumps(summary, allow_nan=False))
    require(a_safe == summary, "strict JSON-safe summary")
    return summary


if __name__ == "__main__":
    check()
