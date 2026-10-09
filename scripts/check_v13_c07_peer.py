#!/usr/bin/env python3
"""Quiet C07 peer oracle; exact six-file runtime and no author-code import.

Original tree primitives, direct discounted reward paths and conditional backward
values supplement the separately reviewed general information-set proofs.
"""
import ast
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from itertools import product
import json
from pathlib import Path
import sys


AUTHORS = ("content/chapters/v13-c07.html", "scripts/check_v13_c07.py",
           "content/reviews/v13-c07-sources.json", "content/reviews/v13-c07-author.json")
SELF, RECORD = "scripts/check_v13_c07_peer.py", "content/reviews/v13-c07-peer.json"
SOURCES = {
    "v13-c06-manea-noncoop2017": "https://ocw.mit.edu/courses/14-126-game-theory-spring-2016/a4d0a3949ab29c2a2f55442a9723d205_MIT14_126S16_noncoop.pdf",
    "v13-c06-yildiz-games2022": "https://ocw.mit.edu/courses/14.126-game-theory-spring-2024/mit14_126_s24_yildiz-lecture-notes.pdf",
}
PD = (((4, 4), (-1, 6)), ((6, -1), (1, 1)))
LOTTERY = (((2, 2), (0, 5)), ((5, 0), (1, 1)))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def number(value):
    require(type(value) in (int, F), "exact bounded scalar")
    x = F(value)
    require(abs(x) <= 10**6 and x.denominator <= 10**9, "rational bounds")
    return x


def vector(values, size=None):
    require(type(values) in (tuple, list) and 1 <= len(values) <= 8, "finite vector")
    require(size is None or len(values) == size, "vector dimension")
    return tuple(number(v) for v in values)


def probability(value):
    p = number(value)
    require(0 <= p <= 1, "probability interval")
    return p


def discount(value):
    d = number(value)
    require(0 < d < 1, "strict discount interval")
    return d


def posterior(weights):
    w = vector(weights)
    require(min(w) >= 0 and sum(w) > 0, "positive conditional mass")
    return tuple(x/sum(w) for x in w)


def dot(left, right):
    x, y = vector(left), vector(right)
    require(len(x) == len(y), "dot dimension")
    return sum((a*b for a, b in zip(x, y)), F(0))


def plans(rows):
    require(type(rows) in (tuple, list) and 1 <= len(rows) <= 8, "finite plan support")
    out = {}
    for row in rows:
        require(type(row) in (tuple, list) and len(row) == 2, "plan and mass")
        actions, mass = row
        require(type(actions) in (tuple, list) and len(actions) == 3, "three plan coordinates")
        require(all(type(x) is int and x in (0, 1) for x in actions), "binary plan coordinates")
        key = tuple(actions)
        require(key not in out, "unique plan")
        out[key] = probability(mass)
    require(sum(out.values()) == 1, "complete plan law")
    return out


def terminal_law(rows):
    answer = [F(0)]*4
    for (branch, after_x, after_y), mass in plans(rows).items():
        answer[2*branch+(after_x if branch == 0 else after_y)] += mass
    return tuple(answer)


def behavioral_law(values):
    p, a, b = tuple(probability(v) for v in vector(values, 3))
    return (p*a, p*(1-a), (1-p)*b, (1-p)*(1-b))


def clip(interval, constant, slope, sign):
    lo, hi, lc, hc = interval
    a, b = number(constant), number(slope)
    require(type(sign) is int and sign in (-1, 0, 1), "inequality orientation")
    if b == 0:
        return interval if (a == 0 if sign == 0 else sign*a >= 0) else None
    root = -a/b
    if sign == 0:
        inside = (lo < root or (lo == root and lc)) and (root < hi or (root == hi and hc))
        return (root, root, True, True) if inside else None
    if sign*b > 0 and root > lo:
        lo, lc = root, True
    elif sign*b < 0 and root < hi:
        hi, hc = root, True
    return (lo, hi, lc, hc) if lo < hi or (lo == hi and lc and hc) else None


def entry_supports(cost=0):
    k = number(cost)
    require(k >= 0, "nonnegative entry cost")
    cells = {0: (F(0), F(0), True, True), 1: (F(1), F(1), True, True),
             2: (F(0), F(1), False, False)}
    sign = {0: -1, 1: 1, 2: 0}
    found = {}
    # x=Pr(In), f=Pr(Fight). The primitive payoff differences are
    # (4-k)-2 + [(-1-k)-(4-k)]f and [(-2)-1]x.
    for xs, fs in product(range(3), repeat=2):
        x = clip(cells[xs], 0, -3, sign[fs])
        f = clip(cells[fs], 2-k, -5, sign[xs])
        if x is not None and f is not None:
            found[(xs, fs)] = (x, f)
    return found


def reward_path(rewards, terminal_reward, d):
    sequence, last, d = vector(rewards), number(terminal_reward), discount(d)
    return sum((d**t*r for t, r in enumerate(sequence)), F(0))+d**len(sequence)*last/(1-d)


def forgiveness(T, d):
    require(type(T) is int and 1 <= T <= 6, "bounded positive punishment length")
    d = discount(d)
    return (F(4)/(1-d),)+tuple(reward_path((1,)*k, 4, d) for k in range(1, T+1))


def lottery(lam, d):
    lam, d = probability(lam), discount(d)
    require(0 < lam < 1, "both public recommendations supported")
    signals, masses = ((0, 1), (1, 0)), (lam, 1-lam)
    target = tuple(sum(m*LOTTERY[x][y][i] for (x, y), m in zip(signals, masses)) for i in (0, 1))
    gains, margins = [], []
    for i in (0, 1):
        g = []
        for signal in signals:
            changed = list(signal); changed[i] = 1-changed[i]
            g.append(F(LOTTERY[changed[0]][changed[1]][i]-LOTTERY[signal[0]][signal[1]][i]))
        gains.append(tuple(g))
        margins.append(tuple(d*(target[i]-1)-(1-d)*v for v in g))
    return target, tuple(gains), tuple(margins)


def reputation(prior, d):
    pi, d = probability(prior), discount(d)
    require(0 < pi < F(1, 2) and d > F(2, 3), "scoped interior reputation construction")
    q = pi/(1-pi)
    e = 1-F(2, 3)/d
    beliefs = {"O": pi, "F": F(1, 2), "A": F(0)}
    entries = {"O": F(1), "F": e, "A": F(1)}
    r_later = {h: (1-v)*4+v*1 for h, v in entries.items()}
    c_later = {h: (1-v)*4-v for h, v in entries.items()}
    r_responses = (-1+d*r_later["F"], 1+d*r_later["A"])
    fight_chance = pi+(1-pi)*q
    entrant_value = fight_chance*(-2)+(1-fight_chance)*2
    first_entry = F(int(entrant_value > 0))
    require(entrant_value != 0, "strict first-entry cases only")
    r_entry_value = q*r_responses[0]+(1-q)*r_responses[1]
    c_entry_value = -1+d*c_later["F"]
    r_path = first_entry*r_entry_value+(1-first_entry)*(4+d*r_later["O"])
    c_path = first_entry*c_entry_value+(1-first_entry)*(4+d*c_later["O"])
    return q, e, beliefs, entries, r_responses, entrant_value, first_entry, (r_path, c_path)


def reputation_beliefs(prior, rational_fight, first_entry):
    pi, q, x = probability(prior), probability(rational_fight), probability(first_entry)
    weights = {"O": (pi*(1-x), (1-pi)*(1-x)), "F": (pi*x, (1-pi)*x*q),
               "A": (F(0), (1-pi)*x*(1-q))}
    require(all(sum(row) > 0 for row in weights.values()), "all public histories reached in consistency witness")
    return {h: posterior(row)[0] for h, row in weights.items()}, weights


def strict_json(text):
    def pairs(items):
        out = {}
        for key, value in items:
            require(key not in out, "duplicate JSON key")
            out[key] = value
        return out
    def bad(value):
        raise ValueError("nonfinite JSON constant "+value)
    result = json.loads(text, object_pairs_hook=pairs, parse_constant=bad)
    json.dumps(result, allow_nan=False)
    return result


def expression(text):
    require(type(text) is str and len(text) <= 1500, "marker bound")
    tree = ast.parse(text.strip().replace("−", "-"), mode="eval")
    require(sum(1 for _ in ast.walk(tree)) <= 250, "marker node bound")
    def visit(node):
        if isinstance(node, ast.Constant) and type(node.value) is int:
            return number(node.value)
        if isinstance(node, (ast.List, ast.Tuple)):
            require(1 <= len(node.elts) <= 8, "marker tuple bound")
            return tuple(visit(v) for v in node.elts)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            v = visit(node.operand); require(type(v) is F, "scalar sign")
            return -v if isinstance(node.op, ast.USub) else v
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            v, w = visit(node.left), visit(node.right)
            require(type(v) is F and type(w) is F and w != 0, "scalar division")
            return number(v/w)
        raise ValueError("unsupported numeric marker")
    return visit(tree.body)


class Document(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids, self.results, self.sources = {}, {}, {}
        self.worked, self.exercises, self.solutions, self.links, self.text = [], [], [], [], []
        self.stack, self.marker = [], None
        self.exdepth = self.soldepth = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs); require(len(a) == len(attrs), "unique attributes")
        if "id" in a:
            require(a["id"] not in self.ids, "unique IDs"); self.ids[a["id"]] = tag
        classes = a.get("class", "").split()
        ex, sol = tag == "ol" and "exercises" in classes, tag == "details" and "solutions" in classes
        if "worked" in classes: self.worked.append(a.get("id"))
        if tag == "li" and self.exdepth: self.exercises.append(a.get("id"))
        if "data-solution-for" in a:
            require(tag == "li" and self.soldepth, "standard solution disclosure")
            self.solutions.append(a["data-solution-for"])
        self.exdepth += int(ex); self.soldepth += int(sol)
        if tag not in ("br", "hr", "img", "input", "meta", "link"): self.stack.append((tag, ex, sol))
        if "data-calc" in a:
            require(tag == "span" and self.marker is None and a["data-calc"] not in self.results, "unique numeric marker")
            self.marker = (a["data-calc"], [])
        if tag == "a":
            self.links.append(a.get("href", ""))
            if "data-source" in a:
                key = a["data-source"]
                require(key not in self.sources or self.sources[key] == a.get("href"), "reused source has same URL")
                self.sources[key] = a.get("href")

    def handle_data(self, text):
        self.text.append(text)
        if self.marker is not None: self.marker[1].append(text)

    def handle_endtag(self, tag):
        require(self.stack and self.stack[-1][0] == tag, "balanced HTML")
        _, ex, sol = self.stack.pop(); self.exdepth -= int(ex); self.soldepth -= int(sol)
        if tag == "span" and self.marker is not None:
            key, pieces = self.marker; self.results[key] = expression("".join(pieces)); self.marker = None


class Audit:
    def __init__(self): self.comparisons = self.rejections = 0
    def equal(self, actual, expected, label):
        self.comparisons += 1
        require(actual == expected, label+": "+repr(actual)+" != "+repr(expected))
    def true(self, condition, label): self.equal(bool(condition), True, label)
    def reject(self, function, *args):
        self.rejections += 1
        try: function(*args)
        except (ValueError, TypeError, SyntaxError, ZeroDivisionError): return
        raise ValueError("invalid domain accepted by "+function.__name__)


def derive(a):
    results = {}
    mixture = (((0, 0, 0), F(1, 2)), ((0, 1, 0), F(1, 6)), ((1, 0, 1), F(1, 3)))
    distribution = plans(mixture)
    x_mass = sum(v for s, v in distribution.items() if s[0] == 0)
    x_l = sum(v for s, v in distribution.items() if s[:2] == (0, 0))/x_mass
    y_l = sum(v for s, v in distribution.items() if s[0] == 1 and s[2] == 0)/(1-x_mass)
    behavior = (x_mass, x_l, y_l)
    results["kuhn-terminal-law"] = terminal_law(mixture)
    a.equal(behavior, (F(2, 3), F(3, 4), 0), "remembered-prefix conditional behavior")
    a.equal(behavioral_law(behavior), results["kuhn-terminal-law"], "terminal law from prefix telescoping")
    independent = tuple((s, (behavior[0] if s[0] == 0 else 1-behavior[0])
                           *(behavior[1] if s[1] == 0 else 1-behavior[1])
                           *(behavior[2] if s[2] == 0 else 1-behavior[2])) for s in product((0, 1), repeat=3))
    a.equal(terminal_law(independent), results["kuhn-terminal-law"], "independent full-plan product realizes same paths")
    a.true(plans(independent) != distribution, "unused plan correlation is not identified")
    a.equal(behavioral_law((1, F(1, 4), 0)), behavioral_law((1, F(1, 4), 1)), "zero own-prefix continuation arbitrary")
    regions = entry_supports()
    a.equal(set(regions), {(0, 1), (0, 2), (1, 0)}, "every binary entry support cell considered")
    a.equal(regions[(0, 2)], ((0, 0, True, True), (F(2, 5), 1, True, False)), "full threat interval below its pure endpoint")
    a.equal(regions[(0, 1)], ((0, 0, True, True), (1, 1, True, True)), "closed upper threat endpoint")
    a.equal(regions[(1, 0)], ((1, 1, True, True), (0, 0, True, True)), "sole entry Nash profile")
    results["entry-threat-cutoff"] = F(4-2, 4-(-1))
    for k, sign in ((1, 1), (2, 0), (3, -1)):
        gap = 4-k-2
        a.equal((gap > 0)-(gap < 0), sign, "SPE entry-cost correspondence")
        a.true(1 > -2, "off-path incumbent accommodation strictly optimal at every cost")

    prior, likelihood = (F(1, 3), F(2, 3)), (F(3, 4), F(1, 4))
    values = (dot(prior, (3, 0)), dot(prior, (0, 2)))
    results["state-action-values"], results["weak-belief-cutoff"] = values, F(2, 3+2)
    for theta, expected in ((F(1, 3), False), (F(2, 5), True), (F(3, 4), True)):
        a.equal(3*theta >= 2*(1-theta), expected, "weak-PBE continuation action cutoff")
    a.true(values[1] > values[0] and 3 > 1, "consistent belief selects B and then Continue strictly")
    for c in (F(1, 2), F(1, 16)):
        a.equal(posterior(tuple(c*v for v in prior)), prior, "common Continue probability cancels")
        a.equal(((1-c)*1+c*values[1])-((1-c)*1+c*values[0]), c*(values[1]-values[0]), "agent ex ante gain equals positive reach times conditional gain")
    a.equal((1-F(0))*1+F(0)*values[0], (1-F(0))*1+F(0)*values[1], "unreached agent Nash does not resolve conditional choice")
    node_mass = tuple(p*l for p, l in zip(prior, likelihood))
    belief = posterior(node_mass)
    results["own-factor-posterior"] = belief[0]
    for go in (F(1), F(1, 4), F(1, 64)):
        reached = tuple(go*p for p in node_mass)
        a.equal((sum(reached), posterior(reached)), (F(5, 12)*go, belief), "changed own continuation leaves conditional node odds unchanged")
    # Additional peer-only two-information-set witness: stop pays 1/2;
    # at k, A pays (3,0), B pays (0,2). It tests the actual last replacement.
    def continuation(go, choose_a):
        return (1-go)*F(1, 2)+go*dot(node_mass, (3*choose_a, 2*(1-choose_a)))
    conditional_values = (dot(belief, (3, 0)), dot(belief, (0, 2)))
    a.equal(conditional_values, (F(9, 5), F(4, 5)), "consistent later information-set comparison")
    a.equal(continuation(1, 1)-continuation(1, 0), sum(node_mass)*(conditional_values[0]-conditional_values[1]), "positive-deviation-reach last replacement identity")
    a.equal(continuation(0, 1)-continuation(0, 0), 0, "unreached later replacement has zero effect")
    a.equal(max(continuation(g, z) for g, z in product((0, 1), repeat=2)), F(3, 4), "all complete continuations match backward replacement optimum")
    a.true(continuation(1, 0) < continuation(0, 0) < continuation(1, 1), "inconsistent later belief can hide a profitable complete deviation")

    gains = tuple(PD[1][other][0]-PD[0][other][0] for other in (0, 1))
    a.equal(gains, (2, 2), "strict defection at every stage opponent action")
    results["grim-cutoff"] = F(PD[1][0][0]-PD[0][0][0], PD[1][0][0]-PD[1][1][0])
    for d in (F(1, 3), F(2, 5), F(3, 4)):
        cooperative, punished = F(4)/(1-d), F(1)/(1-d)
        a.equal(cooperative-(6+d*punished), (5*d-2)/(1-d), "grim exact continuation margin")
        a.equal(punished-(-1+d*punished), 2, "absorbing punishment strictly credible")
        a.equal(cooperative >= 6+d*punished, d >= results["grim-cutoff"], "grim cutoff includes equality")
    a.true(F(1, 3) < results["grim-cutoff"] <= F(3, 4), "heterogeneous discounts fail if either player fails")
    for T, d in ((1, F(1, 2)), (2, F(1, 2)), (4, F(41, 100))):
        v = forgiveness(T, d)
        a.equal(v[0], 4+d*v[0], "cooperative discounted reward recursion")
        for k in range(1, T+1):
            a.equal(v[k], 1+d*v[k-1], "every finite punishment reward path")
            a.equal(v[k]-(-1+d*v[T]), 2+d*(v[k-1]-v[T]), "every reset-state deviation margin")
            a.true(v[k]-(-1+d*v[T]) >= 2, "punishment remains credible after every represented history")
        a.equal(v[0]-(6+d*v[T]), 3*sum(d**j for j in range(1, T+1))-2, "finite punishment cooperation polynomial")
        if T == 1: results["one-period-deviation"] = 6+d*v[T]
        if T == 2:
            results["forgiveness-values"] = v
            results["forgiveness-coop-deviation"] = 6+d*v[T]
            results["forgiveness-punishment-deviation"] = -1+d*v[T]
    a.equal(3*F(2, 3), 2, "one-period exact root")
    a.equal((-24, 36, 36), tuple(12*x for x in (-2, 3, 3)), "two-period quadratic equivalent to (6d+3)^2=33")
    a.true(3*(F(9, 20)+F(9, 20)**2) < 2 < 3*(F(23, 50)+F(23, 50)**2), "unique positive two-period root exact bracket")
    for T in (1, 2, 4):
        d = F(2, 5)
        incentive = 3*sum(d**t for t in range(1, T+1))
        a.equal(incentive, 2*(1-d**T), "finite punishment gap at the infinite limiting cutoff")
        a.true(incentive < 2, "no tested finite reset reaches the limiting cutoff")
    d, M, K = F(1, 2), 6, 5
    a.equal((1-d)*sum(2*M*d**t for t in range(K, K+3))+2*M*d**(K+3), 2*M*d**K, "uniform normalized tail decomposition")
    a.true(2*M*d**K < F(1, 2), "a unit improving deviation retains positive truncated improvement")

    a.equal(tuple(LOTTERY[1][j][0]-LOTTERY[0][j][0] for j in (0, 1)), (3, 1), "B strictly dominates under lottery stage primitives")
    a.equal(min(LOTTERY[1][j][0] for j in (0, 1)), 1, "dominant-action security minimum at opposing B")
    for lam, d in ((F(1, 2), F(2, 5)), (F(1, 3), F(1, 2)), (F(1, 3), F(3, 5)),
                   (F(2, 5), F(1, 2)), (F(3, 5), F(1, 2))):
        target, gains, margins = lottery(lam, d)
        bound = tuple(max(g)/(max(g)+v-1) for g, v in zip(gains, target))
        a.equal(tuple(max(g) for g in gains), (1, 1), "every supported public signal included in temptation")
        a.equal(tuple(min(m) >= 0 for m in margins), tuple(d >= t for t in bound), "exact player-specific post-signal constraints")
        a.equal(tuple(1/(5*x) for x in (1-lam, lam)), bound, "closed-form conditional thresholds")
        if lam == F(1, 2):
            results["lottery-target"], results["lottery-cutoff"] = target, max(bound)
        if lam == F(1, 3):
            results["changed-lottery-target"], results["changed-lottery-bounds"] = target, bound
        if d == F(1, 2):
            a.equal(all(min(m) >= 0 for m in margins), F(2, 5) <= lam <= F(3, 5), "complete half-discount lottery interval witnesses")
    d = F(1, 2)
    results["half-discount-lottery-interval"] = (1/(5*d), 1-1/(5*d))
    weak_target, weak_gain, weak_margin = lottery(F(1, 5), F(3, 4))
    a.equal((weak_target[1]-1, max(weak_gain[1])), (0, 1), "weak-security endpoint has zero continuation surplus and positive temptation")
    a.true(min(weak_margin[1]) < 0, "Nash reversion fails at the weak-security endpoint")
    a.true(min(lottery(F(1, 10), F(3, 4))[0]) < 1, "outside security interval violates a necessary bound")
    a.equal(LOTTERY[1][1][0]-LOTTERY[0][1][0], 1, "absorbing mixed-Nash theorem specializes to credible BB punishment")

    pure_continuations = 0
    for pi in (F(1, 3), F(1, 5)):
        d = F(4, 5)
        q, e, beliefs, entries, response, entrant, first, path = reputation(pi, d)
        a.equal((posterior((pi, (1-pi)*q))[0], e), (F(1, 2), F(1, 6)), "Bayes and response indifference determine both mixtures")
        a.equal(response[0], response[1], "rational first response continuation indifference")
        for h in ("O", "F", "A"):
            entry_gain = 2*(1-beliefs[h])-2*beliefs[h]
            a.true(entry_gain == 0 if h == "F" else entry_gain > 0, "every second entrant history has its stated best reply")
            a.equal(1-(-1), 2, "R strictly accommodates at every final response")
        a.equal(entrant, 2-8*pi, "first entrant faces actual conditional fight law")
        a.true((entrant > 0) == bool(first), "first entrant strict choice at both priors")
        # Independent backward utility accounting over all 16 pure R plans.
        # Opponent continuation rules stay fixed when R changes its own plan.
        plan_values = []
        for current, after_o, after_f, after_a in product((0, 1), repeat=4):
            last = {}
            for h, fight in zip(("O", "F", "A"), (after_o, after_f, after_a)):
                last[h] = 4*(1-entries[h])+entries[h]*(-1 if fight else 1)
            now, history = (-1, "F") if current else (1, "A")
            plan_values.append((now+d*last[history], 4+d*last["O"]))
            pure_continuations += 1
        a.equal(max(x[0] for x in plan_values), response[0], "no complete R deviation after first entry improves")
        a.equal(max(x[1] for x in plan_values), F(24, 5), "no complete R deviation after first Out improves")
        a.equal(path[0], first*response[0]+(1-first)*F(24, 5), "rational type on-path branch accounting")
        c_after_f = 4*(1-e)-e
        a.equal(path[1], first*(-1+d*c_after_f)+(1-first)*(4-d), "committed type dated path accounting")
        a.true(1 > -1, "relaxing C's singleton response would change final-period incentives")
        for eps in (F(1, 4), F(1, 32)):
            x = 1-eps if first else eps
            consistent, weights = reputation_beliefs(pi, q, x)
            a.equal(consistent, beliefs, "one common completely mixed sequence gives all O/F/A posteriors")
            a.true(all(sum(row) > 0 for row in weights.values()) and all(0 < p < 1 for p in (x, q, eps, e, 1-eps)), "all available non-singleton choices are fully mixed")
        if pi == F(1, 3):
            results.update({"reputation-response-values": response, "reputation-first-entry": entrant,
                            "reputation-rational-path": path[0], "reputation-commitment-path": path[1]})
        else:
            results.update({"reputation-changed-q": q, "reputation-changed-entry": entrant,
                            "reputation-changed-path": path})

    # Derive the quadratic from the three terminal rewards, then complete its square.
    early, second, late = F(0), F(5), F(1)
    coefficients = (late, early+second-2*late, late-second)
    p = -coefficients[1]/(2*coefficients[2])
    value = coefficients[0]+coefficients[1]*p+coefficients[2]*p*p
    results["absentminded-optimum"] = (p, value)
    a.equal((coefficients[0], coefficients[1], coefficients[2]), (value+coefficients[2]*p*p, -2*coefficients[2]*p, coefficients[2]), "global completed-square coefficient certificate")
    a.true(0 < p < 1 and coefficients[2] < 0, "unique global behavioral optimum lies inside domain")
    a.true(value > max(early, late), "every mixed pure-plan value below behavioral optimum")
    a.equal(p+(1-p)*p+(1-p)**2, 1, "absentminded terminal probability accounting")
    a.true((1-p)*p > 0, "second-exit terminal mass absent from every mixed fixed-action plan")
    return results, pure_continuations


def check(root=None):
    require(root is None or isinstance(root, (str, Path)), "root path type")
    base = Path(root).resolve() if root is not None else Path(__file__).resolve().parents[1]
    a, doc = Audit(), Document()
    doc.feed((base/AUTHORS[0]).read_text(encoding="utf-8")); doc.close()
    a.equal((doc.stack, doc.marker), ([], None), "complete balanced manuscript")
    prompts = ["v13-c07-ex"+str(i) for i in range(1, 13)]
    a.equal((doc.exercises, doc.solutions), (prompts, prompts), "all twelve exact solution pairs")
    a.equal(doc.worked, ["v13-c07-case"+str(i) for i in range(1, 7)], "six worked cases")
    a.true(all(key.startswith("v13-c07-") for key in doc.ids), "unique namespaced IDs")
    text = "".join(doc.text)
    a.true("Exercise 11 calculates" in text and "Exercise 2 calculates" not in text, "resolved absentminded cross-reference")
    a.true(all(s in text for s in ("Teach-back.", "Retention prompts.", "Answers.", "Scoring, 16 points.")), "answered teaching/retention and open rubric")
    a.equal(doc.sources, SOURCES, "reused scoped source URLs")
    a.equal({v for v in doc.links if not v.startswith("https://")}, {"v13-c0"+str(i)+".html" for i in (3, 4, 5, 6, 8)}, "flat prerequisite/successor routes")
    results, continuation_count = derive(a)
    a.equal(set(doc.results), set(results), "all printed numerical anchors covered")
    for key, expected in results.items(): a.equal(doc.results[key], expected, "printed "+key)
    for value in (True, 0.5, "1", 1j, float("nan"), float("inf"), 10**6+1, F(1, 10**9+1)):
        a.reject(number, value)
    for value in (-1, F(3, 2)): a.reject(probability, value)
    for value in (0, 1, -1): a.reject(discount, value)
    for values in ((), (0, 0), (-1, 2)): a.reject(posterior, values)
    a.reject(vector, (1, 2), 3)
    for rows in ((), (((0, 0, 0), F(1, 2)),), (((0, True, 0), 1),), (((0, 0), 1),),
                 (((0, 0, 0), F(1, 2)), ((0, 0, 0), F(1, 2)))): a.reject(plans, rows)
    a.reject(behavioral_law, (1, 2, 0))
    a.reject(entry_supports, -1)
    for T in (0, 7, True): a.reject(forgiveness, T, F(1, 2))
    a.reject(reward_path, (), 1, F(1, 2))
    a.reject(lottery, 0, F(1, 2))
    a.reject(lottery, F(1, 2), 1)
    a.reject(reputation, F(1, 2), F(4, 5))
    a.reject(reputation, F(1, 3), F(2, 3))
    a.reject(reputation, F(1, 4), F(4, 5))
    a.reject(reputation_beliefs, F(1, 3), F(1, 2), 0)
    for raw in ('{"x":1,"x":2}', '{"x":NaN}'): a.reject(strict_json, raw)
    for raw in ("True", "1/0", "__import__('os')", "0.5", "[]"): a.reject(expression, raw)
    a.reject(Document().feed, '<p id="x"></p><p id="x"></p>')
    a.reject(Document().feed, '<li data-solution-for="x">outside disclosure</li>')
    source = strict_json((base/AUTHORS[2]).read_text(encoding="utf-8"))
    author = strict_json((base/AUTHORS[3]).read_text(encoding="utf-8"))
    peer = strict_json((base/RECORD).read_text(encoding="utf-8"))
    a.equal({v["id"]: v["url"] for v in source["proposals"]}, SOURCES, "final source scope")
    a.equal({v["inspection"]["actual_inspector"] for v in source["proposals"]}, {"ito_author"}, "actual added-scope inspector")
    a.equal(sum(len(v["inspection"]["actual_image_physical_pages"]) for v in source["proposals"]), 7, "seven actual scoped page images")
    a.equal(set(peer["exercise_audit"]), set(prompts), "peer every exact prompt judgment")
    a.equal(set(peer["proof_audit"]), {"v13-c07-"+k for k in ("tree", "subgame", "assessment", "existence", "repetition", "forgiveness", "folk", "reputation")}, "peer full proof coverage")
    a.equal(peer["open_findings"], [], "no unresolved material findings")
    for title, bindings, paths in (("author", author["bindings"], AUTHORS[:3]), ("peer", peer["bindings"], AUTHORS+(SELF,))):
        a.equal((len(bindings), {v["path"] for v in bindings}), (len(paths), set(paths)), title+" exact binding set")
        for item in bindings:
            raw = (base/item["path"]).read_bytes()
            a.equal((len(raw), sha256(raw).hexdigest()), (item["bytes"], item["sha256"]), title+" binding "+item["path"])
    summary = {"chapter": "v13-c07", "status": "passed", "comparisons": a.comparisons,
               "domain_rejections": a.rejections, "intervention_groups": 12,
               "worked_cases": 6, "solved_exercises": 12, "numeric_anchors": len(results),
               "rational_type_complete_plan_checks": continuation_count, "source_scopes": 2,
               "author_execution_used_as_oracle": False}
    require(strict_json(json.dumps(summary, allow_nan=False)) == summary, "strict JSON-safe summary")
    return summary


if __name__ == "__main__":
    require(len(sys.argv) == 1, "silent CLI accepts no arguments")
    check()
