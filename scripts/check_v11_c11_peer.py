"""Separate machine-assisted C11 peer: funded wallets and rational root enclosures.

Only the frozen model's public run(data) is called. Neither author helpers nor
author checker supply any oracle. check() is quiet, strict-JSON-safe, portable,
and unaffected by Python optimization. Every financial case has a stated purpose.
"""
import contextlib
import copy
from fractions import Fraction as F
import hashlib
from html.parser import HTMLParser
import io
import json
from math import isqrt
import os
from pathlib import Path
import re
import runpy
import shutil
import subprocess
import sys
import tempfile

AUTHOR = ['content/chapters/v11-c11.html'] + [
    'content/projects/v11-c11-'+s for s in
    ('inputs.json', 'analysis.py', 'output.json', 'manifest.json', 'README.txt')
] + ['scripts/check_v11_c11.py', 'content/reviews/v11-c11-author.json',
     'content/reviews/v11-c11-sources.json']
SELF = 'scripts/check_v11_c11_peer.py'
REVIEW = 'content/reviews/v11-c11-peer.json'
COUNTS = {}
BAND = F(1, 10**24)
TOL = F(1, 10**34)


def need(ok, label):
    COUNTS['comparisons'] += 1
    if not ok:
        raise ValueError('v11-c11 peer: '+label)


def near(got, expected, label, tolerance=TOL):
    need(abs(F(got)-expected) <= tolerance*max(F(1), abs(expected)), label)


def strict(text):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('duplicate JSON key')
            result[key] = value
        return result
    def bad(value):
        raise ValueError('nonfinite JSON constant '+value)
    return json.loads(text, object_pairs_hook=pairs, parse_constant=bad)


def compare(got, expected, label):
    if isinstance(expected, F):
        need(type(got) is str and re.fullmatch(r'-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?', got) is not None,
             label+' finite decimal serialization')
        near(got, expected, label)
    elif type(expected) is dict:
        need(type(got) is dict and set(got) == set(expected), label+' exact keys')
        for key, value in expected.items():
            compare(got[key], value, label+'.'+key)
    elif type(expected) is list:
        need(type(got) is list and len(got) == len(expected), label+' list size')
        for index, value in enumerate(expected):
            compare(got[index], value, label+'.'+str(index))
    else:
        need(type(got) is type(expected) and got == expected, label+' exact value')


def numbers(raw):
    return {key: F(value) for key, value in raw.items()}


def edit(data, changes):
    result = copy.deepcopy(data)
    for path, value in changes:
        target = result
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value
    return result


def sqrt_interval(x):
    """Floor an integer square root on a 60-place rational grid, not bisection."""
    need(x >= 0, 'square-root domain')
    a, b = isqrt(x.numerator), isqrt(x.denominator)
    if a*a == x.numerator and b*b == x.denominator:
        return F(a, b), F(a, b)
    scale = 10**60
    k = isqrt(x.numerator*scale*scale // x.denominator)
    low, high = F(k, scale), F(k+1, scale)
    need(low*low <= x <= high*high, 'integer-square-root rational certificate')
    return low, high


def auction(p0, impact, free, target):
    """Unique smallest sufficient sale on the independently checked domain."""
    capacity = p0*free-impact*free*free
    if target >= capacity:
        sale = free
        return sale, capacity, ('all_free_assets' if target > capacity else
                               'exact_free_asset_boundary'), (sale, sale)
    if target == 0:
        return F(0), F(0), 'no_sale', (F(0), F(0))
    if impact == 0:
        sale = target/p0
        return sale, target, 'constant_price', (sale, sale)
    low, high = sqrt_interval(p0*p0-4*impact*target)
    a, b = 2*target/(p0+high), 2*target/(p0+low)
    need(0 <= a <= b <= free, 'auction root stays in free-inventory domain')
    need(p0*a-impact*a*a <= target <= p0*b-impact*b*b,
         'rational endpoints bracket required proceeds')
    need(b-a < F(1, 10**54), 'root certificate precision')
    COUNTS['root_certificates'] += 1
    return (a+b)/2, target, 'interior_monotone_root', (a, b)


class Wallets:
    """Each transfer debits an actually funded pocket and credits its recipient."""
    def __init__(self, data):
        self.cash = dict(A=F(data['bank']['cash']), B=F(data['beacon']['cash']),
                         public=F(data['policy']['public_cash']),
                         buyer=F(data['bank']['asset_units'])*F(data['market']['intercept']),
                         retail=F(0), f0=F(0), f1=F(0), customer=F(0),
                         A_equity=F(0), B_equity=F(0))
        self.initial = sum(self.cash.values())

    def pay(self, source, target, amount):
        if not 0 <= amount <= self.cash[source]:
            raise ValueError('unfunded oracle transfer '+source+' to '+target)
        self.cash[source] -= amount
        self.cash[target] += amount
        COUNTS['funded_transfers'] += 1

    def exhaust(self, source, target, claim):
        paid = min(claim, self.cash[source])
        self.pay(source, target, paid)
        return paid


def beacon_end(data, w, receipts, bridge, paid_early):
    due = F(data['beacon']['customer_due'])
    paid_bridge = w.exhaust('B', 'public', bridge)
    paid_late = w.exhaust('B', 'customer', due-paid_early)
    equity = w.cash['B']
    w.pay('B', 'B_equity', equity)
    customer_loss = due-paid_early-paid_late
    network_loss = F(data['bank']['network_due'])-sum(receipts)
    allocation = (F(data['beacon']['opening_equity'])-equity + customer_loss + bridge-paid_bridge)
    need(allocation == network_loss, 'Beacon allocates one network impairment, not two')
    return dict(receipt_cutoff1=receipts[0], receipt_cutoff2=receipts[1], bridge_draw=bridge,
                customer_paid_cutoff1=paid_early, customer_missed_cutoff1=due-paid_early,
                customer_paid_cutoff2=paid_late, customer_terminal_loss=customer_loss,
                bridge_repayment=paid_bridge, public_bridge_loss=bridge-paid_bridge,
                equity_terminal=equity, network_asset_loss=network_loss,
                loss_attribution_residual=allocation-network_loss)


def line_journal(data, cap, actions, terminal_value):
    """Execute each funder's dated rights, including actual after-deviation sales."""
    bank, market = numbers(data['bank']), numbers(data['market'])
    p0, impact, N = market['intercept'], market['impact'], bank['asset_units']
    m = actions.count('R')
    need(2*impact*N <= p0, 'monotone auction domain from primitives')
    w = Wallets(data)
    demand = bank['retail_due'] + m*bank['funder_principal'] + bank['network_due']
    need_cash = max(demand-w.cash['A'], F(0))
    advance = F(data['policy']['advance_fraction'])*p0
    draw = min(need_cash, F(cap), advance*N)
    pledge, free = draw/advance, N-draw/advance
    w.pay('public', 'A', draw)
    sale, receipts, regime, enclosure = auction(p0, impact, free, need_cash-draw)
    need(sale+pledge <= N and 0 <= draw <= F(data['policy']['public_cash']),
         'one pledge; separately funded public commitment')
    price = p0-impact*sale
    w.pay('buyer', 'A', receipts)
    retail = w.exhaust('A', 'retail', bank['retail_due'])
    runner_total = min(m*bank['funder_principal'], w.cash['A'])
    early = [runner_total/m if a == 'R' else F(0) for a in actions]
    for i in range(2):
        w.pay('A', 'f'+str(i), early[i])
    network_early = w.exhaust('A', 'B', bank['network_due'])
    cash_left = w.cash['A']
    customer_early = w.exhaust('B', 'customer', F(data['beacon']['customer_due']))
    principal_left = sum(bank['funder_principal']-early[i] for i in range(2)) + bank['network_due']-network_early
    marked_assets = cash_left+price*(N-sale)
    marked_equity = marked_assets-principal_left-draw
    near(marked_equity, bank['cash']+price*N-bank['retail_due']-2*bank['funder_principal']-bank['network_due'],
         'sales, loan and principal retirement preserve same-price equity', F(1,10**50))
    opening = dict(runners=m, loan=draw, pledged_units=pledge, free_units=free,
                   sale_units=sale, sale_price=price, sale_proceeds=receipts, sale_regime=regime,
                   retail_paid=retail, runners_paid=sum(early), runner_unpaid=m*bank['funder_principal']-sum(early),
                   network_paid=network_early, network_unpaid=bank['network_due']-network_early,
                   cash_remaining=cash_left, retained_units=N-sale, marked_assets=marked_assets,
                   principal_marked_equity=marked_equity,
                   assets_to_equity=marked_assets/marked_equity if marked_equity>BAND else None,
                   cash_residual=F(0), sale_residual=F(0))
    # Production of the only terminal asset payoff, once across its two holders.
    v = F(terminal_value)
    w.cash['A'] += v*(N-sale)
    w.cash['buyer'] += v*sale
    estate = w.cash['A']
    repaid = w.exhaust('A', 'public', draw)
    claims = [bank['funder_principal']*bank['wait_multiplier'] if a == 'W' else
              bank['funder_principal']-early[i] for i,a in enumerate(actions)]
    claims.append(bank['network_due']-network_early)
    total_claim = sum(claims)
    rate = min(F(1), w.cash['A']/total_claim) if total_claim else F(1)
    late = [claim*rate for claim in claims]
    for i in range(2):
        w.pay('A', 'f'+str(i), late[i])
    w.pay('A', 'B', late[2])
    equity = w.cash['A']
    w.pay('A', 'A_equity', equity)
    beacon = beacon_end(data, w, (network_early, late[2]), F(0), customer_early)
    payoff = [w.cash['f'+str(i)] for i in range(2)]
    wait_paid = sum((late[i] for i,a in enumerate(actions) if a=='W'), F(0))
    late_run = sum((late[i] for i,a in enumerate(actions) if a=='R'), F(0))
    interest = sum((bank['funder_principal']*(bank['wait_multiplier']-1) for a in actions if a=='W'), F(0))
    private_loss = sum(claims)-sum(late)
    public_loss = draw-repaid
    gain = w.cash['buyer']-p0*N
    fundamental_loss = N*(p0-v)
    allocation = bank['opening_equity']-equity+private_loss+public_loss
    need(allocation == fundamental_loss+interest+gain, 'Alder loss versus buyer transfer identity')
    need(w.cash['A'] == w.cash['B'] == 0, 'no unallocated intermediary cash')
    resources, recipients = w.initial+N*v, sum(w.cash.values())
    need(resources == recipients, 'all externally funded recipient cash, network claim cancels')
    COUNTS['line_journals'] += 1
    terminal = dict(unit_payoff=v, estate_available=estate, public_repayment=repaid,
                    public_loss=public_loss, public_cash_terminal=w.cash['public'],
                    private_due=total_claim, private_recovery_fraction=rate,
                    waiters_paid=wait_paid, runners_paid_late=late_run, network_paid_late=late[2],
                    private_claim_loss=private_loss, Alder_equity_terminal=equity,
                    runner_payoff_each=(sum(early)+late_run)/m if m else None,
                    waiter_payoff_each=wait_paid/(2-m) if m<2 else None,
                    buyer_gain=gain, waiting_interest_due=interest, buyer_initial_cash=p0*N,
                    buyer_cash_after_sale=p0*N-receipts, buyer_terminal_wealth=w.cash['buyer'],
                    fundamental_asset_loss=fundamental_loss, loss_attribution_residual=F(0),
                    estate_residual=F(0), consolidated_resources=resources,
                    consolidated_recipient_wealth=recipients, consolidated_resource_residual=F(0), beacon=beacon)
    return opening, terminal, payoff, enclosure


def resolution_journal(data, value):
    bank = numbers(data['bank'])
    w = Wallets(data)
    retail = w.exhaust('A', 'retail', bank['retail_due'])
    cash = w.cash['A']
    bridge = min(max(F(data['beacon']['customer_due'])-w.cash['B'], F(0)),
                 F(data['policy']['resolution_bridge_cap']))
    w.pay('public', 'B', bridge)
    customer_early = w.exhaust('B', 'customer', F(data['beacon']['customer_due']))
    v = F(value)
    w.cash['A'] += v*bank['asset_units']
    estate = w.cash['A']
    claims = [bank['funder_principal'], bank['funder_principal'], bank['network_due']]
    rate = min(F(1), estate/sum(claims))
    paid = [x*rate for x in claims]
    for target, amount in zip(('f0','f1','B'), paid):
        w.pay('A', target, amount)
    equity = w.cash['A']
    w.pay('A', 'A_equity', equity)
    beacon = beacon_end(data, w, (F(0), paid[2]), bridge, customer_early)
    resources, recipients = w.initial+v*bank['asset_units'], sum(w.cash.values())
    need(resources == recipients, 'resolution total includes funded bridge, not extra cash')
    COUNTS['resolution_journals'] += 1
    return dict(unit_payoff=v, retail_paid_cutoff1=retail, retained_cash=cash, assets_sold=F(0),
                Alder_estate_cutoff2=estate, restructured_principal_claims=sum(claims), pari_passu_fraction=rate,
                funders_paid_cutoff2=sum(paid[:2]), network_paid_cutoff2=paid[2],
                private_principal_loss=sum(claims)-sum(paid), Alder_equity_terminal=equity,
                cancelled_wait_premium_relative_to_WW=2*bank['funder_principal']*(bank['wait_multiplier']-1),
                estate_residual=F(0), beacon=beacon, public_cash_terminal=w.cash['public'],
                buyer_unused_cash=w.cash['buyer'], consolidated_resources=resources,
                consolidated_recipient_wealth=recipients, consolidated_resource_residual=F(0))


def strategic_oracle(payoffs):
    # Exhaust individual unilateral deviations in all four action profiles.
    strict_profiles, weak_profiles = [], []
    for profile in ('WW','RR','RW','WR'):
        gaps = []
        for i in range(2):
            other = list(profile)
            other[i] = 'W' if profile[i] == 'R' else 'R'
            gaps.append(payoffs[profile][i]-payoffs[''.join(other)][i])
        if all(x > BAND for x in gaps):
            strict_profiles.append(profile)
        if all(x >= -BAND for x in gaps):
            weak_profiles.append(profile)
    d0 = payoffs['RW'][0]-payoffs['WW'][0]
    d1 = payoffs['RR'][0]-payoffs['WR'][0]
    mixed = None
    if abs(d0)>BAND and abs(d1)>BAND and d0*d1<0:
        mixed = -d0/(d1-d0)
        need(0<mixed<1 and (1-mixed)*d0+mixed*d1==0, 'mixed indifference root')
    return dict(run_minus_wait_if_other_waits=d0, run_minus_wait_if_other_runs=d1,
                strict_pure_equilibria=strict_profiles, weak_pure_candidates_with_numeric_band=weak_profiles,
                symmetric_mixed_run_probability=mixed, near_indifference_unresolved=abs(d0)<=BAND or abs(d1)<=BAND,
                numerical_band=BAND)


def validate_case(run, data, label):
    before = copy.deepcopy(data)
    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        result = run(data)
    need(not stdout.getvalue() and not stderr.getvalue() and data==before, label+' quiet pure run API')
    need(strict(json.dumps(result, allow_nan=False))==result, label+' strict JSON output')
    need(set(result)=={'schema','provenance','line_alternatives','resolution_alternative','limits'}, label+' outer keys')
    need(result['schema']==data['schema']+'-output' and result['provenance']==data['provenance'], label+' provenance')
    need(all(x in result['limits'] for x in ('prepositioned taxpayer cash','pledged units','not assigned probabilities','policy optimum')),
         label+' explicit result limits')
    alternatives = result['line_alternatives']
    need(len(alternatives)==len(data['policy']['line_caps']), label+' alternative count')
    for j, cap in enumerate(data['policy']['line_caps']):
        alt = alternatives[j]
        need(set(alt)=={'line_cap','profiles','benchmark_game'} and len(alt['profiles'])==3, label+' profile structure')
        near(alt['line_cap'], F(cap), label+' cap')
        benchmark = {}
        for m, actions in enumerate(('WW','RW','RR')):
            p = alt['profiles'][m]
            opening, terminal, payoff, enclosure = line_journal(data, cap, actions, data['market']['benchmark_terminal_value'])
            compare(p['cutoff1'], opening, label+' cutoff1 '+str(j)+':'+actions)
            s = F(p['cutoff1']['sale_units'])
            need(enclosure[0]-F(1,10**39)<=s<=enclosure[1]+F(1,10**39), label+' serialized sale in rounding enclosure')
            benchmark[actions] = payoff
            if actions=='RW':
                benchmark['WR'] = list(reversed(payoff))
            need(set(p)=={'cutoff1','terminal_states'} and len(p['terminal_states'])==len(data['terminal_states']), label+' states')
            for i, state in enumerate(data['terminal_states']):
                if state['unit_payoff']==data['market']['benchmark_terminal_value']:
                    expected = dict(terminal)
                else:
                    _, expected, _, _ = line_journal(data, cap, actions, state['unit_payoff'])
                expected['label'] = state['label']
                compare(p['terminal_states'][i], expected, label+' terminal '+str(j)+':'+actions+':'+state['label'])
        game = dict(alt['benchmark_game'])
        scope = game.pop('scope')
        need(all(x in scope for x in ('not an empirical crisis frequency','no equilibrium selection','unresolved')), label+' game scope')
        compare(game, strategic_oracle(benchmark), label+' independently enumerated game '+str(j))
    wanted = [dict(label=s['label'], **resolution_journal(data,s['unit_payoff'])) for s in data['terminal_states']]
    compare(result['resolution_alternative'], wanted, label+' resolution')
    COUNTS['cases'] += 1
    return result


def financial_cases(base):
    single = edit(base, [(('policy','line_caps'), ['0']),
                         (('terminal_states',), [{'label':'benchmark','unit_payoff':'1'}])])
    specs = [
        ('flat_price', [(('market','impact'),'0')]),
        ('all_actions_indifferent', [(('market','impact'),'0'),(('bank','wait_multiplier'),'1')]),
        ('zero_wait_premium', [(('bank','wait_multiplier'),'1')]),
        ('known_downside_changes_game', [(('market','benchmark_terminal_value'),'0.6'),
            (('policy','line_caps'),['0','20','80']), (('terminal_states',),[{'label':'known','unit_payoff':'0.6'}])]),
        ('lower_advance', [(('policy','advance_fraction'),'0.5'),(('policy','line_caps'),['80'])]),
        ('funded_A_equity', [(('bank','cash'),'30'),(('bank','opening_equity'),'30')]),
        ('Beacon_own_cash', [(('beacon','cash'),'5'),(('beacon','opening_equity'),'15'),(('policy','line_caps'),['20'])]),
        ('partial_bridge', [(('policy','resolution_bridge_cap'),'3')]),
        ('no_bridge', [(('policy','resolution_bridge_cap'),'0')]),
        ('zero_public_budget', [(('policy','public_cash'),'0'),(('policy','resolution_bridge_cap'),'0')]),
        ('zero_terminal_assets', [(('policy','line_caps'),['20','80']),
            (('terminal_states',),[{'label':'worthless','unit_payoff':'0'}])]),
        ('exact_sale_capacity', [(('bank','funder_principal'),'16'),(('bank','opening_equity'),'50')]),
        ('funded_no_sale', [(('bank','cash'),'38'),(('bank','opening_equity'),'38')])]
    return [(name,edit(single,changes)) for name,changes in specs]


def intervention_assertions(results):
    def g(name, index=0): return results[name]['line_alternatives'][index]['benchmark_game']
    need(g('flat_price')['strict_pure_equilibria']==['WW'], 'flat auction removes run equilibrium in this contract')
    need(g('all_actions_indifferent')['strict_pure_equilibria']==[] and
         set(g('all_actions_indifferent')['weak_pure_candidates_with_numeric_band'])=={'WW','RR','RW','WR'} and
         g('all_actions_indifferent')['near_indifference_unresolved'] and
         g('all_actions_indifferent')['symmetric_mixed_run_probability'] is None,
         'null mixed output is not a denial of degenerate mixed equilibria')
    need(g('zero_wait_premium')['strict_pure_equilibria']==['RR'] and
         g('zero_wait_premium')['near_indifference_unresolved'], 'zero premium retains weak WW but strict RR')
    need(all(g('known_downside_changes_game',i)['strict_pure_equilibria']==['RR'] for i in range(3)),
         'known lower fundamental changes all three benchmark games')
    p = results['lower_advance']['line_alternatives'][0]['profiles'][2]
    near(p['cutoff1']['loan'],F(50),'lower advance binding loan')
    near(p['cutoff1']['free_units'],F(0),'fully pledged assets not sold')
    near(p['cutoff1']['runner_unpaid'],F(10),'cash shortfall despite later estate')
    near(p['terminal_states'][0]['network_paid_late'],F(20),'senior estate recourse then late private recovery')
    res = results['partial_bridge']['resolution_alternative'][0]
    near(res['beacon']['customer_missed_cutoff1'],F(7),'partial bridge leaves dated miss')
    near(res['beacon']['equity_terminal'],F(10),'later resolution recovery does not erase dated miss')
    near(results['no_bridge']['resolution_alternative'][0]['beacon']['customer_missed_cutoff1'],F(10),'stay produces no early cash')
    need(results['exact_sale_capacity']['line_alternatives'][0]['profiles'][2]['cutoff1']['sale_regime']=='exact_free_asset_boundary',
         'exact capacity is feasible equality')
    need(results['funded_no_sale']['line_alternatives'][0]['profiles'][0]['cutoff1']['sale_regime']=='no_sale',
         'funded opening cash creates no-sale branch')


class Fragment(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack=[]; self.ids=[]; self.links=[]; self.sources=[]; self.calc={}
        self.worked=0; self.exercises=0; self.solutions=0; self.active=None
    def handle_starttag(self, tag, attrs):
        a=dict(attrs)
        if 'id' in a: self.ids.append(a['id'])
        if tag=='a': self.links.append(a.get('href',''))
        if 'data-source' in a: self.sources.append(a['data-source'])
        classes=a.get('class','').split()
        if 'worked' in classes: self.worked+=1
        if tag=='li':
            if any('exercises' in c for _,c in self.stack): self.exercises+=1
            if any('solutions' in c for _,c in self.stack): self.solutions+=1
        if 'data-calc' in a:
            need(self.active is None and a['data-calc'] not in self.calc,'unique printed-value anchor')
            self.active=a['data-calc']; self.calc[self.active]=''
        if tag not in ('br','hr','img','meta','link','input'): self.stack.append((tag,classes))
    def handle_endtag(self, tag):
        if tag=='span': self.active=None
        need(bool(self.stack) and self.stack[-1][0]==tag,'balanced fragment '+tag)
        self.stack.pop()
    def handle_data(self, text):
        if self.active is not None: self.calc[self.active]+=text


def round6(value):
    sign='−' if value<0 else ''
    value=abs(value)*10**6
    nearest=(2*value.numerator+value.denominator)//(2*value.denominator)
    return sign+str(nearest//10**6)+'.'+str(nearest%10**6).zfill(6)


def printed_values(fragment, base):
    # These use peer wallets and independently derived analytic leverage formulas.
    rows=[line_journal(base,'0',a,'1') for a in ('WW','RW','RR')]
    o=[r[0] for r in rows]; t=[r[1] for r in rows]
    partial, part, _, _=line_journal(base,'20','RR','1')
    full=[line_journal(base,'80',a,'0.6') for a in ('WW','RW','RR')]
    rg,rd,rx=[resolution_journal(base,v) for v in ('1','0.6','0.1')]
    d0=rows[1][2][0]-rows[0][2][0]; d1=rows[2][2][0]-rows[1][2][1]
    q=F(9,10); equity=20+100*q-100
    s5=sum(sqrt_interval(F(5)))/2
    wanted={
        'maximum_receipts':F(50),'sale_zero':o[0]['sale_units'],'price_zero':o[0]['sale_price'],
        'wait_wait':t[0]['waiter_payoff_each'],'sale_one_rounded':round6(o[1]['sale_units']),
        'price_one_rounded':round6(o[1]['sale_price']),'wait_run_rounded':round6(t[1]['waiter_payoff_each']),
        'sale_two':o[2]['sale_units'],'price_two':o[2]['sale_price'],'equity_wait':t[0]['Alder_equity_terminal'],
        'run_run':t[2]['runner_payoff_each'],'mixed_rounded':round6(-d0/(d1-d0)),
        'belief_run':F(9,10)*rows[1][2][0]+F(1,10)*rows[2][2][0],
        'belief_wait_rounded':round6(F(9,10)*rows[0][2][0]+F(1,10)*rows[1][2][1]),
        'initial_leverage':F(120,20),'marked_equity_wait':equity,'prepayment_leverage':(20+100*q)/equity,
        'retained_mark':80*q,'postpayment_leverage':80*q/equity,'zero_equity_price':F(4,5),
        'zero_equity_sale':F(40),'zero_equity_receipts':F(32),'private_advance':F(4,5)*100*q,
        'pledged_partial':partial['pledged_units'],'sale_partial':partial['sale_units'],
        'price_partial':partial['sale_price'],'receipts_partial':partial['sale_proceeds'],
        'network_partial_early':partial['network_paid'],'beacon_partial_miss':part['beacon']['customer_missed_cutoff1'],
        'network_partial_late':part['network_paid_late'],'network_partial_total':partial['network_paid']+part['network_paid_late'],
        'beacon_partial_equity':part['beacon']['equity_terminal'],'buyer_partial_gain':part['buyer_gain'],
        'network_partial_loss':part['beacon']['network_asset_loss'],
        'full_line_draws':', '.join(str(x[0]['loan']) for x in full),'public_full_loss':full[2][1]['public_loss'],
        'public_full_cash':full[2][1]['public_cash_terminal'],'resolution_estate_good':rg['Alder_estate_cutoff2'],
        'resolution_claims':rg['restructured_principal_claims'],'resolution_estate_down':rd['Alder_estate_cutoff2'],
        'resolution_recovery':rd['pari_passu_fraction'],'resolution_funders_down':rd['funders_paid_cutoff2'],
        'resolution_network_down':rd['network_paid_cutoff2'],'resolution_private_loss':rd['private_principal_loss'],
        'resolution_beacon_equity':rd['beacon']['equity_terminal'],'resolution_network_deep':rx['network_paid_cutoff2'],
        'resolution_bridge_deep_loss':rx['beacon']['public_bridge_loss'],'cancelled_premium':rg['cancelled_wait_premium_relative_to_WW'],
        'marked_equity_one_rounded':round6(o[1]['principal_marked_equity']),
        'resolution_estate_deep':rx['Alder_estate_cutoff2'],'resolution_recovery_deep':rx['pari_passu_fraction'],
        'resolution_funders_deep':rx['funders_paid_cutoff2'],'nonmonotone_low_rounded':round6(50-10*s5),
        'nonmonotone_high_rounded':round6(50+10*s5),'nonmonotone_max':F(25)}
    need(set(fragment.calc)==set(wanted) and len(wanted)==55,'all 55 printed numerical anchors')
    for key, expected in wanted.items():
        text=fragment.calc[key].strip()
        if isinstance(expected,F): near(text.replace('−','-'),expected,'printed '+key)
        else: need(text==expected,'printed '+key)
    # Algebraic claims beyond the numerical anchors.
    need((100*(100*q-80)-100*(20+100*q))==-10000,'leverage derivative numerator')
    need(F(1,100)*50*50==25 and 100-F(1,100)*100**2==0,'excluded nonmonotone capacity counterexample')
    COUNTS['printed_values']=len(wanted)


def invalid_contracts(run, base):
    mutations=[(('schema',),'wrong'),(('provenance',),'unsupported'),(('bank','cash'),20),
        (('bank','cash'),True),(('bank','cash'),None),(('bank','cash'),'20e0'),
        (('bank','cash'),' 20'),(('bank','cash'),'+20'),(('bank','cash'),'020'),
        (('bank','cash'),'20.0000001'),(('bank','cash'),'NaN'),(('bank','cash'),'-1'),
        (('bank','cash'),'17'),(('bank','opening_equity'),'21'),(('beacon','opening_equity'),'9'),
        (('bank','asset_units'),'0'),(('bank','asset_units'),'1001'),(('bank','funder_principal'),'0'),
        (('bank','wait_multiplier'),'0.9'),(('bank','wait_multiplier'),'1.6'),
        (('market','intercept'),'0'),(('market','impact'),'0.01'),(('market','benchmark_terminal_value'),'11'),
        (('policy','advance_fraction'),'0'),(('policy','advance_fraction'),'1.1'),
        (('policy','line_caps'),[]),(('policy','line_caps'),['0','0.0']),
        (('policy','line_caps'),['81']),(('policy','line_caps'),['0','1','2','3','4']),
        (('policy','resolution_bridge_cap'),'81'),(('terminal_states',),[]),
        (('terminal_states',),[{'label':'duplicate','unit_payoff':'1'},{'label':'duplicate','unit_payoff':'0.1'}]),
        (('terminal_states',0,'label'),'../outside'),(('terminal_states',0,'unit_payoff'),'-0.1')]
    cases=[edit(base,[(path,value)]) for path,value in mutations]
    x=copy.deepcopy(base); del x['bank']['cash']; cases.append(x)
    x=copy.deepcopy(base); x['policy']['extra']=0; cases.append(x)
    for i, data in enumerate(cases):
        before=copy.deepcopy(data); out,err=io.StringIO(),io.StringIO()
        rejected=False
        with contextlib.redirect_stdout(out),contextlib.redirect_stderr(err):
            try: run(data)
            except (ValueError,TypeError,KeyError): rejected=True
        need(rejected and data==before and not out.getvalue() and not err.getvalue(), 'invalid contract '+str(i))
    COUNTS['api_invalid_rejections']=len(cases)


def bindings(root):
    def verify(row, path):
        payload=(root/path).read_bytes()
        need(len(payload)==row['bytes'] and hashlib.sha256(payload).hexdigest()==row['sha256'], 'binding '+path)
    manifest=strict((root/'content/projects/v11-c11-manifest.json').read_text())
    need(len(manifest['files'])==4 and {r['file'] for r in manifest['files']}==
         {'v11-c11-'+s for s in ('inputs.json','analysis.py','output.json','README.txt')}, 'manifest exact four')
    for row in manifest['files']: verify(row,'content/projects/'+row['file'])
    author=strict((root/'content/reviews/v11-c11-author.json').read_text())
    rows=author['reviewed_hashes']
    need(len(rows)==8 and {r['path'] for r in rows}==set(AUTHOR)-{'content/reviews/v11-c11-author.json'}, 'author exact eight nonself')
    for row in rows: verify(row,row['path'])
    peer=strict((root/REVIEW).read_text()); rows=peer['reviewed_hashes']
    need(len(rows)==10 and {r['path'] for r in rows}==set(AUTHOR)|{SELF}, 'peer exact nine authors plus checker')
    for row in rows: verify(row,row['path'])


def portable_cli(root, base, saved):
    env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    successes=invalids=aliases=0
    with tempfile.TemporaryDirectory(prefix='v11-c11-peer-') as temporary:
        folder=Path(temporary)
        model=folder/'v11-c11-analysis.py'; model.write_bytes((root/AUTHOR[2]).read_bytes())
        inp=folder/'v11-c11-inputs.json'; inp.write_bytes((root/AUTHOR[1]).read_bytes())
        default=folder/'v11-c11-output.json'
        protected={model:model.read_bytes(),inp:inp.read_bytes()}
        def call(args, optimized=False):
            return subprocess.run([sys.executable]+(['-O'] if optimized else [])+[str(model)]+args,
                                  cwd='/',env=env,capture_output=True,timeout=25)
        for optimized in (False,True):
            for destination in (None,folder/'explicit.json'):
                args=[] if destination is None else ['--input',str(inp),'--output',str(destination)]
                result=call(args,optimized)
                target=default if destination is None else destination
                need(result.returncode==0 and result.stdout==result.stderr==b'' and strict(target.read_text())==saved,
                     'portable quiet CLI generation '+str(optimized))
                successes+=1
            for path in (inp,model):
                for kind in ('direct','resolved','symbolic','hard'):
                    if kind=='direct': output=path
                    elif kind=='resolved':
                        (folder/'sub').mkdir(exist_ok=True)
                        output=folder/'sub'/'..'/path.name
                    else:
                        output=folder/(kind+'-'+path.name)
                        if output.exists() or output.is_symlink(): output.unlink()
                        if kind=='symbolic': output.symlink_to(path)
                        else: os.link(path,output)
                    result=call(['--input',str(inp),'--output',str(output)],optimized)
                    need(result.returncode!=0 and not result.stdout and result.stderr.startswith(b'error:') and
                         all(p.read_bytes()==data for p,data in protected.items()), 'protected output '+kind+' '+path.name)
                    if kind in ('symbolic','hard'): output.unlink()
                    aliases+=1
            # Default destination protection is also exercised, not just explicit --output.
            default.unlink(); default.symlink_to(inp)
            result=call([],optimized)
            need(result.returncode!=0 and not result.stdout and result.stderr.startswith(b'error:') and
                 all(p.read_bytes()==data for p,data in protected.items()), 'default output input alias')
            default.unlink(); aliases+=1
            invalid_bytes=[b'{"x":0,"x":1}',b'{"cash":NaN}',b'\xff',b' '*1000001,
                json.dumps(edit(base,[(('market','impact'),'0.01')])).encode()]
            for index, payload in enumerate(invalid_bytes):
                bad=folder/'invalid.json'; bad.write_bytes(payload)
                target=folder/'preserve.json'; target.write_bytes(b'preserve me\n')
                result=call(['--input',str(bad),'--output',str(target)],optimized)
                need(result.returncode!=0 and not result.stdout and result.stderr.startswith(b'error:') and
                     target.read_bytes()==b'preserve me\n' and bad.read_bytes()==payload,
                     'CLI invalid preserves existing destination '+str(index))
                invalids+=1
        need(all(p.read_bytes()==data for p,data in protected.items()),'all portable source bytes preserved')
    COUNTS.update(portable_cli_successes=successes,cli_invalid_rejections=invalids,protected_output_attempts=aliases)


def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    COUNTS.clear()
    COUNTS.update(comparisons=0,cases=0,root_certificates=0,funded_transfers=0,line_journals=0,resolution_journals=0)
    bindings(root)
    base=strict((root/AUTHOR[1]).read_text())
    out,err=io.StringIO(),io.StringIO()
    with contextlib.redirect_stdout(out),contextlib.redirect_stderr(err):
        module=runpy.run_path(str(root/AUTHOR[2]))
    need(not out.getvalue() and not err.getvalue(),'quiet model import')
    result=validate_case(module['run'],base,'baseline')
    saved=strict((root/AUTHOR[3]).read_text())
    need(result==saved,'saved output matches independently audited fresh calculation')
    results={name:validate_case(module['run'],data,name) for name,data in financial_cases(base)}
    intervention_assertions(results)
    fragment=Fragment(); manuscript=(root/AUTHOR[0]).read_text(); fragment.feed(manuscript); fragment.close()
    need(not fragment.stack and (fragment.worked,fragment.exercises,fragment.solutions)==(4,8,8),'complete reader fragment 4/8/8')
    need(len(fragment.ids)==len(set(fragment.ids)),'unique reader IDs')
    assets={'v11-c11-'+x for x in ('inputs.json','analysis.py','output.json','manifest.json','README.txt')}
    need(assets<=set(fragment.links) and not any(x.startswith('projects/') for x in fragment.links),'flat five downloadable assets')
    need(set(fragment.sources)=={'v11-c01-diamond-dybvig','v06-c12-us-crisis'},'exact scoped primary routes')
    source=strict((root/AUTHOR[8]).read_text())
    need(set(source['reused_source_ids'])==set(fragment.sources) and source['proposals']==[],'source proposals match cited scopes')
    printed_values(fragment,base)
    invalid_contracts(module['run'],base)
    portable_cli(root,base,saved)
    summary=dict(chapter='v11-c11',review='separate machine-assisted peer',status='passed',**COUNTS,
                 financial_interventions=len(results),worked_examples=4,solved_exercises=8,
                 author_bindings=9,peer_checker_bindings=1,
                 limits='Finite original contracts and bounded deterministic interventions; no empirical frequency, current legal power, global welfare optimum, rendered UI or human academic certification.')
    strict(json.dumps(summary,allow_nan=False))
    return summary


if __name__=='__main__':
    print(json.dumps(check(),indent=2,allow_nan=False))
