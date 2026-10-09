"""Coordinator regression for the selected-reserve purchase-cost finding.

The candidate toolkit is exercised, but expected cash is independently built
from the original contract and dated zero prices; no candidate output is used
to choose the expected reserve cost or quote-gate result.
"""
from copy import deepcopy
from fractions import Fraction as F
import contextlib
import importlib.util
import io
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def check():
    stream = io.StringIO()
    with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
        spec = importlib.util.spec_from_file_location(
            'selected_reserve_candidate', ROOT/'content/projects/v10-assessment-analysis.py')
        candidate = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(candidate)
    if stream.getvalue():
        raise RuntimeError('Candidate import emitted output')
    baseline = json.loads((ROOT/'content/projects/v10-assessment-inputs.json').read_text())
    cases = []
    comparisons = 0
    # At the unchanged option terms, the coordinator's separate Gaussian-payoff
    # and discounted-gains audit independently established these two quantities.
    hedge_budget = 8.688302035017628 + 10.736568055382063
    for reserve, quote, expected_pass in (
        ('risky_bond', '110.5', False),
        ('risky_bond', '111.12', False),
        ('risky_bond', '111.13', True),
        ('matched_zeros', '110.5', True),
    ):
        data = deepcopy(baseline)
        data['liability']['coupons'] = ['0', '0', '0']
        data['credit_reserve'].update(default_index=0, settlement_index=0,
                                      recovery_fraction='1')
        data['decision'].update(requested_reserve=reserve, requested_quote=quote)
        original = deepcopy(data)
        with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
            result = candidate.run(data)
        if stream.getvalue() or data != original:
            raise RuntimeError('Candidate API noise or input mutation')
        comparisons += 1
        fixed_cost = F(100)*F(91,100)
        risky_cost = F(9,10)*fixed_cost + F(1,10)*F(100)*F(49,50)
        chosen = risky_cost if reserve == 'risky_bond' else fixed_cost
        floor = max(fixed_cost, chosen)
        expected_threshold = float(floor) + hedge_budget
        decision = result['decision']
        if F(result['bond']['pv']) != fixed_cost or F(result['credit_reserve']['risky_reserve_pv']) != risky_cost:
            raise RuntimeError('Dated reserve prices disagree with independent contract cash')
        comparisons += 2
        if F(decision['selected_reserve_pv']) != chosen or F(decision['reserve_budget_pv']) != floor:
            raise RuntimeError('Reported reserve purchase cost or conservative budget is inconsistent')
        comparisons += 2
        if not math.isclose(decision['quote_with_tested_buffer'], expected_threshold,
                            rel_tol=0, abs_tol=2e-9):
            raise RuntimeError('Quote budget omits actual chosen reserve purchase cost')
        comparisons += 1
        expected_gates = {
            'exercise_matches_european_reference': True,
            'reserve_funds_all_declared_dates': True,
            'quote_covers_tested_loss_budget': expected_pass,
            'controlled_mc_se_within_budget': True,
            'finest_european_tree_difference_within_budget': True,
        }
        if decision['gates'] != expected_gates:
            raise RuntimeError('Incorrect funding or unchanged gate result')
        comparisons += 1
        recommendation = 'eligible_for_limited_demonstration' if expected_pass else 'revise_before_demo'
        if decision['recommendation'] != recommendation:
            raise RuntimeError('Recommendation conflicts with actual initial funding')
        comparisons += 1
        cases.append({'reserve': reserve, 'quote': quote, 'fixed_cost': str(fixed_cost),
                      'chosen_purchase_cost': str(chosen), 'conservative_budget': str(floor),
                      'required_quote': expected_threshold, 'passes': expected_pass})
    return {'status':'passed', 'comparisons':comparisons, 'cases':cases,
            'finding':'production/v10-assessment-selected-reserve-finding.json',
            'scope':'Actual purchase premium is funded; expected credit savings cannot lower the riskless reserve floor. No all-path guarantee follows.'}


if __name__ == '__main__':
    print(json.dumps(check(), indent=2, allow_nan=False))
