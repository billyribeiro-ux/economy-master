#!/usr/bin/env python3
"""Independent Fenwick credit/recovery checks. Import and check() are quiet."""
import contextlib
import copy
from fractions import Fraction as F
import hashlib
from html.parser import HTMLParser
import importlib.util
import io
import itertools
import json
from math import exp, isclose, log, sqrt
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
ASSETS=ROOT/'content/projects'
PREFIX='v10-c04-'


def require(ok,message):
    if not ok:raise AssertionError(message)


def read(path):
    def invalid(value):raise ValueError('nonfinite JSON: '+value)
    return json.loads(path.read_text(),parse_constant=invalid)


class Audit:
    def __init__(self):self.comparisons=0;self.groups=[];self.rejections=0
    def eq(self,actual,expected,label):
        self.comparisons+=1
        if isinstance(expected,F):require(isinstance(actual,str) and F(actual)==expected,label)
        elif isinstance(expected,float):require(isinstance(actual,(int,float)) and not isinstance(actual,bool) and isclose(actual,expected,rel_tol=1e-10,abs_tol=1e-10),label)
        else:require(actual==expected,label)
    def add(self,name):self.groups.append(name)


def product(values):
    x=F(1)
    for v in values:x*=v
    return x


def structural_expected(inp):
    f=F(inp['face']);D=F(inp['discount']);cost=F(inp['workout_asset_fraction'])
    result=[]
    for v,p,q in zip(inp['asset_values'],inp['physical_probabilities'],inp['pricing_probabilities']):
        v,p,q=map(F,[v,p,q]);loss=cost*v if v<f else F(0)
        result.append({'asset':v,'physical_probability':p,'pricing_probability':q,'state_price':D*q,
                       'default':v<f,'workout_cost':loss,'debt_payoff':min(v,f)-loss,
                       'equity_payoff':max(F(0),v-f),'claim_sum':v-loss})
    return result


def event_price(inp):
    # Enumerate mutually exclusive default-year or complete-survival paths.
    f=F(inp['face']);c=F(inp['coupon_amount']);R=F(inp['recovery_fraction'])
    hs=list(map(F,inp['pricing_hazards']));ds=list(map(F,inp['discount_factors']));n=len(hs)
    total=F(0);delayed=F(0);events=[]
    for default in range(n+1):
        probability=product([1-h for h in hs[:default]])*(hs[default] if default<n else 1)
        cash=[c if k<default else F(0) for k in range(n)]
        late=cash[:]
        if default<n:cash[default]+=R*f;late[-1]+=R*f
        else:cash[-1]+=f;late[-1]+=f
        total+=probability*sum(x*d for x,d in zip(cash,ds))
        delayed+=probability*sum(x*d for x,d in zip(late,ds))
        events.append((probability,cash,late))
    return total,delayed,events


def migration_enum(inp,measure):
    M=[[F(x) for x in row] for row in inp[measure+'_matrix']]
    ds=list(map(F,inp['discount_factors']));n=len(ds);start=inp['states'].index(inp['initial_state'])
    f=F(inp['face']);recovery=f*F(inp['recovery_fraction']);dist=[[F(0)]*3 for _ in range(n)]
    price=F(0);first=[F(0)]*n
    for path in itertools.product(range(3),repeat=n):
        full=(start,)+path
        p=product(M[full[k]][full[k+1]] for k in range(n))
        for k,state in enumerate(path):dist[k][state]+=p
        if 2 in path:
            k=path.index(2);first[k]+=p;price+=p*recovery*ds[k]
        else:price+=p*f*ds[-1]
    return dist,first,price


def simpson(fn,a,b,n=1000):
    h=(b-a)/n
    return h*(fn(a)+fn(b)+sum((4 if i%2 else 2)*fn(a+i*h) for i in range(1,n)))/3


class Structure(HTMLParser):
    def __init__(self):super().__init__();self.ids=[];self.h1=0;self.worked=0;self.exercises=0;self.solutions=0;self.stack=[];self.links=[];self.words=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs);self.stack.append((tag,a))
        if 'id' in a:self.ids.append(a['id'])
        if tag=='h1':self.h1+=1
        if tag=='a':self.links.append(a.get('href',''))
        if tag=='aside' and 'worked' in a.get('class','').split():self.worked+=1
        if tag=='li' and len(self.stack)>1:
            parent,pa=self.stack[-2]
            if parent=='ol' and 'exercises' in pa.get('class','').split():self.exercises+=1
            if parent=='ol' and any(t=='details' and 'solutions' in at.get('class','').split() for t,at in self.stack):self.solutions+=1
        if tag in ['br','hr','img','input','meta','link','wbr']:self.stack.pop()
    def handle_endtag(self,tag):
        for i in range(len(self.stack)-1,-1,-1):
            if self.stack[i][0]==tag:self.stack=self.stack[:i];break
    def handle_data(self,data):self.words.extend(data.split())


def check():
    a=Audit();data=read(ASSETS/(PREFIX+'inputs.json'));reference=read(ASSETS/(PREFIX+'output.json'))
    spec=importlib.util.spec_from_file_location('fenwick',ASSETS/(PREFIX+'analysis.py'));m=importlib.util.module_from_spec(spec)
    original=copy.deepcopy(data);capture=io.StringIO()
    with contextlib.redirect_stdout(capture),contextlib.redirect_stderr(capture):spec.loader.exec_module(m);result=m.run(data)
    a.eq(capture.getvalue(),'','quiet import/run');a.eq(data,original,'nonmutating run');a.eq(result,reference,'complete strict reference')
    json.dumps(result,allow_nan=False);a.add('quiet API and complete preserved output')

    expected=structural_expected(data['structural']);s=result['structural'];D=F(data['structural']['discount']);f=F(data['structural']['face'])
    for actual,row in zip(s['states'],expected):
        for k,v in row.items():a.eq(actual[k],v,'structural state '+k)
    debt=sum(r['state_price']*r['debt_payoff'] for r in expected);equity=sum(r['state_price']*r['equity_payoff'] for r in expected)
    asset=sum(r['state_price']*r['asset'] for r in expected);receipt=sum(r['physical_probability']*r['debt_payoff'] for r in expected)
    vals={'debt_price':debt,'equity_price':equity,'gross_asset_value':asset,'claim_value':debt+equity,
          'workout_cost_pv':asset-debt-equity,'physical_default_probability':sum(r['physical_probability'] for r in expected if r['default']),
          'pricing_default_probability':sum(r['pricing_probability'] for r in expected if r['default']),
          'physical_expected_debt_receipt':receipt,'physical_expected_face_loss':f-receipt,
          'physical_expected_debt_return':receipt/debt-1,'promised_simple_yield':f/debt-1,'safe_simple_return':1/D-1,
          'continuous_promised_spread_approx':-log(float(debt/(f*D)))}
    for k,v in vals.items():a.eq(s[k],v,'structural aggregate '+k)
    a.add('state-priced claims, resources and physical versus promised return')

    inp=data['scheduled'];price,late,events=event_price(inp);s=result['scheduled']
    a.eq(s['price_end_date_recovery'],price,'independent exclusive-event pricing')
    a.eq(s['price_maturity_recovery'],late,'independent delayed-recovery paths')
    a.eq(s['recovery_timing_value'],price-late,'timing value')
    ds=list(map(F,inp['discount_factors']));hs=list(map(F,inp['pricing_hazards']));times=list(map(F,inp['times']))
    a.eq(s['default_free_promised_price'],6*sum(ds)+100*ds[-1],'matched safe promised schedule')
    for i,row in enumerate(s['pricing_cash_rows']):
        survival=product(1-h for h in hs[:i+1]);default=events[i][0];previous=survival+default
        vals={'opening_survival':previous,'conditional_default':hs[i],'marginal_default':default,'survival':survival,
              'time':times[i],'discount_factor':ds[i],'survival_coupon':6*survival,'recovery_at_interval_end':40*default,
              'survival_principal':100*survival if i==len(ds)-1 else F(0),
              'present_value':sum(p*cash[i]*ds[i] for p,cash,_ in events),
              'equivalent_constant_intensity_on_interval_approx':-log(float(1-hs[i]))/float(times[i]-(times[i-1] if i else 0))}
        for k,v in vals.items():a.eq(row[k],v,'scheduled cash '+str(i)+' '+k)
    ph=list(map(F,inp['physical_hazards']))
    for i,row in enumerate(s['physical_survival']):
        prev=product(1-h for h in ph[:i]);surv=prev*(1-ph[i])
        for k,v in {'opening_survival':prev,'conditional_default':ph[i],'marginal_default':prev-surv,'survival':surv}.items():a.eq(row[k],v,'physical survival '+k)
    a.add('first-default event enumeration and complete dated recovery ledger')

    inp=data['continuous'];f,T,r,lp,lq,R=[float(F(inp[k])) for k in ['face','maturity','short_rate','physical_intensity','pricing_intensity','recovery_fraction']]
    survival=f*exp(-r*T)*exp(-lq*T)
    recovery=simpson(lambda t:f*R*exp(-r*t)*lq*exp(-lq*t),0,T)
    immediate=survival+recovery;delayed=f*exp(-r*T)*(1-(1-R)*(1-exp(-lq*T)));market=f*exp(-(r+lq*(1-R))*T)
    vals={'physical_survival_approx':exp(-lp*T),'pricing_survival_approx':exp(-lq*T),'survival_principal_pv_approx':survival,
          'immediate_recovery_pv_approx':recovery,'immediate_par_price_approx':immediate,'maturity_recovery_price_approx':delayed,
          'market_value_recovery_price_approx':market,'safe_zero_price_approx':f*exp(-r*T),
          'immediate_par_continuous_spread_approx':-log(immediate/f)/T-r,'maturity_recovery_continuous_spread_approx':-log(delayed/f)/T-r,
          'market_value_recovery_continuous_spread_approx':lq*(1-R)}
    for k,v in vals.items():a.eq(result['continuous'][k],v,'independent density integration '+k)
    a.add('continuous recovery integration and three contractual values')

    inp=data['migration'];n=len(inp['discount_factors']);ds=list(map(F,inp['discount_factors']))
    for name in ['physical','pricing']:
        dist,first,px=migration_enum(inp,name)
        for i,row in enumerate(result['migration'][name+'_rows']):
            previous=F(0) if i==0 else dist[i-1][2]
            vals={'year':i+1,'distribution':[str(x) for x in dist[i]],'cumulative_default':dist[i][2],
                  'marginal_default':first[i],'conditional_default':first[i]/(1-previous),'survival':1-dist[i][2],
                  'discount_factor':ds[i],'first_default_recovery_cash':40*first[i],
                  'principal_cash':100*(1-dist[i][2]) if i==n-1 else F(0),
                  'discounted_probability_weighted_cash':ds[i]*(40*first[i]+(100*(1-dist[i][2]) if i==n-1 else 0))}
            for k,v in vals.items():a.eq(row[k],v,'independent '+name+' path '+str(i)+' '+k)
        a.eq(result['migration'][name+'_weighted_discounted_cash'],px,name+' full path price')
    a.eq(result['migration']['price'],F(23399455,281216),'pricing matrix price')
    a.add('full migration paths, absorption and first-entry cash')

    inp=data['joint'];pa,pb=map(F,inp['marginal_defaults']);face=F(inp['face_each']);LGD=face*(1-F(inp['recovery_fraction']));D=F(inp['discount']);width=F(inp['junior_width'])
    a.eq(result['joint']['frechet_lower'],max(F(0),pa+pb-1),'Frechet lower');a.eq(result['joint']['frechet_upper'],min(pa,pb),'Frechet upper')
    a.eq(result['joint']['loss_given_each_default'],LGD,'LGD in money')
    for row,case in zip(result['joint']['cases'],inp['joint_default_cases']):
        j=F(case['probability']);pp=[1-pa-pb+j,pa-j,pb-j,j];losses=[F(0),LGD,LGD,2*LGD]
        mean=sum(p*x for p,x in zip(pp,losses));jl=sum(p*min(x,width) for p,x in zip(pp,losses));sl=mean-jl
        for state,p,L in zip(row['rows'],pp,losses):
            for k,v in {'probability':p,'pool_loss':L,'junior_loss':min(L,width),'senior_loss':L-min(L,width),
                        'junior_receipt':width-min(L,width),'senior_receipt':2*face-width-(L-min(L,width))}.items():a.eq(state[k],v,'tranche state '+k)
        vals={'joint_probability':j,'default_covariance':j-pa*pb,'default_correlation_approx':float(j-pa*pb)/sqrt(float(pa*(1-pa)*pb*(1-pb))),
              'expected_pool_loss':mean,'pool_loss_variance':sum(p*(L-mean)**2 for p,L in zip(pp,losses)),
              'expected_junior_loss':jl,'expected_senior_loss':sl,'junior_price':D*(width-jl),'senior_price':D*(2*face-width-sl),
              'pool_price':D*(2*face-mean),'probability_loss_above_one_name_loss':j}
        for k,v in vals.items():a.eq(row[k],v,'joint aggregate '+k)
    a.add('complete joint law, feasible dependence and tranche resource closure')

    inp=data['calibration'];F0,T,D,B=[F(inp[k]) for k in ['face','maturity','discount','observed_price']]
    for row in result['calibration']['conditional_calibrations']:
        R=F(row['recovery_fraction']);k=F(row['liquidity_price_multiplier']);ratio=B/(F0*D*k);q=(1-ratio)/(1-R)
        for key,value in {'credit_price_ratio':ratio,'default_probability':q,'intensity_approx':-log(float(1-q))/float(T),
                          'liquidity_yield_wedge_approx':-log(float(k))/float(T),'repriced':F0*D*k*(R*q+1-q),'status':'compatible'}.items():a.eq(row[key],value,'calibration '+key)
    a.eq(result['calibration']['observed_continuous_spread_approx'],-log(float(B/(F0*D)))/float(T),'observed spread convention')
    a.add('all hazard/recovery/liquidity calibrations and repricing')

    def changed(edit):
        x=copy.deepcopy(data);edit(x);return m.run(x)
    cost=changed(lambda d:d['structural'].__setitem__('workout_asset_fraction','.1'))['structural']
    a.eq(cost['debt_price'],F('88.896'),'workout changes resources');a.eq(cost['workout_cost_pv'],F('1.344'),'cost PV');a.eq(str(F(cost['claim_value'])+F(cost['workout_cost_pv'])),F('112.32'),'workout closure')
    phys=changed(lambda d:d['structural'].__setitem__('physical_probabilities',['.2','.5','.3']))['structural']
    a.eq(phys['debt_price'],result['structural']['debt_price'],'P-only change leaves Q price');a.eq(phys['physical_expected_debt_return'],F(1,24),'equal P/Q expected return')
    def no_default(d):d['scheduled']['physical_hazards']=['0']*3;d['scheduled']['pricing_hazards']=['0']*3
    zero=changed(no_default)['scheduled'];a.eq(zero['price_end_date_recovery'],zero['default_free_promised_price'],'zero hazard safe schedule')
    def no_intensity(d):d['continuous']['physical_intensity']='0';d['continuous']['pricing_intensity']='0'
    zero=changed(no_intensity)['continuous']
    for key in ['immediate_par_price_approx','maturity_recovery_price_approx','market_value_recovery_price_approx']:a.eq(zero[key],100*exp(-.03*5),'zero intensity '+key)
    no_rec=changed(lambda d:d['continuous'].__setitem__('recovery_fraction','0'))['continuous']
    for key in ['immediate_par_price_approx','maturity_recovery_price_approx','market_value_recovery_price_approx']:a.eq(no_rec[key],100*exp(-.09*5),'zero recovery '+key)
    singular=changed(lambda d:d['continuous'].__setitem__('short_rate','-.06'))['continuous'];a.eq(singular['immediate_par_price_approx'],112.0,'r plus lambda zero limit')
    full=changed(lambda d:d['continuous'].__setitem__('recovery_fraction','1'))['continuous'];require(full['immediate_par_price_approx']>full['safe_zero_price_approx'],'full-par acceleration');a.eq(full['market_value_recovery_price_approx'],full['safe_zero_price_approx'],'full market recovery')
    def absorbed(d):
        d['migration']['physical_matrix']=[['0','0','1'],['0','0','1'],['0','0','1']]
        d['migration']['pricing_matrix']=copy.deepcopy(d['migration']['physical_matrix'])
    absorbed_result=changed(absorbed)['migration'];a.eq(absorbed_result['price'],F(500,13),'recovery once at year1')
    for row in absorbed_result['pricing_rows'][1:]:a.eq(row['conditional_default'],None,'empty survivor pool');a.eq(row['marginal_default'],F(0),'no repeated default');a.eq(row['first_default_recovery_cash'],F(0),'no repeated recovery')
    for bound in ['0','.1']:
        def boundary(d):
            for row in d['joint']['joint_default_cases']:row['probability']=bound
        val=changed(boundary)['joint']['cases'][0];a.eq(val['expected_pool_loss'],F(12),'marginals preserved at dependence edge');a.eq(val['default_correlation_approx'],-1/9 if bound=='0' else 1.0,'edge correlation')
    def degenerate(d):
        d['joint']['marginal_defaults']=['0','.2']
        for row in d['joint']['joint_default_cases']:row['probability']='0'
    a.eq(changed(degenerate)['joint']['cases'][0]['default_correlation_approx'],None,'degenerate correlation')
    covered=changed(lambda d:d['joint'].__setitem__('recovery_fraction','1'))['joint']['cases'][0]
    a.eq(covered['probability_loss_above_one_name_loss'],F(0),'no-loss probability exact string')
    solvent=changed(lambda d:d['structural'].__setitem__('face','50'))['structural']
    a.eq(solvent['physical_default_probability'],F(0),'no physical default exact string')
    a.eq(solvent['pricing_default_probability'],F(0),'no pricing default exact string')
    def rec_one(d):d['calibration']['recovery_fractions']=['1'];d['calibration']['liquidity_price_multipliers']=['1']
    val=changed(rec_one);a.eq(val['calibration']['conditional_calibrations'][0]['status'],'incompatible','full recovery incompatible quote')
    def unidentified(d):rec_one(d);d['calibration']['observed_price']='90'
    a.eq(changed(unidentified)['calibration']['conditional_calibrations'][0]['status'],'unidentified','full recovery cannot identify hazard')
    def near_certain(d):
        d['calibration'].update({'face':'1000000','discount':'3','observed_price':'1/1000000000000',
                                 'recovery_fractions':['0'],'liquidity_price_multipliers':['1']})
    edge=changed(near_certain)['calibration']['conditional_calibrations'][0]
    a.eq(edge['default_probability'],1-F(1,3*10**18),'near-certain exact probability')
    a.eq(edge['intensity_approx'],(log(3)+18*log(10))/2,'finite intensity from exact tiny survival')
    a.eq(edge['repriced'],F(1,10**12),'near-certain exact repricing')
    a.add('financial interventions and meaningful degenerate boundaries')

    # Every determinate exercise has a separate reconstruction; proof assumptions
    # and the open research critique are additionally audited in the author record.
    ex=copy.deepcopy(data);ex['structural']['face']='120';v=m.run(ex)['structural']
    a.eq(v['debt_price'],F('100.8'),'exercise1 debt');a.eq(v['equity_price'],F('11.52'),'exercise1 equity');a.eq(v['physical_expected_debt_receipt'],F(109),'exercise1 receipt');a.eq(v['physical_expected_debt_return'],F(41,504),'exercise1 return');a.eq(v['promised_simple_yield'],F(4,21),'exercise1 yield');a.eq(v['continuous_promised_spread_approx'],-log(7/8),'exercise1 spread')
    ex['structural'].update({'face':'100','asset_values':['70','80','140','160'],'physical_probabilities':['.1','.3','.3','.3'],'pricing_probabilities':['.2','.25','.25','.3']});v=m.run(ex)['structural']
    for k,val in [('debt_price','85.44'),('equity_price','26.88'),('gross_asset_value','112.32'),('pricing_default_probability','.45')]:a.eq(v[k],F(val),'exercise2 '+k)
    ex=copy.deepcopy(data);ex['scheduled'].update({'coupon_amount':'4','recovery_fraction':'.3','times':['1','2'],'discount_factors':['.95','.90'],'physical_hazards':['.05','.10'],'pricing_hazards':['.05','.10']});v=m.run(ex)['scheduled']
    ep,el,_=event_price(ex['scheduled']);a.eq(v['price_end_date_recovery'],ep,'exercise3 independent paths');a.eq(str(ep),F('87.628'),'exercise3 price');a.eq(v['price_maturity_recovery'],F('87.553'),'exercise3 delayed')
    survivals=[F(1),F('.96'),F('.90'),F('.81')];haz=[1-survivals[i+1]/survivals[i] for i in range(3)]
    a.eq([str(x) for x in haz],['1/25','1/16','1/10'],'exercise4 hazards');a.eq(str(sum(haz)),F('.2025'),'exercise4 nonadditivity');a.eq(str(product(1-h for h in haz)),F('.81'),'exercise4 product')
    for h,expected in zip(haz,[.040821994520255166,.06453852113757118,.10536051565782628]):a.eq(-log(float(1-h)),expected,'exercise4 equivalent intensity')
    ex=copy.deepcopy(data);ex['continuous'].update({'maturity':'4','short_rate':'.02','physical_intensity':'.05','pricing_intensity':'.05'});v=m.run(ex)['continuous']
    quad=100*exp(-.07*4)+simpson(lambda t:40*.05*exp(-.07*t),0,4)
    a.eq(v['immediate_par_price_approx'],quad,'exercise5 recovery integral');a.eq(v['maturity_recovery_price_approx'],100*exp(-.08)*(.4+.6*exp(-.2)),'exercise5 delayed')
    ex['continuous']['short_rate']='-.05';a.eq(m.run(ex)['continuous']['immediate_par_price_approx'],108.0,'exercise5 limit')
    ex['continuous'].update({'maturity':'2','short_rate':'.04','physical_intensity':'.1','pricing_intensity':'.1','recovery_fraction':'1'});v=m.run(ex)['continuous']
    imm=100*exp(-.28)+simpson(lambda t:100*.1*exp(-.14*t),0,2)
    a.eq(v['immediate_par_price_approx'],imm,'exercise6 acceleration');a.eq(v['market_value_recovery_price_approx'],100*exp(-.08),'exercise6 market recovery');a.eq(v['immediate_par_continuous_spread_approx'],-log(imm/100)/2-.04,'exercise6 negative spread')
    ex=copy.deepcopy(data);ex['migration'].update({'initial_state':'B','discount_factors':['25/26','625/676']});v=m.run(ex)['migration']
    _,first,px=migration_enum(ex['migration'],'pricing');a.eq([str(x) for x in first],['1/10','83/1000'],'exercise7 event masses');a.eq(v['price'],px,'exercise7 paths');a.eq(v['price'],F(8575,104),'exercise7 anchor')
    va=F(25,26)*(F('.03')*40+F('.97')*100);vb=F(25,26)*(F('.1')*40+F('.9')*100)
    a.eq(str(F(25,26)*(F('.1')*40+F('.1')*va+F('.8')*vb)),px,'exercise7 independent backward recursion');a.eq(str(vb-va),F(-105,26),'exercise7 migration change')
    ex=copy.deepcopy(data);ex['joint'].update({'marginal_defaults':['.1','.2'],'discount':'.95','joint_default_cases':[{'name':'independent','probability':'.02'},{'name':'alternative','probability':'.04'}]});v=m.run(ex)['joint']
    for row,variance,jl,sl in zip(v['cases'],[900,1044],[F('16.8'),F('15.6')],[F('1.2'),F('2.4')]):
        a.eq(row['expected_pool_loss'],F(18),'exercise8 fixed mean');a.eq(row['pool_loss_variance'],F(variance),'exercise8 variance');a.eq(row['expected_junior_loss'],jl,'exercise8 junior');a.eq(row['expected_senior_loss'],sl,'exercise8 senior')
    a.eq(v['cases'][1]['default_correlation_approx'],1/6,'exercise8 correlation');a.eq(v['cases'][1]['junior_price'],F('42.18'),'exercise8 junior price');a.eq(v['cases'][1]['senior_price'],F('130.72'),'exercise8 senior price')
    ex=copy.deepcopy(data);ex['calibration'].update({'observed_price':'81','recovery_fractions':['.4','.6'],'liquidity_price_multipliers':['1','18/19']});v=m.run(ex)['calibration']
    for row in v['conditional_calibrations']:
        R,k=F(row['recovery_fraction']),F(row['liquidity_price_multiplier']);q=(1-F(81)/(90*k))/(1-R)
        a.eq(row['default_probability'],q,'exercise9 probability');a.eq(row['intensity_approx'],-log(float(1-q))/2,'exercise9 intensity');a.eq(row['repriced'],F(81),'exercise9 identical quote')
    a.add('independent reconstructions for all nine determinate exercises')

    def reject(edit,label):
        x=copy.deepcopy(data);edit(x)
        try:m.validate(x)
        except ValueError:a.rejections+=1
        else:raise AssertionError('invalid input accepted: '+label)
    reject(lambda d:d['structural'].__setitem__('discount',True),'boolean numeric')
    reject(lambda d:d['structural'].__setitem__('face',100.0),'floating numeric')
    reject(lambda d:d['structural'].__setitem__('asset_values',['-1','110','160']),'negative assets')
    reject(lambda d:d['structural'].__setitem__('physical_probabilities',['.1','.6','.4']),'probability sum')
    reject(lambda d:d['structural'].__setitem__('pricing_probabilities',['0','.7','.3']),'nonpositive state price support')
    reject(lambda d:d['structural'].__setitem__('workout_asset_fraction','1.1'),'cost fraction')
    reject(lambda d:d['scheduled'].__setitem__('times',['1','1','3']),'unordered times')
    reject(lambda d:d['scheduled'].__setitem__('discount_factors',['1','0','1']),'zero discount')
    reject(lambda d:d['scheduled'].__setitem__('pricing_hazards',['.02','.03']),'length mismatch')
    reject(lambda d:d['scheduled'].__setitem__('pricing_hazards',['.02','1','.04']),'infinite interval intensity')
    reject(lambda d:d['scheduled'].__setitem__('physical_hazards',['0','.02','.03']),'hazard support mismatch')
    reject(lambda d:d['continuous'].__setitem__('pricing_intensity','-.1'),'negative intensity')
    reject(lambda d:d['continuous'].__setitem__('physical_intensity','0'),'continuous support mismatch')
    reject(lambda d:d['continuous'].__setitem__('recovery_fraction','1.1'),'recovery outside range')
    reject(lambda d:d['continuous'].__setitem__('maturity','0'),'zero maturity')
    reject(lambda d:d['migration']['pricing_matrix'].__setitem__(2,['.1','0','.9']),'nonabsorbing default')
    reject(lambda d:d['migration']['pricing_matrix'].__setitem__(0,['.8','.1','.2']),'invalid transition row')
    reject(lambda d:d['migration']['physical_matrix'].__setitem__(0,['.9','.1','0']),'transition support mismatch')
    reject(lambda d:d['migration'].__setitem__('initial_state','D'),'already-settled claim')
    reject(lambda d:d['joint']['joint_default_cases'][0].__setitem__('probability','.11'),'above Frechet upper')
    reject(lambda d:d['joint']['joint_default_cases'][0].__setitem__('probability','-.01'),'below Frechet lower')
    reject(lambda d:d['joint'].__setitem__('junior_width','200'),'zero senior claim')
    reject(lambda d:d['joint'].__setitem__('physical_equals_pricing',False),'unsupported implicit pricing law')
    reject(lambda d:d['calibration'].__setitem__('recovery_timing','immediate'),'wrong recovery formula contract')
    reject(lambda d:d['calibration'].__setitem__('liquidity_price_multipliers',['0']),'zero liquidity multiplier')
    reject(lambda d:d['conventions'].__setitem__('unit','USD'),'changed fixture convention')
    reject(lambda d:d.__setitem__('hidden_guarantee',True),'unknown field')
    a.add('financial, measure, timing and probability-domain rejections')

    names=[PREFIX+x for x in ['inputs.json','analysis.py','output.json','README.txt']]
    manifest=read(ASSETS/(PREFIX+'manifest.json'));a.eq([v['file'] for v in manifest['files']],names,'complete manifest')
    for row in manifest['files']:
        raw=(ASSETS/row['file']).read_bytes();a.eq(row['bytes'],len(raw),'manifest byte size');a.eq(row['sha256'],hashlib.sha256(raw).hexdigest(),'manifest hash')
    with tempfile.TemporaryDirectory(prefix='fenwick-credit-') as directory:
        base=Path(directory);bundle=base/'bundle';cwd=base/'elsewhere';bundle.mkdir();cwd.mkdir()
        for name in names:shutil.copy2(ASSETS/name,bundle/name)
        for flags in [[],['-O']]:
            p=subprocess.run([sys.executable,'-I','-B']+flags+[str(bundle/(PREFIX+'analysis.py'))],cwd=cwd,capture_output=True,text=True,timeout=30)
            a.eq(p.returncode,0,'portable CLI exit');a.eq(p.stderr,'','portable CLI stderr');a.eq(json.loads(p.stdout),reference,'portable complete output '+str(flags))
        out=cwd/'output.json';p=subprocess.run([sys.executable,'-I','-B',str(bundle/(PREFIX+'analysis.py')),'--input',str(bundle/(PREFIX+'inputs.json')),'--output',str(out)],cwd=cwd,capture_output=True,text=True,timeout=30)
        a.eq(p.returncode,0,'file output exit');a.eq(p.stdout+p.stderr,'','quiet file mode');a.eq(read(out),reference,'complete file output')
    doc=Structure();doc.feed((ROOT/'content/chapters/v10-c04.html').read_text())
    a.eq(doc.h1,0,'no fragment h1');a.eq(len(doc.ids),len(set(doc.ids)),'unique IDs');a.eq(doc.worked,5,'five substantial worked cases');a.eq(doc.exercises,10,'ten graduate exercises');a.eq(doc.solutions,10,'ten ordered solutions')
    for i in range(1,11):require('solution-'+str(i) in doc.ids,'complete solution anchors')
    for name in names+[PREFIX+'manifest.json']:require(name in doc.links,'flat public asset route')
    sources=read(ROOT/'content/reviews/v10-c04-sources.json');a.eq(len(sources),3,'three inspected primary scopes')
    for record in sources:
        require(set(record)==set('id title url use checked verification'.split()),'source record completeness')
        require('sources.html#'+record['id'] in doc.links,'scoped source actually linked')
    a.add('manifest, isolated normal/optimized CLI and teaching structure')
    return {'chapter':'v10-c04','status':'passed','groups':len(a.groups),'comparisons':a.comparisons,'domain_rejections':a.rejections,
            'worked_examples':doc.worked,'complete_exercises':doc.exercises,'group_names':a.groups,
            'limits':'Synthetic-case numerical and domain checks; proof/source audits are separate, and external certification and UI QA are not claimed.'}


if __name__=='__main__':print(json.dumps(check(),indent=2,allow_nan=False))
