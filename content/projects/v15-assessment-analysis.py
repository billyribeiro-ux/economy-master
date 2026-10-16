"""Original synthetic finite policy laboratory; stdlib, exact rational arithmetic."""
from fractions import Fraction as F
from itertools import product
from pathlib import Path
import argparse,json,math,re

def need(ok,message):
    if not ok:raise ValueError(message)
def rational(x):
    need(type(x)in(int,float,str,F),'numeric type; booleans prohibited')
    if type(x)is float:need(math.isfinite(x),'finite number')
    if type(x)is str:need(re.fullmatch(r'-?\d+(?:/\d+)?',x)is not None,'rational string')
    return F(str(x))
def integer(x):
    x=rational(x);need(x.denominator==1,'integer needed');return int(x)
def pack(x):
    if isinstance(x,F):return x.numerator if x.denominator==1 else str(x)
    if isinstance(x,dict):return {k:pack(v)for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [pack(v)for v in x]
    return x

def validate(data):
    need(isinstance(data,dict)and data.get('schema')=='v15-policy-lab-1'and data.get('synthetic')is True,'schema and synthetic flag')
    gs=data['groups'];need(isinstance(gs,list)and len(gs)==4,'four unit-mass groups')
    groups=[]
    for g in gs:
        need(isinstance(g['id'],str)and g['id'],'group ID');mass,income,offset,share,weight=map(rational,(g['mass'],g['income'],g['productivity_offset'],g['damage_share'],g['welfare_weight']));need(mass==1 and income>=0 and offset>=0 and share>=0 and weight>0,'group domain');groups.append((g['id'],income,offset,share,weight))
    need(len({g[0]for g in groups})==4 and sum(g[3]for g in groups)==1,'unique groups and normalized damage shares')
    tech={k:rational(data['technology'][k])for k in ('travel','capacity_cost','administration','abatement_cost','emissions','abatement_reduction')};need(min(tech.values())>=0 and tech['emissions']>=tech['abatement_reduction'],'technology domain')
    menu={k:tuple(map(integer,data['menu'][k]))for k in ('capacity','fee','subsidy','abatement')}
    for name,values in menu.items():need(values and len(values)==len(set(values))and min(values)>=0,'unique nonnegative menu '+name)
    need(0 in menu['capacity']and max(menu['capacity'])<=4 and 0 in menu['fee']and 0 in menu['subsidy']and set(menu['abatement'])<={0,1}and 0 in menu['abatement'],'menu domain')
    reserve=rational(data['treasury']['reserve_limit']);need(reserve>=0 and data['treasury']['refund_rule']=='equal_per_person','treasury domain')
    unc=data['uncertainty'];effects=tuple(map(rational,unc['effects']));damages=tuple(map(rational,unc['damages']));ew=tuple(map(rational,unc['effect_weights']));dw=tuple(map(rational,unc['damage_weights']))
    for values,weights in((effects,ew),(damages,dw)):need(len(values)>=2 and len(values)==len(weights)and len(set(values))==len(values)and min(values)>=0 and min(weights)>0 and sum(weights)==1,'uncertainty domain')
    ev={k:rational(v)for k,v in data['evidence'].items()if k!='selection_bound'};bound=tuple(map(rational,data['evidence']['selection_bound']));need(len(bound)==2 and bound[0]<=bound[1]and ev['holdout_x']!=ev['train_x'],'evidence domain')
    need(data['conventions']=={'participation':'weakly_nonnegative_net_gain_accepts','rationing':'listed_group_priority','policy_ties':'report_all_then_lexicographic_id','uncertainty':'finite_cartesian_sensitivity_states_not_identified_probabilities'},'declared conventions')
    return groups,tech,menu,reserve,effects,damages,ew,dw,ev,bound

def run(data):
    groups,t,menu,limit,effects,damages,ew,dw,ev,bound=validate(data)
    states=[{'id':'T'+str(th)+'D'+str(d),'effect':th,'damage':d,'weight':ep*dp}for th,ep in zip(effects,ew)for d,dp in zip(damages,dw)]
    policies=[(0,0,0,0)]+[(k,f,s,a)for k,f,s,a in product(menu['capacity'],menu['fee'],menu['subsidy'],menu['abatement'])if k>0];policies=sorted(set(policies));rows=[]
    for k,fee,sub,a in policies:
        ident=f'K{k}F{fee}S{sub}A{a}';reserve=k*(t['capacity_cost']+t['administration']+sub)+t['abatement_cost']*a;levy=reserve/4;pre=[g[1]-levy for g in groups];errors=[]
        if reserve>limit:errors.append('reserve_limit')
        if min(pre)<0:errors.append('initial_consumption')
        if k>0 and min(pre)<max(0,fee-sub):errors.append('upfront_user_charge')
        row={'id':ident,'action':[k,fee,sub,a],'reserve':reserve,'levy':levy,'initial_cash':pre,'feasible':not errors,'diagnostics':errors,'states':[]}
        if errors:rows.append(row);continue
        for state in states:
            th,d=state['effect'],state['damage'];wants=[th+g[2]-t['travel']-fee+sub>=0 for g in groups];admitted=[]
            for wants_i in wants:admitted.append(bool(wants_i and sum(admitted)<k))
            m=sum(admitted);gain=[(th+g[2]-t['travel'])*int(z)for g,z in zip(groups,admitted)];production=sum((th+g[2])*int(z)for g,z in zip(groups,admitted));travel=t['travel']*m;emissions=m*(t['emissions']-a*t['abatement_reduction']);damage=d*emissions;realcost=t['capacity_cost']*k+t['administration']*m+t['abatement_cost']*a;expenses=realcost+sub*m;fees=fee*m;refund=reserve+fees-expenses;need(refund>=0,'reserve accounting defect');rebate=refund/4
            consumption=[g[1]+inc+(sub-fee)*int(z)-levy+rebate-g[3]*damage for g,inc,z in zip(groups,gain,admitted)];delta=[c-g[1]for c,g in zip(consumption,groups)];resource=production-travel-realcost-damage;weighted=sum(g[4]*v for g,v in zip(groups,delta));need(sum(delta)==resource and reserve+fees==expenses+refund,'accounting defect')
            state_errors=[]
            if min(consumption)<0:state_errors.append('final_consumption')
            if m>k:state_errors.append('capacity')
            row['states'].append({'state':state['id'],'wants':wants,'admitted':admitted,'participants':m,'production':production,'travel':travel,'emissions':emissions,'damage_loss':damage,'real_public_cost':realcost,'expenses':expenses,'fees':fees,'refund':refund,'consumption':consumption,'delta':delta,'resource_gain':resource,'weighted_gain':weighted,'feasible':not state_errors,'diagnostics':state_errors})
            if state_errors:row['feasible']=False;row['diagnostics'].append(state['id']+':'+','.join(state_errors))
        rows.append(row)
    feasible=[row for row in rows if row['feasible']];need(feasible,'no uniformly feasible policy')
    frontiers=[]
    for j,state in enumerate(states):
        vals=[r['states'][j]['weighted_gain']for r in feasible];best=max(vals);frontiers.append({'state':state['id'],'best':best,'policies':sorted(r['id']for r in feasible if r['states'][j]['weighted_gain']==best)})
    for row in feasible:
        values=[x['weighted_gain']for x in row['states']];regrets=[f['best']-v for f,v in zip(frontiers,values)];row['regrets']=regrets;row['max_regret']=max(regrets);row['expected_weighted']=sum(s['weight']*v for s,v in zip(states,values));row['expected_resource']=sum(s['weight']*x['resource_gain']for s,x in zip(states,row['states']))
    def optimum(field,maximize=True):
        best=(max if maximize else min)(r[field]for r in feasible);return {'value':best,'policies':sorted(r['id']for r in feasible if r[field]==best)}
    # Sharp upper envelope for forecast q on smallest/largest causal effects; damage weights retained.
    lo,hi=min(effects),max(effects);lines=[]
    for row in feasible:
        endpoints=[sum(s['weight']/ew[effects.index(theta)]*z['weighted_gain']for s,z in zip(states,row['states'])if s['effect']==theta)for theta in(lo,hi)];lines.append((row['id'],endpoints[0],endpoints[1]-endpoints[0]))
    envelope=[]
    for ident,intercept,slope in lines:
        lower,upper=F(0),F(1);possible=True
        for _,other_i,other_s in lines:
            ds=slope-other_s;rhs=other_i-intercept
            if ds>0:lower=max(lower,rhs/ds)
            elif ds<0:upper=min(upper,rhs/ds)
            elif rhs>0:possible=False;break
        if possible and lower<=upper:envelope.append({'policy':ident,'intercept':intercept,'slope':slope,'q_interval':[lower,upper]})
    identified_sum=ev['train_treated']-ev['train_untreated'];fits=[]
    for th in effects:
        selection=identified_sum-th;train=ev['baseline_intercept']+ev['baseline_slope']*ev['train_x']+th+selection;holdout=ev['baseline_intercept']+ev['baseline_slope']*ev['holdout_x']+th+selection;fits.append({'effect':th,'selection':selection,'inside_selection_bound':bound[0]<=selection<=bound[1],'train_prediction':train,'train_error':train-ev['train_treated'],'holdout_prediction':holdout,'holdout_error':holdout-ev['holdout_treated']})
    wrong=ev['baseline_intercept']+2*ev['baseline_slope']*ev['holdout_x']+identified_sum
    return pack({'schema':'v15-policy-output-1','states':states,'policy_count':len(rows),'uniformly_feasible_count':len(feasible),'policies':rows,'state_frontiers':frontiers,'expected_weighted_optimum':optimum('expected_weighted'),'expected_resource_optimum':optimum('expected_resource'),'minimax_regret':optimum('max_regret',False),'forecast_envelope':envelope,'evidence':{'identified_sum':identified_sum,'causal_interval':[identified_sum-bound[1],identified_sum-bound[0]],'fits':fits,'wrong_slope_holdout_prediction':wrong,'wrong_slope_holdout_error':wrong-ev['holdout_treated']}})

def main():
    parser=argparse.ArgumentParser();parser.add_argument('input',nargs='?',type=Path);parser.add_argument('output',nargs='?',type=Path);args=parser.parse_args();folder=Path(__file__).resolve().parent;input_path=args.input or folder/'v15-assessment-inputs.json';output_path=args.output or folder/'v15-assessment-output.json'
    protected=[input_path,Path(__file__),folder/'v15-assessment-README.txt',folder/'v15-assessment-manifest.json',folder/'v15-assessment-inputs.json']
    for path in protected:
        need(output_path.resolve()!=path.resolve(),'output aliases protected input/code/README/manifest')
        if output_path.exists()and path.exists():need(not output_path.samefile(path),'hardlink aliases protected payload')
    result=run(json.loads(input_path.read_text()));payload=json.dumps(result,indent=2,sort_keys=True,allow_nan=False)+'\n';output_path.write_text(payload)
if __name__=='__main__':main()
