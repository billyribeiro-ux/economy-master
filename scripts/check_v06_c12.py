#!/usr/bin/env python3
"""Independent exact accounts/solutions and bounded lab contract audit for c12."""
from fractions import Fraction as Q
from pathlib import Path
from html.parser import HTMLParser
import contextlib
import copy
import importlib.util
import io
import json
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT/'content/projects/v06-c12-analysis.py'
INPUT = PROJECT.with_name('v06-c12-inputs.json')
CHAPTER = ROOT/'content/chapters/v06-c12.html'


def need(condition, message):
    if not condition:
        raise AssertionError(message)


def equal(actual, target, message):
    need(Q(actual) == Q(target), message + ': '+str(actual)+' != '+str(target))


def eq_fields(obj, targets, label):
    for key,target in targets.items():
        equal(obj[key], target, label+'.'+key)


class Fragment(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack=[]
        self.exercises=0
        self.solutions=0
        self.worked=0
        self.links=[]
        self.h1=0
        self.ids=[]
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        classes=attrs.get('class','').split()
        if tag=='h1': self.h1+=1
        if tag=='aside' and 'worked' in classes: self.worked+=1
        if 'id' in attrs: self.ids.append(attrs['id'])
        if tag=='a': self.links.append(attrs.get('href',''))
        if tag=='li':
            if any(t=='ol' and 'exercises' in c for t,c in self.stack): self.exercises+=1
            if any(t=='details' and 'solutions' in c for t,c in self.stack): self.solutions+=1
        if tag not in ('br','hr','img','input','meta','link'):
            self.stack.append((tag,classes))
    def handle_endtag(self,tag):
        if self.stack and self.stack[-1][0]==tag:
            self.stack.pop()
        else:
            raise AssertionError('mismatched HTML closing tag '+tag)


def audit_reference(result):
    """Hard-coded independent references, not values computed by lab routines."""
    bank=result['bank']
    eq_fields(bank['opening'],{'assets':110,'deposits':90,'equity':20},'opening')
    eq_fields(bank['sale_full_repayment'],{'face_sold':40,'receipts':30,'remaining_assets':60,'deposits':50,'equity':10,'buyer_discount_gain':10},'sale')
    eq_fields(bank['bridge_full_repayment'],{'remaining_assets':100,'deposits':50,'bridge':30,'equity':20},'bridge')
    eq_fields(bank['bridge_bad'],{'assets':70,'total_liabilities':80,'economic_equity':-10,'senior_payment':30,'late_deposit_payment':40,'creditor_shortfall':10},'bad')
    eq_fields(bank['public_support_bad'],{'cash':15,'loans':70,'total_liabilities':80,'residual_after_full_payment':5,'public_recovery':5,'creditor_shortfall':0},'support')
    col=result['collateral']
    eq_fields(col['no_impact']['minimum_sale'],{'lower':Q(400,9),'upper':Q(400,9),'upper_remaining_debt':40,'upper_remaining_assets':50,'upper_equity':10},'no impact')
    eq_fields(col['full_liquidation']['minimum_sale'],{'lower':100,'upper':100,'upper_remaining_debt':0,'upper_remaining_assets':0,'upper_equity':0},'liquidation')
    eq_fields(col['no_repair'],{'maximizer':25,'maximum_supported_debt':Q(289,4)},'no repair')
    need(col['no_repair']['minimum_sale'] is None and not col['no_repair']['sale_only_feasible'],'impossible branch')
    eq_fields(result['fx'],{'interest_F':Q(3,2),'official_required_F':Q(27,2),'unsupported_max_imports_F':Q(13,2),'closing_reserves_F':4,'closing_debt_F':Q(27,2),'CA_H':Q(51,2),'FA_H':Q(51,2),'valuation_H':-18,'opening_NFA_H':-36,'closing_NFA_H':Q(-57,2),'stock_flow_residual_H':0},'FX')
    eq_fields(result['fiscal']['baseline'],{'gross_issuance':78,'debt_stock_change':-2,'immediate_gap':8,'terminal_cash':Q(21,5),'present_value_margin':Q(420,121)},'baseline fiscal')
    eq_fields(result['fiscal']['linked_bank_support'],{'gross_issuance':93,'immediate_gap':23,'terminal_cash':Q(-73,10),'terminal_shortfall':Q(73,10),'claim_value_at_date_1':Q(50,11),'transfer_component':Q(115,11),'post_support_primary_1':Q(-71,11),'stock_flow_adjustment_1':Q(-16,11),'minimum_terminal_primary':Q(973,10),'present_value_margin':Q(-730,121),'debt_identity_residual':0},'support fiscal')


def check():
    checks=[]
    out=io.StringIO(); err=io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        spec=importlib.util.spec_from_file_location('c12_lab',PROJECT)
        lab=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(lab)
        raw=lab.load(INPUT)
        result=lab.run(raw)
    need(not out.getvalue() and not err.getvalue(),'quiet import and run')
    json.dumps(result,allow_nan=False)
    audit_reference(result)
    checks.append('Four worked examples: exact independent bank, global collateral, FX and fiscal targets')

    # Direct resource transfers across each balance sheet and both sovereign dates.
    b=result['bank']
    for row,a,l,e in [(b['opening'],'assets','deposits','equity'),(b['sale_full_repayment'],'remaining_assets','deposits','equity')]:
        equal(Q(row[a])-Q(row[l]),row[e],'bank book identity')
    equal(10+30-40,0,'withdrawal cash')
    equal(20+10,100-70,'shareholder and creditor loss allocation')
    equal(15+70-50-30,5,'capital injection does not erase old deficit')
    for name in ('baseline','linked_bank_support'):
        f=result['fiscal'][name]
        equal(6+4+Q(f['gross_issuance'])-88-Q(f['cash_payment']),0,'date1 cash')
        equal(Q(f['terminal_cash']),Q(f['present_value_margin'])*Q(121,100),'terminal/PV equivalence')
        equal(Q(f['claim_value_at_date_1'])+Q(f['transfer_component']),f['cash_payment'],'classification preserves cash')
    checks.append('Independent cash transfers, loss allocation, valuation split and finite present-value bridge')

    # Independent candidate evaluation: vertex and endpoints certify concave maximum.
    collateral_count=0
    for units in (Q(40),Q(100)):
        for theta in (Q(1,2),Q(4,5)):
            for impact in (Q(0),Q(1,1000),Q(1,200)):
                price=Q(9,10)
                for debt in (Q(0),Q(20),Q(79),Q(100)):
                    coeff=[theta*units*price,price*(1-theta)-impact*theta*units,-impact*(1-theta)]
                    candidates=[Q(0),units]
                    if coeff[2] != 0:
                        stationary=-coeff[1]/(2*coeff[2])
                        if 0 <= stationary <= units: candidates.append(stationary)
                    direct=lambda x:sum(c*x**j for j,c in enumerate(coeff))
                    maximum=max(direct(x) for x in candidates)
                    c={'units':units,'debt':debt,'ltv':theta,'price_intercept':price,'price_impact':impact}
                    answer=lab.collateral_case(c)
                    equal(answer['maximum_supported_debt'],maximum,'quadratic candidate reference')
                    need(answer['sale_only_feasible']==(debt<=maximum),'global feasibility')
                    bracket=answer['minimum_sale']
                    if bracket is not None:
                        lo,hi=bracket['lower'],bracket['upper']
                        need(0<=lo<=hi<=units,'sale bracket domain')
                        need(hi-lo<=units/Q(2**80) or lo==hi,'bracket width bound')
                        if hi != lo:
                            need(direct(lo)<debt<=direct(hi),'increasing-branch crossing certificate')
                        elif lo>0:
                            equal(direct(lo),debt,'exact binding crossing')
                        else:
                            need(direct(0)>=debt,'zero sale slack')
                        need(bracket['upper_ltv_slack']>=0,'upper bracket collateral condition')
                        need(bracket['upper_nonnegative_debt']==(bracket['upper_remaining_debt']>=0),'explicit debt domain')
                    collateral_count+=1
    checks.append('48 collateral parameter cases: endpoint/vertex global certificate, no-sale/no-repair/full-sale and bounded root branches')

    # Alternative exchange quotes must affect valuation, not fabricate F resources.
    fx_count=0
    for private in (0,8,24,40):
        for quote in ('1.5','2','3'):
            edit=copy.deepcopy(raw); edit['fx']['private_new']=private;edit['fx']['new_quote']=quote
            answer=lab.run(edit)['fx'];r=Q(answer['closing_reserves_F']);d=Q(answer['closing_debt_F'])
            equal(Q(answer['official_required_F']),max(Q(0),Q(27,2)-private),'F funding independent of quote')
            equal(Q(answer['CA_H']),Q(17,2)*Q(quote),'direct current transactions')
            equal(Q(answer['FA_H']),((r-12)-(d-30))*Q(quote),'signed financial transactions')
            equal(-36+Q(answer['FA_H'])+Q(answer['valuation_H']),answer['closing_NFA_H'],'stock-flow identity under quotes')
            fx_count+=1
    stress=copy.deepcopy(raw)
    stress['fx']['private_new']=8; stress['bank']['bad_recovery']=65; stress['fiscal']['primary_2']=100
    changed=lab.run(stress)
    equal(changed['fx']['official_required_F'],Q(11,2),'linked stress FX')
    equal(changed['bank']['public_support_bad']['public_recovery'],0,'linked bank value')
    equal(changed['fiscal']['linked_bank_support']['terminal_cash'],Q(-23,10),'no stale fiscal recovery')
    stress['bank']['bad_recovery']=60
    changed=lab.run(stress)
    need(not changed['fiscal']['supported_bank_pays_creditors_in_full'],'unrepaired bank insolvency exposed')
    equal(changed['bank']['public_support_bad']['creditor_shortfall'],5,'unrepaired creditor gap')
    checks.append('12 external funding/quote cases and linked adverse bank/fiscal scenarios')

    # Solve all determinate exercises without invoking the corresponding lab routines.
    exercise={}
    exercise['1']=[32-8,Q(32-8)/Q('0.8'),8+72-68,72-30-(68-32),54-(68-8),54+10-(68-8)]
    need(exercise['1']==[24,30,12,6,-6,4],'exercise1')
    h2=lambda x:Q(54)+Q(3,40)*x-x*x/Q(1600)
    equal(h2(Q(60)),Q(225,4),'exercise2 global maximum')
    # Completed square: 225/4-(x-60)^2/1600, for every real x.
    for x in (Q(-1),Q(0),Q(60),Q(80),Q(101)):
        equal(h2(x),Q(225,4)-(x-60)**2/Q(1600),'exercise2 square identity')
    sale=Q(80,3);receipts=Q(9,10)*sale;assets=Q(9,10)*(80-sale)
    exercise['2']=[Q(60),h2(Q(60)),sale,receipts,60-receipts,assets,assets-(60-receipts)]
    need(exercise['2']==[60,Q(225,4),Q(80,3),24,36,48,12],'exercise2 no-impact repair')
    h=Q(80)-Q(289,4);sale=Q(25);price=Q(9,10)-sale/Q(500);receipt=price*sale;debt=80-h-receipt;assets=price*(100-sale)
    exercise['3']=[h,sale,price,receipt,debt,assets,assets-debt]
    need(exercise['3']==[Q(31,4),25,Q(17,20),Q(85,4),51,Q(255,4),Q(51,4)],'exercise3')
    equal(Q(4,5)*assets,debt,'exercise3 binding LTV')
    official=3+18+22-10-25-2; reserve=10+25+2+official-18-22; newdebt=2+official
    ca=Q(5,2)*(25-18-2);fa=Q(5,2)*((reserve-10)-(newdebt-20));val=(10-20)*Q(1,2)
    exercise['4']=[official,10+25+2-22-3,ca,fa,val,Q(-20),(reserve-newdebt)*Q(5,2)]
    need(exercise['4']==[6,12,Q(25,2),Q(25,2),-5,-20,Q(-25,2)],'exercise4')
    r=Q(6,5);base=r*50-6-4; rescue=base+8;asset=3/r;transfer=8-asset;primary=6-transfer;adjustment=asset-4
    exercise['5']=[base,base-45,63-r*base,rescue,rescue-45,63+3-r*rescue,asset,transfer,primary,adjustment,r*rescue-3]
    need(exercise['5']==[50,5,3,58,13,Q(-18,5),Q(5,2),Q(11,2),Q(1,2),Q(-3,2),Q(333,5)],'exercise5')
    equal(r*50-primary+adjustment,rescue,'exercise5 debt classification')
    loss=[(0,18),(6,8),(2,12)];worst=[max(x) for x in loss];best=[min(row[i] for row in loss) for i in (0,1)]
    regret=[max(row[i]-best[i] for i in (0,1)) for row in loss]
    need(worst==[18,8,12] and regret==[10,6,4],'exercise6 robust criteria')
    for p,expected in [(Q(0),[0]),(Q(1,4),[0,2]),(Q(3,8),[2]),(Q(1,2),[1,2]),(Q(1),[1])]:
        values=[(1-p)*lo+p*hi for lo,hi in loss];chosen=[i for i,v in enumerate(values) if v==min(values)]
        need(chosen==expected,'exercise6 expected lower envelope')
    exercise['6']={'worst_losses':worst,'worst_regrets':regret,'switch_probabilities':['1/4','1/2']}
    exercise['7']='Manual logic audit: explicit counterfactual, selection, simultaneous tools, anticipatory behavior and transport limitations; evaluated by stated criteria, not one policy opinion.'
    old_liability=20+30*2;new_liability=20+30*3
    a_gap=30-Q(40-20,3);b_gap=30-Q(100-20,3)
    exercise['8']=[40+30*2-old_liability,100-old_liability,40+30*3-new_liability,100-new_liability,a_gap,b_gap,30-a_gap]
    need(exercise['8']==[20,20,20,-10,Q(70,3),Q(10,3),Q(20,3)],'exercise8')
    equal(10+70-50-40,-10,'retention extra loan leaves equity')
    equal(Q(105)-Q(1023,10),Q(27,10),'retention terminal surplus')
    checks.append('All eight exercise solutions recomputed or logic-scoped; delayed answers and expected-loss boundary ties checked')

    invalid=[]
    def add(path,value):
        obj=copy.deepcopy(raw);node=obj
        for key in path[:-1]:node=node[key]
        node[path[-1]]=value;invalid.append(obj)
    for v in (True,0,2,'1'):add(['schema_version'],v)
    for v in (True,0.8,'NaN','Infinity','1e2','1/2',' 1','0.1234567890',1_000_001):add(['bank','cash'],v)
    for field,value in [('withdrawal',10),('withdrawal',91),('sale_price',0),('sale_price','1.1'),('sale_price','0.1'),('bad_recovery',81),('bad_recovery',-1),('injection',-1)]:add(['bank',field],value)
    for field,value in [('ltv',1),('ltv',0),('units',0),('debt',-1),('price_impact',-1),('price_impact','0.01'),('id','bad id')]:add(['collateral',0,field],value)
    add(['collateral'],[]);add(['collateral'],[raw['collateral'][0]]*21);add(['collateral'],[raw['collateral'][0],raw['collateral'][0]])
    for field,value in [('old_quote',0),('new_quote',0),('interest',-1),('imports',-1)]:add(['fx',field],value)
    for field,value in [('gross_rate','0.9'),('gross_rate',0),('cash',1000),('private_cap',-1)]:add(['fiscal',field],value)
    missing=copy.deepcopy(raw);del missing['bank']['cash'];invalid.append(missing)
    extra=copy.deepcopy(raw);extra['extra']=1;invalid.append(extra)
    for obj in invalid:
        try:lab.run(obj)
        except ValueError:pass
        else:raise AssertionError('malformed input accepted')
    checks.append(str(len(invalid))+' malformed input contracts rejected with explicit exceptions')

    # Deliberate report mutations must fail independent accounting/reference audit.
    mutant_count=0
    for path,value in [(['bank','bridge_bad','economic_equity'],'0'),(['fx','CA_H'],'66'),(['fiscal','linked_bank_support','gross_issuance'],'108')]:
        mutant=copy.deepcopy(result);node=mutant
        for key in path[:-1]:node=node[key]
        node[path[-1]]=value
        try:audit_reference(mutant)
        except AssertionError:mutant_count+=1
    need(mutant_count==3,'all deliberate wrong-output mutations caught')
    checks.append('Three injected errors caught: erased bank deficit, official loan as income, double-counted support')

    with tempfile.TemporaryDirectory(prefix='v06-c12-') as td:
        for options in ([],['-O']):
            cp=subprocess.run([sys.executable,*options,str(PROJECT)],cwd=td,text=True,capture_output=True,check=False)
            need(cp.returncode==0 and not cp.stderr and json.loads(cp.stdout)==result,'portable CLI, normal/optimized')
        bad=Path(td)/'bad.json';bad.write_text(json.dumps(invalid[0]))
        cp=subprocess.run([sys.executable,'-O',str(PROJECT),str(bad)],cwd=td,text=True,capture_output=True,check=False)
        need(cp.returncode==2 and not cp.stderr and json.loads(cp.stdout)['status']=='error','optimized invalid CLI')
        for text in ('{"a":1,"a":2}','{"a":NaN}','{"a":Infinity}'):
            bad.write_text(text)
            try:lab.load(bad)
            except ValueError:pass
            else:raise AssertionError('duplicate/nonfinite JSON accepted')
    checks.append('Quiet strict JSON, portable normal/-O CLI, optimized validation, duplicate/nonfinite JSON rejection')

    parser=Fragment();body=CHAPTER.read_text();parser.feed(body)
    need(not parser.stack and parser.h1==0 and parser.worked>=2 and parser.exercises==parser.solutions==8,'chapter structure')
    need(len(parser.ids)==len(set(parser.ids)),'unique IDs')
    source_path=ROOT/'content/reviews/v06-c12-sources.json'
    sources=json.loads(source_path.read_text())
    source_ids={s['id'] for s in sources}
    for s in sources:
        need(set(s)=={'id','title','url','use','checked','verification'} and s['id'].startswith('v06-c12-'),'source proposal schema')
    for href in parser.links:
        if href.startswith('sources.html#'):
            need(href.split('#')[1] in source_ids,'scoped source citation')
        elif href.startswith('v06-c12-'):
            need((ROOT/'content/projects'/href).is_file(),'flat download route')
        elif href.endswith('.html'):
            need((ROOT/'content/chapters'/href).is_file(),'written chapter route '+href)
        elif href.startswith('curriculum.html#'):
            need(href in ('curriculum.html#v06','curriculum.html#v07'),'planned curriculum route')
        else:raise AssertionError('unexpected local route '+href)
    for heading in ('Teach-back','Delayed check','Complete solutions','Sources and next steps'):
        need(heading in body,'required learner section '+heading)
    checks.append('Fragment structure, four worked cases/eight matching solutions, flat artifacts and scoped source/chapter routes')
    return {'status':'passed','checks':checks,'details':{'collateral_cases':collateral_count,'external_cases':fx_count,'invalid_contracts':len(invalid),'caught_report_mutations':mutant_count,'worked_examples':parser.worked,'exercises':parser.exercises,'source_records':len(sources)},
        'limitations':['Synthetic conditional accounts, not empirical crisis forecasts, legal advice or identified policy effects.','Historical body inspection and proof/teaching review documented separately; source truth is not established by arithmetic checks.','Public claim valuation uses a supplied deterministic payoff and discount convention; actual instruments require separate classification.','Visual/mobile/print browser QA remains pending; no browser workaround used.']}


if __name__=='__main__':
    try:
        result=check()
    except Exception as exc:
        print(json.dumps({'status':'failed','error':str(exc)},sort_keys=True,allow_nan=False))
        sys.exit(1)
    print(json.dumps(result,indent=2,sort_keys=True,allow_nan=False))
