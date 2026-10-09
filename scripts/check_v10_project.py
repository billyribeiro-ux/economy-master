"""Independent author checks for the original Alder Volume 10 project."""
from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from io import StringIO
from itertools import product
import json
import math
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT/'content/projects'


def require(test,label):
    if not test:raise AssertionError(label)


class Audit:
    def __init__(self):self.comparisons=0;self.rejections=0;self.interventions=0;self.policies=0
    def eq(self,x,y,label):
        self.comparisons+=1;require(x==y,label+': '+repr(x)+' != '+repr(y))
    def near(self,x,y,label,tol=2e-9):
        self.comparisons+=1;require(math.isfinite(float(x)) and abs(float(x)-float(y))<=tol,label+': '+repr(x)+' != '+repr(y))
    def true(self,test,label):self.comparisons+=1;require(test,label)


def solve(matrix,rhs):
    a=[[F(x) for x in row]+[F(y)] for row,y in zip(matrix,rhs)]
    for col in range(len(rhs)):
        pivot=next(i for i in range(col,len(rhs)) if a[i][col])
        a[col],a[pivot]=a[pivot],a[col]
        scale=a[col][col];a[col]=[x/scale for x in a[col]]
        for i in range(len(rhs)):
            if i!=col:
                scale=a[i][col];a[i]=[x-scale*y for x,y in zip(a[i],a[col])]
    return [row[-1] for row in a]


def adaptive(f,left,right,tol=1e-11):
    if right<=left:return 0.0
    middle=(left+right)/2
    fa,fm,fb=f(left),f(middle),f(right)
    initial=(right-left)*(fa+4*fm+fb)/6
    def refine(a,b,fa,fm,fb,whole,eps,depth):
        m=(a+b)/2;l=(a+m)/2;r=(m+b)/2
        fl,fr=f(l),f(r)
        first=(m-a)*(fa+4*fl+fm)/6;second=(b-m)*(fm+4*fr+fb)/6
        diff=first+second-whole
        if depth==0 or abs(diff)<15*eps:return first+second+diff/15
        return refine(a,m,fa,fl,fm,first,eps/2,depth-1)+refine(m,b,fm,fr,fb,second,eps/2,depth-1)
    return refine(left,right,fa,fm,fb,initial,tol,20)


def ideal_moments(s,k,r,sigma,t,beta):
    d=math.exp(-r*t);vol=sigma*math.sqrt(t);mu=(r-sigma*sigma/2)*t
    cutoff=(math.log(k/s)-mu)/vol
    density=lambda z:math.exp(-z*z/2)/math.sqrt(2*math.pi)
    stock=lambda z:s*math.exp(mu+vol*z)
    put=lambda z:d*max(k-stock(z),0.0)
    def integral(fun):
        knots=sorted(set([-10.0,10.0]+[x for x in (cutoff,-cutoff) if -10<x<10]))
        return math.fsum(adaptive(lambda z:fun(z)*density(z),a,b) for a,b in zip(knots,knots[1:]))
    mean=integral(put);second=integral(lambda z:put(z)**2)
    cross=integral(lambda z:put(z)*d*stock(z));pair_second=integral(lambda z:((put(z)+put(-z))/2)**2)
    var=second-mean*mean;varx=s*s*math.expm1(sigma*sigma*t);cov=cross-mean*s
    return {'mean':mean,'variance':var,'covariance':cov,'control_variance':var+beta*beta*varx-2*beta*cov,'pair_variance':pair_second-mean*mean}


def put_delta(s,k,r,sigma,t):
    # Differentiating the normal payoff integral: -Phi(kappa - sigma sqrt(t)).
    z=(math.log(k/s)-(r-sigma*sigma/2)*t)/(sigma*math.sqrt(t))-sigma*math.sqrt(t)
    return -.5*(1+math.erf(z/math.sqrt(2)))


def independent_normals(seed,count):
    result=[]
    for i in range(count):
        digest=sha256(('alder-project-v1|%d|%d'%(seed,i)).encode()).hexdigest()
        u=math.ldexp(int(digest[:13],16)+.5,-52)
        v=math.ldexp(int(digest[16:29],16)+.5,-52)
        radius=math.sqrt(-math.log(u)*2)
        result.append((radius*math.cos(v*(2*math.pi)),radius*math.sin(v*(2*math.pi))))
    return result


def online(values):
    n=0;mean=0.0;squared=0.0
    for value in values:
        n+=1;delta=value-mean;mean+=delta/n;squared+=delta*(value-mean)
    return n,mean,squared/(n-1)


def all_policies(s,k,u,d,p,growth,n,allowed,depth=0):
    immediate=max(k-s,0.0)
    if depth==n:return [immediate]
    down=all_policies(s*d,k,u,d,p,growth,n,allowed,depth+1)
    up=all_policies(s*u,k,u,d,p,growth,n,allowed,depth+1)
    choices=[((1-p)*low+p*high)/growth for low,high in product(down,up)]
    return ([immediate]+choices) if depth in allowed else choices


def validate_finance(a,data,out,label,full_mc=True,stopping=False):
    times=list(map(F,data['curve']['times']));ins=data['curve']['instruments']
    ds=solve([row['cash'] for row in ins],[row['price'] for row in ins])
    cash=list(map(F,data['liability']['coupons']));cash[-1]+=F(data['liability']['face'])
    pv=sum(x*y for x,y in zip(cash,ds));expo=[t*c*d for t,c,d in zip(times,cash,ds)]
    a.eq(list(map(F,out['bond']['discounts'])),ds,label+' independent simultaneous bootstrap')
    a.eq(F(out['bond']['pv']),pv,label+' dated PV')
    a.eq(list(map(F,out['bond']['key_rate_dollar_exposures'])),expo,label+' key derivative')
    a.eq(F(out['bond']['parallel_dollar_duration']),sum(expo),label+' parallel derivative')
    a.eq(F(out['bond']['parallel_second_derivative']),sum(t*x for t,x in zip(times,expo)),label+' convexity')
    barbell=solve([[ds[0],ds[-1]],[times[0]*ds[0],times[-1]*ds[-1]]],[pv,sum(expo)])
    hedge=[barbell[0],F(0),barbell[1]]
    a.eq(list(map(F,out['bond']['barbell_zero_quantities'])),hedge,label+' independent two-equation barbell')
    gap=[h-c for h,c in zip(hedge,cash)]
    a.eq(sum(g*d for g,d in zip(gap,ds)),F(0),label+' barbell PV neutrality')
    a.eq(sum(g*d*t for g,d,t in zip(gap,ds,times)),F(0),label+' barbell parallel neutrality')
    for row,result in zip(data['curve']['shocks'],out['bond']['shocks']):
        shifts=list(map(F,row['zero_shifts']))
        changed=[float(d)*math.exp(-float(t*z)) for d,t,z in zip(ds,times,shifts)]
        a.near(result['barbell_minus_liability'],math.fsum(float(g)*d for g,d in zip(gap,changed)),label+' direct shocked residual',3e-8)
        a.near(result['first_order_residual'],float(-sum(g*t*d*z for g,t,d,z in zip(gap,times,ds,shifts))),label+' directional first derivative')
        remainder=math.fsum(abs(float(g*d))*math.exp(abs(float(t*z)))*abs(float(t*z))**3/6 for g,d,t,z in zip(gap,ds,times,shifts))
        a.true(abs(result['barbell_minus_liability']-result['second_order_residual'])<=remainder+3e-10,label+' exponential Taylor remainder bound')
    o=data['option'];s,k,sigma=[float(F(o[key])) for key in ('spot','strike','sigma')]
    t=float(times[0]);r=-math.log(float(ds[0]))/t;analytic=out['option']['analytic']
    a.near(analytic['call']-analytic['put'],s-k*float(ds[0]),label+' put-call parity')
    a.near(analytic['put_delta'],put_delta(s,k,r,sigma,t),label+' differentiated-integral delta')
    for grid in out['option']['trees']:
        n=grid['steps'];dt=t/n;u=math.exp(sigma*math.sqrt(dt));d=1/u;growth=math.exp(r*dt);p=(growth-d)/(u-d)
        terminal=math.fsum(math.comb(n,j)*p**j*(1-p)**(n-j)*max(k-s*u**j*d**(n-j),0.0) for j in range(n+1))*float(ds[0])
        a.near(grid['european']['price'],terminal,label+' terminal binomial sum')
        a.true(grid['european']['price']<=grid['bermudan']['price']+1e-10<=grid['american']['price']+2e-10,label+' same-tree exercise-rights ordering')
        h=grid['european']['root_continuation_hedge'];delta=h['stock_units'];bank=h['initial_bank']
        a.near(delta*s+bank,terminal,label+' funded root portfolio')
        a.near(delta*s*u+bank*growth,h['up_value'],label+' up replication')
        a.near(delta*s*d+bank*growth,h['down_value'],label+' down replication')
    if stopping and data['option']['tree_steps'][0]==4:
        n=4;dt=t/n;u=math.exp(sigma*math.sqrt(dt));d=1/u;growth=math.exp(r*dt);p=(growth-d)/(u-d)
        for typ,allowed in (('bermudan',{int(F(x)*n) for x in o['bermudan_fractions']}),('american',set(range(n)))):
            choices=all_policies(s,k,u,d,p,growth,n,allowed)
            a.near(max(choices),out['option']['trees'][0][typ]['price'],label+' exhaustive full-history '+typ)
            a.policies+=len(choices)
    cr=data['credit_reserve'];q=F(cr['pricing_default_probability']);face=F(data['liability']['face'])
    dc=[(cash[i] if i<cr['default_index'] else F(0))+(face*F(cr['recovery_fraction']) if i==cr['settlement_index'] else 0) for i in range(3)]
    dp=sum(c*d for c,d in zip(dc,ds));credit=out['credit_reserve']
    a.eq(list(map(F,credit['default_cash'])),dc,label+' contractual default cash')
    a.eq(F(credit['default_pv']),dp,label+' actual-date recovery discount')
    a.eq(F(credit['risky_reserve_pv']),pv+q*(dp-pv),label+' pricing-mixture PV')
    a.eq(F(credit['apparent_initial_saving']),q*(pv-dp),label+' price discount is expected Q loss')
    discounted_balance=F(0);coverage=True
    for i,row in enumerate(credit['default_funding_ledger']):
        discounted_balance+=(dc[i]-cash[i])*ds[i]
        a.eq(F(row['bank_after_payment']),discounted_balance/ds[i],label+' cumulative discounted funding oracle')
        coverage=coverage and discounted_balance>=0
    a.eq(credit['funds_all_declared_dates_without_injection'],coverage,label+' dated coverage')
    a.eq(F(credit['default_terminal_bank']),(dp-pv)/ds[-1],label+' terminal borrowing identity')
    ht=[float(F(x)) for x in data['hedge']['times']]
    for path,result in zip(data['hedge']['paths'],out['hedge']['paths']):
        spots=[float(F(x)) for x in path['spots']]
        deltas=[put_delta(x,k,r,sigma,t-date) for x,date in zip(spots[:-1],ht[:-1])]+[0.0]
        dg=math.fsum(deltas[i-1]*(math.exp(-r*ht[i])*spots[i]-math.exp(-r*ht[i-1])*spots[i-1]) for i in range(1,len(ht)))
        zero=(analytic['put']+dg-float(ds[0])*max(k-spots[-1],0))/float(ds[0])
        previous=0.0;pv_cost=0.0
        for i in range(len(ht)):
            pv_cost+=math.exp(-r*ht[i])*float(F(data['hedge']['cost_rate']))*abs(deltas[i]-previous)*spots[i]
            previous=deltas[i]
        a.near(result['frictionless']['terminal_error'],zero,label+' discounted stochastic-gain sum')
        a.near(result['with_costs']['terminal_error'],zero-pv_cost/float(ds[0]),label+' funded costs identity')
        a.near(result['with_costs']['present_transaction_costs'],pv_cost,label+' independently timed costs')
        a.near(result['cost_attribution_residual'],0,label+' no hidden injections')
        for ledger in (result['frictionless']['ledger'],result['with_costs']['ledger']):
            for row in ledger:
                a.near(row['bank_after_trade'],row['bank_before_trade']-row['stock_trade_cash']-row['transaction_cost'],label+' every trade is funded')
    budget=float(F(data['decision']['max_tested_terminal_loss']))
    worst=min(x['with_costs']['terminal_error'] for x in out['hedge']['paths'])
    buffer=max(0,-worst-budget)*float(ds[0]);dec=out['decision']
    a.near(dec['additional_initial_cash_for_tested_loss_budget'],buffer,label+' tested-path capital amount')
    selected=pv if data['decision']['requested_reserve']=='matched_zeros' else pv+q*(dp-pv)
    reserve_budget=max(pv,selected)
    a.eq(F(dec['selected_reserve_pv']),selected,label+' actual selected reserve purchase cost')
    a.eq(F(dec['reserve_budget_pv']),reserve_budget,label+' conservative reserve budget includes selected premium')
    a.near(dec['quote_with_tested_buffer'],float(reserve_budget)+analytic['put']+buffer,label+' fully funded reserve and hedge quote')
    a.eq(dec['failed_gates'],[key for key,value in dec['gates'].items() if not value],label+' every failed gate reported')
    if full_mc:
        beta=float(F(o['control_beta']));plain=[];control=[];pairs=[];stocks=[]
        for z,w in independent_normals(o['seed'],o['mc_pairs']):
            obs=[]
            for normal in (z,w,-z):
                stock=s*math.exp((r-.5*sigma*sigma)*t+sigma*math.sqrt(t)*normal)
                obs.append((float(ds[0])*max(k-stock,0.0),float(ds[0])*stock))
            for y,x in obs[:2]:plain.append(y);control.append(y-beta*(x-s));stocks.append(x)
            pairs.append((obs[0][0]+obs[2][0])/2)
        for typ,values in (('plain',plain),('controlled',control),('antithetic',pairs),('discounted_stock',stocks)):
            n,mean,var=online(values);actual=out['option']['monte_carlo'][typ]
            a.eq(actual['units'],n,label+' MC independent sample units')
            a.near(actual['mean'],mean,label+' seed-exact independent MC mean')
            a.near(actual['sample_variance'],var,label+' Welford variance',5e-8)
            a.near(actual['estimated_se'],math.sqrt(var/n),label+' sample-unit SE')
            a.near(actual['approximate_95_interval'][1]-mean,1.96*math.sqrt(var/n),label+' approximate interval')
    return ds,pv


class Fragment(HTMLParser):
    def __init__(self):super().__init__();self.stack=[];self.ids=[];self.hrefs=[];self.points=[]
    def handle_starttag(self,tag,attrs):
        d=dict(attrs);require(tag not in ('html','head','body','script','h1'),'HTML fragment required')
        if 'id' in d:self.ids.append(d['id'])
        if 'href' in d:self.hrefs.append(d['href'])
        if 'data-points' in d:self.points.append(int(d['data-points']))
        if tag not in ('br','hr','img','meta','input','link'):self.stack.append(tag)
    def handle_endtag(self,tag):require(self.stack and self.stack[-1]==tag,'unbalanced '+tag);self.stack.pop()


def check():
    for required in ('content/assessments/parts/v10-project.html',
                     'content/projects/v10-assessment-inputs.json','content/projects/v10-assessment-analysis.py',
                     'content/projects/v10-assessment-output.json','content/projects/v10-assessment-manifest.json',
                     'content/projects/v10-assessment-README.txt','content/reviews/v10-project-sources.json',
                     'content/reviews/v10-project-author.json'):
        require((ROOT/required).is_file(),'missing required project payload: '+required)
    a=Audit();original=json.loads((ASSETS/'v10-assessment-inputs.json').read_text());saved=deepcopy(original)
    stream=StringIO()
    with redirect_stdout(stream),redirect_stderr(stream):
        model=runpy.run_path(str(ASSETS/'v10-assessment-analysis.py'));out=model['run'](original)
    a.eq(stream.getvalue(),'','quiet import and run');a.eq(original,saved,'input not mutated')
    a.eq(out,json.loads((ASSETS/'v10-assessment-output.json').read_text()),'complete baseline reproduction')
    validate_finance(a,original,out,'base',stopping=True)
    o=original['option'];r=out['option']['first_segment_rate']
    ideal=ideal_moments(100,105,r,.25,.5,-.5)
    a.near(out['option']['analytic']['put'],ideal['mean'],'independent adaptive normal payoff integration',3e-10)
    a.near(ideal['mean'],8.6883020350176,'published teaching price',3e-10)
    a.near(ideal['variance'],106.4634569120,'independent ideal plain variance',3e-8)
    a.true(ideal['control_variance']<ideal['variance'],'fixed negative put control ideal reduction')
    a.true(2*ideal['pair_variance']<ideal['variance'],'equal-payoff-evaluation ideal antithetic reduction')
    a.near(out['option']['quadrature']['fine'],ideal['mean'],'model deterministic integration',3e-8)
    step=1e-3
    plus=ideal_moments(100+step,105,r,.25,.5,-.5)['mean'];minus=ideal_moments(100-step,105,r,.25,.5,-.5)['mean']
    a.near((plus-minus)/(2*step),out['option']['analytic']['put_delta'],'finite-difference delta from payoff integral',2e-8)
    a.near((plus+minus-2*ideal['mean'])/step**2,out['option']['analytic']['gamma'],'finite-difference gamma from payoff integral',4e-7)
    a.eq(out['credit_reserve']['default_terminal_bank'],'-6018/91','baseline dated deficit with bridge interest')
    a.eq(out['decision']['failed_gates'],['reserve_funds_all_declared_dates','quote_covers_tested_loss_budget'],'baseline refusal')
    variants=[]
    def change(label,fn):
        data=deepcopy(original);data['option']['mc_pairs']=64;fn(data);variants.append((label,data))
    change('third bootstrap quote',lambda x:x['curve']['instruments'][2].update(price='96.7'))
    change('middle zero shock',lambda x:x['curve']['shocks'][0].update(zero_shifts=['0','.02','0']))
    def negative(x):
        for row,quote in zip(x['curve']['instruments'],('102','105.03','100.92')):row['price']=quote
    change('negative first-segment rates',negative)
    change('zero coupon liability',lambda x:x['liability'].update(coupons=['0','0','0']))
    change('immediate recovery',lambda x:x['credit_reserve'].update(settlement_index=1))
    change('early default',lambda x:x['credit_reserve'].update(default_index=0))
    change('full face recovery',lambda x:x['credit_reserve'].update(recovery_fraction='1'))
    change('zero recovery',lambda x:x['credit_reserve'].update(recovery_fraction='0'))
    change('double pricing default probability',lambda x:x['credit_reserve'].update(pricing_default_probability='.2'))
    change('double trading costs',lambda x:x['hedge'].update(cost_rate='.002'))
    change('zero trading costs',lambda x:x['hedge'].update(cost_rate='0'))
    def terminal(x):
        x['hedge']['times']=['0','1/2']
        for path in x['hedge']['paths']:path['spots']=[path['spots'][0],path['spots'][-1]]
    change('terminal-only hedge',terminal)
    change('same terminal spot calmer history',lambda x:x['hedge']['paths'][2].update(spots=['100','100','100','100','90']))
    change('coarse integration',lambda x:x['option'].update(quadrature_steps=32))
    change('new deterministic seed',lambda x:x['option'].update(seed=0))
    change('wrong-sign fixed control',lambda x:x['option'].update(control_beta='1'))
    change('requested American rights',lambda x:x['decision'].update(requested_exercise='american'))
    def repair(x):
        x['option']['mc_pairs']=2048;x['decision'].update(requested_reserve='matched_zeros',requested_quote='119')
    change('limited demonstration repair',repair)
    change('changed volatility',lambda x:x['option'].update(sigma='.35'))
    results={}
    for label,data in variants:
        result=model['run'](data);validate_finance(a,data,result,label,stopping=label in ('negative first-segment rates','changed volatility'))
        a.interventions+=1;results[label]=result
    a.eq(results['immediate recovery']['credit_reserve']['default_terminal_bank'],'-5858/91','recovery date transfer terminal deficit')
    a.eq(F(results['immediate recovery']['credit_reserve']['risky_reserve_pv'])-F(out['credit_reserve']['risky_reserve_pv']),F(4,25),'expected recovery-date PV transfer')
    a.eq(results['full face recovery']['credit_reserve']['funds_all_declared_dates_without_injection'],False,'full face recovery omits coupons')
    a.eq(results['limited demonstration repair']['decision']['recommendation'],'eligible_for_limited_demonstration','all stated repairs, limited scope')
    a.eq(results['requested American rights']['decision']['gates']['exercise_matches_european_reference'],False,'different rights cannot pass European reference')
    a.near(results['same terminal spot calmer history']['hedge']['paths'][2]['with_costs']['terminal_error'],1.6774453490783,'same payoff different hedge history')
    a.near(results['terminal-only hedge']['hedge']['paths'][2]['with_costs']['terminal_error'],.13630551453564,'terminal-only hedge transfer')
    a.eq((F(3009,500)-F(3009,50))/F(91,100),F(-27081,455),'retaining expected-loss saving still leaves default deficit')
    a.eq(F(3)*(F(95,91)-1),F(12,91),'dated riskfree bridge interest')
    a.near(3*95/91*math.expm1(.02*.5),.031475798010856,'two hundred basis-point borrowing-spread transfer')
    for i,path in enumerate(out['hedge']['paths']):
        doubled=results['double trading costs']['hedge']['paths'][i]
        a.near(doubled['with_costs']['terminalized_transaction_costs'],2*path['with_costs']['terminalized_transaction_costs'],'cost doubling with unchanged strategy')
    # Focused regression: early full-face recovery can cost MORE than the fixed promise.
    # Future/default-only excess cannot purchase the reserve at time zero or fund
    # the hedge in survival. Reconstruct the two dated costs without model helpers.
    expensive=deepcopy(original)
    expensive['liability']['coupons']=['0','0','0']
    expensive['credit_reserve'].update(default_index=0,settlement_index=0,recovery_fraction='1')
    riskless=100*F(91,100)
    risky=F(9,10)*riskless+F(1,10)*100*F(49,50)
    a.eq((riskless,risky,riskless-risky),(F(91),F(917,10),F(-7,10)),'early recovery selected-reserve premium')
    for reserve,quote,passes in (('risky_bond','110.5',False),
                                 ('risky_bond','111.12487009',False),
                                 ('risky_bond','111.12487010',True),
                                 ('matched_zeros','110.5',True)):
        changed=deepcopy(expensive)
        changed['decision'].update(requested_reserve=reserve,requested_quote=quote)
        result=model['run'](changed);decision=result['decision'];a.interventions+=1
        selected=risky if reserve=='risky_bond' else riskless
        a.eq(F(decision['selected_reserve_pv']),selected,'repair selected purchase cost')
        a.eq(F(decision['reserve_budget_pv']),selected,'repair budget uses cost above floor')
        required=float(selected)+out['option']['analytic']['put']+out['decision']['additional_initial_cash_for_tested_loss_budget']
        a.near(decision['quote_with_tested_buffer'],required,'repair independent initial-cash requirement')
        a.eq(decision['gates']['quote_covers_tested_loss_budget'],passes,'repair eight-decimal funding boundary')
        a.true(all(value for key,value in decision['gates'].items() if key!='quote_covers_tested_loss_budget'),'repair leaves other four gates satisfied')
        a.eq(decision['failed_gates'],[] if passes else ['quote_covers_tested_loss_budget'],'repair sole funding failure')
        a.eq(decision['recommendation'],'eligible_for_limited_demonstration' if passes else 'revise_before_demo','repair honest recommendation')
    a.eq((F(out['decision']['selected_reserve_pv']),F(out['decision']['reserve_budget_pv'])),
         (F(46751,500),F(2488,25)),'baseline expected saving does not reduce conservative floor')
    invalid=[]
    def bad(path,value):
        data=deepcopy(original);target=data
        for key in path[:-1]:target=target[key]
        target[path[-1]]=value;invalid.append(data)
    for value in (100,True,None,float('nan'),float('inf'),'NaN','+100','0100','100e0','1/0','1/-1','1/01',' 100','100 ','1'*100):bad(('option','spot'),value)
    for path,value in (
        (('schema',),'bad'),(('provenance',),'real observations'),(('curve','times'),['1','1','2']),
        (('curve','times'),['1/100','1','2']),(('curve','times'),['2','3','4']),
        (('curve','instruments',0,'cash'),['100','1','0']),(('curve','instruments',1,'cash'),['3','0','0']),
        (('curve','instruments',0,'price'),'10'),(('curve','instruments',0,'price'),'111'),
        (('curve','shocks',0,'zero_shifts'),['.06','0','0']),(('liability','face'),'0'),(('liability','coupons'),['3','-1','3']),
        (('option','strike'),'10'),(('option','sigma'),'0'),(('option','sigma'),'1'),
        (('option','tree_steps'),[4,3]),(('option','tree_steps'),[8,4]),(('option','tree_steps'),[4,4]),
        (('option','bermudan_fractions'),['1/3']),(('option','bermudan_fractions'),['1']),
        (('option','bermudan_fractions'),['1/2','0']),(('option','mc_pairs'),True),(('option','mc_pairs'),63),
        (('option','mc_pairs'),4097),(('option','seed'),-1),(('option','seed'),2**32),
        (('option','control_beta'),'3'),(('option','quadrature_steps'),33),(('hedge','times'),['0','1/4']),
        (('hedge','times'),['0','1/100','1/4','3/8','1/2']),(('hedge','cost_rate'),'-.01'),
        (('hedge','paths',0,'spots'),['99','102','104','106','108']),
        (('hedge','paths',0,'spots'),['100','102','104','106','151']),
        (('credit_reserve','pricing_default_probability'),'0'),(('credit_reserve','pricing_default_probability'),'1'),
        (('credit_reserve','default_index'),True),(('credit_reserve','settlement_index'),0),
        (('credit_reserve','recovery_fraction'),'1.1'),(('decision','requested_exercise'),'anytime'),
        (('decision','requested_reserve'),'cashless'),(('decision','requested_quote'),'-1'),
        (('decision','max_mc_standard_error'),'0'),(('decision','max_tree_abs_error'),'0')):bad(path,value)
    bad(('hedge','paths',0,'id'),'Bad Name');bad(('hedge','paths',1,'id'),'steady_rise')
    data=deepcopy(original);data['liability']['extra']=1;invalid.append(data)
    data=deepcopy(original);del data['option'];invalid.append(data)
    invalid.extend([None,[],True])
    for i,data in enumerate(invalid):
        try:model['run'](data)
        except ValueError:a.rejections+=1
        else:raise AssertionError('invalid input accepted '+str(i))
    with tempfile.TemporaryDirectory(prefix='v10-project-check-') as temporary:
        folder=Path(temporary)
        for file in ('v10-assessment-analysis.py','v10-assessment-inputs.json'):shutil.copy2(ASSETS/file,folder/file)
        for optimized in (False,True):
            command=[sys.executable]+(['-O'] if optimized else [])
            explicit=subprocess.run(command+[str(folder/'v10-assessment-analysis.py'),'--input',str(folder/'v10-assessment-inputs.json'),'--output',str(folder/'result.json')],cwd=folder,capture_output=True,text=True,timeout=15)
            a.eq((explicit.returncode,explicit.stdout,explicit.stderr),(0,'',''),'portable quiet explicit CLI')
            a.eq(json.loads((folder/'result.json').read_text()),out,'portable full output')
            default=subprocess.run(command+[str(folder/'v10-assessment-analysis.py')],cwd=folder,capture_output=True,text=True,timeout=15)
            a.eq(default.returncode,0,'default script-relative CLI');a.eq(default.stderr,'','default stderr')
            a.eq(json.loads(default.stdout),out,'default full output')
            api="import contextlib,io,json,runpy; b=io.StringIO();\nwith contextlib.redirect_stdout(b),contextlib.redirect_stderr(b):\n m=runpy.run_path('v10-assessment-analysis.py');d=json.load(open('v10-assessment-inputs.json')); old=json.dumps(d,sort_keys=True);r=m['run'](d)\nif b.getvalue() or json.dumps(d,sort_keys=True)!=old:raise RuntimeError('noise or mutation')\nprint(json.dumps(r,allow_nan=False))"
            result=subprocess.run(command+['-c',api],cwd=folder,capture_output=True,text=True,timeout=15)
            a.eq((result.returncode,result.stderr),(0,''),'normal/optimized quiet portable API');a.eq(json.loads(result.stdout),out,'portable API output')
            for malformed in ('{','{"schema":1,"schema":2}','{"schema":NaN}','{"schema":Infinity}','{"schema":-Infinity}',json.dumps(invalid[0])):
                (folder/'bad.json').write_text(malformed);(folder/'sentinel.json').write_text('preserve')
                failure=subprocess.run(command+[str(folder/'v10-assessment-analysis.py'),'--input',str(folder/'bad.json'),'--output',str(folder/'sentinel.json')],cwd=folder,capture_output=True,text=True,timeout=10)
                require(failure.returncode!=0 and (folder/'sentinel.json').read_text()=='preserve','invalid CLI replaced output');a.rejections+=1
    chapter=ROOT/'content/assessments/parts/v10-project.html'
    if chapter.exists():
        doc=Fragment();doc.feed(chapter.read_text());a.eq(doc.stack,[],'balanced project fragment')
        a.eq(sum(doc.points),100,'rubric totals100');a.eq(len(doc.points),5,'five essential domains')
        a.eq(len(doc.ids),len(set(doc.ids)),'unique project IDs')
        a.true('project' in doc.ids and all(i=='project' or i.startswith('v10-project-') for i in doc.ids),'project-scoped IDs')
        for filename in ('v10-assessment-inputs.json','v10-assessment-analysis.py','v10-assessment-output.json','v10-assessment-manifest.json','v10-assessment-README.txt'):a.true(filename in doc.hrefs,'flat downloadable '+filename)
    manifest=ASSETS/'v10-assessment-manifest.json'
    if manifest.exists():
        entries=json.loads(manifest.read_text())['files'];a.eq(len(entries),4,'four project payload bindings')
        for row in entries:
            payload=(ASSETS/row['file']).read_bytes();a.eq((len(payload),sha256(payload).hexdigest()),(row['bytes'],row['sha256']),'project payload hash')
    author=ROOT/'content/reviews/v10-project-author.json'
    if author.exists():
        entries=json.loads(author.read_text())['reviewed_hashes'];a.eq(len(entries),8,'eight nonself author bindings')
        for row in entries:
            payload=(ROOT/row['path']).read_bytes();a.eq((len(payload),sha256(payload).hexdigest()),(row['bytes'],row['sha256']),'author payload binding')
    return {'project':'v10','status':'passed','comparisons':a.comparisons,'invalid_inputs_rejected':a.rejections,
            'financial_interventions':a.interventions,'full_history_stopping_policies':a.policies,
            'independent_ideal_moments':ideal,'limits':'Author verification using independent numerical oracles; separate peer/coordinator, empirical validation and whole-edition visual QA remain separate.'}


if __name__=='__main__':print(json.dumps(check(),indent=2,allow_nan=False))
