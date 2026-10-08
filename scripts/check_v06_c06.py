"""Exact independent audit of v06-c06 money/bank/operating-model cases.

Uses independent complete closing ledgers rather than trusting lab totals;
quadratic certificates, all rate branches, break-even inequalities and exact
state-contingent real returns. Finite grids supplement separately read proofs.
Standard library only; check() is quiet and directly JSON serializable.
"""
from contextlib import redirect_stdout
from copy import deepcopy
from fractions import Fraction as F
from html.parser import HTMLParser
from io import StringIO
from itertools import product
from pathlib import Path
import ast
import json
import runpy

ROOT = Path(__file__).resolve().parents[1]
CHAPTER = ROOT / 'content/chapters/v06-c06.html'
SOURCES = ROOT / 'content/reviews/v06-c06-sources.json'
LAB = ROOT / 'content/projects/v06-c06-ledger.py'
README = ROOT / 'content/projects/v06-c06-README.txt'
BANK_KEYS = ('R', 'S', 'L', 'IB_asset', 'D', 'IB_debt', 'CB_debt', 'E')
CB_KEYS = ('S', 'advance_A', 'R_A', 'R_B', 'C', 'E')


def require(condition, message):
    if not condition:
        raise ValueError(message)


class Structure(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.lists, self.ids, self.sources, self.links, self.words = [], [], [], [], [], []
        self.worked = self.exercises = self.solutions = self.blocks = self.h1 = 0
        self.in_solutions = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag not in ('br', 'hr', 'img', 'input', 'meta', 'link'):
            self.stack.append(tag)
        self.h1 += tag == 'h1'
        if 'id' in attrs:
            self.ids.append(attrs['id'])
        if 'data-source' in attrs:
            self.sources.append(attrs['data-source'])
        if tag == 'a':
            self.links.append(attrs.get('href', ''))
        self.worked += tag == 'aside' and attrs.get('class') == 'worked'
        if tag == 'details' and attrs.get('class') == 'solutions':
            self.in_solutions = True
            self.blocks += 1
        if tag == 'ol':
            self.lists.append(attrs.get('class'))
        if tag == 'li' and self.lists:
            self.exercises += self.lists[-1] == 'exercises'
            self.solutions += self.in_solutions

    def handle_endtag(self, tag):
        require(self.stack and self.stack.pop() == tag, 'unbalanced HTML: ' + tag)
        if tag == 'ol':
            self.lists.pop()
        if tag == 'details':
            self.in_solutions = False

    def handle_data(self, data):
        self.words.extend(data.split())


def balance_reference(a, b, cb):
    """Construct a full expected book, checking counterparties independently."""
    book = {'A': dict(zip(BANK_KEYS, map(F, a))), 'B': dict(zip(BANK_KEYS, map(F, b))),
            'CB': dict(zip(CB_KEYS, map(F, cb)))}
    for name in ('A', 'B'):
        bank = book[name]
        require(sum(bank[k] for k in BANK_KEYS[:4]) == sum(bank[k] for k in BANK_KEYS[4:]),
                'independent expected bank balance: ' + name)
    central = book['CB']
    require(central['S'] + central['advance_A'] == sum(central[k] for k in CB_KEYS[2:]),
            'independent expected central balance')
    require(book['A']['R'] == central['R_A'] and book['B']['R'] == central['R_B'], 'reserve matching')
    require(book['A']['IB_debt'] == book['B']['IB_asset'] and
            book['B']['IB_debt'] == book['A']['IB_asset'], 'interbank matching')
    require(book['A']['CB_debt'] == central['advance_A'] and book['B']['CB_debt'] == 0,
            'advance matching')
    return book


def verify_snapshot(snapshot, expected):
    actual = {name: {k: F(v) for k, v in accounts.items()}
              for name, accounts in snapshot['accounts'].items()}
    require(actual == expected, 'all expected accounts: ' + snapshot['label'])
    R = expected['A']['R'] + expected['B']['R']
    D = expected['A']['D'] + expected['B']['D']
    L = expected['A']['L'] + expected['B']['L']
    C = expected['CB']['C']
    S = expected['A']['S'] + expected['B']['S']
    E = expected['A']['E'] + expected['B']['E']
    cb_debt = expected['A']['CB_debt'] + expected['B']['CB_debt']
    totals = {'reserves': R, 'deposits': D, 'customer_loans': L, 'public_currency': C, 'M': D + C, 'H': R + C}
    require({k: F(v) for k, v in snapshot['totals'].items()} == totals, 'monetary totals')
    bank_consolidation = {'assets': R + S + L, 'deposits': D, 'central_bank_debt': cb_debt, 'equity': E}
    all_consolidation = {'assets': S + expected['CB']['S'] + L, 'public_deposits': D,
                         'public_currency': C, 'equity': E + expected['CB']['E']}
    require({k: F(v) for k, v in snapshot['consolidated_banks'].items()} == bank_consolidation,
            'independent commercial-bank consolidation')
    require({k: F(v) for k, v in snapshot['consolidated_banks_and_CB'].items()} == all_consolidation,
            'independent banks plus central-bank consolidation')
    require(bank_consolidation['assets'] == D + cb_debt + E, 'bank consolidation balanced')
    require(all_consolidation['assets'] == D + C + E + expected['CB']['E'], 'all consolidation balanced')
    return {key: str(value) for key, value in totals.items()}


def liquidity_choice(v, h, wealth, q):
    """Enumerate endpoints and feasible stationary point of strict quadratic."""
    require(v >= 0 and h > 0 and wealth >= 0, 'liquidity model domain')
    stationary = (v - q) / h
    candidates = {F(0), wealth}
    if 0 <= stationary <= wealth:
        candidates.add(stationary)
    value = lambda m: (v - q) * m - h * m * m / 2
    optimum = max(candidates, key=value)
    require(all(value(optimum) > value(other) for other in candidates if other != optimum),
            'strict quadratic unique optimum')
    return optimum


def operating_rate(base, saturation, slope, floor, ceiling, cap=None):
    """Solve demand/facility regimes with minimum required facility use."""
    require(base >= 0 and saturation > 0 and slope > 0 and -1 < floor <= ceiling, 'rate model domain')
    require(cap is None or cap >= 0, 'facility cap domain')
    required_at_ceiling = saturation - (ceiling - floor) / slope
    necessary = max(F(0), required_at_ceiling - base)
    facility = necessary if cap is None else min(necessary, cap)
    total = base + facility
    rate = floor + slope * max(saturation - total, F(0))
    return facility, total, rate


def loan_quote(funding, cost, probability, recovery):
    require(funding >= 0 and cost >= 0 and 0 <= probability < 1 and 0 <= recovery <= 1,
            'loan model domain')
    return (1 + funding + cost - probability * recovery) / (1 - probability) - 1


def check():
    checks, results = [], {}
    text = CHAPTER.read_text(encoding='utf-8')
    html = Structure()
    html.feed(text)
    require(not html.stack and html.h1 == 0, 'balanced static fragment')
    require(html.worked == 4 and html.exercises == html.solutions == 8 and html.blocks == 1,
            'four worked cases/eight solution pairs')
    require(len(set(html.ids)) == len(html.ids) and all(i.startswith('v06-c06-') for i in html.ids),
            'unique scoped identifiers')
    require({'v06-c01.html', 'v06-c04.html', 'v06-c05.html', 'v06-c07.html'}.issubset(html.links),
            'prerequisite and written successor routes')
    require(all(phrase in text for phrase in ('Teach-back', 'Delayed check', 'Delayed-check answer')),
            'answered teaching gates')
    sources = json.loads(SOURCES.read_text(encoding='utf-8'))
    require(len(sources) == len(set(s['id'] for s in sources)) == 4, 'four unique primary method sources')
    require(set(s['id'] for s in sources) == set(html.sources), 'source-ID alignment')
    for source in sources:
        require(set(source) == {'id', 'title', 'url', 'use', 'checked', 'verification'}, 'source schema')
        require(source['id'].startswith('v06-c06-') and source['url'] in html.links and
                source['checked'] == '2026-10-08', 'source prefix/date/link')
    for asset in (LAB, README):
        require(asset.exists() and asset.name in html.links and 'projects/' + asset.name not in html.links,
                'flat download exists')
    ast.parse(LAB.read_text(encoding='utf-8'))
    require('Alternative branches DO NOT follow one another' in README.read_text(encoding='utf-8'), 'branch scope documented')
    results['structure'] = {'worked': html.worked, 'exercises': html.exercises, 'solutions': html.solutions,
                            'text_words': len(html.words), 'sources': len(sources),
                            'downloads': [LAB.name, README.name]}
    checks.append('static fragment, scoped IDs, 4 worked/8 solved exercises, teaching gates, source alignment and flat assets')

    v, h, w = F(2, 25), F(1, 500), F(30)
    q = (F(3, 50) - F(1, 50)) / 1
    optimum = liquidity_choice(v, h, w, q)
    require((q, optimum, 2 * optimum) == (F(1, 25), F(20), F(40)), 'worked money-demand optimum/units')
    require((v - q) * optimum - h * optimum ** 2 / 2 == F(2, 5), 'worked variable benefit')
    require(liquidity_choice(v, h, w, F(3, 50)) == 10, 'bill-only rate rise')
    require((F(4, 50) - F(2, 50)) == q, 'equal rate changes cancel spread')
    require(liquidity_choice(v, h, w, F(2, 25)) == 0 and liquidity_choice(v, h, w, F(0)) == 30,
            'zero and wealth corners')
    demand_cases = comparisons = 0
    for benefit, curvature, wealth, spread in product(
            (F(0), F(2, 25), F(3, 25)), (F(1, 1000), F(1, 500)),
            (F(0), F(12), F(30)), (F(-1, 50), F(0), F(1, 50), F(3, 50), F(2, 25), F(3, 25))):
        best = liquidity_choice(benefit, curvature, wealth, spread)
        peak = (benefit - spread) / curvature
        require(best == min(wealth, max(F(0), peak)), 'clipped form versus candidate optimization')
        for j in range(33):
            point = wealth * F(j, 32)
            objective = (benefit - spread) * point - curvature * point * point / 2
            complete_square = (benefit - spread) ** 2 / (2 * curvature) - curvature * (point - peak) ** 2 / 2
            require(objective == complete_square, 'global completed-square identity')
            best_value = (benefit - spread) * best - curvature * best * best / 2
            require(best_value >= objective, 'feasible objective comparison')
            comparisons += 1
        demand_cases += 1
    inferred_q = v - h * 15
    bill_rate = F(1, 50) + F(11, 10) * inferred_q
    require((inferred_q, bill_rate) == (F(1, 20), F(3, 40)), 'exercise 1 real opportunity cost and nominal spread')
    require(liquidity_choice(v, h, F(12), inferred_q) == 12 and v - h * 12 == F(7, 125),
            'exercise 1 corner/inference interval')
    for spread in (F(j, 1000) for j in range(101)):
        require((liquidity_choice(v, h, F(12), spread) == 12) == (spread <= F(7, 125)),
                'complete nonnegative corner interval')
    results['money_demand'] = {'main_q': str(q), 'main_m': str(optimum), 'main_M': '40',
                               'parameter_cases': demand_cases, 'exact_point_comparisons': comparisons,
                               'exercise_1_bill_rate': str(bill_rate), 'corner_q_interval': ['0', '7/125']}
    checks.append('money-demand global quadratic certificate, interior/corners/wealth zero, price units and inferred-spread interval')

    quiet = StringIO()
    with redirect_stdout(quiet):
        lab = runpy.run_path(str(LAB))
        output = lab['benchmark']()
    require(quiet.getvalue() == '', 'lab import and benchmark are quiet')
    json.dumps(output, allow_nan=False)
    A0, B0, CB0 = (30,20,150,0,180,0,0,20), (20,40,140,0,180,0,0,20), (80,0,30,20,20,10)
    A_final, B_final, CB_final = (5,20,190,0,180,0,15,20), (60,40,140,0,220,0,0,20), (80,15,5,60,20,10)
    independent_stages = [
        ('opening', A0, B0, CB0),
        ('loan_40_at_A', (30,20,190,0,220,0,0,20), B0, CB0),
        ('B_lends_A_15', (45,20,190,0,220,15,0,20), (5,40,140,15,180,0,0,20), (80,0,45,5,20,10)),
        ('customer_pays_B_40', (5,20,190,0,180,15,0,20), (45,40,140,15,220,0,0,20), (80,0,5,45,20,10)),
        ('CB_advances_A_15', (20,20,190,0,180,15,15,20), (45,40,140,15,220,0,0,20), (80,15,20,45,20,10)),
        ('A_repays_interbank_15', A_final, B_final, CB_final),
    ]
    require(len(output['stages']) == len(independent_stages), 'six transaction stages')
    stage_totals = []
    for actual, (name, a, b, cb) in zip(output['stages'], independent_stages):
        require(actual['label'] == name, 'transaction order')
        stage_totals.append(verify_snapshot(actual, balance_reference(a,b,cb)))
    require([(x['M'], x['H']) for x in stage_totals] ==
            [('380','70'),('420','70'),('420','70'),('420','70'),('420','85'),('420','85')],
            'independent broad/base sequence')
    require(F(380,70) != F(420,70) != F(420,85), 'no constant money/base ratio in fixture')
    require(F(3,4) * 20 == 15 and 20/F(1,10)-190 == 10, 'collateral versus capital headroom')
    require(min(F(20)/F(1,10)-150, F(30)+15-5) == 40, 'opening feasible loan upper bound')
    # Exhaustively check the proposed bound on a rational grid without calling the lab.
    for loan in (F(j,2) for j in range(121)):
        capital_ok = 20 >= F(1,10) * (150 + loan)
        liquidity_ok = 30 + 15 - loan >= 5
        require((capital_ok and liquidity_ok) == (loan <= 40), 'global two-constraint feasible interval')
    independent_branches = {
        'principal_12_from_B_to_A': ((17,20,178,0,180,0,15,20), (48,40,140,0,208,0,0,20), (80,15,17,48,20,10)),
        'loss_12_at_A': ((5,20,178,0,180,0,15,8), B_final, CB_final),
        'CB_buys_20_from_B': (A_final, (80,20,140,0,220,0,0,20), (100,15,5,80,20,10)),
        'CB_buys_20_from_nonbank_at_B': (A_final, (80,40,140,0,240,0,0,20), (100,15,5,80,20,10)),
        'public_withdraws_currency_12_at_B': (A_final, (48,40,140,0,208,0,0,20), (80,15,5,48,32,10)),
        'recapitalization_49/5': ((F(74,5),20,178,0,180,0,15,F(89,5)),
                                 (F(251,5),40,140,0,F(1051,5),0,0,20), (80,15,F(74,5),F(251,5),20,10)),
        'recapitalization_59/5': ((F(84,5),20,178,0,180,0,15,F(99,5)),
                                 (F(241,5),40,140,0,F(1041,5),0,0,20), (80,15,F(84,5),F(241,5),20,10)),
    }
    require(set(independent_branches) == set(output['alternative_branches']), 'complete alternative branch set')
    branch_totals = {name: verify_snapshot(output['alternative_branches'][name], balance_reference(*book))
                     for name, book in independent_branches.items()}
    require((branch_totals['principal_12_from_B_to_A']['M'], branch_totals['loss_12_at_A']['M']) == ('408','420'),
            'principal repayment versus write-down money stocks')
    require((branch_totals['CB_buys_20_from_B']['M'], branch_totals['CB_buys_20_from_nonbank_at_B']['M']) == ('420','440'),
            'bank versus nonbank purchase deposits')
    require(branch_totals['public_withdraws_currency_12_at_B']['M'] == '420' and
            branch_totals['public_withdraws_currency_12_at_B']['H'] == '85', 'currency conversion preserves both aggregates')
    # Reject unbalanced, counterfeit-counterparty and unknown-account changes without mutating the source book.
    original = lab['opening']()
    saved = deepcopy(original)
    bad_journals = [[('A','R',1)], [('A','R',1),('A','E',1)], [('A','not_an_account',1)],
                    [('A','R',-31),('A','D',-31),('CB','R_A',-31),('CB','C',31)]]
    for bad in bad_journals:
        try:
            lab['post'](original,bad)
        except ValueError:
            pass
        else:
            raise ValueError('invalid ledger posting accepted')
        require(original == saved, 'failed journal mutated source book')
    results['bank_ledger'] = {'sequential_snapshots': len(independent_stages),
                              'alternative_snapshots': len(independent_branches),
                              'stage_money_totals': stage_totals, 'branch_money_totals': branch_totals,
                              'invalid_journals_rejected': len(bad_journals),
                              'consolidations_per_snapshot': 2}
    checks.append('independent full-bank/central-bank closing references at 6 sequential and 7 alternative stages, every counterpart and both consolidations')

    exercise2 = balance_reference((20,20,180,0,200,0,0,20), (30,40,140,0,190,0,0,20), (80,0,20,30,20,10))
    require(sum(exercise2[b]['D'] for b in ('A','B'))+20 == 410 and
            sum(exercise2[b]['R'] for b in ('A','B'))+20 == 70, 'exercise 2 monetary aggregates')
    require(exercise2['A']['R']-5 == 15 and 20/F(1,10)-180 == 20, 'exercise 2 payment versus capital capacity')
    minimum_existing = F(1,10)*178 - 8
    minimum_expansion = F(1,10)*198 - 8
    require((minimum_existing, minimum_expansion) == (F(49,5),F(59,5)), 'exercise 5 minimum equity')
    for target_loans, subscription in ((F(178), minimum_existing),(F(198),minimum_expansion)):
        require(8+subscription == F(1,10)*target_loans, 'capital repair binds')
        require(8+subscription-F(1,1000) < F(1,10)*target_loans, 'less equity fails target')
    require(F(5)+minimum_expansion == F(84,5) < 20 and F(84,5)-5 < 20, 'capital compliance does not settle full loan outflow')
    results['capital_and_exercises'] = {'opening_max_loan': '40', 'post_loan_headroom': '10',
                                       'loss_equity': '8', 'loss_loan_value': '178',
                                       'exercise_2_payment_capacity': '15', 'exercise_2_capital_headroom': '20',
                                       'recapitalization_existing': str(minimum_existing),
                                       'recapitalization_with_20_new_loans': str(minimum_expansion)}
    checks.append('capital/liquidity feasible interval, partial deposit retention, positive-equity violation and minimum recapitalizations')

    main_rate = [operating_rate(F(base),F(60),F(1,1000),F(1,100),F(1,20)) for base in (10,40,80,100)]
    require(main_rate == [(10,20,F(1,20)),(0,40,F(3,100)),(0,80,F(1,100)),(0,100,F(1,100))], 'worked reserve-market cases')
    require(operating_rate(F(80),F(60),F(1,1000),F(3,100),F(7,100)) == (0,80,F(3,100)), 'administered-rate shift at floor')
    require(operating_rate(F(50),F(60),F(1,1000),F(1,100),F(1,20)) == (0,50,F(1,50)), 'leaving ample flat region')
    market_cases = 0
    for saturation, slope, floor, width in product((F(20),F(60),F(80)), (F(1,1000),F(1,2000)),
                                                  (F(-1,100),F(0),F(1,100)), (F(0),F(1,100),F(1,20))):
        ceiling = floor + width
        prior_rate = None
        for base in map(F,range(0,121,5)):
            facility,total,rate = operating_rate(base,saturation,slope,floor,ceiling)
            require(facility >= 0 and total == base+facility and floor <= rate <= ceiling, 'facility quantity/rate bounds')
            require(facility*(ceiling-rate) == 0, 'facility ceiling complementary slackness')
            manuscript_rate = min(ceiling,floor+slope*max(saturation-base,F(0)))
            require(rate == manuscript_rate, 'direct capped-rate formula matches reserve/facility solution')
            if prior_rate is not None:
                require(rate <= prior_rate, 'rate nonincreasing in reserve base')
            prior_rate = rate
            market_cases += 1
    exercise6 = [operating_rate(F(base),F(80),F(1,2000),F(1,50),F(1,20)) for base in (10,40,100)]
    require(exercise6 == [(10,20,F(1,20)),(0,40,F(1,25)),(0,100,F(1,50))], 'exercise 6 complete rate/quantity cases')
    require(operating_rate(F(100),F(80),F(1,2000),F(3,100),F(3,50)) == (0,100,F(3,100)), 'exercise 6 parallel administered shift')
    require(operating_rate(F(10),F(80),F(1,2000),F(1,50),F(1,20),cap=F(5)) == (5,15,F(21,400)),
            'limited eligible credit breaks ceiling')
    invalid_rate_cases = [(0,60,0,0,F(1,20)),(-1,60,F(1,1000),0,F(1,20)),
                          (0,0,F(1,1000),0,F(1,20)),(0,60,F(1,1000),F(1,10),F(1,20)),
                          (0,60,F(1,1000),-1,0)]
    for args in invalid_rate_cases:
        try:
            operating_rate(*map(F,args))
        except ValueError:
            pass
        else:
            raise ValueError('invalid reserve model accepted')
    results['reserve_market'] = {'worked_cases': [[str(v) for v in row] for row in main_rate],
                                 'domain_case_comparisons': market_cases,
                                 'exercise_6_cases': [[str(v) for v in row] for row in exercise6],
                                 'limited_access_rate': '21/400', 'invalid_domain_cases_rejected':len(invalid_rate_cases)}
    checks.append('all reserve/facility branches, floor/ceiling equality and inactive ceiling, monotonicity, negative floor and limited collateral-access counterexample')

    quotes = [loan_quote(F(f),F(1,100),F(p),F(2,5))
              for f,p in ((F(1,50),F(1,20)),(F(1,100),F(1,20)),(F(1,100),F(1,10)))]
    require(quotes == [F(6,95),F(1,19),F(4,45)], 'worked break-even quotes')
    loan_cases = 0
    for funding,cost,probability,recovery in product((F(0),F(1,100),F(1,10)),(F(0),F(1,100)),
                                                   (F(0),F(1,20),F(1,10),F(9,10)),(F(0),F(2,5),F(1))):
        quote = loan_quote(funding,cost,probability,recovery)
        required = 1+funding+cost
        receipts = (1-probability)*(1+quote)+probability*recovery
        require(receipts == required and quote >= 0, 'loan break-even equality and feasible promised rate')
        for deviation in (F(-1,1000),F(1,1000)):
            gap = (1-probability)*(1+quote+deviation)+probability*recovery-required
            require(gap == (1-probability)*deviation, 'global exact quote shortfall/surplus identity')
        loan_cases += 1
    require(F(2,5) < 1+F(1,100)+F(1,100), 'p=1 no-success-payment cure')
    require(F(1) == 1+F(0)+F(0), 'p=1 full-recovery zero-cost boundary')
    realized = [F(21,20),F(21,22)]
    expected = sum(realized)/2
    ratio_of_means = F(21,20)/(1+F(1,20))
    require(expected == F(441,440) and ratio_of_means == 1 and expected-1 == F(1,440), 'uncertain exact real returns')
    require(F(110)/(1+F(1,10)) == 100 and F(110)/(1+F(1,20)) == F(2200,21), 'fixed nominal payoff prices')
    require(F(53,50)/F(51,50)-1 == F(2,51), 'delayed exact real net rate')
    require((8+72,70+10) == (80,80), 'delayed opening')
    require(8+84 == 82+10 == 92 and 1+84 == 75+10 == 85 and 6+84 == 75+5+10 == 90,
            'delayed loan/payment/advance accounts')
    require(F(10)/F(1,10)-84 == 16, 'delayed capital headroom')
    results['transmission'] = {'loan_quotes': list(map(str,quotes)), 'loan_parameter_cases':loan_cases,
                               'real_gross_states':list(map(str,realized)), 'expected_real_gross':str(expected),
                               'ratio_of_gross_means':str(ratio_of_means), 'bond_prices':['100','2200/21'],
                               'delayed_capital_headroom':'16', 'delayed_real_net':'2/51'}
    checks.append('global break-even cash-flow inequalities, certain-default boundary, state-dependent real-return expectation, bond arithmetic and complete delayed check')

    report = {'chapter':'v06-c06','status':'passed','checks':checks,'results':results,
              'limitations':[
                  'Exact calculations and finite grids supplement full manuscript/derivation/solution review; they do not certify all prose.',
                  'The ledger is a fixed transaction fixture, not a general bank-data parser, regulatory model or behavioral equilibrium.',
                  'The operating model assumes specified eligibility, collateral and frictionless outside options; the limited-access branch deliberately changes them.',
                  'The money-demand and loan-pricing laws are original synthetic assumptions; no parameters or causal policy effects are estimated.',
                  'Source schema checks accompany separately recorded actual primary passage inspection; historical regimes are not current-rate claims.',
                  'The open identification critique is evaluated by explicit reasoning criteria and separate prose review, not arithmetic.',
                  'No visual/mobile/print QA was performed; root retains dependency-ordered acceptance, shared checks and publication.'
              ]}
    json.dumps(report,allow_nan=False)
    return report


if __name__ == '__main__':
    print(json.dumps(check(),indent=2,allow_nan=False))
