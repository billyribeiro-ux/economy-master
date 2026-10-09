"""Coordinator's independent Volume10 assessment arithmetic; no author model imports."""
from fractions import Fraction as F
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
COUNT=0

def eq(actual,expected,label):
    global COUNT
    COUNT+=1
    if actual!=expected:raise RuntimeError((label,actual,expected))

def near(actual,expected,label,tol=3e-8):
    global COUNT
    COUNT+=1
    if not math.isclose(actual,expected,rel_tol=tol,abs_tol=tol):raise RuntimeError((label,actual,expected))

def integral(fn,lo,hi,n=12000):
    step=(hi-lo)/n
    return step/3*math.fsum([fn(lo),fn(hi)]+[fn(lo+j*step)*(4 if j%2 else 2) for j in range(1,n)])

def gaussian(z):return math.exp(-z*z/2)/math.sqrt(2*math.pi)


def project_anchors():
    dates=(F(1,2),F(1),F(3,2));discounts=tuple(map(F,('.98','.95','.91')))
    promises=(F(3),F(3),F(103))
    reserve=sum((d*c for d,c in zip(discounts,promises)),F(0))
    default_reserve=F(3)*discounts[0]+40*discounts[2]
    expected=F('.9')*reserve+F('.1')*default_reserve
    eq(reserve,F('99.52'),'dated riskless reserve')
    eq(default_reserve,F('39.34'),'default means no year1 coupon and delayed recovery')
    eq(expected,F('93.502'),'risky reserve expected-Q value')
    eq(reserve-expected,F('6.018'),'expected loss is not a riskfree financing gain')
    eq(reserve-default_reserve,3*discounts[1]+63*discounts[2],'statewise dated cash shortfalls')
    rate=-2*math.log(.98);spot=100;strike=105;vol=.25;maturity=.5
    mu=math.log(spot)+(rate-vol*vol/2)*maturity;width=vol*math.sqrt(maturity)
    cut=(math.log(strike)-mu)/width
    put=math.exp(-rate*maturity)*integral(lambda z:(strike-math.exp(mu+width*z))*gaussian(z),-12,cut)
    second=math.exp(-2*rate*maturity)*integral(lambda z:(strike-math.exp(mu+width*z))**2*gaussian(z),-12,cut)
    near(put,8.688302035,'payoff-integral vanilla anchor')
    near(float(reserve)+put,108.208302035,'frictionless combined quote')
    trees={}
    for n,want in [(4,8.917488863),(8,8.873221921),(16,8.790452645),(32,8.706023840)]:
        dt=maturity/n;jump=vol*math.sqrt(dt);rstep=math.exp(rate*dt)
        up=(rstep-math.exp(-jump))/(math.exp(jump)-math.exp(-jump))
        value=math.exp(-rate*maturity)*math.fsum(math.comb(n,j)*up**j*(1-up)**(n-j)*max(strike-spot*math.exp((2*j-n)*jump),0) for j in range(n+1))
        near(value,want,'direct terminal probability sum n'+str(n));trees[n]=value
    n=4;dt=maturity/n;jump=vol*math.sqrt(dt);R=math.exp(rate*dt)
    p=(R-math.exp(-jump))/(math.exp(jump)-math.exp(-jump))
    def feasible_values(time,balance):
        exercise=max(strike-spot*math.exp(balance*jump),0)
        if time==n:return [exercise]
        down=feasible_values(time+1,balance-1);up=feasible_values(time+1,balance+1)
        return [exercise]+[((1-p)*d+p*u)/R for d in down for u in up]
    policies=feasible_values(0,0)
    eq(len(policies),677,'all distinct full-history policy constructions n4')
    american=max(policies)
    near(american,9.300428763,'maximum over full-history stopping policies')
    eq(american>trees[4]>put,True,'separate exercise premium and observed discretization difference')
    return {'riskless_reserve':str(reserve),'risky_reserve':str(expected),'unit_put_integral':put,
            'unit_put_variance_integral':second-put*put,'direct_tree_expectations':trees,
            'full_history_policy_count':len(policies),'n4_early_exercise_price':american}


def solve(matrix,rhs):
    a=[list(map(F,row))+[F(v)] for row,v in zip(matrix,rhs)]
    n=len(a)
    for j in range(n):
        pivot=next(i for i in range(j,n) if a[i][j])
        a[j],a[pivot]=a[pivot],a[j]
        scale=a[j][j];a[j]=[x/scale for x in a[j]]
        for i in range(n):
            if i!=j:
                factor=a[i][j];a[i]=[x-factor*y for x,y in zip(a[i],a[j])]
    return [row[-1] for row in a]


def project_output_check():
    data=json.loads((ROOT/'content/projects/v10-assessment-inputs.json').read_text())
    output=json.loads((ROOT/'content/projects/v10-assessment-output.json').read_text())
    t=list(map(F,data['curve']['times']))
    instruments=data['curve']['instruments']
    d=solve([row['cash'] for row in instruments],[row['price'] for row in instruments])
    bond=output['bond'];eq(list(map(F,bond['discounts'])),d,'full rational system reconstructs discounts')
    cash=list(map(F,data['liability']['coupons']));cash[-1]+=F(data['liability']['face'])
    value=sum(c*x for c,x in zip(cash,d))
    eq(F(bond['pv']),value,'independent promised cash sum')
    quantities=list(map(F,bond['barbell_zero_quantities']))
    eq(sum(a*x for a,x in zip(quantities,d)),value,'barbell value constraint')
    eq(sum(a*x*time for a,x,time in zip(quantities,d,t)),sum(c*x*time for c,x,time in zip(cash,d,t)),'barbell moment constraint')
    for shock,given in zip(data['curve']['shocks'],bond['shocks']):
        dz=list(map(F,shock['zero_shifts']))
        residual=math.fsum(float((a-c)*x)*math.exp(-float(time*z)) for a,c,x,time,z in zip(quantities,cash,d,t,dz))
        near(given['barbell_minus_liability'],residual,'direct net-cash repricing '+shock['id'])
        near(given['first_order_residual'],float(sum(-(a-c)*x*time*z for a,c,x,time,z in zip(quantities,cash,d,t,dz))),'net-cash first derivative '+shock['id'])
    o=data['option'];s,k,sigma=[float(F(o[key])) for key in ('spot','strike','sigma')]
    tau=float(t[0]);r=-math.log(float(d[0]))/tau
    def values(spot,life):
        m=(r-.5*sigma*sigma)*life;w=sigma*math.sqrt(life)
        edge=(math.log(k/spot)-m)/w;discount=math.exp(-r*life)
        price=discount*integral(lambda z:(k-spot*math.exp(m+w*z))*gaussian(z),-12,edge)
        delta=-discount*integral(lambda z:math.exp(m+w*z)*gaussian(z),-12,edge)
        return price,delta
    price,delta=values(s,tau)
    base=output['option']['analytic']
    near(base['put'],price,'saved value vs Gaussian payoff integral')
    near(base['put_delta'],delta,'saved delta vs differentiated payoff integral')
    bump=.05
    gamma=(values(s+bump,tau)[1]-values(s-bump,tau)[1])/(2*bump)
    near(base['gamma'],gamma,'delta-integral slope gamma',2e-7)
    near(base['call']-base['put'],s-k*float(d[0]),'put-call cash parity')
    near(output['option']['quadrature']['fine'],price,'separate high-resolution quadrature',4e-8)
    worst=math.inf
    for path,given in zip(data['hedge']['paths'],output['hedge']['paths']):
        ht=list(map(lambda x:float(F(x)),data['hedge']['times']));levels=list(map(lambda x:float(F(x)),path['spots']))
        holdings=[values(spot,tau-date)[1] for spot,date in zip(levels[:-1],ht[:-1])]+[0.0]
        bank=price;previous_stock=0.0;previous_time=0.0;cost_pv=0.0
        for date,spot,shares,row in zip(ht,levels,holdings,given['with_costs']['ledger']):
            bank*=math.exp(r*(date-previous_time))
            near(row['bank_before_trade'],bank,'funded incoming cash '+path['id'],4e-7)
            trade=(shares-previous_stock)*spot;fee=float(F(data['hedge']['cost_rate']))*abs(trade)
            bank-=trade+fee;cost_pv+=fee*math.exp(-r*date)
            near(row['stock_after'],shares,'payoff-integral hedge holding '+path['id'],4e-7)
            near(row['bank_after_trade'],bank,'funded cash conservation '+path['id'],4e-7)
            previous_stock,previous_time=shares,date
        error=bank-max(k-levels[-1],0)
        near(given['with_costs']['terminal_error'],error,'terminal funded writer outcome '+path['id'],4e-7)
        near(given['frictionless']['terminal_error']-error,cost_pv*math.exp(r*tau),'separate accumulated fee account '+path['id'],4e-7)
        worst=min(worst,error)
    credit=output['credit_reserve'];defaults=list(map(F,credit['default_cash']))
    cum=F(0)
    for time,disc,paid,received,row in zip(t,d,cash,defaults,credit['default_funding_ledger']):
        eq(F(row['bank_before_payment']),cum/disc,'discounted cumulative prior shortfall')
        cum+=(received-paid)*disc
        eq(F(row['bank_after_payment']),cum/disc,'discounted cumulative dated funding')
    eq(F(credit['default_terminal_bank'])*d[-1],-F(credit['default_initial_gap']),'funding gap terminal/PV identity')
    extra=max(0,-worst-float(F(data['decision']['max_tested_terminal_loss'])))*float(d[0])
    near(output['decision']['additional_initial_cash_for_tested_loss_budget'],extra,'tested-path reserve discounted to date0',4e-7)
    near(output['decision']['quote_with_tested_buffer'],float(value)+price+extra,'cash-matched reserve plus funded option buffer',4e-7)
    for key in ('plain','antithetic','controlled'):
        item=output['option']['monte_carlo'][key]
        near(item['estimated_se']**2,item['sample_variance']/item['units'],'reported independent-unit variance '+key)
        near(item['estimate_minus_analytic'],item['mean']-price,'sample error uses matching European target '+key)
    eq(output['decision']['failed_gates'],['reserve_funds_all_declared_dates','quote_covers_tested_loss_budget'],'canonical gate decisions')
    return {'status':'passed','worst_tested_funded_hedge_error':worst,'initial_tested_buffer':extra,
            'scope':'All final saved hedge/credit rows, exact cash/curve constraints, option quadrature/delta/gamma and baseline decision arithmetic; focused selected-reserve validation is recorded separately.'}


def project_transfer_calculations():
    # Reconstruct the six fresh instructor transfers without importing the toolkit.
    discounts=tuple(map(F,('.98','.95','.91')))
    shift=F('.02')/102
    eq(shift,F(1,5100),'project transfer1 last discount quote propagation')
    eq(103*shift,F(103,5100),'project transfer1 fixed cash value change')
    eq((F('.9')*103+F('.1')*40)*shift,F(967,51000),'project transfer1 risky cash value change')
    r=-2*math.log(.98);sigma=.25;T=.5;k=105
    def put_delta(spot,life):
        m=(r-sigma*sigma/2)*life;w=sigma*math.sqrt(life)
        edge=(math.log(k/spot)-m)/w;disc=math.exp(-r*life)
        price=disc*integral(lambda z:(k-spot*math.exp(m+w*z))*gaussian(z),-12,edge)
        delta=-disc*integral(lambda z:math.exp(m+w*z)*gaussian(z),-12,edge)
        return price,delta
    premium=put_delta(100,T)[0]
    def gain_error(times,spots,fee):
        deltas=[put_delta(s,T-t)[1] for t,s in zip(times[:-1],spots[:-1])]+[0.]
        discounted=[math.exp(-r*t)*s for t,s in zip(times,spots)]
        gains=math.fsum(delta*(following-current) for delta,current,following in zip(deltas,discounted,discounted[1:]))
        cost=math.fsum(fee*abs(new-old)*ds for new,old,ds in zip(deltas,[0.]+deltas[:-1],discounted))
        return (premium+gains-cost-.98*max(k-spots[-1],0))/.98
    dates=(0,.125,.25,.375,.5);calm=(100,100,100,100,90);round_trip=(100,85,95,110,90)
    near(gain_error(dates,calm,0),1.806685410882,'project transfer2 calm-history costless error')
    near(gain_error(dates,calm,.001),1.677445349078,'project transfer2 calm-history funded error')
    near(gain_error((0,.5),(100,90),0),.237938687906,'project transfer2 endpoint-only costless error')
    near(gain_error((0,.5),(100,90),.001),.136305514536,'project transfer2 endpoint-only funded error')
    immediate=3*discounts[0]+40*discounts[1]
    eq(immediate,F('40.94'),'project transfer3 actual recovery cash date')
    eq(F('.9')*F('99.52')+F('.1')*immediate,F('93.662'),'project transfer3 changed asset PV')
    eq(37*discounts[1]/discounts[2]-103,F(-5858,91),'project transfer3 account accumulates received recovery')
    near(3*float(discounts[1]/discounts[2])*math.expm1(.02*.5),.031475798011,'project transfer3 additional bridge spread')
    full_face_loss=3*discounts[1]+3*discounts[2]
    eq(full_face_loss,F('5.58'),'project transfer4 full face still omits coupons')
    eq(-full_face_loss/discounts[2],F(-558,91),'project transfer4 unfunded coupons at final date')
    eq((F('6.018')-F('60.18'))/discounts[2],F(-27081,455),'project transfer4 expected saving cannot fund default state')
    m=(r-sigma*sigma/2)*T;w=sigma*math.sqrt(T);edge=(math.log(k/100)-m)/w
    payoff=lambda z:.98*(k-100*math.exp(m+w*z))
    var_y=integral(lambda z:payoff(z)**2*gaussian(z),-12,edge)-premium**2
    cov=integral(lambda z:payoff(z)*(.98*100*math.exp(m+w*z))*gaussian(z),-12,edge)-premium*100
    var_x=10000*math.expm1(sigma*sigma*T)
    near(var_y+var_x-2*cov,737.405478428,'project transfer5 wrong-sign control variance')
    eq(var_y+var_x-2*cov>var_y,True,'project transfer5 unbiased control can increase variance')
    base=gain_error(dates,round_trip,.001);double=gain_error(dates,round_trip,.002)
    near(base-double,.175202993740,'project transfer6 additional financed trading costs')
    near(double,-12.130884682906,'project transfer6 double-cost error')
    buffer=.98*(-base-1);threshold=99.52+premium+buffer
    near(119-threshold,.055129909600,'project transfer6 limited quote slack')
    # Remainder bounds are analytic; these four cases check the stated application.
    net_pv=tuple(map(F,('1.425','-2.85','1.425')));times=tuple(map(F,('.5','1','1.5')))
    for shock in ((.01,.01,.01),(-.01,-.01,-.01),(-.01,0,.01),(0,.01,0)):
        exact=math.fsum(float(a)*math.exp(-float(t)*z) for a,t,z in zip(net_pv,times,shock))
        approx=math.fsum(float(a)*(-float(t)*z+(float(t)*z)**2/2) for a,t,z in zip(net_pv,times,shock))
        bound=math.fsum(abs(float(a))*math.exp(abs(float(t)*z))*abs(float(t)*z)**3/6 for a,t,z in zip(net_pv,times,shock))
        eq(abs(exact-approx)<=bound+1e-14,True,'project guide exponential remainder for declared shock')
    return {'transfers':6,'status':'passed','guide_read':'All eight instructor sections, six transfers, five-domain rubric and full standalone README reviewed.'}


def examination_calculations():
    # FormA: solve original instrument system rather than call the form checker.
    discounts=solve([[100,0,0],[4,104,0],[5,5,105]],[98,F('100.744'),F('101.955')])
    eq(discounts,list(map(F,('.98','.931','.88'))),'A1 instrument system')
    eq(F('101.955')-F('2.5'),F('99.455'),'A1 clean settlement quote')
    hedge=solve([[discounts[0],discounts[2]],[discounts[0]/2,discounts[2]*F(5,2)]],[F('93.1'),F('139.65')])
    eq(hedge,[F('47.5'),F(4655,88)],'A1 exact value/moment hedge')
    near(F('93.1')*F('1.5')*F('.01'),1.3965,'A1 first order middle shift')
    near(93.1*(-math.expm1(-.015)),1.386078423,'A1 exact middle shift')
    rates=(F(1,99),F(9,91));eq(sum(rates)/2,F(491,9009),'A1 Q rate mean')
    ep=(3*rates[0]+rates[1])/4;eq(ep,F(97,3003),'A1 physical rate mean')
    near(float(F(1,19)-ep),.020330547,'A1 averaging/measure decomposition')
    bi=100*math.exp(-.2)+integral(lambda time:50*.06*math.exp(-.1*time),0,2,400)
    bm=math.exp(-.08)*(100*math.exp(-.12)+50*(-math.expm1(-.12)))
    near(bi,87.311152715,'A2 date-of-default integration');near(bm,87.092354973,'A2 terminal recovery')
    near(bi-bm,.218797742,'A2 recovery timing difference')
    near(-math.expm1(-.12),.113079563,'A2 cumulative pricing default')
    eq(F('.1')/F('1.86'),F(5,93),'A2 swap par coupon')
    cash=[100*(1/F('.96')-1-F('.05')),100*(F('.96')/F('.90')-1-F('.05'))]
    eq([x*d for x,d in zip(cash,map(F,('.96','.9')))],list(map(F,('-.8','1.5'))),'A2 discounted net swap coupons')
    collateral=12*F('1.01');debt=12*F('1.06')-(collateral-8)
    eq(debt,F('8.6'),'A2 release immediately repays debt')
    eq(8*F('1.01')-debt*F('1.06'),F('-1.036'),'A2 terminal collateral financing')
    up=F(5,8);R=F(21,20);end=[0,14,46]
    q_up=((1-up)*14)/R;q_down=(up*14+(1-up)*46)/R
    euro=(up*q_up+(1-up)*q_down)/R
    candidates=[F(10)]+[(up*u+(1-up)*d)/R for u in (F(0),q_up) for d in (F(30),q_down)]
    american=max(candidates)
    eq((q_up,q_down),(F(5),F(520,21)),'A3 continuation values')
    eq((american,euro,american-euro),(F(575,42),F(3475,294),F(275,147)),'A3 adapted optimal policy enumeration')
    delta,bank=solve([[120,R],[80,R]],[5,30])
    eq((delta,bank),(F(-5,8),F(1600,21)),'A3 root funded replica')
    next_delta,next_bank=solve([[144,R],[96,R]],[0,14])
    eq((next_delta-delta)*120,F(40),'A3 actual stock trade')
    eq(bank*R-F(40),next_bank,'A3 rebalance uses actual incoming bank')
    eq(bank*R+delta*80,30,'A3 down-node immediate settlement')
    positions=solve([[F('.030'),F('.025')],[30,50]],[4,5000])
    eq(positions,[F(100),F(40)],'A4 restored Greek rank')
    eq(-(-70+positions[0]*F('.5')+positions[1]*F('.4')+10),F(-6),'A4 additional shares with existing holdings')
    w=list(map(F,('.2','.65','.1')));eq(sum(w),F('.95'),'A4 positive stencil mass')
    eq((F('.15')*4-F('-.05')*2,1-2*F('.15')*4-F('.05'),F('.15')*4+F('-.05')*2),(F('.7'),F('-.25'),F('.5')),'A4 spatial refinement weights')
    bound=F('.04')
    for _ in range(20):bound=max(F('.01'),F('.95')*bound+F('.001'))
    near(float(bound),.027169718448,'A4 exact global error recursion')
    eq(F(16)-F(6)**2/F(9),F(12),'A4 residual control variance')
    near(1.96*math.sqrt(12/400),.339481958,'A4 controlled mean halfwidth')
    stock=(70,100,160);claim=(0,10,10)
    for a in (F(0),F(1,6),F(1,3),F(2,3)):
        law=(a,1-3*a/2,a/2)
        eq(sum(law),1,'A5 calibrated normalization')
        eq(sum(x*p for x,p in zip(stock,law)),100,'A5 stock moment')
        eq(F('.95')*sum(x*p for x,p in zip(claim,law)),F('9.5')*(1-a),'A5 capped price family')
    eq([c-F(x-70,9) for c,x in zip(claim,stock)],[F(0),F(20,3),F(0)],'A5 lower endpoint witness')
    eq([10-c for c in claim],[10,0,0],'A5 upper endpoint witness')
    eq(F(160**2-100**2,100)-2*(160-100),F(36),'A5 finite jump residual')
    eq(60//F('4.5'),13,'A5 maximum permitted whole short quantity')
    eq(20*F('4.5'),90,'A5 model uncertainty gate')

    # FormB: different cash/time/information mechanisms, not a number substitution.
    disc=solve([[100,0],[50,52]],[99,F('102.0096')]);eq(disc,list(map(F,('.99','1.0098'))),'B1 negative-forward curve')
    eq(disc[0]/disc[1]-1,F(-1,51),'B1 effective forward')
    positions=solve([[50,100],[52,0]],[40,60]);eq(positions,[F(15,13),F(-23,130)],'B1 exact amortizer cash replication')
    eq(sum(c*d for c,d in zip((40,60),disc)),F('100.188'),'B1 liability value')
    eq((F('.99')*F('.06')/2,F('.99')*F('.02')),(F('.0297'),F('.0198')),'B1 same-curve option difference')
    eq(F('.99')*(3*F('1.06')+F('.98'))/4,F('1.0296'),'B1 physical weights fail pricing calibration')
    first=F('.2');second=F('.1')*F('.05')+F('.7')*F('.2');survival=1-first-second
    eq((first,second,survival),(F('.2'),F('.145'),F('.655')),'B2 first-default rather than absorbing stock')
    delayed=F('.92')*(100*survival+40*first)+F('.88')*40*second
    immediate=F('.96')*40*first+F('.92')*(100*survival+40*second)
    eq((delayed,immediate,immediate-delayed),(F('72.724'),F('73.276'),F('.552')),'B2 recovery settlement dates')
    variation=[-10*(b-a) for a,b in zip((50,56,47),(56,47,52))]
    eq(variation,[-60,90,-50],'B2 futures sign and multiplier')
    eq(100+60+sum(variation),140,'B2 returned margin principal and losses')
    eq(60-55,5,'B2 date1 cash gap despite later receivable')
    debt=100*F('1.005')*F('1.01')*F('1.015')+60*F('1.01')*F('1.015')
    eq(debt,F('164.536575'),'B2 contributions funded on actual dates');eq(140-debt,F('-24.536575'),'B2 funded net result')
    replica=solve([[64,F('1.02')],[96,F('1.02')]],[0,10])
    eq(replica,[F(5,16),F(-1000,51)],'B3 digital shares and initial bank')
    eq(replica[0]*80+replica[1],F(275,51),'B3 digital price')
    eq(F('.04')-F('.06'),F('-.02'),'B3 inverse-stock Ito drift')
    eq(-2*F('.03')+F('.01')+F('.04'),F('-.01'),'B3 discounted inverse-moment exponent')
    near(100*math.exp(-.01),99.004983375,'B3 reciprocal claim price')
    eq(F('.01')-F('.02')+F('.04')-F('.03'),F(0),'B3 inverse payoff PDE')
    eq(-2*F('.02')+3*F('.04'),F('.08'),'B3 square-integrability negative moment exponent')
    premium=F('7.364289723');delta=F('-.436000430455');nextdelta=F('-.216606525638')
    R=F('1.010050167084');G=F('1.005012520859')
    bank=(premium-delta*100)*R;shares=delta*G;wealth=shares*110+bank
    trade=(nextdelta-shares)*110;fee=abs(trade)*F('.001');costlessbank=bank-trade
    ideal=costlessbank*R+nextdelta*G*90-10;paid=ideal-fee*R
    near(float(wealth),3.276084740,'B4 incoming dividend-adjusted wealth')
    near(float(trade),24.373730268,'B4 buyback actual trade cash')
    near(float(ideal),-2.217114078,'B4 funded discrete ideal error')
    near(float(paid),-2.241732769,'B4 funded discrete fee error')
    near(float(F('2.067544281')-wealth),-1.208540459,'B4 external withdrawal from forced mark reset')
    lower=F('8.1')-F('1.96')*F(4,20)-F('.008');upper=F('8.1')+F('1.96')*F(4,20)+F('.008')
    eq((lower,upper),(F('7.7'),F('8.5')),'B4 separate sampling/numerical price interval')
    eq((F('.3')+(8-upper)/20,F('.3')+(8-lower)/20),(F('.275'),F('.315')),'B4 asymmetric inverse Lipschitz range')
    call=(0,0,0,20);asian=(0,0,10,20);terminal=(80,100,100,120)
    for b in (F(0),F('.2'),F('.4'),F('.8')):
        law=(F('.1'),b,F('.8')-b,F('.1'))
        eq(sum(law),1,'B5 calibrated bank')
        eq(sum(x*p for x,p in zip(terminal,law)),100,'B5 calibrated stock')
        eq(sum(x*p for x,p in zip(call,law)),2,'B5 calibrated extra vanilla')
        eq(sum(x*p for x,p in zip(asian,law)),10-10*b,'B5 unspanned fixing price')
    eq([x-c for x,c in zip(asian,call)],[0,0,10,0],'B5 lower endpoint witness')
    eq([F(s,2)-40-x for s,x in zip(terminal,asian)],[0,10,0,0],'B5 upper endpoint witness')
    eq((10-10*F('.4'),2-(10-10*F('.4'))),(F(6),F(-4)),'B5 omitted fixing error')
    return {'form_a_scored_subparts':19,'form_b_scored_subparts':16,
            'scope':'Independent exact cash, probability, hedge, boundary and interval calculations; all exact written prompts and formal solutions were also read by the coordinator.'}


def check():
    global COUNT
    COUNT=0
    project=project_anchors()
    output=project_output_check()
    transfers=project_transfer_calculations()
    exams=examination_calculations()
    return {'batch':'v10-assessment','status':'passed',
            'comparisons':COUNT,'project':project,'current_project_output':output,'project_transfers':transfers,'examinations':exams,
            'scope':'Independent final desk baseline/output, full project guide/transfers and both examination forms. The selected-reserve repair has its additional focused coordinator regression; separate peer records cover the frozen payloads.',
            'limits':'No package acceptance, Monte Carlo coverage, general convergence or empirical adequacy is implied.'}

if __name__=='__main__':print(json.dumps(check(),indent=2))
