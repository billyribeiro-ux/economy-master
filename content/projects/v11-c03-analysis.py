"""Bounded, exact-rational Morrow Components credit-underwriting teaching lab."""
import argparse
from fractions import Fraction as F
import json
from pathlib import Path
import re

SCHEMA = 'v11-c03-morrow-1'
PROVENANCE = 'Original synthetic Morrow Components underwriting case; no observed borrower, market data or real lending approval.'
NUMBER = re.compile(r'-?(?:(?:0|[1-9][0-9]{0,5})(?:\.[0-9]{1,8})?|[1-9][0-9]{0,5}/[1-9][0-9]{0,5})\Z')
IDENTIFIER = re.compile(r'[a-z][a-z0-9_]{0,31}\Z')


def need(condition, message):
    if not condition:
        raise ValueError(message)


def keys(value, expected, label):
    need(type(value) is dict and set(value) == set(expected.split()), label+' has incorrect keys or type')


def number(value, low, high, label):
    need(type(value) is str and len(value) <= 24 and NUMBER.fullmatch(value) is not None,
         label+' must be a bounded plain decimal or rational string')
    result = F(value)
    need(low <= result <= high, label+' is outside its declared range')
    return result


def vector(value, low, high, label):
    need(type(value) is list and len(value) == 3, label+' must have three annual entries')
    return [number(x, low, high, label) for x in value]


def integer(value, low, high, label):
    need(type(value) is int and low <= value <= high, label+' is not a supported integer')


def named_rows(value, low, high, label):
    need(type(value) is list and low <= len(value) <= high, label+' has an unsupported row count')
    seen = set()
    for row in value:
        need(type(row) is dict and type(row.get('id')) is str and IDENTIFIER.fullmatch(row['id']) is not None,
             label+' has an invalid identifier')
        need(row['id'] not in seen, label+' has duplicate identifiers')
        seen.add(row['id'])


def validate(data):
    keys(data, 'schema provenance business scenarios proposals collateral policy', 'input')
    need(data['schema'] == SCHEMA and data['provenance'] == PROVENANCE, 'unknown schema or provenance')
    b = data['business']
    keys(b, 'capital_purchase depreciation valuation_hurdle terminal_operating_value', 'business')
    number(b['capital_purchase'], 1, 999999, 'capital_purchase')
    vector(b['depreciation'], 0, 999999, 'depreciation')
    number(b['valuation_hurdle'], 0, F(1,2), 'valuation_hurdle')
    number(b['terminal_operating_value'], 0, 999999, 'terminal_operating_value')
    named_rows(data['scenarios'], 2, 4, 'scenarios')
    need(sum(row['id'] == 'base' for row in data['scenarios']) == 1, 'exactly one base scenario is required')
    for row in data['scenarios']:
        keys(row, 'id ebitda cash_taxes maintenance_capex working_capital_increase', 'scenario')
        vector(row['ebitda'], -999999, 999999, 'ebitda')
        vector(row['cash_taxes'], 0, 999999, 'cash_taxes')
        vector(row['maintenance_capex'], 0, 999999, 'maintenance_capex')
        vector(row['working_capital_increase'], -999999, 999999, 'working_capital_increase')
    named_rows(data['proposals'], 1, 4, 'proposals')
    for row in data['proposals']:
        keys(row, 'id advance sponsor_cash rate principal evidence', 'proposal')
        advance = number(row['advance'], 1, 999999, 'advance')
        number(row['sponsor_cash'], 0, 999999, 'sponsor_cash')
        rate = number(row['rate'], 0, F(1,2), 'rate')
        principal = vector(row['principal'], 0, 999999, 'principal')
        need(sum(principal) == advance, 'principal schedule must repay exactly the advance')
        balance = advance
        for amortization in principal:
            need(balance*rate+amortization > 0, 'every annual debt-service amount must be positive')
            balance -= amortization
        keys(row['evidence'], 'sponsor_cash_verified cash_forecast_verified priority_verified', 'evidence')
        need(all(type(x) is bool for x in row['evidence'].values()), 'evidence flags must be booleans')
    c = data['collateral']
    keys(c, 'default_year recovery_delay_years assets workout_cost prior_claim assessment_rate physical_default_weight', 'collateral')
    integer(c['default_year'], 1, 3, 'default_year')
    integer(c['recovery_delay_years'], 0, 3, 'recovery_delay_years')
    named_rows(c['assets'], 1, 6, 'assets')
    for row in c['assets']:
        keys(row, 'id gross_value eligible_fraction realization_fraction', 'asset')
        number(row['gross_value'], 0, 999999, 'gross_value')
        number(row['eligible_fraction'], 0, 1, 'eligible_fraction')
        number(row['realization_fraction'], 0, 1, 'realization_fraction')
    for field in ('workout_cost', 'prior_claim'):
        number(c[field], 0, 999999, field)
    number(c['assessment_rate'], 0, F(1,2), 'assessment_rate')
    number(c['physical_default_weight'], 0, 1, 'physical_default_weight')
    p = data['policy']
    keys(p, 'minimum_cash minimum_base_dscr maximum_initial_debt_ebitda minimum_scenario_margin', 'policy')
    number(p['minimum_cash'], 0, 999999, 'minimum_cash')
    number(p['minimum_base_dscr'], 1, 3, 'minimum_base_dscr')
    number(p['maximum_initial_debt_ebitda'], F(1,4), 10, 'maximum_initial_debt_ebitda')
    number(p['minimum_scenario_margin'], 0, 999999, 'minimum_scenario_margin')


def encoded(value):
    if isinstance(value, F):
        return str(value)
    if type(value) is dict:
        return {key: encoded(item) for key, item in value.items()}
    if type(value) is list:
        return [encoded(item) for item in value]
    return value


def run(data):
    """Return strict JSON-compatible evidence; do not mutate input, print or write."""
    validate(data)
    b, c, policy = data['business'], data['collateral'], data['policy']
    floor, required_dscr = F(policy['minimum_cash']), F(policy['minimum_base_dscr'])
    cfads = {row['id']: [F(e)-F(t)-F(k)-F(w) for e,t,k,w in zip(
        row['ebitda'], row['cash_taxes'], row['maintenance_capex'], row['working_capital_increase'])]
        for row in data['scenarios']}
    base = next(row for row in data['scenarios'] if row['id'] == 'base')
    hurdle = F(b['valuation_hurdle'])
    # This valuation distributes CFADS annually and returns the operating cash
    # requirement with terminal business value. It is not the loan cash ledger.
    project_pv = sum(cash/(1+hurdle)**year for year,cash in enumerate(cfads['base'],1))
    project_pv += (F(b['terminal_operating_value'])+floor)/(1+hurdle)**3
    project_cost = F(b['capital_purchase'])+floor
    realization = [{'id':row['id'], 'eligible_value':F(row['gross_value'])*F(row['eligible_fraction']),
                    'sale_cash':F(row['gross_value'])*F(row['eligible_fraction'])*F(row['realization_fraction'])}
                   for row in c['assets']]
    gross = sum(row['sale_cash'] for row in realization)
    cost_paid = min(gross,F(c['workout_cost']))
    net = gross-cost_paid
    prior_paid = min(net,F(c['prior_claim']))
    available = net-prior_paid
    default_year = c['default_year']
    recovery_year = default_year+c['recovery_delay_years']
    assessment = F(c['assessment_rate']); pd = F(c['physical_default_weight'])
    proposals = []
    for proposal in data['proposals']:
        advance, rate = F(proposal['advance']), F(proposal['rate'])
        opening_cash = advance+F(proposal['sponsor_cash'])-F(b['capital_purchase'])
        balance = advance; schedule = []
        for year, payment in enumerate(proposal['principal'],1):
            principal = F(payment); interest = rate*balance
            schedule.append({'year':year,'opening_principal':balance,'interest':interest,
                             'principal':principal,'service':principal+interest,'closing_principal':balance-principal})
            balance -= principal
        scenario_results = []
        for scenario in data['scenarios']:
            cash = opening_cash; minimum = cash
            first_floor = 0 if cash < floor else None
            first_shortfall = 0 if cash < 0 else None
            rows = []
            for i, payment in enumerate(schedule):
                flow = cfads[scenario['id']][i]
                before = cash+flow; after = before-payment['service']
                dscr = flow/payment['service']
                rows.append({'year':i+1,'cfads':flow,
                             'income_if_tax_expense_equals_cash_tax':F(scenario['ebitda'][i])-F(b['depreciation'][i])-payment['interest']-F(scenario['cash_taxes'][i]),
                             'dscr':dscr,'dscr_headroom_cash':flow-required_dscr*payment['service'],
                             'cash_before_service_on_contract_projection':before,
                             'cash_after_service_on_contract_projection':after})
                cash = after; minimum = min(minimum,cash)
                if first_floor is None and cash < floor: first_floor = i+1
                if first_shortfall is None and cash < 0: first_shortfall = i+1
            scenario_results.append({'id':scenario['id'],'rows':rows,'minimum_projected_cash':minimum,
                                     'first_cash_floor_breach_year':first_floor,
                                     'first_payment_shortfall_year':first_shortfall,
                                     'minimum_initial_injection_for_cash_floor':max(F(0),floor-minimum),
                                     'dscr_breach_years':[row['year'] for row in rows if row['dscr'] < required_dscr]})
        claim_row = schedule[default_year-1]
        claim = claim_row['opening_principal']+claim_row['interest']
        recovery = min(claim,available)
        promised_pv = sum(row['service']/(1+assessment)**row['year'] for row in schedule)
        prior_receipts_pv = sum(row['service']/(1+assessment)**row['year'] for row in schedule if row['year'] < default_year)
        default_pv = prior_receipts_pv+recovery/(1+assessment)**recovery_year
        weighted_pv = (1-pd)*promised_pv+pd*default_pv
        recovery_at_default = recovery/(1+assessment)**c['recovery_delay_years']
        collateral_result = {'claim_at_default':claim,'recovery_year':recovery_year,'lender_recovery':recovery,
                             'junior_residual':available-recovery,'nominal_claim_loss':claim-recovery,
                             'recovery_fraction_of_claim':recovery/claim,
                             'recovery_discounted_to_default':recovery_at_default,
                             'discounted_claim_shortfall_at_default':claim-recovery_at_default,
                             'promised_receipts_pv':promised_pv,'default_branch_receipts_pv':default_pv,
                             'physical_scenario_weighted_receipts_pv':weighted_pv,
                             'physical_scenario_margin_over_advance':weighted_pv-advance,
                             'weighted_shortfall_from_promised_pv':promised_pv-weighted_pv}
        ebitda = F(base['ebitda'][0])
        leverage = advance/ebitda if ebitda > 0 else None
        base_results = next(row for row in scenario_results if row['id'] == 'base')
        gates = {'initial_sources_cover_purchase_and_cash_floor':opening_cash >= floor,
                 'base_dscr_meets_defined_floor':not base_results['dscr_breach_years'],
                 'initial_debt_ebitda_within_limit':leverage is not None and leverage <= F(policy['maximum_initial_debt_ebitda']),
                 'all_scenario_payment_dates_preserve_cash_floor':all(row['minimum_projected_cash'] >= floor for row in scenario_results),
                 'physical_scenario_margin_meets_assumed_hurdle':weighted_pv-advance >= F(policy['minimum_scenario_margin']),
                 'required_evidence_recorded':all(proposal['evidence'].values())}
        failures = [key for key,value in gates.items() if not value]
        quantitative = all(value for key,value in gates.items() if key != 'required_evidence_recorded')
        recommendation = ('eligible_for_credit_committee_review' if not failures else
                          'hold_for_evidence' if quantitative else 'restructure_or_refuse')
        proposals.append({'id':proposal['id'],'advance':advance,'sponsor_cash':F(proposal['sponsor_cash']),
                          'opening_cash_if_sources_received':opening_cash,
                          'initial_funding_gap_to_cash_floor':max(F(0),floor-opening_cash),
                          'initial_debt_ebitda':leverage,'contract_schedule':schedule,
                          'scenarios':scenario_results,'collateral_branch':collateral_result,
                          'gates':gates,'failed_gates':failures,'recommendation':recommendation})
    result = encoded({'schema':SCHEMA+'-output','provenance':PROVENANCE,
                      'operating_cfads':cfads,
                      'illustrative_unlevered_valuation':{'initial_uses':project_cost,'pv':project_pv,'npv':project_pv-project_cost,
                          'scope':'Base forecasts distributed annually, minimum cash released with assumed terminal business value; chosen hurdle, not a traded price or a dated debt-service guarantee.'},
                      'collateral_waterfall':{'asset_realizations':realization,'gross_sale_cash':gross,'workout_cost_paid':cost_paid,
                          'unpaid_workout_cost':F(c['workout_cost'])-cost_paid,'prior_claim_paid':prior_paid,
                          'unpaid_prior_claim':F(c['prior_claim'])-prior_paid,'available_to_this_lender_and_juniors':available},
                      'proposals':proposals,
                      'scope':'Three annual end-date projections with no cash interest, distributions or automatic new borrowing. Negative projected balances expose missing finance; they are not completed payments after default. The separate default branch assumes prior instalments paid, no other estate cash and no later operating cash. Scenario weights and assessment rate are stipulated physical-analysis inputs, not a Q law or fair-value proof. Evidence flags record assumptions; no real lending approval.'})
    json.dumps(result,allow_nan=False)
    return result


def strict_pairs(pairs):
    result = {}
    for key,value in pairs:
        need(key not in result,'duplicate JSON key: '+key)
        result[key] = value
    return result


def reject_constant(value):
    raise ValueError('nonfinite JSON constant: '+value)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,default=Path(__file__).with_name('v11-c03-inputs.json'))
    parser.add_argument('--output',type=Path)
    args = parser.parse_args()
    need(args.input.stat().st_size <= 1000000,'input exceeds one megabyte')
    data = json.loads(args.input.read_text(encoding='utf-8'),object_pairs_hook=strict_pairs,parse_constant=reject_constant)
    payload = json.dumps(run(data),indent=2,allow_nan=False)+'\n'
    if args.output is None:
        print(payload,end='')
    else:
        for protected in (args.input,Path(__file__)):
            same_path = args.output.resolve() == protected.resolve()
            same_inode = args.output.exists() and protected.exists() and args.output.samefile(protected)
            need(not (same_path or same_inode),'output must not overwrite input or implementation')
        args.output.write_text(payload,encoding='utf-8')


if __name__ == '__main__':
    main()
