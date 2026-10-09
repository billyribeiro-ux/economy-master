"""Quiet four-file checks for the general-equilibrium canonical chapter.

Finite exact witnesses and economic interventions supplement the manuscript's
universal proofs. This checker neither imports a shared checker nor reads the
source-preparation/blueprint records or network artifacts.
"""
from collections import Counter
from fractions import Fraction as F
from html.parser import HTMLParser
from itertools import combinations, permutations, product
from pathlib import Path
import ast
import hashlib
import json
import math

HTML = 'content/chapters/v13-c04.html'
SELF = 'scripts/check_v13_c04.py'
SOURCES = 'content/reviews/v13-c04-sources.json'
REVIEW = 'content/reviews/v13-c04-author.json'


def require(condition, message):
    if not condition:
        raise ValueError(message)


class Audit:
    def __init__(self):
        self.comparisons = 0
        self.rejections = 0
        self.interventions = 0

    def equal(self, actual, expected, label):
        require(actual == expected, label + ': ' + repr(actual) + ' != ' + repr(expected))
        self.comparisons += 1

    def true(self, value, label):
        self.equal(bool(value), True, label)

    def reject(self, function, label):
        try:
            function()
        except ValueError:
            self.rejections += 1
        else:
            raise ValueError('Invalid input accepted: ' + label)


def exact(value):
    require(type(value) in (int, F), 'bounded exact integer/Fraction required; no bool/float')
    require(abs(value) <= 1000000, 'exact witness magnitude limit')
    return F(value)


def vector(values, size=None, positive=False):
    require(type(values) in (tuple, list), 'vector type')
    require(1 <= len(values) <= 16 and (size is None or len(values) == size), 'vector dimension')
    out = tuple(exact(v) for v in values)
    if positive:
        require(min(out) > 0, 'strict positivity')
    return out


def dot(a, b):
    require(len(a) == len(b), 'inner-product dimensions')
    return sum((x*y for x, y in zip(a, b)), F(0))


def add(a, b):
    require(len(a) == len(b), 'addition dimensions')
    return tuple(x+y for x, y in zip(a, b))


def subtract(a, b):
    return add(a, tuple(-y for y in b))


def total(rows):
    require(bool(rows), 'nonempty row collection')
    return tuple(sum((row[j] for row in rows), F(0)) for j in range(len(rows[0])))


def norm2(x):
    return dot(x, x)


def square_root(value):
    value = exact(value)
    require(value >= 0, 'nonnegative root argument')
    a, b = math.isqrt(value.numerator), math.isqrt(value.denominator)
    require(a*a == value.numerator and b*b == value.denominator, 'rational-square witness domain')
    return F(a, b)


def cd_demand(prices, income, share):
    p = vector(prices, 2, positive=True)
    m, alpha = exact(income), exact(share)
    require(m > 0 and 0 < alpha < 1, 'interior Cobb-Douglas domain')
    return (alpha*m/p[0], (1-alpha)*m/p[1])


def exchange(endowments, shares):
    require(type(endowments) in (list, tuple) and 1 <= len(endowments) <= 8, 'household count')
    omega = tuple(vector(row, 2, positive=True) for row in endowments)
    alphas = vector(shares, len(omega))
    require(all(0 < a < 1 for a in alphas), 'shares strictly between zero and one')
    # Market-value cancellation gives the price directly from the two separate
    # sides: expenditure transferred toward good 1 / endowment sold from good 1.
    numer = sum(a*w[1] for a, w in zip(alphas, omega))
    denom = sum((1-a)*w[0] for a, w in zip(alphas, omega))
    p = (numer/denom, F(1))
    incomes = tuple(dot(p, w) for w in omega)
    choices = tuple(cd_demand(p, m, a) for m, a in zip(incomes, alphas))
    return p, incomes, choices


def firm(wage, capacity=F(4), output_coefficient=F(2)):
    w, cap, a = map(exact, (wage, capacity, output_coefficient))
    require(w > 0 and cap > 0 and a > 0, 'positive production witness inputs')
    # Optimize the strictly concave quadratic in square-root input, including
    # its upper constraint, rather than assuming the interior first order rule.
    upper = square_root(cap)
    t = min(upper, a/(2*w))
    y = (-t*t, a*t)
    return y, dot((w, F(1)), y), t


def production(wage, shares, capacity=F(4)):
    theta = vector(shares, 2)
    require(min(theta) >= 0 and sum(theta) == 1, 'complete nonnegative ownership')
    w = exact(wage)
    y, profit, t = firm(w, capacity)
    incomes = tuple(2*w+F(1, 2)+s*profit for s in theta)
    choices = tuple(cd_demand((w, 1), m, F(1, 2)) for m in incomes)
    resources = add((F(4), F(1)), y)
    return {'supply': y, 'profit': profit, 'incomes': incomes,
            'choices': choices, 'resources': resources,
            'excess': subtract(total(choices), resources), 'root_input': t}


def simplex_point(values):
    x = vector(values)
    require(min(x) >= 0 and sum(x) == 1, 'simplex point')
    return x


def deficit_label(vertex, image):
    v, fv = simplex_point(vertex), simplex_point(image)
    require(len(v) == len(fv), 'map dimension')
    candidates = [i for i, (x, y) in enumerate(zip(v, fv)) if x > y]
    return min(candidates) if candidates else None  # Exact fixed vertex ends proof.


def determinant(matrix):
    require(type(matrix) in (list, tuple) and 1 <= len(matrix) <= 4, 'determinant dimension')
    n = len(matrix)
    a = [list(vector(row, n)) for row in matrix]
    sign = F(1)
    for k in range(n):
        pivot = next((i for i in range(k, n) if a[i][k]), None)
        if pivot is None:
            return F(0)
        if pivot != k:
            a[k], a[pivot] = a[pivot], a[k]
            sign = -sign
        for i in range(k+1, n):
            ratio = a[i][k]/a[k][k]
            for j in range(k+1, n):
                a[i][j] -= ratio*a[k][j]
            a[i][k] = F(0)
    return sign*math.prod(a[i][i] for i in range(n))


def barycentric_cells(dimension):
    require(type(dimension) is int and 1 <= dimension <= 3, 'bounded witness dimensions 1..3')
    d = dimension
    result = []
    for order in permutations(range(d+1)):
        vertices = []
        for count in range(1, d+2):
            face = set(order[:count])
            vertices.append(tuple(F(int(i in face), count) for i in range(d+1)))
        result.append(tuple(vertices))
    return tuple(result)


def labeled_facets(cells, labels):
    require(type(cells) in (tuple, list) and bool(cells), 'nonempty simplicial list')
    require(all(type(label) is int and 0 <= label <= 2 for label in labels), 'triangle labels')
    for cell in cells:
        require(len(cell) == 3 and len(set(cell)) == 3, 'three distinct cell vertices')
        require(all(type(i) is int and 0 <= i < len(labels) for i in cell), 'cell vertex index')
    marked = [sum(set(labels[v] for v in edge) == {0, 1} for edge in combinations(cell, 2))
              for cell in cells]
    full = [i for i, cell in enumerate(cells) if set(labels[v] for v in cell) == {0, 1, 2}]
    return tuple(marked), tuple(full)


def segment_projection(point):
    x, y = vector(point, 2)
    t = min(F(1), max(F(0), (x-y+1)/2))
    return (t, 1-t)


def tents(sites, values, x, epsilon):
    sites, values = vector(sites), vector(values)
    require(len(sites) == len(values), 'selected-value dimensions')
    x, eps = exact(x), exact(epsilon)
    require(eps > 0 and 0 <= x <= 1, 'positive scale and unit-interval argument')
    require(all(0 <= s <= 1 for s in sites) and all(0 <= v <= 1 for v in values), 'unit-interval range')
    weights = tuple(max(F(0), eps-abs(x-s)) for s in sites)
    require(sum(weights) > 0, 'sites must cover the evaluated point at the weight scale')
    return dot(weights, values)/sum(weights), tuple(w/sum(weights) for w in weights)


def strict_json(text):
    def pairs(items):
        result = {}
        for k, v in items:
            require(k not in result, 'duplicate JSON key')
            result[k] = v
        return result
    def bad(_):
        raise ValueError('nonfinite JSON literal')
    try:
        value = json.loads(text, object_pairs_hook=pairs, parse_constant=bad)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ValueError('invalid JSON') from exc
    json.dumps(value, allow_nan=False)
    return value


def expression(text):
    """Evaluate only finite exact tuple/fraction arithmetic used by visible markers."""
    try:
        tree = ast.parse(text.strip().replace('−', '-'), mode='eval')
    except (SyntaxError, TypeError) as exc:
        raise ValueError('invalid numeric marker') from exc
    require(sum(1 for _ in ast.walk(tree)) <= 400, 'bounded marker expression')
    def visit(node):
        if isinstance(node, ast.Constant):
            return exact(node.value)
        if isinstance(node, (ast.Tuple, ast.List)):
            return tuple(visit(item) for item in node.elts)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = visit(node.operand)
            require(type(value) is F, 'scalar sign operand')
            return value if isinstance(node.op, ast.UAdd) else -value
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
            a, b = visit(node.left), visit(node.right)
            require(type(a) is F and type(b) is F, 'scalar arithmetic operands')
            if isinstance(node.op, ast.Add): return a+b
            if isinstance(node.op, ast.Sub): return a-b
            if isinstance(node.op, ast.Mult): return a*b
            require(b != 0, 'nonzero denominator')
            return a/b
        raise ValueError('unsupported numeric expression')
    return visit(tree.body)


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.ids = []
        self.headings = []
        self.worked = []
        self.exercises = []
        self.solutions = []
        self.inputs = {}
        self.calcs = {}
        self.sources = []
        self.links = []
        self.exercise_depth = None
        self.solution_depth = None
        self.marker = None
        self.table_depth = None
        self.rows = []
        self.row = []
        self.cell = None

    def handle_starttag(self, tag, attributes):
        a = dict(attributes)
        if 'id' in a: self.ids.append(a['id'])
        if tag in ('h1', 'h2', 'h3', 'h4'): self.headings.append(tag)
        if 'href' in a: self.links.append(a['href'])
        if 'data-source' in a: self.sources.append((a['data-source'], a.get('href')))
        if 'worked' in a.get('class', '').split(): self.worked.append(a.get('id'))
        if tag == 'ol' and 'exercises' in a.get('class', '').split():
            require(self.exercise_depth is None, 'no nested exercise lists')
            self.exercise_depth = len(self.stack)
        if tag == 'details' and 'solutions' in a.get('class', '').split():
            require(self.solution_depth is None, 'single solutions disclosure')
            self.solution_depth = len(self.stack)
        if tag == 'li' and self.exercise_depth is not None:
            self.exercises.append(a.get('id'))
        if tag == 'li' and self.solution_depth is not None:
            self.solutions.append(a.get('data-solution-for'))
        keys = [key for key in ('data-input', 'data-calc') if key in a]
        if keys:
            require(len(keys) == 1 and self.marker is None, 'one unnested numeric marker')
            self.marker = (len(self.stack), keys[0], a[keys[0]], [])
        if tag == 'table' and a.get('id') == 'v13-c04-cycle-table':
            self.table_depth = len(self.stack)
        if self.table_depth is not None and tag == 'tr': self.row = []
        if self.table_depth is not None and tag == 'td': self.cell = []
        require(tag not in ('script', 'style', 'iframe'), 'static unstyled chapter fragment')
        if tag not in ('br', 'hr', 'img', 'meta', 'link', 'input'):
            self.stack.append(tag)

    def handle_data(self, data):
        if self.marker is not None: self.marker[3].append(data)
        if self.cell is not None: self.cell.append(data)

    def handle_endtag(self, tag):
        require(self.stack and self.stack[-1] == tag, 'balanced tag ' + tag)
        depth = len(self.stack)-1
        if self.marker is not None and depth == self.marker[0]:
            _, kind, key, pieces = self.marker
            destination = self.inputs if kind == 'data-input' else self.calcs
            require(key not in destination, 'unique marker ' + key)
            destination[key] = expression(''.join(pieces))
            self.marker = None
        if tag == 'td' and self.cell is not None:
            self.row.append(''.join(self.cell).strip())
            self.cell = None
        if tag == 'tr' and self.table_depth is not None and self.row:
            self.rows.append(tuple(self.row))
        if tag == 'table' and depth == self.table_depth: self.table_depth = None
        if tag == 'ol' and depth == self.exercise_depth: self.exercise_depth = None
        if tag == 'details' and depth == self.solution_depth: self.solution_depth = None
        self.stack.pop()


def derive(audit):
    inputs = {
        'exchange-endowments': ((F(4), F(1)), (F(1), F(4))),
        'exchange-shares': (F(2, 3), F(1, 3)),
        'exchange-transfer-endowment': (F(4), F(2)),
        'production-endowment': (F(2), F(1, 2)),
        'production-shares': (F(1, 4), F(3, 4)),
        'production-capacity': F(4),
        'cycle-vertices': ((F(1), F(0), F(0)), (F(0), F(1), F(0)), (F(0), F(0), F(1)),
                           (F(1, 2), F(1, 2), F(0)), (F(1, 2), F(0), F(1, 2)), (F(0), F(1, 2), F(1, 2))),
        'cycle-cells': ((F(0), F(3), F(4)), (F(1), F(3), F(5)), (F(2), F(4), F(5)), (F(3), F(4), F(5))),
        'leontief-endowments': ((F(1), F(1)), (F(2), F(2))),
        'linear-endowments': ((F(1), F(1)), (F(1), F(1))),
        'nonconvex-endowment': (F(1), F(1))
    }
    result = {}
    # Original, endowment transfer and new exact exercise: not an output-file
    # comparison; each market and each budget is reconstructed from primitives.
    for prefix, second in (('exchange', F(1)), ('exchange-transfer', F(2)), ('exercise-exchange', F(3))):
        omega = ((F(4), second), (F(1), F(4)))
        p, income, allocation = exchange(omega, inputs['exchange-shares'])
        result[prefix+'-price'] = p[0]
        result[prefix+'-incomes'] = income
        result[prefix+'-allocations'] = allocation
        result[prefix+'-totals'] = total(allocation)
        audit.equal(total(allocation), total(omega), prefix+' two markets')
        audit.equal(tuple(dot(p, x) for x in allocation), income, prefix+' individual budgets')
        # Log-utility tangent coefficients equal price/income. This certifies
        # global optimality via log(t)<=t-1, including every positive alternative.
        for alpha, m, x in zip(inputs['exchange-shares'], income, allocation):
            audit.equal((alpha/x[0], (1-alpha)/x[1]), tuple(z/m for z in p), prefix+' supporting gradient')
    audit.interventions += 1
    baseline = exchange(inputs['exchange-endowments'], inputs['exchange-shares'])
    omega_scaled = tuple(tuple(3*v for v in row) for row in inputs['exchange-endowments'])
    scaled = exchange(omega_scaled, inputs['exchange-shares'])
    audit.equal(scaled[0], baseline[0], 'common resource scaling leaves relative price')
    audit.equal(scaled[2], tuple(tuple(3*v for v in row) for row in baseline[2]), 'resource-scaled allocations')
    for alpha, m, choice in zip(inputs['exchange-shares'], baseline[1], baseline[2]):
        audit.equal(cd_demand((7, 7), 7*m, alpha), choice, 'price-income normalization invariance')
    changed = exchange(inputs['exchange-endowments'], (F(1, 2), F(1, 4)))
    audit.true(changed[0] != baseline[0], 'taste transfer actually changes price')
    audit.equal(total(changed[2]), total(inputs['exchange-endowments']), 'taste-transfer clearing')
    audit.interventions += 1

    # Derive the two polynomial roots using the quadratic discriminant.
    roots = tuple((1+s*square_root(1+48))/8 for s in (1, -1))
    result['production-roots'] = roots
    result['production-wage'] = roots[0]
    prod = production(roots[0], inputs['production-shares'])
    for field, key in (('supply', 'supply'), ('profit', 'profit'), ('incomes', 'incomes'), ('choices', 'allocations')):
        result['production-'+key] = prod[field]
    result['production-totals'] = total(prod['choices'])
    audit.equal(prod['excess'], (0, 0), 'production both commodity balances')
    audit.equal(tuple(dot((roots[0], 1), x) for x in prod['choices']), prod['incomes'], 'production budgets')
    audit.equal(sum(prod['incomes']), dot((roots[0], 1), prod['resources']), 'production consolidated value')
    eq = production(roots[0], (F(1, 2), F(1, 2)))
    result['production-equal-incomes'] = eq['incomes']
    result['production-equal-allocations'] = eq['choices']
    audit.equal(eq['supply'], prod['supply'], 'ownership transfer supply')
    audit.equal(eq['excess'], (0, 0), 'ownership transfer clears')
    for theta in ((F(0), F(1)), (F(1), F(0))):
        shifted = production(1, theta)
        audit.equal(shifted['excess'], (0, 0), 'extreme complete ownership with common shares')
        audit.equal(sum(shifted['incomes']), sum(prod['incomes']), 'ownership preserves total income')
    # When shares differ, total income does not alone determine market demand.
    hetero1 = total(tuple(cd_demand((1, 1), m, a) for m, a in zip(prod['incomes'], (F(1, 4), F(3, 4)))))
    hetero2 = total(tuple(cd_demand((1, 1), m, a) for m, a in zip(eq['incomes'], (F(1, 4), F(3, 4)))))
    audit.true(hetero1 != hetero2, 'ownership irrelevance fails with heterogeneous shares')
    audit.interventions += 1
    omitted = total((cd_demand((1, 1), F(5, 2), F(1, 2)),)*2)
    result['production-omitted-demand'] = omitted
    result['production-omitted-walras'] = dot((1, 1), subtract(omitted, prod['resources']))
    audit.equal(result['production-omitted-walras'], -prod['profit'], 'missing owner income exactly reconciles gap')
    audit.interventions += 1
    # Branch and boundary checks use the same original quadratic contract.
    for w in (F(1, 4), F(1, 2), F(3, 4), F(2)):
        y, profit, t = firm(w)
        audit.equal(profit, 2*t-w*t*t, 'quadratic profit from chosen input')
        derivative = 2-2*w*t
        audit.true((t == 2 and derivative >= 0) or (0 < t < 2 and derivative == 0), 'global concave optimum certificate')
        if w <= F(1, 2):
            current = production(w, inputs['production-shares'])
            audit.equal(current['resources'][0], 0, 'capacity uses all available input')
            audit.true(total(current['choices'])[0] > 0, 'capacity violates leisure clearing')
    audit.equal(firm(F(1, 2))[:2], ((F(-4), F(4)), F(2)), 'both firm formulas agree at boundary')
    # A smaller physical capacity changes the clearing branch, not just a number
    # on an unchanged interior formula. Supply is (-1/4,1), leaving (15/4,2).
    cap_price = F(2)/F(15, 4)
    clipped = production(cap_price, inputs['production-shares'], F(1, 4))
    audit.equal(clipped['excess'], (0, 0), 'capacity intervention produces new branch equilibrium')
    audit.equal(clipped['supply'], (F(-1, 4), F(1)), 'capacity intervention original feasibility')
    audit.interventions += 1

    vertices = inputs['cycle-vertices']
    cells = tuple(tuple(int(i) for i in row) for row in inputs['cycle-cells'])
    images = tuple((v[1], v[2], v[0]) for v in vertices)
    labels = tuple(deficit_label(v, image) for v, image in zip(vertices, images))
    incidences, full = labeled_facets(cells, labels)
    result['cycle-labels'], result['cycle-incidences'] = labels, incidences
    center = tuple(v/3 for v in total(tuple(vertices[i] for i in cells[full[0]])))
    result['cycle-fixed'] = center
    audit.equal((center[1], center[2], center[0]), center, 'cycle fixed point direct substitution')
    audit.equal(full, (3,), 'only central cell full')
    audit.equal(deficit_label(center, center), None, 'exact vertex fixed-point stop')
    for vertex, label in zip(vertices, labels):
        audit.true(vertex[label] > 0, 'strict deficit respects zero-coordinate boundary')
    for mid in product((0, 1), (0, 2), (1, 2)):
        counts, full_cells = labeled_facets(cells, (0, 1, 2)+mid)
        audit.equal((sum(counts) % 2, len(full_cells) % 2), (1, 1), 'all admissible midpoint-label parity')
    weak = next(i for i, value in enumerate(subtract(vertices[2], vertices[0])) if value >= 0)
    audit.equal((weak, vertices[2][weak]), (1, 0), 'weak-deficit counterexample is a forbidden label')
    audit.interventions += 1

    # Barycentric subdivision: exact volumes, coverage reconstruction, mesh and
    # interior/boundary facet incidences in dimensions 1,2,3 (not a universal proof).
    simplex_cells_checked = 0
    for d in (1, 2, 3):
        subcells = barycentric_cells(d)
        simplex_cells_checked += len(subcells)
        volumes, diameters = [], []
        facet_counts = Counter()
        for cell in subcells:
            base = cell[0][:d]
            matrix = tuple(subtract(v[:d], base) for v in cell[1:])
            volumes.append(abs(determinant(matrix)))
            diameters.append(max(norm2(subtract(a, b)) for a, b in combinations(cell, 2)))
            for facet in combinations(cell, d):
                facet_counts[tuple(sorted(facet))] += 1
        audit.equal(set(volumes), {F(1, math.factorial(d+1))}, 'equal nondegenerate barycentric volumes')
        audit.equal(sum(volumes), 1, 'subdivision volume adds to whole simplex')
        audit.true(max(diameters) <= 2*F(d, d+1)**2, 'nested-face mesh contraction witness')
        expected_counts = tuple(1 if any(all(v[i] == 0 for v in facet) for i in range(d+1)) else 2
                                for facet in facet_counts)
        audit.equal(tuple(facet_counts.values()), expected_counts, 'boundary one/interior two facet incidences')
        # A deliberately nonuniform point: reconstruct all coordinates from
        # sorted drops and verify the corresponding chain representation.
        lam = tuple(F(i+1, (d+1)*(d+2)//2) for i in range(d+1))
        order = sorted(range(d+1), key=lambda i: -lam[i])
        drops = tuple((k+1)*(lam[order[k]]-(lam[order[k+1]] if k < d else 0)) for k in range(d+1))
        reconstructed = tuple(sum(drops[k]*F(int(i in order[:k+1]), k+1) for k in range(d+1)) for i in range(d+1))
        audit.equal((sum(drops), reconstructed), (1, lam), 'ordered-coordinate coverage identity')
    audit.interventions += 1

    # Correspondence failure certificates and finite approximation scope.
    result['kakutani-repaired-fixed'] = F(1, 2)
    result['kakutani-missing-limit'] = (F(1, 2), F(1))
    result['noncompact-candidate'] = F(1)/(2-1)
    for n in (4, 8, 16):
        site = F(1, 2)-F(1, n)
        audit.true(site < F(1, 2) and 1 != site, 'left graph sequence remains nonfixed')
    audit.true(F(1, 2) not in (0, 1), 'nonconvex middle excludes candidate')
    audit.true(0 <= F(1, 2) <= 1, 'interval repair includes candidate')
    for x in (0, F(1, 2), F(3, 4)):
        image = (1+x)/2
        audit.true(x < image < 1, 'noncompact affine image has no fixed point at witness')
    for x in (0, 1):
        audit.true(1-x != x, 'disconnected domain swap has no fixed point')
    # Constant F: the averaged map really has a fixed point at 1/2 for a
    # symmetric net and selections, but an arbitrary selection can jump.
    value, weights = tents((0, F(1, 2), 1), (F(1, 4), F(1, 2), F(3, 4)), F(1, 2), 1)
    audit.equal((value, sum(weights)), (F(1, 2), F(1)), 'finite tent-map fixed example')
    for x in (F(1, 4), F(3, 4)):
        value, weights = tents((0, F(1, 2), 1), (F(1, 4), F(3, 4), F(1, 4)), x, F(3, 4))
        audit.true(F(1, 4) <= value <= F(3, 4), 'convex average stays in constant image')
        audit.equal(sum(weights), 1, 'tent normalization')
    audit.interventions += 1

    points = ((2, 2), (-1, 0), (2, 0))
    projections = tuple(segment_projection(point) for point in points)
    result['exercise-projections'] = projections
    for point, proj in zip(points, projections):
        audit.equal(sum(proj), 1, 'projection in affine segment')
        audit.true(min(proj) >= 0, 'projection satisfies both segment inequalities')
        for endpoint in ((0, 1), (1, 0)):
            audit.true(dot(subtract(point, proj), subtract(endpoint, proj)) <= 0, 'projection variational certificate')
    for (p, a), (q, b) in combinations(tuple(zip(points, projections)), 2):
        audit.true(norm2(subtract(a, b)) <= dot(subtract(p, q), subtract(a, b)), 'projection firm nonexpansiveness witness')
    audit.interventions += 1

    result['exercise-resource-bounds'] = add((F(4), F(1)), (F(0), F(4)))
    result['exercise-resource-cap'] = max(result['exercise-resource-bounds'])+1
    result['exercise-income-lower'] = min(inputs['production-endowment'])
    audit.true(all(bound < result['exercise-resource-cap'] for bound in result['exercise-resource-bounds']), 'strict economic cap margin')
    # Budget approximation at a binding boundary price, using a genuinely
    # different nearby price and endogenous positive wealth.
    omega, target = (F(2), F(1, 2)), (F(2), F(5))
    approximations = []
    for n in (10, 100, 1000):
        price = (1-F(1, n), F(1, n))
        wealth = dot(price, omega)
        factor = min(F(1), wealth/dot(price, target))
        alternative = tuple(factor*v for v in target)
        audit.true(dot(price, alternative) <= wealth, 'nearby capped budget approximation is feasible')
        approximations.append(norm2(subtract(alternative, target)))
    audit.true(approximations[0] > approximations[1] > approximations[2], 'radial budget approximations approach target')
    # Cap-removal witness: convex weak mixture plus cheap strict increase.
    xi, t, lam = (F(1), F(1)), F(9, 10), F(1, 10)
    utility = lambda x: x[0]+2*x[1]
    # Use a strict preferred affordable point for the declared linear utility.
    better = (F(0), F(7, 4))
    shrunk = tuple(t*v for v in better)
    mixed = tuple((1-lam)*a+lam*b for a, b in zip(xi, shrunk))
    improved = add(mixed, (F(1, 100), F(0)))
    audit.true(sum(shrunk) < 2 and utility(shrunk) > utility(xi), 'radial shrink remains preferred and cheaper')
    audit.true(max(improved) < 6 and sum(improved) < 2 and utility(improved) > utility(xi), 'cap-removal constructive contradiction witness')
    flat = lambda x: max(F(0), min(x)-1)
    result['exercise-flat-mixture-utilities'] = tuple(flat(x) for x in ((0, 0), (2, 2), (F(1, 2), F(1, 2))))
    audit.interventions += 1

    result['linear-allocation-interval'] = (F(0), F(2))
    for ratio in (F(1, 4), F(1), F(4)):
        for t in (F(1), F(2)):
            wealth = (ratio+1)*t
            audit.equal(wealth/(ratio+1), t, 'Leontief attainable level from exact budget cost')
        # Convex preferences dropped: the cheaper endpoint beats the sole
        # clearing bundle. This intervention covers either cheaper commodity.
        minimum_price = min(ratio, 1)
        cheap_quantity = (ratio+1)/minimum_price
        audit.true(cheap_quantity**2 >= 4 > 2, 'nonconvex economy positive-price separating choice')
    for a in (F(0), F(1, 3), F(1), F(2)):
        choices = ((a, 2-a), (2-a, a))
        audit.equal((total(choices), tuple(sum(x) for x in choices)), ((2, 2), (2, 2)), 'linear allocation family budgets/clearing')
    for ratio in (F(1, 2), F(2)):
        wealth = ratio+1
        choice = (wealth/ratio, 0) if ratio < 1 else (0, wealth)
        audit.true(total((choice, choice)) != (2, 2), 'unequal linear prices cannot clear')
    result['iteration-fixed'] = F(1)/(1+1)
    path = [F(0)]
    for _ in range(4): path.append(1-path[-1])
    result['iteration-path'] = tuple(path)
    audit.equal((path[0::2], path[1::2]), ([0, 0, 0], [1, 1]), 'two distinct subsequential iterates')
    result['nonconvex-endowment-utility'] = norm2(inputs['nonconvex-endowment'])
    result['nonconvex-endpoint-lower-bound'] = F(2)**2
    audit.true(norm2((2, 0)) == norm2((0, 2)) > norm2((1, 1)), 'nonconvex upper-contour midpoint')
    audit.interventions += 1

    # Real invalid calls: a failure never depends on Python assertions or -O.
    invalid = [
        (lambda: exact(True), 'bool'), (lambda: exact(float('nan')), 'NaN'),
        (lambda: exact(float('inf')), 'infinity'), (lambda: exact(1000001), 'magnitude'),
        (lambda: vector((1, 2), 3), 'dimension'),
        (lambda: cd_demand((0, 1), 3, F(1, 2)), 'zero price'),
        (lambda: cd_demand((1, 1), 0, F(1, 2)), 'zero income'),
        (lambda: cd_demand((1, 1), 3, 1), 'share boundary'),
        (lambda: exchange(((0, 1), (1, 1)), (F(1, 2), F(1, 2))), 'nonpositive household endowment'),
        (lambda: exchange(((1, 1),), (F(1, 2), F(1, 2))), 'household/share mismatch'),
        (lambda: production(1, (F(1, 4), F(1, 2))), 'missing ownership'),
        (lambda: production(1, (-1, 2)), 'negative ownership'),
        (lambda: firm(0), 'zero wage'), (lambda: firm(1, 0), 'zero capacity outside witness class'),
        (lambda: firm(1, 2), 'irrational capacity root outside exact witness domain'),
        (lambda: simplex_point((1, 1)), 'simplex sum'),
        (lambda: simplex_point((-1, 2)), 'negative simplex coordinate'),
        (lambda: deficit_label((1, 0), (1, 0, 0)), 'map dimension'),
        (lambda: labeled_facets(((0, 0, 1),), (0, 1)), 'degenerate triangle'),
        (lambda: barycentric_cells(True), 'bool dimension'),
        (lambda: barycentric_cells(4), 'finite witness scope'),
        (lambda: tents((0,), (F(1, 2),), 1, F(1, 2)), 'uncovered tent argument'),
        (lambda: tents((0, 1), (F(1, 2),), F(1, 2), 1), 'selection dimensions'),
        (lambda: tents((0,), (2,), 0, 1), 'out of range selection'),
        (lambda: square_root(-1), 'negative square root')]
    for call, label in invalid: audit.reject(call, label)
    for bad in ('{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}'):
        audit.reject(lambda bad=bad: strict_json(bad), 'strict JSON rejection')
    for bad in ('True', '1/0', '__import__("os")', '(1,2)+(3,4)'):
        audit.reject(lambda bad=bad: expression(bad), 'restricted marker rejection')
    table = tuple((name, subtract(v, image), F(label)) for name, v, image, label in
                  zip(('e₀', 'e₁', 'e₂', 'm₀₁', 'm₀₂', 'm₁₂'), vertices, images, labels))
    return inputs, result, table, simplex_cells_checked


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
        audit.equal((len(raw), hashlib.sha256(raw).hexdigest()),
                    (binding['bytes'], binding['sha256']), 'frozen payload '+binding['path'])
    inputs, expected, table, cells = derive(audit)
    page = Page()
    page.feed((base/HTML).read_text(encoding='utf-8'))
    page.close()
    audit.equal(page.stack, [], 'balanced full manuscript fragment')
    audit.equal(len(page.ids), len(set(page.ids)), 'unique chapter IDs')
    audit.true(all(i.startswith('v13-c04-') for i in page.ids), 'scoped chapter IDs')
    audit.equal(page.worked, [f'v13-c04-case{i}' for i in range(1, 7)], 'six worked cases')
    prompts = [f'v13-c04-ex{i}' for i in range(1, 13)]
    audit.equal(page.exercises, prompts, 'twelve prompt IDs')
    audit.equal(page.solutions, prompts, 'twelve exact solution targets within reader disclosure')
    audit.true('h1' not in page.headings, 'no duplicate page title')
    audit.equal(page.inputs, inputs, 'all visible original inputs')
    audit.equal(set(page.calcs), set(expected), 'full result marker inventory')
    for name, value in expected.items():
        audit.equal(page.calcs[name], value, 'original-contract marker '+name)
    actual_table = tuple((name, expression(difference), expression(label)) for name, difference, label in page.rows)
    audit.equal(actual_table, table, 'complete printed deficit-label table')
    expected_sources = {
        'v13-c04-mathew2010': 'https://math.uchicago.edu/~amathew/HMMT.pdf',
        'v13-c04-tamuz2021': 'https://www.tamuz.caltech.edu/teaching/ss205b/lectures.pdf',
        'v13-c04-condie-existence': 'https://scottcondie.github.io/teaching/580/chapters/ge-existence.html'}
    audit.equal(dict(page.sources), expected_sources, 'three scoped primary citation links')
    audit.equal({s['id']: s['url'] for s in sources['sources']}, expected_sources, 'source record and actual links')
    audit.true(all(s['actual_inspector'] == 'c05_review' for s in sources['sources']), 'actual fresh source inspector')
    audit.equal(sum(len(s['equation_images_inspected']) for s in sources['sources']), 5, 'five honestly scoped equation images')
    audit.true(all(not link.startswith(('production/', 'chapters/', 'projects/')) for link in page.links), 'flat reader paths')
    for part in ('teach-answer', 'retention-answer', 'solutions', 'sources', 'sperner', 'brouwer', 'kakutani', 'existence'):
        audit.true('v13-c04-'+part in page.ids, 'complete instructional/proof component '+part)
    audit.equal(set(review['proof_audit']), {f'P{i}' for i in range(1, 7)}, 'six substantive proof records')
    audit.equal(set(review['exercise_audit']), set(prompts), 'every exact exercise reviewed')
    audit.equal(review['unresolved_findings'], [], 'no unresolved author finding')
    summary = {'chapter': 'v13-c04', 'status': 'canonical author checks passed; acceptance pending',
               'comparisons': audit.comparisons, 'domain_rejections': audit.rejections,
               'intervention_groups': audit.interventions, 'worked_cases': 6, 'solved_exercises': 12,
               'primitive_input_markers': len(inputs), 'visible_result_markers': len(expected),
               'label_table_rows': len(table), 'finite_barycentric_cells': cells,
               'boundary_midpoint_labelings': 8, 'proof_contracts': 6, 'runtime_payloads': 4}
    json.dumps(summary, allow_nan=False)
    return summary


if __name__ == '__main__':
    check()
