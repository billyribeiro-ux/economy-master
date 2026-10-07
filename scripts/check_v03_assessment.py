"""Independent Volume 3 exam, retention and decision-project audit.

Enumerations/integrals supplement the package's separate written proof review.
"""
from fractions import Fraction as F
from itertools import combinations, permutations, product
from math import comb, exp, log, cosh, sqrt, factorial
from pathlib import Path
from statistics import NormalDist
import importlib.util
import json
from check_v03_moments import moments, covariance, near, simpson
from check_v03_conditioning_limits import binomial, Phi
from check_v03_forecasting_foundations import signal_problem
from check_v03_estimation_inference import exact_interval, holm


def check():
    checks=[]
    assert F(3,4)/(1-F(3,4))==3
    near(simpson(lambda t:2*exp(-2*t),0,20),1-exp(-40))
    for n in range(1,20):assert sum(F(1,2**i) for i in range(1,n+1))==1-F(1,2**n)
    assert 40+35-15==60 and 100-60==40 and 40-15==25

    # Form A: labeled selection avoids assuming equal color configurations.
    selected=[sample for sample in permutations(range(10),3) if sum(i<4 for i in sample)==2]
    assert F(len(selected),10*9*8)==F(3,10)
    assert F(sum(sample[0]<4 for sample in selected),len(selected))==F(2,3)
    near(simpson(lambda t:t*.5*exp(-.5*t),0,100),2,tol=3e-10)
    near(simpson(lambda t:(t-2)**2*.5*exp(-.5*t),0,100),4,tol=3e-9)
    A=[(0,0,F(3,10)),(0,1,F(1,10)),(1,0,F(1,5)),(1,1,F(2,5))]
    X=[x for x,z,w in A];Z=[z for x,z,w in A];weights=[w for x,z,w in A]
    assert moments(X,weights)[0]==F(3,5) and moments(Z,weights)[0]==F(1,2)
    assert covariance(X,Z,weights)==F(1,10)
    assert sum(w*(x-(F(4,5) if z else F(2,5)))**2 for x,z,w in A)==F(1,5)
    near(simpson(lambda x:2/x**2,1,100),2*(1-F(1,100)),tol=1e-7)
    near(simpson(lambda x:2/x,1,100),2*log(100),tol=1e-7)
    for n in (1,10,100):assert n*F(1,n)==1
    means=[F(sum(pair),2) for pair in combinations([0,2,4,6],2)]
    assert moments(means,[F(1,6)]*6)[0::2]==(3,F(5,3))
    normal=NormalDist();near(normal.inv_cdf(.975),1.959963984540054)
    near(1-Phi(1),.15865525393145707)
    near(2*(1-Phi(2)),.04550026389635842)
    assert holm([.012,.028,.070],.05)==[0]
    # Beta posterior's polynomial integral is independent of factorial rule.
    B=lambda a,b:sum(F((-1)**j*comb(b-1,j),a+j) for j in range(b))
    assert B(9,5)/B(8,5)==F(8,13)
    assert B(10,5)/B(8,5)==F(36,91)
    assert B(10,5)/B(8,5)-F(8,13)**2==F(20,1183)
    assert 4*F(5,13)==F(20,13)<10*F(8,13)==F(80,13)
    assert F(4,14)==F(2,7)
    assert sqrt(80*125)==100 and F(80+125,2)-100==F(5,2)
    assert F(1,5)*F(4,5)==F(4,25)
    b,v,pi,c=signal_problem(F(1,4),100,-20,F(4,5),F(1,5))
    assert (b,v,pi)==(10,17,25) and (v-b,pi-b)==(7,15) and v-6>b
    checks.append('Diagnostic and Form A: labeled selections, waiting/tail quadrature, exact joint forecasts, finite-population enumeration, normal/Holm inference, beta predictive dependence and report-fee policies')

    # Form B: Poisson convolution/conditional counts, latent dependence.
    for t in range(12):
        joint=[F(2**a*3**(t-a),factorial(a)*factorial(t-a)) for a in range(t+1)]
        assert sum(joint)==F(5**t,factorial(t))
        if t==4:assert joint[2]/sum(joint)==F(216,625)
    for y in (0,.5,1,2):near(1-exp(-y),simpson(lambda t:exp(-t),0,y))
    latent=[]
    for p,prior in ((F(1,10),F(3,4)),(F(9,10),F(1,4))):
        for a,b in product((0,1),repeat=2):
            latent.append((a,b,prior*(p if a else 1-p)*(p if b else 1-p)))
    assert sum(w*a for a,b,w in latent)==F(3,10)
    assert sum(w*a*b for a,b,w in latent)==F(21,100)
    assert covariance([a for a,b,w in latent],[b for a,b,w in latent],[w for a,b,w in latent])==F(3,25)
    forecasts={0:F(9,70),1:F(7,10)}
    assert sum(w*(b-forecasts[a])**2 for a,b,w in latent)==F(99,700)
    for n in (1,2,10,100):
        variance=(n*5+n*(n-1)*4)/F(n*n)
        assert variance==4+F(1,n)
        near(sqrt(n)*F(1,n),1/sqrt(n))
    near(simpson(lambda u:u**-.5,.01,1),2*(1-.1),tol=2e-6)
    gains=[a+a*b for a,b in product((-1,1),repeat=2)]
    stopped=[a if a==-1 else a+a*b for a,b in product((-1,1),repeat=2)]
    assert sum(gains)==sum(stopped)==0
    estimates=[F(2,3),F(4),F(32,3)];weights=[F(1,2),F(1,4),F(1,4)]
    assert moments([1,3,8],weights)[0]==F(13,4)
    assert moments(estimates,weights)[0::2]==(4,F(50,3))
    near(exact_interval(10,0)[1],1-.025**.1)
    near(1-Phi(normal.inv_cdf(.95)-2),.6387600313123355)
    # Gamma predictive probability via a direct, finite-tail integral.
    gamma=lambda r:7**6/factorial(5)*r**5*exp(-7*r)
    near(simpson(lambda r:exp(-3*r)*gamma(r),0,12),.7**6)
    assert 1/F(4)+1/F(9)==F(13,36)
    assert (F(6,9))/(F(13,36))==F(24,13)
    assert 9+F(36,13)==F(153,13)
    assert F(2,3)/(1+F(2,3))==F(2,5)
    near(-50*log((exp(.2)+exp(-.2))/2),-.993403592000368)
    qjoint=[(q,y,F(1,2)*(p if y else 1-p)) for q,p in ((F(1,10),F(3,10)),(F(9,10),F(7,10))) for y in (0,1)]
    assert sum(w*(q-y)**2 for q,y,w in qjoint)==F(1,4)
    assert sum(w*(F(1,2)-y)**2 for q,y,w in qjoint)==F(1,4)
    b,v,pi,c=signal_problem(F(1,2),60,-40,F(3,4),F(1,4))
    assert (b,v,pi)==(10,F(35,2),30) and v-8<b
    assert signal_problem(F(1,2),60,-40,F(1,2),F(1,2))[1]==10
    checks.append('Form B: exact count convolution/latent states, shared-shock mean variance, L1/L2 spike contrast, predictable/stopped gains, weighted selection, endpoint/power inference and gamma/normal/CARA/garbling checks')

    assert F(3,10)*F(7,10)/100==F(21,10000)
    assert F(21,10000)/F(1,10)**2==F(21,100)
    near(exact_interval(10,0,alpha=.1)[1],.2588655508930523)
    assert B(6,5)/B(5,5)==F(1,2)
    assert B(7,5)/B(5,5)-F(1,4)==F(1,44)
    assert F(2,5)*F(3,5)+(F(4,5)-F(2,5))**2==F(2,5)
    assert signal_problem(F(2,5),60,-20,F(1,2),F(1,2))[0::2]==(12,24)
    checks.append('All five retention domains: exact mean bounds, confidence boundary, posterior covariance, proper forecast losses and perfect-information comparison')

    root=Path(__file__).resolve().parents[1]
    spec=importlib.util.spec_from_file_location('v03_decision_benchmark',root/'content/projects/v03-decision-solution.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    case=json.loads((root/'content/projects/v03-decision-case.json').read_text())
    result=module.solve(case)
    for name,a,b,mean,var in [('prevalence',10,15,F(2,5),F(3,325)),
                             ('sensitivity',32,12,F(8,11),F(8,1815)),
                             ('false_positive',12,48,F(1,5),F(4,1525))]:
        post=result['posteriors'][name]
        assert (post['alpha'],post['beta'],post['mean'],post['variance'])==(a,b,mean,var)
        normalization=B(a,b)
        density=lambda x:x**(a-1)*(1-x)**(b-1)/float(normalization)
        near(simpson(density,0,1),1,tol=3e-9)
        near(simpson(lambda x:x*density(x),0,1),mean,tol=3e-9)
        for target,endpoint in zip((.025,.975),post['credible_equal_tail_95']):
            near(simpson(density,0,endpoint),target,tol=3e-9)
    predictive=result['future_good_count']
    independent=[comb(10,k)*B(10+k,25-k)/B(10,15) for k in range(11)]
    assert predictive['pmf']==independent and sum(independent)==1
    assert moments(list(range(11)),independent)[0::2]==(4,F(42,13))
    assert sum(independent[6:])==F(5519,26970)
    s=result['sampling']
    assert s['mle_bias_reference']==0 and s['mle_variance_reference']==F(3,250)
    for a,b in zip(s['equal_tail_exact_confidence_interval'],exact_interval(20,8)):near(a,b)
    assert s['right_tail_null_pvalue']==sum(binomial(20,F(1,4))[8:])==F(27985830133,274877906944)
    for item in s['coverage_diagnostics']:
        p0=F(str(item['p']));intervals=[exact_interval(20,k) for k in range(21)]
        exact=sum(w for k,w in enumerate(binomial(20,p0)) if intervals[k][0]<=p0<=intervals[k][1])
        near(item['coverage'],exact);assert exact>=F(95,100)
    checks.append('Project: independent beta polynomial versus factorial/quadrature/CDF inversion, exact predictive PMF/moments/tail and separate binomial inference/coverage calculations')

    # Enumerate parameters' one-future joint law directly from posterior moments.
    joint={(1,1):F(16,55),(1,0):F(6,55),(0,1):F(3,25),(0,0):F(12,25)}
    assert sum(joint.values())==1
    riskneutral=result['decisions']['0']
    assert riskneutral['ce_no_report']==18
    assert riskneutral['ce_report_before_fee']==F(1242,55)
    assert riskneutral['maximum_deterministic_fee']==F(252,55)
    assert riskneutral['posterior_reports'][1]['good_probability']==F(80,113)
    assert riskneutral['posterior_reports'][0]['good_probability']==F(5,27)
    for a,ce0,cez in [(0.01,2.784083589606284,14.00108808354229),(.03,0,3.3717948687470156)]:
        row=result['decisions'][str(a)]
        moments0=[1,float(F(2,5))*exp(-a*90)+float(F(3,5))*exp(a*30)]
        min_moment=min(sum(float(w)*exp(-a*((90 if theta else -30) if rule[z] else 0))
                           for (theta,z),w in joint.items()) for rule in product((0,1),repeat=2))
        near(-log(min(moments0))/a,row['ce_no_report']);near(row['ce_no_report'],ce0)
        near(-log(min_moment)/a,row['ce_report_before_fee']);near(row['ce_report_before_fee'],cez)
        # Fee subtraction certified by direct expected-utility scaling.
        for fee in case['fees']:
            fee_moment=min_moment*exp(a*fee)
            near(-log(fee_moment)/a,row['ce_report_before_fee']-fee)
            assert (fee_moment<min(moments0))==(row['maximum_deterministic_fee']>fee)
    assert [r['buy'] for r in riskneutral['fee_comparisons']]==[True,True,False,False]
    assert [r['buy'] for r in result['decisions']['0.01']['fee_comparisons']]==[True]*4
    for item,p,fee in zip(result['prior_sensitivity'],[F(9,22),F(9,20),F(1,3)],[F(501,121),F(237,110),F(86,11)]):
        assert item['posterior']['mean']==p
        direct=signal_problem(p,90,-30,F(8,11),F(1,5))
        assert direct[1]-direct[0]==fee==item['risk_neutral_decision']['maximum_deterministic_fee']
    checks.append('Project: all posterior state/report policies, risk-neutral information and fee bounds, directly scaled CARA exponential moments and exact prior sensitivity')

    # Compare simulation output with an independent exact four-state law.
    simulation=result['simulation'];world={(1,1):F(7,25),(1,0):F(7,100),
                                          (0,1):F(39,400),(0,0):F(221,400)}
    base={0:F(2,5),1:F(2,5)};trained={0:F(5,27),1:F(80,113)}
    sharpened={z:q*q/(q*q+(1-q)**2) for z,q in trained.items()}
    for name,q in [('base',base),('trained',trained),('sharpened',sharpened)]:
        expected_brier=sum(w*(q[z]-theta)**2 for (theta,z),w in world.items())
        expected_log=-sum(float(w)*log(q[z] if theta else 1-q[z]) for (theta,z),w in world.items())
        expected=simulation['reference_world_exact_expected_scores'][name]
        near(expected['brier'],expected_brier);near(expected['log'],expected_log)
        row=simulation['scores'][name]
        for metric,target in [('brier',expected_brier),('log',expected_log)]:
            assert abs(row[metric]['mean']-float(target))<4*row[metric]['estimated_iid_standard_error']
    difference=lambda theta,z:float((trained[z]-theta)**2-(base[z]-theta)**2)
    exact_mean=sum(float(w)*difference(theta,z) for (theta,z),w in world.items())
    exact_variance=sum(float(w)*(difference(theta,z)-exact_mean)**2 for (theta,z),w in world.items())
    paired=simulation['paired_differences_vs_base']['trained']['brier']
    near(paired['mean'],-.09087395183873495)
    assert abs(paired['mean']-exact_mean)<4*sqrt(exact_variance/5000)
    assert abs(paired['estimated_iid_standard_error']-sqrt(exact_variance/5000))<.00015
    assert simulation['calibration_by_report'][0]['n']==3180 and simulation['calibration_by_report'][1]['n']==1820
    assert F(2,5)*F(3,5)/10+F(9,10)*F(3,325)==F(21,650)
    checks.append('Project: reference-world proper-score expectations, exact paired-difference variance, seeded sampling diagnostics and shared-parameter cohort variance')
    return {'status':'passed','checks':checks,
            'limitations':['Finite numerical coverage grids and simulations are diagnostics, not general theorem proofs. Complete written solutions/assumptions and the volume-wide instructional review are recorded separately.']}


if __name__=='__main__':
    print(json.dumps(check(),indent=2))
