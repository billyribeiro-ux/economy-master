"""Portlight: a finite, funded two-currency bank/pension settlement project.

All financial values are exact rational strings. run(data) is quiet and does not
mutate input. Every candidate executes available cash with retained unpaid claims;
the reserve is a feasibility limit, never a fictional creditor. No external data,
random draws, legal powers, guarantees or unmodeled emergency finance are used.
"""
import argparse
from fractions import Fraction as Q
from itertools import product
import json
from pathlib import Path
import re


def need(condition, message):
    if not condition:
        raise ValueError(message)


def keys(obj, expected, label):
    need(type(obj) is dict and set(obj) == set(expected.split()), label + ': exact keys required')


def number(value, label, low=Q(0), high=Q(1000)):
    need(type(value) is str and len(value) <= 22 and
         re.fullmatch(r'-?\d{1,8}(?:(?:\.\d{1,8})|(?:/[1-9]\d{0,7}))?', value) is not None,
         label + ': bounded decimal or rational string required')
    result = Q(value)
    need(low <= result <= high, label + ': outside supported domain')
    return result


def validate(data):
    keys(data, 'schema provenance initial_spot bank first_due pension endowments facility limits choices risk_alpha reverse_scenario scenarios', 'input')
    need(type(data['schema']) is int and data['schema'] == 1, 'schema must be integer 1')
    need(type(data['provenance']) is str and 1 <= len(data['provenance']) <= 500, 'provenance text required')
    spot0 = number(data['initial_spot'], 'initial spot', Q(1, 4), Q(4))
    keys(data['bank'], 'home_cash foreign_cash bill long_bond_units domestic_loan_face foreign_claim_face household_deposits pension_deposit foreign_deposits', 'bank')
    bank = {k: number(v, k) for k, v in data['bank'].items()}
    need(bank['long_bond_units'] > 0 and bank['domestic_loan_face'] > 0 and bank['foreign_claim_face'] > 0, 'positive bond and loan books required')
    initial_equity = (bank['home_cash'] + bank['bill'] + bank['long_bond_units'] + bank['domestic_loan_face']
                      - bank['household_deposits'] - bank['pension_deposit']
                      + spot0 * (bank['foreign_cash'] + bank['foreign_claim_face'] - bank['foreign_deposits']))
    need(initial_equity > 0, 'positive reference equity required for a priced equity subscription')
    keys(data['first_due'], 'households foreign_deposits borrower_principal', 'first due')
    due = {k: number(v, k) for k, v in data['first_due'].items()}
    need(due['households'] <= bank['household_deposits'] and due['foreign_deposits'] <= bank['foreign_deposits']
         and 0 < due['borrower_principal'] < bank['domestic_loan_face'], 'first due exceeds or exhausts its supported claim')
    keys(data['pension'], 'cash benefits', 'pension')
    for k, v in data['pension'].items(): number(v, k)
    need(Q(data['pension']['benefits']) > 0, 'positive benefit promise required')
    keys(data['endowments'], 'sponsor_home_cash lender_home_cash dealer_home_cash dealer_foreign_cash collateral_buyer_home_cash', 'endowments')
    endowment = {k: number(v, k) for k, v in data['endowments'].items()}
    keys(data['facility'], 'eligible_bond_units interest', 'facility')
    eligible = number(data['facility']['eligible_bond_units'], 'eligible units')
    need(eligible <= bank['long_bond_units'], 'eligible units exceed separately owned bond inventory')
    number(data['facility']['interest'], 'secured interest', high=Q(1))
    keys(data['limits'], 'home_reserve bank_equity', 'limits')
    for k, v in data['limits'].items(): number(v, k)
    keys(data['choices'], 'bank_equity prefund_foreign pension_contribution', 'choices')
    choices = {}
    for k, values in data['choices'].items():
        need(type(values) is list and 1 <= len(values) <= 4, 'one to four choices per decision required')
        choices[k] = [number(v, k, high=Q(100)) for v in values]
        need(len(set(choices[k])) == len(values), 'duplicate numerical decision')
    need(max(choices['bank_equity']) + max(choices['pension_contribution']) <= endowment['sponsor_home_cash'], 'outside contributions exceed the sponsor cash endowment')
    need(bank['home_cash'] + min(choices['bank_equity']) >= spot0 * max(choices['prefund_foreign']), 'a menu combination overdraws home cash at prefunding')
    alpha = number(data['risk_alpha'], 'risk alpha', high=Q(1))
    need(0 < alpha < 1, 'risk alpha must be strictly between zero and one')
    scenarios = data['scenarios']
    need(type(scenarios) is list and 1 <= len(scenarios) <= 5, 'one to five scenarios required')
    ids, probability = [], Q(0)
    for scenario in scenarios:
        keys(scenario, 'id probability spot bond_yield haircut borrower_cash_first borrower_cash_final collateral_gross collateral_cost collateral_prior_claim foreign_recovery early_fx_cap late_fx_cap prefund_timely', 'scenario')
        need(type(scenario['id']) is str and re.fullmatch(r'[a-z][a-z0-9_]{0,31}', scenario['id']) is not None, 'invalid scenario ID')
        ids.append(scenario['id'])
        prob = number(scenario['probability'], 'physical probability', high=Q(1))
        need(prob > 0, 'all listed scenarios require positive probability')
        probability += prob
        spot = number(scenario['spot'], 'spot', Q(1, 4), Q(4))
        number(scenario['bond_yield'], 'bond yield', high=Q(4))
        haircut = number(scenario['haircut'], 'haircut', high=Q(1))
        need(haircut < 1, 'haircut must be below one')
        quantities = {k: number(scenario[k], k) for k in ('borrower_cash_first', 'borrower_cash_final', 'collateral_gross', 'collateral_cost', 'collateral_prior_claim', 'foreign_recovery', 'early_fx_cap', 'late_fx_cap')}
        need(quantities['collateral_gross'] <= endowment['collateral_buyer_home_cash'], 'collateral buyer has insufficient endowed cash')
        net = quantities['collateral_gross'] - quantities['collateral_cost'] - quantities['collateral_prior_claim']
        need(net >= 0, 'collateral costs and prior claim exceed sale proceeds')
        need(quantities['borrower_cash_first'] <= due['borrower_principal'], 'first borrower payment exceeds scheduled principal')
        need(quantities['borrower_cash_first'] + quantities['borrower_cash_final'] + net <= bank['domestic_loan_face'], 'borrower cash collections exceed the face claim')
        need(quantities['foreign_recovery'] <= bank['foreign_claim_face'], 'foreign collection exceeds face claim')
        need(max(choices['prefund_foreign']) + quantities['early_fx_cap'] <= endowment['dealer_foreign_cash'], 'dealer cannot fund prefunding and early conversion commitments')
        need(spot * quantities['late_fx_cap'] <= endowment['dealer_home_cash'], 'dealer cannot fund the late conversion commitment')
        need(type(scenario['prefund_timely']) is bool, 'prefund_timely must be boolean')
    need(len(set(ids)) == len(ids) and probability == 1, 'scenario IDs must be unique and physical probabilities sum exactly to one')
    need(type(data['reverse_scenario']) is str and data['reverse_scenario'] in ids, 'reverse scenario must identify a listed state')


def evaluate(data, policy, scenario, journal=False, price_override=None):
    b, f, z = policy
    bank = {k: Q(v) for k, v in data['bank'].items()}
    due = {k: Q(v) for k, v in data['first_due'].items()}
    endowed = {k: Q(v) for k, v in data['endowments'].items()}
    s0, spot = Q(data['initial_spot']), Q(scenario['spot'])
    quote = 1 / (1 + Q(scenario['bond_yield'])) ** 2 if price_override is None else price_override
    eligible, rate = Q(data['facility']['eligible_bond_units']), Q(data['facility']['interest'])
    floor, equity_floor = Q(data['limits']['home_reserve']), Q(data['limits']['bank_equity'])
    net_collateral = Q(scenario['collateral_gross']) - Q(scenario['collateral_cost']) - Q(scenario['collateral_prior_claim'])
    borrower_first = Q(scenario['borrower_cash_first'])
    borrower_final = Q(scenario['borrower_cash_final']) + net_collateral
    domestic_loss = bank['domestic_loan_face'] - borrower_first - borrower_final
    foreign_recovery = Q(scenario['foreign_recovery'])
    foreign_loss = bank['foreign_claim_face'] - foreign_recovery
    state = dict(home_cash=bank['home_cash'], foreign_cash=bank['foreign_cash'], foreign_in_transit=Q(0),
                 bill=bank['bill'], long_bonds=bank['long_bond_units'], domestic_loan=bank['domestic_loan_face'],
                 foreign_claim=bank['foreign_claim_face'], household_deposits=bank['household_deposits'],
                 pension_deposit=bank['pension_deposit'], foreign_deposits=bank['foreign_deposits'], secured_claim=Q(0))
    valuation_spot = s0
    pledged, rows = Q(0), []
    pension_cash = Q(data['pension']['cash'])
    benefits = Q(data['pension']['benefits'])
    sponsor_cash = endowed['sponsor_home_cash']
    lender_cash = endowed['lender_home_cash']
    dealer_home, dealer_foreign = endowed['dealer_home_cash'], endowed['dealer_foreign_cash']

    def balance():
        assets = state['home_cash'] + state['bill'] + state['long_bonds'] + state['domestic_loan'] + valuation_spot * (state['foreign_cash'] + state['foreign_in_transit'] + state['foreign_claim'])
        liabilities = state['household_deposits'] + state['pension_deposit'] + state['secured_claim'] + valuation_spot * state['foreign_deposits']
        return dict(assets_H=assets, liabilities_H=liabilities, equity_H=assets - liabilities)

    initial_equity = balance()['equity_H']

    def post(time, event, changes):
        for key, amount in changes.items(): state[key] += amount
        need(all(v >= 0 for v in state.values()), 'negative executed bank asset or liability')
        need(min(pension_cash, benefits, sponsor_cash, lender_cash, dealer_home, dealer_foreign) >= 0, 'unfunded counterparty cash or negative benefit claim')
        snapshot = dict(time=time, event=event, changes=dict(changes), bank=dict(state), valuation_spot=valuation_spot,
                        balance=balance(), pledged_units=pledged, pension_cash=pension_cash, pension_benefits_unpaid=benefits,
                        pension_net_assets_at_bank_claim_face=pension_cash + state['pension_deposit'] - benefits,
                        sponsor_cash=sponsor_cash, lender_cash=lender_cash, dealer_home_cash=dealer_home, dealer_foreign_cash=dealer_foreign)
        if journal: rows.append(snapshot)
        return snapshot

    post('opening', 'reference inventory and separate endowed cash', {})
    sponsor_cash -= b
    post('before_early', 'received funded equity subscription', {'home_cash': b})
    sponsor_cash -= z; pension_cash += z
    post('before_early', 'sponsor paid separate pension contribution', {})
    dealer_home += s0 * f; dealer_foreign -= f
    prefund_account = 'foreign_cash' if scenario['prefund_timely'] else 'foreign_in_transit'
    post('before_early', 'paid for prefunding; record actual foreign delivery status', {'home_cash': -s0 * f, prefund_account: f})
    valuation_spot = spot
    marked = post('before_early', 'recognize FX, long-bond and loan impairment once',
                  {'long_bonds': bank['long_bond_units'] * (quote - 1), 'domestic_loan': -domestic_loss, 'foreign_claim': -foreign_loss})
    early_need = max(Q(0), due['foreign_deposits'] - state['foreign_cash'])
    early_fx = min(early_need, Q(scenario['early_fx_cap']), state['home_cash'] / spot)
    dealer_home += spot * early_fx; dealer_foreign -= early_fx
    post('early_09', 'delivered limited early H-to-F conversion', {'home_cash': -spot * early_fx, 'foreign_cash': early_fx})
    foreign_first = min(state['foreign_cash'], due['foreign_deposits'])
    foreign_close = post('early_09', 'paid early foreign deposit claim from foreign cash', {'foreign_cash': -foreign_first, 'foreign_deposits': -foreign_first})
    post('early_10', 'received borrower first principal cash', {'home_cash': borrower_first, 'domestic_loan': -borrower_first})
    requested_draw = max(Q(0), floor + due['households'] + bank['pension_deposit'] - state['home_cash'])
    capacity = min(endowed['lender_home_cash'], eligible * quote * (1 - Q(scenario['haircut'])))
    draw = min(requested_draw, capacity)
    pledged = draw / (quote * (1 - Q(scenario['haircut'])))
    lender_cash -= draw
    post('early_10', 'received funded secured advance against separate long bonds', {'home_cash': draw, 'secured_claim': draw})
    household_first = min(state['home_cash'], due['households'])
    post('early_10', 'paid priority household withdrawals', {'home_cash': -household_first, 'household_deposits': -household_first})
    pension_first = min(state['home_cash'], bank['pension_deposit'])
    pension_cash += pension_first
    home_close = post('early_10', 'paid pension withdrawal with remaining actual home cash', {'home_cash': -pension_first, 'pension_deposit': -pension_first})
    benefit_first = min(pension_cash, benefits)
    pension_cash -= benefit_first; benefits -= benefit_first
    pension_close = post('early_1015', 'pension paid due benefits; retain any missed claim', {})
    delayed = state['foreign_in_transit']
    post('final_17', 'received previously paid in-transit prefunding', {'foreign_cash': delayed, 'foreign_in_transit': -delayed})
    post('final_17', 'received actual foreign claim recovery', {'foreign_cash': foreign_recovery, 'foreign_claim': -foreign_recovery})
    foreign_final = min(state['foreign_cash'], state['foreign_deposits'])
    post('final_17', 'paid remaining foreign deposits including any early arrears', {'foreign_cash': -foreign_final, 'foreign_deposits': -foreign_final})
    post('final_18', 'maturing bill paid from its separately funded promise', {'home_cash': bank['bill'], 'bill': -bank['bill']})
    post('final_18', 'received borrower final operating and net collateral cash', {'home_cash': borrower_final, 'domestic_loan': -borrower_final})
    interest = rate * draw
    post('final_18', 'accrued secured interest as an expense and payable claim', {'secured_claim': interest})
    late_need_H = max(Q(0), floor + state['secured_claim'] + state['household_deposits'] + state['pension_deposit'] - state['home_cash'])
    late_fx = min(state['foreign_cash'], Q(scenario['late_fx_cap']), late_need_H / spot)
    dealer_home -= spot * late_fx; dealer_foreign += late_fx
    post('final_18', 'received limited late F-to-H conversion before home payments', {'foreign_cash': -late_fx, 'home_cash': spot * late_fx})
    secured_paid = min(state['home_cash'], state['secured_claim'])
    lender_cash += secured_paid
    if secured_paid == state['secured_claim']: pledged = Q(0)
    post('final_18', 'paid senior secured claim; release collateral only if fully repaid', {'home_cash': -secured_paid, 'secured_claim': -secured_paid})
    household_final = min(state['home_cash'], state['household_deposits'])
    post('final_18', 'paid remaining household claims before pension arrears', {'home_cash': -household_final, 'household_deposits': -household_final})
    pension_final = min(state['home_cash'], state['pension_deposit'])
    pension_cash += pension_final
    final_close = post('final_18', 'paid remaining pension bank claim', {'home_cash': -pension_final, 'pension_deposit': -pension_final})
    benefit_final = min(pension_cash, benefits)
    pension_cash -= benefit_final; benefits -= benefit_final
    network_close = post('final_1815', 'pension paid retained benefit arrears when cash actually arrived', {})
    early_shortfalls = dict(foreign_F=due['foreign_deposits'] - foreign_first,
                            households_H=due['households'] - household_first,
                            pension_bank_claim_H=bank['pension_deposit'] - pension_first,
                            pension_benefits_H=Q(data['pension']['benefits']) - benefit_first)
    final_shortfalls = dict(foreign_F=state['foreign_deposits'], households_H=state['household_deposits'],
                            pension_bank_claim_H=state['pension_deposit'], pension_benefits_H=benefits,
                            secured_H=state['secured_claim'])
    timely = all(v == 0 for v in early_shortfalls.values()) and all(v == 0 for v in final_shortfalls.values())
    cash_ok = home_close['bank']['home_cash'] >= floor and final_close['bank']['home_cash'] >= floor
    equity_ok = home_close['balance']['equity_H'] >= equity_floor and final_close['balance']['equity_H'] >= equity_floor
    market_fx = (bank['foreign_cash'] + f + bank['foreign_claim_face'] - bank['foreign_deposits']) * (spot - s0)
    market_bond = bank['long_bond_units'] * (quote - 1)
    reconciliation = initial_equity + b + market_fx + market_bond - domestic_loss - spot * foreign_loss - interest
    need(reconciliation == final_close['balance']['equity_H'], 'capital-flow-adjusted equity reconciliation')
    result = dict(scenario=scenario['id'], bond_price=quote,
                  borrower=dict(primary_cash_first=borrower_first, primary_cash_final=Q(scenario['borrower_cash_final']),
                                collateral_net_to_bank=net_collateral, actual_final_receipt=borrower_final,
                                first_service_ratio=borrower_first / due['borrower_principal'],
                                final_operating_service_ratio=Q(scenario['borrower_cash_final']) / (bank['domestic_loan_face'] - due['borrower_principal']),
                                first_nominal_arrears=due['borrower_principal'] - borrower_first,
                                terminal_nominal_unpaid=domestic_loss, recognized_credit_loss=domestic_loss,
                                terminal_carrying_asset=state['domestic_loan']),
                  foreign_issuer_nominal_unpaid_F=foreign_loss,
                  early_conversion_F=early_fx, late_conversion_F=late_fx,
                  requested_secured_H=requested_draw, secured_capacity_H=capacity, secured_draw_H=draw,
                  pledged_units_initial=draw / (quote * (1 - Q(scenario['haircut']))), secured_interest_H=interest,
                  early_shortfalls=early_shortfalls, final_shortfalls=final_shortfalls,
                  early_foreign_close=foreign_close, early_home_close=home_close,
                  early_pension_close=pension_close, final_home_close=final_close, final_network_close=network_close,
                  equity_bridge=dict(reference_equity_H=initial_equity, received_equity_H=b, fx_mark_H=market_fx,
                                     bond_mark_H=market_bond, domestic_credit_loss_H=domestic_loss,
                                     foreign_credit_loss_H=spot * foreign_loss, interest_expense_H=interest,
                                     closing_equity_H=reconciliation, capital_flow_adjusted_loss_H=initial_equity + b - reconciliation),
                  external_funding=dict(sponsor_cash_committed_H=b + z, sponsor_cash_remaining_H=sponsor_cash,
                                        new_investor_equity_fraction=b / (initial_equity + b),
                                        new_investor_closing_marked_stake_H=b * reconciliation / (initial_equity + b),
                                        lender_cash_remaining_H=lender_cash, lender_claim_H=state['secured_claim'],
                                        dealer_home_cash=dealer_home, dealer_foreign_cash=dealer_foreign),
                  gates=dict(every_external_claim_timely=timely, home_reserve_met=cash_ok, bank_equity_floor_met=equity_ok),
                  feasible=timely and cash_ok and equity_ok)
    if journal: result['journal'] = rows
    return result


def tail_measure(losses, alpha):
    ordered = sorted(losses)
    cumulative, quantile = Q(0), None
    for loss, probability in ordered:
        cumulative += probability
        if quantile is None and cumulative >= alpha: quantile = loss
    remaining, numerator = 1 - alpha, Q(0)
    allocation = []
    for loss, probability in reversed(ordered):
        used = min(remaining, probability)
        if used:
            numerator += used * loss
            allocation.append(dict(loss_H=loss, probability_used=used))
            remaining -= used
    need(remaining == 0, 'incomplete tail probability')
    return dict(alpha=alpha, expected_loss_H=sum(loss * p for loss, p in ordered),
                var_H=quantile, expected_shortfall_H=numerator / (1 - alpha), tail_allocation=allocation)


def reverse_certificate(data, policy, scenario):
    reference = evaluate(data, policy, scenario)
    need(reference['feasible'], 'reverse certificate requires a feasible fixed policy')
    draw = reference['requested_secured_H']
    units, eligible = Q(data['bank']['long_bond_units']), Q(data['facility']['eligible_bond_units'])
    collateral_slope = eligible * (1 - Q(scenario['haircut']))
    collateral_floor = draw / collateral_slope if draw else Q(0)
    bridge = reference['equity_bridge']
    no_bond_equity = (bridge['reference_equity_H'] + bridge['received_equity_H'] + bridge['fx_mark_H']
                      - units - bridge['domestic_credit_loss_H'] - bridge['foreign_credit_loss_H'])
    equity_floor = max(Q(0), (Q(data['limits']['bank_equity']) - no_bond_equity
                            + Q(data['facility']['interest']) * draw) / units)
    critical = max(collateral_floor, equity_floor)
    lower, upper = Q(0), Q(4)
    within = Q(1, 25) <= critical <= 1
    bracket = None
    if within:
        for _ in range(48):
            middle = (lower + upper) / 2
            if 1 / (1 + middle) ** 2 >= critical: lower = middle
            else: upper = middle
        bracket = [lower, upper]
    at_boundary = evaluate(data, policy, scenario, price_override=critical) if critical > 0 else None
    return dict(scenario=scenario['id'], fixed_policy=dict(zip(('bank_equity_H', 'prefund_F', 'pension_contribution_H'), policy)),
                held_fixed='Every other contract, receipt, price, FX rule, funding rule and monitoring time; only the long-bond yield changes.',
                required_draw_H=draw, collateral_price_floor=collateral_floor, equity_price_floor=equity_floor,
                binding_price_floor=critical, equality_feasible=at_boundary['feasible'] if at_boundary else True,
                boundary_within_supported_yield_0_to_4=within, yield_boundary_bracket=bracket,
                yield_boundary_formula='1/sqrt(binding_price_floor) - 1 when the positive price boundary lies in the supported domain',
                boundary_final_equity_H=at_boundary['equity_bridge']['closing_equity_H'] if at_boundary else None,
                limits='No probability or date of failure inferred; this is a fixed-policy one-factor boundary, not a general scenario-search optimum.')


def encode(obj):
    if isinstance(obj, Q): return str(obj)
    if type(obj) is dict: return {k: encode(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)): return [encode(v) for v in obj]
    return obj


def run(data):
    validate(data)
    choices = data['choices']
    candidates, feasible = [], []
    names = ('bank_equity_H', 'prefund_F', 'pension_contribution_H')
    grid = sorted(product(*(map(Q, choices[k]) for k in ('bank_equity', 'prefund_foreign', 'pension_contribution'))))
    for policy in grid:
        results = [evaluate(data, policy, scenario) for scenario in data['scenarios']]
        b, f, z = policy
        good = all(result['feasible'] for result in results)
        row = dict(policy=dict(zip(names, policy)), outside_cash_commitment_H=b + z, feasible=good, scenarios=results)
        candidates.append(row)
        if good: feasible.append(((b + z, f, b, z), policy, row))
    feasible.sort(key=lambda x: x[0])
    selected, risk, certificate = None, None, None
    if feasible:
        _, policy, chosen = feasible[0]
        selected = dict(policy=chosen['policy'], outside_cash_commitment_H=chosen['outside_cash_commitment_H'],
                        scenarios=[evaluate(data, policy, scenario, journal=True) for scenario in data['scenarios']])
        losses = [(row['equity_bridge']['capital_flow_adjusted_loss_H'], Q(scenario['probability']))
                  for row, scenario in zip(selected['scenarios'], data['scenarios'])]
        risk = tail_measure(losses, Q(data['risk_alpha']))
        risk['interpretation'] = 'Stipulated physical scenario probabilities, used only for this finite loss distribution; not pricing probabilities, estimated frequencies, or the robust feasibility criterion.'
        scenario = next(s for s in data['scenarios'] if s['id'] == data['reverse_scenario'])
        certificate = reverse_certificate(data, policy, scenario)
    return encode(dict(schema=1, provenance=data['provenance'],
                       decision_rule='Minimize gross outside cash b+z among policies passing every scenario; then lower prefunded F, bank equity and pension grant to resolve exact ties. No welfare or universal optimum claim.',
                       execution_scope='Every candidate makes actual capped payments in the stipulated priority order. Reserves are monitoring constraints, not claimants. Late payment never erases an earlier missed deadline; remaining claims are retained.',
                       candidate_count=len(candidates), feasible_count=len(feasible), candidates=candidates,
                       selected=selected, selected_loss_measure=risk, reverse_stress=certificate,
                       limits='Original finite contracts. Long-bond mark is retained at a fixed remaining-maturity convention; marked equity is not cash. Pension bank claims are reconciled at face, not certified economic recovery values. Legal borrower arrears survive writeoff; actual authority, evidence, calibration and all later dates remain outside this model.'))


def strict_object(pairs):
    result = {}
    for key, value in pairs:
        need(key not in result, 'duplicate JSON key')
        result[key] = value
    return result


def protect_output(output, sources):
    for source in sources:
        need(output.resolve() != source.resolve(), 'output would overwrite protected input/model')
        if output.exists(): need(not output.samefile(source), 'output aliases protected input/model')


def main():
    here = Path(__file__).resolve()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=here.with_name('v11-assessment-inputs.json'))
    parser.add_argument('--output', type=Path, default=here.with_name('v11-assessment-output.json'))
    args = parser.parse_args()
    try:
        protect_output(args.output, (args.input, here))
        need(args.input.stat().st_size <= 65536, 'input exceeds 65536 bytes')
        def bad_constant(value): raise ValueError('nonfinite JSON constant: ' + value)
        data = json.loads(args.input.read_text(encoding='utf-8'), object_pairs_hook=strict_object, parse_constant=bad_constant)
        result = run(data)
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    except (ValueError, OSError, RecursionError) as error:
        parser.exit(2, str(error) + '\n')


if __name__ == '__main__':
    main()
