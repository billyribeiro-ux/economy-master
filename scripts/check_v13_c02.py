"""Quiet, exact four-file author checks for consumer and producer duality."""
from fractions import Fraction as F
from html.parser import HTMLParser
from pathlib import Path
import ast
import hashlib
import json
import math

HTML = 'content/chapters/v13-c02.html'
SOURCES = 'content/reviews/v13-c02-sources.json'
REVIEW = 'content/reviews/v13-c02-author.json'
SELF = 'scripts/check_v13_c02.py'


def require(ok, message):
    if not ok:
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
            raise ValueError('invalid case accepted: ' + label)


def number(value):
    require(type(value) in (int, F), 'exact integer/Fraction, excluding bool and floats')
    require(abs(value) <= 1000000, 'bounded exact arithmetic')
    return F(value)


def vector(values, size, positive=False):
    require(type(values) in (list, tuple) and len(values) == size, 'vector dimension')
    result = tuple(number(v) for v in values)
    if positive:
        require(min(result) > 0, 'strictly positive prices')
    return result


def root(value):
    value = number(value)
    require(value >= 0, 'nonnegative root argument')
    a, b = math.isqrt(value.numerator), math.isqrt(value.denominator)
    require(a*a == value.numerator and b*b == value.denominator, 'rational-square oracle domain')
    return F(a, b)


def dot(a, b):
    require(len(a) == len(b), 'inner-product dimensions')
    return sum((x*y for x, y in zip(a, b)), F(0))


def matvec(matrix, value):
    return tuple(dot(row, value) for row in matrix)


class Jet:
    """Three-variable exact second-order forward differentiation."""
    def __init__(self, value, gradient=(0, 0, 0), hessian=None):
        self.value = number(value)
        self.gradient = tuple(map(F, gradient))
        self.hessian = tuple(tuple(map(F, row)) for row in
                             (hessian if hessian is not None else ((0, 0, 0),)*3))

    @staticmethod
    def coerce(other):
        return other if isinstance(other, Jet) else Jet(other)

    @staticmethod
    def variable(value, index):
        return Jet(value, tuple(int(i == index) for i in range(3)))

    def __add__(self, other):
        other = self.coerce(other)
        return Jet(self.value+other.value,
                   tuple(a+b for a, b in zip(self.gradient, other.gradient)),
                   tuple(tuple(self.hessian[i][j]+other.hessian[i][j] for j in range(3)) for i in range(3)))
    __radd__ = __add__

    def __neg__(self):
        return self * -1

    def __sub__(self, other):
        return self + -self.coerce(other)

    def __rsub__(self, other):
        return self.coerce(other) + -self

    def __mul__(self, other):
        other = self.coerce(other)
        return Jet(self.value*other.value,
                   tuple(a*other.value+self.value*b for a, b in zip(self.gradient, other.gradient)),
                   tuple(tuple(self.hessian[i][j]*other.value+self.value*other.hessian[i][j]
                               +self.gradient[i]*other.gradient[j]+self.gradient[j]*other.gradient[i]
                               for j in range(3)) for i in range(3)))
    __rmul__ = __mul__

    def unary(self, value, first, second):
        return Jet(value, tuple(first*a for a in self.gradient),
                   tuple(tuple(first*self.hessian[i][j]+second*self.gradient[i]*self.gradient[j]
                               for j in range(3)) for i in range(3)))

    def reciprocal(self):
        require(self.value != 0, 'reciprocal zero')
        v = self.value
        return self.unary(1/v, -1/(v*v), 2/(v*v*v))

    def __truediv__(self, other):
        return self * self.coerce(other).reciprocal()

    def __rtruediv__(self, other):
        return self.coerce(other) * self.reciprocal()

    def sqrt(self):
        require(self.value > 0, 'smooth positive square-root point')
        s = root(self.value)
        return self.unary(s, 1/(2*s), -1/(4*s*s*s))


def stone(prices, income, gamma=(1, 2)):
    prices = vector(prices, 2, True)
    gamma = vector(gamma, 2)
    require(min(gamma) >= 0, 'nonnegative subsistence quantities')
    income = number(income)
    surplus = income-dot(prices, gamma)
    require(surplus >= 0, 'nonempty shifted budget')
    x = tuple(g+surplus/(2*p) for g, p in zip(gamma, prices))
    return x, surplus/(2*root(prices[0]*prices[1]))


def stone_expenditure(prices, target, gamma=(1, 2)):
    prices, gamma, target = vector(prices, 2, True), vector(gamma, 2), number(target)
    require(target >= 0 and min(gamma) >= 0, 'nonnegative target/subsistence')
    return dot(prices, gamma)+2*target*root(prices[0]*prices[1])


def linear_cost(prices, target):
    prices, target = vector(prices, 2, True), number(target)
    require(target >= 0, 'nonnegative linear target')
    return target*min(prices[0], prices[1]/2)


def homothetic(prices, target, alpha=2):
    prices = vector(prices, 3, True)
    target, alpha = number(target), number(alpha)
    require(target >= 0 and alpha > 0, 'homothetic class domain')
    p = tuple(Jet.variable(v, i) for i, v in enumerate(prices))
    unit = alpha*(p[0]*p[1]).sqrt()+p[2]
    h = tuple(target*g for g in unit.gradient)
    return unit, h, target*unit.value


def producer(prices, output_price):
    w, r = vector(prices, 2, True), number(output_price)
    require(r >= 0, 'nonnegative output price')
    s = root(w[0]*w[1])
    q = r/(4*s)
    k, l = q*q*root(w[1]/w[0]), q*q*root(w[0]/w[1])
    cost = dot(w, (k, l))
    w1, w2, rjet = (Jet.variable(v, i) for i, v in enumerate(w+(r,)))
    profit = rjet*rjet/(8*(w1*w2).sqrt())
    return (q, k, l, cost, r*q-cost), profit


def entry(w, r):
    w, r = number(w), number(r)
    require(w > 0 and r > 0, 'positive entry prices')
    # Concavity confines active maximization to its stationary point or endpoints.
    quantities = sorted({F(0), F(3), min(F(3), r/(2*w))})
    plans = [(F(0), (F(0), F(0)))]
    plans += [(r*q-w*(4+q*q), (-4-q*q, q)) for q in quantities]
    maximum = max(value for value, _ in plans)
    supply = tuple(sorted({y for value, y in plans if value == maximum}, key=lambda y: y[1]))
    return maximum, supply


def original_feasible(net):
    input_net, q = vector(net, 2)
    resources = -input_net
    if resources < 0:
        return False
    return resources >= 0 if q <= 0 else q <= 3 and resources >= 4+q*q


def log_shares(prices, income):
    prices, income = vector(prices, 3, True), number(income)
    require(income > 0, 'positive share income')
    logs = tuple(math.log(float(p)) for p in prices)
    require(max(logs)-min(logs) < 1, 'declared share neighborhood')
    shares = tuple(1/3+(logs[(i+1)%3]-logs[(i+2)%3])/12 for i in range(3))
    return shares, tuple(float(income/prices[i])*shares[i] for i in range(3))


def expression(text):
    text = text.replace('−', '-')
    require(len(text) <= 1000, 'bounded displayed arithmetic')
    try:
        tree = ast.parse(text, mode='eval')
    except SyntaxError as error:
        raise ValueError('malformed expression') from error
    def visit(node):
        if isinstance(node, ast.Constant) and type(node.value) is int:
            return number(node.value)
        if isinstance(node, ast.Tuple):
            return tuple(visit(child) for child in node.elts)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            return -visit(node.operand)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            numerator, denominator = visit(node.left), visit(node.right)
            require(denominator != 0, 'zero denominator')
            return numerator/denominator
        raise ValueError('only exact displayed integer/fraction tuples are allowed')
    return visit(tree.body)


def strict_json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    def bad(value):
        raise ValueError('nonfinite JSON ' + value)
    return json.loads(text, object_pairs_hook=pairs, parse_constant=bad)


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.ids = []
        self.worked = []
        self.exercises = []
        self.solutions = []
        self.inputs = {}
        self.calcs = {}
        self.links = []
        self.sources = []
        self.headings = []

    def handle_starttag(self, tag, attrs):
        require(len(attrs) == len(dict(attrs)), 'duplicate HTML attributes')
        a = dict(attrs)
        if 'id' in a:
            self.ids.append(a['id'])
        if 'worked' in a.get('class', '').split():
            self.worked.append(a.get('id'))
        if tag in ('h1', 'h2', 'h3', 'h4'):
            self.headings.append(tag)
        if tag == 'a':
            self.links.append(a.get('href', ''))
        if 'data-source' in a:
            self.sources.append(a['data-source'])
        if tag == 'li' and any('exercises' in n['a'].get('class', '').split() for n in self.stack):
            self.exercises.append(a.get('id'))
        if 'data-solution-for' in a:
            require(tag == 'li' and any('solutions' in n['a'].get('class', '').split() for n in self.stack),
                    'reader-recognized solution wrapper')
            self.solutions.append(a['data-solution-for'])
        if tag not in ('br', 'hr', 'img', 'meta', 'link', 'input', 'wbr'):
            self.stack.append({'tag': tag, 'a': a, 'text': []})

    def handle_data(self, data):
        for node in self.stack:
            node['text'].append(data)

    def handle_endtag(self, tag):
        require(self.stack and self.stack[-1]['tag'] == tag, 'balanced HTML at ' + tag)
        node = self.stack.pop()
        for key, dest in (('data-input', self.inputs), ('data-calc', self.calcs)):
            if key in node['a']:
                marker = node['a'][key]
                require(marker not in dest, 'unique displayed marker')
                dest[marker] = expression(''.join(node['text']).strip())


def derive(audit):
    inputs = {'subsistence': (1, 2), 'stone-prices': (4, 1), 'stone-income': 14,
              'stone-new-prices': (9, 1), 'linear-target': 6, 'linear-prices': (2, 4),
              'roy-point': (1, 2, 3), 'share-coefficient': F(1, 12), 'share-prices': (1, 1, 1),
              'share-income': 3, 'construct-prices': (1, 4, 2), 'construct-target': 3,
              'construct-new-prices': (4, 1, 2), 'producer-input-prices': (1, 4),
              'producer-output-price': 8, 'entry-input-price': 1, 'entry-output-prices': (3, 4, 5, 7)}
    result = {}
    p, m, gamma = vector(inputs['stone-prices'], 2), F(inputs['stone-income']), inputs['subsistence']
    x, u = stone(p, m, gamma)
    result['stone-choice'] = (x, u)
    pp1, pp2, mm = tuple(Jet.variable(v, i) for i, v in enumerate(p+(m,)))
    surplus = mm-pp1*gamma[0]-pp2*gamma[1]
    choices = (gamma[0]+surplus/(2*pp1), gamma[1]+surplus/(2*pp2))
    jacobian = tuple(tuple(c.gradient[:2]) for c in choices)
    income_gradient = tuple(c.gradient[2] for c in choices)
    slutsky = tuple(tuple(jacobian[i][j]+income_gradient[i]*x[j] for j in range(2)) for i in range(2))
    result['stone-jacobian'], result['stone-income-derivative'], result['stone-slutsky'] = jacobian, income_gradient, slutsky
    audit.equal(dot(p, x), m, 'original budget')
    audit.equal((x[0]-1)*(x[1]-2), u*u, 'utility squared')
    audit.equal(tuple(c.value for c in choices), x, 'derivative engine and primal solution')
    audit.equal(matvec(slutsky, p), (F(0), F(0)), 'compensated price kernel')
    direction = (F(1), F(-4))
    audit.equal(slutsky, tuple(tuple(-a*b/8 for b in direction) for a in direction), 'global negative rank-one certificate')
    new_x, new_u = stone(inputs['stone-new-prices'], m)
    result['stone-new-choice'] = (new_x, new_u)
    result['stone-losses'] = (stone_expenditure(inputs['stone-new-prices'], u)-m,
                              m-stone_expenditure(p, new_u))
    audit.equal(stone(p, dot(p, gamma)), ((F(1), F(2)), F(0)), 'zero-surplus boundary')
    audit.equal(stone(tuple(3*v for v in p), 3*m), (x, u), 'common price-income scaling')
    for target in (F(0), F(1, 2), F(2)):
        e = stone_expenditure(p, target)
        audit.equal(stone(p, e)[1], target, 'full target-to-budget transfer')
    audit.interventions += 2
    result['linear-expenditure'] = linear_cost(inputs['linear-prices'], inputs['linear-target'])
    endpoints = ((F(6), F(0)), (F(0), F(3)))
    result['linear-endpoints'] = endpoints
    step = F(1, 4)
    at = linear_cost((2, 4), 6)
    left = (at-linear_cost((2-step, 4), 6))/step
    right = (linear_cost((2+step, 4), 6)-at)/step
    result['linear-slopes'] = (left, right)
    for d in ((1, 0), (-1, 0), (1, 2)):
        derivative = (linear_cost((2+step*d[0], 4+step*d[1]), 6)-at)/step
        audit.equal(derivative, min(dot(h, d) for h in endpoints), 'exact one-sided kink derivative')
    p1, p2, income = tuple(Jet.variable(v, i) for i, v in enumerate(inputs['roy-point']))
    total = income/p1
    cube = (total-3)*(total-3)*(total-3)
    result['roy-zero-derivatives'] = cube.gradient
    result['roy-choice'] = (total.value, F(0))
    result['roy-valid-derivatives'] = total.gradient
    audit.true(total.gradient[2] > 0, 'valid alternative Roy denominator')
    result_away = (Jet.variable(4, 2)/Jet.variable(1, 0)-3)
    cube_away = result_away*result_away*result_away
    audit.equal(-cube_away.gradient[0]/cube_away.gradient[2], F(4), 'Roy away from flat derivative')
    audit.interventions += 2
    shares = (F(1, 3),)*3
    A = ((0, 1, -1), (-1, 0, 1), (1, -1, 0))
    rotation = tuple(tuple(3*(F(A[i][j], 12)+shares[i]*shares[j]-int(i == j)*shares[i])
                           for j in range(3)) for i in range(3))
    result['share-choice'], result['share-slutsky'] = (F(1),)*3, rotation
    audit.equal(tuple(map(sum, rotation)), (0, 0, 0), 'rotational row sums')
    audit.equal(tuple(map(sum, zip(*rotation))), (0, 0, 0), 'rotational column sums')
    audit.true(rotation[0][1] != rotation[1][0], 'exact integrability obstruction')
    for z in ((1, -1, 0), (2, 0, -1), (1, 1, 1)):
        mean = F(sum(z), 3)
        projection = tuple(v-mean for v in z)
        audit.equal(dot(z, matvec(rotation, z)), -dot(projection, projection), 'skew part and projection certificate')
    for prices in ((2, 1, 1), (6, 3, 3)):
        sh, demand = log_shares(prices, 3 if prices[0] == 2 else 9)
        audit.true(min(sh) > F(1, 4) and max(sh) < F(5, 12), 'interior log-share bound')
        audit.true(abs(sum(float(p)*q for p, q in zip(prices, demand))-(3 if prices[0] == 2 else 9)) < 1e-12, 'log-share budget')
    audit.true(all(abs(a-b) < 1e-12 for a, b in zip(log_shares((2, 1, 1), 3)[1], log_shares((6, 3, 3), 9)[1])), 'log-share scale invariance')
    audit.interventions += 1
    unit, h, expenditure = homothetic(inputs['construct-prices'], inputs['construct-target'])
    result['construct-choice'] = (unit.value, h, expenditure)
    _, changed_h, changed_e = homothetic(inputs['construct-new-prices'], inputs['construct-target'])
    result['construct-new-choice'] = changed_h
    audit.equal(dot(inputs['construct-prices'], h), expenditure, 'constructive expenditure witness')
    audit.equal(min(root(h[0]*h[1]), h[2]), F(3), 'direct utility at witness')
    first_mid = homothetic((4, 4, 2), 3)[2]
    second_mid = homothetic((1, 1, 2), 3)[2]
    result['construct-paths'] = ((first_mid-expenditure, changed_e-first_mid),
                                 (second_mid-expenditure, changed_e-second_mid))
    audit.equal(result['construct-paths'], ((12, -12), (-6, 6)), 'both analytic compensated paths')
    _, transfer, transfer_e = homothetic((9, 1, 2), 4, 1)
    transfer_u = min(2*root(transfer[0]*transfer[1]), transfer[2])
    result['alpha-transfer'] = (transfer, transfer_e, transfer_u)
    audit.equal(dot((9, 1, 2), transfer), transfer_e, 'alpha transfer expenditure')
    audit.equal(transfer_u, F(4), 'alpha transfer utility')
    audit.equal(homothetic((1, 4, 2), 0)[1:], ((0, 0, 0), 0), 'homothetic zero target')
    scaled_unit = homothetic((3, 12, 6), 3)[0]
    audit.equal(scaled_unit.value, 3*unit.value, 'unit-cost homogeneity')
    audit.true(scaled_unit.value+1 != 3*(unit.value+1), 'constant violates economic homogeneity')
    audit.interventions += 2
    allocation, profit = producer(inputs['producer-input-prices'], inputs['producer-output-price'])
    result['producer-choice'] = allocation
    result['producer-gradient'], result['producer-hessian'] = profit.gradient, profit.hessian
    all_prices = (F(1), F(4), F(8))
    audit.equal(dot(profit.gradient, all_prices), profit.value, 'profit Euler')
    audit.equal(matvec(profit.hessian, all_prices), (F(0),)*3, 'profit Hessian kernel')
    audit.equal(profit.gradient, (-allocation[1], -allocation[2], allocation[0]), 'net-supply signs')
    for z in ((1, 0, 0), (0, 1, 1), (2, -1, 3), (1, 4, 8)):
        a, b, rho = tuple(F(v)/p for v, p in zip(z, all_prices))
        audit.equal(dot(z, matvec(profit.hessian, z)),
                    profit.value*(2*(rho-(a+b)/2)**2+(a-b)**2/4), 'full Hessian square certificate')
    result['producer-swapped'] = producer((4, 1), 8)[0]
    audit.equal(producer((1, 4), 0)[0], (0, 0, 0, 0, 0), 'zero output-price solution')
    scaled_allocation, scaled_profit = producer((3, 12), 24)
    audit.equal(scaled_allocation[:3], allocation[:3], 'producer degree-zero quantities')
    audit.equal(scaled_profit.value, 3*profit.value, 'producer degree-one profit')
    for q in (F(0), F(1), F(2)):
        k, l = 2*q*q, q*q/2
        audit.equal(k*l, q**4, 'conditional technology equality')
        audit.equal(k+4*l, 4*q*q, 'conditional input-price bound attained')
    audit.interventions += 2
    branches = [entry(inputs['entry-input-price'], price) for price in inputs['entry-output-prices']]
    result['entry-profits'] = tuple(value for value, _ in branches)
    result['entry-quantities'] = tuple(tuple(y[1] for y in supply) if len(supply) > 1 else supply[0][1] for _, supply in branches)
    candidate = F(3, 2)
    result['entry-rejected-candidate'] = (candidate, 3*candidate-4-candidate*candidate)
    result['entry-tied-supplies'] = entry(1, 4)[1]
    result['entry-slopes'] = tuple(y[1] for y in entry(1, 4)[1])
    result['capacity-gradient'] = entry(1, 6)[1][0]
    hole = tuple(v/2 for v in entry(1, 4)[1][1])
    result['technology-hole'] = hole
    result['one-output-input'] = 4+hole[1]**2
    audit.true(not original_feasible(hole), 'convex mixture missing from original set')
    audit.true(original_feasible((-5, 1)), 'actual one-output minimum')
    audit.true(original_feasible((-13, 3)) and not original_feasible((-14, 4)), 'capacity and disposal boundary')
    audit.equal(entry(3, 12)[1], entry(1, 4)[1], 'entry tie scale invariance')
    for ratio, status in ((F(39, 10), 'off'), (F(41, 10), 'interior'),
                          (F(59, 10), 'interior'), (F(61, 10), 'cap')):
        value, supply = entry(1, ratio)
        expected_q = F(0) if status == 'off' else min(F(3), ratio/2)
        audit.equal(tuple(y[1] for y in supply), (expected_q,), 'entry/capacity neighboring branch')
        audit.equal(value, max(F(0), ratio*expected_q-4-expected_q**2), 'complete participation comparison')
    for price in ((1, 3), (1, 4), (1, 7)):
        support = entry(*price)[0]
        audit.equal(dot(price, hole), (dot(price, (0, 0))+dot(price, (-8, 2)))/2, 'hull witness linear value')
        audit.true(dot(price, hole) <= support, 'full-price analytic certificate illustrated')
    audit.interventions += 2
    # Real invalid calls. Mathematical models allow irrational prices; the exact
    # square-root evaluator is deliberately bounded to rational-square test cases.
    for bad in (True, 0.5, float('nan'), float('inf'), 1000001):
        audit.reject(lambda bad=bad: number(bad), 'exact scalar domain')
    for bad in ((0, 1), (-1, 1), (1,), (1, True)):
        audit.reject(lambda bad=bad: stone(bad, 14), 'positive two-price domain')
    audit.reject(lambda: stone((4, 1), 5), 'empty shifted budget')
    audit.reject(lambda: stone_expenditure((4, 1), -1), 'negative target')
    audit.reject(lambda: root(-1), 'negative root')
    audit.reject(lambda: root(2), 'irrational value outside exact oracle')
    audit.reject(lambda: Jet(0).reciprocal(), 'zero reciprocal')
    audit.reject(lambda: Jet(0).sqrt(), 'nonsmooth square-root evaluation')
    audit.reject(lambda: homothetic((1, 4, 2), 1, 0), 'alpha boundary')
    audit.reject(lambda: homothetic((1, 4, 0), 1), 'zero third price')
    audit.reject(lambda: producer((1, 4), -1), 'negative output price')
    audit.reject(lambda: entry(0, 4), 'zero input price')
    audit.reject(lambda: entry(1, 0), 'outside strictly positive entry domain')
    audit.reject(lambda: log_shares((3, 1, 1), 3), 'outside stated logarithmic neighborhood')
    audit.reject(lambda: log_shares((1, 1, 1), 0), 'zero share income')
    for bad in ('{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}'):
        audit.reject(lambda bad=bad: strict_json(bad), 'strict JSON')
    for bad in ('True', '1/0', '__import__("os")'):
        audit.reject(lambda bad=bad: expression(bad), 'restricted numeric marker')
    return inputs, result


def check(root=None):
    base = Path(root) if root is not None else Path(__file__).resolve().parents[1]
    audit = Audit()
    review = strict_json((base/REVIEW).read_text(encoding='utf-8'))
    sources = strict_json((base/SOURCES).read_text(encoding='utf-8'))
    bindings = review['payload_bindings']
    audit.equal({b['path'] for b in bindings}, {HTML, SOURCES, SELF}, 'three nonself author bindings')
    audit.equal(len(bindings), 3, 'binding cardinality')
    for b in bindings:
        raw = (base/b['path']).read_bytes()
        audit.equal((len(raw), hashlib.sha256(raw).hexdigest()), (b['bytes'], b['sha256']), 'frozen author payload')
    inputs, expected = derive(audit)
    doc = Page()
    doc.feed((base/HTML).read_text(encoding='utf-8'))
    doc.close()
    audit.equal(doc.stack, [], 'balanced full fragment')
    audit.equal(len(doc.ids), len(set(doc.ids)), 'unique chapter IDs')
    audit.true(all(i.startswith('v13-c02-') for i in doc.ids), 'scoped chapter IDs')
    audit.equal(doc.worked, [f'v13-c02-case{i}' for i in range(1, 7)], 'six worked cases')
    expected_exercises = [f'v13-c02-ex{i}' for i in range(1, 13)]
    audit.equal(doc.exercises, expected_exercises, 'twelve exact exercise prompts')
    audit.equal(doc.solutions, expected_exercises, 'twelve complete recognized solution pairings')
    audit.true('h1' not in doc.headings, 'fragment has no extra page title')
    audit.equal(doc.inputs, inputs, 'all actual primitive inputs')
    audit.equal(set(doc.calcs), set(expected), 'complete visible numeric inventory')
    for key, value in expected.items():
        audit.equal(doc.calcs[key], value, 'independently derived marker ' + key)
    source_ids = {'v05-c02-consumer', 'v05-c03-condie-supply'}
    audit.equal(set(doc.sources), source_ids, 'two reused method sources')
    audit.equal({s['id'] for s in sources['sources']}, source_ids, 'source record matches citations')
    audit.equal(sources['fresh_primary_body_reads_by_working_author'], 0, 'honest primary inspection attribution')
    audit.true(all(s['actual_primary_inspector'] == 'root' for s in sources['sources']), 'retained actual source inspector')
    audit.true(all(not link.startswith(('production/', 'chapters/', 'projects/')) for link in doc.links), 'flat reader links and no undistributed checker link')
    for anchor in ('teach-answer', 'retention-answer', 'solutions', 'sources'):
        audit.true('v13-c02-'+anchor in doc.ids, 'answered instructional component')
    audit.equal(review['unresolved_findings'], [], 'resolved author findings')
    summary = {'chapter': 'v13-c02', 'status': 'author checks passed; separate acceptance record governs status',
               'comparisons': audit.comparisons, 'domain_rejections': audit.rejections,
               'intervention_groups': audit.interventions, 'worked_cases': 6, 'solved_exercises': 12,
               'primitive_input_markers': len(inputs), 'visible_result_markers': len(expected),
               'proof_contracts': 6, 'runtime_payloads': 4}
    json.dumps(summary, allow_nan=False)
    return summary


if __name__ == '__main__':
    check()
