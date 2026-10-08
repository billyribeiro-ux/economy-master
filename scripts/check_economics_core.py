#!/usr/bin/env python3
"""Independent exact audit of economics-core forms, model ledgers and finite design."""
from collections import Counter
from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
from fractions import Fraction as F
from html.parser import HTMLParser
from itertools import combinations, product
import importlib.util
import io
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

BOOK=Path(__file__).resolve().parents[1]
PROJECT=BOOK/'content/projects'


def need(condition,label):
    if not condition:
        raise AssertionError(label)


def solve(matrix,rhs):
    """Small independent exact row elimination, used on original equilibrium equations."""
    a=[[F(v) for v in row]+[F(b)] for row,b in zip(matrix,rhs)]
    n=len(a)
    for j in range(n):
        pivot=next(i for i in range(j,n) if a[i][j])
        a[j],a[pivot]=a[pivot],a[j]
        scale=a[j][j];a[j]=[v/scale for v in a[j]]
        for i in range(n):
            if i!=j:
                scale=a[i][j];a[i]=[x-scale*y for x,y in zip(a[i],a[j])]
    return tuple(row[-1] for row in a)


def render(value):
    if isinstance(value,F):return str(value)
    if isinstance(value,dict):return {k:render(v) for k,v in value.items()}
    if isinstance(value,(tuple,list)):return [render(v) for v in value]
    return value


def lottery(values,treated):
    n=len(values);m=len(treated)
    def diff(indices):
        return sum((values[i] for i in indices),F(0))/m-sum((values[i] for i in range(n) if i not in indices),F(0))/(n-m)
    actual=diff(treated)
    # Bit-mask implementation independent of the lab's combinations loop.
    all_values=[diff(tuple(i for i in range(n) if mask>>i&1)) for mask in range(1<<n) if bin(mask).count("1")==m]
    return actual,F(sum(abs(x)>=abs(actual) for x in all_values),len(all_values)),Counter(all_values)


def nk_reference(future_x,future_pi,n,u):
    # Unknowns x, pi, j; enumerate both policy branches using the original equations.
    candidates=set()
    for floor in (False,True):
        rows=[[1,0,1],[F(-1,2),1,0],[0,0,1] if floor else [0,-2,1]]
        rhs=[future_x+future_pi+n,future_pi/2+u,-1 if floor else 0]
        x,pi,j=solve(rows,rhs)
        if j==max(F(-1),2*pi):candidates.add((x,pi,j))
    need(len(candidates)==1,'unique finite NK branch')
    return next(iter(candidates))


def reference_policy(policy):
    """Reconstruct complete ledgers from independent first-order systems and cash uses."""
    if policy['kind']=='tax':
        t,tau=F(policy['tariff']),F(policy['carbon']);cap=None
        p=8+t
        # Supply is a constrained maximizer; compare positive stationary point to zero.
        candidates=[F(0)]
        if p-tau>0:candidates.append(p-tau)
        q=max(candidates,key=lambda z:(p-tau)*z-z*z/2)
        permit=F(0)
    else:
        t=tau=F(0);p=F(8);cap=F(policy['cap'])
        q=min(F(8),cap);permit=(p-q)*q
    x,y=solve([[1,0],[0,1]],[20-p,12-p])
    need(x>=0 and y>=0,'reference consumer interior/zero feasible')
    imported=x+y-q
    cost=q*q/2;damage=q*q/4
    ba=20*x-x*x/2;bb=12*y-y*y/2
    profit=p*q-cost-tau*q-permit
    revenue=t*imported+tau*q+permit
    ca=20-8*imported-2+1
    pub_net=20+2-16
    # Funding determined from country external gap after public funding.
    private=-ca-pub_net;b=private/2
    za=100+profit+b-(8+p*x+10)
    zb=100+revenue+1+b-(8+p*y)
    consumption=za+zb+p*(x+y)
    gdp_exp=consumption+20+10+20-8*imported
    base=200+8*q-cost
    saving=(gdp_exp-2+1)-consumption-20
    ua=ba+za-b-3+10;ub=bb+zb-damage-b-3
    sector=ba+bb-cost-8*imported-damage
    fields={'price':p,'x':x,'y':y,'domestic_q':q,'demand':x+y,'imports':imported,'resource_cost':cost,'damage':damage,'carbon':tau,'tariff':t,'permit_shadow':p-q if cap is not None else F(0),'carbon_revenue':tau*q,'tariff_revenue':t*imported,'permit_revenue':permit,'revenue':revenue,'profit_A':profit,'consumer_surplus_A':ba-p*x,'consumer_surplus_B':bb-p*y,'sector_welfare_A':ba-p*x+profit,'sector_welfare_B':bb-p*y+revenue-damage,'sector_welfare':sector,'private_net_borrowing':private,'household_net_borrowing':b,'z_A':za,'z_B':zb,'consumption':consumption,'investment':F(10),'government_consumption':F(20),'net_exports':20-8*imported,'nominal_gdp':gdp_exp,'base_price_gdp':base,'gdp_deflator':gdp_exp/base,'gni':gdp_exp-2,'gndi':gdp_exp-1,'national_saving':saving,'current_account':ca,'capital_account':F(0),'external_asset_acquisition':max(-private,F(0)),'external_liability_incurrence':pub_net+max(private,F(0)),'financial_account':ca,'public_interest':F(2),'public_primary_surplus':F(-4),'public_end_debt':50+pub_net,'public_gross_issuance':25+pub_net,'public_debt_gdp':(50+pub_net)/gdp_exp,'nfa_open':2*(20-15)-50,'nfa_valuation':(F(11,5)-2)*(20-15),'nfa_close':F(11,5)*(20-15)-50+ca,'terminal_numeraire_A':F(175,2)-b,'terminal_numeraire_B':F(155,2)-b,'full_utility_A':ua+F(161,2),'full_utility_B':ub+F(161,2),'adjusted_utility_A':ua,'adjusted_utility_B':ub,'adjusted_utility_total':ua+ub,'global_welfare_gap':(x-12)**2/2+(y-4)**2/2+F(3,4)*(q-F(16,3))**2}
    return fields


def audit_row(row):
    r={k:F(v) for k,v in row.items() if k not in ('id','kind')}
    need(r['demand']==r['x']+r['y']==r['domestic_q']+r['imports'],'energy clearing')
    need(r['z_A']+r['z_B']+r['resource_cost']+20+10+20==200,'numeraire resources')
    need(r['nominal_gdp']==r['consumption']+30+r['net_exports'],'expenditure GDP')
    need(r['nominal_gdp']==200+r['price']*r['domestic_q']-r['resource_cost']+r['tariff_revenue'],'production GDP')
    need(r['current_account']==r['national_saving']-10==r['financial_account'],'saving/current/financial account')
    need(r['financial_account']==r['external_asset_acquisition']-r['external_liability_incurrence'],'gross external finance')
    need(r['private_net_borrowing']+6==-r['current_account'],'public/private external funding')
    need(r['nfa_close']==r['nfa_open']+r['nfa_valuation']+r['financial_account'],'NFA stocks and flows')
    need(r['sector_welfare']==r['sector_welfare_A']+r['sector_welfare_B'],'welfare distribution')
    need(r['adjusted_utility_total']==179+r['sector_welfare'],'terminal-adjusted welfare')
    need(r['public_end_debt']==25+r['public_gross_issuance']==56,'public rollovers')
    need(16+r['revenue']+r['public_gross_issuance']==20+r['revenue']+2+25,'public cash')
    need(min(r['z_A'],r['z_B'])>=0 and r['imports']>=0,'feasible current budgets/imports')
    b=r['household_net_borrowing']
    need(r['terminal_numeraire_A']==100+10+F(11,2)-b-28 and r['terminal_numeraire_B']==100+F(11,2)-b-28,'full terminal household budgets')
    need(min(r['terminal_numeraire_A'],r['terminal_numeraire_B'])>=0,'terminal nonnegative numeraire')
    need(r['terminal_numeraire_A']+r['terminal_numeraire_B']==210+r['nfa_close'],'terminal country resources and foreign settlement')
    need(r['full_utility_A']-F(161,2)==r['adjusted_utility_A'] and r['full_utility_B']-F(161,2)==r['adjusted_utility_B'],'common baseline utility omitted transparently')
    need(r['global_welfare_gap']==F(304,3)-r['sector_welfare']>=0,'global welfare certificate')


class Fragment(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.ids=[];self.links=[];self.sources=[];self.stack=[];self.h1=0;self.part_points=[];self.rubric_points=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag not in {'area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'}:self.stack.append(tag)
        if tag=='h1':self.h1+=1
        if 'id' in a:self.ids.append(a['id'])
        if 'href' in a:self.links.append(a['href'])
        if 'data-source' in a:self.sources.append(a['data-source'])
        if tag=='li' and 'data-points' in a:self.part_points.append(int(a['data-points']))
        if 'rubric' in a.get('class','').split():self.rubric_points.append(int(a['data-points']))
    def handle_endtag(self,tag):
        need(self.stack and self.stack[-1]==tag,'balanced HTML tag '+tag)
        self.stack.pop()


def check():
    checks=[];results={}
    def done(name,**kw):checks.append(dict(name=name,status='pass',**kw))
    # Form A1: solve original marginal-demand and supply system, then certify a global optimum.
    x,y,q,p=solve([[1,0,0,1],[0,1,0,1],[0,0,1,-1],[1,1,-1,0]],[15,9,0,0])
    need((x,y,q,p)==(7,1,8,8),'A1 competitive system')
    need(x*x/2+y*y/2+q*q/2-q*q/4==41,'A1 total surplus')
    for a,b in product(range(16),range(10)):
        welfare=15*a+9*b-F(a*a+b*b,2)-F(3,4)*(a+b)**2
        gap=F((a-6)**2+b*b,2)+F(3,4)*(a+b-6)**2
        need(45-welfare==gap>=0,'A1 exact quadratic certificate')
    need(F(113,2)-36==F(41,2) and 9+F(31,2)==F(49,2),'A1 compensation bounds')
    need((36+22-F(113,2),9-22+F(31,2))==(F(3,2),F(5,2)),'A1 distribution')
    need(86+96==200-18 and 76+92==200-32,'A1 numeraire resources')
    done('Form A D1: equilibrium, 160 certificate evaluations and ownership budgets')
    # A2: explicit finite-state expectations; verify lower bound over a feasible contract grid.
    best=None
    for failure in (F(i,4) for i in range(33)):
        for spread in (F(i,4) for i in range(0,81)):
            ew=failure+F(3,4)*spread
            high=ew-6;low=failure+F(1,4)*spread
            if high>=low and high>=2:
                best=ew if best is None else min(best,ew)
                need(failure+spread>=12,'A2 escrow lower bound')
    need(best==9,'A2 least wage grid plus analytic bound')
    success=16+1-5-12+60-F(3,2)
    failure=16+1-5-12+12-F(3,2)
    profit=F(3,4)*success+F(1,4)*failure-16
    need((success,failure,profit)==(F(117,2),F(21,2),F(61,2)),'A2 contingent cash')
    need((45-9-5,15-2-5,45-8-3-5)==(31,8,29),'A2 action/monitor choice')
    need(32-4==28 and 32-3==29,'retention funding threshold')
    done('Form A D2: IC/participation, escrow and state-contingent credit')
    # A3: distinguish analytic proof in manuscript from finite trajectory diagnostics.
    gamma=F(5,4)*F(6,5);d=F(1,4)+gamma-1
    need((gamma,d)==(F(3,2),F(3,4)),'A3 exact demographic/productivity factor')
    need(F(16,1)/6==F(8,3) and (F(1,2)/d)**2==F(4,9),'A3 states')
    need(F(1,2)*F(2,3)==F(1,3) and F(1,4)*1==F(1,4),'A3 consumption')
    for start in (0.001,0.1,1,4,100):
        k=start;target=4/9
        for _ in range(100):
            nxt=(.75*k+.5*math.sqrt(k))/1.5
            need(min(k,target)-1e-12<=nxt<=max(k,target)+1e-12,'A3 no overshoot on finite path')
            k=nxt
        need(abs(k-target)<1e-9,'A3 positive path diagnostic')
    need(math.isclose(math.log(math.sqrt(1.5)),.5*math.log(1.25)+.5*math.log(1.2),abs_tol=1e-14),'A3 exact log identity numeric evaluation')
    need((F(1,2)/F(1,4))**2==4,'retention no-dilution steady state')
    done('Form A D3: exact accumulation, golden rule and finite convergence diagnostics',path_steps=500)
    # A4: individual cash paths and full country accounts.
    gdp=140+40+20+30-20;gni=gdp-4;gndi=gni+1;saving=gndi-140-20
    need((gdp,gni,gndi,saving,saving-40)==(210,206,207,47,7),'A4 income/saving')
    need(F(51,50)*F(35,34)==F(21,20),'A4 nominal denominator')
    interest=F(80,20);mature=F(2,5)*80;issue=mature+interest-3+2
    need((80+interest-3+2,issue,80-mature+issue)==(83,35,83),'A4 public financing')
    need(2*(50-60)-10+(3-2)*(50-60)+(11-5)==-34,'A4 NFA')
    forward=2*F(105,100)/F(102,100)
    need(forward==F(35,17) and F(21,10)*F(102,100)-2*F(105,100)==F(21,500),'A4 covered cash trade')
    done('Form A D4: national/public/external ledgers and covered parity')
    # A5: original equations solved by elimination, floor branch enumeration, exact lottery.
    later=nk_reference(F(0),F(0),F(-2),F(2));earlier=nk_reference(later[0],later[1],F(0),F(0))
    need(later==(-3,F(1,2),1) and earlier==(F(-3,2),F(-1,2),-1),'A5 announced path')
    need(nk_reference(F(0),F(0),F(0),F(0))==(0,0,0),'A5 unforeseen earlier expectations')
    for v in (F(i,4) for i in range(-40,-3)):
        loss=(v/2+2)**2+v*v/4
        need(loss==F(1,2)*(v+2)**2+2>=2,'A5 feasible global policy loss')
    need(F(1,2)**2+F(9,4)==F(5,2),'A5 rule loss')
    contrast,pval,dist=lottery(list(map(F,[6,4,3,1])),(0,1))
    need(contrast==3 and pval==F(1,3) and dist==Counter({3:1,2:1,0:2,-2:1,-3:1}),'A5 exact randomization')
    results['A5']={'date1':later,'date0':earlier,'pilot_contrast':contrast,'pilot_p':pval}
    done('Form A D5: floor branches, global loss and exact assignment law')
    # Form B1: expenditure-per-utility and wealth effects, trade balances.
    for price,t in [(F(1),F(0)),(F(1,2),F(0)),(F(1,2),F(2)),(F(2),F(0))]:
        wealth_a=6*price+t;utility_a=wealth_a/(price+F(1,2));xa,ya=utility_a,utility_a/2
        if price<1:xb,yb=(6-t)/price,F(0)
        elif price>1:xb,yb=F(0),6-t
        else:xb,yb=6-xa,6-ya
        need(price*(xa+xb-6)+(ya+yb-6)==0,'B1 aggregate trade value')
        if price==F(1,2) and t==2:need((xa,ya,xb,yb)==(5,F(5,2),8,0),'B1 compensated allocation')
        if price==2:need((xa,ya,xb,yb)==(F(24,5),F(12,5),0,6),'B1 endowment wealth')
    for t in (F(i,4) for i in range(25)):
        need(((3+t>=4) and (12-2*t>=6))==(1<=t<=3),'B1 compensation interval')
    done('Form B D1: exchange budgets, demand correspondence and compensation')
    # B2: enumerate strategic deviations instead of using a declared equilibrium list.
    payoff={('W','W'):(F(6,5),F(6,5)),('R','W'):(F(1),F(1,5)),('W','R'):(F(1,5),F(1)),('R','R'):(F(3,5),F(3,5))}
    equilibria=[]
    for actions,pay in payoff.items():
        if all(pay[i]>=payoff[tuple(a if j!=i else ('R' if a=='W' else 'W') for j,a in enumerate(actions))][i] for i in range(2)):
            equilibria.append(''.join(actions))
    need(set(equilibria)=={'WW','RR'},'B2 pure equilibria')
    prob=F(1,3)
    need(1-F(2,5)*prob==F(6,5)-prob==F(13,15),'B2 mixed payoff')
    for runners in (0,1,2):
        draw=max(F(runners)-F(2,5),F(0))
        cash_after=F(2,5)+draw-runners
        late_assets=2+cash_after
        late_deposits=(2-runners)*F(6,5)
        residual=late_assets-draw-late_deposits
        need((draw,residual)==[(F(0),F(0)),(F(3,5),F(1,5)),(F(8,5),F(2,5))][runners],'B2 facility cash/priority')
    need(F(12,5)-(F(2,5)+F(3,2))==F(1,2) and F(8,5)-F(3,2)==F(1,10),'B2 solvency/lender losses')
    done('Form B D2: full strategic deviations and senior funding/loss ledgers')
    # B3: directly evaluate marginal aggregate matches and fixed-point flows.
    u=F(20);v_private=3*u;v_social=u
    matching=lambda v:u*v/(u+v)
    need(matching(v_private)==15 and matching(v_social)==10,'B3 matches')
    need(F(9,10)*80+15==87 and F(9,10)*80+10==82,'B3 timing')
    need(2*matching(v_private)-v_private/2==0 and 2*matching(v_social)-v_social/2==10,'B3 welfare')
    for v in range(201):
        need(10-(2*matching(v)-F(v,2))==F((v-20)**2,2*(v+20))>=0,'B3 independent global gap')
    for f,steady,slope in [(F(3,4),F(2,17),F(3,20)),(F(1,2),F(1,6),F(2,5))]:
        need(F(1,10)+(1-F(1,10)-f)*steady==steady and 1-F(1,10)-f==slope,'B3 unemployment fixed point')
    done('Form B D3: matching, global surplus certificate and unemployment dynamics')
    # B4: bank and government roll-forwards, nonlinear debt boundary.
    need(12+80==90+2 and 27+80==90+15+2 and 33+80==90+15+8,'B4 bank stages')
    need(100+4-2+6==108 and F(108-6,108)==F(17,18),'B4 gross/net public positions')
    debtmap=lambda d:F(51,50)*d-min(F(3,100),F(1,50)+F(1,10)*(d-1))
    need(debtmap(F(1))==1 and debtmap(F(7,5))==F(699,500) and debtmap(F(8,5))==F(801,500),'B4 cap cases')
    need(debtmap(F(3,2))==F(3,2),'B4 cap stationary threshold')
    done('Form B D4: bank capital, recapitalization and capped debt feedback')
    # B5: derive each date by solving original current equations.
    def inflation(prev,shock):return solve([[1,F(-1,2)],[1,1]],[prev/2+1+shock,2])
    pi1,x1=inflation(F(2),F(3));pi2,x2=inflation(pi1,F(0))
    need((pi1,x1,pi2,x2)==(4,-2,F(8,3),F(-2,3)),'B5 adaptive path')
    need(inflation(F(5),F(3))==(5,-3),'B5 permanent-shock fixed point')
    need(math.isclose(math.exp(.03)/math.exp(.04),math.exp(-.01),rel_tol=1e-14),'B5 exact real return')
    need(math.isclose(math.exp(float((pi1+pi2)/100)),math.exp(1/15),rel_tol=1e-14),'B5 price path')
    need(F(110)*F(18,10)/180==F(100)*F(198,100)/180==F(11,10),'B5 quantity observational alternatives')
    for treated_count in (1,2,3):
        for assignment in combinations(range(4),treated_count):
            ys=[10+3*(i in assignment)+F(6,3)*sum(j in assignment for j in range(4) if j!=i) for i in range(4)]
            diff=sum(ys[i] for i in assignment)/treated_count-sum(ys[i] for i in range(4) if i not in assignment)/(4-treated_count)
            need(diff==1,'B5/retention saturation contrasts fail independent identification')
    need(3+6==9 and 1+0==1,'B5 universal effects differ')
    done('Form B D5: exact inflation/return identities and all interference assignments')
    # Oral and delayed targets independent of written numeric examples.
    need((12-4)*4-4*4==16 and F(8*8,1)-F(8*8,2)==32,'oral monopoly/resource objectives')
    need(20-2>15 and 20-13<8 and 20-9>8,'oral signaling IC/participation/cost change')
    need(F(1,2)*F(9,10)**2*8-F(1,2)*F(9,10)*6==F(27,50),'oral credible commitment fee')
    need(4*4-F(4*4,2)==8 and 6*6-F(6*6,2)==18,'oral research global maxima')
    need(104==100+4 and 112==100+8+4,'oral funding balance sheet')
    need(-40+(F(9,5)-2)*5-45==-86,'retention FX reversal')
    done('Oral transfer and delayed checks: strategic, behavioral, innovation and ledger anchors')
    # Load the actual lab quietly; no installed packages or output coercion.
    captured=io.StringIO()
    with redirect_stdout(captured),redirect_stderr(captured):
        spec=importlib.util.spec_from_file_location('economics_core_lab',PROJECT/'economics-core-analysis.py')
        lab=importlib.util.module_from_spec(spec);spec.loader.exec_module(lab)
        data=json.loads((PROJECT/'economics-core-inputs.json').read_text())
        original=deepcopy(data);output=lab.analyze(data)
    need(not captured.getvalue() and data==original,'quiet nonmutating lab API')
    need(output==json.loads((PROJECT/'economics-core-benchmark.json').read_text()),'frozen full benchmark')
    json.dumps(output,allow_nan=False)
    expected_anchors=[(F(96),F(232),F(-45)),(F(304,3),F(2056,9),F(-199,3)),(F(96),F(2296,9),F(-71,3)),(F(100),F(224),F(-77))]
    for policy,row,anchor in zip(data['policies'],output['policies'],expected_anchors):
        ref=reference_policy(policy)
        need(set(ref)==set(row)-{'id','kind'},'complete independently checked numeric fields')
        for key,expected in ref.items():need(F(row[key])==expected,'independent practical field '+policy['id']+'/'+key)
        audit_row(row)
        need(tuple(F(row[k]) for k in ('sector_welfare','nominal_gdp','current_account'))==anchor,'practical published anchors')
    base,carbon,tariff,quota=output['policies']
    lo=F(base['sector_welfare_A'])-F(carbon['sector_welfare_A']);hi=F(carbon['sector_welfare_B'])-F(base['sector_welfare_B'])
    need((lo,hi)==(F(160,9),F(208,9)) and lo<20<hi,'practical carbon compensation')
    for row,transfer in [(carbon,F(20)),(quota,F(26))]:
        need(F(row['z_B'])-transfer>=0 and F(row['z_A'])+transfer>=0,'post-transfer nonnegative budgets')
        need(F(row['adjusted_utility_A'])+transfer>F(base['adjusted_utility_A']) and F(row['adjusted_utility_B'])-transfer>F(base['adjusted_utility_B']),'post-transfer Pareto gains')
    need(F(tariff['nominal_gdp'])/232==F(287,261) and F(tariff['base_price_gdp'])/232==F(260,261) and F(tariff['gdp_deflator'])==F(287,260),'nominal/real/deflator decomposition')
    done('Practical: four full independently derived household, public, national and external ledgers',numeric_fields_per_policy=len(ref))
    # Transfer beyond original rows, including shutdown, zero quota and net asset accumulation.
    sensitivity=deepcopy(data)
    sensitivity['policies']=[dict(id='t'+str(i)+'c'+str(j),kind='tax',tariff=str(F(i,2)),carbon=str(F(j,2))) for i in range(5) for j in range(21)]
    sensitivity['policies'] += [dict(id='cap'+str(i),kind='quota',cap=str(F(i,2))) for i in range(17)]
    sensitivity['policies'] += [dict(id='optimal_cap',kind='quota',cap='16/3')]
    variations=lab.analyze(sensitivity)['policies']
    for policy,row in zip(sensitivity['policies'],variations):
        for key,val in reference_policy(policy).items():need(F(row[key])==val,'practical transfer field '+key)
        audit_row(row)
    equivalent=variations[-1]
    for key in ('x','y','domestic_q','imports','revenue','profit_A','sector_welfare_A','sector_welfare_B','nominal_gdp','current_account'):
        need(equivalent[key]==carbon[key],'auctioned cap/carbon equivalence')
    need(any(F(r['domestic_q'])==0 for r in variations),'shutdown boundary exercised')
    need(any(F(r['external_asset_acquisition'])>0 for r in variations),'negative net borrowing records asset acquisition')
    done('Practical supported-domain transfer and active-set boundaries',policies=len(variations))
    # Independent release selection through chronological revision application.
    pilot=data['pilot'];frozen={}
    for row in sorted(pilot['records'],key=lambda r:r['released']):
        if row['released']<=pilot['cutoff']:frozen[(row['community'],row['period'])]=F(row['usage'])
    changes=[frozen[c,'2024-05']-frozen[c,'2024-04'] for c in 'ABCDEF']
    actual,pval,distribution=lottery(changes,(0,1,2))
    need(changes==list(map(F,[-2,-2,0,0,1,1])) and actual==-2 and pval==F(1,5),'practical cutoff estimator/tail')
    expected_dist=Counter({F(-2):2,F(-4,3):2,F(-2,3):2,F(0):8,F(2,3):2,F(4,3):2,F(2):2})
    need(distribution==expected_dist==Counter(map(F,output['pilot']['assignment_contrasts'])),'practical complete finite distribution')
    later=deepcopy(data);later['pilot']['cutoff']='2024-07-02'
    revised=lab.analyze(later)['pilot']
    need(F(revised['contrast'])==F(-5,3) and F(revised['sharp_null_p'])==F(1,5),'late revision point estimate differs while p unchanged')
    shuffled=deepcopy(data);shuffled['pilot']['records'].reverse();shuffled['policies'].reverse()
    reordered=lab.analyze(shuffled)
    need(reordered['pilot']==output['pilot'] and reordered['policies']==list(reversed(output['policies'])),'ordering invariance')
    need(all(key[2]<='2024-06-15' for key in output['pilot']['selected_release_keys']),'selected availability')
    results['practical_pilot']={'contrast':actual,'p':pval,'distribution':{str(k):v for k,v in distribution.items()},'revised_contrast':F(revised['contrast'])}
    for selected in combinations('ABCDEF',3):
        reassigned=deepcopy(data);reassigned['pilot']['treated']=list(selected)
        actual_row=lab.analyze(reassigned)['pilot']
        independent_contrast,independent_p,_=lottery(changes,tuple('ABCDEF'.index(c) for c in selected))
        need(F(actual_row['contrast'])==independent_contrast and F(actual_row['sharp_null_p'])==independent_p,'all realized assignment transfers')
    done('Historical cutoff, revision leak, complete uniform lottery and order invariance',assignments=20,realized_assignment_transfers=20)
    # Explicitly malformed units, parameters, policy domains, release keys and coverage.
    invalid=[]
    def bad(change):
        candidate=deepcopy(data);change(candidate);invalid.append(candidate)
    bad(lambda d:d['units'].__setitem__('currency','USD'))
    bad(lambda d:d['model'].__setitem__('foreign_energy_price','9'))
    bad(lambda d:d.__setitem__('schema','other'))
    bad(lambda d:d.__setitem__('extra',1))
    bad(lambda d:d['policies'][0].__setitem__('tariff','-1'))
    bad(lambda d:d['policies'][0].__setitem__('tariff','3'))
    bad(lambda d:d['policies'][0].__setitem__('carbon','11'))
    bad(lambda d:d['policies'][0].__setitem__('carbon','-1'))
    bad(lambda d:d['policies'][0].__setitem__('tariff',False))
    bad(lambda d:d['policies'][0].__setitem__('carbon',1.5))
    bad(lambda d:d['policies'][0].__setitem__('carbon','1/0'))
    bad(lambda d:d['policies'][0].__setitem__('carbon','NaN'))
    bad(lambda d:d['policies'][0].__setitem__('kind','subsidy'))
    bad(lambda d:d['policies'][3].__setitem__('cap','9'))
    bad(lambda d:d['policies'][3].__setitem__('cap','-1'))
    bad(lambda d:d['policies'][0].__setitem__('cap','4'))
    bad(lambda d:d['policies'].append(deepcopy(d['policies'][0])))
    bad(lambda d:d.__setitem__('policies',[]))
    bad(lambda d:d['pilot'].__setitem__('assignment','independent-coins'))
    bad(lambda d:d['pilot'].__setitem__('assignment_date','2024-04-01'))
    bad(lambda d:d['pilot'].__setitem__('cutoff','2024-06-09'))
    bad(lambda d:d['pilot'].__setitem__('cutoff','2024-6-15'))
    bad(lambda d:d['pilot'].__setitem__('treated',['A','A','B']))
    bad(lambda d:d['pilot'].__setitem__('treated',['A','B','Z']))
    bad(lambda d:d['pilot'].__setitem__('baseline_period','2024-03'))
    bad(lambda d:d['pilot']['records'].append(deepcopy(d['pilot']['records'][0])))
    bad(lambda d:d['pilot']['records'].pop(3))
    bad(lambda d:d['pilot']['records'][0].__setitem__('usage','-1'))
    bad(lambda d:d['pilot']['records'][0].__setitem__('released','2024-04-20'))
    bad(lambda d:d['pilot']['records'][0].__setitem__('community','Z'))
    bad(lambda d:d['pilot']['records'][0].__setitem__('period','2024-06'))
    for candidate in invalid:
        try:lab.analyze(candidate)
        except ValueError:pass
        else:raise AssertionError('invalid input was accepted')
    done('Input contract failures including wrong units, duplicate releases and missing historical coverage',rejections=len(invalid))
    # Break actual benchmark ledgers; require independent audit detection.
    for key in ('nominal_gdp','nfa_close','sector_welfare','adjusted_utility_total','public_gross_issuance','financial_account'):
        broken=deepcopy(output['policies'][0]);broken[key]=str(F(broken[key])+1)
        try:audit_row(broken)
        except AssertionError:pass
        else:raise AssertionError('damaged ledger not caught: '+key)
    need(F(revised['contrast'])!=F(output['pilot']['contrast']),'vintage mutant detected by point estimate')
    done('Damaged-result detection: six ledger mutants and future-vintage substitution',mutants=7)
    manuscript=(BOOK/'content/cross-assessments/economics-core.html').read_text()
    parser=Fragment();parser.feed(manuscript);parser.close()
    need(not parser.stack and parser.h1==1,'one balanced cumulative h1')
    need(len(parser.ids)==len(set(parser.ids)),'unique cumulative IDs')
    need(parser.part_points==[5]*40 and parser.rubric_points==[5]*40,'forty exact prompt and solution scoring parts')
    for name,start,end in [('A','<h2 id="form-a">','<h2 id="form-b">'),('B','<h2 id="form-b">','<h2 id="practical">')]:
        section=manuscript.split(start,1)[1].split(end,1)[0]
        need(section.count('class="exam-parts"')==5 and section.count('<li data-points="5">')==20 and section.count('class="rubric" data-points="5"')==20,'form '+name+' five domains/100-point scoring')
    for anchor in ('administration','diagnostic','form-a','form-b','practical','oral-transfer','retention','coverage','economics-core-synthesis'):
        need(anchor in parser.ids,'required assessment anchor '+anchor)
    downloads=[x for x in parser.links if x.startswith('economics-core-')]
    need(len(downloads)==4 and all('/' not in x and (PROJECT/x).is_file() for x in downloads),'four flat download links')
    source_records=json.loads((BOOK/'content/reviews/economics-core-sources.json').read_text())
    need({x['id'] for x in source_records}==set(parser.sources) and len(source_records)==10,'scoped source IDs')
    need(all(set(s)=={'id','title','url','use','checked','verification'} and s['id'].startswith('economics-core-') and 'Reuse' in s['verification'] for s in source_records),'honest source-reuse contract')
    need('−2/3 twice, 0 eight times, 2/3 twice' in manuscript,'published exact pilot frequency table')
    need('Their sum is 210+closing NFA' in manuscript,'full terminal resource ledger supplied')
    done('Full manuscript structure, matching point totals, flat assets and source-reuse records',written_points=200,forms=2)
    with tempfile.TemporaryDirectory(prefix='economics-core-check-') as temp:
        destination=Path(temp)/'lab';destination.mkdir()
        for filename in ('economics-core-analysis.py','economics-core-inputs.json'):
            shutil.copyfile(PROJECT/filename,destination/filename)
        for flags in ([],['-O']):
            run=subprocess.run([sys.executable,*flags,str(destination/'economics-core-analysis.py')],cwd=temp,capture_output=True,text=True,check=False)
            need(run.returncode==0 and not run.stderr and json.loads(run.stdout)==output,'portable normal/optimized CLI')
        invalid_path=destination/'invalid.json';invalid_path.write_text(json.dumps(invalid[0]))
        run=subprocess.run([sys.executable,'-O',str(destination/'economics-core-analysis.py'),str(invalid_path)],cwd=temp,capture_output=True,text=True,check=False)
        need(run.returncode!=0 and not run.stdout and 'unit/model contract' in run.stderr,'invalid CLI fails explicitly')
    done('Portable normal/optimized lab CLI and quiet JSON API')
    report={'assessment':'economics-core','status':'pass','checks':checks,'results':render(results),'limitations':['Exact original synthetic models and finite assignment laws, not empirical national-policy estimates.','Finite parameter/path checks supplement the manuscript global certificates and do not prove all economic models.','Source methods are reused within recorded accepted-chapter inspection scopes; no new whole-source audit is claimed.','No browser/mobile/print visual QA, independent human grading or institutionally calibrated timing.']}
    json.dumps(report,allow_nan=False)
    return report


if __name__=='__main__':
    print(json.dumps(check(),indent=2,allow_nan=False))
