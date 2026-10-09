#!/usr/bin/env python3
"""Independent c04 peer arithmetic and input-boundary audit; quiet run()."""
import contextlib
import copy
from decimal import Decimal, localcontext
from fractions import Fraction as F
import hashlib
import importlib.util
import io
from itertools import product
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile

BOOK = Path(__file__).resolve().parents[1]
ASSETS = BOOK / 'content/projects'


def dec(x):
    x = F(x)
    return Decimal(x.numerator) / Decimal(x.denominator)


def mul(xs):
    z = F(1)
    for x in xs:
        z *= x
    return z


def continuous_expected(s):
    # High-precision power-series integration, independent of the author's expm1.
    with localcontext() as ctx:
        ctx.prec = 65
        f,T,r,lp,lq,rho = [dec(s[k]) for k in ('face','maturity','short_rate','physical_intensity','pricing_intensity','recovery_fraction')]
        k = r + lq
        term, integral = T, T
        for n in range(1, 250):
            term *= -k*T/Decimal(n+1)
            integral += term
            if abs(term) < Decimal('1e-60'):
                break
        principal = f * (-k*T).exp()
        recovery = f*rho*lq*integral
        par = principal + recovery
        delayed = f*(-r*T).exp()*(rho+(1-rho)*(-lq*T).exp())
        market = f*(-(r+lq*(1-rho))*T).exp()
        return {k:float(v) for k,v in {
            'physical_survival_approx':(-lp*T).exp(), 'pricing_survival_approx':(-lq*T).exp(),
            'survival_principal_pv_approx':principal, 'immediate_recovery_pv_approx':recovery,
            'immediate_par_price_approx':par, 'maturity_recovery_price_approx':delayed,
            'market_value_recovery_price_approx':market, 'safe_zero_price_approx':f*(-r*T).exp(),
            'immediate_par_continuous_spread_approx':-(par/f).ln()/T-r,
            'maturity_recovery_continuous_spread_approx':-(delayed/f).ln()/T-r,
            'market_value_recovery_continuous_spread_approx':lq*(1-rho)}.items()}


def scheduled_expected(s):
    h = list(map(F, s['pricing_hazards']))
    D = list(map(F, s['discount_factors']))
    n,face,coupon,recovery = len(h),F(s['face']),F(s['coupon_amount']),F(s['face'])*F(s['recovery_fraction'])
    events=[]
    for when in range(n+1):
        prob=mul(1-h[t] for t in range(when))*(h[when] if when<n else 1)
        receipts=[coupon if t<when else F(0) for t in range(n)]
        late=receipts[:]
        if when<n:
            receipts[when]+=recovery;late[-1]+=recovery
        else:
            receipts[-1]+=face;late[-1]+=face
        events.append((prob,receipts,late))
    price=sum(prob*sum(x*d for x,d in zip(cash,D)) for prob,cash,_ in events)
    late=sum(prob*sum(x*d for x,d in zip(cash,D)) for prob,_,cash in events)
    return events,price,late


def migration_expected(s,law):
    M=[list(map(F,row)) for row in s[law+'_matrix']]
    D=list(map(F,s['discount_factors']))
    n,start=len(D),s['states'].index(s['initial_state'])
    distribution=[[F(0)]*3 for _ in range(n)]
    first=[F(0)]*n
    for path in product(range(3), repeat=n):
        full=(start,)+path
        prob=mul(M[full[t]][full[t+1]] for t in range(n))
        for t,state in enumerate(path):
            distribution[t][state]+=prob
        if 2 in path:
            first[path.index(2)]+=prob
    price=F(s['face'])*(F(s['recovery_fraction'])*sum(m*d for m,d in zip(first,D))+(1-sum(first))*D[-1])
    return distribution,first,price


class Audit:
    def __init__(self):
        self.count=0;self.groups=[];self.at=0
    def same(self,got,want,label):
        self.count+=1
        if got!=want:
            raise ValueError(label+': '+repr(got)+' != '+repr(want))
    def exact(self,got,want,label):
        self.count+=1
        if not isinstance(got,str) or F(got)!=F(want):
            raise ValueError(label+': exact mismatch')
    def near(self,got,want,label,absolute=1e-12):
        self.count+=1
        if isinstance(got,bool) or not isinstance(got,(float,int)) or not math.isfinite(got) or not math.isclose(got,float(want),rel_tol=2e-12,abs_tol=absolute):
            raise ValueError(label+': approximate mismatch '+repr(got)+' / '+repr(want))
    def group(self,title):
        self.groups.append({'name':title,'comparisons':self.count-self.at,'status':'passed'});self.at=self.count


def run():
    a=Audit();sys.dont_write_bytecode=True
    data=json.loads((ASSETS/'v10-c04-inputs.json').read_text())
    reference=json.loads((ASSETS/'v10-c04-output.json').read_text())
    before=copy.deepcopy(data);out=io.StringIO();err=io.StringIO()
    with contextlib.redirect_stdout(out),contextlib.redirect_stderr(err):
        spec=importlib.util.spec_from_file_location('c04_peer_sut',ASSETS/'v10-c04-analysis.py')
        m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);actual=m.run(data)
    a.same(out.getvalue()+err.getvalue(),'','quiet model import/run')
    a.same(data,before,'input preserved');a.same(actual,reference,'complete reference reproduction')
    json.dumps(actual,allow_nan=False)

    def structural(s,got):
        face,D,cost=map(F,(s['face'],s['discount'],s['workout_asset_fraction']))
        assets,p,q=[list(map(F,s[k])) for k in ('asset_values','physical_probabilities','pricing_probabilities')]
        debt=[min(v,face)-(cost*v if v<face else 0) for v in assets]
        equity=[v-min(v,face) for v in assets]
        values={
            'debt_price':D*sum(v*w for v,w in zip(debt,q)),
            'equity_price':D*sum(v*w for v,w in zip(equity,q)),
            'gross_asset_value':D*sum(v*w for v,w in zip(assets,q)),
            'workout_cost_pv':D*sum(cost*v*w for v,w in zip(assets,q) if v<face),
            'physical_default_probability':sum(w for v,w in zip(assets,p) if v<face),
            'pricing_default_probability':sum(w for v,w in zip(assets,q) if v<face),
            'physical_expected_debt_receipt':sum(v*w for v,w in zip(debt,p))}
        for key,val in values.items():a.exact(got[key],val,'structural '+key)
        a.exact(got['claim_value'],values['debt_price']+values['equity_price'],'claims add')
        a.exact(got['physical_expected_face_loss'],face-values['physical_expected_debt_receipt'],'expected face loss')
        for i,row in enumerate(got['states']):
            a.exact(row['debt_payoff'],debt[i],'debt state');a.exact(row['equity_payoff'],equity[i],'equity state')
            a.exact(row['claim_sum'],assets[i]-(cost*assets[i] if assets[i]<face else 0),'state resource closure')
            a.exact(row['state_price'],D*q[i],'positive state price')
        if values['debt_price']:
            a.exact(got['physical_expected_debt_return'],values['physical_expected_debt_receipt']/values['debt_price']-1,'expected return')
            a.exact(got['promised_simple_yield'],face/values['debt_price']-1,'promised yield')
            a.near(got['continuous_promised_spread_approx'],-math.log(float(values['debt_price']/(face*D))),'structural log convention')
        return values

    def schedule(s,got):
        events,price,late=scheduled_expected(s)
        a.exact(got['price_end_date_recovery'],price,'exclusive default events')
        a.exact(got['price_maturity_recovery'],late,'delayed recovery events')
        a.exact(got['recovery_timing_value'],price-late,'recovery timing difference')
        n=len(events)-1;D=list(map(F,s['discount_factors']));face=F(s['face']);coupon=F(s['coupon_amount']);rho=F(s['recovery_fraction'])
        for t,row in enumerate(got['pricing_cash_rows']):
            survival=sum(events[i][0] for i in range(t+1,n+1));first=events[t][0]
            a.exact(row['survival'],survival,'coupon survivor probability')
            a.exact(row['marginal_default'],first,'first default probability')
            a.exact(row['survival_coupon'],coupon*survival,'coupon conditional payment')
            a.exact(row['survival_principal'],face*survival if t==n-1 else 0,'dated principal')
            a.exact(row['recovery_at_interval_end'],face*rho*first,'dated recovery')
            a.exact(row['present_value'],sum(prob*cash[t]*D[t] for prob,cash,_ in events),'cash event PV')
        return price,late

    structural(data['structural'],actual['structural'])
    schedule(data['scheduled'],actual['scheduled'])
    for key,val in continuous_expected(data['continuous']).items():a.near(actual['continuous'][key],val,'power-series recovery integration '+key)
    for law in ('physical','pricing'):
        ds,first,price=migration_expected(data['migration'],law)
        a.exact(actual['migration'][law+'_weighted_discounted_cash'],price,'independent '+law+' migration price')
        for i,row in enumerate(actual['migration'][law+'_rows']):
            for v,w in zip(row['distribution'],ds[i]):a.exact(v,w,'migration full-path distribution')
            a.exact(row['marginal_default'],first[i],'first passage')
            a.exact(row['cumulative_default'],sum(first[:i+1]),'absorption accumulation')
            a.exact(row['conditional_default'],first[i]/(1-sum(first[:i])),'surviving risk population')
            a.exact(row['first_default_recovery_cash'],40*first[i],'single recovery')
    a.exact(actual['migration']['price'],F(23399455,281216),'migration worked anchor')
    a.group('Complete reproduction and independent structural/event/integration/migration calculations')

    def joint(s,got):
        pa,pb=map(F,s['marginal_defaults']);L=F(s['face_each'])*(1-F(s['recovery_fraction']));W=F(s['junior_width']);D=F(s['discount']);F0=F(s['face_each'])
        a.exact(got['frechet_lower'],max(F(0),pa+pb-1),'Frechet lower');a.exact(got['frechet_upper'],min(pa,pb),'Frechet upper')
        for case in got['cases']:
            j=F(case['joint_probability']);probs=[1-pa-pb+j,pa-j,pb-j,j];losses=[F(0),L,L,2*L]
            mean=L*(pa+pb);var=L*L*(pa*(1-pa)+pb*(1-pb)+2*(j-pa*pb))
            jl=sum(p*min(x,W) for p,x in zip(probs,losses));sl=mean-jl
            for row,pr,loss in zip(case['rows'],probs,losses):
                a.exact(row['probability'],pr,'joint table')
                a.exact(row['pool_loss'],loss,'pool loss')
                a.exact(row['junior_loss'],min(loss,W),'junior saturation')
                a.exact(row['senior_loss'],max(0,loss-W),'senior attachment')
                a.same(F(row['junior_receipt'])+F(row['senior_receipt']),2*F0-loss,'tranche resource closure')
            for key,val in {'expected_pool_loss':mean,'pool_loss_variance':var,'expected_junior_loss':jl,'expected_senior_loss':sl,'junior_price':D*(W-jl),'senior_price':D*(2*F0-W-sl),'pool_price':D*(2*F0-mean)}.items():a.exact(case[key],val,'joint '+key)
            a.exact(case['probability_loss_above_one_name_loss'],sum(pr for pr,loss in zip(probs,losses) if loss>L),'strict tail')
            denom=pa*(1-pa)*pb*(1-pb)
            if denom:a.near(case['default_correlation_approx'],float(j-pa*pb)/math.sqrt(float(denom)),'indicator correlation')
            else:a.same(case['default_correlation_approx'],None,'undefined correlation')

    def calibration(s,got):
        face,D,B,T=[F(s[k]) for k in ('face','discount','observed_price','maturity')]
        for row in got['conditional_calibrations']:
            R,k=F(row['recovery_fraction']),F(row['liquidity_price_multiplier']);ratio=B/(face*D*k)
            a.exact(row['credit_price_ratio'],ratio,'credit ratio')
            if R==1:
                a.same(row['status'],'unidentified' if ratio==1 else 'incompatible','full recovery status')
                a.same(row['default_probability'],None,'full recovery probability unidentified')
            else:
                q=(1-ratio)/(1-R)
                if 0<=q<1:
                    a.same(row['status'],'compatible','calibration feasible')
                    a.exact(row['default_probability'],q,'conditional q')
                    with localcontext() as ctx:
                        ctx.prec=65;intensity=float(-dec(1-q).ln()/dec(T))
                    a.near(row['intensity_approx'],intensity,'exact-survival log',absolute=1e-35 if q<F(1,10**10) else 1e-12)
                    a.exact(row['repriced'],face*D*k*((1-q)+R*q),'reprice')
                else:a.same(row['status'],'outside finite-intensity model','calibration explicit nonfit')
    joint(data['joint'],actual['joint']);calibration(data['calibration'],actual['calibration'])
    a.group('Joint loss allocation, feasible dependence and complete calibration grid')

    def change(block,values):
        x=copy.deepcopy(data);x[block].update(values)
        with contextlib.redirect_stdout(out),contextlib.redirect_stderr(err):result=m.run(x)
        return x,result

    # Each determinate exercise is reconstructed from its exact prompt.
    x,r=change('structural',{'face':'120'});v=structural(x['structural'],r['structural'])
    a.same([v['debt_price'],v['equity_price'],v['physical_expected_debt_receipt']],[F('100.8'),F('11.52'),F(109)],'exercise1 leverage')
    a.exact(r['structural']['physical_expected_debt_return'],F(41,504),'exercise1 expected return')
    x,r=change('structural',{'asset_values':['70','80','140','160'],'physical_probabilities':['.1','.3','.3','.3'],'pricing_probabilities':['.2','.25','.25','.3']})
    v=structural(x['structural'],r['structural']);a.same([v['debt_price'],v['equity_price'],v['gross_asset_value']],[F('85.44'),F('26.88'),F('112.32')],'exercise2 risk transfer')
    x,r=change('scheduled',{'coupon_amount':'4','recovery_fraction':'.3','times':['1','2'],'discount_factors':['.95','.9'],'physical_hazards':['.05','.1'],'pricing_hazards':['.05','.1']})
    pr,late=schedule(x['scheduled'],r['scheduled']);a.same([pr,late],[F('87.628'),F('87.553')],'exercise3 timing')
    surv=[F(1),F('.96'),F('.9'),F('.81')];haz=[1-b/c for c,b in zip(surv,surv[1:])];masses=[c-b for c,b in zip(surv,surv[1:])]
    a.same(haz,[F('.04'),F('.0625'),F('.1')],'exercise4 conditioning');a.same(masses,[F('.04'),F('.06'),F('.09')],'exercise4 first defaults')
    a.same(sum(haz),F('.2025'),'exercise4 hazards not cumulative');a.same(mul(1-h for h in haz),F('.81'),'exercise4 product')
    for h,target in zip(haz,[.040821994520255166,.06453852113757118,.10536051565782628]):a.near(-math.log(float(1-h)),target,'exercise4 intensities')
    for values,anchor,label in [({'maturity':'4','short_rate':'.02','pricing_intensity':'.05'},82.555981532551,'exercise5 integration'),({'maturity':'4','short_rate':'-.05','pricing_intensity':'.05'},108.,'exercise5 singularity'),({'maturity':'2','short_rate':'.04','pricing_intensity':'.1','recovery_fraction':'1'},93.0223926130204,'exercise6 acceleration')]:
        x,r=change('continuous',values);expected=continuous_expected(x['continuous'])
        for key,val in expected.items():a.near(r['continuous'][key],val,label+' '+key)
        a.near(r['continuous']['immediate_par_price_approx'],anchor,label+' printed anchor',absolute=1e-9)
    x,r=change('migration',{'initial_state':'B','discount_factors':['25/26','625/676']})
    ds,first,price=migration_expected(x['migration'],'pricing')
    a.same(first,[F('.1'),F('.083')],'exercise7 first-default dates');a.exact(r['migration']['price'],price,'exercise7 all paths');a.same(price,F(8575,104),'exercise7 anchor')
    va,vb=F(25,26)*(F('.03')*40+F('.97')*100),F(25,26)*(F('.1')*40+F('.9')*100)
    a.same(F(25,26)*(F('.1')*40+F('.1')*va+F('.8')*vb),price,'exercise7 independent backward price');a.same(vb-va,-F(105,26),'exercise7 downgrade')
    x,r=change('joint',{'marginal_defaults':['.1','.2'],'discount':'.95','joint_default_cases':[{'name':'independent','probability':'.02'},{'name':'alternative','probability':'.04'}]});joint(x['joint'],r['joint'])
    a.exact(r['joint']['cases'][1]['junior_price'],F('42.18'),'exercise8 junior');a.exact(r['joint']['cases'][1]['senior_price'],F('130.72'),'exercise8 senior')
    a.near(-.02/.12,-1/6,'exercise8 correlation lower');a.near(.08/.12,2/3,'exercise8 correlation upper')
    x,r=change('calibration',{'observed_price':'81','recovery_fractions':['.4','.6'],'liquidity_price_multipliers':['1','18/19']});calibration(x['calibration'],r['calibration'])
    a.exact(r['calibration']['conditional_calibrations'][0]['default_probability'],F(1,6),'exercise9 first q');a.exact(r['calibration']['conditional_calibrations'][1]['default_probability'],F(1,12),'exercise9 wedge q')
    a.same(1-F('.81')/F('.9'),F('.1'),'retention conditional versus marginal')
    a.group('Nine determinate exercises and retention; proof/critique audit recorded separately')

    # Boundary repair is tested at both tails, keeping exact probabilities.
    edge={'face':'1000000','discount':'3','observed_price':'1/1000000000000','recovery_fractions':['0'],'liquidity_price_multipliers':['1']}
    x,r=change('calibration',edge);calibration(x['calibration'],r['calibration'])
    a.exact(r['calibration']['conditional_calibrations'][0]['default_probability'],1-F(1,3*10**18),'repaired near-certain q')
    a.near(r['calibration']['conditional_calibrations'][0]['intensity_approx'],(math.log(3)+18*math.log(10))/2,'repaired finite intensity')
    n=999999999999
    x,r=change('calibration',{'face':'1','discount':f'{n}/{n+1}','observed_price':f'{n-1}/{n}','recovery_fractions':['0'],'liquidity_price_multipliers':['1']});calibration(x['calibration'],r['calibration'])
    a.exact(r['calibration']['conditional_calibrations'][0]['default_probability'],F(1,n*n),'tiny positive q retained')
    x,r=change('structural',{'workout_asset_fraction':'.1'});structural(x['structural'],r['structural']);a.exact(r['structural']['workout_cost_pv'],F('1.344'),'workout destroys resources')
    x,r=change('structural',{'face':'50'});structural(x['structural'],r['structural']);a.exact(r['structural']['physical_default_probability'],0,'all-survival P exact zero');a.exact(r['structural']['pricing_default_probability'],0,'all-survival Q exact zero')
    x,r=change('structural',{'physical_probabilities':['.2','.5','.3']});a.same(r['structural']['debt_price'],actual['structural']['debt_price'],'P-only price invariant');a.exact(r['structural']['physical_expected_debt_return'],F(1,24),'P=Q one-period expected rate')
    x,r=change('migration',{'physical_matrix':[['0','0','1']]*3,'pricing_matrix':[['0','0','1']]*3});a.exact(r['migration']['price'],F(500,13),'immediate complete absorption')
    for row in r['migration']['pricing_rows'][1:]:a.same(row['conditional_default'],None,'empty risk set');a.exact(row['first_default_recovery_cash'],0,'no repeat recovery')
    x,r=change('joint',{'recovery_fraction':'1'});joint(x['joint'],r['joint']);a.exact(r['joint']['cases'][0]['probability_loss_above_one_name_loss'],0,'strict zero-loss tail')
    x,r=change('calibration',{'recovery_fractions':['1'],'liquidity_price_multipliers':['1'],'observed_price':'90'});calibration(x['calibration'],r['calibration'])
    x,r=change('calibration',{'recovery_fractions':['.99'],'liquidity_price_multipliers':['1']});calibration(x['calibration'],r['calibration'])
    for values in ({'physical_intensity':'0','pricing_intensity':'0'},{'recovery_fraction':'0'},{'short_rate':'-.1'}):
        x,r=change('continuous',values)
        for key,val in continuous_expected(x['continuous']).items():a.near(r['continuous'][key],val,'continuous boundary '+key)
    a.same(out.getvalue()+err.getvalue(),'','all valid interventions quiet')
    a.group('Repaired calibration tails and economic boundary interventions')

    rejects=[('scheduled','physical_hazards',['0','.02','.03']),('scheduled','pricing_hazards',['.02','1','.04']),('scheduled','times',['1','1','3']),('continuous','physical_intensity','0'),('migration','initial_state','D'),('joint','physical_equals_pricing',False),('joint','joint_default_cases',[{'name':'impossible','probability':'.2'}]),('calibration','recovery_timing','immediate'),('structural','face',100.0)]
    for block,key,value in rejects:
        x=copy.deepcopy(data);x[block][key]=value
        try:m.run(x)
        except ValueError:a.count+=1
        else:raise ValueError('invalid contract accepted: '+block+'.'+key)
    a.group('Nine independent probability, timing and contract rejection probes')

    manifest=json.loads((ASSETS/'v10-c04-manifest.json').read_text())
    for row in manifest['files']:
        raw=(ASSETS/row['file']).read_bytes();a.same(len(raw),row['bytes'],'manifest bytes');a.same(hashlib.sha256(raw).hexdigest(),row['sha256'],'manifest hash')
    author=json.loads((BOOK/'content/reviews/v10-c04-author.json').read_text())
    for row in author['reviewed_hashes']:
        raw=(BOOK/row['path']).read_bytes();a.same(len(raw),row['bytes'],'author bytes');a.same(hashlib.sha256(raw).hexdigest(),row['sha256'],'author payload hash')
    with tempfile.TemporaryDirectory(prefix='c04-independent-peer-') as td:
        folder=Path(td);script=folder/'v10-c04-analysis.py';script.write_bytes((ASSETS/script.name).read_bytes())
        (folder/'v10-c04-inputs.json').write_bytes((ASSETS/'v10-c04-inputs.json').read_bytes())
        elsewhere=folder/'other';elsewhere.mkdir()
        process=subprocess.run([sys.executable,'-I','-B','-O',str(script)],cwd=elsewhere,capture_output=True,text=True,timeout=20)
        a.same(process.returncode,0,'independent isolated optimized CLI');a.same(process.stderr,'','CLI stderr');a.same(json.loads(process.stdout),reference,'CLI full reference')
    a.group('Final manifest/author hashes and independent isolated optimized CLI')
    return {'chapter':'v10-c04','reviewer':'equity_peer','status':'passed','groups':a.groups,'comparisons':a.count,'domain_rejections':len(rejects),'findings_retested':2,
            'limits':'Independent finite calculations and source/proof audit; no author-checker import or oracle, empirical validation, shared acceptance or UI certification.'}


if __name__=='__main__':
    print(json.dumps(run(),indent=2,allow_nan=False))
