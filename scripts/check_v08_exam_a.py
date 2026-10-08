"""Independent exact reconstructions for the original Volume 8 Form A.

Import and check() are quiet; no file is written. The returned object is strict
JSON. Direct cash/claim ledgers, finite capital recurrences, alternative state
replication and contract-boundary checks complement review of the prose. These
checks do not authenticate evidence, calibrate grading or establish real law.
"""
from collections import Counter
from fractions import Fraction as F
from html.parser import HTMLParser
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
MANUSCRIPT = ROOT / 'content/assessments/parts/v08-exam-a.html'


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def capital_check():
    # Compare launch with the cash-releasing alternative, rather than pretend
    # that purchasing the already-owned land is a second current cash payment.
    equipment, working_capital, land, sunk = map(F, (160, 20, 20, 6))
    launch_cash, reject_cash = -equipment-working_capital, land
    incremental_outlay = reject_cash-launch_cash
    require(incremental_outlay == equipment+working_capital+land == 200,
            'Q1 opportunity alternative and initial capital')
    require((launch_cash-sunk)-(reject_cash-sunk) == -incremental_outlay,
            'Q1 past common cost must cancel from alternative comparison')
    rows = []
    for revenue, cost, depreciation, capex, dwc in (
            (140, 80, 20, 35, 5), (160, 96, 20, 35, 5)):
        tax = F(1, 4)*(revenue-cost-depreciation)
        direct_cash = revenue-cost-tax-capex-dwc
        nopat = revenue-cost-depreciation-tax
        before = equipment+working_capital+land
        equipment += capex-depreciation
        working_capital += dwc
        after = equipment+working_capital+land
        net_investment = after-before
        require(direct_cash == nopat-net_investment,
                'Q1 direct cash differs from earnings/capital bridge')
        rows.append((nopat, net_investment, direct_cash, after))
    require(rows == [(30, 20, 10, 220), (33, 20, 13, 240)],
            'Q1 explicit forecasts and components')
    r, g, inherited = F(9, 100), F(3, 100), rows[-1][3]
    explicit_pv = sum(row[2]/(1+r)**t for t, row in enumerate(rows, 1))
    results = []
    for return_on_capital in (F(12, 100), r):
        k, finite_pv, finite_excess_pv = inherited, F(0), F(0)
        first = None
        # Finite cash recurrence plus an exact residual checks the boundary
        # without extrapolating the explicit-period FCFF numerator.
        for t in range(1, 41):
            profit = return_on_capital*k
            reinvestment = g*k
            cash = profit-reinvestment
            if first is None:
                first = (profit, reinvestment, cash)
            finite_pv += cash/(1+r)**t
            finite_excess_pv += (return_on_capital-r)*k/(1+r)**t
            k += reinvestment
        residual = (return_on_capital-g)*k/(r-g)
        terminal = finite_pv+residual/(1+r)**40
        economic_profit_tail = (return_on_capital-r)*k/(r-g)
        require(terminal == inherited+finite_excess_pv+
                economic_profit_tail/(1+r)**40,
                'Q1 capital plus economic-profit identity')
        npv = explicit_pv+terminal/(1+r)**2-incremental_outlay
        results.append((first, terminal, npv))
    require(results == [
        ((F('28.8'), F('7.2'), F('21.6')), 360, F(1462800, 11881)),
        ((F('21.6'), F('7.2'), F('14.4')), 240, F(262800, 11881))],
        'Q1 stable continuation and economic NPV')
    for alternative_g in (F(0), g, F(6, 100)):
        require(alternative_g < r and
                (r-alternative_g)*inherited/(r-alternative_g) == inherited,
                'Q1 growth neutrality requires matched reinvestment')
    require(13*(1+g) != results[0][0][2] and
            13*(1+g) != results[1][0][2], 'Q1 obsolete terminal numerator')
    return {'new_cash_outlay': 180, 'economic_outlay': 200,
            'FCFF': [10, 13], 'end_capital': [220, 240],
            'continuation': [360, 240],
            'NPV': [str(row[2]) for row in results],
            'finite_recurrence_years': 40}


def rate_incentive_check():
    peer_equity, peer_debt = F(300), F(100)
    asset_beta = (peer_equity*F('1.4')+peer_debt*F('.2'))/(peer_equity+peer_debt)
    debt_weight, debt_beta = F('.4'), F('.1')
    equity_weight = 1-debt_weight
    equity_beta = (asset_beta-debt_weight*debt_beta)/equity_weight
    rf, premium = F('.02'), F('.06')
    equity_cost, debt_cost = rf+premium*equity_beta, rf+premium*debt_beta
    wacc = equity_weight*equity_cost+debt_weight*debt_cost
    require((asset_beta, equity_beta, equity_cost, debt_cost, wacc) ==
            (F('1.1'), F(53, 30), F('.126'), F('.026'), F('.086')),
            'Q2 peer transformation and project claim costs')
    # Reconstruct a factor exposure from state returns, independent of the
    # rearranged unlevering equation. This checks units and market weights.
    shocks = tuple(map(F, ('-.12', '-.04', '.04', '.12')))
    asset_returns = [equity_weight*(equity_cost+equity_beta*m)+
                     debt_weight*(debt_cost+debt_beta*m) for m in shocks]
    mean_return = sum(asset_returns)/len(shocks)
    covariance = sum((x-mean_return)*m for x, m in zip(asset_returns, shocks))
    require(mean_return == wacc == rf+asset_beta*premium and
            covariance/sum(m*m for m in shocks) == asset_beta,
            'Q2 aggregated state returns and operating beta')
    require(F('1.4')*F(3, 4) != asset_beta,
            'Q2 omitting debt beta must change the answer')

    state_prices = (F(3, 5), F(2, 5))
    prices = []
    for assets in ((110, 110), (30, 180)):
        debt = tuple(min(F(90), F(a)) for a in assets)
        equity = tuple(F(a)-d for a, d in zip(assets, debt))
        require(all(a == d+e for a, d, e in zip(assets, debt, equity)),
                'Q2 claim payoff conservation')
        d_value = sum(p*d for p, d in zip(state_prices, debt))
        e_value = sum(p*e for p, e in zip(state_prices, equity))
        prices.append((d_value, e_value, d_value+e_value))
    require(prices == [(90, 20, 110), (54, 36, 90)],
            'Q2 nonuniform priced gamble')
    changes = tuple(b-a for a, b in zip(prices[0], prices[1]))
    require(changes == (-36, 16, -20) and sum(changes[:2]) == changes[2],
            'Q2 wealth transfer versus resource destruction')
    unrestricted_owner = sum(prices[1][:2])
    committed_owner = sum(prices[0][:2])-8
    require((unrestricted_owner, committed_owner) == (90, 102),
            'Q2 anticipated financing and external commitment fee')
    return {'operating_beta': str(asset_beta), 'equity_beta': str(equity_beta),
            'WACC': str(wacc), 'prudent_debt_equity': [90, 20],
            'gamble_debt_equity': [54, 36],
            'prospective_owner_wealth': [90, 102]}


def payout_check():
    capacity = min(F(20), F(44)-30)
    floor, rate = F(10), F('.02')
    paths = ((F(-5), F(20)), (F(-17), F(32)))

    def calendar(distribution, operating):
        cash0, term = F(44)-distribution, F(30)
        int1 = term*rate
        before_draw = cash0+operating[0]-18-int1
        draw = max(F(0), floor-before_draw)
        cash1 = before_draw+draw
        int2, line_interest = term*rate, draw*rate
        cash2 = cash1+operating[1]+22-int2-10-line_interest-draw
        term -= 10
        # End-to-end ledger independently cancels draw and its repayment.
        require(cash2 == F(44)-distribution+sum(operating)-18+22-
                int1-int2-10-line_interest, 'Q2 full-horizon cash closure')
        feasible = (0 <= distribution <= 15 and cash0 >= floor and
                    draw <= capacity and cash1 >= floor and cash2 >= floor)
        return feasible, (cash0, before_draw, draw, cash1, cash2, term)

    feasible_grid = [F(n, 10) for n in range(151)
                     if all(calendar(F(n, 10), path)[0] for path in paths)]
    largest = max(feasible_grid)
    # The binding constraint is linear; the exact violating epsilon checks the
    # boundary beyond the grid without claiming the grid proves continuity.
    continuous_bound = F(44)+paths[1][0]-30*rate-18+capacity-floor
    require(largest == continuous_bound == F('12.4'), 'Q2 payout bound')
    require(not calendar(largest+F(1, 1000), paths[1])[0],
            'Q2 payout just beyond boundary must fail')
    rows = [calendar(largest, path)[1] for path in paths]
    require(rows == [
        (F('31.6'), 8, 2, 10, F('39.36'), 20),
        (F('31.6'), -4, 14, 10, F('39.12'), 20)],
        'Q2 quarterly cash/interest/principal calendar')
    require(rows[0][4]-rows[1][4] == (rows[1][2]-rows[0][2])*rate,
            'Q2 collection delay final interest effect')
    npv = F(22)/(1+rate)-18
    require(npv == F(182, 51) > 0 and capacity == 14,
            'Q2 investment value and effective credit capacity')
    return {'effective_revolver': 14, 'maximum_distribution': str(largest),
            'date_1_draws': [2, 14], 'date_1_cash': [10, 10],
            'date_2_cash': [str(row[4]) for row in rows],
            'project_NPV_at_date_1': str(npv),
            'tenths_grid_feasible_values': len(feasible_grid)}


def peers_option_check():
    # E,D,L,N,C, reported, rent bridge, isolated/cycle normalization delta,
    # industrial flag. Retain the software candidate even though excluded.
    inputs = (
        (250, 70, 20, 20, 10, 40, 6, 4, True),
        (360, 80, 20, 0, 20, 63, 0, -8, True),
        (500, 100, 30, 20, 20, 90, 0, -20, True),
        (200, 20, 0, 0, 20, 100, 0, 0, False),
    )
    rows, selected = [], []
    for equity, debt, lease, nci, cash, reported, rent, adjustment, industrial in inputs:
        normalized = reported+rent+adjustment
        ev = equity+debt+lease+nci-cash
        require(normalized > 0 and ev+cash == equity+debt+lease+nci,
                'Q3 positive denominator and complete claims')
        multiple = F(ev, normalized)
        rows.append((ev, normalized, multiple))
        if industrial and normalized > 0:
            selected.append(multiple)
    median = sorted(selected)[len(selected)//2]
    require(rows == [(350, 50, 7), (440, 55, 8), (630, 70, 9), (200, 100, 2)]
            and median == 8 and len(selected) == 3, 'Q3 complete peer universe')
    target_denominator = 80-8-12
    target_ev = median*target_denominator
    excluded_assets, claims = 25+10, 90+30+15
    target_equity, dcf_equity = target_ev+excluded_assets-claims, F(500)+excluded_assets-claims
    require((target_denominator, target_ev, target_equity, target_equity/20,
             dcf_equity, dcf_equity/20) == (60, 480, 380, 19, 400, 20),
            'Q3 target operating/equity bridges')

    spot, up, down, strike, gross_rf = map(F, (90, 132, 66, 100, '1.1'))
    pay_up, pay_down = max(up-strike, 0), max(down-strike, 0)
    delta = (pay_up-pay_down)/(up-down)
    loan_due = delta*down-pay_down
    loan_today = loan_due/gross_rf
    cost = delta*spot-loan_today
    require((pay_up, pay_down, delta, loan_today, cost) ==
            (32, 0, F(16, 33), F(320, 11), F(160, 11)),
            'Q3 independent option replication')
    require(delta*up-loan_due == pay_up and delta*down-loan_due == pay_down,
            'Q3 both terminal option payoffs replicated')
    q = (gross_rf*spot-down)/(up-down)
    require(0 < q < 1 and q == F(1, 2) and
            cost == (q*pay_up+(1-q)*pay_down)/gross_rf,
            'Q3 positive state prices match portfolio cost')
    require((F('.7')*up+F('.3')*down)/gross_rf != spot,
            'Q3 physical-weight shortcut violates observed clone price')
    immediate = spot-strike+F(30)/gross_rf
    early_threshold = (cost-(spot-strike))*gross_rf
    require(immediate == F(190, 11) and immediate-cost == F(30, 11)
            and early_threshold == 27, 'Q3 early receipt and delay threshold')
    for change in (-F(1, 100), F(0), F(1, 100)):
        difference = spot-strike+(early_threshold+change)/gross_rf-cost
        require(difference == change/gross_rf,
                'Q3 exactly dated threshold crossing')
    return {'peer_EV': [350, 440, 630, 200],
            'normalized_EBITDA': [50, 55, 70, 100], 'median': 8,
            'relative_DCF_equity': [380, 400],
            'pricing_up_weight': str(q), 'delay_value': str(cost),
            'immediate_value_at_D30': str(immediate), 'receipt_threshold': 27}


def stock_venture_check():
    buyer_equity = F(420)+40-60
    target_equity = F(180)+10-40-10
    costs = F(18)+9+5
    surplus = F(12)+50-costs
    closing_cash = F(40)+10-costs
    operating = F(420)+180+12+50
    combined_equity = operating+closing_cash-(60+40+10)
    require((buyer_equity, target_equity, surplus, closing_cash, operating,
             combined_equity) == (400, 140, 30, 18, 662, 570) and
            buyer_equity+target_equity+surplus == combined_equity,
            'Q4 closing sources, operating assets and surviving claims')
    issued, old_buyer = F(8), F(20)
    price = combined_equity/(old_buyer+issued)
    gains = (old_buyer*price-buyer_equity, issued*price-target_equity)
    require(price == F(285, 14) and gains == (F(50, 7), F(160, 7)) and
            sum(gains) == surplus, 'Q4 endogenous price and both old gains')
    max_shares = old_buyer*(target_equity+surplus)/buyer_equity
    require(max_shares == F('8.5') and
            old_buyer*combined_equity/(old_buyer+max_shares) == buyer_equity,
            'Q4 maximum-share allocation of all surplus')
    require(old_buyer*combined_equity/(old_buyer+max_shares+F('.001')) < buyer_equity
            and issued*(buyer_equity/old_buyer) != issued*price,
            'Q4 issue bound and old-quote error')

    founders, employees, premoney, new_cash = map(F, (9, 1, 9, 3))
    issue_price = premoney/(founders+employees)
    new_shares = new_cash/issue_price
    # Normalize all counts to the final total: pre-reserve shares form 90%.
    before_reserve = founders+employees+new_shares
    final_total = before_reserve/F('.9')
    reserve = final_total-before_reserve
    weights = tuple(shares/final_total for shares in
                    (founders, employees, new_shares, reserve))
    require((issue_price, new_shares, reserve, final_total) ==
            (F('.9'), F(10, 3), F(40, 27), F(400, 27)) and
            weights == (F(243, 400), F(27, 400), F(9, 40), F(1, 10)) and
            sum(weights) == 1, 'Q4 post-pricing pool and fully diluted ownership')
    require(new_shares/before_reserve == F(1, 4) > weights[2],
            'Q4 investor also diluted by the later reserve')

    def payoff(exit_cash):
        preference = min(new_cash, exit_cash)
        conversion = weights[2]*exit_cash
        investor = max(preference, conversion)
        common = exit_cash-investor
        require(0 <= investor <= exit_cash and common >= 0 and
                investor+common == exit_cash, 'Q4 preference resource conservation')
        return preference, conversion, investor, common

    require(payoff(F(10)) == (3, F('2.25'), 3, 7) and
            payoff(F(20)) == (3, F('4.5'), F('4.5'), F('15.5')),
            'Q4 optional conversion exits')
    threshold = new_cash/weights[2]
    require(threshold == F(40, 3) and payoff(threshold)[0] == payoff(threshold)[1],
            'Q4 conversion threshold')
    for x in (F(0), F(1), F(3), F(10), threshold-F('.001'),
              threshold, threshold+F('.001'), F(20), F(100)):
        preference, conversion, investor, common = payoff(x)
        require((investor == preference) if x <= threshold else (investor == conversion),
                'Q4 piecewise preferred election')
    return {'standalone_equity': [400, 140], 'surplus': 30,
            'combined_equity': 570, 'post_price': str(price),
            'buyer_target_gains': [str(g) for g in gains],
            'maximum_new_shares': str(max_shares),
            'reserve_shares': str(reserve),
            'ownership_fractions': [str(w) for w in weights],
            'conversion_exit_threshold': str(threshold)}


def distress_check():
    secured_face, bond_face, trade_face = map(F, (70, 30, 10))
    collateral, pool = F(55)-5, F(40)-4+4
    deficiency = max(secured_face-collateral, 0)
    eligible = (deficiency, bond_face, trade_face)
    pro_rata = min(F(1), pool/sum(eligible))
    liquidation = (collateral+deficiency*pro_rata, bond_face*pro_rata,
                   trade_face*pro_rata, F(0))
    require((deficiency, pool, pro_rata) == (20, 40, F(2, 3)) and
            liquidation == (F(190, 3), 20, F(20, 3), 0) and
            sum(liquidation) == collateral+pool == 90,
            'Q5 liquidation rights and complete resources')
    gross_rf, restart, cash, new_money, final_cash = map(F, ('1.05', 24, 4, 20, '117.6'))
    require(cash+new_money == restart, 'Q5 baseline closing funding')
    new_due = new_money*gross_rf

    def distribute(transfer):
        remaining = final_cash
        new = min(new_due, remaining)
        remaining -= new
        secured = secured_face-transfer
        require(0 <= secured <= remaining, 'Q5 permitted secured transfer')
        remaining -= secured
        junior_paid = min(bond_face+trade_face, remaining)
        bond = junior_paid*bond_face/(bond_face+trade_face)
        trade = junior_paid*trade_face/(bond_face+trade_face)
        equity = remaining-junior_paid
        payments = (new, secured, bond, trade, equity)
        require(sum(payments) == final_cash and min(payments) >= 0,
                'Q5 continuation full resource closure')
        return payments, tuple(x/gross_rf for x in payments[1:])

    payments, old_values = distribute(F(0))
    require(new_due/gross_rf == new_money == 20 and
            old_values == (F(200, 3), 19, F(19, 3), 0) and
            sum(old_values) == final_cash/gross_rf-new_money == 92,
            'Q5 fair financing and old participation values')
    gains = tuple(v-l for v, l in zip(old_values, liquidation))
    require(gains == (F(10, 3), -1, -F(1, 3), 0) and sum(gains) == 2,
            'Q5 aggregate gain masks two veto losses')
    junior_future_minimum = sum(liquidation[1:3])*gross_rf
    current_junior_cash = sum(payments[2:4])
    lower = junior_future_minimum-current_junior_cash
    upper = secured_face-liquidation[0]*gross_rf
    require((lower, upper) == (F('1.4'), F('3.5')), 'Q5 exact transfer interval')
    for transfer in (lower, F('2.1'), upper):
        _, values = distribute(transfer)
        require(all(v >= l for v, l in zip(values, liquidation)) and
                sum(values) == 92, 'Q5 weak class participation and conservation')
    for transfer in (lower-F('.001'), upper+F('.001')):
        _, values = distribute(transfer)
        require(any(v < l for v, l in zip(values, liquidation)),
                'Q5 transfer just outside interval must fail a class')
    _, values = distribute(F('2.1'))
    middle_gains = tuple(v-l for v, l in zip(values, liquidation))
    require(middle_gains == (F(4, 3), F(1, 2), F(1, 6), 0) and
            sum(middle_gains) == 2, 'Q5 interior surplus allocation')
    stress_cost, stress_final = F(27), F('110.25')
    gap = stress_cost-cash-new_money
    conditional_new = new_money+gap
    conditional_old = (stress_final-conditional_new*gross_rf)/gross_rf
    require(gap == 3 and conditional_new*gross_rf == F('24.15') and
            conditional_old == 82 and conditional_old-sum(liquidation) == -8,
            'Q5 stress closing and conditional all-class loss')
    # Sum of three weak participation constraints contradicts 82 available.
    require(sum(liquidation[:3]) > conditional_old,
            'Q5 redistribution cannot manufacture the missing eight')
    return {'liquidation': [str(x) for x in liquidation],
            'old_continuation_PV': 92, 'old_surplus': 2,
            'participation_transfer_interval': [str(lower), str(upper)],
            'gains_at_transfer_2_1': [str(x) for x in middle_gains],
            'stress_funding_gap': 3, 'conditional_stress_old_value': 82}


class Form(HTMLParser):
    """Verify explicit nesting and examiner-facing assembly contracts."""
    void = {'br', 'hr', 'img', 'input', 'meta', 'link', 'wbr', 'area', 'base',
            'col', 'embed', 'param', 'source', 'track'}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.ids, self.hrefs, self.text = [], [], [], []
        self.parts, self.solutions, self.h2 = {}, [], []
        self.details, self.summaries = 0, 0
        self.solution_started = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        require(tag not in {'html', 'head', 'body', 'h1', 'script', 'style'},
                'Form A must remain a static content fragment')
        if tag not in self.void:
            self.stack.append(tag)
        if 'id' in a:
            self.ids.append(a['id'])
        if tag == 'a':
            self.hrefs.append(a.get('href', ''))
        if tag == 'h2':
            self.h2.append(a.get('id'))
            if a.get('id') == 'solutions-a':
                require('details' in self.stack, 'solution heading must be collapsed')
        if tag == 'details':
            require(a.get('class') == 'solutions', 'Form A solution details class')
            self.solution_started = True
            self.details += 1
        if tag == 'summary':
            self.summaries += 1
        if 'data-points' in a:
            require(not self.solution_started and tag == 'li', 'all prompts precede solutions')
            require(a['id'] not in self.parts, 'duplicate assessed part')
            self.parts[a['id']] = int(a['data-points'])
        if 'data-solution-for' in a:
            require('details' in self.stack and tag == 'li', 'solution outside collapsed section')
            self.solutions.append(a['data-solution-for'])

    def handle_endtag(self, tag):
        require(bool(self.stack) and self.stack[-1] == tag,
                f'Form A misnested closing tag {tag}')
        self.stack.pop()

    def handle_data(self, value):
        self.text.append(value)


def structure_check():
    content = MANUSCRIPT.read_text(encoding='utf-8')
    form = Form()
    form.feed(content)
    form.close()
    require(not form.stack, 'Form A unclosed HTML element')
    expected = {f'v08-a-q{q}{letter}' for q in range(1, 6) for letter in 'abcd'}
    require(set(form.parts) == expected and set(form.parts.values()) == {5} and
            sum(form.parts.values()) == 100, 'Form A twenty five-point parts')
    require(Counter(form.solutions) == Counter({key: 1 for key in expected}),
            'Form A one complete solution mapping per assessed part')
    require(len(form.ids) == len(set(form.ids)) and
            all(i in ('form-a', 'solutions-a') or i.startswith('v08-a-') for i in form.ids),
            'Form A unique namespaced IDs')
    require(form.h2 == ['form-a', 'solutions-a'] and
            form.details == form.summaries == 1, 'Form A headings/details structure')
    for q in range(1, 6):
        require(sum(form.parts[f'v08-a-q{q}{letter}'] for letter in 'abcd') == 20,
                'Form A essential domain score')
    rubrics = re.findall(r'<strong>Scoring:</strong>(.*?)</p>', content, re.S)
    require(len(rubrics) == 20, 'Form A every solution needs analytic rubric')
    for number, rubric in enumerate(rubrics, 1):
        credits = [int(x) for x in re.findall(r',\s*([1-5])(?=\s*[;.])', rubric)]
        require(sum(credits) == 5, f'Form A rubric {number} must total five')
    chapter_routes = {f'v08-c{c:02d}.html' for c in range(1, 13)}
    require(chapter_routes <= set(form.hrefs), 'Form A twelve taught-method routes')
    for phrase in ('240 minutes', 'closed book', 'nonprogrammable calculator',
                   '85/100', '15/20', 'carried-forward arithmetic error'):
        require(phrase in content, f'Form A missing condition: {phrase}')
    source_ids = {href.split('#', 1)[1] for href in form.hrefs if href.startswith('sources.html#')}
    proposed = json.loads((ROOT/'content/reviews/v08-exam-a-sources.json').read_text())
    require(isinstance(proposed, list) and source_ids <= {s['id'] for s in proposed},
            'Form A linked source proposals')
    return {'parts': 20, 'solutions': 20, 'points': 100, 'essential_domains': 5,
            'chapter_routes': 12, 'point_rubrics': 20,
            'words': len(re.findall(r'\b[\w’−]+\b', ' '.join(form.text)))}


def check():
    result = {
        'status': 'passed',
        'groups': [
            'Q1 alternatives, direct FCFF, component capital and finite terminal/economic-profit closure',
            'Q2 market-weight beta/state returns and policy-dependent priced claim conservation',
            'Q2 dated payout calendar, exact binding capacity and full-horizon cash reconciliation',
            'Q3 complete peer normalization, two equity bridges and independently replicated option',
            'Q4 acquisition resources/endogenous ownership and post-pricing venture preference rights',
            'Q5 deficiency waterfall, fair financing, transfer interval and stressed resource impossibility',
            'Twenty prompts/solutions, five-point rubrics, strict fragment nesting and all twelve chapter routes',
        ],
        'numerical_anchors': {
            'D1': capital_check(),
            'D2_rates_incentives': rate_incentive_check(),
            'D2_payout': payout_check(),
            'D3': peers_option_check(),
            'D4': stock_venture_check(),
            'D5': distress_check(),
        },
        'structure': structure_check(),
        'limits': ('Exact conditional numerical and HTML-source checks; full prose, evidence, '
                   'instruction, source scope and grading require recorded review. No UI or human calibration.'),
    }
    json.dumps(result, allow_nan=False)
    return result


if __name__ == '__main__':
    print(json.dumps(check(), indent=2, allow_nan=False))
