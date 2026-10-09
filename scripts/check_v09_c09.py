"""Independent arithmetic, contract and portable-package checks for v09-c09."""
import contextlib
import copy
from fractions import Fraction as F
import hashlib
from html.parser import HTMLParser
import importlib.util
import io
import itertools
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT/'content/projects'


def check():
    count = 0
    groups = []
    def ok(condition, label):
        nonlocal count
        count += 1
        if not condition:
            raise AssertionError('v09-c09: '+label)
    def eq(actual, expected, label):
        ok(F(actual)==F(expected), label)
    def near(actual, expected, label):
        ok(math.isclose(float(actual),float(expected),rel_tol=2e-11,abs_tol=2e-11),label)
    spec=importlib.util.spec_from_file_location('v09_c09_analysis',PROJECT/'v09-c09-analysis.py')
    model=importlib.util.module_from_spec(spec)
    capture=io.StringIO()
    with contextlib.redirect_stdout(capture),contextlib.redirect_stderr(capture):
        spec.loader.exec_module(model)
        data=json.loads((PROJECT/'v09-c09-inputs.json').read_text())
        out=model.run(data)
    ok(capture.getvalue()=='','quiet analysis import and run')
    json.dumps(out,allow_nan=False)

    # Independently fit the currency objective from actual state cash flows;
    # use pairwise differences, not the analysis covariance decomposition.
    def liability_oracle(d):
        d={k:F(v) for k,v in d.items()}
        def states(x):
            return [(d['wealth']-x)*d['safe_gross']+x*(d['safe_gross']+d['excess_mean']+d['excess_sign_loading']*u)+d['income_mean']+d['income_u']*u+d['income_v']*v-d['liability_mean']-d['liability_u']*u-d['liability_v']*v for u,v in itertools.product([1,-1],repeat=2)]
        def moments(x):
            s=states(x);mean=sum(s)/4
            variance=sum((a-b)**2 for a in s for b in s)/32
            return mean,variance
        def utility(x):
            m,v=moments(x);return m-d['gamma']*v/2
        f0,f1,f2=(utility(F(x)) for x in range(3))
        second=f2-2*f1+f0
        ok(second<0,'strict currency curvature')
        raw=F(1,2)-(f1-f0)/second
        x=max(F(0),min(d['wealth']-d['reserve'],raw))
        return x,states(x),moments(x),utility(x)
    for label,changes in [('baseline',{}),('exercise income',{'income_u':12}),('higher aversion',{'income_u':12,'gamma':'0.04'}),('reserve binds',{'reserve':40}),('retention',{'liability_u':6})]:
        d=copy.deepcopy(data);d['liability'].update(changes)
        r=model.run(d)['liability'];x,s,(mean,var),u=liability_oracle(d['liability'])
        for key,value in [('risky_cu',x),('safe_cu',F(d['liability']['wealth'])-x),('mean_surplus',mean),('surplus_variance',var),('mean_variance_criterion',u)]:eq(r[key],value,label+' '+key)
        for row,value in zip(r['states'],s):
            eq(row['surplus'],value,label+' state cash')
            eq(F(row['asset_wealth'])+F(row['income'])-F(row['liability']),value,label+' full cash identity')
        ok(F(r['safe_cu'])>=F(d['liability']['reserve']),label+' reserve')
    eq(out['liability']['risky_cu'],70,'baseline exposure')
    eq(out['liability']['mean_variance_criterion'],'43.44','baseline CU score')
    groups.append('Independent state-cash polynomial optimization, pairwise surplus variance, reserve and liability/income interventions')

    def bisect_choice(derivative,lo=0.0,hi=1.0):
        if derivative(lo)<=0:return lo
        if derivative(hi)>=0:return hi
        for _ in range(90):
            middle=(lo+hi)/2
            if derivative(middle)>0:lo=middle
            else:hi=middle
        return (lo+hi)/2
    d=copy.deepcopy(data)
    d['lifecycle']['households'] += [{'name':'exercise risky endowment','wealth':40,'income_intercept':60,'income_exposure':80},{'name':'exercise certain income','wealth':80,'income_intercept':20,'income_exposure':0}]
    rows=model.run(d)['lifecycle']
    law=d['lifecycle'];p=F(law['up_probability']);zs=[F(law['up_gross'])-1,F(law['down_gross'])-1]
    for inp,row in zip(law['households'],rows):
        w,h0,h=(F(inp[k]) for k in ['wealth','income_intercept','income_exposure'])
        probs=[p,1-p]
        def deriv(x):return sum(float(pr*z)/(float(w+h0)+float(z)*(x+float(h))) for pr,z in zip(probs,zs))
        optimum=bisect_choice(deriv,0.0,float(w))
        near(row['risky_cu'],optimum,'bracketed log optimum '+inp['name'])
        x=F(row['risky_cu'])
        eq(row['cash_cu'],w-x,'log cash')
        for i,z in enumerate(zs):
            value=(w-x)+x*(1+z)+h0+h*z
            eq(row['terminal_wealth'][i],value,'log dated resource identity')
        logu=sum(float(pr)*math.log(float(t)) for pr,t in zip(probs,map(F,row['terminal_wealth'])))
        near(row['expected_log_approx'],logu,'log objective from resources')
        ok(deriv(float(x))<=1e-11 if x==0 else (deriv(float(x))>=-1e-11 if x==w else abs(deriv(float(x)))<1e-11),'log boundary/interior certificate')
    eq(rows[0]['risky_cu'],40,'certain young cap')
    eq(rows[3]['risky_cu'],10,'stock-like young')
    eq(rows[4]['objective_derivative'],'-1/6720','exercise no-short derivative')
    eq(rows[5]['financial_fraction'],'5/8','exercise certain fraction')
    changed=copy.deepcopy(data);changed['lifecycle']['up_probability']='0.6'
    ok(model.run(changed)['lifecycle'][2]['risky_cu']!=out['lifecycle'][2]['risky_cu'],'allowed lifecycle probability affects holding')
    groups.append('Bracketed expected-log optima, nontradable resource cash, stock-like endowment and no-borrow/no-short boundaries')

    # No analytic square-root solver is used by this oracle.
    def node_oracle(d,cs=(1.0,1.0)):
        p=float(F(d['up_probability']));z=[float(F(d['up_gross'])-1),float(F(d['down_gross'])-1)]
        probs=[p,1-p]
        def derivative(alpha):return sum(pr*c*x/(1+alpha*x)**2 for pr,c,x in zip(probs,cs,z))
        alpha=bisect_choice(derivative)
        c=sum(pr*cv/(1+alpha*x) for pr,cv,x in zip(probs,cs,z))
        return alpha,c
    def dynamic_audit(d,r,label):
        au,cu=node_oracle(d['after_up']);ad,cd=node_oracle(d['after_down']);a0,c0=node_oracle(d['initial'],(cu,cd))
        for name,a,c in [('after_up',au,cu),('after_down',ad,cd),('initial_optimum',a0,c0)]:
            near(r[name]['risky_fraction_approx'],a,label+' '+name+' policy')
            near(r[name]['continuation_coefficient_approx'],c,label+' '+name+' value')
        p=F(d['initial']['up_probability']);w=float(F(d['wealth']))
        expected=0.0
        i=0
        for k,(prob,gg,alpha,continuation) in enumerate([(p,F(d['initial']['up_gross']),au,d['after_up']),(1-p,F(d['initial']['down_gross']),ad,d['after_down'])]):
            w1=w*(1+a0*float(gg-1))
            p2=F(continuation['up_probability'])
            for prob2,g2 in [(p2,F(continuation['up_gross'])),(1-p2,F(continuation['down_gross']))]:
                risky=w1*alpha;cash=w1-risky;terminal=cash+risky*float(g2)
                row=r['paths'][i];i+=1
                eq(row['probability'],prob*prob2,label+' path probability')
                near(row['risky_cu_at_period1_approx'],risky,label+' intermediate risky funding')
                near(row['cash_cu_at_period1_approx'],cash,label+' intermediate cash funding')
                near(row['terminal_wealth_approx'],terminal,label+' terminal holdings payoff')
                expected-=float(prob*prob2)/terminal
        near(r['optimal_expected_utility_approx'],expected,label+' path utility')
        near(r['certainty_equivalent_terminal_cu_approx'],-1/expected,label+' CE')
        return a0,c0
    dynamic_audit(data['dynamic'],out['dynamic'],'baseline')
    for label,mutate in [('swapped',lambda d:d.update(after_up=data['dynamic']['after_down'],after_down=data['dynamic']['after_up'])),('iid',lambda d:d.update(initial=data['dynamic']['after_down'],after_up=data['dynamic']['after_down'])),('changed initial probability',lambda d:d['initial'].update(up_probability='0.4'))]:
        d=copy.deepcopy(data);mutate(d['dynamic']);r=model.run(d)['dynamic'];dynamic_audit(d['dynamic'],r,label)
        if label=='swapped':
            near(r['initial_optimum']['risky_fraction_approx'],0,'reversed hedge constrained zero')
            near(r['initial_optimum']['marginal_criterion_approx'],-F(1,150),'reversed hedge sign')
            near(r['certainty_equivalent_terminal_cu_approx'],F(3000,29),'reversed CE')
        if label=='iid':
            near(r['initial_optimum']['risky_fraction_approx'],F(2,9),'IID constant policy')
            near(r['optimal_expected_utility_approx'],-F(81,10000),'IID utility')
            near(sum(float(F(q['probability']))*q['terminal_wealth_approx'] for q in r['paths']),F(625,4),'IID expected wealth')
            for row,val in zip(r['paths'],[F(2500,9),F(1250,9),F(1250,9),F(625,9)]):near(row['terminal_wealth_approx'],val,'IID terminal resources')
    best_grid=-math.inf
    d=data['dynamic'];p=float(F(d['initial']['up_probability']))
    for a0,au,ad in itertools.product([i/10 for i in range(11)],repeat=3):
        value=0.0
        for prob,g,alpha,node in [(p,float(F(d['initial']['up_gross'])),au,d['after_up']),(1-p,float(F(d['initial']['down_gross'])),ad,d['after_down'])]:
            w1=100*(1+a0*(g-1));p2=float(F(node['up_probability']))
            for pr,gg in [(p2,float(F(node['up_gross']))),(1-p2,float(F(node['down_gross'])))]:value-=prob*pr/(w1*(1+alpha*(gg-1)))
        best_grid=max(best_grid,value)
    ok(out['dynamic']['optimal_expected_utility_approx']>=best_grid-1e-14,'optimal nonanticipative policy dominates 1331 coarse alternatives')
    near(out['dynamic']['myopic_first_optimal_continuation_eu_approx'],-F(7,750),'myopic-first comparison retains continuation')
    groups.append('Independent bracketed Bellman choices, complete dated tree cash, IID/reversed opportunities and 1331 coarse feasible policy comparisons')

    for label,changes in [('sale',{}),('purchase',{'risky_before':48,'cash_before':64}),('no fee',{'fee_rate':0}),('all cash',{'target':0}),('all risky',{'target':1})]:
        d=copy.deepcopy(data);d['rebalancing'].update(changes);r=model.run(d)['rebalancing']
        p=d['rebalancing'];old,cash,target,fee=(F(p[k]) for k in ['risky_before','cash_before','target','fee_rate']);w=old+cash
        delta=F(r['signed_risky_trade']);paid=F(r['fee_paid'])
        eq(paid,fee*abs(delta),label+' actual fee')
        eq(r['cash_after'],cash-delta-paid,label+' cash paid at trade')
        eq(r['risky_after'],old+delta,label+' signed quantity')
        eq(F(r['risky_after'])+F(r['cash_after'])+paid,w,label+' original resources')
        eq(F(r['risky_after'])/F(r['wealth_after']),target,label+' post-fee target')
        ok(F(r['cash_after'])>=0 and F(r['risky_after'])>=0,label+' no hidden debt')
        # Solve the monotone target equation directly without either trade formula.
        lo,hi=float(-old),float(cash/(1+fee))
        for _ in range(90):
            mid=(lo+hi)/2
            ratio=(float(old)+mid)/(float(w)-float(fee)*abs(mid))
            if ratio<float(target):lo=mid
            else:hi=mid
        near(delta,(lo+hi)/2,label+' independent target solve')
        for row,g in zip(r['next_period_scenarios'],p['next_risky_gross']):
            eq(row['rebalanced_wealth'],(old+delta)*F(g)+cash-delta-paid,label+' next funded holdings')
            eq(row['difference'],delta*(F(g)-1)-paid,label+' scenario difference')
    eq(out['rebalancing']['next_period_scenarios'][0]['difference'],'456/497','down path relative benefit')
    eq(out['rebalancing']['next_period_scenarios'][1]['difference'],'-72/71','up path relative cost')
    groups.append('Post-fee target solved independently with monotonicity; both trade signs, cash/stock endpoints and path-specific outcomes')

    def band_oracle(w,old,mu,v,gamma,fee):
        # Piecewise cash-funded objective; recover each quadratic vertex by
        # interpolation, then compare all feasible endpoints and vertices.
        upper=(w+fee*old)/(1+fee)
        def value(x):return w-fee*abs(x-old)+mu*x-gamma*v*x*x/2
        candidates={F(0),old,upper}
        for l,r in [(F(0),old),(old,upper)]:
            if r==l:continue
            mid=(l+r)/2;fl,fm,fr=value(l),value(mid),value(r)
            slope=(fr-fl)/(r-l);curvature=4*(fr-2*fm+fl)/(r-l)**2
            vertex=mid-slope/curvature
            if l<=vertex<=r:candidates.add(vertex)
        winner=max(candidates,key=value)
        return winner,value(winner)-w,value(old)-w
    for mu,fee,old in [(F(1,25),F(1,100),F(x)) for x in [0,30,55,70,100]]+[(F(1,25),F(1,50),F(70)),(F(1,5),F(1,100),F(70)),(-F(3,100),F(1,100),F(50)),(F(1,25),F(0),F(70))]:
        r=model.band_decision(F(100),old,mu,F(1,25),F(1,50),fee)
        x,score,hold=band_oracle(F(100),old,mu,F(1,25),F(1,50),fee)
        eq(r['risky_after'],x,'piecewise global band optimum')
        eq(r['variable_criterion'],score,'piecewise criterion')
        eq(r['criterion_gain'],score-hold,'piecewise criterion improvement')
        eq(r['cash_after']+r['risky_after']+r['fee_paid'],100,'band resources')
        ok(r['cash_after']>=0,'band cash nonnegative')
    eq(out['bands'][2]['criterion_gain'],'9/400','exercise trade gain')
    top=model.band_decision(F(100),F(70),F(1,5),F(1,25),F(1,50),F(1,100))
    eq(top['risky_after'],'10070/101','funded ceiling exposure')
    eq(top['fee_paid'],'30/101','funded ceiling fee')
    for width in [F(1,50),F(1,200),F(0)]:
        d=copy.deepcopy(data);d['uncertainty']['half_width']=str(width);r=model.run(d)['uncertainty']
        low=F(1,20)-width
        x,score,hold=band_oracle(F(100),F(50),low,F(1,25),F(1,50),F(1,200))
        eq(r['robust']['risky_after'],x,'independent robust choice')
        eq(r['worst_case_variable_criteria']['robust'],score,'common adverse-law score')
        eq(r['worst_case_variable_criteria']['hold'],hold,'common adverse-law hold')
        for y in [F(0),F(175,4),F(50),F(225,4),F(90)]:
            values=[m*y-F(1,2500)*y*y-F(1,200)*abs(y-50) for m in [low,F(1,20),F(1,20)+width]]
            ok(values[0]==min(values),'lower mean is worst for long-only holdings')
        if width==F(1,200):eq(x,50,'narrow interval exact no-trade boundary')
    for key,val in [('hold',F(1,2)),('nominal',F(25,64)),('robust',F(33,64))]:eq(out['uncertainty']['worst_case_variable_criteria'][key],val,'exercise robust score '+key)
    groups.append('Piecewise quadratic interpolation and full funding boundaries; altered fees/means and independently minimized ambiguity criteria')

    for row in out['horizon']:
        t=row['periods'];eq(F(row['cumulative_log_variance'])/t**2,row['average_log_variance'],'cumulative versus average log units')
    d=copy.deepcopy(data);d['horizon']['periods']=[2]
    r=model.run(d)['horizon'][0]
    vals=[F(6,100)+F(1,5)*(u+v) for u,v in itertools.product([-1,1],repeat=2)]
    eq(r['cumulative_log_variance'],sum((v-F(6,100))**2 for v in vals)/4,'independent two-log-state variance')
    for row in out['withdrawals']['paths']:
        gs=[F(x['gross_return']) for x in row['ledger']]
        eq(row['terminal_wealth'],100*gs[0]*gs[1]-10*(gs[1]+1),'contribution-lot withdrawal value')
        for entry in row['ledger']:eq(F(entry['start'])*F(entry['gross_return']),F(entry['payment'])+F(entry['end']),'withdrawal cash')
    eq(out['withdrawals']['listed_minus_reversed'],4,'sequence difference')
    groups.append('Independent log-sum moment example and withdrawal-lot timing identities')

    invalid=[]
    def reject(name,mutator):
        d=copy.deepcopy(data);mutator(d)
        try:model.run(d)
        except (ValueError,TypeError):invalid.append(name)
        else:raise AssertionError('v09-c09 invalid contract accepted: '+name)
    changes=[
      ('real-data-label',lambda d:d.update(provenance='Observed market data')),
      ('wrong-units',lambda d:d.update(units='Percent weights')),
      ('terminal-fee-convention',lambda d:d['conventions'].update(rebalancing='Fee paid after future returns')),
      ('unexpected-field',lambda d:d['liability'].update(ignored_constraint=1)),
      ('binary-float',lambda d:d['liability'].update(gamma=0.02)),
      ('boolean-wealth',lambda d:d['liability'].update(wealth=True)),
      ('nonfinite',lambda d:d['liability'].update(excess_mean='NaN')),
      ('negative-gamma',lambda d:d['liability'].update(gamma=-1)),
      ('impossible-reserve',lambda d:d['liability'].update(reserve=101)),
      ('negative-income-state',lambda d:d['liability'].update(income_u=21)),
      ('riskless-sign-loading',lambda d:d['liability'].update(excess_sign_loading=0)),
      ('nonpositive-risky-gross',lambda d:d['liability'].update(excess_sign_loading=2)),
      ('missing-downside',lambda d:d['dynamic']['initial'].update(down_gross=1)),
      ('zero-state-probability',lambda d:d['dynamic']['initial'].update(up_probability=0)),
      ('negative-dynamic-wealth',lambda d:d['dynamic'].update(wealth=-1)),
      ('negative-human-endowment',lambda d:d['lifecycle']['households'][0].update(income_exposure=400)),
      ('duplicate-household',lambda d:d['lifecycle']['households'].append(d['lifecycle']['households'][0])),
      ('leveraged-target',lambda d:d['rebalancing'].update(target='1.1')),
      ('confiscatory-fee',lambda d:d['rebalancing'].update(fee_rate=1)),
      ('negative-cash',lambda d:d['rebalancing'].update(cash_before=-1)),
      ('negative-scenario-gross',lambda d:d['rebalancing'].update(next_risky_gross=[-1])),
      ('negative-band-variance',lambda d:d['bands'].update(variance=-1)),
      ('borrowed-old-holding',lambda d:d['bands'].update(risky_before=[101])),
      ('impossible-mean-gross',lambda d:d['bands'].update(mean_excess=-1)),
      ('negative-ambiguity-width',lambda d:d['uncertainty'].update(half_width=-1)),
      ('noninteger-period',lambda d:d['horizon'].update(periods=['2'])),
      ('unfunded-payment',lambda d:d['withdrawals'].update(payment=90))]
    for name,mutator in changes:reject(name,mutator)
    ok(len(invalid)==len(changes),'all named domain rejections')
    groups.append('Meaningful provenance, information/fee, finite-number, preference, endowment and solvency contract rejections')

    reference=json.loads((PROJECT/'v09-c09-output.json').read_text())
    ok(out==reference,'complete output regression')
    manifest=json.loads((PROJECT/'v09-c09-manifest.json').read_text())
    ok({r['file'] for r in manifest['files']}=={'v09-c09-'+s for s in ['inputs.json','analysis.py','output.json','README.txt']},'complete four-file manifest')
    for row in manifest['files']:
        payload=(PROJECT/row['file']).read_bytes()
        ok(len(payload)==row['bytes'] and hashlib.sha256(payload).hexdigest()==row['sha256'],'manifest '+row['file'])
    with tempfile.TemporaryDirectory() as folder:
        temp=Path(folder);src=temp/'isolated';src.mkdir();elsewhere=temp/'elsewhere';elsewhere.mkdir()
        for name in ['v09-c09-analysis.py','v09-c09-inputs.json']:shutil.copyfile(PROJECT/name,src/name)
        for mode in [[],['-O']]:
            p=subprocess.run([sys.executable,*mode,str(src/'v09-c09-analysis.py')],cwd=elsewhere,capture_output=True,text=True,check=True)
            ok(not p.stderr and json.loads(p.stdout)==out,'portable default stdin-free execution '+str(mode))
            dest=elsewhere/('result'+str(len(mode))+'.json')
            p=subprocess.run([sys.executable,*mode,str(src/'v09-c09-analysis.py'),'--input',str(src/'v09-c09-inputs.json'),'--output',str(dest)],cwd=elsewhere,capture_output=True,text=True,check=True)
            ok(not p.stdout and not p.stderr and json.loads(dest.read_text())==out,'portable explicit file mode '+str(mode))
        bad=copy.deepcopy(data);bad['conventions']['dynamic']='Hindsight trades';badpath=temp/'bad.json';badpath.write_text(json.dumps(bad))
        p=subprocess.run([sys.executable,'-O',str(src/'v09-c09-analysis.py'),'--input',str(badpath)],cwd=elsewhere,capture_output=True,text=True)
        ok(p.returncode!=0 and 'Contradictory or incomplete model convention' in p.stderr,'optimized Python retains contract validation')
    class Chapter(HTMLParser):
        def __init__(self):super().__init__();self.tags=[];self.classes=[];self.ids=[];self.sources=[];self.text=[];self.links=[]
        def handle_starttag(self,tag,attrs):
            a=dict(attrs);self.tags.append(tag);self.classes.extend(a.get('class','').split())
            if 'id' in a:self.ids.append(a['id'])
            if 'data-source' in a:self.sources.append(a['data-source'])
            if 'href' in a:self.links.append(a['href'])
        def handle_data(self,data):self.text.append(data)
    body=(ROOT/'content/chapters/v09-c09.html').read_text();h=Chapter();h.feed(body)
    ok('h1' not in h.tags,'fragment leaves page title to builder')
    ok(len(h.ids)==len(set(h.ids)),'unique chapter anchors')
    ok(h.classes.count('worked')>=5 and h.classes.count('exercises')==1 and h.classes.count('solutions')==1,'five worked cases and full problem/solution blocks')
    required=['liability','lifecycle','horizon','bellman','rebalancing','cost-band','implementation','exercises','solutions','teach-back']
    ok(all(x in h.ids for x in required),'complete conceptual sections')
    text=' '.join(h.text)
    ok(len(text.split())>=4500 and 'Delayed check' in text and 'Teach back' in text,'substantive instruction and answered retention')
    proposed=json.loads((ROOT/'content/reviews/v09-c09-sources.json').read_text())
    ok(set(h.sources)=={x['id'] for x in proposed},'scoped source proposals match actual citations')
    for suffix in ['inputs.json','analysis.py','output.json','manifest.json','README.txt']:ok('v09-c09-'+suffix in h.links,'offline link '+suffix)
    groups.append('Complete reference output, manifest, isolated normal/optimized CLI, source/HTML boundaries and instructional structure')
    return {'chapter':'v09-c09','status':'pass','groups':len(groups),'comparisons':count,'coarse_feasible_policies':1331,'domain_rejections':len(invalid),'checks':groups,'limits':'Arithmetic, contract and reproducibility evidence for original synthetic models; proofs/source interpretation and independent peer review are separate; no empirical, human-certification or UI claim.'}


if __name__=='__main__':
    print(json.dumps(check(),ensure_ascii=False,indent=2,allow_nan=False))
