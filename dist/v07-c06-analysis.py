#!/usr/bin/env python3
"""Original exact equity/consolidation teaching benchmark; standard library only."""
from fractions import Fraction as F
import argparse
import json
from pathlib import Path


def number(value):
    if not isinstance(value, str):
        raise ValueError('numeric inputs must be exact rational strings')
    try:
        result = F(value)
    except (ValueError, ZeroDivisionError) as exc:
        raise ValueError('invalid rational input') from exc
    if result < 0:
        raise ValueError('inputs must be nonnegative')
    return result


def numbers(obj):
    return {k: number(v) for k, v in obj.items()}


class Ledger:
    def __init__(self, balances):
        self.balances = dict(balances)
        self.journal = []
        if sum(self.balances.values()) != 0:
            raise ValueError('opening ledger is not balanced')

    def post(self, date, label, changes):
        if sum(changes.values()) != 0:
            raise ValueError('unbalanced journal')
        for account, change in changes.items():
            self.balances[account] = self.balances.get(account, F(0)) + change
        if self.balances['cash'] < 0:
            raise ValueError('event requires unavailable cash; new financing is outside this case')
        self.journal.append({'date': date, 'event': label, 'debit_minus_credit': changes,
                             'cash_after': self.balances['cash'], 'balance_residual': sum(self.balances.values())})


def shares(case):
    n, par = number(case['opening_shares']), number(case['par'])
    held = number(case['observer_shares'])
    if n <= 0 or held > n:
        raise ValueError('invalid opening or observer share count')
    l = Ledger({'cash': number(case['opening_cash']), 'other_assets': number(case['other_assets']),
                'liabilities': -number(case['liabilities']), 'capital': -n * par,
                'apic_issue': -number(case['opening_apic']), 'apic_treasury': F(0),
                'retained': -number(case['opening_retained']), 'treasury': F(0)})
    issued, treasury, profit, dividends, owner_cash = n, F(0), F(0), F(0), F(0)
    opening_equity = n * par + number(case['opening_apic']) + number(case['opening_retained'])
    snapshots = []
    last_date = ''
    for event in case['events']:
        date, kind = event['date'], event['kind']
        if date < last_date:
            raise ValueError('share events must be date ordered')
        last_date = date
        if kind in ('issue', 'repurchase', 'reissue'):
            q, p = number(event['shares']), number(event['price'])
            if q <= 0:
                raise ValueError('share event quantity must be positive')
            cash = q * p
            if kind == 'issue':
                if p < par:
                    raise ValueError('below-par issuance outside stated convention')
                l.post(date, kind, {'cash': cash, 'capital': -q * par, 'apic_issue': -q * (p-par)})
                issued += q
                owner_cash += cash
            elif kind == 'repurchase':
                # Observer never trades; preserve positive outside shares and observer feasibility.
                if q >= issued-treasury or q > issued-treasury-held:
                    raise ValueError('repurchase conflicts with outstanding/observer holdings')
                l.post(date, kind, {'treasury': cash, 'cash': -cash})
                treasury += q
                owner_cash -= cash
            else:
                if q > treasury or treasury == 0:
                    raise ValueError('cannot reissue shares not in treasury')
                # Average cost; the main case has one homogeneous repurchase lot.
                cost = l.balances['treasury'] * q / treasury
                difference = cash - cost
                adjustment = {'cash': cash, 'treasury': -cost}
                if difference >= 0:
                    adjustment['apic_treasury'] = -difference
                else:
                    reserve_used = min(-difference, -l.balances['apic_treasury'])
                    adjustment['apic_treasury'] = reserve_used
                    adjustment['retained'] = -difference-reserve_used
                l.post(date, kind, adjustment)
                treasury -= q
                owner_cash += cash
        elif kind == 'cash_service':
            amount = number(event['amount'])
            l.post(date, kind, {'cash': amount, 'revenue': -amount})
            profit += amount
        elif kind == 'dividend':
            amount = number(event['amount'])
            l.post(date, kind, {'dividends': amount, 'cash': -amount})
            dividends += amount
            owner_cash -= amount
        else:
            raise ValueError('unknown share event')
        snapshots.append({'date': date, 'issued': issued, 'treasury_shares': treasury,
                          'outstanding': issued-treasury, 'observer_fraction': held/(issued-treasury)})
    l.post('X1-12-31', 'close profit', {'revenue': profit, 'retained': -profit})
    l.post('X1-12-31', 'close dividends', {'dividends': -dividends, 'retained': dividends})
    b = l.balances
    equity = -b['capital']-b['apic_issue']-b['apic_treasury']-b['retained']-b['treasury']
    assets = b['cash']+b['other_assets']
    return {'ledger': b, 'journal': l.journal, 'share_snapshots': snapshots, 'profit': profit,
            'net_owner_cash': owner_cash, 'assets': assets, 'liabilities': -b['liabilities'],
            'equity': equity, 'apic_total': -b['apic_issue']-b['apic_treasury'],
            'issued': issued, 'outstanding': issued-treasury, 'treasury_shares': treasury,
            'residuals': {'balance_sheet': assets+b['liabilities']-equity,
                          'equity_rollforward': equity-opening_equity-profit-owner_cash}}


def group(case):
    if case['control_stipulated'] is not True or case['business_stipulated'] is not True:
        raise ValueError('this model requires separately stipulated control and a business acquisition')
    alpha, price = number(case['ownership']), number(case['consideration'])
    if not 0 < alpha <= 1:
        raise ValueError('ownership must be in (0,1]; percentage is not a control test')
    p, s, f = numbers(case['parent_opening']), numbers(case['sub_opening']), numbers(case['post'])
    net = s['share_capital']+s['retained']
    goodwill, nci_open = price-alpha*net, (1-alpha)*net
    if goodwill < 0:
        raise ValueError('bargain-purchase reassessment is outside this positive-goodwill model')
    fraction = f['batch_fraction_sold_outside']
    if fraction > 1 or f['intercompany_cash_settlement'] > f['batch_transfer_price']:
        raise ValueError('invalid sold fraction or settlement beyond invoice')
    if f['batch_transfer_price'] < f['batch_external_cost']:
        raise ValueError('loss-making transfers and impairment outside this markup example')
    pl = Ledger({k: (-v if k in ('external_liabilities','share_capital','retained') else v) for k,v in p.items()})
    sl = Ledger({k: (-v if k in ('external_liabilities','share_capital','retained') else v) for k,v in s.items()})
    pl.post('X1-01-01', 'purchase existing subsidiary shares', {'investment': price, 'cash': -price})
    acquisition_cash = pl.balances['cash']+sl.balances['cash']
    acquisition_assets = sum(v for k,v in p.items() if k in ('cash','land'))-price + sum(s[k] for k in ('cash','external_receivables','inventory','land'))+goodwill
    acquisition = {'cash': acquisition_cash, 'assets': acquisition_assets,
                   'liabilities': p['external_liabilities']+s['external_liabilities'],
                   'parent_equity': p['share_capital']+p['retained'], 'nci': nci_open,
                   'goodwill': goodwill, 'net_acquisition_cash_outflow': price-s['cash'],
                   'elimination_debit_minus_credit': {'sub_capital': s['share_capital'], 'sub_preacquisition_retained': s['retained'], 'goodwill': goodwill, 'investment': -price, 'nci': -nci_open}}
    pl.post('X1-06-30', 'external services', {'cash': f['parent_service_cash'], 'revenue': -f['parent_service_cash']})
    pl.post('X1-06-30', 'operating costs', {'expense': f['parent_operating_cash'], 'cash': -f['parent_operating_cash']})
    pl.post('X1-07-01', 'external batch purchase', {'inventory': f['batch_external_cost'], 'cash': -f['batch_external_cost']})
    pl.post('X1-07-01', 'downstream credit sale', {'intra_receivable': f['batch_transfer_price'], 'revenue': -f['batch_transfer_price']})
    pl.post('X1-07-01', 'batch cost', {'cogs': f['batch_external_cost'], 'inventory': -f['batch_external_cost']})
    sl.post('X1-07-01', 'purchase from parent', {'inventory': f['batch_transfer_price'], 'intra_payable': -f['batch_transfer_price']})
    sales = fraction*f['outside_revenue_if_entire_batch_sold']
    sl.post('X1-09-30', 'outside batch sale', {'cash': sales, 'revenue': -sales})
    sl.post('X1-09-30', 'sold batch cost', {'cogs': fraction*f['batch_transfer_price'], 'inventory': -fraction*f['batch_transfer_price']})
    sl.post('X1-09-30', 'operating costs', {'expense': f['sub_operating_cash'], 'cash': -f['sub_operating_cash']})
    settle = f['intercompany_cash_settlement']
    sl.post('X1-10-01', 'pay parent', {'intra_payable': settle, 'cash': -settle})
    pl.post('X1-10-01', 'receive settlement', {'cash': settle, 'intra_receivable': -settle})
    div, pdiv = f['sub_dividend'], f['parent_dividend']
    sl.post('X1-11-01', 'pay all subsidiary owners', {'dividends': div, 'cash': -div})
    pl.post('X1-11-01', 'dividend from subsidiary', {'cash': alpha*div, 'dividend_income': -alpha*div})
    pl.post('X1-12-01', 'pay parent owners', {'dividends': pdiv, 'cash': -pdiv})
    pprofit = f['parent_service_cash']+f['batch_transfer_price']+alpha*div-f['parent_operating_cash']-f['batch_external_cost']
    sprofit = sales-fraction*f['batch_transfer_price']-f['sub_operating_cash']
    for ledger, profit, dividend in ((pl,pprofit,pdiv),(sl,sprofit,div)):
        changes = {k: -ledger.balances.get(k,F(0)) for k in ('revenue','dividend_income','cogs','expense')}
        changes['retained'] = -profit
        ledger.post('X1-12-31', 'close profit', changes)
        ledger.post('X1-12-31', 'close dividend', {'dividends': -dividend, 'retained': dividend})
    unearned = (f['batch_transfer_price']-f['batch_external_cost'])*(1-fraction)
    intra = f['batch_transfer_price']-settle
    revenue = f['parent_service_cash']+sales
    cogs = fraction*f['batch_external_cost']
    gprofit = revenue-cogs-f['parent_operating_cash']-f['sub_operating_cash']
    nci_profit = (1-alpha)*sprofit  # Downstream elimination belongs wholly to parent's owners.
    parent_profit = gprofit-nci_profit
    parent_equity = p['share_capital']+p['retained']+parent_profit-pdiv
    nci = nci_open+nci_profit-(1-alpha)*div
    assets = {'cash': pl.balances['cash']+sl.balances['cash'], 'external_receivables': s['external_receivables'],
              'inventory': s['inventory']+(1-fraction)*f['batch_external_cost'], 'land': p['land']+s['land'], 'goodwill': goodwill}
    liabilities = p['external_liabilities']+s['external_liabilities']
    cfo = f['parent_service_cash']+sales-f['parent_operating_cash']-f['sub_operating_cash']-f['batch_external_cost']
    financing = -pdiv-(1-alpha)*div
    company = {}
    for name, ledger, profit in (('parent',pl,pprofit),('subsidiary',sl,sprofit)):
        b = ledger.balances
        a = sum(v for k,v in b.items() if k in ('cash','land','inventory','external_receivables','intra_receivable','investment'))
        debt = -b['external_liabilities']-b.get('intra_payable',0)
        eq = -b['share_capital']-b['retained']
        company[name] = {'ledger': b, 'journal': ledger.journal, 'profit': profit, 'assets': a, 'liabilities': debt, 'equity': eq, 'balance_residual': a-debt-eq}
    g = {'assets_by_account': assets, 'assets': sum(assets.values()), 'liabilities': liabilities,
         'parent_equity': parent_equity, 'nci': nci, 'total_equity': parent_equity+nci,
         'revenue': revenue, 'cogs': cogs, 'operating_expense': f['parent_operating_cash']+f['sub_operating_cash'],
         'profit': gprofit, 'parent_profit': parent_profit, 'nci_profit': nci_profit,
         'cfo_post_acquisition': cfo, 'financing_post_acquisition': financing,
         'eliminations': {'investment': price, 'intra_balance': intra, 'intra_sales': f['batch_transfer_price'], 'parent_dividend_income': alpha*div, 'unrealized_inventory_margin': unearned},
         'residuals': {'balance_sheet': sum(assets.values())-liabilities-parent_equity-nci,
                       'profit_bridge': pprofit+sprofit-alpha*div-unearned-gprofit,
                       'cash_bridge': acquisition_cash+cfo+financing-assets['cash'],
                       'asset_elimination': company['parent']['assets']+company['subsidiary']['assets']-price-intra-unearned+goodwill-sum(assets.values()),
                       'nci_net_assets': nci-(1-alpha)*company['subsidiary']['equity'],
                       'acquisition': acquisition_assets-acquisition['liabilities']-acquisition['parent_equity']-nci_open}}
    return {'acquisition': acquisition, **company, 'consolidated': g}


def encode(value):
    if isinstance(value, F):
        return str(value)
    if isinstance(value, dict):
        return {k: encode(v) for k,v in value.items()}
    if isinstance(value, list):
        return [encode(v) for v in value]
    return value


def analyze(data):
    if data['schema'] != 'v07-c06-original-equity-group-v1':
        raise ValueError('unsupported schema')
    return encode({'units': data['units'], 'shares': shares(data['shares']), 'group': group(data['group'])})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', nargs='?', type=Path, default=Path(__file__).with_name('v07-c06-inputs.json'))
    args = parser.parse_args()
    try:
        report = analyze(json.loads(args.input.read_text()))
    except (ValueError, KeyError, TypeError, OSError) as exc:
        parser.exit(2, f'Invalid teaching case: {exc}\n')
    print(json.dumps(report, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
