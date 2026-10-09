"""Independent finite reconstructions and artifact gates for v10-c01.

Proof validity and the research critique require the recorded editorial review.
This checker guards arithmetic, domains and reproducibility, not market truth.
"""
from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
from datetime import date
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from io import StringIO
import json
import math
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
ASSETS=ROOT/'content/projects'
STEM='v10-c01-'


def require(condition,message):
    if not condition:raise AssertionError(message)


class Audit:
    def __init__(self):self.count=0;self.groups=[];self.rejected=0
    def eq(self,actual,expected,label):
        self.count+=1
        if isinstance(expected,F):actual=F(actual)
        require(actual==expected,f'{label}: {actual!r} != {expected!r}')
    def near(self,actual,expected,label):
        self.count+=1
        require(math.isfinite(actual) and abs(actual-expected)<=1e-10*max(1,abs(expected)),label)


def solve(matrix,rhs):
    """Full Gauss-Jordan solve, separate from author forward substitution."""
    rows=[[F(x) for x in a]+[F(y)] for a,y in zip(matrix,rhs)]
    for j in range(len(rows)):
        pivot=next(k for k in range(j,len(rows)) if rows[k][j])
        rows[j],rows[pivot]=rows[pivot],rows[j]
        scale=rows[j][j];rows[j]=[x/scale for x in rows[j]]
        for i in range(len(rows)):
            if i!=j:
                scale=rows[i][j];rows[i]=[x-scale*y for x,y in zip(rows[i],rows[j])]
    return [row[-1] for row in rows]


class Manuscript(HTMLParser):
    def __init__(self):
        super().__init__();self.stack=[];self.ids=[];self.links=[];self.worked=0;self.exercises=0;self.solutions=0
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if 'id' in a:self.ids.append(a['id'])
        if tag=='a':self.links.append(a.get('href',''))
        if tag=='aside' and 'worked' in a.get('class','').split():self.worked+=1
        if tag=='li' and self.stack and self.stack[-1][0]=='ol':
            if 'exercises' in self.stack[-1][1].get('class','').split():self.exercises+=1
            elif any(t=='details' and 'solutions' in at.get('class','').split() for t,at in self.stack):self.solutions+=1
        require(tag!='h1','chapter fragment must not duplicate generated h1')
        if tag not in ('br','hr','img','input','meta','link'):self.stack.append((tag,a))
    def handle_endtag(self,tag):
        require(self.stack and self.stack[-1][0]==tag,'unbalanced HTML '+tag);self.stack.pop()


def check():
    a=Audit();raw=json.loads((ASSETS/(STEM+'inputs.json')).read_text())
    preserved=json.loads((ASSETS/(STEM+'output.json')).read_text())
    captured=StringIO();original=deepcopy(raw)
    with redirect_stdout(captured),redirect_stderr(captured):
        model=runpy.run_path(str(ASSETS/(STEM+'analysis.py')))
        r=model['run'](raw)
    a.eq(captured.getvalue(),'','quiet import/run');a.eq(raw,original,'nonmutating API');a.eq(r,preserved,'complete reference output')
    json.dumps(r,allow_nan=False)
    a.groups.append('quiet nonmutating API and complete strict reference output')

    # Day counts independently sum month segments; invoice uses acquired face.
    elapsed=16+28+31+16;period=16+28+31+30+31+30+15
    a.eq(elapsed,91,'independent elapsed count');a.eq(period,181,'independent period count')
    for k,v in {'elapsed_days':elapsed,'coupon_period_days':period,'days_to_next_coupon':period-elapsed,'days_to_maturity':274}.items():a.eq(r['settlement'][k],v,k)
    s=r['settlement'];dirty=F(3)*F(49,50)+F(103)*F(47,50);ai=F(3*elapsed,period)
    for k,v in {'coupon':F(3),'dirty':dirty,'accrued':ai,'clean':dirty-ai,'invoice_dirty':2500*dirty,'invoice_accrued':2500*ai,'invoice_clean':2500*(dirty-ai)}.items():a.eq(s[k],v,'settlement '+k)
    a.eq(F(s['invoice_clean'])+F(s['invoice_accrued']),F(s['invoice_dirty']),'invoice components')
    a.eq(F(s['invoice_dirty'])-248000,F(1400),'worked cash budget gap')
    a.groups.append('dated settlement, exact accrual and full invoice')

    matrix=[[100,0,0],[4,104,0],[6,6,106]];prices=list(map(F,raw['bootstrap']['prices']))
    d=solve(matrix,prices);expected=[F(24,25),F(9,10),F(21,25)]
    a.eq(d,expected,'independent elimination discounts')
    a.eq(list(map(F,r['curve']['discounts'])),d,'all recovered discounts')
    transposed=[list(row) for row in zip(*matrix)]
    target=list(map(F,[5,5,105]));holdings=solve(transposed,target)
    a.eq(list(map(F,r['curve']['replicating_holdings'])),holdings,'independent transposed-system replica')
    fair=sum(cf*discount for cf,discount in zip(target,d))
    a.eq(fair,F(195,2),'target value')
    a.eq(sum(h*p for h,p in zip(holdings,prices)),fair,'actual instruments cost')
    for i in range(3):
        a.eq(sum(matrix[i][j]*d[j] for j in range(3)),prices[i],'observed price '+str(i))
        a.eq(sum(holdings[j]*matrix[j][i] for j in range(3)),target[i],'every replicated date '+str(i))
        a.near(r['curve']['annual_spots'][i],math.expm1(-math.log(float(d[i]))/(i+1)),'annual quote '+str(i))
        a.near(r['curve']['continuous_spots'][i],-math.log(float(d[i]))/(i+1),'continuous quote '+str(i))
    a.eq(r['curve']['quoted_target_minus_fair'],F(1,2),'arbitrage initial receipt')
    a.groups.append('independent full linear solves, repricing and replica cash')

    # Solve the quadratic algebraically rather than calling the bisection helper.
    price=F(8)*d[0]+108*d[1]
    gross=(8+math.sqrt(64+4*float(price)*108))/(2*float(price))
    y=r['yield_case'];a.eq(y['price'],price,'two-year coupon price')
    a.near(y['annual_ytm'],gross-1,'independent quadratic root')
    a.near(y['root_repricing'],float(price),'root cash closure')
    a.eq(y['terminal_wealth_actual_reinvestment'],F(116),'zero-rate coupon accumulation')
    a.near(y['annualized_terminal_growth'],math.sqrt(116/float(price))-1,'terminal CAGR')
    a.near(y['terminal_wealth_at_ytm_reinvestment'],float(price)*gross*gross,'coupon accumulation identity')
    a.eq(y['sale_price_at_year_one'],F(1080,11),'independent early price')
    a.eq(y['one_year_holding_return'],F(179,14421),'complete holding return')
    a.near((1+.08/2)**2-1,.0816,'periodic-effective conversion')
    a.near(2*math.log(1.04),.07844142630656266,'periodic-continuous conversion')
    a.groups.append('quadratic yield, dated IRR versus wealth and early sale')

    f=r['forward'];a.eq(f['gross_locked'],F(16,15),'forward from exact discounts')
    a.eq(f['receive_at_end'],F(64),'forward repayment')
    a.eq(f['initial_cost'],F(0),'initial forward net cost')
    a.eq(f['offered_lender_contract_value'],F(9,50),'offered contract present value')
    a.eq(f['offered_minus_locked_terminal'],F(1,5),'dated arbitrage final cash')
    a.eq(F(60)*d[0],F(64)*d[1],'zero portfolio budget')
    a.near(f['effective_annual_locked'],1/15,'annual forward quote')
    a.near(f['continuous_annual_locked'],math.log(16/15),'continuous forward quote')
    a.groups.append('forward replication, funding and offered-price inconsistency')

    # Every determinate exercise and all retention prompts.
    outstanding=F(400);cash=[]
    for principal in (100,150,150):
        cash.append(outstanding/F(20)+principal);outstanding-=principal
    a.eq(cash,[F(120),F(165),F(315,2)],'E1 contract amortization')
    pv=sum(cf*df for cf,df in zip(cash,d));wrong=sum(F(cf)*df for cf,df in zip((120,170,170),d))
    a.eq((pv,pv+2,wrong,wrong-pv),(F(396),F(398),F(411),F(15)),'E1 price, cash and error')
    e2_elapsed=(date(2024,5,15)-date(2024,2,15)).days;e2_period=(date(2024,8,15)-date(2024,2,15)).days
    a.eq((e2_elapsed,e2_period),(90,182),'E2 independent datetime counts')
    accrual=F(5,2)*F(e2_elapsed,e2_period)
    a.eq(accrual,F(225,182),'E2 coupon allocation')
    a.eq((F(496,5)+accrual)*1000,F(9139700,91),'E2 full invoice')
    a.eq(accrual-F(5)*F(90,365),F(45,13286),'E2 convention mismatch')
    changed=solve(matrix,[96,97,F('100.20')])
    a.eq(changed,[d[0],F(2329,2600),F(23157,27560)],'E3 quote perturbation')
    a.eq(sum(cf*df for cf,df in zip(target,changed)),F(268721,2756),'E3 target repricing')
    derivative=solve(matrix,[0,1,0]);a.eq(derivative,[F(0),F(1,104),-F(6,106*104)],'E3 full linear sensitivity')
    bad=solve(matrix,[96,F('97.44'),10]);a.eq(bad[2],-F(29,2650),'E4 negative discount')
    arb=[-F(3,52),-F(3,52),F(1)]
    a.eq([sum(arb[j]*matrix[j][i] for j in range(3)) for i in range(3)],[F(0),F(0),F(106)],'E4 every dated payoff')
    a.eq(sum(h*p for h,p in zip(arb,[96,F('97.44'),10])),-F(29,25),'E4 initial receipt')
    # The theorem is proved in prose. These cases guard its stated boundaries.
    for sample in ([F(0),F(108)],[F(8),F(108)],[F(5),F(5),F(105)]):
        p=sum(cf*df for cf,df in zip(sample,d));root=model['yield_root'](sample,p)
        a.near(sum(float(cf)/(1+root)**(i+1) for i,cf in enumerate(sample)),float(p),'E5 cash repricing')
        relevant=[float(d[i])**(-1/(i+1))-1 for i,cf in enumerate(sample) if cf]
        require(min(relevant)-1e-12<=root<=max(relevant)+1e-12,'E5 minimum/maximum spot bound')
    repayment=F(70)*d[0]/d[2];cheap=F(70)*F(21,20)**2
    a.eq((repayment,repayment-cheap,(repayment-cheap)*d[2]),(F(80),F(113,40),F(2373,1000)),'E6 future and present arbitrage cash')
    a.eq(F(70)*d[0],repayment*d[2],'E6 initial replication budget')
    a.near(math.sqrt(float(d[0]/d[2]))-1,.06904496764969759,'E6 annual rate')
    midpoint=math.exp((math.log(float(d[0]))+math.log(float(d[1])))/2)
    interp=r['interpolation'];a.eq(interp['price_per_100_linear'],F(93),'E7 linear discount price')
    a.near(interp['price_per_100_log_linear'],100*midpoint,'E7 log-linear price')
    a.near(interp['price_per_100_perturbed'],100*midpoint*math.exp(.005),'E7 distinct perturbation')
    for u in (1,1.5,2):
        logbase=(2-u)*math.log(float(d[0]))+(u-1)*math.log(float(d[1]))
        perturbed=math.exp(logbase+.02*(u-1)*(2-u))
        require(perturbed>0 and math.log(16/15)-.02*(3-2*u)>0,'E7 positive discount and forward')
        if u!=1.5:a.near(perturbed,float(d[int(u)-1]),'E7 exact endpoint')
    bill=r['bill'];bill_price=F(100)-F(100)*F(3,50)*F(1,2);gain=(100-bill_price)/bill_price
    for k,v in {'price':bill_price,'holding_gain':gain,'investment_simple_360':F(6,97),'investment_simple_365':F(73,1164),'incorrect_simple_yield_price':F(10000,103)}.items():a.eq(bill[k],v,'E8 '+k)
    a.near(bill['effective_annual_360'],float(F(591,9409)),'E8 effective annual')
    a.near(bill['continuous_annual_360'],2*math.log(100/97),'E8 continuous annual')
    a.eq((8+F(1080,11))/F('104.88')-1,F(179,14421),'E9 complete return')
    a.eq(3*F(99,100)+103*F(19,20),F(5041,50),'retention dirty')
    a.eq(F(5041,50)-F(6,5),F(4981,50),'retention clean')
    a.eq(F(99,100)/F(19,20),F(99,95),'retention forward')
    a.eq(F(100,101)-1,-F(1,101),'retention negative yield')
    a.groups.append('all nine determinate exercises and delayed retention; proof/critique separately reviewed')

    def change(edit):
        value=deepcopy(raw);edit(value);return model['run'](value)
    moved=change(lambda x:x['settlement'].__setitem__('settlement','2025-04-17'))
    a.eq(moved['settlement']['elapsed_days'],92,'one-day move')
    a.eq(moved['settlement']['dirty'],s['dirty'],'same supplied discount prices')
    a.eq(F(moved['settlement']['clean'])-F(s['clean']),-F(3,181),'clean offsets changed accrual')
    quote=change(lambda x:x['bootstrap']['prices'].__setitem__(1,'97'))
    a.eq(list(map(F,quote['curve']['discounts'])),changed,'independently solved changed prices')
    offered=change(lambda x:x['forward'].__setitem__('offered_effective_annual_rate','0.06'))
    a.eq(offered['curve'],r['curve'],'offered quote cannot change observed curve')
    a.eq(offered['forward']['offered_lender_contract_value'],-F(9,25),'unfavorable lender contract')
    reinvest=change(lambda x:x['yield_case'].__setitem__('reinvestment_rate','0.10'))
    a.eq(reinvest['yield_case']['terminal_wealth_actual_reinvestment'],F(584,5),'changed coupon accumulation')
    a.eq(reinvest['yield_case']['annual_ytm'],y['annual_ytm'],'reinvestment does not define IRR')
    negative=change(lambda x:x['bootstrap'].__setitem__('prices',['101','110.12','128.78']))
    a.eq(list(map(F,negative['curve']['discounts'])),[F(101,100),F(51,50),F(11,10)],'negative-rate discounts allowed')
    require(negative['yield_case']['annual_ytm']<0,'negative YTM accepted within domain')
    a.groups.append('five independent contract-consistent interventions')

    def reject(edit,label):
        x=deepcopy(raw);edit(x)
        try:model['run'](x)
        except ValueError:a.rejected+=1
        else:raise AssertionError('Invalid domain accepted: '+label)
    reject(lambda x:x['settlement'].__setitem__('face',True),'boolean amount')
    reject(lambda x:x['bill'].__setitem__('discount_rate',.06),'binary floating input')
    reject(lambda x:x['settlement'].__setitem__('settlement','2025-07-15'),'entitlement boundary')
    reject(lambda x:x['settlement'].__setitem__('settlement',True),'nondate')
    reject(lambda x:x['settlement'].__setitem__('maturity','2026-01-16'),'changed contract date')
    reject(lambda x:x['settlement']['discounts'].__setitem__(1,'0'),'zero settlement discount')
    reject(lambda x:x['bootstrap']['cashflows'][1].__setitem__(1,'105'),'contradictory observed contract')
    reject(lambda x:x['bootstrap']['prices'].__setitem__(2,'10'),'negative implied discount')
    reject(lambda x:x['bootstrap']['prices'].__setitem__(2,'11.16'),'zero implied discount')
    reject(lambda x:x['forward'].__setitem__('end_year',1),'invalid loan dates')
    reject(lambda x:x['forward'].__setitem__('start_year',True),'boolean date')
    reject(lambda x:x['forward'].__setitem__('offered_effective_annual_rate','-1'),'nonpositive gross quote')
    reject(lambda x:x['yield_case'].__setitem__('reinvestment_rate','-1'),'nonpositive accumulation factor')
    reject(lambda x:x['yield_case'].__setitem__('sale_yield_at_year_one','-1'),'sale yield boundary')
    reject(lambda x:x['bill'].__setitem__('days',365.0),'noninteger day count')
    reject(lambda x:x['bill'].__setitem__('quote_basis',365),'changed face-discount contract')
    def impossible_bill(x):x['bill']['days']=365;x['bill']['discount_rate']='0.999'
    reject(impossible_bill,'nonpositive bill price')
    reject(lambda x:x['settlement'].__setitem__('face','NaN'),'nonfinite string')
    reject(lambda x:x.__setitem__('extra',1),'unknown field')
    reject(lambda x:x.__setitem__('provenance','actual bond prices'),'false provenance')
    a.groups.append('economic, date, quotation and finite-input rejection boundaries')

    names=[STEM+x for x in ('inputs.json','analysis.py','output.json','README.txt')]
    manifest=json.loads((ASSETS/(STEM+'manifest.json')).read_text())
    a.eq([x['file'] for x in manifest['files']],names,'complete four-file manifest')
    for item in manifest['files']:
        payload=(ASSETS/item['file']).read_bytes();a.eq(len(payload),item['bytes'],'manifest bytes');a.eq(sha256(payload).hexdigest(),item['sha256'],'manifest SHA256')
    with tempfile.TemporaryDirectory(prefix='aster-bond-check-') as folder:
        base=Path(folder);bundle=base/'bundle';cwd=base/'other';bundle.mkdir();cwd.mkdir()
        for name in names:shutil.copy2(ASSETS/name,bundle/name)
        for flags in ([],['-O']):
            result=subprocess.run([sys.executable,'-I','-B']+flags+[str(bundle/(STEM+'analysis.py'))],cwd=cwd,capture_output=True,text=True,timeout=20)
            a.eq(result.returncode,0,'portable exit');a.eq(result.stderr,'','portable stderr');a.eq(json.loads(result.stdout),preserved,'portable complete JSON')
        path=cwd/'result.json';result=subprocess.run([sys.executable,'-I','-B',str(bundle/(STEM+'analysis.py')),'--input',str(bundle/(STEM+'inputs.json')),'--output',str(path)],cwd=cwd,capture_output=True,text=True,timeout=20)
        a.eq(result.returncode,0,'explicit paths exit');a.eq(result.stdout+result.stderr,'','quiet output-file mode');a.eq(json.loads(path.read_text()),preserved,'explicit file result')
    doc=Manuscript();doc.feed((ROOT/'content/chapters/v10-c01.html').read_text());doc.close()
    a.eq(doc.stack,[],'balanced chapter HTML');a.eq(len(doc.ids),len(set(doc.ids)),'unique anchors')
    a.eq((doc.worked,doc.exercises,doc.solutions),(4,10,10),'complete graduate example/exercise/solution structure')
    for name in names+[STEM+'manifest.json']:require(name in doc.links,'missing distributed link '+name)
    sources=json.loads((ROOT/'content/reviews/v10-c01-sources.json').read_text())
    for source in sources:require('sources.html#'+source['id'] in doc.links,'missing scoped source link')
    a.groups.append('manifest, isolated normal/optimized CLI, chapter structure and source routes')
    result={'chapter':'v10-c01','status':'passed','groups':len(a.groups),'comparisons':a.count,'domain_rejections':a.rejected,'group_names':a.groups,'worked_examples':doc.worked,'solved_exercises':doc.solutions,'limits':'Finite conditional arithmetic, file integrity and structure. Editorial proof/source/critique review is separate; no market authentication, human certification or visual UI QA.'}
    json.dumps(result,allow_nan=False);return result


if __name__=='__main__':print(json.dumps(check(),indent=2,allow_nan=False))
