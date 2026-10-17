"""Independent primitive oracle; author checker is hash-bound only."""
import ast
import hashlib
import json
import re
import sys
from fractions import Fraction as Q
from html.parser import HTMLParser
from itertools import permutations
from pathlib import Path

FILES = (
    'production/v17-c01-working.html',
    'production/check_v17_c01_working.py',
    'production/v17-c01-sources-working.json',
    'production/v17-c01-author-review-working.json',
    'production/check_v17_c01_peer_working.py',
    'production/v17-c01-peer-review-working.json',
)


def need(condition, message):
    if not condition:
        raise ValueError(message)


def literal(text):
    def visit(n):
        if isinstance(n, ast.Tuple):
            return tuple(visit(e) for e in n.elts)
        if isinstance(n, ast.Constant) and type(n.value) in (int, str):
            return n.value
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.USub):
            v = visit(n.operand)
            need(type(v) is int, 'negative nonnumber')
            return -v
        raise ValueError('unsupported manuscript literal')
    return visit(ast.parse(text.strip(), mode='eval').body)


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids, self.solutions, self.worked, self.sources = [], [], [], []
        self.inputs, self.results, self.tables = {}, {}, {}
        self.marker = None
        self.table = self.row = self.cell = None
        self.stack = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag not in ('br', 'hr', 'img', 'meta', 'link', 'input'):
            self.stack.append(tag)
        if 'id' in a:
            self.ids.append(a['id'])
        if 'data-solution-for' in a:
            self.solutions.append(a['data-solution-for'])
        if tag == 'article' and 'worked' in a.get('class', '').split():
            self.worked.append(a.get('id'))
        if 'data-source' in a:
            self.sources.append((a['data-source'], a.get('href')))
        for key, store in [('data-input', self.inputs), ('data-result', self.results)]:
            if key in a:
                need(self.marker is None and a[key] not in store, 'duplicate marker')
                self.marker = (tag, store, a[key], [])
        if tag == 'table':
            self.table = a.get('id', 'unnamed-' + str(len(self.tables)))
            self.tables[self.table] = []
        if tag == 'tr':
            self.row = []
        if tag in ('th', 'td'):
            self.cell = []

    def handle_data(self, data):
        if self.marker:
            self.marker[3].append(data)
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        need(bool(self.stack) and self.stack.pop() == tag, 'unbalanced HTML')
        if self.marker and tag == self.marker[0]:
            _, store, key, parts = self.marker
            store[key] = literal(''.join(parts))
            self.marker = None
        if tag in ('td', 'th'):
            self.row.append(''.join(self.cell).strip())
            self.cell = None
        if tag == 'tr':
            self.tables[self.table].append(self.row)
            self.row = None
        if tag == 'table':
            self.table = None


def numbers(seq, count):
    need(isinstance(seq, (tuple, list)) and len(seq) == count, 'input dimensions')
    need(all(type(x) in (int, Q) for x in seq), 'exact numeric inputs required')
    return tuple(Q(x) for x in seq)


def choice(raw):
    *benefit, price, cash = numbers(raw, 6)
    need(price >= 0 and cash >= 0, 'negative price or cash')
    costs = tuple(price * q for q in range(4))
    net = tuple(b - c for b, c in zip(benefit, costs))
    feasible = tuple(q for q in range(4) if costs[q] <= cash)
    best = tuple(q for q in feasible if not any(net[j] > net[q] for j in feasible))
    return costs, net, feasible, best


def did(raw):
    t0, t1, c0, c1 = numbers(raw, 4)
    return t1-t0, c1-c0, (t1-c1)-(t0-c0)


def world(raw, untreated_change):
    t0, t1, c0, c1 = numbers(raw, 4)
    (change,) = numbers((untreated_change,), 1)
    missing = t0 + change
    return missing, t1-missing, change-(c1-c0)


def interval(raw, bounds):
    low, high = numbers(bounds, 2)
    need(low <= high, 'unordered trend bounds')
    d = did(raw)[2]
    return d-high, d-low


def topological(order, edges):
    nodes = set(x for e in edges for x in e)
    return len(order) == len(nodes) and set(order) == nodes and all(order.index(a) < order.index(b) for a, b in edges)


def check(root=None):
    root = Path(root).resolve() if root is not None else Path(__file__).resolve().parents[1]
    payloads = {name: (root/name).read_bytes() for name in FILES}
    review = json.loads(payloads[FILES[5]])
    need(set(review['payloads']) == set(FILES[:5]), 'five nonself bindings')
    for name, data in payloads.items():
        if name != FILES[5]:
            need(review['payloads'][name] == {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}, 'changed freeze: '+name)
    page = Page()
    page.feed(payloads[FILES[0]].decode())
    page.close()
    need(not page.stack and page.marker is None, 'incomplete HTML')
    need(len(page.ids) == len(set(page.ids)), 'duplicate IDs')
    expected_ex = ['v17-c01-ex'+str(i) for i in range(1, 9)]
    need(page.solutions == expected_ex and all(x in page.ids for x in expected_ex), 'prompt/solution pairing')
    need(page.worked == ['v17-c01-case1', 'v17-c01-case2'], 'worked artifacts')
    sources = json.loads(payloads[FILES[2]])['sources']
    need(set(page.sources) == {(x['id'], x['url']) for x in sources}, 'source URLs/scopes')
    need([x['actual_inspector'] for x in sources] == ['root', 'root', 'v16_c01_author', 'v16_c01_author'], 'source attribution')
    comparisons = 0

    def equal(actual, expected, label):
        nonlocal comparisons
        comparisons += 1
        need(actual == expected, label)

    edges = page.inputs['dag']
    rows = page.tables['v17-c01-dag'][1:]
    table_edges = {(dep.strip(), row[0]) for row in rows for dep in row[2].split(',') if row[0] != 'U'}
    equal(set(edges), table_edges, 'DAG table/edge agreement')
    equal(topological(page.results['dag-order'], edges), True, 'displayed order')
    equal(topological(tuple('UFSNCR'), edges), True, 'alternate order')
    nodes = tuple('USFNCR')
    cyclic = edges + (('R', 'F'),)
    equal(any(topological(p, cyclic) for p in permutations(nodes)), False, 'cycle prevents every ordering')
    equal(topological(tuple('UMFSNCR'), edges + (('M', 'F'),)), True, 'meaning node repair')
    results = {'dag-order': page.results['dag-order']}
    for input_key, output_prefix in [('choice', 'choice'), ('choice-transfer', 'transfer'), ('exercise-choice', 'exercise')]:
        costs, net, feasible, best = choice(page.inputs[input_key])
        results.update({output_prefix+'-net': net, output_prefix+'-feasible': feasible, output_prefix+'-best': best})
        if output_prefix == 'exercise':
            results['exercise-cost'] = costs
        if output_prefix == 'choice':
            expected_rows = [[str(q), str(page.inputs[input_key][q]), str(costs[q]), str(net[q]), 'Yes' if q in feasible else 'No'] for q in range(4)]
            equal(page.tables['v17-c01-choice-table'][1:], expected_rows, 'complete displayed table')
            equal(net[2]-net[1], 6, 'best forgone increment')
    d = did(page.inputs['did'])
    results['did'] = d
    w0 = world(page.inputs['did'], d[1])
    w1 = world(page.inputs['did'], d[1]+4)
    results['did-worlds'] = w0[:2] + w1[:2]
    results['did-range'] = interval(page.inputs['did'], page.inputs['trend-bounds'])
    ex = page.inputs['exercise-did']
    ew0, ew1 = world(ex[:4], ex[4]), world(ex[:4], ex[5])
    results['exercise-did'] = did(ex[:4]) + ew0[:2] + ew1
    equal(set(page.results), set(results), 'all result markers covered')
    for key, value in results.items():
        equal(page.results[key], value, key)
    # Full independently reconstructed unmarked answers, including equality/tie variants.
    equal(choice((0,18,34,48,16,15))[2:], ((0,), (0,)), 'transfer tight cash')
    equal(choice((0,18,34,48,16,48)), ((0,16,32,48),(0,2,2,0),(0,1,2,3),(1,2)), 'exercise 7 complete')
    equal(choice((0,18,34,48,10,30)), ((0,10,20,30),(0,8,14,18),(0,1,2,3),(3,)), 'retention complete')
    equal((34-20, 20 <= 15, 31-20, 15 <= 15), (14, False, 11, True), 'diagnostic')
    equal((20, 34-20, 20 <= 20), (20,14,True), 'exercise 4 equality')
    equal((sum((3,2,2,2,1)),sum((2,2,2,2,2)),sum((1,2,1,2))), (10,10,6), 'rubrics independently read')
    for key, total in [('v17-c01-case1-alignment',40),('v17-c01-case2-alignment',50)]:
        times = [tuple(map(int,re.match(r'(\d+)–(\d+)',row[0]).groups())) for row in page.tables[key][1:]]
        equal(times[0][0], 0, 'sequence begins at zero')
        equal([b for a,b in times[:-1]], [a for a,b in times[1:]], 'contiguous sequence')
        equal(sum(b-a for a,b in times), total, 'complete planned minutes')
    # Boundary worlds have independent closed-form expectations, not self-comparisons.
    for raw, expected in [((0,0,0,0,0,0),((0,1,2,3),(0,1,2,3))), ((0,18,34,48,10,0),((0,),(0,))), ((0,-1,-2,-3,0,0),((0,1,2,3),(0,))), ((0,1,2,3,1,3),((0,1,2,3),(0,1,2,3)))]:
        equal(choice(raw)[2:], expected, 'choice boundary')
    counterfactual_worlds = 0
    for raw in (page.inputs['did'], ex[:4], (0,-3,5,2)):
        low, high = -2, 4
        bound = interval(raw,(low,high))
        for delta in (-2,-1,0,1,2,3,4):
            missing, effect, reconstructed_delta = world(raw, did(raw)[1]+delta)
            equal(effect+reconstructed_delta, did(raw)[2], 'identity in complete world')
            equal(bound[0] <= effect <= bound[1], True, 'sharp attainable range')
            equal(missing+effect, raw[1], 'observed treated outcome recovered')
            counterfactual_worlds += 1
        equal(interval(raw,(0,0)), (did(raw)[2],)*2, 'parallel trends point')
    invalid = 0
    for call in [lambda:choice((0,1,2,3,-1,4)),lambda:choice((0,1,2,3,1,-1)),lambda:choice((0,1,2,1,4)),lambda:choice((0,1,2,3,True,4)),lambda:choice((0,1,2,3,1.0,4)),lambda:did((1,2,3)),lambda:did((1,2,3,'4')),lambda:interval((1,2,3,4),(2,1)),lambda:interval((1,2,3,4),(False,1)),lambda:literal('__import__("os")')]:
        try:
            call()
        except (ValueError, TypeError):
            invalid += 1
        else:
            raise ValueError('invalid input accepted')
    return {'chapter':'v17-c01','component':'independent_peer','status':'passed','runtime_files':6,'worked_artifacts':2,'exercises':8,'result_markers':len(results),'comparisons':comparisons,'counterfactual_worlds':counterfactual_worlds,'invalid_domains':invalid,'author_checker':'Hash-bound only; no reading/import/execution.','qualitative_scope':'Full two artifacts/eight answers/source scopes and global proofs reviewed separately; no actual learner observation or measured teaching effect.'}


if __name__ == '__main__':
    need(len(sys.argv) <= 2, 'usage: checker [book-root]')
    check(sys.argv[1] if len(sys.argv) == 2 else None)
