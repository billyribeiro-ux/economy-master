"""Original exact peer normalization and conditional DCF comparison.

Quiet benchmark(data=None) returns strict JSON-compatible data. The CLI prints
JSON; it never writes input/output or requests network access. All prices,
claims and forecasts are fictional. This is not an issuer-data valuation tool.
"""
from fractions import Fraction as F
import json
from pathlib import Path
import sys

DEFAULT_INPUT = Path(__file__).with_name('v08-c07-inputs.json')
CLAIMS = ('common_equity', 'financial_debt', 'lease_claim', 'noncontrolling_claim',
          'excess_cash', 'excluded_holdings')
OPERATING = ('reported_subtotal', 'lease_expense_in_subtotal', 'settled_transitory_cost',
             'transitory_gain', 'cycle_adjustment', 'forward_capacity_adjustment',
             'forward_depreciation')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def exact(value, label):
    require(not isinstance(value, bool) and isinstance(value, (int, str)),
            f'{label}: expected exact integer or rational/decimal string')
    try:
        return F(value)
    except (ValueError, ZeroDivisionError) as exc:
        raise ValueError(f'{label}: invalid exact number') from exc


def encode(value):
    if isinstance(value, F):
        return str(value)
    if isinstance(value, dict):
        return {k: encode(v) for k, v in value.items()}
    if isinstance(value, list):
        return [encode(v) for v in value]
    return value


def median(values):
    ordered = sorted(values)
    require(bool(ordered), 'Cannot aggregate an empty comparable group')
    half = len(ordered)//2
    return ordered[half] if len(ordered) % 2 else (ordered[half-1]+ordered[half])/2


def normalize(row, data):
    require(isinstance(row, dict) and isinstance(row.get('id'), str) and row['id'], 'Missing row ID')
    require(row.get('price_date') == data['price_date'], 'Mixed pricing dates need an explicit remeasurement')
    require(row.get('forecast_period') == data['forecast_period'], 'Mismatched forecast earnings periods')
    require(type(row.get('normalization_supported')) is bool, 'State normalization evidence as a Boolean')
    require(row.get('business') in ('industrial_components', 'software_licensing'), 'Unsupported business classification')
    require(isinstance(row.get('evidence'), str) and row['evidence'], 'Every candidate needs an evidence/exclusion record')
    n = {key: exact(row.get(key), row['id']+' '+key) for key in CLAIMS+OPERATING}
    require(all(n[key] >= 0 for key in CLAIMS), 'Claim values must be nonnegative supplied market values')
    require(all(n[key] >= 0 for key in ('lease_expense_in_subtotal', 'settled_transitory_cost',
                                      'transitory_gain', 'forward_depreciation')), 'Adjustment amounts must have their stated sign')
    require(row.get('reported_basis') in ('after_lease_payments', 'before_lease_payments'), 'Unknown lease reporting basis')
    require(row['reported_basis'] != 'before_lease_payments' or n['lease_expense_in_subtotal'] == 0,
            'Lease expense cannot be added back twice')
    net_claims = (n['financial_debt']+n['lease_claim']+n['noncontrolling_claim']
                  -n['excess_cash']-n['excluded_holdings'])
    ev = n['common_equity']+net_claims
    require(ev > 0, 'Nonpositive operating EV is outside this bounded positive-value exercise')
    recurring = (n['reported_subtotal']+n['lease_expense_in_subtotal']
                 +n['settled_transitory_cost']-n['transitory_gain'])
    forward = recurring+n['cycle_adjustment']+n['forward_capacity_adjustment']
    ebit = forward-n['forward_depreciation']
    reasons = []
    if row['business'] != 'industrial_components':
        reasons.append('different operating/capital model')
    if not row['normalization_supported']:
        reasons.append('unsupported normalization')
    if forward <= 0 or ebit <= 0:
        reasons.append('outside the stated positive-profit comparator group')
    return {'id': row['id'], 'operating_EV': ev, 'net_excluded_claims': net_claims,
            'reported_subtotal': n['reported_subtotal'], 'recurring_common_basis_Y0': recurring,
            'normalized_forward_EBITDA_Y1': forward, 'normalized_forward_EBIT_Y1': ebit,
            'raw_EV_to_reported_subtotal': ev/n['reported_subtotal'] if n['reported_subtotal'] > 0 else None,
            'EV_to_normalized_forward_EBITDA': ev/forward if forward > 0 else None,
            'EV_to_normalized_forward_EBIT': ev/ebit if ebit > 0 else None,
            'included': not reasons, 'exclusion_reasons': reasons}


def benchmark(data=None):
    if data is None:
        data = json.loads(DEFAULT_INPUT.read_text(encoding='utf-8'))
    require(isinstance(data, dict) and type(data.get('spec_version')) is int and data['spec_version'] == 1,
            'Expected original spec_version 1')
    require(data.get('amount_unit') == 'kCU', 'All money inputs must use kCU')
    require(isinstance(data.get('price_date'), str) and isinstance(data.get('forecast_period'), str), 'Declare price date and forecast period')
    peers = data.get('peers')
    require(isinstance(peers, list) and 2 <= len(peers) <= 50, 'Supply two to fifty candidate records')
    target = normalize(data.get('target'), data)
    require(target['included'], 'Target must satisfy this positive-profit model contract')
    require(target['reported_subtotal'] > 0, 'This target comparison requires a positive reported subtotal')
    rows = [normalize(row, data) for row in peers]
    require(len({row['id'] for row in rows+[target]}) == len(rows)+1, 'Candidate and target IDs must be unique')
    selected = [row for row in rows if row['included']]
    require(len(selected) >= 2, 'At least two eligible comparators are required')
    multiples = [row['EV_to_normalized_forward_EBITDA'] for row in selected]
    ev_sum = sum(row['operating_EV'] for row in selected)
    earnings_sum = sum(row['normalized_forward_EBITDA_Y1'] for row in selected)
    med = median(multiples)
    mean = sum(multiples)/len(multiples)
    pooled = ev_sum/earnings_sum
    ebit_med = median([row['EV_to_normalized_forward_EBIT'] for row in selected])
    shares = exact(data['target'].get('ordinary_shares_thousands'), 'Ordinary shares in thousands')
    require(shares > 0, 'Share count must be positive')

    def bridge(ev):
        equity = ev-target['net_excluded_claims']
        require(equity >= 0, 'Negative residual equity requires an explicit distress/claims model')
        return {'operating_value': ev, 'common_equity_value': equity, 'CU_per_share': equity/shares}

    estimates = {name: bridge(multiple*target['normalized_forward_EBITDA_Y1'])
                 for name, multiple in (('median', med), ('arithmetic_mean', mean),
                                        ('pooled', pooled), ('minimum', min(multiples)),
                                        ('maximum', max(multiples)))}
    estimates['EBIT_median'] = bridge(ebit_med*target['normalized_forward_EBIT_Y1'])
    dcf_raw = data.get('target_dcf')
    require(isinstance(dcf_raw, dict), 'Supply conditional target DCF assumptions')
    d = {key: exact(dcf_raw.get(key), key) for key in ('forward_sales', 'operating_tax_rate',
         'stable_growth', 'incremental_and_existing_roic', 'operating_discount_rate')}
    sales, tax, g, R, r = (d[k] for k in ('forward_sales', 'operating_tax_rate', 'stable_growth',
                          'incremental_and_existing_roic', 'operating_discount_rate'))
    require(sales >= target['normalized_forward_EBITDA_Y1'] > 0, 'Positive sales must cover forward EBITDA')
    require(0 <= tax < 1 and R > 0 and r > 0 and 0 <= g < r and g < R,
            'Stable comparison requires usable tax, positive returns/cash and 0 <= g < min(r, ROIC)')
    nopat = target['normalized_forward_EBIT_Y1']*(1-tax)
    reinvestment = nopat*g/R
    fcff = nopat-reinvestment
    ev = fcff/(r-g)
    justified = ev/target['normalized_forward_EBITDA_Y1']
    dcf = {'NOPAT1': nopat, 'net_reinvestment1': reinvestment, 'FCFF1': fcff,
           'opening_productive_capital': nopat/R, 'closing_year1_capital': nopat/R+reinvestment,
           'justified_forward_EV_EBITDA': justified,
           'justified_forward_EV_EBIT': ev/target['normalized_forward_EBIT_Y1'],
           'justified_forward_EV_sales': ev/sales,
           'peer_median_implied_r': g+fcff/estimates['median']['operating_value'],
           'market_EV_implied_r': g+fcff/target['operating_EV'], **bridge(ev)}
    naive = bridge(med*target['reported_subtotal'])
    return encode({'case': data.get('case'), 'amount_unit': 'kCU', 'target': target, 'candidates': rows,
        'selection': [row['id'] for row in selected],
        'summary': {'median': med, 'arithmetic_mean': mean, 'pooled_EV_over_EBITDA': pooled,
                    'range': [min(multiples), max(multiples)], 'EBIT_median': ebit_med,
                    'leave_one_out_medians': [{'removed': row['id'], 'median': median([other['EV_to_normalized_forward_EBITDA'] for other in selected if other['id'] != row['id']])} for row in selected]},
        'relative_estimates': estimates, 'conditional_DCF': dcf,
        'incorrect_reported_denominator_application': {'estimate': naive,
            'operating_value_overstatement': naive['operating_value']-estimates['median']['operating_value']},
        'interpretation': 'Conditional fictional pricing evidence. Candidate selection and normalization are explicit assumptions; no confidence interval, arbitrage profit or investment recommendation follows.'})


if __name__ == '__main__':
    if len(sys.argv) > 2:
        raise SystemExit('Usage: python3 v08-c07-analysis.py [input.json]')
    path = Path(sys.argv[1]) if len(sys.argv) == 2 else DEFAULT_INPUT
    print(json.dumps(benchmark(json.loads(path.read_text(encoding='utf-8'))), indent=2, allow_nan=False))
