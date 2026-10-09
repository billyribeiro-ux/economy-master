"""Coordinator calculations of reviewed original cases; no author imports.

This file is production evidence, not a substitute for separate proof/prompt
review, the final frozen payload checks, or dependency-ordered acceptance.
"""
from fractions import Fraction as F
from pathlib import Path
import json
import math

ROOT=Path(__file__).resolve().parents[1]
COUNT=0


def eq(actual, expected, label):
    global COUNT
    COUNT+=1
    if actual!=expected:raise RuntimeError(label+': '+repr(actual)+' != '+repr(expected))


def near(actual, expected, label):
    global COUNT
    COUNT+=1
    if not math.isclose(float(actual),float(expected),rel_tol=1e-10,abs_tol=1e-10):raise RuntimeError(label)


def intermediation():
    d=json.loads((ROOT/'content/projects/v11-c01-output.json').read_text())
    s=d['screening']
    for key,value in [('funding_threshold_probability',F(4,5)),('pooled_success',F(3,4)),('pooled_receipt',95),('pooled_loan_margin',-5),('funded_mass_if_tested',F(14,25)),('gross_test_policy_value',F(22,5)),('net_test_policy_value',F(7,5)),('maximum_test_cost_against_no_test',F(22,5))]:eq(F(s[key]),F(value),'screening '+key)
    # Four explicit type/signal joint masses give independent conditional values.
    for row,masses in zip(s['branches'],[(F(12,25),F(2,25)),(F(3,25),F(8,25))]):
        good,bad=masses;mass=good+bad;p=(good*F(19,20)+bad*F(9,20))/mass
        for key,value in [('mass',mass),('good_posterior',good/mass),('success_probability',p),('expected_receipt',20+100*p),('loan_margin',20+100*p-100)]:eq(F(row[key]),value,'screening conditional '+key)
    eq(F(14,25)*F(75,14),3,'all tested cost allocated across funded loans')
    eq(F(14,25)*(F(55,7)-F(75,14)),F(7,5),'same expected net value per applicant')
    eq(F(1,2)*5-3,F(-1,2),'new applicant prior makes test privately unprofitable')
    m=d['monitoring']
    for key,value in [('borrower_prudent_payoff',18),('borrower_divert_payoff',20),('borrower_divert_payoff_after_enforcement',12),('unmonitored_receipt',72),('monitored_receipt',108),('aggregate_audit_gain',36),('one_claimant_audit_gain',3),('pooled_initial_funding',106),('pooled_expected_surplus',2),('unmonitored_expected_surplus',-28),('all_duplicate_expected_surplus',-52),('largest_delegation_cost_for_nonnegative_surplus',3),('private_benefit_indifference',6)]:eq(F(m[key]),F(value),'monitoring '+key)
    eq(m['unmonitored_action'],'divert','borrower best reply')
    eq(m['no_audit_is_nash_given_loan'],True,'post-funding twelve-claimant game')
    eq((F(36,6)-5,F(36,12)-5),(F(1),F(-2)),'one claimant deviation thresholds')
    eq((108-100,108-106),(8,2),'no enforcement benefit when borrower already prudent')
    b=d['bank']
    states=[[(24,126,132,18),(16,64,72,8),(40,190,204,26)],
            [(24,162,168,18),(16,64,72,8),(40,226,240,26)],
            [(0,162,144,18),(40,64,96,8),(40,226,240,26)]]
    for actual,groups in zip(b['two_bank_ledger'],states):
        for key,values in zip(['A','B','consolidated'],groups):
            reserve,loans,deposits,equity=map(F,values)
            for field,value in [('reserves',reserve),('loans',loans),('assets',reserve+loans),('deposits',deposits),('equity',equity),('equity_assets',equity/(reserve+loans))]:eq(F(actual[key][field]),value,'two-bank '+key+' '+field)
            eq(reserve+loans,deposits+equity,'independent deposit/settlement conservation')
    eq(F(b['immediate_probe_before_income']['cash_gap']),5,'dated immediate gap')
    eq(b['immediate_probe_before_income']['executable'],False,'no retrospective funding')
    reserves=[F(0),F(10),F(12),F('10.5'),F(7),F(7)]
    for j,row in enumerate(b['A_later_income_ledger']):
        loans=F(157 if j==5 else 162);cash=reserves[j]
        eq(F(row['reserves']),cash,'every later receipt/payment cash')
        eq(F(row['loans']),loans,'uncovered loss is not current cash')
        eq(F(row['equity']),cash+loans-144,'later residual equity')
    for key,value in [('net_interest_income',F('8.5')),('profit',2),('average_earning_loans',F('159.5')),('average_assets',163),('average_equity',19),('net_interest_margin',F(17,319)),('return_on_assets',F(2,163)),('return_on_equity',F(2,19))]:eq(F(b[key]),F(value),'income/denominator '+key)
    eq((24-18,126+18,132+18-18,16+18,72+18),(6,144,132,34,90),'fresh two-bank transfer')
    eq((F(18,150),F(18,168)),(F(3,25),F(3,28)),'external versus internal settlement ratios')
    for loss,expected in [(22,(7,140,3,-15)),(26,(7,136,-1,-19))]:eq((7,162-loss,25-loss,7-loss),expected,'capital versus cash under loss')
    liq=d['liquidity'];u=lambda c:-1/(F(c)+F(1,10))
    direct=F(1,4)*u(1)+F(3,4)*u(F(3,2));insured=F(1,4)*u(F(11,10))+F(3,4)*u(F(29,20))
    for key,value in [('withdrawal_capacity_fraction',F(10,11)),('late_indifference_withdrawal_fraction',F(8,11)),('candidate_no_run_expected_utility',F(-515,744)),('direct_all_long_expected_utility',F(-245,352)),('candidate_utility_gain_over_all_long',F(125,32736)),('full_run_wait_deviation_utility',-10)]:eq(F(liq[key]),F(value),'mutual allocation '+key)
    eq((direct,insured,insured-direct),(F(-245,352),F(-515,744),F(125,32736)),'independent expected utilities')
    for row in liq['scenarios']:
        w=F(row['withdrawal_fraction']);mass=100*w;served=min(mass,F(1000,11));cash=served*F(11,10);remaining=100-cash
        eq(F(row['served_probability']),served/mass,'random rank probability')
        eq(F(row['date1_cash_paid']),cash,'early cash conservation')
        eq(F(row['date2_cash_available']),F(3,2)*remaining,'remaining long payoff')
        eq(F(row['expected_utility_per_withdrawer']),served/mass*u(F(11,10))+(1-served/mass)*u(0),'utility of lottery before averaging')
        if w==1:eq(row['cash_per_waiter'],None,'no actual full-run waiter average')
        else:eq(F(row['cash_per_waiter']),F(3,2)*remaining/(100*(1-w)),'actual mutual residual per waiter')
    eq(F(liq['full_run']['expected_utility_per_withdrawer']),F(-5,3),'full-run strict late best reply')
    eq(liq['full_run_withdrawal_is_strict_best_reply'],True,'post-deposit full run')
    eq(F(3,2)*(1-F(4,5)*F(11,10))/(1-F(4,5)),F(9,10),'feasible early service but late incentive failure')
    return {'status':'current-case-passed','worked_examples_reviewed':4,'solved_exercises_reviewed':8,'scope':'Independent original-case arithmetic audit; final complete manuscript/proof/source/author/peer and acceptance evidence is recorded separately in v11-opening-root-review-notes.json.'}


def bank():
    d=json.loads((ROOT/'content/projects/v11-c02-output.json').read_text())
    # Hand-derived journal table: cash,gross loans,allowance,deposits,equity.
    rows=[(40,260,8,280,20),(24,260,8,264,20),(32,252,8,264,20),
          (37,252,8,264,25),(37,252,8,266,23),(F('35.5'),252,8,266,F('21.5')),
          (F('35.5'),252,14,266,F('15.5')),(F('35.5'),242,4,266,F('15.5')),
          (F('36.5'),242,5,266,F('15.5')),(F('34.5'),242,5,266,F('13.5'))]
    for row,expected in zip(d['journal_states'],rows):
        for key,value in zip(['cash','gross_loans','allowance','deposits','equity'],expected):near(row['accounts'][key],value,'full bank journal '+key)
        C,G,A,D,E=map(F,expected)
        eq(C+60+G-A+8,D+60+E,'independent journal closure')
    near(d['net_income'],F('-4.5'),'cash interest minus interest credit/salary/provision')
    near(d['closing']['assets'],F('339.5'),'book assets')
    near(d['valuation']['economic_equity'],F('34.5')+56+231+6-326,'common-date economic equity')
    near(d['valuation']['severe_economic_equity'],F('34.5')+56+223+6-326,'severe loan mark')
    k=F('11.5');u=F('337.5');r=F(255)
    for field,value in [('adjusted_capital',k),('adjusted_exposure',u),('toy_rwa',r),('toy_risk_ratio',k/r),('toy_leverage_ratio',k/u),('minimum_cash_equity_for_ratios',F('3.8'))]:near(d['base_capital'][field],value,field)
    eq((F('.04')*u-k)/(1-F('.04')),F(25,12),'cash issue denominator condition')
    headrooms=[F('-1.2'),F('5.8'),F('1.712')]
    for row,H in zip(d['liquidity']['forecast'],headrooms):
        near(row['unrestricted_headroom'],H,'dated bank cash prefix')
        near(row['cash_after_assumed_payments'],H+F('4.5'),'restricted plus usable cash')
        eq(row['executable_without_added_funding_through_here'],False,'after failed first cutoff rows conditional')
    near(d['liquidity']['minimum_upfront_external_cash_for_this_fixed_plan'],F('1.2'),'necessary initial liquidity injection')
    eq(d['liquidity']['first_failure_cutoff'],1,'first bank payment failure')
    # Every remaining exercise anchor from its declared changed transaction.
    eq((F('34.5')-5,242+12,266+12-5,F('339.5')+12-5),(F('29.5'),254,273,F('346.5')),'bank exercise1 aggregate entries')
    eq((5-6+8-1,70-8-5,(70-8-5)-(70-6)+1),(6,57,-6),'bank exercise2 allowance/cash closure')
    eq(F(326)-F('34.5')-56-6,F('229.5'),'bank exercise3 zero equity mark')
    eq(F('.7')*237+F('.2')*60+6,F('183.9'),'bank exercise4 altered classification')
    eq(1-F(30,36),F(1,6),'bank exercise5 critical haircut')
    eq([headrooms[0]+12,headrooms[1],headrooms[2]],[F('10.8'),F('5.8'),F('1.712')],'bank earlier contracted receipt')
    issue=F('3.8');near((k+issue)/(u+issue),F('15.3')/F('341.3'),'bank cash issue leverage')
    eq([H+issue for H in headrooms],[F('2.6'),F('9.6'),F('5.512')],'bank joint repair')
    eq(F('-6.5')+issue,F('-2.7'),'cash issue still fails severe economic-value scenario')
    eq((30+34+10-70,30+34+10+12-70-5,30+34+10+12+25-70-5),(4,11,36),'sale instead of loan cash')
    eq(F('4.5')+5+F('.8')*20,F('25.5'),'bank overstatement decomposition')
    return {'status':'current-case-passed','journal_rows':10,'cash_cutoffs':3,'worked_examples_reviewed':3,'solved_exercises_reviewed':8,'scope':'Independent original-case arithmetic audit; final complete manuscript/proof/source/author/peer and acceptance evidence is recorded separately in v11-opening-root-review-notes.json.'}


def borrower():
    d=json.loads((ROOT/'content/projects/v11-c03-output.json').read_text())
    eq(d['operating_cfads'],{'base':['40','42','44'],'downturn':['30','34','38']},'borrower operating bridges')
    project=40/F('1.1')+42/F('1.1')**2+134/F('1.1')**3
    eq(F(d['illustrative_unlevered_valuation']['pv']),project,'separate enterprise PV')
    eq(F(d['illustrative_unlevered_valuation']['npv']),project-140,'enterprise NPV')
    waterfall=d['collateral_waterfall']
    for key,value in [('gross_sale_cash',78),('workout_cost_paid',8),('prior_claim_paid',15),('available_to_this_lender_and_juniors',55)]:eq(F(waterfall[key]),F(value),'borrower waterfall '+key)
    expected={'requested':{'advance':120,'principal':[40,40,40],'interest':[12,8,4],'cash':{'base':[-2,-8,-8],'downturn':[-12,-26,-32]},'claim':88,'decision':'restructure_or_refuse'},
              'revised':{'advance':80,'principal':[20,30,30],'interest':[F('6.4'),F('4.8'),F('2.4')],'cash':{'base':[F('23.6'),F('30.8'),F('42.4')],'downturn':[F('13.6'),F('12.8'),F('18.4')]},'claim':F('64.8'),'decision':'hold_for_evidence'}}
    for result in d['proposals']:
        e=expected[result['id']];service=[F(p)+F(i) for p,i in zip(e['principal'],e['interest'])]
        for t,row in enumerate(result['contract_schedule']):
            eq(F(row['opening_principal']),F(e['advance']-sum(e['principal'][:t])),'borrower remaining debt by total prior principal')
            eq((F(row['interest']),F(row['principal']),F(row['service'])),(F(e['interest'][t]),F(e['principal'][t]),service[t]),'borrower complete funded schedule')
        for scenario in result['scenarios']:
            flows=list(map(F,d['operating_cfads'][scenario['id']]))
            for t,row in enumerate(scenario['rows']):
                eq(F(row['cash_after_service_on_contract_projection']),F(10)+sum(flows[:t+1])-sum(service[:t+1]),'cumulative receipts less cumulative debt')
                eq(F(row['cash_after_service_on_contract_projection']),F(e['cash'][scenario['id']][t]),'independent published cash anchor')
                eq(F(row['dscr']),flows[t]/service[t],'borrower ratio numerator and date')
            eq(F(scenario['minimum_initial_injection_for_cash_floor']),max(F(0),10-min([F(10)]+list(map(F,e['cash'][scenario['id']])))),'minimum initial cash certificate')
        coll=result['collateral_branch'];rate=F('1.06')
        promised=sum(s/rate**t for t,s in enumerate(service,1));default=service[0]/rate+55/rate**3
        for key,value in [('claim_at_default',e['claim']),('lender_recovery',55),('recovery_discounted_to_default',55/rate),('promised_receipts_pv',promised),('default_branch_receipts_pv',default),('physical_scenario_margin_over_advance',F('.88')*promised+F('.12')*default-e['advance'])]:eq(F(coll[key]),F(value),'borrower complete receipt/claim '+key)
        eq(result['recommendation'],e['decision'],'borrower evidence and quantitative distinction')
    eq(F('12.8')-F('2.8'),10,'working capital equality')
    eq(F('12.8')-F('2.80000001'),F('9.99999999'),'one-step boundary failure')
    eq((80+20-130,10-(80+20-130)),(-30,40),'real new sources gap')
    balloon=[F('6.4'),F('6.4'),F('86.4')]
    eq([10+sum([40,42,44][:t+1])-sum(balloon[:t+1]) for t in range(3)],[F('43.6'),F('79.2'),F('36.8')],'borrower retained cash balloon')
    eq(45/F('1.06')**2,F(112500,2809),'delayed revised seniority recovery')
    eq(F('64.8')-45/F('1.06')**2,F(347616,14045),'delayed claim comparison')
    full=F(12368880,148877);default=F(10582880,148877)
    eq((full-80)/(full-default),F(122,475),'fixed branch physical probability break-even')
    eq(full-F('.3')*(full-default)-80,F(-77080,148877),'changed default law margin')
    full8=sum(x/F('1.08')**t for t,x in enumerate([F('26.4'),F('34.8'),F('32.4')],1))
    default8=F('26.4')/F('1.08')+55/F('1.08')**3
    eq(full8,80,'coupon equals assessment rate promised value')
    eq(F('.88')*full8+F('.12')*default8,F(515515,6561),'separate changed assessment rate')
    for face in [20,40,100]:eq(F(200-face,2)-(120-face),F(face,2)-20,'finite risk-shifting threshold')
    eq([F('.1')*k-1 for k in [0,10,12]],[F(-1),F(0),F('.2')],'officer effort incentives')
    eq(30-15/F('1.05'),F(110,7),'delayed retention recovery')
    return {'status':'current-case-passed','worked_examples_reviewed':4,'solved_exercises_reviewed':8,'scope':'Independent original-case arithmetic audit; final complete manuscript/proof/source/author/peer and acceptance evidence is recorded separately in v11-opening-root-review-notes.json.'}


def check():
    global COUNT
    COUNT=0
    result={'v11-c01':intermediation(),'v11-c02':bank(),'v11-c03':borrower()}
    return {'date':'2026-10-09','status':'independent-component-numerical-audit-passed','comparisons':COUNT,'chapters':result,'limits':'No chapter acceptance, empirical law adequacy, regulatory compliance or UI result is implied.'}


if __name__=='__main__':print(json.dumps(check(),indent=2))
