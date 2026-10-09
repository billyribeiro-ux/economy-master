"""Separate c03 peer: principal tranches, cash cuts and priority certificates.

Candidate run() is the subject under test. No author checker or numerical helper
is imported. check() is quiet, strict-JSON-safe, and active under python -O.
"""
from fractions import Fraction as Q
from html.parser import HTMLParser
from pathlib import Path
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT/'content/projects'
MODEL = PROJECT/'v11-c03-analysis.py'
COUNT = REJECTIONS = INTERVENTIONS = 0


def require(condition, label):
    global COUNT
    COUNT += 1
    if not condition:
        raise RuntimeError(label)


def equal(actual, expected, label):
    require(actual == expected, label+': '+repr(actual)+' != '+repr(expected))


def strict(text):
    def invalid(value):
        raise ValueError('nonfinite JSON: '+value)
    return json.loads(text, parse_constant=invalid)


def rational_fields(row, fields):
    return tuple(Q(row[k]) for k in fields.split())


def backward_value(stream, rate):
    """Backward funding recurrence, rather than the model's dated PV sum."""
    value = Q(0)
    for date in range(max(stream), 0, -1):
        value = (value+stream.get(date,Q(0)))/(1+rate)
    return value


def priority_certificate(gross, demands, payments):
    """Conservation/caps and strict priority uniquely pin down allocations.

    If an earlier claim is unsatisfied, every later claim gets zero. This
    certificate checks the output without replaying the model's waterfall loop.
    The final payment is a junior residual with no finite claim cap.
    """
    equal(sum(payments),gross,'all estate cash allocated exactly once')
    require(all(x>=0 for x in payments),'no negative priority payment')
    for i, demand in enumerate(demands):
        require(payments[i]<=demand,'claim payment capped at entitlement')
        if payments[i]<demand:
            equal(sum(payments[i+1:]),0,'unsatisfied earlier claim blocks all downstream cash')


def fiscal_certificate(data, result):
    b, col, policy = data['business'], data['collateral'], data['policy']
    floor = Q(policy['minimum_cash']); minimum_dscr = Q(policy['minimum_base_dscr'])
    flows = {s['id']:[Q(e)-Q(t)-Q(k)-Q(w) for e,t,k,w in zip(s['ebitda'],s['cash_taxes'],s['maintenance_capex'],s['working_capital_increase'])]
             for s in data['scenarios']}
    equal({k:list(map(Q,v)) for k,v in result['operating_cfads'].items()},flows,'operating cash bridge')
    stream = dict(enumerate(flows['base'],1))
    stream[3] += floor+Q(b['terminal_operating_value'])
    project = backward_value(stream,Q(b['valuation_hurdle']))
    equal(rational_fields(result['illustrative_unlevered_valuation'],'initial_uses pv npv'),
          (Q(b['capital_purchase'])+floor,project,project-Q(b['capital_purchase'])-floor),'unlevered backward valuation versus funded uses')
    realized = [Q(a['gross_value'])*Q(a['eligible_fraction'])*Q(a['realization_fraction']) for a in col['assets']]
    gross = sum(realized); costs = Q(col['workout_cost']); senior = Q(col['prior_claim'])
    wf = result['collateral_waterfall']
    equal(Q(wf['gross_sale_cash']),gross,'eligible realized estate, not appraisal')
    equal([Q(x['sale_cash']) for x in wf['asset_realizations']],realized,'individual collateral proceeds')
    equal([Q(x['eligible_value']) for x in wf['asset_realizations']],
          [Q(x['gross_value'])*Q(x['eligible_fraction']) for x in col['assets']],'eligibility before realization')
    equal(Q(wf['unpaid_workout_cost'])+Q(wf['workout_cost_paid']),costs,'cost claim paid plus unpaid')
    equal(Q(wf['unpaid_prior_claim'])+Q(wf['prior_claim_paid']),senior,'prior claim paid plus unpaid')
    equal(len(result['proposals']),len(data['proposals']),'all proposals retained')
    scenario_inputs={s['id']:s for s in data['scenarios']}
    for proposal, out in zip(data['proposals'],result['proposals']):
        equal(out['id'],proposal['id'],'proposal identity')
        principal = list(map(Q,proposal['principal'])); rate = Q(proposal['rate'])
        advance = Q(proposal['advance'])
        # Treat each scheduled principal amount as a separate tranche that
        # pays its coupon on every date up to its own maturity. No recursive
        # opening-loan-balance state is needed to generate interest or service.
        tranche_cash = [[amount*rate*(date<=maturity)+amount*(date==maturity)
                         for date in range(1,4)] for maturity,amount in enumerate(principal,1)]
        service = [sum(row[t] for row in tranche_cash) for t in range(3)]
        interest = [service[t]-principal[t] for t in range(3)]
        opening = advance+Q(proposal['sponsor_cash'])-Q(b['capital_purchase'])
        equal(rational_fields(out,'advance sponsor_cash opening_cash_if_sources_received initial_funding_gap_to_cash_floor'),
              (advance,Q(proposal['sponsor_cash']),opening,max(Q(0),floor-opening)),'fully funded sources and uses')
        for t, row in enumerate(out['contract_schedule']):
            remaining = sum(principal[t:])
            equal((row['year'],*rational_fields(row,'opening_principal interest principal service closing_principal')),
                  (t+1,remaining,interest[t],principal[t],service[t],sum(principal[t+1:])), 'principal-tranche debt service')
        cash_ok=[]; base_coverage=None
        for scenario in out['scenarios']:
            name=scenario['id']; cf=flows[name]; inp=scenario_inputs[name]
            # Cash is the sum of source/use vectors cut at each date, including
            # closing. Every service is already generated by independent tranches.
            paths=[opening+sum(cf[:t])-sum(sum(row[:t]) for row in tranche_cash) for t in range(4)]
            warnings=[]
            for t, row in enumerate(scenario['rows']):
                earnings=Q(inp['ebitda'][t])-Q(inp['cash_taxes'][t])-Q(b['depreciation'][t])-interest[t]
                equal(rational_fields(row,'cfads income_if_tax_expense_equals_cash_tax dscr dscr_headroom_cash cash_before_service_on_contract_projection cash_after_service_on_contract_projection'),
                      (cf[t],earnings,cf[t]/service[t],cf[t]-minimum_dscr*service[t],paths[t]+cf[t],paths[t+1]), 'cash cut, earnings and flow coverage')
                if cf[t]<minimum_dscr*service[t]: warnings.append(t+1)
            equal(scenario['dscr_breach_years'],warnings,'cross-multiplied covenant dates')
            equal((Q(scenario['minimum_projected_cash']),scenario['first_cash_floor_breach_year'],scenario['first_payment_shortfall_year']),
                  (min(paths),next((t for t,v in enumerate(paths) if v<floor),None),next((t for t,v in enumerate(paths) if v<0),None)), 'floor breach distinguished from actual shortfall')
            injection=Q(scenario['minimum_initial_injection_for_cash_floor'])
            equal(injection,max(Q(0),floor-min(paths)),'minimal up-front injection')
            require(all(v+injection>=floor for v in paths),'cash-injection sufficiency')
            if injection>0:
                require(any(v+injection-Q(1,10**8)<floor for v in paths),'strictly smaller injection fails at a minimizing date')
            cash_ok.append(min(paths)>=floor)
            if name=='base': base_coverage=not warnings
        branch=out['collateral_branch']; d=col['default_year']; lag=col['recovery_delay_years']
        claim=sum(principal[d-1:])*(1+rate)
        recovery=Q(branch['lender_recovery']); junior=Q(branch['junior_residual'])
        priority_certificate(gross,[costs,senior,claim],
                             [Q(wf['workout_cost_paid']),Q(wf['prior_claim_paid']),recovery,junior])
        equal(recovery+junior,Q(wf['available_to_this_lender_and_juniors']),'available estate split at lender cap')
        a=Q(col['assessment_rate']); p=Q(col['physical_default_weight'])
        full_stream=dict(enumerate(service,1))
        default_stream={t:service[t-1] for t in range(1,d)}
        default_stream[d+lag]=recovery
        promised=backward_value(full_stream,a); default=backward_value(default_stream,a)
        mixed_stream={t:(1-p)*full_stream.get(t,Q(0))+p*default_stream.get(t,Q(0)) for t in set(full_stream)|set(default_stream)}
        mixed=backward_value(mixed_stream,a)
        at_default=recovery if lag==0 else backward_value({lag:recovery},a)
        equal((branch['recovery_year'],*rational_fields(branch,'claim_at_default nominal_claim_loss recovery_fraction_of_claim recovery_discounted_to_default discounted_claim_shortfall_at_default promised_receipts_pv default_branch_receipts_pv physical_scenario_weighted_receipts_pv physical_scenario_margin_over_advance weighted_shortfall_from_promised_pv')),
              (d+lag,claim,claim-recovery,recovery/claim,at_default,claim-at_default,promised,default,mixed,mixed-advance,promised-mixed), 'dated physical receipt streams and distinct shortfall objects')
        earnings=Q(scenario_inputs['base']['ebitda'][0]); leverage=advance/earnings if earnings>0 else None
        equal(None if out['initial_debt_ebitda'] is None else Q(out['initial_debt_ebitda']),leverage,'positive earnings leverage domain')
        gates={
            'initial_sources_cover_purchase_and_cash_floor':opening>=floor,
            'base_dscr_meets_defined_floor':base_coverage,
            'initial_debt_ebitda_within_limit':earnings>0 and advance<=Q(policy['maximum_initial_debt_ebitda'])*earnings,
            'all_scenario_payment_dates_preserve_cash_floor':all(cash_ok),
            'physical_scenario_margin_meets_assumed_hurdle':mixed-advance>=Q(policy['minimum_scenario_margin']),
            'required_evidence_recorded':all(proposal['evidence'].values())}
        equal(out['gates'],gates,'six independent credit gates')
        equal(set(out['failed_gates']),{k for k,v in gates.items() if not v},'complete failure reasons')
        quantitative=all(v for k,v in gates.items() if k!='required_evidence_recorded')
        expected='restructure_or_refuse' if not quantitative else 'eligible_for_credit_committee_review' if gates['required_evidence_recorded'] else 'hold_for_evidence'
        equal(out['recommendation'],expected,'evidence cannot override failed financial gate')


def quiet_run(model,data):
    before=copy.deepcopy(data); capture=io.StringIO()
    with contextlib.redirect_stdout(capture),contextlib.redirect_stderr(capture):
        out=model.run(data)
    equal(capture.getvalue(),'','quiet candidate API')
    equal(data,before,'nonmutating candidate API')
    equal(strict(json.dumps(out,allow_nan=False)),out,'strict JSON result')
    return out


def edited(data,path,value):
    x=copy.deepcopy(data); target=x
    for key in path[:-1]: target=target[key]
    target[path[-1]]=value
    return x


def exercises_and_boundaries(model,data,base):
    global INTERVENTIONS
    def test(x):
        global INTERVENTIONS
        INTERVENTIONS+=1
        out=quiet_run(model,x); fiscal_certificate(x,out)
        return out
    requested,revised=base['proposals']
    rq=requested['scenarios'][0]['rows'][0]; rv=revised['scenarios'][0]['rows'][0]
    equal(rational_fields(rq,'cfads income_if_tax_expense_equals_cash_tax dscr cash_after_service_on_contract_projection'),
          (Q(40),Q(27),Q(10,13),Q(-2)),'exercise1 requested earnings and debt cash')
    equal(rational_fields(rv,'cfads income_if_tax_expense_equals_cash_tax dscr cash_after_service_on_contract_projection'),
          (Q(40),Q(163,5),Q(50,33),Q(118,5)),'exercise1 revised earnings and debt cash')
    equal(Q(base['illustrative_unlevered_valuation']['npv']),Q(42260,1331),'worked positive enterprise NPV distinct from liquidity')
    # Exact floor boundary; follow-on cash moves while year1 is unchanged.
    for extra,passes in [('2.8',True),('2.80000001',False)]:
        x=edited(data,['scenarios',1,'working_capital_increase',1],'7.8' if passes else '7.80000001')
        out=test(x)['proposals'][1]
        equal([Q(r['cash_after_service_on_contract_projection']) for r in out['scenarios'][1]['rows']],
              [Q('13.6'),Q('12.8')-Q(extra),Q('18.4')-Q(extra)],'exercise2 exact balances')
        equal(out['gates']['all_scenario_payment_dates_preserve_cash_floor'],passes,'exercise2 inclusive boundary')
    x=edited(data,['proposals',1,'sponsor_cash'],'20'); out=test(x)['proposals'][1]
    equal(rational_fields(out,'opening_cash_if_sources_received initial_funding_gap_to_cash_floor'),(Q(-30),Q(40)),'exercise3 sources do not follow loan automatically')
    equal([Q(s['minimum_initial_injection_for_cash_floor']) for s in requested['scenarios']],[Q(18),Q(42)],'exercise3 requested scenario injections')
    x=edited(data,['proposals',1,'principal'],['0','0','80']); out=test(x)['proposals'][1]
    equal([Q(r['service']) for r in out['contract_schedule']],[Q('6.4'),Q('6.4'),Q('86.4')],'exercise4 balloon interest and principal')
    equal([Q(r['cash_after_service_on_contract_projection']) for r in out['scenarios'][0]['rows']],[Q('43.6'),Q('79.2'),Q('36.8')],'exercise4 retained surpluses fund balloon')
    equal([Q(r['dscr']) for r in out['scenarios'][0]['rows']],[Q(25,4),Q(105,16),Q(55,108)],'exercise4 ratio still fails at maturity')
    x=edited(data,['collateral','prior_claim'],'25'); x['collateral']['recovery_delay_years']=2
    out=test(x)['proposals'][1]['collateral_branch']
    equal((out['recovery_year'],*rational_fields(out,'lender_recovery nominal_claim_loss recovery_discounted_to_default discounted_claim_shortfall_at_default')),
          (4,Q(45),Q('19.8'),Q(112500,2809),Q(347616,14045)),'exercise5 priority and separate default/receipt dates')
    out=test(edited(data,['collateral','prior_claim'],'100'))
    equal(rational_fields(out['collateral_waterfall'],'workout_cost_paid prior_claim_paid unpaid_prior_claim'),(Q(8),Q(70),Q(30)),'exercise5 senior deficit cap')
    equal(Q(out['proposals'][1]['collateral_branch']['lender_recovery']),0,'exercise5 lender receives no negative cash')
    full=backward_value({1:Q('26.4'),2:Q('34.8'),3:Q('32.4')},Q('.06'))
    bad=backward_value({1:Q('26.4'),3:Q(55)},Q('.06'))
    threshold=(full-80)/(full-bad)
    equal(threshold,Q(122,475),'exercise6 algebraic probability boundary')
    for weight,passes in [('122/475',True),('0.25684211',False),('0.30',False)]:
        out=test(edited(data,['collateral','physical_default_weight'],weight))['proposals'][1]
        equal(out['gates']['physical_scenario_margin_meets_assumed_hurdle'],passes,'exercise6 exact inclusive margin boundary')
        if weight=='0.30': equal(Q(out['collateral_branch']['physical_scenario_margin_over_advance']),Q(-77080,148877),'exercise6 larger physical default weight')
    out=test(edited(data,['collateral','assessment_rate'],'0.08'))['proposals'][1]
    equal(rational_fields(out['collateral_branch'],'promised_receipts_pv physical_scenario_weighted_receipts_pv'),(Q(80),Q(515515,6561)),'exercise6 coupon versus chosen hurdle')
    for face,answer in [(20,(20,100,10,90)),(40,(40,80,20,80)),(100,(100,20,50,50))]:
        prudent=(min(face,120),max(120-face,0))
        gamble=(sum(Q(1,2)*min(face,v) for v in [0,200]),sum(Q(1,2)*max(v-face,0) for v in [0,200]))
        equal(prudent+gamble,answer,'exercise7 independent limited-liability allocations')
        equal(gamble[1]-prudent[1],Q(face,2)-20,'exercise7 incentive threshold')
    equal([Q(1,10)*k-1 for k in [0,10,12]],[-1,0,Q(1,5)],'exercise7 officer private effort advantage')
    equal((Q('.15')-Q('.05'))*40,4,'worked4 lender gross credit-loss benefit')
    equal((Q('.15')-Q('.05'))*40-1,3,'worked4 combined surplus before transfers')
    x=copy.deepcopy(data); x['proposals'][1]['evidence']={key:True for key in x['proposals'][1]['evidence']}
    out=test(x)
    equal(out['proposals'][1]['recommendation'],'eligible_for_credit_committee_review','exercise8 evidence permits review only')
    equal(out['proposals'][0]['recommendation'],'restructure_or_refuse','evidence not permission to ignore cash failure')
    x=edited(data,['scenarios',1,'working_capital_increase',1],'8'); out=test(x)['proposals'][1]
    equal(Q(out['scenarios'][1]['rows'][1]['cash_after_service_on_contract_projection']),Q('9.8'),'exercise8 predicted cash-floor intervention')
    # Additional interventions target omitted-stock/timing and cap failures.
    for path,value in [(['collateral','workout_cost'],'100'),
                       (['collateral','assets',0,'gross_value'],'900'),
                       (['collateral','default_year'],1),
                       (['collateral','default_year'],3),
                       (['collateral','recovery_delay_years'],0),
                       (['scenarios',0,'ebitda',0],'0')]:
        test(edited(data,path,value))
    equal([7+11-9,7+11+8-9-12],[9,5],'retention dated cash')
    equal(Q(30)-Q(15)/Q('1.05'),Q(110,7),'retention discounted recovery gap')


def domain_tests(model,data):
    global REJECTIONS
    cases=[(['proposals',1,'advance'],True),(['proposals',1,'advance'],'1/0'),
           (['proposals',1,'advance'],'8e1'),(['proposals',1,'rate'],'0.50000001'),
           (['proposals',1,'principal'],['80','0','0']),(['proposals',1,'principal'],['20','30','29']),
           (['proposals',1,'evidence','priority_verified'],1),
           (['collateral','default_year'],True),(['collateral','recovery_delay_years'],4),
           (['collateral','assets',1,'id'],'equipment'),(['collateral','physical_default_weight'],'1.00000001'),
           (['collateral','assets',0,'eligible_fraction'],'1.00000001'),
           (['scenarios',0,'id'],'not_base'),(['scenarios',1,'id'],'base'),
           (['scenarios',1,'cash_taxes',0],'-1'),(['policy','minimum_base_dscr'],'0.99')]
    for path,value in cases:
        x=edited(data,path,value); before=copy.deepcopy(x)
        try: model.run(x)
        except ValueError: REJECTIONS+=1
        else: raise RuntimeError('invalid input accepted: '+repr(path))
        equal(x,before,'rejected input preserved')
    # Nonpositive earnings and a funding gap are valid economic failures, not
    # missing/invalid JSON. These cases are included among the financial tests.


def portable_and_guards(data,base):
    global REJECTIONS
    with tempfile.TemporaryDirectory(prefix='v11-c03-peer-') as folder:
        dest=Path(folder); model=dest/MODEL.name; inp=dest/'v11-c03-inputs.json'
        shutil.copy2(MODEL,model); inp.write_text(json.dumps(data))
        for flags in ([],['-O']):
            proc=subprocess.run([sys.executable,*flags,str(model)],cwd='/',capture_output=True,text=True,timeout=20)
            equal((proc.returncode,proc.stderr),(0,''),'isolated default CLI normal/optimized')
            equal(strict(proc.stdout),base,'isolated two-file complete result')
            target=dest/'output.json'
            proc=subprocess.run([sys.executable,*flags,str(model),'--input',str(inp),'--output',str(target)],cwd='/',capture_output=True,text=True,timeout=20)
            equal((proc.returncode,proc.stdout,proc.stderr),(0,'',''),'explicit portable output-file CLI')
            equal(strict(target.read_text()),base,'explicit portable complete output')
            for protected in (inp,model):
                sym=dest/('symlink-'+protected.name); hard=dest/('hardlink-'+protected.name)
                if not sym.exists(): sym.symlink_to(protected)
                if not hard.exists(): hard.hardlink_to(protected)
                original=protected.read_bytes()
                for alias in (protected,sym,hard):
                    proc=subprocess.run([sys.executable,*flags,str(model),'--input',str(inp),'--output',str(alias)],cwd='/',capture_output=True,text=True,timeout=20)
                    require(proc.returncode!=0,'protected direct or inode-alias output rejected')
                    equal(protected.read_bytes(),original,'rejected overwrite preserves bytes')
            for bad in ['{"schema":1,"schema":2}','{"schema":NaN}',json.dumps(edited(data,['proposals',1,'advance'],80))]:
                invalid=dest/'bad.json'; invalid.write_text(bad); target.write_text('preserve')
                proc=subprocess.run([sys.executable,*flags,str(model),'--input',str(invalid),'--output',str(target)],cwd='/',capture_output=True,text=True,timeout=20)
                require(proc.returncode!=0,'malformed input CLI rejected')
                equal(target.read_text(),'preserve','invalid input cannot replace existing output')
                REJECTIONS+=1


class Manuscript(HTMLParser):
    def __init__(self):
        super().__init__(); self.stack=[]; self.ids=[]; self.worked=0; self.lists=[]; self.solving=False; self.prompts=0; self.answers=0; self.sources=set(); self.links=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if 'id' in a: self.ids.append(a['id'])
        if 'worked' in a.get('class','').split(): self.worked+=1
        if tag=='details' and 'solutions' in a.get('class','').split(): self.solving=True
        if tag=='ol': self.lists.append('solutions' if self.solving else 'exercises' if 'exercises' in a.get('class','').split() else '')
        if tag=='li' and self.lists:
            self.prompts+=self.lists[-1]=='exercises'; self.answers+=self.lists[-1]=='solutions'
        if 'data-source' in a: self.sources.add(a['data-source'])
        if tag=='a': self.links.append(a.get('href',''))
        if tag not in ('br','hr','img','input','meta','link'): self.stack.append(tag)
    def handle_endtag(self,tag):
        if not self.stack or self.stack.pop()!=tag: raise RuntimeError('unbalanced manuscript '+tag)
        if tag=='ol': self.lists.pop()
        if tag=='details': self.solving=False


def bindings_and_structure():
    peer=strict((ROOT/'content/reviews/v11-c03-peer.json').read_text())
    expected={'content/chapters/v11-c03.html','scripts/check_v11_c03.py',
              'content/reviews/v11-c03-author.json','content/reviews/v11-c03-sources.json'}
    expected.update('content/projects/v11-c03-'+name for name in ('inputs.json','analysis.py','output.json','README.txt','manifest.json'))
    equal({r['path'] for r in peer['reviewed_hashes']},expected,'all nine frozen author files bound')
    equal(len(peer['reviewed_hashes']),9,'no duplicate reviewed path')
    equal(peer['checker_binding']['path'],'scripts/check_v11_c03_peer.py','own exact checker bound')
    for row in peer['reviewed_hashes']+[peer['checker_binding']]:
        payload=(ROOT/row['path']).read_bytes()
        equal((len(payload),hashlib.sha256(payload).hexdigest()),(row['bytes'],row['sha256']),'peer exact payload '+row['path'])
    author=strict((ROOT/'content/reviews/v11-c03-author.json').read_text())
    equal({r['path'] for r in author['reviewed_hashes']},expected-{'content/reviews/v11-c03-author.json'},'author complete nonself scope')
    for row in author['reviewed_hashes']:
        payload=(ROOT/row['path']).read_bytes()
        equal((len(payload),hashlib.sha256(payload).hexdigest()),(row['bytes'],row['sha256']),'author binding remains current')
    manifest=strict((PROJECT/'v11-c03-manifest.json').read_text())
    equal({r['file'] for r in manifest['files']},{'v11-c03-'+x for x in ('inputs.json','analysis.py','output.json','README.txt')},'four exact lab bindings')
    for row in manifest['files']:
        payload=(PROJECT/row['file']).read_bytes()
        equal((len(payload),hashlib.sha256(payload).hexdigest()),(row['bytes'],row['sha256']),'portable manifest identity')
    doc=Manuscript(); doc.feed((ROOT/'content/chapters/v11-c03.html').read_text())
    equal(doc.stack,[],'balanced complete fragment')
    equal((doc.worked,doc.prompts,doc.answers),(4,8,8),'four worked cases and all eight solved prompts')
    equal(len(doc.ids),len(set(doc.ids)),'unique IDs')
    source=strict((ROOT/'content/reviews/v11-c03-sources.json').read_text())
    equal(doc.sources,{r['id'] for r in source['proposals']},'actual source routes match proposals')
    require(all('v11-c03-'+x in doc.links for x in ('inputs.json','analysis.py','output.json','manifest.json','README.txt')),'five flat portable attachment links')


def check():
    global COUNT, REJECTIONS, INTERVENTIONS
    COUNT=REJECTIONS=INTERVENTIONS=0
    data=strict((PROJECT/'v11-c03-inputs.json').read_text())
    spec=importlib.util.spec_from_file_location('v11_c03_candidate',MODEL)
    model=importlib.util.module_from_spec(spec); capture=io.StringIO()
    with contextlib.redirect_stdout(capture),contextlib.redirect_stderr(capture): spec.loader.exec_module(model)
    equal(capture.getvalue(),'','quiet candidate import')
    base=quiet_run(model,data); fiscal_certificate(data,base)
    equal(base,strict((PROJECT/'v11-c03-output.json').read_text()),'saved output after independent certificates')
    exercises_and_boundaries(model,data,base)
    domain_tests(model,data)
    portable_and_guards(data,base)
    bindings_and_structure()
    result={'chapter':'v11-c03','review':'separate internal peer','status':'passed',
            'comparisons':COUNT,'financial_interventions':INTERVENTIONS,
            'invalid_inputs_rejected':REJECTIONS,'worked_examples_reviewed':4,'exact_prompts_solved':8,
            'frozen_author_payloads_verified':9,'own_checker_bound':True,
            'independent_methods':['principal-maturity tranche cash matrix','cutoff source/use sums and minimal-injection certificate',
                                   'priority conservation/cap/complementarity certificate','backward valuation of dated physical cash streams',
                                   'exact policy and incentive boundaries'],
            'limits':'Separate machine-assisted peer review; original assumptions, current legal rights, real borrower evidence and external human certification remain outside scope.'}
    json.dumps(result,allow_nan=False)
    return result


if __name__=='__main__':
    print(json.dumps(check(),indent=2,allow_nan=False))
