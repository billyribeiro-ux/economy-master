"""Independent cash, dated-payoff and portable-contract checks for Volume11 Chapter03."""
from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from io import StringIO
import json
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT/'content/projects'


def require(condition, message):
    if not condition:
        raise AssertionError(message)


class Audit:
    def __init__(self):
        self.comparisons = 0
        self.rejections = 0
        self.interventions = 0

    def eq(self, actual, expected, message):
        self.comparisons += 1
        require(actual == expected, message+': '+repr(actual)+' != '+repr(expected))


def fiscal_oracle(a, data, result):
    """Use cumulative principal/interest and dated statewise streams, not model helpers."""
    b, c, p = data['business'], data['collateral'], data['policy']
    floor = F(p['minimum_cash']); m = F(p['minimum_base_dscr'])
    scenarios = {row['id']:row for row in data['scenarios']}
    cashflows = {name:[F(row['ebitda'][i])-sum(F(row[key][i]) for key in
                  ('cash_taxes','maintenance_capex','working_capital_increase')) for i in range(3)]
                for name,row in scenarios.items()}
    a.eq({name:list(map(F,values)) for name,values in result['operating_cfads'].items()},cashflows,'cash bridge')
    h = 1+F(b['valuation_hurdle'])
    pv = sum(cashflows['base'][i]/h**(i+1) for i in range(3))+(floor+F(b['terminal_operating_value']))/h**3
    a.eq(F(result['illustrative_unlevered_valuation']['pv']),pv,'separate enterprise present value')
    a.eq(F(result['illustrative_unlevered_valuation']['npv']),pv-F(b['capital_purchase'])-floor,'enterprise funding cost')
    gross = sum(F(row['gross_value'])*F(row['eligible_fraction'])*F(row['realization_fraction']) for row in c['assets'])
    cost, senior = F(c['workout_cost']), F(c['prior_claim'])
    # Cumulative priority intervals partition realized cash independently of
    # the implementation's sequential remaining-cash loop.
    paid_cost = min(gross,cost)
    paid_senior = min(gross,cost+senior)-min(gross,cost)
    available = max(F(0),gross-cost-senior)
    wf = result['collateral_waterfall']
    for key,expected in {'gross_sale_cash':gross,'workout_cost_paid':paid_cost,
                         'prior_claim_paid':paid_senior,'unpaid_workout_cost':cost-paid_cost,
                         'unpaid_prior_claim':senior-paid_senior,'available_to_this_lender_and_juniors':available}.items():
        a.eq(F(wf[key]),expected,'priority cash '+key)
    for source,realized in zip(c['assets'],wf['asset_realizations']):
        a.eq(F(realized['eligible_value']),F(source['gross_value'])*F(source['eligible_fraction']),'asset eligibility')
        a.eq(F(realized['sale_cash']),F(realized['eligible_value'])*F(source['realization_fraction']),'asset cash realization')
    for proposal, actual in zip(data['proposals'],result['proposals']):
        loan, equity, rate = F(proposal['advance']), F(proposal['sponsor_cash']), F(proposal['rate'])
        principal = list(map(F,proposal['principal']))
        balances = [loan-sum(principal[:i]) for i in range(3)]
        interest = [rate*x for x in balances]
        service = [x+y for x,y in zip(principal,interest)]
        opening = loan+equity-F(b['capital_purchase'])
        a.eq(F(actual['opening_cash_if_sources_received']),opening,'sources and uses recomputed')
        a.eq(F(actual['initial_funding_gap_to_cash_floor']),max(F(0),floor-opening),'initial funding gap')
        a.eq(sum(principal),loan,'full principal amortization')
        for i,row in enumerate(actual['contract_schedule']):
            a.eq((row['year'],F(row['opening_principal']),F(row['interest']),F(row['principal']),F(row['service']),F(row['closing_principal'])),
                 (i+1,balances[i],interest[i],principal[i],service[i],balances[i]-principal[i]),'entire debt row')
        cash_gates = []; base_pass = None
        for scenario in actual['scenarios']:
            name = scenario['id']; flows = cashflows[name]
            # Interest through t = r[tL - sum_{j<t}(t-j)*a_j].
            cumulative_cash = [opening+sum(flows[:t])-sum(principal[:t])-
                               rate*(t*loan-sum((t-j)*principal[j-1] for j in range(1,t)))
                               for t in (1,2,3)]
            ratio = [flows[i]/service[i] for i in range(3)]
            path = [opening]+cumulative_cash
            a.eq([F(row['cash_after_service_on_contract_projection']) for row in scenario['rows']],cumulative_cash,'cumulative funded cash oracle')
            for i,row in enumerate(scenario['rows']):
                a.eq(F(row['cash_before_service_on_contract_projection']),cumulative_cash[i]+service[i],'cash before payment')
                a.eq(F(row['cfads']),flows[i],'row cash bridge')
                a.eq(F(row['dscr']),ratio[i],'defined DSCR')
                a.eq(F(row['dscr_headroom_cash']),flows[i]-m*service[i],'cash headroom at DSCR floor')
                income=F(scenarios[name]['ebitda'][i])-F(b['depreciation'][i])-interest[i]-F(scenarios[name]['cash_taxes'][i])
                a.eq(F(row['income_if_tax_expense_equals_cash_tax']),income,'income differs from debt service')
            a.eq(F(scenario['minimum_projected_cash']),min(path),'all dated balances include closing')
            a.eq(scenario['first_cash_floor_breach_year'],next((t for t,value in enumerate(path) if value < floor),None),'first cash-floor breach')
            a.eq(scenario['first_payment_shortfall_year'],next((t for t,value in enumerate(path) if value < 0),None),'first unfunded payment')
            a.eq(F(scenario['minimum_initial_injection_for_cash_floor']),max(F(0),floor-min(path)),'minimal cash-injection certificate')
            breach=[i+1 for i,value in enumerate(ratio) if value < m]
            a.eq(scenario['dscr_breach_years'],breach,'coverage warning dates')
            cash_gates.append(min(path)>=floor)
            if name == 'base': base_pass = not breach
        d, lag = c['default_year'], c['recovery_delay_years']
        claim=loan-sum(principal[:d-1])+interest[d-1]
        paid=min(gross,cost+senior+claim)-min(gross,cost+senior)
        residual=max(F(0),gross-cost-senior-claim)
        a.eq(paid_cost+paid_senior+paid+residual,gross,'statewise waterfall conservation')
        q = actual['collateral_branch']; discount=1+F(c['assessment_rate']); prob=F(c['physical_default_weight'])
        full_stream={i+1:service[i] for i in range(3)}
        default_stream={i+1:service[i] for i in range(d-1)}
        default_stream[d+lag]=paid
        full_pv=sum(value/discount**t for t,value in full_stream.items())
        default_pv=sum(value/discount**t for t,value in default_stream.items())
        # Mix cash AT EACH DATE first, then discount, independently of the model's PV mixture.
        dates=set(full_stream)|set(default_stream)
        mixture=sum(((1-prob)*full_stream.get(t,F(0))+prob*default_stream.get(t,F(0)))/discount**t for t in dates)
        for key,expected in {'claim_at_default':claim,'lender_recovery':paid,'junior_residual':residual,
                             'nominal_claim_loss':claim-paid,'recovery_fraction_of_claim':paid/claim,
                             'recovery_discounted_to_default':paid/discount**lag,
                             'discounted_claim_shortfall_at_default':claim-paid/discount**lag,
                             'promised_receipts_pv':full_pv,'default_branch_receipts_pv':default_pv,
                             'physical_scenario_weighted_receipts_pv':mixture,
                             'physical_scenario_margin_over_advance':mixture-loan,
                             'weighted_shortfall_from_promised_pv':full_pv-mixture}.items():
            a.eq(F(q[key]),expected,'dated lender cash '+key)
        a.eq(q['recovery_year'],d+lag,'actual recovery date')
        ebitda=F(scenarios['base']['ebitda'][0]); lev=loan/ebitda if ebitda>0 else None
        a.eq(F(actual['initial_debt_ebitda']) if actual['initial_debt_ebitda'] is not None else None,lev,'positive-earnings leverage domain')
        gates={'initial_sources_cover_purchase_and_cash_floor':opening>=floor,
               'base_dscr_meets_defined_floor':base_pass,
               'initial_debt_ebitda_within_limit':lev is not None and lev<=F(p['maximum_initial_debt_ebitda']),
               'all_scenario_payment_dates_preserve_cash_floor':all(cash_gates),
               'physical_scenario_margin_meets_assumed_hurdle':mixture-loan>=F(p['minimum_scenario_margin']),
               'required_evidence_recorded':all(proposal['evidence'].values())}
        a.eq(actual['gates'],gates,'all six gates independently reconstructed')
        a.eq(actual['failed_gates'],[key for key,value in gates.items() if not value],'no missing failed gate')
        quantitative=all(value for key,value in gates.items() if key!='required_evidence_recorded')
        expected='eligible_for_credit_committee_review' if all(gates.values()) else 'hold_for_evidence' if quantitative else 'restructure_or_refuse'
        a.eq(actual['recommendation'],expected,'limited recommendation follows every gate')


class Fragment(HTMLParser):
    def __init__(self):
        super().__init__(); self.stack=[]; self.ids=[]; self.worked=0; self.prompts=0; self.answers=0; self.ols=[]; self.solutions=False

    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if 'id' in attrs:self.ids.append(attrs['id'])
        if 'worked' in attrs.get('class','').split():self.worked+=1
        if tag=='details' and 'solutions' in attrs.get('class','').split():self.solutions=True
        if tag=='ol':self.ols.append('exercises' if 'exercises' in attrs.get('class','').split() else 'solutions' if self.solutions else 'other')
        if tag=='li' and self.ols:
            if self.ols[-1]=='exercises':self.prompts+=1
            if self.ols[-1]=='solutions':self.answers+=1
        if tag not in ('br','hr','img','input','meta','link'):self.stack.append(tag)

    def handle_endtag(self,tag):
        require(bool(self.stack) and self.stack[-1]==tag,'unbalanced HTML '+tag)
        self.stack.pop()
        if tag=='ol':self.ols.pop()
        if tag=='details':self.solutions=False


def check():
    a=Audit(); original=json.loads((ASSETS/'v11-c03-inputs.json').read_text())
    noise=StringIO()
    with redirect_stdout(noise),redirect_stderr(noise):
        model=runpy.run_path(str(ASSETS/'v11-c03-analysis.py'))
        saved=deepcopy(original); output=model['run'](original)
    a.eq(noise.getvalue(),'','quiet import and API');a.eq(original,saved,'input is unchanged')
    a.eq(output,json.loads((ASSETS/'v11-c03-output.json').read_text()),'complete saved output')
    fiscal_oracle(a,original,output)
    requested,revised=output['proposals']
    a.eq(requested['recommendation'],'restructure_or_refuse','requested contract rejected')
    a.eq(revised['failed_gates'],['required_evidence_recorded'],'revised missing evidence isolated')
    a.eq(F(revised['collateral_branch']['physical_scenario_margin_over_advance']),F(244400,148877),'independent baseline margin anchor')
    a.eq(F(output['illustrative_unlevered_valuation']['npv']),F(42260,1331),'positive project NPV is a distinct object')
    variants=[]
    def change(label,operation):
        data=deepcopy(original);operation(data);variants.append((label,data))
    change('sponsor funding omitted',lambda x:x['proposals'][1].update(sponsor_cash='20'))
    change('evidence documented',lambda x:x['proposals'][1].update(evidence={key:True for key in x['proposals'][1]['evidence']}))
    change('cash floor equality',lambda x:x['scenarios'][1]['working_capital_increase'].__setitem__(1,'7.8'))
    change('cash floor one unit below at eight decimals',lambda x:x['scenarios'][1]['working_capital_increase'].__setitem__(1,'7.80000001'))
    change('recovery immediate',lambda x:x['collateral'].update(recovery_delay_years=0))
    change('prior claim and delay transfer',lambda x:x['collateral'].update(prior_claim='25',recovery_delay_years=2))
    change('prior claim consumes net estate',lambda x:x['collateral'].update(prior_claim='100'))
    change('cost exceeds estate',lambda x:x['collateral'].update(workout_cost='100'))
    change('default before first payment',lambda x:x['collateral'].update(default_year=1))
    change('default before final payment',lambda x:x['collateral'].update(default_year=3,recovery_delay_years=3))
    change('zero default weight',lambda x:x['collateral'].update(physical_default_weight='0'))
    change('certain default branch',lambda x:x['collateral'].update(physical_default_weight='1'))
    change('zero assessment discount',lambda x:x['collateral'].update(assessment_rate='0'))
    change('higher assessment hurdle',lambda x:x['collateral'].update(assessment_rate='0.08'))
    change('larger default weight',lambda x:x['collateral'].update(physical_default_weight='0.3'))
    change('bullet repayment',lambda x:x['proposals'][1].update(principal=['0','0','80']))
    change('higher contractual coupon',lambda x:x['proposals'][1].update(rate='0.12'))
    change('changed funded advance',lambda x:x['proposals'][1].update(advance='90',sponsor_cash='50',principal=['30','30','30']))
    change('nonpositive base EBITDA',lambda x:x['scenarios'][0]['ebitda'].__setitem__(0,'0'))
    change('claim capped with junior surplus',lambda x:x['collateral']['assets'][0].update(gross_value='900'))
    change('working capital releases cash',lambda x:x['scenarios'][1]['working_capital_increase'].__setitem__(1,'-5'))
    values={}
    for name,data in variants:
        result=model['run'](data);fiscal_oracle(a,data,result);a.interventions+=1;values[name]=result
    a.eq(values['sponsor funding omitted']['proposals'][1]['initial_funding_gap_to_cash_floor'],'40','restructure has no invented opening cash')
    a.eq(values['evidence documented']['proposals'][1]['recommendation'],'eligible_for_credit_committee_review','evidence changes permitted classroom status')
    for name,passes in (('cash floor equality',True),('cash floor one unit below at eight decimals',False)):
        a.eq(values[name]['proposals'][1]['gates']['all_scenario_payment_dates_preserve_cash_floor'],passes,'exact cash threshold')
    transfer=values['prior claim and delay transfer']['proposals'][1]['collateral_branch']
    a.eq((F(transfer['lender_recovery']),transfer['recovery_year'],F(transfer['discounted_claim_shortfall_at_default'])),(F(45),4,F(347616,14045)),'seniority and delay exercise')
    q=revised['collateral_branch'];g=F(q['promised_receipts_pv']);bad=F(q['default_branch_receipts_pv'])
    a.eq((g-80)/(g-bad),F(122,475),'physical probability threshold exercise')
    a.eq(F(values['larger default weight']['proposals'][1]['collateral_branch']['physical_scenario_margin_over_advance']),F(-77080,148877),'probability intervention overturns margin')
    a.eq(F(values['higher assessment hurdle']['proposals'][1]['collateral_branch']['physical_scenario_margin_over_advance']),F(-9365,6561),'assessment-rate intervention overturns margin')
    # Independent one-period statewise payoff and officer-deviation exercise answers.
    for face,expected in ((20,(20,100,10,90)),(40,(40,80,20,80)),(100,(100,20,50,50))):
        lender_safe=min(face,120);equity_safe=max(120-face,0)
        lender_risky=sum(F(1,2)*min(face,x) for x in (0,200))
        equity_risky=sum(F(1,2)*max(x-face,0) for x in (0,200))
        a.eq((lender_safe,equity_safe,lender_risky,equity_risky),expected,'risk shifting statewise split')
        a.eq(equity_risky-equity_safe,F(face,2)-20,'risk shifting threshold')
    a.eq([F(1,10)*k-1 for k in (0,10,12)],[F(-1),F(0),F(1,5)],'officer effort deviations')
    a.eq((7+11-9,7+11+8-9-12),(9,5),'fresh retention cash')
    a.eq(F(30)-F(15)/F(21,20),F(110,7),'fresh retention dated recovery')
    invalid=[]
    def bad_input(path,value):
        data=deepcopy(original);target=data
        for key in path[:-1]:target=target[key]
        target[path[-1]]=value;invalid.append(data)
    for value in (80,True,None,float('nan'),float('inf'),'NaN','+80','080','8e1',' 80','80 ','1/0','0/2','1/-2','1/02','0.123456789','9'*30):
        bad_input(('proposals',1,'advance'),value)
    for path,value in (
        (('schema',),'wrong'),(('provenance',),'observed borrower'),(('business','capital_purchase'),'0'),
        (('business','depreciation'),['1','2']),(('business','valuation_hurdle'),'0.51'),
        (('scenarios',),[]),(('scenarios',0,'id'),'wrongbase'),(('scenarios',1,'id'),'base'),
        (('scenarios',1,'cash_taxes',0),'-1'),(('scenarios',1,'maintenance_capex',0),'-1'),
        (('proposals',),[]),(('proposals',1,'id'),'requested'),(('proposals',1,'id'),'Bad ID'),
        (('proposals',1,'principal'),['20','30','29']),(('proposals',1,'principal'),['80','0','0']),
        (('proposals',1,'rate'),'-0.01'),(('proposals',1,'rate'),'0.50000001'),
        (('proposals',1,'evidence','priority_verified'),1),
        (('collateral','default_year'),True),(('collateral','default_year'),0),(('collateral','default_year'),4),
        (('collateral','recovery_delay_years'),-1),(('collateral','recovery_delay_years'),4),
        (('collateral','physical_default_weight'),'1.00000001'),(('collateral','physical_default_weight'),'-0.01'),
        (('collateral','assets',0,'eligible_fraction'),'1.01'),(('collateral','assets',0,'realization_fraction'),'-1'),
        (('policy','minimum_base_dscr'),'0.99'),(('policy','maximum_initial_debt_ebitda'),'0'),
        (('policy','minimum_scenario_margin'),'-1')):
        bad_input(path,value)
    extra=deepcopy(original);extra['policy']['unknown']=1;invalid.append(extra)
    missing=deepcopy(original);del missing['collateral']['assessment_rate'];invalid.append(missing)
    for data in invalid:
        try:model['run'](data)
        except ValueError:a.rejections+=1
        else:raise AssertionError('invalid API input accepted')
    with tempfile.TemporaryDirectory() as directory:
        folder=Path(directory)
        for name in ('v11-c03-analysis.py','v11-c03-inputs.json'):shutil.copy2(ASSETS/name,folder/name)
        for optimize in (False,True):
            command=[sys.executable]+(['-O'] if optimize else [])
            explicit=subprocess.run(command+['v11-c03-analysis.py','--input','v11-c03-inputs.json','--output','result.json'],cwd=folder,capture_output=True,text=True,timeout=10)
            a.eq((explicit.returncode,explicit.stdout,explicit.stderr),(0,'',''),'portable explicit CLI quiet')
            a.eq(json.loads((folder/'result.json').read_text()),output,'portable explicit complete output')
            default=subprocess.run(command+['v11-c03-analysis.py'],cwd=folder,capture_output=True,text=True,timeout=10)
            a.eq((default.returncode,default.stderr),(0,''),'portable default CLI')
            a.eq(json.loads(default.stdout),output,'portable default complete output')
            program="import contextlib,io,json,runpy; capture=io.StringIO();\nwith contextlib.redirect_stdout(capture),contextlib.redirect_stderr(capture):\n model=runpy.run_path('v11-c03-analysis.py');data=json.load(open('v11-c03-inputs.json'));before=json.dumps(data,sort_keys=True);result=model['run'](data)\nif capture.getvalue() or json.dumps(data,sort_keys=True)!=before:raise RuntimeError('API noise or mutation')\nprint(json.dumps(result,allow_nan=False))"
            api=subprocess.run(command+['-c',program],cwd=folder,capture_output=True,text=True,timeout=10)
            a.eq((api.returncode,api.stderr),(0,''),'portable quiet API contract')
            a.eq(json.loads(api.stdout),output,'portable quiet API complete output')
            for invalid_json in ('{','{"schema":1,"schema":2}','{"schema":NaN}','{"schema":Infinity}','{"schema":-Infinity}',json.dumps(invalid[0])):
                (folder/'bad.json').write_text(invalid_json);(folder/'sentinel.json').write_text('preserve')
                rejected=subprocess.run(command+['v11-c03-analysis.py','--input','bad.json','--output','sentinel.json'],cwd=folder,capture_output=True,text=True,timeout=10)
                require(rejected.returncode!=0 and (folder/'sentinel.json').read_text()=='preserve','invalid CLI replaced output');a.rejections+=1
            for protected in ('v11-c03-inputs.json','v11-c03-analysis.py'):
                original_path=folder/protected
                before=original_path.read_bytes()
                symbolic=folder/('symbolic-'+protected)
                hard=folder/('hard-'+protected)
                if not symbolic.exists(): symbolic.symlink_to(original_path)
                if not hard.exists(): hard.hardlink_to(original_path)
                for target in (original_path,symbolic,hard):
                    rejected=subprocess.run(command+['v11-c03-analysis.py','--output',str(target)],cwd=folder,capture_output=True,text=True,timeout=10)
                    a.eq((rejected.returncode!=0,original_path.read_bytes()==before),(True,True),'protected input/implementation direct or alias')
    chapter=ROOT/'content/chapters/v11-c03.html';doc=Fragment();doc.feed(chapter.read_text())
    a.eq(doc.stack,[],'balanced HTML');a.eq(len(doc.ids),len(set(doc.ids)),'unique IDs')
    a.eq((doc.worked,doc.prompts,doc.answers),(4,8,8),'worked cases and complete prompt/solution count')
    a.eq(all(value in doc.ids for value in ('objective','exercises','teach-back','sources')),True,'required instructional sections')
    source=json.loads((ROOT/'content/reviews/v11-c03-sources.json').read_text())
    a.eq([row['id'] for row in source['proposals']],['v11-c03-occ-commercial'],'scoped primary proposal')
    manifest=json.loads((ASSETS/'v11-c03-manifest.json').read_text())
    a.eq(len(manifest['files']),4,'four portable payload bindings')
    for row in manifest['files']:
        payload=(ASSETS/row['file']).read_bytes()
        a.eq((len(payload),sha256(payload).hexdigest()),(row['bytes'],row['sha256']),'portable payload binding')
    author=json.loads((ROOT/'content/reviews/v11-c03-author.json').read_text())
    a.eq(len(author['reviewed_hashes']),8,'eight nonself author bindings')
    for row in author['reviewed_hashes']:
        payload=(ROOT/row['path']).read_bytes()
        a.eq((len(payload),sha256(payload).hexdigest()),(row['bytes'],row['sha256']),'author payload binding')
    return {'chapter':'v11-c03','status':'passed','comparisons':a.comparisons,
            'invalid_inputs_rejected':a.rejections,'financial_interventions':a.interventions,
            'worked_examples':4,'solved_exercises':8,
            'scope':'Independent exact cumulative cash, priority intervals and dated physical branch streams; portable normal/optimized API and CLI. Original assumptions are not empirical validation or real lending approval; separate peer/coordinator acceptance pending.'}


if __name__=='__main__':
    print(json.dumps(check(),indent=2,allow_nan=False))
