#!/usr/bin/env python3
"""Focused independent checks of Ridgeway's three-year cash and claim contract."""
from copy import deepcopy
from fractions import Fraction as F
from html.parser import HTMLParser
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT/'content/projects/v08-c12-analysis.py'


class Fragment(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.ids = [], []
        self.examples = self.exercises = self.solutions = 0
        self.mode = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if 'id' in a:
            self.ids.append(a['id'])
        if 'worked' in a.get('class','').split():
            self.examples += 1
        if tag == 'ol' and a.get('class') == 'exercises':
            self.mode = 'exercises'
        if tag == 'details' and a.get('class') == 'solutions':
            self.mode = 'solutions'
        if tag == 'li' and self.mode:
            setattr(self,self.mode,getattr(self,self.mode)+1)
        if tag not in ('br','hr','img','meta','link','input'):
            self.stack.append(tag)

    def handle_endtag(self, tag):
        assert self.stack and self.stack.pop() == tag, 'HTML nesting mismatch: '+tag
        if (tag == 'ol' and self.mode == 'exercises') or (tag == 'details' and self.mode == 'solutions'):
            self.mode = None


def check():
    spec = importlib.util.spec_from_file_location('v08_c12_lab',PROJECT)
    lab = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(lab)
    data = json.loads(PROJECT.with_name('v08-c12-inputs.json').read_text())
    result = lab.compute(data)
    checks = []
    growth, tax = F(21,20), F(1,4)
    q = {'normal':F(3,5),'downside':F(2,5)}
    prices = result['state_prices_at_1']
    assert prices == {'normal':F(4,7),'downside':F(8,21)} and sum(prices.values()) == 1/growth
    base = {'normal':list(map(F,['54','58','96.25'])),
            'downside':list(map(F,['44','42','69']))}
    pv = lambda cash: sum(x/growth**(i+1) for i,x in enumerate(cash))
    weighted_pv = lambda paths: sum(q[s]*pv(paths[s]) for s in q)
    for s in q:
        assert [row['fcff'] for row in result['base_operations'][s]] == base[s]
    assert F(56)*F(3,4)+20-1+24+F(15)*F(3,4) == base['normal'][2]
    assert F(32)*F(3,4)+20-F(1,2)+18+F(10)*F(3,4) == base['downside'][2]
    assert weighted_pv(base) == result['base_unlevered_value'] == F(519080,3087)
    assert F(3,4)*pv(base['normal'])+F(1,4)*pv(base['downside']) == F(180370,1029)
    assert q['normal']/growth**3 == F(1600,3087)  # Exercise 1 NWC omission.
    changed = deepcopy(data)
    changed['physical_probabilities'] = {'normal':'0.2','downside':'0.8'}
    assert lab.compute(changed)['base_unlevered_value'] == result['base_unlevered_value']
    checks.append('Positive state-price certificate, full NWC/disposal accounting, physical versus pricing probability separation')

    increments = {'none':{'normal':[F(0)]*3,'downside':[F(0)]*3},
                  'A':{'normal':list(map(F,['20.25','20.25','29.75'])),
                       'downside':list(map(F,['14.25','14.25','21.5']))},
                  'B':{'normal':list(map(F,['10.5','10.5','12.5'])),
                       'downside':list(map(F,['6','6','8']))}}
    investments, debt0, cash0 = {'none':0,'A':50,'B':20},{'none':40,'A':70,'B':45},{'none':30,'A':15,'B':15}
    principals = {'none':[20,20,0],'A':[30,30,10],'B':[25,20,0]}
    terminal = {'none':{'normal':F('205.9225'),'downside':F('150.8475')},
                'A':{'normal':F('227.9684375'),'downside':F('151.7284375')},
                'B':{'normal':F('217.94015625'),'downside':F('148.67890625')}}
    for k, policy in result['policies'].items():
        assert policy['initial_cash'] == cash0[k] and policy['initial_debt'] == debt0[k]
        assert policy['project_operating_value'] == weighted_pv(increments[k])
        assert policy['project_operating_npv'] == weighted_pv(increments[k])-investments[k]
        for s in q:
            rows = policy['schedule'][s]
            assert [row['project_fcff'] for row in rows] == increments[k][s]
            for t in range(1,4):
                # Accumulate all prior after-tax debt service and operating receipts to t,
                # independently of the lab's one-step cash recursion.
                cash = cash0[k]*growth**t
                for j in range(t):
                    opening_d = debt0[k]-sum(principals[k][:j])
                    net_cash = base[s][j]+increments[k][s][j]-F(3,4)*F(1,20)*opening_d-principals[k][j]
                    cash += net_cash*growth**(t-j-1)
                assert cash == rows[t-1]['closing_cash_before_final_distribution']
                assert rows[t-1]['closing_debt'] == debt0[k]-sum(principals[k][:t])
                assert rows[t-1]['taxable_operating_income_after_interest'] > 0
                assert cash >= (15 if t<3 else 0)
            assert rows[-1]['closing_cash_before_final_distribution'] == terminal[k][s]
            continuation = (base[s][2]+increments[k][s][2])/growth
            assert policy['date2_operating_continuation'][s] == continuation
            assert pv([base[s][i]+increments[k][s][i] for i in range(3)]) == (
                (base[s][0]+increments[k][s][0])/growth+
                (base[s][1]+increments[k][s][1]+continuation)/growth**2)
        assert policy['equity_after_financing'] == sum(q[s]*terminal[k][s] for s in q)/growth**3 == policy['terminal_equity_pv']
        assert policy['feasible_baseline'] is True
    checks.append('Independent accumulated cash paths, full loan extinction, positive taxable capacity, finite continuation and both equity valuation routes')

    n,a,b = (result['policies'][k] for k in ('none','A','B'))
    assert n['old_owner_equity'] == F(163460,1029)
    assert a['incremental_tax_shield_pv'] == F(12815,18522)
    assert b['incremental_tax_shield_pv'] == F(5,84)
    assert a['incremental_old_owner_value'] == a['old_owner_equity']-n['old_owner_equity'] == F(106147,18522)
    assert b['incremental_old_owner_value'] == b['old_owner_equity']-n['old_owner_equity'] == F(202981,37044)
    assert a['new_owner_fraction'] == F(111132,3159559)
    assert a['new_shares'] == F(1111320,3048427)
    assert a['fair_issue_price_per_share']*a['new_shares'] == 6
    new_payoff_price = sum(q[s]*terminal['A'][s]*a['new_shares']/(10+a['new_shares']) for s in q)/growth**3
    assert new_payoff_price == 6
    wrong_shares = 60/n['old_owner_equity']
    wrong_new_value = a['equity_after_financing']*wrong_shares/(10+wrong_shares)
    assert wrong_shares == F(3087,8173) and wrong_new_value-6 == F(106147,508902)
    assert a['year1_debt_ebitda']['downside'] == F(20,31)
    assert b['year1_debt_ebitda']['downside'] == F(10,27)
    assert result['selected_feasible_policy'] == 'A'
    changed = deepcopy(data)
    changed['policies']['A'].update(equity_gross='0',equity_issue_fee='0')
    no_issue = lab.compute(changed)
    assert no_issue['policies']['A']['initial_cash'] == 10
    assert no_issue['policies']['A']['feasible_baseline'] is False
    assert no_issue['selected_feasible_policy'] == 'B'
    checks.append('Fair new equity payoff and dilution, old-quote transfer, covenant dates and exclusion of unfunded positive-NPV policy')

    threshold = result['A_fee_indifference_to_B']
    assert threshold == F(46357,37044)
    for fee in (threshold,F(3,2)):
        changed = deepcopy(data)
        changed['policies']['A'].update(equity_issue_fee=str(fee),equity_gross=str(5+fee))
        amended = lab.compute(changed)
        assert amended['policies']['A']['initial_cash'] == 15
        diff = amended['policies']['A']['incremental_old_owner_value']-b['incremental_old_owner_value']
        assert diff == threshold-fee
        if fee>threshold:
            assert amended['selected_feasible_policy'] == 'B'
    q_boundary = F(124679,223320)
    changed = deepcopy(data)
    changed['pricing_weights'] = {'normal':str(q_boundary),'downside':str(1-q_boundary)}
    boundary = lab.compute(changed)['policies']
    assert boundary['A']['incremental_old_owner_value'] == boundary['B']['incremental_old_owner_value']
    cost_boundary = F(9313,75660)
    assert cost_boundary*F(3,4)*pv([F(1)]*3) == a['incremental_old_owner_value']-b['incremental_old_owner_value']
    assert a['incremental_old_owner_value']-2 < b['incremental_old_owner_value']
    checks.append('Exact fee, priced-state-weight and annual-cost indifference boundaries; current rental opportunity reverses choice')

    for key,expected_cash,expected_gap,headroom in [('none',19,0,39),('A',F(51,8),F(69,8),F(211,8)),('B',F(65,16),F(175,16),F(385,16))]:
        stress = result['policies'][key]['receivable_stress']['downside']
        assert stress['cash_at_1_mechanical'] == expected_cash
        assert stress['funding_gap_at_1'] == expected_gap
        assert stress['maximum_extra_receivable_without_breach'] == headroom
    assert F(2,5)*35*(1/growth-1/growth**2) == F(40,63)
    comps = result['comparable_check']
    assert comps['physical_mean_base_ebitda'] == 63
    assert comps['multiples'] == [F(12,5),F(5,2),F(27,10)]
    assert comps['median_indicated_unlevered_value'] == F(315,2)
    assert comps['median_indicated_equity'] == F(130715,882)
    assert comps['indicated_unlevered_range'] == [F(756,5),F(1701,10)]
    checks.append('Mechanical stress funding gaps separated from timing-only loss; consistent all-equity peer scope and target tax-shield bridge')

    for change in ('cash_rate','zero_weight','principal','tax_capacity','impossible_equity_issue'):
        changed = deepcopy(data)
        if change == 'cash_rate': changed['after_tax_cash_rate'] = '0'
        elif change == 'zero_weight': changed['pricing_weights'] = {'normal':'1','downside':'0'}
        elif change == 'principal': changed['policies']['A']['new_principal'] = ['10','10','9']
        elif change == 'tax_capacity': changed['policies']['A']['annual_fixed_cost'] = '50'
        else: changed['policies']['A'].update(equity_issue_fee='200',equity_gross='205')
        try:
            lab.compute(changed)
        except ValueError:
            pass
        else:
            raise AssertionError('Invalid assumption accepted: '+change)
    fragment = Fragment()
    body = (ROOT/'content/chapters/v08-c12.html').read_text()
    fragment.feed(body)
    assert not fragment.stack and len(fragment.ids) == len(set(fragment.ids))
    assert (fragment.examples,fragment.exercises,fragment.solutions) == (3,8,8)
    assert 'Teach-back' in body and 'Delayed check' in body
    reference = json.loads(PROJECT.with_name('v08-c12-output.json').read_text())
    assert reference == lab.serial(result)
    cli = subprocess.run([sys.executable,str(PROJECT)],capture_output=True,text=True,check=True)
    assert json.loads(cli.stdout) == reference
    checks.append('Focused assumption guards, balanced original chapter and eight complete solutions, exact output and standalone CLI')
    return {'status':'passed','checks':checks,'worked_examples':3,'exercises':8,
            'limitations':'Fictional contracts and supplied state prices; no actual lending/tax verification or visual UI review claimed.'}


if __name__ == '__main__':
    print(json.dumps(check(),indent=2,allow_nan=False))
