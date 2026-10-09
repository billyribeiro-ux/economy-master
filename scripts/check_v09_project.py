#!/usr/bin/env python3
"""Independent exact checks for the original Tern integrated project; quiet check()."""
import contextlib
import copy
from fractions import Fraction as F
import hashlib
from html.parser import HTMLParser
import importlib.util
import io
import itertools
import json
from math import isclose, sqrt
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'content/projects'
STEM = 'v09-assessment-'


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def load_json(path):
    def bad(value):
        raise ValueError('non-finite JSON constant: '+value)
    return json.loads(path.read_text(), parse_constant=bad)


class Checks:
    def __init__(self):
        self.comparisons = 0
        self.groups = []
        self.rejections = 0

    def eq(self, actual, expected, label):
        self.comparisons += 1
        if isinstance(expected, F):
            require(isinstance(actual, str) and F(actual) == expected, label)
        elif isinstance(expected, float):
            require(isinstance(actual, (int, float)) and not isinstance(actual, bool)
                    and isclose(actual, expected, rel_tol=1e-11, abs_tol=1e-12), label)
        else:
            require(actual == expected, label)

    def group(self, name):
        self.groups.append(name)


def product(values):
    result = F(1)
    for v in values:
        result *= v
    return result


def sample_cov(x, y):
    n = len(x)
    return (sum(a*b for a,b in zip(x,y))-sum(x)*sum(y)/n)/(n-1)


def records_at(data, asset, periods, cutoff):
    # Independent keyed reconstruction, with the liquidation account kept alive.
    rows = {}
    for row in data['research']['series_records']:
        if row['asset'] == asset and row['released_on'] <= cutoff:
            key = row['period']
            if key not in rows or (row['released_on'], row['version']) > (rows[key]['released_on'], rows[key]['version']):
                rows[key] = row
    result = []
    for period in periods:
        if asset == 'CX' and period >= 4:
            result.append(F(0))
        else:
            row = rows[period]
            result.append(F(row['gross_return'])-F(row['fee_on_beginning_nav']))
    return result


def metrics(values, benchmark):
    n = len(values); active = [a-b for a,b in zip(values,benchmark)]
    ma = sum(active)/n; var = sample_cov(active,active)
    slope = sample_cov(values,benchmark)/sample_cov(benchmark,benchmark)
    intercept = sum(values)/n-slope*sum(benchmark)/n
    gv = product([1+a for a in values]); gb = product([1+a for a in benchmark])
    return {
        'net_returns': [str(a) for a in values], 'mean_net_active': ma,
        'sample_active_variance': var, 'tracking_error_per_period_approx': sqrt(float(var)),
        'sample_information_ratio_approx': None if not var else float(ma)/sqrt(float(var)),
        'net_growth_factor': gv, 'benchmark_growth_factor': gb,
        'compound_relative_wealth': gv/gb-1, 'terminal_factor_difference': gv-gb,
        'last_net_active': active[-1], 'benchmark_slope': slope, 'sample_intercept': intercept,
        'sample_residual_squared_sum': sum((v-intercept-slope*b)**2 for v,b in zip(values,benchmark))
    }


def independent_claim_cov(data):
    r=data['research']; p=data['portfolio']; f=p['forecast']
    e=records_at(data,'E',range(1,5),r['decision_cutoff'])
    b=records_at(data,'B',range(1,5),r['decision_cutoff'])
    ss=[[sample_cov(x,y) for y in [e,b]] for x in [e,b]]
    cov=[[2*ss[i][j]+F(f['prior_covariance'][i][j])/2 for j in range(2)] for i in range(2)]
    L=[[F(1),F(0)],[F(0),F(1)],[F(2,5),F(3,5)],
       [F(f['private_equity_loading']),F(f['private_bond_loading'])]]
    claim=[[sum(L[i][a]*cov[a][b]*L[j][b] for a in range(2) for b in range(2)) for j in range(4)] for i in range(4)]
    claim[2][2]+=F(f['manager_residual_variance']); claim[3][3]+=F(f['private_residual_variance'])
    return ss,cov,claim


def bilinear(w, cov):
    return sum(w[i]*cov[i][j]*w[j] for i in range(len(w)) for j in range(len(w)))


def budget(data, positions):
    p=data['portfolio']; names=['E','B','manager']
    fee=sum(F(p['entry_cost_rates'][k])*abs(v-F(p['initial_liquid'][k])) for k,v in zip(names,positions))
    cash=F(p['initial_wealth'])-F(p['private_initial_value'])-sum(positions)-fee
    return fee,cash


def ledger(data, positions, scenario, sale=F(0), net_price=F(0)):
    # Derive treasury directly from two cash dates and remaining security units.
    p=data['portfolio']; fee,c=budget(data,positions); g=F(p['cash_half_year_factor'])
    x,y,z=positions; call=F(scenario['call_t1']); grant=F(scenario['grant_t1'])
    grant2=F(scenario['grant_t2']); private=F(scenario['private_distribution'])
    opening=c*g; cash1=opening+sale*net_price-call-grant
    liquid=x*(1+F(scenario['equity_return']))+(y-sale)*(1+F(scenario['bond_return']))+z*(1+F(scenario['manager_return']))
    cash2=None if cash1<0 else cash1*g
    total=None if cash2 is None else cash2+liquid+private
    gap2=None if total is None else max(F(0),grant2-total)
    reserve=None if total is None or gap2 else total-grant2
    buffer_gap=max(F(0),F(p['policy']['cash_buffer'])-cash1)
    gap1=max(F(0),-cash1)
    return {
        'cash_before_t1':opening, 'bond_original_units_sold_t1':sale, 'net_sale_proceeds_t1':sale*net_price,
        'capital_call_t1':call, 'grant_t1':grant, 'payment_gap_t1':gap1, 'buffer_gap_t1':buffer_gap,
        'cash_after_t1':None if cash1<0 else cash1, 'cash_t2':cash2,
        'remaining_liquid_proceeds_t2':liquid, 'private_distribution_t2':private, 'grant_t2':grant2,
        'payment_gap_t2':gap2, 'terminal_reserve':reserve,
        'floor_gap':None if reserve is None else max(F(0),F(p['policy']['terminal_floor'])-reserve),
        'payments_funded':gap1==0 and gap2==0,
        'cash_and_floor_pass':buffer_gap==0 and reserve is not None and reserve>=F(p['policy']['terminal_floor'])
    }


def independent_grid(data):
    p=data['portfolio']; f=p['forecast']; pol=p['policy']; _,cov,C=independent_claim_cov(data)
    lot=F(p['lot']); W=F(p['initial_wealth']); g=F(p['cash_half_year_factor'])
    benchmark=[F(p['benchmark'][k]) for k in ['E','B','manager']]
    private=F(f['private_distribution_mean']); bills=[F(s['call_t1'])+F(s['grant_t1']) for s in [p['planning_flows']]+p['design_stresses']]
    feasible=[]; all_rows={}; rejects={}
    ranges=[range(int(F(p['caps'][k])/lot)+1) for k in ['E','B','manager']]
    for index in itertools.product(*ranges):
        pos=[lot*i for i in index]; x,y,z=pos; fee,c=budget(data,pos)
        V=bilinear(pos+[F(1)],C)
        active=bilinear([pos[i]-benchmark[i] for i in range(3)]+[F(0)],C)
        flows=p['planning_flows']
        pre_private=x*(1+F(f['equity_mean']))+y*(1+F(f['bond_mean']))+g*g*c-g*(F(flows['call_t1'])+F(flows['grant_t1']))+private-F(flows['grant_t2'])
        manager_base=F(2,5)*F(f['equity_mean'])+F(3,5)*F(f['bond_mean'])-F(f['manager_annual_fee'])
        lo=pre_private+z*(1+manager_base+F(f['manager_overlay_lower']))
        hi=pre_private+z*(1+manager_base+F(f['manager_overlay_upper']))
        penalty=F(pol['gamma'])*V/(2*W)
        margin=g*c-max(bills)-F(pol['cash_buffer'])
        failures=[]
        if c<0:failures.append('negative_cash')
        if V>F(pol['total_variance_limit']):failures.append('total_risk')
        if active>F(pol['active_variance_limit']):failures.append('active_risk')
        if margin<0:failures.append('cash_buffer')
        stresses={s['name']:ledger(data,pos,s) for s in p['design_stresses']}
        if any(not s['cash_and_floor_pass'] for s in stresses.values()):failures.append('design_stress')
        row={'E':x,'B':y,'manager':z,'fee':fee,'cash':c,'variance':V,'active_variance':active,
             'lower_mean_reserve':lo,'upper_mean_reserve':hi,'robust_score':lo-penalty,'nominal_score':hi-penalty,
             'date1_cash_margin':margin,'feasible':not failures,'violations':failures,'stresses':stresses}
        all_rows[tuple(pos)]=row
        if not failures:feasible.append(row)
        for why in failures:rejects[why]=rejects.get(why,0)+1
    rank=lambda key:sorted(feasible,key=lambda r:(-r[key],r['variance'],r['fee'],r['E'],r['B'],r['manager']))
    return rank('robust_score'),rank('nominal_score'),all_rows,rejects,C


class ProjectHTML(HTMLParser):
    def __init__(self):
        super().__init__();self.ids=[];self.h1=0;self.links=[];self.points=[];self.solution_items=0;self.stack=[];self.words=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs);self.stack.append((tag,a))
        if 'id' in a:self.ids.append(a['id'])
        if tag=='h1':self.h1+=1
        if tag=='a':self.links.append(a.get('href',''))
        if tag=='tr' and 'data-points' in a:self.points.append(int(a['data-points']))
        if tag=='li' and any(t=='details' and 'solutions' in v.get('class','').split() for t,v in self.stack):
            if len(self.stack)>=2 and self.stack[-2][0]=='ol':self.solution_items+=1
        if tag in ['br','hr','img','input','meta','link','source','wbr']:self.stack.pop()
    def handle_endtag(self,tag):
        for i in range(len(self.stack)-1,-1,-1):
            if self.stack[i][0]==tag:self.stack=self.stack[:i];break
    def handle_data(self,data):
        self.words.extend(data.split())


def check():
    t=Checks(); data=load_json(ASSETS/(STEM+'inputs.json')); preserved=load_json(ASSETS/(STEM+'output.json'))
    script=ASSETS/(STEM+'analysis.py')
    spec=importlib.util.spec_from_file_location('tern_benchmark',script); model=importlib.util.module_from_spec(spec)
    captured=io.StringIO(); original=copy.deepcopy(data)
    with contextlib.redirect_stdout(captured),contextlib.redirect_stderr(captured):
        spec.loader.exec_module(model); result=model.run(data)
    t.eq(captured.getvalue(),'','quiet import and run');t.eq(data,original,'run must not mutate input')
    t.eq(result,preserved,'complete strict reference-output regression')
    json.dumps(result,allow_nan=False)
    t.group('quiet API and complete preserved output')

    # The raw records supply expected evidence; no author-model helper is used.
    r=data['research']; audit=result['research'];cut=r['decision_cutoff'];end=r['evaluation_cutoff']
    e=records_at(data,'E',range(1,5),cut);b=records_at(data,'B',range(1,5),cut)
    bm=[F(2,5)*x+F(3,5)*y for x,y in zip(e,b)]
    t.eq(audit['training_manager_benchmark'],[str(x) for x in bm],'training comparison')
    t.eq([q['asset'] for q in audit['eligible_ranked']],['K','M'],'admitted open complete candidates')
    t.eq(audit['selected_manager'],'K','frozen selection')
    t.eq(audit['excluded_managers'],{'CX':'closed before decision','N':'not admitted by decision cutoff'},'both exclusions disclosed')
    for row in audit['eligible_ranked']:
        expected=metrics(records_at(data,row['asset'],range(1,5),cut),bm)
        for k,v in expected.items():t.eq(row['statistics'][k],v,'training '+row['asset']+' '+k)
        for period,trace in enumerate(row['vintages'],1):
            records=[v for v in r['series_records'] if v['asset']==row['asset'] and v['period']==period and v['released_on']<=cut]
            raw=max(records,key=lambda v:(v['released_on'],v['version']))
            t.eq(trace['version'],raw['version'],'chosen version');t.eq(trace['released_on'],raw['released_on'],'chosen release')
            t.eq(trace['net_return'],F(raw['gross_return'])-F(raw['fee_on_beginning_nav']),'net fee base')
    late_bm=[F(2,5)*x+F(3,5)*y for x,y in zip(records_at(data,'E',range(1,5),end),records_at(data,'B',range(1,5),end))]
    for collection in ['retrospective_same_eligible_ranked','late_backfilled_ranked']:
        for row in audit[collection]:
            expected=metrics(records_at(data,row['asset'],range(1,5),end),late_bm)
            for k,v in expected.items():t.eq(row['statistics'][k],v,collection+' '+row['asset']+' '+k)
    t.eq([x['asset'] for x in audit['retrospective_same_eligible_ranked']],['M','K'],'later revision changes ranking')
    t.eq([x['asset'] for x in audit['late_backfilled_ranked']],['N','M','K'],'backfill changes universe')
    t.eq([x['winner'] for x in audit['search_log_results']],['K','K','K','M'],'complete four-trial result')
    t.eq(audit['search_log_results'][-1]['undefined'],['K'],'zero TE has undefined IR')
    t.group('point-in-time selection, late revisions and complete search')

    cohort={a:product([1+x for x in records_at(data,a,range(1,5),cut)]) for a in ['K','M','CX']}
    t.eq(audit['training_full_cohort_return'],sum(cohort.values())/3-1,'full cohort training')
    t.eq(audit['training_survivor_only_return'],(cohort['K']+cohort['M'])/2-1,'survivor comparison')
    t.eq(audit['initial_cohort_training']['CX']['statistics']['net_growth_factor'],F(1911,2500),'CX last loss retained')
    t.eq(audit['initial_cohort_training']['CX']['vintages'][-1]['source'],'post-liquidation zero-return cash','closure cash trace')
    h_e=records_at(data,'E',range(5,9),end);h_b=records_at(data,'B',range(5,9),end)
    h_bm=[F(2,5)*x+F(3,5)*y for x,y in zip(h_e,h_b)]
    t.eq(audit['holdout_manager_benchmark'],[str(x) for x in h_bm],'evaluation comparison')
    for a in ['K','M']:
        for k,v in metrics(records_at(data,a,range(5,9),end),h_bm).items():t.eq(audit['holdout_statistics'][a][k],v,'held-out '+a+' '+k)
    full={a:product([1+x for x in records_at(data,a,range(1,9),end)]) for a in ['K','M','CX']}
    for a,v in full.items():t.eq(audit['final_restated_cohort_growth_factors'][a],v,'restated full history '+a)
    t.eq(audit['final_restated_full_cohort_return'],sum(full.values())/3-1,'restated initial cohort')
    t.eq(audit['final_restated_survivor_only_return'],(full['K']+full['M'])/2-1,'restated survivors')
    t.group('all entrants, closure capital and held-out evaluation')

    ss,cov,C=independent_claim_cov(data)
    for i in range(2):
        for j in range(2):
            t.eq(result['risk_model']['quarterly_sample'][i][j],ss[i][j],'independent sample cross product')
            t.eq(result['risk_model']['planning_factor_covariance'][i][j],cov[i][j],'prior blend')
    t.eq(result['risk_model']['planning_determinant'],F(436,3515625),'positive determinant')
    # Enumerate an independent finite joint law and recover the full 4x4 covariance.
    aa=sqrt(float(cov[0][0]));bb=float(cov[0][1])/aa;cc=sqrt(float(cov[1][1]-cov[0][1]**2/cov[0][0]))
    states=[]
    for u1,u2,um,up in itertools.product([-1,1],repeat=4):
        fe=aa*u1;fb=bb*u1+cc*u2;fm=.4*fe+.6*fb+.04*um;fp=140*fe+40*fb+20*up
        require(min(1.08+fe,1.03+fb,1.042+fm,320+fp)>0,'finite-law gross payoffs positive')
        states.append([fe,fb,fm,fp])
    for i in range(4):
        t.eq(sum(s[i] for s in states)/16,0.0,'finite-law centered mean')
        for j in range(4):t.eq(sum(s[i]*s[j] for s in states)/16,float(C[i][j]),'finite-law full claim covariance')
    # Exact Sylvester elimination supplies a second PSD check without approximate eigenvalues.
    work=[row[:] for row in C]
    for k in range(4):
        pivot=work[k][k];require(pivot>0,'full claim covariance positive pivots')
        for i in range(k+1,4):
            for j in range(k+1,4):work[i][j]-=work[i][k]*work[k][j]/pivot
    t.group('sample, prior and coherent full-claim risk')

    ranked,nominal,all_rows,rejects,C=independent_grid(data)
    opt=result['optimization'];t.eq(opt['candidate_count'],len(all_rows),'complete grid count')
    t.eq(opt['feasible_count'],len(ranked),'complete feasible count');t.eq(len(ranked),670,'canonical feasible set')
    t.eq(opt['nonexclusive_rejections'],rejects,'every nonexclusive violation count')
    for i,expected in enumerate(ranked):
        for k in opt['robust_ranked'][i]:t.eq(opt['robust_ranked'][i][k],expected[k],f'full independently ranked row {i} {k}')
    for label,expected in [('robust',ranked[0]),('nominal',nominal[0])]:
        for k,v in expected.items():
            if k!='stresses':t.eq(opt[label][k],v,label+' '+k)
            else:
                for name,led in v.items():
                    for a,b in led.items():t.eq(opt[label]['stresses'][name][a],b,label+' '+name+' '+a)
    p=data['portfolio'];benchpos=tuple(F(p['benchmark'][k]) for k in ['E','B','manager'])
    benchmark=all_rows[benchpos]
    for k,v in benchmark.items():
        if k!='stresses':t.eq(result['benchmark'][k],v,'benchmark '+k)
        else:
            for name,led in v.items():
                for a,b in led.items():t.eq(result['benchmark']['stresses'][name][a],b,'benchmark '+name+' '+a)
    t.group('global grid, all rankings, benchmark and design cash')

    imp=result['implementation'];target=ranked[0];targetpos=tuple(target[k] for k in ['E','B','manager'])
    actual=all_rows[(F(300),F(275),F(0))];naive=all_rows[(F(325),F(275),F(0))]
    permitted=[x for x in ranked if x['B']==275 and x['manager']==0 and 250<=x['E']<=325]
    t.eq([imp['authorized_fallback'][k] for k in ['E','B','manager']],[str(permitted[0][k]) for k in ['E','B','manager']],'best authorized continuation')
    t.eq(imp['unfilled_bond_sale'],F(25),'unfilled sale');t.eq(imp['unfilled_equity_buy'],F(25),'unfilled buy')
    for label,row in [('naive_complete_equity_order',naive),('authorized_fallback',actual)]:
        for k,v in row.items():
            if k!='stresses':t.eq(imp[label][k],v,label+' '+k)
            else:
                for name,led in v.items():
                    for a,b in led.items():t.eq(imp[label]['stresses'][name][a],b,label+' '+name+' '+a)
    G=[product([1+x for x in values]) for values in [h_e,h_b,records_at(data,'K',range(5,9),end)]]
    scenario={**p['realized_private'],'equity_return':G[0]-1,'bond_return':G[1]-1,'manager_return':G[2]-1}
    ledgers={}
    for name,pos in [('target',targetpos),('actual',(F(300),F(275),F(0))),('benchmark',benchpos),('nominal_counterfactual',tuple(nominal[0][k] for k in ['E','B','manager']))]:
        ledgers[name]=ledger(data,pos,scenario)
        for k,v in ledgers[name].items():t.eq(result['realized_report']['cash_ledgers'][name][k],v,'realized '+name+' '+k)
    rt,ra,rb=[ledgers[k]['terminal_reserve'] for k in ['target','actual','benchmark']]
    gap=result['realized_report']['reserve_gap_decomposition']
    t.eq(gap['policy_selection'],rt-rb,'target policy gap');t.eq(gap['implementation'],ra-rt,'implementation gap');t.eq(gap['total'],ra-rb,'total gap')
    opportunity=25*(G[0]-G[1]);fee_growth=(actual['fee']-target['fee'])*F(p['cash_half_year_factor'])**2
    t.eq(gap['target_minus_actual_opportunity_component'],opportunity,'both unfilled legs retained')
    t.eq(gap['fee_difference_at_terminal'],fee_growth,'fee savings carried to terminal')
    t.eq(gap['cash_principal_timing_adjustment'],F(0),'offset notionals')
    t.eq(gap['target_minus_actual_reserve'],opportunity+fee_growth,'self financing implementation identity')
    t.eq(gap['target_minus_actual_reserve'],rt-ra,'independent full-ledger identity')
    t.group('partial sale, authorized orders and realized attribution')

    s=p['outside_stress'];g=F(p['cash_half_year_factor']);mark=F(s['bond_t1_mark'])
    spread=F(s['bond_spread_per_original_unit']);fee=F(s['bond_fee_per_original_unit']);net=mark-spread-fee
    q=(F(s['call_t1'])+F(s['grant_t1'])+20-target['cash']*g)/net
    expected={'bond_net_price_per_original_unit':net,'required_original_units_for_buffer':q,'actual_original_units_sold':q,
              'gross_marked_value_removed':q*mark,'spread_cost':q*spread,'fee_cost':q*fee,'net_cash_raised':q*net,
              'forgone_bond_terminal_proceeds':q*(1+F(s['bond_return']))}
    for k,v in expected.items():t.eq(result['outside_design'][k],v,'forced sale '+k)
    forced=ledger(data,targetpos,s,q,net)
    for k,v in forced.items():t.eq(result['outside_design']['ledger'][k],v,'outside-design ledger '+k)
    t.eq(result['outside_design']['external_funding_at_terminal_to_restore_floor'],F(700)-forced['terminal_reserve'],'outside funding is not assumed')
    t.eq(str(q*net+q*spread+q*fee),q*mark,'marked-wealth conservation at sale')
    t.eq(result['outside_design']['ledger']['terminal_reserve'],F(84232137,153280),'independent reserve anchor')
    t.group('contingency rights, marked wealth and unresolved floor')

    def changed(edit):
        value=copy.deepcopy(data);edit(value);return model.run(value)
    def early(value):
        for row in value['research']['series_records']:
            if (row['asset'],row['period'],row['version'])==('M',4,2):row['released_on']='2025-01-02'
    revised=changed(early);t.eq(revised['research']['selected_manager'],'M','availability intervention')
    t.eq(revised['optimization'],result['optimization'],'research rank is not a silently re-estimated forward model')
    t.eq(revised['realized_report']['cash_ledgers']['nominal_counterfactual']['terminal_reserve'],F(7543884431,8000000),'selected M held-out cash')
    def future(value):
        for row in value['research']['series_records']:
            if row['asset']=='K' and row['period']==5:row['gross_return']=str(F(row['gross_return'])+F(1,10))
    altered=changed(future)
    t.eq(altered['research']['selected_manager'],'K','held-out selection independence')
    t.eq(altered['optimization'],result['optimization'],'held-out allocation independence')
    t.eq(altered['risk_model'],result['risk_model'],'held-out risk independence')
    t.eq(altered['realized_report']['cash_ledgers']['nominal_counterfactual']['terminal_reserve'],F(7545697583,8000000),'future return affects report only')
    single=changed(lambda d:d['portfolio']['forecast'].__setitem__('manager_overlay_upper','0'))
    t.eq(single['optimization']['robust'],single['optimization']['nominal'],'singleton ambiguity')
    full=changed(lambda d:d['portfolio']['execution'].__setitem__('available_bond_sale_units','100'))
    t.eq(full['implementation']['authorized_fallback'],full['optimization']['robust'],'full fill returns target')
    t.eq(full['realized_report']['reserve_gap_decomposition']['implementation'],F(0),'no implementation gap at full fill')
    for cap in [20,0]:
        altered=changed(lambda d:d['portfolio']['outside_stress'].__setitem__('bond_sale_capacity',str(cap)))
        ex=ledger(data,targetpos,s,F(cap),net)
        for k,v in ex.items():t.eq(altered['outside_design']['ledger'][k],v,'capacity '+str(cap)+' '+k)
        t.eq(altered['optimization'],result['optimization'],'outside capacity does not rewrite initial design')
    higher=copy.deepcopy(data);higher['portfolio']['policy']['gamma']='6'
    hres=model.run(higher);h_rank,h_nom,*_=independent_grid(higher)
    for name,row in [('robust',h_rank[0]),('nominal',h_nom[0])]:
        t.eq([hres['optimization'][name][k] for k in ['E','B','manager']],[str(row[k]) for k in ['E','B','manager']],'independent higher-gamma optimum')
    t.group('information, preference, fill and capacity interventions')

    def reject(edit,label):
        value=copy.deepcopy(data);edit(value)
        try:model.validate(value)
        except ValueError:t.rejections+=1
        else:raise AssertionError('accepted invalid domain: '+label)
    reject(lambda d:d['portfolio']['entry_cost_rates'].__setitem__('E',True),'boolean number')
    reject(lambda d:d['portfolio']['forecast'].__setitem__('equity_mean',.08),'floating number')
    reject(lambda d:d['portfolio']['forecast'].__setitem__('manager_residual_variance','0'),'zero residual')
    reject(lambda d:d['portfolio']['forecast']['prior_covariance'][1].__setitem__(0,'.003'),'asymmetry')
    reject(lambda d:d['portfolio']['forecast'].__setitem__('prior_covariance',[['.01','.02'],['.02','.01']]),'indefinite covariance')
    reject(lambda d:d['portfolio']['forecast'].__setitem__('sample_weight','.25'),'contradictory blend')
    reject(lambda d:d['portfolio']['forecast'].__setitem__('manager_equity_loading','.5'),'contradictory comparison loading')
    reject(lambda d:d.__setitem__('unexpected',0),'unknown field')
    reject(lambda d:d['research'].__setitem__('series_records',[r for r in d['research']['series_records'] if not(r['asset']=='CX' and r['period']==3)]),'missing last liquidation return')
    def shifted(value):
        for row in value['research']['series_records']:
            if row['period']==8:row['observation_end']='2026-01-02'
    reject(shifted,'uniform last boundary shift must not pass common-date test')
    reject(lambda d:d['research']['series_records'][0].__setitem__('observation_end','2024-03-30'),'mismatched interval')
    reject(lambda d:d['research'].__setitem__('training_periods',[1,2,4,3]),'changed sample split')
    reject(lambda d:d['research'].__setitem__('decision_cutoff','2025-01-04'),'contradictory decision date')
    reject(lambda d:d['research']['series_records'][0].__setitem__('released_on','2024-03-30'),'release before observation')
    reject(lambda d:d['research']['admitted_on'].__setitem__('N','2025-08-01'),'return predates admission')
    reject(lambda d:d['research']['series_records'].append(copy.deepcopy(d['research']['series_records'][0])),'duplicate version')
    def post_closure(value):
        row=copy.deepcopy(next(r for r in value['research']['series_records'] if r['asset']=='K' and r['period']==4))
        row['asset']='CX';value['research']['series_records'].append(row)
    reject(post_closure,'fund return after liquidation')
    reject(lambda d:d['research']['series_records'][0].__setitem__('gross_return','-1'),'zero net research wealth')
    reject(lambda d:d['portfolio']['entry_cost_rates'].__setitem__('E','1'),'invalid fee')
    reject(lambda d:d['portfolio'].__setitem__('borrowing','100'),'unsupported financing')
    reject(lambda d:d['portfolio'].__setitem__('lot','10'),'contradictory lot')
    reject(lambda d:d['portfolio']['caps'].__setitem__('E','10000'),'oversized exhaustive grid')
    reject(lambda d:d['portfolio']['policy'].__setitem__('terminal_floor','2000'),'infeasible own benchmark')
    reject(lambda d:d['portfolio'].__setitem__('cash_half_year_factor','.99'),'outside cash convention')
    reject(lambda d:d['portfolio']['outside_stress'].__setitem__('bond_spread_per_original_unit','1'),'nonpositive sale proceeds')
    reject(lambda d:d['portfolio']['execution'].__setitem__('available_bond_sale_units','24'),'fractional initial lot')
    reject(lambda d:d['portfolio']['forecast'].__setitem__('equity_mean','-.95'),'negative gross payoff in bounded witness')
    reject(lambda d:d['portfolio']['forecast'].__setitem__('private_distribution_mean','1'),'negative private payoff in bounded witness')
    reject(lambda d:d['portfolio']['forecast'].__setitem__('private_distribution_mean','0'),'zero mean positive-variance private claim')
    reject(lambda d:d['research']['closures']['CX'].__setitem__('announced_on','2024-01-01'),'premature liquidation announcement')
    reject(lambda d:d.__setitem__('provenance','real market data'),'false provenance')
    reject(lambda d:d['research'].__setitem__('search_log',['mean_net_active']),'concealed search')
    t.group('economic and information-domain rejections')

    manifest=load_json(ASSETS/(STEM+'manifest.json'))
    names=[STEM+suffix for suffix in ['inputs.json','analysis.py','output.json','README.txt']]
    t.eq([v['file'] for v in manifest['files']],names,'complete four-file manifest')
    for rec in manifest['files']:
        payload=(ASSETS/rec['file']).read_bytes()
        t.eq(rec['bytes'],len(payload),'manifest size '+rec['file'])
        t.eq(rec['sha256'],hashlib.sha256(payload).hexdigest(),'manifest hash '+rec['file'])
    with tempfile.TemporaryDirectory(prefix='tern-project-') as folder:
        base=Path(folder);bundle=base/'bundle';cwd=base/'elsewhere';bundle.mkdir();cwd.mkdir()
        for name in names:shutil.copy2(ASSETS/name,bundle/name)
        for flags in [[],['-O']]:
            cmd=[sys.executable,'-I','-B']+flags+[str(bundle/(STEM+'analysis.py'))]
            process=subprocess.run(cmd,cwd=cwd,capture_output=True,text=True,timeout=30)
            t.eq(process.returncode,0,'isolated CLI status '+str(flags));t.eq(process.stderr,'','isolated CLI stderr')
            t.eq(json.loads(process.stdout),preserved,'isolated complete output '+str(flags))
        out=cwd/'result.json'
        process=subprocess.run([sys.executable,'-I','-B',str(bundle/(STEM+'analysis.py')),'--input',str(bundle/(STEM+'inputs.json')),'--output',str(out)],cwd=cwd,capture_output=True,text=True,timeout=30)
        t.eq(process.returncode,0,'explicit input/output status');t.eq(process.stdout+process.stderr,'','explicit file output is quiet')
        t.eq(load_json(out),preserved,'complete file output')
    html=ProjectHTML();html.feed((ROOT/'content/assessments/parts/v09-project.html').read_text())
    t.eq(html.h1,0,'fragment has no duplicate title');t.eq(len(html.ids),len(set(html.ids)),'unique anchors')
    t.eq(html.solution_items,8,'eight ordered complete guide solutions')
    t.eq(html.points,[20,20,20,20,10,10],'100-point rubric and six domain weights')
    for n in range(1,7):require('v09-project-deliverable-'+str(n) in html.ids,'all substantive deliverable anchors')
    for name in names+[STEM+'manifest.json']:require(name in html.links,'flat published asset route')
    source_records=load_json(ROOT/'content/reviews/v09-project-sources.json')
    catalog=load_json(ROOT/'content/sources.json')
    if isinstance(catalog,dict):catalog=catalog['sources']
    existing={s['id']:s for s in catalog}
    for source in source_records:
        t.eq(source,existing[source['id']],'exact reused primary source '+source['id'])
        require('sources.html#'+source['id'] in html.links,'scoped source linked in narrative')
    t.group('portable normal and optimized execution, hashes, structure and sources')
    return {'project':'v09','case':'Tern Scholarship Pool','status':'passed','groups':len(t.groups),
            'comparisons':t.comparisons,'domain_rejections':t.rejections,
            'independent_grid_candidates':len(all_rows),'independent_feasible_rankings':len(ranked),
            'group_names':t.groups,'limits':'Exact synthetic-case verification and scoped input checks; no external human certification, empirical validation or UI QA.'}


if __name__=='__main__':
    print(json.dumps(check(),indent=2,allow_nan=False))
