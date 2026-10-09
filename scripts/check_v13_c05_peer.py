#!/usr/bin/env python3
"""Independent, quiet C05 peer certificates; exactly six canonical runtime files.

Original manuscript primitives drive the oracle. Neither the author checker nor
its outputs are imported. Finite witnesses accompany, and do not replace, the
separate review of the universal separation, welfare and Arrow proofs.
"""
import ast
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from itertools import permutations
import json
from pathlib import Path


AUTHORS = ("content/chapters/v13-c05.html", "scripts/check_v13_c05.py",
           "content/reviews/v13-c05-sources.json", "content/reviews/v13-c05-author.json")
SELF, RECORD = "scripts/check_v13_c05_peer.py", "content/reviews/v13-c05-peer.json"
SOURCES = {
    "v13-c05-border-welfare2016": "https://healy.econ.ohio-state.edu/kcb/Notes/SecondWelfare.pdf",
    "v13-c05-mit-socialchoice2010": "https://ocw.mit.edu/courses/6-254-game-theory-with-engineering-applications-spring-2010/6515e0e0f030169a75c41139c2f554ac_MIT6_254S10_lec21.pdf",
    "v13-c05-borgers-aggregation2021": "https://websites.umich.edu/~tborgers/GE.pdf",
    "v05-c05-mit-welfare": "https://ocw.mit.edu/courses/14-04-intermediate-microeconomic-theory-fall-2020/1gcajw7hbthjPcO8f8wCXWoKIBXEYkUEH_transcript.pdf",
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


def dot(left, right):
    a, b = vector(left), vector(right)
    require(len(a) == len(b), "inner product dimension")
    return sum((x*y for x, y in zip(a, b)), F(0))


def total(rows):
    require(type(rows) in (list, tuple) and 1 <= len(rows) <= 8, "row count")
    rows = tuple(vector(row) for row in rows)
    require(len({len(row) for row in rows}) == 1, "ragged rows")
    return tuple(sum(row[j] for row in rows) for j in range(len(rows[0])))


def demand(price, income, share):
    p, m, a = vector(price, 2), number(income), number(share)
    require(min(p) > 0 and m >= 0 and 0 < a < 1, "Cobb-Douglas domain")
    return (a*m/p[0], (1-a)*m/p[1])


def subsistence(price, income, floor):
    p, m, s = vector(price, 2), number(income), vector(floor, 2)
    require(min(p) > 0 and min(s) >= 0 and m >= dot(p, s), "subsistence affordability")
    r = m-dot(p, s)
    return tuple(s[j]+r/(2*p[j]) for j in range(2))


def ledger(price, endowments, shares, output, target):
    p, theta, y = vector(price, 2), vector(shares, 2), vector(output, 2)
    require(min(p) > 0 and min(theta) >= 0 and sum(theta) == 1, "price/ownership domain")
    require(type(endowments) in (list, tuple) and len(endowments) == 2, "two endowments")
    require(type(target) in (list, tuple) and len(target) == 2, "two target bundles")
    omega, x = tuple(vector(w, 2) for w in endowments), tuple(vector(v, 2) for v in target)
    require(all(min(w) >= 0 for w in omega+x), "nonnegative consumption/endowment")
    profit = dot(p, y)
    endowed = tuple(dot(p, w)+theta[i]*profit for i, w in enumerate(omega))
    wealth = tuple(dot(p, v) for v in x)
    transfers = tuple(wealth[i]-endowed[i] for i in range(2))
    return profit, endowed, wealth, transfers


def ballots(values):
    require(type(values) in (tuple, list) and 1 <= len(values) <= 9, "finite electorate")
    require(all(type(x) is str for x in values), "ballot strings")
    symbols = set(values[0])
    require(2 <= len(symbols) <= 6, "finite alternatives")
    require(all(len(v) == len(symbols) and set(v) == symbols for v in values), "strict common-domain ballots")
    return tuple(values), tuple(sorted(symbols))


def pair_votes(values, left, right):
    profile, symbols = ballots(values)
    require(left in symbols and right in symbols and left != right, "distinct alternatives")
    return sum(v.index(left) < v.index(right) for v in profile)


def borda(values):
    profile, symbols = ballots(values)
    score = dict.fromkeys(symbols, 0)
    for vote in profile:
        for points, name in enumerate(reversed(vote)):
            score[name] += points
    return tuple(score[name] for name in symbols)


def weak_order(blocks):
    require(type(blocks) in (list, tuple) and 1 <= len(blocks) <= 4, "ordered partition")
    require(all(type(b) in (list, tuple) and b for b in blocks), "nonempty tie blocks")
    flat = tuple(x for b in blocks for x in b)
    require(2 <= len(flat) <= 4 and all(type(x) is int for x in flat), "finite alternative labels")
    require(len(set(flat)) == len(flat) and set(flat) == set(range(len(flat))), "partition of all alternatives")
    return tuple(next(k for k, block in enumerate(blocks) if x in block) for x in range(len(flat)))


def all_three_orders():
    # Ordered set partitions, not a Cartesian search over numerical rank codes.
    orders = set()
    for names in permutations(range(3)):
        for cut in range(4):
            blocks = [[names[0]]]
            for j in range(2):
                if cut & (1 << j):
                    blocks.append([])
                blocks[-1].append(names[j+1])
            orders.add(weak_order(blocks))
    return tuple(sorted(orders))


def compare(order, left, right):
    return (order[left] < order[right])-(order[left] > order[right])


def median_contests(policies, peaks):
    x, z = vector(policies), vector(peaks)
    require(tuple(sorted(set(x))) == x and len(x) >= 2, "ordered distinct policies")
    require(len(z) % 2 == 1 and all(p in x for p in z), "odd electorate with feasible peaks")
    m = sorted(z)[len(z)//2]
    votes = []
    for y in x:
        if y != m:
            signs = tuple((abs(p-m) < abs(p-y))-(abs(p-m) > abs(p-y)) for p in z)
            votes.append(tuple(signs.count(s) for s in (1, -1, 0)))
    return m, tuple(votes)


def social_optimum(resource, coefficients, mode):
    r, c = number(resource), vector(coefficients, 2)
    require(r > 0 and min(c) > 0 and mode in ("sum", "minimum"), "social objective domain")
    if mode == "sum":
        scale = r/sum(x*x for x in c)
        return tuple(scale*x*x for x in c)
    attainable_t_squared = r/sum(1/(x*x) for x in c)
    return tuple(attainable_t_squared/(x*x) for x in c)


def strict_json(text):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "duplicate JSON key")
            result[key] = value
        return result
    def bad(value):
        raise ValueError("nonfinite JSON constant: "+value)
    result = json.loads(text, object_pairs_hook=unique, parse_constant=bad)
    json.dumps(result, allow_nan=False)
    return result


def expression(text):
    raw = text.strip().replace("−", "-")
    require(len(raw) <= 1500, "marker size")
    tree = ast.parse(raw, mode="eval")
    require(sum(1 for _ in ast.walk(tree)) <= 300, "marker nodes")
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
            v, w = visit(node.left), visit(node.right)
            require(type(v) is F and type(w) is F and w != 0, "scalar division")
            return number(v/w)
        raise ValueError("unsupported numeric expression")
    return visit(tree.body)


class Document(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids, self.results, self.sources = {}, {}, {}
        self.worked, self.exercises, self.solutions, self.links, self.text = [], [], [], [], []
        self.stack, self.marker = [], None
        self.exdepth = self.soldepth = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        require(len(a) == len(attrs), "duplicate HTML attribute")
        if "id" in a:
            require(a["id"] not in self.ids, "duplicate HTML ID")
            self.ids[a["id"]] = tag
        classes = a.get("class", "").split()
        ex = tag == "ol" and "exercises" in classes
        sol = tag == "details" and "solutions" in classes
        if "worked" in classes:
            self.worked.append(a.get("id"))
        if tag == "li" and self.exdepth:
            self.exercises.append(a.get("id"))
        if "data-solution-for" in a:
            require(tag == "li" and self.soldepth, "paired answer disclosure")
            self.solutions.append(a["data-solution-for"])
        self.exdepth += int(ex)
        self.soldepth += int(sol)
        if tag not in ("br", "hr", "img", "input", "meta", "link"):
            self.stack.append((tag, ex, sol))
        if "data-calc" in a:
            require(tag == "span" and self.marker is None and a["data-calc"] not in self.results,
                    "single unique numeric marker")
            self.marker = (a["data-calc"], [])
        if tag == "a":
            self.links.append(a.get("href", ""))
            if "data-source" in a:
                require(a["data-source"] not in self.sources, "duplicate source marker")
                self.sources[a["data-source"]] = a.get("href")

    def handle_data(self, text):
        self.text.append(text)
        if self.marker is not None:
            self.marker[1].append(text)

    def handle_endtag(self, tag):
        require(self.stack and self.stack[-1][0] == tag, "balanced HTML nesting")
        _, ex, sol = self.stack.pop()
        self.exdepth -= int(ex)
        self.soldepth -= int(sol)
        if tag == "span" and self.marker is not None:
            key, pieces = self.marker
            self.results[key] = expression("".join(pieces))
            self.marker = None


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
    result = {}
    p, endowments, tastes = (1, 1), ((5, 1), (1, 5)), (F(1, 3), F(2, 3))
    wealth = tuple(dot(p, w) for w in endowments)
    x = tuple(demand(p, m, alpha) for m, alpha in zip(wealth, tastes))
    result.update({"exchange-wealth": wealth, "exchange-allocation": x})
    a.equal(total(x), total(endowments), "exchange commodity conservation")
    a.equal((x[0][0]*x[0][1]**2, x[1][0]**2*x[1][1]), (32, 32), "two exact utility cubes")
    a.equal(tuple(dot(p, v) for v in x), wealth, "exchange spent wealth")
    # The externality example keeps private budget optimality and loses own-bundle preferences.
    initial, amended = ((0, 3), (6, 0)), ((2, 2), (4, 0))
    utility = lambda v: (v[0][0]+2*v[0][1], v[1][0]-3*v[0][1])
    result["external-before"], result["external-after"] = utility(initial), utility(amended)
    a.equal((tuple(dot((1, 2), v) for v in initial), total(initial)), ((6, 6), (6, 3)), "initial budgets and resources")
    a.equal((total(amended), amended[0][0]-initial[0][0], amended[1][0]-initial[1][0]),
            ((6, 2), 2, -2), "funded compensation and one disposed unit")
    a.true(utility(amended)[0] == utility(initial)[0] and utility(amended)[1] > utility(initial)[1], "external Pareto improvement")
    # Without LNS, an equilibrium can park a surplus with a satiated household.
    a.equal((min(2, 1), 0), (min(1, 1), 0), "satiated household accepts strictly cheaper bundle")
    a.true(min(1, 1) == min(2, 1) and 1 > 0 and 1+1 == 2, "missing-LNS Pareto improvement witness")

    # Explicit noncompact boundary projection; these witnesses do not prove the lemma.
    for n in (4, 9):
        z, c, normal = (F(-1, n), F(-1, n)), (F(-1, n), 0), (0, 1)
        a.equal(tuple(c[j]-z[j] for j in range(2)), (0, F(1, n)), "nearest upper-half-plane normal")
        a.equal(dot(normal, (c[0], 0)), 0, "normalized separating normal has nonzero limit")
        lam, d, boundary, zn = F(1, 4), (1, 1), (0, 2), (F(1, n), 2)
        dn = tuple(d[j]+(1-lam)*(boundary[j]-zn[j])/lam for j in range(2))
        a.true(min(dn) > 0, "perturbed interior point stays in open quadrant")
        a.equal(tuple(lam*dn[j]+(1-lam)*zn[j] for j in range(2)),
                tuple(lam*d[j]+(1-lam)*boundary[j] for j in range(2)), "interior-segment exact identity")
    a.equal(dot((0, 1), (100, 1)), 1, "exterior-origin strict half-plane support")
    a.true(dot((1, 0), (2, 0)) > dot((1, 0), (1, -7)), "relative contour separated by ambient resource interior")
    a.true(dot((1, -1), (1, -3)) > dot((1, -1), (2, 0)), "negative price contradicts downward resource support")

    p, omega, theta = (2, 1), ((3, 1), (2, 2)), (F(1, 4), F(3, 4))
    # Optimize the full quadratic technology by its affine derivative and square remainder.
    n = (4*p[1]-p[0])/F(2*p[1])
    y = (-n, 4*n-n*n)
    a.equal((n, y), (1, (-1, 3)), "interior global production maximizer")
    a.equal((-1, 2, -1), (-p[1]*n*n, 2*p[1]*n, -p[1]), "profit minus optimum is negative square")
    target = ((F(10, 3), F(10, 3)), (F(2, 3), F(8, 3)))
    profit, endowed, target_wealth, transfers = ledger(p, omega, theta, y, target)
    result.update({"production-target": target, "target-wealth": target_wealth,
                   "owner-income": endowed, "target-transfers": transfers})
    a.equal((profit, total(target)), (1, total((total(omega), y))), "profit and material feasibility")
    a.equal(tuple(demand(p, m, alpha) for m, alpha in zip(target_wealth, (F(2, 3), F(1, 3)))), target, "target global demands")
    a.equal((sum(transfers), sum(endowed), sum(target_wealth)), (0, 14, 14), "owned profits and balanced transfers")
    swapped = ledger(p, omega, tuple(reversed(theta)), y, target)
    result["changed-owner-income"], result["changed-transfers"] = swapped[1], swapped[3]
    a.equal(sum(swapped[3]), 0, "ownership change preserves transfer balance")
    result["ignored-profit-transfers"] = tuple(target_wealth[i]-dot(p, omega[i]) for i in range(2))
    a.equal(sum(result["ignored-profit-transfers"]), profit, "omitted profit creates unfunded net receipt")
    scaled = ledger((14, 7), omega, theta, y, target)
    a.equal(scaled, tuple(7*z if type(z) is F else tuple(7*v for v in z) for z in (profit, endowed, target_wealth, transfers)), "nominal price normalization")

    result["boundary-wealth"] = (dot((1, 0), (0, 0)), dot((1, 0), (1, 1)))
    a.equal(dot((1, 0), (0, 9)), 0, "zero-wealth free-good improvement is affordable")
    a.true(9 > 0 and min(1, 1) == 1, "support alone allows unbounded better free consumption")
    a.equal((dot((1, 1), (0, 0)), dot((1, 1), (1, 1))), (0, 2), "alternative strictly positive supporting price")
    a.true(F(1, 2)*(1+1) == 1 and 0 == dot((1, 1), (0, 0)), "direct budget bound upgrades without cheaper point")
    # Generic cheaper-bundle cost identity: the supporting-price gap is strict.
    a.equal((1-F(1, 10))*5+F(1, 10)*2, F(47, 10), "equal-cost better point mixed toward cheaper point")
    plans, resources = ((0, 0), (-1, 1), (-2, 3)), ((2, 0), (1, 1), (0, 3))
    result["discrete-plans"], result["discrete-utilities"] = plans, tuple(min(v) for v in resources)
    # At normalized p=(1-t,t), plan values are intercept+slope*t.
    values = tuple((r, c-r) for r, c in plans)
    differences = tuple(tuple(values[1][j]-values[k][j] for j in range(2)) for k in (0, 2))
    lower, upper = (-F(intercept, slope) for intercept, slope in differences)
    a.equal((lower, upper), (F(1, 2), F(1, 3)), "full normalized support inequalities incompatible")
    a.true(lower > upper, "no admissible price supports efficient discrete plan")
    weight = F(resources[0][0]-resources[0][1], (plans[2][1]-plans[0][1])-(plans[2][0]-plans[0][0]))
    mix = tuple((1-weight)*plans[0][j]+weight*plans[2][j] for j in range(2))
    result["convexified-weight"], result["convexified-bundle"] = weight, total(((2, 0), mix))
    a.true(not any(all(mix[j] <= v[j] for j in range(2)) for v in plans), "convexified plan absent from all original disposal branches")
    a.true(min(result["convexified-bundle"]) > max(result["discrete-utilities"]), "convexification changes attainable utility")

    p, income_pairs, alphas = (2, 1), ((8, 12), (12, 8)), (F(1, 4), F(3, 4))
    aggregates = tuple(total(tuple(demand(p, m, alpha) for m, alpha in zip(incomes, alphas))) for incomes in income_pairs)
    result["aggregate-before"], result["aggregate-after"] = aggregates
    a.equal(tuple(dot(p, z) for z in aggregates), (20, 20), "redistribution changes quantities within same total budget")
    a.equal(tuple(aggregates[1][j]-aggregates[0][j] for j in range(2)), (-1, 2), "heterogeneous-income slope effect")
    one_slice = lambda m, k: (m*m+1-(1-k)**2)/4
    a.equal(tuple(one_slice(m, 1-m) for m in (F(9, 20), F(1, 2), F(11, 20))), (F(1, 4),)*3, "nonaffine demand aggregates on just one slice")
    a.equal((one_slice(F(9, 20), F(9, 20)), one_slice(F(19, 40), F(17, 40))),
            (F(9, 40), F(179, 800)), "same off-slice total income no longer aggregates")
    for m in (F(3, 5), F(4, 5)):
        inferior = (1-m, -1+2*m)
        a.true(min(inferior) > 0 and sum(inferior) == m, "negative common slope consistent with bounded positive demand")
    floors = ((1, 0), (0, 1))
    slope = tuple(F(1, 2*q) for q in p)
    intercepts = tuple(tuple(s[j]-slope[j]*dot(p, s) for j in range(2)) for s in floors)
    before, after = tuple(tuple(subsistence(p, m, s) for m, s in zip(incomes, floors)) for incomes in income_pairs)
    result.update({"common-slope": slope, "common-intercepts": intercepts,
                   "subsistence-before": before, "subsistence-after": after, "subsistence-total": total(before)})
    a.equal((total(after), dot(p, total(after))), (total(before), 20), "subsistence redistribution invariance")
    a.equal((dot(p, slope), tuple(dot(p, z) for z in intercepts)), (1, (0, 0)), "affine budget identities")
    for price in ((2, 1), (3, 2)):
        individual = tuple(subsistence(price, m, s) for m, s in zip((8, 12), floors))
        a.equal(total(individual), subsistence(price, 20, total(floors)), "explicit representative family across two prices")
        a.equal(tuple(subsistence(price, dot(price, s), s) for s in floors), floors, "threshold budgets have unique feasible subsistence bundles")

    profile = ("ABCD", "ABDC", "BCAD", "BCDA", "CABD")
    result["majority-counts"] = tuple(pair_votes(profile, left, right) for left, right in ("AB", "AC", "AD", "BC", "BD", "CD"))
    a.true(all(2*pair_votes(profile, left, right) > len(profile) for left, right in ("AB", "BC", "CA")), "strict majority three-cycle")
    old, new = ("ABC",)*3+("BCA",)*2, ("ACB",)*3+("BAC",)*2
    result["borda-before"], result["borda-after"] = borda(old), borda(new)
    a.equal(tuple(v.index("A") < v.index("B") for v in old), tuple(v.index("A") < v.index("B") for v in new), "every voter keeps A/B information")
    a.true(borda(old)[0] < borda(old)[1] and borda(new)[0] > borda(new)[1], "Borda violates IIA")
    median, result["median-votes"] = median_contests(tuple(range(7)), (0, 2, 3, 5, 6))
    a.equal(median, 3, "median policy")
    a.true(all(row[0] >= 3 for row in result["median-votes"]), "cross-side tie leaves absolute winning majority")
    repeat_median, repeats = median_contests(tuple(range(7)), (0, 3, 3, 3, 6))
    a.true(repeat_median == 3 and all(row[0] >= 3 for row in repeats), "repeated median peaks belong to decisive coalitions")
    a.equal(sum(p > 3 for p in (0, 3, 3, 3, 6)), 1, "strict-above-median count would fail")

    orders = all_three_orders()
    a.equal(len(orders), 13, "all weak orders on three labeled alternatives")
    auxiliary_profiles = 0
    for left, right, third in permutations(range(3)):
        for sign in (-1, 0, 1):
            preserved = ((left,), (third,)) if sign == 1 else (((third,), (left,)) if sign == -1 else ((left, third),))
            inside = weak_order(((left,), (right,), (third,)))
            outside = weak_order(((right,),)+preserved)
            a.equal((compare(inside, left, right), compare(outside, left, right),
                     compare(inside, right, third), compare(outside, right, third), compare(outside, left, third)),
                    (1, -1, 1, 1, sign), "first propagation preserves outsider comparison including tie")
            preserved = ((third,), (right,)) if sign == 1 else (((right,), (third,)) if sign == -1 else ((third, right),))
            inside = weak_order(((third,), (left,), (right,)))
            outside = weak_order(preserved+((left,),))
            a.equal((compare(inside, left, right), compare(outside, left, right),
                     compare(inside, third, left), compare(outside, third, left), compare(outside, third, right)),
                    (1, -1, 1, 1, sign), "second propagation preserves outsider comparison including tie")
            auxiliary_profiles += 2
    for size in (3, 4):
        reached = {(0, 1)}
        while True:
            expanded = reached | {(a0, c) for a0, b0 in reached for c in range(size) if c not in (a0, b0)} | {(c, b0) for a0, b0 in reached for c in range(size) if c not in (a0, b0)}
            if expanded == reached:
                break
            reached = expanded
        a.equal(reached, set(permutations(range(size), 2)), "propagation reaches every orientation with no fourth-alternative requirement")
    partition = (weak_order(((0,), (1,), (2,))), weak_order(((2,), (0,), (1,))), weak_order(((1,), (2,), (0,))))
    a.equal(tuple(tuple(i for i, w in enumerate(partition) if compare(w, x, y) > 0) for x, y in ((0, 1), (2, 1), (0, 2))),
            ((0, 1), (1,), (0,)), "minimal-coalition exact split orientation")
    candidates = tuple(w for w in orders if compare(w, 0, 1) > 0)
    strict_branch = tuple(w for w in candidates if compare(w, 2, 1) > 0)
    reverse_branch = tuple(w for w in candidates if compare(w, 2, 1) <= 0)
    a.equal((len(candidates), len(strict_branch), len(reverse_branch), sum(w[1] == w[2] for w in reverse_branch)), (5, 3, 2, 1), "exhaustive social weak-order contraction branches")
    a.true(all(compare(w, 0, 2) > 0 for w in reverse_branch), "weak reverse branch including social tie forces strict conclusion")
    for x, y, z in permutations(range(3)):
        a.true(all(compare(w, x, z) > 0 for w in orders if compare(w, x, y) > 0 and compare(w, y, z) >= 0), "strict-plus-weak transitivity in every orientation")
    a.equal((weak_order(((0, 1, 2),)), weak_order(((0,), (1,), (2,)))), ((0, 0, 0), (0, 1, 2)), "strict-dictator convention permits refinement of dictator ties")

    result["utilitarian-allocation"] = social_optimum(12, (1, 2), "sum")
    result["weighted-allocation"] = social_optimum(12, (2, 2), "sum")
    result["maxmin-allocation"] = social_optimum(12, (1, 2), "minimum")
    for coefficients, key in (((1, 2), "utilitarian-allocation"), ((2, 2), "weighted-allocation")):
        c, chosen = vector(coefficients), result[key]
        a.equal((sum(chosen), chosen[0]*c[1]**2-chosen[1]*c[0]**2), (12, 0), "Cauchy-Schwarz global equality certificate")
    a.equal((12*(1+4), 12*(4+4)), (60, 96), "squared social objective maxima")
    x, y = result["maxmin-allocation"]
    a.equal((x, 4*y, x+y), (F(48, 5), F(48, 5), 12), "max-min resource lower bound attained")
    a.equal(social_optimum(12, (4, 2), "sum"), result["maxmin-allocation"], "individual rescaling changes unchanged-weight choice")
    a.equal(social_optimum(12, (F(1, 4)*4, 2), "sum"), result["utilitarian-allocation"], "inverse weight adjustment restores original ordering")
    menu = ((1, 4), (2, 2))
    result["origin-before"] = tuple(min(v) for v in menu)
    result["origin-after"] = tuple(min(v[0]+3, v[1]) for v in menu)
    a.equal((min(1, 2), min(1, 3)), (1, 1), "max-min may retain a Pareto-dominated tied option")
    return result, auxiliary_profiles, len(orders)


def check(root=None):
    require(root is None or isinstance(root, (str, Path)), "root path type")
    base = Path(root).resolve() if root is not None else Path(__file__).resolve().parents[1]
    a, doc = Audit(), Document()
    doc.feed((base/AUTHORS[0]).read_text(encoding="utf-8"))
    doc.close()
    a.equal((doc.stack, doc.marker), ([], None), "complete balanced manuscript")
    prompts = ["v13-c05-ex"+str(i) for i in range(1, 13)]
    a.equal((doc.exercises, doc.solutions), (prompts, prompts), "all twelve exact paired prompts/solutions")
    a.equal(doc.worked, ["v13-c05-case"+str(i) for i in range(1, 7)], "six original worked cases")
    a.true(all(key.startswith("v13-c05-") for key in doc.ids), "unique namespaced IDs")
    a.equal(doc.sources, SOURCES, "four scoped source links")
    a.equal({v for v in doc.links if not v.startswith("https://")}, {"v13-c%02d.html" % i for i in (1, 2, 3, 4, 6)}, "flat prerequisite/successor links")
    a.true(all(t in "".join(doc.text) for t in ("Teach-back.", "Delayed retention.", "Answers:", "Scoring, 16 points.")), "answered retention and explicit open rubric")
    results, profiles, order_count = mathematical_oracle(a)
    a.equal(set(doc.results), set(results), "all printed numerical anchors covered")
    for key, expected in results.items():
        a.equal(doc.results[key], expected, "printed "+key)

    for value in (True, 0.5, "1", float("nan"), float("inf"), 1j, 10**6+1, F(1, 10**9+1)):
        a.reject(number, value)
    a.reject(vector, ())
    a.reject(vector, (1, 2), 3)
    a.reject(total, ((1, 2), (1,)))
    for p, m, alpha in (((0, 1), 2, F(1, 2)), ((1, 1), -1, F(1, 2)), ((1, 1), 1, 0)):
        a.reject(demand, p, m, alpha)
    a.reject(subsistence, (2, 1), F(19, 10), (1, 0))
    a.reject(subsistence, (1, 0), 3, (0, 1))
    a.reject(ledger, (1, 1), ((1, 1), (1, 1)), (F(1, 4), F(1, 4)), (-1, 3), ((1, 1), (1, 1)))
    a.reject(ledger, (1, 1), ((1, 1),), (F(1, 2), F(1, 2)), (-1, 3), ((1, 1), (1, 1)))
    for value in ((), ("AAB",), ("ABC", "ABD"), ("ABC", 7)):
        a.reject(ballots, value)
    a.reject(pair_votes, ("ABC",), "A", "A")
    for value in (((0,), (0, 1)), ((0,), (2,)), ((False,), (1,)), ((), (0, 1))):
        a.reject(weak_order, value)
    a.reject(median_contests, (0, 1, 2), (0, 1))
    a.reject(median_contests, (0, 2, 1), (1,))
    a.reject(median_contests, (0, 1, 2), (3,))
    a.reject(social_optimum, 0, (1, 2), "sum")
    a.reject(social_optimum, 12, (0, 2), "minimum")
    a.reject(social_optimum, 12, (1, 2), "unproved")
    for raw in ('{"a":1,"a":2}', '{"a":NaN}'):
        a.reject(strict_json, raw)
    for raw in ("True", "1/0", "__import__('os')", "0.5", "[]"):
        a.reject(expression, raw)
    a.reject(Document().feed, '<p id="x"></p><p id="x"></p>')
    a.reject(Document().feed, '<li data-solution-for="x">outside disclosure</li>')

    source = strict_json((base/AUTHORS[2]).read_text(encoding="utf-8"))
    author = strict_json((base/AUTHORS[3]).read_text(encoding="utf-8"))
    peer = strict_json((base/RECORD).read_text(encoding="utf-8"))
    a.equal({s["id"]: s["url"] for s in source["proposals"]}, SOURCES, "source-record mapping")
    a.equal([s["inspection"].get("actual_inspector") for s in source["proposals"][:3]], ["ito_author"]*3, "actual primary reader attribution")
    a.equal([len(s["inspection"]["actual_image_physical_pages"]) for s in source["proposals"][:3]], [4, 7, 0], "honest scoped primary images")
    a.equal(source["proposals"][3]["inspection"]["mode"], "prior_scope_reuse", "historical welfare transcript scope")
    a.equal(set(peer["exercise_audit"]), set(prompts), "peer judgment for every exact answer")
    a.equal(set(peer["proof_audit"]), {"v13-c05-"+s for s in ("first", "separation", "second", "failures", "aggregation", "arrow", "social")}, "peer every proof route")
    a.equal(peer["open_findings"], [], "no unresolved material findings")
    for title, bindings, paths in (("author", author["bindings"], AUTHORS[:3]), ("peer", peer["bindings"], AUTHORS+(SELF,))):
        a.equal((len(bindings), {v["path"] for v in bindings}), (len(paths), set(paths)), title+" exact binding scope")
        for item in bindings:
            raw = (base/item["path"]).read_bytes()
            a.equal((len(raw), sha256(raw).hexdigest()), (item["bytes"], item["sha256"]), title+" binding "+item["path"])
    summary = {"chapter": "v13-c05", "status": "passed", "comparisons": a.comparisons,
               "domain_rejections": a.rejections, "intervention_groups": 13,
               "worked_cases": 6, "solved_exercises": 12, "visible_result_markers": len(results),
               "oriented_auxiliary_profiles": profiles, "three_alternative_weak_orders": order_count,
               "source_scopes": 4, "author_execution_used_as_oracle": False}
    require(strict_json(json.dumps(summary, allow_nan=False)) == summary, "strict JSON-safe summary")
    return summary


if __name__ == "__main__":
    check()
