"""Independent bounded arithmetic and portable-contract checks for V11 C09."""
import argparse
from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
from fractions import Fraction as F
import hashlib
from html.parser import HTMLParser
import importlib.util
import io
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
OWNED = ["content/chapters/v11-c09.html"]+["content/projects/v11-c09-"+s for s in ("inputs.json","analysis.py","output.json","manifest.json","README.txt")]+["scripts/check_v11_c09.py","content/reviews/v11-c09-sources.json"]


def wire(x):
    if isinstance(x,F): return str(x)
    if isinstance(x,dict): return {k:wire(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)): return [wire(v) for v in x]
    return x


def quantities(raw):
    return {k:F(v) if type(v) is str and k!='id' else v for k,v in raw.items()}


class Fragment(HTMLParser):
    def __init__(self):
        super().__init__(); self.ids=[]; self.sources=set(); self.links=[]
        self.worked=0; self.exercises=0; self.solutions=0
        self.ex=False; self.sol=False; self.pairs=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if 'id' in a:self.ids.append(a['id'])
        if 'href' in a:self.links.append(a['href'])
        if 'data-source' in a:self.sources.add(a['data-source'])
        if 'worked' in a.get('class','').split():self.worked+=1
        if tag=='ol' and 'exercises' in a.get('class','').split():self.ex=True
        if tag=='details' and 'solutions' in a.get('class','').split():self.sol=True
        if tag=='li':
            self.exercises+=self.ex;self.solutions+=self.sol
            if 'data-solution-for' in a:self.pairs.append(a['data-solution-for'])
    def handle_endtag(self,tag):
        if tag=='ol':self.ex=False
        if tag=='details':self.sol=False


def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    project=root/'content/projects'
    counts=dict(comparisons=0,financial_interventions=0,exporter_states=0,sovereign_states=0,design_certificates=0,api_rejections=0,cli_rejections=0,protected_alias_attempts=0,portable_cli_runs=0,author_bindings=0)
    def need(ok,label):
        counts['comparisons']+=1
        if not ok:raise RuntimeError(label)
    def eq(a,b,label):need(wire(a)==wire(b),label+': '+repr(a)+' != '+repr(wire(b)))
    def qeq(a,b,label):eq(F(a),b,label)
    capture=io.StringIO()
    with redirect_stdout(capture),redirect_stderr(capture):
        spec=importlib.util.spec_from_file_location('c09_author_target',project/'v11-c09-analysis.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    eq(capture.getvalue(),'','quiet import')
    data=json.loads((project/'v11-c09-inputs.json').read_text())
    def run(d):
        before=deepcopy(d);log=io.StringIO()
        with redirect_stdout(log),redirect_stderr(log):out=module.run(d)
        eq(log.getvalue(),'','quiet run');eq(d,before,'input unmodified')
        return out

    # Only public run is called. All oracle quantities below come from original
    # contracts, independent balance identities and active-line certificates.
    def cash_oracle(d,s,h=None,x=F(0)):
        e=quantities(d['exporter']);s=quantities(s);p=quantities(d['parity'])
        h=e['hedge_F'] if h is None else h
        # A foreign deposit buying one F at maturity costs spot/RF in H;
        # its maturity financing charge gives the agreed benchmark strike.
        k=(p['spot_H_per_F']/p['foreign_gross'])*p['home_gross']
        u=e['offshore_cash_H'];n=e['net_receivable_F'];D=e['debt_H'];S=s['spot_H_per_F']
        m=h*s['margin_H_per_hedged_F'];posted=min(m,u+x)
        converted=min(n if s['receipt_before_cutoff'] else F(0),s['conversion_cap_F'])
        transferred=min(S*converted,s['transfer_cap_H'])
        gain=h*k-h*s['fixing_H_per_F']
        receipt=s['positive_settlement_fraction']*max(gain,F(0));liability=max(-gain,F(0))
        available=u+x-posted+transferred+receipt
        forward_short=max(F(0),liability-available);forward_paid=liability-forward_short
        debt_short=max(F(0),D-max(F(0),available-liability));debt_paid=D-debt_short
        cutoff=max(F(0),available-liability-D)
        on_H=S*converted-transferred;late_F=n-converted
        full_early=u-m;full_late=u-m+transferred+receipt-liability-D
        minimum=max(F(0),-full_early,-full_late)
        worth=u+x+n*S+gain-(1-s['positive_settlement_fraction'])*max(gain,F(0))-D
        return locals()

    def exporter_audit(d,s,row,h=None,x=F(0)):
        z=cash_oracle(d,s,h,x)
        expected=dict(hedge_F=z['h'],initial_injection_H=x,margin_required_H=z['m'],margin_posted_H=z['posted'],margin_unposted_H=z['m']-z['posted'],converted_F=z['converted'],transferred_H=z['transferred'],derivative_contract_H=z['gain'],derivative_received_H=z['receipt'],derivative_positive_loss_H=max(z['gain'],F(0))-z['receipt'],derivative_paid_H=z['forward_paid'],derivative_unpaid_H=z['forward_short'],debt_paid_H=z['debt_paid'],debt_unpaid_H=z['debt_short'],cutoff_cash_H=z['cutoff'],later_offshore_cash_H=z['cutoff']+z['posted'],onshore_H=z['on_H'],later_onshore_F=z['late_F'],minimum_initial_injection_H=z['minimum'],terminal_account_value_H=z['worth'],direct_terminal_value_H=z['worth'],value_residual_H=F(0))
        eq(row['id'],s['id'],'export id');eq({k:row[k] for k in expected},expected,'original-contract exporter oracle')
        eq(row['all_cutoffs_met'],x>=z['minimum'],'necessary and sufficient prefix requirement')
        eq(z['cutoff']+z['posted']+z['on_H']+z['late_F']*z['S']-z['forward_short']-z['debt_short'],z['worth'],'independent full inventory/liability conservation')
        trail=row['cash_trail'];eq(len(trail),5,'complete dated trail')
        eq([r['event'] for r in trail],['early_collateral','receipt_conversion_transfer','derivative_settles_before_debt','external_debt_cutoff','later_collateral_and_receipt_release'],'contract event order')
        expected_cash=[z['u']+x-z['posted'],z['u']+x-z['posted']+z['transferred'],max(F(0),z['available']-z['liability']),z['cutoff'],z['cutoff']+z['posted']]
        eq([r['offshore_cash_H'] for r in trail],expected_cash,'all offshore cash snapshots')
        need(all(F(r['offshore_cash_H'])>=0 for r in trail),'no negative actual cash')
        eq(trail[0]['segregated_collateral_H'],z['posted'],'collateral stays an asset')
        eq({k:trail[1][k] for k in ('onshore_H','onshore_F','late_receivable_F')},dict(onshore_H=z['on_H'],onshore_F=(z['n'] if z['s']['receipt_before_cutoff'] else F(0))-z['converted'],late_receivable_F=F(0) if z['s']['receipt_before_cutoff'] else z['n']),'location and delayed claim')
        eq({k:trail[2][k] for k in ('received_H','paid_H','unpaid_H')},dict(received_H=z['receipt'],paid_H=z['forward_paid'],unpaid_H=z['forward_short']),'derivative payment priority')
        eq((trail[3]['debt_paid_H'],trail[3]['debt_unpaid_H']),(z['debt_paid'],z['debt_short']),'debt obligation retained')
        eq((trail[4]['onshore_H'],trail[4]['onshore_F']),(z['on_H'],z['late_F']),'late assets released without invented transfer')
        counts['exporter_states']+=1

    def sovereign_audit(d,s,row):
        v=quantities(d['sovereign']);s=quantities(s)
        H=v['cash_after_primary_spending_H'];L=v['local_due_H'];S=s['spot_H_per_F']
        local_short=max(F(0),L-H);H_after=max(F(0),H-L)
        bought=min(H_after/S,s['conversion_cap_F']);closing_H=H_after-bought*S
        resources=v['reserves_F']-v['blocked_reserves_F']+s['export_fiscal_receipt_F']+s['new_borrowing_F']+bought
        obligations=s['essential_imports_F']+v['foreign_due_F'];available=resources-v['reserve_floor_F']
        import_short=max(F(0),s['essential_imports_F']-available)
        debt_short=min(v['foreign_due_F'],max(F(0),obligations-available))
        imports=s['essential_imports_F']-import_short;paid=v['foreign_due_F']-debt_short
        close_F=resources-imports-paid
        old=v['foreign_due_F']+v['other_foreign_principal_F'];closing=old+s['new_borrowing_F']-paid
        direct=S*closing-v['opening_spot_H_per_F']*old
        valuation=(S-v['opening_spot_H_per_F'])*old;transactions=S*(s['new_borrowing_F']-paid)
        expected=dict(local_paid_H=L-local_short,local_unpaid_H=local_short,bought_F=bought,dealer_receipt_H=bought*S,closing_cash_H=closing_H,before_external_payments_F=resources,imports_paid_F=imports,imports_unpaid_F=import_short,debt_paid_F=paid,debt_unpaid_F=debt_short,closing_free_reserves_F=close_F,blocked_released_only_later_F=v['blocked_reserves_F'],minimum_external_topup_F=max(F(0),obligations-available),closing_foreign_principal_F=closing,new_loan_later_due_F=s['new_borrowing_F']*v['new_loan_gross'],foreign_debt_value_change_H=direct,foreign_debt_revaluation_H=valuation,foreign_debt_transactions_H=transactions,cash_residual_F=F(0),debt_value_residual_H=F(0))
        eq(row['id'],s['id'],'sovereign id');eq({k:row[k] for k in expected},expected,'independent sovereign deficit/stock oracle')
        eq(row['all_current_payments_met'],local_short==0 and import_short==0 and debt_short==0,'separate currency cutoffs')
        eq(direct,valuation+transactions,'debt value decomposition')
        eq(H,L-local_short+bought*S+closing_H,'H dealer/local-service conservation')
        eq(resources,imports+paid+close_F,'F payments and reserve conservation')
        need(close_F>=v['reserve_floor_F'] and closing_H>=0,'executed reserve floor and H cash')
        eq(closing,v['other_foreign_principal_F']+debt_short+s['new_borrowing_F'],'arrears never disappear')
        counts['sovereign_states']+=1

    def design_audit(d,out):
        design=out['hedge_design'];h=F(design['hedge_F']);x=F(design['minimum_common_injection_H'])
        n=F(d['exporter']['net_receivable_F']);need(0<=h<=n and x>=0,'compact design domain')
        selected=[s for s in d['export_scenarios'] if s['id'] in d['hedge_design_scenarios']]
        # Recover affine coefficients independently from the actual full-payment
        # cash prefixes at h=0 and1, not from the model's reported coefficients.
        lines=[('nonnegative_injection',F(0),F(0))]
        for s in selected:
            z0=cash_oracle(d,s,F(0));z1=cash_oracle(d,s,F(1))
            for key,field in (('early','full_early'),('late','full_late')):
                b=-z0[field];a=z0[field]-z1[field];lines.append((s['id']+':'+key,a,b))
        eq(design['constraints'],[dict(label=k,slope=a,intercept=b) for k,a,b in lines],'independent cash-derived design constraints')
        values=[a*h+b for _,a,b in lines]
        eq(x,max(values),'primal feasible maximum at chosen h')
        active=[(a,b) for _,a,b in lines if a*h+b==x]
        eq(design['active_constraints'],[k for k,a,b in lines if a*h+b==x],'binding constraints')
        # Convex support certificate proves global optimality without duplicating
        # the implementation's pairwise-intersection search.
        if n==0: eq(h,F(0),'singleton design interval')
        elif h==0: need(any(a>=0 for a,b in active),'left endpoint supporting line')
        elif h==n: need(any(a<=0 for a,b in active),'right endpoint supporting line')
        else:
            low=min(a for a,b in active);high=max(a for a,b in active)
            need(low<=0<=high,'interior supporting slopes straddle zero')
            if low<0<high:
                b_lo=next(b for a,b in active if a==low);b_hi=next(b for a,b in active if a==high)
                weight=high/(high-low)
                eq(weight*low+(1-weight)*high,F(0),'dual slope cancellation')
                eq(weight*b_lo+(1-weight)*b_hi,x,'global affine lower bound equals feasible value')
            else:need(any(a==0 and b==x for a,b in active),'constant support')
        need(type(design['candidate_count']) is int and 1<=design['candidate_count']<=38,'bounded finite search size')
        eq(design['selected_scenarios'],d['hedge_design_scenarios'],'design selection explicit')
        eq(design['hedge_interval_F'],[F(0),n],'hedge interval')
        eq(len(design['funded_selected_scenarios']),len(selected),'selected trails complete')
        for s,row in zip(selected,design['funded_selected_scenarios']):
            exporter_audit(d,s,row,h,x);need(row['all_cutoffs_met'],'funded selected scenario passes')
        counts['design_certificates']+=1

    def other_audit(d,out):
        w=d['willingness'];Y=F(w['resources_H']);C=F(w['default_cost_H']);D=F(w['promised_F']);cap=F(w['capacity_F'])
        eq(len(out['willingness']),len(w['spots_H_per_F']),'choice rows')
        for s,row in zip(w['spots_H_per_F'],out['willingness']):
            s=F(s);feasible=cap>=D
            eq((row['spot_H_per_F'],row['full_payment_feasible'],row['utility_repay_if_feasible'],row['utility_default']),(s,feasible,Y-s*D,Y-C),'separate capacity and preference scores')
            eq(row['choice'],'repay' if feasible and s*D<=C else 'default_or_restructure','feasible choice with tie')
        r=quantities(d['rescheduling']);old=r['due_F']*r['discount_one'];new=r['replacement_F']*r['discount_two']
        eq(out['rescheduling'],dict(original_PV_F=old,replacement_PV_F=new,creditor_PV_change_F=new-old,first_date_cash_relief_F=r['due_F'],second_date_added_due_F=r['replacement_F']),'dated PV is independent of cash relief')

    out=run(data)
    eq(out,json.loads((project/'v11-c09-output.json').read_text()),'entire preserved report')
    p=quantities(data['parity']);k=p['spot_H_per_F']/p['foreign_gross']*p['home_gross']
    qeq(out['parity']['forward_H_per_F'],k,'financed foreign deposit price')
    qeq(out['parity']['full_hedge_gross_H'],F(data['exporter']['net_receivable_F'])*k,'gross full-hedge receipt')
    eq(len(out['exporter']),len(data['export_scenarios']),'all export scenarios')
    eq(len(out['sovereign']),len(data['sovereign_scenarios']),'all sovereign scenarios')
    for s,row in zip(data['export_scenarios'],out['exporter']):exporter_audit(data,s,row)
    for s,row in zip(data['sovereign_scenarios'],out['sovereign']):sovereign_audit(data,s,row)
    design_audit(data,out);other_audit(data,out)

    def variant(changes,export_rows=(),sovereign_rows=(),design=False,other=False):
        d=deepcopy(data)
        for path,value in changes:
            target=d
            for part in path[:-1]:target=target[part]
            target[path[-1]]=value
        r=run(d)
        for j in export_rows:exporter_audit(d,d['export_scenarios'][j],r['exporter'][j])
        for j in sovereign_rows:sovereign_audit(d,d['sovereign_scenarios'][j],r['sovereign'][j])
        if design:design_audit(d,r)
        if other:other_audit(d,r)
        counts['financial_interventions']+=1
        return r
    variant([(('exporter','hedge_F'),'0')],export_rows=(1,2,5),design=True)
    variant([(('exporter','net_receivable_F'),'0'),(('exporter','hedge_F'),'0')],export_rows=(0,6),design=True)
    partial=variant([(('export_scenarios',2,'fixing_H_per_F'),'100')],export_rows=(2,),design=True)
    need(F(partial['exporter'][2]['derivative_unpaid_H'])>0 and F(partial['exporter'][2]['debt_paid_H'])==0,'unpaid negative hedge has priority')
    variant([(('export_scenarios',5,'positive_settlement_fraction'),'0')],export_rows=(5,))
    variant([(('export_scenarios',5,'positive_settlement_fraction'),'1')],export_rows=(5,))
    variant([(('export_scenarios',0,'receipt_before_cutoff'),False)],export_rows=(0,))
    variant([(('export_scenarios',4,'conversion_cap_F'),'0')],export_rows=(4,))
    variant([(('export_scenarios',3,'transfer_cap_H'),'0')],export_rows=(3,))
    fully_posted=variant([(('exporter','offshore_cash_H'),'18')],export_rows=(2,),design=True)
    eq((fully_posted['exporter'][2]['margin_unposted_H'],fully_posted['exporter'][2]['debt_unpaid_H']),('0','4/17'),'funded margin still leaves later shortage')
    variant([(('parity','home_gross'),'19/20'),(('parity','foreign_gross'),'1')],export_rows=(0,1,2),design=True)
    local=variant([(('sovereign','cash_after_primary_spending_H'),'20')],sovereign_rows=(0,2))
    qeq(local['sovereign'][2]['local_unpaid_H'],F(16),'foreign topup cannot pay earlier H shortage')
    grant=variant([(('sovereign','reserves_F'),'50')],sovereign_rows=(2,))
    loan=variant([(('sovereign_scenarios',2,'new_borrowing_F'),'20')],sovereign_rows=(2,))
    eq((grant['sovereign'][2]['debt_paid_F'],loan['sovereign'][2]['debt_paid_F']),('40','40'),'same current grant and loan funding')
    eq((grant['sovereign'][2]['closing_foreign_principal_F'],loan['sovereign'][2]['closing_foreign_principal_F']),('60','80'),'financing source changes future principal')
    released=variant([(('sovereign','blocked_reserves_F'),'0')],sovereign_rows=(2,))
    qeq(released['sovereign'][2]['debt_unpaid_F'],F(12),'early reserve release only partly closes gap')
    variant([(('sovereign','reserve_floor_F'),'0')],sovereign_rows=(2,))
    variant([(('willingness','spots_H_per_F'),['2','3','9/4']), (('rescheduling','replacement_F'),'380/9')],other=True)
    variant([(('willingness','capacity_F'),'39'),(('willingness','default_cost_H'),'200')],other=True)
    variant([(('hedge_design_scenarios',),['weak_currency','margin_squeeze','joint','receipt_delay'])],design=True)
    boundary_cash=F(12)+F(818,17)
    boundary=variant([(('exporter','offshore_cash_H'),str(boundary_cash))],export_rows=(5,))
    below=variant([(('exporter','offshore_cash_H'),str(boundary_cash-F(1,100)))],export_rows=(5,))
    need(boundary['exporter'][5]['all_cutoffs_met'],'exact joint funding boundary succeeds')
    qeq(below['exporter'][5]['debt_unpaid_H'],F(1,100),'one cent below joint boundary fails by one cent')
    flat=variant([(('exporter','offshore_cash_H'),'1000')],design=True)
    eq((flat['hedge_design']['hedge_F'],flat['hedge_design']['minimum_common_injection_H']),('0','0'),'smallest hedge on a flat minimum')

    # Every nontrivial printed result is calculated independently, including
    # results that are not outputs of the laboratory itself.
    html=(root/'content/chapters/v11-c09.html').read_text()
    gross=80*k;surplus=12+gross-100;weak=80*(k-F(4,5));joint=80*(k-F(9,10))
    transfer_debt=100-(8+40+weak);delay=100-(8+weak)
    h=F(36)/(F(9,40)+F(27,68));x=F(9,40)*h-12
    printed={
        '106/85':k,'1696/17':gross,'200/17':surplus,'64/17':gross-96,'4/17':100-gross,
        '608/17':weak,'1832/17':8+64+weak,'132/17':8+64+weak-100,'276/17':transfer_debt,
        '1424/17':8+40+weak,'818/17':100-(6+32+joint/2),'172/17':100-12-64-joint/2,
        '472/17':joint,'236/17':joint/2,'882/17':6+32+joint/2,'344/17':80*(F(3,2)-k),
        '106/17':18+100+80*(F(3,2)-k)-12-120,'956/17':delay,'744/17':8+weak,
        '27/68':k-F(4,5)-F(1,20),'2720/47':h,'48/47':x,'428/47':12-h/20,
        '204/47':32-F(65,136)*h,'1040/47':80-h,'30/47':F(27,68)/(F(27,68)+F(9,40)),
        '17/47':F(9,40)/(F(27,68)+F(9,40)),'9/4':F(90,40),'198/5':44*F(9,10),
        '8/5':44*F(9,10)-40*F(19,20),'380/9':40*F(19,20)/F(9,10),
        '663/5':102*F(13,10),'636/5':120*F(53,50),'27/5':102*F(13,10)-120*F(53,50),
        '612/5':102*F(6,5),'24/5':120*F(53,50)-102*F(6,5),'208/17':transfer_debt-4,
        '38/85':k-F(4,5),'5/6':1/F(6,5),'2/3':1/F(3,2)}
    for literal,value in printed.items():eq(F(literal),value,'independent printed result '+literal);need(literal in html,'printed result present '+literal)
    constants={'1/2','1/20','1/4','1/5','11/10','13/10','19/20','3/2','3/4','3/40','4/5','51/50','53/50','6/5','9/10','9/40','9/5'}
    tokens=set(re.findall(r'(?<![\d.])\d+/\d+(?!\d|\.\d)',html))
    eq(tokens-set(printed),constants,'all other printed fractions are declared inputs/probabilities/quote changes')
    eq((F(3,2)/F(6,5)-1,(1/F(3,2))/(1/F(6,5))-1),(F(1,4),-F(1,5)),'finite inverse quote changes')
    states=[(F(3,4),F(80)),(F(1,4),F(144))];mean=sum(p*y for p,y in states)
    eq(mean,F(96),'physical expected receipts');eq(sum(p*(y-mean)**2 for p,y in states),F(768),'physical variance in H squared')
    for text,value,places in [('1.247059',k,6),('99.764706',gross,6),('3.764706',gross-96,6),('57.872340',h,6),('1.021277',x,6)]:
        need(text in html and abs(F(text)-value)<=F(1,2*10**places),'printed rounding '+text)

    invalid=[
        (('schema',),True),(('extra',),'0'),(('parity','home_gross'),'0'),(('parity','foreign_gross'),'201/100'),(('parity','spot_H_per_F'),'0'),
        (('exporter','offshore_cash_H'),12),(('exporter','offshore_cash_H'),True),(('exporter','offshore_cash_H'),'NaN'),(('exporter','offshore_cash_H'),'1e2'),
        (('exporter','offshore_cash_H'),' 12'),(('exporter','offshore_cash_H'),'+12'),(('exporter','offshore_cash_H'),'01'),(('exporter','offshore_cash_H'),'1/0'),
        (('exporter','offshore_cash_H'),'1/1000000000'),(('exporter','offshore_cash_H'),'0.123456789'),(('exporter','offshore_cash_H'),'-1'),(('exporter','offshore_cash_H'),'10001'),
        (('exporter','hedge_F'),'81'),(('export_scenarios',),[]),(('export_scenarios',0,'id'),'Not-valid'),(('export_scenarios',1,'id'),'clear'),
        (('export_scenarios',0,'receipt_before_cutoff'),1),(('export_scenarios',0,'positive_settlement_fraction'),'101/100'),(('export_scenarios',0,'margin_H_per_hedged_F'),'3'),
        (('export_scenarios',0,'spot_H_per_F'),'101'),(('export_scenarios',0,'fixing_H_per_F'),'0'),(('export_scenarios',0,'transfer_cap_H'),'-1'),
        (('hedge_design_scenarios',),['clear','clear']),(('hedge_design_scenarios',),['missing']),(('hedge_design_scenarios',),['clear']*5),
        (('sovereign','blocked_reserves_F'),'27'),(('sovereign','new_loan_gross'),'0'),(('sovereign_scenarios',),[]),
        (('sovereign_scenarios',0,'new_borrowing_F'),'10001'),(('sovereign_scenarios',0,'spot_H_per_F'),'-1'),
        (('willingness','spots_H_per_F'),[]),(('willingness','capacity_F'),'-1'),(('rescheduling','discount_one'),'0'),(('rescheduling','replacement_F'),44)]
    for path,value in invalid:
        d=deepcopy(data);target=d
        for key in path[:-1]:target=target[key]
        target[path[-1]]=value
        before=deepcopy(d);log=io.StringIO();rejected=False
        with redirect_stdout(log),redirect_stderr(log):
            try:module.run(d)
            except ValueError:rejected=True
        need(rejected,'invalid API path '+repr(path));eq(log.getvalue(),'','quiet invalid API');eq(d,before,'invalid input not mutated')
        counts['api_rejections']+=1

    # Public CLI and real filesystem alias behavior, never original files.
    with tempfile.TemporaryDirectory(prefix='v11-c09-check-') as temporary:
        folder=Path(temporary);package=folder/'portable';package.mkdir();away=folder/'away';away.mkdir()
        model=package/'v11-c09-analysis.py';inp=package/'v11-c09-inputs.json'
        shutil.copy2(project/model.name,model);shutil.copy2(project/inp.name,inp)
        def cli(args,optimized=False):
            return subprocess.run([sys.executable,'-B']+(['-O'] if optimized else [])+[str(model)]+args,cwd=away,capture_output=True,text=True,timeout=25)
        for optimized in (False,True):
            proc=cli([],optimized);eq((proc.returncode,proc.stdout,proc.stderr),(0,'',''),'quiet portable default CLI');eq(json.loads((package/'v11-c09-output.json').read_text()),out,'default exact output');counts['portable_cli_runs']+=1
            target=folder/'explicit.json';proc=cli(['--input',str(inp),'--output',str(target)],optimized)
            eq((proc.returncode,proc.stdout,proc.stderr),(0,'',''),'quiet explicit CLI');eq(json.loads(target.read_text()),out,'explicit exact output');counts['portable_cli_runs']+=1
            for protected in (inp,model):
                original=protected.read_bytes();(package/'subdir').mkdir(exist_ok=True)
                for kind in ('direct','resolved','symlink','hardlink'):
                    if kind=='direct':alias=protected
                    elif kind=='resolved':alias=package/'subdir'/'..'/protected.name
                    else:
                        alias=package/('alias-'+kind)
                        if kind=='symlink':alias.symlink_to(protected)
                        else:alias.hardlink_to(protected)
                    proc=cli(['--input',str(inp),'--output',str(alias)],optimized)
                    eq(proc.returncode,2,'actual output alias rejected');need('overwrite' in proc.stderr,'specific alias diagnostic');eq(proc.stdout,'','alias emits no report');eq(protected.read_bytes(),original,'protected bytes retained')
                    if kind in ('symlink','hardlink'):alias.unlink()
                    counts['protected_alias_attempts']+=1
            for bad in ('{"schema":1,"schema":1}', '{"schema":NaN}', '[]', ' '*150001):
                bad_path=folder/'bad.json';bad_path.write_text(bad);target.write_text('PRESERVE')
                proc=cli(['--input',str(bad_path),'--output',str(target)],optimized)
                eq(proc.returncode,2,'invalid JSON/size CLI');eq(proc.stdout,'','invalid CLI quiet stdout');need(bool(proc.stderr),'invalid CLI explains');eq(target.read_text(),'PRESERVE','invalid input does not overwrite report');counts['cli_rejections']+=1

    parsed=Fragment();parsed.feed(html)
    eq((parsed.worked,parsed.exercises,parsed.solutions),(4,8,8),'worked/exercise/solution structure')
    eq(len(parsed.ids),len(set(parsed.ids)),'unique manuscript ids')
    eq(parsed.pairs,['v11-c09-ex'+str(i) for i in range(1,9)],'exact solution pairs')
    need('Teach-back and delayed retention' in html,'answered teaching and delayed review')
    flat=['v11-c09-'+s for s in ('inputs.json','analysis.py','output.json','manifest.json','README.txt')]
    for filename in flat:need(filename in parsed.links and 'projects/'+filename not in parsed.links,'flat reader asset '+filename)
    source_rows=json.loads((root/'content/reviews/v11-c09-sources.json').read_text())
    eq(parsed.sources,{r['id'] for r in source_rows},'exact scoped source proposals')
    manifest=json.loads((project/'v11-c09-manifest.json').read_text())
    eq(manifest['schema'],'v11-c09-manifest-1','manifest schema')
    expected_files=['v11-c09-'+s for s in ('inputs.json','analysis.py','output.json','README.txt')]
    eq([r['file'] for r in manifest['files']],expected_files,'exact four portable payloads')
    for row in manifest['files']:
        raw=(project/row['file']).read_bytes();eq((row['bytes'],row['sha256']),(len(raw),hashlib.sha256(raw).hexdigest()),'manifest payload '+row['file'])
    review=json.loads((root/'content/reviews/v11-c09-author.json').read_text())
    eq({r['path'] for r in review['reviewed_hashes']},set(OWNED),'exact eight author nonself bindings')
    eq(len(review['reviewed_hashes']),8,'no duplicate author bindings')
    for row in review['reviewed_hashes']:
        raw=(root/row['path']).read_bytes();eq((row['bytes'],row['sha256']),(len(raw),hashlib.sha256(raw).hexdigest()),'author payload '+row['path']);counts['author_bindings']+=1
    return dict(chapter='v11-c09',status='passed',**counts)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',type=Path)
    args=parser.parse_args(argv);print(json.dumps(check(args.root),sort_keys=True));return 0


if __name__=='__main__':raise SystemExit(main())
