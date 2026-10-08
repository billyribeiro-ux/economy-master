"""Original fixed monetary ledger, exact arithmetic and no external inputs.

Currency units at a common instant. No interest, taxes, fees or valuation
changes except in the explicitly named loss branch. Branches are alternatives.
"""
from copy import deepcopy
from fractions import Fraction as F
import json

BANK_ASSETS = ('R', 'S', 'L', 'IB_asset')
BANK_FINANCING = ('D', 'IB_debt', 'CB_debt', 'E')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate(book):
    require(set(book) == {'A', 'B', 'CB'}, 'exactly two banks and one central bank')
    for name in ('A', 'B'):
        bank = book[name]
        require(set(bank) == set(BANK_ASSETS + BANK_FINANCING), 'bank account contract')
        require(all(value >= 0 for value in bank.values()), 'negative fixed-case bank balance')
        require(sum(bank[k] for k in BANK_ASSETS) == sum(bank[k] for k in BANK_FINANCING),
                'unbalanced bank ' + name)
    cb = book['CB']
    require(set(cb) == {'S', 'advance_A', 'R_A', 'R_B', 'C', 'E'}, 'central-bank account contract')
    require(all(value >= 0 for value in cb.values()), 'negative fixed-case central-bank balance')
    require(cb['S'] + cb['advance_A'] == cb['R_A'] + cb['R_B'] + cb['C'] + cb['E'],
            'unbalanced central bank')
    require(cb['R_A'] == book['A']['R'] and cb['R_B'] == book['B']['R'], 'reserve counterpart mismatch')
    require(cb['advance_A'] == book['A']['CB_debt'] and book['B']['CB_debt'] == 0,
            'central advance counterpart mismatch')
    require(book['A']['IB_debt'] == book['B']['IB_asset'] and
            book['B']['IB_debt'] == book['A']['IB_asset'], 'interbank counterpart mismatch')


def opening():
    book = {
        'A': {'R': 30, 'S': 20, 'L': 150, 'IB_asset': 0, 'D': 180, 'IB_debt': 0, 'CB_debt': 0, 'E': 20},
        'B': {'R': 20, 'S': 40, 'L': 140, 'IB_asset': 0, 'D': 180, 'IB_debt': 0, 'CB_debt': 0, 'E': 20},
        'CB': {'S': 80, 'advance_A': 0, 'R_A': 30, 'R_B': 20, 'C': 20, 'E': 10},
    }
    result = {entity: {account: F(value) for account, value in accounts.items()}
              for entity, accounts in book.items()}
    validate(result)
    return result


def post(book, changes):
    """Apply stated journal changes transactionally; return a fresh valid book."""
    updated = deepcopy(book)
    for entity, account, amount in changes:
        require(entity in updated and account in updated[entity], 'unknown account')
        updated[entity][account] += F(amount)
    validate(updated)
    return updated


def snapshot(label, book):
    validate(book)
    R, S, L, D, bank_E, cb_debt = (sum(book[b][key] for b in ('A', 'B'))
                                   for key in ('R', 'S', 'L', 'D', 'E', 'CB_debt'))
    C, cb_S, cb_E = (book['CB'][key] for key in ('C', 'S', 'E'))
    consolidated_banks = {'assets': R + S + L, 'deposits': D,
                          'central_bank_debt': cb_debt, 'equity': bank_E}
    consolidated_all = {'assets': S + cb_S + L, 'public_deposits': D,
                        'public_currency': C, 'equity': bank_E + cb_E}
    require(consolidated_banks['assets'] == D + cb_debt + bank_E, 'consolidated banks')
    require(consolidated_all['assets'] == D + C + bank_E + cb_E, 'banks plus central bank')
    convert = lambda record: {key: str(value) for key, value in record.items()}
    return {'label': label, 'accounts': {name: convert(accounts) for name, accounts in book.items()},
            'totals': convert({'reserves': R, 'deposits': D, 'customer_loans': L,
                               'public_currency': C, 'M': D + C, 'H': R + C}),
            'consolidated_banks': convert(consolidated_banks),
            'consolidated_banks_and_CB': convert(consolidated_all)}


def benchmark():
    book = opening()
    stages = [snapshot('opening', book)]
    entries = [
        ('loan_40_at_A', [('A', 'L', 40), ('A', 'D', 40)]),
        ('B_lends_A_15', [('A', 'R', 15), ('A', 'IB_debt', 15),
                          ('B', 'R', -15), ('B', 'IB_asset', 15),
                          ('CB', 'R_A', 15), ('CB', 'R_B', -15)]),
        ('customer_pays_B_40', [('A', 'R', -40), ('A', 'D', -40),
                               ('B', 'R', 40), ('B', 'D', 40),
                               ('CB', 'R_A', -40), ('CB', 'R_B', 40)]),
        ('CB_advances_A_15', [('A', 'R', 15), ('A', 'CB_debt', 15),
                              ('CB', 'advance_A', 15), ('CB', 'R_A', 15)]),
        ('A_repays_interbank_15', [('A', 'R', -15), ('A', 'IB_debt', -15),
                                  ('B', 'R', 15), ('B', 'IB_asset', -15),
                                  ('CB', 'R_A', -15), ('CB', 'R_B', 15)]),
    ]
    for label, journal in entries:
        book = post(book, journal)
        stages.append(snapshot(label, book))
    require(book['A']['CB_debt'] == F(3, 4) * book['A']['S'], 'stated collateral advance cap')
    branches = {}
    branch_entries = {
        'principal_12_from_B_to_A': [('A', 'R', 12), ('A', 'L', -12),
                                    ('B', 'R', -12), ('B', 'D', -12),
                                    ('CB', 'R_A', 12), ('CB', 'R_B', -12)],
        'loss_12_at_A': [('A', 'L', -12), ('A', 'E', -12)],
        'CB_buys_20_from_B': [('B', 'R', 20), ('B', 'S', -20),
                              ('CB', 'S', 20), ('CB', 'R_B', 20)],
        'CB_buys_20_from_nonbank_at_B': [('B', 'R', 20), ('B', 'D', 20),
                                        ('CB', 'S', 20), ('CB', 'R_B', 20)],
        'public_withdraws_currency_12_at_B': [('B', 'R', -12), ('B', 'D', -12),
                                             ('CB', 'R_B', -12), ('CB', 'C', 12)],
    }
    for label, journal in branch_entries.items():
        branches[label] = snapshot(label, post(book, journal))
    loss_book = post(book, branch_entries['loss_12_at_A'])
    for subscription in (F(49, 5), F(59, 5)):
        label = 'recapitalization_' + str(subscription)
        journal = [('A', 'R', subscription), ('A', 'E', subscription),
                   ('B', 'R', -subscription), ('B', 'D', -subscription),
                   ('CB', 'R_A', subscription), ('CB', 'R_B', -subscription)]
        branches[label] = snapshot(label, post(loss_book, journal))
    return {
        'provenance': 'Original synthetic fixed accounting fixture; not observed bank data.',
        'units': 'Nominal currency units at a common instant; no interest or fees accrue during these postings.',
        'accounts': {'R': 'central-bank reserves', 'S': 'government securities at stated carrying value',
                      'L': 'customer-loan carrying value', 'D': 'nonbank customer deposits',
                      'E': 'equity', 'C': 'public currency', 'IB': 'interbank', 'CB': 'central bank'},
        'conventions': ['Government and nonbanks are outside both consolidation boundaries.',
                         'No bank vault cash, foreign positions or other central-bank account holders.',
                         'All branch cases restart from the final stage; recapitalizations restart from its loss branch.',
                         'A secured advance leaves collateral on the bank balance sheet; it is not an outright sale.',
                         'The ledger validates accounts, not profitability, a complete regulatory system or causal effects.'],
        'stages': stages, 'alternative_branches': branches,
    }


if __name__ == '__main__':
    print(json.dumps(benchmark(), indent=2, allow_nan=False))
