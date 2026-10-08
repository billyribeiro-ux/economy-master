"""Quiet independent checks of the original v09-c07 teaching package."""
from collections import Counter
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
from fractions import Fraction as F
import hashlib
from html.parser import HTMLParser
import importlib.util
import io
import json
from math import isclose
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT/'content/projects'


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def load_lab():
    spec = importlib.util.spec_from_file_location('v09_c07_lab', PROJECT/'v09-c07-analysis.py')
    module = importlib.util.module_from_spec(spec)
    capture = io.StringIO()
    with redirect_stdout(capture), redirect_stderr(capture):
        spec.loader.exec_module(module)
    require(not capture.getvalue(), 'Quiet import')
    return module


def run_quiet(lab, data):
    capture = io.StringIO()
    with redirect_stdout(capture), redirect_stderr(capture):
        result = lab.run(data)
    require(not capture.getvalue(), 'Quiet run')
    json.dumps(result, allow_nan=False)
    return result


def fvec(values):
    return [F(x) for x in values]


def pricing_check(lab, data, out):
    rows = out['pricing']['regimes']
    require([F(r['price']) for r in rows] == [98, 94], 'Regime prices')
    require([F(r['expected_return']) for r in rows] == [F(1,49), F(3,47)], 'Conditional means')
    for row, q in zip(rows, [(F(9,20), F(11,20)), (F(7,20), F(13,20))]):
        price = F(row['price'])
        # State-price recovery from bond+claim prices, separate from the lab's price sum.
        recovered_high = (price-80)/40
        require(recovered_high == q[0] and 1-recovered_high == q[1], 'Positive state-price recovery')
        payoff_gains = [120-price, 80-price]
        require(fvec(row['financed_one_share_payoffs']) == payoff_gains and min(payoff_gains) < 0 < max(payoff_gains),
                'Financed gain is risky, not sure arbitrage')
        require(q[0]*payoff_gains[0]+q[1]*payoff_gains[1] == 0, 'Zero price of financed payoff')
        m = fvec(row['SDF']); gross = [F(120)/price, F(80)/price]
        mean = (gross[0]+gross[1])/2-1
        cov = sum((m[i]-1)*(gross[i]-1-mean)/2 for i in range(2))
        require(sum(m)/2 == 1 and sum(m[i]*gross[i]/2 for i in range(2)) == 1, 'SDF moments')
        require(F(row['SDF_return_covariance']) == cov == -mean, 'Conditional covariance compensation')
    require(F(out['pricing']['constant_quiet_benchmark_stress_residual']) == F(100,2303), 'Constant benchmark residual')
    changed = deepcopy(data)
    changed['pricing']['physical'] = ['3/5','2/5']
    for row in changed['pricing']['regimes']:row['state_prices'] = ['2/5','3/5']
    other = run_quiet(lab, changed)['pricing']['regimes'][0]
    require(F(other['price']) == 96 and F(other['expected_return']) == F(1,12) and
            fvec(other['SDF']) == [F(2,3), F(3,2)] and F(other['SDF_return_covariance']) == -F(1,12),
            'Exercise1 different physical probabilities')
    require(F(7,20)*26-F(13,20)*14 == 0 and F(7,20)*26+F(13,20)*14 == F(91,5),
            'Exercise2 previsible versus hindsight payoff price')
    return {'prices':[98,94], 'conditional_means':['1/49','3/47'], 'hindsight_claim_price':'91/5',
            'exercise1_mean':'1/12'}


def sign_enumeration(n, threshold):
    successes = sum(bin(mask).count('1') >= threshold for mask in range(2**n))
    return F(successes, 2**n)


def selection_check(lab, data, out):
    value = out['selection']
    # Independently sum actual +/- CU observations; do not use the lab's count-profit helper.
    candidate_results = []
    for row in data['selection']['rules']:
        train = [1 if c=='+' else -1 for c in row['training']]
        later = [1 if c=='+' else -1 for c in row['holdout']]
        candidate_results.append((sum(train), row['id'], sum(later)))
    ordered = sorted(candidate_results, key=lambda x:(-x[0], x[1]))
    require(ordered[0] == (8,'A01',0) and value['selected_before_holdout'] == 'A01', 'Training-only choice')
    require(F(value['selected_training_net_profit']) == F(34,5) and
            F(value['frozen_holdout_net_profit']) == -F(4,5), 'Common cost ledger')
    one = sign_enumeration(12,10)
    require(one == F(79,4096) == F(value['single_prespecified_rule_tail']), 'Exact sign enumeration')
    # Recursion for the probability at least one independent candidate has crossed.
    hit = F(0)
    for _ in range(20):hit = hit+(1-hit)*one
    require(hit == F(value['independent_family_tail']) and F(value['bonferroni_bound']) == F(395,1024), 'Family and union bound')
    require(isclose(float(hit),value['independent_family_tail_approx'],abs_tol=1e-12,rel_tol=1e-12), 'Named approximate probability')
    require(F(value['frozen_holdout_tail']) == sign_enumeration(8,4) == F(163,256), 'Frozen holdout tail')
    # Future outcomes cannot select the training winner. Make an unselected holdout perfect.
    changed = deepcopy(data);changed['selection']['rules'][19]['holdout'] = '+'*8
    revised = run_quiet(lab,changed)['selection']
    require(revised['selected_before_holdout'] == 'A01' and revised['frozen_holdout_net_profit'] == '-4/5',
            'No holdout leakage into selection')
    changed = deepcopy(data);changed['selection']['rules'][1]['training'] = data['selection']['rules'][0]['training']
    require(run_quiet(lab,changed)['selection']['selected_before_holdout']=='A01', 'Prespecified lexical tie')
    ex4 = sign_enumeration(8,6)
    require(ex4 == F(37,256) and 6-2-8*F(1,5) == F(12,5), 'Exercise4 probability/profit')
    return {'single_tail':'79/4096','twenty_trial_tail_approx':float(hit),
            'frozen_net_profit':'-4/5','exercise4_tail':'37/256',
            'exercise4_family_approx':float(1-(1-ex4)**20)}


def event_information_check(lab,data,out):
    e=out['event']
    buy=F(109)+F(1,4)+1; sell=F(110)-F(1,4)
    require(F(e['entry_cash_including_information'])==buy==F(441,4) and
            F(e['exit_cash_after_fee'])==sell==F(439,4), 'Exercise3 executable cash')
    require(F(e['net_profit'])==sell-buy==-F(1,2) and
            F(e['net_return_on_total_cash'])==(sell-buy)/buy==-F(2,441), 'Return on actual committed cash')
    require(F(e['unavailable_prior_mid_to_exit_mid_return'])==F(11,100) and
            F(e['postrelease_mid_to_mid_return'])==F(1,36), 'Midquote comparisons')
    require(F(e['break_even_information_fee'])==F(1,2), 'Realized fee ceiling')
    changed=deepcopy(data);changed['event']['information_fee']='0'
    free=run_quiet(lab,changed)['event']
    require(F(free['net_return_on_total_cash'])==F(2,437) and F(free['net_profit'])==F(1,2), 'Delayed free-information ledger')
    # Enumerate the two optional decisions instead of reusing the lab information function.
    payoffs=[0,6]; no_info=max(F(1,2)*sum(a*(x-3) for x in payoffs) for a in (0,1))
    informed=F(1,2)*sum(max(a*(x-3) for a in (0,1)) for x in payoffs)
    require(no_info==0 and informed==F(3,2), 'Exercise6 optional decisions')
    info=out['information']
    require(F(info['best_without_information'])==0 and F(info['gross_value_of_information'])==F(3,2) and
            F(info['incremental_value_after_fee'])==F(1,2) and info['optimal_acquisition']=='buy', 'Information value versus cost')
    for fee, status in [('3/2','indifferent'),('2','do_not_buy')]:
        changed=deepcopy(data);changed['information']['fee']=fee
        item=run_quiet(lab,changed)['information']
        require(item['optimal_acquisition']==status and
                F(item['if_signal_fully_reprices_quote_incremental_value'])==-F(fee), 'Information acquisition boundary')
    return {'event_net_return':'-2/441','free_information_return':'2/437','information_value':'3/2'}


def behavior_check(lab,data,out):
    b=out['behavior']
    # Bayes posteriors from joint event masses, then direct central moments.
    actual=F(3,8)/(F(3,8)+F(1,8)); perceived=F(9,20)/(F(9,20)+F(1,20))
    require(F(b['true_posterior'])==actual==F(3,4) and
            F(b['optimistic_posterior'])==perceived==F(9,10), 'Signal likelihood Bayes step')
    for key, belief in [('belief_equilibrium',[actual,perceived]),('correct_belief_counterfactual',[actual,actual])]:
        row=b[key]; price=F(row['price']); positions=fvec(row['holdings']); cash=fvec(row['cash_after_trade'])
        aversions=[F(1,100),F(1,288)]
        require(sum(positions)==2 and sum(cash)==1000, 'Market clearing and cash conservation')
        for i,p in enumerate(belief):
            mean=p*140+(1-p)*60
            variance=p*(140-mean)**2+(1-p)*(60-mean)**2
            curvature=aversions[i]*variance
            require(F(row['subjective_means'][i])==mean and F(row['subjective_variances'][i])==variance,
                    'Subjective distribution, not mean-only adjustment')
            require(F(row['risk_curvatures'][i])==curvature and mean-price-curvature*positions[i]==0,
                    'Individual stationarity at clearing price')
            require(cash[i]==500+price*(1-positions[i]), 'Endowment/position cash budget')
            def criterion(n):return 500+price*(1-n)+n*mean-aversions[i]*n*n*variance/2
            for shift in [F(-2),F(-1,5),F(3,2)]:
                require(criterion(positions[i])-criterion(positions[i]+shift)==curvature*shift**2/2>0,
                        'Strict concavity certificate')
        wealth=[fvec(row['terminal_wealth'][i]) for i in range(2)]
        for s,x in enumerate([140,60]):
            require(sum(wealth[i][s] for i in range(2))==1000+2*x and
                    all(wealth[i][s]==cash[i]+positions[i]*x for i in range(2)), 'Terminal resources')
        q=fvec(row['one_supporting_state_price_vector'])
        require(min(q)>0 and sum(q)==1 and q[0]*140+q[1]*60==price, 'No-arbitrage supporting prices')
    require(F(b['belief_equilibrium']['price'])==F(888,7) and
            fvec(b['belief_equilibrium']['holdings'])==[F(-4,7),F(18,7)], 'Biased-belief equilibrium anchors')
    require(F(b['correct_belief_counterfactual']['price'])==F(11040,97) and
            fvec(b['correct_belief_counterfactual']['holdings'])==[F(50,97),F(144,97)], 'Exercise5 counterfactual')
    require(F(b['price_difference_from_counterfactual'])==F(8856,679), 'Counterfactual price difference')
    gains=fvec(b['one_share_short_terminal_gains'])
    require(gains==[F(-92,7),F(468,7)] and actual*gains[0]+(1-actual)*gains[1]==F(48,7)==F(b['physical_expected_short_gain']),
            'Risky short, positive expectation and possible loss')
    changed=deepcopy(data);changed['behavior']['optimistic_good_likelihoods']=['3/4','1/4']
    same=run_quiet(lab,changed)['behavior']
    require(F(same['price_difference_from_counterfactual'])==0, 'No belief difference means no counterfactual discrepancy')
    return {'price':'888/7','correct_belief_price':'11040/97','short_gains':['-92/7','468/7'],'true_expected_short_gain':'48/7'}


def independent_funding_ledger(wealth,n):
    # Direct cash-account reconstruction with the fixed contractual numbers.
    free=F(wealth)-95*n-21*n
    if free<0:return {'entered':False}
    restricted=F(105*n+21*n)
    additional=F(144*n)-restricted
    survives=free>=additional
    convergence=free+restricted+100*n-100*n-2*n
    if survives:
        free-=additional;restricted+=additional
        closing=[]
        for common in [90,110]:closing.append(free+restricted+common*n-common*n-2*n)
        require(closing[0]==closing[1], 'Exact common payoff cancellation after funding')
        divergence=closing[0]
    else:
        divergence=free+restricted+80*n-120*n-2*n
    return {'entered':True,'survives':survives,'convergence':convergence,'divergence':divergence,
            'expected_gain':F(3,4)*convergence+F(1,4)*divergence-wealth}


def funding_check(lab,data,out):
    row=out['funding']
    require(F(row['initial_long_asset'])+F(row['initial_locked_collateral'])+F(row['initial_free_cash'])-
            F(row['initial_short_liability'])==125, 'Initial funded balance sheet')
    require(F(row['initial_free_cash'])==9 and F(row['stress_topup_required'])==18 and
            F(row['stress_required_collateral'])==144 and not row['stress_margin_survives'], 'Eligible cash versus required margin')
    require(F(row['stress_marked_equity_before_fees'])==95 and F(row['total_fee_at_closing'])==2,
            'Marking is not eligible cash, fee remains due only at closing')
    cases=[]
    for wealth,n in [(125,1),(115,1),(133,1),(134,1),(250,1),(250,2),(250,3),(125,0)]:
        changed=deepcopy(data);changed['funding'].update(wealth=str(wealth),pairs=n)
        actual=run_quiet(lab,changed)['funding']; expected=independent_funding_ledger(wealth,n)
        if not expected['entered']:
            require(actual['status']=='entry_infeasible', 'No fabricated financing for inadmissible pair count')
        else:
            require(actual['status']=='entered' and actual['stress_margin_survives']==expected['survives'], 'Stress liquidity boundary')
            require(F(actual['convergence_final_wealth'])==expected['convergence'] and
                    F(actual['divergence_final_wealth'])==expected['divergence'] and
                    F(actual['physical_expected_net_gain'])==expected['expected_gain'], 'Complete funded path cash ledger')
        require(actual['maximum_entry_pairs']==wealth//116 and actual['maximum_stress_surviving_pairs']==wealth//134,
                'Entry and stress capacity distinguished')
        cases.append({'wealth':wealth,'pairs':n,'entry':expected['entered']})
    for probability, expectation in [('0',8),('1/5',0),('1',-32)]:
        changed=deepcopy(data);changed['funding']['divergence_probability']=probability
        require(F(run_quiet(lab,changed)['funding']['physical_expected_net_gain'])==expectation, 'Physical scenario probability boundaries')
    require(independent_funding_ledger(250,2)['expected_gain']==-4 and
            independent_funding_ledger(250,1)['expected_gain']==8, 'Exercise7 sizing transfer')
    return {'entry_capital_per_pair':116,'stress_capital_per_pair':134,'baseline_expected_gain':-2,
            'exercise7_two_pairs_expected_gain':-4,'exercise7_one_pair_expected_gain':8,'cases':cases}


def domain_check(lab,data):
    invalid=[]
    def bad(label, keys, value):
        changed=deepcopy(data);target=changed
        for key in keys[:-1]:target=target[key]
        target[keys[-1]]=value;invalid.append((label,changed))
    bad('log-label',['conventions','returns'],'log')
    bad('upfront-pair-fees',['conventions','fee_timing'],'paid_at_entry')
    bad('pledgeable-long-label',['conventions','funding'],'long_can_collateralize')
    bad('zero-state-price',['pricing','regimes',0,'state_prices'],['0','1'])
    bad('wrong-safe-price-sum',['pricing','regimes',0,'state_prices'],['1/2','3/4'])
    bad('invalid-physical-probability',['pricing','physical'],['3/2','-1/2'])
    bad('missing-candidate',['selection','rules'],data['selection']['rules'][:-1])
    bad('invalid-return-sign',['selection','rules',0,'training'],'++++++++++00')
    bad('pre-information-execution',['event','entry_minute'],500)
    bad('ask-below-mid',['event','entry_ask'],'100')
    bad('negative-cost',['event','information_fee'],'-1')
    bad('degenerate-signal',['behavior','true_good_likelihoods'],['1','0'])
    bad('zero-risk-curvature',['behavior','risk_aversion'],['0','1/288'])
    bad('nonpositive-pricing-vector',['behavior','supply'],'1000')
    bad('changed-information-contract',['information','contract'],'unlimited_fixed_quote')
    bad('fractional-pairs',['funding','pairs'],'1/2')
    bad('invalid-margin',['funding','maintenance_margin'],'2')
    bad('insolvent-closing-fee',['funding','total_closing_fee_per_pair'],'200')
    bad('binary-float-input',['funding','wealth'],125.0)
    for label,changed in invalid:
        try:run_quiet(lab,changed)
        except ValueError:continue
        raise AssertionError('Invalid fixed-contract input accepted: '+label)
    return [label for label,_ in invalid]


class Chapter(HTMLParser):
    void={'br','hr','img','input','meta','link','col','wbr'}
    def __init__(self):
        super().__init__();self.stack=[];self.ids=[];self.links=[];self.text=[]
        self.worked=self.exercise_count=self.solution_count=0
        self.exercise_depth=self.solution_depth=None
    def handle_starttag(self,tag,attributes):
        a=dict(attributes)
        if tag not in self.void:self.stack.append(tag)
        if 'id' in a:self.ids.append(a['id'])
        if tag=='a':self.links.append(a['href'])
        if a.get('class')=='worked':self.worked+=1
        if tag=='ol' and a.get('class')=='exercises':self.exercise_depth=len(self.stack)
        if tag=='details' and a.get('class')=='solutions':self.solution_depth=len(self.stack)
        if tag=='li' and self.exercise_depth is not None:self.exercise_count+=1
        if tag=='li' and self.solution_depth is not None:self.solution_count+=1
    def handle_endtag(self,tag):
        require(self.stack and self.stack[-1]==tag,'Misnested manuscript tag '+tag)
        if tag=='ol' and self.exercise_depth==len(self.stack):self.exercise_depth=None
        if tag=='details' and self.solution_depth==len(self.stack):self.solution_depth=None
        self.stack.pop()
    def handle_data(self,text):self.text.append(text)


def artifact_check():
    parsed=Chapter();parsed.feed((ROOT/'content/chapters/v09-c07.html').read_text());parsed.close()
    require(not parsed.stack and len(parsed.ids)==len(set(parsed.ids)), 'Chapter nesting and unique anchors')
    require(parsed.worked>=3 and parsed.exercise_count==parsed.solution_count==8,'Full examples/exercises/solutions structure')
    sources=json.loads((ROOT/'content/reviews/v09-c07-sources.json').read_text())
    cited={x.split('#')[1] for x in parsed.links if x.startswith('sources.html#')}
    require(cited=={s['id'] for s in sources},'Exact scoped source proposals for citations')
    expected={f'v09-c07-{s}' for s in ['inputs.json','analysis.py','output.json','README.txt']}
    manifest=json.loads((PROJECT/'v09-c07-manifest.json').read_text())
    require(Counter(x['file'] for x in manifest['files'])==Counter(expected),'Four-file manifest')
    for item in manifest['files']:
        payload=(PROJECT/item['file']).read_bytes()
        require(len(payload)==item['bytes'] and hashlib.sha256(payload).hexdigest()==item['sha256'],'Manifest identity '+item['file'])
    require(expected|{'v09-c07-manifest.json'}<=set(parsed.links),'Flat asset routes')
    require({'v09-c05.html','v09-c06.html','curriculum.html#v09-c08'}<=set(parsed.links),'Exact prerequisite and successor routes')
    return {'worked_examples':parsed.worked,'exercises':parsed.exercise_count,'full_solutions':parsed.solution_count,
            'words':len(re.findall(r'\b[\w’−]+\b',' '.join(parsed.text))),'manifest_files':4,'source_records':len(sources)}


def check():
    lab=load_lab();data=json.loads((PROJECT/'v09-c07-inputs.json').read_text());out=run_quiet(lab,data)
    require(out==json.loads((PROJECT/'v09-c07-output.json').read_text()),'Complete preserved reference equality')
    result={'status':'passed','groups':[
        'Conditional state-price recovery, moments and measurable versus hindsight gains',
        'Independent sign-sequence enumeration, trial-family recursion and frozen evaluation',
        'Executable event cash and optional information decisions, costs and timing',
        'Bayes distributions, market clearing, strict concavity and statewise resources',
        'Separate funding ledgers, exact call boundary, indivisible sizing and closing fees',
        'All determinate exercise anchors and answered delayed transfer checks',
        'Meaningful input-domain and contradictory-contract rejections',
        'Complete output, strict HTML, solved structure, scoped sources and manifest'],
        'anchors':{'pricing':pricing_check(lab,data,out),'selection':selection_check(lab,data,out),
                   'event_information':event_information_check(lab,data,out),'behavior':behavior_check(lab,data,out),
                   'funding':funding_check(lab,data,out)},
        'domain_rejections':domain_check(lab,data),'structure':artifact_check(),
        'limits':'Exact synthetic calculations and artifact checks; full conceptual/source review is separate. No empirical validation, UI QA or human certification.'}
    json.dumps(result,allow_nan=False)
    return result


if __name__=='__main__':
    print(json.dumps(check(),indent=2,allow_nan=False))
