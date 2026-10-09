"""Independent bounded peer audit of the canonical Harbor research dossier.

Reads the frozen author quartet plus these two peer payloads, writes nothing,
and imports no author checker. Statistical oracles use cell generating counts,
exact weighted tails, and affine comparison roots rather than saved outputs.
"""
from collections import Counter
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from itertools import combinations, product
import csv
import io
import json
from pathlib import Path
import re
import sys

AUTHOR = {
    'content/chapters/v12-c12.html': (53355, 'd4aaa65c4a90654a4f14568be1f509d6a18cdc3de7462c523418982e8f305294'),
    'scripts/check_v12_c12.py': (30647, '270a31c577acc45c17ca4445537afcbea9252eec5999b220465ac3ad653b356f'),
    'content/reviews/v12-c12-sources.json': (14291, '65772a8c67264475e0f8b142831c96eff9cb88cb90a76628531b2de3c2ba2317'),
    'content/reviews/v12-c12-author.json': (17196, 'bf99c01169b3e5d91becbc2a60bfd8c3cf7d6e960fb35c838812a8200f738bae'),
}
SELF = 'scripts/check_v12_c12_peer.py'
REVIEW = 'content/reviews/v12-c12-peer.json'
SCHEMAS = {
    'frame-baseline.csv': ('unit_id', 'trial_participant', 'x_stratum'),
    'trial-assignment.csv': ('unit_id', 'a'),
    'trial-followup-cents.csv': ('unit_id', 'outcome_cents'),
    'auxiliary-notes.csv': ('unit_id', 'note_id'),
    'teaching-only-potential-outcomes.csv': ('unit_id', 'y0_cents', 'y1_cents'),
    'restricted-followup-cents.csv': ('unit_id', 'outcome_cents', 'access_status'),
}
SOURCES = {'asa-pvalues-2016', 'v04-c01-aea-data-faq',
           'v12-c12-olken-preanalysis2015', 'v12-c12-dahabreh-target2019'}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def rational(value):
    require(type(value) in (int, F), 'exact rational required; bool excluded')
    return F(value)


def sequence(values, count=None):
    require(type(values) in (tuple, list) and len(values) > 0, 'nonempty sequence')
    require(count is None or len(values) == count, 'sequence dimension')
    return tuple(rational(v) for v in values)


def average(values):
    values = sequence(values)
    return sum(values)/len(values)


def weighted(values, weights):
    values, weights = sequence(values), sequence(weights)
    require(len(values) == len(weights), 'weight dimension')
    require(all(w >= 0 for w in weights) and sum(weights) == 1, 'probability weights')
    return sum(v*w for v, w in zip(values, weights))


def moment(law):
    require(type(law) is Counter and bool(law), 'finite count law')
    require(all(type(n) is int and n > 0 for n in law.values()), 'positive integer masses')
    values = {rational(v): n for v, n in law.items()}
    total = sum(values.values())
    mu = sum(v*n for v, n in values.items())/total
    return mu, sum((v-mu)**2*n for v, n in values.items())/total


def cell_law(control, treated=None):
    """Six balanced cell records from pair sums and complementary pairs."""
    control = sequence(control, 4)
    treated = control if treated is None else sequence(treated, 4)
    records = []
    for pair in combinations(range(4), 2):
        other = tuple(i for i in range(4) if i not in pair)
        y1 = tuple(treated[i] for i in pair)
        y0 = tuple(control[i] for i in other)
        contrast = (sum(y1)-sum(y0))/2
        vhat = ((y1[0]-y1[1])**2+(y0[0]-y0[1])**2)/4
        records.append((pair, contrast, vhat))
    return tuple(records)


def combine(first, second, weights=(F(1, 2), F(1, 2))):
    weights = sequence(weights, 2)
    require(all(w >= 0 for w in weights) and sum(weights) == 1, 'cell weights')
    law, vhat_law = Counter(), Counter()
    for low, high in product(first, second):
        law[weights[0]*low[1]+weights[1]*high[1]] += 1
        vhat_law[weights[0]**2*low[2]+weights[1]**2*high[2]] += 1
    return law, vhat_law


def probabilities(law):
    moment(law)  # Validates finite integer-mass law.
    total = sum(law.values())
    two = {t: F(sum(n for s, n in law.items() if abs(s) >= abs(t)), total) for t in law}
    selected = {t: F(sum(n for s, n in law.items() if (s >= t if t >= 0 else s <= t)), total)
                for t in law}
    replay = {t: F(sum(n for s, n in law.items() if selected[s] <= selected[t]), total)
              for t in law}
    return two, selected, replay


def csv_text(kind, rows):
    require(kind in SCHEMAS, 'known schema')
    return ','.join(SCHEMAS[kind])+'\n'+''.join(','.join(str(v) for v in row)+'\n' for row in rows)


def uint(text, maximum):
    require(type(text) is str and re.fullmatch(r'0|[1-9][0-9]{0,3}', text) is not None,
            'canonical unsigned integer')
    result = int(text)
    require(result <= maximum, 'bounded integer')
    return result


def table(kind, text):
    require(kind in SCHEMAS and type(text) is str and len(text) < 10000, 'CSV type/schema')
    require(text.endswith('\n') and '\r' not in text and '\x00' not in text, 'CSV LF contract')
    try:
        rows = list(csv.reader(io.StringIO(text), strict=True))
    except csv.Error as exc:
        raise ValueError('invalid CSV') from exc
    require(rows and tuple(rows[0]) == SCHEMAS[kind], 'CSV header')
    count = 32 if kind == 'frame-baseline.csv' else 9 if kind == 'auxiliary-notes.csv' else 8
    require(len(rows) == count+1, 'CSV row count')
    result, keys = [], set()
    for row in rows[1:]:
        require(len(row) == len(SCHEMAS[kind]), 'CSV row width')
        ident = uint(row[0], 32 if kind == 'frame-baseline.csv' else 8)
        require(ident > 0, 'positive unit ID')
        key = (ident, row[1]) if kind == 'auxiliary-notes.csv' else ident
        require(key not in keys, 'duplicate primary key')
        keys.add(key)
        if kind == 'auxiliary-notes.csv':
            require(re.fullmatch(r'[A-Za-z0-9-]{1,20}', row[1]) is not None, 'note ID')
            parsed = (ident, row[1])
        elif kind == 'frame-baseline.csv':
            parsed = (ident, uint(row[1], 1), uint(row[2], 1))
        elif kind == 'trial-assignment.csv':
            parsed = (ident, uint(row[1], 1))
        elif kind == 'restricted-followup-cents.csv':
            if ident == 8:
                require(row[1:] == ['', 'withheld'], 'explicitly withheld amount')
                parsed = (ident, None, 'withheld')
            else:
                require(row[2] == 'observed', 'observed access status')
                parsed = (ident, uint(row[1], 1200), 'observed')
        else:
            parsed = (ident,) + tuple(uint(v, 1200) for v in row[1:])
        result.append(parsed)
    expected = set(range(1, 33 if kind == 'frame-baseline.csv' else 9))
    require({r[0] for r in result} == expected, 'complete primary ID coverage')
    return tuple(result)


def analyst(raw, completion=None):
    """Peer information contract: receives no oracle or saved complete-data totals."""
    require(type(raw) is dict, 'accessible input mapping')
    common = {'frame-baseline.csv', 'trial-assignment.csv', 'auxiliary-notes.csv'}
    full, restricted = 'trial-followup-cents.csv', 'restricted-followup-cents.csv'
    require(set(raw) in (common | {full}, common | {restricted}), 'exact accessible inventory')
    redacted = restricted in raw
    require((type(completion) is int and 0 <= completion <= 1200) if redacted
            else completion is None, 'explicit bounded cent completion only when restricted')
    frame = table('frame-baseline.csv', raw['frame-baseline.csv'])
    require(all(s == int(i <= 8) and x == int(i > 4 and not 9 <= i <= 14)
                for i, s, x in frame), 'fixed frame contract')
    assignments = dict(table('trial-assignment.csv', raw['trial-assignment.csv']))
    require(sum(assignments[i] for i in range(1, 5)) == 2 and
            sum(assignments[i] for i in range(5, 9)) == 2, 'balanced assignment')
    kind = restricted if redacted else full
    observed = {r[0]: r[1] for r in table(kind, raw[kind])}
    if redacted:
        observed[8] = completion
    notes = table('auxiliary-notes.csv', raw['auxiliary-notes.csv'])
    rows = tuple((i, int(i > 4), assignments[i], F(observed[i], 100)) for i in range(1, 9))
    return rows, notes


def contrasts(rows):
    return tuple(average([y for i, x, a, y in rows if x == cell and a == 1]) -
                 average([y for i, x, a, y in rows if x == cell and a == 0]) for cell in (0, 1))


def parse_json(text):
    def unique(pairs):
        out = {}
        for key, value in pairs:
            require(key not in out, 'duplicate JSON key')
            out[key] = value
        return out
    def finite(value):
        raise ValueError('nonfinite JSON')
    return json.loads(text, object_pairs_hook=unique, parse_constant=finite)


def display(value):
    if isinstance(value, tuple):
        return '('+','.join(display(v) for v in value)+')'
    return str(value).replace('-', '−')


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.ids, self.prompts, self.answers = [], set(), [], []
        self.cases, self.sources = [], set()
        self.fixtures, self.values, self.active = {}, {}, []
        self.tables, self.current_table, self.current_row, self.current_cell = [], None, None, None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        ident = a.get('id')
        if ident is not None:
            require(ident.startswith('v12-c12-') and ident not in self.ids, 'unique chapter ID')
            self.ids.add(ident)
        classes = a.get('class', '').split()
        if 'worked' in classes:
            self.cases.append(ident)
        if tag == 'li' and any('exercises' in cls for unused, cls in self.stack):
            require(ident is not None, 'exercise ID')
            self.prompts.append(ident)
        if 'data-solution-for' in a:
            require(any('solutions' in cls for unused, cls in self.stack), 'solution disclosure')
            self.answers.append(a['data-solution-for'])
        if 'data-source' in a:
            self.sources.add(a['data-source'])
        for attr, destination, expected in (('data-fixture', self.fixtures, 'pre'),
                                             ('data-calc', self.values, 'span')):
            if attr in a:
                name = a[attr]
                require(tag == expected and name not in destination, 'unique visible fixture/marker')
                destination[name] = ''
                self.active.append((destination, name, len(self.stack)))
        if tag == 'table':
            require(self.current_table is None, 'non-nested tables')
            self.current_table = []
        elif tag == 'tr':
            self.current_row = []
        elif tag in ('td', 'th'):
            self.current_cell = ''
        if tag not in ('br', 'hr', 'img', 'input', 'meta', 'link'):
            self.stack.append((tag, classes))

    def handle_data(self, data):
        for destination, name, depth in self.active:
            destination[name] += data
        if self.current_cell is not None:
            self.current_cell += data

    def handle_endtag(self, tag):
        require(self.stack and self.stack[-1][0] == tag, 'balanced HTML')
        self.stack.pop()
        self.active = [a for a in self.active if a[2] < len(self.stack)]
        if tag in ('td', 'th'):
            self.current_row.append(' '.join(self.current_cell.split()))
            self.current_cell = None
        elif tag == 'tr':
            self.current_table.append(tuple(self.current_row))
            self.current_row = None
        elif tag == 'table':
            self.tables.append(tuple(self.current_table))
            self.current_table = None

    def finish(self):
        self.close()
        require(not self.stack and not self.active, 'closed document')
        expected = [f'v12-c12-e{i}' for i in range(1, 13)]
        require(self.prompts == self.answers == expected, 'twelve exact prompt/answer pairs')
        require(self.cases == [f'v12-c12-case{i}' for i in range(1, 7)], 'six worked cases')
        require(self.sources == SOURCES, 'four scoped sources')
        return self


def page(text):
    result = Page()
    result.feed(text)
    return result.finish()


class Audit:
    def __init__(self):
        self.comparisons, self.rejections = 0, 0
        self.interventions = []

    def test(self, ok, label):
        require(ok, label)
        self.comparisons += 1

    def equal(self, got, expected, label):
        self.test(got == expected, label)

    def rejects(self, action, label):
        try:
            action()
        except (ValueError, TypeError):
            self.rejections += 1
            self.comparisons += 1
        else:
            raise ValueError('not rejected: '+label)


def check(root=None):
    root = Path(root) if root is not None else Path(__file__).resolve().parents[1]
    names = tuple(AUTHOR) + (SELF, REVIEW)
    data = {name: (root/name).read_bytes() for name in names}
    audit = Audit()
    for name, (size, digest) in AUTHOR.items():
        audit.equal((len(data[name]), sha256(data[name]).hexdigest()), (size, digest),
                    'frozen author identity '+name)
    html = data['content/chapters/v12-c12.html'].decode('utf-8')
    doc = page(html)
    source = parse_json(data['content/reviews/v12-c12-sources.json'].decode('utf-8'))
    author = parse_json(data['content/reviews/v12-c12-author.json'].decode('utf-8'))
    peer = parse_json(data[REVIEW].decode('utf-8'))

    # Six raw fixtures reconstructed from declared persons, not author helpers.
    b = tuple(F(i) for i in (1, 2, 3, 4, 2, 4, 6, 8))
    effect = (F(1),)*4+(F(3),)*4
    actual_treated = {3, 4, 7, 8}
    observed = tuple(b[i]+effect[i]*int(i+1 in actual_treated) for i in range(8))
    frame = tuple((i, int(i <= 8), 0 if i <= 4 or 9 <= i <= 14 else 1) for i in range(1, 33))
    assignments = tuple((i, int(i in actual_treated)) for i in range(1, 9))
    amounts = tuple((i+1, int(y*100)) for i, y in enumerate(observed))
    notes = tuple((i, f'note-{i}') for i in range(1, 8))+((8, 'note-8a'), (8, 'note-8b'))
    potentials = tuple((i+1, int(b[i]*100), int((b[i]+effect[i])*100)) for i in range(8))
    restricted = tuple((i, amount if i != 8 else '', 'withheld' if i == 8 else 'observed')
                       for i, amount in amounts)
    fixture_rows = (frame, assignments, amounts, notes, potentials, restricted)
    fixtures = {kind: csv_text(kind, rows) for kind, rows in zip(SCHEMAS, fixture_rows)}
    audit.equal(set(doc.fixtures), set(fixtures), 'six visible CSV fixtures')
    for kind, expected in fixtures.items():
        audit.equal(doc.fixtures[kind], expected, 'visible complete fixture '+kind)
        audit.equal(len(table(kind, doc.fixtures[kind])), len(fixture_rows[list(SCHEMAS).index(kind)]),
                    'parsed complete fixture '+kind)
    common = {'frame-baseline.csv', 'trial-assignment.csv', 'auxiliary-notes.csv'}
    full = {k: v for k, v in fixtures.items() if k in common | {'trial-followup-cents.csv'}}
    limited = {k: v for k, v in fixtures.items() if k in common | {'restricted-followup-cents.csv'}}
    rows, note_rows = analyst(full)
    d = contrasts(rows)
    anchors = {'observed-contrasts': d, 'observed-primary': weighted(d, (F(1, 2),)*2),
               'trial-effect': average(effect)}
    by_id = {r[0]: r for r in rows}
    doubled = tuple(by_id[i] for i, note in note_rows)
    anchors['duplicate-pooled'] = average([r[3] for r in doubled if r[2]]) - average([r[3] for r in doubled if not r[2]])
    dd = contrasts(doubled)
    anchors['duplicate-high'] = dd[1]
    anchors['duplicate-stratified'] = weighted(dd, (F(1, 2),)*2)
    audit.equal(len(doubled), 9, 'notes are records, not persons')

    # Alternative-law generating counts built independently per stratum.
    low = cell_law(b[:4], tuple(v+1 for v in b[:4]))
    high = cell_law(b[4:], tuple(v+3 for v in b[4:]))
    trial, nv = combine(low, high)
    mu, var = moment(trial)
    base_var = tuple(sum((v-average(cell))**2 for v in cell)/3 for cell in (b[:4], b[4:]))
    actual_low = next(r for r in low if r[0] == (2, 3))
    actual_high = next(r for r in high if r[0] == (2, 3))
    anchors.update({'assignment-count': sum(trial.values()), 'baseline-stratum-variances': base_var,
                    'trial-variance': var, 'observed-neyman': (actual_low[2]+actual_high[2])/4,
                    'mean-neyman': moment(nv)[0]})
    audit.equal(mu, average(effect), 'unbiased finite trial target')
    audit.equal(var, sum(base_var)/4, 'variance via generating counts versus covariance')
    audit.equal(moment(nv)[0], var, 'Neyman expectation under constant cell effects')
    pair_choices = tuple(r[0] for r in low)
    for i in range(4):
        audit.equal(F(sum(i in pair for pair in pair_choices), 6), F(1, 2), 'marginal inclusion')
        for j in range(i+1, 4):
            audit.equal(F(sum(i in pair and j in pair for pair in pair_choices), 6)-F(1, 4),
                        -F(1, 12), 'dependent inclusion covariance')

    # Sharp-null polynomial convolution and the printed full orbit table.
    frozen_low, frozen_high = cell_law(observed[:4]), cell_law(observed[4:])
    null, unused_nv = combine(frozen_low, frozen_high)
    two, chosen, replay = probabilities(null)
    actual = anchors['observed-primary']
    total = sum(null.values())
    anchors.update({'null-variance': moment(null)[1], 'two-sided-p': two[actual],
                    'selected-p': chosen[actual],
                    'selected-size': F(sum(n for t, n in null.items() if chosen[t] <= F(1, 20)), total),
                    'selected-zero': chosen[F(0)], 'calibrated-p': replay[actual]})
    audit.equal(moment(null)[0], 0, 'sharp-null center')
    audit.test(moment(null)[1] != var != anchors['observed-neyman'], 'three different variance objects')
    for t in null:
        audit.equal(null[t], null[-t], 'complement reflected mass')
        audit.equal(replay[t], two[t], 'full chosen-direction calibration')
        audit.equal(replay[t], min(1, 2*chosen[t]), 'orbit-specific doubling identity including zero')
    for alpha in sorted(set(two.values())):
        audit.test(F(sum(n for t, n in null.items() if two[t] <= alpha), total) <= alpha,
                   'inclusive finite tied-tail validity')
    audit.equal(sum(n for t, n in null.items() if two[t] <= F(1, 20)), 0, 'no nonrandomized 5 percent rejection')
    printed_orbit = next(t for t in doc.tables if t[0][0] == 'Positive |T|')
    expected_orbit = [('Positive |T|', 'Count at +T', 'Count at −T')]
    expected_orbit += [(str(t), str(null[t]), str(null[-t])) for t in sorted(null) if t > 0]
    expected_orbit.append(('0', str(null[0])+' total'))
    audit.equal(printed_orbit, tuple(expected_orbit), 'every unmarked sharp-null table count')

    # Weak-null completion agrees with all observed records but differs away from the actual assignment.
    weak_y0, weak_y1 = list(observed), list(observed)
    weak_y1[0] += 1
    weak_y1[1] -= 1
    audit.equal(sum(a-b for a, b in zip(weak_y1, weak_y0)), 0, 'weak-zero average completion')
    audit.test(weak_y1 != weak_y0, 'weak-zero completion is not sharp zero')
    weak, unused = combine(cell_law(tuple(weak_y0[:4]), tuple(weak_y1[:4])),
                           cell_law(tuple(weak_y0[4:]), tuple(weak_y1[4:])))
    audit.test(weak != null, 'fixed-y reference not identified by weak null')
    audit.interventions.append('Observationally compatible weak-zero completion changes the assignment law')

    # Positive scaling and translations must preserve inclusive and selected ordering.
    for transformed, factor in ((tuple(y/2 for y in observed), F(1, 2)),
                                 (tuple(y+1 for y in observed), F(1))):
        law, unused = combine(cell_law(transformed[:4]), cell_law(transformed[4:]))
        audit.equal(law, Counter({t*factor: n for t, n in null.items()}), 'unit/level transfer law')
        p, s, r = probabilities(law)
        audit.equal((p[actual*factor], s[actual*factor], r[actual*factor]),
                    (two[actual], chosen[actual], replay[actual]), 'unit-invariant tails')
    all_tied, unused = combine(cell_law((7,)*4), cell_law((7,)*4))
    audit.equal(all_tied, Counter({F(0): 36}), 'all-constant complete ties')
    audit.equal(probabilities(all_tied)[0][F(0)], 1, 'all ties retained in tail')
    # Unequal score masses separately verify the finite proof beyond this symmetric example.
    unbalanced_scores = Counter({F(-2): 1, F(0): 3, F(5): 2})
    pvals = probabilities(unbalanced_scores)[0]
    for alpha in pvals.values():
        audit.test(F(sum(n for t, n in unbalanced_scores.items() if pvals[t] <= alpha), 6) <= alpha,
                   'nonuniform tied-score validity')
    audit.interventions.append('Units, common translations, complete ties and a nonuniform finite score law')

    # Target calculations from roster counts; no iid-person sampling assumption.
    counts = Counter((s, x) for i, s, x in frame)
    n_target = sum(n for (s, x), n in counts.items() if s == 0)
    target_q = tuple(F(counts[0, x], n_target) for x in (0, 1))
    participation = tuple(F(counts[1, x], counts[0, x]+counts[1, x]) for x in (0, 1))
    odds = tuple((1-p)/p for p in participation)
    weight = tuple(2*o for o in odds)
    levels = (tuple(average(cell) for cell in (b[:4], b[4:])),
              tuple(average(cell) for cell in (tuple(v+1 for v in b[:4]), tuple(v+3 for v in b[4:]))))
    pop_levels = tuple(weighted(m, target_q) for m in levels)
    totals = tuple(sum(weight[x]*y for i, x, a, y in rows if a == arm) for arm in (0, 1))
    sample_levels = tuple(t/n_target for t in totals)
    target_law, target_vhat = combine(low, high, target_q)
    target_mean, target_var = moment(target_law)
    target_observed_vhat = sum(q*q*v for q, v in zip(target_q, (actual_low[2], actual_high[2])))
    anchors.update({'participation': participation, 'inverse-odds': odds,
                    'target-levels': pop_levels, 'target-effect': pop_levels[1]-pop_levels[0],
                    'treatment-weight-total': sum(2*w for w in weight), 'weighted-outcome-totals': totals,
                    'target-sample-levels': sample_levels, 'target-sample-effect': sample_levels[1]-sample_levels[0],
                    'target-variance': target_var, 'target-neyman': target_observed_vhat,
                    'weight-diagnostic': sum(counts[1, x]*odds[x] for x in (0, 1))/n_target})
    audit.equal(target_mean, pop_levels[1]-pop_levels[0], 'target mean by design convolution')
    audit.equal(target_var, sum(q*q*v for q, v in zip(target_q, base_var)), 'target variance by covariance')
    audit.equal(moment(target_vhat)[0], target_var, 'target variance estimator expectation')
    audit.equal(n_target, 24, 'target population denominator')
    for arm in (0, 1):
        # Direct finite (I,Z) sum uses 32 persons and 36 balanced whole-vector atoms.
        expectation = F(0)
        for lp, hp in product(pair_choices, pair_choices):
            selected_ids = {i+1 for i in lp} | {i+5 for i in hp}
            contribution = F(0)
            denominator = F(0)
            for i in range(1, 9):
                if int(i in selected_ids) == arm:
                    x = int(i > 4)
                    contribution += weight[x]*(b[i-1]+arm*effect[i-1])
                    denominator += weight[x]
            audit.equal(denominator, n_target, 'every treatment-specific fixed weight total')
            expectation += contribution/F(32*36)
        audit.equal(expectation/F(n_target, 32), pop_levels[arm], 'finite (I,Z) weighting identity')
    pooled_q = tuple(F(counts[0, x]+counts[1, x], 32) for x in (0, 1))
    effects = tuple(levels[1][x]-levels[0][x] for x in (0, 1))
    anchors['pooled-population-effect'] = weighted(effects, pooled_q)
    anchors['pooled-sample-effect'] = weighted(d, pooled_q)
    audit.equal(anchors['pooled-sample-effect'], anchors['duplicate-pooled'], 'distinct errors share a number')
    audit.test(anchors['pooled-sample-effect'] != anchors['target-sample-effect'], 'target not pooled frame')
    for q in ((F(1), F(0)), (F(0), F(1))):
        law, unused = combine(low, high, q)
        x = 0 if q[0] else 1
        audit.equal(moment(law), (effects[x], base_var[x]), 'single-supported-cell target transfer')
    audit.interventions.append('Target-population change and single-cell endpoint distributions')

    shift = (F(1), F(-2))
    shifted = tuple(weighted(tuple(v+k for v, k in zip(m, shift)), target_q) for m in levels)
    anchors['shifted-levels'] = shifted
    audit.equal(shifted[1]-shifted[0], anchors['target-effect'], 'common cell shifts preserve effect only')
    audit.test(shifted != pop_levels, 'level transport fails under common shifts')
    corner = tuple(weighted(tuple(e+t for e, t in zip(effects, delta)), target_q)
                   for delta in product((F(-1, 2), F(1, 2)), (F(-1), F(1))))
    sensitivity = min(corner), max(corner)
    supported = F(1, 5)*effects[0]+F(3, 5)*effects[1]
    support_bounds = supported-F(12, 5), supported+F(12, 5)
    anchors['effect-sensitivity'] = '['+str(sensitivity[0])+','+str(sensitivity[1])+']'
    anchors['unsupported-bound'] = '['+str(support_bounds[0])+','+str(support_bounds[1])+']'
    for alpha in (F(0), F(1, 3), F(1)):
        delta = (alpha-F(1, 2), 2*alpha-1)
        audit.equal(weighted(tuple(e+t for e, t in zip(effects, delta)), target_q),
                    (1-alpha)*sensitivity[0]+alpha*sensitivity[1], 'attained effect sensitivity interpolation')
        new_means = (12*(1-alpha), 12*alpha)
        audit.equal(supported+F(1, 5)*(new_means[1]-new_means[0]),
                    (1-alpha)*support_bounds[0]+alpha*support_bounds[1], 'attained unsupported-cell mixture')
    audit.interventions.append('Effect-only transport, sharp rectangle corners and unsupported-cell endpoint mixtures')

    # Restricted information is rebuilt using retained CSV only. No oracle amount enters.
    retained = table('restricted-followup-cents.csv', fixtures['restricted-followup-cents.csv'])
    known = {i: F(amount, 100) for i, amount, access in retained if access == 'observed'}
    require(set(known) == set(range(1, 8)), 'seven retained records')
    low_counts = Counter(r[1] for r in cell_law(tuple(known[i] for i in range(1, 5))))
    # Polynomial for four times T: 2*low + 2*treated high sum - total high.
    affine = Counter()
    for l, multiplicity in low_counts.items():
        for high_pair in combinations(range(5, 9), 2):
            constant = 2*l+2*sum(known.get(i, 0) for i in high_pair)-sum(known[i] for i in (5, 6, 7))
            slope = F(1) if 8 in high_pair else F(-1)
            affine[(constant, slope)] += multiplicity
    # Solve the two signed affine comparisons directly; equality roots partition the domain.
    roots = {F(0), F(12)}
    for constant, slope in affine:
        for sign in (F(-1), F(1)):
            a, intercept = sign*slope-1, sign*constant-9
            if a != 0:
                root_value = -intercept/a
                if 0 <= root_value <= 12:
                    roots.add(root_value)
    audit.equal(sorted(roots), list(map(F, (0, 1, 2, 4, 12))), 'all affine decision breakpoints')
    def tail_at(w):
        w = rational(w)
        require(0 <= w <= 12, 'restricted outcome bound')
        return F(sum(n for (c, s), n in affine.items() if abs(c+s*w) >= 9+w), 36)
    positive_classes = Counter()
    for (c, s), n in affine.items():
        positive_classes[c*s] += n
    audit.equal({c: n for c, n in positive_classes.items() if abs(c) >= 9},
                {F(9): 2, F(-17): 2, F(-13): 4, F(-11): 4, F(-9): 4}, 'printed affine comparison classes')
    audit.equal(sum(n for c, n in positive_classes.items() if -9 < c < 9), 20, 'remaining classes never qualify')
    intervals = ((1, 100), (101, 200), (201, 400), (401, 1200))
    region_counts = Counter({tail_at(F(0)): 1})
    for lo, hi in intervals:
        midpoint = F(lo+hi, 200)
        expected_tail = tail_at(midpoint)
        audit.equal(tail_at(F(lo, 100)), expected_tail, 'first admissible cent of root region')
        audit.equal(tail_at(F(hi, 100)), expected_tail, 'inclusive upper cent of root region')
        # There are no comparison roots between these endpoints: every sign is fixed.
        audit.test(not any(F(lo, 100) < r < F(hi, 100) for r in roots), 'no hidden breakpoint')
        region_counts[expected_tail] += hi-lo+1
    audit.equal(region_counts, Counter({F(4, 9): 1, F(1, 3): 100, F(2, 9): 100,
                                       F(1, 9): 200, F(1, 18): 800}), 'all 1201 cent possibilities by root regions')
    partition_table = next(t for t in doc.tables if t[0][0] == 'CU completion')
    audit.equal(tuple((row[2], int(row[3])) for row in partition_table[1:]),
                ((str(tail_at(F(0))), 1),)+tuple((str(tail_at(F(lo, 100))), hi-lo+1) for lo, hi in intervals),
                'all printed p-partition rows')
    complete_case = tuple(r for r in rows if r[0] != 8)
    anchors.update({'completion-lattice': '{9/4+k/400:k=0,...,1200}',
                    'completion-count': sum(region_counts.values()), 'completion-envelope': '[9/4,21/4]',
                    'zero-imputation': F(9, 4), 'complete-case': weighted(contrasts(complete_case), (F(1, 2),)*2),
                    'completion-p-set': '{'+','.join(map(str, sorted(region_counts)))+'}'})
    for cents in (0, 1, 100, 101, 200, 201, 400, 401, 1200):
        completed, unused = analyst(limited, cents)
        test_stat = weighted(contrasts(completed), (F(1, 2),)*2)
        audit.equal(test_stat, F(900+cents, 400), 'explicit available-input statistic')
        law, unused = combine(cell_law(tuple(r[3] for r in completed[:4])),
                              cell_law(tuple(r[3] for r in completed[4:])))
        audit.equal(probabilities(law)[0][test_stat], tail_at(F(cents, 100)), 'convolution versus affine root tail')
    audit.equal(F(900+1200, 400)-F(900, 400), F(3), 'sharp statistic envelope length')
    audit.equal(F(901, 400)-F(900, 400), F(1, 400), 'cent-lattice step')
    audit.test(min(region_counts) > F(1, 20), 'nonrejection invariant across information-compatible completions')
    audit.interventions.append('All restricted cent cases covered by affine-root regions with inclusive boundary transfers')

    # Strict data/information checks remain live under -O; no author helper is invoked.
    shuffled = {k: v.splitlines()[0]+'\n'+'\n'.join(reversed(v.splitlines()[1:]))+'\n' for k, v in full.items()}
    audit.equal(analyst(shuffled)[0], rows, 'row order is not identity')
    for invalid in (True, False, 1.0, float('nan'), float('inf'), '1', None):
        audit.rejects(lambda invalid=invalid: rational(invalid), 'exact scalar type')
    for invalid in ((), (1, 2, 3), (1, 2, 3, True)):
        audit.rejects(lambda invalid=invalid: cell_law(invalid), 'cell domain')
    for q in ((1, 1), (-1, 2), (F(1, 2),), (True, 0)):
        audit.rejects(lambda q=q: combine(low, high, q), 'target weight domain')
    audit.rejects(lambda: analyst({**full, 'teaching-only-potential-outcomes.csv': fixtures['teaching-only-potential-outcomes.csv']}),
                  'oracle leakage into analyst world')
    audit.rejects(lambda: analyst(limited), 'unavailable outcome without completion')
    for completion in (True, 0.0, '100', -1, 1201):
        audit.rejects(lambda completion=completion: analyst(limited, completion), 'invalid restricted completion')
    audit.rejects(lambda: analyst(full, 100), 'unrequested completion in complete world')
    for amount in ('', 'NaN', '1.2', '-1', '+1', '0100', ' 100', '1201'):
        altered = dict(full)
        altered['trial-followup-cents.csv'] = full['trial-followup-cents.csv'].replace('1,100\n', '1,'+amount+'\n')
        audit.rejects(lambda altered=altered: analyst(altered), 'invalid cent representation')
    changes = (
        ('trial-followup-cents.csv', '8,1100\n', '7,1100\n'),
        ('trial-assignment.csv', '1,0\n', '1,1\n'),
        ('auxiliary-notes.csv', '8,note-8b\n', '8,note-8a\n'),
        ('frame-baseline.csv', '1,1,0\n', '1,0,0\n'),
        ('trial-followup-cents.csv', 'unit_id,outcome_cents', 'unit_id,amount'),
    )
    for kind, old, new in changes:
        altered = {**full, kind: full[kind].replace(old, new, 1)}
        audit.rejects(lambda altered=altered: analyst(altered), 'key/design/schema violation')
    bad_restricted = {**limited, 'restricted-followup-cents.csv': limited['restricted-followup-cents.csv'].replace('8,,withheld', '8,1100,withheld')}
    audit.rejects(lambda: analyst(bad_restricted, 100), 'undeclared unredacted information')
    audit.rejects(lambda: table('trial-followup-cents.csv', fixtures['trial-followup-cents.csv'].replace('\n', '\r\n')), 'CSV newline contract')
    audit.rejects(lambda: page(html.replace('id="v12-c12-e2"', 'id="v12-c12-e1"', 1)), 'duplicate exercise ID')
    audit.rejects(lambda: page(html.replace('data-solution-for="v12-c12-e1"', 'data-solution-for="v12-c12-e2"', 1)), 'incorrect pairing')
    for invalid in ('{"a":1,"a":2}', '{"a":NaN}', '{"a":Infinity}'):
        audit.rejects(lambda invalid=invalid: parse_json(invalid), 'strict JSON')
    audit.interventions.append('Accessible data inventory, cent/key/assignment restrictions and explicit invalid completions')

    audit.equal(set(doc.values), set(anchors), 'all 39 printed markers independently covered')
    for key, value in anchors.items():
        audit.equal(doc.values[key].strip(), display(value), 'printed marker '+key)
    audit.equal({s['id'] for s in source['sources']}, SOURCES, 'source scope inventory')
    audit.equal(source['source_reading_boundary']['new_primary_reads_by_this_author'], 0, 'honest author primary scope')
    asa = next(s for s in source['sources'] if s['id'] == 'asa-pvalues-2016')
    audit.test('unrecorded' in asa['actual_inspector'] and 'prior verification record' in asa['actual_inspector'],
               'ASA historical inspector limitation preserved')
    for binding in author['payload_bindings']:
        name = binding['path']
        audit.equal((binding['bytes'], binding['sha256']), AUTHOR[name], 'author nonself binding')
    audit.equal(set(peer['bindings']), set(AUTHOR) | {SELF}, 'four author plus peer checker bindings')
    for name, binding in peer['bindings'].items():
        audit.equal(binding, {'bytes': len(data[name]), 'sha256': sha256(data[name]).hexdigest()}, 'peer exact binding '+name)
    audit.equal(set(peer['exercise_audit']), {f'v12-c12-e{i}' for i in range(1, 13)}, 'twelve distinct solution judgments')
    audit.test(not peer['unresolved_findings'], 'no open substantive finding')
    summary = {'chapter': 'v12-c12', 'status': 'independent peer checks passed',
               'comparisons': audit.comparisons, 'rejections': audit.rejections,
               'intervention_groups': len(audit.interventions), 'interventions': audit.interventions,
               'worked_cases': len(doc.cases), 'solved_exercises': len(doc.answers),
               'printed_markers': len(anchors), 'visible_fixtures': len(fixtures),
               'design_atoms': total, 'restricted_completions_covered': sum(region_counts.values()),
               'restricted_method': 'Exact affine roots and constant-sign intervals, with integer-cent counts; endpoint convolution cross-checks.',
               'restricted_p_counts': {str(k): v for k, v in sorted(region_counts.items())},
               'runtime_payloads': len(names),
               'limits': 'Separate machine-assisted substantive review; no new primary-body inspection, rendered reader verification, empirical validity certification or coordinator acceptance.'}
    json.dumps(summary, allow_nan=False)
    return summary


if __name__ == '__main__':
    if len(sys.argv) != 1:
        raise SystemExit('usage: python3 -B check_v12_c12_peer.py')
    check()
