#!/usr/bin/env python3
"""Original exact, finite-horizon operating/financing integration laboratory.

No network or packages. Fractions are used internally; output reports exact values
and decimals. A mechanical receivable stress is NOT a priced rescue transaction.
"""
from fractions import Fraction as F
import json
from pathlib import Path
import sys

STATES = ('normal', 'downside')


def serial(x):
    if isinstance(x, F):
        return {'exact': str(x), 'decimal': float(x)}
    if isinstance(x, dict):
        return {k: serial(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [serial(v) for v in x]
    return x


def compute(data):
    r, cash_r, tax = map(F, (data['risk_free_rate'], data['after_tax_cash_rate'], data['operating_tax_rate']))
    if r < 0 or cash_r != r or not 0 <= tax < 1:
        raise ValueError('This model requires nonnegative r, cash net return equal to r, and 0 <= tax < 1')
    q = {s: F(data['pricing_weights'][s]) for s in STATES}
    p = {s: F(data['physical_probabilities'][s]) for s in STATES}
    for weights in (q, p):
        if sum(weights.values()) != 1 or not all(0 < x < 1 for x in weights.values()):
            raise ValueError('Both states require positive probabilities/weights summing to one')
    old_cash, old_debt, old_shares = map(F, (data['opening_cash'], data['opening_debt'], data['old_shares']))
    min_cash, cap, ratio_cap = map(F, (data['minimum_cash'], data['initial_debt_cap'], data['year1_debt_ebitda_cap']))
    existing_principal = list(map(F, data['existing_principal']))
    if len(existing_principal) != 3 or sum(existing_principal) != old_debt or min(existing_principal) < 0 or old_shares <= 0:
        raise ValueError('Three nonnegative principal installments must clear existing debt; positive old shares')
    if min(old_cash, old_debt, min_cash, cap, ratio_cap) < 0:
        raise ValueError('Cash, debt and covenant limits must be nonnegative')

    def value(paths):
        return sum(q[s] * paths[s][i] / (1+r)**(i+1) for s in STATES for i in range(3))

    b = data['base']
    dep, initial_nwc = F(b['annual_depreciation']), F(b['opening_nwc'])
    if 3*dep != F(b['opening_ppe']):
        raise ValueError('Base equipment must have zero terminal tax basis in this case')
    base = {}
    for state in STATES:
        revenues = list(map(F, b['revenue'][state]))
        if len(revenues) != 3 or min(revenues) < 0:
            raise ValueError('Three nonnegative annual base revenues required')
        nwc = initial_nwc
        rows = []
        for i, revenue in enumerate(revenues):
            ebitda = revenue*(1-F(b['variable_cost_fraction']))-F(b['annual_fixed_cost'])
            ebit = ebitda-dep
            closing_nwc = revenue*F(b['nwc_revenue_fraction'])
            change = closing_nwc-nwc
            release = closing_nwc if i == 2 else F(0)
            salvage = F(b['gross_terminal_salvage'][state])*(1-tax) if i == 2 else F(0)
            fcff = ebit*(1-tax)+dep-change+release+salvage
            rows.append({'year':i+1, 'revenue':revenue,'ebitda':ebitda,'ebit':ebit,
                         'nwc_before_windup':closing_nwc,'delta_nwc_before_windup':change,
                         'nwc_release':release,'after_tax_salvage':salvage,'fcff':fcff})
            nwc = closing_nwc
        base[state] = rows
    base_value = value({s:[x['fcff'] for x in base[s]] for s in STATES})
    policies = {}
    for key, a in data['policies'].items():
        equipment, nwc0, project_dep = map(F,(a['equipment_now'],a['nwc_now'],a['annual_depreciation']))
        new_debt, equity_gross, fee = map(F,(a['new_debt'],a['equity_gross'],a['equity_issue_fee']))
        new_principal = list(map(F,a['new_principal']))
        if len(new_principal) != 3 or sum(new_principal) != new_debt or min(new_principal) < 0:
            raise ValueError('Each new loan must clear in three nonnegative installments')
        if 3*project_dep != equipment or min(equipment,nwc0,new_debt,equity_gross,fee) < 0:
            raise ValueError('Project equipment requires zero terminal tax basis and nonnegative financing inputs')
        investment = equipment+nwc0
        c0 = old_cash+new_debt+equity_gross-investment-fee
        debt0 = old_debt+new_debt
        schedules, cash_paths, project_paths = {}, {}, {}
        for state in STATES:
            c, d, new_d = c0, debt0, new_debt
            rows, cash_sequence, project_sequence = [], [], []
            for i in range(3):
                proj_ebitda = F(a['revenue'][state])*(1-F(a['variable_cost_fraction']))-F(a['annual_fixed_cost'])
                proj_ebit = proj_ebitda-project_dep
                proj_cf = proj_ebit*(1-tax)+project_dep
                if i == 2:
                    proj_cf += nwc0+F(a['gross_terminal_salvage'][state])*(1-tax)
                interest = r*d
                shield, new_shield = tax*interest, tax*r*new_d
                total_ebit = base[state][i]['ebit']+proj_ebit
                if total_ebit-interest < 0:
                    raise ValueError('Full current tax use fails: rebuild taxes and shield pricing')
                principal = existing_principal[i]+new_principal[i]
                operating_cf = base[state][i]['fcff']+proj_cf
                opening_c = c
                c = (1+cash_r)*c+operating_cf+shield-interest-principal
                d -= principal
                new_d -= new_principal[i]
                rows.append({'year':i+1,'project_ebitda':proj_ebitda,'project_ebit':proj_ebit,
                             'total_ebitda':base[state][i]['ebitda']+proj_ebitda,
                             'taxable_operating_income_after_interest':total_ebit-interest,
                             'project_fcff':proj_cf,'combined_fcff':operating_cf,
                             'opening_cash':opening_c,'after_tax_cash_income':cash_r*opening_c,
                             'interest':interest,'tax_shield':shield,'new_debt_tax_shield':new_shield,
                             'principal':principal,'closing_debt':d,'closing_cash_before_final_distribution':c})
                cash_sequence.append(c)
                project_sequence.append(proj_cf)
            schedules[state], cash_paths[state], project_paths[state] = rows,cash_sequence,project_sequence
        project_value = value(project_paths)
        shield_value = sum(schedules['normal'][i]['tax_shield']/(1+r)**(i+1) for i in range(3))
        added_shield = sum(schedules['normal'][i]['new_debt_tax_shield']/(1+r)**(i+1) for i in range(3))
        equity_post = base_value+project_value+shield_value+c0-debt0
        equity_old = equity_post-equity_gross
        if equity_post <= 0 or equity_old <= 0:
            raise ValueError('Fair issuance requires positive total equity and a positive old-owner residual; this funding cannot be sold under the supplied contract')
        terminal_equity_pv = sum(q[s]*cash_paths[s][-1]/(1+r)**3 for s in STATES)
        ratios = {s:schedules[s][0]['closing_debt']/schedules[s][0]['total_ebitda'] for s in STATES}
        feasible = c0 >= min_cash and debt0 <= cap and all(
            min(cash_paths[s][:2]) >= min_cash and cash_paths[s][-1] >= 0 and ratios[s] <= ratio_cap for s in STATES)
        new_fraction = equity_gross/equity_post
        new_shares = old_shares*equity_gross/equity_old
        shock = F(data['diagnostic_receivable_shock'])
        stress = {s:{'cash_at_1_mechanical':cash_paths[s][0]-shock,
                     'funding_gap_at_1':max(F(0),min_cash-(cash_paths[s][0]-shock)),
                     'maximum_extra_receivable_without_breach':cash_paths[s][0]-min_cash} for s in ('downside',)}
        policies[key] = {'investment_now':investment,'initial_cash':c0,'initial_debt':debt0,
                         'project_operating_value':project_value,'project_operating_npv':project_value-investment,
                         'total_tax_shield_pv':shield_value,'incremental_tax_shield_pv':added_shield,
                         'incremental_old_owner_value':project_value-investment+added_shield-fee,
                         'equity_after_financing':equity_post,'old_owner_equity':equity_old,
                         'terminal_equity_pv':terminal_equity_pv,'new_owner_fraction':new_fraction,
                         'new_shares':new_shares,'fair_issue_price_per_share':equity_old/old_shares,
                         'year1_debt_ebitda':ratios,'feasible_baseline':feasible,
                         'schedule':schedules,'receivable_stress':stress,
                         'date2_operating_continuation':{s:schedules[s][2]['combined_fcff']/(1+r) for s in STATES}}
    physical_ebitda = sum(p[s]*base[s][0]['ebitda'] for s in STATES)
    multiples = sorted(F(x['unlevered_operations'])/F(x['physical_forward_ebitda']) for x in data['peer_inputs'])
    if len(multiples) != 3:
        raise ValueError('This original peer case uses three supplied all-equity observations')
    comparison = {'multiples':multiples,'physical_mean_base_ebitda':physical_ebitda,
                  'indicated_unlevered_range':[m*physical_ebitda for m in (multiples[0],multiples[-1])],
                  'median_indicated_unlevered_value':multiples[1]*physical_ebitda}
    comparison['median_indicated_equity'] = comparison['median_indicated_unlevered_value']+policies['none']['total_tax_shield_pv']+old_cash-old_debt
    a, b_result = policies['A'],policies['B']
    fee_threshold = a['project_operating_npv']+a['incremental_tax_shield_pv']-b_result['incremental_old_owner_value']
    chosen = max((key for key in policies if policies[key]['feasible_baseline']),
                 key=lambda key:policies[key]['incremental_old_owner_value'],default=None)
    return {'case':'Ridgeway Calibration Partners; fictional three-year closed business',
            'state_prices_at_1':{s:q[s]/(1+r) for s in STATES},'base_operations':base,
            'base_unlevered_value':base_value,'policies':policies,'comparable_check':comparison,
            'A_fee_indifference_to_B':fee_threshold,'selected_feasible_policy':chosen,
            'valuation_scope':'Claim values and issuance terms require feasible_baseline=true; an infeasible policy yields conditional continuation diagnostics, not prices of defaulted or revised contracts.',
            'stress_scope':'Mechanical date-1 cash diagnostic only; no covenant waiver, rescue loan or distressed claim valuation assumed.'}


if __name__ == '__main__':
    path = Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).with_name('v08-c12-inputs.json')
    print(json.dumps(serial(compute(json.loads(path.read_text()))),indent=2,allow_nan=False))
