#!/usr/bin/env python3
"""Independent checks for original v07-c11 comparison cases; standard library."""
import contextlib
from copy import deepcopy
from fractions import Fraction as F
import hashlib
from html.parser import HTMLParser
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
PROJECTS=ROOT/'content/projects'


def require(condition,label):
    if not condition:raise AssertionError(label)


def equal(actual,expected,label):
    require(F(actual)==F(expected),f'{label}: {actual} != {expected}')


def inventory_oracle(report,case):
    """Independently expand the small integer-quantity test lots into unit costs.

    Uses slicing of physical cost lists, outside cash flows and net assets;
    does not use benchmark layer consumption or its accounting residuals.
    Test scope is integer quantities in original/probe cases, not all API inputs.
    """
    def units(lots):
        result=[]
        for lot in lots:
            q=F(lot['quantity'])
            require(q.denominator==1,'integer-unit oracle scope')
            result += [F(lot['unit_cost'])]*int(q)
        return result
    old_reserve=F(0)
    profits={m:F(case['opening_retained']) for m in ('FIFO','LIFO')}
    stocks={m:units(case['opening_layers']) for m in ('FIFO','LIFO')}
    cash=F(case['opening_cash'])
    for index,p in enumerate(case['periods']):
        purchases=units(p['purchases'])
        q=F(p['sold'])
        require(q.denominator==1,'integer sold scope')
        sold=int(q)
        revenue=sold*F(p['sale_price'])
        cfo=revenue-sum(purchases,F(0))-F(p['operating_cash'])
        purchase_cash=cash-sum(purchases,F(0))
        sale_cash=purchase_cash+revenue
        cash+=cfo
        expected={}
        for method in ('FIFO','LIFO'):
            opening=sum(stocks[method],F(0))
            all_costs=stocks[method]+purchases
            split=sold if method=='FIFO' else len(all_costs)-sold
            used=all_costs[:split] if method=='FIFO' else all_costs[split:]
            stocks[method]=all_costs[split:] if method=='FIFO' else all_costs[:split]
            cogs=sum(used,F(0));inv=sum(stocks[method],F(0))
            profit=revenue-cogs-F(p['operating_cash'])
            profits[method]+=profit
            equity=F(case['share_capital'])+profits[method]
            expected[method]={'cogs':cogs,'closing_inventory':inv,'profit':profit,'equity':equity}
            row=report['bases'][method][index]
            targets={'opening_inventory':opening,'purchases':sum(purchases,F(0)),
                     'revenue':revenue,'cogs':cogs,'profit':profit,
                     'closing_inventory':inv,'closing_quantity':len(stocks[method]),
                     'inventory_change':inv-opening,'closing_cash':cash,'cfo':cfo,
                     'cash_after_purchase':purchase_cash,'cash_after_sale':sale_cash,
                     'assets':cash+inv,'liabilities':F(case['liabilities']),
                     'retained':profits[method],'equity':equity}
            for key,target in targets.items():equal(row[key],target,method+' '+key)
            require(cash+inv-F(case['liabilities'])==equity,'independent net assets')
            require(all(F(v)==0 for v in row['residuals'].values()),'reported residuals')
        reserve=expected['FIFO']['closing_inventory']-expected['LIFO']['closing_inventory']
        bridge=report['common_FIFO_bridge'][index]
        for key,target in {'opening_reserve':old_reserve,'closing_reserve':reserve,
                           'reserve_change':reserve-old_reserve,'cogs_adjustment':old_reserve-reserve,
                           'profit_adjustment':reserve-old_reserve,'equity_adjustment':reserve,'cash_adjustment':0}.items():
            equal(bridge[key],target,'reserve bridge '+key)
        old_reserve=reserve


def asset_oracle(report,case):
    """Closed cumulative-depreciation functions, independent of yearly recursion."""
    c,r=F(case['cost']),F(case['residual'])
    old,elapsed,left,correct=(case[k] for k in ('original_life','elapsed_years','revised_remaining_life','correct_original_life'))
    annual=(c-r)/old
    value_at_change=c-elapsed*annual
    new_annual=(value_at_change-r)/left
    error_annual=(c-r)/correct
    for name,rows in report['schedules'].items():
        def cumulative(year):
            if name=='original':return min(year,old)*annual
            if name=='corrected_history':return min(year,correct)*error_annual
            return min(year,elapsed)*annual+min(max(year-elapsed,0),left)*new_annual
        for year,row in enumerate(rows,1):
            before,after=cumulative(year-1),cumulative(year)
            equal(row['opening_asset'],c-before,'asset opening')
            equal(row['closing_asset'],c-after,'asset closing')
            equal(row['depreciation'],after-before,'asset expense')
            equal(row['profit'],F(case['cash_profit_before_depreciation'])-(after-before),'asset income')
            equal(F(row['profit'])+F(row['depreciation']),row['cfo'],'asset CFO')
        equal(rows[-1]['closing_asset'],r,'residual value bound')
    targets={'original_start_revision_asset':value_at_change,'revised_annual_depreciation':new_annual,
             'corrected_start_revision_asset':c-elapsed*error_annual,'corrected_annual_depreciation':error_annual,
             'earliest_comparative_opening_equity_correction':(elapsed-1)*(annual-error_annual),
             'last_comparative_profit_correction':annual-error_annual,
             'cumulative_prior_asset_equity_correction':elapsed*(annual-error_annual),
             'prior_correction_cash':0,'prior_correction_in_discovery_profit':0}
    for key,target in targets.items():equal(report[key],target,key)


def check():
    checks=[]
    source=PROJECTS/'v07-c11-analysis.py'
    data=json.loads((PROJECTS/'v07-c11-inputs.json').read_text())
    spec=importlib.util.spec_from_file_location('v07_c11_benchmark',source)
    module=importlib.util.module_from_spec(spec)
    out,err=io.StringIO(),io.StringIO()
    with contextlib.redirect_stdout(out),contextlib.redirect_stderr(err):
        spec.loader.exec_module(module)
        result=module.analyze(data)
    require(not out.getvalue() and not err.getvalue(),'quiet import/API')
    json.dumps(result,allow_nan=False)
    require(result==json.loads((PROJECTS/'v07-c11-output.json').read_text()),'preserved baseline exact')
    inventory_oracle(result['inventory'],data['inventory'])
    # Independent prompt anchors make accidental changes to both data/code visible.
    for method,targets in {'FIFO':[(260,240,260,720,960,860,220),(280,360,170,770,1130,1030,50)],
                           'LIFO':[(340,160,180,720,880,780,220),(360,200,90,770,970,870,50)]}.items():
        for row,target in zip(result['inventory']['bases'][method],targets):
            for key,v in zip(('cogs','closing_inventory','profit','closing_cash','assets','equity','cfo'),target):equal(row[key],v,'baseline '+key)
    checks.append('Quiet strict-JSON API and preserved output; independent unit-cost, external-cash and net-asset baseline oracle')

    inventory_probes=[]
    liquid=deepcopy(data)
    liquid['inventory']['periods'].append({'period':'X3','purchases':[],'sold':'90','sale_price':'5','operating_cash':'50'})
    inventory_probes.append(liquid)
    equal_cost=deepcopy(data)
    for p in equal_cost['inventory']['periods']:p['purchases'][0]['unit_cost']='2'
    inventory_probes.append(equal_cost)
    falling=deepcopy(data)
    falling['inventory']['periods'][0]['purchases'][0]['unit_cost']='1/2'
    falling['inventory']['periods'][1]['purchases'][0]['unit_cost']='1/4'
    inventory_probes.append(falling)
    no_sales=deepcopy(data)
    no_sales['inventory']['periods']=no_sales['inventory']['periods'][:1]
    no_sales['inventory']['periods'][0]['sold']='0'
    inventory_probes.append(no_sales)
    for probe in inventory_probes:inventory_oracle(module.analyze(probe)['inventory'],probe['inventory'])
    lr=module.analyze(liquid)['inventory']
    for method,profit in [('FIFO',40),('LIFO',200)]:
        row=lr['bases'][method][-1]
        for key,target in {'profit':profit,'cfo':400,'closing_cash':1170,'closing_inventory':0,'assets':1170,'equity':1070}.items():equal(row[key],target,'liquidation '+key)
    equal(lr['common_FIFO_bridge'][-1]['reserve_change'],-160,'reserve release')
    checks.append('Four economic inventory transfers: liquidation, identical costs, falling costs and zero sales preserve the correct stock/flow/cash bridges')

    asset_oracle(result['asset'],data['asset'])
    for key,target in {'original_start_revision_asset':80,'revised_annual_depreciation':F(80,3),'corrected_start_revision_asset':60,'corrected_annual_depreciation':30,'cumulative_prior_asset_equity_correction':-20,'earliest_comparative_opening_equity_correction':-10,'last_comparative_profit_correction':-10}.items():equal(result['asset'][key],target,'machine '+key)
    asset_probes=[]
    for left in (1,4,7):
        probe=deepcopy(data);probe['asset']['revised_remaining_life']=left;asset_probes.append(probe)
    residual=deepcopy(data)
    residual['asset'].update(cost='150',residual='30',revised_remaining_life=2,cash_profit_before_depreciation='90')
    asset_probes.append(residual)
    for probe in asset_probes:asset_oracle(module.analyze(probe)['asset'],probe['asset'])
    ex4=module.analyze(residual)['asset']
    equal(ex4['original_start_revision_asset'],110,'exercise4 carrying')
    equal(ex4['revised_annual_depreciation'],40,'exercise4 new expense')
    equal(ex4['schedules']['new_estimate'][2]['profit'],50,'exercise4 profit')
    checks.append('Independent cumulative-depreciation oracle, comparative opening/current split, four remaining-life/residual cases and cash invariance')

    s=result['segments']
    for key,target in {'segment_revenue_sum':540,'segment_profit_sum':90,'external_revenue':500,'operating_expenses':440,'operating_profit':60,'profit_before_tax':52,'net_income':39,'assets':330}.items():equal(s[key],target,'segment '+key)
    require(s['cfo'] is None,'missing cash evidence must remain unknown')
    require([F(x['profit']) for x in s['segments']]==[54,36],'baseline segment profit split')
    moved=deepcopy(data)
    moved['segments']['items'][0]['internal_revenue']='50'
    moved['segments']['items'][1]['significant_expenses']['cost_category']='90'
    moved['segments']['internal_expense_included']='50'
    ms=module.analyze(moved)['segments']
    require([F(x['profit']) for x in ms['segments']]==[64,26],'changed segment profit split')
    for key in ('external_revenue','operating_expenses','operating_profit','profit_before_tax','net_income','assets'):equal(ms[key],s[key],'matched transfer invariance '+key)
    checks.append('Segment expenses, revenue/profit/asset reconciliation, matched internal-price invariance and honest missing-CFO state')

    purchases=F(260)-120+140
    fifo_cogs=(120+30)+purchases-(140+45)
    require((purchases,fifo_cogs,70+45-30)==(280,245,85),'exercise2 reserve')
    require(70-(140-120)==85-(185-150)==50,'exercise2 CFO')
    require((80-10,80-10,160-20,80-20,100-30)==(70,70,140,60,70),'exercise5 error')
    require((340-260-54,200-130-36,90-40-20-10-8)==(26,34,12),'exercise6 diagnose wrong PBT')
    require(F(252,240)-1==F(168,160)-1==F(420,400)-1==F(1,20),'exercise7 recast growth')
    require(F(252,260)-1==F(-2,65) and F(168,140)-1==F(1,5),'unrecast growth')
    require(F(660-100-20,500)-1==F(2,25),'exercise8 perimeter/currency')
    require(F(540*52,53)==F(28080,53) and F(540*52,53*500)-1==F(79,1325),'exercise8 conditional calendar')
    checks.append('All determinate exercise/retention targets checked; source-judgment questions separately reviewed against explicit criteria')

    # Financially wrong outputs should fail independently, even if internally labeled.
    wrong_reports=[]
    wrong=deepcopy(result['inventory']);wrong['bases']['FIFO'][1]['profit']='250';wrong_reports.append(wrong)
    wrong=deepcopy(result['inventory']);wrong['bases']['FIFO'][1]['closing_cash']='930';wrong_reports.append(wrong)
    wrong=deepcopy(result['inventory']);wrong['common_FIFO_bridge'][1]['profit_adjustment']='160';wrong_reports.append(wrong)
    for wrong in wrong_reports:
        try:inventory_oracle(wrong,data['inventory'])
        except AssertionError:pass
        else:raise AssertionError('independent oracle accepted a financially wrong adjustment')
    wrong_asset=deepcopy(result['asset']);wrong_asset['prior_correction_in_discovery_profit']='-20'
    try:asset_oracle(wrong_asset,data['asset'])
    except AssertionError:pass
    else:raise AssertionError('oracle accepted a prior error in current profit')
    checks.append('Four consequential wrong-report detections: closing reserve as profit, invented cash, wrong bridge and discovery-year error expense')

    invalid=[]
    def mutate(path,val):
        d=deepcopy(data);o=d
        for k in path[:-1]:o=o[k]
        o[path[-1]]=val;invalid.append(d)
    mutate(['inventory','periods',0,'sold'],'201')
    mutate(['inventory','periods',0,'purchases',0,'unit_cost'],'6')
    mutate(['inventory','periods',0,'operating_cash'],'900')
    mutate(['inventory','opening_cash'],'501')
    mutate(['inventory','periods',1,'period'],'X1')
    mutate(['inventory','periods',0,'sold'],True)
    mutate(['inventory','opening_layers',0,'quantity'],'-1')
    mutate(['asset','original_life'],True)
    mutate(['asset','revised_remaining_life'],0)
    mutate(['asset','residual'],'120')
    mutate(['asset','elapsed_years'],4)
    mutate(['segments','internal_expense_included'],'0')
    mutate(['segments','internal_receivables'],'301')
    mutate(['segments','items',1,'name'],'Hardware')
    for d in invalid:
        try:module.analyze(d)
        except (ValueError,TypeError,KeyError):pass
        else:raise AssertionError('invalid case accepted')
    checks.append(f'{len(invalid)} consequential inventory, timing, precision, useful-life and segment-contract failures rejected')

    for optimized in (False,True):
        command=[sys.executable]+(['-O'] if optimized else [])+[str(source)]
        p=subprocess.run(command,cwd='/tmp',capture_output=True,text=True,check=False)
        require(p.returncode==0 and not p.stderr,'portable benchmark CLI')
        require(json.loads(p.stdout)==result,'normal/optimized CLI exact output')
    html=(ROOT/'content/chapters/v07-c11.html').read_text()
    class Structure(HTMLParser):
        def __init__(self):
            super().__init__();self.mode=None;self.detail=False;self.counts={'worked':0,'exercises':0,'solutions':0}
        def handle_starttag(self,tag,attrs):
            a=dict(attrs)
            if tag=='aside' and a.get('class')=='worked':self.counts['worked']+=1
            if tag=='details' and a.get('class')=='solutions':self.detail=True
            if tag=='ol' and a.get('class')=='exercises':self.mode='exercises'
            elif tag=='ol' and self.detail:self.mode='solutions'
            if tag=='li' and self.mode:self.counts[self.mode]+=1
        def handle_endtag(self,tag):
            if tag=='ol':self.mode=None
            if tag=='details':self.detail=False
    parser=Structure();parser.feed(html)
    require(parser.counts=={'worked':3,'exercises':8,'solutions':8},'complete chapter structure')
    for name in ('inputs.json','analysis.py','output.json','README.txt'):require(f'href="v07-c11-{name}"' in html,'flat lab link')
    require('Teach-back criteria and illustrative answer' in html and 'Delayed-check answers' in html,'answered teaching prompts')
    sources=json.loads((ROOT/'content/reviews/v07-c11-sources.json').read_text())
    require(len(sources)==9 and all(s['verification'] and s['id'].startswith('v07-c11-') for s in sources),'scoped source records')
    require(all('sources.html#'+s['id'] in html for s in sources),'source routes used')
    checks.append('Portable normal/optimized CLI, three worked cases, eight matched solutions, answered retrieval and nine scoped sources')
    files=['content/chapters/v07-c11.html','content/projects/v07-c11-inputs.json','content/projects/v07-c11-analysis.py','content/projects/v07-c11-output.json','content/projects/v07-c11-README.txt','content/reviews/v07-c11-sources.json']
    return {'status':'passed','chapter':'v07-c11','checks':checks,
            'counts':{'inventory_probes':len(inventory_probes),'asset_probes':len(asset_probes),'matched_segment_transfer':1,'invalid_contracts':len(invalid),'wrong_report_mutations':4,'exercises':8},
            'sha256':{f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in files},
            'limitations':['Synthetic accounting and stated schedules only; no actual filing, standard-election, useful-life or materiality judgment.','Integer-unit independent inventory oracle covers the original/probe lots; benchmark also supports rational quantities without a claim of exhaustive input testing.','Source evidence classification and comparability judgments require the written rubric.','No visual, browser, mobile or print QA.']}


if __name__=='__main__':
    print(json.dumps(check(),indent=2,allow_nan=False))
