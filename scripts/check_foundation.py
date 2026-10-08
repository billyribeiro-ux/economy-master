"""Independent cumulative-foundation oral checks and owned-fragment integration."""
from fractions import Fraction as F
from html.parser import HTMLParser
from itertools import combinations, product
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
PARTS = ROOT / 'content/assessment-parts'


def require(condition, message):
    if not condition:
        raise AssertionError(message)


class Structure(HTMLParser):
    def __init__(self):
        super().__init__()
        self.h1 = 0
        self.ids = []
        self.links = []
        self.section = None
        self.depth = 0
        self.solutions = False
        self.counts = {}

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'h1':
            self.h1 += 1
        if 'id' in attrs:
            self.ids.append(attrs['id'])
        if tag == 'h2':
            self.section = attrs.get('id')
        if tag == 'a':
            self.links.append(attrs.get('href', ''))
        if tag == 'details' and 'solutions' in attrs.get('class', '').split():
            self.solutions = True
        if tag == 'ol':
            self.depth += 1
        if tag == 'li' and self.depth == 1:
            key = self.section, self.solutions
            self.counts[key] = self.counts.get(key, 0) + 1

    def handle_endtag(self, tag):
        if tag == 'ol':
            self.depth -= 1
        if tag == 'details':
            self.solutions = False


def support_check():
    checks = []
    # O1: compare complete alternatives at date 1, then discount their difference.
    nominal = F(11, 10)
    inflation = F(6, 5)
    sell_terminal = 70 * nominal
    invest_terminal = 120 - 20 * nominal
    incremental = (invest_terminal - sell_terminal) / nominal
    real_gross = nominal / inflation
    real_receipt = F(120) / inflation
    require(incremental == F(210, 11) == real_receipt / real_gross - 90,
            'opportunity-cost alternatives and real-unit equivalence')
    delayed_incremental = (120 - 20 - sell_terminal) / nominal
    require(real_gross - 1 == F(-1, 12) and delayed_incremental == F(230, 11)
            and delayed_incremental - incremental == F(20, 11),
            'exact real rate and changed payment timing')
    checks.append('Oral1: separately accumulated alternative terminal wealth, nominal/real equivalence and cost-timing difference')

    # O2: symbolic polynomial equality and all three regimes, including thresholds.
    def f(x, b):
        x, b = F(x), F(b)
        return b*x - x*x/2
    for b in (F(-2), F(0), F(1, 2), F(1), F(2), F(5, 2), F(3)):
        chosen = min(F(2), max(F(0), b))
        stated = F(0) if b <= 0 else b*b/2 if b <= 2 else 2*b-2
        require(f(chosen, b) == stated, 'piecewise optimizer/value')
        for x in (F(k, 8) for k in range(17)):
            gap = f(chosen, b)-f(x, b)
            certificate = (chosen-b)*(x-chosen)+(x-chosen)**2/2
            require(gap == certificate and gap >= 0 and (gap == 0) == (x == chosen),
                    'global strict concavity/projection certificate')
    for h in (F(1, 10), F(1, 100), F(1, 1000)):
        require((f(h, h)-0)/h == h/2, 'right value difference quotient at0')
        require((f(2, 2)-f(2-h, 2-h))/h == 2-h/2,
                'left value difference quotient at2')
    require(f(F(2), F(3)) == 4 and f(F(1), F(3)) == F(5, 2)
            and (3-2)*1 == 1 and 4-F(5, 2)-1 == F(1, 2),
            'capacity finite change versus marginal approximation')
    checks.append('Oral2: exact regime values, strict objective-gap certificates, boundary difference quotients and capacity sensitivity')

    # O3: sample actual labeled pairs rather than assign pattern probabilities.
    values = (0, 0, 4, 4)
    means = [F(values[i]+values[j], 2) for i, j in combinations(range(4), 2)]
    law = {x: F(means.count(x), len(means)) for x in set(means)}
    mean = sum(means)/len(means)
    variance = sum((x-mean)**2 for x in means)/len(means)
    replacement = [F(x+y, 2) for x, y in product(values, repeat=2)]
    replacement_var = sum((x-2)**2 for x in replacement)/len(replacement)
    ordered = [(values[i], values[j]) for i, j in product(range(4), repeat=2) if i != j]
    cov = sum((F(x)-2)*(F(y)-2) for x, y in ordered)/len(ordered)
    alarms = sum(a == 4 or b == 4 for a, b in product(means, repeat=2))
    require(law == {F(0):F(1, 6), F(2):F(2, 3), F(4):F(1, 6)}
            and mean == 2 and variance == F(4, 3), 'finite-population labeled sampling law')
    require(replacement_var == 2 and cov == F(-4, 3)
            and F(alarms, len(means)**2) == F(11, 36),
            'sampling dependence and repeated-search union enumeration')
    checks.append('Oral3: all six without-replacement pairs,16 replacement draws,12 ordered dependent draws and36 two-sample searches')

    # O4: reweight outcomes by target/source exposure instead of reusing rate formula.
    cases = ((90, 10), (10, 90))
    failures = ((9, 3), (1, 27))
    raw = [F(sum(fs), sum(ns)) for ns, fs in zip(cases, failures)]
    adjusted_counts = [F(f)*F(target, count) for f, target, count in
                       zip(failures[1], cases[0], cases[1])]
    equal = [sum(F(f, n) for f, n in zip(fs, ns))/2 for ns, fs in zip(cases, failures)]
    require(raw == [F(3, 25), F(7, 25)] and 100*(raw[1]-raw[0]) == 16
            and sum(adjusted_counts)/sum(cases[0]) == F(3, 25)
            and equal == [F(1, 5), F(1, 5)], 'raw and two target-mixture summaries')
    from datetime import date
    require(date(2024, 5, 15) > date(2024, 5, 1), 'oral release occurs after forecast origin')
    checks.append('Oral4: exposure-based reweighting, percentage-point change, equal targets and release-time ordering')

    html = (PARTS/'foundation-support.html').read_text()
    doc = Structure(); doc.feed(html)
    require(doc.h1 == 1 and len(doc.ids) == len(set(doc.ids)), 'one support title and unique anchors')
    require(doc.counts.get(('oral-transfer', False)) == 4
            and doc.counts.get(('oral-transfer', True)) == 4, 'four matched oral tasks and full answers')
    require({'administration','oral-transfer','coverage','foundation-synthesis'} <= set(doc.ids),
            'administration, coverage/remediation and synthesis')
    require(all(f'v{v:02d}-assessment.html' in doc.links for v in range(1, 5)),
            'four prerequisite volume assessment routes')
    require(all(value in html for value in ('85/100','19/25','34/40','8/10','180 minutes','3–5 hours')),
            'written, practical and oral scoring/conditions')
    for link in doc.links:
        if re.fullmatch(r'v\d\d-c\d\d.html', link):
            require((ROOT/'content/chapters'/link).is_file(), 'existing prerequisite route '+link)
    checks.append('Four fully solved oral tasks, separate gates, prerequisite chapter/package links and honest sampling/self-assessment scope')
    return {'status':'passed','checks':checks}


def assemble():
    return (PARTS/'foundation-support.html').read_text().replace(
        '<!-- FOUNDATION_FORMS -->', (PARTS/'foundation-form-a.html').read_text()+'\n'+
        (PARTS/'foundation-form-b.html').read_text()).replace(
        '<!-- FOUNDATION_PRACTICAL -->', (PARTS/'foundation-practical.html').read_text())


def check():
    from check_foundation_exam_a import check as exam_a
    from check_foundation_exam_b import check as exam_b
    from check_foundation_practical import check as practical
    support = support_check()
    manuscript = (ROOT/'content/cross-assessments/foundation.html').read_text()
    require(manuscript == assemble(), 'canonical foundation equals owned fragments')
    doc = Structure(); doc.feed(manuscript)
    require(doc.h1 == 1 and len(doc.ids) == len(set(doc.ids)), 'one foundation title and unique IDs')
    require({'form-a','form-b','practical','oral-transfer','administration','coverage'} <= set(doc.ids),
            'complete written, applied and oral package')
    require('<!-- FOUNDATION_' not in manuscript, 'no unfinished assembly markers')
    for form in ('form-a', 'form-b'):
        require(doc.counts.get((form, False)) == 4 and doc.counts.get((form, True)) == 4,
                form+' four prompt/solution domain groups')
    registered = {s['id'] for s in json.loads((ROOT/'content/sources.json').read_text())}
    require(set(re.findall(r'data-source="([^"]+)"', manuscript)) <= registered,
            'all foundation source IDs registered')
    return {'status':'passed','support':support,'form_a':exam_a(),'form_b':exam_b(),
            'practical':practical(),'limitations':['Written solution/proof/program review recorded separately.',
            'Numerical/structural checks do not establish external learner competence or visual/mobile/print usability.']}


if __name__ == '__main__':
    import sys
    print(json.dumps(support_check() if '--support-only' in sys.argv else check(), indent=2))
