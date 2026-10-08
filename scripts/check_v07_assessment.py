"""Volume 7 assembly and independently reconstructed diagnostic/retention checks.

The specialist exam/project checkers contain separate financial reconstructions.
Recorded full solution and evidence reviews remain necessary; these checks do
not establish external certification, source applicability, or visual QA.
"""
from fractions import Fraction as F
from html.parser import HTMLParser
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARTS = ('v07-support-opening.html', 'v07-exam-a.html', 'v07-exam-b.html',
         'v07-project.html', 'v07-support-closing.html')


def require(condition, message):
    if not condition:
        raise AssertionError(message)


class Structure(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.points = {}
        self.solutions = []
        self.links = []

    def handle_starttag(self, tag, attributes):
        a = dict(attributes)
        if 'id' in a:
            self.ids.append(a['id'])
        if 'data-points' in a:
            self.points[a.get('id')] = int(a['data-points'])
        if 'data-solution-for' in a:
            self.solutions.append(a['data-solution-for'])
        if tag == 'a':
            self.links.append(a.get('href', ''))


def support_check():
    # Derive from the question inputs, preserving exact units and timing.
    old_profit, new_profit = 300-240, 360-270
    require((F(old_profit, 300), F(new_profit, 360)) == (F(1, 5), F(1, 4))
            and F(360, 300)-1 == F(1, 5)
            and F(new_profit, old_profit)-1 == F(1, 2), 'D1 margins and growth')
    require(70-90+110 == 90 and max(90-70, 0) == 20, 'D2 dated gap')
    require(140-95 == (140+20)-(95+20) == 45, 'D3 financing identity')
    require(20-11-12 == -3 and F(120, 15-9) == 20, 'D4/D5 relevant cost')
    require(F(121)/F(11, 10)**2 == 100 and F(100)*F(12, 9) == F(400, 3),
            'D6/D7 dated and period scaling')

    # R1 reconstruct every stock independently from the listed transactions.
    profit = 120-70-20-10
    ar, inv, ppe, ap, equity = 30+120-110, 20+75-70, 50-10, 25+75-60, 60+profit
    direct = 110-60-20
    indirect = profit+10-(ar-30)-(inv-20)+(ap-25)
    cash = 20+direct
    require((profit, direct, indirect) == (20, 30, 30), 'R1 cash bridge')
    require((cash, ar, inv, ppe, ap, 35, equity) == (50, 40, 25, 40, 40, 35, 80)
            and cash+ar+inv+ppe == ap+35+equity == 155, 'R1 complete close')
    dep = F(60-6, 3)
    carrying = F(100)
    debt_path = []
    for _ in range(2):
        interest = carrying*F(8, 100)
        carrying += interest-6
        debt_path.append((interest, carrying))
    require(dep == 18 and 60-dep == 42
            and debt_path == [(8, 102), (F(204, 25), F(2604, 25))], 'R2 schedules')
    group_profit = 60-14+40-6
    nci_profit = F(3, 10)*40
    dta = F(12, 4)
    require((group_profit, nci_profit, group_profit-nci_profit) == (80, 12, 68)
            and dta == 3 and -12+dta == -9, 'R3 group and deferred tax')
    buy_advantage_cu = 1800-(8-6)*500
    require(buy_advantage_cu == 800 and F(buy_advantage_cu, 1000) == F(4, 5)
            and F(30)*F(4, 5)/150 == F(4, 25), 'R4 relevant cost and matched return')
    # The cash K already includes opening-debt interest; changes occur at end-date.
    def financing(k):
        needed_draw = max(0, 15-k)
        allowed_draw = min(needed_draw, 25-10)
        return 10+needed_draw, k+allowed_draw, max(0, 15-k-allowed_draw)
    require(financing(-5) == (30, 10, 5) and financing(-5+6) == (24, 15, 0),
            'R5 financing limit and cancellation')
    require(-(75-60) == -15 and min(50, 46)-40 == 6, 'R5/R6 stock adjustments')
    return {'status': 'passed', 'groups': 7,
            'scope': 'Diagnostic arithmetic and six retention reconstructions; open evidence/oral criteria reviewed in editorial record'}


def check():
    from check_v07_exam_a import check as check_a
    from check_v07_exam_b import check as check_b
    from check_v07_project import check as check_project
    assembled = (ROOT/'content/assessments/v07.html').read_text()
    expected = '\n\n'.join((ROOT/'content/assessments/parts'/name).read_text().strip()
                           for name in PARTS)+'\n'
    require(assembled == expected, 'Volume 7 assembly is stale relative to reviewed parts')
    doc = Structure(); doc.feed(assembled)
    require(len(doc.ids) == len(set(doc.ids)), 'Duplicate assessment anchors')
    for component in ('diagnostic', 'exam-rules', 'form-a', 'solutions-a', 'form-b',
                      'solutions-b', 'project', 'oral-transfer', 'retention',
                      'notation-index', 'concept-index', 'volume-synthesis'):
        require(component in doc.ids, 'Missing component: '+component)
    require(all(f'v07-d{i}' in doc.ids for i in range(1, 9)), 'Diagnostic incomplete')
    require(all(f'v07-r{i}' in doc.ids for i in range(1, 7)), 'Retention incomplete')
    for form in ('a', 'b'):
        question_ids = {f'v07-{form}-q{n}{part}' for n in range(1, 6) for part in 'abcd'}
        require(all(doc.points.get(k) == 5 for k in question_ids), 'Exam points incomplete')
        require(sum(doc.points[k] for k in question_ids) == 100, 'Exam total')
        require(question_ids <= set(doc.solutions), 'Missing matched worked solution')
        require(all(doc.solutions.count(k) == 1 for k in question_ids), 'Repeated solution mapping')
    require(all(f'v07-c{i:02}.html' in doc.links for i in range(1, 13)), 'Incomplete chapter routes')
    return {'status': 'passed', 'assembly': 'Exact reviewed-fragment match; 40 matched five-point parts; 12 chapter routes',
            'support': support_check(), 'form_a': check_a(), 'form_b': check_b(),
            'project': check_project()}


if __name__ == '__main__':
    print(json.dumps(check(), indent=2, allow_nan=False))
