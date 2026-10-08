#!/usr/bin/env python3
"""Original double-entry lab: exact integer USD cents, no network or packages.

Posting proves arithmetic balance, not recognition, occurrence or feasibility.
All dates and source descriptions in the supplied case are fictional.
"""
from copy import deepcopy
from datetime import date
import json
from pathlib import Path
import sys

TYPES = {'asset', 'contra_asset', 'liability', 'capital', 'retained',
         'revenue', 'expense', 'distribution'}
TEMPORARY = {'revenue', 'expense', 'distribution'}
MAX_AMOUNT = 10**12


def require(condition, message):
    if not condition:
        raise ValueError(message)


def amount(value, signed=False):
    require(type(value) is int and abs(value) <= MAX_AMOUNT,
            'amount must be a bounded integer number of cents, not bool/float')
    require(signed or value > 0, 'entry amounts must be positive')
    return value


def day(value):
    require(type(value) is str, 'date must be an ISO string')
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError('invalid calendar date') from exc
    require(parsed.isoformat() == value, 'date must be YYYY-MM-DD')
    return parsed


def validate(raw):
    require(type(raw) is dict, 'input must be an object')
    require(raw.get('schema') == 'v07-c01-ledger-v1' and raw.get('synthetic') is True,
            'recognized explicitly synthetic case required')
    meta = raw['metadata']
    require(meta['currency'] == 'USD' and meta['amount_unit'] == 'cent', 'USD cents required')
    start, end = day(meta['period_start']), day(meta['period_end'])
    require(start <= end, 'ordered reporting dates required')
    chart = raw['accounts']
    require(type(chart) is dict and 1 <= len(chart) <= 100, 'bounded account chart required')
    for key, row in chart.items():
        require(type(key) is str and key and type(row) is dict, 'account object required')
        require(row['type'] in TYPES and type(row['label']) is str and row['label'], 'valid account type/label required')
    require(sum(row['type'] == 'retained' for row in chart.values()) == 1, 'one retained-earnings account required')
    opening = raw['opening_debit_balances']
    require(type(opening) is dict and set(opening) == set(chart), 'opening balance for every account required')
    for key, val in opening.items():
        amount(val, signed=True)
        require(chart[key]['type'] not in TEMPORARY or val == 0, 'temporary accounts start at zero')
    require(sum(opening.values()) == 0, 'opening trial balance must balance')
    ids = set()
    for group in ('transactions', 'adjustments'):
        entries = raw[group]
        require(type(entries) is list and len(entries) <= 200, 'bounded journal list required')
        previous = start
        for entry in entries:
            require(type(entry) is dict, 'journal entry object required')
            key = entry['id']
            require(type(key) is str and key and key not in ids, 'unique entry id required')
            ids.add(key)
            effective, recorded = day(entry['effective_date']), day(entry['recorded_date'])
            require(start <= effective <= end and effective >= previous, 'effective dates must be ordered within the reporting period')
            require(recorded >= effective, 'recording cannot precede the supplied event/adjustment date')
            require(group != 'adjustments' or effective == end, 'this lab posts adjustments at period end')
            previous = effective
            require(type(entry['source']) is str and entry['source'], 'source reference required')
            require(type(entry['explanation']) is str and entry['explanation'], 'entry explanation required')
            lines = entry['lines']
            require(type(lines) is list and 2 <= len(lines) <= len(chart), 'at least two distinct account lines required')
            used, total = set(), 0
            for line in lines:
                require(type(line) is dict and set(line) == {'account', 'side', 'cents'}, 'exact posting fields required')
                account, side = line['account'], line['side']
                require(account in chart and account not in used, 'known distinct account required')
                require(side in ('Dr', 'Cr'), 'side must be Dr or Cr')
                total += amount(line['cents']) * (1 if side == 'Dr' else -1)
                used.add(account)
            require(total == 0, 'unbalanced entry: ' + key)
    follow = raw['wage_followup']
    require(follow['cash_account'] in chart and chart[follow['cash_account']]['type'] == 'asset', 'followup cash account')
    require(follow['payable_account'] in chart and chart[follow['payable_account']]['type'] == 'liability', 'followup payable account')
    require(follow['expense_account'] in chart and chart[follow['expense_account']]['type'] == 'expense', 'followup expense account')
    amount(follow['payment_cents'])
    require(end < day(follow['reversal_date']) <= day(follow['payment_date']), 'followup after reporting period required')
    return chart


def post(balances, entries):
    ledger = deepcopy(balances)
    history = []
    for entry in entries:
        delta = 0
        for line in entry['lines']:
            signed = line['cents'] * (1 if line['side'] == 'Dr' else -1)
            ledger[line['account']] += signed
            delta += signed
        require(delta == 0 and sum(ledger.values()) == 0, 'posting balance failed')
        history.append({'entry_id': entry['id'], 'debit_balance_sum': sum(ledger.values()),
                        'balances': dict(ledger)})
    return ledger, history


def snapshot(chart, balances):
    total = lambda kind: sum(v for a, v in balances.items() if chart[a]['type'] in kind)
    assets = total({'asset', 'contra_asset'})
    liabilities = -total({'liability'})
    capital = -total({'capital'})
    retained = -total({'retained'})
    revenue = -total({'revenue'})
    expenses = total({'expense'})
    distributions = total({'distribution'})
    equity = capital + retained + revenue - expenses - distributions
    debit = sum(max(0, v) for v in balances.values())
    credit = sum(max(0, -v) for v in balances.values())
    require(assets == liabilities + equity and debit == credit, 'mapped equation failed')
    trial = {a: {'debit_cents': max(0, v), 'credit_cents': max(0, -v)} for a, v in balances.items()}
    abnormal = [a for a, v in balances.items()
                if (chart[a]['type'] in {'asset', 'expense', 'distribution'} and v < 0)
                or (chart[a]['type'] in {'contra_asset', 'liability', 'capital', 'revenue'} and v > 0)]
    return {'debit_balances_cents': dict(balances), 'trial_balance': trial,
            'trial_debit_cents': debit, 'trial_credit_cents': credit,
            'assets_cents': assets, 'liabilities_cents': liabilities,
            'contributed_capital_cents': capital, 'retained_account_cents': retained,
            'open_revenue_cents': revenue, 'open_expenses_cents': expenses,
            'open_profit_cents': revenue-expenses, 'open_distributions_cents': distributions,
            'equity_cents': equity, 'equation_residual_cents': assets-liabilities-equity,
            'opposite_normal_balance_flags': abnormal}


def make_entry(key, effective, recorded, explanation, amounts):
    return {'id': key, 'effective_date': effective, 'recorded_date': recorded,
            'source': 'Derived closing/followup workpaper', 'explanation': explanation,
            'lines': [{'account': account, 'side': 'Dr' if val > 0 else 'Cr', 'cents': abs(val)}
                      for account, val in amounts.items() if val]}


def closing_entries(chart, balances, end, recorded):
    retained = next(a for a, row in chart.items() if row['type'] == 'retained')
    result = []
    for kind in ('revenue', 'expense', 'distribution'):
        amounts = {a: -v for a, v in balances.items() if chart[a]['type'] == kind and v}
        if amounts:
            amounts[retained] = -sum(amounts.values())
            result.append(make_entry('close_' + kind, end, recorded,
                                    'Transfer ' + kind + ' balances to retained earnings', amounts))
    return result


def wages_after_close(chart, closed, follow, prepared_on):
    cash, payable, expense = [follow[x] for x in ('cash_account', 'payable_account', 'expense_account')]
    accrued = -closed[payable]
    payment = follow['payment_cents']
    require(0 <= accrued <= payment, 'followup requires payment covering the accrued wages')
    dated = follow['payment_date']
    direct = [make_entry('pay_without_reversal', dated, max(dated, prepared_on),
                        'Settle prior accrual and pay current wages',
                        {payable: accrued, expense: payment-accrued, cash: -payment})]
    reverse = []
    if accrued:
        reverse.append(make_entry('reverse_wage_accrual', follow['reversal_date'], max(follow['reversal_date'], prepared_on),
                                  'Optional reversal, not cancellation of the obligation',
                                  {payable: accrued, expense: -accrued}))
    reverse.append(make_entry('pay_after_reversal', dated, max(dated, prepared_on), 'Record full payroll cash payment',
                              {expense: payment, cash: -payment}))
    direct_balances, _ = post(closed, direct)
    reverse_balances, _ = post(closed, reverse)
    require(direct_balances == reverse_balances, 'reversal equivalence failed')
    return {'scope': 'Selected wage entries only; not a complete next-month statement',
            'prior_accrual_cents': accrued, 'next_period_wage_expense_cents': payment-accrued,
            'cash_payment_cents': payment, 'direct_entries': direct, 'reversal_entries': reverse,
            'identical_ending_balances': True, 'ending_debit_balances_cents': direct_balances}


def run(raw):
    chart = validate(raw)
    unadjusted, operating_history = post(raw['opening_debit_balances'], raw['transactions'])
    adjusted, adjustment_history = post(unadjusted, raw['adjustments'])
    recorded = max([raw['metadata']['period_end']] + [e['recorded_date'] for e in raw['transactions']+raw['adjustments']])
    closing = closing_entries(chart, adjusted, raw['metadata']['period_end'], recorded)
    closed, closing_history = post(adjusted, closing)
    require(all(v == 0 for a, v in closed.items() if chart[a]['type'] in TEMPORARY), 'temporary balances not closed')
    follow = wages_after_close(chart, closed, raw['wage_followup'], recorded)
    return {'schema': raw['schema'], 'synthetic': True, 'currency': 'USD', 'amount_unit': 'cent',
            'entity': raw['metadata']['entity'], 'period_end': raw['metadata']['period_end'],
            'unadjusted': snapshot(chart, unadjusted), 'adjusted': snapshot(chart, adjusted),
            'closing_entries': closing, 'post_closing': snapshot(chart, closed),
            'posting_history': operating_history+adjustment_history+closing_history,
            'wage_followup': follow,
            'limitation': 'Arithmetic and supplied account mappings only: recognition, evidence completeness, legal authority and cash availability require separate review.'}


def unique_pairs(items):
    result = {}
    for key, val in items:
        require(key not in result, 'duplicate JSON key')
        result[key] = val
    return result


def bad_constant(value):
    raise ValueError('nonfinite JSON constant: ' + value)


def main():
    try:
        require(len(sys.argv) <= 2, 'usage: python3 v07-c01-ledger.py [input.json]')
        path = Path(sys.argv[1]) if len(sys.argv) == 2 else Path(__file__).with_name('v07-c01-transactions.json')
        require(path.stat().st_size <= 300_000, 'input exceeds 300000 bytes')
        raw = json.loads(path.read_text(), object_pairs_hook=unique_pairs, parse_constant=bad_constant)
        result = run(raw)
    except (ValueError, KeyError, TypeError, OSError) as exc:
        print(json.dumps({'status': 'error', 'message': str(exc)}, allow_nan=False))
        return 2
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
