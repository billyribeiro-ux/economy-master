"""Independent financial checks for Lumen's original linked forecast."""
from contextlib import redirect_stdout
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
PROJECT = ROOT/'content/projects/v07-c10-analysis.py'


def need(condition, label):
    if not condition:
        raise AssertionError(label)


def eq(value, target, label):
    need(Q(value) == Q(target), label)


def independent_journal():
    """Fixed observed-case postings reconstructed independently of driver code."""
    ledger = {k:Q(v) for k,v in dict(cash=20,ar=40,inventory=30,ppe=110,
                                   ap=-25,term=-50,revolver=0,equity=-125).items()}
    snapshots = []
    for events in [
        [dict(ar=500,equity=-500),dict(cash=480,ar=-480),
         dict(inventory=360,ap=-360),dict(ap=349,cash=-349),
         dict(equity=325,inventory=-325),dict(equity=100,cash=-100),
         dict(equity=20,ppe=-20),dict(equity=5,cash=-5),dict(equity=10,cash=-10),
         dict(cash=44,revolver=-44),dict(ppe=50,cash=-50),dict(equity=10,cash=-10)],
        [dict(ar=600,equity=-600),dict(cash=588,ar=-588),
         dict(inventory=403,ap=-403),dict(ap='398.7',cash='-398.7'),
         dict(equity=390,inventory=-390),dict(equity=110,cash=-110),
         dict(equity=30,ppe=-30),dict(equity='9.4',cash='-9.4'),
         dict(equity='12.12',cash='-12.12'),dict(ppe=30,cash=-30),
         dict(equity=10,cash=-10),dict(revolver='17.78',cash='-17.78')]
    ]:
        for event in events:
            need(sum(Q(v) for v in event.values()) == 0, 'balanced independent entry')
            for k,v in event.items(): ledger[k] += Q(v)
            need(sum(ledger.values()) == 0, 'balanced journal prefix')
        snapshots.append(dict(ledger))
    return snapshots


def identities(row):
    c, o = row['closing'], row['opening']
    q = lambda key:Q(row[key])
    eq(q('cfo'), q('cash_receipts')-q('supplier_cash')-q('cash_opex')-q('interest')-q('tax'), 'external cash ledger')
    eq(q('cfo'), q('net_income')+q('depreciation')-q('nwc_change'), 'indirect cash')
    eq(Q(c['cash'])-Q(o['cash']), q('cfo')+q('cfi')+q('cff'), 'cash rollforward')
    eq(q('debt_change'), Q(c['revolver'])-Q(o['revolver']), 'debt rollforward')
    eq(Q(c['equity'])-Q(o['equity']), q('net_income')+q('cff')-q('debt_change'), 'equity rollforward')
    eq(Q(c['ppe'])-Q(o['ppe']), -q('cfi')-q('depreciation'), 'asset rollforward')
    eq(sum(Q(c[k]) for k in ['cash','receivables','inventory','ppe']),
       sum(Q(c[k]) for k in ['payables','term_debt','revolver','equity']), 'balance sheet')


class Fragment(HTMLParser):
    def __init__(self):
        super().__init__();self.stack=[];self.counts=[];self.ols=[];self.worked=0;self.links=[]
    def handle_starttag(self, tag, attrs):
        a=dict(attrs)
        if tag=='aside' and 'worked' in a.get('class','').split():self.worked+=1
        if tag=='a':self.links.append(a.get('href',''))
        if tag=='ol':self.ols.append(0)
        if tag=='li' and self.ols:self.ols[-1]+=1
        if tag not in ['br','hr','img','meta','link','input']:self.stack.append(tag)
    def handle_endtag(self, tag):
        need(self.stack and self.stack[-1]==tag,'HTML nesting '+tag);self.stack.pop()
        if tag=='ol':self.counts.append(self.ols.pop())


def check():
    spec=importlib.util.spec_from_file_location('lumen',PROJECT);lab=importlib.util.module_from_spec(spec)
    data=json.loads(PROJECT.with_name('v07-c10-inputs.json').read_text());quiet=io.StringIO()
    with redirect_stdout(quiet):spec.loader.exec_module(lab);report=lab.forecast(data)
    need(not quiet.getvalue(),'quiet API');json.dumps(report,allow_nan=False)
    need(report['status']=='feasible-at-annual-dates','baseline feasible')
    targets=[dict(revenue=500,cogs=325,purchases=360,cash_receipts=480,supplier_cash=349,
                  depreciation=20,ebit=55,interest=5,tax=10,net_income=40,nwc_change=44,cfo=16,cfi=-50,cff=34,debt_change=44),
             dict(revenue=600,cogs=390,purchases=403,cash_receipts=588,supplier_cash='398.7',
                  depreciation=30,ebit=70,interest='9.4',tax='12.12',net_income='48.48',nwc_change='20.7',cfo='57.78',cfi=-30,cff='-27.78',debt_change='-17.78')]
    for row, target, ledger in zip(report['rows'],targets,independent_journal()):
        identities(row)
        for key,value in target.items():eq(row[key],value,key)
        for key,account,sign in [('cash','cash',1),('receivables','ar',1),('inventory','inventory',1),('ppe','ppe',1),
                                 ('payables','ap',-1),('term_debt','term',-1),('revolver','revolver',-1),('equity','equity',-1)]:
            eq(row['closing'][key],sign*ledger[account],'journal closing '+key)
    checks=['Two independent signed journals,30 flow anchors and every stock/cash/equity reconciliation']
    slow=deepcopy(data);slow['years'][0]['receivables_sales']='1/5';failure=lab.forecast(slow)
    need(failure['status']=='funding-shortfall' and not failure['rows'],'failed year is not presented as feasible')
    for key,value in dict(net_income=40,cfo=-24,required_revolver=84,gap_to_minimum=24,cash_after_maximum_draw=-4).items():eq(failure['failure'][key],value,key)
    slow['years'][0]['dividend']=0;eq(lab.forecast(slow)['failure']['gap_to_minimum'],14,'dividend cut insufficient')
    slow['years'][0]['capex']=36;repair=lab.forecast(slow);need(repair['status']=='feasible-at-annual-dates','combined repair')
    for key,value in dict(revolver=60,ppe=126,equity=165,cash=20).items():eq(repair['rows'][0]['closing'][key],value,key)
    for row in repair['rows']:identities(row)
    quick=deepcopy(data);quick['years'][0]['receivables_sales']='1/10';q=lab.forecast(quick)
    eq(q['rows'][0]['cfo'],26,'faster collections');eq(q['rows'][0]['closing']['revolver'],34,'less borrowing')
    eq(q['rows'][1]['interest'],'8.4','next-year interest');eq(q['rows'][1]['net_income'],'49.28','next-year profit')
    cap=deepcopy(data);cap['years'][0]['capex']=40;d=lab.forecast(cap)
    for key,value in dict(depreciation=28,interest='8.4',net_income='50.88').items():eq(d['rows'][1][key],value,'delayed '+key)
    for candidate in [q,d]:
        for row in candidate['rows']:identities(row)
    checks.append('Collection shock, funding refusal, combined repair and propagated working-capital/capex/interest effects')
    closure=lambda vals:lab.average_debt_closure(*(Q(x) for x in vals))
    a=closure([-8,10,20,'1/10','1/5',50]);eq(a['required_debt'],40,'circular debt');eq(a['interest'],'2.5','mean interest');eq(a['cash'],20,'circular cash')
    b=closure([-8,10,20,'1/10','1/5',35]);need(not b['feasible'],'credit binds');eq(b['gap_at_limit'],'4.8','gap net of interest')
    e=closure([2,20,25,'1/10','1/5',50]);eq(e['required_debt'],'45.625','exercise6 debt');eq(e['interest'],'3.28125','exercise6 interest');eq(e['cash'],25,'exercise6 cash')
    eq(closure([2,20,25,'1/10','1/5',40])['gap_at_limit'],'5.4','exercise6 limit')
    zero=closure([80,30,20,'1/10','1/5',60]);eq(zero['required_debt'],0,'zero-debt branch');eq(zero['cash'],'48.8','full repayment retains interest-adjusted surplus')
    eq(44*Q('10.5')-400,62,'revenue effect');eq(Q(62,400),'0.155','revenue growth')
    eq(4*10+40*Q('.5')+4*Q('.5'),62,'interaction decomposition')
    eq(325+65-30+25-36,349,'purchases/exercise2');eq(349-(325-11),35,'inventory omission')
    eq(80-30,50,'exercise4 cash');eq(20-24-36+60,20,'exercise5 repair cash')
    eq(20+100+65+126,311,'exercise5 assets');eq(36+50+60+165,311,'exercise5 claims')
    # Same incorrect capex recognition can preserve the balance-sheet identity
    # while violating the external cash ledger; it must not be certified by A=L+E.
    wrong_indirect=0+20-44;wrong_direct=480-349-100-5
    eq(wrong_indirect,-24,'exercise7 wrong indirect');eq(wrong_direct,26,'exercise7 wrong direct')
    eq(285-(36+50+84+115),0,'balanced wrong case');eq(285-(36+50+34+115),50,'other route residual')
    eq(5-30+40,15,'annual cash');eq(30-5,25,'dated cash gap')
    checks.append('Average-interest positive/zero-debt branches, binding limit, all eight exercise answers and delayed check')
    for change in [('opening','equity',126),('policy','revolver_limit',-1),('policy','tax_rate',1),('policy','new_asset_life',0)]:
        bad=deepcopy(data);bad[change[0]][change[1]]=change[2]
        try:lab.forecast(bad)
        except ValueError:pass
        else:raise AssertionError('invalid contract accepted '+str(change))
    for key,value in [('old_asset_depreciation',111),('cash_opex',200),('receivables_sales','6/5'),('capex',50.0)]:
        bad=deepcopy(data);bad['years'][0][key]=value
        try:lab.forecast(bad)
        except ValueError:pass
        else:raise AssertionError('invalid contract accepted '+key)
    wrong=deepcopy(report['rows'][0]);wrong['cfo']='56'
    try:identities(wrong)
    except AssertionError:pass
    else:raise AssertionError('working-capital sign error not detected')
    checks.append('Eight meaningful input-domain failures and a wrong-cash result detected')
    html=(ROOT/'content/chapters/v07-c10.html').read_text();fragment=Fragment();fragment.feed(html)
    need(not fragment.stack and fragment.worked==3 and fragment.counts==[8,8],'chapter structure')
    need('Teach-back benchmark' in html and 'Delayed-check answer' in html,'answered retrieval')
    sources=json.loads((ROOT/'content/reviews/v07-c10-sources.json').read_text())
    need({s['id'] for s in sources}=={link.split('#')[1] for link in fragment.links if link.startswith('sources.html#')},'source coverage')
    for link in fragment.links:
        if link.startswith('v07-c10-'):need((PROJECT.parent/link).is_file(),'missing offline asset')
    with tempfile.TemporaryDirectory(prefix='lumen-check-') as temp:
        result=subprocess.run([sys.executable,str(PROJECT)],cwd=temp,capture_output=True,text=True,check=True)
    need(not result.stderr and json.loads(result.stdout)==report,'portable CLI')
    checks.append('Complete three-example/eight-solution fragment, scoped sources, local assets and portable quiet JSON API')
    return dict(chapter='v07-c10',status='passed',checks=checks,
                limitations=['Exact synthetic annual forecasts do not verify real assumptions, credit access or intrayear feasibility.',
                             'Tax-loss and complex recognition regimes are outside the supplied contract.',
                             'Visual/mobile/print UI QA remains pending.'])


if __name__=='__main__':print(json.dumps(check(),indent=2,allow_nan=False))
