"""Original finite governance decision lab; exact arithmetic, no external data.

run(data) is quiet and nonmutating. Rejected candidates contain signed funding
projections, never executed negative cash. Only the selected feasible policy has
an execution journal. Its dated contract ends after cutoff 3, with residual
deposits and assets explicitly retained. No legal authority is inferred.
"""
import argparse
from fractions import Fraction as F
from itertools import product
import json
from pathlib import Path
import re
import sys


def need(ok, message):
    if not ok:
        raise ValueError(message)


def keys(d, names, label):
    need(type(d) is dict and set(d) == set(names.split()), label + ': exact keys required')


def num(x, label, low=F(0), high=F(10000)):
    need(type(x) is str and re.fullmatch(r'-?\d{1,8}(?:\.\d{1,8})?', x) is not None,
         label + ': bounded decimal string required')
    q = F(x)
    need(low <= q <= high, label + ': outside domain')
    return q


def validate(d):
    keys(d, 'schema units institution choices terms limits scenarios incentives', 'input')
    need(type(d['schema']) is int and d['schema'] == 1, 'schema must be integer 1')
    need(type(d['units']) is str and 1 <= len(d['units']) <= 200, 'units required')
    z = d['institution']
    keys(z, 'cash security_units eligible_units loans deposits short_debt cluster_loans', 'institution')
    q = {k: num(v, k) for k, v in z.items()}
    need(q['loans'] > 0 and q['security_units'] > 0, 'positive loan and security books required')
    need(q['eligible_units'] <= q['security_units'] and q['cluster_loans'] <= q['loans'], 'inventory bound')
    need(q['cash']+q['security_units']+q['loans']-q['deposits']-q['short_debt'] >= 0, 'negative opening equity')
    keys(d['choices'], 'lending cash_equity term_replacement', 'choices')
    for k, values in d['choices'].items():
        need(type(values) is list and 1 <= len(values) <= 5, 'one to five choices required')
        vals = [num(v, k, high=F(100)) for v in values]
        need(len(set(vals)) == len(vals), 'duplicate numerical choice')
    need(max(map(F, d['choices']['term_replacement'])) <= q['short_debt'], 'cannot replace more old debt')
    keys(d['terms'], 'term_fee term_coupon roll_interest secured_interest equity_charge', 'terms')
    for k, v in d['terms'].items(): num(v, k, high=F(1))
    keys(d['limits'], 'cash_floor equity_floor concentration', 'limits')
    num(d['limits']['cash_floor'], 'cash floor'); num(d['limits']['equity_floor'], 'equity floor')
    num(d['limits']['concentration'], 'concentration', high=F(1))
    rows = d['scenarios']
    need(type(rows) is list and 1 <= len(rows) <= 6, 'one to six scenarios required')
    ids = []
    for s in rows:
        keys(s, 'id security_price haircut loan_loss_fixed loan_loss_per_new operating_loss rollover facility_open facility_ceiling principal_receipts interest_receipts withdrawal_fixed withdrawal_per_new', 'scenario')
        need(type(s['id']) is str and re.fullmatch(r'[a-z][a-z0-9_]{0,31}', s['id']) is not None, 'invalid scenario ID')
        ids.append(s['id'])
        num(s['security_price'], 'security price', low=F(1,10000), high=F(2))
        num(s['haircut'], 'haircut', high=F(9999,10000))
        for k in ('loan_loss_per_new', 'rollover'): num(s[k], k, high=F(1))
        for k in ('loan_loss_fixed', 'operating_loss', 'facility_ceiling'): num(s[k], k)
        need(type(s['facility_open']) is bool, 'facility_open must be boolean')
        for k in ('principal_receipts', 'interest_receipts', 'withdrawal_fixed', 'withdrawal_per_new'):
            need(type(s[k]) is list and len(s[k]) == 3, 'three dated values required')
            for v in s[k]: num(v, k, high=F(1) if k == 'withdrawal_per_new' else F(10000))
        for x in map(F, d['choices']['lending']):
            need(q['loans']+x-F(s['loan_loss_fixed'])-F(s['loan_loss_per_new'])*x >= sum(map(F,s['principal_receipts'])), 'principal receipts exceed surviving loans')
            need(sum(map(F,s['withdrawal_fixed']))+x*sum(map(F,s['withdrawal_per_new'])) <= q['deposits']+x, 'withdrawals exceed deposits')
        for b,t in product(map(F,d['choices']['cash_equity']),map(F,d['choices']['term_replacement'])):
            need(q['cash']+b-F(d['terms']['term_fee'])*t >= F(s['operating_loss']), 'opening operating loss cannot be paid')
    need(len(set(ids)) == len(ids), 'duplicate scenario ID')
    keys(d['incentives'], 'concealment_bonus funded_penalty common_audit_failure conditional_detection false_positive', 'incentives')
    for k,v in d['incentives'].items(): num(v,k,high=F(10000) if k in ('concealment_bonus','funded_penalty') else F(1))
    need(F(d['incentives']['concealment_bonus']) > 0, 'positive concealment bonus required')


def projection(d, policy, s):
    i = {k:F(v) for k,v in d['institution'].items()}
    z = {k:F(v) for k,v in d['terms'].items()}
    x,b,t = policy
    floor = F(d['limits']['cash_floor'])
    price,haircut = F(s['security_price']),F(s['haircut'])
    c0 = i['cash']+b-z['term_fee']*t
    equity0 = i['cash']+i['security_units']+i['loans']-i['deposits']-i['short_debt']+b-z['term_fee']*t
    loss = F(s['loan_loss_fixed'])+F(s['loan_loss_per_new'])*x
    op = F(s['operating_loss'])
    roll = (i['short_debt']-t)*F(s['rollover'])
    receipt = list(map(F,s['principal_receipts'])); interest = list(map(F,s['interest_receipts']))
    withdrawal = [F(a)+F(k)*x for a,k in zip(s['withdrawal_fixed'],s['withdrawal_per_new'])]
    capacity = min(i['eligible_units']*price*(1-haircut),F(s['facility_ceiling'])) if s['facility_open'] else F(0)
    pre = c0-op+receipt[0]+interest[0]+roll-(i['short_debt']-t)-withdrawal[0]-z['term_coupon']*t
    requested = max(F(0),floor-pre); draw = min(requested,capacity)
    cash = pre+draw; equity = equity0+i['security_units']*(price-1)-loss-op+interest[0]-z['term_coupon']*t
    loans = i['loans']+x-loss-receipt[0]; deposits = i['deposits']+x-withdrawal[0]
    snapshots = []
    def snapshot(date, roll_debt, secured, term):
        assets = cash+i['security_units']*price+loans
        liabilities = deposits+roll_debt+secured+term
        need(assets-liabilities == equity, 'projection accounting identity')
        snapshots.append({'cutoff':date,'cash_after_full_planned_payments':cash,'equity':equity,'loans':loans,'deposits':deposits,'rolled_debt':roll_debt,'secured_debt':secured,'term_debt':term,'assets':assets,'liabilities':liabilities,'cash_short_of_floor':max(F(0),floor-cash),'unfinanced_payment_shortfall':max(F(0),-cash)})
    snapshot(1,roll,draw,t)
    cash += receipt[1]+interest[1]-withdrawal[1]-(1+z['roll_interest'])*roll-(1+z['secured_interest'])*draw-z['term_coupon']*t
    equity += interest[1]-z['roll_interest']*roll-z['secured_interest']*draw-z['term_coupon']*t
    loans -= receipt[1]; deposits -= withdrawal[1]
    snapshot(2,F(0),F(0),t)
    cash += receipt[2]+interest[2]-withdrawal[2]-(1+z['term_coupon'])*t
    equity += interest[2]-z['term_coupon']*t
    loans -= receipt[2]; deposits -= withdrawal[2]
    snapshot(3,F(0),F(0),F(0))
    return {'scenario':s['id'],'cash_before_secured_draw':pre,'collateral_capacity':capacity,'requested_minimum_draw':requested,'secured_draw':draw,'pledged_units':draw/(price*(1-haircut)),'cutoffs':snapshots,'cash_limits_met':all(r['cash_after_full_planned_payments']>=floor for r in snapshots),'equity_limits_met':all(r['equity']>=F(d['limits']['equity_floor']) for r in snapshots)}


def execution(d, policy, s, projected):
    """Selected feasible plan only: actual dated account updates and rights."""
    i = {k:F(v) for k,v in d['institution'].items()}; z = {k:F(v) for k,v in d['terms'].items()}
    x,b,t = policy; price = F(s['security_price'])
    state = {'cash':i['cash'],'securities':i['security_units'],'loans':i['loans'],'deposits':i['deposits'],'old_short':i['short_debt'],'rolled':F(0),'secured':F(0),'term':F(0),'equity':i['cash']+i['security_units']+i['loans']-i['deposits']-i['short_debt']}
    rows = []; pledged = F(0)
    def post(date,event,changes):
        for k,v in changes.items(): state[k]+=v
        assets=sum(state[k] for k in ('cash','securities','loans'))
        debt=sum(state[k] for k in ('deposits','old_short','rolled','secured','term'))
        need(assets-debt==state['equity'],'execution accounting identity')
        need(all(v>=0 for k,v in state.items() if k!='equity'),'negative executed account')
        rows.append({'date':date,'event':event,'changes':dict(changes),'accounts':dict(state),'pledged_units':pledged})
    post(0,'initial inventory',{})
    post(0,'received cash equity',{'cash':b,'equity':b})
    post(0,'received growth deposits',{'cash':x,'deposits':x})
    post(0,'funded new loans',{'cash':-x,'loans':x})
    post(0,'received term funding',{'cash':t,'term':t})
    post(0,'repaid replaced old principal',{'cash':-t,'old_short':-t})
    post(0,'paid term origination fee',{'cash':-z['term_fee']*t,'equity':-z['term_fee']*t})
    loss=F(s['loan_loss_fixed'])+F(s['loan_loss_per_new'])*x
    post(1,'joint marks and credit writeoff',{'securities':i['security_units']*(price-1),'loans':-loss,'equity':i['security_units']*(price-1)-loss})
    op=F(s['operating_loss']);post(1,'paid operating incident',{'cash':-op,'equity':-op})
    roll=(i['short_debt']-t)*F(s['rollover']);draw=projected['secured_draw']
    for j in range(3):
        date=j+1;principal=F(s['principal_receipts'][j]);interest=F(s['interest_receipts'][j]);w=F(s['withdrawal_fixed'][j])+F(s['withdrawal_per_new'][j])*x
        post(date,'collected loan principal',{'cash':principal,'loans':-principal})
        post(date,'collected interest',{'cash':interest,'equity':interest})
        if j==0:
            post(date,'received contracted rollover',{'cash':roll,'rolled':roll})
            pledged=projected['pledged_units'];post(date,'received secured cash against separate eligible pool',{'cash':draw,'secured':draw})
            post(date,'repaid remaining old principal',{'cash':-(i['short_debt']-t),'old_short':-(i['short_debt']-t)})
        if j==1:
            post(date,'repaid rollover with interest',{'cash':-(1+z['roll_interest'])*roll,'rolled':-roll,'equity':-z['roll_interest']*roll})
            pledged=F(0);post(date,'repaid secured debt with interest and released pledge',{'cash':-(1+z['secured_interest'])*draw,'secured':-draw,'equity':-z['secured_interest']*draw})
        if j==2: post(date,'repaid term principal',{'cash':-t,'term':-t})
        post(date,'paid term coupon',{'cash':-z['term_coupon']*t,'equity':-z['term_coupon']*t})
        post(date,'paid deposit withdrawals',{'cash':-w,'deposits':-w})
        p=projected['cutoffs'][j]
        need(state['cash']==p['cash_after_full_planned_payments'] and state['equity']==p['equity'],'projection and execution disagree')
    return {'scenario':s['id'],'rows':rows,'remaining_deposits':state['deposits'],'remaining_loans':state['loans'],'remaining_securities':state['securities']}


def encode(x):
    if isinstance(x,F): return str(x)
    if isinstance(x,dict): return {k:encode(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)): return [encode(v) for v in x]
    return x


def run(data):
    validate(data)
    z={k:F(v) for k,v in data['terms'].items()};i={k:F(v) for k,v in data['institution'].items()}
    candidates=[]; feasible=[]
    choices=data['choices'];grid=sorted(product(*(map(F,choices[k]) for k in ('lending','cash_equity','term_replacement'))))
    for policy in grid:
        x,b,t=policy;concentration=(i['cluster_loans']+x)/(i['loans']+x)
        paths=[projection(data,policy,s) for s in data['scenarios']]
        cost=z['equity_charge']*b+(z['term_fee']+3*z['term_coupon'])*t
        reasons=[]
        if concentration>F(data['limits']['concentration']):reasons.append('concentration')
        for p in paths:
            if not p['cash_limits_met']:reasons.append(p['scenario']+':cash')
            if not p['equity_limits_met']:reasons.append(p['scenario']+':equity')
        row={'policy':dict(zip(('lending','cash_equity','term_replacement'),policy)),'concentration':concentration,'ranking_cost':cost,'feasible':not reasons,'failed_gates':reasons,'scenario_projections':paths}
        candidates.append(row)
        if not reasons:feasible.append(((-x,cost,b,t),policy,row))
    feasible.sort(key=lambda x:x[0])
    chosen=feasible[0] if feasible else None
    ins={k:F(v) for k,v in data['incentives'].items()};g=ins['concealment_bonus'];f=ins['funded_penalty'];p=(1-ins['common_audit_failure'])*ins['conditional_detection'];alpha=ins['false_positive']
    threshold=(g+alpha*f)/(g+f)
    out={'schema':1,'provenance':'Original synthetic contracts and board rule; no empirical probability or statutory threshold.','selection_rule':'Maximum lending, then lowest declared ranking cost, then lower equity and term choices to break exact ties.','projection_warning':'Rejected rows are signed full-payment funding projections. Only selected_execution is an executed nonnegative-cash journal.','candidate_count':len(candidates),'feasible_count':len(feasible),'candidates':candidates,'selected_policy':chosen[2]['policy'] if chosen else None,'selected_ranking_cost':chosen[2]['ranking_cost'] if chosen else None,'selected_execution':[execution(data,chosen[1],s,p) for s,p in zip(data['scenarios'],chosen[2]['scenario_projections'])] if chosen else [],'incentive':{'effective_detection':p,'truthful_expected_payoff':-alpha*f,'conceal_expected_payoff':(1-p)*g-p*f,'truthful_advantage':p*(g+f)-g-alpha*f,'weak_truthful_threshold':threshold,'truthful_weakly_preferred':p>=threshold,'truthful_strictly_preferred':p>threshold},'limits':'Finite three-cutoff contract, unchanged scenario set and fixed withdrawal behavior. Residual claims remain. Feasibility and integrity do not establish calibration, authority, authenticity or actual funding availability.'}
    return encode(out)


def strict_object(pairs):
    d={}
    for k,v in pairs:
        need(k not in d,'duplicate JSON key');d[k]=v
    return d


def output_guard(target, sources):
    for p in sources:
        need(target.resolve()!=p.resolve(),'output would overwrite a protected input/model')
        if target.exists():need(not target.samefile(p),'output aliases a protected input/model')


def main():
    here=Path(__file__).resolve();parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,default=here.with_name('v11-c12-inputs.json'))
    parser.add_argument('--output',type=Path,default=here.with_name('v11-c12-output.json'))
    args=parser.parse_args()
    try:
        output_guard(args.output,(args.input,here))
        need(args.input.stat().st_size<=65536,'input exceeds 65536 bytes')
        raw=args.input.read_text(encoding='utf-8')
        def bad_constant(value):raise ValueError('nonfinite JSON constant')
        data=json.loads(raw,object_pairs_hook=strict_object,parse_constant=bad_constant)
        result=run(data)
        args.output.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    except (ValueError,OSError,RecursionError) as e:parser.exit(2,str(e)+'\n')


if __name__=='__main__':main()
