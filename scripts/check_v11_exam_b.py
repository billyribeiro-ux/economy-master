"""Original-contract audit of V11 Form B; no chapter model or saved oracle.

Exact state enumeration, chronological journals, two independent ES methods,
branch endpoints and a two-variable vertex certificate recompute the answers.
check() needs only the four owned files, is quiet and returns strict JSON-safe
metadata. Input/domain checks do not depend on assertions or Python optimization.
"""
from fractions import Fraction as F
from html.parser import HTMLParser
from itertools import combinations, product
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
HTML = 'content/assessments/parts/v11-exam-b.html'
SELF = 'scripts/check_v11_exam_b.py'
SOURCES = 'content/reviews/v11-exam-b-sources.json'
AUTHOR = 'content/reviews/v11-exam-b-author.json'
SCORES = ((6,8,6),(10,10),(6,8,6),(10,10),(6,8,6))
POINTS = {'v11-b-q'+str(i)+letter:score for i,scores in enumerate(SCORES,1)
          for letter,score in zip('abc',scores)}
SOURCE_IDS = {'v11-c01-diamond-monitoring','v11-c03-occ-commercial',
    'v11-c04-rockafellar-uryasev','v11-c02-bcbs-liquidity2008',
    'v10-c12-fed-guidance','v06-c09-debt','v11-c12-bcbs-governance2015'}


def require(ok, label):
    if not ok:
        raise ValueError('V11 Form B: '+label)


class Audit:
    def __init__(self):
        self.comparisons=0; self.rejections=0; self.interventions=[]
    def eq(self,actual,expected,label):
        self.comparisons+=1
        require(actual==expected,label+'; '+repr(actual)+' != '+repr(expected))
    def ok(self,condition,label):
        self.eq(bool(condition),True,label)
    def reject(self,function,label):
        try:
            function()
        except ValueError:
            self.rejections+=1
        else:
            raise ValueError('V11 Form B: expected rejection '+label)
    def intervention(self,name):
        self.interventions.append(name)


def strict(text):
    def pairs(items):
        result={}
        for k,v in items:
            require(k not in result,'duplicate JSON key')
            result[k]=v
        return result
    def bad(x):
        raise ValueError('nonfinite JSON '+x)
    return json.loads(text,object_pairs_hook=pairs,parse_constant=bad)


class Fragment(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack=[]; self.ids=[]; self.points={}; self.solutions=[]
        self.links=[]; self.sources=[]; self.calc={}; self.active=None; self.h1=0
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if 'id' in a: self.ids.append(a['id'])
        if tag=='h1': self.h1+=1
        if tag=='a': self.links.append(a.get('href',''))
        if 'data-source' in a: self.sources.append(a['data-source'])
        if 'data-points' in a:
            require(tag=='li' and 'id' in a and a['id'] not in self.points,'unique scored prompt li')
            self.points[a['id']]=int(a['data-points'])
        if 'data-solution-for' in a:
            self.solutions.append(a['data-solution-for'])
        if 'data-calc' in a:
            require(self.active is None and a['data-calc'] not in self.calc,'unique numeric anchor')
            self.active=a['data-calc']; self.calc[self.active]=''
        if tag not in ('br','hr','img','meta','link','input'):
            self.stack.append(tag)
    def handle_endtag(self,tag):
        if tag=='span': self.active=None
        require(bool(self.stack) and self.stack[-1]==tag,'balanced fragment '+tag)
        self.stack.pop()
    def handle_data(self,text):
        if self.active is not None: self.calc[self.active]+=text


def monitored_payoffs(share,cost,fee,conditional=True):
    """Enumerate default/nondefault receipts for each action and loss bearer."""
    require(0<=share<=1 and cost>=0 and fee>=0,'monitor share/cost/fee domain')
    actions=[]
    for monitor,p in ((False,F(3,20)),(True,F(1,20))):
        transfer=fee if monitor or not conditional else F(0)
        lender=sum(prob*(-loss*share) for prob,loss in ((p,F(20)),(1-p,F(0))))
        investor=sum(prob*(-loss*(1-share)) for prob,loss in ((p,F(20)),(1-p,F(0))))
        lender+=transfer-(cost if monitor else 0)
        investor-=transfer
        actions.append((lender,investor))
    return tuple(actions[1][i]-actions[0][i] for i in range(2))


def repayment(principal,rate,amortization,cash,cfads,grants):
    require(principal>=0 and rate>=0 and cash>=0 and
            len(amortization)==len(cfads)==len(grants)>0,'debt schedule domain')
    require(all(x>=0 for x in amortization+cfads+grants) and sum(amortization)==principal,
            'nonnegative complete principal amortization')
    rows=[]; actual=True
    for date,(amort,receipt,grant) in enumerate(zip(amortization,cfads,grants),1):
        interest=principal*rate; service=amort+interest
        available=cash+receipt+grant
        gap=max(service-available,F(0))
        # Negative projections are diagnostic only; subsequent full-service rows
        # cannot be labeled executed after the first failure.
        cash=available-service
        rows.append(dict(date=date,opening=principal,interest=interest,principal=amort,
                         service=service,cash=cash,gap=gap,executed=actual and gap==0))
        actual=actual and gap==0
        principal-=amort
    return rows


def allowance_journal(provision,chargeoff):
    require(provision>=0 and 0<=chargeoff<=10+provision and chargeoff<=182,'covered chargeoff')
    balances=[dict(cash=F(18),gross=F(182),allowance=F(10),deposits=F(160),debt=F(12),equity=F(18))]
    row=dict(balances[-1]);row['allowance']+=provision;row['equity']-=provision;balances.append(row)
    row=dict(balances[-1]);row['gross']-=chargeoff;row['allowance']-=chargeoff;balances.append(row)
    return balances


def loss_law(theta):
    require(0<=theta<=F(1,4),'feasible joint loss probability')
    # Enumerate individual positions, retaining the common marginal constraints.
    events=[((0,0),F(1,2)+theta),((6,0),F(1,4)-theta),
            ((0,6),F(1,4)-theta),((6,6),theta)]
    law={}
    for losses,p in events:
        law[sum(losses)]=law.get(sum(losses),F(0))+p
    return events,sorted(law.items())


def risk(law,alpha):
    require(0<alpha<1 and all(p>=0 for _,p in law) and sum(p for _,p in law)==1,'finite tail domain')
    remaining=1-alpha; numerator=F(0)
    for loss,p in sorted(law,reverse=True):
        taken=min(p,remaining);numerator+=loss*taken;remaining-=taken
    require(remaining==0,'enough tail mass')
    cumulative=F(0);var=None
    for loss,p in sorted(law):
        cumulative+=p
        if cumulative>=alpha:
            var=F(loss);break
    # Independent piecewise-linear variational characterization, evaluated at
    # every kink; a convex piecewise-affine objective attains its minimum there.
    dual=min(F(z)+sum(p*max(F(loss-z),F(0)) for loss,p in law)/(1-alpha) for z,_ in law)
    return var,numerator/(1-alpha),dual


def common_routes(marginal_a,marginal_b,common):
    require(0<=common<1 and common<=marginal_a<=1 and common<=marginal_b<=1,
            'common event must be inside both marginals')
    a=(marginal_a-common)/(1-common);b=(marginal_b-common)/(1-common)
    events=[(True,True,True,common)]
    for first,second in product((False,True),repeat=2):
        p=(1-common)*(a if first else 1-a)*(b if second else 1-b)
        events.append((False,first,second,p))
    both=sum(p for _,first,second,p in events if first and second)
    posterior=sum(p for shared,first,second,p in events if shared and first and second)/both if both else None
    return a,b,both,posterior,events


def settlement(x,gate=F(3,10),extra=F(0),stale=False):
    require(0<=x<=1 and 0<=gate<=1 and extra>=0,'severity/gate/contribution domain')
    cash=F(10)+extra
    collateral=F(60)
    haircut=F(1,10)+F(1,5)*x
    advance=collateral*(1-haircut)
    receivable=F(12) if stale or x<gate else F(0)
    paid_due=F(60)+20*x
    return cash+advance+receivable-paid_due


def reserve_certificate(horizon,gate):
    """Each branch is decreasing affine: inspect endpoints and one-sided limits."""
    require(0<=horizon<=1 and 0<=gate<=1,'finite reverse horizon')
    values=[settlement(F(0),gate),settlement(horizon,gate)]
    if 0<gate<=horizon:
        values += [F(16)-32*gate,F(4)-32*gate]
    return max(F(0),-min(values)),values


def pension(states,cap):
    require(cap>=0 and sum(row[0] for row in states)==1 and
            all(p>=0 and type(n) is int and n>0 and a>=0 and g>=0 for p,n,a,g in states),
            'pension state probability, survivor and resource domain')
    rows=[]
    for p,n,assets,guarantor in states:
        obligation=30*n
        plan_paid=min(assets,obligation)
        shortage=obligation-plan_paid
        payment=min(shortage,cap,guarantor)
        total=plan_paid+payment
        row=dict(probability=p,promise=F(obligation),shortfall=shortage,guarantee=payment,
                 benefit=total,per_survivor=total/n,unpaid=obligation-total,
                 sponsor=assets-plan_paid,unused=guarantor-payment,resources=assets+guarantor)
        rows.append(row)
    return rows


def sovereign(borrow,grant,conversion=F(2),next_resources=F(18),cap=F(7)):
    require(0<=borrow<=cap and grant>=0 and 0<=conversion<=2 and 2*conversion<=12,
            'sovereign funded currency and commitment domain')
    home=F(12)-2*conversion
    cash=F(9)+8+conversion+borrow+grant
    first=cash-10-15
    last=first+next_resources-12-F(11,10)*borrow
    return home,first,last


def grant_vertices(gap,net_future,gross,cap):
    """Solve all feasible pair intersections in (B,g), not the printed formula."""
    require(gap>=0 and net_future>=0 and gross>=1 and cap>=0,'borrowing optimization domain')
    # Inequalities a*B+b*g >= c preserve the first cutoff, carried cash, cap and
    # nonnegativity. The finite corner enumeration is bounded to ten pairs.
    constraints=[(F(1),F(1),gap),(-(gross-1),F(1),gap-net_future),
                 (F(1),F(0),F(0)),(F(-1),F(0),-cap),(F(0),F(1),F(0))]
    candidates=set()
    for (a,b,c),(d,e,f) in combinations(constraints,2):
        det=a*e-b*d
        if det:
            B=(c*e-b*f)/det;g=(a*f-c*d)/det
            if all(x*B+y*g>=z for x,y,z in constraints):candidates.add((B,g))
    require(bool(candidates),'feasible grant vertex exists')
    return min(candidates,key=lambda x:(x[1],x[0])),sorted(candidates)


def conduct(face,detection=F(1,3),collectible=F(9)):
    require(face>=0 and 0<=detection<=1 and collectible>=0,'conduct domain')
    # State payoffs include the full gain in both states and only actual payment.
    return (1-detection)*6+detection*(6-min(face,collectible))


def resolution(asset,grant):
    """Pay named recipients from separate public, sponsor, issuer/client pockets."""
    require(asset>=0 and 0<=grant<=F(1,5),'resolution estate and grant domain')
    bridge=1-grant
    pockets=dict(issuer=F(6),client=F(1),public=F(1),private=grant,
                 notes=F(0),suppliers=F(0),issuer_equity=F(0),client_equity=F(0))
    def transfer(source,target,amount):
        require(0<=amount<=pockets[source],'unfunded resolution transfer')
        pockets[source]-=amount;pockets[target]+=amount
    transfer('issuer','client',F(6))
    transfer('public','client',bridge)
    transfer('private','client',grant)
    transfer('client','suppliers',F(8))
    require(pockets['client']==0 and pockets['issuer']==0,'early cash exhausted')
    pockets['issuer']+=asset
    notes=min(F(28),pockets['issuer']);transfer('issuer','notes',notes)
    late=min(F(6),pockets['issuer']);transfer('issuer','client',late)
    issuer_equity=pockets['issuer'];transfer('issuer','issuer_equity',issuer_equity)
    repayment=min(bridge,pockets['client']);transfer('client','public',repayment)
    client_equity=pockets['client'];transfer('client','client_equity',client_equity)
    return dict(notes=notes,late=late,issuer_equity=issuer_equity,bridge=bridge,
                repayment=repayment,public_loss=bridge-repayment,public_cash=pockets['public'],
                client_equity=client_equity,network_loss=F(12)-6-late,
                initial_resources=F(8)+grant+asset,recipients=sum(pockets.values()),
                private_residual=pockets['private'])


def finance(a):
    expected={}
    no_fee=monitored_payoffs(F(3,5),F(3,2),F(0))
    paid=monitored_payoffs(F(3,5),F(3,2),F(2,5))
    unconditional=monitored_payoffs(F(3,5),F(3,2),F(2,5),False)
    a.eq(no_fee,(F(-3,10),F(4,5)),'unpaid monitor retains too little')
    a.eq(paid,(F(1,10),F(2,5)),'completion fee shares net surplus')
    a.eq(unconditional,no_fee,'unconditional transfer cancels from effort comparison')
    expected.update(monitor_benefit=sum(no_fee)+F(3,2),monitor_surplus=sum(no_fee),
                    monitor_private_benefit=no_fee[0]+F(3,2),monitor_without_fee=no_fee[0],
                    monitor_with_fee=paid[0],monitor_investor=paid[1])
    retained=monitored_payoffs(F(1),F(3,2),F(0))
    a.eq(retained[0],F(1,2),'full retained loss restores private incentive')
    a.intervention('retain full exposure; monitoring incentive changes')
    old=repayment(F(60),F(2,25),[F(20),F(40)],F(4),[F(18),F(26)],[F(0),F(0)])
    new=repayment(F(48),F(1,25),[F(18),F(30)],F(4),[F(18),F(26)],[F(0),F(0)])
    grant=max(F(0),-new[-1]['cash'])
    funded=repayment(F(48),F(1,25),[F(18),F(30)],F(4),[F(18),F(26)],[F(0),grant])
    a.eq([r['executed'] for r in old],[False,False],'old service table not executed after early failure')
    a.eq([r['executed'] for r in new],[True,False],'amendment still misses second date')
    a.eq([r['cash'] for r in funded],[F(52,25),F(0)],'timely grant funds complete amended path')
    expected.update(old_service1=old[0]['service'],old_service2=old[1]['service'],old_gap1=old[0]['gap'],
                    new_service1=new[0]['service'],new_service2=new[1]['service'],
                    restructure_carry=new[0]['cash'],restructure_grant=grant)
    less=repayment(F(48),F(1,25),[F(18),F(30)],F(4),[F(18),F(26)],[F(0),grant-F(1,100)])
    a.eq(less[-1]['gap'],F(1,100),'one-cent-smaller sponsor contribution fails')
    a.intervention('fund the amendment at the required date; test sharp contribution')
    balances=allowance_journal(F(6),F(12))
    for row in balances:
        a.eq(row['cash']+row['gross']-row['allowance'],row['deposits']+row['debt']+row['equity'],'book identity after each entry')
        a.eq(row['cash'],F(18),'noncash recognition does not alter cash')
    a.eq(balances[1]['gross']-balances[1]['allowance'],balances[2]['gross']-balances[2]['allowance'],'covered chargeoff leaves net loans')
    expected.update(allowance_after_provision=balances[1]['allowance'],assets_after_provision=F(184),
                    equity_after_provision=balances[1]['equity'],gross_after_chargeoff=balances[2]['gross'],
                    allowance_after_chargeoff=balances[2]['allowance'])
    a.eq(allowance_journal(F(0),F(10))[-1]['equity'],F(18),'fully covered alternate chargeoff has no new loss')
    a.intervention('consume a pre-existing sufficient allowance without new provision')
    for theta in (F(0),F(1,20),F(1,10),F(1,5),F(1,4)):
        events,law=loss_law(theta)
        a.eq(sum(p for _,p in events),F(1),'joint probabilities sum to one')
        for position in (0,1):
            a.eq(sum(p for losses,p in events if losses[position]==6),F(1,4),'fixed marginal loss probability')
        mean=sum(F(loss)*p for loss,p in law)
        var,es,dual=risk(law,F(4,5))
        a.eq(mean,F(3),'dependence leaves marginal expected sum fixed')
        a.eq(es,dual,'tail filling agrees with convex hinge objective')
        a.eq(es,min(F(6)+30*theta,F(12)),'derived piecewise ES across financial branches')
        a.eq(es<=9,theta<=F(1,10),'exact dependence policy boundary')
        if theta==F(1,5): expected.update(var_boundary=var,es_boundary=es)
    expected.update(loss_mean=F(3),theta_limit=(F(9)-6)/30)
    a.intervention('vary joint-loss dependence at fixed marginals across tail regimes')
    for theta in (F(999,10000),F(1001,10000)):
        _,es,_=risk(loss_law(theta)[1],F(4,5))
        a.eq(es<=9,theta<F(1,10),'risk-limit sides')
    fixed=[(F(120),F(4),F(1)),(F(100),F(2),F(-1))]
    delta_y=F(1,100)
    fixed_delta=sum(sign*(-duration*value*delta_y) for value,duration,sign in fixed)
    eve=F(120)+80-100-50;nii=(F(80)-50)*delta_y
    a.eq((fixed_delta,nii),(F(-14,5),F(3,10)),'opposite EVE and NII directions')
    expected.update(eve_open=eve,eve_change=fixed_delta,eve_after=eve+fixed_delta,
                    nii_change=nii,alm_cash_gap=F(8)-5)
    a.eq((F(50)-80)*delta_y,-nii,'swapping floating balances changes income, not fixed EVE delta')
    a.intervention('reverse floating repricing gap while preserving fixed value sensitivity')
    x,y,both,posterior,events=common_routes(F(2,25),F(3,25),F(1,25))
    a.eq(sum(p for *_,p in events),F(1),'complete common/residual state law')
    a.eq(sum(p for _,first,_,p in events if first),F(2,25),'route A reconstructed marginal')
    a.eq(sum(p for _,_,second,p in events if second),F(3,25),'route B reconstructed marginal')
    expected.update(route_a_conditional=x,route_b_conditional=y,route_joint=both,route_posterior=posterior,
                    route_false_product=F(2,25)*F(3,25))
    independent=common_routes(F(2,25),F(3,25),F(0))
    a.eq(independent[2],F(6,625),'removing common failure makes the marginal product appropriate')
    a.intervention('remove common event while preserving unconditional route marginals')
    gate=F(3,10); horizon=F(1,2)
    reserve,endpoints=reserve_certificate(horizon,gate)
    a.eq(reserve,F(12),'branch endpoint reserve certificate')
    a.eq(F(16)-32*gate,F(32,5),'strictly positive left-limit headroom')
    a.eq(settlement(gate),F(-28,5),'attained failure at discontinuous timing change')
    for severity in (F(0),F(1,5),gate-F(1,1000000),gate,gate+F(1,1000000),horizon,F(1)):
        actual=settlement(severity)
        a.eq(actual<0,severity>=gate,'actual first-failure set')
        a.eq(settlement(severity,stale=True)<0,severity>horizon,'stale continuous failure set')
        if severity<=horizon: a.ok(settlement(severity,extra=reserve)>=0,'funded cash covers required interval sample')
    a.ok(all(value+reserve>=0 for value in endpoints),'affine branch minima certificate covers entire interval')
    a.ok(settlement(horizon,extra=reserve-F(1,100))<0,'any one-cent-underfunded plan fails the binding endpoint')
    expected.update(reverse_left_limit=F(16)-32*gate,reverse_at_jump=settlement(gate),reverse_first=gate,
                    stale_boundary=horizon,reverse_min_headroom=min(endpoints),reverse_required_cash=reserve)
    a.eq(reserve_certificate(horizon,F(3,5))[0],F(0),'later processing gate changes reverse certificate')
    a.intervention('move receipt gate beyond required stress interval')
    states=[(F(3,10),1,F(45),F(20)),(F(1,2),2,F(55),F(20)),(F(1,5),2,F(30),F(8))]
    rows=pension(states,F(20))
    for row in rows:
        a.eq(row['benefit']+row['sponsor']+row['unused'],row['resources'],'pension and guarantee conserved by state')
        a.eq(row['promise']-row['benefit'],row['unpaid'],'benefit shortfall not extra asset')
    means={key:sum(r['probability']*r[key] for r in rows) for key in ('promise','benefit','unpaid','guarantee')}
    a.eq(means['promise'],means['benefit']+means['unpaid'],'expected benefits reconcile')
    expected.update(pension_bad_guarantee=rows[2]['guarantee'],pension_bad_benefit=rows[2]['benefit'],
                    pension_bad_per_member=rows[2]['per_survivor'],pension_bad_unpaid=rows[2]['unpaid'],
                    pension_expected_promise=means['promise'],pension_expected_benefit=means['benefit'],
                    pension_expected_unpaid=means['unpaid'],pension_expected_guarantee=means['guarantee'])
    rich=list(states);rich[2]=(F(1,5),2,F(30),F(30))
    a.eq(pension(rich,F(20))[2]['unpaid'],F(10),'funding guarantor alone still leaves nominal cap')
    a.eq(pension(rich,F(30))[2]['unpaid'],F(0),'both nominal cap and funding must cover benefit shortage')
    a.intervention('change guarantor resources and then cap; separate both constraints')
    for B in (F(6),F(13,2),F(7)):
        _,first,last=sovereign(B,F(0))
        a.ok(first>=0 and last<0,'no-grant permissible early funding fails later')
        a.eq(last,-B/10,'carry retained in sovereign budget')
    (B,g),vertices=grant_vertices(F(6),F(6),F(11,10),F(7))
    a.eq((B,g),(F(60,11),F(6,11)),'sharp grant plan from feasible vertices')
    a.eq(sovereign(B,g),(F(8),F(0),F(0)),'optimal plan funds both dates and home conversion leg')
    a.ok(all(candidate_g>=g for _,candidate_g in vertices),'minimum over all feasible corner candidates')
    # Independent nonnegative dual certificate: (g+B>=6)+10(g-B/10>=0).
    a.eq(11*g,F(6),'sharp global lower-bound certificate')
    expected.update(sovereign_H_left=F(8),sovereign_F_before=F(19),
                    sovereign_no_grant_gap=-sovereign(F(6),F(0))[2],
                    sovereign_min_grant=g,sovereign_borrow_at_min=B)
    a.eq(grant_vertices(F(6),F(6),F(11,10),F(5))[0],(F(5),F(1)),'lower sovereign borrowing cap binds')
    a.intervention('reduce sovereign borrowing cap; optimal grant and carry recomputed')
    a.eq(grant_vertices(F(6),F(6),F(1),F(7))[0],(F(6),F(0)),'zero borrowing interest removes rollover deficit here')
    a.intervention('remove new borrowing interest, preserving cash carry')
    for face in (F(0),F(6),F(9),F(30)):
        a.eq(conduct(face),F(6)-F(1,3)*min(face,F(9)),'state payoff versus collectible-fine formula')
        a.ok(conduct(face)>0,'face fine alone cannot deter within collectible ceiling')
    weak=F(6,9)
    a.eq(conduct(F(9),weak),F(0),'weak deterrence equality')
    a.ok(conduct(F(9),weak+F(1,100))<0,'strict deterrence requires higher actual detection')
    a.eq(conduct(F(8),F(9,10)),F(-6,5),'smaller collectible fine can deter with higher detection')
    expected.update(conduct_floor_payoff=conduct(F(30)),conduct_weak_detection=weak)
    a.intervention('increase actual detection through the weak deterrence threshold')
    baseline_good=resolution(F(54),F(0));baseline_bad=resolution(F(57,2),F(0))
    expected.update(issuer_notes_after_conversion=F(40)-12,issuer_equity_after_conversion=F(8)+12,
                    client_early_gap=F(8)-1-6,issuer_good_equity=baseline_good['issuer_equity'],
                    client_good_equity=baseline_good['client_equity'],client_bad_late=baseline_bad['late'],
                    public_bad_loss=baseline_bad['public_loss'],network_impairment=baseline_bad['network_loss'])
    minimum=baseline_bad['public_loss']-F(2,5)
    improved=resolution(F(57,2),minimum);good_improved=resolution(F(54),minimum)
    a.eq(minimum,F(1,10),'minimum genuine private contribution')
    a.eq(improved['public_loss'],F(2,5),'binding public loss cap')
    a.ok(resolution(F(57,2),minimum-F(1,100))['public_loss']>F(2,5),'smaller funded private grant fails cap')
    for grant in (F(0),F(1,10),F(1,5)):
        for asset in (F(28),F(57,2),F(54)):
            row=resolution(asset,grant)
            a.eq(row['initial_resources'],row['recipients'],'all issuer/client/public/private recipients conserved')
            a.eq(row['network_loss'],F(5)+grant-row['client_equity']+row['public_loss'],'network impairment allocated once')
            a.eq(row['public_cash'],1-row['public_loss'],'undrawn public cash remains real wealth')
            a.eq(row['private_residual'],F(0),'private grant has no implicit residual right')
    expected.update(private_min_contribution=minimum,public_reduced_bridge=improved['bridge'],
                    public_reduced_loss=improved['public_loss'],public_reduced_terminal_cash=improved['public_cash'],
                    client_grant_good_equity=good_improved['client_equity'])
    a.intervention('replace part of public lending with separately funded private grant; adverse allocation changes')
    a.intervention('reduce issuer estate to senior-note boundary; client and public losses respond')
    a.reject(lambda:loss_law(F(3,10)),'impossible dependence')
    a.reject(lambda:risk([(0,F(1))],F(1)),'zero ES tail')
    a.reject(lambda:common_routes(F(1,10),F(1,5),F(3,20)),'common event exceeds marginal')
    a.reject(lambda:settlement(F(-1,10)),'negative severity')
    a.reject(lambda:allowance_journal(F(0),F(11)),'insufficient allowance')
    a.reject(lambda:pension([(F(1),0,F(5),F(5))],F(10)),'zero survivor denominator')
    a.reject(lambda:sovereign(F(8),F(0)),'uncommitted borrowing')
    a.reject(lambda:sovereign(F(6),F(0),conversion=F(3)),'currency permission cap')
    a.reject(lambda:conduct(F(-1)),'negative fine')
    a.reject(lambda:resolution(F(54),F(3,10)),'unpermitted private contribution')
    return expected


def check(root=None):
    root=Path(root) if root is not None else ROOT
    a=Audit()
    fragment=Fragment();text=(root/HTML).read_text();fragment.feed(text);fragment.close()
    a.eq(fragment.stack,[],'closed HTML fragment')
    a.eq(fragment.h1,0,'no extra document h1')
    a.eq(fragment.points,POINTS,'all thirteen exact scored subparts')
    a.eq(sorted(fragment.solutions),sorted(POINTS),'one complete solution per prompt')
    a.eq(len(fragment.ids),len(set(fragment.ids)),'unique assessment IDs')
    a.ok(all(x in ('form-b','solutions-b') or x.startswith('v11-b-') for x in fragment.ids),'scoped detail IDs')
    a.eq(sum(fragment.points.values()),100,'exact total points')
    for q in range(1,6):
        a.eq(sum(v for k,v in fragment.points.items() if k.startswith('v11-b-q'+str(q))),20,'domain '+str(q)+' points')
    a.ok({f'v11-c{i:02}.html' for i in range(1,13)}<=set(fragment.links),'all twelve chapter coverage links')
    a.ok(not any(url.startswith(('projects/','chapters/')) for url in fragment.links),'flat reader links')
    sources=strict((root/SOURCES).read_text())
    a.eq(set(fragment.sources),SOURCE_IDS,'exact cited method sources')
    a.eq({r['id'] for r in sources['reused_sources']},SOURCE_IDS,'source records match manuscript')
    a.eq(len(sources['reused_sources']),len(SOURCE_IDS),'no duplicate source record')
    a.eq(sources['proposals'],[],'accepted scoped sources only')
    expected=finance(a)
    a.eq(set(fragment.calc),set(expected),'all printed numeric anchors independently derived')
    for name,value in expected.items():
        a.eq(F(fragment.calc[name].strip().replace('−','-')),value,'printed '+name)
    record=strict((root/AUTHOR).read_text());rows=record['reviewed_hashes']
    a.eq({r['path'] for r in rows},{HTML,SELF,SOURCES},'exact three nonself author bindings')
    a.eq(len(rows),3,'no missing or duplicate author binding')
    for row in rows:
        blob=(root/row['path']).read_bytes()
        a.eq((len(blob),hashlib.sha256(blob).hexdigest()),(row['bytes'],row['sha256']),'author binding '+row['path'])
    summary=dict(component='v11-exam-b',status='passed',points=100,domains=5,
                 scored_subparts=len(POINTS),solved_subparts=len(fragment.solutions),
                 printed_numerical_anchors=len(expected),comparisons=a.comparisons,
                 financial_interventions=len(a.interventions),domain_rejections=a.rejections,
                 chapter_outcomes=12,author_bindings=3,
                 method='Exact original-contract state enumeration, dated journals, tail/hinge comparison, branch-minimum and vertex/dual certificates; no chapter model or saved-output oracle.',
                 limits='Finite synthetic contracts; local EVE approximation; no empirical frequency, current legal authority, timing calibration, human certification or rendered QA.')
    strict(json.dumps(summary,allow_nan=False))
    return summary


if __name__=='__main__':
    print(json.dumps(check(),indent=2,allow_nan=False))
