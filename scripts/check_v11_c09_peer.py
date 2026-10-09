"""Separate machine-assisted peer checks for frozen V11-C09.

Only the model's public run API is used. Currency-pocket journals and elimination
of hedge interval inequalities supply original-contract oracles. No author helper
or checker is a numerical oracle. Quiet check() is portable and -O independent.
"""
import contextlib
import copy
from fractions import Fraction as F
import hashlib
from html.parser import HTMLParser
import io
import json
import os
from pathlib import Path
import re
import runpy
import shutil
import subprocess
import sys
import tempfile

AUTHOR = ['content/chapters/v11-c09.html']+['content/projects/v11-c09-'+s for s in
    ('inputs.json','analysis.py','output.json','manifest.json','README.txt')]+[
    'scripts/check_v11_c09.py','content/reviews/v11-c09-author.json','content/reviews/v11-c09-sources.json']
SELF = 'scripts/check_v11_c09_peer.py'
REVIEW = 'content/reviews/v11-c09-peer.json'
COUNTS = {}


def need(ok, label):
    COUNTS['comparisons'] += 1
    if not ok:
        raise ValueError('v11-c09 peer: '+label)


def encode(x):
    if isinstance(x,F): return str(x)
    if isinstance(x,dict): return {k:encode(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)): return [encode(v) for v in x]
    return x


def eq(got, wanted, label):
    got=encode(got)
    wanted=encode(wanted)
    need(got==wanted, label+'; got '+repr(got)+' expected '+repr(wanted))


def exact(got, wanted, label):
    need(F(got)==wanted,label)


def strict(text):
    def pairs(items):
        result={}
        for k,v in items:
            if k in result: raise ValueError('duplicate JSON key')
            result[k]=v
        return result
    def bad(x): raise ValueError('nonfinite JSON constant '+x)
    return json.loads(text,object_pairs_hook=pairs,parse_constant=bad)


def q(raw):
    return {k:F(v) if type(v) is str and k!='id' else v for k,v in raw.items()}


def mutate(data, edits):
    data=copy.deepcopy(data)
    for path,value in edits:
        target=data
        for step in path[:-1]: target=target[step]
        target[path[-1]]=value
    return data


def strike(data):
    p=q(data['parity'])
    # Buy the deposit delivering one F, then finance that cost to maturity.
    deposit_price=p['spot_H_per_F']/p['foreign_gross']
    return deposit_price*p['home_gross']


def exporter_journal(data, scenario, hedge=None, injection=F(0)):
    e=q(data['exporter']); s=q(scenario); k=strike(data)
    h=e['hedge_F'] if hedge is None else hedge
    S=s['spot_H_per_F']; n=e['net_receivable_F']; D=e['debt_H']; u=e['offshore_cash_H']
    gross=h*k-h*s['fixing_H_per_F']
    negative=-gross if gross<0 else F(0)
    positive=gross if gross>0 else F(0)
    received=positive*s['positive_settlement_fraction']
    # Separate actual pockets, an unarrived claim and two surviving liabilities.
    wallet={'off':u+injection,'collateral':F(0),'on_H':F(0),'on_F':F(0),'late_F':n}
    liabilities={'ndf':negative,'debt':D}
    def shift(source,destination,amount):
        need(amount>=0 and wallet[source]>=amount,'funded internal transfer '+source)
        wallet[source]-=amount; wallet[destination]+=amount
    def pay(claim):
        available=wallet['off']
        amount=liabilities[claim] if available>=liabilities[claim] else available
        wallet['off']-=amount; liabilities[claim]-=amount
        need(wallet['off']>=0 and liabilities[claim]>=0,'no negative cash or disappearing claim')
        return amount
    margin=h*s['margin_H_per_hedged_F']
    posted=margin if wallet['off']>=margin else wallet['off']
    shift('off','collateral',posted)
    trail=[dict(event='early_collateral',offshore_cash_H=wallet['off'],segregated_collateral_H=posted)]
    if s['receipt_before_cutoff']: shift('late_F','on_F',n)
    converted=wallet['on_F'] if wallet['on_F']<=s['conversion_cap_F'] else s['conversion_cap_F']
    wallet['on_F']-=converted; wallet['on_H']+=converted*S
    transfer=wallet['on_H'] if wallet['on_H']<=s['transfer_cap_H'] else s['transfer_cap_H']
    shift('on_H','off',transfer)
    trail.append(dict(event='receipt_conversion_transfer',offshore_cash_H=wallet['off'],onshore_H=wallet['on_H'],onshore_F=wallet['on_F'],late_receivable_F=wallet['late_F']))
    wallet['off']+=received
    nd_paid=pay('ndf')
    trail.append(dict(event='derivative_settles_before_debt',offshore_cash_H=wallet['off'],received_H=received,paid_H=nd_paid,unpaid_H=liabilities['ndf']))
    debt_paid=pay('debt'); cutoff=wallet['off']
    trail.append(dict(event='external_debt_cutoff',offshore_cash_H=cutoff,debt_paid_H=debt_paid,debt_unpaid_H=liabilities['debt']))
    shift('collateral','off',wallet['collateral'])
    shift('late_F','on_F',wallet['late_F'])
    trail.append(dict(event='later_collateral_and_receipt_release',offshore_cash_H=wallet['off'],onshore_F=wallet['on_F'],onshore_H=wallet['on_H']))
    actual_value=wallet['off']+wallet['on_H']+S*wallet['on_F']-sum(liabilities.values())
    direct=u+injection+S*n+gross-(positive-received)-D
    exact(actual_value,direct,'currency/location financial conservation')
    # Fund the two stipulated prefixes using FULL posting, not the partial trail.
    prefix0=u-margin
    prefix1=prefix0+transfer+received-negative-D
    required=max(F(0),-prefix0,-prefix1)
    all_met=posted==margin and not any(liabilities.values())
    need(all_met==(injection>=required),'independent necessary/sufficient early contribution')
    COUNTS['exporter_journals']+=1
    return encode(dict(id=s['id'],hedge_F=h,initial_injection_H=injection,margin_required_H=margin,
        margin_posted_H=posted,margin_unposted_H=margin-posted,converted_F=converted,transferred_H=transfer,
        derivative_contract_H=gross,derivative_received_H=received,derivative_positive_loss_H=positive-received,
        derivative_paid_H=nd_paid,derivative_unpaid_H=liabilities['ndf'],debt_paid_H=debt_paid,debt_unpaid_H=liabilities['debt'],
        cutoff_cash_H=cutoff,later_offshore_cash_H=wallet['off'],onshore_H=wallet['on_H'],later_onshore_F=wallet['on_F'],
        minimum_initial_injection_H=required,all_cutoffs_met=all_met,terminal_account_value_H=actual_value,
        direct_terminal_value_H=direct,value_residual_H=actual_value-direct,cash_trail=trail))


def full_prefixes(data,s,h):
    e=q(data['exporter']);s=q(s)
    margin=h*s['margin_H_per_hedged_F']
    arriving=e['net_receivable_F']*int(s['receipt_before_cutoff'])
    bought=arriving if arriving<=s['conversion_cap_F'] else s['conversion_cap_F']
    delivered=min(bought*s['spot_H_per_F'],s['transfer_cap_H'])
    settlement=h*(strike(data)-s['fixing_H_per_F'])
    executed=settlement*s['positive_settlement_fraction'] if settlement>=0 else settlement
    early=e['offshore_cash_H']-margin
    return early,early+delivered+executed-e['debt_H']


def hedge_elimination(data,report):
    n=F(data['exporter']['net_receivable_F'])
    selected=[s for s in data['export_scenarios'] if s['id'] in data['hedge_design_scenarios']]
    lines=[('nonnegative_injection',F(0),F(0))]
    for s in selected:
        v0=full_prefixes(data,s,F(0));v1=full_prefixes(data,s,F(1))
        for i,label in enumerate(('early','late')):
            lines.append((s['id']+':'+label,v0[i]-v1[i],-v0[i]))
    # Eliminate h from x >= a*h+b and 0<=h<=n. A positive slope bounds
    # h above; a negative slope bounds h below. Pairwise lower<=upper
    # conditions, plus the box endpoints, are necessary AND sufficient.
    positive=[(a,b) for _,a,b in lines if a>0]
    negative=[(a,b) for _,a,b in lines if a<0]
    bounds=[b for _,a,b in lines if a==0]
    bounds += [b for a,b in positive] + [a*n+b for a,b in negative]
    bounds += [(ap*bn-an*bp)/(ap-an) for an,bn in negative for ap,bp in positive]
    x=max(bounds)
    lower=max([F(0)]+[(x-b)/a for a,b in negative])
    upper=min([n]+[(x-b)/a for a,b in positive])
    need(0<=lower<=upper<=n,'nonempty exact hedge interval at minimum cash')
    need(all(a*lower+b<=x for _,a,b in lines),'constructed smallest hedge is feasible')
    h=lower
    eq(report['constraints'],[dict(label=label,slope=a,intercept=b) for label,a,b in lines],'cash-prefix affine coefficients')
    eq(report['hedge_F'],h,'interval elimination minimum and smallest-hedge tie')
    eq(report['minimum_common_injection_H'],x,'global minimum from eliminated inequalities')
    eq(report['hedge_interval_F'],[F(0),n],'stated hedge box')
    eq(report['selected_scenarios'],data['hedge_design_scenarios'],'declared design selection')
    eq(report['active_constraints'],[label for label,a,b in lines if a*h+b==x],'exact active set')
    eq(report['tie_rule'],'smallest hedge among minimum-injection candidates','documented tie behavior')
    need(type(report['candidate_count']) is int and 1<=report['candidate_count']<=38,'finite implementation search bounded')
    eq(len(report['funded_selected_scenarios']),len(selected),'all selected funded trails')
    for s,row in zip(selected,report['funded_selected_scenarios']):
        eq(row,exporter_journal(data,s,h,x),'design funding meets actual contract '+s['id'])
        need(row['all_cutoffs_met'],'constructed funding closes both cutoffs')
    COUNTS['design_certificates']+=1
    return h,x,lines


def sovereign_journal(data,scenario):
    v=q(data['sovereign']);s=q(scenario);spot=s['spot_H_per_F']
    home=v['cash_after_primary_spending_H']; local_due=v['local_due_H']
    local_paid=min(home,local_due);home-=local_paid
    bought=min(s['conversion_cap_F'],home/spot);dealer=bought*spot;home-=dealer
    reserve=v['reserves_F']-v['blocked_reserves_F']
    # Receipt pockets are counted exactly once; the blocked account never enters.
    sources=[reserve,s['export_fiscal_receipt_F'],s['new_borrowing_F'],bought]
    available=sum(sources); pool=available-v['reserve_floor_F']
    need(pool>=0,'opening floor and nonnegative settled sources')
    payments=[]
    for due in (s['essential_imports_F'],v['foreign_due_F']):
        payment=min(due,pool);pool-=payment;payments.append(payment)
    imports_paid,debt_paid=payments
    finalF=pool+v['reserve_floor_F']
    debt_arrears=v['foreign_due_F']-debt_paid
    # Close principal by named surviving claims, independently of B0+N-p.
    debt_components=[debt_arrears,v['other_foreign_principal_F'],s['new_borrowing_F']]
    closing_principal=sum(debt_components)
    opening=v['foreign_due_F']+v['other_foreign_principal_F']
    value_change=spot*closing_principal-v['opening_spot_H_per_F']*opening
    revalued=(spot-v['opening_spot_H_per_F'])*opening
    transacted=spot*s['new_borrowing_F']-spot*debt_paid
    exact(v['cash_after_primary_spending_H'],local_paid+dealer+home,'sovereign H uses and dealer receipt')
    exact(sum(sources),sum(payments)+finalF,'sovereign F sources/uses and preserved floor')
    exact(value_change,revalued+transacted,'translated old-principal and transaction bridge')
    need(home>=0 and finalF>=v['reserve_floor_F'],'actual nonnegative currency balances')
    COUNTS['sovereign_journals']+=1
    return encode(dict(id=s['id'],policy='conditional capacity ledger: local service, conversion, essential imports, foreign debt; preserve floor',
        local_paid_H=local_paid,local_unpaid_H=local_due-local_paid,bought_F=bought,dealer_receipt_H=dealer,closing_cash_H=home,
        before_external_payments_F=available,imports_paid_F=imports_paid,imports_unpaid_F=s['essential_imports_F']-imports_paid,
        debt_paid_F=debt_paid,debt_unpaid_F=debt_arrears,closing_free_reserves_F=finalF,
        blocked_released_only_later_F=v['blocked_reserves_F'],minimum_external_topup_F=max(F(0),v['reserve_floor_F']+s['essential_imports_F']+v['foreign_due_F']-available),
        closing_foreign_principal_F=closing_principal,new_loan_later_due_F=s['new_borrowing_F']*v['new_loan_gross'],
        foreign_debt_value_change_H=value_change,foreign_debt_revaluation_H=revalued,foreign_debt_transactions_H=transacted,
        cash_residual_F=available-sum(payments)-finalF,debt_value_residual_H=value_change-revalued-transacted,
        all_current_payments_met=(local_paid==local_due and imports_paid==s['essential_imports_F'] and debt_paid==v['foreign_due_F'])))


def choice_and_pv(data,out):
    w=data['willingness'];cap=F(w['capacity_F']);promised=F(w['promised_F']);cost=F(w['default_cost_H']);Y=F(w['resources_H'])
    rows=[]
    for price in map(F,w['spots_H_per_F']):
        repayment_eligible=cap>=promised
        advantage=cost-price*promised
        rows.append(dict(spot_H_per_F=price,full_payment_feasible=repayment_eligible,utility_repay_if_feasible=Y-price*promised,
            utility_default=Y-cost,choice='repay' if repayment_eligible and advantage>=0 else 'default_or_restructure',
            equality_rule='repay on an exact feasible tie'))
    eq(out['willingness'],rows,'capacity-filtered preference menu')
    r=q(data['rescheduling']);old=sum([r['due_F']*r['discount_one']]);new=sum([r['replacement_F']*r['discount_two']])
    eq(out['rescheduling'],dict(original_PV_F=old,replacement_PV_F=new,creditor_PV_change_F=new-old,
        first_date_cash_relief_F=r['due_F'],second_date_added_due_F=r['replacement_F']),'dated claim PV and timing')


def run_case(run,data,label,export_ids=(),sovereign_ids=(),design=False,other=False):
    before=copy.deepcopy(data);log=io.StringIO()
    with contextlib.redirect_stdout(log),contextlib.redirect_stderr(log): out=run(data)
    eq(log.getvalue(),'','quiet public API '+label);eq(data,before,'input preserved '+label)
    json.dumps(out,allow_nan=False)
    eq(out['parity']['forward_H_per_F'],strike(data),'funded benchmark '+label)
    eq(out['parity']['full_hedge_gross_H'],F(data['exporter']['net_receivable_F'])*strike(data),'matched notional benchmark '+label)
    eq([r['id'] for r in out['exporter']],[r['id'] for r in data['export_scenarios']],'exporter state ordering')
    eq([r['id'] for r in out['sovereign']],[r['id'] for r in data['sovereign_scenarios']],'sovereign state ordering')
    for s,row in zip(data['export_scenarios'],out['exporter']):
        if s['id'] in export_ids: eq(row,exporter_journal(data,s),'separate exporter journal '+label+'/'+s['id'])
    for s,row in zip(data['sovereign_scenarios'],out['sovereign']):
        if s['id'] in sovereign_ids: eq(row,sovereign_journal(data,s),'separate sovereign journal '+label+'/'+s['id'])
    if design: hedge_elimination(data,out['hedge_design'])
    if other: choice_and_pv(data,out)
    COUNTS['cases']+=1
    return out


def financial_changes(run,base,out):
    results={}
    def change(label,edits,exp=(),sov=(),design=False,other=False):
        d=mutate(base,edits);results[label]=run_case(run,d,label,exp,sov,design,other)
        COUNTS['financial_interventions']+=1
        return results[label]
    # Timing, access and counterparty asymmetry: perturb specific contract failures.
    change('zero_notional',[(('exporter','hedge_F'),'0')],('weak_currency','joint','margin_squeeze'))
    change('negative_rates',[(('parity','home_gross'),'4/5'),(('parity','foreign_gross'),'9/10')],('clear','weak_currency','margin_squeeze'),design=True)
    neg=change('unpaid_ndf',[(('export_scenarios',2,'fixing_H_per_F'),'3')],('margin_squeeze',),design=True)
    need(F(neg['exporter'][2]['derivative_unpaid_H'])>0 and neg['exporter'][2]['debt_paid_H']=='0','negative settlement takes priority even when unpaid')
    change('positive_loss',[(('export_scenarios',5,'positive_settlement_fraction'),'0')],('joint',))
    change('full_positive_collection',[(('export_scenarios',5,'positive_settlement_fraction'),'1')],('joint',))
    change('no_conversion',[(('export_scenarios',4,'conversion_cap_F'),'0')],('conversion_lock',))
    change('no_transfer',[(('export_scenarios',3,'transfer_cap_H'),'0')],('transfer_lock',))
    change('receipt_moved_late',[(('export_scenarios',1,'receipt_before_cutoff'),False)],('weak_currency',),design=True)
    # Exact funding threshold and a smaller amount are actual reruns, not prose.
    bound=F(12)+F(818,17)
    at=change('joint_exact_funding',[(('exporter','offshore_cash_H'),str(bound))],('joint',))
    under=change('joint_underfunding',[(('exporter','offshore_cash_H'),str(bound-F(1,100)))],('joint',))
    need(at['exporter'][5]['all_cutoffs_met'],'exact joint funding closes cutoff')
    eq(under['exporter'][5]['debt_unpaid_H'],F(1,100),'one-cent smaller cash leaves one-cent arrears')
    # Distinct finite minimax cases test box endpoints, flat minima and selected sets.
    change('four_state_design',[(('hedge_design_scenarios',),['margin_squeeze','weak_currency','joint','receipt_delay'])],design=True)
    flat=change('flat_design',[(('exporter','offshore_cash_H'),'1000')],design=True)
    eq((flat['hedge_design']['hedge_F'],flat['hedge_design']['minimum_common_injection_H']),('0','0'),'smallest h on a flat optimum')
    change('singleton_design',[(('exporter','net_receivable_F'),'0'),(('exporter','hedge_F'),'0')],('clear','receipt_delay'),design=True)
    endpoint=change('weak_only_design',[(('hedge_design_scenarios',),['weak_currency']),
        (('export_scenarios',1,'margin_H_per_hedged_F'),'0')],design=True)
    eq(endpoint['hedge_design']['minimum_common_injection_H'],'0','one-sided design attains zero cash need')
    # Sovereign resource source and denomination changes preserve named stocks.
    release=change('early_reserve_release',[(('sovereign','blocked_reserves_F'),'0')],sov=('rollover_stop',))
    eq(release['sovereign'][2]['debt_unpaid_F'],'12','release eight closes only eight of gap')
    # The funded grant arrives before this counterfactual's opening snapshot,
    # increasing owned reserves; it is not relabeled export income or borrowing.
    grant=change('timely_grant',[(('sovereign','reserves_F'),'50')],sov=('rollover_stop',))
    loan=change('timely_new_loan',[(('sovereign_scenarios',2,'new_borrowing_F'),'20')],sov=('rollover_stop',))
    eq((grant['sovereign'][2]['debt_paid_F'],loan['sovereign'][2]['debt_paid_F']),('40','40'),'same timely cash delivers same current payment')
    eq((grant['sovereign'][2]['closing_foreign_principal_F'],loan['sovereign'][2]['closing_foreign_principal_F']),('60','80'),'grant versus loan future liability')
    local=change('local_currency_shortage',[(('sovereign','cash_after_primary_spending_H'),'20'),(('sovereign_scenarios',2,'new_borrowing_F'),'100')],sov=('rollover_stop',))
    eq((local['sovereign'][2]['local_unpaid_H'],local['sovereign'][2]['minimum_external_topup_F']),('16','0'),'ample F does not cure earlier H under one-way purchase policy')
    imports=change('import_shortage',[(('sovereign_scenarios',2,'essential_imports_F'),'40')],sov=('rollover_stop',))
    eq((imports['sovereign'][2]['imports_unpaid_F'],imports['sovereign'][2]['debt_paid_F']),('8','0'),'imports priority and retained arrears')
    change('no_floor',[(('sovereign','reserve_floor_F'),'0')],sov=('rollover_stop',))
    change('choice_and_equal_PV',[(('willingness','spots_H_per_F'),['2','3','9/4']),
        (('rescheduling','replacement_F'),'380/9')],other=True)
    change('infeasible_willingness',[(('willingness','capacity_F'),'39'),(('willingness','default_cost_H'),'200')],other=True)
    change('nonmonotone_discount',[(('rescheduling','discount_one'),'1/2'),(('rescheduling','discount_two'),'3/2')],other=True)
    return results


def printed_arithmetic(base,out,html):
    K=strike(base)
    # Exercise1: independently finance the full two-currency trades.
    home_loan=F(120);foreign_deposit=home_loan/F(6,5);foreign_terminal=foreign_deposit*F(51,50)
    home_repay=home_loan*F(53,50);sale=foreign_terminal*F(13,10)
    exact(sale,F(663,5),'high-forward gross proceeds');exact(home_repay,F(636,5),'home loan repayment');exact(sale-home_repay,F(27,5),'high-forward covered profit')
    foreign_loan=F(100);home_terminal=foreign_loan*F(6,5)*F(53,50);purchase=foreign_loan*F(51,50)*F(6,5)
    exact(purchase,F(612,5),'reverse forward purchase');exact(home_terminal-purchase,F(24,5),'reverse covered profit')
    exact(F(3,2)/F(6,5)-1,F(1,4),'H/F percentage change');exact(F(2,3)/F(5,6)-1,-F(1,5),'reciprocal percentage change')
    # Exercise2: physical expectation and second moment; no pricing law assumed.
    payoffs=[F(80),F(144)];weights=[F(3,4),F(1,4)]
    mean=sum(p*y for p,y in zip(weights,payoffs));second=sum(p*y*y for p,y in zip(weights,payoffs))
    exact(mean,F(96),'physical receipt mean');exact(second-mean*mean,F(768),'physical receipt variance')
    exact(F(80)*K,F(1696,17),'ideal hedge receipt');exact(F(80)*K-mean,F(64,17),'hedged minus expected unhedged');exact(F(100)-F(80)*K,F(4,17),'standalone loan value gap')
    # Every baseline exporter state has already been checked from pocket events.
    cases={r['id']:r for r in out['exporter']}
    for state in ('clear','weak_currency'):
        eq([cases[state][k] for k in ('margin_posted_H','cutoff_cash_H','later_offshore_cash_H')],['4','132/17','200/17'],'worked2 liquid baseline '+state)
    anchors={
        'transfer_lock':{'debt_unpaid_H':'276/17','onshore_H':'24','later_onshore_F':'0','minimum_initial_injection_H':'276/17','terminal_account_value_H':'200/17'},
        'conversion_lock':{'debt_unpaid_H':'276/17','onshore_H':'0','later_onshore_F':'30','minimum_initial_injection_H':'276/17','terminal_account_value_H':'200/17'},
        'joint':{'margin_posted_H':'6','transferred_H':'32','onshore_H':'8','later_onshore_F':'30','derivative_contract_H':'472/17','derivative_received_H':'236/17','debt_unpaid_H':'818/17','terminal_account_value_H':'-172/17'},
        'margin_squeeze':{'margin_required_H':'18','margin_posted_H':'12','margin_unposted_H':'6','derivative_paid_H':'344/17','debt_unpaid_H':'4/17','minimum_initial_injection_H':'106/17'},
        'receipt_delay':{'debt_unpaid_H':'956/17','minimum_initial_injection_H':'956/17','terminal_account_value_H':'200/17'}}
    for state,fields in anchors.items():eq({k:cases[state][k] for k in fields},fields,'worked/solution printed figures '+state)
    exact(F(cases['transfer_lock']['debt_unpaid_H'])-4,F(208,17),'late collateral partial cure still leaves arrears')
    exact(F(80)*(F(4,5)-F(9,10)),-F(8),'joint fixing loss')
    exact(F(200,17)-8-F(236,17),-F(172,17),'joint economic loss decomposition')
    exact(F(12)-4+F(608,17),F(744,17),'delayed receipt debt cash')
    h=F(2720,47);x=F(48,47)
    eq(out['hedge_design']['hedge_F'],h,'printed hedge optimum');eq(out['hedge_design']['minimum_common_injection_H'],x,'printed cash optimum')
    exact(F(30,47)*F(9,40)+F(17,47)*(-F(27,68)),F(0),'printed dual coefficients cancel')
    exact(F(30,47)*(-12)+F(17,47)*24,x,'printed global lower bound')
    exact(h/20-12,-F(428,47),'nonbinding weak early constraint');exact(F(65,136)*h-32,-F(204,47),'nonbinding squeeze late constraint');exact(80-h,F(1040,47),'residual terminal notional')
    lines=[(F(0),F(0)),(F(1,20),F(-12)),(-F(27,68),F(24)),(F(9,40),F(-12)),(F(65,136),F(-32))]
    exact(max(a*0+b for a,b in lines),F(24),'zero hedge requirement');exact(max(a*80+b for a,b in lines),F(106,17),'full hedge requirement')
    exact(F(24)-F(27,68)*80,-F(132,17),'weak full-hedge late constraint')
    sov=out['sovereign']
    for index,expected in enumerate([['12','24','40','64','12','40','12','80','22'],['12','36','28','64','12','40','12','80','22'],['6','18','46','36','12','20','4','80','0']]):
        keys=('bought_F','dealer_receipt_H','closing_cash_H','before_external_payments_F','imports_paid_F','debt_paid_F','closing_free_reserves_F','closing_foreign_principal_F','new_loan_later_due_F')
        eq([sov[index][key] for key in keys],expected,'worked3 full currency table')
    eq([r['foreign_debt_value_change_H'] for r in sov],['-40','40','40'],'reported debt-value changes')
    eq([r['foreign_debt_revaluation_H'] for r in sov],['0','100','100'],'old debt revaluation')
    exact(F(40)*F(19,20),F(38),'original PV');exact(F(44)*F(9,10),F(198,5),'replacement PV');exact(F(198,5)-38,F(8,5),'creditor PV change');exact(F(38)/F(9,10),F(380,9),'PV-preserving date2 payment');exact(F(90)/40,F(9,4),'feasible indifference spot')
    for rounded,value in [('1.247059',K),('99.764706',80*K),('3.764706',80*K-96),('57.872340',h),('1.021277',x)]:
        need(abs(F(rounded)-value)<=F(1,2000000),'six-place manuscript rounding '+rounded)
        need(rounded in html,'rounded figure is actually in manuscript '+rounded)
    # Cover every nontrivial literal fraction, using already independent journals,
    # financed trades and eliminated constraints rather than the saved report.
    literals={
        '106/85':K,'1696/17':80*K,'200/17':F(cases['clear']['terminal_account_value_H']),
        '64/17':80*K-mean,'4/17':F(100)-80*K,
        '608/17':F(cases['weak_currency']['derivative_received_H']),
        '1832/17':F(cases['weak_currency']['cash_trail'][2]['offshore_cash_H']),
        '132/17':F(cases['weak_currency']['cutoff_cash_H']),
        '276/17':F(cases['transfer_lock']['debt_unpaid_H']),
        '1424/17':F(cases['transfer_lock']['cash_trail'][2]['offshore_cash_H']),
        '818/17':F(cases['joint']['debt_unpaid_H']),
        '172/17':-F(cases['joint']['terminal_account_value_H']),
        '472/17':F(cases['joint']['derivative_contract_H']),
        '236/17':F(cases['joint']['derivative_received_H']),
        '882/17':F(cases['joint']['cash_trail'][2]['offshore_cash_H']),
        '344/17':F(cases['margin_squeeze']['derivative_paid_H']),
        '106/17':F(cases['margin_squeeze']['minimum_initial_injection_H']),
        '956/17':F(cases['receipt_delay']['debt_unpaid_H']),
        '744/17':F(cases['receipt_delay']['debt_paid_H']),
        '27/68':-F(out['hedge_design']['constraints'][2]['slope']),
        '2720/47':F(out['hedge_design']['hedge_F']),
        '48/47':F(out['hedge_design']['minimum_common_injection_H']),
        '428/47':12-h/20,'204/47':32-F(65,136)*h,'1040/47':80-h,
        '30/47':F(27,68)/(F(27,68)+F(9,40)),
        '17/47':F(9,40)/(F(27,68)+F(9,40)),
        '9/4':F(90)/40,'198/5':44*F(9,10),'8/5':44*F(9,10)-40*F(19,20),
        '380/9':40*F(19,20)/F(9,10),'663/5':sale,'636/5':home_repay,
        '27/5':sale-home_repay,'612/5':purchase,'24/5':home_terminal-purchase,
        '208/17':F(cases['transfer_lock']['debt_unpaid_H'])-4,
        '38/85':K-F(4,5),'5/6':1/F(6,5),'2/3':1/F(3,2)}
    for literal,value in literals.items():
        exact(literal,value,'all printed nontrivial fractions '+literal)
        need(literal in html,'reviewed fraction remains in exact manuscript '+literal)
    primitive={'1/2','1/20','1/4','1/5','11/10','13/10','19/20','3/2','3/4','3/40','4/5','51/50','53/50','6/5','9/10','9/40','9/5'}
    observed=set(re.findall(r'(?<![\d.])\d+/\d+(?!\d|\.\d)',html))
    eq(observed-set(literals),primitive,'remaining fractions are stated inputs/probabilities or independently checked quote changes')


def invalid_contracts(run,base):
    mutations=[
        (('schema',),True),(('parity','spot_H_per_F'),'0'),(('parity','home_gross'),'49/100'),(('parity','foreign_gross'),'201/100'),
        (('exporter','hedge_F'),'81'),(('exporter','debt_H'),100), (('exporter','offshore_cash_H'),True),
        (('exporter','offshore_cash_H'),'1e2'),(('exporter','offshore_cash_H'),'NaN'),(('exporter','offshore_cash_H'),' 12'),
        (('exporter','offshore_cash_H'),'1/0'),(('exporter','offshore_cash_H'),'1000000000'),(('exporter','offshore_cash_H'),'0.123456789'),
        (('export_scenarios',0,'receipt_before_cutoff'),1),(('export_scenarios',0,'id'),'A'),(('export_scenarios',1,'id'),'clear'),
        (('export_scenarios',0,'positive_settlement_fraction'),'-1/10'),(('export_scenarios',0,'positive_settlement_fraction'),'11/10'),
        (('export_scenarios',0,'margin_H_per_hedged_F'),'21/10'),(('export_scenarios',0,'fixing_H_per_F'),'0'),
        (('export_scenarios',0,'conversion_cap_F'),'-1'),(('export_scenarios',),[]),
        (('hedge_design_scenarios',),['unknown']), (('hedge_design_scenarios',),['clear','clear']), (('hedge_design_scenarios',),[[]]),
        (('sovereign','blocked_reserves_F'),'27'),(('sovereign','new_loan_gross'),'0'),(('sovereign_scenarios',0,'spot_H_per_F'),'101'),
        (('willingness','spots_H_per_F'),[]), (('willingness','capacity_F'),'-1'),(('rescheduling','discount_two'),'0')]
    candidates=[mutate(base,[(path,value)]) for path,value in mutations]
    candidates += [None,[],dict(base,extra='x'),{k:v for k,v in base.items() if k!='sovereign'}]
    for candidate in candidates:
        before=copy.deepcopy(candidate);log=io.StringIO();rejected=False
        with contextlib.redirect_stdout(log),contextlib.redirect_stderr(log):
            try:run(candidate)
            except ValueError:rejected=True
        need(rejected,'actual invalid API contract rejection')
        eq(candidate,before,'invalid payload unmodified');eq(log.getvalue(),'','quiet invalid API')
        COUNTS['invalid_api_rejections']+=1


class Fragment(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.ids=[];self.links=[];self.sources=[];self.worked=0;self.prompts=[];self.targets=[];self.ex=False
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if 'id' in a:self.ids.append(a['id'])
        if 'href' in a:self.links.append(a['href'])
        if 'data-source' in a:self.sources.append(a['data-source'])
        if 'worked' in a.get('class','').split():self.worked+=1
        if tag=='ol' and 'exercises' in a.get('class','').split():self.ex=True
        if tag=='li' and self.ex:self.prompts.append(a.get('id'))
        if 'data-solution-for' in a:self.targets.append(a['data-solution-for'])
    def handle_endtag(self,tag):
        if tag=='ol':self.ex=False


def structural_bindings(root):
    html=(root/AUTHOR[0]).read_text();p=Fragment();p.feed(html)
    eq(p.worked,4,'four full worked containers');eq(p.prompts,['v11-c09-ex'+str(i) for i in range(1,9)],'eight exact original prompts');eq(p.targets,p.prompts,'every complete solution paired')
    eq(len(p.ids),len(set(p.ids)),'unique manuscript IDs');need('Teach-back and delayed retention' in html,'answered teaching/retention')
    for suffix in ('inputs.json','analysis.py','output.json','manifest.json','README.txt'):
        name='v11-c09-'+suffix;need(name in p.links and 'projects/'+name not in p.links,'flat downloadable '+name)
    source_rows=strict((root/'content/reviews/v11-c09-sources.json').read_text())
    eq(set(p.sources),{r['id'] for r in source_rows},'exact scoped source routing')
    eq(len(source_rows),6,'five reused plus one historical primary record')
    for r in source_rows:
        need(r['url'].startswith('https://') and bool(r['verification']) and bool(r['use']),'source scope is documented')
    manifest=strict((root/'content/projects/v11-c09-manifest.json').read_text())
    expected=['v11-c09-'+s for s in ('inputs.json','analysis.py','output.json','README.txt')]
    eq([r['file'] for r in manifest['files']],expected,'exact four manifest payloads')
    for r in manifest['files']:
        raw=(root/'content/projects'/r['file']).read_bytes()
        eq((r['bytes'],r['sha256']),(len(raw),hashlib.sha256(raw).hexdigest()),'manifest binding '+r['file'])
    author=strict((root/'content/reviews/v11-c09-author.json').read_text())
    eq({r['path'] for r in author['reviewed_hashes']},set(AUTHOR)-{'content/reviews/v11-c09-author.json'},'author binds exact eight nonself files')
    eq(len(author['reviewed_hashes']),8,'author has no duplicate binding')
    for r in author['reviewed_hashes']:
        raw=(root/r['path']).read_bytes();eq((r['bytes'],r['sha256']),(len(raw),hashlib.sha256(raw).hexdigest()),'author binding '+r['path'])
    peer=strict((root/REVIEW).read_text())
    eq({r['path'] for r in peer['reviewed_hashes']},set(AUTHOR)|{SELF},'peer binds final nine author and own checker')
    eq(len(peer['reviewed_hashes']),10,'no missing/duplicate peer binding')
    for r in peer['reviewed_hashes']:
        raw=(root/r['path']).read_bytes();eq((r['bytes'],r['sha256']),(len(raw),hashlib.sha256(raw).hexdigest()),'peer final binding '+r['path'])
    eq((len(peer['worked_audit']),len(peer['exercise_audit'])),(4,8),'full peer worked and prompt audit recorded')
    eq(peer['open_findings'],[],'no unresolved peer findings')


def portable_cli(root,baseline):
    with tempfile.TemporaryDirectory(prefix='v11-c09-peer-cli-') as temporary:
        folder=Path(temporary);package=folder/'package';package.mkdir();away=folder/'away';away.mkdir()
        model=package/'v11-c09-analysis.py';source=package/'v11-c09-inputs.json'
        shutil.copy2(root/'content/projects'/model.name,model);shutil.copy2(root/'content/projects'/source.name,source)
        env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1')
        for optimized in (False,True):
            command=[sys.executable]+(['-O'] if optimized else [])+[str(model)]
            def execute(args):return subprocess.run(command+args,cwd=away,env=env,capture_output=True,text=True,timeout=20)
            r=execute([]);eq((r.returncode,r.stdout,r.stderr),(0,'',''),'quiet sibling-default CLI')
            eq(strict((package/'v11-c09-output.json').read_text()),baseline,'portable default exact result')
            result=folder/'result.json';r=execute(['--input',str(source),'--output',str(result)])
            eq((r.returncode,r.stdout,r.stderr),(0,'',''),'quiet explicit CLI');eq(strict(result.read_text()),baseline,'portable explicit result')
            (package/'nested').mkdir(exist_ok=True)
            for target in (source,model):
                for kind in ('direct','resolved','symbolic','hard'):
                    candidate=target if kind=='direct' else package/'nested'/'..'/target.name if kind=='resolved' else package/(target.name+'.'+kind)
                    if kind=='symbolic':candidate.symlink_to(target)
                    elif kind=='hard':os.link(target,candidate)
                    before=source.read_bytes(),model.read_bytes()
                    r=execute(['--input',str(source),'--output',str(candidate)])
                    eq(r.returncode,2,'protected output rejects '+kind);eq(r.stdout,'','no output on alias rejection');need('overwrite' in r.stderr,'specific alias error')
                    eq((source.read_bytes(),model.read_bytes()),before,'both original payloads survive alias attempt')
                    COUNTS['protected_output_rejections']+=1
                    if kind in ('symbolic','hard'):candidate.unlink()
            malformed=[b'{"schema":1,"schema":2}',b'{"schema":NaN}',b'[]',b' '*150001,b'\xff']
            for payload in malformed:
                invalid=folder/'invalid.json';invalid.write_bytes(payload);result.write_text('PRESERVE\n')
                r=execute(['--input',str(invalid),'--output',str(result)])
                eq(r.returncode,2,'actual invalid CLI rejection');eq(r.stdout,'','invalid CLI has no report');need(r.stderr.startswith('error:'),'invalid CLI error message');eq(result.read_text(),'PRESERVE\n','invalid CLI preserves destination')
                COUNTS['invalid_cli_rejections']+=1
    return {'normal_and_optimized':True,'quiet_default_and_explicit':True,'independent_working_directory':True,'direct_resolved_symbolic_hard_aliases':True}


def check(root=None):
    global COUNTS
    COUNTS=dict(comparisons=0,cases=0,financial_interventions=0,exporter_journals=0,sovereign_journals=0,design_certificates=0,invalid_api_rejections=0,invalid_cli_rejections=0,protected_output_rejections=0)
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    log=io.StringIO()
    with contextlib.redirect_stdout(log),contextlib.redirect_stderr(log):ns=runpy.run_path(str(root/'content/projects/v11-c09-analysis.py'))
    eq(log.getvalue(),'','quiet model import')
    data=strict((root/'content/projects/v11-c09-inputs.json').read_text())
    baseline=run_case(ns['run'],data,'baseline',[r['id'] for r in data['export_scenarios']],[r['id'] for r in data['sovereign_scenarios']],True,True)
    eq(baseline,strict((root/'content/projects/v11-c09-output.json').read_text()),'saved report after original-contract checks')
    financial_changes(ns['run'],data,baseline);printed_arithmetic(data,baseline,(root/AUTHOR[0]).read_text())
    invalid_contracts(ns['run'],data)
    portable=portable_cli(root,baseline)
    structural_bindings(root)
    summary=dict(chapter='v11-c09',status='passed',review_type='separate machine-assisted peer',**COUNTS,
        worked_examples=4,solved_exercises=8,portable=portable,
        independent_methods=['currency-pocket journals with explicit surviving claims','exact interval elimination for all finite hedge constraints and smallest-hedge ties','separate sovereign source/use and surviving-principal inventory','funded two-loan parity and physical second-moment calculation','capacity-filtered preference and dated claim PV'],
        limits='Bounded synthetic contract review; no current legal applicability, empirical behavioral calibration, human academic certification or rendered QA claim.')
    json.dumps(summary,allow_nan=False)
    return summary


if __name__=='__main__':print(json.dumps(check(),indent=2,allow_nan=False))
