"""Frozen historical transformations and exact fictional macro accounts.

Run with Python 3; optional sole argument is a compatible local JSON input path.
Only the standard library is used. No source is fetched, file overwritten or
investment/policy recommendation generated. Importing this module is quiet.
"""
from datetime import date
from fractions import Fraction as F
import json
from pathlib import Path
import sys

PARAMETERS = {'c0', 'c', 'tax_rate', 'import_share', 'exports', 'e',
              'external_debt_open', 'external_interest_rate', 'reserves_open',
              'reserve_floor', 'private_foreign_loan', 'public_debt_open',
              'public_gross_return', 'public_maturity', 'public_issuance_capacity',
              'investment_sensitivity', 'reference_output', 'reference_real_rate'}
OBSERVATIONS = {'real_gdp_q4', 'nominal_gdp_q4', 'real_gdp_year', 'payroll_change',
                'unemployment', 'participation', 'employment_population',
                'cpi_month', 'cpi_year', 'current_account_q3',
                'current_account_q2_revised', 'current_account_q2_previous'}


def validate(data):
    if data.get('schema') != 'v06-assessment-1':
        raise ValueError('unsupported schema')
    cutoff = date.fromisoformat(data['information_cutoff'][:10])
    rows = data['observations']
    ids = [row['id'] for row in rows]
    if len(ids) != len(set(ids)) or set(ids) != OBSERVATIONS:
        raise ValueError('missing, duplicate or unknown observation ID')
    for row in rows:
        F(row['value'])
        if date.fromisoformat(row['release']) > cutoff:
            raise ValueError('observation source is beyond information cutoff')
        for key in ('unit', 'period', 'frequency', 'adjustment', 'vintage', 'source'):
            if not isinstance(row[key], str) or not row[key].strip():
                raise ValueError('incomplete observation metadata')
        if not row['source'].startswith('https://'):
            raise ValueError('expected explicit public source URL')
    p = data['synthetic']['parameters']
    if set(p) != PARAMETERS:
        raise ValueError('missing or unknown synthetic parameter')
    p = {k: F(v) for k, v in p.items()}
    if any(p[k] < 0 for k in PARAMETERS-{'reference_real_rate'}):
        raise ValueError('negative quantity or inadmissible coefficient')
    if not (0 <= p['c'] < 1 and 0 <= p['tax_rate'] < 1
            and 0 <= p['import_share'] < 1 and p['e'] > 0
            and p['public_gross_return'] >= 1 and p['reference_output'] > 0
            and p['public_maturity'] <= p['public_debt_open']):
        raise ValueError('inadmissible rate, quote or maturity')
    names = []
    for s in data['synthetic']['scenarios']:
        if set(s) != {'id', 'investment_intercept', 'government_consumption', 'rate_feedback'}:
            raise ValueError('invalid scenario fields')
        if not isinstance(s['id'], str) or not s['id']:
            raise ValueError('scenario ID must be a nonempty string')
        names.append(s['id'])
        if any(F(s[k]) < 0 for k in s if k != 'id'):
            raise ValueError('negative scenario spending or feedback')
    if not names or len(names) != len(set(names)):
        raise ValueError('empty or duplicate scenario IDs')
    return p


def historical(data):
    d = {r['id']: F(r['value']) for r in data['observations']}
    real = 1+d['real_gdp_q4']/100
    nominal = 1+d['nominal_gdp_q4']/100
    monthly = 1+d['cpi_month']/100
    if min(real, nominal, monthly) <= 0 or d['participation'] <= 0:
        raise ValueError('invalid gross factor or participation denominator')
    return {
        'real_quarter_percent_from_rounded_headline': 100*(float(real)**.25-1),
        'implied_deflator_annual_percent_from_rounded_headlines': 100*(nominal/real-1),
        'constant_monthly_cpi_annual_percent_not_forecast': 100*(monthly**12-1),
        'naive_unemployment_percent_from_rounded_ratios': 100*(1-d['employment_population']/d['participation']),
        'current_account_q2_revision_billion_usd': d['current_account_q2_revised']-d['current_account_q2_previous'],
        'current_account_q3_change_using_same_release_billion_usd': d['current_account_q3']-d['current_account_q2_revised'],
        'current_account_q3_mixed_vintage_change_billion_usd': d['current_account_q3']-d['current_account_q2_previous']
    }


def scenario(p, s):
    i0, g, psi = (F(s[k]) for k in ('investment_intercept', 'government_consumption', 'rate_feedback'))
    foreign_interest = p['external_interest_rate']*p['external_debt_open']
    income_abroad = -p['e']*foreign_interest
    bp = p['investment_sensitivity']*psi
    denominator = 1-p['c']*(1-p['tax_rate'])+p['import_share']+bp
    if denominator <= 0:
        raise ValueError('nonpositive goods-market denominator')
    y = (p['c0']+p['c']*income_abroad+i0+g+p['exports']+bp*p['reference_output'])/denominator
    r = p['reference_real_rate']+psi*(y-p['reference_output'])
    investment = i0-p['investment_sensitivity']*(r-p['reference_real_rate'])
    taxes = p['tax_rate']*y
    consumption = p['c0']+p['c']*(y-taxes+income_abroad)
    imports = p['import_share']*y
    if min(y, investment, consumption) < 0 or y == 0:
        raise ValueError('negative modeled activity or zero GDP denominator')
    gndi = y+income_abroad
    saving = gndi-consumption-g
    ca = p['exports']-imports+income_abroad
    primary = taxes-g
    public_interest = (p['public_gross_return']-1)*p['public_debt_open']
    debt = p['public_debt_open']+public_interest-primary
    issuance = p['public_maturity']+public_interest-primary
    if min(debt, issuance) < 0:
        raise ValueError('negative public debt/issuance requires a new asset policy')
    pre_official_reserves = (p['reserves_open']+p['exports']/p['e']
                            +p['private_foreign_loan']-imports/p['e']
                            -p['external_debt_open']-foreign_interest)
    official = max(F(0), p['reserve_floor']-pre_official_reserves)
    reserves = pre_official_reserves+official
    external_debt = p['private_foreign_loan']+official
    asset_transactions = (reserves-p['reserves_open'])*p['e']
    liability_transactions = (external_debt-p['external_debt_open'])*p['e']
    nfa0 = (p['reserves_open']-p['external_debt_open'])*p['e']
    nfa1 = (reserves-external_debt)*p['e']
    # Household receipts include domestic public interest, a within-country flow.
    private_saving = y-taxes+income_abroad+public_interest-consumption
    public_saving = primary-public_interest
    checks = {
        'goods_market': y-consumption-investment-g-p['exports']+imports,
        'saving_investment': saving-investment-ca,
        'sector_saving': saving-private_saving-public_saving,
        'public_cash': issuance+taxes-g-public_interest-p['public_maturity'],
        'public_stock': debt-(p['public_debt_open']-p['public_maturity']+issuance),
        'external_cash': reserves-pre_official_reserves-official,
        'balance_of_payments': ca-(asset_transactions-liability_transactions),
        'net_foreign_assets': nfa1-nfa0-ca
    }
    if any(checks.values()):
        raise AssertionError('an accounting identity failed')
    return dict(id=s['id'], output=y, consumption=consumption, investment=investment,
                government_consumption=g, taxes=taxes, imports=imports,
                real_rate=r, national_disposable_income=gndi, national_saving=saving,
                private_saving=private_saving, public_saving=public_saving,
                current_account=ca, primary_surplus=primary, public_debt=debt,
                public_debt_gdp=debt/y, public_issuance=issuance,
                public_funding_gap=max(F(0), issuance-p['public_issuance_capacity']),
                official_foreign_loan_needed=official, closing_reserves=reserves,
                closing_external_debt=external_debt, asset_transactions=asset_transactions,
                liability_transactions=liability_transactions, opening_nfa=nfa0,
                closing_nfa=nfa1, accounting_residuals=checks)


def encode(value):
    if isinstance(value, F):
        return {'exact': str(value), 'decimal': float(value)}
    raise TypeError(type(value).__name__)


def analyze(data):
    p = validate(data)
    return {'historical': historical(data),
            'synthetic': [scenario(p, s) for s in data['synthetic']['scenarios']],
            'interpretation': 'Model candidates require the reported funding. The loan-needed field is a requirement, not an approval. Domestic funding gaps make those candidates infeasible under the stated cap. Historical figures do not identify synthetic coefficients.'}


def main():
    if len(sys.argv) > 2:
        raise ValueError('supply at most one local JSON input path')
    path = Path(sys.argv[1]) if len(sys.argv) == 2 else Path(__file__).with_name('v06-assessment-data.json')
    result = analyze(json.loads(path.read_text()))
    print(json.dumps(result, default=encode, indent=2, allow_nan=False))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, TypeError, ZeroDivisionError, OSError) as error:
        print('Input/model error: '+str(error), file=sys.stderr)
        sys.exit(2)
