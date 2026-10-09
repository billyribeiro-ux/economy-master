#!/usr/bin/env python3
"""Tern Scholarship Pool: original point-in-time research and funded policy project."""
import argparse
import datetime as dt
from fractions import Fraction as F
import json
from math import sqrt
from pathlib import Path

CONVENTIONS = {
    'unit':'CU','dates':['2025-01-03','2025-07-03','2026-01-03'],
    'research':'four training periods; four untouched evaluation periods; latest version available at cutoff only',
    'selection':'highest training arithmetic net active mean among admitted open managers with complete training record; ties by asset ID',
    'manager_benchmark':'quarterly 40% E and 60% B comparison, stipulated zero benchmark fees',
    'closure':'CX liquidation is included in period3 net return; proceeds park at zero return with no further fees',
    'stub':'net return zero for every research holding between training end and decision date',
    'risk':'half of four-times quarterly sample covariance plus half supplied annual prior; additive planning proxy, not exact compounded annual variance',
    'private':'existing stake cannot be sold or pledged; capital call is an internal portfolio investment; final proceeds include all capital and exit costs',
    'trading':'initial liquid holdings in 25-CU units at unit reference price; entry costs on actual turnover paid from cash; sell bonds before equity purchases',
    'stress_sale':'outside-design bond sale only under prior board authority; continuous original units at supplied mark less spread and fee; no borrowing',
    'scenario':'planning means, dated conditional stresses and held-out observations are distinct inputs; no scenario probabilities or empirical alpha claim'
}


def need(condition, message):
    if not condition:
        raise ValueError(message)


def num(value):
    if isinstance(value,F):
        return value
    need(type(value) in (int,str),'Use integers or finite rational strings, not floats or booleans')
    try:
        result=F(value)
    except (ValueError,ZeroDivisionError,OverflowError) as exc:
        raise ValueError('invalid rational value') from exc
    need(abs(result)<=10**9 and result.denominator<=10**12,'number exceeds finite case guardrails')
    return result


def keys(value, fields):
    need(isinstance(value,dict) and set(value)==set(fields.split()),'missing or unknown field')


def date(value):
    need(isinstance(value,str),'date must be an ISO string')
    try:
        d=dt.date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError('invalid ISO date') from exc
    need(d.isoformat()==value,'use exact YYYY-MM-DD date')
    return d


def factor(returns):
    value=F(1)
    for r in returns:
        value*=1+r
    return value


def mean(values):
    return sum(values)/len(values)


def covariance(x,y):
    need(len(x)==len(y) and len(x)>1,'matched sample lengths required')
    mx,my=mean(x),mean(y)
    return sum((a-mx)*(b-my) for a,b in zip(x,y))/(len(x)-1)


def available_series(data,asset,periods,cutoff):
    """Each vintage is chosen before computing a return; closure cash is explicit."""
    r=data['research']
    closure=r['closures'].get(asset)
    values=[];trace=[]
    for period in periods:
        if closure and closure['announced_on']<=cutoff and period>closure['last_period']:
            values.append(F(0));trace.append({'period':period,'source':'post-liquidation zero-return cash'})
            continue
        candidates=[v for v in r['series_records'] if v['asset']==asset and v['period']==period and v['released_on']<=cutoff]
        need(candidates,f'missing available observation for {asset} period {period}')
        v=max(candidates,key=lambda v:(v['released_on'],v['version']))
        net=num(v['gross_return'])-num(v['fee_on_beginning_nav'])
        values.append(net)
        trace.append({'period':period,'source':'return record','version':v['version'],
                      'released_on':v['released_on'],'gross_return':num(v['gross_return']),
                      'fee':num(v['fee_on_beginning_nav']),'net_return':net})
    return values,trace


def manager_statistics(returns,benchmark):
    active=[a-b for a,b in zip(returns,benchmark)]
    av=covariance(active,active)
    bmvar=covariance(benchmark,benchmark)
    slope=None if bmvar==0 else covariance(returns,benchmark)/bmvar
    intercept=None if slope is None else mean(returns)-slope*mean(benchmark)
    residual=None if slope is None else [r-intercept-slope*b for r,b in zip(returns,benchmark)]
    return {'net_returns':returns,'mean_net_active':mean(active),'sample_active_variance':av,
            'tracking_error_per_period_approx':sqrt(float(av)),
            'sample_information_ratio_approx':None if av==0 else float(mean(active))/sqrt(float(av)),
            'net_growth_factor':factor(returns),'benchmark_growth_factor':factor(benchmark),
            'compound_relative_wealth':factor(returns)/factor(benchmark)-1,
            'terminal_factor_difference':factor(returns)-factor(benchmark),
            'last_net_active':active[-1],'benchmark_slope':slope,'sample_intercept':intercept,
            'sample_residual_squared_sum':None if residual is None else sum(e*e for e in residual)}


def research_audit(data):
    r=data['research'];cutoff=r['decision_cutoff'];end=r['evaluation_cutoff']
    train=r['training_periods'];holdout=r['holdout_periods']
    et,_=available_series(data,'E',train,cutoff);bt,_=available_series(data,'B',train,cutoff)
    benchmark=[F(2,5)*e+F(3,5)*b for e,b in zip(et,bt)]
    cohort={};eligible=[]
    for asset in r['initial_cohort']:
        series,trace=available_series(data,asset,train,cutoff)
        cohort[asset]={'statistics':manager_statistics(series,benchmark),'vintages':trace}
    for asset in r['manager_ids']:
        closure=r['closures'].get(asset)
        closed=closure is not None and closure['announced_on']<=cutoff and closure['last_period']<=train[-1]
        if r['admitted_on'][asset]<=cutoff and not closed:
            series,trace=available_series(data,asset,train,cutoff)
            eligible.append({'asset':asset,'statistics':manager_statistics(series,benchmark),'vintages':trace})
    need(eligible,'no eligible manager')
    eligible.sort(key=lambda q:(-q['statistics']['mean_net_active'],q['asset']))
    selected=eligible[0]['asset']
    latest_e=available_series(data,'E',train,end)[0]
    latest_b=available_series(data,'B',train,end)[0]
    latest_benchmark=[F(2,5)*e+F(3,5)*b for e,b in zip(latest_e,latest_b)]
    revised=[];backfilled=[]
    for asset in r['manager_ids']:
        if asset in r['closures']:
            continue
        series,trace=available_series(data,asset,train,end)
        record={'asset':asset,'statistics':manager_statistics(series,latest_benchmark),'vintages':trace}
        if asset in [q['asset'] for q in eligible]:revised.append(record)
        backfilled.append(record)
    revised.sort(key=lambda q:(-q['statistics']['mean_net_active'],q['asset']))
    backfilled.sort(key=lambda q:(-q['statistics']['mean_net_active'],q['asset']))
    trials=[]
    for metric in r['search_log']:
        key={'mean_net_active':'mean_net_active','compound_relative':'compound_relative_wealth',
             'last_net_active':'last_net_active','sample_information_ratio':'sample_information_ratio_approx'}[metric]
        valid=[q for q in eligible if q['statistics'][key] is not None]
        winner=min(valid,key=lambda q:(-q['statistics'][key],q['asset']))['asset'] if valid else None
        trials.append({'metric':metric,'winner':winner,'undefined':[q['asset'] for q in eligible if q['statistics'][key] is None]})
    eh,_=available_series(data,'E',holdout,end);bh,_=available_series(data,'B',holdout,end)
    hbenchmark=[F(2,5)*e+F(3,5)*b for e,b in zip(eh,bh)]
    hstats={}
    for q in eligible:
        series,_=available_series(data,q['asset'],holdout,end)
        hstats[q['asset']]=manager_statistics(series,hbenchmark)
    survivors=[a for a in r['initial_cohort'] if a not in r['closures']]
    initial_factors=[cohort[a]['statistics']['net_growth_factor'] for a in r['initial_cohort']]
    survivor_factors=[cohort[a]['statistics']['net_growth_factor'] for a in survivors]
    full={a:factor(available_series(data,a,train+holdout,end)[0]) for a in r['initial_cohort']}
    return {'selection_cutoff':cutoff,'selected_manager':selected,'eligible_ranked':eligible,
            'excluded_managers':{a:('closed before decision' if a in r['closures'] else 'not admitted by decision cutoff') for a in r['manager_ids'] if a not in [q['asset'] for q in eligible]},
            'training_manager_benchmark':benchmark,'initial_cohort_training':cohort,
            'training_full_cohort_return':mean(initial_factors)-1,
            'training_survivor_only_return':mean(survivor_factors)-1,
            'retrospective_same_eligible_ranked':revised,'late_backfilled_ranked':backfilled,
            'search_log_results':trials,'holdout_statistics':hstats,
            'holdout_manager_benchmark':hbenchmark,'holdout_equity_returns':eh,'holdout_bond_returns':bh,
            'final_restated_cohort_growth_factors':full,
            'final_restated_full_cohort_return':mean(list(full.values()))-1,
            'final_restated_survivor_only_return':mean([full[a] for a in survivors])-1,
            'restatement_note':'Final eight-period cohort statistics use all revisions available at evaluation cutoff. They do not replace the frozen selection inputs.'}


def planning_covariance(data):
    r=data['research'];f=data['portfolio']['forecast']
    E=available_series(data,'E',r['training_periods'],r['decision_cutoff'])[0]
    B=available_series(data,'B',r['training_periods'],r['decision_cutoff'])[0]
    series=[E,B]
    sample=[[covariance(series[i],series[j]) for j in range(2)] for i in range(2)]
    prior=[[num(v) for v in row] for row in f['prior_covariance']]
    weight=num(f['sample_weight']);multiplier=num(f['additive_periods_per_year'])
    cov=[[weight*multiplier*sample[i][j]+(1-weight)*prior[i][j] for j in range(2)] for i in range(2)]
    return {'quarterly_sample':sample,'planning_factor_covariance':cov,
            'planning_determinant':cov[0][0]*cov[1][1]-cov[0][1]**2}


def quad(vector,cov):
    return sum(vector[i]*cov[i][j]*vector[j] for i in range(2) for j in range(2))


def holding(data,x,y,z):
    p=data['portfolio'];values=list(map(num,[x,y,z]));names=['E','B','manager']
    fee=sum(num(p['entry_cost_rates'][k])*abs(value-num(p['initial_liquid'][k])) for k,value in zip(names,values))
    cash=num(p['initial_wealth'])-num(p['private_initial_value'])-sum(values)-fee
    return {'E':values[0],'B':values[1],'manager':values[2],'fee':fee,'cash':cash}


def cash_ledger(data,h,scenario,sale=F(0),net_sale_price=F(0)):
    p=data['portfolio'];g=num(p['cash_half_year_factor'])
    sale,net_sale_price=num(sale),num(net_sale_price)
    need(0<=sale<=h['B'] and net_sale_price>=0,'invalid bond sale')
    opening=g*h['cash'];proceeds=sale*net_sale_price
    call,grant,grant2=(num(scenario[k]) for k in ['call_t1','grant_t1','grant_t2'])
    residual=opening+proceeds-call-grant
    payment_gap=max(F(0),-residual);buffer_gap=max(F(0),num(p['policy']['cash_buffer'])-residual)
    cash2=None if residual<0 else residual*g
    liquid2=h['E']*(1+num(scenario['equity_return']))+(h['B']-sale)*(1+num(scenario['bond_return']))+h['manager']*(1+num(scenario['manager_return']))
    private=num(scenario['private_distribution'])
    available=None if cash2 is None else cash2+liquid2+private
    terminal_gap=None if available is None else max(F(0),grant2-available)
    reserve=None if available is None or terminal_gap>0 else available-grant2
    return {'cash_before_t1':opening,'bond_original_units_sold_t1':sale,'net_sale_proceeds_t1':proceeds,
            'capital_call_t1':call,'grant_t1':grant,'payment_gap_t1':payment_gap,'buffer_gap_t1':buffer_gap,
            'cash_after_t1':None if residual<0 else residual,'cash_t2':cash2,'remaining_liquid_proceeds_t2':liquid2,
            'private_distribution_t2':private,'grant_t2':grant2,'payment_gap_t2':terminal_gap,
            'terminal_reserve':reserve,'floor_gap':None if reserve is None else max(F(0),num(p['policy']['terminal_floor'])-reserve),
            'payments_funded':payment_gap==0 and terminal_gap==0,
            'cash_and_floor_pass':buffer_gap==0 and reserve is not None and reserve>=num(p['policy']['terminal_floor'])}


def assess(data,h,cov):
    p=data['portfolio'];f=p['forecast'];policy=p['policy'];g=num(p['cash_half_year_factor']);W=num(p['initial_wealth'])
    x,y,z=(h[k] for k in ['E','B','manager']);be,bb=num(f['manager_equity_loading']),num(f['manager_bond_loading'])
    exposures=[x+be*z+num(f['private_equity_loading']),y+bb*z+num(f['private_bond_loading'])]
    variance=quad(exposures,cov)+z*z*num(f['manager_residual_variance'])+num(f['private_residual_variance'])
    benchmark=p['benchmark'];active=[x-num(benchmark['E'])+be*(z-num(benchmark['manager'])),y-num(benchmark['B'])+bb*(z-num(benchmark['manager']))]
    av=quad(active,cov)+(z-num(benchmark['manager']))**2*num(f['manager_residual_variance'])
    flows=p['planning_flows']
    common=(1+num(f['equity_mean']))*x+(1+num(f['bond_mean']))*y+g*(g*h['cash']-num(flows['call_t1'])-num(flows['grant_t1']))+num(f['private_distribution_mean'])-num(flows['grant_t2'])
    base_manager=be*num(f['equity_mean'])+bb*num(f['bond_mean'])-num(f['manager_annual_fee'])
    low=common+z*(1+base_manager+num(f['manager_overlay_lower']))
    high=common+z*(1+base_manager+num(f['manager_overlay_upper']))
    penalty=num(policy['gamma'])*variance/(2*W)
    bills=[num(flows['call_t1'])+num(flows['grant_t1'])]+[num(s['call_t1'])+num(s['grant_t1']) for s in p['design_stresses']]
    margin=g*h['cash']-max(bills)-num(policy['cash_buffer'])
    violations=[]
    if h['cash']<0:violations.append('negative_cash')
    if any(value<0 or value>num(p['caps'][k]) for k,value in [('E',x),('B',y),('manager',z)]):violations.append('position_cap')
    if any(value%num(p['lot']) for value in [x,y,z]):violations.append('initial_lot')
    if variance>num(policy['total_variance_limit']):violations.append('total_risk')
    if av>num(policy['active_variance_limit']):violations.append('active_risk')
    if margin<0:violations.append('cash_buffer')
    stresses={s['name']:cash_ledger(data,h,s) for s in p['design_stresses']}
    if any(not v['cash_and_floor_pass'] for v in stresses.values()):violations.append('design_stress')
    return {**h,'factor_exposures_including_private':exposures,'variance':variance,'active_variance':av,
            'lower_mean_reserve':low,'upper_mean_reserve':high,'robust_score':low-penalty,'nominal_score':high-penalty,
            'date1_cash_margin':margin,'feasible':not violations,'violations':violations,'stresses':stresses}


def optimize(data,cov):
    p=data['portfolio'];lot=num(p['lot']);feasible=[];rejections={};total=0
    for i in range(int(num(p['caps']['E'])/lot)+1):
        for j in range(int(num(p['caps']['B'])/lot)+1):
            for k in range(int(num(p['caps']['manager'])/lot)+1):
                a=assess(data,holding(data,i*lot,j*lot,k*lot),cov);total+=1
                if a['feasible']:feasible.append(a)
                for why in a['violations']:rejections[why]=rejections.get(why,0)+1
    need(feasible,'no feasible portfolio')
    def rank(key):return sorted(feasible,key=lambda a:(-a[key],a['variance'],a['fee'],a['E'],a['B'],a['manager']))
    robust,nominal=rank('robust_score'),rank('nominal_score')
    fields=['E','B','manager','fee','cash','variance','active_variance','lower_mean_reserve','upper_mean_reserve','robust_score','nominal_score']
    return {'candidate_count':total,'feasible_count':len(feasible),'nonexclusive_rejections':rejections,
            'robust':robust[0],'nominal':nominal[0],
            'robust_ranked':[{key:a[key] for key in fields} for a in robust]},feasible


def implementation(data,opt,feasible,cov):
    p=data['portfolio'];e=p['execution'];target=opt['robust'];old=p['initial_liquid']
    if target['E']<num(old['E']) or target['B']>num(old['B']):
        return {'available':False,'reason':'execution fixture requires a bond-sale/equity-buy target'}
    sale_required=num(old['B'])-target['B'];sale=min(sale_required,num(e['available_bond_sale_units']))
    actual_bond=num(old['B'])-sale
    naive=assess(data,holding(data,target['E'],actual_bond,target['manager']),cov)
    permitted=[a for a in feasible if a['B']==actual_bond and a['manager']==target['manager'] and num(old['E'])<=a['E']<=target['E']]
    if not permitted:
        return {'available':False,'reason':'no preauthorized feasible continuation after the partial bond sale',
                'bond_sale_executed':sale,'naive_complete_equity_order':naive}
    chosen=min(permitted,key=lambda a:(-a['robust_score'],a['variance'],a['fee'],a['E']))
    return {'available':True,'target_bond_sale':sale_required,'bond_sale_executed':sale,
            'unfilled_bond_sale':sale_required-sale,'unfilled_equity_buy':target['E']-chosen['E'],
            'naive_complete_equity_order':naive,'authorized_fallback':chosen,
            'rule':'Bond sale settles before the equity order is sized; no buy-and-resell or hidden extra fee.'}


def reporting(data,audit,opt,execution,benchmark):
    r=data['research'];p=data['portfolio'];selected=audit['selected_manager']
    eg=factor(audit['holdout_equity_returns']);bg=factor(audit['holdout_bond_returns'])
    mg=factor(available_series(data,selected,r['holdout_periods'],r['evaluation_cutoff'])[0])
    scenario={**p['realized_private'],'equity_return':eg-1,'bond_return':bg-1,'manager_return':mg-1}
    rows={'target':cash_ledger(data,opt['robust'],scenario),'nominal_counterfactual':cash_ledger(data,opt['nominal'],scenario),
          'benchmark':cash_ledger(data,benchmark,scenario)}
    if execution['available']:
        rows['actual']=cash_ledger(data,execution['authorized_fallback'],scenario)
    gap=None
    if 'actual' in rows and all(rows[k]['terminal_reserve'] is not None for k in ['actual','target','benchmark']):
        actual,target,bmark=(rows[k]['terminal_reserve'] for k in ['actual','target','benchmark'])
        g=num(p['cash_half_year_factor']);h=execution['authorized_fallback'];t=opt['robust']
        opportunity=(t['E']-h['E'])*(eg-1)+(t['B']-h['B'])*(bg-1)+(t['manager']-h['manager'])*(mg-1)
        fee_adjustment=(h['fee']-t['fee'])*g*g
        cash_principal_adjustment=(sum(t[k]-h[k] for k in ['E','B','manager']))*(1-g*g)
        gap={'policy_selection':target-bmark,'implementation':actual-target,'total':actual-bmark,
             'target_minus_actual_opportunity_component':opportunity,
             'fee_difference_at_terminal':fee_adjustment,
             'cash_principal_timing_adjustment':cash_principal_adjustment,
             'target_minus_actual_reserve':opportunity+fee_adjustment+cash_principal_adjustment}
    return {'manager_used':selected,'realized_liquid_factors':{'E':eg,'B':bg,'manager':mg},
            'cash_ledgers':rows,'reserve_gap_decomposition':gap,
            'return_scope':'Matched wealth outcomes; no TWR is claimed without flow-boundary values for the private stake.'}


def forced_sale(data,h):
    p=data['portfolio'];s=p['outside_stress'];g=num(p['cash_half_year_factor'])
    mark=num(s['bond_t1_mark']);spread=num(s['bond_spread_per_original_unit']);fee=num(s['bond_fee_per_original_unit'])
    net=mark-spread-fee
    bill=num(s['call_t1'])+num(s['grant_t1']);needed=max(F(0),(bill+num(p['policy']['cash_buffer'])-g*h['cash'])/net)
    actual=min(needed,h['B'],num(s['bond_sale_capacity']))
    ledger=cash_ledger(data,h,s,actual,net)
    return {'bond_net_price_per_original_unit':net,'required_original_units_for_buffer':needed,
            'actual_original_units_sold':actual,'gross_marked_value_removed':actual*mark,
            'spread_cost':actual*spread,'fee_cost':actual*fee,'net_cash_raised':actual*net,
            'forgone_bond_terminal_proceeds':actual*(1+num(s['bond_return'])),'ledger':ledger,
            'external_funding_at_terminal_to_restore_floor':ledger['floor_gap'],
            'scope':'Authorized contingency sale funds dated cash. Any reserve-floor gap remains visible; outside contributions are not assumed.'}


def serial(value):
    if isinstance(value,F):return str(value)
    if isinstance(value,dict):return {k:serial(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [serial(v) for v in value]
    return value


def validate(data):
    keys(data,'schema case provenance conventions research portfolio')
    need(data['schema']=='v09-assessment-tern-1' and data['case']=='Tern Scholarship Pool','wrong fixture identity')
    need(data['conventions']==CONVENTIONS,'fixed timing, provenance or policy convention contradicted')
    need(data['provenance']=='All data, identifiers, vintages, prices, private claims and policy choices are original synthetic teaching inputs; no observations or current legal facts.','synthetic provenance must remain explicit')
    r=data['research'];keys(r,'decision_cutoff evaluation_cutoff training_periods holdout_periods initial_cohort manager_ids admitted_on closures selection_rule_frozen_on search_log series_records')
    need(r['training_periods']==[1,2,3,4] and r['holdout_periods']==[5,6,7,8],'fixed training and holdout partitions')
    need(r['initial_cohort']==['K','M','CX'] and r['manager_ids']==['K','M','CX','N'],'fixed original cohort and manager universe')
    need(r['search_log']==['mean_net_active','compound_relative','last_net_active','sample_information_ratio'],'complete four-trial search record required')
    need(date(r['selection_rule_frozen_on'])<=date(r['decision_cutoff'])<date(r['evaluation_cutoff']),'selection/evaluation order')
    keys(r['admitted_on'],'K M CX N');keys(r['closures'],'CX');keys(r['closures']['CX'],'last_period announced_on')
    need(r['closures']['CX']['last_period']==3,'fixed liquidation period')
    need(date(r['closures']['CX']['announced_on'])<=date(r['decision_cutoff']),'liquidation must be known by selection')
    for value in r['admitted_on'].values():date(value)
    need(all(r['admitted_on'][a]<='2024-01-01' for a in r['initial_cohort']),'initial cohort must exist before training')
    need(isinstance(r['series_records'],list) and 1<=len(r['series_records'])<=100,'bounded research records')
    seen=set();endings={}
    for row in r['series_records']:
        keys(row,'asset period version observation_end released_on gross_return fee_on_beginning_nav')
        need(row['asset'] in ['E','B','K','M','CX','N'] and type(row['period']) is int and 1<=row['period']<=8 and type(row['version']) is int and row['version']>0,'invalid record key')
        key=(row['asset'],row['period'],row['version']);need(key not in seen,'duplicate version');seen.add(key)
        need(date(row['observation_end'])<date(row['released_on']),'release must follow observation end')
        if row['period'] in endings:need(endings[row['period']]==row['observation_end'],'common return boundaries required')
        endings[row['period']]=row['observation_end']
        gross,fee=num(row['gross_return']),num(row['fee_on_beginning_nav'])
        need(-1<gross-fee<=10 and 0<=fee<1,'nonpositive net wealth or invalid fee')
        if row['asset'] in ['E','B']:need(fee==0,'index return fee perimeter fixed')
        if row['asset']=='CX':need(row['period']<=3,'do not invent post-liquidation fund returns')
        if row['asset'] in r['manager_ids']:need(row['released_on']>=r['admitted_on'][row['asset']],'record predates database admission')
    need(set(endings)==set(range(1,9)) and all(endings[i]<endings[i+1] for i in range(1,8)),'ordered complete observation periods')
    need([endings[i] for i in range(1,9)]==['2024-03-31','2024-06-30','2024-09-30','2024-12-31','2025-04-03','2025-07-03','2025-10-03','2026-01-03'],'fixed research boundaries must match the stated quarterly and portfolio horizons')
    need(endings[3]<=r['closures']['CX']['announced_on'],'liquidation announcement cannot precede the last return boundary')
    need(endings[4]<r['decision_cutoff']<endings[5] and endings[8]<r['evaluation_cutoff'],'cutoffs must separate training/holdout information')
    need(r['decision_cutoff']==data['conventions']['dates'][0],'decision cutoff and portfolio date must agree')
    for a in ['E','B','K','M','N']:
        available_series(data,a,list(range(1,9)),r['evaluation_cutoff'])
    available_series(data,'CX',[1,2,3],r['decision_cutoff'])
    p=data['portfolio'];keys(p,'initial_wealth private_initial_value initial_liquid lot caps entry_cost_rates cash_half_year_factor benchmark policy forecast planning_flows design_stresses outside_stress execution realized_private')
    for k in ['initial_liquid','caps','entry_cost_rates','benchmark']:keys(p[k],'E B manager')
    for k in ['initial_liquid','caps','benchmark']:
        need(all(num(v)>=0 for v in p[k].values()),'nonnegative long positions required')
    W,P,lot=num(p['initial_wealth']),num(p['private_initial_value']),num(p['lot'])
    need(0<P<W<=1000000 and lot==25,'positive bounded wealth/private stake and fixed 25-CU lot')
    need(sum(num(v) for v in p['initial_liquid'].values())<=W-P,'inherited assets exceed budget')
    need(all(num(v)%lot==0 for k in ['initial_liquid','caps','benchmark'] for v in p[k].values()),'initial grid fields must be lots')
    count=1
    for value in p['caps'].values():count*=int(num(value)/lot)+1
    need(count<=10000,'bounded exhaustive grid required')
    need(all(0<=num(v)<1 for v in p['entry_cost_rates'].values()),'invalid entry costs')
    need(1<=num(p['cash_half_year_factor'])<=2,'cash factor outside scope')
    keys(p['policy'],'gamma total_variance_limit active_variance_limit cash_buffer terminal_floor')
    need(num(p['policy']['gamma'])>0 and all(num(v)>=0 for v in p['policy'].values()),'positive preference/nonnegative limits required')
    f=p['forecast'];keys(f,'equity_mean bond_mean manager_equity_loading manager_bond_loading manager_annual_fee manager_overlay_lower manager_overlay_upper manager_residual_variance prior_covariance sample_weight additive_periods_per_year private_distribution_mean private_equity_loading private_bond_loading private_residual_variance')
    for k,v in f.items():
        if k!='prior_covariance':num(v)
    need(num(f['sample_weight'])==F(1,2) and num(f['additive_periods_per_year'])==4,'fixed disclosed covariance blend')
    need(num(f['manager_equity_loading'])==F(2,5) and num(f['manager_bond_loading'])==F(3,5),'manager comparison and loadings must agree')
    need(0<=num(f['manager_overlay_lower'])<=num(f['manager_overlay_upper']) and 0<=num(f['manager_annual_fee'])<1,'invalid overlay interval/fee')
    need(num(f['manager_residual_variance'])>0 and num(f['private_residual_variance'])>0 and num(f['private_distribution_mean'])>0,'positive residual variances/private mean proceeds')
    need(num(f['equity_mean'])>-1 and num(f['bond_mean'])>-1,'positive mean gross returns required')
    need(1+F(2,5)*num(f['equity_mean'])+F(3,5)*num(f['bond_mean'])-num(f['manager_annual_fee'])+num(f['manager_overlay_lower'])>0,'positive lower mean manager gross return required')
    matrix=f['prior_covariance'];need(isinstance(matrix,list) and len(matrix)==2 and all(isinstance(row,list) and len(row)==2 for row in matrix),'two-factor covariance required')
    v=[[num(x) for x in row] for row in matrix]
    need(v[0][1]==v[1][0] and v[0][0]>0 and v[0][0]*v[1][1]>v[0][1]**2,'symmetric positive-definite prior required')
    keys(p['planning_flows'],'call_t1 grant_t1 grant_t2')
    keys(p['realized_private'],'call_t1 grant_t1 grant_t2 private_distribution')
    for obj in [p['planning_flows'],p['realized_private']]:need(all(num(v)>=0 for v in obj.values()),'nonnegative cash obligations/proceeds')
    need(isinstance(p['design_stresses'],list) and 1<=len(p['design_stresses'])<=10,'bounded stress set required')
    names=set()
    for s in p['design_stresses']+[p['outside_stress']]:
        extra=' bond_t1_mark bond_spread_per_original_unit bond_fee_per_original_unit bond_sale_capacity' if s is p['outside_stress'] else ''
        keys(s,'name equity_return bond_return manager_return private_distribution call_t1 grant_t1 grant_t2'+extra)
        need(isinstance(s['name'],str) and s['name'] and s['name'] not in names,'unique named stresses');names.add(s['name'])
        need(all(-1<=num(s[k])<=10 for k in ['equity_return','bond_return','manager_return']),'invalid stressed return')
        need(all(num(s[k])>=0 for k in ['private_distribution','call_t1','grant_t1','grant_t2']),'nonnegative stress cash flows')
    s=p['outside_stress'];need(num(s['bond_t1_mark'])>num(s['bond_spread_per_original_unit'])+num(s['bond_fee_per_original_unit']) and min(num(s[k]) for k in ['bond_spread_per_original_unit','bond_fee_per_original_unit','bond_sale_capacity'])>=0,'funded positive net stress sale price/capacity required')
    e=p['execution'];keys(e,'available_bond_sale_units mode equity_buy_unit_price bond_sale_unit_price')
    need(e['mode']=='bond_sale_first_then_choose_best_feasible_portfolio_with_that_exact_sale' and num(e['equity_buy_unit_price'])==1 and num(e['bond_sale_unit_price'])==1,'fixed execution order/prices contradicted')
    need(num(e['available_bond_sale_units'])>=0 and num(e['available_bond_sale_units'])%lot==0,'execution capacity must be nonnegative lots')
    cov=planning_covariance(data)['planning_factor_covariance']
    # A disclosed bounded joint law witnesses moment consistency, not a fitted law.
    # Four independent equiprobable signs drive two factors and two residuals.
    a=sqrt(float(cov[0][0]));b=float(cov[0][1])/a
    c=sqrt(float(cov[1][1]-cov[0][1]*cov[0][1]/cov[0][0]))
    manager_bound=abs(.4*a+.6*b)+.6*c+sqrt(float(num(f['manager_residual_variance'])))
    pe,pb=float(num(f['private_equity_loading'])),float(num(f['private_bond_loading']))
    private_bound=abs(pe*a+pb*b)+abs(pb*c)+sqrt(float(num(f['private_residual_variance'])))
    need(1+float(num(f['equity_mean']))>a+1e-12 and 1+float(num(f['bond_mean']))>abs(b)+c+1e-12,'bounded planning law requires positive liquid gross payoffs')
    manager_mean=.4*float(num(f['equity_mean']))+.6*float(num(f['bond_mean']))-float(num(f['manager_annual_fee']))+float(num(f['manager_overlay_lower']))
    need(1+manager_mean>manager_bound+1e-12 and float(num(f['private_distribution_mean']))>private_bound+1e-12,'bounded planning law requires positive manager/private payoffs')
    need(assess(data,holding(data,*[num(p['benchmark'][k]) for k in ['E','B','manager']]),cov)['feasible'],'declared policy benchmark is infeasible')


def run(data):
    validate(data)
    audit=research_audit(data);risk=planning_covariance(data);cov=risk['planning_factor_covariance']
    opt,feasible=optimize(data,cov);p=data['portfolio']
    benchmark=assess(data,holding(data,*[num(p['benchmark'][k]) for k in ['E','B','manager']]),cov)
    execution=implementation(data,opt,feasible,cov)
    return serial({'case':data['case'],'research':audit,'risk_model':risk,'optimization':opt,'benchmark':benchmark,
                   'implementation':execution,'realized_report':reporting(data,audit,opt,execution,benchmark),
                   'outside_design':forced_sale(data,opt['robust']),
                   'limits':'Synthetic vintage audit and conditional policy; no empirical alpha validation, real investment recommendation, scenario probabilities or legal certification.'})


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,default=Path(__file__).with_name('v09-assessment-inputs.json'))
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    value=run(json.loads(args.input.read_text()))
    text=json.dumps(value,indent=2,allow_nan=False)+'\n'
    if args.output:args.output.write_text(text)
    else:print(text,end='')


if __name__=='__main__':
    main()
