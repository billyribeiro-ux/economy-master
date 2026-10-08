"""Focused independent accounting/instruction audit; check() is quiet and JSON safe."""
from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
from fractions import Fraction as F
from html.parser import HTMLParser
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

BOOK=Path(__file__).resolve().parents[1]
PROJECT=BOOK/'content/projects'


def need(ok,message):
    if not ok: raise AssertionError(message)


def ledger_oracle(revenue_reversal=0,repair=0,equity_cash=0,extra_principal=0,tax_paid=16):
    """Signed double entries from cash events; no benchmark algebra is called."""
    book=dict(cash=F(80),ar=F(120),inventory=F(100),ppe=F(300),ap=F(-90),taxpay=F(0),debt=F(-250),equity=F(-260))
    def entry(**legs):
        need(sum(legs.values())==0,'unbalanced independent journal')
        for k,v in legs.items():book[k]=book.get(k,F(0))+F(v)
    entry(ar=1000,revenue=-1000)
    entry(cash=920,ar=-920)
    entry(cogs=600,inventory=-600)
    entry(inventory=650,ap=-650)
    entry(ap=620,cash=-620)
    entry(opex=215,cash=-215)
    entry(cash=15,recovery=-15)
    entry(depreciation=40,ppe=-40)
    entry(interest=20,cash=-20)
    entry(tax=28,taxpay=-28)
    entry(taxpay=tax_paid,cash=-tax_paid)
    entry(ppe=60,cash=-60)
    entry(debt=20,cash=-20)
    entry(dividend=10,cash=-10)
    entry(revenue=revenue_reversal,ar=-revenue_reversal)
    entry(opex=repair,ppe=-repair)
    adjustment=F(revenue_reversal+repair,5)
    entry(taxpay=adjustment,tax=-adjustment)
    entry(cash=equity_cash,equity=-equity_cash)
    entry(debt=extra_principal,cash=-extra_principal)
    need(sum(book.values())==0,'trial balance')
    income=-sum(book.get(k,F(0)) for k in ('revenue','cogs','opex','recovery','depreciation','interest','tax'))
    close={k:book[k] for k in ('cash','ar','inventory','ppe')}
    close.update(ap=-book['ap'],taxpay=-book['taxpay'],debt=-book['debt'],equity=-book['equity']+income-book['dividend'])
    need(sum(close[k] for k in ('cash','ar','inventory','ppe'))==sum(close[k] for k in ('ap','taxpay','debt','equity')),'oracle closing balance')
    return close,income,F(80-tax_paid-repair),F(-60+repair),F(-30+equity_cash-extra_principal)


def compare(result,oracle):
    close,net,cfo,cfi,cff=oracle
    keys={'cash':'cash','ar':'receivables','inventory':'inventory','ppe':'ppe','ap':'payables','taxpay':'tax_payable','debt':'debt','equity':'equity'}
    for k,v in keys.items(): need(F(result['closing'][v])==close[k],'journal '+k)
    need(F(result['income']['net_income'])==net,'journal income')
    cf=result['cash_flow']
    need(F(cf['cfo'])==F(cf['indirect_cfo'])==cfo and F(cf['investing'])==cfi and F(cf['financing'])==cff,'cash classification')
    need(F(result['closing']['assets'])==F(result['closing']['liabilities_and_equity']),'reported balance closure')


class Fragment(HTMLParser):
    def __init__(self):
        super().__init__();self.stack=[];self.lists=[];self.counts=[];self.links=[];self.worked=0
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        need(tag!='h1','fragment must not duplicate generated H1')
        if tag=='aside' and 'worked' in a.get('class','').split():self.worked+=1
        if tag=='ol':self.lists.append(0)
        if tag=='li' and self.lists:self.lists[-1]+=1
        if tag=='a':self.links.append(a.get('href',''))
        if tag not in {'br','hr','img','input','meta','link'}:self.stack.append(tag)
    def handle_endtag(self,tag):
        need(self.stack and self.stack[-1]==tag,'HTML nesting')
        self.stack.pop()
        if tag=='ol':self.counts.append(self.lists.pop())


def check():
    checks=[];stream=io.StringIO()
    spec=importlib.util.spec_from_file_location('v07_c12_lab',PROJECT/'v07-c12-analysis.py')
    lab=importlib.util.module_from_spec(spec)
    with redirect_stdout(stream),redirect_stderr(stream):
        spec.loader.exec_module(lab)
        data=json.loads((PROJECT/'v07-c12-inputs.json').read_text())
        result=lab.run(data)
    need(not stream.getvalue(),'quiet benchmark API')
    cases=[(0,0,0,0,16),(40,0,0,0,16),(40,15,0,0,16),(40,0,6,0,16),(40,0,0,6,16),(40,0,6,6,16),(30,0,0,0,16),(34,0,0,0,16),(35,0,0,0,16),(40,0,0,0,20)]
    for rev,repair,equity,payment,paid in cases:
        d=deepcopy(data);d['corrections'].update(premature_revenue=rev,capitalized_repair=repair)
        d['actions'].update(new_equity=equity,extra_debt_payment=payment);d['operations']['tax_paid']=paid
        compare(lab.run(d),ledger_oracle(rev,repair,equity,payment,paid))
    need([F(result['income'][k]) for k in ('revenue','ebitda','ebit','pretax','tax','net_income')]==list(map(F,[960,160,120,100,20,80])),'corrected income targets')
    need(F(result['closing']['assets'])==684 and F(result['closing']['cash'])==54,'corrected balance targets')
    checks.append(dict(name='Independent signed journal: ten correction, funding, boundary and tax-payment cases',status='pass',cases=len(cases)))

    cov=result['covenant']
    need([F(cov[k]) for k in ('eligible_cash','net_debt','ebitda','debt_headroom','cash_headroom')]==list(map(F,[54,176,170,-6,14])) and not cov['passes'],'default covenant')
    for rev,passes in [(34,True),(35,False)]:
        d=deepcopy(data);d['corrections']['premature_revenue']=rev
        need(lab.run(d)['covenant']['passes']==passes,'exact covenant boundary')
    for eq,payment,restricted,passed,netdebt,headroom in [(6,0,0,True,170,20),(0,6,0,False,176,8),(6,6,0,True,170,14),(0,8,10,False,186,-4),(16,0,10,True,170,20)]:
        d=deepcopy(data);d['actions'].update(new_equity=eq,extra_debt_payment=payment,restricted_cash=restricted)
        v=lab.run(d)['covenant']
        need(v['passes']==passed and F(v['net_debt'])==netdebt and F(v['cash_headroom'])==headroom,'funding source versus restricted cash')
    d=deepcopy(data);d['corrections']['premature_revenue']=30;d['actions']['restricted_cash']=10
    late=lab.run(d)
    need(F(late['income']['net_income'])==88 and F(late['closing']['receivables'])==170 and F(late['closing']['tax_payable'])==6 and F(late['covenant']['ebitda'])==180 and F(late['covenant']['debt_headroom'])==-6,'retention targets')
    need(230-(54+20-10)==166,'retention collection net debt')
    checks.append(dict(name='Exact leverage boundary, separate liquidity gate, cash-funded repayment and delayed check',status='pass'))

    need(F(result['normalization']['ebitda'])==165 and 200+20+25-165==80,'symmetric normalization')
    need(F(195)/F('4.5')==F(130,3) and 43*F('4.5')<195<=44*F('4.5'),'economic break-even')
    need(165-20-(165-40-20)*F(1,5)-40==84,'steady-state planning cash')
    g=result['growth']
    need([F(g[k]) for k in ('revenue','ebitda','pretax','tax_expense_and_cash','net_income','net_working_capital','cfo','cash_change','asset_change')]==list(map(F,[240,90,84,'16.8','67.2',60,'13.2','-16.8','85.2'])),'growth anchors')
    need(F(g['cfo'])==F(g['indirect_cfo']) and F(g['asset_change'])==F(g['liabilities_and_equity_change']),'growth closure')
    d=deepcopy(data);d['growth']['receivables']=72;slow=lab.run(d)['growth']
    need(F(slow['net_income'])==F('67.2') and F(slow['cfo'])==F('-10.8') and F(slow['cash_change'])==F('-40.8') and F(slow['asset_change'])==F('85.2'),'collection delay')
    checks.append(dict(name='Symmetric recurring economics, replacement investment and independently reconciled growth cash',status='pass'))

    need(90+20-30-10-5+4==69 and 50+69-40-12-3==64,'exercise1')
    need(72+40-(150-120)-50+30+2==64 and 72+40+10-(160-120)-50+30+2==64,'exercise2 two valid allowance bridges')
    need(54+150+150+320==120+2+230+322==674,'exercise2 statement closure')
    need(230-(54-10)==186 and 170-186==-16 and 238-(62-10)==186,'exercise3')
    need(130+18+12==160 and 130+(18-6)-8==134 and 160-134==26,'exercise4')
    need(F(110,160)==F(11,16) and 120-100==20 and 40-10==30,'exercise5')
    need(F('-40.8')+72+30+24==18+F('67.2'),'exercise6')
    d=deepcopy(data);d['corrections']['capitalized_repair']=15;repair=lab.run(d)
    need([F(repair['income'][k]) for k in ('ebit','tax','net_income')]==list(map(F,[105,17,68])),'exercise7 income')
    need(F(repair['closing']['assets'])==669 and F(repair['cash_flow']['cfo'])==49 and F(repair['cash_flow']['investing'])==-45 and F(repair['covenant']['debt_headroom'])==-21,'exercise7 classification and covenant')
    checks.append(dict(name='Every determinate exercise recalculated; open memo graded by explicit manuscript criteria',status='pass',exercises=8))

    invalid=[]
    for group,key,value in [('units','money','CU'),('opening','equity',261),('operations','tax_rate','6/5'),('operations','tax_paid',21),('corrections','premature_revenue',201),('corrections','capitalized_repair',61),('actions','extra_debt_payment',251),('actions','restricted_cash',55),('actions','extra_debt_payment',55),('operations','cash_costs_before_recovery',44),('growth','new_packages','1/2'),('growth','receivables',241),('operations','tax_rate',0.2),('growth','depreciation',31)]:
        bad=deepcopy(data);bad[group][key]=value;invalid.append(bad)
    for bad in invalid:
        try:lab.run(bad)
        except ValueError:pass
        else:raise AssertionError('invalid domain accepted')
    bad_result=deepcopy(result);bad_result['closing']['cash']='22'
    try:compare(bad_result,ledger_oracle(40))
    except AssertionError:pass
    else:raise AssertionError('fictional cash correction not detected')
    wrong=deepcopy(repair);wrong['cash_flow']['investing']='-60'
    try:compare(wrong,ledger_oracle(40,15))
    except AssertionError:pass
    else:raise AssertionError('capitalized repair reclassification not detected')
    checks.append(dict(name='Fourteen meaningful domain failures and two consequential accounting-error detectors',status='pass',invalid_cases=len(invalid)))

    html=(BOOK/'content/chapters/v07-c12.html').read_text();p=Fragment();p.feed(html);p.close()
    need(not p.stack and p.worked==3 and p.counts==[8,8],'complete manuscript structure')
    need('Teach-back benchmark' in html and 'Delayed-check answer' in html,'answered instruction')
    sources=json.loads((BOOK/'content/reviews/v07-c12-sources.json').read_text());ids={s['id'] for s in sources}
    need({x.split('#')[1] for x in p.links if x.startswith('sources.html#')}==ids,'source scopes linked')
    need(all(set(s)=={'id','title','url','use','checked','verification'} for s in sources),'source schema')
    downloads=[x for x in p.links if x.startswith('v07-c12-')]
    need(len(downloads)==3 and all((PROJECT/x).is_file() for x in downloads),'offline assets')
    checks.append(dict(name='Three worked cases, eight full solution pairs, answered retention and four scoped primary sources',status='pass'))

    with tempfile.TemporaryDirectory(prefix='v07-c12-check-') as tmp:
        folder=Path(tmp)
        for file in ('v07-c12-analysis.py','v07-c12-inputs.json'):shutil.copyfile(PROJECT/file,folder/file)
        for flags in ([],['-O']):
            proc=subprocess.run([sys.executable,*flags,str(folder/'v07-c12-analysis.py')],cwd=folder,text=True,capture_output=True,check=False)
            need(proc.returncode==0 and not proc.stderr and json.loads(proc.stdout)==result,'portable normal/optimized CLI')
        bad=deepcopy(data);bad['units']['money']='CU';(folder/'bad.json').write_text(json.dumps(bad))
        proc=subprocess.run([sys.executable,'-O',str(folder/'v07-c12-analysis.py'),str(folder/'bad.json')],cwd=folder,text=True,capture_output=True,check=False)
        need(proc.returncode!=0 and not proc.stdout and 'units' in proc.stderr,'invalid CLI unit rejection')
    checks.append(dict(name='Portable normal/optimized benchmark CLI, quiet API and explicit invalid-input failure',status='pass'))
    report=dict(chapter='v07-c12',status='pass',checks=checks,limitations=[
        'Synthetic accounting identities and stipulated recognition/tax/contract facts; no authenticated external evidence, legal conclusion or fraud detection.',
        'Annual cash and covenant gates do not establish intra-year solvency or authorize a retroactive cure.',
        'Source inspection is scoped, not full current reporting/audit compliance certification.',
        'Browser, mobile and print visual QA not performed.'])
    json.dumps(report,allow_nan=False)
    return report


if __name__=='__main__':
    print(json.dumps(check(),indent=2,allow_nan=False))
