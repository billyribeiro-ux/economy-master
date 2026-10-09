"""Exact finite-game author checks; quiet, portable and read-only.

Original payoff/conditional-prior reconstruction, bounded support systems,
CE vertices and explicit deviation maps supplement the manuscript proofs.
"""
from fractions import Fraction as F
from html.parser import HTMLParser
from itertools import combinations, product
from pathlib import Path
import ast
import hashlib
import json

HTML = 'content/chapters/v13-c06.html'
SELF = 'scripts/check_v13_c06.py'
SOURCES = 'content/reviews/v13-c06-sources.json'
REVIEW = 'content/reviews/v13-c06-author.json'


def require(ok, label):
    if not ok:
        raise ValueError(label)


class Audit:
    def __init__(self):
        self.comparisons = 0
        self.rejections = 0
        self.interventions = 0

    def equal(self, actual, expected, label):
        require(actual == expected, label+': '+repr(actual)+' != '+repr(expected))
        self.comparisons += 1

    def true(self, value, label):
        self.equal(bool(value), True, label)

    def reject(self, call, label):
        try:
            call()
        except ValueError:
            self.rejections += 1
        else:
            raise ValueError('invalid case accepted: '+label)


def exact(value):
    require(type(value) in (int, F), 'exact integer/Fraction required, no bool or float')
    require(abs(value) <= 1000000, 'bounded witness arithmetic')
    return F(value)


def vector(value, size=None):
    require(type(value) in (tuple, list) and 1 <= len(value) <= 16, 'nonempty bounded vector')
    require(size is None or len(value) == size, 'vector dimension')
    return tuple(exact(x) for x in value)


def probability(value, size=None):
    out = vector(value, size)
    require(min(out) >= 0 and sum(out) == 1, 'probabilities nonnegative and sum to one')
    return out


def game(value):
    require(type(value) in (tuple, list) and 1 <= len(value) <= 3, 'finite row action count')
    require(type(value[0]) in (tuple, list) and 1 <= len(value[0]) <= 3, 'finite column action count')
    width = len(value[0])
    rows = []
    for row in value:
        require(type(row) in (tuple, list) and len(row) == width, 'rectangular game')
        rows.append(tuple(vector(pair, 2) for pair in row))
    return tuple(rows)


def dims(g):
    return len(g), len(g[0])


def product_law(p, q):
    p, q = probability(p), probability(q)
    return tuple(a*b for a in p for b in q)


def payoff(g, mu):
    n, m = dims(g)
    mu = probability(mu, n*m)
    return tuple(sum(mu[r*m+c]*g[r][c][i] for r in range(n) for c in range(m)) for i in (0, 1))


def action_values(g, opponent, player):
    require(type(player) is int and player in (0, 1), 'two-player index')
    n, m = dims(g)
    if player == 0:
        q = probability(opponent, m)
        return tuple(sum(q[c]*g[r][c][0] for c in range(m)) for r in range(n))
    p = probability(opponent, n)
    return tuple(sum(p[r]*g[r][c][1] for r in range(n)) for c in range(m))


def is_nash(g, p, q):
    n, m = dims(g)
    p, q = probability(p, n), probability(q, m)
    values = (action_values(g, q, 0), action_values(g, p, 1))
    return all(sum(a*b for a, b in zip(own, vals)) == max(vals) for own, vals in zip((p, q), values))


def binary_differences(g):
    require(dims(g) == (2, 2), 'binary game')
    row0 = g[0][1][0]-g[1][1][0]
    row1 = (g[0][0][0]-g[1][0][0])-row0
    col0 = g[1][0][1]-g[1][1][1]
    col1 = (g[0][0][1]-g[0][1][1])-col0
    return (row0, row1), (col0, col1)


def strict_corner_equilibria(g):
    """Complete for two-action games with strict replies to each pure opponent.

    This condition excludes any equilibrium with only one player mixing. The
    remaining supports are the four pure pairs and the unique interior candidate.
    """
    row, col = binary_differences(g)
    require(all(x != 0 for x in (row[0], sum(row), col[0], sum(col))), 'strict pure-opponent reply class')
    result = []
    for p, q in product((F(0), F(1)), repeat=2):
        if is_nash(g, (p, 1-p), (q, 1-q)):
            result.append((p, q))
    if row[1] != 0 and col[1] != 0:
        p, q = -col[0]/col[1], -row[0]/row[1]
        if 0 < p < 1 and 0 < q < 1 and is_nash(g, (p, 1-p), (q, 1-q)):
            result.append((p, q))
    return tuple(sorted(result))


def constrained_bound(values, floors):
    values, floors = vector(values), vector(floors)
    require(len(values) == len(floors), 'payoff/floor dimensions')
    require(min(floors) > 0 and sum(floors) < 1, 'strictly positive feasible floors')
    return sum(a*b for a, b in zip(values, floors))+(1-sum(floors))*max(values)


def reverse_floors(limit, tremble, k):
    sigma, tau = probability(limit), probability(tremble)
    require(len(sigma) == len(tau) and min(tau) > 0, 'fully mixed matching tremble')
    require(type(k) is int and k >= 1, 'positive sequence index')
    return tuple(t if s == 0 else min(t/2, F(1, k)) for s, t in zip(sigma, tau))


def linear_solve(matrix, rhs):
    require(type(matrix) in (list, tuple) and 1 <= len(matrix) <= 4, 'small square system')
    n = len(matrix)
    b = vector(rhs, n)
    rows = [list(vector(row, n))+[b[i]] for i, row in enumerate(matrix)]
    for col in range(n):
        pivot = next((r for r in range(col, n) if rows[r][col]), None)
        if pivot is None:
            return None
        rows[col], rows[pivot] = rows[pivot], rows[col]
        scale = rows[col][col]
        rows[col] = [x/scale for x in rows[col]]
        for r in range(n):
            if r != col:
                factor = rows[r][col]
                rows[r] = [a-factor*b for a, b in zip(rows[r], rows[col])]
    return tuple(row[-1] for row in rows)


def entry_coefficients(prior):
    pi = probability(prior, 4)
    marginal = ((pi[0]+pi[1], pi[2]+pi[3]), (pi[0]+pi[2], pi[1]+pi[3]))
    require(all(x > 0 for row in marginal for x in row), 'positive own-type marginals')
    weights, coefficients = [], []
    for player in (0, 1):
        for t in (0, 1):
            joint = (pi[2*t], pi[2*t+1]) if player == 0 else (pi[t], pi[2+t])
            belief = tuple(x/marginal[player][t] for x in joint)
            weights.append(belief)
            row = [F(0)]*4
            for other in (0, 1): row[2*(1-player)+other] = -4*belief[other]
            coefficients.append((F(3 if t == 0 else 1), tuple(row)))
    return marginal, tuple(weights), tuple(coefficients)


def entry_outcome(prior, strategy):
    x = vector(strategy, 4)
    require(all(0 <= a <= 1 for a in x), 'type entry probabilities')
    marginal, weights, coeff = entry_coefficients(prior)
    gains = tuple(a+sum(b*c for b, c in zip(row, x)) for a, row in coeff)
    best = all((p == 0 and g <= 0) or (p == 1 and g >= 0) or (0 < p < 1 and g == 0) for p, g in zip(x, gains))
    values = tuple(sum(marginal[i][t]*x[2*i+t]*gains[2*i+t] for t in (0, 1)) for i in (0, 1))
    aggregate = tuple(sum(marginal[i][t]*x[2*i+t] for t in (0, 1)) for i in (0, 1))
    return {'conditional': weights, 'gains': gains, 'best': best, 'values': values, 'aggregate': aggregate}


def entry_support_systems(prior):
    """Enumerate the 81 pure/mixed type-agent support patterns for the baseline.

    This reconstructs candidates from conditional laws, not the manuscript's
    aggregate best-response table. Completeness in the baseline also has an
    analytic five-region proof; no general claim about degenerate type games.
    """
    _, _, coeff = entry_coefficients(prior)
    solutions = set()
    for pattern in product((0, 1, 2), repeat=4):
        matrix, rhs = [], []
        for i, mode in enumerate(pattern):
            if mode in (0, 1):
                matrix.append(tuple(F(int(j == i)) for j in range(4))); rhs.append(F(mode))
            else:
                constant, row = coeff[i]; matrix.append(row); rhs.append(-constant)
        candidate = linear_solve(matrix, rhs)
        if candidate is None or any(x < 0 or x > 1 for x in candidate): continue
        if any(mode == 2 and not 0 < candidate[i] < 1 for i, mode in enumerate(pattern)): continue
        if entry_outcome(prior, candidate)['best']: solutions.add(candidate)
    return tuple(sorted(solutions))


def ce_rows(g):
    n, m = dims(g)
    rows, labels = [], []
    for player, count in ((0, n), (1, m)):
        for rec, dev in product(range(count), repeat=2):
            if rec == dev: continue
            row = []
            for r, c in product(range(n), range(m)):
                own = r if player == 0 else c
                changed = g[dev][c][player] if player == 0 else g[r][dev][player]
                row.append(g[r][c][player]-changed if own == rec else F(0))
            rows.append(tuple(row)); labels.append((player, rec, dev))
    return tuple(labels), tuple(rows)


def ce_gaps(g, mu):
    n, m = dims(g); mu = probability(mu, n*m)
    _, rows = ce_rows(g)
    return tuple(sum(a*b for a, b in zip(row, mu)) for row in rows)


def deviation_value(g, mu, player, rule):
    n, m = dims(g); mu = probability(mu, n*m)
    require(type(player) is int and player in (0, 1), 'player index')
    count = n if player == 0 else m
    require(type(rule) in (tuple, list) and len(rule) == count, 'deviation rule dimension')
    require(all(type(a) is int and 0 <= a < count for a in rule), 'deviation rule actions')
    result = F(0)
    for r, c in product(range(n), range(m)):
        value = g[rule[r]][c][0] if player == 0 else g[r][rule[c]][1]
        result += mu[r*m+c]*value
    return result


def cce_gaps(g, mu):
    values = payoff(g, mu)
    out = []
    for player, count in enumerate(dims(g)):
        for dev in range(count):
            out.append(values[player]-deviation_value(g, mu, player, (dev,)*count))
    return tuple(out)


def conditional_values(g, mu, player, rec, dev):
    n, m = dims(g); mu = probability(mu, n*m)
    require(type(player) is int and player in (0, 1), 'conditional player')
    count = (n, m)[player]
    require(type(rec) is int and type(dev) is int and 0 <= rec < count and 0 <= dev < count, 'recommendation/deviation index')
    mass = sum(mu[r*m+c] for r, c in product(range(n), range(m)) if (r if player == 0 else c) == rec)
    require(mass > 0, 'positive recommendation mass needed for conditional division')
    obey, change = F(0), F(0)
    for r, c in product(range(n), range(m)):
        if (r if player == 0 else c) != rec: continue
        obey += mu[r*m+c]*g[r][c][player]
        change += mu[r*m+c]*(g[dev][c][0] if player == 0 else g[r][dev][1])
    return obey/mass, change/mass


def ce_vertices(g):
    require(dims(g) == (2, 2), 'bounded four-profile CE vertex oracle')
    _, rows = ce_rows(g)
    rows = rows+tuple(tuple(F(int(i == j)) for j in range(4)) for i in range(4))
    vertices = set()
    for active in combinations(rows, 3):
        candidate = linear_solve(((1, 1, 1, 1),)+active, (1, 0, 0, 0))
        if candidate is not None and all(sum(a*b for a, b in zip(row, candidate)) >= 0 for row in rows):
            vertices.add(candidate)
    return tuple(sorted(vertices))


def strict_json(text):
    def pairs(items):
        out = {}
        for key, value in items:
            require(key not in out, 'duplicate JSON key'); out[key] = value
        return out
    def bad(_): raise ValueError('nonfinite JSON literal')
    try:
        data = json.loads(text, object_pairs_hook=pairs, parse_constant=bad)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError('invalid JSON') from exc
    json.dumps(data, allow_nan=False)
    return data


def expression(text):
    try:
        tree = ast.parse(text.strip().replace('−', '-'), mode='eval')
    except (TypeError, SyntaxError) as exc:
        raise ValueError('numeric marker syntax') from exc
    require(sum(1 for _ in ast.walk(tree)) <= 500, 'bounded numeric marker')
    def visit(node):
        if isinstance(node, ast.Constant): return exact(node.value)
        if isinstance(node, (ast.List, ast.Tuple)): return tuple(visit(x) for x in node.elts)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            a = visit(node.operand); require(type(a) is F, 'scalar sign')
            return a if isinstance(node.op, ast.UAdd) else -a
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
            a, b = visit(node.left), visit(node.right)
            require(type(a) is F and type(b) is F, 'scalar arithmetic')
            if isinstance(node.op, ast.Add): return a+b
            if isinstance(node.op, ast.Sub): return a-b
            if isinstance(node.op, ast.Mult): return a*b
            require(b != 0, 'nonzero denominator'); return a/b
        raise ValueError('unsupported marker expression')
    return visit(tree.body)


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.ids, self.headings, self.worked = [], [], [], []
        self.exercises, self.solutions, self.sources, self.links = [], [], [], []
        self.inputs, self.calcs = {}, {}
        self.exercise_depth = self.solution_depth = self.marker = None

    def handle_starttag(self, tag, attributes):
        a = dict(attributes)
        if 'id' in a: self.ids.append(a['id'])
        if tag in ('h1', 'h2', 'h3', 'h4'): self.headings.append(tag)
        if 'href' in a: self.links.append(a['href'])
        if 'data-source' in a: self.sources.append((a['data-source'], a.get('href')))
        if 'worked' in a.get('class', '').split(): self.worked.append(a.get('id'))
        if tag == 'ol' and 'exercises' in a.get('class', '').split():
            require(self.exercise_depth is None, 'no nested exercise lists'); self.exercise_depth = len(self.stack)
        if tag == 'details' and 'solutions' in a.get('class', '').split():
            require(self.solution_depth is None, 'one unnested disclosure'); self.solution_depth = len(self.stack)
        if tag == 'li' and self.exercise_depth is not None: self.exercises.append(a.get('id'))
        if tag == 'li' and self.solution_depth is not None: self.solutions.append(a.get('data-solution-for'))
        keys = [k for k in ('data-input', 'data-calc') if k in a]
        if keys:
            require(len(keys) == 1 and self.marker is None, 'single unnested numeric marker')
            self.marker = (len(self.stack), keys[0], a[keys[0]], [])
        require(tag not in ('script', 'style', 'iframe'), 'static chapter fragment')
        if tag not in ('br', 'hr', 'img', 'input', 'meta', 'link'): self.stack.append(tag)

    def handle_data(self, text):
        if self.marker is not None: self.marker[3].append(text)

    def handle_endtag(self, tag):
        require(self.stack and self.stack[-1] == tag, 'balanced tag '+tag)
        depth = len(self.stack)-1
        if self.marker is not None and self.marker[0] == depth:
            _, kind, name, pieces = self.marker
            target = self.inputs if kind == 'data-input' else self.calcs
            require(name not in target, 'unique marker '+name)
            target[name] = expression(''.join(pieces)); self.marker = None
        if tag == 'ol' and depth == self.exercise_depth: self.exercise_depth = None
        if tag == 'details' and depth == self.solution_depth: self.solution_depth = None
        self.stack.pop()


def derive(audit):
    inputs = {
        'zero-sum-matrix': ((F(3), F(-1)), (F(-2), F(2))), 'zero-sum-transfer': F(5),
        'weak-game': (((F(2), F(2)), (F(1), F(2))), ((F(2), F(1)), (F(0), F(0)))),
        'uniform-tremble': F(1, 10),
        'coordination-game': (((F(4), F(4)), (F(0), F(2))), ((F(2), F(0)), (F(3), F(3)))),
        'entry-costs': (F(1), F(3)), 'entry-parameters': (F(4), F(4)),
        'entry-correlated-prior': (F(3, 8), F(1, 8), F(1, 8), F(3, 8)),
        'recommendation-game': (((F(6), F(6)), (F(1), F(8))), ((F(8), F(1)), (F(0), F(0)))),
        'cyclic-game': ((F(1), F(-1), F(2)), (F(2), F(1), F(-1)), (F(-1), F(2), F(1))),
        'asymmetric-row-floor': F(1, 10), 'asymmetric-column-floor': F(1, 5),
        'perfection-limit': (F(1, 2), F(1, 2), F(0)),
        'perfection-tremble': (F(9, 20), F(9, 20), F(1, 10)),
        'mixed-dominance-matrix': ((F(2), F(0), F(2)), (F(0), F(2), F(2)), (F(1), F(1), F(1))),
        'coordination-transfer': (F(5), F(5)),
        'entry-anticorrelated-prior': (F(1, 8), F(3, 8), F(3, 8), F(1, 8)),
        'recommendation-transfer': (F(5), F(5))}
    result = {}
    # Reconstruct zero-sum supports, pure reply cycle and both saddle directions.
    zero_games = []
    for prefix, ul in (('zero-sum', F(3)), ('zero-sum-transfer', inputs['zero-sum-transfer'])):
        A = ((ul, F(-1)), (F(-2), F(2)))
        g = game(tuple(tuple((a, -a) for a in row) for row in A)); zero_games.append(g)
        candidates = strict_corner_equilibria(g)
        audit.equal(len(candidates), 1, prefix+' complete support classification')
        p, q = candidates[0]
        mu = product_law((p, 1-p), (q, 1-q)); values = payoff(g, mu)
        result[prefix+'-mix'] = (p, q); result[prefix+'-value'] = values[0]
        audit.equal(values[0]+values[1], 0, prefix+' zero-sum identity')
        audit.equal(action_values(g, (q, 1-q), 0), (values[0],)*2, prefix+' row global saddle bound')
        audit.equal(action_values(g, (p, 1-p), 1), (values[1],)*2, prefix+' column global saddle bound')
    audit.interventions += 1
    transformed = game(tuple(tuple((2*u+7, 3*v-5) for u, v in row) for row in zero_games[0]))
    audit.equal(strict_corner_equilibria(transformed), strict_corner_equilibria(zero_games[0]), 'positive affine utility invariance')
    audit.interventions += 1

    weak = game(inputs['weak-game'])
    audit.equal(binary_differences(weak), ((1, -1), (1, -1)), 'entire weak-game affine reply differences')
    for p, q in ((1, F(1, 3)), (F(2, 5), 1), (1, 1), (F(1, 2), F(1, 2)), (0, 0)):
        audit.equal(is_nash(weak, (p, 1-p), (q, 1-q)), p == 1 or q == 1, 'continuum branch/boundary witness')
    for prefix, alpha, beta in (('weak-tremble', F(1, 10), F(1, 10)), ('asymmetric-tremble', F(1, 10), F(1, 5))):
        p, q = 1-alpha, 1-beta
        result[prefix+'-profile'] = (p, q)
        values = payoff(weak, product_law((p, 1-p), (q, 1-q)))
        result[prefix+'-payoffs'] = values
        bounds = (constrained_bound(action_values(weak, (q, 1-q), 0), (alpha, alpha)),
                  constrained_bound(action_values(weak, (p, 1-p), 1), (beta, beta)))
        audit.equal(values, bounds, 'actual constrained linear global optima')
        audit.true(not is_nash(weak, (p, 1-p), (q, 1-q)), 'trembles need not be unconstrained Nash')
    for eps in (F(1, 20), F(1, 100)):
        vals = (action_values(weak, (1-eps, eps), 0), action_values(weak, (1-eps, eps), 1))
        audit.true(all(v[0] > v[1] for v in vals), 'fixed limit actions best against fully mixed tail')
    audit.interventions += 1
    floors = reverse_floors(inputs['perfection-limit'], inputs['perfection-tremble'], 10)
    result['perfection-floor-example'] = floors
    result['perfection-residual-example'] = tuple(t-d for t, d in zip(inputs['perfection-tremble'], floors))
    audit.true(min(floors) > 0 and sum(floors) < 1, 'reverse floors feasible')
    audit.equal(sum(result['perfection-residual-example']), 1-sum(floors), 'residual simplex accounting')
    for k in (10, 20):
        tau = ((1-F(1, k))/2, (1-F(1, k))/2, F(1, k))
        d = reverse_floors(inputs['perfection-limit'], tau, k)
        audit.true(max(d) <= F(1, k) and min(d) > 0 and sum(d) < 1, 'explicit vanishing floor tail witness')
        audit.equal(tau[2]-d[2], 0, 'all outside-support mass forced at its floor')
    audit.interventions += 1

    dominance = inputs['mixed-dominance-matrix']
    result['mixed-dominance-vector'] = tuple((dominance[0][j]+dominance[1][j])/2 for j in range(3))
    dg = game(tuple(tuple((a, 0) for a in row) for row in dominance))
    audit.true(is_nash(dg, (0, 0, 1), (F(1, 2), F(1, 2), 0)), 'specified dominated-action profile is Nash')
    audit.true(all(any(dominance[i][j] < dominance[2][j] for j in range(3)) for i in (0, 1)), 'no pure action dominates D')
    for q in ((F(1, 3),)*3, (F(2, 5), F(1, 2), F(1, 10))):
        vals = action_values(dg, q, 0)
        audit.equal((vals[0]+vals[1])/2-vals[2], q[2], 'mixed weak dominance strict under full support')
    audit.interventions += 1
    for prefix, last in (('coordination', F(3)), ('coordination-transfer', F(5))):
        g = game((((4, 4), (0, 2)), ((2, 0), (last, last))))
        equilibria = strict_corner_equilibria(g)
        audit.equal(len(equilibria), 3, 'complete coordination support count')
        interior = next((p, q) for p, q in equilibria if 0 < p < 1 and 0 < q < 1)
        result[prefix+'-mix'] = interior
        values = payoff(g, product_law((interior[0], 1-interior[0]), (interior[1], 1-interior[1])))
        result[prefix+('-mixed-payoffs' if prefix == 'coordination' else '-payoffs')] = values
        for p, q in ((F(1), F(1)), (F(0), F(0))):
            # Small fully mixed perturbations retain the strict equilibrium action.
            eps = F(1, 100)
            taup, tauq = ((1-eps)*p+eps/2, (1-eps)*q+eps/2)
            rv, cv = action_values(g, (tauq, 1-tauq), 0), action_values(g, (taup, 1-taup), 1)
            audit.true((rv[0] > rv[1]) == (p == 1) and (cv[0] > cv[1]) == (q == 1), 'strict pure equilibrium tremble certificate')
    audit.interventions += 1

    independent = (F(1, 4),)*4
    candidates = entry_support_systems(independent)
    outcomes = sorted((entry_outcome(independent, s)['aggregate'], s, entry_outcome(independent, s)['values']) for s in candidates)
    result['entry-equilibria'] = tuple(item[0] for item in outcomes)
    result['entry-payoffs'] = tuple(item[2] for item in outcomes)
    type_menu = sorted({((s[0]+s[1])/2, (s[0], s[1])) for s in candidates} |
                       {((s[2]+s[3])/2, (s[2], s[3])) for s in candidates})
    result['entry-type-menu'] = tuple(s for _, s in type_menu)
    audit.equal(len(outcomes), 5, 'independent finite type-agent support systems find five outcomes')
    for aggregate, strategy, values in outcomes:
        outcome = entry_outcome(independent, strategy)
        audit.true(outcome['best'], 'every type satisfies actual conditional best reply')
        # Sum payoffs directly across the four joint states as a separate ledger.
        direct = []
        for player in (0, 1):
            value = F(0)
            for own, other in product((0, 1), repeat=2):
                value += F(1, 4)*strategy[2*player+own]*(4-(1 if own == 0 else 3)-4*strategy[2*(1-player)+other])
            direct.append(value)
        audit.equal(tuple(direct), values, 'type-conditional and joint-state expectations agree')
    audit.interventions += 1
    for prefix, pi in (('entry-correlated', inputs['entry-correlated-prior']), ('entry-anticorrelated', inputs['entry-anticorrelated-prior'])):
        outcome = entry_outcome(pi, (1, 0, 1, 0))
        result[prefix+'-conditionals'] = (outcome['conditional'][0][0], outcome['conditional'][1][0])
        result[prefix+'-gains'] = outcome['gains'][:2]
        result[prefix+'-payoffs'] = outcome['values']
        audit.true(outcome['best'], 'changed-prior low-only profile is BNE')
        audit.equal(outcome['aggregate'], (F(1, 2), F(1, 2)), 'unchanged aggregate rates and type marginals')
    naive = entry_outcome(independent, (1, 0, 1, 0))
    audit.true(naive['gains'][:2] != result['entry-correlated-gains'], 'unconditional belief substitution changes incentives')
    # Correlation is absent with a pure own-type marginal only by changing scope;
    # it cannot license division by the zero marginal (rejected below).
    audit.interventions += 1

    recommend = game(inputs['recommendation-game'])
    ne = strict_corner_equilibria(recommend)
    audit.equal(len(ne), 3, 'complete recommendation-game Nash set')
    pn, qn = next((p, q) for p, q in ne if 0 < p < 1 and 0 < q < 1)
    result['recommendation-nash-probability'] = 1-pn
    result['recommendation-nash-payoffs'] = payoff(recommend, product_law((pn, 1-pn), (qn, 1-qn)))
    vertex_counts = []
    for prefix, yy in (('recommendation', F(6)), ('recommendation-transfer', F(5))):
        g = game((((yy, yy), (1, 8)), ((8, 1), (0, 0))))
        vertices = ce_vertices(g); vertex_counts.append(len(vertices))
        scores = [(sum(payoff(g, mu)), mu) for mu in vertices]
        maximum = max(value for value, _ in scores)
        maximizing = [mu for value, mu in scores if value == maximum]
        audit.equal(len(maximizing), 1, 'unique CE welfare vertex from original payoff inequalities')
        mu = maximizing[0]
        result[prefix+'-optimum'] = mu
        result[prefix+('-optimal-payoffs' if prefix == 'recommendation' else '-payoffs')] = payoff(g, mu)
        result[prefix+('-optimal-welfare' if prefix == 'recommendation' else '-welfare')] = maximum
        audit.true(min(ce_gaps(g, mu)) >= 0, 'computed optimal distribution obeys every pairwise constraint')
        # Independently check every recommendation-contingent deterministic rule.
        for i in (0, 1):
            deviations = tuple(deviation_value(g, mu, i, rule) for rule in product(range(2), repeat=2))
            audit.equal(max(deviations), payoff(g, mu)[i], 'all binary contingent rules obey')
        # Match global proof bound and exact equality restrictions, not just LP output.
        alpha, beta, gamma, delta = mu
        k = 8-yy
        audit.equal((delta, beta-k*alpha, gamma-k*alpha), (0, 0, 0), 'unique equality-case constraints')
        audit.equal(alpha, F(1, 1+2*k), 'normalization completes the global equality certificate')
    optimum = result['recommendation-optimum']
    result['recommendation-private-y'] = conditional_values(recommend, optimum, 0, 0, 1)
    result['recommendation-private-a'] = conditional_values(recommend, optimum, 0, 1, 0)
    py = optimum[0]+optimum[1]; qy = optimum[0]+optimum[2]
    independent_same = product_law((py, 1-py), (qy, 1-qy))
    result['recommendation-independent'] = independent_same
    result['recommendation-independent-slack'] = ce_gaps(recommend, independent_same)[0]
    audit.true(min(ce_gaps(recommend, independent_same)) < 0, 'preserving marginals does not preserve obedience')
    audit.true(not is_nash(recommend, (1, 0), (1, 0)) and optimum[0] > 0, 'public YY disclosure has a profitable deviation')
    audit.true(result['recommendation-optimal-welfare'] > max(sum(payoff(recommend, product_law((p, 1-p), (q, 1-q)))) for p, q in ne), 'CE outside every Nash-distribution welfare hull')
    for p, q in ne:
        mu = product_law((p, 1-p), (q, 1-q))
        audit.true(min(ce_gaps(recommend, mu)) >= 0, 'Nash product is CE including zero recommendation mass')
    mix = (F(0), F(1, 3), F(2, 3), F(0))
    audit.true(min(ce_gaps(recommend, mix)) >= 0, 'mixture of two pure Nash distributions is CE')
    audit.interventions += 1

    A = inputs['cyclic-game']
    cyclic = game(tuple(tuple((A[r][c], A[c][r]) for c in range(3)) for r in range(3)))
    diagonal = tuple(F(int(r == c), 3) for r, c in product(range(3), repeat=2))
    uniform = product_law((F(1, 3),)*3, (F(1, 3),)*3)
    result['cyclic-diagonal-payoffs'] = payoff(cyclic, diagonal)
    result['cyclic-fixed-deviation'] = deviation_value(cyclic, diagonal, 0, (0, 0, 0))
    rule = (1, 2, 0)
    result['cyclic-contingent-deviation'] = deviation_value(cyclic, diagonal, 0, rule)
    result['cyclic-obedience-slack'] = ce_gaps(cyclic, diagonal)[0]
    result['cyclic-independent-payoff'] = payoff(cyclic, uniform)[0]
    audit.true(min(cce_gaps(cyclic, diagonal)) >= 0 and min(ce_gaps(cyclic, diagonal)) < 0, 'diagonal CCE not CE')
    audit.true(is_nash(cyclic, (F(1, 3),)*3, (F(1, 3),)*3), 'independent uniform is Nash')
    audit.true(min(ce_gaps(cyclic, uniform)) >= 0, 'independent uniform is CE')
    for lam in (F(0), F(1, 2), F(1)):
        mu = tuple((1-lam)*a+lam*b for a, b in zip(uniform, diagonal))
        follow = payoff(cyclic, mu)[0]
        fixed = deviation_value(cyclic, mu, 0, (0,)*3)
        conditional = deviation_value(cyclic, mu, 0, rule)
        audit.equal((follow, fixed, conditional), (F(2, 3)+lam/3, F(2, 3), F(2, 3)+4*lam/3), 'full one-parameter payoff contract')
        audit.true(min(cce_gaps(cyclic, mu)) >= 0, 'family CCE at scoped intervention')
        audit.equal(min(ce_gaps(cyclic, mu)) >= 0, lam == 0, 'CE boundary is lambda zero')
        for i in (0, 1):
            values = tuple(deviation_value(cyclic, mu, i, d) for d in product(range(3), repeat=3))
            audit.equal(max(values), conditional, 'all 27 contingent rules per player independently evaluated')
        if lam == F(1, 2):
            result['cyclic-transfer-payoffs'] = (follow, fixed, conditional)
            result['cyclic-transfer-slack'] = ce_gaps(cyclic, mu)[0]
    audit.interventions += 1
    # Two-action equivalence is an algebraic identity for arbitrary joint laws,
    # not an attempted two-action separating counterexample.
    for mu in (optimum, independent_same, (F(1, 4),)*4):
        ce = ce_gaps(recommend, mu); cce = cce_gaps(recommend, mu)
        audit.equal(cce, (ce[1], ce[0], ce[3], ce[2]), 'binary CCE equals the reverse-target CE comparisons')
    audit.interventions += 1

    invalid = [
        (lambda: exact(True), 'bool utility'), (lambda: exact(float('nan')), 'NaN'),
        (lambda: exact(float('inf')), 'infinity'), (lambda: exact(1000001), 'magnitude cap'),
        (lambda: probability((F(1, 2), F(1, 3))), 'probability sum'),
        (lambda: probability((-1, 2)), 'negative probability'),
        (lambda: probability((1,), 2), 'probability dimension'),
        (lambda: game(()), 'empty game'), (lambda: game((((1, 2),), ((1, 2), (3, 4)))), 'jagged game'),
        (lambda: game((((1,),),)), 'missing player payoff'),
        (lambda: game((((1, 2, 3),),)), 'extra player payoff'),
        (lambda: strict_corner_equilibria(weak), 'continuum outside strict-corner classifier'),
        (lambda: constrained_bound((1, 2), (F(1, 2), F(1, 2))), 'floors exhaust simplex'),
        (lambda: constrained_bound((1, 2), (0, F(1, 10))), 'nonpositive floor'),
        (lambda: constrained_bound((1, 2), (F(1, 10),)), 'floor dimensions'),
        (lambda: reverse_floors((1, 0), (1, 0), 10), 'non-full tremble'),
        (lambda: reverse_floors((1, 0), (F(1, 2), F(1, 2)), 0), 'sequence index'),
        (lambda: reverse_floors((1, 0), (1,), 10), 'limit/tremble dimensions'),
        (lambda: entry_coefficients((1, 0, 0, 0)), 'null own-type marginal'),
        (lambda: entry_outcome(independent, (1, 0, 2, 0)), 'invalid type strategy'),
        (lambda: entry_outcome(independent, (1, 0)), 'missing type strategy'),
        (lambda: payoff(recommend, (1, 0)), 'joint dimension'),
        (lambda: deviation_value(cyclic, diagonal, 0, (1, 2)), 'contingent rule dimension'),
        (lambda: deviation_value(cyclic, diagonal, 0, (1, 2, 3)), 'out of range contingent action'),
        (lambda: deviation_value(cyclic, diagonal, True, (1, 2, 0)), 'bool player'),
        (lambda: conditional_values(recommend, (1, 0, 0, 0), 0, 1, 0), 'null recommendation division'),
        (lambda: conditional_values(recommend, optimum, 0, 2, 0), 'recommendation index'),
        (lambda: ce_vertices(cyclic), 'vertex enumeration outside bounded 2x2 scope')]
    for call, label in invalid: audit.reject(call, label)
    for text in ('{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}'):
        audit.reject(lambda text=text: strict_json(text), 'strict JSON')
    for text in ('True', '1/0', '__import__("os")', '(1,2)+(3,4)'):
        audit.reject(lambda text=text: expression(text), 'restricted numeric expression')
    return inputs, result, vertex_counts


def check(root=None):
    base = Path(root) if root is not None else Path(__file__).resolve().parents[1]
    audit = Audit()
    review = strict_json((base/REVIEW).read_text(encoding='utf-8'))
    sources = strict_json((base/SOURCES).read_text(encoding='utf-8'))
    bindings = review['payload_bindings']
    audit.equal({b['path'] for b in bindings}, {HTML, SELF, SOURCES}, 'three nonself bindings')
    audit.equal(len(bindings), 3, 'binding cardinality')
    for binding in bindings:
        raw = (base/binding['path']).read_bytes()
        audit.equal((len(raw), hashlib.sha256(raw).hexdigest()), (binding['bytes'], binding['sha256']), 'frozen payload '+binding['path'])
    inputs, expected, vertex_counts = derive(audit)
    page = Page(); page.feed((base/HTML).read_text(encoding='utf-8')); page.close()
    audit.equal(page.stack, [], 'balanced full HTML fragment')
    audit.equal(len(page.ids), len(set(page.ids)), 'unique IDs')
    audit.true(all(i.startswith('v13-c06-') for i in page.ids), 'chapter namespace')
    audit.equal(page.worked, [f'v13-c06-case{i}' for i in range(1, 7)], 'six complete worked cases')
    prompts = [f'v13-c06-ex{i}' for i in range(1, 13)]
    audit.equal(page.exercises, prompts, 'all twelve prompts')
    audit.equal(page.solutions, prompts, 'twelve reader-recognized exact solution pairings')
    audit.true('h1' not in page.headings, 'no extra page title')
    audit.equal(page.inputs, inputs, 'all declared original input markers')
    audit.equal(set(page.calcs), set(expected), 'complete visible result inventory')
    for name, value in expected.items(): audit.equal(page.calcs[name], value, 'independent numerical result '+name)
    citations = {
        'v13-c06-yildiz-games2022':'https://ocw.mit.edu/courses/14.126-game-theory-spring-2024/mit14_126_s24_yildiz-lecture-notes.pdf',
        'v13-c06-manea-noncoop2017':'https://ocw.mit.edu/courses/14-126-game-theory-spring-2016/a4d0a3949ab29c2a2f55442a9723d205_MIT14_126S16_noncoop.pdf',
        'v13-c06-roughgarden2013-equilibria':'https://www.timroughgarden.org/f13/l/l13.pdf'}
    audit.equal(dict(page.sources), citations, 'exact primary citation URLs')
    audit.equal({s['id']:s['url'] for s in sources['sources']}, citations, 'source record citation match')
    audit.true(all(s['actual_inspector'] == 'c05_review' for s in sources['sources']), 'actual primary body inspector')
    audit.equal(sum(len(s['images_inspected']) for s in sources['sources']), 6, 'six specifically inspected page images')
    audit.true(all(not link.startswith(('production/', 'chapters/', 'projects/')) for link in page.links), 'flat reader links')
    for anchor in ('teach-answer','retention-answer','sources','solutions','nash','perfection','bayesian','correlated','coarse'):
        audit.true('v13-c06-'+anchor in page.ids, 'instruction/proof component '+anchor)
    audit.equal(set(review['proof_audit']), {f'P{i}' for i in range(1, 7)}, 'all six proof audits')
    audit.equal(set(review['exercise_audit']), set(prompts), 'every exact exercise audited')
    audit.equal(review['unresolved_findings'], [], 'no unresolved author finding')
    summary = {'chapter':'v13-c06','status':'author checks passed; acceptance recorded separately',
               'comparisons':audit.comparisons,'domain_rejections':audit.rejections,'intervention_groups':audit.interventions,
               'worked_cases':6,'solved_exercises':12,'primitive_markers':len(inputs),'result_markers':len(expected),
               'bayesian_support_patterns':81,'bayesian_baseline_equilibria':5,'ce_vertex_counts':vertex_counts,
               'ternary_deviation_maps_per_player':27,'proof_contracts':6,'runtime_payloads':4}
    json.dumps(summary, allow_nan=False)
    return summary


if __name__ == '__main__':
    check()
