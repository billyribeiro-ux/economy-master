#!/usr/bin/env python3
"""Independent exact financial checks for the bounded v07-c06 teaching cases."""
import contextlib
from copy import deepcopy
from fractions import Fraction as F
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PROJECTS = ROOT / 'content/projects'


def require(condition, label):
    if not condition:
        raise AssertionError(label)


def value(obj, *keys):
    for key in keys:
        obj = obj[key]
    return F(obj)


def equal(actual, expected, label):
    require(F(actual) == F(expected), f'{label}: {actual} != {expected}')


def group_oracle(report, case):
    """External-flow/resource calculation for the fixed opening-company case.

    Intentionally independent of benchmark Ledger/group; covers changes in
    ownership, acquisition price, sold fraction, settlement and dividends only.
    Other baseline primitives are fixed and checked by the input contract below.
    """
    a, price = F(case['ownership']), F(case['consideration'])
    f = case['post']
    z, k, d, dp = (F(f[x]) for x in ('batch_fraction_sold_outside','intercompany_cash_settlement','sub_dividend','parent_dividend'))
    p_cash = 290-price+k+a*d-dp
    s_cash = 20+200*z-k-d
    p_profit, s_profit = 50+a*d, 140*z-20
    total_profit = 10+160*z
    nci_profit = (1-a)*s_profit
    parent_profit = total_profit-nci_profit
    goodwill = price-160*a
    expected = {
        'parent': {'profit': p_profit, 'assets': p_cash+200+price+60-k,
                   'liabilities': 100, 'equity': 400+p_profit-dp},
        'subsidiary': {'profit': s_profit, 'assets': s_cash+160+60*(1-z),
                       'liabilities': 100-k, 'equity': 160+s_profit-d},
        'consolidated': {'revenue': 80+200*z, 'cogs': 40*z, 'operating_expense': 70,
                         'profit': total_profit, 'parent_profit': parent_profit, 'nci_profit': nci_profit,
                         'assets': p_cash+s_cash+400-40*z+goodwill, 'liabilities': 140,
                         'parent_equity': 400+parent_profit-dp, 'nci': (1-a)*(160+s_profit-d),
                         'total_equity': 560-160*a+total_profit-dp-(1-a)*d,
                         'cfo_post_acquisition': -30+200*z, 'financing_post_acquisition': -dp-(1-a)*d},
        'acquisition': {'cash': 340-price, 'assets': 700-160*a, 'liabilities': 140,
                        'parent_equity': 400, 'nci': (1-a)*160, 'goodwill': goodwill,
                        'net_acquisition_cash_outflow': price-40}}
    for section, fields in expected.items():
        for key, target in fields.items():
            equal(report[section][key], target, f'{section}.{key}')
    equal(report['parent']['ledger']['cash'], p_cash, 'parent cash')
    equal(report['subsidiary']['ledger']['cash'], s_cash, 'sub cash')
    g = report['consolidated']
    for key,target in {'cash': p_cash+s_cash, 'inventory': 80-40*z, 'external_receivables':20,'land':300,'goodwill':goodwill}.items():
        equal(g['assets_by_account'][key],target,key)
    for key,target in {'investment':price,'intra_balance':60-k,'intra_sales':60,'parent_dividend_income':a*d,'unrealized_inventory_margin':20*(1-z)}.items():
        equal(g['eliminations'][key],target,key)
    for label, residual in g['residuals'].items():
        equal(residual,0,label)
    for entity in ('parent','subsidiary'):
        equal(report[entity]['balance_residual'],0,entity+' balance')
        for row in report[entity]['journal']:
            equal(sum(F(x) for x in row['debit_minus_credit'].values()),0,'journal balance')
            require(F(row['cash_after']) >= 0,'company cash timing')
    equal(sum(F(x) for x in report['acquisition']['elimination_debit_minus_credit'].values()),0,'acquisition entry')


def check():
    checks = []
    source = PROJECTS / 'v07-c06-analysis.py'
    data = json.loads((PROJECTS / 'v07-c06-inputs.json').read_text())
    spec = importlib.util.spec_from_file_location('v07_c06_benchmark', source)
    module = importlib.util.module_from_spec(spec)
    capture = io.StringIO()
    with contextlib.redirect_stdout(capture):
        spec.loader.exec_module(module)
        baseline = module.analyze(data)
    require(capture.getvalue() == '', 'import and API must be quiet')
    json.dumps(baseline, allow_nan=False)
    require(baseline == json.loads((PROJECTS/'v07-c06-output.json').read_text()), 'preserved output exact')
    checks.append('Quiet exact-rational API and preserved baseline output agree')

    # Pin the independent oracle's scope; metadata and irrelevant prose are not hashes.
    expected_parent = dict(cash='300',land='200',external_liabilities='100',share_capital='300',retained='100')
    expected_sub = dict(cash='40',external_receivables='20',inventory='40',land='100',external_liabilities='40',share_capital='100',retained='60')
    require(data['group']['parent_opening']==expected_parent and data['group']['sub_opening']==expected_sub,'oracle opening-company contract')
    for key,target in {'parent_service_cash':'80','parent_operating_cash':'50','batch_external_cost':'40','batch_transfer_price':'60','outside_revenue_if_entire_batch_sold':'200','sub_operating_cash':'20'}.items():
        equal(data['group']['post'][key],target,'fixed oracle primitive')
    group_oracle(baseline['group'],data['group'])
    checks.append('Independent external-resource and cash oracle matches acquisition, both companies, group, NCI and all eliminations')

    s = baseline['shares']
    for key,target in {'profit':30,'net_owner_cash':0,'assets':230,'liabilities':80,'equity':150,'apic_total':F(145,2),'issued':125,'outstanding':110,'treasury_shares':15}.items():
        equal(s[key],target,'shares.'+key)
    for key,target in {'cash':80,'other_assets':150,'liabilities':-80,'capital':F(-125,2),'apic_issue':F(-135,2),'apic_treasury':-5,'retained':-60,'treasury':45}.items():
        equal(s['ledger'][key],target,'share ledger.'+key)
    for row,cash in zip(s['journal'],[100,130,120,60,80,80,80]):
        equal(row['cash_after'],cash,'share cash prefix')
        equal(sum(F(x) for x in row['debit_minus_credit'].values()),0,'share entry')
    require(len(s['journal'])==7,'share posting count')
    for snap,(issued,treasury,fraction) in zip(s['share_snapshots'],[(125,0,F(8,25)),(125,0,F(8,25)),(125,0,F(8,25)),(125,20,F(8,21)),(125,15,F(4,11))]):
        equal(snap['issued'],issued,'issued count')
        equal(snap['treasury_shares'],treasury,'treasury count')
        equal(snap['observer_fraction'],fraction,'observer ownership')
    require(all(F(v)==0 for v in s['residuals'].values()), 'share residuals')
    checks.append('Juniper account balances, seven cash/posting prefixes and five ownership snapshots independently matched')

    low = deepcopy(data)
    low['shares']['events'] += [dict(date='X1-11-01',kind='reissue',shares='5',price='2'),dict(date='X1-12-01',kind='reissue',shares='5',price='1')]
    low_report = module.analyze(low)['shares']
    for key,target in {'assets':245,'equity':165,'outstanding':120,'profit':30,'apic_total':F(135,2)}.items():
        equal(low_report[key],target,'below-cost '+key)
    for key,target in {'cash':95,'retained':-50,'treasury':15,'apic_treasury':0}.items():
        equal(low_report['ledger'][key],target,'below-cost account '+key)
    full = deepcopy(data)
    full['shares']['events'][-1]['shares']='20'
    full_report=module.analyze(full)['shares']
    for key,target in {'equity':210,'outstanding':125,'treasury_shares':0,'apic_total':F(175,2)}.items():
        equal(full_report[key],target,'full reissue '+key)
    checks.append('Below-cost reissues exhaust treasury APIC then debit RE without a profit loss; full reissue removes treasury')

    probes = []
    for z in ('0','1/2','1'):
        for a,price in (('3/4','150'),('1','200'),('2/5','100')):
            d=deepcopy(data)
            d['group']['ownership'],d['group']['consideration']=a,price
            d['group']['post']['batch_fraction_sold_outside']=z
            if z=='0':
                d['group']['post']['intercompany_cash_settlement']='0'
                d['group']['post']['sub_dividend']='0'
            probes.append(d)
    for k in ('0','60'):
        d=deepcopy(data);d['group']['post']['intercompany_cash_settlement']=k;probes.append(d)
    d=deepcopy(data);d['group']['post']['sub_dividend']='0';probes.append(d)
    for d in probes:
        group_oracle(module.analyze(d)['group'],d['group'])
    checks.append(f'{len(probes)} meaningful group sensitivities: zero/full sale, full/minority ownership with stipulated control, settlement and dividends')

    # All determinate exercise/retention anchors independently solved as exact arithmetic.
    require((60+40+12-7,90+40+12-7)==(105,135),'exercise 1')
    require(F(80)*(F(240)+20*F(5,2))/100-240==-8,'exercise 3 transfer')
    require((F(150)+50-160,580+10,400+50)==(40,590,450),'exercise 4 full goodwill')
    require((200-60-20,280-40-70,F(120,4),170-30)==(120,170,30,140),'exercise 5 full outside sale')
    require((40+60-12,F(60-12,4),88-F(60-12,4),88-F(60,4))==(88,12,76,73),'exercise 6 directions')
    require((165+75,400+F(155,2)-20,40+F(25,2))==(240,F(915,2),F(105,2)),'exercise 7 dividend')
    require(50+F(3,10)*20-F(3,10)*8==F(268,5),'exercise 8 equity method')
    require(300-(150-40)+70-20-4==236 and 177+15+59-15==236,'retention cash/perimeter')
    checks.append('All eight solution numerical targets and delayed-check arithmetic independently recomputed; conceptual scope reviewed separately')

    # A balanced but wrong consolidation must not pass the independent oracle.
    mutations=[]
    wrong=deepcopy(baseline['group']);wrong['consolidated']['revenue']='155';mutations.append(wrong)
    wrong=deepcopy(baseline['group']);wrong['consolidated']['nci_profit']='10';mutations.append(wrong)
    wrong=deepcopy(baseline['group']);wrong['consolidated']['assets']='656';mutations.append(wrong)
    wrong=deepcopy(baseline['group']);wrong['consolidated']['assets_by_account']['cash']='248';mutations.append(wrong)
    for wrong in mutations:
        try:
            group_oracle(wrong,data['group'])
        except AssertionError:
            pass
        else:
            raise AssertionError('oracle accepted financially wrong report')
    checks.append('Oracle rejects four deliberately wrong reports: scaled revenue, wrong NCI, retained margin and internal dividend cash')

    invalid=[]
    def bad_group(key,val):
        d=deepcopy(data);d['group'][key]=val;invalid.append(d)
    bad_group('control_stipulated',False);bad_group('business_stipulated',False)
    bad_group('ownership','0');bad_group('ownership','5/4');bad_group('consideration','100');bad_group('consideration','301')
    for key,val in [('batch_fraction_sold_outside','3/2'),('intercompany_cash_settlement','61'),('sub_dividend','100'),('batch_transfer_price','30')]:
        d=deepcopy(data);d['group']['post'][key]=val;invalid.append(d)
    d=deepcopy(data);d['shares']['events'][-1]['shares']='21';invalid.append(d)
    d=deepcopy(data);d['shares']['events'][3]['price']='10';invalid.append(d)
    d=deepcopy(data);d['shares']['events'][0]['price']='1/4';invalid.append(d)
    d=deepcopy(data);d['group']['ownership']=True;invalid.append(d)
    for d in invalid:
        try:
            module.analyze(d)
        except (ValueError,KeyError,TypeError):
            pass
        else:
            raise AssertionError('invalid financial contract accepted')
    checks.append(f'{len(invalid)} consequential invalid cases rejected: classification scope, ownership, funding, inventory, share rights and exact numeric type')

    for optimized in (False,True):
        command=[sys.executable]+(['-O'] if optimized else [])+[str(source)]
        completed=subprocess.run(command,cwd='/tmp',capture_output=True,text=True,check=False)
        require(completed.returncode==0 and not completed.stderr,'portable CLI')
        require(json.loads(completed.stdout)==baseline,'normal/optimized CLI exact output')
    html=(ROOT/'content/chapters/v07-c06.html').read_text()
    require(html.count('class="worked"')>=3 and html.count('<ol class="exercises">')==1,'worked/exercise structure')
    from html.parser import HTMLParser
    class Count(HTMLParser):
        def __init__(self):
            super().__init__();self.mode=None;self.counts={'exercises':0,'solutions':0};self.in_details=False
        def handle_starttag(self,tag,attrs):
            a=dict(attrs)
            if tag=='details' and a.get('class')=='solutions':self.in_details=True
            if tag=='ol' and a.get('class')=='exercises':self.mode='exercises'
            elif tag=='ol' and self.in_details:self.mode='solutions'
            if tag=='li' and self.mode:self.counts[self.mode]+=1
        def handle_endtag(self,tag):
            if tag=='ol':self.mode=None
            if tag=='details':self.in_details=False
    parser=Count();parser.feed(html)
    require(parser.counts=={'exercises':8,'solutions':8},'eight matching exercises and solutions')
    for name in ('inputs.json','analysis.py','output.json','README.txt'):
        require(f'href="v07-c06-{name}"' in html,'flat download link')
    require('Teach-back' in html and 'Delayed-check answers' in html,'answered retention')
    sources=json.loads((ROOT/'content/reviews/v07-c06-sources.json').read_text())
    require(len(sources)==6 and all(x['id'].startswith('v07-c06-') and x['verification'] for x in sources),'scoped source records')
    checks.append('Portable normal/optimized CLI, four flat downloads, four worked cases, eight solution pairs and answered retention')
    files=['content/chapters/v07-c06.html','content/projects/v07-c06-inputs.json','content/projects/v07-c06-analysis.py','content/projects/v07-c06-output.json','content/projects/v07-c06-README.txt','content/reviews/v07-c06-sources.json']
    return {'status':'passed','checks':checks,'counts':{'group_sensitivities':len(probes),'invalid_contracts':len(invalid),'wrong_report_mutations':len(mutations),'exercises':8},
            'sha256':{f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in files},
            'limitations':['Financial arithmetic and stated model contracts only; actual control, valuation, legal distributability and complete standards compliance are not established.','No visual/browser/print QA or external human certification.','Independent parameter oracle fixes the stated opening balances and core operating primitives; it is not a generic consolidation engine.']}


if __name__=='__main__':
    print(json.dumps(check(),indent=2,allow_nan=False))
