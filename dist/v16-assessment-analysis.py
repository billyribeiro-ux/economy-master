"""Original synthetic research rehearsal. Standard library only; no real empirical claim."""
from fractions import Fraction as F
from itertools import product
from pathlib import Path
import json,os,sys

PREFIX='v16-assessment-'

def require(ok,message):
    if not ok:raise ValueError(message)

def rational(value):
    require(type(value) in (str,int),'exact integer or rational string required')
    try:return F(value)
    except (ValueError,ZeroDivisionError) as exc:raise ValueError('invalid rational') from exc

def keys(obj,expected):
    require(type(obj) is dict and set(obj)==set(expected),'unexpected object fields')

def plain(value):
    if isinstance(value,F):return value.numerator if value.denominator==1 else str(value)
    if isinstance(value,dict):return {k:plain(v) for k,v in value.items()}
    if isinstance(value,(tuple,list)):return [plain(v) for v in value]
    return value

def choice(a,cost,h,cap):
    require(h>0 and cap>=0 and a>=0 and cost>=0,'invalid lending model domain')
    return min(cap,max(F(0),(a-cost)/h))

def run(data):
    keys(data,('schema','provenance','banks','ledger','sensitivity','model'))
    require(data['schema']=='v16-research-rehearsal-1','unsupported schema')
    require(type(data['provenance']) is dict and data['provenance'].get('kind')=='original synthetic teaching data','synthetic provenance required')
    require(data['provenance'].get('raw_unit')=='thousand currency units' and data['provenance'].get('analysis_unit')=='million currency units','unit contract')
    banks=data['banks'];require(type(banks) is list and len(banks)==6,'six banks required')
    lookup={};cohorts={};pairs={}
    for b in banks:
        keys(b,('bank','pair','offer','cohort','borrowers'))
        require(all(type(b[k]) is str and b[k] for k in ('bank','pair','cohort')),'nonempty IDs')
        require(b['bank'] not in lookup and b['cohort'] not in cohorts,'unique bank and cohort')
        require(type(b['offer']) is int and b['offer'] in (0,1),'binary integer assignment')
        require(type(b['borrowers']) is int and b['borrowers']>0,'positive cohort size')
        lookup[b['bank']]=b;cohorts[b['cohort']]=b;pairs.setdefault(b['pair'],[]).append(b)
    require(len(pairs)==3 and all(len(p)==2 and sum(b['offer'] for b in p)==1 for p in pairs.values()),'three one-offer pairs')
    require(len({b['borrowers'] for b in banks})==1,'equal cohort size for this target')
    ledger=data['ledger'];require(type(ledger) is list,'ledger list')
    observations={}
    for row in ledger:
        keys(row,('cohort','date','component','revision','value_thousands'))
        require(row['cohort'] in cohorts,'unmatched cohort')
        require(type(row['date']) is int and row['date'] in (0,1),'date0/1')
        require(row['component'] in ('own','other'),'known component')
        require(type(row['revision']) is int and row['revision'] in (0,1),'revision0/1')
        require(type(row['value_thousands']) is int and row['value_thousands']>=0,'observed nonnegative integer stock; missing is not zero')
        key=(row['cohort'],row['date'],row['component'],row['revision']);require(key not in observations,'duplicate exact ledger key');observations[key]=F(row['value_thousands'],1000)
    snapshots={};revisions=[]
    for version in (0,1):
        analysis=[]
        for b in banks:
            r={'bank':b['bank'],'pair':b['pair'],'offer':b['offer'],'cohort':b['cohort']}
            for component in ('own','other'):
                values=[]
                for date in (0,1):
                    candidates=[(rev,v) for (cohort,t,c,rev),v in observations.items() if cohort==b['cohort'] and t==date and c==component and rev<=version]
                    require(bool(candidates),'missing required stock cell')
                    rev,v=max(candidates);values.append(v)
                    if version==1 and rev==1:
                        old=observations.get((b['cohort'],date,component,0));require(old is not None,'restatement needs original version')
                        revisions.append({'cohort':b['cohort'],'date':date,'component':component,'old':old,'new':v,'change':v-old})
                r[component+'_before'],r[component+'_after']=values;r[component+'_change']=values[1]-values[0]
            r['total_before']=r['own_before']+r['other_before'];r['total_after']=r['own_after']+r['other_after'];r['total_change']=r['total_after']-r['total_before'];analysis.append(r)
        pair_rows=[]
        for name in sorted(pairs):
            rows=[r for r in analysis if r['pair']==name];treated=next(r for r in rows if r['offer']);control=next(r for r in rows if not r['offer'])
            pair_rows.append({'pair':name,**{c:treated[c+'_change']-control[c+'_change'] for c in ('own','other','total')}})
        estimate={c:sum(r[c] for r in pair_rows)/3 for c in ('own','other','total')}
        require(estimate['own']+estimate['other']==estimate['total'],'component reconciliation')
        reference=[sum(sign*r['total'] for sign,r in zip(signs,pair_rows))/3 for signs in product((-1,1),repeat=3)]
        tail=sum(abs(v)>=abs(estimate['total']) for v in reference)
        snapshots[str(version)]={'analysis':analysis,'paired_contrasts':pair_rows,'estimate':estimate,'sharp_null':{'reference':reference,'tail':tail,'assignments':len(reference),'p':F(tail,len(reference))}}
    sensitivity=data['sensitivity'];keys(sensitivity,('unrecorded_contrast_bounds','transport_displacement'));bounds=sensitivity['unrecorded_contrast_bounds'];require(type(bounds) is list and len(bounds)==2,'two measurement bounds');lo,hi=map(rational,bounds);require(lo<=hi,'ordered measurement bounds');transport=rational(sensitivity['transport_displacement']);require(transport>=0,'nonnegative transport displacement')
    model=data['model'];keys(model,('a','baseline_cost','types','policies'));a=rational(model['a']);r0=rational(model['baseline_cost']);require(a>=0 and r0>=0,'nonnegative benefit/cost')
    types=model['types'];require(type(types) is list and len(types)==3,'three lending types');parameters=[];seen=set()
    for item in types:
        keys(item,('pair','curvature','capacity','displacement','other_baseline'));name=item['pair'];require(name in pairs and name not in seen,'unique matched model type');seen.add(name)
        h,k,l,o=[rational(item[v]) for v in ('curvature','capacity','displacement','other_baseline')];require(h>0 and k>=0 and l>=0 and o>=0,'model domains');parameters.append((name,h,k,l,o))
    policies=model['policies'];require(type(policies) is list and len(policies)>0,'nonempty policy list');names=set();policy_rows=[]
    for item in policies:
        keys(item,('name','subsidy','budget'));name=item['name'];require(type(name) is str and name and name not in names,'unique policy names');names.add(name)
        subsidy,budget=rational(item['subsidy']),rational(item['budget']);require(0<=subsidy<=r0 and budget>=0,'valid subsidy and budget')
        detail=[]
        for pair,h,k,l,o in parameters:
            x0=choice(a,r0,h,k);x1=choice(a,r0-subsidy,h,k);dx=x1-x0
            detail.append({'pair':pair,'baseline':x0,'offer':x1,'bank_increment':dx,'other_increment':-l*dx,'borrower_increment':(1-l)*dx,'other_after':o-l*dx,'transport_borrower_increment':(1-transport)*dx,'marginal_at_offer':a-(r0-subsidy)-h*x1,'capacity':k})
        spend=subsidy*sum(t['offer'] for t in detail);failures=[]
        if spend>budget:failures.append('subsidy_spending_exceeds_budget')
        if any(t['other_after']<0 for t in detail):failures.append('negative_other_lender_stock')
        if any(o-transport*t['bank_increment']<0 for (_,h,k,l,o),t in zip(parameters,detail)):failures.append('negative_transport_other_stock')
        policy_rows.append({'name':name,'subsidy':subsidy,'budget':budget,'spending':spend,'feasible':not failures,'diagnostics':failures,'mean_bank_increment':sum(t['bank_increment'] for t in detail)/3,'mean_borrower_increment':sum(t['borrower_increment'] for t in detail)/3,'mean_transport_increment':sum(t['transport_borrower_increment'] for t in detail)/3,'types':detail})
    output={'schema':'v16-research-results-1','status':'synthetic_rehearsal_only','raw_records':len(ledger),'analysis_rows_per_snapshot':6,'snapshots':snapshots,'restatements':revisions,'correction_delta':{c:snapshots['1']['estimate'][c]-snapshots['0']['estimate'][c] for c in ('own','other','total')},'measurement_sensitivity':{'unrecorded_contrast_bounds':[lo,hi],'compatible_observed_contrast':[snapshots['1']['estimate']['total']+lo,snapshots['1']['estimate']['total']+hi],'scope':'measurement scenario, not causal confidence interval'},'policies':policy_rows,'limits':['Sharp-null p values concern the stipulated paired lottery and no interference, not a weak-average-effect null.','Structural parameters and displacement are assumed, not identified by fitting three contrasts.','Budget feasibility is not welfare approval; synthetic corrections are not a real-paper replication.']}
    result=plain(output);json.dumps(result,allow_nan=False);return result

def protected_output(output,input_path,code_path):
    protected={input_path,code_path}
    for directory in (code_path.parent,input_path.parent):
        protected.update(directory/(PREFIX+suffix) for suffix in ('inputs.json','analysis.py','README.txt','manifest.json'))
    destination=output.resolve()
    for path in protected:
        if destination==path.resolve():raise ValueError('output aliases protected research input')
        if output.exists() and path.exists() and os.path.samefile(output,path):raise ValueError('output hardlink aliases protected research input')

def main(argv=None):
    argv=sys.argv[1:] if argv is None else argv
    require(len(argv) in (0,2),'usage: python v16-assessment-analysis.py [input.json output.json]')
    code=Path(__file__).resolve();input_path=Path(argv[0]) if argv else code.with_name(PREFIX+'inputs.json');output=Path(argv[1]) if argv else code.with_name(PREFIX+'output.json')
    protected_output(output,input_path,code)
    data=json.loads(input_path.read_text(),parse_constant=lambda x:(_ for _ in ()).throw(ValueError('nonfinite JSON')))
    result=run(data);output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')

if __name__=='__main__':main()
