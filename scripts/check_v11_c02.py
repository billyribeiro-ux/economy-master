"""Independent journal-vector, valuation and cash-prefix checks for v11-c02.

The checker does not use the lab's posting, measurement or capital helpers.
check() is quiet; all requirements remain active with python -O.
"""
from decimal import Decimal as D
from fractions import Fraction as F
from html.parser import HTMLParser
from pathlib import Path
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import math
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / 'content/projects'
MODEL = PROJECT / 'v11-c02-analysis.py'
COUNT = 0
REJECTS = 0
INTERVENTIONS = 0


def need(condition, label):
    global COUNT
    COUNT += 1
    if not condition:
        raise RuntimeError(label)


def eq(actual, expected, label):
    need(actual == expected, label + ': ' + repr(actual) + ' != ' + repr(expected))


def near(actual, expected, label):
    need(math.isclose(float(actual), float(expected), rel_tol=2e-11, abs_tol=2e-10), label)


def nums(actual, expected, label):
    for key, value in expected.items():
        near(actual[key], value, label + '.' + key)


def strict_json(text):
    def invalid(token):
        raise ValueError('nonfinite result: ' + token)
    return json.loads(text, parse_constant=invalid)


# Each column states independently chosen double-entry counter-accounts. The
# model uses a procedural branch for each transaction; these vectors also make
# the identity's linear conservation certificate visible.
VECTORS = {
    'originate_deposit': {'gross_loans': 1, 'deposits': 1},
    'external_payment': {'cash': -1, 'deposits': -1},
    'principal_collection': {'cash': 1, 'gross_loans': -1},
    'cash_interest': {'cash': 1, 'equity': 1},
    'deposit_interest': {'deposits': 1, 'equity': -1},
    'cash_expense': {'cash': -1, 'equity': -1},
    'provision': {'allowance': 1, 'equity': -1},
    'chargeoff': {'gross_loans': -1, 'allowance': -1},
    'recovery': {'cash': 1, 'allowance': 1},
    'dividend': {'cash': -1, 'equity': -1},
    'allowance_release': {'allowance': -1, 'equity': 1},
}
SIGNS = {'cash': 1, 'free_securities': 1, 'pledged_securities': 1,
         'gross_loans': 1, 'allowance': -1, 'property': 1, 'goodwill': 1,
         'deposits': -1, 'wholesale': -1, 'other_liabilities': -1, 'equity': -1}


def balances(s):
    assets = sum(s[k] for k in ('cash', 'free_securities', 'pledged_securities',
                               'gross_loans', 'property', 'goodwill')) - s['allowance']
    debt = s['deposits'] + s['wholesale'] + s['other_liabilities']
    return {'assets': assets, 'liabilities': debt, 'equity': s['equity'],
            'net_loans': s['gross_loans'] - s['allowance'],
            'identity_residual': assets-debt-s['equity']}


def journal_oracle(data, result):
    s = {k: D(str(v)) for k, v in data['opening'].items()}
    nums(result['opening'], balances(s), 'opening identity')
    income = D(0)
    distribution = D(0)
    for entry, actual in zip(data['journal'], result['journal_states']):
        kind, amount = entry['kind'], D(str(entry['amount']))
        vector = VECTORS[kind]
        eq(sum(SIGNS[k]*change for k, change in vector.items()), 0, kind+' balanced vector')
        s = {k: value+amount*vector.get(k, 0) for k, value in s.items()}
        if kind == 'dividend':
            distribution += amount
        else:
            income += amount*vector.get('equity', 0)
        eq(actual['id'], entry['id'], 'journal original ID')
        nums(actual['accounts'], s, 'independent journal '+entry['id'])
        nums(actual['totals'], balances(s), 'journal totals '+entry['id'])
    eq(len(result['journal_states']), len(data['journal']), 'all journal entries reported')
    nums(result['closing_accounts'], s, 'closing vector sum')
    nums(result['closing'], balances(s), 'closing totals')
    near(result['net_income'], income, 'income separated from distribution')
    near(result['dividends'], distribution, 'distribution total')
    near(result['income_equity_residual'], 0, 'equity roll-forward')
    return s


def cash_oracle(data, out, closing=None):
    """Compute each prefix from the starting stocks and cumulative dated flows.

    This does not replay the model's mutable forecast-state updates.
    """
    s = closing or {k: D(str(v)) for k, v in out['closing_accounts'].items()}
    r, q = data['repair']['kind'], D(str(data['repair']['amount']))
    cash_added = q if r in ('cash_equity', 'unsecured_borrow') else D(0)
    equity_added = q if r in ('cash_equity', 'deposit_conversion') else D(0)
    converted = q if r == 'deposit_conversion' else D(0)
    borrowed = q if r == 'unsecured_borrow' else D(0)
    post = dict(s)
    post['cash'] += cash_added
    post['equity'] += equity_added
    post['deposits'] -= converted
    post['wholesale'] += borrowed
    nums(out['post_repair_accounts'], post, 'repair counter-entries')
    liq = data['liquidity']
    capacity = (1-D(str(liq['haircut'])))*D(str(data['valuation']['free_security_value']))
    repay = capacity*D(str(liq['secured_gross']))
    near(out['liquidity']['secured_capacity'], capacity, 'free-only haircut advance')
    near(out['liquidity']['secured_interest'], repay-capacity, 'financing income cost')
    heads = []
    events = liq['events']
    for i, row in enumerate(out['liquidity']['forecast']):
        cutoff = events[i]['cutoff']
        cumulative = {k: sum(D(str(e[k])) for e in events[:i+1]) for k in
                      ('loan_principal_in', 'deposits_out', 'wholesale_out', 'other_out')}
        has_drawn = cutoff >= liq['draw_cutoff']
        has_repaid = cutoff >= liq['repay_cutoff']
        cash = (post['cash'] + cumulative['loan_principal_in']
                - cumulative['deposits_out']-cumulative['wholesale_out']-cumulative['other_out']
                + capacity*has_drawn - repay*has_repaid)
        h = cash-D(str(liq['restricted_cash']))
        heads.append(h)
        near(row['cash_after_assumed_payments'], cash, 'cumulative cash conservation')
        near(row['unrestricted_headroom'], h, 'cumulative usable cash')
        near(row['payment_shortfall'], max(D(0), -h), 'actual payment gap')
        eq(row['executable_without_added_funding_through_here'], min(heads)>=0, 'no retroactive cure')
        encumbered = has_drawn and not has_repaid
        expected = dict(post)
        expected.update(cash=cash,
                        free_securities=post['free_securities']*(not encumbered),
                        pledged_securities=post['pledged_securities']+post['free_securities']*encumbered,
                        gross_loans=post['gross_loans']-cumulative['loan_principal_in'],
                        deposits=post['deposits']-cumulative['deposits_out'],
                        wholesale=post['wholesale']-cumulative['wholesale_out']+capacity*(has_drawn-has_repaid),
                        other_liabilities=post['other_liabilities']-cumulative['other_out'],
                        equity=post['equity']-(repay-capacity)*has_repaid)
        nums(row['projected_accounts_if_all_payments_made'], expected, 'closed-form projected accounts')
        nums(row['totals'], balances(expected), 'projected accounting conservation')
    first = next((events[i]['cutoff'] for i, h in enumerate(heads) if h<0), None)
    prefix = next((i for i, h in enumerate(heads) if h<0), len(heads))
    eq(out['liquidity']['first_failure_cutoff'], first, 'first failed payment cutoff')
    eq(out['liquidity']['executable_prefix_cutoffs'], prefix, 'executable prefix length')
    eq(out['liquidity']['feasible_through_horizon'], first is None, 'whole cash plan feasibility')
    near(out['liquidity']['minimum_upfront_external_cash_for_this_fixed_plan'], max(D(0), -min(heads)), 'prefix injection certificate')
    return post, heads


def capital_oracle(data, actual, s):
    b, rules = balances(s), data['instructional_capital']
    k, u = s['equity']-s['goodwill'], b['assets']-s['goodwill']
    rwa = sum(D(str(rules[w]))*exposure for w, exposure in
              [('loan_weight', s['gross_loans']-s['allowance']),
               ('security_weight', s['free_securities']+s['pledged_securities']),
               ('property_weight', s['property'])])
    r, l = D(str(rules['risk_ratio_floor'])), D(str(rules['leverage_floor']))
    nums(actual, {'adjusted_capital': k, 'adjusted_exposure': u, 'toy_rwa': rwa,
                 'book_equity_to_assets': s['equity']/b['assets'],
                 'toy_risk_ratio': k/rwa, 'toy_leverage_ratio': k/u,
                 'minimum_cash_equity_for_ratios': max(D(0), r*rwa-k, (l*u-k)/(1-l)),
                 'minimum_deposit_conversion_for_ratios': max(D(0), r*rwa-k, l*u-k)}, 'ratio algebra')
    eq(actual['risk_gate'], k>=r*rwa, 'cross-multiplied risk gate')
    eq(actual['leverage_gate'], k>=l*u, 'cross-multiplied exposure gate')


def valuation_oracle(data, out, post):
    v = data['valuation']
    assets = post['cash']+sum(D(str(v[k])) for k in ('free_security_value', 'pledged_security_value',
                              'loan_value', 'property_value', 'goodwill_value'))
    debt = post['deposits']+post['wholesale']+post['other_liabilities']
    economic = assets-debt
    nums(out['valuation'], {'book_equity': post['equity'], 'economic_assets': assets,
                           'economic_equity': economic,
                           'severe_economic_equity': economic-D(str(v['loan_value']))+D(str(v['severe_loan_value'])),
                           'book_to_economic_equity_change': economic-post['equity']}, 'complete marks without duplicate allowance')


def run_quiet(model, data):
    before = copy.deepcopy(data)
    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        result = model.run(data)
    eq((stdout.getvalue(), stderr.getvalue()), ('', ''), 'quiet run API')
    eq(data, before, 'nonmutating run API')
    eq(strict_json(json.dumps(result, allow_nan=False)), result, 'strict JSON round trip')
    return result


def change(data, path, value):
    result = copy.deepcopy(data)
    target = result
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    return result


def exercises_and_interventions(model, data, base):
    global INTERVENTIONS
    # Independent literal account anchors prevent a shared input typo becoming
    # the expected answer through the data-driven vector reconstruction.
    nums(base['closing_accounts'], {'cash': 34.5, 'gross_loans': 242, 'allowance': 5,
                                    'deposits': 266, 'wholesale': 50, 'other_liabilities': 10, 'equity': 13.5}, 'worked1 anchors')
    nums(base['closing'], {'assets': 339.5, 'liabilities': 326, 'net_loans': 237}, 'worked1 totals')
    nums(base['valuation'], {'economic_assets': 327.5, 'economic_equity': 1.5, 'severe_economic_equity': -6.5}, 'worked2 marks')
    nums(base['base_capital'], {'adjusted_capital': 11.5, 'adjusted_exposure': 337.5,
                               'toy_rwa': 255, 'minimum_cash_equity_for_ratios': 3.8}, 'worked2 ratios')
    eq([r['unrestricted_headroom'] for r in base['liquidity']['forecast']], [-1.2, 5.8, 1.712], 'worked3 exact cash prefixes')

    def variant(x):
        global INTERVENTIONS
        INTERVENTIONS += 1
        return run_quiet(model, x)

    # All three repairs keep the same actual payment schedule, and the cash
    # issue includes its own proceeds in its leverage denominator.
    for kind in ('cash_equity', 'deposit_conversion', 'unsecured_borrow'):
        x = change(data, ['repair'], {'kind': kind, 'amount': 3.8})
        out = variant(x)
        post, heads = cash_oracle(x, out)
        capital_oracle(x, out['post_repair_capital'], post)
        valuation_oracle(x, out, post)
        near(out['post_repair_capital']['adjusted_capital'], 11.5 if kind=='unsecured_borrow' else 15.3, 'repair capital mechanism')
        near(heads[0], -1.2 if kind=='deposit_conversion' else 2.6, 'repair cash mechanism')
        if kind=='cash_equity':
            near(out['valuation']['severe_economic_equity'], -2.7, 'repair does not eliminate severe valuation deficit')
            nums(out['liquidity']['forecast'][-1]['totals'], {'assets': 268.012, 'liabilities': 251, 'equity': 17.012}, 'funded end balance')
    almost = variant(change(data, ['repair'], {'kind': 'cash_equity', 'amount': 3.799}))
    eq(almost['post_repair_capital']['risk_gate'], False, 'joint minimum is binding')
    near(F(4,100)*F(675,2)-F(23,2), 2, 'leverage numerator gap')
    eq((F(4,100)*F(675,2)-F(23,2))/(1-F(4,100)), F(25,12), 'cash enters leverage denominator')

    x = copy.deepcopy(data)
    x['journal'] += [{'id': 'E1-origin', 'kind': 'originate_deposit', 'amount': 12},
                     {'id': 'E1-external', 'kind': 'external_payment', 'amount': 5}]
    out = variant(x)
    nums(out['closing_accounts'], {'cash': 29.5, 'gross_loans': 254, 'deposits': 273, 'equity': 13.5}, 'exercise1 settlement')
    nums(out['closing'], {'assets': 346.5, 'liabilities': 333}, 'exercise1 external versus internal')

    x = copy.deepcopy(data)
    x['opening'].update(gross_loans=70, allowance=6, deposits=110, equity=2)
    x['valuation'].update(loan_value=57, severe_loan_value=50)
    x['journal'] = [{'id': 'E2-provision', 'kind': 'provision', 'amount': 6},
                    {'id': 'E2-chargeoff', 'kind': 'chargeoff', 'amount': 8},
                    {'id': 'E2-recovery', 'kind': 'recovery', 'amount': 1}]
    for e in x['liquidity']['events']:
        e['loan_principal_in'] = 0
    out = variant(x)
    journal_oracle(x, out)
    nums(out['closing_accounts'], {'gross_loans': 62, 'allowance': 5, 'cash': 41, 'equity': -4}, 'exercise2 feasible allowance sequence')
    near(out['closing']['net_loans'], 57, 'exercise2 final net loans')
    near(out['closing']['assets']-out['opening']['assets'], -6, 'exercise2 assets change including recovery cash')

    for loan, expected in ((231, 1.5), (223, -6.5), (229.5, 0)):
        out = variant(change(data, ['valuation', 'loan_value'], loan))
        near(out['valuation']['economic_equity'], F(str(loan))-F('229.5'), 'exercise3 residual function')
        near(out['valuation']['economic_equity'], expected, 'exercise3 mark boundary')
        eq(out['closing_accounts'], base['closing_accounts'], 'mark does not post cash/book entry')
        eq(out['liquidity'], base['liquidity'], 'loan mark alone not funding')

    out = variant(change(data, ['instructional_capital', 'loan_weight'], .7))
    near(out['base_capital']['toy_rwa'], 183.9, 'exercise4 reweighted denominator')
    near(out['base_capital']['toy_risk_ratio'], F(115,1839), 'exercise4 ratio')
    eq((out['base_capital']['risk_gate'], out['base_capital']['leverage_gate']), (True, False), 'exercise4 gates')
    eq((out['valuation'], out['liquidity'], out['closing_accounts']),
       (base['valuation'], base['liquidity'], base['closing_accounts']), 'weight is neither value nor cash')

    eq(1-(F(70)-30-10)/36, F(1,6), 'exercise5 haircut threshold')
    for haircut in (.166, .167, 1):
        x = change(data, ['liquidity', 'haircut'], haircut)
        out = variant(x)
        cash_oracle(x, out)
        eq(out['liquidity']['forecast'][0]['executable_without_added_funding_through_here'], haircut<1/6, 'haircut boundary sides')
    x = copy.deepcopy(data)
    x['liquidity']['events'][0]['loan_principal_in'] += 12
    x['liquidity']['events'][1]['loan_principal_in'] = 0
    out = variant(x)
    eq([r['unrestricted_headroom'] for r in out['liquidity']['forecast']], [10.8, 5.8, 1.712], 'exercise5 real timing intervention')
    eq(out['liquidity']['feasible_through_horizon'], True, 'same total receipts different feasibility')

    # Further separate provision, use, receipt and supported release.
    out = variant(change(data, ['journal', 7, 'amount'], 9))
    nums(out['closing_accounts'], {'gross_loans': 243, 'allowance': 6, 'equity': 13.5, 'cash': 34.5}, 'covered chargeoff intervention')
    eq(out['closing'], base['closing'], 'covered chargeoff neutrality')
    out = variant(change(data, ['journal', 6, 'amount'], 7))
    nums(out['closing_accounts'], {'allowance': 6, 'equity': 12.5, 'cash': 34.5}, 'additional provision')
    eq([r['unrestricted_headroom'] for r in out['liquidity']['forecast']], [-1.2, 5.8, 1.712], 'provision does not fund cash')
    eq(out['valuation']['economic_equity'], base['valuation']['economic_equity'], 'fixed complete PV not allowance deduction')
    out = variant(change(data, ['journal', 8, 'amount'], 2))
    nums(out['closing_accounts'], {'cash': 35.5, 'allowance': 6, 'equity': 13.5}, 'recovery cash and allowance credit')
    near(out['net_income'], -4.5, 'no double-counted recovery income')
    near(out['closing']['assets'], 339.5, 'recovery net-book offset')
    x = copy.deepcopy(data)
    x['journal'].append({'id': 'release', 'kind': 'allowance_release', 'amount': 1})
    out = variant(x)
    nums(out['closing_accounts'], {'cash': 34.5, 'allowance': 4, 'equity': 14.5}, 'separate release')
    near(out['net_income'], -3.5, 'release raises earnings separately')
    out = variant(change(data, ['journal', 9, 'amount'], 0))
    nums(out['closing_accounts'], {'cash': 36.5, 'equity': 15.5}, 'no dividend retains cash and equity')
    near(out['net_income'], -4.5, 'dividend is not income expense')

    for path, value in [(['liquidity', 'restricted_cash'], 0),
                        (['liquidity', 'draw_cutoff'], 2),
                        (['liquidity', 'repay_cutoff'], 2),
                        (['liquidity', 'secured_gross'], .99)]:
        x = change(data, path, value)
        out = variant(x)
        cash_oracle(x, out)
    x = copy.deepcopy(data)
    x['opening'].update(free_securities=20, pledged_securities=40)
    x['valuation'].update(free_security_value=18, pledged_security_value=38)
    out = variant(x)
    near(out['liquidity']['secured_capacity'], 14.4, 'encumbrance lowers available facility')
    near(out['liquidity']['forecast'][0]['unrestricted_headroom'], -15.6, 'encumbrance actual gap')
    near(out['valuation']['economic_equity'], 1.5, 'encumbrance not an automatic valuation loss')

    # Exercises 7 and 8 concern an alternative sale and an audit of a false
    # report, not an unsupported second feature of the secured-funding model.
    book_loss, economic_loss = F(40)-34, F(36)-34
    eq((F('13.5')-book_loss, F('1.5')-economic_loss), (F('7.5'), F('-.5')), 'exercise7 distinct valuation bases')
    sale_heads = [30+34+10-70, 30+34+10+12-70-5, 30+34+10+12+25-70-5]
    eq(sale_heads, [4,11,36], 'exercise7 no secured draw or repayment')
    wrong = F('34.5')+5+10+F('.8')*56-70
    over = F('4.5')+5+F('.8')*20
    eq((wrong, over, wrong-over), (F('24.3'),F('25.5'),F('-1.2')), 'exercise8 three quantified overstatements')
    eq((70-9)-(70-4-(9-4)), 0, 'retention covered chargeoff')
    eq((7-6, max(0, -min(2,-3,1))), (1,3), 'retention dated gap and cash certificate')


def invalid_inputs(model, data):
    global REJECTS
    def reject(x, label):
        global REJECTS
        before = copy.deepcopy(x)
        try:
            model.run(x)
        except ValueError:
            REJECTS += 1
        else:
            raise RuntimeError('accepted invalid API input: '+label)
        # JSON spellings allow unchanged NaN values to be compared here.
        eq(json.dumps(x, sort_keys=True), json.dumps(before, sort_keys=True), label+' rejection is nonmutating')

    cases = [(['schema_version'], True), (['provenance'], ''), (['opening','cash'], True),
             (['opening','cash'], '40'), (['opening','cash'], float('nan')),
             (['opening','cash'], float('inf')), (['opening','cash'], 10**1000),
             (['opening','cash'], -1), (['opening','equity'], 21),
             (['journal'], []), (['journal',0,'amount'], -1),
             (['journal',0,'kind'], 'cash_from_allowance'), (['journal',1,'amount'], 100),
             (['journal',7,'amount'], 15), (['journal',0,'id'], 'J2'),
             (['valuation','loan_value'], -1), (['instructional_capital','loan_weight'], -1),
             (['instructional_capital','leverage_floor'], 1),
             (['liquidity','restricted_cash'], 35), (['liquidity','haircut'], 1.1),
             (['liquidity','secured_gross'], 0), (['liquidity','draw_cutoff'], True),
             (['liquidity','draw_cutoff'], 3), (['liquidity','repay_cutoff'], 4),
             (['liquidity','events',1,'cutoff'], 1),
             (['liquidity','events',0,'loan_principal_in'], 238),
             (['liquidity','events',0,'deposits_out'], 300),
             (['liquidity','events',0,'wholesale_out'], 51),
             (['liquidity','events',0,'other_out'], 11),
             (['repair'], {'kind':'none','amount':1}),
             (['repair'], {'kind':'deposit_conversion','amount':212}),
             (['repair'], {'kind':'invent_cash','amount':1})]
    for path, value in cases:
        reject(change(data, path, value), repr(path))
    x = copy.deepcopy(data); x['extra'] = 1; reject(x, 'extra root field')
    x = copy.deepcopy(data); del x['opening']['cash']; reject(x, 'missing account')
    x = copy.deepcopy(data); x['liquidity']['events'][0]['phantom_in'] = 1; reject(x, 'extra event field')
    x = copy.deepcopy(data); x['journal'] *= 5; reject(x, 'journal length bound')
    x = copy.deepcopy(data); x['journal'].append({'id':'bad-release','kind':'allowance_release','amount':6}); reject(x, 'negative allowance')
    x = copy.deepcopy(data)
    for k in ('loan_weight','security_weight','property_weight'): x['instructional_capital'][k] = 0
    reject(x, 'zero weighted denominator')
    x = copy.deepcopy(data)
    for k in ('loan_weight','security_weight','property_weight'): x['instructional_capital'][k] = 5e-324
    reject(x, 'ratio outside finite JSON-number output range')
    for account, mark in (('free_securities','free_security_value'), ('pledged_securities','pledged_security_value'),
                          ('property','property_value'), ('goodwill','goodwill_value')):
        x = copy.deepcopy(data)
        x['opening']['equity'] -= x['opening'][account]
        x['opening'][account] = 0
        x['valuation'][mark] = 1
        reject(x, 'positive mark of absent '+account)
    x = copy.deepcopy(data)
    x['opening'].update(gross_loans=0, allowance=0, equity=-212)
    x['journal'] = [{'id':'zero','kind':'cash_interest','amount':0}]
    for e in x['liquidity']['events']: e['loan_principal_in'] = 0
    reject(x, 'positive mark of absent gross loans')
    x['opening'].update(gross_loans=240, allowance=240)
    out = run_quiet(model, x)
    near(out['closing']['net_loans'], 0, 'fully allowed gross claims remain actual claims')
    near(out['valuation']['economic_equity'], 13, 'complete positive loan PV allowed with zero book net loans')


class Chapter(HTMLParser):
    def __init__(self):
        super().__init__(); self.ids=[]; self.solutions=[]; self.worked=0; self.sources=set(); self.local=[]
    def handle_starttag(self, tag, attrs):
        a=dict(attrs)
        if 'id' in a: self.ids.append(a['id'])
        if 'data-solution-for' in a: self.solutions.append(a['data-solution-for'])
        if 'worked' in a.get('class','').split(): self.worked += 1
        if 'data-source' in a: self.sources.add(a['data-source'])
        if a.get('href','').startswith('#'): self.local.append(a['href'][1:])


def structure_and_hashes():
    chapter=Chapter(); chapter.feed((ROOT/'content/chapters/v11-c02.html').read_text())
    expected=['v11-c02-e'+str(i) for i in range(1,9)]
    eq(len(chapter.ids),len(set(chapter.ids)),'unique chapter IDs')
    eq([x for x in chapter.ids if x in expected],expected,'all eight exact exercises')
    eq(chapter.solutions,expected,'every prompt has one corresponding solution')
    eq(chapter.worked,3,'three worked examples')
    need(set(chapter.local)<=set(chapter.ids),'local chapter anchors resolve')
    need({'objective','allowance','economic-value','capital-ratios','dated-liquidity','teach-back'}<=set(chapter.ids),'required teaching sections')
    sources=strict_json((ROOT/'content/reviews/v11-c02-sources.json').read_text())
    eq(chapter.sources,{x['id'] for x in sources},'source routes match scoped proposals')
    eq(len(sources),3,'three primary scoped source records')
    for s in sources:
        need(s['url'].startswith('https://') and s['checked']=='2026-10-09' and len(s['verification'])>100,'source inspection metadata')
    manifest=strict_json((PROJECT/'v11-c02-manifest.json').read_text())
    eq({x['file'] for x in manifest['files']},{'v11-c02-'+x for x in ('inputs.json','analysis.py','output.json','README.txt')},'manifest exact four lab payloads')
    for item in manifest['files']:
        payload=(PROJECT/item['file']).read_bytes()
        eq((len(payload),hashlib.sha256(payload).hexdigest()),(item['bytes'],item['sha256']),'manifest '+item['file'])
    author=strict_json((ROOT/'content/reviews/v11-c02-author.json').read_text())
    paths={'content/chapters/v11-c02.html','scripts/check_v11_c02.py','content/reviews/v11-c02-sources.json'}
    paths.update('content/projects/v11-c02-'+x for x in ('inputs.json','analysis.py','output.json','README.txt','manifest.json'))
    eq({x['path'] for x in author['reviewed_hashes']},paths,'eight exact nonself author bindings')
    eq(len(author['reviewed_hashes']),8,'no duplicate author binding')
    for item in author['reviewed_hashes']:
        payload=(ROOT/item['path']).read_bytes()
        eq((len(payload),hashlib.sha256(payload).hexdigest()),(item['bytes'],item['sha256']),'author binding '+item['path'])


def cli_checks(data, base):
    # Only temporary copies can be targeted by destructive-path test requests.
    with tempfile.TemporaryDirectory(prefix='v11-c02-check-') as directory:
        temp=Path(directory); model=temp/MODEL.name; inp=temp/'v11-c02-inputs.json'
        model.write_bytes(MODEL.read_bytes()); inp.write_text(json.dumps(data))
        for flag in ([],['-O']):
            proc=subprocess.run([sys.executable,*flag,str(model)],cwd='/',capture_output=True,text=True,timeout=20)
            eq((proc.returncode,proc.stderr),(0,''),'portable CLI normal/optimized')
            eq(strict_json(proc.stdout),base,'portable CLI saved base')
            output=temp/'valid-output.json'
            proc=subprocess.run([sys.executable,*flag,str(model),str(inp),'--output',str(output)],cwd='/',capture_output=True,text=True,timeout=20)
            eq((proc.returncode,proc.stdout,proc.stderr),(0,'',''),'quiet output-file CLI')
            eq(strict_json(output.read_text()),base,'output file result')
            for protected in (inp,model):
                symbolic=temp/('sym-'+protected.name)
                hard=temp/('hard-'+protected.name)
                if not symbolic.exists(): symbolic.symlink_to(protected)
                if not hard.exists(): hard.hardlink_to(protected)
                before=protected.read_bytes()
                for target in (protected,symbolic,hard):
                    proc=subprocess.run([sys.executable,*flag,str(model),str(inp),'--output',str(target)],cwd='/',capture_output=True,text=True,timeout=20)
                    eq((proc.returncode,proc.stdout),(2,''),'overwrite guard rejects direct/alias output')
                    need('overwrite' in proc.stderr,'clear overwrite diagnostic')
                    eq(protected.read_bytes(),before,'overwrite rejection preserves bytes')
            for invalid in ('{"schema_version":1,"schema_version":1}', '{"x":NaN}', 'x'*200001):
                bad=temp/'bad.json'; bad.write_text(invalid)
                proc=subprocess.run([sys.executable,*flag,str(model),str(bad)],cwd='/',capture_output=True,text=True,timeout=20)
                eq((proc.returncode,proc.stdout),(2,''),'strict CLI rejects duplicate/nonfinite/oversized input')
                need(proc.stderr.startswith('error: '),'concise invalid CLI diagnostic')


def check():
    global COUNT, REJECTS, INTERVENTIONS
    COUNT=0; REJECTS=0; INTERVENTIONS=0
    data=strict_json((PROJECT/'v11-c02-inputs.json').read_text())
    spec=importlib.util.spec_from_file_location('v11_c02_checked_model',MODEL)
    model=importlib.util.module_from_spec(spec)
    capture=io.StringIO()
    with contextlib.redirect_stdout(capture),contextlib.redirect_stderr(capture):
        spec.loader.exec_module(model)
    eq(capture.getvalue(),'','quiet model import')
    base=run_quiet(model,data)
    closing=journal_oracle(data,base)
    capital_oracle(data,base['base_capital'],closing)
    post,_=cash_oracle(data,base,closing)
    capital_oracle(data,base['post_repair_capital'],post)
    valuation_oracle(data,base,post)
    eq(base,strict_json((PROJECT/'v11-c02-output.json').read_text()),'saved base reproduced after independent recomputation')
    exercises_and_interventions(model,data,base)
    invalid_inputs(model,data)
    cli_checks(data,base)
    structure_and_hashes()
    summary={'chapter':'v11-c02','status':'passed','comparisons':COUNT,
             'financial_interventions':INTERVENTIONS,'invalid_api_inputs_rejected':REJECTS,
             'worked_examples':3,'solved_exercises':8,'author_payload_hashes_verified':8,
             'methods':['independent account-change vectors and identity conservation',
                        'complete-value bridge and cross-multiplied capital inequalities',
                        'cumulative cash prefixes and closed-form projected accounts',
                        'financial timing/valuation/repair/allowance interventions',
                        'strict API and normal/optimized isolated CLI with byte-preserving path guards'],
             'limits':'Author calculation and bounded implementation checks; separate peer, coordinator acceptance and real-world evidence remain distinct.'}
    json.dumps(summary,allow_nan=False)
    return summary


if __name__=='__main__':
    print(json.dumps(check(),indent=2,allow_nan=False))
