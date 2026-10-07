"""Optional foundations-project benchmark; standard-library Python only."""
from pathlib import Path
import json
import math

def solve(case):
    cash = case['owner_capital'] + case['opening_loan'] - case['equipment_purchase']
    loan = case['opening_loan']; units = 0; earnings = 0; rows = []
    for month in case['months']:
        interest = loan * case['monthly_interest_rate']
        revenue = month['units_sold'] * case['sale_price']
        purchases = month['units_purchased'] * case['inventory_unit_cost']
        cogs = month['units_sold'] * case['inventory_unit_cost']
        units += month['units_purchased'] - month['units_sold']
        assert units >= 0, 'Cannot sell nonexistent inventory in this case.'
        profit = revenue - cogs - month['other_expense'] - interest
        earnings += profit
        cash += revenue - purchases - month['other_expense'] - interest - month['principal_payment']
        loan -= month['principal_payment']
        assets = cash + units*case['inventory_unit_cost'] + case['equipment_purchase']
        equity = case['owner_capital'] + earnings
        assert math.isclose(assets, loan + equity), 'Balance sheet does not reconcile.'
        rows.append({'month':month['month'],'cash':cash,'inventory_units':units,
                     'debt':loan,'interest':interest,'revenue':revenue,'cogs':cogs,'profit':profit})
    proposal = case['future_project']; rate = proposal['annual_discount_benchmark']
    assert math.isclose(sum(s['probability'] for s in proposal['scenarios']),1)
    expected = sum(s['probability']*s['receipt'] for s in proposal['scenarios'])
    discount = (1+rate)**proposal['receipt_horizon_years']
    after_project = cash-proposal['initial_cost']
    after_withdrawal = after_project-proposal['proposed_owner_withdrawal']
    return {'months':rows,'cumulative_profit':earnings,'closing_assets':assets,
            'closing_equity':equity,'expected_project_receipt':expected,
            'benchmark_npv':expected/discount-proposal['initial_cost'],
            'scenario_npvs':[s['receipt']/discount-proposal['initial_cost'] for s in proposal['scenarios']],
            'cash_after_project':after_project,'cash_after_project_and_withdrawal':after_withdrawal,
            'project_meets_buffer':after_project>=proposal['cash_buffer_minimum'],
            'project_and_withdrawal_meet_buffer':after_withdrawal>=proposal['cash_buffer_minimum'],
            'closing_cash_in_initial_purchasing_power':cash/(1+case['price_index_growth_to_month_3'])}

if __name__ == '__main__':
    inputs = json.loads((Path(__file__).parent/'v01-case.json').read_text())
    print(json.dumps(solve(inputs),indent=2))
