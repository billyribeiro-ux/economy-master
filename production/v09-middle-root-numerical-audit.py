"""Coordinator recomputations from inputs and algebra, independent of chapter programs."""
from fractions import Fraction as F
from itertools import product
from math import comb, sqrt, prod
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
COUNTS = {}
CHAPTER = None


def eq(actual, expected, label):
    COUNTS[CHAPTER] = COUNTS.get(CHAPTER, 0)+1
    if actual != expected:
        raise AssertionError(f"{CHAPTER}: {label}: {actual!r} != {expected!r}")


def near(actual, expected, label, tol=1e-10):
    eq(abs(float(actual)-float(expected)) <= tol, True, label)


def vector(v):
    return [F(x) for x in v]


def dot(a,b):
    return sum((x*y for x,y in zip(a,b)), F(0))


def mean(a):
    return sum(a,F(0))/len(a)


def centered(a):
    return [v-mean(a) for v in a]


def variance(a):
    return dot(centered(a),centered(a))/(len(a)-1)


def two_slopes(y,x,z):
    xc,zc,yc=map(centered,(x,z,y))
    a,b,c=dot(xc,xc),dot(xc,zc),dot(zc,zc)
    d,e=dot(xc,yc),dot(zc,yc)
    bx,bz=(c*d-b*e)/(a*c-b*b),(a*e-b*d)/(a*c-b*b)
    alpha=mean(y)-bx*mean(x)-bz*mean(z)
    return [alpha,bx,bz],[v-alpha-bx*u-bz*w for v,u,w in zip(y,x,z)]


def load(n):
    p=ROOT/'content/projects'
    return [json.loads((p/f'v09-c{n:02}-{suffix}.json').read_text()) for suffix in ('inputs','output')]


CHAPTER='v09-c06'
d,o=load(6)
rf=F(51,50)
for row,(u,v,e) in zip(o['pricing']['states'],product((-1,1),repeat=3)):
    m=(1-F(u,4)-F(v,5)-F(e,10))/rf
    f1,f2=F(3,100)+F(3*u,25),F(1,50)+F(v,10)
    a=rf+F(3,2)*f1-F(1,4)*f2
    b=a+F(1,250)+F(e,25)
    eq(F(row['sdf']),m,'positive kernel')
    eq(vector(row['factor_excess_payoffs']),[f1,f2],'factors')
    eq(F(row['replicated_gross_payoff']),a,'exact spanning')
    eq(F(row['priced_residual_gross_payoff']),b,'priced omitted risk')
    eq(a-F(3,2)*(rf+f1)+F(1,4)*(rf+f2)+F(27,100)*rf,F(51,2500),'clone arbitrage')
eq(mean([F(r['sdf'])*F(r['priced_residual_gross_payoff']) for r in o['pricing']['states']]),F(1),'residual claim price')
eq(mean([F(r['sdf'])*F(r['residual']) for r in o['pricing']['states']]),-F(1,250)/rf,'nonzero residual valuation')
for row in o['diversification']['rows']:
    n=row['assets']
    outcomes=[F(1,50)+F(1,5)*(F(2*k,n)-1) for k in range(n+1)]
    loss=F(sum(comb(n,k) for k,pay in enumerate(outcomes) if pay<0),2**n)
    eq(F(row['physical_probability_of_loss']),loss,'binomial loss mass')
    eq(F(row['average_residual_variance']),F(1,25*n),'finite residual variance')
    eq(F(row['product_sdf_cv_squared']),F(101,100)**n-1,'nonuniform product kernel')
    near(row['hypothetical_uniform_bound_on_mean'],.1/sqrt(n),'conditional uniform bound')
sample=d['empirical']['observations'];x=[F(r['factor_1']) for r in sample];z=[F(r['factor_2']) for r in sample];y=[F(r['asset_excess']) for r in sample]
coef,res=two_slopes(y,x,z)
eq(vector(o['empirical']['two_factor_ols']['coefficients']),coef,'independent centered two-by-two regression')
eq(coef,[F(1,500),F(5,4),-F(1,2)],'full coefficient anchors')
eq(dot(res,res),F(1,5000),'full SSE')
slope=dot(centered(x),centered(y))/dot(centered(x),centered(x));alpha=mean(y)-slope*mean(x)
eq(vector(o['empirical']['one_factor_ols']['coefficients']),[alpha,slope],'short regression')
eq([alpha,slope],[-F(3,1000),F(1)],'short anchors')
eq(F(o['empirical']['two_factor_ols']['r_squared_with_intercept']),1-dot(res,res)/dot(centered(y),centered(y)),'full R2')
# Exact cross-section inverse from its two-column Gram determinant, independent of lab solver.
B=[vector(row) for row in d['empirical']['cross_section_betas']];mu=vector(d['empirical']['cross_section_mean_excess'])
a,b,c=sum(r[0]**2 for r in B),sum(r[0]*r[1] for r in B),sum(r[1]**2 for r in B)
v,w=dot([r[0] for r in B],mu),dot([r[1] for r in B],mu)
lam=[(c*v-b*w)/(a*c-b*b),(a*w-b*v)/(a*c-b*b)]
eq(vector(o['empirical']['cross_section_no_free_intercept']['coefficients']),lam,'second pass')
eq(lam,[F(3,250),F(9,500)],'second-pass anchors')
values=[F(0)]*4;cash=F(100);gross=cost=F(0)
for n,(row,out) in enumerate(zip(d['construction']['observations'],o['construction']['periods'])):
    ranks=sorted(range(4),key=lambda j:F(row['signals'][j]));targets=[F(50) if j in ranks[-2:] else -F(50) for j in range(4)]
    vol=sum(abs(new-old) for new,old in zip(targets,values));pnl=dot(targets,vector(row['simple_returns']))
    values=[v*(1+r) for v,r in zip(targets,vector(row['simple_returns']))]
    closevol=sum(abs(v) for v in values) if n==3 else F(0)
    fee=(vol+closevol)/1000;cash+=pnl-fee-F(1,10);gross+=pnl;cost+=fee
    eq(F(out['rebalance_dollar_volume']),vol,'drift-aware volume')
    eq(F(out['gross_cash_profit']),pnl,'gross cash')
    eq(F(out['ending_equity']),cash,'net account equity')
eq([gross,cost,cash],[F(11),F(101,100),F(10959,100)],'full account')
# Every determinate exercise transfer is independently derived.
eq(F(5,4)*F(4,100)+F(1,2)*F(25,1000)+F(4,100),F(41,400),'exercise1 fair return')
eq(F(441,400)/F(103,100)-1,F(29,412),'exercise1 repriced return')
eq(F(3,100)*F(104,100),F(39,1250),'exercise1 sure payoff')
eq(F(3,100)*F(2,5)-F(2,1000),F(1,100),'exercise2 nontraded premium')
eq(F(1,5)*F(15,100)/10,F(3,1000),'exercise3 mean bound')
near(.2*sqrt(float(F(9,10000)+F(225,1000000))),.00670820393249937,'exercise3 common shock')
yc=[v+F(6,1000)+F(3,4)*f for v,f in zip(y,z)];cf,rr=two_slopes(yc,x,z)
eq(cf,[F(8,1000),F(5,4),F(1,4)],'exercise4 coefficients')
eq(1-dot(rr,rr)/dot(centered(yc),centered(yc)),F(125,129),'exercise4 R2')
for triple in [[-F(3,1000),F(1),F(0)],[F(7,1000),-F(1,2),F(1,2)]]:
    fit=[triple[0]+triple[1]*xx+triple[2]*(3*xx-F(2,100)) for xx in x]
    eq(sum((a-b)**2 for a,b in zip(y,fit)),F(1,1000),'exercise5 singular fitted set')
dl=[F(3,4250),F(1,4250)];newlam=[a+b for a,b in zip(lam,dl)];newmu=[mu[0]+F(1,250)]+mu[1:]
eq([a-dot(row,newlam) for a,row in zip(newmu,B)],[F(9,1700),F(3,1700),-F(1,340),-F(1,850)],'exercise6 new pricing errors')
eq(F(100)+5+6-F(2,1000)*(200+415+198)-F(2,10),F(54587,500),'exercise7 final cash')

CHAPTER='v09-c07'
d,o=load(7)
for regime in o['pricing']['regimes']:
    q=vector(regime['state_prices']);p=dot(q,[F(120),F(80)]);m=[2*x for x in q];r=[F(120)/p-1,F(80)/p-1]
    eq(F(regime['price']),p,'conditional price')
    eq(F(regime['expected_return']),mean(r),'conditional mean')
    eq(mean([m[i]*r[i] for i in range(2)]),F(0),'conditional excess valuation')
    eq(F(regime['SDF_return_covariance']),mean([(m[i]-1)*(r[i]-mean(r)) for i in range(2)]),'conditional covariance')
rules=d['selection']['rules'];selected=sorted(rules,key=lambda r:(-r['training'].count('+'),r['id']))[0]
eq(o['selection']['selected_before_holdout'],selected['id'],'training-only selector')
p=F(sum(comb(12,k) for k in range(10,13)),2**12)
eq(F(o['selection']['single_prespecified_rule_tail']),p,'exact sign probability')
eq(F(o['selection']['independent_family_tail']),1-(1-p)**20,'conditional family probability')
eq(F(o['selection']['bonferroni_bound']),20*p,'union bound')
eq(F(o['selection']['frozen_holdout_tail']),F(sum(comb(8,k) for k in range(4,9)),2**8),'holdout tail')
eq(F(o['selection']['frozen_holdout_net_profit']),F(2*selected['holdout'].count('+')-8)-F(8,10),'holdout cash')
event=o['event'];entry=F(109)+F(1,4)+1;exitcash=F(110)-F(1,4)
eq(F(event['entry_cash_including_information']),entry,'event entry')
eq(F(event['net_return_on_total_cash']),exitcash/entry-1,'event committed-cash return')
for key,beliefs in [('belief_equilibrium',[F(3,4),F(9,10)]),('correct_belief_counterfactual',[F(3,4)]*2)]:
    means=[60+80*p for p in beliefs];vars=[p*(1-p)*80**2 for p in beliefs];k=[vars[0]/100,vars[1]/288]
    price=(means[0]*k[1]+means[1]*k[0]-2*k[0]*k[1])/(k[0]+k[1]);h=[(u-price)/kk for u,kk in zip(means,k)]
    b=o['behavior'][key]
    eq(F(b['price']),price,'belief clearing price')
    eq(vector(b['holdings']),h,'subjective optimal holdings')
    eq(sum(h),F(2),'share clearing')
    cash=[500+price*(1-v) for v in h]
    eq(vector(b['cash_after_trade']),cash,'cash budgets')
    eq(sum(cash),F(1000),'cash clearing')
    eq([sum(F(row[i]) for row in b['terminal_wealth']) for i in range(2)],[F(1280),F(1120)],'terminal resource clearing')
    q=vector(b['one_supporting_state_price_vector']);eq(dot(q,[F(140),F(60)]),price,'positive no-arbitrage valuation')
eq(F(o['behavior']['price_difference_from_counterfactual']),F(888,7)-F(11040,97),'behavior counterfactual gap')
eq(F(o['information']['gross_value_of_information']),F(3,2),'value of information')
eq(F(o['information']['incremental_value_after_fee']),F(1,2),'net information')
f=o['funding'];entry=95+F(1,5)*105;topup=F(6,5)*(120-105)
eq(F(f['entry_capital_per_pair']),entry,'entry capital')
eq(F(f['stress_survival_capital_per_pair']),entry+topup,'stress capital')
eq(F(f['stress_topup_required']),topup,'margin call')
eq(F(f['divergence_final_wealth']),F(125)+80-95+105-120-2,'forced close cash')
eq(F(f['physical_expected_net_gain']),F(3,4)*8-F(1,4)*32,'expected constrained policy')
eq(F(104)/96-1,F(1,12),'exercise1 mean')
eq(F(7,20)*26+F(13,20)*14,F(91,5),'exercise2 hindsight claim price')
eq((F(110)-F(1,4))/(109+F(1,4)+1)-1,-F(2,441),'exercise3 event return')
p=F(sum(comb(8,k) for k in range(6,9)),2**8);eq(p,F(37,256),'exercise4 tail');near(1-(1-p)**20,.9559,'exercise4 family rounded',5e-5)
eq(4-F(8,5),F(12,5),'exercise4 net')
eq([int(F(250)//entry),int(F(250)//(entry+topup))],[2,1],'exercise7 funding sizes')
eq([250+2*8,250-2*32,250+8],[266,186,258],'exercise7 dated cash outcomes')
eq(F(4,5)*8-F(1,5)*32,F(0),'retention break-even probability')

CHAPTER='v09-c08'
d,o=load(8);m=d['monthly'];market,style,gross,rf,flows=[vector(m[k]) for k in ('market_excess','style_factor','fund_gross','risk_free','end_contributions')]
net=[v-F(1,500) for v in gross];benchmark=[r+x for r,x in zip(rf,market)];active=[v-b for v,b in zip(net,benchmark)]
eq(F(o['net_information_ratio']['mean']),mean(active),'net active mean')
eq(F(o['net_information_ratio']['sample_variance_n_minus_1']),variance(active),'active variance')
eq(variance(active),F(1,17500),'active variance anchor')
near(o['net_information_ratio']['ratio_approx'],float(mean(active))/sqrt(float(variance(active))),'IR')
for key,returns in [('gross_two_factor',gross),('net_two_factor',net)]:
    y=[v-r for v,r in zip(returns,rf)];coef,res=two_slopes(y,market,style)
    eq([F(o[key]['intercept'])]+vector(o[key]['loadings']),coef,'orthogonal-factor regression')
    eq(vector(o[key]['residuals']),res,'OLS residual')
    eq(F(o[key]['residual_sum_squares']),dot(res,res),'SSE')
    avar=dot(res,res)/5*(F(1,8)+mean(market)**2/dot(centered(market),centered(market))+mean(style)**2/dot(centered(style),centered(style)))
    eq(F(o[key]['classic_alpha_variance']),avar,'independent centered-intercept variance')
eq(F(o['net_two_factor']['classic_alpha_variance']),F(4401,2000000000),'intercept variance anchor')
eq(F(o['net_market_only']['intercept']),F(1,1000),'omitted style alpha')
for key,returns in [('fund_ledger',net),('matched_benchmark_ledger',benchmark)]:
    nav=F(1000)
    for i,(r,flow,out) in enumerate(zip(returns,flows,o[key]['rows'])):
        eq(F(out['beginning_nav']),nav,'dated beginning NAV');nav=nav*(1+r)+flow;eq(F(out['next_nav']),nav,'dated ending NAV')
    eq(F(o[key]['terminal_nav']),nav,'terminal NAV')
    eq(F(o[key]['time_weighted_return']),prod(1+r for r in returns)-1,'exact TWR')
    # Closed quadratic in G^4, independent of program bisection.
    z=(-500+sqrt(250000+4000*float(nav)))/2000;g=z**.25
    near(o[key]['monthly_money_weighted_return_approx'],g-1,'quadratic MWR root')
eq(F(o['matched_flow_terminal_wealth_difference']),F(o['fund_ledger']['terminal_nav'])-F(o['matched_benchmark_ledger']['terminal_nav']),'matched investor opportunity wealth')
effects=[];prs=[];brs=[]
for item,out in zip(d['attribution']['periods'],o['attribution']['periods']):
    w,W,r,b=[vector(item[k]) for k in ('portfolio_weights','benchmark_weights','portfolio_sector_returns','benchmark_sector_returns')];rp,rb=dot(w,r),dot(W,b)
    e=[sum((wi-Wi)*(bi-rb) for wi,Wi,bi in zip(w,W,b)),sum(Wi*(ri-bi) for Wi,ri,bi in zip(W,r,b)),sum((wi-Wi)*(ri-bi) for wi,Wi,ri,bi in zip(w,W,r,b))]
    eq([F(out[k]) for k in ('allocation','selection','interaction')],e,'sector decomposition');eq(sum(e),rp-rb,'attribution sum');effects.append(e);prs.append(rp);brs.append(rb)
linked=[effects[0][j]*(1+brs[1])+effects[1][j]*(1+prs[0]) for j in range(3)]
eq([F(o['attribution']['linked_effects'][k]) for k in ('allocation','selection','interaction')],linked,'linked effects')
eq(sum(linked),(1+prs[0])*(1+prs[1])-(1+brs[0])*(1+brs[1]),'compound gap')
funds=d['panel']['funds'];panel=o['fund_panel'];initial=[f for f in funds if f['entry_period']==1]
ranked=sorted(initial,key=lambda f:(-prod(1+F(r) for r in f['net_returns'][:2]),f['id']))
eq(panel['selected_ids'],[f['id'] for f in ranked[:2]],'prior cohort ranking')
outs={f['id']:prod(1+(F(r) if r is not None else 0) for r in f['net_returns'][2:])-1 for f in initial}
eq(F(panel['selected_outcome_return']),mean([outs[f['id']] for f in ranked[:2]]),'retain selected liquidation')
eq(F(panel['all_initial_cohort_outcome_return']),mean(list(outs.values())),'initial-cohort result')
annual=[mean([F(f['net_returns'][t]) for f in funds if f['net_returns'][t] is not None]) for t in range(4)]
filtered=[mean([F(f['net_returns'][t]) for f in funds if f['exit_period'] is None and f['net_returns'][t] is not None]) for t in range(4)]
eq(annual,[F(1,16),F(7,100),-F(1,20),F(0)],'complete opening universe')
eq(F(panel['all_available_equal_weight_compound_return']),prod(1+r for r in annual)-1,'all-available compound result')
eq(F(panel['hindsight_survivor_only_compound_return']),prod(1+r for r in filtered)-1,'hindsight filter')
# Independent exercise transfers and rounding anchors.
eq((200*F(14,100)+400*F(5,100)-2-2)/600,F(11,150),'exercise1 active dollar net')
eq(32+28+20-2-2-F(2,5),F(378,5),'exercise1 aggregate net profit')
a=vector(['-.01','0','.01','.02']);eq(variance(a),F(1,6000),'exercise2 tracking variance');eq(variance(a)*(12+2*11*F(1,4)),F(7,2400),'exercise2 serial risk')
near(.06/sqrt(float(F(7,2400))),1.11098412,'exercise2 serial-adjusted ratio',1e-8)
eq(mean(active)-F(1,1000),F(1,1000),'exercise3 increased fee active mean')
eq(dot(vector(['.6','.4']),vector(['.1','.02'])),F(17,250),'exercise4 equal weights return')
eq(F(209)*F(89,100),F(18601,100),'exercise5 beginning-fee NAV')
eq(F(1089,1000)*F(891,1000)-1,-F(29701,1000000),'exercise5 ending-fee TWR')
near((-1+sqrt(8.4404))/2-1,-.04738167,'exercise5 MWR',1e-8)
eq((F(9025,100)+80)/200-1,-F(119,800),'exercise6 repaired selected panel')
eq(F(17,16)*F(107,100)-1,F(219,1600),'exercise6 repaired all-available panel')
reversed_links=[effects[1][j]*(1+brs[0])+effects[0][j]*(1+prs[1]) for j in range(3)]
eq(reversed_links,vector(['.010325','.00592','.005135']),'exercise7 reversed components')
eq(sum(reversed_links),sum(linked),'exercise7 preserved gap')
eq(F(3,1000)-F(15,10000),F(15,10000),'exercise8 net alpha')
eq([F(15,10000)-F(196,100)*F(2,1000),F(15,10000)+F(196,100)*F(2,1000)],[-F(242,100000),F(542,100000)],'exercise8 nominal interval')

result={'date':'2026-10-08','status':'pass','method':'Independent coordinator exact-fraction and closed-form recomputation; chapter analysis modules are not imported. Full prose/proof/solution audit is recorded separately.','comparisons_by_chapter':COUNTS,'total_comparisons':sum(COUNTS.values())}
(ROOT/'production/v09-middle-root-numerical-audit.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
