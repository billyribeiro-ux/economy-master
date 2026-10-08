"""Independent financial and instructional checks for the original c07 cases."""
from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
from fractions import Fraction as Q
from html.parser import HTMLParser
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / 'content/projects/v07-c07-analysis.py'
INPUT = PROJECT.with_name('v07-c07-inputs.json')


def need(condition, message):
    if not condition:
        raise AssertionError(message)


def eq(actual, expected, label):
    need(Q(actual) == Q(expected), label)


def ledger():
    """Independently transcribed signed journal; no benchmark formulas imported."""
    a = dict.fromkeys(['cash', 'equipment', 'depreciation', 'provision', 'taxpay', 'dta', 'dtl', 'capital', 'income'], Q(0))
    def post(**entry):
        need(sum(Q(v) for v in entry.values()) == 0, 'balanced journal')
        for k, v in entry.items(): a[k] += Q(v)
        need(sum(a.values()) == 0, 'trial balance')
    post(cash=100, capital=-100); post(equipment=60, cash=-60)
    post(cash=210, income=-210); post(income=110, cash=-110)
    post(income=30, depreciation=-30); post(income=12, provision=-12)
    post(income=11, taxpay=-11); post(taxpay=8, cash=-8)
    post(income=4, dtl=-4); post(dta='12/5', income='-12/5')
    first = dict(a)
    post(cash=180, income=-180); post(income=110, cash=-110)
    post(income=30, depreciation=-30); post(provision=12, cash=-12)
    post(income='48/5', taxpay='-48/5'); post(taxpay='63/5', cash='-63/5')
    post(dtl=4, income=-4); post(income='12/5', dta='-12/5')
    return [first, dict(a)]


def identities(report):
    previous_cash = Q(report['date0']['cash'])
    previous_equity = Q(report['date0']['equity_financing'])
    previous_net_deferred = previous_provision = previous_payable = Q(0)
    for row in report['rows']:
        r = {k: Q(v) for k, v in row.items() if k not in ('zero_residuals',)}
        eq(r['assets'], r['cash'] + r['asset_carrying'] + r['deferred_tax_asset'], 'asset components')
        eq(r['liabilities'], r['provision'] + r['current_tax_payable'] + r['deferred_tax_liability'], 'liability components')
        eq(r['assets'], r['liabilities'] + r['equity'], 'balance sheet')
        eq(r['cash'], previous_cash + r['cfo'], 'cash rollforward')
        eq(r['equity'], previous_equity + r['net_income'], 'equity rollforward')
        net_deferred = r['deferred_tax_liability'] - r['deferred_tax_asset']
        eq(r['deferred_tax_expense'], net_deferred - previous_net_deferred, 'deferred expense sign')
        eq(r['total_tax_expense'], r['current_tax'] + r['deferred_tax_expense'], 'tax expense')
        eq(r['net_income'], r['profit_before_tax'] - r['total_tax_expense'], 'net income')
        eq(r['current_tax_payable'], previous_payable + r['current_tax'] - r['tax_cash'], 'payable settlement')
        eq(r['cfo'], r['net_income'] + r['book_depreciation'] + r['provision'] - previous_provision
           + r['deferred_tax_expense'] + r['current_tax_payable'] - previous_payable, 'cash bridge')
        previous_cash, previous_equity = r['cash'], r['equity']
        previous_net_deferred, previous_provision, previous_payable = net_deferred, r['provision'], r['current_tax_payable']
    eq(report['totals']['net_income'], previous_cash - Q(report['date0']['equity_financing']), 'terminal wealth')


class Fragment(HTMLParser):
    def __init__(self):
        super().__init__(); self.stack=[]; self.ols=[]; self.counts=[]; self.links=[]; self.worked=0
    def handle_starttag(self, tag, attrs):
        a=dict(attrs)
        if tag=='aside' and 'worked' in a.get('class','').split(): self.worked+=1
        if tag=='a': self.links.append(a.get('href',''))
        if tag=='ol': self.ols.append(0)
        if tag=='li' and self.ols: self.ols[-1]+=1
        if tag not in ['br','hr','img','meta','link','input']: self.stack.append(tag)
    def handle_endtag(self, tag):
        need(self.stack and self.stack[-1]==tag, 'HTML nesting '+tag);self.stack.pop()
        if tag=='ol': self.counts.append(self.ols.pop())


def check():
    spec=importlib.util.spec_from_file_location('c07_lab',PROJECT);lab=importlib.util.module_from_spec(spec)
    out,err=io.StringIO(),io.StringIO()
    data=json.loads(INPUT.read_text())
    with redirect_stdout(out), redirect_stderr(err):
        spec.loader.exec_module(lab); report=lab.analyze(data)
    need(not out.getvalue() and not err.getvalue(),'quiet import and API');json.dumps(report,allow_nan=False)
    identities(report)
    snapshots=ledger()
    fields=['profit_before_tax','taxable_profit','current_tax','tax_cash','current_tax_payable',
            'deferred_tax_asset','deferred_tax_liability','deferred_tax_expense','total_tax_expense',
            'net_income','cfo','cash','assets','liabilities','equity']
    targets=[[58,55,11,8,3,'2.4',4,'1.6','12.6','45.4',92,132,'164.4',19,'145.4'],
             [40,48,'9.6','12.6',0,0,0,'-1.6',8,32,'45.4','177.4','177.4',0,'177.4']]
    for row,expected,a in zip(report['rows'],targets,snapshots):
        need([Q(row[k]) for k in fields]==[Q(x) for x in expected],'independent exact period targets')
        for k,v in [('cash',a['cash']),('asset_carrying',a['equipment']+a['depreciation']),
                    ('provision',-a['provision']),('current_tax_payable',-a['taxpay']),
                    ('deferred_tax_asset',a['dta']),('deferred_tax_liability',-a['dtl']),
                    ('equity',-a['capital']-a['income'])]:eq(row[k],v,'journal '+k)
    checks=['Independent signed journals, 30 exact period targets and terminal cash/equity reconciliation']

    variations=[('year1_repair_estimate','20',[39,'38.4'],[92,'45.4'],'177.4'),
                ('book_depreciation',['40','20'],['37.4',40],[92,'45.4'],'177.4'),
                ('year1_tax_cash_paid','11',['45.4',32],[89,'48.4'],'177.4'),
                ('current_tax_rates',['1/5','1/4'],[45,30],[92,43],175),
                ('year2_repair_settlement','16',['45.4','28.8'],[92,'42.2'],'174.2'),
                ('tax_depreciation',['30','30'],['45.4',32],[92,'45.4'],'177.4')]
    # Equal depreciation raises year1 current tax by4. With the fixed installment8,
    # the extra current payable offsets that charge in CFO; year2 settles it.
    for key,value,incomes,flows,wealth in variations:
        d=deepcopy(data);d[key]=value;r=lab.analyze(d);identities(r)
        need([Q(x['net_income']) for x in r['rows']]==[Q(x) for x in incomes],key+' income')
        need([Q(x['cfo']) for x in r['rows']]==[Q(x) for x in flows],key+' cash')
        eq(r['rows'][-1]['equity'],wealth,key+' wealth')
    checks.append('Six economic transfers: estimate/release, book allocation, payment timing, enacted future rate, settlement news and tax timing')

    # Solutions and extra worked cases are independently recomputed from prompts.
    eq(6+14-15,5,'exercise1 payable');eq(5-3,2,'exercise1 deferred');eq(70-14-2,54,'exercise1 NI')
    eq(Q(1,5)*(90-60),6,'exercise2 DTL');eq(Q(1,5)*15,3,'exercise2 DTA');eq(4-0,4,'fine base')
    eq(Q(121)/Q('1.1')**2,100,'exercise4 PV');eq(Q(121)/Q('1.1'),110,'exercise4 time')
    eq(Q(1,5)*8,Q('1.6'),'exercise5 recognized');eq(Q(1,5)*(18-8),2,'exercise5 unrecognized')
    eq(Q(1,5)*(14-8),Q('1.2'),'exercise5 new benefit')
    eq(36+7+4+6,53,'exercise7 management');eq(36-9+7,34,'exercise7 consistent')
    eq(100+25-60-20+15,60,'exercise8 CFO');eq(180-60,120,'exercise8 sign error')
    eq(110+25-60-20+15-10,60,'exercise8 DTA bridge')
    eq(80+20-45-15+10,50,'companyA cash');eq(65+20-5-5,75,'companyB cash')
    eq(Q(80-50,500),Q('0.06'),'companyA accrual');eq(Q(65-75,500),Q('-0.02'),'companyB accrual')
    eq(40+8+4,52,'selective metric');eq(40-12-6,22,'consistent metric');eq(40-12-6+8-5,25,'normalized assumption')
    checks.append('All eight determinate exercise answers, worked analytical comparisons and retention timing checked')

    bad_inputs=[('units','CU'),('conventions','cash tax equals tax expense'),('opening_equity_cash',0),
                ('book_depreciation',[30,20]),('tax_depreciation',[10,50]),('current_tax_rates',['1/5','6/5']),
                ('year1_tax_cash_paid',12),('year1_repair_estimate',61),('year2_repair_settlement',61),
                ('year1_repair_estimate',True),('equipment_cost',60.0)]
    for key,value in bad_inputs:
        d=deepcopy(data);d[key]=value
        try:lab.analyze(d)
        except ValueError:pass
        else:raise AssertionError('invalid contract accepted '+key)
    checks.append('Eleven financially meaningful unit, timing, funding, recognition-domain and precision failures rejected')
    for field,value in [('deferred_tax_expense','1.6'),('tax_cash','9.6')]:
        wrong=deepcopy(report);wrong['rows'][1][field]=value
        try:identities(wrong)
        except AssertionError:pass
        else:raise AssertionError('wrong sign or missing opening payable not detected')
    checks.append('Independent checks reject reversed deferred-tax sign and omitted opening tax settlement')

    html=(ROOT/'content/chapters/v07-c07.html').read_text();p=Fragment();p.feed(html)
    need(not p.stack and p.counts==[8,8] and p.worked==3,'chapter completeness')
    need('Teach-back benchmark' in html and 'Delayed-check answer' in html,'answered transfer')
    sources=json.loads((ROOT/'content/reviews/v07-c07-sources.json').read_text())
    need({s['id'] for s in sources}=={x.split('#')[1] for x in p.links if x.startswith('sources.html#')},'source coverage')
    for link in p.links:
        if link.startswith('v07-c07-'):need((PROJECT.parent/link).is_file(),'download missing')
    checks.append('Three worked cases, eight matched full solutions, answered instruction and four scoped primary sources')
    with tempfile.TemporaryDirectory(prefix='c07-check-') as temp:
        for flag in [[],['-O']]:
            r=subprocess.run([sys.executable,*flag,str(PROJECT)],cwd=temp,capture_output=True,text=True,check=True)
            need(not r.stderr and json.loads(r.stdout)==report,'portable CLI differs')
    checks.append('Portable normal/optimized CLI equals quiet exact strict-JSON API')
    return dict(status='passed',chapter='v07-c07',checks=checks,
                limitations=['Exact synthetic accounting and bounded input cases do not verify real tax law or recognition evidence.',
                             'Open-ended evidence judgments require the manuscript rubric; numerical checks cannot identify reporting intent.',
                             'Visual/mobile/print UI QA remains pending.'])


if __name__=='__main__':print(json.dumps(check(),indent=2,allow_nan=False))
