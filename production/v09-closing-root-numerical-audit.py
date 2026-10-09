#!/usr/bin/env python3
"""Coordinator reconstruction: no chapter model/checker is imported.

Exact dated cash/state sums, Decimal Newton IRRs, per-share execution prices,
and direct finite-state reserve moments provide independent numeric evidence.
Run from any directory. The resulting JSON is production evidence, not a lab.
"""
from collections import Counter
from decimal import Decimal, localcontext
from fractions import Fraction as F
from itertools import product
import hashlib
import json
from math import prod, sqrt
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COUNTS = Counter()
ANCHORS = {}


def eq(chapter, label, actual, expected):
    if isinstance(expected, dict):
        for key, value in expected.items():
            eq(chapter, label + '.' + key, actual[key], value)
        return
    if isinstance(expected, (list, tuple)):
        if len(actual) != len(expected):
            raise AssertionError((chapter, label, 'length'))
        for i, value in enumerate(expected):
            eq(chapter, label + '.' + str(i), actual[i], value)
        return
    if expected is None or isinstance(expected, (str, bool)):
        good = actual == expected
    elif isinstance(expected, float) or isinstance(actual, float):
        good = abs(float(actual) - float(expected)) <= 1e-10 * max(1, abs(float(expected)))
    else:
        good = F(actual) == expected
    if not good:
        raise AssertionError((chapter, label, actual, str(expected)))
    COUNTS[chapter] += 1


def load(chapter, suffix):
    return json.loads((ROOT / f'content/projects/{chapter}-{suffix}.json').read_text())


def irr(cash):
    # Newton on the terminal-value polynomial, rather than the lab's bisection.
    with localcontext() as context:
        context.prec = 65
        coefficients = [Decimal(F(c).numerator) / Decimal(F(c).denominator) for c in cash]
        n, x = len(cash)-1, Decimal('1.2')
        for _ in range(100):
            value = sum(c*x**(n-i) for i,c in enumerate(coefficients))
            derivative = sum(c*(n-i)*x**(n-i-1) for i,c in enumerate(coefficients[:-1]))
            new = x-value/derivative
            if new <= 0:
                new = x/2
            if abs(new-x) < Decimal('1e-55'):
                x = new
                break
            x = new
        if abs(sum(c*x**(n-i) for i,c in enumerate(coefficients))) > Decimal('1e-45'):
            raise AssertionError('Newton residual')
        return float(x-1)


def c10():
    c='v09-c10'; o=load(c,'output'); d=load(c,'inputs')
    p=d['property']; debt=F(p['loan']); lender=[-debt]; operating=[]
    for i in range(3):
        principal=F(p['principal_payments'][i]); interest=debt*F(p['loan_rate'])
        operating.append(F(p['noi'][i])-F(p['capex'][i])); lender.append(principal+interest)
        eq(c,f'debt row{i}',o['property']['operations'][i],{'opening_debt':debt,'interest':interest,
            'principal':principal,'debt_service':lender[-1],'closing_debt':debt-principal,'operating_cash':operating[-1]})
        debt-=principal
    eq(c,'lender cash',o['property']['lender_cash'],lender)
    eq(c,'lender irr',o['property']['lender_irr'],irr(lender))
    initial=F(p['purchase'])+F(p['entry_cost'])
    for name,noi,cap in [('base',F(p['forward_noi']),F(p['exit_cap_rate'])),
                         ('stress',F(p['stress_forward_noi']),F(p['stress_exit_cap_rate']))]:
        gross=noi/cap; sale=gross*(1-F(p['sale_cost_rate'])); asset=[-initial]+operating[:]
        asset[-1]+=sale; equity=[a-b for a,b in zip(asset,lender)]
        eq(c,name,o['property'][name],{'gross_sale':gross,'sale_cost':gross-sale,'net_sale':sale,
            'asset_cash':asset,'equity_cash':equity,
            'asset_npv_at_supplied_rate':sum(v/(1+F(p['asset_discount_rate']))**t for t,v in enumerate(asset)),
            'asset_irr':irr(asset),'equity_irr':irr(equity)})
    # Stationary covariance sum includes every ordered date pair.
    theta=F(3,5); var=F(1,25)*(1-theta)/(1+theta)
    sumvar=sum(var*theta**abs(i-j) for i,j in product(range(4),repeat=2))
    eq(c,'population',o['smoothing']['population'],{'latent_variance':F(1,25),'reported_variance':var,
        'reported_sigma':sqrt(var),'latent_beta':F(2,3),'reported_beta':F(4,15),
        'latent_market_covariance':F(3,200),'reported_market_covariance':F(3,500),
        'reported_market_correlation':.4,'latent_sharpe':F(3,10),'reported_sharpe':.6,
        'variance_of_sum':sumvar,'long_run_variance_per_period':F(1,25)})
    latent=list(map(F,d['smoothing']['latent_path'])); marks=[]; last=F(2,25)
    for i,r in enumerate(latent):
        last=theta*last+(1-theta)*r; marks.append(last)
        eq(c,f'marked wealth{i}',o['smoothing']['finite_path']['wealth_indices'][i],
           {'latent_index':prod(1+x for x in latent[:i+1]),'appraisal_index':prod(1+x for x in marks)})
    eq(c,'reported path',o['smoothing']['finite_path']['reported_returns'],marks)
    eq(c,'inverted path',o['smoothing']['finite_path']['unsmoothed_returns'],latent)
    C=list(map(F,[40,32,22,2])); D=list(map(F,[0,8,12,110])); cf=[y-x for x,y in zip(C,D)]
    multipliers=[prod(map(F,d['private']['benchmark_gross_returns'][i:])) for i in range(4)]
    fvc=sum(x*g for x,g in zip(C,multipliers)); fvd=sum(x*g for x,g in zip(D,multipliers))
    eq(c,'private flows',o['private'],{'investment_capital':F(90),'unused_commitment_released_at_3':F(10),
        'carry_paid_at_3':F(10),'lp_contributions':C,'lp_net_distributions':D,'lp_net_cash':cf,
        'lp_net_irr':irr(cf),'gross_investment_multiple':F(14,9),'lp_net_tvpi':F(65,48),
        'lp_net_dpi':F(65,48),'lp_rvpi':F(0),'gp_management_plus_carry':F(16),'lp_net_profit':F(34)})
    eq(c,'benchmark',o['private']['benchmark'],{'terminal_multipliers':multipliers,
        'fv_contributions':fvc,'fv_net_distributions':fvd,'cash_flow_matched_ratio':fvd/fvc,'terminal_relative_excess':fvd-fvc})
    delayed=[F(0),F(0),F(12),F(118)]
    eq(c,'delayed irr',o['private']['delayed_lp_irr_if_funded'],irr([a-b for a,b in zip(delayed,C)]))
    for name,initial_cash,distributions in [('liquidity_base',90,D),('liquidity_delayed',90,delayed),('repair',96,delayed)]:
        record=o['private'][name] if name!='repair' else o['private']['repair_by_reducing_initial_gated_allocation']['ledger']
        # Cumulative external sources/uses, independent of the model's row recurrence.
        before=[F(initial_cash)-sum(C[:t+1])+sum(distributions[:t])-t for t in range(4)]
        after=[a+b for a,b in zip(before,distributions)]; feasible=min(before)>=0
        for t in range(4):
            eq(c,f'{name} cash{t}',record['ledger'][t],{'before_distribution':before[t],'after_distribution':after[t]})
        eq(c,name,record,{'minimum_cash':min(before),'feasible':feasible,
            'terminal_cash':after[-1] if feasible else None,'additional_initial_reserve_needed':max(F(0),-min(before))})
    cash=F(1000); high=F(1000)
    for i,pnl in enumerate([-20,-10,80]):
        interest=cash/100; fee=cash/100; pre=cash+interest+pnl-fee
        incentive=max(F(0),(pre-high)/5); end=pre-incentive
        eq(c,f'futures row{i}',o['futures']['ledger'][i],{'opening_cash':cash,'interest':interest,
            'management_fee':fee,'variation_cash':F(pnl),'pre_performance_cash':pre,'performance_fee':incentive,
            'ending_cash':end,'ending_high_water':max(high,end),'free_cash_above_margin':end-200})
        cash=end; high=max(high,end)
    eq(c,'futures terminal',o['futures'],{'terminal_cash':cash,'net_total_return':cash/1000-1,
        'spot_total_return':F(3,25),'new_contract_initial_cash_price':F(0)})
    eq(c,'futures margin failure',o['futures']['stress_first_period'],{'ending_cash':F(150),'margin_shortfall':F(50),'feasible':False})
    # Exercise anchors are reconstructed from their separate prompts.
    sale=F(105)/F('.084')*F('.97'); ac=[F(-1020),F(78),F(84),F(90)+sale]
    eq(c,'E1 NPV',sum(a/F('1.1')**i for i,a in enumerate(ac)),F(131660,1331))
    eq(c,'E1 terminal equity',ac[-1]-lender[-1],F('708.9'))
    eq(c,'E2 latent variance',F('.12')**2*(1+F('.5'))/(1-F('.5')),F('.0432'))
    eq(c,'E2 sum variance',2*F('.12')**2*(1+F('.5')),F('.0432'))
    inferred=[2*F(a)-F(b) for a,b in zip(['.01','.05','-.02'],['.04','.01','.05'])]
    eq(c,'E3 unsmoothing',inferred,[F('-.02'),F('.09'),F('-.09')])
    eq(c,'E3 latent wealth',prod(1+r for r in inferred),F('.972062'))
    eq(c,'E4 reduced-distribution net multiple',F(8+12+94,sum(C)),F(19,16))
    eq(c,'E4 FV distributions',F(8)*multipliers[1]+F(12)*multipliers[2]+94,F('113.38'))
    eq(c,'E5 repaired dated balances',[F(98)-sum(C[:t+1])+sum(delayed[:t])-t-(2 if t else 0) for t in range(4)],list(map(F,[58,23,0,9])))
    debtpay=[min(F(108),v) for v in [150,60]]; eqpay=[max(F(0),v-108) for v in [150,60]]
    eq(c,'E6 debt expectation',F('.9')*debtpay[0]+F('.1')*debtpay[1],F('103.2'))
    eq(c,'E6 equity expectation',F('.9')*eqpay[0]+F('.1')*eqpay[1],F('37.8'))
    cash=high=F(500); endings=[]
    for pnl in [-20,10,40]:
        pre=cash+cash/100+pnl-cash/50; cash=pre-max(F(0),(pre-high)/5); high=max(high,cash);endings.append(cash)
    eq(c,'E7 high-water cash',endings,list(map(F,['475','480.25','512.358'])))
    ANCHORS[c]={'property_base_equity_irr':o['property']['base']['equity_irr'],
        'private_net_irr':irr(cf),'delayed_pre_distribution':[50,17,-6,3],'repaired_final_cash':127,
        'smoothing_four_period_sum_variance':str(sumvar),'exercise7_cash':list(map(str,endings))}


def c11():
    c='v09-c11';o=load(c,'output');d=load(c,'inputs')
    prices=[F(p) for p,n in d['book']['asks'] for _ in range(n)]
    for row,limit,fok in zip(o['book']['orders'],[None,F('100.2'),F('100.2')],[False,False,True]):
        available=[p for p in prices if limit is None or p<=limit]
        filled=available[:300] if not fok or len(available)>=300 else []
        n=len(filled);gross=sum(filled,F(0));fee=F('.01')*n
        eq(c,'snapshot '+row['id'],row,{'filled':n,'cancelled':300-n,'gross':gross,'fees':fee,
            'cash_change':-gross-fee,'average':gross/n if n else None})
    eq(c,'signed spreads',o['book']['orders'][0]['spreads'],{'effective':F('.4'),'realized':F('.1'),
        'midpoint_component':F('.3'),'effective_bps':F(40),'realized_bps':F(10),'midpoint_component_bps':F(30)})
    # Enumerate latent value, type and independent liquidity direction.
    states=[]
    for value,informed,p_type in product([98,102],[True,False],[None]):
        if informed: states.append((F(1,2)*F(2,5),value,1 if value==102 else -1,True))
        else:
            for direction in [-1,1]:states.append((F(1,2)*F(3,5)*F(1,2),value,direction,False))
    conditional={s:sum(p*v for p,v,direction,_ in states if direction==s)/sum(p for p,_,direction,_ in states if direction==s) for s in [-1,1]}
    eq(c,'Bayesian dealer',o['dealer'],{'ask':conditional[1],'bid':conditional[-1],
        'spread':conditional[1]-conditional[-1],'high_given_buy':F(7,10),'high_given_sell':F(3,10)})
    dealer=sum(p*direction*(conditional[direction]-v) for p,v,direction,_ in states)
    eq(c,'dealer state profit',o['dealer']['expected_dealer_profit'],dealer)
    for state,row in zip(d['queue']['states'],o['queue']['states']):
        owners=['ahead']*80+['ours']*100;fill=owners[:state['sell_volume']].count('ours')
        used=fill*F('49.91')+(100-fill)*(F(state['deadline_ask'])+F('.01'))
        paper=6000-5000+100*F(state['deadline_mid']); actual=6000-used+100*F(state['deadline_mid'])
        cancel=6000-fill*F('49.91')+fill*F(state['deadline_mid'])
        eq(c,'queue '+state['id'],row,{'passive_fill':fill,'deadline_fill':100-fill,'complete_cash':used,
            'paper_wealth':paper,'complete_wealth':actual,'cancel_wealth':cancel,
            'complete_shortfall':paper-actual,'cancel_shortfall':paper-cancel})
    eq(c,'expected queue',o['queue'],{'expected_complete_cash':F(5033),'expected_complete_shortfall':F(33),'expected_cancel_shortfall':F(132,5)})
    fills=[F('20.25')]*200+[F('20.35')]*150; cash=10000-sum(fills)-350*F('.02')
    actual=cash+350*F('20.5');paper=500*F('20.5')
    eq(c,'shortfall funded wealth',o['shortfall'],{'gross':sum(fills),'fees':F(7),'cash_after_fills':cash,
        'actual_wealth':actual,'paper_wealth':paper,'shortfall':paper-actual,'delay':F(100),
        'execution':sum(p-F('20.2') for p in fills),'opportunity':150*F('.3'),
        'external_vwap':F('20.3'),'filled_vwap_cost':F('-2.5'),'filled_vwap_cost_with_fees':F('4.5')})
    def schedule(a,b):
        # Sum independently priced share slices, not the aggregate quadratic.
        first=sum(F(50)+F('.05')*(F(i)+F(1,2))+F('.2')*a+F('.1') for i in range(a))
        cash=[first+sum(F(50)+shock+F('.05')*(F(a+j)+F(1,2))+F('.1')*b+F('.1') for j in range(b)) for shock in [F('-.5'),F('.5')]]
        costs=[v-50*(a+b) for v in cash];mean=sum(costs)/2;variance=sum((v-mean)**2 for v in costs)/2
        return {'q1':a,'q2':b,'expected_cost':mean,'variance':variance,'objective':mean+F('.4')*variance,'state_cash':cash,'state_costs':costs}
    grids=[]
    for Q,row in enumerate(o['impact']['capacity_grid']):
        allrows=[schedule(a,b) for a in range(6) for b in range(10) if a+b==Q]
        winner=min(allrows,key=lambda p:(p['objective'],p['q1']));grids.append(winner)
        eq(c,f'capacity Q{Q}',row,{'quantity':Q,'q1':winner['q1'],'q2':winner['q2'],
            'objective':winner['objective'],'net_score':F('1.5')*Q-winner['objective'],
            'optimal_schedules':[[p['q1'],p['q2']] for p in allrows if p['objective']==winner['objective']]})
    for row in o['impact']['candidates']:
        eq(c,'required schedule '+str(row['q1']),row,schedule(row['q1'],row['q2']))
    # All eight determinate exercise components, separate from judgments/rubrics.
    eq(c,'E1 sell spreads',[-2*(F('49.95')-p) for p in [F(50),F('49.8')]]+[ -2*(F('49.8')-50)],list(map(F,['.1','-.3','.4'])))
    sells=[F(p) for p,n in d['book']['bids'] for _ in range(n)][:450]
    eq(c,'E2 sale cash',sum(sells)-F('.01')*450,F('44915.5'))
    eq(c,'E2 limited sale cash',sum(p for p in sells if p>=F('99.8'))-4,F(39936))
    eq(c,'E3 quotes',[F(5,8)*104+F(3,8)*96,F(3,8)*104+F(5,8)*96],list(map(F,[101,99])))
    eq(c,'E4 queue cash',F(2,5)*(80*F('49.91')+20*F('49.61'))+F(3,5)*5061,F('5030.6'))
    eq(c,'E4 probability',(F(5061)-5011)/(5061-4991),F(5,7))
    eq(c,'E5 sold actual wealth',250*F('29.85')-5+150*F('29.7'),F('11912.5'))
    eq(c,'E6 vwap',sum(q*p for q,p in [(1000,F('20.1')),(2000,F('20.3')),(2000,F('20.4'))])/5000,F('20.3'))
    eq(c,'E7 integer switch',(F('14.7')-F('14.4'))/(16-F('12.25')),F(2,25))
    eq(c,'E7 continuous boundary',F('1.2')+3*F(6,35),F('1.5')+F('1.25')*F(6,35))
    scores=[2*q-p['objective'] for q,p in enumerate(grids)]
    eq(c,'E8 best authorized size',max(range(15),key=lambda q:scores[q]),8)
    eq(c,'E8 last nonnegative',max(q for q in range(15) if scores[q]>=0),14)
    eq(c,'retention cash needed',sum(fills)+150*F('20.6')+500*F('.02'),F('10202.5'))
    ANCHORS[c]={'fixed_target_schedule':[5,7],'capacity_score_winner':6,'exercise8_size':8,
        'shortfall':str(paper-actual),'source_of_numeric_independence':'unit-price integration and scenario wealth'}


def c12():
    c='v09-c12';d=load(c,'inputs');o=load(c,'output');g=F('1.01')
    states=[(F(s['probability']),F(s['equity_return']),F(s['bond_return'])) for s in d['moment_states']]
    means=[sum(p*r for p,*rs in states for r in [rs[j]]) for j in range(2)]
    cov=[[sum(p*q*(a[i+1]-b[i+1])*(a[j+1]-b[j+1])/2 for a in states for b in states for p,q in [(a[0],b[0])]) for j in range(2)] for i in range(2)]
    eq(c,'pairwise witness',o['moment_witness'],{'mean':means,'covariance':cov,'determinant':cov[0][0]*cov[1][1]-cov[0][1]**2})
    def position(x,y,gamma=4,mean_shift=F(0)):
        fee=abs(F(x)-300)/100+abs(F(y)-400)/200;cash=1000-x-y-fee
        reserves=[x*(1+r+mean_shift)+y*(1+s)+g*(g*cash-150)-50 for _,r,s in states]
        mean=sum(p*r for (p,_,_),r in zip(states,reserves));variance=sum(p*(r-mean)**2 for (p,_,_),r in zip(states,reserves))
        active=[(x-400)*r+(y-400)*s for _,r,s in states];am=sum(p*r for (p,_,_),r in zip(states,active))
        av=sum(p*(r-am)**2 for (p,_,_),r in zip(states,active))
        return {'equity':F(x),'bond':F(y),'fee':fee,'cash':cash,'expected_reserve':mean,
            'variance':variance,'active_variance':av,'criterion':mean-F(gamma,2000)*variance}
    def reserve(p,er,br,l1,l2,D=F(0),X=F(0)):
        after=p['cash']*g+X+D-l1
        return None if after<0 else p['equity']*(1+er)+p['bond']*(1+br)+g*after-l2-F('1.08')*D
    feasible=[];rejections=Counter()
    for x,y in product(range(0,501,10),range(0,601,10)):
        p=position(x,y);reason=[]
        if p['cash']<0:reason.append('cash')
        if p['variance']>10000:reason.append('total_risk')
        if p['active_variance']>36:reason.append('active_risk')
        if g*p['cash']-180<20:reason.append('date1_buffer')
        # Independent future cash aggregation, including both dated feasibility tests.
        values=[reserve(p,F(s['equity_return']),F(s['bond_return']),F(s['grant_t1']),F(s['grant_t2'])) for s in d['design_stresses']]
        if any(v is None or v<650 for v in values) or g*p['cash']-180<20:reason.append('design_stress')
        rejections.update(reason)
        if not reason:feasible.append(p)
    order=lambda p:(-p['criterion'],p['variance'],p['fee'],p['equity'],p['bond'])
    feasible.sort(key=order)
    eq(c,'enumeration count',o['optimization']['candidates'],3111)
    eq(c,'rejection counts',o['optimization']['nonexclusive_rejection_counts'],dict(rejections))
    eq(c,'full independent feasible ranking',o['optimization']['feasible_ranked'],feasible)
    chosen=feasible[0];eq(c,'selected',o['optimization']['selected'],chosen)
    eq(c,'benchmark',o['benchmark'],position(400,400));eq(c,'inherited',o['inherited_position'],position(300,400))
    # Full two-date reserve and borrowing certificates.
    opening=chosen['cash']*g
    eq(c,'grant thresholds',o['date1_bill_thresholds'],{'no_line_keep_buffer':opening-20,'max_line_keep_buffer':opening+5,'max_line_allow_zero_cash':opening+25})
    eq(c,'unfunded event',o['reverse_stress']['no_external_funding_max_line'],{'payment_gap_t1':240-opening-25,
        'buffer_gap_t1':260-opening-25,'cash_after_t1':None,'terminal_reserve':None})
    eq(c,'buffer only',o['reverse_stress']['buffer_only_external_funding_max_line']['terminal_reserve'],reserve(chosen,F('-.25'),F('-.08'),240,60,F(25),260-opening-25))
    repair_values=[]
    for D,key in [(F(0),'both_constraints_no_line'),(F(25),'both_constraints_max_line')]:
        required1=260-opening-D
        # Solve terminal cash required backwards from all date-2 obligations.
        required_end_cash=650+60+F('1.08')*D-F('673.1')
        X=max(F(0),required1,required_end_cash/g+240-opening-D)
        eq(c,key,o['reverse_stress'][key],{'minimum_contribution':X})
        eq(c,key+' terminal',o['reverse_stress'][key]['ledger']['terminal_reserve'],F(650))
        repair_values.append(X)
    eq(c,'minimum repair draw',o['reverse_stress']['minimum_external_funding']['draw'],F(0))
    eq(c,'loan increases outside cost',repair_values[1]-repair_values[0],F(175,101))
    for label,x,y in [('target',370,430),('actual',360,430),('benchmark',400,400)]:
        p=position(x,y);v=reserve(p,F('.12'),F('.01'),150,50)
        eq(c,label+' outcome',o['execution_report'][label+'_ledger'],{'cash_after_t1':g*p['cash']-150,'terminal_reserve':v})
    eq(c,'active failure',o['execution_report']['actual_position'],position(360,430))
    # Exercise interventions use the same independently generated feasible pairs.
    for gamma,xy,score in [(2,(400,400),F('855.5799')),(6,(370,400),F('836.85293'))]:
        ranking=[position(p['equity'],p['bond'],gamma) for p in feasible];ranking.sort(key=order)
        eq(c,'E3 gamma'+str(gamma),[ranking[0]['equity'],ranking[0]['bond'],ranking[0]['criterion']],[F(xy[0]),F(xy[1]),score])
    a,b=position(370,430),position(370,420)
    eq(c,'E3 crossing',2000*(a['expected_reserve']-b['expected_reserve'])/(a['variance']-b['variance']),F(69599,12940))
    draw=220-opening;end=reserve(chosen,F('-.15'),F('-.12'),200,60,draw)
    eq(c,'E4 funded loan still fails',end,F('632.73282'))
    p=position(350,430);end=reserve(p,F('.12'),F('.01'),150,50)
    eq(c,'E6 two unfilled lots',[p['fee'],p['cash'],p['variance'],p['active_variance'],end],list(map(F,['.65','219.35','8555','91','848.558935'])))
    zero=[p for p in feasible if p['active_variance']==0]
    eq(c,'E7 zero active risk',len(zero),1);eq(c,'E7 zero active score',zero[0]['criterion'],F('845.6599'))
    changed=[position(p['equity'],p['bond'],4,F('-.02')) for p in feasible];changed.sort(key=order)
    eq(c,'E7 shifted mean winner',[changed[0]['equity'],changed[0]['bond'],changed[0]['expected_reserve'],changed[0]['criterion']],list(map(F,['370','430','857.052915','838.584515'])))
    eq(c,'retention raised floor',F(660)-reserve(chosen,F('-.15'),F('-.12'),180,60),F('5.747085'))
    ANCHORS[c]={'candidate_pairs':3111,'feasible_pairs':len(feasible),'winner':[370,430],
        'reverse_contribution_zero_line':str(repair_values[0]),'reverse_contribution_full_line':str(repair_values[1]),
        'method':'pairwise witness covariance and direct state-reserve moments for every candidate'}


if __name__=='__main__':
    c10();c11();c12()
    report={'status':'pass','reviewer':'coordinating author','method':'No author model/checker imports; reconstruct from original dated cash, unit prices and state laws.',
        'comparisons_by_chapter':dict(COUNTS),'total_comparisons':sum(COUNTS.values()),'anchors':ANCHORS,
        'audited_outputs':[{ 'path':f'content/projects/{c}-output.json','sha256':hashlib.sha256((ROOT/f'content/projects/{c}-output.json').read_bytes()).hexdigest()} for c in COUNTS],
        'limits':'Finite synthetic arithmetic audit. Proof, pedagogy, complete open-response rubrics and source scope reviewed separately; no human certification or visual UI claim.'}
    target=Path(__file__).with_suffix('.json');target.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
