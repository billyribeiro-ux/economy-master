"""Volume 4 assessment assembly, prerequisite/retention arithmetic and integration."""
from decimal import Decimal, ROUND_HALF_UP
from fractions import Fraction as F
from html.parser import HTMLParser
import json
import math
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
PARTS = ROOT / "content/assessment-parts"


def require(condition, message):
    if not condition:
        raise AssertionError(message)


class Sections(HTMLParser):
    def __init__(self):
        super().__init__()
        self.section = None
        self.ids = []
        self.h1 = 0
        self.depth = 0
        self.in_solution = False
        self.counts = {}
        self.links = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.ids.append(attrs["id"])
        if tag == "h1":
            self.h1 += 1
        if tag == "h2":
            self.section = attrs.get("id")
        if tag == "details" and attrs.get("class") == "solutions":
            self.in_solution = True
        if tag == "ol":
            self.depth += 1
        if tag == "li" and self.depth == 1:
            key = (self.section, self.in_solution)
            self.counts[key] = self.counts.get(key, 0) + 1
        if tag == "a":
            self.links.append(attrs.get("href", ""))

    def handle_endtag(self, tag):
        if tag == "ol":
            self.depth -= 1
        if tag == "details":
            self.in_solution = False


def support_check():
    checks = []
    # Diagnostic: exact quantities, with independent state/matrix representations.
    require(F(3, 100) - F(2, 100) == F(1, 100), "percentage-point change")
    require(F(3, 2)-1 == F(1, 2), "relative percentage change")
    require(F(105)/F(105, 100) == 100 and F(11, 10)**2 == F(121, 100),
            "discount and compound periods")
    require(F(3, 4)*4+F(1, 4)*10 == F(11, 2), "target population weights")
    require(F(9, 10)*4+F(1, 10)*10 == F(23, 5), "sample mixture")
    joint = {(1, 1): F(4, 25), (1, 0): F(1, 25),
             (0, 1): F(2, 25), (0, 0): F(18, 25)}
    positive = sum(p for (event, signal), p in joint.items() if signal)
    require(sum(joint.values()) == 1 and positive == F(6, 25)
            and joint[1, 1]/positive == F(2, 3), "Bayes state enumeration")
    covariance_sum = sum(13 if i == j else 9 for i in range(25) for j in range(25))
    require(F(covariance_sum, 25**2) == F(229, 25), "common shock average")
    require(F(5)-F(196, 100) == F(76, 25)
            and F(5)+F(196, 100) == F(174, 25), "normal mean interval")
    require(tuple(a+b for a, b in zip((3, 3), (-1, 1))) == (2, 4)
            and sum(a*b for a, b in zip((3, 3), (-1, 1))) == 0,
            "orthogonal decomposition")
    require(F(7, 10)*2 == F(7, 5) and F(3, 10)*8 == F(12, 5)
            and F(2, 10) == F(1, 5), "asymmetric action costs")
    checks.append("All eight diagnostic results: exact unit/discount/mixture/Bayes/covariance/interval/projection/decision calculations")

    # Retention: independently form the normal equations and residual identities.
    require(F(100*100, 100) == 100 and F(100*121, 110) == 110
            and F(110, 100)-1 == F(1, 10), "real calendar-gap comparison")
    x, y = (0, 1, 2), (2, 2, 5)
    n, sx, sy = len(x), sum(x), sum(y)
    sxx, sxy = sum(t*t for t in x), sum(t*v for t, v in zip(x, y))
    determinant = n*sxx-sx*sx
    intercept = F(sy*sxx-sx*sxy, determinant)
    slope = F(n*sxy-sx*sy, determinant)
    fit = [intercept+slope*t for t in x]
    residual = [v-f for v, f in zip(y, fit)]
    sse = sum(r*r for r in residual)
    sst = sum((F(v)-F(sy, n))**2 for v in y)
    require((intercept, slope) == (F(3, 2), F(3, 2))
            and fit == [F(3, 2), F(3), F(9, 2)], "retention normal-equation solve")
    require(sum(residual) == 0 and sum(t*r for t, r in zip(x, residual)) == 0
            and sse == F(3, 2) and 1-sse/sst == F(3, 4), "projection checks and R2")
    values = (-2, 0, 1, 3)
    mean = F(sum(values), len(values))
    variance = (sum(F(v*v) for v in values)-len(values)*mean**2)/(len(values)-1)
    require(mean == F(1, 2) and variance == F(13, 3)
            and variance/len(values) == F(13, 12), "paired replicate moments")
    require(abs(math.sqrt(float(variance/len(values)))-1.0408329997330663) < 1e-14,
            "reported standard-error approximation")
    # Express endpoint extrapolation as affine weights on first/latest values.
    def endpoint(first_x, first_y, last_x, last_y, target):
        w = F(target-first_x, last_x-first_x)
        return (1-w)*first_y+w*last_y
    fixed = [endpoint(1, 5, 3, 6, t) for t in (4, 5)]
    updating = [fixed[0], endpoint(1, 5, 4, 10, 5)]
    def loss(predictions):
        return sum((F(actual)-p)**2 for actual, p in zip((10, 11), predictions))/2
    require(fixed == [F(13, 2), F(7)] and updating[1] == F(35, 3)
            and loss(fixed) == F(113, 8) and loss(updating) == F(457, 72),
            "fixed versus updating forecast protocol")
    ratios = [Decimal(100)*u/10000 for u in (354, 426)]
    displays = [r.quantize(Decimal('.1'), rounding=ROUND_HALF_UP) for r in ratios]
    require(ratios == [Decimal('3.54'), Decimal('4.26')]
            and displays == [Decimal('3.5'), Decimal('4.3')]
            and displays[1]-displays[0] == Decimal('.8')
            and (ratios[1]-ratios[0]).quantize(Decimal('.1')) == Decimal('.7'),
            "retention rounding-order departure")
    checks.append("All determinate retention results: independent normal-equation solve, raw-moment paired variance, affine endpoint forecasts, exact MSE and decimal rounding order")

    support = (PARTS/'v04-support.html').read_text()
    parsed = Sections(); parsed.feed(support)
    require(parsed.h1 == 1, "support has one canonical assessment title")
    require(parsed.counts.get(('diagnostic', False)) == 8
            and parsed.counts.get(('diagnostic', True)) == 8, "diagnostic matched answers")
    require(parsed.counts.get(('retention', False)) == 6
            and parsed.counts.get(('retention', True)) == 6, "retention matched answers")
    require(set(f'v04-c{i:02d}.html' for i in range(1, 13)) <= set(parsed.links),
            "all twelve chapter reference routes")
    require({'diagnostic', 'exam-rules', 'oral-transfer', 'retention', 'remediation',
             'notation-index', 'concept-index', 'volume-synthesis'} <= set(parsed.ids),
            "support components")
    require('85/100' in support and '15/20' in support and '180 minutes' in support
            and '51/60' in support and '7.5/10' in support, "criterion-based scoring")
    checks.append("Eight diagnostic and six retention solution pairs; scoring, oral/remediation and twelve-chapter notation/concept/synthesis routes")
    return {"status": "passed", "checks": checks}


def check():
    from check_v04_exam_a import check as exam_a
    from check_v04_exam_b import check as exam_b
    from check_v04_project import check as project
    support = support_check()
    assembled = (PARTS/'v04-support.html').read_text().replace(
        '<!-- ASSESSMENT_FORMS -->', (PARTS/'v04-form-a.html').read_text()+'\n'+(PARTS/'v04-form-b.html').read_text()).replace(
        '<!-- INTEGRATIVE_PROJECT -->', (PARTS/'v04-project.html').read_text())
    manuscript = (ROOT/'content/assessments/v04.html').read_text()
    require(manuscript == assembled, "canonical package equals all owned source parts")
    parsed = Sections(); parsed.feed(manuscript)
    require(parsed.h1 == 1 and len(parsed.ids) == len(set(parsed.ids)),
            "single title and unique assessment anchors")
    require({'form-a', 'form-b', 'project'} <= set(parsed.ids), "exams and project present")
    for form in ('form-a', 'form-b'):
        require(parsed.counts.get((form, False)) == 5
                and parsed.counts.get((form, True)) == 5,
                form + " has five matched domain questions and answer groups")
    require('<!-- ASSESSMENT_' not in manuscript and '<!-- INTEGRATIVE_' not in manuscript,
            "no unfinished assembly markers")
    source_ids = {s['id'] for s in json.loads((ROOT/'content/sources.json').read_text())}
    require(set(re.findall(r'data-source="([^"]+)"', manuscript)) <= source_ids,
            "assessment citations registered")
    return {"status": "passed", "support": support, "form_a": exam_a(),
            "form_b": exam_b(), "project": project(),
            "limitations": ["Written prompt/solution and empirical-inference review is separately recorded by root.",
                            "Finite numerical and structural checks do not externally assess learner competence or establish visual/mobile/print usability."]}


if __name__ == '__main__':
    import sys
    print(json.dumps(support_check() if '--support-only' in sys.argv else check(), indent=2))
