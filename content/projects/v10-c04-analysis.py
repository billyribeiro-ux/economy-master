#!/usr/bin/env python3
"""Fenwick: finite credit contracts, recovery timing and conditional calibration."""
import argparse
from fractions import Fraction as F
import json
from math import exp, expm1, log, log1p, sqrt
from pathlib import Path

CONVENTIONS = {
 'unit':'CU','time':'years after 1 January 2027; date zero is before all payouts',
 'structural':'one nonrecourse zero-coupon debt; default is asset value strictly below face; no other claims or interim payout',
 'scheduled':'first default occurs at an interval end before that date coupon; recovery of par replaces all remaining rights; delayed comparison pays the same recovery only at final maturity',
 'continuous':'constant deterministic short rate and measure-labeled intensities; immediate recovery of par, maturity-paid recovery and recovery of pre-default market value are different contracts',
 'transition':'annual row-stochastic P and Q on A,B,D; D is absorbing; recovery paid once on first entry into D before any maturity principal',
 'joint':'two nonrecourse notes settle at one year; stipulated risk-neutral investors make physical and pricing probabilities equal in this separate example only',
 'liquidity':'a supplied nonreplicable frictional valuation wedge relative to a credit benchmark; not a second executable price for identical freely replicable cash flows'
}


def need(ok,message):
    if not ok:raise ValueError(message)


def number(value):
    need(type(value) in (int,str),'use integer or rational string, never a float or boolean')
    try:v=F(value)
    except (ValueError,ZeroDivisionError,OverflowError) as e:raise ValueError('invalid finite rational') from e
    need(abs(v)<=10**6 and v.denominator<=10**12,'finite case bounds exceeded')
    return v


def fields(obj,names):
    need(isinstance(obj,dict) and set(obj)==set(names.split()),'missing or unknown field')


def vector(values):
    need(isinstance(values,list) and 1<=len(values)<=12,'bounded nonempty vector required')
    return [number(v) for v in values]


def unit(value):
    v=number(value);need(0<=v<=1,'fraction outside [0,1]');return v


def discounts(values):
    vv=vector(values);need(all(0<x<=3 for x in vv),'positive bounded discount factors required');return vv


def probability(values,strict=False):
    vv=vector(values);need(sum(vv)==1 and all((0<x<=1 if strict else 0<=x<=1) for x in vv),'invalid probability vector');return vv


def survival(hazards):
    last=F(1);out=[]
    for h in hazards:
        marginal=last*h;current=last-marginal
        out.append({'opening_survival':last,'conditional_default':h,'marginal_default':marginal,'survival':current})
        last=current
    return out


def structural(data):
    f=number(data['face']);d=number(data['discount']);cost=number(data['workout_asset_fraction'])
    v=vector(data['asset_values']);p=vector(data['physical_probabilities']);q=vector(data['pricing_probabilities'])
    rows=[]
    for a,pp,qq in zip(v,p,q):
        default=a<f;workout=cost*a if default else F(0)
        debt=(a-workout) if default else f;equity=max(F(0),a-f)
        rows.append({'asset':a,'physical_probability':pp,'pricing_probability':qq,'state_price':d*qq,
                     'default':default,'workout_cost':workout,'debt_payoff':debt,'equity_payoff':equity,'claim_sum':debt+equity})
    debt=d*sum(r['pricing_probability']*r['debt_payoff'] for r in rows)
    eq=d*sum(r['pricing_probability']*r['equity_payoff'] for r in rows)
    asset=d*sum(qq*a for qq,a in zip(q,v));cpv=d*sum(r['pricing_probability']*r['workout_cost'] for r in rows)
    pdebt=sum(r['physical_probability']*r['debt_payoff'] for r in rows)
    return {'states':rows,'gross_asset_value':asset,'debt_price':debt,'equity_price':eq,'workout_cost_pv':cpv,
            'claim_value':debt+eq,'physical_default_probability':sum((r['physical_probability'] for r in rows if r['default']),F(0)),
            'pricing_default_probability':sum((r['pricing_probability'] for r in rows if r['default']),F(0)),
            'physical_expected_debt_receipt':pdebt,'physical_expected_face_loss':f-pdebt,
            'physical_expected_debt_return':None if debt==0 else pdebt/debt-1,
            'promised_simple_yield':None if debt==0 else f/debt-1,'safe_simple_return':1/d-1,
            'continuous_promised_spread_approx':None if debt==0 else -log(float(debt/(f*d)))}


def scheduled(data):
    f=number(data['face']);c=number(data['coupon_amount']);rec=number(data['recovery_fraction'])*f
    dd=discounts(data['discount_factors']);times=vector(data['times'])
    P=survival(vector(data['physical_hazards']));Q=survival(vector(data['pricing_hazards']))
    rows=[];previous=F(0)
    for i,(prob,d,time) in enumerate(zip(Q,dd,times)):
        coupon=c*prob['survival'];principal=f*prob['survival'] if i==len(dd)-1 else F(0)
        recovery=rec*prob['marginal_default']
        rows.append({**prob,'time':time,'discount_factor':d,'survival_coupon':coupon,'survival_principal':principal,
                     'recovery_at_interval_end':recovery,'present_value':d*(coupon+principal+recovery),
                     'equivalent_constant_intensity_on_interval_approx':-log1p(-float(prob['conditional_default']))/float(time-previous)})
        previous=time
    coupons=sum(d*c*prob['survival'] for d,prob in zip(dd,Q))
    delayed=coupons+dd[-1]*(f*Q[-1]['survival']+rec*(1-Q[-1]['survival']))
    return {'physical_survival':P,'pricing_cash_rows':rows,'price_end_date_recovery':sum(r['present_value'] for r in rows),
            'price_maturity_recovery':delayed,'default_free_promised_price':sum(dd)*c+dd[-1]*f,
            'recovery_timing_value':sum(r['present_value'] for r in rows)-delayed}


def continuous(data):
    f,T,r,lp,lq,R=[float(number(data[k])) for k in ['face','maturity','short_rate','physical_intensity','pricing_intensity','recovery_fraction']]
    k=r+lq;integral=T if k==0 else -expm1(-k*T)/k
    survival_p, survival_q=exp(-lp*T),exp(-lq*T)
    survival_pv=f*exp(-k*T);recovery_pv=f*R*lq*integral
    immediate=survival_pv+recovery_pv
    delayed=f*exp(-r*T)*(R+(1-R)*survival_q)
    rmv=f*exp(-(r+lq*(1-R))*T)
    return {'physical_survival_approx':survival_p,'pricing_survival_approx':survival_q,
            'survival_principal_pv_approx':survival_pv,'immediate_recovery_pv_approx':recovery_pv,
            'immediate_par_price_approx':immediate,'maturity_recovery_price_approx':delayed,
            'market_value_recovery_price_approx':rmv,'safe_zero_price_approx':f*exp(-r*T),
            'immediate_par_continuous_spread_approx':-log(immediate/f)/T-r,
            'maturity_recovery_continuous_spread_approx':-log(delayed/f)/T-r,
            'market_value_recovery_continuous_spread_approx':lq*(1-R),
            'scope':'Three different recovery contracts under the same supplied Q intensity; no diffusion or fitted physical model.'}


def migration_path(matrix,start,periods):
    dist=[F(int(i==start)) for i in range(3)];last=F(0);result=[]
    for t in range(1,periods+1):
        dist=[sum(dist[i]*matrix[i][j] for i in range(3)) for j in range(3)]
        marginal=dist[2]-last;surv=1-dist[2]
        result.append({'year':t,'distribution':dist[:],'cumulative_default':dist[2],'marginal_default':marginal,
                       'conditional_default':None if last==1 else marginal/(1-last),'survival':surv})
        last=dist[2]
    return result


def migration(data):
    dd=discounts(data['discount_factors']);f=number(data['face']);rec=f*number(data['recovery_fraction'])
    out={};start=data['states'].index(data['initial_state'])
    for name in ['physical','pricing']:
        matrix=[[number(v) for v in row] for row in data[name+'_matrix']]
        path=migration_path(matrix,start,len(dd));rows=[]
        for i,(d,prob) in enumerate(zip(dd,path)):
            recovery=rec*prob['marginal_default'];principal=f*prob['survival'] if i==len(dd)-1 else F(0)
            rows.append({**prob,'discount_factor':d,'first_default_recovery_cash':recovery,'principal_cash':principal,
                         'discounted_probability_weighted_cash':d*(recovery+principal)})
        out[name+'_rows']=rows
        out[name+'_weighted_discounted_cash']=sum(x['discounted_probability_weighted_cash'] for x in rows)
    out['price']=out['pricing_weighted_discounted_cash']
    out['scope']='P-weighted discounted cash is a comparison, not a no-arbitrage price. D is absorbing; default recovery is paid once.'
    return out


def joint(data):
    face=number(data['face_each']);R=number(data['recovery_fraction']);d=number(data['discount']);width=number(data['junior_width'])
    pa,pb=vector(data['marginal_defaults']);loss=face*(1-R);lower=max(F(0),pa+pb-1);upper=min(pa,pb);cases=[]
    denominator=pa*(1-pa)*pb*(1-pb)
    for entry in data['joint_default_cases']:
        j=number(entry['probability']);pp=[1-pa-pb+j,pa-j,pb-j,j];ll=[F(0),loss,loss,2*loss]
        rows=[]
        for label,pv,L in zip(['neither','A_only','B_only','both'],pp,ll):
            junior=min(L,width);senior=L-junior
            rows.append({'state':label,'probability':pv,'pool_loss':L,'junior_loss':junior,'senior_loss':senior,
                         'junior_receipt':width-junior,'senior_receipt':2*face-width-senior})
        mean=sum(r['probability']*r['pool_loss'] for r in rows)
        junior=sum(r['probability']*r['junior_loss'] for r in rows);senior=mean-junior
        cases.append({'name':entry['name'],'joint_probability':j,'rows':rows,
                      'default_covariance':j-pa*pb,'default_correlation_approx':None if denominator==0 else float(j-pa*pb)/sqrt(float(denominator)),
                      'expected_pool_loss':mean,'pool_loss_variance':sum(r['probability']*(r['pool_loss']-mean)**2 for r in rows),
                      'expected_junior_loss':junior,'expected_senior_loss':senior,
                      'junior_price':d*(width-junior),'senior_price':d*(2*face-width-senior),
                      'pool_price':d*(2*face-mean),'probability_loss_above_one_name_loss':sum((r['probability'] for r in rows if r['pool_loss']>loss),F(0))})
    return {'frechet_lower':lower,'frechet_upper':upper,'loss_given_each_default':loss,'cases':cases,
            'scope':'Q=P is explicitly stipulated here only; these are conditional loss and tranche-price comparisons.'}


def calibration(data):
    f=number(data['face']);T=number(data['maturity']);d=number(data['discount']);P=number(data['observed_price']);rows=[]
    for R in vector(data['recovery_fractions']):
        for k in vector(data['liquidity_price_multipliers']):
            ratio=P/(f*d*k)
            row={'recovery_fraction':R,'liquidity_price_multiplier':k,'credit_price_ratio':ratio,
                 'liquidity_yield_wedge_approx':-log(float(k))/float(T)}
            if R==1:
                row.update({'status':'unidentified' if ratio==1 else 'incompatible','default_probability':None,'intensity_approx':None,'repriced':None})
            else:
                pd=(1-ratio)/(1-R)
                if not 0<=pd<1:
                    row.update({'status':'outside finite-intensity model','default_probability':None,'intensity_approx':None,'repriced':None})
                else:
                    # Preserve tiny hazards with log1p; near certain default,
                    # convert exact positive survival before any float rounding.
                    log_survival=log1p(-float(pd)) if pd<=F(1,2) else log(float(1-pd))
                    row.update({'status':'compatible','default_probability':pd,'intensity_approx':-log_survival/float(T),
                                'repriced':f*d*k*(1-(1-R)*pd)})
            rows.append(row)
    return {'observed_continuous_spread_approx':-log(float(P/(f*d)))/float(T),'conditional_calibrations':rows,
            'scope':'One maturity-paid-recovery price identifies no unique hazard/recovery/liquidity triple or physical default law.'}


def validate(data):
    fields(data,'schema case provenance conventions structural scheduled continuous migration joint calibration')
    need(data['schema']=='v10-c04-credit-1' and data['case']=='Fenwick Credit Desk','fixture identity')
    need(data['provenance']=='Original synthetic teaching contracts and probabilities; no observed prices, estimated defaults or current legal claims.','synthetic provenance required')
    need(data['conventions']==CONVENTIONS,'explicit fixed contract contradicted')
    s=data['structural'];fields(s,'face discount asset_values physical_probabilities pricing_probabilities workout_asset_fraction')
    need(number(s['face'])>0 and 0<number(s['discount'])<=3,'positive face/discount')
    assets=vector(s['asset_values']);p=probability(s['physical_probabilities'],True);q=probability(s['pricing_probabilities'],True)
    need(len(assets)==len(p)==len(q) and all(a>=0 for a in assets) and max(assets)>0,'nonnegative asset states and matched support')
    unit(s['workout_asset_fraction'])
    s=data['scheduled'];fields(s,'face coupon_amount recovery_fraction times discount_factors physical_hazards pricing_hazards')
    need(number(s['face'])>0 and number(s['coupon_amount'])>=0,'positive face/nonnegative coupon');unit(s['recovery_fraction'])
    tt=vector(s['times']);dd=discounts(s['discount_factors']);ph=vector(s['physical_hazards']);qh=vector(s['pricing_hazards'])
    need(len(tt)==len(dd)==len(ph)==len(qh) and 0<tt[0] and tt[-1]<=50 and all(a<b for a,b in zip(tt,tt[1:])),'matched strictly dated schedule')
    need(all(0<=v<1 for v in ph+qh) and all((a==0)==(b==0) for a,b in zip(ph,qh)),'finite hazards and common P/Q support required')
    s=data['continuous'];fields(s,'face maturity short_rate physical_intensity pricing_intensity recovery_fraction')
    need(number(s['face'])>0 and 0<number(s['maturity'])<=50,'positive bounded maturity/face');unit(s['recovery_fraction'])
    need(-F(1,5)<=number(s['short_rate'])<=1,'bounded short rate, negative rates allowed')
    ph,qh=number(s['physical_intensity']),number(s['pricing_intensity'])
    need(0<=ph<=2 and 0<=qh<=2 and (ph==0)==(qh==0),'bounded nonnegative equivalent-measure intensities')
    s=data['migration'];fields(s,'face recovery_fraction states initial_state discount_factors physical_matrix pricing_matrix')
    need(number(s['face'])>0,'positive migration face');unit(s['recovery_fraction']);discounts(s['discount_factors'])
    need(s['states']==['A','B','D'] and s['initial_state'] in ['A','B'],'fixed state order and initially live claim')
    matrices=[]
    for key in ['physical_matrix','pricing_matrix']:
        a=s[key];need(isinstance(a,list) and len(a)==3,'three-state matrix')
        a=[probability(row) for row in a];need(all(len(row)==3 for row in a) and a[-1]==[0,0,1],'default absorbing')
        matrices.append(a)
    need(all((matrices[0][i][j]==0)==(matrices[1][i][j]==0) for i in range(3) for j in range(3)),'P/Q migration support mismatch')
    s=data['joint'];fields(s,'face_each recovery_fraction discount marginal_defaults joint_default_cases junior_width physical_equals_pricing')
    face=number(s['face_each']);need(face>0 and 0<number(s['discount'])<=3 and 0<number(s['junior_width'])<2*face,'positive tranche contract')
    unit(s['recovery_fraction']);pp=vector(s['marginal_defaults']);need(len(pp)==2 and all(0<=v<=1 for v in pp),'two marginal defaults')
    need(s['physical_equals_pricing'] is True,'this example stipulates Q=P explicitly')
    need(isinstance(s['joint_default_cases'],list) and 1<=len(s['joint_default_cases'])<=10,'bounded joint cases');names=set()
    for row in s['joint_default_cases']:
        fields(row,'name probability');need(isinstance(row['name'],str) and row['name'] and row['name'] not in names,'unique case names');names.add(row['name'])
        need(max(F(0),sum(pp)-1)<=number(row['probability'])<=min(pp),'inconsistent joint marginals')
    s=data['calibration'];fields(s,'face maturity discount observed_price recovery_fractions liquidity_price_multipliers recovery_timing')
    need(number(s['face'])>0 and 0<number(s['maturity'])<=50 and 0<number(s['discount'])<=3 and number(s['observed_price'])>0,'positive bounded calibration contract')
    need(s['recovery_timing']=='maturity','calibration formula requires maturity-paid recovery')
    need(all(0<=v<=1 for v in vector(s['recovery_fractions'])) and all(0<v<=1 for v in vector(s['liquidity_price_multipliers'])),'valid recovery/wedge grid')


def serial(value):
    if isinstance(value,F):return str(value)
    if isinstance(value,dict):return {k:serial(v) for k,v in value.items()}
    if isinstance(value,list):return [serial(v) for v in value]
    return value


def run(data):
    validate(data)
    return serial({'case':data['case'],'structural':structural(data['structural']),
                   'scheduled':scheduled(data['scheduled']),'continuous':continuous(data['continuous']),
                   'migration':migration(data['migration']),'joint':joint(data['joint']),
                   'calibration':calibration(data['calibration']),
                   'limits':'Supplied synthetic contracts and P/Q laws, not estimated defaults, guaranteed returns or legal advice.'})


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,default=Path(__file__).with_name('v10-c04-inputs.json'))
    parser.add_argument('--output',type=Path)
    args=parser.parse_args();out=run(json.loads(args.input.read_text()))
    text=json.dumps(out,indent=2,allow_nan=False)+'\n'
    if args.output:args.output.write_text(text)
    else:print(text,end='')


if __name__=='__main__':main()
