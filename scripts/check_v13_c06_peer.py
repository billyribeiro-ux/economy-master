#!/usr/bin/env python3
"""Quiet independent C06 peer oracle; only the six bound canonical files.

Exact support intervals, conditional state ledgers and linear dual certificates
are derived from the original games. No author module, output or blueprint is
an oracle. Finite calculations supplement the separately reviewed proofs.
"""
import ast
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from itertools import product
import json
from pathlib import Path


AUTHORS = ("content/chapters/v13-c06.html", "scripts/check_v13_c06.py",
           "content/reviews/v13-c06-sources.json", "content/reviews/v13-c06-author.json")
SELF, RECORD = "scripts/check_v13_c06_peer.py", "content/reviews/v13-c06-peer.json"
SOURCES = {
    "v13-c06-yildiz-games2022": "https://ocw.mit.edu/courses/14.126-game-theory-spring-2024/mit14_126_s24_yildiz-lecture-notes.pdf",
    "v13-c06-manea-noncoop2017": "https://ocw.mit.edu/courses/14-126-game-theory-spring-2016/a4d0a3949ab29c2a2f55442a9723d205_MIT14_126S16_noncoop.pdf",
    "v13-c06-roughgarden2013-equilibria": "https://www.timroughgarden.org/f13/l/l13.pdf",
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def exact(value):
    require(type(value) in (int, F), "bounded exact scalar")
    v = F(value)
    require(abs(v) <= 10**6 and v.denominator <= 10**9, "rational bound")
    return v


def vector(values, length=None):
    require(type(values) in (tuple, list) and 1 <= len(values) <= 9, "bounded nonempty vector")
    require(length is None or len(values) == length, "vector dimension")
    return tuple(exact(v) for v in values)


def law(values, length=None):
    p = vector(values, length)
    require(min(p) >= 0 and sum(p) == 1, "probability simplex")
    return p


def game(rows):
    require(type(rows) in (tuple, list) and 1 <= len(rows) <= 3, "row actions")
    require(type(rows[0]) in (tuple, list) and 1 <= len(rows[0]) <= 3, "column actions")
    width = len(rows[0])
    require(all(type(row) in (tuple, list) and len(row) == width for row in rows), "rectangular game")
    return tuple(tuple(vector(pair, 2) for pair in row) for row in rows)


def joint(p, q):
    return tuple(x*y for x in law(p) for y in law(q))


def utility(g, distribution):
    n, m = len(g), len(g[0])
    mu = law(distribution, n*m)
    return tuple(sum((mu[r*m+c]*g[r][c][i] for r, c in product(range(n), range(m))), F(0)) for i in (0, 1))


def action_values(g, opponent, player):
    require(type(player) is int and player in (0, 1), "player index")
    n, m = len(g), len(g[0])
    if player == 0:
        q = law(opponent, m)
        return tuple(sum(q[c]*g[r][c][0] for c in range(m)) for r in range(n))
    p = law(opponent, n)
    return tuple(sum(p[r]*g[r][c][1] for r in range(n)) for c in range(m))


def cut(interval, constant, slope, sign):
    """Intersect a probability interval with sign*(constant+slope*x)>=0 or =0."""
    if interval is None:
        return None
    a, b = exact(constant), exact(slope)
    require(type(sign) is int and sign in (-1, 0, 1), "inequality direction")
    lo, hi, lc, hc = interval
    if b == 0:
        return interval if (a == 0 if sign == 0 else sign*a >= 0) else None
    threshold = -a/b
    if sign == 0:
        inside = (lo < threshold or (lc and lo == threshold)) and (threshold < hi or (hc and threshold == hi))
        return (threshold, threshold, True, True) if inside else None
    if sign*b > 0 and threshold > lo:
        lo, lc = threshold, True
    elif sign*b < 0 and threshold < hi:
        hi, hc = threshold, True
    return (lo, hi, lc, hc) if lo < hi or (lo == hi and lc and hc) else None


def supports(g):
    """Solve all nine 2x2 support cells, preserving open ends and continua."""
    require((len(g), len(g[0])) == (2, 2), "binary support scope")
    row = (g[0][1][0]-g[1][1][0], g[0][0][0]-g[1][0][0]-g[0][1][0]+g[1][1][0])
    col = (g[1][0][1]-g[1][1][1], g[0][0][1]-g[0][1][1]-g[1][0][1]+g[1][1][1])
    cells = {0: (F(0), F(0), True, True), 1: (F(1), F(1), True, True),
             2: (F(0), F(1), False, False)}
    direction = {0: -1, 1: 1, 2: 0}
    result = {}
    for ps, qs in product(range(3), repeat=2):
        p = cut(cells[ps], *col, direction[qs])
        q = cut(cells[qs], *row, direction[ps])
        if p is not None and q is not None:
            result[(ps, qs)] = (p, q)
    return result


def point_equilibria(g):
    regions = supports(g)
    require(all(p[0] == p[1] and q[0] == q[1] for p, q in regions.values()), "not a finite point correspondence")
    return tuple(sorted((p[0], q[0]) for p, q in regions.values()))


def floors(limit, tremble, index):
    s, t = law(limit), law(tremble)
    require(len(s) == len(t) and min(t) > 0, "matching fully mixed tremble")
    require(type(index) is int and index > 0, "positive sequence index")
    return tuple(v if s[j] == 0 else min(v/2, F(1, index)) for j, v in enumerate(t))


def constrained_vertices(lower):
    d = vector(lower)
    require(min(d) > 0 and sum(d) < 1, "positive feasible tremble floors")
    return tuple(tuple(v+(1-sum(d) if j == k else 0) for j, v in enumerate(d)) for k in range(len(d)))


def recommendation_gains(g, distribution):
    n, m = len(g), len(g[0])
    mu = law(distribution, n*m)
    out = {}
    for who, count in enumerate((n, m)):
        for rec, dev in product(range(count), repeat=2):
            if rec == dev:
                continue
            out[(who, rec, dev)] = sum((mu[r*m+c]*(g[r][c][who]-(g[dev][c][who] if who == 0 else g[r][dev][who]))
                                      for r, c in product(range(n), range(m)) if (r if who == 0 else c) == rec), F(0))
    return out


def change_value(g, distribution, player, rule):
    n, m = len(g), len(g[0])
    mu = law(distribution, n*m)
    require(type(player) is int and player in (0, 1), "deviating player")
    count = (n, m)[player]
    require(type(rule) in (tuple, list) and len(rule) == count, "deviation rule dimension")
    require(all(type(x) is int and 0 <= x < count for x in rule), "deviation actions")
    return sum((mu[r*m+c]*(g[rule[r]][c][0] if player == 0 else g[r][rule[c]][1])
                for r, c in product(range(n), range(m))), F(0))


def conditional(g, distribution, player, recommendation):
    n, m = len(g), len(g[0])
    mu = law(distribution, n*m)
    require(type(player) is int and player in (0, 1), "conditional player")
    count = (n, m)[player]
    require(type(recommendation) is int and 0 <= recommendation < count, "recommendation index")
    states = [(r, c) for r, c in product(range(n), range(m)) if (r if player == 0 else c) == recommendation]
    mass = sum(mu[r*m+c] for r, c in states)
    require(mass > 0, "positive recommendation needed for conditioning")
    return tuple(sum(mu[r*m+c]*(g[a][c][0] if player == 0 else g[r][a][1]) for r, c in states)/mass for a in range(count))


def entry(prior, plans):
    pi = law(prior, 4)
    require(type(plans) in (tuple, list) and len(plans) == 2, "two type plans")
    s = tuple(vector(v, 2) for v in plans)
    require(all(0 <= v <= 1 for z in s for v in z), "entry probabilities")
    marginal, belief, gain, payoff = [], [], [], []
    for i in (0, 1):
        masses, beliefs, gains = [], [], []
        for t in (0, 1):
            cells = (pi[2*t], pi[2*t+1]) if i == 0 else (pi[t], pi[2+t])
            mass = sum(cells)
            require(mass > 0, "positive own-type marginal")
            b = tuple(v/mass for v in cells)
            masses.append(mass); beliefs.append(b)
            gains.append(4-(1 if t == 0 else 3)-4*sum(b[z]*s[1-i][z] for z in (0, 1)))
        marginal.append(tuple(masses)); belief.append(tuple(beliefs)); gain.append(tuple(gains))
        payoff.append(sum(pi[2*r+c]*s[i][(r, c)[i]]*(4-(1 if (r, c)[i] == 0 else 3)-4*s[1-i][(r, c)[1-i]])
                          for r, c in product(range(2), repeat=2)))
    optimal = all((g <= 0 if p == 0 else g >= 0 if p == 1 else g == 0)
                  for pvec, gvec in zip(s, gain) for p, g in zip(pvec, gvec))
    return tuple(marginal), tuple(belief), tuple(gain), tuple(payoff), optimal


def entry_response(opponent):
    q = exact(opponent)
    require(0 <= q <= 1, "opponent entry probability")
    intervals = tuple((F(0), F(0)) if 4-c-4*q < 0 else (F(1), F(1)) if 4-c-4*q > 0 else (F(0), F(1)) for c in (1, 3))
    return tuple(sum(v[j] for v in intervals)/2 for j in (0, 1)), intervals


def recover_plan(own, opponent):
    q = exact(own)
    (lo, hi), intervals = entry_response(opponent)
    require(lo <= q <= hi, "aggregate is a best reply")
    v = [z[0] for z in intervals]
    free = [j for j, z in enumerate(intervals) if z[0] != z[1]]
    require(len(free) <= 1, "one indifferent type in this entry model")
    if free:
        v[free[0]] = 2*q-sum(v)
    require(sum(v)/2 == q and all(0 <= x <= 1 for x in v), "identified equilibrium type plan")
    return tuple(v)


def strict_json(text):
    def pairs(items):
        d = {}
        for key, value in items:
            require(key not in d, "duplicate JSON key")
            d[key] = value
        return d
    def bad(value):
        raise ValueError("nonfinite JSON constant: "+value)
    result = json.loads(text, object_pairs_hook=pairs, parse_constant=bad)
    json.dumps(result, allow_nan=False)
    return result


def expression(text):
    require(type(text) is str and len(text) <= 2000, "marker text bound")
    tree = ast.parse(text.strip().replace("−", "-"), mode="eval")
    require(sum(1 for _ in ast.walk(tree)) <= 300, "marker node bound")
    def visit(node):
        if isinstance(node, ast.Constant) and type(node.value) is int:
            return exact(node.value)
        if isinstance(node, (ast.Tuple, ast.List)):
            require(1 <= len(node.elts) <= 9, "marker tuple bound")
            return tuple(visit(v) for v in node.elts)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            v = visit(node.operand)
            require(type(v) is F, "scalar sign")
            return -v if isinstance(node.op, ast.USub) else v
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            v, w = visit(node.left), visit(node.right)
            require(type(v) is F and type(w) is F and w != 0, "scalar division")
            return exact(v/w)
        raise ValueError("unsupported numeric expression")
    return visit(tree.body)


class Document(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids, self.inputs, self.results, self.sources = {}, {}, {}, {}
        self.worked, self.exercises, self.solutions, self.links = [], [], [], []
        self.stack, self.marker = [], None
        self.exdepth = self.soldepth = 0

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
            require(tag == "li" and self.soldepth, "solution disclosure")
            self.solutions.append(a["data-solution-for"])
        self.exdepth += int(ex); self.soldepth += int(sol)
        if tag not in ("br", "hr", "img", "input", "meta", "link"):
            self.stack.append((tag, ex, sol))
        markers = [k for k in ("data-input", "data-calc") if k in a]
        if markers:
            require(len(markers) == 1 and self.marker is None and tag == "span", "single marker")
            target = self.inputs if markers[0] == "data-input" else self.results
            key = a[markers[0]]
            require(key not in target, "unique marker")
            self.marker = (target, key, [])
        if tag == "a":
            self.links.append(a.get("href", ""))
            if "data-source" in a:
                require(a["data-source"] not in self.sources, "unique citation")
                self.sources[a["data-source"]] = a.get("href")

    def handle_data(self, text):
        if self.marker is not None:
            self.marker[2].append(text)

    def handle_endtag(self, tag):
        require(self.stack and self.stack[-1][0] == tag, "balanced HTML")
        _, ex, sol = self.stack.pop()
        self.exdepth -= int(ex); self.soldepth -= int(sol)
        if tag == "span" and self.marker is not None:
            target, key, text = self.marker
            target[key] = expression("".join(text)); self.marker = None


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


def derive(a):
    inputs = {
        "zero-sum-matrix": ((3, -1), (-2, 2)), "zero-sum-transfer": 5,
        "weak-game": (((2, 2), (1, 2)), ((2, 1), (0, 0))), "uniform-tremble": F(1, 10),
        "coordination-game": (((4, 4), (0, 2)), ((2, 0), (3, 3))),
        "entry-costs": (1, 3), "entry-parameters": (4, 4),
        "entry-correlated-prior": (F(3, 8), F(1, 8), F(1, 8), F(3, 8)),
        "recommendation-game": (((6, 6), (1, 8)), ((8, 1), (0, 0))),
        "cyclic-game": ((1, -1, 2), (2, 1, -1), (-1, 2, 1)),
        "asymmetric-row-floor": F(1, 10), "asymmetric-column-floor": F(1, 5),
        "perfection-limit": (F(1, 2), F(1, 2), 0), "perfection-tremble": (F(9, 20), F(9, 20), F(1, 10)),
        "mixed-dominance-matrix": ((2, 0, 2), (0, 2, 2), (1, 1, 1)),
        "coordination-transfer": (5, 5), "entry-anticorrelated-prior": (F(1, 8), F(3, 8), F(3, 8), F(1, 8)),
        "recommendation-transfer": (5, 5),
    }
    result = {}
    for label, upper in (("zero-sum", 3), ("zero-sum-transfer", 5)):
        matrix = ((upper, -1), (-2, 2))
        g = game(tuple(tuple((x, -x) for x in row) for row in matrix))
        ne = point_equilibria(g)
        a.equal(len(ne), 1, "all nine support cells give unique zero-sum equilibrium")
        p, q = ne[0]; mu = joint((p, 1-p), (q, 1-q)); value = utility(g, mu)[0]
        result[label+"-mix"], result[label+"-value"] = (p, q), value
        a.equal(action_values(g, (q, 1-q), 0), (value, value), "row global saddle guarantee")
        a.equal(action_values(g, (p, 1-p), 1), (-value, -value), "column global saddle guarantee")
        altered = game(tuple(tuple((3*x+7, 2*y-5) for x, y in row) for row in g))
        a.equal(supports(altered), supports(g), "positive affine own utilities preserve complete correspondence")

    weak = game(inputs["weak-game"])
    regions = supports(weak)
    a.equal(set(regions), {(0, 1), (1, 0), (1, 1), (1, 2), (2, 1)}, "complete weak-game continuum support cells")
    a.equal(regions[(2, 1)], ((0, 1, False, False), (1, 1, True, True)), "entire open horizontal edge plus endpoints")
    a.equal(regions[(1, 2)], ((1, 1, True, True), (0, 1, False, False)), "entire open vertical edge plus endpoints")
    for label, row_floor, col_floor in (("weak-tremble", F(1, 10), F(1, 10)), ("asymmetric-tremble", F(1, 10), F(1, 5))):
        p, q = 1-row_floor, 1-col_floor
        result[label+"-profile"] = (p, q)
        result[label+"-payoffs"] = utility(weak, joint((p, 1-p), (q, 1-q)))
        for player, own, opp, lower in ((0, p, q, row_floor), (1, q, p, col_floor)):
            pay = action_values(weak, (opp, 1-opp), player)
            vertices = constrained_vertices((lower, lower))
            feasible_values = tuple(sum(x*y for x, y in zip(v, pay)) for v in vertices)
            a.true(pay[0] > pay[1], "positive opposing tremble makes first action strictly better")
            a.equal(result[label+"-payoffs"][player], max(feasible_values), "constrained vertex global optimum")
            a.true(own < 1 and result[label+"-payoffs"][player] < max(pay), "perturbed profile need not be unconstrained Nash")
    sigma, tau = inputs["perfection-limit"], inputs["perfection-tremble"]
    d = floors(sigma, tau, 10)
    result["perfection-floor-example"] = d
    result["perfection-residual-example"] = tuple(t-v for t, v in zip(tau, d))
    a.equal((sum(d), sum(result["perfection-residual-example"])), (F(3, 10), F(7, 10)), "floor/residual mass accounting")
    for k in (2, 10, 100):
        t = ((1-F(1, k))/2, (1-F(1, k))/2, F(1, k))
        d = floors(sigma, t, k)
        a.true(min(d) > 0 and max(d) <= F(1, k) and sum(d) < 1, "explicit vanishing feasible-floor sequence")
        a.equal(t[2]-d[2], 0, "outside-support action forced exactly at its floor")
    dominance = inputs["mixed-dominance-matrix"]
    dominating = tuple(F(dominance[0][j]+dominance[1][j], 2) for j in range(3))
    result["mixed-dominance-vector"] = dominating
    a.true(all(any(row[j] < dominance[2][j] for j in range(3)) for row in dominance[:2]), "neither pure alternative weakly dominates")
    dg = game(tuple(tuple((v, 0) for v in row) for row in dominance))
    a.equal(action_values(dg, (F(1, 2), F(1, 2), 0), 0), (1, 1, 1), "dominated-action profile is still Nash on restricted opponent support")
    a.equal(tuple(dominating[j]-dominance[2][j] for j in range(3)), (0, 0, 1), "gain equals strictly positive Z probability under every full-support tremble")
    a.equal(action_values(dg, (0, 0, 1), 1), (0, 0, 0), "opponent indifferent at the nonperfect Nash profile")

    for label, last in (("coordination", 3), ("coordination-transfer", 5)):
        g = game((((4, 4), (0, 2)), ((2, 0), (last, last))))
        ne = point_equilibria(g)
        a.equal(tuple((p, q) for p, q in ne if p in (0, 1)), ((0, 0), (1, 1)), "both pure coordination equilibria")
        interior = tuple((p, q) for p, q in ne if 0 < p < 1)
        a.equal(len(interior), 1, "one remaining fully mixed support")
        p, q = interior[0]
        result[label+"-mix"] = (p, q)
        result[label+("-mixed-payoffs" if label == "coordination" else "-payoffs")] = utility(g, joint((p, 1-p), (q, 1-q)))
        for own, opponent in ((0, F(1, 100)), (1, F(99, 100))):
            pay = action_values(g, (opponent, 1-opponent), 0)
            a.true((pay[0] > pay[1]) == bool(own), "strict pure choice survives small full-support noise")

    thresholds = {F(4-c, 4) for c in inputs["entry-costs"]}
    candidates = sorted(thresholds | {F(0), F(1, 2), F(1)})
    bne, plans, values = [], {}, []
    for p, q in product(candidates, repeat=2):
        low, high = entry_response(q)[0]; left, right = entry_response(p)[0]
        if low <= p <= high and left <= q <= right:
            bne.append((p, q))
            s = (recover_plan(p, q), recover_plan(q, p))
            data = entry((F(1, 4),)*4, s)
            a.true(data[-1], "each recovered type plan satisfies every interim best reply")
            a.equal(data[3], tuple(sum(m*g*x for m, g, x in zip(data[0][i], data[2][i], s[i])) for i in (0, 1)), "joint-state and interim payoff accounting agree")
            plans[p], plans[q] = s
            values.append(data[3])
    result["entry-equilibria"], result["entry-type-menu"], result["entry-payoffs"] = tuple(bne), tuple(plans[q] for q in sorted(plans)), tuple(values)
    a.equal(len(bne), 5, "complete breakpoint/constant-response candidate set")
    a.equal(tuple(entry_response(q)[0] for q in (F(1, 8), F(1, 4), F(1, 2), F(3, 4), F(7, 8))),
            ((1, 1), (F(1, 2), 1), (F(1, 2), F(1, 2)), (0, F(1, 2)), (0, 0)), "all five response regions including boundary intervals")
    low_only = ((1, 0), (1, 0))
    for label in ("entry-correlated", "entry-anticorrelated"):
        data = entry(inputs[label+"-prior"], low_only)
        result[label+"-conditionals"] = tuple(b[0] for b in data[1][0])
        result[label+"-gains"], result[label+"-payoffs"] = data[2][0], data[3]
        a.equal(data[0], ((F(1, 2), F(1, 2)),)*2, "unchanged own-type marginals")
        a.true(data[-1], "low-only entry optimal under changed conditional law")
    independent = entry((F(1, 4),)*4, low_only)
    a.equal(independent[2], ((1, -1), (1, -1)), "marginal substitution would change conditional gains")
    sparse = entry((0, F(1, 2), F(1, 2), 0), low_only)
    a.equal((sparse[2], sparse[3], sparse[-1]), (((3, -3), (3, -3)), (F(3, 2), F(3, 2)), True), "joint zero cells allowed with positive own marginals")
    a.equal(F(0)*(-3), 0, "null-type ex ante gain cannot impose interim optimality")

    recommend = game(inputs["recommendation-game"])
    ne = point_equilibria(recommend)
    a.equal(len(ne), 3, "complete recommendation-game Nash supports")
    p, q = next((p, q) for p, q in ne if 0 < p < 1)
    result["recommendation-nash-probability"] = 1-p
    result["recommendation-nash-payoffs"] = utility(recommend, joint((p, 1-p), (q, 1-q)))
    for label, yy in (("recommendation", 6), ("recommendation-transfer", 5)):
        g = game((((yy, yy), (1, 8)), ((8, 1), (0, 0))))
        k = F(8-yy); alpha = 1/(1+2*k); mu = (alpha, k*alpha, k*alpha, F(0))
        gains = recommendation_gains(g, mu)
        a.true(min(gains.values()) >= 0, "candidate obeys all four updated constraints")
        welfare = sum(utility(g, mu)); weight = F(2*yy-9)/(1+2*k)
        # A nonnegative linear combination of CE slacks and AA probability is
        # exactly the objective gap, for EVERY joint law (coefficient identity).
        basis = tuple(tuple(F(int(i == j)) for j in range(4)) for i in range(4))
        rows = tuple(tuple(recommendation_gains(g, e)[label0] for e in basis) for label0 in ((0, 0, 1), (1, 0, 1)))
        gap = tuple(welfare-sum(g[r][c]) for r, c in product(range(2), repeat=2))
        certificate = tuple(weight*(rows[0][j]+rows[1][j])+(welfare if j == 3 else 0) for j in range(4))
        a.equal(gap, certificate, "global CE objective dual certificate for all probability vectors")
        a.true(weight > 0 and welfare > 0 and 1+2*k > 0, "zero gap forces both binding slacks and zero AA mass")
        a.equal((mu[1]-k*mu[0], mu[2]-k*mu[0], sum(mu)), (0, 0, 1), "unique equality solution from normalization")
        result[label+"-optimum"] = mu
        result[label+("-optimal-payoffs" if label == "recommendation" else "-payoffs")] = utility(g, mu)
        result[label+("-optimal-welfare" if label == "recommendation" else "-welfare")] = welfare
        for i in (0, 1):
            a.equal(max(change_value(g, mu, i, rule) for rule in product(range(2), repeat=2)), utility(g, mu)[i], "all four private contingent rules obey")
    optimum = result["recommendation-optimum"]
    result["recommendation-private-y"] = conditional(recommend, optimum, 0, 0)
    pay = conditional(recommend, optimum, 0, 1)
    result["recommendation-private-a"] = (pay[1], pay[0])
    marginal_y = optimum[0]+optimum[1]
    product_mu = joint((marginal_y, 1-marginal_y), (marginal_y, 1-marginal_y))
    result["recommendation-independent"] = product_mu
    result["recommendation-independent-slack"] = recommendation_gains(recommend, product_mu)[(0, 0, 1)]
    a.true(result["recommendation-independent-slack"] < 0, "same marginals do not preserve private obedience")
    a.true(optimum[0] > 0 and recommend[1][0][0] > recommend[0][0][0], "public YY realization has a profitable deviation")
    nash_values = tuple(sum(utility(recommend, joint((p, 1-p), (q, 1-q)))) for p, q in ne)
    a.true(sum(utility(recommend, optimum)) > max(nash_values), "CE welfare exceeds entire Nash-distribution convex hull")
    a.true(4*8+1 > 5*result["recommendation-optimal-payoffs"][0], "positive own rescaling preserves incentives but can change social optimizer")
    for p, q in ne:
        mu = joint((p, 1-p), (q, 1-q))
        a.true(min(recommendation_gains(recommend, mu).values()) >= 0, "Nash product is CE including null recommendations")
    a.true(min(recommendation_gains(recommend, (0, F(1, 3), F(2, 3), 0)).values()) >= 0, "mixture of Nash products remains CE")
    for mu in (optimum, product_mu):
        ce = recommendation_gains(recommend, mu); following = utility(recommend, mu)
        a.equal(tuple(following[i]-change_value(recommend, mu, i, (b, b)) for i, b in product(range(2), repeat=2)),
                tuple(ce[(i, 1-b, b)] for i, b in product(range(2), repeat=2)), "binary CCE comparisons are exactly CE comparisons")

    matrix = inputs["cyclic-game"]
    g = game(tuple(tuple((matrix[r][c], matrix[c][r]) for c in range(3)) for r in range(3)))
    nu, diagonal = (F(1, 9),)*9, tuple(F(int(r == c), 3) for r, c in product(range(3), repeat=2))
    cyclic_rule = (1, 2, 0)
    result["cyclic-diagonal-payoffs"] = utility(g, diagonal)
    result["cyclic-fixed-deviation"] = change_value(g, diagonal, 0, (0, 0, 0))
    result["cyclic-contingent-deviation"] = change_value(g, diagonal, 0, cyclic_rule)
    result["cyclic-obedience-slack"] = recommendation_gains(g, diagonal)[(0, 0, 1)]
    result["cyclic-independent-payoff"] = utility(g, nu)[0]
    for i in (0, 1):
        rules = tuple(product(range(3), repeat=3))
        intercepts = tuple(change_value(g, nu, i, rule) for rule in rules)
        endpoints = tuple(change_value(g, diagonal, i, rule) for rule in rules)
        a.equal(set(intercepts), {F(2, 3)}, "every one of 27 rules has same independent intercept")
        a.equal((max(endpoints), endpoints.count(max(endpoints))), (2, 1), "unique cyclic rule has largest diagonal endpoint")
        a.equal(tuple(change_value(g, diagonal, i, (b,)*3) for b in range(3)), (F(2, 3),)*3, "each fixed action has unchanged endpoint")
    a.equal((utility(g, nu), utility(g, diagonal)), ((F(2, 3),)*2, (1, 1)), "full-family following payoff coefficients")
    a.equal(set(recommendation_gains(g, nu).values()), {F(0)}, "independent uniform is CE")
    a.equal(tuple(recommendation_gains(g, diagonal)[(i, a0, (a0+1) % 3)] for i, a0 in product(range(2), range(3))), (F(-1, 3),)*6, "every cyclic CE slack is -lambda/3 throughout the family")
    halfway = tuple((x+y)/2 for x, y in zip(nu, diagonal))
    result["cyclic-transfer-payoffs"] = (utility(g, halfway)[0], change_value(g, halfway, 0, (0,)*3), change_value(g, halfway, 0, cyclic_rule))
    result["cyclic-transfer-slack"] = recommendation_gains(g, halfway)[(0, 0, 1)]
    following_coefficients = (utility(g, nu)[0], utility(g, diagonal)[0]-utility(g, nu)[0])
    deviation_coefficients = (change_value(g, nu, 0, cyclic_rule),
                              change_value(g, diagonal, 0, cyclic_rule)-change_value(g, nu, 0, cyclic_rule))
    a.equal(tuple(x-y for x, y in zip(deviation_coefficients, following_coefficients)), (0, 1), "conditional gain polynomial is exactly lambda")
    return inputs, result


def check(root=None):
    require(root is None or isinstance(root, (str, Path)), "root path type")
    base = Path(root).resolve() if root is not None else Path(__file__).resolve().parents[1]
    a, doc = Audit(), Document()
    doc.feed((base/AUTHORS[0]).read_text(encoding="utf-8")); doc.close()
    a.equal((doc.stack, doc.marker), ([], None), "balanced complete chapter")
    exercises = ["v13-c06-ex"+str(i) for i in range(1, 13)]
    a.equal((doc.exercises, doc.solutions), (exercises, exercises), "all twelve paired prompts/solutions")
    a.equal(doc.worked, ["v13-c06-case"+str(i) for i in range(1, 7)], "six worked cases")
    a.true(all(k.startswith("v13-c06-") for k in doc.ids), "unique namespaced IDs")
    a.true({"v13-c06-teach-answer", "v13-c06-retention-answer"} <= set(doc.ids), "answered teaching and delayed retention")
    a.equal(doc.sources, SOURCES, "exact three primary URLs")
    a.equal({x for x in doc.links if not x.startswith("https://")}, {"v13-c03.html", "v13-c04.html", "v13-c05.html", "v05-c07.html", "v13-c07.html"}, "flat prerequisite and successor routes")
    inputs, results = derive(a)
    a.equal(doc.inputs, inputs, "every visible original primitive")
    a.equal(set(doc.results), set(results), "all printed results covered")
    for key, value in results.items():
        a.equal(doc.results[key], value, "printed "+key)
    for value in (True, "1", 0.5, float("nan"), float("inf"), 1j, 10**6+1, F(1, 10**9+1)):
        a.reject(exact, value)
    a.reject(vector, ())
    a.reject(vector, (1, 2), 3)
    a.reject(law, (-1, 2))
    a.reject(law, (F(1, 2), F(1, 3)))
    for g in ((), (((1, 2),), ((1, 2), (3, 4))), (((1,),),)):
        a.reject(game, g)
    weak = game(inputs["weak-game"])
    a.reject(point_equilibria, weak)
    a.reject(supports, game((((1, 2),),)))
    a.reject(cut, (0, 1, True, True), 0, 1, True)
    for d in ((0, F(1, 10)), (F(1, 2), F(1, 2)), (F(3, 4), F(3, 4))):
        a.reject(constrained_vertices, d)
    a.reject(floors, (1, 0), (1, 0), 10)
    a.reject(floors, (1, 0), (F(1, 2), F(1, 2)), 0)
    a.reject(floors, (1, 0), (1,), 10)
    a.reject(entry, (1, 0, 0, 0), ((1, 0), (1, 0)))
    a.reject(entry, (F(1, 4),)*4, ((2, 0), (1, 0)))
    a.reject(entry, (F(1, 4),)*4, ((1, 0),))
    a.reject(entry_response, F(11, 10))
    a.reject(recover_plan, F(1, 4), F(1, 2))
    a.reject(conditional, weak, (1, 0, 0, 0), 0, 1)
    a.reject(conditional, weak, (1, 0, 0, 0), True, 0)
    a.reject(change_value, weak, (F(1, 4),)*4, 0, (0, 2))
    a.reject(change_value, weak, (F(1, 4),)*4, 0, (0,))
    a.reject(utility, weak, (1, 0))
    for raw in ('{"x":1,"x":2}', '{"x":NaN}'):
        a.reject(strict_json, raw)
    for raw in ("True", "1/0", "__import__('os')", "0.5", "[]"):
        a.reject(expression, raw)
    a.reject(Document().feed, '<p id="x"></p><p id="x"></p>')
    a.reject(Document().feed, '<li data-solution-for="x">outside disclosure</li>')
    source = strict_json((base/AUTHORS[2]).read_text(encoding="utf-8"))
    author = strict_json((base/AUTHORS[3]).read_text(encoding="utf-8"))
    peer = strict_json((base/RECORD).read_text(encoding="utf-8"))
    a.equal({v["id"]: v["url"] for v in source["sources"]}, SOURCES, "source-record scope")
    a.equal({v["actual_inspector"] for v in source["sources"]}, {"c05_review"}, "actual primary inspection attribution")
    a.equal(sum(len(v["images_inspected"]) for v in source["sources"]), 6, "six specifically inspected source images")
    a.equal(set(peer["exercise_audit"]), set(exercises), "peer every exact answer judgment")
    a.equal(set(peer["proof_audit"]), {"nash", "perfection", "bayesian", "correlated", "coarse", "support_completeness"}, "peer full theorem and completeness scope")
    a.equal(peer["open_findings"], [], "no unresolved finding")
    for title, bindings, paths in (("author", author["payload_bindings"], AUTHORS[:3]), ("peer", peer["bindings"], AUTHORS+(SELF,))):
        a.equal((len(bindings), {v["path"] for v in bindings}), (len(paths), set(paths)), title+" exact bindings")
        for item in bindings:
            raw = (base/item["path"]).read_bytes()
            a.equal((len(raw), sha256(raw).hexdigest()), (item["bytes"], item["sha256"]), title+" binding "+item["path"])
    result = {"chapter": "v13-c06", "status": "passed", "comparisons": a.comparisons,
              "domain_rejections": a.rejections, "intervention_groups": 12,
              "worked_cases": 6, "solved_exercises": 12, "input_markers": len(inputs), "result_markers": len(results),
              "binary_support_cells_per_game": 9, "baseline_bayesian_equilibria": 5,
              "ternary_contingent_rules_per_player": 27, "source_scopes": 3,
              "author_execution_used_as_oracle": False}
    require(strict_json(json.dumps(result, allow_nan=False)) == result, "strict JSON-safe summary")
    return result


if __name__ == "__main__":
    check()
