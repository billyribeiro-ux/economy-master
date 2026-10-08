"""Independent ledger and index checks for the national-accounts chapter.

All values are synthetic. Exact rational cross-valuations establish index
identities before approximate square roots. No network or third-party packages.
"""
from fractions import Fraction as F
from html.parser import HTMLParser
from itertools import product
from math import isclose, sqrt
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def dot(a, b):
    require(len(a) == len(b) and len(a) > 0, 'basket dimensions')
    return sum((F(x)*F(y) for x, y in zip(a, b)), F(0))


def fisher_squared(p0, q0, p1, q1):
    require(len(p0) == len(q0) == len(p1) == len(q1) > 0, 'basket dimensions')
    require(all(F(v) > 0 for seq in (p0, q0, p1, q1) for v in seq),
            'this positive-basket method excludes nonpositive inputs')
    v0, v1 = dot(p0, q0), dot(p1, q1)
    a, b = dot(p0, q1), dot(p1, q0)
    quantity = (a/v0)*(v1/b)
    price = (b/v0)*(v1/a)
    return quantity, price, v0, v1


def reconcile(outputs, intermediate, income_rows, expenditure, target):
    values = [F(o)-F(i) for o, i in zip(outputs, intermediate)]
    require(all(sum(map(F, row)) == va for row, va in zip(income_rows, values)),
            'industry income differs from value added')
    c, investment, government, exports, imports = map(F, expenditure)
    require(sum(values) == c+investment+government+exports-imports == F(target),
            'production/expenditure totals differ')
    return values


class Chapter(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.lists, self.ids, self.sources = [], [], [], []
        self.worked = self.exercises = self.solutions = 0
        self.solution_block = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag not in ('br', 'hr', 'img', 'input', 'meta', 'link'):
            self.stack.append(tag)
        if 'id' in attrs:
            self.ids.append(attrs['id'])
        if 'data-source' in attrs:
            self.sources.append(attrs['data-source'])
        self.worked += tag == 'aside' and 'worked' in attrs.get('class', '').split()
        if tag == 'details' and attrs.get('class') == 'solutions':
            self.solution_block = True
        if tag == 'ol':
            self.lists.append(attrs.get('class'))
        if tag == 'li' and self.lists:
            self.exercises += self.lists[-1] == 'exercises'
            self.solutions += self.solution_block

    def handle_endtag(self, tag):
        require(bool(self.stack) and self.stack.pop() == tag, 'HTML balance: '+tag)
        if tag == 'ol':
            self.lists.pop()
        if tag == 'details':
            self.solution_block = False


def check():
    chapter = (ROOT/'content/chapters/v06-c01.html').read_text()
    doc = Chapter()
    doc.feed(chapter)
    require(not doc.stack and len(doc.ids) == len(set(doc.ids)), 'HTML stack/IDs')
    require((doc.worked, doc.exercises, doc.solutions) == (3, 8, 8), 'chapter package')
    proposals = json.loads((ROOT/'content/reviews/v06-c01-sources.json').read_text())
    require(set(doc.sources) == {x['id'] for x in proposals}, 'source proposal coverage')
    require(all(x['url'].startswith('https://www.bea.gov/') and x['verification']
                for x in proposals), 'official inspected source records')

    # Rebuild both complete industry ledgers independently of their HTML tables.
    va = reconcile([60, 150, 50], [10, 60+20, 0],
                   [[30, 5, 3, 12], [50, 10, 5, 5], [20, 5, 2, 23]],
                   [80+30+25, 40+10, 20, 20, 10+20+25], 170)
    require(va == [50, 70, 50], 'worked ledger')
    require((170+8-18, 170-20, 170+8-18-20) == (160, 150, 140), 'national/net')
    government_consumption, government_investment = 16, 4
    domestic_saving = 170-135-government_consumption
    all_investment = 50+government_investment
    require((domestic_saving, all_investment) == (19, 54) and
            domestic_saving-all_investment == 20-55, 'public investment saving convention')
    exercise_va = reconcile([80, 200], [20, 80+20],
                            [[40, 5, 2, 13], [60, 15, 8, 17]],
                            [90+15, 50+10, 20, 30, 20+20+15], 160)
    require(exercise_va == [60, 100], 'exercise ledger')
    require((160+12-22, 160-20, 160+12-22-20) == (150, 140, 130), 'exercise bridge')

    # A holding gain changes an inventory balance, not production.
    opening, resale, production = F(20), F(20)*F(5, 4), F(30)
    investment, gain, closing = production-resale, resale-opening, production
    require((resale, investment, resale+investment) == (25, 5, 30), 'inventory GDP')
    require(closing-opening == investment+gain == 10, 'inventory reconciliation')
    require(12-12 == 0 and 12-10 == 2, 'old inventory sale')
    require((100+5)-100 == 5, 'imported fixed investment')

    prices, quantities = [(1, 4), (2, 2), (4, 1)], [(100, 25), (110, 50), (100, 120)]
    nominal = [dot(p, q) for p, q in zip(prices, quantities)]
    fixed = [dot(prices[0], q) for q in quantities]
    require(nominal == [200, 320, 520] and fixed == [200, 310, 580], 'basket values')
    links = [fisher_squared(prices[i], quantities[i], prices[i+1], quantities[i+1])
             for i in range(2)]
    require([v[0] for v in links] == [F(248, 125), F(143, 98)], 'quantity links')
    levels = [200.0]
    for q2, p2, v0, v1 in links:
        require(q2*p2 == (v1/v0)**2, 'exact factor reversal')
        levels.append(levels[-1]*sqrt(q2))
    require(isclose(levels[1], 281.70906978654415) and
            isclose(levels[2], 340.2951899844172), 'aggregate chain levels')
    components = [[prices[0][j]*quantities[t][j] for j in range(2)] for t in range(3)]
    require([sum(x) for x in components] == [200, 310, 580], 'single-good components')
    require(not isclose(levels[1], sum(components[1])) and
            not isclose(levels[2], sum(components[2])), 'nonadditivity counterexample')
    scale = 320/levels[1]
    rebased = [v*scale for v in levels]
    require(isclose(rebased[1], 320) and all(isclose(levels[i+1]/levels[i],
            rebased[i+1]/rebased[i]) for i in range(2)), 'reference invariance')
    require(F(120, 520) == F(3, 13) and components[2][1]/levels[2] > 1,
            'nominal share versus invalid chain share')

    q2, p2, v0, v1 = fisher_squared((2, 3), (30, 20), (3, 2), (40, 30))
    require((q2, p2, v0, v1) == (F(51, 26), F(39, 34), 120, 180), 'exercise index')
    require(q2*p2 == F(9, 4), 'exercise factor reversal')
    require(isclose(120*sqrt(q2), 168.06592113261345) and
            isclose(100*sqrt(p2), 107.1008320943125), 'exercise rounded values')
    require(F(170, 120)-1 == F(5, 12), 'fixed-base growth')

    # Exhaustive small positive baskets check algebra and time reversal across
    # changing relative prices, not only the manuscript's examples.
    case_count = 0
    for vals in product((1, 3), repeat=8):
        p0, q0, p1, q1 = (vals[i:i+2] for i in range(0, 8, 2))
        q2, p2, v0, v1 = fisher_squared(p0, q0, p1, q1)
        reverse = fisher_squared(p1, q1, p0, q0)
        require(q2*p2 == (v1/v0)**2 and q2*reverse[0] == p2*reverse[1] == 1,
                'general index identities')
        case_count += 1
    for bad in [((1,), (1, 2), (1,), (1,)), ((0,), (1,), (1,), (1,)),
                ((1,), (-1,), (1,), (1,))]:
        try:
            fisher_squared(*bad)
        except ValueError:
            pass
        else:
            raise ValueError('invalid positive-basket input accepted')

    gdp, gdi, cfc, npi = 500, 490, 40, 30-50
    measured = (gdp-gdi, gdp+npi, gdi+npi, gdp-cfc, gdi-cfc, gdi+npi-cfc)
    require(measured == (10, 480, 470, 460, 450, 430), 'measured bridges')
    for k, delta, investment, loss, expected in [(F(100), F(1, 10), 15, 0, 105),
                                                (F(80), F(1, 8), 20, 5, 85)]:
        closing = k*(1-delta)+investment-loss
        require(closing == expected, 'physical capital')
        value_change = 3*closing-2*k
        transactions = 3*investment-3*delta*k-3*loss
        holding = k*(3-2)
        require(value_change == transactions+holding, 'capital stock reconciliation')
    require(3*85-2*80 == 95 and 3*105-2*100 == 115, 'capital values')

    # Exact trade budgets and purchasing power in distinct physical goods.
    for price_import, expected_imports in [(2, 30), (3, 20)]:
        exports = F(60)
        imported = exports/price_import
        consumption = 40+imported*price_import
        require(imported == expected_imports and consumption+exports-exports == 100,
                'import-price terms-of-trade case')
    for price_output, expected in [(5, (100, 500, 250)), (4, (80, 400, 200))]:
        exports = 40*price_output
        imports_quantity = F(exports, 2)
        gdp = 100*price_output
        consumption = 60*price_output+2*imports_quantity
        require((imports_quantity, gdp, F(gdp, 2)) == expected and
                consumption+exports-2*imports_quantity == gdp, 'export-price case')
    require(sum([30, 30, 40]) == 100 and sum([20, 20, 80]) == 120, 'distribution sums')
    require(F(120, 100)-1 == F(1, 5) and F(20, 30)-1 == -F(1, 3), 'mean/median')
    require(F(108, 80) == F(90, 80)*F(12, 10) == F(27, 20), 'retention compounding')
    require((F(90, 5)/F(80, 4))-1 == -F(1, 10), 'retention per capita')
    return {'status': 'passed', 'worked_examples': doc.worked, 'solved_exercises': 8,
            'complete_industry_ledgers': 2, 'positive_basket_identity_cases': case_count,
            'invalid_basket_cases': 3, 'chain_levels': levels,
            'checks': ['industry/final-use/income reconciliation', 'inventory holding gains',
                       'national/net/discrepancy bridges', 'exact Fisher identities and chaining',
                       'nonadditivity and reference invariance', 'physical/value capital bridge',
                       'terms-of-trade budgets', 'distribution and retention calculations'],
            'limitations': ['Numerical checks supplement the separate accounting and instructional review.']}


if __name__ == '__main__':
    print(json.dumps(check(), indent=2))
