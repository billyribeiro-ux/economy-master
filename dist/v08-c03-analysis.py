"""Mariner Calibration Services's original exact capital-path DCF, with coherent terminal sensitivity.

Standard library only. Quiet benchmark(data=None) returns strict JSON-compatible
data. CLI accepts an optional input JSON path and prints, without writing files.
This is a bounded operating model, not a market-data service or general tax,
financing, distress or valuation engine.
"""
from fractions import Fraction as F
import json
from pathlib import Path
import sys

DEFAULT_INPUT = Path(__file__).with_name('v08-c03-inputs.json')


def exact(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ValueError(f'{label}: use an exact integer or rational/decimal string')
    try:
        return F(value)
    except (ValueError, ZeroDivisionError) as exc:
        raise ValueError(f'{label}: invalid exact number') from exc


def require(condition, message):
    if not condition:
        raise ValueError(message)


def encode(value):
    if isinstance(value, F):
        return str(value)
    if isinstance(value, dict):
        return {key: encode(item) for key, item in value.items()}
    if isinstance(value, list):
        return [encode(item) for item in value]
    return value


def parse(data):
    require(isinstance(data, dict) and data.get('spec_version') == 1,
            'Expected original model spec_version 1')
    require(data.get('amount_unit') == 'kCU', 'All monetary model inputs must use kCU')
    raw = data.get('parameters')
    require(isinstance(raw, dict), 'parameters must be an object')
    names = ('initial_operating_capital', 'ppe_share_of_capital',
             'depreciation_rate_on_opening_ppe', 'sales_per_opening_capital',
             'operating_tax_rate', 'operating_discount_rate', 'stable_roic',
             'stable_growth', 'excess_cash_value', 'nonoperating_asset_value',
             'debt_market_value', 'ordinary_shares_thousands')
    require(all(name in raw for name in names), 'Missing a required model parameter')
    p = {name: exact(raw[name], name) for name in names}
    require(p['initial_operating_capital'] > 0, 'Opening operating capital must be positive')
    require(0 <= p['ppe_share_of_capital'] <= 1, 'PPE capital share must lie in [0,1]')
    require(0 <= p['depreciation_rate_on_opening_ppe'] <= 1,
            'Book depreciation rate must lie in [0,1]')
    require(p['sales_per_opening_capital'] > 0, 'Sales/capital must be positive')
    require(0 <= p['operating_tax_rate'] < 1, 'Operating tax rate must lie in [0,1)')
    require(p['stable_roic'] > 0, 'Stable ROIC must be positive in this model')
    require(p['ordinary_shares_thousands'] > 0, 'Shares must be positive')
    require(all(p[name] >= 0 for name in ('excess_cash_value', 'nonoperating_asset_value',
                                         'debt_market_value')), 'Bridge claim values must be nonnegative')
    stages = data.get('stages')
    require(isinstance(stages, list) and 1 <= len(stages) <= 50,
            'Supply one to fifty explicit annual stages')
    result = []
    for year, row in enumerate(stages, 1):
        require(isinstance(row, dict) and type(row.get('year')) is int and row['year'] == year,
                'Stage years must be consecutive exact integers beginning at one')
        rho = exact(row.get('roic'), f'year {year} ROIC')
        require(rho > 0, 'Every modeled NOPAT/ROIC must be positive')
        if year == len(stages):
            require(row.get('reinvestment_rate') == 'terminal',
                    'Final explicit year must already use the terminal reinvestment policy')
            require(rho == p['stable_roic'],
                    'Final explicit ROIC must match stable ROIC; extend the transition first')
            b = None
        else:
            b = exact(row.get('reinvestment_rate'), f'year {year} reinvestment rate')
            require(0 <= b <= 1, 'Explicit reinvestment rate must lie in [0,1]')
        result.append((year, rho, b))
    return p, result


def year_row(year, capital, rho, b, p):
    opening_ppe = p['ppe_share_of_capital']*capital
    opening_nwc = capital-opening_ppe
    sales = p['sales_per_opening_capital']*capital
    nopat = rho*capital
    ebit = nopat/(1-p['operating_tax_rate'])
    tax = ebit-nopat
    depreciation = p['depreciation_rate_on_opening_ppe']*opening_ppe
    cash_operating_cost = sales-ebit-depreciation
    require(cash_operating_cost >= 0,
            'ROIC/tax/turnover/depreciation assumptions imply negative operating cash cost')
    investment = b*nopat
    delta_nwc = (1-p['ppe_share_of_capital'])*investment
    capex = depreciation+p['ppe_share_of_capital']*investment
    closing_ppe = opening_ppe+capex-depreciation
    closing_nwc = opening_nwc+delta_nwc
    close_capital = closing_ppe+closing_nwc
    fcff = nopat-investment
    direct_cash = sales-cash_operating_cost-tax-delta_nwc-capex
    require(close_capital == capital+investment and direct_cash == fcff,
            'Internal capital/cash closure failed')
    return {'year': year, 'opening_capital': capital, 'opening_ppe': opening_ppe,
            'opening_operating_nwc': opening_nwc, 'roic': rho,
            'reinvestment_rate': b, 'sales': sales, 'EBIT': ebit,
            'operating_tax_paid': tax, 'NOPAT': nopat, 'depreciation': depreciation,
            'cash_operating_cost': cash_operating_cost, 'capex': capex,
            'change_operating_nwc': delta_nwc, 'net_reinvestment': investment,
            'closing_ppe': closing_ppe, 'closing_operating_nwc': closing_nwc,
            'closing_capital': close_capital, 'FCFF': fcff,
            'FCFF_direct_cash_bridge': direct_cash}


def forecast(p, stages, discount_rate=None, stable_growth=None):
    r = p['operating_discount_rate'] if discount_rate is None else discount_rate
    g = p['stable_growth'] if stable_growth is None else stable_growth
    rho_stable = p['stable_roic']
    require(r > 0, 'Operating discount rate must be positive')
    require(0 <= g < r, 'Stable growth must be nonnegative and strictly below discount rate')
    require(g <= rho_stable, 'Growth requires reinvestment above NOPAT; outside this bounded model')
    b_stable = g/rho_stable
    capital = p['initial_operating_capital']
    rows = []
    for year, rho, explicit_b in stages:
        b = b_stable if explicit_b is None else explicit_b
        row = year_row(year, capital, rho, b, p)
        row['discount_factor'] = (1+r)**(-year)
        row['present_value_FCFF'] = row['FCFF']*row['discount_factor']
        row['economic_profit'] = row['NOPAT']-r*capital
        capital = row['closing_capital']
        rows.append(row)
    h = len(rows)
    next_row = year_row(h+1, capital, rho_stable, b_stable, p)
    for row, following in zip(rows, rows[1:]+[next_row]):
        old_change = (following['roic']-row['roic'])*row['opening_capital']
        new_earnings = following['roic']*row['net_reinvestment']
        require(following['NOPAT']-row['NOPAT'] == old_change+new_earnings,
                'Old/new capital earnings decomposition failed')
        row['change_next_NOPAT_on_old_capital'] = old_change
        row['next_NOPAT_from_new_capital'] = new_earnings
        row['next_NOPAT_growth'] = (following['NOPAT']-row['NOPAT'])/row['NOPAT']
    require(next_row['NOPAT'] == rows[-1]['NOPAT']*(1+g), 'Horizon growth timing mismatch')
    terminal = next_row['FCFF']/(r-g)
    pv_terminal = terminal/(1+r)**h
    pv_explicit = sum(row['present_value_FCFF'] for row in rows)
    operating_value = pv_explicit+pv_terminal
    pv_economic_profit = sum(row['economic_profit']*row['discount_factor'] for row in rows)
    ep_value = (p['initial_operating_capital']+pv_economic_profit
                +(terminal-capital)/(1+r)**h)
    require(ep_value == operating_value, 'DCF versus economic-profit bridge failed')
    equity = (operating_value+p['excess_cash_value']+p['nonoperating_asset_value']
              -p['debt_market_value'])
    require(equity >= 0, 'Negative residual equity needs a distress/claim model outside this lab')
    return {'discount_rate': r, 'stable_growth': g, 'stable_roic': rho_stable,
            'stable_reinvestment_rate': b_stable, 'explicit_years': rows,
            'first_continuation_year': next_row, 'terminal_value_date': h,
            'terminal_value': terminal, 'terminal_present_value': pv_terminal,
            'explicit_present_value': pv_explicit, 'operating_value': operating_value,
            'terminal_share_of_operating_value': pv_terminal/operating_value if operating_value else None,
            'economic_profit_value': ep_value, 'equity_value': equity,
            'value_per_ordinary_share_CU': equity/p['ordinary_shares_thousands']}


def benchmark(data=None):
    if data is None:
        data = json.loads(DEFAULT_INPUT.read_text(encoding='utf-8'))
    p, stages = parse(data)
    base = forecast(p, stages)
    grid = data.get('sensitivity')
    require(isinstance(grid, dict), 'Supply a sensitivity-grid object')
    rates = grid.get('discount_rates')
    growths = grid.get('stable_growth_rates')
    require(isinstance(rates, list) and isinstance(growths, list)
            and 1 <= len(rates) <= 12 and 1 <= len(growths) <= 12,
            'Supply nonempty sensitivity axes with at most twelve values each')
    sensitivity = []
    for r_raw in rates:
        for g_raw in growths:
            candidate = forecast(p, stages, exact(r_raw, 'sensitivity discount rate'),
                                 exact(g_raw, 'sensitivity growth'))
            sensitivity.append({key: candidate[key] for key in
                ('discount_rate', 'stable_growth', 'stable_reinvestment_rate',
                 'operating_value', 'equity_value', 'terminal_value',
                 'terminal_share_of_operating_value')})
    return encode({'case': data.get('case'), 'amount_unit': 'kCU',
                   'note': 'Exact original conditional model; sensitivity recomputes final explicit reinvestment and continuation capital.',
                   'base': base, 'sensitivity': sensitivity})


if __name__ == '__main__':
    if len(sys.argv) > 2:
        raise SystemExit('Usage: python3 v08-c03-analysis.py [input.json]')
    source = Path(sys.argv[1]) if len(sys.argv) == 2 else DEFAULT_INPUT
    print(json.dumps(benchmark(json.loads(source.read_text(encoding='utf-8'))), indent=2, allow_nan=False))
