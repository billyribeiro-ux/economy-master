#!/usr/bin/env python3
"""Independent calendar, accounting, finite-state and package checks for c10."""
import contextlib
import copy
from datetime import date, timedelta
from fractions import Fraction as F
from html.parser import HTMLParser
import io
import itertools
import json
import math
from pathlib import Path
import random
import runpy
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
PROGRAM=ROOT/'content/projects/v04-c10-panel.py'
DATA=ROOT/'content/projects/v04-c10-data.json'
CHAPTER=ROOT/'content/chapters/v04-c10.html'
SOURCES=ROOT/'content/reviews/v04-c10-sources.json'


def require(condition,message):
    if not condition:
        raise AssertionError(message)


def previous_calendar_month(text):
    year,month=map(int,text.split('-'))
    return (date(year,month,1)-timedelta(days=1)).strftime('%Y-%m')


def expect_error(function,*args):
    try:
        function(*args)
    except (ValueError,TypeError):
        return
    raise AssertionError('expected explicit invalid-input failure')


def expectation(values):
    return sum(values,F(0))/len(values)


def covariance(xs,ys):
    mx,my=expectation(xs),expectation(ys)
    return expectation([(x-mx)*(y-my) for x,y in zip(xs,ys)])


class Manuscript(HTMLParser):
    def __init__(self):
        super().__init__();self.worked=0;self.exercises=0;self.answers=0
        self.exercise_depth=0;self.solution=False;self.pre=False;self.buffer=[]
        self.snippets=[];self.links=[];self.sources=set();self.forbidden=[]
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag in {'h1','html','body'}:self.forbidden.append(tag)
        if tag=='aside' and attrs.get('class')=='worked':self.worked+=1
        if tag=='ol' and attrs.get('class')=='exercises':self.exercise_depth=1
        elif tag=='ol' and self.exercise_depth:self.exercise_depth+=1
        if tag=='details' and attrs.get('class')=='solutions':self.solution=True
        if tag=='li' and self.exercise_depth==1:self.exercises+=1
        if tag=='li' and self.solution:self.answers+=1
        if tag=='a':self.links.append(attrs.get('href',''))
        if attrs.get('data-source'):self.sources.add(attrs['data-source'])
        if tag=='pre':self.pre=True;self.buffer=[]
    def handle_endtag(self,tag):
        if tag=='ol' and self.exercise_depth:self.exercise_depth-=1
        if tag=='details':self.solution=False
        if tag=='pre':self.pre=False;self.snippets.append(''.join(self.buffer))
    def handle_data(self,value):
        if self.pre:self.buffer.append(value)


def check():
    checks=[];output=io.StringIO()
    with contextlib.redirect_stdout(output):mod=runpy.run_path(str(PROGRAM),run_name='c10_check')
    require(not output.getvalue(),'import must not print')
    original=DATA.read_bytes();data=json.loads(original);before=copy.deepcopy(data)
    report=mod['make_report'];base=report(data)
    require(data==before,'report mutated inputs')
    grid={(r['entity'],r['month']):r for r in base['grid']}
    # Independently construct lags using dates and scan input rows; no ordinal arithmetic.
    for record in base['grid']:
        key=(record['entity'],previous_calendar_month(record['month']))
        earlier=[r for r in data['sales'] if (r['entity'],r['month'])==key]
        expected=None
        if earlier:
            price=next(r['index'] for r in data['prices'] if r['month']==key[1])
            expected=F(100*earlier[0]['nominal_usd'],price)
        require(record['lag_real_usd']==expected,'calendar lag disagrees with independent date/row scan')
    for year in [1900,1999,2000,2023,2024,2099,2100]:
        for month in range(1,13):
            stamp=f'{year:04d}-{month:02d}'
            require(mod['month_text'](mod['month_number'](stamp)-1)==previous_calendar_month(stamp),'calendar rollover')
    require(grid['B','2024-02']['status']=='active_unreported' and grid['B','2024-03']['lag_real_usd'] is None,
            'missing active month must not compress time')
    require(grid['C','2024-01']['status']=='not_operating' and grid['D','2024-03']['status']=='not_operating',
            'nonoperation status')
    require(grid['A','2024-02']['real_growth']==F(1,10) and grid['A','2024-03']['real_growth']==F(1,11)
            and grid['C','2024-03']['real_growth']==0 and grid['D','2024-02']['real_growth']==F(-1,4), 'growth arithmetic')
    checks.append('All twelve grid lags agree with independent datetime predecessor/row-scan calculation; 84 rollover cases including leap years; missing/entry/exit statuses and growth')

    require([r['active_count'] for r in base['monthly']]==[3,4,3] and
            [r['observed_count'] for r in base['monthly']]==[3,3,3], 'active/observed denominators')
    require([r['observed_mean_real_usd'] for r in base['monthly']]==[F(700,3),F(710,3),F(200)],'monthly observed means')
    require([r['whole_roster_total_real_usd'] for r in base['monthly']]==[700,None,600], 'unknown aggregate propagation')
    require(base['observed_endpoint_mean_growth']==F(-1,7),'changing-composition growth')
    require(base['endpoint_cohort']=={'entities':['A','B'],'first_mean':F(150),'last_mean':F(150),'growth':F(0)},'endpoint cohort')
    require(base['complete_window_cohort']=={'entities':['A'],'first_mean':F(100),'last_mean':F(120),'growth':F(1,5)},'complete-window cohort')
    require(base['endpoint_total_decomposition']=={'continuing_change':F(0),'entry_contribution':F(300),'exit_contribution':F(-400),'total_change':F(-100)},'entry/exit accounting')
    rng=random.Random(10410)
    for _ in range(24):
        shuffled=copy.deepcopy(data)
        for key in ['sales','roster','prices','quarter']:rng.shuffle(shuffled[key])
        require(report(shuffled)==base,'record order affected report')
    removed=copy.deepcopy(data);removed['sales']=[r for r in removed['sales'] if (r['entity'],r['month'])!=('B','2024-03')]
    reduced=report(removed)
    require(reduced['monthly'][-1]['whole_roster_total_real_usd'] is None and
            reduced['endpoint_total_decomposition'] is None and reduced['endpoint_cohort']['entities']==['A'], 'coverage mutation')
    require(reduced['monthly'][-1]['observed_mean_real_usd']==210,'changed observed denominator')
    checks.append('Exact cohort and observed-population comparisons, closed-roster entry/exit identity, 24 shuffled-input invariance runs and missing-endpoint coverage mutation')

    q=base['quarter']
    require(q['nominal_sales_usd']==700 and q['real_sales_base_usd']==620 and
            q['incorrect_mean_index_deflation']==F(7000,11) and q['consistent_aggregate_index']==F(3500,31),'matched-period deflation')
    require(q['quarter_end_inventory']==9 and q['mean_observed_endpoint_inventory']==F(35,3), 'stock target')
    require(q['pooled_defect_rate']==F(11,60) and q['mean_monthly_defect_rate']==F(1,5), 'exposure aggregation')
    balances=[F(100)]
    for change in [F(1,10),F(-1,10),F(1,5)]:balances.append(balances[-1]*(1+change))
    require(balances==[100,110,99,F(594,5)] and q['compounded_return']==balances[-1]/100-1==F(47,250), 'sequential-return independent calculation')
    require(q['quarter_flow_usd']==120 and (F(101,100)**4-1)==F(4060401,100000000),'annualized flow/rate distinction')
    # The shipped program freezes January2024=100 and refuses misleading
    # rescaling. Separately verify the manuscript's valid hand rebasing math.
    rescaled=copy.deepcopy(data)
    for row in rescaled['prices']:row['index']*=2
    expect_error(report,rescaled)
    feb_base=[F(p*100,110) for p in [100,110,120]]
    require(feb_base==[F(1000,11),100,F(1200,11)] and
            [100*F(n)/p for n,p in zip([100,121,144],feb_base)]==[110,121,132], 'exercise 3 rebasing')
    require(F(144,100)/F(120,100)-1==F(1,5),'real/nominal exact ratio')
    ex4=copy.deepcopy(data)
    for row,d,v,inventory,r in zip(ex4['quarter'],[1,0,4],[5,15,20],[8,12,7],[500,0,-500]):
        row.update(defects=d,deliveries=v,end_inventory=inventory,return_bps=r)
    q4=report(ex4)['quarter']
    require(q4['pooled_defect_rate']==F(1,8) and q4['mean_monthly_defect_rate']==F(2,15) and
            q4['quarter_end_inventory']==7 and q4['compounded_return']==F(-1,400),'exercise 4 transfer values')
    checks.append('Independent sequential wealth calculation; exact monthly deflation versus aggregate shortcut, index rebasing, stock/rate/flow targets and exercise 3–4 transfer arithmetic')

    # Exhaustively enumerate all equally likely shock states. This checks laws
    # without reusing the program covariance or mean-variance formulas.
    states=list(itertools.product([-2,2],repeat=6))
    ys=[[10+F(e[t])+F(e[t-1],2) for t in range(1,6)] for e in states]
    columns=list(zip(*ys))
    require(all(expectation(list(col))==10 and covariance(col,col)==5 for col in columns), 'stationary marginal moments')
    require(all(covariance(columns[t],columns[t-1])==2 for t in range(1,5)), 'lag-one stationarity')
    require(covariance(columns[4],columns[2])==0,'lag-two moment')
    averages=[sum(row[:4])/4 for row in ys]
    require(covariance(averages,averages)==2==base['stipulated_law_moments']['average_variance'], 'four-period exact mean variance')
    verified=0
    for theta in [F(-1),F(-1,2),F(0),F(1,2),F(2)]:
        for n in range(1,7):
            model=copy.deepcopy(data);model['law'].update(ma_numerator=theta.numerator,ma_denominator=theta.denominator,average_length=n)
            results=report(model)['stipulated_law_moments']
            paths=itertools.product([-2,2],repeat=n+1)
            means=[sum((F(e[t])+theta*e[t-1] for t in range(1,n+1)),F(0))/n for e in paths]
            require(covariance(means,means)==results['average_variance'],'finite-state law parameter grid')
            verified+=1
    walk=[[sum(e[:t]) for t in range(1,6)] for e in itertools.product([-2,2],repeat=5)]
    require(covariance([r[4] for r in walk],[r[4] for r in walk])==20 and
            covariance([r[1] for r in walk],[r[4] for r in walk])==8,'random walk moments')
    pairs=list(itertools.product([-2,2],repeat=3))
    dt1=[3+e[1]-e[0] for e in pairs];dt2=[3+e[2]-e[1] for e in pairs]
    require(expectation(dt1)==3 and covariance(dt1,dt1)==8 and covariance(dt1,dt2)==-4,'differenced trend')
    require(math.isclose(math.sqrt(2),1.4142135623730951) and math.isclose(math.sqrt(5)/2,1.118033988749895),'SE values')
    checks.append('Exhaustive 64-state stationary MA law, 30 theta/window mean-variance grids, 32 random-walk paths and differenced-trend covariance enumeration')

    path=[F(0),F(1),F(0),F(-1),F(0)];den=sum(v*v for v in path)
    require(sum(path[t]*path[t-1] for t in range(1,5))/den==0 and
            sum(path[t]*path[t-2] for t in range(2,5))/den==F(-1,2),'sample ACF exercise')
    # Ten independent individual shocks +/-2 and a common shock +/-3.
    panel=list(itertools.product([-1,1],repeat=11))
    first=[3*s[0]+2*s[1] for s in panel]
    second=[3*s[0]+2*s[2] for s in panel]
    mean=[3*s[0]+F(2*sum(s[1:]),10) for s in panel]
    require(covariance(first,first)==13 and covariance(first,second)==9 and covariance(mean,mean)==F(47,5), 'shared-shock exact panel variance')
    require(F(13,10)<F(47,5),'iid variance understatement')
    require(F(100*121,110)==110 and F(110,90)-1==F(2,9),'delayed real change')
    delayed=list(itertools.product([-1,1],repeat=3))
    z1=[e[1]-e[0] for e in delayed];z2=[e[2]-e[1] for e in delayed]
    require(covariance(z1,z1)==2 and covariance(z1,z2)==-1,'delayed dependence')
    checks.append('Exact sample ACF, exhaustive 2,048-state shared-panel shock variance and delayed-check real-change/covariance answers')

    # Valid boundary reports must distinguish absence, zero and undefined ratios.
    zero=copy.deepcopy(data);zero['sales'][0]['nominal_usd']=0
    zg={(r['entity'],r['month']):r for r in report(zero)['grid']}
    require(zg['A','2024-02']['real_difference']==110 and zg['A','2024-02']['real_growth'] is None,'zero lag denominator')
    empty=copy.deepcopy(data);empty['sales']=[]
    er=report(empty)
    require(all(r['observed_mean_real_usd'] is None and r['whole_roster_total_real_usd'] is None for r in er['monthly']) and
            er['endpoint_cohort']['growth'] is None,'all active reports missing')
    zerorates=copy.deepcopy(data)
    for row in zerorates['quarter']:row.update(nominal_usd=0,defects=0,deliveries=0)
    zerorates['law']['shock_magnitude']=0
    zr=report(zerorates)
    require(zr['quarter']['consistent_aggregate_index'] is None and zr['quarter']['pooled_defect_rate'] is None and
            zr['quarter']['mean_monthly_defect_rate'] is None and zr['stipulated_law_moments']['rho1'] is None,'zero boundary diagnostics')
    require(zr['stipulated_law_moments']['average_variance']==0,'zero-shock law')
    checks.append('True-zero versus unknown lags; absent cohort and active-report totals; zero sales/exposure and degenerate-law undefined ratios')

    invalid=[]
    def mutation(path,value):
        bad=copy.deepcopy(data);target=bad
        for key in path[:-1]:target=target[key]
        target[path[-1]]=value;invalid.append(bad)
    mutation(['sales'],data['sales']+[data['sales'][0]])
    mutation(['roster'],data['roster']+[data['roster'][0]])
    mutation(['prices'],data['prices']+[data['prices'][0]])
    mutation(['prices',1,'month'],'2024-01')
    mutation(['prices',1,'index'],0)
    mutation(['prices'],data['prices'][:2])
    mutation(['sales',0,'entity'],'unknown')
    mutation(['sales',0,'month'],'2023-12')
    mutation(['sales',5,'month'],'2024-01')
    for value in [True,1.5,None,-1,1000000001]:mutation(['sales',0,'nominal_usd'],value)
    for value in ['2024-13','2024-00','24-01','2024-1','2024-01\n','1800-12',True]:mutation(['sales',0,'month'],value)
    mutation(['quarter',0,'defects'],11)
    mutation(['quarter',0,'return_bps'],-10001)
    mutation(['quarter',1,'month'],'2024-01')
    mutation(['law','ma_denominator'],0)
    mutation(['law','average_length'],0)
    mutation(['schema_version'],True)
    mutation(['window','end'],'2024-01')
    mutation(['roster',0,'active_through'],'2023-12')
    mutation(['units','price_index'],'')
    mutation(['units','nominal_sales'],'EUR per calendar month')
    mutation(['units','real_sales'],'February 2024 price USD per calendar month')
    mutation(['prices',0,'index'],200)
    shifted_window=copy.deepcopy(data)
    shifted_window['window']={'start':'2024-02','end':'2024-04'}
    invalid.append(shifted_window)
    for bad in invalid:expect_error(report,bad)
    with tempfile.TemporaryDirectory(prefix='v04-c10-') as tmp:
        folder=Path(tmp)
        valid=subprocess.run([sys.executable,str(PROGRAM)],cwd=folder,capture_output=True,text=True)
        require(valid.returncode==0 and not valid.stderr and json.loads(valid.stdout)==json.loads(json.dumps(base,default=mod['encode'])), 'CLI report / independent cwd')
        documents=[json.dumps(bad) for bad in invalid]+['{"schema_version":1,"schema_version":1}','{"x":NaN}','{broken']
        for optimized in [False,True]:
            prefix=[sys.executable]+(['-O'] if optimized else [])+[str(PROGRAM)]
            for i,document in enumerate(documents):
                target=folder/(str(i)+'.json');target.write_text(document)
                result=subprocess.run(prefix+[str(target)],capture_output=True,text=True)
                require(result.returncode!=0 and not result.stdout and 'longitudinal input error' in result.stderr,'invalid CLI must fail without report')
        bad=folder/'invalid-encoding.json';bad.write_bytes(b'\xff')
        for target in [bad,folder/'absent.json']:
            result=subprocess.run([sys.executable,str(PROGRAM),str(target)],capture_output=True,text=True)
            require(result.returncode!=0 and not result.stdout,'file/encoding failure')
    require(DATA.read_bytes()==original,'input bytes changed')
    checks.append(str(len(documents))+' invalid duplicate/date/schema/type/count/law files rejected under normal and optimized Python; valid CLI from other directory and read-only/file-error checks')

    parser=Manuscript();html=CHAPTER.read_text();parser.feed(html)
    require(not parser.forbidden and parser.worked==2 and parser.exercises==8 and parser.answers==8,'manuscript package counts')
    proposed=json.loads(SOURCES.read_text())
    require(parser.sources=={s['id'] for s in proposed},'source IDs')
    for link in parser.links:
        if link.startswith('v04-c10-'):require((ROOT/'content/projects'/link).is_file(),'flat download missing')
    require(len(parser.snippets)==1,'one displayed snippet expected')
    output=io.StringIO()
    with contextlib.redirect_stdout(output):exec(compile(parser.snippets[0],'c10 snippet','exec'),{})
    require(output.getvalue()=='None\n','calendar instructional snippet')
    require(all(label in html for label in ['Capability:','Prerequisite:','Teach-back','Delayed check','v04-c11.html']),'instructional gates')
    checks.append('Two worked examples, eight matched exercises/solutions, source proposals, flat downloads, executed calendar snippet and retention/successor gates')
    return {'chapter':'v04-c10','status':'passed','checks':checks,'limitations':[
        'Analytic derivations, economic targets and open-response criteria were reviewed separately; numerical checks do not prove arbitrary modified programs correct.',
        'Panel data and probability laws are synthetic. No empirical stationarity, population representativeness or causal performance is established.',
        'The bounded monthly laboratory does not infer roster truth, recover missing active sales or implement general inference/chain-index methods.',
        'Whole-library acceptance/integration remains with root; visual/mobile/print QA remains pending after prior browser-policy rejection.']}


if __name__=='__main__':print(json.dumps(check(),indent=2))
