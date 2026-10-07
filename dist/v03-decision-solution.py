"""Instructor benchmark: exact belief/policy laws and reproducible diagnostics.

Usage: python3 v03-decision-solution.py [v03-decision-case.json]
Standard library only. Money is per decision; synthetic assumptions are explicit.
Simulation verifies behavior in a stated reference world, not theorem validity.
"""
from fractions import Fraction as F
from itertools import product
from math import comb, factorial, exp, log, sqrt
from pathlib import Path
import json
import random
import sys


def beta_integral(a,b):
    return F(factorial(a-1)*factorial(b-1),factorial(a+b-1))


def beta_cdf(x,a,b):
    # Integer-shape identity: differentiate the binomial tail to obtain
    # x^(a-1)(1-x)^(b-1)/B(a,b); both functions vanish at x=0.
    n=a+b-1
    return sum(comb(n,k)*x**k*(1-x)**(n-k) for k in range(a,n+1))


def bisect_probability(fn,target,increasing=True):
    lo,hi=0.,1.
    for _ in range(70):
        mid=(lo+hi)/2
        if (fn(mid)<target)==increasing:lo=mid
        else:hi=mid
    return (lo+hi)/2


def binomial(n,p):
    return [comb(n,k)*p**k*(1-p)**(n-k) for k in range(n+1)]


def interval(n,k,alpha):
    lower=bisect_probability(lambda p:sum(binomial(n,p)[k:]),alpha/2) if k else 0.
    upper=bisect_probability(lambda p:sum(binomial(n,p)[:k+1]),alpha/2,False) if k<n else 1.
    return lower,upper


def posterior(training):
    a,b,k,n=[training[key] for key in ('alpha','beta','successes','trials')]
    if not all(type(x) is int for x in (a,b,k,n)) or min(a,b)<=0 or not 0<=k<=n:
        raise ValueError('Positive integer prior shapes and valid integer trial counts required')
    a+=k;b+=n-k
    return {'alpha':a,'beta':b,'mean':F(a,a+b),
            'variance':F(a*b,(a+b)**2*(a+b+1)),
            'credible_equal_tail_95':[bisect_probability(lambda x:beta_cdf(x,a,b),.025),
                                      bisect_probability(lambda x:beta_cdf(x,a,b),.975)]}


def joint_law(p,s,f):
    return {(1,1):p*s,(1,0):p*(1-s),(0,1):(1-p)*f,(0,0):(1-p)*(1-f)}


def decision(p,s,f,payoff,aversion):
    good,bad,abstain=[F(payoff[key]) for key in ('good','bad','abstain')]
    joint=joint_law(p,s,f)
    reports={z:{'mass':sum(w for (theta,signal),w in joint.items() if signal==z)} for z in (0,1)}
    for z in reports:reports[z]['good_probability']=joint[1,z]/reports[z]['mass']
    if aversion==0:
        constant_values={0:abstain,1:p*good+(1-p)*bad}
        no_information=max(constant_values,key=constant_values.get)
        policies={rule:sum(w*((good if theta else bad) if rule[z] else abstain)
                            for (theta,z),w in joint.items())
                  for rule in product((0,1),repeat=2)}
        best=max(policies,key=policies.get)
        ce0=constant_values[no_information];cez=policies[best]
        pi=p*max(good,abstain)+(1-p)*max(bad,abstain)
        threshold=(abstain-bad)/(good-bad)
    else:
        a=float(aversion)
        # CARA: compare exponential moments, minimizing rather than negating.
        constant={0:exp(-a*abstain),1:float(p)*exp(-a*good)+float(1-p)*exp(-a*bad)}
        no_information=min(constant,key=constant.get)
        policies={rule:sum(float(w)*exp(-a*((good if theta else bad) if rule[z] else abstain))
                            for (theta,z),w in joint.items())
                  for rule in product((0,1),repeat=2)}
        best=min(policies,key=policies.get)
        ce0=-log(constant[no_information])/a;cez=-log(policies[best])/a
        pi=None
        threshold=(exp(-a*bad)-exp(-a*abstain))/(exp(-a*bad)-exp(-a*good))
    return {'posterior_reports':reports,'no_report_invest':bool(no_information),
            'policy_invest_negative_positive':list(map(bool,best)),
            'ce_no_report':ce0,'ce_report_before_fee':cez,
            'maximum_deterministic_fee':cez-ce0,
            'risk_neutral_perfect_information_payoff':pi,
            'invest_probability_threshold':threshold}


def score(forecast,y):
    return (forecast-y)**2,-log(forecast if y else 1-forecast)


def summarize(values):
    n=len(values);mean=sum(values)/n
    variance=sum((v-mean)**2 for v in values)/(n-1)
    return {'mean':mean,'estimated_iid_standard_error':sqrt(variance/n)}


def simulation(case,predicted):
    setting=case['simulation'];rng=random.Random(setting['seed'])
    forecasts={'base':{0:float(predicted['p']),1:float(predicted['p'])},
               'trained':{z:float(predicted['reports'][z]['good_probability']) for z in (0,1)}}
    power=setting['sharpening_power']
    forecasts['sharpened']={z:q**power/(q**power+(1-q)**power) for z,q in forecasts['trained'].items()}
    data=[]
    for _ in range(setting['trials']):
        theta=int(rng.random()<setting['p'])
        likelihood=setting['sensitivity'] if theta else setting['false_positive']
        z=int(rng.random()<likelihood);data.append((theta,z))
    scores={name:{'brier':[],'log':[]} for name in forecasts}
    for theta,z in data:
        for name in forecasts:
            b,l=score(forecasts[name][z],theta)
            scores[name]['brier'].append(b);scores[name]['log'].append(l)
    summary={name:{key:summarize(values) for key,values in losses.items()} for name,losses in scores.items()}
    differences={name:{key:summarize([a-b for a,b in zip(scores[name][key],scores['base'][key])])
                       for key in ('brier','log')} for name in ('trained','sharpened')}
    calibration={}
    for z in (0,1):
        group=[theta for theta,signal in data if signal==z]
        calibration[z]={'n':len(group),'observed_good_rate':sum(group)/len(group),
                        'trained_probability':forecasts['trained'][z]}
    true=joint_law(F(str(setting['p'])),F(str(setting['sensitivity'])),F(str(setting['false_positive'])))
    expected={name:{key:sum(float(w)*score(qs[z],theta)[i] for (theta,z),w in true.items())
                   for i,key in enumerate(('brier','log'))} for name,qs in forecasts.items()}
    return {'seed':setting['seed'],'trials':len(data),'scores':summary,
            'paired_differences_vs_base':differences,'calibration_by_report':calibration,
            'reference_world_exact_expected_scores':expected,
            'interpretation':'Fixed known reference parameters generate iid cases; its iid errors do not justify errors for shared-parameter posterior predictive cohorts or dependent real horizons.'}


def solve(case):
    if not case['payoff']['bad']<case['payoff']['abstain']<case['payoff']['good']:
        raise ValueError('This laboratory requires bad < abstain < good payoffs')
    if case['sampling']['n']!=case['training']['prevalence']['trials']:
        raise ValueError('Observed prevalence inference must use its actual trial count')
    if min(case['risk_aversion'])<0:
        raise ValueError('This benchmark compares risk-neutral and risk-averse preferences')
    posts={name:posterior(t) for name,t in case['training'].items()}
    p,s,f=[posts[name]['mean'] for name in ('prevalence','sensitivity','false_positive')]
    baseline=decision(p,s,f,case['payoff'],0)
    decisions={str(a):decision(p,s,f,case['payoff'],a) for a in case['risk_aversion']}
    for row in decisions.values():
        row['fee_comparisons']=[{'fee':fee,'ce_after_fee':row['ce_report_before_fee']-fee,
                                'buy':row['maximum_deterministic_fee']>fee} for fee in case['fees']]
    a,b=posts['prevalence']['alpha'],posts['prevalence']['beta']
    m=case['future_count_trials']
    predictive=[comb(m,k)*beta_integral(a+k,b+m-k)/beta_integral(a,b) for k in range(m+1)]
    assert sum(predictive)==1
    count_mean=sum(k*w for k,w in enumerate(predictive))
    count_variance=sum((k-count_mean)**2*w for k,w in enumerate(predictive))
    sample=case['sampling'];n=sample['n'];k=case['training']['prevalence']['successes']
    alpha=sample['alpha'];phat=F(k,n)
    intervals=[interval(n,j,alpha) for j in range(n+1)]
    sampling={'observed_mle':phat,'plug_in_se':sqrt(float(phat*(1-phat)/n)),
              'equal_tail_exact_confidence_interval':intervals[k],
              'boundary_zero_interval':intervals[0],
              'right_tail_null_pvalue':sum(binomial(n,F(str(sample['null_p'])))[k:]),
              'coverage_diagnostics':[{'p':p0,'coverage':sum(w for j,w in enumerate(binomial(n,p0))
                    if intervals[j][0]<=p0<=intervals[j][1])} for p0 in sample['coverage_grid']],
              'mle_bias_reference':sum((F(j,n)-F(str(sample['reference_p'])))*w
                    for j,w in enumerate(binomial(n,F(str(sample['reference_p']))))),
              'mle_variance_reference':F(str(sample['reference_p']))*(1-F(str(sample['reference_p'])))/n}
    sensitivities=[]
    for prior in case['prior_sensitivity']:
        t={**case['training']['prevalence'],**prior};post=posterior(t)
        sensitivities.append({'prior':prior,'posterior':post,
                              'risk_neutral_decision':decision(post['mean'],s,f,case['payoff'],0)})
    return {'posteriors':posts,'decisions':decisions,
            'future_good_count':{'pmf':predictive,'mean':count_mean,'variance':count_variance,
                                 'probability_at_least_six':sum(predictive[6:]),
                                 'posterior_mean_binomial_variance':m*p*(1-p)},
            'sampling':sampling,'prior_sensitivity':sensitivities,
            'simulation':simulation(case,{'p':p,'reports':baseline['posterior_reports']})}


def json_safe(value):
    if isinstance(value,F):return {'exact':str(value),'decimal':float(value)}
    if isinstance(value,dict):return {str(k):json_safe(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [json_safe(v) for v in value]
    return value


if __name__=='__main__':
    path=Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).with_name('v03-decision-case.json')
    print(json.dumps(json_safe(solve(json.loads(path.read_text()))),indent=2))
