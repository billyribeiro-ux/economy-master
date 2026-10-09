"""Independent Form B peer: exact contracts, quantile intervals and priority tranches.

The financial oracle imports no author helper.  The author check is executed
only after the independent calculations as an additional integration gate.
The six-file author-plus-peer package is portable; check() is quiet and read-only.
"""
from contextlib import redirect_stdout, redirect_stderr
from fractions import Fraction as Q
from hashlib import sha256
from html.parser import HTMLParser
from io import StringIO
from pathlib import Path
import json
import re
import runpy
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
HTML = 'content/assessments/parts/v11-exam-b.html'
AUTHOR_CODE = 'scripts/check_v11_exam_b.py'
AUTHOR = 'content/reviews/v11-exam-b-author.json'
SOURCES = 'content/reviews/v11-exam-b-sources.json'
SELF = 'scripts/check_v11_exam_b_peer.py'
REVIEW = 'content/reviews/v11-exam-b-peer.json'
AUTHORED = (HTML, AUTHOR_CODE, AUTHOR, SOURCES)
PACKAGE = AUTHORED + (SELF, REVIEW)
SCORES = ((6, 8, 6), (10, 10), (6, 8, 6), (10, 10), (6, 8, 6))
POINTS = {'v11-b-q' + str(i) + letter: points
          for i, row in enumerate(SCORES, 1) for letter, points in zip('abc', row)}
SOURCE_IDS = {'v11-c01-diamond-monitoring', 'v11-c03-occ-commercial',
              'v11-c04-rockafellar-uryasev', 'v11-c02-bcbs-liquidity2008',
              'v10-c12-fed-guidance', 'v06-c09-debt', 'v11-c12-bcbs-governance2015'}


def require(condition, message):
    if not condition:
        raise ValueError('Form B peer: ' + message)


def strict(text):
    def unique(items):
        result = {}
        for key, value in items:
            require(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    def nonfinite(value):
        raise ValueError('nonfinite JSON constant: ' + value)
    return json.loads(text, object_pairs_hook=unique, parse_constant=nonfinite)


class Audit:
    def __init__(self):
        self.comparisons = self.rejections = self.interventions = self.portable = 0
    def eq(self, actual, expected, label):
        self.comparisons += 1
        require(actual == expected, label + ': ' + repr(actual) + ' != ' + repr(expected))
    def yes(self, condition, label):
        self.eq(bool(condition), True, label)
    def reject(self, function, label):
        try:
            function()
        except ValueError:
            self.rejections += 1
        else:
            raise ValueError('missing rejection: ' + label)


class Reader(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []; self.ids = []; self.links = []; self.sources = []
        self.points = {}; self.answers = {}; self.numbers = {}; self.headings = []
        self.answer = self.number = self.table = self.row = self.cell = None
        self.tables = []
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'id' in attrs: self.ids.append(attrs['id'])
        if tag == 'a': self.links.append(attrs.get('href', ''))
        if 'data-source' in attrs: self.sources.append(attrs['data-source'])
        if tag in ('h1', 'h2', 'h3', 'h4'): self.headings.append(tag)
        if 'data-points' in attrs:
            require(tag == 'li' and attrs['id'] not in self.points, 'unique scored list item')
            self.points[attrs['id']] = int(attrs['data-points'])
        if 'data-solution-for' in attrs:
            target = attrs['data-solution-for']
            require(target not in self.answers, 'unique prompt solution')
            self.answer = target; self.answers[target] = ''
        if 'data-calc' in attrs:
            require(self.number is None and attrs['data-calc'] not in self.numbers, 'unique numeric span')
            self.number = attrs['data-calc']; self.numbers[self.number] = ''
        if tag == 'table': self.table = []; self.tables.append(self.table)
        if tag == 'tr': self.row = []
        if tag in ('td', 'th'): self.cell = ''
        if tag not in ('br', 'hr', 'img', 'meta', 'link', 'input'): self.stack.append(tag)
    def handle_data(self, value):
        if self.answer is not None: self.answers[self.answer] += value
        if self.number is not None: self.numbers[self.number] += value
        if self.cell is not None: self.cell += value
    def handle_endtag(self, tag):
        if tag == 'li': self.answer = None
        if tag == 'span': self.number = None
        if tag in ('td', 'th'):
            self.row.append(' '.join(self.cell.split())); self.cell = None
        if tag == 'tr': self.table.append(self.row); self.row = None
        if tag == 'table': self.table = None
        require(bool(self.stack) and self.stack[-1] == tag, 'balanced HTML at ' + tag)
        self.stack.pop()


def tail_by_quantile_intervals(law, alpha):
    """Integrate the increasing quantile over [alpha,1], preserving boundary atoms."""
    require(0 < alpha < 1 and all(p >= 0 for _, p in law) and sum(p for _, p in law) == 1,
            'finite quantile domain')
    cumulative = Q(0); integral = Q(0); quantile = None
    for loss, mass in sorted(law):
        right = cumulative + mass
        if quantile is None and mass > 0 and right >= alpha: quantile = Q(loss)
        integral += loss * max(Q(0), right - max(cumulative, alpha))
        cumulative = right
    return quantile, integral / (1 - alpha)


def dependence(theta):
    require(0 <= theta <= Q(1, 4), 'joint Bernoulli feasibility')
    return [(Q(0), Q(1, 2) + theta), (Q(6), Q(1, 2) - 2 * theta), (Q(12), theta)]


def cash_prefixes(face, rate, principal, receipts, opening, grants):
    require(len(principal) == len(receipts) == len(grants) and sum(principal) == face,
            'complete dated principal contract')
    require(all(x >= 0 for x in principal + receipts + grants) and rate >= 0 and opening >= 0,
            'nonnegative dated resources')
    rows = []
    for i, redemption in enumerate(principal):
        outstanding = face - sum(principal[:i])
        interest = rate * outstanding
        rows.append((outstanding, interest, redemption, redemption + interest))
    projected = [opening + sum(receipts[:i + 1]) + sum(grants[:i + 1])
                 - sum(row[3] for row in rows[:i + 1]) for i in range(len(rows))]
    return rows, projected


def dated_headroom(x, gate=Q(3, 10), cash=Q(0)):
    require(0 <= x <= 1 and 0 <= gate <= 1 and cash >= 0, 'stress timing domain')
    usable_receipts = Q(12) if x < gate else Q(0)
    return Q(10) + cash + 60 * (1 - Q(1, 10) - x / 5) + usable_receipts - (60 + 20 * x)


def pension_row(survivors, assets, guarantor, cap=Q(20)):
    require(type(survivors) is int and survivors > 0 and min(assets, guarantor, cap) >= 0,
            'positive survivor and funded pension domain')
    promise = Q(30 * survivors)
    shortfall = max(Q(0), promise - assets)
    support = min(shortfall, cap, guarantor)
    benefit = min(promise, assets + support)
    return (promise, shortfall, support, benefit, benefit / survivors,
            promise - benefit, max(Q(0), assets - promise), guarantor - support)


def sovereign_plan(cap=Q(7), gross=Q(11, 10), conversion=Q(2)):
    """One-dimensional convex envelope, independently of the author's LP vertices."""
    require(cap >= 0 and gross >= 1 and 0 <= conversion <= 2, 'sovereign contract domain')
    first_gap = Q(25) - (9 + 8 + conversion)
    net_future = Q(18) - 12
    # g must exceed both first_gap-B and first_gap-net_future+(gross-1)B.
    crossing = net_future / gross
    candidates = {Q(0), cap}
    if 0 <= crossing <= cap: candidates.add(crossing)
    plans = [(max(Q(0), first_gap - borrow, first_gap - net_future + (gross - 1) * borrow), borrow)
             for borrow in candidates]
    grant, borrow = min(plans)
    first = 9 + 8 + conversion + borrow + grant - 25
    final = first + 18 - 12 - gross * borrow
    return grant, borrow, first, final, Q(12) - 2 * conversion


def priority_estates(asset, grant):
    """Allocate cumulative-priority tranches, then the separate client's estate."""
    require(asset >= 0 and 0 <= grant <= Q(1, 5), 'estate/private grant domain')
    note_payment = min(asset, Q(28))
    client_receipt = min(max(Q(0), asset - 28), Q(6))
    issuer_equity = max(Q(0), asset - 34)
    bridge = 1 - grant
    public_receipt = min(client_receipt, bridge)
    client_equity = max(Q(0), client_receipt - bridge)
    public_loss = bridge - public_receipt
    public_cash = 1 - bridge + public_receipt
    return (note_payment, client_receipt, issuer_equity, public_receipt,
            public_loss, client_equity, public_cash)


def independent_finance(a, doc):
    expected = {}
    benefit = (Q(3, 20) - Q(1, 20)) * 20
    cost, share, fee = Q(3, 2), Q(3, 5), Q(2, 5)
    private = share * benefit - cost
    investor = (1 - share) * benefit - fee
    expected.update(monitor_benefit=benefit, monitor_surplus=benefit-cost,
                    monitor_private_benefit=share*benefit, monitor_without_fee=private,
                    monitor_with_fee=private+fee, monitor_investor=investor)
    a.eq(private + fee + investor, benefit-cost, 'fee is a transfer')
    a.eq((private + fee) - fee, private, 'unconditional fee cancels from effort choice')
    a.eq(cost-share*benefit, Q(3, 10), 'minimum weak monitor fee')
    a.eq((1-share)*benefit, Q(4, 5), 'maximum weak investor fee')
    a.yes(private < 0 < private+fee and investor > 0, 'individual participation at conditional fee')
    a.interventions += 1  # Weak monitor fee equality versus strict improvement.
    old, old_cash = cash_prefixes(Q(60), Q(2, 25), [Q(20), Q(40)], [Q(18), Q(26)], Q(4), [Q(0), Q(0)])
    amended, amended_cash = cash_prefixes(Q(48), Q(1, 25), [Q(18), Q(30)], [Q(18), Q(26)], Q(4), [Q(0), Q(0)])
    required = max(Q(0), -amended_cash[1])
    _, funded = cash_prefixes(Q(48), Q(1, 25), [Q(18), Q(30)], [Q(18), Q(26)], Q(4), [Q(0), required])
    a.yes(old_cash[0] < 0, 'original contract first failure; later row is only a schedule')
    a.eq(funded, [Q(52, 25), Q(0)], 'amended funded prefixes')
    a.eq(amended_cash[1] + required - Q(1, 100), Q(-1, 100), 'strictly insufficient grant')
    a.interventions += 1
    expected.update(old_service1=old[0][3], old_service2=old[1][3], old_gap1=-old_cash[0],
                    new_service1=amended[0][3], new_service2=amended[1][3],
                    restructure_carry=amended_cash[0], restructure_grant=required)
    balance = (Q(18), Q(182), Q(10), Q(160), Q(12), Q(18))
    provision = (0, 0, 6, 0, 0, -6); chargeoff = (0, -12, -12, 0, 0, 0)
    after_provision = tuple(x+y for x, y in zip(balance, provision))
    after_chargeoff = tuple(x+y for x, y in zip(after_provision, chargeoff))
    for row in (balance, after_provision, after_chargeoff):
        cash, gross, allowance, deposits, debt, equity = row
        a.eq(cash+gross-allowance, deposits+debt+equity, 'double-entry balance')
        a.eq(cash, Q(18), 'provision and allowance use create no cash')
    a.eq(after_provision[1]-after_provision[2], after_chargeoff[1]-after_chargeoff[2], 'net loans unchanged by covered chargeoff')
    expected.update(allowance_after_provision=after_provision[2], assets_after_provision=sum(after_provision[:2])-after_provision[2],
                    equity_after_provision=after_provision[-1], gross_after_chargeoff=after_chargeoff[1],
                    allowance_after_chargeoff=after_chargeoff[2])
    for theta in (Q(0), Q(99, 1000), Q(1, 10), Q(101, 1000), Q(199, 1000), Q(1, 5), Q(201, 1000), Q(1, 4)):
        law = dependence(theta)
        a.eq(sum(p for _, p in law), Q(1), 'dependence distribution sums to one')
        a.eq(sum(loss*p for loss, p in law), Q(3), 'fixed marginal mean')
        var, es = tail_by_quantile_intervals(law, Q(4, 5))
        a.eq(es, 6+30*theta if theta <= Q(1, 5) else Q(12), 'quantile integral versus two ES branches')
        a.eq(es <= 9, theta <= Q(1, 10), 'sharp ES policy set')
        if theta == Q(1, 5): expected.update(var_boundary=var, es_boundary=es)
    expected.update(loss_mean=Q(3), theta_limit=Q(9-6, 30))
    a.interventions += 2  # Risk-limit and tail-atom boundaries, not a fuzz grid.
    eve = Q(120+80-100-50); change = Q(-4*120+2*100, 100)
    expected.update(eve_open=eve, eve_change=change, eve_after=eve+change,
                    nii_change=Q(80-50, 100), alm_cash_gap=Q(8-5))
    a.yes(change < 0 < expected['nii_change'], 'opposite value and annual income directions')
    a.eq(-change, Q(14, 5), 'signed liability sensitivity contributes positively')
    c, pa, pb = Q(1, 25), Q(2, 25), Q(3, 25)
    conditional_a, conditional_b = (pa-c)/(1-c), (pb-c)/(1-c)
    residual_joint = (1-c)*conditional_a*conditional_b
    joint = c+residual_joint
    expected.update(route_a_conditional=conditional_a, route_b_conditional=conditional_b,
                    route_joint=joint, route_posterior=c/joint, route_false_product=pa*pb)
    a.eq((1-c)*conditional_a+c, pa, 'route A total probability')
    a.eq((1-c)*conditional_b+c, pb, 'route B total probability')
    a.yes(joint > pa*pb, 'common-cause positive dependence')
    a.eq((pa-pa)/(1-pa), Q(0), 'common event at smaller marginal leaves no residual A failure')
    a.eq(pa/(pa+(1-pa)*Q(0)*(pb-pa)/(1-pa)), Q(1), 'boundary posterior one')
    a.interventions += 1
    gate, end = Q(3, 10), Q(1, 2)
    left = Q(16)-32*gate
    expected.update(reverse_left_limit=left, reverse_at_jump=dated_headroom(gate), reverse_first=gate,
                    stale_boundary=Q(16, 32), reverse_min_headroom=dated_headroom(end),
                    reverse_required_cash=-dated_headroom(end))
    for x in (Q(0), gate-Q(1, 1000), gate, gate+Q(1, 1000), end, Q(1)):
        a.eq(dated_headroom(x) < 0, x >= gate, 'actual attained failure boundary')
        a.eq(Q(16)-32*x < 0, x > end, 'stale model continuous boundary')
    # Both branches have derivative -32; their minima are endpoints or one-sided limits.
    a.eq((left+12, dated_headroom(gate, cash=Q(12)), dated_headroom(end, cash=Q(12))),
         (Q(92, 5), Q(32, 5), Q(0)), 'whole interval certificate including timing jump')
    a.eq(dated_headroom(end, cash=Q(1199, 100)), Q(-1, 100), 'underfunded boundary rejects')
    a.eq(dated_headroom(end, gate=Q(3, 5)), Q(0), 'gate after requested range needs no contribution')
    a.interventions += 2
    states = [(Q(3, 10), 1, Q(45), Q(20)), (Q(1, 2), 2, Q(55), Q(20)), (Q(1, 5), 2, Q(30), Q(8))]
    pension = [pension_row(n, assets, available) for _, n, assets, available in states]
    for (_, _, assets, available), row in zip(states, pension):
        a.eq(row[3]+row[6]+row[7], assets+available, 'pension recipient conservation in each state')
        a.eq(row[3]+row[5], row[0], 'paid and unpaid benefits exhaust promise')
    means = [sum(prob*row[k] for (prob, *_), row in zip(states, pension)) for k in range(8)]
    expected.update(pension_bad_guarantee=pension[2][2], pension_bad_benefit=pension[2][3],
                    pension_bad_per_member=pension[2][4], pension_bad_unpaid=pension[2][5],
                    pension_expected_promise=means[0], pension_expected_benefit=means[3],
                    pension_expected_unpaid=means[5], pension_expected_guarantee=means[2])
    a.eq(pension_row(2, Q(30), Q(30))[5], Q(10), 'guarantor resources alone do not change cap')
    a.eq(pension_row(2, Q(30), Q(30), Q(30))[5], Q(0), 'both cap and resources permit full benefits')
    a.interventions += 1
    grant, borrow, first, final, home = sovereign_plan()
    a.eq((first, final), (Q(0), Q(0)), 'grant minimizer funds both dates with carry')
    a.eq(grant*11, Q(6), 'nonnegative inequality certificate attains bound')
    for B in (Q(0), Q(6), Q(7)):
        first_without = Q(19)+B-25
        last_without = first_without+18-12-Q(11, 10)*B
        a.eq(last_without, -B/10, 'borrowing carry retained exactly')
        a.yes(first_without < 0 or last_without < 0, 'no grant cannot fund both dates')
    expected.update(sovereign_H_left=home, sovereign_F_before=Q(9+8+2), sovereign_no_grant_gap=Q(6, 10),
                    sovereign_min_grant=grant, sovereign_borrow_at_min=borrow)
    a.eq(sovereign_plan(cap=Q(5))[:4], (Q(1), Q(5), Q(0), Q(1, 2)), 'borrowing cap becomes binding')
    a.eq(sovereign_plan(gross=Q(1))[:4], (Q(0), Q(6), Q(0), Q(0)), 'zero-interest carry is feasible')
    a.eq(sovereign_plan(conversion=Q(1))[:4], (Q(17, 11), Q(60, 11), Q(0), Q(0)), 'tighter conversion changes funded grant')
    a.interventions += 3
    for face in (Q(0), Q(6), Q(9), Q(100)):
        payoff = Q(2, 3)*6 + Q(1, 3)*(6-min(face, Q(9)))
        a.yes(payoff >= 3, 'face amount cannot circumvent collectible penalty cap')
    weak = Q(6, 9)
    expected.update(conduct_floor_payoff=Q(6)-Q(1, 3)*9, conduct_weak_detection=weak)
    a.eq(6-weak*9, Q(0), 'weak deterrence permits indifference')
    a.yes(6-(weak+Q(1, 100))*9 < 0, 'strict deterrence with effective probability increase')
    a.eq(6-Q(9, 10)*8, Q(-6, 5), 'smaller collectible fine can deter at sufficient probability')
    a.eq(6-Q(1)*5, Q(1), 'a fine below gain cannot deter even with certain detection')
    a.interventions += 1
    good = priority_estates(Q(54), Q(0)); bad = priority_estates(Q(57, 2), Q(0))
    expected.update(issuer_notes_after_conversion=Q(40-12), issuer_equity_after_conversion=Q(8+12),
                    client_early_gap=Q(8-1-6), issuer_good_equity=good[2], client_good_equity=good[5],
                    client_bad_late=bad[1], public_bad_loss=bad[4], network_impairment=Q(12)-6-bad[1])
    gmin = Q(1)-bad[1]-Q(2, 5)
    repaired = priority_estates(Q(57, 2), gmin); good_repaired = priority_estates(Q(54), gmin)
    expected.update(private_min_contribution=gmin, public_reduced_bridge=1-gmin,
                    public_reduced_loss=repaired[4], public_reduced_terminal_cash=repaired[6],
                    client_grant_good_equity=good_repaired[5])
    a.eq(repaired[4], Q(2, 5), 'public loss equality at minimum private contribution')
    a.yes(priority_estates(Q(57, 2), gmin-Q(1, 1000))[4] > Q(2, 5), 'strictly smaller private cash fails mandate')
    for asset, gift in ((Q(54), Q(0)), (Q(57, 2), Q(0)), (Q(54), gmin), (Q(57, 2), gmin), (Q(28), Q(1, 5))):
        notes, late, issuer_eq, paid, loss, client_eq, public_cash = priority_estates(asset, gift)
        a.eq(notes+late+issuer_eq, asset, 'issuer priority tranches conserve estate')
        a.eq(8+notes+issuer_eq+client_eq+public_cash, 8+asset+gift, 'separate funded accounts and all recipients reconcile')
        a.eq(Q(12)-6-late, 5+gift-client_eq+loss, 'network claim impairment allocated once')
        a.eq(public_cash, 1-loss, 'undrawn public money remains with public vehicle')
        a.eq(1+6+gift+(1-gift)-8, 0, 'dated client supplier payment funded before cutoff')
    a.interventions += 2
    # Check every numeric cell in the prompt pension table and all three answer tables.
    a.eq(len(doc.tables), 5, 'coverage, supplied state and three solution tables')
    numeric = lambda row: tuple(Q(cell.replace('−', '-')) for cell in row[1:])
    a.eq([numeric(row) for row in doc.tables[1][1:]], [tuple(row) for row in states], 'all supplied pension state data')
    a.eq([numeric(row) for row in doc.tables[2][1:]], old+amended, 'all contractual principal, interest and service cells')
    a.eq([numeric(row) for row in doc.tables[3][1:]], pension, 'all pension state solution cells')
    expected_resolution = [(Q(54),)+good[:6], (Q(57, 2),)+bad[:6]]
    a.eq([numeric(row) for row in doc.tables[4][1:]], expected_resolution, 'all issuer/client/public waterfall cells')
    a.eq(set(doc.numbers), set(expected), 'exact set of printed anchors')
    for name, value in expected.items():
        a.eq(Q(doc.numbers[name].strip().replace('−', '-')), value, 'independent printed anchor ' + name)
    a.reject(lambda: dependence(Q(251, 1000)), 'impossible joint probability')
    a.reject(lambda: tail_by_quantile_intervals([(Q(0), Q(1))], Q(1)), 'empty ES tail')
    a.reject(lambda: dated_headroom(Q(-1, 100)), 'outside severity range')
    a.reject(lambda: pension_row(0, Q(30), Q(30)), 'zero survivor denominator')
    a.reject(lambda: sovereign_plan(conversion=Q(3)), 'unavailable currency conversion')
    a.reject(lambda: priority_estates(Q(54), Q(21, 100)), 'unpermitted contribution menu')
    return len(expected)


def structure_and_bindings(a, verify_bindings):
    doc = Reader(); doc.feed((ROOT/HTML).read_text()); doc.close()
    a.eq(doc.stack, [], 'complete fragment structure')
    a.eq(doc.points, POINTS, 'thirteen exact scored prompts')
    a.eq(set(doc.answers), set(POINTS), 'every prompt has exactly one solution')
    a.eq(len(doc.ids), len(set(doc.ids)), 'unique IDs')
    a.yes(all(i in ('form-b', 'solutions-b') or i.startswith('v11-b-') for i in doc.ids), 'scoped ID namespace')
    a.eq(doc.headings[0], 'h2', 'assessment heading starts at h2')
    a.yes('h1' not in doc.headings, 'no extra document title')
    a.eq(sum(doc.points.values()), 100, 'total score')
    for q in range(1, 6):
        a.eq(sum(v for k, v in doc.points.items() if k.startswith('v11-b-q'+str(q))), 20, 'equal essential domain')
    for target, points in POINTS.items():
        a.yes(str(points)+' points:' in doc.answers[target], 'explicit answer scoring '+target)
    a.yes({f'v11-c{i:02}.html' for i in range(1, 13)} <= set(doc.links), 'all twelve taught chapter routes')
    a.yes(all(not url.startswith(('chapters/', 'projects/')) for url in doc.links), 'flat reader routes')
    sources = strict((ROOT/SOURCES).read_text())
    a.eq(set(doc.sources), SOURCE_IDS, 'cited method scope')
    a.eq({row['id'] for row in sources['reused_sources']}, SOURCE_IDS, 'source records and manuscript agree')
    a.eq(len(sources['reused_sources']), 7, 'no duplicate source records')
    a.eq(sources['proposals'], [], 'no new unsupported primary claims')
    author = strict((ROOT/AUTHOR).read_text())
    rows = author['reviewed_hashes']
    a.eq({r['path'] for r in rows}, {HTML, AUTHOR_CODE, SOURCES}, 'exact three author nonself bindings')
    a.eq(len(rows), 3, 'author binding membership')
    for row in rows:
        body = (ROOT/row['path']).read_bytes()
        a.eq((len(body), sha256(body).hexdigest()), (row['bytes'], row['sha256']), 'author byte binding')
    if verify_bindings:
        peer = strict((ROOT/REVIEW).read_text())
        rows = peer['reviewed_hashes']
        a.eq({r['path'] for r in rows}, set(AUTHORED) | {SELF}, 'four author payloads and own checker')
        a.eq(len(rows), 5, 'exact five peer nonself bindings')
        for row in rows:
            body = (ROOT/row['path']).read_bytes()
            a.eq((len(body), sha256(body).hexdigest()), (row['bytes'], row['sha256']), 'peer byte binding')
        a.eq({row['prompt'] for row in peer['prompt_solution_audit']}, set(POINTS), 'all thirteen recorded prompt audits')
    return doc


def isolated(a):
    with tempfile.TemporaryDirectory(prefix='v11-form-b-peer-') as temp:
        root = Path(temp)
        for relative in PACKAGE:
            dest = root/relative; dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT/relative, dest)
        a.eq(sum(p.is_file() for p in root.rglob('*')), 6, 'only six portable payloads')
        program = ('import contextlib,io,json,runpy; s=io.StringIO()\n'
                   'with contextlib.redirect_stdout(s),contextlib.redirect_stderr(s):\n'
                   ' m=runpy.run_path('+repr(str(root/SELF))+'); r=m["check"](portable=False)\n'
                   'if s.getvalue(): raise ValueError("nonquiet portable peer API")\n'
                   'print(json.dumps(r,sort_keys=True,allow_nan=False))')
        summaries = []
        for option in ([], ['-O']):
            result = subprocess.run([sys.executable, '-I', '-B']+option+['-c', program],
                                    cwd='/', capture_output=True, text=True, timeout=30)
            a.eq(result.returncode, 0, 'isolated normal/optimized peer exit')
            a.eq(result.stderr, '', 'isolated stderr')
            summary = strict(result.stdout); a.eq(summary['status'], 'passed', 'isolated peer gates')
            summaries.append(summary); a.portable += 1
        a.eq(summaries[0], summaries[1], 'isolated normal and optimized evidence match')
        a.eq(sum(p.is_file() for p in root.rglob('*')), 6, 'portable API does not add files')


def check(portable=True, verify_bindings=True):
    a = Audit()
    doc = structure_and_bindings(a, verify_bindings)
    anchors = independent_finance(a, doc)
    for bad in ('{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}', '{"x":-Infinity}'):
        a.reject(lambda text=bad: strict(text), 'strict JSON')
    stream = StringIO()
    with redirect_stdout(stream), redirect_stderr(stream):
        author = runpy.run_path(str(ROOT/AUTHOR_CODE))['check']()
    a.eq(stream.getvalue(), '', 'quiet author check as integration only')
    a.eq((author['status'], author['points'], author['scored_subparts']), ('passed', 100, 13), 'author integration gates')
    if portable:
        require(verify_bindings, 'portable package needs final peer bindings')
        isolated(a)
    result = dict(component='v11-exam-b-peer', status='passed', independent_comparisons=a.comparisons,
                  scored_subparts=13, solved_subparts=13, printed_numeric_anchors=anchors,
                  complete_numeric_tables=4, points=100, essential_domains=5, chapter_outcomes=12,
                  focused_interventions=a.interventions, oracle_domain_and_strict_json_rejections=a.rejections,
                  author_nonself_bindings=3, author_payload_bindings=4 if verify_bindings else 0,
                  peer_checker_binding=bool(verify_bindings), portable_runs=a.portable,
                  author_integration_comparisons=author['comparisons'],
                  method='Independent cash prefixes, double-entry vectors, quantile-interval integration, branch bounds, one-dimensional funding envelope and cumulative priority tranches; author check is integration only.',
                  limits='Finite supplied contracts; local duration approximation; no real settlement, empirical frequency, national authority, psychometric equating, human certification or rendered QA.')
    strict(json.dumps(result, allow_nan=False))
    return result


if __name__ == '__main__':
    print(json.dumps(check(), sort_keys=True, allow_nan=False))
