"""Exact support arithmetic and complete assembly gates for Volume 11."""
from fractions import Fraction as F
from html.parser import HTMLParser
from itertools import product
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
PARTS = ('v11-support-opening.html', 'v11-exam-a.html', 'v11-exam-b.html',
         'v11-project.html', 'v11-support-closing.html')
SUPPORT = ['content/assessments/parts/'+PARTS[0],
           'content/assessments/parts/'+PARTS[-1],
           'scripts/check_v11_assessment.py', 'content/reviews/v11-support-sources.json']


def require(condition, label):
    if not condition:
        raise RuntimeError(label)


class SupportHTML(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack = []; self.ids = []; self.points = {}; self.solutions = []
        self.links = []; self.answers = {}; self.answer = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if 'id' in a:
            self.ids.append(a['id'])
        if tag == 'li' and 'data-points' in a:
            require(a.get('id') and a['id'] not in self.points, 'unique scored list prompt')
            self.points[a['id']] = int(a['data-points'])
        if 'data-solution-for' in a:
            require(self.answer is None, 'non-nested support answer')
            self.answer = a['data-solution-for']
            self.solutions.append(self.answer); self.answers[self.answer] = ''
        if tag == 'a':
            self.links.append(a.get('href', ''))
        if tag not in ('br', 'hr', 'img', 'input', 'meta', 'link'):
            self.stack.append(tag)

    def handle_endtag(self, tag):
        require(self.stack and self.stack[-1] == tag, 'balanced HTML: '+tag)
        self.stack.pop()
        if tag == 'li':
            self.answer = None

    def handle_data(self, text):
        if self.answer:
            self.answers[self.answer] += text


def support_check():
    count = 0
    def eq(got, expected, label):
        nonlocal count
        count += 1
        require(got == expected, label+': '+repr(got)+' != '+repr(expected))
    parser = SupportHTML()
    for name in (PARTS[0], PARTS[-1]):
        parser.feed((ROOT/'content/assessments/parts'/name).read_text())
        require(not parser.stack, 'closed support fragment')
    def printed(key, *tokens):
        for token in tokens:
            eq(token in parser.answers['v11-'+key], True, key+' printed '+token)
    def balance(row, label):
        eq(sum(row[:3]), sum(row[3:]), label)

    # D1: journal vectors, order cash/loans/securities/deposits/debt/equity.
    row = [12, 58, 30, 70, 20, 10]
    for event, delta, expected in [
        ('withdrawal', [-8, 0, 0, -8, 0, 0], [4, 58, 30, 62, 20, 10]),
        ('outside loan', [5, 0, 0, 0, 5, 0], [9, 58, 30, 62, 25, 10])]:
        row = [x+y for x, y in zip(row, delta)]
        eq(row, expected, 'D1 '+event); balance(row, 'D1 balanced '+event)
    eq((sum(row[:3]), sum(row[3:5])), (97, 87), 'D1 closing aggregates')
    printed('d1', '97', '87', 'equity remains ten')

    # D2: joint applicant masses, not a posterior applied to every applicant.
    pass_good, pass_bad = F(3, 4)*F(4, 5), F(1, 4)*F(1, 5)
    pass_total = pass_good+pass_bad
    posterior = pass_good/pass_total
    receipt = posterior*112+(1-posterior)*52
    eq((pass_total, posterior, receipt), (F(13, 20), F(12, 13), F(1396, 13)), 'D2 posterior loan')
    eq(pass_good*(112-100)+pass_bad*(52-100)-2, F(14, 5), 'D2 applicant-level funded gain')
    eq(F(3, 4)*112+F(1, 4)*52-100, -3, 'D2 unscreened loss')
    printed('d2', '13/20', '12/13', '1396/13', '107.384615', '14/5', '96/13')
    eq(round(float(receipt), 6), 107.384615, 'D2 rounded receipt')

    eq(10*F('.95')+110*F('.90'), F('108.5'), 'D3 dated value')
    eq(120*F('.90'), 108, 'D3 delayed value'); printed('d3', '108.5', '108 CU', '0.5')
    law = [(0, F('.8')), (10, F('.15')), (50, F('.05'))]
    eq(sum(x*p for x, p in law), 4, 'D4 expected loss')
    eq(sum(p for x, p in law if x > 10), F('.05'), 'D4 strict tail')
    cumulative = F(0); quantile = None
    for loss, probability in law:
        cumulative += probability
        if quantile is None and cumulative >= F('.95'):
            quantile = loss
    eq(quantile, 10, 'D4 left quantile'); printed('d4', 'four CU', '0.05', 'ten CU')
    prefixes = [5+4-10, 5+4-10+8-6]
    contribution = max([0]+[-v for v in prefixes])
    eq((contribution, [v+contribution for v in prefixes]), (1, [0, 2]), 'D5 necessary and sufficient cash')
    printed('d5', 'one CU', 'zero at cutoff 1 and two at cutoff 2')
    eq((F(3, 4)*4, F(1, 4)*4), (3, 1), 'D6 physical versus state price')
    printed('d6', 'three CU', 'one CU')
    converted = 20*F('1.5'); transferred = min(converted, 12)
    eq((converted+3, 3+transferred, 20-3-transferred, converted-transferred),
       (33, 15, 5, 18), 'D7 assets and location')
    printed('d7', '33 H', '18 H onshore', '15 H', 'five H')
    pay = {('S', 'S'): (4, 4), ('S', 'R'): (1, 6),
           ('R', 'S'): (6, 1), ('R', 'R'): (2, 2)}
    equilibria = []
    for profile, values in pay.items():
        alternatives = [(('R' if profile[0] == 'S' else 'S'), profile[1]),
                        (profile[0], ('R' if profile[1] == 'S' else 'S'))]
        if all(values[i] >= pay[alternatives[i]][i] for i in (0, 1)):
            equilibria.append(''.join(profile))
    eq(equilibria, ['RR'], 'D8 complete unilateral deviations')
    printed('d8', 'RR is the unique Nash equilibrium', 'eight at SS and four at RR')
    eq((5+10-8, 8-5), (7, 3), 'O2 actual dated receipt example')

    # R1: lending, settlement and impairment are three different entries.
    row = [9, 61, 30, 80, 10, 10]
    for delta, expected in [
        ([0, 10, 0, 10, 0, 0], [9, 71, 30, 90, 10, 10]),
        ([-7, 0, 0, -7, 0, 0], [2, 71, 30, 83, 10, 10]),
        ([0, -4, 0, 0, 0, -4], [2, 67, 30, 83, 10, 6])]:
        row = [x+y for x, y in zip(row, delta)]
        eq(row, expected, 'R1 event'); balance(row, 'R1 balance')
    eq((sum(row[:3]), row[0], 6-5), (99, 2, 1), 'R1 final resources and borrower gap')
    printed('r1', '99', 'two', 'one-CU service gap', 'equity to six')

    law = [(0, F('.7')), (8, F('.2')), (40, F('.1'))]
    remaining = F('.2'); weighted = F(0)
    for value, probability in reversed(law):
        taken = min(remaining, probability); weighted += value*taken; remaining -= taken
    eq((remaining, weighted/F('.2')), (0, 24), 'R2 exact upper-tail mass')
    eq((F('.7') < F('.8') <= F('.9')), True, 'R2 quantile eight')
    first = 6+3-12; final = first+9-4; topup = max(0, -first, -final)
    eq((topup, first+topup, final+topup), (3, 0, 5), 'R2 independent cash prefixes')
    eq(10*F('.8')*(1-F('.25')), 6, 'R2 capacity is late')
    printed('r2', '=8', '=24', 'three', 'zero and five', 'six CU')

    # R3: a five-state joint law establishes dependence without a label shortcut.
    states = [(True, True, F('.1'))]
    for a, b in product((False, True), repeat=2):
        probability = F('.9')*(F('.2') if a else F('.8'))*(F('.2') if b else F('.8'))
        states.append((a, b, probability))
    eq(sum(p for _, _, p in states), 1, 'R3 law total')
    joint = sum(p for a, b, p in states if a and b)
    marginals = [sum(p for a, b, p in states if (a, b)[i]) for i in (0, 1)]
    eq((joint, marginals[0]*marginals[1], joint-marginals[0]*marginals[1]),
       (F('.136'), F('.0784'), F('.0576')), 'R3 common-failure effect')
    scenarios = [(8, 2, 0), (1, 7, 4)]
    eq((max(map(sum, scenarios)), sum(max(s[i] for s in scenarios) for i in range(3))),
       (12, 19), 'R3 consistent versus marginal maxima')
    eq(set(('a', 'b'))-set(('a', 'a')), {'b'}, 'R3 unpaid identity')
    printed('r3', '0.136', '0.0784', '0.0576', 'twelve', 'nineteen', 'b unpaid')

    # R4: guarantee owner wealth is included once, with statewise endowment.
    pensions = []
    for assets in (20, 60):
        guarantee = min(12, max(40-assets, 0))
        benefit = min(40, assets+guarantee)
        sponsor = max(assets-40, 0); public = 12-guarantee
        eq(benefit+sponsor+public, assets+12, 'R4 all-recipient conservation')
        pensions.append((guarantee, 40-benefit, sponsor))
    eq(pensions, [(12, 8, 0), (0, 0, 20)], 'R4 state claims')
    eq(tuple(F(sum(row[i] for row in pensions), 2) for i in range(3)), (6, 4, 10), 'R4 expectations')
    h_after = 66-16; bought = min(F(h_after, 2), 15)
    eq((h_after-2*bought, 8+bought, 30-8-bought), (20, 23, 7), 'R4 currency cap')
    printed('r4', 'one', 'eight unpaid benefits', 'six', 'four', 'ten', 'twenty H', '23 usable F', 'seven F')

    # R5: conversion, bridge, downstream timing and an actual manager payoff.
    assets = 4+76-20; old_equity = 10
    write_down = 20-old_equity; senior_left = 20-write_down
    advance = 9-4; interest = F('5.5')-advance
    conversion = 4+interest
    terminal_cash = 56-(advance+interest)-(50-9)-(senior_left-conversion)
    senior_value = senior_left-conversion+terminal_cash
    eq((write_down, advance, conversion, terminal_cash, senior_value),
       (10, 5, F('4.5'), 4, F('9.5')), 'R5 funded resolution')
    eq(50+senior_value+interest, assets, 'R5 full allocation')
    detect = (1-F('.25'))*F('.5'); improved = (1-F('.25'))*F('.6')
    eq((detect, 3-(3+5)*detect, improved, 3-(3+5)*improved),
       (F(3, 8), 0, F('.45'), F('-.6')), 'R5 incentive tie and strict repair')
    printed('r5', '4.5', '9.5', 'eight-CU', '3/8', 'zero', '0.45', '−0.6')

    eq(len(parser.ids), len(set(parser.ids)), 'unique support anchors')
    for prefix, number, points in [('v11-d', 8, 5), ('v11-o', 5, 4), ('v11-r', 5, 10)]:
        wanted = {prefix+str(i): points for i in range(1, number+1)}
        eq({k: v for k, v in parser.points.items() if k.startswith(prefix)}, wanted, 'scored '+prefix)
    eq(set(parser.solutions), set(parser.points), 'complete exact prompt/answer mapping')
    eq(len(parser.solutions), len(parser.points), 'no duplicated answer')
    for anchor in ('diagnostic', 'exam-rules', 'oral-transfer', 'retention', 'notation-index', 'concept-index', 'volume-synthesis'):
        eq(anchor in parser.ids, True, 'required support '+anchor)
    author_path = ROOT/'content/reviews/v11-support-author.json'
    bindings = 0
    if author_path.exists():
        rows = json.loads(author_path.read_text())['reviewed_hashes']
        eq({r['path'] for r in rows}, set(SUPPORT), 'exact four nonself payload paths')
        eq(len(rows), 4, 'no duplicate author binding')
        for item in rows:
            raw = (ROOT/item['path']).read_bytes()
            eq((len(raw), hashlib.sha256(raw).hexdigest()), (item['bytes'], item['sha256']), 'author binding '+item['path'])
            bindings += 1
    return dict(status='passed', comparisons=count, diagnostic_items=8, diagnostic_points=40,
                oral_transfers=5, oral_points=20, retention_items=5, retention_points=50,
                author_payload_hashes_verified=bindings,
                limits='Original authored support; no empirical timing/equating, learner achievement, legal authority, human certification or rendered UI claim.')


def check():
    result = support_check()
    require(result['author_payload_hashes_verified'] == 4, 'complete support author bindings')
    parts = [(ROOT/'content/assessments/parts'/name).read_text().strip() for name in PARTS]
    actual = (ROOT/'content/assessments/v11.html').read_text()
    require(actual == '\n\n'.join(parts)+'\n', 'exact five-part final assembly')
    parser = SupportHTML(); parser.feed(actual)
    require(not parser.stack and len(parser.ids) == len(set(parser.ids)), 'balanced unique assembly')
    for anchor in ('diagnostic', 'exam-rules', 'form-a', 'solutions-a', 'form-b', 'solutions-b',
                   'project', 'oral-transfer', 'retention', 'notation-index', 'concept-index', 'volume-synthesis'):
        require(anchor in parser.ids, 'required final anchor '+anchor)
    from check_v11_exam_a import check as exam_a
    from check_v11_exam_b import check as exam_b
    from check_v11_project import check as project
    from check_v11_exam_a_peer import check as peer_a
    from check_v11_exam_b_peer import check as peer_b
    from check_v11_project_peer import check as peer_project
    from check_v11_support_peer import check as peer_support
    result['component_checks'] = {name: checker() for name, checker in (
        ('exam_a_author', exam_a), ('exam_b_author', exam_b), ('project_author', project),
        ('exam_a_peer', peer_a), ('exam_b_peer', peer_b), ('project_peer', peer_project), ('support_peer', peer_support))}
    result['assembly_parts'] = list(PARTS)
    json.dumps(result, allow_nan=False)
    return result


if __name__ == '__main__':
    print(json.dumps(support_check() if '--support-only' in sys.argv else check(), indent=2))
